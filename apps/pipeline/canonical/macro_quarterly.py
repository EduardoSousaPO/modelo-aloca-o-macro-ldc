"""F-015 — `macro_quarterly`: 83 trimestres de variáveis macro, *wide*. **Classe C.**

Materializa três artefatos em `data/canonical/`:

| Artefato | O que é |
|---|---|
| `macro_quarterly.parquet` | 83 linhas × 42 colunas, `2006Q1..2026Q3`, `MacroQuarterlySchema` |
| `macro_quarterly_provenance.parquet` | *long*, 1 linha por célula rastreável (CA-120) |
| `relatorio_macro.json` | nulos por coluna **com motivo**, canários, unidades, diff |

O que este módulo faz, e **só** isto:

1. **Lê a régua de F-014** (`alinhado_trimestral.parquet`) e usa os valores dela **bit a bit** para
   toda coluna de nível. Nenhum nível é recalculado aqui: `ipca_12m` de `2006Q1` **é** a célula de
   `BCB_SGS_13522` em `2006Q1` do alinhado (canário 1 do relatório).
2. **Alinha a curva** (`CURVA_*`, `INCLINACAO_*`, `BREAKEVEN_5A`) chamando `alinhar_series` de
   F-014 sobre a fatia `source=DERIVADO` de `raw_series` — essas séries ficaram **fora** de
   `alinhado_trimestral` por decisão de F-014 (`FONTES_FORA_DO_ALINHAMENTO`), e a função é pública
   exatamente para que a feature dona da derivação a chame depois.
3. **Monta a grade de apoio** `2001Q1..2005Q4` (20 trimestres) com a **mesma** regra de F-014, para
   que `pib_yoy`, `ibcbr_yoy`, `usdbrl_var_12m` e os deltas existam já em `2006Q1` em vez de
   nascerem nulos por falta de `T-4`/`T-1` dentro da janela. O apoio é **conferido célula a célula**
   contra `alinhado_trimestral` na parte que as duas cobrem (`conferir_apoio_contra_alinhado`): se
   divergir em um único valor, o build **para**. É o que torna a reexpressão da regra verificável
   em vez de uma segunda verdade.
4. **Deriva** as variações (a/a por razão, t/t por razão), a **aceleração** do IPCA 12m, a
   **tendência** (média móvel de 20 trimestres) e o **hiato** do IBC-Br, e o `vertice_extrapolado`.
5. **Acumula no trimestre** o que é fluxo e não ponto — `ipca_tri` (3 meses de `BCB_SGS_433`),
   `cdi_tri` (`BCB_SGS_12`) e `selic_over_tri` (`BCB_SGS_11`) — por **produto geométrico**, nunca
   soma, e só quando o trimestre está **completo** (contagem de observações igual à contagem de dias
   úteis da ANBIMA, ou 3 meses). Incompleto → `NULL` com motivo (Anti-SPEC §10.1.1, §10.1.4).
6. **Grava a procedência por célula** (`macro_quarterly_provenance`): `(quarter, column)` →
   `series_id`/`source`/`vintage`/`collected_at`. É assim que CA-120 é cumprido numa tabela wide
   (`CONTRACTS.md §3.1`).

O que este módulo **não** faz:

- **nenhuma estimativa.** `2026Q3` não tem PIB nem IBC-Br divulgados: as colunas ficam **nulas** e a
  linha carrega `is_estimated=True` (CA-060). Nunca uma estimativa "para fechar a linha".
- **nenhum z-score.** `MacroQuarterlySchema` não tem coluna de z-score; a padronização é de F-019.
  Se um dia tiver, a janela é **expanding** (só passado) — o `MacroQuarterlySchema` de hoje não
  oferece onde um z-score "fitted" na amostra inteira pudesse entrar sem ser notado.
- **nenhuma classificação de regime** (F-019) e **nenhuma materialização `asof`** (F-018). Esta é a
  materialização **`revised`**: `lag_adjusted = False` nas 83 linhas, por contrato.

## Unidade de cada coluna — a decisão que mais pode machucar a jusante

**Toda taxa e toda variação desta tabela estão em por cento / pontos percentuais**, nunca em fração.
É o que o vocabulário de unidades do projeto já usa (`UNIDADES_VALIDAS` tem `%`, `%a.a.`, `pp` e
nenhuma "fração"), o que `LIMIAR_SELIC_PP = 0.25` pressupõe para `selic_meta_delta`, e o que os três
canários exigem (`ipca_12m` de `2006Q1` tem de ser **5,32**, o número que o SGS 13522 publica).

→ **Consequência para F-017:** `ret_real = (1 + ret) / (1 + ipca_tri) − 1` de
`asset_returns_quarterly` trabalha em **fração**, então o consumidor de `ipca_tri` tem de dividir
por 100. O mapa completo coluna → unidade está em `UNIDADES` (abaixo) e é gravado em
`relatorio_macro.json → unidades`, para que a conversão seja uma leitura e não uma suposição.

## Anti-look-ahead, nesta tabela

Nenhuma célula do trimestre `T` usa observação com data de referência posterior ao fim de `T`. A
afirmação é verificável no artefato: o diagnóstico que `construir` devolve traz, por
`(quarter, column)`, a **última** `date_obs` consumida, e `relatorio_macro.json` publica o máximo
por coluna. Duas ressalvas honestas:

- a grade `civil`/`corrido` de F-014 mira o último dia **civil** do trimestre, que em 24 dos 83
  trimestres é 1 a 3 dias depois do último dia **útil** (`quarter_end`). `2006Q3` fecha em 29/09
  (sábado dia 30) e o IPCA de setembro tem `date = 2006-09-30`. É data de **referência**, não de
  divulgação: continua dentro de `T`;
- **data de divulgação** é outro assunto — o IPCA de setembro só sai em meados de outubro. Respeitar
  isso é a materialização `asof` (**F-018**), e é por isso que esta carrega `lag_adjusted=False`.

**Sem rede, sempre.** Entradas: `alinhado_trimestral.parquet`, `raw_series.parquet` e
`series_catalog.parquet` de `data/canonical/`, mais `data/processed/calendario/`.

**Idempotente por construção.** Nada aqui lê o relógio: `vintage`/`collected_at` vêm do dado (D-b) e
o relatório carrega `versao_build` (`sha256` do conjunto de módulos), não hora de geração.

Referências: SPEC RF-021 (CA-059..061), RF-025, RF-026, RF-047 (CA-120), CA-007, CA-044 ·
ADR-001 (Proposta: eixo inflação = **aceleração**) · ADR-006 §(b) ·
`docs/research/metodologia-regimes-macro.md §2`, §6.2 · `docs/contracts/CONTRACTS.md §3`, §3.1 ·
`docs/wiki/context/F-015.md` (dicionário de colunas + revisão numérica).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.canonical.alinhamento import (
    NOME_ALINHADO,
    Trimestre,
    alinhar_series,
    dias_uteis_de_lacuna,
    fatiar_para_alinhamento,
    grade_da_serie,
    grade_de_trimestres,
    inicio_observado_por_serie,
    selecionar_vintage,
    validar_indice_temporal,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    ErroCanonico,
    caminhos_dos_componentes,
    exigir_series,
    validar_procedencia,
)
from apps.pipeline.canonical.build_raw_series import (
    versao_build as _hash_dos_componentes,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    caminho_canonical,
    garantir_diretorio,
    raiz_repo,
    sha256_de,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from apps.pipeline.extract.calendario_anbima import Calendario
from packages.shared.schemas import (
    COLUNAS_RASTREAVEIS,
    LIMITE_FFILL_DIAS_UTEIS,
    AlinhadoTrimestralSchema,
    MacroQuarterlyProvenanceSchema,
    MacroQuarterlySchema,
    RawSeriesSchema,
    load_catalog,
    quarters_da_janela,
)
from packages.shared.schemas.macro_quarterly import (
    PRIMEIRO_TRIMESTRE,
    ULTIMO_TRIMESTRE,
)
from packages.shared.schemas.regimes import LIMIAR_SELIC_PP, CicloSelic

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────

NOME_MACRO = "macro_quarterly.parquet"
NOME_PROVENANCE = "macro_quarterly_provenance.parquet"
NOME_RELATORIO = "relatorio_macro.json"

#: Esta é a materialização **`revised`** (último `vintage` de cada série). O `asof` é F-018.
LAG_ADJUSTED = False
MATERIALIZACAO = "revised"

#: Os módulos que determinam o conteúdo de `macro_quarterly`, **nesta ordem** — base de
#: `versao_build`. Mesmo critério de F-014 (P1-1 do QA da Onda 2): este módulo, o contrato das duas
#: tabelas, a régua temporal de onde vem todo nível, o builder das guardas, o calendário que decide
#: todo `quarter_end` e o catálogo como dado. Mudar qualquer um muda o Parquet.
MODULOS_DO_MACRO: tuple[str, ...] = (
    "apps.pipeline.canonical.macro_quarterly",
    "packages.shared.schemas.macro_quarterly",
    "apps.pipeline.canonical.alinhamento",
    "packages.shared.schemas.alinhado_trimestral",
    "apps.pipeline.canonical.build_raw_series",
    "apps.pipeline.extract.calendario_anbima",
    "packages.shared.schemas.series_catalog_data",
)

N_TRIMESTRES_TENDENCIA = 20
"""ADR-001 §4 / metodologia §2: a tendência do IBC-Br é a média móvel de **20 trimestres**."""

PRIMEIRO_TRIMESTRE_DE_APOIO = "2001Q1"
"""Início da grade de apoio.

`2001Q1` e não antes porque é onde o calendário da ANBIMA de F-008 começa a ter cobertura
(`2001-01-01`); pedir `2000Q4` levantaria `ForaDaCoberturaDoCalendario`. 20 trimestres de apoio
bastam para todo `T-4` e todo `T-1` da janela, e é o máximo disponível.
"""

#: As 11 séries da curva (F-016), que F-014 deixou **fora** de `alinhado_trimestral` por serem
#: `source=DERIVADO`. F-015 as alinha aqui, com `alinhar_series`, exobre a mesma grade.
SERIES_DA_CURVA: tuple[str, ...] = (
    "CURVA_REAL_1A",
    "CURVA_REAL_3A",
    "CURVA_REAL_5A",
    "CURVA_NOMINAL_1A",
    "CURVA_NOMINAL_3A",
    "CURVA_NOMINAL_5A",
    "INCLINACAO_REAL_5A_1A",
    "INCLINACAO_REAL_5A_3A",
    "INCLINACAO_NOMINAL_5A_1A",
    "INCLINACAO_NOMINAL_5A_3A",
    "BREAKEVEN_5A",
)

#: Os quatro vértices que `MacroQuarterlySchema` publica — e cuja ausência acende
#: `vertice_extrapolado` (CA-023/024). A ordem é a de prioridade na procedência da flag.
VERTICES_PUBLICADOS: tuple[tuple[str, str], ...] = (
    ("curva_real_1a", "CURVA_REAL_1A"),
    ("curva_nominal_1a", "CURVA_NOMINAL_1A"),
    ("curva_real_5a", "CURVA_REAL_5A"),
    ("curva_nominal_5a", "CURVA_NOMINAL_5A"),
)

VERTICE_ANCORA = "CURVA_REAL_5A"
"""Série de procedência de `vertice_extrapolado` quando **nenhum** vértice faltou.

