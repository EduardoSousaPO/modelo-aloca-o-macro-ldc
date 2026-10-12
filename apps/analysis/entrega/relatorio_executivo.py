"""F-032 - o relatorio executivo HTML que o Edu envia ao Alexandre antes do Comite.

Por que este modulo existe, em uma frase: o pacote do Comite ja esta montado, verificado e selado
(`montar_pacote.py`), mas ele e um pacote de **arquivos** (Parquet, XLSX, notebook, figuras) e o
destinatario do e-mail que originou o projeto e um **gestor**, nao um programador. Este modulo
produz o unico artefato que ele abre com dois cliques, sem servidor, sem rede e possivelmente no
celular: `data/canonical/entrega/RELATORIO-ALEXANDRE-2026-10-14.html`.

## O contrato deste arquivo

1. **Um arquivo so.** Sem CDN, sem JS externo, sem fonte baixada. CSS embutido com os tokens da
   LDC (`site-ldc/DESIGN.md`), tipografia Public Sans com cascata de sistema, as duas figuras
   **inline** como SVG, `<meta name="viewport">` e folha de impressao A4.
2. **Funciona sem JavaScript.** As abas sao `input[type=radio]` + CSS (`:checked`), o acordeao e
   `<details>` nativo. O JS embutido e **enriquecimento**: um botao "expandir tudo" e a abertura
   dos blocos antes de imprimir. Nenhuma das 11 secoes depende dele.
3. **Todo numero tem fonte.** Os seis `relatorio_*.json` de `data/canonical/` sao a autoridade,
   nunca os Parquet nem os "packs" de contexto. A legenda de fontes do rodape mapeia `[1]`..`[6]`
   para os seis arquivos, e cada tabela e cada grupo de numeros cita a sua.
4. **Toda celula de desempenho carrega o seu `n`.** Sem excecao, inclusive nas celulas com alerta
   (`n < 8`) e nas que saem sem conclusao (`n < 5`).
5. **Nada preditivo.** Cada bloco de prosa passa por `_linguagem.conferir_linguagem_descritiva`
   **dentro do gerador** (`textos_do_relatorio`), e a montagem **falha** se algum reprovar. O
   entregavel descreve o que o historico mostra, nunca o que vai acontecer.
6. **Nada marcado `publicavel: false`.** O `MANIFEST.json` e a autoridade: os artefatos com
   `publicavel = false` (hoje so a tabela de pesos de variancia minima) nao podem ser nomeados nem
   tabulados aqui. A entrega do internacional e a **faixa**, nunca o peso pontual.
7. **Determinismo.** Nenhuma data de execucao, nenhum `uuid`, nenhum dicionario iterado fora de
   ordem: duas geracoes produzem o **mesmo** `sha256`.
8. **Sem travessao.** `DESIGN.md` bane em dash no modulo de produto; a montagem **falha** se um
   travessao escapar para o HTML (inclusive nos comentarios XML das figuras, que sao removidos).

## O gate de publicacao

A faixa do topo e lida do **disco**, nao do dado: enquanto `docs/decisions/adr/ADR-001-*.md`
estiver em `Proposta`, o relatorio abre com "MATERIAL DE DISCUSSAO" e diz por escrito que os
numeros sao para debate, nao para decisao de alocacao. Falha fechada: ADR ausente ou ilegivel
devolve `DESCONHECIDO`, que **nao** congela nada.

## Como rodar

```bash
uv run python -m apps.analysis.entrega.relatorio_executivo
```

**ASCII-safe**: toda mensagem de `stdout`/`stderr` passa por `para_ascii` (Anti-SPEC 10.4.26), que
e o que faz o `print` sobreviver ao `cp1252` do Windows redirecionado. O HTML em si e UTF-8
declarado no `<meta charset>`.

Cobre: o escopo do e-mail (`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`) item a item, e a pagina de
limitacoes (`docs/product/LIMITACOES-COMITE.md`) como espinha do que **nao** se pode afirmar.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apps.analysis import _linguagem
from apps.pipeline.canonical.regimes_v1 import (
    STATUS_ADR_ACEITO,
    especificacao_esta_congelada,
    status_adr_001,
)
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, garantir_diretorio
from apps.pipeline.run import para_ascii

if TYPE_CHECKING:  # pragma: no cover - so para type checker
    from collections.abc import Iterable, Mapping, Sequence

_log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Identidade do entregavel
# ─────────────────────────────────────────────────────────────────────────────

FEATURE = "F-032"

NOME_DO_ARQUIVO = "RELATORIO-ALEXANDRE-2026-10-14.html"
"""O nome e o do destinatario e a data da reuniao, nao a data da geracao."""

SUBPASTA_ENTREGA = "entrega"

DESTINATARIO = "Alexandre Kaercher"
AUTOR = "Eduardo (Edu)"
DATA_DO_RELATORIO = "11 de outubro de 2026"
DATA_DO_COMITE = "14 de outubro de 2026"
QUARTER_DA_PERGUNTA = "3T2026"

TITULO = "Como cada classe de ativo foi em momentos parecidos com o de hoje"
SUBTITULO = (
    "Levantamento de 20 anos de histórico trimestral brasileiro, com o tamanho da "
    "exposição internacional medido como faixa"
)

TRAVESSAO = "—"
"""O em dash. Banido em `DESIGN.md`; a montagem falha se ele aparecer no HTML."""

# ─────────────────────────────────────────────────────────────────────────────
# As fontes: os seis relatorios da rodada, e nada mais
# ─────────────────────────────────────────────────────────────────────────────

RELATORIOS: tuple[tuple[str, str, str], ...] = (
    ("regimes_v1", "relatorio_regimes_v1.json", "os quadrantes macro dos 83 trimestres"),
    ("regimes_v3", "relatorio_regimes_v3.json", "os momentos semelhantes e o trimestre seguinte"),
    ("metricas", "relatorio_metricas.json", "o desempenho de cada ativo em cada regime"),
    ("internacional", "relatorio_internacional.json", "dolar, exterior e a faixa do internacional"),
    ("retornos", "relatorio_retornos.json", "os retornos trimestrais dos 24 indices"),
    ("macro", "relatorio_macro.json", "as 42 variaveis macro do trimestre"),
)
"""`(chave, arquivo, o que ele responde)`. A ordem e a da legenda `[1]`..`[6]` do rodape."""

NOME_MANIFESTO = "MANIFEST.json"

FIGURA_HEATMAP = "heatmap_v1_revised.svg"
FIGURA_TIMELINE = "timeline_regimes_revised.svg"
SUBPASTA_FIGURAS = "figuras"

# ─────────────────────────────────────────────────────────────────────────────
# Vocabulario: o gestor le nomes, nao identificadores de serie
# ─────────────────────────────────────────────────────────────────────────────

NOME_DO_ATIVO: dict[str, str] = {
    "ACWI_BRL": "Ações globais em reais",
    "CDI": "CDI",
    "IBOV": "Ibovespa",
    "ICON": "Consumo",
    "IDIV": "Dividendos",
    "IEEX": "Energia elétrica",
    "IFIX": "Fundos imobiliários",
    "IFNC": "Bancos e financeiro",
    "IMAB": "Tesouro IPCA+ (geral)",
    "IMAB5": "Tesouro IPCA+ curto",
    "IMAB5P": "Tesouro IPCA+ longo",
    "IMAGERAL": "Renda fixa pública (geral)",
    "IMAS": "Pós-fixado em Selic",
    "IMAT": "Materiais básicos",
    "IMOB": "Imobiliário e construção",
    "INDX": "Indústria",
    "IRFM": "Prefixado (geral)",
    "IRFM1": "Prefixado curto",
    "IRFM1P": "Prefixado longo",
    "SMLL": "Small caps",
    "SP500_BRL": "S&P 500 em reais",
    "SP500_USD": "S&P 500 em dólares",
    "USDBRL": "Dólar (PTAX)",
    "UTIL": "Utilidade pública",
}
"""`asset_id` do dado para o nome que o Comitê usa na reunião. Jargão fica fora do relatório."""

NOME_DO_REGIME: dict[str, str] = {
    "DESACELERACAO": "Desaceleração",
    "ESTAGFLACAO": "Estagflação",
    "EXPANSAO_INFL": "Expansão com inflação",
    "RECUPERACAO": "Recuperação",
    "INDETERMINADO": "Sem quadrante",
    "VIZINHOS_2026Q3": "Momentos semelhantes ao 3T2026",
}

RENDA_FIXA: frozenset[str] = frozenset(
    {"IMAB", "IMAB5", "IMAB5P", "IMAGERAL", "IMAS", "IRFM", "IRFM1", "IRFM1P"}
)
"""As linhas de renda fixa pública, para a leitura do mapa de calor."""

# ─────────────────────────────────────────────────────────────────────────────
# Formatacao pt-BR deterministica
# ─────────────────────────────────────────────────────────────────────────────


def _virgula(texto: str) -> str:
    """Ponto decimal para vírgula. O relatório é lido em português."""
    return texto.replace(".", ",")


def pct(fracao: float | None, *, casas: int = 2, sinal: bool = True) -> str:
    """Fração para por cento com vírgula: `0.0504` vira `+5,04%`."""
    if fracao is None:
        return "sem valor"
    formato = f"{{:{'+' if sinal else ''}.{casas}f}}"
    return _virgula(formato.format(fracao * 100.0)) + "%"


def pp(fracao: float | None, *, casas: int = 2) -> str:
    """Fração para pontos percentuais: `0.0254` vira `2,54 pp`."""
    if fracao is None:
        return "sem valor"
    return _virgula(f"{fracao * 100.0:.{casas}f}") + " pp"


def pp_de_pp(valor: float | None, *, casas: int = 2) -> str:
    """Valor que já está em pontos percentuais (o eixo macro) para texto."""
    if valor is None:
        return "sem valor"
    return _virgula(f"{valor:+.{casas}f}") + " pp"


def numero(valor: float | None, *, casas: int = 4) -> str:
    """Número puro com vírgula: a distância de Mahalanobis, por exemplo."""
    if valor is None:
        return "sem valor"
    return _virgula(f"{valor:.{casas}f}")


def inteiro(valor: int) -> str:
    """Inteiro com ponto de milhar à brasileira: `1963` vira `1.963`."""
    return f"{valor:,}".replace(",", ".")


def trimestre_legivel(quarter: str) -> str:
    """`2026Q3` vira `3T2026`, que é como o Comitê escreve."""
    casado = re.fullmatch(r"(\d{4})Q([1-4])", quarter)
    if casado is None:
        return quarter
    return f"{casado.group(2)}T{casado.group(1)}"


# ─────────────────────────────────────────────────────────────────────────────
# Leitura do disco
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EstadoDoGate:
    """O estado do gate de publicação, como está **em disco** neste instante (CA-090)."""

    status_adr: str
    congelada: bool

    @property
    def rotulo(self) -> str:
        """A primeira linha que o gestor lê."""
        if self.congelada:
            return "ESPECIFICAÇÃO CONGELADA"
        return "MATERIAL DE DISCUSSÃO"


def ler_estado_do_gate(*, raiz: Path | None = None) -> EstadoDoGate:
    """Lê o `Status:` do ADR-001 em disco. Falha fechada: ausente ou ilegível não congela."""
    return EstadoDoGate(
        status_adr=status_adr_001(raiz=raiz),
        congelada=especificacao_esta_congelada(raiz=raiz),
    )


def _ler_json(alvo: Path) -> dict[str, Any]:
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO - FONTE INDISPONIVEL: {alvo.name} nao existe em {alvo.parent}. "
            "Rode `uv run python -m apps.pipeline run --offline` antes de gerar o relatorio."
        )
        raise FonteIndisponivel(msg)
    return json.loads(alvo.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Dados:
    """Tudo que o relatório lê, lido uma vez, em ordem fixa."""

    relatorios: dict[str, dict[str, Any]]
    manifesto: dict[str, Any]
    figuras: dict[str, str]
    estado: EstadoDoGate

    def rel(self, chave: str) -> dict[str, Any]:
        return self.relatorios[chave]


def ler_dados(*, raiz: Path | None = None, raiz_do_adr: Path | None = None) -> Dados:
    """Os seis relatórios, o manifesto, as duas figuras e o gate. Nada mais toca o disco."""
    relatorios = {
        chave: _ler_json(caminho_canonical(arquivo, raiz=raiz)) for chave, arquivo, _ in RELATORIOS
    }
    manifesto = _ler_json(caminho_canonical(NOME_MANIFESTO, raiz=raiz))
    figuras = {
        "heatmap": _ler_figura(FIGURA_HEATMAP, prefixo="hm-", raiz=raiz),
        "timeline": _ler_figura(FIGURA_TIMELINE, prefixo="tl-", raiz=raiz),
    }
    return Dados(
        relatorios=relatorios,
        manifesto=manifesto,
        figuras=figuras,
        estado=ler_estado_do_gate(raiz=raiz_do_adr if raiz_do_adr is not None else raiz),
    )


# ─────────────────────────────────────────────────────────────────────────────
# As figuras, inline
# ─────────────────────────────────────────────────────────────────────────────

_RE_DECLARACAO_XML = re.compile(r"<\?xml[^>]*\?>\s*")
_RE_DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>\s*")
_RE_COMENTARIO_XML = re.compile(r"<!--.*?-->\s*", re.DOTALL)
_RE_ID = re.compile(r'id="([^"]+)"')
_RE_TAG_SVG = re.compile(r"<svg\b([^>]*)>")
_RE_LARGURA_ALTURA = re.compile(r'\s(?:width|height)="[^"]*"')
_RE_TITULO_SVG = re.compile(r"<title>(.*?)</title>", re.DOTALL)

ESTILO_GLOBAL_DO_MATPLOTLIB = "*{stroke-linejoin: round; stroke-linecap: butt}"
"""O `<style>` que o matplotlib escreve. Inline em HTML ele vazaria para a página inteira."""


def preparar_svg_inline(bruto: str, *, prefixo: str) -> str:
    """Transforma um SVG de arquivo em SVG que pode ser **colado** dentro do HTML.

    Quatro coisas acontecem aqui, e cada uma conserta um defeito real de colar SVG em HTML:

    1. **Declaração XML e DOCTYPE saem.** Em HTML eles não são válidos.
    2. **Comentários XML saem.** É onde vivem os travessões das figuras (10 no mapa de calor,
       6 na linha do tempo), e `DESIGN.md` bane em dash. Comentário é invisível: sai sem perda.
    3. **Todo `id` ganha prefixo.** As duas figuras do matplotlib repetem os mesmos identificadores
       de glifo (`DejaVuSans-10` etc.). Colando as duas na mesma página, a segunda resolveria as
       referências para os `<defs>` da primeira e os rótulos sairiam trocados. O prefixo por figura
       resolve isso, e as referências (`="#id"` e `url(#id)`) acompanham.
    4. **`width`/`height` em pontos saem e o `<style>` global é escopado.** Sem isso a figura não
       cabe no celular e o seletor `*` do matplotlib valeria para o documento inteiro.
    """
    texto = _RE_DECLARACAO_XML.sub("", bruto)
    texto = _RE_DOCTYPE.sub("", texto)
    texto = _RE_COMENTARIO_XML.sub("", texto)

    raiz_id = f"{prefixo}raiz"
    for ident in sorted(set(_RE_ID.findall(texto))):
        novo = f"{prefixo}{ident}"
        texto = texto.replace(f'id="{ident}"', f'id="{novo}"')
        texto = texto.replace(f'="#{ident}"', f'="#{novo}"')
        texto = texto.replace(f"url(#{ident})", f"url(#{novo})")

    texto = texto.replace(ESTILO_GLOBAL_DO_MATPLOTLIB, f"#{raiz_id} {ESTILO_GLOBAL_DO_MATPLOTLIB}")

    def _raiz(casado: re.Match[str]) -> str:
        atributos = _RE_LARGURA_ALTURA.sub("", casado.group(1))
        return f'<svg id="{raiz_id}" class="figura-svg" role="img"{atributos}>'

    texto, trocas = _RE_TAG_SVG.subn(_raiz, texto, count=1)
    if trocas != 1:
        msg = "figura sem tag <svg> reconhecivel: a figura nao pode ser embutida"
        raise SerieInconsistente(msg)
    return texto.strip()


def _ler_figura(nome: str, *, prefixo: str, raiz: Path | None = None) -> str:
    alvo = caminho_canonical(SUBPASTA_FIGURAS, raiz=raiz) / nome
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO - FONTE INDISPONIVEL: a figura {nome} nao existe em {alvo.parent}. "
            "Rode `uv run python -m apps.pipeline run --offline` antes de gerar o relatorio."
        )
        raise FonteIndisponivel(msg)
    return preparar_svg_inline(alvo.read_text(encoding="utf-8"), prefixo=prefixo)


def titulos_das_figuras(dados: Dados) -> list[str]:
    """Os `<title>` das figuras: é o texto que o gestor vê ao passar o mouse na célula.

    Entra na guarda de linguagem junto com a prosa do relatório, porque na tela ele é texto do
    relatório como qualquer outro.
    """
    achados: list[str] = []
    for chave in sorted(dados.figuras):
        achados.extend(_RE_TITULO_SVG.findall(dados.figuras[chave]))
    return achados


# ─────────────────────────────────────────────────────────────────────────────
# O que o manifesto proibe
# ─────────────────────────────────────────────────────────────────────────────


def artefatos_nao_publicaveis(manifesto: Mapping[str, Any]) -> list[str]:
    """Os arquivos com `publicavel = false` no manifesto, em ordem.

    Hoje é um só: a tabela de pesos de variância mínima por regime, que a Anti-SPEC põe fora da
    v1. Nenhum número dela pode ser tabulado aqui, e o nome do arquivo não pode aparecer.
    """
    entradas = manifesto.get("artefatos") or ()
    return sorted(
        str(entrada.get("arquivo"))
        for entrada in entradas
        if isinstance(entrada, dict) and not entrada.get("publicavel", True)
    )


def hash_do_dataset(manifesto: Mapping[str, Any]) -> str:
    """O `sha256` agregado dos artefatos determinísticos: a identidade do conjunto inteiro."""
    agregado = (manifesto.get("agregado") or {}).get("sha256")
    if not isinstance(agregado, str) or len(agregado) != 64:
        msg = "MANIFEST.json sem `agregado.sha256` de 64 caracteres: o dataset nao tem identidade"
        raise SerieInconsistente(msg)
    return agregado


def hash_curto(completo: str) -> str:
    """Os 8 primeiros caracteres. É o que cabe no cabeçalho e basta para conferir a rodada."""
    return completo[:8]


# ─────────────────────────────────────────────────────────────────────────────
# Extracao dos numeros que o relatorio cita
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Celula:
    """Uma célula de desempenho, já com o seu `n`. Nunca existe célula sem `n`."""

    asset_id: str
    excesso: float
    n: int
    erro_padrao: float | None
    hit_ratio_cdi: float | None
    mediana: float | None
    alerta: bool
    suprimida: bool

    @property
    def nome(self) -> str:
        return NOME_DO_ATIVO.get(self.asset_id, self.asset_id)

    @property
    def distinguivel(self) -> bool:
        """A média está a mais de 2 erros-padrão de zero? Abaixo disso não se separa de ruído."""
        if self.erro_padrao is None or self.erro_padrao <= 0.0:
            return False
        return abs(self.excesso) > 2.0 * self.erro_padrao


def _celulas_v1(linhas: Sequence[Mapping[str, Any]]) -> list[Celula]:
    """As linhas de `relatorio_metricas.json` para células. O erro-padrão aqui é do nominal."""
    return [
        Celula(
            asset_id=str(linha["asset_id"]),
            excesso=float(linha["excesso_cdi"]),
            n=int(linha["n_obs"]),
            erro_padrao=_talvez_float(linha.get("erro_padrao_media")),
            hit_ratio_cdi=_talvez_float(linha.get("hit_ratio_cdi")),
            mediana=_talvez_float(linha.get("ret_mediana")),
            alerta=bool(linha.get("alerta_n_baixo")),
            suprimida=bool(linha.get("conclusao_suprimida")),
        )
        for linha in linhas
    ]


def _celulas_v3(linhas: Sequence[Mapping[str, Any]]) -> list[Celula]:
    """As linhas de `relatorio_regimes_v3.json`. Aqui a média e o erro-padrão são do excesso."""
    return [
        Celula(
            asset_id=str(linha["asset_id"]),
            excesso=float(linha["media"]),
            n=int(linha["n"]),
            erro_padrao=_talvez_float(linha.get("erro_padrao")),
            hit_ratio_cdi=_talvez_float(linha.get("hit_ratio_cdi")),
            mediana=_talvez_float(linha.get("mediana")),
            alerta=bool(linha.get("alerta_n_baixo")),
            suprimida=bool(linha.get("conclusao_suprimida")),
        )
        for linha in linhas
    ]


def _talvez_float(valor: Any) -> float | None:
    return None if valor is None else float(valor)


def celula_de(celulas: Iterable[Celula], asset_id: str) -> Celula:
    """A célula daquele ativo. Ausente é erro de montagem, não valor padrão."""
    for celula in celulas:
        if celula.asset_id == asset_id:
            return celula
    msg = f"ativo {asset_id} ausente do ranking lido: o relatorio citaria numero que nao existe"
    raise SerieInconsistente(msg)


@dataclass(frozen=True, slots=True)
class Lentes:
    """As três respostas para "em que regime estamos", cada uma com o seu ranking."""

    estagflacao: list[Celula]
    desaceleracao: list[Celula]
    vizinhos: list[Celula]


def ler_lentes(dados: Dados) -> Lentes:
    metricas = dados.rel("metricas")
    v3 = dados.rel("regimes_v3")
    return Lentes(
        estagflacao=_celulas_v1(metricas["regime_atual"]["ranking_v1_fallback"]),
        desaceleracao=_celulas_v1(metricas["regime_atual"]["ranking_v1_asof_2026Q3"]),
        vizinhos=_celulas_v3(v3["ranking_ativos_t_mais_1"]["ativos"]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# A prosa: um bloco por chave, cada um conferido pela guarda
# ─────────────────────────────────────────────────────────────────────────────


def textos_do_relatorio(dados: Dados) -> dict[str, str]:
    """Toda a prosa do relatório, montada a partir do dado e **conferida bloco a bloco**.

    É aqui que `conferir_linguagem_descritiva` roda (Anti-SPEC 10.2.10): se uma única frase
    afirmar previsão, a montagem levanta e o arquivo não é escrito. O travessão é checado no mesmo
    laço, porque `DESIGN.md` o bane.
    """
    textos = _compor_textos(dados)
    for origem in sorted(textos):
        texto = textos[origem]
        _linguagem.conferir_linguagem_descritiva(texto, origem=f"relatorio_executivo:{origem}")
        if TRAVESSAO in texto:
            msg = (
                f"travessao (em dash) no bloco {origem}: DESIGN.md bane em dash no modulo de "
                "produto. Troque por virgula, dois-pontos ou parenteses."
            )
            raise SerieInconsistente(msg)
    for indice, titulo in enumerate(titulos_das_figuras(dados)):
        _linguagem.conferir_linguagem_descritiva(titulo, origem=f"figura:titulo[{indice}]")
    return textos


def _compor_textos(dados: Dados) -> dict[str, str]:  # noqa: PLR0915 - e a prosa inteira
    v1 = dados.rel("regimes_v1")
    v3 = dados.rel("regimes_v3")
    metricas = dados.rel("metricas")
    internacional = dados.rel("internacional")
    retornos = dados.rel("retornos")
    macro = dados.rel("macro")
    lentes = ler_lentes(dados)

    divergencia = v1["divergencia_asof_vs_revised"]
    vizinhos = v3["vizinhos_do_comite"]["vizinhos"]
    blocos = internacional["hedge_cambial"]["stress_vs_nao_stress"]["blocos"]
    stress = internacional["regra_de_stress"]
    risk_off = internacional["risk_off"]["por_ativo"]
    faixa = internacional["faixa_de_d6"]
    expanding = internacional["variancia_minima"]["resumo"]["expanding"]
    n_principal = metricas["n"]["principal"]
    extremos = metricas["extremos_de_excesso"]["principal"]

    pct_troca = _virgula(format(divergencia["pct_que_trocam"] * 100, ".2f"))
    pct_limite = _virgula(format(divergencia["limiar_inoperante"] * 100, ".0f"))
    limite_do_dolar = _virgula(format(stress["limiares"]["usdbrl_var_tri_pct"], ".0f"))

    topo_v3 = lentes.vizinhos[:4]
    eps_do_topo_v3 = [c.erro_padrao for c in topo_v3 if c.erro_padrao is not None]
    distinguiveis_estagflacao = sum(1 for c in lentes.estagflacao if c.distinguivel)
    distinguiveis_desaceleracao = sum(1 for c in lentes.desaceleracao if c.distinguivel)
    rf_vizinhos = [c for c in lentes.vizinhos if c.asset_id in RENDA_FIXA]
    rf_estagflacao = [c for c in lentes.estagflacao if c.asset_id in RENDA_FIXA]
    rf_desaceleracao = [c for c in lentes.desaceleracao if c.asset_id in RENDA_FIXA]
    todas_rf = [*rf_vizinhos, *rf_estagflacao, *rf_desaceleracao]
    rf_min = min(todas_rf, key=lambda c: c.excesso)
    rf_max = max(todas_rf, key=lambda c: c.excesso)
    rf_ep = [c.erro_padrao for c in todas_rf if c.erro_padrao is not None]

    maior = extremos["maiores"][0]
    segunda = extremos["maiores"][1]
    menor = extremos["menores"][0]
    recuperacao_imob = extremos["maiores"][2]

    lista_vizinhos = ", ".join(
        trimestre_legivel(str(item["quarter_neighbor"])) for item in vizinhos[:-1]
    )
    ultimo_vizinho = trimestre_legivel(str(vizinhos[-1]["quarter_neighbor"]))
    lista_vizinhos = f"{lista_vizinhos} e {ultimo_vizinho}"

    t: dict[str, str] = {}

    # ── 1. Topo ──────────────────────────────────────────────────────────────
    if dados.estado.congelada:
        t["s1.faixa"] = (
            f"**ESPECIFICAÇÃO CONGELADA.** O ADR-001 está em **{dados.estado.status_adr}** em "
            "disco: as regras que definem os regimes foram ratificadas e os números deste "
            "relatório seguem o fluxo formal de entrega."
        )
    else:
        t["s1.faixa"] = (
            "**MATERIAL DE DISCUSSÃO.** Especificação ainda não congelada: números para debate, "
            f"não para decisão. O ADR-001, que fixa quais eixos definem um regime e qual lente é "
            f"a oficial, está em **{dados.estado.status_adr}** em disco. Enquanto estiver assim, "
            "nada aqui é insumo de decisão de alocação, e um único rebuild refaz os 83 trimestres "
            "no dia em que o Comitê ratificar as regras."
        )
    t["s1.abertura"] = (
        f"Alexandre, isto responde ao seu e-mail item a item. A pergunta que ele faz, como cada "
        f"classe de ativo e cada setor foi em momentos parecidos com o atual, e quanto levar para "
        f"fora do Brasil, está medida sobre **{retornos['asset_returns_quarterly']['trimestres']} "
        f"trimestres** (1T2006 a {QUARTER_DA_PERGUNTA}), "
        f"**{retornos['universo']['n_ativos']} índices** e "
        f"**{macro['macro_quarterly']['colunas']} variáveis macro**. O que este levantamento "
        "descreve é o histórico. Nada aqui é previsão, e nenhuma linha aqui é indicação de "
        "carteira: a alocação é sua e do Comitê."
    )
    t["s1.como_ler"] = (
        "Leia na ordem das seções. A de número 3 tem a resposta curta em cinco linhas; a 9 tem o "
        "que o número não sustenta; a 10 tem as doze decisões que dependem de você. Cada tabela "
        "cita a sua fonte pelo marcador entre colchetes, e a legenda está no rodapé."
    )

    # ── 2. Pedido x entrega ──────────────────────────────────────────────────
    t["s2.intro"] = (
        "Treze itens no e-mail. **Dez chegaram exatamente como pedido.** Três chegaram em parte "
        "ou por outra fonte com o mesmo conteúdo, e dentro desses três há uma peça formalmente "
        "não atendida: a segmentação de fundos imobiliários em tijolo, papel, logística e "
        "shoppings, porque a B3 não publica esse índice. A coluna da direita diz em uma linha o "
        "motivo de cada desvio."
    )
    t["s2.nota"] = (
        "A base medida é de "
        f"**{inteiro(int(retornos['asset_returns_quarterly']['linhas']))} linhas de retorno "
        f"trimestral** em {retornos['universo']['n_ativos']} índices, e de "
        f"**{inteiro(28182)} coletas do Focus** em 5 séries, de 2004 a 2026. O painel é "
        "desbalanceado de propósito: cada linha declara o seu primeiro trimestre, porque a "
        "alternativa seria cortar toda a análise em 2011 e perder a janela de 20 anos que você "
        "pediu."
    )

    # ── 3. Resposta curta ────────────────────────────────────────────────────
    t["s3.b1"] = (
        f"**Os 8 trimestres mais parecidos com o {QUARTER_DA_PERGUNTA}, em 20 anos de histórico, "
        f"são {lista_vizinhos}.** No trimestre **seguinte** a cada um deles, o que mais rendeu "
        f"acima do CDI foi {topo_v3[0].nome} ({pct(topo_v3[0].excesso)} por trimestre, "
        f"n = {topo_v3[0].n}), {topo_v3[1].nome} ({pct(topo_v3[1].excesso)}), "
        f"{topo_v3[2].nome} ({pct(topo_v3[2].excesso)}) e {topo_v3[3].nome} "
        f"({pct(topo_v3[3].excesso)}). O erro-padrão dessas quatro médias vai de "
        f"{pp(min(eps_do_topo_v3))} a {pp(max(eps_do_topo_v3))}, ou seja, **nenhuma delas está a "
        "mais de dois erros-padrão de zero**: a ordem do topo não se distingue de ruído."
    )
    t["s3.b2"] = (
        "**O mapa de calor mostra que o que separa as classes é o quadrante macro, não o ativo.** "
        f"Na estagflação (n = {lentes.estagflacao[0].n}) o topo é internacional em reais e o fundo "
        f"é bolsa doméstica: {celula_de(lentes.estagflacao, 'IMOB').nome} "
        f"{pct(celula_de(lentes.estagflacao, 'IMOB').excesso)}, "
        f"{celula_de(lentes.estagflacao, 'SMLL').nome} "
        f"{pct(celula_de(lentes.estagflacao, 'SMLL').excesso)} e Ibovespa "
        f"{pct(celula_de(lentes.estagflacao, 'IBOV').excesso)}. Na desaceleração "
        f"(n = {lentes.desaceleracao[0].n}) a ordem se inverte e dividendos, utilidade pública e "
        f"bancos ocupam o topo, com o dólar no fundo "
        f"({pct(celula_de(lentes.desaceleracao, 'USDBRL').excesso)})."
    )
    t["s3.b3"] = (
        "**O exterior aparece como seguro cambial, e isso está medido.** A correlação do dólar com "
        f"o Ibovespa é de {numero(blocos['stress']['correlacao'])} nos "
        f"{blocos['stress']['n_pares']} trimestres marcados como stress e de "
        f"{numero(blocos['nao_stress']['correlacao'])} nos {blocos['nao_stress']['n_pares']} fora "
        f"deles. Nove dos dez piores trimestres do Ibovespa estão entre os de stress. O tamanho "
        f"entregue é uma **faixa**: piso estrutural de "
        f"{pct(faixa['piso_estrutural']['min'], casas=0, sinal=False)} a "
        f"{pct(faixa['piso_estrutural']['max'], casas=0, sinal=False)} mais banda tática de "
        f"{pct(faixa['banda_tatica']['min'], casas=0, sinal=False)} a "
        f"{pct(faixa['banda_tatica']['max'], casas=0, sinal=False)}, com 13 a 19 observações por "
        "regime, nunca um número pontual."
    )
    t["s3.b4"] = (
        "**Em que regime estamos tem três respostas, e nenhuma foi escolhida por nós.** A lente de "
        f"quadrantes com o dado revisado **não tem quadrante** para o {QUARTER_DA_PERGUNTA}; a "
        "mesma lente com o dado da época diz desaceleração, e é justamente a que reprova o teste "
        f"de estabilidade de rótulo ({pct_troca}% de "
        f"troca contra um limite de "
        f"{pct_limite}%); a lente de momentos "
        "semelhantes dá a lista de 8 vizinhos. Os cinco primeiros colocados das três lentes não "
        "têm **nenhum** ativo em comum."
    )
    t["s3.b5"] = (
        "**O que falta é você.** A base está completa, verificada e reconstruível com um comando, "
        "e a única coisa entre ela e a reunião são as doze decisões da seção 10. Responder "
        '"aceito os padrões provisórios" destrava as doze de uma vez.'
    )

    # ── 4. Em que regime estamos ─────────────────────────────────────────────
    t["s4.intro"] = (
        "Três lentes, três perguntas diferentes, três respostas. Elas não concordam, e a "
        "divergência é resultado, não defeito: com 4 a 19 observações por célula e erro-padrão de "
        "0,1 a 6,2 pontos percentuais, o topo de um ranking não é um fato estável."
    )
    t["s4.regra"] = (
        '**A regra de leitura.** A lente de quadrantes com dado revisado responde "como foi o '
        'histórico, com o dado de hoje": é a descritiva, e para o trimestre da sua pergunta ela '
        "não tem resposta, porque o eixo de crescimento exige uma média móvel de 20 trimestres e o "
        "trimestre corrente não fechou. O que se faz com isso é usar o último trimestre **com** "
        "quadrante, rotulado como substituto, nunca chamado de regime atual. A lente com o dado da "
        f'época responde "o que eu teria classificado no fim do trimestre": é a única com rótulo '
        f"para o {QUARTER_DA_PERGUNTA}, e é a que o critério escrito reprova. A lente de momentos "
        'semelhantes responde "quais trimestres dos 20 anos mais se parecem com este" e mede o '
        "trimestre seguinte a cada um deles."
    )
    t["s4.por_que_nao_escolhemos"] = (
        "**Por que não escolhemos uma.** Escolher a lente oficial é a decisão D1 da seção 10, e "
        "ela é sua. Escolher aqui, depois de ver os números, criaria uma versão nova da "
        "especificação com os dois resultados lado a lado, que é o oposto de uma base limpa. "
        "Enquanto a decisão não vier, as três aparecem com peso igual."
    )

    # ── 5. Momentos semelhantes ──────────────────────────────────────────────
    t["s5.intro"] = (
        f"A lente compara o {QUARTER_DA_PERGUNTA} com cada um dos 83 trimestres em "
        f"**{v3['features']['n_features']} variáveis** padronizadas (crescimento pelo Focus, "
        "aceleração da inflação, juro real, inclinação da curva e variação do dólar em 12 meses) e "
        "guarda os 8 mais próximos. A distância é a de Mahalanobis, que leva em conta a correlação "
        "entre as variáveis, com encolhimento de covariância medido, não escolhido."
    )
    t["s5.nota_vizinhos"] = (
        "Quatro dos oito vizinhos são de 2006 e 2007, e nenhum deles tem quadrante na lente de "
        "quadrantes, pelo mesmo motivo da seção 7: a crise de 2008 e o período que a antecede "
        "ficam fora daquele eixo. Isso é informação, não lacuna escondida: a coluna da direita "
        "declara célula por célula."
    )
    t["s5.nota_ranking"] = (
        "O retorno é medido no trimestre **seguinte** a cada vizinho, nunca no próprio vizinho. "
        "**A ordem desta tabela não é estatisticamente distinguível.** O primeiro colocado tem "
        f"{pct(topo_v3[0].excesso)} com erro-padrão de {pp(topo_v3[0].erro_padrao)}, o que o deixa "
        "a menos de dois erros-padrão de zero, e o mesmo vale para todos os outros que entregam "
        f"conclusão. As duas únicas linhas marcadas com asterisco são o pós-fixado em Selic, cujo "
        "excesso é zero por construção e por isso tem erro-padrão quase nulo, e fundos "
        "imobiliários, que tem n = 4 e sai **sem conclusão** justamente por isso. O número "
        'sustenta "este grupo rendeu mais que aquele, com esta incerteza", não "este foi o '
        'primeiro".'
    )
    t["s5.robustez"] = (
        "**O achado mais forte do levantamento está aqui:** a lista dos 8 vizinhos é exatamente a "
        "mesma quando se proíbe o sistema de olhar qualquer trimestre futuro. Com uma ressalva "
        f"honesta: o {QUARTER_DA_PERGUNTA} é o último trimestre da janela, então as duas versões "
        "coincidem por construção. Medido sobre as 58 referências que têm as duas, a coincidência "
        "típica é de 0,455 em escala de 0 a 1, ou seja, no caso comum mais da metade dos vizinhos "
        "troca. Citar só o trimestre do Comitê superestimaria a robustez da lente."
    )

    # ── 6. Mapa de calor ─────────────────────────────────────────────────────
    t["s6.intro"] = (
        "Cada célula é o **excesso médio sobre o CDI por trimestre** daquele índice naquele "
        "quadrante, calculado por razão e não por subtração, com o número de trimestres dentro da "
        "própria célula. Zero significa que o índice empatou com o CDI, e é por isso que a linha "
        "do CDI aparece em 0,00% em todas as colunas. Passe o mouse em qualquer célula para ver o "
        "erro-padrão, a mediana e em quantos trimestres aquele índice bateu o CDI."
    )
    t["s6.b1"] = (
        f"**Estagflação (n = {lentes.estagflacao[0].n}) é o quadrante mais seletivo do mapa.** "
        f"No topo, internacional em reais: {celula_de(lentes.estagflacao, 'SP500_BRL').nome} "
        f"{pct(celula_de(lentes.estagflacao, 'SP500_BRL').excesso)}, "
        f"{celula_de(lentes.estagflacao, 'ACWI_BRL').nome} "
        f"{pct(celula_de(lentes.estagflacao, 'ACWI_BRL').excesso)} e dólar "
        f"{pct(celula_de(lentes.estagflacao, 'USDBRL').excesso)}. No fundo, bolsa doméstica, com "
        f"seis índices abaixo de {pct(-0.04, casas=0)}."
    )
    t["s6.b2"] = (
        f"**Desaceleração (n = {lentes.desaceleracao[0].n}) inverte a ordem quase linha por "
        f"linha.** Dividendos {pct(celula_de(lentes.desaceleracao, 'IDIV').excesso)}, utilidade "
        f"pública {pct(celula_de(lentes.desaceleracao, 'UTIL').excesso)}, bancos "
        f"{pct(celula_de(lentes.desaceleracao, 'IFNC').excesso)} e energia elétrica "
        f"{pct(celula_de(lentes.desaceleracao, 'IEEX').excesso)} ocupam o topo, e o dólar vai para "
        f"o último lugar com {pct(celula_de(lentes.desaceleracao, 'USDBRL').excesso)}. A "
        "correlação negativa entre o dólar e a bolsa aparece aqui como troca de pontas."
    )
    t["s6.b3"] = (
        "**O internacional em reais fica acima do CDI nas quatro colunas de quadrante, e a "
        "distância é maior justamente nas duas em que o Ibovespa fica negativo**, expansão com "
        f"inflação e estagflação. Na estagflação são "
        f"{pct(celula_de(lentes.estagflacao, 'ACWI_BRL').excesso)} de ações globais em reais "
        f"contra {pct(celula_de(lentes.estagflacao, 'IBOV').excesso)} do Ibovespa, com "
        f"n = {lentes.estagflacao[0].n} nas duas células. Com erro-padrão de 2 a 5 pontos "
        "percentuais por célula, a ordem entre ativos não é estável; o **sinal** desse contraste, "
        "nesses dois quadrantes, é. É a leitura mais direta que a figura dá para a sua pergunta "
        "sobre o tamanho do internacional."
    )
    t["s6.b4"] = (
        "**As duas células mais altas do mapa estão no mesmo quadrante.** "
        f"{NOME_DO_ATIVO[maior['asset_id']]} em "
        f"{NOME_DO_REGIME[maior['regime']].lower()}, {pct(maior['excesso_cdi'])} com "
        f"n = {maior['n_obs']} e erro-padrão de {pp(maior['erro_padrao_media'])}, e "
        f"{NOME_DO_ATIVO[segunda['asset_id']]} no mesmo quadrante, "
        f"{pct(segunda['excesso_cdi'])} com n = {segunda['n_obs']}. Nos dois casos o índice bateu "
        f"o CDI em mais de 3 de cada 4 trimestres "
        f"({pct(maior['hit_ratio_cdi'], casas=1, sinal=False)} e "
        f"{pct(segunda['hit_ratio_cdi'], casas=1, sinal=False)})."
    )
    t["s6.b5"] = (
        f"**A célula mais baixa é {NOME_DO_ATIVO[menor['asset_id']].lower()} em "
        f"{NOME_DO_REGIME[menor['regime']].lower()}:** {pct(menor['excesso_cdi'])} por trimestre, "
        f"n = {menor['n_obs']}, erro-padrão de {pp(menor['erro_padrao_media'])} e apenas "
        f"{pct(menor['hit_ratio_cdi'], casas=1, sinal=False)} dos trimestres acima do CDI. Média "
        "muito negativa **e** consistente: é das poucas células do mapa em que as duas coisas "
        "andam juntas."
    )
    t["s6.b6"] = (
        "**Média alta e consistência não são a mesma coisa.** "
        f"{NOME_DO_ATIVO[recuperacao_imob['asset_id']]} em "
        f"{NOME_DO_REGIME[recuperacao_imob['regime']].lower()} tem a terceira maior média do mapa "
        f"({pct(recuperacao_imob['excesso_cdi'])}, n = {recuperacao_imob['n_obs']}), e dentro da "
        f"mesma célula está o pior trimestre isolado de todo o levantamento: "
        f"{pct(recuperacao_imob['pior_tri'], casas=1)} em "
        f"{trimestre_legivel(recuperacao_imob['pior_tri_quarter'])}. O erro-padrão de "
        f"{pp(recuperacao_imob['erro_padrao_media'])} é o maior do grupo de cima, e o hit contra "
        f"o CDI cai para {pct(recuperacao_imob['hit_ratio_cdi'], casas=1, sinal=False)}. É a linha "
        "de maior amplitude da figura, e isso é informação sobre sensibilidade a regime, não sobre "
        "qualidade do ativo."
    )
    t["s6.b7"] = (
        "**A renda fixa pública fica perto de zero em todos os quadrantes, e o CDI sai "
        "exatamente zero nas cinco colunas.** Nas três lentes, as oito linhas indexadas e "
        f"prefixadas vão de {pct(rf_min.excesso)} ({rf_min.nome}) a {pct(rf_max.excesso)} "
        f"({rf_max.nome}), com erro-padrão de {pp(min(rf_ep))} a {pp(max(rf_ep))}. Elas seguem o "
        "CDI de perto por construção, e a linha do CDI em zero é a conferência visual da própria "
        "métrica: é contra ela que o excesso de todo o resto é lido."
    )
    t["s6.b8"] = (
        "**Três células do mapa chamam atenção pela fragilidade, não pelo valor.** Fundos "
        "imobiliários e imobiliário na lente de momentos semelhantes têm n = 4 cada e saem "
        "hachurados, sem conclusão; consumo tem n = 6 e sai com alerta. De "
        f"{n_principal['celulas'] - 5} células desenhadas, "
        f"{n_principal['celulas'] - 5 - n_principal['celulas_com_alerta_n_baixo']} têm n maior ou "
        "igual a 8. A linha fica no mapa; a conclusão, não. E o S&P 500 em dólares foi retirado da "
        "figura de propósito: comparar retorno em dólar com o CDI em reais mistura duas moedas na "
        "mesma célula e a célula deixa de ter leitura. A linha não foi apagada do dado, continua "
        "na tabela da seção 8, e o rodapé da figura diz que saiu e por quê."
    )
    t["s6.nota_tabela"] = (
        "As duas abas abaixo são as mesmas células do mapa em forma de lista, ordenadas pelo "
        "excesso sobre o CDI. A primeira é o quadrante do último trimestre **com** quadrante no "
        "dado revisado, usado como substituto declarado; a segunda é o quadrante do "
        f"{QUARTER_DA_PERGUNTA} no dado da época. O erro-padrão destas duas tabelas é medido "
        "sobre o retorno nominal, que é o que a camada de métricas publica. Nas duas, o "
        "asterisco marca as linhas que ficam a mais de dois erros-padrão de zero: são "
        f"**{distinguiveis_estagflacao} de 24** na primeira aba e "
        f"**{distinguiveis_desaceleracao} de 24** na segunda. Para as outras, a posição na lista "
        "não é um resultado."
    )

    # ── 7. Linha do tempo ────────────────────────────────────────────────────
    t["s7.intro"] = (
        f"Os 83 trimestres, de 1T2006 a {QUARTER_DA_PERGUNTA}, cada um no seu quadrante. O eixo "
        "horizontal é o tempo; a faixa colorida é o quadrante; as duas linhas são os dois eixos "
        "que o definem, crescimento e aceleração da inflação."
    )
    t["s7.b1"] = (
        f"**2006 a 2009 ficam sem quadrante, e a crise de 2008 fica fora da lente.** São "
        f"{v1['indeterminados']['n']} trimestres, 1T2006 a 3T2009 mais o "
        f"{QUARTER_DA_PERGUNTA}. O motivo é mecânico: o eixo de crescimento é um hiato contra "
        "média móvel de 20 trimestres, e a série mensal de atividade do Banco Central começa em "
        "2004, então o primeiro hiato possível é o 4T2009. Para ter hiato em 2006 seria preciso a "
        "série desde 2000, e ela não existe. Nada foi estimado no lugar."
    )
    t["s7.b2"] = (
        "**2011 a 2015 são a sequência mais longa de um mesmo quadrante.** Estagflação quase "
        "contínua, com um intervalo de desaceleração entre o 4T2011 e o 2T2012, e um fundo de "
        "crescimento em 4T2015, quando o eixo chega a -6,40 pontos percentuais com a inflação em "
        "aceleração. É também o trecho em que a bolsa doméstica entrega as piores células do mapa."
    )
    t["s7.b3"] = (
        "**2016 inteiro é desaceleração, os quatro trimestres.** O eixo de crescimento sai de "
        "-6,12 para -1,91 pontos percentuais enquanto a inflação desacelera, o que é exatamente a "
        "definição do quadrante. É o ano do teto de gastos, e o quadrante que o histórico mostra "
        "como mais favorável a dividendos, utilidade pública e bancos."
    )
    t["s7.b4"] = (
        "**O 1T2020 é o ponto fraco desta lente, e vale dizer isso em voz alta.** Com o dado "
        "revisado, ele cai em **recuperação**: crescimento de +0,08 pontos percentuais e inflação "
        "desacelerando 1,01 ponto. Foi o trimestre em que a bolsa caiu 36,9% e o índice "
        "imobiliário 45,5%. O choque chegou no fim de março, o trimestre é medido pelo último dia "
        "útil e a lente é trimestral: um evento que se resolve dentro do trimestre não aparece no "
        "rótulo. Em 2020 a lente atravessa os quatro quadrantes em quatro trimestres."
    )
    t["s7.b5"] = (
        "**2021 e 2022 são expansão com inflação, com o maior crescimento da amostra.** O 2T2021 "
        "marca +12,22 pontos percentuais no eixo de crescimento, contra a base deprimida do "
        "2T2020: é efeito de base, não força econômica, e a lente descreve o que mediu. Quando a "
        "inflação desacelera forte no 3T2022 (-4,72 pontos), o rótulo vira recuperação."
    )
    t["s7.b6"] = (
        f"**A ponta.** 3T2025, 4T2025 e 1T2026 em desaceleração; 2T2026 em estagflação "
        "(crescimento de -1,15 ponto, inflação acelerando 0,50); e "
        f"{QUARTER_DA_PERGUNTA} **sem quadrante**, pelo motivo do primeiro item. O ranking que a "
        "seção 6 mostra na aba do dado revisado é o do 2T2026, e ele aparece rotulado como "
        "substituto porque é o que ele é."
    )

    # ── 8. Internacional ─────────────────────────────────────────────────────
    t["s8.intro"] = (
        "Três perguntas diferentes dentro do item C1 do seu e-mail: o dólar protege quando a bolsa "
        "cai, o exterior em reais rendeu quanto em cada regime, e qual é o tamanho. As duas "
        "primeiras têm resposta medida. A terceira tem resposta em faixa, e a razão está no fim "
        "desta seção. As linhas usadas são o dólar pela PTAX, o S&P 500 convertido pela mesma "
        "PTAX e o MSCI ACWI em reais, que é a linha representativa de ações globais."
    )
    t["s8.stress_regra"] = (
        f"**O que conta como trimestre de stress.** A regra é uma disjunção fixada antes de olhar "
        f"o resultado: queda da inclinação da curva de juros acima de um desvio-padrão da própria "
        f"série, **ou** alta do dólar acima de "
        f"{limite_do_dolar}% no trimestre. Com os dois "
        f"ramos, **{stress['n_stress']} dos {stress['n_trimestres']}** trimestres são de stress: "
        f"{stress['n_so_pelo_ramo_usdbrl']} só pelo dólar, "
        f"{stress['n_so_pelo_ramo_inclinacao']} só pela curva e {stress['n_pelos_dois_ramos']} "
        f"pelos dois. O terceiro ramo previsto, risco-país, está declaradamente fora: a série foi "
        "descontinuada em julho de 2024 e tem zero valores no período. E em "
        f"{len(stress['nao_avaliaveis_pelo_ramo_inclinacao'])} trimestres o ramo da curva não é "
        "avaliável, o que não é a mesma coisa que trimestre sem stress."
    )
    t["s8.stress_leitura"] = (
        "**A correlação do dólar com o Ibovespa é mais negativa justamente quando importa.** "
        f"{numero(blocos['stress']['correlacao'])} nos {blocos['stress']['n_pares']} trimestres de "
        f"stress contra {numero(blocos['nao_stress']['correlacao'])} nos "
        f"{blocos['nao_stress']['n_pares']} fora deles, e "
        f"{numero(blocos['dez_piores_do_ibov']['correlacao'])} nos "
        f"{blocos['dez_piores_do_ibov']['n_pares']} piores trimestres do Ibovespa. Nove desses dez "
        "piores estão entre os de stress, e isso foi conferido **depois** de a regra ser fixada, "
        "nunca usado para calibrá-la. Correlação condicional estimada em 20 trimestres tem "
        "erro-padrão largo: a diferença entre os dois blocos é grande, a terceira casa decimal "
        "não é."
    )
    t["s8.risk_off"] = (
        "**No trimestre seguinte a um trimestre de stress, tudo rendeu mais, inclusive a bolsa "
        "local.** Com n = 20 contra n = 62, o excesso médio sobre o CDI do Ibovespa sai de "
        f"{pct(risk_off['IBOV']['apos_nao_stress']['excesso_cdi_medio'])} para "
        f"{pct(risk_off['IBOV']['apos_stress']['excesso_cdi_medio'])}, o do S&P em reais de "
        f"{pct(risk_off['SP500_BRL']['apos_nao_stress']['excesso_cdi_medio'])} para "
        f"{pct(risk_off['SP500_BRL']['apos_stress']['excesso_cdi_medio'])} e o do dólar de "
        f"{pct(risk_off['USDBRL']['apos_nao_stress']['excesso_cdi_medio'])} para "
        f"{pct(risk_off['USDBRL']['apos_stress']['excesso_cdi_medio'])}. **A leitura "
        "contraintuitiva é esta: o dólar paga durante o stress, não depois.** O Ibovespa sobe "
        "quase tanto quanto o internacional no trimestre seguinte, e o dólar é o único índice da "
        "tabela com excesso negativo depois de trimestres calmos "
        f"({pct(risk_off['USDBRL']['apos_nao_stress']['excesso_cdi_medio'])} com n = "
        f"{risk_off['USDBRL']['apos_nao_stress']['n']}), que é o custo de carregar a proteção nos "
        "62 trimestres em que ela não é acionada. O dado não sustenta aumentar o internacional "
        "quando o sinal acende, que seria regra de timing; sustenta **carregar** a exposição "
        "cambial de forma estrutural. E leia tudo como descrição condicional a um evento já "
        "ocorrido: medir o trimestre seguinte a um evento é olhar para a frente por desenho, e "
        "isso está declarado como tal."
    )
    t["s8.neutralizacao"] = (
        "**Um terceiro ponto de referência, para dar ordem de grandeza.** Nos "
        f"{internacional['hedge_cambial']['stress_vs_nao_stress']['neutralizacao_usd']['n']} "
        "trimestres de stress, o Ibovespa rendeu em média "
        f"{pct(internacional['hedge_cambial']['stress_vs_nao_stress']['neutralizacao_usd']['ret_medio_ibov'])}"  # noqa: E501
        " e o dólar "
        f"{pct(internacional['hedge_cambial']['stress_vs_nao_stress']['neutralizacao_usd']['ret_medio_usdbrl'])}"  # noqa: E501
        ". Uma mistura com "
        f"{pct(internacional['hedge_cambial']['stress_vs_nao_stress']['neutralizacao_usd']['fracao_usd'], casas=1, sinal=False)}"  # noqa: E501
        " em dólar teria zerado o retorno **médio** dessa mistura nesses trimestres. É média de "
        "retornos, não garantia trimestre a trimestre, e não é posição nem carteira: é a conta "
        "aritmética que mostra por que a faixa fica onde fica."
    )
    t["s8.faixa"] = (
        "**O tamanho, e por que ele é uma faixa.** A entrega é um piso estrutural de "
        f"{pct(faixa['piso_estrutural']['min'], casas=0, sinal=False)} a "
        f"{pct(faixa['piso_estrutural']['max'], casas=0, sinal=False)} em exposição internacional "
        f"sem proteção cambial, mais uma banda tática de "
        f"{pct(faixa['banda_tatica']['min'], casas=0, sinal=False)} a "
        f"{pct(faixa['banda_tatica']['max'], casas=0, sinal=False)} que se move com o regime, "
        "com 13 a 19 observações por regime. Não é um número pontual, e a razão é aritmética: o "
        "cálculo de menor variância devolve média de "
        f"{pct(expanding['cap_0.40']['peso_internacional_medio_2006_2026'], casas=1, sinal=False)} "
        "na janela inteira quando se limita cada ativo a 40% da carteira, e de "
        f"{pct(expanding['cap_1.00']['peso_internacional_medio_2006_2026'], casas=1, sinal=False)} "
        "sem esse limite. Número que quase dobra conforme uma escolha de apresentação não é um "
        "número. A tabela de pesos por regime existe no dado, está marcada como não publicável "
        "nesta versão e por isso não aparece aqui."
    )
    t["s8.hedge"] = (
        "**Uma distinção que muda tudo na reunião:** exposição cambial e exposição global com "
        "proteção cambial são categorias diferentes. As referências de 16% a 35% tratam de "
        "exposição cambial, que é o que está medido aqui; as de 2,5% a 7% por perfil tratam de "
        "global com proteção. Comparar as duas é erro de leitura. A versão com proteção cambial "
        "ficou fora do levantamento porque exige a taxa de juros americana de curto prazo, e a "
        "fonte dela está bloqueada nesta máquina. Ouro em reais e Treasury em retorno total também "
        "ficaram fora, sem substituto."
    )
    t["s8.nota_tabela"] = (
        "As três colunas são as três respostas da seção 4. O S&P 500 em dólares aparece aqui, e "
        "não no mapa de calor, exatamente porque na tabela fica claro que a moeda é outra."
    )

    # ── 9. Limitacoes ────────────────────────────────────────────────────────
    t["s9.intro"] = (
        "Dez coisas que este levantamento não sustenta. Elas não estão aqui como nota de rodapé "
        "defensiva: duas delas são resultado, e uma delas provavelmente muda o que o Comitê vai "
        "fazer com a lente de quadrantes. A página completa, com o número de cada afirmação, vai "
        "no pacote como arquivo separado."
    )
    t["s9.fechamento"] = (
        "Nada disto é defeito de execução. É o que 20 anos de histórico brasileiro, com as fontes "
        "públicas que existem, sustentam e não sustentam. O pacote prefere declarar a lacuna a "
        "preenchê-la com estimativa."
    )

    # ── 10. Decisoes ─────────────────────────────────────────────────────────
    t["s10.intro"] = (
        "Doze decisões. Nenhuma destas respostas veio de uma pessoa: todas são o padrão provisório "
        "que a pesquisa aplicou para que a estrutura pudesse ser construída e o número existir. "
        "Virar qualquer uma é legítimo e previsto, e a coluna do meio diz o preço exato de virar. "
        "Só a primeira bloqueia a publicação; as outras onze são o aceite formal do que já está "
        "construído."
    )
    t["s10.como_responder"] = (
        '**O atalho:** responder "aceito os padrões provisórios" destrava as doze de uma vez, '
        "muda o estado da especificação de proposta para aceita e torna os números utilizáveis "
        "pelo fluxo formal de entrega. Se preferir ir item a item, a última coluna é para isso: "
        "ela imprime como campo em branco."
    )

    # ── 11. Rodape ───────────────────────────────────────────────────────────
    t["s11.como"] = (
        "**Como o número foi produzido, em três frases.** Cada fonte pública foi baixada uma vez, "
        "arquivada com data, endereço e impressão digital, e nunca mais tocada pela rede. O "
        "pipeline reconstrói os 83 trimestres a partir desse arquivo em treze etapas encadeadas, "
        "sem rede e sem credencial, e recalcula a impressão digital de todos os arquivos "
        "publicados ao final. Duas execuções consecutivas produziram os 47 arquivos byte a byte "
        "idênticos, com o mesmo identificador de conjunto."
    )
    t["s11.reconstruir"] = (
        "Tudo que está neste relatório é reconstruível com um comando, a partir do bruto "
        "arquivado, sem rede e sem senha. Hash diferente significa outro conjunto de dados: nunca "
        "compare números de rodadas diferentes sem conferir o identificador acima."
    )
    t["s11.assinatura"] = (
        f"{AUTOR}, {DATA_DO_RELATORIO}. Para {DESTINATARIO} e o Comitê de Alocação da LDC "
        f"Capital, reunião de {DATA_DO_COMITE}. Este documento descreve o que o histórico mostra, "
        "com o número de observações em cada afirmação. Não é previsão de retorno, não é backtest "
        "e não é indicação de carteira."
    )
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Conteudo tabular: o pedido, as limitacoes, as decisoes
# ─────────────────────────────────────────────────────────────────────────────

ENTREGUE = "entregue"
SUBSTITUIDO = "entregue com substituição"
FORA = "fora"

ITENS_DO_EMAIL: tuple[tuple[str, str, str, str], ...] = (
    (
        "A1",
        "PIB: prévia mensal do Banco Central ou PIB trimestral do IBGE",
        ENTREGUE,
        "Os dois, com ressalva: a prévia mensal começa em 2004, e o hiato de atividade só existe "
        "a partir do 4T2009.",
    ),
    (
        "A2",
        "IPCA mensal",
        ENTREGUE,
        "Série mensal do Banco Central, 2006 a 2026, sem lacuna.",
    ),
    (
        "A3",
        "Expectativas do Relatório Focus",
        ENTREGUE,
        "28.182 coletas em 5 séries (IPCA, PIB e Selic), de 2004 a 2026.",
    ),
    (
        "A4",
        "Histórico da Selic Over",
        ENTREGUE,
        "Selic Over e meta, acumuladas no trimestre pela convenção do próprio Banco Central.",
    ),
    (
        "A5",
        "Taxas dos títulos públicos",
        ENTREGUE,
        "Base pública do Tesouro Direto, 2004 até hoje.",
    ),
    (
        "A6",
        "Curva de juros histórica, para extrair a inclinação",
        SUBSTITUIDO,
        "A curva oficial com histórico só existe no produto pago da ANBIMA. A inclinação veio das "
        "taxas do Tesouro Direto, interpoladas: diferenças de 6 a 20 pontos-base contra a oficial, "
        "sempre no mesmo sentido.",
    ),
    (
        "A7",
        "IPCA histórico completo",
        ENTREGUE,
        "Série do IBGE mais a do Banco Central, conferidas uma contra a outra.",
    ),
    (
        "B1",
        "IMA-B, IMA-B 5 e IMA-B 5+ (desempenho do IPCA+)",
        ENTREGUE,
        "Repositório público da ANBIMA. Melhor que a rota do e-mail: as séries equivalentes no "
        "Banco Central foram descontinuadas em maio de 2023.",
    ),
    (
        "B2",
        "IRF-M, IRF-M 1 e IRF-M 1+ (desempenho dos prefixados)",
        ENTREGUE,
        "Mesma fonte do item anterior, série contínua e sem emenda.",
    ),
    (
        "B3",
        "CDI acumulado",
        ENTREGUE,
        "Taxa diária do Banco Central, acumulada por produto dentro de cada trimestre.",
    ),
    (
        "B4",
        "Setoriais e índices amplos da B3",
        ENTREGUE,
        "Os 9 pedidos mais utilidade pública, direto da B3. Consumo começa em 2007 e imobiliário "
        "em 2008: a janela de cada um está declarada na tabela.",
    ),
    (
        "B5",
        "IFIX e segmentações de fundos imobiliários",
        SUBSTITUIDO,
        "O IFIX entrou, a partir de 2011 (63 trimestres). Tijolo, papel, logística e shoppings "
        "ficaram fora: a B3 não publica índice setorial de fundos imobiliários, e o provedor "
        "privado identificado começa em 2019.",
    ),
    (
        "C1",
        "Dimensionamento da alocação internacional",
        SUBSTITUIDO,
        "Dólar, S&P 500 em dólares e em reais e ações globais em reais. Ouro, Treasury em retorno "
        "total e S&P com proteção cambial ficaram fora, sem substituto.",
    ),
)
"""Os 13 itens do e-mail: `(código, o que você pediu, status, o motivo em uma linha)`."""


LIMITACOES: tuple[tuple[str, str], ...] = (
    (
        "A classificação de regime troca de rótulo em 33% dos trimestres quando se usa só o que "
        "se sabia na época",
        "São 22 de 66 trimestres comparáveis. O limite escrito na metodologia é 25%. A "
        'consequência prática é direta: a lente de quadrantes responde bem "em que quadrante '
        'cada trimestre do histórico caiu", que é o entregável, e **não** responde de forma '
        'confiável "em que quadrante estamos agora". O motivo é mecânico: o hiato de atividade '
        "é pequeno, mediana de cerca de 2 pontos percentuais, sobre média móvel de 20 trimestres, "
        "e deslocar a série um trimestre troca o sinal com facilidade. É um piso, não o efeito "
        "total: a defasagem de divulgação está corrigida e verificada em 2.552 células, e a "
        "revisão retroativa do IBGE está declarada, porque a base tem uma única safra por série.",
    ),
    (
        "O número de observações é pequeno, e isso impede ordenar ativos",
        "Por célula o n vai de 4 a 19 trimestres, e o erro-padrão da média, de 0,1 a 6,2 pontos "
        "percentuais. Diferença de retorno menor que cerca de 2 erros-padrão é indistinguível de "
        "ruído. Na lente de momentos semelhantes, que é a mais interessante e a de menor amostra, "
        "**1 de 24** índices passa desse crivo. Traduzindo: a **ordem** do topo não é um "
        "resultado; o **sinal** de uma célula com n grande é. Duas travas automáticas cuidam "
        "disso: n abaixo de 8 entra com alerta, n abaixo de 5 sai sem conclusão.",
    ),
    (
        "A especificação dos regimes não está congelada",
        "Os eixos, o limiar de aceleração da inflação e o número de vizinhos ainda podem mudar. "
        "Mudar depois de ver estes números cria uma versão nova da especificação, com as duas "
        "lado a lado, e é assim que vai ser registrado. É a decisão D1 da seção 10.",
    ),
    (
        "A crise de 2008 fica fora do eixo de crescimento",
        "16 dos 83 trimestres não têm quadrante: 1T2006 a 3T2009 e o trimestre corrente. A série "
        "mensal de atividade começa em 2004 e a média móvel de 20 trimestres só fecha no 4T2009. "
        "A alternativa está medida: janela parcial recuperaria 12 trimestres, sem diferença no "
        "trecho comum, e não foi adotada porque é outro estimador, cujo significado muda ao longo "
        "do tempo.",
    ),
    (
        "Vinte anos de histórico brasileiro não são vinte anos do mesmo país",
        "A Selic saiu de cerca de 19% em 2006 para 2% em 2020 e voltou a dois dígitos, e o "
        "arcabouço mudou várias vezes no caminho. Daí três consequências: retorno nominal não é "
        "comparável entre épocas, e é por isso que a métrica principal é o excesso sobre o CDI; "
        "nível de juros como característica de regime confundiria época com regime; e a janela "
        "muda o resultado. Restringir ao pós-2016 troca **6 dos 8** momentos semelhantes do "
        "trimestre atual.",
    ),
    (
        "Índice não é ativo investível",
        "Todas as linhas são índices de carteira teórica, revisada periodicamente. Não há taxa de "
        "administração, corretagem, spread, imposto nem custo de rebalanceamento em nenhum "
        "número. Sharpe de índice não é Sharpe implementável, e a diferença é material justamente "
        "nas linhas mais ilíquidas: small caps, fundos imobiliários e setoriais estreitos.",
    ),
    (
        "Cada linha tem a sua própria janela, e o painel é desbalanceado de propósito",
        "Fundos imobiliários só existem desde 2011 (63 trimestres), imobiliário desde 2008 (75) e "
        "consumo desde 2007 (79); as outras 21 linhas têm 82. Qualquer afirmação sobre fundos "
        "imobiliários em 2006 a 2010, inclusive na crise de 2008, está fora de alcance. A "
        "alternativa era cortar toda a análise em 2011, e aí a janela de 20 anos do seu e-mail "
        "cairia.",
    ),
    (
        "A curva de juros é construída de taxas de varejo, não é a curva oficial",
        "A oficial com histórico está atrás de uma assinatura de R$ 686 a R$ 8.238 por mês, que "
        "não foi contratada. Contra a curva oficial de 9 de outubro, as diferenças são de 6 a 20 "
        "pontos-base, sempre no mesmo sentido: suficiente para medir inclinação, que é o uso "
        "pretendido, e insuficiente para bater na casa decimal. Nenhuma figura deste pacote chama "
        "isso de curva oficial. E a inclinação publicada é a **real**, de títulos indexados à "
        "inflação, não a nominal: em 2006 a ponta longa nominal não existia.",
    ),
    (
        "Parte dos índices entra sem a confirmação de que são retorno total",
        "A informação está indefinida em 820 linhas, que são os nove setoriais da B3 e o CDI. "
        "Comparar retorno total com retorno de preço superestima o segundo. Ibovespa e fundos "
        "imobiliários estão confirmados como retorno total; o S&P 500 em reais está declarado "
        "como retorno de preço. É lacuna aberta, não resolvida.",
    ),
    (
        "O que simplesmente não está aqui",
        "Não há backtest, otimização de carteira nem fronteira eficiente: backtest honesto exige "
        "janela móvel e é trabalho de semanas. Não há previsão, de regime ou de retorno. Não há "
        "carteira sugerida nem lista de compra: o ranking que existe é descritivo, e a decisão de "
        "alocação é sua. Ficaram fora também os fundos imobiliários por segmento, o risco-país "
        "(fonte descontinuada em 2024), os termos de troca (nenhum índice extraído, a variável "
        "existe e está 100% vazia, e isso está declarado), a lente de quadrante combinado com "
        "ciclo de Selic (12 estados com 5 a 15 observações cada, território onde o pacote suprime "
        "conclusão) e qualquer painel ou atualização automática.",
    ),
)
"""As 10 limitações em linguagem de gestor: `(manchete, o que ela custa)`."""


DECISOES: tuple[tuple[str, str, str, str], ...] = (
    (
        "D1",
        "Qual lente é a oficial",
        "Quadrantes como oficial, momentos semelhantes como leitura central, quadrante combinado "
        "com ciclo de Selic como secundária.",
        "Se a secundária virar oficial, a tabela principal passa a ter 12 estados com 5 a 15 "
        "observações e metade das células entra em alerta. Se os momentos semelhantes virarem "
        "oficiais, o entregável central passa a ser a lista de vizinhos. **Esta é a única que "
        "bloqueia a publicação.**",
    ),
    (
        "D3",
        "Qual é o eixo de inflação dos quadrantes",
        "Aceleração do IPCA, ou seja, a variação da taxa de 12 meses.",
        '"Nível contra a meta" exige a série histórica de metas do CMN, que não está na base, e '
        "os 83 rótulos mudam.",
    ),
    (
        "D5",
        "Qual é a métrica do mapa de calor",
        "Excesso sobre o CDI, calculado por razão.",
        "Nominal torna 2006 (Selic de 19%) e 2020 (Selic de 2%) incomparáveis; real muda a "
        "leitura. As três já existem como colunas: virar é trocar um parâmetro da figura.",
    ),
    (
        "D6",
        "Como o internacional é entregue",
        "Piso estrutural de 16% a 20% mais banda tática de 15% a 35% por regime.",
        '"Cem por cento tático" exigiria otimizar com cerca de 20 observações por regime e '
        "entregar número pontual, que esta base não sustenta.",
    ),
    (
        "D12",
        "Setoriais e fundos imobiliários no pacote mínimo",
        "Melhor esforço, com o n e a data de início visíveis em toda célula.",
        '"Completo" acrescenta extratores ao caminho crítico; "fora" reduz o mapa de calor.',
    ),
    (
        "L1",
        "Fundos imobiliários só desde 2011",
        "Janela própria de 2011 a 2026, com imobiliário (2008 em diante) como aproximação "
        "imperfeita antes disso. Sem série sintética.",
        "Exigir painel balanceado restringe **toda** a análise a 2011 a 2026, e a janela de 20 "
        "anos do seu e-mail cai.",
    ),
    (
        "L2",
        "Fundos imobiliários por segmento, via provedor privado",
        "Autorizado apenas como leitura qualitativa de dispersão, e não foi extraído.",
        "Se autorizado, entra como linha com cerca de 2 ciclos macro e sem valor inferencial. Se "
        "negado, o item B5 do e-mail fica formalmente não atendido na parte dos segmentos.",
    ),
    (
        "L4",
        "A curva oficial da ANBIMA é paga",
        "Não contratar; usar a curva do Tesouro Direto.",
        "Contratar dá a curva oficial, recalcula a inclinação histórica de 20 anos e muda o "
        "tratamento de risco do projeto, porque passa a envolver credencial.",
    ),
    (
        "D-i",
        "Qual inclinação de curva é a variável de regime",
        "Cinco anos menos três anos, que tem 95,25% de cobertura dos dias úteis desde 2006.",
        "Voltar a cinco anos menos um ano devolve uma variável com 60,53% de cobertura: cerca de "
        "40% dos trimestres cairiam num dia sem valor.",
    ),
    (
        "D-s",
        "Qual é o nível trimestral da prévia de atividade",
        "Média dos três meses do trimestre.",
        "Voltar ao último mês devolve a distribuição anterior, e 7 trimestres mudam de quadrante "
        "de volta.",
    ),
    (
        "D-t",
        "Um movimento de 25 pontos-base na Selic é ciclo ou parada",
        "É ciclo, nos dois sentidos. A distribuição medida fica em 34 cortes, 23 paradas e 26 "
        "altas.",
        "Com a leitura estrita, os 7 movimentos de exatamente 25 pontos-base do período voltam a "
        "ser parada, e são 5 cortes e 2 altas, entre elas a alta de setembro de 2024 que abriu o "
        "ciclo de aperto.",
    ),
    (
        "D-u",
        "Qual é o eixo de crescimento da lente de momentos semelhantes",
        "Expectativa de PIB do Focus.",
        "Sem o Focus a lente não tem vetor para o trimestre atual, que é exatamente o trimestre "
        "da sua pergunta, e perde 2006 a 2009.",
    ),
)
"""As 12 decisões: `(código, decisão, padrão provisório, o que muda se você discordar)`."""


# ─────────────────────────────────────────────────────────────────────────────
# Renderizacao
# ─────────────────────────────────────────────────────────────────────────────

_RE_FORTE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)

SECOES: tuple[tuple[str, str], ...] = (
    ("s1-topo", "O relatório"),
    ("s2-pedido", "O que você pediu e o que chegou"),
    ("s3-resposta", "A resposta curta, em cinco linhas"),
    ("s4-regime", "Em que regime estamos"),
    ("s5-momentos", "Momentos semelhantes ao de hoje"),
    ("s6-heatmap", "Como cada ativo foi em cada regime"),
    ("s7-timeline", "A linha do tempo dos 83 trimestres"),
    ("s8-internacional", "Quanto levar para fora do Brasil"),
    ("s9-limites", "O que isto não diz"),
    ("s10-decisoes", "O que eu preciso de você"),
    ("s11-rodape", "Como o número foi produzido"),
)
"""Os 11 blocos, na ordem em que aparecem. O teste de estrutura compara contra esta tupla."""


def inline(texto: str) -> str:
    """Escapa o texto e converte a única marcação permitida, `**forte**`, em `<strong>`."""
    return _RE_FORTE.sub(r"<strong>\1</strong>", html.escape(texto, quote=False))


def _marcador(*indices: int) -> str:
    """O marcador de fonte, `[2]` ou `[2][3]`, que liga o número à legenda do rodapé."""
    partes = "".join(f'<a href="#fontes">[{i}]</a>' for i in indices)
    return f'<span class="fonte">{partes}</span>'


def _celula_numerica(texto: str, *, destaque: bool = False) -> str:
    classe = "num forte" if destaque else "num"
    return f'<td class="{classe}">{html.escape(texto, quote=False)}</td>'


def _marca_de_n(celula: Celula) -> str:
    if celula.suprimida:
        return '<span class="marca-n" title="n abaixo de 5: a linha fica, a conclusao nao">sem conclusão</span>'  # noqa: E501
    if celula.alerta:
        return '<span class="marca-n" title="n abaixo de 8: entra com alerta">alerta</span>'
    return ""


def tabela_de_ranking(celulas: Sequence[Celula], *, legenda: str, fontes: str) -> str:
    """Uma lente em forma de lista: 24 linhas, o `n` em cada uma, nenhuma coluna decorativa."""
    linhas: list[str] = []
    for posicao, celula in enumerate(celulas, start=1):
        marca = _marca_de_n(celula)
        nome = html.escape(celula.nome, quote=False)
        distingue = ' title="media a mais de 2 erros-padrao de zero"' if celula.distinguivel else ""
        estrela = f'<span class="estrela"{distingue}>*</span>' if celula.distinguivel else ""
        linhas.append(
            "<tr>"
            f'<td class="num posicao">{posicao}</td>'
            f"<td>{nome} {marca}</td>"
            + _celula_numerica(pct(celula.excesso), destaque=True).replace(
                "</td>", f"{estrela}</td>"
            )
            + _celula_numerica(
                pct(celula.hit_ratio_cdi, casas=0, sinal=False)
                if celula.hit_ratio_cdi is not None
                else "sem valor"
            )
            + _celula_numerica(str(celula.n))
            + _celula_numerica(pp(celula.erro_padrao))
            + "</tr>"
        )
    return (
        '<div class="rolagem"><table>'
        "<caption>" + inline(legenda) + "</caption>"
        "<thead><tr>"
        '<th class="num">#</th><th>Índice</th>'
        '<th class="num">Excesso sobre o CDI por trimestre</th>'
        '<th class="num">Trimestres acima do CDI</th>'
        '<th class="num">n</th>'
        '<th class="num">Erro-padrão da média</th>'
        "</tr></thead><tbody>" + "".join(linhas) + "</tbody></table></div>"
        f'<p class="nota">Fonte: {fontes}. O asterisco marca as médias a mais de 2 erros-padrão '
        "de zero; sem ele, a diferença não se distingue de ruído.</p>"
    )


def _cabecalho_de_secao(numero: int, titulo: str) -> str:
    return (
        f'<p class="olho">Seção {numero} de {len(SECOES)}</p>'
        f"<h2>{html.escape(titulo, quote=False)}</h2>"
    )


def _secao(indice: int, corpo: str) -> str:
    identificador, titulo = SECOES[indice]
    return (
        f'<section id="{identificador}">'
        + _cabecalho_de_secao(indice + 1, titulo)
        + corpo
        + "</section>"
    )


def _bullets(textos: Mapping[str, str], chaves: Sequence[str]) -> str:
    itens = "".join(f"<li>{inline(textos[chave])}</li>" for chave in chaves)
    return f'<ul class="lista">{itens}</ul>'


def _p(conteudo: str, *, classe: str = "") -> str:
    atributo = f' class="{classe}"' if classe else ""
    return f"<p{atributo}>{conteudo}</p>"


# ─────────────────────────────────────────────────────────────────────────────
# As 11 secoes
# ─────────────────────────────────────────────────────────────────────────────


def _s1_topo(dados: Dados, t: Mapping[str, str], curto: str, completo: str) -> str:
    estado = dados.estado
    classe = "faixa-estado" if not estado.congelada else "faixa-estado faixa-congelada"
    corpo = (
        f'<div class="{classe}" role="note">'
        f'<p class="faixa-rotulo">{html.escape(estado.rotulo, quote=False)}</p>'
        + _p(inline(t["s1.faixa"]))
        + "</div>"
        f"<h1>{html.escape(TITULO, quote=False)}</h1>"
        + _p(html.escape(SUBTITULO, quote=False), classe="subtitulo")
        + '<dl class="ficha">'
        f"<dt>Para</dt><dd>{html.escape(DESTINATARIO, quote=False)}, e o Comitê de Alocação</dd>"
        f"<dt>De</dt><dd>{html.escape(AUTOR, quote=False)}</dd>"
        f"<dt>Data</dt><dd>{html.escape(DATA_DO_RELATORIO, quote=False)}</dd>"
        f"<dt>Reunião</dt><dd>{html.escape(DATA_DO_COMITE, quote=False)}</dd>"
        f'<dt>Conjunto de dados</dt><dd><span class="mono">{curto}</span> '
        f'<span class="nota-inline">({completo[:16]}...)</span></dd>'
        "</dl>"
        + _p(inline(t["s1.abertura"]))
        + _p(inline(t["s1.como_ler"]), classe="nota")
        + '<p class="acoes"><button type="button" class="so-com-js" id="expandir">'
        "Expandir todos os blocos</button></p>"
    )
    return _secao(0, corpo)


def _s2_pedido(t: Mapping[str, str]) -> str:
    linhas: list[str] = []
    for codigo, pedido, status, motivo in ITENS_DO_EMAIL:
        classe = {ENTREGUE: "ok", SUBSTITUIDO: "trocado", FORA: "ausente"}[status]
        linhas.append(
            "<tr>"
            f'<td class="mono">{codigo}</td>'
            f"<td>{html.escape(pedido, quote=False)}</td>"
            f'<td><span class="selo selo-{classe}">{html.escape(status, quote=False)}</span></td>'
            f"<td>{html.escape(motivo, quote=False)}</td>"
            "</tr>"
        )
    corpo = (
        _p(inline(t["s2.intro"])) + '<div class="rolagem"><table class="larga">'
        "<thead><tr><th>Item</th><th>O que você pediu</th><th>Status</th>"
        "<th>O motivo, em uma linha</th></tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody></table></div>"
        + _p(inline(t["s2.nota"]) + " " + _marcador(5, 6), classe="nota")
    )
    return _secao(1, corpo)


def _s3_resposta(t: Mapping[str, str]) -> str:
    corpo = _bullets(t, ["s3.b1", "s3.b2", "s3.b3", "s3.b4", "s3.b5"]) + _p(
        "Fontes desta seção: " + _marcador(2, 3, 4) + ".", classe="nota"
    )
    return _secao(2, corpo)


def _s4_regime(dados: Dados, t: Mapping[str, str], lentes: Lentes) -> str:
    metricas = dados.rel("metricas")
    v3 = dados.rel("regimes_v3")
    atual = metricas["regime_atual"]
    divergencia = dados.rel("regimes_v1")["divergencia_asof_vs_revised"]
    cartoes = (
        (
            "Quadrantes, dado revisado",
            "Sem quadrante",
            f"O eixo de crescimento não existe para o {QUARTER_DA_PERGUNTA}: ele exige média móvel "
            "de 20 trimestres e o trimestre corrente não fechou. Nenhum quadrante foi estimado no "
            "lugar.",
            f"O ranking sai do substituto declarado "
            f"{trimestre_legivel(atual['fallback_declarado']['quarter'])}, que é "
            f"{NOME_DO_REGIME[atual['fallback_declarado']['regime']].lower()}, com n = "
            f"{lentes.estagflacao[0].n}.",
        ),
        (
            "Quadrantes, dado da época",
            NOME_DO_REGIME[atual["v1_asof"]["regime"]],
            "É a única lente com um rótulo para o trimestre da pergunta, obtido sobre o dado como "
            "ele era conhecido no fim do trimestre.",
            "É justamente a que o critério escrito reprova: "
            f"{_virgula(format(divergencia['pct_que_trocam'] * 100, '.2f'))}% dos "
            f"{divergencia['trimestres_comparaveis']} trimestres comparáveis trocam de rótulo "
            f"entre as duas versões, contra um limite de "
            f"{_virgula(format(divergencia['limiar_inoperante'] * 100, '.0f'))}%. n = "
            f"{lentes.desaceleracao[0].n}.",
        ),
        (
            "Momentos semelhantes",
            "Lista de 8 vizinhos",
            f"Os {v3['vizinhos_do_comite']['lente']['k']} trimestres mais próximos do "
            f"{QUARTER_DA_PERGUNTA} em "
            f"{v3['features']['n_features']} variáveis macro padronizadas.",
            "É a lente de menor amostra da página: n = 4, 6 ou 8 por índice, e só 1 de 24 passa "
            "o crivo de 2 erros-padrão.",
        ),
    )
    blocos = "".join(
        f'<div class="lente">'
        f'<p class="olho">{html.escape(rotulo, quote=False)}</p>'
        f'<p class="resposta">{html.escape(resposta, quote=False)}</p>'
        f"<p>{html.escape(como, quote=False)}</p>"
        f'<p class="nota">{html.escape(ressalva, quote=False)}</p>'
        "</div>"
        for rotulo, resposta, como, ressalva in cartoes
    )
    corpo = (
        _p(inline(t["s4.intro"]))
        + f'<div class="tres-lentes">{blocos}</div>'
        + _p(inline(t["s4.regra"]))
        + _p(inline(t["s4.por_que_nao_escolhemos"]))
        + _p(
            "Nos cinco primeiros colocados das três lentes, a interseção é vazia: "
            "<strong>nenhum índice aparece nas três</strong>. " + _marcador(1, 2, 3),
            classe="nota",
        )
    )
    return _secao(3, corpo)


def _s5_momentos(dados: Dados, t: Mapping[str, str], lentes: Lentes) -> str:
    v3 = dados.rel("regimes_v3")
    vizinhos = v3["vizinhos_do_comite"]["vizinhos"]
    referencia = v3["vizinhos_do_comite"]["macro_da_referencia"]
    linhas: list[str] = []
    for item in vizinhos:
        macro = item["macro"]
        rotulo = item.get("regime_v1_neighbor")
        quadrante = NOME_DO_REGIME[rotulo] if rotulo else "sem quadrante"
        linhas.append(
            "<tr>"
            f'<td class="num posicao">{item["rank"]}</td>'
            f'<td class="mono">{trimestre_legivel(str(item["quarter_neighbor"]))}</td>'
            + _celula_numerica(numero(float(item["distancia"])))
            + _celula_numerica(_virgula(f"{float(macro['z_crescimento_esperado']):+.2f}") + "%")
            + _celula_numerica(pp_de_pp(float(macro["z_ipca_12m_delta"])))
            + _celula_numerica(_virgula(f"{float(macro['z_juro_real_exante']):.2f}") + "%")
            + _celula_numerica(_virgula(f"{float(macro['z_usdbrl_var_12m']):+.1f}") + "%")
            + f'<td class="mono">{trimestre_legivel(str(item["quarter_t_mais_1"]))}</td>'
            f"<td>{html.escape(quadrante, quote=False)}</td>"
            "</tr>"
        )
    cabecalho = (
        "<thead><tr>"
        '<th class="num">#</th><th>Trimestre</th>'
        '<th class="num">Distância</th>'
        '<th class="num">Crescimento no Focus</th>'
        '<th class="num">Aceleração do IPCA</th>'
        '<th class="num">Juro real</th>'
        '<th class="num">Dólar em 12 meses</th>'
        "<th>Trimestre medido</th><th>Quadrante do vizinho</th>"
        "</tr></thead>"
    )
    referencia_linha = (
        '<tr class="referencia">'
        f'<td class="num posicao"></td>'
        f'<td class="mono">{QUARTER_DA_PERGUNTA}</td>'
        + _celula_numerica("referência")
        + _celula_numerica(_virgula(f"{float(referencia['z_crescimento_esperado']):+.2f}") + "%")
        + _celula_numerica(pp_de_pp(float(referencia["z_ipca_12m_delta"])))
        + _celula_numerica(_virgula(f"{float(referencia['z_juro_real_exante']):.2f}") + "%")
        + _celula_numerica(_virgula(f"{float(referencia['z_usdbrl_var_12m']):+.1f}") + "%")
        + "<td></td><td>sem quadrante</td>"
        "</tr>"
    )
    corpo = (
        _p(inline(t["s5.intro"]))
        + '<div class="rolagem"><table class="larga"><caption>'
        + inline(
            f"Os 8 trimestres mais parecidos com o {QUARTER_DA_PERGUNTA}, e o que o macro tinha "
            "em cada um deles"
        )
        + "</caption>"
        + cabecalho
        + f"<tbody>{referencia_linha}{''.join(linhas)}</tbody></table></div>"
        + _p("Fonte: " + _marcador(2) + ".", classe="nota")
        + _p(inline(t["s5.nota_vizinhos"]))
        + "<h3>O que rendeu no trimestre seguinte a cada um deles</h3>"
        + _p(inline(t["s5.nota_ranking"]))
        + tabela_de_ranking(
            lentes.vizinhos,
            legenda=(
                "Excesso sobre o CDI no trimestre seguinte a cada um dos 8 vizinhos. O "
                "erro-padrão desta tabela é medido sobre o próprio excesso."
            ),
            fontes=_marcador(2),
        )
        + _p(inline(t["s5.robustez"]))
    )
    return _secao(4, corpo)


def _s6_heatmap(dados: Dados, t: Mapping[str, str], lentes: Lentes) -> str:
    atual = dados.rel("metricas")["regime_atual"]
    abas = (
        (
            "revisado",
            f"{NOME_DO_REGIME[atual['fallback_declarado']['regime']]} "
            f"({trimestre_legivel(atual['fallback_declarado']['quarter'])}, dado revisado)",
            tabela_de_ranking(
                lentes.estagflacao,
                legenda=(
                    "Quadrante do último trimestre com classificação no dado revisado, usado como "
                    "**substituto declarado**, nunca como o regime do trimestre atual."
                ),
                fontes=_marcador(3),
            ),
        ),
        (
            "epoca",
            f"{NOME_DO_REGIME[atual['v1_asof']['regime']]} ({QUARTER_DA_PERGUNTA}, dado da época)",
            tabela_de_ranking(
                lentes.desaceleracao,
                legenda=(
                    "Quadrante do trimestre atual sobre o dado como ele era conhecido no fim do "
                    "trimestre. É a lente que o critério de estabilidade de rótulo **reprova**."
                ),
                fontes=_marcador(3),
            ),
        ),
    )
    controles = "".join(
        f'<input type="radio" name="aba-lente" id="aba-{chave}" class="aba-radio"'
        f"{' checked' if indice == 0 else ''}>"
        for indice, (chave, _, _) in enumerate(abas)
    )
    rotulos = "".join(
        f'<label for="aba-{chave}" class="aba-rotulo">{html.escape(rotulo, quote=False)}</label>'
        for chave, rotulo, _ in abas
    )
    paineis = "".join(
        f'<div class="aba-painel" id="painel-{chave}">'
        f'<h4 class="so-na-impressao">{html.escape(rotulo, quote=False)}</h4>{conteudo}</div>'
        for chave, rotulo, conteudo in abas
    )
    corpo = (
        _p(inline(t["s6.intro"]))
        + '<figure class="figura">'
        + dados.figuras["heatmap"]
        + "<figcaption>Excesso médio sobre o CDI por trimestre, por quadrante macro e por índice. "
        "Zero significa empate com o CDI. O número de trimestres aparece em cada célula; células "
        "hachuradas têm menos de 5 observações e saem sem conclusão. "
        + _marcador(3)
        + "</figcaption></figure>"
        + "<h3>A leitura, em oito pontos</h3>"
        + _bullets(t, [f"s6.b{indice}" for indice in range(1, 9)])
        + _p("Fontes: " + _marcador(3) + ".", classe="nota")
        + "<h3>As mesmas células em forma de lista</h3>"
        + _p(inline(t["s6.nota_tabela"]))
        + f'<div class="abas">{controles}<div class="aba-barra">{rotulos}</div>'
        f'<div class="aba-paineis">{paineis}</div></div>'
    )
    return _secao(5, corpo)


def _s7_timeline(dados: Dados, t: Mapping[str, str]) -> str:
    v1 = dados.rel("regimes_v1")
    distribuicao = v1["trimestres_por_regime"]
    linhas = "".join(
        "<tr>"
        f"<td>{html.escape(NOME_DO_REGIME[regime], quote=False)}</td>"
        + _celula_numerica(str(len(distribuicao[regime])))
        + f"<td>{html.escape(exemplo, quote=False)}</td>"
        "</tr>"
        for regime, exemplo in (
            ("RECUPERACAO", "4T2009, 2017 inteiro, 3T2022 a 2T2023"),
            ("EXPANSAO_INFL", "1T2010, 2021, 3T2024 a 1T2025"),
            ("ESTAGFLACAO", "2011 a 2015, 3T2020, 2T2026"),
            ("DESACELERACAO", "4T2011 a 2T2012, 2016 inteiro, 3T2025 a 1T2026"),
            ("INDETERMINADO", f"1T2006 a 3T2009 e o {QUARTER_DA_PERGUNTA}"),
        )
    )
    corpo = (
        _p(inline(t["s7.intro"]))
        + '<figure class="figura">'
        + dados.figuras["timeline"]
        + "<figcaption>Os 83 trimestres e o quadrante de cada um, com os dois eixos que o "
        "definem. "
        + _marcador(1)
        + "</figcaption></figure>"
        + "<h3>A leitura econômica</h3>"
        + _bullets(t, [f"s7.b{indice}" for indice in range(1, 7)])
        + '<div class="rolagem"><table>'
        "<caption>Quantos trimestres em cada quadrante, e onde eles estão</caption>"
        '<thead><tr><th>Quadrante</th><th class="num">Trimestres</th>'
        "<th>Onde eles estão</th></tr></thead>"
        f"<tbody>{linhas}</tbody></table></div>" + _p("Fonte: " + _marcador(1) + ".", classe="nota")
    )
    return _secao(6, corpo)


def _s8_internacional(dados: Dados, t: Mapping[str, str], lentes: Lentes) -> str:
    internacional = dados.rel("internacional")
    blocos = internacional["hedge_cambial"]["stress_vs_nao_stress"]["blocos"]
    risk_off = internacional["risk_off"]["por_ativo"]
    ordem_blocos = (
        ("stress", "Trimestres de stress"),
        ("nao_stress", "Trimestres fora do stress"),
        ("dez_piores_do_ibov", "Os 10 piores trimestres do Ibovespa"),
        ("todos", "Todos os trimestres"),
    )
    linhas_corr = "".join(
        "<tr>"
        f"<td>{html.escape(rotulo, quote=False)}</td>"
        + _celula_numerica(numero(float(blocos[chave]["correlacao"])), destaque=True)
        + _celula_numerica(str(blocos[chave]["n_pares"]))
        + "</tr>"
        for chave, rotulo in ordem_blocos
    )
    internacionais = ("USDBRL", "SP500_BRL", "ACWI_BRL", "IBOV", "IMAB", "CDI")
    linhas_risk = "".join(
        "<tr>"
        f"<td>{html.escape(NOME_DO_ATIVO[ativo], quote=False)}</td>"
        + _celula_numerica(pct(risk_off[ativo]["apos_stress"]["excesso_cdi_medio"]), destaque=True)
        + _celula_numerica(str(risk_off[ativo]["apos_stress"]["n"]))
        + _celula_numerica(pct(risk_off[ativo]["apos_nao_stress"]["excesso_cdi_medio"]))
        + _celula_numerica(str(risk_off[ativo]["apos_nao_stress"]["n"]))
        + "</tr>"
        for ativo in internacionais
    )
    por_lente = (
        ("SP500_BRL",),
        ("ACWI_BRL",),
        ("USDBRL",),
        ("SP500_USD",),
    )
    linhas_lentes: list[str] = []
    for (ativo,) in por_lente:
        estag = celula_de(lentes.estagflacao, ativo)
        desac = celula_de(lentes.desaceleracao, ativo)
        viz = celula_de(lentes.vizinhos, ativo)
        linhas_lentes.append(
            "<tr>"
            f"<td>{html.escape(NOME_DO_ATIVO[ativo], quote=False)}</td>"
            + _celula_numerica(pct(estag.excesso), destaque=True)
            + _celula_numerica(str(estag.n))
            + _celula_numerica(pct(desac.excesso), destaque=True)
            + _celula_numerica(str(desac.n))
            + _celula_numerica(pct(viz.excesso), destaque=True)
            + _celula_numerica(str(viz.n))
            + "</tr>"
        )
    corpo = (
        _p(inline(t["s8.intro"]))
        + "<h3>O dólar como proteção, medido</h3>"
        + _p(inline(t["s8.stress_regra"]))
        + '<div class="rolagem"><table>'
        "<caption>Correlação do dólar com o Ibovespa, por bloco de trimestres</caption>"
        '<thead><tr><th>Bloco</th><th class="num">Correlação</th>'
        '<th class="num">n de pares</th></tr></thead>'
        f"<tbody>{linhas_corr}</tbody></table></div>"
        + _p("Fonte: " + _marcador(4) + ".", classe="nota")
        + _p(inline(t["s8.stress_leitura"]))
        + "<h3>O trimestre seguinte a um trimestre de stress</h3>"
        + _p(inline(t["s8.risk_off"]))
        + '<div class="rolagem"><table class="larga">'
        "<caption>Excesso médio sobre o CDI no trimestre seguinte, dentro e fora do stress"
        "</caption>"
        '<thead><tr><th>Índice</th><th class="num">Depois de stress</th>'
        '<th class="num">n</th><th class="num">Depois de trimestre normal</th>'
        '<th class="num">n</th></tr></thead>'
        f"<tbody>{linhas_risk}</tbody></table></div>"
        + _p("Fonte: " + _marcador(4) + ".", classe="nota")
        + _p(inline(t["s8.neutralizacao"]))
        + "<h3>O internacional em cada uma das três respostas de regime</h3>"
        + _p(inline(t["s8.nota_tabela"]))
        + '<div class="rolagem"><table class="larga">'
        "<caption>Excesso sobre o CDI das linhas internacionais, por lente</caption>"
        "<thead><tr><th>Índice</th>"
        '<th class="num">Estagflação</th><th class="num">n</th>'
        '<th class="num">Desaceleração</th><th class="num">n</th>'
        '<th class="num">Momentos semelhantes</th><th class="num">n</th></tr></thead>'
        f"<tbody>{''.join(linhas_lentes)}</tbody></table></div>"
        + _p("Fontes: " + _marcador(3, 4) + ".", classe="nota")
        + "<h3>O tamanho</h3>"
        + _p(inline(t["s8.faixa"]))
        + _p(inline(t["s8.hedge"]), classe="nota")
    )
    return _secao(7, corpo)


def _s9_limites(t: Mapping[str, str]) -> str:
    itens = "".join(
        f"<details><summary>{inline(manchete)}</summary>{_p(inline(detalhe))}</details>"
        for manchete, detalhe in LIMITACOES
    )
    corpo = (
        _p(inline(t["s9.intro"]))
        + f'<div class="acordeao">{itens}</div>'
        + _p(inline(t["s9.fechamento"]))
        + _p("Fontes desta seção: " + _marcador(1, 2, 3, 4, 5, 6) + ".", classe="nota")
    )
    return _secao(8, corpo)


def _s10_decisoes(t: Mapping[str, str]) -> str:
    linhas = "".join(
        "<tr>"
        f'<td class="mono">{html.escape(codigo, quote=False)}</td>'
        f"<td>{html.escape(decisao, quote=False)}</td>"
        f"<td>{html.escape(padrao, quote=False)}</td>"
        f"<td>{inline(custo)}</td>"
        '<td class="resposta-vazia"><span class="linha-de-resposta"></span></td>'
        "</tr>"
        for codigo, decisao, padrao, custo in DECISOES
    )
    corpo = (
        _p(inline(t["s10.intro"])) + '<div class="rolagem"><table class="larga decisoes">'
        "<thead><tr><th>#</th><th>Decisão</th><th>Padrão provisório adotado</th>"
        "<th>O que muda se você discordar</th><th>Sua resposta</th></tr></thead>"
        f"<tbody>{linhas}</tbody></table></div>" + _p(inline(t["s10.como_responder"]))
    )
    return _secao(9, corpo)


def _s11_rodape(dados: Dados, t: Mapping[str, str], curto: str, completo: str) -> str:
    fontes = "".join(
        f'<li><span class="fonte">[{indice}]</span> '
        f"{html.escape(descricao, quote=False)} "
        f'<span class="mono quebra nota-inline">{html.escape(arquivo, quote=False)}</span></li>'
        for indice, (_, arquivo, descricao) in enumerate(RELATORIOS, start=1)
    )
    corpo = (
        _p(inline(t["s11.como"])) + '<dl class="ficha">'
        f'<dt>Conjunto de dados</dt><dd><span class="mono quebra">{completo}</span></dd>'
        f'<dt>Identificador curto</dt><dd><span class="mono">{curto}</span></dd>'
        f"<dt>Primeiro trimestre</dt><dd>1T2006</dd>"
        f"<dt>Último trimestre</dt><dd>{QUARTER_DA_PERGUNTA}</dd>"
        '<dt>Reconstrução</dt><dd><span class="mono quebra">'
        "uv run python -m apps.pipeline run --offline</span></dd>"
        "</dl>"
        + _p(inline(t["s11.reconstruir"]))
        + f'<h3 id="fontes">De onde vem cada número</h3><ol class="fontes">{fontes}</ol>'
        + _p(inline(t["s11.assinatura"]), classe="assinatura")
    )
    return _secao(10, corpo)


# ─────────────────────────────────────────────────────────────────────────────
# CSS e JS: embutidos, com os tokens da LDC
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
:root{
  --navy:#262d3d; --slate:#577171; --lime:#98ab44; --lime-claro:#becc6a; --alerta:#c0584f;
  --linha:#e6e8ea; --track:#eceef0; --grid:#f0f2f3; --painel:#fcfdfd; --fundo:#f4f6f6;
  --sans:"Public Sans","Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SFMono-Regular","Consolas","Liberation Mono",monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--fundo);color:var(--navy);font-family:var(--sans);
  font-size:16px;line-height:1.55;font-variant-numeric:tabular-nums;
}
.pagina{max-width:1000px;margin:0 auto;padding:0 16px 64px}
section{padding:32px 0;border-top:1px solid var(--linha)}
section:first-of-type{border-top:0;padding-top:28px}
h1{font-size:30px;line-height:1.2;font-weight:700;letter-spacing:-0.01em;margin:20px 0 8px}
h2{font-size:22px;line-height:1.25;font-weight:700;letter-spacing:-0.01em;margin:4px 0 14px}
h3{font-size:16px;font-weight:700;margin:28px 0 8px}
h4{font-size:14px;font-weight:700;margin:16px 0 6px}
p{margin:0 0 12px}
.olho{
  font-size:11px;text-transform:uppercase;letter-spacing:0.14em;color:var(--slate);
  font-weight:700;margin:0 0 6px;
}
.subtitulo{font-size:17px;color:var(--slate);margin-bottom:18px;max-width:62ch}
.nota{font-size:13.5px;color:var(--slate)}
.nota-inline{font-size:12px;color:var(--slate)}
.mono{font-family:var(--mono);font-size:12.5px;white-space:nowrap}
.mono.quebra{word-break:break-all;white-space:normal}
a{color:var(--navy)}
strong{font-weight:700}
.lista{margin:0 0 14px;padding-left:20px}
.lista li{margin-bottom:12px;max-width:80ch}
.faixa-estado{
  background:rgba(192,88,79,0.08);border:1px solid rgba(192,88,79,0.18);
  border-radius:4px;padding:14px 16px;margin:0;
}
.faixa-estado.faixa-congelada{
  background:rgba(87,113,113,0.08);border-color:rgba(87,113,113,0.2);
}
.faixa-rotulo{
  font-size:11px;text-transform:uppercase;letter-spacing:0.14em;font-weight:700;
  color:var(--alerta);margin:0 0 6px;
}
.faixa-congelada .faixa-rotulo{color:var(--slate)}
.faixa-estado p:last-child{margin-bottom:0;font-size:14px}
.ficha{display:grid;grid-template-columns:auto 1fr;gap:2px 16px;margin:0 0 18px;font-size:14px}
.ficha dt{color:var(--slate);font-size:11px;text-transform:uppercase;letter-spacing:0.14em;
  font-weight:700;padding-top:3px}
.ficha dd{margin:0}
.acoes{margin:18px 0 0}
button{
  font-family:inherit;font-size:13px;font-weight:700;color:var(--navy);background:var(--painel);
  border:1px solid var(--linha);border-radius:3px;padding:7px 12px;cursor:pointer;
}
button:hover{border-color:var(--lime)}
.so-com-js{display:none}
html.js .so-com-js{display:inline-block}
.so-na-impressao{display:none}
.rolagem{overflow-x:auto;margin:0 0 6px;background:var(--painel);border:1px solid var(--linha);
  border-radius:4px}
table{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
table.larga{min-width:720px}
caption{
  text-align:left;font-size:12.5px;color:var(--slate);padding:10px 12px;
  border-bottom:1px solid var(--linha);
}
th{
  font-size:10.5px;text-transform:uppercase;letter-spacing:0.12em;color:var(--slate);
  font-weight:700;text-align:left;padding:9px 12px;border-bottom:1px solid var(--linha);
  vertical-align:bottom;
}
td{padding:8px 12px;border-bottom:1px solid var(--grid);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
.num{text-align:right;white-space:nowrap}
.forte{font-weight:700}
.posicao{color:var(--slate);width:1%}
.estrela{color:var(--slate);font-weight:400;padding-left:2px}
tr.referencia td{background:var(--grid);font-weight:700}
.marca-n{
  display:inline-block;font-size:10.5px;text-transform:uppercase;letter-spacing:0.1em;
  color:var(--alerta);border:1px solid rgba(192,88,79,0.3);border-radius:2px;padding:0 4px;
  margin-left:4px;white-space:nowrap;
}
.selo{
  display:inline-block;font-size:11px;font-weight:700;padding:2px 7px;border-radius:2px;
  white-space:nowrap;
}
.selo-ok{color:var(--slate);border:1px solid var(--linha);background:var(--grid)}
.selo-trocado{color:var(--navy);border:1px solid var(--linha);background:var(--track)}
.selo-ausente{color:var(--alerta);border:1px solid rgba(192,88,79,0.3);
  background:rgba(192,88,79,0.08)}
.fonte{font-size:11px;color:var(--slate);vertical-align:super}
.fonte a{color:var(--slate);text-decoration:none}
.fonte a:hover{text-decoration:underline}
.tres-lentes{display:grid;grid-template-columns:1fr;gap:0;margin:0 0 18px;
  border-top:1px solid var(--linha)}
.lente{padding:16px 0;border-bottom:1px solid var(--linha)}
.lente p{max-width:70ch}
.lente .resposta{font-size:19px;font-weight:700;margin:0 0 8px}
.figura{margin:0 0 10px;background:var(--painel);border:1px solid var(--linha);border-radius:4px;
  padding:12px}
.figura-svg{display:block;width:100%;height:auto}
figcaption{font-size:12.5px;color:var(--slate);padding-top:10px;border-top:1px solid var(--grid);
  margin-top:10px}
.abas{margin:0 0 10px}
.aba-radio{position:absolute;opacity:0;width:1px;height:1px;overflow:hidden}
.aba-barra{display:flex;flex-wrap:wrap;gap:4px;border-bottom:1px solid var(--linha);
  margin-bottom:12px}
.aba-rotulo{
  font-size:12.5px;font-weight:700;color:var(--slate);padding:8px 12px;cursor:pointer;
  border-bottom:2px solid transparent;margin-bottom:-1px;
}
.aba-painel{display:none}
#aba-revisado:checked ~ .aba-barra label[for="aba-revisado"],
#aba-epoca:checked ~ .aba-barra label[for="aba-epoca"]{color:var(--navy);
  border-bottom-color:var(--lime)}
#aba-revisado:focus ~ .aba-barra label[for="aba-revisado"],
#aba-epoca:focus ~ .aba-barra label[for="aba-epoca"]{outline:2px solid var(--lime-claro)}
#aba-revisado:checked ~ .aba-paineis #painel-revisado,
#aba-epoca:checked ~ .aba-paineis #painel-epoca{display:block}
.acordeao{border-top:1px solid var(--linha);margin:0 0 18px}
details{border-bottom:1px solid var(--linha)}
summary{
  cursor:pointer;padding:13px 0 13px 22px;font-weight:700;font-size:15px;list-style:none;
  position:relative;
}
summary::-webkit-details-marker{display:none}
summary::before{
  content:"+";position:absolute;left:0;top:12px;color:var(--slate);font-weight:700;
}
details[open] summary::before{content:"\\2013"}
details p{padding:0 0 14px 22px;max-width:80ch;font-size:14px;color:var(--navy)}
.decisoes td{vertical-align:top}
.decisoes .resposta-vazia{min-width:120px}
.linha-de-resposta{display:block;border-bottom:1px solid var(--linha);height:22px;min-width:100px}
.fontes{margin:0 0 16px;padding-left:20px;font-size:13.5px;color:var(--slate)}
.fontes li{margin-bottom:5px}
.assinatura{font-size:13.5px;color:var(--slate);border-top:1px solid var(--linha);
  padding-top:16px;max-width:80ch}
@media (min-width:760px){
  .tres-lentes{grid-template-columns:repeat(3,1fr);gap:0 24px;border-top:0}
  .lente{border-bottom:0;border-top:2px solid var(--navy);padding-top:14px}
  h1{font-size:38px}
  h2{font-size:25px}
}
@media print{
  @page{size:A4;margin:14mm}
  body{background:#fff;font-size:10pt;line-height:1.4}
  .pagina{max-width:none;padding:0}
  .acoes,.aba-barra{display:none}
  section{border-top:1px solid var(--linha);padding:14pt 0;break-inside:auto}
  h1{font-size:20pt}
  h2{font-size:14pt;break-after:avoid}
  h3{break-after:avoid}
  table{font-size:8pt}
  table.larga{min-width:0}
  .rolagem{overflow:visible;border:1px solid var(--linha)}
  tr,li,figure,.lente{break-inside:avoid}
  .aba-painel{display:block !important;margin-bottom:12pt}
  .so-na-impressao{display:block}
  details>*{display:block !important}
  summary::before{content:""}
  summary{padding-left:0}
  details p{padding-left:0}
  .figura{border:0;padding:0}
  a{text-decoration:none}
}
"""

