"""F-022 — testes unitários de `apps/pipeline/canonical/metricas_regime.py`. **Classe C.**

| Bloco | O que cobre | CA |
|---|---|---|
| 1 | excesso por **razão** vs. subtração — a média da razão ≠ média das subtrações | CA-069 |
| 2 | média/mediana lado a lado, desvio, erro-padrão = desvio/√n | CA-092 |
| 3 | `hit_ratio` e `hit_ratio_cdi` | CA-092 |
| 4 | Sharpe trimestral: desvio 0 → `None`, `n < 2` → `None`, anualização declarada | CA-094 |
| 5 | drawdown = `pior_tri`/`melhor_tri` com data; contiguidade | metodologia §3 |
| 6 | flags de `n`: `n < 8` alerta, `n < 5` suprime **mantendo a linha** | CA-108, CA-109 |
| 7 | janela própria do ativo: `n_obs` só dos trimestres dele | CA-093 |
| 8 | horizonte T0 × T+1 e os vizinhos da V3 | CA-102 |
| 9 | `beta_ibov` e a junção de **D-r** (`regimes.parquet`) | CA-088 |
| 10 | **acervo real** `data/canonical/` — padrão `Acervo` | todos |

Todo dado deste arquivo fora do bloco 10 é **sintético e nomeado como tal** (Anti-SPEC §10.1.2).
O bloco 10 segue o padrão `Acervo` de `test_canonical_regimes_v1.py §9`: nunca falha por ausência
de `data/` (que não está no git), e entra por acréscimo quando o Parquet existe.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd
import pytest

from apps.pipeline.canonical import metricas_regime as M
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.asset_returns_quarterly import RegimeAssetMetricsSchema
from packages.shared.schemas.regimes import (
    N_ALERTA,
    N_SUPRESSAO,
    MetricaDistancia,
    RegimesSchema,
    RegimeV1,
    StatusRegimeV1,
)

COMO_GERAR = "rode `uv run python -m apps.pipeline.canonical.metricas_regime`"

# ─────────────────────────────────────────────────────────────────────────────
# Ajudantes sintéticos
# ─────────────────────────────────────────────────────────────────────────────


def _quarters(n: int, *, ano_inicial: int = 2010) -> list[str]:
    """`n` trimestres consecutivos a partir de `{ano_inicial}Q1`."""
    periodos = pd.period_range(f"{ano_inicial}Q1", periods=n, freq="Q")
    return [f"{p.year}Q{p.quarter}" for p in periodos]


def _celula_sintetica(
    *,
    nominal: list[float | None],
    excesso: list[float | None] | None = None,
    real: list[float | None] | None = None,
    quarters: list[str] | None = None,
) -> pd.DataFrame:
    """A fatia que `metricas_da_celula` recebe — **dado sintético**, nomeado como tal."""
    rotulos = quarters or _quarters(len(nominal))
    return pd.DataFrame(
        {
            "quarter": rotulos,
            M.COLUNA_NOMINAL: nominal,
            M.COLUNA_PRIMARIA: excesso if excesso is not None else nominal,
            M.COLUNA_REAL: real if real is not None else nominal,
        }
    )


def _metricas(
    celula: pd.DataFrame,
    *,
    asset_id: str = "IBOV",
    referencia: pd.Series | None = None,
) -> dict:
    """`metricas_da_celula` com os parâmetros fixos que não interessam ao teste em questão."""
    return M.metricas_da_celula(
        celula,
        lente=M.LENTE_V1,
        regime=RegimeV1.RECUPERACAO.value,
        asset_id=asset_id,
        data_inicio_serie=pd.Timestamp("2006-01-02"),
        referencia_beta=referencia if referencia is not None else pd.Series(dtype="float64"),
        fonte_versao="f" * 64,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Excesso sobre CDI: razão, nunca subtração (CA-069, Anti-SPEC §10.2.13)
# ─────────────────────────────────────────────────────────────────────────────


def test_excesso_por_razao_reproduz_o_numero_de_ca069() -> None:
    """CA-069 ao pé da letra: `r=0,10`, `cdi=0,0325` → 0,06538..., **não** 0,0675."""
    obtido = M.excesso_por_razao(0.10, 0.0325)
    assert obtido == pytest.approx(0.065375302663438, abs=1e-12)
    assert obtido != pytest.approx(0.10 - 0.0325, abs=1e-6)


def test_media_do_excesso_por_razao_nao_e_a_media_das_subtracoes() -> None:
    """O ponto central de CA-069 **na agregação**: agregar razões ≠ agregar subtrações.

    Três trimestres com CDI de dois dígitos ao ano. A média das razões e a média das subtrações
    diferem em mais de 0,1 pp — e é essa diferença que a Anti-SPEC §10.2.13 proíbe de ignorar.
    """
    retornos = [0.10, -0.05, 0.22]
    cdis = [0.0325, 0.0290, 0.0350]
    razoes = [M.excesso_por_razao(r, c) for r, c in zip(retornos, cdis, strict=True)]
    subtracoes = [r - c for r, c in zip(retornos, cdis, strict=True)]

    media_razao = M.media_do_excesso(pd.Series(razoes))
    media_subtracao = float(np.mean(subtracoes))

    assert media_razao is not None
    assert media_razao != pytest.approx(media_subtracao, abs=1e-6)
    assert abs(media_razao - media_subtracao) > 0.001


def test_media_do_excesso_nao_recalcula_a_coluna_apenas_agrega() -> None:
    """`media_do_excesso` é média aritmética da coluna já calculada por razão em F-017."""
    serie = pd.Series([0.01, 0.03, None, 0.05])
    assert M.media_do_excesso(serie) == pytest.approx(0.03)


def test_media_do_excesso_de_celula_vazia_e_none_nunca_zero() -> None:
    """Célula sem observação devolve `None`. `0` significaria "empatou com o CDI"."""
    assert M.media_do_excesso(pd.Series(dtype="float64")) is None
    assert M.media_do_excesso(pd.Series([None, None], dtype="float64")) is None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Média, mediana, desvio e erro-padrão (CA-092)
# ─────────────────────────────────────────────────────────────────────────────


def test_media_e_mediana_aparecem_lado_a_lado() -> None:
    """CA-092: as duas na mesma célula. Um outlier separa uma da outra, e isso é o sinal."""
    celula = _celula_sintetica(nominal=[0.01, 0.02, 0.03, 0.04, 0.90])
    saida = _metricas(celula)
    assert saida["ret_medio"] == pytest.approx(0.20)
    assert saida["ret_mediana"] == pytest.approx(0.03)
    assert saida["ret_medio"] != pytest.approx(saida["ret_mediana"])


def test_erro_padrao_e_desvio_dividido_por_raiz_de_n() -> None:
    """CA-092 literal: `erro_padrao_media == ret_desvio / sqrt(n_obs)`."""
    celula = _celula_sintetica(nominal=[0.05, -0.02, 0.11, 0.00, 0.07, -0.09])
    saida = _metricas(celula)
    esperado = saida["ret_desvio"] / np.sqrt(saida["n_obs"])
    assert saida["erro_padrao_media"] == pytest.approx(esperado, abs=1e-15)


def test_desvio_e_amostral_ddof_1_e_nao_populacional() -> None:
    """`ddof=1`. Com `ddof=0` o número é menor e o erro-padrão subestima o ruído."""
    valores = [0.05, -0.02, 0.11, 0.00]
    celula = _celula_sintetica(nominal=list(valores))
    saida = _metricas(celula)
    assert saida["ret_desvio"] == pytest.approx(float(pd.Series(valores).std(ddof=1)))
    assert saida["ret_desvio"] != pytest.approx(float(np.std(valores)), abs=1e-9)


def test_desvio_e_erro_padrao_com_uma_observacao_sao_none() -> None:
    """`n = 1` não tem dispersão. `0` seria afirmar certeza onde não há amostra."""
    saida = _metricas(_celula_sintetica(nominal=[0.07]))
    assert saida["n_obs"] == 1
    assert saida["ret_medio"] == pytest.approx(0.07)
    assert saida["ret_desvio"] is None
    assert saida["erro_padrao_media"] is None


def test_erro_padrao_de_12_por_cento_com_n_20_fica_perto_de_2_7_pp() -> None:
    """A nota de potência de `metodologia §3`, verificada: ~2,7 pp com n=20 e desvio de 12%."""
    assert M.erro_padrao(0.12, 20) == pytest.approx(0.02683, abs=1e-4)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Hit ratios (CA-092)
# ─────────────────────────────────────────────────────────────────────────────


def test_hit_ratio_conta_estritamente_positivos() -> None:
    """Retorno exatamente `0` **não** conta como acerto — empatar não é bater."""
    assert M.hit_ratio(pd.Series([0.1, -0.1, 0.0, 0.2])) == pytest.approx(0.5)


def test_hit_ratio_ignora_nulo_em_vez_de_tratar_como_perda() -> None:
    """Nulo é ausência de observação (Anti-SPEC §10.1.4), não um trimestre perdido."""
    assert M.hit_ratio(pd.Series([0.1, None, 0.2, None])) == pytest.approx(1.0)


def test_hit_ratio_cdi_sai_do_excesso_nao_do_nominal() -> None:
    """A métrica que o Comitê usa: % de trimestres em que **bateu o CDI**, não em que subiu."""
    celula = _celula_sintetica(
        nominal=[0.04, 0.02, 0.01, 0.03],
        excesso=[0.01, -0.01, -0.02, 0.00],
    )
    saida = _metricas(celula)
    assert saida["hit_ratio"] == pytest.approx(1.0)
    assert saida["hit_ratio_cdi"] == pytest.approx(0.25)


def test_hit_ratio_de_celula_vazia_e_none() -> None:
    """Sem observação não há fração. `0.0` diria "nunca bateu", que é outra afirmação."""
    assert M.hit_ratio(pd.Series(dtype="float64")) is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Sharpe trimestral (CA-094)
# ─────────────────────────────────────────────────────────────────────────────


def test_sharpe_e_media_do_excesso_sobre_desvio_do_excesso() -> None:
    """A fórmula deste módulo, explícita — e é sobre o excesso **por razão**."""
    excessos = pd.Series([0.02, -0.01, 0.04, 0.00])
    esperado = float(excessos.mean()) / float(excessos.std(ddof=1))
    assert M.sharpe_trimestral(excessos) == pytest.approx(esperado, abs=1e-15)


def test_sharpe_com_desvio_zero_e_none_nunca_infinito() -> None:
    """O caso da linha `CDI` (excesso identicamente ~0): `None`, não `inf` nem `nan`."""
    assert M.sharpe_trimestral(pd.Series([0.01, 0.01, 0.01, 0.01])) is None
    assert M.sharpe_trimestral(pd.Series([0.0, 0.0, 0.0])) is None


def test_sharpe_com_menos_de_duas_observacoes_e_none() -> None:
    """`n < 2` não tem desvio amostral, logo não tem Sharpe."""
    assert M.sharpe_trimestral(pd.Series([0.03])) is None
    assert M.sharpe_trimestral(pd.Series(dtype="float64")) is None


def test_sharpe_na_celula_usa_o_excesso_e_nao_o_nominal() -> None:
    """Na célula completa, `sharpe_tri` ignora `ret_tri` — é o excesso que entra."""
    celula = _celula_sintetica(
        nominal=[0.10, 0.10, 0.10, 0.10],
        excesso=[0.02, -0.01, 0.04, 0.00],
    )
    saida = _metricas(celula)
    assert saida["sharpe_tri"] == pytest.approx(M.sharpe_trimestral(celula[M.COLUNA_PRIMARIA]))


def test_anualizacao_e_raiz_de_4_e_nunca_entra_na_coluna() -> None:
    """CA-094: o fator é `sqrt(4) = 2`, aplicado **só** no relatório, e declarado."""
    assert pytest.approx(np.sqrt(4)) == M.FATOR_ANUALIZACAO_SHARPE
    assert M.sharpe_anualizado(0.5) == pytest.approx(1.0)
    assert M.sharpe_anualizado(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Drawdown: pior/melhor trimestre com data (metodologia §3)
# ─────────────────────────────────────────────────────────────────────────────


def test_pior_e_melhor_trazem_valor_e_data() -> None:
    """O drawdown desta tabela: mínimo e máximo, cada um com o trimestre."""
    celula = _celula_sintetica(
        nominal=[0.05, -0.30, 0.12, -0.02],
        quarters=["2010Q1", "2010Q2", "2010Q3", "2010Q4"],
    )
    saida = _metricas(celula)
    assert saida["pior_tri"] == pytest.approx(-0.30)
    assert saida["pior_tri_quarter"] == "2010Q2"
    assert saida["melhor_tri"] == pytest.approx(0.12)
    assert saida["melhor_tri_quarter"] == "2010Q3"


def test_pior_tri_ignora_nulo_e_pega_o_trimestre_do_valor() -> None:
    """Trimestre sem observação não pode ser o pior — não existe retorno nele."""
    celula = _celula_sintetica(
        nominal=[None, -0.10, 0.04],
        quarters=["2010Q1", "2010Q2", "2010Q3"],
    )
    saida = _metricas(celula)
    assert saida["n_obs"] == 2
    assert saida["pior_tri_quarter"] == "2010Q2"


def test_empate_no_pior_resolve_pelo_trimestre_mais_antigo() -> None:
    """Determinismo: dois trimestres com o mesmo mínimo → o mais antigo, sempre."""
    celula = _celula_sintetica(
        nominal=[-0.10, 0.05, -0.10],
        quarters=["2010Q1", "2010Q2", "2010Q3"],
    )
    assert _metricas(celula)["pior_tri_quarter"] == "2010Q1"


def test_pior_e_melhor_de_celula_vazia_sao_none() -> None:
    """Sem observação, nem valor nem data — e a linha continua existindo."""
    saida = _metricas(_celula_sintetica(nominal=[None, None]))
    assert saida["n_obs"] == 0
    assert saida["pior_tri"] is None
    assert saida["pior_tri_quarter"] is None
    assert saida["melhor_tri_quarter"] is None


def test_contiguidade_conta_blocos_e_o_maior_bloco() -> None:
    """A medida que justifica `pior_tri` em vez de max-drawdown."""
    assert M.contiguidade(["2010Q1", "2010Q2", "2010Q3"]) == {
        "n_trimestres": 3,
        "n_blocos": 1,
        "maior_bloco": 3,
    }
    assert M.contiguidade(["2010Q1", "2011Q1", "2011Q2"]) == {
        "n_trimestres": 3,
        "n_blocos": 2,
        "maior_bloco": 2,
    }
    assert M.contiguidade([]) == {"n_trimestres": 0, "n_blocos": 0, "maior_bloco": 0}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Flags de `n` (CA-108, CA-109)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [0, 1, 4])
def test_n_abaixo_de_5_suprime_conclusao_e_acende_alerta(n: int) -> None:
    """CA-109: `n < 5` suprime a **conclusão**; CA-108 também acende com `n < 8`."""
    saida = _metricas(_celula_sintetica(nominal=[0.01] * n if n else [None]))
    assert saida["n_obs"] == n
    assert saida["conclusao_suprimida"] is True
    assert saida["alerta_n_baixo"] is True


@pytest.mark.parametrize("n", [5, 6, 7])
def test_n_entre_5_e_7_alerta_mas_nao_suprime(n: int) -> None:
    """A faixa intermediária: hachura no heatmap, conclusão ainda permitida."""
    saida = _metricas(_celula_sintetica(nominal=[0.01, 0.02] * 4)[:n])
    assert saida["n_obs"] == n
    assert saida["alerta_n_baixo"] is True
    assert saida["conclusao_suprimida"] is False


@pytest.mark.parametrize("n", [8, 12, 20])
def test_n_de_8_em_diante_nao_acende_flag(n: int) -> None:
    """`N_ALERTA = 8` é o piso **inclusivo**: `n = 8` não é `n` baixo."""
    saida = _metricas(_celula_sintetica(nominal=[0.01] * n))
    assert saida["alerta_n_baixo"] is False
    assert saida["conclusao_suprimida"] is False


def test_celula_com_n_abaixo_de_5_mantem_a_linha_com_os_numeros() -> None:
    """CA-109 **não** é apagar a célula: suprimir a conclusão é outra coisa que suprimir o dado."""
    celula = _celula_sintetica(nominal=[0.10, -0.04, 0.06], excesso=[0.06, -0.07, 0.02])
    saida = _metricas(celula)
    assert saida["conclusao_suprimida"] is True
    assert saida["n_obs"] == 3
    assert saida["ret_medio"] is not None
    assert saida["excesso_cdi"] is not None
    assert saida["hit_ratio_cdi"] is not None


def test_celula_sem_observacao_continua_na_tabela_com_n_zero() -> None:
    """Anti-SPEC §10.2.8/CA-095: `n` em **toda** célula — inclusive a vazia, com `n = 0`."""
    saida = _metricas(_celula_sintetica(nominal=[]))
    assert saida["n_obs"] == 0
    assert saida["excesso_cdi"] is None
    assert saida["conclusao_suprimida"] is True
    assert saida["data_inicio_serie"] == pd.Timestamp("2006-01-02")


def test_limiares_vem_do_schema_nao_de_numero_solto() -> None:
    """Os pisos são constantes do contrato (`packages/shared/schemas/regimes.py`)."""
    assert (N_ALERTA, N_SUPRESSAO) == (8, 5)
    assert M.DICIONARIO_DE_METRICAS["alerta_n_baixo"].startswith(f"n_obs < {N_ALERTA}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Janela própria do ativo (CA-093)
# ─────────────────────────────────────────────────────────────────────────────


def _regimes_v1_sintetico(mapa: dict[str, str | None]) -> pd.DataFrame:
    """Uma tabela mínima no formato de `regimes_v1.parquet` — **sintética**."""
    return pd.DataFrame(
        {
            "quarter": list(mapa),
            "regime_v1": [mapa[q] for q in mapa],
            "status_regime_v1": [
                StatusRegimeV1.CLASSIFICADO.value if mapa[q] else StatusRegimeV1.INDETERMINADO.value
                for q in mapa
            ],
        }
    )


def _retornos_sintetico(linhas: list[tuple[str, str, float | None]]) -> pd.DataFrame:
    """`(quarter, asset_id, ret)` → o formato de `asset_returns_quarterly` — **sintético**."""
    quadro = pd.DataFrame(linhas, columns=["quarter", "asset_id", M.COLUNA_NOMINAL])
    quadro[M.COLUNA_PRIMARIA] = quadro[M.COLUNA_NOMINAL]
    quadro[M.COLUNA_REAL] = quadro[M.COLUNA_NOMINAL]
    quadro["data_inicio_serie"] = pd.Timestamp("2010-12-30")
    return quadro


def test_n_obs_reflete_so_os_trimestres_existentes_do_ativo() -> None:
    """CA-093: ativo de janela curta (IFIX começa em 2010Q4) tem `n_obs` só dos seus trimestres.

    O regime tem 4 trimestres; o IFIX só existe em 2 deles. `n_obs` tem de ser 2 — nunca 4 com
    dois zeros, que é o backfill sintético que a Anti-SPEC §10.1.1/§10.1.4 proíbe.
    """
    regimes = _regimes_v1_sintetico(
        {
            "2010Q1": RegimeV1.RECUPERACAO.value,
            "2010Q2": RegimeV1.RECUPERACAO.value,
            "2011Q1": RegimeV1.RECUPERACAO.value,
            "2011Q2": RegimeV1.RECUPERACAO.value,
        }
    )
    retornos = _retornos_sintetico(
        [
            ("2011Q1", "IFIX", 0.03),
            ("2011Q2", "IFIX", 0.01),
            ("2010Q1", "IBOV", 0.05),
            ("2010Q2", "IBOV", -0.02),
            ("2011Q1", "IBOV", 0.04),
            ("2011Q2", "IBOV", 0.00),
        ]
    )
    bloco = M._celulas(
        lente=M.LENTE_V1,
        grupos=M.trimestres_por_regime_v1(regimes),
        retornos=retornos,
        horizonte=M.Horizonte.CONTEMPORANEO,
        ativos=["IBOV", "IFIX"],
        inicio={"IBOV": pd.Timestamp("2006-01-02"), "IFIX": pd.Timestamp("2010-12-30")},
        fonte_versao="f" * 64,
    )
    por_ativo = {linha["asset_id"]: linha for linha in bloco if linha["regime"] == "RECUPERACAO"}
    assert por_ativo["IFIX"]["n_obs"] == 2
    assert por_ativo["IBOV"]["n_obs"] == 4
    assert por_ativo["IFIX"]["ret_medio"] == pytest.approx(0.02)


def test_trimestres_indeterminados_nao_viram_um_quinto_rotulo() -> None:
    """D-m: `regime_v1` nulo fica **fora** das células; não é regime nem entra em outro."""
    regimes = _regimes_v1_sintetico(
        {
            "2010Q1": RegimeV1.RECUPERACAO.value,
            "2010Q2": None,
            "2010Q3": RegimeV1.ESTAGFLACAO.value,
        }
    )
    grupos = M.trimestres_por_regime_v1(regimes)
    assert set(grupos) == {r.value for r in RegimeV1}
    assert grupos[RegimeV1.RECUPERACAO.value] == ["2010Q1"]
    assert grupos[RegimeV1.ESTAGFLACAO.value] == ["2010Q3"]
    assert "2010Q2" not in [q for quarters in grupos.values() for q in quarters]
    assert StatusRegimeV1.INDETERMINADO.value not in grupos


# ─────────────────────────────────────────────────────────────────────────────
# 8. Horizonte T0 × T+1 (CA-102)
# ─────────────────────────────────────────────────────────────────────────────


def test_quarter_do_horizonte_contemporaneo_e_o_proprio_trimestre() -> None:
    """Horizonte `T0` não desloca nada."""
    assert M.quarter_do_horizonte("2014Q3", M.Horizonte.CONTEMPORANEO) == "2014Q3"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("2014Q3", "2014Q4"), ("2014Q4", "2015Q1"), ("2006Q1", "2006Q2")],
)
def test_quarter_do_horizonte_t_mais_1_atravessa_o_ano(entrada: str, esperado: str) -> None:
    """`T+1` de `Q4` é o `Q1` do ano seguinte — e nunca `T-1`."""
    assert M.quarter_do_horizonte(entrada, M.Horizonte.T_MAIS_1) == esperado


def test_horizonte_t_mais_1_mede_o_trimestre_seguinte_nunca_o_proprio() -> None:
    """CA-102 na célula: regime em `2010Q1` com horizonte `T+1` lê o retorno de `2010Q2`."""
    regimes = _regimes_v1_sintetico({"2010Q1": RegimeV1.RECUPERACAO.value})
    retornos = _retornos_sintetico([("2010Q1", "IBOV", 0.50), ("2010Q2", "IBOV", -0.10)])
    comum = {
        "lente": M.LENTE_V1,
        "grupos": M.trimestres_por_regime_v1(regimes),
        "retornos": retornos,
        "ativos": ["IBOV"],
        "inicio": {"IBOV": pd.Timestamp("2006-01-02")},
        "fonte_versao": "f" * 64,
    }
    t0 = M._celulas(horizonte=M.Horizonte.CONTEMPORANEO, **comum)
    t1 = M._celulas(horizonte=M.Horizonte.T_MAIS_1, **comum)
    celula_t0 = next(c for c in t0 if c["regime"] == "RECUPERACAO")
    celula_t1 = next(c for c in t1 if c["regime"] == "RECUPERACAO")
    assert celula_t0["ret_medio"] == pytest.approx(0.50)
    assert celula_t1["ret_medio"] == pytest.approx(-0.10)
    assert celula_t1["pior_tri_quarter"] == "2010Q2"


def test_observacoes_dos_vizinhos_em_t_mais_1_usa_a_funcao_de_f021() -> None:
    """A junção vizinho → `T+1` vem de `regimes_v3.retornos_em_t_mais_1` (importada)."""
    vizinhos = [M.Vizinho(rank=1, quarter="2010Q1", distancia=0.5)]
    retornos = _retornos_sintetico(
        [("2010Q1", "IBOV", 0.50), ("2010Q2", "IBOV", -0.10), ("2010Q3", "IBOV", 0.07)]
    )
    saida = M.observacoes_dos_vizinhos(vizinhos, retornos, horizonte=M.Horizonte.T_MAIS_1)
    assert list(saida["quarter"]) == ["2010Q2"]
    assert list(saida["quarter_vizinho"]) == ["2010Q1"]
    assert set(M.COLUNAS_DE_RETORNO).issubset(saida.columns)


def test_observacoes_dos_vizinhos_contemporaneo_le_o_proprio_vizinho() -> None:
    """A metade "horizonte cruzado": retorno **no** vizinho, declarado como sensibilidade."""
    vizinhos = [M.Vizinho(rank=1, quarter="2010Q1", distancia=0.5)]
    retornos = _retornos_sintetico([("2010Q1", "IBOV", 0.50), ("2010Q2", "IBOV", -0.10)])
    saida = M.observacoes_dos_vizinhos(vizinhos, retornos, horizonte=M.Horizonte.CONTEMPORANEO)
    assert list(saida["quarter"]) == ["2010Q1"]


def test_vizinho_sem_t_mais_1_nao_contribui_e_aparece_no_n() -> None:
    """Vizinho no fim da janela: `T+1` não existe, o `n` cai — não vira o retorno do vizinho."""
    vizinhos = [
        M.Vizinho(rank=1, quarter="2010Q1", distancia=0.5),
        M.Vizinho(rank=2, quarter="2026Q3", distancia=0.9),
    ]
    retornos = _retornos_sintetico([("2010Q2", "IBOV", -0.10), ("2026Q3", "IBOV", 0.33)])
    saida = M.observacoes_dos_vizinhos(vizinhos, retornos, horizonte=M.Horizonte.T_MAIS_1)
    assert list(saida["quarter"]) == ["2010Q2"]
    assert "2026Q3" not in list(saida["quarter"])


def test_nome_do_regime_v3_declara_a_referencia() -> None:
    """O "regime" da V3 é o conjunto de momentos parecidos com uma referência nomeada."""
    assert M.nome_do_regime_v3("2026Q3") == "VIZINHOS_2026Q3"
    assert M.nome_do_regime_v3().startswith(M.PREFIXO_REGIME_V3)


def test_vizinhos_da_lente_canonica_recusa_tabela_sem_a_lente() -> None:
    """Lente ausente é `BLOQUEADO — FONTE INDISPONÍVEL`, nunca uma lista vazia silenciosa."""
    vazia = pd.DataFrame(
        {
            "quarter_ref": ["2026Q3"],
            "rank": [1],
            "quarter_neighbor": ["2006Q3"],
            "distancia": [1.0],
            "metrica": [MetricaDistancia.EUCLIDIANA.value],
            "k_usado": [8],
            "somente_passado": [False],
            "restrito_pos_2016": [False],
        }
    )
    with pytest.raises(FonteIndisponivel, match="lente canonica"):
        M.vizinhos_da_lente_canonica(vazia)


def test_vizinhos_da_lente_canonica_ignora_as_outras_23_combinacoes() -> None:
    """A lente é `mahalanobis` / `k=8` / `somente_passado=False` / `pos2016=False` (D-u)."""
    base = {
        "quarter_ref": "2026Q3",
        "quarter_neighbor": "2006Q3",
        "distancia": 1.0,
        "k_usado": 8,
    }
    tabela = pd.DataFrame(
        [
            {
                **base,
                "rank": 1,
                "metrica": MetricaDistancia.MAHALANOBIS.value,
                "somente_passado": False,
                "restrito_pos_2016": False,
            },
            {
                **base,
                "rank": 1,
                "metrica": MetricaDistancia.MAHALANOBIS.value,
                "somente_passado": True,
                "restrito_pos_2016": False,
            },
            {
                **base,
                "rank": 1,
                "metrica": MetricaDistancia.EUCLIDIANA.value,
                "somente_passado": False,
                "restrito_pos_2016": False,
            },
        ]
    )
    assert len(M.vizinhos_da_lente_canonica(tabela)) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 9. `beta_ibov` e a junção de D-r
# ─────────────────────────────────────────────────────────────────────────────


def test_beta_contra_si_mesmo_e_um() -> None:
    """Sanity check do beta: `beta(x, x) == 1`."""
    serie = pd.Series([0.05, -0.02, 0.11, 0.00], index=_quarters(4))
    assert M.beta_vs_referencia(serie, serie) == pytest.approx(1.0)


def test_beta_de_serie_dobrada_e_dois() -> None:
    """`beta(2x, x) == 2` — a álgebra, sem depender de dado real."""
    ref = pd.Series([0.05, -0.02, 0.11, 0.00], index=_quarters(4))
    assert M.beta_vs_referencia(ref * 2, ref) == pytest.approx(2.0)


def test_beta_alinha_por_quarter_e_nao_por_posicao() -> None:
    """As séries entram indexadas por `quarter`; desalinhar em silêncio é o bug clássico."""
    ref = pd.Series([0.05, -0.02, 0.11], index=["2010Q1", "2010Q2", "2010Q3"])
    ativo = pd.Series([0.10, -0.04], index=["2010Q2", "2010Q3"])
    esperado = M.beta_vs_referencia(ativo, ref.loc[["2010Q2", "2010Q3"]])
    assert M.beta_vs_referencia(ativo, ref) == pytest.approx(esperado)


def test_beta_com_referencia_constante_e_none() -> None:
    """Variância zero na referência: `None`, não divisão por zero."""
    ref = pd.Series([0.01, 0.01, 0.01], index=_quarters(3))
    ativo = pd.Series([0.02, 0.05, -0.01], index=_quarters(3))
    assert M.beta_vs_referencia(ativo, ref) is None


def test_beta_com_menos_de_dois_pares_e_none() -> None:
    """Um ponto em comum não define covariância."""
    ref = pd.Series([0.01], index=["2010Q1"])
    ativo = pd.Series([0.02, 0.05], index=["2010Q1", "2010Q2"])
    assert M.beta_vs_referencia(ativo, ref) is None


def _macro_sintetico(quarters: list[str], deltas: list[float | None]) -> pd.DataFrame:
    """O mínimo de `macro_quarterly` que a junção consome — **sintético**."""
    return pd.DataFrame({"quarter": quarters, "selic_meta_delta": deltas})


def _regimes_v1_completo(mapa: dict[str, str | None]) -> pd.DataFrame:
    """Uma `regimes_v1` com **todas** as colunas de `COLUNAS_V1_DE_REGIMES` — sintética."""
    quadro = _regimes_v1_sintetico(mapa)
    quadro["g_score"] = 1.0
    quadro["pi_score"] = 0.5
    quadro["n_obs_regime_v1"] = 10
    quadro["alerta_n_baixo"] = False
    quadro["lag_adjusted"] = False
    quadro["trocou_vs_revised"] = None
    quadro["especificacao_congelada"] = False
    quadro["versao_especificacao"] = "V1"
    quadro["fonte_versao"] = "a" * 64
    return quadro


def test_juncao_bloqueia_por_stress_flag_ausente_e_por_regime_v1_nulo() -> None:
    """**D-r** medido: os dois bloqueios que impedem `regimes.parquet` hoje, nomeados."""
    mapa = {q: None for q in _quarters(2, ano_inicial=2006)}
    mapa.update(dict(zip(_quarters(4, ano_inicial=2010), [r.value for r in RegimeV1], strict=True)))
    regimes = _regimes_v1_completo(mapa)
    macro = _macro_sintetico(list(mapa), [-0.50] * len(mapa))

    juncao = M.montar_regimes(regimes_v1=regimes, macro=macro)

    assert juncao.gravavel is False
    assert juncao.tabela is None
    assert len(juncao.bloqueios) == 2
    assert any("regime_v1" in b for b in juncao.bloqueios)
    assert any("stress_flag" in b for b in juncao.bloqueios)
    assert juncao.trimestres_indeterminados == sorted(_quarters(2, ano_inicial=2006))


def test_juncao_valida_contra_regimes_schema_quando_o_que_falta_e_fornecido() -> None:
    """A prova de que o que falta é **dado**, não implementação.

    Com `stress_flag` injetado (é de F-026/RF-039) e sem os `INDETERMINADO` (é D-m), a junção
    passa por `RegimesSchema` — incluindo o check `todos_os_quadrantes_povoados`. `ciclo_selic`
    vem da função publicada em `macro_quarterly.py` (**D-t**) e `regime_v2` é a concatenação que
    o próprio contrato define.
    """
    quarters = _quarters(4, ano_inicial=2010)
    mapa = dict(zip(quarters, [r.value for r in RegimeV1], strict=True))
    regimes = _regimes_v1_completo({**mapa, "2009Q4": None})
    macro = _macro_sintetico([*quarters, "2009Q4"], [-0.50, 0.75, 0.00, 0.25, -0.25])
    stress = pd.Series({q: False for q in [*quarters, "2009Q4"]})

    juncao = M.montar_regimes(
        regimes_v1=regimes, macro=macro, stress_flag=stress, somente_classificados=True
    )

    assert juncao.bloqueios == []
    assert juncao.gravavel is True
    tabela = juncao.tabela
    assert tabela is not None
    assert len(tabela) == 4
    RegimesSchema.validate(tabela, lazy=True)
    assert set(tabela["ciclo_selic"]) == {"CORTE", "ALTA", "NEUTRO"}
    for _, linha in tabela.iterrows():
        assert linha["regime_v2"] == f"{linha['regime_v1']}_{linha['ciclo_selic']}"
    assert tabela["regime_v1b"].isna().all()


def test_juncao_usa_a_desigualdade_nao_estrita_de_d_t() -> None:
    """`|Δ| >= 0,25` é **movimento**, não parada (**D-t**) — nos dois sentidos.

    ⚠️ **Correção de uma frase errada que circula no projeto.** O `relatorio_macro.json` e os
    resumos de D-t dizem "os cortes reais de 25 bps de 2024Q2/Q3". Medido em
    `macro_quarterly.parquet`: **`2024Q2 = −0,25` (CORTE) e `2024Q3 = +0,25` (ALTA — a alta de
    set/2024)**. Os **7** trimestres com `|Δ| = 0,25` exato são `2011Q3`, `2012Q4`, `2014Q2`,
    `2020Q3`, `2024Q2`, `2024Q3` e `2026Q1`: **5 `CORTE` e 2 `ALTA`**. O que D-t faz é tirar todos
    os 7 de `NEUTRO`; chamá-los de "cortes" inverte o sinal de dois deles — e `2024Q3` é
    justamente um dos vizinhos de `2026Q3` na V3, logo entra nas células desta feature.

    Por isso o teste cobre os **dois** sentidos no limiar exato, e não só o de corte.
    """
    quarters = _quarters(4, ano_inicial=2010)
    mapa = dict(zip(quarters, [r.value for r in RegimeV1], strict=True))
    macro = _macro_sintetico(quarters, [-0.25, 0.25, 0.00, -0.24])
    juncao = M.montar_regimes(
        regimes_v1=_regimes_v1_completo(mapa),
        macro=macro,
        stress_flag=pd.Series({q: False for q in quarters}),
    )
    assert juncao.tabela is not None
    ciclos = dict(zip(juncao.tabela["quarter"], juncao.tabela["ciclo_selic"], strict=True))
    assert ciclos[quarters[0]] == "CORTE"
    assert ciclos[quarters[1]] == "ALTA"
    assert ciclos[quarters[2]] == "NEUTRO"
    assert ciclos[quarters[3]] == "NEUTRO"


def test_juncao_bloqueia_quando_o_delta_da_selic_esta_ausente() -> None:
    """`ciclo_selic(None)` é `None`, nunca `NEUTRO`: pausa inventada é dado inventado."""
    quarters = _quarters(4, ano_inicial=2010)
    mapa = dict(zip(quarters, [r.value for r in RegimeV1], strict=True))
    juncao = M.montar_regimes(
        regimes_v1=_regimes_v1_completo(mapa),
        macro=_macro_sintetico(quarters, [-0.50, None, 0.75, 0.00]),
        stress_flag=pd.Series({q: False for q in quarters}),
    )
    assert juncao.gravavel is False
    assert any("ciclo_selic nulo" in b for b in juncao.bloqueios)


def test_conferir_gate_recusa_entrada_que_discorda_do_adr() -> None:
    """CA-090: Parquet gerado com outro status de ADR não entra em silêncio."""
    regimes = _regimes_v1_completo({"2010Q1": RegimeV1.RECUPERACAO.value})
    regimes["especificacao_congelada"] = True
    with pytest.raises(SerieInconsistente, match="especificacao_congelada"):
        M.conferir_gate(regimes, congelada=False)
    M.conferir_gate(_regimes_v1_completo({"2010Q1": None}), congelada=False)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Ranking e concordância entre lentes (CA-098, CA-099, CA-103)
# ─────────────────────────────────────────────────────────────────────────────


def _metricas_sinteticas(linhas: list[tuple[str, str, str, int, float | None]]) -> pd.DataFrame:
    """`(lente, regime, asset_id, n_obs, excesso)` → tabela no formato da saída — sintética."""
    quadro = pd.DataFrame(linhas, columns=["lente", "regime", "asset_id", "n_obs", "excesso_cdi"])
    for coluna in (
        "ret_medio",
        "ret_mediana",
        "erro_padrao_media",
        "hit_ratio_cdi",
        "sharpe_tri",
        "pior_tri",
    ):
        quadro[coluna] = quadro["excesso_cdi"]
    quadro["pior_tri_quarter"] = "2010Q1"
    quadro["alerta_n_baixo"] = quadro["n_obs"] < N_ALERTA
    quadro["conclusao_suprimida"] = quadro["n_obs"] < N_SUPRESSAO
    return quadro


def test_ranking_ordena_por_excesso_e_poe_celula_vazia_no_fim() -> None:
    """CA-098: ordem por `excesso_cdi`. `None` não é "o melhor" — vai para o fim."""
    tabela = _metricas_sinteticas(
        [
            ("V1", "RECUPERACAO", "IBOV", 12, 0.01),
            ("V1", "RECUPERACAO", "IFIX", 0, None),
            ("V1", "RECUPERACAO", "IMAB", 12, 0.05),
            ("V1", "ESTAGFLACAO", "IBOV", 12, 0.99),
        ]
    )
    ranking = M.ranking_do_regime(tabela, lente="V1", regime="RECUPERACAO")
    assert [c["asset_id"] for c in ranking] == ["IMAB", "IBOV", "IFIX"]
    assert ranking[-1]["excesso_cdi"] is None
    assert all("n_obs" in c for c in ranking)


def test_ranking_carrega_n_e_as_duas_flags_em_toda_linha() -> None:
    """CA-095/CA-099: nenhuma linha de nenhuma tabela sai sem `n` e sem o semáforo."""
    tabela = _metricas_sinteticas(
        [("V1", "RECUPERACAO", "IBOV", 4, 0.02), ("V1", "RECUPERACAO", "IMAB", 12, 0.01)]
    )
    ranking = M.ranking_do_regime(tabela, lente="V1", regime="RECUPERACAO")
    suprimida = next(c for c in ranking if c["asset_id"] == "IBOV")
    assert suprimida["n_obs"] == 4
    assert suprimida["conclusao_suprimida"] is True
    assert suprimida["alerta_n_baixo"] is True
    assert suprimida["excesso_cdi"] == pytest.approx(0.02)


def test_top_n_ignora_celula_sem_observacao() -> None:
    """O top-5 da concordância nunca inclui um ativo que não existia no regime."""
    ranking = [
        {"asset_id": "A", "excesso_cdi": 0.05},
        {"asset_id": "B", "excesso_cdi": None},
        {"asset_id": "C", "excesso_cdi": 0.01},
    ]
    assert M.top_n_de(ranking, 5) == ["A", "C"]


def test_concordancia_reporta_divergencia_em_vez_de_omitir() -> None:
    """CA-103: a divergência é **resultado**. Jaccard, interseção e o que é exclusivo de cada."""
    rankings = {
        "V1": [{"asset_id": a, "excesso_cdi": 0.1} for a in ("A", "B", "C")],
        "V3": [{"asset_id": a, "excesso_cdi": 0.1} for a in ("B", "C", "D")],
    }
    saida = M.concordancia_entre_lentes(rankings, n=3)
    assert saida["top_por_lente"] == {"V1": ["A", "B", "C"], "V3": ["B", "C", "D"]}
    par = saida["pares"]["V1__x__V3"]
    assert par["em_comum"] == ["B", "C"]
    assert par["jaccard"] == pytest.approx(2 / 4)
    assert par["so_em_V1"] == ["A"]
    assert par["so_em_V3"] == ["D"]
    assert saida["em_todas_as_lentes"] == ["B", "C"]


# ─────────────────────────────────────────────────────────────────────────────
# 11. Acervo real (`data/canonical/`) — padrão `Acervo`
# ─────────────────────────────────────────────────────────────────────────────


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (mesma semântica de `test_canonical_regimes_v1.py`)."""
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
        M.NOME_RETORNOS,
        M.NOME_NEIGHBORS_V3,
        "macro_quarterly.parquet",
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
def _construido() -> M.ResultadoMetricas:
    """`construir(gravar=False)` memoizado — o teste não escreve em `data/`."""
    return M.construir(gravar=False)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_tres_tabelas_validam_e_tem_pk_unica() -> None:
    """As 3 tabelas passam por `RegimeAssetMetricsSchema` com PK `(lente, regime, asset_id)`."""
    for tabela in M.TABELAS:
        quadro = _construido().tabelas[tabela.rotulo]
        RegimeAssetMetricsSchema.validate(quadro, lazy=True)
        assert not quadro.duplicated(subset=["lente", "regime", "asset_id"]).any()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_tem_n_em_toda_celula_e_nenhuma_linha_sem_n() -> None:
    """Anti-SPEC §10.2.8 / CA-095 no dado: `n_obs` não é nulo em célula nenhuma."""
    for tabela in M.TABELAS:
        quadro = _construido().tabelas[tabela.rotulo]
        assert quadro["n_obs"].notna().all()
        assert (quadro["n_obs"] >= 0).all()
        assert quadro["fonte_versao"].notna().all()
        assert quadro["data_inicio_serie"].notna().all()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_flags_batem_com_os_limiares_celula_a_celula() -> None:
    """CA-108/109 no dado: as duas flags são **função** de `n_obs`, sem exceção."""
    for tabela in M.TABELAS:
        quadro = _construido().tabelas[tabela.rotulo]
        assert (quadro["alerta_n_baixo"] == (quadro["n_obs"] < N_ALERTA)).all()
        assert (quadro["conclusao_suprimida"] == (quadro["n_obs"] < N_SUPRESSAO)).all()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_erro_padrao_e_desvio_sobre_raiz_de_n_em_toda_celula() -> None:
    """CA-092 conferido nas 336 células, sem tolerância além do ponto flutuante."""
    for tabela in M.TABELAS:
        quadro = _construido().tabelas[tabela.rotulo]
        com_desvio = quadro.loc[quadro["ret_desvio"].notna()]
        esperado = com_desvio["ret_desvio"] / np.sqrt(com_desvio["n_obs"])
        assert np.allclose(com_desvio["erro_padrao_media"], esperado, atol=1e-15)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_media_do_excesso_bate_com_groupby_independente() -> None:
    """A conferência de classe C: `groupby().mean()` em pandas puro, fora do módulo.

    Recalcula `excesso_cdi` das 96 células da V1 a partir de `regimes_v1.parquet` +
    `asset_returns_quarterly.parquet`, sem passar por `metricas_da_celula`.
    """
    resultado = _construido()
    regimes = M.ler_regimes_v1()
    retornos = M.ler_retornos()
    grupos = M.trimestres_por_regime_v1(regimes)
    mapa = {q: regime for regime, quarters in grupos.items() for q in quarters}

    fatia = retornos.loc[retornos["quarter"].isin(mapa)].copy()
    fatia["regime"] = fatia["quarter"].map(mapa)
    direto = fatia.groupby(["regime", "asset_id"])[M.COLUNA_PRIMARIA].mean()

    tabela = resultado.principal
    v1 = tabela.loc[tabela["lente"] == M.LENTE_V1]
    conferidas = 0
    for _, linha in v1.iterrows():
        chave = (str(linha["regime"]), str(linha["asset_id"]))
        if chave not in direto.index:
            continue
        conferidas += 1
        assert linha["excesso_cdi"] == pytest.approx(
            float(direto.loc[chave]), abs=M.TOLERANCIA_RECALCULO_FLOAT
        )
    assert conferidas >= 90


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_cdi_tem_excesso_praticamente_zero_e_sharpe_none() -> None:
    """O sanity check de ADR-002: a linha `CDI` do heatmap é identicamente ~0."""
    tabela = _construido().principal
    cdi = tabela.loc[tabela["asset_id"] == "CDI"]
    assert len(cdi) == 5
    assert cdi["excesso_cdi"].abs().max() < 1e-12
    assert cdi["sharpe_tri"].isna().all()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_beta_do_ibov_contra_si_mesmo_e_um() -> None:
    """Sanity check do beta no dado real."""
    tabela = _construido().principal
    ibov = tabela.loc[tabela["asset_id"] == "IBOV"]
    assert np.allclose(ibov["beta_ibov"].to_numpy(dtype=float), 1.0, atol=1e-12)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_declara_o_regime_de_2026q3_como_indeterminado_na_revised() -> None:
    """O achado que vai ao Comitê: a V1 `revised` **não tem** quadrante para o trimestre dele."""
    bloco = _construido().relatorio["regime_atual"]
    assert bloco["quarter"] == "2026Q3"
    assert bloco["v1_revised"]["regime"] is None
    assert bloco["v1_revised"]["status"] == StatusRegimeV1.INDETERMINADO.value
    assert bloco["v1_revised"]["motivo_indeterminado"] == "GAP_AUSENTE"
    assert bloco["fallback_declarado"]["quarter"] == "2026Q2"
    assert bloco["ranking_v1_fallback"]


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_v3_le_os_8_vizinhos_do_comite_de_f021() -> None:
    """A lista de vizinhos é **a de F-021**, não recalculada aqui (CONTRACTS §5.2a)."""
    resultado = _construido()
    assert [v.quarter for v in resultado.vizinhos] == [
        "2006Q3",
        "2006Q4",
        "2006Q1",
        "2024Q3",
        "2014Q4",
        "2007Q1",
        "2024Q2",
        "2014Q3",
    ]
    t_mais_1 = [linha["quarter_t_mais_1"] for linha in resultado.relatorio["vizinhos_v3"]["lista"]]
    assert t_mais_1[0] == "2006Q4"
    assert "2026Q4" not in t_mais_1


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_ranking_v3_da_tabela_concorda_com_o_de_f021() -> None:
    """A tabela e `ranking_de_ativos` de F-021 medem a mesma coisa — então têm de bater."""
    relatorio = _construido().relatorio["vizinhos_v3"]
    da_tabela = {
        c["asset_id"]: (c["n_obs"], c["excesso_cdi"])
        for c in relatorio["ranking_t_mais_1_da_tabela"]
    }
    de_f021 = {
        c["asset_id"]: (c["n"], c["media"]) for c in relatorio["ranking_t_mais_1_importado_de_f021"]
    }
    assert set(da_tabela) == set(de_f021)
    for asset_id, (n, media) in de_f021.items():
        n_tabela, media_tabela = da_tabela[asset_id]
        assert n_tabela == n
        if media is None:
            assert media_tabela is None
        else:
            assert media_tabela == pytest.approx(media, abs=1e-12)


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_juncao_de_regimes_fica_bloqueada_com_os_dois_motivos() -> None:
    """**D-r** no dado real: `regimes.parquet` não é gravável, e o relatório diz por quê."""
    resultado = _construido()
    assert resultado.juncao.gravavel is False
    assert len(resultado.juncao.trimestres_indeterminados) == 16
    assert "2026Q3" in resultado.juncao.trimestres_indeterminados
    bloco = resultado.relatorio["juncao_regimes"]
    assert bloco["gravado"] is False
    assert set(bloco["derivaveis"]) == {"ciclo_selic", "regime_v2", "regime_v1b"}
    assert any("regime_v1" in b for b in bloco["bloqueios"])
    assert any("stress_flag" in b for b in bloco["bloqueios"])
    assert not caminho_canonical(M.NOME_REGIMES_JUNTOS).is_file()


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_gate_de_publicacao_fechado_e_propagado() -> None:
    """CA-090: ADR-001 em `Proposta` ⇒ nada daqui é publicável, e isso está no relatório."""
    gate = _construido().relatorio["gate_de_publicacao"]
    assert gate["especificacao_congelada"] is False
    assert gate["publicavel"] is False
    assert "NAO CONGELADA" in gate["veredito"]
    assert gate["status_do_adr"] == "PROPOSTA"


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_nenhuma_linha_com_lente_v2() -> None:
    """F-020 não existe: nenhuma célula inventa a lente V2 (`ciclo_selic` sozinho não é lente)."""
    for tabela in M.TABELAS:
        quadro = _construido().tabelas[tabela.rotulo]
        assert M.LENTE_V2 not in set(quadro["lente"])


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_duas_rodadas_dao_o_mesmo_parquet() -> None:
    """RF-048/CA-121: função pura sobre o disco — nada de relógio, nada de estado."""
    primeira = M.construir(gravar=False)
    segunda = M.construir(gravar=False)
    for tabela in M.TABELAS:
        assert primeira.tabelas[tabela.rotulo].to_parquet(index=False) == segunda.tabelas[
            tabela.rotulo
        ].to_parquet(index=False)
    assert primeira.relatorio == segunda.relatorio


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_horizonte_cruzado_difere_do_principal_na_v1() -> None:
    """Medir em `T+1` **muda** o número — é por isso que as duas tabelas existem separadas.

    As **únicas** 4 células da V1 que não mudam são as do `CDI`, cujo excesso sobre si mesmo é
    identicamente ~0 em qualquer horizonte. Elas entram na asserção como exceção **nomeada**, não
    como tolerância: se mais alguma célula ficasse igual, isto acusaria que o deslocamento de
    trimestre não aconteceu.
    """
    resultado = _construido()
    chave = ["lente", "regime", "asset_id"]
    t0 = resultado.principal.set_index(chave)["excesso_cdi"]
    t1 = resultado.tabelas[M.TABELA_HORIZONTE_CRUZADO.rotulo].set_index(chave)["excesso_cdi"]
    v1 = [i for i in t0.index if i[0] == M.LENTE_V1]
    iguais = [i for i in v1 if abs(float(t0.loc[i]) - float(t1.loc[i])) <= 1e-9]
    assert {i[2] for i in iguais} == {"CDI"}
    assert len(iguais) == 4
    assert len(v1) == 96


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_asof_difere_da_revised_como_ca074_preve() -> None:
    """A V1 troca de rótulo em 33,33% dos trimestres entre `revised` e `asof` (CA-074)."""
    resultado = _construido()
    chave = ["lente", "regime", "asset_id"]
    revised = resultado.principal.set_index(chave)
    asof = resultado.tabelas[M.TABELA_ASOF.rotulo].set_index(chave)
    comuns = [i for i in asof.index if i in revised.index]
    assert comuns
    diferentes = sum(
        1
        for i in comuns
        if abs(float(revised.loc[i, "excesso_cdi"]) - float(asof.loc[i, "excesso_cdi"])) > 1e-9
    )
    assert diferentes > 0


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_razao_vs_subtracao_tem_diferenca_material_declarada() -> None:
    """CA-069 no dado real: a diferença entre razão e subtração é publicada em pp."""
    bloco = _construido().relatorio["excesso_razao_vs_subtracao"]
    assert bloco["celulas_comparadas"] == 96
    assert bloco["max_abs_diferenca_pp"] > 0.1
    assert bloco["piores_5"]


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_concordancia_e_distribuicao_sobre_todas_as_referencias() -> None:
    """P1 do QA da Onda 3: concordância V1 × V3 é **distribuição**, não o número de `2026Q3`.

    Olhar só o último trimestre é escolher a evidência depois de ver o resultado (Anti-SPEC
    §10.2.9). Medido nas 61 referências com quadrante V1: **mediana 0,111**, nenhuma igual a 1,0,
    e `2026Q3` **fora** da distribuição porque não tem quadrante na `revised` (D-m).
    """
    bloco = _construido().relatorio["concordancia_por_referencia"]
    assert bloco["referencias_na_lente"] == 77
    assert bloco["referencias_comparadas"] == 61
    assert len(bloco["referencias_sem_quadrante_v1"]) == 16
    assert "2026Q3" in bloco["referencias_sem_quadrante_v1"]
    assert bloco["do_quarter_do_comite"] is None

    dist = bloco["distribuicao_jaccard"]
    assert 0.0 <= dist["min"] <= dist["mediana"] <= dist["max"] <= 1.0
    assert dist["n_iguais_a_1"] == 0, (
        "nenhuma referência tem top-5 idêntico entre V1 e V3 — se passar a ter, a leitura do "
        "slide muda"
    )
    assert dist["mediana"] < 0.25, "a concordância típica é baixa; é esse o recado"
    assert dist["n_zeros"] > 0

    for linha in bloco["por_referencia"]:
        assert linha["regime_v1_da_referencia"] in {r.value for r in RegimeV1}
        assert linha["jaccard"] is not None
        assert set(linha["em_comum"]) == set(linha["top_v1"]) & set(linha["top_v3_t_mais_1"])


