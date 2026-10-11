"""Varredura de `data/processed/`: as convenções que a Onda 1 uniformizou valem em TODA série.

O que cada extrator garante na sua própria série está testado no arquivo dele, sobre fixture. Este
arquivo faz a pergunta que nenhum extrator pode responder sozinho: **as 51 séries de
`processed_series` que estão em disco seguem a mesma convenção?** É a checagem que pegou as duas
séries derivadas em BRL com `vintage` da última data de pregão em vez da data da coleta.

Lê o que os extratores produziram (`data/processed/`), não fixture. `data/` é reconstruível e fica
fora do git (`CLAUDE.md §4`), então **sem Parquet o teste pula** com a instrução de como gerar — é o
único jeito de uma checagem de camada conviver com um `data/` não versionado.

Duas tabelas ficam **fora** da varredura porque não são `processed_series`:
`calendario/dias_uteis_anbima.parquet` (grade de datas, `CalendarioDiasUteisSchema`) e
`tesouro-direto/td_painel.parquet` (painel de 750 `series_id` compostos) — a segunda é conferida à
parte, porque o contrato dela é o mesmo `ProcessedSeriesSchema`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from apps.pipeline.common import caminho_camada
from apps.pipeline.common.io_layers import Camada
from packages.shared.schemas import ProcessedSeriesSchema

COLUNAS = (
    "series_id",
    "date",
    "value",
    "source",
    "freq",
    "vintage",
    "unit",
    "collected_at",
)
"""As 8 colunas de `ProcessedSeriesSchema`, nesta ordem."""

FORA_DA_VARREDURA = ("calendario", "td_painel")
PAINEL_TESOURO = "tesouro-direto/td_painel.parquet"
COMO_GERAR = "rode `python -m apps.pipeline.extract.<fonte> --offline` (ou sem --offline, com rede)"


def _parquets_de_serie() -> list[pd.Series]:
    raiz = caminho_camada(Camada.PROCESSED)
    if not raiz.is_dir():
        return []
    return sorted(
        p
        for p in raiz.glob("*/*.parquet")
        if not any(marca in p.as_posix() for marca in FORA_DA_VARREDURA)
    )


@pytest.fixture(scope="module")
def series_em_disco() -> list:
    alvos = _parquets_de_serie()
    if len(alvos) < 10:
        pytest.skip(f"data/processed/ tem {len(alvos)} Parquet(s) de série — {COMO_GERAR}")
    return alvos


def test_toda_serie_tem_as_8_colunas_e_passa_no_pandera(series_em_disco: list) -> None:
    """`strict=True`: nenhuma coluna ad hoc, nenhuma faltando, em nenhuma fonte."""
    for alvo in series_em_disco:
        quadro = pd.read_parquet(alvo)
        assert tuple(quadro.columns) == COLUNAS, alvo.name
        ProcessedSeriesSchema.validate(quadro, lazy=True)


def test_vintage_e_uma_data_sem_hora_nao_nula_e_constante_na_serie(series_em_disco: list) -> None:
    """D-b: `vintage` = a data (sem hora) do `collected_at` do manifesto do bruto.

    Nulo, com hora, ou variando dentro da série são as três formas de a convenção ter escapado —
    a última foi como `SP500_BRL` e `ACWI_BRL` apareceram com a data do último pregão.
    """
    for alvo in series_em_disco:
        quadro = pd.read_parquet(alvo)
        vintage = quadro["vintage"]
        assert vintage.notna().all(), f"{alvo.name}: vintage nulo"
        assert (vintage == vintage.dt.normalize()).all(), f"{alvo.name}: vintage com hora"
        assert (vintage == vintage.iloc[0]).all(), f"{alvo.name}: vintage não é constante"
        assert (vintage == quadro["collected_at"].dt.normalize()).all(), (
            f"{alvo.name}: vintage não é a data do collected_at"
        )


def test_serie_mensal_e_trimestral_tem_date_em_fim_de_periodo(series_em_disco: list) -> None:
    """D-a: `date` de série M/Q é o último dia **civil** do período (`CLAUDE.md §3`)."""
    vistas = {"M": 0, "Q": 0}
    for alvo in series_em_disco:
        quadro = pd.read_parquet(alvo)
        freqs = set(quadro["freq"])
        assert len(freqs) == 1, f"{alvo.name}: mais de uma freq na mesma série ({freqs})"
        freq = freqs.pop()
        if freq not in ("M", "Q"):
            continue
        vistas[freq] += 1
        datas = pd.DatetimeIndex(quadro["date"])
        fim = datas + (pd.offsets.MonthEnd(0) if freq == "M" else pd.offsets.QuarterEnd(0))
        fora = [d.date().isoformat() for d in datas[datas != fim][:3]]
        assert not fora, f"{alvo.name}: freq={freq} com date fora do fim de período {fora}"
    assert vistas["M"] >= 9 and vistas["Q"] >= 5, f"séries M/Q encontradas: {vistas}"


def test_pk_unica_e_nenhuma_data_depois_da_coleta(series_em_disco: list) -> None:
    """PK `(series_id, date, vintage)` e a guarda `sem_data_futura`, série por série."""
    for alvo in series_em_disco:
        quadro = pd.read_parquet(alvo)
        assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any(), alvo.name
        assert (quadro["date"] <= quadro["collected_at"]).all(), f"{alvo.name}: date > collected_at"


def test_painel_do_tesouro_segue_as_mesmas_convencoes() -> None:
    """O painel tem 750 `series_id` num arquivo só, mas o contrato é o mesmo (F-005)."""
    alvo = caminho_camada(Camada.PROCESSED) / PAINEL_TESOURO
    if not alvo.is_file():
        pytest.skip(f"{PAINEL_TESOURO} ausente — {COMO_GERAR}")
    quadro = pd.read_parquet(alvo)
    assert tuple(quadro.columns) == COLUNAS
    assert quadro["series_id"].nunique() > 700
    vintage = quadro["vintage"]
    assert vintage.notna().all()
    assert (vintage == vintage.dt.normalize()).all()
    assert (vintage == vintage.iloc[0]).all()
    assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any()
