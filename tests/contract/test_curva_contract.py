"""F-016 — contrato das 11 séries de curva: `ProcessedSeriesSchema` + `series_catalog` + F-013.

Este arquivo responde a uma pergunta só: **as 11 séries que F-016 grava entram no `raw_series` de
F-013 sem nenhuma mudança naquele build?** Por isso ele não reimplementa validação: importa as
quatro guardas públicas de `apps/pipeline/canonical/build_raw_series.py` (CA-055/CA-120, CA-058,
CA-077, CA-076) e as roda sobre o que `data/processed/curva/` contém de verdade — gravado num
`tmp_path`, a partir do recorte real de `tests/fixtures/processed/`.

O que fica travado aqui:

- as 8 colunas de `ProcessedSeriesSchema`, nesta ordem, com `strict=True` (nada a mais entra);
- os 11 `series_id` **exatamente** como o catálogo os escreve, com `source=DERIVADO`, `freq=D` e a
  `unit` declarada (`%a.a.` nos vértices e no breakeven, `pp` nas inclinações);
- PK `(series_id, date, vintage)` única e `date <= collected_at`;
- `vintage`/`collected_at` **herdados do painel** (D-b): nenhuma linha nasce do relógio da rodada;
- `data/processed/curva/` **não** está na lista de tabelas que F-013 exclui — é o que garante que
  o próximo build do canônico absorve as 11 séries sem ninguém editar `build_raw_series.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from apps.pipeline.canonical import curva as C
from apps.pipeline.canonical.build_raw_series import (
    COLUNAS_RAW_SERIES,
    PK_RAW_SERIES,
    TABELAS_FORA_DO_RAW_SERIES,
    carregar_processed,
    consolidar,
    descobrir_parquets_de_serie,
    exigir_series,
    validar_frequencia_nativa,
    validar_procedencia,
    validar_sem_mistura_de_fontes,
)
from apps.pipeline.extract.tesouro_direto import NOME_PROCESSADO as NOME_PAINEL
from packages.shared.schemas import ProcessedSeriesSchema, load_catalog

if TYPE_CHECKING:
    from collections.abc import Iterator

PAINEL_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "processed" / NOME_PAINEL


@pytest.fixture(scope="module")
def gravado(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, C.ResultadoCurva]]:
    """Roda F-016 inteiro num `tmp_path` sobre o recorte real e devolve `(raiz, resultado)`.

    Sobre o **recorte versionado**, nunca sobre `data/processed/`: o contrato tem de ser
    verificável num `actions/checkout` limpo, que é onde o CI roda (P1-4 do QA da Onda 1).
    """
    raiz = tmp_path_factory.mktemp("curva_contract")
    destino = raiz / "data" / "processed" / NOME_PAINEL
    destino.parent.mkdir(parents=True)
    destino.write_bytes(PAINEL_FIXTURE.read_bytes())
    resultado = C.construir(raiz=raiz, caminho_painel=destino)
    yield raiz, resultado


@pytest.fixture(scope="module")
def series_em_disco(gravado: tuple[Path, C.ResultadoCurva]) -> dict[str, pd.DataFrame]:
    """As 11 séries **lidas de volta do Parquet** — não os DataFrames em memória."""
    raiz, resultado = gravado
    del raiz
    return {sid: pd.read_parquet(caminho) for sid, (caminho, _) in resultado.series.items()}


# ─────────────────────────────────────────────────────────────────────────────
# O schema e o catálogo
# ─────────────────────────────────────────────────────────────────────────────


def test_as_11_series_do_catalogo_foram_gravadas(series_em_disco: dict[str, pd.DataFrame]) -> None:
    """Nem uma série a mais, nem uma a menos — e os ids são os do `series_catalog`."""
    catalogo = {e.series_id for e in load_catalog()}

    assert set(series_em_disco) == {
        "CURVA_REAL_1A",
        "CURVA_REAL_3A",
        "CURVA_REAL_5A",
        "CURVA_NOMINAL_1A",
        "CURVA_NOMINAL_3A",
        "CURVA_NOMINAL_5A",
        "INCLINACAO_REAL_5A_3A",
        "INCLINACAO_NOMINAL_5A_3A",
        "INCLINACAO_REAL_5A_1A",
        "INCLINACAO_NOMINAL_5A_1A",
        "BREAKEVEN_5A",
    }
    assert set(series_em_disco) == set(C.SERIES_DE_F016)
    assert set(series_em_disco) <= catalogo


@pytest.mark.parametrize("series_id", C.SERIES_DE_F016)
def test_cada_serie_passa_o_processed_series_schema(
    series_id: str, series_em_disco: dict[str, pd.DataFrame]
) -> None:
    """O portão `data/processed/` → `data/canonical/` do `CONTRACTS.md §0`, série por série."""
    quadro = series_em_disco[series_id]

    validado = ProcessedSeriesSchema.validate(quadro, lazy=True)

    assert list(validado.columns) == list(COLUNAS_RAW_SERIES)
    assert len(validado) == len(quadro)


@pytest.mark.parametrize("series_id", C.SERIES_DE_F016)
def test_procedencia_de_cada_serie_casa_com_o_catalogo(
    series_id: str, series_em_disco: dict[str, pd.DataFrame]
) -> None:
    """`source`, `freq` e `unit` são os **declarados** no catálogo — não os convenientes."""
    entrada = {e.series_id: e for e in load_catalog()}[series_id]
    quadro = series_em_disco[series_id]

    assert set(quadro["source"]) == {"DERIVADO"} == {entrada.fonte.value}
    assert set(quadro["freq"]) == {"D"} == {entrada.freq.value}
    assert set(quadro["unit"]) == {entrada.unit.value}
    assert entrada.unit.value == ("pp" if series_id.startswith("INCLINACAO") else "%a.a.")
    assert entrada.status.value != "a_confirmar"


@pytest.mark.parametrize("series_id", C.SERIES_DE_F016)
def test_pk_unica_e_date_nunca_depois_de_collected_at(
    series_id: str, series_em_disco: dict[str, pd.DataFrame]
) -> None:
    """PK `(series_id, date, vintage)` e a guarda de data futura do schema, por série."""
    quadro = series_em_disco[series_id]

    assert not quadro.duplicated(subset=list(PK_RAW_SERIES)).any()
    assert (quadro["date"] <= quadro["collected_at"]).all()
    assert quadro["vintage"].notna().all()


def test_vintage_e_collected_at_sao_herdados_do_painel(
    gravado: tuple[Path, C.ResultadoCurva], series_em_disco: dict[str, pd.DataFrame]
) -> None:
    """D-b: a safra vem do painel do Tesouro, data base por data base — nunca do relógio."""
    raiz, _ = gravado
    painel = pd.read_parquet(raiz / "data" / "processed" / NOME_PAINEL)
    esperado = (
        painel.groupby("date", sort=True)
        .agg(vintage=("vintage", "max"), collected_at=("collected_at", "max"))
        .reset_index()
    )

    for series_id, quadro in series_em_disco.items():
        juntos = quadro.merge(esperado, on="date", suffixes=("", "_painel"))
        assert len(juntos) == len(quadro), series_id
        assert (juntos["vintage"] == juntos["vintage_painel"]).all(), series_id
        assert (juntos["collected_at"] == juntos["collected_at_painel"]).all(), series_id


def test_valor_nulo_e_o_unico_campo_que_pode_faltar(
    series_em_disco: dict[str, pd.DataFrame],
) -> None:
    """Ausência de vértice vira `value` nulo **declarado**; nenhuma outra coluna aceita nulo."""
    for series_id, quadro in series_em_disco.items():
        for coluna in COLUNAS_RAW_SERIES:
            if coluna == "value":
                continue
            assert quadro[coluna].notna().all(), f"{series_id}.{coluna}"


# ─────────────────────────────────────────────────────────────────────────────
# A integração com F-013 (sem tocar `build_raw_series.py`)
# ─────────────────────────────────────────────────────────────────────────────


def test_a_pasta_curva_nao_esta_na_lista_de_exclusao_de_f013() -> None:
    """`data/processed/curva/` é absorvida pelo build do canônico — é o contrato de integração.

    O calendário, o painel do Tesouro e as 5 fatias do Focus (D-k) estão **fora** de `raw_series`
    por motivo declarado; a curva, que é justamente a série canônica que nasce do painel, tem de
    estar **dentro**. O conjunto é afirmado **exato** de propósito: exclusão nova tem de passar
    por aqui.
    """
    excluidas = set(TABELAS_FORA_DO_RAW_SERIES)

    assert excluidas == {
        "calendario/dias_uteis_anbima.parquet",
        "tesouro-direto/td_painel.parquet",
        "focus/FOCUS_ANUAIS.parquet",
        "focus/FOCUS_MENSAIS.parquet",
        "focus/FOCUS_TRIMESTRAIS.parquet",
        "focus/FOCUS_SELIC.parquet",
        "focus/FOCUS_INFLACAO_12M.parquet",
    }
    for series_id in C.SERIES_DE_F016:
        assert C.nome_do_parquet(series_id) not in excluidas
        assert C.nome_do_parquet(series_id).startswith("curva/")


def test_as_11_series_sao_descobertas_pelo_build_do_canonico(
    gravado: tuple[Path, C.ResultadoCurva],
) -> None:
    """`descobrir_parquets_de_serie` acha as 11 e não confunde o painel com série do catálogo."""
    raiz, _ = gravado
    alvos, excluidas = descobrir_parquets_de_serie(raiz_processed=raiz / "data" / "processed")

    nomes = {caminho.stem for caminho in alvos}
    assert set(C.SERIES_DE_F016) <= nomes
    assert {t.arquivo for t in excluidas} == {"tesouro-direto/td_painel.parquet"}
    assert "relatorio_curva.json" not in {c.name for c in alvos}


def test_as_4_guardas_do_build_canonico_passam_na_curva(
    gravado: tuple[Path, C.ResultadoCurva],
) -> None:
    """As guardas de CA-055/CA-120, CA-058, CA-077 e CA-076, rodadas tal como F-013 as roda.

    É o teste que impede a feature de "passar no próprio contrato e quebrar o canônico": se um
    `unit`, um `source` ou a frequência nativa divergir do catálogo, é aqui que aparece — com o
    mesmo código que vai rodar no build.
    """
    raiz, _ = gravado
    alvos, _ = descobrir_parquets_de_serie(raiz_processed=raiz / "data" / "processed")
    da_curva = [c for c in alvos if c.parent.name == C.PASTA_CURVA]
    catalogo = load_catalog()

    quadro = consolidar(carregar_processed(da_curva))

    validar_procedencia(quadro, catalogo)
    validar_frequencia_nativa(quadro, catalogo)
    validar_sem_mistura_de_fontes(quadro)
    exigir_series(quadro, catalogo, C.SERIES_DE_F016)
    assert list(quadro.columns) == list(COLUNAS_RAW_SERIES)
    assert len(quadro) == len(C.SERIES_DE_F016) * quadro["date"].nunique()


def test_serie_exigida_e_ausente_bloqueia_em_vez_de_virar_lacuna(
    gravado: tuple[Path, C.ResultadoCurva],
) -> None:
    """CA-076 pelo avesso: pedir uma série que a curva não produz para o pipeline, não preenche.

    `TESOURO_TD_PRECOTAXA` existe no catálogo e é a **fonte** desta curva, mas não é uma das 11
    séries que F-016 grava — é o caso que mais se parece com um engano plausível.
    """
    raiz, _ = gravado
    alvos, _ = descobrir_parquets_de_serie(raiz_processed=raiz / "data" / "processed")
    quadro = consolidar(carregar_processed([c for c in alvos if c.parent.name == C.PASTA_CURVA]))

    with pytest.raises(Exception, match="FONTE INDISPONÍVEL"):
        exigir_series(quadro, load_catalog(), ["TESOURO_TD_PRECOTAXA"])


# ─────────────────────────────────────────────────────────────────────────────
# Negativos do contrato
# ─────────────────────────────────────────────────────────────────────────────


def test_conferir_catalogo_recusa_serie_fora_do_catalogo() -> None:
    """Série sem entrada no catálogo falha **antes** de gravar — nunca depois, no build.

    `CURVA_REAL_10A` é medida no relatório (`VERTICES_FORA_DO_CATALOGO`) e **não** tem entrada:
    é exatamente o que CA-055 proíbe de gravar, e o que esta guarda tem de pegar.
    """
    assert "CURVA_REAL_10A" in C.VERTICES_FORA_DO_CATALOGO
    with pytest.raises(C.CurvaInconsistente, match="sem entrada no series_catalog"):
        C.conferir_catalogo(["CURVA_REAL_10A"])


def test_unidade_trocada_entre_vertice_e_inclinacao_seria_pega_pelo_build(
    gravado: tuple[Path, C.ResultadoCurva],
) -> None:
    """Se a inclinação fosse gravada em `%a.a.` (em vez de `pp`), o build do canônico recusaria.

    É o teste de escala de `AGENTS.md §15.5`: `pp` e `%a.a.` são números parecidos e unidades
    diferentes, e trocá-las não muda nenhum valor — só o significado.
    """
    raiz, _ = gravado
    alvos, _ = descobrir_parquets_de_serie(raiz_processed=raiz / "data" / "processed")
    quadro = consolidar(carregar_processed([c for c in alvos if c.parent.name == C.PASTA_CURVA]))
    adulterado = quadro.copy()
    adulterado.loc[adulterado["series_id"] == C.SERIE_INCLINACAO_REAL, "unit"] = "%a.a."

    with pytest.raises(Exception, match="unit="):
        validar_procedencia(adulterado, load_catalog())


def test_relatorio_tem_cobertura_e_canarios(gravado: tuple[Path, C.ResultadoCurva]) -> None:
    """O JSON de `data/processed/curva/` carrega o que o Parquet de 8 colunas não pode."""
    import json

    raiz, resultado = gravado
    del raiz
    assert resultado.caminho_relatorio is not None
    relatorio = json.loads(resultado.caminho_relatorio.read_text(encoding="utf-8"))

    assert relatorio["metrica_taxa"] == "TAXA_VENDA"
    assert relatorio["metrica_prazo"] == "dias_corridos"
    assert set(relatorio["series"]) == set(C.SERIES_DE_F016)
    vertices = relatorio["cobertura_de_2006_em_diante"]["vertices"]
    assert vertices["CURVA_REAL_3A"]["no_catalogo"] is True
    assert vertices["CURVA_NOMINAL_10A"]["no_catalogo"] is False
    assert set(relatorio["cobertura_de_2006_em_diante"]["inclinacoes"]) == {
        "INCLINACAO_REAL_5A_1A",
        "INCLINACAO_REAL_5A_3A",
        "INCLINACAO_NOMINAL_5A_1A",
        "INCLINACAO_NOMINAL_5A_3A",
    }
    assert relatorio["canarios"]
    for serie in relatorio["series"].values():
        assert serie["sha256"]
        assert set(serie) >= {"n_linhas", "pct_nulos", "motivos", "pct_nulos_por_ano"}
