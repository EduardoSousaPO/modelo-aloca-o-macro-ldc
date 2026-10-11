"""F-026 — testes de **contrato** de `internacional_por_regime` e `internacional_pesos`.

| Bloco | O que cobre | CA |
|---|---|---|
| A | `InternacionalPorRegimeSchema` item a item: PK, enum de `lente`, `n` | CA-104, CA-095 |
| B | o que o contrato de retornos **recusa** | CA-105, CA-108 |
| C | `InternacionalPesosSchema`: long-only, soma 1, cap, banda | CA-107 |
| D | o que o contrato de pesos **recusa** | CA-107 |
| E | a relação com as tabelas de origem (F-017, F-022) | CA-104 |
| F | o acervo em disco satisfaz os dois contratos | todos |

Contrato é o que o schema **recusa**, não só o que ele aceita: cada teste de recusa aqui existe
porque o erro correspondente é silencioso se o pandera não o pegar — peso negativo numa carteira
long-only, soma 0,98 em vez de 1, correlação de 1 ponto, `n_pares` maior que `n_obs`.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

from apps.pipeline.canonical import internacional as I  # noqa: E741 - modulo, nao variavel
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.asset_returns_quarterly import (
    ASSET_IDS_VALIDOS,
    ATIVOS_INTERNACIONAIS,
    AssetReturnsQuarterlySchema,
    RegimeAssetMetricsSchema,
)
from packages.shared.schemas.internacional import (
    ATIVO_INTERNACIONAL_REPRESENTATIVO,
    ATIVOS_DA_TABELA_POR_REGIME,
    BANDA_TATICA_MAX,
    BANDA_TATICA_MIN,
    CAP_POR_ATIVO,
    CARTEIRA_VARIANCIA_MINIMA,
    ESCOPO_EXPANDING,
    ESCOPO_POR_REGIME,
    ESCOPOS_PESOS,
    LENTES_INTERNACIONAL,
    PK_PESOS,
    PK_POR_REGIME,
    InternacionalPesosSchema,
    InternacionalPorRegimeSchema,
)

ERROS_DE_SCHEMA = (SchemaError, SchemaErrors)

COLUNAS_POR_REGIME: tuple[str, ...] = tuple(InternacionalPorRegimeSchema.to_schema().columns)
COLUNAS_PESOS: tuple[str, ...] = tuple(InternacionalPesosSchema.to_schema().columns)


# ─────────────────────────────────────────────────────────────────────────────
# Linhas-base sintéticas que os contratos aceitam
# ─────────────────────────────────────────────────────────────────────────────


def _linha_por_regime(**sobrescritas: object) -> dict[str, object]:
    """Uma célula válida de `internacional_por_regime` — **sintética**, nomeada como tal."""
    base: dict[str, object] = {
        "lente": "V1",
        "regime": "RECUPERACAO",
        "asset_id": ATIVO_INTERNACIONAL_REPRESENTATIVO,
        "n_obs": 19,
        "ret_medio": 0.035,
        "ret_mediana": 0.030,
        "excesso_cdi": 0.012,
        "ret_real": 0.020,
        "hit_ratio_cdi": 0.58,
        "corr_ibov": 0.42,
        "n_pares_ibov": 19,
        "corr_imab": 0.11,
        "n_pares_imab": 19,
        "is_total_return": True,
        "alerta_n_baixo": False,
        "conclusao_suprimida": False,
        "especificacao_congelada": False,
        "fonte_versao": "a" * 64,
    }
    base.update(sobrescritas)
    return base


def _tabela_por_regime(*linhas: dict[str, object]) -> pd.DataFrame:
    """Um DataFrame com as linhas dadas, na ordem das colunas do contrato."""
    return pd.DataFrame(list(linhas), columns=list(COLUNAS_POR_REGIME))


def _carteira_de_pesos(
    pesos: dict[str, float],
    *,
    escopo: str = ESCOPO_POR_REGIME,
    chave: str = "RECUPERACAO",
    cap: float = CAP_POR_ATIVO,
    com_banda: bool = True,
) -> pd.DataFrame:
    """Uma carteira válida de `internacional_pesos` — **sintética**, soma 1 por construção."""
    carteira = "+".join(CARTEIRA_VARIANCIA_MINIMA)
    linhas = [
        {
            "escopo": escopo,
            "chave": chave,
            "carteira": carteira,
            "asset_id": asset_id,
            "peso": peso,
            "cap": cap,
            "peso_na_banda": (
                I.truncar_na_banda(peso)
                if com_banda and asset_id == ATIVO_INTERNACIONAL_REPRESENTATIVO
                else None
            ),
            "n_obs": 19,
            "rho_shrinkage": 0.41,
            "alerta_n_baixo": False,
            "conclusao_suprimida": False,
            "especificacao_congelada": False,
            "fonte_versao": "b" * 64,
        }
        for asset_id, peso in pesos.items()
    ]
    return pd.DataFrame(linhas, columns=list(COLUNAS_PESOS))


PESOS_VALIDOS = {"CDI": 0.40, "IMAB": 0.34, "IBOV": 0.10, ATIVO_INTERNACIONAL_REPRESENTATIVO: 0.16}


# ─────────────────────────────────────────────────────────────────────────────
# A. `InternacionalPorRegimeSchema` — o que ele aceita
# ─────────────────────────────────────────────────────────────────────────────


def test_contrato_por_regime_aceita_a_linha_base() -> None:
    """A linha-base passa: se este teste falha, todos os de recusa abaixo mentem."""
    InternacionalPorRegimeSchema.validate(_tabela_por_regime(_linha_por_regime()), lazy=True)


def test_contrato_por_regime_tem_as_colunas_que_ca104_e_ca105_exigem() -> None:
    """CA-104 (as métricas de F-022) + CA-105 (as 2 correlações **com** `n` de pares)."""
    for coluna in ("n_obs", "ret_medio", "excesso_cdi", "ret_real", "hit_ratio_cdi"):
        assert coluna in COLUNAS_POR_REGIME
    for coluna in ("corr_ibov", "n_pares_ibov", "corr_imab", "n_pares_imab"):
        assert coluna in COLUNAS_POR_REGIME
    assert "is_total_return" in COLUNAS_POR_REGIME  # CA-064


def test_contrato_por_regime_tem_a_pk_declarada() -> None:
    """A PK é `(lente, regime, asset_id)` — uma célula por combinação, nunca duas."""
    assert PK_POR_REGIME == ("lente", "regime", "asset_id")
    assert InternacionalPorRegimeSchema.to_schema().unique == list(PK_POR_REGIME)


def test_contrato_por_regime_aceita_as_tres_lentes_de_rf038() -> None:
    """V1 `revised`, V1 `asof` e V3 — as três leituras cabem na mesma tabela."""
    assert set(LENTES_INTERNACIONAL) == {"V1", "V1_ASOF", "V3"}
    linhas = [_linha_por_regime(lente=lente, regime=f"R_{lente}") for lente in LENTES_INTERNACIONAL]
    InternacionalPorRegimeSchema.validate(_tabela_por_regime(*linhas), lazy=True)


def test_contrato_por_regime_aceita_celula_vazia_com_n_zero() -> None:
    """`n_obs = 0` com retornos nulos é **válido**: a linha fica, dizendo que não há observação."""
    vazia = _linha_por_regime(
        n_obs=0,
        ret_medio=None,
        ret_mediana=None,
        excesso_cdi=None,
        ret_real=None,
        hit_ratio_cdi=None,
        corr_ibov=None,
        n_pares_ibov=0,
        corr_imab=None,
        n_pares_imab=0,
        alerta_n_baixo=True,
        conclusao_suprimida=True,
    )
    InternacionalPorRegimeSchema.validate(_tabela_por_regime(vazia), lazy=True)


def test_contrato_por_regime_aceita_is_total_return_nulo() -> None:
    """`None` = a confirmar (G-01). Não é `False` — a ausência de flag é informação (CA-064)."""
    InternacionalPorRegimeSchema.validate(
        _tabela_por_regime(_linha_por_regime(is_total_return=None)), lazy=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# B. `InternacionalPorRegimeSchema` — o que ele RECUSA
# ─────────────────────────────────────────────────────────────────────────────


def test_contrato_por_regime_recusa_n_obs_nulo() -> None:
    """Anti-SPEC §10.2.8: nenhuma célula sai sem `n`. O contrato é o último guardião disso."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(n_obs=None)), lazy=True
        )


