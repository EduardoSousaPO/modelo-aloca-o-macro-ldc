# Harness Solo vs Harness v2 tradicional

> Lista objetiva de tudo que mudou. Serve como referência para migrar projetos antigos.

---

## Removido (não criar mais)

- `state/project-state.json` → substituído por cabeçalho do `TODO.md` (fase + foco atual)
- `state/progress.jsonl` → substituído por `git log` + seção "Concluído" do `TODO.md`
- `state/handoffs/T-XXX.[agente].json` → handoff implícito: `git log` + corpo do PR
- `state/bugs/BUG-NNN.md` → seção "Bugs abertos" do `TODO.md`
- `state/evals/` → runs de CI + artefatos em `.github/`
- `docs/plans/TASKS.md` (tasks atômicas com spec_refs) → features no `TODO.md`
- `docs/plans/WAVE-PLAN.md` (detalhado por task) → `docs/plans/PLAN.md` **opcional**, por features agrupadas em ondas
- `docs/plans/AGENT-BRIEFS/codex-brief.md` → não existe mais (sem Codex)
- `docs/plans/AGENT-BRIEFS/cli-brief.md` → não existe (mesmo agente orquestra e gera)
- `.cursor/rules/backend.mdc`, `frontend.mdc`, `infra.mdc` → opcional e único, só se o Cursor Agent entrar
- `PROCESS.md` com marcos de faturamento → opcional
- `infra/harness/validate_harness.py` + schemas JSON de validação de estado → CI do GitHub cobre

## Adicionado / renomeado

- `TODO.md` na raiz — estado vivo em markdown
- `packages/shared/types/` — **source of truth dos contratos** (Zod + TS)
- `CONTRACTS.md` reescrito como **espelho legível**, não como documento fonte

## Preservado (sem mudanças)

- `AGENTS.md` (≤ 150 linhas)
- `docs/product/PRD.md`
- `docs/specs/SPEC.md` (**com seção Anti-SPEC obrigatória**)
- `docs/contracts/CONTRACTS.md` (formato novo, função igual)
- `docs/decisions/adr/`
- `.github/workflows/ci.yml` — **CI continua sendo o evaluator**
- Separação generator (gera) ↔ evaluator (valida) via CI
- Rastreabilidade RF → feature → PR
- Princípio "resolver com o mínimo" do skill-scout

---

## Mapeamento rápido para migrar um projeto v2 → Solo

| Ação | Comando / passo |
|---|---|
| Congelar agentes | Pausar qualquer trabalho em andamento |
| Criar `TODO.md` | A partir de `state/project-state.json` + tarefas abertas |
| Arquivar `state/` | `git mv state/ .archive/state-v2-<data>/` |
| Arquivar `TASKS.md` / `WAVE-PLAN.md` | `git mv docs/plans/TASKS.md .archive/` (ou integrar conteúdo relevante no TODO.md/PLAN.md) |
| Migrar contratos para código | Criar arquivos Zod em `packages/shared/types/` a partir do `CONTRACTS.md` |
| Reescrever `CONTRACTS.md` | Versão espelho legível apontando para os novos Zod |
| Atualizar `AGENTS.md` | Trocar seção de agentes para Gerador (Claude Code) + Infra (Cursor Agent opcional) |
| Remover `.cursor/rules/*.mdc` | Se não usar Cursor Agent, apagar. Se usar, consolidar em um único arquivo |
| Rodar CI | Garantir que tudo passa antes de abrir PR de migração |

O detalhamento passo a passo está no **Guia Prático de Uso — Cenário E (migração v2 → Solo)**.
