"""Tokens de desenho e utilitários comuns às figuras de `apps/analysis/figuras/`.

Criado por **F-023**. `timeline_regimes.py` (F-025) declara os mesmos tokens de cromo
localmente porque nasceu antes deste arquivo e está **congelado** para F-023 — há teste
(`test_figura_heatmap.py §1`) que compara os dois conjuntos token a token, de modo que eles não
podem divergir em silêncio. **Dívida registrada:** o orquestrador pode fazer F-025 importar daqui
num passo puramente mecânico.

O que mora aqui, e por quê:

| Bloco | Conteúdo | Por que é comum |
|---|---|---|
| Cromo | superfície, tintas, grade, eixo, crítico | o mesmo sistema visual |
| Escala divergente | arcos frio/quente, neutro, `Colormap` | parâmetro do sistema |
| Contraste | `luminancia_relativa`, `contraste`, `tinta_legivel_sobre` | cor de texto por conta |
| Procedência | `versao_build`, `sha256_do_arquivo`, `caminho_figuras` | RF-047/CA-121 |
| Gravação | `gravar_figura_deterministica` | 3 rodadas = bytes idênticos |
| Gate | `MARCA_NAO_CONGELADA`, `desenhar_rodape` | CA-090 no pé e na marca d'água |

## A escala divergente, e por que ela é **computada** e não escolhida

A `dataviz` manda: *diverging = dois matizes + ponto médio cinza neutro, passos iguais por arco*.
Os valores documentados na paleta de referência são a **rampa sequencial azul** (passos 100→700) e
o **neutro** `#f0efec`; o par divergente recomendado é **azul ↔ vermelho**, mas o arco vermelho
**não tem rampa publicada** — só as âncoras `#e34948` (slot 8) e `#d03b3b` (status crítico).

Em vez de escolher 4 vermelhos a olho (o que a skill proíbe), o arco quente é **derivado**: para
cada passo azul, procura-se por bisseção o ponto do caminho `branco → #e34948 → preto` com a
**mesma luminância relativa**. Matiz HSV é preservado exatamente (clarear misturando com branco e
escurecer multiplicando por um escalar não mudam o matiz), a luminância casa com erro < 0,002, e
os dois arcos ficam simétricos por construção — que é o que "passos iguais por arco" significa
quando o olho lê magnitude como *escuridão*.

Resultado medido com `dataviz/scripts/validate_palette.py` (modo claro, superfície `#fcfcfb`,
`--pairs all`), par espelhado por par espelhado — **os 4 pares passam os seis checks**:

| passo | frio | quente | ΔE protan | ΔE visão normal | contraste vs superfície |
|---|---|---|---|---|---|
| 1 | `#6da7ec` | `#ed8786` | 14,7 | 21,9 | 2,44 / 2,43 (WARN → alívio por rótulo) |
| 2 | `#3987e5` | `#e55555` | 21,6 | 30,8 | 3,54 / 3,55 |
| 3 | `#256abf` | `#bc3d3c` | 20,5 | 28,3 | 5,26 / 5,28 |
| 4 | `#184f95` | `#8f2e2d` | 17,1 | 23,4 | 7,89 / 7,88 |

O par espelhado é **o** par que importa numa escala divergente: é ele que carrega o **sinal** do
excesso. O WARN de contraste do passo 1 é o alívio previsto na própria skill ("visible labels") e
está coberto por CA-095, que já obriga número e `n` em toda célula.

**Verde está deliberadamente fora.** Verde × vermelho é o par que colapsa em protanopia e
deuteranopia, e é exatamente a convenção que o mercado usaria por reflexo.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # antes de qualquer import de desenho: nenhuma janela, nenhum backend GUI

from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm

from apps.pipeline.canonical.build_raw_series import caminhos_dos_componentes
from apps.pipeline.canonical.build_raw_series import versao_build as _hash_dos_componentes
from apps.pipeline.common.io_layers import caminho_canonical, garantir_diretorio

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

    from matplotlib.colors import Colormap
    from matplotlib.figure import Figure

# ─────────────────────────────────────────────────────────────────────────────
# Cromo — os papéis de `dataviz/references/palette.md`
# ─────────────────────────────────────────────────────────────────────────────

SUPERFICIE = "#fcfcfb"
PLANO_PAGINA = "#f9f9f7"
TINTA_PRIMARIA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_MUTED = "#898781"
TINTA_INVERSA = "#ffffff"
COR_GRADE = "#e1e0d9"
COR_EIXO = "#c3c2b7"
COR_CRITICO = "#d03b3b"

#: Os tokens que `timeline_regimes.py` (congelado) também declara — travados por teste.
TOKENS_COMPARTILHADOS_COM_F025: tuple[str, ...] = (
    "SUPERFICIE",
    "TINTA_PRIMARIA",
    "TINTA_SECUNDARIA",
    "TINTA_MUTED",
    "COR_GRADE",
    "COR_EIXO",
    "COR_CRITICO",
)

# ─────────────────────────────────────────────────────────────────────────────
# Escala divergente
# ─────────────────────────────────────────────────────────────────────────────

#: Ponto médio: o cinza neutro documentado. Nunca um matiz — o meio tem de ler como "nada".
NEUTRO_DIVERGENTE = "#f0efec"

#: Arco **frio** (valor positivo): passos 300, 400, 500 e 600 da rampa sequencial azul documentada.
ARCO_FRIO: tuple[str, ...] = ("#6da7ec", "#3987e5", "#256abf", "#184f95")

#: Âncora do arco quente: o vermelho documentado (slot categórico 8).
ANCORA_QUENTE = "#e34948"

#: Arco **quente** (valor negativo), derivado de `ANCORA_QUENTE` casando a luminância de cada
#: passo de `ARCO_FRIO`. Congelado aqui para revisão; `arco_quente_derivado()` reproduz.
ARCO_QUENTE: tuple[str, ...] = ("#ed8786", "#e55555", "#bc3d3c", "#8f2e2d")

#: Cinza do "sem conclusão" (`n < 5`). **Diferente** do neutro divergente de propósito: se fosse
#: o mesmo, a célula suprimida leria como "empatou com o CDI", que é uma afirmação.
CINZA_SUPRIMIDO = "#e1e0d9"
#: Hachura da célula suprimida — a ausência de conclusão num segundo canal, nunca só cor.
HACHURA_SUPRIMIDO = "///"

_RE_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _componentes(cor: str) -> tuple[float, float, float]:
    """`#rrggbb` → os três canais em [0, 1]. Recusa qualquer coisa que não seja hex de 6 dígitos."""
    if not _RE_HEX.match(cor):
        msg = f"cor fora do formato #rrggbb: {cor!r}"
        raise ValueError(msg)
    bruto = cor.lstrip("#")
    return tuple(int(bruto[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(componentes: Sequence[float]) -> str:
    """Três canais em [0, 1] → `#rrggbb`, com arredondamento para 8 bits (determinístico)."""
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in componentes)


def _linearizar(canal: float) -> float:
    """sRGB → linear, a transferência da WCAG 2.x."""
    return canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4


def luminancia_relativa(cor: str) -> float:
    """Luminância relativa da WCAG 2.x — a grandeza que o olho lê como "mais escuro"."""
    vermelho, verde, azul = (_linearizar(c) for c in _componentes(cor))
    return 0.2126 * vermelho + 0.7152 * verde + 0.0722 * azul


def contraste(primeira: str, segunda: str) -> float:
    """Razão de contraste WCAG entre duas cores (>= 1). Simétrica."""
    luminancias = sorted((luminancia_relativa(primeira), luminancia_relativa(segunda)))
    return (luminancias[1] + 0.05) / (luminancias[0] + 0.05)


def tinta_legivel_sobre(fundo: str) -> str:
    """A tinta (primária ou inversa) que **contrasta mais** com o fundo — conta, não gosto."""
    if contraste(TINTA_INVERSA, fundo) >= contraste(TINTA_PRIMARIA, fundo):
        return TINTA_INVERSA
    return TINTA_PRIMARIA


def _tinta_ou_sombra(base: str, parametro: float) -> str:
    """Ponto do caminho `branco → base → preto`. `t = 0` é branco, `0,5` é a base, `1` é preto.

    Os dois ramos preservam o **matiz HSV** da base exatamente: clarear é mistura com branco
    (tint) e escurecer é multiplicação por escalar (shade).
    """
    canais = _componentes(base)
    if parametro <= 0.5:
        fracao = parametro / 0.5
        return _hex([1.0 + (c - 1.0) * fracao for c in canais])
    fracao = (parametro - 0.5) / 0.5
    return _hex([c * (1.0 - fracao) for c in canais])


def arco_quente_derivado(
    *,
    ancora: str = ANCORA_QUENTE,
    arco_frio: Sequence[str] = ARCO_FRIO,
    iteracoes: int = 80,
) -> tuple[str, ...]:
    """O arco quente que casa, passo a passo, a luminância de `arco_frio` (bisseção determinística).

    `iteracoes` fixas (não "até convergir") para que o resultado não dependa de aritmética de
    plataforma: 80 bisseções em [0, 1] esgotam a precisão de `float` muito antes do 8º bit de cor.
    """
    derivados: list[str] = []
    for passo_frio in arco_frio:
        alvo = luminancia_relativa(passo_frio)
        baixo, alto = 0.0, 1.0
        for _ in range(iteracoes):
            meio = (baixo + alto) / 2
            if luminancia_relativa(_tinta_ou_sombra(ancora, meio)) > alvo:
                baixo = meio
            else:
                alto = meio
        derivados.append(_tinta_ou_sombra(ancora, (baixo + alto) / 2))
    return tuple(derivados)


def mapa_divergente(
    *,
    arco_negativo: Sequence[str] = ARCO_QUENTE,
    neutro: str = NEUTRO_DIVERGENTE,
    arco_positivo: Sequence[str] = ARCO_FRIO,
    nome: str = "ldc_divergente",
) -> Colormap:
    """`Colormap` divergente: polo negativo → neutro → polo positivo, passos iguais por arco.

    Contínua (e não em faixas) porque a grandeza é contínua; o número exato de cada célula está
    escrito nela, então a cor carrega **magnitude e sinal**, não o valor.
    """
    ancoras = [*reversed(list(arco_negativo)), neutro, *arco_positivo]
    return LinearSegmentedColormap.from_list(nome, ancoras, N=512)


def normalizacao_centrada_em_zero(extremo: float) -> Normalize:
    """Escala **simétrica** em torno de 0: `-extremo → 0 → +extremo`.

    Simétrica é obrigatório: com `vmin`/`vmax` independentes, o zero sairia do meio da rampa e o
    cinza neutro deixaria de significar "empatou com o CDI" (ADR-002 §3).
    """
    if not extremo > 0:
        msg = f"extremo da escala divergente tem de ser positivo, recebi {extremo!r}"
        raise ValueError(msg)
    return TwoSlopeNorm(vmin=-extremo, vcenter=0.0, vmax=extremo)


# ─────────────────────────────────────────────────────────────────────────────
# Procedência e gravação
# ─────────────────────────────────────────────────────────────────────────────

#: Subpasta de `data/canonical/` onde as figuras e os dados plotados vivem.
SUBPASTA_FIGURAS = "figuras"
FORMATOS: tuple[str, ...] = ("png", "svg")
DPI_PNG = 150


def versao_build(modulos: Sequence[str]) -> str:
    """`sha256` do conjunto de módulos que determina o conteúdo da figura (RF-047/CA-121)."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos))


