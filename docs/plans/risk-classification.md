# Risk Classification — Harness v3.2

> Toda feature é classificada A / B / C / D **antes** de começar. A classificação define o rigor do Feed Forward (Definition of Ready + Feature Contract) e do Feedback (CI por níveis, matriz de validação, dataset congelado/rollback).
>
> **Escopo:** referência curta usada por `/SDD-avancado`, `/agents-protocol`, pelos prompts 1–3 e pelo `AGENTS.md`. Projeto de **dados/quant que roda local**: não há deploy, servidor, banco real nem env de produção — o que existe de "produção" aqui é **publicar número para o Comitê**.

---

## Tabela mestre

| Classe | Exemplos | Feed Forward exigido | Feedback exigido |
|---|---|---|---|
| **A — Trivial** | typo, docstring, título/cor de figura sem mudar o número, entrada de catálogo que ninguém consome | Item no `TODO.md` com 1 CA | CI Nível 1 (`ruff check` + `ruff format --check` + `pytest tests/unit`) · `main` direto permitido |
| **B — Normal** | novo extrator de fonte, infra de extração, job de arquivamento, figura/tabela sobre número já validado | DoR completa + Feature Contract curto (bloco no TODO.md) + **fixture gravada** da fonte | CI Nível 1 + matriz CA→teste→evidência + evidência de dados (linhas, `min`/`max`, % de nulos, 3 valores conferidos na fonte) · branch `feat/*` ou `data/*` obrigatória |
| **C — Crítica** | schema do canônico, alinhamento temporal, cálculo de retorno/deflação, série derivada que alimenta regime, classificação de regime, métricas do heatmap, orquestrador | DoR + Feature Contract dedicado + Anti-SPEC revisada | CI Nível 2 (integration + contract tests sobre fixture, `pandera` em todo DataFrame) + **diff numérico** vs. o canônico anterior + reconstrução completa + **revisão numérica independente** |
| **D — Publicação/credencial** | enviar número ao Alexandre/Comitê, congelar e versionar o dataset entregue, usar credencial ou API paga, corrigir número já apresentado | DoR + Feature Contract + seção em `docs/plans/infra-ops.md` com **Rollback** | CI Nível 3 (e2e + duas execuções → mesmo hash) + **dataset congelado** (versão + hash) + revisão humana do número + smoke test do pacote |

---

## Como classificar (regras de desempate)

1. Se o resultado **sai para fora** (Alexandre, Comitê, print por WhatsApp) ou se usa **credencial/fonte paga** → **D**, não negociável.
2. Se toca a **camada canônica** — schema, alinhamento temporal, cálculo de retorno, definição ou classificação de regime → **C**.
3. Se cria/altera **contrato de dados** (schema `pandera`/`pydantic`, coluna, `series_id` do catálogo) ou liga uma série nova no pipeline → mínimo **B** (C se entra no canônico).
4. Se é mudança **isolada**, sem alterar nenhum valor de output → **A**.
5. Em dúvida entre duas classes, **escolha a mais alta**. Escalar é barato; número errado no Comitê é caro.

---

## Implicações operacionais

### Classe A
- Pode ir direto em `main` se o agente tem CI local verde e registro no TODO.
- Dispensa Feature Contract.
- Não precisa de matriz de validação formal — o teste unitário já é a evidência.
- **Vira B no instante em que qualquer valor de output muda** ou em que uma série passa a ser consumida.

### Classe B
- Branch `feat/<slug>` (ou `data/<slug>`) + PR.
- Feature Contract inline no item do `TODO.md` (ver template).
- Matriz de validação simples: cada CA tem 1 teste identificado.
- **Fixture gravada** da resposta real da fonte em `tests/fixtures/`; rede só sob `@pytest.mark.network`.
- Evidência de dados: nº de linhas, `min`/`max` de data, % de nulos por coluna crítica e **3 valores conferidos contra a fonte** (print/link).

### Classe C
- Idem B, mais:
  - Feature Contract dedicado (bloco detalhado no TODO ou arquivo em `docs/plans/feature-contracts/`).
  - Testes de integração/contrato obrigatórios sobre fixture, com `pandera` no DataFrame de entrada e de saída.
  - Anti-SPEC revisada especificamente para a feature (checagem explícita no Prompt 3).
  - **Reconstrução completa** de `data/canonical/` a partir de zero.
  - **Diff numérico** vs. a versão anterior do canônico, com **cada** divergência explicada.
  - **Revisão numérica independente** antes do merge: quem calculou **não** confere.

### Classe D
- Idem C, mais:
  - Seção própria em `docs/plans/infra-ops.md` com **Rollback** obrigatória — sem ela, não sai.
  - **Dataset congelado** antes do envio: hash por arquivo + hash agregado registrados, diretório nunca mais tocado.
  - Smoke test do pacote evidenciado (abre no Excel, contagem de linhas, nulos em coluna crítica, paridade Parquet × CSV/XLSX).
  - **Revisão humana do número** pelo Edu, com 3 valores conferidos por série.
  - Linha em `docs/wiki/log.md` + comunicação escrita das substituições de fonte (`docs/plans/DECISIONS_LOG.md`).
  - ADR se há trade-off arquitetural real.

