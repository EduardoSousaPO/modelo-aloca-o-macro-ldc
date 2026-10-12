"""Contrato das views web (F-W001) — pydantic ⇄ JSON emitido ⇄ `schema.d.ts`.

Este arquivo responde **uma** pergunta: *o que o portal importa como tipo descreve exatamente o que
o exportador grava?* Se a resposta falhar, o modo de falha é o pior possível — `undefined` numa
célula de tela, sem exceção em lugar nenhum.

A prova é em três elos, e cada elo é um bloco:

| # | Elo | Como é provado |
|---|---|---|
| 1 | **modelo ⇒ JSON**: o arquivo emitido valida contra o modelo, e `extra="forbid"`
garante que não há campo fora do contrato | `model_validate` sobre o arquivo gravado |
| 2 | **modelo ⇒ `.d.ts`**: toda interface existe e todo campo do modelo é campo da interface |
leitura do `.d.ts` gerado (`tipos_ts.campos_por_interface`) |
| 3 | **`.d.ts` ⇒ JSON**: as chaves de todo objeto emitido são campos da interface correspondente |
varredura recursiva do JSON contra o `.d.ts` |

1 + 2 + 3 fecham: `chaves(JSON) ⊆ campos(modelo) = campos(.d.ts)`, com igualdade nos campos
obrigatórios. Mais: `UNIDADE_POR_CAMPO` tem de cobrir **todo** campo numérico publicado (RF-W014 —
é o que impede o erro de 100×), e `SLOT_DA_VIEW` tem de cobrir as 6 views.

Os blocos 1-3 rodam sobre a canônica **sintética** de `tests/unit/test_web_export.py` (uma só
fixture para as duas suítes: duplicá-la criaria duas verdades sobre a forma do canônico) e **nunca
pulam**. O bloco 4 é o `Acervo`: os mesmos três elos sobre `data/canonical/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from apps.pipeline.canonical.regimes_v1 import status_adr_001
from apps.web_export import exportar as X
from apps.web_export import tipos_ts, views
from packages.shared.schemas.web_views import (
    CASAS_POR_UNIDADE,
    MODELOS_DO_CONTRATO,
    NOME_CURRENT,
    NOME_META,
    NOME_TIPOS_TS,
    SCHEMA_VERSAO,
    SLOT_DA_VIEW,
    UNIDADE_POR_CAMPO,
    VIEWS,
    MetaWeb,
    PonteiroCurrent,
)
from tests.unit.test_web_export import (  # noqa: F401 - a fixture é usada por nome
    TAG,
    acervo_real,
    canonical_sintetico,
    exportacao_real,
)

MODELO_POR_ARQUIVO: dict[str, type[BaseModel]] = {
    NOME_META: MetaWeb,
    NOME_CURRENT: PonteiroCurrent,
    **{f"{nome}.json": modelo for nome, modelo in VIEWS.items()},
}
"""De cada arquivo emitido para o modelo que o descreve. É o mapa que o `.d.ts` também imprime."""


@pytest.fixture
def exportacao_sintetica(canonical_sintetico: Path) -> X.ResultadoExportacao:  # noqa: F811
    """Uma exportação completa sobre a canônica sintética — sem rede, sem `data/`."""
    return X.exportar(
        tag=TAG, destino=canonical_sintetico / "data" / "web", raiz=canonical_sintetico
    )


def _arquivos(resultado: X.ResultadoExportacao) -> dict[str, Path]:
    caminhos = {nome: resultado.pasta_da_tag / nome for nome in MODELO_POR_ARQUIVO}
    caminhos[NOME_CURRENT] = resultado.destino / NOME_CURRENT
    return caminhos


def _ler(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))


# ═════════════════════════════════════════════════════════════════════════════
# 1 — modelo ⇒ JSON
# ═════════════════════════════════════════════════════════════════════════════


def test_todo_arquivo_emitido_valida_contra_o_seu_modelo(
    exportacao_sintetica: X.ResultadoExportacao,
) -> None:
    """Os 8 arquivos JSON validam. `extra="forbid"` faz disso uma prova de ausência de extra."""
    for nome, caminho in _arquivos(exportacao_sintetica).items():
        assert caminho.is_file(), nome
        MODELO_POR_ARQUIVO[nome].model_validate(_ler(caminho))


def test_campo_a_mais_na_view_e_reprovado(exportacao_sintetica: X.ResultadoExportacao) -> None:
    """A trava de RF-W015 em ação: coluna que não está no contrato levanta nomeando o campo."""
    corpo = _ler(exportacao_sintetica.pasta_da_tag / "heatmap_regime_ativo.json")
    corpo["coluna_inventada"] = 1
    with pytest.raises(ValidationError, match="coluna_inventada"):
        VIEWS["heatmap_regime_ativo"].model_validate(corpo)
    celulas = _ler(exportacao_sintetica.pasta_da_tag / "heatmap_regime_ativo.json")
    celulas["celulas"][0]["sharpe_tri"] = 0.1
    with pytest.raises(ValidationError, match="sharpe_tri"):
        VIEWS["heatmap_regime_ativo"].model_validate(celulas)


def test_campo_faltando_na_view_e_reprovado(exportacao_sintetica: X.ResultadoExportacao) -> None:
    """Campo ausente é erro, não `undefined`: nullable é `null` **explícito** (RF-W013)."""
    corpo = _ler(exportacao_sintetica.pasta_da_tag / "ranking_atual.json")
    del corpo["rankings"][0]["erro_padrao_media"]
    with pytest.raises(ValidationError, match="erro_padrao_media"):
        VIEWS["ranking_atual"].model_validate(corpo)


def test_toda_view_carrega_o_envelope_e_o_gate(
    exportacao_sintetica: X.ResultadoExportacao,
) -> None:
    """As 6 views têm `view`, `tela`, `pergunta`, `tag`, `dataset_sha256`, `gate` e `fontes`."""
    for nome in VIEWS:
        corpo = _ler(exportacao_sintetica.pasta_da_tag / f"{nome}.json")
        assert corpo["view"] == nome
        assert corpo["tela"] == views.TELA_POR_VIEW[nome]
        assert corpo["pergunta"].endswith("?"), "a tela abre com a PERGUNTA que responde (P7)"
        assert corpo["tag"] == exportacao_sintetica.tag
        assert corpo["dataset_sha256"] == exportacao_sintetica.dataset_sha256
        assert set(corpo["gate"]) == set(
            (
                "especificacao_congelada",
                "status_adr_001",
                "veredito_publicacao",
                "marca",
                "publicavel",
            )
        )
        assert corpo["fontes"], "toda view declara de que artefato saiu"
        assert set(corpo["fontes"]) <= set(views.ARTEFATOS_LIDOS) | {"MANIFEST.json"}


# ═════════════════════════════════════════════════════════════════════════════
# 2 — modelo ⇒ `.d.ts`
# ═════════════════════════════════════════════════════════════════════════════


def _campos_declarados(modelo: type[BaseModel]) -> set[str]:
    return set(modelo.model_fields)


def _modelos_alcancaveis() -> dict[str, type[BaseModel]]:
    """Todo modelo alcançável das raízes do contrato, por nome de classe."""
    achados: dict[str, type[BaseModel]] = {}
    pilha = list(MODELOS_DO_CONTRATO)
    while pilha:
        modelo = pilha.pop()
        if modelo.__name__ in achados:
            continue
        achados[modelo.__name__] = modelo
        for campo in modelo.model_fields.values():
            for candidato in (campo.annotation, *getattr(campo.annotation, "__args__", ())):
                for interno in (candidato, *getattr(candidato, "__args__", ())):
                    if isinstance(interno, type) and issubclass(interno, BaseModel):
                        pilha.append(interno)
    return achados


def test_dts_tem_uma_interface_por_modelo(exportacao_sintetica: X.ResultadoExportacao) -> None:
    """Nenhum modelo do contrato fica sem tipo, e o `.d.ts` não inventa interface."""
    texto = (exportacao_sintetica.pasta_da_tag / NOME_TIPOS_TS).read_text(encoding="utf-8")
    interfaces = tipos_ts.campos_por_interface(texto)
    assert set(interfaces) == set(_modelos_alcancaveis())


def test_dts_cobre_todo_campo_de_todo_modelo(
    exportacao_sintetica: X.ResultadoExportacao,
) -> None:
    """Campo do modelo que não virou campo da interface é campo que o front não consegue ler."""
    texto = (exportacao_sintetica.pasta_da_tag / NOME_TIPOS_TS).read_text(encoding="utf-8")
    interfaces = tipos_ts.campos_por_interface(texto)
    for nome, modelo in _modelos_alcancaveis().items():
        assert interfaces[nome] == _campos_declarados(modelo), nome


def test_dts_nomeia_cada_arquivo_e_a_sua_interface(
    exportacao_sintetica: X.ResultadoExportacao,
) -> None:
    """O cabeçalho do `.d.ts` é o mapa arquivo → interface: o front não adivinha o tipo."""
    texto = (exportacao_sintetica.pasta_da_tag / NOME_TIPOS_TS).read_text(encoding="utf-8")
    for arquivo, modelo in MODELO_POR_ARQUIVO.items():
        assert f"//   {arquivo} -> {modelo.__name__}" in texto
    assert exportacao_sintetica.dataset_sha256 in texto
    assert "NAO EDITE A MAO" in texto


def test_nullable_virou_union_com_null() -> None:
    """`float | None` em pydantic é `number | null` em TS — nunca campo opcional."""
    assert tipos_ts.tipo_ts({"anyOf": [{"type": "number"}, {"type": "null"}]}) == "number | null"
    assert tipos_ts.tipo_ts({"type": "array", "items": {"type": "string"}}) == "string[]"
    assert (
        tipos_ts.tipo_ts({"type": "object", "additionalProperties": {"type": "integer"}})
        == "Record<string, number>"
    )
    assert tipos_ts.tipo_ts({"$ref": "#/$defs/GateDaView"}) == "GateDaView"
    assert tipos_ts.tipo_ts({"const": "no-cache"}) == '"no-cache"'


def test_no_sem_traducao_levanta() -> None:
    """O gerador falha ruidosamente no que não sabe traduzir, em vez de emitir `any`."""
    with pytest.raises(ValueError, match="sem tradu"):
        tipos_ts.tipo_ts({"type": "bytes"})


# ═════════════════════════════════════════════════════════════════════════════
# 3 — `.d.ts` ⇒ JSON (o elo que fecha a prova)
# ═════════════════════════════════════════════════════════════════════════════

CHAVES_DINAMICAS: frozenset[str] = frozenset(
    {
        "arquivos",
        "casas_por_unidade",
        "contagens",
        "estilo_por_rotulo",
        "legenda",
        "mercado_por_quarter",
        "por_grupo",
        "quadrante_por_quarter",
        "politica_de_cache",
        "t_mais_1_por_quarter",
        "top5_por_lente",
        "unidade_por_campo",
        "unidade_de_apresentacao",
        "fator_de_apresentacao",
        "casas_de_apresentacao",
        "versao_build",
    }
)
"""Campos que são `Record<string, X>`: as chaves ali são **dado** (trimestre, rótulo, nome de
arquivo), não nome de campo, e por isso a varredura desce para os valores sem conferir as chaves."""


def _chaves_do_json(no: Any, *, dentro_de_mapa: bool = False) -> set[str]:
    """Todo nome de campo que aparece no JSON, pulando chaves de `Record<string, X>`."""
    achados: set[str] = set()
    if isinstance(no, dict):
        if not dentro_de_mapa:
            achados |= set(no)
        for chave, valor in no.items():
            achados |= _chaves_do_json(valor, dentro_de_mapa=chave in CHAVES_DINAMICAS)
    elif isinstance(no, list):
        for item in no:
            achados |= _chaves_do_json(item)
    return achados


def test_toda_chave_emitida_existe_no_dts(exportacao_sintetica: X.ResultadoExportacao) -> None:
    """**A asserção central da feature**: nenhuma chave gravada está fora do `.d.ts`."""
    texto = (exportacao_sintetica.pasta_da_tag / NOME_TIPOS_TS).read_text(encoding="utf-8")
    conhecidos = set().union(*tipos_ts.campos_por_interface(texto).values())
    for nome, caminho in _arquivos(exportacao_sintetica).items():
        emitidas = _chaves_do_json(_ler(caminho))
        assert emitidas <= conhecidos, f"{nome}: fora do .d.ts -> {sorted(emitidas - conhecidos)}"


def test_chaves_do_topo_sao_as_da_interface_do_arquivo(
    exportacao_sintetica: X.ResultadoExportacao,
) -> None:
    """E no topo a correspondência é **exata**: o arquivo é a interface, campo a campo."""
    texto = (exportacao_sintetica.pasta_da_tag / NOME_TIPOS_TS).read_text(encoding="utf-8")
    interfaces = tipos_ts.campos_por_interface(texto)
    for nome, caminho in _arquivos(exportacao_sintetica).items():
        assert set(_ler(caminho)) == interfaces[MODELO_POR_ARQUIVO[nome].__name__], nome


# ═════════════════════════════════════════════════════════════════════════════
# 3b — Unidades, precisão e o índice de views
# ═════════════════════════════════════════════════════════════════════════════

CAMPOS_NUMERICOS_SEM_UNIDADE: frozenset[str] = frozenset(
    {
        "alerta_abaixo_de",
        "arquivos_contados",
        "extremo_simetrico",
        "limite_inferior",
        "limite_superior",
        "n_celulas",
        "n_celulas_com_valor",
        "bytes",
        "bytes_das_views",
        "coluna",
        "colunas",
        "k_completo",
        "k_usado",
        "ks",
        "lag_divulgacao_dias",
        "limite_bytes",
        "linha",
        "linhas",
        "n_artefatos",
        "n_artefatos_fora_do_agregado",
        "n_comparaveis",
        "n_cobrem_1t2006",
        "n_decisoes_pendentes",
        "n_divergencias",
        "n_features",
        "n_indeterminados",
        "n_presentes",
        "n_registros",
        "n_series",
        "n_stress",
        "n_total",
        "n_trimestres",
        "n_vizinhos",
        "n_obs_regime_v1",
        "numero",
        "posicao",
        "rank",
        "schema_versao",
        "supressao_abaixo_de",
    }
)
"""Contagem, índice de grade, byte e peso de faixa: números sem unidade de mercado.

