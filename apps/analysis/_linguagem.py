"""A guarda **única** de linguagem descritiva da camada de análise (Anti-SPEC §10.2.10).

Por que existe, em uma frase: até 2026-10-11 havia **três** guardas — uma lista de frases em
`figuras/heatmap_regime_ativo.py`, uma tupla de 5 termos dentro de um teste de
`figuras/timeline_regimes.py` e a única executável e reutilizável, em
`tabelas/ranking_regime_atual.py`. O QA da Onda 4 (**P2-1**) mediu a consequência: a guarda de
F-024, aplicada aos textos das outras features, **reprova** material legítimo —

- as 5 figuras, pela própria ressalva *"Nada aqui e projecao"*;
- `LIMITACOES-COMITE.md`, por `nunca "quanto vai render"`, por *"**Backtest**, otimização ou
  fronteira eficiente — … não está neste pacote"* e por *"a **recomendação** é do Alexandre"*.

Todas são **negações legítimas**. O defeito não estava nos textos: estava na janela de negação, que
só reconhecia `não`/`nunca` **imediatamente antes** do termo. Três guardas divergentes é pior que
uma: a mais frouxa deixa passar o que a mais severa proibiria, e nenhuma é a autoridade.

## O modelo: duas listas, porque o risco tem duas formas

1. **Forma assertiva** (`"vai render"`, `"esperamos"`, `"recomendamos"`) — proibida, com **uma**
   exceção medida: a frase **citada dentro de uma negação curta**, que é como os dois documentos
   reais dizem o que não fazem — `Nunca "quanto vai render"` e `… não "este é o melhor"`. A janela
   aqui é **curta de propósito** (`JANELA_DE_NEGACAO_ASSERTIVA`, 40 caracteres, só para trás):
   uma afirmação preditiva de verdade (`"o IBOV vai render +5%"`) nunca tem `não`/`nunca` colado
   nela, e um parágrafo que começa negando e três linhas depois afirma **não** escapa.
2. **Substantivo preditivo** (`"previsão"`, `"backtest"`, `"recomendação"`) — permitido **só sob
   negação**. Proibi-lo por inteiro tornaria impossível escrever o aviso que blinda a reunião: é
   exatamente dizendo *"não é previsão, não é backtest"* que o documento se protege.

A janela de negação olha para trás **e** para a frente do termo, e reconhece as construções que o
português de verdade usa: `não`/`nunca`/`nenhum`, `nada ... é`, `≠`, `sem`, `proíbe`, `fora deste
pacote`, além do cabeçalho de seção `O que NÃO está neste pacote` — que nega **tudo** o que vem
abaixo dele, e por isso é tratado como negação de **seção**, não de janela.

## Como usar

```python
from apps.analysis import _linguagem

_linguagem.conferir_linguagem_descritiva(texto, origem="heatmap_v1_revised")
```

Levanta `SerieInconsistente` nomeando **o que** achou e **onde**. Para teste de texto de figura,
`termos_preditivos_em(texto)` devolve a lista em vez de levantar.

Cobre: Anti-SPEC §10.2.10 · CA-097 (a figura nomeia a métrica, não insinua desempenho) ·
`AGENTS.md §7`. Consumido por `figuras/heatmap_regime_ativo.py`,
`figuras/timeline_regimes.py` e `tabelas/ranking_regime_atual.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.pipeline.common.errors import SerieInconsistente

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Sequence

#: Formas **assertivas** de previsão: proibidas por inteiro, em qualquer contexto. Acentuadas e sem
#: acento, porque o acento é o primeiro a cair quando alguém reescreve a frase à mão — e porque o
#: texto renderizado das figuras passa por `para_ascii` (Anti-SPEC §10.4.26).
FORMAS_PREDITIVAS_PROIBIDAS: tuple[str, ...] = (
    "vai render",
    "vai subir",
    "vai cair",
    "vai performar",
    "vai entregar",
    "deve render",
    "deve subir",
    "deve cair",
    "deve performar",
    "tende a render",
    "tende a subir",
    "tende a cair",
    "retorno esperado",
    "esperado para",
    "projetamos",
    "prevemos",
    "esperamos",
    "espera-se",
    "estimamos que",
    "recomendamos",
    "recomendacao de alocacao:",
    "recomendação de alocação:",
    "sugerimos",
    "melhor aposta",
    "aposta para",
    "e o melhor",
    "é o melhor",
)

#: Substantivos preditivos: permitidos **só sob negação**. Ver o cabeçalho do módulo.
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
    "quanto vai render",
)

#: O que conta como negação na vizinhança do termo. `nada` entra porque "**Nada** aqui e projecao"
#: é a ressalva literal das 5 figuras, e `fora de`/`fora desta`/`fora deste` porque é como a
#: Anti-SPEC e a página de limitações declaram escopo.
#: Deliberadamente **fora** da lista: `descritivo`. A palavra aparece em cabeçalho e em selo de
#: quase todo artefato desta camada, então aceitá-la como negação absolveria qualquer afirmação
#: preditiva que caísse na mesma vizinhança — a guarda viraria decoração.
MARCADORES_DE_NEGACAO: tuple[str, ...] = (
    "não",
    "nao",
    "nunca",
    "nenhum",
    "nenhuma",
    "nada",
    "nem ",
    "sem ",
    "≠",
    "proib",
    "fora de escopo",
    "fora desta",
    "fora deste",
    "jamais",
)

#: Quantos caracteres a guarda olha **antes** do termo procurando a negação. 80 era a janela de
#: F-024 e é curta para "Esta pagina mede o que aconteceu ...; nao e previsao": subiu para 160.
JANELA_DE_NEGACAO_ANTES = 160

#: A janela da **forma assertiva** é curta e só para trás: ela existe apenas para a frase citada
#: dentro de uma negação (`Nunca "quanto vai render"`), não para absolver um parágrafo inteiro.
JANELA_DE_NEGACAO_ASSERTIVA = 40

#: E quantos **depois**. Existe porque "Previsao: nenhuma - este documento e descritivo" e
#: "Backtest? Nao ha." negam o termo **à frente**, que é construção corrente em título e em tabela.
JANELA_DE_NEGACAO_DEPOIS = 60

#: Cabeçalhos que negam **toda a seção** abaixo deles, não só uma janela de caracteres. É a forma
#: que `LIMITACOES-COMITE.md` usa para listar o que ficou fora — e listar o que ficou fora exige
#: nomear o que ficou fora.
CABECALHOS_DE_NEGACAO: tuple[str, ...] = (
    "o que nao esta neste pacote",
    "o que não está neste pacote",
    "o que ficou fora",
    "o que este levantamento nao sustenta",
    "o que este levantamento não sustenta",
    "o que nao foi feito",
    "o que não foi feito",
)


def _secao_negada(minusculo: str, posicao: int) -> bool:
    """O termo está **abaixo** de um cabeçalho que nega a seção inteira?

    Olha para trás até o cabeçalho de negação mais próximo e aceita se nenhum outro cabeçalho de
    nível igual ou maior apareceu entre ele e o termo — isto é, se o termo ainda está **dentro** da
    seção que nega.
    """
    prefixo = minusculo[:posicao]
    for cabecalho in CABECALHOS_DE_NEGACAO:
        inicio = prefixo.rfind(cabecalho)
        if inicio == -1:
            continue
        # A seção vai do cabeçalho até o próximo cabeçalho Markdown de mesmo nível ou acima.
        resto = prefixo[inicio + len(cabecalho) :]
        if "\n## " not in resto and "\n# " not in resto:
            return True
    return False


def _negado_no_contexto(minusculo: str, posicao: int, termo: str) -> bool:
    """Esta ocorrência específica do termo está sob negação?"""
    antes = minusculo[max(0, posicao - JANELA_DE_NEGACAO_ANTES) : posicao]
    depois = minusculo[posicao + len(termo) : posicao + len(termo) + JANELA_DE_NEGACAO_DEPOIS]
    if any(marcador in antes or marcador in depois for marcador in MARCADORES_DE_NEGACAO):
        return True
    return _secao_negada(minusculo, posicao)


def substantivos_sem_negacao(texto: str) -> list[str]:
    """Os substantivos preditivos que aparecem **sem** negação em volta — lista, não exceção."""
    minusculo = texto.lower()
    achados: list[str] = []
    for termo in SUBSTANTIVOS_PREDITIVOS_SOB_NEGACAO:
        posicao = minusculo.find(termo)
        while posicao != -1:
            if not _negado_no_contexto(minusculo, posicao, termo):
                achados.append(termo)
                break
            posicao = minusculo.find(termo, posicao + len(termo))
    return achados


def formas_assertivas(texto: str) -> list[str]:
    """As formas assertivas presentes no texto **e não citadas dentro de uma negação curta**.

    Uma ocorrência só é absolvida se houver negação nos `JANELA_DE_NEGACAO_ASSERTIVA` caracteres
    imediatamente anteriores — o caso `Nunca "quanto vai render"`. Se **qualquer** ocorrência da
    forma estiver solta, a forma entra na lista.
    """
    minusculo = texto.lower()
    achadas: list[str] = []
    for forma in FORMAS_PREDITIVAS_PROIBIDAS:
        posicao = minusculo.find(forma)
        while posicao != -1:
            antes = minusculo[max(0, posicao - JANELA_DE_NEGACAO_ASSERTIVA) : posicao]
            if not any(marcador in antes for marcador in MARCADORES_DE_NEGACAO):
                achadas.append(forma)
                break
            posicao = minusculo.find(forma, posicao + len(forma))
    return achadas


def termos_preditivos_em(texto: str) -> list[str]:
    """Tudo que a guarda reprovaria neste texto. Vazio = texto descritivo."""
    return [*formas_assertivas(texto), *substantivos_sem_negacao(texto)]


def conferir_linguagem_descritiva(texto: str, *, origem: str = "texto") -> None:
    """Levanta `SerieInconsistente` se o texto afirmar previsão (Anti-SPEC §10.2.10).

    `origem` entra na mensagem para que a falha diga **qual** artefato reprovou — com três
    consumidores, "linguagem preditiva" sem o nome do arquivo é uma caça ao tesouro.
    """
    assertivas = formas_assertivas(texto)
    soltos = substantivos_sem_negacao(texto)
    if assertivas or soltos:
        msg = (
            f"linguagem preditiva em {origem} (Anti-SPEC §10.2.10): formas assertivas "
            f"{assertivas}; substantivos preditivos sem negação no contexto {soltos}. "
            "O entregável é descritivo: 'rendeu X, n = Y', nunca 'vai render'."
        )
        raise SerieInconsistente(msg)


def conferir_textos(textos: Sequence[str], *, origem: str = "texto") -> None:
    """A guarda sobre uma lista de textos (os de uma figura, por exemplo), um a um."""
    for indice, texto in enumerate(textos):
        conferir_linguagem_descritiva(texto, origem=f"{origem}[{indice}]")
