"""F-014 — alinhamento trimestral: grade, forward-fill, painel desbalanceado e build. **Classe C.**

Quatro seções, com fontes de verdade diferentes de propósito:

- **A — a grade** (`CA-065`), sobre o calendário **real** da ANBIMA reconstruído das páginas HTML
  versionadas em `tests/fixtures/anbima-feriados/` (2006, 2024, 2025, 2026). É o que faz os
  casos-armadilha — 30/09 em sábado, 31/12 em domingo, Sexta-feira Santa em 29/03 — serem
  conferidos contra **feriado publicado**, nunca contra regra reimplementada no teste.
- **B — forward-fill e lacuna** (`CA-066`, `CA-067`), sobre séries **sintéticas nomeadas** e um
  calendário sintético, porque só assim se constrói a lacuna de exatamente 5 e de exatamente 6
  dias úteis. Dado sintético só existe aqui (Anti-SPEC §10.1.2).
- **C — índice temporal e painel** (`CA-063`, `CA-068`): duplicata divergente, data fora de ordem,
  duas safras de `vintage`, série que começa no meio do trimestre, mês aberto ausente.
- **D — o build de ponta a ponta** em `tmp_path`, inclusive idempotência por `sha256`.
- **E — acervos reais**, parametrizado: `tests/fixtures/processed/` (recortes versionados, **nunca
  pula**) e `data/canonical/` (as 49 séries completas, por acréscimo). `LDC_IGNORAR_DATA=1`
  desliga o segundo — é o padrão de `tests/unit/test_processed_layer_conventions.py`.

O **diff numérico da classe C** está em `test_acervo_toda_celula_com_valor_e_identica_a_origem`
(seção E): cada valor alinhado é comparado, sem tolerância de float, ao valor de `raw_series` na
`date_obs` que a própria linha registra.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from apps.pipeline.canonical.alinhamento import (
    MODULOS_DO_ALINHAMENTO,
    NOME_ALINHADO,
    NOME_RELATORIO,
    DatasDuplicadasNaSerie,
    GradeIndefinida,
    InicioDeSerieIncoerente,
    Trimestre,
    alinhar_series,
    construir,
    dias_uteis_de_lacuna,
    fatiar_para_alinhamento,
    grade_da_serie,
    grade_de_trimestres,
    inicio_observado_por_serie,
    selecionar_vintage,
    series_de_calendario_corrido,
    validar_indice_temporal,
    versao_build,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    materializar_catalogo,
)
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import Camada, caminho_camada, caminho_canonical, sha256_de
from apps.pipeline.extract.calendario_anbima import Calendario, parse_feriados_do_ano
from packages.shared.schemas import (
    COLUNAS_ALINHADO,
    GRADE_BANCARIA,
    GRADE_CIVIL,
    GRADE_CORRIDO,
    LIMITE_FFILL_DIAS_UTEIS,
    MOTIVO_LACUNA_ACIMA_DO_LIMITE,
    MOTIVO_SEM_OBSERVACAO,
    AlinhadoTrimestralSchema,
    load_catalog,
    quarters_da_janela,
)

RAIZ_TESTES = Path(__file__).resolve().parents[1]
FIXTURES_FERIADOS = RAIZ_TESTES / "fixtures" / "anbima-feriados"
FIXTURES_PROCESSED = RAIZ_TESTES / "fixtures" / "processed"

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
"""Liga o modo "árvore limpa": só os acervos versionados entram, `data/` é ignorado."""

COLUNAS_RAW = ("series_id", "date", "value", "source", "freq", "vintage", "unit", "collected_at")

CATALOGO = {entrada.series_id: entrada for entrada in load_catalog()}
"""O catálogo declarado, indexado — toda série sintética herda dele `source`/`freq`/`unit`."""


# ─────────────────────────────────────────────────────────────────────────────
# Infra de fixture: calendário real das páginas versionadas e calendário sintético
# ─────────────────────────────────────────────────────────────────────────────


def calendario_real_de(*anos: int) -> Calendario:
    """Calendário da ANBIMA reconstruído das páginas HTML **reais** de `tests/fixtures/`.

    Só os anos cujas páginas estão versionadas (2006, 2024, 2025, 2026) — é o recorte que faz a
    seção A rodar no CI sem `data/` e sem rede, com feriado **publicado** em vez de inventado.
    """
    feriados = []
    for ano in anos:
        paginas = sorted(FIXTURES_FERIADOS.glob(f"{ano}__*.html"))
        assert paginas, f"fixture do ano {ano} ausente em {FIXTURES_FERIADOS}"
        feriados.extend(
            parse_feriados_do_ano(paginas[0].read_bytes(), ano=ano, origem=paginas[0].name)
        )
    return Calendario.de_feriados(feriados, ano_inicio=min(anos), ano_fim=max(anos))


def calendario_sintetico(
    ano_inicio: int, ano_fim: int, feriados: Mapping[date, str] | None = None
) -> Calendario:
    """Calendário **sintético** (sem feriado, salvo os passados) — nomeado como tal.

    Existe para construir lacunas de tamanho exato: com feriado real não se controla quantos dias
    úteis separam duas datas. Nenhum número de produção sai daqui.
    """
    return Calendario(
        feriados=dict(sorted((feriados or {}).items())),
        cobertura_inicio=date(ano_inicio, 1, 1),
        cobertura_fim=date(ano_fim, 12, 31),
    )


def serie_sintetica(
    series_id: str, pontos: Iterable[tuple[str, float | None]], *, vintage: str = "2026-10-10"
) -> pd.DataFrame:
    """Uma série **sintética** no contrato de `raw_series`, com metadado do catálogo real.

    `source`/`freq`/`unit` vêm da entrada do catálogo para que as guardas públicas de F-013
    (`validar_procedencia`, `validar_frequencia_nativa`) rodem sobre ela de verdade: fixture que
    burla a guarda não prova nada.
    """
    entrada = CATALOGO[series_id]
    quando = pd.Timestamp(vintage)
    return pd.DataFrame(
        {
            "series_id": series_id,
            "date": [pd.Timestamp(d) for d, _ in pontos],
            "value": [v for _, v in pontos],
            "source": entrada.fonte.value,
            "freq": entrada.freq.value,
            "vintage": quando,
            "unit": entrada.unit.value,
            "collected_at": quando,
        }
    ).loc[:, list(COLUNAS_RAW)]


def inicio_de(raw: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """`{series_id: min(date)}` — o início observado, como o catálogo materializado o mede."""
    return {str(k): pd.Timestamp(v) for k, v in raw.groupby("series_id")["date"].min().items()}


def alinhar(
    raw: pd.DataFrame, *, calendario: Calendario, quarters: Sequence[str], **extra: Any
) -> pd.DataFrame:
    """Atalho: alinha `raw` nos `quarters` pedidos, com o início medido no próprio dado."""
    return alinhar_series(
        raw,
        calendario=calendario,
        inicio_por_serie=extra.pop("inicio_por_serie", inicio_de(raw)),
        trimestres=grade_de_trimestres(calendario, quarters=quarters),
        fonte_versao=extra.pop("fonte_versao", "f" * 64),
        **extra,
    )


def celula(tabela: pd.DataFrame, series_id: str, quarter: str) -> pd.Series:
    """A única linha de `(series_id, quarter)` — levanta se houver zero ou duas."""
    recorte = tabela[(tabela["series_id"] == series_id) & (tabela["quarter"] == quarter)]
    assert len(recorte) == 1, f"{series_id} {quarter}: {len(recorte)} linha(s)"
    return recorte.iloc[0]


# ═════════════════════════════════════════════════════════════════════════════
# A — a grade dos 83 trimestres (CA-065)
# ═════════════════════════════════════════════════════════════════════════════


def test_a_janela_tem_83_trimestres_de_2006q1_a_2026q3() -> None:
    """A janela de 20 anos do e-mail do Alexandre, sem trimestre repetido nem faltando."""
    quarters = quarters_da_janela()
    assert len(quarters) == 83
    assert (quarters[0], quarters[-1]) == ("2006Q1", "2026Q3")
    assert list(quarters) == sorted(quarters)


def test_a_grade_cai_toda_em_dia_util_e_dentro_do_trimestre() -> None:
    """CA-065 nos 16 trimestres cobertos pela fixture: `quarter_end` é dia útil e é do trimestre."""
    calendario = calendario_real_de(2006)
    calendario_recente = calendario_real_de(2024, 2025, 2026)
    for cal, anos in ((calendario, (2006,)), (calendario_recente, (2024, 2025, 2026))):
        alvos = [f"{ano}Q{tri}" for ano in anos for tri in (1, 2, 3, 4)]
        for tri in grade_de_trimestres(cal, quarters=alvos):
            assert cal.e_dia_util(tri.quarter_end), tri
            assert str(pd.Timestamp(tri.quarter_end).to_period("Q")) == tri.quarter
            assert tri.quarter_end <= tri.fim_civil


@pytest.mark.parametrize(
    ("quarter", "esperado", "motivo"),
    [
        ("2006Q1", "2006-03-31", "31/03/2006 é sexta-feira útil"),
        ("2006Q2", "2006-06-30", "30/06/2006 é sexta-feira útil"),
        ("2006Q3", "2006-09-29", "30/09/2006 é sábado -> anda para a sexta"),
        ("2006Q4", "2006-12-29", "31/12 é domingo e 30/12 é sábado -> 29/12"),
    ],
)
def test_armadilhas_de_fim_de_trimestre_em_2006(quarter: str, esperado: str, motivo: str) -> None:
    """Os dois trimestres de 2006 em que o fim civil **não** é dia útil (CA-065)."""
    (tri,) = grade_de_trimestres(calendario_real_de(2006), quarters=[quarter])
    assert tri.quarter_end == date.fromisoformat(esperado), motivo


@pytest.mark.parametrize(
    ("quarter", "esperado", "motivo"),
    [
        ("2024Q1", "2024-03-28", "29/03/2024 é Sexta-feira Santa, feriado publicado pela ANBIMA"),
        ("2024Q2", "2024-06-28", "30/06/2024 é domingo"),
        ("2025Q4", "2025-12-31", "31/12 É dia útil na lista da ANBIMA (a B3 é que não negocia)"),
        ("2026Q1", "2026-03-31", "31/03/2026 é terça-feira útil"),
    ],
)
def test_armadilhas_de_fim_de_trimestre_em_2024_2026(
    quarter: str, esperado: str, motivo: str
) -> None:
    """Carnaval e Sexta-feira Santa movem o fim de trimestre; 31/12 **não** move (D-h)."""
    (tri,) = grade_de_trimestres(calendario_real_de(2024, 2025, 2026), quarters=[quarter])
    assert tri.quarter_end == date.fromisoformat(esperado), motivo


def test_31_12_e_dia_util_bancario_e_e_por_isso_que_a_b3_precisa_de_ffill() -> None:
    """A afirmação central de D-h, conferida no calendário: 31/12/2025 é dia útil para a ANBIMA.

    Como a B3 não negocia nesse dia, a série da B3 tem de voltar 1 dia útil — e é por isso que
    `ffill_dias_uteis = 1` aparece em todo 4º trimestre (seção E).
    """
    cal = calendario_real_de(2024, 2025, 2026)
    assert cal.e_dia_util(date(2025, 12, 31))
    assert cal.nome_do_feriado(date(2025, 12, 31)) is None
    assert cal.dia_util_anterior(date(2025, 12, 31)) == date(2025, 12, 30)


@pytest.mark.parametrize(
    ("series_id", "freq", "esperada"),
    [
        ("B3_IBOV", "D", GRADE_BANCARIA),
        ("BCB_SGS_12", "D", GRADE_BANCARIA),
        ("BCB_SGS_432", "D", GRADE_CORRIDO),
        ("BCB_SGS_433", "M", GRADE_CIVIL),
        ("BCB_SGS_22109", "Q", GRADE_CIVIL),
    ],
)
def test_cada_serie_cai_na_regua_certa(series_id: str, freq: str, esperada: str) -> None:
    """A meta Selic é a única diária de calendário corrido do acervo (`DECISIONS_LOG §2.2`)."""
    assert grade_da_serie(series_id, freq) == esperada


def test_freq_desconhecida_nao_ganha_grade_por_default() -> None:
    """Grade inventada é um trimestre errado em silêncio — melhor levantar."""
    with pytest.raises(GradeIndefinida):
        grade_da_serie("BCB_SGS_12", "W")


def test_alvo_de_grade_desconhecida_levanta() -> None:
    """O `Trimestre` não devolve data para uma régua que o contrato não conhece."""
    tri = Trimestre(quarter="2006Q1", quarter_end=date(2006, 3, 31), fim_civil=date(2006, 3, 31))
    with pytest.raises(GradeIndefinida):
        tri.alvo("b3")


# ═════════════════════════════════════════════════════════════════════════════
# B — forward-fill e lacuna (CA-066, CA-067)
# ═════════════════════════════════════════════════════════════════════════════


def test_contagem_de_lacuna_e_semiaberta_no_inicio() -> None:
    """Observação **no** alvo dá 0; a véspera útil dá 1; a semana anterior dá 5."""
    cal = calendario_sintetico(2020, 2021)
    alvo = date(2020, 12, 31)  # quinta-feira, sem feriado no calendário sintético
    assert dias_uteis_de_lacuna(cal, alvo, alvo) == 0
    assert dias_uteis_de_lacuna(cal, date(2020, 12, 30), alvo) == 1
    assert dias_uteis_de_lacuna(cal, date(2020, 12, 24), alvo) == 5
    assert dias_uteis_de_lacuna(cal, date(2020, 12, 23), alvo) == 6


def test_fim_de_semana_nao_conta_como_dia_util_de_ffill() -> None:
    """Alvo em sábado com observação na sexta: nenhum dia útil foi pulado, então `ffill = 0`.

    A data real continua em `date_obs` — a informação não se perde, só não é contada como passo.
    """
    cal = calendario_sintetico(2006, 2006)
    assert dias_uteis_de_lacuna(cal, date(2006, 9, 29), date(2006, 9, 30)) == 0


def test_observacao_no_fechamento_tem_ffill_zero() -> None:
    """O caso normal: a série tem o último dia útil do trimestre."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-30", 100.0), ("2020-12-31", 119_017.24)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2020Q4"]), "B3_IBOV", "2020Q4")
    assert linha["ffill_dias_uteis"] == 0
    assert linha["value"] == 119_017.24
    assert pd.Timestamp(linha["date_obs"]) == pd.Timestamp("2020-12-31")