def test_contrato_por_regime_recusa_lente_inventada() -> None:
    """`V2`, `V4` ou `V1_REVISED` não existem neste enum — lente nova exige feature."""
    for lente in ("V2", "V4", "V1_REVISED", "v1"):
        with pytest.raises(ERROS_DE_SCHEMA):
            InternacionalPorRegimeSchema.validate(
                _tabela_por_regime(_linha_por_regime(lente=lente)), lazy=True
            )


def test_contrato_por_regime_recusa_asset_id_fora_do_catalogo() -> None:
    """Anti-SPEC §10.4.24: ativo que não está em `ASSET_IDS_VALIDOS` não entra no canônico."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(asset_id="SP500_TOTAL_RETURN_SINTETICO")),
            lazy=True,
        )


def test_contrato_por_regime_recusa_pk_duplicada() -> None:
    """Duas células para a mesma `(lente, regime, ativo)` = alguém somou tabelas diferentes."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(), _linha_por_regime()), lazy=True
        )


@pytest.mark.parametrize("valor", [-1.0001, 1.0001, 2.0, -3.0])
def test_contrato_por_regime_recusa_correlacao_fora_de_menos_um_a_um(valor: float) -> None:
    """Correlação fora de [−1, 1] é erro de cálculo, não resultado."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(corr_ibov=valor)), lazy=True
        )


def test_contrato_por_regime_recusa_correlacao_com_menos_de_dois_pares() -> None:
    """Correlação de 1 par **não existe**: o check `correlacao_exige_pares` recusa."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(corr_ibov=0.9, n_pares_ibov=1)), lazy=True
        )


