# TODO — PomoFocus (exemplo preenchido)

> Exemplo de `TODO.md` realmente em uso no meio de um projeto. Use como referência — não copie literal.

**Projeto:** PomoFocus (SaaS de pomodoro para times)
**Última atualização:** 2026-04-15 18:40

---

## 1. Em andamento

- [~] **F-006 — Iniciar e pausar sessão de pomodoro**
  - Branch: `feat/pomodoro-session`
  - Status: implementação ~70%. Falta o endpoint `POST /sessions/:id/pause` e cobrir CA-023.
  - Próximo passo: escrever teste para `pause()` bloqueando sessão já pausada.
  - Arquivos tocados: `apps/api/src/sessions/*`, `packages/shared/types/session.ts`, `tests/integration/session.test.ts`.

---

## 2. Backlog (próximas)

- [ ] **F-007 — Encerrar sessão e registrar duração efetiva** (depende de F-006)
- [ ] **F-008 — Histórico de sessões por usuário** (depende de F-007)
- [ ] **F-009 — Export CSV do histórico** (depende de F-008)
- [ ] **F-010 — Integração Slack (notificar fim de foco)** — depende de decisão em ADR-004 (ainda não aprovado)

---

## 3. Concluído

- [x] **F-001 — Monorepo + CI verde em push** — `#12` / `a1b2c3d` — 2026-04-08
- [x] **F-002 — Health check da API** — `#13` / `f4e5d6a` — 2026-04-08
- [x] **F-003 — Login com e-mail/senha** — `#15` / `9c8b7a6` — 2026-04-10
- [x] **F-004 — Signup com confirmação por e-mail** — `#17` / `3d2e1f0` — 2026-04-11
- [x] **F-005 — Dashboard vazio pós-login** — `#18` / `7b6a5c4` — 2026-04-13

---

## 4. Bloqueios

- Nenhum ativo.

## 5. Bugs

- [ ] **B-001** — `GET /sessions` retorna 500 quando usuário tem 0 sessões (em vez de `[]`). Descoberto em staging 2026-04-14. Arquivo: `apps/api/src/sessions/list.ts`. Preciso reproduzir em teste de integração.

## 6. Ideias (fora de escopo, revisar depois)

- Adicionar "modo silencioso" — nenhuma notificação.
- Gráfico semanal de foco no dashboard.
- Export ICS (calendário) além de CSV.

## 7. Débito técnico

- Refatorar `apps/web/src/lib/api.ts` — usa fetch direto em 4 lugares, deveria passar pelo client wrapper.
- Migrar testes antigos de `tests/integration/auth/` para usar o setup novo de `fixtures/auth.ts`.

---

## 8. Definition of Done (referência — não mexer)

Uma feature está **done** quando:

1. Todos os critérios de aceite do item têm teste passando.
2. `npm run lint && npm run typecheck && npm test` verde localmente.
3. CI do GitHub Actions verde.
4. Se mudou contrato: `packages/shared/types/` atualizado + `CONTRACTS.md` espelhado.
5. Se adicionou dependência ou tomou decisão arquitetural: ADR criado.
6. PR mergeado em `main` (ou merge direto se tarefa trivial).
7. Este arquivo atualizado: item movido para "Concluído" com SHA/PR.
