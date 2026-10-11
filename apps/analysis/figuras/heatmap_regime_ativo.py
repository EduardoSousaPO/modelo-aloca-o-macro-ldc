"""F-023 — Heatmap regime × ativo: o **entregável visual central**. RF-033 / CA-095..097.

Uma frase: *em cada regime macro, quanto cada ativo rendeu **acima ou abaixo do CDI**, com o `n`
na própria célula*. Linhas = os **24** ativos de `asset_returns_quarterly`, agrupados por classe;
colunas = os 4 quadrantes da V1 **mais** a coluna dos vizinhos da V3; célula = `excesso_cdi`
(ADR-002 / **D5 provisório**), em escala divergente centrada em zero.

## O que entra e o que sai

| Vista (slug) | Insumo em `data/canonical/` | O que a figura mostra |
|---|---|---|
| **`v1_revised`** | `regime_asset_metrics.parquet` | V1 `revised` em T0 (4 col.) + V3 em T+1 |
| `v1_asof` | `regime_asset_metrics_asof.parquet` | V1 `asof` em T0 — só V1 (a V3 não tem `asof`) |
| `v3_t1` | `regime_asset_metrics_horizonte_cruzado.parquet` | V1 em T+1 + V3 contemporânea |

A janela e o `n` de cada regime saem de `regimes_v1{,_asof}.parquet` (F-019), lidos e validados
pela função **importada** de F-025 — não recalculados aqui.

> ⚠️ **Dívida de nome, para o orquestrador.** O slug `v3_t1` vem do briefing desta feature, mas a
> vista que ele nomeia é o **horizonte cruzado**, em que a V1 é medida em T+1 e a V3 é
> **contemporânea (T0)** — ou seja, o slug sugere o oposto do horizonte da V3 naquela figura.
> O título, o cabeçalho de cada coluna e o Parquet de dados plotados dizem o horizonte correto em
> todos os casos; só o **nome do arquivo** é infeliz. Renomear para `heatmap_horizonte_cruzado` é
> trocar uma constante (`VISTAS`) e re-rodar.

Saída em `data/canonical/figuras/`: `heatmap_{v1_revised,v1_asof,v3_t1}.{png,svg}` +
`heatmap_dados.parquet` — **os dados exatamente como plotados**, para que a figura seja conferível
célula a célula em vez de acreditada.

## As decisões de forma, e por que nenhuma é de gosto

1. **Heatmap, e não 24 barras agrupadas.** A pergunta é "esta classe, neste regime" — uma matriz
   de identidade × identidade com um valor contínuo dentro. Barra agrupada com 24 × 5 = 120
   barras não é lida por ninguém; a matriz é.
2. **Escala divergente simétrica, centrada em zero** (`dataviz`, ADR-002 §3): azul = bateu o CDI,
   vermelho = perdeu do CDI, cinza = empatou. A simetria (`-extremo .. +extremo`) é o que faz o
   cinza do meio significar "zero" — com `vmin`/`vmax` independentes o zero sairia do meio e a
   figura mentiria sobre o sinal. **Verde está deliberadamente fora**: verde × vermelho é o par
   que colapsa em protanopia/deuteranopia (ver `_comum.py`).
3. **`n` em toda célula, sem exceção** (CA-095, Anti-SPEC §10.2.8). Não é anotação opcional: a
   grade é verificada antes de desenhar (`exigir_grade_completa`) e a célula sem `n` é erro, não
   espaço em branco. `n` varia por ativo dentro da mesma coluna (`IFIX` 2011+, `ICON` 2007+,
   `IMOB` 2008+ — **CA-093**), e é isso que o `n` por célula torna visível.
4. **Três estados de confiança, cada um em dois canais.**
   - `n >= 8`: cor divergente + número em destaque.
   - `5 <= n < 8` (`alerta_n_baixo`, CA-096/CA-108): a cor fica, mais **borda tracejada** e um
     **asterisco** no número. Dois canais além da cor.
   - `n < 5` (`conclusao_suprimida`, CA-109): a célula **perde a cor divergente** — vira cinza
     hachurado — e o número **sai de destaque**, rebaixado a `prelim. x,x`. Perder o canal de
     magnitude é o ponto: a célula não pode ser lida como afirmação, e o número continua ali para
     quem quiser conferir.
5. **Linhas agrupadas por classe, em ordem fixa declarada** (`GRUPOS`), com vão entre grupos e
   título de grupo à esquerda. A ordem **nunca** é por ranking: ordenar por desempenho mudaria a
   posição de cada linha a cada rodada e destruiria a comparação entre figuras.
6. **`CDI` é a última linha** e é identicamente zero — o *sanity check* visual da própria métrica
   (ADR-002 §"Consequências"). Se a linha do CDI não sair cinza-neutra em todas as colunas, o
   excesso sobre CDI está errado em algum lugar.
7. **Tooltip textual no SVG** (`<title>` por célula): erro-padrão da média, `hit_ratio_cdi`,
   mediana, `pior_tri` e as flags. É o que não cabe na célula sem poluí-la, e no PNG não existe —
   por isso o SVG é o artefato de conferência.

## Honestidade estatística (Anti-SPEC §10.2)

- **Descritivo, nunca preditivo** (§10.2.10): todo texto fala no passado ("rendeu", "performou").
  Há teste que varre **todos** os textos da figura procurando vocabulário de projeção.
- **`n` em toda célula e nenhuma conclusão com `n < 5`** (§10.2.8, CA-109).
- **Excesso sobre CDI por razão, nunca subtração** (§10.2.13/CA-069): a coluna lida é
  `excesso_cdi` de F-022, que já é a média de `(1+r)/(1+cdi)−1`. Esta figura **não recalcula nada**.
- **`asof` sempre rotulada** (§10.2.7): a materialização está no título e no rodapé, e o rodapé da
  vista `asof` repete que a V1 troca de rótulo em 33,33% dos trimestres comparáveis (CA-074) —
  logo não é operacional nessa forma.
- **Erro-padrão no rodapé e no tooltip**: com `n` de 4 a 19 e desvio trimestral de bolsa, o
  erro-padrão da média é de 0,4 a 5 pp. A figura diz isso por escrito; ordenar o topo sem ler essa
  linha é ler ruído.
- **Gate de publicação** (CA-090): `especificacao_congelada=False` ⇒ marca d'água diagonal + linha
  de rodapé `ESPECIFICAÇÃO NÃO CONGELADA — não publicável`. A figura é gerada (desenvolver é
  liberado), mas nasce **não publicável**.
- **`SP500_USD` é retorno em USD** e o excesso dele contra o CDI em BRL mistura moedas. A linha
  fica (é dado real da tabela), com asterisco de moeda no rótulo e nota no rodapé — declarada, não
  escondida nem apagada.

## Determinismo

Nenhum valor sai do relógio. `Figure` instanciada direta (sem `pyplot`, sem estado global),
backend `Agg`, `svg.hashsalt` fixo, `Date: None` no SVG, `Software` fixo no PNG, e o arco quente da
paleta é **derivado por bisseção de iterações fixas**, não por convergência. Três rodadas no mesmo
checkout produzem os 7 artefatos byte-idênticos.

**Nota de contrato:** `data/canonical/figuras/` é artefato **derivado de figura**, não tabela
canônica — por isso o Parquet de dados plotados não tem schema em `packages/shared/schemas/`
(F-023 é classe B e não acrescenta schema). O contrato das colunas é `COLUNAS_DADOS_PLOTADOS`,
travado por teste, e **todo nome de coluna herdado de `regime_asset_metrics` é literal**, sem
renomeação (Anti-SPEC §10.4.24 em espírito).

Cobre: RF-033 (CA-095, CA-096, CA-097), RF-040 (CA-108/109 na apresentação) · CA-090 como gate ·
e-mail B1-B5, C1 · Anti-SPEC §10.2.7, §10.2.8, §10.2.10, §10.2.13, §10.4.26.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # antes de qualquer import de desenho: nenhuma janela, nenhum backend GUI

import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from apps.analysis.figuras import _comum
from apps.analysis.figuras.timeline_regimes import ler_regimes
from apps.pipeline.canonical.metricas_regime import (
    TABELA_ASOF,
    TABELA_HORIZONTE_CRUZADO,
    TABELA_PRINCIPAL,
    Tabela,
)
from apps.pipeline.canonical.regimes_v1 import (
    Materializacao,
    alerta_n_baixo,
    conclusao_suprimida,
    especificacao_esta_congelada,
    veredito_publicacao,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, garantir_diretorio, raiz_repo
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from packages.shared.schemas.asset_returns_quarterly import RegimeAssetMetricsSchema
from packages.shared.schemas.regimes import RegimeV1, StatusRegimeV1

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

    from matplotlib.axes import Axes

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Vistas: uma figura por tabela de F-022
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Vista:
    """Uma figura: de qual tabela de F-022 ela sai e como se chama em disco."""

    slug: str
    tabela: Tabela
    titulo: str
    #: O que o rodapé precisa dizer **só** nesta vista (ex.: o achado de CA-074 na `asof`).
    ressalva: str


VISTA_PRINCIPAL = Vista(
    slug="v1_revised",
    tabela=TABELA_PRINCIPAL,
    titulo="V1 revised (T0) + V3 vizinhos (T+1)",
    ressalva=(
        "Materializacao `revised`: legitima para descricao historica e sempre rotulada "
        "(Anti-SPEC 10.2.7). A V1 revised NAO tem quadrante para 2026Q3 (D-m, ibcbr_gap "
        "ausente) - nenhum foi estimado no lugar."
    ),
)

VISTA_ASOF = Vista(
    slug="v1_asof",
    tabela=TABELA_ASOF,
    titulo="V1 asof (T0) — a leitura operacional",
    ressalva=(
        "ATENCAO (CA-074): a V1 troca de rotulo entre `revised` e `asof` em 22 dos 66 trimestres "
        "comparaveis (33,33% > 25%). Pelo criterio escrito, a V1 NAO e operacional na forma "
        "`asof`; esta figura existe para o Comite ver a alternativa, nao como a resposta."
    ),
)

VISTA_HORIZONTE_CRUZADO = Vista(
    slug="v3_t1",
    tabela=TABELA_HORIZONTE_CRUZADO,
    titulo="horizonte cruzado — V1 em T+1, V3 contemporânea (T0)",
    ressalva=(
        "Vista de CONTROLE: cruza os horizontes para isolar o efeito do HORIZONTE do efeito da "
        "LENTE. O slug do arquivo (`v3_t1`) vem do briefing de F-023 e e enganoso - aqui a V3 e "
        "medida em T0; o horizonte correto de cada coluna esta no cabecalho dela."
    ),
)

VISTAS: dict[str, Vista] = {
    v.slug: v for v in (VISTA_PRINCIPAL, VISTA_ASOF, VISTA_HORIZONTE_CRUZADO)
}

NOME_DADOS_PLOTADOS = "heatmap_dados.parquet"

#: Os módulos que determinam o conteúdo da figura, **nesta ordem** — base de `versao_build`.
#: `metricas_regime` entra porque os nomes das tabelas, dos horizontes e os limiares de `n` moram
#: lá; o schema entra porque a lista de ativos e o contrato das colunas moram nele.
MODULOS_DO_HEATMAP: tuple[str, ...] = (
    "apps.analysis.figuras.heatmap_regime_ativo",
    "apps.analysis.figuras._comum",
    "apps.pipeline.canonical.metricas_regime",
    "packages.shared.schemas.asset_returns_quarterly",
)

#: Semente fixa dos `id` do SVG: sem ela o SVG muda de bytes entre processos (determinismo).
SALGA_SVG = "ldc-f023-heatmap-regime-ativo"

# ─────────────────────────────────────────────────────────────────────────────
# As linhas: 24 ativos, agrupados por classe, em ordem **declarada**
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Grupo:
    """Um bloco de linhas do heatmap — uma classe de ativo."""

    nome: str
    ativos: tuple[str, ...]


#: A ordem das linhas. **Nunca por ranking** — por classe, e dentro da classe por duração/porte,
#: que é a ordem que o Comitê usa para falar de carteira. `CDI` fecha a figura porque é a
#: referência da métrica: a linha dele tem de sair identicamente zero (ADR-002).
GRUPOS: tuple[Grupo, ...] = (
    Grupo(
        "Renda fixa — indices ANBIMA",
        ("IMAS", "IMAGERAL", "IRFM1", "IRFM1P", "IRFM", "IMAB5", "IMAB5P", "IMAB"),
    ),
    Grupo("Acoes — indices amplos", ("IBOV", "IDIV", "SMLL")),
    Grupo("Acoes — setoriais B3", ("INDX", "ICON", "IMAT", "IEEX", "IMOB", "IFNC", "UTIL")),
    Grupo("Fundos imobiliarios", ("IFIX",)),
    Grupo("Internacional (em BRL)", ("SP500_BRL", "ACWI_BRL", "SP500_USD")),
    Grupo("Cambio", ("USDBRL",)),
    Grupo("Referencia da metrica", ("CDI",)),
)

ORDEM_DOS_ATIVOS: tuple[str, ...] = tuple(ativo for grupo in GRUPOS for ativo in grupo.ativos)

#: Ativos cuja unidade **não** é retorno em BRL: o excesso contra o CDI em BRL mistura moedas.
#: Ficam na figura (é dado real), marcados, nunca apagados em silêncio.
ATIVOS_FORA_DA_MOEDA: tuple[str, ...] = ("SP500_USD",)
MARCA_MOEDA = " ‡"

#: Rótulo legível de cada regime da V1 — na ordem de declaração do enum, igual a F-025.
ROTULO_DO_REGIME_V1: dict[str, str] = {
    RegimeV1.RECUPERACAO.value: "RECUPERACAO\n(↑g, ↓π)",
    RegimeV1.EXPANSAO_INFL.value: "EXPANSAO_INFL\n(↑g, ↑π)",
    RegimeV1.ESTAGFLACAO.value: "ESTAGFLACAO\n(↓g, ↑π)",
    RegimeV1.DESACELERACAO.value: "DESACELERACAO\n(↓g, ↓π)",
}

LENTE_V1 = "V1"
LENTE_V3 = "V3"

# ─────────────────────────────────────────────────────────────────────────────
# Geometria — tudo em fração da figura, numa só lista, para que nada colida
# ─────────────────────────────────────────────────────────────────────────────

FIGSIZE: tuple[float, float] = (13.8, 15.4)

#: Vão vertical entre grupos, em "alturas de linha".
VAO_ENTRE_GRUPOS = 0.95
#: Recuo de cada célula dentro do seu slot — é o vão de superfície entre preenchimentos vizinhos
#: que a `dataviz` pede ("2px surface gap between fills").
RECUO_X = 0.006
RECUO_Y = 0.055

MARGEM_ESQUERDA = 0.035
X_GRADE_ESQUERDA = 0.175
X_GRADE_DIREITA = 0.988
Y_GRADE_TOPO = 0.885
Y_GRADE_BASE = 0.268
Y_TOPO_DA_LEGENDA = 0.219
Y_TOPO_DO_RODAPE = 0.168
ENTRELINHA_RODAPE = 0.0112

#: `x` (fração do eixo) do título de grupo — alinhado à margem esquerda da figura, não ao rótulo
#: do ativo: nome de classe é longo e encostaria na borda se fosse alinhado à direita.
X_ROTULO_DE_GRUPO = (MARGEM_ESQUERDA - X_GRADE_ESQUERDA) / (X_GRADE_DIREITA - X_GRADE_ESQUERDA)

FONTE_VALOR = 10.0
FONTE_N = 7.2
FONTE_PRELIM = 7.0
FONTE_ROTULO_LINHA = 8.6
FONTE_ROTULO_GRUPO = 8.0
FONTE_CABECALHO = 9.0

#: Largura da borda tracejada de `alerta_n_baixo`.
LARGURA_BORDA_ALERTA = 1.4
MARCA_ALERTA = "*"
PREFIXO_PRELIMINAR = "prelim."

LEITURA_DESCRITIVA = (
    "Leitura descritiva: quanto cada ativo rendeu acima (azul) ou abaixo (vermelho) do CDI nos "
    "trimestres daquele regime. Nada aqui e projecao (Anti-SPEC 10.2.10)."
)

NOME_DA_METRICA = "excesso sobre CDI medio trimestral"
"""CA-097: a métrica é **nomeada**, não insinuada."""

#: Construções **afirmativamente** preditivas — nenhuma pode aparecer em texto da figura
#: (§10.2.10). A lista é de frases, não de radicais: a própria figura diz "Nada aqui e projecao",
#: e banir o radical `projec` proibiria a ressalva junto com o que ela ressalva.
VOCABULARIO_PREDITIVO: tuple[str, ...] = (
    "vai render",
    "vai subir",
    "vai cair",
    "deve render",
    "deve subir",
    "deve cair",
    "retorno esperado",
    "esperado para",
    "previsao de",
    "projecao de",
    "projetamos",
    "estimamos",
    "recomenda",
    "tende a",
    "e o melhor",
)

# ─────────────────────────────────────────────────────────────────────────────
# O contrato de colunas dos dados plotados
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
    "erro_padrao_media",
    "hit_ratio_cdi",
    "sharpe_tri",
    "pior_tri",
    "pior_tri_quarter",
    "alerta_n_baixo",
    "conclusao_suprimida",
    "data_inicio_serie",
    "fonte_versao",
)

#: O contrato completo do Parquet de dados plotados, **nesta ordem**.
COLUNAS_DADOS_PLOTADOS: tuple[str, ...] = (
    "vista",
    "tabela",
    "materializacao",
    "horizonte",
    *COLUNAS_HERDADAS_DE_METRICAS,
    "grupo",
    "linha",
    "coluna",
    "y_centro",
    "cor_hex",
    "hachura",
    "borda",
    "tinta_do_texto",
    "rotulo_valor",
    "rotulo_n",
    "gid",
    "tooltip",
)


@dataclass(frozen=True, slots=True)
class ColunaDoHeatmap:
    """Uma coluna da figura: uma `(lente, regime)` com o horizonte em que foi medida."""

    lente: str
    regime: str
    horizonte: str
    #: Nº de trimestres do regime (da fonte do regime, não do `n` de um ativo).
    trimestres_no_regime: int | None

    @property
    def rotulo(self) -> str:
        """O cabeçalho da coluna, em 1 ou 2 linhas."""
        if self.lente == LENTE_V1:
            return ROTULO_DO_REGIME_V1.get(self.regime, self.regime)
        return self.regime.replace("_", "\n")


@dataclass(frozen=True, slots=True)
class ResultadoHeatmap:
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
    """`sha256` do conjunto `MODULOS_DO_HEATMAP` — o `versao_build` do rodapé (RF-047/CA-121)."""
    return _comum.versao_build(modulos or MODULOS_DO_HEATMAP)


def ler_metricas(vista: Vista, *, raiz: Path | None = None) -> pd.DataFrame:
    """Lê e **valida** a tabela da vista com `RegimeAssetMetricsSchema`. Ausente = falha."""
    alvo = caminho_canonical(vista.tabela.nome_arquivo, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.metricas_regime --offline`."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        validado = RegimeAssetMetricsSchema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz regime_asset_metrics: {erro}"
        raise SerieInconsistente(msg) from erro
    return (
        pd.DataFrame(validado)
        .sort_values(["lente", "regime", "asset_id"], kind="stable")
        .reset_index(drop=True)
    )


def janela_e_trimestres_por_regime(
    materializacao: Materializacao | str, *, raiz: Path | None = None
) -> tuple[tuple[str, str], dict[str, int]]:
    """`(primeiro, último)` trimestre e quantos trimestres cada quadrante V1 tem.

    Vem de `regimes_v1{,_asof}.parquet` pela função **importada** de F-025 (que já valida com
    `RegimesV1Schema`) — a figura não reconta regime nenhum.
    """
    regimes = ler_regimes(materializacao, raiz=raiz)
    quarters = [str(q) for q in regimes["quarter"]]
    classificados = regimes[regimes["status_regime_v1"] == StatusRegimeV1.CLASSIFICADO.value]
    contagem = {
        str(rotulo): int(n) for rotulo, n in classificados["regime_v1"].value_counts().items()
    }
    return (quarters[0], quarters[-1]), contagem


# ─────────────────────────────────────────────────────────────────────────────
# A função pura: os dados exatamente como vão ser plotados
# ─────────────────────────────────────────────────────────────────────────────


def ordem_das_colunas(
    metricas: pd.DataFrame,
    vista: Vista,
    trimestres_por_regime: Mapping[str, int] | None = None,
) -> tuple[ColunaDoHeatmap, ...]:
    """As colunas, **na ordem de declaração do enum `RegimeV1`**, e a V3 depois delas.

    A ordem é do contrato, não do dado: assim duas vistas da mesma lente ficam comparáveis coluna
    a coluna, e um regime que desaparecesse da tabela apareceria como coluna faltante (erro), não
    como reordenação silenciosa.
    """
    contagem = dict(trimestres_por_regime or {})
    presentes = set(zip(metricas["lente"], metricas["regime"], strict=True))
    colunas: list[ColunaDoHeatmap] = [
        ColunaDoHeatmap(
            lente=LENTE_V1,
            regime=rotulo.value,
            horizonte=vista.tabela.horizonte_v1.value,
            trimestres_no_regime=contagem.get(rotulo.value),
        )
        for rotulo in RegimeV1
        if (LENTE_V1, rotulo.value) in presentes
    ]
    if vista.tabela.horizonte_v3 is not None:
        regimes_v3 = sorted({r for lente, r in presentes if lente == LENTE_V3})
        colunas += [
            ColunaDoHeatmap(
                lente=LENTE_V3,
                regime=regime,
                horizonte=vista.tabela.horizonte_v3.value,
                trimestres_no_regime=None,
            )
            for regime in regimes_v3
        ]
    if not colunas:
        msg = f"nenhuma coluna para a vista {vista.slug!r}: a tabela não tem lente V1 nem V3"
        raise SerieInconsistente(msg)
    return tuple(colunas)


def posicoes_das_linhas(grupos: Sequence[Grupo] = GRUPOS) -> dict[str, float]:
    """`asset_id -> centro da linha`, em "alturas de linha" contadas do topo, com vão entre grupos.

    O vão não é decoração: é o que separa dois preenchimentos vizinhos de classes diferentes e o
    que dá lugar ao título do grupo sem empurrar rótulo para cima de célula.
    """
    posicoes: dict[str, float] = {}
    cursor = 0.0
    for ordem, grupo in enumerate(grupos):
        if ordem:
            cursor += VAO_ENTRE_GRUPOS
        for ativo in grupo.ativos:
            posicoes[ativo] = cursor + 0.5
            cursor += 1.0
    return posicoes


def altura_total(grupos: Sequence[Grupo] = GRUPOS) -> float:
    """Altura da grade em "alturas de linha", vãos incluídos."""
    linhas = sum(len(g.ativos) for g in grupos)
    return linhas + VAO_ENTRE_GRUPOS * (len(grupos) - 1)


def extremo_simetrico(valores: Sequence[float]) -> float:
    """O `|v|` máximo arredondado para cima no 0,5 pp — o fim dos dois arcos da escala.

    Arredondar para cima (e não usar o máximo cru) faz a escala não se mexer por causa do último
    dígito de uma célula, e deixa a legenda com números redondos.
    """
    finitos = [abs(float(v)) for v in valores if pd.notna(v)]
    if not finitos:
        msg = "nenhum valor finito de excesso_cdi para dimensionar a escala"
        raise SerieInconsistente(msg)
    bruto = max(finitos)
    passo = 0.005
    return max(passo, (int(bruto / passo) + 1) * passo)


def _virgula(valor: float, casas: int = 2) -> str:
    """Número em pt-BR (vírgula decimal) — o rodapé é lido por humano brasileiro."""
    return f"{valor:.{casas}f}".replace(".", ",")


def _formatar_pct(valor: float, *, com_sinal: bool = True) -> str:
    """Fração → `+8,2` (pt-BR, uma decimal). É o número que a célula mostra."""
    texto = f"{valor * 100:+.1f}" if com_sinal else f"{valor * 100:.1f}"
    return texto.replace(".", ",")


def _tooltip_da_celula(linha: Mapping[str, Any], coluna: ColunaDoHeatmap) -> str:
    """O texto do `<title>` do SVG: o que não cabe na célula mas decide a leitura dela."""
    partes = [
        f"{linha['asset_id']} | {coluna.lente} {coluna.regime} (horizonte {coluna.horizonte})",
        f"{NOME_DA_METRICA}: {_formatar_pct(float(linha['excesso_cdi']))}%",
        f"n = {int(linha['n_obs'])}",
    ]
    erro = linha["erro_padrao_media"]
    if pd.notna(erro):
        partes.append(f"erro-padrao da media: {_formatar_pct(float(erro), com_sinal=False)} pp")
    if pd.notna(linha["hit_ratio_cdi"]):
        partes.append(
            f"hit_ratio_cdi: {_formatar_pct(float(linha['hit_ratio_cdi']), com_sinal=False)}% "
            f"dos trimestres bateram o CDI"
        )
    for rotulo, chave in (
        ("mediana do retorno", "ret_mediana"),
        ("pior trimestre", "pior_tri"),
    ):
        valor = linha[chave]
        if pd.notna(valor):
            partes.append(f"{rotulo}: {_formatar_pct(float(valor))}%")
    if pd.notna(linha["pior_tri_quarter"]):
        partes.append(f"pior trimestre em {linha['pior_tri_quarter']}")
    if bool(linha["conclusao_suprimida"]):
        partes.append("CONCLUSAO SUPRIMIDA (n < 5, CA-109): indicacao preliminar")
    elif bool(linha["alerta_n_baixo"]):
        partes.append("ALERTA_N_BAIXO (n < 8, CA-108)")
    partes.append(f"serie comeca em {pd.Timestamp(linha['data_inicio_serie']).date()}")
    return " | ".join(partes)


def dados_plotados(
    metricas: pd.DataFrame,
    *,
    vista: Vista,
    trimestres_por_regime: Mapping[str, int] | None = None,
    extremo: float | None = None,
) -> pd.DataFrame:
    """**A função pura da feature**: o DataFrame que a figura desenha, e nada mais.

    Uma linha por `(asset_id, coluna)`. As colunas de métrica são as de `regime_asset_metrics`,
    com o **mesmo nome**; o que se acrescenta é a posição na grade, a cor/hachura/borda que o
    desenho vai usar, os dois rótulos de texto e o tooltip.

    Nada é recalculado: `excesso_cdi`, `n_obs` e as duas flags vêm da tabela. As flags são
    **reconferidas** contra `alerta_n_baixo(n)`/`conclusao_suprimida(n)` de F-019 e a divergência é
    erro — é o que impede a figura de hachurar por conta própria ou de deixar de hachurar.
    """
    colunas = ordem_das_colunas(metricas, vista, trimestres_por_regime)
    posicoes = posicoes_das_linhas()
    indexado = metricas.set_index(["lente", "regime", "asset_id"], drop=False)
    valores = [
        float(v)
        for v in metricas.loc[metricas["asset_id"].isin(ORDEM_DOS_ATIVOS), "excesso_cdi"]
        if pd.notna(v)
    ]
    escala = extremo if extremo is not None else extremo_simetrico(valores)
    mapa = _comum.mapa_divergente()
    norma = _comum.normalizacao_centrada_em_zero(escala)

    registros: list[dict[str, Any]] = []
    for grupo in GRUPOS:
        for ativo in grupo.ativos:
            for indice_coluna, coluna in enumerate(colunas):
                chave = (coluna.lente, coluna.regime, ativo)
                if chave not in indexado.index:
                    msg = (
                        f"grade incompleta: {ativo} não tem célula em "
                        f"{coluna.lente}/{coluna.regime} na tabela {vista.tabela.nome_arquivo} "
                        f"(CA-095: toda célula exibe n)"
                    )
                    raise SerieInconsistente(msg)
                linha = indexado.loc[chave]
                registros.append(
                    _registro_da_celula(
                        linha,
                        vista=vista,
                        grupo=grupo,
                        coluna=coluna,
                        indice_coluna=indice_coluna,
                        y_centro=posicoes[ativo],
                        mapa=mapa,
                        norma=norma,
                    )
                )

    saida = pd.DataFrame.from_records(registros)
    saida["linha"] = [ORDEM_DOS_ATIVOS.index(a) for a in saida["asset_id"]]
    saida = saida.sort_values(["linha", "coluna"], kind="stable").reset_index(drop=True)
    return saida[list(COLUNAS_DADOS_PLOTADOS)]


def _registro_da_celula(
    linha: pd.Series,
    *,
    vista: Vista,
    grupo: Grupo,
    coluna: ColunaDoHeatmap,
    indice_coluna: int,
    y_centro: float,
    mapa: Any,
    norma: Any,
) -> dict[str, Any]:
    """Uma célula: o que veio da tabela + como ela vai ser pintada e escrita."""
    n = int(linha["n_obs"])
    suprimida = bool(linha["conclusao_suprimida"])
    alerta = bool(linha["alerta_n_baixo"])
    if (alerta, suprimida) != (alerta_n_baixo(n), conclusao_suprimida(n)):
        msg = (
            f"flags de {linha['asset_id']} em {coluna.lente}/{coluna.regime} não batem com n={n}: "
            f"tabela diz alerta={alerta}/suprimida={suprimida}, os limiares de F-019 dizem "
            f"{alerta_n_baixo(n)}/{conclusao_suprimida(n)}"
        )
        raise SerieInconsistente(msg)

    excesso = linha["excesso_cdi"]
    if pd.isna(excesso):
        msg = (
            f"excesso_cdi nulo em {linha['asset_id']} / {coluna.lente} {coluna.regime} com "
            f"n={n}: a figura não inventa cor nem número (Anti-SPEC §10.1.1)"
        )
        raise SerieInconsistente(msg)

    if suprimida:
        cor = _comum.CINZA_SUPRIMIDO
        hachura = _comum.HACHURA_SUPRIMIDO
        rotulo_valor = f"{PREFIXO_PRELIMINAR} {_formatar_pct(float(excesso))}"
    else:
        cor = matplotlib.colors.to_hex(mapa(norma(float(excesso))))
        hachura = ""
        rotulo_valor = _formatar_pct(float(excesso)) + (MARCA_ALERTA if alerta else "")

    registro: dict[str, Any] = {chave: linha[chave] for chave in COLUNAS_HERDADAS_DE_METRICAS}
    registro.update(
        vista=vista.slug,
        tabela=vista.tabela.nome_arquivo,
        materializacao=vista.tabela.materializacao.value,
        horizonte=coluna.horizonte,
        grupo=grupo.nome,
        coluna=indice_coluna,
        y_centro=float(y_centro),
        cor_hex=cor,
        hachura=hachura,
        borda=(alerta and not suprimida),
        tinta_do_texto=_comum.tinta_legivel_sobre(cor),
        rotulo_valor=rotulo_valor,
        rotulo_n=f"n={n}" + (f" {MARCA_ALERTA}" if alerta and not suprimida else ""),
        gid=f"celula-{linha['asset_id']}-{coluna.lente}-{coluna.regime}",
        tooltip=_tooltip_da_celula(linha, coluna),
    )
    return registro


def exigir_grade_completa(
    dados: pd.DataFrame,
    *,
    n_colunas: int,
    ativos: Sequence[str] = ORDEM_DOS_ATIVOS,
) -> None:
    """**CA-095 em código:** a grade é `ativos × colunas` cheia e **toda** célula tem `n`.

    Célula faltando apareceria como superfície branca e seria lida como "não houve"; célula sem
    `n` seria uma afirmação sem amostra. Nenhuma das duas pode sair daqui.
    """
    esperado = len(ativos) * n_colunas
    if len(dados) != esperado:
        msg = f"grade tem {len(dados)} células, esperado {len(ativos)} x {n_colunas} = {esperado}"
        raise SerieInconsistente(msg)
    if set(dados["asset_id"]) != set(ativos):
        faltando = sorted(set(ativos) - set(dados["asset_id"]))
        sobrando = sorted(set(dados["asset_id"]) - set(ativos))
        msg = f"ativos fora da grade declarada: faltando {faltando}, sobrando {sobrando}"
        raise SerieInconsistente(msg)
    sem_n = dados[dados["rotulo_n"].isna() | (dados["rotulo_n"].astype(str) == "")]
    if not sem_n.empty:
        msg = f"{len(sem_n)} células sem anotação de n (CA-095)"
        raise SerieInconsistente(msg)
    if dados["n_obs"].isna().any():
        msg = "n_obs nulo em alguma célula — CA-095 proíbe célula sem n"
        raise SerieInconsistente(msg)


def contagem_de_flags(dados: pd.DataFrame) -> dict[str, int]:
    """Quantas células em cada estado de confiança — o que vai à legenda e ao relatório."""
    suprimidas = int(dados["conclusao_suprimida"].sum())
    alertas = int(dados["alerta_n_baixo"].sum())
    return {
        "celulas": int(len(dados)),
        "plenas": int(len(dados)) - alertas,
        "alerta_n_baixo": alertas - suprimidas,
        "conclusao_suprimida": suprimidas,
    }


def inicio_das_series(dados: pd.DataFrame) -> dict[str, str]:
    """`asset_id -> data_inicio_serie` em ISO, na ordem das linhas — o rodapé de CA-097."""
    por_ativo = dados.groupby("asset_id")["data_inicio_serie"].first()
    return {
        ativo: str(pd.Timestamp(por_ativo[ativo]).date())
        for ativo in ORDEM_DOS_ATIVOS
        if ativo in por_ativo.index
    }


# ─────────────────────────────────────────────────────────────────────────────
# O desenho
# ─────────────────────────────────────────────────────────────────────────────


def _pintar_celulas(eixo: Axes, dados: pd.DataFrame) -> None:
    """Uma `Rectangle` por célula + o valor e o `n` dentro dela."""
    for _, linha in dados.iterrows():
        x0 = float(linha["coluna"]) + RECUO_X
        y0 = float(linha["y_centro"]) - 0.5 + RECUO_Y
        suprimida = bool(linha["conclusao_suprimida"])
        retangulo = Rectangle(
            (x0, y0),
            1.0 - 2 * RECUO_X,
            1.0 - 2 * RECUO_Y,
            facecolor=str(linha["cor_hex"]),
            hatch=str(linha["hachura"]) or None,
            edgecolor=(
                _comum.TINTA_MUTED
                if suprimida
                else (_comum.TINTA_SECUNDARIA if bool(linha["borda"]) else "none")
            ),
            linewidth=LARGURA_BORDA_ALERTA if (suprimida or bool(linha["borda"])) else 0.0,
            linestyle=(0, (2.4, 1.6)) if bool(linha["borda"]) else "solid",
            zorder=2,
        )
        retangulo.set_gid(str(linha["gid"]))
        eixo.add_patch(retangulo)

        centro_x = float(linha["coluna"]) + 0.5
        tinta = str(linha["tinta_do_texto"])
        eixo.text(
            centro_x,
            float(linha["y_centro"]) - 0.12,
            str(linha["rotulo_valor"]),
            ha="center",
            va="center",
            fontsize=FONTE_PRELIM if suprimida else FONTE_VALOR,
            fontweight="normal" if suprimida else "bold",
            fontstyle="italic" if suprimida else "normal",
            color=_comum.TINTA_SECUNDARIA if suprimida else tinta,
            zorder=3,
        )
        eixo.text(
            centro_x,
            float(linha["y_centro"]) + 0.26,
            str(linha["rotulo_n"]),
            ha="center",
            va="center",
            fontsize=FONTE_N,
            color=_comum.TINTA_SECUNDARIA if suprimida else tinta,
            zorder=3,
        )


def _rotulos_das_linhas(eixo: Axes) -> None:
    """Nome do ativo à esquerda de cada linha + título de cada grupo no vão acima dele."""
    posicoes = posicoes_das_linhas()
    for grupo in GRUPOS:
        topo = min(posicoes[a] for a in grupo.ativos) - 0.5
        eixo.text(
            X_ROTULO_DE_GRUPO,
            topo - 0.33,
            grupo.nome.upper(),
            transform=eixo.get_yaxis_transform(),
            ha="left",
            va="center",
            fontsize=FONTE_ROTULO_GRUPO,
            fontweight="bold",
            color=_comum.TINTA_SECUNDARIA,
            clip_on=False,
        )
        for ativo in grupo.ativos:
            sufixo = MARCA_MOEDA if ativo in ATIVOS_FORA_DA_MOEDA else ""
            eixo.text(
                -0.012,
                posicoes[ativo],
                f"{ativo}{sufixo}",
                transform=eixo.get_yaxis_transform(),
                ha="right",
                va="center",
                fontsize=FONTE_ROTULO_LINHA,
                color=_comum.TINTA_PRIMARIA,
                clip_on=False,
            )


def _cabecalho_das_colunas(eixo: Axes, colunas: Sequence[ColunaDoHeatmap]) -> None:
    """Cabeçalho de cada coluna: regime, lente + horizonte e quantos trimestres o regime tem."""
    for indice, coluna in enumerate(colunas):
        eixo.text(
            indice + 0.5,
            1.016,
            coluna.rotulo,
            transform=eixo.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=FONTE_CABECALHO,
            fontweight="bold",
            color=_comum.TINTA_PRIMARIA,
            clip_on=False,
        )
        detalhe = f"lente {coluna.lente} · horizonte {coluna.horizonte}"
        if coluna.trimestres_no_regime is not None:
            detalhe += f" · {coluna.trimestres_no_regime} trimestres"
        eixo.text(
            indice + 0.5,
            1.004,
            detalhe,
            transform=eixo.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=7.2,
            color=_comum.TINTA_MUTED,
            clip_on=False,
        )


def _legenda_de_escala(figura: Figure, *, extremo: float, contagem: Mapping[str, int]) -> None:
    """Barra da escala divergente (com o zero nomeado) + as três classes de confiança, com `n`."""
    eixo = figura.add_axes((MARGEM_ESQUERDA, Y_TOPO_DA_LEGENDA - 0.016, 0.26, 0.012))
    mapeavel = ScalarMappable(
        norm=_comum.normalizacao_centrada_em_zero(extremo), cmap=_comum.mapa_divergente()
    )
    barra = figura.colorbar(mapeavel, cax=eixo, orientation="horizontal")
    marcas = [-extremo, -extremo / 2, 0.0, extremo / 2, extremo]
    barra.set_ticks(marcas)
    barra.set_ticklabels([_formatar_pct(m) + "%" for m in marcas])
    barra.outline.set_visible(False)
    barra.ax.tick_params(colors=_comum.TINTA_MUTED, labelsize=7.2, length=2)
    figura.text(
        MARGEM_ESQUERDA,
        Y_TOPO_DA_LEGENDA + 0.004,
        f"{NOME_DA_METRICA} (pontos percentuais por trimestre) — zero = empatou com o CDI",
        ha="left",
        va="bottom",
        fontsize=7.6,
        color=_comum.TINTA_SECUNDARIA,
    )

    alcas = [
        Patch(
            facecolor=_comum.ARCO_FRIO[1],
            edgecolor=_comum.SUPERFICIE,
            label=f"n >= 8 — numero em destaque (n={contagem['plenas']} celulas)",
        ),
        Patch(
            facecolor=_comum.ARCO_FRIO[1],
            edgecolor=_comum.TINTA_SECUNDARIA,
            linestyle="--",
            linewidth=LARGURA_BORDA_ALERTA,
            label=(
                f"5 <= n < 8 — ALERTA_N_BAIXO, borda tracejada + {MARCA_ALERTA} "
                f"(n={contagem['alerta_n_baixo']})"
            ),
        ),
        Patch(
            facecolor=_comum.CINZA_SUPRIMIDO,
            edgecolor=_comum.TINTA_MUTED,
            hatch=_comum.HACHURA_SUPRIMIDO,
            label=(
                f"n < 5 — sem conclusao, cinza hachurado e '{PREFIXO_PRELIMINAR}' "
                f"(n={contagem['conclusao_suprimida']})"
            ),
        ),
        Line2D(
            [],
            [],
            linestyle="none",
            marker="$‡$",
            markersize=8,
            color=_comum.TINTA_SECUNDARIA,
            label="retorno em moeda estrangeira (ver rodape)",
        ),
    ]
    figura.legend(
        handles=alcas,
        loc="upper left",
        bbox_to_anchor=(0.34, Y_TOPO_DA_LEGENDA + 0.012),
        ncols=1,
        frameon=False,
        fontsize=8,
        labelcolor=_comum.TINTA_SECUNDARIA,
        handlelength=1.8,
        labelspacing=0.5,
    )


def _linhas_do_rodape(
    dados: pd.DataFrame,
    *,
    vista: Vista,
    versao: str,
    hashes_dos_insumos: Mapping[str, str],
) -> list[str]:
    """O rodapé de CA-097: a métrica nomeada, `data_inicio` de **cada** série e a procedência."""
    inicios = inicio_das_series(dados)
    erros = [float(e) * 100 for e in dados["erro_padrao_media"] if pd.notna(e)]
    faixa_erro = (
        f"erro-padrao da media nesta figura: de {_virgula(min(erros))} a {_virgula(max(erros))} "
        f"pp por trimestre - diferencas menores que ~2 erros-padrao nao sao ruido distinguivel"
        if erros
        else "erro-padrao da media indisponivel (n < 2 em toda celula)"
    )
    procedencias = [f"{nome} {h[:12]}" for nome, h in sorted(hashes_dos_insumos.items())]
    pares = [f"{ativo} {data}" for ativo, data in inicios.items()]
    por_linha = 8
    blocos = [
        "    " + " · ".join(pares[i : i + por_linha]) for i in range(0, len(pares), por_linha)
    ]
    linhas = [
        f"Metrica: {NOME_DA_METRICA} = media de (1+r_ativo)/(1+r_cdi)-1 nos trimestres do regime "
        f"(razao, nunca subtracao - CA-069/Anti-SPEC 10.2.13). ADR-002/D5 PROVISORIO.",
        f"n em toda celula (CA-095). Borda tracejada + {MARCA_ALERTA} = ALERTA_N_BAIXO, n < 8 "
        f"(CA-096/CA-108). Cinza hachurado + '{PREFIXO_PRELIMINAR}' = n < 5, nenhuma conclusao "
        f"afirmativa (CA-109). n por celula pode ser menor que o do regime: janela propria do "
        f"ativo (CA-093).",
        faixa_erro,
        vista.ressalva,
        f"‡ {', '.join(ATIVOS_FORA_DA_MOEDA)}: retorno em USD. O excesso contra o CDI em BRL "
        f"mistura moedas - a linha fica porque e dado real da tabela, declarada e nao apagada.",
        f"data_inicio de cada serie (CA-097), {len(inicios)} ativos:",
        *blocos,
        f"versao_build {versao[:12]} | sha256 dos insumos lidos nesta rodada:",
        *["    " + " · ".join(procedencias[i : i + 3]) for i in range(0, len(procedencias), 3)],
        f"Fonte: data/canonical/{vista.tabela.nome_arquivo} (F-022) + "
        f"regimes_v1{'_asof' if vista.tabela.materializacao is Materializacao.ASOF else ''}"
        f".parquet (F-019). fonte_versao das metricas: "
        f"{str(dados['fonte_versao'].iloc[0])[:12]}.",
    ]
    return linhas


def desenhar(
    dados: pd.DataFrame,
    *,
    vista: Vista,
    colunas: Sequence[ColunaDoHeatmap],
    extremo: float,
    janela: tuple[str, str],
    versao: str,
    hashes_dos_insumos: Mapping[str, str],
    congelada: bool,
) -> Figure:
    """Desenha **uma** vista e devolve a `Figure` (nada é gravado aqui).

    Separar desenho de gravação é o que faz o teste poder inspecionar textos, cores, hachuras e
    bordas sem tocar o disco — e o que faz `construir` ser a única função com efeito colateral.
    """
    recorte = dados[dados["vista"] == vista.slug].reset_index(drop=True)
    if recorte.empty:
        msg = f"nenhuma linha da vista {vista.slug!r} nos dados plotados"
        raise SerieInconsistente(msg)
    exigir_grade_completa(recorte, n_colunas=len(colunas))

    figura = Figure(figsize=FIGSIZE, dpi=_comum.DPI_PNG, facecolor=_comum.SUPERFICIE)
    eixo = figura.add_axes(
        (
            X_GRADE_ESQUERDA,
            Y_GRADE_BASE,
            X_GRADE_DIREITA - X_GRADE_ESQUERDA,
            Y_GRADE_TOPO - Y_GRADE_BASE,
        )
    )
    eixo.set_facecolor(_comum.SUPERFICIE)
    eixo.set_xlim(0, len(colunas))
    eixo.set_ylim(altura_total(), 0)
    eixo.set_xticks([])
    eixo.set_yticks([])
    for lado in eixo.spines.values():
        lado.set_visible(False)

    _pintar_celulas(eixo, recorte)
    _rotulos_das_linhas(eixo)
    _cabecalho_das_colunas(eixo, colunas)

    figura.suptitle(
        f"Excesso sobre CDI por regime macro x ativo — {vista.titulo}",
        x=MARGEM_ESQUERDA,
        y=0.982,
        ha="left",
        fontsize=15.5,
        fontweight="bold",
        color=_comum.TINTA_PRIMARIA,
    )
    for ordem, texto in enumerate(
        (
            f"{len(ORDEM_DOS_ATIVOS)} ativos x {len(colunas)} regimes · materializacao "
            f"{vista.tabela.materializacao.value} · janela {janela[0]}-{janela[1]} · escala "
            f"divergente simetrica +/-{_formatar_pct(extremo, com_sinal=False)} pp, centrada em 0",
            LEITURA_DESCRITIVA,
        )
    ):
        figura.text(
            MARGEM_ESQUERDA,
            0.962 - ordem * 0.0165,
            texto,
            ha="left",
            va="top",
            fontsize=9.2,
            color=_comum.TINTA_SECUNDARIA,
        )

    _legenda_de_escala(figura, extremo=extremo, contagem=contagem_de_flags(recorte))
    _comum.desenhar_rodape(
        figura,
        linhas=_linhas_do_rodape(
            recorte, vista=vista, versao=versao, hashes_dos_insumos=hashes_dos_insumos
        ),
        congelada=congelada,
        x=MARGEM_ESQUERDA,
        y_topo=Y_TOPO_DO_RODAPE,
        entrelinha=ENTRELINHA_RODAPE,
    )
    return figura


# ─────────────────────────────────────────────────────────────────────────────
# Gravação
# ─────────────────────────────────────────────────────────────────────────────


def gravar_figura(
    figura: Figure,
    *,
    vista: Vista,
    versao: str,
    tooltips: Mapping[str, str] | None = None,
    raiz: Path | None = None,
) -> dict[str, Path]:
    """Grava PNG + SVG determinísticos e injeta os tooltips textuais no SVG."""
    saidas = _comum.gravar_figura_deterministica(
        figura,
        base_do_nome=f"heatmap_{vista.slug}",
        versao=versao,
        salga_svg=SALGA_SVG,
        identificacao="F-023",
        raiz=raiz,
    )
    if tooltips and "svg" in saidas:
        injetados = _comum.injetar_tooltips_svg(saidas["svg"], tooltips)
        _log.info("tooltips injetados no SVG de %s: %d de %d", vista.slug, injetados, len(tooltips))
    return saidas


def gravar_dados(dados: pd.DataFrame, *, raiz: Path | None = None) -> Path:
    """Grava `heatmap_dados.parquet` — os dados plotados, conferíveis célula a célula."""
    destino = garantir_diretorio(_comum.caminho_figuras(raiz=raiz)) / NOME_DADOS_PLOTADOS
    dados.to_parquet(destino, index=False)
    return destino


def construir(
    *,
    vistas: Sequence[str] | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
) -> ResultadoHeatmap:
    """Lê o canônico, monta os dados plotados, desenha e (opcionalmente) grava.

    `vistas=None` significa **as três**: a principal é o entregável, a `asof` existe para mostrar
    que a troca de 33% de CA-074 não é retórica, e o horizonte cruzado é o controle que separa o
    efeito do horizonte do efeito da lente. Tabela ausente em disco é falha explícita, nunca um
    fallback silencioso para outra vista.
    """
    escolhidas = [VISTAS[s] for s in (vistas or VISTAS)]
    hashes: dict[str, str] = {}
    blocos: list[pd.DataFrame] = []
    contexto: dict[str, dict[str, Any]] = {}

    for vista in escolhidas:
        metricas = ler_metricas(vista, raiz=raiz)
        hashes[vista.tabela.nome_arquivo] = _comum.sha256_do_arquivo(
            caminho_canonical(vista.tabela.nome_arquivo, raiz=raiz)
        )
        janela, trimestres = janela_e_trimestres_por_regime(vista.tabela.materializacao, raiz=raiz)
        nome_regimes = (
            "regimes_v1_asof.parquet"
            if vista.tabela.materializacao is Materializacao.ASOF
            else "regimes_v1.parquet"
        )
        hashes[nome_regimes] = _comum.sha256_do_arquivo(caminho_canonical(nome_regimes, raiz=raiz))
        colunas = ordem_das_colunas(metricas, vista, trimestres)
        bloco = dados_plotados(metricas, vista=vista, trimestres_por_regime=trimestres)
        blocos.append(bloco)
        contexto[vista.slug] = {
            "colunas": colunas,
            "janela": janela,
            "extremo": extremo_simetrico(bloco["excesso_cdi"].tolist()),
        }

    dados = pd.concat(blocos, ignore_index=True)
    versao = versao_build()
    congelada = especificacao_esta_congelada(raiz=raiz)
    if not congelada:
        _log.warning(
            "%s: toda figura desta rodada carrega a marca de CA-090",
            veredito_publicacao(congelada),
        )

    figuras: dict[str, Figure] = {}
    caminhos: dict[str, Path] = {}
    for vista in escolhidas:
        bloco = dados[dados["vista"] == vista.slug].reset_index(drop=True)
        figura = desenhar(
            dados,
            vista=vista,
            colunas=contexto[vista.slug]["colunas"],
            extremo=contexto[vista.slug]["extremo"],
            janela=contexto[vista.slug]["janela"],
            versao=versao,
            hashes_dos_insumos=hashes,
            congelada=congelada,
        )
        figuras[vista.slug] = figura
        if gravar:
            tooltips = dict(zip(bloco["gid"], bloco["tooltip"], strict=True))
            for formato, caminho in gravar_figura(
                figura, vista=vista, versao=versao, tooltips=tooltips, raiz=raiz
            ).items():
                caminhos[f"{vista.slug}.{formato}"] = caminho

    caminho_dados = gravar_dados(dados, raiz=raiz) if gravar else None
    relatorio = montar_relatorio(
        dados,
        versao=versao,
        hashes_dos_insumos=hashes,
        congelada=congelada,
        contexto=contexto,
        caminhos=caminhos,
        caminho_dados=caminho_dados,
    )
    if gravar:
        _log.info(
            "figuras gravadas em %s (%d arquivos, %d celulas plotadas)",
            _comum.caminho_figuras(raiz=raiz),
            len(caminhos),
            len(dados),
        )
    return ResultadoHeatmap(
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
    contexto: Mapping[str, Mapping[str, Any]],
    caminhos: Mapping[str, Path],
    caminho_dados: Path | None,
) -> dict[str, Any]:
    """O que o stdout imprime e o que vai ao relatório do PR — sem nada do relógio."""
    por_vista: dict[str, Any] = {}
    for slug, bloco in dados.groupby("vista", sort=True):
        ctx = contexto.get(str(slug), {})
        extremos = bloco.dropna(subset=["excesso_cdi"]).sort_values("excesso_cdi")
        por_vista[str(slug)] = {
            "tabela": str(bloco["tabela"].iloc[0]),
            "materializacao": str(bloco["materializacao"].iloc[0]),
            "celulas": int(len(bloco)),
            "ativos": int(bloco["asset_id"].nunique()),
            "colunas": [f"{c.lente}/{c.regime} ({c.horizonte})" for c in ctx.get("colunas", ())],
            "janela": list(ctx.get("janela", ())),
            "extremo_da_escala": float(ctx.get("extremo", 0.0)),
            "flags": contagem_de_flags(bloco),
            "n_minimo": int(bloco["n_obs"].min()),
            "n_maximo": int(bloco["n_obs"].max()),
            "tres_maiores": [
                f"{r.asset_id} {r.lente}/{r.regime} {_formatar_pct(r.excesso_cdi)}% n={r.n_obs}"
                for r in extremos.tail(3).iloc[::-1].itertuples()
            ],
            "tres_menores": [
                f"{r.asset_id} {r.lente}/{r.regime} {_formatar_pct(r.excesso_cdi)}% n={r.n_obs}"
                for r in extremos.head(3).itertuples()
            ],
            "celulas_suprimidas": [
                f"{r.asset_id} {r.lente}/{r.regime} n={r.n_obs}"
                for r in bloco[bloco["conclusao_suprimida"]].itertuples()
            ],
        }
    return {
        "feature": "F-023 — heatmap regime x ativo (RF-033, CA-095..097; gate CA-090)",
        "versao_build": versao,
        "hashes_dos_insumos": dict(sorted(hashes_dos_insumos.items())),
        "metrica": {
            "coluna": "excesso_cdi",
            "nome": NOME_DA_METRICA,
            "adr": "ADR-002 (Proposta) — D5 provisorio",
            "unidade": "fracao por trimestre (D-o); a figura exibe em pp",
        },
        "especificacao": {
            "especificacao_congelada": congelada,
            "veredito_publicacao": veredito_publicacao(congelada),
            "marca_na_figura": None if congelada else _comum.MARCA_NAO_CONGELADA,
        },
        "paleta": {
            "arco_negativo": list(_comum.ARCO_QUENTE),
            "neutro": _comum.NEUTRO_DIVERGENTE,
            "arco_positivo": list(_comum.ARCO_FRIO),
            "cinza_suprimido": _comum.CINZA_SUPRIMIDO,
        },
        "ordem_das_linhas": [{"grupo": g.nome, "ativos": list(g.ativos)} for g in GRUPOS],
        "data_inicio_por_serie": inicio_das_series(dados),
        "por_vista": por_vista,
        "arquivos": {chave: str(caminho) for chave, caminho in sorted(caminhos.items())},
        "dados_plotados": str(caminho_dados) if caminho_dados else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

ESCOLHA_TODAS = "todas"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.analysis.figuras.heatmap_regime_ativo",
        description=(
            "Gera data/canonical/figuras/heatmap_{v1_revised,v1_asof,v3_t1}.{png,svg} + o Parquet "
            "dos dados plotados, a partir das 3 tabelas regime_asset_metrics de F-022 e de "
            "regimes_v1 (F-019). Celula = excesso sobre CDI medio trimestral, escala divergente "
            "centrada em 0, n em toda celula. Nunca toca a rede. Enquanto ADR-001 estiver em "
            "Proposta, a figura carrega a marca ESPECIFICACAO NAO CONGELADA (CA-090)."
        ),
    )
    parser.add_argument(
        "--vista",
        choices=[*VISTAS, ESCOLHA_TODAS],
        default=ESCOLHA_TODAS,
        help="v1_revised (principal), v1_asof, v3_t1 (horizonte cruzado) ou todas (default).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = figuras geradas; `1` = falha explícita e nada gravado."""
    args = _parser().parse_args(argv)
    configurar_logging()
    escolhidas = None if args.vista == ESCOLHA_TODAS else [args.vista]
    try:
        resultado = construir(vistas=escolhidas)
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
    print(f"metrica: {relatorio['metrica']['coluna']} ({relatorio['metrica']['nome']})")
    for slug, bloco in relatorio["por_vista"].items():
        print(
            f"{slug}: {bloco['celulas']} celulas = {bloco['ativos']} ativos x "
            f"{len(bloco['colunas'])} colunas | janela {'-'.join(bloco['janela'])} | escala +/-"
            f"{bloco['extremo_da_escala'] * 100:.1f} pp | n de {bloco['n_minimo']} a "
            f"{bloco['n_maximo']}"
        )
        flags = bloco["flags"]
        print(
            f"  flags: {flags['plenas']} plenas | {flags['alerta_n_baixo']} ALERTA_N_BAIXO | "
            f"{flags['conclusao_suprimida']} suprimidas"
        )
        for rotulo, chave in (("+", "tres_maiores"), ("-", "tres_menores")):
            for item in bloco[chave]:
                print(f"  {rotulo} {item}")
    for chave, caminho in relatorio["arquivos"].items():
        print(f"gravado {chave}: {caminho}")
    print(f"dados plotados: {relatorio['dados_plotados']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
