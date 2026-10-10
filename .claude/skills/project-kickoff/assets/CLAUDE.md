# CLAUDE.md — Instruções específicas do Claude Code (Harness v3.2)

> Ajustes que só fazem sentido para o Claude Code. Tudo que vale para qualquer agente está em `AGENTS.md`.
> **Máximo: ~140 linhas.**
>
> **v3.2:** integra Project Wiki (`docs/wiki/`) e Fast Fix (`/fast-fix`).

---

## 1. Mapa rápido

- `docs/wiki/index.md` — **leia primeiro** (mapa da memória sintetizada)
- `AGENTS.md` — papéis, classificação A/B/C/D, regras universais, autonomia/pausa
- `TODO.md` — estado atual + Feature Contract inline por feature B/C/D
- `docs/specs/SPEC.md` — comportamento esperado + Anti-SPEC (§6)
- `docs/contracts/CONTRACTS.md` — interfaces (espelho de `packages/shared/types/`)
- `packages/shared/types/` — **source of truth** dos contratos
- `docs/plans/CURRENT_REALITY.md` — estado real do repo (projetos existentes)
- `docs/plans/DECISIONS_LOG.md` — decisões operacionais que voltam ao debate
- `docs/plans/feature-contracts/` — Feature Contracts detalhados (C/D quando o bloco no TODO ficar grande)
- `docs/wiki/log.md` — histórico cronológico (ingest, releases, bugfixes)
- `docs/wiki/runbooks/` — receitas operacionais e bugs recorrentes
- `docs/wiki/context/<F-NNN>.md` — Context Pack da tarefa ativa
- `templates/risk-classification.md` ou `docs/plans/risk-classification.md` — referência A/B/C/D

---

## 2. Ao iniciar uma sessão

Antes de qualquer coisa:

```
1. Ler docs/wiki/index.md (mapa da memória)
2. Ler docs/wiki/context/<tarefa-ativa>.md se existir (handoff)
3. Ler TODO.md (estado + Feature Contract do item em andamento)
4. Ler AGENTS.md (papéis + classificação + autonomia/pausa)
5. Ler SPEC relevante se há feature ativa
6. Ler Feature Contract (inline no TODO ou em docs/plans/feature-contracts/)
7. Ler docs/wiki/log.md últimas entradas (≤ 7 dias)
8. git status && git log --oneline -5
9. Decidir: continuar feature em andamento OU próxima do backlog OU bloqueio OU bug urgente
10. Reportar fase + classe da feature + DoR completa? + pode continuar autônomo?
```

---

## 3. Comandos úteis (ajuste ao projeto real)

```bash
npm run dev              # dev local
npm run lint             # ESLint
npm run typecheck        # tsc --noEmit
npm test                 # unit + integration (Vitest)
npm run test:integration # integration isolado
npm run test:e2e         # Playwright
npm run build            # build de produção
npm run ci:n1            # N1: lint + typecheck + unit (obrigatório A/B + Fast Fix)
npm run ci:n2            # N2: N1 + integration + contract + build (obrigatório C)
npm run ci:n3            # N3: N2 + e2e + smoke (obrigatório D)
```

Se o projeto não tem `ci:n*` scripts, use os comandos individuais e ajuste mapa em `docs/plans/`.

---

## 4. Atalhos de delegação

- **"Bug urgente / hot fix":** dispare **`/fast-fix`** — modo enxuto Project Quick com Prompt 0 embutido. Se escalar para C/D, sai do modo automaticamente.
- **"Implementar feature X":** siga o **Prompt 2** do `checklists/prompts-cheatsheet.md` — valida DoR, cria Feature Contract se B/C/D, implementa, prepara matriz.
- **"Revisar meu PR":** execute o **Prompt 3** — gera matriz CA→teste→evidência, retorna **APROVADO / MUDANÇAS_SOLICITADAS / BLOQUEADO**.
- **"Atualizar a wiki / ingest este log/print/erro":** use **`/wiki ingest`** — distribui na wiki certa + atualiza `log.md`.
- **"Gere context pack para F-NNN":** use **`/wiki context F-NNN`** — cria pack reusável entre Claude/Codex/Cursor.
- **"Auditar a wiki / wiki está bagunçada":** use **`/wiki lint`** seguido de **`/wiki repair`** se necessário.
- **"Investigar bug":** primeiro reproduza com um teste falhando; só depois corrija.

---

## 5. O que NUNCA fazer neste projeto

- Editar `PRD.md`, `SPEC.md` ou Anti-SPEC sem autorização humana.
- Aprovar PR sem matriz de validação preenchida (classes B/C/D).
- Criar pasta `scripts/` na raiz, `state/`, `handoffs/` ou arquivos JSON de estado.
- Inventar tipos em vez de usar `packages/shared/types/`.
- Fazer merge com CI vermelho.
- Rodar migration/deploy/env em produção sem `cursor-brief` com rollback e sem staging (classe D).
- Desabilitar teste ou usar `.skip` sem ADR justificando.
- Forçar Fast Fix em bug que toca auth/payment/db/env/deploy. Escale.
- Atualizar `wiki/overview.md` ou `wiki/architecture.md` quando contradiz PRD/SPEC. Ajuste a fonte primeiro.

---

## 6. Quando pausar e pedir confirmação

Pause imediatamente se:
- Feature crescer além do Feature Contract.
- Precisar alterar arquivo fora da lista "podem ser alterados".
- Classe estimada era B e virou C/D.
- Precisar tocar banco/env/deploy real.
- Encontrar conflito entre docs e código (ou entre wiki e fonte).
- DoR do próximo item estiver incompleta.
- Fast Fix escalou para classe C/D.

Regras completas em `AGENTS.md §9`.

---

## 7. Quando gerar brief para Cursor Agent

Apenas quando a tarefa envolve (classe D):
- Migration Supabase / RLS (Supabase MCP)
- Deploy Vercel / envs (Vercel MCP)
- Workflow GitHub Actions complexo / secrets (GitHub MCP)

Brief fica em `docs/plans/cursor-brief.md` — uma seção por operação, **sempre** com Rollback.

---

## 8. Matriz de validação (lembrete)

Para B/C/D, ao final do Prompt 3:

| CA | Teste | Tipo | Status | Evidência |
|---|---|---|---|---|
| CA-NNN | `arquivo.test.ts` | integration | passou | log do `npm test` |

Sem evidência objetiva → `MUDANÇAS_SOLICITADAS`.

---

## 9. Continuidade entre agentes (acabaram tokens? mudou para Codex/Cursor?)

Antes de fechar a sessão, **rode `/wiki context <F-NNN>`** para a tarefa ativa. O Context Pack vai para `docs/wiki/context/<F-NNN>.md`. Outro agente abre `wiki/index.md` + `wiki/context/<F-NNN>.md` e continua sem perda significativa.

Detalhes em `AGENTS.md §22`.

---

*Atualize este arquivo se mudar scripts, paths ou atalhos do projeto.*
