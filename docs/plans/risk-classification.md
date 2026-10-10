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

## Exemplos concretos **deste projeto** (estrategia-macro-ldc-dados)

> Adicionado em 2026-10-10 por `/SDD-avancado`. A tabela mestre acima é genérica (SaaS/web); aqui ela é
> traduzida para um projeto de **dados/quant que roda local**. Direção vinda de `AGENTS.md §2`.
>
> **O risco dominante aqui não é "derrubar o site": é entregar número errado ao Comitê.** O modo de
> falha é **silencioso** — um trimestre desalinhado, um retorno acumulado errado, um IPCA aplicado duas
> vezes passam sem levantar exceção e contaminam todo o modelo a jusante. Por isso a classe **C** é
> deliberadamente ampla: tudo que toca a camada canônica é C, mesmo que pareça pequeno.

### Classe A — Trivial (neste projeto)

- Ajuste de texto em `README.md`, `docs/wiki/*` ou docstring.
- Renomear célula de notebook, reordenar import, corrigir typo de legenda.
- Melhorar título/cor de uma figura **sem mudar o número** nem a métrica plotada.
- Criar `docs/plans/DECISIONS_LOG.md` a partir do template e registrar substituição já decidida (F-032).
- Acrescentar entrada `status: a_confirmar` ou `descartada` ao catálogo **sem** nenhum extrator passar a
  usá-la.

**Vira B na hora em que:** o valor de qualquer output muda, ou uma série passa a ser consumida.

### Classe B — Normal (neste projeto)

- **Novo extrator de fonte** (SGS, SIDRA, ANBIMA S3, API B3, Tesouro, Yahoo/MSCI, Focus, Teva, FRED):
  F-002 a F-012.
- Infra de extração: cliente HTTP com UA, retry, validação de shape, normalizador de número pt-BR,
  cache por `ETag` (F-001, F-030).
- Job diário de arquivamento idempotente (F-009).
- **Agregação mensal → trimestral de uma série nova** que ainda não entrou no canônico.
- Figura/tabela nova construída **sobre** números já validados (heatmap F-023, ranking F-024,
  timeline F-025, página de limitações F-028, notebook F-027).
- Teste de contrato com valor-canário (F-030).

**Validação extra obrigatória (B):** amostra conferida contra a fonte — nº de linhas, `min`/`max` de data,
% de nulos por coluna crítica e **3 valores conferidos** com print/link.

### Classe C — Crítica (neste projeto) — **a classe mais larga**

Qualquer uma destas, isoladamente, já é C:

- **Schema do dataset canônico** (`raw_series`, `macro_quarterly`, `asset_returns_quarterly`, `regimes`,
  `regime_neighbors`, `series_catalog` materializado) — F-013, F-015.
- **Regras de alinhamento temporal**: calendário de dias úteis, fim de trimestre, lag de divulgação,
  limite de forward-fill — F-014.
- **Cálculo de retorno**: acumulação geométrica, excesso sobre CDI, deflação por IPCA, anualização,
  conversão a BRL — F-017.
- **Construção de série derivada que alimenta regime**: interpolação de vértices e inclinação da curva —
  F-016.
- **Definição ou classificação de regime macro** (V1, V2, V3) e a janela de 20 anos — F-019, F-020, F-021.
- **Métricas por regime × ativo** que vão ao heatmap — F-022.
- **Regra anti-look-ahead** e as materializações `asof`/`revised` — F-018.
- **Bloco internacional** (retornos por regime, `stress_flag`, faixa de alocação) — F-026.
- **Orquestrador do pipeline** e a garantia de idempotência/hash — F-029.

**Validação extra obrigatória (C), além do CI N2:**
1. **Reconstrução completa** de `data/canonical/` a partir de zero.
2. **Diff numérico** vs. a versão anterior do canônico, com **cada** divergência explicada (não basta
   "mudou porque melhorou").
3. **Revisão numérica independente** — quem calculou **não** confere.
4. Checagem explícita da **Anti-SPEC** (`SPEC.md §10`), item por item, no QA.
5. ADR se houve trade-off arquitetural; `DECISIONS_LOG` se houve troca de fonte.

### Classe D — Publicação / credencial (neste projeto)

- **Enviar qualquer número ao Alexandre ou ao Comitê** (relatório, planilha, figura, mensagem com
  número) — F-031.
- Usar **credencial ou API paga** (ANBIMA Feed, Bloomberg, Comdinheiro, MacroMicro, Cbonds) — hoje nada
  no caminho crítico depende disso; se L4 virar "contratar o Feed", **F-016 sobe de C para D**.
- **Alterar número já apresentado** ao Comitê (correção pós-envio).
- Congelar/versionar o dataset entregue.

**Validação extra obrigatória (D), além do CI N3:** revisão humana do número pelo Edu com 3 valores
conferidos por série · dataset **congelado** (versão + hash) · linha em `docs/wiki/log.md` ·
**Rollback** escrito em `docs/plans/infra-ops.md` · comunicação escrita das substituições de fonte ·
nenhum segredo no repositório.

> **Não existe "A/B" para publicação.** Mandar um print de heatmap por WhatsApp para o Alexandre é
> classe D tanto quanto enviar o pacote completo.

### Gatilhos de reclassificação observados neste projeto

| De → Para | Gatilho concreto |
|---|---|
| A → B | a mudança passa a alterar valor de output ou liga uma série nova no pipeline |
| B → C | o extrator começa a **agregar para trimestral dentro do canônico**, a mexer no calendário, a calcular retorno, deflacionar, ou a virar feature de regime |
| B → C | "só um ajustinho" no `ffill`, no limiar de ΔSelic, no `k` da V3 ou na média móvel de 20 trimestres |
| C → D | o resultado vai para o Alexandre/Comitê, ou passa a exigir credencial/fonte paga |
| qualquer → D | alguém pede "me manda só esse número do heatmap" |

### "Teste fake" na versão dados — padrões que o QA rejeita aqui

Além dos padrões genéricos listados acima:

- Teste que afirma `len(df) > 0` sem checar **contagem mínima esperada** (não pega truncamento
  silencioso: 20.000 linhas do Olinda, `range=max` do Yahoo, `fredgraph.csv` sem `cosd`).
- Teste que mocka a **resposta da fonte com dado sintético plausível** e não usa a fixture gravada.
- Teste de extrator que não exercita o **caminho de erro com HTTP 200** (corpo de erro do SGS).
- Teste de retorno que compara o resultado com **a própria fórmula reimplementada no teste** (tautologia)
  em vez de um valor conhecido da fonte (ex.: CDI 2006 = 15,0271%).
- Teste de alinhamento que usa só trimestres "fáceis" e nenhum caso-armadilha (feriado, 31/12 em fim de
  semana, série que começa depois de 2006).
- Teste de schema que valida um DataFrame **construído no próprio teste** com as colunas certas, sem
  nunca passar o output real do pipeline.
- Comparação de float com `==` onde a tolerância importa — ou, pior, tolerância tão larga
  (`abs < 0.1`) que qualquer erro de escala passa.
- Marcar com `@pytest.mark.network` um teste que **deveria** rodar sobre fixture, só para ele não rodar
  no CI.

---

*Esta referência é espelhada em `harness-v3-manual.md §7`. Em caso de divergência, prevalece este arquivo.*
