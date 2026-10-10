"""Schema de `macro_quarterly` — 83 trimestres de variáveis macro (1T2006 → 3T2026).

Fonte de verdade do contrato (SPEC RF-021, RF-023, RF-025; CA-059..061, CA-065..068, CA-072..074).
Base de desenho: `docs/research/metodologia-regimes-macro.md §6.2`.

**Classe C.** Qualquer alteração aqui (coluna, unidade, regra de alinhamento) exige Feature Contract
classe C, diff numérico vs. a versão anterior e reconstrução completa de `data/canonical/`.

Duas materializações:
- `macro_quarterly_asof`    → `lag_adjusted = True`  (respeita a defasagem; para decisão)
- `macro_quarterly_revised` → `lag_adjusted = False` (série revisada de hoje; descritiva)

**Procedência (RF-047 / CA-120).** `macro_quarterly` é **wide** — uma coluna por variável, cada uma
vinda de uma série diferente —, então `source`/`series_id`/`vintage`/`collected_at` não cabem na
linha: a linha é um trimestre, não um valor. A resposta a "de onde veio este número?" fica na tabela
companheira `MacroQuarterlyProvenanceSchema` (long, PK `(quarter, column)`), materializada em
`data/canonical/macro_quarterly_provenance.parquet` junto com a tabela wide.
"""

from __future__ import annotations

import pandera as pa
from pandera.typing import Series

from packages.shared.schemas.raw_series import FONTES_VALIDAS

QUARTER_REGEX = r"^(200[6-9]|20[1-2][0-9])Q[1-4]$"
N_TRIMESTRES_JANELA = 83
PRIMEIRO_TRIMESTRE = "2006Q1"
ULTIMO_TRIMESTRE = "2026Q3"


class MacroQuarterlySchema(pa.DataFrameModel):
    """Grade trimestral de variáveis macro. PK: `quarter`. Fim de período = último dia útil."""

    quarter: Series[str] = pa.Field(nullable=False, unique=True, str_matches=QUARTER_REGEX)
    quarter_end: Series[pa.DateTime] = pa.Field(nullable=False)

    # --- crescimento (RF-003, RF-004) -------------------------------------------------------
    pib_yoy: Series[float] = pa.Field(nullable=True)
    pib_qoq_sa: Series[float] = pa.Field(nullable=True)
    ibcbr_yoy: Series[float] = pa.Field(nullable=True)
    ibcbr_yoy_trend: Series[float] = pa.Field(nullable=True)
    ibcbr_gap: Series[float] = pa.Field(nullable=True)

    # --- inflação (RF-001, RF-002) ----------------------------------------------------------
    ipca_12m: Series[float] = pa.Field(nullable=True)
    ipca_12m_delta: Series[float] = pa.Field(nullable=True)
    ipca_tri: Series[float] = pa.Field(nullable=True)
    ipca_meta: Series[float] = pa.Field(
        nullable=True, description="Metas do CMN — gap G-02 (a confirmar); nulo se ausente."
    )
    ipca_desvio_meta: Series[float] = pa.Field(nullable=True)

    # --- juros (RF-005, RF-006) -------------------------------------------------------------
    selic_meta_fim: Series[float] = pa.Field(nullable=True, ge=0, le=60)
    selic_meta_delta: Series[float] = pa.Field(nullable=True)
    selic_over_tri: Series[float] = pa.Field(nullable=True)
    cdi_tri: Series[float] = pa.Field(nullable=True)
    juro_real_exante: Series[float] = pa.Field(nullable=True)

    # --- curva (RF-009) ---------------------------------------------------------------------
    curva_real_1a: Series[float] = pa.Field(nullable=True)
    curva_real_5a: Series[float] = pa.Field(nullable=True)
    curva_nominal_1a: Series[float] = pa.Field(nullable=True)
    curva_nominal_5a: Series[float] = pa.Field(nullable=True)
    inclinacao_real_5a_1a: Series[float] = pa.Field(nullable=True)
    inclinacao_nominal_5a_1a: Series[float] = pa.Field(nullable=True)
    breakeven_5a: Series[float] = pa.Field(nullable=True)
    vertice_extrapolado: Series[bool] = pa.Field(
        nullable=False, description="True = vértice do trimestre foi extrapolado (CA-023/024)."
    )

    # --- câmbio e externo (RF-015, RF-017) --------------------------------------------------
    usdbrl_fim: Series[float] = pa.Field(nullable=True, gt=0)
    usdbrl_var_tri: Series[float] = pa.Field(nullable=True)
    usdbrl_var_12m: Series[float] = pa.Field(nullable=True)
    termos_troca_yoy: Series[float] = pa.Field(nullable=True)
    embi_br_fim: Series[float] = pa.Field(
        nullable=True, description="EMBI+ morre em 30/07/2024 (L8); nulo depois, sem emenda."
    )
    embi_delta_tri: Series[float] = pa.Field(nullable=True)
    ust10_fim: Series[float] = pa.Field(nullable=True)
    vix_fim: Series[float] = pa.Field(nullable=True)

    # --- expectativas Focus (RF-007) --------------------------------------------------------
    focus_ipca_12m: Series[float] = pa.Field(nullable=True)
    focus_pib_ano: Series[float] = pa.Field(nullable=True)
    focus_selic_fim: Series[float] = pa.Field(nullable=True)
    surpresa_ipca: Series[float] = pa.Field(nullable=True)
    surpresa_pib: Series[float] = pa.Field(nullable=True)
    surpresa_selic: Series[float] = pa.Field(nullable=True)

    # --- auditoria (RF-025, RF-047) ---------------------------------------------------------
    is_estimated: Series[bool] = pa.Field(
        nullable=False, description="True = trimestre corrente incompleto (CA-060)."
    )
    lag_adjusted: Series[bool] = pa.Field(
        nullable=False, description="True = materialização `asof` (CA-072)."
    )
    fonte_versao: Series[str] = pa.Field(
        nullable=False, description="Hash do código que gerou a linha (RF-047)."
    )

    class Config:
        """Configuração do schema."""

        name = "macro_quarterly"
        strict = True
        coerce = True
        unique = ["quarter"]

    @pa.dataframe_check(name="janela_de_83_trimestres")
    def _janela_completa(cls, df: object) -> bool:  # noqa: N805
        """A grade tem exatamente 83 trimestres, de 2006Q1 a 2026Q3 (CA-059)."""
        quarters = sorted(df["quarter"].unique())  # type: ignore[index]
        return (
            len(quarters) == N_TRIMESTRES_JANELA
            and quarters[0] == PRIMEIRO_TRIMESTRE
            and quarters[-1] == ULTIMO_TRIMESTRE
        )

    @pa.dataframe_check(name="lag_adjusted_homogeneo")
    def _lag_homogeneo(cls, df: object) -> bool:  # noqa: N805
        """Uma materialização não mistura `asof` e `revised` na mesma tabela."""
        return int(df["lag_adjusted"].nunique()) == 1  # type: ignore[index]


