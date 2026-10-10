# Skills Manifest — [Nome do Projeto] (v3.1)

> Output do `/skill-scout`. Lista enxuta das capacidades do projeto, como cada uma será resolvida e **qual risco operacional carrega**.

**Data:** YYYY-MM-DD
**Versão:** 1.1 (v3.1 — com risco operacional)
**Referência:** SPEC v[X], PLAN v[Y]

---

## 1. Capacidades mapeadas

| # | Domínio | Capacidade | Decisão | Recurso | Classe sugerida | Risco operacional |
|---|---|---|---|---|---|---|
| 1 | Auth | login + signup + sessão | tool_nativa | Supabase Auth SDK | C | dados sensíveis, sem MCP |
| 2 | Banco | migrations + RLS | mcp | Supabase MCP | D | produção, rollback obrigatório, staging |
| 3 | Deploy | web + env | mcp | Vercel MCP | D | produção, envs, rollback via `vercel rollback` |
| 4 | PR / Actions | abertura de PR, status check | nativo | `gh` CLI + Claude Code | B | — |
| 5 | E-mail | transacional | tool_nativa | SDK Resend direto | C | env `RESEND_API_KEY`, fallback planejado |
| 6 | Testes unit/integ | runner | tool_nativa | Vitest | A/B | — |
| 7 | E2E | testes ponta a ponta | tool_nativa | Playwright | C | roda só em N3 |
| 8 | Observabilidade | erros em produção | tool_nativa | Sentry SDK | C | env `SENTRY_DSN` |
| 9 | Pagamento | Stripe / MP | tool_nativa | SDK oficial | D | webhook, idempotência, reconciliação, ADR |

**Legenda decisão:**

- `tool_nativa` — biblioteca/SDK instalada direto no projeto, sem skill extra
- `mcp` — resolvido via MCP em sessão do Cursor Agent (classe D)
- `skill_existente` — skill já instalada
- `skill_nova` — skill a ser criada (último recurso)

**Legenda classe:** ver `risk-classification.md`.

---

## 2. MCPs necessários

> Confirme que estão ativos no Cursor antes de começar execução.

- [ ] **Supabase MCP** — migrations, RLS, seed (classe D)
- [ ] **Vercel MCP** — deploy, envs (classe D)
- [ ] **GitHub MCP** — PR, Actions (opcional se `gh` CLI cobrir)

Configuração: `.cursor/mcp.json` com as variáveis `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `VERCEL_TOKEN`, `GITHUB_TOKEN`.

---

## 3. Skills existentes que serão usadas

- `/project-kickoff` — já consumida
- `/consultor-prd` — já consumida
- `/SDD-avancado` — já consumida
- `/agents-protocol` — próximo passo

Skills extras: *nenhuma* para este projeto.

---

## 4. Skills novas a criar

> Se a tabela de capacidades não marcou `skill_nova`, esta seção fica vazia — cenário ideal.

- *(vazio)*

---

## 5. ADRs sugeridos

> Capacidades com dependência externa nova/crítica geram ADR.

- [ ] ADR-NNN — Escolha de provedor de e-mail (Resend vs SendGrid)
- [ ] ADR-NNN — Estratégia de pagamento (Stripe vs MP vs dual)

---

## 6. Envs necessárias (visão consolidada)

| Env | Ambiente | Escopo | Notas |
|---|---|---|---|
| `SUPABASE_URL` | dev/staging/prod | todas | via Vercel MCP |
| `SUPABASE_SERVICE_ROLE_KEY` | dev/staging/prod | backend | **nunca expor ao client** |
| `RESEND_API_KEY` | staging/prod | backend | — |
| `STRIPE_SECRET_KEY` | staging/prod | backend | webhook separado |
| `SENTRY_DSN` | staging/prod | ambos | frontend e backend |

---

## 7. Observações

- [ex: Stripe exige webhook idempotente — prever F-0XX classe D com Feature Contract detalhado]
- [ex: Supabase RLS precisa auditoria antes de qualquer feature C/D em tabela nova]

---

## 8. Aprovação

- [ ] Todas as capacidades da SPEC mapeadas
- [ ] Nenhum MCP ou skill adicionada sem justificativa real
- [ ] Classe de risco atribuída a cada capacidade
- [ ] ADRs necessários listados
- [ ] Envs consolidadas
- [ ] Manifest revisado
- [ ] Próximo passo: `/agents-protocol`
