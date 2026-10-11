"""F-021 — testes de **contrato** de `regime_neighbors` e `regime_neighbors_v3`. **Classe C.**

Uma regra quebrada por teste, no padrão de `test_macro_quarterly_contract.py`: cada teste
negativo mostra **qual** check recusa **qual** violação. Quatro seções:

| Seção | Sobre o quê |
|---|---|
| **A** | `RegimeNeighborsV3Schema` — os 7 checks, um a um, com o negativo de cada |
| **B** | `RegimeNeighborsSchema` — o contrato de CA-089, que a projeção tem de satisfazer |
| **C** | a relação entre os dois schemas (mesmo nome ⇒ mesmo significado) |
| **D** | o **acervo real** de `data/canonical/`, se existir |
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

from apps.pipeline.canonical.regimes_v3 import (
    FEATURES_USADAS,
    NOME_NEIGHBORS,
    NOME_NEIGHBORS_V3,
)
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.regimes import (
    JANELA_AMOSTRA_COMPLETA,
    JANELA_EXPANDING,
    K_VIZINHOS_PADRAO,
    K_VIZINHOS_SENSIBILIDADE,
    N_TRIMESTRES_EXCLUIDOS_VIZINHANCA,
    SEPARADOR_DE_FEATURES,
    SHRINKAGE_LEDOIT_WOLF,
    SHRINKAGE_NAO_SE_APLICA,
    VERSAO_ESPECIFICACAO_V3,
    MetricaDistancia,
    RegimeNeighborsSchema,
    RegimeNeighborsV3Schema,
    RegimeV1,
    StatusRegimeV1,
    indice_do_quarter,
)

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

FEATURES_DECLARADAS = SEPARADOR_DE_FEATURES.join(f.nome for f in FEATURES_USADAS)

ERROS_DE_SCHEMA = (SchemaError, SchemaErrors)


def _linha(**sobrepor: Any) -> dict[str, Any]:
    """Uma linha **válida** de `regime_neighbors_v3`. Os testes quebram um campo por vez."""
    base: dict[str, Any] = {
        "quarter_ref": "2026Q3",
        "rank": 1,
        "quarter_neighbor": "2014Q4",
        "distancia": 1.4097,
        "metrica": MetricaDistancia.MAHALANOBIS.value,
        "k_usado": K_VIZINHOS_PADRAO,
        "n_vizinhos": K_VIZINHOS_PADRAO,
        "n_features": len(FEATURES_USADAS),
        "features_usadas": FEATURES_DECLARADAS,
        "regime_v1_neighbor": RegimeV1.DESACELERACAO.value,
        "status_regime_v1_neighbor": StatusRegimeV1.CLASSIFICADO.value,
        "quarter_t_mais_1": "2015Q1",
        "shrinkage": SHRINKAGE_LEDOIT_WOLF,
        "janela_padronizacao": JANELA_AMOSTRA_COMPLETA,
        "somente_passado": False,
        "restrito_pos_2016": False,
        "alerta_n_baixo": False,
        "especificacao_congelada": False,
        "versao_especificacao": VERSAO_ESPECIFICACAO_V3,
        "lag_adjusted": False,
        "fonte_versao": "a" * 64 + "-nf5",
    }
    base.update(sobrepor)
    return base


def _quadro(*linhas: dict[str, Any]) -> pd.DataFrame:
    quadro = pd.DataFrame(list(linhas))
    quadro["regime_v1_neighbor"] = quadro["regime_v1_neighbor"].astype("string")
    quadro["quarter_t_mais_1"] = quadro["quarter_t_mais_1"].astype("string")
    return quadro


# ─────────────────────────────────────────────────────────────────────────────
# Seção A — `RegimeNeighborsV3Schema`, um check por teste
# ─────────────────────────────────────────────────────────────────────────────


def test_linha_valida_passa() -> None:
    """O fixture de base é válido — sem isto, todo teste negativo seria vácuo."""
    RegimeNeighborsV3Schema.validate(_quadro(_linha()), lazy=True)


def test_coluna_extra_e_recusada() -> None:
    """`strict=True`: coluna inventada fora do schema não entra em `data/canonical/`."""
    quadro = _quadro(_linha())
    quadro["palpite_do_analista"] = 1.0
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(quadro, lazy=True)


def test_pk_duplicada_e_recusada() -> None:
    """PK `(ref, rank, métrica, k, pos2016, somente_passado)`: duas linhas iguais não coexistem."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(), _linha(quarter_neighbor="2006Q3", quarter_t_mais_1="2006Q4")),
            lazy=True,
        )


