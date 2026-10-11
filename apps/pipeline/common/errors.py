"""Exceções da infra de extração — uma por modo de falha catalogado na pesquisa.

Cada classe aqui existe porque `docs/research/fontes-de-dados.md §RISCOS DE EXTRAÇÃO` registra um
modo de falha **confirmado** nas fontes deste projeto. O ponto da hierarquia é que o extrator
**levante ruidosamente** em vez de gravar lixo: a Anti-SPEC §10.1.5 proíbe tratar HTTP 200 como
sucesso, e §10.1.1/§10.1.4 proíbem preencher lacuna com valor inventado ou `0`.

| Exceção | Risco | Anti-SPEC |
|---|---|---|
| `RespostaDeErroComStatus200` | R1 (SGS devolve erro com HTTP 200) | §10.1.5 |
| `RespostaTruncada` | R2 (Olinda `$top`, Yahoo `range=max`, FRED sem `cosd`) | §10.1.1 |
| `UserAgentObrigatorio` | R4 (Yahoo sem UA → 429; CKAN do BCB → página de erro) | — |
| `FormatoInesperado` | R11 (`.xls` que é XLSX; `.xls` que é HTML) | — |
| `ConteudoDivergente` | R8 (janela rolante) + idempotência (CA-121) | §10.4.22 |
| `NumeroNaoReconhecido` | R13 (separador de milhar inconsistente) | §10.1.4 |
| `DataNaoReconhecida` | R12 (`ms{AAMMDD}`, PTAX `MM-DD-YYYY`, SGS `dd/mm/aaaa`) | — |
| `FonteIndisponivel` | R5/R22 (rede bloqueada, 502 do SGS) | — |
"""

from __future__ import annotations


class ErroDeExtracao(Exception):
    """Base de toda falha da infra de extração. Capturar isto nunca esconde um bug de parse."""


class FonteIndisponivel(ErroDeExtracao):
    """A fonte não respondeu de forma utilizável após os retries configurados.

    É o `BLOQUEADO — FONTE INDISPONÍVEL` de `CLAUDE.md §4` na forma de exceção: nenhum extrator
    tem licença para substituir a série por estimativa quando isto acontece.
    """


class FalhaDeTransporte(ErroDeExtracao):
    """Falha na camada de rede (timeout, reset, DNS) — **retentável**.

    Existe separada de `FonteIndisponivel` para que o retry com backoff saiba o que vale repetir.
    R5 mediu exatamente este par no FRED: `ReadTimeout` e depois `ConnectionReset(10054)`.
    """


class RespostaDeErroComStatus200(ErroDeExtracao):
    """Corpo de erro servido com HTTP 200 (R1) — o modo de falha dominante deste projeto.

    O SGS devolve `{"error": "...janela de consulta de, no máximo, 10 anos..."}` com status 200, e
    série inexistente devolve HTML com status 200. Anti-SPEC §10.1.5.
    """


class RespostaTruncada(ErroDeExtracao):
    """Resposta completa para o HTTP, mas com menos linhas que o mínimo esperado (R2)."""


class UserAgentObrigatorio(ErroDeExtracao):
    """Tentativa de requisição sem User-Agent de browser numa fonte que o exige (R4, CA-045)."""


class FormatoInesperado(ErroDeExtracao):
    """Os magic bytes não correspondem ao formato que o extrator esperava (R11)."""


class ConteudoDivergente(ErroDeExtracao):
    """Já existe arquivo com este nome determinístico em `data/raw/` e o conteúdo é **outro**.

    Sobrescrever em silêncio apagaria dado de janela rolante (R8) e quebraria a reprodutibilidade
    por hash (CA-121). Quem chama decide: `sobrescrever_se_diferente=True` ou outro nome.
    """


class SerieInconsistente(ErroDeExtracao):
    """O corpo abriu e é do formato certo, mas o conteúdo não é a série esperada.

    Ticker/índice trocado, moeda trocada, granularidade diferente da pedida, data futura, data
    repetida, nível nulo, `is_total_return` ausente numa conversão. Nasceu em
    `extract/yahoo.py` e subiu para cá na consolidação da Onda 1 (D-g), quando a conversão a BRL
    desceu para `apps/pipeline/transform/cambio.py` e passou a precisar do mesmo erro sem
    importar um extrator.
    """


class NumeroNaoReconhecido(ErroDeExtracao):
    """A string não é um número na convenção declarada (R13).

    Levantar aqui é o que impede o erro de escala clássico: `"0.82"` lido como pt-BR daria `82.0`.
    """


class DataNaoReconhecida(ErroDeExtracao):
    """A string não é uma data no formato declarado para a fonte (R12)."""
