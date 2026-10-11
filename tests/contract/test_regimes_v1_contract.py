"""F-019 — contrato de `regimes_v1`. **Classe C** (CA-088, CA-078, CA-072, Anti-SPEC §10.2.8).

Dois acervos, padrão `Acervo`:

- **`sintetico`** — construído em memória a partir de uma `macro_quarterly` sintética de 83
  trimestres. **Nunca pula**: é o que faz este contrato rodar no CI, onde `data/` não existe.
- **`data/canonical`** — o Parquet real, quando está em disco (não está no git).

O que este arquivo trava, e o que ele **deliberadamente não** trava:

- trava: PK, enum dos 4 rótulos, nulo só onde é permitido, `n` em **toda** linha, homogeneidade de
  `lag_adjusted`, `fonte_versao` como hash de 64 hexas, coerência `status ⇔ rótulo ⇔ motivo`, e o
  fato de `COLUNAS_V1_DE_REGIMES` ser um **subconjunto nominal** de `RegimesSchema`;
- não trava: `ciclo_selic`/`regime_v2`/`stress_flag` (F-020/F-021) e a junção final em `regimes`
  (F-022). O teste de que `RegimesSchema` **recusa** o `regime_v1` nulo está aqui de propósito: é
  o aviso, em forma de teste, de que F-022 precisa decidir o que fazer com os 16 indeterminados.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd
import pytest

from apps.pipeline.canonical import regimes_v1 as R
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.regimes import (
    COLUNAS_V1_DE_REGIMES,
    N_ALERTA,
    N_SUPRESSAO,
    MotivoIndeterminado,
    RegimesSchema,
    RegimesV1Schema,
    RegimeV1,
    StatusRegimeV1,
)

QUARTERS_83 = [
    f"{ano}Q{tri}"
    for ano in range(2006, 2027)
    for tri in (1, 2, 3, 4)
    if not (ano == 2026 and tri == 4)
]


def _macro_sintetica_83() -> pd.DataFrame:
    """83 trimestres sintéticos que povoam os 4 quadrantes **e** deixam nulos declarados.

    Os 15 primeiros têm `ibcbr_gap` nulo de propósito: é a forma do dado real (D-m), e um acervo
    sintético que só tenha trimestres bonitos não testaria o contrato que importa.
    """
    g: list[float | None] = []
    pi: list[float | None] = []
    for i, _ in enumerate(QUARTERS_83):
        if i < 15:
            g.append(None)
            pi.append(0.5)
            continue
        g.append(1.0 if (i // 2) % 2 == 0 else -1.0)
        pi.append(0.5 if i % 2 == 0 else -0.5)
    return pd.DataFrame(
        {
            "quarter": QUARTERS_83,
            R.COLUNA_CRESCIMENTO: g,
            R.COLUNA_INFLACAO: pi,
            "lag_adjusted": [False] * len(QUARTERS_83),
        }
    )


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (mesma semântica de `test_curva_contract.py`)."""
    return os.environ.get("LDC_IGNORAR_DATA", "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


@dataclass(frozen=True)
class Acervo:
    """De onde vem a tabela sob contrato."""

    rotulo: str
    caminho: Path | None
    obrigatorio: bool


def _acervos() -> tuple[Acervo, ...]:
    acervos = [Acervo("sintetico", None, obrigatorio=True)]
    if not ignorar_data_real():
        alvo = caminho_canonical(R.NOME_REGIMES_POR_MATERIALIZACAO[R.Materializacao.REVISED.value])
        acervos.append(Acervo("data/canonical", alvo, obrigatorio=False))
    return tuple(acervos)


ACERVOS = _acervos()
IDS = [a.rotulo for a in ACERVOS]


@cache
def _tabela(acervo: Acervo) -> pd.DataFrame:
    if acervo.caminho is None:
        return R.classificar(_macro_sintetica_83())
    if not acervo.caminho.is_file():
        pytest.skip(
            f"{acervo.rotulo}: {acervo.caminho.name} ausente — rode "
            "`uv run python -m apps.pipeline.canonical.regimes_v1`"
        )
    return pd.read_parquet(acervo.caminho)


@pytest.fixture(params=ACERVOS, ids=IDS)
def acervo(request: pytest.FixtureRequest) -> Acervo:
    """Um acervo por vez — o sintético sempre, o real por acréscimo."""
    return request.param


@pytest.fixture
def tabela(acervo: Acervo) -> pd.DataFrame:
    """A tabela `regimes_v1` do acervo em teste."""
    return _tabela(acervo)


# ─────────────────────────────────────────────────────────────────────────────
# 1. O schema aceita a tabela, e a tabela tem a forma do contrato
# ─────────────────────────────────────────────────────────────────────────────


def test_tabela_satisfaz_regimes_v1_schema(tabela: pd.DataFrame) -> None:
    """CA-088: a tabela passa por pandera, com todos os checks de DataFrame."""
    validada = RegimesV1Schema.validate(tabela, lazy=True)
    assert len(validada) == len(tabela)


def test_quarter_e_pk(tabela: pd.DataFrame) -> None:
    """PK `quarter`: única, não nula e no formato `AAAAQn` da janela de 20 anos."""
    assert tabela["quarter"].is_unique
    assert tabela["quarter"].notna().all()
    assert tabela["quarter"].str.fullmatch(r"(200[6-9]|20[1-2][0-9])Q[1-4]").all()


def test_regime_v1_so_tem_valores_do_enum_ou_nulo(tabela: pd.DataFrame) -> None:
    """CA-078: nenhum rótulo fora dos 4 do enum; o único "outro" possível é o nulo declarado."""
    presentes = set(tabela["regime_v1"].dropna().unique())
    assert presentes <= {r.value for r in RegimeV1}
    assert presentes, "nenhum trimestre classificado: a tabela nao tem conteudo"


def test_os_quatro_quadrantes_estao_povoados(tabela: pd.DataFrame) -> None:
    """CA-078/CA-080: nenhum quadrante fica vazio na amostra."""
    assert set(tabela["regime_v1"].dropna().unique()) == {r.value for r in RegimeV1}


def test_n_existe_em_toda_linha(tabela: pd.DataFrame) -> None:
    """Anti-SPEC §10.2.8: célula sem `n` é impossível — nem uma linha, nem uma célula."""
    assert tabela["n_obs_regime_v1"].notna().all()
    assert (tabela["n_obs_regime_v1"] >= 1).all()


def test_n_bate_com_o_tamanho_do_grupo(tabela: pd.DataFrame) -> None:
    """`n` não é um número qualquer: é a contagem do próprio grupo, recontável do dado."""
    chave = tabela["regime_v1"].fillna(StatusRegimeV1.INDETERMINADO.value)
    recontado = chave.map(chave.value_counts())
    assert tabela["n_obs_regime_v1"].tolist() == recontado.tolist()


def test_flags_de_n_sao_derivadas_dos_limiares_do_contrato(tabela: pd.DataFrame) -> None:
    """CA-108/CA-109: as flags não são digitadas à mão, são função de `n`."""
    assert tabela["alerta_n_baixo"].tolist() == (tabela["n_obs_regime_v1"] < N_ALERTA).tolist()
    assert (
        tabela["conclusao_suprimida"].tolist() == (tabela["n_obs_regime_v1"] < N_SUPRESSAO).tolist()
    )


def test_status_rotulo_e_motivo_sao_coerentes(tabela: pd.DataFrame) -> None:
    """`CLASSIFICADO` ⇔ tem rótulo ⇔ não tem motivo. Sem terceiro estado."""
    classificado = tabela["status_regime_v1"] == StatusRegimeV1.CLASSIFICADO.value
    assert (classificado == tabela["regime_v1"].notna()).all()
    assert (classificado == tabela["motivo_indeterminado"].isna()).all()
    motivos = set(tabela["motivo_indeterminado"].dropna().unique())
    assert motivos <= {m.value for m in MotivoIndeterminado}


def test_lag_adjusted_e_homogeneo(tabela: pd.DataFrame) -> None:
    """CA-072: a tabela nunca mistura `asof` e `revised`."""
    assert tabela["lag_adjusted"].unique().tolist() in ([True], [False])


def test_fonte_versao_e_hash_de_64_hexas(tabela: pd.DataFrame) -> None:
    """CA-088: `fonte_versao` é o hash do código, igual em todas as linhas do build."""
    unicos = tabela["fonte_versao"].unique().tolist()
    assert len(unicos) == 1
    assert len(unicos[0]) == 64
    assert set(unicos[0]) <= set("0123456789abcdef")


def test_especificacao_congelada_e_falsa_enquanto_adr_001_estiver_em_proposta(
    tabela: pd.DataFrame,
) -> None:
    """CA-090: o gate de publicação está no dado, não só na prosa."""
    assert not tabela["especificacao_congelada"].any()
    assert tabela["versao_especificacao"].unique().tolist() == ["V1"]


def test_trocou_vs_revised_e_nulo_na_materializacao_revised(tabela: pd.DataFrame) -> None:
    """Só a `asof` compara contra a `revised`; na `revised` a coluna é nula por contrato."""
    if bool(tabela["lag_adjusted"].iloc[0]):
        pytest.skip("acervo asof: a coluna e preenchida por construcao")
    assert tabela["trocou_vs_revised"].isna().all()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Negativos — o contrato recusa o que tem de recusar
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def valida() -> pd.DataFrame:
    """Uma tabela válida pequena, ponto de partida dos negativos."""
    return R.classificar(
        pd.DataFrame(
            {
                "quarter": ["2010Q1", "2010Q2", "2010Q3", "2010Q4"],
                R.COLUNA_CRESCIMENTO: [1.0, 1.0, -1.0, -1.0],
                R.COLUNA_INFLACAO: [1.0, -1.0, 1.0, -1.0],
                "lag_adjusted": [False] * 4,
            }
        )
    )


def test_rotulo_fora_do_enum_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo: `BOOM` não é quadrante da V1."""
    ruim = valida.copy()
    ruim.loc[0, "regime_v1"] = "BOOM"
    with pytest.raises(Exception, match="(?i)regime_v1|isin"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_rotulo_nulo_com_status_classificado_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo: sem rótulo e marcado como classificado é exatamente a falha silenciosa."""
    ruim = valida.copy()
    ruim.loc[0, "regime_v1"] = None
    with pytest.raises(Exception, match="(?i)status_coerente_com_o_rotulo"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_indeterminado_sem_motivo_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo: "não sei" sem dizer por quê não entra no canônico."""
    ruim = valida.copy()
    ruim.loc[0, "regime_v1"] = None
    ruim.loc[0, "status_regime_v1"] = StatusRegimeV1.INDETERMINADO.value
    with pytest.raises(Exception, match="(?i)status_coerente_com_o_rotulo"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_classificado_sem_sinal_de_eixo_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo: rótulo com eixo não resolvido significaria quadrante vindo do nada."""
    ruim = valida.copy()
    ruim["crescimento_acima"] = pd.array([None, True, False, False], dtype="boolean")
    with pytest.raises(Exception, match="(?i)eixos_presentes_se_classificado"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_n_nulo_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo (Anti-SPEC §10.2.8): célula sem `n` é impossível pelo contrato."""
    ruim = valida.copy()
    ruim["n_obs_regime_v1"] = [None, 1, 1, 1]
    with pytest.raises(Exception, match="(?i)n_obs_regime_v1|nullable|int"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_n_zero_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo: `n = 0` é célula que não existe, não célula vazia."""
    ruim = valida.copy()
    ruim.loc[0, "n_obs_regime_v1"] = 0
    with pytest.raises(Exception, match="(?i)greater_than_or_equal_to|ge"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_quarter_duplicado_e_recusado(valida: pd.DataFrame) -> None:
    """Negativo: PK duplicada."""
    ruim = pd.concat([valida, valida.iloc[[0]]], ignore_index=True)
    with pytest.raises(Exception, match="(?i)unique|duplicate"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_mistura_de_materializacao_e_recusada(valida: pd.DataFrame) -> None:
    """Negativo (CA-072): `asof` e `revised` na mesma tabela."""
    ruim = valida.copy()
    ruim.loc[0, "lag_adjusted"] = True
    with pytest.raises(Exception, match="(?i)lag_adjusted_homogeneo"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_coluna_extra_e_recusada(valida: pd.DataFrame) -> None:
    """Negativo (Anti-SPEC §10.4.24): coluna de DataFrame fora do schema não existe."""
    ruim = valida.copy()
    ruim["regime_v9"] = "INVENTADO"
    with pytest.raises(Exception, match="(?i)regime_v9|strict|column"):
        RegimesV1Schema.validate(ruim, lazy=True)


def test_fonte_versao_nao_hash_e_recusada(valida: pd.DataFrame) -> None:
    """Negativo (CA-088): `fonte_versao` tem de ser o hash, não "v1" nem a hora do build."""
    ruim = valida.copy()
    ruim["fonte_versao"] = "2026-10-11T01:00"
    with pytest.raises(Exception, match="(?i)fonte_versao|str_matches"):
        RegimesV1Schema.validate(ruim, lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Relação com `RegimesSchema` — o que F-022 herda
# ─────────────────────────────────────────────────────────────────────────────


def test_colunas_da_v1_existem_em_regimes_schema_com_o_mesmo_nome() -> None:
    """O subconjunto é nominal: nada aqui vira uma coluna "parecida" lá."""
    completo = set(RegimesSchema.to_schema().columns)
    parcial = set(RegimesV1Schema.to_schema().columns)
    assert set(COLUNAS_V1_DE_REGIMES) <= completo
    assert set(COLUNAS_V1_DE_REGIMES) <= parcial


def test_colunas_de_v2_e_v3_nao_estao_na_tabela_da_v1() -> None:
    """F-019 não grava coluna de outra lente — nem nula, para ninguém ler como calculada."""
    parcial = set(RegimesV1Schema.to_schema().columns)
    assert {"ciclo_selic", "regime_v2", "stress_flag", "regime_v1b"}.isdisjoint(parcial)


def test_regimes_schema_continua_recusando_regime_v1_nulo() -> None:
    """O aviso para F-022, em forma de teste.

    `RegimesSchema.regime_v1` é `nullable=False`: a junção das três lentes **não** pode
    simplesmente concatenar os 16 indeterminados. A decisão (excluir as linhas, criar um rótulo
    novo no enum, ou outra coisa) é de F-022 e exige alteração de contrato, logo pausa.
    """
    coluna = RegimesSchema.to_schema().columns["regime_v1"]
    assert coluna.nullable is False
    assert RegimesV1Schema.to_schema().columns["regime_v1"].nullable is True


def test_enum_dos_quatro_rotulos_nao_foi_alterado() -> None:
    """F-019 **acrescentou** ao módulo de schema e não tocou o enum existente."""
    assert [r.value for r in RegimeV1] == [
        "RECUPERACAO",
        "EXPANSAO_INFL",
        "ESTAGFLACAO",
        "DESACELERACAO",
    ]
    assert len(RegimeV1) == 4


def test_check_de_quadrantes_povoados_de_regimes_schema_segue_de_pe() -> None:
    """`todos_os_quadrantes_povoados` continua no contrato completo, intocado."""
    checks = {c.name for c in RegimesSchema.to_schema().checks}
    assert "todos_os_quadrantes_povoados" in checks
