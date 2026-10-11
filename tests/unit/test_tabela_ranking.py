"""F-024 — testes da tabela "regime atual → ranking de ativos" + concordância entre lentes.

**RF-034 / CA-098, CA-099 · RF-037 / CA-103 · CA-090 como gate.**

Organização, e o motivo de cada bloco:

| Bloco | O que trava | CA |
|---|---|---|
| 1 | formatação pt-BR determinística e os **símbolos de `n`** (`†`/`‡`) | CA-099, §10.2.8 |
| 2 | o bloco A: as **3** respostas, o fallback **declarado**, nada inventado | CA-098 |
| 3 | o bloco B: ordem por `excesso_cdi`, célula vazia no fim, `n` em toda linha | CA-098/099 |
| 4 | **Spearman e postos** com casos de valor conhecido (fórmula fechada) | CA-103 |
| 5 | o bloco C: Jaccard por par, 1 linha por lente, divergência **reportada** | CA-103 |
| 6 | a **distribuição** `somente_passado` × descritiva — o vácuo do Jaccard 1,0 | QA P1-2 |
| 7 | o Markdown: 3 respostas, **nada preditivo**, determinístico, gate | CA-090, §10.2.10 |
| 8 | **acervo real** `data/canonical/` — números idênticos aos de F-022/F-021 | todos |

Os blocos 1-7 rodam sobre **fixtures sintéticas**, nomeadas como tal (Anti-SPEC §10.1.2), e
**nunca pulam**: rodam no CI sem `data/`. O bloco 8 segue o padrão `Acervo` de
`test_figura_timeline_regimes.py §7` — entra por acréscimo quando os Parquets existem em disco e
é desligado por `LDC_IGNORAR_DATA=1`.

**Nenhum número sintético imita dado real.** Os valores das fixtures são redondos de propósito
(`+5%`, `+3%`, `−2%`) para que qualquer confusão entre sintético e acervo seja óbvia na leitura.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from apps.analysis.tabelas import ranking_regime_atual as T
from apps.pipeline.canonical.metricas_regime import (
    LENTE_V1,
    LENTE_V3,
    TABELA_ASOF,
    TABELA_PRINCIPAL,
)
from apps.pipeline.canonical.regimes_v1 import Materializacao
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.asset_returns_quarterly import ASSET_IDS_VALIDOS
from packages.shared.schemas.regimes import (
    K_VIZINHOS_PADRAO,
    N_ALERTA,
    N_SUPRESSAO,
    MetricaDistancia,
    MotivoIndeterminado,
    RegimeV1,
    StatusRegimeV1,
)

COMO_GERAR = "rode `uv run python -m apps.analysis.tabelas.ranking_regime_atual`"
VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

QUARTER = "2026Q3"
FALLBACK = "2026Q2"
FONTE_VERSAO_SINTETICA = "a" * 64
VERSAO_SINTETICA = "b" * 64

#: Os 24 primeiros ids do contrato. `ASSET_IDS_VALIDOS` tem **32** nomes válidos, mas
#: `asset_returns_quarterly` só tem série para 24 (F-017) — e 24 é a grade que o bloco B
#: exige completa (CA-095 em espírito). O recorte é por `[:24]` de propósito: se a grade real
#: mudar, o teste que compara com o acervo é que denuncia, não este.
ATIVOS = ASSET_IDS_VALIDOS[: T.N_ATIVOS_ESPERADO]


# ─────────────────────────────────────────────────────────────────────────────
# Ajudantes sintéticos — dado nomeado como sintético (Anti-SPEC §10.1.2)
# ─────────────────────────────────────────────────────────────────────────────


def metricas_sinteticas(
    *,
    lente: str,
    regime: str,
    n_por_ativo: dict[str, int] | None = None,
    excesso_por_ativo: dict[str, float | None] | None = None,
    n_padrao: int = 16,
) -> pd.DataFrame:
    """Uma tabela no formato de `regime_asset_metrics`, 24 ativos. **Sintética.**

    O excesso padrão é decrescente e **redondo** (`+2,3%`, `+2,2%`, …), então a ordenação
    esperada é a ordem de `ATIVOS` e qualquer embaralhamento aparece como diferença de posição.
    """
    n_por_ativo = n_por_ativo or {}
    excesso_por_ativo = excesso_por_ativo or {}
    linhas: list[dict[str, Any]] = []
    for indice, ativo in enumerate(ATIVOS):
        n = n_por_ativo.get(ativo, n_padrao)
        excesso = excesso_por_ativo.get(ativo, round(0.024 - indice * 0.001, 4))
        linhas.append(
            {
                "lente": lente,
                "regime": regime,
                "asset_id": ativo,
                "n_obs": n,
                "ret_medio": None if excesso is None else excesso + 0.03,
                "ret_mediana": None if excesso is None else excesso + 0.02,
                "ret_desvio": 0.08,
                "erro_padrao_media": None if n < 2 else 0.08 / math.sqrt(n),
                "hit_ratio": 0.5,
                "excesso_cdi": excesso,
                "hit_ratio_cdi": 0.5,
                "ret_real": None if excesso is None else excesso - 0.01,
                "sharpe_tri": 0.25,
                "pior_tri": -0.1,
                "pior_tri_quarter": "2020Q1",
                "melhor_tri": 0.2,
                "melhor_tri_quarter": "2009Q2",
                "beta_ibov": 1.0,
                "alerta_n_baixo": n < N_ALERTA,
                "conclusao_suprimida": n < N_SUPRESSAO,
                "data_inicio_serie": pd.Timestamp("2006-01-02"),
                "fonte_versao": FONTE_VERSAO_SINTETICA,
            }
        )
    return pd.DataFrame(linhas)


def regimes_sinteticos(*, rotulo_do_quarter: str | None, asof: bool = False) -> pd.DataFrame:
    """Uma tabela no formato de `regimes_v1`, 4 trimestres. **Sintética.**

    `rotulo_do_quarter=None` reproduz **D-m**: `2026Q3` sem quadrante, com `status` e `motivo`
    preenchidos — nunca um quadrante estimado no lugar.
    """
    quarters = ["2025Q4", "2026Q1", FALLBACK, QUARTER]
    rotulos: list[str | None] = [
        RegimeV1.RECUPERACAO.value,
        RegimeV1.EXPANSAO_INFL.value,
        RegimeV1.ESTAGFLACAO.value,
        rotulo_do_quarter,
    ]
    if asof:
        rotulos[0] = RegimeV1.DESACELERACAO.value
    return pd.DataFrame(
        {
            "quarter": quarters,
            "regime_v1": rotulos,
            "status_regime_v1": [
                StatusRegimeV1.INDETERMINADO.value
                if r is None
                else StatusRegimeV1.CLASSIFICADO.value
                for r in rotulos
            ],
            "motivo_indeterminado": [
                MotivoIndeterminado.GAP_AUSENTE.value if r is None else None for r in rotulos
            ],
            "g_score": [1.0, 1.5, -0.5, None if rotulo_do_quarter is None else -1.15],
            "pi_score": [0.5, 0.6, 0.2, None if rotulo_do_quarter is None else -0.5],
            "n_obs_regime_v1": [13, 19, 16, 13],
            "lag_adjusted": [asof] * 4,
        }
    )


def neighbors_sinteticos(
    *,
    por_referencia: dict[str, list[str]] | None = None,
    somente_passado: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Uma tabela no formato de `regime_neighbors_v3`. **Sintética.**

    `por_referencia` é a variante descritiva, `somente_passado` a sem look-ahead. As duas são
    comparadas como **conjuntos** no bloco 6, igual ao que o módulo faz.
    """
    descritiva = por_referencia or {
        QUARTER: ["2006Q3", "2006Q4", "2006Q1", "2024Q3", "2014Q4", "2007Q1", "2024Q2", "2014Q3"]
    }
    passado = somente_passado or {}
    linhas: list[dict[str, Any]] = []
    for apenas_passado, mapa in ((False, descritiva), (True, passado)):
        for quarter_ref, vizinhos in mapa.items():
            for rank, vizinho in enumerate(vizinhos, start=1):
                periodo = pd.Period(vizinho, freq="Q") + 1
                linhas.append(
                    {
                        "quarter_ref": quarter_ref,
                        "rank": rank,
                        "quarter_neighbor": vizinho,
                        "distancia": 0.9 + rank * 0.1,
                        "metrica": MetricaDistancia.MAHALANOBIS.value,
                        "k_usado": K_VIZINHOS_PADRAO,
                        "somente_passado": apenas_passado,
                        "restrito_pos_2016": False,
                        "quarter_t_mais_1": f"{periodo.year}Q{periodo.quarter}",
                        "regime_v1_neighbor": None if rank <= 3 else RegimeV1.EXPANSAO_INFL.value,
                        "status_regime_v1_neighbor": (
                            StatusRegimeV1.INDETERMINADO.value
                            if rank <= 3
                            else StatusRegimeV1.CLASSIFICADO.value
                        ),
                    }
                )
    return pd.DataFrame(linhas)


