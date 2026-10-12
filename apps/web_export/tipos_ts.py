"""Gerador de `schema.d.ts` — os tipos TypeScript **derivados** dos modelos pydantic (RF-W013).

Por que gerado e não escrito à mão: o contrato entre este repositório e o portal (`site-ldc`) tem de
ter **uma** definição por conceito. Tipo TS digitado à mão divergiria do JSON na primeira coluna
nova, e a divergência apareceria como `undefined` numa célula da tela — exatamente o modo de falha
silenciosa que o projeto inteiro combate.

O caminho é `pydantic → JSON Schema → TypeScript`: `model_json_schema()` já resolve `$defs`,
`anyOf` com `null` e `Literal`, então aqui só existe tradução sintática. Nenhum tipo é inferido do
JSON emitido — se um campo não está no modelo, ele não existe no `.d.ts` **e** o `extra="forbid"`
reprova a view antes de gravar.

Determinismo: as interfaces saem em ordem alfabética e os campos na ordem **declarada** no modelo
(que é a do JSON Schema). Duas gerações ⇒ bytes idênticos.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

TIPO_POR_JSON: dict[str, str] = {
    "boolean": "boolean",
    "integer": "number",
    "number": "number",
    "string": "string",
}

INDENTACAO = "  "


def _literal(valor: Any) -> str:
    if isinstance(valor, str):
        return f'"{valor}"'
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if valor is None:
        return "null"
    return str(valor)


def tipo_ts(no: dict[str, Any]) -> str:
    """Um nó de JSON Schema em TypeScript. Falha ruidosamente no que não sabe traduzir."""
    if "$ref" in no:
        return str(no["$ref"]).rsplit("/", 1)[-1]
    if "const" in no:
        return _literal(no["const"])
    if "enum" in no:
        return " | ".join(_literal(v) for v in no["enum"])
    if "anyOf" in no:
        partes = [tipo_ts(alternativa) for alternativa in no["anyOf"]]
        vistos: list[str] = []
        for parte in partes:
            if parte not in vistos:
                vistos.append(parte)
        return " | ".join(vistos)
    tipo = no.get("type")
    if tipo == "null":
        return "null"
    if tipo == "array":
        itens = no.get("items")
        interno = tipo_ts(itens) if isinstance(itens, dict) else "unknown"
        return f"({interno})[]" if "|" in interno else f"{interno}[]"
    if tipo == "object":
        extra = no.get("additionalProperties")
        if isinstance(extra, dict):
            return f"Record<string, {tipo_ts(extra)}>"
        return "Record<string, unknown>"
    if isinstance(tipo, str) and tipo in TIPO_POR_JSON:
        return TIPO_POR_JSON[tipo]
    if tipo is None and not no:
        return "unknown"
    msg = f"nó de JSON Schema sem tradução para TypeScript: {no!r}"
    raise ValueError(msg)


def _bloco_de_interface(nome: str, definicao: dict[str, Any]) -> str:
    propriedades: dict[str, Any] = definicao.get("properties", {})
    obrigatorios = set(definicao.get("required", list(propriedades)))
    linhas = [f"export interface {nome} {{"]
    descricao = definicao.get("description")
    if descricao:
        linhas.insert(0, f"/** {' '.join(str(descricao).split())} */")
    for campo, no in propriedades.items():
        doc = no.get("description")
        if doc:
            linhas.append(f"{INDENTACAO}/** {' '.join(str(doc).split())} */")
        opcional = "" if campo in obrigatorios else "?"
        linhas.append(f"{INDENTACAO}{campo}{opcional}: {tipo_ts(no)};")
    linhas.append("}")
    return "\n".join(linhas)


def coletar_definicoes(modelos: tuple[type[BaseModel], ...]) -> dict[str, dict[str, Any]]:
    """Toda interface alcançável das raízes, por nome — a raiz também entra como interface."""
    definicoes: dict[str, dict[str, Any]] = {}
    for modelo in modelos:
        esquema = modelo.model_json_schema(ref_template="#/$defs/{model}")
        for nome, definicao in (esquema.pop("$defs", {}) or {}).items():
            definicoes.setdefault(nome, definicao)
        definicoes.setdefault(esquema.get("title", modelo.__name__), esquema)
    return definicoes


def gerar(
    modelos: tuple[type[BaseModel], ...],
    *,
    tag: str,
    dataset_sha256: str,
    arquivos: dict[str, str],
) -> str:
    """O `schema.d.ts` completo, com cabeçalho de procedência e o mapa arquivo → interface."""
    definicoes = coletar_definicoes(modelos)
    cabecalho = [
        "// GERADO por apps/web_export (F-W001) de packages/shared/schemas/web_views.py.",
        "// NAO EDITE A MAO: o contrato e o modelo pydantic; este arquivo e derivado dele.",
        f"// tag: {tag}",
        f"// DATASET_SHA256: {dataset_sha256}",
        "//",
        "// Mapa arquivo -> interface:",
    ]
    cabecalho += [
        f"//   {arquivo} -> {interface}" for arquivo, interface in sorted(arquivos.items())
    ]
    cabecalho += [
        "//",
        "// Todo campo nullable e `| null`, nunca ausente: ausencia e erro de contrato, e o",
        "// exportador reprova a view antes de gravar (extra=forbid + campo obrigatorio).",
        "",
    ]
    corpo = [_bloco_de_interface(nome, definicoes[nome]) for nome in sorted(definicoes)]
    return "\n".join(cabecalho) + "\n" + "\n\n".join(corpo) + "\n"


def campos_por_interface(texto: str) -> dict[str, set[str]]:
    """As interfaces do `.d.ts` e seus campos — o leitor que o teste de contrato usa.

    Parse deliberadamente simples (o arquivo é gerado por `gerar`, não por um humano): abre em
    `export interface X {`, fecha em `}` na coluna 0, e cada linha `nome: tipo;` é um campo.
    """
    achados: dict[str, set[str]] = {}
    atual: str | None = None
    for linha in texto.splitlines():
        if linha.startswith("export interface "):
            atual = linha.removeprefix("export interface ").split("{", 1)[0].strip()
            achados[atual] = set()
            continue
        if linha == "}":
            atual = None
            continue
        if atual is None or ":" not in linha or linha.strip().startswith("/*"):
            continue
        nome = linha.split(":", 1)[0].strip().removesuffix("?")
        if nome and nome.isidentifier():
            achados[atual].add(nome)
    return achados
