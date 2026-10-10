# TODO — [Nome do Projeto]

> Estado vivo do projeto. Substitui `state/project-state.json`, `progress.jsonl` e `handoffs/` do Harness v2 tradicional.
> Atualize ao iniciar, ao terminar uma feature e ao fim do dia.
>
> **v3.1 — Feedback Hardened:** cada feature B/C/D traz o **Feature Contract inline** (DoR + escopo + arquivos + matriz). Features A podem ter apenas a descrição mínima.

**Última revisão:** 2026-04-24
**Fase:** kickoff | discovery | spec | execução | manutenção
**Foco atual:** <feature ou objetivo da semana>

---

## 1. Em andamento

> Máximo 2 itens simultâneos. Se tiver mais, você está dispersando.

### [ ] F-003 — Login com e-mail/senha

- **Risco:** C (auth é sempre C no mínimo)
- **Cobre:** RF-001, RF-002
- **Branch:** `feat/login-pkce`
- **CI alvo:** N2 (lint + typecheck + unit + integration + contract + build)

**Definition of Ready**
- [x] RFs claros (RF-001, RF-002)
- [x] Critérios de aceite testáveis (abaixo)
- [x] Escopo incluído/excluído explícito
- [x] Risco confirmado (C)
- [x] Arquivos prováveis listados
- [x] Testes mapeados (abaixo)
- [x] Contratos Zod: `LoginInput`, `LoginResponse` em `packages/shared/types/auth.ts`
- [x] Banco: usa tabela `users` existente, sem migration
- [x] Produção: rate limit em memória, sem env nova

**Escopo incluído**
- POST /auth/login com validação Zod
- Cookie httpOnly + SameSite=Lax
- Rate limit 5/min/IP em memória
- Testes integração + e2e

**Escopo excluído**
- Não implementa 2FA (vira F-0XX)
- Não adiciona login social (vira F-0XX)
- Não altera tabela `users`

**Arquivos que podem ser alterados**
- `packages/shared/types/auth.ts`
- `apps/api/src/auth/login.ts`
- `apps/web/src/routes/login.tsx`
- `tests/integration/auth.login.test.ts`
- `tests/e2e/login.spec.ts`
- `docs/contracts/CONTRACTS.md` (espelho)

**Arquivos que NÃO podem ser alterados (sem pausa + confirmação)**
- `docs/specs/SPEC.md`
- `docs/product/PRD.md`
- Tabela `users` (migration) — qualquer mudança vira F-0XX com classe D

**Critérios de aceite**
- [ ] **CA-001:** POST /auth/login retorna 200 + JWT em cookie httpOnly quando credenciais válidas
- [ ] **CA-002:** retorna 401 com `INVALID_CREDENTIALS` quando senha errada
- [ ] **CA-003:** rate limit 5/min por IP — 6ª tentativa retorna 429 com `retry_after`
- [ ] **CA-004:** fluxo UI ponta a ponta (login → dashboard) funciona

**Testes obrigatórios** (mínimos por classe em `risk-classification.md`)

| Teste | Tipo | Cobre CA | Arquivo |
|---|---|---|---|
| login credenciais válidas | integration | CA-001 | `tests/integration/auth.login.test.ts` |
| login senha errada | integration negativo | CA-002 | idem |
| rate limit | integration | CA-003 | idem |
| login payload sem email | integration edge case | CA-001 | idem |
| fluxo UI | e2e | CA-004 | `tests/e2e/login.spec.ts` |

**Anti-SPEC relevante** (SPEC §6)
- NÃO logar senhas/tokens
- NÃO permitir admin acessar dados de outros usuários
- NÃO armazenar senha em texto claro

**Matriz de validação (preenchida no Prompt 3 — QA)**

| CA | Teste | Tipo | Status | Evidência |
|---|---|---|---|---|
| CA-001 | `auth.login.test.ts::valid_credentials` | integration | — | — |
| CA-002 | `auth.login.test.ts::invalid_password` | integration | — | — |
| CA-003 | `auth.login.test.ts::rate_limit` | integration | — | — |
| CA-004 | `login.spec.ts::happy_path` | e2e | — | — |

