"""Varredura de `processed_series`: as convenções que a Onda 1 uniformizou valem em TODA série.

O que cada extrator garante na sua própria série está testado no arquivo dele, sobre fixture. Este
arquivo faz a pergunta que nenhum extrator pode responder sozinho: **as séries que estão em disco
seguem a mesma convenção?** É a checagem que pegou as duas séries derivadas em BRL com `vintage`
da última data de pregão em vez da data da coleta.

**Dois acervos, não um** (P1-4 do QA da Onda 1). Até 2026-10-11 a varredura lia só
`data/processed/` e pulava sem Parquet; `data/` não está no git e o job `n1-basic` não reconstrói
nada, então num `actions/checkout` limpo as 4 varreduras pulavam e D-a/D-b podiam regredir verde.
Agora:

- **`tests/fixtures/processed/`** — recorte real (2006-01..2006-06 + os últimos 3 meses) de 7
  séries de 5 fontes + o painel do Tesouro, ≤ 20 KB cada, **versionado**. Roda sempre e **não
  pula**: fixture ausente é falha;
- **`data/processed/`** — as 51 séries completas, quando existem, **por acréscimo**. Os pisos
  deste acervo são os fortes (≥ 10 Parquets, ≥ 9 séries M, ≥ 5 séries Q, > 700 `series_id` no
  painel); os da fixture são os que cabem no recorte.

`LDC_IGNORAR_DATA=1` desliga o segundo acervo — é como se reproduz localmente a árvore limpa do
CI sem apagar `data/`.

Duas tabelas ficam **fora** da varredura por série porque não são `processed_series` ponto a
ponto: `calendario/dias_uteis_anbima.parquet` (grade de datas, `CalendarioDiasUteisSchema`) e
`tesouro-direto/td_painel.parquet` (painel de 750 `series_id` compostos) — a segunda é conferida
à parte, porque o contrato dela é o mesmo `ProcessedSeriesSchema`.

Procedência de cada recorte: `tests/fixtures/processed/README.md`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
"""Liga o modo "árvore limpa": só os acervos versionados entram, `data/` é ignorado."""

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "processed"


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


@dataclass(frozen=True)
class Acervo:
    """Uma raiz de `processed_series` com os pisos que cabem no seu recorte.

    Os pisos são por acervo de propósito: a fixture tem 7 séries recortadas e o disco tem as 51
    completas. Usar o piso da fixture no disco esconderia fonte inteira faltando; usar o piso do
    disco na fixture obrigaria a versionar 20 anos de dado, que
    `tests/fixtures/README.md` proíbe.
    """

    rotulo: str
    raiz: Path
    minimo_parquets: int
    minimo_series_m: int
    minimo_series_q: int
    minimo_series_painel: int

    def parquets_de_serie(self) -> list[Path]:
        if not self.raiz.is_dir():
            return []
        return sorted(
            p
            for p in self.raiz.glob("*/*.parquet")
            if not any(marca in p.as_posix() for marca in FORA_DA_VARREDURA)
        )


ACERVO_FIXTURES = Acervo(
    "fixtures",
    RAIZ_FIXTURES,
    minimo_parquets=7,
    minimo_series_m=2,
    minimo_series_q=2,
    minimo_series_painel=400,
)

ACERVO_DISCO = Acervo(
    "data/processed",
    caminho_camada(Camada.PROCESSED),
    minimo_parquets=10,
    minimo_series_m=9,
    minimo_series_q=5,
    minimo_series_painel=700,
)


def _acervos() -> tuple[Acervo, ...]:
    """A fixture sempre; `data/processed/` por acréscimo, quando tem acervo de verdade."""
    if ignorar_data_real() or len(ACERVO_DISCO.parquets_de_serie()) < ACERVO_DISCO.minimo_parquets:
        return (ACERVO_FIXTURES,)
    return (ACERVO_FIXTURES, ACERVO_DISCO)


ACERVOS = _acervos()
IDS = [a.rotulo for a in ACERVOS]


@pytest.fixture(params=ACERVOS, ids=IDS)
def acervo(request: pytest.FixtureRequest) -> Acervo:
    """Acervo sob varredura. `fixtures` nunca pula: recorte ausente é falha."""
    alvo: Acervo = request.param
    encontrados = alvo.parquets_de_serie()
    if len(encontrados) < alvo.minimo_parquets:
        pytest.fail(
            f"{alvo.rotulo}: {len(encontrados)} Parquet(s) de série, mínimo "
            f"{alvo.minimo_parquets} — {COMO_GERAR}"
        )
    return alvo


@pytest.fixture
def series_em_disco(acervo: Acervo) -> list[Path]:
    """Os Parquets de `processed_series` do acervo, já com o piso de quantidade conferido."""
    return acervo.parquets_de_serie()


def test_toda_serie_tem_as_8_colunas_e_passa_no_pandera(series_em_disco: list[Path]) -> None:
    """`strict=True`: nenhuma coluna ad hoc, nenhuma faltando, em nenhuma fonte."""
    for alvo in series_em_disco:
        quadro = pd.read_parquet(alvo)
        assert tuple(quadro.columns) == COLUNAS, alvo.name
        ProcessedSeriesSchema.validate(quadro, lazy=True)


def test_vintage_e_uma_data_sem_hora_nao_nula_e_constante_na_serie(
    series_em_disco: list[Path],
) -> None:
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


def test_serie_mensal_e_trimestral_tem_date_em_fim_de_periodo(
    acervo: Acervo, series_em_disco: list[Path]
) -> None:
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
    assert vistas["M"] >= acervo.minimo_series_m and vistas["Q"] >= acervo.minimo_series_q, (
        f"{acervo.rotulo}: séries M/Q encontradas: {vistas}"
    )


def test_pk_unica_e_nenhuma_data_depois_da_coleta(series_em_disco: list[Path]) -> None:
    """PK `(series_id, date, vintage)` e a guarda `sem_data_futura`, série por série."""
    for alvo in series_em_disco:
        quadro = pd.read_parquet(alvo)
        assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any(), alvo.name
        assert (quadro["date"] <= quadro["collected_at"]).all(), f"{alvo.name}: date > collected_at"


def test_painel_do_tesouro_segue_as_mesmas_convencoes(acervo: Acervo) -> None:
    """O painel tem 750 `series_id` num arquivo só, mas o contrato é o mesmo (F-005)."""
    alvo = acervo.raiz / PAINEL_TESOURO
    if not alvo.is_file():
        pytest.fail(f"{acervo.rotulo}: {PAINEL_TESOURO} ausente — {COMO_GERAR}")
    quadro = pd.read_parquet(alvo)
    assert tuple(quadro.columns) == COLUNAS
    assert quadro["series_id"].nunique() > acervo.minimo_series_painel
    ProcessedSeriesSchema.validate(quadro, lazy=True)
    vintage = quadro["vintage"]
    assert vintage.notna().all()
    assert (vintage == vintage.dt.normalize()).all()
    assert (vintage == vintage.iloc[0]).all()
    assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any()


def test_o_acervo_versionado_entra_sempre() -> None:
    """Meta-teste do P1-4: a varredura não pode depender de `data/` existir.

    Se alguém trocar a fixture `acervo` por um `pytest.skip` condicional, é este teste que
    acusa — ele afirma que o acervo versionado está na parametrização **sem** condição de
    ambiente, e que o recorte está de fato no git.
    """
    assert ACERVO_FIXTURES in ACERVOS
    assert len(ACERVO_FIXTURES.parquets_de_serie()) >= ACERVO_FIXTURES.minimo_parquets
    assert (RAIZ_FIXTURES / PAINEL_TESOURO).is_file()
