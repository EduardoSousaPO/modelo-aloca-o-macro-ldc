"""F-018 — contrato da materialização `asof` e das suas duas tabelas. **Classe C.**

O que este arquivo prova, e nada além:

1. **`lag_adjusted=True` é contrato, e nunca se mistura.** `MacroQuarterlySchema` aceita as 83
   linhas com a flag acesa e **recusa** a tabela meio virada (`lag_adjusted_homogeneo`, CA-072) —
   é a mesma ideia do `test_schema_recusa_mistura_de_asof_e_revised` de F-015, agora pelo outro
   lado do par.
2. **`MacroQuarterlyAsofProvenanceSchema` é acréscimo, não alteração.** Ele tem **todas** as
   colunas, a PK e os checks de `MacroQuarterlyProvenanceSchema` **mais** `date_obs` e `lag_dias`;
   e o schema de F-015 continua **recusando** as duas (prova de que nada foi alterado embaixo de
   F-015, `AGENTS.md §7`).
3. **O teste central (CA-072) sobre o Parquet publicado.** Nenhuma linha de procedência da `asof`
   tem `date_obs + lag_dias` depois do `quarter_end` do seu trimestre. A consulta é refeita aqui,
   a partir dos dois artefatos em disco, **sem** importar a função que o build usa.
4. **A `revised` de F-015 continua intacta.** `macro_quarterly.parquet` segue com
   `lag_adjusted=False` nas 83 linhas: a `asof` grava ao lado, nunca por cima.
5. **A revisão numérica de classe C**: reprodução bit a bit do `revised`, os 3 canários, o % de
   trimestres diferentes por coluna e a idempotência por `sha256`.

A seção de acervo (`data/canonical/`) roda por acréscimo e é desligada por `LDC_IGNORAR_DATA=1`;
a de contrato puro roda sempre, sobre quadros mínimos construídos aqui.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from apps.pipeline.canonical.asof import (
    LAG_ADJUSTED,
    MATERIALIZACAO,
    NOME_ASOF,
    NOME_ASOF_PROVENANCE,
    NOME_RELATORIO_ASOF,
    construir,
    lags_de_divulgacao,
    lags_por_coluna,
)
from apps.pipeline.canonical.macro_quarterly import NOME_MACRO, NOME_PROVENANCE
from apps.pipeline.common.io_layers import caminho_canonical, sha256_de
from packages.shared.schemas import (
    COLUNAS_RASTREAVEIS,
    MacroQuarterlyAsofProvenanceSchema,
    MacroQuarterlyProvenanceSchema,
    MacroQuarterlySchema,
    load_catalog,
    quarters_da_janela,
)
from packages.shared.schemas.macro_quarterly import (
    N_TRIMESTRES_JANELA,
    ULTIMO_TRIMESTRE,
)

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
CATALOGO = {entrada.series_id: entrada for entrada in load_catalog()}

# ═════════════════════════════════════════════════════════════════════════════
# A — o contrato da tabela wide com a flag acesa
# ═════════════════════════════════════════════════════════════════════════════


def macro_minimo(*, lag_adjusted: bool = LAG_ADJUSTED) -> pd.DataFrame:
    """Um `macro_quarterly` válido mínimo: 83 linhas, tudo nulo onde é anulável."""
    quarters = list(quarters_da_janela())
    quadro = pd.DataFrame({"quarter": quarters})
    quadro["quarter_end"] = [pd.Period(q, freq="Q").end_time.normalize() for q in quarters]
    for coluna in COLUNAS_RASTREAVEIS:
        if coluna == "vertice_extrapolado":
            quadro[coluna] = False
        else:
            quadro[coluna] = pd.Series([float("nan")] * len(quarters), dtype="float64")
    quadro["is_estimated"] = [q == ULTIMO_TRIMESTRE for q in quarters]
    quadro["lag_adjusted"] = lag_adjusted
    quadro["fonte_versao"] = "0" * 64
    return quadro.loc[:, list(MacroQuarterlySchema.to_schema().columns)]


def test_schema_aceita_a_materializacao_asof_nas_83_linhas() -> None:
    """A `asof` usa **o mesmo** `MacroQuarterlySchema`: o que muda é a flag, não o contrato."""
    validado = MacroQuarterlySchema.validate(macro_minimo(lag_adjusted=True), lazy=True)
    assert len(validado) == N_TRIMESTRES_JANELA
    assert bool(validado["lag_adjusted"].all())
    assert LAG_ADJUSTED is True
    assert MATERIALIZACAO == "asof"


def test_schema_recusa_mistura_de_asof_e_revised_na_tabela_wide() -> None:
    """`lag_adjusted_homogeneo` (CA-072): uma linha `revised` numa tabela `asof` **falha**."""
    misturado = macro_minimo(lag_adjusted=True)
    misturado.loc[0, "lag_adjusted"] = False
    with pytest.raises(Exception, match="lag_adjusted_homogeneo"):
        MacroQuarterlySchema.validate(misturado, lazy=True)


# ═════════════════════════════════════════════════════════════════════════════
# B — `MacroQuarterlyAsofProvenanceSchema`: acréscimo, não alteração
# ═════════════════════════════════════════════════════════════════════════════


def procedencia_minima(*, lag_adjusted: bool = LAG_ADJUSTED) -> pd.DataFrame:
    """Duas linhas de procedência `asof` válidas — uma de nível, uma de fluxo."""
    return pd.DataFrame(
        {
            "quarter": ["2010Q1", "2026Q3"],
            "column": ["pib_yoy", "ipca_12m"],
            "series_id": ["SIDRA_1620_V583_90707", "BCB_SGS_13522"],
            "source": ["IBGE_SIDRA", "BCB_SGS"],
            "vintage": [pd.Timestamp("2026-10-11"), pd.Timestamp("2026-10-11")],
            "collected_at": [pd.Timestamp("2026-10-11"), pd.Timestamp("2026-10-11")],
            "lag_adjusted": [lag_adjusted, lag_adjusted],
            "fonte_versao": ["0" * 64, "0" * 64],
            "date_obs": [pd.Timestamp("2009-12-31"), pd.Timestamp("2026-08-31")],
            "lag_dias": [60, 10],
        }
    ).loc[:, list(MacroQuarterlyAsofProvenanceSchema.to_schema().columns)]


def test_procedencia_asof_e_superconjunto_da_de_f015() -> None:
    """Mesmas colunas, mesma PK, mesmos checks — **mais** `date_obs` e `lag_dias`."""
    base = MacroQuarterlyProvenanceSchema.to_schema()
    estendido = MacroQuarterlyAsofProvenanceSchema.to_schema()
    assert set(base.columns) < set(estendido.columns)
    assert set(estendido.columns) - set(base.columns) == {"date_obs", "lag_dias"}
    assert estendido.unique == base.unique == ["quarter", "column"]
    # pandera carrega os checks herdados pelo **nome do método** (`_lag_homogeneo`), e não pelo
    # `name=` do decorador: o que importa é que os dois continuam valendo na subclasse.
    nomes = {c.name for c in estendido.checks}
    assert {"_vintage_coerente", "_lag_homogeneo"} <= nomes
    assert len(estendido.checks) == len(base.checks) == 2


def test_procedencia_minima_satisfaz_o_schema_novo() -> None:
    """O contrato aceita a forma publicada, com `date_obs` anterior ao trimestre da linha."""
    validado = MacroQuarterlyAsofProvenanceSchema.validate(procedencia_minima(), lazy=True)
    assert len(validado) == 2
    assert list(validado["lag_dias"]) == [60, 10]


def test_schema_de_f015_continua_recusando_as_duas_colunas_novas() -> None:
    """A prova de que foi **acréscimo**: `strict=True` do schema de F-015 recusa o superconjunto.

    Se este teste passar a falhar, alguém alterou `MacroQuarterlyProvenanceSchema` — o que é
    pausa, não acréscimo (`AGENTS.md §7`), e quebraria `macro_quarterly_provenance.parquet`.
    """
    with pytest.raises(Exception, match="date_obs|lag_dias|column"):
        MacroQuarterlyProvenanceSchema.validate(procedencia_minima(), lazy=True)


def test_procedencia_asof_recusa_mistura_de_materializacao() -> None:
    """`lag_adjusted_homogeneo` herdado: procedência meio `asof`, meio `revised`, **falha**."""
    misturado = procedencia_minima()
    misturado.loc[0, "lag_adjusted"] = False
    with pytest.raises(Exception, match="_lag_homogeneo"):
        MacroQuarterlyAsofProvenanceSchema.validate(misturado, lazy=True)


def test_procedencia_asof_recusa_lag_negativo_e_absurdo() -> None:
    """`lag_dias` em [0, 400]: defasagem negativa é divulgação antes da referência."""
    for valor in (-1, 401):
        errado = procedencia_minima()
        errado.loc[0, "lag_dias"] = valor
        with pytest.raises(Exception, match="lag_dias|greater|less"):
            MacroQuarterlyAsofProvenanceSchema.validate(errado, lazy=True)


def test_procedencia_asof_recusa_pk_repetida_e_coluna_fora_do_contrato() -> None:
    """PK `(quarter, column)` e `column` dentro de `COLUNAS_RASTREAVEIS` — como na de F-015."""
    repetido = procedencia_minima()
    repetido.loc[1, ["quarter", "column"]] = ["2010Q1", "pib_yoy"]
    with pytest.raises(Exception, match="unique"):
        MacroQuarterlyAsofProvenanceSchema.validate(repetido, lazy=True)

    inventada = procedencia_minima()
    inventada.loc[0, "column"] = "pib_yoy_asof"
    with pytest.raises(Exception, match="isin|column"):
        MacroQuarterlyAsofProvenanceSchema.validate(inventada, lazy=True)


def test_procedencia_asof_recusa_vintage_depois_da_coleta() -> None:
    """Check herdado de F-015: não se conhece um valor antes de baixá-lo."""
    errado = procedencia_minima()
    errado.loc[0, "vintage"] = pd.Timestamp("2026-10-12")
    with pytest.raises(Exception, match="_vintage_coerente"):
        MacroQuarterlyAsofProvenanceSchema.validate(errado, lazy=True)


def test_lag_por_coluna_cobre_todas_as_colunas_rastreaveis() -> None:
    """Toda coluna rastreável tem um lag declarado — nenhuma fica sem resposta no relatório."""
    mapa = lags_por_coluna(lags_de_divulgacao())
    assert set(mapa) == set(COLUNAS_RASTREAVEIS)
    assert all(0 <= v <= 400 for v in mapa.values())


# ═════════════════════════════════════════════════════════════════════════════
# C — acervo real: o teste central, os canários e o diff numérico
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


def acervo_disponivel() -> bool:
    """Os artefatos da `asof` **e** os de F-015 existem nesta máquina?"""
    return (
        not ignorar_data_real()
        and caminho_canonical(NOME_ASOF).is_file()
        and caminho_canonical(NOME_ASOF_PROVENANCE).is_file()
        and caminho_canonical(NOME_MACRO).is_file()
    )


acervo = pytest.mark.skipif(
    not acervo_disponivel(),
    reason=(
        f"acervo ausente (ou {VAR_IGNORAR_DATA} ligada): rode "
        f"`uv run python -m apps.pipeline.canonical.asof --offline`"
    ),
)


@pytest.fixture(scope="module")
def asof() -> pd.DataFrame:
    """`macro_quarterly_asof.parquet` publicado, validado pelo schema."""
    return MacroQuarterlySchema.validate(pd.read_parquet(caminho_canonical(NOME_ASOF)), lazy=True)


@pytest.fixture(scope="module")
def procedencia() -> pd.DataFrame:
    """`macro_quarterly_asof_provenance.parquet` publicado, validado pelo schema novo."""
    return MacroQuarterlyAsofProvenanceSchema.validate(
        pd.read_parquet(caminho_canonical(NOME_ASOF_PROVENANCE)), lazy=True
    )


@pytest.fixture(scope="module")
def revised() -> pd.DataFrame:
    """`macro_quarterly.parquet` (F-015) publicado — a outra metade do par."""
    return MacroQuarterlySchema.validate(pd.read_parquet(caminho_canonical(NOME_MACRO)), lazy=True)


@pytest.fixture(scope="module")
def relatorio() -> dict[str, object]:
    """`relatorio_asof.json` publicado."""
    import json

    return json.loads(caminho_canonical(NOME_RELATORIO_ASOF).read_text(encoding="utf-8"))


@acervo
def test_acervo_asof_tem_83_linhas_com_a_flag_acesa(asof: pd.DataFrame) -> None:
    """CA-059 + CA-072 no artefato: 83 linhas `2006Q1..2026Q3`, `lag_adjusted=True` em todas."""
    assert len(asof) == N_TRIMESTRES_JANELA
    assert list(asof["quarter"]) == list(quarters_da_janela())
    assert bool(asof["lag_adjusted"].all())
    assert asof.shape[1] == 42


@acervo
def test_acervo_revised_de_f015_continua_intacta(revised: pd.DataFrame) -> None:
    """A `asof` grava **ao lado**: `macro_quarterly.parquet` segue `lag_adjusted=False` nas 83."""
    assert len(revised) == N_TRIMESTRES_JANELA
    assert not revised["lag_adjusted"].any()
    antiga = MacroQuarterlyProvenanceSchema.validate(
        pd.read_parquet(caminho_canonical(NOME_PROVENANCE)), lazy=True
    )
    assert not antiga["lag_adjusted"].any()
    assert "date_obs" not in antiga.columns


@acervo
def test_acervo_nenhuma_celula_usa_dado_divulgado_depois_do_fim_do_trimestre(
    asof: pd.DataFrame, procedencia: pd.DataFrame
) -> None:
    """**O teste central — CA-072.**

    Para cada linha de procedência: `date_obs + lag_dias <= quarter_end` do trimestre da linha. A
    consulta é escrita **aqui**, a partir dos dois Parquets em disco, sem importar a função que o
    build usa — se a `asof` for publicada com uma célula olhando para o futuro, este teste falha
    independentemente do que o módulo acredite.
    """
    juntos = procedencia.merge(asof.loc[:, ["quarter", "quarter_end"]], on="quarter", how="left")
    assert juntos["quarter_end"].notna().all()
    com_data = juntos.loc[juntos["date_obs"].notna()].copy()
    assert len(com_data) > 2_000
    divulgacao = com_data["date_obs"] + pd.to_timedelta(com_data["lag_dias"], unit="D")
    atrasadas = com_data.loc[divulgacao > com_data["quarter_end"]]
    assert atrasadas.empty, (
        f"{len(atrasadas)} célula(s) com look-ahead: "
        f"{atrasadas.loc[:, ['quarter', 'column', 'date_obs']].head(5).to_dict('records')}"
    )


@acervo
def test_acervo_o_lag_da_procedencia_bate_com_o_catalogo(procedencia: pd.DataFrame) -> None:
    """`lag_dias` da linha é o que o `series_catalog` declara para os insumos da coluna."""
    esperado = lags_por_coluna(lags_de_divulgacao())
    medido = procedencia.groupby("column")["lag_dias"].agg(["min", "max"])
    for coluna, linha in medido.iterrows():
        assert linha["min"] == linha["max"] == esperado[str(coluna)], coluna


@acervo
def test_acervo_procedencia_resolve_no_catalogo_e_cobre_as_celulas_preenchidas(
    asof: pd.DataFrame, procedencia: pd.DataFrame
) -> None:
    """CA-120 na `asof`, por anti-join nas duas direções — e todo `series_id` no catálogo."""
    assert set(procedencia["series_id"]) <= set(CATALOGO)

    preenchidas = {
        (q, coluna)
        for coluna in COLUNAS_RASTREAVEIS
        for q, valor in zip(asof["quarter"], asof[coluna], strict=True)
        if pd.notna(valor)
    }
    com_procedencia = set(zip(procedencia["quarter"], procedencia["column"], strict=True))
    # `vertice_extrapolado` é booleana e nunca nula: tem procedência nos 83, inclusive quando False
    flag = {(q, "vertice_extrapolado") for q in asof["quarter"]}
    assert (preenchidas | flag) - com_procedencia == set()
    assert com_procedencia - (preenchidas | flag) == set()


@acervo
def test_acervo_os_tres_canarios_do_relatorio_batem(
    relatorio: dict[str, object], asof: pd.DataFrame, revised: pd.DataFrame
) -> None:
    """Os 3 canários de `AGENTS.md §15.9`, recalculados aqui a partir dos dois Parquets.

    1. `pib_yoy` de `2010Q1` na `asof` **é** o de `2009Q4` na `revised` (lag 60 d);
    2. `ipca_12m` de `2026Q3` na `asof` vem da observação de **2026-08-31** (lag 10 d);
    3. `focus_ipca_12m` é **idêntico** nas duas (lag 0).
    """
    canarios = relatorio["canarios"]  # type: ignore[index]
    pelo_relatorio = canarios["pib_yoy_asof_2010Q1_e_o_revised_de_2009Q4"]
    assert pelo_relatorio["bate"] is True
    assert canarios["ipca_12m_asof_2026Q3_e_de_agosto"]["date_obs_usada"] == "2026-08-31"
    assert canarios["focus_ipca_12m_identico"]["bate"] is True

    de_asof = asof.set_index("quarter")
    de_revised = revised.set_index("quarter")
    assert de_asof.loc["2010Q1", "pib_yoy"] == de_revised.loc["2009Q4", "pib_yoy"]
    assert de_asof.loc["2010Q1", "pib_yoy"] != de_revised.loc["2010Q1", "pib_yoy"]
    for coluna in ("focus_ipca_12m", "focus_pib_ano", "focus_selic_fim", "cdi_tri", "usdbrl_fim"):
        esquerda, direita = de_revised[coluna], de_asof[coluna]
        assert ((esquerda.isna() & direita.isna()) | (esquerda == direita)).all(), coluna


@acervo
def test_acervo_ipca_12m_do_asof_vem_do_penultimo_mes(
    asof: pd.DataFrame, procedencia: pd.DataFrame
) -> None:
    """A regra observação a observação, medida nos 83: `date_obs` de `ipca_12m` é o 2º mês de `T`.

    O IPCA tem `lag = 10` d e `date` de fim de mês civil (D-a), então a última divulgação que cabe
    no fim de `T` é sempre a do **penúltimo** mês de `T` — exceto onde a série não cobre o
    trimestre. É a forma geral do canário 2.
    """
    linhas = procedencia.loc[procedencia["column"] == "ipca_12m"].set_index("quarter")
    assert len(linhas) == N_TRIMESTRES_JANELA
    for quarter, linha in linhas.iterrows():
        esperado = (pd.Period(str(quarter), freq="Q").end_time - pd.offsets.MonthEnd(1)).normalize()
        assert pd.Timestamp(linha["date_obs"]) == esperado, quarter
    fim = asof.set_index("quarter")["quarter_end"]
    assert (linhas["date_obs"] + pd.Timedelta(days=10) <= fim.loc[linhas.index]).all()


@acervo
def test_acervo_reproduz_o_revised_bit_a_bit_e_publica_o_diff(
    relatorio: dict[str, object],
) -> None:
    """O diff numérico de classe C: a montagem **sem** defasagem reproduz F-015, 0 divergência."""
    diff = relatorio["diff_vs_revised_em_disco"]  # type: ignore[index]
    assert diff["conferido"] is True
    assert diff["reproduz_bit_a_bit"] is True
    assert diff["divergencias"] == 0
    assert diff["max_abs_dif"] == 0.0
    assert diff["celulas_conferidas_sem_tolerancia"] >= 83 * len(COLUNAS_RASTREAVEIS) - 1
    assert len(str(diff["sha256_revised_em_disco"])) == 64


@acervo
def test_acervo_comparacao_por_coluna_e_completa_e_coerente(
    relatorio: dict[str, object], asof: pd.DataFrame, revised: pd.DataFrame
) -> None:
    """O relatório mede o % de trimestres diferentes **por coluna** — recalculado aqui."""
    comparacao = relatorio["comparacao_por_coluna"]  # type: ignore[index]
    assert set(comparacao) == set(COLUNAS_RASTREAVEIS)
    for coluna, bloco in comparacao.items():
        esquerda = revised[coluna].astype("float64")
        direita = asof[coluna].astype("float64")
        iguais = (esquerda.isna() & direita.isna()) | (esquerda == direita)
        assert bloco["n_diferentes"] == int((~iguais).sum()), coluna
        assert bloco["identica"] is bool(iguais.all()), coluna

    assert "focus_ipca_12m" in relatorio["colunas_identicas"]  # type: ignore[index]
    assert "cdi_tri" in relatorio["colunas_identicas"]  # type: ignore[index]
    for coluna in ("pib_yoy", "ibcbr_yoy", "ipca_12m", "ipca_tri", "ibcbr_gap"):
        assert coluna in relatorio["colunas_que_mudam"], coluna  # type: ignore[index]


@acervo
def test_acervo_publica_o_percentual_de_troca_de_quadrante(relatorio: dict[str, object]) -> None:
    """CA-073/CA-074: o % é calculado, exposto, e acima de 25% o texto afirma o que deve."""
    bloco = relatorio["troca_de_quadrante_proxy_v1"]  # type: ignore[index]
    assert bloco["trimestres_comparaveis"] > 50
    assert bloco["pct_que_trocam"] is not None
    assert bloco["limiar_pct"] == 25.0
    acima = bloco["pct_que_trocam"] > 25.0
    assert bloco["operacional"] is (not acima)
    assert ("NAO E OPERACIONAL" in bloco["texto"]) is acima
    assert relatorio["nota_para_f019"]  # type: ignore[index]


@acervo
def test_acervo_relatorio_declara_as_limitacoes_e_a_versao(relatorio: dict[str, object]) -> None:
    """Vintage único, lag em dias civis e proxy de quadrante vão **no relatório**."""
    limitacoes = relatorio["limitacoes"]  # type: ignore[index]
    assert "vintage_unico" in limitacoes
    assert "DEGENERADA" in limitacoes["vintage_unico"]
    assert "lag_em_dias_civis" in limitacoes
    assert len(str(relatorio["versao_build"])) == 64  # type: ignore[index]
    assert relatorio["versao_build"] != relatorio["versao_build_do_revised"]  # type: ignore[index]


@acervo
def test_acervo_e_idempotente_por_hash() -> None:
    """RF-048/CA-121: reconstruir sobre o acervo real reescreve os **mesmos bytes**.

    E, de passagem, reconfere **ao vivo** a reprodução do `revised`: `construir` levanta
    `ReproducaoDivergente` se a montagem sem defasagem deixar de bater com
    `macro_quarterly.parquet` em disco — inclusive se outra feature o tiver reconstruído depois.
    """
    hashes = []
    for _ in range(2):
        resultado = construir()
        diff = resultado.relatorio["diff_vs_revised_em_disco"]
        assert diff["divergencias"] == 0
        assert diff["sha256_revised_em_disco"] == sha256_de(
            caminho_canonical(NOME_MACRO).read_bytes()
        )
        hashes.append(
            tuple(
                sha256_de(caminho_canonical(nome).read_bytes())
                for nome in (NOME_ASOF, NOME_ASOF_PROVENANCE, NOME_RELATORIO_ASOF)
            )
        )
    assert hashes[0] == hashes[1]