def test_mesma_posicao_em_metricas_diferentes_coexiste() -> None:
    """A métrica é parte da PK: rank 1 em Mahalanobis e em Euclidiana são linhas distintas."""
    RegimeNeighborsV3Schema.validate(
        _quadro(
            _linha(),
            _linha(
                metrica=MetricaDistancia.EUCLIDIANA.value,
                shrinkage=SHRINKAGE_NAO_SE_APLICA,
                quarter_neighbor="2006Q3",
                quarter_t_mais_1="2006Q4",
                regime_v1_neighbor=None,
                status_regime_v1_neighbor=StatusRegimeV1.INDETERMINADO.value,
            ),
        ),
        lazy=True,
    )


def test_trimestre_de_referencia_nao_e_vizinho_de_si_mesmo() -> None:
    """O caso trivial do check de vizinhança: `T` não pode ser vizinho de `T`."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(quarter_neighbor="2026Q3", quarter_t_mais_1=None)), lazy=True
        )


@pytest.mark.parametrize("vizinho", ["2026Q2", "2026Q1"])
def test_vizinho_adjacente_e_recusado_pelo_contrato(vizinho: str) -> None:
    """**CA-085 como contrato:** `T-1` e `T-2` são recusados no schema, não só no teste."""
    assert indice_do_quarter("2026Q3") - indice_do_quarter(vizinho) <= (
        N_TRIMESTRES_EXCLUIDOS_VIZINHANCA
    )
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(quarter_neighbor=vizinho, quarter_t_mais_1=None)), lazy=True
        )


def test_vizinho_a_tres_trimestres_passa() -> None:
    """A borda do outro lado: `T-3` é elegível (a exclusão é de 2, não de 3)."""
    RegimeNeighborsV3Schema.validate(
        _quadro(_linha(quarter_neighbor="2025Q4", quarter_t_mais_1="2026Q1")), lazy=True
    )


def test_somente_passado_com_vizinho_futuro_e_recusado() -> None:
    """O **anti-look-ahead como contrato**: na variante só-passado não há vizinho no futuro."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(
                _linha(
                    quarter_ref="2014Q4",
                    quarter_neighbor="2024Q3",
                    quarter_t_mais_1="2024Q4",
                    somente_passado=True,
                    janela_padronizacao=JANELA_EXPANDING,
                    regime_v1_neighbor=RegimeV1.EXPANSAO_INFL.value,
                )
            ),
            lazy=True,
        )


def test_t_mais_1_que_nao_e_o_seguinte_do_vizinho_e_recusado() -> None:
    """**CA-102 como contrato:** apontar o próprio vizinho (ou `T+2`) é recusado."""
    for errado in ("2014Q4", "2015Q2"):
        with pytest.raises(ERROS_DE_SCHEMA):
            RegimeNeighborsV3Schema.validate(_quadro(_linha(quarter_t_mais_1=errado)), lazy=True)


def test_t_mais_1_nulo_passa_no_fim_da_janela() -> None:
    """O último trimestre da janela não tem seguinte: nulo é a resposta certa, não `2026Q4`."""
    RegimeNeighborsV3Schema.validate(
        _quadro(
            _linha(
                quarter_ref="2014Q4",
                quarter_neighbor="2026Q3",
                quarter_t_mais_1=None,
                regime_v1_neighbor=None,
                status_regime_v1_neighbor=StatusRegimeV1.INDETERMINADO.value,
            )
        ),
        lazy=True,
    )


def test_mahalanobis_sem_shrinkage_e_recusada() -> None:
    """**CA-084 como contrato:** Mahalanobis com `shrinkage != ledoit_wolf` não entra."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(shrinkage=SHRINKAGE_NAO_SE_APLICA)), lazy=True
        )


def test_euclidiana_com_shrinkage_e_recusada() -> None:
    """E o inverso: a Euclidiana não usa covariância, então não pode alegar shrinkage."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(
                _linha(metrica=MetricaDistancia.EUCLIDIANA.value, shrinkage=SHRINKAGE_LEDOIT_WOLF)
            ),
            lazy=True,
        )


def test_shrinkage_fora_do_vocabulario_e_recusado() -> None:
    """`shrinkage` é enumerado: "nenhum", "oas" ou texto livre não entram."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(shrinkage="nenhum")), lazy=True)


def test_rotulo_nulo_exige_status_indeterminado() -> None:
    """O nulo nunca é mudo: sem rótulo, `status` tem de dizer `INDETERMINADO`."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(regime_v1_neighbor=None)), lazy=True)
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(status_regime_v1_neighbor=StatusRegimeV1.INDETERMINADO.value)),
            lazy=True,
        )


def test_rotulo_fora_do_enum_e_recusado() -> None:
    """`regime_v1_neighbor` só aceita os 4 quadrantes de ADR-001 §5."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(regime_v1_neighbor="CRESCIMENTO_FORTE")), lazy=True
        )


def test_janela_de_padronizacao_cruzada_e_recusada() -> None:
    """`expanding` e `somente_passado` andam juntos — a mistura é recusada (metodologia §5.1)."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(janela_padronizacao=JANELA_EXPANDING)), lazy=True
        )