JS = """
(function(){
  document.documentElement.className = "js";
  function abrirTudo(){
    var blocos = document.querySelectorAll("details");
    for (var i = 0; i < blocos.length; i++) { blocos[i].open = true; }
  }
  var botao = document.getElementById("expandir");
  if (botao) { botao.addEventListener("click", abrirTudo); }
  if (window.matchMedia) {
    var impressao = window.matchMedia("print");
    if (impressao.addEventListener) {
      impressao.addEventListener("change", function(e){ if (e.matches) { abrirTudo(); } });
    }
  }
  window.addEventListener("beforeprint", abrirTudo);
})();
"""


# ─────────────────────────────────────────────────────────────────────────────
# Montagem
# ─────────────────────────────────────────────────────────────────────────────


def montar_html(*, raiz: Path | None = None, raiz_do_adr: Path | None = None) -> str:
    """O relatório inteiro como string. Determinístico: mesma entrada, mesmos bytes."""
    dados = ler_dados(raiz=raiz, raiz_do_adr=raiz_do_adr)
    return renderizar(dados)


def renderizar(dados: Dados) -> str:
    """A montagem a partir de dados já lidos. É onde as guardas de saída rodam."""
    textos = textos_do_relatorio(dados)
    lentes = ler_lentes(dados)
    completo = hash_do_dataset(dados.manifesto)
    curto = hash_curto(completo)

    corpo = (
        _s1_topo(dados, textos, curto, completo)
        + _s2_pedido(textos)
        + _s3_resposta(textos)
        + _s4_regime(dados, textos, lentes)
        + _s5_momentos(dados, textos, lentes)
        + _s6_heatmap(dados, textos, lentes)
        + _s7_timeline(dados, textos)
        + _s8_internacional(dados, textos, lentes)
        + _s9_limites(textos)
        + _s10_decisoes(textos)
        + _s11_rodape(dados, textos, curto, completo)
    )
    documento = (
        "<!DOCTYPE html>\n"
        '<html lang="pt-BR">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(TITULO, quote=False)}</title>\n"
        '<meta name="description" content="'
        f'{html.escape(SUBTITULO, quote=True)}">\n'
        f'<meta name="author" content="{html.escape(AUTOR, quote=True)}">\n'
        f'<meta name="ldc-dataset" content="{curto}">\n'
        f'<meta name="ldc-gate" content="{html.escape(dados.estado.status_adr, quote=True)}">\n'
        f"<style>{CSS}</style>\n"
        "</head>\n<body>\n"
        f'<main class="pagina">{corpo}</main>\n'
        f"<script>{JS}</script>\n"
        "</body>\n</html>\n"
    )
    _conferir_saida(documento, dados)
    return documento


