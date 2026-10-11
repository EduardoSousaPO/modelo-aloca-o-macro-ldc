"""F-015 — `macro_quarterly`: transformações, acumulação, grade e build. **Classe C.**

Quatro seções, com fontes de verdade diferentes de propósito:

- **A — as transformações puras** (`variacao_por_razao`, `diferenca_em_pp`, `media_movel`,
  `hiato_vs_tendencia`, `acumulacao_geometrica`, `ciclo_selic`, `focus_do_inicio_do_trimestre`),
  sobre números **sintéticos** cravados à mão. Cada uma tem um teste nomeado, e os casos negativos
  (subtração no lugar da razão, soma no lugar do produto, janela de 19 trimestres) **falham**.
- **B — a grade e a observação de fim de período**, com calendário **sintético** (sem feriado além
  de 1º de janeiro), porque só assim se constrói lacuna de exatamente 5 e de exatamente 6 dias
  úteis. Dado sintético só existe aqui e está nomeado como tal (Anti-SPEC §10.1.2).
- **C — o build de ponta a ponta em `tmp_path`**, sobre um `raw_series` **sintético** de 2001 a
  2026 que reproduz a forma do real (PIB até 2026Q2, IBC-Br até jul/2026). É o que faz CA-059,
  CA-060 e CA-120 rodarem no CI **sem** `data/` e sem rede.
- **D — acervo real** (`data/canonical/`), no padrão `Acervo` de F-014: diff numérico contra
  `alinhado_trimestral`, reconstrução independente de cada derivada, anti-look-ahead, canários e
  idempotência por `sha256`. `LDC_IGNORAR_DATA=1` desliga esta seção (é a árvore limpa do CI).

O **diff numérico da classe C** está em
`test_acervo_todo_nivel_e_identico_a_celula_do_alinhado` e em
`test_acervo_derivadas_reproduzidas_por_conta_independente` (seção D): cada nível é comparado sem
tolerância à célula de F-014, e cada derivada é recalculada por uma conta escrita **aqui**, que não
importa nada do módulo sob teste.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import apps.pipeline.canonical.macro_quarterly as macro_quarterly_modulo
from apps.pipeline.canonical.alinhamento import (
    Trimestre,
    grade_de_trimestres,
)
from apps.pipeline.canonical.alinhamento import (
    construir as construir_alinhado,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    materializar_catalogo,
)
from apps.pipeline.canonical.macro_quarterly import (
    ACUMULADAS,
    CATALOGO_DO_FOCUS,
    MEDIAS,
    MOTIVO_SERIE_SEM_VALOR,
    MOTIVO_TRIMESTRE_INCOMPLETO,
    N_TRIMESTRES_TENDENCIA,
    NOME_MACRO,
    NOME_PROVENANCE,
    NOME_RELATORIO,
    ORIGENS,
    SERIES_DA_CURVA,
    SERIES_DO_FOCUS,
    Acumulado,
    ApoioDivergente,
    acumulacao_geometrica,
    acumular_por_trimestre,
    carregar_focus,
    ciclo_selic,
    conferir_apoio_contra_alinhado,
    construir,
    diferenca_em_pp,
    focus_do_inicio_do_trimestre,
    grade_estendida,
    hiato_vs_tendencia,
    insumos_da_coluna,
    media_movel,
    media_por_trimestre,
    medias_no_trimestre,
    observacoes_de_fim_de_periodo,
    quarters_de_apoio,
    sensibilidade_da_tendencia,
    series_de_nivel,
    variacao_por_razao,
    versao_build,
)
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    caminho_canonical,
    garantir_diretorio,
    sha256_de,
)
from apps.pipeline.extract.calendario_anbima import Calendario
from packages.shared.schemas import (
    COLUNAS_RASTREAVEIS,
    LIMITE_FFILL_DIAS_UTEIS,
    MacroQuarterlyProvenanceSchema,
    MacroQuarterlySchema,
    RawSeriesSchema,
    load_catalog,
    quarters_da_janela,
)
from packages.shared.schemas.regimes import LIMIAR_SELIC_PP

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
"""Liga o modo "árvore limpa": só o sintético entra, `data/` é ignorado (padrão de F-014)."""

CATALOGO = {entrada.series_id: entrada for entrada in load_catalog()}
"""O catálogo declarado, indexado — toda série sintética herda dele `source`/`freq`/`unit`."""

COLETADO_EM = pd.Timestamp("2026-10-11 03:00:00")
"""`collected_at` sintético, fixo: o schema exige `date <= collected_at` e o build é idempotente."""


# ═════════════════════════════════════════════════════════════════════════════
# A — transformações puras, sobre números cravados à mão
# ═════════════════════════════════════════════════════════════════════════════


def test_variacao_a_a_e_a_razao_entre_t_e_t_menos_4() -> None:
    """a/a numa grade trimestral é `v[T]/v[T-4]-1`, em por cento."""
    serie = pd.Series([100.0, 101.0, 102.0, 103.0, 110.0], index=list("abcde"))
    saida = variacao_por_razao(serie, 4)
    assert saida.iloc[:4].isna().all(), "sem T-4 não há a/a: nulo, nunca 0"
    assert saida.iloc[4] == pytest.approx(10.0)


def test_variacao_t_t_e_a_razao_entre_t_e_t_menos_1() -> None:
    """t/t é o mesmo cálculo com `passos=1` — é o que CA-044 pede para `usdbrl_var_tri`."""
    serie = pd.Series([2.0, 2.5, 2.0])
    saida = variacao_por_razao(serie, 1)
    assert saida.iloc[1] == pytest.approx(25.0)
    assert saida.iloc[2] == pytest.approx(-20.0)


def test_variacao_por_razao_difere_da_diferenca_de_niveis() -> None:
    """Negativo: quem usar `v[T]-v[T-1]` no lugar da razão obtém **outro** número.

    PTAX de 2,00 para 2,50: a razão diz **+25%**; a diferença de níveis diz `0,50`, que não é
    variação percentual nenhuma. O teste existe para que trocar a fórmula quebre (CA-044).
    """
    serie = pd.Series([2.0, 2.5])
    assert variacao_por_razao(serie, 1).iloc[1] == pytest.approx(25.0)
    assert float(serie.diff().iloc[1]) == pytest.approx(0.5)
    assert variacao_por_razao(serie, 1).iloc[1] != pytest.approx(float(serie.diff().iloc[1]))


def test_variacao_por_razao_com_base_zero_da_nulo_e_nao_infinito() -> None:
    """Denominador `0` → `NaN`. Nunca `inf`, nunca `0` (Anti-SPEC §10.1.4)."""
    serie = pd.Series([0.0, 5.0])
    assert pd.isna(variacao_por_razao(serie, 1).iloc[1])


def test_variacao_por_razao_rejeita_passos_zero() -> None:
    """`passos=0` compararia T consigo mesmo: erro de programação, não resultado."""
    with pytest.raises(ValueError, match="passos"):
        variacao_por_razao(pd.Series([1.0, 2.0]), 0)


def test_diferenca_em_pp_e_a_aceleracao_do_ipca_12m() -> None:
    """`ipca_12m_delta` é o eixo de inflação da V1 (ADR-001 §4): Δ em pontos percentuais.

    IPCA 12m de 4,50 → 5,20 → 5,00: a aceleração é `+0,70` e depois `-0,20` pp. A razão (`5,20/4,50
    - 1 = 15,6%`) seria um número sem leitura econômica aqui.
    """
    ipca_12m = pd.Series([4.50, 5.20, 5.00])
    saida = diferenca_em_pp(ipca_12m)
    assert pd.isna(saida.iloc[0])
    assert saida.iloc[1] == pytest.approx(0.70)
    assert saida.iloc[2] == pytest.approx(-0.20)


def test_media_movel_de_20_exige_janela_cheia() -> None:
    """19 trimestres → `NaN`; o 20º é a média dos 20. `min_periods` é a janela, não 1."""
    serie = pd.Series([float(i) for i in range(1, 21)])
    saida = media_movel(serie)
    assert saida.iloc[: N_TRIMESTRES_TENDENCIA - 1].isna().all()
    assert saida.iloc[N_TRIMESTRES_TENDENCIA - 1] == pytest.approx(10.5)


def test_media_movel_anda_com_a_janela() -> None:
    """A média de T é dos 20 trimestres **terminando em T** — janela móvel, não acumulada."""
    serie = pd.Series([float(i) for i in range(1, 22)])
    saida = media_movel(serie)
    assert saida.iloc[20] == pytest.approx(11.5)


def test_hiato_com_menos_de_20_trimestres_e_nulo() -> None:
    """Hiato sem janela cheia é `None`, nunca uma média de 19 disfarçada (CA-007/CA-061)."""
    yoy = pd.Series([1.0] * 19)
    tendencia, gap = hiato_vs_tendencia(yoy)
    assert tendencia.isna().all()
    assert gap.isna().all()


def test_hiato_e_o_yoy_menos_a_media_movel_de_20() -> None:
    """Com 20 trimestres de a/a, o hiato é exatamente `yoy - média(yoy[T-19..T])`."""
    yoy = pd.Series([2.0] * 19 + [5.0])
    tendencia, gap = hiato_vs_tendencia(yoy)
    esperado_tendencia = (19 * 2.0 + 5.0) / 20
    assert tendencia.iloc[19] == pytest.approx(esperado_tendencia)
    assert gap.iloc[19] == pytest.approx(5.0 - esperado_tendencia)


def test_acumulacao_geometrica_nao_e_soma() -> None:
    """Negativo: 3 meses de 1% dão **3,0301%**, não 3%. Soma no lugar do produto quebra."""
    assert acumulacao_geometrica([1.0, 1.0, 1.0]) == pytest.approx(3.0301, abs=1e-9)
    assert acumulacao_geometrica([1.0, 1.0, 1.0]) != pytest.approx(3.0, abs=1e-6)


def test_acumulacao_geometrica_aceita_deflacao() -> None:
    """Taxa negativa é dado real (deflação, 2017): entra no produto sem tratamento especial."""
    assert acumulacao_geometrica([0.5, -0.2, 0.3]) == pytest.approx(
        (1.005 * 0.998 * 1.003 - 1) * 100, abs=1e-9
    )


def test_acumulacao_geometrica_com_nulo_levanta() -> None:
    """Nulo no meio do trimestre é **ausência**, e ausência não acumula como se fosse 0."""
    with pytest.raises(ValueError, match="incompleto"):
        acumulacao_geometrica([1.0, float("nan"), 1.0])


def test_acumulacao_geometrica_vazia_levanta() -> None:
    """Trimestre sem nenhuma observação não vale `0%`: vale `BLOQUEADO`."""
    with pytest.raises(ValueError, match="vazia"):
        acumulacao_geometrica([])


@pytest.mark.parametrize(
    ("delta", "esperado"),
    [
        (-1.50, "CORTE"),
        (-0.26, "CORTE"),
        (-0.25, "CORTE"),
        (-0.24, "NEUTRO"),
        (0.0, "NEUTRO"),
        (0.24, "NEUTRO"),
        (0.25, "ALTA"),
        (0.26, "ALTA"),
        (2.75, "ALTA"),
    ],
)
def test_ciclo_selic_nos_tres_estados(delta: float, esperado: str) -> None:
    """Os 3 estados e as duas bordas do limiar de 0,25 pp (**D-t**).

    `|Δ| == 0,25` é **movimento**, não parada, desde D-t (2026-10-11). A leitura literal da
    metodologia §2 (`< -0,25` / `> +0,25`) punha 7 trimestres com `|Δ| = 0,25` exato em `NEUTRO`,
    entre eles **2024Q2 e 2024Q3** — cortes reais de 25 bps do Copom (P1-2 do QA da Onda 2). 25 pb
    é o menor passo que o Copom dá: chamá-lo de pausa rotula como parada justamente o início e o
    fim dos ciclos. Só `|Δ| < 0,25` é `NEUTRO`.
    """
    assert ciclo_selic(delta) == esperado
    assert pytest.approx(0.25) == LIMIAR_SELIC_PP


@pytest.mark.parametrize("delta", [-0.25, 0.25])
def test_ciclo_selic_na_borda_exata_nao_e_neutro(delta: float) -> None:
    """Negativo de D-t: a desigualdade **não** pode voltar a ser estrita.

    Travado sozinho porque a regressão é de 1 caractere (`<=` → `<`) e nenhum número publicado
    gritaria: a distribuição mudaria de 36/16/31 para 29/30/24 em silêncio.
    """
    assert ciclo_selic(delta) != "NEUTRO"
    assert ciclo_selic(delta) == ("CORTE" if delta < 0 else "ALTA")


def test_ciclo_selic_sem_delta_e_none_e_nao_neutro() -> None:
    """Negativo: trimestre sem Δ não tem ciclo. `NEUTRO` ali inventaria uma pausa medida."""
    assert ciclo_selic(None) is None
    assert ciclo_selic(float("nan")) is None


def test_focus_do_inicio_do_trimestre_usa_a_coleta_do_fim_de_t_menos_1() -> None:
    """A expectativa de T é a última coleta até o fim de `T-1` (metodologia §2, V1b)."""
    h0 = pd.Series({"2005Q4": 4.4, "2006Q1": 4.5, "2006Q2": 4.6})
    saida = focus_do_inicio_do_trimestre(h0, None, ["2006Q1", "2006Q2"])
    assert saida["2006Q1"] == pytest.approx(4.4)
    assert saida["2006Q2"] == pytest.approx(4.5)


def test_focus_do_inicio_do_trimestre_troca_para_h1_no_primeiro_trimestre() -> None:
    """Negativo do erro de 1 ano: em `2006Q1` a coleta é de dez/2005, então o ano de T é `H1`.

    Sem a troca, `focus_pib_ano` de todo 1º trimestre traria a expectativa do **ano que acabou** —
    um erro silencioso de um ano em 1/4 das linhas.
    """
    h0 = pd.Series({"2005Q4": 3.0, "2006Q1": 3.8})
    h1 = pd.Series({"2005Q4": 3.5, "2006Q1": 4.2})
    saida = focus_do_inicio_do_trimestre(h0, h1, ["2006Q1", "2006Q2"])
    assert saida["2006Q1"] == pytest.approx(3.5), "1º trimestre usa H1 (o ano de T)"
    assert saida["2006Q2"] == pytest.approx(3.8), "2º trimestre usa H0 (mesmo ano)"


def test_focus_sem_coleta_anterior_sai_nulo() -> None:
    """Primeiro trimestre da grade de apoio não tem `T-1`: nulo, não a coleta de T."""
    h0 = pd.Series({"2006Q1": 4.5})
    saida = focus_do_inicio_do_trimestre(h0, None, ["2006Q1"])
    assert pd.isna(saida["2006Q1"])


def test_sensibilidade_da_tendencia_mede_a_alternativa_sem_adota_la() -> None:
    """O bloco de sensibilidade conta quantos trimestres `min_periods=8` recuperaria."""
    yoy = pd.Series({f"{2001 + i // 4}Q{i % 4 + 1}": 2.0 + i * 0.1 for i in range(30)})
    janela = list(yoy.index)[10:]
    bloco = sensibilidade_da_tendencia(yoy, janela)
    assert bloco["trimestres_com_gap_se_min_periods_8"] > bloco["trimestres_com_gap_adotado"]
    assert bloco["trimestres_recuperados"] > 0


# ═════════════════════════════════════════════════════════════════════════════
# B — grade, observação de fim de período e acumulação (calendário sintético)
# ═════════════════════════════════════════════════════════════════════════════


def calendario_sintetico(ano_inicio: int, ano_fim: int) -> Calendario:
    """Calendário **sintético**: só 1º de janeiro é feriado, em cada ano da cobertura.

    O `Calendario` exige pelo menos um feriado por ano coberto. Um só, numa data que é feriado de
    verdade, deixa a contagem de dias úteis previsível — é o que permite construir lacuna de
    exatamente 5 e de exatamente 6 dias úteis. Nenhum número de produção sai daqui.
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


