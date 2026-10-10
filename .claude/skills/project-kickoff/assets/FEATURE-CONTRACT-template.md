# Feature Contract — F-NNN [Nome da feature]

> Contrato operacional da feature. Obrigatório para classes **B, C, D**. Opcional para **A**.
>
> **Onde vive:** preferencialmente como bloco dentro do próprio item no `TODO.md`. Só extraia para `docs/plans/feature-contracts/F-NNN.md` se o bloco passar de ~40 linhas (típico em C e D).
>
> **Quando criar:** antes da primeira linha de código. Gerado pelo agente no Prompt 2 quando ainda não existe.
>
> **Quem atualiza:** o agente ao longo da implementação, se o escopo mudar — mas mudança de escopo exige **pausa** e confirmação humana.

---

## Identificação

- **ID:** F-NNN
- **Nome:** [curto]
- **Risco:** [A | B | C | D]  — ver `risk-classification.md`
- **Cobre:** RF-NNN, RF-NNN (referência ao `SPEC.md`)
- **Branch proposta:** `feat/<slug>`
- **Data:** YYYY-MM-DD

---

## Objetivo

[1–3 frases. O que esta feature entrega e para quem.]

---

## Definition of Ready (DoR)

> Marque todos antes de começar a implementar. Se algum está em branco → **pausa**, resolva antes.

- [ ] Há RFs ou justificativa clara para a feature.
- [ ] Critérios de aceite explícitos (lista abaixo).
- [ ] Escopo **incluído** descrito (o que será feito).
- [ ] Escopo **excluído** descrito (o que não será feito).
- [ ] Classificação de risco A/B/C/D confirmada.
- [ ] Arquivos prováveis de alteração listados.
- [ ] Testes esperados listados (unit / integration / e2e / smoke).
- [ ] Contratos Zod necessários identificados (ou decisão explícita de que não precisa).
- [ ] Dependências externas/services identificados.
- [ ] Impacto em banco avaliado (migration necessária? destrutiva?).
- [ ] Impacto em produção avaliado (rollback? staging? feature flag?).

---

## Critérios de aceite

- **CA-NNN:** [Given/When/Then ou prosa curta e testável]
- **CA-NNN:** ...

---

## Escopo incluído

- [bullet concreto: "POST /auth/login retornando JWT em cookie httpOnly"]
- ...

## Escopo excluído (não será feito nesta feature)

- [bullet concreto: "Não adiciona 2FA — fica para F-0XX"]
- ...

---

## Arquivos

### Arquivos que podem ser alterados

- `apps/api/src/auth/login.ts`
- `apps/web/src/routes/login.tsx`
- `packages/shared/types/auth.ts`
- `tests/integration/auth.login.test.ts`

### Arquivos que NÃO podem ser alterados

- `docs/specs/SPEC.md` (sem autorização humana)
- `docs/product/PRD.md`
- Anti-SPEC (`SPEC.md §6`)
- Arquivos fora do escopo listado acima

> **Regra v3.1 Validation Mode Patch:** qualquer alteração fora da lista "podem ser alterados" resulta em `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT` no QA, exceto se o agente apresentar **justificativa aceita** com 7 itens (arquivo, motivo, impacto, escopo, contrato, testes, reclassificação — ver `AGENTS.md §18`).
>
> Se a justificativa toca **produto, produção, banco, auth, pagamento ou dados sensíveis**, o agente pausa e pede confirmação humana. Nunca prossegue automaticamente.

---

## Contratos

- [ ] Contratos Zod já existem em `packages/shared/types/` — **sim**, especificamente: `LoginInput`, `LoginResponse`.
- [ ] Contratos a **criar/atualizar**: [lista]
- [ ] `CONTRACTS.md` precisa ser atualizado? **[sim/não]** — justifique.

---

## Testes obrigatórios

> Mapear **antes** de implementar. Se não há teste proposto para um CA, o CA não está pronto.
>
> **Mínimos por classe** (fonte única em `risk-classification.md §Testes mínimos`):
>
> - **A:** teste opcional se a mudança é realmente isolada; senão vira B.
> - **B:** ≥1 teste por CA (unit ou integration).
> - **C:** ≥1 teste por CA crítico + ≥1 edge case + ≥1 teste negativo + integration obrigatório se há API/auth/regra/dados + e2e se toca fluxo principal + build.
> - **D:** integration quando aplicável + smoke + staging + rollback + migration validation + envs + e2e/manual evidenciado.
>
> Testes "fake" (`expect(true).toBe(true)`, teste que só renderiza, teste que mocka a regra sob validação) **não contam** — o Prompt 3 rejeita.

