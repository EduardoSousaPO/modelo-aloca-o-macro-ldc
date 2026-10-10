# Risk Classification — Harness v3.1

> Toda feature é classificada A / B / C / D **antes** de começar. A classificação define o rigor do Feed Forward (Definition of Ready + Feature Contract) e do Feedback (CI por níveis, matriz de validação, staging/rollback).
>
> **Escopo:** referência curta usada por `/SDD-avancado`, `/agents-protocol`, pelos prompts 1–3 e pelo `AGENTS.md`.

---

## Tabela mestre

| Classe | Exemplos | Feed Forward exigido | Feedback exigido |
|---|---|---|---|
| **A — Trivial** | typo, ajuste de cópia, layout pequeno, mudança isolada sem contrato | Item no `TODO.md` com 1 CA | CI Nível 1 (lint+typecheck+test) · `main` direto permitido |
| **B — Normal** | nova tela, CRUD simples, ajuste de fluxo, endpoint não crítico | DoR completa + Feature Contract curto (bloco no TODO.md) | CI Nível 1 + matriz CA→teste→evidência · branch `feat/*` obrigatória |
| **C — Crítica** | auth, autorização, pagamento, billing, permissões, dados sensíveis, webhooks, regra de negócio central | DoR + Feature Contract dedicado + Anti-SPEC revisada | CI Nível 2 (integration + contract tests) + matriz + revisão humana sugerida |
| **D — Produção/Infra** | migration, RLS, deploy, env var, Stripe/MP, alteração em banco real, rollout público | DoR + Feature Contract + cursor-brief + plano de rollback + feature flag se muda contrato público | CI Nível 3 (E2E/smoke/migration validation) + staging obrigatório + smoke test pós-deploy |

---

## Como classificar (regras de desempate)

1. Se toca **produção, banco real ou env vars reais** → **D**, não negociável.
2. Se envolve **auth, dinheiro, permissões ou dados sensíveis** → **C**.
3. Se cria/altera **contrato público** (rota, schema, evento) → mínimo **B** (C se crítico).
4. Se é **código isolado** sem contrato, sem efeito visível em produção → **A**.
5. Em dúvida entre duas classes, **escolha a mais alta**. Escalar é barato; rebaixar depois de um incidente é caro.

---

## Implicações operacionais

### Classe A
- Pode ir direto em `main` se o agente tem CI local verde e registro no TODO.
- Dispensa Feature Contract.
- Não precisa de matriz de validação formal — o teste unitário já é a evidência.

### Classe B
- Branch `feat/<slug>` + PR.
- Feature Contract inline no item do `TODO.md` (ver template).
- Matriz de validação simples: cada CA tem 1 teste identificado.

### Classe C
- Idem B, mais:
  - Feature Contract dedicado (bloco detalhado no TODO ou arquivo em `docs/plans/feature-contracts/`).
  - Testes de integração obrigatórios.
  - Anti-SPEC revisada especificamente para a feature (checagem explícita no Prompt 3).
  - Revisão humana sugerida antes do merge (não só autorrevisão do Claude).

### Classe D
- Idem C, mais:
  - `cursor-brief.md` com seção **Rollback** obrigatória.
  - Staging antes de produção — sem exceção.
  - Smoke test automatizado ou script manual descrito no brief.
  - Feature flag se altera contrato público ou rollout gradual.
  - **Backup/restore plan** se a migration for destrutiva (DROP, ALTER TYPE incompatível, etc).
  - ADR se há trade-off arquitetural real.

---

## Quem classifica

- **Primeira passagem:** `/SDD-avancado` marca cada feature do TODO com a classe sugerida.
- **Revisão contínua:** o desenvolvedor ou o Claude Code no **Prompt 2** valida a classe antes de começar — se a feature cresceu ou a natureza mudou, reclassifique **antes** de implementar.
- **Escalada automática:** se durante a implementação uma feature B começa a tocar produção/banco/RLS, o agente deve **pausar**, reclassificar para D e pedir Feature Contract expandido.

---

## Gate de autonomia

O Claude Code pode **continuar automaticamente** em features A e B sem pedir confirmação a cada passo, desde que dentro do escopo do Feature Contract.

Para **C e D**, o agente **deve pausar** em marcos específicos:
- Antes de tocar migration/RLS/env (qualquer classe D).
- Antes de alterar rota/endpoint legado sem paridade de teste.
- Antes de ativar feature flag em produção.
- Antes de executar rollback ou smoke test manual.

Regras completas de autonomia em `AGENTS.md §9`.

---

## Testes mínimos por classe (Validation Mode Patch)

> **Fonte única.** `AGENTS.md`, templates, prompts e checklists apontam para esta seção. Em caso de divergência, prevalece esta.

### Classe A — Trivial
- Teste **opcional**, desde que a mudança seja realmente isolada e sem comportamento novo.
- `lint` e `typecheck` **obrigatórios** se houve código.
- **Se alterar comportamento observável → vira Classe B.**

### Classe B — Normal
- **≥1 teste por critério de aceite** (unit ou integration conforme natureza).
- `lint + typecheck + test` obrigatórios.
- `build` obrigatório se o projeto tem script de build.

### Classe C — Crítica
- **≥1 teste por CA crítico** (auth, permissões, valores).
- **≥1 teste de edge case** (input inválido, ausência de dados, estado vazio/erro).
- **≥1 teste negativo** (permissão errada, token expirado, idempotência quebrada, etc.).
- **Integration test obrigatório** quando envolve API, auth, regra de negócio ou dados.
- **E2E obrigatório** se a feature toca o fluxo principal do usuário.
- `build` obrigatório.

### Classe D — Produção / Infra
- **Integration test** quando aplicável (ex.: validar migration com seed → query).
- **Smoke test obrigatório** (script ou manual evidenciado com log).
- **Validação em staging obrigatória** antes de produção — com print/log anexado.
- **Rollback plan obrigatório** no `cursor-brief.md`.
- **Migration validation** quando tocar banco (dry-run, diff de schema).
- **Validação de env/secrets** quando aplicável (listar variáveis, confirmar presença).
- **E2E automatizado ou teste manual evidenciado** se a automação ainda não existir — manual só vale com passos escritos + print/log.

---

## Teste fake não conta

> O Prompt 3 (QA em Validation Mode) rejeita estes padrões como "não coberto", mesmo que "passem":

**Sinais de teste fake:**

- `expect(true).toBe(true)` ou variantes tautológicas.
- Teste que só verifica que um componente **renderiza** sem validar comportamento (clique, input, output).
- Teste que declara um CA no nome mas **não exercita** a regra correspondente.
- Teste que mocka **justamente a regra que deveria validar** (ex.: mocka o `bcrypt.compare` para retornar `true` num teste de login com senha errada).
- Teste com assertion genérica (`expect(result).toBeDefined()`) em cima de valor que o código garante estaticamente.
- Teste que lê o próprio valor de retorno e o compara consigo mesmo.
- Teste condicional de tipo (`expect(typeof x).toBe('string')`) sem validar conteúdo.
- Teste que roda mas cuja falha não invalida a feature (ex.: `try/catch` silencioso em volta do assertion).
- Teste com `.only` ou `.skip` deixado no PR.

**Quando usar mocks:**

- Mock vale para dependências externas (HTTP, clock, UUID determinístico).
- Mock **não** vale para substituir a regra do sistema sob teste.
- Em classe C/D que toca dados, prefira container real (Postgres local via Testcontainers, Supabase local) em vez de mock do banco.

---

*Esta referência é espelhada em `harness-v3-manual.md §7`. Em caso de divergência, prevalece este arquivo.*