#: A variante sem look-ahead do cenário: **a mesma** lista do trimestre do Comitê (o caso
#: "vácuo" de P1-2) — o módulo tem de dizer que esse 1,0 não prova robustez.
VIZINHOS_SOMENTE_PASSADO: dict[str, list[str]] = {
    QUARTER: ["2014Q3", "2024Q2", "2007Q1", "2014Q4", "2024Q3", "2006Q1", "2006Q4", "2006Q3"]
}


def cenario_sintetico() -> dict[str, Any]:
    """O cenário completo do Comitê, em sintético: `2026Q3` indeterminado na `revised`.

    É o caso que de fato vai ao slide (**D-m** + **CA-074**), e é o único em que as três lentes
    apontam para células diferentes — logo o único em que a página pode errar de verdade.
    """
    revised = regimes_sinteticos(rotulo_do_quarter=None)
    asof = regimes_sinteticos(rotulo_do_quarter=RegimeV1.DESACELERACAO.value, asof=True)
    vizinhos_df = neighbors_sinteticos(somente_passado=VIZINHOS_SOMENTE_PASSADO)
    vizinhos = T.vizinhos_do_quarter(vizinhos_df, quarter=QUARTER)
    respostas = T.respostas_do_regime_atual(
        regimes_revised=revised,
        regimes_asof=asof,
        vizinhos=vizinhos,
        quarter=QUARTER,
    )
    lentes = T.lentes_da_pagina(respostas)
    metricas = {
        TABELA_PRINCIPAL.rotulo: pd.concat(
            [
                metricas_sinteticas(lente=LENTE_V1, regime=RegimeV1.ESTAGFLACAO.value),
                metricas_sinteticas(
                    lente=LENTE_V3,
                    regime=T.nome_do_regime_v3(QUARTER),
                    n_padrao=8,
                    n_por_ativo={ATIVOS[-1]: 4, ATIVOS[-2]: 6},
                    excesso_por_ativo={ATIVOS[0]: -0.01, ATIVOS[1]: 0.05},
                ),
            ],
            ignore_index=True,
        ),
        TABELA_ASOF.rotulo: metricas_sinteticas(
            lente=LENTE_V1, regime=RegimeV1.DESACELERACAO.value, n_padrao=13
        ),
    }
    ranking = T.tabela_de_ranking(metricas=metricas, lentes=lentes, versao=VERSAO_SINTETICA)
    bloco_c = T.concordancia(ranking=ranking, lentes=lentes, neighbors=vizinhos_df)
    return {
        "revised": revised,
        "asof": asof,
        "neighbors": vizinhos_df,
        "vizinhos": vizinhos,
        "respostas": respostas,
        "lentes": lentes,
        "metricas": metricas,
        "ranking": ranking,
        "bloco_c": bloco_c,
    }


@pytest.fixture(scope="module")
def cenario() -> dict[str, Any]:
    """O cenário sintético, montado uma vez — as funções são puras, nada muda entre testes."""
    return cenario_sintetico()


def markdown_do_cenario(cenario: dict[str, Any], *, congelada: bool = False) -> str:
    """A página do cenário sintético, com hashes sintéticos."""
    return T.markdown_da_pagina(
        respostas=cenario["respostas"],
        vizinhos=cenario["vizinhos"],
        ranking=cenario["ranking"],
        lentes=cenario["lentes"],
        bloco_c=cenario["bloco_c"],
        versao=VERSAO_SINTETICA,
        hashes={"sintetico.parquet": FONTE_VERSAO_SINTETICA},
        congelada=congelada,
        status_adr="PROPOSTA",
        pct_de_troca=1 / 3,
        quarter=QUARTER,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1 — Formatação pt-BR e os símbolos de `n`
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (0.036012559549817615, "+3,60%"),
        (-0.069, "-6,90%"),
        (0.0, "+0,00%"),
        (None, T.AUSENTE),
        (float("nan"), T.AUSENTE),
    ],
)
def test_pct_formata_em_pt_br_com_sinal_explicito(valor: float | None, esperado: str) -> None:
    """Separador decimal é vírgula, sinal é explícito e ausência é `—`, nunca `0`."""
    assert T.pct(valor) == esperado


def test_pp_e_num_nao_dependem_de_locale() -> None:
    """Nenhum `locale`: a formatação é a mesma em qualquer máquina (determinismo)."""
    assert T.pp(0.0206) == "2,06"
    assert T.num(0.1111111111111111) == "0,111"
    assert T.num(None) == T.AUSENTE


@pytest.mark.parametrize(
    ("n", "esperado"),
    [
        (0, T.SIMBOLO_N_SUPRIMIDO),
        (4, T.SIMBOLO_N_SUPRIMIDO),
        (5, T.SIMBOLO_N_ALERTA),
        (7, T.SIMBOLO_N_ALERTA),
        (8, T.SIMBOLO_N_OK),
        (19, T.SIMBOLO_N_OK),
    ],
)
def test_simbolo_de_n_usa_os_limiares_do_contrato(n: int, esperado: str) -> None:
    """`‡` abaixo de 5, `†` abaixo de 8, nada a partir de 8 — os limiares são de F-019."""
    assert T.simbolo_de_n(n) == esperado


def test_simbolos_mudam_exatamente_nos_limiares_importados() -> None:
    """Se alguém mudar `N_ALERTA`/`N_SUPRESSAO` no contrato, o símbolo acompanha — sem cópia."""
    assert T.simbolo_de_n(N_SUPRESSAO - 1) == T.SIMBOLO_N_SUPRIMIDO
    assert T.simbolo_de_n(N_SUPRESSAO) == T.SIMBOLO_N_ALERTA
    assert T.simbolo_de_n(N_ALERTA - 1) == T.SIMBOLO_N_ALERTA
    assert T.simbolo_de_n(N_ALERTA) == T.SIMBOLO_N_OK


def test_em_erros_padrao_devolve_none_quando_nao_ha_dispersao() -> None:
    """Erro-padrão zero ou ausente não vira divisão por zero nem `inf`."""
    assert T.em_erros_padrao(0.05, 0.025) == pytest.approx(2.0)
    assert T.em_erros_padrao(-0.05, 0.025) == pytest.approx(2.0)
    assert T.em_erros_padrao(0.05, 0.0) is None
    assert T.em_erros_padrao(0.05, None) is None
    assert T.em_erros_padrao(None, 0.02) is None


# ═════════════════════════════════════════════════════════════════════════════
# 2 — Bloco A: as três respostas, o fallback declarado, nada inventado
# ═════════════════════════════════════════════════════════════════════════════