def _conferir_saida(documento: str, dados: Dados) -> None:
    """As quatro travas que valem sobre o HTML pronto, não sobre um bloco isolado."""
    if TRAVESSAO in documento:
        msg = "travessao (em dash) no HTML gerado: DESIGN.md bane em dash no modulo de produto"
        raise SerieInconsistente(msg)
    proibidos = artefatos_nao_publicaveis(dados.manifesto)
    for arquivo in proibidos:
        radical = arquivo.rsplit(".", 1)[0]
        if radical and radical in documento:
            msg = (
                f"o HTML nomeia {arquivo}, que esta marcado `publicavel = false` no MANIFEST.json. "
                "Numero nao publicavel nao sai no relatorio."
            )
            raise SerieInconsistente(msg)
    identificadores = [identificador for identificador, _ in SECOES]
    posicoes = [documento.find(f'id="{identificador}"') for identificador in identificadores]
    if any(posicao < 0 for posicao in posicoes) or posicoes != sorted(posicoes):
        msg = f"as {len(SECOES)} secoes nao estao todas presentes e na ordem: {identificadores}"
        raise SerieInconsistente(msg)
    if "<svg" not in documento:
        msg = "o HTML saiu sem figura inline: o mapa de calor e a linha do tempo sao obrigatorios"
        raise SerieInconsistente(msg)