É o vértice com 0,00% de nulos no painel de F-016 — a âncora natural da família. Quando algum
vértice falta, a procedência é a do **primeiro que faltou** em `VERTICES_PUBLICADOS`: a flag é uma
afirmação sobre aquela ausência, então a linha de procedência aponta para ela.
"""

#: O esqueleto macro sem o qual esta tabela não é `macro_quarterly` — ausência para o build com
#: `BLOQUEADO — FONTE INDISPONÍVEL` (CA-076) em vez de entregar 83 linhas quase vazias.
SERIES_EXIGIDAS: tuple[str, ...] = (
    "BCB_SGS_1",
    "BCB_SGS_11",
    "BCB_SGS_12",
    "BCB_SGS_432",
    "BCB_SGS_433",
    "BCB_SGS_13522",
    "BCB_SGS_24364",
    "SIDRA_1620_V583_90707",
)


class ApoioDivergente(ErroCanonico):
    """A grade de apoio discorda de `alinhado_trimestral` numa célula que as duas cobrem.

    Não é dado ruim: é **bug de régua**. Se a reexpressão da regra de F-014 usada para os 20
    trimestres de apoio não reproduzir o alinhado dentro da janela, qualquer `T-4` calculado com ela
    está medindo outra coisa, e o build para em vez de publicar um a/a com duas convenções.
    """


class TrimestreIncompleto(ErroCanonico):
    """Reservada: trimestre sem a contagem de observações que a acumulação exige.

    Hoje o caminho de produção **não** levanta — trimestre incompleto vira `NULL` com motivo, que é
    o que CA-061/Anti-SPEC §10.1.1 pedem. A classe existe para o caso em que a ausência for de
    série **exigida** e precisar parar o build.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Dicionário de colunas: fórmula, série de origem, unidade e motivo de ausência
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Origem:
    """De onde vem uma coluna de `macro_quarterly` — a linha do dicionário de §5 da wiki.

    `series_id` nulo significa "não há fonte disponível hoje": a coluna sai **nula** e
    `motivo_ausencia` é publicado no relatório. Nunca é preenchida por proxy não acordado
    (`AGENTS.md §9`: `BLOQUEADO — FONTE INDISPONÍVEL` em vez de inventar).
    """

    series_id: str | None
    formula: str
    unidade: str
    motivo_ausencia: str | None = None


@dataclass(frozen=True, slots=True)
class Insumo:
    """Uma série materializada que entra numa coluna, e de que trimestre ela é lida.

    Existe porque `series_id` de `Origem` é a série do **catálogo**, e no Focus o catálogo registra
    o *EntitySet* (`FOCUS_ANUAIS`), não a série materializada (`FOCUS_A_SELIC_H0`) — é a convenção
    que F-010 documentou explicitamente para F-015. `deslocamento = 1` significa "a coleta do fim
    de `T-1`", que é a leitura de "coleta do início de T" da metodologia §2 (V1b).
    """

    series_id: str
    deslocamento: int = 0


#: Quais séries materializadas entram em cada coluna, quando isso **não** é
#: `(Insumo(ORIGENS[coluna].series_id),)`. É o que o diagnóstico anti-look-ahead consulta para
#: saber que data foi de fato consumida.
INSUMOS: dict[str, tuple[Insumo, ...]] = {
    "focus_ipca_12m": (Insumo("FOCUS_I12_IPCA_N", 1),),
    "focus_pib_ano": (Insumo("FOCUS_A_PIB_TOTAL_H0", 1), Insumo("FOCUS_A_PIB_TOTAL_H1", 1)),
    "focus_selic_fim": (Insumo("FOCUS_A_SELIC_H0", 1), Insumo("FOCUS_A_SELIC_H1", 1)),
    "juro_real_exante": (Insumo("CURVA_NOMINAL_1A"), Insumo("FOCUS_I12_IPCA_N", 1)),
    "surpresa_ipca": (Insumo("BCB_SGS_13522"), Insumo("FOCUS_I12_IPCA_N", 1)),
    "surpresa_pib": (
        Insumo("SIDRA_1620_V583_90707"),
        Insumo("FOCUS_A_PIB_TOTAL_H0", 1),
        Insumo("FOCUS_A_PIB_TOTAL_H1", 1),
    ),
    "surpresa_selic": (
        Insumo("BCB_SGS_432"),
        Insumo("FOCUS_A_SELIC_H0", 1),
        Insumo("FOCUS_A_SELIC_H1", 1),
    ),
}

#: As séries materializadas do Focus que esta feature lê de `data/processed/focus/` — e **só**
#: estas. `data/canonical/raw_series.parquet` não as tem (F-013 roda antes de F-010 nesta onda), e
#: reconstruí-lo aqui mexeria num artefato que F-017 está lendo em paralelo (`AGENTS.md §13`).
SERIES_DO_FOCUS: tuple[str, ...] = (
    "FOCUS_I12_IPCA_N",
    "FOCUS_A_PIB_TOTAL_H0",
    "FOCUS_A_PIB_TOTAL_H1",
    "FOCUS_A_SELIC_H0",
    "FOCUS_A_SELIC_H1",
)

#: Série materializada do Focus → entrada do `series_catalog` que a registra (CA-120).
CATALOGO_DO_FOCUS: dict[str, str] = {
    "FOCUS_I12_IPCA_N": "FOCUS_INFLACAO_12M",
    "FOCUS_A_PIB_TOTAL_H0": "FOCUS_ANUAIS",
    "FOCUS_A_PIB_TOTAL_H1": "FOCUS_ANUAIS",
    "FOCUS_A_SELIC_H0": "FOCUS_ANUAIS",
    "FOCUS_A_SELIC_H1": "FOCUS_ANUAIS",
}

_MOTIVO_FOCUS = (
    "depende do Focus (F-010): se `data/processed/focus/` não estiver materializado, a coluna sai "
    "nula — a V1 do pacote mínimo não depende do Focus (PLAN §5, corte nº 4)"
)
_MOTIVO_META = (
    "série histórica de metas de inflação do CMN é o gap G-02 (`a_confirmar`); ADR-001 escolheu "
    "aceleração justamente para não depender dela"
)

