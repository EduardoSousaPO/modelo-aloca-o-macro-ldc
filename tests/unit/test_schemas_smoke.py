"""Testes de fumaça dos contratos — o chão que o CI N1 precisa para não ser vácuo.

Antes destes testes, `pytest tests/unit` saía com **exit 5** (`no tests ran`), que o GitHub Actions
trata como falha: o gate "uma onda só abre com a anterior verde" (`AGENTS.md §13`) era
intransponível por construção. Ver `docs/plans/AUDITORIA-HARNESS.md §F-7`.

Os testes aqui não são placeholders. Eles fecham as invariantes do catálogo que, se quebrarem,
quebram silenciosamente toda métrica calculada sobre `status = ok`:

- o catálogo **carrega** (`N_SERIES_ESPERADAS` entradas, `series_id` únicos);
- nenhuma entrada `ok` carrega o identificador placeholder `a_confirmar` (CA-054);
- nenhuma série **FRED** conta como usável no pacote mínimo, mesmo `ok`
  (`skills-manifest.md §3`: fonte bloqueada nesta máquina);
- os schemas pandera do canônico **importam** e expõem as colunas que a SPEC promete.

`pandera` não está instalado na máquina do Edu (`skills-manifest.md §2`), então os testes que
dependem dela usam `importorskip` — os de catálogo rodam de qualquer jeito, direto sobre os dicts.
"""

from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

#: Contagem exata do catálogo. Era **132** até 2026-10-10; **F-007** acrescentou as 2 séries
#: derivadas em BRL (`ACWI_BRL`, `SP500_BRL`, `fonte = DERIVADO`), levando a 134; **F-016**
#: acrescentou as 4 do vértice de 3 anos (`CURVA_REAL_3A`, `CURVA_NOMINAL_3A`,
#: `INCLINACAO_REAL_5A_3A`, `INCLINACAO_NOMINAL_5A_3A`, `fonte = DERIVADO`) por **D-i** —
#: decisão provisória do orquestrador de 2026-10-11, porque CA-025 (inclinação real em >= 95% dos
#: dias úteis de 2006-2026) **não fecha** com o vértice curto de 1 ano (60,53%) e fecha com o de
#: 3 anos (95,25%) —, levando a **138**.
#: ATENÇÃO (orquestrador): o número também é citado em `docs/contracts/CONTRACTS.md §2.1`,
#: no `README.md` e em `docs/plans/AUDITORIA-HARNESS.md` — arquivos do orquestrador durante a
#: onda (`AGENTS.md §8/§13`), que ficaram **sem** atualizar de propósito. Outra feature que
#: acrescente série ao catálogo vai mexer nesta mesma linha.
N_SERIES_ESPERADAS = 138
RAIZ = Path(__file__).resolve().parents[2]


