"""Contratos de dados do projeto — **fonte de verdade**.

`pandera` para schema de DataFrame, `pydantic` para catálogo e config de extrator.
Espelho legível: `docs/contracts/CONTRACTS.md` (nunca o contrário: primeiro o schema, depois o doc).

| Módulo | O que define | SPEC |
|---|---|---|
| `raw_series` | `raw_series` / `processed_series` (granularidade nativa) | RF-020 |
| `calendario` | `calendario_dias_uteis` (grade de dias úteis da ANBIMA) | RF-018 |
| `series_catalog` | `SeriesCatalogEntry`, `ExtractorConfig`, `SeriesCatalogSchema`,
`SeriesCatalogMaterializedSchema` | RF-019, RF-047 |
| `series_catalog_data` | o catálogo **como dado** (uma entrada por série) | RF-019 |
| `macro_quarterly` | `macro_quarterly` (83 trimestres) + procedência | RF-021, RF-047 |
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
from packages.shared.schemas.calendario import (
    FONTE_CALENDARIO,
    CalendarioDiasUteisSchema,
)
from packages.shared.schemas.macro_quarterly import (
    COLUNAS_RASTREAVEIS,
    N_TRIMESTRES_JANELA,
    MacroQuarterlyProvenanceSchema,
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
    FONTES_BLOQUEADAS_NO_PACOTE_MINIMO,
    LIMIAR_COBERTURA_2006,
    Confianca,
    ExtractorConfig,
    Fonte,
    Freq,
    SeriesCatalogEntry,
    SeriesCatalogMaterializedSchema,
    SeriesCatalogSchema,
    StatusSerie,
    Transformacao,
    Unidade,
    load_catalog,
    resumo_catalogo,
)

__all__ = [
    "ASSET_IDS_VALIDOS",
    "COLUNAS_RASTREAVEIS",
    "FEATURES_V3",
    "FONTES_BLOQUEADAS_NO_PACOTE_MINIMO",
    "FONTE_CALENDARIO",
    "K_VIZINHOS_PADRAO",
    "LIMIAR_COBERTURA_2006",
    "N_TRIMESTRES_JANELA",
    "AssetReturnsQuarterlySchema",
    "CalendarioDiasUteisSchema",
    "CicloSelic",
    "Confianca",
    "ExtractorConfig",
    "Fonte",
    "Freq",
    "MacroQuarterlyProvenanceSchema",
    "MacroQuarterlySchema",
    "MetricaDistancia",
    "ProcessedSeriesSchema",
    "RawSeriesSchema",
    "RegimeAssetMetricsSchema",
    "RegimeNeighborsSchema",
    "RegimeV1",
    "RegimesSchema",
    "SeriesCatalogEntry",
    "SeriesCatalogMaterializedSchema",
    "SeriesCatalogSchema",
    "StatusSerie",
    "Transformacao",
    "Unidade",
    "load_catalog",
    "resumo_catalogo",
]
