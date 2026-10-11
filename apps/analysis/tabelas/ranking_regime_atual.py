"""F-024 — Tabela de 1 página "regime atual → ranking de ativos" + concordância entre lentes.

**RF-034 / CA-098, CA-099 · RF-037 / CA-103 · CA-090 como gate.**

O que esta tabela é, em uma frase: a página que o Comitê lê quando pergunta *"em que regime
estamos e o que performou em momentos assim?"* — e que responde **três vezes**, porque as três
lentes do projeto discordam e esconder isso seria o único erro irreparável aqui.

## Os quatro blocos, e por que cada um existe

- **A — "Em que regime estamos?", com as 3 respostas lado a lado** (CA-098). A V1 `revised` não
  tem quadrante para `2026Q3` (**D-m**); a V1 `asof` tem um, mas é a materialização que
  **CA-074** reprovou; a V3 responde com 8 vizinhos. Escolher uma seria decidir por fora do
  ADR-001 — então as três aparecem, com a regra de leitura.
- **B — ranking dos 24 ativos por lente**, ordenado por `excesso_cdi` (CA-098/CA-099): `n` e
  erro-padrão em toda linha, símbolo para `n < 8` e `n < 5`, nenhuma afirmação conclusiva
  abaixo de 5.
- **C — concordância** (CA-103): Jaccard top-5/top-10, **Spearman** sobre os 24 ativos e a
  **distribuição** do Jaccard `somente_passado` × descritiva nas referências da V3. A
  divergência **é** o resultado; a distribuição existe porque citar só `2026Q3` é escolher a
  evidência depois de ver o número (QA da Onda 3, **P1-2**).
- **D — "o que isso NÃO diz", em 3 linhas** (Anti-SPEC §10.2.8/§10.2.9/§10.2.10): `n` pequeno,
  especificação não congelada, descritivo ≠ preditivo. É o que blinda a reunião.

## O que entra

| Insumo | Arquivo em `data/canonical/` | O que se lê dele |
|---|---|---|
| métricas, lente canônica | `regime_asset_metrics.parquet` | V1 `revised` em `T0`, V3 em `T+1` |
| métricas, operacional | `regime_asset_metrics_asof.parquet` | V1 `asof` em `T0` |
| V1 `revised`/`asof` | `regimes_v1{,_asof}.parquet` | rótulo, `status`, `motivo`, **CA-074** |
| V3 | `regime_neighbors_v3.parquet` (**D-u**) | 8 vizinhos, `T+1` e as 2 variantes |

Saída em `data/canonical/tabelas/`: `ranking_regime_atual.{parquet,csv,md}` e
`concordancia_lentes.{parquet,csv,md}`. O `.md` é a página; os outros dois são o **mesmo** dado,
conferível linha a linha.

## As três decisões que não são de gosto

1. **A página nunca escolhe uma lente.** Há uma `REGRA_DE_LEITURA` escrita no bloco A dizendo o
   que cada resposta serve para responder, e nada mais. A alternativa — abrir com a `asof`, que é
   a única que dá um rótulo para `2026Q3` — seria publicar como "o regime atual" exatamente a
   materialização que **CA-074 já reprovou** (troca de rótulo em 33,33% dos trimestres
   comparáveis, acima do limiar de 25%). A escolha de qual lente abre a página é **D1**, do Edu.
2. **O ranking da V1 `revised` sai do fallback `2026Q2`, e a palavra "fallback" aparece em toda
   linha.** `2026Q3` é `INDETERMINADO` por construção (o IBC-Br dessazonalizado do trimestre
   corrente não fecha antes do fim do trimestre, e `ibcbr_gap` precisa de média móvel de 20
   trimestres). Não há quadrante a estimar (Anti-SPEC §10.1.1); há o **último trimestre com
   quadrante**, rotulado como tal — no dado, no CSV e na página.
3. **Spearman implementado à mão em numpy.** `scipy` não está no `.venv` e instalar dependência
   exige ADR (Anti-SPEC §10.4.25), com entrega em 2026-10-14. A correlação de posto com empate
   médio são ~10 linhas (`postos` + `spearman`) e tem caso conhecido no teste
   (`x=[1,2,3,4,5]`, `y=[2,1,4,3,5]` ⇒ `rho = 0,8` pela fórmula fechada `1 − 6Σd²/n(n²−1)`).

## Honestidade estatística (Anti-SPEC §10.2)

- **Descritivo, nunca preditivo** (§10.2.10): há guarda executável —
  `conferir_linguagem_descritiva` levanta se qualquer forma de previsão aparecer no Markdown.
- **`n` em toda célula** (§10.2.8): a coluna `n_obs` é obrigatória nas 72 linhas, e `simbolo_n`
  traduz os limiares `N_ALERTA`/`N_SUPRESSAO` importados de F-019 — nunca redefinidos aqui.
- **`asof` sempre rotulada** (§10.2.7): a materialização está no nome da lente, na coluna
  `materializacao` e na ressalva de CA-074.
- **Nada escolhido depois de ver o número** (§10.2.9): o bloco C publica a **distribuição** do
  Jaccard sobre todas as referências, não só a do trimestre do Comitê.
- **Gate de publicação** (CA-090): `especificacao_congelada=False` ⇒ a página nasce com a marca
  `ESPECIFICAÇÃO NÃO CONGELADA — não publicável` e o rodapé repete o veredito.

## Determinismo

Nenhum valor sai do relógio, da rede ou do ambiente. Toda formatação é fixa (pt-BR, 2 casas), o
Markdown é montado a partir dos DataFrames e os dois Parquets saem byte-idênticos em rodadas
sucessivas no mesmo checkout.

**Nota de contrato:** `data/canonical/tabelas/` é artefato **derivado de análise**, não tabela
canônica — por isso não tem schema em `packages/shared/schemas/` (F-024 é classe B e não
acrescenta schema). O contrato das colunas é `COLUNAS_RANKING`/`COLUNAS_CONCORDANCIA`, travado por
teste, e todo nome herdado de `regime_asset_metrics` é **literal**, sem renomeação.

Cobre: RF-034, RF-037 · CA-098, CA-099, CA-103 (+ CA-090 como gate) · e-mail: o objetivo literal ·
Anti-SPEC §10.2.7, §10.2.8, §10.2.9, §10.2.10, §10.4.25, §10.4.26.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.canonical.build_raw_series import caminhos_dos_componentes
from apps.pipeline.canonical.build_raw_series import versao_build as _hash_dos_componentes
from apps.pipeline.canonical.metricas_regime import (
    COLUNA_PRIMARIA,
    LENTE_V1,
    LENTE_V3,
    TABELA_ASOF,
    TABELA_PRINCIPAL,
    Horizonte,
    Tabela,
    concordancia_entre_lentes,
    ler_neighbors_v3,
    ler_regimes_v1,
    nome_do_regime_v3,
    ranking_do_regime,
)
from apps.pipeline.canonical.regimes_v1 import (
    LIMIAR_TROCA_REGIME_INOPERANTE,
    Materializacao,
    alerta_n_baixo,
    conclusao_suprimida,
    divergencia_entre_materializacoes,
    especificacao_esta_congelada,
    status_adr_001,
    veredito_publicacao,
)
from apps.pipeline.canonical.regimes_v3 import QUARTER_DO_COMITE
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, garantir_diretorio, raiz_repo
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from packages.shared.schemas.asset_returns_quarterly import RegimeAssetMetricsSchema
from packages.shared.schemas.regimes import (
    K_VIZINHOS_PADRAO,
    N_ALERTA,
    N_SUPRESSAO,
    MetricaDistancia,
    MotivoIndeterminado,
    StatusRegimeV1,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes, destinos e constantes
# ─────────────────────────────────────────────────────────────────────────────

#: Subpasta de `data/canonical/` onde as tabelas desta camada vivem.
SUBPASTA_TABELAS = "tabelas"

NOME_RANKING = "ranking_regime_atual"
NOME_CONCORDANCIA = "concordancia_lentes"
FORMATOS: tuple[str, ...] = ("parquet", "csv", "md")

NOME_REGIMES_V1 = "regimes_v1.parquet"
NOME_REGIMES_V1_ASOF = "regimes_v1_asof.parquet"
NOME_NEIGHBORS_V3 = "regime_neighbors_v3.parquet"

#: Os módulos que determinam o conteúdo desta página, **nesta ordem** — base de `versao_build`.
#: Mesmo critério de F-022/F-025: este módulo, o produtor das métricas que ele lê e os dois
#: contratos onde moram os limiares de `n` e os nomes das colunas. Mudar qualquer um muda a página.
MODULOS_DA_TABELA: tuple[str, ...] = (
    "apps.analysis.tabelas.ranking_regime_atual",
    "apps.pipeline.canonical.metricas_regime",
    "packages.shared.schemas.asset_returns_quarterly",
    "packages.shared.schemas.regimes",
)

N_ATIVOS_ESPERADO = 24
"""Os 24 `asset_id` de `asset_returns_quarterly` (F-017). Linha faltando é falha, não omissão."""

N_LENTES = 3
"""V1 `revised`, V1 `asof` e V3 — as três respostas de CA-098. **V2 não existe** (F-020 cortada)."""

SEPARADOR_DE_PAR = "__x__"
"""Como `concordancia_entre_lentes` (F-022) nomeia um par de lentes. Reusado, nunca redefinido."""

TOPS_DA_CONCORDANCIA: tuple[int, ...] = (3, 5, 10)
"""`top-3` é o que CA-103 pede por lente; `top-5`/`top-10` são os pares de Jaccard do bloco C."""

LIMIAR_ERROS_PADRAO = 2.0
"""Quantos erros-padrão uma diferença precisa ter para não ser confundível com ruído.

Não é um teste de hipótese: é a nota de potência de `metodologia §3` escrita como número. Com
`n = 8` e erro-padrão de 2,5 a 5 pp, **nada** no ranking da V3 passa daqui — e é isso que a página
tem de dizer antes de qualquer ordem de ativos.
"""

SIMBOLO_N_OK = ""
SIMBOLO_N_ALERTA = "†"
SIMBOLO_N_SUPRIMIDO = "‡"
"""Os símbolos de `n` do bloco B. Os limiares vêm de F-019/contrato, nunca redefinidos aqui."""

LEGENDA_SIMBOLOS = (
    f"`†` n < {N_ALERTA} (ALERTA_N_BAIXO, CA-108) · "
    f"`‡` n < {N_SUPRESSAO} (conclusão suprimida, CA-099/CA-109: a linha fica, a conclusão não) · "
    f"`*` diferença acima de {LIMIAR_ERROS_PADRAO:.0f} erros-padrão da média"
)

MARCA_NAO_CONGELADA = "ESPECIFICAÇÃO NÃO CONGELADA — não publicável"
"""CA-090 por escrito. Enquanto ADR-001 estiver em `Proposta`, é obrigatória na página."""

MARCA_NAO_CONGELADA_ASCII = "ESPECIFICACAO NAO CONGELADA - nao publicavel"
"""A mesma marca, em ASCII puro, para `logging` e `print`.

