# Architecture — [Nome do Projeto]

> **Arquitetura técnica viva.** Síntese do SPEC + realidade do código.
>
> **Fonte de verdade:** `docs/specs/SPEC.md` + `packages/shared/types/`.
> Esta página existe para que qualquer agente entenda a topologia em < 5 min sem ler todo o SPEC.

**Última revisão:** YYYY-MM-DD
**Versão do SPEC refletida:** [hash ou data]

---

## 1. Topologia em 1 diagrama (ASCII)

```
[ Browser / SPA ]
       │
       ▼  HTTPS
[ Next.js / API ]
   │       │
   ▼       ▼
[ DB ]   [ Externos: Stripe, Resend, ... ]
```

## 2. Stack

| Camada | Tech | Versão | Notas |
|---|---|---|---|
| Frontend | ... | ... | ... |
| Backend | ... | ... | ... |
| DB | ... | ... | RLS? índices? |
| Infra | ... | ... | provider, regiões |
| Auth | ... | ... | sessão? JWT? cookie? |
| Observabilidade | ... | ... | logs, traces, métricas |

## 3. Módulos

> Cada módulo tem sua própria página em `wiki/modules/`. Aqui só o mapa.

| Módulo | Responsabilidade | Página |
|---|---|---|
| auth | login, sessão, permissões | [`modules/auth.md`](./modules/auth.md) |
| db | schema, migrations, RLS | [`modules/db.md`](./modules/db.md) |
| api | endpoints HTTP | [`modules/api.md`](./modules/api.md) |
| web | UI / SPA | [`modules/web.md`](./modules/web.md) |
| payments | Stripe / MP / Pix | [`modules/payments.md`](./modules/payments.md) |
| jobs | filas, cron | [`modules/jobs.md`](./modules/jobs.md) |
| deploy | Vercel / GH Actions | [`modules/deploy.md`](./modules/deploy.md) |

> Crie módulos só quando o projeto realmente tem essa área. Não invente módulos vazios.

## 4. Fronteiras (boundaries)

Onde Zod **deve** estar:

- API request/response (`apps/api/**`)
- Env vars (carregamento)
- Storage (DB serialization quando aplicável)
- IPC / mensageria interna

## 5. Decisões arquiteturais (ADRs ativos)

| ADR | Decisão | Status |
|---|---|---|
| ADR-001 | Next.js + Supabase | aceito |
| ADR-002 | Cookie httpOnly em vez de localStorage | aceito |
| ADR-003 | ... | ... |

→ Documentos completos em [`docs/decisions/adr/`](../decisions/adr/).

## 6. Restrições arquiteturais ativas (Anti-SPEC ressaltada)

> Os 3-5 itens da Anti-SPEC mais relevantes para arquitetura. O resto está em SPEC §6.

- NÃO inventar tipos fora de `packages/shared/types/`.
- NÃO usar `localStorage` para tokens.
- NÃO bypass RLS por convicção; só com `service_role` em job server-side documentado.
- ...

## 7. O que NÃO faz parte da arquitetura

> Coisas que parecem mas não são. Reduz alucinação do agente.

- Não há cache distribuído (sem Redis).
- Não há fila assíncrona (sem RabbitMQ/SQS); jobs rodam em cron Vercel.
- ...

---

## Links

- SPEC completo → [`docs/specs/SPEC.md`](../specs/SPEC.md)
- Contratos → [`docs/contracts/CONTRACTS.md`](../contracts/CONTRACTS.md)
- Realidade do código → [`docs/plans/CURRENT_REALITY.md`](../plans/CURRENT_REALITY.md)
- Decisões → [`docs/decisions/adr/`](../decisions/adr/)
- Decisões operacionais → [`docs/plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md)

---

*Atualize: ao adicionar/remover módulo, ao trocar lib core, ao aprovar ADR. Não atualize por refactor interno de módulo.*
