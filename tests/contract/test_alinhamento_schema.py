"""Contrato de `AlinhadoTrimestralSchema` — a grade trimestral *long* de F-014. **Classe C.**

Cada teste aqui pega uma linha **válida** e quebra **uma** regra, afirmando que o pandera recusa
pelo nome do check. É o complemento de `tests/unit/test_canonical_alinhamento.py`: lá se prova que
o build produz o número certo, aqui se prova que o contrato **recusa** o número errado — inclusive
os erros que um agente futuro cometeria de boa-fé (preencher lacuna acima do limite, herdar valor
sem registrar o ffill, criar uma segunda grade de fim de trimestre).

Nada aqui lê disco: as linhas são sintéticas e nomeadas como tal (Anti-SPEC §10.1.2).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pandera as pa
import pytest

from apps.pipeline.canonical.alinhamento import series_de_calendario_corrido
from apps.pipeline.extract.bcb_sgs import SERIES_DIARIAS_DE_CALENDARIO
from packages.shared.schemas import (
    COLUNAS_ALINHADO,
    GRADE_BANCARIA,
    GRADE_CIVIL,
    GRADE_CORRIDO,
    GRADES_VALIDAS,
    LIMITE_FFILL_DIAS_UTEIS,
    MOTIVO_LACUNA_ACIMA_DO_LIMITE,
    MOTIVO_SEM_OBSERVACAO,
    MOTIVOS_VALIDOS,
    PK_ALINHADO,
    AlinhadoTrimestralSchema,
    load_catalog,
)
from packages.shared.schemas.alinhado_trimestral import (
    N_TRIMESTRES_JANELA,
    PRIMEIRO_TRIMESTRE,
    ULTIMO_TRIMESTRE,
    quarters_da_janela,
)

VERSAO = "0" * 64
"""`fonte_versao` sintético — 64 hexas, o formato de um `sha256`."""


def linha_sintetica(**sobrescritas: Any) -> dict[str, Any]:
    """Uma linha **válida** de `alinhado_trimestral`, para ser quebrada em um ponto por teste."""
    base: dict[str, Any] = {
        "quarter": "2006Q1",
        "quarter_end": pd.Timestamp("2006-03-31"),
        "series_id": "B3_IBOV",
        "grade": GRADE_BANCARIA,
        "date_alvo": pd.Timestamp("2006-03-31"),
        "date_obs": pd.Timestamp("2006-03-31"),
        "value": 37951.97,
        "ffill_dias_uteis": 0,
        "date_ultima_obs": pd.Timestamp("2006-03-31"),
        "lacuna_dias_uteis": 0,
        "motivo_nulo": None,
        "freq": "D",
        "unit": "index",
        "source": "B3_API",
        "vintage": pd.Timestamp("2026-10-10"),
        "collected_at": pd.Timestamp("2026-10-10"),
        "data_inicio_serie": pd.Timestamp("2006-01-02"),
        "fonte_versao": VERSAO,
    }
    base.update(sobrescritas)
    return base


def quadro(*linhas: dict[str, Any]) -> pd.DataFrame:
    """DataFrame no contrato, com `motivo_nulo` já no dtype de string anulável."""
    tabela = pd.DataFrame(list(linhas)).loc[:, list(COLUNAS_ALINHADO)]
    tabela["motivo_nulo"] = tabela["motivo_nulo"].astype("string")
    return tabela


def erro_de(tabela: pd.DataFrame) -> str:
    """Valida esperando falha e devolve a mensagem — é nela que o nome do check é conferido."""
    with pytest.raises((pa.errors.SchemaErrors, pa.errors.SchemaError)) as capturado:
        AlinhadoTrimestralSchema.validate(tabela, lazy=True)
    return str(capturado.value)


# ─────────────────────────────────────────────────────────────────────────────
# A linha válida e as constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────


def test_linha_valida_passa_e_mantem_as_18_colunas_na_ordem() -> None:
    """A ordem das colunas é parte do artefato: Parquet reordenado é diff espúrio."""
    validado = AlinhadoTrimestralSchema.validate(quadro(linha_sintetica()), lazy=True)
    assert tuple(validado.columns) == COLUNAS_ALINHADO
    assert len(COLUNAS_ALINHADO) == 18


def test_janela_do_contrato_e_de_83_trimestres_de_2006q1_a_2026q3() -> None:
    """A janela de 20 anos do e-mail, derivada — nunca uma lista digitada (CA-059/RF-021)."""
    quarters = quarters_da_janela()
    assert len(quarters) == N_TRIMESTRES_JANELA == 83
    assert quarters[0] == PRIMEIRO_TRIMESTRE == "2006Q1"
    assert quarters[-1] == ULTIMO_TRIMESTRE == "2026Q3"
    assert len(set(quarters)) == len(quarters)


def test_limite_de_ffill_e_o_do_adr_006() -> None:
    """ADR-006 §(b).8 congela 5 dias úteis; o número vive no contrato, não no código."""
    assert LIMITE_FFILL_DIAS_UTEIS == 5
    assert GRADES_VALIDAS == [GRADE_BANCARIA, GRADE_CORRIDO, GRADE_CIVIL]
    assert MOTIVOS_VALIDOS == [MOTIVO_LACUNA_ACIMA_DO_LIMITE, MOTIVO_SEM_OBSERVACAO]
    assert PK_ALINHADO == ("series_id", "quarter")


def test_grades_validas_e_motivos_sao_listas_nao_tuplas() -> None:
    """Armadilha do pandera (F-008 §4.2): `isin` de tupla de 1 reprova toda linha.

    As duas constantes entram em `isin`. Guardá-las como **lista** é o que impede a regressão
    silenciosa de alguém "padronizar" para tupla e ver o schema rejeitar o dado inteiro.
    """
    assert isinstance(GRADES_VALIDAS, list)
    assert isinstance(MOTIVOS_VALIDOS, list)


def test_as_tres_fontes_de_calendario_corrido_dizem_a_mesma_coisa() -> None:
    """A régua de dia corrido é declarada em **três** lugares e tem de coincidir nos três.

    1. `series_catalog_data` → `SeriesCatalogEntry.calendario == "corrido"` (a fonte de verdade,
       acrescentada em 2026-10-11 pelo P1-2 do QA da Onda 2);
    2. `apps/pipeline/canonical/alinhamento.py` → `series_de_calendario_corrido()`, que **deriva**
       do catálogo em vez de digitar a lista;
    3. `apps/pipeline/extract/bcb_sgs.py` → `SERIES_DIARIAS_DE_CALENDARIO`, a guarda do lado da
       extração (que afrouxa a checagem de "série diária só tem dia útil").

    Série de calendário corrido declarada em só um dos lados seria **extraída** com a guarda certa
    e **alinhada na grade errada** (último dia útil em vez do último dia civil) — divergência que
    nenhum teste de módulo isolado pega e que vale 1 a 3 dias de defasagem em 24 dos 83 trimestres.
    """
    do_extrator = {f"BCB_SGS_{codigo}" for codigo in SERIES_DIARIAS_DE_CALENDARIO}
    do_catalogo = {e.series_id for e in load_catalog() if e.calendario == "corrido"}
    assert series_de_calendario_corrido() == frozenset(do_catalogo) == frozenset(do_extrator)
    assert do_catalogo == {"BCB_SGS_432"}, "hoje só a meta Selic publica em dia corrido"


def test_toda_serie_diaria_do_catalogo_declara_o_seu_calendario_ou_e_bancaria() -> None:
    """`calendario = None` cai na grade bancária — o default, e ele tem de ser **o** default.

    O teste existe para que o dia em que uma série diária nova chegar sem `calendario` medido o
    comportamento seja o declarado (grade bancária), não uma surpresa.
    """
    diarias = [e for e in load_catalog() if e.freq.value == "D"]
    assert diarias, "o catálogo tem séries diárias"
    sem_medida = [e.series_id for e in diarias if e.calendario is None]
    assert all(s not in series_de_calendario_corrido() for s in sem_medida)


# ─────────────────────────────────────────────────────────────────────────────
# Campos: tipo, domínio e faixa
# ─────────────────────────────────────────────────────────────────────────────


def test_coluna_ad_hoc_e_recusada() -> None:
    """`strict=True` / Anti-SPEC §10.4.24: coluna inventada fora do schema não entra."""
    tabela = quadro(linha_sintetica())
    tabela["ret_tri"] = 0.1
    assert "ret_tri" in erro_de(tabela)


def test_coluna_faltando_e_recusada() -> None:
    """`add_missing_columns=False`: coluna ausente é erro, não `NaN` silencioso."""
    tabela = quadro(linha_sintetica()).drop(columns=["ffill_dias_uteis"])
    assert "ffill_dias_uteis" in erro_de(tabela)


def test_pk_duplicada_e_recusada() -> None:
    """PK `(series_id, quarter)`: dois valores para o mesmo trimestre é ambiguidade, não dado."""
    assert erro_de(quadro(linha_sintetica(), linha_sintetica(value=1.0)))


@pytest.mark.parametrize("ffill", [6, 7, 83])
def test_ffill_acima_de_5_dias_uteis_e_recusado(ffill: int) -> None:
    """CA-067: o limite de ADR-006 §(b).8 é do **contrato**, não só do código do build."""
    tabela = quadro(linha_sintetica(ffill_dias_uteis=ffill, lacuna_dias_uteis=ffill))
    assert "ffill_dias_uteis" in erro_de(tabela)


def test_ffill_negativo_e_recusado() -> None:
    """`ffill` é uma contagem de passos para trás; negativo não significa nada."""
    assert erro_de(quadro(linha_sintetica(ffill_dias_uteis=-1, lacuna_dias_uteis=-1)))


def test_grade_fora_das_tres_e_recusada() -> None:
    """Grade nova sem passar pelo contrato é como a opção (b) de D-h entraria por descuido."""
    assert erro_de(quadro(linha_sintetica(grade="b3")))


def test_motivo_nulo_fora_dos_dois_e_recusado() -> None:
    """Ausência tem causa nomeada: motivo livre vira "não sei" documentado como se fosse dado."""
    assert erro_de(
        quadro(linha_sintetica(value=None, date_obs=None, motivo_nulo="feriado_municipal"))
    )


def test_source_fora_das_fontes_validas_e_recusado() -> None:
    """A procedência resolve no catálogo (CA-055/CA-120) — fonte inventada para antes."""
    assert erro_de(quadro(linha_sintetica(source="PLANILHA_DO_ANALISTA")))


# ─────────────────────────────────────────────────────────────────────────────
# Checks de DataFrame: a coerência que o tipo não pega
# ─────────────────────────────────────────────────────────────────────────────


def test_celula_nula_sem_motivo_e_recusada() -> None:
    """`value` nulo sem `motivo_nulo` é lacuna anônima — o oposto de CA-067."""
    tabela = quadro(linha_sintetica(value=None, date_obs=None, motivo_nulo=None))
    assert "nulo_tem_motivo_e_nao_tem_data" in erro_de(tabela)


def test_celula_nula_com_date_obs_preenchida_e_recusada() -> None:
    """Se o valor não foi usado, não existe "data da observação usada"."""
    tabela = quadro(
        linha_sintetica(
            value=None,
            motivo_nulo=MOTIVO_LACUNA_ACIMA_DO_LIMITE,
            lacuna_dias_uteis=9,
        )
    )
    assert "nulo_tem_motivo_e_nao_tem_data" in erro_de(tabela)


def test_celula_nula_com_ffill_e_recusada() -> None:
    """Não se gasta forward-fill para não produzir valor."""
    tabela = quadro(
        linha_sintetica(
            value=None,
            date_obs=None,
            motivo_nulo=MOTIVO_SEM_OBSERVACAO,
            ffill_dias_uteis=2,
            lacuna_dias_uteis=2,
        )
    )
    assert "nulo_tem_motivo_e_nao_tem_data" in erro_de(tabela)


def test_valor_herdado_sem_registrar_o_ffill_e_recusado() -> None:
    """**O erro central de CA-066.** Usar a observação da véspera e gravar `ffill = 0` apaga o
    único rastro de que o número não é do fechamento do trimestre — é como o 4º trimestre da B3
    passaria por "fechamento do dia" pelos próximos 20 anos."""
    tabela = quadro(
        linha_sintetica(
            date_obs=pd.Timestamp("2006-03-30"),
            date_ultima_obs=pd.Timestamp("2006-03-30"),
            ffill_dias_uteis=0,
            lacuna_dias_uteis=1,
        )
    )
    assert "ffill_e_a_lacuna_quando_ha_valor" in erro_de(tabela)


def test_lacuna_acima_do_limite_com_valor_e_recusada() -> None:
    """CA-067 pelo contrapositivo: medir a lacuna em 9 d.u. e ainda assim preencher."""
    tabela = quadro(
        linha_sintetica(
            date_obs=pd.Timestamp("2006-03-20"),
            date_ultima_obs=pd.Timestamp("2006-03-20"),
            ffill_dias_uteis=5,
            lacuna_dias_uteis=9,
        )
    )
    assert "lacuna_acima_do_limite_nunca_tem_valor" in erro_de(tabela)


def test_observacao_depois_do_alvo_e_recusada() -> None:
    """Base do `asof` (Anti-SPEC §10.2.7): o trimestre não enxerga o dia seguinte."""
    tabela = quadro(
        linha_sintetica(
            date_obs=pd.Timestamp("2006-04-03"), date_ultima_obs=pd.Timestamp("2006-04-03")
        )
    )
    assert "observacao_nunca_depois_do_alvo" in erro_de(tabela)


def test_observacao_que_nao_e_a_ultima_disponivel_e_recusada() -> None:
    """Pegar a penúltima observação disponível é erro de busca, não escolha legítima."""
    tabela = quadro(
        linha_sintetica(
            date_obs=pd.Timestamp("2006-03-30"),
            date_ultima_obs=pd.Timestamp("2006-03-31"),
            ffill_dias_uteis=1,
            lacuna_dias_uteis=1,
        )
    )
    assert "date_obs_e_a_ultima_observacao_disponivel" in erro_de(tabela)


def test_linha_antes_do_inicio_da_serie_e_recusada() -> None:
    """CA-063 / Anti-SPEC §10.1.1: o painel é desbalanceado por desenho (ICON, IMOB, IFIX)."""
    tabela = quadro(
        linha_sintetica(series_id="B3_IFIX", data_inicio_serie=pd.Timestamp("2010-12-30"))
    )
    assert "sem_linha_antes_do_inicio_da_serie" in erro_de(tabela)


@pytest.mark.parametrize("fora", ["2005Q4", "2026Q4", "2030Q1"])
def test_trimestre_fora_da_janela_de_20_anos_e_recusado(fora: str) -> None:
    """A janela é 2006Q1..2026Q3; trimestre fora dela não é dado, é erro de grade."""
    periodo = pd.Period(fora, freq="Q")
    tabela = quadro(
        linha_sintetica(
            quarter=fora,
            quarter_end=pd.Timestamp(periodo.end_time.date()),
            date_alvo=pd.Timestamp(periodo.end_time.date()),
            date_obs=pd.Timestamp(periodo.end_time.date()),
            date_ultima_obs=pd.Timestamp(periodo.end_time.date()),
        )
    )
    assert erro_de(tabela)


def test_trimestre_imediatamente_depois_da_janela_falha_pelo_check_da_janela() -> None:
    """`2026Q4` casa o regex de `quarter` — quem o recusa é o check da janela de 83, e é ele que
    tem de ser nomeado no erro: a ponta viva do dataset é onde um trimestre a mais entraria."""
    tabela = quadro(
        linha_sintetica(
            quarter="2026Q4",
            quarter_end=pd.Timestamp("2026-12-31"),
            date_alvo=pd.Timestamp("2026-12-31"),
            date_obs=pd.Timestamp("2026-12-31"),
            date_ultima_obs=pd.Timestamp("2026-12-31"),
        )
    )
    assert "quarter_dentro_da_janela_de_83" in erro_de(tabela)


def test_quarter_end_de_outro_trimestre_e_recusado() -> None:
    """CA-065: o rótulo e a data têm de ser do mesmo trimestre, sempre."""
    tabela = quadro(linha_sintetica(quarter_end=pd.Timestamp("2006-06-30")))
    assert "quarter_end_e_date_alvo_caem_no_trimestre" in erro_de(tabela)


def test_duas_grades_de_fim_de_trimestre_sao_recusadas() -> None:
    """**O alarme da opção (b) de D-h.** Duas réguas de fim de trimestre no mesmo `quarter`
    exigiriam declarar a grade em toda tabela e figura; o contrato de hoje é a opção (a), então
    `quarter_end` divergente na mesma linha de tempo tem de falhar aqui, não no slide."""
    tabela = quadro(
        linha_sintetica(),
        linha_sintetica(
            series_id="ANBIMA_IMAB",
            source="ANBIMA_S3",
            quarter_end=pd.Timestamp("2006-03-30"),
            date_alvo=pd.Timestamp("2006-03-30"),
            date_obs=pd.Timestamp("2006-03-30"),
            date_ultima_obs=pd.Timestamp("2006-03-30"),
            value=1193.861827,
        ),
    )
    assert "quarter_end_unico_por_trimestre" in erro_de(tabela)


def test_unidade_que_muda_dentro_da_serie_e_recusada() -> None:
    """Escala trocada no meio da série é o erro do Validation Mode §5 que não levanta exceção."""
    tabela = quadro(
        linha_sintetica(),
        linha_sintetica(
            quarter="2006Q2",
            quarter_end=pd.Timestamp("2006-06-30"),
            date_alvo=pd.Timestamp("2006-06-30"),
            date_obs=pd.Timestamp("2006-06-30"),
            date_ultima_obs=pd.Timestamp("2006-06-30"),
            unit="%",
        ),
    )
    assert "metadado_constante_por_serie" in erro_de(tabela)


def test_grade_que_muda_dentro_da_serie_e_recusada() -> None:
    """A régua é da série, não da linha: metade dos trimestres numa grade é inauditável."""
    tabela = quadro(
        linha_sintetica(),
        linha_sintetica(
            quarter="2006Q2",
            quarter_end=pd.Timestamp("2006-06-30"),
            date_alvo=pd.Timestamp("2006-06-30"),
            date_obs=pd.Timestamp("2006-06-30"),
            date_ultima_obs=pd.Timestamp("2006-06-30"),
            grade=GRADE_CIVIL,
        ),
    )
    assert "metadado_constante_por_serie" in erro_de(tabela)


def test_celula_nula_valida_passa_com_a_lacuna_registrada() -> None:
    """O caminho **positivo** de CA-067: nula, com motivo, com a lacuna medida e sem ffill."""
    tabela = quadro(
        linha_sintetica(
            series_id="BCB_SGS_22109",
            source="BCB_SGS",
            freq="Q",
            grade=GRADE_CIVIL,
            unit="index",
            quarter="2026Q3",
            quarter_end=pd.Timestamp("2026-09-30"),
            date_alvo=pd.Timestamp("2026-09-30"),
            date_obs=None,
            value=None,
            date_ultima_obs=pd.Timestamp("2026-06-30"),
            lacuna_dias_uteis=65,
            motivo_nulo=MOTIVO_LACUNA_ACIMA_DO_LIMITE,
        )
    )
    validado = AlinhadoTrimestralSchema.validate(tabela, lazy=True)
    assert validado["value"].isna().all()
    assert validado["lacuna_dias_uteis"].iloc[0] == 65
    assert pd.Timestamp(validado["date_ultima_obs"].iloc[0]) == pd.Timestamp("2026-06-30")


def test_grade_corrido_aceita_alvo_depois_do_quarter_end() -> None:
    """3T2006: `quarter_end = 2006-09-29` (sábado no civil) e `date_alvo = 2006-09-30`.

    É a única forma de a meta Selic (SGS 432, calendário corrido) ter o valor do dia 30 sem
    quebrar a grade bancária única — e o contrato tem de aceitá-la **explicitamente**.
    """
    tabela = quadro(
        linha_sintetica(
            series_id="BCB_SGS_432",
            source="BCB_SGS",
            unit="%a.a.",
            grade=GRADE_CORRIDO,
            quarter="2006Q3",
            quarter_end=pd.Timestamp("2006-09-29"),
            date_alvo=pd.Timestamp("2006-09-30"),
            date_obs=pd.Timestamp("2006-09-30"),
            date_ultima_obs=pd.Timestamp("2006-09-30"),
            value=14.25,
        )
    )
    validado = AlinhadoTrimestralSchema.validate(tabela, lazy=True)
    assert validado["date_alvo"].iloc[0] > validado["quarter_end"].iloc[0]