def sha256_do_arquivo(alvo: Path) -> str:
    """`sha256` de um insumo lido, byte a byte — o "hash dos insumos" do rodapé."""
    return hashlib.sha256(Path(alvo).read_bytes()).hexdigest()


def caminho_figuras(*, raiz: Path | None = None) -> Path:
    """`data/canonical/figuras/` — a pasta de saída desta camada."""
    return caminho_canonical(SUBPASTA_FIGURAS, raiz=raiz)


def gravar_figura_deterministica(
    figura: Figure,
    *,
    base_do_nome: str,
    versao: str,
    salga_svg: str,
    identificacao: str,
    raiz: Path | None = None,
    formatos: Sequence[str] = FORMATOS,
) -> dict[str, Path]:
    """Grava PNG + SVG sem nenhum metadado vindo do relógio.

    `svg.hashsalt` fixo (senão os `id` do SVG mudam entre processos), `Date: None` no SVG e
    `Software` fixo no PNG. É o que faz "a figura mudou" significar "o código ou o dado mudou".
    """
    destino = garantir_diretorio(caminho_figuras(raiz=raiz))
    software = f"estrategia-macro-ldc-dados {identificacao} versao_build={versao}"
    saidas: dict[str, Path] = {}
    for formato in formatos:
        alvo = destino / f"{base_do_nome}.{formato}"
        metadados: dict[str, Any] = (
            {"Software": software}
            if formato == "png"
            else {"Date": None, "Creator": software, "Title": base_do_nome}
        )
        with matplotlib.rc_context({"svg.hashsalt": salga_svg}):
            figura.savefig(alvo, format=formato, facecolor=SUPERFICIE, metadata=metadados)
        saidas[formato] = alvo
    return saidas


