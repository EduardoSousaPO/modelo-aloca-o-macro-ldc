"""Guardas de contrato do canônico, validadas por comportamento (não por leitura de docstring).

Dois defeitos reais da auditoria do harness (`docs/plans/AUDITORIA-HARNESS.md`), cada um com o
teste que prova a correção:

- **E-2 / P1-6** — `sem_trimestre_antes_do_inicio_da_serie` comparava **só o ano**, então aceitava
  `2010Q1..Q3` para o IFIX (início 2010-12-30), `2007Q1..Q3` para o IMOB e `2006Q1..Q3` para o
  ICON: exatamente os três casos que a Anti-SPEC §10.1.1 nomeia como backfill proibido e que
  CA-063 manda ausentar da tabela.
- **Risco 3 / P1-10** — `RegimeNeighborsSchema.n_features` tinha `ge=5` e **rejeitava** o cenário de
  corte que o `PLAN.md §5` prevê como aceitável (Focus e curva cortados → 4 features).

Estes testes constroem o DataFrame mínimo que passa pelo schema inteiro e mexem **um** valor por
vez — é a única forma de provar que o check pega o caso, e não que o docstring promete pegar.
"""

from __future__ import annotations

from typing import Any

import pytest

pa = pytest.importorskip("pandera")
pd = pytest.importorskip("pandas")

from packages.shared.schemas.asset_returns_quarterly import (  # noqa: E402
    ASSET_IDS_VALIDOS,
    N_MINIMO_ATIVOS,
    AssetReturnsQuarterlySchema,
)
from packages.shared.schemas.regimes import RegimeNeighborsSchema  # noqa: E402

INICIO_IFIX = "2010-12-30"  # pesquisa §B8; S-06 no DECISIONS_LOG
INICIO_IMOB = "2007-12-28"  # pesquisa §B8; S-07 no DECISIONS_LOG
INICIO_ANTIGO = "2006-01-02"


def _linha_ativo(quarter: str, asset_id: str, data_inicio: str) -> dict[str, Any]:
    """Linha válida de `asset_returns_quarterly`; só `quarter`/`data_inicio` variam."""
    return {
        "quarter": quarter,
        "asset_id": asset_id,
        "price_ini": 100.0,
        "price_fim": 103.0,
        "ret_tri": 0.03,
        "ret_excesso_cdi": 0.005,
        "ret_real": 0.012,
        "vol_intra_tri": 0.11,
        "dd_intra_tri": -0.04,
        "is_total_return": True,
        "n_dias_uteis": 62.0,
        "ffill_dias_uteis": 0,
        "data_inicio_serie": pd.Timestamp(data_inicio),
        "source": "B3_API",
        "series_id": f"B3_{asset_id}",
        "fonte_versao": "deadbeef",
    }


def _painel(quarter_ifix: str, inicio_ifix: str = INICIO_IFIX) -> pd.DataFrame:
    """Painel mínimo: 18 ativos antigos em 2011Q1 + o IFIX no trimestre sob teste.

    18 é o piso de `minimo_de_ativos` (CA-062) — sem eles o schema falharia por outro motivo e o
    teste não provaria nada sobre o backfill.
    """
    antigos = [a for a in ASSET_IDS_VALIDOS if a != "IFIX"][:N_MINIMO_ATIVOS]
    linhas = [_linha_ativo("2011Q1", a, INICIO_ANTIGO) for a in antigos]
    linhas.append(_linha_ativo(quarter_ifix, "IFIX", inicio_ifix))
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────────────────────────────────────
# E-2 / P1-6 — backfill sintético
# ─────────────────────────────────────────────────────────────────────────────


def test_painel_de_referencia_e_valido() -> None:
    """Controle: sem o controle, um teste de rejeição não distingue a causa da falha."""
    AssetReturnsQuarterlySchema.validate(_painel("2011Q1"))


@pytest.mark.parametrize("quarter_proibido", ["2010Q1", "2010Q2", "2010Q3"])
def test_ifix_antes_de_2011q1_e_rejeitado(quarter_proibido: str) -> None:
    """CA-063: IFIX começa em 30/12/2010, logo 2010Q1..Q3 **não existem** na tabela.

    `2010Q3` é o caso que a versão anterior do check aceitava (mesmo ano do início).
    """
    with pytest.raises(pa.errors.SchemaError):
        AssetReturnsQuarterlySchema.validate(_painel(quarter_proibido))


def test_trimestre_que_contem_o_inicio_e_aceito_no_schema() -> None:
    """2010Q4 contém 30/12/2010: é parcial, não anterior — o schema aceita, por desenho.

    Quem decide se um trimestre de meia janela tem retorno calculável é a regra de `price_ini`
    (último dia útil de T−1) em F-014, não este check.
    """
    AssetReturnsQuarterlySchema.validate(_painel("2010Q4"))


def test_imob_antes_de_2008q1_e_rejeitado() -> None:
    """Mesmo defeito, outro ativo: IMOB começa em 28/12/2007 (S-07 no `DECISIONS_LOG.md`)."""
    painel = _painel("2011Q1")
    alvo = painel["asset_id"] == "IMOB"
    assert alvo.sum() == 1, "o painel de referência deveria conter exatamente uma linha de IMOB"
    painel.loc[alvo, "data_inicio_serie"] = pd.Timestamp(INICIO_IMOB)
    painel.loc[alvo, "quarter"] = "2007Q3"
    with pytest.raises(pa.errors.SchemaError):
        AssetReturnsQuarterlySchema.validate(painel)


# ─────────────────────────────────────────────────────────────────────────────
# Risco 3 / P1-10 — piso de features da V3
# ─────────────────────────────────────────────────────────────────────────────


def _vizinhos(n_features: int) -> pd.DataFrame:
    """Saída mínima de V3: 2 vizinhos de um trimestre de referência."""
    return pd.DataFrame(
        [
            {
                "quarter_ref": "2026Q3",
                "rank": rank,
                "quarter_neighbor": vizinho,
                "distancia": 0.5 * rank,
                "metrica": "mahalanobis",
                "k_usado": 8,
                "n_features": n_features,
                "regime_v1_neighbor": "ESTAGFLACAO",
                "shrinkage": "ledoit_wolf",
                "restrito_pos_2016": False,
                "fonte_versao": "deadbeef",
            }
            for rank, vizinho in enumerate(("2015Q4", "2016Q1"), start=1)
        ]
    )


@pytest.mark.parametrize("n_features", [3, 4, 5, 6])
def test_n_features_aceita_o_cenario_de_corte_do_plan(n_features: int) -> None:
    """`PLAN.md §5`: cortes 4 (Focus) e 5 (curva) são independentes e podem cair juntos.

    6 = tudo pronto · 5 = sem curva (CA-086) · 4 = sem Focus e sem curva · 3 = G-02 também aberto.
    """
    RegimeNeighborsSchema.validate(_vizinhos(n_features))


@pytest.mark.parametrize("n_features", [2, 7])
def test_n_features_fora_do_piso_e_do_teto_e_rejeitado(n_features: int) -> None:
    """2 features não é "momentos semelhantes", é ruído; 7 não existe (`FEATURES_V3` tem 6)."""
    with pytest.raises(pa.errors.SchemaError):
        RegimeNeighborsSchema.validate(_vizinhos(n_features))
