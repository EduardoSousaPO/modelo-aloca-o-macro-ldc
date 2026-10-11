"""F-025 — Timeline de regimes V1 2006Q1→2026Q3 sobre IBOV e Selic meta. **RF-035 / CA-100.**

O que esta figura é, em uma frase: **o sanity check visual** com quem viveu o período. Se a faixa
de regimes não "fizer sentido" para o Comitê — 2008, 2015-2016, 2020, 2021-2022 —, a hipótese H-02
do PRD cai, e **isso é resultado**, não defeito (`TODO.md` F-025, `modules/regimes.md`).

## O que entra e o que sai

| Insumo | Arquivo em `data/canonical/` | O que se lê dele |
|---|---|---|
| V1 `revised` | `regimes_v1.parquet` | `regime_v1`, `status_regime_v1`, `n_obs_regime_v1`, gate |
| V1 `asof` | `regimes_v1_asof.parquet` | o mesmo, na materialização defasada (F-018) |
| Níveis | `alinhado_trimestral.parquet` | `B3_IBOV` (índice) e `BCB_SGS_432` (Selic meta, %a.a.) |

Saída em `data/canonical/figuras/`: `timeline_regimes_{revised,asof}.png` + `.svg` e
`timeline_regimes_dados.parquet` — **os dados exatamente como plotados**, para que a figura seja
conferível linha a linha em vez de acreditada.

## As três decisões de forma, e por que não são de gosto

1. **Dois painéis empilhados, nunca dois eixos y no mesmo painel.** IBOV é nível de índice
   (37.952 → 186.340, escala log) e Selic meta é %a.a. (16,50 → 13,75). Sobrepor as duas num
   painel com eixo esquerdo e direito é o erro nº 1 de gráfico: a posição relativa das curvas
   passa a ser um artefato da escolha de escala, e "o IBOV cruzou a Selic em 2016" é uma frase
   sem significado. A skill `dataviz` proíbe eixo duplo e manda **painéis separados ou pequenos
   múltiplos**; o eixo x é compartilhado, então a leitura cronológica conjunta — que é o que
   CA-100 pede — fica intacta, e **a faixa colorida cobre os 83 trimestres sobre as duas séries**
   porque é desenhada dentro de cada painel.
2. **Faixa em dois canais: lavagem + fita saturada.** O fundo de cada painel recebe a cor do
   quadrante como *lavagem* (~14% de opacidade — a regra de área da `dataviz`, "nunca um bloco
   saturado"), senão a linha em cima fica ilegível; e a **cor validada, cheia**, aparece numa fita
   fina na base do painel. Lavagem clara não carrega identidade sozinha, então a identidade vem
   da fita + legenda + rótulo direto nas faixas longas.
3. **`INDETERMINADO` é cinza hachurado, não uma cor.** Os 16 trimestres sem `ibcbr_gap` (**D-m**,
   2006Q1-2009Q3 na `revised`) não têm quadrante, e dar-lhes uma cor categórica os faria parecer
   um 5º regime. Hachura + cinza neutro dizem "ausência", que é o que são — e é o que impede o
   "buraco visual não explicado" de CA-100: **não há buraco; há faixa rotulada de ausência.**

## Paleta (validada, não escolhida a olho)

Os 4 quadrantes usam os slots **1, 2, 3 e 7** da paleta de referência da `dataviz`
(azul, laranja, água, violeta). O conjunto passou os seis checks em modo claro **no pairlist
completo** (`--pairs all`, superfície `#fcfcfb`): nenhum FAIL — banda de luminosidade, piso de
croma, separação sob protanopia/deuteranopia, piso de visão normal e contraste. O pairlist
completo é o certo aqui porque a ordem em que os quadrantes se encostam no tempo é dada pelo dado,
não pelo desenho: qualquer par pode virar vizinho.

A associação **quadrante → slot segue a ordem de declaração do enum `RegimeV1`** e é fixa para
sempre (`COR_POR_REGIME`). Deliberadamente **não** há semântica de valência (verde = bom, vermelho
= ruim): `modules/regimes.md` registra que ler o rótulo como juízo é o erro de leitura mais comum
— `RECUPERACAO` é hiato de crescimento acima da tendência, não "boa notícia", e `ESTAGFLACAO` com
IPCA caindo de 11% para 7% não é pior que `RECUPERACAO` com IPCA a 7,17%.

## Honestidade estatística (Anti-SPEC §10.2)

- **Descritivo, nunca preditivo** (§10.2.10): o subtítulo diz "como foi", e não há uma única
  projeção, extrapolação ou linha tracejada para frente.
- **`n` em toda célula** (§10.2.8): a legenda traz `n` de cada quadrante e dos indeterminados.
- **`asof` é sempre rotulada** (§10.2.7): cada figura diz no título qual materialização desenha, e
  os trimestres em que as duas discordam ganham **marcador** — 22 trocas de rótulo + 2 trocas de
  *status* = os 24 de `trocou_vs_revised`. A troca de 33,33% nos 66 comparáveis já acionou CA-074
  e está no rodapé: **a V1 não é operacional na forma `asof`**.
- **Gate de publicação** (CA-090): `especificacao_congelada=False` ⇒ marca d'água diagonal + linha
  de rodapé `ESPECIFICAÇÃO NÃO CONGELADA — não publicável`. A figura é gerada (desenvolver é
  liberado), mas nasce não publicável.

## Determinismo

Nenhum valor sai do relógio. `Figure` instanciada direta (sem `pyplot`, sem estado global),
backend `Agg`, `svg.hashsalt` fixo, `metadata={"Date": None}` no SVG e `Software` fixo no PNG. Duas
rodadas no mesmo checkout produzem SVG e Parquet byte-idênticos; o PNG é verificado na prática
(ver `docs/wiki/context/F-025.md`).

**Nota de contrato:** `data/canonical/figuras/` é artefato **derivado de figura**, não tabela
canônica — por isso o Parquet de dados plotados não tem schema em `packages/shared/schemas/`
(F-025 é classe B e não acrescenta schema). O contrato das colunas é `COLUNAS_DADOS_PLOTADOS`,
travado por teste, e **todo nome de coluna vinda de `regimes_v1` é literal**, sem renomeação
(Anti-SPEC §10.4.24 em espírito). Quem transformar isso em insumo de modelo migra para classe C.

Cobre: RF-035 · CA-100 (+ CA-090 como gate) · e-mail A1, A2, A4, B4 · Anti-SPEC §10.2.7, §10.2.8,
§10.2.10, §10.4.26.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # antes de qualquer import de desenho: nenhuma janela, nenhum backend GUI

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from apps.pipeline.canonical.build_raw_series import caminhos_dos_componentes
from apps.pipeline.canonical.build_raw_series import versao_build as _hash_dos_componentes
from apps.pipeline.canonical.regimes_v1 import (
    Materializacao,
    especificacao_esta_congelada,
    veredito_publicacao,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, garantir_diretorio, raiz_repo
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from packages.shared.schemas.regimes import RegimesV1Schema, RegimeV1, StatusRegimeV1

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

    from matplotlib.axes import Axes

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Insumos e destinos
# ─────────────────────────────────────────────────────────────────────────────

#: Série do IBOV em `alinhado_trimestral` — **nível** do índice, não retorno.
SERIE_IBOV = "B3_IBOV"
#: Série da **Selic meta** (SGS 432), em %a.a. Não é a Selic efetiva (SGS 1178/4189).
SERIE_SELIC_META = "BCB_SGS_432"

NOME_ALINHADO = "alinhado_trimestral.parquet"
NOME_REGIMES_POR_MATERIALIZACAO: dict[str, str] = {
    Materializacao.REVISED.value: "regimes_v1.parquet",
    Materializacao.ASOF.value: "regimes_v1_asof.parquet",
}

#: Subpasta de `data/canonical/` onde as figuras e os dados plotados vivem.
SUBPASTA_FIGURAS = "figuras"
NOME_DADOS_PLOTADOS = "timeline_regimes_dados.parquet"
FORMATOS: tuple[str, ...] = ("png", "svg")
DPI_PNG = 150

#: Os módulos que determinam o conteúdo da figura, **nesta ordem** — base de `versao_build`.
#: O schema entra porque o enum dos 4 rótulos e os nomes das colunas moram lá.
MODULOS_DA_TIMELINE: tuple[str, ...] = (
    "apps.analysis.figuras.timeline_regimes",
    "packages.shared.schemas.regimes",
)

N_TRIMESTRES_ESPERADO = 83
"""A janela do escopo: 2006Q1→2026Q3 (`ESCOPO-EMAIL-ALEXANDRE.md`, 20 anos trimestrais)."""


class TipoDeTroca(StrEnum):
    """Como `asof` e `revised` discordam num trimestre. Vai **no dado**, não só no desenho."""

    NENHUMA = "NENHUMA"
    #: As duas classificam, com quadrantes diferentes — os 22 de CA-074.
    ROTULO = "ROTULO"
    #: Uma classifica e a outra não (2009Q4 e 2026Q3) — troca de `status`, não de quadrante.
    STATUS = "STATUS"


# ─────────────────────────────────────────────────────────────────────────────
# Paleta — validada com `dataviz/scripts/validate_palette.py`, não escolhida a olho
# ─────────────────────────────────────────────────────────────────────────────

#: Slots 1, 2, 3 e 7 da paleta de referência da `dataviz` (azul, laranja, água, violeta).
#: `validate_palette.py "#2a78d6,#eb6834,#1baf7a,#4a3aa7" --mode light --pairs all` → 0 FAIL.
PALETA_CATEGORICA: tuple[str, ...] = ("#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7")

#: Quadrante → cor, na **ordem de declaração do enum**. Fixa; nunca reciclada, nunca por ranking.
COR_POR_REGIME: dict[str, str] = dict(
    zip([r.value for r in RegimeV1], PALETA_CATEGORICA, strict=True)
)

#: `INDETERMINADO` não é um 5º regime: cinza neutro (a tinta "muted" do sistema) + hachura.
COR_INDETERMINADO = "#898781"
HACHURA_INDETERMINADO = "///"
ROTULO_INDETERMINADO = StatusRegimeV1.INDETERMINADO.value

#: Cromo do gráfico (superfície, tintas, grade) — os papéis de `dataviz/references/palette.md`.
SUPERFICIE = "#fcfcfb"
TINTA_PRIMARIA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_MUTED = "#898781"
COR_GRADE = "#e1e0d9"
COR_EIXO = "#c3c2b7"
COR_CRITICO = "#d03b3b"

#: Opacidade da lavagem de fundo (`dataviz`: área é lavagem, "nunca um bloco saturado").
ALPHA_LAVAGEM = 0.14
#: Altura da fita saturada na base do painel, em fração do eixo.
ALTURA_FITA = 0.035
#: `y` (fração do eixo) dos marcadores de divergência `asof` × `revised`.
Y_MARCADORES = 0.075
#: Faixa com pelo menos tantos trimestres recebe rótulo direto dentro do painel.
MINIMO_PARA_ROTULO_DIRETO = 5

#: Abreviação de cada rótulo para o texto dentro da faixa (a legenda traz o nome completo).
ABREVIACAO: dict[str, str] = {
    RegimeV1.RECUPERACAO.value: "REC",
    RegimeV1.EXPANSAO_INFL.value: "EXP",
    RegimeV1.ESTAGFLACAO.value: "EST",
    RegimeV1.DESACELERACAO.value: "DES",
    ROTULO_INDETERMINADO: "IND",
}

# ─────────────────────────────────────────────────────────────────────────────
# Geometria — tudo em fração da figura, numa só lista, para que nada colida
#
# Os números são frouxos de propósito: título/subtítulo em cima, painéis no meio, legenda e
# rodapé embaixo, cada bloco com faixa própria. Mexer num sem olhar os outros é como os rótulos
# do eixo x acabam por baixo da legenda.
# ─────────────────────────────────────────────────────────────────────────────

FIGSIZE: tuple[float, float] = (13.5, 9.0)
MARGEM_ESQUERDA = 0.045
Y_TOPO_DOS_PAINEIS = 0.862
Y_BASE_DOS_PAINEIS = 0.235
Y_TOPO_DA_LEGENDA = 0.185
Y_TOPO_DO_RODAPE = 0.082
ENTRELINHA_RODAPE = 0.021

#: Semente fixa dos `id` do SVG: sem ela o SVG muda de bytes entre processos (determinismo).
SALGA_SVG = "ldc-f025-timeline-regimes"

MARCA_NAO_CONGELADA = "ESPECIFICAÇÃO NÃO CONGELADA — não publicável"
"""CA-090 por escrito, na figura. Enquanto ADR-001 estiver em `Proposta`, é obrigatória."""

LEITURA_DESCRITIVA = (
    "Leitura descritiva: o que o IBOV e a Selic meta fizeram em cada regime. "
    "Nada aqui é projeção (Anti-SPEC §10.2.10)."
)

# ─────────────────────────────────────────────────────────────────────────────
# O contrato de colunas dos dados plotados
# ─────────────────────────────────────────────────────────────────────────────

#: Colunas de `regimes_v1` reproduzidas **com o mesmo nome e o mesmo significado**.
COLUNAS_HERDADAS_DE_REGIMES_V1: tuple[str, ...] = (
    "quarter",
    "regime_v1",
    "status_regime_v1",
    "n_obs_regime_v1",
    "lag_adjusted",
    "especificacao_congelada",
    "versao_especificacao",
    "fonte_versao",
)

#: O contrato completo do Parquet de dados plotados, **nesta ordem**.
COLUNAS_DADOS_PLOTADOS: tuple[str, ...] = (
    "materializacao",
    *COLUNAS_HERDADAS_DE_REGIMES_V1,
    "quarter_end",
    "ibov_nivel",
    "selic_meta_pct",
    "cor_hex",
    "hachura",
    "rotulo_da_faixa",
    "trocou_vs_outra_materializacao",
    "tipo_de_troca",
)


@dataclass(frozen=True, slots=True)
class Faixa:
    """Um trecho contíguo de trimestres com o mesmo rótulo — uma faixa colorida da figura."""

    inicio: int
    fim: int
    rotulo: str
    cor: str
    hachura: str

    @property
    def n_trimestres(self) -> int:
        """Quantos trimestres a faixa cobre (inclusive nas duas pontas)."""
        return self.fim - self.inicio + 1


@dataclass(frozen=True, slots=True)
class ResultadoTimeline:
    """O que uma rodada produziu — a figura é a leitura, isto é a evidência."""

    dados: pd.DataFrame
    figuras: dict[str, Figure]
    caminhos: dict[str, Path]
    caminho_dados: Path | None
    relatorio: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Leitura dos insumos
# ─────────────────────────────────────────────────────────────────────────────


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do conjunto `MODULOS_DA_TIMELINE` — o `versao_build` do rodapé (RF-047/CA-121)."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DA_TIMELINE))


def sha256_do_arquivo(alvo: Path) -> str:
    """`sha256` do Parquet lido, byte a byte — o "hash dos insumos" do rodapé."""
    return hashlib.sha256(Path(alvo).read_bytes()).hexdigest()


def caminho_figuras(*, raiz: Path | None = None) -> Path:
    """`data/canonical/figuras/` — a pasta de saída desta camada."""
    return caminho_canonical(SUBPASTA_FIGURAS, raiz=raiz)


def ler_regimes(materializacao: Materializacao | str, *, raiz: Path | None = None) -> pd.DataFrame:
    """Lê e **valida** `regimes_v1{,_asof}.parquet` com `RegimesV1Schema`. Ausente = falha."""
    chave = Materializacao(materializacao).value
    alvo = caminho_canonical(NOME_REGIMES_POR_MATERIALIZACAO[chave], raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.regimes_v1 --materializacao {chave}`."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        validado = RegimesV1Schema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz regimes_v1: {erro}"
        raise SerieInconsistente(msg) from erro
    return pd.DataFrame(validado).sort_values("quarter", kind="stable").reset_index(drop=True)


def ler_niveis(*, raiz: Path | None = None) -> pd.DataFrame:
    """`quarter | quarter_end | ibov_nivel | selic_meta_pct` de `alinhado_trimestral`.

    Nada é interpolado nem preenchido: célula nula chega nula e a linha quebra o desenho da série
    naquele ponto (Anti-SPEC §10.1.1). As duas séries são `D` com `ffill`, então na prática não
    há nulo — e se aparecer, aparece como descontinuidade declarada, não como reta inventada.
    """
    alvo = caminho_canonical(NOME_ALINHADO, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.alinhamento`."
        )
        raise FonteIndisponivel(msg)
    return niveis_de(pd.read_parquet(alvo))


def niveis_de(alinhado: pd.DataFrame) -> pd.DataFrame:
    """Recorta IBOV e Selic meta de uma tabela no formato de `alinhado_trimestral` (função pura)."""
    faltando = [c for c in ("quarter", "quarter_end", "series_id", "value") if c not in alinhado]
    if faltando:
        msg = f"entrada não parece `alinhado_trimestral`: falta {faltando}"
        raise SerieInconsistente(msg)
    recorte = alinhado[alinhado["series_id"].isin([SERIE_IBOV, SERIE_SELIC_META])]
    ausentes = {SERIE_IBOV, SERIE_SELIC_META} - set(recorte["series_id"].unique())
    if ausentes:
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: série(s) {sorted(ausentes)} fora de {NOME_ALINHADO}"
        raise FonteIndisponivel(msg)
    largo = (
        recorte.pivot_table(index=["quarter", "quarter_end"], columns="series_id", values="value")
        .reset_index()
        .rename(columns={SERIE_IBOV: "ibov_nivel", SERIE_SELIC_META: "selic_meta_pct"})
    )
    largo.columns.name = None
    return (
        largo[["quarter", "quarter_end", "ibov_nivel", "selic_meta_pct"]]
        .sort_values("quarter", kind="stable")
        .reset_index(drop=True)
    )


# ─────────────────────────────────────────────────────────────────────────────
# A função pura: os dados exatamente como vão ser plotados
# ─────────────────────────────────────────────────────────────────────────────


def rotulos_das_faixas(tabela: pd.DataFrame) -> dict[str, str]:
    """`quarter -> rótulo da faixa`: o quadrante, ou `INDETERMINADO`. Nunca uma estimativa.

    O rótulo sai de `status_regime_v1`, não de `regime_v1.notna()`: é o `status` que é
    `nullable=False` no contrato, e o check `status_coerente_com_o_rotulo` do schema já garante
    que os dois nunca discordam. Ler o status é ler a afirmação; ler o nulo é inferi-la.
    """
    classificado = tabela["status_regime_v1"] == StatusRegimeV1.CLASSIFICADO.value
    rotulos = tabela["regime_v1"].where(classificado, ROTULO_INDETERMINADO)
    return dict(zip(tabela["quarter"].astype(str), rotulos.astype(str), strict=True))


def _tipo_de_troca(rotulo_a: str, rotulo_b: str) -> str:
    """Como os dois rótulos do mesmo trimestre discordam (ou não) entre materializações."""
    if rotulo_a == rotulo_b:
        return TipoDeTroca.NENHUMA.value
    if ROTULO_INDETERMINADO in (rotulo_a, rotulo_b):
        return TipoDeTroca.STATUS.value
    return TipoDeTroca.ROTULO.value


def dados_plotados(
    regimes_por_materializacao: Mapping[str, pd.DataFrame],
    niveis: pd.DataFrame,
) -> pd.DataFrame:
    """**A função pura da feature**: devolve o DataFrame que a figura desenha, e nada mais.

    Uma linha por `(materializacao, quarter)`. As colunas de regime são as de `regimes_v1`, com o
    mesmo nome; o que se acrescenta é o par de níveis, a cor/hachura que o desenho vai usar e a
    divergência entre as duas materializações.

    A divergência é calculada **aqui**, comparando as duas tabelas, e não copiada de
    `trocou_vs_revised`: assim o número da figura é verificável contra a coluna do Parquet em vez
    de herdado dela (há teste que confirma que os dois coincidem). Quando só uma materialização é
    pedida, `trocou_vs_outra_materializacao` é `False` e `tipo_de_troca` é `NENHUMA` em todas as
    linhas — não há com o que comparar, e inventar comparação seria pior que não ter.
    """
    if not regimes_por_materializacao:
        msg = "nenhuma materialização para plotar"
        raise SerieInconsistente(msg)

    rotulos = {
        chave: rotulos_das_faixas(tabela) for chave, tabela in regimes_por_materializacao.items()
    }

    pedacos: list[pd.DataFrame] = []
    for chave in sorted(regimes_por_materializacao):
        tabela = regimes_por_materializacao[chave]
        outras = [k for k in sorted(regimes_por_materializacao) if k != chave]
        bloco = tabela[list(COLUNAS_HERDADAS_DE_REGIMES_V1)].copy()
        bloco.insert(0, "materializacao", chave)
        bloco = bloco.merge(niveis, on="quarter", how="left", validate="one_to_one")
        if bloco["quarter_end"].isna().any():
            orfaos = bloco.loc[bloco["quarter_end"].isna(), "quarter"].tolist()
            msg = f"trimestres sem nível de IBOV/Selic em {NOME_ALINHADO}: {orfaos}"
            raise SerieInconsistente(msg)

        meus = [rotulos[chave][q] for q in bloco["quarter"]]
        bloco["cor_hex"] = [COR_POR_REGIME.get(r, COR_INDETERMINADO) for r in meus]
        bloco["hachura"] = [
            HACHURA_INDETERMINADO if r == ROTULO_INDETERMINADO else "" for r in meus
        ]
        bloco["rotulo_da_faixa"] = meus
        tipos = [
            next(
                (
                    tipo
                    for outra in outras
                    if (tipo := _tipo_de_troca(rotulos[chave][q], rotulos[outra][q]))
                    != TipoDeTroca.NENHUMA.value
                ),
                TipoDeTroca.NENHUMA.value,
            )
            for q in bloco["quarter"]
        ]
        bloco["tipo_de_troca"] = tipos
        bloco["trocou_vs_outra_materializacao"] = [t != TipoDeTroca.NENHUMA.value for t in tipos]
        pedacos.append(bloco)

    saida = pd.concat(pedacos, ignore_index=True)
    saida = saida.sort_values(["materializacao", "quarter"], kind="stable").reset_index(drop=True)
    return saida[list(COLUNAS_DADOS_PLOTADOS)]


def faixas_de(dados: pd.DataFrame) -> list[Faixa]:
    """Agrupa trimestres consecutivos de mesmo rótulo nas faixas que serão desenhadas."""
    saida: list[Faixa] = []
    for posicao, (_, linha) in enumerate(dados.reset_index(drop=True).iterrows()):
        rotulo = str(linha["rotulo_da_faixa"])
        if saida and saida[-1].rotulo == rotulo and saida[-1].fim == posicao - 1:
            anterior = saida.pop()
            saida.append(Faixa(anterior.inicio, posicao, rotulo, anterior.cor, anterior.hachura))
            continue
        saida.append(Faixa(posicao, posicao, rotulo, str(linha["cor_hex"]), str(linha["hachura"])))
    return saida


def exigir_cobertura_total(faixas: Sequence[Faixa], n_trimestres: int) -> None:
    """**CA-100 em código:** as faixas cobrem os `n` trimestres, contíguas, sem buraco.

    Buraco aqui seria exatamente o "buraco visual não explicado" que o CA proíbe: um trimestre sem
    faixa nenhuma apareceria como superfície branca e seria lido como "nada aconteceu".
    """
    if not faixas:
        msg = "nenhuma faixa a desenhar"
        raise SerieInconsistente(msg)
    if faixas[0].inicio != 0 or faixas[-1].fim != n_trimestres - 1:
        msg = (
            f"faixas não cobrem a janela: começam em {faixas[0].inicio} e terminam em "
            f"{faixas[-1].fim}, para {n_trimestres} trimestres"
        )
        raise SerieInconsistente(msg)
    for anterior, seguinte in zip(faixas, faixas[1:], strict=False):
        if seguinte.inicio != anterior.fim + 1:
            msg = (
                f"buraco nas faixas entre as posições {anterior.fim} e {seguinte.inicio} "
                f"(CA-100: a faixa cobre os {n_trimestres} trimestres sem buraco)"
            )
            raise SerieInconsistente(msg)
    coberto = sum(f.n_trimestres for f in faixas)
    if coberto != n_trimestres:
        msg = f"faixas cobrem {coberto} trimestres, esperado {n_trimestres} (CA-100)"
        raise SerieInconsistente(msg)


def contagem_por_rotulo(dados: pd.DataFrame) -> dict[str, int]:
    """`n` por rótulo, na ordem do enum + `INDETERMINADO` — o `n` que vai à legenda (§10.2.8)."""
    bruto = dados["rotulo_da_faixa"].value_counts().to_dict()
    ordem = [*[r.value for r in RegimeV1], ROTULO_INDETERMINADO]
    return {rotulo: int(bruto.get(rotulo, 0)) for rotulo in ordem if bruto.get(rotulo, 0)}


# ─────────────────────────────────────────────────────────────────────────────
# O desenho
# ─────────────────────────────────────────────────────────────────────────────


def _rotulos_do_eixo_x(quarters: Sequence[str]) -> tuple[list[int], list[str]]:
    """Uma marca por ano, no `Q1` — 21 anos em 83 trimestres cabem sem colidir."""
    posicoes = [i for i, q in enumerate(quarters) if q.endswith("Q1")]
    return posicoes, [quarters[i][:4] for i in posicoes]


def _pintar_faixas(eixo: Axes, faixas: Sequence[Faixa], *, com_rotulo: bool) -> None:
    """Lavagem de fundo + fita saturada na base + rótulo direto nas faixas longas."""
    for faixa in faixas:
        esquerda, direita = faixa.inicio - 0.5, faixa.fim + 0.5
        eixo.axvspan(
            esquerda,
            direita,
            facecolor=faixa.cor,
            alpha=ALPHA_LAVAGEM,
            hatch=faixa.hachura or None,
            edgecolor=faixa.cor if faixa.hachura else "none",
            linewidth=0.0,
            zorder=0,
        )
        eixo.axvspan(
            esquerda,
            direita,
            ymin=0.0,
            ymax=ALTURA_FITA,
            facecolor=faixa.cor,
            alpha=1.0,
            hatch=faixa.hachura or None,
            edgecolor=SUPERFICIE if faixa.hachura else "none",
            linewidth=0.0,
            zorder=3,
        )
        if com_rotulo and faixa.n_trimestres >= MINIMO_PARA_ROTULO_DIRETO:
            eixo.text(
                (faixa.inicio + faixa.fim) / 2,
                0.965,
                ABREVIACAO.get(faixa.rotulo, faixa.rotulo[:3]),
                transform=eixo.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=8,
                color=TINTA_SECUNDARIA,
                zorder=4,
            )


def _marcar_divergencias(eixo: Axes, dados: pd.DataFrame) -> None:
    """Marcadores dos trimestres em que a outra materialização discorda (§10.2.7)."""
    posicoes = dados.reset_index(drop=True)
    for tipo, marcador, preenchido in (
        (TipoDeTroca.ROTULO.value, "v", True),
        (TipoDeTroca.STATUS.value, "s", False),
    ):
        xs = [i for i, t in enumerate(posicoes["tipo_de_troca"]) if t == tipo]
        if not xs:
            continue
        eixo.plot(
            xs,
            [Y_MARCADORES] * len(xs),
            transform=eixo.get_xaxis_transform(),
            linestyle="none",
            marker=marcador,
            markersize=7,
            markerfacecolor=TINTA_PRIMARIA if preenchido else SUPERFICIE,
            markeredgecolor=TINTA_PRIMARIA,
            markeredgewidth=1.2,
            clip_on=False,
            zorder=5,
        )


def _desenhar_serie(
    eixo: Axes,
    valores: Sequence[float],
    *,
    titulo: str,
    log: bool,
) -> None:
    """Uma série por painel — eixo y único, linha de 2px em tinta primária, grade recessiva."""
    eixo.plot(
        range(len(valores)),
        list(valores),
        color=TINTA_PRIMARIA,
        linewidth=2.0,
        solid_capstyle="round",
        zorder=2,
    )
    if log:
        eixo.set_yscale("log")
    eixo.set_title(titulo, loc="left", fontsize=11, color=TINTA_PRIMARIA, pad=6)
    eixo.set_facecolor(SUPERFICIE)
    eixo.grid(visible=True, axis="y", color=COR_GRADE, linewidth=0.8, zorder=1)
    eixo.set_axisbelow(True)
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eixo.spines[lado].set_color(COR_EIXO)
        eixo.spines[lado].set_linewidth(0.8)
    eixo.tick_params(colors=TINTA_MUTED, labelsize=9, length=3)


def _legenda(figura: Figure, dados: pd.DataFrame) -> None:
    """Legenda sempre presente, com `n` em cada entrada (§10.2.8) e os dois marcadores."""
    contagem = contagem_por_rotulo(dados)
    alcas: list[Any] = [
        Patch(
            facecolor=COR_POR_REGIME.get(rotulo, COR_INDETERMINADO),
            edgecolor=SUPERFICIE,
            hatch=HACHURA_INDETERMINADO if rotulo == ROTULO_INDETERMINADO else None,
            label=f"{rotulo} (n={n})",
        )
        for rotulo, n in contagem.items()
    ]
    n_rotulo = int((dados["tipo_de_troca"] == TipoDeTroca.ROTULO.value).sum())
    n_status = int((dados["tipo_de_troca"] == TipoDeTroca.STATUS.value).sum())
    if n_rotulo or n_status:
        alcas += [
            Line2D(
                [],
                [],
                linestyle="none",
                marker="v",
                markerfacecolor=TINTA_PRIMARIA,
                markeredgecolor=TINTA_PRIMARIA,
                markersize=7,
                label=f"a outra materialização dá outro quadrante (n={n_rotulo})",
            ),
            Line2D(
                [],
                [],
                linestyle="none",
                marker="s",
                markerfacecolor=SUPERFICIE,
                markeredgecolor=TINTA_PRIMARIA,
                markersize=7,
                label=f"a outra materialização classifica/indetermina (n={n_status})",
            ),
        ]
    figura.legend(
        handles=alcas,
        loc="upper center",
        bbox_to_anchor=(0.5, Y_TOPO_DA_LEGENDA),
        ncols=4,
        frameon=False,
        fontsize=9,
        labelcolor=TINTA_SECUNDARIA,
        handlelength=1.6,
        columnspacing=1.6,
    )


def _rodape(
    figura: Figure,
    *,
    linhas: Sequence[str],
    congelada: bool,
) -> None:
    """Procedência no pé da figura + a marca de CA-090 quando a especificação não está congelada."""
    for ordem, texto in enumerate(linhas):
        figura.text(
            MARGEM_ESQUERDA,
            Y_TOPO_DO_RODAPE - ordem * ENTRELINHA_RODAPE,
            texto,
            ha="left",
            va="top",
            fontsize=8,
            color=TINTA_MUTED,
        )
    if not congelada:
        figura.text(
            MARGEM_ESQUERDA,
            Y_TOPO_DO_RODAPE - len(linhas) * ENTRELINHA_RODAPE,
            MARCA_NAO_CONGELADA,
            ha="left",
            va="top",
            fontsize=9,
            fontweight="bold",
            color=COR_CRITICO,
        )
        figura.text(
            0.5,
            0.5,
            MARCA_NAO_CONGELADA,
            ha="center",
            va="center",
            fontsize=30,
            fontweight="bold",
            color=COR_CRITICO,
            alpha=0.10,
            rotation=20,
            zorder=10,
        )


def desenhar(
    dados: pd.DataFrame,
    *,
    materializacao: Materializacao | str,
    versao: str,
    hashes_dos_insumos: Mapping[str, str],
) -> Figure:
    """Desenha a figura de **uma** materialização e devolve a `Figure` (nada é gravado aqui).

    Separar desenho de gravação é o que faz o teste poder inspecionar textos, cores e limites de
    eixo sem tocar o disco — e o que faz `construir` ser a única função com efeito colateral.
    """
    chave = Materializacao(materializacao).value
    recorte = (
        dados[dados["materializacao"] == chave]
        .sort_values("quarter", kind="stable")
        .reset_index(drop=True)
    )
    if recorte.empty:
        msg = f"nenhuma linha da materializacao {chave!r} nos dados plotados"
        raise SerieInconsistente(msg)

    quarters = [str(q) for q in recorte["quarter"]]
    faixas = faixas_de(recorte)
    exigir_cobertura_total(faixas, len(quarters))
    congelada = bool(recorte["especificacao_congelada"].all())

    figura = Figure(figsize=FIGSIZE, dpi=DPI_PNG, facecolor=SUPERFICIE)
    eixos = figura.subplots(
        2, 1, sharex=True, gridspec_kw={"height_ratios": [1.3, 1.0], "hspace": 0.18}
    )
    figura.subplots_adjust(
        left=0.065, right=0.985, top=Y_TOPO_DOS_PAINEIS, bottom=Y_BASE_DOS_PAINEIS
    )

    _desenhar_serie(
        eixos[0],
        recorte["ibov_nivel"].tolist(),
        titulo="IBOV — nível do índice (escala log, eixo próprio)",
        log=True,
    )
    _desenhar_serie(
        eixos[1],
        recorte["selic_meta_pct"].tolist(),
        titulo="Selic meta (SGS 432) — % a.a. (eixo próprio)",
        log=False,
    )
    for ordem, eixo in enumerate(eixos):
        _pintar_faixas(eixo, faixas, com_rotulo=ordem == 0)
        _marcar_divergencias(eixo, recorte)
        eixo.set_xlim(-0.5, len(quarters) - 0.5)
    posicoes, textos = _rotulos_do_eixo_x(quarters)
    eixos[1].set_xticks(posicoes)
    eixos[1].set_xticklabels(textos, fontsize=9, color=TINTA_MUTED)

    figura.suptitle(
        f"Regimes macro V1 sobre IBOV e Selic meta — {quarters[0]} a {quarters[-1]} "
        f"({len(quarters)} trimestres, materialização {chave})",
        x=MARGEM_ESQUERDA,
        y=0.972,
        ha="left",
        fontsize=15,
        fontweight="bold",
        color=TINTA_PRIMARIA,
    )
    for ordem, linha in enumerate(
        (
            LEITURA_DESCRITIVA,
            "Faixa de fundo = quadrante V1 do trimestre; cinza hachurado = sem quadrante "
            "(`ibcbr_gap` ausente, D-m) — ausência declarada, não buraco.",
        )
    ):
        figura.text(
            MARGEM_ESQUERDA,
            0.932 - ordem * 0.024,
            linha,
            ha="left",
            va="top",
            fontsize=9.5,
            color=TINTA_SECUNDARIA,
        )
    _legenda(figura, recorte)
    _rodape(
        figura,
        linhas=(
            f"versao_build {versao[:12]} | "
            + " | ".join(f"{nome} {h[:12]}" for nome, h in sorted(hashes_dos_insumos.items())),
            f"Fonte: data/canonical/{NOME_REGIMES_POR_MATERIALIZACAO[chave]} + "
            f"{NOME_ALINHADO} ({SERIE_IBOV}, {SERIE_SELIC_META}). "
            f"fonte_versao dos rótulos: {str(recorte['fonte_versao'].iloc[0])[:12]}.",
            "V1 troca de rótulo entre `revised` e `asof` em 22 dos 66 trimestres comparáveis "
            "(33,33% > 25% de CA-074): a V1 NÃO é operacional na forma `asof`.",
        ),
        congelada=congelada,
    )
    return figura


# ─────────────────────────────────────────────────────────────────────────────
# Gravação
# ─────────────────────────────────────────────────────────────────────────────


def gravar_figura(
    figura: Figure,
    *,
    materializacao: Materializacao | str,
    versao: str,
    raiz: Path | None = None,
) -> dict[str, Path]:
    """Grava PNG + SVG de forma determinística: nenhum metadado sai do relógio."""
    chave = Materializacao(materializacao).value
    destino = garantir_diretorio(caminho_figuras(raiz=raiz))
    software = f"estrategia-macro-ldc-dados F-025 versao_build={versao}"
    saidas: dict[str, Path] = {}
    for formato in FORMATOS:
        alvo = destino / f"timeline_regimes_{chave}.{formato}"
        metadados: dict[str, Any] = (
            {"Software": software}
            if formato == "png"
            else {"Date": None, "Creator": software, "Title": f"timeline_regimes_{chave}"}
        )
        with matplotlib.rc_context({"svg.hashsalt": SALGA_SVG}):
            figura.savefig(alvo, format=formato, facecolor=SUPERFICIE, metadata=metadados)
        saidas[formato] = alvo
    return saidas


def gravar_dados(dados: pd.DataFrame, *, raiz: Path | None = None) -> Path:
    """Grava `timeline_regimes_dados.parquet` — os dados plotados, conferíveis linha a linha."""
    destino = garantir_diretorio(caminho_figuras(raiz=raiz)) / NOME_DADOS_PLOTADOS
    dados.to_parquet(destino, index=False)
    return destino


def construir(
    *,
    materializacoes: Sequence[Materializacao] | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
) -> ResultadoTimeline:
    """Lê o canônico, monta os dados plotados, desenha e (opcionalmente) grava.

    `materializacoes=None` significa **as duas**: a figura `revised` é a descritiva e a `asof`
    existe para mostrar que a troca de 33% não é retórica. A `asof` ausente em disco é falha
    explícita, nunca um fallback silencioso para `revised` (§10.2.7).
    """
    alvo = list(materializacoes) if materializacoes else list(Materializacao)
    regimes = {Materializacao(m).value: ler_regimes(m, raiz=raiz) for m in alvo}
    niveis = ler_niveis(raiz=raiz)
    dados = dados_plotados(regimes, niveis)

    versao = versao_build()
    hashes = {
        NOME_ALINHADO: sha256_do_arquivo(caminho_canonical(NOME_ALINHADO, raiz=raiz)),
        **{
            NOME_REGIMES_POR_MATERIALIZACAO[chave]: sha256_do_arquivo(
                caminho_canonical(NOME_REGIMES_POR_MATERIALIZACAO[chave], raiz=raiz)
            )
            for chave in regimes
        },
    }

    congelada_no_dado = bool(dados["especificacao_congelada"].all())
    congelada_em_disco = especificacao_esta_congelada(raiz=raiz)
    if congelada_no_dado != congelada_em_disco:
        _log.warning(
            "gate divergente: especificacao_congelada=%s no dado e %s no ADR-001 em disco - "
            "a figura segue o DADO, que e o que gerou os rotulos",
            congelada_no_dado,
            congelada_em_disco,
        )
    if not congelada_no_dado:
        _log.warning(
            "%s: toda figura desta rodada carrega a marca de CA-090",
            veredito_publicacao(congelada_no_dado),
        )

    figuras: dict[str, Figure] = {}
    caminhos: dict[str, Path] = {}
    for chave in sorted(regimes):
        figura = desenhar(dados, materializacao=chave, versao=versao, hashes_dos_insumos=hashes)
        figuras[chave] = figura
        if gravar:
            for formato, caminho in gravar_figura(
                figura, materializacao=chave, versao=versao, raiz=raiz
            ).items():
                caminhos[f"{chave}.{formato}"] = caminho

    caminho_dados = gravar_dados(dados, raiz=raiz) if gravar else None
    relatorio = montar_relatorio(
        dados,
        versao=versao,
        hashes_dos_insumos=hashes,
        congelada=congelada_no_dado,
        caminhos=caminhos,
        caminho_dados=caminho_dados,
    )
    if gravar:
        _log.info(
            "figuras gravadas em %s (%d arquivos, %d linhas de dados plotados)",
            caminho_figuras(raiz=raiz),
            len(caminhos),
            len(dados),
        )
    return ResultadoTimeline(
        dados=dados,
        figuras=figuras,
        caminhos=caminhos,
        caminho_dados=caminho_dados,
        relatorio=relatorio,
    )


def montar_relatorio(
    dados: pd.DataFrame,
    *,
    versao: str,
    hashes_dos_insumos: Mapping[str, str],
    congelada: bool,
    caminhos: Mapping[str, Path],
    caminho_dados: Path | None,
) -> dict[str, Any]:
    """O que o stdout imprime e o que vai ao relatório do PR — sem nada do relógio."""
    por_materializacao: dict[str, Any] = {}
    for chave, bloco in dados.groupby("materializacao", sort=True):
        faixas = faixas_de(bloco.sort_values("quarter", kind="stable"))
        por_materializacao[str(chave)] = {
            "trimestres": int(len(bloco)),
            "primeiro": str(bloco["quarter"].min()),
            "ultimo": str(bloco["quarter"].max()),
            "faixas": len(faixas),
            "n_por_rotulo": contagem_por_rotulo(bloco),
            "trocas_de_rotulo": int((bloco["tipo_de_troca"] == TipoDeTroca.ROTULO.value).sum()),
            "trocas_de_status": int((bloco["tipo_de_troca"] == TipoDeTroca.STATUS.value).sum()),
            "trimestres_que_trocam": [
                str(q)
                for q, t in zip(bloco["quarter"], bloco["tipo_de_troca"], strict=True)
                if t != TipoDeTroca.NENHUMA.value
            ],
        }
    return {
        "versao_build": versao,
        "hashes_dos_insumos": dict(sorted(hashes_dos_insumos.items())),
        "especificacao": {
            "especificacao_congelada": congelada,
            "veredito_publicacao": veredito_publicacao(congelada),
            "marca_na_figura": None if congelada else MARCA_NAO_CONGELADA,
        },
        "por_materializacao": por_materializacao,
        "arquivos": {chave: str(caminho) for chave, caminho in sorted(caminhos.items())},
        "dados_plotados": str(caminho_dados) if caminho_dados else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

ESCOLHA_AMBAS = "ambas"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.analysis.figuras.timeline_regimes",
        description=(
            "Gera data/canonical/figuras/timeline_regimes_{revised,asof}.{png,svg} + o Parquet "
            "dos dados plotados, a partir de regimes_v1 (F-019) e alinhado_trimestral (F-014). "
            "Nunca toca a rede. Enquanto ADR-001 estiver em Proposta, especificacao_congelada="
            "False e a figura carrega a marca ESPECIFICACAO NAO CONGELADA (CA-090)."
        ),
    )
    parser.add_argument(
        "--materializacao",
        choices=[*[m.value for m in Materializacao], ESCOLHA_AMBAS],
        default=ESCOLHA_AMBAS,
        help="revised, asof, ou ambas (default).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = figuras geradas; `1` = falha explícita e nada gravado."""
    args = _parser().parse_args(argv)
    configurar_logging()
    escolhidas = (
        None if args.materializacao == ESCOLHA_AMBAS else [Materializacao(args.materializacao)]
    )
    try:
        resultado = construir(materializacoes=escolhidas)
    except ErroDeExtracao as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 1

    relatorio = resultado.relatorio
    # ASCII puro nos `print`: o stdout do console no Windows e cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(f"versao_build {relatorio['versao_build'][:12]}")
    for nome, digest in relatorio["hashes_dos_insumos"].items():
        print(f"  insumo {nome}: sha256 {digest[:12]}")
    espec = relatorio["especificacao"]
    print(f"gate CA-090: {espec['veredito_publicacao']}")
    for chave, bloco in relatorio["por_materializacao"].items():
        print(
            f"{chave}: {bloco['trimestres']} trimestres ({bloco['primeiro']}..{bloco['ultimo']}) "
            f"| {bloco['faixas']} faixas | trocas rotulo {bloco['trocas_de_rotulo']} / status "
            f"{bloco['trocas_de_status']}"
        )
        for rotulo, n in bloco["n_por_rotulo"].items():
            print(f"  {rotulo}: n={n}")
    for chave, caminho in relatorio["arquivos"].items():
        print(f"gravado {chave}: {caminho}")
    print(f"dados plotados: {relatorio['dados_plotados']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
