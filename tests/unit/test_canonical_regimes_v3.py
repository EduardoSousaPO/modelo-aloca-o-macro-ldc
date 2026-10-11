"""F-021 — testes da V3 (vizinhos mais próximos + retorno em T+1). **Classe C.**

Quatro seções, nesta ordem de confiança:

| Seção | Sobre o quê | O que prova |
|---|---|---|
| **A** | álgebra em matriz sintética | Mahalanobis, shrinkage de Ledoit-Wolf, padronização |
| **B** | busca de vizinhos | CA-085 (exclusão + desempate) e `n < k` declarado |
| **C** | retorno em T+1 e ranking | CA-102 e as regras de `n` (CA-108/109) |
| **D** | **acervo real** de `data/canonical/` | o Parquet publicado, com recálculo à mão em numpy |

A seção D é a cobertura de **integração** desta feature. Ela não usa `@pytest.mark.integration`
porque o marcador **não está registrado** no `pyproject` e `--strict-markers` falharia a coleta —
é o mesmo padrão declarado de `test_processed_layer_conventions.py` e `test_canonical_retornos.py`
(`TODO.md §6`): a seção **pula** sem `data/canonical/`.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.pipeline.canonical import regimes_v3 as modulo
from apps.pipeline.canonical.macro_quarterly import NOME_MACRO
from apps.pipeline.canonical.regimes_v3 import (
    ESPECIFICACAO_CONGELADA,
    FEATURES_DESCARTADAS,
    FEATURES_USADAS,
    LENTES,
    MIN_OBS_PADRONIZACAO_EXPANDING,
    QUARTER_DO_COMITE,
    CovarianciaSingular,
    FeaturesInsuficientes,
    Lente,
    Vizinho,
    covariancia_amostral,
    distancia_em_trimestres,
    distancias_euclidianas,
    distancias_mahalanobis,
    fonte_versao_declarada,
    inverter,
    janela,
    ledoit_wolf,
    matriz_de_features,
    montar_vizinhos,
    padronizar,
    projetar_no_contrato,
    quarter_seguinte,
    ranking_de_ativos,
    retornos_em_t_mais_1,
    rotulos_v1_de_anotacao,
    trimestres_com_vetor_completo,
    vizinhos_mais_proximos,
)
from apps.pipeline.canonical.retornos import NOME_RETORNOS
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.regimes import (
    K_VIZINHOS_PADRAO,
    K_VIZINHOS_SENSIBILIDADE,
    N_ALERTA,
    N_SUPRESSAO,
    N_TRIMESTRES_EXCLUIDOS_VIZINHANCA,
    MetricaDistancia,
    RegimeNeighborsV3Schema,
    RegimeV1,
    StatusRegimeV1,
    indice_do_quarter,
)

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
"""Liga o modo "árvore limpa": `data/` é ignorado e a seção D pula."""

NOME_NEIGHBORS = modulo.NOME_NEIGHBORS
NOME_NEIGHBORS_V3 = modulo.NOME_NEIGHBORS_V3

# ─────────────────────────────────────────────────────────────────────────────
# Seção A — álgebra, em matriz sintética
# ─────────────────────────────────────────────────────────────────────────────


def _matriz_aleatoria(n: int = 40, p: int = 5, semente: int = 7) -> np.ndarray:
    """Matriz com correlação de verdade entre as colunas — e com semente fixa."""
    gerador = np.random.default_rng(semente)
    base = gerador.normal(size=(n, 2))
    ruido = gerador.normal(scale=0.4, size=(n, p))
    carga = gerador.normal(size=(2, p))
    return base @ carga + ruido


def test_mahalanobis_com_covariancia_identidade_e_a_euclidiana() -> None:
    """Com `Sigma = I`, a Mahalanobis **é** a Euclidiana — bit a bit, não "parecida".

    É o que prova que a diferença entre as duas métricas publicadas está só na covariância: se
    alguém trocar a forma quadrática por outra coisa, este teste cai.
    """
    x = _matriz_aleatoria()
    referencia, candidatos = x[0], x[1:]
    identidade = np.eye(x.shape[1])
    np.testing.assert_allclose(
        distancias_mahalanobis(referencia, candidatos, identidade),
        distancias_euclidianas(referencia, candidatos),
        rtol=0,
        atol=0,
    )


def test_euclidiana_e_a_raiz_da_soma_dos_quadrados() -> None:
    """Conta independente da implementação, escrita aqui, para a Euclidiana não ser tautologia."""
    referencia = np.array([0.0, 0.0, 0.0])
    candidatos = np.array([[3.0, 4.0, 0.0], [1.0, 1.0, 1.0]])
    np.testing.assert_allclose(distancias_euclidianas(referencia, candidatos), [5.0, np.sqrt(3.0)])


def test_distancia_e_simetrica_e_zero_contra_si_mesma() -> None:
    """Propriedades de métrica: `d(u, u) = 0` e `d(u, v) = d(v, u)`."""
    x = _matriz_aleatoria()
    sigma = ledoit_wolf(x).sigma
    inversa = inverter(sigma)
    u, v = x[3], x[9]
    assert distancias_mahalanobis(u, u.reshape(1, -1), inversa)[0] == pytest.approx(0.0)
    ida = distancias_mahalanobis(u, v.reshape(1, -1), inversa)[0]
    volta = distancias_mahalanobis(v, u.reshape(1, -1), inversa)[0]
    assert ida == pytest.approx(volta)


def test_ledoit_wolf_tem_intensidade_entre_zero_e_um() -> None:
    """`rho` é uma intensidade de encolhimento: fora de [0, 1] não é Ledoit-Wolf."""
    for semente in range(5):
        resultado = ledoit_wolf(_matriz_aleatoria(semente=semente))
        assert 0.0 <= resultado.intensidade <= 1.0


def test_ledoit_wolf_formula_fechada_bate_com_o_laco_explicito() -> None:
    """A identidade que tira o laço sobre `k` do estimador vale numericamente.

    `sum_k ||x_k x_k' - S||_F^2 = sum_k |x_k|^4 - n ||S||_F^2`. O módulo usa o lado direito (duas
    linhas de numpy); aqui calculamos o lado esquerdo com o laço, e os dois têm de bater.
    """
    x = _matriz_aleatoria()
    n, p = x.shape
    centrada = x - x.mean(axis=0)
    amostral = centrada.T @ centrada / n
    laco = sum(
        float((((linha.reshape(-1, 1) @ linha.reshape(1, -1)) - amostral) ** 2).sum())
        for linha in centrada
    )
    fechada = float((((centrada**2).sum(axis=1)) ** 2).sum()) - n * float((amostral**2).sum())
    assert laco == pytest.approx(fechada, rel=1e-12)

    # e, com isso, o `rho` que o módulo publica é o da definição
    mu = float(np.trace(amostral)) / p
    d2 = float(((amostral - mu * np.eye(p)) ** 2).sum())
    esperado = min(max(laco / n**2, 0.0), d2) / d2
    assert ledoit_wolf(x).intensidade == pytest.approx(esperado, rel=1e-12)


def test_shrinkage_torna_matriz_singular_inversivel() -> None:
    """Matriz com coluna repetida: a amostral **não** inverte; a encolhida inverte (CA-084).

    É o teste que justifica o shrinkage em vez de uma explicação na docstring: a covariância de
    um painel 83×5 com features correlacionadas pode ser numericamente singular, e aí a
    Mahalanobis simplesmente não existe.
    """
    x = _matriz_aleatoria(n=12, p=4)
    x[:, 3] = x[:, 1]  # colinearidade perfeita
    amostral = covariancia_amostral(x)
    assert np.linalg.matrix_rank(amostral) < amostral.shape[0]
    with pytest.raises(np.linalg.LinAlgError):
        np.linalg.cholesky(amostral)

    resultado = ledoit_wolf(x)
    assert resultado.intensidade > 0
    inversa = inverter(resultado.sigma)
    np.testing.assert_allclose(resultado.sigma @ inversa, np.eye(resultado.p), rtol=1e-8, atol=1e-8)
    assert resultado.cond_encolhida < resultado.cond_amostral


def test_covariancia_amostral_crua_nao_e_usada_pela_mahalanobis() -> None:
    """**Negativo de CA-084:** usar a amostral crua muda a distância, e o módulo não a usa.

    `covariancia_amostral` existe só para este teste. Se a produção passar a usá-la, as
    distâncias do acervo mudam e a seção D (que recalcula com a encolhida) quebra.
    """
    x = _matriz_aleatoria()
    encolhida = ledoit_wolf(x)
    assert encolhida.intensidade > 0
    crua = covariancia_amostral(x)
    com_crua = distancias_mahalanobis(x[0], x[1:], inverter(crua))
    com_shrinkage = distancias_mahalanobis(x[0], x[1:], inverter(encolhida.sigma))
    assert not np.allclose(com_crua, com_shrinkage)
    fonte = Path(modulo.__file__ or "").read_text(encoding="utf-8")
    assert (
        "covariancia_amostral("
        not in fonte.split("def covariancia_amostral", 1)[1].split("def ledoit_wolf", 1)[0]
    ), "a amostral crua não pode ser chamada no caminho de produção"


def test_shrinkage_de_matriz_ja_isotropica_nao_encolhe() -> None:
    """Se `S` já é múltipla da identidade, o alvo **é** `S` e não há nada a encolher."""
    x = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])
    resultado = ledoit_wolf(x)
    np.testing.assert_allclose(resultado.sigma, covariancia_amostral(x), rtol=1e-12, atol=1e-12)


def test_shrinkage_recusa_amostra_de_uma_observacao() -> None:
    """Com n = 1 não há covariância: erro nomeado, nunca uma matriz de zeros."""
    with pytest.raises(FeaturesInsuficientes):
        ledoit_wolf(np.ones((1, 3)))


def test_inverter_recusa_matriz_nao_definida_positiva() -> None:
    """Covariância degenerada levanta `CovarianciaSingular`, não `LinAlgError` cru."""
    with pytest.raises(CovarianciaSingular):
        inverter(np.array([[1.0, 2.0], [2.0, 1.0]]))


def _matriz_de_quarters(valores: dict[str, list[float]]) -> pd.DataFrame:
    """Quadro `trimestre × feature` sintético, com índice de trimestre de verdade."""
    quarters = janela()[: len(next(iter(valores.values())))]
    return pd.DataFrame(valores, index=list(quarters))


def test_padronizar_na_amostra_completa_da_media_zero_e_desvio_um() -> None:
    """z-score é z-score: média 0 e desvio amostral 1 na janela de estimação."""
    matriz = _matriz_de_quarters({"a": [1.0, 2.0, 3.0, 4.0], "b": [10.0, 0.0, -10.0, 5.0]})
    z, parametros = padronizar(matriz, ate=None)
    assert z.mean().abs().max() == pytest.approx(0.0, abs=1e-12)
    assert z.std(ddof=1).sub(1.0).abs().max() == pytest.approx(0.0, abs=1e-12)
    assert parametros["a"]["n"] == 4


def test_padronizar_expanding_nao_usa_o_futuro() -> None:
    """**O teste de look-ahead.** Mexer em `T+1` não muda o z-score de `T`.

    Metodologia §5.1 e Anti-SPEC §10.2.7: na variante `somente_passado` a média e o desvio saem
    só do que se conhecia em `T`. Aqui o valor de `T+1` é multiplicado por 100 e o z de `T` tem
    de sair **idêntico ao bit** — enquanto o da amostra completa muda (o controle do teste).
    """
    original = _matriz_de_quarters({"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [2.0, 1.0, 0.0, 3.0, 9.0]})
    alterada = original.copy()
    alterada.iloc[3] = alterada.iloc[3] * 100.0

    corte = original.index[2]
    z_antes, _ = padronizar(original, ate=corte)
    z_depois, _ = padronizar(alterada, ate=corte)
    for coluna in original.columns:
        assert z_antes.loc[corte, coluna] == z_depois.loc[corte, coluna]

    completa_antes, _ = padronizar(original, ate=None)
    completa_depois, _ = padronizar(alterada, ate=None)
    assert completa_antes.loc[corte, "a"] != completa_depois.loc[corte, "a"]


def test_padronizar_recusa_feature_constante() -> None:
    """Desvio zero é 0/0: feature constante não separa momento nenhum e levanta."""
    matriz = _matriz_de_quarters({"a": [1.0, 1.0, 1.0, 1.0], "b": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(FeaturesInsuficientes):
        padronizar(matriz, ate=None)


def test_padronizar_recusa_janela_de_uma_observacao() -> None:
    """Com 1 observação até `T` não existe desvio amostral."""
    matriz = _matriz_de_quarters({"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]})
    with pytest.raises(FeaturesInsuficientes):
        padronizar(matriz, ate=matriz.index[0])


# ─────────────────────────────────────────────────────────────────────────────
# Seção B — busca de vizinhos (CA-085, CA-087)
# ─────────────────────────────────────────────────────────────────────────────


def test_exclui_o_proprio_trimestre_e_os_dois_adjacentes() -> None:
    """CA-085: `T`, `T-1` e `T-2` (e, por simetria, `T+1`/`T+2`) não entram no ranking.

    As distâncias são montadas de propósito **crescentes a partir do próprio `T`**: sem a
    exclusão, os 3 primeiros colocados seriam exatamente os trimestres vizinhos no tempo.
    """
    candidatos = ["2019Q1", "2019Q2", "2019Q3", "2019Q4", "2020Q1", "2020Q2", "2021Q4"]
    distancias = np.array([0.6, 0.5, 0.1, 0.0, 0.2, 0.3, 0.9])
    vizinhos = vizinhos_mais_proximos("2019Q4", candidatos, distancias, k=8)
    encontrados = [v.quarter for v in vizinhos]
    assert "2019Q4" not in encontrados
    for proibido in ("2019Q2", "2019Q3", "2020Q1", "2020Q2"):
        assert proibido not in encontrados, f"{proibido} está a <= 2 trimestres de 2019Q4"
    assert encontrados == ["2019Q1", "2021Q4"]
    assert all(
        distancia_em_trimestres(q, "2019Q4") > N_TRIMESTRES_EXCLUIDOS_VIZINHANCA
        for q in encontrados
    )


def test_desempate_fica_com_o_trimestre_mais_recente() -> None:
    """CA-085: distâncias iguais ao bit → prevalece o mais recente, sempre."""
    candidatos = ["2010Q1", "2014Q1", "2018Q1"]
    distancias = np.array([0.5, 0.5, 0.5])
    vizinhos = vizinhos_mais_proximos("2020Q1", candidatos, distancias, k=3)
    assert [v.quarter for v in vizinhos] == ["2018Q1", "2014Q1", "2010Q1"]
    # e a ordem de entrada não muda nada
    invertidos = vizinhos_mais_proximos("2020Q1", candidatos[::-1], distancias, k=3)
    assert [v.quarter for v in invertidos] == ["2018Q1", "2014Q1", "2010Q1"]


def test_k_maior_que_o_pool_devolve_menos_vizinhos_sem_preencher() -> None:
    """`k = 8` com 3 candidatos elegíveis devolve **3** — e quem chama declara `n < 8`."""
    candidatos = ["2010Q1", "2011Q1", "2012Q1", "2019Q3", "2019Q4"]
    distancias = np.array([0.1, 0.2, 0.3, 0.05, 0.01])
    vizinhos = vizinhos_mais_proximos("2020Q1", candidatos, distancias, k=K_VIZINHOS_PADRAO)
    assert len(vizinhos) == 3 < K_VIZINHOS_PADRAO
    assert [v.rank for v in vizinhos] == [1, 2, 3]


def test_ranks_sao_contiguos_desde_um() -> None:
    """`rank` é posição, não identificador: começa em 1 e não tem buraco."""
    candidatos = [q for q in janela()[:30] if q < "2012Q1"]
    distancias = np.linspace(1.0, 2.0, len(candidatos))
    vizinhos = vizinhos_mais_proximos("2013Q3", candidatos, distancias, k=5)
    assert [v.rank for v in vizinhos] == [1, 2, 3, 4, 5]
    assert [v.distancia for v in vizinhos] == sorted(v.distancia for v in vizinhos)


def test_vizinhos_recusa_distancias_de_tamanho_errado() -> None:
    """Candidato sem distância é bug de chamada, não um vizinho a menos."""
    with pytest.raises(FeaturesInsuficientes):
        vizinhos_mais_proximos("2020Q1", ["2010Q1", "2011Q1"], np.array([0.1]), k=2)


def _matriz_sintetica(n: int = 40) -> pd.DataFrame:
    """`n` trimestres × as 5 features, com estrutura e semente fixa."""
    quarters = list(janela()[:n])
    gerador = np.random.default_rng(11)
    dados = _matriz_aleatoria(n=n, p=len(FEATURES_USADAS), semente=3) + gerador.normal(
        scale=0.01, size=(n, len(FEATURES_USADAS))
    )
    return pd.DataFrame(dados, index=quarters, columns=[f.nome for f in FEATURES_USADAS])


def _rotulos_sinteticos(matriz: pd.DataFrame) -> pd.Series:
    """Um rótulo V1 por trimestre, ciclando os 4 quadrantes, com 2 `INDETERMINADO`."""
    rotulos = [r.value for r in RegimeV1]
    serie = pd.Series(
        {q: rotulos[i % len(rotulos)] for i, q in enumerate(matriz.index)}, dtype="object"
    )
    serie.iloc[5] = None
    serie.iloc[9] = None
    return serie


def test_montar_vizinhos_valida_no_schema_e_cobre_as_quatro_lentes() -> None:
    """A tabela longa sai validada e com as 4 lentes × 2 métricas × 3 `k` (CA-087, CA-089)."""
    matriz = _matriz_sintetica(n=60)  # chega a 2020Q4: a lente pos2016 precisa de ref >= 2017Q1
    completos, faltando = trimestres_com_vetor_completo(matriz)
    assert not faltando
    tabela = montar_vizinhos(
        matriz,
        rotulos=_rotulos_sinteticos(matriz),
        completos=completos,
        pool=completos,
        fonte_versao="sintetico-nf5",
        n_features=len(FEATURES_USADAS),
        features_usadas="|".join(f.nome for f in FEATURES_USADAS),
    )
    RegimeNeighborsV3Schema.validate(tabela, lazy=True)
    assert set(tabela["k_usado"]) == set(K_VIZINHOS_SENSIBILIDADE)
    assert set(tabela["metrica"]) == {m.value for m in MetricaDistancia}
    combinacoes = set(zip(tabela["somente_passado"], tabela["restrito_pos_2016"], strict=True))
    assert combinacoes == {(lente.somente_passado, lente.restrito_pos_2016) for lente in LENTES}
    # o rótulo nulo do vizinho vira INDETERMINADO, nunca um quadrante inventado
    indeterminados = tabela.loc[tabela["regime_v1_neighbor"].isna()]
    assert not indeterminados.empty
    assert set(indeterminados["status_regime_v1_neighbor"]) == {StatusRegimeV1.INDETERMINADO.value}


def test_montar_vizinhos_e_funcao_pura() -> None:
    """Duas chamadas com a mesma entrada dão a mesma tabela — RF-048 na fonte, não no Parquet."""
    matriz = _matriz_sintetica(n=30)
    completos, _ = trimestres_com_vetor_completo(matriz)
    argumentos = {
        "rotulos": _rotulos_sinteticos(matriz),
        "completos": completos,
        "pool": completos,
        "fonte_versao": "sintetico-nf5",
        "n_features": len(FEATURES_USADAS),
        "features_usadas": "a|b|c|d|e",
        "lentes": (Lente(somente_passado=False, restrito_pos_2016=False),),
    }
    primeira = montar_vizinhos(matriz, **argumentos)  # type: ignore[arg-type]
    segunda = montar_vizinhos(matriz, **argumentos)  # type: ignore[arg-type]
    pd.testing.assert_frame_equal(primeira, segunda)


def test_somente_passado_nunca_pega_vizinho_no_futuro() -> None:
    """Na lente `somente_passado` todo vizinho é anterior à referência — sem exceção."""
    matriz = _matriz_sintetica(n=45)
    completos, _ = trimestres_com_vetor_completo(matriz)
    tabela = montar_vizinhos(
        matriz,
        rotulos=_rotulos_sinteticos(matriz),
        completos=completos,
        pool=completos,
        fonte_versao="sintetico-nf5",
        n_features=len(FEATURES_USADAS),
        features_usadas="a|b|c|d|e",
        lentes=(Lente(somente_passado=True, restrito_pos_2016=False),),
    )
    assert not tabela.empty
    futuros = tabela.loc[
        tabela["quarter_neighbor"].map(indice_do_quarter)
        >= tabela["quarter_ref"].map(indice_do_quarter)
    ]
    assert futuros.empty
    # e a referência só existe depois de `MIN_OBS_PADRONIZACAO_EXPANDING` trimestres de história
    primeira = sorted(tabela["quarter_ref"].unique())[0]
    assert completos.index(primeira) >= MIN_OBS_PADRONIZACAO_EXPANDING - 1


def test_projetar_no_contrato_descarta_a_variante_expanding() -> None:
    """A tabela de contrato é só a descritiva: as duas janelas colidiriam na PK dela."""
    matriz = _matriz_sintetica(n=45)
    completos, _ = trimestres_com_vetor_completo(matriz)
    rotulos = _rotulos_sinteticos(matriz)
    com_rotulo = [q for q in completos if rotulos.get(q)]
    tabela = montar_vizinhos(
        matriz,
        rotulos=rotulos,
        completos=completos,
        pool=com_rotulo,
        fonte_versao="sintetico-nf5",
        n_features=len(FEATURES_USADAS),
        features_usadas="a|b|c|d|e",
    )
    contrato = projetar_no_contrato(tabela)
    assert "somente_passado" not in contrato.columns
    assert contrato["regime_v1_neighbor"].notna().all()
    assert len(contrato) < len(tabela)


# ─────────────────────────────────────────────────────────────────────────────
# Seção C — retorno em T+1 (CA-102) e ranking (CA-108/109)
# ─────────────────────────────────────────────────────────────────────────────


def test_quarter_seguinte_anda_um_trimestre_e_para_no_fim_da_janela() -> None:
    """`T+1` é o trimestre seguinte; no último da janela é `None`, nunca um trimestre inventado."""
    assert quarter_seguinte("2006Q1") == "2006Q2"
    assert quarter_seguinte("2019Q4") == "2020Q1"
    assert quarter_seguinte(janela()[-1]) is None
    assert quarter_seguinte("1999Q1") is None


def _retornos_sinteticos() -> pd.DataFrame:
    """Painel mínimo com `ret_excesso_cdi` distinto por trimestre, para a troca T/T+1 doer."""
    linhas = [
        {"quarter": q, "asset_id": ativo, "ret_excesso_cdi": valor}
        for q, valor in (
            ("2010Q1", -0.10),
            ("2010Q2", 0.20),
            ("2014Q3", -0.30),
            ("2014Q4", 0.40),
        )
        for ativo, valor in ((ativo, valor) for ativo in ("IBOV", "IMAB"))
    ]
    return pd.DataFrame(linhas)


def test_retorno_e_medido_no_trimestre_seguinte_ao_vizinho() -> None:
    """**CA-102.** O vizinho é `2010Q1`; o retorno lido é o de `2010Q2`.

    O painel sintético tem sinais opostos em `T` e `T+1` de propósito: se a implementação ler o
    próprio vizinho, a média troca de sinal e o teste cai.
    """
    observado = retornos_em_t_mais_1([Vizinho(1, "2010Q1", 0.5)], _retornos_sinteticos())
    assert set(observado["quarter"]) == {"2010Q2"}
    assert set(observado["quarter_vizinho"]) == {"2010Q1"}
    assert observado["ret_excesso_cdi"].unique().tolist() == [0.20]


def test_vizinho_no_fim_da_janela_nao_contribui_com_retorno() -> None:
    """Sem `T+1` não há retorno: a ausência aparece no `n`, não como retorno do vizinho."""
    observado = retornos_em_t_mais_1([Vizinho(1, janela()[-1], 0.5)], _retornos_sinteticos())
    assert observado.empty


def test_ranking_tem_n_em_toda_linha_e_erro_padrao_pela_formula() -> None:
    """Anti-SPEC §10.2.8 + metodologia §3: `n` em toda célula, média **e** mediana, s/√n."""
    observado = retornos_em_t_mais_1(
        [Vizinho(1, "2010Q1", 0.1), Vizinho(2, "2014Q3", 0.2)], _retornos_sinteticos()
    )
    ranking = ranking_de_ativos(observado)
    assert ranking
    for linha in ranking:
        assert "n" in linha and linha["n"] >= 0
        assert linha["media"] is not None
        assert linha["mediana"] is not None
    ibov = next(linha for linha in ranking if linha["asset_id"] == "IBOV")
    valores = pd.Series([0.20, 0.40])
    assert ibov["n"] == 2
    assert ibov["media"] == pytest.approx(0.30)
    assert ibov["desvio"] == pytest.approx(float(valores.std(ddof=1)))
    assert ibov["erro_padrao"] == pytest.approx(float(valores.std(ddof=1)) / np.sqrt(2))
    assert ibov["hit_ratio_cdi"] == pytest.approx(1.0)


def test_ranking_marca_alerta_e_supressao_pelos_limiares_do_contrato() -> None:
    """CA-108/109: `n < 8` acende alerta, `n < 5` suprime a conclusão — e a linha continua lá."""
    observado = pd.DataFrame(
        {
            "asset_id": ["X"] * 6 + ["Y"] * 3,
            "quarter": [f"2010Q{i % 4 + 1}" for i in range(9)],
            "quarter_vizinho": ["2009Q4"] * 9,
            "ret_excesso_cdi": [0.01] * 6 + [0.02] * 3,
        }
    )
    ranking = {linha["asset_id"]: linha for linha in ranking_de_ativos(observado)}
    assert ranking["X"]["n"] == 6 < N_ALERTA
    assert ranking["X"]["alerta_n_baixo"] is True
    assert ranking["X"]["conclusao_suprimida"] is False
    assert ranking["Y"]["n"] == 3 < N_SUPRESSAO
    assert ranking["Y"]["conclusao_suprimida"] is True
    assert "Y" in ranking, "suprimir a conclusão não é apagar o dado"


def test_ranking_ordena_pela_media_decrescente() -> None:
    """O ranking é um ranking: média maior em cima, e ativo sem retorno não vai para o topo."""
    observado = pd.DataFrame(
        {
            "asset_id": ["BAIXO", "ALTO", "VAZIO"],
            "quarter": ["2010Q2", "2010Q2", "2010Q2"],
            "quarter_vizinho": ["2010Q1"] * 3,
            "ret_excesso_cdi": [-0.05, 0.07, None],
        }
    )
    ranking = ranking_de_ativos(observado)
    assert [linha["asset_id"] for linha in ranking] == ["ALTO", "BAIXO", "VAZIO"]
    assert ranking[-1]["n"] == 0
    assert ranking[-1]["conclusao_suprimida"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Seção C' — rótulo V1 de anotação, features e versão
# ─────────────────────────────────────────────────────────────────────────────


def _macro_sintetico(gap: list[float | None], aceleracao: list[float | None]) -> pd.DataFrame:
    quarters = list(janela()[: len(gap)])
    return pd.DataFrame(
        {"ibcbr_gap": gap, "ipca_12m_delta": aceleracao},
        index=quarters,
    )


def test_rotulo_v1_cobre_os_quatro_quadrantes_de_adr_001() -> None:
    """ADR-001 §5: os 4 rótulos saem dos sinais de `g` e `pi`, nesta combinação e não outra."""
    macro = _macro_sintetico([1.0, 1.0, -1.0, -1.0], [-1.0, 1.0, 1.0, -1.0])
    rotulos = rotulos_v1_de_anotacao(macro)
    assert list(rotulos) == [
        RegimeV1.RECUPERACAO.value,
        RegimeV1.EXPANSAO_INFL.value,
        RegimeV1.ESTAGFLACAO.value,
        RegimeV1.DESACELERACAO.value,
    ]


def test_rotulo_v1_com_eixo_exatamente_zero_herda_o_trimestre_anterior() -> None:
    """CA-079: empate exato herda o sinal de `T-1` — nunca cai num quadrante por acaso."""
    macro = _macro_sintetico([1.0, 0.0], [1.0, 0.0])
    rotulos = rotulos_v1_de_anotacao(macro)
    assert rotulos.iloc[1] == rotulos.iloc[0] == RegimeV1.EXPANSAO_INFL.value


def test_rotulo_v1_sem_gap_fica_indeterminado() -> None:
    """D-m: `ibcbr_gap` nulo → sem quadrante. `None`, nunca um rótulo plausível."""
    macro = _macro_sintetico([None, 1.0], [1.0, 1.0])
    rotulos = rotulos_v1_de_anotacao(macro)
    assert rotulos.iloc[0] is None
    assert rotulos.iloc[1] == RegimeV1.EXPANSAO_INFL.value


def test_features_declaradas_tem_entre_tres_e_seis_e_nomes_unicos() -> None:
    """`n_features` ∈ [3, 6] é contrato (`RegimeNeighborsSchema`), e CA-086 exige a declaração."""
    assert 3 <= len(FEATURES_USADAS) <= 6
    nomes = [f.nome for f in FEATURES_USADAS]
    assert len(set(nomes)) == len(nomes)
    assert FEATURES_DESCARTADAS, "feature cortada tem de ter motivo escrito, não ausência muda"
    for _nome, motivo in FEATURES_DESCARTADAS:
        assert len(motivo) > 40
    for feature in FEATURES_USADAS:
        if feature.substitui is not None:
            assert feature.motivo_da_substituicao, f"{feature.nome} substitui sem motivo escrito"


def test_matriz_de_features_recusa_menos_de_tres_e_mais_de_seis() -> None:
    """O piso de 3 e o teto de 6 são do contrato, e o módulo não os contorna."""
    macro = _macro_sintetico([1.0, 2.0], [1.0, 2.0])
    inclinacao = pd.Series({q: 1.0 for q in macro.index})
    with pytest.raises(FeaturesInsuficientes):
        matriz_de_features(macro, inclinacao=inclinacao, features=FEATURES_USADAS[:2])
    with pytest.raises(FeaturesInsuficientes):
        matriz_de_features(
            macro, inclinacao=inclinacao, features=(*FEATURES_USADAS, *FEATURES_USADAS[:2])
        )


def test_fonte_versao_declara_o_numero_de_features() -> None:
    """CA-086 pede o corte declarado **no `fonte_versao`** — não só no relatório."""
    assert fonte_versao_declarada("abc", n_features=5).endswith("-nf5")
    assert fonte_versao_declarada("abc", n_features=5) != fonte_versao_declarada(
        "abc", n_features=6
    )


def test_especificacao_nao_esta_congelada_e_o_build_avisa() -> None:
    """CA-090: ADR-001 em Proposta ⇒ `especificacao_congelada=False` e aviso no build."""
    assert ESPECIFICACAO_CONGELADA is False
    fonte = Path(modulo.__file__ or "").read_text(encoding="utf-8")
    assert "CA-090" in fonte
    assert "_log.warning" in fonte


def test_o_modulo_de_producao_nao_le_o_relogio() -> None:
    """Guarda de idempotência (RF-048/CA-121): nada aqui lê o relógio.

    Uma leitura de relógio faria o Parquet mudar sem o dado mudar — e só se perceberia no dia
    seguinte, depois de o número ter ido ao Comitê.
    """
    fonte = Path(modulo.__file__ or "").read_text(encoding="utf-8")
    for proibido in (".now(", ".today(", "time.time("):
        assert proibido not in fonte, f"{proibido} em regimes_v3.py quebra a idempotência"


def test_sequencias_do_contrato_sao_tuplas() -> None:
    """Ordem e imutabilidade fazem parte: `FEATURES_USADAS` e `LENTES` são tuplas."""
    assert isinstance(FEATURES_USADAS, tuple)
    assert isinstance(FEATURES_DESCARTADAS, tuple)
    assert isinstance(LENTES, tuple)
    assert isinstance(janela(), tuple)


# ─────────────────────────────────────────────────────────────────────────────
# Seção D — acervo real (`data/canonical/`). É a cobertura de integração.
# ─────────────────────────────────────────────────────────────────────────────


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


def acervo_disponivel() -> bool:
    """Os Parquets de que a seção D depende existem nesta máquina?"""
    return all(
        caminho_canonical(nome).is_file()
        for nome in (NOME_NEIGHBORS_V3, NOME_NEIGHBORS, NOME_MACRO, NOME_RETORNOS)
    )


pulo_do_acervo = pytest.mark.skipif(
    ignorar_data_real() or not acervo_disponivel(),
    reason=(
        "seção D roda sobre data/canonical/. Ligue com "
        "`uv run python -m apps.pipeline.canonical.regimes_v3 --offline` e "
        f"{VAR_IGNORAR_DATA} desligada."
    ),
)


@pytest.fixture(scope="module")
def acervo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """`(v3, contrato, macro, retornos)` do acervo real, sem recalcular nada."""
    return (
        pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3)),
        pd.read_parquet(caminho_canonical(NOME_NEIGHBORS)),
        pd.read_parquet(caminho_canonical(NOME_MACRO)),
        pd.read_parquet(caminho_canonical(NOME_RETORNOS)),
    )


@pulo_do_acervo
def test_acervo_valida_nos_dois_schemas(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Os dois Parquets publicados passam pelo portão pandera deles (RF-026/CA-089)."""
    from packages.shared.schemas import RegimeNeighborsSchema

    v3, contrato, _, _ = acervo
    RegimeNeighborsV3Schema.validate(v3, lazy=True)
    RegimeNeighborsSchema.validate(contrato, lazy=True)
    assert len(v3) > len(contrato)


