# PLAN — [Nome do Projeto]

> **Opcional.** Só crie quando o projeto tem mais de ~8 features ou dependências não-triviais entre features.
> Para projetos pequenos, o `TODO.md` ordenado já basta.
>
> Versão: 1.0 — Referência: SPEC v[X]

---

## 1. Stack

- **Frontend:** [ex: Next.js 14 + React 19 + TailwindCSS + shadcn]
- **Backend:** [ex: Next.js Route Handlers ou tRPC]
- **Banco:** [ex: Supabase Postgres]
- **Auth:** [ex: Supabase Auth + JWT httpOnly]
- **Deploy:** [ex: Vercel (app) + Supabase (db)]
- **Testes:** Vitest + Playwright
- **Tipos compartilhados:** Zod + TypeScript em `packages/shared/types/`

Justificativa das escolhas principais: ver `docs/decisions/adr/ADR-001-stack.md`.

---

## 2. Arquitetura em alto nível

```
┌────────────┐   HTTPS   ┌────────────┐   Postgres   ┌────────────┐
│  apps/web  │──────────▶│  apps/api  │─────────────▶│  Supabase  │
└────────────┘           └────────────┘              └────────────┘
       │                        │
       │    import tipos Zod    │
       └────────▶ packages/shared/types/ ◀──────────┘
```

---

## 3. Ondas (sequência de features)

> Uma onda = um bloco coerente. Features de uma onda podem ser implementadas em qualquer ordem; ondas seguintes só começam quando a anterior está **verde no CI**.

### Onda 1 — Fundação (1–2 dias)
**Objetivo:** aplicação rodando com auth e dashboard vazio.

- F-001 — Estrutura do monorepo + CI
- F-002 — Health check da API
- F-003 — Login com e-mail/senha
- F-004 — Signup com confirmação de e-mail

**Critério de saída da onda:** consigo criar conta → login → ver dashboard vazio, com todos os testes verdes.

### Onda 2 — Jornada principal (2–3 dias)
**Objetivo:** usuário consegue realizar o caso de uso principal.

- F-005 — Dashboard com dados reais
- F-006 — CRUD do recurso principal
- F-007 — Exportar relatório PDF

**Critério de saída:** smoke test e2e da jornada principal passa em staging.

### Onda 3 — Polimento e produção (1 dia)
**Objetivo:** entregar para usuários reais.

- F-008 — Logging estruturado + monitoring (Sentry)
- F-009 — Seed de dados e staging
- F-010 — Deploy produção + smoke test

---

## 4. Dependências entre ondas

```
Onda 1 ──► Onda 2 ──► Onda 3
            │
            └─► (pode iniciar infra de monitoring em paralelo)
```

---

## 5. Riscos técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| PDF gen lento em batches grandes | Média | Alta | job assíncrono + limite de 10k linhas síncrono |
| Rate limit e-mail provider | Baixa | Média | fallback para segundo provider |

---

## 6. ADRs a escrever

- ADR-001 — Escolha de stack
- ADR-002 — Estratégia de auth (JWT vs cookie vs Supabase Auth nativo)
- ADR-003 — Estratégia de testes e cobertura mínima

---

*Próximo passo: popular `TODO.md` com a Onda 1 e começar a implementar feature a feature.*
