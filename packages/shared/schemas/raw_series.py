"""Schema da camada `raw_series` — toda série na granularidade nativa.

Fonte de verdade do contrato (SPEC RF-020, CA-056..058). Espelho legível em
`docs/contracts/CONTRACTS.md`. Base de desenho: `docs/research/metodologia-regimes-macro.md §6.1`.

Regras que este schema faz valer:
- granularidade **nativa** (diário/mensal/trimestral) — trimestral primário é erro irreversível;
- toda linha tem procedência (`source`, `series_id`, `collected_at`);
- `vintage` existe desde o dia 1, senão o look-ahead bias fica invisível;
- `value` pode ser nulo (feriado, mês sem divulgação) mas **nunca** preenchido por interpolação.
"""

from __future__ import annotations

import pandera as pa
from pandera.typing import Series

FONTES_VALIDAS: tuple[str, ...] = (
    "BCB_SGS",
    "BCB_OLINDA",
    "IBGE_SIDRA",
    "ANBIMA_S3",
    "ANBIMA_WEB",
    "TESOURO_CKAN",
    "B3_API",
    "TEVA_GCS",
    "YAHOO",
    "MSCI",
    "FRED",
    "IPEADATA",
    "CVM",
    "DERIVADO",
    "MANUAL",
)

FREQS_VALIDAS: tuple[str, ...] = ("D", "M", "Q", "A")

UNIDADES_VALIDAS: tuple[str, ...] = (
    "%",
    "%/dia",
    "%a.a.",
    "pp",
    "index",
    "BRL",
    "USD",
    "ratio",
    "bps",
    "R$ milhoes",
)


class RawSeriesSchema(pa.DataFrameModel):
    """Tabela longa de séries brutas. PK lógica: (series_id, date, vintage)."""

    series_id: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z0-9_\.\^=\-]+$")
    date: Series[pa.DateTime] = pa.Field(nullable=False)
    value: Series[float] = pa.Field(nullable=True)
    source: Series[str] = pa.Field(nullable=False, isin=FONTES_VALIDAS)
    freq: Series[str] = pa.Field(nullable=False, isin=FREQS_VALIDAS)
    vintage: Series[pa.DateTime] = pa.Field(nullable=True)
    unit: Series[str] = pa.Field(nullable=False, isin=UNIDADES_VALIDAS)
    collected_at: Series[pa.DateTime] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "raw_series"
        strict = True
        coerce = True
        unique = ["series_id", "date", "vintage"]
        unique_column_names = True
        add_missing_columns = False

    @pa.dataframe_check(name="sem_data_futura")
    def _sem_data_futura(cls, df: object) -> bool:  # noqa: N805
        """`date` nunca pode ser maior que `collected_at` (ex.: meta Selic com data futura)."""
        return bool((df["date"] <= df["collected_at"]).all())  # type: ignore[index]


class ProcessedSeriesSchema(RawSeriesSchema):
    """Mesmo contrato de `raw_series`, já tipado e validado por fonte em `data/processed/`.

    Diferença operacional: aqui `value` nulo só é aceito quando a ausência é esperada
    (feriado, mês sem divulgação) e está registrada pelo extrator — nunca por falha de parse.
    """

    class Config:
        """Configuração do schema."""

        name = "processed_series"
        strict = True
        coerce = True
        unique = ["series_id", "date", "vintage"]
