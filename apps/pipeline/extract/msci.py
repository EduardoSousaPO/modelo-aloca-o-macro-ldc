"""Extrator MSCI — níveis diários `NETR` (net total return) do `indexmaster` (F-007, SPEC RF-016).

Fonte: `https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph` — endpoint
JSON **público, gratuito, sem chave e não documentado** da app web da MSCI
(`docs/research/fontes-de-dados.md §C10.4`). É a **rota recomendada** do bloco internacional: o
`^GSPC` do Yahoo é price return e os ETFs `ACWI`/`URTH` só começam em 2008/2012, enquanto o
**ACWI `892400` variante `NETR`** é retorno total de verdade desde **2000-12-29** e cobre 2006 com
folga (Anti-SPEC §10.2.12).

Caminho: `ClienteHTTP` → parse → `arquivar_bruto` (`data/raw/msci/`, idempotente, com manifesto) →
`gravar_processado_parquet` (`data/processed/msci/<series_id>.parquet`), na **frequência nativa
diária** (`data_frequency=DAILY`, 6.726 pontos medidos) e na **moeda original, USD**. A série em
BRL é derivação pela PTAX de F-003 e sai como `ACWI_BRL`, série própria (CA-047).

As quatro pegadinhas medidas desta fonte, e onde cada uma é tratada:

1. **Erro vem com HTTP 200 e chaves `error_code`/`error_message`** — não `error`, que é a chave que
   `validar_corpo_json_array` da infra reconhece. `start_date=19960101` devolve
   `{"error_code":" 100","error_message":" null Invalid Parameter start_date : '19960101.
   Calculation date cannot be earlier than 19970101'"}` com status 200 (R1, Anti-SPEC §10.1.5).
   Daí a guarda própria em `_corpo_json` e o `start_date` mínimo declarado.
2. **Código de índice inexistente devolve HTTP 200 com `INDEX_LEVELS: []`**, sem erro nenhum —
   medido em `705000` (o MSCI Brazil "a confirmar" do catálogo) e em `999999`. A guarda é
   `contagem_minima_esperada` (R2).
3. **`index_variant` muda a série inteira.** `STRD` é preço (começa em 1997-01-01) e `NETR` é
   retorno total líquido (começa em 2000-12-29). A resposta ecoa `index_variant_type` e
   `msci_index_code`: o parser confere os dois contra o pedido, porque uma variante trocada seria
   um gráfico igualmente bonito e uma série diferente.
4. **O endpoint pode quebrar sem aviso** (R18 — não é API publicada). Por isso o `valor_canario`
   do contrato é conferido a cada execução, não só no teste: ACWI `NETR` em **31/01/2006 =
   121,3858** (CA-046).

Uso:

```bash
uv run python -m apps.pipeline.extract.msci                    # ACWI WORLD USA EM, ao vivo
uv run python -m apps.pipeline.extract.msci --indices ACWI     # só o ACWI
uv run python -m apps.pipeline.extract.msci --offline          # relê data/raw, sem rede
```
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from apps.pipeline.common import (
    DO_CONTRATO,
    SUFIXO_MANIFESTO,
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    FormatoDetectado,
    RespostaDeErroComStatus200,
    SerieInconsistente,
    arquivar_bruto,
    caminho_destino_raw,
    collected_at_do_bruto,
    configurar_logging,
    exigir_contagem_minima,
    exigir_formato,
    gravar_processado_parquet,
    ler_texto,
    nome_arquivo_raw,
    obter_logger,
    para_data,
    para_float_ponto_decimal,
    sha256_de,
)

# A conversão a BRL vive em `apps/pipeline/transform/cambio.py` desde a consolidação da Onda 1
# (D-g): antes morava em `extract/yahoo.py` e este módulo importava **um extrator** só por causa
# dela. O que ainda vem de `yahoo.py` é `entrada_do_catalogo`, um utilitário de 3 linhas sobre o
# catálogo compartilhado — e é dívida pequena, registrada no `TODO.md §6`.
from apps.pipeline.extract.yahoo import entrada_do_catalogo
from apps.pipeline.transform import carregar_ptax, converter_para_brl
from packages.shared.schemas import ExtractorConfig, Fonte, Freq, load_catalog

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from apps.pipeline.common import Transporte
    from packages.shared.schemas import SeriesCatalogEntry

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Catálogo local: códigos, variante, janela e pisos de contagem
# ─────────────────────────────────────────────────────────────────────────────

URL_LEVELS = "https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph"

#: Variante usada em todo o módulo: **net total return**. `STRD` (preço) não entra: misturar
#: preço e retorno total no mesmo heatmap é Anti-SPEC §10.2.12, e o catálogo só tem entradas
#: `*_NETR`.
VARIANTE = "NETR"
MOEDA = "USD"
FREQUENCIA_NATIVA = "DAILY"

#: `chave do extrator -> (index_codes, series_id do catálogo)`. Conferido contra
#: `series_catalog_data` na importação do módulo. `MSCI_BRAZIL` fica fora: o código testado na
#: pesquisa (`705000`) devolve lista vazia e a entrada está `status = a_confirmar` — nenhum
#: identificador é inventado aqui.
INDICES: dict[str, tuple[str, str]] = {
    "ACWI": ("892400", "MSCI_ACWI_NETR"),
    "WORLD": ("990100", "MSCI_WORLD_NETR"),
    "USA": ("984000", "MSCI_USA_NETR"),
    "EM": ("891800", "MSCI_EM_NETR"),
}

INDICES_SUPORTADOS: tuple[str, ...] = tuple(INDICES)
#: Default da CLI: os quatro `status = ok`. `ACWI` é o do item **C1**; `USA` é a alternativa de
#: retorno total para os EUA; `WORLD` e `EM` decompõem o ACWI.
INDICES_PADRAO: tuple[str, ...] = INDICES_SUPORTADOS

#: `start_date` mínimo aceito pela fonte. Abaixo disso a resposta é HTTP 200 com `error_message`
#: `"Calculation date cannot be earlier than 19970101"` (pegadinha nº 1).
DATA_MINIMA_FONTE = date(1997, 1, 1)
INICIO_PADRAO = DATA_MINIMA_FONTE

#: Piso anti-truncamento (R2): níveis medidos ao vivo em 2026-10-10 na janela
#: `19970101 -> 20261010`. Os quatro índices `NETR` começam juntos em 2000-12-29 e por isso têm a
#: mesma contagem.
NIVEIS_MINIMOS: dict[str, int] = {
    "ACWI": 6726,
    "WORLD": 6726,
    "USA": 6726,
    "EM": 6726,
}

#: `(data ISO, nível)` conferido em 2026-10-10. O do `ACWI` é o **valor-canário da SPEC**
#: (CA-046), reconferido contra outra superfície da própria fonte
#: (`data_frequency=END_OF_MONTH`, requisição e payload distintos do diário).
VALORES_CANARIO: dict[str, tuple[str, float]] = {
    "ACWI": ("2006-01-31", 121.38580887703861),
    "WORLD": ("2006-01-31", 2895.079155796253),
    "USA": ("2006-01-31", 2802.4605533869526),
    "EM": ("2006-01-31", 266.29008264699576),
}

#: `data_inicio` medido: é o primeiro dia da variante `NETR` dos quatro índices.
DATA_INICIO_NETR = date(2000, 12, 29)

DESTINO_RAW = "data/raw/msci"
SUBPASTA_PROCESSED = "msci"
EXTENSAO_RAW = "json"
ENCODING = "utf-8"
PAUSA_ENTRE_INDICES_S = 1.0

#: Chaves de erro desta fonte, servidas **com HTTP 200** (pegadinha nº 1). `CHAVES_DE_ERRO` da
#: infra cobre `error`/`erro`/`errors`/`erros` — nenhuma delas aparece aqui.
CHAVES_DE_ERRO_MSCI: frozenset[str] = frozenset({"error_code", "error_message"})

#: Séries derivadas em BRL: `chave do índice -> series_id do catálogo`. Só o ACWI por enquanto —
#: é o `ACWI_BRL` de `ATIVOS_INTERNACIONAIS` (ADR-003) e é **retorno total**, o que o torna o
#: comparável legítimo do IMA-B/IFIX no mesmo heatmap.
SERIES_BRL: dict[str, str] = {"ACWI": "ACWI_BRL"}


def _catalogo_msci() -> dict[str, SeriesCatalogEntry]:
    """Entradas do catálogo das chaves suportadas, conferidas na importação do módulo."""
    catalogo = {e.series_id: e for e in load_catalog()}
    resolvido: dict[str, SeriesCatalogEntry] = {}
    for chave, (codigo, series_id) in INDICES.items():
        entrada = catalogo.get(series_id)
        if entrada is None:
            msg = f"{series_id} não está em packages/shared/schemas/series_catalog_data.py"
            raise ErroDeExtracao(msg)
        esperado = f"{codigo} / {VARIANTE}"
        if entrada.identificador != esperado:
            msg = (
                f"{series_id}: catálogo diz identificador={entrada.identificador!r}, "
                f"o extrator usa {esperado!r}"
            )
            raise ErroDeExtracao(msg)
        if entrada.is_total_return is not True:
            msg = (
                f"{series_id}: variante {VARIANTE} é retorno total, mas o catálogo diz "
                f"is_total_return={entrada.is_total_return!r} (Anti-SPEC §10.2.12)"
            )
            raise ErroDeExtracao(msg)
        resolvido[chave] = entrada
    return resolvido


CATALOGO: dict[str, SeriesCatalogEntry] = _catalogo_msci()


def codigo_de(chave: str) -> str:
    """`892400` — o `index_codes` do índice."""
    entrada_do_indice(chave)
    return INDICES[chave][0]


def series_id_de(chave: str) -> str:
    """`MSCI_ACWI_NETR` — o `series_id` do catálogo."""
    entrada_do_indice(chave)
    return INDICES[chave][1]


def entrada_do_indice(chave: str) -> SeriesCatalogEntry:
    """Entrada do catálogo do índice — de onde saem `unit` e `is_total_return`."""
    if chave not in CATALOGO:
        msg = f"índice {chave!r} não suportado; use um de {list(INDICES_SUPORTADOS)}"
        raise ErroDeExtracao(msg)
    return CATALOGO[chave]


def config_do_indice(chave: str) -> ExtractorConfig:
    """`ExtractorConfig` do índice: o contrato é a configuração, nada aqui é hard-code solto."""
    entrada = entrada_do_indice(chave)
    return ExtractorConfig(
        nome=f"msci_{chave.lower()}_{VARIANTE.lower()}",
        fonte=Fonte.MSCI,
        series_ids=(entrada.series_id,),
        base_url=URL_LEVELS,
        formato="json",
        encoding=ENCODING,
        # A app web da MSCI recusa cliente sem UA de browser (R4).
        requer_user_agent_browser=True,
        janela_maxima_dias=None,  # 26 anos de diário num GET só (~360 KB)
        contagem_minima_esperada=NIVEIS_MINIMOS[chave],
        valor_canario=VALORES_CANARIO[chave],
        destino_raw=DESTINO_RAW,
        timeout_s=180.0,  # a pesquisa mediu 1,76 s; a app web é lenta em horário de pico
    )


def parametros_janela(
    chave: str,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    *,
    frequencia: str = FREQUENCIA_NATIVA,
) -> dict[str, Any]:
    """Querystring do `getLevelDataForGraph`, com o piso de `start_date` da fonte.

    `start_date` anterior a 1997-01-01 é recusado pela fonte **com HTTP 200** — levantar aqui dá
    o diagnóstico certo em vez de deixar a guarda de shape descobrir depois.
    """
    if inicio < DATA_MINIMA_FONTE:
        msg = (
            f"start_date={inicio.isoformat()} é anterior ao mínimo da fonte "
            f"({DATA_MINIMA_FONTE.isoformat()}): a MSCI responde HTTP 200 com "
            f"error_message 'Calculation date cannot be earlier than 19970101'"
        )
        raise ValueError(msg)
    termino = fim or datetime.now(tz=UTC).date()
    if termino < inicio:
        msg = f"janela invertida: inicio={inicio.isoformat()} > fim={termino.isoformat()}"
        raise ValueError(msg)
    return {
        "currency_symbol": MOEDA,
        "index_variant": VARIANTE,
        "start_date": inicio.strftime("%Y%m%d"),
        "end_date": termino.strftime("%Y%m%d"),
        "data_frequency": frequencia,
        "baseValue": "false",
        "index_codes": INDICES[chave][0],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parse
# ─────────────────────────────────────────────────────────────────────────────


def _corpo_json(conteudo: bytes, *, origem: str) -> dict[str, Any]:
    """Bytes → `dict`, recusando corpo vazio, HTML, array e o erro com HTTP 200 da MSCI (R1)."""
    exigir_formato(conteudo, FormatoDetectado.JSON, origem=origem)
    try:
        corpo = json.loads(ler_texto(conteudo, ENCODING))
    except json.JSONDecodeError as exc:
        msg = f"{origem}: corpo não é JSON válido ({exc})"
        raise RespostaDeErroComStatus200(msg) from exc
    if not isinstance(corpo, dict):
        msg = f"{origem}: esperado objeto JSON, veio {type(corpo).__name__}"
        raise RespostaDeErroComStatus200(msg)
    encontradas = sorted(CHAVES_DE_ERRO_MSCI.intersection(k.lower() for k in corpo))
    if encontradas:
        detalhe = "; ".join(f"{k}={corpo.get(k)!r}" for k in encontradas)
        msg = f"{origem}: HTTP 200 com corpo de ERRO da MSCI (Anti-SPEC §10.1.5). {detalhe}"
        raise RespostaDeErroComStatus200(msg)
    return corpo


def _niveis(corpo: dict[str, Any], *, chave: str, origem: str) -> list[dict[str, Any]]:
    """`indexes.INDEX_LEVELS`, com a guarda de código e variante ecoados pela fonte."""
    codigo, series_id = INDICES[chave]
    ecoado = str(corpo.get("msci_index_code", ""))
    if ecoado != codigo:
        msg = (
            f"{origem}: msci_index_code={ecoado!r}, pedido {codigo!r} — a fonte devolveu outro "
            f"índice e {series_id} descreveria uma série que não é a dele"
        )
        raise SerieInconsistente(msg)
    variante = str(corpo.get("index_variant_type", ""))
    if variante != VARIANTE:
        msg = (
            f"{origem}: index_variant_type={variante!r}, pedido {VARIANTE!r} — STRD é preço e "
            f"NETR é retorno total; trocar a variante troca a série (Anti-SPEC §10.2.12)"
        )
        raise SerieInconsistente(msg)
    moeda = str(corpo.get("ISO_currency_symbol", ""))
    if moeda != MOEDA:
        msg = f"{origem}: ISO_currency_symbol={moeda!r}, pedido {MOEDA!r} — erro de escala"
        raise SerieInconsistente(msg)

    indices = corpo.get("indexes")
    if not isinstance(indices, dict):
        msg = f"{origem}: resposta sem a chave 'indexes' (chaves vistas: {sorted(corpo)})"
        raise SerieInconsistente(msg)
    niveis = indices.get("INDEX_LEVELS")
    if not isinstance(niveis, list):
        msg = f"{origem}: indexes.INDEX_LEVELS ausente ou não é lista ({niveis!r})"
        raise SerieInconsistente(msg)
    return niveis


def parse_niveis(
    conteudo: bytes,
    *,
    chave: str,
    origem: str,
    collected_at: datetime,
    minimo: int | None | object = DO_CONTRATO,
) -> pd.DataFrame:
    """Bytes do `getLevelDataForGraph` → DataFrame no contrato `ProcessedSeriesSchema`.

    Não grava nada: validar antes de escrever é o que CA-003 pede, e quem escreve é
    `gravar_processado_parquet`. Levanta em vez de devolver série vazia (o código inexistente que
    responde `INDEX_LEVELS: []` com HTTP 200), curta, com nível nulo, data duplicada, fora de
    ordem ou no futuro.

    `minimo` segue o idioma de `ClienteHTTP.json_array`: default = o
    `contagem_minima_esperada` do contrato (6.726 níveis); `None` desliga a guarda, que é o que a
    fixture — um recorte de 1 ano, limitado a 200 KB — precisa.
    """
    config = config_do_indice(chave)
    entrada = entrada_do_indice(chave)
    corpo = _corpo_json(conteudo, origem=origem)
    niveis = _niveis(corpo, chave=chave, origem=origem)

    datas = [
        para_data(e.get("calc_date"), FormatoData.AAAAMMDD, origem=origem)
        if isinstance(e, dict)
        else None
        for e in niveis
    ]
    valores = [
        para_float_ponto_decimal(e.get("level_eod"), origem=origem) if isinstance(e, dict) else None
        for e in niveis
    ]

    quadro = pd.DataFrame(
        {
            "series_id": entrada.series_id,
            "date": pd.to_datetime(pd.Series(datas, dtype="object")),
            "value": pd.Series(valores, dtype="float64"),
            "source": Fonte.MSCI.value,
            "freq": Freq.DIARIA.value,
            # D-b: `vintage` = data (sem hora) de `collected_at`, que sai do manifesto do bruto.
            "vintage": pd.Timestamp(collected_at).tz_localize(None).normalize(),
            "unit": entrada.unit.value,
            "collected_at": pd.Timestamp(collected_at).tz_localize(None),
        }
    )
    piso = config.contagem_minima_esperada if minimo is DO_CONTRATO else minimo
    _validar(quadro, chave=chave, origem=origem, minimo=piso)  # type: ignore[arg-type]
    return quadro.reset_index(drop=True)


def _validar(quadro: pd.DataFrame, *, chave: str, origem: str, minimo: int | None) -> None:
    """Guardas de conteúdo: contagem, nulo, duplicata, ordem e data futura."""
    exigir_contagem_minima(len(quadro), minimo=minimo, origem=f"{chave} @ {origem}")

    if quadro["date"].isna().any():
        msg = f"{origem}: {int(quadro['date'].isna().sum())} nível(is) sem calc_date"
        raise SerieInconsistente(msg)
    # `value` nulo é legítimo em `processed_series` quando a ausência é esperada. Aqui não é: o
    # `level_eod` é a razão de ser da resposta e nulo nele só sai de falha de parse. Nunca
    # preencher com `0` (Anti-SPEC §10.1.4) — levantar.
    if quadro["value"].isna().any():
        msg = f"{origem}: {int(quadro['value'].isna().sum())} nível(is) com level_eod nulo"
        raise SerieInconsistente(msg)

    duplicadas = quadro.loc[quadro["date"].duplicated(keep=False), "date"]
    if not duplicadas.empty:
        amostra = sorted({d.date().isoformat() for d in duplicadas})[:5]
        msg = f"{origem}: calc_date repetido (amostra: {amostra})"
        raise SerieInconsistente(msg)
    if not quadro["date"].is_monotonic_increasing:
        msg = f"{origem}: calc_date fora de ordem crescente"
        raise SerieInconsistente(msg)
    futuras = quadro.loc[quadro["date"] > quadro["collected_at"], "date"]
    if not futuras.empty:
        msg = f"{origem}: data futura na série (máx {futuras.max().date().isoformat()})"
        raise SerieInconsistente(msg)


def conferir_canario(quadro: pd.DataFrame, *, chave: str, origem: str) -> tuple[str, float] | None:
    """Confere o `valor_canario` do contrato (CA-046), se a janela extraída o cobre.

    Rodar isto em **produção**, não só no teste, é a resposta ao R18: o endpoint não é documentado
    e pode mudar sem aviso. 121,3858 em 31/01/2006 é a assinatura do ACWI `NETR`.
    """
    config = config_do_indice(chave)
    if config.valor_canario is None:
        return None
    dia, esperado = config.valor_canario
    linha = quadro.loc[quadro["date"] == pd.Timestamp(dia), "value"]
    if linha.empty:
        return None
    obtido = float(linha.to_numpy()[0])
    if obtido != esperado:
        msg = (
            f"{origem}: valor-canário de {chave} em {dia} é {esperado!r}, a fonte devolveu "
            f"{obtido!r} — endpoint não documentado mudou, ou a variante/código é outro (R18)"
        )
        raise SerieInconsistente(msg)
    return (dia, esperado)


# ─────────────────────────────────────────────────────────────────────────────
# Extração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoIndice:
    """Evidência de dados de um índice — o que vai para o relatório do Feature Contract."""

    chave: str
    codigo: str
    series_id: str
    linhas: int
    data_inicio: date
    data_fim: date
    pct_nulos_value: float
    valor_minimo: float
    valor_maximo: float
    valor_final: float
    canario: tuple[str, float] | None
    is_total_return: bool | None
    sha256_raw: str
    bytes_raw: int
    caminho_raw: Path | None
    raw_idempotente: bool
    caminho_processed: Path | None
    series_id_brl: str | None = None
    linhas_brl: int | None = None
    dias_sem_ptax: int | None = None
    caminho_processed_brl: Path | None = None

    def resumo(self) -> str:
        """Uma linha para o log e para a CLI, **só em ASCII** (cp1252 no terminal do Windows)."""
        raw = "idempotente" if self.raw_idempotente else "novo"
        canario = f"{self.canario[0]}={self.canario[1]:.4f}" if self.canario else "fora da janela"
        brl = ""
        if self.series_id_brl:
            brl = f", {self.series_id_brl}: {self.linhas_brl} linhas ({self.dias_sem_ptax} s/PTAX)"
        return (
            f"{self.series_id} [{self.codigo}/{VARIANTE}]: {self.linhas} linhas, "
            f"{self.data_inicio} -> {self.data_fim}, min={self.valor_minimo:.4f} "
            f"max={self.valor_maximo:.4f} fim={self.valor_final:.4f}, "
            f"nulos={self.pct_nulos_value:.2%}, total_return={self.is_total_return}, "
            f"canario {canario}, raw {raw} sha256={self.sha256_raw[:12]}...{brl}"
        )


def nome_processado(series_id: str) -> str:
    """`msci/MSCI_ACWI_NETR.parquet` — caminho relativo dentro de `data/processed/`."""
    return f"{SUBPASTA_PROCESSED}/{series_id}.parquet"


def _resultado(
    quadro: pd.DataFrame,
    *,
    chave: str,
    canario: tuple[str, float] | None,
    sha256_raw: str,
    bytes_raw: int,
    caminho_raw: Path | None,
    raw_idempotente: bool,
    caminho_processed_: Path | None,
) -> ResultadoIndice:
    entrada = entrada_do_indice(chave)
    return ResultadoIndice(
        chave=chave,
        codigo=INDICES[chave][0],
        series_id=entrada.series_id,
        linhas=len(quadro),
        data_inicio=quadro["date"].min().date(),
        data_fim=quadro["date"].max().date(),
        pct_nulos_value=float(quadro["value"].isna().mean()),
        valor_minimo=float(quadro["value"].min()),
        valor_maximo=float(quadro["value"].max()),
        valor_final=float(quadro["value"].iloc[-1]),
        canario=canario,
        is_total_return=entrada.is_total_return,
        sha256_raw=sha256_raw,
        bytes_raw=bytes_raw,
        caminho_raw=caminho_raw,
        raw_idempotente=raw_idempotente,
        caminho_processed=caminho_processed_,
    )


def _gravar_brl(
    quadro: pd.DataFrame,
    *,
    chave: str,
    raiz: Path | None,
    gravar: bool,
) -> tuple[str, int, int, Path | None] | None:
    """Deriva e grava `ACWI_BRL` pela PTAX do mesmo dia útil (CA-047), se a PTAX existir."""
    series_id_brl = SERIES_BRL.get(chave)
    if series_id_brl is None:
        return None
    destino = entrada_do_catalogo(series_id_brl)
    try:
        ptax = carregar_ptax(raiz=raiz)
    except ErroDeExtracao as exc:
        _log.warning("%s nao produzida: %s", series_id_brl, exc)
        return None
    conversao = converter_para_brl(
        quadro,
        series_id_destino=series_id_brl,
        ptax=ptax,
        is_total_return=destino.is_total_return,
        unit=destino.unit.value,
        origem=series_id_brl,
    )
    caminho = (
        gravar_processado_parquet(conversao.quadro, nome=nome_processado(series_id_brl), raiz=raiz)
        if gravar
        else None
    )
    return (series_id_brl, conversao.linhas, conversao.dias_sem_ptax, caminho)


def _com_brl(resultado: ResultadoIndice, brl: tuple[str, int, int, Path | None]) -> ResultadoIndice:
    """Cópia do resultado com os campos da série derivada em BRL preenchidos."""
    series_id_brl, linhas_brl, dias_sem_ptax, caminho = brl
    return replace(
        resultado,
        series_id_brl=series_id_brl,
        linhas_brl=linhas_brl,
        dias_sem_ptax=dias_sem_ptax,
        caminho_processed_brl=caminho,
    )


def extrair_indice(
    chave: str,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
    com_brl: bool = True,
    minimo: int | None | object = DO_CONTRATO,
) -> ResultadoIndice:
    """Baixa, parseia, arquiva o bruto e grava o processado de **um** índice.

    A ordem é download → parse → `arquivar_bruto` → `gravar_processado_parquet`, e o nome do
    bruto carrega o **último `calc_date`** do histórico (não "hoje"): é o que torna a segunda
    rodada do dia byte-idêntica (CA-027) e o que faz uma republicação divergente do mesmo
    retrato bater em `ConteudoDivergente` em vez de apagar o anterior (R8).
    """
    config = config_do_indice(chave)
    cliente = ClienteHTTP(config, transporte=transporte)
    resposta = cliente.get(params=parametros_janela(chave, inicio, fim))
    conteudo = resposta.conteudo

    quadro = parse_niveis(
        conteudo,
        chave=chave,
        origem=resposta.url,
        collected_at=resposta.obtida_em,
        minimo=minimo,
    )
    canario = conferir_canario(quadro, chave=chave, origem=resposta.url)
    data_ref = quadro["date"].max().date()

    arquivado = arquivar_bruto(
        conteudo,
        destino=caminho_destino_raw(config, raiz=raiz),
        nome=nome_arquivo_raw(
            f"{INDICES[chave][0]}_{VARIANTE}", data_ref=data_ref, extensao=EXTENSAO_RAW
        ),
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
    )
    destino = (
        gravar_processado_parquet(quadro, nome=nome_processado(config.series_ids[0]), raiz=raiz)
        if gravar
        else None
    )
    resultado = _resultado(
        quadro,
        chave=chave,
        canario=canario,
        sha256_raw=arquivado.sha256,
        bytes_raw=arquivado.bytes_gravados,
        caminho_raw=arquivado.caminho,
        raw_idempotente=arquivado.idempotente,
        caminho_processed_=destino,
    )
    if com_brl:
        brl = _gravar_brl(quadro, chave=chave, raiz=raiz, gravar=gravar)
        if brl is not None:
            resultado = _com_brl(resultado, brl)
    _log.info("%s", resultado.resumo())
    return resultado


def _bruto_arquivado(chave: str, *, raiz: Path | None) -> Path:
    """O bruto mais recente do índice em `data/raw/msci/` (modo `--offline`)."""
    pasta = caminho_destino_raw(config_do_indice(chave), raiz=raiz)
    # `*` casa com ponto, então o glob pegaria também o `.meta.json` do manifesto, que ordena
    # depois e passaria por "o mais recente".
    padrao = f"{INDICES[chave][0]}_{VARIANTE}__*.{EXTENSAO_RAW}"
    candidatos = sorted(
        (c for c in pasta.glob(padrao) if not c.name.endswith(SUFIXO_MANIFESTO)), reverse=True
    )
    if not candidatos:
        msg = f"modo offline: nenhum bruto de {INDICES[chave][0]}/{VARIANTE} em {pasta}"
        raise ErroDeExtracao(msg)
    return candidatos[0]


def extrair_indice_offline(
    chave: str,
    *,
    raiz: Path | None = None,
    gravar: bool = True,
    com_brl: bool = True,
    caminho: Path | None = None,
    minimo: int | None | object = DO_CONTRATO,
    collected_at: datetime | None = None,
) -> ResultadoIndice:
    """Reprocessa um índice do bruto já arquivado — sem rede, sem reescrever `data/raw/`.

    `collected_at` só é aceito **explícito**: sem ele e sem manifesto do bruto, recusa
    (`ManifestoAusente`) em vez de datar o Parquet pelo relógio da rodada (D-b, CA-121).
    """
    alvo = caminho or _bruto_arquivado(chave, raiz=raiz)
    conteudo = alvo.read_bytes()
    # D-b: `collected_at` (e portanto `vintage`) sai do manifesto do bruto, não do relógio.
    quadro = parse_niveis(
        conteudo,
        chave=chave,
        origem=str(alvo),
        collected_at=collected_at_do_bruto(alvo, collected_at=collected_at),
        minimo=minimo,
    )
    canario = conferir_canario(quadro, chave=chave, origem=str(alvo))
    destino = (
        gravar_processado_parquet(quadro, nome=nome_processado(series_id_de(chave)), raiz=raiz)
        if gravar
        else None
    )
    resultado = _resultado(
        quadro,
        chave=chave,
        canario=canario,
        sha256_raw=sha256_de(conteudo),
        bytes_raw=len(conteudo),
        caminho_raw=alvo,
        raw_idempotente=True,
        caminho_processed_=destino,
    )
    if com_brl:
        brl = _gravar_brl(quadro, chave=chave, raiz=raiz, gravar=gravar)
        if brl is not None:
            resultado = _com_brl(resultado, brl)
    _log.info("[offline] %s", resultado.resumo())
    return resultado


def extrair(
    chaves: Sequence[str] | None = None,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    offline: bool = False,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
    com_brl: bool = True,
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, ResultadoIndice]:
    """Roda os índices pedidos (default: `INDICES_PADRAO`) e devolve a evidência por chave."""
    alvos = tuple(chaves) if chaves else INDICES_PADRAO
    resultados: dict[str, ResultadoIndice] = {}
    for posicao, chave in enumerate(alvos):
        if offline:
            resultados[chave] = extrair_indice_offline(
                chave, raiz=raiz, gravar=gravar, com_brl=com_brl
            )
            continue
        if posicao:
            dormir(PAUSA_ENTRE_INDICES_S)
        resultados[chave] = extrair_indice(
            chave,
            inicio=inicio,
            fim=fim,
            transporte=transporte,
            raiz=raiz,
            gravar=gravar,
            com_brl=com_brl,
        )
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.msci",
        description="Extrai niveis diarios NETR dos indices MSCI (F-007, SPEC RF-016).",
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        metavar="CHAVE",
        choices=INDICES_SUPORTADOS,
        help=f"subconjunto a extrair (default: {' '.join(INDICES_PADRAO)})",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reprocessa o bruto já em data/raw/msci/, sem tocar a rede",
    )
    parser.add_argument(
        "--sem-gravar",
        action="store_true",
        help="não escreve em data/processed/ (só confere e imprime a evidência)",
    )
    parser.add_argument(
        "--sem-brl",
        action="store_true",
        help="não deriva ACWI_BRL (que depende da PTAX de F-003)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` em sucesso, `1` em qualquer `ErroDeExtracao`."""
    args = _parser().parse_args(list(argv) if argv is not None else None)
    configurar_logging()
    try:
        resultados = extrair(
            args.indices,
            offline=args.offline,
            gravar=not args.sem_gravar,
            com_brl=not args.sem_brl,
        )
    except ErroDeExtracao as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for resultado in resultados.values():
        print(resultado.resumo())
    cobrem_2006 = sum(1 for r in resultados.values() if r.data_inicio <= date(2006, 1, 31))
    print(f"{len(resultados)} indice(s); {cobrem_2006} com data_inicio <= 2006-01-31")
    return 0


def _main_cli() -> None:  # pragma: no cover - invocado só por `python -m`
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _main_cli()