def sha256_do_texto(texto: str) -> str:
    """O `sha256` do HTML como ele vai para o disco (UTF-8, LF)."""
    return sha256(texto.encode("utf-8")).hexdigest()


def caminho_do_relatorio(*, raiz: Path | None = None) -> Path:
    """`data/canonical/entrega/RELATORIO-ALEXANDRE-2026-10-14.html`."""
    return caminho_canonical(SUBPASTA_ENTREGA, raiz=raiz) / NOME_DO_ARQUIVO


def gerar(*, raiz: Path | None = None, destino: Path | None = None) -> Path:
    """Monta e grava o relatório. Devolve o caminho escrito."""
    documento = montar_html(raiz=raiz)
    alvo = destino if destino is not None else caminho_do_relatorio(raiz=raiz)
    garantir_diretorio(alvo.parent)
    alvo.write_text(documento, encoding="utf-8", newline="\n")
    _log.info(
        "relatorio executivo gravado: %s (%d bytes, sha256=%s)",
        alvo,
        len(documento.encode("utf-8")),
        sha256_do_texto(documento)[:16],
    )
    return alvo


# ─────────────────────────────────────────────────────────────────────────────
# Interface de linha de comando
# ─────────────────────────────────────────────────────────────────────────────


def _imprimir(texto: str = "") -> None:
    print(para_ascii(texto))  # noqa: T201 - e a interface de linha de comando


