"""Schema de `macro_quarterly` — 83 trimestres de variáveis macro (1T2006 → 3T2026).

Fonte de verdade do contrato (SPEC RF-021, RF-023, RF-025; CA-059..061, CA-065..068, CA-072..074).
Base de desenho: `docs/research/metodologia-regimes-macro.md §6.2`.

**Classe C.** Qualquer alteração aqui (coluna, unidade, regra de alinhamento) exige Feature Contract
classe C, diff numérico vs. a versão anterior e reconstrução completa de `data/canonical/`.

Duas materializações:
- `macro_quarterly_asof`    → `lag_adjusted = True`  (respeita a defasagem; para decisão)
- `macro_quarterly_revised` → `lag_adjusted = False` (série revisada de hoje; descritiva)
"""

from __future__ import annotations

import pandera as pa
from pandera.typing import Series

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