O console do Windows é cp1252 e o `StreamHandler` do `logging` **não** aceita `encoding=`:
mandar o texto acentuado para lá produz `--- Logging error ---` e o aviso de CA-090 some
justamente quando mais importa. A versão acentuada vai ao Markdown, que é escrito com
`encoding="utf-8"` explícito (Anti-SPEC §10.4.26).
"""

TITULO = "Regime atual → ranking de ativos"

SUBTITULO_DESCRITIVO = (
    "Leitura **descritiva**: em trimestres semelhantes, cada ativo rendeu isto, com este `n`. "
    "Não há projeção, extrapolação nem recomendação de alocação nesta página "
    "(Anti-SPEC §10.2.10; a alocação é do Alexandre)."
)

REGRA_DE_LEITURA = (
    "**Regra de leitura — as três respostas servem a perguntas diferentes.** "
    'A **V1 `revised`** responde *"como foi o histórico, com o dado já revisado"*: é a lente '
    "descritiva, e para `{quarter}` ela **não tem resposta** — o que se faz com isso é usar o "
    "último trimestre com quadrante, **rotulado como fallback**, nunca chamado de regime atual. "
    'A **V1 `asof`** responde *"o que eu teria classificado no fim do trimestre"*: é a única com '
    "um rótulo para `{quarter}`, e é justamente a que **CA-074 reprovou** ({pct_troca} de troca de "
    "rótulo contra o limiar de {limiar}) — serve para o Comitê ver a alternativa, não como a "
    'resposta. A **V3** responde *"quais trimestres dos 20 anos mais se parecem com este"* e '
    "mede o trimestre **seguinte** a cada um deles (CA-102). "
    "**Qual delas abre a página é decisão do Edu (D1), não deste módulo** — e enquanto ADR-001 "
    "estiver em `Proposta` nenhuma das três é publicável (CA-090)."
)

#: As 3 linhas do bloco D. Curtas de propósito: é o que cabe no rodapé de um slide.
O_QUE_ISSO_NAO_DIZ: tuple[str, ...] = (
    "**`n` pequeno não distingue ativos.** Nesta página o `n` por célula vai de **{n_min} a "
    "{n_max}** trimestres e o erro-padrão da média, de **{ep_min} a {ep_max} pp**. Diferença de "
    "retorno menor que ~{limiar} erros-padrão é indistinguível de ruído: a **ordem** do topo não "
    "é um resultado, o **sinal** de uma célula com `n` grande é (metodologia §3, nota de "
    "potência).",
    "**A especificação de regime não está congelada.** ADR-001 está em `Proposta`: os eixos, o "
    "limiar de aceleração e o `k` da V3 ainda podem mudar, e mudar depois de ver estes números "
    "nasce como V1.1 com as duas versões lado a lado (Anti-SPEC §10.2.9). Nada aqui é publicável "
    "antes do gate de classe D (CA-090).",
    "**Descritivo não é preditivo.** Esta página mede o que aconteceu em trimestres parecidos, com "
    "amostra pequena, especificação provisória e sem nenhum custo de transação, imposto ou "
    "fricção de índice teórico. Não é previsão de retorno, não é backtest e não é recomendação de "
    "alocação (Anti-SPEC §10.2.10, §10.2.11, §10.3.16).",
)

#: Formas **assertivas** de previsão: não podem aparecer no Markdown de jeito nenhum. A guarda é
#: executável, não um pedido na revisão. Acentuada e sem acento, porque o acento é o primeiro a
#: cair quando alguém reescreve a frase à mão.
FORMAS_PREDITIVAS_PROIBIDAS: tuple[str, ...] = (
    "vai render",
    "vai subir",
    "vai cair",
    "vai performar",
    "deve render",
    "deve subir",
    "deve cair",
    "deve performar",
    "tende a render",
    "projetamos",
    "prevemos",
    "esperamos",
    "espera-se",
    "estimamos que",
    "recomendamos",
    "recomendacao de alocacao:",
    "sugerimos",
    "melhor aposta",
    "aposta para",
)

#: Substantivos preditivos que **só** podem aparecer sob negação ("não é previsão", "nenhum
#: backtest"). Proibi-los por inteiro tornaria o bloco D impossível de escrever — é justamente
#: nele que se diz o que a página **não** é; e permiti-los soltos deixaria passar um
#: "Previsão para 4T2026: +5%". Então a guarda exige a negação no contexto imediato.
SUBSTANTIVOS_PREDITIVOS_SOB_NEGACAO: tuple[str, ...] = (
    "previsao",
    "previsão",
    "projecao",
    "projeção",
    "extrapolacao",
    "extrapolação",
    "backtest",
    "recomendacao",
    "recomendação",
)

JANELA_DE_NEGACAO = 80
"""Quantos caracteres antes do termo a guarda olha procurando a negação."""

MARCADORES_DE_NEGACAO: tuple[str, ...] = (
    "não",
    "nao",
    "nunca",
    "nenhum",
    "nem ",
    "sem ",
    "≠",
    "proib",
    "fora de escopo",
    "fora desta",
)


class SecaoDaConcordancia(StrEnum):
    """As três seções do bloco C — vão **no dado**, não só no Markdown."""

    #: 1 linha por lente com o top-3 (a letra de CA-103).
    POR_LENTE = "POR_LENTE"
    #: Jaccard top-5/top-10 e Spearman, par a par.
    PAR_DE_LENTES = "PAR_DE_LENTES"
    #: A distribuição do Jaccard `somente_passado` × descritiva nas referências da V3 (QA P1-2).
    DISTRIBUICAO_SOMENTE_PASSADO = "DISTRIBUICAO_SOMENTE_PASSADO"


class StatusDaResposta(StrEnum):
    """Que tipo de resposta a lente dá para o trimestre perguntado."""

    #: A lente classifica o próprio trimestre perguntado.
    CLASSIFICADO = "CLASSIFICADO"
    #: A lente não tem quadrante para o trimestre; o ranking sai do fallback declarado.
    INDETERMINADO_COM_FALLBACK = "INDETERMINADO_COM_FALLBACK"
    #: A V3 não tem rótulo: tem um conjunto de vizinhos.
    VIZINHOS = "VIZINHOS"


# ─────────────────────────────────────────────────────────────────────────────
# O contrato de colunas das duas tabelas
# ─────────────────────────────────────────────────────────────────────────────

#: Colunas de `regime_asset_metrics` reproduzidas **com o mesmo nome e o mesmo significado**.
COLUNAS_HERDADAS_DE_METRICAS: tuple[str, ...] = (
    "lente",
    "regime",
    "asset_id",
    "n_obs",
    "excesso_cdi",
    "ret_medio",
    "ret_mediana",
    "hit_ratio_cdi",
    "erro_padrao_media",
    "alerta_n_baixo",
    "conclusao_suprimida",
    "fonte_versao",
)

#: O contrato completo de `ranking_regime_atual.parquet`, **nesta ordem**.
COLUNAS_RANKING: tuple[str, ...] = (
    "lente_rotulo",
    "lente_titulo",
    *COLUNAS_HERDADAS_DE_METRICAS[:3],
    "materializacao",
    "horizonte",
    "quarter_perguntado",
    "quarter_da_celula",
    "e_fallback",
    "tabela_de_origem",
    "posicao",
    *COLUNAS_HERDADAS_DE_METRICAS[3:],
    "excesso_em_erros_padrao",
    "distinguivel_de_ruido",
    "simbolo_n",
    "versao_build",
)

#: O contrato completo de `concordancia_lentes.parquet` — tabela **tidy**, chave/métrica/valor.
#: É o único formato em que as 3 seções do bloco C cabem num Parquet sem coluna inventada por
#: seção (Anti-SPEC §10.4.24 em espírito): quem quiser a seção filtra por `secao`.
COLUNAS_CONCORDANCIA: tuple[str, ...] = (
    "secao",
    "chave",
    "metrica",
    "valor_num",
    "valor_texto",
    "versao_build",
)


# ─────────────────────────────────────────────────────────────────────────────
# Estruturas
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RespostaDeRegime:
    """O que **uma** lente responde a "em que regime estamos?" — uma linha do bloco A."""

    titulo: str
    quarter_perguntado: str
    status: str
    resposta: str
    #: De qual trimestre sai a célula de métricas (igual ao perguntado, ou o fallback).
    quarter_da_celula: str
    #: O regime/`VIZINHOS_*` que indexa a célula em `regime_asset_metrics`.
    regime_da_celula: str
    como_chega: str
    ressalva: str

    @property
    def e_fallback(self) -> bool:
        """A resposta veio de outro trimestre que não o perguntado?"""
        return self.quarter_da_celula != self.quarter_perguntado


@dataclass(frozen=True, slots=True)
class Lente:
    """Uma das três colunas do bloco B: de onde o ranking sai e como ele se chama."""

    rotulo: str
    resposta: RespostaDeRegime
    lente: str
    materializacao: str
    horizonte: str
    tabela: Tabela


@dataclass(frozen=True, slots=True)
class ResultadoTabela:
    """O que uma rodada produziu — o Markdown é a leitura, os DataFrames são a evidência."""

    ranking: pd.DataFrame
    concordancia: pd.DataFrame
    markdown_ranking: str
    markdown_concordancia: str
    respostas: tuple[RespostaDeRegime, ...]
    vizinhos: pd.DataFrame
    caminhos: dict[str, Path]
    relatorio: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Hash, caminhos e leitura
# ─────────────────────────────────────────────────────────────────────────────


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do conjunto `MODULOS_DA_TABELA` — o `versao_build` do rodapé (RF-047/CA-121)."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DA_TABELA))


def sha256_do_arquivo(alvo: Path) -> str:
    """`sha256` do arquivo lido, byte a byte — o "hash dos insumos" do rodapé."""
    return hashlib.sha256(Path(alvo).read_bytes()).hexdigest()


def caminho_tabelas(*, raiz: Path | None = None) -> Path:
    """`data/canonical/tabelas/` — a pasta de saída desta camada."""
    return caminho_canonical(SUBPASTA_TABELAS, raiz=raiz)


def ler_metricas(tabela: Tabela, *, raiz: Path | None = None) -> pd.DataFrame:
    """Lê e **valida** uma das tabelas de F-022 com `RegimeAssetMetricsSchema`. Ausente = falha."""
    alvo = caminho_canonical(tabela.nome_arquivo, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            "`uv run python -m apps.pipeline.canonical.metricas_regime` (F-022)."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        validado = RegimeAssetMetricsSchema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz regime_asset_metrics: {erro}"
        raise SerieInconsistente(msg) from erro
    return pd.DataFrame(validado).reset_index(drop=True)


def hashes_dos_insumos(*, raiz: Path | None = None) -> dict[str, str]:
    """`sha256` de cada Parquet lido — é o que distingue "o código mudou" de "o dado mudou"."""
    nomes = (
        TABELA_PRINCIPAL.nome_arquivo,
        TABELA_ASOF.nome_arquivo,
        NOME_REGIMES_V1,
        NOME_REGIMES_V1_ASOF,
        NOME_NEIGHBORS_V3,
    )
    saida: dict[str, str] = {}
    for nome in nomes:
        alvo = caminho_canonical(nome, raiz=raiz)
        if not alvo.is_file():
            msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe."
            raise FonteIndisponivel(msg)
        saida[nome] = sha256_do_arquivo(alvo)
    return dict(sorted(saida.items()))


# ─────────────────────────────────────────────────────────────────────────────
# Formatação pt-BR — fixa, para que o Markdown seja determinístico
# ─────────────────────────────────────────────────────────────────────────────

AUSENTE = "—"


def _virgula(texto: str) -> str:
    """Separador decimal pt-BR. É só isto: nenhum `locale`, que depende do ambiente."""
    return texto.replace(".", ",")


def pct(valor: float | None, *, casas: int = 2, sinal: bool = True) -> str:
    """Fração → percentual pt-BR com sinal explícito (`+3,60%`). `None` → `—`."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return AUSENTE
    formato = f"{{:{'+' if sinal else ''}.{casas}f}}"
    return _virgula(formato.format(float(valor) * 100.0)) + "%"