def test_as_tres_respostas_existem_e_nenhuma_e_escolhida(cenario: dict[str, Any]) -> None:
    """**CA-098:** a página responde pela V1 `revised`, pela V1 `asof` e pela V3 — as três."""
    respostas = cenario["respostas"]
    assert len(respostas) == T.N_LENTES == 3
    titulos = [r.titulo for r in respostas]
    assert titulos == ["V1 `revised`", "V1 `asof`", "V3 (vizinhos)"]
    assert [r.resposta for r in respostas] == [
        StatusRegimeV1.INDETERMINADO.value,
        RegimeV1.DESACELERACAO.value,
        T.nome_do_regime_v3(QUARTER),
    ]


def test_quarter_sem_quadrante_responde_indeterminado_e_nunca_um_rotulo(
    cenario: dict[str, Any],
) -> None:
    """**Anti-SPEC §10.1.1:** `2026Q3` sem `ibcbr_gap` não recebe quadrante estimado."""
    revised = cenario["respostas"][0]
    assert revised.status == T.StatusDaResposta.INDETERMINADO_COM_FALLBACK.value
    assert revised.resposta == StatusRegimeV1.INDETERMINADO.value
    assert revised.resposta not in {r.value for r in RegimeV1}
    assert MotivoIndeterminado.GAP_AUSENTE.value in revised.como_chega


def test_fallback_e_o_ultimo_trimestre_com_quadrante_e_vem_rotulado(
    cenario: dict[str, Any],
) -> None:
    """O ranking da `revised` sai de `2026Q2`, e a palavra "fallback" vai na ressalva e no dado."""
    revised = cenario["respostas"][0]
    assert revised.quarter_da_celula == FALLBACK
    assert revised.regime_da_celula == RegimeV1.ESTAGFLACAO.value
    assert revised.e_fallback is True
    assert "fallback" in revised.ressalva.lower()
    bloco = cenario["ranking"]
    da_revised = bloco.loc[bloco["lente_rotulo"].str.startswith("V1_revised")]
    assert set(da_revised["e_fallback"]) == {True}
    assert set(da_revised["quarter_da_celula"]) == {FALLBACK}
    assert set(da_revised["quarter_perguntado"]) == {QUARTER}


def test_quarter_classificado_nao_usa_fallback() -> None:
    """Quando a lente **tem** quadrante para o trimestre, a célula é a dele — sem fallback."""
    regimes = regimes_sinteticos(rotulo_do_quarter=RegimeV1.DESACELERACAO.value)
    resposta = T.resposta_v1(regimes, materializacao=Materializacao.REVISED, quarter=QUARTER)
    assert resposta.status == T.StatusDaResposta.CLASSIFICADO.value
    assert resposta.quarter_da_celula == QUARTER
    assert resposta.e_fallback is False


def test_sem_nenhum_quadrante_na_historia_a_resposta_e_bloqueada() -> None:
    """Sem **nenhum** trimestre com quadrante não há fallback honesto: falha ruidosa."""
    regimes = pd.DataFrame(
        {
            "quarter": [FALLBACK, QUARTER],
            "regime_v1": [None, None],
            "status_regime_v1": [StatusRegimeV1.INDETERMINADO.value] * 2,
            "motivo_indeterminado": [MotivoIndeterminado.GAP_AUSENTE.value] * 2,
            "g_score": [None, None],
            "pi_score": [None, None],
            "n_obs_regime_v1": [1, 1],
            "lag_adjusted": [False, False],
        }
    )
    with pytest.raises(FonteIndisponivel, match="nenhum trimestre com quadrante"):
        T.resposta_v1(regimes, materializacao=Materializacao.REVISED, quarter=QUARTER)


def test_quarter_fora_da_janela_falha_em_vez_de_devolver_vazio() -> None:
    """Perguntar por um trimestre que a tabela não tem é erro de janela, não resposta vazia."""
    regimes = regimes_sinteticos(rotulo_do_quarter=None)
    with pytest.raises(SerieInconsistente, match="não está em regimes_v1"):
        T.resposta_v1(regimes, materializacao=Materializacao.REVISED, quarter="2030Q1")


def test_ressalva_da_asof_traz_ca074_medido_nao_escrito_a_mao() -> None:
    """**CA-074:** o percentual sai de `divergencia_entre_materializacoes`, não do texto."""
    revised = regimes_sinteticos(rotulo_do_quarter=RegimeV1.RECUPERACAO.value)
    asof = regimes_sinteticos(rotulo_do_quarter=RegimeV1.DESACELERACAO.value, asof=True)
    texto = T.ressalva_ca074(revised, asof)
    # 2 dos 4 trimestres trocam de rótulo na fixture: 50% > limiar de 25% ⇒ CA-074 acionado.
    assert "CA-074 acionado" in texto
    assert "50,00%" in texto
    assert "não é operacional" in texto


def test_ressalva_dentro_do_limiar_nao_acusa_ca074() -> None:
    """Abaixo do limiar o texto é o de CA-073 — a guarda não grita sem motivo."""
    revised = regimes_sinteticos(rotulo_do_quarter=RegimeV1.ESTAGFLACAO.value)
    texto = T.ressalva_ca074(revised, revised.copy())
    assert "CA-074 acionado" not in texto
    assert "dentro** do limiar" in texto or "dentro" in texto


def test_os_oito_vizinhos_saem_da_lente_canonica_com_distancia_e_t_mais_1(
    cenario: dict[str, Any],
) -> None:
    """**CA-098/CA-102:** 8 vizinhos, `rank` 1..8, distância e o `T+1` de cada um."""
    vizinhos = cenario["vizinhos"]
    assert len(vizinhos) == K_VIZINHOS_PADRAO == 8
    assert list(vizinhos["rank"]) == list(range(1, 9))
    assert vizinhos["distancia"].is_monotonic_increasing
    for _, linha in vizinhos.iterrows():
        seguinte = pd.Period(linha["quarter_neighbor"], freq="Q") + 1
        assert linha["quarter_t_mais_1"] == f"{seguinte.year}Q{seguinte.quarter}"
        assert linha["quarter_t_mais_1"] != linha["quarter_neighbor"]


def test_lente_canonica_ausente_bloqueia_em_vez_de_cair_em_outra_variante() -> None:
    """Sem a lente principal (`mahalanobis`, `k=8`, descritiva) a página **não** improvisa."""
    neighbors = neighbors_sinteticos()
    so_passado = neighbors.assign(somente_passado=True)
    with pytest.raises(FonteIndisponivel, match="não tem a lente canônica"):
        T.vizinhos_do_quarter(so_passado, quarter=QUARTER)


# ═════════════════════════════════════════════════════════════════════════════
# 3 — Bloco B: ordenação, célula vazia no fim, `n` em toda linha
# ═════════════════════════════════════════════════════════════════════════════


def test_ranking_tem_as_tres_lentes_com_os_24_ativos_cada(cenario: dict[str, Any]) -> None:
    """3 lentes × 24 ativos = 72 linhas, e o contrato de colunas é o declarado."""
    ranking = cenario["ranking"]
    assert len(ranking) == T.N_LENTES * T.N_ATIVOS_ESPERADO == 72
    assert list(ranking.columns) == list(T.COLUNAS_RANKING)
    assert ranking.groupby("lente_rotulo")["asset_id"].nunique().eq(24).all()


def test_ranking_ordena_por_excesso_decrescente_em_cada_lente(cenario: dict[str, Any]) -> None:
    """**CA-098:** a ordem é `excesso_cdi` decrescente, e `posicao` é 1..24 sem buraco."""
    ranking = cenario["ranking"]
    for rotulo, bloco in ranking.groupby("lente_rotulo"):
        assert list(bloco["posicao"]) == list(range(1, 25)), rotulo
        valores = [v for v in bloco["excesso_cdi"] if pd.notna(v)]
        assert valores == sorted(valores, reverse=True), rotulo


