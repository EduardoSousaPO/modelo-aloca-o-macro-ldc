"""Contratos de dados do projeto — **fonte de verdade**.

`pandera` para schema de DataFrame, `pydantic` para catálogo e config de extrator.
Espelho legível: `docs/contracts/CONTRACTS.md` (nunca o contrário: primeiro o schema, depois o doc).

| Módulo | O que define | SPEC |
|---|---|---|
| `raw_series` | `raw_series` / `processed_series` (granularidade nativa) | RF-020 |
| `series_catalog` | `SeriesCatalogEntry`, `ExtractorConfig`, `SeriesCatalogSchema` | RF-019 |
| `series_catalog_data` | o catálogo **como dado** (uma entrada por série) | RF-019 |
| `macro_quarterly` | `macro_quarterly` (83 trimestres) | RF-021 |
| `asset_returns_quarterly` | retornos por ativo + métricas por regime | RF-022, RF-032 |
| `regimes` | `regimes` e `regime_neighbors` (V1/V2/V3) | RF-027..031 |

Todo DataFrame que entra ou sai de `data/canonical/` passa por um destes schemas (`AGENTS.md §19`).
"""

from __future__ import annotations

from packages.shared.schemas.asset_returns_quarterly import (
    ASSET_IDS_VALIDOS,
    AssetReturnsQuarterlySchema,
    RegimeAssetMetricsSchema,
)
from packages.shared.schemas.macro_quarterly import (
    N_TRIMESTRES_JANELA,
    MacroQuarterlySchema,
)
from packages.shared.schemas.raw_series import (
    ProcessedSeriesSchema,
    RawSeriesSchema,
)
from packages.shared.schemas.regimes import (
    FEATURES_V3,
    K_VIZINHOS_PADRAO,
    CicloSelic,
    MetricaDistancia,
    RegimeNeighborsSchema,
    RegimesSchema,
    RegimeV1,
)
from packages.shared.schemas.series_catalog import (
    Confianca,
    ExtractorConfig,
    Fonte,
    Freq,
    SeriesCatalogEntry,
    SeriesCatalogSchema,
    StatusSerie,
    Transformacao,
    Unidade,
    load_catalog,
    resumo_catalogo,
)

__all__ = [
    "ASSET_IDS_VALIDOS",
    "FEATURES_V3",
    "K_VIZINHOS_PADRAO",
    "N_TRIMESTRES_JANELA",
    "AssetReturnsQuarterlySchema",
    "CicloSelic",
    "Confianca",
    "ExtractorConfig",
    "Fonte",
    "Freq",
    "MacroQuarterlySchema",
    "MetricaDistancia",
    "ProcessedSeriesSchema",
    "RawSeriesSchema",
    "RegimeAssetMetricsSchema",
    "RegimeNeighborsSchema",
    "RegimeV1",
    "RegimesSchema",
    "SeriesCatalogEntry",
    "SeriesCatalogSchema",
    "StatusSerie",
    "Transformacao",
    "Unidade",
    "load_catalog",
    "resumo_catalogo",
]
