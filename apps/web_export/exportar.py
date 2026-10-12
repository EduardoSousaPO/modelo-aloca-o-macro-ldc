"""A ponte **única** do dataset congelado para o portal LDC Analytics (F-W001, classe C).

```
run --offline → verify → freeze --tag <t> → python -m apps.web_export exportar --tag <t>
```

Este módulo lê `data/canonical/MANIFEST.json` + `FROZEN.txt`, **aplica o gate**, e escreve
`<destino>/<tag>/` com `meta.json`, as **6 views** de `packages/shared/schemas/web_views.py`, o
`schema.d.ts` com os tipos TypeScript, e — **por último** — `<destino>/current.json`, o ponteiro.

## Onde o gate vive

**Aqui, não no front** (`docs/research/ldc-analytics-arquitetura.md §7.1`). O bundle que desce para
o
browser é texto baixável por quem passar do auth: filtro no front é decoração. As quatro travas:

1. **`publicavel: false` ⇒ recusa.** Nenhum valor de artefato marcado assim é lido ou emitido (hoje
   `internacional_pesos.parquet`, **D-af**). A lista de inclusão **não vence o manifesto**: se um
   artefato de `views.ARTEFATOS_LIDOS` aparecer marcado, o exportador para em vez de omitir em
   silêncio — o princípio de F-031.
2. **Artefato proibido ⇒ recusa** (`views.ARTEFATOS_PROIBIDOS`, RF-W015): `raw_series`, os
   `*_provenance`, `regime_neighbors` (variante de contrato), `ldc.duckdb`, `internacional_pesos`.
3. **Divergência de hash ⇒ recusa.** Chama o `verificar` de `apps/pipeline/run.py` — o mesmo que o
   `verify` da linha de comando — e para se qualquer artefato determinístico divergir. Manifesto
   ausente também para: não há dataset do qual exportar.
4. **`especificacao_congelada` viaja em toda view.** Lido do **ADR-001 em disco**
   (`regimes_v1.status_adr_001`, falha fechada). Enquanto estiver em `Proposta`, cada view nasce com
   a faixa de não publicável — e o dia em que o Edu virar o `Status`, o rebuild tira a faixa **sem
   uma linha de código**.

E a trava de `n`: célula com `n < 5` sai **com o valor e com `conclusao_suprimida: true`**. O número
continua no JSON porque o portal mostra "sem conclusão (n=4)", não uma célula vazia — e ausência
rotulada é o P10 do PRD. Quem decide o estado é `regimes_v1.conclusao_suprimida`, importada.

## Determinismo (CA-121 aplicado ao JSON)

Nada aqui lê o relógio: `data_do_dado` vem do manifesto, que vem do `date_max` do bruto. As chaves
saem ordenadas (`sort_keys=True`), os floats com casas fixas por unidade declarada, o fim de linha é
LF e `-0.0` é normalizado para `0.0`. Duas exportações da mesma tag ⇒ **mesmo `sha256` em todos os
arquivos**, provado em `tests/unit/test_web_export.py`.

## Orçamento

`web_views.LIMITE_DE_BYTES` (400 KB) sobre as 6 views + `schema.d.ts`, **medido** e não estimado. O
exportador recusa gravar acima disso: um portal que carrega 2 MB de JSON em 4G não cumpre RNF-W001 e
o lugar de descobrir isso é aqui, não no celular do Alexandre minutos antes da reunião.
"""

from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.analysis.entrega.montar_pacote import N_DECISOES, N_LIMITACOES, artefatos_do_manifesto
from apps.pipeline.canonical.build_raw_series import caminhos_dos_componentes
from apps.pipeline.canonical.build_raw_series import versao_build as _hash_dos_componentes
from apps.pipeline.canonical.regimes_v1 import (
    especificacao_esta_congelada,
    status_adr_001,
    veredito_publicacao,
)
from apps.pipeline.common.errors import ErroDeExtracao
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    garantir_diretorio,
    raiz_repo,
    sha256_de,
)
from apps.pipeline.run import NOME_FROZEN, NOME_MANIFESTO, _validar_tag, verificar
from apps.web_export import tipos_ts, views
from packages.shared.schemas.web_views import (
    CASAS_POR_UNIDADE,
    LIMITE_DE_BYTES,
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
    casas_de_apresentacao_por_campo,
    fator_de_apresentacao_por_campo,
    unidade_de_apresentacao_por_campo,
)

