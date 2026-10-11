"""Contratos de dados do projeto — **fonte de verdade**.

`pandera` para schema de DataFrame, `pydantic` para catálogo e config de extrator.
Espelho legível: `docs/contracts/CONTRACTS.md` (nunca o contrário: primeiro o schema, depois o doc).

| Módulo | O que define | SPEC |
|---|---|---|
| `raw_series` | `raw_series` / `processed_series` (granularidade nativa) | RF-020 |
| `alinhado_trimestral` | grade trimestral *long* (último d.u., ffill <= 5 d.u.) | RF-023 |
| `calendario` | `calendario_dias_uteis` (grade de dias úteis da ANBIMA) | RF-018 |
| `series_catalog` | `SeriesCatalogEntry`, `ExtractorConfig`, `SeriesCatalogSchema`,
`SeriesCatalogMaterializedSchema` | RF-019, RF-047 |
| `series_catalog_data` | o catálogo **como dado** (uma entrada por série) | RF-019 |
| `macro_quarterly` | `macro_quarterly` (83 tri.) + procedência `revised`/`asof` | RF-021, RF-025 |
| `asset_returns_quarterly` | retornos por ativo + métricas por regime | RF-022, RF-032 |
| `regimes` | `regimes` e `regime_neighbors` (V1/V2/V3) | RF-027..031 |

Todo DataFrame que entra ou sai de `data/canonical/` passa por um destes schemas (`AGENTS.md §19`).
"""

from __future__ import annotations

from packages.shared.schemas.alinhado_trimestral import (
    COLUNAS_ALINHADO,
    GRADE_BANCARIA,
    GRADE_CIVIL,
    GRADE_CORRIDO,
    GRADES_VALIDAS,
    LIMITE_FFILL_DIAS_UTEIS,
    MOTIVO_LACUNA_ACIMA_DO_LIMITE,
    MOTIVO_SEM_OBSERVACAO,
    MOTIVOS_VALIDOS,
    PK_ALINHADO,
    AlinhadoTrimestralSchema,
    quarters_da_janela,
)
from packages.shared.schemas.asset_returns_quarterly import (
    ASSET_IDS_VALIDOS,
    ATIVOS_ACOES_B3,
    ATIVOS_FII,
    ATIVOS_INTERNACIONAIS,
    ATIVOS_RENDA_FIXA,
    N_MINIMO_ATIVOS,
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
    MacroQuarterlyAsofProvenanceSchema,
    MacroQuarterlyProvenanceSchema,
    MacroQuarterlySchema,
)
from packages.shared.schemas.raw_series import (
    ProcessedSeriesSchema,
    RawSeriesSchema,
)
from packages.shared.schemas.regimes import (
    COLUNAS_V1_DE_REGIMES,
    FEATURES_V3,
    K_VIZINHOS_PADRAO,
    K_VIZINHOS_SENSIBILIDADE,
    LIMIAR_ACELERACAO_PP,
    LIMIAR_CRESCIMENTO_PP,
    N_ALERTA,
    N_SUPRESSAO,
    N_TRIMESTRES_EXCLUIDOS_VIZINHANCA,
    SENSIBILIDADE_ACELERACAO_PP,
    VERSAO_ESPECIFICACAO_V1,
    CicloSelic,
    MetricaDistancia,
    MotivoIndeterminado,
    RegimeNeighborsSchema,
    RegimeNeighborsV3Schema,
    RegimesSchema,
    RegimesV1Schema,
    RegimeV1,
    StatusRegimeV1,
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
    "ATIVOS_ACOES_B3",
    "ATIVOS_FII",
    "ATIVOS_INTERNACIONAIS",
    "ATIVOS_RENDA_FIXA",
    "COLUNAS_ALINHADO",
    "COLUNAS_RASTREAVEIS",
    "COLUNAS_V1_DE_REGIMES",
    "FEATURES_V3",
    "FONTES_BLOQUEADAS_NO_PACOTE_MINIMO",
    "FONTE_CALENDARIO",
    "GRADES_VALIDAS",
    "GRADE_BANCARIA",
    "GRADE_CIVIL",
    "GRADE_CORRIDO",
    "K_VIZINHOS_PADRAO",
    "K_VIZINHOS_SENSIBILIDADE",
    "LIMIAR_ACELERACAO_PP",
    "LIMIAR_CRESCIMENTO_PP",
    "LIMITE_FFILL_DIAS_UTEIS",
    "LIMIAR_COBERTURA_2006",
    "MOTIVOS_VALIDOS",
    "MOTIVO_LACUNA_ACIMA_DO_LIMITE",
    "MOTIVO_SEM_OBSERVACAO",
    "N_ALERTA",
    "N_MINIMO_ATIVOS",
    "N_SUPRESSAO",
    "N_TRIMESTRES_EXCLUIDOS_VIZINHANCA",
    "N_TRIMESTRES_JANELA",
    "PK_ALINHADO",
    "SENSIBILIDADE_ACELERACAO_PP",
    "VERSAO_ESPECIFICACAO_V1",
    "AlinhadoTrimestralSchema",
    "AssetReturnsQuarterlySchema",
    "CalendarioDiasUteisSchema",
    "CicloSelic",
    "Confianca",
    "ExtractorConfig",
    "Fonte",
    "Freq",
    "MacroQuarterlyAsofProvenanceSchema",
    "MacroQuarterlyProvenanceSchema",
    "MacroQuarterlySchema",
    "MetricaDistancia",
    "MotivoIndeterminado",
    "ProcessedSeriesSchema",
    "RawSeriesSchema",
    "RegimeAssetMetricsSchema",
    "RegimeNeighborsSchema",
    "RegimeNeighborsV3Schema",
    "RegimeV1",
    "RegimesSchema",
    "RegimesV1Schema",
    "SeriesCatalogEntry",
    "SeriesCatalogMaterializedSchema",
    "SeriesCatalogSchema",
    "StatusRegimeV1",
    "StatusSerie",
    "Transformacao",
    "Unidade",
    "load_catalog",
    "quarters_da_janela",
    "resumo_catalogo",
]
