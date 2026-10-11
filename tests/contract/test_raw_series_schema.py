"""Contratos de `raw_series` e do `series_catalog` materializado — o portão pandera (RF-026).

Este arquivo testa **o schema**, não o build: cada caso constrói o DataFrame mínimo que passa
inteiro e mexe **um** valor por vez, que é a única forma de provar que o check pega o caso em vez
de o docstring prometer que pega (mesmo método de `tests/unit/test_canonical_guards.py`).

O primeiro diretório de testes `tests/contract/` do projeto nasce aqui. A nota de F-002 no
`TODO.md` registrou que "não existe `tests/contract/`" porque, para um **extrator**, o contrato
vivo é o teste `@pytest.mark.network` contra a fonte. Para a **camada canônica** é diferente: o
contrato é o schema pandera, roda sem rede e tem de rodar no CI N2 separado do teste de unidade —
é o `pytest tests/contract -m "not network"` do `AGENTS.md §6`.

Cobre: CA-053, CA-054, CA-056, CA-057, CA-075, CA-077, CA-120 (parte de schema) e as 3 guardas
novas de `SeriesCatalogMaterializedSchema`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pa = pytest.importorskip("pandera")
pd = pytest.importorskip("pandas")

from apps.pipeline.canonical.build_raw_series import (  # noqa: E402
    COLUNAS_RAW_SERIES,
    NOME_RAW_SERIES,
    _gravar_parquet_validado,
    materializar_catalogo,
)
from packages.shared.schemas import (  # noqa: E402
    LIMIAR_COBERTURA_2006,
    RawSeriesSchema,
    SeriesCatalogMaterializedSchema,
    StatusSerie,
    load_catalog,
)
from packages.shared.schemas.series_catalog import IDENTIFICADOR_A_CONFIRMAR  # noqa: E402

CATALOGO = load_catalog()
N_SERIES_CATALOGO = 134
"""O número vivo está em `tests/unit/test_schemas_smoke.py`; aqui é a âncora do materializado."""


def _linha(**sobrescreve: Any) -> dict[str, Any]:
    """Linha válida de `raw_series`. Só o que o teste quer quebrar vem por `sobrescreve`."""
    base: dict[str, Any] = {
        "series_id": "BCB_SGS_433",
        "date": pd.Timestamp("2026-09-30"),
        "value": 0.82,
        "source": "BCB_SGS",
        "freq": "M",
        "vintage": pd.Timestamp("2026-10-10"),
        "unit": "%",
        "collected_at": pd.Timestamp("2026-10-10 20:30:00"),
    }
    base.update(sobrescreve)
    return base


def _quadro(*linhas: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(list(linhas) or [_linha()])[list(COLUNAS_RAW_SERIES)]


# ─────────────────────────────────────────────────────────────────────────────
# RawSeriesSchema
# ─────────────────────────────────────────────────────────────────────────────


def test_linha_de_referencia_e_valida() -> None:
    """Controle: sem ele, uma rejeição não distingue a causa da falha."""
    RawSeriesSchema.validate(_quadro())


def test_linha_sem_source_e_rejeitada() -> None:
    """CA-057: `source` é `nullable=False` — linha sem origem não existe no canônico."""
    with pytest.raises(pa.errors.SchemaError):
        RawSeriesSchema.validate(_quadro(_linha(source=None)))


def test_linha_sem_series_id_e_rejeitada() -> None:
    """CA-057, o outro identificador obrigatório."""
    with pytest.raises(pa.errors.SchemaError):
        RawSeriesSchema.validate(_quadro(_linha(series_id=None)))


def test_coluna_de_origem_ausente_e_rejeitada() -> None:
    """CA-075: DataFrame canônico **sem** a coluna de origem nem chega à escrita."""
    sem_source = _quadro().drop(columns=["source"])
    with pytest.raises(pa.errors.SchemaError):
        RawSeriesSchema.validate(sem_source)


def test_coluna_ad_hoc_e_rejeitada() -> None:
    """Anti-SPEC §10.4.24 + `strict=True`: nenhuma coluna fora de `packages/shared/schemas/`."""
    com_extra = _quadro().assign(comentario_do_analista="ajustei na mão")
    # `strict=True` reporta coluna extra como `SchemaErrors` (plural), diferente de coluna
    # **faltando**, que vem como `SchemaError` — daí os dois tipos na expectativa.
    with pytest.raises((pa.errors.SchemaError, pa.errors.SchemaErrors)):
        RawSeriesSchema.validate(com_extra)


def test_source_fora_do_enum_de_fontes_e_rejeitado() -> None:
    """Fonte inventada (ou "SINTETICO") não entra: o enum tem 15 valores e é o contrato."""
    with pytest.raises(pa.errors.SchemaError):
        RawSeriesSchema.validate(_quadro(_linha(source="SINTETICO")))


def test_date_posterior_a_collected_at_e_rejeitada() -> None:
    """Check `sem_data_futura` — o caso real da meta Selic com data no futuro (CA-013)."""
    futura = _linha(date=pd.Timestamp("2027-01-31"))
    with pytest.raises(pa.errors.SchemaError):
        RawSeriesSchema.validate(_quadro(futura))


def test_value_nulo_e_aceito() -> None:
    """Feriado e mês sem divulgação são `NULL` legítimo — nunca `0` (Anti-SPEC §10.1.4)."""
    RawSeriesSchema.validate(_quadro(_linha(value=None)))


def test_duas_extracoes_coexistem_como_vintages_distintos() -> None:
    """CA-056: a PK é `(series_id, date, vintage)`, então a 2ª safra **não** viola nada."""
    RawSeriesSchema.validate(
        _quadro(
            _linha(),
            _linha(
                value=0.84,
                vintage=pd.Timestamp("2026-10-11"),
                collected_at=pd.Timestamp("2026-10-11 20:30:00"),
            ),
        )
    )


def test_pk_duplicada_e_rejeitada() -> None:
    """A mesma safra do mesmo ponto duas vezes viola `unique=['series_id','date','vintage']`."""
    with pytest.raises(pa.errors.SchemaError):
        RawSeriesSchema.validate(_quadro(_linha(), _linha(value=0.91)))


def test_nada_e_gravado_quando_o_portao_recusa(tmp_path: Path) -> None:
    """A ordem do portão: valida **e só então** escreve. Recusado ⇒ zero rastro em disco."""
    with pytest.raises(pa.errors.SchemaErrors):
        _gravar_parquet_validado(
            _quadro().drop(columns=["source"]),
            nome=NOME_RAW_SERIES,
            schema=RawSeriesSchema,
            raiz=tmp_path,
        )
    assert not (tmp_path / "data" / "canonical" / NOME_RAW_SERIES).exists()


def test_gravacao_valida_devolve_sha256_do_arquivo(tmp_path: Path) -> None:
    """Controle do portão + o `sha256` que vai para o `relatorio_build.json`."""
    import hashlib

    destino, digest, tamanho = _gravar_parquet_validado(
        _quadro(), nome=NOME_RAW_SERIES, schema=RawSeriesSchema, raiz=tmp_path
    )
    corpo = destino.read_bytes()
    assert digest == hashlib.sha256(corpo).hexdigest()
    assert tamanho == len(corpo)


# ─────────────────────────────────────────────────────────────────────────────
# series_catalog — CA-053 / CA-054
# ─────────────────────────────────────────────────────────────────────────────


def test_catalogo_valida_e_nenhum_identificador_e_vazio() -> None:
    """CA-053: 134 entradas, nenhuma com identificador vazio, todas com `confianca`."""
    assert len(CATALOGO) == N_SERIES_CATALOGO
    for entrada in CATALOGO:
        assert entrada.identificador.strip() not in {"", "-", "?", "TODO"}
        assert entrada.confianca.value in {"CONFIRMADO", "CONFIRMADO_SUB", "NAO_VERIFICADO"}


def test_identificador_a_confirmar_implica_status_a_confirmar() -> None:
    """CA-054: o placeholder legítimo é a string literal, e arrasta o status."""
    for entrada in CATALOGO:
        if entrada.identificador == IDENTIFICADOR_A_CONFIRMAR:
            assert entrada.status is StatusSerie.A_CONFIRMAR, entrada.series_id


def test_identificador_vazio_e_recusado_pelo_pydantic() -> None:
    """O negativo de CA-053: o validator recusa placeholder silencioso."""
    pydantic = pytest.importorskip("pydantic")
    modelo = CATALOGO[0].model_dump()
    modelo["identificador"] = "-"
    with pytest.raises(pydantic.ValidationError):
        load_catalog([modelo])


def test_series_id_duplicado_e_recusado() -> None:
    """`load_catalog()` é o portão: catálogo com chave repetida não carrega."""
    modelo = CATALOGO[0].model_dump()
    with pytest.raises(ValueError, match="duplicado"):
        load_catalog([modelo, dict(modelo)])


# ─────────────────────────────────────────────────────────────────────────────
# SeriesCatalogMaterializedSchema — as 3 guardas novas
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def catalogo_materializado() -> pd.DataFrame:
    """Catálogo materializado com **uma** série observada — o mínimo que exercita as 3 guardas."""
    raw = _quadro(
        _linha(date=pd.Timestamp("2006-01-31"), value=0.59),
        _linha(date=pd.Timestamp("2026-09-30"), value=0.82),
    )
    return materializar_catalogo(CATALOGO, raw)


def test_materializado_de_referencia_e_valido(catalogo_materializado: pd.DataFrame) -> None:
    """Controle + CA-053 no formato tabular: as 134 entradas passam pelo schema novo."""
    validado = SeriesCatalogMaterializedSchema.validate(catalogo_materializado, lazy=True)
    assert len(validado) == N_SERIES_CATALOGO
    assert int(validado["presente_no_processed"].sum()) == 1
    assert int(validado["n_obs"].sum()) == 2


def test_materializado_herda_as_19_colunas_do_catalogo_declarado(
    catalogo_materializado: pd.DataFrame,
) -> None:
    """O subtipo **acrescenta**: nenhuma coluna do catálogo declarado desapareceu."""
    declaradas = {
        "series_id",
        "nome",
        "item_email",
        "fonte",
        "identificador",
        "fonte_url",
        "freq",
        "data_inicio",
        "data_fim",
        "unit",
        "transformacao_padrao",
        "lag_divulgacao_dias",
        "confianca",
        "status",
        "is_total_return",
        "janela_rolante",
        "fonte_instavel",
        "licenca_restrita",
        "obs",
    }
    assert declaradas <= set(catalogo_materializado.columns)


def test_serie_ausente_com_janela_observada_e_rejeitada(
    catalogo_materializado: pd.DataFrame,
) -> None:
    """Guarda `ausente_nao_tem_observacao`: copiar `data_inicio` declarado para o observado falha.

    É o modo de falha mais fácil desta tabela — e o que faria o relatório afirmar que uma série
    sem extrator rodado "cobre 1T2006" (Anti-SPEC §10.1.2).
    """
    adulterado = catalogo_materializado.copy()
    alvo = adulterado.index[~adulterado["presente_no_processed"]][0]
    adulterado.loc[alvo, "data_inicio_observada"] = pd.Timestamp("2006-01-02")
    with pytest.raises(pa.errors.SchemaErrors):
        SeriesCatalogMaterializedSchema.validate(adulterado, lazy=True)


def test_serie_ausente_com_n_obs_positivo_e_rejeitada(
    catalogo_materializado: pd.DataFrame,
) -> None:
    """Mesma guarda, pelo outro campo: contagem sem dado é número inventado."""
    adulterado = catalogo_materializado.copy()
    alvo = adulterado.index[~adulterado["presente_no_processed"]][0]
    adulterado.loc[alvo, "n_obs"] = 10
    with pytest.raises(pa.errors.SchemaErrors):
        SeriesCatalogMaterializedSchema.validate(adulterado, lazy=True)


def test_cobre_1t2006_nao_pode_divergir_do_inicio_observado(
    catalogo_materializado: pd.DataFrame,
) -> None:
    """Guarda `cobre_1t2006_derivado_do_observado`: a coluna é derivada, nunca digitada."""
    adulterado = catalogo_materializado.copy()
    alvo = adulterado.index[adulterado["presente_no_processed"]][0]
    assert bool(adulterado.loc[alvo, "cobre_1t2006"]) is True
    adulterado.loc[alvo, "cobre_1t2006"] = False
    with pytest.raises(pa.errors.SchemaErrors):
        SeriesCatalogMaterializedSchema.validate(adulterado, lazy=True)


def test_limiar_de_cobertura_e_o_do_prd(catalogo_materializado: pd.DataFrame) -> None:
    """O limiar é **2006-01-31** (PRD §7), não o 1º dia útil de 2006."""
    assert LIMIAR_COBERTURA_2006.isoformat() == "2006-01-31"
    presente = catalogo_materializado[catalogo_materializado["presente_no_processed"]].iloc[0]
    assert presente["data_inicio_observada"] == pd.Timestamp("2006-01-31")
    assert bool(presente["cobre_1t2006"]) is True


def test_janela_observada_invertida_e_rejeitada(catalogo_materializado: pd.DataFrame) -> None:
    """Guarda `janela_observada_coerente`: `fim < inicio` é bug de agregação, não dado."""
    adulterado = catalogo_materializado.copy()
    alvo = adulterado.index[adulterado["presente_no_processed"]][0]
    adulterado.loc[alvo, "data_fim_observada"] = pd.Timestamp("2005-12-31")
    with pytest.raises(pa.errors.SchemaErrors):
        SeriesCatalogMaterializedSchema.validate(adulterado, lazy=True)


def test_pct_nulos_fora_de_0_100_e_rejeitado(catalogo_materializado: pd.DataFrame) -> None:
    """`pct_nulos` é percentual (0..100), não fração — trocar a escala falha no schema."""
    adulterado = catalogo_materializado.copy()
    alvo = adulterado.index[adulterado["presente_no_processed"]][0]
    adulterado.loc[alvo, "pct_nulos"] = 150.0
    with pytest.raises(pa.errors.SchemaErrors):
        SeriesCatalogMaterializedSchema.validate(adulterado, lazy=True)


def test_toda_serie_do_materializado_tem_fonte_url(
    catalogo_materializado: pd.DataFrame,
) -> None:
    """CA-055/CA-120 pelo lado do catálogo: a procedência resolve até a URL, para as 134."""
    assert catalogo_materializado["fonte_url"].notna().all()
    assert (catalogo_materializado["fonte_url"].str.len() >= 8).all()