def quadro_raw(linhas: Iterable[Mapping[str, object]]) -> pd.DataFrame:
    """`DataFrame` validado por `RawSeriesSchema` — o portão da entrada, igual à produção."""
    return RawSeriesSchema.validate(pd.DataFrame(list(linhas)), lazy=True)


def test_quarters_de_apoio_sao_os_20_anteriores_a_2006q1() -> None:
    """A grade de apoio é `2001Q1..2005Q4`, derivada do contrato — nunca digitada."""
    apoio = quarters_de_apoio()
    assert len(apoio) == N_TRIMESTRES_TENDENCIA
    assert apoio[0] == "2001Q1"
    assert apoio[-1] == "2005Q4"
    assert set(apoio).isdisjoint(quarters_da_janela())


def test_grade_estendida_e_apoio_mais_janela_em_ordem() -> None:
    """A grade do cálculo é apoio + janela, ordenada, sem repetir trimestre."""
    cal = calendario_sintetico(2001, 2030)
    grade = grade_estendida(cal, quarters=["2006Q1", "2006Q2"])
    rotulos = [t.quarter for t in grade]
    assert rotulos[:2] == ["2001Q1", "2001Q2"]
    assert rotulos[-2:] == ["2006Q1", "2006Q2"]
    assert len(rotulos) == len(set(rotulos)) == N_TRIMESTRES_TENDENCIA + 2