def test_ativo_sem_negociacao_no_fechamento_usa_a_vespera_e_registra_1_dia_util() -> None:
    """**CA-066 e D-h.** A B3 não negocia em 31/12: o valor é do dia 30 e `ffill = 1`."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-29", 118_000.0), ("2020-12-30", 119_017.24)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2020Q4"]), "B3_IBOV", "2020Q4")
    assert pd.Timestamp(linha["date_alvo"]) == pd.Timestamp("2020-12-31")
    assert pd.Timestamp(linha["date_obs"]) == pd.Timestamp("2020-12-30")
    assert linha["ffill_dias_uteis"] == 1
    assert linha["lacuna_dias_uteis"] == 1
    assert linha["value"] == 119_017.24
    assert pd.isna(linha["motivo_nulo"])


def test_feriado_no_fim_do_trimestre_move_o_alvo_e_nao_gasta_ffill() -> None:
    """Feriado em 31/12: o alvo **anda para trás** (30/12) e a série que o tem fica com ffill 0."""
    cal = calendario_sintetico(2020, 2020, {date(2020, 12, 31): "Feriado sintético"})
    (tri,) = grade_de_trimestres(cal, quarters=["2020Q4"])
    assert tri.quarter_end == date(2020, 12, 30)
    raw = serie_sintetica("B3_IBOV", [("2020-12-29", 1.0), ("2020-12-30", 2.0)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2020Q4"]), "B3_IBOV", "2020Q4")
    assert linha["ffill_dias_uteis"] == 0
    assert linha["value"] == 2.0


def test_lacuna_de_exatamente_5_dias_uteis_e_aceita() -> None:
    """A fronteira de ADR-006 §(b).8: 5 é o limite **inclusivo**."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-01", 1.0), ("2020-12-24", 99.0)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2020Q4"]), "B3_IBOV", "2020Q4")
    assert linha["ffill_dias_uteis"] == LIMITE_FFILL_DIAS_UTEIS == 5
    assert linha["value"] == 99.0


