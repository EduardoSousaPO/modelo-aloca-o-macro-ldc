"""F-031 — monta o pacote de entrega ao Comitê **sem publicar** + smoke test do pacote.

```bash
python -m apps.analysis.entrega.montar_pacote                 # monta o pacote + .zip
python -m apps.analysis.entrega.montar_pacote --smoke         # monta e roda o smoke
python -m apps.analysis.entrega.montar_pacote --so-smoke      # só o smoke, sobre o pacote em disco
python -m apps.analysis.entrega.montar_pacote --saida DIR     # outro destino (dentro de `data/`)
```

**O que este módulo NÃO faz, de propósito:** não envia nada, não roda `freeze`, não cria `git tag`,
não reconstrói o canônico e não calcula um único número. Os 8 passos do gate da classe D estão em
`docs/wiki/runbooks/entrega-comite.md`; este módulo é o **passo 6** (smoke) e a preparação física
dos passos 1-5. Enquanto o ADR-001 estiver em `Proposta`, o pacote existe mas **não sai**.

## O conteúdo (lista de inclusão fechada)

| Pasta do pacote | O que vai | Vem de |
|---|---|---|
| raiz | `README-COMITE.md`, `LIMITACOES-COMITE.md`, `SUBSTITUICOES-DE-FONTE.md`,
  `PACOTE-COMITE.xlsx`, `MANIFEST.json`, `FROZEN.txt`, `HASHES.txt` | gerado / copiado |
| `dados/` | as **10** tabelas de `TABELAS_DO_PACOTE`, em **Parquet** (cópia byte a byte)
  **e** CSV pt-BR | `data/canonical/*.parquet` |
| `figuras/` | 2 timelines + 3 heatmaps, em PNG **e** SVG | `data/canonical/figuras/` |
| `tabelas/` | ranking e concordância, em `.md` **e** `.csv` | `data/canonical/tabelas/` |
| `notebook/` | o caderno `.ipynb` **limpo** (versionado) + o HTML **executado** |
  `apps/analysis/notebooks/`, `data/canonical/entrega/` |

**Excluído por leitura do manifesto (D-af):** todo artefato com `publicavel: false` —
hoje `internacional_pesos.parquet` (Anti-SPEC §10.3.16/§10.5). O módulo **recusa** montar se um
nome da lista de inclusão estiver marcado como não publicável: a lista não vence o manifesto.
**Excluído por omissão:** tudo o que não está na lista (`raw_series`, `alinhado_trimestral`,
`series_catalog`, os `*_provenance`, `regime_neighbors` da V1, `ldc.duckdb` e os `relatorio_*.json`
— que seguem disponíveis no repositório para quem for reproduzir).

## Convenções do CSV (declaradas no `README-COMITE.md` e na aba `Leia-me`)

Separador `;` · decimal `,` · encoding **UTF-8 com BOM** · fim de linha `LF` · sem índice. O BOM é
o que faz o Excel em português abrir o arquivo com as colunas separadas sem passar pelo assistente
de importação; o `;` é o separador de lista do Windows pt-BR.

## Determinismo (CA-121 aplicado ao pacote)

Nada aqui lê o relógio: as propriedades do XLSX e os timestamps das entradas do `.zip` são
constantes (`DATA_FIXA_DO_PACOTE`, `DATA_FIXA_NO_ZIP`), a ordem das entradas é a ordem alfabética
do caminho POSIX e o `.xlsx` é **re-zipado** depois de o `openpyxl` gravá-lo, porque o `openpyxl`
grava o timestamp corrente em cada entrada do zip interno. Duas montagens ⇒ mesmo `sha256` do
`.zip`.

Cobre: CA-113 (conteúdo nos dois formatos + figuras + 1-páginas + README com versão e hash) ·
CA-114 (nenhum arquivo editado à mão: tudo sai daqui) · CA-115/CA-116 (o selo e o veredito de
bloqueio vêm do gate em disco) · CA-117 (`SUBSTITUICOES-DE-FONTE.md`) · CA-121 (idempotência).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.analysis import _linguagem
from apps.analysis.tabelas.ranking_regime_atual import (
    MARCA_NAO_CONGELADA,
    MARCA_NAO_CONGELADA_ASCII,
    respostas_do_regime_atual,
    vizinhos_do_quarter,
)
from apps.pipeline.canonical.regimes_v1 import especificacao_esta_congelada, status_adr_001
from apps.pipeline.canonical.regimes_v3 import QUARTER_DO_COMITE
from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, raiz_repo
from apps.pipeline.run import (
    ARTEFATOS_NAO_PUBLICAVEIS,
    NOME_FROZEN,
    NOME_MANIFESTO,
    commit_em_disco,
    para_ascii,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

_log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Identidade do pacote
# ─────────────────────────────────────────────────────────────────────────────

NOME_DO_PACOTE = "pacote_comite_2026-10-14"
"""Nome do diretório e do `.zip`. A data é a da reunião do Comitê, não a da montagem."""

TAG_DA_ENTREGA = "comite-2026-10-14"
"""A tag git que o **humano** cria no passo 4 do gate (`infra-ops.md §1.3`). Aqui é só texto."""

VERSAO_DO_PACOTE = "v1.0"
FEATURE = "F-031"

SUBPASTA_ENTREGA = "entrega"
"""`data/canonical/entrega/` — onde F-027 já grava o HTML executado."""

NOME_README = "README-COMITE.md"
NOME_LIMITACOES = "LIMITACOES-COMITE.md"
NOME_SUBSTITUICOES = "SUBSTITUICOES-DE-FONTE.md"
NOME_XLSX = "PACOTE-COMITE.xlsx"
NOME_HASHES = "HASHES.txt"

DATA_FIXA_DO_PACOTE = datetime(2026, 10, 14, 0, 0, 0)  # noqa: DTZ001 - constante, não é relógio
"""Propriedades do XLSX. Constante amarrada à reunião: `datetime.now()` quebraria CA-121."""

DATA_FIXA_NO_ZIP = (1980, 1, 1, 0, 0, 0)
"""O menor timestamp que o formato ZIP representa. Igual em toda entrada, em qualquer máquina."""

NIVEL_DE_COMPRESSAO = 9
"""Fixo: o nível muda os bytes comprimidos, logo muda o `sha256` do `.zip`."""

# ─────────────────────────────────────────────────────────────────────────────
# Lista de inclusão — fechada, e conferida contra o `MANIFEST.json`
# ─────────────────────────────────────────────────────────────────────────────

TABELAS_DO_PACOTE: tuple[str, ...] = (
    "macro_quarterly",
    "macro_quarterly_asof",
    "asset_returns_quarterly",
    "regimes_v1",
    "regimes_v1_asof",
    "regime_neighbors_v3",
    "regime_asset_metrics",
    "regime_asset_metrics_asof",
    "regime_asset_metrics_horizonte_cruzado",
    "internacional_por_regime",
)
"""As 10 tabelas do pacote mínimo. `internacional_pesos` **não** está aqui (Anti-SPEC §10.5)."""

FIGURAS_DO_PACOTE: tuple[str, ...] = (
    "timeline_regimes_revised",
    "timeline_regimes_asof",
    "heatmap_v1_revised",
    "heatmap_v1_asof",
    "heatmap_horizonte_cruzado",
)
"""2 timelines + 3 heatmaps. Cada uma entra em `.png` **e** `.svg`."""

EXTENSOES_DE_FIGURA: tuple[str, ...] = ("png", "svg")

TABELAS_DE_UMA_PAGINA: tuple[str, ...] = ("ranking_regime_atual", "concordancia_lentes")
"""As duas tabelas de 1 página de F-024. Cada uma entra em `.md` **e** `.csv`."""

EXTENSOES_DE_TABELA: tuple[str, ...] = ("md", "csv")

NOME_NOTEBOOK = "entrega_comite_2026-10-14"
CAMINHO_NOTEBOOK_LIMPO = Path("apps/analysis/notebooks") / f"{NOME_NOTEBOOK}.ipynb"
CAMINHO_NOTEBOOK_HTML = Path(SUBPASTA_ENTREGA) / f"{NOME_NOTEBOOK}.html"

CAMINHO_LIMITACOES = Path("docs/product") / NOME_LIMITACOES
CAMINHO_DECISIONS_LOG = Path("docs/plans/DECISIONS_LOG.md")

# ─────────────────────────────────────────────────────────────────────────────
# CSV pt-BR
# ─────────────────────────────────────────────────────────────────────────────

CSV_SEPARADOR = ";"
CSV_DECIMAL = ","
CSV_ENCODING = "utf-8-sig"
"""UTF-8 **com BOM**: é o que faz o Excel pt-BR abrir sem o assistente de importação."""
CSV_FIM_DE_LINHA = "\n"

# ─────────────────────────────────────────────────────────────────────────────
# Nulos legítimos — contagens travadas (o oposto de "ignore os nulos")
# ─────────────────────────────────────────────────────────────────────────────

COLUNAS_CRITICAS: dict[str, tuple[str, ...]] = {
    "macro_quarterly": ("quarter", "quarter_end", "fonte_versao"),
    "macro_quarterly_asof": ("quarter", "quarter_end", "fonte_versao", "lag_adjusted"),
    "asset_returns_quarterly": (
        "quarter",
        "asset_id",
        "source",
        "series_id",
        "fonte_versao",
        "data_inicio_serie",
    ),
    "regimes_v1": (
        "quarter",
        "status_regime_v1",
        "n_obs_regime_v1",
        "fonte_versao",
        "especificacao_congelada",
    ),
    "regimes_v1_asof": ("quarter", "status_regime_v1", "n_obs_regime_v1", "fonte_versao"),
    "regime_neighbors_v3": (
        "quarter_ref",
        "rank",
        "quarter_neighbor",
        "distancia",
        "metrica",
        "k_usado",
        "fonte_versao",
    ),
    "regime_asset_metrics": ("lente", "regime", "asset_id", "n_obs", "ret_medio", "excesso_cdi"),
    "regime_asset_metrics_asof": (
        "lente",
        "regime",
        "asset_id",
        "n_obs",
        "ret_medio",
        "excesso_cdi",
    ),
    "regime_asset_metrics_horizonte_cruzado": (
        "lente",
        "regime",
        "asset_id",
        "n_obs",
        "ret_medio",
        "excesso_cdi",
    ),
    "internacional_por_regime": (
        "lente",
        "regime",
        "asset_id",
        "n_obs",
        "ret_medio",
        "excesso_cdi",
        "especificacao_congelada",
    ),
}
"""Por tabela, as colunas que **não** admitem nulo. `regime_v1` e `ret_tri` ficam fora porque
têm nulo legítimo e **contado** — ver `NULOS_LEGITIMOS`."""

N_ANCORAS_SEM_RETORNO = 23
"""`asset_returns_quarterly`: o **primeiro** trimestre de cada série não tem retorno (sem
`price_ini`). 23 dos 24 ativos têm essa linha-âncora; o CDI não (é taxa acumulada, não preço).
Travado como número: se virar 24 ou 22, o painel mudou e o smoke avisa."""

N_TRIMESTRES_INDETERMINADOS = 16
"""`regimes_v1`/`regimes_v1_asof`: `regime_v1` é nulo nos 16 trimestres `INDETERMINADO`
(2006Q1-2009Q3 + 2026Q3). O nulo **é** o resultado (D-m); o que o smoke exige é que ele apareça
exatamente onde `status_regime_v1 == INDETERMINADO`."""

STATUS_INDETERMINADO = "INDETERMINADO"

NULOS_LEGITIMOS: tuple[str, ...] = (
    f"`asset_returns_quarterly`: {N_ANCORAS_SEM_RETORNO} linhas sem `ret_tri`/`ret_excesso_cdi` — "
    "o primeiro trimestre de cada série, que não tem preço inicial para medir retorno",
    f"`regimes_v1` e `regimes_v1_asof`: {N_TRIMESTRES_INDETERMINADOS} linhas sem `regime_v1` — "
    f"os trimestres com `status_regime_v1 = {STATUS_INDETERMINADO}`",
)

# ─────────────────────────────────────────────────────────────────────────────
# XLSX — abas, fonte e formatos pt-BR
# ─────────────────────────────────────────────────────────────────────────────

ABA_LEIA_ME = "Leia-me"
ABA_REGIME_ATUAL = "Regime atual"
ABA_HEATMAP = "Heatmap"
ABA_VIZINHOS = "Vizinhos 3T2026"
ABA_MACRO = "Macro trimestral"
ABA_RETORNOS = "Retornos trimestrais"
ABA_LIMITACOES = "Limitações"
ABA_DECISOES = "Decisões"

ABAS_ESPERADAS: tuple[str, ...] = (
    ABA_LEIA_ME,
    ABA_REGIME_ATUAL,
    ABA_HEATMAP,
    ABA_VIZINHOS,
    ABA_MACRO,
    ABA_RETORNOS,
    ABA_LIMITACOES,
    ABA_DECISOES,
)

FONTE_DO_PACOTE = "Arial"
TAMANHO_DA_FONTE = 10

#: `[$-416]` é o LCID de português (Brasil): força vírgula decimal e ponto de milhar **no
#: arquivo**, em vez de depender do idioma do Windows de quem abre.
LOCALE_PT_BR = "[$-416]"
FORMATO_PERCENTUAL = f"{LOCALE_PT_BR}0.00%"
FORMATO_NUMERO = f"{LOCALE_PT_BR}#,##0.0000"
FORMATO_INTEIRO = f"{LOCALE_PT_BR}#,##0"

COLUNAS_PERCENTUAIS: frozenset[str] = frozenset(
    {
        "ret_tri",
        "ret_excesso_cdi",
        "ret_real",
        "excesso_cdi",
        "ret_medio",
        "ret_mediana",
        "ret_desvio",
        "erro_padrao_media",
        "hit_ratio",
        "hit_ratio_cdi",
        "pior_tri",
        "melhor_tri",
        "vol_intra_tri",
        "dd_intra_tri",
    }
)
"""Colunas gravadas em **fração** no canônico e exibidas como percentual no XLSX."""

COLUNAS_INTEIRAS: frozenset[str] = frozenset(
    {
        "n_obs",
        "n_obs_regime_v1",
        "n_dias_uteis",
        "ffill_dias_uteis",
        "rank",
        "k_usado",
        "n_vizinhos",
        "n_features",
        "n_pares_ibov",
        "n_pares_imab",
        "posicao",
        "linha",
        "coluna",
    }
)

LARGURA_MAXIMA_DA_COLUNA = 46
LIMITE_DE_CARACTERES_NA_CELULA = 32000
"""O limite do formato é 32.767; cortamos antes e declaramos o corte."""

#: A matriz do mapa de calor: 23 ativos (linhas) × 5 regimes (colunas), com `n` ao lado do valor.
VISTA_DO_HEATMAP = "v1_revised"
NOME_HEATMAP_DADOS = "figuras/heatmap_dados.parquet"
N_ATIVOS_NO_HEATMAP = 23
N_REGIMES_NO_HEATMAP = 5

N_LIMITACOES = 10
N_DECISOES = 12
N_COLUNAS_DO_BLOCO_A = 9
"""As 9 colunas do bloco A de F-024 — as três respostas a "em que regime estamos"."""

# ─────────────────────────────────────────────────────────────────────────────
# Gate de publicação (CA-090) — lido do disco, nunca digitado
# ─────────────────────────────────────────────────────────────────────────────

TEXTO_DO_GATE_NAO_PUBLICAVEL = "NÃO PUBLICÁVEL — ESPECIFICAÇÃO NÃO CONGELADA"
"""O selo que vai no topo do README, da aba `Leia-me`, do `HASHES.txt` e das abas de número.