#: Coluna → origem. **É o contrato legível de F-015**: toda coluna rastreável de
#: `MacroQuarterlySchema` tem exatamente uma linha aqui, e o teste de contrato confere a bijeção.
ORIGENS: dict[str, Origem] = {
    # --- crescimento -----------------------------------------------------------------------
    "pib_yoy": Origem(
        "SIDRA_1620_V583_90707",
        "(v[T] / v[T-4] - 1) * 100 sobre o índice de volume **sem** ajuste sazonal",
        "%",
    ),
    "pib_qoq_sa": Origem(
        "SIDRA_5932_V6564_90707",
        "nível da série publicada pelo IBGE (variação T/T-1 dessazonalizada)",
        "%",
    ),
    "ibcbr_yoy": Origem(
        "BCB_SGS_24364",
        "(v[T] / v[T-4] - 1) * 100 sobre o IBC-Br **com** ajuste sazonal, fim de período",
        "%",
    ),
    "ibcbr_yoy_trend": Origem(
        "BCB_SGS_24364",
        f"média móvel de {N_TRIMESTRES_TENDENCIA} trimestres de `ibcbr_yoy` (janela cheia, "
        f"terminando em T; `min_periods` = {N_TRIMESTRES_TENDENCIA})",
        "%",
    ),
    "ibcbr_gap": Origem(
        "BCB_SGS_24364",
        "`ibcbr_yoy` - `ibcbr_yoy_trend` (hiato proxy; eixo de crescimento da V1, ADR-001 §4)",
        "pp",
    ),
    # --- inflação --------------------------------------------------------------------------
    "ipca_12m": Origem(
        "BCB_SGS_13522",
        "nível da série de IPCA acumulado em 12 meses, no fim do trimestre",
        "%",
    ),
    "ipca_12m_delta": Origem(
        "BCB_SGS_13522",
        "`ipca_12m`[T] - `ipca_12m`[T-1] — a **aceleração** que ADR-001 §4 adota como eixo de "
        "inflação da V1",
        "pp",
    ),
    "ipca_tri": Origem(
        "BCB_SGS_433",
        "(prod(1 + v/100) - 1) * 100 sobre os **3** meses do trimestre — geométrico, nunca soma",
        "%",
    ),
    "ipca_meta": Origem(None, "nível da meta do CMN vigente no trimestre", "%", _MOTIVO_META),
    "ipca_desvio_meta": Origem(
        None, "`ipca_12m` - `ipca_meta`", "pp", f"derivada de `ipca_meta`: {_MOTIVO_META}"
    ),
    # --- juros -----------------------------------------------------------------------------
    "selic_meta_fim": Origem(
        "BCB_SGS_432", "nível da meta Selic do Copom no último dia civil do trimestre", "%a.a."
    ),
    "selic_meta_delta": Origem(
        "BCB_SGS_432",
        "`selic_meta_fim`[T] - `selic_meta_fim`[T-1] — insumo do ciclo Selic da V2 "
        f"(limiar {LIMIAR_SELIC_PP} pp)",
        "pp",
    ),
    "selic_over_tri": Origem(
        "BCB_SGS_11",
        "(prod(1 + v/100) - 1) * 100 sobre a Selic over diária do trimestre",
        "%",
    ),
    "cdi_tri": Origem(
        "BCB_SGS_12",
        "(prod(1 + v/100) - 1) * 100 sobre o CDI diário do trimestre (ADR-006 §6)",
        "%",
    ),
    "juro_real_exante": Origem(
        "FOCUS_INFLACAO_12M",
        "((1 + `curva_nominal_1a`/100) / (1 + `focus_ipca_12m`/100) - 1) * 100 — Fisher **por "
        "razão**, não por subtração (ADR-006, Anti-SPEC §10.2.13). A ponta nominal é o pré de 1 "
        "ano de F-016 (`CURVA_NOMINAL_1A`), a ponta de inflação é `FOCUS_I12_IPCA_N` da coleta do "
        "fim de T-1",
        "%a.a.",
        _MOTIVO_FOCUS,
    ),
    # --- curva (F-016) ---------------------------------------------------------------------
    "curva_real_1a": Origem(
        "CURVA_REAL_1A", "nível do vértice interpolado, último dia útil", "%a.a."
    ),
    "curva_real_5a": Origem(
        "CURVA_REAL_5A", "nível do vértice interpolado, último dia útil", "%a.a."
    ),
    "curva_nominal_1a": Origem(
        "CURVA_NOMINAL_1A", "nível do vértice interpolado, último dia útil", "%a.a."
    ),
    "curva_nominal_5a": Origem(
        "CURVA_NOMINAL_5A", "nível do vértice interpolado, último dia útil", "%a.a."
    ),
    "inclinacao_real_5a_1a": Origem(
        "INCLINACAO_REAL_5A_1A",
        "nível da série de F-016 (5a - 1a). **Secundária** por D-i: a principal provisória é "
        "`INCLINACAO_REAL_5A_3A`, que não tem coluna neste schema (ver §7 do contexto de F-015)",
        "pp",
    ),
    "inclinacao_nominal_5a_1a": Origem(
        "INCLINACAO_NOMINAL_5A_1A", "nível da série de F-016 (5a - 1a)", "pp"
    ),
    "breakeven_5a": Origem(
        "BREAKEVEN_5A", "nível da série de F-016 (inflação implícita de 5 anos, por razão)", "%a.a."
    ),
    "vertice_extrapolado": Origem(
        VERTICE_ANCORA,
        "True se **algum** dos 4 vértices publicados é nulo no trimestre — a ausência que F-016 "
        "recusou extrapolar (CA-023/024)",
        "bool",
    ),
    # --- câmbio e externo ------------------------------------------------------------------
    "usdbrl_fim": Origem(
        "BCB_SGS_1", "nível da PTAX de venda no último dia útil do trimestre", "BRL"
    ),
    "usdbrl_var_tri": Origem("BCB_SGS_1", "(v[T] / v[T-1] - 1) * 100 — por razão (CA-044)", "%"),
    "usdbrl_var_12m": Origem("BCB_SGS_1", "(v[T] / v[T-4] - 1) * 100 — por razão (CA-044)", "%"),
    "termos_troca_yoy": Origem(
        None,
        "(v[T] / v[T-4] - 1) * 100 sobre o índice de termos de troca",
        "%",
        "nenhum índice de termos de troca (nem o proxy IC-Br do BCB) foi extraído até aqui; "
        "a DoR de F-015 já previa esta coluna nula e declarada",
    ),
    "embi_br_fim": Origem(
        None,
        "nível do EMBI+ Brasil no último dia útil do trimestre",
        "bps",
        "EMBI+ morre em 30/07/2024 (L8) e não há fonte livre para a série histórica; emendar "
        "outro spread seria substituição silenciosa (Anti-SPEC §10.3.19)",
    ),
    "embi_delta_tri": Origem(
        None, "`embi_br_fim`[T] - `embi_br_fim`[T-1]", "bps", "derivada de `embi_br_fim` (L8)"
    ),
    "ust10_fim": Origem("YAHOO_TNX", "nível do yield de 10 anos no último dia útil", "%a.a."),
    "vix_fim": Origem("YAHOO_VIX", "nível do VIX no último dia útil", "index"),
    # --- expectativas Focus (F-010) --------------------------------------------------------
    "focus_ipca_12m": Origem(
        "FOCUS_INFLACAO_12M",
        "mediana de `FOCUS_I12_IPCA_N` (IPCA 12 meses à frente, **não** suavizado) na última "
        "coleta até o último dia útil de T-1 — a 'coleta do início de T' da metodologia §2",
        "%",
        _MOTIVO_FOCUS,
    ),
    "focus_pib_ano": Origem(
        "FOCUS_ANUAIS",
        "mediana do PIB Total do **ano-calendário de T** na última coleta até o fim de T-1: "
        "`FOCUS_A_PIB_TOTAL_H0` quando a coleta já está no ano de T, `H1` quando T é um 1º "
        "trimestre (a coleta cai em dezembro do ano anterior)",
        "%",
        _MOTIVO_FOCUS,
    ),
    "focus_selic_fim": Origem(
        "FOCUS_ANUAIS",
        "mediana da Selic de fim do **ano-calendário de T** na última coleta até o fim de T-1 "
        "(`FOCUS_A_SELIC_H0`/`H1` pela mesma regra de `focus_pib_ano`)",
        "%a.a.",
        _MOTIVO_FOCUS,
    ),
    "surpresa_ipca": Origem(
        "FOCUS_INFLACAO_12M",
        "`ipca_12m` - `focus_ipca_12m` (metodologia §2 V1b: realizado menos a expectativa da "
        "coleta do início de T)",
        "pp",
        _MOTIVO_FOCUS,
    ),
    "surpresa_pib": Origem(
        "FOCUS_ANUAIS",
        "`pib_yoy` - `focus_pib_ano` (metodologia §2 V1b). **Limitação declarada:** o realizado é "
        "a/a trimestral e a expectativa é do ano-calendário — não são o mesmo objeto",
        "pp",
        _MOTIVO_FOCUS,
    ),
    "surpresa_selic": Origem(
        "FOCUS_ANUAIS",
        "`selic_meta_fim` - `focus_selic_fim`. **Limitação declarada:** o horizonte da "
        "expectativa encurta dentro do ano (12 meses num 1º trimestre, ~3 num 4º)",
        "pp",
        _MOTIVO_FOCUS,
    ),
}

#: Coluna → unidade, derivado de `ORIGENS` (nunca digitado duas vezes). Vai para o relatório.
UNIDADES: dict[str, str] = {nome: origem.unidade for nome, origem in ORIGENS.items()}

#: Colunas cujo valor é uma **acumulação** no trimestre, não um ponto de fim de período.
ACUMULADAS: dict[str, str] = {
    "ipca_tri": "BCB_SGS_433",
    "selic_over_tri": "BCB_SGS_11",
    "cdi_tri": "BCB_SGS_12",
}

MOTIVO_TRIMESTRE_INCOMPLETO = "trimestre_incompleto_para_acumulacao"
MOTIVO_SEM_LAG = "sem_trimestre_de_referencia_na_grade"
MOTIVO_JANELA_CURTA = "janela_da_media_movel_incompleta"
MOTIVO_SEM_FONTE = "sem_fonte_disponivel"
MOTIVO_SERIE_SEM_VALOR = "serie_sem_valor_no_trimestre"


def series_de_nivel() -> tuple[str, ...]:
    """As séries consumidas em **nível** (fim de período), sem repetição e em ordem estável.

    Derivada de `ORIGENS`, nunca digitada: coluna nova com `series_id` entra aqui sozinha. As séries
    de `ACUMULADAS` ficam de fora porque não são lidas como ponto de fim de período — são somadas
    geometricamente dentro do trimestre por `acumular_por_trimestre`.
    """
    fora = set(ACUMULADAS.values()) | set(SERIES_DA_CURVA) | set(CATALOGO_DO_FOCUS.values())
    vistas: dict[str, None] = {}
    for origem in ORIGENS.values():
        if origem.series_id is None or origem.series_id in fora:
            continue
        vistas.setdefault(origem.series_id, None)
    return tuple(vistas)


# ─────────────────────────────────────────────────────────────────────────────
# Transformações puras — cada uma com um teste unitário sintético nomeado
# ─────────────────────────────────────────────────────────────────────────────


def variacao_por_razao(serie: pd.Series, passos: int) -> pd.Series:
    """`(v[t] / v[t-passos] - 1) * 100` — variação **por razão**, em por cento.

    Nunca por diferença de logaritmo nem por subtração de níveis: é a convenção de ADR-006 §(b) e
    a que CA-044 exige para `usdbrl_var_tri`/`usdbrl_var_12m`. `passos=4` é a/a numa grade
    trimestral; `passos=1` é t/t. Denominador nulo, zero ou ausente → `NaN`, nunca `0`.
    """
    if passos < 1:
        msg = f"passos tem de ser >= 1 (recebido {passos})"
        raise ValueError(msg)
    base = serie.shift(passos)
    base = base.where(base.ne(0))
    return (serie / base - 1.0) * 100.0


def diferenca_em_pp(serie: pd.Series, passos: int = 1) -> pd.Series:
    """`v[t] - v[t-passos]`, em pontos percentuais — a **aceleração** quando `serie` já é taxa.

    É o que ADR-001 §4 chama de eixo de inflação da V1 (`ipca_12m_delta`) e o que alimenta o ciclo
    Selic (`selic_meta_delta`). Diferença, e não razão, porque a grandeza já está em pontos
    percentuais: a razão de duas taxas não tem leitura econômica aqui.
    """
    if passos < 1:
        msg = f"passos tem de ser >= 1 (recebido {passos})"
        raise ValueError(msg)
    return serie - serie.shift(passos)


def media_movel(serie: pd.Series, janela: int = N_TRIMESTRES_TENDENCIA) -> pd.Series:
    """Média móvel de `janela` trimestres **terminando em t**, com janela **cheia** obrigatória.

    `min_periods = janela`: com 19 observações o resultado é `NaN`, não uma média de 19. Média de
    janela parcial não é dado inventado, mas é **outro estimador** — e um cujo significado muda ao
    longo do tempo, o que tornaria o hiato de 2006 incomparável com o de 2015. A ausência fica
    declarada no relatório (`nulos_por_coluna.<coluna>.motivos`) em vez de ser dissolvida.
    """
    if janela < 1:
        msg = f"janela tem de ser >= 1 (recebido {janela})"
        raise ValueError(msg)
    return serie.rolling(window=janela, min_periods=janela).mean()


def hiato_vs_tendencia(
    yoy: pd.Series, *, janela: int = N_TRIMESTRES_TENDENCIA
) -> tuple[pd.Series, pd.Series]:
    """`(tendência, hiato)` = `(média móvel de janela, yoy - tendência)`.

    É o eixo de crescimento da V1 (ADR-001 §4 / metodologia §2): IBC-Br a/a **menos** a média móvel
    de 20 trimestres de si mesma. Com menos de `janela` trimestres de a/a disponíveis, as duas
    séries saem nulas no ponto — o que CA-007 pede que seja ou preenchido ou marcado, e que o
    relatório declara trimestre a trimestre.
    """
    tendencia = media_movel(yoy, janela=janela)
    return tendencia, yoy - tendencia


