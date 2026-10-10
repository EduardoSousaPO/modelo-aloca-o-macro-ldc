"""Logging da infra de extração — um formato, timestamps ISO-8601, idempotente.

Por que um módulo em vez de `print`: o modo de falha dominante do projeto é **número errado que
chega ao comitê sem levantar exceção** (`TODO.md §0`). Quando a falha é silenciosa por natureza
— dia sem divulgação da ANBIMA (R17, `ausencia_e_caso_normal`), retry que deu certo na 2ª
tentativa, resposta 304 do cache condicional — o rastro no log é a única evidência que sobra.

`configurar_logging()` é chamado pelos *entrypoints* (job, notebook, teste que queira ver o
rastro), **nunca** na importação de um módulo de biblioteca: biblioteca que configura o logging
global do processo rouba a decisão de quem chama.
"""

from __future__ import annotations

import logging
import sys

FORMATO = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"
FORMATO_DATA = "%Y-%m-%dT%H:%M:%S"
NOME_LOGGER_RAIZ = "pipeline"


def obter_logger(nome: str) -> logging.Logger:
    """Logger do namespace `pipeline.*` — use `obter_logger(__name__)` em todo módulo.

    Não configura handler: só nomeia. Sem `configurar_logging()`, as mensagens ficam silenciosas
    (comportamento padrão de biblioteca), o que é o que se quer dentro do `pytest`.
    """
    if nome.startswith(f"{NOME_LOGGER_RAIZ}."):
        return logging.getLogger(nome)
    return logging.getLogger(f"{NOME_LOGGER_RAIZ}.{nome.rsplit('.', maxsplit=1)[-1]}")


def configurar_logging(*, nivel: int = logging.INFO, forcar: bool = False) -> logging.Logger:
    """Instala um `StreamHandler` em `stderr` no logger `pipeline`. Idempotente.

    `forcar=True` troca o handler existente (útil quando o nível muda em meio à sessão).
    Devolve o logger raiz do pipeline para quem quiser logar direto.
    """
    raiz = logging.getLogger(NOME_LOGGER_RAIZ)
    if raiz.handlers and not forcar:
        raiz.setLevel(nivel)
        return raiz
    for handler in list(raiz.handlers):
        raiz.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(fmt=FORMATO, datefmt=FORMATO_DATA))
    raiz.addHandler(handler)
    raiz.setLevel(nivel)
    # O pipeline não é o `root` do processo: propagar duplicaria a linha em quem já configurou
    # logging (Jupyter, por exemplo).
    raiz.propagate = False
    return raiz