def _carrega_dados_do_catalogo() -> tuple[dict[str, Any], ...]:
    """Carrega `series_catalog_data.py` **sem** passar por `__init__.py` (que importa pandera)."""
    caminho = RAIZ / "packages" / "shared" / "schemas" / "series_catalog_data.py"
    spec = importlib.util.spec_from_file_location("series_catalog_data_smoke", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return tuple(modulo.SERIES_CATALOG)


@pytest.fixture(scope="module")
def catalogo_dados() -> tuple[dict[str, Any], ...]:
    """O catálogo como dado bruto (lista de dicts), sem dependência de pandera."""
    return _carrega_dados_do_catalogo()


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo como dado — roda sem pandera
# ─────────────────────────────────────────────────────────────────────────────


def test_catalogo_tem_a_contagem_esperada(catalogo_dados: tuple[dict[str, Any], ...]) -> None:
    """A contagem é citada em `CONTRACTS.md §2.1`, no README e na auditoria — não pode derivar."""
    assert len(catalogo_dados) == N_SERIES_ESPERADAS


def test_series_id_unico(catalogo_dados: tuple[dict[str, Any], ...]) -> None:
    """`series_id` é PK de `series_catalog`; duplicata silenciosa duplicaria linha no canônico."""
    contagem = Counter(e["series_id"] for e in catalogo_dados)
    duplicados = sorted(sid for sid, n in contagem.items() if n > 1)
    assert duplicados == []


def test_toda_entrada_tem_campos_obrigatorios(catalogo_dados: tuple[dict[str, Any], ...]) -> None:
    """Sem `identificador`, `fonte` e `confianca` a série não é rastreável até a fonte."""
    obrigatorios = (
        "series_id",
        "nome",
        "item_email",
        "fonte",
        "identificador",
        "fonte_url",
        "freq",
        "unit",
        "confianca",
    )
    faltando = {
        e["series_id"]: [c for c in obrigatorios if not e.get(c)]
        for e in catalogo_dados
        if any(not e.get(c) for c in obrigatorios)
    }
    assert faltando == {}


def test_entrada_ok_nunca_tem_identificador_a_confirmar(
    catalogo_dados: tuple[dict[str, Any], ...],
) -> None:
    """CA-054: identificador placeholder exige `status = a_confirmar`. Nada de palpite como `ok`."""
    infratores = sorted(
        e["series_id"]
        for e in catalogo_dados
        if e.get("status", "ok") == "ok" and e["identificador"] == "a_confirmar"
    )
    assert infratores == []


def test_descontinuada_tem_data_fim(catalogo_dados: tuple[dict[str, Any], ...]) -> None:
    """Série morta sem `data_fim` vira emenda silenciosa de fontes no alinhamento trimestral."""
    infratores = sorted(
        e["series_id"]
        for e in catalogo_dados
        if e.get("status") == "descontinuada" and not e.get("data_fim")
    )
    assert infratores == []


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo validado pelos contratos pydantic (precisa de pandera: o módulo
# `series_catalog` define também um DataFrameModel)
# ─────────────────────────────────────────────────────────────────────────────


def test_load_catalog_valida_todas_as_entradas() -> None:
    """`load_catalog()` é o portão de entrada do pipeline: tem de passar em todas de hoje."""
    pytest.importorskip("pandera")
    from packages.shared.schemas.series_catalog import load_catalog, resumo_catalogo

    catalogo = load_catalog()
    assert len(catalogo) == N_SERIES_ESPERADAS
    resumo = resumo_catalogo(catalogo)
    assert resumo["total"] == N_SERIES_ESPERADAS
    assert sum(resumo[s] for s in ("ok", "a_confirmar", "descontinuada", "descartada", "paga")) == (
        N_SERIES_ESPERADAS
    )


def test_fred_nunca_e_usavel_no_pacote_minimo() -> None:
    """P1-9 da auditoria: FRED está **bloqueado nesta máquina** (`skills-manifest.md §3`).

    As séries FRED têm identificador confirmado e seguem `status = ok` — o que é verdade sobre o
    identificador. Mas `usavel_no_pacote_minimo` responde outra pergunta ("dá para extrair até o
    Comitê?") e para FRED a resposta é não, em 3/3 tentativas medidas.
    """
    pytest.importorskip("pandera")
    from packages.shared.schemas.series_catalog import Fonte, StatusSerie, load_catalog

    catalogo = load_catalog()
    fred = [e for e in catalogo if e.fonte is Fonte.FRED]
    assert len(fred) == 13, "o catálogo deveria ter 13 séries FRED"
    assert any(e.status is StatusSerie.OK for e in fred), "o teste perde o sentido se nenhuma é ok"
    usaveis = sorted(e.series_id for e in fred if e.usavel_no_pacote_minimo)
    assert usaveis == []


def test_cobre_2006_usa_o_limiar_do_prd() -> None:
    """O limiar é `2006-01-31` (PRD §7), não o 1º dia útil de 2006 — ver C-2 da auditoria."""
    pytest.importorskip("pandera")
    from datetime import date

    from packages.shared.schemas.series_catalog import LIMIAR_COBERTURA_2006, load_catalog

    assert date(2006, 1, 31) == LIMIAR_COBERTURA_2006
    por_id = {e.series_id: e for e in load_catalog()}
    # DTWEXBGS começa em 02/01/2006 (pesquisa §C10): cobre, nos dois limiares.
    assert por_id["FRED_DTWEXBGS"].cobre_2006 is True
    # IFIX começa em 30/12/2010: não cobre, e isso é fato da fonte, não da métrica.
    assert por_id["B3_IFIX"].cobre_2006 is False
    # Início não medido devolve None — "não medido" nunca é "não cobre".
    assert por_id["BCB_SGS_11"].cobre_2006 is None


@pytest.mark.xfail(
    strict=False,
    reason="C-2 da auditoria: 17 séries `ok` seguem sem `data_inicio` medido na pesquisa. "
    "Enquanto isso, a métrica de cobertura do PRD §7 é incalculável para elas. Falha "
    "declarada (não silenciada) para que o número apareça no CI sem bloquear a onda; "
    "fecha quando a pesquisa medir os inícios (ver docs/wiki/log.md 2026-10-10).",
)
def test_toda_serie_ok_tem_data_inicio_medido() -> None:
    """Lista, no log do CI, exatamente quais séries `ok` ainda não têm início medido."""
    pytest.importorskip("pandera")
    from packages.shared.schemas.series_catalog import StatusSerie, load_catalog

    sem_inicio = sorted(
        e.series_id for e in load_catalog() if e.status is StatusSerie.OK and e.data_inicio is None
    )
    assert sem_inicio == [], f"{len(sem_inicio)} séries `ok` sem data_inicio: {sem_inicio}"


# ─────────────────────────────────────────────────────────────────────────────
# Schemas do canônico — só importam com pandera
# ─────────────────────────────────────────────────────────────────────────────


def test_schemas_do_canonico_importam() -> None:
    """Se o import do pacote quebra, nenhuma feature de Onda 1+ roda (P0-2 da auditoria)."""
    pytest.importorskip("pandera")
    from packages.shared.schemas import (
        AssetReturnsQuarterlySchema,
        MacroQuarterlyProvenanceSchema,
        MacroQuarterlySchema,
        RegimeNeighborsSchema,
        RegimesSchema,
    )

    for schema in (
        MacroQuarterlySchema,
        MacroQuarterlyProvenanceSchema,
        AssetReturnsQuarterlySchema,
        RegimesSchema,
        RegimeNeighborsSchema,
    ):
        assert schema.to_schema().columns, f"{schema.__name__} sem colunas"


def test_macro_quarterly_tem_a_janela_e_as_colunas_de_auditoria() -> None:
    """CA-059/CA-072: 83 trimestres declarados e as 3 colunas de auditoria presentes."""
    pytest.importorskip("pandera")
    from packages.shared.schemas.macro_quarterly import (
        N_TRIMESTRES_JANELA,
        PRIMEIRO_TRIMESTRE,
        ULTIMO_TRIMESTRE,
        MacroQuarterlySchema,
    )

    assert (N_TRIMESTRES_JANELA, PRIMEIRO_TRIMESTRE, ULTIMO_TRIMESTRE) == (83, "2006Q1", "2026Q3")
    colunas = MacroQuarterlySchema.to_schema().columns
    assert {"is_estimated", "lag_adjusted", "fonte_versao"} <= set(colunas)


def test_provenance_cobre_as_colunas_rastreaveis_de_macro_quarterly() -> None:
    """CA-120: toda coluna de variável de `macro_quarterly` é endereçável na tabela companheira."""
    pytest.importorskip("pandera")
    from packages.shared.schemas.macro_quarterly import (
        COLUNAS_RASTREAVEIS,
        COLUNAS_SEM_PROCEDENCIA,
        MacroQuarterlyProvenanceSchema,
        MacroQuarterlySchema,
    )

    colunas_wide = set(MacroQuarterlySchema.to_schema().columns)
    assert set(COLUNAS_RASTREAVEIS) == colunas_wide - set(COLUNAS_SEM_PROCEDENCIA)
    assert "ipca_12m" in COLUNAS_RASTREAVEIS
    assert "quarter" not in COLUNAS_RASTREAVEIS

    prov = MacroQuarterlyProvenanceSchema.to_schema().columns
    assert {"series_id", "source", "vintage", "collected_at"} <= set(prov)
