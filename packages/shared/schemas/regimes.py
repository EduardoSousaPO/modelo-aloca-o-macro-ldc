"""Schemas de `regimes` e `regime_neighbors` — classificação macro por três lentes.

Fonte de verdade do contrato (SPEC RF-027..RF-031, RF-036, RF-039; CA-078..091, CA-101..107).
Base de desenho: `docs/research/metodologia-regimes-macro.md §2 e §6.4`.

**Classe C.** A especificação de V1/V2/V3 é **congelada em ADR antes de rodar sobre os retornos**
(RF-031). Enquanto `ADR-001` estiver com status *Proposta*, o número não é publicável.

`[PROVISÓRIO D1]` V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário.
`[PROVISÓRIO D3]` eixo inflação = **aceleração** (delta do IPCA 12m), não desvio da meta.
"""

from __future__ import annotations

from enum import StrEnum

import pandera as pa
from pandera.typing import Series

QUARTER_REGEX = r"^(200[6-9]|20[1-2][0-9])Q[1-4]$"

K_VIZINHOS_PADRAO = 8
K_VIZINHOS_SENSIBILIDADE: tuple[int, ...] = (5, 8, 12)
N_TRIMESTRES_EXCLUIDOS_VIZINHANCA = 2
LIMIAR_SELIC_PP = 0.25
N_ALERTA = 8
N_SUPRESSAO = 5
LIMIAR_TROCA_REGIME_INOPERANTE = 0.25


class RegimeV1(StrEnum):
    """Quadrantes crescimento x inflação (RF-027)."""

    RECUPERACAO = "RECUPERACAO"
    EXPANSAO_INFL = "EXPANSAO_INFL"
    ESTAGFLACAO = "ESTAGFLACAO"
    DESACELERACAO = "DESACELERACAO"


class CicloSelic(StrEnum):
    """Camada de política monetária (RF-028)."""

    CORTE = "CORTE"
    ALTA = "ALTA"
    NEUTRO = "NEUTRO"


class MetricaDistancia(StrEnum):
    """Métrica da V3 (RF-029)."""

    MAHALANOBIS = "mahalanobis"
    EUCLIDIANA = "euclidiana"


FEATURES_V3: tuple[str, ...] = (
    "z_ibcbr_gap",
    "z_ipca_desvio_meta",
    "z_juro_real_exante",
    "z_inclinacao",
    "z_usdbrl_var_12m",
    "z_termos_troca_yoy",
)


class RegimesSchema(pa.DataFrameModel):
    """Rótulos e escores por trimestre. PK: `quarter`."""

    quarter: Series[str] = pa.Field(nullable=False, unique=True, str_matches=QUARTER_REGEX)
    regime_v1: Series[str] = pa.Field(nullable=False, isin=tuple(r.value for r in RegimeV1))
    regime_v1b: Series[str] = pa.Field(
        nullable=True,
        description="Versão vs. Focus — fase 2 (D2); nulo na v1, nunca copiado de regime_v1.",
    )
    ciclo_selic: Series[str] = pa.Field(nullable=False, isin=tuple(c.value for c in CicloSelic))
    regime_v2: Series[str] = pa.Field(
        nullable=False, description="regime_v1 + '_' + ciclo_selic — corte secundário (CA-083)."
    )
    stress_flag: Series[bool] = pa.Field(
        nullable=False,
        description="Inclinação cai > 1 d.p. OU USDBRL sobe > 10% no trimestre (RF-039).",
    )
    g_score: Series[float] = pa.Field(nullable=True)
    pi_score: Series[float] = pa.Field(nullable=True)
    n_obs_regime_v1: Series[int] = pa.Field(
        nullable=False, ge=1, description="`n` do quadrante — vai para toda célula de toda tabela."
    )
    alerta_n_baixo: Series[bool] = pa.Field(nullable=False)
    lag_adjusted: Series[bool] = pa.Field(
        nullable=False, description="True = classificado sobre `macro_quarterly_asof` (CA-072)."
    )
    trocou_vs_revised: Series[bool] = pa.Field(
        nullable=True,
        description="True = o rótulo difere da variante `revised`; a média alimenta CA-073/074.",
    )
    especificacao_congelada: Series[bool] = pa.Field(
        nullable=False, description="False enquanto ADR-001 estiver em status Proposta (CA-090)."
    )
    versao_especificacao: Series[str] = pa.Field(
        nullable=False, description="'V1' | 'V1.1' — mudança posterior nunca sobrescreve (CA-091)."
    )
    fonte_versao: Series[str] = pa.Field(
        nullable=False, description="Hash do código que gerou a classificação (CA-088)."
    )

    class Config:
        """Configuração do schema."""

        name = "regimes"
        strict = True
        coerce = True
        unique = ["quarter"]

    @pa.dataframe_check(name="todos_os_quadrantes_povoados")
    def _quadrantes_povoados(cls, df: object) -> bool:  # noqa: N805
        """Os 4 quadrantes da V1 existem na amostra (CA-078/080)."""
        return int(df["regime_v1"].nunique()) == len(RegimeV1)  # type: ignore[index]


class RegimeNeighborsSchema(pa.DataFrameModel):
    """Saída da V3: os k trimestres mais parecidos. PK: (quarter_ref, rank, metrica)."""

    quarter_ref: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    rank: Series[int] = pa.Field(nullable=False, ge=1, le=12)
    quarter_neighbor: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    distancia: Series[float] = pa.Field(nullable=False, ge=0)
    metrica: Series[str] = pa.Field(
        nullable=False, isin=tuple(m.value for m in MetricaDistancia)
    )
    k_usado: Series[int] = pa.Field(nullable=False, isin=K_VIZINHOS_SENSIBILIDADE)
    n_features: Series[int] = pa.Field(
        nullable=False,
        ge=5,
        le=6,
        description="5 quando a curva (RF-009) não ficou pronta — declarado, não silencioso.",
    )
    regime_v1_neighbor: Series[str] = pa.Field(
        nullable=False, isin=tuple(r.value for r in RegimeV1)
    )
    shrinkage: Series[str] = pa.Field(
        nullable=False, description="'ledoit_wolf' obrigatório em mahalanobis (CA-084)."
    )
    restrito_pos_2016: Series[bool] = pa.Field(
        nullable=False, description="True = variante V3-pos2016 (robustez a quebra estrutural)."
    )
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "regime_neighbors"
        strict = True
        coerce = True
        unique = ["quarter_ref", "rank", "metrica", "k_usado", "restrito_pos_2016"]

    @pa.dataframe_check(name="exclui_vizinhos_adjacentes")
    def _exclui_adjacentes(cls, df: object) -> bool:  # noqa: N805
        """Os 2 trimestres imediatamente anteriores ao de referência não entram (CA-085)."""
        return bool((df["quarter_ref"] != df["quarter_neighbor"]).all())  # type: ignore[index]