def test_lacuna_de_6_dias_uteis_vira_nulo_com_a_lacuna_registrada() -> None:
    """**CA-067 (negativo).** 1 dia útil além do limite: `NULL`, nunca interpolação nem `0`."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-01", 1.0), ("2020-12-23", 99.0)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2020Q4"]), "B3_IBOV", "2020Q4")
    assert pd.isna(linha["value"]), "lacuna acima do limite NÃO pode produzir valor"
    assert linha["value"] != 0
    assert pd.isna(linha["date_obs"])
    assert linha["ffill_dias_uteis"] == 0
    assert linha["lacuna_dias_uteis"] == 6
    assert pd.Timestamp(linha["date_ultima_obs"]) == pd.Timestamp("2020-12-23")
    assert linha["motivo_nulo"] == MOTIVO_LACUNA_ACIMA_DO_LIMITE


def test_valor_nulo_na_fonte_nao_conta_como_observacao() -> None:
    """Feriado de mercado chega como `value` nulo: o alinhamento volta ao último valor real."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-30", 50.0), ("2020-12-31", None)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2020Q4"]), "B3_IBOV", "2020Q4")
    assert linha["value"] == 50.0
    assert pd.Timestamp(linha["date_obs"]) == pd.Timestamp("2020-12-30")
    assert linha["ffill_dias_uteis"] == 1


def test_sem_observacao_nenhuma_no_alvo_usa_motivo_sem_observacao() -> None:
    """Primeiro trimestre da janela com a série começando depois dele, mas com início anterior."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)])
    tabela = alinhar(
        raw,
        calendario=cal,
        quarters=["2020Q3", "2020Q4"],
        inicio_por_serie={"B3_IBOV": pd.Timestamp("2020-01-02")},
    )
    vazia = celula(tabela, "B3_IBOV", "2020Q3")
    assert pd.isna(vazia["value"])
    assert vazia["motivo_nulo"] == MOTIVO_SEM_OBSERVACAO
    assert pd.isna(vazia["date_ultima_obs"])
    assert vazia["lacuna_dias_uteis"] == 0


def test_serie_de_calendario_corrido_alinha_no_ultimo_dia_civil() -> None:
    """SGS 432: o alvo é 30/09 (sábado), não 29/09 — e `quarter_end` segue sendo o dia útil."""
    cal = calendario_sintetico(2006, 2006)
    raw = serie_sintetica(
        "BCB_SGS_432",
        [("2006-09-28", 14.75), ("2006-09-29", 14.75), ("2006-09-30", 14.25)],
    )
    linha = celula(alinhar(raw, calendario=cal, quarters=["2006Q3"]), "BCB_SGS_432", "2006Q3")
    assert linha["grade"] == GRADE_CORRIDO
    assert pd.Timestamp(linha["date_alvo"]) == pd.Timestamp("2006-09-30")
    assert pd.Timestamp(linha["quarter_end"]) == pd.Timestamp("2006-09-29")
    assert linha["value"] == 14.25
    assert linha["ffill_dias_uteis"] == 0


def test_nada_e_interpolado_nem_reescalado() -> None:
    """Todo `value` alinhado é um valor que existe na entrada, idêntico (Anti-SPEC §10.1.1)."""
    cal = calendario_sintetico(2020, 2020)
    pontos = [("2020-10-01", 1.5), ("2020-11-30", 2.5), ("2020-12-31", 3.5)]
    raw = serie_sintetica("B3_IBOV", pontos)
    tabela = alinhar(raw, calendario=cal, quarters=["2020Q4"])
    assert set(tabela["value"].dropna()) <= {v for _, v in pontos}


# ═════════════════════════════════════════════════════════════════════════════
# C — índice temporal, vintage e painel desbalanceado (CA-063, CA-068)
# ═════════════════════════════════════════════════════════════════════════════


def test_data_duplicada_com_valor_divergente_falha_ruidosamente() -> None:
    """**CA-068 (negativo).** Escolher uma das duas em silêncio esconde revisão ou bug."""
    raw = pd.concat(
        [
            serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)]),
            serie_sintetica("B3_IBOV", [("2020-12-31", 2.0)]),
        ],
        ignore_index=True,
    )
    with pytest.raises(DatasDuplicadasNaSerie) as erro:
        validar_indice_temporal(raw)
    assert "2020-12-31" in str(erro.value)


def test_data_duplicada_identica_e_deduplicada_sem_falhar() -> None:
    """Dois extratores reexportando o mesmo ponto não é conflito — é repetição."""
    raw = pd.concat(
        [
            serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)]),
            serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)]),
        ],
        ignore_index=True,
    )
    assert len(validar_indice_temporal(raw)) == 1


def test_entrada_fora_de_ordem_produz_o_mesmo_resultado() -> None:
    """CA-068: o pipeline **ordena**; data fora de ordem não é motivo para falhar."""
    cal = calendario_sintetico(2020, 2020)
    pontos = [("2020-12-29", 1.0), ("2020-12-30", 2.0), ("2020-12-31", 3.0)]
    ordenado = alinhar(serie_sintetica("B3_IBOV", pontos), calendario=cal, quarters=["2020Q4"])
    invertido = alinhar(
        serie_sintetica("B3_IBOV", list(reversed(pontos))), calendario=cal, quarters=["2020Q4"]
    )
    pd.testing.assert_frame_equal(ordenado, invertido, check_exact=True)


def test_serie_com_duas_frequencias_falha() -> None:
    """Série que muda de frequência no meio não tem grade — e escolher uma é inventar."""
    raw = pd.concat(
        [
            serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)]),
            serie_sintetica("BCB_SGS_433", [("2020-12-31", 0.5)]).assign(series_id="B3_IBOV"),
        ],
        ignore_index=True,
    )
    with pytest.raises(SerieInconsistente):
        validar_indice_temporal(raw)


def test_duas_safras_de_vintage_usam_a_mais_recente() -> None:
    """A materialização desta tabela é `revised`: a safra mais nova ganha, sem duplicar a PK."""
    antiga = serie_sintetica("BCB_SGS_22109", [("2020-12-31", 100.0)], vintage="2026-10-01")
    nova = serie_sintetica("BCB_SGS_22109", [("2020-12-31", 101.5)], vintage="2026-10-10")
    selecionado = selecionar_vintage(pd.concat([antiga, nova], ignore_index=True))
    assert len(selecionado) == 1
    assert selecionado["value"].iloc[0] == 101.5

    cal = calendario_sintetico(2020, 2020)
    tabela = alinhar(
        pd.concat([antiga, nova], ignore_index=True), calendario=cal, quarters=["2020Q4"]
    )
    linha = celula(tabela, "BCB_SGS_22109", "2020Q4")
    assert linha["value"] == 101.5
    assert pd.Timestamp(linha["vintage"]) == pd.Timestamp("2026-10-10")


def test_serie_que_comeca_no_meio_do_trimestre_nao_tem_linha_anterior() -> None:
    """**CA-063.** O trimestre que *contém* o início existe; os anteriores **não existem**."""
    cal = calendario_sintetico(2010, 2011)
    raw = serie_sintetica("B3_IFIX", [("2010-12-30", 1000.0), ("2011-03-31", 1100.0)])
    tabela = alinhar(
        raw, calendario=cal, quarters=["2010Q1", "2010Q2", "2010Q3", "2010Q4", "2011Q1"]
    )
    assert sorted(tabela["quarter"]) == ["2010Q4", "2011Q1"]
    assert pd.Timestamp(tabela["data_inicio_serie"].iloc[0]) == pd.Timestamp("2010-12-30")
    linha = celula(tabela, "B3_IFIX", "2010Q4")
    assert linha["value"] == 1000.0
    assert linha["ffill_dias_uteis"] == 1  # 31/12/2010 é dia útil; o IFIX só tem o dia 30


def test_serie_sem_inicio_declarado_levanta_em_vez_de_assumir_2006() -> None:
    """ "Não sei quando a série começa" nunca pode virar "começa em 2006"."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)])
    with pytest.raises(InicioDeSerieIncoerente):
        alinhar_series(
            raw,
            calendario=cal,
            inicio_por_serie={},
            trimestres=grade_de_trimestres(cal, quarters=["2020Q4"]),
        )


