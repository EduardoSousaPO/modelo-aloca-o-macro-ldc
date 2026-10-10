---
name: agents-protocol
description: >
  Transforma a documentação SDD aprovada no protocolo de execução multi-agente do Harness v3.2 — fluxo enxuto para desenvolvedor solo com Claude Code (gerador), Codex/Cursor (continuidade ou infra) e CI (avaliador). Gera PLAN por features, atualiza AGENTS.md com papéis + classificação A/B/C/D + autonomia/pausa, produz cursor-brief com Rollback quando há classe D, e entrega os 4 prompts do dia a dia (Fast Fix, Início de sessão, Implementar feature, QA Validation Mode) + checklists daily-ops e feature-pr.
  Use SEMPRE após /SDD-avancado estar concluído e aprovado. Ative também quando o usuário mencionar: "começar a desenvolver", "passar para implementação", "iniciar execução", "como executar o plano", "configurar protocolo de agentes", "configurar AGENTS.md", "prompts do dia a dia", ou qualquer variação que indique transição da documentação para execução feature a feature.
  Substitui a antiga skill cursor-team-protocol (rename em v3.2 — o nome novo reflete que a skill orquestra TODOS os agentes, não apenas Cursor).
---

# /agents-protocol — Protocolo Multi-Agente (Harness v3.2 · Project Wiki + Fast Fix)

> **Renamed em v3.2** de `cursor-team-protocol` → `agents-protocol`. O escopo nunca foi exclusivo do Cursor: a skill define o **contrato comum entre Claude Code, Codex, Cursor Agent e CI**. O `cursor-brief.md` continua sendo um dos outputs (só quando classe D + MCP).

Você ativou o **Agents Protocol** v3.2. O time enxuto é: **você + Claude Code (gerador principal) + Codex (continuidade quando Claude esgota) + Cursor Agent (infra/MCP, opcional, classe D) + CI (avaliador)**. Não existem 3 LLMs coordenados — existem papéis estruturais.

**Novidades do Validation Mode Patch** (complementam o Feedback Hardened):

- QA opera em **Validation Mode** — tenta quebrar a feature antes de aprovar.
- **Fail fast em DoR incompleta** em domínio sensível → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`.
- **Arquivo fora do Feature Contract** sem justificativa aceita → `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT`.
- **Auto-reclassificação de risco** (A→B→C→D) obrigatória quando a natureza muda.
- **Testes mínimos por classe** consolidados em `risk-classification.md`.
- **DECISIONS_LOG.md** opcional como memória operacional entre ADR e TODO.
- Cursor Agent **não decide produto nem comportamento** — só executa infra.

**Pré-requisitos:** os seguintes artefatos devem existir e estar aprovados:

- `docs/specs/SPEC.md` — RFs, CAs, Anti-SPEC
- `docs/contracts/CONTRACTS.md` — espelho dos contratos
- `packages/shared/types/` — schemas Zod (fonte de verdade)
- `TODO.md` — lista inicial de features com classificação A/B/C/D
- `AGENTS.md` — contrato com agentes (versão v3.1)

Se faltar algum, execute `/SDD-avancado` antes.

---

## O que esta skill produz

```
docs/plans/
├── PLAN.md                           ← OPCIONAL: ondas (se complexidade justifica)
├── cursor-brief.md                   ← OPCIONAL: brief para Cursor Agent (classe D)
├── feature-contracts/                ← OPCIONAL: Feature Contracts extensos (C/D)
│   └── F-NNN.md
└── skills-manifest.md                ← já existia? preserva.