def test_grade_estendida_nao_pede_data_fora_da_cobertura_do_calendario() -> None:
    """O apoio para em `cobertura_inicio`: feriado fora da cobertura não se adivinha (D-f)."""
    cal = calendario_sintetico(2005, 2010)
    grade = grade_estendida(cal, quarters=["2006Q1"])
    assert [t.quarter for t in grade][0] == "2005Q1"


def test_observacao_de_fim_de_periodo_aceita_ffill_de_5_e_recusa_6() -> None:
    """A régua de F-014 reexpressa: `lacuna <= 5` usa o valor; `6` vira `NULL` registrado."""
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2006Q1"])
    alvo = trimestres[0].quarter_end
    for passos, esperado in ((LIMITE_FFILL_DIAS_UTEIS, 7.0), (LIMITE_FFILL_DIAS_UTEIS + 1, None)):
        obs = cal.dia_util_anterior(alvo, passos)
        quadro = quadro_raw(
            [linha_raw("B3_IBOV", date(2006, 1, 2), 1.0), linha_raw("B3_IBOV", obs, 7.0)]
        )
        saida = observacoes_de_fim_de_periodo(
            quadro,
            calendario=cal,
            trimestres=trimestres,
            inicio_por_serie={"B3_IBOV": pd.Timestamp("2006-01-02")},
        )
        linha = saida.iloc[0]
        if esperado is None:
            assert pd.isna(linha["value"]), f"lacuna de {passos} d.u. tem de virar NULL (CA-067)"
            assert linha["motivo_nulo"] == MOTIVO_SERIE_SEM_VALOR
        else:
            assert linha["value"] == pytest.approx(esperado)
            assert int(linha["lacuna_dias_uteis"]) == passos


def test_observacao_de_fim_de_periodo_respeita_o_painel_desbalanceado() -> None:
    """Nenhuma linha antes do início real da série (CA-063) — nem na grade de apoio."""
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2006Q1", "2006Q2", "2006Q3"])
    quadro = quadro_raw([linha_raw("B3_ICON", date(2006, 6, 30), 1000.0)])
    saida = observacoes_de_fim_de_periodo(
        quadro,
        calendario=cal,
        trimestres=trimestres,
        inicio_por_serie={"B3_ICON": pd.Timestamp("2006-06-30")},
    )
    assert sorted(saida["quarter"]) == ["2006Q2", "2006Q3"]


def test_observacao_de_fim_de_periodo_exige_inicio_declarado() -> None:
    """Negativo: "não sei quando a série começa" nunca pode virar "começa em 2006"."""
    cal = calendario_sintetico(2005, 2007)
    quadro = quadro_raw([linha_raw("B3_IBOV", date(2006, 3, 31), 1.0)])
    with pytest.raises(SerieInconsistente, match="data_inicio_observada"):
        observacoes_de_fim_de_periodo(
            quadro,
            calendario=cal,
            trimestres=grade_de_trimestres(cal, quarters=["2006Q1"]),
            inicio_por_serie={},
        )


def test_conferir_apoio_contra_alinhado_passa_quando_as_reguas_coincidem() -> None:
    """A conferência devolve o nº de células batidas — e `0` divergência é o caso normal."""
    apoio = pd.DataFrame(
        {
            "series_id": ["X", "X"],
            "quarter": ["2006Q1", "2006Q2"],
            "date_obs": [pd.Timestamp("2006-03-31"), pd.Timestamp("2006-06-30")],
            "value": [1.0, 2.0],
        }
    )
    assert conferir_apoio_contra_alinhado(apoio, apoio.copy()) == 2


def test_conferir_apoio_contra_alinhado_levanta_na_divergencia_de_valor() -> None:
    """Negativo: uma célula diferente para o build. Duas réguas nunca saem juntas."""
    apoio = pd.DataFrame(
        {
            "series_id": ["X"],
            "quarter": ["2006Q1"],
            "date_obs": [pd.Timestamp("2006-03-31")],
            "value": [1.0],
        }
    )
    outro = apoio.copy()
    outro["value"] = [1.0000001]
    with pytest.raises(ApoioDivergente, match="divergem"):
        conferir_apoio_contra_alinhado(apoio, outro)


def test_conferir_apoio_sem_celula_em_comum_levanta() -> None:
    """Sem interseção não há conferência — e sem conferência o apoio não é publicável."""
    apoio = pd.DataFrame(
        {
            "series_id": ["X"],
            "quarter": ["2006Q1"],
            "date_obs": [pd.Timestamp("2006-03-31")],
            "value": [1.0],
        }
    )
    outro = apoio.copy()
    outro["series_id"] = ["Y"]
    with pytest.raises(ApoioDivergente, match="nenhuma célula em comum"):
        conferir_apoio_contra_alinhado(apoio, outro)


def test_acumular_por_trimestre_mensal_exige_os_3_meses() -> None:
    """`ipca_tri` só existe com os 3 meses do trimestre; com 2, `NULL` + motivo."""
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2005Q4", "2006Q1"])
    completo = quadro_raw(
        [
            linha_raw("BCB_SGS_433", quando, 1.0)
            for quando in (date(2006, 1, 31), date(2006, 2, 28), date(2006, 3, 31))
        ]
    )
    saida = acumular_por_trimestre(
        completo, series_id="BCB_SGS_433", calendario=cal, trimestres=trimestres
    )
    assert saida[0].value == pytest.approx(3.0301, abs=1e-9)
    assert saida[0].n_obs == saida[0].n_esperado == 3
    assert saida[0].date_obs_max == date(2006, 3, 31)

    incompleto = quadro_raw(
        [linha_raw("BCB_SGS_433", quando, 1.0) for quando in (date(2006, 1, 31), date(2006, 3, 31))]
    )
    parcial = acumular_por_trimestre(
        incompleto, series_id="BCB_SGS_433", calendario=cal, trimestres=trimestres
    )
    assert parcial[0].value is None
    assert parcial[0].motivo_nulo == MOTIVO_TRIMESTRE_INCOMPLETO
    assert (parcial[0].n_obs, parcial[0].n_esperado) == (2, 3)