def test_mensal_sem_o_mes_do_fim_do_trimestre_e_nulo_nao_herda_o_mes_anterior() -> None:
    """**O caso do mês aberto.** 3T sem setembro não vira "agosto": a célula é nula e declarada.

    Um mês atrás são ~21 dias úteis, muito além do limite de 5 — então a regra de ADR-006 §(b).8
    já responde certo, e o teste trava a resposta.
    """
    cal = calendario_sintetico(2026, 2026)
    raw = serie_sintetica("BCB_SGS_24363", [("2026-06-30", 100.0), ("2026-07-31", 101.0)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2026Q3"]), "BCB_SGS_24363", "2026Q3")
    assert pd.isna(linha["value"])
    assert linha["value"] != 101.0
    assert linha["motivo_nulo"] == MOTIVO_LACUNA_ACIMA_DO_LIMITE
    assert pd.Timestamp(linha["date_ultima_obs"]) == pd.Timestamp("2026-07-31")
    assert linha["lacuna_dias_uteis"] > LIMITE_FFILL_DIAS_UTEIS


def test_mensal_com_o_mes_fechado_alinha_no_fim_civil_com_ffill_zero() -> None:
    """O par positivo do teste acima: `date` de série mensal já é fim de período (D-a)."""
    cal = calendario_sintetico(2006, 2006)
    raw = serie_sintetica("BCB_SGS_433", [("2006-02-28", 0.41), ("2006-03-31", 0.43)])
    linha = celula(alinhar(raw, calendario=cal, quarters=["2006Q1"]), "BCB_SGS_433", "2006Q1")
    assert linha["grade"] == GRADE_CIVIL
    assert linha["value"] == 0.43
    assert linha["ffill_dias_uteis"] == 0


def test_trimestral_sem_o_trimestre_divulgado_e_nulo() -> None:
    """PIB do trimestre corrente ainda não existe (lag de 60 d): nulo, nunca o trimestre antes."""
    cal = calendario_sintetico(2026, 2026)
    raw = serie_sintetica("BCB_SGS_22109", [("2026-03-31", 100.0), ("2026-06-30", 101.0)])
    tabela = alinhar(raw, calendario=cal, quarters=["2026Q2", "2026Q3"])
    assert celula(tabela, "BCB_SGS_22109", "2026Q2")["value"] == 101.0
    nula = celula(tabela, "BCB_SGS_22109", "2026Q3")
    assert pd.isna(nula["value"])
    assert nula["motivo_nulo"] == MOTIVO_LACUNA_ACIMA_DO_LIMITE


def test_nenhuma_serie_na_janela_bloqueia_em_vez_de_entregar_tabela_vazia() -> None:
    """Tabela vazia a jusante é pior que falha: `BLOQUEADO — FONTE INDISPONÍVEL`."""
    cal = calendario_sintetico(2020, 2020)
    raw = serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)])
    with pytest.raises(FonteIndisponivel):
        alinhar_series(
            raw,
            calendario=cal,
            inicio_por_serie={"B3_IBOV": pd.Timestamp("2020-12-31")},
            trimestres=grade_de_trimestres(cal, quarters=["2020Q1"]),
        )


def test_serie_derivada_fica_fora_do_build_com_motivo_registrado() -> None:
    """`SP500_BRL`/`ACWI_BRL` (e a curva de F-016) são alinhadas pela feature dona delas."""
    raw = pd.concat(
        [
            serie_sintetica("B3_IBOV", [("2020-12-31", 1.0)]),
            serie_sintetica("SP500_BRL", [("2020-12-31", 2.0)]),
        ],
        ignore_index=True,
    )
    dentro, fora = fatiar_para_alinhamento(raw)
    assert set(dentro["series_id"]) == {"B3_IBOV"}
    assert [e["series_id"] for e in fora] == ["SP500_BRL"]
    assert "F-017" in fora[0]["motivo"]


# ═════════════════════════════════════════════════════════════════════════════
# D — o build de ponta a ponta em tmp_path
# ═════════════════════════════════════════════════════════════════════════════

QUARTERS_DO_BUILD_SINTETICO = ("2020Q3", "2020Q4", "2021Q1")