def test_celula_sem_observacao_vai_para_o_fim_nunca_para_o_topo() -> None:
    """`None` não é "o melhor": célula sem excesso fecha o ranking (regra de F-022)."""
    metricas = metricas_sinteticas(
        lente=LENTE_V1,
        regime=RegimeV1.ESTAGFLACAO.value,
        excesso_por_ativo={ATIVOS[0]: None},
    )
    lente = T.Lente(
        rotulo="sintetica",
        resposta=T.RespostaDeRegime(
            titulo="sintetica",
            quarter_perguntado=QUARTER,
            status=T.StatusDaResposta.CLASSIFICADO.value,
            resposta=RegimeV1.ESTAGFLACAO.value,
            quarter_da_celula=QUARTER,
            regime_da_celula=RegimeV1.ESTAGFLACAO.value,
            como_chega="",
            ressalva="",
        ),
        lente=LENTE_V1,
        materializacao=Materializacao.REVISED.value,
        horizonte="T0",
        tabela=TABELA_PRINCIPAL,
    )
    linhas = T.linhas_do_ranking(metricas, lente, versao=VERSAO_SINTETICA)
    assert linhas[-1]["asset_id"] == ATIVOS[0]
    assert linhas[-1]["excesso_cdi"] is None
    assert linhas[0]["asset_id"] != ATIVOS[0]


def test_toda_linha_do_ranking_carrega_n_e_as_duas_flags(cenario: dict[str, Any]) -> None:
    """**Anti-SPEC §10.2.8:** nenhuma célula, em nenhuma tabela, sai sem `n`."""
    ranking = cenario["ranking"]
    assert ranking["n_obs"].notna().all()
    assert ranking["n_obs"].ge(0).all()
    assert ranking["alerta_n_baixo"].notna().all()
    assert ranking["conclusao_suprimida"].notna().all()
    assert ranking["simbolo_n"].notna().all()


def test_flags_batem_com_o_simbolo_linha_a_linha(cenario: dict[str, Any]) -> None:
    """O símbolo não é decoração: é a tradução das flags, conferida célula a célula."""
    for _, linha in cenario["ranking"].iterrows():
        n = int(linha["n_obs"])
        assert bool(linha["conclusao_suprimida"]) == (n < N_SUPRESSAO)
        assert bool(linha["alerta_n_baixo"]) == (n < N_ALERTA)
        assert linha["simbolo_n"] == T.simbolo_de_n(n)


def test_ativo_com_n_abaixo_de_5_mantem_a_linha_e_recebe_o_simbolo(
    cenario: dict[str, Any],
) -> None:
    """**CA-099/CA-109:** a linha fica com o número; a **conclusão** é que é suprimida."""
    ranking = cenario["ranking"]
    suprimidas = ranking.loc[ranking["conclusao_suprimida"]]
    assert len(suprimidas) == 1
    linha = suprimidas.iloc[0]
    assert linha["asset_id"] == ATIVOS[-1]
    assert int(linha["n_obs"]) == 4
    assert pd.notna(linha["excesso_cdi"])  # o número continua lá
    assert linha["simbolo_n"] == T.SIMBOLO_N_SUPRIMIDO


def test_grade_incompleta_de_ativos_falha_em_vez_de_omitir_linha() -> None:
    """Ativo faltando é **falha**, não omissão silenciosa: a página não sai com 23 linhas."""
    metricas = metricas_sinteticas(lente=LENTE_V1, regime=RegimeV1.ESTAGFLACAO.value)
    incompleta = metricas.loc[metricas["asset_id"] != ATIVOS[0]]
    lente = T.lentes_da_pagina(
        T.respostas_do_regime_atual(
            regimes_revised=regimes_sinteticos(rotulo_do_quarter=None),
            regimes_asof=regimes_sinteticos(
                rotulo_do_quarter=RegimeV1.DESACELERACAO.value, asof=True
            ),
            vizinhos=T.vizinhos_do_quarter(neighbors_sinteticos(), quarter=QUARTER),
            quarter=QUARTER,
        )
    )[0]
    with pytest.raises(SerieInconsistente, match="esperados 24"):
        T.linhas_do_ranking(incompleta, lente, versao=VERSAO_SINTETICA)


def test_celula_inexistente_bloqueia_com_instrucao_de_como_gerar() -> None:
    """Pedir uma célula que F-022 não produziu devolve `BLOQUEADO — FONTE INDISPONÍVEL`."""
    metricas = metricas_sinteticas(lente=LENTE_V1, regime=RegimeV1.ESTAGFLACAO.value)
    lente = T.Lente(
        rotulo="sintetica",
        resposta=T.RespostaDeRegime(
            titulo="sintetica",
            quarter_perguntado=QUARTER,
            status=T.StatusDaResposta.VIZINHOS.value,
            resposta="VIZINHOS_INEXISTENTE",
            quarter_da_celula=QUARTER,
            regime_da_celula="VIZINHOS_INEXISTENTE",
            como_chega="",
            ressalva="",
        ),
        lente=LENTE_V3,
        materializacao=Materializacao.REVISED.value,
        horizonte="T+1",
        tabela=TABELA_PRINCIPAL,
    )
    with pytest.raises(FonteIndisponivel, match="FONTE INDISPONÍVEL"):
        T.linhas_do_ranking(metricas, lente, versao=VERSAO_SINTETICA)


# ═════════════════════════════════════════════════════════════════════════════
# 4 — Spearman e postos, com casos de valor conhecido
# ═════════════════════════════════════════════════════════════════════════════


def test_postos_sem_empate_sao_1_a_n() -> None:
    """Posto é posição na ordem crescente, não o valor."""
    assert list(T.postos([10.0, 30.0, 20.0])) == [1.0, 3.0, 2.0]


def test_postos_com_empate_usam_a_media_do_grupo() -> None:
    """`[1, 2, 2, 3]` → `[1, 2,5, 2,5, 4]` — o `method="average"` que Spearman pressupõe."""
    assert list(T.postos([1.0, 2.0, 2.0, 3.0])) == [1.0, 2.5, 2.5, 4.0]


def test_postos_nao_dependem_da_ordem_de_entrada() -> None:
    """Invertendo a entrada, cada elemento mantém o seu posto (determinismo)."""
    valores = [5.0, 1.0, 3.0, 3.0, 9.0]
    diretos = dict(zip(valores, T.postos(valores), strict=True))
    invertidos = dict(zip(valores[::-1], T.postos(valores[::-1]), strict=True))
    assert diretos == invertidos


def test_spearman_concordancia_perfeita_e_1() -> None:
    """Mesma ordem ⇒ `rho = 1`, mesmo com escalas completamente diferentes."""
    assert T.spearman([1.0, 2.0, 3.0, 4.0], [10.0, 200.0, 3000.0, 40000.0]) == pytest.approx(1.0)


def test_spearman_ordem_invertida_e_menos_1() -> None:
    """Ordem exatamente oposta ⇒ `rho = −1`."""
    assert T.spearman([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) == pytest.approx(-1.0)


def test_spearman_bate_com_a_formula_fechada_sem_empate() -> None:
    """Caso conhecido: `x=[1..5]`, `y=[2,1,4,3,5]` ⇒ `1 − 6·Σd²/[n(n²−1)] = 1 − 24/120 = 0,8`."""
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 1.0, 4.0, 3.0, 5.0]
    soma_d2 = sum((a - b) ** 2 for a, b in zip(x, y, strict=True))
    fechada = 1 - 6 * soma_d2 / (len(x) * (len(x) ** 2 - 1))
    assert fechada == pytest.approx(0.8)
    assert T.spearman(x, y) == pytest.approx(fechada)


