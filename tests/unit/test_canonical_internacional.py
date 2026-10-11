"""F-026 — testes unitários de `apps/pipeline/canonical/internacional.py`. **Classe C.**

| Bloco | O que cobre | CA |
|---|---|---|
| 1 | variância mínima: forma **fechada** de 2 ativos, long-only, soma 1, cap | §4.3 item 1 |
| 2 | expanding **não usa o futuro** (desvio e pesos) | metodologia §5.1 |
| 3 | correlação: alinhamento por índice, `n` de pares, `None` com < 2 pares | CA-105 |
| 4 | `stress_flag` pela disjunção declarada; ramos separados; não avaliável | CA-106 |
| 5 | truncamento na banda tática + a faixa de D6 (nunca número pontual) | CA-107 |
| 6 | flags de `n`: `n < 8` alerta, `n < 5` suprime — **a linha fica** | CA-108/109 |
| 7 | **anti-subtração**: excesso por razão ≠ média das subtrações | CA-069 |
| 8 | negativos: hedgeado × sem hedge, total × price return, EMBI fora | CA-104/106 |
| 9 | `stress_flag` destrava a junção de **D-r** de F-022 | CA-088 |
| 10 | **acervo real** `data/canonical/` — padrão `Acervo` | todos |

Todo dado deste arquivo fora do bloco 10 é **sintético e nomeado como tal** (Anti-SPEC §10.1.2).
O bloco 10 segue o padrão `Acervo` de `test_canonical_metricas_regime.py §11`: nunca falha por
ausência de `data/` (que não está no git) e entra por acréscimo quando o Parquet existe.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
import pytest

from apps.pipeline.canonical import internacional as I  # noqa: E741 - modulo, nao variavel
from apps.pipeline.canonical.metricas_regime import excesso_por_razao, montar_regimes
from apps.pipeline.canonical.regimes_v1 import status_adr_001
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.internacional import (
    ATIVO_INTERNACIONAL_REPRESENTATIVO,
    ATIVOS_SEM_FONTE,
    BANDA_TATICA_MAX,
    BANDA_TATICA_MIN,
    CARTEIRA_VARIANCIA_MINIMA,
    LIMIAR_USDBRL_VAR_TRI_PCT,
    MIN_OBS_DESVIO_EXPANDING,
    InternacionalPesosSchema,
    InternacionalPorRegimeSchema,
)
from packages.shared.schemas.regimes import N_ALERTA, N_SUPRESSAO, RegimeV1

COMO_GERAR = "rode `uv run python -m apps.pipeline.canonical.internacional`"


def _quarters(n: int, *, ano_inicial: int = 2010) -> list[str]:
    """`n` trimestres consecutivos a partir de `{ano_inicial}Q1` — **sintéticos**."""
    periodos = pd.period_range(f"{ano_inicial}Q1", periods=n, freq="Q")
    return [f"{p.year}Q{p.quarter}" for p in periodos]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Variância mínima — a forma fechada de 2 ativos é o oráculo
# ─────────────────────────────────────────────────────────────────────────────


def _peso_fechado_de_2_ativos(s11: float, s22: float, s12: float) -> float:
    """`w1 = (σ22 − σ12) / (σ11 + σ22 − 2σ12)` — a solução analítica, escrita à mão aqui."""
    return (s22 - s12) / (s11 + s22 - 2.0 * s12)


@pytest.mark.parametrize(
    ("s11", "s22", "s12"),
    [
        (0.04, 0.01, 0.0),  # sem correlacao: peso inverso a variancia
        (0.04, 0.01, 0.005),  # correlacao positiva
        (0.04, 0.01, -0.008),  # correlacao negativa
        (0.02, 0.02, 0.004),  # variancias iguais => 50/50
    ],
)
def test_variancia_minima_de_2_ativos_bate_a_forma_fechada(
    s11: float, s22: float, s12: float
) -> None:
    """O oráculo do solver: 2 ativos sem cap têm solução analítica, e ela tem de sair exata."""
    sigma = np.array([[s11, s12], [s12, s22]])
    esperado = _peso_fechado_de_2_ativos(s11, s22, s12)
    obtido = I.variancia_minima(sigma, cap=1.0)
    assert obtido[0] == pytest.approx(esperado, abs=1e-12)
    assert obtido[1] == pytest.approx(1.0 - esperado, abs=1e-12)


def test_variancia_minima_de_variancias_iguais_e_meio_a_meio() -> None:
    """Caso fechado mais legível de todos: `σ11 = σ22` ⇒ 50/50, qualquer que seja `σ12`."""
    pesos = I.variancia_minima(np.array([[0.02, 0.004], [0.004, 0.02]]), cap=1.0)
    assert pesos == pytest.approx([0.5, 0.5], abs=1e-12)


def test_variancia_minima_e_long_only_e_soma_um() -> None:
    """Long-only e soma 1 nas duas restrições, inclusive quando a irrestrita pediria peso < 0.

    Com `σ12` muito positivo e variâncias desiguais, a solução **sem** restrição de sinal manda
    vender o ativo de maior variância. O solver tem de responder com `0`, não com negativo.
    """
    sigma = np.array([[0.01, 0.02], [0.02, 0.09]])
    irrestrito = _peso_fechado_de_2_ativos(0.01, 0.09, 0.02)
    assert not 0.0 <= irrestrito <= 1.0 or irrestrito > 1.0  # a irrestrita sai da caixa
    pesos = I.variancia_minima(sigma, cap=1.0)
    assert (pesos >= 0.0).all()
    assert pesos.sum() == pytest.approx(1.0, abs=1e-12)


def test_variancia_minima_respeita_o_cap_e_o_canto_fica_exatamente_no_cap() -> None:
    """Com cap, o ativo quase sem variância para **no** cap — não acima, não aproximadamente."""
    sigma = np.diag([1e-6, 0.04, 0.09])  # o primeiro e um "CDI" sintetico
    pesos = I.variancia_minima(sigma, cap=0.40)
    assert pesos[0] == pytest.approx(0.40, abs=1e-12)
    assert (pesos <= 0.40 + 1e-12).all()
    assert pesos.sum() == pytest.approx(1.0, abs=1e-12)


def test_variancia_minima_sem_cap_concentra_no_ativo_de_variancia_quase_nula() -> None:
    """O contraponto do teste anterior: é o **cap** que impede o canto, não o solver."""
    sigma = np.diag([1e-6, 0.04, 0.09])
    pesos = I.variancia_minima(sigma, cap=1.0)
    assert pesos[0] > 0.95


def test_variancia_minima_recusa_cap_que_nao_alcanca_soma_um() -> None:
    """`cap × p < 1` é **inviável** e tem de falhar nomeando o número, não devolver pesos."""
    with pytest.raises(I.AlocacaoInviavel, match="nao alcanca soma 1"):
        I.variancia_minima(np.eye(3), cap=0.30)


def test_variancia_minima_recusa_matriz_nao_quadrada() -> None:
    """Guarda de forma: `(n, p)` com `n != p` não é covariância."""
    with pytest.raises(I.AlocacaoInviavel, match="matriz quadrada"):
        I.variancia_minima(np.zeros((2, 3)), cap=1.0)


def test_variancia_minima_e_o_minimo_de_verdade_contra_busca_em_grade() -> None:
    """Prova independente do solver: nenhuma carteira da grade bate a devolvida.

    A grade é **outro método** (força bruta na simplex com passo de 1 pp). Se o conjunto ativo
    estiver errado, a grade acha algo melhor e o teste quebra.
    """
    rng = np.random.default_rng(20261011)
    base = rng.normal(size=(40, 4))
    sigma = np.cov(base, rowvar=False) + np.eye(4) * 0.01
    pesos = I.variancia_minima(sigma, cap=0.40)
    melhor = float(pesos @ sigma @ pesos)
    passo = 0.01
    grade = np.arange(0.0, 0.40 + 1e-12, passo)
    for w0 in grade:
        for w1 in grade:
            for w2 in grade:
                w3 = 1.0 - w0 - w1 - w2
                if w3 < -1e-12 or w3 > 0.40 + 1e-12:
                    continue
                candidata = np.array([w0, w1, w2, max(w3, 0.0)])
                assert float(candidata @ sigma @ candidata) >= melhor - 1e-12


def test_pesos_de_amostra_devolve_none_com_amostra_curta() -> None:
    """Menos de `MIN_OBS_COVARIANCIA` trimestres ⇒ célula **sem** pesos, não pesos de 2 pontos."""
    amostra = pd.DataFrame({"A": [0.01, 0.02], "B": [0.03, -0.01]}, index=_quarters(2))
    assert I.pesos_de_amostra(amostra) is None


def test_pesos_de_amostra_usa_o_shrinkage_importado_de_f021() -> None:
    """`rho` é **medido**: vem de `regimes_v3.ledoit_wolf`, e está em [0, 1] por construção."""
    rng = np.random.default_rng(7)
    amostra = pd.DataFrame(rng.normal(scale=0.05, size=(20, 3)), columns=["A", "B", "C"])
    pesos = I.pesos_de_amostra(amostra, cap=0.50)
    assert pesos is not None
    assert 0.0 <= pesos.rho <= 1.0
    assert pesos.n_obs == 20
    assert sum(pesos.pesos) == pytest.approx(1.0, abs=1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Expanding: nada posterior a T−1 entra no número de T
# ─────────────────────────────────────────────────────────────────────────────


def test_desvio_expanding_usa_somente_o_passado() -> None:
    """O desvio de `T` é o das linhas `< T`: confere contra `np.std(ddof=1)` à mão."""
    serie = pd.Series([1.0, 3.0, 2.0, 8.0, 5.0, 4.0, 9.0, 7.0, 6.0, 10.0], index=_quarters(10))
    desvio = I.desvio_expanding_ate_t_menos_1(serie, min_obs=3)
    assert pd.isna(desvio.iloc[0])
    assert pd.isna(desvio.iloc[2])  # so 2 anteriores
    esperado = float(np.std(serie.to_numpy()[:3], ddof=1))
    assert desvio.iloc[3] == pytest.approx(esperado, abs=1e-12)
    esperado_7 = float(np.std(serie.to_numpy()[:7], ddof=1))
    assert desvio.iloc[7] == pytest.approx(esperado_7, abs=1e-12)


def test_desvio_expanding_nao_muda_quando_o_futuro_muda() -> None:
    """A prova de anti-look-ahead: mexer na **última** linha não move nenhum desvio anterior."""
    valores = [1.0, 3.0, 2.0, 8.0, 5.0, 4.0, 9.0, 7.0, 6.0, 10.0]
    original = I.desvio_expanding_ate_t_menos_1(pd.Series(valores, index=_quarters(10)), min_obs=3)
    mexido = list(valores)
    mexido[-1] = 1_000.0
    depois = I.desvio_expanding_ate_t_menos_1(pd.Series(mexido, index=_quarters(10)), min_obs=3)
    pd.testing.assert_series_equal(original, depois)


def _retornos_sinteticos(n: int = 30, *, semente: int = 11) -> pd.DataFrame:
    """Painel longo sintético com os 4 ativos da carteira — **sintético**, nomeado como tal."""
    rng = np.random.default_rng(semente)
    quarters = _quarters(n, ano_inicial=2000)
    linhas = []
    escalas = {"CDI": 0.0005, "IMAB": 0.03, "IBOV": 0.10, ATIVO_INTERNACIONAL_REPRESENTATIVO: 0.07}
    for asset_id, escala in escalas.items():
        valores = rng.normal(loc=0.02, scale=escala, size=n)
        for quarter, valor in zip(quarters, valores, strict=True):
            linhas.append({"quarter": quarter, "asset_id": asset_id, "ret_tri": float(valor)})
    return pd.DataFrame(linhas)


def test_pesos_expanding_nao_usam_o_futuro() -> None:
    """Mexer no **último** trimestre não muda nenhum peso anterior (metodologia §5.1)."""
    painel = _retornos_sinteticos()
    antes = I.pesos_expanding(painel, cap=0.40, min_obs=MIN_OBS_DESVIO_EXPANDING)
    ultimo = max(str(q) for q in painel["quarter"].unique())
    mexido = painel.copy()
    alvo = mexido["quarter"] == ultimo
    mexido.loc[alvo, "ret_tri"] = mexido.loc[alvo, "ret_tri"] + 10.0
    depois = I.pesos_expanding(mexido, cap=0.40, min_obs=MIN_OBS_DESVIO_EXPANDING)
    anteriores = [q for q in antes if q < ultimo]
    assert anteriores
    for quarter in anteriores:
        assert antes[quarter].pesos == pytest.approx(depois[quarter].pesos, abs=1e-12)


def test_pesos_expanding_de_t_tem_n_igual_ao_numero_de_trimestres_antes_de_t() -> None:
    """`n_obs` do peso de `T` conta trimestres **estritamente** antes de `T`: o próprio sai."""
    painel = _retornos_sinteticos(n=20)
    por_quarter = I.pesos_expanding(painel, cap=0.40, min_obs=5)
    quarters = sorted(str(q) for q in painel["quarter"].unique())
    for quarter, pesos in por_quarter.items():
        assert pesos.n_obs == quarters.index(quarter)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Correlação condicional (CA-105)
# ─────────────────────────────────────────────────────────────────────────────


def test_correlacao_perfeita_positiva_e_negativa() -> None:
    """Casos conhecidos: `+1` e `−1` exatos, com o `n` de pares ao lado."""
    indice = _quarters(6)
    a = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=indice)
    assert I.correlacao_de_pares(a, a * 3.0).valor == pytest.approx(1.0, abs=1e-12)
    assert I.correlacao_de_pares(a, -a * 2.0).valor == pytest.approx(-1.0, abs=1e-12)
    assert I.correlacao_de_pares(a, a).n_pares == 6


def test_correlacao_alinha_por_indice_e_nao_por_posicao() -> None:
    """Padrões de nulo diferentes: o par é por `quarter`, nunca por posição na lista."""
    a = pd.Series([1.0, 2.0, 3.0, 4.0], index=["2010Q1", "2010Q2", "2010Q3", "2010Q4"])
    b = pd.Series([3.0, 4.0, 5.0], index=["2010Q3", "2010Q4", "2011Q1"])
    saida = I.correlacao_de_pares(a, b)
    assert saida.n_pares == 2
    por_posicao = I.correlacao_de_pares(pd.Series(a.to_numpy()[:3]), pd.Series(b.to_numpy()))
    assert por_posicao.n_pares == 3  # o erro que o alinhamento por indice evita


def test_correlacao_com_menos_de_dois_pares_e_none_e_declara_o_n() -> None:
    """Correlação de 1 ponto não existe: `None`, **com** o `n` que a impediu."""
    a = pd.Series([1.0], index=["2010Q1"])
    b = pd.Series([2.0], index=["2010Q1"])
    saida = I.correlacao_de_pares(a, b)
    assert saida.valor is None
    assert saida.n_pares == 1
    assert saida.como_dicionario() == {"correlacao": None, "n_pares": 1}


def test_correlacao_de_serie_constante_e_none_nao_nan() -> None:
    """Desvio zero de um lado ⇒ `None` explícito, nunca `NaN` vazando para o Parquet."""
    indice = _quarters(5)
    constante = pd.Series([0.01] * 5, index=indice)
    variavel = pd.Series([0.01, 0.02, -0.01, 0.03, 0.0], index=indice)
    assert I.correlacao_de_pares(constante, variavel).valor is None


def test_piores_trimestres_do_ibov_sao_os_dez_menores_em_ordem() -> None:
    """CA-105: "os 10 piores trimestres do IBOV", crescente, empate pelo mais antigo."""
    quarters = _quarters(12, ano_inicial=2000)
    valores = [0.10, -0.30, 0.05, -0.20, -0.05, 0.02, -0.40, 0.01, -0.10, 0.07, -0.02, 0.03]
    painel = pd.DataFrame(
        {
            "quarter": quarters,
            "asset_id": ["IBOV"] * 12,
            "ret_tri": valores,
        }
    )
    piores = I.piores_trimestres_do_ibov(painel, n=3)
    assert piores == [quarters[6], quarters[1], quarters[3]]


# ─────────────────────────────────────────────────────────────────────────────
# 4. `stress_flag` pela regra declarada (CA-106)
# ─────────────────────────────────────────────────────────────────────────────


def _stress_sintetico(
    *, inclinacoes: list[float], cambio: list[float], min_obs: int = 3
) -> pd.DataFrame:
    """A regra de CA-106 sobre séries **sintéticas** controladas."""
    indice = _quarters(len(inclinacoes))
    return I.stress_por_trimestre(
        inclinacao=pd.Series(inclinacoes, index=indice),
        usdbrl_var_tri=pd.Series(cambio, index=indice),
        min_obs=min_obs,
    )


def test_stress_marca_o_ramo_do_cambio_acima_de_dez_por_cento() -> None:
    """Ramo 2 da disjunção: `usdbrl_var_tri > 10%`, estritamente, sem depender da inclinação."""
    stress = _stress_sintetico(
        inclinacoes=[1.0] * 6,
        cambio=[0.0, 9.99, LIMIAR_USDBRL_VAR_TRI_PCT, 10.01, 25.0, -30.0],
    )
    assert stress["ramo_usdbrl"].tolist() == [False, False, False, True, True, False]
    assert stress["stress_flag"].tolist() == [False, False, False, True, True, False]


def test_stress_marca_o_ramo_da_inclinacao_por_queda_de_mais_de_um_desvio() -> None:
    """Ramo 1: `Δincl < −1σ_exp`. A série sobe de forma suave e depois **cai** forte."""
    inclinacoes = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 0.2]
    stress = _stress_sintetico(inclinacoes=inclinacoes, cambio=[0.0] * 10, min_obs=3)
    assert stress["ramo_inclinacao"].tolist()[-1] is True
    assert not stress["ramo_inclinacao"].tolist()[:-1].count(True)
    ultima = stress.iloc[-1]
    assert ultima["delta_inclinacao"] == pytest.approx(-1.6, abs=1e-12)
    assert ultima["delta_inclinacao"] < ultima["limiar_queda"]


def test_stress_nao_marca_queda_pequena_nem_alta_grande() -> None:
    """ "Cai mais de 1 desvio" é sobre a **queda**: subida enorme não é stress pelo ramo 1."""
    inclinacoes = [1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 9.0]
    stress = _stress_sintetico(inclinacoes=inclinacoes, cambio=[0.0] * 10, min_obs=3)
    assert not stress["ramo_inclinacao"].any()


def test_stress_e_disjuncao_e_nao_conjuncao() -> None:
    """RF-039 diz **ou**: um ramo sozinho marca, e o relatório conta os dois separados."""
    inclinacoes = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 0.2]
    cambio = [0.0, 0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    stress = _stress_sintetico(inclinacoes=inclinacoes, cambio=cambio, min_obs=3)
    assert stress.loc[stress["quarter"] == _quarters(10)[4], "stress_flag"].all()
    assert stress.loc[stress["quarter"] == _quarters(10)[9], "stress_flag"].all()
    assert int(stress["stress_flag"].sum()) == 2


def test_stress_sem_desvio_estimavel_e_nao_avaliavel_e_nao_falso_disfarcado() -> None:
    """Os primeiros trimestres não têm 8 anteriores: `avaliavel_inclinacao=False`, declarado."""
    stress = _stress_sintetico(inclinacoes=[1.0, 2.0, 0.0, 5.0, 3.0], cambio=[0.0] * 5, min_obs=3)
    assert stress["avaliavel_inclinacao"].tolist() == [False, False, False, False, True]
    assert not stress.loc[~stress["avaliavel_inclinacao"], "ramo_inclinacao"].any()


def test_stress_com_inclinacao_nula_nao_e_avaliavel_pelo_ramo_1_mas_o_cambio_vale() -> None:
    """Buraco na inclinação não cega o ramo do câmbio — os ramos são independentes."""
    inclinacoes = [1.0, 1.1, 1.2, 1.3, float("nan"), 1.5]
    stress = _stress_sintetico(inclinacoes=inclinacoes, cambio=[0.0, 0, 0, 0, 30.0, 0], min_obs=3)
    linha = stress.iloc[4]
    assert not bool(linha["avaliavel_inclinacao"])
    assert bool(linha["ramo_usdbrl"])
    assert bool(linha["stress_flag"])


def test_stress_tem_o_ramo_embi_sempre_falso_e_declarado() -> None:
    """CA-106: o ramo EMBI fica **declaradamente** fora (L8) — coluna presente e sempre `False`."""
    stress = _stress_sintetico(inclinacoes=[1.0] * 6, cambio=[0.0] * 6)
    assert "ramo_embi" in stress.columns
    assert not stress["ramo_embi"].any()
    assert "EMBI" in I.RAMO_EMBI_FORA and "Fase 2" in I.RAMO_EMBI_FORA


def test_serie_de_stress_flag_e_indexada_por_quarter_e_booleana() -> None:
    """O formato que `montar_regimes` espera — o contrato entre F-026 e F-022."""
    stress = _stress_sintetico(inclinacoes=[1.0] * 5, cambio=[0, 0, 20.0, 0, 0])
    serie = I.serie_de_stress_flag(stress)
    assert serie.index.tolist() == _quarters(5)
    assert serie.dtype == bool
    assert serie.sum() == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. A banda e a faixa (CA-107)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("cru", "esperado"),
    [
        (0.0, BANDA_TATICA_MIN),
        (0.05, BANDA_TATICA_MIN),
        (BANDA_TATICA_MIN, BANDA_TATICA_MIN),
        (0.22, 0.22),
        (BANDA_TATICA_MAX, BANDA_TATICA_MAX),
        (0.60, BANDA_TATICA_MAX),
        (1.0, BANDA_TATICA_MAX),
    ],
)
def test_truncar_na_banda_satura_nos_dois_extremos(cru: float, esperado: float) -> None:
    """A banda tática de ADR-003 é um intervalo **fechado**: fora dela, satura; dentro, preserva."""
    assert I.truncar_na_banda(cru) == pytest.approx(esperado, abs=1e-15)


def test_truncar_na_banda_preserva_none() -> None:
    """Célula sem peso continua sem peso — `None` nunca vira 15%."""
    assert I.truncar_na_banda(None) is None


def test_tabela_de_faixa_entrega_intervalo_e_nunca_numero_pontual() -> None:
    """CA-107: cada linha tem `faixa_sugerida` (par) + `n` + selo; nenhum "o número é X"."""
    resumo = {
        "por_regime": {
            "cap_0.40": {
                "RECUPERACAO": {"peso_internacional": 0.236, "n_obs": 19},
                "ESTAGFLACAO": {"peso_internacional": 0.02, "n_obs": 6},
            }
        }
    }
    faixa = I.tabela_de_faixa(resumo)
    assert faixa["forma"].startswith("piso estrutural + banda tatica")
    assert "NUNCA numero pontual" in faixa["forma"]
    assert faixa["selo"] == I.SELO_NAO_RECOMENDACAO
    por_regime = {linha["regime"]: linha for linha in faixa["linhas"]}
    assert por_regime["RECUPERACAO"]["peso_sugerido_na_banda"] == pytest.approx(0.236)
    assert por_regime["RECUPERACAO"]["truncado"] is False
    assert por_regime["ESTAGFLACAO"]["peso_sugerido_na_banda"] == pytest.approx(BANDA_TATICA_MIN)
    assert por_regime["ESTAGFLACAO"]["truncado"] is True
    assert por_regime["ESTAGFLACAO"]["alerta_n_baixo"] is True
    for linha in faixa["linhas"]:
        assert isinstance(linha["faixa_sugerida"], list) and len(linha["faixa_sugerida"]) == 2
        assert linha["faixa_sugerida"][0] < linha["faixa_sugerida"][1]
        assert "n_obs" in linha


def test_tabela_de_faixa_declara_a_distincao_entre_hedgeado_e_cambial() -> None:
    """ADR-003 Contexto: 2,5-7% hedgeado (XP) **não** é 16-35% cambial (FGV). Erro de leitura."""
    faixa = I.tabela_de_faixa({"por_regime": {"cap_0.40": {}}})
    assert "HEDGEADO" in faixa["distincao_obrigatoria"]
    assert "CAMBIAL" in faixa["distincao_obrigatoria"]


def test_faixa_cobre_o_piso_estrutural_mesmo_quando_o_peso_cru_e_menor() -> None:
    """O piso é **estrutural**: regime com peso cru de 2% não "pede menos que o piso"."""
    faixa = I.tabela_de_faixa(
        {"por_regime": {"cap_0.40": {"X": {"peso_internacional": 0.02, "n_obs": 12}}}}
    )
    linha = faixa["linhas"][0]
    assert linha["faixa_sugerida"][0] <= I.PISO_ESTRUTURAL_MIN
    assert linha["faixa_sugerida"][1] >= I.PISO_ESTRUTURAL_MAX


# ─────────────────────────────────────────────────────────────────────────────
# 6. Flags de `n` (CA-108 / CA-109)
# ─────────────────────────────────────────────────────────────────────────────


def test_neutralizacao_e_risk_off_trazem_as_duas_flags_de_n() -> None:
    """`n` em toda célula + as duas flags: é regra de apresentação, não de conveniência."""
    quarters = _quarters(6)
    painel = pd.DataFrame(
        [
            {"quarter": q, "asset_id": "IBOV", "ret_tri": -0.10, "ret_excesso_cdi": -0.12}
            for q in quarters
        ]
        + [
            {"quarter": q, "asset_id": "USDBRL", "ret_tri": 0.05, "ret_excesso_cdi": 0.03}
            for q in quarters
        ]
    )
    saida = I.neutralizacao_do_usd(painel, quarters[:4])
    assert saida["n"] == 4
    assert saida["alerta_n_baixo"] is True  # 4 < 8
    assert saida["conclusao_suprimida"] is True  # 4 < 5
    assert saida["fracao_usd"] == pytest.approx(0.10 / 0.15, abs=1e-12)


def test_neutralizacao_devolve_none_quando_o_ibov_nao_caiu() -> None:
    """Sem queda não há o que neutralizar — e o motivo vai escrito, não implícito."""
    quarters = _quarters(4)
    painel = pd.DataFrame(
        [{"quarter": q, "asset_id": "IBOV", "ret_tri": 0.04} for q in quarters]
        + [{"quarter": q, "asset_id": "USDBRL", "ret_tri": 0.01} for q in quarters]
    )
    saida = I.neutralizacao_do_usd(painel, quarters)
    assert saida["fracao_usd"] is None
    assert "nao caiu" in saida["motivo"]


def test_limiares_de_n_sao_os_do_contrato() -> None:
    """Os limiares vêm de `packages.shared.schemas.regimes` — não há cópia local deles."""
    assert N_ALERTA == 8
    assert N_SUPRESSAO == 5
    assert MIN_OBS_DESVIO_EXPANDING == 8


# ─────────────────────────────────────────────────────────────────────────────
# 7. Anti-subtração (CA-069 / Anti-SPEC §10.2.13)
# ─────────────────────────────────────────────────────────────────────────────


def test_excesso_por_razao_nao_e_subtracao_e_a_diferenca_e_material() -> None:
    """Com CDI de 3,25% e retorno de 10%: razão 6,538%, subtração 6,75%. 0,21 pp numa célula."""
    assert excesso_por_razao(0.10, 0.0325) == pytest.approx(0.06537530, abs=1e-8)
    assert excesso_por_razao(0.10, 0.0325) != pytest.approx(0.10 - 0.0325, abs=1e-5)


def test_media_de_excessos_por_razao_difere_da_media_das_subtracoes() -> None:
    """O erro que a Anti-SPEC §10.2.13 proíbe, medido numa célula sintética de 4 trimestres."""
    retornos = [0.10, -0.05, 0.20, 0.00]
    cdis = [0.0325, 0.0300, 0.0450, 0.0250]
    por_razao = float(
        np.mean([excesso_por_razao(r, c) for r, c in zip(retornos, cdis, strict=True)])
    )
    por_subtracao = float(np.mean([r - c for r, c in zip(retornos, cdis, strict=True)]))
    assert abs(por_razao - por_subtracao) > 1e-4


# ─────────────────────────────────────────────────────────────────────────────
# 8. Negativos: o que o módulo se recusa a fazer
# ─────────────────────────────────────────────────────────────────────────────


def test_hedgeado_nao_esta_na_carteira_nem_na_tabela() -> None:
    """D7/CA-104: `SP500_HEDGE` não existe em disco e **não** é aproximado nem somado."""
    assert "SP500_HEDGE" in ATIVOS_SEM_FONTE
    assert "SP500_HEDGE" not in CARTEIRA_VARIANCIA_MINIMA
    assert "SP500_HEDGE" not in I.ATIVOS_DA_TABELA_POR_REGIME


def test_carteira_de_variancia_minima_nao_mistura_total_return_com_price_return() -> None:
    """Anti-SPEC §10.2.12 / CA-064: o internacional da covariância é o **total return**."""
    assert ATIVO_INTERNACIONAL_REPRESENTATIVO == "ACWI_BRL"
    assert I.ATIVO_INTERNACIONAL_ALTERNATIVO not in CARTEIRA_VARIANCIA_MINIMA


def test_matriz_de_retornos_bloqueia_em_vez_de_imputar_ativo_ausente() -> None:
    """Ativo sem série ⇒ `BLOQUEADO — FONTE INDISPONÍVEL`, nunca coluna de zeros."""
    painel = pd.DataFrame(
        [{"quarter": q, "asset_id": "CDI", "ret_tri": 0.02} for q in _quarters(8)]
    )
    with pytest.raises(I.FonteIndisponivel, match="BLOQUEADO — FONTE INDISPONÍVEL"):
        I.matriz_de_retornos(painel, quarters=_quarters(8), ativos=("CDI", "IBOV"))


def test_matriz_de_retornos_descarta_trimestre_incompleto_em_vez_de_preencher() -> None:
    """Trimestre sem um dos ativos **sai** da covariância, e o `n` diz quantos sobraram."""
    quarters = _quarters(5)
    linhas = [{"quarter": q, "asset_id": "CDI", "ret_tri": 0.02} for q in quarters]
    linhas += [{"quarter": q, "asset_id": "IBOV", "ret_tri": 0.03} for q in quarters[:3]]
    linhas += [{"quarter": q, "asset_id": "IBOV", "ret_tri": None} for q in quarters[3:]]
    larga = I.matriz_de_retornos(pd.DataFrame(linhas), quarters=quarters, ativos=("CDI", "IBOV"))
    assert len(larga) == 3
    assert larga.notna().all().all()


def test_bloqueio_de_anti_spec_da_variancia_minima_esta_declarado() -> None:
    """A tabela de pesos é apoio interno: o bloqueio nomeia as duas seções e a feature destino."""
    texto = I.BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA
    assert "10.3.16" in texto
    assert "10.5" in texto
    assert "F-035" in texto


def test_status_adr_003_e_lido_do_disco_e_falha_fechada(tmp_path) -> None:  # noqa: ANN001
    """Arquivo ausente ⇒ `DESCONHECIDO`, que **não** congela D6. Nunca o contrário."""
    assert I.status_adr_003(raiz=tmp_path) == I.STATUS_ADR_DESCONHECIDO
    assert I.d6_esta_congelada(raiz=tmp_path) is False


def test_status_adr_003_usa_a_mesma_leitura_que_o_adr_001(tmp_path) -> None:  # noqa: ANN001
    """A leitura de status é a **mesma** de F-019: mesmo formato, mesma resposta."""
    alvo_003 = tmp_path / I.CAMINHO_ADR_003
    alvo_001 = tmp_path / "docs" / "decisions" / "adr" / "ADR-001-lente-de-regime-oficial.md"
    alvo_003.parent.mkdir(parents=True, exist_ok=True)
    corpo = "# ADR\n\n- **Status:** **Aceita** — depois de tudo\n"
    alvo_003.write_text(corpo, encoding="utf-8")
    alvo_001.write_text(corpo, encoding="utf-8")
    assert I.status_adr_003(raiz=tmp_path) == status_adr_001(raiz=tmp_path) == "ACEITA"
    assert I.d6_esta_congelada(raiz=tmp_path) is True


# ─────────────────────────────────────────────────────────────────────────────
# 9. `stress_flag` destrava a junção de D-r (CA-088)
# ─────────────────────────────────────────────────────────────────────────────


def _regimes_v1_sintetico(quarters: list[str]) -> pd.DataFrame:
    """Mínimo de `regimes_v1` que `montar_regimes` consome — **sintético**.

    Os 4 quadrantes são povoados em rodízio porque `RegimesSchema` tem o check
    `todos_os_quadrantes_povoados` (CA-078/080): uma amostra de um só rótulo é recusada pelo
    contrato, e é o contrato que este bloco está exercitando.
    """
    rotulos = [r.value for r in RegimeV1]
    return pd.DataFrame(
        {
            "quarter": quarters,
            "regime_v1": [rotulos[i % len(rotulos)] for i in range(len(quarters))],
            "status_regime_v1": ["CLASSIFICADO"] * len(quarters),
            "motivo_indeterminado": [None] * len(quarters),
            "g_score": [1.0] * len(quarters),
            "pi_score": [1.0] * len(quarters),
            "crescimento_acima": [True] * len(quarters),
            "inflacao_acelerando": [False] * len(quarters),
            "desempate_aplicado": [False] * len(quarters),
            "n_obs_regime_v1": [len(quarters)] * len(quarters),
            "alerta_n_baixo": [False] * len(quarters),
            "conclusao_suprimida": [False] * len(quarters),
            "alerta_desbalanceamento": [True] * len(quarters),
            "lag_adjusted": [False] * len(quarters),
            "trocou_vs_revised": [None] * len(quarters),
            "especificacao_congelada": [False] * len(quarters),
            "versao_especificacao": ["V1"] * len(quarters),
            "fonte_versao": ["sintetico"] * len(quarters),
        }
    )


def test_stress_flag_de_f026_remove_o_bloqueio_de_stress_flag_da_juncao_de_f022() -> None:
    """O contrato entre as duas features: F-022 deixou o bloqueio, F-026 o resolve.

    Antes (sem a série): a junção bloqueia por `stress_flag`. Depois (com a série desta feature):
    aquele bloqueio **desaparece**. Nenhum outro bloqueio é tocado — `regime_v1` nulo é **D-m**.
    """
    quarters = _quarters(8)
    regimes = _regimes_v1_sintetico(quarters)
    macro = pd.DataFrame({"quarter": quarters, "selic_meta_delta": [0.5] * 8})

    sem = montar_regimes(regimes_v1=regimes, macro=macro, stress_flag=None)
    assert any("stress_flag" in b for b in sem.bloqueios)

    stress = _stress_sintetico(inclinacoes=[1.0] * 8, cambio=[0, 0, 20.0, 0, 0, 0, 0, 0])
    com = montar_regimes(
        regimes_v1=regimes, macro=macro, stress_flag=I.serie_de_stress_flag(stress)
    )
    assert not any("stress_flag" in b for b in com.bloqueios)
    assert com.gravavel
    assert com.tabela is not None
    assert int(com.tabela["stress_flag"].sum()) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 10. Acervo real (`data/canonical/`) — padrão `Acervo`
# ─────────────────────────────────────────────────────────────────────────────


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (mesma semântica de `test_canonical_metricas_regime.py`)."""
    return os.environ.get("LDC_IGNORAR_DATA", "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


@dataclass(frozen=True)
class Acervo:
    """As entradas de `data/canonical/` que o build real precisa, e se a ausência é falha."""

    rotulo: str
    entradas: tuple[str, ...]
    obrigatorio: bool


ACERVO = Acervo(
    rotulo="canonical",
    entradas=(
        "regimes_v1.parquet",
        "regimes_v1_asof.parquet",
        "asset_returns_quarterly.parquet",
        "regime_neighbors_v3.parquet",
        "macro_quarterly.parquet",
        "raw_series.parquet",
        "series_catalog.parquet",
    ),
    obrigatorio=False,
)

TEM_ACERVO = not ignorar_data_real() and all(
    caminho_canonical(nome).is_file() for nome in ACERVO.entradas
)

MOTIVO = (
    "LDC_IGNORAR_DATA ligada"
    if ignorar_data_real()
    else f"acervo ausente em data/canonical/ — {COMO_GERAR}"
)


@cache
def _construido() -> I.ResultadoInternacional:
    """`construir(gravar=False)` memoizado — o teste não escreve em `data/`."""
    return I.construir(gravar=False)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_as_duas_tabelas_validam_e_tem_pk_unica() -> None:
    """Os dois Parquets passam pelos seus schemas com a PK declarada."""
    resultado = _construido()
    InternacionalPorRegimeSchema.validate(resultado.por_regime, lazy=True)
    InternacionalPesosSchema.validate(resultado.pesos, lazy=True)
    assert not resultado.por_regime.duplicated(subset=["lente", "regime", "asset_id"]).any()
    assert not resultado.pesos.duplicated(
        subset=["escopo", "chave", "cap", "carteira", "asset_id"]
    ).any()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_tem_n_em_toda_celula() -> None:
    """Anti-SPEC §10.2.8: `n_obs` não é nulo em célula nenhuma, nas duas tabelas."""
    resultado = _construido()
    for quadro in (resultado.por_regime, resultado.pesos):
        assert quadro["n_obs"].notna().all()
        assert (quadro["n_obs"] >= 0).all()
        assert quadro["fonte_versao"].notna().all()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_ca104_colunas_de_retorno_sao_identicas_as_de_f022() -> None:
    """**CA-104 no dado**: as colunas comuns batem com `regime_asset_metrics.parquet` exatamente.

    Resíduo **zero**, não "pequeno": é a mesma função de F-022 sobre a mesma fatia. Qualquer
    valor diferente de 0 significa que alguém reimplementou o cálculo aqui.
    """
    alvo = caminho_canonical("regime_asset_metrics.parquet")
    if not alvo.is_file():
        pytest.skip("regime_asset_metrics.parquet ausente — rode F-022")
    f022 = pd.read_parquet(alvo)
    aqui = _construido().por_regime
    comuns = ["ret_medio", "ret_mediana", "excesso_cdi", "ret_real", "hit_ratio_cdi", "n_obs"]
    esquerda = aqui.loc[aqui["lente"] == "V1"].set_index(["regime", "asset_id"])
    direita = f022.loc[f022["lente"] == "V1"].set_index(["regime", "asset_id"])
    indice = esquerda.index.intersection(direita.index)
    assert len(indice) >= len(I.ATIVOS_DA_TABELA_POR_REGIME)
    for coluna in comuns:
        a = esquerda.loc[indice, coluna].astype("float64")
        b = direita.loc[indice, coluna].astype("float64")
        assert ((a - b).abs().fillna(0.0) == 0.0).all(), coluna


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_stress_flag_tem_os_dois_ramos_e_os_trimestres_listados() -> None:
    """CA-106 no dado: a regra marca trimestres, os dois ramos contribuem e a lista existe."""
    relatorio = _construido().relatorio["regra_de_stress"]
    assert relatorio["n_trimestres"] == 83
    assert relatorio["n_stress"] > 0
    assert relatorio["n_so_pelo_ramo_inclinacao"] > 0
    assert relatorio["n_so_pelo_ramo_usdbrl"] > 0
    assert len(relatorio["trimestres_de_stress"]) == relatorio["n_stress"]
    assert relatorio["embi_delta_tri_nao_nulos"] == 0  # o ramo EMBI nao tem fonte (L8)
    assert "2008Q4" in [linha["quarter"] for linha in relatorio["trimestres_de_stress"]]


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_stress_destrava_a_juncao_de_regimes_de_f022() -> None:
    """Com a série real, o bloqueio de `stress_flag` sai e só o de `regime_v1` (D-m) fica."""
    bloco = _construido().relatorio["regra_de_stress"]["destrava_regimes_schema"]
    assert bloco["bloqueio_de_stress_flag_resolvido"] is True
    assert bloco["bloqueios_restantes"]
    assert all("stress_flag" not in b for b in bloco["bloqueios_restantes"])


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_hedge_funciona_melhor_no_stress_e_o_n_esta_ao_lado() -> None:
    """CA-105 no dado: `corr(USDBRL, IBOV)` é **mais negativa** no stress que fora dele.

    Não é hipótese que o teste impõe ao dado: é o achado medido (−0,80 contra −0,42), e o teste
    existe para **denunciar** se uma mudança de pipeline o inverter em silêncio.
    """
    blocos = _construido().relatorio["hedge_cambial"]["stress_vs_nao_stress"]["blocos"]
    assert blocos["stress"]["correlacao"] < blocos["nao_stress"]["correlacao"]
    assert blocos["stress"]["correlacao"] < 0.0
    for bloco in blocos.values():
        assert bloco["n_pares"] >= 2
        assert "alerta_n_baixo" in bloco
    assert blocos["dez_piores_do_ibov"]["n_pares"] == 10


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_pesos_sao_long_only_somam_um_e_respeitam_o_cap() -> None:
    """As três restrições, conferidas no Parquet publicado e não só no solver."""
    pesos = _construido().pesos
    assert (pesos["peso"] >= 0.0).all()
    assert (pesos["peso"] <= pesos["cap"] + 1e-9).all()
    somas = pesos.groupby(["escopo", "chave", "cap", "carteira"])["peso"].sum()
    assert ((somas - 1.0).abs() < 1e-9).all()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_peso_na_banda_existe_so_no_internacional_e_esta_na_banda() -> None:
    """CA-107: a banda é sobre o internacional, e nenhum valor sai de [15%, 35%]."""
    pesos = _construido().pesos
    com_banda = pesos.loc[pesos["peso_na_banda"].notna()]
    assert set(com_banda["asset_id"].unique()) == {ATIVO_INTERNACIONAL_REPRESENTATIVO}
    assert (com_banda["peso_na_banda"] >= BANDA_TATICA_MIN - 1e-12).all()
    assert (com_banda["peso_na_banda"] <= BANDA_TATICA_MAX + 1e-12).all()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_expanding_nao_usa_o_futuro_no_primeiro_trimestre_com_peso() -> None:
    """O primeiro peso expanding aparece só depois de `MIN_OBS_DESVIO_EXPANDING` trimestres."""
    pesos = _construido().pesos
    expanding = pesos.loc[pesos["escopo"] == I.ESCOPO_EXPANDING]
    assert not expanding.empty
    assert (expanding["n_obs"] >= MIN_OBS_DESVIO_EXPANDING).all()
    primeiro = expanding["chave"].min()
    assert primeiro > "2006Q1"


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_gate_de_publicacao_esta_fechado_e_nada_e_publicavel() -> None:
    """CA-090 + Anti-SPEC: ADR-001/ADR-003 em Proposta ⇒ `publicavel=False`, com o selo."""
    gate = _construido().relatorio["gate_de_publicacao"]
    assert gate["publicavel"] is False
    assert gate["adr_001"]["especificacao_congelada"] is False
    assert gate["adr_003_d6"]["d6_congelada"] is False
    assert gate["anti_spec"]["variancia_minima_fora_da_v1"] is True
    assert I.SELO_NAO_RECOMENDACAO in gate["selo"]
    assert (_construido().pesos["especificacao_congelada"] == False).all()  # noqa: E712


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_ativos_sem_fonte_saem_bloqueados_e_nao_aproximados() -> None:
    """Anti-SPEC §10.1.1: ouro, UST10 e o hedgeado saem **nomeados** como indisponíveis."""
    relatorio = _construido().relatorio["universo"]
    for ativo in ATIVOS_SEM_FONTE:
        assert ativo in relatorio["bloqueados_sem_fonte"]
        assert "BLOQUEADO" in relatorio["bloqueados_sem_fonte"][ativo]
    assert ativo not in set(_construido().por_regime["asset_id"].unique())
    assert "HEDGEADO" in relatorio["hedge_d7"].upper()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_decomposicao_do_sp500_em_brl_fecha() -> None:
    """`(1+SP500_BRL) = (1+SP500_USD)(1+USDBRL)`: se não fechar, "em BRL" é afirmação vazia."""
    bloco = _construido().relatorio["universo"]["decomposicao_sp500"]
    assert bloco["conferido"] is True
    assert bloco["max_abs_residuo"] < 1e-12
    assert bloco["n"] >= 80


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_duas_rodadas_dao_o_mesmo_hash() -> None:
    """Idempotência (RF-048/CA-121): nada de relógio, nada de estado, mesmo byte."""
    primeira = I.construir(gravar=False).relatorio["hashes"]
    segunda = I.construir(gravar=False).relatorio["hashes"]
    assert primeira == segunda


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_flag_de_total_return_distingue_acwi_de_sp500() -> None:
    """CA-064 no dado: o representativo é total return e o alternativo não — e os dois aparecem."""
    por_regime = _construido().por_regime
    flags = por_regime.drop_duplicates(subset=["asset_id"]).set_index("asset_id")["is_total_return"]
    assert bool(flags[ATIVO_INTERNACIONAL_REPRESENTATIVO]) is True
    assert bool(flags[I.ATIVO_INTERNACIONAL_ALTERNATIVO]) is False