AGENTS.md                             ← atualizado: Gerador + Infra + Avaliador + classificação + autonomia
TODO.md                               ← cada feature com classe A/B/C/D + DoR + Feature Contract inline
```

**O que NÃO produz:**
- `WAVE-PLAN.md` por task atômica
- `AGENT-BRIEFS/codex-brief.md` / `cli-brief.md`
- `state/handoffs/`
- `.cursor/rules/` múltiplos por módulo

---

## O time enxuto

```
┌─────────────────────────────────────────────────────────────┐
│                    Desenvolvedor solo                       │
│                                                             │
│  Sessão Claude Code                    (Cursor Agent,       │
│  ┌──────────────────────┐               classe D only)      │
│  │ Gerador              │              ┌──────────────┐     │
│  │ - Feature Contract   │              │ Infra via MCP│     │
│  │ - código + testes    │  brief D     │ - migrations │     │
│  │ - autonomia/pausa    │─────────────▶│ - deploy     │     │
│  │ - matriz de validação│              │ - env        │     │
│  └──────────────────────┘              │ - Rollback   │     │
│              │                          └──────────────┘     │
│              ▼                                               │
│         ┌─────────┐                                          │
│         │  CI     │ N1 / N2 / N3 (evaluator independente)    │
│         └─────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

- **Gerador:** Claude Code (Opus). Valida DoR, preenche Feature Contract (B/C/D), escreve código + testes, preenche matriz de validação, atualiza `TODO.md`.
- **Infra (opcional, classe D):** Cursor Agent + MCPs. Executa migrações/deploy/env com Rollback planejado.
- **Evaluator:** CI do GitHub Actions — níveis N1/N2/N3 conforme classe da feature.

---

## Processo — 5 passos

### PASSO 1 — Análise dos artefatos SDD

Leia na ordem:

1. `TODO.md` — ver features, classes A/B/C/D, DoR
2. `docs/contracts/CONTRACTS.md` + `packages/shared/types/` — contratos
3. `docs/specs/SPEC.md` — RFs, CAs, Anti-SPEC
4. `docs/plans/skills-manifest.md` (se existir)
5. `docs/plans/CURRENT_REALITY.md` (se projeto existente)

Extraia:
- Stack completa
- Quais features são classe C ou D (precisam de mais rigor)
- Quais features precisam de infra MCP (classe D)
- Dependências entre features

### PASSO 2 — Decidir se precisa de `PLAN.md` (ondas)

- **≤ 6 features** e dependências lineares → `TODO.md` ordenado basta.
- **> 6 features** ou dependências cruzadas → crie `docs/plans/PLAN.md` usando `assets/PLAN-template.md`. Organize em ondas por **feature**, não por task.

### PASSO 3 — Atualizar AGENTS.md para v3.1

Garanta que contém:

- 3 papéis (Gerador / Infra opcional / Avaliador).
- **Classificação A/B/C/D** (tabela §2).
- **CI por níveis** (N1/N2/N3).
- **Regras de arquivos editáveis sem permissão** (TODO, CONTRACTS, PLAN, ADR, cursor-brief, CURRENT_REALITY, matriz) e **proibidos sem autorização** (PRD, SPEC, Anti-SPEC).
- **Autonomia vs pausa** (§9).

Use `assets/AGENTS-template.md` como referência.

### PASSO 4 — Feature Contracts

Para cada feature classe **B, C, D** que ainda não tem Feature Contract:

- Classe B: bloco inline no TODO.md (use `templates/FEATURE-CONTRACT-template.md` como guia, versão enxuta).
- Classe C: bloco detalhado no TODO.md OU arquivo em `docs/plans/feature-contracts/F-NNN.md`.
- Classe D: arquivo dedicado em `docs/plans/feature-contracts/F-NNN.md` + seção em `cursor-brief.md` com **Rollback**.

Campos mínimos: objetivo, escopo incluído/excluído, arquivos permitidos/proibidos, contratos Zod, testes obrigatórios, Anti-SPEC relevante, matriz vazia, plano de rollback (só D).

### PASSO 5 — Gerar `cursor-brief.md` (só se há classe D)

**Só crie `docs/plans/cursor-brief.md` se houver features classe D com operação via MCP.**