def test_spearman_com_empate_difere_da_formula_fechada_e_usa_pearson_nos_postos() -> None:
    """Com empate a fórmula fechada **não** vale; o módulo usa Pearson nos postos, que vale."""
    x = [1.0, 2.0, 2.0, 4.0]
    y = [1.0, 2.0, 3.0, 4.0]
    soma_d2 = sum((a - b) ** 2 for a, b in zip(x, y, strict=True))
    fechada = 1 - 6 * soma_d2 / (len(x) * (len(x) ** 2 - 1))
    assert fechada == pytest.approx(0.9)  # a fechada erra: ignora o empate
    assert T.spearman(x, y) == pytest.approx(0.9486832980505139)


def test_spearman_devolve_none_quando_um_lado_e_constante() -> None:
    """Variância zero não dá correlação 0 — dá correlação **indefinida**."""
    assert T.spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None


def test_spearman_devolve_none_com_menos_de_dois_pares() -> None:
    """Um ponto não tem ordem."""
    assert T.spearman([1.0], [2.0]) is None
    assert T.spearman([], []) is None


def test_spearman_recusa_vetores_de_tamanhos_diferentes() -> None:
    """Comparar 24 ativos com 23 seria emparelhar ativos errados — falha explícita."""
    with pytest.raises(SerieInconsistente, match="mesmo tamanho"):
        T.spearman([1.0, 2.0, 3.0], [1.0, 2.0])


# ═════════════════════════════════════════════════════════════════════════════
# 5 — Bloco C: concordância por lente e par a par
# ═════════════════════════════════════════════════════════════════════════════


def test_concordancia_tem_uma_linha_por_lente_com_top_3(cenario: dict[str, Any]) -> None:
    """**CA-103, a letra:** 1 linha por lente, com os 3 primeiros ativos."""
    bloco = cenario["bloco_c"]
    assert len(bloco["por_lente"]) == T.N_LENTES
    for dados in bloco["por_lente"].values():
        assert len(dados["top_3"]) == 3
        assert len(dados["top_5"]) == 5
        assert len(dados["top_10"]) == 10


def test_concordancia_reporta_a_divergencia_em_vez_de_omitir(cenario: dict[str, Any]) -> None:
    """**CA-103, o espírito:** o par divergente aparece com Jaccard, não é deixado de fora."""
    bloco = cenario["bloco_c"]
    assert len(bloco["pares"]) == 3  # as 3 combinações de 3 lentes
    for dados in bloco["pares"].values():
        assert dados["jaccard_top5"] is not None
        assert dados["jaccard_top10"] is not None
        assert "em_comum_top5" in dados


def test_jaccard_do_par_bate_com_a_definicao_de_conjuntos(cenario: dict[str, Any]) -> None:
    """`|A ∩ B| / |A ∪ B|` recalculado fora do módulo, a partir dos top-5 publicados."""
    bloco = cenario["bloco_c"]
    for chave, dados in bloco["pares"].items():
        a = set(bloco["por_lente"][dados["lente_a"]]["top_5"])
        b = set(bloco["por_lente"][dados["lente_b"]]["top_5"])
        esperado = len(a & b) / len(a | b)
        assert dados["jaccard_top5"] == pytest.approx(esperado), chave
        assert dados["em_comum_top5"] == sorted(a & b), chave


def test_tabela_de_concordancia_tem_as_tres_secoes_no_contrato(cenario: dict[str, Any]) -> None:
    """A tabela *tidy* carrega as 3 seções do bloco C, e nada fora de `COLUNAS_CONCORDANCIA`."""
    tabela = T.tabela_de_concordancia(cenario["bloco_c"], versao=VERSAO_SINTETICA)
    assert list(tabela.columns) == list(T.COLUNAS_CONCORDANCIA)
    assert set(tabela["secao"]) == {s.value for s in T.SecaoDaConcordancia}
    por_lente = tabela.loc[tabela["secao"] == T.SecaoDaConcordancia.POR_LENTE.value]
    assert por_lente["chave"].nunique() == T.N_LENTES
    assert (por_lente["metrica"] == "top_3").sum() == T.N_LENTES


def test_registros_da_lente_devolvem_nan_a_none() -> None:
    """`NaN` não é `None`: a ida e volta pelo DataFrame não pode promover célula vazia ao topo."""
    quadro = pd.DataFrame(
        {
            "lente_rotulo": ["x", "x"],
            "asset_id": ["CDI", "IBOV"],
            "excesso_cdi": [float("nan"), 0.01],
        }
    )
    registros = T._registros_da_lente(quadro, "x")
    assert registros[0]["excesso_cdi"] is None
    assert registros[1]["excesso_cdi"] == pytest.approx(0.01)


# ═════════════════════════════════════════════════════════════════════════════
# 6 — A distribuição `somente_passado` × descritiva (QA da Onda 3, P1-2)
# ═════════════════════════════════════════════════════════════════════════════


def test_distribuicao_das_variantes_v3_e_sobre_todas_as_referencias_comuns() -> None:
    """**QA P1-2:** o Jaccard é medido em **cada** referência que tem as duas variantes."""
    descritiva = {
        "2026Q3": ["2006Q1", "2006Q2", "2006Q3", "2006Q4"],
        "2025Q4": ["2006Q1", "2006Q2", "2024Q1", "2024Q2"],
        "2024Q4": ["2020Q1", "2020Q2", "2020Q3", "2020Q4"],
    }
    passado = {
        # igual por inteiro ⇒ Jaccard 1,0 (o caso "vácuo" do último trimestre)
        "2026Q3": ["2006Q4", "2006Q3", "2006Q2", "2006Q1"],
        # metade em comum ⇒ 2/6 = 0,333
        "2025Q4": ["2006Q1", "2006Q2", "2011Q1", "2011Q2"],
        # nada em comum ⇒ 0,0
        "2024Q4": ["2014Q1", "2014Q2", "2014Q3", "2014Q4"],
    }
    bloco = T.jaccard_das_variantes_v3(
        neighbors_sinteticos(por_referencia=descritiva, somente_passado=passado)
    )
    assert bloco["referencias_comparadas"] == 3
    distribuicao = bloco["distribuicao"]
    assert distribuicao["max"] == pytest.approx(1.0)
    assert distribuicao["mediana"] == pytest.approx(1 / 3)
    assert distribuicao["min"] == pytest.approx(0.0)
    assert distribuicao["n_iguais_a_1"] == 1
    assert distribuicao["n_zeros"] == 1
    assert bloco["do_quarter_do_comite"]["jaccard"] == pytest.approx(1.0)


def test_referencia_so_na_variante_descritiva_fica_fora_da_distribuicao() -> None:
    """Comparar contra uma variante que não existe naquela referência seria inventar o par."""
    bloco = T.jaccard_das_variantes_v3(
        neighbors_sinteticos(
            por_referencia={"2026Q3": ["2006Q1"], "2010Q1": ["2006Q2"]},
            somente_passado={"2026Q3": ["2006Q1"]},
        )
    )
    assert bloco["referencias_descritiva"] == 2
    assert bloco["referencias_somente_passado"] == 1
    assert bloco["referencias_comparadas"] == 1


def test_sem_a_variante_somente_passado_a_conta_bloqueia() -> None:
    """Sem as duas variantes não há distribuição — e a página não finge que há."""
    with pytest.raises(FonteIndisponivel, match="as duas variantes"):
        T.jaccard_das_variantes_v3(neighbors_sinteticos())


# ═════════════════════════════════════════════════════════════════════════════
# 7 — O Markdown: as 3 respostas, nada preditivo, determinismo e gate
# ═════════════════════════════════════════════════════════════════════════════


def test_markdown_traz_os_quatro_blocos(cenario: dict[str, Any]) -> None:
    """A página é A + B + C + D + rodapé — nenhum bloco cai em silêncio."""
    texto = markdown_do_cenario(cenario)
    assert "## A. Em que regime estamos" in texto
    assert "## B. Ranking de ativos por lente" in texto
    assert "## C. Concordância entre lentes" in texto
    assert "## D. O que isso **não** diz" in texto
    assert "`versao_build`" in texto