def test_contrato_por_regime_recusa_n_pares_maior_que_n_obs() -> None:
    """Par exige os dois lados: `n_pares > n_obs` é impossível e denuncia alinhamento errado."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(n_obs=10, n_pares_ibov=11, n_pares_imab=10)),
            lazy=True,
        )


def test_contrato_por_regime_recusa_hit_ratio_fora_de_zero_a_um() -> None:
    """`hit_ratio_cdi` é fração, não por cento: 58 em vez de 0,58 é recusado."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(
            _tabela_por_regime(_linha_por_regime(hit_ratio_cdi=58.0)), lazy=True
        )


def test_contrato_por_regime_e_strict_e_recusa_coluna_inventada() -> None:
    """Anti-SPEC §10.4.24: coluna fora do schema é recusada, não ignorada."""
    quadro = _tabela_por_regime(_linha_por_regime())
    quadro["peso_sugerido"] = 0.20
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPorRegimeSchema.validate(quadro, lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# C. `InternacionalPesosSchema` — o que ele aceita
# ─────────────────────────────────────────────────────────────────────────────


def test_contrato_pesos_aceita_a_carteira_base() -> None:
    """Long-only, soma 1, cap respeitado, banda só no internacional: a carteira base passa."""
    InternacionalPesosSchema.validate(_carteira_de_pesos(PESOS_VALIDOS), lazy=True)


def test_contrato_pesos_tem_a_pk_declarada_e_os_dois_escopos() -> None:
    """PK inclui `cap` e `carteira`: as sensibilidades convivem sem colidir."""
    assert PK_PESOS == ("escopo", "chave", "cap", "carteira", "asset_id")
    assert InternacionalPesosSchema.to_schema().unique == list(PK_PESOS)
    assert set(ESCOPOS_PESOS) == {ESCOPO_POR_REGIME, ESCOPO_EXPANDING}


def test_contrato_pesos_aceita_o_mesmo_ativo_em_caps_diferentes() -> None:
    """A sensibilidade de cap não é PK duplicada — é justamente o que `cap` na PK permite."""
    quadro = pd.concat(
        [
            _carteira_de_pesos(PESOS_VALIDOS, cap=CAP_POR_ATIVO),
            _carteira_de_pesos(PESOS_VALIDOS, cap=1.0),
        ],
        ignore_index=True,
    )
    InternacionalPesosSchema.validate(quadro, lazy=True)


def test_contrato_pesos_aceita_escopo_expanding_com_quarter_na_chave() -> None:
    """No escopo `EXPANDING` a `chave` é o `quarter` — a mesma coluna, outro significado."""
    InternacionalPesosSchema.validate(
        _carteira_de_pesos(PESOS_VALIDOS, escopo=ESCOPO_EXPANDING, chave="2026Q3"), lazy=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# D. `InternacionalPesosSchema` — o que ele RECUSA
# ─────────────────────────────────────────────────────────────────────────────


def test_contrato_pesos_recusa_peso_negativo() -> None:
    """Long-only é **contrato**, não só restrição do solver: short é recusado no Parquet."""
    pesos = dict(PESOS_VALIDOS)
    pesos["IBOV"] = -0.10
    pesos["IMAB"] = 0.54
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(_carteira_de_pesos(pesos), lazy=True)


def test_contrato_pesos_recusa_soma_diferente_de_um() -> None:
    """Soma 0,98 passa por qualquer checagem de coluna — e é recusada pelo check de carteira."""
    pesos = dict(PESOS_VALIDOS)
    pesos["CDI"] = 0.38
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(_carteira_de_pesos(pesos), lazy=True)


def test_contrato_pesos_recusa_peso_acima_do_cap_declarado_na_linha() -> None:
    """`cap` vive na linha: peso de 0,50 com `cap = 0,40` é incoerente **com a própria linha**."""
    pesos = {"CDI": 0.50, "IMAB": 0.24, "IBOV": 0.10, ATIVO_INTERNACIONAL_REPRESENTATIVO: 0.16}
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(_carteira_de_pesos(pesos, cap=0.40), lazy=True)


def test_contrato_pesos_recusa_banda_em_ativo_domestico() -> None:
    """CA-107: a banda é sobre o **internacional**. Banda no CDI é erro de leitura materializado."""
    quadro = _carteira_de_pesos(PESOS_VALIDOS)
    quadro.loc[quadro["asset_id"] == "CDI", "peso_na_banda"] = 0.40
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(quadro, lazy=True)


@pytest.mark.parametrize("valor", [0.10, 0.1499, 0.3501, 0.60])
def test_contrato_pesos_recusa_banda_fora_de_quinze_a_trinta_e_cinco(valor: float) -> None:
    """`peso_na_banda` fora de [15%, 35%] significa que o truncamento não foi aplicado."""
    quadro = _carteira_de_pesos(PESOS_VALIDOS)
    quadro.loc[quadro["asset_id"] == ATIVO_INTERNACIONAL_REPRESENTATIVO, "peso_na_banda"] = valor
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(quadro, lazy=True)


def test_contrato_pesos_recusa_rho_fora_de_zero_a_um() -> None:
    """`rho` de Ledoit-Wolf é uma intensidade em [0, 1] — fora disso, o estimador está errado."""
    quadro = _carteira_de_pesos(PESOS_VALIDOS)
    quadro["rho_shrinkage"] = 1.5
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(quadro, lazy=True)


def test_contrato_pesos_recusa_escopo_inventado() -> None:
    """Escopo novo (ex.: `POR_ANO`) exige feature, não uma string nova no Parquet."""
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(
            _carteira_de_pesos(PESOS_VALIDOS, escopo="POR_ANO"), lazy=True
        )


def test_contrato_pesos_e_strict_e_recusa_coluna_inventada() -> None:
    """A tabela de pesos não ganha coluna por conveniência (Anti-SPEC §10.4.24)."""
    quadro = _carteira_de_pesos(PESOS_VALIDOS)
    quadro["recomendacao"] = "comprar"
    with pytest.raises(ERROS_DE_SCHEMA):
        InternacionalPesosSchema.validate(quadro, lazy=True)


def test_contrato_pesos_nao_tem_coluna_de_retorno_esperado_nem_de_recomendacao() -> None:
    """Anti-SPEC §10.2.10 no **contrato**: não há onde escrever previsão nesta tabela."""
    proibidas = {"retorno_esperado", "recomendacao", "alvo", "previsao", "sharpe_esperado"}
    assert not proibidas & set(COLUNAS_PESOS)


# ─────────────────────────────────────────────────────────────────────────────
# E. A relação com as tabelas de origem
# ─────────────────────────────────────────────────────────────────────────────


def test_universo_internacional_e_subconjunto_do_catalogo_de_f017() -> None:
    """Os ativos desta feature existem em `asset_returns_quarterly` por contrato."""
    for asset_id in ATIVOS_DA_TABELA_POR_REGIME:
        assert asset_id in ASSET_IDS_VALIDOS
    assert ATIVO_INTERNACIONAL_REPRESENTATIVO in ATIVOS_INTERNACIONAIS


def test_carteira_de_variancia_minima_e_o_conjunto_pequeno_de_quatro_ativos() -> None:
    """`metodologia §4.3` item 1: conjunto **pequeno**. 4 ativos com `n ≈ 15` já é muito."""
    assert len(CARTEIRA_VARIANCIA_MINIMA) == 4
    assert set(CARTEIRA_VARIANCIA_MINIMA) <= set(ATIVOS_DA_TABELA_POR_REGIME)
    assert CAP_POR_ATIVO * len(CARTEIRA_VARIANCIA_MINIMA) >= 1.0  # viavel


def test_lente_do_internacional_nao_colide_com_a_de_f022() -> None:
    """`V1_ASOF` **não** existe em `RegimeAssetMetricsSchema`: os contratos são distintos.

    É o que permite as três leituras numa tabela só sem alterar o schema de F-022 — que seria
    alteração de contrato existente, logo pausa (`AGENTS.md §9`).
    """
    assert "V1_ASOF" in LENTES_INTERNACIONAL
    linha_de_f022 = {
        "lente": "V1_ASOF",
        "regime": "RECUPERACAO",
        "asset_id": ATIVO_INTERNACIONAL_REPRESENTATIVO,
        "n_obs": 19,
        "ret_medio": 0.03,
        "ret_mediana": 0.03,
        "ret_desvio": 0.10,
        "erro_padrao_media": 0.02,
        "hit_ratio": 0.6,
        "excesso_cdi": 0.01,
        "hit_ratio_cdi": 0.5,
        "ret_real": 0.02,
        "sharpe_tri": 0.1,
        "pior_tri": -0.2,
        "pior_tri_quarter": "2008Q4",
        "melhor_tri": 0.3,
        "melhor_tri_quarter": "2009Q2",
        "beta_ibov": 0.5,
        "alerta_n_baixo": False,
        "conclusao_suprimida": False,
        "data_inicio_serie": pd.Timestamp("2006-01-02"),
        "fonte_versao": "c" * 64,
    }
    with pytest.raises(ERROS_DE_SCHEMA):
        RegimeAssetMetricsSchema.validate(pd.DataFrame([linha_de_f022]), lazy=True)


def test_banda_tatica_contem_o_piso_estrutural_de_adr003() -> None:
    """A banda [15%, 35%] contém o piso [16%, 20%]: se não contivesse, a faixa seria incoerente."""
    assert BANDA_TATICA_MIN <= I.PISO_ESTRUTURAL_MIN
    assert BANDA_TATICA_MAX >= I.PISO_ESTRUTURAL_MAX


# ─────────────────────────────────────────────────────────────────────────────
# F. O acervo em disco satisfaz os contratos
# ─────────────────────────────────────────────────────────────────────────────


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (mesma semântica dos demais testes de contrato)."""
    return os.environ.get("LDC_IGNORAR_DATA", "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


TEM_POR_REGIME = not ignorar_data_real() and caminho_canonical(I.NOME_POR_REGIME).is_file()
TEM_PESOS = not ignorar_data_real() and caminho_canonical(I.NOME_PESOS).is_file()
MOTIVO = "acervo ausente — rode `uv run python -m apps.pipeline.canonical.internacional`"


@pytest.mark.skipif(not TEM_POR_REGIME, reason=MOTIVO)
def test_acervo_por_regime_satisfaz_o_contrato() -> None:
    """O Parquet publicado passa pelo schema, com as colunas na ordem do contrato."""
    quadro = pd.read_parquet(caminho_canonical(I.NOME_POR_REGIME))
    InternacionalPorRegimeSchema.validate(quadro, lazy=True)
    assert list(quadro.columns) == list(COLUNAS_POR_REGIME)


@pytest.mark.skipif(not TEM_PESOS, reason=MOTIVO)
def test_acervo_pesos_satisfaz_o_contrato() -> None:
    """Idem para a tabela de pesos — inclusive os três checks de carteira."""
    quadro = pd.read_parquet(caminho_canonical(I.NOME_PESOS))
    InternacionalPesosSchema.validate(quadro, lazy=True)
    assert list(quadro.columns) == list(COLUNAS_PESOS)


@pytest.mark.skipif(not TEM_POR_REGIME, reason=MOTIVO)
def test_acervo_por_regime_tem_as_tres_lentes_e_os_seis_ativos() -> None:
    """RF-038 pede as três leituras; o universo é o declarado, sem ativo a mais nem a menos."""
    quadro = pd.read_parquet(caminho_canonical(I.NOME_POR_REGIME))
    assert set(quadro["lente"].unique()) == set(LENTES_INTERNACIONAL)
    assert set(quadro["asset_id"].unique()) == set(ATIVOS_DA_TABELA_POR_REGIME)


@pytest.mark.skipif(not TEM_POR_REGIME, reason=MOTIVO)
def test_acervo_por_regime_nao_tem_ativo_sem_fonte() -> None:
    """Anti-SPEC §10.1.1: ouro, UST10 e hedgeado **não** aparecem com proxy silencioso."""
    quadro = pd.read_parquet(caminho_canonical(I.NOME_POR_REGIME))
    assert not set(quadro["asset_id"].unique()) & set(I.ATIVOS_SEM_FONTE)


@pytest.mark.skipif(not (TEM_POR_REGIME and TEM_PESOS), reason=MOTIVO)
def test_acervo_fonte_versao_e_a_mesma_nas_duas_tabelas() -> None:
    """As duas tabelas saem da **mesma** rodada: `fonte_versao` idêntico é o que prova isso."""
    a = pd.read_parquet(caminho_canonical(I.NOME_POR_REGIME))["fonte_versao"].unique()
    b = pd.read_parquet(caminho_canonical(I.NOME_PESOS))["fonte_versao"].unique()
    assert len(a) == len(b) == 1
    assert a[0] == b[0]


@pytest.mark.skipif(not TEM_POR_REGIME, reason=MOTIVO)
def test_acervo_retornos_de_origem_continuam_validos() -> None:
    """A entrada de F-017 não foi tocada por esta feature: continua satisfazendo o contrato dela."""
    alvo = caminho_canonical("asset_returns_quarterly.parquet")
    if not alvo.is_file():
        pytest.skip("asset_returns_quarterly.parquet ausente")
    AssetReturnsQuarterlySchema.validate(pd.read_parquet(alvo), lazy=True)