def test_media_por_trimestre_e_a_media_dos_3_meses_e_exige_os_3() -> None:
    """**D-s:** o nivel trimestral do IBC-Br e a media aritmetica dos 3 meses do trimestre.

    Numeros cravados a mao: 100 / 110 / 120 -> media **110**, que e o mes do meio e **nao** o
    ultimo (120). E a diferenca que o P1-1 do QA da Onda 2 mediu em 4,2646 pp no `ibcbr_yoy`
    real. Com 2 meses, `NULL` + `MOTIVO_TRIMESTRE_INCOMPLETO` — nunca a media de 2 disfarcada.
    """
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2005Q4", "2006Q1"])
    completo = quadro_raw(
        [
            linha_raw("BCB_SGS_24364", quando, valor)
            for quando, valor in (
                (date(2006, 1, 31), 100.0),
                (date(2006, 2, 28), 110.0),
                (date(2006, 3, 31), 120.0),
            )
        ]
    )
    saida = media_por_trimestre(completo, series_id="BCB_SGS_24364", trimestres=trimestres)
    assert saida[0].quarter == "2006Q1"
    assert saida[0].value == pytest.approx(110.0)
    assert saida[0].value != pytest.approx(120.0), "fim de periodo nao e media do trimestre"
    assert (saida[0].n_obs, saida[0].n_esperado) == (3, 3)
    # `obs = media_3m`: a procedencia registra a ULTIMA das 3 observacoes.
    assert saida[0].date_obs_max == date(2006, 3, 31)

    incompleto = quadro_raw(
        [
            linha_raw("BCB_SGS_24364", quando, 100.0)
            for quando in (date(2006, 1, 31), date(2006, 2, 28))
        ]
    )
    parcial = media_por_trimestre(incompleto, series_id="BCB_SGS_24364", trimestres=trimestres)
    assert parcial[0].value is None
    assert parcial[0].motivo_nulo == MOTIVO_TRIMESTRE_INCOMPLETO
    assert (parcial[0].n_obs, parcial[0].n_esperado) == (2, 3)


def test_media_por_trimestre_e_aritmetica_nao_geometrica() -> None:
    """Negativo de D-s: indice de **nivel** media aritmeticamente; so fluxo encadeia.

    Com 100 / 110 / 120 a media aritmetica e 110,0 e a geometrica (media dos logs) e ~109,696.
    Trocar uma pela outra nao falharia nenhum check de schema — por isso o teste existe.
    """
    cal = calendario_sintegro = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2005Q4", "2006Q1"])
    quadro = quadro_raw(
        [
            linha_raw("BCB_SGS_24364", quando, valor)
            for quando, valor in (
                (date(2006, 1, 31), 100.0),
                (date(2006, 2, 28), 110.0),
                (date(2006, 3, 31), 120.0),
            )
        ]
    )
    obtido = media_por_trimestre(quadro, series_id="BCB_SGS_24364", trimestres=trimestres)[0].value
    geometrica = float(np.exp(np.mean(np.log([100.0, 110.0, 120.0]))))
    assert obtido == pytest.approx(110.0)
    assert geometrica == pytest.approx(109.69613, abs=1e-5)
    assert obtido != pytest.approx(geometrica, abs=1e-6)
    assert calendario_sintegro is cal


def test_media_por_trimestre_recusa_serie_de_grade_bancaria() -> None:
    """A media do trimestre esta definida para grade civil; serie diaria e erro de programacao."""
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2005Q4", "2006Q1"])
    diaria = quadro_raw([linha_raw("BCB_SGS_12", date(2006, 3, 31), 0.04)])
    with pytest.raises(SerieInconsistente, match="grade civil"):
        media_por_trimestre(diaria, series_id="BCB_SGS_12", trimestres=trimestres)


def test_acumular_por_trimestre_diario_exige_todos_os_dias_uteis() -> None:
    """`cdi_tri` com um dia útil faltando é `NULL`, não uma taxa menor em silêncio."""
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2005Q4", "2006Q1"])
    dias = cal.dias_uteis(
        cal.proximo_dia_util(trimestres[0].quarter_end), trimestres[1].quarter_end
    )
    completo = quadro_raw([linha_raw("BCB_SGS_12", quando, 0.05) for quando in dias])
    saida = acumular_por_trimestre(
        completo, series_id="BCB_SGS_12", calendario=cal, trimestres=trimestres
    )
    assert saida[0].value == pytest.approx((1.0005 ** len(dias) - 1) * 100, abs=1e-9)
    assert saida[0].n_obs == saida[0].n_esperado == len(dias)

    com_buraco = quadro_raw([linha_raw("BCB_SGS_12", q, 0.05) for q in dias[:-1]])
    parcial = acumular_por_trimestre(
        com_buraco, series_id="BCB_SGS_12", calendario=cal, trimestres=trimestres
    )
    assert parcial[0].value is None
    assert parcial[0].motivo_nulo == MOTIVO_TRIMESTRE_INCOMPLETO


def test_acumular_por_trimestre_sem_serie_devolve_motivo() -> None:
    """Série ausente devolve uma linha por trimestre com motivo — não lista vazia."""
    cal = calendario_sintetico(2005, 2007)
    trimestres = grade_de_trimestres(cal, quarters=["2005Q4", "2006Q1"])
    vazio = quadro_raw([linha_raw("BCB_SGS_433", date(2006, 1, 31), 1.0)])
    saida = acumular_por_trimestre(
        vazio, series_id="BCB_SGS_12", calendario=cal, trimestres=trimestres
    )
    assert [a.motivo_nulo for a in saida] == [MOTIVO_SERIE_SEM_VALOR]


# ═════════════════════════════════════════════════════════════════════════════
# C — build de ponta a ponta em tmp_path, sobre raw_series SINTÉTICO
# ═════════════════════════════════════════════════════════════════════════════

#: As séries sintéticas, com a forma da real: o que cada uma é e até quando existe.
#: `fim` `None` = até a ponta diária; as datas copiam o real (PIB até 2026Q2, IBC-Br até jul/2026),
#: que é o que faz CA-060 ser testável sem `data/`.
FIM_SINTETICO: Mapping[str, date] = {
    "SIDRA_1620_V583_90707": date(2026, 6, 30),
    "SIDRA_5932_V6564_90707": date(2026, 6, 30),
    "BCB_SGS_24364": date(2026, 7, 31),
}

INICIO_SINTETICO = date(2001, 1, 1)
PONTA_SINTETICA = date(2026, 10, 9)


def _series_sinteticas() -> tuple[str, ...]:
    """Tudo que o build (meu + o de F-014) precisa: o meu consumo + o pacote mínimo de F-014."""
    from apps.pipeline.canonical.alinhamento import SERIES_EXIGIDAS as EXIGIDAS_F014

    return tuple(
        dict.fromkeys(
            (
                *series_de_nivel(),
                *ACUMULADAS.values(),
                *SERIES_DA_CURVA,
                *EXIGIDAS_F014,
            )
        )
    )