def test_markdown_traz_as_tres_respostas_e_a_regra_de_leitura(cenario: dict[str, Any]) -> None:
    """**CA-098:** as três respostas e a regra que diz para que cada uma serve."""
    texto = markdown_do_cenario(cenario)
    assert "V1 `revised`" in texto
    assert "V1 `asof`" in texto
    assert "V3 (vizinhos)" in texto
    assert StatusRegimeV1.INDETERMINADO.value in texto
    assert RegimeV1.DESACELERACAO.value in texto
    assert T.nome_do_regime_v3(QUARTER) in texto
    assert "Regra de leitura" in texto
    assert "decisão do Edu (D1)" in texto


def test_markdown_traz_os_oito_vizinhos_com_datas_e_distancias(cenario: dict[str, Any]) -> None:
    """O bloco A lista os 8 vizinhos **com data e distância**, não só a contagem."""
    texto = markdown_do_cenario(cenario)
    for _, linha in cenario["vizinhos"].iterrows():
        assert f"`{linha['quarter_neighbor']}`" in texto
        assert T.num(float(linha["distancia"]), casas=4) in texto


def test_markdown_traz_as_tres_linhas_do_bloco_d_com_n_medido(cenario: dict[str, Any]) -> None:
    """Bloco D com as 3 linhas, e a faixa de `n`/erro-padrão **medida nesta rodada**."""
    texto = markdown_do_cenario(cenario)
    assert "1. **`n` pequeno não distingue ativos.**" in texto
    assert "2. **A especificação de regime não está congelada.**" in texto
    assert "3. **Descritivo não é preditivo.**" in texto
    ranking = cenario["ranking"]
    assert f"**{int(ranking['n_obs'].min())} a {int(ranking['n_obs'].max())}**" in texto
    assert "{n_min}" not in texto  # nenhum placeholder sobrou


def test_markdown_tem_a_legenda_dos_simbolos_e_o_simbolo_no_ativo(
    cenario: dict[str, Any],
) -> None:
    """**CA-099:** o ativo com `n < 5` aparece marcado, e a legenda diz o que a marca significa."""
    texto = markdown_do_cenario(cenario)
    assert T.SIMBOLO_N_SUPRIMIDO in texto
    assert f"n < {N_SUPRESSAO}" in texto
    assert f"n < {N_ALERTA}" in texto
    suprimida = cenario["ranking"].loc[cenario["ranking"]["conclusao_suprimida"]].iloc[0]
    assert f"`{suprimida['asset_id']}`{T.SIMBOLO_N_SUPRIMIDO}" in texto


def test_markdown_nao_tem_linguagem_preditiva(cenario: dict[str, Any]) -> None:
    """**Anti-SPEC §10.2.10:** a página gerada passa pela própria guarda, sem exceção."""
    T.conferir_linguagem_descritiva(markdown_do_cenario(cenario))
    T.conferir_linguagem_descritiva(
        T.markdown_da_concordancia(cenario["bloco_c"], versao=VERSAO_SINTETICA, congelada=False)
    )


@pytest.mark.parametrize(
    "frase",
    [
        "O IBOV vai render +5% no próximo trimestre.",
        "Esperamos excesso sobre o CDI em renda variável.",
        "Recomendamos aumentar a exposição internacional.",
        "Projetamos 4% para o trimestre.",
        "Previsão para 4T2026: IBOV +5%.",
        "Backtest da estratégia: +12% ao ano.",
    ],
)
def test_guarda_recusa_frase_preditiva(frase: str) -> None:
    """**Teste negativo:** cada forma preditiva conhecida é recusada, com o termo no erro."""
    with pytest.raises(SerieInconsistente, match="linguagem preditiva"):
        T.conferir_linguagem_descritiva(frase)


@pytest.mark.parametrize(
    "frase",
    [
        "Não é previsão de retorno, não é backtest e não é recomendação de alocação.",
        "Nenhuma projeção, nenhuma extrapolação: só o que aconteceu, com n.",
        "Descritivo ≠ preditivo: nada aqui é projeção.",
        # As 4 frases REAIS que o QA da Onda 4 (P2-1) mediu sendo reprovadas pela guarda antiga,
        # cuja janela de negação só olhava para trás e só via `não`/`nunca` colados ao termo.
        "Nada aqui e projecao: a figura descreve o passado, com n em toda celula.",
        'O que este levantamento sustenta: "rendeu X, n = Y". Nunca "quanto vai render".',
        "Backtest, otimizacao ou fronteira eficiente - nada disso esta neste pacote.",
        "A recomendacao de alocacao e do Alexandre; este levantamento nao a faz.",
    ],
)
def test_guarda_aceita_o_substantivo_sob_negacao(frase: str) -> None:
    """O bloco D **precisa** dizer o que a página não é: sob negação, o termo é permitido.

    As 4 últimas frases são as **reais** que o QA da Onda 4 (**P2-1**) pegou sendo reprovadas: a
    guarda desta feature, aplicada aos textos das figuras e de `LIMITACOES-COMITE.md`, recusava
    negação legítima. A guarda única (`apps/analysis/_linguagem.py`) olha a janela nos **dois**
    sentidos e reconhece `nada … é` e cabeçalho de seção negada.
    """
    T.conferir_linguagem_descritiva(frase)


def test_markdown_e_deterministico(cenario: dict[str, Any]) -> None:
    """**CA-121:** duas montagens do mesmo cenário dão o **mesmo** texto, caractere a caractere."""
    assert markdown_do_cenario(cenario) == markdown_do_cenario(cenario)
    outro = cenario_sintetico()
    assert markdown_do_cenario(outro) == markdown_do_cenario(cenario)


def test_markdown_carrega_a_marca_do_gate_quando_a_especificacao_nao_esta_congelada(
    cenario: dict[str, Any],
) -> None:
    """**CA-090:** com ADR-001 em `Proposta`, a página nasce **não publicável**, e diz isso."""
    nao_congelada = markdown_do_cenario(cenario, congelada=False)
    assert T.MARCA_NAO_CONGELADA in nao_congelada
    assert nao_congelada.count(T.MARCA_NAO_CONGELADA) >= 2  # cabeçalho e rodapé
    congelada = markdown_do_cenario(cenario, congelada=True)
    assert T.MARCA_NAO_CONGELADA not in congelada


def test_rodape_traz_versao_build_e_o_hash_de_cada_insumo(cenario: dict[str, Any]) -> None:
    """O rodapé é o que distingue "mudou o código" de "mudou o dado"."""
    texto = markdown_do_cenario(cenario)
    assert VERSAO_SINTETICA in texto
    assert FONTE_VERSAO_SINTETICA in texto
    assert "sintetico.parquet" in texto
    for modulo in T.MODULOS_DA_TABELA:
        assert modulo in texto


def test_versao_build_e_hash_estavel_do_conjunto_de_modulos() -> None:
    """`versao_build` é `sha256` do conjunto de módulos: 64 hex, e estável na mesma árvore."""
    primeiro = T.versao_build()
    assert len(primeiro) == 64
    assert set(primeiro) <= set("0123456789abcdef")
    assert primeiro == T.versao_build()
    # Mudar o conjunto muda o hash — é o ponto.
    assert T.versao_build(("apps.analysis.tabelas.ranking_regime_atual",)) != primeiro


def test_insumo_ausente_bloqueia_com_instrucao(tmp_path: Path) -> None:
    """Sem `regime_asset_metrics` a tabela não sai, e o erro diz **qual** comando rodar."""
    with pytest.raises(FonteIndisponivel, match="metricas_regime"):
        T.ler_metricas(TABELA_PRINCIPAL, raiz=tmp_path)
    with pytest.raises(FonteIndisponivel, match="FONTE INDISPONÍVEL"):
        T.hashes_dos_insumos(raiz=tmp_path)


