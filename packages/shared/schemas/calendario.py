"""Schema de `calendario_dias_uteis` — a grade de dias úteis da ANBIMA (RF-018).

Fonte de verdade do contrato (SPEC RF-018, CA-051/CA-052). Espelho legível em
`docs/contracts/CONTRACTS.md §7`. Produzido por `apps/pipeline/extract/calendario_anbima.py`
(F-008) e consumido por F-014 (alinhamento) e F-017 (retornos trimestrais).

Esta tabela **não** é `processed_series`: não é uma série de valores, é uma grade de datas com
dois atributos. Por isso não tem `value`/`unit`/`freq`/`vintage`, e a procedência fica no
manifesto de `data/raw/anbima-feriados/*.meta.json` (um por página de ano, com `sha256`, URL e
hora da coleta) em vez de em colunas — o que também deixa o parquet **byte-idêntico** entre
execuções, que é o que RF-048 pede.

Armadilha do pandera medida em 2026-10-10 e travada aqui: `isin` de **um** valor tem de ser
`list`, não tupla. `isin=("ANBIMA_WEB",)` reprova toda linha nesta versão, porque a tupla de um
elemento é desempacotada e o `set` vira o conjunto de *letras* da string. Tupla com 2+ itens
funciona — é por isso que `FONTES_VALIDAS` em `raw_series.py` passa.
"""

from __future__ import annotations

import pandas as pd
import pandera as pa
from pandera.typing import Series

from packages.shared.schemas.series_catalog import Fonte

FONTE_CALENDARIO: list[str] = [Fonte.ANBIMA_WEB.value]
"""Única fonte aceita na coluna `fonte` — **lista** de propósito (ver docstring do módulo)."""

DIAS_DE_FIM_DE_SEMANA = 5
"""`weekday() >= 5` é sábado ou domingo: nunca dia útil no calendário bancário/B3."""


class CalendarioDiasUteisSchema(pa.DataFrameModel):
    """Contrato de `data/processed/calendario/dias_uteis_anbima.parquet`. PK: `data`."""

    data: Series[pa.DateTime] = pa.Field(nullable=False, unique=True)
    dia_util: Series[bool] = pa.Field(nullable=False)
    feriado: Series[pd.StringDtype] = pa.Field(nullable=True)
    fonte: Series[str] = pa.Field(nullable=False, isin=FONTE_CALENDARIO)

    class Config:
        """Configuração do schema."""

        name = "calendario_dias_uteis"
        strict = True
        coerce = True
        unique = ["data"]
        unique_column_names = True
        add_missing_columns = False

    @pa.dataframe_check(name="grade_civil_sem_lacuna")
    def _sem_lacuna(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """A grade é civil e contínua: um dia por data, sem buraco entre min e max."""
        if df.empty:
            return False
        esperado = (df["data"].max() - df["data"].min()).days + 1
        return len(df) == esperado and bool(df["data"].is_monotonic_increasing)

    @pa.dataframe_check(name="feriado_nunca_e_dia_util")
    def _feriado_nao_e_dia_util(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """Data com nome de feriado não pode estar marcada como dia útil."""
        return not bool((df["feriado"].notna() & df["dia_util"]).any())

    @pa.dataframe_check(name="fim_de_semana_nunca_e_dia_util")
    def _fim_de_semana_nao_e_dia_util(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """Sábado e domingo nunca são dia útil (o calendário é bancário/B3)."""
        return not bool((df["data"].dt.weekday.ge(DIAS_DE_FIM_DE_SEMANA) & df["dia_util"]).any())
