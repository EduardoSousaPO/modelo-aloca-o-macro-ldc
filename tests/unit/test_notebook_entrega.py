"""F-027 — testes do notebook de entrega ao Comitê de Alocação.

**RF-041 / CA-110, CA-111 · `AGENTS.md §19` e `CLAUDE.md §3` (notebook sem lógica de negócio).**

O risco que estes testes cobrem não é "o notebook quebra": é **o notebook virar um segundo
pipeline**. Num caderno é barato escrever `df["x"] * 100` ou um `def retorno(...)` e, a partir
daí, existem dois lugares que calculam a mesma coisa e divergem em silêncio — exatamente o
cenário em que um número errado chega à reunião. Daí a regra ser estrutural (AST) e não um
pedido na revisão.

| Bloco | O que trava | CA |
|---|---|---|
| 1 | o arquivo é um notebook válido e está **com outputs limpos** | CA-111 |
| 2 | **nenhuma lógica de negócio** nas células de código (AST) | CA-110 |
| 3 | o notebook **importa** de `apps/` e nada mais calcula | CA-110 |
| 4 | determinismo e ausência de rede (nada de relógio, `random`, HTTP, magias) | CA-111 |
| 5 | estrutura: o gate, as 11 seções e os ganchos de conteúdo exigidos | CA-110/111 |
| 6 | **linguagem descritiva** em toda célula markdown | §10.2.10 |
| 7 | **acervo real**: execução ponta a ponta (padrão `Acervo`, pula sem `data/`) | CA-111 |

Os blocos 1-6 são estáticos: leem o `.ipynb` e **nunca pulam** — rodam no CI sem `data/`. O
bloco 7 segue o padrão `Acervo` de `test_tabela_ranking.py §8`: entra por acréscimo quando
`data/canonical/` existe na máquina e é desligado por `LDC_IGNORAR_DATA=1`.

**A regra de "sem cálculo", declarada por extenso** (é a definição que o bloco 2 aplica):

1. nenhuma célula de código define **função** (`def`, `async def`, `lambda`) ou **classe**;
2. nenhuma célula de código usa **operador aritmético** sobre nada — `+ - * / // % ** @` — nem
   na forma composta (`+=`, `*=`, …). Comparação (`==`, `<`) e combinação booleana de máscaras
   do pandas (`&`, `|`, `~`) **são** permitidas: recortar linha não é calcular;
3. nenhuma célula de código chama **método de agregação ou transformação numérica** do pandas
   (`sum`, `mean`, `pct_change`, `corr`, `groupby`, `apply`, `rolling`, …).

O que sobra é o que o notebook pode fazer: abrir arquivo (`pd.read_parquet`, `json.loads`),
recortar (`loc`, `head`, `isin`, `sort_values`), formatar pela função pública de `apps/`
(`pct`, `pp`, `num`, `Styler.format`) e mostrar (`display`, `Markdown`, `SVG`).
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path

import nbformat
import pytest

from apps.analysis.tabelas.ranking_regime_atual import conferir_linguagem_descritiva
from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, raiz_repo

RAIZ = raiz_repo()
NOTEBOOK = RAIZ / "apps" / "analysis" / "notebooks" / "entrega_comite_2026-10-14.ipynb"
README = RAIZ / "apps" / "analysis" / "notebooks" / "README.md"

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
COMO_GERAR = "rode `uv run python -m apps.pipeline run --offline`"

# ─────────────────────────────────────────────────────────────────────────────
# A regra de "sem cálculo", em código
# ─────────────────────────────────────────────────────────────────────────────

OPERADORES_ARITMETICOS: tuple[type[ast.operator], ...] = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.MatMult,
)
"""Os 8 operadores aritméticos de Python. `BitAnd`/`BitOr`/`BitXor` ficam fora de propósito:
`a & b` sobre `pd.Series` é máscara booleana (recorte), não conta."""

DEFINICOES_PROIBIDAS: tuple[type[ast.AST], ...] = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ClassDef,
)

METODOS_DE_CALCULO: frozenset[str] = frozenset(
    {
        "agg",
        "aggregate",
        "apply",
        "applymap",
        "corr",
        "corrwith",
        "cov",
        "cumprod",
        "cumsum",
        "diff",
        "div",
        "ewm",
        "expanding",
        "groupby",
        "mean",
        "median",
        "mul",
        "pct_change",
        "pipe",
        "prod",
        "quantile",
        "resample",
        "rolling",
        "sem",
        "std",
        "sub",
        "transform",
        "truediv",
        "var",
    }
)
"""Métodos que **calculam**. `sum`/`max`/`min`/`len` builtins sobre lista de arquivos são
contagem de inventário, não métrica — a lista cobre o que vem de `pd.DataFrame`/`pd.Series`,
que é onde o cálculo de negócio moraria."""

IMPORTS_PERMITIDOS: frozenset[str] = frozenset(
    {
        "json",
        "sys",
        "pathlib",
        "pandas",
        "IPython.display",
        "apps.analysis.tabelas.ranking_regime_atual",
        "apps.pipeline.common.io_layers",
    }
)

MODULOS_DE_REDE: tuple[str, ...] = ("requests", "httpx", "urllib", "socket", "boto3", "yfinance")
FONTES_DE_NAO_DETERMINISMO: tuple[str, ...] = (
    "datetime.now",
    "datetime.today",
    "time.time",
    "random.",
    "uuid",
    "os.environ",
    "getenv",
    "np.random",
)

SECOES_EXIGIDAS: tuple[str, ...] = (
    "## 0. O gate",
    "## 1. O pedido do e-mail",
    "## 2. Os dados",
    "## 3. Regimes macro",
    '## 4. "Momentos semelhantes"',
    "## 5. O mapa de calor",
    '## 6. "Em que regime estamos?"',
    "## 7. Internacional",
    "## 8. Limitações",
    "## 9. As doze decisões",
    "## 10. Como reproduzir",
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def notebook() -> nbformat.NotebookNode:
    """O `.ipynb` versionado, lido sem conversão de versão."""
    return nbformat.read(str(NOTEBOOK), as_version=nbformat.NO_CONVERT)


@pytest.fixture(scope="module")
def celulas_de_codigo(notebook: nbformat.NotebookNode) -> list[nbformat.NotebookNode]:
    return [c for c in notebook.cells if c.cell_type == "code"]


@pytest.fixture(scope="module")
def celulas_markdown(notebook: nbformat.NotebookNode) -> list[nbformat.NotebookNode]:
    return [c for c in notebook.cells if c.cell_type == "markdown"]


@pytest.fixture(scope="module")
def arvores(celulas_de_codigo: list[nbformat.NotebookNode]) -> list[tuple[str, ast.Module]]:
    """Uma `ast.Module` por célula de código — se alguma não parseia, é erro, não `skip`."""
    return [(c.id, ast.parse(c.source)) for c in celulas_de_codigo]


# ═════════════════════════════════════════════════════════════════════════════
# 1 — É um notebook válido e está com outputs limpos (CA-111)
# ═════════════════════════════════════════════════════════════════════════════


def test_o_arquivo_existe_no_caminho_do_contrato() -> None:
    assert NOTEBOOK.is_file(), f"notebook ausente em {NOTEBOOK}"
    assert README.is_file(), f"README da pasta ausente em {README}"


def test_nbformat_validate_passa(notebook: nbformat.NotebookNode) -> None:
    nbformat.validate(notebook)
    assert notebook.nbformat == 4
    assert notebook.nbformat_minor >= 5, "minor < 5 nao tem `id` de celula no schema"


def test_toda_celula_tem_id_explicito_e_unico(notebook: nbformat.NotebookNode) -> None:
    ids = [c.get("id") for c in notebook.cells]
    assert all(ids), "celula sem `id`: o nbformat sortearia um e os bytes mudariam a cada gravacao"
    assert len(ids) == len(set(ids)), f"ids repetidos: {ids}"


def test_outputs_limpos(celulas_de_codigo: list[nbformat.NotebookNode]) -> None:
    """CA-111: o commit não leva output. Nem um."""
    com_output = {c.id: len(c.get("outputs", [])) for c in celulas_de_codigo if c.get("outputs")}
    assert com_output == {}, f"celulas com output no commit: {com_output}"


def test_execution_count_zerado(celulas_de_codigo: list[nbformat.NotebookNode]) -> None:
    sujas = [c.id for c in celulas_de_codigo if c.get("execution_count") is not None]
    assert sujas == [], f"execution_count preenchido em {sujas} - rode `nbconvert --clear-output`"


def test_sem_metadata_de_execucao_nas_celulas(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """`metadata.execution` guarda horário de execução: é relógio dentro do arquivo versionado."""
    sujas = [c.id for c in celulas_de_codigo if "execution" in c.get("metadata", {})]
    assert sujas == [], f"metadata.execution em {sujas}"


def test_o_arquivo_usa_lf_e_nao_crlf() -> None:
    """Determinismo entre checkouts: CRLF muda o `sha256` do mesmo conteúdo (DECISIONS_LOG D-v)."""
    assert b"\r" not in NOTEBOOK.read_bytes(), "o .ipynb tem CR: o hash deixa de ser comparavel"


def test_tem_pelo_menos_um_bloco_de_cada_tipo(
    celulas_de_codigo: list[nbformat.NotebookNode],
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    assert len(celulas_markdown) >= 11, "11 secoes exigem ao menos 11 celulas markdown"
    assert len(celulas_de_codigo) >= 15, "muito pouca celula de codigo para as 11 secoes"


# ═════════════════════════════════════════════════════════════════════════════
# 2 — Nenhuma lógica de negócio nas células de código (CA-110)
# ═════════════════════════════════════════════════════════════════════════════


def test_nenhuma_celula_define_funcao_ou_classe(arvores: list[tuple[str, ast.Module]]) -> None:
    achados = [
        (ident, type(no).__name__, getattr(no, "lineno", None))
        for ident, arvore in arvores
        for no in ast.walk(arvore)
        if isinstance(no, DEFINICOES_PROIBIDAS)
    ]
    assert achados == [], (
        f"definicao em celula de notebook: {achados}. Toda funcao vive em apps/ "
        "(CLAUDE.md §3 / AGENTS.md §19); o notebook importa."
    )


def test_nenhuma_celula_usa_operador_aritmetico(arvores: list[tuple[str, ast.Module]]) -> None:
    """A regra dura: conta no notebook é cálculo duplicado esperando para divergir."""
    achados = [
        (ident, type(no.op).__name__, getattr(no, "lineno", None))
        for ident, arvore in arvores
        for no in ast.walk(arvore)
        if isinstance(no, (ast.BinOp, ast.AugAssign)) and isinstance(no.op, OPERADORES_ARITMETICOS)
    ]
    assert achados == [], (
        f"operador aritmetico em celula de notebook: {achados}. "
        "Formatacao em pt-BR vem de `pct`/`pp`/`num` de apps/analysis/tabelas/."
    )


def test_nenhuma_celula_chama_metodo_de_calculo(arvores: list[tuple[str, ast.Module]]) -> None:
    achados = [
        (ident, no.attr, getattr(no, "lineno", None))
        for ident, arvore in arvores
        for no in ast.walk(arvore)
        if isinstance(no, ast.Attribute) and no.attr in METODOS_DE_CALCULO
    ]
    assert achados == [], (
        f"metodo de calculo chamado no notebook: {achados}. Quem agrega e "
        "apps/pipeline/canonical/, e o resultado dele ja esta em data/canonical/."
    )


def test_nenhuma_celula_tem_magia_de_ipython(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """`%`/`!` não parseiam como Python e escondem instalação de dependência e shell."""
    achados = [
        (c.id, linha.strip())
        for c in celulas_de_codigo
        for linha in c.source.splitlines()
        if linha.lstrip().startswith(("%", "!", "%%"))
    ]
    assert achados == [], f"magia de IPython no notebook: {achados}"


# ═════════════════════════════════════════════════════════════════════════════
# 3 — O notebook importa de apps/ e nada mais (CA-110)
# ═════════════════════════════════════════════════════════════════════════════


def _modulos_importados(arvores: list[tuple[str, ast.Module]]) -> set[str]:
    nomes: set[str] = set()
    for _, arvore in arvores:
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes.update(alias.name for alias in no.names)
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes.add(no.module)
    return nomes


def test_importa_de_apps_e_so_do_que_esta_declarado(
    arvores: list[tuple[str, ast.Module]],
) -> None:
    importados = _modulos_importados(arvores)
    assert importados <= IMPORTS_PERMITIDOS, (
        f"import fora da lista declarada: {sorted(importados - IMPORTS_PERMITIDOS)}. "
        "Dependencia nova exige ADR (Anti-SPEC §10.4.25)."
    )
    de_apps = {m for m in importados if m.startswith("apps.")}
    assert de_apps, "CA-110 exige que o notebook IMPORTE de apps/ - nenhum import encontrado"


def test_nenhuma_importacao_de_rede(arvores: list[tuple[str, ast.Module]]) -> None:
    importados = _modulos_importados(arvores)
    achados = [m for m in importados if m.split(".")[0] in MODULOS_DE_REDE]
    assert achados == [], f"modulo de rede importado no notebook: {achados}"


def test_os_caminhos_passam_pelo_resolvedor_de_camada(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """Nenhum `data/canonical/...` escrito à mão: o endereço da camada é de `io_layers`."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    assert "caminho_canonical" in fonte, "o notebook tem de resolver caminho por io_layers"
    assert "data/canonical" not in fonte, "caminho de camada escrito a mao no notebook"
    assert "data\\canonical" not in fonte, "caminho de camada escrito a mao no notebook"
    assert "C:\\" not in fonte and "/Users/" not in fonte, "caminho absoluto de maquina no notebook"