`n_obs`, `n_pares*` e tudo que é **retorno, correlação, distância ou taxa** está em
`UNIDADE_POR_CAMPO` — é o que o teste abaixo trava. Peso de faixa (`piso_*`, `banda_*`, `cap_usado`)
usa as casas de `peso` pela via do exportador, e é fração por construção.

`extremo_simetrico`, `limite_inferior` e `limite_superior` (`EixoDeCorDaVista`) são o único caso em
que a unidade **não pode** ser fixada pelo nome do campo: ela é a do campo que a linha nomeia em
`campo`, e o exportador arredonda cada um pelas casas desse campo (`views.eixos_de_cor`).
Declarar aqui uma unidade única para eles diria na tela uma unidade que a linha talvez não tenha.
"""


def _campos_numericos_dos_modelos() -> set[str]:
    numericos: set[str] = set()
    for modelo in _modelos_alcancaveis().values():
        esquema = modelo.model_json_schema(ref_template="#/$defs/{model}")
        for campo, no in (esquema.get("properties") or {}).items():
            alternativas = no.get("anyOf") or [no]
            if any(alt.get("type") in {"number", "integer"} for alt in alternativas):
                numericos.add(campo)
            itens = no.get("items")
            if isinstance(itens, dict) and itens.get("type") in {"number", "integer"}:
                numericos.add(campo)
    return numericos


def test_todo_campo_numerico_tem_unidade_declarada() -> None:
    """RF-W014: unidade **por campo**. Campo numérico novo sem unidade reprova aqui."""
    sem_unidade = _campos_numericos_dos_modelos() - set(UNIDADE_POR_CAMPO)
    assert sem_unidade <= CAMPOS_NUMERICOS_SEM_UNIDADE, sorted(
        sem_unidade - CAMPOS_NUMERICOS_SEM_UNIDADE
    )


def test_toda_unidade_declarada_tem_casas_decimais() -> None:
    """Unidade sem casas declaradas deixaria o `repr` do float vazar para o JSON."""
    assert set(UNIDADE_POR_CAMPO.values()) <= set(CASAS_POR_UNIDADE)
    for casas in CASAS_POR_UNIDADE.values():
        assert 0 <= casas <= 8


def test_indice_de_views_cobre_as_seis(exportacao_sintetica: X.ResultadoExportacao) -> None:
    """As 6 views do PRD, cada uma com o seu slot de `[arq §1.1]` e o seu `sha256` no `meta`."""
    assert set(SLOT_DA_VIEW) == set(VIEWS)
    assert len(VIEWS) == 6
    meta = _ler(exportacao_sintetica.pasta_da_tag / NOME_META)
    assert meta["schema_versao"] == SCHEMA_VERSAO
    assert {entrada["view"] for entrada in meta["views"]} == set(VIEWS)
    for entrada in meta["views"]:
        assert entrada["slot_arquitetura"] == SLOT_DA_VIEW[entrada["view"]]
        assert entrada["arquivo"] == f"{entrada['view']}.json"


def test_status_dos_adrs_concorda_com_a_funcao_do_gate(canonical_sintetico: Path) -> None:  # noqa: F811
    """O ADR-001 do catálogo e o do **gate** vêm do mesmo arquivo e têm de dizer o mesmo.

    O gate usa `regimes_v1.status_adr_001` (importada). A T-07 usa o leitor genérico dos 7 ADRs.
    Duas leituras do mesmo disco que divergissem seriam duas verdades sobre o gate.
    """
    do_catalogo = {
        item["id"]: item["status"] for item in views.status_dos_adrs(raiz=canonical_sintetico)
    }
    assert do_catalogo["ADR-001"] == status_adr_001(raiz=canonical_sintetico)
    assert len(do_catalogo) == 7


# ═════════════════════════════════════════════════════════════════════════════
# 4 — Acervo real (padrão `Acervo`; LDC_IGNORAR_DATA=1 desliga)
# ═════════════════════════════════════════════════════════════════════════════


@acervo_real
def test_acervo_os_tres_elos_fecham(exportacao_real: X.ResultadoExportacao) -> None:  # noqa: F811
    """Os mesmos 3 elos sobre `data/canonical/`: valida, cobre e nada sobra."""
    texto = (exportacao_real.pasta_da_tag / NOME_TIPOS_TS).read_text(encoding="utf-8")
    interfaces = tipos_ts.campos_por_interface(texto)
    conhecidos = set().union(*interfaces.values())
    caminhos = {nome: exportacao_real.pasta_da_tag / nome for nome in MODELO_POR_ARQUIVO}
    caminhos[NOME_CURRENT] = exportacao_real.destino / NOME_CURRENT
    for nome, caminho in caminhos.items():
        corpo = _ler(caminho)
        MODELO_POR_ARQUIVO[nome].model_validate(corpo)
        assert set(corpo) == interfaces[MODELO_POR_ARQUIVO[nome].__name__], nome
        emitidas = _chaves_do_json(corpo)
        assert emitidas <= conhecidos, f"{nome}: {sorted(emitidas - conhecidos)}"


@acervo_real
def test_acervo_catalogo_declara_cobertura_e_decisoes(
    exportacao_real: X.ResultadoExportacao,  # noqa: F811
) -> None:
    """T-07: 138 séries com cobertura declarada **e** observada, 10 limitações, 12 decisões, 7
    ADRs.
    """
    catalogo = _ler(exportacao_real.pasta_da_tag / "catalogo.json")
    assert catalogo["cobertura"]["n_series"] == len(catalogo["series"]) == 138
    assert len(catalogo["limitacoes"]) == 10
    assert len(catalogo["decisoes_pendentes"]) == 12
    assert len(catalogo["adrs"]) == 7
    assert {item["id"] for item in catalogo["adrs"]} == {f"ADR-00{i}" for i in range(1, 8)}
    for serie in catalogo["series"]:
        assert "data_inicio" in serie and "data_inicio_observada" in serie
    assert catalogo["artefatos_nao_publicaveis"][0]["artefato"] == "internacional_pesos.parquet"
    assert catalogo["artefatos_nao_publicaveis"][0]["motivo"]
    assert all("sha256" in artefato for artefato in catalogo["artefatos"])
