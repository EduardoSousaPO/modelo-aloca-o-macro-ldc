"""F-022 — testes de **contrato** de `regime_asset_metrics` e da junção de `regimes`.

| Bloco | O que cobre | CA |
|---|---|---|
| A | `RegimeAssetMetricsSchema` item a item: PK, enum de `lente`, `n_obs` | CA-095 (pré), CA-092 |
| B | o que o contrato **recusa**: sem `n`, lente inventada, PK duplicada | CA-095, CA-108 |
| C | a relação com as tabelas de origem (V1, vizinhos V3, retornos) | CA-093, CA-102 |
| D | `RegimesSchema` e a junção de **D-r**: por que `regimes.parquet` não existe | CA-088 |
| E | o acervo em disco satisfaz o contrato | todos |

Contrato é o que o schema **recusa**, não só o que ele aceita: cada teste de recusa aqui existe
porque o erro correspondente é silencioso se o pandera não o pegar.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

from apps.pipeline.canonical import metricas_regime as M
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.asset_returns_quarterly import (
    ASSET_IDS_VALIDOS,
    AssetReturnsQuarterlySchema,
    RegimeAssetMetricsSchema,
)
from packages.shared.schemas.regimes import (
    COLUNAS_V1_DE_REGIMES,
    K_VIZINHOS_PADRAO,
    N_ALERTA,
    N_SUPRESSAO,
    RegimeNeighborsV3Schema,
    RegimesSchema,
    RegimesV1Schema,
    RegimeV1,
)

ERROS_DE_SCHEMA = (SchemaError, SchemaErrors)

COLUNAS_DO_CONTRATO: tuple[str, ...] = tuple(RegimeAssetMetricsSchema.to_schema().columns)


# ─────────────────────────────────────────────────────────────────────────────
# Linha-base sintética que o contrato aceita
# ─────────────────────────────────────────────────────────────────────────────


def _linha(**sobrescritas: object) -> dict[str, object]:
    """Uma célula válida de `regime_asset_metrics` — **sintética**, nomeada como tal."""
    base: dict[str, object] = {
        "lente": "V1",
        "regime": RegimeV1.RECUPERACAO.value,
        "asset_id": "IBOV",
        "n_obs": 12,
        "ret_medio": 0.04,
        "ret_mediana": 0.03,
        "ret_desvio": 0.10,
        "erro_padrao_media": 0.10 / 12**0.5,
        "hit_ratio": 0.75,
        "excesso_cdi": 0.01,
        "hit_ratio_cdi": 0.5,
        "ret_real": 0.02,
        "sharpe_tri": 0.1,
        "pior_tri": -0.20,
        "pior_tri_quarter": "2015Q3",
        "melhor_tri": 0.30,
        "melhor_tri_quarter": "2009Q2",
        "beta_ibov": 1.0,
        "alerta_n_baixo": False,
        "conclusao_suprimida": False,
        "data_inicio_serie": pd.Timestamp("2006-01-02"),
        "fonte_versao": "a" * 64,
    }
    base.update(sobrescritas)
    return base


def _tabela(*linhas: dict[str, object]) -> pd.DataFrame:
    """As linhas como DataFrame, com `data_inicio_serie` já em datetime."""
    quadro = pd.DataFrame(list(linhas) or [_linha()])
    quadro["data_inicio_serie"] = pd.to_datetime(quadro["data_inicio_serie"])
    return quadro


# ─────────────────────────────────────────────────────────────────────────────
# A. O contrato aceita o que tem de aceitar
# ─────────────────────────────────────────────────────────────────────────────


def test_linha_base_sintetica_passa_pelo_contrato() -> None:
    """Sem este teste, todos os de recusa poderiam passar por outro motivo."""
    RegimeAssetMetricsSchema.validate(_tabela(), lazy=True)


def test_pk_e_lente_regime_asset_id() -> None:
    """A PK declarada no contrato é exatamente a de `CONTRACTS.md §4.1`."""
    assert RegimeAssetMetricsSchema.to_schema().unique == ["lente", "regime", "asset_id"]


def test_lente_aceita_so_v1_v2_v3() -> None:
    """`lente ∈ {V1, V2, V3}` — e é por isso que materialização e horizonte não cabem nela."""
    for lente in (M.LENTE_V1, M.LENTE_V2, M.LENTE_V3):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(lente=lente)), lazy=True)


def test_n_obs_e_obrigatorio_e_nao_anulavel_por_contrato() -> None:
    """RN-04 / DoR de F-022: `n_obs` não anulável é o que garante `n` em toda célula."""
    coluna = RegimeAssetMetricsSchema.to_schema().columns["n_obs"]
    assert coluna.nullable is False
    assert "int" in str(coluna.dtype).lower()


def test_as_17_metricas_de_rf032_existem_no_contrato() -> None:
    """RF-032 nomeia as métricas; nenhuma pode estar fora do schema (Anti-SPEC §10.4.24)."""
    exigidas = {
        "n_obs",
        "ret_medio",
        "ret_mediana",
        "ret_desvio",
        "erro_padrao_media",
        "hit_ratio",
        "excesso_cdi",
        "hit_ratio_cdi",
        "ret_real",
        "sharpe_tri",
        "pior_tri",
        "pior_tri_quarter",
        "melhor_tri",
        "melhor_tri_quarter",
        "beta_ibov",
        "alerta_n_baixo",
        "conclusao_suprimida",
    }
    assert exigidas <= set(COLUNAS_DO_CONTRATO)


def test_celula_sem_observacao_e_valida_com_metricas_nulas() -> None:
    """Ativo que não existia no regime: `n_obs = 0` e todas as métricas nulas — linha presente."""
    vazia = _linha(
        n_obs=0,
        ret_medio=None,
        ret_mediana=None,
        ret_desvio=None,
        erro_padrao_media=None,
        hit_ratio=None,
        excesso_cdi=None,
        hit_ratio_cdi=None,
        ret_real=None,
        sharpe_tri=None,
        pior_tri=None,
        pior_tri_quarter=None,
        melhor_tri=None,
        melhor_tri_quarter=None,
        beta_ibov=None,
        alerta_n_baixo=True,
        conclusao_suprimida=True,
    )
    RegimeAssetMetricsSchema.validate(_tabela(vazia), lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# B. O contrato recusa o que tem de recusar
# ─────────────────────────────────────────────────────────────────────────────


def test_contrato_recusa_celula_sem_n() -> None:
    """CA-095 **no contrato**: célula sem `n` é impossível, não só desencorajada."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(n_obs=None)), lazy=True)