**Notas:** começar pelo schema Zod em `auth.ts`; teste primeiro, implementação depois.

---

## 2. Backlog (próximas features)

> Ordem é intencional. Priorizado por valor × risco × dependência. Cada item trará seu bloco de Feature Contract ao ser movido para "Em andamento".

### [ ] F-004 — Signup com confirmação por e-mail
- **Risco:** C (envia e-mail real, cria conta)
- **Cobre:** RF-003
- **Depende de:** F-003
- **Resumo:** envia e-mail via Resend, valida token, cria conta com `is_active=false` até confirmar.
- *Feature Contract será preenchido ao entrar em andamento.*

### [ ] F-005 — Dashboard inicial
- **Risco:** B
- **Cobre:** RF-010
- **Resumo:** mostra métricas reais (sem mock); empty state tratado; p95 < 500ms.

### [ ] F-006 — Exportar relatório PDF
- **Risco:** B (ou C se batches > 100k)
- **Cobre:** RF-015
- **Resumo:** PDF gerado server-side; batches > 100k linhas falham cedo com erro amigável.

---

## 3. Concluído

> Movido para cá ao fazer merge. Inclua SHA/PR.

- [x] **F-002 — Health check + boilerplate API** — `#12` — `a1b2c3d` — 2026-04-16 (classe A, CI N1 verde)
- [x] **F-001 — Estrutura do monorepo + CI** — `#5` — `0f8e7d6` — 2026-04-15 (classe B)

---

## 4. Bloqueios

- [ ] *(vazio)*

> Se tiver bloqueio: descreva o problema, o que já foi tentado e o que precisa para destravar. **Não pausar trabalho em outra feature para resolver bloqueio — use o bloqueio como input de conversa com humano/cliente e siga em outra coisa.**

---

## 5. Bugs abertos

| ID | Descrição curta | Repro | Gravidade | Classe se virar feature | Nota |
|---|---|---|---|---|---|
| BUG-001 | Token JWT não invalida no logout | `POST /auth/logout && GET /me` ainda retorna 200 | alta | C | candidato a próxima sessão |

---

## 6. Ideias / parking lot

> Coisas que apareceram mas não devem quebrar o foco. Revisar a cada 2 semanas.

- Integração com Google Sign-In (seria v2)
- Dark mode (baixa prioridade)
- Webhook de auditoria externa

---

## 7. Definition of Done (DoD) — aplica a TODA feature

### Classe A
- [ ] CI N1 local verde (`npm run lint && npm run typecheck && npm test`)
- [ ] `TODO.md` atualizado (item → Concluído com SHA)
- [ ] Teste cobre o CA (mesmo que unit simples)

### Classe B
- [ ] Tudo de A +
- [ ] Feature Contract preenchido acima
- [ ] Matriz de validação com status = passou em todos CAs
- [ ] CI verde no PR
- [ ] `CONTRACTS.md` atualizado se contratos mudaram

### Classe C
- [ ] Tudo de B +
- [ ] CI N2 verde (integration + contract + build)
- [ ] Anti-SPEC verificada explicitamente no Prompt 3
- [ ] Revisão humana antes do merge (recomendada)
- [ ] ADR se houve decisão arquitetural

### Classe D
- [ ] Tudo de C +
- [ ] CI N3 verde (e2e + smoke)
- [ ] `cursor-brief.md` com Rollback executado
- [ ] Staging validado antes de produção
- [ ] Smoke test pós-deploy registrado
- [ ] Feature flag se altera contrato público

---

*Este arquivo substitui por completo `state/project-state.json`, `progress.jsonl`, `handoffs/*.json` e `bugs/*.md` do Harness v2. O histórico vive no `git log`. Feature Contracts vivem aqui inline (ou em `docs/plans/feature-contracts/F-NNN.md` quando extensos). Decisões operacionais que provavelmente voltarão ao debate vão para `docs/plans/DECISIONS_LOG.md`. Produto e comportamento permanecem em PRD/SPEC/Anti-SPEC e só mudam com autorização humana.*