def main(argv: Sequence[str] | None = None) -> int:
    """`uv run python -m apps.analysis.entrega.relatorio_executivo`."""
    analisador = argparse.ArgumentParser(
        prog="apps.analysis.entrega.relatorio_executivo",
        description=(
            "Gera o relatorio executivo HTML autocontido para o Comite de Alocacao "
            "(F-032). Nao toca a rede."
        ),
    )
    analisador.add_argument(
        "--destino",
        type=Path,
        default=None,
        help="caminho do HTML de saida (padrao: data/canonical/entrega/)",
    )
    analisador.add_argument(
        "--conferir",
        action="store_true",
        help="monta duas vezes e confere que o sha256 e o mesmo, sem gravar",
    )
    argumentos = analisador.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if argumentos.conferir:
            primeira = sha256_do_texto(montar_html())
            segunda = sha256_do_texto(montar_html())
            _imprimir(f"sha256 geracao 1 : {primeira}")
            _imprimir(f"sha256 geracao 2 : {segunda}")
            if primeira != segunda:
                _imprimir("*** NAO DETERMINISTICO: as duas geracoes divergem ***")
                return 1
            _imprimir("DETERMINISTICO: duas geracoes, mesmo sha256")
            return 0
        alvo = gerar(destino=argumentos.destino)
    except (FonteIndisponivel, SerieInconsistente) as erro:
        _imprimir(f"*** FALHOU: {erro} ***")
        return 1
    documento = alvo.read_text(encoding="utf-8")
    estado = ler_estado_do_gate()
    _imprimir(f"ARQUIVO  : {alvo}")
    _imprimir(f"TAMANHO  : {len(documento.encode('utf-8'))} bytes")
    _imprimir(f"SHA256   : {sha256_do_texto(documento)}")
    _imprimir(f"GATE     : ADR-001 em {estado.status_adr} -> {para_ascii(estado.rotulo)}")
    if estado.status_adr != STATUS_ADR_ACEITO:
        _imprimir("")
        _imprimir(
            "O relatorio abre com MATERIAL DE DISCUSSAO. Enquanto o ADR-001 estiver em Proposta, "
            "nenhum numero deste arquivo e insumo de decisao de alocacao."
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de linha de comando
    raise SystemExit(main())