É a versão sem redundância de `MARCA_NAO_CONGELADA` (que já termina em "não publicável"): o selo
aqui **abre** com o veredito, porque é a primeira linha que o gestor lê."""

MARCADOR_DO_GATE = "NÃO PUBLICÁVEL"
"""O que o smoke procura em README/XLSX/notebook enquanto o ADR-001 estiver em `Proposta`."""

VEREDITO_BLOQUEADO = "BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA"
VEREDITO_LIBERADO_PELO_ADR = "ADR-001 aceito — passo 2 do gate cumprido"


@dataclass(frozen=True, slots=True)
class Gate:
    """O estado do gate de publicação, como está **em disco** neste instante."""

    status_adr_001: str
    congelada: bool

    @property
    def veredito(self) -> str:
        """O texto curto que vai ao topo de todo artefato do pacote."""
        return VEREDITO_LIBERADO_PELO_ADR if self.congelada else VEREDITO_BLOQUEADO

    @property
    def selo(self) -> str:
        """O selo de não publicável — vazio quando o ADR-001 está aceito."""
        return "" if self.congelada else TEXTO_DO_GATE_NAO_PUBLICAVEL


def ler_gate(*, raiz: Path | None = None) -> Gate:
    """O gate de CA-090: status do ADR-001 em disco + se a especificação está congelada.

    Falha fechada por construção — `status_adr_001` devolve `DESCONHECIDO` para arquivo ausente
    ou ilegível, e `DESCONHECIDO` **não** congela nada.
    """
    return Gate(
        status_adr_001=status_adr_001(raiz=raiz),
        congelada=especificacao_esta_congelada(raiz=raiz),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Manifesto: a autoridade sobre o que pode sair
# ─────────────────────────────────────────────────────────────────────────────


def caminho_do_pacote(*, raiz: Path | None = None) -> Path:
    """`data/canonical/entrega/pacote_comite_2026-10-14/` — o destino padrão."""
    return caminho_canonical(SUBPASTA_ENTREGA, raiz=raiz) / NOME_DO_PACOTE


def ler_manifesto(*, raiz: Path | None = None) -> dict[str, Any]:
    """`data/canonical/MANIFEST.json` como dicionário. Ausente ⇒ `BLOQUEADO`."""
    alvo = caminho_canonical(NOME_MANIFESTO, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {NOME_MANIFESTO} não existe em {alvo.parent}. "
            "Rode `python -m apps.pipeline run --offline` antes de montar o pacote."
        )
        raise SerieInconsistente(msg)
    return json.loads(alvo.read_text(encoding="utf-8"))


def artefatos_do_manifesto(manifesto: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """`{caminho relativo POSIX: entrada}` — o índice do manifesto por nome de arquivo."""
    entradas = manifesto.get("artefatos") or ()
    return {
        str(entrada["arquivo"]): dict(entrada)
        for entrada in entradas
        if isinstance(entrada, dict) and entrada.get("arquivo")
    }


def nao_publicaveis(manifesto: Mapping[str, Any]) -> dict[str, str]:
    """`{arquivo: motivo}` dos artefatos que o manifesto marca `publicavel: false` (**D-af**).

    A fonte de verdade é o **manifesto em disco**, não a constante do `run.py` — a constante
    entra só como complemento do motivo quando o manifesto não o escreveu.
    """
    marcados: dict[str, str] = {}
    for nome, entrada in artefatos_do_manifesto(manifesto).items():
        if entrada.get("publicavel") is False:
            marcados[nome] = str(
                entrada.get("motivo_nao_publicavel")
                or ARTEFATOS_NAO_PUBLICAVEIS.get(nome)
                or "marcado publicavel: false no MANIFEST.json"
            )
    return marcados


def dataset_sha256(manifesto: Mapping[str, Any]) -> str:
    """O `DATASET_SHA256` — o agregado do manifesto, que amarra o pacote ao dataset."""
    agregado = manifesto.get("agregado") or {}
    return str(agregado.get("sha256") or "")


def validar_lista_de_inclusao(manifesto: Mapping[str, Any]) -> None:
    """A lista de inclusão **não vence** o manifesto: nome proibido ou ausente ⇒ `BLOQUEADO`.

    É a trava que impede o erro mais caro desta feature: alguém acrescenta um nome à
    `TABELAS_DO_PACOTE` sem notar que o manifesto o marcou `publicavel: false`.
    """
    proibidos = nao_publicaveis(manifesto)
    conhecidos = artefatos_do_manifesto(manifesto)
    faltando: list[str] = []
    for nome in _arquivos_esperados_no_manifesto():
        if nome in proibidos:
            msg = (
                f"BLOQUEADO — ARTEFATO NÃO PUBLICÁVEL: '{nome}' está na lista de inclusão de "
                f"{FEATURE} e o {NOME_MANIFESTO} o marca `publicavel: false` — "
                f"{proibidos[nome]}"
            )
            raise SerieInconsistente(msg)
        if nome not in conhecidos:
            faltando.append(nome)
    if faltando:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {len(faltando)} artefato(s) da lista de inclusão "
            f"não estão no {NOME_MANIFESTO}: {', '.join(sorted(faltando))}. "
            "Rode `python -m apps.pipeline run --offline`."
        )
        raise SerieInconsistente(msg)


def _arquivos_esperados_no_manifesto() -> tuple[str, ...]:
    """Os nomes, no vocabulário do manifesto (POSIX relativo a `data/canonical/`)."""
    nomes = [f"{nome}.parquet" for nome in TABELAS_DO_PACOTE]
    nomes += [f"figuras/{nome}.{ext}" for nome in FIGURAS_DO_PACOTE for ext in EXTENSOES_DE_FIGURA]
    nomes += [
        f"tabelas/{nome}.{ext}" for nome in TABELAS_DE_UMA_PAGINA for ext in EXTENSOES_DE_TABELA
    ]
    nomes.append(CAMINHO_NOTEBOOK_HTML.as_posix())
    nomes.append(NOME_HEATMAP_DADOS)
    return tuple(nomes)


# ─────────────────────────────────────────────────────────────────────────────
# CSV e hash
# ─────────────────────────────────────────────────────────────────────────────


def sha256_do_arquivo(alvo: Path) -> str:
    """`sha256` do conteúdo do arquivo.

    `read_bytes()` e não `open("rb")`: o lint de encoding de CA-022 reprova **qualquer** `open()`
    sem `encoding=` em `apps/`, inclusive em modo binário, e a regra sintática vale mais que a
    exceção — o maior arquivo do pacote tem 2,1 MB, então ler inteiro não custa nada.
    """
    return hashlib.sha256(alvo.read_bytes()).hexdigest()


def gravar_csv_ptbr(dados: pd.DataFrame, destino: Path) -> Path:
    """CSV pt-BR determinístico: `;`, vírgula decimal, UTF-8 **com BOM**, `LF`, sem índice."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    dados.to_csv(
        destino,
        sep=CSV_SEPARADOR,
        decimal=CSV_DECIMAL,
        encoding=CSV_ENCODING,
        index=False,
        lineterminator=CSV_FIM_DE_LINHA,
    )
    return destino


CSV_DE_F024_SEPARADOR = ","
CSV_DE_F024_ENCODING = "utf-8"
"""As duas tabelas de 1 página vêm de F-024 com **outra** convenção de CSV: vírgula como
separador, ponto decimal e UTF-8 **sem** BOM. O pacote as copia byte a byte (arquivo de outra
feature, congelado para F-031) e **declara a diferença** no `README-COMITE.md` e na aba `Leia-me`.
Reescrevê-las em pt-BR criaria uma segunda verdade para a mesma tabela."""