# ─────────────────────────────────────────────────────────────────────────────
# Gate de publicação (CA-090)
# ─────────────────────────────────────────────────────────────────────────────

MARCA_NAO_CONGELADA = "ESPECIFICAÇÃO NÃO CONGELADA — não publicável"
"""CA-090 por escrito, na figura. Enquanto ADR-001 estiver em `Proposta`, é obrigatória."""


def desenhar_rodape(
    figura: Figure,
    *,
    linhas: Sequence[str],
    congelada: bool,
    x: float,
    y_topo: float,
    entrelinha: float,
    fontsize: float = 7.4,
) -> None:
    """Procedência no pé da figura + a marca de CA-090 quando a especificação não está congelada."""
    for ordem, texto in enumerate(linhas):
        figura.text(
            x,
            y_topo - ordem * entrelinha,
            texto,
            ha="left",
            va="top",
            fontsize=fontsize,
            color=TINTA_MUTED,
        )
    if not congelada:
        figura.text(
            x,
            y_topo - len(linhas) * entrelinha,
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


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip textual no SVG
# ─────────────────────────────────────────────────────────────────────────────

_RE_GRUPO_COM_ID = re.compile(r'<g id="(?P<gid>[^"]+)">')

_ESCAPES_XML: tuple[tuple[str, str], ...] = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
)