def acumulacao_geometrica(valores_percentuais: Sequence[float] | pd.Series) -> float:
    """`(prod(1 + v/100) - 1) * 100` — encadeamento **geométrico** de taxas em por cento.

    A soma simples erra sistematicamente para cima (e o erro cresce com o nível da taxa): em
    4T2008, com a Selic a 13,75%, a diferença entre o produto e a soma dos ~63 dias úteis já é
    material. É a mesma convenção de ADR-006 §6 para o CDI trimestral e de CA-070 para retornos.
    """
    valores = pd.Series(list(valores_percentuais), dtype="float64")
    if valores.empty:
        msg = "acumulação geométrica de série vazia não é 0: é ausência"
        raise ValueError(msg)
    if bool(valores.isna().any()):
        msg = "acumulação geométrica com valor nulo: o trimestre está incompleto, não é 0"
        raise ValueError(msg)
    return float((np.prod(1.0 + valores.to_numpy() / 100.0) - 1.0) * 100.0)


def ciclo_selic(delta_pp: float | None, *, limiar: float = LIMIAR_SELIC_PP) -> str | None:
    """Ciclo de política monetária do trimestre, a partir de `selic_meta_delta`.

    Regra do contrato (`CONTRACTS.md §5.3`, `LIMIAR_SELIC_PP = 0,25`; metodologia §2 V2):
    `delta < -limiar` → `CORTE` (cortando) · `delta > +limiar` → `ALTA` (subindo) ·
    caso contrário → `NEUTRO` (parada). `None` entra e sai `None` — trimestre sem delta não tem
    ciclo, e chamar isso de `NEUTRO` inventaria uma pausa que ninguém mediu.

    **Não é coluna desta tabela.** `MacroQuarterlySchema` não tem `ciclo_selic`: o rótulo mora em
    `RegimesSchema` (F-019). A função vive aqui porque o insumo (`selic_meta_delta`) é desta
    feature, e `relatorio_macro.json` publica a distribuição medida dos 3 estados.
    """
    if delta_pp is None or (isinstance(delta_pp, float) and pd.isna(delta_pp)):
        return None
    if delta_pp < -limiar:
        return str(CicloSelic.CORTE)
    if delta_pp > limiar:
        return str(CicloSelic.ALTA)
    return str(CicloSelic.NEUTRO)


# ─────────────────────────────────────────────────────────────────────────────
# A grade: janela de 83 + 20 trimestres de apoio
# ─────────────────────────────────────────────────────────────────────────────


def quarters_de_apoio() -> tuple[str, ...]:
    """Os 20 rótulos `2001Q1..2005Q4` — derivados, nunca digitados."""
    fim = pd.Period(PRIMEIRO_TRIMESTRE, freq="Q") - 1
    periodos = pd.period_range(PRIMEIRO_TRIMESTRE_DE_APOIO, str(fim), freq="Q")
    return tuple(str(p) for p in periodos)


def grade_estendida(
    calendario: Calendario, *, quarters: Sequence[str] | None = None
) -> tuple[Trimestre, ...]:
    """Apoio + janela, numa só tupla ordenada — a grade sobre a qual tudo é derivado.

    `quarters` é a **janela** (os 83 em produção; um recorte no teste); o apoio é sempre os 20
    trimestres anteriores ao primeiro da janela que o calendário cobre.
    """
    janela = tuple(quarters) if quarters is not None else quarters_da_janela()
    if not janela:
        msg = "janela vazia: não há trimestre para materializar"
        raise ValueError(msg)
    primeiro = pd.Period(janela[0], freq="Q")
    apoio = [
        str(primeiro - n)
        for n in range(N_TRIMESTRES_TENDENCIA, 0, -1)
        if (primeiro - n).start_time.date() >= calendario.cobertura_inicio
    ]
    return grade_de_trimestres(calendario, quarters=(*apoio, *janela))


# ─────────────────────────────────────────────────────────────────────────────
# Observação de fim de período — a mesma regra de F-014, aplicável ao apoio
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Celula:
    """Uma observação de fim de período: o valor, a data de onde veio e a lacuna medida."""

    quarter: str
    series_id: str
    date_alvo: date
    date_obs: date | None
    value: float | None
    lacuna_dias_uteis: int
    motivo_nulo: str | None


def observacoes_de_fim_de_periodo(
    raw: pd.DataFrame,
    *,
    calendario: Calendario,
    trimestres: Sequence[Trimestre],
    inicio_por_serie: Mapping[str, Any],
) -> pd.DataFrame:
    """A regra de F-014 (`alinhar_series`) reexpressa para uma grade **que pode sair da janela**.

    Existe por um motivo só: `AlinhadoTrimestralSchema` recusa, por contrato, qualquer `quarter`
    fora de `2006Q1..2026Q3` (check `quarter_dentro_da_janela_de_83`), e `alinhar_series` valida com
    ele. Sem os 20 trimestres de apoio, `pib_yoy` de `2006Q1` precisaria de `2005Q1` e nasceria
    **nulo** — e, por tabela, `ibcbr_gap` só existiria de 2011Q4 em diante em vez de 2009Q4.

    A reexpressão usa as **peças públicas** de F-014 (`grade_da_serie`, `dias_uteis_de_lacuna`,
    `LIMITE_FFILL_DIAS_UTEIS`, `selecionar_vintage`, `validar_indice_temporal`) e é **conferida
    célula a célula** contra o artefato de F-014 em `conferir_apoio_contra_alinhado`, que o build
    chama antes de derivar qualquer coisa. Duas réguas discordando é o modo de falha que esta
    conferência existe para tornar impossível.

    Devolve um quadro *long* `(quarter, series_id, date_alvo, date_obs, value, lacuna_dias_uteis,
    motivo_nulo)`, com uma linha por `(trimestre, série)` a partir do início real da série.
    """
    faltando = [c for c in RawSeriesSchema.to_schema().columns if c not in raw.columns]
    if faltando:
        msg = f"colunas ausentes para observar fim de período: {faltando}"
        raise SerieInconsistente(msg)

    preparado = validar_indice_temporal(selecionar_vintage(raw))
    linhas: list[Celula] = []
    for series_id, grupo in preparado.groupby("series_id", sort=True):
        sid = str(series_id)
        if sid not in inicio_por_serie:
            msg = f"{sid}: sem `data_inicio_observada` em inicio_por_serie"
            raise SerieInconsistente(msg)
        inicio = pd.Timestamp(inicio_por_serie[sid])
        grade = grade_da_serie(sid, str(grupo["freq"].iloc[0]))
        com_valor = grupo.loc[grupo["value"].notna()]
        datas = pd.DatetimeIndex(com_valor["date"]).to_numpy()
        valores = com_valor["value"].to_numpy()

        for tri in trimestres:
            alvo = tri.alvo(grade)
            alvo_ts = pd.Timestamp(alvo)
            if inicio > alvo_ts:
                continue
            posicao = int(np.searchsorted(datas, np.datetime64(alvo_ts), side="right")) - 1
            if posicao < 0:
                linhas.append(Celula(tri.quarter, sid, alvo, None, None, 0, MOTIVO_SERIE_SEM_VALOR))
                continue
            ultima = pd.Timestamp(datas[posicao])
            lacuna = dias_uteis_de_lacuna(calendario, ultima.date(), alvo)
            if lacuna > LIMITE_FFILL_DIAS_UTEIS:
                linhas.append(
                    Celula(tri.quarter, sid, alvo, None, None, lacuna, MOTIVO_SERIE_SEM_VALOR)
                )
                continue
            linhas.append(
                Celula(tri.quarter, sid, alvo, ultima.date(), float(valores[posicao]), lacuna, None)
            )

    quadro = pd.DataFrame([asdict(c) for c in linhas])
    if quadro.empty:
        msg = "nenhuma observação de fim de período na grade pedida"
        raise FonteIndisponivel(f"BLOQUEADO — FONTE INDISPONÍVEL: {msg}")
    return quadro.sort_values(["series_id", "quarter"], kind="mergesort").reset_index(drop=True)


def conferir_apoio_contra_alinhado(apoio: pd.DataFrame, alinhado: pd.DataFrame) -> int:
    """Confere, célula a célula e **sem tolerância**, o apoio contra `alinhado_trimestral`.

    Compara só o que as duas cobrem — `(series_id, quarter)` presentes nos dois — e exige igualdade
    exata de `value` (nulo contra nulo inclusive) e de `date_obs`. Devolve o nº de células
    conferidas; divergência levanta `ApoioDivergente`.

    É o **diff numérico de classe C** desta feature na direção que importa: nenhum nível publicado
    em `macro_quarterly` pode diferir da régua de F-014, e nenhuma derivada pode ter sido calculada
    com uma régua diferente da dos níveis.
    """
    esquerda = apoio.loc[:, ["series_id", "quarter", "date_obs", "value"]].copy()
    direita = alinhado.loc[:, ["series_id", "quarter", "date_obs", "value"]].copy()
    esquerda["date_obs"] = pd.to_datetime(esquerda["date_obs"])
    direita["date_obs"] = pd.to_datetime(direita["date_obs"])
    juntos = esquerda.merge(direita, on=["series_id", "quarter"], suffixes=("_apoio", "_f014"))
    if juntos.empty:
        msg = (
            "apoio e alinhado_trimestral não têm nenhuma célula em comum — a conferência de régua "
            "não pode ser feita, e sem ela o apoio não é publicável"
        )
        raise ApoioDivergente(msg)

    valor_igual = (juntos["value_apoio"].isna() & juntos["value_f014"].isna()) | (
        juntos["value_apoio"] == juntos["value_f014"]
    )
    data_igual = (juntos["date_obs_apoio"].isna() & juntos["date_obs_f014"].isna()) | (
        juntos["date_obs_apoio"] == juntos["date_obs_f014"]
    )
    ruim = juntos.loc[~(valor_igual & data_igual)]
    if not ruim.empty:
        amostra = [
            f"{r.series_id} {r.quarter}: apoio {r.value_apoio!r}@{r.date_obs_apoio} != "
            f"F-014 {r.value_f014!r}@{r.date_obs_f014}"
            for r in ruim.head(5).itertuples(index=False)
        ]
        msg = (
            f"{len(ruim)} célula(s) do apoio divergem de alinhado_trimestral: {amostra}. "
            f"As duas réguas têm de ser a mesma — o build para (classe C)."
        )
        raise ApoioDivergente(msg)
    return int(len(juntos))


# ─────────────────────────────────────────────────────────────────────────────
# Acumulação no trimestre (fluxo, não ponto)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Acumulado:
    """O resultado de acumular um trimestre: valor, contagens, última data e motivo.

    `date_obs_max` é a data da **última** observação que entrou no produto — é o que o teste
    anti-look-ahead inspeciona para as três colunas de fluxo (`ipca_tri`, `cdi_tri`,
    `selic_over_tri`), que não têm uma `date_obs` única como as colunas de nível.
    """

    quarter: str
    value: float | None
    n_obs: int
    n_esperado: int
    motivo_nulo: str | None
    date_obs_max: date | None = None


