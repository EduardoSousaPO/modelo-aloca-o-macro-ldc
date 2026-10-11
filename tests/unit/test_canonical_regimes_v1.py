"""F-019 — testes da V1 (quadrantes crescimento x inflação). **Classe C.**

Organização, e o motivo de cada bloco:

| Bloco | O que trava | CA |
|---|---|---|
| 1 | os 4 quadrantes com valores conhecidos, e a tabela de verdade inteira | CA-078 |
| 2 | o desempate exato de `g_T`/`pi_T` = limiar, e o que ele **não** faz | CA-079 |
| 3 | eixo nulo → `INDETERMINADO` com motivo; nunca estimativa | CA-078, §10.1.1 |
| 4 | `n` por célula, alerta `n < 8`, supressão `n < 5`, desbalanceamento | CA-080, 108, 109 |
| 5 | o gate de publicação sai do **status do ADR-001 em disco** | CA-090, CA-091 |
| 6 | função pura: duas rodadas, mesmo resultado | CA-081 |
| 7 | anti-look-ahead: T não enxerga T+1 | CA-072, §10.2.7 |
| 8 | guardas de entrada (ordem, duplicata, mistura de materialização, coluna faltando) | CA-072 |
| 9 | **acervo real** `data/canonical/` — distribuição, canários, sensibilidade, hash | todos |

O bloco 9 segue o padrão `Acervo` de `test_canonical_alinhamento.py §E`: o acervo sintético **nunca
pula** (roda no CI, sem `data/`), e o acervo real entra por acréscimo quando o Parquet existe.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd
import pytest

from apps.pipeline.canonical import regimes_v1 as R
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.regimes import (
    LIMIAR_ACELERACAO_PP,
    LIMIAR_CRESCIMENTO_PP,
    N_ALERTA,
    N_QUADRANTE_MAXIMO_CA080,
    N_QUADRANTE_MINIMO_CA080,
    N_SUPRESSAO,
    VERSAO_ESPECIFICACAO_V1,
    VERSAO_ESPECIFICACAO_V1_1,
    MotivoIndeterminado,
    RegimeV1,
    StatusRegimeV1,
)

COMO_GERAR = "rode `uv run python -m apps.pipeline.canonical.regimes_v1`"

# ─────────────────────────────────────────────────────────────────────────────
# Ajudantes sintéticos — dado nomeado como sintético (Anti-SPEC §10.1.2)
# ─────────────────────────────────────────────────────────────────────────────


def _quarters(n: int, *, ano_inicial: int = 2006) -> list[str]:
    """`n` trimestres consecutivos a partir de `{ano_inicial}Q1`, na ordem do contrato."""
    saida: list[str] = []
    ano, tri = ano_inicial, 1
    for _ in range(n):
        saida.append(f"{ano}Q{tri}")
        tri += 1
        if tri == 5:
            ano, tri = ano + 1, 1
    return saida


def macro_sintetico(
    g: list[float | None],
    pi: list[float | None],
    *,
    lag_adjusted: bool = False,
    quarters: list[str] | None = None,
) -> pd.DataFrame:
    """Uma `macro_quarterly` **sintética** com as 4 colunas que a V1 consome, e só elas."""
    qs = quarters if quarters is not None else _quarters(len(g))
    return pd.DataFrame(
        {
            "quarter": qs,
            R.COLUNA_CRESCIMENTO: g,
            R.COLUNA_INFLACAO: pi,
            "lag_adjusted": [lag_adjusted] * len(qs),
        }
    )


def _uma(g: float | None, pi: float | None) -> R.Classificacao:
    """Classifica um trimestre isolado (sem herança possível) e devolve o veredito."""
    return R.classificar_trimestres(["2010Q1"], [g], [pi])[0]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Os 4 quadrantes, com valores conhecidos (CA-078)
# ─────────────────────────────────────────────────────────────────────────────

#: `(g_T, pi_T, quadrante)` — a leitura econômica de cada célula do ADR-001 §5.
QUADRANTES_CONHECIDOS = [
    (2.5, 1.0, RegimeV1.EXPANSAO_INFL, "cresce acima da tendencia com inflacao acelerando"),
    (2.5, -1.0, RegimeV1.RECUPERACAO, "cresce acima da tendencia com inflacao desacelerando"),
    (-2.5, 1.0, RegimeV1.ESTAGFLACAO, "cresce abaixo da tendencia com inflacao acelerando"),
    (-2.5, -1.0, RegimeV1.DESACELERACAO, "cresce abaixo da tendencia com inflacao desacelerando"),
]


@pytest.mark.parametrize(
    ("g", "pi", "esperado", "leitura"),
    QUADRANTES_CONHECIDOS,
    ids=[q[2].value for q in QUADRANTES_CONHECIDOS],
)
def test_os_quatro_quadrantes_com_valores_conhecidos(
    g: float, pi: float, esperado: RegimeV1, leitura: str
) -> None:
    """CA-078: cada combinação de sinais cai no quadrante que o ADR-001 §5 nomeia."""
    veredito = _uma(g, pi)
    assert veredito.regime == esperado.value, leitura
    assert veredito.status == StatusRegimeV1.CLASSIFICADO.value
    assert veredito.motivo is None
    assert veredito.crescimento_acima is (g > LIMIAR_CRESCIMENTO_PP)
    assert veredito.inflacao_acelerando is (pi > LIMIAR_ACELERACAO_PP)
    assert veredito.desempate_aplicado is False


def test_rotulo_cobre_a_tabela_de_verdade_inteira() -> None:
    """Os 4 pares de booleanos produzem os 4 rótulos distintos — nenhum fica inalcançável."""
    produzidos = {
        R.rotulo(crescimento_acima=c, inflacao_acelerando=i)
        for c in (True, False)
        for i in (True, False)
    }
    assert produzidos == set(RegimeV1)


def test_eixo_de_crescimento_invertido_erraria_2015Q4() -> None:
    """Negativo: trocar o sinal do eixo de crescimento muda o quadrante de 2015Q4.

    Prova que o canário 2015Q4 **discrimina**: com `g` invertido (+6,40 em vez de −6,40) e o mesmo
    `pi`, o rótulo vira `EXPANSAO_INFL`. Um canário que não muda quando a regra muda não testa nada.
    """
    canario = next(c for c in R.CANARIOS if c.quarter == "2015Q4")
    assert canario.g_esperado is not None
    certo = _uma(canario.g_esperado, canario.pi_esperado).regime
    invertido = _uma(-canario.g_esperado, canario.pi_esperado).regime
    assert certo == RegimeV1.ESTAGFLACAO.value
    assert invertido == RegimeV1.EXPANSAO_INFL.value
    assert certo != invertido


def test_eixo_de_inflacao_e_aceleracao_nao_nivel() -> None:
    """D3/ADR-001 §4: o eixo é `ipca_12m_delta`, e `ipca_12m` alto com delta negativo desacelera.

    É o trade-off que o ADR §Consequências registra: IPCA 12m a 10% **em queda** entra no lado
    "desacelerando". O teste existe para que a limitação seja uma escolha visível, não um bug.
    """
    assert R.COLUNA_INFLACAO == "ipca_12m_delta"
    assert _uma(1.0, -0.5).regime == RegimeV1.RECUPERACAO.value


# ─────────────────────────────────────────────────────────────────────────────
# 2. Desempate exato (CA-079)
# ─────────────────────────────────────────────────────────────────────────────


def test_empate_em_g_herda_o_sinal_de_crescimento_do_trimestre_anterior() -> None:
    """CA-079: `g_T = 0` exatamente herda o sinal de crescimento de `T-1`."""
    classificacoes = R.classificar_trimestres(_quarters(2), [1.5, 0.0], [-1.0, -1.0])
    assert [c.regime for c in classificacoes] == [RegimeV1.RECUPERACAO.value] * 2
    assert classificacoes[1].crescimento_acima is True
    assert classificacoes[1].desempate_aplicado is True
    assert classificacoes[0].desempate_aplicado is False


def test_empate_em_g_apos_trimestre_abaixo_herda_abaixo() -> None:
    """O desempate herda o sinal **real** de T-1, não um default otimista."""
    classificacoes = R.classificar_trimestres(_quarters(2), [-1.5, 0.0], [-1.0, -1.0])
    assert [c.regime for c in classificacoes] == [RegimeV1.DESACELERACAO.value] * 2
    assert classificacoes[1].crescimento_acima is False


def test_empate_em_pi_herda_o_sinal_de_inflacao_do_trimestre_anterior() -> None:
    """CA-079 vale para os dois eixos, cada um com a sua própria herança."""
    classificacoes = R.classificar_trimestres(_quarters(2), [1.0, 1.0], [0.8, 0.0])
    assert [c.regime for c in classificacoes] == [RegimeV1.EXPANSAO_INFL.value] * 2
    assert classificacoes[1].inflacao_acelerando is True


def test_empate_nos_dois_eixos_herda_os_dois() -> None:
    """Empate simultâneo não é caso especial: cada eixo herda o seu sinal de T-1."""
    classificacoes = R.classificar_trimestres(_quarters(2), [-2.0, 0.0], [3.0, 0.0])
    assert [c.regime for c in classificacoes] == [RegimeV1.ESTAGFLACAO.value] * 2
    assert classificacoes[1].crescimento_acima is False
    assert classificacoes[1].inflacao_acelerando is True


def test_empate_no_primeiro_trimestre_fica_indeterminado() -> None:
    """Sem `T-1` não há sinal para herdar — e o default seria dado inventado (§10.1.1)."""
    veredito = _uma(0.0, 1.0)
    assert veredito.regime is None
    assert veredito.status == StatusRegimeV1.INDETERMINADO.value
    assert veredito.motivo == MotivoIndeterminado.EMPATE_SEM_SINAL_ANTERIOR.value
    assert veredito.desempate_aplicado is True


def test_empate_depois_de_trimestre_sem_sinal_nao_pula_para_t_menos_2() -> None:
    """A herança é estritamente de `T-1`: `[1.5, nulo, 0.0]` não devolve o sinal de `T-2`.

    "Herdar do último trimestre que tinha sinal" é uma **regra diferente** da que o ADR-001 §5
    congela, e adotá-la aqui seria mudar a especificação em silêncio (Anti-SPEC §10.2.9).
    """
    classificacoes = R.classificar_trimestres(_quarters(3), [1.5, None, 0.0], [-1.0, -1.0, -1.0])
    assert classificacoes[0].regime == RegimeV1.RECUPERACAO.value
    assert classificacoes[1].motivo == MotivoIndeterminado.GAP_AUSENTE.value
    assert classificacoes[2].regime is None
    assert classificacoes[2].motivo == MotivoIndeterminado.EMPATE_SEM_SINAL_ANTERIOR.value


def test_herança_de_empate_encadeia_deterministicamente() -> None:
    """Dois empates seguidos: o segundo herda o sinal que o primeiro já resolveu."""
    classificacoes = R.classificar_trimestres(_quarters(3), [2.0, 0.0, 0.0], [-1.0, -1.0, -1.0])
    assert [c.regime for c in classificacoes] == [RegimeV1.RECUPERACAO.value] * 3
    assert [c.desempate_aplicado for c in classificacoes] == [False, True, True]


@pytest.mark.parametrize("quase", [-1e-9, 1e-9, -0.003228])
def test_quase_empate_nao_aciona_o_desempate(quase: float) -> None:
    """A comparação de empate é `== 0` exato — `2024Q1` (g = −0,003228) classifica por sinal."""
    veredito = R.classificar_trimestres(_quarters(2), [5.0, quase], [-1.0, -1.0])[1]
    assert veredito.desempate_aplicado is False
    assert veredito.crescimento_acima is (quase > 0)


def test_resolver_eixo_distingue_ausente_de_empate() -> None:
    """`Eixo` separa "não tem número" de "tem número e é o limiar" — motivos diferentes."""
    ausente = R.resolver_eixo(None, limiar=0.0, sinal_anterior=True)
    empate = R.resolver_eixo(0.0, limiar=0.0, sinal_anterior=None)
    assert (ausente.ausente, ausente.empate, ausente.sinal) == (True, False, None)
    assert (empate.ausente, empate.empate, empate.sinal) == (False, True, None)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Nulo → INDETERMINADO, com motivo (CA-078, Anti-SPEC §10.1.1)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("g", "pi", "motivo"),
    [
        (None, 1.0, MotivoIndeterminado.GAP_AUSENTE),
        (1.0, None, MotivoIndeterminado.ACELERACAO_AUSENTE),
        (None, None, MotivoIndeterminado.AMBOS_AUSENTES),
        (float("nan"), 1.0, MotivoIndeterminado.GAP_AUSENTE),
    ],
    ids=["gap_nulo", "aceleracao_nula", "ambos_nulos", "gap_nan"],
)
def test_eixo_nulo_vira_indeterminado_com_motivo(
    g: float | None, pi: float | None, motivo: MotivoIndeterminado
) -> None:
    """Eixo sem número → sem quadrante, com o motivo **no dado**. Nunca uma estimativa."""
    veredito = _uma(g, pi)
    assert veredito.regime is None
    assert veredito.status == StatusRegimeV1.INDETERMINADO.value
    assert veredito.motivo == motivo.value


def test_indeterminado_nao_recebe_escore_inventado() -> None:
    """O escore do eixo ausente fica nulo na tabela — nada de 0 no lugar (§10.1.4)."""
    tabela = R.classificar(macro_sintetico([None, 1.0, -1.0], [1.0, 1.0, -1.0]))
    linha = tabela.loc[tabela["quarter"] == "2006Q1"].iloc[0]
    assert pd.isna(linha["regime_v1"])
    assert pd.isna(linha["g_score"])
    assert linha["pi_score"] == 1.0
    assert pd.isna(linha["crescimento_acima"])
    assert bool(linha["inflacao_acelerando"]) is True


def test_um_eixo_ausente_basta_para_indeterminar() -> None:
    """Não existe "meio classificado": um eixo sem número já tira o trimestre da grade."""
    assert _uma(None, 99.0).regime is None
    assert _uma(99.0, None).regime is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. `n` por célula, alerta e supressão (CA-080, CA-108, CA-109)
# ─────────────────────────────────────────────────────────────────────────────


def test_n_por_regime_e_o_tamanho_do_grupo_em_toda_linha() -> None:
    """Anti-SPEC §10.2.8: nenhuma célula desta tabela sai sem `n`, e `n` é o do seu grupo."""
    tabela = R.classificar(macro_sintetico([1.0, 1.0, -1.0], [1.0, 1.0, -1.0]))
    assert tabela["n_obs_regime_v1"].tolist() == [2, 2, 1]
    assert tabela["n_obs_regime_v1"].notna().all()
    assert (tabela["n_obs_regime_v1"] >= 1).all()


def test_n_menor_que_8_liga_alerta_n_baixo() -> None:
    """CA-108: `n < 8` → `alerta_n_baixo`; `n >= 8` → sem alerta."""
    assert R.alerta_n_baixo(N_ALERTA - 1) is True
    assert R.alerta_n_baixo(N_ALERTA) is False
    tabela = R.classificar(macro_sintetico([1.0] * 7, [1.0] * 7))
    assert tabela["n_obs_regime_v1"].unique().tolist() == [7]
    assert tabela["alerta_n_baixo"].all()


def test_n_menor_que_5_liga_conclusao_suprimida() -> None:
    """CA-109: `n < 5` → nenhuma conclusão afirmativa sobre a célula."""
    assert R.conclusao_suprimida(N_SUPRESSAO - 1) is True
    assert R.conclusao_suprimida(N_SUPRESSAO) is False
    tabela = R.classificar(macro_sintetico([1.0] * 4, [1.0] * 4))
    assert tabela["conclusao_suprimida"].all()
    assert tabela["alerta_n_baixo"].all(), "n < 5 implica n < 8: as duas flags acendem"


def test_n_com_8_alerta_mas_nao_suprime() -> None:
    """Os dois limiares são distintos: 5 <= n < 8 alerta sem suprimir (D10)."""
    tabela = R.classificar(macro_sintetico([1.0] * 6, [1.0] * 6))
    assert tabela["alerta_n_baixo"].all()
    assert not tabela["conclusao_suprimida"].any()


@pytest.mark.parametrize(
    ("n", "desbalanceado"),
    [(9, True), (10, False), (20, False), (35, False), (36, True)],
)
def test_alerta_de_desbalanceamento_usa_a_faixa_de_ca080(n: int, desbalanceado: bool) -> None:
    """CA-080: `n` por quadrante entre 10 e 35; fora disso o pipeline emite alerta."""
    assert R.alerta_desbalanceamento(n) is desbalanceado
    assert (N_QUADRANTE_MINIMO_CA080, N_QUADRANTE_MAXIMO_CA080) == (10, 35)


def test_contagem_conta_os_indeterminados_como_grupo_proprio() -> None:
    """O `n` dos indeterminados é publicado, não escondido — é o "67 de 83" verificável."""
    contagem = R.contagem_por_grupo(
        R.classificar_trimestres(_quarters(4), [None, None, 1.0, -1.0], [1.0, 1.0, 1.0, -1.0])
    )
    assert contagem == {
        StatusRegimeV1.INDETERMINADO.value: 2,
        RegimeV1.EXPANSAO_INFL.value: 1,
        RegimeV1.DESACELERACAO.value: 1,
    }


def test_distribuicao_separa_quadrantes_de_indeterminados() -> None:
    """O bloco `distribuicao` do relatório conta quadrantes povoados sem o grupo indeterminado."""
    tabela = R.classificar(macro_sintetico([None, 1.0, -1.0], [1.0, 1.0, -1.0]))
    bloco = R.distribuicao(tabela)
    assert bloco["quadrantes_povoados"] == 2
    assert bloco["quadrantes_esperados"] == 4
    assert StatusRegimeV1.INDETERMINADO.value in bloco["por_grupo"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Gate de publicação: o status do ADR-001 em disco (CA-090, CA-091)
# ─────────────────────────────────────────────────────────────────────────────


def _escrever_adr(raiz: Path, status: str) -> None:
    alvo = raiz / R.CAMINHO_ADR_001
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(
        f"# ADR-001 — sintetico\n\n- **Status:** **{status}** — nota\n- **Data:** 2026-10-11\n",
        encoding="utf-8",
    )


def test_adr_001_do_repo_esta_em_proposta_e_nao_congela(raiz_repo: Path) -> None:
    """CA-090 no estado de hoje: ADR-001 em `Proposta` ⇒ nada daqui é publicável."""
    assert R.status_adr_001(raiz=raiz_repo) == "PROPOSTA"
    assert R.especificacao_esta_congelada(raiz=raiz_repo) is False
    assert R.veredito_publicacao(False) == R.VEREDITO_NAO_CONGELADA
    assert "BLOQUEADO" in R.VEREDITO_NAO_CONGELADA


def test_adr_aceito_congela_a_especificacao(tmp_path: Path) -> None:
    """A flag segue o ADR, não uma constante: `Aceita` em disco ⇒ `True`."""
    _escrever_adr(tmp_path, "Aceita")
    assert R.status_adr_001(raiz=tmp_path) == R.STATUS_ADR_ACEITO
    assert R.especificacao_esta_congelada(raiz=tmp_path) is True


@pytest.mark.parametrize("status", ["Proposta", "Rejeitada", "Substituida"])
def test_qualquer_status_que_nao_seja_aceita_nao_congela(tmp_path: Path, status: str) -> None:
    """Só `Aceita` congela. "Em revisão", "Proposta" e afins **não** liberam publicação."""
    _escrever_adr(tmp_path, status)
    assert R.especificacao_esta_congelada(raiz=tmp_path) is False


def test_adr_ausente_falha_fechada(tmp_path: Path) -> None:
    """Negativo: ADR ilegível não pode virar "congelada" por acidente."""
    assert R.status_adr_001(raiz=tmp_path) == R.STATUS_ADR_DESCONHECIDO
    assert R.especificacao_esta_congelada(raiz=tmp_path) is False


def test_adr_sem_linha_de_status_falha_fechada(tmp_path: Path) -> None:
    """ADR existe mas sem `- **Status:**` reconhecível → `DESCONHECIDO`, não congelada."""
    alvo = tmp_path / R.CAMINHO_ADR_001
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text("# ADR-001\n\nsem linha de status\n", encoding="utf-8")
    assert R.especificacao_esta_congelada(raiz=tmp_path) is False


def test_tabela_carrega_especificacao_congelada_falsa_em_todas_as_linhas() -> None:
    """CA-090 no dado: a coluna é `False` em toda linha enquanto o ADR não for aceito."""
    tabela = R.classificar(macro_sintetico([1.0, -1.0], [1.0, -1.0]), congelada=False)
    assert tabela["especificacao_congelada"].tolist() == [False, False]


def test_versao_especificacao_nasce_v1_e_v1_1_nao_sobrescreve() -> None:
    """CA-091: um ajuste posterior nasce como `V1.1` **ao lado** da `V1`, nunca por cima."""
    entrada = macro_sintetico([1.0, -1.0], [1.0, -1.0])
    v1 = R.classificar(entrada)
    v1_1 = R.classificar(entrada, versao_especificacao=VERSAO_ESPECIFICACAO_V1_1)
    assert v1["versao_especificacao"].unique().tolist() == [VERSAO_ESPECIFICACAO_V1]
    assert v1_1["versao_especificacao"].unique().tolist() == [VERSAO_ESPECIFICACAO_V1_1]
    assert v1["versao_especificacao"].tolist() != v1_1["versao_especificacao"].tolist()
    # As duas tabelas coexistem: nada em `v1` mudou por existir uma `V1.1`.
    assert v1["versao_especificacao"].unique().tolist() == [VERSAO_ESPECIFICACAO_V1]


def test_versao_especificacao_fora_do_par_e_recusada_pelo_schema() -> None:
    """Negativo: `V2` não é uma versão da V1 — o contrato recusa (CA-091)."""
    with pytest.raises(Exception, match="(?i)versao_especificacao|isin"):
        R.classificar(macro_sintetico([1.0], [1.0]), versao_especificacao="V2")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Função pura e idempotente (CA-081)
# ─────────────────────────────────────────────────────────────────────────────


def test_duas_chamadas_com_a_mesma_entrada_dao_o_mesmo_resultado() -> None:
    """CA-081: sem estado, sem relógio, sem aleatoriedade."""
    entrada = macro_sintetico([1.0, 0.0, None, -2.0], [1.0, -1.0, 1.0, -1.0])
    primeira = R.classificar(entrada)
    segunda = R.classificar(entrada)
    pd.testing.assert_frame_equal(primeira, segunda)


def test_classificar_nao_muta_a_entrada() -> None:
    """A entrada é lida, nunca escrita — o chamador pode reusar o mesmo DataFrame."""
    entrada = macro_sintetico([1.0, -1.0], [1.0, -1.0])
    antes = entrada.copy(deep=True)
    R.classificar(entrada)
    pd.testing.assert_frame_equal(entrada, antes)


def test_fonte_versao_e_hash_de_arquivo_nao_do_processo() -> None:
    """CA-088: `fonte_versao` é o sha256 do conjunto de módulos, igual entre rodadas."""
    versao = R.versao_build()
    assert len(versao) == 64 and all(c in "0123456789abcdef" for c in versao)
    assert versao == R.versao_build()
    tabela = R.classificar(macro_sintetico([1.0], [1.0]))
    assert tabela["fonte_versao"].unique().tolist() == [versao]


def test_versao_build_muda_se_um_componente_muda(tmp_path: Path) -> None:
    """Negativo: editar o schema (onde moram os limiares) tem de mudar o hash."""
    copias = []
    for nome in R.MODULOS_DO_REGIME_V1:
        origem = Path(__import__(nome, fromlist=["__file__"]).__file__ or "")
        destino = tmp_path / origem.name
        destino.write_bytes(origem.read_bytes())
        copias.append(destino)
    from apps.pipeline.canonical.build_raw_series import versao_build as hash_de

    antes = hash_de(copias)
    copias[-1].write_bytes(copias[-1].read_bytes() + b"\n# limiar mudou\n")
    assert hash_de(copias) != antes


# ─────────────────────────────────────────────────────────────────────────────
# 7. Anti-look-ahead (CA-072, Anti-SPEC §10.2.7)
# ─────────────────────────────────────────────────────────────────────────────


def test_classificacao_de_t_nao_muda_quando_t_mais_1_muda() -> None:
    """A prova direta: mexer em **todo** o futuro não mexe em nenhum rótulo do passado."""
    g = [1.0, -2.0, 0.5, -0.5, 3.0]
    pi = [1.0, 1.0, -1.0, -1.0, 2.0]
    base = R.classificar_trimestres(_quarters(5), g, pi)
    for corte in range(1, 5):
        mexido_g = [*g[:corte], *[-v * 10 for v in g[corte:]]]
        mexido_pi = [*pi[:corte], *[-v * 10 for v in pi[corte:]]]
        alterado = R.classificar_trimestres(_quarters(5), mexido_g, mexido_pi)
        assert [c.regime for c in alterado[:corte]] == [c.regime for c in base[:corte]], (
            f"o rotulo de T < {corte} mudou quando T >= {corte} mudou: ha look-ahead"
        )


def test_truncar_a_amostra_nao_muda_os_rotulos_que_sobram() -> None:
    """Classificar `2006Q1..T` dá, em `2006Q1..T`, exatamente o que a amostra cheia dá."""
    g = [1.0, -2.0, 0.0, -0.5, 3.0, None, 2.0]
    pi = [1.0, 1.0, -1.0, -1.0, 2.0, 1.0, 0.0]
    cheia = R.classificar_trimestres(_quarters(7), g, pi)
    for corte in range(1, 8):
        truncada = R.classificar_trimestres(_quarters(corte), g[:corte], pi[:corte])
        assert [c.regime for c in truncada] == [c.regime for c in cheia[:corte]]
        assert [c.motivo for c in truncada] == [c.motivo for c in cheia[:corte]]


def test_remover_linhas_futuras_muda_n_mas_nao_rotulo() -> None:
    """`n` é estatística da amostra inteira — declarado, e separado do rótulo.

    Truncar a amostra muda `n_obs_regime_v1` (é uma contagem da amostra) e **não** muda
    `regime_v1`. Quem fizer backtest precisa de janela expanding; está no relatório.
    """
    entrada = macro_sintetico([1.0, 1.0, 1.0, -1.0], [1.0, 1.0, 1.0, -1.0])
    cheia = R.classificar(entrada)
    curta = R.classificar(entrada.iloc[:2].copy())
    assert cheia["regime_v1"].tolist()[:2] == curta["regime_v1"].tolist()
    assert cheia["n_obs_regime_v1"].tolist()[:2] == [3, 3]
    assert curta["n_obs_regime_v1"].tolist() == [2, 2]


def test_divergencia_entre_materializacoes_reporta_pct_e_veredito() -> None:
    """CA-073/CA-074: a % de troca é calculada e, acima de 25%, o texto diz "não operacional"."""
    revised = R.classificar(macro_sintetico([1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0]))
    asof = R.classificar(
        macro_sintetico([-1.0, -1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0], lag_adjusted=True)
    )
    bloco = R.divergencia_entre_materializacoes(revised, asof)
    assert bloco["trimestres_comparaveis"] == 4
    assert bloco["trimestres_que_trocam"] == 2
    assert bloco["pct_que_trocam"] == 0.5
    assert bloco["modelo_operacional"] is False
    assert "NAO e operacional" in bloco["texto"]


def test_divergencia_pequena_nao_declara_modelo_inoperante() -> None:
    """Abaixo de 25% o texto cita CA-073 e **não** afirma que o modelo caiu."""
    g = [1.0] * 10
    revised = R.classificar(macro_sintetico(g, [1.0] * 10))
    asof = R.classificar(macro_sintetico([-1.0, *g[1:]], [1.0] * 10, lag_adjusted=True))
    bloco = R.divergencia_entre_materializacoes(revised, asof)
    assert bloco["pct_que_trocam"] == 0.1
    assert bloco["modelo_operacional"] is True
    assert "NAO e operacional" not in bloco["texto"]


def test_trocou_vs_revised_e_nulo_na_materializacao_revised() -> None:
    """Não existe "trocou em relação a si mesma": a coluna fica nula em `revised`."""
    tabela = R.classificar(macro_sintetico([1.0, -1.0], [1.0, -1.0]))
    assert tabela["trocou_vs_revised"].isna().all()


def test_trocou_vs_revised_marca_a_linha_na_materializacao_asof() -> None:
    """Na `asof`, a coluna diz trimestre a trimestre se o rótulo mudou (CA-073)."""
    revised = R.classificar(macro_sintetico([1.0, 1.0], [1.0, 1.0]))
    asof = R.classificar(
        macro_sintetico([-1.0, 1.0], [1.0, 1.0], lag_adjusted=True),
        rotulos_revised=R.rotulos_de(revised),
    )
    assert asof["trocou_vs_revised"].tolist() == [True, False]
    assert asof["lag_adjusted"].all()


def test_sensibilidade_do_limiar_da_aceleracao_mede_e_nao_escolhe() -> None:
    """±0,1 pp no limiar: quantos trocam. Medir não é adotar (Anti-SPEC §10.2.9)."""
    entrada = macro_sintetico([1.0, 1.0, 1.0], [0.05, 0.5, -0.5])
    bloco = R.sensibilidade_limiar_aceleracao(entrada)
    assert bloco["limiar_base_pp"] == LIMIAR_ACELERACAO_PP
    assert bloco["deslocamento_pp"] == 0.1
    assert set(bloco["variantes"]) == {"+0.10", "-0.10"}
    # `pi = 0,05` está entre 0 e 0,1: é o único que vira RECUPERACAO com o limiar em +0,1 pp.
    assert bloco["variantes"]["+0.10"]["trimestres_que_trocam"] == 1
    assert bloco["variantes"]["+0.10"]["trocas"][0]["quarter"] == "2006Q1"
    assert bloco["max_trimestres_que_trocam"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 8. Guardas de entrada
# ─────────────────────────────────────────────────────────────────────────────


def test_entrada_fora_de_ordem_e_recusada() -> None:
    """O desempate lê `T-1`: entrada desordenada mudaria a herança em silêncio."""
    with pytest.raises(SerieInconsistente, match="ordem crescente"):
        R.classificar_trimestres(["2010Q2", "2010Q1"], [1.0, 1.0], [1.0, 1.0])


def test_quarter_duplicado_e_recusado() -> None:
    """`quarter` é a PK da tabela: duplicata é erro de entrada, não de contrato."""
    with pytest.raises(SerieInconsistente, match="duplicado"):
        R.classificar_trimestres(["2010Q1", "2010Q1"], [1.0, 1.0], [1.0, 1.0])


def test_sequencias_de_tamanhos_diferentes_sao_recusadas() -> None:
    """Desalinhar `g` e `pi` daria rótulo com o `pi` do trimestre errado."""
    with pytest.raises(SerieInconsistente, match="tamanhos diferentes"):
        R.classificar_trimestres(["2010Q1", "2010Q2"], [1.0], [1.0, 1.0])


def test_mistura_de_asof_e_revised_na_entrada_e_recusada() -> None:
    """CA-072: uma tabela nunca mistura as duas materializações."""
    entrada = macro_sintetico([1.0, -1.0], [1.0, -1.0])
    entrada.loc[0, "lag_adjusted"] = True
    with pytest.raises(SerieInconsistente, match="mistura"):
        R.classificar(entrada)


def test_coluna_do_eixo_faltando_e_recusada() -> None:
    """Sem `ibcbr_gap` não há eixo de crescimento — falha nomeando a coluna."""
    entrada = macro_sintetico([1.0], [1.0]).drop(columns=[R.COLUNA_CRESCIMENTO])
    with pytest.raises(SerieInconsistente, match=R.COLUNA_CRESCIMENTO):
        R.classificar(entrada)


def test_macro_asof_ausente_da_fonte_indisponivel(tmp_path: Path) -> None:
    """F-018 ainda não materializou `asof`: falha explícita, nunca fallback para `revised`."""
    with pytest.raises(FonteIndisponivel, match="FONTE INDISPONÍVEL"):
        R.ler_macro(materializacao=R.Materializacao.ASOF, raiz=tmp_path)


def test_materializacao_da_entrada_le_lag_adjusted() -> None:
    """A materialização vem do dado, não de um argumento que pode discordar dele."""
    assert R.materializacao_da_entrada(macro_sintetico([1.0], [1.0])) is R.Materializacao.REVISED
    assert (
        R.materializacao_da_entrada(macro_sintetico([1.0], [1.0], lag_adjusted=True))
        is R.Materializacao.ASOF
    )


# ─────────────────────────────────────────────────────────────────────────────
# 9. Acervo real (`data/canonical/`) — padrão `Acervo`
# ─────────────────────────────────────────────────────────────────────────────


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (mesma semântica de `test_canonical_curva.py`)."""
    return os.environ.get("LDC_IGNORAR_DATA", "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


@dataclass(frozen=True)
class Acervo:
    """Uma materialização de `macro_quarterly` em disco, com o que se espera dela."""

    rotulo: str
    materializacao: R.Materializacao
    #: `True` = ausência é **falha**; `False` = skip com motivo (o Parquet não está no git).
    obrigatorio: bool


def _acervos() -> tuple[Acervo, ...]:
    if ignorar_data_real():
        return ()
    return (
        Acervo("revised", R.Materializacao.REVISED, obrigatorio=False),
        Acervo("asof", R.Materializacao.ASOF, obrigatorio=False),
    )


ACERVOS = _acervos()
IDS = [a.rotulo for a in ACERVOS]


@cache
def _construido(acervo: Acervo) -> R.ResultadoRegimesV1:
    """`construir(gravar=False)` memoizado por acervo — o teste não escreve em `data/`."""
    nome = R.NOME_MACRO_POR_MATERIALIZACAO[acervo.materializacao.value]
    if not caminho_canonical(nome).is_file():
        if acervo.obrigatorio:  # pragma: no cover - hoje nenhum acervo e obrigatorio
            pytest.fail(f"{acervo.rotulo}: falta {nome}")
        pytest.skip(f"{acervo.rotulo}: {nome} ausente — {COMO_GERAR}")
    return R.construir(materializacao=acervo.materializacao, gravar=False)


@pytest.fixture(params=ACERVOS, ids=IDS)
def acervo(request: pytest.FixtureRequest) -> Acervo:
    """Uma materialização por vez."""
    return request.param


@pytest.fixture
def construido(acervo: Acervo) -> R.ResultadoRegimesV1:
    """O resultado do build sobre o acervo em teste."""
    return _construido(acervo)


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_tem_83_trimestres_e_os_4_quadrantes_povoados(
    construido: R.ResultadoRegimesV1,
) -> None:
    """CA-078/CA-080 sobre o dado real: 83 linhas, 4 quadrantes povoados."""
    tabela = construido.regimes
    assert len(tabela) == 83
    assert tabela["quarter"].is_unique
    assert sorted(tabela["quarter"])[0] == "2006Q1"
    assert sorted(tabela["quarter"])[-1] == "2026Q3"
    povoados = set(tabela["regime_v1"].dropna().unique())
    assert povoados == {r.value for r in RegimeV1}


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_tem_n_por_quadrante_na_faixa_de_ca080(construido: R.ResultadoRegimesV1) -> None:
    """CA-080: cada quadrante com `n` entre 10 e 35; fora disso o relatório alerta."""
    bloco = construido.relatorio["distribuicao"]
    quadrantes = {
        k: v for k, v in bloco["por_grupo"].items() if k != StatusRegimeV1.INDETERMINADO.value
    }
    assert len(quadrantes) == 4
    for nome, celula in quadrantes.items():
        assert N_QUADRANTE_MINIMO_CA080 <= celula["n"] <= N_QUADRANTE_MAXIMO_CA080, (
            f"{nome} com n={celula['n']} fora da faixa de CA-080"
        )
        assert celula["alerta_n_baixo"] is False
        assert celula["conclusao_suprimida"] is False
    assert bloco["desbalanceamento_ca080"] is False


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_declara_os_indeterminados_com_motivo(construido: R.ResultadoRegimesV1) -> None:
    """D-m no dado: os trimestres sem `ibcbr_gap` ficam fora, com motivo e sem estimativa."""
    bloco = construido.relatorio["indeterminados"]
    tabela = construido.regimes
    assert bloco["n"] == int(tabela["regime_v1"].isna().sum())
    assert bloco["n"] + construido.relatorio["regimes_v1"]["classificados"] == 83
    for motivo in bloco["por_motivo"]:
        assert motivo in {m.value for m in MotivoIndeterminado}
    sem_rotulo = tabela.loc[tabela["regime_v1"].isna()]
    assert sem_rotulo["motivo_indeterminado"].notna().all()
    assert (sem_rotulo["status_regime_v1"] == StatusRegimeV1.INDETERMINADO.value).all()


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_reproduz_os_canarios_conferidos_a_mao(construido: R.ResultadoRegimesV1) -> None:
    """3 canários + 1 quase-empate, conferidos célula a célula contra `macro_quarterly`."""
    if construido.materializacao is not R.Materializacao.REVISED:
        pytest.skip("os canarios foram lidos da materializacao revised")
    canarios = construido.relatorio["canarios"]
    for canario in R.CANARIOS:
        achado = canarios[canario.quarter]
        assert achado["regime"] == canario.regime_esperado, canario.nota
        assert achado["pi_score"] == pytest.approx(canario.pi_esperado, abs=R.TOLERANCIA_CANARIO_PP)
        if canario.g_esperado is None:
            assert achado["g_score"] is None
        else:
            assert achado["g_score"] == pytest.approx(
                canario.g_esperado, abs=R.TOLERANCIA_CANARIO_PP
            )


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_tem_timeline_legivel_de_83_linhas(construido: R.ResultadoRegimesV1) -> None:
    """RF-035: a timeline `ano-trimestre -> regime` é publicada no relatório, em ordem."""
    linha_do_tempo = construido.relatorio["timeline"]
    assert len(linha_do_tempo) == 83
    assert [item["quarter"] for item in linha_do_tempo] == sorted(
        item["quarter"] for item in linha_do_tempo
    )
    assert all(
        item["regime"] in {r.value for r in RegimeV1} or item["regime"] is None
        for item in linha_do_tempo
    )


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_declara_que_nada_e_publicavel(construido: R.ResultadoRegimesV1) -> None:
    """CA-090: ADR-001 em Proposta ⇒ `especificacao_congelada=False` nas 83 linhas."""
    espec = construido.relatorio["especificacao"]
    assert espec["especificacao_congelada"] is False
    assert espec["veredito_publicacao"] == R.VEREDITO_NAO_CONGELADA
    assert not construido.regimes["especificacao_congelada"].any()
    assert construido.regimes["versao_especificacao"].unique().tolist() == [VERSAO_ESPECIFICACAO_V1]


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_e_idempotente_no_byte(construido: R.ResultadoRegimesV1) -> None:
    """Anti-SPEC §10.4.22 / CA-081: duas rodadas sobre o mesmo dado dão o mesmo Parquet."""
    segunda = R.construir(materializacao=construido.materializacao, gravar=False)
    assert segunda.relatorio["regimes_v1"]["sha256"] == construido.relatorio["regimes_v1"]["sha256"]
    pd.testing.assert_frame_equal(segunda.regimes, construido.regimes)
    assert json.dumps(segunda.relatorio, sort_keys=True) == json.dumps(
        construido.relatorio, sort_keys=True
    )


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_tem_sensibilidade_baixa_ao_limiar_da_aceleracao(
    construido: R.ResultadoRegimesV1,
) -> None:
    """Robustez do único limiar livre: ±0,1 pp não pode reescrever a amostra."""
    bloco = construido.relatorio["sensibilidade_limiar_aceleracao"]
    assert bloco["trimestres_na_amostra"] == 83
    assert set(bloco["variantes"]) == {"+0.10", "-0.10"}
    assert bloco["max_pct_que_trocam"] is not None
    assert bloco["max_pct_que_trocam"] < 0.25, (
        "mais de 1/4 da amostra trocando com 0,1 pp de limiar significaria que o eixo de "
        "inflacao esta no ruido, nao no sinal"
    )


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_reporta_divergencia_asof_vs_revised_ou_diz_por_que_nao(
    construido: R.ResultadoRegimesV1,
) -> None:
    """CA-073/CA-074: ou há percentual, ou o relatório diz que `asof` não existe. Nunca vazio."""
    bloco = construido.relatorio["divergencia_asof_vs_revised"]
    motivo = construido.relatorio["motivo_divergencia"]
    if bloco is None:
        assert "asof" in motivo and "nao existe" in motivo
        return
    assert bloco["pct_que_trocam"] is None or 0.0 <= bloco["pct_que_trocam"] <= 1.0
    assert bloco["limiar_inoperante"] == 0.25
    if bloco["pct_que_trocam"] is not None and bloco["pct_que_trocam"] > 0.25:
        assert "NAO e operacional" in bloco["texto"]


@pytest.mark.skipif(not ACERVOS, reason="LDC_IGNORAR_DATA ligada")
def test_acervo_usa_so_colunas_de_t_da_materializacao_recebida(
    construido: R.ResultadoRegimesV1,
) -> None:
    """Anti-look-ahead no acervo real: truncar o futuro não muda rótulo nenhum do passado."""
    macro = R.ler_macro(materializacao=construido.materializacao)
    ordenado = macro.sort_values("quarter", kind="stable").reset_index(drop=True)
    cheia = R.rotulos_de(construido.regimes)
    for corte in (20, 40, 60, 80):
        truncada = R.classificar(ordenado.iloc[:corte].copy())
        for quarter, regime in R.rotulos_de(truncada).items():
            assert regime == cheia[quarter], (
                f"{quarter} mudou de rotulo ao truncar a amostra em {corte}: ha look-ahead"
            )
