# Checklist por Feature / PR — Harness v3.2 · Project Wiki + Fast Fix

> Validação rápida antes de mergear uma feature. Rigor por classe A/B/C/D.
> Para bug urgente A/B sem auth/payment/db: use `/fast-fix` (Project Quick) — checklist próprio dentro da skill.
> Complementa `skills/agents-protocol/references/delivery-checklist.md` — se divergirem, prevalece o do skill.

---

## Antes de começar a feature (Feed Forward)

- [ ] Li `wiki/index.md` + `wiki/context/<F-NNN>.md` se existir (handoff de sessão anterior).
- [ ] Li o item no `TODO.md` (RFs + CAs + dependências + Feature Contract inline).
- [ ] Confirmei a classe A/B/C/D. **Se a natureza pode subir durante a execução, marquei risco de reclassificação.**
- [ ] Validei a Definition of Ready. **Se incompleta em domínio sensível → BLOQUEADO — DEFINITION OF READY INCOMPLETA.**
- [ ] Feature Contract presente (inline ou `docs/plans/feature-contracts/`) para B/C/D.
- [ ] Li SPEC relevante + Anti-SPEC (§6).
- [ ] Consultei `DECISIONS_LOG.md` se há linha relacionada ao domínio.
- [ ] `packages/shared/types/` tem os tipos; se faltam, adicionei **antes**.
- [ ] Testes mínimos por classe identificados (ver `risk-classification.md`).
- [ ] Branch `feat/<slug>` criada (classe A pode ir em `main`).

---

## Durante a implementação

- [ ] Teste falhando escrito para cada CA **antes** do código.
- [ ] Só alterei arquivos listados em "podem ser alterados" do Feature Contract.
- [ ] **Se precisei sair da lista**, apresentei justificativa (7 itens) e atualizei o contrato; se toca produto/produção/banco/auth/pagamento/dados sensíveis, pausei.
- [ ] **Se a feature mudou de natureza (tocou auth, banco, env, fluxo principal), reclassifiquei antes de continuar** e atualizei Feature Contract + testes + CI alvo + matriz + TODO.
- [ ] Tipos vêm exclusivamente de `packages/shared/types/` — sem paralelos.
- [ ] Cruzei com a Anti-SPEC — nada proibido foi introduzido.
- [ ] Commits atômicos referenciando TODO (`feat(auth): login PKCE (TODO #3)`).
- [ ] Decisão operacional recorrente → linha em `DECISIONS_LOG.md`. Arquitetura → ADR. Produto → PAUSE + autorização humana.

---

## Antes de abrir PR / merge — por classe

### Classe A
- [ ] `npm run lint && npm run typecheck && npm test` (N1) verde.
- [ ] Teste cobre o CA (ou a mudança é verdadeiramente isolada — se alterou comportamento, virou B).

### Classe B (adicionais)
- [ ] Feature Contract preenchido + matriz de validação com status em todos os CAs.
- [ ] **Testes mínimos cumpridos: ≥1 teste por CA.**
- [ ] Nenhum teste fake (ver `risk-classification.md §Teste fake não conta`).
- [ ] `CONTRACTS.md` atualizado se contratos mudaram.
- [ ] Build verde (se o projeto tem).

### Classe C (adicionais)
- [ ] CI N2 local verde (integration + contract + build).
- [ ] **Testes mínimos cumpridos: ≥1 por CA crítico + ≥1 edge case + ≥1 negativo.**
- [ ] Integration test presente se envolve API/auth/regra de negócio/dados.
- [ ] E2E presente se toca fluxo principal.
- [ ] Anti-SPEC verificada explicitamente no Prompt 3 (lista específica marcada).
- [ ] **Validation Mode** exercitado — tentei quebrar a feature (inputs inválidos, permissões, idempotência, edge cases).
- [ ] Revisão humana antes do merge (recomendada).
- [ ] ADR criado se houve decisão arquitetural / dependência nova.

### Classe D (adicionais)
- [ ] CI N3 verde (e2e + smoke + migration validation).
- [ ] `docs/plans/cursor-brief.md` com seção **Rollback** preenchida.
- [ ] Staging validado — log/print anexado ao PR.
- [ ] Feature flag configurada se altera contrato público.
- [ ] Smoke test pós-deploy planejado/executado.
- [ ] Backup plan descrito se migration é destrutiva.
- [ ] Env vars listadas e confirmadas presentes.
- [ ] E2E automatizado **ou** teste manual com passos escritos + print/log.

---

## No PR

- [ ] Título: `feat(<escopo>): <resumo curto>`.
- [ ] Corpo segue `skills/agents-protocol/assets/pr-description-template.md`.
- [ ] Ligação com TODO.md explícita.
- [ ] Matriz de validação anexada (B/C/D) com seção Validation Mode preenchida (C/D).
- [ ] CI do GitHub Actions verde no nível correspondente (N1/N2/N3).
- [ ] **Prompt 3 (Validation Mode)** executado → APROVADO com evidência, MUDANÇAS_SOLICITADAS com issues, ou BLOQUEADO com causa clara.

---

## Após merge (UPDATE MEMORY — v3.2)

- [ ] `TODO.md`: item → "Concluído" com SHA/PR.
- [ ] Branch deletada (local + remoto).
- [ ] Fechou onda? Marcar no `PLAN.md`.
- [ ] Ideias/bugs surgidos registrados no `TODO.md`.
- [ ] Classe D: smoke pós-deploy em produção confirmado.
- [ ] Se surgiu decisão operacional digna de memória: linha adicionada em `DECISIONS_LOG.md`.
- [ ] **Wiki:** linha em `wiki/log.md` tipo `[RELEASE]` ou `[BUGFIX]`.
- [ ] **Wiki (C/D):** resumo de ≤ 5 linhas em `wiki/features/F-NNN.md`.
- [ ] **Wiki:** se a feature alterou módulo significativamente, atualizar `wiki/modules/<mod>.md`.
- [ ] **Wiki:** deletar `wiki/context/F-NNN.md` se existia (Context Pack consumido).

---

## Sinais de alerta — pare e repense

- PR com > 800 linhas → quebre.
- Teste cobre > 1 CA → fragmente.
- Precisou editar `PRD.md`/`SPEC.md`/Anti-SPEC → pare, confirme com humano.
- CI vermelho e pensou em `.skip` → não. Arrume.
- Feature cresceu → volte ao TODO, reclassifique, talvez divida.
- Classe B começou a tocar banco/auth/env → reclassifique C ou D antes de continuar (**regra: suba, nunca desça**).
- Classe D sem Rollback → BLOQUEADO.
- Aprovar sem matriz em B/C/D → proibido.
- Aprovar sem rodar Validation Mode em C/D → MUDANÇAS_SOLICITADAS.
- Teste que só verifica render, `expect(true)`, ou mocka a regra sob validação → teste fake não conta, reavalie.
- `DECISIONS_LOG` virando diário → pode.
