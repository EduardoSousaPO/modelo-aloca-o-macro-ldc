# Guia de Estrutura — Harness Solo

> O que vai em cada pasta e por quê. Leia antes de criar qualquer arquivo fora do padrão.

---

## Árvore completa

```
projeto/
├── AGENTS.md               ← contrato universal com agentes (≤150 linhas)
├── CLAUDE.md               ← ajustes específicos do Claude Code (≤100 linhas)
├── TODO.md                 ← estado vivo: em andamento + backlog + bugs (substitui state/)
├── README.md               ← visão humana do projeto
├── .gitignore
│
├── docs/                   ← documentação permanente
│   ├── product/
│   │   └── PRD.md          ← o quê e por quê (output de /consultor-prd)
│   ├── specs/
│   │   └── SPEC.md         ← o que o sistema faz + Anti-SPEC (output de /SDD-avancado)
│   ├── contracts/
│   │   └── CONTRACTS.md    ← espelho legível dos tipos em packages/shared/types/
│   ├── plans/
│   │   ├── PLAN.md         ← OPCIONAL: ordem de ataque por ondas de features
│   │   ├── skills-manifest.md  ← OPCIONAL: output de /skill-scout
│   │   └── cursor-brief.md ← OPCIONAL: brief para Cursor Agent em tarefas de infra
│   └── decisions/adr/
│       └── ADR-NNN-*.md    ← uma decisão arquitetural por arquivo
│
├── apps/                   ← código das aplicações
│   ├── web/                ← Next.js / Vite / etc.
│   └── api/                ← Next.js route handlers / Express / FastAPI / etc.
│
├── packages/
│   └── shared/
│       └── types/          ← SOURCE OF TRUTH dos contratos (Zod + TypeScript)
│           ├── api.ts      ← envelope de response, erros
│           ├── auth.ts
│           ├── user.ts
│           └── index.ts    ← re-export
│
├── tests/                  ← todos os testes
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── infra/                  ← OPCIONAL (só se tiver banco/deploy)
│   └── supabase/migrations/
│
└── .github/
    └── workflows/ci.yml    ← evaluator automático: lint + typecheck + test
```

---

## Regras por pasta

### `docs/`
- Documentação permanente. **O agente lê mas não edita sem permissão explícita.**
- Fonte de verdade para requisitos e decisões.

### `packages/shared/types/`
- **Source of truth dos contratos.** Schemas Zod + tipos TS.
- Qualquer endpoint, evento, IPC ou storage externo passa por aqui.
- Regra: se vai criar um contrato em `CONTRACTS.md`, primeiro crie o schema Zod aqui.

### `apps/`
- Uma subpasta por aplicação. Sem `scripts/` genéricos na raiz do monorepo.
- Testes mais próximos do código ficam em `apps/<app>/__tests__/` (seguindo convenção do framework); testes que cruzam módulos vão em `tests/`.

### `tests/`
- `unit/` — testes isolados de funções puras e módulos.
- `integration/` — testes que tocam dependências reais (DB em container, API interna).
- `e2e/` — Playwright / Cypress.
- Um teste por critério de aceite (CA) da SPEC, no mínimo.

### `infra/`
- Migrations Supabase, scripts Terraform, Dockerfiles.
- Modificado principalmente pelo Cursor Agent (via MCPs), nunca em produção direto.

### `.github/workflows/`
- `ci.yml` é o **evaluator** do harness. Obrigatório desde o kickoff.
- Sem CI, não há separação generator/evaluator — qualquer fix vira aposta.

---

## Onde NÃO colocar coisas

- **Nunca** crie uma pasta genérica `scripts/` na raiz. Scripts pertencem ao módulo que os usa (`apps/<app>/scripts/`, `infra/scripts/`).
- **Nunca** recrie `state/`, `handoffs/` ou `progress.jsonl`. Estado vive em `TODO.md` + git.
- **Nunca** coloque lógica de negócio em `packages/shared/` — só tipos, schemas e utilitários *puros*.

---

## Justificativa das diferenças em relação ao Harness v2 tradicional

| Harness v2 tradicional | Harness Solo | Motivo |
|---|---|---|
| `state/project-state.json` + `progress.jsonl` + `handoffs/*.json` | `TODO.md` + `git log` | Sozinho, JSON machine-readable agrega overhead. Markdown + git dá rastreabilidade equivalente. |
| `docs/plans/TASKS.md` com tasks atômicas + `WAVE-PLAN.md` | `TODO.md` com features + `PLAN.md` opcional por ondas | Tarefa atômica faz sentido para coordenar 3 agentes. Para um dev, feature é a unidade útil. |
| `CONTRACTS.md` com OpenAPI/JSON-Schema em Markdown | `packages/shared/types/` (Zod) + `CONTRACTS.md` como espelho | Contrato como código evita drift e gera validação runtime automática. |
| `.cursor/rules/global.mdc` obrigatório | Opcional, só se Cursor Agent for usado | Sem time para coordenar, rule não paga o custo de manutenção. |
| `PROCESS.md` com marcos de faturamento | Opcional | Solo geralmente não tem cliente externo com gates. |
| `infra/harness/validate_harness.py` customizado | CI do GitHub faz o papel | Menos superfície para manter. |