def acumular_por_trimestre(
    pontos: pd.DataFrame,
    *,
    series_id: str,
    calendario: Calendario,
    trimestres: Sequence[Trimestre],
) -> list[Acumulado]:
    """Acumula geometricamente a série `series_id` dentro de cada trimestre da grade.

    Janela de `T` = `(fim de T-1, fim de T]`, com o "fim" da **grade da própria série**: último dia
    útil para série diária bancária, último dia civil para série mensal. Semiaberta à esquerda para
    que nenhum dia seja contado duas vezes entre trimestres vizinhos.

    **Completude é obrigatória.** Série diária: a contagem de observações tem de ser igual ao número
    de dias úteis da ANBIMA na janela. Série mensal: 3 observações. Qualquer coisa diferente →
    `value = None` com `MOTIVO_TRIMESTRE_INCOMPLETO` e as duas contagens registradas. Acumular um
    trimestre com buraco entregaria uma taxa **menor** que a real sem levantar exceção — o modo de
    falha silenciosa que a Anti-SPEC §10.1.1/§10.1.4 nomeia.
    """
    fatia = pontos.loc[pontos["series_id"] == series_id]
    if fatia.empty:
        return [
            Acumulado(t.quarter, None, 0, 0, MOTIVO_SERIE_SEM_VALOR, None) for t in trimestres[1:]
        ]
    grade = grade_da_serie(series_id, str(fatia["freq"].iloc[0]))
    serie = (
        fatia.loc[fatia["value"].notna()].set_index("date")["value"].sort_index().astype("float64")
    )

    saida: list[Acumulado] = []
    for anterior, atual in zip(trimestres[:-1], trimestres[1:], strict=True):
        inicio = pd.Timestamp(anterior.alvo(grade))
        fim = pd.Timestamp(atual.alvo(grade))
        janela = serie.loc[(serie.index > inicio) & (serie.index <= fim)]
        if grade == "civil":
            esperado = len(pd.period_range(inicio + pd.Timedelta(days=1), fim, freq="M"))
        else:
            esperado = calendario.dias_uteis_entre(
                (inicio + pd.Timedelta(days=1)).date(), fim.date()
            )
        if len(janela) == 0 or len(janela) != esperado:
            saida.append(
                Acumulado(
                    atual.quarter,
                    None,
                    int(len(janela)),
                    int(esperado),
                    MOTIVO_TRIMESTRE_INCOMPLETO if len(janela) else MOTIVO_SERIE_SEM_VALOR,
                    None,
                )
            )
            continue
        saida.append(
            Acumulado(
                atual.quarter,
                acumulacao_geometrica(janela),
                int(len(janela)),
                int(esperado),
                None,
                pd.Timestamp(janela.index.max()).date(),
            )
        )
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# Montagem da tabela wide + procedência
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoMacro:
    """O que o build produziu — o CLI imprime, o teste inspeciona, o QA confere."""

    macro: pd.DataFrame
    provenance: pd.DataFrame
    diagnostico: pd.DataFrame
    relatorio: dict[str, Any]
    trimestres: tuple[Trimestre, ...]
    caminho_macro: Path
    caminho_provenance: Path
    caminho_relatorio: Path


def _niveis_wide(observacoes: pd.DataFrame, quarters: Sequence[str]) -> pd.DataFrame:
    """`observacoes` (long) → quadro `quarter × series_id` de valores de fim de período."""
    wide = observacoes.pivot_table(
        index="quarter", columns="series_id", values="value", aggfunc="first", dropna=False
    )
    return wide.reindex(index=list(quarters))


def _datas_wide(observacoes: pd.DataFrame, quarters: Sequence[str]) -> pd.DataFrame:
    """Idem, para `date_obs` — é o que o teste anti-look-ahead inspeciona."""
    copia = observacoes.copy()
    copia["date_obs"] = pd.to_datetime(copia["date_obs"])
    wide = copia.pivot_table(
        index="quarter", columns="series_id", values="date_obs", aggfunc="first", dropna=False
    )
    return wide.reindex(index=list(quarters))


def _coluna(wide: pd.DataFrame, series_id: str, quarters: Sequence[str]) -> pd.Series:
    """A coluna da série no quadro wide, ou uma coluna toda nula se a série não existe."""
    if series_id in wide.columns:
        return wide[series_id].astype("float64")
    return pd.Series(np.nan, index=list(quarters), dtype="float64")


