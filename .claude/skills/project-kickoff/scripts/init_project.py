#!/usr/bin/env python3
"""
init_project.py — Inicializa um novo projeto com a estrutura do Harness v3.2 (Project Wiki + Fast Fix).

Uso:
    python scripts/init_project.py --name meu-saas --path /caminho/base --type saas

Gera estrutura mínima:
    docs/
        product/, specs/, contracts/
        plans/                       (feature-contracts, risk-classification, FEATURE-CONTRACT,
                                      VALIDATION-MATRIX, CURRENT_REALITY, DECISIONS_LOG templates)
        wiki/                        (NOVO v3.2 — index.md, log.md, overview.md, architecture.md
                                      + diretórios modules/, features/, runbooks/, context/)
        decisions/adr/
    apps/, packages/shared/types/, tests/, infra/
    AGENTS.md (v3.2), CLAUDE.md (v3.2), TODO.md, README.md, .gitignore
    .github/workflows/ci.yml (N1 ativo + N2/N3 comentados)

Não cria: state/, handoffs/, progress.jsonl, PROCESS.md, WAVE-PLAN.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_DIR / "assets"
WIKI_ASSETS_DIR = ASSETS_DIR / "wiki"

# Pastas da árvore mínima do Harness v3.2
DIRS = [
    "docs/product",
    "docs/specs",
    "docs/contracts",
    "docs/plans",
    "docs/plans/_templates",          # templates de referência (separados dos docs ativos)
    "docs/plans/feature-contracts",
    "docs/decisions/adr",
    # Project Wiki (v3.2)
    "docs/wiki",
    "docs/wiki/modules",
    "docs/wiki/features",
    "docs/wiki/runbooks",
    "docs/wiki/context",
    # Código
    "apps",
    "packages/shared/types",
    "tests/unit",
    "tests/integration",
    "tests/contract",
    "tests/e2e",
    "infra",
    ".github/workflows",
]

# Cópias a partir de assets/ da skill: (asset, destino relativo)
ASSET_COPIES = [
    ("AGENTS.md", "AGENTS.md"),
    ("CLAUDE.md", "CLAUDE.md"),
    ("TODO.md", "TODO.md"),
    ("README.md", "README.md"),
    ("gitignore", ".gitignore"),
    ("ci.yml", ".github/workflows/ci.yml"),
    ("ADR-template.md", "docs/decisions/adr/ADR-template.md"),
]

# Templates v3.2 que vão para docs/plans/_templates/ (referência fria — não polui docs/plans/ ativo)
# risk-classification.md fica fora do _templates/ porque é referência QUENTE (lido em todo Prompt 1/2/3).
PLANS_TEMPLATE_COPIES = [
    ("risk-classification.md", "docs/plans/risk-classification.md"),
    ("FEATURE-CONTRACT-template.md", "docs/plans/_templates/FEATURE-CONTRACT-template.md"),
    ("VALIDATION-MATRIX-template.md", "docs/plans/_templates/VALIDATION-MATRIX-template.md"),
    ("CURRENT_REALITY-template.md", "docs/plans/_templates/CURRENT_REALITY-template.md"),
    ("DECISIONS_LOG-template.md", "docs/plans/_templates/DECISIONS_LOG-template.md"),
]

# Templates da Project Wiki (v3.2): (asset wiki/, destino relativo)
# overview-template.md e architecture-template.md viram overview.md/architecture.md (cópia ativa).
# runbook-template.md e context-pack-template.md ficam como _TEMPLATE.md dentro das pastas.
WIKI_TEMPLATE_COPIES = [
    ("index.md", "docs/wiki/index.md"),
    ("log.md", "docs/wiki/log.md"),
    ("overview-template.md", "docs/wiki/overview.md"),
    ("architecture-template.md", "docs/wiki/architecture.md"),
    ("runbook-template.md", "docs/wiki/runbooks/_TEMPLATE.md"),
    ("context-pack-template.md", "docs/wiki/context/_TEMPLATE.md"),
]


def log(msg: str) -> None:
    print(f"[kickoff] {msg}")


def run_git(root: Path, *args: str) -> None:
    try:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        log(f"git {' '.join(args)} falhou: {exc.stderr.decode(errors='ignore').strip()}")
    except FileNotFoundError:
        log("git não encontrado no PATH — pulei init/commit. Faça manualmente.")


def render_text(content: str, substitutions: dict[str, str]) -> str:
    for key, value in substitutions.items():
        content = content.replace(f"[{key}]", value)
    return content


def copy_with_substitutions(src: Path, dest: Path, substitutions: dict[str, str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = src.read_text(encoding="utf-8")
    dest.write_text(render_text(raw, substitutions), encoding="utf-8")


def create_structure(root: Path, name: str, project_type: str, stack: str | None) -> None:
    substitutions = {
        "Nome do Projeto": name,
        "YYYY-MM-DD": date.today().isoformat(),
        "Nome": "",
    }

    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)

    # 1) Arquivos da raiz (AGENTS, CLAUDE, TODO, README, .gitignore, ci.yml, ADR template)
    for asset_name, rel in ASSET_COPIES:
        src = ASSETS_DIR / asset_name
        if not src.exists():
            log(f"aviso: asset {asset_name} ausente em {ASSETS_DIR} — pulando.")
            continue
        copy_with_substitutions(src, root / rel, substitutions)
        log(f"criei {rel}")

    # 2) Templates v3.1 em docs/plans/
    for template_name, rel in PLANS_TEMPLATE_COPIES:
        src = ASSETS_DIR / template_name
        if not src.exists():
            log(f"aviso: template {template_name} ausente em {ASSETS_DIR} — pulando.")
            continue
        copy_with_substitutions(src, root / rel, substitutions)
        log(f"criei {rel}")

    # 3) Project Wiki (v3.2) — index, log, overview, architecture + templates dentro das subpastas
    if WIKI_ASSETS_DIR.exists():
        for wiki_template, rel in WIKI_TEMPLATE_COPIES:
            src = WIKI_ASSETS_DIR / wiki_template
            if not src.exists():
                log(f"aviso: wiki template {wiki_template} ausente em {WIKI_ASSETS_DIR} — pulando.")
                continue
            copy_with_substitutions(src, root / rel, substitutions)
            log(f"criei {rel} (wiki v3.2)")
    else:
        log("aviso: pasta assets/wiki/ ausente — wiki não populada. Atualize a skill.")

    # 4) .gitkeep nas pastas que precisam existir vazias
    empty_dirs = [
        "docs/product",
        "docs/specs",
        "docs/contracts",
        "docs/plans/feature-contracts",
        "docs/wiki/modules",
        "docs/wiki/features",
        "apps",
        "packages/shared/types",
        "tests/unit",
        "tests/integration",
        "tests/contract",
        "tests/e2e",
        "infra",
    ]
    for empty in empty_dirs:
        path = root / empty
        if path.exists() and not any(path.iterdir()):
            (path / ".gitkeep").write_text("", encoding="utf-8")

    # 5) Stack no README
    if stack:
        readme = root / "README.md"
        if readme.exists():
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- [ex: Next.js 14, TypeScript, Supabase, Vercel]",
                    f"- {stack}",
                ),
                encoding="utf-8",
            )

    # 6) Tipo de projeto no topo do TODO.md
    todo = root / "TODO.md"
    if todo.exists():
        text = todo.read_text(encoding="utf-8").replace(
            "**Fase:** kickoff | discovery | spec | execução | manutenção",
            f"**Fase:** kickoff\n**Tipo:** {project_type}",
        )
        todo.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicializa projeto no formato Harness v3.2 (Project Wiki + Fast Fix).")
    parser.add_argument("--name", required=True, help="Nome (slug kebab-case), ex: saas-financeiro")
    parser.add_argument("--path", required=True, help="Caminho base onde criar a pasta do projeto")
    parser.add_argument(
        "--type",
        default="app",
        choices=["saas", "app", "api", "landing", "tool", "other"],
        help="Tipo de projeto",
    )
    parser.add_argument("--stack", default=None, help="Stack prevista (livre), ex: 'Next.js + Supabase'")
    parser.add_argument("--no-git", action="store_true", help="Não inicializa git nem commita")
    args = parser.parse_args()

    base = Path(args.path).expanduser().resolve()
    if not base.exists():
        log(f"ERRO: caminho base não existe: {base}")
        return 2

    root = base / args.name
    if root.exists():
        if any(root.iterdir()):
            log(f"AVISO: {root} já existe e não está vazio. Abortando para evitar sobrescrever.")
            log("Rode novamente com outro --name ou apague a pasta manualmente.")
            return 3

    root.mkdir(parents=True, exist_ok=True)
    log(f"criando projeto em {root}")

    create_structure(root, args.name, args.type, args.stack)

    if not args.no_git:
        run_git(root, "init")
        run_git(root, "add", ".")
        run_git(root, "commit", "-m", "chore: kickoff Harness v3.2 (Project Wiki + Fast Fix)")

    log("")
    log(f"OK projeto '{args.name}' criado com sucesso em {root}")
    log("")
    log("Project Wiki populada em docs/wiki/:")
    log("  - index.md, log.md, overview.md, architecture.md")
    log("  - modules/, features/, runbooks/, context/ (vazias com _TEMPLATE.md de referência)")
    log("")
    log("docs/plans/ ativo (referência QUENTE — lido em todo Prompt):")
    log("  - risk-classification.md")
    log("docs/plans/_templates/ (referência FRIA — copie para docs/plans/ quando usar):")
    log("  - FEATURE-CONTRACT, VALIDATION-MATRIX, CURRENT_REALITY, DECISIONS_LOG (templates)")
    log("")
    log("Proximos passos:")
    log(f"  1. cd {root}")
    log("  2. Abra o Claude Code nesta pasta")
    log("  3. Rode /consultor-prd para o discovery e gerar docs/product/PRD.md")
    log("  4. Apos PRD/SPEC aprovados, peca ao agente:")
    log("     'atualize wiki/overview.md a partir do PRD'")
    log("     'atualize wiki/architecture.md a partir do SPEC'")
    log("  5. Para bug urgente em qualquer momento: /fast-fix")
    log("  6. Para varios bugs do cliente: /triage-bugs (lista colada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
