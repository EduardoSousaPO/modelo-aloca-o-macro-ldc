"""Schema de `asset_returns_quarterly` — retorno trimestral por ativo.

Fonte de verdade do contrato (SPEC RF-022, RF-023, RF-024; CA-062..064, CA-065..071).
Base de desenho: `docs/research/metodologia-regimes-macro.md §6.3`.

**Classe C.** Excesso sobre CDI e retorno real são **sempre** razão `(1+r)/(1+b)-1`; encadeamento
geométrico. Painel **desbalanceado por desenho**: ativo que começa depois de 2006 (IFIX 2011, ICON
2007, IMOB 2008, FII segmentado 2019) **não tem linha** antes do seu início — nunca `0`,
nunca valor herdado.
"""

from __future__ import annotations

import pandera as pa
from pandera.typing import Series

QUARTER_REGEX = r"^(200[6-9]|20[1-2][0-9])Q[1-4]$"

ATIVOS_RENDA_FIXA: tuple[str, ...] = (
    "CDI",
    "IMAB",
    "IMAB5",
    "IMAB5P",
    "IRFM",
    "IRFM1",
    "IRFM1P",
    "IMAGERAL",
    "IMAS",
)

ATIVOS_ACOES_B3: tuple[str, ...] = (
    "IBOV",
    "IDIV",
    "SMLL",
    "INDX",
    "ICON",
    "IMAT",
    "IEEX",
    "IMOB",
    "IFNC",
    "UTIL",
)

ATIVOS_FII: tuple[str, ...] = (
    "IFIX",
    "FII_TIJOLO",
    "FII_PAPEL",
    "FII_LOGISTICA",
    "FII_SHOPPINGS",
    "FII_LAJES",
)

ATIVOS_INTERNACIONAIS: tuple[str, ...] = (
    "SP500_BRL",
    "SP500_USD",
    "SP500_HEDGE",
    "ACWI_BRL",
    "UST10_BRL",
    "GOLD_BRL",
    "USDBRL",
)

ASSET_IDS_VALIDOS: tuple[str, ...] = (
    ATIVOS_RENDA_FIXA + ATIVOS_ACOES_B3 + ATIVOS_FII + ATIVOS_INTERNACIONAIS
)

N_MINIMO_ATIVOS = 18


class AssetReturnsQuarterlySchema(pa.DataFrameModel):
    """Retornos trimestrais por ativo. PK: (quarter, asset_id)."""

    quarter: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    asset_id: Series[str] = pa.Field(nullable=False, isin=ASSET_IDS_VALIDOS)

    price_ini: Series[float] = pa.Field(nullable=True, gt=0)
    price_fim: Series[float] = pa.Field(nullable=True, gt=0)

    ret_tri: Series[float] = pa.Field(nullable=True, ge=-1.0, le=5.0)
    ret_excesso_cdi: Series[float] = pa.Field(
        nullable=True, description="(1+ret)/(1+cdi)-1 — razão, nunca subtração (CA-069)."
    )
    ret_real: Series[float] = pa.Field(
        nullable=True, description="(1+ret)/(1+ipca_tri)-1 — IPCA do mesmo trimestre (CA-071)."
    )

    vol_intra_tri: Series[float] = pa.Field(nullable=True, ge=0)
    dd_intra_tri: Series[float] = pa.Field(nullable=True, le=0)

    is_total_return: Series[bool] = pa.Field(
        nullable=True,
        description="None = a confirmar (G-01, setoriais B3). Price e total return nunca "
        "são comparados sem esta flag (CA-064).",
    )
    n_dias_uteis: Series[float] = pa.Field(nullable=True, ge=0, le=70)
    ffill_dias_uteis: Series[int] = pa.Field(
        nullable=False, ge=0, le=5, description="Forward-fill usado; > 5 d.u. vira NULL (CA-067)."
    )
    data_inicio_serie: Series[pa.DateTime] = pa.Field(
        nullable=False, description="Janela própria do ativo, no rodapé das figuras (CA-063)."
    )
    source: Series[str] = pa.Field(nullable=False)
    series_id: Series[str] = pa.Field(nullable=False)
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "asset_returns_quarterly"
        strict = True
        coerce = True
        unique = ["quarter", "asset_id"]

    @pa.dataframe_check(name="minimo_de_ativos")
    def _minimo_de_ativos(cls, df: object) -> bool:  # noqa: N805
        """O entregável exige >= 18 ativos distintos (CA-062)."""
        return int(df["asset_id"].nunique()) >= N_MINIMO_ATIVOS  # type: ignore[index]

    @pa.dataframe_check(name="sem_trimestre_antes_do_inicio_da_serie")
    def _sem_backfill_sintetico(cls, df: object) -> bool:  # noqa: N805
        """Nenhuma linha anterior ao início real da série do ativo (CA-063 / Anti-SPEC §10.1)."""
        ini_ano = df["data_inicio_serie"].dt.year  # type: ignore[index]
        q_ano = df["quarter"].str.slice(0, 4).astype(int)  # type: ignore[index]
        return bool((q_ano >= ini_ano).all())


class RegimeAssetMetricsSchema(pa.DataFrameModel):
    """Métricas por (regime, ativo) — insumo direto do heatmap (RF-032, RF-033, RF-040)."""

    lente: Series[str] = pa.Field(nullable=False, isin=("V1", "V2", "V3"))
    regime: Series[str] = pa.Field(nullable=False)
    asset_id: Series[str] = pa.Field(nullable=False, isin=ASSET_IDS_VALIDOS)

    n_obs: Series[int] = pa.Field(nullable=False, ge=0)
    ret_medio: Series[float] = pa.Field(nullable=True)
    ret_mediana: Series[float] = pa.Field(nullable=True)
    ret_desvio: Series[float] = pa.Field(nullable=True, ge=0)
    erro_padrao_media: Series[float] = pa.Field(nullable=True, ge=0)
    hit_ratio: Series[float] = pa.Field(nullable=True, ge=0, le=1)
    excesso_cdi: Series[float] = pa.Field(nullable=True)
    hit_ratio_cdi: Series[float] = pa.Field(nullable=True, ge=0, le=1)
    ret_real: Series[float] = pa.Field(nullable=True)
    sharpe_tri: Series[float] = pa.Field(nullable=True)
    pior_tri: Series[float] = pa.Field(nullable=True)
    pior_tri_quarter: Series[str] = pa.Field(nullable=True)
    melhor_tri: Series[float] = pa.Field(nullable=True)
    melhor_tri_quarter: Series[str] = pa.Field(nullable=True)
    beta_ibov: Series[float] = pa.Field(nullable=True)

    alerta_n_baixo: Series[bool] = pa.Field(
        nullable=False, description="True quando n_obs < 8 (CA-108)."
    )
    conclusao_suprimida: Series[bool] = pa.Field(
        nullable=False, description="True quando n_obs < 5 (CA-109)."
    )
    data_inicio_serie: Series[pa.DateTime] = pa.Field(nullable=False)
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "regime_asset_metrics"
        strict = True
        coerce = True
        unique = ["lente", "regime", "asset_id"]