FEATURE = "F-W001"

MODULOS_DO_WEB_EXPORT: tuple[str, ...] = (
    "apps.web_export.exportar",
    "apps.web_export.views",
    "apps.web_export.tipos_ts",
    "packages.shared.schemas.web_views",
)
"""O que entra no `web_export_versao_build`: mudar o schema das views muda a versão do
exportador.
"""

SUBPASTA_PADRAO = "web"
"""Destino padrão: `data/web/` — **fora** de `data/canonical/`. Ver `AVISO_DESTINO_NO_CANONICAL`."""

AVISO_DESTINO_NO_CANONICAL = (
    "AVISO: o destino esta DENTRO de data/canonical/. `run.inventariar` varre essa pasta "
    "recursivamente, entao cada JSON escrito aqui aparece no `verify` como 'nao listado no "
    "manifesto' (divergencia GRAVE, rc != 0) e um `freeze` novo passaria a incluir o JSON no "
    "DATASET_SHA256 - que o proprio JSON cita. E a mesma colisao que D-ag resolveu para o pacote "
    "de entrega, e a saida e a mesma: uma exclusao por prefixo em run.py. Enquanto ela nao "
    "existir, "
    "use --destino data/web (o padrao) ou apague a pasta depois de coletar a evidencia."
)

MENSAGEM_SEM_MANIFESTO = (
    "BLOQUEADO - FONTE INDISPONIVEL: {alvo} nao existe. O exportador nao inventa dataset: rode "
    "`python -m apps.pipeline run --offline` e depois `python -m apps.pipeline freeze --tag <tag>`."
)


class ErroDeExportacao(ErroDeExtracao):
    """Base das falhas desta ponte. Nenhuma delas é recuperável emitindo JSON parcial."""


class DatasetDivergente(ErroDeExportacao):
    """O `sha256` em disco não bate com o `MANIFEST.json` — exportar publicaria outro dataset."""


class GateFechadoParaOArtefato(ErroDeExportacao):
    """Um artefato que o exportador leria está marcado `publicavel: false` (D-af)."""


class ArtefatoProibido(ErroDeExportacao):
    """RF-W015: artefato que o portal não pode consumir apareceu na lista de leitura."""


class OrcamentoExcedido(ErroDeExportacao):
    """O conjunto passou de `LIMITE_DE_BYTES`. Reduzir precisão é permitido; agregar não é."""


# ─────────────────────────────────────────────────────────────────────────────
# Gate
# ─────────────────────────────────────────────────────────────────────────────

MARCA_DO_GATE = (
    "MATERIAL DE DISCUSSAO - especificacao nao congelada (ADR-001 em Proposta). Nenhum numero "
    "desta tela e insumo de decisao de alocacao."
)


def ler_gate(*, raiz: Path | None = None) -> dict[str, Any]:
    """O gate como está **em disco**. Falha fechada: ADR ausente ⇒ `DESCONHECIDO` ⇒ não
    congelada.
    """
    congelada = especificacao_esta_congelada(raiz=raiz)
    return {
        "especificacao_congelada": congelada,
        "status_adr_001": status_adr_001(raiz=raiz),
        "veredito_publicacao": veredito_publicacao(congelada),
        "marca": "" if congelada else MARCA_DO_GATE,
        "publicavel": congelada,
    }


def caminho_do_manifesto(*, raiz: Path | None = None) -> Path:
    return caminho_camada(Camada.CANONICAL, raiz=raiz) / NOME_MANIFESTO