def pp(valor: float | None, *, casas: int = 2) -> str:
    """Fração → pontos percentuais pt-BR, sem sinal (usado em erro-padrão). `None` → `—`."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return AUSENTE
    return _virgula(f"{float(valor) * 100.0:.{casas}f}")


def num(valor: float | None, *, casas: int = 3) -> str:
    """Número adimensional pt-BR (distância, Jaccard, Spearman). `None` → `—`."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return AUSENTE
    return _virgula(f"{float(valor):.{casas}f}")


# ─────────────────────────────────────────────────────────────────────────────
# Bloco A — "em que regime estamos?", três vezes
# ─────────────────────────────────────────────────────────────────────────────


def _linha_do_quarter(regimes: pd.DataFrame, quarter: str) -> pd.Series:
    """A linha de `regimes_v1` daquele trimestre. Ausente = a janela não é a esperada."""
    fatia = regimes.loc[regimes["quarter"] == quarter]
    if fatia.empty:
        msg = f"{quarter} não está em regimes_v1 ({len(regimes)} trimestres): a janela mudou?"
        raise SerieInconsistente(msg)
    return fatia.iloc[0]


def ultimo_quarter_com_quadrante(regimes: pd.DataFrame, *, antes_de: str) -> str:
    """O último trimestre **com** quadrante antes do perguntado — o fallback do bloco A.

    Não é um filtro de conveniência: é a única alternativa honesta a estimar um quadrante que o
    dado não tem (Anti-SPEC §10.1.1). Quem usar tem de carregar a palavra "fallback" junto, e é
    por isso que `e_fallback` é **coluna** do Parquet, não nota de rodapé.
    """
    candidatos = regimes.loc[
        (regimes["quarter"] < antes_de) & regimes["regime_v1"].notna(), "quarter"
    ]
    if candidatos.empty:
        msg = f"nenhum trimestre com quadrante V1 antes de {antes_de}: F-019 não rodou?"
        raise FonteIndisponivel(msg)
    return str(sorted(str(q) for q in candidatos)[-1])


def resposta_v1(
    regimes: pd.DataFrame,
    *,
    materializacao: Materializacao,
    quarter: str = QUARTER_DO_COMITE,
    ressalva: str = "",
) -> RespostaDeRegime:
    """A resposta de **uma** materialização da V1, com o fallback declarado quando não há quadrante.

    O status sai de `status_regime_v1`, não de `regime_v1.notna()`: é o `status` que é
    `nullable=False` no contrato, e ler o nulo seria inferir a afirmação em vez de lê-la.
    """
    chave = Materializacao(materializacao).value
    titulo = f"V1 `{chave}`"
    linha = _linha_do_quarter(regimes, quarter)
    classificado = str(linha["status_regime_v1"]) == StatusRegimeV1.CLASSIFICADO.value

    if classificado:
        regime = str(linha["regime_v1"])
        return RespostaDeRegime(
            titulo=titulo,
            quarter_perguntado=quarter,
            status=StatusDaResposta.CLASSIFICADO.value,
            resposta=regime,
            quarter_da_celula=quarter,
            regime_da_celula=regime,
            como_chega=(
                f"quadrante crescimento × inflação de `{quarter}` sobre a materialização "
                f"`{chave}`: `g_score = {pp(_pp_para_fracao(linha['g_score']))} pp`, "
                f"`pi_score = {pp(_pp_para_fracao(linha['pi_score']))} pp` "
                f"(n do grupo = {int(linha['n_obs_regime_v1'])})"
            ),
            ressalva=ressalva,
        )

    motivo = (
        AUSENTE if pd.isna(linha["motivo_indeterminado"]) else str(linha["motivo_indeterminado"])
    )
    fallback = ultimo_quarter_com_quadrante(regimes, antes_de=quarter)
    regime_fallback = str(_linha_do_quarter(regimes, fallback)["regime_v1"])
    explicacao = _explicacao_do_motivo(motivo)
    return RespostaDeRegime(
        titulo=titulo,
        quarter_perguntado=quarter,
        status=StatusDaResposta.INDETERMINADO_COM_FALLBACK.value,
        resposta=StatusRegimeV1.INDETERMINADO.value,
        quarter_da_celula=fallback,
        regime_da_celula=regime_fallback,
        como_chega=(
            f"**não tem quadrante para `{quarter}`** (`motivo = {motivo}`): {explicacao} "
            f"Nenhum quadrante foi estimado no lugar (Anti-SPEC §10.1.1)."
        ),
        ressalva=(
            f"o ranking do bloco B sai do **fallback declarado `{fallback}` "
            f"({regime_fallback})** — o último trimestre **com** quadrante, nunca apresentado "
            f'como "o regime de `{quarter}`". ' + ressalva
        ).strip(),
    )


def _pp_para_fracao(valor: Any) -> float | None:
    """`g_score`/`pi_score` estão em **pp** (D-o); `pp()` espera fração. Converte só para exibir."""
    return None if pd.isna(valor) else float(valor) / 100.0


def _explicacao_do_motivo(motivo: str) -> str:
    """Por que o trimestre ficou sem quadrante, em uma frase — o `motivo` traduzido."""
    traducao = {
        MotivoIndeterminado.GAP_AUSENTE.value: (
            "`ibcbr_gap` exige média móvel de 20 trimestres e o IBC-Br dessazonalizado do "
            "trimestre corrente não fechou (**D-m**) — por construção, o último trimestre da "
            "janela nunca terá hiato."
        ),
        MotivoIndeterminado.ACELERACAO_AUSENTE.value: (
            "`ipca_12m_delta` não está disponível para o trimestre (**D-m**)."
        ),
        MotivoIndeterminado.AMBOS_AUSENTES.value: (
            "nem `ibcbr_gap` nem `ipca_12m_delta` existem para o trimestre (**D-m**)."
        ),
    }
    return traducao.get(motivo, "o eixo exigido não existe para o trimestre (**D-m**).")


def ressalva_ca074(regimes_revised: pd.DataFrame, regimes_asof: pd.DataFrame) -> str:
    """A ressalva de **CA-074**, com o percentual medido — nunca um número escrito à mão."""
    divergencia = divergencia_entre_materializacoes(regimes_revised, regimes_asof)
    pcto = divergencia["pct_que_trocam"]
    operacional = divergencia["modelo_operacional"]
    texto = (
        f"⚠️ **CA-074 acionado:** a V1 troca de rótulo entre `revised` e `asof` em "
        f"**{pct(pcto, sinal=False)}** dos {divergencia['trimestres_comparaveis']} trimestres "
        f"comparáveis ({divergencia['trimestres_que_trocam']} trocas), acima do limiar de "
        f"{pct(divergencia['limiar_inoperante'], casas=0, sinal=False)}: pelo critério escrito a "
        f"V1 **não é operacional na forma `asof`**."
    )
    if operacional:
        texto = (
            f"troca de rótulo `revised` × `asof` em {pct(pcto, sinal=False)} dos "
            f"{divergencia['trimestres_comparaveis']} comparáveis, **dentro** do limiar de "
            f"{pct(divergencia['limiar_inoperante'], casas=0, sinal=False)} (CA-073)."
        )
    return texto


def vizinhos_do_quarter(
    neighbors: pd.DataFrame,
    *,
    quarter: str = QUARTER_DO_COMITE,
    k: int = K_VIZINHOS_PADRAO,
) -> pd.DataFrame:
    """Os `k` vizinhos da lente **principal** de F-021, com distância, `T+1` e rótulo V1.

    Lê `regime_neighbors_v3.parquet` (**D-u**) e **não** recalcula distância nenhuma: a lente é
    `mahalanobis` + `k = 8` + `somente_passado=False` + `restrito_pos_2016=False`, as outras 23
    combinações do Parquet são sensibilidade e não entram nesta página.
    """
    fatia = neighbors.loc[
        (neighbors["quarter_ref"] == quarter)
        & (neighbors["metrica"] == MetricaDistancia.MAHALANOBIS.value)
        & (neighbors["k_usado"] == k)
        & (~neighbors["somente_passado"].astype(bool))
        & (~neighbors["restrito_pos_2016"].astype(bool))
    ].sort_values("rank", kind="stable")
    if fatia.empty:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {NOME_NEIGHBORS_V3} não tem a lente canônica de "
            f"{quarter} (mahalanobis, k={k}). Rode F-021."
        )
        raise FonteIndisponivel(msg)
    colunas = [
        "rank",
        "quarter_neighbor",
        "distancia",
        "quarter_t_mais_1",
        "regime_v1_neighbor",
        "status_regime_v1_neighbor",
    ]
    return fatia[colunas].reset_index(drop=True)