@pytest.mark.skipif(not TEM_ACERVO, reason=MOTIVO)
def test_acervo_ciclo_selic_de_2024q3_e_alta_e_nao_corte() -> None:
    """⚠️ Correção de fato (P1 do QA): `2024Q3` é **ALTA** de 25 bps, não corte.

    A frase "os cortes reais de 25 bps de 2024Q2/Q3" circula em `relatorio_macro.json` e nos
    resumos de **D-t** e está **errada na metade**: `2024Q2 = −0,25` (CORTE) mas
    `2024Q3 = +0,25` (ALTA — a alta de set/2024). Os 7 trimestres com `|Δ| = 0,25` exato são
    5 `CORTE` e 2 `ALTA`. `2024Q3` é vizinho de `2026Q3` na V3, então o rótulo errado entraria na
    leitura desta feature.
    """
    from apps.pipeline.canonical.macro_quarterly import ciclo_selic

    macro = M.ler_macro()
    delta = dict(zip(macro["quarter"].astype(str), macro["selic_meta_delta"], strict=True))

    assert float(delta["2024Q2"]) == pytest.approx(-0.25)
    assert float(delta["2024Q3"]) == pytest.approx(+0.25)
    assert ciclo_selic(delta["2024Q2"]) == "CORTE"
    assert ciclo_selic(delta["2024Q3"]) == "ALTA"

    no_limiar = {q: v for q, v in delta.items() if abs(abs(float(v)) - 0.25) < 1e-9}
    assert len(no_limiar) == 7
    rotulos = [ciclo_selic(v) for v in no_limiar.values()]
    assert rotulos.count("CORTE") == 5
    assert rotulos.count("ALTA") == 2
    assert "NEUTRO" not in rotulos, "D-t: |Δ| >= 0,25 é movimento, nos DOIS sentidos"

    juncao = _construido().juncao
    assert juncao.distribuicao_ciclo["ALTA"] >= 2