def test_nada_escreve_em_data(celulas_de_codigo: list[nbformat.NotebookNode]) -> None:
    """Anti-SPEC §10.4.22: `data/` só muda por script do pipeline. O notebook só lê."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    for proibido in ("to_parquet", "to_csv", "write_text", "write_bytes", "mkdir", "savefig"):
        assert proibido not in fonte, f"o notebook escreveria em disco: `{proibido}`"


# ═════════════════════════════════════════════════════════════════════════════
# 4 — Determinismo (CA-111)
# ═════════════════════════════════════════════════════════════════════════════


def test_nenhuma_fonte_de_nao_determinismo(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    achados = [t for t in FONTES_DE_NAO_DETERMINISMO if t in fonte]
    assert achados == [], f"fonte de nao determinismo no notebook: {achados}"


def test_o_notebook_declara_a_sua_procedencia(notebook: nbformat.NotebookNode) -> None:
    ldc = notebook.metadata.get("ldc", {})
    assert ldc.get("feature") == "F-027"
    assert "CA-110" in ldc.get("cobre", "")
    assert "CA-111" in ldc.get("cobre", "")
    assert "sem logica de negocio" in ldc.get("regra", "")


# ═════════════════════════════════════════════════════════════════════════════
# 5 — Estrutura: o gate, as 11 seções e os ganchos de conteúdo
# ═════════════════════════════════════════════════════════════════════════════


def test_as_onze_secoes_estao_presentes_e_em_ordem(
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    texto = "\n".join(c.source for c in celulas_markdown)
    posicoes = [texto.find(secao) for secao in SECOES_EXIGIDAS]
    faltando = [s for s, p in zip(SECOES_EXIGIDAS, posicoes, strict=True) if p < 0]
    assert faltando == [], f"secao ausente: {faltando}"
    assert posicoes == sorted(posicoes), "as secoes nao estao na ordem 0..10"


def test_o_gate_vem_do_relatorio_e_do_manifest(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """CA-090: a marca de "não publicável" é **lida do disco**, nunca uma frase digitada."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    assert "relatorio_regimes_v1.json" in fonte
    assert "especificacao_congelada" in fonte
    assert "veredito_publicacao" in fonte
    assert "MANIFEST.json" in fonte
    assert "DATASET_SHA256" in fonte