def acervo_sintetico_em_disco(raiz: Path) -> pd.DataFrame:
    """Monta `data/canonical/{raw_series,series_catalog}.parquet` **sintéticos** em `raiz`.

    Traz as 9 séries de `SERIES_EXIGIDAS` (senão o portão CA-076 barra, como deve) + a B3 sem o
    último dia útil de 2020, que é o caso D-h, + uma série derivada, que tem de sair.
    """
    diarias = [
        ("2020-09-29", 1.0),
        ("2020-09-30", 2.0),
        ("2020-12-30", 3.0),
        ("2020-12-31", 4.0),
        ("2021-03-30", 5.0),
        ("2021-03-31", 6.0),
    ]
    sem_o_fim_do_ano = [p for p in diarias if p[0] != "2020-12-31"]
    pedacos = [
        serie_sintetica("B3_IBOV", sem_o_fim_do_ano),
        serie_sintetica("ANBIMA_IMAB", diarias),
        serie_sintetica("ANBIMA_IMAGERAL", diarias),
        serie_sintetica("ANBIMA_IRFM", diarias),
        serie_sintetica("BCB_SGS_1", diarias),
        serie_sintetica("BCB_SGS_12", diarias),
        serie_sintetica(
            "BCB_SGS_432",
            [(d, 2.0) for d in pd.date_range("2020-09-01", "2021-03-31").strftime("%Y-%m-%d")],
        ),
        serie_sintetica(
            "BCB_SGS_433",
            [("2020-09-30", 0.64), ("2020-12-31", 1.35), ("2021-03-31", 0.93)],
        ),
        serie_sintetica(
            "SIDRA_1737_V63",
            [("2020-09-30", 0.64), ("2020-12-31", 1.35), ("2021-03-31", 0.93)],
        ),
        serie_sintetica("SP500_BRL", diarias),
    ]
    raw = pd.concat(pedacos, ignore_index=True).sort_values(["series_id", "date"], kind="mergesort")
    destino = caminho_camada(Camada.CANONICAL, raiz=raiz)
    destino.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(destino / NOME_RAW_SERIES, index=False)
    materializar_catalogo(load_catalog(), raw).to_parquet(destino / NOME_CATALOGO, index=False)
    return raw


def test_build_sintetico_grava_os_dois_artefatos_validados(tmp_path: Path) -> None:
    """O build escreve `alinhado_trimestral.parquet` + relatório, e o Parquet passa no schema."""
    acervo_sintetico_em_disco(tmp_path)
    resultado = construir(
        raiz=tmp_path,
        calendario=calendario_sintetico(2020, 2021),
        quarters=QUARTERS_DO_BUILD_SINTETICO,
    )
    assert resultado.caminho_alinhado == caminho_canonical(NOME_ALINHADO, raiz=tmp_path)
    assert resultado.caminho_alinhado.is_file()
    assert resultado.caminho_relatorio.is_file()

    gravado = pd.read_parquet(resultado.caminho_alinhado)
    AlinhadoTrimestralSchema.validate(gravado, lazy=True)
    assert tuple(gravado.columns) == COLUNAS_ALINHADO
    assert set(gravado["series_id"]) == set(resultado.alinhado["series_id"])
    assert "SP500_BRL" not in set(gravado["series_id"]), "série derivada tem de ficar fora"
    assert [e["series_id"] for e in resultado.excluidas] == ["SP500_BRL"]


def test_build_sintetico_reproduz_o_caso_d_h_no_quarto_trimestre(tmp_path: Path) -> None:
    """A B3 sem 31/12 fica com `ffill = 1`; as demais séries diárias, com 0."""
    acervo_sintetico_em_disco(tmp_path)
    resultado = construir(
        raiz=tmp_path,
        calendario=calendario_sintetico(2020, 2021),
        quarters=QUARTERS_DO_BUILD_SINTETICO,
    )
    tabela = resultado.alinhado
    assert celula(tabela, "B3_IBOV", "2020Q4")["ffill_dias_uteis"] == 1
    assert celula(tabela, "ANBIMA_IMAB", "2020Q4")["ffill_dias_uteis"] == 0
    com_ffill = tabela[tabela["ffill_dias_uteis"] > 0]
    assert set(com_ffill["series_id"]) == {"B3_IBOV"}
    assert set(com_ffill["quarter"]) == {"2020Q4"}


def test_relatorio_tem_ffill_por_serie_e_por_trimestre(tmp_path: Path) -> None:
    """O relatório é o insumo da revisão independente: a contagem tem de estar **no dado**."""
    acervo_sintetico_em_disco(tmp_path)
    resultado = construir(
        raiz=tmp_path,
        calendario=calendario_sintetico(2020, 2021),
        quarters=QUARTERS_DO_BUILD_SINTETICO,
    )
    relatorio = json.loads(resultado.caminho_relatorio.read_text(encoding="utf-8"))
    assert relatorio["feature"] == "F-014"
    assert relatorio["ffill_por_serie"] == {"B3_IBOV": {"1": 1}}
    assert relatorio["ffill_por_trimestre"]["2020Q4"]["series"] == ["B3_IBOV"]
    assert relatorio["decisao_d_h"]["celulas_com_ffill"] == 1
    assert relatorio["alinhado_trimestral"]["sha256"] == sha256_de(
        resultado.caminho_alinhado.read_bytes()
    )
    assert "SP500_BRL" in {e["series_id"] for e in relatorio["series_fora_do_alinhamento"]}
    assert "hora" not in json.dumps(relatorio).lower()


def test_build_e_idempotente_por_hash(tmp_path: Path) -> None:
    """RF-048/CA-121: duas rodadas sobre a mesma entrada dão Parquet e relatório byte-idênticos."""
    acervo_sintetico_em_disco(tmp_path)
    hashes = []
    for _ in range(2):
        resultado = construir(
            raiz=tmp_path,
            calendario=calendario_sintetico(2020, 2021),
            quarters=QUARTERS_DO_BUILD_SINTETICO,
        )
        hashes.append(
            (
                sha256_de(resultado.caminho_alinhado.read_bytes()),
                sha256_de(resultado.caminho_relatorio.read_bytes()),
            )
        )
    assert hashes[0] == hashes[1]


def test_versao_build_cobre_os_cinco_componentes_e_nao_so_este_arquivo() -> None:
    """P1-1 do QA da Onda 2, aplicado aqui: hash **do conjunto**, não de um arquivo.

    Editar o calendário, o contrato da tabela ou o catálogo muda `alinhado_trimestral` sem tocar
    `alinhamento.py`. `versao_build` igual com Parquet diferente é indistinguível de bug — por isso
    os cinco módulos entram no hash, e retirar qualquer um tem de mudar o resultado.
    """
    assert len(MODULOS_DO_ALINHAMENTO) == 5
    assert "apps.pipeline.extract.calendario_anbima" in MODULOS_DO_ALINHAMENTO
    assert "packages.shared.schemas.series_catalog_data" in MODULOS_DO_ALINHAMENTO
    completo = versao_build()
    assert len(completo) == 64
    assert completo == versao_build(MODULOS_DO_ALINHAMENTO)
    for fora in MODULOS_DO_ALINHAMENTO:
        parcial = tuple(m for m in MODULOS_DO_ALINHAMENTO if m != fora)
        assert versao_build(parcial) != completo, fora


def test_build_sem_raw_series_bloqueia(tmp_path: Path) -> None:
    """Sem a camada de F-013 não há o que alinhar — e a mensagem diz o comando que falta."""
    with pytest.raises(FonteIndisponivel) as erro:
        construir(raiz=tmp_path, calendario=calendario_sintetico(2020, 2021))
    assert "BLOQUEADO — FONTE INDISPONÍVEL" in str(erro.value)
    assert "build_raw_series" in str(erro.value)