def montar_macro(
    *,
    observacoes: pd.DataFrame,
    acumulados: Mapping[str, Mapping[str, Acumulado]],
    metadado: Mapping[str, Mapping[str, Any]],
    trimestres: Sequence[Trimestre],
    quarters: Sequence[str],
    fonte_versao: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """`(macro, provenance, diagnostico)` — a montagem inteira, sem disco e sem relógio.

    `observacoes` cobre a grade **estendida** (apoio + janela); `quarters` é só a janela publicada.
    Toda derivada é calculada na grade estendida e **depois** recortada, que é como `T-4` de
    `2006Q1` existe. O recorte é a última operação: nada da janela depende da ordem em que as
    colunas foram montadas.
    """
    todos = [t.quarter for t in trimestres]
    niveis = _niveis_wide(observacoes, todos)
    datas = _datas_wide(observacoes, todos)
    valores: dict[str, pd.Series] = {}

    def nivel(series_id: str) -> pd.Series:
        return _coluna(niveis, series_id, todos)

    def nulo() -> pd.Series:
        return pd.Series(np.nan, index=todos, dtype="float64")

    # --- crescimento -----------------------------------------------------------------------
    valores["pib_yoy"] = variacao_por_razao(nivel("SIDRA_1620_V583_90707"), 4)
    valores["pib_qoq_sa"] = nivel("SIDRA_5932_V6564_90707")
    valores["ibcbr_yoy"] = variacao_por_razao(nivel("BCB_SGS_24364"), 4)
    tendencia, gap = hiato_vs_tendencia(valores["ibcbr_yoy"])
    valores["ibcbr_yoy_trend"] = tendencia
    valores["ibcbr_gap"] = gap

    # --- inflação --------------------------------------------------------------------------
    valores["ipca_12m"] = nivel("BCB_SGS_13522")
    valores["ipca_12m_delta"] = diferenca_em_pp(valores["ipca_12m"])
    valores["ipca_meta"] = nulo()
    valores["ipca_desvio_meta"] = nulo()

    # --- juros -----------------------------------------------------------------------------
    valores["selic_meta_fim"] = nivel("BCB_SGS_432")
    valores["selic_meta_delta"] = diferenca_em_pp(valores["selic_meta_fim"])

    # --- acumuladas (fluxo) ----------------------------------------------------------------
    for coluna, series_id in ACUMULADAS.items():
        por_quarter = acumulados.get(series_id, {})
        valores[coluna] = pd.Series(
            {q: (por_quarter[q].value if q in por_quarter else np.nan) for q in todos},
            dtype="float64",
        )

    # --- curva (F-016) ---------------------------------------------------------------------
    for coluna, series_id in VERTICES_PUBLICADOS:
        valores[coluna] = nivel(series_id)
    valores["inclinacao_real_5a_1a"] = nivel("INCLINACAO_REAL_5A_1A")
    valores["inclinacao_nominal_5a_1a"] = nivel("INCLINACAO_NOMINAL_5A_1A")
    valores["breakeven_5a"] = nivel("BREAKEVEN_5A")
    faltou_vertice = pd.concat(
        [valores[coluna].isna() for coluna, _ in VERTICES_PUBLICADOS], axis=1
    ).any(axis=1)

    # --- câmbio e externo ------------------------------------------------------------------
    valores["usdbrl_fim"] = nivel("BCB_SGS_1")
    valores["usdbrl_var_tri"] = variacao_por_razao(valores["usdbrl_fim"], 1)
    valores["usdbrl_var_12m"] = variacao_por_razao(valores["usdbrl_fim"], 4)
    valores["termos_troca_yoy"] = nulo()
    valores["embi_br_fim"] = nulo()
    valores["embi_delta_tri"] = nulo()
    valores["ust10_fim"] = nivel("YAHOO_TNX")
    valores["vix_fim"] = nivel("YAHOO_VIX")

    # --- expectativas (F-010) --------------------------------------------------------------
    # A régua do Focus é a **coleta** (F-010: `date` = dia da pesquisa, nunca fim de período), e a
    # coleta de referência de T é a última até o fim de T-1 — daí o deslocamento de 1 trimestre.
    valores["focus_ipca_12m"] = focus_do_inicio_do_trimestre(nivel("FOCUS_I12_IPCA_N"), None, todos)
    valores["focus_pib_ano"] = focus_do_inicio_do_trimestre(
        nivel("FOCUS_A_PIB_TOTAL_H0"), nivel("FOCUS_A_PIB_TOTAL_H1"), todos
    )
    valores["focus_selic_fim"] = focus_do_inicio_do_trimestre(
        nivel("FOCUS_A_SELIC_H0"), nivel("FOCUS_A_SELIC_H1"), todos
    )
    valores["juro_real_exante"] = (
        (1.0 + valores["curva_nominal_1a"] / 100.0) / (1.0 + valores["focus_ipca_12m"] / 100.0)
        - 1.0
    ) * 100.0
    valores["surpresa_ipca"] = valores["ipca_12m"] - valores["focus_ipca_12m"]
    valores["surpresa_pib"] = valores["pib_yoy"] - valores["focus_pib_ano"]
    valores["surpresa_selic"] = valores["selic_meta_fim"] - valores["focus_selic_fim"]

    janela = list(quarters)
    macro = pd.DataFrame({"quarter": janela})
    macro["quarter_end"] = [
        pd.Timestamp(t.quarter_end) for t in trimestres if t.quarter in set(janela)
    ]
    for coluna in COLUNAS_RASTREAVEIS:
        if coluna == "vertice_extrapolado":
            macro[coluna] = faltou_vertice.reindex(janela).fillna(value=True).to_numpy(dtype=bool)
            continue
        macro[coluna] = valores[coluna].reindex(janela).to_numpy(dtype="float64")
    macro["is_estimated"] = [q == ULTIMO_TRIMESTRE for q in janela]
    macro["lag_adjusted"] = LAG_ADJUSTED
    macro["fonte_versao"] = fonte_versao
    macro = macro.loc[:, list(MacroQuarterlySchema.to_schema().columns)]

    provenance, diagnostico = _montar_procedencia(
        macro=macro,
        datas=datas,
        acumulados=acumulados,
        metadado=metadado,
        faltou_vertice=faltou_vertice,
        quarters=janela,
        fonte_versao=fonte_versao,
    )
    return (
        MacroQuarterlySchema.validate(macro, lazy=True),
        MacroQuarterlyProvenanceSchema.validate(provenance, lazy=True),
        diagnostico,
    )


def _serie_de_procedencia(coluna: str, quarter: str, faltou_vertice: pd.Series) -> str | None:
    """A `series_id` que responde por `(quarter, coluna)` — uma só, que é o que a PK permite."""
    if coluna != "vertice_extrapolado":
        return ORIGENS[coluna].series_id
    if not bool(faltou_vertice.get(quarter, True)):
        return VERTICE_ANCORA
    return None  # resolvido pelo chamador: o primeiro vértice que faltou


def insumos_da_coluna(coluna: str) -> tuple[Insumo, ...]:
    """Quais séries materializadas, e de que trimestre, a coluna consome."""
    if coluna in INSUMOS:
        return INSUMOS[coluna]
    series_id = ORIGENS[coluna].series_id
    return (Insumo(series_id),) if series_id is not None else ()


def _datas_consumidas(coluna: str, quarter: str, datas: pd.DataFrame) -> pd.Timestamp | None:
    """A **última** `date_obs` que a célula `(quarter, coluna)` consumiu.

    Para nível é a própria `date_obs` do trimestre; para derivada com `T-k` é a de `T`, que é a mais
    recente das duas (`T-k` é, por construção, anterior); para coluna de Focus é a `date_obs` da
    coleta de `T-1`. É o que o teste anti-look-ahead inspeciona e o que `relatorio_macro.json`
    publica por coluna.
    """
    candidatas: list[pd.Timestamp] = []
    for insumo in insumos_da_coluna(coluna):
        if insumo.series_id not in datas.columns:
            continue
        rotulo = str(pd.Period(quarter, freq="Q") - insumo.deslocamento)
        if rotulo not in datas.index:
            continue
        valor = datas.loc[rotulo, insumo.series_id]
        if valor is not None and pd.notna(valor):
            candidatas.append(pd.Timestamp(valor))
    return max(candidatas) if candidatas else None


def _montar_procedencia(
    *,
    macro: pd.DataFrame,
    datas: pd.DataFrame,
    acumulados: Mapping[str, Mapping[str, Acumulado]],
    metadado: Mapping[str, Mapping[str, Any]],
    faltou_vertice: pd.Series,
    quarters: Sequence[str],
    fonte_versao: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Uma linha de procedência por célula **não nula** de coluna rastreável (CA-120)."""
    linhas: list[dict[str, Any]] = []
    diagnostico: list[dict[str, Any]] = []
    indexado = macro.set_index("quarter")
    for coluna in COLUNAS_RASTREAVEIS:
        origem = ORIGENS[coluna]
        for quarter in quarters:
            valor = indexado.loc[quarter, coluna]
            preenchida = bool(valor) if coluna == "vertice_extrapolado" else pd.notna(valor)
            series_id = origem.series_id
            if coluna == "vertice_extrapolado":
                series_id = _serie_de_procedencia(coluna, quarter, faltou_vertice)
                if series_id is None:
                    series_id = next(
                        (
                            sid
                            for nome, sid in VERTICES_PUBLICADOS
                            if pd.isna(indexado.loc[quarter, nome])
                        ),
                        VERTICE_ANCORA,
                    )
                preenchida = True  # a flag é booleana e nunca nula: sempre tem procedência
            if series_id is None or not preenchida:
                continue
            meta = metadado.get(series_id)
            if meta is None:
                msg = (
                    f"{coluna}/{quarter}: série {series_id} sem metadado de procedência — "
                    f"`macro_quarterly_provenance` não pode ter linha sem `source`/`collected_at`"
                )
                raise SerieInconsistente(msg)
            ultima = _datas_consumidas(coluna, quarter, datas)
            if coluna in ACUMULADAS:
                detalhe = acumulados.get(series_id, {}).get(quarter)
                ultima = (
                    pd.Timestamp(detalhe.date_obs_max)
                    if detalhe is not None and detalhe.date_obs_max is not None
                    else None
                )
            linhas.append(
                {
                    "quarter": quarter,
                    "column": coluna,
                    "series_id": series_id,
                    "source": meta["source"],
                    "vintage": meta["vintage"],
                    "collected_at": meta["collected_at"],
                    "lag_adjusted": LAG_ADJUSTED,
                    "fonte_versao": fonte_versao,
                }
            )
            diagnostico.append(
                {
                    "quarter": quarter,
                    "column": coluna,
                    "series_id": series_id,
                    "date_obs_max": ultima,
                    "quarter_end": indexado.loc[quarter, "quarter_end"],
                    "fim_civil": pd.Timestamp(pd.Period(quarter, freq="Q").end_time.date()),
                    "unidade": origem.unidade,
                }
            )
    provenance = pd.DataFrame(linhas)
    if provenance.empty:
        msg = "nenhuma célula rastreável preenchida: a tabela wide não tem procedência a gravar"
        raise FonteIndisponivel(f"BLOQUEADO — FONTE INDISPONÍVEL: {msg}")
    provenance = provenance.sort_values(["quarter", "column"], kind="mergesort").reset_index(
        drop=True
    )
    return provenance, pd.DataFrame(diagnostico)


# ─────────────────────────────────────────────────────────────────────────────
# Entradas do build
# ─────────────────────────────────────────────────────────────────────────────


def _ler_canonical(nome: str, *, schema: Any, raiz: Path | None) -> pd.DataFrame:
    """Lê um Parquet de `data/canonical/` e **valida** com o seu schema antes de usar."""
    alvo = caminho_canonical(nome, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode, em ordem, "
            f"`uv run python -m apps.pipeline.canonical.build_raw_series --offline` (F-013) e "
            f"`uv run python -m apps.pipeline.canonical.alinhamento` (F-014)."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return schema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz {schema.Config.name}: {erro}"
        raise SerieInconsistente(msg) from erro


def _ler_catalogo(*, raiz: Path | None) -> pd.DataFrame:
    """Lê `series_catalog.parquet` e exige as colunas que o painel desbalanceado usa.

    Mesma política de F-014 (`COLUNAS_DO_CATALOGO_CONSUMIDAS`): o portão completo é a **escrita**
    em F-013; revalidá-lo na leitura transformaria um acréscimo legítimo de coluna numa falha desta
    feature sem que o dado tivesse mudado.
    """
    alvo = caminho_canonical(NOME_CATALOGO, raiz=raiz)
    if not alvo.is_file():
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe (rode F-013)."
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    faltando = [
        c
        for c in ("series_id", "presente_no_processed", "data_inicio_observada")
        if c not in quadro.columns
    ]
    if faltando:
        msg = f"{alvo.name} sem as colunas que o macro consome: {faltando}"
        raise SerieInconsistente(msg)
    return quadro


def metadado_de_procedencia(raw: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """`{series_id: {source, vintage, collected_at}}` — o que a procedência por célula precisa.

    `vintage` e `collected_at` são o **máximo** da série, que é a definição da materialização
    `revised` (`selecionar_vintage` de F-014 mantém só a última safra). `vintage` nulo continua
    nulo: série não revisável não ganha data inventada.
    """
    saida: dict[str, dict[str, Any]] = {}
    for series_id, grupo in raw.groupby("series_id", sort=True):
        vintage = grupo["vintage"].max()
        coletado = grupo["collected_at"].max()
        saida[str(series_id)] = {
            "source": str(grupo["source"].iloc[0]),
            "vintage": pd.Timestamp(vintage) if pd.notna(vintage) else pd.NaT,
            "collected_at": pd.Timestamp(coletado),
        }
    return saida


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DO_MACRO` — o `fonte_versao` desta tabela.

    Hash de arquivos, não do processo (RF-047/CA-121), reusando
    `caminhos_dos_componentes`/`versao_build` de F-013: um só algoritmo de hash de componentes na
    camada canônica. O conjunto, e não só este arquivo, porque editar o contrato, a régua de F-014,
    o calendário ou o catálogo muda o Parquet sem tocar aqui.
    """
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DO_MACRO))


def fatiar_curva(raw: pd.DataFrame) -> pd.DataFrame:
    """A fatia `source=DERIVADO` da curva que F-014 deixou de fora, para alinhar aqui."""
    return raw.loc[raw["series_id"].isin(SERIES_DA_CURVA)].copy()


def carregar_focus(*, raiz: Path | None = None) -> tuple[pd.DataFrame | None, str]:
    """Lê as 5 séries do Focus de `data/processed/focus/`, ou diz por que não leu.

    Lê a camada **processada** de F-010 e não `raw_series`, de propósito: nesta onda F-013 rodou
    **antes** de F-010, então `data/canonical/raw_series.parquet` não tem o Focus, e reconstruí-lo
    aqui mexeria num artefato que F-017 está lendo em paralelo (`AGENTS.md §13` congela o que é
    compartilhado). `ProcessedSeriesSchema` é o mesmo contrato de `raw_series`, então
    `alinhar_series` e `observacoes_de_fim_de_periodo` aceitam a fatia sem adaptação.

    Ausência não é erro: devolve `(None, motivo)` e as 7 colunas dependentes do Focus saem nulas e
    declaradas (`PLAN §5`, corte nº 4 — a V1 do pacote mínimo não depende do Focus).
    """
    pasta = caminho_camada(Camada.PROCESSED, raiz=raiz) / "focus"
    arquivos = sorted(pasta.glob("*.parquet")) if pasta.is_dir() else []
    if not arquivos:
        return None, (
            f"{pasta} nao existe ou esta vazia: F-010 (Focus) nao materializou nesta rodada. "
            f"As 7 colunas dependentes do Focus saem nulas e declaradas (PLAN §5, corte n. 4)."
        )
    pedacos = [pd.read_parquet(caminho) for caminho in arquivos]
    bruto = pd.concat(pedacos, ignore_index=True)
    fatia = bruto.loc[bruto["series_id"].isin(SERIES_DO_FOCUS)].copy()
    ausentes = sorted(set(SERIES_DO_FOCUS) - set(fatia["series_id"].unique()))
    if ausentes:
        return None, (
            f"{pasta} existe, mas sem as series que esta feature consome: {ausentes}. "
            f"Colunas de Focus nulas e declaradas, em vez de meia coluna sem aviso."
        )
    fatia = fatia.loc[:, list(RawSeriesSchema.to_schema().columns)]
    validada = RawSeriesSchema.validate(fatia, lazy=True)
    return validada, (
        f"consumido de {pasta}: {len(validada)} linhas, {validada['series_id'].nunique()} series "
        f"({validada['date'].min().date()} .. {validada['date'].max().date()}). Regua: ultima "
        f"coleta ate o ultimo dia util de T-1 (a 'coleta do inicio de T' da metodologia §2)."
    )