def escapar_xml(texto: str) -> str:
    """Escapa o mínimo necessário para um nó de texto XML (`&`, `<`, `>`)."""
    for bruto, trocado in _ESCAPES_XML:
        texto = texto.replace(bruto, trocado)
    return texto


def injetar_tooltips_svg(alvo: Path, tooltips: Mapping[str, str]) -> int:
    """Insere `<title>` em cada `<g id=...>` cujo `gid` esteja em `tooltips`. Devolve quantos.

    `<title>` é o tooltip nativo do SVG: abrir o arquivo num navegador e passar o mouse pela
    célula mostra o erro-padrão, o `hit_ratio_cdi` e as flags, que **não** cabem na célula sem
    poluí-la. É uma transformação de string pura — o SVG continua determinístico.
    """
    corpo = Path(alvo).read_text(encoding="utf-8")
    injetados = 0

    def _substituir(achado: re.Match[str]) -> str:
        nonlocal injetados
        gid = achado.group("gid")
        if gid not in tooltips:
            return achado.group(0)
        injetados += 1
        return f"{achado.group(0)}<title>{escapar_xml(tooltips[gid])}</title>"

    novo = _RE_GRUPO_COM_ID.sub(_substituir, corpo)
    if injetados:
        Path(alvo).write_text(novo, encoding="utf-8")
    return injetados