def test_contrato_recusa_n_negativo() -> None:
    """`n_obs >= 0`: contagem negativa é erro de montagem, não dado."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(n_obs=-1)), lazy=True)


def test_coerce_transforma_flag_booleana_nula_em_false_em_silencio() -> None:
    """⚠️ **ACHADO DE CONTRATO, não aceitação.** `nullable=False` + `coerce=True` em coluna `bool`
    **não recusa** `None`: o pandera manda `astype(bool)`, e em pandas `None → False` e
    `NaN → True`. Ou seja, uma flag de `n` ausente vira "não há alerta" **sem exceção nenhuma** —
    exatamente o modo de falha silenciosa que `AGENTS.md §2` diz ser o dominante deste projeto.

    O teste trava o comportamento medido (para que mudança de versão do pandera apareça) e prova
    que **este módulo não depende do schema** para isso: as duas flags saem de `alerta_n_baixo(n)`
    e `conclusao_suprimida(n)` sobre um `int`, então não existe caminho que produza `None`.

    Dívida para o orquestrador: `Check(lambda s: s.notna().all())` nas 2 flags de
    `RegimeAssetMetricsSchema` e nas 3 de `RegimesSchema` — é **alteração** de schema, logo pausa.
    """
    for flag in ("alerta_n_baixo", "conclusao_suprimida"):
        validada = RegimeAssetMetricsSchema.validate(_tabela(_linha(**{flag: None})), lazy=True)
        assert bool(validada[flag].iloc[0]) is False, "o coerce silencioso mudou de comportamento"

    for n in (0, 1, 4, 5, 7, 8, 20):
        saida = M.metricas_da_celula(
            pd.DataFrame(
                {
                    "quarter": [f"2010Q{i % 4 + 1}" for i in range(n)],
                    M.COLUNA_NOMINAL: [0.01] * n,
                    M.COLUNA_PRIMARIA: [0.01] * n,
                    M.COLUNA_REAL: [0.01] * n,
                }
            ),
            lente="V1",
            regime=RegimeV1.RECUPERACAO.value,
            asset_id="IBOV",
            data_inicio_serie=pd.Timestamp("2006-01-02"),
            referencia_beta=pd.Series(dtype="float64"),
            fonte_versao="a" * 64,
        )
        assert isinstance(saida["alerta_n_baixo"], bool)
        assert isinstance(saida["conclusao_suprimida"], bool)


def test_contrato_recusa_lente_inventada() -> None:
    """Uma lente V4 ou "V1_asof" não entra: a materialização vira **tabela**, não valor de enum."""
    for lente in ("V4", "V1_asof", "v1", "V1-T+1"):
        with pytest.raises(ERROS_DE_SCHEMA):
            RegimeAssetMetricsSchema.validate(_tabela(_linha(lente=lente)), lazy=True)


def test_contrato_recusa_asset_id_fora_do_universo() -> None:
    """`asset_id` tem de estar em `ASSET_IDS_VALIDOS` — ativo novo passa por acréscimo de schema."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(asset_id="PETR4")), lazy=True)