def resposta_v3(vizinhos: pd.DataFrame, *, quarter: str = QUARTER_DO_COMITE) -> RespostaDeRegime:
    """A resposta da V3: não é um rótulo, é um **conjunto** de momentos parecidos."""
    nomes = " · ".join(str(q) for q in vizinhos["quarter_neighbor"])
    return RespostaDeRegime(
        titulo="V3 (vizinhos)",
        quarter_perguntado=quarter,
        status=StatusDaResposta.VIZINHOS.value,
        resposta=nome_do_regime_v3(quarter),
        quarter_da_celula=quarter,
        regime_da_celula=nome_do_regime_v3(quarter),
        como_chega=(
            f"os **{len(vizinhos)}** trimestres mais próximos de `{quarter}` em 5 features "
            "padronizadas (Mahalanobis com shrinkage de Ledoit-Wolf, `k = "
            f"{K_VIZINHOS_PADRAO}`): {nomes}. O retorno é medido no trimestre **seguinte** a cada "
            "vizinho (`T+1`, CA-102), nunca no próprio vizinho."
        ),
        ressalva=(
            f"`n = {len(vizinhos)}` por ativo no melhor caso — é a lente com a **menor** amostra "
            "da página, e nenhuma ordem de ativos dela sobrevive a 2 erros-padrão (F-021)."
        ),
    )


def respostas_do_regime_atual(
    *,
    regimes_revised: pd.DataFrame,
    regimes_asof: pd.DataFrame,
    vizinhos: pd.DataFrame,
    quarter: str = QUARTER_DO_COMITE,
) -> tuple[RespostaDeRegime, ...]:
    """As **três** respostas de CA-098, na ordem em que vão à página. Nunca uma só.

    A ordem é `revised` → `asof` → V3 e é fixa: é a ordem de *menos* para *mais* pressuposto
    sobre o trimestre corrente (a `revised` declara que não sabe; a `asof` arrisca um rótulo que
    CA-074 reprovou; a V3 troca o rótulo por um conjunto de precedentes). Qual **abre** a página é
    D1, do Edu.
    """
    return (
        resposta_v1(regimes_revised, materializacao=Materializacao.REVISED, quarter=quarter),
        resposta_v1(
            regimes_asof,
            materializacao=Materializacao.ASOF,
            quarter=quarter,
            ressalva=ressalva_ca074(regimes_revised, regimes_asof),
        ),
        resposta_v3(vizinhos, quarter=quarter),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bloco B — o ranking por lente
# ─────────────────────────────────────────────────────────────────────────────


def simbolo_de_n(n: int) -> str:
    """`‡` com `n < 5`, `†` com `n < 8`, vazio a partir de 8. Os limiares vêm de F-019."""
    if conclusao_suprimida(n):
        return SIMBOLO_N_SUPRIMIDO
    if alerta_n_baixo(n):
        return SIMBOLO_N_ALERTA
    return SIMBOLO_N_OK


def em_erros_padrao(excesso: float | None, erro_padrao: float | None) -> float | None:
    """`|excesso| / erro-padrão da média`. `None` quando não há dispersão estimável.

    ⚠️ **O numerador e o denominador não são medidos sobre a mesma série, e isso é declarado na
    página.** `excesso_cdi` é a média de `ret_excesso_cdi`; `erro_padrao_media` é, no contrato de
    F-022, `desvio(ret_tri)/√n` — o erro-padrão do retorno **nominal**. Para os ativos de bolsa as
    duas dispersões são praticamente a mesma (o CDI varia pouco dentro do trimestre), mas para o
    `CDI` e para os índices que o seguem (`IMAS`, `IRFM1`) a dispersão do **excesso** é muito
    menor, e nesses casos esta razão **subestima** a distância do zero. É por isso que ela é um
    **semáforo de confiança** e não uma estatística de teste: serve para dizer "não insista nesta
    ordem", nunca para dizer "este é significativo".

    Não há como fazer melhor sem acrescentar uma coluna (`erro_padrao_excesso`) a
    `RegimeAssetMetricsSchema`, que é **alteração** de schema existente e, portanto, classe C
    própria (`AGENTS.md §9`) — fica registrado como dívida no pack desta feature.
    """
    if excesso is None or erro_padrao is None or erro_padrao == 0.0:
        return None
    return abs(float(excesso)) / float(erro_padrao)


def lentes_da_pagina(
    respostas: Sequence[RespostaDeRegime],
) -> tuple[Lente, ...]:
    """As três lentes do bloco B, derivadas das três respostas do bloco A.

    Os rótulos são **os mesmos** de `relatorio_metricas.json → concordancia_entre_lentes`
    (`V1_revised_ESTAGFLACAO_2026Q2`, `V1_asof_DESACELERACAO_2026Q3`,
    `V3_vizinhos_2026Q3_T_mais_1`), para que qualquer número desta página seja rastreável até o
    relatório de F-022 sem tradução.
    """
    revised, asof, v3 = respostas
    return (
        Lente(
            rotulo=f"V1_revised_{revised.regime_da_celula}_{revised.quarter_da_celula}",
            resposta=revised,
            lente=LENTE_V1,
            materializacao=Materializacao.REVISED.value,
            horizonte=TABELA_PRINCIPAL.horizonte_v1.value,
            tabela=TABELA_PRINCIPAL,
        ),
        Lente(
            rotulo=f"V1_asof_{asof.regime_da_celula}_{asof.quarter_da_celula}",
            resposta=asof,
            lente=LENTE_V1,
            materializacao=Materializacao.ASOF.value,
            horizonte=TABELA_ASOF.horizonte_v1.value,
            tabela=TABELA_ASOF,
        ),
        Lente(
            rotulo=f"V3_vizinhos_{v3.quarter_perguntado}_T_mais_1",
            resposta=v3,
            lente=LENTE_V3,
            materializacao=Materializacao.REVISED.value,
            horizonte=Horizonte.T_MAIS_1.value,
            tabela=TABELA_PRINCIPAL,
        ),
    )


def linhas_do_ranking(metricas: pd.DataFrame, lente: Lente, *, versao: str) -> list[dict[str, Any]]:
    """As 24 linhas de uma lente, já ordenadas — a ordenação é de F-022, não daqui.

    `ranking_do_regime` ordena por `excesso_cdi` decrescente e manda célula **sem observação**
    para o fim (`None` não é "o melhor"). Aqui só se acrescenta o que é de apresentação: a
    posição, o símbolo de `n` e a razão `|excesso| / erro-padrão`.
    """
    bruto = ranking_do_regime(metricas, lente=lente.lente, regime=lente.resposta.regime_da_celula)
    if not bruto:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {lente.tabela.nome_arquivo} não tem a célula "
            f"(lente={lente.lente}, regime={lente.resposta.regime_da_celula}). Rode F-022."
        )
        raise FonteIndisponivel(msg)
    if len(bruto) != N_ATIVOS_ESPERADO:
        msg = (
            f"{lente.rotulo}: {len(bruto)} ativos, esperados {N_ATIVOS_ESPERADO}. Linha de ativo "
            "faltando é falha, não omissão (CA-095)."
        )
        raise SerieInconsistente(msg)

    linhas: list[dict[str, Any]] = []
    for posicao, celula in enumerate(bruto, start=1):
        razao = em_erros_padrao(celula["excesso_cdi"], celula["erro_padrao_media"])
        n_obs = int(celula["n_obs"])
        linhas.append(
            {
                "lente_rotulo": lente.rotulo,
                "lente_titulo": lente.resposta.titulo,
                "lente": lente.lente,
                "regime": lente.resposta.regime_da_celula,
                "asset_id": celula["asset_id"],
                "materializacao": lente.materializacao,
                "horizonte": lente.horizonte,
                "quarter_perguntado": lente.resposta.quarter_perguntado,
                "quarter_da_celula": lente.resposta.quarter_da_celula,
                "e_fallback": lente.resposta.e_fallback,
                "tabela_de_origem": lente.tabela.nome_arquivo,
                "posicao": posicao,
                "n_obs": n_obs,
                "excesso_cdi": celula["excesso_cdi"],
                "ret_medio": celula["ret_medio"],
                "ret_mediana": celula["ret_mediana"],
                "hit_ratio_cdi": celula["hit_ratio_cdi"],
                "erro_padrao_media": celula["erro_padrao_media"],
                "alerta_n_baixo": bool(celula["alerta_n_baixo"]),
                "conclusao_suprimida": bool(celula["conclusao_suprimida"]),
                "fonte_versao": _fonte_versao_da_celula(metricas, lente, celula["asset_id"]),
                "excesso_em_erros_padrao": razao,
                "distinguivel_de_ruido": bool(razao is not None and razao >= LIMIAR_ERROS_PADRAO),
                "simbolo_n": simbolo_de_n(n_obs),
                "versao_build": versao,
            }
        )
    return linhas


def _fonte_versao_da_celula(metricas: pd.DataFrame, lente: Lente, asset_id: str) -> str:
    """O `fonte_versao` da célula de origem — o hash do código de F-022 que produziu o número."""
    fatia = metricas.loc[
        (metricas["lente"] == lente.lente)
        & (metricas["regime"] == lente.resposta.regime_da_celula)
        & (metricas["asset_id"] == asset_id),
        "fonte_versao",
    ]
    return str(fatia.iloc[0])


def tabela_de_ranking(
    *,
    metricas: Mapping[str, pd.DataFrame],
    lentes: Sequence[Lente],
    versao: str,
) -> pd.DataFrame:
    """As 72 linhas (3 lentes × 24 ativos) do bloco B, no contrato `COLUNAS_RANKING`."""
    linhas: list[dict[str, Any]] = []
    for lente in lentes:
        linhas.extend(linhas_do_ranking(metricas[lente.tabela.rotulo], lente, versao=versao))
    quadro = pd.DataFrame(linhas, columns=list(COLUNAS_RANKING))
    faltando = [c for c in COLUNAS_RANKING if c not in quadro]
    if faltando:
        msg = f"contrato de ranking violado: falta {faltando}"
        raise SerieInconsistente(msg)
    return quadro