def focus_do_inicio_do_trimestre(
    h0: pd.Series, h1: pd.Series | None, quarters: Sequence[str]
) -> pd.Series:
    """A expectativa, para o período **de T**, da última coleta até o fim de `T-1`.

    `h0` é o horizonte "período corrente da pesquisa" e `h1` o seguinte (convenção de F-010). Como
    a coleta de referência de `T` cai no fim de `T-1`, o ano-calendário da coleta é o ano de `T`
    **exceto** quando `T` é um 1º trimestre — aí a coleta é de dezembro do ano anterior e o
    horizonte certo é `h1`. Sem essa troca, `focus_pib_ano` de todo 1º trimestre traria a
    expectativa do **ano que acabou**, que é um erro silencioso de 1 ano em 1/4 das linhas.

    `h1` ausente (série de horizonte único, como a inflação de 12 meses) → só desloca.
    """
    saida: dict[str, float] = {}
    for rotulo in quarters:
        periodo = pd.Period(rotulo, freq="Q")
        anterior = str(periodo - 1)
        if anterior not in h0.index:
            continue
        mesmo_ano = (periodo - 1).year == periodo.year
        fonte = h0 if (mesmo_ano or h1 is None) else h1
        if anterior in fonte.index:
            saida[rotulo] = float(fonte[anterior]) if pd.notna(fonte[anterior]) else np.nan
    return pd.Series(saida, dtype="float64").reindex(list(quarters))


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────


def _iso(valor: Any) -> str | None:
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return None
    return pd.Timestamp(valor).date().isoformat()


def sensibilidade_da_tendencia(
    ibcbr_yoy_estendido: pd.Series, quarters: Sequence[str], *, minimo: int = 8
) -> dict[str, Any]:
    """Quanto o hiato do IBC-Br mudaria se a média móvel aceitasse janela parcial.

    O default do módulo é janela **cheia** de 20 trimestres, e isso custa 15 trimestres de
    `ibcbr_gap` (2006Q1..2009Q3) — o limite duro da série, que começa em 2004. Este bloco mede a
    alternativa (`min_periods = minimo`) **sem adotá-la**: quantos trimestres ela recupera e qual o
    maior desvio no trecho em que as duas definições coexistem. É o material da decisão que o
    relatório entrega ao orquestrador em vez de tomar sozinho (CA-007, `AGENTS.md §9`).
    """
    janela = list(quarters)
    estrito = media_movel(ibcbr_yoy_estendido).reindex(janela)
    parcial = (
        ibcbr_yoy_estendido.rolling(window=N_TRIMESTRES_TENDENCIA, min_periods=minimo)
        .mean()
        .reindex(janela)
    )
    gap_estrito = (ibcbr_yoy_estendido.reindex(janela) - estrito).dropna()
    gap_parcial = (ibcbr_yoy_estendido.reindex(janela) - parcial).dropna()
    comum = gap_estrito.index.intersection(gap_parcial.index)
    return {
        "regra_adotada": f"media movel de {N_TRIMESTRES_TENDENCIA} trimestres, janela cheia",
        "trimestres_com_gap_adotado": int(len(gap_estrito)),
        "trimestres_com_gap_se_min_periods_8": int(len(gap_parcial)),
        "trimestres_recuperados": int(len(gap_parcial) - len(gap_estrito)),
        "max_abs_diferenca_no_trecho_comum_pp": (
            round(float((gap_parcial[comum] - gap_estrito[comum]).abs().max()), 6)
            if len(comum)
            else None
        ),
        "nota": (
            "nao adotada: media de janela parcial e outro estimador, e um cujo significado muda "
            "ao longo do tempo — o hiato de 2006 deixaria de ser comparavel ao de 2015"
        ),
    }