# Colunas que são chave ou auditoria da própria linha — não vêm de uma série do catálogo e por isso
# não têm (nem precisam de) linha de procedência.
COLUNAS_SEM_PROCEDENCIA: tuple[str, ...] = (
    "quarter",
    "quarter_end",
    "is_estimated",
    "lag_adjusted",
    "fonte_versao",
)

# Derivado do próprio schema: coluna nova em `MacroQuarterlySchema` entra aqui automaticamente, e
# `macro_quarterly_provenance` passa a aceitá-la sem edição manual (nem esquecimento).
COLUNAS_RASTREAVEIS: tuple[str, ...] = tuple(
    nome for nome in MacroQuarterlySchema.to_schema().columns if nome not in COLUNAS_SEM_PROCEDENCIA
)


class MacroQuarterlyProvenanceSchema(pa.DataFrameModel):
    """Procedência por célula de `macro_quarterly` — a resposta de CA-120 para a tabela wide.

    Uma linha por `(quarter, column)` com valor não nulo na tabela wide. É o que torna
    "de onde veio este número?" respondível **no dado**, e não só no código: `series_id` resolve em
    `series_catalog` (que carrega `fonte_url`), `vintage` diz em que data o valor era aquele e
    `collected_at` diz quando o pipeline o baixou.

    **Classe C** (`AGENTS.md §2`): é parte do contrato do canônico.
    """

    quarter: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    column: Series[str] = pa.Field(
        nullable=False,
        isin=COLUNAS_RASTREAVEIS,
        description="Coluna de `macro_quarterly` à qual esta procedência se refere.",
    )
    series_id: Series[str] = pa.Field(
        nullable=False,
        str_matches=r"^[A-Z0-9_\.\^=\-]+$",
        description="Série de origem; existe em `series_catalog` (CA-120).",
    )
    source: Series[str] = pa.Field(nullable=False, isin=FONTES_VALIDAS)
    vintage: Series[pa.DateTime] = pa.Field(
        nullable=True,
        description="Vintage usado; nulo = série não revisável (igual a `raw_series`).",
    )
    collected_at: Series[pa.DateTime] = pa.Field(
        nullable=False, description="Quando o pipeline baixou o dado que gerou a célula."
    )
    lag_adjusted: Series[bool] = pa.Field(
        nullable=False,
        description="Materialização a que esta procedência pertence (`asof` ou `revised`).",
    )
    fonte_versao: Series[str] = pa.Field(
        nullable=False, description="Mesmo hash de código da linha wide correspondente."
    )

    class Config:
        """Configuração do schema."""

        name = "macro_quarterly_provenance"
        strict = True
        coerce = True
        unique = ["quarter", "column"]

    @pa.dataframe_check(name="vintage_nao_posterior_a_coleta")
    def _vintage_coerente(cls, df: object) -> bool:  # noqa: N805
        """`vintage <= collected_at`: não se conhece um valor antes de baixá-lo."""
        vintage = df["vintage"]  # type: ignore[index]
        return bool((vintage.isna() | (vintage <= df["collected_at"])).all())  # type: ignore[index]

    @pa.dataframe_check(name="lag_adjusted_homogeneo")
    def _lag_homogeneo(cls, df: object) -> bool:  # noqa: N805
        """Uma materialização de procedência não mistura `asof` e `revised`."""
        return int(df["lag_adjusted"].nunique()) == 1  # type: ignore[index]