def ler_csv_de_f024(alvo: Path) -> pd.DataFrame:
    """A volta do CSV das tabelas de 1 página — convenção de F-024, não a do `dados/`."""
    return pd.read_csv(alvo, sep=CSV_DE_F024_SEPARADOR, encoding=CSV_DE_F024_ENCODING)


def ler_csv_ptbr(alvo: Path) -> pd.DataFrame:
    """A volta de `gravar_csv_ptbr` — usada pelo smoke para **abrir** cada CSV do pacote."""
    return pd.read_csv(
        alvo,
        sep=CSV_SEPARADOR,
        decimal=CSV_DECIMAL,
        encoding=CSV_ENCODING,
        low_memory=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Textos lidos do disco: as 10 limitações e as 12 decisões
# ─────────────────────────────────────────────────────────────────────────────

_ID_DA_CELULA_DAS_LIMITACOES = "md-s8"
_RE_ITEM_NUMERADO = re.compile(r"^\s*(\d{1,2})\.\s+(.*)$")


def limitacoes_do_notebook(*, raiz: Path | None = None) -> tuple[str, ...]:
    """As **10** limitações, lidas da célula `md-s8` do caderno de F-027 — nunca digitadas aqui.

    Por que do caderno e não de `LIMITACOES-COMITE.md`: a página tem 8 blocos de prosa, não uma
    lista de 10; a condensação em uma linha cada vive no caderno, que tem teste travando a
    contagem em 10 (F-027 §9). Uma só fonte, um só número.
    """
    alvo = (raiz or raiz_repo()) / CAMINHO_NOTEBOOK_LIMPO
    caderno = json.loads(alvo.read_text(encoding="utf-8"))
    for celula in caderno.get("cells", ()):
        if celula.get("id") == _ID_DA_CELULA_DAS_LIMITACOES:
            return _itens_numerados("".join(celula.get("source", ())))
    msg = (
        f"BLOQUEADO — FONTE INDISPONÍVEL: o caderno {alvo.name} não tem a célula "
        f"'{_ID_DA_CELULA_DAS_LIMITACOES}' com as {N_LIMITACOES} limitações."
    )
    raise SerieInconsistente(msg)


def _itens_numerados(markdown: str) -> tuple[str, ...]:
    """Itens de lista numerada em Markdown, com as continuações indentadas colapsadas."""
    itens: list[list[str]] = []
    for linha in markdown.splitlines():
        achado = _RE_ITEM_NUMERADO.match(linha)
        if achado is not None:
            itens.append([achado.group(2).strip()])
        elif itens and linha.strip() and linha.startswith((" ", "\t")):
            itens[-1].append(linha.strip())
    return tuple(" ".join(partes) for partes in itens)


_RE_LINHA_DE_TABELA = re.compile(r"^\|(?P<corpo>.*)\|\s*$")
_CABECALHO_DAS_DECISOES = "## 7."


def decisoes_a_ratificar(*, raiz: Path | None = None) -> tuple[dict[str, str], ...]:
    """As **12** decisões pendentes, lidas da tabela da §7 de `LIMITACOES-COMITE.md`.

    Cada item traz `id`, `decisao`, `padrao_provisorio` e `se_discordar` — as 4 colunas da página.
    """
    alvo = (raiz or raiz_repo()) / CAMINHO_LIMITACOES
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    dentro = False
    celulas: list[list[str]] = []
    for linha in linhas:
        if linha.startswith("## "):
            dentro = linha.startswith(_CABECALHO_DAS_DECISOES)
            continue
        if not dentro:
            continue
        achado = _RE_LINHA_DE_TABELA.match(linha)
        if achado is None:
            continue
        partes = [parte.strip() for parte in achado.group("corpo").split("|")]
        if len(partes) < 4 or set("".join(partes)) <= {"-", ":", " "}:
            continue
        celulas.append(partes[:4])
    registros = [
        {
            "id": _sem_markdown(linha[0]),
            "decisao": _sem_markdown(linha[1]),
            "padrao_provisorio": _sem_markdown(linha[2]),
            "se_discordar": _sem_markdown(linha[3]),
        }
        for linha in celulas[1:]  # a primeira linha de células é o cabeçalho da tabela
    ]
    if len(registros) != N_DECISOES:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: a §7 de {NOME_LIMITACOES} tem {len(registros)} "
            f"decisões, e o pacote espera {N_DECISOES}."
        )
        raise SerieInconsistente(msg)
    return tuple(registros)


def _sem_markdown(texto: str) -> str:
    """Tira ênfase e crase do Markdown para a célula de planilha ficar legível."""
    limpo = texto.replace("**", "").replace("`", "").replace("<br>", " ")
    return re.sub(r"\s+", " ", limpo).strip()


_RE_SECAO_SUBSTITUICOES = re.compile(r"^##\s+1\.\s+Substitui", re.IGNORECASE)


def texto_das_substituicoes(*, raiz: Path | None = None) -> str:
    """A §1 do `DECISIONS_LOG.md` — as 12 substituições de fonte com os 4 campos (CA-117).

    O texto acompanha o pacote como arquivo próprio em vez de link: CA-117 pede que a
    comunicação **acompanhe** o pacote, e o Alexandre não abre o repositório.
    """
    alvo = (raiz or raiz_repo()) / CAMINHO_DECISIONS_LOG
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    inicio: int | None = None
    fim = len(linhas)
    for indice, linha in enumerate(linhas):
        if inicio is None and _RE_SECAO_SUBSTITUICOES.match(linha):
            inicio = indice
            continue
        if inicio is not None and linha.startswith("## "):
            fim = indice
            break
    if inicio is None:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {CAMINHO_DECISIONS_LOG.name} não tem a seção "
            "'1. Substituições de fonte' que CA-117 exige junto ao pacote."
        )
        raise SerieInconsistente(msg)
    corpo = "\n".join(linhas[inicio:fim]).rstrip()
    return corpo + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# O XLSX
# ─────────────────────────────────────────────────────────────────────────────


def _estilizar_cabecalho(planilha: Any, n_colunas: int, *, linha: int = 1) -> None:
    preenchimento = PatternFill("solid", fgColor="DDDDDD")
    for coluna in range(1, n_colunas + 1):
        celula = planilha.cell(row=linha, column=coluna)
        celula.font = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE, bold=True)
        celula.fill = preenchimento
        celula.alignment = Alignment(vertical="top", wrap_text=True)


def _formato_da_coluna(nome: str) -> str | None:
    if nome in COLUNAS_PERCENTUAIS:
        return FORMATO_PERCENTUAL
    if nome in COLUNAS_INTEIRAS:
        return FORMATO_INTEIRO
    return None


