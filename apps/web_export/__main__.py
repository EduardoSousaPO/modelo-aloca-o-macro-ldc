"""`python -m apps.web_export exportar --tag <tag>` — o espelho de `python -m apps.pipeline`."""

from __future__ import annotations

import sys

from apps.web_export.exportar import main

if __name__ == "__main__":
    sys.exit(main())