def test_build_sem_serie_exigida_bloqueia(tmp_path: Path) -> None:
    """**CA-076.** Falta o CDI: o build para, em vez de entregar painel mais magro em silêncio."""
    raw = acervo_sintetico_em_disco(tmp_path)
    sem_cdi = raw[raw["series_id"] != "BCB_SGS_12"]
    destino = caminho_camada(Camada.CANONICAL, raiz=tmp_path)
    sem_cdi.to_parquet(destino / NOME_RAW_SERIES, index=False)
    materializar_catalogo(load_catalog(), sem_cdi).to_parquet(destino / NOME_CATALOGO, index=False)
    with pytest.raises(FonteIndisponivel) as erro:
        construir(
            raiz=tmp_path,
            calendario=calendario_sintetico(2020, 2021),
            quarters=QUARTERS_DO_BUILD_SINTETICO,
        )
    assert "BCB_SGS_12" in str(erro.value)


def test_catalogo_de_outra_rodada_que_raw_series_bloqueia(tmp_path: Path) -> None:
    """Os dois artefatos de F-013 têm de vir do mesmo build: início velho = painel errado."""
    raw = acervo_sintetico_em_disco(tmp_path)
    catalogo = materializar_catalogo(load_catalog(), raw)
    mexido = catalogo.copy()
    alvo = mexido["series_id"] == "B3_IBOV"
    mexido.loc[alvo, "data_inicio_observada"] = pd.Timestamp("2006-01-02")
    with pytest.raises(InicioDeSerieIncoerente) as erro:
        inicio_observado_por_serie(mexido, raw[raw["source"] != "DERIVADO"])
    assert "B3_IBOV" in str(erro.value)


# ═════════════════════════════════════════════════════════════════════════════
# E — acervos reais (fixture versionada + data/canonical, padrão `Acervo`)
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


@dataclass(frozen=True)
class Acervo:
    """Uma fonte real de séries para alinhar, com os pisos que cabem no seu recorte.

    Os pisos são por acervo de propósito: a fixture tem 7 séries recortadas em 2006-01..2006-06 +
    a ponta viva, e `data/canonical/` tem as 49 completas. Usar o piso da fixture no disco
    esconderia fonte inteira faltando.
    """

    rotulo: str
    minimo_series: int
    quarters: tuple[str, ...]
    anos_do_calendario: tuple[int, ...]


ACERVO_FIXTURES = Acervo(
    rotulo="fixtures",
    minimo_series=7,
    quarters=("2006Q1", "2006Q2", "2006Q3", "2006Q4"),
    anos_do_calendario=(2006,),
)
ACERVO_CANONICAL = Acervo(
    rotulo="data/canonical",
    minimo_series=40,
    quarters=quarters_da_janela(),
    anos_do_calendario=(),
)


def raw_series_do_acervo(acervo: Acervo) -> pd.DataFrame:
    """A tabela longa do acervo, já sem as séries derivadas (que são de F-016/F-017)."""
    if acervo is ACERVO_FIXTURES:
        pedacos = [
            pd.read_parquet(p)
            for p in sorted(FIXTURES_PROCESSED.glob("*/*.parquet"))
            if "td_painel" not in p.as_posix()
        ]
        bruto = pd.concat(pedacos, ignore_index=True)
    else:
        bruto = pd.read_parquet(caminho_canonical(NOME_RAW_SERIES))
    return fatiar_para_alinhamento(bruto)[0]


def calendario_do_acervo(acervo: Acervo) -> Calendario:
    """Calendário real: das páginas versionadas na fixture, do Parquet extraído no disco."""
    if acervo is ACERVO_FIXTURES:
        return calendario_real_de(*acervo.anos_do_calendario)
    return Calendario.do_parquet()


def canonical_disponivel() -> bool:
    """`data/canonical/raw_series.parquet` + o calendário processado existem nesta máquina?"""
    return (
        caminho_canonical(NOME_RAW_SERIES).is_file()
        and (
            caminho_camada(Camada.PROCESSED) / "calendario" / "dias_uteis_anbima.parquet"
        ).is_file()
    )


def _acervos() -> tuple[Acervo, ...]:
    """A fixture sempre; `data/canonical/` por acréscimo, quando existe de verdade."""
    if ignorar_data_real() or not canonical_disponivel():
        return (ACERVO_FIXTURES,)
    return (ACERVO_FIXTURES, ACERVO_CANONICAL)


ACERVOS = _acervos()


@pytest.fixture(params=ACERVOS, ids=[a.rotulo for a in ACERVOS])
def acervo(request: pytest.FixtureRequest) -> Acervo:
    """Acervo sob alinhamento. `fixtures` **nunca pula**: recorte ausente é falha."""
    alvo: Acervo = request.param
    if alvo is ACERVO_FIXTURES and not FIXTURES_PROCESSED.is_dir():
        pytest.fail(f"recorte versionado ausente em {FIXTURES_PROCESSED}")
    return alvo


@pytest.fixture
def alinhado_do_acervo(acervo: Acervo) -> tuple[Acervo, pd.DataFrame, pd.DataFrame]:
    """`(acervo, raw, alinhado)` — o alinhamento recalculado a partir do acervo."""
    raw = raw_series_do_acervo(acervo)
    assert raw["series_id"].nunique() >= acervo.minimo_series, (
        f"{acervo.rotulo}: {raw['series_id'].nunique()} série(s), mínimo {acervo.minimo_series}"
    )
    calendario = calendario_do_acervo(acervo)
    tabela = alinhar_series(
        raw,
        calendario=calendario,
        inicio_por_serie=inicio_de(raw),
        trimestres=grade_de_trimestres(calendario, quarters=acervo.quarters),
    )
    return acervo, raw, tabela


def test_acervo_toda_celula_com_valor_e_identica_a_origem(
    alinhado_do_acervo: tuple[Acervo, pd.DataFrame, pd.DataFrame],
) -> None:
    """**O diff numérico da classe C.** Cada valor alinhado é o valor bruto na `date_obs` gravada.

    Comparação **exata** (`==` em `float64`, sem tolerância): não há cálculo nenhum nesta camada
    para tolerar. O `validate="one_to_one"` do merge é parte da afirmação — se a `date_obs` de uma
    linha casasse com duas linhas de `raw_series`, o teste falharia em vez de comparar a primeira.
    """
    _, raw, tabela = alinhado_do_acervo
    com_valor = tabela[tabela["value"].notna()]
    assert len(com_valor) > 0

    junto = com_valor.merge(
        raw[["series_id", "date", "vintage", "value", "source", "unit", "freq"]],
        left_on=["series_id", "date_obs", "vintage"],
        right_on=["series_id", "date", "vintage"],
        how="left",
        suffixes=("_alinhado", "_bruto"),
        validate="one_to_one",
    )
    assert junto["value_bruto"].notna().all(), "date_obs que não existe em raw_series"
    divergentes = junto[junto["value_alinhado"] != junto["value_bruto"]]
    assert len(divergentes) == 0, divergentes.head().to_string()
    for coluna in ("source", "unit", "freq"):
        assert (junto[f"{coluna}_alinhado"] == junto[f"{coluna}_bruto"]).all(), coluna


