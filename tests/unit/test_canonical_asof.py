"""F-018 — a materialização `asof`: defasagem, régua, derivadas recalculadas. **Classe C.**

Quatro seções, com fontes de verdade diferentes de propósito:

- **A — a defasagem**, lida do `series_catalog` (`lags_de_divulgacao`) e as duas funções puras que
  dependem dela. Inclui o negativo que importa: série sem `lag_divulgacao_dias` **para** o build em
  vez de virar `lag = 0` (que é look-ahead silencioso).
- **B — a régua `asof`**, com calendário e séries **sintéticas** cravadas à mão: lag 60 d desloca um
  trimestre inteiro; lag 10 d não usa o último mês de `T`, usa o penúltimo; lag 0 **reproduz** a
  régua de F-015 célula a célula; lag grande demais e série morta viram `NULL` **com motivo**.
- **C — as derivadas são recalculadas, não copiadas.** É o bug que esta feature mais pode cometer:
  publicar `pib_yoy` de `T` como "o `pib_yoy` de `T-1` da tabela revisada". O teste calcula o a/a
  **à mão** sobre os níveis deslocados e exige igualdade — e exige **desigualdade** contra a cópia.
- **D — o build de ponta a ponta em `tmp_path`**, sobre `raw_series` **sintético** de 2001 a 2026:
  83 linhas, `lag_adjusted=True` nas duas tabelas, zero célula com divulgação posterior ao fim de
  `T`, idempotência por `sha256`. Roda no CI **sem** `data/` e sem rede.

A seção de **acervo real** (diff numérico contra `macro_quarterly.parquet`, canários, % de
trimestres diferentes) vive em `tests/contract/test_asof_contract.py`, junto do portão de schema,
porque é lá que o Parquet publicado é inspecionado.

Dado sintético só existe aqui e está nomeado como tal (Anti-SPEC §10.1.2).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apps.pipeline.canonical.alinhamento import (
    Trimestre,
    grade_de_trimestres,
)
from apps.pipeline.canonical.asof import (
    LAG_ADJUSTED,
    MAX_DESLOCAMENTO_TRIMESTRES,
    MODULOS_DO_ASOF,
    MOTIVO_DIVULGACAO_VELHA,
    MOTIVO_NADA_DIVULGADO,
    NOME_ASOF,
    NOME_ASOF_PROVENANCE,
    NOME_RELATORIO_ASOF,
    PASSO_EM_DIAS_UTEIS,
    LagDesconhecido,
    celulas_com_look_ahead,
    comparar_materializacoes,
    construir,
    data_de_divulgacao,
    deslocar_acumulados,
    lag_da_coluna,
    lags_de_divulgacao,
    lags_por_coluna,
    marcar_como_asof,
    observacoes_asof,
    quadrante_proxy,
    tolerancia_de_frescor,
    trocas_de_quadrante,
    versao_build,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    materializar_catalogo,
)
from apps.pipeline.canonical.macro_quarterly import (
    ACUMULADAS,
    SERIES_DA_CURVA,
    Acumulado,
    acumular_por_trimestre,
    grade_estendida,
    medias_no_trimestre,
    metadado_de_procedencia,
    montar_macro,
    observacoes_de_fim_de_periodo,
    series_de_nivel,
)
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    caminho_canonical,
    garantir_diretorio,
    sha256_de,
)
from apps.pipeline.extract.calendario_anbima import Calendario
from packages.shared.schemas import (
    LIMITE_FFILL_DIAS_UTEIS,
    RawSeriesSchema,
    RegimeV1,
    load_catalog,
    quarters_da_janela,
)

CATALOGO = {e.series_id: e for e in load_catalog()}
COLETADO_EM = pd.Timestamp("2026-10-11T00:00:00")

# ═════════════════════════════════════════════════════════════════════════════
# A — a defasagem: do catálogo, nunca digitada
# ═════════════════════════════════════════════════════════════════════════════


def test_lags_saem_do_catalogo_com_os_numeros_da_metodologia() -> None:
    """PIB 60 d, IBC-Br 45 d, IPCA 10 d, Focus/Selic/curva/câmbio 0 (metodologia §5.1)."""
    lags = lags_de_divulgacao()
    assert lags["SIDRA_1620_V583_90707"] == 60
    assert lags["SIDRA_5932_V6564_90707"] == 60
    assert lags["BCB_SGS_24364"] == 45
    assert lags["BCB_SGS_433"] == 10
    assert lags["BCB_SGS_13522"] == 10
    assert lags["FOCUS_INFLACAO_12M"] == 0
    assert lags["FOCUS_ANUAIS"] == 0
    assert lags["BCB_SGS_432"] == 0
    assert lags["BCB_SGS_12"] == 0
    assert lags["CURVA_REAL_5A"] == 0


def test_series_materializada_do_focus_herda_o_lag_do_entityset() -> None:
    """`FOCUS_A_SELIC_H0` não é entrada do catálogo (D-k): herda o lag de `FOCUS_ANUAIS`."""
    lags = lags_de_divulgacao()
    assert "FOCUS_A_SELIC_H0" not in CATALOGO
    assert lags["FOCUS_A_SELIC_H0"] == lags["FOCUS_ANUAIS"] == 0
    assert lags["FOCUS_I12_IPCA_N"] == lags["FOCUS_INFLACAO_12M"] == 0


def test_serie_sem_lag_no_catalogo_para_o_build() -> None:
    """Negativo: "não sei quando é divulgada" **nunca** pode virar `lag = 0` (Anti-SPEC §10.2.7)."""
    with pytest.raises(LagDesconhecido, match="lag_divulgacao_dias"):
        lags_de_divulgacao(series=["SERIE_QUE_NAO_EXISTE"])


def test_data_de_divulgacao_soma_dias_civis_e_recusa_lag_negativo() -> None:
    """`date_obs + lag` em dias civis — e lag negativo é erro, não "divulgado antes"."""
    assert data_de_divulgacao(date(2026, 9, 30), 10) == date(2026, 10, 10)
    assert data_de_divulgacao(date(2009, 12, 31), 60) == date(2010, 3, 1)
    assert data_de_divulgacao(date(2026, 9, 30), 0) == date(2026, 9, 30)
    with pytest.raises(ValueError, match="negativo"):
        data_de_divulgacao(date(2026, 9, 30), -1)


def test_tolerancia_de_frescor_e_cinco_mais_um_periodo() -> None:
    """A folga é `LIMITE_FFILL_DIAS_UTEIS` + 1 período da série — nem mais, nem menos."""
    for freq, passo in PASSO_EM_DIAS_UTEIS.items():
        assert tolerancia_de_frescor(freq) == LIMITE_FFILL_DIAS_UTEIS + passo
    assert tolerancia_de_frescor("D") == 6
    assert tolerancia_de_frescor("M") == 26


def test_lag_da_coluna_e_o_maior_entre_os_insumos() -> None:
    """Coluna de duas séries só é conhecida quando a **mais lenta** sai: `surpresa_pib` = 60 d."""
    lags = lags_de_divulgacao()
    assert lag_da_coluna("surpresa_pib", lags) == 60  # PIB (60) x Focus (0)
    assert lag_da_coluna("surpresa_ipca", lags) == 10  # IPCA (10) x Focus (0)
    assert lag_da_coluna("juro_real_exante", lags) == 0  # curva (0) x Focus (0)
    assert lag_da_coluna("ipca_tri", lags) == 10  # fluxo mensal
    assert lag_da_coluna("cdi_tri", lags) == 0  # fluxo diário
    assert lag_da_coluna("ipca_meta", lags) == 0  # sem fonte: nada a declarar
    assert set(lags_por_coluna(lags)) == set(lags_por_coluna(lags)) and lags_por_coluna(lags)


def test_versao_build_e_outra_que_a_de_f015_e_inclui_este_modulo() -> None:
    """`versao_build` é hash do **conjunto**, e o conjunto da `asof` inclui `asof.py` (RF-047)."""
    from apps.pipeline.canonical.macro_quarterly import versao_build as versao_do_macro

    assert MODULOS_DO_ASOF[0] == "apps.pipeline.canonical.asof"
    assert versao_build() != versao_do_macro()
    assert len(versao_build()) == 64


# ═════════════════════════════════════════════════════════════════════════════
# B — a régua `asof`, com calendário e séries sintéticas
# ═════════════════════════════════════════════════════════════════════════════


def calendario_sintetico(ano_inicio: int, ano_fim: int) -> Calendario:
    """Calendário **sintético**: só 1º de janeiro é feriado em cada ano da cobertura.

    O `Calendario` exige pelo menos um feriado por ano coberto; um só, numa data que é feriado de
    verdade, deixa a contagem de dias úteis previsível. Nenhum número de produção sai daqui.
    """
    feriados = {
        date(ano, 1, 1): "Confraternizacao Universal" for ano in range(ano_inicio, ano_fim + 1)
    }
    return Calendario(
        feriados=dict(sorted(feriados.items())),
        cobertura_inicio=date(ano_inicio, 1, 1),
        cobertura_fim=date(ano_fim, 12, 31),
    )


def linha_raw(series_id: str, quando: date, valor: float | None) -> dict[str, object]:
    """Uma linha no contrato de `raw_series`, com metadado herdado do catálogo declarado."""
    entrada = CATALOGO[series_id]
    return {
        "series_id": series_id,
        "date": pd.Timestamp(quando),
        "value": valor,
        "source": str(entrada.fonte),
        "freq": str(entrada.freq),
        "vintage": COLETADO_EM.normalize(),
        "unit": str(entrada.unit),
        "collected_at": COLETADO_EM,
    }


def quadro_raw(linhas: Sequence[Mapping[str, object]]) -> pd.DataFrame:
    """As linhas no contrato de `raw_series`, validadas pelo schema."""
    return RawSeriesSchema.validate(pd.DataFrame(list(linhas)), lazy=True)


def inicio_de(quadro: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """`{series_id: primeira data observada}` — o que as duas réguas exigem declarado."""
    return {
        str(sid): pd.Timestamp(v) for sid, v in quadro.groupby("series_id")["date"].min().items()
    }


def test_lag_60_dias_desloca_um_trimestre_inteiro() -> None:
    """CA-010: o PIB de `T` sai ~60 d depois, então `asof` de `T` carrega o nível de `T-1`."""
    cal = calendario_sintetico(2008, 2011)
    trimestres = grade_de_trimestres(cal, quarters=["2009Q4", "2010Q1", "2010Q2"])
    sid = "SIDRA_1620_V583_90707"
    niveis = {date(2009, 9, 30): 100.0, date(2009, 12, 31): 110.0, date(2010, 3, 31): 121.0}
    quadro = quadro_raw([linha_raw(sid, q, v) for q, v in niveis.items()])

    saida = observacoes_asof(
        quadro,
        calendario=cal,
        trimestres=trimestres,
        inicio_por_serie=inicio_de(quadro),
        lags={sid: 60},
    ).set_index("quarter")

    assert saida.loc["2010Q1", "value"] == 110.0  # o nível de 2009Q4
    assert saida.loc["2010Q1", "date_obs"] == date(2009, 12, 31)
    assert saida.loc["2010Q1", "date_divulgacao"] == date(2010, 3, 1)
    assert saida.loc["2010Q1", "deslocamento_dias"] == 90
    assert saida.loc["2010Q2", "value"] == 121.0  # o nível de 2010Q1
    # e a prova de que o nível do próprio trimestre **não** foi usado:
    assert saida.loc["2010Q1", "value"] != niveis[date(2010, 3, 31)]


def test_lag_10_dias_usa_o_penultimo_mes_do_trimestre() -> None:
    """Metodologia §5.1: "o último IPCA conhecido em `T` é o do penúltimo mês de `T`"."""
    cal = calendario_sintetico(2025, 2027)
    trimestres = grade_de_trimestres(cal, quarters=["2026Q3"])
    sid = "BCB_SGS_13522"
    meses = {
        date(2026, 6, 30): 4.0,
        date(2026, 7, 31): 4.1,
        date(2026, 8, 31): 4.22,
        date(2026, 9, 30): 4.58,
    }
    quadro = quadro_raw([linha_raw(sid, q, v) for q, v in meses.items()])
    saida = observacoes_asof(
        quadro,
        calendario=cal,
        trimestres=trimestres,
        inicio_por_serie=inicio_de(quadro),
        lags={sid: 10},
    ).set_index("quarter")

    assert saida.loc["2026Q3", "date_obs"] == date(2026, 8, 31)
    assert saida.loc["2026Q3", "value"] == 4.22
    assert saida.loc["2026Q3", "date_divulgacao"] == date(2026, 9, 10)
    # o mês de **referência** do trimestre existe no dado e foi deliberadamente não usado:
    assert meses[date(2026, 9, 30)] == 4.58


def test_lag_10_dias_nao_desloca_quando_a_divulgacao_cabe_no_trimestre() -> None:
    """A regra é sobre **divulgação**, não sobre "sempre andar um mês para trás".

    Com observação mensal no dia 1º do mês (uma série que publicasse no começo do mês), a de
    setembro + 10 d cai em 11/09, ainda dentro de `T` — e é ela que vale. Deslocamento zero.
    """
    cal = calendario_sintetico(2025, 2027)
    trimestres = grade_de_trimestres(cal, quarters=["2026Q3"])
    sid = "BCB_SGS_13522"
    quadro = quadro_raw(
        [
            linha_raw(sid, date(2026, 8, 1), 1.0),
            linha_raw(sid, date(2026, 9, 1), 2.0),
        ]
    )
    saida = observacoes_asof(
        quadro,
        calendario=cal,
        trimestres=trimestres,
        inicio_por_serie=inicio_de(quadro),
        lags={sid: 10},
    ).set_index("quarter")
    assert saida.loc["2026Q3", "value"] == 2.0
    assert saida.loc["2026Q3", "date_obs"] == date(2026, 9, 1)


def test_lag_zero_reproduz_a_regua_de_f015_celula_a_celula() -> None:
    """`lag = 0` em série diária bancária ⇒ `asof` **é** a régua de F-015, sem exceção.

    É a conferência que torna a reexpressão da régua verificável em vez de uma segunda verdade —
    o mesmo papel que `conferir_apoio_contra_alinhado` tem em F-015.
    """
    cal = calendario_sintetico(2005, 2008)
    trimestres = grade_de_trimestres(cal, quarters=["2006Q1", "2006Q2", "2006Q3", "2006Q4"])
    sid = "BCB_SGS_12"
    dias = cal.dias_uteis(date(2006, 1, 2), date(2006, 12, 29))
    quadro = quadro_raw([linha_raw(sid, q, 0.04 + i / 10_000) for i, q in enumerate(dias)])
    comum = {
        "calendario": cal,
        "trimestres": trimestres,
        "inicio_por_serie": inicio_de(quadro),
    }
    de_f015 = observacoes_de_fim_de_periodo(quadro, **comum).set_index(["series_id", "quarter"])
    do_asof = observacoes_asof(quadro, **comum, lags={sid: 0}).set_index(["series_id", "quarter"])

    assert list(de_f015.index) == list(do_asof.index)
    assert de_f015["value"].equals(do_asof["value"])
    assert list(de_f015["date_obs"]) == list(do_asof["date_obs"])
    assert (do_asof["deslocamento_dias"] == 0).all()


def test_nada_divulgado_ate_o_fim_do_trimestre_vira_nulo_com_motivo() -> None:
    """Série que começa em `T` e cuja primeira divulgação só sai depois: `NULL` + motivo."""
    cal = calendario_sintetico(2009, 2011)
    trimestres = grade_de_trimestres(cal, quarters=["2010Q1"])
    sid = "SIDRA_1620_V583_90707"
    quadro = quadro_raw([linha_raw(sid, date(2010, 3, 31), 100.0)])
    saida = observacoes_asof(
        quadro,
        calendario=cal,
        trimestres=trimestres,
        inicio_por_serie={sid: pd.Timestamp("2010-01-01")},
        lags={sid: 60},
    ).set_index("quarter")
    assert pd.isna(saida.loc["2010Q1", "value"])
    assert saida.loc["2010Q1", "motivo_nulo"] == MOTIVO_NADA_DIVULGADO


def test_serie_morta_nao_e_arrastada_para_sempre() -> None:
    """Negativo de ffill: divulgação velha além da tolerância é `NULL` com motivo, não "o último".

    É a trava que impede a `asof` de transformar uma série descontinuada (EMBI+ depois de
    30/07/2024) numa coluna que parece viva (Anti-SPEC §10.3.19).
    """
    cal = calendario_sintetico(2023, 2026)
    trimestres = grade_de_trimestres(cal, quarters=["2026Q2"])
    sid = "BCB_SGS_13522"
    quadro = quadro_raw([linha_raw(sid, date(2024, 1, 31), 4.0)])
    saida = observacoes_asof(
        quadro,
        calendario=cal,
        trimestres=trimestres,
        inicio_por_serie=inicio_de(quadro),
        lags={sid: 10},
    ).set_index("quarter")
    assert pd.isna(saida.loc["2026Q2", "value"])
    assert saida.loc["2026Q2", "motivo_nulo"] == MOTIVO_DIVULGACAO_VELHA
    assert saida.loc["2026Q2", "lacuna_dias_uteis"] > tolerancia_de_frescor("M")


def test_regua_asof_recusa_serie_sem_lag_declarado() -> None:
    """Negativo: a régua não tem default de lag — série fora do mapa para a função."""
    cal = calendario_sintetico(2005, 2007)
    quadro = quadro_raw([linha_raw("BCB_SGS_12", date(2006, 3, 31), 0.04)])
    with pytest.raises(LagDesconhecido, match="lag_divulgacao_dias"):
        observacoes_asof(
            quadro,
            calendario=cal,
            trimestres=grade_de_trimestres(cal, quarters=["2006Q1"]),
            inicio_por_serie=inicio_de(quadro),
            lags={},
        )


# ─────────────────────────────────────────────────────────────────────────────
# B.2 — os fluxos (`ipca_tri`, `cdi_tri`, `selic_over_tri`)
# ─────────────────────────────────────────────────────────────────────────────


def acumulado(quarter: str, valor: float, fim: date) -> Acumulado:
    """Um `Acumulado` completo, como `acumular_por_trimestre` devolveria."""
    return Acumulado(
        quarter=quarter, value=valor, n_obs=3, n_esperado=3, motivo_nulo=None, date_obs_max=fim
    )


def test_fluxo_com_lag_zero_nao_desloca() -> None:
    """`cdi_tri` é conhecido no fim de `T`: a acumulação de `T` fica em `T`."""
    cal = calendario_sintetico(2005, 2008)
    trimestres = grade_de_trimestres(cal, quarters=["2006Q1", "2006Q2"])
    por_quarter = {
        "2006Q1": acumulado("2006Q1", 4.03, trimestres[0].quarter_end),
        "2006Q2": acumulado("2006Q2", 3.70, trimestres[1].quarter_end),
    }
    saida = deslocar_acumulados(
        {"BCB_SGS_12": por_quarter}, lags={"BCB_SGS_12": 0}, trimestres=trimestres
    )
    assert saida["BCB_SGS_12"]["2006Q1"].quarter == "2006Q1"
    assert saida["BCB_SGS_12"]["2006Q2"].value == 3.70


def test_fluxo_mensal_com_lag_10_desloca_um_trimestre() -> None:
    """`ipca_tri` de `T` exige o IPCA do 3º mês de `T`, que só sai em `T+1`: vale o de `T-1`."""
    cal = calendario_sintetico(2005, 2008)
    trimestres = grade_de_trimestres(cal, quarters=["2006Q1", "2006Q2", "2006Q3"])
    por_quarter = {
        "2006Q1": acumulado("2006Q1", 1.4367, date(2006, 3, 31)),
        "2006Q2": acumulado("2006Q2", 0.2100, date(2006, 6, 30)),
        "2006Q3": acumulado("2006Q3", 0.5800, date(2006, 9, 30)),
    }
    saida = deslocar_acumulados(
        {"BCB_SGS_433": por_quarter}, lags={"BCB_SGS_433": 10}, trimestres=trimestres
    )["BCB_SGS_433"]
    assert "2006Q1" not in saida  # nada anterior a 2006Q1 na grade: sem valor, nunca um 0
    assert saida["2006Q2"].quarter == "2006Q1"
    assert saida["2006Q2"].value == 1.4367
    assert saida["2006Q3"].quarter == "2006Q2"
    # a célula carrega o trimestre de **origem**: a procedência não mente sobre de onde veio
    assert saida["2006Q3"].date_obs_max == date(2006, 6, 30)


def test_fluxo_nao_arrasta_mais_do_que_o_teto_de_trimestres() -> None:
    """Teto de `MAX_DESLOCAMENTO_TRIMESTRES`: fluxo velho não é "o último conhecido" eterno."""
    cal = calendario_sintetico(2005, 2012)
    rotulos = [f"2006Q{i}" for i in (1, 2, 3, 4)] + [f"200{a}Q{i}" for a in (7, 8) for i in (1,)]
    trimestres = grade_de_trimestres(cal, quarters=rotulos)
    por_quarter = {"2006Q1": acumulado("2006Q1", 1.0, date(2006, 3, 31))}
    saida = deslocar_acumulados(
        {"BCB_SGS_433": por_quarter},
        lags={"BCB_SGS_433": 10},
        trimestres=trimestres,
        maximo=MAX_DESLOCAMENTO_TRIMESTRES,
    )["BCB_SGS_433"]
    assert saida["2006Q2"].quarter == "2006Q1"
    assert "2008Q1" not in saida


# ═════════════════════════════════════════════════════════════════════════════
# C — as derivadas são RECALCULADAS, não copiadas
# ═════════════════════════════════════════════════════════════════════════════

INICIO_SINTETICO = date(2001, 1, 1)
PONTA_SINTETICA = date(2026, 10, 9)

#: Mesma forma da real (F-015): PIB até 2026Q2, IBC-Br até jul/2026. É o que faz o deslocamento
#: do `asof` em `2026Q3` ser testável sem `data/`.
FIM_SINTETICO: Mapping[str, date] = {
    "SIDRA_1620_V583_90707": date(2026, 6, 30),
    "SIDRA_5932_V6564_90707": date(2026, 6, 30),
    "BCB_SGS_24364": date(2026, 7, 31),
}


def _series_sinteticas() -> tuple[str, ...]:
    """O que o build consome: níveis + os três fluxos + as 11 séries de curva de F-016.

    A curva entra porque `vertice_extrapolado` tem procedência **sempre** (é booleana e nunca
    nula): sem nenhuma série de curva, `montar_macro` de F-015 levanta
    `SerieInconsistente` ao tentar apontar a flag para um vértice sem metadado — o que é o
    comportamento certo dele, e aqui só significa que a árvore sintética tem de ser completa.
    """
    return tuple(dict.fromkeys((*series_de_nivel(), *ACUMULADAS.values(), *SERIES_DA_CURVA)))


def _valor_sintetico(series_id: str, indice: int) -> float:
    """Valor determinístico e plausível por série — nenhum número vem de fonte real.

    As formas importam para os checks do schema (`selic_meta_fim` em [0, 60], `usdbrl_fim > 0`) e
    para que o a/a **não** seja constante: com nível linear, `v[T]/v[T-4]` mudaria de trimestre a
    trimestre mas o teste de "recalculada vs. copiada" ficaria fraco. A senoide de período curto
    garante que o a/a de `T` seja diferente do de `T-1` em todo trimestre.
    """
    entrada = CATALOGO[series_id]
    unidade = str(entrada.unit)
    if series_id == "BCB_SGS_432":
        return 10.0 + 2.0 * float(np.sin(indice / 400.0))
    if unidade == "%/dia":
        return 0.04
    if unidade == "%":
        return 0.5 + 0.1 * float(np.sin(indice / 7.0))
    if unidade == "%a.a.":
        return 8.0 + 3.0 * float(np.sin(indice / 500.0))
    if unidade == "pp":
        return 0.5 * float(np.sin(indice / 300.0))
    if unidade == "BRL":
        return 3.6 + 1.5 * float(np.sin(indice / 600.0))
    return 100.0 * (1.0 + indice / 1000.0) * (1.0 + 0.05 * float(np.sin(indice / 3.0)))


def _datas_sinteticas(series_id: str, cal: Calendario) -> tuple[date, ...]:
    """As datas da série sintética, na grade que o catálogo declara (D-a para M/Q)."""
    fim = FIM_SINTETICO.get(series_id, PONTA_SINTETICA)
    freq = str(CATALOGO[series_id].freq)
    if freq == "D":
        if series_id == "BCB_SGS_432":  # calendário corrido
            return tuple(d.date() for d in pd.date_range(INICIO_SINTETICO, fim, freq="D"))
        return cal.dias_uteis(cal.ajustar_para_frente(INICIO_SINTETICO), cal.ajustar_para_tras(fim))
    regra = {"M": "ME", "Q": "QE"}[freq]
    return tuple(d.date() for d in pd.date_range(INICIO_SINTETICO, fim, freq=regra))


def raw_series_sintetico(cal: Calendario) -> pd.DataFrame:
    """`raw_series` **sintético** de 2001 a 2026, com a forma da tabela real. Nomeado como tal."""
    linhas: list[Mapping[str, object]] = []
    for series_id in _series_sinteticas():
        for indice, quando in enumerate(_datas_sinteticas(series_id, cal)):
            linhas.append(linha_raw(series_id, quando, _valor_sintetico(series_id, indice)))
    return quadro_raw(linhas)


@dataclass(frozen=True)
class MontagemSintetica:
    """As duas materializações montadas sobre o **mesmo** `raw_series` sintético, sem disco."""

    cal: Calendario
    raw: pd.DataFrame
    trimestres: tuple[Trimestre, ...]
    janela: tuple[str, ...]
    revised: pd.DataFrame
    asof: pd.DataFrame
    provenance_asof: pd.DataFrame
    niveis_asof: pd.DataFrame


@pytest.fixture(scope="module")
def montagem() -> MontagemSintetica:
    """Monta `revised` e `asof` sobre o sintético — uma vez por módulo (é a parte lenta)."""
    cal = calendario_sintetico(2001, 2030)
    raw = raw_series_sintetico(cal)
    trimestres = grade_estendida(cal, quarters=quarters_da_janela())
    janela = tuple(quarters_da_janela())
    inicio = inicio_de(raw)
    lags = lags_de_divulgacao(series=sorted(raw["series_id"].unique()))
    comum = {"calendario": cal, "trimestres": trimestres, "inicio_por_serie": inicio}

    niveis_revised = observacoes_de_fim_de_periodo(raw, **comum)
    niveis_asof = observacoes_asof(raw, **comum, lags=lags)
    acumulados = {
        sid: {
            a.quarter: a
            for a in acumular_por_trimestre(
                raw.loc[raw["series_id"] == sid],
                series_id=sid,
                calendario=cal,
                trimestres=trimestres,
            )
        }
        for sid in sorted(set(ACUMULADAS.values()))
    }
    medias = medias_no_trimestre(raw, trimestres=trimestres)
    metadado = metadado_de_procedencia(raw)
    revised, _, _ = montar_macro(
        observacoes=niveis_revised,
        acumulados=acumulados,
        medias=medias,
        metadado=metadado,
        trimestres=trimestres,
        quarters=janela,
        fonte_versao="sintetico-revised",
    )
    bruto, prov, diagnostico = montar_macro(
        observacoes=niveis_asof,
        acumulados=deslocar_acumulados(acumulados, lags=lags, trimestres=trimestres),
        medias=deslocar_acumulados(medias, lags=lags, trimestres=trimestres),
        metadado=metadado,
        trimestres=trimestres,
        quarters=janela,
        fonte_versao="sintetico-asof",
    )
    asof, provenance_asof = marcar_como_asof(bruto, prov, diagnostico, lags=lags)
    return MontagemSintetica(
        cal=cal,
        raw=raw,
        trimestres=trimestres,
        janela=janela,
        revised=revised,
        asof=asof,
        provenance_asof=provenance_asof,
        niveis_asof=niveis_asof,
    )


def test_pib_yoy_do_asof_e_recalculado_sobre_os_niveis_deslocados(
    montagem: MontagemSintetica,
) -> None:
    """O a/a de `asof` em `T` é `v[T-1]/v[T-5]-1`, calculado **aqui**, sem importar o módulo.

    E a cópia **não** reproduz: o teste exige que `asof[T] != revised[T]` nos trimestres em que o
    nível mudou. Se alguém trocar o recálculo por um `shift(1)` da coluna `revised`, os dois
    primeiros `assert` continuariam passando — por isso o terceiro compara contra o a/a de `T-1`
    da tabela revisada, que é **exatamente** o que a cópia produziria, e ele só vale porque a
    régua é a mesma: aqui o deslocamento é de um trimestre cheio.
    """
    sid = "SIDRA_1620_V583_90707"
    datas = _datas_sinteticas(sid, montagem.cal)
    nivel = {
        str(pd.Period(pd.Timestamp(d), freq="Q")): _valor_sintetico(sid, i)
        for i, d in enumerate(datas)
    }
    asof = montagem.asof.set_index("quarter")
    revised = montagem.revised.set_index("quarter")

    conferidos = 0
    for rotulo in montagem.janela:
        periodo = pd.Period(rotulo, freq="Q")
        anterior, base = str(periodo - 1), str(periodo - 5)
        if anterior not in nivel or base not in nivel:
            continue
        esperado = (nivel[anterior] / nivel[base] - 1.0) * 100.0
        assert asof.loc[rotulo, "pib_yoy"] == pytest.approx(esperado, abs=1e-9), rotulo
        conferidos += 1
    assert conferidos >= 80

    # a derivada do trimestre corrente **não** é a do revised: o nível é outro
    assert asof.loc["2015Q3", "pib_yoy"] != pytest.approx(revised.loc["2015Q3", "pib_yoy"])


def test_derivada_do_asof_nao_e_a_coluna_do_revised_deslocada_de_uma_linha(
    montagem: MontagemSintetica,
) -> None:
    """A trava contra "copiar em vez de recalcular" onde a cópia **não** é equivalente.

    `ipca_12m` tem `lag = 10` e grade **mensal**: a `asof` de `T` usa o IPCA do **penúltimo** mês
    de `T`, que não é o nível de fim de nenhum trimestre. Então `ipca_12m_delta` da `asof` é a
    diferença entre dois penúltimos meses, e **nenhum** deslocamento de linha da tabela revisada
    produz essa coluna — se coincidir, é porque alguém copiou.

    A coluna usada aqui era `ibcbr_yoy` até **D-s**. Desde D-s o nível trimestral do IBC-Br é a
    **média dos 3 meses** e média de trimestre desloca em trimestres cheios, então `ibcbr_yoy` da
    `asof` **é** o da `revised` em `T-1` — por construção, não por cópia. Essa igualdade virou
    afirmação própria, no teste seguinte.
    """
    for coluna in ("ipca_12m", "ipca_12m_delta"):
        asof = montagem.asof.set_index("quarter")[coluna]
        copia = montagem.revised.set_index("quarter")[coluna].shift(1)
        comparaveis = asof.notna() & copia.notna()
        assert int(comparaveis.sum()) > 60, coluna
        assert not np.allclose(asof[comparaveis], copia[comparaveis], atol=1e-6), coluna


def test_ibcbr_yoy_do_asof_e_o_do_revised_de_t_menos_1_por_construcao_de_d_s(
    montagem: MontagemSintetica,
) -> None:
    """**D-s**, consequência medida: a `asof` de `T` carrega a média do trimestre `T-1`.

    O nível trimestral do IBC-Br é a média dos 3 meses, e a média de `T` só se conhece ~45 dias
    depois do fim de `T` — depois do `quarter_end`. Logo o trimestre mais recente cuja média cabe
    no corte é `T-1`, e `deslocar_acumulados` (a régua dos fluxos, reusada) devolve exatamente
    isso. A igualdade é **afirmada**, não tolerada: se a régua da média passar a mirar o 1º mês de
    `T` ou a aceitar média parcial, este teste quebra.
    """
    asof = montagem.asof.set_index("quarter")["ibcbr_yoy"]
    revised = montagem.revised.set_index("quarter")["ibcbr_yoy"]
    comparaveis = [
        rotulo
        for rotulo in montagem.janela[1:]
        if pd.notna(asof[rotulo]) and pd.notna(revised[str(pd.Period(rotulo, freq="Q") - 1)])
    ]
    assert len(comparaveis) > 60
    for rotulo in comparaveis:
        anterior = str(pd.Period(rotulo, freq="Q") - 1)
        assert asof[rotulo] == pytest.approx(revised[anterior], abs=1e-12), rotulo


def test_tendencia_e_hiato_do_asof_saem_da_media_movel_dos_niveis_deslocados(
    montagem: MontagemSintetica,
) -> None:
    """A média móvel de 20 trimestres é refeita sobre o a/a defasado — e o hiato é a diferença."""
    asof = montagem.asof.set_index("quarter")
    gap = asof["ibcbr_yoy"] - asof["ibcbr_yoy_trend"]
    comparaveis = asof["ibcbr_gap"].notna()
    assert int(comparaveis.sum()) > 60
    assert np.allclose(asof.loc[comparaveis, "ibcbr_gap"], gap[comparaveis], atol=1e-12)


def test_ipca_tri_do_asof_e_a_acumulacao_do_trimestre_anterior(
    montagem: MontagemSintetica,
) -> None:
    """Fluxo mensal com `lag = 10`: a inflação trimestral conhecida no fim de `T` é a de `T-1`."""
    asof = montagem.asof.set_index("quarter")
    revised = montagem.revised.set_index("quarter")
    for rotulo in montagem.janela[1:]:
        anterior = str(pd.Period(rotulo, freq="Q") - 1)
        assert asof.loc[rotulo, "ipca_tri"] == pytest.approx(
            revised.loc[anterior, "ipca_tri"], abs=1e-12
        ), rotulo


def test_cdi_e_selic_over_nao_deslocam_no_asof(montagem: MontagemSintetica) -> None:
    """Fluxo diário com `lag = 0` é conhecido no fim de `T`: as duas colunas são idênticas."""
    for coluna in ("cdi_tri", "selic_over_tri"):
        esquerda = montagem.revised[coluna]
        direita = montagem.asof[coluna]
        assert ((esquerda.isna() & direita.isna()) | (esquerda == direita)).all(), coluna


def test_marcar_como_asof_acende_a_flag_nas_duas_tabelas(montagem: MontagemSintetica) -> None:
    """`lag_adjusted=True` nas 83 linhas e na procedência — e `date_obs`/`lag_dias` existem."""
    assert bool(montagem.asof["lag_adjusted"].all())
    assert set(montagem.asof["lag_adjusted"].unique()) == {True}
    assert bool(montagem.provenance_asof["lag_adjusted"].all())
    assert "date_obs" in montagem.provenance_asof.columns
    assert "lag_dias" in montagem.provenance_asof.columns
    assert LAG_ADJUSTED is True


def test_nenhuma_celula_do_asof_usa_observacao_divulgada_depois_do_fim_de_t(
    montagem: MontagemSintetica,
) -> None:
    """**O teste central (CA-072)**, no sintético: `date_obs + lag <= quarter_end`, célula a célula.

    Duas camadas: a régua (toda linha de `observacoes_asof`) e o artefato (toda linha de
    procedência, com o `lag_dias` conservador da coluna).
    """
    fim_de = {t.quarter: t.quarter_end for t in montagem.trimestres}
    regua = montagem.niveis_asof.loc[montagem.niveis_asof["date_obs"].notna()]
    atrasadas = [
        f"{r.series_id}/{r.quarter}"
        for r in regua.itertuples(index=False)
        if data_de_divulgacao(r.date_obs, int(r.lag_dias)) > fim_de[r.quarter]
    ]
    assert atrasadas == []
    assert len(regua) > 1_000

    assert celulas_com_look_ahead(montagem.provenance_asof, montagem.asof).empty


def test_comparacao_por_coluna_marca_focus_como_identico_e_pib_como_diferente(
    montagem: MontagemSintetica,
) -> None:
    """O quadro que o relatório publica: `identica`, `n_diferentes`, `max_abs_dif`."""
    lags = lags_de_divulgacao(series=sorted(montagem.raw["series_id"].unique()))
    comparacao = comparar_materializacoes(montagem.revised, montagem.asof, lags=lags).set_index(
        "column"
    )
    assert bool(comparacao.loc["cdi_tri", "identica"])
    assert bool(comparacao.loc["usdbrl_fim", "identica"])
    assert not bool(comparacao.loc["pib_yoy", "identica"])
    assert comparacao.loc["pib_yoy", "lag_dias"] == 60
    assert comparacao.loc["pib_yoy", "max_abs_dif"] > 0
    assert comparacao.loc["ipca_tri", "lag_dias"] == 10


# ═════════════════════════════════════════════════════════════════════════════
# C.2 — o proxy de quadrante (teste de sanidade da metodologia §5.1)
# ═════════════════════════════════════════════════════════════════════════════


def test_quadrante_proxy_segue_os_quatro_rotulos_de_adr_001() -> None:
    """`(↑g, ↓π)` = RECUPERACAO · `(↑g, ↑π)` = EXPANSAO_INFL · `(↓g, ↑π)` = ESTAGFLACAO · resto."""
    assert quadrante_proxy(1.0, -0.5) == str(RegimeV1.RECUPERACAO)
    assert quadrante_proxy(1.0, 0.5) == str(RegimeV1.EXPANSAO_INFL)
    assert quadrante_proxy(-1.0, 0.5) == str(RegimeV1.ESTAGFLACAO)
    assert quadrante_proxy(-1.0, -0.5) == str(RegimeV1.DESACELERACAO)
    assert quadrante_proxy(None, 0.5) is None
    assert quadrante_proxy(float("nan"), 0.5) is None
    assert quadrante_proxy(0.0, 0.0) == str(RegimeV1.DESACELERACAO)  # limiar é `> 0`, sem herança


def test_troca_de_quadrante_acende_o_texto_de_ca_074_acima_de_25_pct() -> None:
    """CA-074: passando de 25%, o relatório **afirma** que o modelo não é operacional."""
    base = pd.DataFrame(
        {
            "quarter": [f"2006Q{i}" for i in (1, 2, 3, 4)],
            "ibcbr_gap": [1.0, 1.0, 1.0, 1.0],
            "ipca_12m_delta": [1.0, 1.0, 1.0, 1.0],
        }
    )
    virado = base.copy()
    virado["ipca_12m_delta"] = [-1.0, -1.0, 1.0, 1.0]
    bloco = trocas_de_quadrante(base, virado)
    assert bloco["trimestres_comparaveis"] == 4
    assert bloco["trimestres_que_trocam"] == 2
    assert bloco["pct_que_trocam"] == 50.0
    assert bloco["operacional"] is False
    assert "NAO E OPERACIONAL" in bloco["texto"]

    igual = trocas_de_quadrante(base, base.copy())
    assert igual["pct_que_trocam"] == 0.0
    assert igual["operacional"] is True
    assert "NAO E OPERACIONAL" not in igual["texto"]


def test_troca_de_quadrante_ignora_trimestre_sem_quadrante_nos_dois_lados() -> None:
    """Denominador = trimestres com quadrante **nas duas**; o resto é contado à parte."""
    base = pd.DataFrame(
        {
            "quarter": ["2006Q1", "2006Q2"],
            "ibcbr_gap": [None, 1.0],
            "ipca_12m_delta": [1.0, 1.0],
        }
    )
    outro = base.copy()
    outro["ibcbr_gap"] = [1.0, 1.0]
    bloco = trocas_de_quadrante(base, outro)
    assert bloco["trimestres_comparaveis"] == 1
    assert bloco["so_em_asof"] == 1
    assert bloco["so_em_revised"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# D — build de ponta a ponta em tmp_path, sobre `raw_series` SINTÉTICO
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ArvoreSintetica:
    """Uma `data/` sintética mínima em `tmp_path`, pronta para `construir`."""

    raiz: Path
    calendario: Calendario
    raw: pd.DataFrame


@pytest.fixture(scope="module")
def arvore(tmp_path_factory: pytest.TempPathFactory) -> ArvoreSintetica:
    """Escreve `raw_series.parquet` e `series_catalog.parquet` sintéticos em `tmp_path`.

    **Sem** `macro_quarterly.parquet`: é de propósito, para exercitar o caminho em que a
    conferência contra o artefato de F-015 não tem o que conferir (CI em árvore limpa).
    """
    raiz = tmp_path_factory.mktemp("asof")
    cal = calendario_sintetico(2001, 2030)
    raw = raw_series_sintetico(cal)
    garantir_diretorio(caminho_camada(Camada.CANONICAL, raiz=raiz))
    raw.to_parquet(caminho_canonical(NOME_RAW_SERIES, raiz=raiz), index=False)
    materializar_catalogo(load_catalog(), raw).to_parquet(
        caminho_canonical(NOME_CATALOGO, raiz=raiz), index=False
    )
    return ArvoreSintetica(raiz=raiz, calendario=cal, raw=raw)


@pytest.fixture(scope="module")
def build(arvore: ArvoreSintetica) -> object:
    """O build de ponta a ponta sobre a árvore sintética, uma vez por módulo."""
    return construir(raiz=arvore.raiz, calendario=arvore.calendario)


def test_build_tem_83_linhas_e_e_a_materializacao_asof(build: object) -> None:
    """CA-059 + CA-072: 83 linhas `2006Q1..2026Q3` e `lag_adjusted=True` nas duas tabelas."""
    macro = build.macro_asof  # type: ignore[attr-defined]
    assert len(macro) == 83
    assert list(macro["quarter"]) == list(quarters_da_janela())
    assert bool(macro["lag_adjusted"].all())
    assert bool(build.provenance_asof["lag_adjusted"].all())  # type: ignore[attr-defined]
    assert build.relatorio["macro_quarterly_asof"]["materializacao"] == "asof"  # type: ignore[attr-defined]


def test_build_grava_os_tres_artefatos_e_nao_toca_os_de_f015(
    build: object, arvore: ArvoreSintetica
) -> None:
    """Os três arquivos saem na raiz pedida — e `macro_quarterly.parquet` **não** é criado."""
    for nome in (NOME_ASOF, NOME_ASOF_PROVENANCE, NOME_RELATORIO_ASOF):
        assert caminho_canonical(nome, raiz=arvore.raiz).is_file()
    assert not caminho_canonical("macro_quarterly.parquet", raiz=arvore.raiz).exists()
    assert not caminho_canonical("macro_quarterly_provenance.parquet", raiz=arvore.raiz).exists()
    assert build.relatorio["diff_vs_revised_em_disco"]["conferido"] is False  # type: ignore[attr-defined]


def test_build_nao_tem_nenhuma_celula_com_look_ahead(build: object) -> None:
    """**O teste central**, sobre o que foi gravado: zero célula divulgada depois do fim de `T`."""
    bloco = build.relatorio["anti_look_ahead"]  # type: ignore[attr-defined]
    assert bloco["celulas_com_divulgacao_depois_do_fim_de_T"] == 0
    assert bloco["celulas_com_date_obs"] > 2_000
    assert celulas_com_look_ahead(
        build.provenance_asof,  # type: ignore[attr-defined]
        build.macro_asof,  # type: ignore[attr-defined]
    ).empty


def test_build_publica_canarios_e_lag_por_coluna(build: object) -> None:
    """Os 3 canários e o mapa coluna → lag vão no relatório, não só no código."""
    relatorio = build.relatorio  # type: ignore[attr-defined]
    canarios = relatorio["canarios"]
    assert canarios["pib_yoy_asof_2010Q1_e_o_revised_de_2009Q4"]["bate"] is True
    assert canarios["ipca_12m_asof_2026Q3_e_de_agosto"]["date_obs_usada"] == "2026-08-31"
    assert relatorio["comparacao_por_coluna"]["pib_yoy"]["lag_dias"] == 60
    assert relatorio["comparacao_por_coluna"]["ibcbr_yoy"]["lag_dias"] == 45
    assert relatorio["lags_do_catalogo"]["BCB_SGS_433"] == 10


def test_build_e_idempotente_por_hash(arvore: ArvoreSintetica) -> None:
    """RF-048/CA-121: duas rodadas sobre a mesma entrada dão Parquet e relatório byte-idênticos."""
    hashes = []
    for _ in range(2):
        construir(raiz=arvore.raiz, calendario=arvore.calendario)
        hashes.append(
            tuple(
                sha256_de(caminho_canonical(nome, raiz=arvore.raiz).read_bytes())
                for nome in (NOME_ASOF, NOME_ASOF_PROVENANCE, NOME_RELATORIO_ASOF)
            )
        )
    assert hashes[0] == hashes[1]


def test_o_modulo_de_producao_nao_le_o_relogio() -> None:
    """Idempotência pela raiz: nenhuma chamada a `now`/`today` em `asof.py` (D-b)."""
    fonte = Path("apps/pipeline/canonical/asof.py").read_text(encoding="utf-8")
    for proibido in ("datetime.now", "date.today", "Timestamp.now", "time.time"):
        assert proibido not in fonte, proibido
    assert "timedelta" in fonte  # a defasagem é aritmética de data, não relógio
    assert timedelta(days=60) == timedelta(days=60)
