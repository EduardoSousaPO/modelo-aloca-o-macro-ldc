"""Orquestrador "um comando" do pipeline (F-029) — `run`, `verify`, `freeze`.

RF-046 (um comando reconstrói tudo), RF-048 (idempotência por hash) · CA-118, CA-119, CA-121,
CA-122 · `AGENTS.md §6` (N3 = `sha256` idêntico em duas execuções) · `docs/plans/infra-ops.md §1.2`
(dataset congelado) · `docs/wiki/runbooks/reconstruir-dataset.md`.

**O que este módulo é.** A *ordem* do pipeline, escrita em um lugar só, e o *hash* do que ela
produziu. Nada de cálculo: toda etapa é uma chamada ao `construir()` da feature dona
(`apps/pipeline/canonical/*.py`) ou ao `main()` do extrator (`apps/pipeline/extract/*.py`). Se um
número está errado, o bug é da feature dona — este arquivo só decide **quem roda quando** e
**grava a evidência**.

**Três comandos:**

```bash
python -m apps.pipeline run --offline              # reconstrói de data/processed (sem rede)
python -m apps.pipeline run --online               # extrai das fontes e reconstrói tudo
python -m apps.pipeline verify                     # recalcula sha256 e confere com o MANIFEST
python -m apps.pipeline freeze --tag comite-2026-10-14
```

**Decisões que valem ler antes de mexer:**

1. **`--offline` não toca `data/raw/`.** A fonte do modo offline é `data/processed/`, que é o que
   o teste de reprodutibilidade consegue montar a partir de `tests/fixtures/processed/` e o que o
   runbook preserva. Reprocessar `raw -> processed` sem rede é explícito: `--reprocessar`.
2. **Parada no primeiro erro.** Etapa que levanta `ErroDeExtracao` (inclusive
   `BLOQUEADO — FONTE INDISPONÍVEL`) para o pipeline ali, nomeia a etapa e imprime o comando de
   retomada. Nenhuma etapa a jusante roda com insumo faltando — é o oposto de "preencher a lacuna".
3. **`ldc.duckdb` não é determinístico** e está declarado como tal: duas execuções sobre o mesmo
   `data/processed/` produzem `.duckdb` com bytes diferentes (medido: mesmo tamanho, `sha256`
   diferente) porque o arquivo carrega metadado interno da própria escrita. Ele é derivado e
   descartável (ADR-006 §(a).2 — *views* sobre o Parquet), então entra no manifesto com
   `determinista: false` e **fica fora do hash agregado**. O `verify` reporta a diferença como
   informativa, nunca como falha. Quem quer o diretório inteiro determinístico roda
   `run --offline --sem-duckdb`.
4. **Só escreve dentro de `data/`.** Os dois arquivos deste módulo (`MANIFEST.json`, `FROZEN.txt`)
   nascem em `data/canonical/` (ou no `--saida`, que é validado contra `<raiz>/data`). `freeze`
   **não** chama git: lê `.git/HEAD` para registrar o commit e deixa `git tag` para o humano
   (`infra-ops.md §1.3`).
5. **Nada aqui lê o relógio.** `data_do_dado` sai dos relatórios das features (`date_max` de
   `raw_series`, último trimestre de `macro_quarterly`), nunca de `datetime.now()` — é o que faz
   o `MANIFEST.json` ser byte-idêntico entre duas execuções (CA-121) e o que faz `FROZEN.txt`
   dizer a data **do dado**, não a do congelamento.
6. **Log e saída em ASCII puro.** `para_ascii` transliteram toda mensagem antes do `print`: o
   `stdout` redirecionado no Windows é cp1252 e `—`/`·` viram `UnicodeEncodeError`
   (Anti-SPEC §10.4.26), inclusive quando a mensagem vem da exceção de outro módulo.

Anti-SPEC: §10.4.21 (nada commitado — `data/` está no `.gitignore`), §10.4.22 (nada em `data/`
vem de edição manual), §10.4.26 (encoding declarado em todo leitor/escritor), §10.4.29 (o
`MANIFEST.json` é artefato de `data/`, não arquivo de estado na raiz).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import pkgutil
import sys
import time
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from apps.pipeline.common.errors import ErroDeExtracao
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    garantir_diretorio,
    raiz_repo,
    sha256_de,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger

_log = obter_logger(__name__)

NOME_MANIFESTO = "MANIFEST.json"
NOME_FROZEN = "FROZEN.txt"
VERSAO_DO_MANIFESTO = 1

#: Arquivos de `data/canonical/` que **não** são artefato do pipeline: o placeholder do git e os
#: dois arquivos que este módulo escreve (incluí-los faria o manifesto hashear a si mesmo).
NAO_SAO_ARTEFATO: frozenset[str] = frozenset({".gitkeep", NOME_MANIFESTO, NOME_FROZEN})

#: Artefatos **derivados e descartáveis** cujos bytes não são reprodutíveis. Entram no manifesto
#: com `determinista: false`, ficam fora do agregado e o `verify` só os reporta. Ver decisão 3.
NAO_DETERMINISTICOS: frozenset[str] = frozenset({"ldc.duckdb"})

#: Primeira coluna encontrada é a que dá `date_min`/`date_max` do artefato (CA-118). `quarter` é
#: string ordenável (`2006Q1` < `2026Q3`), então `min`/`max` lexicográficos são a data certa.
COLUNAS_DE_DATA: tuple[str, ...] = ("date", "quarter", "date_obs", "quarter_ref")

#: Quantas colunas com nulo o resumo de tela lista por artefato antes de resumir o resto.
MAX_COLUNAS_NO_RESUMO = 6


class ErroDeOrquestracao(ErroDeExtracao):
    """Falha do orquestrador: etapa inexistente, `--raiz` incompatível, `--saida` fora de `data/`.

    Herda de `ErroDeExtracao` para que a CLI tenha **um** `except` e o processo saia com `1` em
    qualquer falha explícita, sem traceback.
    """


class FalhaDeEtapa(ErroDeExtracao):
    """Uma etapa falhou. A mensagem nomeia a etapa e o comando de retomada (CA-118)."""


class EtapaNaoChamavel(ErroDeExtracao):
    """O módulo de uma etapa **opcional** existe, mas ainda não expõe ponto de entrada.

    Acontece com feature vizinha em construção (F-022/F-025 foram escritas em paralelo a esta):
    o pacote já está no disco e o `construir()` ainda não. Numa etapa opcional isso é **pular com
    aviso**, não falhar — o contrato da etapa opcional é "se o módulo existir *e* for chamável,
    roda; registre". Falha de verdade **dentro** do `construir()` continua parando o pipeline.
    """


# ─────────────────────────────────────────────────────────────────────────────
# ASCII
# ─────────────────────────────────────────────────────────────────────────────

_SUBSTITUICOES_ASCII: tuple[tuple[str, str], ...] = (
    ("—", "-"),
    ("–", "-"),
    ("·", "|"),
    ("→", "->"),
    ("≤", "<="),
    ("≥", ">="),
    ("“", '"'),
    ("”", '"'),
    ("‘", "'"),
    ("’", "'"),
    ("…", "..."),
    ("±", "+/-"),
)


def para_ascii(texto: str) -> str:
    """Transliteração ASCII de qualquer mensagem antes de ir para `stdout`/`stderr`.

    Existe porque o `stdout` redirecionado no Windows é cp1252 e as mensagens deste pipeline
    nascem em português — inclusive as que vêm de exceções de outros módulos
    (`BLOQUEADO — FONTE INDISPONÍVEL` tem um travessão). Sem isto, o `print` que informa a falha
    falharia com `UnicodeEncodeError` e esconderia a falha real (Anti-SPEC §10.4.26).
    """
    for origem, destino in _SUBSTITUICOES_ASCII:
        texto = texto.replace(origem, destino)
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.encode("ascii", "replace").decode("ascii")


def _imprimir(texto: str = "") -> None:
    print(para_ascii(texto))


# ─────────────────────────────────────────────────────────────────────────────
# Etapas — a ordem do pipeline, em um lugar só
# ─────────────────────────────────────────────────────────────────────────────


class Fase(StrEnum):
    """Fase da etapa. `EXTRACAO` é a única que depende de rede (e só em `--online`)."""

    EXTRACAO = "extracao"
    TRANSFORMACAO = "transformacao"
    CANONICO = "canonico"
    ANALISE = "analise"


@dataclass(frozen=True, slots=True)
class Contexto:
    """O que uma etapa precisa saber da rodada. `raiz=None` significa a raiz do repositório."""

    raiz: Path | None = None
    offline: bool = True
    com_duckdb: bool = True


@dataclass(frozen=True, slots=True)
class Etapa:
    """Uma etapa nomeada do pipeline.

    `artefatos` é só documentação/conferência: o manifesto hasheia o diretório inteiro, então uma
    etapa opcional que grave arquivos de nome desconhecido (F-022, F-025) continua coberta.
    """

    nome: str
    fase: Fase
    descricao: str
    executar: Callable[[Contexto], None]
    artefatos: tuple[str, ...] = ()
    #: Módulo que precisa existir para a etapa rodar. `None` = etapa obrigatória.
    modulo_opcional: str | None = None

    @property
    def opcional(self) -> bool:
        return self.modulo_opcional is not None


def _rodar_extrator(ctx: Contexto, *, modulo: str, extras: Sequence[str] = ()) -> None:
    """Chama o `main()` do extrator. `--offline` só é passado em `--reprocessar`."""
    if ctx.raiz is not None:
        msg = (
            f"etapa de extração não aceita --raiz: {modulo} grava sempre em "
            f"{raiz_repo()}/data/raw (io_layers.raiz_repo). Use --raiz apenas com as etapas "
            f"canônicas (run --offline)."
        )
        raise ErroDeOrquestracao(msg)
    argv = [*extras]
    if ctx.offline:
        argv.append("--offline")
    codigo = importlib.import_module(modulo).main(argv)
    if codigo != 0:
        msg = f"{modulo} saiu com código {codigo} (a mensagem da fonte está no log acima)"
        raise FalhaDeEtapa(msg)


def _rodar_construir(ctx: Contexto, *, modulo: str, **kwargs: Any) -> None:
    """Chama o `construir(raiz=...)` da feature dona — nunca reimplementa o cálculo."""
    importlib.import_module(modulo).construir(raiz=ctx.raiz, **kwargs)


def _rodar_opcional(ctx: Contexto, *, modulo: str) -> None:
    """Etapa opcional (F-022/F-025): `construir(raiz=)` se houver, senão `main([])`.

    A assinatura da feature vizinha ainda não existe quando esta feature é escrita, então a ponte
    é por introspecção e **declarada**: `construir(raiz=...)` é a convenção das 8 etapas canônicas
    e o que esta ponte tenta primeiro.
    """
    mod = importlib.import_module(modulo)
    construir = getattr(mod, "construir", None)
    if callable(construir):
        construir(raiz=ctx.raiz)
        return
    principal = getattr(mod, "main", None)
    if not callable(principal):
        msg = (
            f"{modulo} existe mas ainda não expõe `construir(raiz=...)` nem `main(argv)` — o "
            f"orquestrador não tem como chamá-lo (a convenção das etapas canônicas é "
            f"`construir(*, raiz=None)`)."
        )
        raise EtapaNaoChamavel(msg)
    if ctx.raiz is not None:
        msg = (
            f"{modulo} só expõe `main(argv)`, que grava na raiz do repositório: incompatível com "
            f"--raiz. Exponha `construir(*, raiz=None)` ou rode esta etapa sem --raiz."
        )
        raise ErroDeOrquestracao(msg)
    codigo = principal([])
    if codigo not in (0, None):
        msg = f"{modulo}.main saiu com código {codigo}"
        raise FalhaDeEtapa(msg)


def _rodar_figuras(ctx: Contexto) -> None:
    """Roda **todo** submódulo de `apps/analysis/figuras/` que exponha `construir`, em ordem.

    Descoberta em vez de lista: F-025 entregou `timeline_regimes`, e o heatmap (F-023) e o
    ranking (F-024) entram na mesma pasta depois. O pacote `apps.analysis.figuras` não reexporta
    `construir` (cada figura é um módulo), então a ponte varre `pkgutil.iter_modules` e chama o
    que existir — figura nova é desenhada pelo `run` sem tocar neste arquivo.
    """
    pacote = importlib.import_module("apps.analysis.figuras")
    caminhos = list(getattr(pacote, "__path__", []))
    chamados: list[str] = []
    for info in sorted(pkgutil.iter_modules(caminhos), key=lambda i: i.name):
        modulo = importlib.import_module(f"apps.analysis.figuras.{info.name}")
        construir = getattr(modulo, "construir", None)
        if not callable(construir):
            continue
        construir(raiz=ctx.raiz)
        chamados.append(info.name)
    if not chamados:
        msg = (
            "apps.analysis.figuras existe mas nenhum submódulo expõe `construir(raiz=...)` — "
            "nada a desenhar (F-025 em construção)."
        )
        raise EtapaNaoChamavel(msg)
    _log.info("figuras desenhadas por: %s", ", ".join(chamados))


def etapas() -> tuple[Etapa, ...]:
    """A ordem completa do pipeline. **Esta tupla é o contrato de ordem** (teste em `tests/unit`).

    Extração (9 etapas, `--online`/`--reprocessar`) -> transformação (`curva`, que grava em
    `data/processed/`) -> canônico (8 etapas) -> análise (2 opcionais, de F-022 e F-025).
    `sgs` vem antes de `yahoo`/`msci` porque a conversão a BRL usa a PTAX de F-003 (D-g);
    `calendario` vem antes do canônico porque `alinhamento` lê a grade de dias úteis.
    """
    extratores: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("extract_sgs", "apps.pipeline.extract.bcb_sgs", ("--todas",)),
        ("extract_sidra", "apps.pipeline.extract.ibge_sidra", ()),
        ("extract_focus", "apps.pipeline.extract.bcb_focus", ()),
        ("extract_calendario", "apps.pipeline.extract.calendario_anbima", ()),
        ("extract_anbima", "apps.pipeline.extract.anbima_s3", ()),
        ("extract_tesouro", "apps.pipeline.extract.tesouro_direto", ()),
        ("extract_b3", "apps.pipeline.extract.b3_indices", ()),
        ("extract_yahoo", "apps.pipeline.extract.yahoo", ()),
        ("extract_msci", "apps.pipeline.extract.msci", ()),
    )
    de_extracao = tuple(
        Etapa(
            nome=nome,
            fase=Fase.EXTRACAO,
            descricao=f"{modulo} -> data/raw + data/processed",
            executar=_fabrica_extrator(modulo, extras),
        )
        for nome, modulo, extras in extratores
    )
    return (
        *de_extracao,
        Etapa(
            nome="curva",
            fase=Fase.TRANSFORMACAO,
            descricao="F-016: painel do Tesouro -> 11 series de curva em data/processed/curva/",
            executar=lambda ctx: _rodar_construir(ctx, modulo="apps.pipeline.canonical.curva"),
        ),
        Etapa(
            nome="build_raw_series",
            fase=Fase.CANONICO,
            descricao="F-013: data/processed/ -> raw_series + series_catalog (+ ldc.duckdb)",
            executar=lambda ctx: _rodar_construir(
                ctx,
                modulo="apps.pipeline.canonical.build_raw_series",
                com_duckdb=ctx.com_duckdb,
            ),
            artefatos=("raw_series.parquet", "series_catalog.parquet", "relatorio_build.json"),
        ),
        Etapa(
            nome="alinhamento",
            fase=Fase.CANONICO,
            descricao="F-014: raw_series + calendario ANBIMA -> alinhado_trimestral",
            executar=lambda ctx: _rodar_construir(
                ctx, modulo="apps.pipeline.canonical.alinhamento"
            ),
            artefatos=("alinhado_trimestral.parquet", "relatorio_alinhamento.json"),
        ),
        Etapa(
            nome="macro_quarterly",
            fase=Fase.CANONICO,
            descricao="F-015: alinhado + Focus -> macro_quarterly (revised) + provenance",
            executar=lambda ctx: _rodar_construir(
                ctx, modulo="apps.pipeline.canonical.macro_quarterly"
            ),
            artefatos=(
                "macro_quarterly.parquet",
                "macro_quarterly_provenance.parquet",
                "relatorio_macro.json",
            ),
        ),
        Etapa(
            nome="asof",
            fase=Fase.CANONICO,
            descricao="F-018: materializacao asof (anti-look-ahead) + provenance com lag",
            executar=lambda ctx: _rodar_construir(ctx, modulo="apps.pipeline.canonical.asof"),
            artefatos=(
                "macro_quarterly_asof.parquet",
                "macro_quarterly_asof_provenance.parquet",
                "relatorio_asof.json",
            ),
        ),
        Etapa(
            nome="retornos",
            fase=Fase.CANONICO,
            descricao="F-017: alinhado -> asset_returns_quarterly (24 ativos)",
            executar=lambda ctx: _rodar_construir(ctx, modulo="apps.pipeline.canonical.retornos"),
            artefatos=("asset_returns_quarterly.parquet", "relatorio_retornos.json"),
        ),
        Etapa(
            nome="regimes_v1",
            fase=Fase.CANONICO,
            descricao="F-019: regimes V1 (quadrantes) sobre macro_quarterly revised",
            executar=lambda ctx: _rodar_construir(
                ctx, modulo="apps.pipeline.canonical.regimes_v1", materializacao="revised"
            ),
            artefatos=("regimes_v1.parquet", "relatorio_regimes_v1.json"),
        ),
        Etapa(
            nome="regimes_v1_asof",
            fase=Fase.CANONICO,
            descricao="F-019 sobre a materializacao asof (a lente de DECISAO)",
            executar=lambda ctx: _rodar_construir(
                ctx, modulo="apps.pipeline.canonical.regimes_v1", materializacao="asof"
            ),
            artefatos=("regimes_v1_asof.parquet", "relatorio_regimes_v1_asof.json"),
        ),
        Etapa(
            nome="regimes_v3",
            fase=Fase.CANONICO,
            descricao="F-021: vizinhos Mahalanobis (Ledoit-Wolf) -> regime_neighbors{,_v3}",
            executar=lambda ctx: _rodar_construir(ctx, modulo="apps.pipeline.canonical.regimes_v3"),
            artefatos=(
                "regime_neighbors_v3.parquet",
                "regime_neighbors.parquet",
                "relatorio_regimes_v3.json",
            ),
        ),
        Etapa(
            nome="metricas_regime",
            fase=Fase.CANONICO,
            descricao="F-022 (opcional): metricas regime x ativo, se o modulo existir",
            executar=lambda ctx: _rodar_opcional(
                ctx, modulo="apps.pipeline.canonical.metricas_regime"
            ),
            modulo_opcional="apps.pipeline.canonical.metricas_regime",
        ),
        Etapa(
            nome="figuras",
            fase=Fase.ANALISE,
            descricao="F-025 (opcional): toda figura de apps/analysis/figuras/ com construir()",
            executar=_rodar_figuras,
            modulo_opcional="apps.analysis.figuras",
        ),
    )


def _fabrica_extrator(modulo: str, extras: tuple[str, ...]) -> Callable[[Contexto], None]:
    """Fecha `modulo`/`extras` por valor — `lambda` em laço captura a variável, não o valor."""
    return lambda ctx: _rodar_extrator(ctx, modulo=modulo, extras=extras)


def nomes_das_etapas() -> tuple[str, ...]:
    return tuple(etapa.nome for etapa in etapas())


def modulo_disponivel(nome_do_modulo: str) -> bool:
    """`True` se o módulo é importável — sem importá-lo (evita efeito colateral de import)."""
    try:
        return importlib.util.find_spec(nome_do_modulo) is not None
    except (ImportError, ValueError):
        return False


def selecionar_etapas(
    *,
    online: bool,
    reprocessar: bool = False,
    ate: str | None = None,
    so: str | None = None,
    com_opcionais: bool = True,
) -> tuple[Etapa, ...]:
    """Fatia a ordem completa conforme as flags. `--so` tem precedência sobre `--ate`.

    Extração entra só em `--online` (fontes vivas) ou `--reprocessar` (mesmo caminho, `--offline`
    em cada extrator). `--so <etapa>` roda exatamente uma, mesmo opcional ou de extração — é o
    comando de retomada que a mensagem de falha imprime.
    """
    todas = etapas()
    por_nome = {etapa.nome: etapa for etapa in todas}
    for rotulo, valor in (("--so", so), ("--ate", ate)):
        if valor is not None and valor not in por_nome:
            msg = (
                f"{rotulo} {valor!r} não é uma etapa. Etapas validas, nesta ordem: "
                f"{', '.join(por_nome)}"
            )
            raise ErroDeOrquestracao(msg)
    if so is not None:
        return (por_nome[so],)
    com_extracao = online or reprocessar
    escolhidas = [
        etapa
        for etapa in todas
        if (com_extracao or etapa.fase is not Fase.EXTRACAO)
        and (com_opcionais or not etapa.opcional)
    ]
    if ate is not None:
        nomes = [etapa.nome for etapa in escolhidas]
        if ate not in nomes:
            msg = (
                f"--ate {ate!r} é uma etapa valida, mas está fora da selecao desta rodada "
                f"(fase {por_nome[ate].fase.value}"
                f"{', opcional' if por_nome[ate].opcional else ''}). Selecao atual: "
                f"{', '.join(nomes)}"
            )
            raise ErroDeOrquestracao(msg)
        escolhidas = escolhidas[: nomes.index(ate) + 1]
    return tuple(escolhidas)


# ─────────────────────────────────────────────────────────────────────────────
# Inventário de `data/canonical/` — linhas, datas, nulos, hash
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Artefato:
    """Um arquivo de `data/canonical/` com o que CA-118 pede e o `sha256` de CA-121."""

    arquivo: str
    bytes: int
    sha256: str
    determinista: bool
    linhas: int | None = None
    colunas: int | None = None
    coluna_de_data: str | None = None
    date_min: str | None = None
    date_max: str | None = None
    pct_nulos: float | None = None
    nulos_por_coluna: Mapping[str, float] = field(default_factory=dict)

    def como_dicionario(self) -> dict[str, Any]:
        """Forma estável para o `MANIFEST.json` — nada de `Path`, `Timestamp` ou `float` cru.

        Artefato declarado **não determinístico** entra com `sha256`/`bytes` nulos e o motivo:
        é o que faz o `MANIFEST.json` ser byte-idêntico entre duas execuções (CA-121) sem
        esconder que o arquivo existe. O hash dele aparece no resumo de tela, que descreve o
        disco; o manifesto registra só o que é reproduzível.
        """
        comum: dict[str, Any] = {
            "arquivo": self.arquivo,
            "colunas": self.colunas,
            "coluna_de_data": self.coluna_de_data,
            "date_max": self.date_max,
            "date_min": self.date_min,
            "determinista": self.determinista,
            "linhas": self.linhas,
            "nulos_por_coluna_pct": dict(sorted(self.nulos_por_coluna.items())),
            "pct_nulos": self.pct_nulos,
        }
        if not self.determinista:
            return {
                **comum,
                "bytes": None,
                "sha256": None,
                "motivo_sem_hash": (
                    "derivado e descartavel (ADR-006 (a).2); os bytes mudam a cada escrita, "
                    "entao registrar o hash tornaria o proprio MANIFEST.json nao reproduzivel"
                ),
            }
        return {**comum, "bytes": self.bytes, "sha256": self.sha256}


def _texto_de_data(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor)
    return texto[:10] if "T" in texto or " " in texto else texto


def _perfil_do_parquet(caminho: Path) -> dict[str, Any]:
    """Linhas, colunas, min/max da coluna de data e % de nulos **por coluna** (CA-118).

    Lido do Parquet, não do relatório da feature: o manifesto tem de poder ser conferido contra o
    arquivo publicado, mesmo que o relatório não exista.
    """
    import pandas as pd

    quadro = pd.read_parquet(caminho)
    linhas = int(len(quadro))
    nulos: dict[str, float] = {}
    for coluna in quadro.columns:
        n_nulos = int(quadro[coluna].isna().sum())
        if n_nulos:
            nulos[str(coluna)] = round(n_nulos * 100.0 / linhas, 6) if linhas else 0.0
    celulas = linhas * len(quadro.columns)
    coluna_de_data = next((c for c in COLUNAS_DE_DATA if c in quadro.columns), None)
    date_min = date_max = None
    if coluna_de_data is not None and linhas:
        serie = quadro[coluna_de_data].dropna()
        if len(serie):
            date_min = _texto_de_data(serie.min())
            date_max = _texto_de_data(serie.max())
    return {
        "linhas": linhas,
        "colunas": int(len(quadro.columns)),
        "coluna_de_data": coluna_de_data,
        "date_min": date_min,
        "date_max": date_max,
        "pct_nulos": round(int(quadro.isna().sum().sum()) * 100.0 / celulas, 6) if celulas else 0.0,
        "nulos_por_coluna": nulos,
    }


def inventariar(*, raiz: Path | None = None) -> tuple[Artefato, ...]:
    """Todo artefato de `data/canonical/`, **recursivo**, ordenado pelo caminho relativo.

    Recursivo de propósito: `data/canonical/figuras/` (F-025) é publicado junto com as tabelas, e
    artefato publicado que não está no manifesto é artefato que o `verify` não protege. O nome no
    manifesto é o caminho relativo em POSIX (`figuras/timeline_regimes_dados.parquet`), então a
    ordem do agregado é estável entre Windows e Linux.
    """
    pasta = caminho_camada(Camada.CANONICAL, raiz=raiz)
    if not pasta.is_dir():
        msg = (
            f"{pasta} não existe — nada a inventariar. Rode `python -m apps.pipeline run "
            f"--offline` (ou `--online`, se `data/processed/` também estiver vazio)."
        )
        raise ErroDeOrquestracao(msg)
    achados: list[Artefato] = []
    for caminho in sorted(pasta.rglob("*"), key=lambda p: p.as_posix()):
        if not caminho.is_file() or caminho.name in NAO_SAO_ARTEFATO:
            continue
        relativo = caminho.relative_to(pasta).as_posix()
        corpo = caminho.read_bytes()
        perfil = _perfil_do_parquet(caminho) if caminho.suffix == ".parquet" else {}
        achados.append(
            Artefato(
                arquivo=relativo,
                bytes=len(corpo),
                sha256=sha256_de(corpo),
                determinista=relativo not in NAO_DETERMINISTICOS,
                **perfil,
            )
        )
    return tuple(achados)


def hash_agregado(artefatos: Iterable[Artefato]) -> str:
    """`sha256` do corpo `"<sha256>  <arquivo>\\n"` dos artefatos **deterministicos**, por nome.

    É o formato do `sha256sum` de `infra-ops.md §1.2` — assim o agregado do manifesto é
    reproduzível na linha de comando, sem este módulo:

    ```bash
    find data/canonical -type f -name '*.parquet' -o -name 'relatorio_*.json' | sort | \\
      xargs sha256sum | sed 's|data/canonical/||' | sha256sum
    ```
    """
    corpo = "".join(
        f"{a.sha256}  {a.arquivo}\n"
        for a in sorted(artefatos, key=lambda a: a.arquivo)
        if a.determinista
    )
    return sha256_de(corpo.encode("utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Manifesto
# ─────────────────────────────────────────────────────────────────────────────


def _versao_build_do_relatorio(valor: Any) -> str | None:
    """`str` em 6 relatorios; em `relatorio_retornos.json` e `{"modulos": [...], "sha256": ...}`."""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, Mapping):
        sha = valor.get("sha256")
        return str(sha) if sha else None
    return None


def versoes_de_build(*, raiz: Path | None = None) -> dict[str, str]:
    """`versao_build` declarado por cada `relatorio_*.json` de `data/canonical/`.

    É a impressão digital do **código** que produziu o dado (`versao_build` hasheia os módulos da
    feature, com fim de linha normalizado — D-v (b)). Vai ao manifesto porque o gate da classe D
    exige "dataset congelado (versão + hash)": o `sha256` diz *o que* saiu, o `versao_build` diz
    *de que código*.
    """
    pasta = caminho_camada(Camada.CANONICAL, raiz=raiz)
    encontrados: dict[str, str] = {}
    for caminho in sorted(pasta.glob("relatorio_*.json")):
        try:
            conteudo = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        versao = _versao_build_do_relatorio(conteudo.get("versao_build"))
        if versao:
            encontrados[caminho.name] = versao
    return encontrados


def data_do_dado(*, raiz: Path | None = None) -> dict[str, str | None]:
    """A data **do dado**, nunca a do relógio: `date_max`/`vintage` do bruto e último trimestre.

    `FROZEN.txt` e o manifesto citam isto. Usar `datetime.now()` aqui tornaria o manifesto
    diferente entre duas execuções idênticas (quebrando CA-121) e faria o pacote do Comitê dizer
    "congelado em X" quando a pergunta do Alexandre é "até quando vai o dado".
    """
    pasta = caminho_camada(Camada.CANONICAL, raiz=raiz)

    def _ler(nome: str) -> dict[str, Any]:
        caminho = pasta / nome
        if not caminho.is_file():
            return {}
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    build = _ler("relatorio_build.json").get("raw_series", {})
    macro = _ler("relatorio_macro.json").get("macro_quarterly", {})
    vintages = build.get("vintages") or []
    return {
        "date_max_raw_series": build.get("date_max"),
        "date_min_raw_series": build.get("date_min"),
        "vintage_max": str(max(vintages)) if vintages else None,
        "ultimo_trimestre_macro": macro.get("ultimo_trimestre"),
        "primeiro_trimestre_macro": macro.get("primeiro_trimestre"),
    }


def commit_em_disco(*, raiz: Path | None = None) -> dict[str, str | None]:
    """Commit e ref correntes lidos de `.git/` — **sem** chamar `git` (nada é alterado).

    `freeze` registra o commit para o rollback poder reconstruir o que foi enviado
    (`infra-ops.md §1.3`). Criar a tag continua sendo ato humano: o módulo não executa git.
    """
    git = (raiz or raiz_repo()) / ".git"
    cabeca = git / "HEAD"
    if not cabeca.is_file():
        return {"commit": None, "ref": None}
    texto = cabeca.read_text(encoding="utf-8").strip()
    if not texto.startswith("ref: "):
        return {"commit": texto or None, "ref": None}
    ref = texto.removeprefix("ref: ").strip()
    arquivo = git / Path(ref)
    if arquivo.is_file():
        return {"commit": arquivo.read_text(encoding="utf-8").strip() or None, "ref": ref}
    empacotadas = git / "packed-refs"
    if empacotadas.is_file():
        for linha in empacotadas.read_text(encoding="utf-8").splitlines():
            if linha.endswith(f" {ref}"):
                return {"commit": linha.split(" ", 1)[0], "ref": ref}
    return {"commit": None, "ref": ref}


def montar_manifesto(
    *, raiz: Path | None = None, congelamento: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """O `MANIFEST.json` como dicionário — determinístico por construção (nada de relógio)."""
    artefatos = inventariar(raiz=raiz)
    deterministicos = [a for a in artefatos if a.determinista]
    return {
        "manifesto_versao": VERSAO_DO_MANIFESTO,
        "feature": "F-029",
        "convencao": {
            "agregado": (
                "sha256 do corpo '<sha256>  <arquivo>\\n' dos artefatos deterministicos, "
                "ordenados por nome, terminador LF (formato sha256sum)"
            ),
            "excluidos_do_agregado": sorted(NAO_DETERMINISTICOS),
            "nao_sao_artefato": sorted(NAO_SAO_ARTEFATO),
            "motivo_da_exclusao": (
                "ldc.duckdb e derivado e descartavel (ADR-006 (a).2: views sobre o Parquet) e "
                "nao e byte-reproduzivel: duas execucoes sobre o mesmo data/processed produzem "
                "o mesmo tamanho e sha256 diferente. Rode run --sem-duckdb para um diretorio "
                "integralmente deterministico."
            ),
        },
        "agregado": {
            "sha256": hash_agregado(artefatos),
            "n_artefatos": len(deterministicos),
            "n_artefatos_fora_do_agregado": len(artefatos) - len(deterministicos),
            "bytes": sum(a.bytes for a in deterministicos),
            "linhas": sum(a.linhas or 0 for a in deterministicos),
        },
        "artefatos": [a.como_dicionario() for a in artefatos],
        "versao_build": versoes_de_build(raiz=raiz),
        "data_do_dado": data_do_dado(raiz=raiz),
        "congelamento": dict(congelamento) if congelamento else None,
    }


def gravar_manifesto(manifesto: Mapping[str, Any], *, destino: Path) -> Path:
    """Grava o manifesto com `sort_keys` + `indent=2` + LF: dois `run` -> arquivo byte-idêntico."""
    garantir_diretorio(destino.parent)
    destino.write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destino


def caminho_do_manifesto(*, raiz: Path | None = None) -> Path:
    return caminho_camada(Camada.CANONICAL, raiz=raiz) / NOME_MANIFESTO


# ─────────────────────────────────────────────────────────────────────────────
# run
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EtapaExecutada:
    """Resultado de uma etapa: `pulada` só acontece em etapa opcional sem módulo."""

    nome: str
    fase: Fase
    situacao: str
    segundos: float
    detalhe: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoRodada:
    executadas: tuple[EtapaExecutada, ...]
    artefatos: tuple[Artefato, ...]
    agregado: str
    caminho_manifesto: Path | None
    segundos: float


def executar(
    *,
    raiz: Path | None = None,
    online: bool = False,
    reprocessar: bool = False,
    ate: str | None = None,
    so: str | None = None,
    com_duckdb: bool = True,
    com_opcionais: bool = True,
    escrever_manifesto: bool = True,
) -> ResultadoRodada:
    """Roda as etapas selecionadas **na ordem**, parando na primeira falha (CA-118).

    Levanta `FalhaDeEtapa` com a etapa nomeada e o comando de retomada. Nada é "continuado" com
    insumo faltando: a etapa seguinte leria o artefato da anterior e produziria número errado sem
    exceção, que é o modo de falha dominante deste projeto.
    """
    selecionadas = selecionar_etapas(
        online=online, reprocessar=reprocessar, ate=ate, so=so, com_opcionais=com_opcionais
    )
    ctx = Contexto(raiz=raiz, offline=not online, com_duckdb=com_duckdb)
    garantir_diretorio(caminho_camada(Camada.CANONICAL, raiz=raiz))
    executadas: list[EtapaExecutada] = []
    inicio_total = time.monotonic()
    for ordem, etapa in enumerate(selecionadas, start=1):
        rotulo = f"[{ordem}/{len(selecionadas)}] {etapa.nome}"
        if etapa.opcional and not modulo_disponivel(etapa.modulo_opcional or ""):
            _log.info("%s: pulada (modulo %s ausente)", rotulo, etapa.modulo_opcional)
            _imprimir(f"{rotulo}: PULADA - modulo {etapa.modulo_opcional} ainda nao existe")
            executadas.append(
                EtapaExecutada(
                    nome=etapa.nome,
                    fase=etapa.fase,
                    situacao="pulada",
                    segundos=0.0,
                    detalhe=f"modulo {etapa.modulo_opcional} ausente",
                )
            )
            continue
        _imprimir(f"{rotulo}: {etapa.descricao}")
        inicio = time.monotonic()
        try:
            etapa.executar(ctx)
        except ErroDeOrquestracao:
            raise
        except EtapaNaoChamavel as erro:
            if not etapa.opcional:
                raise FalhaDeEtapa(
                    _mensagem_de_falha(etapa, erro, online=online, raiz=raiz)
                ) from erro
            _log.warning("%s: pulada - %s", rotulo, erro)
            _imprimir(f"{rotulo}: PULADA - {erro}")
            executadas.append(
                EtapaExecutada(
                    nome=etapa.nome,
                    fase=etapa.fase,
                    situacao="pulada",
                    segundos=time.monotonic() - inicio,
                    detalhe="modulo presente, sem construir()/main() ainda",
                )
            )
            continue
        except Exception as erro:  # noqa: BLE001 - a etapa é código de terceiro deste repo
            decorrido = time.monotonic() - inicio
            executadas.append(
                EtapaExecutada(
                    nome=etapa.nome,
                    fase=etapa.fase,
                    situacao="falhou",
                    segundos=decorrido,
                    detalhe=f"{type(erro).__name__}: {erro}",
                )
            )
            raise FalhaDeEtapa(_mensagem_de_falha(etapa, erro, online=online, raiz=raiz)) from erro
        decorrido = time.monotonic() - inicio
        _log.info("%s: ok em %.1fs", rotulo, decorrido)
        executadas.append(
            EtapaExecutada(nome=etapa.nome, fase=etapa.fase, situacao="ok", segundos=decorrido)
        )
    artefatos = inventariar(raiz=raiz)
    caminho = None
    if escrever_manifesto:
        caminho = gravar_manifesto(
            montar_manifesto(raiz=raiz), destino=caminho_do_manifesto(raiz=raiz)
        )
    return ResultadoRodada(
        executadas=tuple(executadas),
        artefatos=artefatos,
        agregado=hash_agregado(artefatos),
        caminho_manifesto=caminho,
        segundos=time.monotonic() - inicio_total,
    )


def _mensagem_de_falha(
    etapa: Etapa, erro: BaseException, *, online: bool, raiz: Path | None
) -> str:
    """Mensagem acionável: etapa, fase, causa, o que NÃO rodou e como retomar."""
    modo = "--online" if online else "--offline"
    sufixo = f" --raiz {raiz}" if raiz is not None else ""
    posteriores = [e.nome for e in etapas()]
    seguintes = posteriores[posteriores.index(etapa.nome) + 1 :]
    pendentes = f"nao rodaram: {', '.join(seguintes)}" if seguintes else "era a ultima etapa"
    return (
        f"FALHA na etapa '{etapa.nome}' (fase {etapa.fase.value}) -> {type(erro).__name__}: "
        f"{erro}\n"
        f"  O pipeline PAROU aqui; {pendentes}.\n"
        f"  Retome so esta etapa com: python -m apps.pipeline run {modo} "
        f"--so {etapa.nome}{sufixo}\n"
        f"  Diagnostico: docs/wiki/runbooks/reconstruir-dataset.md (secao 5) | "
        f"docs/wiki/runbooks/fonte-fora-do-ar.md se a causa for a fonte."
    )


def imprimir_resumo(resultado: ResultadoRodada) -> None:
    """Resumo final de CA-118: etapas, linhas, min/max de data, % de nulos e hashes."""
    _imprimir()
    _imprimir("=== ETAPAS ===")
    for executada in resultado.executadas:
        detalhe = f" | {executada.detalhe}" if executada.detalhe else ""
        _imprimir(
            f"{executada.nome:<20} {executada.situacao:<7} {executada.segundos:>7.1f}s{detalhe}"
        )
    _imprimir()
    _imprimir("=== ARTEFATOS (data/canonical) ===")
    for artefato in resultado.artefatos:
        linhas = "-" if artefato.linhas is None else f"{artefato.linhas}"
        janela = (
            f" | {artefato.date_min} -> {artefato.date_max}"
            if artefato.date_min is not None
            else ""
        )
        nulos = "" if artefato.pct_nulos is None else f" | nulos {artefato.pct_nulos}%"
        marca = "" if artefato.determinista else " | NAO DETERMINISTICO (fora do agregado)"
        _imprimir(
            f"{artefato.arquivo:<42} {linhas:>8} linhas | {artefato.bytes:>9} B | "
            f"sha256 {artefato.sha256}{janela}{nulos}{marca}"
        )
        if artefato.nulos_por_coluna:
            itens = sorted(artefato.nulos_por_coluna.items(), key=lambda par: (-par[1], par[0]))
            mostradas = ", ".join(f"{col} {pct}%" for col, pct in itens[:MAX_COLUNAS_NO_RESUMO])
            resto = len(itens) - MAX_COLUNAS_NO_RESUMO
            extra = f" (+{resto} outras colunas com nulo)" if resto > 0 else ""
            _imprimir(f"{'':<42}   nulos por coluna: {mostradas}{extra}")
    _imprimir()
    _imprimir(f"AGREGADO sha256: {resultado.agregado}")
    if resultado.caminho_manifesto is not None:
        _imprimir(f"manifesto: {resultado.caminho_manifesto}")
    _imprimir(f"tempo total: {resultado.segundos:.1f}s")


# ─────────────────────────────────────────────────────────────────────────────
# verify
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Divergencia:
    arquivo: str
    situacao: str
    esperado: str | None
    obtido: str | None
    #: Divergência em artefato declarado não determinístico — reportada, nunca reprovada.
    informativa: bool = False


@dataclass(frozen=True, slots=True)
class ResultadoVerificacao:
    caminho_manifesto: Path
    conferidos: int
    agregado_esperado: str | None
    agregado_obtido: str
    divergencias: tuple[Divergencia, ...]

    @property
    def graves(self) -> tuple[Divergencia, ...]:
        return tuple(d for d in self.divergencias if not d.informativa)

    @property
    def ok(self) -> bool:
        return not self.graves


def verificar(
    *, raiz: Path | None = None, caminho_manifesto: Path | None = None
) -> ResultadoVerificacao:
    """Recalcula o `sha256` de `data/canonical/*` e confere contra o `MANIFEST.json` (CA-121).

    Detecta byte alterado, artefato ausente, artefato novo não listado e agregado divergente.
    Divergência em `ldc.duckdb` é **informativa** (decisão 3 do módulo).
    """
    alvo = caminho_manifesto or caminho_do_manifesto(raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"{alvo} não existe: não há manifesto com que comparar. Gere um com "
            f"`python -m apps.pipeline run --offline` ou "
            f"`python -m apps.pipeline freeze --tag <tag>`."
        )
        raise ErroDeOrquestracao(msg)
    try:
        manifesto = json.loads(alvo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        msg = f"{alvo} não é JSON válido ({erro}) — regere o manifesto antes de verificar."
        raise ErroDeOrquestracao(msg) from erro
    esperados = {
        str(item["arquivo"]): item for item in manifesto.get("artefatos", []) if "arquivo" in item
    }
    atuais = {artefato.arquivo: artefato for artefato in inventariar(raiz=raiz)}
    divergencias: list[Divergencia] = []
    for nome in sorted(set(esperados) | set(atuais)):
        declarado = esperados.get(nome)
        atual = atuais.get(nome)
        informativa = nome in NAO_DETERMINISTICOS or (
            declarado is not None and declarado.get("determinista") is False
        )
        if atual is None:
            divergencias.append(
                Divergencia(
                    nome,
                    "ausente em disco",
                    str((declarado or {}).get("sha256")),
                    None,
                    informativa,
                )
            )
        elif declarado is None:
            divergencias.append(
                Divergencia(nome, "nao listado no manifesto", None, atual.sha256, informativa)
            )
        elif declarado.get("sha256") is None:
            # Artefato declarado não determinístico: o manifesto não guarda hash dele, então não
            # há o que conferir. Reportado para que a ausência de conferência fique visível.
            divergencias.append(
                Divergencia(nome, "hash nao conferido (derivado)", None, atual.sha256, True)
            )
        elif str(declarado.get("sha256")) != atual.sha256:
            divergencias.append(
                Divergencia(
                    nome,
                    "sha256 divergente",
                    str(declarado.get("sha256")),
                    atual.sha256,
                    informativa,
                )
            )
    agregado_esperado = (manifesto.get("agregado") or {}).get("sha256")
    agregado_obtido = hash_agregado(atuais.values())
    if agregado_esperado and agregado_esperado != agregado_obtido:
        divergencias.append(
            Divergencia("<agregado>", "agregado divergente", agregado_esperado, agregado_obtido)
        )
    return ResultadoVerificacao(
        caminho_manifesto=alvo,
        conferidos=len(atuais),
        agregado_esperado=str(agregado_esperado) if agregado_esperado else None,
        agregado_obtido=agregado_obtido,
        divergencias=tuple(divergencias),
    )


def imprimir_verificacao(resultado: ResultadoVerificacao) -> None:
    _imprimir(f"manifesto: {resultado.caminho_manifesto}")
    _imprimir(f"artefatos conferidos: {resultado.conferidos}")
    _imprimir(f"agregado esperado: {resultado.agregado_esperado}")
    _imprimir(f"agregado obtido:   {resultado.agregado_obtido}")
    for divergencia in resultado.divergencias:
        marca = "INFO" if divergencia.informativa else "FALHA"
        _imprimir(
            f"{marca} {divergencia.arquivo}: {divergencia.situacao} | "
            f"esperado {divergencia.esperado} | obtido {divergencia.obtido}"
        )
    _imprimir("VERIFY OK" if resultado.ok else "VERIFY FALHOU")


# ─────────────────────────────────────────────────────────────────────────────
# freeze
# ─────────────────────────────────────────────────────────────────────────────

_TAG_PERMITIDA = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_")

ROLLBACK: tuple[str, ...] = (
    "1. Nao enviar. Se ja enviado: e-mail de correcao citando esta tag e o DATASET_SHA256 acima,",
    "   dizendo qual tabela/coluna tem problema e que o numero nao deve ser usado.",
    "2. Marcar a versao como revogada em docs/wiki/log.md ([REVOKED], com tag e hash) e",
    "   restaurar a versao anterior de data/canonical/.",
    "3. Reconstruir do data/raw arquivado: python -m apps.pipeline run --offline",
    "4. Rodar o diff numerico vs. a versao enviada e comunicar CADA divergencia (F-031).",
    "5. Conferir antes de qualquer reenvio: python -m apps.pipeline verify  (tem de sair 0).",
    "6. Versao corrigida sai com tag NOVA (nunca git tag -f) - infra-ops.md 1.3 e 1.6.",
)


def _validar_tag(tag: str) -> str:
    if not tag or set(tag) - _TAG_PERMITIDA:
        msg = (
            f"tag {tag!r} inválida: use só ASCII `[A-Za-z0-9._-]` (ex.: `comite-2026-10-14`). A "
            f"tag vai para `FROZEN.txt` e para o `git tag` que o humano cria depois."
        )
        raise ErroDeOrquestracao(msg)
    return tag


def _validar_saida(saida: Path | None, *, raiz: Path | None) -> Path:
    """`--saida` tem de ficar dentro de `<raiz>/data` — o módulo não escreve fora de `data/`."""
    base = caminho_camada(Camada.CANONICAL, raiz=raiz)
    if saida is None:
        return base
    alvo = Path(saida).resolve()
    pasta_de_dados = ((raiz or raiz_repo()) / "data").resolve()
    if pasta_de_dados != alvo and pasta_de_dados not in alvo.parents:
        msg = (
            f"--saida {alvo} está fora de {pasta_de_dados}: este módulo nunca escreve fora de "
            f"`data/`. Para congelar num diretório de teste, aponte `--raiz` para a árvore de "
            f"teste (ela precisa ter `data/canonical/`) e deixe `--saida` dentro dela."
        )
        raise ErroDeOrquestracao(msg)
    return alvo


@dataclass(frozen=True, slots=True)
class ResultadoCongelamento:
    tag: str
    caminho_manifesto: Path
    caminho_frozen: Path
    agregado: str
    manifesto: Mapping[str, Any]


def texto_frozen(manifesto: Mapping[str, Any]) -> str:
    """`FROZEN.txt` — ASCII, legível por humano, com tag, data **do dado** e rollback."""
    congelamento = manifesto.get("congelamento") or {}
    agregado = manifesto.get("agregado") or {}
    datas = manifesto.get("data_do_dado") or {}
    linhas = [
        "DATASET CONGELADO - estrategia-macro-ldc-dados (F-029)",
        "",
        f"tag                 : {congelamento.get('tag')}",
        f"DATASET_SHA256      : {agregado.get('sha256')}",
        f"artefatos no hash   : {agregado.get('n_artefatos')}",
        f"fora do hash        : {agregado.get('n_artefatos_fora_do_agregado')} "
        f"({', '.join(sorted(NAO_DETERMINISTICOS))} - derivado, nao reproduzivel byte a byte)",
        f"git commit          : {congelamento.get('git_commit')}",
        f"git ref             : {congelamento.get('git_ref')}",
        "",
        "DATA DO DADO (nao do relogio - nada aqui le datetime.now)",
        f"  raw_series        : {datas.get('date_min_raw_series')} -> "
        f"{datas.get('date_max_raw_series')}",
        f"  vintage mais novo : {datas.get('vintage_max')}",
        f"  macro_quarterly   : {datas.get('primeiro_trimestre_macro')} -> "
        f"{datas.get('ultimo_trimestre_macro')}",
        "",
        "VERSAO DE BUILD POR RELATORIO (sha256 dos modulos que produziram o dado)",
    ]
    for nome, versao in sorted((manifesto.get("versao_build") or {}).items()):
        linhas.append(f"  {nome:<34} {versao}")
    linhas += [
        "",
        "COMO CONFERIR",
        "  python -m apps.pipeline verify",
        "  (recalcula o sha256 de data/canonical/* e compara com MANIFEST.json; sai != 0 se",
        "   qualquer artefato deterministico divergir)",
        "",
        "ROLLBACK (obrigatorio em classe D - docs/plans/infra-ops.md 1.6)",
        *ROLLBACK,
        "",
        "Este arquivo e gerado por apps/pipeline/run.py. Nao edite a mao (Anti-SPEC 10.4.22).",
    ]
    return para_ascii("\n".join(linhas) + "\n")


def congelar(
    *, tag: str, raiz: Path | None = None, saida: Path | None = None
) -> ResultadoCongelamento:
    """Escreve `MANIFEST.json` + `FROZEN.txt` com a tag, o commit e o rollback. Não chama git."""
    tag = _validar_tag(tag)
    destino = _validar_saida(saida, raiz=raiz)
    git = commit_em_disco(raiz=raiz)
    # O agregado é calculado antes para poder entrar na instrução de tag: o `git tag -a` do
    # `infra-ops.md §1.3` cita o `DATASET_SHA256` na própria mensagem da tag.
    agregado = hash_agregado(inventariar(raiz=raiz))
    manifesto = montar_manifesto(
        raiz=raiz,
        congelamento={
            "tag": tag,
            "git_commit": git["commit"],
            "git_ref": git["ref"],
            "rollback": list(ROLLBACK),
            "instrucao_de_tag": (
                f'git tag -a {tag} -m "dataset congelado - DATASET_SHA256={agregado}"'
                f" (ato humano: este modulo nao executa git)"
            ),
        },
    )
    caminho_manifesto = gravar_manifesto(manifesto, destino=destino / NOME_MANIFESTO)
    caminho_frozen = destino / NOME_FROZEN
    garantir_diretorio(caminho_frozen.parent)
    caminho_frozen.write_text(texto_frozen(manifesto), encoding="utf-8")
    return ResultadoCongelamento(
        tag=tag,
        caminho_manifesto=caminho_manifesto,
        caminho_frozen=caminho_frozen,
        agregado=str((manifesto["agregado"])["sha256"]),
        manifesto=manifesto,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline",
        description=(
            "Orquestrador do pipeline (F-029): reconstroi data/raw -> data/processed -> "
            "data/canonical com um comando, confere o hash e congela o dataset."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    run = sub.add_parser(
        "run",
        help="reconstroi o pipeline na ordem e grava data/canonical/MANIFEST.json",
        description=(
            "Roda as etapas na ordem e para na primeira falha. --offline reconstroi de "
            "data/processed (sem rede); --online extrai das fontes antes."
        ),
    )
    modo = run.add_mutually_exclusive_group(required=True)
    modo.add_argument(
        "--offline",
        action="store_true",
        help="nao toca a rede: reconstroi de data/processed (e data/raw com --reprocessar)",
    )
    modo.add_argument(
        "--online", action="store_true", help="roda os 9 extratores contra as fontes vivas"
    )
    run.add_argument(
        "--reprocessar",
        action="store_true",
        help="com --offline: reprocessa data/raw -> data/processed antes do canonico",
    )
    run.add_argument("--ate", metavar="ETAPA", help="roda da primeira etapa ate esta (inclusive)")
    run.add_argument("--so", metavar="ETAPA", help="roda exatamente uma etapa")
    run.add_argument(
        "--raiz",
        type=Path,
        help="arvore alternativa com data/ (usada pelos testes; invalida nas etapas de extracao)",
    )
    run.add_argument(
        "--sem-duckdb",
        action="store_true",
        help="pula o ldc.duckdb derivado - deixa data/canonical/ integralmente deterministico",
    )
    run.add_argument(
        "--sem-opcionais", action="store_true", help="pula as etapas opcionais (F-022, F-025)"
    )
    run.add_argument(
        "--sem-manifesto", action="store_true", help="nao grava MANIFEST.json ao final"
    )
    run.add_argument(
        "--listar-etapas", action="store_true", help="lista a ordem das etapas e sai (nao roda)"
    )

    verify = sub.add_parser(
        "verify",
        help="recalcula o sha256 de data/canonical/* e compara com o MANIFEST.json",
        description="Sai com codigo != 0 se qualquer artefato deterministico divergir (CA-121).",
    )
    verify.add_argument("--raiz", type=Path, help="arvore alternativa com data/")
    verify.add_argument("--manifesto", type=Path, help="manifesto a usar (default: o do canonical)")

    freeze = sub.add_parser(
        "freeze",
        help="grava MANIFEST.json + FROZEN.txt com tag, commit e rollback",
        description=(
            "Congela data/canonical/: hash por artefato, hash agregado, versao_build de cada "
            "relatorio, commit lido de .git/HEAD e instrucao de rollback. Nao executa git."
        ),
    )
    freeze.add_argument("--tag", required=True, help="ex.: comite-2026-10-14")
    freeze.add_argument("--raiz", type=Path, help="arvore alternativa com data/")
    freeze.add_argument(
        "--saida",
        type=Path,
        help="diretorio de destino (default: data/canonical; tem de ficar dentro de <raiz>/data)",
    )
    return parser


def _listar_etapas(*, online: bool, reprocessar: bool, com_opcionais: bool) -> int:
    for ordem, etapa in enumerate(
        selecionar_etapas(online=online, reprocessar=reprocessar, com_opcionais=com_opcionais),
        start=1,
    ):
        marca = " [opcional]" if etapa.opcional else ""
        _imprimir(f"{ordem:>2}. {etapa.nome:<20} {etapa.fase.value:<15} {etapa.descricao}{marca}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada. `0` = tudo certo; `1` = falha explícita (sem traceback)."""
    args = _parser().parse_args(argv)
    configurar_logging()
    try:
        if args.comando == "run":
            if args.listar_etapas:
                return _listar_etapas(
                    online=args.online,
                    reprocessar=args.reprocessar,
                    com_opcionais=not args.sem_opcionais,
                )
            if args.reprocessar and args.online:
                msg = "--reprocessar só vale com --offline (em --online a extração já é a fonte)."
                raise ErroDeOrquestracao(msg)
            _imprimir(f"raiz: {args.raiz or raiz_repo()}")
            _imprimir(f"modo: {'online' if args.online else 'offline'}")
            resultado = executar(
                raiz=args.raiz,
                online=args.online,
                reprocessar=args.reprocessar,
                ate=args.ate,
                so=args.so,
                com_duckdb=not args.sem_duckdb,
                com_opcionais=not args.sem_opcionais,
                escrever_manifesto=not args.sem_manifesto,
            )
            imprimir_resumo(resultado)
            return 0
        if args.comando == "verify":
            resultado = verificar(raiz=args.raiz, caminho_manifesto=args.manifesto)
            imprimir_verificacao(resultado)
            return 0 if resultado.ok else 1
        congelado = congelar(tag=args.tag, raiz=args.raiz, saida=args.saida)
        _imprimir(f"tag: {congelado.tag}")
        _imprimir(f"DATASET_SHA256: {congelado.agregado}")
        _imprimir(f"manifesto: {congelado.caminho_manifesto}")
        _imprimir(f"frozen: {congelado.caminho_frozen}")
        _imprimir("git: NAO executado (crie a tag a mao - infra-ops.md 1.3)")
        return 0
    except ErroDeExtracao as erro:
        print(para_ascii(f"FALHA: {erro}"), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
