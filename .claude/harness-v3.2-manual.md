# Harness v3.2 — Manual Operacional Único (Project Wiki + Fast Fix)

> **Documento único do Harness v3.2.** Tudo que você precisa para operar o Harness nos seus projetos está aqui. Comece pelo Quick Start (§0). Use o resto como referência por seção quando precisar.

**Versão:** 3.2 — Project Wiki + Fast Fix + MVP Lite + Triage
**Escopo:** desenvolvedor solo, um agente gerador (Claude Code), Codex e Cursor opcionais para continuidade ou infra/MCP, CI como avaliador independente.
**Tempo de leitura:** 5 min para o Quick Start (§0). 25-35 min para o manual inteiro.

---

## Índice

0. [**Quick Start — qual cenário sou eu?**](#0-quick-start--qual-cenário-sou-eu) ← **comece aqui**
1. [O que é Harness v3.2 em 60 segundos](#1-o-que-é-harness-v32-em-60-segundos)
2. [Princípios não-negociáveis](#2-princípios-não-negociáveis)
3. [Feed Forward, Feedback e Memória](#3-feed-forward-feedback-e-memória)
4. [Estrutura padrão do projeto](#4-estrutura-padrão-do-projeto)
5. [As 8 skills](#5-as-8-skills)
6. [Os 4 prompts do dia a dia](#6-os-4-prompts-do-dia-a-dia)
7. [Classificação de risco A/B/C/D](#7-classificação-de-risco-abcd)
8. [Definition of Ready](#8-definition-of-ready)
9. [Feature Contract](#9-feature-contract)
10. [Matriz de Validação](#10-matriz-de-validação)
11. [CI por níveis](#11-ci-por-níveis)
12. [Project Wiki — memória sintetizada viva](#12-project-wiki--memória-sintetizada-viva)
13. [Fast Fix — Project Quick para bug urgente](#13-fast-fix--project-quick-para-bug-urgente)
14. [Modos de rigor (incluindo MVP Lite)](#14-modos-de-rigor)
15. [Cenário A — Projeto novo](#15-cenário-a--projeto-novo)
16. [Cenário B — Projeto já iniciado](#16-cenário-b--projeto-já-iniciado)
17. [Cenário C — Projeto em produção](#17-cenário-c--projeto-em-produção)
18. [Cenário D — Projeto bagunçado](#18-cenário-d--projeto-bagunçado)
19. [Cenário E — Migração v2 / v3.1 → v3.2](#19-cenário-e--migração-v2--v31--v32)
20. [Cenário F — Bug urgente / Project Quick](#20-cenário-f--bug-urgente--project-quick)
21. [Cenário G — Triagem de bugs em lote](#21-cenário-g--triagem-de-bugs-em-lote)
22. [Cenário H — MVP / validação de ideia](#22-cenário-h--mvp--validação-de-ideia)
23. [Continuidade entre agentes (Claude ↔ Codex ↔ Cursor)](#23-continuidade-entre-agentes-claude--codex--cursor)
24. [Operação diária](#24-operação-diária)
25. [Checklist por feature / PR](#25-checklist-por-feature--pr)
26. [Antipadrões](#26-antipadrões)
27. [Quando NÃO usar o Harness](#27-quando-não-usar-o-harness)
28. [Referência rápida](#28-referência-rápida)
29. [Anexos — mapa do pacote](#29-anexos--mapa-do-pacote)

---

## 0. Quick Start — qual cenário sou eu?

> **Tabela de decisão de 30 segundos.** Encontre sua linha, dispare o comando.

| Sou... | Faço isso |
|---|---|
| **Começando projeto novo do zero** | `/project-kickoff` → `/consultor-prd` → `/SDD-avancado` → `/agents-protocol` → loop |
| **Tenho ideia para validar em < 1 semana, sem produção** | modo **MVP Lite** (§22). Só `TODO.md` + classe + commit + 1 teste no caminho crítico. Pule kickoff completo. |
| **Entrando em projeto já iniciado, sem docs do Harness** | Cenário B (§16) — gere `CURRENT_REALITY.md` antes de `/consultor-prd` retroativo |
| **Trabalhando em projeto em produção** | Cenário C (§17). Toda feature que toca prod = classe D (rollback + staging + smoke). Bug em prod sem domínios sensíveis: `/fast-fix`. |
| **Projeto bagunçado, código duplicado, sem padrão** | Cenário D (§18) — `/wiki lint` → CURRENT_REALITY → 0 código antes do diagnóstico |
| **Bug urgente, cliente travado, < 30 min** | `/fast-fix` (Prompt 0). Gates duros saem do modo se for C/D. |
| **Cliente mandou 5 bugs, preciso priorizar** | `/triage-bugs` (lista colada) — devolve plano de ataque em < 5 min |
| **Vou desenvolver feature normal (CRUD, endpoint, tela)** | Prompt 1 (início) → Prompt 2 (classe B/C com Feature Contract) → Prompt 3 (QA Validation Mode) |
| **Acabaram tokens / vou continuar em Codex ou Cursor** | `/wiki context F-NNN` antes de fechar. Próximo agente lê `wiki/index.md` + `wiki/context/F-NNN.md` |
| **Vou subir migration / mudar env / deploy real** | Classe D obrigatória. `/agents-protocol` Prompt 2 com cursor-brief + rollback + staging + smoke. |
| **Decisão técnica grande aparecendo** | ADR em `docs/decisions/adr/` |
| **Decisão pequena que provavelmente volta ao debate** | linha em `docs/plans/DECISIONS_LOG.md` |

### Se você só tem 5 minutos hoje, leia isto

1. Existem **8 skills** — não precisa decorar. Você dispara pela frase ("/fast-fix", "/triage-bugs", etc) e o agente faz o resto.
2. Existem **4 prompts** — Fast Fix (0), Início (1), Implementar (2), QA (3). Tudo em `skills/agents-protocol/references/prompts-cheatsheet.md`.
3. **Toda feature B/C/D tem classe**: A trivial, B normal, C crítico (auth/payment), D produção. Em dúvida, suba.
4. **Wiki é memória viva** mantida pela IA. Você não escreve à mão. `/wiki ingest` recebe print/log/decisão; `/wiki lint` audita; `/wiki repair` corrige.
5. Se o agente disser **BLOQUEADO**, ele está te protegendo. Resolva a causa, não contorne.

Pronto. Resto do manual é referência.

---

## 1. O que é Harness v3.2 em 60 segundos

**Harness v3.2 = Harness v3.1 + Project Wiki + Fast Fix.** A mesma leveza para dev solo (1 agente gerador, CI como avaliador, TODO.md + git como estado), agora com **memória sintetizada viva** entre fontes brutas e agentes, e **modo Project Quick** para bug urgente.

**Project Wiki** (camada 1 do v3.2):
1. **`docs/wiki/`** — diretório de Markdown mantido pela IA via `/wiki ingest|context|lint|repair`.
2. **`wiki/index.md`** — primeira leitura de qualquer agente.
3. **`wiki/log.md`** — histórico cronológico vivo (ingests, releases, bugfixes, validações).
4. **`wiki/overview.md`** + **`wiki/architecture.md`** — síntese do PRD/SPEC em formato escaneável.
5. **`wiki/modules/`**, **`wiki/features/`**, **`wiki/runbooks/`**, **`wiki/context/`** — memória por área, por feature, runbooks operacionais, e Context Packs descartáveis para handoff entre agentes.

> A wiki é **memória sintetizada**, NUNCA fonte de verdade. PRD/SPEC/CONTRACTS/ADR continuam autoritativos.

**Fast Fix** (camada 2 do v3.2):
6. **`/fast-fix`** — skill dedicada com Prompt 0 embutido. Bug urgente classe A/B sem auth/payment/db/env/deploy, < 30 min. Gates objetivos. Sai do modo automaticamente se escala para C/D.

Tudo o mais do v3.1 permanece: 1 agente gerador (Claude Code), Cursor Agent opcional só para infra/MCP (classe D), sem `state/`, sem `handoffs/`, sem `progress.jsonl`, sem `AGENT-BRIEFS/`, feature como unidade de trabalho, contratos em Zod, Anti-SPEC sagrada, classificação A/B/C/D, DoR, Feature Contract, Validation Mode, três estados (CONTINUE/PAUSE/BLOQUEADO).

---

## 2. Princípios não-negociáveis

1. **Desenvolvedor solo.** Um agente gerador principal: Claude Code.
2. **Cursor Agent / Codex opcionais.** Cursor para infra/MCP (classe D); Codex para continuidade quando Claude esgota tokens.
3. **CI é o avaliador independente.** Gerador ≠ avaliador.
4. **Estado em `TODO.md` + `git log`.** Sem `state/`, sem `progress.jsonl`, sem `handoffs/`, sem `AGENT-BRIEFS/`, sem JSON paralelo.
5. **Feature é a unidade.** Nunca task atômica.
6. **Contrato é código.** Zod em `packages/shared/types/` é fonte; `CONTRACTS.md` é espelho.
7. **Anti-SPEC é sagrada.** Não alterável por agente sem autorização humana.
8. **CI verde é condição de merge.** Sem exceção.
9. **Produção exige staging, rollback e smoke test.** Classe D, não negociável.
10. **Wiki é memória sintetizada, NUNCA fonte de verdade.** (v3.2)
11. **Fast Fix é exceção justificada, não norma.** (v3.2)
12. **Toda feature B/C/D termina com 1 linha em `wiki/log.md`.** (v3.2)
13. **Sem burocracia desnecessária.** Quando em dúvida, corte.

---

## 3. Feed Forward, Feedback e Memória

| Feed Forward (antes da execução) | Feedback (após a execução) | Memória (v3.2) |
|---|---|---|
| `docs/wiki/index.md` | lint | `docs/wiki/log.md` |
| `docs/wiki/context/<F-NNN>.md` | typecheck | `docs/wiki/runbooks/<slug>.md` |
| PRD | unit tests | `docs/wiki/features/<F-NNN>.md` (após merge) |
| SPEC + Anti-SPEC | integration tests | `docs/wiki/modules/<mod>.md` |
| AGENTS.md | contract tests | `docs/wiki/overview.md` |
| CLAUDE.md | e2e tests | `docs/wiki/architecture.md` |
| TODO.md | build | `docs/plans/DECISIONS_LOG.md` |
| contratos Zod | smoke tests | ADRs (`docs/decisions/adr/`) |
| critérios de aceite | CI por níveis N1/N2/N3 | |
| Definition of Ready | Matriz de Validação | |
| Feature Contract | Validation Mode (B/C/D) | |
| Classificação A/B/C/D | Checagem de arquivos vs permitidos | |
| CURRENT_REALITY.md | Anti-SPEC explícita | |
| `wiki/log.md` recente | Validação de staging/rollback/smoke (D) | |

**Quanto melhor o Feed Forward**, mais previsível o output.
**Quanto melhor o Feedback**, menor o risco de degradação acumulada.
**Quanto melhor a Memória** (v3.2), menos retrabalho em sessões futuras e melhor continuidade entre agentes.

---

## 4. Estrutura padrão do projeto

```
projeto/
├── AGENTS.md                         contrato com agentes (≤360 linhas, v3.2)
├── CLAUDE.md                         ajustes específicos do Claude Code (≤140 linhas, v3.2)
├── TODO.md                           estado vivo + Feature Contract inline (B/C/D)
├── README.md
├── docs/
│   ├── product/PRD.md                o quê e por quê
│   ├── specs/SPEC.md                 RFs + CAs + Anti-SPEC (§6 sagrada)
│   ├── contracts/CONTRACTS.md        espelho legível de packages/shared/types/
│   ├── plans/
│   │   ├── PLAN.md                                ondas (opcional)
│   │   ├── CURRENT_REALITY.md                     estado real (projetos existentes)
│   │   ├── DECISIONS_LOG.md                       decisões operacionais (volta ao debate)
│   │   ├── risk-classification.md                 A/B/C/D
│   │   ├── FEATURE-CONTRACT-template.md           template local
│   │   ├── VALIDATION-MATRIX-template.md          template local
│   │   ├── skills-manifest.md                     output do /skill-scout (opcional)
│   │   ├── cursor-brief.md                        brief de infra MCP (opcional)
│   │   └── feature-contracts/F-NNN.md             contratos extensos (C/D)
│   ├── wiki/                         PROJECT WIKI (v3.2 — memória sintetizada viva)
│   │   ├── index.md                  mapa principal (lido primeiro por todo agente)
│   │   ├── log.md                    histórico cronológico (≤ 200 linhas)
│   │   ├── overview.md               projeto em 1 página
│   │   ├── architecture.md           arquitetura técnica viva
│   │   ├── modules/                  1 página por módulo (auth, db, payments, ...)
│   │   ├── features/                 resumo curto após merge (C/D)
│   │   ├── runbooks/                 deploy, rollback, smoke, bug recorrente
│   │   └── context/                  Context Packs por tarefa (descartáveis)
│   └── decisions/adr/                1 arquivo por decisão arquitetural
├── apps/                             código das aplicações
├── packages/shared/types/            FONTE DE VERDADE dos contratos (Zod/TS)
├── tests/unit|integration|contract|e2e/
├── infra/                            migrations, configs de deploy
└── .github/workflows/ci.yml          N1 ativo + N2/N3 comentados
```

**Pastas que NUNCA existem:** `state/`, `handoffs/`, `AGENT-BRIEFS/`, `progress.jsonl`, `scripts/` genérico na raiz.

---

## 5. As 8 skills

Ordem canônica em projeto novo: **1 → 2 → 3 → (4 opcional) → 5 → loop com 6/7/8 conforme cenário**.

### 5.1. `/project-kickoff`
Cria estrutura padrão. Em v3.2, copia também `docs/wiki/` populada com `index.md`, `log.md`, `overview.md`, `architecture.md` + diretórios `modules/`, `features/`, `runbooks/`, `context/`.

### 5.2. `/consultor-prd`
16 etapas de discovery → `docs/product/PRD.md`. Em modo retroativo, lê `CURRENT_REALITY.md` primeiro.

### 5.3. `/SDD-avancado`
Com PRD aprovado, gera `SPEC.md` (Anti-SPEC sagrada) + `CONTRACTS.md` (espelho) + schemas Zod + `TODO.md` com features classificadas A/B/C/D, DoR embutida e Feature Contract inline para B/C/D.

### 5.4. `/skill-scout` (opcional)
Gate de 3 níveis (nativo/MCP → skill existente → criar skill) + análise de risco operacional → `docs/plans/skills-manifest.md`.

### 5.5. `/agents-protocol`
Atualiza `AGENTS.md` com papéis + classificação + autonomia. Gera `cursor-brief.md` com Rollback obrigatório quando há classe D.

### 5.6. `/wiki` (NOVO v3.2)
Mantém a Project Wiki. Modos: `ingest` (processa fonte bruta), `context` (cria Context Pack), `lint` (audita), `repair` (corrige). Detalhes em §12.

### 5.7. `/fast-fix` (NOVO v3.2)
Modo Project Quick para bug urgente classe A/B sem auth/payment/db, < 30 min. Detalhes em §13.

### 5.8. `/triage-bugs` (NOVO v3.2)
Triagem em lote de bugs (cliente, suporte, equipe). Recebe lista colada, devolve em < 5 min: classificação por bug + modo recomendado + prioridade + plano do dia + atualização estruturada do `TODO.md §5`. **Nunca executa fix automaticamente** — humano confirma o plano. Detalhes em §21.

---

## 6. Os 4 prompts do dia a dia

> Versão canônica em `skills/agents-protocol/references/prompts-cheatsheet.md`.

### Prompt 0 — Fast Fix (NOVO v3.2)
Bug urgente classe A/B. Lê `wiki/runbooks/` e `wiki/log.md` primeiro. Gates duros: auth/payment/db/env/deploy → SAIR. Diff > 50 linhas → SAIR. Tempo > 30 min → SAIR. Termina com 1 linha em `wiki/log.md` e runbook se bug capaz de voltar.

### Prompt 1 — Início de sessão
Lê `wiki/index.md` + `wiki/context/<atual>.md` + `TODO.md` + `AGENTS.md` + Feature Contract + `wiki/log.md` recente + `git status`. Reporta fase, classe, DoR, Feature Contract presente, wiki health, autonomia.

### Prompt 2 — Implementar feature
Valida DoR → reclassifica se necessário → cria Feature Contract para B/C/D → atualiza Zod primeiro → branch → teste falhando → implementação → CI no nível da classe → matriz de validação → docs → PR ou merge → atualiza TODO. **Pós-merge (v3.2):** linha em `wiki/log.md`, resumo em `wiki/features/` (C/D), atualização de `wiki/modules/` se aplicável, deleção do Context Pack consumido.

### Prompt 3 — QA do PR (Validation Mode)
Lê Feature Contract → `git diff` → arquivos alterados vs permitidos → contratos → Anti-SPEC → matriz CA→teste→tipo→**status**→**evidência** → tenta quebrar (Validation Mode) → CI → produção (D). Retorna **APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO**. Nunca APROVADO sem evidência.

---

## 7. Classificação de risco A/B/C/D

| Classe | Exemplos | Feed Forward | CI alvo | Feedback extra | Modo recomendado |
|---|---|---|---|---|---|
| **A** | typo, layout, ajuste sem contrato | item simples no TODO | N1 | merge direto em `main` permitido | Standard ou Fast Fix |
| **B** | CRUD simples, endpoint não crítico | DoR + Feature Contract inline | N1 + matriz | branch `feat/*` obrigatória | Standard ou Fast Fix |
| **C** | auth, pagamento, permissões, dados sensíveis | DoR + Feature Contract (detalhado) + Anti-SPEC revisada | N2 (integration + contract + build) | revisão humana sugerida | Deep Work |
| **D** | migration, RLS, deploy, env, Stripe/MP | DoR + Feature Contract + cursor-brief + rollback + feature flag | N3 (e2e + smoke + migration validation) | staging **obrigatório** | Production |

**Desempates:**
1. Toca produção/banco real/envs → D.
2. Envolve auth/dinheiro/permissões/dados sensíveis → C.
3. Cria/altera contrato público → mínimo B.
4. Código isolado sem contrato → A.
5. Em dúvida, escolha a classe mais alta.

Referência completa: `docs/plans/risk-classification.md`.

---

## 8. Definition of Ready

Feature com DoR incompleta **não entra em execução**. No Prompt 2, se DoR está incompleta em domínio sensível (produção, banco, auth, pagamento, dados sensíveis) → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`.

Marque antes de começar:
- [ ] RFs vinculados ou justificativa clara.
- [ ] CAs claros e testáveis.
- [ ] Escopo **incluído** descrito.
- [ ] Escopo **excluído** descrito.
- [ ] Classificação A/B/C/D confirmada.
- [ ] Arquivos prováveis de alteração listados.
- [ ] Testes esperados (unit / integration / contract / e2e / smoke).
- [ ] Contratos Zod necessários ou decisão de que não precisa.
- [ ] Dependências externas.
- [ ] Impacto em banco.
- [ ] Impacto em produção (staging, rollback, feature flag).

Onde vive: **inline no item do `TODO.md`**, junto com o Feature Contract.

---

## 9. Feature Contract

Obrigatório para **B, C, D**. Opcional para A.

**Campos:**
- ID + nome + risco + cobre RF(s) + branch + CI alvo
- Objetivo (1–3 frases)
- Definition of Ready (checklist acima)
- Critérios de aceite
- Escopo incluído / excluído
- Arquivos **que podem ser alterados**
- Arquivos **que NÃO podem ser alterados** (qualquer alteração exige pausa)
- Contratos Zod (a usar/criar)
- Testes obrigatórios (matriz teste → tipo → CA → arquivo)
- Comandos obrigatórios (CI no nível alvo)
- Infra/Produção (só C/D): migration, env, staging, feature flag, **rollback plan**
- Anti-SPEC relevante (itens específicos)
- Matriz de validação (preenchida no QA)
- Gate de autonomia

**Onde vive:**
1. **Preferência:** bloco inline dentro do item do `TODO.md`.
2. Alternativa: `docs/plans/feature-contracts/F-NNN.md` se passar de ~40 linhas (típico C/D).

Template completo: `docs/plans/FEATURE-CONTRACT-template.md`.

---

## 10. Matriz de Validação

**Obrigatória no Prompt 3 (QA) para B/C/D.** Sem evidência objetiva em algum CA → `MUDANÇAS_SOLICITADAS`. Nunca `APROVADO`.

| CA | Teste | Tipo | Status | Evidência |
|---|---|---|---|---|
| CA-001 | `auth.login.test.ts::valid_credentials` | integration | passou | `npm test -- auth.login` log |
| CA-002 | `auth.login.test.ts::invalid_password` | integration | passou | idem |
| CA-003 | `login.spec.ts::happy_path` | e2e | passou | Playwright report |
| CA-004 | N/A | não coberto | falhou | criar teste antes do merge |

**O que conta como evidência:** saída de `npm test` com teste nomeado, Playwright report, CI log com `✔ passed`, migration aplicada em staging com `select`, script de smoke com exit code 0.

**O que NÃO conta:** afirmação do agente, "o código parece correto", teste com `.skip`/`.only`, cobertura genérica sem amarração ao CA.

---

## 11. CI por níveis

| Nível | Contém | Obrigatório para |
|---|---|---|
| **N1** | lint + typecheck + unit (+ build se rápido) | A, B, **Fast Fix** |
| **N2** | N1 + integration + contract + db validation + build | B relevante, C |
| **N3** | N2 + e2e + smoke + migration validation + preview deploy check | C crítica, D |

Cada projeto mapeia os scripts reais. O que importa é o **escopo do gate**, não o comando.

---

## 12. Project Wiki — memória sintetizada viva

A Project Wiki vive em `docs/wiki/`. É **memória sintetizada** entre fontes brutas (prints, logs, decisões, transcrições de Cursor/Codex) e os agentes (Claude Code, Codex, Cursor).

**Princípio:** a wiki **nunca** substitui PRD/SPEC/CONTRACTS/ADR. Sintetiza e linka.

### 12.1. Estrutura

| Página | Conteúdo | Tamanho-alvo |
|---|---|---|
| `wiki/index.md` | mapa principal — primeira leitura | ≤ 80 linhas |
| `wiki/log.md` | histórico cronológico (ingest, releases, bug fixes, validações) | ≤ 200 linhas |
| `wiki/overview.md` | 1 página com o projeto hoje (síntese do PRD) | ≤ 150 linhas |
| `wiki/architecture.md` | arquitetura técnica viva (síntese do SPEC + código real) | ≤ 150 linhas |
| `wiki/modules/<mod>.md` | memória por área (auth, db, payments, deploy) | ≤ 200 linhas |
| `wiki/features/<F-NNN>.md` | resumo de 1 parágrafo após merge (C/D) | ≤ 30 linhas |
| `wiki/runbooks/<slug>.md` | passos para deploy, rollback, smoke, bug recorrente | ≤ 150 linhas |
| `wiki/context/<F-NNN>.md` | Context Pack por tarefa (descartável) | ≤ 150 linhas |

### 12.2. Skill `/wiki` — 4 modos

| Modo | Quando usar | Saída |
|---|---|---|
| **`/wiki ingest <fonte>`** | usuário cola print/log/erro/transcript/decisão | atualiza páginas relevantes + linha em `log.md` tipo `INGEST` |
| **`/wiki context <F-NNN>`** | antes de feature significativa; ou para handoff entre agentes | cria/atualiza `wiki/context/<F-NNN>.md` |
| **`/wiki lint`** | início de projeto bagunçado; antes de refactor grande; antes de produção | relatório curto (somente leitura) |
| **`/wiki repair`** | depois de lint, para aplicar correções | edita páginas + arquiva log se inchado |

### 12.3. Quando usar a wiki

| Cenário | Comece por |
|---|---|
| Início de sessão | ler `wiki/index.md` + `wiki/context/<atual>.md` |
| Bug urgente | `/fast-fix` (lê `wiki/runbooks/` + `wiki/log.md`) |
| Nova feature B/C/D | `/wiki context F-NNN` antes do Prompt 2 |
| Continuar em outro agente | abrir `wiki/index.md` + `wiki/context/<atual>.md` |
| Projeto bagunçado | `/wiki lint` → `/wiki repair` antes de codar |
| Após merge C/D | resumo curto em `wiki/features/F-NNN.md` |
| Bug recorrente (≥ 2 ocorrências) | criar `wiki/runbooks/bug-<slug>.md` |

### 12.4. Fonte de verdade vs. wiki

| Domínio | Fonte de verdade | Espelho na wiki |
|---|---|---|
| Produto | `docs/product/PRD.md` | `wiki/overview.md` |
| Comportamento + Anti-SPEC | `docs/specs/SPEC.md` | `wiki/architecture.md` (resumo) |
| Contratos | `packages/shared/types/` (Zod) | `docs/contracts/CONTRACTS.md` (legível) |
| Decisão arquitetural | `docs/decisions/adr/ADR-NNN.md` | citada em `wiki/architecture.md` |
| Decisão operacional | `docs/plans/DECISIONS_LOG.md` | linha em `wiki/log.md` quando relevante |
| Estado vivo | `TODO.md` + `git log` | resumo em `wiki/log.md` |

### 12.5. Cadência

- **Diariamente (em loop normal):** linha em `wiki/log.md` por release/bugfix; Context Pack se a tarefa continua.
- **A cada 2-4 semanas, ou antes de release:** rode `/wiki lint`. Se relatar amarelo/vermelho, `/wiki repair` na próxima janela.
- **NÃO use `/wiki lint` antes de cada microtarefa.** É checkpoint, não cerimônia.

---

## 13. Fast Fix — Project Quick para bug urgente

`/fast-fix` é o **modo Project Quick**: bug urgente classe A/B sem auth/payment/dados sensíveis/banco/env/deploy, < 30 min do diagnóstico ao PR.

### 13.1. Quando USAR

Reúna **TODOS**:

- [ ] Bug confirmado (não suspeita).
- [ ] Classe A ou B.
- [ ] Não toca: auth, autorização, pagamento/billing, webhook financeiro, dados sensíveis/financeiros, RLS, migration, env vars, deploy, integração externa crítica.
- [ ] Estimativa < 30 min.
- [ ] Você confirma a urgência (cliente travado, demo iminente, dev parado).

### 13.2. Quando NÃO usar

- Toca auth/payment/dados sensíveis → Standard/Deep Work.
- Exige migration/rollback/deploy → Production.
- "Acho que é fácil" sem diagnóstico → Standard.
- Sem teste reproduzindo → Standard (escreva teste primeiro).
- Bug recorrente (≥ 2 ocorrências passadas) → Deep Work.

### 13.3. Processo (resumido — Prompt 0)

1. **Screen** (60s) — `wiki/index.md`, `wiki/runbooks/`, `wiki/log.md` últimos 30 dias, `TODO.md §5`. Se runbook existe, **siga o runbook**.
2. **Gate de classe** (30s) — confirmar A/B sem domínios sensíveis. Se não, SAIR.
3. **Reprodução** (5 min) — UM teste falha do jeito esperado.
4. **Fix** (10–15 min) — diff mínimo, ≤ 3 arquivos, ≤ 50 linhas.
5. **Validação** (3 min) — CI N1 verde.
6. **Wiki memory** (1 min) — linha em `wiki/log.md` tipo `BUGFIX`. Runbook se bug capaz de voltar.
7. **PR/Commit** — A: commit em main; B: branch + PR + CI verde.
8. **Fechamento** (30s) — TODO.md §5 → Resolvido.

### 13.4. Gates duros (saída automática do modo)

| Gate | Se falha |
|---|---|
| Toca auth/payment/dados sensíveis | SAIR — escalar para Standard/Deep Work |
| Diff > 50 linhas ou > 3 arquivos | SAIR |
| Tempo > 30 min | SAIR |
| Migration/env/deploy aparecem | SAIR — escalar para Production |
| Sem teste reproduzindo | SAIR — escrever teste via Standard |
| ≥ 2 ocorrências passadas | SAIR — Deep Work (bug com causa profunda) |

Detalhes completos em `skills/fast-fix/SKILL.md`. Antipadrões em `skills/fast-fix/references/anti-patterns.md`.

---

## 14. Modos de rigor

Escala de cerimônia. Comece pelo modo do tamanho do risco. Em dúvida, suba.

| Modo | Quando | Cerimônia |
|---|---|---|
| **MVP Lite** (NOVO v3.2) | validação de ideia, hackathon, protótipo < 1 semana, **sem produção, sem dinheiro real, sem dados sensíveis** | só `TODO.md` + classe + branch + 1 teste no caminho crítico + commit + linha em `wiki/log.md`. Sem PRD/SPEC/Feature Contract obrigatórios. |
| **Fast Fix** | bug urgente A/B sem domínios sensíveis, < 30 min | `/fast-fix` (Prompt 0) — gates duros, sai do modo se escala |
| **Standard** | feature B | Feature Contract inline + matriz + Validation Mode no QA |
| **Deep Work** | feature C | Feature Contract detalhado + Validation Mode forte + revisão humana sugerida |
| **Production** | classe D (migration/deploy/env) | Feature Contract + cursor-brief + rollback + staging + smoke + e2e |
| **Project Reorg** | projeto bagunçado | `/wiki lint` + CURRENT_REALITY + 0 código até autorização |

### 14.5. MVP Lite — quando e como (NOVO v3.2)

Resolve o gap entre "pular o Harness inteiro" (que era a única opção em v3.1) e "Standard com Feature Contract" (que é overkill para validar ideia em 3 dias).

**Use MVP Lite quando TODOS os critérios baterem:**

- [ ] Vida estimada do projeto/módulo < 1 semana **OU** propósito é validar ideia antes de decidir se vira projeto.
- [ ] Não vai para produção real (cliente real / dinheiro real / dados sensíveis).
- [ ] Sem auth crítica, sem payment, sem webhook financeiro, sem RLS.
- [ ] Você aceita jogar o código fora se a hipótese falhar.

**Cerimônia mínima do MVP Lite:**

1. `/project-kickoff` cria a estrutura (mas você ignora a maioria dos templates).
2. Anote a hipótese em `TODO.md`:
   ```
   ## Hipótese MVP
   - O que valido: [ex: usuários convertem mais com onboarding em 1 step vs 3 steps]
   - Como sei que validou: [ex: ≥ 30% conversão em 50 sessões]
   - Prazo: [ex: 4 dias]
   - Critério de promoção a Standard: [ex: hipótese validada → migrar para PRD/SPEC retroativos]
   ```
3. Loop:
   - Crie branch `mvp/<slug>`.
   - Implemente o caminho crítico.
   - **1 teste no caminho crítico** (não 5, não nenhum — exatamente 1 que prova que o fluxo principal funciona).
   - Commit.
   - 1 linha em `wiki/log.md` tipo `[MVP]`.
4. Sem PRD/SPEC/CONTRACTS/Feature Contract/matriz obrigatórios.
5. Wiki só recebe o `log.md` (sem overview/architecture/runbooks até virar Standard).

**Quando MVP Lite vira obrigatoriamente Standard:**

- O MVP foi validado e vai virar produto. **Migre antes da próxima feature relevante:**
  1. Cenário B (§16) — gere `CURRENT_REALITY.md` do que existe.
  2. `/consultor-prd` retroativo → PRD.
  3. `/SDD-avancado` retroativo → SPEC + Anti-SPEC + Zod.
  4. `/agents-protocol` → AGENTS.md + cursor-brief se houver D.
- O MVP começou a tocar produção, auth, payment ou dados sensíveis. **Pare imediatamente:** abra Feature Contract para a próxima feature ANTES de continuar.
- O MVP passou de 1 semana de uso real (mesmo interno).

**Antipadrões do MVP Lite:**

- "Vou usar MVP Lite porque é mais rápido" para algo que vai a produção. **Não.** MVP Lite é para validação descartável.
- Ficar > 2 semanas em MVP Lite. **Migre ou descarte.** Cada dia extra acumula dívida invisível.
- MVP Lite com auth real ou conexão a banco de produção. **Não.** Use Standard.

---

## 15. Cenário A — Projeto novo

---

## 15. Cenário A — Projeto novo

1. `mkdir meu-saas && cd meu-saas`
2. `/project-kickoff` — estrutura + templates v3.2 em `docs/plans/` e `docs/wiki/`.
3. `/consultor-prd` — 16 etapas → PRD.md.
4. `/SDD-avancado` — SPEC + CONTRACTS + Zod + TODO com A/B/C/D + Feature Contract inline.
5. **(NOVO v3.2)** Peça ao agente:
   - "atualize `docs/wiki/overview.md` a partir do PRD"
   - "atualize `docs/wiki/architecture.md` a partir do SPEC"
6. `/skill-scout` opcional.
7. `/agents-protocol` — AGENTS.md + cursor-brief.md se houver D.
8. Loop de features: Prompt 1 → Prompt 2 → Prompt 3.
9. **Pós-merge (v3.2):** linha em `wiki/log.md`, resumo em `wiki/features/` (C/D), `/wiki context F-NNN+1` se quiser preparar a próxima.

---

## 16. Cenário B — Projeto já iniciado

1. **Diagnóstico** — `/wiki lint` antes de tudo (ainda sem wiki, vai dar vermelho — esperado).
2. **Espinha mínima:** copie `AGENTS.md` v3.2, `TODO.md`, `CLAUDE.md` v3.2, `ci.yml`, ADR template + pastas `docs/plans/`, `docs/wiki/`, `packages/shared/types/`.
3. **Obrigatório: `docs/plans/CURRENT_REALITY.md`** — gere antes de PRD/SPEC retroativos.
4. **(NOVO v3.2)** `/wiki ingest <CURRENT_REALITY>` — sintetiza para `wiki/overview.md` e `wiki/architecture.md`.
5. **PRD retroativo** — `/consultor-prd` em modo retroativo, respeitando CURRENT_REALITY.
6. **SPEC retroativo a partir do código** — `/SDD-avancado`, extraindo RFs do que existe.
7. `/agents-protocol`.
8. Próxima feature nasce v3.2 (Standard/Deep Work conforme classe).

**Regra de ouro:** não traga o código antigo à conformidade num big-bang. Refactor por oportunidade, dentro de Feature Contract.

---

## 17. Cenário C — Projeto em produção

Diferença vs. B: **adoção gradual, sem tocar no que funciona. Nenhum refactor preventivo.**

Regras:
- Nenhum refactor preventivo.
- Nenhuma migration preventiva.
- Paridade de testes antes de refatorar rota.
- Feature flag se muda contrato público.

Sequência:
1. Diagnóstico + **CURRENT_REALITY.md**.
2. **(NOVO v3.2)** Wiki bootstrapping: `wiki/overview.md` + `wiki/architecture.md` + `wiki/runbooks/` para deploys/rollbacks já existentes.
3. Espinha mínima priorizando **CI verde primeiro**.
4. PRD retroativo com seção "Restrições de produção" (tabelas/endpoints intocáveis).
5. SPEC **parcial** — só para a próxima feature.
6. `CONTRACTS.md` só para os tipos da feature nova.
7. Anti-SPEC crítica: "não mexer em tabela X sem migration plan", "não alterar `/v1/*`".
8. ADRs retroativos para decisões já tomadas.
9. `/agents-protocol` — toda operação D em produção exige Rollback + staging + smoke.

Features de produção → **classe D**. Sem exceção quando toca banco/env/deploy real.

**Bug em produção?** → cenário F (`/fast-fix`) se A/B sem domínios sensíveis. Senão, Production.

---

## 18. Cenário D — Projeto bagunçado

**Objetivo:** chegar à estrutura padrão sem quebrar nada, em incrementos auditáveis.

### Fases

**Fase 0 (NOVO v3.2) — Wiki First**
- `/project-kickoff` (cria `docs/wiki/`).
- `/wiki lint` — relata vermelho (esperado).
- Gere `docs/plans/CURRENT_REALITY.md` (template).
- `/wiki ingest <CURRENT_REALITY>` para popular `overview.md` e `architecture.md`.
- **Zero código até esta fase fechar.**

**Fase 1 — Inventário** (→ `docs/plans/inventario.md`).

**Fase 2 — Alvo** (→ `docs/plans/target-structure.md` com MOVE_PARA/MESCLA/ARQUIVAR/MANTER).

**Fase 3 — Plano em ondas** (→ `docs/plans/PLAN.md` com ondas R-1..R-5).

**Fase 4 — Execução** — cada item é feature classe B ou C, com Feature Contract.

**Fase 5 — Consolidação** — PRD/SPEC retroativo (cenário B com CURRENT_REALITY).

---

## 19. Cenário E — Migração v2 / v3.1 → v3.2

### De v2 tradicional

Tabela de conversão (preservada do v3.1):

| v2 | v3.2 |
|---|---|
| `state/project-state.json` | excluir → `TODO.md` |
| `state/progress.jsonl` | excluir → `git log` + `wiki/log.md` |
| `state/handoffs/*.json` | excluir → `wiki/context/<F-NNN>.md` |
| `state/bugs/*.json` | excluir → `TODO.md §5` + `wiki/runbooks/` se recorrente |
| `WAVE-PLAN.md` por task | `PLAN.md` por feature (ou remover se ≤6 features) |
| `AGENT-BRIEFS/*` | excluir / mover cursor-brief para `docs/plans/cursor-brief.md` |

### De v3.1 → v3.2 (mais simples)

1. Substituir `AGENTS.md` v3.1 → v3.2 (preserva tudo, adiciona §21 e §22).
2. Substituir `CLAUDE.md` v3.1 → v3.2 (preserva tudo, adiciona wiki/index na leitura inicial).
3. Criar `docs/wiki/` com `index.md`, `log.md`, `overview.md`, `architecture.md` (gere a partir de PRD/SPEC já existentes).
4. Criar diretórios vazios `wiki/modules/`, `wiki/features/`, `wiki/runbooks/`, `wiki/context/`.
5. Instalar skills `/wiki` e `/fast-fix`.
6. Atualizar `prompts-cheatsheet.md` (adicionar Prompt 0).
7. Próxima feature já usa fluxo v3.2.

**Não precisa migrar histórico passado.** O `wiki/log.md` começa do zero e cresce a partir de agora.

---

## 20. Cenário F — Bug urgente / Project Quick

> **Foco extra do v3.2.** Cenário mais comum em projetos em produção, em desenvolvimento com prazo, ou demo iminente.

### 20.1. Diagnóstico em 60 segundos

Antes de tocar código:

1. **Bug confirmado?** Tem repro? Se "acho que é..." → Standard, não Fast Fix.
2. **Que classe?** Toca auth/payment/dados sensíveis → C; banco/migration/env/deploy → D. **Se C ou D, NÃO use Fast Fix.**
3. **Já apareceu?** Cheque `wiki/log.md` últimos 30 dias e `wiki/runbooks/`. Se runbook existe, siga. Se ≥ 2 ocorrências, é Deep Work.
4. **Tempo disponível?** < 30 min até o PR? Se não, é Standard.

### 20.2. Execução (Prompt 0)

Cole o Prompt 0 de `skills/agents-protocol/references/prompts-cheatsheet.md §0` no Claude Code. O agente executa:

```
SCREEN → GATE → REPRO → FIX → VALIDAÇÃO → WIKI MEMORY → PR → FECHAMENTO
```

Cada passo tem tempo-alvo e gate de saída. Se algo cresce, o próprio agente sai do modo e escala.

### 20.3. Após o fast-fix

- Se o bug **vai voltar** (p. ex. ambiente flaky, integração instável): runbook em `wiki/runbooks/bug-<slug>.md`.
- Se o bug **revelou design ruim**: abrir feature de Deep Work no `TODO.md §2 Backlog` para refactor consciente.
- Se o bug **mostrou lacuna em monitoring**: ADR ou DECISIONS_LOG.

### 20.4. Quando o Fast Fix falha

| Sintoma | Próximo passo |
|---|---|
| Diagnóstico revelou auth/payment afetado | escale para Deep Work (Prompt 2 classe C) |
| Diagnóstico revelou migration/env necessária | escale para Production (Prompt 2 classe D) |
| Causa raiz não está no diff inicial | escale para Standard com investigação de teste primeiro |
| Bug é o 3º+ no mesmo módulo | abra ADR ou refactor em Deep Work |
| Tempo passou de 30 min sem terminar | pause; vire Standard com Feature Contract |

**Não force Fast Fix em algo que cresceu. Falhar nesse modo é indicador de que o problema é maior do que parece.**

### 20.5. Lista de fast-fixes típicos vs. NÃO-fast-fixes

| ✅ Fast Fix | ❌ NÃO Fast Fix |
|---|---|
| Typo em label de UI | Renomear chave do JWT |
| Off-by-one em paginação | Mudar política de RLS |
| Null check faltando em endpoint não crítico | Mudar fluxo de auth |
| Validação Zod faltante em campo público | Adicionar campo em payload de pagamento |
| Cor errada no botão | Mudar copy de termo de uso (jurídico) |
| Layout quebrado em mobile | Migration de schema |
| Trocar string de erro genérica | Trocar provider de e-mail |
| Lógica isolada de formatação | Adicionar dependência de runtime |

---

## 21. Cenário G — Triagem de bugs em lote

> **Cenário comum:** o cliente / suporte / equipe te enviou ≥ 2 bugs na mesma janela. Antes de atacar, decida o quê, em que ordem e em qual modo.

### 21.1. Quando usar `/triage-bugs`

- ≥ 2 bugs reportados no mesmo dia/turno.
- Você precisa caber o que dá no tempo disponível e parquear o resto.
- Mistura provável de classes A/B/C/D e modos diferentes.

### 21.2. Como usar (resumo — Prompt 4 dentro da skill)

Cole no Claude Code:

```
/triage-bugs

Lista (texto livre, 1 bug por bloco, pode vir de Slack/e-mail/GitHub):
<<<
[BUG 1] ...
[BUG 2] ...
[BUG 3] ...
>>>

Tempo disponível hoje: [ex: 4 horas]
Prioridade declarada: [ex: BUG 1 é P0 | "todos" = sem prioridade declarada]
```

A skill devolve em < 5 min:

- **Tabela:** ID + bug + classe + domínio + urgência + impacto + esforço + modo + recorrência + score.
- **Plano de hoje:** lista ordenada com comando exato para cada bug que cabe.
- **Backlog:** o que não cabe hoje, ordenado.
- **Escalations:** classe D, vulnerabilidade, recorrência ≥ 3 — atenção humana antes de tocar.
- **Wiki updates:** acrescenta linhas em `TODO.md §5`, 1 linha em `wiki/log.md` tipo `[INGEST]`, stubs de runbook se recorrência detectada.
- **Próxima ação imediata:** comando exato para começar agora.

### 21.3. Regras importantes

- **Triagem nunca executa fix sozinha.** Devolve plano, espera você confirmar.
- **Bugs financeiros / payment / webhook** = quase sempre classe D, mesmo que o cliente diga "pode esperar".
- **Vulnerabilidade ativa de auth** = P0-emergência, mesmo que o tempo declarado pelo usuário seja curto. O agente reporta; o humano decide a janela.
- **Recorrência ≥ 3** do mesmo padrão = pare de aplicar fast-fix; vá para Deep Work com refator.
- **Pedido de feature disfarçado de bug** = marca como NÃO É BUG, abre como feature em `TODO §2 Backlog`. Não infla §5.
- **Lista com ≥ 8 bugs** = dev solo perde qualidade. Quebre em 2 sessões.

### 21.4. TODO.md §5 estendido (após triagem)

A tabela de bugs ganha colunas extras:

```
| ID | Descrição | Repro | Classe | Domínio | Urgência | Impacto | Esforço | Modo | Status | Notas |
| BUG-NNN | ... | ... | C | auth | P0 | crítico | < 30min | standard | TRIADO | recorrência? runbook? |
```

`Status` evolui: `TRIADO → EM FIX → EM QA → RESOLVIDO` (com SHA/PR).

### 21.5. Exemplos completos

Em `skills/triage-bugs/references/triage-examples.md` — 5 casos reais (lista in → plano out), incluindo recorrência detectada e vulnerabilidade ativa.

---

## 22. Cenário H — MVP / validação de ideia

> **Cenário comum:** você teve uma ideia e quer testar em 3-7 dias antes de decidir se vira projeto. Standard é overkill; pular o Harness inteiro deixa você sem nada.

### 22.1. Use modo MVP Lite (§14.5)

Critérios obrigatórios para MVP Lite:

- [ ] Vida estimada < 1 semana **ou** propósito é validar hipótese.
- [ ] Sem produção real, sem dinheiro real, sem dados sensíveis.
- [ ] Sem auth crítica / payment / webhook financeiro / RLS.
- [ ] Você aceita jogar o código fora se a hipótese falhar.

### 22.2. Cerimônia mínima

1. `/project-kickoff` (ignora a maioria dos templates por enquanto).
2. Anote a hipótese no topo do `TODO.md`:
   ```
   ## Hipótese MVP
   - O que valido: [...]
   - Como sei que validou: [...]
   - Prazo: [...]
   - Critério de promoção a Standard: [...]
   ```
3. Loop:
   - Branch `mvp/<slug>`.
   - Implementa caminho crítico.
   - **1 teste no caminho crítico** (não 5, não nenhum).
   - Commit.
   - 1 linha em `wiki/log.md` tipo `[MVP]`.
4. **Sem** PRD/SPEC/CONTRACTS/Feature Contract/matriz obrigatórios.
5. Wiki só recebe `log.md` por enquanto.

### 22.3. Quando MVP Lite vira obrigatoriamente Standard

- Hipótese validada → vai virar produto. Migre para Standard ANTES da próxima feature relevante (cenário B retroativo).
- MVP começou a tocar produção, auth, payment, dados sensíveis. **Pare imediatamente** e abra Feature Contract.
- MVP passou de 1 semana de uso real (mesmo interno).

### 22.4. Antipadrões

- "Vou usar MVP Lite porque é mais rápido" para algo que vai a produção. **Não.**
- Ficar > 2 semanas em MVP Lite sem migrar nem descartar. **Acumula dívida invisível.**
- MVP Lite com banco de produção, env real, ou auth de cliente real. **Não.**

---

## 23. Continuidade entre agentes (Claude ↔ Codex ↔ Cursor)

> **Cenário comum:** Claude esgotou tokens / você quer trabalhar offline com Codex / vai operar infra com Cursor Agent.

### 23.1. Antes de fechar a sessão atual

```
/wiki context F-NNN
```

O agente cria/atualiza `docs/wiki/context/F-NNN.md` com:
- Estado atual (o que está feito, o que falta)
- Arquivos relevantes
- Restrições da tarefa
- Próximos passos concretos
- Decisões abertas
- Handoff: "última ação", "o que NÃO fiz e o próximo deveria evitar"

### 23.2. No próximo agente

Abra Codex/Cursor. Cole isto:

```
[CONTINUAR TAREFA]

Leia, nesta ordem:
1. docs/wiki/index.md
2. docs/wiki/context/F-NNN.md
3. AGENTS.md (regras universais)
4. TODO.md (item F-NNN)
5. Feature Contract (inline em TODO ou em docs/plans/feature-contracts/)

Depois execute o passo "PRÓXIMOS PASSOS CONCRETOS" do context pack, respeitando as restrições e o handoff.

Quando terminar (ou pausar): atualize wiki/context/F-NNN.md com o novo handoff.
```

O próximo agente tem contexto completo sem precisar reler o repositório inteiro.

### 23.3. Ao fim da feature

- Resumo de ≤ 5 linhas em `wiki/features/F-NNN.md` (C/D).
- Linha em `wiki/log.md` tipo `RELEASE`.
- **Delete** `wiki/context/F-NNN.md` (Context Pack consumido).

### 23.4. Por que isso funciona

- `AGENTS.md` é o contrato comum entre todos os agentes — não precisa duplicar regras.
- `wiki/index.md` é o mapa que qualquer agente entende em < 1 min.
- `wiki/context/F-NNN.md` é o estado da tarefa, atualizado pelo último agente que tocou.
- Estado real do código continua em `git` + `TODO.md`. A wiki é síntese, não cópia.

---

## 24. Operação diária

**Máximo 10 itens. 5 minutos no total.**

### Abrir o dia
- `git pull`.
- Abrir Claude Code. Cole **Prompt 1**.
- Decidir: continuar feature, iniciar próxima, resolver bloqueio, ou bug urgente (`/fast-fix`).
- Checar classe + DoR + autonomia + wiki health antes de começar.

### Durante
- Uma branch por vez.
- Teste primeiro, implementação depois.
- Ideias/bugs → `TODO.md` agora.
- Feature cresceu? Pause, reclassifique, talvez divida.

### Fechar
- Atualizar `TODO.md` com matriz preenchida se há item em QA.
- PR aberto? **Prompt 3** → APROVADO com evidência → merge.
- **Update memory:** linha em `wiki/log.md`. Se tarefa continua, `/wiki context F-NNN`.
- `git push`.

### Cadência semanal/quinzenal
- A cada 2-4 semanas, ou antes de release: `/wiki lint`. Repair se preciso.

---

## 25. Checklist por feature / PR

Ver `skills/agents-protocol/references/feature-pr.md` (v3.2 — checklist por classe + Update Memory).

---

## 26. Antipadrões

- **"TODO.md só na cabeça hoje"** → não.
- **"Refactor rápido sem PRD/SPEC"** → sem Feature Contract vira dívida invisível.
- **"CI vermelho mas teste passa local, vou mergear"** → nunca.
- **"Vou rodar 3 sessões paralelas"** → se atropelam.
- **"Feature cresceu mas vou terminar logo"** → pause, reclassifique.
- **"Classe B mas começou a tocar banco"** → reclassifique para C ou D **antes** de continuar.
- **"Classe D sem rollback, só dessa vez"** → bloqueia no Prompt 3.
- **"Aprovar PR sem matriz"** → proibido para B/C/D.
- **"Editar PRD/SPEC/Anti-SPEC para caber a feature"** → pause e confirme com humano.
- **"Validation Mode é chato, só rodei o happy path"** → em C/D, isso é `MUDANÇAS_SOLICITADAS`.
- **"DoR faltou um campo mas tá perto"** (em domínio sensível) → `BLOQUEADO`.
- **"Mexi num arquivo fora da lista porque estava no caminho"** → sem justificativa, `BLOQUEADO`.
- **"Vou usar Fast Fix nesse bug de auth, é só 2 linhas"** (NOVO v3.2) → não, escale.
- **"Esqueci de atualizar `wiki/log.md`"** (NOVO v3.2) → feature B/C/D não fecha sem isso.
- **"`/wiki lint` antes de cada microtarefa"** (NOVO v3.2) → não, é checkpoint quinzenal/pre-release.
- **"Edito `wiki/architecture.md` para `caber` a feature"** (NOVO v3.2) → ajuste o SPEC primeiro; wiki é espelho.
- **"Wiki virou diário"** (NOVO v3.2) → revise, arquive, corte.

---

## 27. Quando NÃO usar o Harness

Pule o framework inteiro se:

- **Script descartável de 1 arquivo** que vai rodar 3 vezes.
- **Protótipo de 2 horas** para validar UI.
- **Spike técnico** ("essa lib aguenta 10k req/s?") — crie só o mínimo para medir.
- **Time de 2+ devs.** Provavelmente quer o Harness v2 tradicional ou um meio-termo.

Regra: se o projeto não dura nem 1 semana ou você não liga de perder o código, pule.

---

## 28. Referência rápida

### Comandos do Claude Code

| Comando | Quando |
|---|---|
| `/project-kickoff` | repo novo |
| `/consultor-prd` | depois do kickoff |
| `/SDD-avancado` | com PRD aprovado |
| `/skill-scout` | integrações não triviais (opcional) |
| `/agents-protocol` | antes de começar execução |
| `/wiki ingest \| context \| lint \| repair` | manter memória sintetizada (v3.2) |
| `/fast-fix` | bug urgente A/B sem auth/payment/db (v3.2) |
| `/triage-bugs` | ≥ 2 bugs do cliente para priorizar (v3.2) |

### Prompts de bolso

| Prompt | Quando |
|---|---|
| Prompt 0 | bug urgente (v3.2) |
| Prompt 1 | toda abertura do Claude Code |
| Prompt 2 | toda nova feature B/C/D |
| Prompt 3 | antes de todo merge (B/C/D) |

### Localização dos artefatos

| Preciso de... | Vai em... |
|---|---|
| Mapa da memória sintetizada | `docs/wiki/index.md` (v3.2) |
| Histórico cronológico | `docs/wiki/log.md` (v3.2) |
| Contexto reusável entre agentes | `docs/wiki/context/F-NNN.md` (v3.2) |
| Receita operacional / bug recorrente | `docs/wiki/runbooks/<slug>.md` (v3.2) |
| Resumo da feature após merge | `docs/wiki/features/F-NNN.md` (v3.2) |
| Estado atual + Feature Contract inline | `TODO.md` (raiz) |
| O quê e por quê | `docs/product/PRD.md` |
| O que o sistema faz | `docs/specs/SPEC.md` (Anti-SPEC §6) |
| Contratos legíveis | `docs/contracts/CONTRACTS.md` |
| **Contratos executáveis** | `packages/shared/types/*.ts` |
| Estado real do repo | `docs/plans/CURRENT_REALITY.md` |
| Decisão arquitetural | `docs/decisions/adr/ADR-NNN-*.md` |
| Decisão operacional recorrente | `docs/plans/DECISIONS_LOG.md` |
| Regras para agentes | `AGENTS.md` (raiz) |
| Ajustes do Claude Code | `CLAUDE.md` (raiz) |

### Princípios não-negociáveis (resumo)

1. Gerador ↔ Avaliador é estrutural (CI).
2. Contrato é código (Zod).
3. Anti-SPEC é sagrada.
4. Estado único (TODO.md + git log).
5. CI verde no nível da classe = merge.
6. Feature é a unidade.
7. Classificação A/B/C/D obrigatória.
8. Matriz de validação obrigatória (B/C/D).
9. Produção exige staging + rollback + smoke (D).
10. Validation Mode no QA (B/C/D).
11. Sem evidência, nunca APROVADO.
12. BLOQUEADO é retorno legítimo.
13. Suba a classe, nunca desça.
14. Teste fake não conta.
15. **Wiki é memória sintetizada, NUNCA fonte de verdade. (v3.2)**
16. **Fast Fix é exceção, não norma. Em dúvida, escale. (v3.2)**
17. **Toda feature B/C/D termina com 1 linha em `wiki/log.md`. (v3.2)**

---

## 29. Anexos — mapa do pacote

Este manual é o **documento único** do Harness v3.2. Tudo o mais é skill self-contained ou utilitário para o mantenedor.

### Pacote enxuto — o que vai para o seu repo

```
skills/                          ← copie para ~/.claude/skills/ ou .claude/skills/
harness-v3.2-manual.html         ← solte na raiz do projeto (referência humana única)
```

Mais nada é necessário. Cada skill carrega seus próprios templates em `assets/`.

### Skills (`skills/`)

| Skill | Conteúdo |
|---|---|
| `/project-kickoff` | cria estrutura + escreve AGENTS.md/CLAUDE.md/TODO.md/CI/wiki/etc.; assets em `skills/project-kickoff/assets/` (incluindo `assets/wiki/` para Project Wiki) |
| `/consultor-prd` | 16 etapas → PRD.md (modo retroativo lê `CURRENT_REALITY.md`) |
| `/SDD-avancado` | SPEC + Anti-SPEC + CONTRACTS + Zod + TODO com classe + DoR + Feature Contract inline |
| `/skill-scout` | catálogo de capacidades + análise de risco operacional (opcional) |
| `/agents-protocol` | AGENTS, cursor-brief, **prompts-cheatsheet** (4 prompts), **daily-ops**, **feature-pr** — em `references/` |
| `/wiki` (v3.2) | `ingest \| context \| lint \| repair` |
| `/fast-fix` (v3.2) | Project Quick com Prompt 0 embutido |
| `/triage-bugs` (v3.2) | Triagem em lote — devolve plano de ataque + atualiza TODO §5 |

### Templates dentro das skills

- `skills/project-kickoff/assets/` — todos os templates da raiz do projeto + `assets/wiki/` (6 templates da Project Wiki).
- `skills/agents-protocol/assets/` — AGENTS-template, cursor-brief, FEATURE-CONTRACT, VALIDATION-MATRIX, DECISIONS_LOG, risk-classification, PR template.
- `skills/SDD-avancado/assets/` — PRD/SPEC/CONTRACTS/PLAN/TODO templates + Zod example + risk-classification.
- `skills/consultor-prd/assets/` — CURRENT_REALITY template + completeness checklist + prd_template.
- `skills/skill-scout/assets/` — skills-manifest-template.
- `skills/wiki/references/wiki-flows.md` — 6 fluxos de exemplo (ingest, context, lint, repair).
- `skills/fast-fix/references/anti-patterns.md` — 10 armadilhas de fast-fix.
- `skills/agents-protocol/references/prompts-cheatsheet.md` — **fonte canônica dos 4 prompts (0/1/2/3)**.
- `skills/agents-protocol/references/daily-ops.md` — rotina diária.
- `skills/agents-protocol/references/feature-pr.md` — checklist por feature/PR.

### Pacote raiz (mantenedor)

- `README.md` — instruções de deploy.
- `CHANGELOG-v3.2.md` — diff v3.1 → v3.2.
- `harness-v3.2-manual.md` — **este arquivo, fonte do HTML.**
- `harness-v3.2-manual.html` — manual offline para soltar no projeto.
- `_build_html.py` — `python _build_html.py` regera o HTML quando o MD muda.
- `legacy/` — `harness-v3.1-manual.md` + `CHANGELOG-v3.1.md` (não vai para deploy).

---

*Última atualização: 2026-05-08 — Harness v3.2 · Project Wiki + Fast Fix · documento único consolidado.*