def test_acervo_respeita_o_limite_de_ffill_e_declara_todo_nulo(
    alinhado_do_acervo: tuple[Acervo, pd.DataFrame, pd.DataFrame],
) -> None:
    """CA-066/CA-067 no dado real: ffill ∈ 0..5, e todo nulo tem motivo e lacuna registrada."""
    _, _, tabela = alinhado_do_acervo
    assert tabela["ffill_dias_uteis"].between(0, LIMITE_FFILL_DIAS_UTEIS).all()
    nulos = tabela[tabela["value"].isna()]
    assert nulos["motivo_nulo"].notna().all()
    por_lacuna = nulos[nulos["motivo_nulo"] == MOTIVO_LACUNA_ACIMA_DO_LIMITE]
    assert (por_lacuna["lacuna_dias_uteis"] > LIMITE_FFILL_DIAS_UTEIS).all()
    assert por_lacuna["date_ultima_obs"].notna().all()


def test_acervo_nao_preenche_buraco_grande_do_recorte(
    alinhado_do_acervo: tuple[Acervo, pd.DataFrame, pd.DataFrame],
) -> None:
    """A trava mais forte do limite de ffill, construída sem dado sintético.

    O recorte da fixture **pula** 2006-07 a 2026-06. Se o forward-fill fosse ilimitado, 3T2006 e
    4T2006 herdariam o valor de 30/06/2006 e ninguém notaria — o número pareceria plausível. Com o
    limite de 5 d.u. os dois trimestres têm de ser **nulos**, com a lacuna medida em dezenas de
    dias úteis.
    """
    acervo, _, tabela = alinhado_do_acervo
    if acervo is not ACERVO_FIXTURES:
        pytest.skip("Acervo data/canonical: as séries são contínuas, não há buraco de recorte")
    for quarter in ("2006Q3", "2006Q4"):
        recorte = tabela[tabela["quarter"] == quarter]
        assert len(recorte) == 7
        assert recorte["value"].isna().all(), f"{quarter} não pode herdar junho de 2006"
        assert (recorte["lacuna_dias_uteis"] > LIMITE_FFILL_DIAS_UTEIS).all()


def test_acervo_fixture_alinha_1t2006_e_2t2006_com_o_valor_do_recorte(
    alinhado_do_acervo: tuple[Acervo, pd.DataFrame, pd.DataFrame],
) -> None:
    """Os dois trimestres cobertos pelo recorte, conferidos contra o Parquet versionado."""
    acervo, raw, tabela = alinhado_do_acervo
    if acervo is not ACERVO_FIXTURES:
        pytest.skip("Acervo data/canonical: a conferência equivalente é o diff numérico")
    esperado = {
        ("ANBIMA_IMAB", "2006Q1"): "2006-03-31",
        ("B3_IBOV", "2006Q1"): "2006-03-31",
        ("YAHOO_GSPC", "2006Q1"): "2006-03-31",
        ("BCB_SGS_433", "2006Q1"): "2006-03-31",
        ("SIDRA_1737_V63", "2006Q1"): "2006-03-31",
        ("BCB_SGS_22109", "2006Q1"): "2006-03-31",
        ("SIDRA_1621_V584_90707", "2006Q1"): "2006-03-31",
        ("ANBIMA_IMAB", "2006Q2"): "2006-06-30",
        ("B3_IBOV", "2006Q2"): "2006-06-30",
    }
    for (series_id, quarter), data_obs in esperado.items():
        linha = celula(tabela, series_id, quarter)
        assert pd.Timestamp(linha["date_obs"]) == pd.Timestamp(data_obs), (series_id, quarter)
        assert linha["ffill_dias_uteis"] == 0
        bruto = raw[(raw["series_id"] == series_id) & (raw["date"] == pd.Timestamp(data_obs))][
            "value"
        ]
        assert linha["value"] == bruto.iloc[0]


def test_acervo_e_idempotente_na_funcao(
    alinhado_do_acervo: tuple[Acervo, pd.DataFrame, pd.DataFrame],
) -> None:
    """Duas chamadas sobre a mesma entrada dão DataFrames idênticos, coluna por coluna."""
    acervo, raw, primeiro = alinhado_do_acervo
    calendario = calendario_do_acervo(acervo)
    segundo = alinhar_series(
        raw,
        calendario=calendario,
        inicio_por_serie=inicio_de(raw),
        trimestres=grade_de_trimestres(calendario, quarters=acervo.quarters),
    )
    pd.testing.assert_frame_equal(primeiro, segundo, check_exact=True)


# ─────────────────────────────────────────────────────────────────────────────
# E.2 — só sobre `data/canonical/` real (pula com motivo quando o acervo não existe)
# ─────────────────────────────────────────────────────────────────────────────

MOTIVO_SEM_ACERVO = (
    "Acervo data/canonical ausente (ou LDC_IGNORAR_DATA ligada): rode "
    "`python -m apps.pipeline.canonical.build_raw_series --offline` e depois "
    "`python -m apps.pipeline.canonical.alinhamento --offline`"
)

#: Números medidos em 2026-10-11 sobre as 51 séries de `raw_series` (49 alinhadas).
LINHAS_ESPERADAS = 4038
SERIES_ESPERADAS = 49
CELULAS_FFILL_ESPERADAS = 215
TRIMESTRES_COM_FFILL_ESPERADOS = 20
SERIES_B3_ESPERADAS = 11


@pytest.fixture
def artefato_real() -> pd.DataFrame:
    """`data/canonical/alinhado_trimestral.parquet`, como o build o gravou."""
    if ignorar_data_real() or not caminho_canonical(NOME_ALINHADO).is_file():
        pytest.skip(MOTIVO_SEM_ACERVO)
    return pd.read_parquet(caminho_canonical(NOME_ALINHADO))


def test_real_artefato_tem_as_contagens_medidas(artefato_real: pd.DataFrame) -> None:
    """As contagens do relatório de build, travadas: 4.038 linhas, 49 séries, 83 trimestres."""
    AlinhadoTrimestralSchema.validate(artefato_real, lazy=True)
    assert len(artefato_real) == LINHAS_ESPERADAS
    assert artefato_real["series_id"].nunique() == SERIES_ESPERADAS
    assert artefato_real["quarter"].nunique() == 83
    assert sorted(artefato_real["quarter"].unique()) == list(quarters_da_janela())
    assert artefato_real.groupby("quarter")["quarter_end"].nunique().eq(1).all()


def test_real_painel_desbalanceado_tem_exatamente_os_tres_casos(
    artefato_real: pd.DataFrame,
) -> None:
    """CA-063: só ICON, IMOB e IFIX têm menos de 83 trimestres — e pelos pontos-base certos."""
    por_serie = artefato_real.groupby("series_id").size()
    curtas = por_serie[por_serie < 83].to_dict()
    assert curtas == {"B3_ICON": 80, "B3_IFIX": 64, "B3_IMOB": 76}
    inicios = artefato_real.groupby("series_id")["data_inicio_serie"].first()
    assert pd.Timestamp(inicios["B3_ICON"]) == pd.Timestamp("2006-12-28")
    assert pd.Timestamp(inicios["B3_IMOB"]) == pd.Timestamp("2007-12-28")
    assert pd.Timestamp(inicios["B3_IFIX"]) == pd.Timestamp("2010-12-30")


