"""Extrator IBGE SIDRA: IPCA (número-índice e variações) e PIB trimestral (F-004, RF-002/RF-004).

Fonte: `https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/all[/c11255/{cat}]`
— sem autenticação, sem cadastro, custo zero (`docs/research/fontes-de-dados.md §A3`). É a fonte
**primária** de IPCA e PIB do projeto; o SGS é espelho (SGS 433 ≡ `t/1737 v/63`,
SGS 22109 ≡ `t/1621 v/584 c11255/90707`) e serve para **reconciliação**, não como substituto —
só o SIDRA tem o **número-índice** do IPCA (deflator) e a abertura setorial do PIB por `c11255`.

Caminho: `ClienteHTTP.get` → `validar_corpo_json_array` (guarda R1) → descarte do cabeçalho →
parse → `arquivar_bruto` (`data/raw/sidra/`, idempotente, com manifesto) →
`gravar_processado_parquet` (`data/processed/sidra/<series_id>.parquet`), na **frequência nativa**
(mensal no IPCA, trimestral no PIB). Agregação para a grade trimestral é derivada e fica adiante
(F-015/F-017, Anti-SPEC §10.4.28).

As seis pegadinhas medidas desta fonte, e onde cada uma é tratada:

1. **A primeira linha do array é o cabeçalho**, não dado (CA-004). `descartar_cabecalho` exige que
   ela seja o cabeçalho (`V == "Valor"`) e **falha** se a fonte mudar o shape — tratar cabeçalho
   como dado colocaria a string `"Valor"` no lugar de um número e um período `"Mês (Código)"`.
2. **Resposta vazia vem com HTTP 200 e só o cabeçalho.** Período fora do intervalo da tabela
   (`p/197001` em `t/1737`) devolve `[{cabeçalho}]`, 200, `application/json` — o modo de falha
   silenciosa desta fonte (R1/R2). Zero linha de dado levanta `RespostaTruncada`.
3. **`V` é string com ponto decimal** (`"0.82"`, `"7695.8200000000000"`) →
   `para_float_ponto_decimal`. `para_float_ptbr` leria `"7695.82"` como 769.582 — erro de escala
   silencioso. Ausência é `"..."`/`".."`/`"-"`/`"X"`/`""` → `None`, **nunca** `0`
   (Anti-SPEC §10.1.4): `t/5932 v/6564` em 1996T1 e `t/1737 v/63` em 1979/12 são `"..."` reais.
4. **O período é `D3C`**: `AAAAMM` no mensal (`202609`) e `AAAAT` no trimestral (`200601` =
   1º trimestre de 2006). **Os dois têm 6 caracteres e são indistinguíveis pelo texto** —
   `200601` é janeiro/2006 em `t/1737` e 1T2006 em `t/1621`. Quem decide é o `freq` do **catálogo**,
   nunca o palpite do parser. A data gravada é o **fim do período** (`CLAUDE.md §3`).
5. **Tabela/variável errada não levanta sozinha:** `t/1620` é volume **sem** ajuste sazonal e
   `t/1621` **com**; trocar uma pela outra mudaria o eixo de crescimento sem erro. Cada linha é
   conferida contra `D2C` (variável) e `D4C` (categoria de `c11255`) pedidos, e contra `NC == "1"`.
6. **Encoding UTF-8 explícito** (R10, Anti-SPEC §10.4.26): a API serve UTF-8 e o default do locale
   no Windows (cp1252) corromperia `"Número-índice"` e `"Variação mensal"`. O `encoding` vem do
   `ExtractorConfig` e desce até `validar_corpo_json_array`.

`vintage` = a **data** (sem hora) do `collected_at` registrado no **manifesto do bruto** (D-b da
consolidação da Onda 1, `docs/plans/DECISIONS_LOG.md §2`), não o relógio da rodada: é o que faz
uma revisão retroativa do PIB coexistir com o retrato anterior em vez de sobrescrevê-lo — mesmo
quando o IBGE revisa o passado **sem** acrescentar trimestre novo, caso em que "última data do
histórico" não mudaria —, com a PK `(series_id, date, vintage)` ainda única (RF-025 / CA-122 /
Anti-SPEC §10.2.7). A `data_ref` do nome do arquivo bruto continua sendo a última data do
histórico: é o retrato, não a safra.

Uso:

```bash
uv run python -m apps.pipeline.extract.ibge_sidra                                  # as 6 séries
uv run python -m apps.pipeline.extract.ibge_sidra --series SIDRA_1737_V2266        # só uma
uv run python -m apps.pipeline.extract.ibge_sidra --offline                        # relê data/raw
```
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pandas as pd

from apps.pipeline.common import (
    DO_CONTRATO,
    SUFIXO_MANIFESTO,
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    arquivar_bruto,
    caminho_destino_raw,
    configurar_logging,
    exigir_contagem_minima,
    gravar_processado_parquet,
    ler_texto,
    nome_arquivo_raw,
    obter_logger,
    obtido_em_arquivado,
    para_data,
    para_float_ponto_decimal,
    sha256_de,
    validar_corpo_json_array,
)
from packages.shared.schemas import (
    ExtractorConfig,
    Fonte,
    Freq,
    StatusSerie,
    load_catalog,
)

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from collections.abc import Sequence
    from pathlib import Path

    from apps.pipeline.common import RespostaBruta, Transporte
    from packages.shared.schemas import SeriesCatalogEntry

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Catálogo local: consulta, pisos, canários
# ─────────────────────────────────────────────────────────────────────────────

URL_BASE = "https://apisidra.ibge.gov.br/values"

#: Classificação "Setores e subsetores" das Contas Nacionais Trimestrais. É a única usada aqui:
#: `90707` = PIB a preços de mercado (o agregado). As outras 20 categorias (Agro `90687`,
#: Indústria `90691`, Serviços `90696`, FBCF `93406`…) são a **fase 2** — abertura setorial,
#: deliberadamente fora do Feature Contract de F-004.
CLASSIFICACAO_SETORES = 11255
CATEGORIA_PIB_PRECOS_DE_MERCADO = 90707

#: Rótulo que a 1ª linha do array traz na chave `V`. É a assinatura do cabeçalho: a linha de dado
#: traz um número ou um marcador de ausência, nunca a palavra "Valor".
ROTULO_CABECALHO_V = "Valor"
#: Código do nível territorial N1 (Brasil). `n1/all` devolve só esta linha por período.
NIVEL_BRASIL = "1"

#: Marcadores de ausência **documentados pelo SIDRA**, superconjunto explícito de `AUSENCIAS` da
#: infra: `".."` não se aplica, `"..."` não disponível, `"-"` zero absoluto, `"X"` omitido por
#: sigilo. `"X"` não está em `AUSENCIAS` e precisa estar aqui para não levantar. Em todos os casos
#: o valor é `None` — nunca `0` (Anti-SPEC §10.1.4).
AUSENCIAS_SIDRA: frozenset[str] = frozenset({"", "-", "..", "...", "X"})

DESTINO_RAW = "data/raw/sidra"
SUBPASTA_PROCESSED = "sidra"
EXTENSAO_RAW = "json"

#: Fração mínima de passos **não decrescentes** exigida de uma série de número-índice de preço
#: (CA-004). **Medido em 2026-10-10 na série real `t/1737 v/2266`: 0,9626** no histórico completo
#: (21 meses de deflação em 562, de 199708 a 202608) e **0,9435** de 2006 em diante. A SPEC CA-004
#: escreve ">= 99 %", que a série real **não cumpre** — ver §5 de `docs/wiki/context/F-004.md`.
#: O piso aqui é 0,90: discrimina com folga um número-índice de uma série de **variação**
#: (`v/63` tem ~0,5 de passos não decrescentes), que é o erro que a CA quer pegar.
MONOTONIA_MINIMA = 0.90


class RespostaSidraInconsistente(ErroDeExtracao):
    """O JSON é um array válido, mas não é a tabela/variável/período pedidos."""


@dataclass(frozen=True, slots=True)
class ConsultaSidra:
    """Uma consulta ao apisidra: tabela, variável e (opcionalmente) categoria de `c11255`."""

    tabela: int
    variavel: int
    classificacao: int | None = None
    categoria: int | None = None

    @property
    def identificador(self) -> str:
        """`t/1621 v/584 c11255/90707` — exatamente como o catálogo escreve."""
        base = f"t/{self.tabela} v/{self.variavel}"
        if self.classificacao is None:
            return base
        return f"{base} c{self.classificacao}/{self.categoria}"

    @property
    def slug(self) -> str:
        """`t1621_v584_c90707` — o `<serie>` do nome de arquivo (`tests/fixtures/README.md`)."""
        base = f"t{self.tabela}_v{self.variavel}"
        if self.classificacao is None:
            return base
        return f"{base}_c{self.categoria}"

    @property
    def url(self) -> str:
        """URL completa, histórico inteiro (`p/all`) — o e-mail pede "histórico completo" (A7)."""
        url = f"{URL_BASE}/t/{self.tabela}/n1/all/v/{self.variavel}/p/all"
        if self.classificacao is not None:
            url = f"{url}/c{self.classificacao}/{self.categoria}"
        return url


def _pib(tabela: int, variavel: int) -> ConsultaSidra:
    return ConsultaSidra(
        tabela=tabela,
        variavel=variavel,
        classificacao=CLASSIFICACAO_SETORES,
        categoria=CATEGORIA_PIB_PRECOS_DE_MERCADO,
    )


#: As 6 séries `fonte == IBGE_SIDRA` e `status == ok` do catálogo. `_conferir_catalogo()` falha na
#: importação se este mapa e `series_catalog_data.py` divergirem **em qualquer direção** — é o que
#: impede uma série nova no catálogo de ficar sem extrator em silêncio.
CONSULTAS: dict[str, ConsultaSidra] = {
    "SIDRA_1737_V63": ConsultaSidra(tabela=1737, variavel=63),
    "SIDRA_1737_V2265": ConsultaSidra(tabela=1737, variavel=2265),
    "SIDRA_1737_V2266": ConsultaSidra(tabela=1737, variavel=2266),
    "SIDRA_1621_V584_90707": _pib(1621, 584),
    "SIDRA_1620_V583_90707": _pib(1620, 583),
    "SIDRA_5932_V6564_90707": _pib(5932, 6564),
}

#: Piso anti-truncamento (R2): nº de **linhas de dado** (já sem o cabeçalho) medido em 2026-10-10.
#: `t/1737` = 562 períodos (197912→202609); as três tabelas trimestrais = 122 (199601→202602).
#: A série só cresce: vir menos é truncamento silencioso ou tabela trocada.
LINHAS_MINIMAS: dict[str, int] = {
    "SIDRA_1737_V63": 562,
    "SIDRA_1737_V2265": 562,
    "SIDRA_1737_V2266": 562,
    "SIDRA_1621_V584_90707": 122,
    "SIDRA_1620_V583_90707": 122,
    "SIDRA_5932_V6564_90707": 122,
}

#: `(data ISO de **fim de período**, valor)` conferido contra a API em 2026-10-10. Os de
#: `SIDRA_1621_V584_90707` e `SIDRA_5932_V6564_90707` são os valores-canário da SPEC
#: (CA-008 e `fontes-de-dados.md §A3`); o de `SIDRA_1737_V63` é o de CA-002/CA-004.
VALORES_CANARIO: dict[str, tuple[str, float]] = {
    "SIDRA_1737_V63": ("2026-09-30", 0.82),
    "SIDRA_1737_V2265": ("2026-09-30", 4.58),
    "SIDRA_1737_V2266": ("2026-09-30", 7695.82),
    "SIDRA_1621_V584_90707": ("2006-03-31", 131.74),
    "SIDRA_1620_V583_90707": ("2006-03-31", 128.18),
    "SIDRA_5932_V6564_90707": ("2006-03-31", 1.6),
}

#: Séries de número-índice de **preço**, as únicas sujeitas à guarda de monotonia de CA-004. O
#: índice de **volume** do PIB (`t/1620`, `t/1621`) cai em recessão: exigir monotonia dele seria
#: transformar a crise de 2015 em erro de extração.
SERIES_NUMERO_INDICE_DE_PRECO: frozenset[str] = frozenset({"SIDRA_1737_V2266"})

SERIES_SUPORTADAS: tuple[str, ...] = tuple(CONSULTAS)


def consulta_de(series_id: str) -> ConsultaSidra:
    """A `ConsultaSidra` da série, ou `ErroDeExtracao` se a série não é desta fonte."""
    try:
        return CONSULTAS[series_id]
    except KeyError:
        msg = f"série {series_id!r} não é do SIDRA; use uma de {list(SERIES_SUPORTADAS)}"
        raise ErroDeExtracao(msg) from None


def entrada_de(series_id: str) -> SeriesCatalogEntry:
    """A entrada do catálogo da série — fonte de verdade de `freq`, `unit` e `data_inicio`."""
    return _CATALOGO[series_id]


def config_de(series_id: str) -> ExtractorConfig:
    """`ExtractorConfig` da série: o contrato é a configuração, nada aqui é hard-code solto."""
    consulta = consulta_de(series_id)
    return ExtractorConfig(
        nome=f"ibge_sidra_{consulta.slug}",
        fonte=Fonte.IBGE_SIDRA,
        series_ids=(series_id,),
        base_url=consulta.url,
        formato="json",
        # R10 / Anti-SPEC §10.4.26: a API serve UTF-8 e o locale do Windows é cp1252. Explícito.
        encoding="utf-8",
        # O apisidra fica atrás de Cloudflare (a raiz do host serve o desafio "Just a moment...").
        requer_user_agent_browser=True,
        janela_maxima_dias=None,  # mensal/trimestral: `p/all` numa requisição, sem fatiar
        contagem_minima_esperada=LINHAS_MINIMAS[series_id],
        valor_canario=VALORES_CANARIO[series_id],
        destino_raw=DESTINO_RAW,
        timeout_s=120.0,
    )


def _carregar_catalogo() -> dict[str, SeriesCatalogEntry]:
    """Séries `IBGE_SIDRA` com `status == ok`, indexadas por `series_id`."""
    return {
        e.series_id: e
        for e in load_catalog()
        if e.fonte is Fonte.IBGE_SIDRA and e.status is StatusSerie.OK
    }


_CATALOGO: dict[str, SeriesCatalogEntry] = _carregar_catalogo()


def _conferir_catalogo() -> None:
    """Falha na importação se `CONSULTAS` e o catálogo divergirem (nos dois sentidos).

    O catálogo é a fonte de verdade de `series_id`, `freq`, `unit` e `data_inicio`; aqui ficam só
    a consulta e o layout. Série `IBGE_SIDRA`/`ok` sem entrada em `CONSULTAS` é série que o
    Feature Contract manda extrair e ninguém extrai — e o jeito de isso não passar em silêncio é
    quebrar no `import`.
    """
    faltam_aqui = sorted(set(_CATALOGO) - set(CONSULTAS))
    if faltam_aqui:
        msg = (
            f"séries IBGE_SIDRA com status=ok sem consulta em CONSULTAS: {faltam_aqui}. "
            f"O Feature Contract de F-004 cobre todas as entradas ok da fonte"
        )
        raise ErroDeExtracao(msg)
    faltam_no_catalogo = sorted(set(CONSULTAS) - set(_CATALOGO))
    if faltam_no_catalogo:
        msg = (
            f"CONSULTAS tem série que não está no catálogo como IBGE_SIDRA/ok: {faltam_no_catalogo}"
        )
        raise ErroDeExtracao(msg)
    for series_id, consulta in CONSULTAS.items():
        declarado = _CATALOGO[series_id].identificador
        if declarado != consulta.identificador:
            msg = (
                f"{series_id}: catálogo diz identificador={declarado!r}, "
                f"o módulo monta {consulta.identificador!r}"
            )
            raise ErroDeExtracao(msg)


_conferir_catalogo()


# ─────────────────────────────────────────────────────────────────────────────
# Parse
# ─────────────────────────────────────────────────────────────────────────────


def descartar_cabecalho(bruto: list[dict[str, object]], *, origem: str) -> list[dict[str, object]]:
    """Remove a **primeira linha** do array, que é o cabeçalho de rótulos (CA-004).

    Exige que ela *seja* o cabeçalho (`V == "Valor"`): se a fonte parar de mandá-lo, tratar a
    linha 1 como dado gravaria a string `"Valor"` no lugar de um número e `"Mês (Código)"` no
    lugar de um período. Array sem nenhuma linha de dado depois do descarte é a resposta vazia
    com HTTP 200 desta fonte (R1/R2) e levanta `RespostaTruncada` via `exigir_contagem_minima`.
    """
    if not bruto:
        msg = f"{origem}: array JSON vazio — nem o cabeçalho veio"
        raise RespostaSidraInconsistente(msg)
    cabecalho = bruto[0]
    if str(cabecalho.get("V", "")) != ROTULO_CABECALHO_V:
        msg = (
            f"{origem}: a 1ª linha deveria ser o cabeçalho (V={ROTULO_CABECALHO_V!r}), "
            f"veio V={cabecalho.get('V')!r}. O layout da fonte mudou: não trate como dado"
        )
        raise RespostaSidraInconsistente(msg)
    linhas = bruto[1:]
    exigir_contagem_minima(len(linhas), minimo=1, origem=f"{origem} (linhas de dado)")
    return linhas


def valor_sidra(bruto: object, *, origem: str) -> float | None:
    """`"0.82"` → `0.82` · `"..."`/`".."`/`"-"`/`"X"`/`""` → `None` · resto levanta.

    Ausência é `None` e **nunca** `0` (Anti-SPEC §10.1.4): `t/5932 v/6564` em 1996T1 não tem
    variação contra o trimestre anterior porque não existe trimestre anterior na tabela — zero ali
    seria afirmar que o PIB ficou parado.
    """
    if isinstance(bruto, str) and bruto.strip() in AUSENCIAS_SIDRA:
        return None
    return para_float_ponto_decimal(bruto, origem=origem)


def fim_do_periodo(codigo: object, *, freq: Freq, origem: str) -> date:
    """`D3C` → data de **fim do período**. `freq` vem do catálogo, nunca é inferido.

    `"202609"` com `freq=M` é 2026-09-30; `"200601"` com `freq=Q` é 2006-03-31. Os dois códigos
    têm 6 caracteres e **o texto não diz qual é qual** — `"200601"` é janeiro/2006 em `t/1737` e
    1º trimestre de 2006 em `t/1621`. Inferir seria escolher em silêncio entre duas leituras
    corretas, que é exatamente o R12 do projeto.
    """
    texto = str(codigo).strip()
    if len(texto) != 6 or not texto.isdigit():
        msg = f"{origem}: período {codigo!r} não é AAAAMM nem AAAAT (6 dígitos)"
        raise RespostaSidraInconsistente(msg)
    ano, sufixo = int(texto[:4]), int(texto[4:])
    if freq is Freq.MENSAL:
        if not 1 <= sufixo <= 12:
            msg = f"{origem}: período mensal {codigo!r} com mês {sufixo}"
            raise RespostaSidraInconsistente(msg)
        mes = sufixo
    elif freq is Freq.TRIMESTRAL:
        if not 1 <= sufixo <= 4:
            msg = f"{origem}: período trimestral {codigo!r} com trimestre {sufixo}"
            raise RespostaSidraInconsistente(msg)
        mes = sufixo * 3
    else:  # pragma: no cover - o catálogo só traz M e Q nesta fonte
        msg = f"{origem}: freq {freq} não suportada no SIDRA (só M e Q)"
        raise RespostaSidraInconsistente(msg)
    primeiro = para_data(f"{ano:04d}{mes:02d}01", FormatoData.AAAAMMDD, origem=origem)
    if primeiro is None:  # pragma: no cover - defensivo; a string acima nunca é ausência
        msg = f"{origem}: período {codigo!r} não produziu data"
        raise RespostaSidraInconsistente(msg)
    # Fim de período: último dia civil do mês (mensal) ou do 3º mês do trimestre (trimestral).
    return (pd.Timestamp(primeiro) + pd.offsets.MonthEnd(0)).date()


def _conferir_linha(linha: dict[str, object], *, consulta: ConsultaSidra, origem: str) -> None:
    """Guarda contra tabela/variável/categoria/território trocados (pegadinha 5 do docstring)."""
    if str(linha.get("NC", "")) != NIVEL_BRASIL:
        msg = f"{origem}: linha com nível territorial NC={linha.get('NC')!r}, esperado Brasil (1)"
        raise RespostaSidraInconsistente(msg)
    if str(linha.get("D2C", "")) != str(consulta.variavel):
        msg = (
            f"{origem}: linha com variável D2C={linha.get('D2C')!r}, "
            f"esperada {consulta.variavel} ({linha.get('D2N')!r})"
        )
        raise RespostaSidraInconsistente(msg)
    if consulta.categoria is not None and str(linha.get("D4C", "")) != str(consulta.categoria):
        msg = (
            f"{origem}: linha com categoria D4C={linha.get('D4C')!r}, "
            f"esperada c{consulta.classificacao}/{consulta.categoria}"
        )
        raise RespostaSidraInconsistente(msg)


def parse_valores(
    conteudo: bytes,
    *,
    series_id: str,
    origem: str,
    collected_at: datetime,
    minimo: int | None | object = DO_CONTRATO,
) -> pd.DataFrame:
    """Bytes do apisidra → DataFrame no contrato `ProcessedSeriesSchema` (8 colunas, long).

    Não grava nada: validar antes de escrever é o que CA-003 pede, e quem escreve é
    `gravar_processado_parquet`. Levanta em vez de devolver série curta, com período repetido,
    fora de ordem, com buraco de mês/trimestre, ou da tabela errada.

    `minimo` segue o idioma de `ClienteHTTP.json_array`: por default usa
    `ExtractorConfig.contagem_minima_esperada` (562 no IPCA, 122 no PIB); `None` desliga a guarda,
    que é o que a fixture — recorte de 2006 + 2026, limitada a 200 KB — precisa.
    """
    config = config_de(series_id)
    consulta = consulta_de(series_id)
    entrada = entrada_de(series_id)

    # R10: o `encoding` do contrato desce até a decodificação — nada herda o locale.
    bruto = json.loads(ler_texto(conteudo, config.encoding))
    if not isinstance(bruto, list):
        msg = f"{origem}: esperado array JSON, veio {type(bruto).__name__}"
        raise RespostaSidraInconsistente(msg)

    linhas = descartar_cabecalho(bruto, origem=origem)
    for linha in linhas:
        _conferir_linha(linha, consulta=consulta, origem=origem)

    datas = [fim_do_periodo(r.get("D3C"), freq=entrada.freq, origem=origem) for r in linhas]
    valores = [valor_sidra(r.get("V"), origem=f"{origem} @ {r.get('D3C')}") for r in linhas]

    quadro = pd.DataFrame(
        {
            # O `series_id` vem do catálogo, nunca do rótulo `D2N` da fonte (que é prosa).
            "series_id": series_id,
            "date": pd.to_datetime(pd.Series(datas, dtype="object")),
            "value": pd.Series(valores, dtype="float64"),
            "source": Fonte.IBGE_SIDRA.value,
            "freq": entrada.freq.value,
            # D-b: `vintage` = a data (sem hora) de `collected_at`, que sai do manifesto do
            # bruto. É a safra de extração — identifica a revisão do IBGE mesmo quando ela só
            # muda o passado, sem acrescentar período novo (RF-025 / Anti-SPEC §10.2.7).
            "vintage": pd.Timestamp(collected_at).tz_localize(None).normalize(),
            "unit": entrada.unit.value,
            "collected_at": pd.Timestamp(collected_at).tz_localize(None),
        }
    )
    piso = config.contagem_minima_esperada if minimo is DO_CONTRATO else minimo
    _validar(quadro, series_id=series_id, origem=origem, minimo=piso)  # type: ignore[arg-type]
    return quadro.reset_index(drop=True)


def _validar(quadro: pd.DataFrame, *, series_id: str, origem: str, minimo: int | None) -> None:
    """Guardas de conteúdo: contagem, duplicata, ordem, continuidade, data futura, monotonia."""
    exigir_contagem_minima(len(quadro), minimo=minimo, origem=f"{series_id} @ {origem}")

    if quadro["date"].isna().any():
        msg = f"{origem}: {int(quadro['date'].isna().sum())} linha(s) sem período"
        raise RespostaSidraInconsistente(msg)

    duplicadas = quadro.loc[quadro["date"].duplicated(keep=False), "date"]
    if not duplicadas.empty:
        amostra = sorted({d.date().isoformat() for d in duplicadas})[:5]
        msg = f"{origem}: período repetido (amostra: {amostra})"
        raise RespostaSidraInconsistente(msg)
    if not quadro["date"].is_monotonic_increasing:
        msg = f"{origem}: períodos fora de ordem crescente"
        raise RespostaSidraInconsistente(msg)

    _exigir_continuidade(quadro, series_id=series_id, origem=origem)

    futuras = quadro.loc[quadro["date"] > quadro["collected_at"], "date"]
    if not futuras.empty:
        msg = f"{origem}: período futuro no histórico (máx {futuras.max().date().isoformat()})"
        raise RespostaSidraInconsistente(msg)

    if series_id in SERIES_NUMERO_INDICE_DE_PRECO:
        _exigir_monotonia_de_indice(quadro, origem=origem)


def _exigir_continuidade(quadro: pd.DataFrame, *, series_id: str, origem: str) -> None:
    """Nenhum mês (ou trimestre) faltando entre o primeiro e o último período devolvido.

    A fonte publica a série inteira num GET; buraco no meio é período que o IBGE não devolveu, e
    preencher por interpolação está proibido (`CLAUDE.md §4`). Levantar é a única saída.
    """
    freq = entrada_de(series_id).freq
    codigo = "M" if freq is Freq.MENSAL else "Q"
    nome = "mes(es)" if freq is Freq.MENSAL else "trimestre(s)"
    periodos = quadro["date"].dt.to_period(codigo)
    esperados = pd.period_range(periodos.iloc[0], periodos.iloc[-1], freq=codigo)
    faltando = sorted(set(esperados) - set(periodos))
    if faltando:
        msg = (
            f"{origem}: {len(faltando)} {nome} faltando entre "
            f"{periodos.iloc[0]} e {periodos.iloc[-1]} (amostra: "
            f"{[str(p) for p in faltando[:5]]}). Lacuna não se preenche por interpolação"
        )
        raise RespostaSidraInconsistente(msg)


def _exigir_monotonia_de_indice(quadro: pd.DataFrame, *, origem: str) -> None:
    """CA-004: número-índice de preço sobe na maioria esmagadora dos meses.

    O piso é `MONOTONIA_MINIMA` e não os 99 % literais da SPEC porque a série real tem 21 meses
    de deflação (0,9626 de passos não decrescentes, medido em 2026-10-10) — ver `MONOTONIA_MINIMA`.
    """
    valores = quadro["value"].to_numpy()
    if len(valores) < 2:
        return
    passos = len(valores) - 1
    nao_decrescentes = int((valores[1:] >= valores[:-1]).sum())
    fracao = nao_decrescentes / passos
    if fracao < MONOTONIA_MINIMA:
        msg = (
            f"{origem}: só {fracao:.4f} dos {passos} passos são não decrescentes (mínimo "
            f"{MONOTONIA_MINIMA}). Isto não é um número-índice de preço — confira a variável"
        )
        raise RespostaSidraInconsistente(msg)


def fracao_nao_decrescente(quadro: pd.DataFrame) -> float:
    """Fração de passos não decrescentes da série — a evidência objetiva de CA-004."""
    valores = quadro["value"].to_numpy()
    if len(valores) < 2:
        return 1.0
    return float((valores[1:] >= valores[:-1]).sum()) / (len(valores) - 1)


def variacao_no_trimestre_por_razao(quadro: pd.DataFrame) -> pd.DataFrame:
    """IPCA trimestral a partir do número-índice: `I_fim / I_ini_anterior - 1`, em % (CA-005).

    Helper de **reconciliação**, não a transformação canônica: a grade trimestral do dataset é
    F-015/F-017 e passa pelo schema do canônico (classe C). Aqui serve a uma coisa só — provar que
    a razão do número-índice de `v/2266` dá o mesmo que o encadeamento geométrico de `v/63`
    (equivalentemente, de SGS 433) no mesmo trimestre, com tolerância de 1e-6.

    Devolve `date` (fim do trimestre) e `value` (variação em %), sem o primeiro trimestre da série,
    que não tem índice do trimestre anterior para servir de base.
    """
    serie = quadro.set_index("date")["value"].sort_index()
    fim_de_trimestre = serie.resample("QE").last()
    razao = fim_de_trimestre / fim_de_trimestre.shift(1) - 1.0
    return (
        pd.DataFrame({"date": razao.index, "value": razao.to_numpy() * 100.0})
        .dropna(subset=["value"])
        .reset_index(drop=True)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Extração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoSerie:
    """Evidência de dados de uma série — o que vai para o relatório do Feature Contract."""

    series_id: str
    identificador: str
    linhas: int
    data_inicio: date
    data_fim: date
    #: A **safra** da extração: a data de `collected_at` (do manifesto do bruto), não a última
    #: data do histórico — ver D-b em `docs/plans/DECISIONS_LOG.md §2`.
    vintage: date
    pct_nulos_value: float
    valor_inicial: float | None
    valor_final: float | None
    sha256_raw: str
    bytes_raw: int
    caminho_raw: Path | None
    raw_idempotente: bool
    caminho_processed: Path | None

    def resumo(self) -> str:
        """Uma linha para o log e para a CLI, **só em ASCII**.

        O `stdout` do terminal do Windows é cp1252: `print` de `->` escrito como seta Unicode
        levanta `UnicodeEncodeError` no meio de uma execução que já gravou tudo. Mesma raiz do
        Anti-SPEC §10.4.26, do outro lado do pipe.
        """
        raw = "idempotente" if self.raw_idempotente else "novo"
        final = "None" if self.valor_final is None else f"{self.valor_final:.6f}"
        return (
            f"{self.series_id}: {self.linhas} linhas, {self.data_inicio} -> {self.data_fim}, "
            f"ultimo={final}, nulos={self.pct_nulos_value:.2%}, "
            f"vintage={self.vintage}, raw {raw} sha256={self.sha256_raw[:12]}..."
        )


def _primeiro_valor_nao_nulo(quadro: pd.DataFrame) -> float | None:
    validos = quadro["value"].dropna()
    return None if validos.empty else float(validos.iloc[0])


def _resultado(
    quadro: pd.DataFrame,
    *,
    series_id: str,
    sha256_raw: str,
    bytes_raw: int,
    caminho_raw: Path | None,
    raw_idempotente: bool,
    caminho_processed: Path | None,
) -> ResultadoSerie:
    ultimo = quadro["value"].iloc[-1]
    return ResultadoSerie(
        series_id=series_id,
        identificador=consulta_de(series_id).identificador,
        linhas=len(quadro),
        data_inicio=quadro["date"].min().date(),
        data_fim=quadro["date"].max().date(),
        vintage=quadro["vintage"].max().date(),
        pct_nulos_value=float(quadro["value"].isna().mean()),
        valor_inicial=_primeiro_valor_nao_nulo(quadro),
        valor_final=None if pd.isna(ultimo) else float(ultimo),
        sha256_raw=sha256_raw,
        bytes_raw=bytes_raw,
        caminho_raw=caminho_raw,
        raw_idempotente=raw_idempotente,
        caminho_processed=caminho_processed,
    )


def nome_processado(series_id: str) -> str:
    """`sidra/SIDRA_1737_V2266.parquet` — caminho relativo dentro de `data/processed/`."""
    return f"{SUBPASTA_PROCESSED}/{series_id}.parquet"


def _baixar(series_id: str, *, transporte: Transporte | None) -> RespostaBruta:
    """GET + guarda R1 (HTTP 200 com corpo de erro/HTML/objeto) antes de qualquer parse."""
    config = config_de(series_id)
    cliente = ClienteHTTP(config, transporte=transporte)
    resposta = cliente.get()
    # A guarda de shape roda aqui, sobre a resposta, para que o corpo de erro com HTTP 200 nunca
    # alcance `json.loads` do parser nem `arquivar_bruto`. A contagem mínima é do parser, que sabe
    # descontar o cabeçalho — por isso `minimo=None` não é passado por aqui.
    validar_corpo_json_array(resposta, encoding=config.encoding)
    return resposta


def extrair_serie(
    series_id: str,
    *,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
) -> ResultadoSerie:
    """Baixa, arquiva o bruto, parseia e grava o processado de **uma** série.

    A `data_ref` do nome do arquivo bruto é a **última data do histórico** (o retrato), não
    "hoje": é o que torna o segundo download do mesmo retrato byte-idêntico e idempotente
    (CA-027) e o que faz uma revisão retroativa do IBGE bater em `ConteudoDivergente` em vez de
    sobrescrever o retrato anterior (R8/CA-122).
    """
    resposta = _baixar(series_id, transporte=transporte)
    conteudo = resposta.conteudo
    quadro = parse_valores(
        conteudo, series_id=series_id, origem=resposta.url, collected_at=resposta.obtida_em
    )
    data_ref = quadro["date"].max().date()

    arquivado = arquivar_bruto(
        conteudo,
        destino=caminho_destino_raw(config_de(series_id), raiz=raiz),
        nome=nome_arquivo_raw(
            consulta_de(series_id).slug, data_ref=data_ref, extensao=EXTENSAO_RAW
        ),
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
    )
    destino = (
        gravar_processado_parquet(quadro, nome=nome_processado(series_id), raiz=raiz)
        if gravar
        else None
    )
    resultado = _resultado(
        quadro,
        series_id=series_id,
        sha256_raw=arquivado.sha256,
        bytes_raw=arquivado.bytes_gravados,
        caminho_raw=arquivado.caminho,
        raw_idempotente=arquivado.idempotente,
        caminho_processed=destino,
    )
    _log.info("%s", resultado.resumo())
    return resultado


def _bruto_arquivado(series_id: str, *, raiz: Path | None) -> Path:
    """O arquivo bruto mais recente da série em `data/raw/sidra/` (modo `--offline`).

    O manifesto é `<nome>.meta.json` e **também** casa com `*__*.json`: sem o filtro de
    `SUFIXO_MANIFESTO` a ordenação reversa o escolheria antes do dado, e `--offline` parsearia o
    manifesto. É um erro que não aparece em fonte binária e aparece em toda fonte JSON.
    """
    pasta = caminho_destino_raw(config_de(series_id), raiz=raiz)
    slug = consulta_de(series_id).slug
    candidatos = sorted(
        (
            p
            for p in pasta.glob(f"{slug}__*.{EXTENSAO_RAW}")
            if not p.name.endswith(SUFIXO_MANIFESTO)
        ),
        reverse=True,
    )
    if not candidatos:
        msg = f"modo offline: nenhum bruto de {series_id} ({slug}) em {pasta}"
        raise ErroDeExtracao(msg)
    return candidatos[0]


def extrair_serie_offline(
    series_id: str,
    *,
    raiz: Path | None = None,
    gravar: bool = True,
    caminho: Path | None = None,
) -> ResultadoSerie:
    """Reprocessa uma série do bruto já arquivado — sem rede, sem reescrever `data/raw/`."""
    alvo = caminho or _bruto_arquivado(series_id, raiz=raiz)
    conteudo = alvo.read_bytes()
    # D-b: `collected_at` sai do manifesto do bruto, não do relógio — duas rodadas `--offline`
    # sobre o mesmo arquivo têm de produzir o mesmo Parquet.
    quadro = parse_valores(
        conteudo,
        series_id=series_id,
        origem=str(alvo),
        collected_at=obtido_em_arquivado(alvo) or datetime.now(tz=UTC),
    )
    destino = (
        gravar_processado_parquet(quadro, nome=nome_processado(series_id), raiz=raiz)
        if gravar
        else None
    )
    resultado = _resultado(
        quadro,
        series_id=series_id,
        sha256_raw=sha256_de(conteudo),
        bytes_raw=len(conteudo),
        caminho_raw=alvo,
        raw_idempotente=True,
        caminho_processed=destino,
    )
    _log.info("[offline] %s", resultado.resumo())
    return resultado


def extrair(
    series: Sequence[str] | None = None,
    *,
    offline: bool = False,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
) -> dict[str, ResultadoSerie]:
    """Roda as séries pedidas (default: `SERIES_SUPORTADAS`) e devolve a evidência por série."""
    alvos = tuple(series) if series else SERIES_SUPORTADAS
    resultados: dict[str, ResultadoSerie] = {}
    for series_id in alvos:
        if offline:
            resultados[series_id] = extrair_serie_offline(series_id, raiz=raiz, gravar=gravar)
        else:
            resultados[series_id] = extrair_serie(
                series_id, transporte=transporte, raiz=raiz, gravar=gravar
            )
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.ibge_sidra",
        description="Extrai IPCA e PIB trimestral do IBGE SIDRA (F-004, SPEC RF-002/RF-004).",
    )
    parser.add_argument(
        "--series",
        nargs="+",
        metavar="SERIES_ID",
        choices=SERIES_SUPORTADAS,
        help=f"subconjunto a extrair (default: todas — {' '.join(SERIES_SUPORTADAS)})",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reprocessa o bruto já em data/raw/sidra/, sem tocar a rede",
    )
    parser.add_argument(
        "--sem-gravar",
        action="store_true",
        help="não escreve em data/processed/ (só confere e imprime a evidência)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` em sucesso, `1` em qualquer `ErroDeExtracao`."""
    args = _parser().parse_args(list(argv) if argv is not None else None)
    configurar_logging()
    try:
        resultados = extrair(args.series, offline=args.offline, gravar=not args.sem_gravar)
    except ErroDeExtracao as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for resultado in resultados.values():
        print(resultado.resumo())
    cobrem_2006 = sum(1 for r in resultados.values() if r.data_inicio <= date(2006, 3, 31))
    print(f"{len(resultados)} serie(s); {cobrem_2006} cobrindo 1T2006")
    return 0


def _main_cli() -> None:  # pragma: no cover - invocado só por `python -m`
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _main_cli()
