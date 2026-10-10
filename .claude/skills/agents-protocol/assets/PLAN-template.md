# PLAN — [Nome do Projeto]

> Plano de entrega organizado por **ondas de features** (não por tarefas atômicas). Criar apenas quando o TODO.md ordenado não é suficiente — tipicamente projetos com > 6 features ou com dependências cruzadas.

**Versão:** 1.0
**Data:** YYYY-MM-DD
**Responsável:** Desenvolvedor solo

---

## 1. Visão geral

Uma frase resumindo o objetivo do plano e o horizonte temporal.

> Exemplo: "Entregar o MVP em 3 ondas ao longo de 4 semanas — fundação (auth + base), core (domínio de negócio), polimento (observabilidade + export)."

---

## 2. Stack e premissas

- Linguagem/framework: [ex: TypeScript, Next.js 14, React 19]
- Banco: [ex: Supabase Postgres]
- Hosting: [ex: Vercel]
- Dependências externas: [ex: Resend, Stripe]
- Pré-requisitos aprovados: SPEC v[X], CONTRACTS v[Y]

---

## 3. Ondas de entrega

> Cada onda é um conjunto coerente de features que entregam valor observável. Granularidade mínima: **feature** (nunca task).

### Onda 1 — Fundação

**Objetivo:** aplicação rodando localmente com auth e layout básico.
**Duração estimada:** 1–2 dias.

- F-001 — Estrutura do monorepo + CI verde em push
- F-002 — Health check da API
- F-003 — Login com e-mail/senha (depende de F-001, F-002)
- F-004 — Signup com confirmação por e-mail (depende de F-003)
- F-005 — Dashboard vazio pós-login (depende de F-003)

**Critério de saída da onda:** criar conta → confirmar e-mail → login → ver dashboard vazio; CI verde em main.

**Infra necessária (MCP):**
- Supabase MCP — migration inicial (`users`, `sessions`), política RLS
- Vercel MCP — deploy de preview + env `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

### Onda 2 — Core de negócio

**Objetivo:** o fluxo principal do produto ponta a ponta, persistido.
**Duração estimada:** 3–5 dias.

- F-006 — [feature principal do domínio]
- F-007 — [feature dependente]
- F-008 — [feature dependente]
- F-009 — [feature dependente]

**Critério de saída da onda:** usuário consegue [resultado observável central do produto].

**Infra necessária (MCP):**
- Supabase MCP — tabelas `[nome]` + RLS por `owner_id`
- Vercel MCP — nenhum env novo

---

### Onda 3 — Polimento + observabilidade

**Objetivo:** produto pronto para beta.
**Duração estimada:** 2–3 dias.

- F-010 — Export de dados (CSV)
- F-011 — Logs estruturados + integração Sentry
- F-012 — Página de billing (stub)

**Critério de saída da onda:** smoke test completo passa; erros em produção aparecem no Sentry.

**Infra necessária (MCP):**
- Vercel MCP — envs `SENTRY_DSN`, `SENTRY_AUTH_TOKEN`
- Supabase MCP — view `user_activity` para export

---

## 4. Dependências entre ondas

```
Onda 1 ──▶ Onda 2 ──▶ Onda 3
   │                    ▲
   └──── F-012 pode começar em paralelo ao final da Onda 2
```

Se uma feature atravessa duas ondas, documente aqui.

---

## 5. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Supabase RLS errada permite vazamento | Alto | Teste de segurança dedicado em cada migration |
| Custo de e-mail acima do estimado | Médio | Usar plano free do Resend até 100 usuários |
| Deploy Vercel preview falha com env nova | Baixo | Listar todos os envs no cursor-brief.md |

---

## 6. Métricas de acompanhamento

- % de features da onda atual concluídas
- CI verde em main: sim/não
- Dias desde último deploy em produção

---

## 7. Aprovação

- [ ] Ondas refletem dependências reais (não inventadas)
- [ ] Critério de saída de cada onda é observável
- [ ] Infra via MCP está mapeada por onda
- [ ] Não existem tasks atômicas neste plano (só features)