def test_contrato_recusa_pk_duplicada() -> None:
    """Duas linhas para a mesma célula significariam duas materializações misturadas."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(), _linha()), lazy=True)


def test_contrato_recusa_hit_ratio_fora_de_0_1() -> None:
    """Os dois hit ratios são frações. `75` (em %) seria o erro de escala clássico (D-o)."""
    for coluna in ("hit_ratio", "hit_ratio_cdi"):
        with pytest.raises(ERROS_DE_SCHEMA):
            RegimeAssetMetricsSchema.validate(_tabela(_linha(**{coluna: 75.0})), lazy=True)
        with pytest.raises(ERROS_DE_SCHEMA):
            RegimeAssetMetricsSchema.validate(_tabela(_linha(**{coluna: -0.1})), lazy=True)


def test_contrato_recusa_desvio_e_erro_padrao_negativos() -> None:
    """Dispersão negativa é impossível; `ge=0` pega sinal trocado na fórmula."""
    for coluna in ("ret_desvio", "erro_padrao_media"):
        with pytest.raises(ERROS_DE_SCHEMA):
            RegimeAssetMetricsSchema.validate(_tabela(_linha(**{coluna: -0.01})), lazy=True)


def test_contrato_recusa_coluna_inventada_porque_e_strict() -> None:
    """`strict=True` (Anti-SPEC §10.4.24): é o que transforma "coluna nova" em **pausa**.

    É também a razão de existirem 3 tabelas em vez de uma com `materializacao`/`horizonte`.
    """
    quadro = _tabela()
    quadro["horizonte"] = "T+1"
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(quadro, lazy=True)


def test_contrato_recusa_data_inicio_serie_nula() -> None:
    """CA-097: o rodapé das figuras precisa da janela própria de cada série."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(data_inicio_serie=pd.NaT)), lazy=True)


