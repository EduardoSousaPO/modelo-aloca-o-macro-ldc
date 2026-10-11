"""Extrator dos índices da B3 — amplos, setoriais e IFIX — pela API `indexStatisticsProxy`.

F-006 · RF-012 (e-mail **B4**) e RF-013 (e-mail **B5**) · CA-034..039.

A fonte é a **API JSON interna** do portal de listados:

```
GET https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{b64}
b64 = base64(json({"language": "pt-br", "index": "IBOV", "year": "2006"}))
```

Três fatos sobre essa resposta mandam no desenho deste módulo:

1. **É uma matriz dia × mês de um ano**: `results` tem 31 itens (`day` = 1..31) e cada item traz
   `rateValue1..rateValue12` = janeiro..dezembro. Uma série diária só existe depois do *unpivot*
   (CA-034). Uma requisição por **índice × ano** — 11 índices × 21 anos, serializadas.
2. **Os valores são strings pt-BR** (`"38.484,84"`), com ponto de **milhar**. Só
   `para_float_ptbr` converte isso sem erro de escala de 1000x (CA-035).
3. **Ano sem série é HTTP 200 com `{"min":null,"max":null,"results":null}`** — e isso é o caso
   **normal** para ICON antes de 2006, IMOB antes de 2007, IFIX antes de 2010. Corpo de erro de
   verdade (HTML do shell Angular, `{"error": ...}`, JSON inválido) é recusado
   (`RespostaDeErroComStatus200`); ano legitimamente vazio é registrado e seguido adiante.
   Preencher esse vazio seria violar a Anti-SPEC §10.1.1 — **não há backfill aqui**.

Janela por índice (ADR-005): cada série entra com o seu início real medido. O contrato de cada um
é a entrada do catálogo (`packages/shared/schemas/series_catalog_data.py`), inclusive o
`data_inicio` que separa "ano-base com um ponto só" de "ano completo que veio truncado".

Anti-SPEC relevante: §10.1.1 (sem backfill sintético), §10.1.4 (ausência é `None`, nunca `0`),
§10.1.5 (HTTP 200 não é sucesso), §10.4.27 (**proibido** scrapear a página SPA da B3 — só a API).

CLI:

```bash
python -m apps.pipeline.extract.b3_indices                       # tudo: 11 índices, 2006→hoje
python -m apps.pipeline.extract.b3_indices --indices IBOV IFIX
python -m apps.pipeline.extract.b3_indices --anos 2006 2011-2013
python -m apps.pipeline.extract.b3_indices --offline             # relê data/raw/, sem rede
```
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from apps.pipeline.common import (
    ClienteHTTP,
    ErroDeExtracao,
    FonteIndisponivel,
    FormatoDetectado,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    Transporte,
    arquivar_bruto,
    cabecalhos_de_browser,
    caminho_destino_raw,
    gravar_processado_parquet,
    ler_texto,
    obter_logger,
    obtido_em_arquivado,
    para_float_ptbr,
    sha256_de,
)
from apps.pipeline.common.http import CHAVES_DE_ERRO
from packages.shared.schemas import (
    ExtractorConfig,
    Fonte,
    SeriesCatalogEntry,
    StatusSerie,
    load_catalog,
)

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Contrato da fonte
# ─────────────────────────────────────────────────────────────────────────────

#: Caminho do proxy, sem o payload base64 (que entra como último segmento da URL).
BASE_URL_B3 = (
    "https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay"
)

#: A B3 recusa (ou devolve lixo) sem UA de browser; o `Referer` do próprio portal acompanha o UA.
REFERER_B3 = "https://sistemaswebb3-listados.b3.com.br/"

#: Primeiro ano da janela do e-mail ("últimos 20 anos" ≈ 2006 → hoje).
ANO_INICIAL = 2006

#: Pausa entre requisições consecutivas. São ~231 chamadas a uma API interna não documentada:
#: serializar com pausa curta é o que mantém a extração abaixo do radar de volume.
PAUSA_ENTRE_REQUISICOES_S = 0.4

#: Mínimo de fechamentos num ano **completo** de bolsa brasileira (o piso medido é 245; 240 é
#: margem). Entra no `ExtractorConfig.contagem_minima_esperada` — é a guarda anti-truncamento (R2).
PONTOS_MINIMOS_ANO_COMPLETO = 240

#: Mínimo por mês **fechado** do ano corrente (≈ 21 d.u./mês; 15 é margem). Ano corrente não tem
#: 240 pontos por definição, então a guarda dele é proporcional ao calendário.
PONTOS_MINIMOS_POR_MES_CORRENTE = 15

#: Nome de índice na API: 4 letras maiúsculas (`IBOV`, `IEEX`, `IFIL`). Serve para separar os
#: índices do `B3_COTAHIST`, que divide a mesma `Fonte.B3_API` e não passa por este endpoint.
_PADRAO_CODIGO_INDICE = re.compile(r"^[A-Z]{4}$")

_PADRAO_ANOS_CLI = re.compile(r"^(?P<inicio>\d{4})(?:-(?P<fim>\d{4}))?$")

FONTE = Fonte.B3_API.value
FREQ_NATIVA = "D"
UNIDADE = "index"


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo: quem este extrator serve
# ─────────────────────────────────────────────────────────────────────────────


def indices_do_catalogo(
    catalogo: tuple[SeriesCatalogEntry, ...] | None = None,
) -> tuple[SeriesCatalogEntry, ...]:
    """Entradas `B3_API` com `status = ok` cujo identificador é código de índice de 4 letras.

    É o catálogo que decide o universo, não uma lista literal neste arquivo: `IFIL` está como
    `descartada` (é filtro de liquidez, não segmento — ADR-005) e `B3_COTAHIST` como `descartada`
    (fase 2), e os dois saem daqui sozinhos quando a decisão mudar de lado.
    """
    entradas = catalogo if catalogo is not None else load_catalog()
    return tuple(
        e
        for e in entradas
        if e.fonte is Fonte.B3_API
        and e.status is StatusSerie.OK
        and _PADRAO_CODIGO_INDICE.match(e.identificador)
    )


def config_extrator(
    entradas: Sequence[SeriesCatalogEntry],
    *,
    timeout_s: float = 60.0,
    max_retries: int = 3,
) -> ExtractorConfig:
    """`ExtractorConfig` do extrator — um contrato para as N séries da mesma fonte."""
    return ExtractorConfig(
        nome="b3_indices",
        fonte=Fonte.B3_API,
        series_ids=tuple(e.series_id for e in entradas),
        base_url=BASE_URL_B3,
        formato="json",
        encoding="utf-8",
        requer_user_agent_browser=True,
        janela_maxima_dias=None,  # a janela da API é o ano; não se fatia por dias
        contagem_minima_esperada=PONTOS_MINIMOS_ANO_COMPLETO,
        valor_canario=("2006-02-01", 38484.84),
        destino_raw="data/raw/b3",
        timeout_s=timeout_s,
        max_retries=max_retries,
    )


def payload_b64(codigo: str, ano: int) -> str:
    """Último segmento da URL: `base64(json({language, index, year}))`.

    `separators` sem espaço e `year` como **string** reproduzem o payload que o portal manda — foi
    assim que a pesquisa (§B8) mediu a resposta, e é assim que o canário confere.
    """
    corpo = json.dumps(
        {"language": "pt-br", "index": codigo, "year": str(ano)},
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return base64.b64encode(corpo.encode("utf-8")).decode("ascii")


def nome_arquivo_ano(ano: int) -> str:
    """`<ano>.json` — o bruto da B3 é a matriz de um ano inteiro, então o ano **é** a referência."""
    return f"{ano}.json"


# ─────────────────────────────────────────────────────────────────────────────
# Guarda de shape e unpivot
# ─────────────────────────────────────────────────────────────────────────────


def validar_corpo_matriz(
    resposta: RespostaBruta,
    *,
    encoding: str = "utf-8",
) -> list[dict[str, Any]] | None:
    """Recusa corpo de erro com HTTP 200 e devolve `results`; `None` = ano sem série.

    A distinção é o ponto todo (Anti-SPEC §10.1.5 vs. §10.1.1):

    - corpo vazio, HTML (o shell Angular da B3), JSON inválido, objeto com chave de erro ou sem
      `results` → `RespostaDeErroComStatus200`: a resposta **não é utilizável** e nada deve ser
      gravado a partir dela;
    - `{"min": null, "max": null, "results": null}` → `None`: o ano existe, a série ainda não.
      É o que a API devolve para IFIX/2009. Isso não é erro e **também não é zero**.
    """
    origem = resposta.url
    formato = resposta.formato
    if formato is FormatoDetectado.VAZIO:
        msg = f"{origem}: HTTP {resposta.status} com corpo vazio — resposta não utilizável"
        raise RespostaDeErroComStatus200(msg)
    if formato is FormatoDetectado.HTML:
        amostra = resposta.conteudo[:160].decode(encoding, errors="replace")
        msg = (
            f"{origem}: HTTP {resposta.status} com corpo HTML. A API devolveu página, não JSON — "
            f"e scrapear a SPA da B3 é proibido (Anti-SPEC §10.4.27). Amostra: {amostra!r}"
        )
        raise RespostaDeErroComStatus200(msg)

    texto = ler_texto(resposta.conteudo, encoding)
    try:
        corpo = json.loads(texto)
    except json.JSONDecodeError as exc:
        msg = f"{origem}: HTTP {resposta.status} com corpo que não é JSON válido ({exc})"
        raise RespostaDeErroComStatus200(msg) from exc

    if not isinstance(corpo, dict):
        msg = f"{origem}: esperado objeto JSON com 'results', veio {type(corpo).__name__}"
        raise RespostaDeErroComStatus200(msg)

    erradas = sorted(CHAVES_DE_ERRO.intersection(k.lower() for k in corpo))
    if erradas:
        detalhe = "; ".join(f"{k}={corpo.get(k)!r}" for k in erradas)
        raise RespostaDeErroComStatus200(
            f"{origem}: HTTP {resposta.status} com corpo de ERRO (Anti-SPEC §10.1.5). {detalhe}"
        )
    if "results" not in corpo:
        msg = f"{origem}: objeto JSON sem a chave 'results' (chaves: {sorted(corpo)})"
        raise RespostaDeErroComStatus200(msg)

    resultados = corpo["results"]
    if resultados is None or resultados == []:
        return None
    if not isinstance(resultados, list):
        msg = f"{origem}: 'results' deveria ser lista, veio {type(resultados).__name__}"
        raise RespostaDeErroComStatus200(msg)
    for item in resultados:
        if not isinstance(item, dict):
            msg = f"{origem}: item de 'results' não é objeto, veio {type(item).__name__}"
            raise RespostaDeErroComStatus200(msg)
    return resultados


def desempacotar_matriz(
    resultados: Iterable[dict[str, Any]],
    *,
    codigo: str,
    ano: int,
) -> list[tuple[date, float]]:
    """*Unpivot* da matriz dia × mês em `[(data, fechamento)]` ordenado (CA-034).

    Regras, todas verificáveis em teste:

    - `rateValue<m>` mapeia o mês `m` (1 = janeiro); `day` mapeia o dia (CA-034);
    - célula nula/vazia/`"-"`/`"ND"` é **omitida** — nunca `0` (CA-037, Anti-SPEC §10.1.4);
    - a conversão passa sempre por `para_float_ptbr`, então `"38.484,84"` → `38484.84` e nunca
      `38.48` (CA-035);
    - célula **com** valor numa data que não existe (31 de fevereiro) é contradição da fonte e
      levanta `ErroDeExtracao` em vez de virar linha errada.
    """
    pontos: list[tuple[date, float]] = []
    for item in resultados:
        dia = item.get("day")
        if not isinstance(dia, int) or isinstance(dia, bool) or not 1 <= dia <= 31:
            msg = f"{codigo}/{ano}: item de 'results' com 'day' inválido: {dia!r}"
            raise ErroDeExtracao(msg)
        for mes in range(1, 13):
            bruto = item.get(f"rateValue{mes}")
            if bruto is None:
                continue
            valor = para_float_ptbr(bruto, origem=f"{codigo}/{ano} dia={dia} mes={mes}")
            if valor is None:  # "", "-", "ND", "N/A" → ausência, não zero
                continue
            try:
                quando = date(ano, mes, dia)
            except ValueError as exc:
                msg = (
                    f"{codigo}/{ano}: valor {bruto!r} numa data inexistente "
                    f"(dia={dia}, mes={mes}) — matriz inconsistente, nada é gravado"
                )
                raise ErroDeExtracao(msg) from exc
            pontos.append((quando, valor))
    pontos.sort(key=lambda par: par[0])
    exigir_datas_crescentes_e_unicas(pontos, origem=f"{codigo}/{ano}")
    return pontos


def exigir_datas_crescentes_e_unicas(
    pontos: Sequence[tuple[date, float]],
    *,
    origem: str,
) -> None:
    """Datas estritamente crescentes e sem repetição (Validation Mode, `AGENTS.md §15.7`)."""
    anterior: date | None = None
    for quando, _ in pontos:
        if anterior is not None and quando <= anterior:
            relacao = "repetida" if quando == anterior else "fora de ordem"
            msg = f"{origem}: data {relacao} no unpivot: {quando.isoformat()} após {anterior}"
            raise ErroDeExtracao(msg)
        anterior = quando
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Guarda de cobertura por ano (anti-truncamento, usando o catálogo como contrato)
# ─────────────────────────────────────────────────────────────────────────────


def pontos_minimos_do_ano(ano: int, *, entrada: SeriesCatalogEntry, hoje: date) -> int:
    """Quantos fechamentos o ano `ano` **tem** de trazer para esta série, ou `0` se nenhum.

    O contrato é o `data_inicio` medido no catálogo:

    | situação | mínimo |
    |---|---|
    | ano anterior ao ano do `data_inicio` | `0` — a série não existia (ICON/2005, IFIX/2009) |
    | ano **do** `data_inicio` | `1` — pode ser só o ponto-base (CA-036, CA-038) |
    | ano completo já encerrado | `PONTOS_MINIMOS_ANO_COMPLETO` |
    | ano corrente | `15 × meses fechados` |
    | ano futuro | `0` |
    """
    inicio = entrada.data_inicio
    if ano > hoje.year:
        return 0
    if inicio is not None:
        if ano < inicio.year:
            return 0
        if ano == inicio.year:
            return 1
    if ano == hoje.year:
        return PONTOS_MINIMOS_POR_MES_CORRENTE * max(hoje.month - 1, 0)
    return PONTOS_MINIMOS_ANO_COMPLETO


# ─────────────────────────────────────────────────────────────────────────────
# Extração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoIndice:
    """O que uma série rendeu — insumo da matriz de validação e de `wiki/context/F-006.md`."""

    series_id: str
    codigo: str
    linhas: int
    data_inicio_observada: date | None
    data_fim_observada: date | None
    data_inicio_catalogo: date | None
    primeiro_ano_com_dado: int | None
    primeiro_ano_efetivo: int | None
    anos_sem_dado: tuple[int, ...]
    pontos_por_ano: dict[int, int]
    nulos: int
    sha256_por_ano: dict[int, str]
    caminho_parquet: Path | None

    @property
    def pct_nulos(self) -> float:
        """% de `value` nulo no parquet — por construção 0,0: célula vazia é linha omitida."""
        return 0.0 if not self.linhas else 100.0 * self.nulos / self.linhas


def _naive_utc(momento: datetime) -> datetime:
    """UTC sem tzinfo: `RawSeriesSchema` compara `date <= collected_at` em datetime naive."""
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(UTC).replace(tzinfo=None)


def _arquivar_ano(
    conteudo: bytes,
    *,
    destino: Path,
    ano: int,
    origem: str,
    obtido_em: datetime,
    cabecalhos: dict[str, str],
) -> tuple[str, datetime]:
    """Arquiva `<destino>/<ano>.json` e devolve `(sha256, obtido_em efetivo)`.

    Se o conteúdo já arquivado é byte-idêntico, o `obtido_em` **original** é preservado — é o que
    faz o parquet sair igual na segunda rodada (idempotência, `AGENTS.md §15.6`), já que
    `collected_at` sai daqui.
    """
    alvo = destino / nome_arquivo_ano(ano)
    anterior = obtido_em_arquivado(alvo)
    if (
        anterior is not None
        and alvo.is_file()
        and sha256_de(alvo.read_bytes()) == sha256_de(conteudo)
    ):
        obtido_em = anterior
    resultado = arquivar_bruto(
        conteudo,
        destino=destino,
        nome=nome_arquivo_ano(ano),
        origem=origem,
        obtido_em=obtido_em,
        cabecalhos=cabecalhos,
    )
    if resultado.idempotente:
        _log.info("bruto inalterado: %s", resultado.caminho)
    return resultado.sha256, obtido_em


def _ler_ano_arquivado(destino: Path, ano: int) -> tuple[bytes, datetime] | None:
    alvo = destino / nome_arquivo_ano(ano)
    if not alvo.is_file():
        return None
    obtido_em = obtido_em_arquivado(alvo) or datetime.now(tz=UTC)
    return alvo.read_bytes(), obtido_em


def extrair_indice(
    entrada: SeriesCatalogEntry,
    *,
    config: ExtractorConfig,
    anos: Sequence[int],
    cliente: ClienteHTTP | None = None,
    offline: bool = False,
    raiz: Path | None = None,
    hoje: date | None = None,
    dormir: Callable[[float], None] = time.sleep,
    pausa_s: float = PAUSA_ENTRE_REQUISICOES_S,
    gravar: bool = True,
) -> ResultadoIndice:
    """Extrai uma série: ano a ano, arquiva o bruto, faz o unpivot e grava o parquet.

    `offline=True` relê `data/raw/b3/<CODIGO>/<ano>.json` sem tocar a rede — é como a extração é
    reexecutada sem bater 231 vezes na API, e como o teste roda sobre fixture.
    """
    hoje = hoje or datetime.now(tz=UTC).date()
    codigo = entrada.identificador
    destino = caminho_destino_raw(config, raiz=raiz) / codigo
    cabecalhos_extra = {"Referer": REFERER_B3}

    pontos: list[tuple[date, float]] = []
    collected_por_ano: dict[int, datetime] = {}
    pontos_por_ano: dict[int, int] = {}
    sha_por_ano: dict[int, str] = {}
    anos_sem_dado: list[int] = []

    for posicao, ano in enumerate(sorted(set(anos))):
        minimo = pontos_minimos_do_ano(ano, entrada=entrada, hoje=hoje)
        if offline:
            lido = _ler_ano_arquivado(destino, ano)
            if lido is None:
                if minimo == 0:
                    _log.debug("%s/%s: sem bruto e sem série esperada — ignorado", codigo, ano)
                    continue
                msg = (
                    f"{codigo}/{ano}: modo --offline e nenhum bruto em "
                    f"{destino / nome_arquivo_ano(ano)}. Rode uma vez com rede antes"
                )
                raise FonteIndisponivel(msg)
            conteudo, obtido_em = lido
            url = f"{config.base_url}/{payload_b64(codigo, ano)}"
            sha_por_ano[ano] = sha256_de(conteudo)
        else:
            if cliente is None:
                msg = "extrair_indice sem cliente e sem offline=True"
                raise ErroDeExtracao(msg)
            if posicao and pausa_s > 0:
                dormir(pausa_s)
            resposta = cliente.get(payload_b64(codigo, ano), cabecalhos_extra=cabecalhos_extra)
            conteudo, url = resposta.conteudo, resposta.url
            sha, obtido_em = _arquivar_ano(
                conteudo,
                destino=destino,
                ano=ano,
                origem=url,
                obtido_em=resposta.obtida_em,
                cabecalhos=dict(resposta.cabecalhos),
            )
            sha_por_ano[ano] = sha

        resultados = validar_corpo_matriz(
            RespostaBruta(url=url, status=200, conteudo=conteudo, obtida_em=obtido_em),
            encoding=config.encoding,
        )
        if resultados is None:
            if minimo:
                msg = (
                    f"{codigo}/{ano}: a API devolveu 'results: null' num ano que o catálogo diz "
                    f"ter série (data_inicio={entrada.data_inicio}). Mínimo esperado {minimo} — "
                    f"não há licença para preencher isto (Anti-SPEC §10.1.1)"
                )
                raise RespostaTruncada(msg)
            anos_sem_dado.append(ano)
            continue

        do_ano = desempacotar_matriz(resultados, codigo=codigo, ano=ano)
        if not do_ano:
            if minimo:
                msg = f"{codigo}/{ano}: matriz sem nenhuma célula preenchida, mínimo {minimo}"
                raise RespostaTruncada(msg)
            anos_sem_dado.append(ano)
            continue
        if len(do_ano) < minimo:
            msg = (
                f"{codigo}/{ano}: {len(do_ano)} fechamentos, mínimo esperado {minimo} — provável "
                f"truncamento silencioso (R2). Confira o ano na fonte antes de seguir"
            )
            raise RespostaTruncada(msg)
        if minimo == 0:
            _log.warning(
                "%s/%s: %d fechamentos num ano ANTERIOR ao data_inicio do catálogo (%s). O dado "
                "é mantido e a divergência precisa ir para o DECISIONS_LOG",
                codigo,
                ano,
                len(do_ano),
                entrada.data_inicio,
            )

        pontos += do_ano
        pontos_por_ano[ano] = len(do_ano)
        collected_por_ano[ano] = obtido_em

    pontos.sort(key=lambda par: par[0])
    exigir_datas_crescentes_e_unicas(pontos, origem=f"{codigo} (série completa)")

    quadro = _montar_quadro(
        pontos,
        series_id=entrada.series_id,
        collected_por_ano=collected_por_ano,
    )
    caminho = None
    if gravar and not quadro.empty:
        caminho = gravar_processado_parquet(
            quadro, nome=f"b3/{entrada.series_id}.parquet", raiz=raiz
        )

    anos_com_dado = sorted(pontos_por_ano)
    efetivos = [a for a in anos_com_dado if pontos_por_ano[a] >= PONTOS_MINIMOS_ANO_COMPLETO]
    return ResultadoIndice(
        series_id=entrada.series_id,
        codigo=codigo,
        linhas=len(quadro),
        data_inicio_observada=pontos[0][0] if pontos else None,
        data_fim_observada=pontos[-1][0] if pontos else None,
        data_inicio_catalogo=entrada.data_inicio,
        primeiro_ano_com_dado=anos_com_dado[0] if anos_com_dado else None,
        primeiro_ano_efetivo=efetivos[0] if efetivos else None,
        anos_sem_dado=tuple(anos_sem_dado),
        pontos_por_ano=pontos_por_ano,
        nulos=int(quadro["value"].isna().sum()) if not quadro.empty else 0,
        sha256_por_ano=sha_por_ano,
        caminho_parquet=caminho,
    )


def _montar_quadro(
    pontos: Sequence[tuple[date, float]],
    *,
    series_id: str,
    collected_por_ano: dict[int, datetime],
) -> pd.DataFrame:
    """Série long no contrato `ProcessedSeriesSchema` — as 8 colunas, nada mais.

    `collected_at` vem do manifesto do bruto daquele ano, não do relógio da rodada: assim a
    segunda execução sobre o mesmo bruto produz o mesmo parquet. `vintage` é a **data** (sem
    hora) desse `collected_at` — a convenção uniforme da Onda 1 (D-b). A B3 não revisa
    fechamento de índice, então aqui o `vintage` não carrega informação nova; carrega
    comparabilidade com o resto de `data/processed/`, cuja PK é `(series_id, date, vintage)`.
    """
    colunas = ["series_id", "date", "value", "source", "freq", "vintage", "unit", "collected_at"]
    if not pontos:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in colunas})
    datas = [p[0] for p in pontos]
    coletas = pd.to_datetime(
        [_naive_utc(collected_por_ano.get(q.year, datetime.now(tz=UTC))) for q in datas]
    )
    return pd.DataFrame(
        {
            "series_id": series_id,
            "date": pd.to_datetime(datas),
            "value": [p[1] for p in pontos],
            "source": FONTE,
            "freq": FREQ_NATIVA,
            "vintage": coletas.normalize(),
            "unit": UNIDADE,
            "collected_at": coletas,
        },
        columns=colunas,
    )


def extrair(
    *,
    codigos: Sequence[str] | None = None,
    anos: Sequence[int] | None = None,
    offline: bool = False,
    raiz: Path | None = None,
    transporte: Transporte | None = None,
    hoje: date | None = None,
    dormir: Callable[[float], None] = time.sleep,
    pausa_s: float = PAUSA_ENTRE_REQUISICOES_S,
    catalogo: tuple[SeriesCatalogEntry, ...] | None = None,
    gravar: bool = True,
) -> tuple[ResultadoIndice, ...]:
    """Roda o extrator para os índices pedidos (default: todos os `ok` do catálogo)."""
    hoje = hoje or datetime.now(tz=UTC).date()
    disponiveis = indices_do_catalogo(catalogo)
    if codigos:
        pedidos = {c.upper() for c in codigos}
        conhecidos = {e.identificador for e in disponiveis}
        desconhecidos = sorted(pedidos - conhecidos)
        if desconhecidos:
            msg = (
                f"índice(s) {desconhecidos} não estão no catálogo com status=ok. Disponíveis: "
                f"{sorted(conhecidos)}"
            )
            raise ErroDeExtracao(msg)
        entradas = tuple(e for e in disponiveis if e.identificador in pedidos)
    else:
        entradas = disponiveis
    janela = tuple(anos) if anos else tuple(range(ANO_INICIAL, hoje.year + 1))

    config = config_extrator(entradas)
    cliente = (
        None
        if offline
        else ClienteHTTP(
            config,
            transporte=transporte,
            cabecalhos_base=cabecalhos_de_browser({"Referer": REFERER_B3}),
            dormir=dormir,
        )
    )
    resultados: list[ResultadoIndice] = []
    for entrada in entradas:
        _log.info(
            "extraindo %s (%s), %d anos", entrada.series_id, entrada.identificador, len(janela)
        )
        resultados.append(
            extrair_indice(
                entrada,
                config=config,
                anos=janela,
                cliente=cliente,
                offline=offline,
                raiz=raiz,
                hoje=hoje,
                dormir=dormir,
                pausa_s=pausa_s,
                gravar=gravar,
            )
        )
    return tuple(resultados)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _anos_do_cli(tokens: Sequence[str] | None) -> tuple[int, ...] | None:
    """`2006 2011-2013` → `(2006, 2011, 2012, 2013)`."""
    if not tokens:
        return None
    anos: set[int] = set()
    for token in tokens:
        casado = _PADRAO_ANOS_CLI.match(token.strip())
        if not casado:
            msg = f"--anos aceita AAAA ou AAAA-AAAA, recebido {token!r}"
            raise ErroDeExtracao(msg)
        inicio = int(casado.group("inicio"))
        fim = int(casado.group("fim") or inicio)
        if fim < inicio:
            msg = f"--anos {token!r}: intervalo invertido"
            raise ErroDeExtracao(msg)
        anos.update(range(inicio, fim + 1))
    return tuple(sorted(anos))


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.b3_indices",
        description=(
            "Extrai os índices da B3 (amplos, setoriais e IFIX) da API indexStatisticsProxy, "
            "arquiva o bruto por índice/ano e grava a série diária em data/processed/b3/."
        ),
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        metavar="COD",
        help="códigos da API (IBOV, IEEX, IFIX…). Default: todos os ok do catálogo.",
    )
    parser.add_argument(
        "--anos",
        nargs="+",
        metavar="AAAA[-AAAA]",
        help=f"anos ou intervalos. Default: {ANO_INICIAL}→ano corrente.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="não toca a rede: relê o bruto já arquivado em data/raw/b3/.",
    )
    parser.add_argument(
        "--pausa",
        type=float,
        default=PAUSA_ENTRE_REQUISICOES_S,
        metavar="SEG",
        help=f"pausa entre requisições (default {PAUSA_ENTRE_REQUISICOES_S}s).",
    )
    return parser


def _relatorio(resultados: Sequence[ResultadoIndice]) -> str:
    cabecalho = (
        f"{'serie':<12} {'cod':<5} {'linhas':>7} {'inicio':>11} {'fim':>11} "
        f"{'1o ano':>7} {'% nulos':>8}"
    )
    linhas = [cabecalho, "-" * len(cabecalho)]
    for r in resultados:
        linhas.append(
            f"{r.series_id:<12} {r.codigo:<5} {r.linhas:>7} "
            f"{(r.data_inicio_observada or '-')!s:>11} {(r.data_fim_observada or '-')!s:>11} "
            f"{(r.primeiro_ano_efetivo or '-')!s:>7} {r.pct_nulos:>7.2f}%"
        )
    total = sum(r.linhas for r in resultados)
    linhas.append("-" * len(cabecalho))
    linhas.append(f"{len(resultados)} séries, {total} linhas")
    return "\n".join(linhas)


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI."""
    from apps.pipeline.common import configurar_logging

    configurar_logging()
    args = _construir_parser().parse_args(argv)
    resultados = extrair(
        codigos=args.indices,
        anos=_anos_do_cli(args.anos),
        offline=args.offline,
        pausa_s=args.pausa,
    )
    print(_relatorio(resultados))  # noqa: T201 — é a saída do CLI
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