# ─────────────────────────────────────────────────────────────────────────────
# Bloco C — concordância: Jaccard, Spearman e a distribuição da variante sem look-ahead
# ─────────────────────────────────────────────────────────────────────────────


def postos(valores: Sequence[float]) -> np.ndarray:
    """Postos de 1 a `n` com **média nos empates** — o `rankdata(method="average")` à mão.

    Empate tratado por média é o que a correlação de Spearman pressupõe; tratá-lo por ordem de
    chegada tornaria o resultado dependente da ordem das linhas, que aqui é a ordem do ranking.
    """
    vetor = np.asarray(valores, dtype="float64")
    if vetor.size == 0:
        return vetor
    ordem = np.argsort(vetor, kind="stable")
    cru = np.empty(vetor.size, dtype="float64")
    cru[ordem] = np.arange(1, vetor.size + 1, dtype="float64")
    for valor in np.unique(vetor):
        empatados = vetor == valor
        if int(empatados.sum()) > 1:
            cru[empatados] = float(cru[empatados].mean())
    return cru


def spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Correlação de posto de Spearman, **em numpy** (`scipy` exigiria ADR — §10.4.25).

    É Pearson sobre os postos, que é a definição geral (a fórmula fechada
    `1 − 6Σd²/[n(n²−1)]` só vale sem empate). `None` quando há menos de 2 pares ou quando um dos
    lados é constante — correlação com variância zero não é 0, é indefinida.
    """
    x = np.asarray(a, dtype="float64")
    y = np.asarray(b, dtype="float64")
    if x.size != y.size:
        msg = f"spearman exige vetores do mesmo tamanho: {x.size} != {y.size}"
        raise SerieInconsistente(msg)
    if x.size < 2:
        return None
    px, py = postos(x), postos(y)
    if float(px.std()) == 0.0 or float(py.std()) == 0.0:
        return None
    return float(np.corrcoef(px, py)[0, 1])


def spearman_entre_lentes(ranking: pd.DataFrame, rotulo_a: str, rotulo_b: str) -> dict[str, Any]:
    """Spearman de `excesso_cdi` entre duas lentes, sobre os ativos que as **duas** medem."""
    a = ranking.loc[ranking["lente_rotulo"] == rotulo_a].set_index("asset_id")
    b = ranking.loc[ranking["lente_rotulo"] == rotulo_b].set_index("asset_id")
    comuns = sorted(set(a.index[a["excesso_cdi"].notna()]) & set(b.index[b["excesso_cdi"].notna()]))
    return {
        "n_ativos": len(comuns),
        "rho": spearman(
            [float(a.loc[ativo, "excesso_cdi"]) for ativo in comuns],
            [float(b.loc[ativo, "excesso_cdi"]) for ativo in comuns],
        ),
    }


def jaccard_das_variantes_v3(
    neighbors: pd.DataFrame, *, k: int = K_VIZINHOS_PADRAO
) -> dict[str, Any]:
    """A distribuição do Jaccard **`somente_passado` × descritiva** nas referências da V3.

    **Por que está nesta página (QA da Onda 3, P1-2):** `TODO.md §F-021` chamava de "o achado mais
    forte da feature" o fato de as duas variantes darem a **mesma** lista de 8 vizinhos para
    `2026Q3` (Jaccard 1,0). O número é verdadeiro e **vácuo**: `2026Q3` é o último trimestre da
    janela, então não existe futuro para a variante descritiva escolher e as duas coincidem **por
    construção**. Medido em todas as referências que têm as duas variantes, o Jaccard tem mediana
    ~0,45 — a lente descritiva troca **mais da metade** do conjunto de vizinhos no caso típico.

    A conta compara **conjuntos de vizinhos**, não distâncias: nada é recalculado aqui.
    """
    base = neighbors.loc[
        (neighbors["metrica"] == MetricaDistancia.MAHALANOBIS.value)
        & (neighbors["k_usado"] == k)
        & (~neighbors["restrito_pos_2016"].astype(bool))
    ]
    descritiva = base.loc[~base["somente_passado"].astype(bool)]
    somente_passado = base.loc[base["somente_passado"].astype(bool)]
    referencias = sorted(
        set(descritiva["quarter_ref"].astype(str)) & set(somente_passado["quarter_ref"].astype(str))
    )
    if not referencias:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {NOME_NEIGHBORS_V3} não tem as duas variantes "
            f"(somente_passado True/False) para k={k}. Rode F-021."
        )
        raise FonteIndisponivel(msg)

    por_referencia: list[dict[str, Any]] = []
    for quarter_ref in referencias:
        a = set(
            descritiva.loc[
                descritiva["quarter_ref"].astype(str) == quarter_ref, "quarter_neighbor"
            ].astype(str)
        )
        b = set(
            somente_passado.loc[
                somente_passado["quarter_ref"].astype(str) == quarter_ref, "quarter_neighbor"
            ].astype(str)
        )
        uniao = a | b
        por_referencia.append(
            {
                "quarter_ref": quarter_ref,
                "n_em_comum": len(a & b),
                "jaccard": (len(a & b) / len(uniao)) if uniao else None,
            }
        )

    valores = pd.Series(
        [linha["jaccard"] for linha in por_referencia if linha["jaccard"] is not None],
        dtype="float64",
    )
    do_comite = next(
        (linha for linha in por_referencia if linha["quarter_ref"] == QUARTER_DO_COMITE), None
    )
    return {
        "k": k,
        "referencias_descritiva": int(descritiva["quarter_ref"].nunique()),
        "referencias_somente_passado": int(somente_passado["quarter_ref"].nunique()),
        "referencias_comparadas": int(len(valores)),
        "distribuicao": {
            "min": float(valores.min()),
            "q1": float(valores.quantile(0.25)),
            "mediana": float(valores.median()),
            "media": float(valores.mean()),
            "q3": float(valores.quantile(0.75)),
            "max": float(valores.max()),
            "n_iguais_a_1": int((valores == 1.0).sum()),
            "n_zeros": int((valores == 0.0).sum()),
        },
        "do_quarter_do_comite": do_comite,
        "por_referencia": por_referencia,
        "leitura": (
            "O Jaccard 1,0 de "
            f"{QUARTER_DO_COMITE} e vacuo: e o ultimo trimestre da janela, logo as duas variantes "
            "coincidem por construcao. A distribuicao sobre todas as referencias e o numero "
            "honesto (QA da Onda 3, P1-2)."
        ),
    }


def _registros_da_lente(ranking: pd.DataFrame, rotulo: str) -> list[dict[str, Any]]:
    """As linhas de uma lente como `list[dict]`, com `NaN` devolvido a `None`.

    `top_n_de` (F-022) ignora célula sem observação testando `is None`, e `NaN` **não** é `None`:
    a ida e volta pelo DataFrame transformaria "célula vazia" em "célula no topo do ranking".
    """
    registros = ranking.loc[ranking["lente_rotulo"] == rotulo].to_dict("records")
    return [
        {
            **linha,
            "excesso_cdi": (None if pd.isna(linha["excesso_cdi"]) else float(linha["excesso_cdi"])),
        }
        for linha in registros
    ]


def concordancia(
    *,
    ranking: pd.DataFrame,
    lentes: Sequence[Lente],
    neighbors: pd.DataFrame,
    tops: Sequence[int] = TOPS_DA_CONCORDANCIA,
) -> dict[str, Any]:
    """O bloco C inteiro: por lente, par a par e a distribuição das variantes da V3.

    O Jaccard e os top-`n` por lente vêm de `concordancia_entre_lentes` (F-022) — a mesma função
    que gerou `relatorio_metricas.json`, chamada uma vez por `n`. O que esta camada acrescenta é
    **Spearman** sobre os 24 ativos (que mede a ordem inteira, não só o topo) e a distribuição de
    P1-2.
    """
    rankings = {lente.rotulo: _registros_da_lente(ranking, lente.rotulo) for lente in lentes}
    por_top = {n: concordancia_entre_lentes(rankings, n=n) for n in tops}
    pares: dict[str, Any] = {}
    # As chaves dos pares (e a ordem dentro de cada par) são **as de F-022**, não as daqui: é o
    # que faz cada número desta página ser achável em `relatorio_metricas.json` sem tradução.
    for chave in por_top[tops[0]]["pares"]:
        a, b = chave.split(SEPARADOR_DE_PAR)
        bloco: dict[str, Any] = {"lente_a": a, "lente_b": b}
        for n in tops:
            do_par = por_top[n]["pares"][chave]
            bloco[f"jaccard_top{n}"] = do_par["jaccard"]
            bloco[f"em_comum_top{n}"] = do_par["em_comum"]
        bloco["spearman"] = spearman_entre_lentes(ranking, a, b)
        pares[chave] = bloco
    return {
        "tops": list(tops),
        "por_lente": {
            lente.rotulo: {
                "titulo": lente.resposta.titulo,
                "regime": lente.resposta.regime_da_celula,
                "quarter_da_celula": lente.resposta.quarter_da_celula,
                **{f"top_{n}": por_top[n]["top_por_lente"][lente.rotulo] for n in tops},
                "n_obs_da_celula": sorted(
                    {int(v) for v in ranking.loc[ranking["lente_rotulo"] == lente.rotulo, "n_obs"]}
                ),
                "erro_padrao_min": float(
                    ranking.loc[ranking["lente_rotulo"] == lente.rotulo, "erro_padrao_media"].min()
                ),
                "erro_padrao_max": float(
                    ranking.loc[ranking["lente_rotulo"] == lente.rotulo, "erro_padrao_media"].max()
                ),
                "ativos_acima_de_2_ep": int(
                    ranking.loc[
                        ranking["lente_rotulo"] == lente.rotulo, "distinguivel_de_ruido"
                    ].sum()
                ),
            }
            for lente in lentes
        },
        "pares": pares,
        "em_todas_as_lentes": {n: por_top[n]["em_todas_as_lentes"] for n in tops},
        "variantes_v3": jaccard_das_variantes_v3(neighbors),
        "leitura": (
            "Divergencia entre lentes e RESULTADO, nao erro (CA-103). Nenhuma lente foi escolhida "
            "e nenhuma foi omitida."
        ),
    }


def tabela_de_concordancia(bloco: Mapping[str, Any], *, versao: str) -> pd.DataFrame:
    """O bloco C em forma **tidy** — `secao | chave | metrica | valor_num | valor_texto`."""
    linhas: list[dict[str, Any]] = []

    def _acrescentar(
        secao: str, chave: str, metrica: str, *, num_: float | None = None, texto: str = ""
    ) -> None:
        linhas.append(
            {
                "secao": secao,
                "chave": chave,
                "metrica": metrica,
                "valor_num": num_,
                "valor_texto": texto,
                "versao_build": versao,
            }
        )

    for rotulo, dados in bloco["por_lente"].items():
        for n in bloco["tops"]:
            _acrescentar(
                SecaoDaConcordancia.POR_LENTE.value,
                rotulo,
                f"top_{n}",
                texto=" | ".join(dados[f"top_{n}"]),
            )
        _acrescentar(
            SecaoDaConcordancia.POR_LENTE.value,
            rotulo,
            "n_obs_da_celula",
            texto=" | ".join(str(v) for v in dados["n_obs_da_celula"]),
        )
        _acrescentar(
            SecaoDaConcordancia.POR_LENTE.value,
            rotulo,
            "ativos_acima_de_2_ep",
            num_=float(dados["ativos_acima_de_2_ep"]),
        )

    for chave, dados in bloco["pares"].items():
        for n in bloco["tops"]:
            _acrescentar(
                SecaoDaConcordancia.PAR_DE_LENTES.value,
                chave,
                f"jaccard_top{n}",
                num_=dados[f"jaccard_top{n}"],
                texto=" | ".join(dados[f"em_comum_top{n}"]),
            )
        _acrescentar(
            SecaoDaConcordancia.PAR_DE_LENTES.value,
            chave,
            "spearman_excesso_cdi",
            num_=dados["spearman"]["rho"],
            texto=f"n_ativos={dados['spearman']['n_ativos']}",
        )

    variantes = bloco["variantes_v3"]
    for metrica, valor in variantes["distribuicao"].items():
        _acrescentar(
            SecaoDaConcordancia.DISTRIBUICAO_SOMENTE_PASSADO.value,
            "somente_passado__x__descritiva",
            metrica,
            num_=float(valor),
        )
    _acrescentar(
        SecaoDaConcordancia.DISTRIBUICAO_SOMENTE_PASSADO.value,
        "somente_passado__x__descritiva",
        "referencias_comparadas",
        num_=float(variantes["referencias_comparadas"]),
    )
    do_comite = variantes["do_quarter_do_comite"]
    _acrescentar(
        SecaoDaConcordancia.DISTRIBUICAO_SOMENTE_PASSADO.value,
        "somente_passado__x__descritiva",
        f"jaccard_em_{QUARTER_DO_COMITE}",
        num_=None if do_comite is None else do_comite["jaccard"],
        texto="vacuo: ultimo trimestre da janela, coincidem por construcao (QA P1-2)",
    )
    return pd.DataFrame(linhas, columns=list(COLUNAS_CONCORDANCIA))


# ─────────────────────────────────────────────────────────────────────────────
# Markdown — a página. Derivada dos DataFrames, nunca escrita à mão
# ─────────────────────────────────────────────────────────────────────────────


def _sem_negacao_no_contexto(minusculo: str, termo: str) -> bool:
    """Alguma ocorrência de `termo` aparece **sem** negação nos `JANELA_DE_NEGACAO` chars antes?"""
    posicao = minusculo.find(termo)
    while posicao != -1:
        contexto = minusculo[max(0, posicao - JANELA_DE_NEGACAO) : posicao]
        if not any(marcador in contexto for marcador in MARCADORES_DE_NEGACAO):
            return True
        posicao = minusculo.find(termo, posicao + len(termo))
    return False


def conferir_linguagem_descritiva(texto: str) -> None:
    """Levanta se qualquer forma de previsão aparecer no Markdown (Anti-SPEC §10.2.10).

    Duas listas, porque o risco tem duas formas. **Forma assertiva** ("vai render", "esperamos")
    é proibida por inteiro. **Substantivo preditivo** ("previsão", "backtest", "recomendação") é
    permitido **só sob negação** — é exatamente o que o bloco D faz ("não é previsão de retorno,
    não é backtest"), e proibi-lo por inteiro tornaria o aviso impossível de escrever.

    É uma guarda **executável**, não um pedido na revisão: o risco real deste projeto é uma frase
    preditiva entrar num slide que já passou por três revisões de número.
    """
    minusculo = texto.lower()
    assertivas = [p for p in FORMAS_PREDITIVAS_PROIBIDAS if p in minusculo]
    soltos = [
        termo
        for termo in SUBSTANTIVOS_PREDITIVOS_SOB_NEGACAO
        if _sem_negacao_no_contexto(minusculo, termo)
    ]
    if assertivas or soltos:
        msg = (
            f"linguagem preditiva na tabela (Anti-SPEC §10.2.10): formas assertivas "
            f"{assertivas}; substantivos preditivos sem negação no contexto {soltos}. "
            "O entregável é descritivo: 'rendeu X, n = Y', nunca 'vai render'."
        )
        raise SerieInconsistente(msg)


def _tabela_md(cabecalho: Sequence[str], linhas: Sequence[Sequence[str]]) -> list[str]:
    """Uma tabela Markdown — sem alinhamento por espaço, para o diff ser legível."""
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join(["---"] * len(cabecalho)) + "|"]
    saida.extend("| " + " | ".join(celula for celula in linha) + " |" for linha in linhas)
    return saida


def _bloco_a(
    respostas: Sequence[RespostaDeRegime], vizinhos: pd.DataFrame, *, quarter: str
) -> list[str]:
    """Bloco A — as três respostas lado a lado + os 8 vizinhos + a regra de leitura."""
    linhas = [
        f"## A. Em que regime estamos ({quarter})? — **três** respostas, nenhuma escolhida por nós",
        "",
    ]
    linhas += _tabela_md(
        ("Lente", f"Resposta para `{quarter}`", "Como ela chega nisso", "Ressalva"),
        [
            (
                resposta.titulo,
                f"**{resposta.resposta}**",
                resposta.como_chega,
                resposta.ressalva or AUSENTE,
            )
            for resposta in respostas
        ],
    )
    linhas += [
        "",
        f"**Os {len(vizinhos)} vizinhos de `{quarter}`** (V3: Mahalanobis + Ledoit-Wolf, "
        f"`k = {K_VIZINHOS_PADRAO}`, amostra completa) — o retorno do bloco B é medido em `T+1`:",
        "",
    ]
    linhas += _tabela_md(
        ("rank", "vizinho", "distância", "`T+1` medido", "V1 do vizinho"),
        [
            (
                str(int(linha["rank"])),
                f"`{linha['quarter_neighbor']}`",
                num(float(linha["distancia"]), casas=4),
                f"`{linha['quarter_t_mais_1']}`",
                (
                    f"*{StatusRegimeV1.INDETERMINADO.value.lower()}* (**D-m**)"
                    if pd.isna(linha["regime_v1_neighbor"])
                    else f"`{linha['regime_v1_neighbor']}`"
                ),
            )
            for _, linha in vizinhos.iterrows()
        ],
    )
    return linhas


def _bloco_b(ranking: pd.DataFrame, lentes: Sequence[Lente]) -> list[str]:
    """Bloco B — um ranking de 24 ativos por lente, ordenado por `excesso_cdi` (CA-098)."""
    linhas = [
        "## B. Ranking de ativos por lente — **excesso sobre CDI médio trimestral**",
        "",
        f"Métrica primária: `excesso_cdi` = média de `{COLUNA_PRIMARIA}` = "
        "`(1+r)/(1+cdi) − 1`, trimestre a trimestre, "
        "**sempre por razão, nunca por subtração** (ADR-002/D5, Anti-SPEC §10.2.13).",
        "",
        "⚠️ **Leia as colunas pelo nome.** `excesso CDI` é o excesso; `ret médio` e "
        "`ret mediana` são do retorno **nominal** (`ret_tri`) — vão lado a lado porque "
        "divergência grande entre média e mediana é **um trimestre dominando** (CA-092), e é por "
        "isso que a linha `CDI` tem excesso `+0,00%` e mediana nominal positiva. O `ep` também é "
        "o do retorno **nominal** (`desvio(ret_tri)/√n`, o que F-022 publica), então "
        "`|excesso| / ep` é um **semáforo de confiança**, não uma estatística de teste: para o "
        "`CDI` e para os índices que o seguem ela subestima a distância do zero.",
        "",
    ]
    for indice, lente in enumerate(lentes, start=1):
        bloco = ranking.loc[ranking["lente_rotulo"] == lente.rotulo]
        ns = sorted({int(v) for v in bloco["n_obs"]})
        acima = int(bloco["distinguivel_de_ruido"].sum())
        fallback = (
            f" · **fallback declarado** (`{lente.resposta.quarter_perguntado}` é "
            f"`{StatusRegimeV1.INDETERMINADO.value}`)"
            if lente.resposta.e_fallback
            else ""
        )
        linhas += [
            f"### B.{indice} {lente.resposta.titulo} / `{lente.resposta.regime_da_celula}` "
            f"— `{lente.resposta.quarter_da_celula}`, horizonte `{lente.horizonte}`, "
            f"n = {', '.join(str(v) for v in ns)}{fallback}",
            "",
        ]
        linhas += _tabela_md(
            (
                "#",
                "ativo",
                "excesso CDI",
                "ret médio (nom.)",
                "ret mediana (nom.)",
                "hit vs CDI",
                "n",
                "ep (pp, nom.)",
                r"\|excesso\| / ep",
            ),
            [
                (
                    str(int(linha["posicao"])),
                    f"`{linha['asset_id']}`{linha['simbolo_n']}",
                    pct(linha["excesso_cdi"]),
                    pct(linha["ret_medio"]),
                    pct(linha["ret_mediana"]),
                    num(linha["hit_ratio_cdi"], casas=2),
                    str(int(linha["n_obs"])),
                    pp(linha["erro_padrao_media"]),
                    num(linha["excesso_em_erros_padrao"], casas=2)
                    + ("*" if bool(linha["distinguivel_de_ruido"]) else ""),
                )
                for _, linha in bloco.iterrows()
            ],
        )
        linhas += [
            "",
            f"Ativos desta lente com excesso acima de {LIMIAR_ERROS_PADRAO:.0f} "
            f"erros-padrão da média: **{acima} de {len(bloco)}** — "
            + (
                "a ordem do topo não se distingue de ruído."
                if acima == 0
                else "para os demais, a ordem não se distingue de ruído."
            ),
            "",
        ]
    linhas += [f"Legenda: {LEGENDA_SIMBOLOS}.", ""]
    return linhas


def _bloco_c(bloco: Mapping[str, Any]) -> list[str]:
    """Bloco C — a concordância, em 3 sub-tabelas (CA-103 + a distribuição de P1-2)."""
    tops = bloco["tops"]
    linhas = [
        "## C. Concordância entre lentes — a divergência **é** o resultado (CA-103)",
        "",
        "### C.1 Uma linha por lente",
        "",
    ]
    linhas += _tabela_md(
        (
            "Lente",
            "regime / trimestre",
            f"top-{tops[0]}",
            f"top-{tops[1]}",
            "n",
            f"acima de {LIMIAR_ERROS_PADRAO:.0f} ep",
        ),
        [
            (
                dados["titulo"],
                f"`{dados['regime']}` / `{dados['quarter_da_celula']}`",
                " · ".join(f"`{a}`" for a in dados[f"top_{tops[0]}"]),
                " · ".join(f"`{a}`" for a in dados[f"top_{tops[1]}"]),
                ", ".join(str(v) for v in dados["n_obs_da_celula"]),
                f"{dados['ativos_acima_de_2_ep']} de {N_ATIVOS_ESPERADO}",
            )
            for dados in bloco["por_lente"].values()
        ],
    )
    em_todas = bloco["em_todas_as_lentes"][tops[1]]
    comuns = (
        "**nenhum ativo — a interseção é vazia.**"
        if not em_todas
        else "**" + " · ".join(f"`{a}`" for a in em_todas) + "**."
    )
    linhas += [
        "",
        f"Em todas as três lentes, no top-{tops[1]}: {comuns}",
        "",
        "### C.2 Par a par — Jaccard do topo e Spearman da ordem inteira",
        "",
    ]
    linhas += _tabela_md(
        (
            "Par de lentes",
            f"Jaccard top-{tops[1]}",
            f"em comum (top-{tops[1]})",
            f"Jaccard top-{tops[2]}",
            "Spearman (24 ativos)",
        ),
        [
            (
                f"`{dados['lente_a']}`<br>× `{dados['lente_b']}`",
                num(dados[f"jaccard_top{tops[1]}"]),
                " · ".join(f"`{a}`" for a in dados[f"em_comum_top{tops[1]}"]) or AUSENTE,
                num(dados[f"jaccard_top{tops[2]}"]),
                num(dados["spearman"]["rho"]),
            )
            for dados in bloco["pares"].values()
        ],
    )
    variantes = bloco["variantes_v3"]
    distribuicao = variantes["distribuicao"]
    do_comite = variantes["do_quarter_do_comite"]
    jaccard_comite = None if do_comite is None else do_comite["jaccard"]
    linhas += [
        "",
        "Spearman é correlação de **posto** sobre `excesso_cdi` nos 24 ativos: mede se a ordem "
        "inteira concorda, não só o topo. Implementada em numpy (`scipy` exigiria ADR — "
        "Anti-SPEC §10.4.25).",
        "",
        "### C.3 A V3 sem look-ahead × a V3 descritiva — a **distribuição**, não só o último",
        "",
        f"A variante `somente_passado` (z-score, covariância e candidatos **só até `T`**) dá a "
        f"**mesma** lista de {K_VIZINHOS_PADRAO} vizinhos que a descritiva em "
        f"`{QUARTER_DO_COMITE}` — Jaccard **{num(jaccard_comite)}**. Esse número é **vácuo**: "
        f"`{QUARTER_DO_COMITE}` é o último trimestre da janela, então não existe futuro para a "
        "variante descritiva escolher e as duas coincidem **por construção** "
        "(**QA da Onda 3, P1-2**). O número honesto é a distribuição sobre as "
        f"**{variantes['referencias_comparadas']}** referências que têm as duas variantes:",
        "",
    ]
    linhas += _tabela_md(
        ("estatística", "Jaccard `somente_passado` × descritiva"),
        [
            ("mínimo", num(distribuicao["min"])),
            ("1º quartil", num(distribuicao["q1"])),
            ("**mediana**", f"**{num(distribuicao['mediana'])}**"),
            ("média", num(distribuicao["media"])),
            ("3º quartil", num(distribuicao["q3"])),
            ("máximo", num(distribuicao["max"])),
            (
                "referências com Jaccard 1,0",
                f"{distribuicao['n_iguais_a_1']} de {variantes['referencias_comparadas']}",
            ),
            (
                "referências com Jaccard 0",
                f"{distribuicao['n_zeros']} de {variantes['referencias_comparadas']}",
            ),
        ],
    )
    linhas += [
        "",
        f"**Leitura:** no caso típico a lente descritiva troca **mais da metade** do conjunto de "
        f"vizinhos em relação à variante sem look-ahead (mediana "
        f"{num(distribuicao['mediana'])}), e em "
        f"{distribuicao['n_iguais_a_1']} de {variantes['referencias_comparadas']} referências as "
        "duas coincidem por inteiro. Citar só o trimestre do Comitê **superestima** a robustez da "
        "V3 — é o mesmo erro que o QA pegou em F-021.",
        "",
    ]
    return linhas


def _bloco_d(ranking: pd.DataFrame) -> list[str]:
    """Bloco D — as 3 linhas de "o que isso NÃO diz".

    A faixa de `n` e de erro-padrão da primeira linha é **medida nesta rodada**, não escrita à
    mão: um aviso com número velho é pior que nenhum aviso.
    """
    linhas = ["## D. O que isso **não** diz", ""]
    contexto = {
        "n_min": int(ranking["n_obs"].min()),
        "n_max": int(ranking["n_obs"].max()),
        "ep_min": pp(float(ranking["erro_padrao_media"].min()), casas=1),
        "ep_max": pp(float(ranking["erro_padrao_media"].max()), casas=1),
        "limiar": f"{LIMIAR_ERROS_PADRAO:.0f}",
    }
    linhas += [
        f"{i}. {texto.format(**contexto)}" for i, texto in enumerate(O_QUE_ISSO_NAO_DIZ, start=1)
    ]
    linhas.append("")
    return linhas


def _rodape(
    *,
    versao: str,
    hashes: Mapping[str, str],
    congelada: bool,
    status_adr: str,
) -> list[str]:
    """Rodapé: `versao_build`, `sha256` de cada insumo e o gate de CA-090."""
    linhas = [
        "---",
        "",
        f"`versao_build` **`{versao}`** — `sha256` do conjunto "
        f"{{{', '.join('`' + m + '`' for m in MODULOS_DA_TABELA)}}}. Mudar qualquer um muda a "
        "página de propósito.",
        "",
        "Insumos lidos, com `sha256`:",
        "",
    ]
    linhas += _tabela_md(
        ("arquivo em `data/canonical/`", "`sha256`"),
        [(f"`{nome}`", f"`{digest}`") for nome, digest in sorted(hashes.items())],
    )
    linhas += [
        "",
        f"**Gate CA-090:** `ADR-001` está em **{status_adr}**, logo "
        f"`especificacao_congelada = {str(congelada).lower()}` e o veredito é "
        f"**{veredito_publicacao(congelada)}**"
        + ("." if congelada else f" — **{MARCA_NAO_CONGELADA}**."),
        "",
        "Decisões provisórias que esta página carrega: **D1** (qual lente abre), "
        "**D5/ADR-002** (`excesso_cdi` como métrica primária), **D-m** (`2026Q3` sem quadrante na "
        "V1 `revised`), **D-u** (a V3 lê `regime_neighbors_v3`). Métricas e ordenação são de "
        "`metricas_regime` (F-022); vizinhos e `T+1`, de `regimes_v3` (F-021); rótulos V1, de "
        "`regimes_v1` (F-019). Esta camada lê, compara e apresenta — não recalcula.",
    ]
    return linhas


def markdown_da_pagina(
    *,
    respostas: Sequence[RespostaDeRegime],
    vizinhos: pd.DataFrame,
    ranking: pd.DataFrame,
    lentes: Sequence[Lente],
    bloco_c: Mapping[str, Any],
    versao: str,
    hashes: Mapping[str, str],
    congelada: bool,
    status_adr: str,
    pct_de_troca: float | None,
    quarter: str = QUARTER_DO_COMITE,
) -> str:
    """A página de 1 arquivo: blocos A, B, C, D e rodapé. **É o que o Comitê lê.**"""
    linhas = [f"# {TITULO} — `{quarter}`", ""]
    if not congelada:
        linhas += [f"> ⛔ **{MARCA_NAO_CONGELADA}** (CA-090: `ADR-001` em {status_adr}).", ""]
    linhas += [f"> {SUBTITULO_DESCRITIVO}", ""]
    linhas += _bloco_a(respostas, vizinhos, quarter=quarter)
    linhas += [
        "",
        REGRA_DE_LEITURA.format(
            quarter=quarter,
            pct_troca=pct(pct_de_troca, sinal=False),
            limiar=pct(LIMIAR_TROCA_REGIME_INOPERANTE, casas=0, sinal=False),
        ),
        "",
    ]
    linhas += _bloco_b(ranking, lentes)
    linhas += _bloco_c(bloco_c)
    linhas += _bloco_d(ranking)
    linhas += _rodape(versao=versao, hashes=hashes, congelada=congelada, status_adr=status_adr)
    texto = "\n".join(linhas).rstrip() + "\n"
    conferir_linguagem_descritiva(texto)
    return texto


def markdown_da_concordancia(bloco: Mapping[str, Any], *, versao: str, congelada: bool) -> str:
    """O bloco C em arquivo próprio — a "tabela de concordância" de RF-037, sozinha."""
    linhas = [f"# Concordância entre lentes — `{QUARTER_DO_COMITE}`", ""]
    if not congelada:
        linhas += [f"> ⛔ **{MARCA_NAO_CONGELADA}** (CA-090).", ""]
    linhas += [
        "> Leitura **descritiva** (Anti-SPEC §10.2.10). A divergência entre lentes é reportada "
        "como resultado, nunca omitida (CA-103).",
        "",
    ]
    linhas += _bloco_c(bloco)
    linhas += [
        "---",
        "",
        f"`versao_build` **`{versao}`**. Tabela conferível em "
        f"`{SUBPASTA_TABELAS}/{NOME_CONCORDANCIA}.parquet` e `.csv` "
        "(formato *tidy*: `secao | chave | metrica | valor_num | valor_texto`).",
    ]
    texto = "\n".join(linhas).rstrip() + "\n"
    conferir_linguagem_descritiva(texto)
    return texto


# ─────────────────────────────────────────────────────────────────────────────
# Gravação
# ─────────────────────────────────────────────────────────────────────────────


def gravar_tabela(
    quadro: pd.DataFrame, texto: str, *, nome: str, raiz: Path | None = None
) -> dict[str, Path]:
    """Grava `<nome>.{parquet,csv,md}` em `data/canonical/tabelas/`, os três do mesmo DataFrame."""
    pasta = garantir_diretorio(caminho_tabelas(raiz=raiz))
    caminhos: dict[str, Path] = {}
    for formato in FORMATOS:
        alvo = pasta / f"{nome}.{formato}"
        if formato == "parquet":
            quadro.to_parquet(alvo, index=False)
        elif formato == "csv":
            quadro.to_csv(alvo, index=False, encoding="utf-8", lineterminator="\n")
        else:
            alvo.write_text(texto, encoding="utf-8", newline="\n")
        caminhos[f"{nome}.{formato}"] = alvo
    return caminhos


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────


def montar_relatorio(
    *,
    respostas: Sequence[RespostaDeRegime],
    ranking: pd.DataFrame,
    bloco_c: Mapping[str, Any],
    versao: str,
    hashes: Mapping[str, str],
    congelada: bool,
    status_adr: str,
    caminhos: Mapping[str, Path],
) -> dict[str, Any]:
    """O que o stdout imprime e o que vai ao relatório do PR — sem nada do relógio."""
    return {
        "feature": "F-024",
        "versao_build": versao,
        "hashes_dos_insumos": dict(sorted(hashes.items())),
        "gate_de_publicacao": {
            "adr": "ADR-001",
            "status_do_adr": status_adr,
            "especificacao_congelada": congelada,
            "veredito": veredito_publicacao(congelada),
            "marca": None if congelada else MARCA_NAO_CONGELADA,
        },
        "regime_atual": [
            {
                "lente": r.titulo,
                "quarter_perguntado": r.quarter_perguntado,
                "status": r.status,
                "resposta": r.resposta,
                "quarter_da_celula": r.quarter_da_celula,
                "regime_da_celula": r.regime_da_celula,
                "e_fallback": r.e_fallback,
            }
            for r in respostas
        ],
        "ranking": {
            "linhas": int(len(ranking)),
            "lentes": sorted(set(ranking["lente_rotulo"].astype(str))),
            "ativos_por_lente": int(
                ranking.groupby("lente_rotulo", sort=True)["asset_id"].nunique().min()
            ),
            "celulas_sem_n": int(ranking["n_obs"].isna().sum()),
            "com_alerta_n_baixo": int(ranking["alerta_n_baixo"].sum()),
            "com_conclusao_suprimida": int(ranking["conclusao_suprimida"].sum()),
            "acima_de_2_erros_padrao": int(ranking["distinguivel_de_ruido"].sum()),
        },
        "concordancia": {
            "em_todas_as_lentes": bloco_c["em_todas_as_lentes"],
            "pares": {
                chave: {
                    "jaccard_top5": dados["jaccard_top5"],
                    "jaccard_top10": dados["jaccard_top10"],
                    "spearman": dados["spearman"]["rho"],
                }
                for chave, dados in bloco_c["pares"].items()
            },
            "variantes_v3": {
                "referencias_comparadas": bloco_c["variantes_v3"]["referencias_comparadas"],
                **bloco_c["variantes_v3"]["distribuicao"],
            },
        },
        "arquivos": {chave: str(caminho) for chave, caminho in sorted(caminhos.items())},
    }


def construir(
    *,
    raiz: Path | None = None,
    gravar: bool = True,
    quarter: str = QUARTER_DO_COMITE,
) -> ResultadoTabela:
    """Lê o canônico, monta as duas tabelas e (opcionalmente) grava os 6 arquivos.

    Nenhuma rede, nenhum relógio, nenhuma variável de ambiente: duas chamadas no mesmo checkout
    com o mesmo `data/canonical/` produzem Parquet, CSV e Markdown byte-idênticos.
    """
    versao = versao_build()
    congelada = especificacao_esta_congelada(raiz=raiz)
    status_adr = status_adr_001(raiz=raiz)
    if not congelada:
        _log.warning(
            "%s: ADR-001 em %s, especificacao_congelada=False (CA-090)",
            MARCA_NAO_CONGELADA_ASCII,
            status_adr,
        )

    regimes_revised = ler_regimes_v1(materializacao=Materializacao.REVISED, raiz=raiz)
    regimes_asof = ler_regimes_v1(materializacao=Materializacao.ASOF, raiz=raiz)
    neighbors = ler_neighbors_v3(raiz=raiz)
    metricas = {
        TABELA_PRINCIPAL.rotulo: ler_metricas(TABELA_PRINCIPAL, raiz=raiz),
        TABELA_ASOF.rotulo: ler_metricas(TABELA_ASOF, raiz=raiz),
    }

    vizinhos = vizinhos_do_quarter(neighbors, quarter=quarter)
    respostas = respostas_do_regime_atual(
        regimes_revised=regimes_revised,
        regimes_asof=regimes_asof,
        vizinhos=vizinhos,
        quarter=quarter,
    )
    pct_de_troca = divergencia_entre_materializacoes(regimes_revised, regimes_asof)[
        "pct_que_trocam"
    ]
    lentes = lentes_da_pagina(respostas)
    if len(lentes) != N_LENTES:
        msg = f"{len(lentes)} lentes, esperadas {N_LENTES} (CA-098)"
        raise SerieInconsistente(msg)

    ranking = tabela_de_ranking(metricas=metricas, lentes=lentes, versao=versao)
    bloco_c = concordancia(ranking=ranking, lentes=lentes, neighbors=neighbors)
    tabela_concordancia = tabela_de_concordancia(bloco_c, versao=versao)

    hashes = hashes_dos_insumos(raiz=raiz)
    markdown_ranking = markdown_da_pagina(
        respostas=respostas,
        vizinhos=vizinhos,
        ranking=ranking,
        lentes=lentes,
        bloco_c=bloco_c,
        versao=versao,
        hashes=hashes,
        congelada=congelada,
        status_adr=status_adr,
        pct_de_troca=pct_de_troca,
        quarter=quarter,
    )
    markdown_concordancia = markdown_da_concordancia(bloco_c, versao=versao, congelada=congelada)

    caminhos: dict[str, Path] = {}
    if gravar:
        caminhos |= gravar_tabela(ranking, markdown_ranking, nome=NOME_RANKING, raiz=raiz)
        caminhos |= gravar_tabela(
            tabela_concordancia, markdown_concordancia, nome=NOME_CONCORDANCIA, raiz=raiz
        )

    relatorio = montar_relatorio(
        respostas=respostas,
        ranking=ranking,
        bloco_c=bloco_c,
        versao=versao,
        hashes=hashes,
        congelada=congelada,
        status_adr=status_adr,
        caminhos=caminhos,
    )
    return ResultadoTabela(
        ranking=ranking,
        concordancia=tabela_concordancia,
        markdown_ranking=markdown_ranking,
        markdown_concordancia=markdown_concordancia,
        respostas=respostas,
        vizinhos=vizinhos,
        caminhos=caminhos,
        relatorio=relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m apps.analysis.tabelas.ranking_regime_atual",
        description=(
            "Gera data/canonical/tabelas/ranking_regime_atual.{parquet,csv,md} e "
            "concordancia_lentes.{parquet,csv,md} a partir de regime_asset_metrics (F-022), "
            "regimes_v1 (F-019) e regime_neighbors_v3 (F-021). Nunca toca a rede. Enquanto "
            "ADR-001 estiver em Proposta, a pagina nasce com a marca ESPECIFICACAO NAO CONGELADA "
            "(CA-090) e nao e publicavel."
        ),
    )


def _acrescentar_argumentos(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "--sem-gravar",
        action="store_true",
        help="monta tudo e imprime o resumo, sem escrever em data/canonical/tabelas/.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = tabelas geradas; `1` = falha explícita e nada gravado."""
    args = _acrescentar_argumentos(_parser()).parse_args(argv)
    configurar_logging()
    try:
        resultado = construir(gravar=not args.sem_gravar)
    except ErroDeExtracao as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 1

    relatorio = resultado.relatorio
    # ASCII puro nos `print`: o stdout do console no Windows e cp1252 (Anti-SPEC 10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(f"versao_build {relatorio['versao_build'][:12]}")
    for nome, digest in relatorio["hashes_dos_insumos"].items():
        print(f"  insumo {nome}: sha256 {digest[:12]}")
    print(f"gate CA-090: {relatorio['gate_de_publicacao']['veredito']}")
    for resposta in relatorio["regime_atual"]:
        marca = " (FALLBACK)" if resposta["e_fallback"] else ""
        print(
            f"regime atual | {resposta['lente']}: {resposta['resposta']} "
            f"[{resposta['status']}] -> celula {resposta['regime_da_celula']} "
            f"@ {resposta['quarter_da_celula']}{marca}"
        )
    bloco = relatorio["ranking"]
    print(
        f"ranking: {bloco['linhas']} linhas | {len(bloco['lentes'])} lentes x "
        f"{bloco['ativos_por_lente']} ativos | celulas sem n: {bloco['celulas_sem_n']} | "
        f"alerta n baixo: {bloco['com_alerta_n_baixo']} | conclusao suprimida: "
        f"{bloco['com_conclusao_suprimida']} | acima de 2 ep: "
        f"{bloco['acima_de_2_erros_padrao']}"
    )
    for chave, par in relatorio["concordancia"]["pares"].items():
        print(
            f"concordancia {chave}: jaccard top5 {par['jaccard_top5']:.4f} | top10 "
            f"{par['jaccard_top10']:.4f} | spearman {par['spearman']:.4f}"
        )
    variantes = relatorio["concordancia"]["variantes_v3"]
    print(
        f"variantes V3 (somente_passado x descritiva) em "
        f"{variantes['referencias_comparadas']} refs: mediana {variantes['mediana']:.4f} | "
        f"q1 {variantes['q1']:.4f} | q3 {variantes['q3']:.4f} | "
        f"iguais a 1: {variantes['n_iguais_a_1']}"
    )
    for chave, caminho in relatorio["arquivos"].items():
        print(f"gravado {chave}: {caminho}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