| Teste | Tipo | Cobre CA | Arquivo |
|---|---|---|---|
| `login com credenciais válidas retorna 200 + cookie` | integration | CA-001 | `tests/integration/auth.login.test.ts` |
| `login com senha errada retorna 401 INVALID_CREDENTIALS` | integration negativo | CA-002 | idem |
| `rate limit 5/min/IP` | integration | CA-003 | idem |
| `login com payload sem campo email retorna 400` | integration edge case | CA-001 | idem |
| `fluxo login na UI` | e2e (classe C/D) | CA-001 | `tests/e2e/login.spec.ts` |

---

## Comandos obrigatórios (CI local)

**Nível CI alvo:** [N1 | N2 | N3] — derivado da classe de risco.

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run test:integration`  *(a partir de N2)*
- `npm run test:e2e`          *(a partir de N3)*
- `npm run build`             *(a partir de N2)*

---

## Infra / Produção (só para classes C e D)

- **Migration necessária?** [sim/não] — se sim: `infra/supabase/migrations/NNNN_nome.sql`
- **Migration é destrutiva?** [sim/não] — se sim, descreva backup plan.
- **Precisa Cursor Agent via MCP?** [sim/não] — se sim, seção correspondente em `docs/plans/cursor-brief.md`.
- **Env vars novas?** [lista]
- **Staging obrigatório?** [sim/não] — para classe D, sempre sim.
- **Feature flag?** [sim/não] — sim se altera contrato público ou rollout gradual.
- **Rollback plan (≤5 linhas):**
  1. [passo]
  2. [passo]

---

## Evidência esperada (Matriz de Validação)

> Preencher o status durante o Prompt 3 — QA do PR. Se algum CA não tem evidência objetiva, resultado é **MUDANÇAS_SOLICITADAS**.

| CA | Teste | Tipo | Status | Evidência (comando/arquivo/log) |
|---|---|---|---|---|
| CA-001 | `auth.login.test.ts` | integration | [passou/falhou/não coberto] | `npm test -- auth.login` log |
| CA-002 | idem | integration | — | — |
| CA-003 | idem | integration | — | — |

---

## Anti-SPEC — checagem específica

Para classes C e D, o agente **lista explicitamente** quais itens da Anti-SPEC (`SPEC.md §6`) são mais relevantes para esta feature, e confirma no QA que nenhum foi violado.

- [ ] NÃO logar senhas/tokens/PII.
- [ ] NÃO permitir admin alterar senha de outros usuários.
- [ ] [item específico desta feature]

---

## Gate de autonomia

O agente pode prosseguir automaticamente enquanto:
- Os arquivos alterados estão na lista "podem ser alterados".
- Os CAs sendo implementados são os descritos acima.
- Os testes estão passando localmente.
- Não foi detectada mudança em PRD/SPEC/Anti-SPEC.
- A classe não precisou subir (ver auto-reclassificação em `AGENTS.md §16`).

O agente **deve pausar** se:
- Precisar alterar arquivo fora da lista permitida **e** a alteração toca produto/produção/banco/auth/pagamento/dados sensíveis (se for operacional sem risco, aplica-se o fluxo de justificativa — `AGENTS.md §18`).
- Um CA novo surgir (mudança de escopo).
- Encontrar conflito entre código existente e SPEC.
- Classe estimada era A/B e precisa subir para C/D (reclassifique primeiro).
- Qualquer operação de produção/infra real (classe D).

O agente **deve retornar BLOQUEADO** se:
- DoR está incompleta e a lacuna toca domínio sensível → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`.
- Arquivo alterado fora da lista sem justificativa aceita → `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT`.
- Reclassificação foi identificada mas o contrato ainda não foi atualizado → `BLOQUEADO — RECLASSIFICAÇÃO PENDENTE`.
- Anti-SPEC violada → `BLOQUEADO — ANTI-SPEC VIOLADA`.

---

## Resultado final

- **Status:** [em andamento | concluído | bloqueado]
- **PR:** [#NNN](link)
- **SHA:** [hash]
- **Data de merge:** YYYY-MM-DD
- **Evidência consolidada:** ver matriz acima + log do CI.

---

*Este contrato é a fonte de verdade da feature. Se o código diverge do contrato, ou o contrato diverge da realidade, corrija o contrato (ou o código) — nunca ignore a divergência.*