def _valor_para_celula(valor: Any) -> Any:
    """Converte para algo que o `openpyxl` escreve **sem** fórmula e sem estourar a célula."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, bool | int | float):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.date().isoformat()
    texto = str(valor)
    if pd.isna(valor) if not isinstance(valor, str) else False:  # pragma: no cover - defensivo
        return None
    if texto.startswith(("=", "+", "-", "@")) and not _parece_numero(texto):
        # Nada no pacote recalcula: um texto que começa com `=` entraria como fórmula.
        texto = "'" + texto
    return texto[:LIMITE_DE_CARACTERES_NA_CELULA]


def _parece_numero(texto: str) -> bool:
    try:
        float(texto.replace(CSV_DECIMAL, "."))
    except ValueError:
        return False
    return True


def _escrever_tabela(
    planilha: Any,
    dados: pd.DataFrame,
    *,
    linha_inicial: int = 1,
    com_formato: bool = True,
) -> int:
    """Escreve cabeçalho + corpo a partir de `linha_inicial`. Devolve a próxima linha livre."""
    colunas = list(dados.columns)
    for indice, nome in enumerate(colunas, start=1):
        planilha.cell(row=linha_inicial, column=indice, value=str(nome))
    _estilizar_cabecalho(planilha, len(colunas), linha=linha_inicial)
    formatos = [_formato_da_coluna(str(nome)) if com_formato else None for nome in colunas]
    fonte = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE)
    for deslocamento, (_, registro) in enumerate(dados.iterrows(), start=1):
        for indice, (nome, formato) in enumerate(zip(colunas, formatos, strict=True), start=1):
            celula = planilha.cell(
                row=linha_inicial + deslocamento,
                column=indice,
                value=_valor_para_celula(registro[nome]),
            )
            celula.font = fonte
            if formato is not None:
                celula.number_format = formato
            elif isinstance(celula.value, float):
                celula.number_format = FORMATO_NUMERO
    _ajustar_larguras(planilha, dados, linha_do_cabecalho=linha_inicial)
    return linha_inicial + len(dados) + 1


def _ajustar_larguras(planilha: Any, dados: pd.DataFrame, *, linha_do_cabecalho: int) -> None:
    """Largura por coluna pela amostra do cabeçalho e das 50 primeiras linhas (determinístico)."""
    del linha_do_cabecalho
    amostra = dados.head(50)
    for indice, nome in enumerate(dados.columns, start=1):
        larguras = [len(str(nome))]
        larguras += [len(str(valor)) for valor in amostra[nome].tolist() if valor is not None]
        largura = min(max(larguras) + 2, LARGURA_MAXIMA_DA_COLUNA)
        planilha.column_dimensions[get_column_letter(indice)].width = largura


def _escrever_bloco_de_texto(planilha: Any, linhas: Sequence[Sequence[str]]) -> int:
    """Escreve pares rótulo/valor em A/B. Devolve a próxima linha livre."""
    negrito = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE, bold=True)
    normal = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE)
    for indice, par in enumerate(linhas, start=1):
        rotulo = planilha.cell(row=indice, column=1, value=_valor_para_celula(par[0]))
        rotulo.font = negrito
        rotulo.alignment = Alignment(vertical="top")
        if len(par) > 1:
            valor = planilha.cell(row=indice, column=2, value=_valor_para_celula(par[1]))
            valor.font = normal
            valor.alignment = Alignment(vertical="top", wrap_text=True)
    planilha.column_dimensions["A"].width = 34
    planilha.column_dimensions["B"].width = LARGURA_MAXIMA_DA_COLUNA * 2
    return len(linhas) + 2


def matriz_do_heatmap(
    heatmap: pd.DataFrame, *, vista: str = VISTA_DO_HEATMAP
) -> tuple[pd.DataFrame, tuple[str, ...], tuple[str, ...]]:
    """A matriz `ativo × regime` de `excesso_cdi` com o `n` ao lado, na ordem da figura.

    Não recalcula nada: lê `figuras/heatmap_dados.parquet` (F-023), que já traz `linha`/`coluna`
    com a ordenação publicada, e só repivota.
    """
    recorte = heatmap.loc[heatmap["vista"] == vista]
    if recorte.empty:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {NOME_HEATMAP_DADOS} não tem a vista '{vista}'. "
            "Rode a etapa `figuras` de `python -m apps.pipeline run --offline`."
        )
        raise SerieInconsistente(msg)
    ativos = tuple(
        recorte.sort_values("linha", kind="stable")["asset_id"].drop_duplicates().tolist()
    )
    regimes = tuple(
        recorte.sort_values("coluna", kind="stable")["regime"].drop_duplicates().tolist()
    )
    indexado = recorte.set_index(["asset_id", "regime"])
    registros: list[dict[str, Any]] = []
    for ativo in ativos:
        registro: dict[str, Any] = {"asset_id": ativo}
        for regime in regimes:
            chave = (ativo, regime)
            if chave in indexado.index:
                linha = indexado.loc[chave]
                registro[regime] = float(linha["excesso_cdi"])
                registro[f"n ({regime})"] = int(linha["n_obs"])
            else:  # pragma: no cover - a grade de F-023 é completa
                registro[regime] = None
                registro[f"n ({regime})"] = None
        registros.append(registro)
    return pd.DataFrame.from_records(registros), ativos, regimes


def _aba_heatmap(planilha: Any, heatmap: pd.DataFrame, gate: Gate) -> None:
    matriz, ativos, regimes = matriz_do_heatmap(heatmap)
    aviso = (
        f"Excesso sobre o CDI medio trimestral por regime x ativo. {gate.selo or gate.veredito}. "
        "A coluna `n` ao lado de cada regime e o numero de observacoes da celula (Anti-SPEC "
        "§10.2.8): n < 8 e alerta, n < 5 sai sem conclusao. Valores colados, sem formula."
    )
    cabecalho = planilha.cell(row=1, column=1, value=aviso)
    cabecalho.font = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE, bold=True)
    cabecalho.alignment = Alignment(vertical="top", wrap_text=True)
    _escrever_tabela(planilha, matriz, linha_inicial=3)
    # Formatação condicional divergente, centrada em 0, só nas colunas de valor.
    limite = _limite_simetrico(matriz, regimes)
    regra = ColorScaleRule(
        start_type="num",
        start_value=-limite,
        start_color="C0504D",
        mid_type="num",
        mid_value=0.0,
        mid_color="FFFFFF",
        end_type="num",
        end_value=limite,
        end_color="4F81BD",
    )
    primeira = 4
    ultima = primeira + len(ativos) - 1
    for indice, nome in enumerate(matriz.columns, start=1):
        if nome in regimes:
            letra = get_column_letter(indice)
            planilha.conditional_formatting.add(f"{letra}{primeira}:{letra}{ultima}", regra)
    planilha.freeze_panes = "B4"


def _limite_simetrico(matriz: pd.DataFrame, regimes: Sequence[str]) -> float:
    """O extremo da escala divergente: `max(|valor|)` arredondado para cima, em 0,5 pp."""
    valores = matriz[list(regimes)].abs().to_numpy(dtype=float)
    maximo = float(pd.Series(valores.ravel()).dropna().max() or 0.0)
    passo = 0.005
    return max(passo, float(int(maximo / passo) + 1) * passo)


def _bloco_a_do_regime_atual(
    *, regimes_revised: pd.DataFrame, regimes_asof: pd.DataFrame, vizinhos: pd.DataFrame
) -> pd.DataFrame:
    """O bloco A de F-024 — as **três** respostas a "em que regime estamos", nenhuma escolhida."""
    respostas = respostas_do_regime_atual(
        regimes_revised=regimes_revised,
        regimes_asof=regimes_asof,
        vizinhos=vizinhos,
        quarter=QUARTER_DO_COMITE,
    )
    return pd.DataFrame.from_records(
        [
            {
                "lente": resposta.titulo,
                "trimestre_perguntado": resposta.quarter_perguntado,
                "status": resposta.status,
                "resposta": resposta.resposta,
                "trimestre_da_celula": resposta.quarter_da_celula,
                "regime_da_celula": resposta.regime_da_celula,
                "e_fallback": resposta.e_fallback,
                "como_chega": _sem_markdown(resposta.como_chega),
                "ressalva": _sem_markdown(resposta.ressalva),
            }
            for resposta in respostas
        ]
    )


def construir_xlsx(
    destino: Path,
    *,
    gate: Gate,
    manifesto: Mapping[str, Any],
    tabelas: Mapping[str, pd.DataFrame],
    heatmap: pd.DataFrame,
    vizinhos: pd.DataFrame,
    limitacoes: Sequence[str],
    decisoes: Sequence[Mapping[str, str]],
) -> Path:
    """`PACOTE-COMITE.xlsx` — 8 abas, pt-BR, **valores colados** (zero fórmula)."""
    livro = Workbook()
    livro.properties.created = DATA_FIXA_DO_PACOTE
    livro.properties.modified = DATA_FIXA_DO_PACOTE
    livro.properties.creator = f"{FEATURE} - apps.analysis.entrega.montar_pacote"
    livro.properties.lastModifiedBy = livro.properties.creator
    livro.properties.title = f"Pacote de entrega ao Comite de Alocacao - {VERSAO_DO_PACOTE}"

    folha = livro.active
    folha.title = ABA_LEIA_ME
    _escrever_bloco_de_texto(folha, _linhas_do_leia_me(gate=gate, manifesto=manifesto))

    _aba_do_regime_atual(livro.create_sheet(ABA_REGIME_ATUAL), tabelas, vizinhos, gate)
    _aba_heatmap(livro.create_sheet(ABA_HEATMAP), heatmap, gate)
    _escrever_tabela(livro.create_sheet(ABA_VIZINHOS), vizinhos)
    _escrever_tabela(livro.create_sheet(ABA_MACRO), tabelas["macro_quarterly"])
    _escrever_tabela(livro.create_sheet(ABA_RETORNOS), tabelas["asset_returns_quarterly"])
    _escrever_tabela(
        livro.create_sheet(ABA_LIMITACOES),
        pd.DataFrame.from_records(
            [
                {"#": i, "limitacao": _sem_markdown(texto)}
                for i, texto in enumerate(limitacoes, start=1)
            ]
        ),
    )
    _escrever_tabela(livro.create_sheet(ABA_DECISOES), pd.DataFrame.from_records(list(decisoes)))

    destino.parent.mkdir(parents=True, exist_ok=True)
    livro.save(destino)
    _rezipar_deterministico(destino)
    return destino


def _aba_do_regime_atual(
    planilha: Any, tabelas: Mapping[str, pd.DataFrame], vizinhos: pd.DataFrame, gate: Gate
) -> None:
    bloco_a = _bloco_a_do_regime_atual(
        regimes_revised=tabelas["regimes_v1"],
        regimes_asof=tabelas["regimes_v1_asof"],
        vizinhos=vizinhos,
    )
    titulo = planilha.cell(
        row=1,
        column=1,
        value=(
            f"A. Em que regime estamos ({QUARTER_DO_COMITE})? Tres respostas, nenhuma escolhida "
            f"por este pacote. {gate.selo or gate.veredito}."
        ),
    )
    titulo.font = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE, bold=True)
    titulo.alignment = Alignment(vertical="top", wrap_text=True)
    proxima = _escrever_tabela(planilha, bloco_a, linha_inicial=3)
    rotulo = planilha.cell(
        row=proxima + 1,
        column=1,
        value=(
            "B. Ranking de ativos por lente - excesso sobre o CDI medio trimestral, com `n` em "
            "toda linha (fonte: tabelas/ranking_regime_atual)."
        ),
    )
    rotulo.font = Font(name=FONTE_DO_PACOTE, size=TAMANHO_DA_FONTE, bold=True)
    rotulo.alignment = Alignment(vertical="top", wrap_text=True)
    _escrever_tabela(planilha, tabelas["__ranking__"], linha_inicial=proxima + 3)


def _linhas_do_leia_me(*, gate: Gate, manifesto: Mapping[str, Any]) -> list[list[str]]:
    """O conteúdo da aba `Leia-me`: o gate primeiro, os hashes depois."""
    data = manifesto.get("data_do_dado") or {}
    agregado = manifesto.get("agregado") or {}
    indice = artefatos_do_manifesto(manifesto)
    commit = commit_em_disco() or {}
    linhas: list[list[str]] = [
        ["PACOTE", f"Levantamento de dados macro e de ativos - {VERSAO_DO_PACOTE} ({FEATURE})"],
        ["GATE", gate.selo or gate.veredito],
        ["STATUS DO ADR-001", gate.status_adr_001],
        ["ESPECIFICACAO CONGELADA", "sim" if gate.congelada else "nao"],
        [
            "O QUE O GATE SIGNIFICA",
            "Enquanto o ADR-001 estiver em Proposta, todo numero deste arquivo e material de "
            "discussao, nao insumo de decisao de alocacao. Nada aqui e previsao, de regime ou de "
            "retorno (Anti-SPEC §10.2.10).",
        ],
        ["", ""],
        ["DATASET_SHA256", dataset_sha256(manifesto)],
        ["CONVENCAO DO AGREGADO", str((manifesto.get("convencao") or {}).get("agregado", ""))],
        ["ARTEFATOS NO AGREGADO", str(agregado.get("n_artefatos", ""))],
        ["PRIMEIRO TRIMESTRE", str(data.get("primeiro_trimestre_macro", ""))],
        ["ULTIMO TRIMESTRE", str(data.get("ultimo_trimestre_macro", ""))],
        ["DATA MAXIMA DO BRUTO", str(data.get("date_max_raw_series", ""))],
        ["COMMIT", str(commit.get("commit") or "indisponivel")],
        ["TAG PREVISTA (ato humano)", TAG_DA_ENTREGA],
        ["", ""],
        [
            "FORMATO DOS CSV EM dados/",
            f"separador '{CSV_SEPARADOR}', decimal '{CSV_DECIMAL}', UTF-8 com BOM, fim de linha LF",
        ],
        [
            "FORMATO DOS CSV EM tabelas/",
            f"ATENCAO, convencao DIFERENTE: separador '{CSV_DE_F024_SEPARADOR}', ponto decimal, "
            "UTF-8 SEM BOM. Sao arquivos gerados por outra etapa do pipeline e copiados byte a "
            "byte - reescreve-los criaria uma segunda versao da mesma tabela.",
        ],
        [
            "UNIDADES",
            "macro em por cento / pontos percentuais; retornos em fracao no dado e exibidos como "
            "percentual nas abas. Mapa de unidades em relatorio_macro.json -> unidades.",
        ],
        [
            "FORMULAS",
            "nenhuma. Todo valor esta colado: o arquivo descreve um dataset congelado e nao "
            "recalcula nada ao abrir.",
        ],
        [
            "NULOS LEGITIMOS",
            " | ".join(NULOS_LEGITIMOS),
        ],
        ["", ""],
        ["HASHES DOS ARTEFATOS (sha256)", "o mesmo valor que MANIFEST.json publica"],
    ]
    for nome in _arquivos_esperados_no_manifesto():
        entrada = indice.get(nome) or {}
        linhas.append([nome, str(entrada.get("sha256") or "")])
    proibidos = nao_publicaveis(manifesto)
    linhas.append(["", ""])
    linhas.append(["FORA DESTE PACOTE (publicavel: false)", f"{len(proibidos)} artefato(s)"])
    for nome, motivo in sorted(proibidos.items()):
        linhas.append([nome, motivo])
    return linhas


CARIMBO_FIXO_NO_XLSX = "2026-10-14T00:00:00Z"
"""O que entra em `dcterms:modified`. Ver `_rezipar_deterministico`."""

NOME_DAS_PROPRIEDADES_DO_XLSX = "docProps/core.xml"

_RE_MODIFICADO_EM = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")


def _rezipar_deterministico(alvo: Path) -> None:
    """Reescreve o zip interno do `.xlsx` com timestamp fixo, preservando ordem e conteúdo.

    **Duas** fontes de relógio, as duas medidas nesta máquina:

    1. o `zipfile` grava a hora corrente em **cada entrada** do zip;
    2. o `openpyxl` **sobrescreve** `wb.properties.modified` com o UTC do momento do `save()`,
       ignorando o valor que o chamador fixou — então `docProps/core.xml` muda a cada segundo
       (medido: duas montagens no mesmo minuto diferiram só em `…T13:32:05Z` × `…T13:32:06Z`).

    Sem as duas correções o `sha256` do pacote muda entre montagens — e é o `sha256` que amarra o
    pacote ao dataset congelado (CA-121).
    """
    with zipfile.ZipFile(alvo) as origem:
        itens = [(info, origem.read(info.filename)) for info in origem.infolist()]
    temporario = alvo.with_name(alvo.name + ".tmp")
    carimbo = CARIMBO_FIXO_NO_XLSX.encode("ascii")
    with zipfile.ZipFile(
        temporario, "w", zipfile.ZIP_DEFLATED, compresslevel=NIVEL_DE_COMPRESSAO
    ) as saida:
        for info, conteudo in itens:
            corpo = conteudo
            if info.filename == NOME_DAS_PROPRIEDADES_DO_XLSX:
                corpo = _RE_MODIFICADO_EM.sub(rb"\g<1>" + carimbo + rb"\g<2>", corpo)
            nova = zipfile.ZipInfo(info.filename, date_time=DATA_FIXA_NO_ZIP)
            nova.compress_type = zipfile.ZIP_DEFLATED
            nova.external_attr = info.external_attr
            nova.create_system = 0
            saida.writestr(nova, corpo)
    temporario.replace(alvo)


# ─────────────────────────────────────────────────────────────────────────────
# README do pacote
# ─────────────────────────────────────────────────────────────────────────────


def markdown_do_readme(*, gate: Gate, manifesto: Mapping[str, Any], frozen_presente: bool) -> str:
    """`README-COMITE.md` — uma página para o gestor, determinística, com o gate no topo."""
    data = manifesto.get("data_do_dado") or {}
    commit = commit_em_disco() or {}
    proibidos = nao_publicaveis(manifesto)
    selo = (
        f"> ⛔ **{gate.selo}**\n>\n"
        f"> O `ADR-001` (lente de regime oficial) está em **{gate.status_adr_001}** no "
        "repositório, logo `especificacao_congelada = false` (CA-090). Veredito do fluxo de "
        f"publicação: **{gate.veredito}**. Este pacote é **material de discussão** — ele existe "
        "para ser lido e criticado na reunião, e o envio formal só acontece depois dos 8 passos "
        "de `AGENTS.md §14`.\n"
        if not gate.congelada
        else f"> ✅ **{gate.veredito}** — `ADR-001` está em **{gate.status_adr_001}** em disco.\n"
    )
    linhas = [
        f"# Pacote de dados para o Comitê de Alocação — {VERSAO_DO_PACOTE}",
        "",
        selo,
        "**Para:** Alexandre Kaercher e o Comitê de Alocação da LDC Capital  ",
        "**Reunião:** 2026-10-14  ",
        f"**Janela:** {data.get('primeiro_trimestre_macro', '')} → "
        f"{data.get('ultimo_trimestre_macro', '')} "
        f"(dado bruto até {data.get('date_max_raw_series', '')})",
        "",
        "## 1. O que é isto",
        "",
        "O levantamento de dados que o e-mail de outubro pediu: 20 anos de séries macro "
        "brasileiras e de índices de ativos, em frequência trimestral, com uma leitura de "
        "**regimes macro** por cima — em que quadrante cada trimestre do histórico caiu e, "
        "em momentos parecidos, como cada classe de ativo rendeu, **com quantas observações**.",
        "",
        "É uma base de discussão, descritiva do passado. Nada aqui é previsão, backtest ou "
        "recomendação de carteira — isso está fora deste pacote por decisão de escopo "
        "(Anti-SPEC §10.3.16 e §10.2.10).",
        "",
        "## 2. Como ler, em 4 passos",
        "",
        f"1. **`notebook/{NOME_NOTEBOOK}.html`** — abra no navegador. É o caminho guiado: o gate, "
        'o pedido do e-mail × o entregue, os regimes, os "momentos semelhantes", o mapa de '
        "calor e as limitações, nessa ordem.",
        f"2. **`{NOME_LIMITACOES}`** — leia inteiro antes da reunião. É a página que diz o que o "
        "número sustenta e o que não sustenta.",
        f"3. **`{NOME_XLSX}`** — a planilha, se preferir Excel. 8 abas, a primeira é o `Leia-me` "
        "com o gate e os hashes. **Nenhuma fórmula:** todo valor está colado, porque o arquivo "
        "descreve um dataset congelado.",
        "4. **`dados/`** — as tabelas inteiras, para cruzar com modelo próprio.",
        "",
        "## 3. O que tem dentro",
        "",
        "| Pasta | Conteúdo |",
        "|---|---|",
        f"| raiz | `{NOME_README}`, `{NOME_LIMITACOES}`, `{NOME_SUBSTITUICOES}`, `{NOME_XLSX}`, "
        f"`{NOME_MANIFESTO}`, "
        + (f"`{NOME_FROZEN}`, " if frozen_presente else "")
        + f"`{NOME_HASHES}` |",
        f"| `dados/` | {len(TABELAS_DO_PACOTE)} tabelas, cada uma em **Parquet** e **CSV** |",
        f"| `figuras/` | {len(FIGURAS_DO_PACOTE)} figuras (2 linhas do tempo + 3 mapas de calor), "
        "cada uma em **PNG** e **SVG** |",
        f"| `tabelas/` | {len(TABELAS_DE_UMA_PAGINA)} tabelas de 1 página, em **Markdown** e "
        "**CSV** |",
        "| `notebook/` | o caderno `.ipynb` (reproduzível) e o **HTML executado** |",
        "",
        "## 4. Convenções que mudam o número",
        "",
        f"- **CSV de `dados/`:** separador `{CSV_SEPARADOR}`, vírgula decimal, **UTF-8 com BOM**, "
        "fim de linha `LF`. É o formato que o Excel em português abre com as colunas já "
        "separadas, sem passar pelo assistente de importação.",
        f"- **CSV de `tabelas/`:** convenção **diferente** — separador `{CSV_DE_F024_SEPARADOR}`, "
        "ponto decimal, UTF-8 **sem** BOM. São as duas tabelas de 1 página, geradas por outra "
        "etapa do pipeline e copiadas byte a byte para o `sha256` continuar conferindo; "
        "reescrevê-las em pt-BR criaria uma segunda versão da mesma tabela.",
        "- **Unidades:** macro em **por cento / pontos percentuais**; retornos em **fração** no "
        "dado (a planilha os exibe como percentual). Cruzar as duas sem olhar a unidade erra por "
        "100×; o mapa de unidades está em `relatorio_macro.json → unidades`.",
        "- **Trimestre = último dia útil**, não média do período.",
        "- **Excesso sobre o CDI é calculado por razão, nunca por subtração.**",
        "- **`n` aparece em toda célula.** `n < 8` entra com alerta e `n < 5` sai **sem "
        "conclusão** — a ordem de um ranking com `n` pequeno não é estatisticamente "
        "distinguível.",
        "",
        "### Nulos legítimos, contados",
        "",
        *[f"- {texto}" for texto in NULOS_LEGITIMOS],
        "",
        "Fora desses dois casos, **nenhuma coluna crítica tem nulo** — e isso é verificado "
        "automaticamente pelo smoke test do pacote.",
        "",
        "## 5. Versão e impressão digital",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Versão | `{VERSAO_DO_PACOTE}` |",
        f"| Feature | `{FEATURE}` |",
        f"| `DATASET_SHA256` | `{dataset_sha256(manifesto)}` |",
        f"| Commit | `{commit.get('commit') or 'indisponível'}` |",
        f"| Tag git prevista (ato humano) | `{TAG_DA_ENTREGA}` |",
        f"| Status do `ADR-001` em disco | `{gate.status_adr_001}` |",
        "",
        f"`{NOME_HASHES}` traz o `sha256` de **cada** arquivo deste pacote e repete o "
        f"`DATASET_SHA256`. `{NOME_MANIFESTO}` é a cópia do manifesto do dataset. "
        "**Hash diferente = outro dataset:** nunca comparar números de rodadas diferentes sem "
        "conferir.",
        "",
        "## 6. O que não está neste pacote",
        "",
        "- Recomendação de alocação, carteira sugerida, backtest, otimização ou qualquer "
        "projeção. O ranking que existe é descritivo.",
        "- FII por segmento, risco-país, termos de troca, ouro, S&P com hedge cambial e a lente "
        "V2 completa — cada ausência está explicada na página de limitações.",
    ]
    for nome, motivo in sorted(proibidos.items()):
        linhas.append(f"- `{nome}` — {motivo}")
    linhas += [
        "",
        f"## 7. Substituições de fonte ({NOME_SUBSTITUICOES})",
        "",
        "Onde a fonte pedida no e-mail não existia, estava descontinuada ou era paga, o pacote "
        "usou outra — e cada troca está registrada com **fonte pedida, fonte usada, motivo e "
        f"impacto na comparabilidade** em `{NOME_SUBSTITUICOES}`. Todas são **provisórias**: "
        "nenhuma recebeu aval ainda.",
        "",
        "## 8. Como reproduzir",
        "",
        "Nada neste pacote foi digitado à mão — todo arquivo sai de script versionado (CA-114):",
        "",
        "```bash",
        "uv sync --extra dev",
        "python -m apps.pipeline run --offline      # reconstrói data/canonical/",
        "python -m apps.pipeline verify             # confere o sha256 de cada artefato",
        "python -m apps.analysis.entrega.montar_pacote --smoke   # remonta este pacote e confere",
        "```",
        "",
        "Duas montagens seguidas produzem o **mesmo** `sha256` do `.zip`: timestamps e ordem das "
        "entradas são fixos, e nada no pacote lê o relógio.",
        "",
    ]
    return "\n".join(linhas)


# ─────────────────────────────────────────────────────────────────────────────
# Montagem
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoMontagem:
    """O que a montagem produziu — insumo do relatório e do smoke."""

    pacote: Path
    zip: Path
    sha256_do_zip: str
    gate: Gate
    manifesto: dict[str, Any]
    arquivos: tuple[tuple[str, int, str], ...]
    """`(caminho relativo POSIX, bytes, sha256)` de cada arquivo do pacote, em ordem."""
    excluidos: dict[str, str]
    frozen_presente: bool


def _carregar_tabelas(*, raiz: Path | None) -> dict[str, pd.DataFrame]:
    tabelas = {
        nome: pd.read_parquet(caminho_canonical(f"{nome}.parquet", raiz=raiz))
        for nome in TABELAS_DO_PACOTE
    }
    tabelas["__ranking__"] = pd.read_parquet(
        caminho_canonical("tabelas/ranking_regime_atual.parquet", raiz=raiz)
    )
    return tabelas


def montar(
    *,
    raiz: Path | None = None,
    saida: Path | None = None,
) -> ResultadoMontagem:
    """Monta o pacote em `saida` (padrão: `data/canonical/entrega/<NOME_DO_PACOTE>/`) + `.zip`.

    Idempotente: o diretório é recriado do zero a cada chamada e o `.zip` sai com o mesmo
    `sha256`. **Não publica nada** — ver o docstring do módulo.
    """
    manifesto = ler_manifesto(raiz=raiz)
    validar_lista_de_inclusao(manifesto)
    gate = ler_gate(raiz=raiz)
    if not gate.congelada:
        _log.warning(
            "%s: ADR-001 em '%s' - pacote montado com selo de nao publicavel (CA-090)",
            para_ascii(VEREDITO_BLOQUEADO),
            gate.status_adr_001,
        )

    pacote = saida or caminho_do_pacote(raiz=raiz)
    if pacote.exists():
        shutil.rmtree(pacote)
    (pacote / "dados").mkdir(parents=True)
    (pacote / "figuras").mkdir()
    (pacote / "tabelas").mkdir()
    (pacote / "notebook").mkdir()

    base_do_repo = raiz or raiz_repo()
    tabelas = _carregar_tabelas(raiz=raiz)

    # (c) dados: Parquet (cópia byte a byte, para o sha256 bater com o MANIFEST) + CSV pt-BR
    for nome in TABELAS_DO_PACOTE:
        origem = caminho_canonical(f"{nome}.parquet", raiz=raiz)
        shutil.copyfile(origem, pacote / "dados" / origem.name)
        gravar_csv_ptbr(tabelas[nome], pacote / "dados" / f"{nome}.csv")

    # (d) figuras e (e) tabelas de 1 página
    for nome in FIGURAS_DO_PACOTE:
        for extensao in EXTENSOES_DE_FIGURA:
            origem = caminho_canonical(f"figuras/{nome}.{extensao}", raiz=raiz)
            shutil.copyfile(origem, pacote / "figuras" / origem.name)
    for nome in TABELAS_DE_UMA_PAGINA:
        for extensao in EXTENSOES_DE_TABELA:
            origem = caminho_canonical(f"tabelas/{nome}.{extensao}", raiz=raiz)
            shutil.copyfile(origem, pacote / "tabelas" / origem.name)

    # (f) notebook: o `.ipynb` limpo (versionado) + o HTML executado
    shutil.copyfile(
        base_do_repo / CAMINHO_NOTEBOOK_LIMPO,
        pacote / "notebook" / CAMINHO_NOTEBOOK_LIMPO.name,
    )
    shutil.copyfile(
        caminho_canonical(CAMINHO_NOTEBOOK_HTML.as_posix(), raiz=raiz),
        pacote / "notebook" / CAMINHO_NOTEBOOK_HTML.name,
    )

    # (b) página de limitações e (CA-117) o texto das substituições de fonte
    shutil.copyfile(base_do_repo / CAMINHO_LIMITACOES, pacote / NOME_LIMITACOES)
    (pacote / NOME_SUBSTITUICOES).write_text(
        _cabecalho_das_substituicoes(gate) + texto_das_substituicoes(raiz=raiz),
        encoding="utf-8",
        newline="\n",
    )

    # (g) o XLSX
    heatmap = pd.read_parquet(caminho_canonical(NOME_HEATMAP_DADOS, raiz=raiz))
    vizinhos = vizinhos_do_quarter(tabelas["regime_neighbors_v3"], quarter=QUARTER_DO_COMITE)
    construir_xlsx(
        pacote / NOME_XLSX,
        gate=gate,
        manifesto=manifesto,
        tabelas=tabelas,
        heatmap=heatmap,
        vizinhos=vizinhos,
        limitacoes=limitacoes_do_notebook(raiz=raiz),
        decisoes=decisoes_a_ratificar(raiz=raiz),
    )

    # (h) MANIFEST.json + FROZEN.txt + o README
    shutil.copyfile(caminho_canonical(NOME_MANIFESTO, raiz=raiz), pacote / NOME_MANIFESTO)
    frozen = caminho_canonical(NOME_FROZEN, raiz=raiz)
    frozen_presente = frozen.is_file()
    if frozen_presente:
        shutil.copyfile(frozen, pacote / NOME_FROZEN)
    readme = markdown_do_readme(gate=gate, manifesto=manifesto, frozen_presente=frozen_presente)
    _linguagem.conferir_linguagem_descritiva(readme, origem=NOME_README)
    (pacote / NOME_README).write_text(readme, encoding="utf-8", newline="\n")

    # HASHES.txt — por último, porque cobre tudo o que já está no diretório
    arquivos = gravar_hashes(pacote, manifesto=manifesto, gate=gate)

    destino_zip = pacote.with_name(f"{pacote.name}.zip")
    sha_do_zip = zipar_deterministico(pacote, destino_zip)
    return ResultadoMontagem(
        pacote=pacote,
        zip=destino_zip,
        sha256_do_zip=sha_do_zip,
        gate=gate,
        manifesto=manifesto,
        arquivos=arquivos,
        excluidos=nao_publicaveis(manifesto),
        frozen_presente=frozen_presente,
    )


def _cabecalho_das_substituicoes(gate: Gate) -> str:
    return "\n".join(
        [
            "# Substituições de fonte que acompanham o pacote (CA-117 / RF-045)",
            "",
            f"> ⛔ **{gate.selo}**" if not gate.congelada else f"> ✅ **{gate.veredito}**",
            ">",
            "> Cópia literal da §1 de `docs/plans/DECISIONS_LOG.md`, com os 4 campos que o "
            "contrato exige: **fonte pedida**, **fonte usada**, **por quê** e **impacto na "
            "comparabilidade**. Todas as 12 são **provisórias** — nenhuma recebeu aval de "
            "Edu/Alexandre.",
            "",
        ]
    )


def arquivos_do_pacote(pacote: Path) -> tuple[Path, ...]:
    """Todo arquivo do pacote, em ordem alfabética do caminho POSIX relativo."""
    return tuple(
        sorted(
            (p for p in pacote.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(pacote).as_posix(),
        )
    )


def gravar_hashes(
    pacote: Path, *, manifesto: Mapping[str, Any], gate: Gate
) -> tuple[tuple[str, int, str], ...]:
    """`HASHES.txt` — `sha256` de cada arquivo do pacote + o `DATASET_SHA256`. ASCII puro."""
    destino = pacote / NOME_HASHES
    if destino.exists():
        destino.unlink()
    registros = tuple(
        (p.relative_to(pacote).as_posix(), p.stat().st_size, sha256_do_arquivo(p))
        for p in arquivos_do_pacote(pacote)
    )
    corpo = [
        f"PACOTE              : {NOME_DO_PACOTE}",
        f"VERSAO              : {VERSAO_DO_PACOTE}  ({FEATURE})",
        f"GATE                : {MARCA_NAO_CONGELADA_ASCII if not gate.congelada else 'ADR-001 aceito'}",  # noqa: E501
        f"STATUS_ADR_001      : {gate.status_adr_001}",
        f"VEREDITO            : {para_ascii(gate.veredito)}",
        f"DATASET_SHA256      : {dataset_sha256(manifesto)}",
        f"TAG_PREVISTA        : {TAG_DA_ENTREGA}  (git tag e ato humano - gate passo 4)",
        f"ARQUIVOS            : {len(registros)}",
        "",
        "Formato abaixo: '<sha256>  <bytes>  <caminho relativo>', ordenado por caminho POSIX.",
        f"O proprio {NOME_HASHES} nao se autoinclui. Nenhum arquivo foi editado a mao (CA-114).",
        "",
    ]
    corpo += [f"{sha}  {tamanho:>10}  {nome}" for nome, tamanho, sha in registros]
    corpo.append("")
    destino.write_text(para_ascii("\n".join(corpo)), encoding="utf-8", newline="\n")
    return registros


def zipar_deterministico(origem: Path, destino: Path) -> str:
    """`.zip` com timestamps fixos e ordem fixa. Devolve o `sha256` do arquivo gerado."""
    if destino.exists():
        destino.unlink()
    with zipfile.ZipFile(
        destino, "w", zipfile.ZIP_DEFLATED, compresslevel=NIVEL_DE_COMPRESSAO
    ) as saida:
        for alvo in arquivos_do_pacote(origem):
            relativo = f"{origem.name}/{alvo.relative_to(origem).as_posix()}"
            info = zipfile.ZipInfo(relativo, date_time=DATA_FIXA_NO_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            saida.writestr(info, alvo.read_bytes())
    return sha256_do_arquivo(destino)


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test do pacote (`infra-ops.md §1.5`) — passo 6 do gate
# ─────────────────────────────────────────────────────────────────────────────

OK = "OK"
FALHA = "FALHA"
INFO = "INFO"


@dataclass(frozen=True, slots=True)
class Checagem:
    """Uma linha do smoke: o que foi conferido, o veredito e a evidência."""

    nome: str
    veredito: str
    evidencia: str

    @property
    def falhou(self) -> bool:
        return self.veredito == FALHA


@dataclass(slots=True)
class ResultadoSmoke:
    """O smoke inteiro. `rc != 0` se qualquer checagem falhou."""

    pacote: Path
    checagens: list[Checagem] = field(default_factory=list)

    def registrar(self, nome: str, ok: bool, evidencia: str) -> None:
        self.checagens.append(Checagem(nome, OK if ok else FALHA, evidencia))

    def informar(self, nome: str, evidencia: str) -> None:
        self.checagens.append(Checagem(nome, INFO, evidencia))

    @property
    def falhas(self) -> tuple[Checagem, ...]:
        return tuple(c for c in self.checagens if c.falhou)

    @property
    def rc(self) -> int:
        return 1 if self.falhas else 0


def artefatos_proibidos_no_pacote(pacote: Path, proibidos: Mapping[str, str]) -> tuple[str, ...]:
    """Os nomes-base de artefatos `publicavel: false` encontrados **em qualquer lugar** do pacote.

    Compara pelo nome do arquivo, não pelo caminho: o pacote reorganiza as pastas, então um
    `internacional_pesos.parquet` copiado para `dados/` tem de ser pego do mesmo jeito.
    """
    bases = {Path(nome).name for nome in proibidos}
    encontrados = {
        alvo.relative_to(pacote).as_posix()
        for alvo in arquivos_do_pacote(pacote)
        if alvo.name in bases
    }
    return tuple(sorted(encontrados))


def _conferir_tabela(
    resultado: ResultadoSmoke,
    *,
    nome: str,
    pacote: Path,
    indice_do_manifesto: Mapping[str, Mapping[str, Any]],
) -> None:
    """Abre o Parquet e o CSV da tabela, confere linhas vs. manifesto, datas e nulos críticos."""
    parquet = pacote / "dados" / f"{nome}.parquet"
    csv = pacote / "dados" / f"{nome}.csv"
    if not parquet.is_file() or not csv.is_file():
        resultado.registrar(
            f"{nome}: Parquet + CSV presentes",
            False,
            f"parquet={parquet.is_file()} csv={csv.is_file()}",
        )
        return
    dados = pd.read_parquet(parquet)
    do_csv = ler_csv_ptbr(csv)
    entrada = indice_do_manifesto.get(f"{nome}.parquet") or {}
    esperado = entrada.get("linhas")
    resultado.registrar(
        f"{nome}: linhas Parquet == MANIFEST",
        esperado is None or int(esperado) == len(dados),
        f"{len(dados)} linhas (MANIFEST: {esperado})",
    )
    resultado.registrar(
        f"{nome}: paridade Parquet x CSV",
        len(dados) == len(do_csv) and list(dados.columns) == list(do_csv.columns),
        f"parquet {dados.shape} x csv {do_csv.shape}",
    )
    resultado.registrar(
        f"{nome}: sha256 do Parquet == MANIFEST",
        str(entrada.get("sha256") or "") == sha256_do_arquivo(parquet),
        f"{sha256_do_arquivo(parquet)[:16]}... (MANIFEST: {str(entrada.get('sha256'))[:16]}...)",
    )
    _conferir_datas(resultado, nome=nome, dados=dados, entrada=entrada)
    _conferir_nulos(resultado, nome=nome, dados=dados)


def _conferir_datas(
    resultado: ResultadoSmoke,
    *,
    nome: str,
    dados: pd.DataFrame,
    entrada: Mapping[str, Any],
) -> None:
    coluna = entrada.get("coluna_de_data")
    if not coluna or coluna not in dados.columns:
        resultado.informar(f"{nome}: min/max de data", "tabela sem coluna de data no MANIFEST")
        return
    serie = dados[coluna].dropna().astype(str)
    minimo, maximo = (serie.min(), serie.max()) if not serie.empty else ("", "")
    esperados = (str(entrada.get("date_min") or ""), str(entrada.get("date_max") or ""))
    resultado.registrar(
        f"{nome}: min/max de {coluna} == MANIFEST",
        (minimo, maximo) == esperados,
        f"{minimo} -> {maximo} (MANIFEST: {esperados[0]} -> {esperados[1]})",
    )


def _conferir_nulos(resultado: ResultadoSmoke, *, nome: str, dados: pd.DataFrame) -> None:
    criticas = [c for c in COLUNAS_CRITICAS.get(nome, ()) if c in dados.columns]
    faltando = [c for c in COLUNAS_CRITICAS.get(nome, ()) if c not in dados.columns]
    if faltando:
        resultado.registrar(
            f"{nome}: colunas criticas presentes", False, f"ausentes: {', '.join(faltando)}"
        )
        return
    nulos = {c: int(dados[c].isna().sum()) for c in criticas}
    com_nulo = {c: n for c, n in nulos.items() if n}
    resultado.registrar(
        f"{nome}: zero nulos nas {len(criticas)} colunas criticas",
        not com_nulo,
        "zero nulos" if not com_nulo else f"nulos em {com_nulo}",
    )
    if nome == "asset_returns_quarterly":
        ancoras = int(dados["ret_tri"].isna().sum())
        sem_preco_inicial = int(dados.loc[dados["ret_tri"].isna(), "price_ini"].isna().sum())
        resultado.registrar(
            f"{nome}: nulo de ret_tri so nas {N_ANCORAS_SEM_RETORNO} ancoras",
            ancoras == N_ANCORAS_SEM_RETORNO == sem_preco_inicial,
            f"{ancoras} linhas sem ret_tri, {sem_preco_inicial} delas sem price_ini",
        )
    if nome in {"regimes_v1", "regimes_v1_asof"}:
        nulos_de_regime = int(dados["regime_v1"].isna().sum())
        indeterminados = int((dados["status_regime_v1"] == STATUS_INDETERMINADO).sum())
        resultado.registrar(
            f"{nome}: nulo de regime_v1 so nos {N_TRIMESTRES_INDETERMINADOS} indeterminados",
            nulos_de_regime == indeterminados == N_TRIMESTRES_INDETERMINADOS,
            f"{nulos_de_regime} nulos, {indeterminados} com status {STATUS_INDETERMINADO}",
        )


def _conferir_xlsx(resultado: ResultadoSmoke, *, pacote: Path, gate: Gate) -> None:
    alvo = pacote / NOME_XLSX
    if not alvo.is_file():
        resultado.registrar(f"{NOME_XLSX}: presente", False, "arquivo ausente")
        return
    livro = load_workbook(alvo, read_only=True, data_only=True)
    try:
        abas = tuple(livro.sheetnames)
        resultado.registrar(
            f"{NOME_XLSX}: as {len(ABAS_ESPERADAS)} abas esperadas",
            abas == ABAS_ESPERADAS,
            f"abas: {' | '.join(abas)}",
        )
        for aba, esperado in _dimensoes_esperadas(pacote).items():
            if aba not in abas:
                resultado.registrar(f"{NOME_XLSX}/{aba}: dimensao", False, "aba ausente")
                continue
            planilha = livro[aba]
            obtido = (planilha.max_row, planilha.max_column)
            resultado.registrar(
                f"{NOME_XLSX}/{aba}: dimensao",
                obtido == esperado,
                f"{obtido[0]}x{obtido[1]} (esperado {esperado[0]}x{esperado[1]})",
            )
        texto = _texto_da_aba(livro[ABA_LEIA_ME]) if ABA_LEIA_ME in abas else ""
        resultado.registrar(
            f"{NOME_XLSX}: DATASET_SHA256 na aba {ABA_LEIA_ME}",
            "DATASET_SHA256" in texto,
            f"{len(texto)} caracteres na aba",
        )
        if not gate.congelada:
            resultado.registrar(
                f"{NOME_XLSX}: texto do gate na aba {ABA_LEIA_ME}",
                MARCADOR_DO_GATE in texto and TEXTO_DO_GATE_NAO_PUBLICAVEL in texto,
                f"marcador={MARCADOR_DO_GATE in texto} "
                f"selo={TEXTO_DO_GATE_NAO_PUBLICAVEL in texto}",
            )
    finally:
        livro.close()


def _dimensoes_esperadas(pacote: Path) -> dict[str, tuple[int, int]]:
    """As dimensões que as abas de dado têm de ter, derivadas dos Parquet do próprio pacote."""
    esperadas: dict[str, tuple[int, int]] = {}
    for aba, nome in ((ABA_MACRO, "macro_quarterly"), (ABA_RETORNOS, "asset_returns_quarterly")):
        alvo = pacote / "dados" / f"{nome}.parquet"
        if alvo.is_file():
            dados = pd.read_parquet(alvo)
            esperadas[aba] = (len(dados) + 1, len(dados.columns))
    esperadas[ABA_HEATMAP] = (
        3 + N_ATIVOS_NO_HEATMAP,
        1 + 2 * N_REGIMES_NO_HEATMAP,
    )
    ranking = pacote / "tabelas" / "ranking_regime_atual.csv"
    if ranking.is_file():
        linhas_do_ranking = ler_csv_de_f024(ranking)
        # bloco A: título (1) + branco + cabeçalho na 3 + 3 lentes = 6; rótulo do B na 8;
        # cabeçalho do B na 10; uma linha por célula do ranking depois.
        esperadas[ABA_REGIME_ATUAL] = (
            10 + len(linhas_do_ranking),
            max(len(linhas_do_ranking.columns), N_COLUNAS_DO_BLOCO_A),
        )
    neighbors = pacote / "dados" / "regime_neighbors_v3.parquet"
    if neighbors.is_file():
        vizinhos = vizinhos_do_quarter(pd.read_parquet(neighbors), quarter=QUARTER_DO_COMITE)
        esperadas[ABA_VIZINHOS] = (len(vizinhos) + 1, len(vizinhos.columns))
    esperadas[ABA_LIMITACOES] = (N_LIMITACOES + 1, 2)
    esperadas[ABA_DECISOES] = (N_DECISOES + 1, 4)
    return esperadas


def _texto_da_aba(planilha: Any) -> str:
    return "\n".join(
        str(celula.value)
        for linha in planilha.iter_rows()
        for celula in linha
        if celula.value is not None
    )


def _conferir_notebook_e_html(resultado: ResultadoSmoke, *, pacote: Path, gate: Gate) -> None:
    html = pacote / "notebook" / CAMINHO_NOTEBOOK_HTML.name
    ipynb = pacote / "notebook" / CAMINHO_NOTEBOOK_LIMPO.name
    resultado.registrar(
        "notebook: .ipynb limpo presente",
        ipynb.is_file() and ipynb.stat().st_size > 0,
        f"{ipynb.name} ({ipynb.stat().st_size if ipynb.is_file() else 0} bytes)",
    )
    if not html.is_file():
        resultado.registrar("notebook: HTML executado presente", False, "HTML ausente")
        return
    texto = html.read_text(encoding="utf-8")
    resultado.registrar(
        "notebook: HTML cita DATASET_SHA256",
        "DATASET_SHA256" in texto,
        f"{texto.count('DATASET_SHA256')} ocorrencia(s) em {html.stat().st_size} bytes",
    )
    if not gate.congelada:
        resultado.registrar(
            "notebook: texto do gate no HTML",
            MARCA_NAO_CONGELADA in texto or MARCA_NAO_CONGELADA_ASCII in texto,
            f"selo acentuado={MARCA_NAO_CONGELADA in texto} "
            f"ascii={MARCA_NAO_CONGELADA_ASCII in texto}",
        )
    _conferir_hash_citado_no_html(resultado, texto=texto, pacote=pacote)


_RE_SHA256 = re.compile(r"\b[0-9a-f]{64}\b")


def _conferir_hash_citado_no_html(resultado: ResultadoSmoke, *, texto: str, pacote: Path) -> None:
    """O agregado citado no HTML × o do manifesto — **INFO**, e a nota diz por quê.

    O HTML executado **é** um artefato do manifesto e entra no agregado. Logo o agregado que o
    caderno imprime é, por construção, o da rodada **anterior** à inclusão do próprio HTML: exigir
    igualdade aqui seria exigir que um hash contenha a si mesmo. O que vale como versão do pacote
    é o `DATASET_SHA256` de `MANIFEST.json`/`HASHES.txt`.
    """
    manifesto_do_pacote = pacote / NOME_MANIFESTO
    if not manifesto_do_pacote.is_file():
        return
    agregado = dataset_sha256(json.loads(manifesto_do_pacote.read_text(encoding="utf-8")))
    citados = set(_RE_SHA256.findall(texto))
    if agregado in citados:
        resultado.informar(
            "notebook: agregado citado no HTML == MANIFEST", f"{agregado[:16]}... coincide"
        )
        return
    resultado.informar(
        "notebook: agregado citado no HTML != MANIFEST",
        f"esperado por construcao: o HTML e artefato do manifesto e entra no agregado, "
        f"logo cita o agregado da rodada anterior. MANIFEST: {agregado[:16]}...",
    )


def smoke(
    pacote: Path, *, raiz: Path | None = None, manifesto: Mapping[str, Any] | None = None
) -> ResultadoSmoke:
    """O smoke test do pacote de `infra-ops.md §1.5`, automatizado. `rc != 0` em qualquer falha."""
    resultado = ResultadoSmoke(pacote=pacote)
    if not pacote.is_dir():
        resultado.registrar("pacote: diretorio existe", False, f"{pacote} nao e diretorio")
        return resultado
    do_disco = dict(manifesto) if manifesto is not None else ler_manifesto(raiz=raiz)
    gate = ler_gate(raiz=raiz)
    indice = artefatos_do_manifesto(do_disco)

    resultado.informar("gate: ADR-001 em disco", f"{gate.status_adr_001} -> {gate.veredito}")

    proibidos = nao_publicaveis(do_disco)
    encontrados = artefatos_proibidos_no_pacote(pacote, proibidos)
    resultado.registrar(
        f"exclusao: nenhum dos {len(proibidos)} artefatos 'publicavel: false' no pacote",
        not encontrados,
        "nenhum" if not encontrados else f"PROIBIDO no pacote: {', '.join(encontrados)}",
    )

    for nome in TABELAS_DO_PACOTE:
        _conferir_tabela(resultado, nome=nome, pacote=pacote, indice_do_manifesto=indice)

    for nome in FIGURAS_DO_PACOTE:
        for extensao in EXTENSOES_DE_FIGURA:
            alvo = pacote / "figuras" / f"{nome}.{extensao}"
            resultado.registrar(
                f"figura {nome}.{extensao}",
                alvo.is_file() and alvo.stat().st_size > 0,
                f"{alvo.stat().st_size if alvo.is_file() else 0} bytes",
            )
    for nome in TABELAS_DE_UMA_PAGINA:
        for extensao in EXTENSOES_DE_TABELA:
            alvo = pacote / "tabelas" / f"{nome}.{extensao}"
            resultado.registrar(
                f"tabela de 1 pagina {nome}.{extensao}",
                alvo.is_file() and alvo.stat().st_size > 0,
                f"{alvo.stat().st_size if alvo.is_file() else 0} bytes",
            )

    _conferir_xlsx(resultado, pacote=pacote, gate=gate)
    _conferir_notebook_e_html(resultado, pacote=pacote, gate=gate)
    _conferir_documentos(resultado, pacote=pacote, gate=gate, manifesto=do_disco)
    _conferir_hashes(resultado, pacote=pacote)
    return resultado


def _conferir_documentos(
    resultado: ResultadoSmoke, *, pacote: Path, gate: Gate, manifesto: Mapping[str, Any]
) -> None:
    readme = pacote / NOME_README
    resultado.registrar(
        f"{NOME_README}: presente", readme.is_file(), "ok" if readme.is_file() else "ausente"
    )
    if readme.is_file():
        texto = readme.read_text(encoding="utf-8")
        resultado.registrar(
            f"{NOME_README}: cita versao e DATASET_SHA256",
            VERSAO_DO_PACOTE in texto and dataset_sha256(manifesto) in texto,
            f"versao={VERSAO_DO_PACOTE in texto} hash={dataset_sha256(manifesto) in texto}",
        )
        if not gate.congelada:
            resultado.registrar(
                f"{NOME_README}: texto do gate no topo",
                MARCADOR_DO_GATE in texto.split("## 1.")[0],
                f"marcador no preambulo={MARCADOR_DO_GATE in texto.split('## 1.')[0]}",
            )
        try:
            _linguagem.conferir_linguagem_descritiva(texto, origem=NOME_README)
            descritivo, detalhe = True, "nenhum termo preditivo sem negacao"
        except SerieInconsistente as erro:  # pragma: no cover - a guarda roda na montagem
            descritivo, detalhe = False, str(erro)
        resultado.registrar(f"{NOME_README}: linguagem descritiva", descritivo, detalhe)
    for nome in (NOME_LIMITACOES, NOME_SUBSTITUICOES, NOME_MANIFESTO):
        alvo = pacote / nome
        resultado.registrar(
            f"{nome}: presente",
            alvo.is_file() and alvo.stat().st_size > 0,
            f"{alvo.stat().st_size if alvo.is_file() else 0} bytes",
        )
    frozen = pacote / NOME_FROZEN
    if frozen.is_file():
        resultado.registrar(
            f"{NOME_FROZEN}: cita a tag da entrega",
            TAG_DA_ENTREGA in frozen.read_text(encoding="utf-8"),
            f"{frozen.stat().st_size} bytes",
        )
    else:
        resultado.informar(
            f"{NOME_FROZEN}: ausente",
            "passo 4 do gate (`python -m apps.pipeline freeze --tag "
            f"{TAG_DA_ENTREGA}`) e ato do Edu e ainda nao foi executado",
        )


def _conferir_hashes(resultado: ResultadoSmoke, *, pacote: Path) -> None:
    alvo = pacote / NOME_HASHES
    if not alvo.is_file():
        resultado.registrar(f"{NOME_HASHES}: presente", False, "ausente")
        return
    texto = alvo.read_text(encoding="utf-8")
    citados = {
        partes[2]: partes[0]
        for partes in (linha.split() for linha in texto.splitlines())
        if len(partes) == 3 and _RE_SHA256.fullmatch(partes[0])
    }
    esperados = {
        p.relative_to(pacote).as_posix(): sha256_do_arquivo(p)
        for p in arquivos_do_pacote(pacote)
        if p.name != NOME_HASHES
    }
    divergentes = {
        nome: (sha, citados.get(nome))
        for nome, sha in esperados.items()
        if citados.get(nome) != sha
    }
    resultado.registrar(
        f"{NOME_HASHES}: cobre os {len(esperados)} arquivos, com sha256 conferido",
        not divergentes and len(citados) == len(esperados),
        "todos conferem"
        if not divergentes and len(citados) == len(esperados)
        else f"{len(divergentes)} divergencia(s), {len(citados)} citados x {len(esperados)}",
    )
    resultado.registrar(
        f"{NOME_HASHES}: traz o DATASET_SHA256",
        "DATASET_SHA256" in texto,
        "linha presente" if "DATASET_SHA256" in texto else "linha ausente",
    )


def imprimir_smoke(resultado: ResultadoSmoke) -> None:
    """A saída colável do smoke, em ASCII puro (Anti-SPEC §10.4.26)."""
    _imprimir("")
    _imprimir(f"SMOKE TEST DO PACOTE - {resultado.pacote}")
    _imprimir("-" * 100)
    for checagem in resultado.checagens:
        _imprimir(f"[{checagem.veredito:4}] {checagem.nome}: {checagem.evidencia}")
    _imprimir("-" * 100)
    total = len(resultado.checagens)
    informativas = sum(1 for c in resultado.checagens if c.veredito == INFO)
    _imprimir(
        f"{total} checagens: {total - len(resultado.falhas) - informativas} OK, "
        f"{len(resultado.falhas)} FALHA, {informativas} INFO -> rc={resultado.rc}"
    )


def imprimir_montagem(resultado: ResultadoMontagem) -> None:
    """A árvore do pacote com tamanhos + os hashes, colável no relatório."""
    _imprimir(f"PACOTE   : {resultado.pacote}")
    _imprimir(f"ZIP      : {resultado.zip}")
    _imprimir(f"SHA256   : {resultado.sha256_do_zip}")
    _imprimir(
        f"GATE     : {para_ascii(resultado.gate.veredito)} "
        f"(ADR-001 em {resultado.gate.status_adr_001})"
    )
    _imprimir(f"DATASET  : {dataset_sha256(resultado.manifesto)}")
    _imprimir(f"EXCLUIDOS: {', '.join(sorted(resultado.excluidos)) or 'nenhum'}")
    estado_do_frozen = "presente" if resultado.frozen_presente else "AUSENTE (passo 4 do Edu)"
    _imprimir(f"FROZEN   : {estado_do_frozen}")
    _imprimir("")
    total = 0
    for nome, tamanho, _ in resultado.arquivos:
        total += tamanho
        _imprimir(f"{tamanho:>12}  {nome}")
    _imprimir(f"{total:>12}  TOTAL ({len(resultado.arquivos)} arquivos)")
    _imprimir(f"{resultado.zip.stat().st_size:>12}  {resultado.zip.name}")
    _imprimir("")
    for linha in AVISO_SOBRE_VERIFY:
        _imprimir(linha)


AVISO_SOBRE_VERIFY: tuple[str, ...] = (
    "ORDEM DO GATE (interacao com F-029, resolvida em D-ag):",
    "  O pacote vive DENTRO de data/canonical/, que `python -m apps.pipeline verify` cobre",
    "  recursivamente. Desde D-ag (2026-10-11) `inventariar()` ignora o prefixo",
    "  entrega/pacote_comite_, entao o pacote em disco NAO reprova mais o verify e NAO entra",
    "  no DATASET_SHA256 - conferido: VERIFY OK com o pacote montado, agregado inalterado.",
    "  Ordem correta do gate, ainda assim: run --offline -> verify -> freeze --tag ->",
    "  montar_pacote --smoke. O pacote copia o MANIFEST.json, logo precisa do freeze antes.",
    "  `montar_pacote --limpar` continua existindo para apagar o pacote quando quiser.",
)
"""O aviso que o gate precisa ler. Ver `docs/wiki/runbooks/entrega-comite.md §1` e §5."""


def limpar(*, raiz: Path | None = None, saida: Path | None = None) -> tuple[Path, ...]:
    """Apaga o diretório do pacote e o `.zip`, para `verify`/`freeze` voltarem a passar.

    Existe por causa da interação descrita em `AVISO_SOBRE_VERIFY`: o pacote é artefato de
    entrega **dentro** da árvore que o `verify` protege. Apagar é seguro — o pacote é
    reconstruível por um comando, e é isso que CA-114 garante.
    """
    pacote = saida or caminho_do_pacote(raiz=raiz)
    removidos: list[Path] = []
    arquivo_zip = pacote.with_name(f"{pacote.name}.zip")
    if pacote.is_dir():
        shutil.rmtree(pacote)
        removidos.append(pacote)
    if arquivo_zip.is_file():
        arquivo_zip.unlink()
        removidos.append(arquivo_zip)
    return tuple(removidos)


def _imprimir(texto: str = "") -> None:
    print(para_ascii(texto))  # noqa: T201 - é a interface de linha de comando


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _validar_saida(saida: Path | None, *, raiz: Path | None) -> Path | None:
    """`--saida` só dentro de `<raiz>/data` — a mesma trava de `run.py`."""
    if saida is None:
        return None
    base = ((raiz or raiz_repo()) / "data").resolve()
    alvo = saida.resolve()
    if base not in alvo.parents and alvo != base:
        msg = (
            f"BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT: --saida precisa estar dentro de "
            f"{base}, e veio {alvo}."
        )
        raise SerieInconsistente(msg)
    return alvo


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.analysis.entrega.montar_pacote",
        description=(
            "Monta o pacote de entrega ao Comite (F-031) SEM publicar. O envio e ato humano e "
            "exige os 8 passos de AGENTS.md secao 14 - ver "
            "docs/wiki/runbooks/entrega-comite.md."
        ),
    )
    parser.add_argument("--saida", type=Path, help="diretorio do pacote (dentro de data/)")
    parser.add_argument("--raiz", type=Path, help="arvore alternativa com data/ (testes)")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="roda o smoke test depois de montar (rc != 0 se falhar)",
    )
    parser.add_argument(
        "--so-smoke",
        action="store_true",
        help="nao monta: roda o smoke sobre o pacote que ja esta em disco",
    )
    parser.add_argument(
        "--limpar",
        action="store_true",
        help="apaga o pacote e o .zip (para `apps.pipeline verify`/`freeze` voltarem a passar)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada. `0` = tudo certo; `1` = smoke reprovou; `2` = bloqueio de contrato."""
    argumentos = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        saida = _validar_saida(argumentos.saida, raiz=argumentos.raiz)
        if argumentos.limpar:
            removidos = limpar(raiz=argumentos.raiz, saida=saida)
            for alvo in removidos:
                _imprimir(f"REMOVIDO : {alvo}")
            if not removidos:
                _imprimir("nada a remover: o pacote nao esta em disco")
            _imprimir(
                "Agora `python -m apps.pipeline verify` e `freeze` voltam a cobrir so o canonico."
            )
            return 0
        if argumentos.so_smoke:
            pacote = saida or caminho_do_pacote(raiz=argumentos.raiz)
            resultado_smoke = smoke(pacote, raiz=argumentos.raiz)
            imprimir_smoke(resultado_smoke)
            return resultado_smoke.rc
        montado = montar(raiz=argumentos.raiz, saida=saida)
        imprimir_montagem(montado)
        if not montado.gate.congelada:
            _imprimir("")
            _imprimir(f"*** {para_ascii(VEREDITO_BLOQUEADO)} ***")
            _imprimir(
                "O pacote esta montado e selado como NAO PUBLICAVEL. ENQUANTO ADR-001 ESTIVER "
                "EM PROPOSTA, O PACOTE NAO SAI (AGENTS.md secao 14, passo 2)."
            )
        if argumentos.smoke:
            resultado_smoke = smoke(
                montado.pacote, raiz=argumentos.raiz, manifesto=montado.manifesto
            )
            imprimir_smoke(resultado_smoke)
            return resultado_smoke.rc
    except SerieInconsistente as erro:
        _imprimir(str(erro))
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de linha de comando
    raise SystemExit(main())
