"""`python -m apps.pipeline` — entrada do orquestrador (F-029).

Arquivo deliberadamente fino: a implementação toda está em `apps/pipeline/run.py`, que é
importável por teste e por notebook sem passar pela CLI. Aqui só se amarra o subcomando ao
processo:

```bash
python -m apps.pipeline run --offline
python -m apps.pipeline verify
python -m apps.pipeline freeze --tag comite-2026-10-14
```

`pyproject.toml` está **congelado** nesta onda, então não há `[project.scripts]`: o comando
oficial é `python -m apps.pipeline` (registrado no runbook e em `docs/wiki/context/F-029.md`).
"""

from __future__ import annotations

from apps.pipeline.run import main

if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