def test_rank_acima_de_n_vizinhos_e_recusado() -> None:
    """`rank` é posição dentro do que foi achado: rank 8 com `n_vizinhos = 3` é impossível."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(
            _quadro(_linha(rank=8, n_vizinhos=3, alerta_n_baixo=True)), lazy=True
        )


def test_k_fora_da_sensibilidade_do_contrato_e_recusado() -> None:
    """`k` só pode ser 5, 8 ou 12 — escolher `k = 7` "porque fica melhor" é Anti-SPEC §10.2.9."""
    assert 7 not in K_VIZINHOS_SENSIBILIDADE
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(k_usado=7, n_vizinhos=7)), lazy=True)


@pytest.mark.parametrize("n_features", [2, 7])
def test_n_features_fora_de_tres_a_seis_e_recusado(n_features: int) -> None:
    """O piso 3 e o teto 6 de `n_features` são do contrato (`CONTRACTS.md §5.2`)."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(n_features=n_features)), lazy=True)


def test_distancia_negativa_e_recusada() -> None:
    """Distância é `>= 0` por definição de métrica."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(distancia=-0.1)), lazy=True)


def test_trimestre_fora_da_janela_de_vinte_anos_e_recusado() -> None:
    """O regex de `quarter` fecha a janela: `2005Q4` e `2031Q1` não existem neste projeto."""
    for fora in ("2005Q4", "2031Q1"):
        with pytest.raises(ERROS_DE_SCHEMA):
            RegimeNeighborsV3Schema.validate(_quadro(_linha(quarter_ref=fora)), lazy=True)


def test_versao_de_especificacao_fora_do_vocabulario_e_recusada() -> None:
    """CA-091: ajuste posterior nasce como `V3.1`; "V4" ou "final" não são versões válidas."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(versao_especificacao="V4")), lazy=True)


def test_features_usadas_e_obrigatoria() -> None:
    """CA-086: o corte de feature nunca é silencioso — a lista é `nullable=False`."""
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsV3Schema.validate(_quadro(_linha(features_usadas=None)), lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# Seção B — `RegimeNeighborsSchema`, o contrato de CA-089
# ─────────────────────────────────────────────────────────────────────────────


def _linha_de_contrato(**sobrepor: Any) -> dict[str, Any]:
    """Uma linha válida de `regime_neighbors` (as 13 colunas do contrato)."""
    colunas = list(RegimeNeighborsSchema.to_schema().columns)
    base = {k: v for k, v in _linha().items() if k in colunas}
    base.update(sobrepor)
    return base


def test_contrato_linha_valida_passa() -> None:
    """CA-089: PK, `metrica` no enum e `rank` dentro de `k` — a linha de base passa."""
    quadro = pd.DataFrame([_linha_de_contrato()])
    RegimeNeighborsSchema.validate(quadro, lazy=True)
    assert len(quadro.columns) == len(RegimeNeighborsSchema.to_schema().columns)


def test_contrato_recusa_rotulo_v1_nulo() -> None:
    """A colisão com **D-m**, travada em teste: o contrato **não** aceita vizinho sem V1.

    É por isso que F-021 publica **dois** artefatos. Se algum dia esta linha passar, é porque a
    coluna virou anulável — e aí os dois artefatos devem ser colapsados num só.
    """
    quadro = pd.DataFrame([_linha_de_contrato(regime_v1_neighbor=None)])
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsSchema.validate(quadro, lazy=True)


def test_contrato_recusa_metrica_fora_do_enum() -> None:
    """CA-089: `metrica` ∈ {mahalanobis, euclidiana} — "cosseno" não entra."""
    quadro = pd.DataFrame([_linha_de_contrato(metrica="cosseno")])
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsSchema.validate(quadro, lazy=True)


def test_contrato_recusa_rank_acima_de_doze() -> None:
    """`rank` vai de 1 a 12 (o maior `k` da sensibilidade)."""
    quadro = pd.DataFrame([_linha_de_contrato(rank=13)])
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsSchema.validate(quadro, lazy=True)


def test_contrato_recusa_coluna_extra() -> None:
    """`strict=True` também no contrato: `somente_passado` **não** cabe nele hoje."""
    quadro = pd.DataFrame([{**_linha_de_contrato(), "somente_passado": True}])
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeNeighborsSchema.validate(quadro, lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# Seção C — a relação entre os dois schemas
# ─────────────────────────────────────────────────────────────────────────────


def test_v3_e_superconjunto_de_colunas_do_contrato() -> None:
    """Todo nome do contrato existe na V3 — "mesmo nome, mesmo significado" é verificável."""
    do_contrato = set(RegimeNeighborsSchema.to_schema().columns)
    da_v3 = set(RegimeNeighborsV3Schema.to_schema().columns)
    assert do_contrato <= da_v3, f"faltam na V3: {sorted(do_contrato - da_v3)}"


def test_colunas_novas_da_v3_sao_exatamente_as_declaradas() -> None:
    """O acréscimo é fechado: nada entrou na V3 sem estar na lista de motivos do schema."""
    do_contrato = set(RegimeNeighborsSchema.to_schema().columns)
    da_v3 = set(RegimeNeighborsV3Schema.to_schema().columns)
    assert da_v3 - do_contrato == {
        "n_vizinhos",
        "features_usadas",
        "status_regime_v1_neighbor",
        "quarter_t_mais_1",
        "janela_padronizacao",
        "somente_passado",
        "alerta_n_baixo",
        "especificacao_congelada",
        "versao_especificacao",
        "lag_adjusted",
    }


def test_pk_da_v3_estende_a_do_contrato() -> None:
    """A PK da V3 é a do contrato + `somente_passado` — e nada mais."""
    do_contrato = list(RegimeNeighborsSchema.to_schema().unique)
    da_v3 = list(RegimeNeighborsV3Schema.to_schema().unique)
    assert set(do_contrato) < set(da_v3)
    assert set(da_v3) - set(do_contrato) == {"somente_passado"}


def test_so_o_contrato_exige_rotulo_v1_nao_nulo() -> None:
    """A diferença de nulidade que motiva os dois artefatos está no schema, não na prosa."""
    assert RegimeNeighborsSchema.to_schema().columns["regime_v1_neighbor"].nullable is False
    assert RegimeNeighborsV3Schema.to_schema().columns["regime_v1_neighbor"].nullable is True


# ─────────────────────────────────────────────────────────────────────────────
# Seção D — acervo real
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


pulo_do_acervo = pytest.mark.skipif(
    ignorar_data_real()
    or not all(caminho_canonical(nome).is_file() for nome in (NOME_NEIGHBORS, NOME_NEIGHBORS_V3)),
    reason=(
        "seção D roda sobre data/canonical/. Ligue com "
        "`uv run python -m apps.pipeline.canonical.regimes_v3 --offline`."
    ),
)


@pulo_do_acervo
def test_acervo_os_dois_parquets_passam_nos_schemas() -> None:
    """O portão pandera sobre o que **está em disco** (RF-026), não sobre um quadro de teste."""
    RegimeNeighborsV3Schema.validate(
        pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3)), lazy=True
    )
    RegimeNeighborsSchema.validate(pd.read_parquet(caminho_canonical(NOME_NEIGHBORS)), lazy=True)