def test_a_capa_declara_o_gate_e_o_carater_descritivo(
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    capa = celulas_markdown[0].source
    assert "não** está congelada" in capa or "não está congelada" in capa
    assert "ADR-001" in capa
    assert "material de discussão" in capa


def test_a_secao_de_limitacoes_linka_a_pagina_do_comite(
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    texto = "\n".join(c.source for c in celulas_markdown)
    assert "LIMITACOES-COMITE.md" in texto, "a secao 8 tem de linkar a pagina, nao copia-la"


def test_a_secao_8_tem_as_dez_limitacoes(celulas_markdown: list[nbformat.NotebookNode]) -> None:
    secao = next(c.source for c in celulas_markdown if "## 8. Limitações" in c.source)
    itens = [linha for linha in secao.splitlines() if linha[:3].strip().rstrip(".").isdigit()]
    assert len(itens) == 10, f"a secao 8 lista {len(itens)} limitacoes, nao 10"


def test_a_secao_9_tem_as_doze_decisoes(celulas_markdown: list[nbformat.NotebookNode]) -> None:
    secao = next(c.source for c in celulas_markdown if "## 9. As doze decisões" in c.source)
    linhas = [
        linha
        for linha in secao.splitlines()
        if linha.startswith("| **D") or linha.startswith("| **L")
    ]
    assert len(linhas) == 12, f"a secao 9 lista {len(linhas)} decisoes, nao 12"


def test_a_secao_10_traz_os_comandos_de_reproducao(
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    texto = "\n".join(c.source for c in celulas_markdown)
    assert "python -m apps.pipeline run --offline" in texto
    assert "python -m apps.pipeline verify" in texto
    assert "jupyter lab apps/analysis/notebooks/" in texto


def test_a_vista_de_horizonte_cruzado_resolve_o_nome_com_fallback(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """Renomeada no fechamento da Onda 4: o caderno nao depende de qual nome esta em disco."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    assert "heatmap_horizonte_cruzado.svg" in fonte, "o nome NOVO tem de ser o primeiro candidato"
    assert "heatmap_v3_t1.svg" in fonte, "o nome antigo tem de continuar como fallback"
    assert fonte.find("heatmap_horizonte_cruzado.svg") < fonte.find("heatmap_v3_t1.svg")


def test_a_tabela_de_variancia_minima_fica_fora(
    celulas_de_codigo: list[nbformat.NotebookNode],
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    """Anti-SPEC §10.5: variância mínima por regime está **fora** da entrega de 2026-10-14."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    assert "internacional_pesos" not in fonte, "o notebook leria a tabela bloqueada pela Anti-SPEC"
    assert "peso_variancia_minima" not in fonte
    assert "peso_sugerido_na_banda" not in fonte
    texto = "\n".join(c.source for c in celulas_markdown)
    assert "§10.5" in texto, "a ausencia tem de ser declarada, nao silenciosa"


def test_o_internacional_entrega_faixa_e_nao_numero_pontual(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """CA-107: a resposta de D6 é faixa — piso estrutural + banda tática."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    assert "faixa_de_d6" in fonte
    assert "piso_estrutural" in fonte
    assert "banda_tatica" in fonte
    assert "numero_pontual_rejeitado" in fonte


def test_todo_bloco_com_celula_mostra_n(celulas_de_codigo: list[nbformat.NotebookNode]) -> None:
    """Anti-SPEC §10.2.8: nenhuma célula sai sem `n`. As colunas de `n` são selecionadas."""
    fonte = "\n".join(c.source for c in celulas_de_codigo)
    for coluna in ("n_obs", "n_pares", "erro_padrao", "conclusao_suprimida", "alerta_n_baixo"):
        assert coluna in fonte, f"o notebook nunca mostra `{coluna}`"


# ═════════════════════════════════════════════════════════════════════════════
# 6 — Linguagem descritiva em toda célula markdown (Anti-SPEC §10.2.10)
# ═════════════════════════════════════════════════════════════════════════════


def test_toda_celula_markdown_passa_na_guarda(
    celulas_markdown: list[nbformat.NotebookNode],
) -> None:
    """Reusa a guarda **executável** de F-024 — a mesma que trava a tabela do Comitê."""
    falhas: list[tuple[str, str]] = []
    for celula in celulas_markdown:
        try:
            conferir_linguagem_descritiva(celula.source)
        except SerieInconsistente as erro:  # pragma: no cover - só quando alguém escreve previsão
            falhas.append((celula.id, str(erro)))
    assert falhas == [], f"linguagem preditiva no notebook: {falhas}"


def test_a_guarda_reprovaria_uma_frase_preditiva_no_notebook() -> None:
    """Contraprova: sem ela o teste acima passaria por não exercitar nada."""
    with pytest.raises(SerieInconsistente):
        conferir_linguagem_descritiva("## 4. Vizinhos\n\nO IBOV vai render no proximo tri.")


def test_as_celulas_de_codigo_tambem_nao_tem_forma_preditiva(
    celulas_de_codigo: list[nbformat.NotebookNode],
) -> None:
    """Comentário e literal de célula de código vão ao HTML exportado como qualquer outro texto."""
    falhas: list[tuple[str, str]] = []
    for celula in celulas_de_codigo:
        try:
            conferir_linguagem_descritiva(celula.source)
        except SerieInconsistente as erro:  # pragma: no cover
            falhas.append((celula.id, str(erro)))
    assert falhas == [], f"linguagem preditiva em celula de codigo: {falhas}"


# ═════════════════════════════════════════════════════════════════════════════
# 7 — Acervo real: execução ponta a ponta (padrão `Acervo`)
# ═════════════════════════════════════════════════════════════════════════════

ARTEFATOS_EXIGIDOS: tuple[str, ...] = (
    "MANIFEST.json",
    "relatorio_build.json",
    "relatorio_regimes_v1.json",
    "relatorio_regimes_v3.json",
    "relatorio_internacional.json",
    "alinhado_trimestral.parquet",
    "macro_quarterly.parquet",
    "raw_series.parquet",
    "internacional_por_regime.parquet",
    "figuras/timeline_regimes_revised.svg",
    "figuras/heatmap_v1_revised.svg",
    "tabelas/ranking_regime_atual.md",
    "tabelas/concordancia_lentes.md",
)


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
    """Todos os insumos que o notebook abre existem nesta máquina?"""
    return all(caminho_canonical(nome).is_file() for nome in ARTEFATOS_EXIGIDOS)


acervo_real = pytest.mark.skipif(
    ignorar_data_real() or not canonical_disponivel(),
    reason=f"data/canonical/ ausente ou {VAR_IGNORAR_DATA} ligada — {COMO_GERAR}",
)


@acervo_real
@pytest.mark.slow
def test_acervo_executa_ponta_a_ponta_sem_erro(tmp_path: Path) -> None:
    """CA-111: roda de ponta a ponta sobre o canônico já construído, **sem tocar no repo**.

    O caderno executado é gravado em `tmp_path`; o kernel roda com a raiz do repositório como
    diretório de trabalho (é de lá que o caderno descobre a raiz e importa `apps/`), e o
    `.ipynb` versionado é conferido por `sha256` antes e depois.
    """
    from nbconvert.preprocessors import ExecutePreprocessor

    antes = hashlib.sha256(NOTEBOOK.read_bytes()).hexdigest()
    nb = nbformat.read(str(NOTEBOOK), as_version=4)
    ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(
        nb, {"metadata": {"path": str(RAIZ)}}
    )

    executado = tmp_path / "executado.ipynb"
    nbformat.write(nb, str(executado))

    erros = [
        (c.id, saida.get("ename"), saida.get("evalue"))
        for c in nb.cells
        if c.cell_type == "code"
        for saida in c.get("outputs", [])
        if saida.get("output_type") == "error"
    ]
    assert erros == [], f"a execucao falhou: {erros}"

    de_codigo = [c for c in nb.cells if c.cell_type == "code"]
    sem_saida = [c.id for c in de_codigo if not c.get("outputs")]
    assert sem_saida == [], f"celula de codigo sem saida nenhuma: {sem_saida}"
    assert executado.is_file() and executado.stat().st_size > 100_000

    depois = hashlib.sha256(NOTEBOOK.read_bytes()).hexdigest()
    assert antes == depois, "a execucao sujou o .ipynb versionado"


@acervo_real
def test_acervo_o_gate_em_disco_continua_fechado() -> None:
    """Enquanto ADR-001 estiver em `Proposta`, o notebook abre com a marca de não publicável.

    Se este teste falhar, a especificação foi congelada — e o texto da capa precisa ser revisto
    junto com o fluxo de publicação (classe D).
    """
    relatorio = json.loads(
        caminho_canonical("relatorio_regimes_v1.json").read_text(encoding="utf-8")
    )
    espec = relatorio["especificacao"]
    assert espec["especificacao_congelada"] is False
    assert "NAO CONGELADA" in espec["veredito_publicacao"]


@acervo_real
def test_acervo_a_vista_de_horizonte_cruzado_existe_com_um_dos_dois_nomes() -> None:
    candidatos = ("figuras/heatmap_horizonte_cruzado.svg", "figuras/heatmap_v3_t1.svg")
    presentes = [nome for nome in candidatos if caminho_canonical(nome).is_file()]
    assert presentes, f"nenhuma das vistas de horizonte cruzado em disco: {candidatos}"
