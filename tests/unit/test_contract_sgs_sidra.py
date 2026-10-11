"""Reconciliação SGS × SIDRA **por `date`**, sobre fixture versionada e sobre `data/processed/`.

Por que este arquivo existe: SGS 433 e SIDRA `t/1737 v/63` são **a mesma série** (IPCA, variação
mensal) e SGS 22109 é **a mesma série** que SIDRA `t/1621 v/584 c11255/90707` (PIB trimestral,
índice de volume com ajuste sazonal). F-004 provou a igualdade valor a valor — mas teve de juntar
as duas por `Period`, porque o SGS gravava `2026-09-01` e o SIDRA `2026-09-30`: **nenhuma linha
casava por `date`**. A consolidação da Onda 1 (D-a) uniformizou `date` em fim de período, e é isso
que este teste trava: `max|dif| == 0` com `join` por `date`, sem conversão de período no caminho.

**Por que duas fontes de dado, e não uma.** Até 2026-10-11 este arquivo lia só `data/processed/`
e, sem Parquet, **pulava**. `data/` não está no git e o job `n1-basic` não reconstrói nada, então
num `actions/checkout` limpo a trava inteira pulava — a evidência central da consolidação não era
verificada por nenhum CI e D-a/D-b podiam regredir verde (P1-4 do QA da Onda 1). Agora:

- **`tests/fixtures/processed/`** (versionado, recorte real de ≤ 20 KB por série) roda **sempre**
  e nunca pula: ausência de fixture é falha, não skip;
- **`data/processed/`** (reconstruível, 51 séries completas) roda **além** disso, quando existe —
  a janela inteira é mais forte e continua sendo verificada na máquina de quem extrai.

`LDC_IGNORAR_DATA=1` desliga o segundo acervo: é como se simula localmente a árvore limpa do CI
sem apagar `data/` (`uv run pytest tests/unit/test_contract_sgs_sidra.py` com a variável ligada
tem de passar com os mesmos N testes, zero pulados).

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

#: `(rótulo, parquet do SGS, parquet do SIDRA, frequência esperada)` — os dois pares em que duas
#: fontes independentes publicam a mesma série (CA-002 e CA-009).
PARES: tuple[tuple[str, str, str, str], ...] = (
    ("IPCA variação mensal", "sgs/BCB_SGS_433.parquet", "sidra/SIDRA_1737_V63.parquet", "M"),
    (
        "PIB índice de volume dessazonalizado",
        "sgs/BCB_SGS_22109.parquet",
        "sidra/SIDRA_1621_V584_90707.parquet",
        "Q",
    ),
)

COMO_GERAR = (
    "rode `uv run python -m apps.pipeline.extract.bcb_sgs --offline` e "
    "`uv run python -m apps.pipeline.extract.ibge_sidra --offline`"
)

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
    """Um conjunto de Parquets de `processed_series` com os pisos que cabem no seu recorte.

    Os pisos são por acervo de propósito: a fixture é um recorte (9 meses, 4 trimestres) e o
    disco é a série inteira (273 meses, 90 trimestres). Usar o piso da fixture no disco
    esconderia série truncada; usar o piso do disco na fixture obrigaria a versionar 20 anos de
    dado — o que `tests/fixtures/README.md` proíbe.
    """

    rotulo: str
    raiz: Path
    minimo_m: int
    minimo_q: int
    #: `True` = ausência de Parquet é **falha** (o acervo está no git); `False` = é skip.
    obrigatorio: bool

    def minimo(self, freq: str) -> int:
        return self.minimo_m if freq == "M" else self.minimo_q


def _acervos() -> tuple[Acervo, ...]:
    """A fixture sempre; `data/processed/` por acréscimo, quando existe e não foi ignorado."""
    acervos = [Acervo("fixtures", RAIZ_FIXTURES, minimo_m=9, minimo_q=4, obrigatorio=True)]
    disco = caminho_camada(Camada.PROCESSED)
    if not ignorar_data_real() and disco.is_dir() and any(disco.glob("*/*.parquet")):
        acervos.append(
            Acervo("data/processed", disco, minimo_m=240, minimo_q=80, obrigatorio=False)
        )
    return tuple(acervos)


ACERVOS = _acervos()

CASOS = [(a, *p) for a in ACERVOS for p in PARES]
IDS = [f"{a.rotulo}:{p[1]}" for a in ACERVOS for p in PARES]


def _ler(acervo: Acervo, relativo: str, *, rotulo: str) -> pd.DataFrame | None:
    alvo = acervo.raiz / relativo
    if alvo.is_file():
        return pd.read_parquet(alvo)
    if acervo.obrigatorio:
        pytest.fail(
            f"{acervo.rotulo}: falta {relativo} — este acervo está no git e a trava de D-a não "
            f"pode pular. Regenere com o script de `tests/fixtures/processed/README.md`."
        )
    pytest.skip(f"{rotulo}: falta {relativo} em {acervo.rotulo}/ — {COMO_GERAR}")
    return None


@pytest.mark.parametrize(("acervo", "rotulo", "sgs", "sidra", "freq"), CASOS, ids=IDS)
def test_sgs_e_sidra_casam_por_date_com_diferenca_zero(
    acervo: Acervo, rotulo: str, sgs: str, sidra: str, freq: str
) -> None:
    """D-a: `join` por `date` casa e `max|dif| == 0` nas duas fontes da mesma série."""
    a = _ler(acervo, sgs, rotulo=rotulo)
    b = _ler(acervo, sidra, rotulo=rotulo)
    assert a is not None and b is not None

    assert set(a["freq"]) == {freq}, f"{sgs} deveria ser {freq}"
    assert set(b["freq"]) == {freq}, f"{sidra} deveria ser {freq}"

    junto = (
        a[["date", "value"]]
        .rename(columns={"value": "sgs"})
        .merge(
            b[["date", "value"]].rename(columns={"value": "sidra"}),
            on="date",
            how="inner",
            validate="one_to_one",
        )
        .dropna()
    )
    minimo = acervo.minimo(freq)
    assert len(junto) >= minimo, (
        f"{rotulo} [{acervo.rotulo}]: só {len(junto)} período(s) casaram por `date` (mínimo "
        f"{minimo}) — é o sintoma de convenção de data divergente entre extratores, não de dado "
        f"faltando"
    )
    assert float((junto["sgs"] - junto["sidra"]).abs().max()) == 0.0, (
        f"{rotulo} [{acervo.rotulo}]: as duas fontes publicam a mesma série; qualquer diferença "
        f"é erro de parse ou revisão não registrada"
    )


@pytest.mark.parametrize(("acervo", "rotulo", "sgs", "sidra", "freq"), CASOS, ids=IDS)
def test_as_duas_fontes_gravam_fim_de_periodo(
    acervo: Acervo, rotulo: str, sgs: str, sidra: str, freq: str
) -> None:
    """A data de toda linha M/Q é o **último dia civil** do período (`CLAUDE.md §3`)."""
    for relativo in (sgs, sidra):
        quadro = _ler(acervo, relativo, rotulo=rotulo)
        assert quadro is not None
        datas = pd.DatetimeIndex(quadro["date"])
        fim = datas + (pd.offsets.MonthEnd(0) if freq == "M" else pd.offsets.QuarterEnd(0))
        assert (datas == fim).all(), (
            f"{relativo} [{acervo.rotulo}]: há data que não é fim de período"
        )


def test_o_acervo_versionado_entra_sempre() -> None:
    """Meta-teste do P1-4: a trava não pode depender de `data/` existir.

    Se alguém reintroduzir o `pytest.skip` sem Parquet, este teste é o que acusa — ele afirma que
    o acervo de fixture está na lista de parametrização **sem** condição de ambiente.
    """
    assert any(a.rotulo == "fixtures" and a.obrigatorio for a in ACERVOS)
    for _, sgs, sidra, _ in PARES:
        for relativo in (sgs, sidra):
            assert (RAIZ_FIXTURES / relativo).is_file(), f"fixture ausente: {relativo}"