@pulo_do_acervo
def test_acervo_pk_e_unica_nos_dois() -> None:
    """Duplicata de PK em disco é o erro que mais cala: conferido por `duplicated`, não por fé."""
    v3 = pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3))
    contrato = pd.read_parquet(caminho_canonical(NOME_NEIGHBORS))
    assert not v3.duplicated(subset=list(RegimeNeighborsV3Schema.to_schema().unique)).any()
    assert not contrato.duplicated(subset=list(RegimeNeighborsSchema.to_schema().unique)).any()


@pulo_do_acervo
def test_acervo_rank_e_contiguo_em_toda_lente() -> None:
    """Em cada grupo da PK o `rank` é `1..n_vizinhos`, sem buraco e sem repetição."""
    v3 = pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3))
    chave = ["quarter_ref", "metrica", "k_usado", "restrito_pos_2016", "somente_passado"]
    for _, grupo in v3.groupby(chave, sort=False):
        esperado = list(range(1, len(grupo) + 1))
        assert sorted(grupo["rank"]) == esperado
        assert set(grupo["n_vizinhos"]) == {len(grupo)}
        assert len(grupo) <= int(grupo["k_usado"].iloc[0])


@pulo_do_acervo
def test_acervo_distancia_cresce_com_o_rank() -> None:
    """Ranking é ranking: dentro do grupo, a distância é monótona não-decrescente."""
    v3 = pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3))
    chave = ["quarter_ref", "metrica", "k_usado", "restrito_pos_2016", "somente_passado"]
    for _, grupo in v3.groupby(chave, sort=False):
        ordenado = grupo.sort_values("rank")
        assert ordenado["distancia"].is_monotonic_increasing


@pulo_do_acervo
def test_acervo_gate_de_publicacao_esta_fechado() -> None:
    """CA-090 no dado: enquanto ADR-001 estiver em Proposta, nenhuma linha diz "congelada"."""
    v3 = pd.read_parquet(caminho_canonical(NOME_NEIGHBORS_V3))
    assert set(v3["especificacao_congelada"].astype(bool)) == {False}
    assert set(v3["versao_especificacao"]) == {VERSAO_ESPECIFICACAO_V3}
    assert set(v3["lag_adjusted"].astype(bool)) == {False}