Cada seção tem:
- Contexto (feature + arquivos Zod relevantes)
- Operação exata via MCP
- Critério de aceite (evidência objetiva)
- Variáveis de ambiente necessárias
- **Rollback (obrigatório para D)** — passos para reverter se falhar
- Staging antes de produção
- Smoke test pós-execução

Template em `assets/cursor-brief-template.md`.

---

## O Loop de Execução por Feature (v3.1)

```
1. LEITURA
   Ler TODO.md item + Feature Contract + SPEC.md + Anti-SPEC + packages/shared/types/.

2. CLASSIFICAÇÃO + DoR
   Confirmar A/B/C/D. Validar Definition of Ready. Incompleta → pausa.

3. FEATURE CONTRACT (B/C/D)
   Criar/validar. Campos: objetivo, escopo, arquivos permitidos/proibidos, contratos,
   testes, Anti-SPEC relevante, rollback (D), matriz vazia.

4. CONTRATOS
   Atualizar packages/shared/types/ primeiro. CONTRACTS.md espelha.

5. BRANCH
   feat/<slug> a partir de main.

6. TESTES PRIMEIRO
   Teste falhando por CA, conforme a matriz do contrato.

7. IMPLEMENTAÇÃO
   Só toca arquivos permitidos. Se sair da lista → pausa.

8. CI LOCAL (nível conforme classe)
   A/B: N1 · C: N2 · D: N3

9. INFRA (D)
   Gerar seção em cursor-brief.md com Rollback. Pausar até humano executar + staging.

10. MATRIZ DE VALIDAÇÃO
    Preencher CA → teste → tipo → status → evidência.

11. PR + MERGE
    B/C/D: PR com pr-description-template.md. CI verde no nível exigido.
    A trivial: merge direto em main possível.

12. ATUALIZA TODO.md
    Move para Concluído com SHA/PR. Registra bugs/ideias novas.
```

Tudo em **uma única sessão** do Claude Code.

---

## Prompts prontos (v3.1 · Validation Mode Patch)

**Fonte canônica:** `checklists/prompts-cheatsheet.md` (raiz do pacote). Abaixo, versão compacta para referência rápida. Em caso de divergência, o cheatsheet prevalece.

### Prompt 1 — Início de sessão (compacto)

```
[INÍCIO DE SESSÃO — HARNESS v3.1 · VALIDATION MODE]

Leia: TODO.md, AGENTS.md, SPEC.md relevante, Feature Contract ativo,
CURRENT_REALITY.md (se existir), DECISIONS_LOG.md (linhas da feature),
risk-classification.md, git status/log.

Responda: Fase · Feature em andamento · Classe · CI alvo · DoR · Feature Contract ·
Risco de reclassificação · Decisões relevantes · Bloqueios · Git · Próxima ação · Autonomia (SIM/NÃO + motivo).

Versão canônica completa: checklists/prompts-cheatsheet.md §1.
```

### Prompt 2 — Implementar feature (compacto)

```
[IMPLEMENTAR FEATURE — F-NNN · HARNESS v3.1 VALIDATION MODE]

Loop. ▲ = pausa · ■ = BLOQUEADO.

1. Leitura (TODO + Feature Contract + SPEC + Anti-SPEC + types + DECISIONS_LOG).
2. Classificação A/B/C/D + CI alvo + testes mínimos.
3. ■ DoR incompleta em domínio sensível → BLOQUEADO — DEFINITION OF READY INCOMPLETA.
4. Feature Contract criado/atualizado (B/C/D obrigatório).
5. Contratos: types primeiro, CONTRACTS.md depois.
6. Branch feat/<slug>.
7. Testes primeiro, respeitando mínimos por classe. Sem teste fake.
8. Implementar. ■ arquivo fora do contrato sem justificativa aceita → BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT.
9. Auto-reclassificação: se subir, ■ BLOQUEADO — RECLASSIFICAÇÃO PENDENTE até contrato atualizado.
10. CI local no nível da classe.
11. ▲ Infra (D) → cursor-brief com Rollback/Staging/Smoke → pausa até humano + staging.
12. Matriz de validação preenchida.
13. Decisão operacional → DECISIONS_LOG. Decisão de produto → PAUSE e peça autorização.
14. Docs: CONTRACTS/PLAN/ADR. NÃO editar PRD/SPEC/Anti-SPEC sem autorização.
15. PR/merge. A pode ir direto em main; B/C/D exigem PR + CI verde + matriz.

Versão canônica: checklists/prompts-cheatsheet.md §2.
```