def _valor_sintetico(series_id: str, indice: int) -> float:
    """Valor determinístico e plausível por série — nenhum número vem de fonte real.

    As formas importam para os checks do schema (`selic_meta_fim` em [0, 60], `usdbrl_fim > 0`) e
    para o `ciclo_selic` ter os 3 estados: a meta Selic sobe, para e cai ao longo da amostra.
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
        return 2.0 + 1.5 * float(np.sin(indice / 600.0)) + 1.6
    return 100.0 * (1.0 + indice / 1000.0)


def _datas_sinteticas(series_id: str, cal: Calendario) -> tuple[date, ...]:
    """As datas da série sintética, na grade que o catálogo declara (D-a para M/Q)."""
    fim = FIM_SINTETICO.get(series_id, PONTA_SINTETICA)
    freq = str(CATALOGO[series_id].freq)
    if freq == "D":
        if series_id == "BCB_SGS_432":  # calendário corrido (D-c/§2.2)
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


def focus_sintetico(cal: Calendario) -> pd.DataFrame:
    """As 5 séries do Focus, **sintéticas**, no contrato de `ProcessedSeriesSchema`."""
    dias = cal.dias_uteis(
        cal.ajustar_para_frente(INICIO_SINTETICO), cal.ajustar_para_tras(date(2026, 10, 2))
    )
    linhas: list[dict[str, object]] = []
    for series_id in SERIES_DO_FOCUS:
        entrada = CATALOGO[CATALOGO_DO_FOCUS[series_id]]
        for indice, quando in enumerate(dias):
            linhas.append(
                {
                    "series_id": series_id,
                    "date": pd.Timestamp(quando),
                    "value": 4.0 + 0.5 * float(np.sin(indice / 250.0)),
                    "source": str(entrada.fonte),
                    "freq": "D",
                    "vintage": COLETADO_EM.normalize(),
                    "unit": str(entrada.unit),
                    "collected_at": COLETADO_EM,
                }
            )
    return RawSeriesSchema.validate(pd.DataFrame(linhas), lazy=True)


@dataclass(frozen=True)
class ArvoreSintetica:
    """Uma `data/` sintética completa em `tmp_path`, pronta para `construir`."""

    raiz: Path
    calendario: Calendario
    raw: pd.DataFrame


def montar_arvore(tmp_path: Path, *, com_focus: bool) -> ArvoreSintetica:
    """Escreve `raw_series`, `series_catalog`, o alinhado de F-014 e (opcional) o Focus."""
    cal = calendario_sintetico(2001, 2030)
    raw = raw_series_sintetico(cal)
    garantir_diretorio(caminho_camada(Camada.CANONICAL, raiz=tmp_path))
    raw.to_parquet(caminho_canonical(NOME_RAW_SERIES, raiz=tmp_path), index=False)
    materializar_catalogo(load_catalog(), raw).to_parquet(
        caminho_canonical(NOME_CATALOGO, raiz=tmp_path), index=False
    )
    if com_focus:
        pasta = caminho_camada(Camada.PROCESSED, raiz=tmp_path) / "focus"
        garantir_diretorio(pasta)
        focus_sintetico(cal).to_parquet(pasta / "FOCUS_SINTETICO.parquet", index=False)
    construir_alinhado(raiz=tmp_path, calendario=cal)
    return ArvoreSintetica(raiz=tmp_path, calendario=cal, raw=raw)


@pytest.fixture(scope="module")
def arvore_com_focus(tmp_path_factory: pytest.TempPathFactory) -> ArvoreSintetica:
    """Árvore sintética **com** Focus — o caminho completo das 37 colunas rastreáveis."""
    return montar_arvore(tmp_path_factory.mktemp("macro_focus"), com_focus=True)


@pytest.fixture(scope="module")
def build_sintetico(arvore_com_focus: ArvoreSintetica) -> object:
    """O build de ponta a ponta sobre a árvore sintética, uma vez por módulo."""
    return construir(raiz=arvore_com_focus.raiz, calendario=arvore_com_focus.calendario)


def test_build_sintetico_tem_exatamente_83_linhas_de_2006q1_a_2026q3(
    build_sintetico: object,
) -> None:
    """CA-059: 83 linhas, `2006Q1..2026Q3`, sem trimestre repetido nem faltando."""
    macro = build_sintetico.macro  # type: ignore[attr-defined]
    assert len(macro) == 83
    assert list(macro["quarter"]) == list(quarters_da_janela())
    assert not macro["quarter"].duplicated().any()


def test_build_sintetico_marca_is_estimated_so_no_trimestre_corrente(
    build_sintetico: object,
) -> None:
    """CA-060: `is_estimated=True` só em `2026Q3`, e o PIB de lá é **nulo**, não estimado."""
    macro = build_sintetico.macro.set_index("quarter")  # type: ignore[attr-defined]
    assert bool(macro.loc["2026Q3", "is_estimated"])
    assert not macro.drop(index="2026Q3")["is_estimated"].any()
    assert pd.isna(macro.loc["2026Q3", "pib_yoy"])
    assert pd.isna(macro.loc["2026Q3", "ibcbr_yoy"])


def test_build_sintetico_e_a_materializacao_revised(build_sintetico: object) -> None:
    """`lag_adjusted=False` nas 83 linhas: o `asof` é F-018, e a tabela não mistura as duas."""
    macro = build_sintetico.macro  # type: ignore[attr-defined]
    assert not macro["lag_adjusted"].any()
    assert bool(build_sintetico.provenance["lag_adjusted"].eq(False).all())  # type: ignore[attr-defined]


def test_build_sintetico_grava_os_tres_artefatos(
    build_sintetico: object, arvore_com_focus: ArvoreSintetica
) -> None:
    """Os três arquivos saem em `data/canonical/` da raiz pedida — e em nenhum outro lugar."""
    for nome in (NOME_MACRO, NOME_PROVENANCE, NOME_RELATORIO):
        assert caminho_canonical(nome, raiz=arvore_com_focus.raiz).is_file()
    assert build_sintetico.caminho_macro.name == NOME_MACRO  # type: ignore[attr-defined]


def test_build_sintetico_e_idempotente_por_hash(arvore_com_focus: ArvoreSintetica) -> None:
    """RF-048/CA-121: duas rodadas sobre a mesma entrada dão Parquet byte-idêntico."""
    hashes = []
    for _ in range(2):
        construir(raiz=arvore_com_focus.raiz, calendario=arvore_com_focus.calendario)
        hashes.append(
            tuple(
                sha256_de(caminho_canonical(nome, raiz=arvore_com_focus.raiz).read_bytes())
                for nome in (NOME_MACRO, NOME_PROVENANCE, NOME_RELATORIO)
            )
        )
    assert hashes[0] == hashes[1]


def test_build_sintetico_sem_focus_deixa_as_7_colunas_nulas_e_declaradas(
    tmp_path: Path,
) -> None:
    """Focus ausente → 7 colunas nulas **com motivo no relatório**, nunca estimadas."""
    arvore = montar_arvore(tmp_path, com_focus=False)
    resultado = construir(raiz=arvore.raiz, calendario=arvore.calendario)
    dependentes = (
        "focus_ipca_12m",
        "focus_pib_ano",
        "focus_selic_fim",
        "juro_real_exante",
        "surpresa_ipca",
        "surpresa_pib",
        "surpresa_selic",
    )
    for coluna in dependentes:
        assert resultado.macro[coluna].isna().all(), coluna
        assert resultado.relatorio["nulos_por_coluna"][coluna]["motivo"]
    assert resultado.relatorio["focus"]["consumido"] is False
    assert "nao existe ou esta vazia" in resultado.relatorio["focus"]["motivo"]


def test_build_sintetico_ciclo_selic_tem_os_tres_estados(build_sintetico: object) -> None:
    """A amostra sintética sobe, para e corta a Selic: os 3 estados aparecem no relatório."""
    distribuicao = build_sintetico.relatorio["ciclo_selic"]["distribuicao"]  # type: ignore[attr-defined]
    assert set(distribuicao) == {"ALTA", "CORTE", "NEUTRO"}
    assert sum(distribuicao.values()) == 83


def test_medias_no_trimestre_cobre_exatamente_as_series_de_medias(
    arvore_com_focus: ArvoreSintetica,
) -> None:
    """**D-s:** `MEDIAS` é o contrato legível, e `medias_no_trimestre` não inventa série nenhuma."""
    cal = arvore_com_focus.calendario
    trimestres = grade_estendida(cal, quarters=quarters_da_janela())
    medias = medias_no_trimestre(arvore_com_focus.raw, trimestres=trimestres)
    assert set(medias) == set(MEDIAS.values()) == {"BCB_SGS_24364"}
    assert set(MEDIAS) == {"ibcbr_yoy", "ibcbr_yoy_trend", "ibcbr_gap"}
    for por_quarter in medias.values():
        assert all(a.n_esperado == 3 for a in por_quarter.values())


def test_build_sintetico_procedencia_de_ibcbr_aponta_o_ultimo_mes_da_media(
    build_sintetico: object,
) -> None:
    """`obs = media_3m`: 1 linha por célula, `date_obs` = a **última** das 3 observações (D-s).

    A escolha é a mesma de `ACUMULADAS` e é o que mantém `date_obs <= quarter_end` um limite
    **superior** verificável no Parquet — e, na `asof` de F-018, `date_obs + lag_dias`.
    """
    diag = build_sintetico.diagnostico  # type: ignore[attr-defined]
    fatia = diag.loc[diag["column"].isin(sorted(MEDIAS))]
    assert not fatia.empty
    assert (fatia["series_id"] == "BCB_SGS_24364").all()
    com_data = fatia.loc[fatia["date_obs_max"].notna()]
    assert len(com_data) > 150
    # O último mês do trimestre: mês 3, 6, 9 ou 12 — nunca o 1º mês de T nem um mês de T+1.
    meses = pd.to_datetime(com_data["date_obs_max"]).dt.month
    assert set(meses.unique()) <= {3, 6, 9, 12}
    assert (pd.to_datetime(com_data["date_obs_max"]) <= com_data["fim_civil"]).all()


def test_build_para_se_o_alinhado_nao_tem_serie_exigida(tmp_path: Path) -> None:
    """**D-v (P1-3 do QA da Onda 2):** `alinhado_trimestral` sem série exigida **para** o build.

    Era o achado: `exigir_series` só rodava contra `raw_series`, então um `alinhado_trimestral`
    sem `BCB_SGS_13522` fazia o build **concluir em silêncio** — a régua reexpressa em
    `observacoes_de_fim_de_periodo` cobria a ausência, `ipca_12m` saía com 83 valores não nulos e
    só o contador de células conferidas caía (1.328 → 1.245), que nenhum teste afirmava. A feature
    afirma que "todo nível é a célula de F-014": a série exigida tem de estar **nos dois**.
    """
    arvore = montar_arvore(tmp_path, com_focus=True)
    alvo = caminho_canonical("alinhado_trimestral.parquet", raiz=arvore.raiz)
    alinhado = pd.read_parquet(alvo)
    assert "BCB_SGS_13522" in set(alinhado["series_id"])
    alinhado.loc[alinhado["series_id"] != "BCB_SGS_13522"].to_parquet(alvo, index=False)

    with pytest.raises(FonteIndisponivel, match="BLOQUEADO — FONTE INDISPONÍVEL"):
        construir(raiz=arvore.raiz, calendario=arvore.calendario)


# ═════════════════════════════════════════════════════════════════════════════
# D — acervo real: diff numérico, reconstrução independente, anti-look-ahead
# ═════════════════════════════════════════════════════════════════════════════


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
    """O acervo real desta máquina está completo para rodar a seção D?"""
    return (
        not ignorar_data_real()
        and caminho_canonical(NOME_MACRO).is_file()
        and caminho_canonical("alinhado_trimestral.parquet").is_file()
        and caminho_canonical(NOME_RAW_SERIES).is_file()
    )


MOTIVO_SEM_ACERVO = (
    f"acervo data/canonical ausente (ou {VAR_IGNORAR_DATA} ligada): rode "
    f"`uv run python -m apps.pipeline.canonical.macro_quarterly --offline`"
)

acervo = pytest.mark.skipif(not canonical_disponivel(), reason=MOTIVO_SEM_ACERVO)


@pytest.fixture(scope="module")
def macro_real() -> pd.DataFrame:
    """`macro_quarterly.parquet` do acervo, validado pelo schema."""
    return MacroQuarterlySchema.validate(pd.read_parquet(caminho_canonical(NOME_MACRO)), lazy=True)


@pytest.fixture(scope="module")
def alinhado_real() -> pd.DataFrame:
    """`alinhado_trimestral.parquet` do acervo — a régua de F-014."""
    return pd.read_parquet(caminho_canonical("alinhado_trimestral.parquet"))


@pytest.fixture(scope="module")
def provenance_real() -> pd.DataFrame:
    """`macro_quarterly_provenance.parquet` do acervo, validado pelo schema."""
    return MacroQuarterlyProvenanceSchema.validate(
        pd.read_parquet(caminho_canonical(NOME_PROVENANCE)), lazy=True
    )


def _nivel_do_alinhado(alinhado: pd.DataFrame, series_id: str) -> pd.Series:
    """A coluna de nível de uma série, indexada por `quarter` — direto do artefato de F-014."""
    fatia = alinhado.loc[alinhado["series_id"] == series_id]
    return fatia.set_index("quarter")["value"].astype("float64")


def _media_do_trimestre(raw: pd.DataFrame, series_id: str) -> pd.Series:
    """A média dos meses do trimestre, recalculada **aqui** de `raw_series` (**D-s**).

    Conta independente e deliberadamente ingênua (`groupby` do período trimestral da própria
    `date`, sem a grade de F-014 e sem importar `media_por_trimestre`): é o que faz o diff de
    classe C do nível de `ibcbr_*` ser conferência e não tautologia. Trimestre com menos de 3
    meses sai `NaN`, igual à régua publicada.
    """
    fatia = raw.loc[(raw["series_id"] == series_id) & raw["value"].notna()].copy()
    fatia["quarter"] = pd.PeriodIndex(pd.to_datetime(fatia["date"]), freq="Q").astype(str)
    por_quarter = fatia.groupby("quarter")["value"]
    media = por_quarter.mean().astype("float64")
    return media.where(por_quarter.size() == 3)


#: Coluna de nível → série de origem. Repetido **de propósito** (não importado de `ORIGENS`): é o
#: que faz o diff numérico ser uma conferência independente e não uma tautologia.
NIVEIS_ESPERADOS: Mapping[str, str] = {
    "pib_qoq_sa": "SIDRA_5932_V6564_90707",
    "ipca_12m": "BCB_SGS_13522",
    "selic_meta_fim": "BCB_SGS_432",
    "usdbrl_fim": "BCB_SGS_1",
    "ust10_fim": "YAHOO_TNX",
    "vix_fim": "YAHOO_VIX",
}


@acervo
@pytest.mark.parametrize("coluna", sorted(NIVEIS_ESPERADOS))
def test_acervo_todo_nivel_e_identico_a_celula_do_alinhado(
    coluna: str, macro_real: pd.DataFrame, alinhado_real: pd.DataFrame
) -> None:
    """**Diff numérico de classe C:** nível é a célula de F-014, bit a bit, sem tolerância."""
    esperado = _nivel_do_alinhado(alinhado_real, NIVEIS_ESPERADOS[coluna]).reindex(
        list(macro_real["quarter"])
    )
    obtido = macro_real.set_index("quarter")[coluna]
    assert obtido.isna().equals(esperado.isna()), f"{coluna}: padrão de nulos diverge de F-014"
    presentes = obtido.notna()
    assert (obtido[presentes] == esperado[presentes]).all(), f"{coluna}: valor diverge de F-014"


@acervo
def test_acervo_derivadas_reproduzidas_por_conta_independente(
    macro_real: pd.DataFrame, alinhado_real: pd.DataFrame
) -> None:
    """Cada derivada publicada é reproduzida por uma conta escrita **aqui**, não importada.

    Só o trecho em que a conta independente consegue ver `T-k` (a partir de `2007Q1` para a/a e de
    `2006Q2` para t/t) — o resto depende da grade de apoio, que é conferida em
    `conferir_apoio_contra_alinhado` e em `test_acervo_apoio_bate_com_o_alinhado`.
    """
    macro = macro_real.set_index("quarter")
    quarters = list(macro.index)

    def razao(series_id: str, passos: int) -> pd.Series:
        nivel = _nivel_do_alinhado(alinhado_real, series_id).reindex(quarters)
        return (nivel / nivel.shift(passos) - 1.0) * 100.0

    # **D-s:** o nível trimestral do IBC-Br é a média dos 3 meses, não a célula de fim de período
    # de F-014. A média é recalculada aqui de `raw_series`, sem importar o módulo. Com a leitura
    # antiga (fim de período) esta mesma conta divergia do publicado em 4,2646 pp — é o número que
    # o P1-1 do QA da Onda 2 mediu, e este teste é o que trava o lado certo da decisão.
    raw_para_media = pd.read_parquet(caminho_canonical(NOME_RAW_SERIES))
    ibcbr_nivel = _media_do_trimestre(raw_para_media, "BCB_SGS_24364").reindex(quarters)
    ibcbr_yoy = (ibcbr_nivel / ibcbr_nivel.shift(4) - 1.0) * 100.0
    verificacoes = {
        "pib_yoy": razao("SIDRA_1620_V583_90707", 4),
        "ibcbr_yoy": ibcbr_yoy,
        "usdbrl_var_12m": razao("BCB_SGS_1", 4),
        "usdbrl_var_tri": razao("BCB_SGS_1", 1),
        "ipca_12m_delta": _nivel_do_alinhado(alinhado_real, "BCB_SGS_13522")
        .reindex(quarters)
        .diff(),
        "selic_meta_delta": _nivel_do_alinhado(alinhado_real, "BCB_SGS_432")
        .reindex(quarters)
        .diff(),
        "ibcbr_yoy_trend": ibcbr_yoy.rolling(
            N_TRIMESTRES_TENDENCIA, min_periods=N_TRIMESTRES_TENDENCIA
        ).mean(),
    }
    verificacoes["ibcbr_gap"] = ibcbr_yoy - verificacoes["ibcbr_yoy_trend"]

    # Piso de trimestres comparáveis por coluna: a conta independente só vê `T-k` **dentro** da
    # janela, então a tendência de 20 trimestres só nasce em 2011Q4 aqui (contra 2009Q4 no
    # publicado, que usa a grade de apoio). A diferença é exatamente o que o apoio acrescenta.
    piso = {"ibcbr_yoy_trend": 59, "ibcbr_gap": 59}
    for coluna, esperado in verificacoes.items():
        comparavel = esperado.dropna().index.intersection(macro.index[macro[coluna].notna()])
        minimo = piso.get(coluna, 60)
        assert len(comparavel) >= minimo, f"{coluna}: só {len(comparavel)} trimestres comparáveis"
        diferenca = (macro.loc[comparavel, coluna] - esperado[comparavel]).abs().max()
        assert diferenca < 1e-9, f"{coluna}: divergência máxima de {diferenca}"


@acervo
def test_acervo_apoio_bate_com_o_alinhado_celula_a_celula() -> None:
    """A grade de apoio reproduz F-014 nos 83 trimestres — é o que autoriza usá-la em `T-4`."""
    cal = Calendario.do_parquet()
    raw = pd.read_parquet(caminho_canonical(NOME_RAW_SERIES))
    alinhado = pd.read_parquet(caminho_canonical("alinhado_trimestral.parquet"))
    consumidas = (*series_de_nivel(), *ACUMULADAS.values())
    fatia = raw.loc[raw["series_id"].isin(consumidas)]
    inicio = {
        str(sid): pd.Timestamp(quando)
        for sid, quando in fatia.groupby("series_id")["date"].min().items()
    }
    apoio = observacoes_de_fim_de_periodo(
        fatia,
        calendario=cal,
        trimestres=grade_estendida(cal),
        inicio_por_serie=inicio,
    )
    assert conferir_apoio_contra_alinhado(apoio, alinhado) >= 83


@acervo
def test_acervo_anti_look_ahead_nenhuma_observacao_posterior_ao_fim_do_trimestre() -> None:
    """**Anti-look-ahead:** nenhuma célula de `T` usa observação com `date_obs` depois de `T`.

    A fronteira é o último dia **civil** de `T` e não o `quarter_end`: a grade `civil`/`corrido` de
    F-014 (D-a) mira o fim civil, que em 24 dos 83 trimestres é 1 a 3 dias depois do último dia
    útil — `2006Q3` fecha em 29/09 e o IPCA de setembro tem `date = 2006-09-30`. É data de
    **referência**, dentro de `T`; data de **divulgação** é a materialização `asof` (F-018), e esta
    tabela carrega `lag_adjusted=False` justamente por isso.
    """
    cal = Calendario.do_parquet()
    resultado = construir(calendario=cal)
    diagnostico = resultado.diagnostico
    com_data = diagnostico.loc[diagnostico["date_obs_max"].notna()]
    assert len(com_data) > 1000, "diagnóstico vazio: o teste não estaria provando nada"
    fora = com_data.loc[com_data["date_obs_max"] > com_data["fim_civil"]]
    assert fora.empty, (
        f"{len(fora)} célula(s) usam observação posterior ao fim do trimestre: "
        f"{fora.head(5).to_dict('records')}"
    )
    bloco = resultado.relatorio["anti_look_ahead"]
    assert bloco["celulas_com_date_obs_depois_do_fim_civil_de_T"] == 0


@acervo
def test_acervo_os_quatro_canarios_batem_com_a_fonte(macro_real: pd.DataFrame) -> None:
    """Os 4 valores-canário, conferidos contra a fonte original (`AGENTS.md §15.9`).

    `ipca_12m` de `2006Q1` é o acumulado 12m que o SGS 13522 publica em mar/2006 (**5,32**);
    `selic_meta_fim` de `4T2008` é a meta do Copom vigente em 31/12/2008 (**13,75**); `pib_yoy` de
    `1T2010` é `152,53 / 139,67 - 1` do índice de volume **sem** ajuste sazonal do SIDRA
    (**9,2074%** — o IBGE divulgou "cerca de 9,2%"); e `focus_ipca_12m` de `2026Q3` é a última
    coleta de `FOCUS_I12_IPCA_N` até 30/06/2026 (**4,19**), que é o que prova a régua de
    deslocamento de um trimestre.
    """
    macro = macro_real.set_index("quarter")
    assert float(macro.loc["2006Q1", "ipca_12m"]) == pytest.approx(5.32)
    assert float(macro.loc["2008Q4", "selic_meta_fim"]) == pytest.approx(13.75)
    assert float(macro.loc["2010Q1", "pib_yoy"]) == pytest.approx(9.207417, abs=1e-6)

    focus = caminho_camada(Camada.PROCESSED) / "focus" / "FOCUS_INFLACAO_12M.parquet"
    if focus.is_file():
        bruto = pd.read_parquet(focus)
        serie = bruto.loc[bruto["series_id"] == "FOCUS_I12_IPCA_N"].sort_values("date")
        ate = serie.loc[serie["date"] <= pd.Timestamp("2026-06-30"), "value"]
        assert float(macro.loc["2026Q3", "focus_ipca_12m"]) == pytest.approx(float(ate.iloc[-1]))


@acervo
def test_acervo_cdi_e_ipca_trimestrais_sao_geometricos(alinhado_real: pd.DataFrame) -> None:
    """`cdi_tri` e `ipca_tri` reproduzidos pelo produto dos fatores, calculado aqui.

    O CDI entra pela série diária (`BCB_SGS_12`) e o IPCA pelos 3 meses (`BCB_SGS_433`) — as duas
    de `raw_series`, porque acumulação não é leitura de fim de período e `alinhado_trimestral` não
    a tem. A soma simples **não** reproduz o valor (é o teste negativo de CA-070).
    """
    del alinhado_real
    cal = Calendario.do_parquet()
    raw = pd.read_parquet(caminho_canonical(NOME_RAW_SERIES))
    macro = pd.read_parquet(caminho_canonical(NOME_MACRO)).set_index("quarter")
    grade = {t.quarter: t for t in grade_de_trimestres(cal)}

    for coluna, series_id, alvo in (
        ("cdi_tri", "BCB_SGS_12", "quarter_end"),
        ("ipca_tri", "BCB_SGS_433", "fim_civil"),
    ):
        serie = raw.loc[raw["series_id"] == series_id].set_index("date")["value"].sort_index()
        for rotulo in ("2006Q1", "2008Q4", "2020Q2", "2026Q3"):
            periodo = pd.Period(rotulo, freq="Q")
            anterior = grade.get(str(periodo - 1))
            if anterior is None:
                inicio = pd.Timestamp((periodo - 1).end_time.date())
            else:
                inicio = pd.Timestamp(getattr(anterior, alvo))
            fim = pd.Timestamp(getattr(grade[rotulo], alvo))
            janela = serie.loc[(serie.index > inicio) & (serie.index <= fim)].dropna()
            produto = (np.prod(1.0 + janela.to_numpy() / 100.0) - 1.0) * 100.0
            assert float(macro.loc[rotulo, coluna]) == pytest.approx(produto, abs=1e-9), (
                f"{coluna}/{rotulo}: produto geométrico não reproduz o publicado"
            )
            if len(janela) > 3:
                soma = float(janela.sum())
                assert float(macro.loc[rotulo, coluna]) != pytest.approx(soma, abs=1e-6), (
                    f"{coluna}/{rotulo}: a soma simples reproduziu o valor — é geométrico?"
                )


@acervo
def test_acervo_vertice_extrapolado_acende_quando_falta_vertice(macro_real: pd.DataFrame) -> None:
    """CA-023/024: a flag é True exatamente nos trimestres em que algum vértice é nulo."""
    vertices = ["curva_real_1a", "curva_nominal_1a", "curva_real_5a", "curva_nominal_5a"]
    faltou = macro_real[vertices].isna().any(axis=1)
    assert macro_real["vertice_extrapolado"].equals(faltou.rename("vertice_extrapolado"))
    assert bool(faltou.any()), "sem nenhum vértice faltando o teste não prova nada"


@acervo
def test_acervo_nenhuma_coluna_tem_valor_interpolado_entre_nulos(
    macro_real: pd.DataFrame,
) -> None:
    """CA-061: nulo nunca é "fechado". Uma coluna com valor **entre** dois nulos é suspeita.

    O padrão legítimo é bloco: nulo no começo (falta `T-k` ou a janela da média móvel) ou no fim
    (trimestre corrente sem divulgação). Valor isolado no meio de nulos seria interpolação.
    """
    for coluna in COLUNAS_RASTREAVEIS:
        if coluna == "vertice_extrapolado":
            continue
        presente = macro_real[coluna].notna().to_numpy()
        if not presente.any():
            continue
        if coluna in (
            "curva_real_1a",
            "inclinacao_real_5a_1a",
            "curva_nominal_1a",
            "inclinacao_nominal_5a_1a",
            "breakeven_5a",
            "curva_nominal_5a",
            "juro_real_exante",
        ):
            continue  # a curva tem buraco legítimo no meio: vértice sem suporte (F-016 §3.4)
        indices = np.flatnonzero(presente)
        assert bool(presente[indices[0] : indices[-1] + 1].all()), (
            f"{coluna}: valor isolado entre nulos — interpolação?"
        )


@acervo
def test_acervo_e_idempotente_por_hash() -> None:
    """Reconstruir sobre o acervo real reescreve os **mesmos bytes** (RF-048/CA-121)."""
    antes = tuple(
        sha256_de(caminho_canonical(nome).read_bytes())
        for nome in (NOME_MACRO, NOME_PROVENANCE, NOME_RELATORIO)
    )
    construir()
    depois = tuple(
        sha256_de(caminho_canonical(nome).read_bytes())
        for nome in (NOME_MACRO, NOME_PROVENANCE, NOME_RELATORIO)
    )
    assert antes == depois


@acervo
def test_acervo_versao_build_e_hash_de_arquivo_e_nao_do_processo(macro_real: pd.DataFrame) -> None:
    """`fonte_versao` é o `sha256` do conjunto de módulos — igual em todas as 83 linhas."""
    assert bool(macro_real["fonte_versao"].eq(macro_real["fonte_versao"].iloc[0]).all())
    assert macro_real["fonte_versao"].iloc[0] == versao_build()


def test_insumos_cobrem_toda_coluna_rastreavel() -> None:
    """Toda coluna rastreável tem insumo declarado, ou está declarada como sem fonte."""
    for coluna in COLUNAS_RASTREAVEIS:
        insumos = insumos_da_coluna(coluna)
        if ORIGENS[coluna].series_id is None:
            assert insumos == (), coluna
            assert ORIGENS[coluna].motivo_ausencia, f"{coluna}: sem fonte e sem motivo declarado"
        else:
            assert insumos, coluna


def test_series_de_nivel_exclui_curva_acumuladas_e_focus() -> None:
    """`series_de_nivel` é o que se lê de `raw_series` em fim de período — e só isso."""
    nivel = set(series_de_nivel())
    assert nivel.isdisjoint(SERIES_DA_CURVA)
    assert nivel.isdisjoint(ACUMULADAS.values())
    assert nivel.isdisjoint(CATALOGO_DO_FOCUS.values())
    assert "BCB_SGS_13522" in nivel


def test_carregar_focus_sem_pasta_devolve_motivo(tmp_path: Path) -> None:
    """Focus ausente não é erro: é `(None, motivo)` e colunas nulas declaradas."""
    quadro, motivo = carregar_focus(raiz=tmp_path)
    assert quadro is None
    assert "nao existe ou esta vazia" in motivo


def test_carregar_focus_com_serie_faltando_recusa_meia_coluna(tmp_path: Path) -> None:
    """Negativo: pasta com parte das séries → `None` + motivo, nunca meia coluna sem aviso."""
    pasta = caminho_camada(Camada.PROCESSED, raiz=tmp_path) / "focus"
    garantir_diretorio(pasta)
    parcial = focus_sintetico(calendario_sintetico(2001, 2030))
    parcial = parcial.loc[parcial["series_id"] == "FOCUS_I12_IPCA_N"]
    parcial.to_parquet(pasta / "parcial.parquet", index=False)
    quadro, motivo = carregar_focus(raiz=tmp_path)
    assert quadro is None
    assert "sem as series que esta feature consome" in motivo


def test_acumulado_e_trimestre_sao_imutaveis() -> None:
    """`Acumulado` e `Trimestre` são `frozen`: nenhum estágio reescreve o resultado do outro."""
    item = Acumulado("2006Q1", 1.0, 3, 3, None, date(2006, 3, 31))
    with pytest.raises((AttributeError, TypeError)):
        item.value = 2.0  # type: ignore[misc]
    tri = Trimestre("2006Q1", date(2006, 3, 31), date(2006, 3, 31))
    with pytest.raises((AttributeError, TypeError)):
        tri.quarter = "2006Q2"  # type: ignore[misc]


def test_o_modulo_de_producao_nao_le_o_relogio() -> None:
    """Guarda de idempotência: `macro_quarterly.py` não lê o relógio em lugar nenhum.

    É a condição de RF-048/CA-121 que nenhum teste de hash pega sozinho: `collected_at` e
    `vintage` vêm do dado (D-b) e `fonte_versao` é hash de arquivo. Uma leitura de relógio no
    módulo faria o Parquet mudar sem o dado mudar, e só se perceberia no dia seguinte.
    """
    fonte = Path(macro_quarterly_modulo.__file__ or "").read_text(encoding="utf-8")
    for proibido in (".now(", ".today(", "time.time("):
        assert proibido not in fonte, f"{proibido} em macro_quarterly.py quebra a idempotência"
    assert isinstance(COLETADO_EM, pd.Timestamp)


def test_sequencias_do_contrato_sao_tuplas() -> None:
    """`SERIES_DA_CURVA`/`SERIES_DO_FOCUS` são tuplas: ordem e imutabilidade fazem parte."""
    for sequencia in (SERIES_DA_CURVA, SERIES_DO_FOCUS):
        assert isinstance(sequencia, tuple)
        assert len(set(sequencia)) == len(sequencia)
    assert isinstance(quarters_de_apoio(), tuple)


def test_grade_estendida_recusa_janela_vazia() -> None:
    """Janela vazia é erro de chamada, não tabela de 0 linha."""
    cal = calendario_sintetico(2005, 2007)
    with pytest.raises(ValueError, match="janela vazia"):
        grade_estendida(cal, quarters=[])


def _sequencia_de_trimestres(cal: Calendario, quantos: int) -> Sequence[Trimestre]:
    """Atalho de leitura para os testes de acumulação."""
    return grade_de_trimestres(cal, quarters=list(quarters_da_janela())[:quantos])