def montar_relatorio(
    *,
    macro: pd.DataFrame,
    provenance: pd.DataFrame,
    diagnostico: pd.DataFrame,
    acumulados: Mapping[str, Mapping[str, Acumulado]],
    celulas_conferidas: int,
    motivo_focus: str,
    sensibilidade: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    """`relatorio_macro.json` — **sem relógio**, para que dois builds sejam byte-idênticos.

    O bloco que a revisão numérica independente usa é `nulos_por_coluna` (com `motivo`),
    `canarios` e `anti_look_ahead`.
    """
    n = len(macro)
    nulos: dict[str, Any] = {}
    for coluna in COLUNAS_RASTREAVEIS:
        if coluna == "vertice_extrapolado":
            nulos[coluna] = {
                "nulos": 0,
                "pct": 0.0,
                "unidade": UNIDADES[coluna],
                "formula": ORIGENS[coluna].formula,
                "series_id": ORIGENS[coluna].series_id,
                "motivo": None,
                "true": int(macro[coluna].sum()),
            }
            continue
        vazios = int(macro[coluna].isna().sum())
        origem = ORIGENS[coluna]
        nulos[coluna] = {
            "nulos": vazios,
            "pct": round(100.0 * vazios / n, 2),
            "unidade": origem.unidade,
            "formula": origem.formula,
            "series_id": origem.series_id,
            "motivo": origem.motivo_ausencia
            if origem.series_id is None
            else _motivo_de_nulo_derivado(coluna, macro),
            "primeiro_trimestre_com_valor": _primeiro_com_valor(macro, coluna),
        }

    por_coluna = diagnostico.groupby("column")["date_obs_max"].max()
    com_data = diagnostico.loc[diagnostico["date_obs_max"].notna()]
    atrasadas = com_data.loc[com_data["date_obs_max"] > com_data["quarter_end"]]
    fora_do_trimestre = com_data.loc[com_data["date_obs_max"] > com_data["fim_civil"]]
    ciclos = [ciclo_selic(v) for v in macro["selic_meta_delta"]]

    return {
        "macro_quarterly": {
            "linhas": n,
            "colunas": int(macro.shape[1]),
            "primeiro_trimestre": str(macro["quarter"].iloc[0]),
            "ultimo_trimestre": str(macro["quarter"].iloc[-1]),
            "materializacao": MATERIALIZACAO,
            "lag_adjusted": LAG_ADJUSTED,
            "is_estimated_em": sorted(macro.loc[macro["is_estimated"], "quarter"]),
            "sha256": hashes["sha256_macro"],
            "bytes": hashes["bytes_macro"],
        },
        "macro_quarterly_provenance": {
            "linhas": int(len(provenance)),
            "colunas_cobertas": int(provenance["column"].nunique()),
            "series_distintas": int(provenance["series_id"].nunique()),
            "sha256": hashes["sha256_provenance"],
            "bytes": hashes["bytes_provenance"],
        },
        "unidades": dict(sorted(UNIDADES.items())),
        "nulos_por_coluna": dict(sorted(nulos.items())),
        "acumulacao": {
            series_id: {
                "trimestres_com_valor": sum(1 for a in por_q.values() if a.value is not None),
                "trimestres_incompletos": sorted(
                    a.quarter
                    for a in por_q.values()
                    if a.motivo_nulo == MOTIVO_TRIMESTRE_INCOMPLETO
                ),
            }
            for series_id, por_q in sorted(acumulados.items())
        },
        "anti_look_ahead": {
            "regra": (
                "nenhuma célula de T usa observação com data de referência posterior ao fim "
                "civil de T; `date_obs > quarter_end` só ocorre na grade civil/corrido, cujo "
                "alvo é o último dia civil (ADR-006, D-a)"
            ),
            "celulas_com_date_obs_depois_do_fim_civil_de_T": int(len(fora_do_trimestre)),
            "celulas_com_date_obs_depois_do_quarter_end": int(len(atrasadas)),
            "celulas_com_data_medida": int(len(com_data)),
            "colunas_afetadas": sorted(atrasadas["column"].unique().tolist()),
            "date_obs_max_por_coluna": {
                str(k): _iso(v) for k, v in sorted(por_coluna.items()) if pd.notna(v)
            },
        },
        "ciclo_selic": {
            "regra": f"|delta| <= {LIMIAR_SELIC_PP} pp -> NEUTRO; < -{LIMIAR_SELIC_PP} -> CORTE; "
            f"> +{LIMIAR_SELIC_PP} -> ALTA",
            "distribuicao": {
                estado: int(sum(1 for c in ciclos if c == estado))
                for estado in sorted({c for c in ciclos if c is not None})
            },
            "sem_delta": int(sum(1 for c in ciclos if c is None)),
        },
        "diff_vs_alinhado_trimestral": {
            "celulas_conferidas_sem_tolerancia": celulas_conferidas,
            "divergencias": 0,
        },
        "canarios": _canarios(macro),
        "sensibilidade_ibcbr_gap": dict(sensibilidade),
        "focus": {
            "consumido": bool(macro["focus_ipca_12m"].notna().any()),
            "series_lidas": list(SERIES_DO_FOCUS),
            "entrada_no_catalogo": dict(sorted(CATALOGO_DO_FOCUS.items())),
            "motivo": motivo_focus,
        },
        "versao_build": hashes["versao_build"],
        "modulos_da_versao": list(MODULOS_DO_MACRO),
    }


def _motivo_de_nulo_derivado(coluna: str, macro: pd.DataFrame) -> str | None:
    """O motivo dos nulos de uma coluna que **tem** fonte — ou `None` se não há nulo."""
    vazios = int(macro[coluna].isna().sum())
    if vazios == 0:
        return None
    if coluna in ("ibcbr_yoy_trend", "ibcbr_gap"):
        return (
            f"{MOTIVO_JANELA_CURTA}: a média móvel de {N_TRIMESTRES_TENDENCIA} trimestres exige "
            f"janela cheia e o IBC-Br (SGS 24364) começa em 2004, logo o a/a começa em 2005Q1 — "
            f"o primeiro hiato possível é 2009Q4. Mais 15 trimestres só com IBC-Br anterior a "
            f"2004, que não existe. CA-007 **não é satisfazível** com a série real (ver relatório)"
        )
    if coluna in ACUMULADAS:
        return MOTIVO_TRIMESTRE_INCOMPLETO
    if coluna in ("pib_yoy", "ibcbr_yoy", "pib_qoq_sa"):
        return (
            "PIB (SIDRA, até 2026Q2) e IBC-Br (SGS, até jul/2026) não cobrem 2026Q3: a lacuna "
            "passa de 5 dias úteis e a célula é NULL por CA-061/CA-067, nunca estimativa (CA-060)"
        )
    return MOTIVO_SERIE_SEM_VALOR


def _primeiro_com_valor(macro: pd.DataFrame, coluna: str) -> str | None:
    """O primeiro trimestre em que a coluna tem valor — o jeito curto de ler a cobertura."""
    presentes = macro.loc[macro[coluna].notna(), "quarter"]
    return str(presentes.iloc[0]) if len(presentes) else None


def _canarios(macro: pd.DataFrame) -> dict[str, Any]:
    """Os 3 valores-canário conferidos à mão contra a fonte (AGENTS.md §15.9)."""
    indexado = macro.set_index("quarter")

    def valor(quarter: str, coluna: str) -> float | None:
        if quarter not in indexado.index:
            return None
        bruto = indexado.loc[quarter, coluna]
        return None if pd.isna(bruto) else round(float(bruto), 6)

    return {
        "ipca_12m_2006Q1": {
            "valor": valor("2006Q1", "ipca_12m"),
            "esperado": 5.32,
            "fonte": "SGS 13522, IPCA acumulado 12m de mar/2006",
        },
        "selic_meta_fim_2008Q4": {
            "valor": valor("2008Q4", "selic_meta_fim"),
            "esperado": 13.75,
            "fonte": "SGS 432, meta Selic do Copom vigente em 31/12/2008",
        },
        "pib_yoy_2010Q1": {
            "valor": valor("2010Q1", "pib_yoy"),
            "esperado": 9.207417,
            "fonte": "SIDRA t/1620 v/583 c11255/90707: 152,53 / 139,67 - 1",
        },
        "focus_ipca_12m_2026Q3": {
            "valor": valor("2026Q3", "focus_ipca_12m"),
            "esperado": 4.19,
            "fonte": (
                "FOCUS_I12_IPCA_N, ultima coleta ate 2026-06-30 (o fim de 2026Q2) = 4,1900 — "
                "prova a regua de deslocamento de 1 trimestre"
            ),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────


def construir(
    *,
    raiz: Path | None = None,
    calendario: Calendario | None = None,
    quarters: Sequence[str] | None = None,
) -> ResultadoMacro:
    """Reconstrói `macro_quarterly`, a procedência e o relatório de ponta a ponta.

    Sem rede, sem estado, sem efeito fora de `data/canonical/`. `calendario` e `quarters` existem
    para o teste cravar um calendário de fixture; em produção os dois saem do disco e dos 83
    trimestres do contrato.
    """
    raw = _ler_canonical(NOME_RAW_SERIES, schema=RawSeriesSchema, raiz=raiz)
    alinhado = _ler_canonical(NOME_ALINHADO, schema=AlinhadoTrimestralSchema, raiz=raiz)
    catalogo = _ler_catalogo(raiz=raiz)
    declarado = load_catalog()

    # A guarda de procedência de F-013 na entrada desta camada (CA-055) e o pacote mínimo (CA-076).
    validar_procedencia(raw, declarado)
    exigir_series(fatiar_para_alinhamento(raw)[0], declarado, SERIES_EXIGIDAS)

    cal = calendario if calendario is not None else Calendario.do_parquet(raiz=raiz)
    trimestres = grade_estendida(cal, quarters=quarters)
    janela = [t.quarter for t in trimestres if t.quarter in set(quarters or quarters_da_janela())]
    inicio = inicio_observado_por_serie(catalogo, raw)
    versao = versao_build()

    consumidas = (*series_de_nivel(), *ACUMULADAS.values())
    fatia = raw.loc[raw["series_id"].isin(consumidas)].copy()
    ausentes = sorted(set(consumidas) - set(fatia["series_id"].unique()))
    if ausentes:
        _log.warning("series consumidas ausentes de raw_series: %s", ausentes)

    focus, motivo_focus = carregar_focus(raiz=raiz)
    if focus is not None:
        fatia = pd.concat([fatia, focus], ignore_index=True)
        inicio = {
            **inicio,
            **{
                str(sid): pd.Timestamp(quando)
                for sid, quando in focus.groupby("series_id")["date"].min().items()
            },
        }
    _log.info("focus: %s", motivo_focus)

    observacoes = observacoes_de_fim_de_periodo(
        fatia, calendario=cal, trimestres=trimestres, inicio_por_serie=inicio
    )
    celulas = conferir_apoio_contra_alinhado(observacoes, alinhado)
    _log.info("apoio conferido contra alinhado_trimestral: %d celulas, 0 divergencias", celulas)

    # `alinhar_series` (F-014) sobre a fatia do Focus **dentro da janela**: é o portão pandera
    # (`AlinhadoTrimestralSchema`) sobre o alinhamento do Focus, e a conferência cruzada de que a
    # régua reexpressa em `observacoes_de_fim_de_periodo` dá o mesmo resultado célula a célula.
    if focus is not None:
        celulas += conferir_apoio_contra_alinhado(
            observacoes,
            alinhar_series(
                focus,
                calendario=cal,
                inicio_por_serie=inicio,
                trimestres=[t for t in trimestres if t.quarter in set(janela)],
                fonte_versao=versao,
            ),
        )

    # A curva (F-016) ficou fora de `alinhado_trimestral` por ser `source=DERIVADO`: F-015 chama
    # `alinhar_series` sobre ela, que é para isso que a função é pública (F-014 §docstring).
    curva = fatiar_curva(raw)
    if not curva.empty:
        alinhada = alinhar_series(
            curva,
            calendario=cal,
            inicio_por_serie=inicio,
            trimestres=[t for t in trimestres if t.quarter in set(janela)],
            fonte_versao=versao,
        )
        da_curva = pd.DataFrame(
            {
                "quarter": alinhada["quarter"].astype(str),
                "series_id": alinhada["series_id"].astype(str),
                "date_alvo": pd.to_datetime(alinhada["date_alvo"]).dt.date,
                "date_obs": pd.to_datetime(alinhada["date_obs"]).dt.date,
                "value": alinhada["value"].astype("float64"),
                "lacuna_dias_uteis": alinhada["lacuna_dias_uteis"].astype(int),
                "motivo_nulo": alinhada["motivo_nulo"].astype(object),
            }
        )
        observacoes = pd.concat([observacoes, da_curva], ignore_index=True)
    else:
        _log.warning("nenhuma serie de curva em raw_series: as colunas de curva sairao nulas")

    acumulados: dict[str, dict[str, Acumulado]] = {}
    for series_id in sorted(set(ACUMULADAS.values())):
        bruto = raw.loc[raw["series_id"] == series_id]
        pontos = validar_indice_temporal(selecionar_vintage(bruto))
        acumulados[series_id] = {
            a.quarter: a
            for a in acumular_por_trimestre(
                pontos, series_id=series_id, calendario=cal, trimestres=trimestres
            )
        }

    metadado = metadado_de_procedencia(raw)
    if focus is not None:
        # A procedência aponta para a entrada do **catálogo** (`FOCUS_ANUAIS`,
        # `FOCUS_INFLACAO_12M`), que é onde CA-120 resolve: o `series_id` materializado por
        # horizonte (`FOCUS_A_SELIC_H0`) é, por decisão de F-010, deliberadamente fora do catálogo.
        por_subserie = metadado_de_procedencia(focus)
        for subserie, entrada in CATALOGO_DO_FOCUS.items():
            if subserie in por_subserie:
                metadado.setdefault(entrada, por_subserie[subserie])

    macro, provenance, diagnostico = montar_macro(
        observacoes=observacoes,
        acumulados=acumulados,
        metadado=metadado,
        trimestres=trimestres,
        quarters=janela,
        fonte_versao=versao,
    )

    destino_macro = caminho_canonical(NOME_MACRO, raiz=raiz)
    destino_prov = caminho_canonical(NOME_PROVENANCE, raiz=raiz)
    garantir_diretorio(destino_macro.parent)
    macro.to_parquet(destino_macro, index=False)
    provenance.to_parquet(destino_prov, index=False)
    corpo_macro = destino_macro.read_bytes()
    corpo_prov = destino_prov.read_bytes()
    _log.info(
        "gravado %s (%d linhas, %d colunas, sha256=%s...) e %s (%d linhas)",
        destino_macro.name,
        len(macro),
        macro.shape[1],
        sha256_de(corpo_macro)[:12],
        destino_prov.name,
        len(provenance),
    )

    todos = [t.quarter for t in trimestres]
    ibcbr_yoy_estendido = variacao_por_razao(
        _coluna(_niveis_wide(observacoes, todos), "BCB_SGS_24364", todos), 4
    )
    relatorio = montar_relatorio(
        macro=macro,
        provenance=provenance,
        diagnostico=diagnostico,
        acumulados=acumulados,
        celulas_conferidas=celulas,
        motivo_focus=motivo_focus,
        sensibilidade=sensibilidade_da_tendencia(ibcbr_yoy_estendido, janela),
        hashes={
            "sha256_macro": sha256_de(corpo_macro),
            "bytes_macro": len(corpo_macro),
            "sha256_provenance": sha256_de(corpo_prov),
            "bytes_provenance": len(corpo_prov),
            "versao_build": versao,
        },
    )
    destino_relatorio = caminho_canonical(NOME_RELATORIO, raiz=raiz)
    destino_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ResultadoMacro(
        macro=macro,
        provenance=provenance,
        diagnostico=diagnostico,
        relatorio=relatorio,
        trimestres=trimestres,
        caminho_macro=destino_macro,
        caminho_provenance=destino_prov,
        caminho_relatorio=destino_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.macro_quarterly",
        description=(
            "Materializa data/canonical/macro_quarterly.parquet + "
            "macro_quarterly_provenance.parquet + relatorio_macro.json a partir de "
            "alinhado_trimestral (F-014) e raw_series (F-013). Nunca toca a rede."
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Aceito por simetria com os extratores e sem efeito: esta camada só lê o disco.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = build feito; `1` = falha explícita e nada gravado."""
    _parser().parse_args(argv)
    configurar_logging()
    try:
        resultado = construir()
    except ErroDeExtracao as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 1

    bloco = resultado.relatorio["macro_quarterly"]
    prov = resultado.relatorio["macro_quarterly_provenance"]
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{NOME_MACRO}: {bloco['linhas']} linhas | {bloco['colunas']} colunas | "
        f"{bloco['primeiro_trimestre']}..{bloco['ultimo_trimestre']} | "
        f"{bloco['materializacao']} | sha256 {bloco['sha256']}"
    )
    print(
        f"{NOME_PROVENANCE}: {prov['linhas']} linhas | {prov['colunas_cobertas']} colunas | "
        f"{prov['series_distintas']} series | sha256 {prov['sha256']}"
    )
    diff = resultado.relatorio["diff_vs_alinhado_trimestral"]
    print(
        f"diff vs alinhado_trimestral: {diff['celulas_conferidas_sem_tolerancia']} celulas, "
        f"{diff['divergencias']} divergencias"
    )
    for nome, canario in sorted(resultado.relatorio["canarios"].items()):
        print(f"canario {nome}: {canario['valor']} (esperado {canario['esperado']})")
    vazias = [
        nome
        for nome, bloco_nulo in resultado.relatorio["nulos_por_coluna"].items()
        if bloco_nulo["nulos"] == bloco["linhas"]
    ]
    print(f"colunas 100% nulas ({len(vazias)}): {', '.join(vazias)}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
