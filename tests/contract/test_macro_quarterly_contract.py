"""F-015 — contrato de `macro_quarterly` e `macro_quarterly_provenance`. **Classe C.**

O que este arquivo prova, e nada além:

1. **O schema é o contrato.** As 42 colunas de `MacroQuarterlySchema`, nesta ordem, com os checks
   de janela (`janela_de_83_trimestres`, CA-059) e de materialização homogênea; e as 8 de
   `MacroQuarterlyProvenanceSchema` com `vintage <= collected_at`. Linha fora do contrato é
   **rejeitada** — há teste negativo para cada regra que importa.
2. **O dicionário de colunas é completo e bijetivo.** Toda coluna rastreável do schema tem uma
   linha em `ORIGENS` (série de origem, fórmula, unidade) e nenhuma linha de `ORIGENS` descreve
   coluna que não existe. É o que impede uma coluna nova entrar sem fórmula declarada.
3. **CA-120 por anti-join.** Toda célula não nula de coluna rastreável tem exatamente uma linha em
   `macro_quarterly_provenance`, e todo `series_id` da procedência **resolve** em `series_catalog`.
4. **CA-061 por construção.** Coluna sem fonte disponível sai nula **com motivo declarado**, e o
   teste falha se alguma ganhar valor sem ganhar fonte.

A seção de acervo (`data/canonical/`) roda por acréscimo e é desligada por `LDC_IGNORAR_DATA=1`; a
de contrato puro roda sempre, sobre quadros mínimos construídos aqui.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

import pandas as pd
import pytest

from apps.pipeline.canonical.macro_quarterly import (
    ACUMULADAS,
    CATALOGO_DO_FOCUS,
    LAG_ADJUSTED,
    MATERIALIZACAO,
    NOME_MACRO,
    NOME_PROVENANCE,
    NOME_RELATORIO,
    ORIGENS,
    SERIES_DA_CURVA,
    UNIDADES,
    VERTICE_ANCORA,
    VERTICES_PUBLICADOS,
)
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas import (
    COLUNAS_RASTREAVEIS,
    MacroQuarterlyProvenanceSchema,
    MacroQuarterlySchema,
    load_catalog,
    quarters_da_janela,
)
from packages.shared.schemas.macro_quarterly import (
    COLUNAS_SEM_PROCEDENCIA,
    N_TRIMESTRES_JANELA,
    PRIMEIRO_TRIMESTRE,
    ULTIMO_TRIMESTRE,
)
from packages.shared.schemas.raw_series import FONTES_VALIDAS

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

CATALOGO = {entrada.series_id: entrada for entrada in load_catalog()}

UNIDADES_ESPERADAS: frozenset[str] = frozenset({"%", "%a.a.", "pp", "index", "BRL", "bps", "bool"})
"""As unidades que `macro_quarterly` usa. **Nenhuma fração** — ver §"Unidade" do módulo."""


# ═════════════════════════════════════════════════════════════════════════════
# A — o schema é o contrato: colunas, ordem, checks e os negativos
# ═════════════════════════════════════════════════════════════════════════════


def quadro_minimo(*, lag_adjusted: bool = LAG_ADJUSTED) -> pd.DataFrame:
    """Um `macro_quarterly` válido mínimo: 83 linhas, tudo nulo onde é anulável.

    Serve para provar o **contrato**, não o dado: é a forma de verificar que o schema rejeita o que
    tem de rejeitar sem depender de `data/`.
    """
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


def test_quadro_minimo_satisfaz_o_schema() -> None:
    """O contrato aceita 83 linhas com **tudo** nulo: nulo é legítimo e informativo."""
    validado = MacroQuarterlySchema.validate(quadro_minimo(), lazy=True)
    assert len(validado) == N_TRIMESTRES_JANELA


def test_schema_tem_as_42_colunas_na_ordem_do_contrato() -> None:
    """A ordem das colunas é parte do artefato — mudar a ordem é mudar o Parquet."""
    colunas = list(MacroQuarterlySchema.to_schema().columns)
    assert len(colunas) == 42
    assert colunas[:2] == ["quarter", "quarter_end"]
    assert colunas[-3:] == ["is_estimated", "lag_adjusted", "fonte_versao"]
    assert set(colunas) == set(COLUNAS_RASTREAVEIS) | set(COLUNAS_SEM_PROCEDENCIA)


def test_schema_recusa_82_trimestres() -> None:
    """CA-059 negativo: 82 linhas **falham**. A janela de 20 anos é contrato, não convenção."""
    curto = quadro_minimo().iloc[:-1]
    with pytest.raises(Exception, match="janela_de_83_trimestres|83"):
        MacroQuarterlySchema.validate(curto, lazy=True)


def test_schema_recusa_trimestre_repetido() -> None:
    """CA-059 negativo: `quarter` é PK — repetir `2006Q1` falha."""
    repetido = quadro_minimo()
    repetido.loc[1, "quarter"] = PRIMEIRO_TRIMESTRE
    with pytest.raises(Exception, match="unique|janela"):
        MacroQuarterlySchema.validate(repetido, lazy=True)


def test_schema_recusa_coluna_extra() -> None:
    """`strict=True`: coluna inventada fora de `packages/shared/schemas/` falha (§10.4.24)."""
    extra = quadro_minimo()
    extra["ipca_nucleo"] = 1.0
    with pytest.raises(Exception, match="ipca_nucleo|column"):
        MacroQuarterlySchema.validate(extra, lazy=True)


def test_schema_recusa_mistura_de_asof_e_revised() -> None:
    """`lag_adjusted_homogeneo`: uma materialização não mistura as duas (CA-072)."""
    misturado = quadro_minimo()
    misturado.loc[0, "lag_adjusted"] = True
    with pytest.raises(Exception, match="lag_adjusted_homogeneo"):
        MacroQuarterlySchema.validate(misturado, lazy=True)


def test_schema_recusa_selic_fora_da_faixa() -> None:
    """`selic_meta_fim` em [0, 60] % a.a.: 1375 (escala errada por 100x) falha."""
    errado = quadro_minimo()
    errado.loc[0, "selic_meta_fim"] = 1375.0
    with pytest.raises(Exception, match="selic_meta_fim|le"):
        MacroQuarterlySchema.validate(errado, lazy=True)


def test_schema_recusa_cambio_nao_positivo() -> None:
    """`usdbrl_fim > 0`: `0` seria "sem cotação" preenchido com zero (Anti-SPEC §10.1.4)."""
    errado = quadro_minimo()
    errado.loc[0, "usdbrl_fim"] = 0.0
    with pytest.raises(Exception, match="usdbrl_fim|gt"):
        MacroQuarterlySchema.validate(errado, lazy=True)


def test_vertice_extrapolado_nulo_e_coagido_para_false_e_nao_rejeitado() -> None:
    """Limitação **medida** do contrato: `coerce=True` transforma nulo booleano em `False`.

    `vertice_extrapolado` é `nullable=False`, mas o `coerce` do schema roda **antes** do check de
    nulidade: um `None` entra como `False`, e `False` quer dizer "nenhum vértice faltou" — o
    oposto da ausência. O schema, portanto, **não** é a guarda aqui; a guarda é o build, que sempre
    calcula a flag a partir dos quatro vértices (coberto por
    `test_acervo_vertice_extrapolado_acende_quando_falta_vertice`, em `tests/unit/`). Este teste
    existe para que a limitação fique registrada no lugar onde alguém a procuraria, em vez de ser
    redescoberta como bug.
    """
    com_nulo = quadro_minimo()
    com_nulo["vertice_extrapolado"] = pd.Series([None] * len(com_nulo), dtype="object")
    validado = MacroQuarterlySchema.validate(com_nulo, lazy=True)
    assert not validado["vertice_extrapolado"].any()


def test_schema_recusa_fonte_versao_nula() -> None:
    """Linha canônica sem `fonte_versao` não é rastreável (RF-047) — e não passa."""
    errado = quadro_minimo()
    errado["fonte_versao"] = pd.Series([None] * len(errado), dtype="object")
    with pytest.raises(Exception, match="fonte_versao|nullable"):
        MacroQuarterlySchema.validate(errado, lazy=True)


def procedencia_minima(**ajustes: object) -> pd.DataFrame:
    """Uma linha válida de `macro_quarterly_provenance`, com os ajustes pedidos."""
    base: dict[str, object] = {
        "quarter": [PRIMEIRO_TRIMESTRE],
        "column": ["ipca_12m"],
        "series_id": ["BCB_SGS_13522"],
        "source": ["BCB_SGS"],
        "vintage": [pd.Timestamp("2026-10-11")],
        "collected_at": [pd.Timestamp("2026-10-11 03:00:00")],
        "lag_adjusted": [LAG_ADJUSTED],
        "fonte_versao": ["0" * 64],
    }
    base.update({chave: [valor] for chave, valor in ajustes.items()})
    return pd.DataFrame(base)


def test_procedencia_minima_satisfaz_o_schema() -> None:
    """A linha de procedência mínima passa — é o contrato de `CONTRACTS.md §3.1`."""
    assert len(MacroQuarterlyProvenanceSchema.validate(procedencia_minima(), lazy=True)) == 1


def test_procedencia_aceita_vintage_nulo() -> None:
    """`vintage` nulo = série não revisável (igual a `raw_series`) — é legítimo."""
    MacroQuarterlyProvenanceSchema.validate(procedencia_minima(vintage=pd.NaT), lazy=True)


def test_procedencia_recusa_vintage_depois_da_coleta() -> None:
    """`vintage_nao_posterior_a_coleta`: não se conhece um valor antes de baixá-lo."""
    futuro = procedencia_minima(vintage=pd.Timestamp("2027-01-01"))
    with pytest.raises(Exception, match="vintage_nao_posterior_a_coleta"):
        MacroQuarterlyProvenanceSchema.validate(futuro, lazy=True)


def test_procedencia_recusa_coluna_que_nao_e_rastreavel() -> None:
    """`column` ∈ `COLUNAS_RASTREAVEIS`: procedência de `quarter_end` não existe nem faz sentido."""
    errado = procedencia_minima(column="quarter_end")
    with pytest.raises(Exception, match="column|isin"):
        MacroQuarterlyProvenanceSchema.validate(errado, lazy=True)


def test_procedencia_recusa_fonte_fora_do_enum() -> None:
    """`source` é o mesmo enum de 15 fontes de `raw_series` — "Bloomberg" não entra."""
    errado = procedencia_minima(source="BLOOMBERG")
    with pytest.raises(Exception, match="source|isin"):
        MacroQuarterlyProvenanceSchema.validate(errado, lazy=True)


def test_procedencia_recusa_pk_repetida() -> None:
    """PK `(quarter, column)`: duas procedências para a mesma célula é ambiguidade, não dado."""
    duplicada = pd.concat([procedencia_minima(), procedencia_minima()], ignore_index=True)
    with pytest.raises(Exception, match="unique|quarter"):
        MacroQuarterlyProvenanceSchema.validate(duplicada, lazy=True)


# ═════════════════════════════════════════════════════════════════════════════
# B — o dicionário de colunas: bijeção com o schema, unidade e motivo declarados
# ═════════════════════════════════════════════════════════════════════════════


def test_origens_cobre_exatamente_as_colunas_rastreaveis() -> None:
    """Bijeção: coluna nova no schema **tem** de ganhar fórmula e origem, ou o teste quebra."""
    assert set(ORIGENS) == set(COLUNAS_RASTREAVEIS)
    assert len(ORIGENS) == 37


@pytest.mark.parametrize("coluna", sorted(ORIGENS))
def test_cada_coluna_declara_formula_unidade_e_fonte_ou_motivo(coluna: str) -> None:
    """Cada linha do dicionário é completa: fórmula, unidade conhecida e (fonte **ou** motivo)."""
    origem = ORIGENS[coluna]
    assert origem.formula.strip(), f"{coluna}: sem fórmula declarada"
    assert origem.unidade in UNIDADES_ESPERADAS, f"{coluna}: unidade {origem.unidade!r} estranha"
    if origem.series_id is None:
        assert origem.motivo_ausencia, f"{coluna}: sem fonte e sem motivo — isso é um buraco"
    else:
        assert origem.series_id in CATALOGO, (
            f"{coluna}: `{origem.series_id}` não existe em series_catalog (CA-120)"
        )


def test_unidades_sao_derivadas_do_dicionario_e_nao_digitadas_duas_vezes() -> None:
    """`UNIDADES` é projeção de `ORIGENS`: uma unidade só pode ser mudada num lugar."""
    assert {nome: origem.unidade for nome, origem in ORIGENS.items()} == UNIDADES
    assert set(UNIDADES) == set(COLUNAS_RASTREAVEIS)


def test_nenhuma_unidade_e_fracao() -> None:
    """A tabela é em por cento/pp. Fração no meio seria o erro de escala de 100x do §15.5.

    O consumidor que precisa de fração (F-017, `ret_real`) divide por 100 — e a regra está
    publicada em `relatorio_macro.json → unidades`, não deduzida do código.
    """
    assert "ratio" not in set(UNIDADES.values())
    assert UNIDADES["ipca_tri"] == "%"
    assert UNIDADES["selic_meta_delta"] == "pp"


def test_colunas_de_curva_apontam_para_series_de_f016() -> None:
    """As 7 colunas de curva + a flag vêm das 11 séries de F-016, e de nenhuma outra."""
    de_curva = {
        nome
        for nome, origem in ORIGENS.items()
        if origem.series_id is not None and origem.series_id in SERIES_DA_CURVA
    }
    assert de_curva == {
        "curva_real_1a",
        "curva_real_5a",
        "curva_nominal_1a",
        "curva_nominal_5a",
        "inclinacao_real_5a_1a",
        "inclinacao_nominal_5a_1a",
        "breakeven_5a",
        "vertice_extrapolado",
    }
    assert {sid for _, sid in VERTICES_PUBLICADOS} <= set(SERIES_DA_CURVA)
    assert VERTICE_ANCORA in SERIES_DA_CURVA


def test_series_do_focus_resolvem_em_entrada_do_catalogo() -> None:
    """CA-120 no Focus: o `series_id` materializado não está no catálogo, o EntitySet está.

    É a convenção que F-010 documentou para F-015 ("o catálogo registra a fonte, não a série"), e é
    por isso que a procedência aponta para `FOCUS_ANUAIS`/`FOCUS_INFLACAO_12M`.
    """
    for subserie, entrada in CATALOGO_DO_FOCUS.items():
        assert subserie not in CATALOGO, f"{subserie} entrou no catálogo: reveja a procedência"
        assert entrada in CATALOGO, f"{entrada} não existe em series_catalog"
        assert str(CATALOGO[entrada].fonte) in FONTES_VALIDAS


def test_colunas_acumuladas_vem_de_serie_de_frequencia_nativa_mais_fina() -> None:
    """Acumulação exige granularidade nativa: mensal para o IPCA, diária para CDI e Selic."""
    esperado: Mapping[str, str] = {"BCB_SGS_433": "M", "BCB_SGS_12": "D", "BCB_SGS_11": "D"}
    for coluna, series_id in ACUMULADAS.items():
        assert ORIGENS[coluna].series_id == series_id
        assert str(CATALOGO[series_id].freq) == esperado[series_id]


def test_materializacao_declarada_e_revised() -> None:
    """Esta feature produz **só** `revised`; `asof` é F-018 e tem `lag_adjusted=True`."""
    assert MATERIALIZACAO == "revised"
    assert LAG_ADJUSTED is False


# ═════════════════════════════════════════════════════════════════════════════
# C — acervo real: CA-120 por anti-join, CA-059/060/061 no artefato publicado
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
    """Os dois Parquets de F-015 existem nesta máquina?"""
    return (
        not ignorar_data_real()
        and caminho_canonical(NOME_MACRO).is_file()
        and caminho_canonical(NOME_PROVENANCE).is_file()
    )


acervo = pytest.mark.skipif(
    not acervo_disponivel(),
    reason=(
        f"acervo ausente (ou {VAR_IGNORAR_DATA} ligada): rode "
        f"`uv run python -m apps.pipeline.canonical.macro_quarterly --offline`"
    ),
)


@pytest.fixture(scope="module")
def macro() -> pd.DataFrame:
    """`macro_quarterly.parquet` publicado, validado pelo schema."""
    return MacroQuarterlySchema.validate(pd.read_parquet(caminho_canonical(NOME_MACRO)), lazy=True)


@pytest.fixture(scope="module")
def provenance() -> pd.DataFrame:
    """`macro_quarterly_provenance.parquet` publicado, validado pelo schema."""
    return MacroQuarterlyProvenanceSchema.validate(
        pd.read_parquet(caminho_canonical(NOME_PROVENANCE)), lazy=True
    )


@acervo
def test_acervo_tem_83_linhas_de_2006q1_a_2026q3(macro: pd.DataFrame) -> None:
    """CA-059 no artefato publicado: 83 trimestres, em ordem, sem repetir nem faltar."""
    assert len(macro) == N_TRIMESTRES_JANELA
    assert list(macro["quarter"]) == list(quarters_da_janela())
    assert macro["quarter"].iloc[0] == PRIMEIRO_TRIMESTRE
    assert macro["quarter"].iloc[-1] == ULTIMO_TRIMESTRE


@acervo
def test_acervo_is_estimated_so_no_trimestre_corrente(macro: pd.DataFrame) -> None:
    """CA-060: `2026Q3` é a **única** linha marcada, e o que falta nela é nulo, não estimado."""
    marcadas = sorted(macro.loc[macro["is_estimated"], "quarter"])
    assert marcadas == [ULTIMO_TRIMESTRE]


@acervo
def test_acervo_quarter_end_cai_no_trimestre_da_linha(macro: pd.DataFrame) -> None:
    """A chave de junção com `asset_returns_quarterly` é `quarter_end` — e ele pertence a `T`."""
    periodo = pd.DatetimeIndex(macro["quarter_end"]).to_period("Q").astype(str)
    assert list(periodo) == list(macro["quarter"])


@acervo
def test_acervo_ca120_toda_celula_rastreavel_tem_procedencia(
    macro: pd.DataFrame, provenance: pd.DataFrame
) -> None:
    """**CA-120 por anti-join:** célula não nula sem linha de procedência → conjunto vazio.

    A flag `vertice_extrapolado` conta como sempre preenchida (é booleana e não anulável), então
    ela tem de ter procedência nos 83 trimestres.
    """
    esperadas = {
        (quarter, coluna)
        for coluna in COLUNAS_RASTREAVEIS
        for quarter, valor in zip(macro["quarter"], macro[coluna], strict=True)
        if coluna == "vertice_extrapolado" or pd.notna(valor)
    }
    presentes = set(zip(provenance["quarter"], provenance["column"], strict=True))
    assert not (esperadas - presentes), f"{len(esperadas - presentes)} célula(s) sem procedência"
    assert not (presentes - esperadas), (
        f"{len(presentes - esperadas)} procedência(s) para célula nula — procedência de nulo é "
        f"afirmação sobre dado que não existe"
    )


@acervo
def test_acervo_procedencia_resolve_no_catalogo(provenance: pd.DataFrame) -> None:
    """CA-120: todo `series_id` da procedência existe em `series_catalog` (que carrega a URL)."""
    desconhecidas = sorted(set(provenance["series_id"]) - set(CATALOGO))
    assert not desconhecidas, f"series_id fora do catálogo: {desconhecidas}"


@acervo
def test_acervo_procedencia_bate_com_o_dicionario_de_colunas(provenance: pd.DataFrame) -> None:
    """A `series_id` gravada é a que `ORIGENS` declara — exceto a flag, que aponta a ausência."""
    for coluna, grupo in provenance.groupby("column"):
        declarada = ORIGENS[str(coluna)].series_id
        if coluna == "vertice_extrapolado":
            assert set(grupo["series_id"]) <= set(SERIES_DA_CURVA)
            continue
        assert set(grupo["series_id"]) == {declarada}, coluna


@acervo
def test_acervo_procedencia_e_homogenea_na_materializacao(provenance: pd.DataFrame) -> None:
    """A procedência pertence a **uma** materialização, e é a mesma da tabela wide."""
    assert bool(provenance["lag_adjusted"].eq(LAG_ADJUSTED).all())
    assert bool(provenance["fonte_versao"].eq(provenance["fonte_versao"].iloc[0]).all())


@acervo
def test_acervo_coluna_sem_fonte_e_nula_em_todos_os_83(macro: pd.DataFrame) -> None:
    """CA-061: coluna cuja fonte não existe hoje é **100% nula** — nunca meia coluna."""
    for coluna, origem in ORIGENS.items():
        if origem.series_id is not None:
            continue
        assert macro[coluna].isna().all(), (
            f"{coluna} tem valor sem fonte declarada: de onde veio? (CA-120)"
        )


@acervo
def test_acervo_relatorio_declara_motivo_de_cada_coluna_com_nulo(macro: pd.DataFrame) -> None:
    """Todo nulo publicado tem motivo no relatório — é o que torna a lacuna auditável."""
    import json

    relatorio = json.loads(caminho_canonical(NOME_RELATORIO).read_text(encoding="utf-8"))
    bloco = relatorio["nulos_por_coluna"]
    assert set(bloco) == set(COLUNAS_RASTREAVEIS)
    for coluna, detalhe in bloco.items():
        if detalhe["nulos"] == 0:
            continue
        assert detalhe["motivo"], f"{coluna}: {detalhe['nulos']} nulos sem motivo declarado"
    assert relatorio["macro_quarterly"]["linhas"] == len(macro)
    assert relatorio["diff_vs_alinhado_trimestral"]["divergencias"] == 0