# ═════════════════════════════════════════════════════════════════════════════
# 8 — Acervo real `data/canonical/` (padrão `Acervo`; desligado por LDC_IGNORAR_DATA=1)
# ═════════════════════════════════════════════════════════════════════════════

N_REFERENCIAS_DAS_DUAS_VARIANTES = 58
"""As 58 referências que têm `somente_passado` **e** descritiva — o número do QA P1-2."""

NOME_RELATORIO_METRICAS = "relatorio_metricas.json"
NOME_RELATORIO_V3 = "relatorio_regimes_v3.json"


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


def canonical_disponivel() -> bool:
    """Os Parquets e os dois relatórios que o bloco 8 confere existem nesta máquina?"""
    alvos = [
        TABELA_PRINCIPAL.nome_arquivo,
        TABELA_ASOF.nome_arquivo,
        T.NOME_REGIMES_V1,
        T.NOME_REGIMES_V1_ASOF,
        T.NOME_NEIGHBORS_V3,
        NOME_RELATORIO_METRICAS,
        NOME_RELATORIO_V3,
    ]
    return all(caminho_canonical(nome).is_file() for nome in alvos)


acervo_real = pytest.mark.skipif(
    ignorar_data_real() or not canonical_disponivel(),
    reason=f"data/canonical/ ausente ou {VAR_IGNORAR_DATA} ligada — {COMO_GERAR}",
)