def test_contrato_recusa_fonte_versao_nula() -> None:
    """RF-047: rastreabilidade por linha — sem `fonte_versao` não se sabe que código gerou."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(_tabela(_linha(fonte_versao=None)), lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# C. A relação com as tabelas de origem
# ─────────────────────────────────────────────────────────────────────────────


def test_o_universo_de_ativos_e_o_mesmo_das_duas_tabelas() -> None:
    """`regime_asset_metrics.asset_id` e `asset_returns_quarterly.asset_id` compartilham o enum."""
    de_metricas = RegimeAssetMetricsSchema.to_schema().columns["asset_id"].checks
    de_retornos = AssetReturnsQuarterlySchema.to_schema().columns["asset_id"].checks
    assert [c.name for c in de_metricas] == [c.name for c in de_retornos]
    assert "IBOV" in ASSET_IDS_VALIDOS
    assert M.ASSET_ID_REFERENCIA_BETA in ASSET_IDS_VALIDOS


def test_os_limiares_de_n_sao_os_do_contrato_de_regimes() -> None:
    """`N_ALERTA`/`N_SUPRESSAO` moram em `schemas/regimes.py` — nunca duplicados no módulo."""
    assert (N_ALERTA, N_SUPRESSAO) == (8, 5)
    assert "n_obs < 8" in RegimeAssetMetricsSchema.to_schema().columns["alerta_n_baixo"].description
    assert (
        "n_obs < 5"
        in RegimeAssetMetricsSchema.to_schema().columns["conclusao_suprimida"].description
    )


def test_os_4_regimes_da_v1_sao_o_enum_do_contrato() -> None:
    """A lente V1 desta tabela usa os 4 rótulos de `RegimeV1`, sem um 5º para os indeterminados."""
    assert len(RegimeV1) == 4
    regimes = M.trimestres_por_regime_v1(
        pd.DataFrame({"quarter": ["2010Q1"], "regime_v1": [RegimeV1.RECUPERACAO.value]})
    )
    assert set(regimes) == {r.value for r in RegimeV1}


def test_o_regime_da_v3_nao_colide_com_o_enum_da_v1() -> None:
    """`regime` é string livre, mas o rótulo da V3 tem de ser inconfundível com um quadrante."""
    nome = M.nome_do_regime_v3("2026Q3")
    assert nome not in {r.value for r in RegimeV1}
    assert nome.startswith(M.PREFIXO_REGIME_V3)


def test_a_lente_v3_lida_e_a_canonica_de_d_u() -> None:
    """`CONTRACTS.md §5.2a`: `mahalanobis`, `k=8`, sem `somente_passado`, sem `pos2016`."""
    colunas = RegimeNeighborsV3Schema.to_schema().columns
    assert {"somente_passado", "restrito_pos_2016", "k_usado", "metrica"} <= set(colunas)
    assert K_VIZINHOS_PADRAO == 8


def test_f022_so_consome_colunas_que_existem_de_fato_em_regime_neighbors_v3() -> None:
    """⚠️ **`CONTRACTS.md §5.2a` está errada** (P1 do QA) — e F-022 não depende dela.

    A §5.2a diz que `RegimeNeighborsV3Schema` tem "**`rho_shrinkage`** e **as 5 features em
    unidade original**". **Nenhuma dessas colunas existe**, nem no schema nem no Parquet: `rho`
    mora em `relatorio_regimes_v3.json → shrinkage`. A verdade é o schema em
    `packages/shared/schemas/regimes.py` + as colunas reais do Parquet.

    Este teste é a guarda: ele falha se F-022 passar a depender de coluna que o contrato **de
    código** não declara, e trava as 8 colunas que `vizinhos_da_lente_canonica` de fato lê.
    """
    reais = set(RegimeNeighborsV3Schema.to_schema().columns)
    fantasmas = {"rho_shrinkage"} | {
        f"z_{nome}" for nome in ("ibcbr_gap", "ipca_desvio_meta", "juro_real_exante", "inclinacao")
    }
    assert not (fantasmas & reais), "o schema mudou: revise CONTRACTS.md §5.2a e este teste"

    lidas = {
        "quarter_ref",
        "rank",
        "quarter_neighbor",
        "distancia",
        "metrica",
        "k_usado",
        "somente_passado",
        "restrito_pos_2016",
    }
    assert lidas <= reais


def test_t_mais_1_e_coluna_do_contrato_de_vizinhos_nao_invencao_desta_feature() -> None:
    """CA-102 vive no schema de F-021 (`quarter_t_mais_1`); F-022 **consome**, não define."""
    assert "quarter_t_mais_1" in RegimeNeighborsV3Schema.to_schema().columns
    assert M.quarter_do_horizonte("2014Q4", M.Horizonte.T_MAIS_1) == "2015Q1"


def test_regimes_v1_schema_e_a_entrada_e_tem_regime_v1_anulavel() -> None:
    """A entrada é `RegimesV1Schema`, onde `regime_v1` é **anulável** — e por isso D-m cabe nela."""
    assert RegimesV1Schema.to_schema().columns["regime_v1"].nullable is True
    assert RegimesSchema.to_schema().columns["regime_v1"].nullable is False


# ─────────────────────────────────────────────────────────────────────────────
# D. `RegimesSchema` e a junção de D-r
# ─────────────────────────────────────────────────────────────────────────────


def test_regimes_schema_exige_as_tres_colunas_que_nao_sao_de_f019() -> None:
    """A aritmética de **D-r**, no contrato: 3 colunas `nullable=False` fora de F-019."""
    colunas = RegimesSchema.to_schema().columns
    for nome in ("ciclo_selic", "regime_v2", "stress_flag"):
        assert colunas[nome].nullable is False


def test_colunas_v1_de_regimes_e_exatamente_o_que_f019_fornece() -> None:
    """Toda coluna de `COLUNAS_V1_DE_REGIMES` existe em `RegimesSchema` com o mesmo nome."""
    assert set(COLUNAS_V1_DE_REGIMES) <= set(RegimesSchema.to_schema().columns)


def test_o_que_f022_declara_como_derivavel_cobre_as_colunas_que_sobram() -> None:
    """Fechamento da conta de D-r: V1 + derivável + bloqueado = **todas** as colunas do contrato."""
    todas = set(RegimesSchema.to_schema().columns)
    de_f019 = set(COLUNAS_V1_DE_REGIMES)
    derivaveis = set(M.DERIVAVEIS_NA_JUNCAO)
    bloqueadas = {"regime_v1", "stress_flag"}
    assert todas == de_f019 | derivaveis | bloqueadas
    assert de_f019 & derivaveis == set()


def test_regimes_schema_recusa_regime_v1_nulo() -> None:
    """O motivo nº 1 de `regimes.parquet` não existir — no contrato, não na prosa."""
    linhas = []
    for i, rotulo in enumerate([*[r.value for r in RegimeV1], None]):
        linhas.append(
            {
                "quarter": f"2010Q{i + 1}" if i < 4 else "2011Q1",
                "regime_v1": rotulo,
                "regime_v1b": None,
                "ciclo_selic": "NEUTRO",
                "regime_v2": f"{rotulo}_NEUTRO",
                "stress_flag": False,
                "g_score": 1.0,
                "pi_score": 0.5,
                "n_obs_regime_v1": 10,
                "alerta_n_baixo": False,
                "lag_adjusted": False,
                "trocou_vs_revised": None,
                "especificacao_congelada": False,
                "versao_especificacao": "V1",
                "fonte_versao": "a" * 64,
            }
        )
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimesSchema.validate(pd.DataFrame(linhas), lazy=True)


def test_stress_flag_nulo_passa_pelo_schema_virando_false_logo_a_guarda_e_do_modulo() -> None:
    """⚠️ **O motivo nº 2 de D-r, e a razão de `montar_regimes` bloquear ANTES de validar.**

    `stress_flag` é `nullable=False`, mas `coerce=True` converte `None → False`: um
    `regimes.parquet` sem a regra de RF-039 **passaria** pelo contrato declarando que **nenhum**
    trimestre dos 83 foi de stress — dado inventado, com o selo do pandera (Anti-SPEC §10.1.1).

    É por isso que o bloqueio de `montar_regimes` é uma lista de `bloqueios` avaliada **antes** de
    `RegimesSchema.validate`, e não a validação em si. Este teste prova as duas metades.
    """
    linhas = [
        {
            "quarter": f"2010Q{i + 1}",
            "regime_v1": rotulo,
            "regime_v1b": None,
            "ciclo_selic": "NEUTRO",
            "regime_v2": f"{rotulo}_NEUTRO",
            "stress_flag": None,
            "g_score": 1.0,
            "pi_score": 0.5,
            "n_obs_regime_v1": 10,
            "alerta_n_baixo": False,
            "lag_adjusted": False,
            "trocou_vs_revised": None,
            "especificacao_congelada": False,
            "versao_especificacao": "V1",
            "fonte_versao": "a" * 64,
        }
        for i, rotulo in enumerate(r.value for r in RegimeV1)
    ]
    validada = RegimesSchema.validate(pd.DataFrame(linhas), lazy=True)
    assert not validada["stress_flag"].any(), "o coerce silencioso mudou de comportamento"

    regimes_v1 = pd.DataFrame(
        {
            "quarter": [f"2010Q{i + 1}" for i in range(4)],
            "regime_v1": [r.value for r in RegimeV1],
            "g_score": 1.0,
            "pi_score": 0.5,
            "n_obs_regime_v1": 10,
            "alerta_n_baixo": False,
            "lag_adjusted": False,
            "trocou_vs_revised": None,
            "especificacao_congelada": False,
            "versao_especificacao": "V1",
            "fonte_versao": "a" * 64,
        }
    )
    macro = pd.DataFrame(
        {"quarter": [f"2010Q{i + 1}" for i in range(4)], "selic_meta_delta": [0.0] * 4}
    )
    juncao = M.montar_regimes(regimes_v1=regimes_v1, macro=macro, stress_flag=None)
    assert juncao.gravavel is False
    assert juncao.tabela is None
    assert any("stress_flag" in b for b in juncao.bloqueios)


def test_regimes_schema_exige_os_4_quadrantes_povoados() -> None:
    """`todos_os_quadrantes_povoados`: uma tabela `regimes` filtrada demais também é recusada.

    É o terceiro caminho fechado: excluir linhas até sobrar um subconjunto que "passe" não passa.
    """
    linhas = [
        {
            "quarter": "2010Q1",
            "regime_v1": RegimeV1.RECUPERACAO.value,
            "regime_v1b": None,
            "ciclo_selic": "NEUTRO",
            "regime_v2": "RECUPERACAO_NEUTRO",
            "stress_flag": False,
            "g_score": 1.0,
            "pi_score": 0.5,
            "n_obs_regime_v1": 10,
            "alerta_n_baixo": False,
            "lag_adjusted": False,
            "trocou_vs_revised": None,
            "especificacao_congelada": False,
            "versao_especificacao": "V1",
            "fonte_versao": "a" * 64,
        }
    ]
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimesSchema.validate(pd.DataFrame(linhas), lazy=True)


def test_regime_asset_metrics_schema_nao_tem_coluna_de_gate_de_publicacao() -> None:
    """Por que o gate (CA-090) é propagado no relatório: não existe coluna para ele aqui."""
    colunas = set(COLUNAS_DO_CONTRATO)
    assert "especificacao_congelada" not in colunas
    assert "versao_especificacao" not in colunas
    assert "especificacao_congelada" in RegimesSchema.to_schema().columns


def test_regime_asset_metrics_schema_nao_tem_materializacao_nem_horizonte() -> None:
    """A justificativa das 3 tabelas, verificada no contrato em vez de afirmada na docstring."""
    colunas = set(COLUNAS_DO_CONTRATO)
    assert not ({"materializacao", "lag_adjusted", "horizonte"} & colunas)
    assert len({t.nome_arquivo for t in M.TABELAS}) == len(M.TABELAS)


# ─────────────────────────────────────────────────────────────────────────────
# E. O acervo em disco satisfaz o contrato
# ─────────────────────────────────────────────────────────────────────────────


def _ignorar_data_real() -> bool:
    return os.environ.get("LDC_IGNORAR_DATA", "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


ARTEFATOS = tuple(t.nome_arquivo for t in M.TABELAS)
TEM_ACERVO = not _ignorar_data_real() and all(
    caminho_canonical(nome).is_file() for nome in ARTEFATOS
)
MOTIVO = (
    "LDC_IGNORAR_DATA ligada"
    if _ignorar_data_real()
    else "rode `uv run python -m apps.pipeline.canonical.metricas_regime`"
)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
@pytest.mark.parametrize("nome", ARTEFATOS)
def test_acervo_em_disco_valida_pelo_contrato(nome: str) -> None:
    """O Parquet gravado passa por `RegimeAssetMetricsSchema` lido de volta do disco."""
    quadro = pd.read_parquet(caminho_canonical(nome))
    RegimeAssetMetricsSchema.validate(quadro, lazy=True)
    assert set(quadro.columns) == set(COLUNAS_DO_CONTRATO)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
@pytest.mark.parametrize("nome", ARTEFATOS)
def test_acervo_tem_todos_os_ativos_em_todos_os_regimes(nome: str) -> None:
    """A grade é completa: `regimes × ativos` sem buraco — CA-095 antes da figura existir."""
    quadro = pd.read_parquet(caminho_canonical(nome))
    ativos = quadro["asset_id"].nunique()
    for (_, _), grupo in quadro.groupby(["lente", "regime"]):
        assert grupo["asset_id"].nunique() == ativos


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_nao_tem_regimes_parquet() -> None:
    """**D-r**: a junção fica bloqueada, então o artefato **não** existe — e isso é contrato."""
    assert not caminho_canonical(M.NOME_REGIMES_JUNTOS).is_file()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_fonte_versao_e_o_mesmo_nas_tres_tabelas() -> None:
    """Uma rodada = um `fonte_versao`: tabelas de rodadas diferentes nunca se misturam."""
    versoes = {
        v
        for nome in ARTEFATOS
        for v in pd.read_parquet(caminho_canonical(nome))["fonte_versao"].unique()
    }
    assert len(versoes) == 1
    assert versoes == {M.versao_build()}