def test_real_o_ffill_e_so_o_caso_d_h(artefato_real: pd.DataFrame) -> None:
    """**D-h medido.** 215 células com `ffill = 1`, todas da B3, todas em 4º trimestre.

    Nenhuma outra série do acervo precisa de forward-fill em nenhum dos 83 trimestres — o que
    também diz que o calendário da ANBIMA bate com o das séries do BCB, da ANBIMA, do Yahoo e do
    MSCI nos 83 fechamentos.
    """
    com_ffill = artefato_real[artefato_real["ffill_dias_uteis"] > 0]
    assert len(com_ffill) == CELULAS_FFILL_ESPERADAS
    assert set(com_ffill["ffill_dias_uteis"]) == {1}
    assert com_ffill["series_id"].nunique() == SERIES_B3_ESPERADAS
    assert set(com_ffill["source"]) == {"B3_API"}
    assert com_ffill["quarter"].nunique() == TRIMESTRES_COM_FFILL_ESPERADOS
    assert sorted(com_ffill["quarter"].unique()) == [f"{ano}Q4" for ano in range(2006, 2026)]
    sem_ffill = artefato_real[artefato_real["ffill_dias_uteis"] == 0]
    assert set(sem_ffill[sem_ffill["source"] == "B3_API"]["quarter"].str[-2:]) == {"Q1", "Q2", "Q3"}


def test_real_os_sete_nulos_sao_o_trimestre_aberto(artefato_real: pd.DataFrame) -> None:
    """Os únicos nulos do acervo são 3T2026 de 7 séries M/Q ainda não divulgadas (CA-061/CA-067)."""
    nulos = artefato_real[artefato_real["value"].isna()]
    assert len(nulos) == 7
    assert set(nulos["quarter"]) == {"2026Q3"}
    assert set(nulos["motivo_nulo"]) == {MOTIVO_LACUNA_ACIMA_DO_LIMITE}
    assert set(nulos["freq"]) <= {"M", "Q"}
    assert sorted(nulos["series_id"]) == [
        "BCB_SGS_22099",
        "BCB_SGS_22109",
        "BCB_SGS_24363",
        "BCB_SGS_24364",
        "SIDRA_1620_V583_90707",
        "SIDRA_1621_V584_90707",
        "SIDRA_5932_V6564_90707",
    ]
    assert (nulos["lacuna_dias_uteis"] >= 42).all()


@pytest.mark.parametrize(
    ("series_id", "quarter", "date_obs", "valor", "ffill"),
    [
        ("B3_IBOV", "2006Q1", "2006-03-31", 37951.97, 0),
        ("ANBIMA_IMAB", "2006Q1", "2006-03-31", 1193.861827, 0),
        ("BCB_SGS_433", "2006Q1", "2006-03-31", 0.43, 0),
        ("SIDRA_1737_V63", "2006Q1", "2006-03-31", 0.43, 0),
        ("B3_IBOV", "2006Q4", "2006-12-28", 44473.71, 1),
    ],
)
def test_real_valores_canario(
    artefato_real: pd.DataFrame,
    series_id: str,
    quarter: str,
    date_obs: str,
    valor: float,
    ffill: int,
) -> None:
    """Os canários de 1T2006 (+ o 4T2006 do IBOV, que é D-h com nome e data).

    `BCB_SGS_433` e `SIDRA_1737_V63` são o IPCA de **março/2006 = 0,43%** por duas fontes
    independentes — o canário que o e-mail do Alexandre pede no item A2/A7.
    """
    linha = celula(artefato_real, series_id, quarter)
    assert pd.Timestamp(linha["date_obs"]) == pd.Timestamp(date_obs)
    assert linha["value"] == valor
    assert linha["ffill_dias_uteis"] == ffill


def test_real_ibov_no_4t2006_usa_o_ultimo_pregao_e_nao_o_dia_util_bancario(
    artefato_real: pd.DataFrame,
) -> None:
    """A prova de que `quarter_end` e `date_obs` divergem, e de que isso está **registrado**."""
    linha = celula(artefato_real, "B3_IBOV", "2006Q4")
    assert pd.Timestamp(linha["quarter_end"]) == pd.Timestamp("2006-12-29")
    assert pd.Timestamp(linha["date_obs"]) == pd.Timestamp("2006-12-28")
    assert linha["ffill_dias_uteis"] == 1
    bruto = pd.read_parquet(caminho_canonical(NOME_RAW_SERIES))
    ibov = bruto[bruto["series_id"] == "B3_IBOV"]
    assert pd.Timestamp("2006-12-29") not in set(ibov["date"]), "a B3 não negociou em 29/12/2006"
    assert linha["value"] == ibov[ibov["date"] == pd.Timestamp("2006-12-28")]["value"].iloc[0]


def test_real_grade_de_83_trimestres_cai_toda_em_dia_util(artefato_real: pd.DataFrame) -> None:
    """CA-065 nos 83, contra o calendário completo de `data/processed/` (não só na fixture)."""
    cal = Calendario.do_parquet()
    fins = artefato_real.groupby("quarter")["quarter_end"].first()
    assert len(fins) == 83
    for quarter, fim in fins.items():
        assert cal.e_dia_util(pd.Timestamp(fim).date()), quarter
    divergentes = sum(
        1
        for quarter, fim in fins.items()
        if pd.Timestamp(fim) != pd.Period(str(quarter), freq="Q").end_time.normalize()
    )
    assert divergentes == 24, "24 dos 83 fins de trimestre não caem no último dia civil"


def test_real_relatorio_bate_com_o_parquet(artefato_real: pd.DataFrame) -> None:
    """O relatório não é texto solto: `sha256` e contagens são do artefato que está em disco."""
    caminho = caminho_canonical(NOME_RELATORIO)
    if not caminho.is_file():
        pytest.skip(MOTIVO_SEM_ACERVO)
    relatorio = json.loads(caminho.read_text(encoding="utf-8"))
    bloco = relatorio["alinhado_trimestral"]
    assert bloco["sha256"] == sha256_de(caminho_canonical(NOME_ALINHADO).read_bytes())
    assert bloco["linhas"] == len(artefato_real)
    assert bloco["series"] == artefato_real["series_id"].nunique()
    assert bloco["celulas_nulas"] == int(artefato_real["value"].isna().sum())
    assert bloco["distribuicao_ffill_dias_uteis"] == {"0": 3823, "1": 215}
    assert len(relatorio["ffill_por_trimestre"]) == TRIMESTRES_COM_FFILL_ESPERADOS
    assert len(relatorio["ffill_por_serie"]) == SERIES_B3_ESPERADAS
    assert len(relatorio["grade"]["fins_de_periodo"]) == 83


def test_real_series_de_calendario_corrido_fecha_no_dia_civil(
    artefato_real: pd.DataFrame,
) -> None:
    """A meta Selic (SGS 432) é a única `grade=corrido`, e usa o último dia **civil**."""
    corridas = artefato_real[artefato_real["grade"] == GRADE_CORRIDO]
    assert set(corridas["series_id"]) == set(series_de_calendario_corrido()) == {"BCB_SGS_432"}
    assert len(corridas) == 83
    for _, linha in corridas.iterrows():
        fim_civil = pd.Period(str(linha["quarter"]), freq="Q").end_time.normalize()
        assert pd.Timestamp(linha["date_alvo"]) == fim_civil
        assert pd.Timestamp(linha["date_obs"]) == fim_civil
    assert (corridas["ffill_dias_uteis"] == 0).all()
    divergem = corridas[corridas["date_alvo"] != corridas["quarter_end"]]
    assert len(divergem) == 24, "nos 24 trimestres de fim civil não útil as duas datas divergem"