@pytest.fixture(scope="module")
def resultado_real():  # noqa: ANN201 - ResultadoTabela
    """A página recalculada do acervo real, **sem gravar** (o teste não mexe em `data/`)."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponível")
    return T.construir(gravar=False)


@pytest.fixture(scope="module")
def relatorio_metricas() -> dict[str, Any]:
    """`relatorio_metricas.json` de F-022 — a referência numérica independente desta feature."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponível")
    return json.loads(caminho_canonical(NOME_RELATORIO_METRICAS).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def relatorio_v3() -> dict[str, Any]:
    """`relatorio_regimes_v3.json` de F-021 — os 8 vizinhos e o ranking em `T+1`."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponível")
    return json.loads(caminho_canonical(NOME_RELATORIO_V3).read_text(encoding="utf-8"))


@acervo_real
def test_acervo_as_tres_respostas_sao_as_de_f022(
    resultado_real,  # noqa: ANN001
    relatorio_metricas: dict[str, Any],
) -> None:
    """As 3 respostas batem com `relatorio_metricas.json → regime_atual`, uma a uma."""
    do_f022 = relatorio_metricas["regime_atual"]
    revised, asof, v3 = resultado_real.respostas
    assert revised.resposta == do_f022["v1_revised"]["status"] == "INDETERMINADO"
    assert do_f022["v1_revised"]["regime"] is None
    assert revised.quarter_da_celula == do_f022["fallback_declarado"]["quarter"]
    assert revised.regime_da_celula == do_f022["fallback_declarado"]["regime"]
    assert asof.resposta == do_f022["v1_asof"]["regime"]
    assert v3.resposta == T.nome_do_regime_v3(do_f022["quarter"])


@acervo_real
def test_acervo_vizinhos_sao_os_oito_de_f021(
    resultado_real,  # noqa: ANN001
    relatorio_v3: dict[str, Any],
) -> None:
    """Os 8 vizinhos e as 8 distâncias são **os de F-021**, não recalculados aqui."""
    do_f021 = relatorio_v3["vizinhos_do_comite"]["vizinhos"]
    vizinhos = resultado_real.vizinhos
    assert len(vizinhos) == len(do_f021) == 8
    for esperado, (_, obtido) in zip(do_f021, vizinhos.iterrows(), strict=True):
        assert obtido["rank"] == esperado["rank"]
        assert obtido["quarter_neighbor"] == esperado["quarter_neighbor"]
        assert obtido["quarter_t_mais_1"] == esperado["quarter_t_mais_1"]
        assert float(obtido["distancia"]) == pytest.approx(esperado["distancia"], abs=1e-12)


@acervo_real
def test_acervo_ranking_v3_e_byte_a_byte_o_de_f021(
    resultado_real,  # noqa: ANN001
    relatorio_v3: dict[str, Any],
) -> None:
    """O ranking da V3 em `T+1` bate com `relatorio_regimes_v3.json`, ativo a ativo.

    É a conferência mais forte do bloco: **três** módulos independentes (F-021, F-022 e esta
    página) chegam ao mesmo número para os 24 ativos, por caminhos diferentes.
    """
    do_f021 = {
        linha["asset_id"]: linha for linha in relatorio_v3["ranking_ativos_t_mais_1"]["ativos"]
    }
    ranking = resultado_real.ranking
    da_v3 = ranking.loc[ranking["lente"] == LENTE_V3]
    assert len(da_v3) == 24
    for _, linha in da_v3.iterrows():
        esperado = do_f021[linha["asset_id"]]
        assert int(linha["n_obs"]) == int(esperado["n"])
        assert float(linha["excesso_cdi"]) == pytest.approx(esperado["media"], abs=1e-12)


@acervo_real
def test_acervo_erro_padrao_da_pagina_e_o_nominal_e_a_pagina_diz_isso(
    resultado_real,  # noqa: ANN001
    relatorio_v3: dict[str, Any],
) -> None:
    """O `ep` da página é o do retorno **nominal** (F-022), e F-021 publica o do **excesso**.

    Os dois números são diferentes (`INDX`: 2,60 pp contra 2,54 pp) porque medem dispersões
    diferentes. A escolha é deliberada — a coluna vem de `RegimeAssetMetricsSchema`, e
    acrescentar `erro_padrao_excesso` seria alteração de schema existente, logo classe C própria.
    O que **não** é aceitável é a página não dizer qual dos dois ela mostra, e é isso que este
    teste trava.
    """
    do_f021 = {
        linha["asset_id"]: linha for linha in relatorio_v3["ranking_ativos_t_mais_1"]["ativos"]
    }
    ranking = resultado_real.ranking
    da_v3 = ranking.loc[ranking["lente"] == LENTE_V3].set_index("asset_id")
    nominal = float(da_v3.loc["INDX", "erro_padrao_media"])
    do_excesso = float(do_f021["INDX"]["erro_padrao"])
    assert nominal != pytest.approx(do_excesso, abs=1e-6)
    assert nominal > do_excesso  # a dispersão nominal inclui a variação do próprio CDI
    texto = resultado_real.markdown_ranking
    assert "ep (pp, nom.)" in texto
    assert "semáforo de confiança" in texto
    assert "ret médio (nom.)" in texto


@acervo_real
def test_acervo_rankings_da_v1_sao_os_de_f022(
    resultado_real,  # noqa: ANN001
    relatorio_metricas: dict[str, Any],
) -> None:
    """Os dois rankings da V1 (fallback `revised` e `asof`) batem com F-022, na mesma ordem."""
    ranking = resultado_real.ranking
    pares = (
        ("V1_revised", relatorio_metricas["regime_atual"]["ranking_v1_fallback"]),
        ("V1_asof", relatorio_metricas["regime_atual"]["ranking_v1_asof_2026Q3"]),
    )
    for prefixo, esperado in pares:
        bloco = ranking.loc[ranking["lente_rotulo"].str.startswith(prefixo)]
        assert list(bloco["asset_id"]) == [c["asset_id"] for c in esperado], prefixo
        for (_, linha), celula in zip(bloco.iterrows(), esperado, strict=True):
            assert int(linha["n_obs"]) == celula["n_obs"]
            assert float(linha["excesso_cdi"]) == pytest.approx(celula["excesso_cdi"], abs=1e-12)
            assert float(linha["ret_mediana"]) == pytest.approx(celula["ret_mediana"], abs=1e-12)
            assert float(linha["hit_ratio_cdi"]) == pytest.approx(
                celula["hit_ratio_cdi"], abs=1e-12
            )
            assert float(linha["erro_padrao_media"]) == pytest.approx(
                celula["erro_padrao_media"], abs=1e-12
            )


@acervo_real
def test_acervo_jaccard_top5_bate_com_o_de_f022(
    resultado_real,  # noqa: ANN001
    relatorio_metricas: dict[str, Any],
) -> None:
    """**CA-103:** o Jaccard top-5 por par é **o mesmo** que F-022 publicou (0,0 · 0,111 · 0,25)."""
    do_f022 = relatorio_metricas["concordancia_entre_lentes"]["pares"]
    pares = resultado_real.relatorio["concordancia"]["pares"]
    assert set(pares) == set(do_f022)
    for chave, dados in pares.items():
        assert dados["jaccard_top5"] == pytest.approx(do_f022[chave]["jaccard"], abs=1e-12)


@acervo_real
def test_acervo_intersecao_das_tres_lentes_e_vazia(resultado_real) -> None:  # noqa: ANN001
    """O achado de F-022 que vai ao Comitê: nenhum ativo está no top-5 das três lentes."""
    em_todas = resultado_real.relatorio["concordancia"]["em_todas_as_lentes"]
    assert em_todas[5] == []
    assert "interseção é vazia" in resultado_real.markdown_ranking


@acervo_real
def test_acervo_distribuicao_das_variantes_v3_reproduz_o_qa_p1_2(resultado_real) -> None:  # noqa: ANN001
    """**QA P1-2 medido:** 58 referências, mediana ~0,455, e o 1,0 de `2026Q3` declarado vácuo."""
    variantes = resultado_real.relatorio["concordancia"]["variantes_v3"]
    assert variantes["referencias_comparadas"] == N_REFERENCIAS_DAS_DUAS_VARIANTES
    assert variantes["mediana"] == pytest.approx(5 / 11, abs=1e-9)  # 0,4545…
    assert variantes["q1"] == pytest.approx(3 / 13, abs=1e-9)  # 0,2308…
    assert variantes["max"] == pytest.approx(1.0)
    assert variantes["min"] == pytest.approx(0.0)
    assert variantes["n_iguais_a_1"] == 7
    texto = resultado_real.markdown_ranking
    assert "**0,455**" in texto
    assert "vácuo" in texto
    assert "P1-2" in texto


@acervo_real
def test_acervo_spearman_recalculado_fora_do_modulo(resultado_real) -> None:  # noqa: ANN001
    """Spearman reconferido por Pearson-sobre-postos escrito **dentro do teste**, não importado."""
    ranking = resultado_real.ranking
    pares = resultado_real.relatorio["concordancia"]["pares"]
    for chave, dados in pares.items():
        a, b = chave.split(T.SEPARADOR_DE_PAR)
        serie_a = ranking.loc[ranking["lente_rotulo"] == a].set_index("asset_id")["excesso_cdi"]
        serie_b = ranking.loc[ranking["lente_rotulo"] == b].set_index("asset_id")["excesso_cdi"]
        comuns = sorted(set(serie_a.index) & set(serie_b.index))
        esperado = float(
            serie_a[comuns].rank(method="average").corr(serie_b[comuns].rank(method="average"))
        )
        assert dados["spearman"] == pytest.approx(esperado, abs=1e-12), chave


@acervo_real
def test_acervo_tem_72_linhas_com_n_em_toda_celula(resultado_real) -> None:  # noqa: ANN001
    """**Anti-SPEC §10.2.8 no dado real:** 3 lentes × 24 ativos, zero células sem `n`."""
    ranking = resultado_real.ranking
    assert len(ranking) == 72
    assert ranking["n_obs"].notna().all()
    assert ranking["n_obs"].min() >= 1
    assert resultado_real.relatorio["ranking"]["celulas_sem_n"] == 0
    assert resultado_real.relatorio["ranking"]["ativos_por_lente"] == 24


@acervo_real
def test_acervo_as_duas_celulas_suprimidas_sao_ifix_e_imob_da_v3(resultado_real) -> None:  # noqa: ANN001
    """**CA-099 no dado real:** as 2 células com `n = 4` são as que F-021/F-022 apontaram."""
    ranking = resultado_real.ranking
    suprimidas = ranking.loc[ranking["conclusao_suprimida"]]
    assert sorted(suprimidas["asset_id"]) == ["IFIX", "IMOB"]
    assert set(suprimidas["lente"]) == {LENTE_V3}
    assert set(suprimidas["n_obs"]) == {4}
    assert set(suprimidas["simbolo_n"]) == {T.SIMBOLO_N_SUPRIMIDO}


@acervo_real
def test_acervo_gate_de_publicacao_fechado_e_na_pagina(resultado_real) -> None:  # noqa: ANN001
    """**CA-090:** ADR-001 em `Proposta` ⇒ não publicável, e a página carrega a marca."""
    gate = resultado_real.relatorio["gate_de_publicacao"]
    assert gate["especificacao_congelada"] is False
    assert gate["marca"] == T.MARCA_NAO_CONGELADA
    # O aviso que vai ao `logging` é ASCII puro: cp1252 no console não engole o acentuado,
    # e um `--- Logging error ---` no lugar do aviso de CA-090 é o pior desfecho possível.
    assert T.MARCA_NAO_CONGELADA_ASCII.isascii()
    assert "NAO CONGELADA" in gate["veredito"]
    assert T.MARCA_NAO_CONGELADA in resultado_real.markdown_ranking
    assert T.MARCA_NAO_CONGELADA in resultado_real.markdown_concordancia


@acervo_real
def test_acervo_markdown_real_nao_tem_linguagem_preditiva(resultado_real) -> None:  # noqa: ANN001
    """**Anti-SPEC §10.2.10 no entregável real** — é o texto que vai ao slide."""
    T.conferir_linguagem_descritiva(resultado_real.markdown_ranking)
    T.conferir_linguagem_descritiva(resultado_real.markdown_concordancia)


@acervo_real
def test_acervo_duas_construcoes_dao_os_mesmos_bytes(resultado_real) -> None:  # noqa: ANN001
    """**CA-121:** nada lê o relógio — duas construções dão Parquet, CSV e Markdown idênticos."""
    outra = T.construir(gravar=False)
    assert outra.markdown_ranking == resultado_real.markdown_ranking
    assert outra.markdown_concordancia == resultado_real.markdown_concordancia
    assert outra.ranking.to_parquet(index=False) == resultado_real.ranking.to_parquet(index=False)
    assert outra.concordancia.to_parquet(index=False) == resultado_real.concordancia.to_parquet(
        index=False
    )


@acervo_real
def test_acervo_hashes_do_rodape_sao_os_dos_arquivos_em_disco(resultado_real) -> None:  # noqa: ANN001
    """O `sha256` do rodapé é o do byte do arquivo, conferido fora do módulo."""
    import hashlib

    for nome, digest in resultado_real.relatorio["hashes_dos_insumos"].items():
        esperado = hashlib.sha256(caminho_canonical(nome).read_bytes()).hexdigest()
        assert digest == esperado, nome
        assert digest in resultado_real.markdown_ranking


@acervo_real
def test_acervo_arquivos_gravados_batem_com_o_recalculo() -> None:
    """Os 6 arquivos em `data/canonical/tabelas/` são o que o módulo produz agora."""
    pasta = T.caminho_tabelas()
    if not pasta.is_dir():
        pytest.skip(f"tabelas ainda não geradas — {COMO_GERAR}")
    resultado = T.construir(gravar=False)
    md = pasta / f"{T.NOME_RANKING}.md"
    if md.is_file():
        assert md.read_text(encoding="utf-8") == resultado.markdown_ranking
    md_concordancia = pasta / f"{T.NOME_CONCORDANCIA}.md"
    if md_concordancia.is_file():
        assert md_concordancia.read_text(encoding="utf-8") == resultado.markdown_concordancia
