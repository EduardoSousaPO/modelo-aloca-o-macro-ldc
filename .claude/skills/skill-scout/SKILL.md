---
name: skill-scout
description: >
  Verifica, no contexto do Harness v3.1, se as capacidades necessárias para executar o projeto já estão cobertas por ferramentas nativas (Claude Code, Cursor) ou MCPs disponíveis — e registra o resultado em docs/plans/skills-manifest.md, incluindo análise de risco operacional (produção, rollback, staging, envs, ADR). Princípio: resolver com o mínimo. Priorize sempre tool nativo / MCP antes de pensar em criar skill nova.
  Use esta skill APÓS o /SDD-avancado estar aprovado e ANTES de começar a executar features. Ative quando o usuário mencionar: "verificar skills", "preparar capacidades", "skill scout", "o que temos disponível", "quais MCPs usar", "precisa criar skill?", "risco operacional", ou qualquer variação indicando transição da documentação para execução. Opcional — só faz sentido se o projeto envolve integrações não triviais (Supabase, Stripe, e-mail, deploy, etc.).
---

# /skill-scout — Resolver capacidades com o mínimo + risco operacional (v3.1)

Você ativou o **Skill Scout** do Harness v3.1. Sua missão é verificar se as capacidades que o projeto precisa já estão cobertas por ferramentas nativas ou MCPs — e indicar para cada uma **qual risco operacional carrega** (produção, env, rollback, ADR).

> **Princípio:** Cada skill nova é uma superfície para manter. Cada MCP novo é um vetor de erro. Cada dependência nova tem custo. Resolver com o mínimo é a regra.

**Posição no fluxo:**

```
/consultor-prd → /SDD-avancado → [/skill-scout] → /agents-protocol → execução
```

Esta skill é **opcional**. Se o projeto é um CRUD simples com stack conhecida, pule.

---

## Diferenças em relação ao v3.0

| v3.0 | v3.1 | Motivo |
|---|---|---|
| Gate de 3 níveis (nativo/MCP → skill → criar skill) | Gate de 3 níveis + análise de **risco operacional** por capacidade | Capacidade que toca produção/env/banco precisa de marcação explícita |
| Output com decisão técnica | Output com decisão técnica + classe de risco sugerida (C ou D para a feature associada) | Alinha skill-scout com classificação A/B/C/D |
| Não avalia necessidade de ADR | Indica necessidade de ADR por capacidade | Dependência crítica nova exige ADR |

---

## O que esta skill produz

```
docs/plans/skills-manifest.md      ← único output
```

Conteúdo enxuto: lista de capacidades + decisão (tool nativa | MCP | skill existente | criar skill) + **risco operacional** (classe sugerida C/D, precisa staging/rollback/ADR, env vars, segredos).

**O que NÃO produz por padrão:** novas skills. Criar skill é último recurso.

---

## Processo — 3 passos

### PASSO 1 — Mapear capacidades necessárias

Leia:
- `docs/specs/SPEC.md` — quais comportamentos
- `docs/contracts/CONTRACTS.md` + `packages/shared/types/` — quais integrações
- `docs/plans/PLAN.md` (se existir)
- `docs/plans/CURRENT_REALITY.md` (se existir)

Extraia capacidades por domínio:
- Auth (Supabase Auth? Clerk? custom JWT?)
- Banco + Migrations
- Deploy
- E-mail
- Storage
- Pagamentos
- Analytics / Logging
- CI/CD
- Webhooks externos (Stripe, MP, etc.)
- Agendamento / Jobs

### PASSO 2 — Para cada capacidade, aplicar GATE SOLO + análise de risco

**Percorra na ordem. Pare no primeiro nível que resolver.**

#### Nível 1 — Nativo ou MCP resolve?

**MCPs relevantes:**

| Capacidade | MCP | Decisão |
|---|---|---|
| SQL / migrations / RLS Supabase | Supabase MCP | → MCP (classe D) |
| Deploy / variáveis Vercel | Vercel MCP | → MCP (classe D) |
| PR / issues / Actions | GitHub MCP | → MCP (classe C/D conforme operação) |
| E-mail Resend | Resend MCP (se disponível) | → MCP (classe C) |

#### Nível 2 — Skill existente?
#### Nível 3 — Criar skill nova?

Criar skill nova **só se**:
- Não há MCP nem tool nativa.
- Não há skill existente adequada.
- A capacidade é **recorrente** (≥ 3 projetos).
- Genuinamente reutilizável.
- Sem a skill, output inconsistente.

#### Análise de risco operacional (v3.1 · reforçada pelo Validation Mode Patch)

Para cada capacidade, responda:

- **Afeta produção?** [sim/não] — se sim, classe D.
- **Precisa Cursor Agent (MCP)?** [sim/não]
- **Precisa staging antes de produção?** [sim/não]
- **Precisa rollback plan?** [sim/não]
- **Envolve segredos/env vars?** [sim/não + nome das envs]
- **Precisa ADR?** [sim/não + motivo — geralmente quando é dependência nova crítica]
- **Precisa linha no DECISIONS_LOG?** [sim/não + motivo — decisões operacionais menores que não justificam ADR mas voltam ao debate]
- **Testes mínimos exigidos (ver `risk-classification.md §Testes mínimos`):** [unit / integration / contract / e2e / smoke / migration validation]
- **Classe sugerida para features que a usam:** [A/B/C/D]
- **Risco de auto-reclassificação alto?** [sim/não — ex.: "feature marcada como B mas quase certo vai tocar auth → trate como C desde o início"]

### PASSO 3 — Gerar `docs/plans/skills-manifest.md`

Use `assets/skills-manifest-template.md` — enxuto, 1 página.

Salve e comunique:

```
skills-manifest.md gerado.

Resumo:
- N capacidades cobertas por MCP/nativo
- M capacidades cobertas por skill existente
- K capacidades requerem skill nova (se > 0, listadas)

Risco operacional:
- X capacidades exigem classe D (produção/infra)
- Y capacidades exigem classe C (dados sensíveis / auth / pagamento)
- Z envs novas a configurar
- W ADRs a escrever

Próximo passo: /agents-protocol
```

---

## Regras desta skill

- **MCPs têm prioridade.** Supabase MCP faz migrations — não crie skill `supabase-migrations`.
- **Skills específicas de cliente não entram no catálogo global.** Ficam em `docs/` ou `AGENTS.md`.
- **Menos é mais.** Se o manifest tiver mais de 5 skills listadas, provavelmente há sobreposição.
- **Qualidade > quantidade.**
- **Não crie `state/*.json`.**
- **Capacidade que toca produção = classe D.** Marcar explicitamente no manifest.
- **Capacidade com dependência externa nova = ADR.** Marcar no manifest.

---

## Assets desta skill

- `assets/skills-manifest-template.md` — template do manifest (v3.1 com risco operacional)

## Referências

- `references/skill-creation-protocol.md`
- `references/catalog-scan-guide.md`
