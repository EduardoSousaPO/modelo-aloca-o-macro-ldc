"""Configuração mínima da suíte de testes.

Duas responsabilidades, nenhuma a mais:

1. **Garantir o import da raiz do repo.** `pyproject.toml` já define
   `[tool.pytest.ini_options] pythonpath = ["."]`, mas quem roda `pytest` de dentro de `tests/`
   (ou com outro `rootdir`) perde isso. Sem a raiz no `sys.path`,
   `from packages.shared.schemas import ...` falha — era o P0 nº 2 da auditoria do harness.
2. **Publicar os caminhos canônicos** da raiz e de `tests/fixtures/` como fixtures, para que nenhum
   teste calcule `Path(__file__).parent.parent...` por conta própria.

Fixture de fonte externa é **sempre** arquivo gravado em `tests/fixtures/<fonte>/`
(convenção em `tests/fixtures/README.md`); chamada viva só sob `@pytest.mark.network`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parent.parent

if str(RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPO))


@pytest.fixture(scope="session")
def raiz_repo() -> Path:
    """Raiz do repositório — âncora de todo caminho relativo em teste."""
    return RAIZ_REPO


@pytest.fixture(scope="session")
def dir_fixtures() -> Path:
    """`tests/fixtures/` — único lugar de onde um teste pode ler resposta de fonte externa."""
    return RAIZ_REPO / "tests" / "fixtures"
