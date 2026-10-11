"""F-013 — o build de `raw_series` + `series_catalog` (CA-053..058, CA-075..077, CA-120).

Três camadas de teste, nesta ordem:

1. **Sobre mini-Parquet gerados em `tmp_path`** (seção A): cada guarda do build recebe o caso que
   ela existe para pegar, e um caso de controle que tem de passar. As fixturas são **derivadas do
   próprio catálogo** (`load_catalog()`), nunca digitadas: assim `source`/`freq`/`unit` da fixture
   não podem divergir do contrato sem o teste quebrar. Nada é commitado — ver
   `tests/fixtures/canonical/README.md`.
2. **Build de ponta a ponta em `tmp_path`** (seção B): reconstrução completa, idempotência por
   `sha256` e a view do DuckDB conferida contra o pandas.
3. **Sobre o `data/processed/` real** (seção C): o que nenhuma fixture pode responder — as 51
   séries em disco entram no canônico **idênticas linha a linha** à origem, e os 3 valores-canário
   sobrevivem à consolidação. `data/` é reconstruível e fica fora do git, então sem Parquet a
   seção **pula** (é o mesmo padrão de `test_processed_layer_conventions.py`; o marker
   `integration` não existe em `pyproject.toml` e `--strict-markers` recusaria inventá-lo).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

pa = pytest.importorskip("pandera")
pd = pytest.importorskip("pandas")

from apps.pipeline.canonical.build_raw_series import (  # noqa: E402
    COLUNAS_OBSERVADAS,
    COLUNAS_RAW_SERIES,
    MODULOS_DO_BUILD,
    NOME_CATALOGO,
    NOME_DUCKDB,
    NOME_RAW_SERIES,
    NOME_RELATORIO,
    PK_RAW_SERIES,
    TABELAS_FORA_DO_RAW_SERIES,
    FrequenciaNaoNativa,
    ProcedenciaNaoResolvida,
    caminhos_dos_componentes,
    carregar_processed,
    consolidar,
    construir,
    descobrir_parquets_de_serie,
    exigir_series,
    materializar_catalogo,
    validar_frequencia_nativa,
    validar_procedencia,
    validar_sem_mistura_de_fontes,
    versao_build,
)
from apps.pipeline.common import caminho_camada  # noqa: E402
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente  # noqa: E402
from apps.pipeline.common.io_layers import Camada  # noqa: E402
from packages.shared.schemas import load_catalog  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator

    from packages.shared.schemas import SeriesCatalogEntry

CATALOGO = load_catalog()
POR_ID: dict[str, Any] = {e.series_id: e for e in CATALOGO}

#: Séries reais do catálogo usadas nas fixturas, uma por frequência que o build trata.
SERIE_D = "B3_IBOV"
SERIE_M = "BCB_SGS_433"
SERIE_Q = "BCB_SGS_22109"
SERIE_A_CONFIRMAR = "MSCI_BRAZIL"

COLETA = pd.Timestamp("2026-10-10 20:30:00")
VINTAGE = pd.Timestamp("2026-10-10")

COMO_GERAR = "rode `python -m apps.pipeline.extract.<fonte> --offline` (ou sem --offline, com rede)"


# ─────────────────────────────────────────────────────────────────────────────
# Fixturas mínimas, derivadas do catálogo
# ─────────────────────────────────────────────────────────────────────────────


def _entrada(series_id: str) -> SeriesCatalogEntry:
    entrada = POR_ID.get(series_id)
    assert entrada is not None, f"{series_id} saiu do catálogo — ajuste a fixture, não o teste"
    return entrada


def mini_serie(
    series_id: str,
    datas: list[str],
    valores: list[float | None],
    *,
    vintage: pd.Timestamp = VINTAGE,
    coleta: pd.Timestamp = COLETA,
    source: str | None = None,
    freq: str | None = None,
) -> pd.DataFrame:
    """Mini `processed_series` de uma série **real** do catálogo, nas 8 colunas e nessa ordem.

    `source`/`freq` só são passados quando o teste quer justamente divergir do catálogo — é assim
    que os casos negativos ficam distinguíveis de um erro de digitação na fixture.
    """
    entrada = _entrada(series_id)
    assert len(datas) == len(valores)
    return pd.DataFrame(
        {
            "series_id": series_id,
            "date": pd.to_datetime(datas),
            "value": pd.array(valores, dtype="float64"),
            "source": source or entrada.fonte.value,
            "freq": freq or entrada.freq.value,
            "vintage": vintage,
            "unit": entrada.unit.value,
            "collected_at": coleta,
        }
    )[list(COLUNAS_RAW_SERIES)]


def _mini_focus(entityset: str, series_id: str) -> pd.DataFrame:
    """Fatia do Focus como F-010 a grava: `processed_series` **válida**, com `series_id` composto.

    O EntitySet (`FOCUS_ANUAIS`, …) está no catálogo; o `series_id` composto
    (`FOCUS_A_IPCA_H0`, …) **não** — é justamente o que exige a exclusão de D-k.
    """
    return mini_serie(entityset, ["2006-01-02", "2006-01-03"], [4.5, 4.6]).assign(
        series_id=series_id
    )


def painel_de_controle() -> pd.DataFrame:
    """Três séries válidas (D, M, Q) — o controle sem o qual um teste de rejeição não prova nada."""
    return pd.concat(
        [
            mini_serie(
                SERIE_D, ["2006-01-02", "2006-01-03", "2006-02-01"], [36000.0, 36100.0, 38484.84]
            ),
            mini_serie(SERIE_M, ["2026-08-31", "2026-09-30"], [-0.32, 0.82]),
            mini_serie(SERIE_Q, ["2026-03-31", "2026-06-30"], [100.0, 101.0]),
        ],
        ignore_index=True,
    )


def _gravar_mini_processed(base: Path, quadros: dict[str, pd.DataFrame]) -> Path:
    """Escreve `<base>/data/processed/<subpasta>/<nome>.parquet` e devolve `data/processed/`."""
    destino = base / "data" / "processed"
    for relativo, quadro in quadros.items():
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        quadro.to_parquet(alvo, index=False)
    return destino


@pytest.fixture
def registros_do_build() -> Iterator[list[str]]:
    """Mensagens de `pipeline.build_raw_series`, capturadas no próprio logger do módulo.

    Não uso `caplog`: `configurar_logging()` põe `propagate = False` no logger `pipeline`, e um
    teste anterior que chame o CLI deixaria o `caplog` (que escuta a raiz) cego — exatamente o
    tipo de evidência silenciosa que `logging_setup.py` existe para evitar.
    """
    import logging

    mensagens: list[str] = []

    class _Captura(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            mensagens.append(record.getMessage())

    logger = logging.getLogger("pipeline.build_raw_series")
    handler = _Captura(level=logging.INFO)
    nivel_anterior = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield mensagens
    finally:
        logger.removeHandler(handler)
        logger.setLevel(nivel_anterior)


@pytest.fixture
def processed_minimo(tmp_path: Path) -> Path:
    """`data/processed/` sintético com 3 séries + as 7 tabelas que o build tem de ignorar.

    As 5 de `focus/` são `processed_series` **válidas** (D-k): o que as exclui não é o schema, e
    sim o `series_id` composto que não resolve no catálogo — por isso entram aqui como série de
    verdade, com `series_id` de Focus, e não como quadro de 3 colunas.
    """
    nao_serie = pd.DataFrame(
        {"data": pd.to_datetime(["2006-01-02"]), "dia_util": [True], "fonte": ["ANBIMA_WEB"]}
    )
    focus = {
        f"focus/{entityset}.parquet": _mini_focus(entityset, series_id)
        for entityset, series_id in (
            ("FOCUS_ANUAIS", "FOCUS_A_IPCA_H0"),
            ("FOCUS_MENSAIS", "FOCUS_M_IPCA_H0"),
            ("FOCUS_TRIMESTRAIS", "FOCUS_Q_PIB_TOTAL_H0"),
            ("FOCUS_SELIC", "FOCUS_RCOPOM_SELIC_R1-2007"),
            ("FOCUS_INFLACAO_12M", "FOCUS_I12_IPCA_N"),
        )
    }
    _gravar_mini_processed(
        tmp_path,
        {
            **focus,
            "b3/B3_IBOV.parquet": mini_serie(
                SERIE_D, ["2006-01-02", "2006-01-03", "2006-02-01"], [36000.0, 36100.0, 38484.84]
            ),
            "sgs/BCB_SGS_433.parquet": mini_serie(
                SERIE_M, ["2026-08-31", "2026-09-30"], [-0.32, 0.82]
            ),
            "sgs/BCB_SGS_22109.parquet": mini_serie(
                SERIE_Q, ["2026-03-31", "2026-06-30"], [100.0, 101.0]
            ),
            "calendario/dias_uteis_anbima.parquet": nao_serie,
            "tesouro-direto/td_painel.parquet": nao_serie,
        },
    )
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# Seção A — guardas, uma a uma
# ─────────────────────────────────────────────────────────────────────────────


def test_controle_painel_valido_passa_em_todas_as_guardas() -> None:
    """Controle: sem ele, uma rejeição não distingue "a guarda pegou" de "a fixture é inválida"."""
    raw = consolidar(painel_de_controle())
    validar_procedencia(raw, CATALOGO)
    validar_frequencia_nativa(raw, CATALOGO)
    validar_sem_mistura_de_fontes(raw)
    assert tuple(raw.columns) == COLUNAS_RAW_SERIES
    assert len(raw) == 7


def test_descoberta_exclui_calendario_painel_do_tesouro_e_focus(processed_minimo: Path) -> None:
    """As 7 tabelas fora do canônico ficam fora, **com motivo registrado** (não em silêncio).

    O calendário sai por **schema** (não é série de valores); o painel do Tesouro e as 5 fatias do
    Focus saem por **catálogo** — `series_id` composto que não resolve em `series_catalog` (D-k).
    """
    alvos, excluidas = descobrir_parquets_de_serie(
        raiz_processed=processed_minimo / "data" / "processed"
    )
    # Ordem = `sorted()` do caminho POSIX (b3/ < calendario/ < sgs/ < tesouro-direto/), o que torna
    # a lista de insumos — e o Parquet que sai dela — independente da ordem do sistema de arquivos.
    assert [a.name for a in alvos] == [
        "B3_IBOV.parquet",
        "BCB_SGS_22109.parquet",
        "BCB_SGS_433.parquet",
    ]
    assert {e.arquivo for e in excluidas} == set(TABELAS_FORA_DO_RAW_SERIES)
    assert all(len(e.motivo) > 40 for e in excluidas), "motivo da exclusão tem de ser auditável"


def test_processed_sem_pasta_devolve_bloqueado_fonte_indisponivel(tmp_path: Path) -> None:
    """Sem insumo não se inventa canônico vazio (Anti-SPEC §10.1.1)."""
    with pytest.raises(FonteIndisponivel, match="BLOQUEADO — FONTE INDISPONÍVEL"):
        descobrir_parquets_de_serie(raiz_processed=tmp_path / "nao-existe")


def test_parquet_que_nao_e_processed_series_derruba_a_carga(tmp_path: Path) -> None:
    """Portão de entrada: `ProcessedSeriesSchema` por arquivo, com o nome do culpado no erro."""
    destino = _gravar_mini_processed(
        tmp_path, {"sgs/intruso.parquet": pd.DataFrame({"foo": [1], "bar": ["x"]})}
    )
    with pytest.raises(SerieInconsistente, match="intruso.parquet"):
        carregar_processed([destino / "sgs" / "intruso.parquet"])


def test_duas_extracoes_coexistem_como_vintages_distintos() -> None:
    """CA-056: mesma série, mesma data, safras diferentes → 2 linhas e PK intacta."""
    hoje = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    amanha = mini_serie(
        SERIE_M,
        ["2026-09-30"],
        [0.84],
        vintage=pd.Timestamp("2026-10-11"),
        coleta=pd.Timestamp("2026-10-11 20:30:00"),
    )
    raw = consolidar(pd.concat([hoje, amanha], ignore_index=True))
    assert len(raw) == 2
    assert not raw.duplicated(subset=list(PK_RAW_SERIES)).any()
    assert sorted(raw["value"]) == [0.82, 0.84]


def test_duplicata_identica_na_pk_e_removida_sem_perder_valor() -> None:
    """Reexportar o mesmo ponto duas vezes é idempotente, não erro."""
    uma = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    raw = consolidar(pd.concat([uma, uma], ignore_index=True))
    assert len(raw) == 1
    assert raw["value"].iloc[0] == 0.82


def test_pk_repetida_com_valor_divergente_falha_ruidosamente() -> None:
    """Validation Mode §7: escolher uma das duas em silêncio esconderia revisão de fonte."""
    uma = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    outra = mini_serie(SERIE_M, ["2026-09-30"], [0.91])
    with pytest.raises(SerieInconsistente, match="divergente"):
        consolidar(pd.concat([uma, outra], ignore_index=True))


# ── P1-3/P2-1 (QA da Onda 2): o dedup não pode cegar as guardas nem contar errado ───


def test_pk_repetida_com_mesmo_value_e_source_divergente_levanta() -> None:
    """P1-3: o furo medido pelo QA — mesma PK, mesmo `value`, `source` diferente **passava**.

    Duas defesas hoje: `consolidar` mede divergência nas 8 colunas, e
    `validar_sem_mistura_de_fontes` roda no concatenado, antes de qualquer `drop_duplicates`.
    O terceiro `assert` mostra por que a ordem importa: sobre o quadro já deduplicado por PK a
    guarda de CA-077 **passa**, porque a linha que provava a mistura não existe mais.
    """
    real = mini_serie(SERIE_D, ["2006-01-02"], [36000.0])
    enxertada = real.copy()
    enxertada["source"] = "YAHOO"
    bruto = pd.concat([real, enxertada], ignore_index=True)

    cego = bruto.drop_duplicates(subset=list(PK_RAW_SERIES), keep="first")
    validar_sem_mistura_de_fontes(cego)  # evidência apagada: era o cenário Anti-SPEC §10.3.19

    with pytest.raises(SerieInconsistente, match="mais de um `source`"):
        validar_sem_mistura_de_fontes(bruto)
    with pytest.raises(SerieInconsistente, match="divergente"):
        consolidar(bruto)


@pytest.mark.parametrize("coluna", ["unit", "freq", "collected_at"])
def test_pk_repetida_com_qualquer_coluna_divergente_levanta(coluna: str) -> None:
    """Mesma data, mesmo número, escala/frequência/safra outra é conflito, não repetição."""
    uma = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    outra = uma.copy()
    outra[coluna] = {"unit": "index", "freq": "Q", "collected_at": pd.Timestamp("2026-10-11")}[
        coluna
    ]
    with pytest.raises(SerieInconsistente, match="divergente"):
        consolidar(pd.concat([uma, outra], ignore_index=True))


def test_pk_repetida_com_value_nulo_contra_preenchido_levanta() -> None:
    """`value=0.82` vs. `NaN` na mesma PK: o nulo não pode ser absorvido pelo dedup."""
    preenchida = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    vazia = mini_serie(SERIE_M, ["2026-09-30"], [None])
    with pytest.raises(SerieInconsistente, match="divergente"):
        consolidar(pd.concat([preenchida, vazia], ignore_index=True))


def test_tres_copias_identicas_removem_duas_e_logam_duas(
    registros_do_build: list[str],
) -> None:
    """P2-1: `int(duplicadas.sum()) // 2` logava 1 para 3 cópias. Agora loga as 2 removidas."""
    uma = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    raw = consolidar(pd.concat([uma, uma, uma], ignore_index=True))
    assert len(raw) == 1
    assert raw["value"].iloc[0] == 0.82
    assert [m for m in registros_do_build if "dedup" in m] == [
        "dedup: 2 linha(s) idêntica(s) na PK removida(s)"
    ]


def test_sem_duplicata_nao_loga_dedup(registros_do_build: list[str]) -> None:
    """Controle: sem duplicata não há linha de dedup no log (nem `0 linha(s)`)."""
    consolidar(painel_de_controle())
    assert [m for m in registros_do_build if "dedup" in m] == []


def test_ordenacao_e_deterministica_independente_da_ordem_de_entrada() -> None:
    """Dois embaralhamentos da mesma entrada produzem o **mesmo** DataFrame — base do hash igual."""
    painel = painel_de_controle()
    a = consolidar(painel.sample(frac=1.0, random_state=1).reset_index(drop=True))
    b = consolidar(painel.sample(frac=1.0, random_state=7).reset_index(drop=True))
    pd.testing.assert_frame_equal(a, b)
    assert a["series_id"].is_monotonic_increasing


# ── CA-058: frequência nativa ───────────────────────────────────────────────


def test_serie_mensal_reamostrada_para_trimestral_e_rejeitada() -> None:
    """CA-058, o caso literal do CA: IPCA mensal gravado como `Q` — data não é fim de tri."""
    reamostrada = mini_serie(
        SERIE_M, ["2026-07-31", "2026-08-31", "2026-09-30"], [0.07, -0.32, 0.82], freq="Q"
    )
    with pytest.raises(FrequenciaNaoNativa, match="freq="):
        validar_frequencia_nativa(consolidar(reamostrada), CATALOGO)


def test_serie_trimestral_espalhada_em_datas_mensais_e_rejeitada() -> None:
    """O inverso: série `Q` com 3 pontos dentro do mesmo trimestre civil."""
    espalhada = mini_serie(
        SERIE_Q, ["2026-04-30", "2026-05-31", "2026-06-30"], [100.0, 100.5, 101.0]
    )
    with pytest.raises(FrequenciaNaoNativa):
        validar_frequencia_nativa(consolidar(espalhada), CATALOGO)


def test_freq_diferente_da_nativa_declarada_no_catalogo_e_rejeitada() -> None:
    """Série diária do catálogo gravada como mensal — mesmo com datas em fim de mês."""
    trocada = mini_serie(SERIE_D, ["2026-08-31", "2026-09-30"], [130000.0, 131000.0], freq="M")
    with pytest.raises(FrequenciaNaoNativa, match="nativa declarada"):
        validar_frequencia_nativa(consolidar(trocada), CATALOGO)


def test_duas_freqs_na_mesma_serie_e_rejeitado() -> None:
    """Série que muda de frequência no meio é erro de extrator, não dado."""
    misturada = pd.concat(
        [
            mini_serie(SERIE_M, ["2026-08-31"], [-0.32]),
            mini_serie(SERIE_M, ["2026-09-30"], [0.82], freq="Q"),
        ],
        ignore_index=True,
    )
    with pytest.raises(FrequenciaNaoNativa, match="freq na mesma série"):
        validar_frequencia_nativa(consolidar(misturada), CATALOGO)


def test_date_de_serie_mensal_fora_do_fim_de_periodo_e_rejeitada() -> None:
    """D-a: o 1º dia do mês que a API do SGS devolve não pode chegar ao canônico."""
    primeiro_dia = mini_serie(SERIE_M, ["2026-09-01"], [0.82])
    with pytest.raises(FrequenciaNaoNativa, match="fim de período"):
        validar_frequencia_nativa(consolidar(primeiro_dia), CATALOGO)


# ── CA-054/055/120: procedência ─────────────────────────────────────────────


def test_series_id_fora_do_catalogo_e_rejeitado() -> None:
    """CA-055/CA-120: toda linha resolve para uma URL do catálogo, ou não entra."""
    orfa = mini_serie(SERIE_D, ["2006-01-02"], [36000.0])
    orfa["series_id"] = "SERIE_QUE_NAO_EXISTE"
    with pytest.raises(ProcedenciaNaoResolvida, match="sem entrada no series_catalog"):
        validar_procedencia(consolidar(orfa), CATALOGO)


def test_source_divergente_do_catalogo_e_rejeitado() -> None:
    """`source` da linha tem de ser a `fonte` do catálogo — senão a URL de procedência mente."""
    trocada = mini_serie(SERIE_D, ["2006-01-02"], [36000.0], source="YAHOO")
    with pytest.raises(ProcedenciaNaoResolvida, match="source="):
        validar_procedencia(consolidar(trocada), CATALOGO)


def test_unit_divergente_do_catalogo_e_rejeitado() -> None:
    """Escala trocada é o erro silencioso clássico: `%` lido como `index` passa pelo pandera."""
    trocada = mini_serie(SERIE_M, ["2026-09-30"], [0.82])
    trocada["unit"] = "index"
    with pytest.raises(ProcedenciaNaoResolvida, match="unit="):
        validar_procedencia(consolidar(trocada), CATALOGO)


def test_serie_a_confirmar_nao_entra_no_canonico() -> None:
    """CA-054: identificador não confirmado pela pesquisa fica fora do caminho crítico."""
    assert _entrada(SERIE_A_CONFIRMAR).status.value == "a_confirmar"
    suspeita = mini_serie(SERIE_A_CONFIRMAR, ["2006-01-31"], [100.0])
    with pytest.raises(ProcedenciaNaoResolvida, match="a_confirmar"):
        validar_procedencia(consolidar(suspeita), CATALOGO)


def test_mistura_de_fontes_na_mesma_serie_e_rejeitada() -> None:
    """CA-077: real + sintético no mesmo `series_id` → duas `source`, e isso falha."""
    real = mini_serie(SERIE_M, ["2026-08-31"], [-0.32])
    enxertada = mini_serie(SERIE_M, ["2026-09-30"], [0.82], source="MANUAL")
    with pytest.raises(SerieInconsistente, match="mais de um `source`"):
        validar_sem_mistura_de_fontes(pd.concat([real, enxertada], ignore_index=True))


def test_serie_derivada_com_series_id_proprio_e_aceita() -> None:
    """CA-077, o outro lado: `DERIVADO` é legítimo **porque** tem `series_id` próprio (D-d)."""
    derivada = mini_serie("SP500_BRL", ["2026-10-09"], [1.0])
    assert _entrada("SP500_BRL").fonte.value == "DERIVADO"
    raw = consolidar(pd.concat([painel_de_controle(), derivada], ignore_index=True))
    validar_procedencia(raw, CATALOGO)
    validar_sem_mistura_de_fontes(raw)


# ── CA-076: lacuna sem substituto ───────────────────────────────────────────


def test_exigir_serie_ausente_devolve_bloqueado_fonte_indisponivel() -> None:
    """CA-076: a ausência para o pipeline; não vira lacuna preenchida."""
    raw = consolidar(painel_de_controle())
    with pytest.raises(FonteIndisponivel, match="BLOQUEADO — FONTE INDISPONÍVEL"):
        exigir_series(raw, CATALOGO, ["FOCUS_ANUAIS", "CURVA_REAL_5A"])


def test_exigir_serie_presente_nao_levanta() -> None:
    """Controle da guarda acima."""
    exigir_series(consolidar(painel_de_controle()), CATALOGO, [SERIE_D, SERIE_M])


# ── CA-053: catálogo materializado ──────────────────────────────────────────


def test_catalogo_materializado_tem_as_138_entradas_e_as_6_colunas_observadas() -> None:
    """CA-053: o catálogo materializado é o catálogo **inteiro**, não só o que veio."""
    tabela = materializar_catalogo(CATALOGO, consolidar(painel_de_controle()))
    assert len(tabela) == len(CATALOGO) == 138  # 134 + as 4 de D-i (F-016, vértice de 3 anos)
    for coluna in COLUNAS_OBSERVADAS:
        assert coluna in tabela.columns
    assert int(tabela["presente_no_processed"].sum()) == 3
    assert tabela["series_id"].is_unique


def test_catalogo_materializado_mede_janela_nulos_e_cobertura_do_observado() -> None:
    """As 6 colunas vêm do dado, não do declarado."""
    raw = consolidar(
        pd.concat(
            [
                mini_serie(SERIE_M, ["2026-07-31", "2026-08-31", "2026-09-30"], [0.07, None, 0.82]),
                mini_serie(SERIE_D, ["2010-12-30"], [100.0]),
            ],
            ignore_index=True,
        )
    )
    tabela = materializar_catalogo(CATALOGO, raw).set_index("series_id")
    mensal = tabela.loc[SERIE_M]
    assert mensal["n_obs"] == 3
    assert mensal["pct_nulos"] == pytest.approx(100 / 3)
    assert mensal["data_inicio_observada"] == pd.Timestamp("2026-07-31")
    assert mensal["data_fim_observada"] == pd.Timestamp("2026-09-30")
    assert bool(mensal["cobre_1t2006"]) is False
    tardia = tabela.loc[SERIE_D]
    assert bool(tardia["cobre_1t2006"]) is False, "início em 2010 não cobre 1T2006"


def test_catalogo_materializado_nao_herda_janela_declarada_para_serie_ausente() -> None:
    """A guarda `ausente_nao_tem_observacao`: `data_inicio` declarado ≠ observado."""
    tabela = materializar_catalogo(CATALOGO, consolidar(painel_de_controle()))
    ausentes = tabela[~tabela["presente_no_processed"]]
    assert len(ausentes) == 135  # 131 + as 4 de D-i, que este painel de controle não traz
    assert ausentes["data_inicio_observada"].isna().all()
    assert (ausentes["n_obs"] == 0).all()
    assert (~ausentes["cobre_1t2006"]).all()
    # ... e o declarado continua lá, lado a lado, porque a divergência é informação.
    assert ausentes["data_inicio"].notna().any()


# ─────────────────────────────────────────────────────────────────────────────
# Seção B — build de ponta a ponta em tmp_path
# ─────────────────────────────────────────────────────────────────────────────


def _sha256(caminho: Path) -> str:
    import hashlib

    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def test_build_completo_grava_os_quatro_artefatos(processed_minimo: Path) -> None:
    """Reconstrução completa a partir de zero: 2 Parquet + relatório + DuckDB."""
    resultado = construir(
        raiz=processed_minimo, raiz_processed=processed_minimo / "data" / "processed"
    )
    canonical = processed_minimo / "data" / "canonical"
    assert (canonical / NOME_RAW_SERIES).is_file()
    assert (canonical / NOME_CATALOGO).is_file()
    assert (canonical / NOME_RELATORIO).is_file()
    assert (canonical / NOME_DUCKDB).is_file()

    relatorio = json.loads((canonical / NOME_RELATORIO).read_text(encoding="utf-8"))
    assert relatorio["raw_series"]["linhas"] == 7
    assert relatorio["raw_series"]["series"] == 3
    assert relatorio["raw_series"]["sha256"] == _sha256(canonical / NOME_RAW_SERIES)
    assert relatorio["series_catalog"]["sha256"] == _sha256(canonical / NOME_CATALOGO)
    assert relatorio["series_catalog"]["linhas"] == 138  # D-i: 134 + 4 (F-016)
    assert len(relatorio["tabelas_excluidas"]) == len(TABELAS_FORA_DO_RAW_SERIES) == 7
    assert len(relatorio["series"]) == 3
    assert len(relatorio["versao_build"]) == 64
    assert relatorio["linhas_dedup"] == 0
    assert resultado.relatorio == relatorio


# ── P1-1 (QA da Onda 2): `versao_build` não pode ser cego ao catálogo ───────


def _copiar_componentes(destino: Path) -> list[Path]:
    """Cópias dos `MODULOS_DO_BUILD` em `tmp_path`, com o mesmo nome de arquivo."""
    destino.mkdir(parents=True, exist_ok=True)
    copias: list[Path] = []
    for origem in caminhos_dos_componentes():
        copia = destino / origem.name
        copia.write_bytes(origem.read_bytes())
        copias.append(copia)
    return copias


def test_versao_build_hasheia_o_conjunto_e_nao_depende_do_caminho(tmp_path: Path) -> None:
    """Controle do hash de conjunto: cópias byte-idênticas dão a **mesma** versão."""
    assert len(caminhos_dos_componentes()) == len(MODULOS_DO_BUILD) == 4
    assert versao_build(_copiar_componentes(tmp_path / "copia")) == versao_build()


def test_versao_build_muda_quando_o_catalogo_de_dados_muda(tmp_path: Path) -> None:
    """P1-1: editar `series_catalog_data.py` mudava o artefato **sem** mudar `versao_build`.

    Era a causa de um materializado publicado obsoleto passar por reproduzível. O catálogo entra
    no conjunto hasheado, então qualquer edição nele move a versão.
    """
    copias = _copiar_componentes(tmp_path / "copia")
    catalogo = next(c for c in copias if c.name == "series_catalog_data.py")
    catalogo.write_bytes(catalogo.read_bytes() + b"\n# is_total_return=False no YAHOO_GSPC\n")
    assert versao_build(copias) != versao_build()


@pytest.mark.parametrize("modulo", ["raw_series.py", "series_catalog.py"])
def test_versao_build_muda_quando_um_schema_do_portao_muda(tmp_path: Path, modulo: str) -> None:
    """Os dois schemas que servem de portão também determinam o Parquet."""
    copias = _copiar_componentes(tmp_path / "copia")
    alvo = next(c for c in copias if c.name == modulo)
    alvo.write_bytes(alvo.read_bytes() + b"\n# coluna nova\n")
    assert versao_build(copias) != versao_build()


def test_relatorio_carrega_catalogo_sha256_e_os_componentes(processed_minimo: Path) -> None:
    """O diagnóstico de "artefato velho" tem de estar **no dado**, não só no código."""
    import hashlib

    resultado = construir(
        raiz=processed_minimo,
        raiz_processed=processed_minimo / "data" / "processed",
        com_duckdb=False,
    )
    arquivo_catalogo = next(
        c for c in caminhos_dos_componentes() if c.name == "series_catalog_data.py"
    )
    esperado = hashlib.sha256(arquivo_catalogo.read_bytes()).hexdigest()
    assert resultado.relatorio["catalogo_sha256"] == esperado
    assert resultado.relatorio["versao_build_componentes"] == list(MODULOS_DO_BUILD)


# ── P1-2 (QA da Onda 2): `calendario` chega ao materializado ────────────────


def test_materializado_publica_calendario_do_catalogo(processed_minimo: Path) -> None:
    """P1-2: `BCB_SGS_432` publica em dia corrido, e o consumidor do Parquet tem de saber.

    Lido **do Parquet gravado**, não do DataFrame em memória: o furo original era `strict=True`
    deixar a coluna fora do artefato mesmo com o campo presente no catálogo pydantic.
    """
    resultado = construir(
        raiz=processed_minimo,
        raiz_processed=processed_minimo / "data" / "processed",
        com_duckdb=False,
    )
    tabela = pd.read_parquet(resultado.caminho_catalogo).set_index("series_id")
    assert "calendario" in tabela.reset_index().columns
    assert tabela.loc["BCB_SGS_432", "calendario"] == "corrido"
    assert tabela.loc["BCB_SGS_11", "calendario"] == "dias_uteis"
    # Série não diária não declara calendário — e nulo continua nulo, não vira a string "None".
    assert pd.isna(tabela.loc[SERIE_M, "calendario"])
    assert pd.isna(tabela.loc[SERIE_Q, "calendario"])
    assert set(tabela["calendario"].dropna().unique()) <= {"dias_uteis", "corrido"}
    assert _entrada("BCB_SGS_432").calendario == "corrido"


# ── P1-3 (QA da Onda 2): o build inteiro recusa a substituição de fonte ─────


def test_build_recusa_mesma_pk_com_source_divergente_e_nao_grava(tmp_path: Path) -> None:
    """O cenário do QA ("BUILD PASSOU: 5 linhas, sources=['B3_API']") agora para o build."""
    original = mini_serie(SERIE_D, ["2006-01-02", "2006-01-03"], [36000.0, 36100.0])
    enxertado = original.copy()
    enxertado["source"] = "YAHOO"
    _gravar_mini_processed(
        tmp_path, {"b3/B3_IBOV.parquet": original, "yahoo/B3_IBOV.parquet": enxertado}
    )
    with pytest.raises((SerieInconsistente, ProcedenciaNaoResolvida)):
        construir(raiz=tmp_path, raiz_processed=tmp_path / "data" / "processed", com_duckdb=False)
    assert not (tmp_path / "data" / "canonical" / NOME_RAW_SERIES).exists()


def test_build_remove_duplicata_identica_entre_arquivos_e_registra_no_relatorio(
    tmp_path: Path,
) -> None:
    """P2-2: o dedup deixa rastro **no dado** (`linhas_dedup`), não só no `_log.info`."""
    serie = mini_serie(SERIE_M, ["2026-08-31", "2026-09-30"], [-0.32, 0.82])
    _gravar_mini_processed(
        tmp_path, {"sgs/BCB_SGS_433.parquet": serie, "sgs-reexport/BCB_SGS_433.parquet": serie}
    )
    resultado = construir(
        raiz=tmp_path, raiz_processed=tmp_path / "data" / "processed", com_duckdb=False
    )
    assert len(resultado.raw_series) == 2
    assert resultado.relatorio["linhas_dedup"] == 2


def test_build_e_idempotente_mesmo_sha256_em_duas_execucoes(processed_minimo: Path) -> None:
    """RF-048/CA-121: nada no build depende do relógio, então 2 rodadas dão o mesmo hash."""
    argumentos = {
        "raiz": processed_minimo,
        "raiz_processed": processed_minimo / "data" / "processed",
    }
    primeiro = construir(**argumentos)
    hashes_1 = {
        nome: _sha256(primeiro.caminho_raw_series.parent / nome)
        for nome in (NOME_RAW_SERIES, NOME_CATALOGO, NOME_RELATORIO)
    }
    construir(**argumentos)
    hashes_2 = {
        nome: _sha256(primeiro.caminho_raw_series.parent / nome)
        for nome in (NOME_RAW_SERIES, NOME_CATALOGO, NOME_RELATORIO)
    }
    assert hashes_1 == hashes_2


def test_duckdb_derivado_responde_o_mesmo_que_o_pandas(processed_minimo: Path) -> None:
    """ADR-006 §(a).2: o DuckDB é view sobre o Parquet — divergir dele é impossível por desenho."""
    duckdb = pytest.importorskip("duckdb")
    resultado = construir(
        raiz=processed_minimo, raiz_processed=processed_minimo / "data" / "processed"
    )
    assert resultado.caminho_duckdb is not None
    conexao = duckdb.connect(str(resultado.caminho_duckdb), read_only=True)
    try:
        linhas = conexao.execute("SELECT count(*) FROM raw_series").fetchone()[0]
        series = conexao.execute("SELECT count(DISTINCT series_id) FROM raw_series").fetchone()[0]
        soma = conexao.execute(
            "SELECT sum(value) FROM raw_series WHERE series_id = ?", [SERIE_D]
        ).fetchone()[0]
        catalogo = conexao.execute("SELECT count(*) FROM series_catalog").fetchone()[0]
    finally:
        conexao.close()

    esperado = resultado.raw_series
    assert linhas == len(esperado)
    assert series == esperado["series_id"].nunique()
    assert soma == pytest.approx(
        float(esperado.loc[esperado["series_id"] == SERIE_D, "value"].sum())
    )
    assert catalogo == len(resultado.catalogo)


def test_build_sem_duckdb_nao_cria_o_arquivo(processed_minimo: Path) -> None:
    """O DuckDB é opcional por contrato (ADR-006): o canônico fecha sem ele."""
    resultado = construir(
        raiz=processed_minimo,
        raiz_processed=processed_minimo / "data" / "processed",
        com_duckdb=False,
    )
    assert resultado.caminho_duckdb is None
    assert not (processed_minimo / "data" / "canonical" / NOME_DUCKDB).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Seção C — sobre o data/processed/ real (pula sem dado)
# ─────────────────────────────────────────────────────────────────────────────


def _alvos_reais() -> list[Path]:
    base = caminho_camada(Camada.PROCESSED)
    if not base.is_dir():
        return []
    alvos, _ = descobrir_parquets_de_serie()
    return alvos


@pytest.fixture(scope="module")
def raw_real() -> pd.DataFrame:
    """`raw_series` reconstruído do `data/processed/` real, em memória (não grava nada)."""
    alvos = _alvos_reais()
    if len(alvos) < 40:
        pytest.skip(f"data/processed/ tem {len(alvos)} Parquet(s) de série — {COMO_GERAR}")
    return consolidar(carregar_processed(alvos))


def test_real_todas_as_guardas_passam_no_dado_em_disco(raw_real: pd.DataFrame) -> None:
    """O que nenhuma fixture prova: as 51 séries reais satisfazem as 4 invariantes."""
    validar_procedencia(raw_real, CATALOGO)
    validar_frequencia_nativa(raw_real, CATALOGO)
    validar_sem_mistura_de_fontes(raw_real)
    assert raw_real["series_id"].nunique() >= 51
    assert not raw_real.duplicated(subset=list(PK_RAW_SERIES)).any()


def test_real_cada_serie_e_identica_linha_a_linha_a_sua_origem(raw_real: pd.DataFrame) -> None:
    """**Diff numérico de F-013** (classe C): o canônico não transforma nada.

    Como esta é a 1ª versão do canônico, o diff é "vs. `data/processed/`": série por série, o
    recorte de `raw_series` tem de ser **igual, célula por célula**, ao Parquet de origem — mesma
    contagem, mesmos valores, mesma procedência. Qualquer agregação, `ffill` ou arredondamento
    acidental quebra aqui.
    """
    conferidas = 0
    for caminho in _alvos_reais():
        origem = pd.read_parquet(caminho)[list(COLUNAS_RAW_SERIES)]
        for series_id, grupo in origem.groupby("series_id"):
            esperado = (
                grupo.sort_values(list(PK_RAW_SERIES), kind="mergesort")
                .reset_index(drop=True)
                .astype({"value": "float64"})
            )
            obtido = (
                raw_real[raw_real["series_id"] == series_id]
                .sort_values(list(PK_RAW_SERIES), kind="mergesort")
                .reset_index(drop=True)
                .astype({"value": "float64"})
            )
            assert len(obtido) == len(esperado), f"{series_id}: {len(obtido)} != {len(esperado)}"
            pd.testing.assert_frame_equal(obtido, esperado, check_dtype=False, check_exact=True)
            conferidas += 1
    assert conferidas >= 51, f"só {conferidas} séries conferidas contra a origem"


@pytest.mark.parametrize(
    ("series_id", "quando", "esperado"),
    [
        ("ANBIMA_IMAB", "2003-09-16", 723.070317),
        ("B3_IBOV", "2006-02-01", 38484.84),
        ("BCB_SGS_433", "2026-09-30", 0.82),
    ],
)
def test_real_valores_canario_sobrevivem_a_consolidacao(
    raw_real: pd.DataFrame, series_id: str, quando: str, esperado: float
) -> None:
    """Os 3 canários de F-002/F-006/F-003, relidos **do canônico**, não da origem."""
    recorte = raw_real[
        (raw_real["series_id"] == series_id) & (raw_real["date"] == pd.Timestamp(quando))
    ]
    assert len(recorte) == 1, f"{series_id} em {quando}: {len(recorte)} linha(s)"
    assert float(recorte["value"].iloc[0]) == pytest.approx(esperado, abs=1e-9)
    assert recorte["unit"].iloc[0] == _entrada(series_id).unit.value


def test_real_catalogo_materializado_bate_com_o_observado(raw_real: pd.DataFrame) -> None:
    """O catálogo materializado não pode contar nada diferente do que `raw_series` tem."""
    tabela = materializar_catalogo(CATALOGO, raw_real)
    assert int(tabela["presente_no_processed"].sum()) == raw_real["series_id"].nunique()
    assert int(tabela["n_obs"].sum()) == len(raw_real)
    por_id = tabela.set_index("series_id")
    for series_id, grupo in raw_real.groupby("series_id"):
        linha = por_id.loc[str(series_id)]
        assert linha["n_obs"] == len(grupo)
        assert linha["data_inicio_observada"] == grupo["date"].min()
        assert linha["data_fim_observada"] == grupo["date"].max()
