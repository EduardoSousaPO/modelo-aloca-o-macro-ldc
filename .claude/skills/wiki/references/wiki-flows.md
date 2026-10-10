# Wiki Flows — referência detalhada

> Exemplos por modo. Use como apoio quando o contexto da operação não estiver óbvio.

---

## Fluxo 1 — INGEST de print de erro

**Usuário:** "ingest este erro: `[stack trace de NextAuth: JWTSessionError: ...]`"

**Agente:**

1. Tipo identificado: erro recorrente em auth.
2. Verifica se `wiki/runbooks/bug-jwt-*.md` existe → não.
3. Verifica `TODO.md §5 Bugs abertos` → BUG-001 já listado.
4. Cria `wiki/runbooks/bug-jwt-session-error.md` usando template.
5. Linka runbook no item BUG-001 do `TODO.md`.
6. Adiciona linha em `wiki/log.md`:
   ```
   - [2026-05-08 14:32] [INGEST] erro NextAuth JWTSessionError — runbook criado em wiki/runbooks/bug-jwt-session-error.md — ref: BUG-001
   ```
7. Reporta ao usuário: "Runbook criado. Próxima ocorrência → consulte runbook antes de tentar fix."

---

## Fluxo 2 — INGEST de decisão verbal

**Usuário:** "decisão: a partir de agora não vamos mais usar TanStack Query — fica só fetch nativo + SWR onde já existe."

**Agente:**

1. Tipo: decisão operacional (não muda PRD/SPEC).
2. Verifica `architecture.md` se TanStack está mencionada → sim, em §2 Stack.
3. Pause: avisa que isso é decisão operacional **e** afeta arquitetura. Pede confirmação:
   - "Adiciono linha em DECISIONS_LOG + atualizo `wiki/architecture.md`?"
4. Após OK:
   - DECISIONS_LOG: `- [2026-05-08] [deps] não adicionar nova feature usando TanStack Query — motivo: simplificação — impacto: SWR fica para casos com cache; fetch nativo padrão — ref: conversa de 2026-05-08`
   - `architecture.md`: troca linha sobre TanStack para "removido — usar SWR (legado) ou fetch nativo".
   - `wiki/log.md`: `- [2026-05-08 15:10] [INGEST] decisão sobre TanStack Query — DECISIONS_LOG L23 + architecture.md atualizado`

---

## Fluxo 3 — INGEST com conflito

**Usuário:** "ingest: o cliente confirmou que precisamos de RLS na tabela `users` antes da próxima onda."

**Agente:**

1. Lê `wiki/architecture.md` → diz que RLS está em `users` ✅.
2. Lê `docs/plans/CURRENT_REALITY.md §4 Banco real` → diz que RLS NÃO está em `users` ❌.
3. Conflito detectado.
4. **Pausa:** relata o conflito, mostra os 2 trechos, pergunta qual é a verdade.
5. Não grava nada até resolver.

---

## Fluxo 4 — CONTEXT pack para passar do Claude para Codex

**Usuário:** "/wiki context F-007 — quero terminar isso no Codex à tarde porque acabaram meus tokens"

**Agente:**

1. Lê F-007 no `TODO.md`. Feature Contract presente.
2. Lê `wiki/modules/auth.md`, `DECISIONS_LOG.md`, últimos eventos do `log.md`.
3. Cria `wiki/context/F-007-signup-confirmacao.md` com template preenchido:
   - Estado atual: `[x] Schema, [x] Teste falhando, [ ] Implementação, [ ] E-mail Resend`
   - Próximos passos: 4 itens executáveis
   - Handoff de "Claude Code (sessão 2026-05-08 manhã)" para "Codex"
   - "Última ação: criei branch + Zod + integration test falhando"
   - "O que NÃO fiz e o próximo deveria evitar: não toquei na tabela `users` — escopo proíbe"
4. Reporta caminho + resumo de 5 linhas que o usuário pode colar no Codex.

---

## Fluxo 5 — LINT antes de release

**Usuário:** "/wiki lint — vou subir para produção amanhã"

**Agente (não altera nada):**

```
WIKI LINT — 2026-05-08

SAÚDE: amarelo

ÓRFÃS: nenhuma
INALCANÇÁVEIS: wiki/modules/payments.md (citado em index, arquivo não existe)
CONTRADIÇÕES:
  - architecture.md §2 Stack diz "Resend"; CURRENT_REALITY.md §5 diz "SendGrid"
DECISÕES CONFLITANTES: nenhuma
RUNBOOKS FALTANDO:
  - BUG-002 (gravidade alta) sem runbook em wiki/runbooks/
FEATURES C/D SEM RESUMO:
  - F-005 (mergeada em PR #34, classe C) sem entrada em wiki/features/
LOG > 200 LINHAS: não (124 linhas)
CONTEXT PACKS ÓRFÃOS:
  - wiki/context/F-003-login.md (feature mergeada em PR #28)

RECOMENDAÇÃO: rodar `/wiki repair` antes de release. Contradição Resend/SendGrid exige humano (pode afetar deploy).
```

---

## Fluxo 6 — REPAIR após lint

**Usuário:** "/wiki repair"

**Agente:**

1. Para cada item:
   - **Inalcançável `payments.md`**: pergunta — criar página com template? (pause se módulo não existe no código).
   - **Contradição Resend/SendGrid**: NÃO altera; lista para humano. Adiciona TODO.
   - **Runbook faltante BUG-002**: pergunta detalhes ou abre stub.
   - **F-005 sem resumo**: gera resumo de 5 linhas em `wiki/features/F-005.md` a partir do PR #34.
   - **Context pack órfão F-003**: deleta após confirmar com usuário.
2. Cada operação registrada em `wiki/log.md` tipo `WIKI`.
3. Reporta lista do que foi feito + o que ficou pendente para humano.

---

## Quando o ingest deve virar ADR (não DECISIONS_LOG)

| Sinal | Vai para ADR | Vai para DECISIONS_LOG |
|---|---|---|
| Trade-off técnico real (custo, complexidade, vendor lock-in) | ✓ | |
| Mudança de stack (lib core, DB, host) | ✓ | |
| Decisão "não fazer X agora" sem impacto estrutural | | ✓ |
| "Mantemos comportamento legado por compatibilidade" | | ✓ |
| "Campo Y continua opcional" | | ✓ |
| Padrão arquitetural novo aplicado em N módulos | ✓ | |

Em dúvida: ADR sempre tem **alternativas consideradas + consequências**. Se você não sabe escrever isso, é DECISIONS_LOG.

---

*Estas referências evoluem com o uso real. Se um fluxo virou comum e não está aqui, adicione.*