### Prompt 3 — QA em Validation Mode (compacto)

```
[QA — VALIDATION MODE · HARNESS v3.1]

Você está em VALIDATION MODE. Assuma que implementação E testes podem estar errados.
Trabalho: TENTAR QUEBRAR antes de aprovar. Sem evidência, nunca APROVADO.

1. Ler artefatos (Feature Contract, TODO, SPEC/Anti-SPEC, DECISIONS_LOG, types, risk-classification).
2. git diff. Arquivos alterados vs permitidos.
3. DoR + DoD.
4. Auto-reclassificação — a feature deveria ser classe mais alta?
5. Contratos alinhados?
6. Anti-SPEC respeitada item a item?
7. Testes mínimos por classe (risk-classification.md).
8. Detectar teste fake (lista no risk-classification.md §Teste fake não conta).
9. Validation Mode — tente quebrar: inputs inválidos, ausência, permissões, idempotência,
   edge cases, UI vazio/loading/erro, fora de escopo alterado?
10. Matriz CA → teste → tipo → status → evidência.
11. CI local no nível da classe.
12. Produção (D): cursor-brief Rollback + staging + feature flag + smoke.
13. DECISIONS_LOG consultado se há comportamento aparentemente estranho.

Responda APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO com seções completas.

Critérios (ordem):
- DoR incompleta em domínio sensível            → BLOQUEADO
- Arquivo fora do contrato sem justificativa    → BLOQUEADO
- Anti-SPEC violada                              → BLOQUEADO
- Reclassificação pendente                       → BLOQUEADO
- Classe D sem rollback/staging                  → BLOQUEADO
- Teste mínimo por classe ausente                → MUDANÇAS_SOLICITADAS
- Teste fake detectado                           → MUDANÇAS_SOLICITADAS
- CI vermelho                                    → MUDANÇAS_SOLICITADAS
- CA sem evidência objetiva                      → MUDANÇAS_SOLICITADAS
- Validation Mode pulado em C/D                  → MUDANÇAS_SOLICITADAS

Versão canônica: checklists/prompts-cheatsheet.md §3.
```

---

## Regras desta skill

- **Um único gerador.** Sempre Claude Code. Cursor Agent só para classe D com MCP.
- **Feature é a unidade.** Nunca task atômica.
- **Classificação A/B/C/D é obrigatória.** Determina DoR, Feature Contract, CI alvo.
- **Matriz de validação é obrigatória em B/C/D.** Sem evidência → sem APROVADO.
- **TODO.md é o estado único.** Feature Contract vive inline por padrão; só vai para arquivo em `docs/plans/feature-contracts/` se extenso.
- **Classe D sempre pausa.** Antes de tocar produção, migration ou env.
- **Rollback é obrigatório em cursor-brief.** Sem ele, a tarefa não entra em staging.
- **Não duplique contratos.** Zod é fonte; `CONTRACTS.md` é espelho.

---

## Assets desta skill

- `assets/PLAN-template.md` — template de PLAN.md (ondas por feature)
- `assets/AGENTS-template.md` — template canônico de AGENTS.md v3.1
- `assets/cursor-brief-template.md` — template de brief por operação com Rollback
- `assets/pr-description-template.md` — template para corpo de PR

## Referências

- `references/wave-planning-guide.md` — como agrupar features em ondas
- `references/delivery-checklist.md` — checklist de entrega por feature
- `references/agent-roles.md` — papéis detalhados
