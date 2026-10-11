"""Contrato de `AssetReturnsQuarterlySchema` — retorno por ativo (F-017). **Classe C.**

Cada teste pega uma tabela **válida** e quebra **uma** regra, afirmando que o pandera recusa pelo
nome do check ou da coluna. É o complemento de `tests/unit/test_canonical_retornos.py`: lá se
prova que o build produz o número certo, aqui que o contrato **recusa** o errado — inclusive os
erros que um agente futuro cometeria de boa-fé (backfillar o IFIX para 2006, preencher o 1º
trimestre com `0`, publicar menos de 18 ativos, mandar `is_total_return` como `0/1`).

O caso central é `sem_trimestre_antes_do_inicio_da_serie`: **2010Q4 do IFIX é aceito** (é o
trimestre que *contém* 30/12/2010 — parcial, não anterior) e **2010Q3 é recusado**. Quem anula o
retorno de 2010Q4 é a regra de `price_ini` de F-017, não o schema — e isso também tem teste.

Nada aqui lê disco: as linhas são sintéticas e nomeadas como tal (Anti-SPEC §10.1.2).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pandera as pa
import pytest

from packages.shared.schemas import (
    ASSET_IDS_VALIDOS,
    ATIVOS_ACOES_B3,
    ATIVOS_FII,
    ATIVOS_INTERNACIONAIS,
    ATIVOS_RENDA_FIXA,
    N_MINIMO_ATIVOS,
    AssetReturnsQuarterlySchema,
    RegimeAssetMetricsSchema,
)

VERSAO = "0" * 64
"""`fonte_versao` sintético — 64 hexas, o formato de um `sha256`."""

COLUNAS_RETORNOS: tuple[str, ...] = tuple(AssetReturnsQuarterlySchema.to_schema().columns)
"""As colunas do contrato, **na ordem do schema** — nunca digitadas de novo aqui."""

ATIVOS_DA_BASE: tuple[str, ...] = tuple(ASSET_IDS_VALIDOS[:N_MINIMO_ATIVOS])
"""Os 18 primeiros `asset_id` do enum: o mínimo que o check `minimo_de_ativos` exige."""


def linha_sintetica(**sobrescritas: Any) -> dict[str, Any]:
    """Uma linha **válida** de `asset_returns_quarterly`, para ser quebrada em um ponto."""
    base: dict[str, Any] = {
        "quarter": "2006Q2",
        "asset_id": "IBOV",
        "price_ini": 37951.97,
        "price_fim": 36630.66,
        "ret_tri": -0.034815320522228466,
        "ret_excesso_cdi": -0.06815183636009114,
        "ret_real": -0.03577528875027025,
        "vol_intra_tri": 0.156404318393232,
        "dd_intra_tri": -0.21752821450767745,
        "is_total_return": True,
        "n_dias_uteis": 61.0,
        "ffill_dias_uteis": 0,
        "data_inicio_serie": pd.Timestamp("2006-01-02"),
        "source": "B3_API",
        "series_id": "B3_IBOV",
        "fonte_versao": VERSAO,
    }
    base.update(sobrescritas)
    return base


def quadro(*linhas: dict[str, Any]) -> pd.DataFrame:
    """DataFrame no contrato, com `is_total_return` no dtype booleano **anulável**."""
    tabela = pd.DataFrame(list(linhas)).loc[:, list(COLUNAS_RETORNOS)]
    tabela["is_total_return"] = tabela["is_total_return"].astype("boolean")
    return tabela


def base_valida(**sobrescritas: Any) -> pd.DataFrame:
    """18 linhas válidas — uma por `asset_id` — para o check `minimo_de_ativos` passar."""
    return quadro(
        *(linha_sintetica(asset_id=asset_id, **sobrescritas) for asset_id in ATIVOS_DA_BASE)
    )


def erro_de(tabela: pd.DataFrame) -> str:
    """Valida esperando falha e devolve a mensagem — é nela que o nome do check é conferido."""
    with pytest.raises((pa.errors.SchemaErrors, pa.errors.SchemaError)) as capturado:
        AssetReturnsQuarterlySchema.validate(tabela, lazy=True)
    return str(capturado.value)


# ─────────────────────────────────────────────────────────────────────────────
# A tabela válida e as constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────


def test_a_tabela_sintetica_valida_passa() -> None:
    """Sanidade: se a base não passasse, todo teste negativo abaixo seria vacuamente verde."""
    validada = AssetReturnsQuarterlySchema.validate(base_valida(), lazy=True)
    assert len(validada) == N_MINIMO_ATIVOS
    assert tuple(validada.columns) == COLUNAS_RETORNOS


def test_o_enum_de_asset_id_tem_os_32_valores_em_quatro_blocos() -> None:
    """Universo fechado: 9 de renda fixa + 10 de ações + 6 de FII + 7 internacionais = 32."""
    assert len(ASSET_IDS_VALIDOS) == 32
    assert len(set(ASSET_IDS_VALIDOS)) == 32
    assert (
        len(ATIVOS_RENDA_FIXA) + len(ATIVOS_ACOES_B3) + len(ATIVOS_FII) + len(ATIVOS_INTERNACIONAIS)
    ) == 32
    assert "CDI" in ATIVOS_RENDA_FIXA
    assert "IFIX" in ATIVOS_FII
    assert {"SP500_BRL", "SP500_USD", "ACWI_BRL"} <= set(ATIVOS_INTERNACIONAIS)


def test_a_pk_e_quarter_mais_asset_id() -> None:
    """PK `(quarter, asset_id)` — a chave com que o heatmap de F-022 junta regime e ativo."""
    assert AssetReturnsQuarterlySchema.to_schema().unique == ["quarter", "asset_id"]


def test_o_contrato_declara_que_o_excesso_e_por_razao() -> None:
    """A convenção fica **no contrato**, não só no código: `razão, nunca subtração` (§10.2.13).

    Travar o texto é o que impede a próxima pessoa de "simplificar" a fórmula para `r − cdi` e
    continuar com o contrato parecendo o mesmo.
    """
    colunas = AssetReturnsQuarterlySchema.to_schema().columns
    excesso = colunas["ret_excesso_cdi"].description or ""
    real = colunas["ret_real"].description or ""
    assert "(1+ret)/(1+cdi)-1" in excesso.replace(" ", "")
    assert "razão" in excesso and "nunca subtração" in excesso
    assert "(1+ret)/(1+ipca_tri)-1" in real.replace(" ", "")
    assert "mesmo trimestre" in real


def test_o_contrato_declara_is_total_return_como_tri_estado() -> None:
    """`None` = a confirmar (G-01), e não `False`: a flag existe para CA-064."""
    coluna = AssetReturnsQuarterlySchema.to_schema().columns["is_total_return"]
    assert coluna.nullable is True
    assert "None" in (coluna.description or "")


# ─────────────────────────────────────────────────────────────────────────────
# `sem_trimestre_antes_do_inicio_da_serie` — o check do painel desbalanceado (CA-063)
# ─────────────────────────────────────────────────────────────────────────────

IFIX_INICIO = pd.Timestamp("2010-12-30")


def linha_de_ifix(quarter: str, **sobrescritas: Any) -> dict[str, Any]:
    """Uma linha de IFIX naquele trimestre, com o início **real** da série (30/12/2010)."""
    return linha_sintetica(
        quarter=quarter,
        asset_id="IFIX",
        series_id="B3_IFIX",
        data_inicio_serie=IFIX_INICIO,
        **sobrescritas,
    )


def base_com_ifix(quarter: str, **sobrescritas: Any) -> pd.DataFrame:
    """A base de 18 ativos com a linha de IFIX substituída pela do trimestre pedido."""
    linhas = [
        linha_sintetica(asset_id=asset_id) for asset_id in ATIVOS_DA_BASE if asset_id != "IFIX"
    ]
    linhas.append(linha_de_ifix(quarter, **sobrescritas))
    return quadro(*linhas)


def test_o_trimestre_que_contem_o_inicio_do_ifix_e_aceito() -> None:
    """**2010Q4 passa.** Contém 30/12/2010: é parcial, não anterior ao início (CONTRACTS §4)."""
    validada = AssetReturnsQuarterlySchema.validate(
        base_com_ifix("2010Q4", price_ini=None, ret_tri=None), lazy=True
    )
    linha = validada[validada["asset_id"] == "IFIX"].iloc[0]
    assert linha["quarter"] == "2010Q4"
    assert pd.isna(linha["ret_tri"]), "2010Q4 é meia janela: sem T−1 não há retorno"


def test_o_primeiro_retorno_do_ifix_em_2011q1_e_aceito() -> None:
    """**2011Q1 passa com retorno.** É o 1º trimestre em que existe `price_ini` (= 1.000,00)."""
    validada = AssetReturnsQuarterlySchema.validate(
        base_com_ifix("2011Q1", price_ini=1000.00, price_fim=1028.25, ret_tri=0.02825),
        lazy=True,
    )
    linha = validada[validada["asset_id"] == "IFIX"].iloc[0]
    assert linha["ret_tri"] == pytest.approx(0.02825, abs=1e-12)


@pytest.mark.parametrize("quarter", ["2006Q1", "2010Q1", "2010Q2", "2010Q3"])
def test_trimestre_anterior_ao_inicio_do_ifix_e_recusado(quarter: str) -> None:
    """**Backfill sintético proibido** (Anti-SPEC §10.1.1): nenhum IFIX antes de 2010Q4."""
    assert "sem_trimestre_antes_do_inicio_da_serie" in erro_de(base_com_ifix(quarter))


def test_a_comparacao_e_por_trimestre_e_nao_so_por_ano() -> None:
    """A correção E-2 da auditoria: comparar só o ano deixava passar `2010Q1..Q3` do IFIX.

    Se o check olhasse apenas o ano, `2010Q3` passaria — e o IFIX ganharia 3 trimestres que não
    existem, com retorno calculado contra nível inventado.
    """
    assert "sem_trimestre_antes_do_inicio_da_serie" in erro_de(base_com_ifix("2010Q3"))
    AssetReturnsQuarterlySchema.validate(
        base_com_ifix("2010Q4", price_ini=None, ret_tri=None), lazy=True
    )


@pytest.mark.parametrize(
    ("asset_id", "series_id", "inicio", "antes", "primeiro"),
    [
        ("ICON", "B3_ICON", "2006-12-28", "2006Q3", "2006Q4"),
        ("IMOB", "B3_IMOB", "2007-12-28", "2007Q3", "2007Q4"),
    ],
)
def test_icon_e_imob_tambem_sao_barrados_antes_do_seu_inicio(
    asset_id: str, series_id: str, inicio: str, antes: str, primeiro: str
) -> None:
    """Os outros dois casos nomeados na Anti-SPEC §10.1.1 (ADR-005 §3)."""

    def com(quarter: str) -> pd.DataFrame:
        linhas = [linha_sintetica(asset_id=outro) for outro in ATIVOS_DA_BASE if outro != asset_id]
        linhas.append(
            linha_sintetica(
                quarter=quarter,
                asset_id=asset_id,
                series_id=series_id,
                data_inicio_serie=pd.Timestamp(inicio),
                is_total_return=None,
            )
        )
        return quadro(*linhas)

    assert "sem_trimestre_antes_do_inicio_da_serie" in erro_de(com(antes))
    AssetReturnsQuarterlySchema.validate(com(primeiro), lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# `minimo_de_ativos` — CA-062
# ─────────────────────────────────────────────────────────────────────────────


def test_menos_de_dezoito_ativos_e_recusado() -> None:
    """**CA-062.** O entregável exige >= 18 `asset_id` distintos; 17 não passa."""
    tabela = quadro(*(linha_sintetica(asset_id=asset_id) for asset_id in ATIVOS_DA_BASE[:-1]))
    assert "minimo_de_ativos" in erro_de(tabela)


def test_asset_id_fora_do_enum_e_recusado() -> None:
    """Anti-SPEC §10.4.24: ativo inventado não entra, nem com nome plausível."""
    linhas = [linha_sintetica(asset_id=a) for a in ATIVOS_DA_BASE]
    linhas.append(linha_sintetica(asset_id="IBOVESPA_TR", series_id="B3_IBOV"))
    assert "asset_id" in erro_de(quadro(*linhas))


def test_pk_duplicada_e_recusada() -> None:
    """`(quarter, asset_id)` duas vezes é o sintoma de pipeline que duplica em vez de atualizar."""
    linhas = [linha_sintetica(asset_id=a) for a in ATIVOS_DA_BASE]
    linhas.append(linha_sintetica(asset_id="IBOV"))
    assert erro_de(quadro(*linhas))


def test_quarter_fora_da_janela_de_vinte_anos_e_recusado() -> None:
    """A janela do e-mail é 2006→2026: `2005Q4` e `1999Q1` não existem nesta tabela."""
    for quarter in ("2005Q4", "1999Q1", "2006Q5", "2006-Q1"):
        assert "quarter" in erro_de(base_valida(quarter=quarter)), quarter


# ─────────────────────────────────────────────────────────────────────────────
# Domínios numéricos — o que o schema recusa por ser impossível
# ─────────────────────────────────────────────────────────────────────────────


def test_retorno_abaixo_de_menos_cem_por_cento_e_recusado() -> None:
    """`ret_tri < −1` significa valor negativo de um índice: impossível, não "ruim"."""
    assert "ret_tri" in erro_de(base_valida(ret_tri=-1.5))


def test_retorno_absurdamente_alto_e_recusado() -> None:
    """`ret_tri > 5` (500 % num trimestre) é erro de escala, não um trimestre excepcional."""
    assert "ret_tri" in erro_de(base_valida(ret_tri=12.0))


@pytest.mark.parametrize("preco", [0.0, -1.0])
def test_preco_nao_positivo_e_recusado(preco: float) -> None:
    """Número-índice não é zero nem negativo — e dividir por ele daria `inf`."""
    assert "price_ini" in erro_de(base_valida(price_ini=preco))
    assert "price_fim" in erro_de(base_valida(price_fim=preco))


def test_drawdown_positivo_e_recusado() -> None:
    """`dd_intra_tri` é uma queda: `> 0` é sinal invertido, o bug clássico do max drawdown."""
    assert "dd_intra_tri" in erro_de(base_valida(dd_intra_tri=0.05))


def test_volatilidade_negativa_e_recusada() -> None:
    """Desvio-padrão negativo não existe."""
    assert "vol_intra_tri" in erro_de(base_valida(vol_intra_tri=-0.01))


def test_ffill_acima_do_limite_de_cinco_dias_uteis_e_recusado() -> None:
    """ADR-006 §(b).8 / CA-067: acima de 5 d.u. o valor vira `NULL`, não chega aqui com ffill 6."""
    assert "ffill_dias_uteis" in erro_de(base_valida(ffill_dias_uteis=6))


def test_ffill_nulo_e_recusado() -> None:
    """A coluna é não anulável: "não sei quanto preenchi" é pior que 0."""
    assert "ffill_dias_uteis" in erro_de(base_valida(ffill_dias_uteis=None))


def test_mais_de_setenta_dias_uteis_num_trimestre_e_recusado() -> None:
    """Nenhum trimestre tem 71 dias úteis: é dia de outro trimestre entrando na janela."""
    assert "n_dias_uteis" in erro_de(base_valida(n_dias_uteis=71.0))


@pytest.mark.parametrize("coluna", ["data_inicio_serie", "source", "series_id", "fonte_versao"])
def test_rastreabilidade_por_linha_e_obrigatoria(coluna: str) -> None:
    """RF-047/CA-075: linha sem procedência ou sem janela própria não é gravável."""
    assert coluna in erro_de(base_valida(**{coluna: None}))


def test_coluna_a_mais_e_recusada() -> None:
    """`strict = True`: coluna nova no canônico é mudança de contrato, não acréscimo de dado.

    É por isso que a taxonomia de motivo de nulo de F-017 vive no `relatorio_retornos.json` e não
    numa 17ª coluna (`AGENTS.md §13`).
    """
    tabela = base_valida()
    tabela["motivo_nulo"] = "primeiro_trimestre_da_serie_sem_t_menos_1"
    assert erro_de(tabela)


# ─────────────────────────────────────────────────────────────────────────────
# O que o contrato PERMITE — e que é tão importante quanto o que ele recusa
# ─────────────────────────────────────────────────────────────────────────────


def test_metricas_nulas_sao_permitidas_porque_o_primeiro_trimestre_nao_tem_retorno() -> None:
    """O 1º trimestre de cada série entra com `price_fim` e **todas** as métricas nulas."""
    tabela = base_valida(
        price_ini=None,
        ret_tri=None,
        ret_excesso_cdi=None,
        ret_real=None,
        vol_intra_tri=None,
        dd_intra_tri=None,
        n_dias_uteis=None,
    )
    validada = AssetReturnsQuarterlySchema.validate(tabela, lazy=True)
    assert validada["ret_tri"].isna().all()
    assert validada["price_fim"].notna().all(), "o nível de T é dado real e fica"


def test_cdi_sem_nivel_de_preco_e_permitido() -> None:
    """O CDI é taxa acumulada: `price_ini`/`price_fim` nulos, `ret_tri` presente, excesso **0**."""
    linhas = [linha_sintetica(asset_id=a) for a in ATIVOS_DA_BASE if a != "CDI"]
    linhas.append(
        linha_sintetica(
            asset_id="CDI",
            series_id="BCB_SGS_12",
            source="BCB_SGS",
            price_ini=None,
            price_fim=None,
            ret_tri=0.033166778620813187,
            ret_excesso_cdi=0.0,
            ret_real=0.02198733543957454,
            dd_intra_tri=0.0,
            is_total_return=None,
            data_inicio_serie=pd.Timestamp("2004-01-02"),
            quarter="2008Q4",
        )
    )
    validada = AssetReturnsQuarterlySchema.validate(quadro(*linhas), lazy=True)
    cdi = validada[validada["asset_id"] == "CDI"].iloc[0]
    assert pd.isna(cdi["price_ini"]) and pd.isna(cdi["price_fim"])
    assert cdi["ret_excesso_cdi"] == 0.0


def test_is_total_return_nulo_e_permitido_e_nao_vira_zero_ou_um() -> None:
    """**G-01.** Setorial da B3 entra `None`; o dtype é `boolean`, então `None` não vira `0`."""
    validada = AssetReturnsQuarterlySchema.validate(base_valida(is_total_return=None), lazy=True)
    assert str(validada["is_total_return"].dtype) == "boolean"
    assert validada["is_total_return"].isna().all()
    # `object`/`bool` do numpy transformariam `None` em `False` (ou em `0`) sem avisar: o dtype
    # anulável é o que mantém "a confirmar" distinguível de "é price return".
    assert validada["is_total_return"].iloc[0] is pd.NA
    assert not bool((validada["is_total_return"] == False).any())  # noqa: E712


def test_price_e_total_return_convivem_na_mesma_tabela_com_a_flag() -> None:
    """**CA-064.** `SP500_USD` (price) e `IBOV` (total) na mesma tabela, distinguidos pela flag."""
    linhas = [linha_sintetica(asset_id=a) for a in ATIVOS_DA_BASE if a != "SP500_USD"]
    linhas.append(
        linha_sintetica(
            asset_id="SP500_USD",
            series_id="YAHOO_GSPC",
            source="YAHOO",
            is_total_return=False,
        )
    )
    validada = AssetReturnsQuarterlySchema.validate(quadro(*linhas), lazy=True)
    flags = validada.set_index("asset_id")["is_total_return"]
    assert bool(flags["IBOV"]) is True
    assert bool(flags["SP500_USD"]) is False
    comparaveis = validada[validada["is_total_return"].eq(True)]
    assert "SP500_USD" not in set(comparaveis["asset_id"]), (
        "price return não entra numa comparação de total return sem a flag dizer"
    )


# ─────────────────────────────────────────────────────────────────────────────
# A ponte para F-022 (`RegimeAssetMetricsSchema`)
# ─────────────────────────────────────────────────────────────────────────────


def test_as_tres_metricas_de_f017_tem_contraparte_no_schema_por_regime() -> None:
    """O que F-017 entrega por trimestre é o que F-022 agrega por regime — sem coluna órfã."""
    por_regime = set(RegimeAssetMetricsSchema.to_schema().columns)
    assert {"excesso_cdi", "ret_real", "ret_medio"} <= por_regime
    assert "n_obs" in por_regime
    assert RegimeAssetMetricsSchema.to_schema().columns["n_obs"].nullable is False
    assert set(RegimeAssetMetricsSchema.to_schema().unique) == {"lente", "regime", "asset_id"}