@pulo_do_acervo
def test_acervo_declara_cinco_features_em_toda_linha(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """CA-086: o corte de feature está **no dado**, em `n_features` e em `features_usadas`."""
    v3, contrato, _, _ = acervo
    assert set(v3["n_features"]) == {len(FEATURES_USADAS)}
    assert set(contrato["n_features"]) == {len(FEATURES_USADAS)}
    declarada = set(v3["features_usadas"])
    assert len(declarada) == 1
    assert declarada == {"|".join(f.nome for f in FEATURES_USADAS)}
    assert all("-nf5" in str(v) for v in v3["fonte_versao"].unique())


@pulo_do_acervo
def test_acervo_oito_vizinhos_do_trimestre_do_comite(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """O entregável: `2026Q3` tem 8 vizinhos na lente principal, com `T+1` de cada (CA-101/102)."""
    v3, _, _, _ = acervo
    fatia = v3.loc[
        (v3["quarter_ref"] == QUARTER_DO_COMITE)
        & (v3["metrica"] == MetricaDistancia.MAHALANOBIS.value)
        & (v3["k_usado"] == K_VIZINHOS_PADRAO)
        & (~v3["somente_passado"].astype(bool))
        & (~v3["restrito_pos_2016"].astype(bool))
    ].sort_values("rank")
    assert len(fatia) == K_VIZINHOS_PADRAO
    assert list(fatia["rank"]) == list(range(1, K_VIZINHOS_PADRAO + 1))
    assert fatia["distancia"].is_monotonic_increasing
    assert not fatia["alerta_n_baixo"].any()
    for _, linha in fatia.iterrows():
        assert quarter_seguinte(str(linha["quarter_neighbor"])) == str(linha["quarter_t_mais_1"])
        assert (
            distancia_em_trimestres(str(linha["quarter_neighbor"]), QUARTER_DO_COMITE)
            > N_TRIMESTRES_EXCLUIDOS_VIZINHANCA
        )


@pulo_do_acervo
def test_acervo_distancia_do_vizinho_mais_proximo_recalculada_em_numpy_puro(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**A verificação à mão.** A distância do rank 1 de `2026Q3`, refeita deste arquivo.

    O recálculo não importa nada do módulo além da leitura da inclinação (que vem de
    `raw_series`): z-score, shrinkage de Ledoit-Wolf e forma quadrática são reescritos aqui, em
    numpy, a partir de `macro_quarterly.parquet`. Se o módulo e esta conta discordarem em mais de
    `1e-10`, o número publicado está errado.
    """
    v3, _, macro, _ = acervo
    matriz = pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3))  # só para falhar cedo se vazio
    assert not matriz.empty

    indexado = macro.set_index("quarter").sort_index()
    inclinacao = modulo.inclinacao_real_5a_3a(
        pd.read_parquet(caminho_canonical("raw_series.parquet")),
        pd.read_parquet(caminho_canonical("series_catalog.parquet")),
        calendario=__import__(
            "apps.pipeline.extract.calendario_anbima", fromlist=["Calendario"]
        ).Calendario.do_parquet(),
        fonte_versao="conferencia",
    )
    colunas = {
        "z_crescimento_esperado": indexado["focus_pib_ano"],
        "z_ipca_12m_delta": indexado["ipca_12m_delta"],
        "z_juro_real_exante": indexado["juro_real_exante"],
        "z_inclinacao_real_5a_3a": inclinacao.reindex(indexado.index),
        "z_usdbrl_var_12m": indexado["usdbrl_var_12m"],
    }
    bruto = pd.DataFrame(colunas, index=indexado.index).astype("float64")
    cheio = bruto.loc[bruto.notna().all(axis=1)]

    # z-score na amostra completa, à mão
    z = (cheio - cheio.mean()) / cheio.std(ddof=1)
    x = z.to_numpy()
    n, p = x.shape
    centrada = x - x.mean(axis=0)
    amostral = centrada.T @ centrada / n
    mu = float(np.trace(amostral)) / p
    d2 = float(((amostral - mu * np.eye(p)) ** 2).sum())
    b2 = float((((centrada**2).sum(axis=1)) ** 2).sum()) / n**2 - float((amostral**2).sum()) / n
    rho = min(max(b2, 0.0), d2) / d2
    sigma = rho * mu * np.eye(p) + (1.0 - rho) * amostral
    inversa = np.linalg.inv(sigma)

    fatia = v3.loc[
        (v3["quarter_ref"] == QUARTER_DO_COMITE)
        & (v3["metrica"] == MetricaDistancia.MAHALANOBIS.value)
        & (v3["k_usado"] == K_VIZINHOS_PADRAO)
        & (~v3["somente_passado"].astype(bool))
        & (~v3["restrito_pos_2016"].astype(bool))
    ].sort_values("rank")
    for _, linha in fatia.iterrows():
        delta = (
            z.loc[str(linha["quarter_neighbor"])].to_numpy() - z.loc[QUARTER_DO_COMITE].to_numpy()
        )
        a_mao = float(np.sqrt(delta @ inversa @ delta))
        assert a_mao == pytest.approx(float(linha["distancia"]), abs=1e-10), (
            f"rank {linha['rank']} ({linha['quarter_neighbor']}): publicado "
            f"{linha['distancia']}, à mão {a_mao}"
        )


@pulo_do_acervo
def test_acervo_cdi_tem_excesso_nulo_no_ranking(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Sanity check da métrica: o excesso do CDI **sobre o CDI** é 0 em todo trimestre."""
    v3, _, _, retornos = acervo
    fatia = v3.loc[
        (v3["quarter_ref"] == QUARTER_DO_COMITE)
        & (v3["metrica"] == MetricaDistancia.MAHALANOBIS.value)
        & (v3["k_usado"] == K_VIZINHOS_PADRAO)
        & (~v3["somente_passado"].astype(bool))
        & (~v3["restrito_pos_2016"].astype(bool))
    ].sort_values("rank")
    vizinhos = [
        Vizinho(int(r["rank"]), str(r["quarter_neighbor"]), float(r["distancia"]))
        for _, r in fatia.iterrows()
    ]
    ranking = {
        linha["asset_id"]: linha
        for linha in ranking_de_ativos(retornos_em_t_mais_1(vizinhos, retornos))
    }
    assert ranking["CDI"]["media"] == pytest.approx(0.0, abs=1e-12)
    assert ranking["CDI"]["n"] == K_VIZINHOS_PADRAO


@pulo_do_acervo
def test_acervo_nenhum_vizinho_do_passado_veio_do_futuro(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Anti-look-ahead no artefato: `somente_passado=True` não tem uma única linha futura."""
    v3, _, _, _ = acervo
    passado = v3.loc[v3["somente_passado"].astype(bool)]
    assert not passado.empty
    assert (
        passado["quarter_neighbor"].map(indice_do_quarter)
        < passado["quarter_ref"].map(indice_do_quarter)
    ).all()
    assert set(passado["janela_padronizacao"]) == {"expanding_ate_T"}


@pulo_do_acervo
def test_acervo_sem_vetor_completo_fica_fora_da_lente(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Trimestre sem o vetor cheio **não** entra — nem como referência, nem como vizinho."""
    import json

    v3, _, _, _ = acervo
    relatorio = json.loads(
        caminho_canonical("relatorio_regimes_v3.json").read_text(encoding="utf-8")
    )
    sem_v3 = {bloco["quarter"] for bloco in relatorio["cobertura"]["sem_v3_por_falta_de_feature"]}
    assert sem_v3, "o relatório tem de nomear quem ficou de fora"
    assert sem_v3.isdisjoint(set(v3["quarter_ref"]))
    assert sem_v3.isdisjoint(set(v3["quarter_neighbor"]))
    for bloco in relatorio["cobertura"]["sem_v3_por_falta_de_feature"]:
        assert bloco["features_ausentes"], "ficar de fora tem de ter a feature nomeada"