---

## Quem classifica

- **Primeira passagem:** `/SDD-avancado` marca cada feature do TODO com a classe sugerida.
- **Revisão contínua:** o desenvolvedor ou o Claude Code no **Prompt 2** valida a classe antes de começar — se a feature cresceu ou a natureza mudou, reclassifique **antes** de implementar.
- **Escalada automática:** se durante a implementação uma feature B começa a tocar a **camada canônica** (schema, alinhamento, retorno, regime), o agente deve **pausar**, reclassificar para **C** e pedir Feature Contract expandido; se o resultado passa a sair para o Alexandre/Comitê ou a exigir credencial, vai para **D**.

---

## Gate de autonomia

O Claude Code pode **continuar automaticamente** em features A e B sem pedir confirmação a cada passo, desde que dentro do escopo do Feature Contract.

Para **C e D**, o agente **deve pausar** em marcos específicos:
- Antes de alterar schema do canônico, regra de alinhamento temporal ou cálculo de retorno (qualquer classe C).
- Antes de congelar o dataset ou gerar o pacote de entrega (qualquer classe D).
- Antes de usar credencial ou qualquer fonte paga.
- Antes de executar o rollback de uma versão já enviada, ou o smoke test manual do pacote.

Regras completas de autonomia em `AGENTS.md §9`.

---

## Testes mínimos por classe (Validation Mode Patch)

> **Fonte única.** `AGENTS.md`, templates, prompts e checklists apontam para esta seção. Em caso de divergência, prevalece esta.

### Classe A — Trivial
- Teste **opcional**, desde que a mudança seja realmente isolada e sem comportamento novo.
- `ruff check .` e `ruff format --check .` **obrigatórios** se houve código.
- **Se alterar qualquer valor de output → vira Classe B.**

### Classe B — Normal
- **≥1 teste por critério de aceite** (unit ou integration conforme natureza).
- `ruff` + `pytest tests/unit` obrigatórios.
- **Fixture gravada** da resposta real da fonte; nenhum teste de rede fora de `@pytest.mark.network`.
- **≥1 teste de caminho de erro**: HTTP 200 com corpo de erro, corpo vazio/0 bytes, encoding errado, HTML onde se esperava planilha.

### Classe C — Crítica
- **≥1 teste por CA crítico** (alinhamento, acumulação geométrica, deflação, limiar de regime).
- **≥1 teste de edge case** (feriado, fim de trimestre em fim de semana, série que começa depois de 2006, ausência de dado).
- **≥1 teste negativo** (`ffill` além do limite, look-ahead, excesso sobre CDI por subtração em vez de razão).
- **Integration/contract test obrigatório** sobre fixture quando toca fonte, schema `pandera` ou cálculo.
- **Diff numérico** vs. o canônico anterior + **reconstrução completa** de `data/canonical/` do zero.
- **Valor-canário** conhecido da fonte (ex.: CDI 2006 = 15,0271%) — não a fórmula reimplementada no teste.

### Classe D — Publicação / credencial
- **CI N3**: `pytest tests/e2e -m "not network"` + **duas execuções do zero com o mesmo hash**.
- **Smoke test obrigatório** do pacote (script ou manual evidenciado com log/print).
- **Dataset congelado**: hash por arquivo + hash agregado registrados antes do envio.
- **Rollback plan obrigatório** em `docs/plans/infra-ops.md`.
- **Validação de credencial** quando aplicável (onde vive, escopo, como revogar) — hoje: nenhuma autorizada.
- **Revisão humana do número** com 3 valores conferidos por série — automação não substitui.

---

## Teste fake não conta

> O Prompt 3 (QA em Validation Mode) rejeita estes padrões como "não coberto", mesmo que "passem":

**Sinais de teste fake:**

- `assert True` ou variantes tautológicas.
- Teste que só verifica que a função **roda sem exceção**, sem validar nenhum valor.
- Teste que declara um CA no nome mas **não exercita** a regra correspondente.
- Teste que mocka **justamente a regra que deveria validar** (ex.: mocka o normalizador de número pt-BR no teste que deveria provar a conversão de `"38.484,84"`).
- Assertion genérica (`assert df is not None`) em cima de valor que o código já garante.
- Teste que lê o próprio valor de retorno e o compara consigo mesmo.
- Checagem de tipo (`assert isinstance(x, str)`) sem validar conteúdo.
- Teste que roda mas cuja falha não invalida a feature (`try/except` silencioso em volta do `assert`).
- `@pytest.mark.skip`, `xfail` sem ADR, ou teste excluído por `-k` deixado no PR.

**Quando usar mocks:**

- Mock vale para dependências externas (HTTP, relógio, caminho temporário).
- Mock **não** vale para substituir a regra do sistema sob teste.
- Em classe B/C que toca fonte externa, use **fixture gravada** da resposta real — e, em C, o **dataset congelado** da versão anterior para o diff numérico — nunca dado sintético "plausível".

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

*Esta referência é espelhada em `.claude/harness-v3.2-manual.md §7`. Em caso de divergência, prevalece este arquivo.*
