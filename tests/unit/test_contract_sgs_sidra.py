"""Reconciliação SGS × SIDRA **por `date`**, sobre os Parquets de `data/processed/`.

Por que este arquivo existe: SGS 433 e SIDRA `t/1737 v/63` são **a mesma série** (IPCA, variação
mensal) e SGS 22109 é **a mesma série** que SIDRA `t/1621 v/584 c11255/90707` (PIB trimestral,
índice de volume com ajuste sazonal). F-004 provou a igualdade valor a valor — mas teve de juntar
as duas por `Period`, porque o SGS gravava `2026-09-01` e o SIDRA `2026-09-30`: **nenhuma linha
casava por `date`**. A consolidação da Onda 1 (D-a) uniformizou `date` em fim de período, e é isso
que este teste trava: `max|dif| == 0` com `join` por `date`, sem conversão de período no caminho.

Não é teste de rede nem de fixture: lê o que os extratores produziram em `data/processed/`. Se os
Parquets não existirem (CI limpo, máquina nova, `data/` apagado — e `data/` é reconstruível por
desenho, `CLAUDE.md §4`), o teste **pula** com a instrução de como gerá-los. É o único jeito de
um teste de consistência entre fontes conviver com um `data/` fora do git.
"""

from __future__ import annotations

import pandas as pd
import pytest

from apps.pipeline.common import caminho_processed

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


def _ler(relativo: str) -> pd.DataFrame | None:
    alvo = caminho_processed(relativo)
    if not alvo.is_file():
        return None
    return pd.read_parquet(alvo)


@pytest.mark.parametrize(("rotulo", "sgs", "sidra", "freq"), PARES, ids=[p[1] for p in PARES])
def test_sgs_e_sidra_casam_por_date_com_diferenca_zero(
    rotulo: str, sgs: str, sidra: str, freq: str
) -> None:
    """D-a: `join` por `date` casa e `max|dif| == 0` nas duas fontes da mesma série."""
    a, b = _ler(sgs), _ler(sidra)
    if a is None or b is None:
        pytest.skip(f"{rotulo}: falta {sgs} ou {sidra} em data/processed/ — {COMO_GERAR}")

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
    minimo = 240 if freq == "M" else 80
    assert len(junto) >= minimo, (
        f"{rotulo}: só {len(junto)} período(s) casaram por `date` — é o sintoma de convenção de "
        f"data divergente entre extratores, não de dado faltando"
    )
    assert float((junto["sgs"] - junto["sidra"]).abs().max()) == 0.0, (
        f"{rotulo}: as duas fontes publicam a mesma série; qualquer diferença é erro de parse "
        f"ou revisão não registrada"
    )


@pytest.mark.parametrize(("rotulo", "sgs", "sidra", "freq"), PARES, ids=[p[1] for p in PARES])
def test_as_duas_fontes_gravam_fim_de_periodo(rotulo: str, sgs: str, sidra: str, freq: str) -> None:
    """A data de toda linha M/Q é o **último dia civil** do período (`CLAUDE.md §3`)."""
    for relativo in (sgs, sidra):
        quadro = _ler(relativo)
        if quadro is None:
            pytest.skip(f"{rotulo}: falta {relativo} em data/processed/ — {COMO_GERAR}")
        datas = pd.DatetimeIndex(quadro["date"])
        fim = datas + (pd.offsets.MonthEnd(0) if freq == "M" else pd.offsets.QuarterEnd(0))
        assert (datas == fim).all(), f"{relativo}: há data que não é fim de período"