def ler_manifesto(*, raiz: Path | None = None) -> dict[str, Any]:
    """`MANIFEST.json` como dicionário. Ausente ou ilegível ⇒ `BLOQUEADO - FONTE INDISPONIVEL`."""
    alvo = caminho_do_manifesto(raiz=raiz)
    if not alvo.is_file():
        raise ErroDeExportacao(MENSAGEM_SEM_MANIFESTO.format(alvo=alvo))
    try:
        return json.loads(alvo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        msg = f"BLOQUEADO - FONTE INDISPONIVEL: {alvo} nao e JSON valido ({erro})."
        raise ErroDeExportacao(msg) from erro


def ler_frozen(*, raiz: Path | None = None) -> dict[str, str | None]:
    """O que o `FROZEN.txt` declara (tag e `DATASET_SHA256`), ou `presente: False` se não
    existir.
    """
    alvo = caminho_camada(Camada.CANONICAL, raiz=raiz) / NOME_FROZEN
    if not alvo.is_file():
        return {"presente": None, "tag": None, "dataset_sha256": None}
    achado: dict[str, str | None] = {"presente": "sim", "tag": None, "dataset_sha256": None}
    for linha in alvo.read_text(encoding="utf-8").splitlines():
        if ":" not in linha:
            continue
        chave, valor = linha.split(":", 1)
        rotulo, texto = chave.strip(), valor.strip()
        if rotulo == "tag":
            achado["tag"] = texto or None
        elif rotulo == "DATASET_SHA256":
            achado["dataset_sha256"] = texto or None
    return achado


def exigir_dataset_intacto(*, raiz: Path | None = None) -> str:
    """Roda o `verify` do pipeline e devolve o `DATASET_SHA256`. Divergência grave ⇒ recusa."""
    resultado = verificar(raiz=raiz)
    if not resultado.ok:
        detalhe = "; ".join(
            f"{d.arquivo}: {d.situacao} (esperado {d.esperado}, obtido {d.obtido})"
            for d in resultado.graves
        )
        msg = (
            "BLOQUEADO - DATASET DIVERGENTE: o `verify` do pipeline reprovou, entao exportar "
            f"publicaria numero de outro dataset. Divergencias graves: {detalhe}"
        )
        raise DatasetDivergente(msg)
    return resultado.agregado_obtido


def conferir_lista_de_inclusao(manifesto: dict[str, Any]) -> None:
    """A lista de leitura **não vence o manifesto** — e nenhum proibido entra nela (RF-W015)."""
    entradas = artefatos_do_manifesto(manifesto)
    intrusos = sorted(set(views.ARTEFATOS_LIDOS) & set(views.ARTEFATOS_PROIBIDOS))
    if intrusos:
        msg = (
            f"BLOQUEADO - ARTEFATO PROIBIDO: {intrusos} esta em ARTEFATOS_LIDOS e em "
            "ARTEFATOS_PROIBIDOS. RF-W015 proibe o portal de consumir esses artefatos."
        )
        raise ArtefatoProibido(msg)
    bloqueados = [
        (nome, str(entradas[nome].get("motivo_nao_publicavel") or "publicavel:false"))
        for nome in views.ARTEFATOS_LIDOS
        if nome in entradas and entradas[nome].get("publicavel") is False
    ]
    if bloqueados:
        detalhe = "; ".join(f"{nome}: {motivo}" for nome, motivo in bloqueados)
        msg = (
            "BLOQUEADO - GATE FECHADO PARA O ARTEFATO: o MANIFEST.json marca como publicavel:false "
            f"artefato que esta view leria. A lista de inclusao NAO vence o manifesto. {detalhe}"
        )
        raise GateFechadoParaOArtefato(msg)
    ausentes = [nome for nome in views.ARTEFATOS_LIDOS if nome not in entradas]
    if ausentes:
        msg = (
            f"BLOQUEADO - FONTE INDISPONIVEL: {ausentes} nao esta(o) no MANIFEST.json. Artefato "
            "nao manifestado e artefato que o `verify` nao protege."
        )
        raise ErroDeExportacao(msg)


def versao_build(modulos: tuple[str, ...] | None = None) -> str:
    """`sha256` dos módulos desta ponte — o mesmo algoritmo de `versao_build` do pipeline (D-v)."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DO_WEB_EXPORT))


# ─────────────────────────────────────────────────────────────────────────────
# Serialização
# ─────────────────────────────────────────────────────────────────────────────


def serializar(objeto: Any, *, compacto: bool) -> bytes:
    """JSON determinístico: chaves ordenadas, UTF-8, LF, sem relógio e sem `NaN`.

    As views saem **compactas** (são payload de rede); `meta.json` e `current.json` saem indentados,
    porque é o Edu que os lê quando algo divergir. Nos dois casos `allow_nan=False`: `NaN` em JSON
    é extensão, e `JSON.parse` do browser rejeita.
    """
    if compacto:
        texto = json.dumps(
            objeto, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    else:
        texto = json.dumps(objeto, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    return (texto + "\n").encode("utf-8")


def gravar(destino: Path, corpo: bytes) -> dict[str, Any]:
    """Grava com LF preservado (modo binário) e devolve o perfil do arquivo."""
    garantir_diretorio(destino.parent)
    destino.write_bytes(corpo)
    return {
        "arquivo": destino.name,
        "bytes": len(corpo),
        "sha256": sha256_de(corpo),
        "bytes_gzip": len(gzip.compress(corpo, compresslevel=9, mtime=0)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reduções declaradas
# ─────────────────────────────────────────────────────────────────────────────


def reducoes_declaradas() -> list[dict[str, Any]]:
    """O que **não** entra nesta tag, com o motivo. Nenhuma omissão fica implícita."""
    return [
        {
            "o_que": (
                "vizinhos: a view traz 1 das 4 lentes - mahalanobis, somente_passado=True, janela "
                "cheia - nos 3 k (5/8/12). As 9.692 linhas das 4 lentes x 2 metricas nao cabem no "
                "orcamento de 400 KB."
            ),
            "artefato": views.NOME_NEIGHBORS_V3,
            "por_que": (
                "RNF-W001 (carregamento < 3 s em 4G). A euclidiana e a variante restrito_pos_2016 "
                "continuam no Parquet e entram quando o payload sair do bundle. Nada foi agregado: "
                "a lente exportada vem linha a linha."
            ),
        },
        {
            "o_que": (
                "heatmap: a view traz as 322 celulas COMO PLOTADAS (figuras/heatmap_dados). As 3 "
                "tabelas regime_asset_metrics{,_asof,_horizonte_cruzado} (120/96/120) nao entram "
                "nesta tag - o que elas acrescentam e a linha SP500_USD e as metricas "
                "beta_ibov/sharpe/melhor_tri/ret_desvio/hit_ratio."
            ),
            "artefato": "regime_asset_metrics.parquet",
            "por_que": (
                "o hover de T-02 pede erro-padrao, hit_ratio_cdi, mediana, pior_tri e as flags - "
                "todos presentes nas 322 celulas. As 336 linhas extras custariam ~1/4 do orcamento "
                "para repetir o que a figura ja tem."
            ),
        },
        {
            "o_que": "T-05 (Ativo em foco) nao tem view nesta tag.",
            "artefato": "asset_returns_quarterly.parquet",
            "por_que": (
                "T-05 e v2 no PRD 10 e exige a serie ponto a ponto (1.963 linhas). O MVP sao T-01, "
                "T-02, T-03 e T-07."
            ),
        },
        {
            "o_que": "a tabela 'pedido x entregue' por item do e-mail (RF-W034) nao e emitida.",
            "artefato": None,
            "por_que": (
                "vive na 1 de LIMITACOES-COMITE.md como prosa, e extrair tabela de Markdown por "
                "regex nesta ponte criaria uma segunda verdade sobre o escopo. As 10 limitacoes e "
                "as 12 decisoes vem das funcoes que F-031 ja publica."
            ),
        },
        {
            "o_que": "nenhuma conversao de unidade e aplicada ao VALOR (RF-W014).",
            "artefato": None,
            "por_que": (
                "cada campo publica a unidade NATIVA do pipeline, declarada em "
                "meta.unidade_por_campo: retorno em fracao, Selic em % a.a. Zero conversao no "
                "numero e zero chance de erro de 100x aqui. A apresentacao (0,0504 -> 5,04%) e do "
                "front, e desde 2026-10-11 ela NAO e mais regra escrita la: o meta declara "
                "unidade_de_apresentacao, fator_de_apresentacao e casas_de_apresentacao campo a "
                "campo, e a tela le a tabela."
            ),
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Exportação
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoExportacao:
    """O que o CLI imprime e o que o teste confere."""

    tag: str
    destino: Path
    pasta_da_tag: Path
    dataset_sha256: str
    arquivos: tuple[dict[str, Any], ...]
    bytes_das_views: int
    bytes_totais: int
    bytes_gzip_totais: int
    gate: dict[str, Any]
    destino_no_canonical: bool

    @property
    def por_arquivo(self) -> dict[str, dict[str, Any]]:
        return {str(item["arquivo"]): item for item in self.arquivos}


def destino_padrao(*, raiz: Path | None = None) -> Path:
    return (raiz or raiz_repo()) / "data" / SUBPASTA_PADRAO


def exportar(
    *, tag: str, destino: Path | None = None, raiz: Path | None = None
) -> ResultadoExportacao:
    """Lê o dataset congelado, aplica o gate e escreve a tag. O ponteiro vai **por último**."""
    tag = _validar_tag(tag)
    manifesto = ler_manifesto(raiz=raiz)
    conferir_lista_de_inclusao(manifesto)
    dataset_sha256 = exigir_dataset_intacto(raiz=raiz)
    frozen = ler_frozen(raiz=raiz)
    if frozen["dataset_sha256"] and frozen["dataset_sha256"] != dataset_sha256:
        msg = (
            f"BLOQUEADO - DATASET DIVERGENTE: {NOME_FROZEN} declara "
            f"{frozen['dataset_sha256']} e o manifesto em disco agrega {dataset_sha256}. "
            "Congele de novo antes de exportar."
        )
        raise DatasetDivergente(msg)

    gate = ler_gate(raiz=raiz)
    base = (destino or destino_padrao(raiz=raiz)).resolve()
    pasta = base / tag
    canonical = caminho_camada(Camada.CANONICAL, raiz=raiz).resolve()
    no_canonical = base == canonical or canonical in base.parents

    ctx = views.Contexto(
        raiz=raiz,
        tag=tag,
        dataset_sha256=dataset_sha256,
        gate=gate,
        manifesto=manifesto,
    )
    reducoes = reducoes_declaradas()
    payloads = views.construir_todas(ctx, reducoes=reducoes)

    perfis: list[dict[str, Any]] = []
    indice: list[dict[str, Any]] = []
    for nome, payload in payloads.items():
        modelo = VIEWS[nome]
        validado = modelo.model_validate(payload)
        corpo = serializar(validado.model_dump(mode="json"), compacto=True)
        arquivo = f"{nome}.json"
        perfil = gravar(pasta / arquivo, corpo)
        perfis.append(perfil)
        indice.append(
            {
                "arquivo": arquivo,
                "view": nome,
                "tela": views.TELA_POR_VIEW[nome],
                "slot_arquitetura": SLOT_DA_VIEW[nome],
                "bytes": perfil["bytes"],
                "sha256": perfil["sha256"],
                "n_registros": _n_registros(payload),
            }
        )

    tipos = tipos_ts.gerar(
        MODELOS_DO_CONTRATO,
        tag=tag,
        dataset_sha256=dataset_sha256,
        arquivos={
            NOME_META: MetaWeb.__name__,
            NOME_CURRENT: PonteiroCurrent.__name__,
            **{f"{nome}.json": VIEWS[nome].__name__ for nome in payloads},
        },
    )
    perfis.append(gravar(pasta / NOME_TIPOS_TS, tipos.encode("utf-8")))

    bytes_das_views = sum(int(perfil["bytes"]) for perfil in perfis)
    if bytes_das_views > LIMITE_DE_BYTES:
        detalhe = ", ".join(f"{p['arquivo']}={p['bytes']}" for p in perfis)
        msg = (
            f"BLOQUEADO - ORCAMENTO EXCEDIDO: as views + {NOME_TIPOS_TS} somam {bytes_das_views} "
            f"bytes e o limite de RNF-W001 e {LIMITE_DE_BYTES}. Reduza a precisao numerica "
            f"declarada ou corte uma lente com declaracao em `reducoes` - nunca agregue. {detalhe}"
        )
        raise OrcamentoExcedido(msg)

    meta = _montar_meta(
        tag=tag,
        dataset_sha256=dataset_sha256,
        manifesto=manifesto,
        frozen=frozen,
        gate=gate,
        indice=indice,
        payloads=payloads,
        reducoes=reducoes,
        bytes_das_views=bytes_das_views,
        arquivos_contados=len(perfis),
        raiz=raiz,
    )
    corpo_meta = serializar(MetaWeb.model_validate(meta).model_dump(mode="json"), compacto=False)
    perfis.append(gravar(pasta / NOME_META, corpo_meta))

    ponteiro = {
        "tag": tag,
        "dataset_sha256": dataset_sha256,
        "meta": f"{tag}/{NOME_META}",
        "arquivos": {nome: f"{tag}/{nome}.json" for nome in payloads}
        | {"schema_ts": f"{tag}/{NOME_TIPOS_TS}"},
        "especificacao_congelada": bool(gate["especificacao_congelada"]),
        "cache_control": "no-cache",
        "cache_control_da_tag": "immutable",
    }
    corpo_ponteiro = serializar(
        PonteiroCurrent.model_validate(ponteiro).model_dump(mode="json"), compacto=False
    )
    perfis.append(gravar(base / NOME_CURRENT, corpo_ponteiro))

    return ResultadoExportacao(
        tag=tag,
        destino=base,
        pasta_da_tag=pasta,
        dataset_sha256=dataset_sha256,
        arquivos=tuple(perfis),
        bytes_das_views=bytes_das_views,
        bytes_totais=sum(int(perfil["bytes"]) for perfil in perfis),
        bytes_gzip_totais=sum(int(perfil["bytes_gzip"]) for perfil in perfis),
        gate=gate,
        destino_no_canonical=no_canonical,
    )


def _n_registros(payload: dict[str, Any]) -> int:
    """O tamanho do payload principal da view — o que o portal mostra como "N linhas"."""
    for chave in ("celulas", "rankings", "trimestres", "series"):
        valor = payload.get(chave)
        if isinstance(valor, list):
            return len(valor)
    return 0


def _montar_meta(
    *,
    tag: str,
    dataset_sha256: str,
    manifesto: dict[str, Any],
    frozen: dict[str, str | None],
    gate: dict[str, Any],
    indice: list[dict[str, Any]],
    payloads: dict[str, dict[str, Any]],
    reducoes: list[dict[str, Any]],
    bytes_das_views: int,
    arquivos_contados: int,
    raiz: Path | None,
) -> dict[str, Any]:
    """`meta.json` — tudo lido do manifesto e do disco, **nada do relógio** (CA-121)."""
    agregado = manifesto.get("agregado") or {}
    congelamento = manifesto.get("congelamento") or {}
    entradas = artefatos_do_manifesto(manifesto)
    nao_publicaveis = sorted(
        nome for nome, entrada in entradas.items() if entrada.get("publicavel") is False
    )
    do_catalogo = payloads["catalogo"]
    contagens = {
        "n_artefatos_publicaveis": len(do_catalogo["artefatos"]),
        "n_artefatos_nao_publicaveis": len(nao_publicaveis),
        "n_celulas_do_heatmap": len(payloads["heatmap_regime_ativo"]["celulas"]),
        "n_lentes_na_t01": len(payloads["ranking_atual"]["respostas"]),
        "n_linhas_do_ranking": len(payloads["ranking_atual"]["rankings"]),
        "n_pontos_da_timeline": len(payloads["regimes_timeline"]["trimestres"]),
        "n_referencias_de_vizinhos": len(payloads["vizinhos"]["referencias"]),
        "n_series_do_catalogo": len(do_catalogo["series"]),
        "n_trimestres": int(payloads["regimes_timeline"]["n_trimestres"]),
        "n_views": len(payloads),
    }
    limitacoes = [dict(item) for item in do_catalogo["limitacoes"]]
    if len(limitacoes) != N_LIMITACOES:
        msg = (
            f"BLOQUEADO - FONTE INDISPONIVEL: o caderno trouxe {len(limitacoes)} limitacoes e o "
            f"contrato espera {N_LIMITACOES}."
        )
        raise ErroDeExportacao(msg)
    if len(do_catalogo["decisoes_pendentes"]) != N_DECISOES:
        msg = (
            f"BLOQUEADO - FONTE INDISPONIVEL: a 7 de LIMITACOES-COMITE.md trouxe "
            f"{len(do_catalogo['decisoes_pendentes'])} decisoes e o contrato espera {N_DECISOES}."
        )
        raise ErroDeExportacao(msg)
    return {
        "schema_versao": SCHEMA_VERSAO,
        "feature": FEATURE,
        "tag": tag,
        "dataset_sha256": dataset_sha256,
        "dataset_sha256_curto": dataset_sha256[:12],
        "agregado": {
            "sha256": str(agregado.get("sha256") or dataset_sha256),
            "n_artefatos": int(agregado.get("n_artefatos") or 0),
            "n_artefatos_fora_do_agregado": int(agregado.get("n_artefatos_fora_do_agregado") or 0),
            "bytes": int(agregado.get("bytes") or 0),
            "linhas": int(agregado.get("linhas") or 0),
        },
        "data_do_dado": {
            chave: (manifesto.get("data_do_dado") or {}).get(chave)
            for chave in (
                "date_min_raw_series",
                "date_max_raw_series",
                "vintage_max",
                "primeiro_trimestre_macro",
                "ultimo_trimestre_macro",
            )
        },
        "congelamento": {
            "tag": congelamento.get("tag"),
            "git_commit": congelamento.get("git_commit"),
            "git_ref": congelamento.get("git_ref"),
            "frozen_txt_presente": frozen["presente"] is not None,
            "dataset_congelado": bool(congelamento.get("tag")) and frozen["presente"] is not None,
        },
        "versao_build": dict(sorted((manifesto.get("versao_build") or {}).items())),
        "web_export_versao_build": versao_build(),
        "gate": dict(gate),
        "views": indice,
        "contagens": dict(sorted(contagens.items())),
        "limitacoes": limitacoes,
        "n_decisoes_pendentes": len(do_catalogo["decisoes_pendentes"]),
        "unidade_por_campo": dict(sorted(UNIDADE_POR_CAMPO.items())),
        "casas_por_unidade": dict(sorted(CASAS_POR_UNIDADE.items())),
        "unidade_de_apresentacao": unidade_de_apresentacao_por_campo(),
        "fator_de_apresentacao": fator_de_apresentacao_por_campo(),
        "casas_de_apresentacao": casas_de_apresentacao_por_campo(),
        "reducoes": reducoes,
        "orcamento": {
            "limite_bytes": LIMITE_DE_BYTES,
            "bytes_das_views": bytes_das_views,
            "ok": bytes_das_views <= LIMITE_DE_BYTES,
            "arquivos_contados": arquivos_contados,
        },
        "artefatos_nao_publicaveis": nao_publicaveis,
        "politica_de_cache": {
            NOME_CURRENT: "no-cache (o unico; e o ponteiro, e vai gravado POR ULTIMO)",
            f"{tag}/*": "immutable (o caminho contem a tag, logo o conteudo nunca muda)",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def imprimir(resultado: ResultadoExportacao) -> None:
    """O resumo de tela — em ASCII, como todo stdout deste projeto."""
    print(f"tag                 : {resultado.tag}")
    print(f"destino             : {resultado.pasta_da_tag}")
    print(f"DATASET_SHA256      : {resultado.dataset_sha256}")
    print(f"gate                : {resultado.gate['veredito_publicacao']}")
    print(f"ADR-001 em disco    : {resultado.gate['status_adr_001']}")
    print(f"orcamento das views : {resultado.bytes_das_views} / {LIMITE_DE_BYTES} bytes")
    print(
        f"total escrito       : {resultado.bytes_totais} bytes ({resultado.bytes_gzip_totais} gzip)"
    )
    print("arquivos:")
    for item in resultado.arquivos:
        print(f"  {item['arquivo']:<32} {item['bytes']:>8} B  {item['sha256'][:12]}")
    if resultado.destino_no_canonical:
        print(AVISO_DESTINO_NO_CANONICAL)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.web_export",
        description="Exporta o dataset congelado como JSON por visao para o portal LDC Analytics.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    exportar_cmd = sub.add_parser("exportar", help="le o MANIFEST.json e escreve <destino>/<tag>/")
    exportar_cmd.add_argument("--tag", required=True, help="a tag do dataset congelado")
    exportar_cmd.add_argument(
        "--destino", default=None, help="diretorio base (padrao: data/web/ na raiz do repo)"
    )
    exportar_cmd.add_argument("--raiz", default=None, help="raiz do repo (padrao: detectada)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """`python -m apps.web_export exportar --tag <tag>`. `rc != 0` em qualquer recusa do gate."""
    args = _parser().parse_args(argv)
    try:
        resultado = exportar(
            tag=args.tag,
            destino=Path(args.destino) if args.destino else None,
            raiz=Path(args.raiz) if args.raiz else None,
        )
    except ErroDeExtracao as erro:
        print(str(erro))
        return 1
    imprimir(resultado)
    return 0
