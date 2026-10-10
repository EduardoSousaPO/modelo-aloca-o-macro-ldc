# Wiki — estrategia-macro-ldc-dados

> **Mapa principal da Project Wiki** — primeira leitura de qualquer agente. A wiki é a **memória
> sintetizada**: não substitui ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR, referencia e resume.
> Mantida via `/wiki ingest · context · lint · repair`.

**Última revisão:** 2026-10-10 (housekeeping + `/wiki lint` → `repair`)
**Saúde da wiki:** verde — `modules/` e `runbooks/` populados; índice alinhado aos arquivos que existem

## O projeto em 3 linhas

Ferramenta interna de dados/quant da **LDC Capital**: pipeline Python que extrai e alinha 20 anos de séries
macro brasileiras e de desempenho de ativos/subsetores num dataset canônico **trimestral** (83 trimestres),
para identificar **regimes macro** e medir como cada classe de ativo performou em momentos semelhantes.
Alimenta o modelo de alocação macro doméstica + o dimensionamento da alocação internacional.
**Prazo:** Comitê de Alocação em **2026-10-14**. Roda local — sem auth, pagamento ou deploy.
**Estado:** harness estruturado; **nenhum extrator implementado**; 8 decisões bloqueantes abertas.

## Leitura inicial obrigatória

1. **este arquivo** · 2. [`ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md) — **fonte de
verdade do escopo, imutável** · 3. [`TODO.md`](../../TODO.md) — estado vivo + Feature Contract do item
ativo · 4. [`AGENTS.md`](../../AGENTS.md) — papéis, A/B/C/D, autonomia/pausa, Fast Fix

## Páginas da wiki

| Página | O que tem | Quando ler |
|---|---|---|
| [overview.md](./overview.md) | o que o projeto entrega hoje, em 1 página | toda nova sessão |
| [architecture.md](./architecture.md) | topologia fontes → raw → processed → canonical → análise | antes de mexer em módulo |
| [log.md](./log.md) | histórico cronológico (≤ 200 linhas) | abertura de sessão; quando um número "parece estranho" |
| [modules/](./modules/) | [`sgs`](./modules/sgs.md) · [`sidra`](./modules/sidra.md) · [`anbima`](./modules/anbima.md) · [`b3`](./modules/b3.md) · [`internacional`](./modules/internacional.md) · [`canonical`](./modules/canonical.md) · [`regimes`](./modules/regimes.md) | **antes de tocar o módulo** |
| [runbooks/](./runbooks/) | [reconstruir-dataset](./runbooks/reconstruir-dataset.md) · [fonte-fora-do-ar](./runbooks/fonte-fora-do-ar.md) | emergência ou operação repetida |
| [features/](./features/) | resumo de 1 parágrafo por feature C/D mergeada | *(vazio — nenhuma C/D mergeada)* |
| [context/](./context/) | Context Packs temporários por tarefa ativa | início de feature/fix |

## Fontes de verdade (fora da wiki)

| Domínio | Onde | Espelho na wiki |
|---|---|---|
| Escopo pedido | [`product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md) | citado em `overview.md` |
| Produto (52 RFs) | [`product/PRD.md`](../product/PRD.md) | `overview.md` |
| Comportamento + **Anti-SPEC §10** | [`specs/SPEC.md`](../specs/SPEC.md) | `architecture.md` §6 |
| Contratos de dados | [`packages/shared/schemas/`](../../packages/shared/schemas/) · espelho legível em [`contracts/CONTRACTS.md`](../contracts/CONTRACTS.md) | `modules/canonical.md` |
| Pesquisa de fontes e metodologia | [`research/`](../research/) — **vários agentes escrevem; nunca sobrescrever** | `modules/*.md` |
| Plano de execução (ondas) | [`plans/PLAN.md`](../plans/PLAN.md) | — |
| Risco A/B/C/D | [`plans/risk-classification.md`](../plans/risk-classification.md) | — |
| Capacidades, ambiente e conectividade medidos | [`plans/skills-manifest.md`](../plans/skills-manifest.md) | `runbooks/fonte-fora-do-ar.md` |
| Decisões arquiteturais | [`decisions/adr/`](../decisions/adr/) — **ADR-001..006, todos em Proposta** | `architecture.md` §5 |
| Decisão operacional / **troca de fonte** | [`plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md) — 12 substituições provisórias | linha em `log.md` |
| Prompts do dia a dia | [`plans/prompts-cheatsheet.md`](../plans/prompts-cheatsheet.md) | — |
| Rollback / operação | [`plans/infra-ops.md`](../plans/infra-ops.md) | `runbooks/reconstruir-dataset.md` §6 |
| Checklists (daily-ops, feature-PR) | [`plans/checklists/`](../plans/checklists/) | — |
| Estado vivo | [`TODO.md`](../../TODO.md) + `git log` | resumo em `log.md` |
| Dados | `data/` — **não versionado**, reconstruível; a verdade é o **script** | `modules/canonical.md` |

> `plans/prompts-cheatsheet.md`, `plans/infra-ops.md` e `plans/checklists/` (`daily-ops.md`,
> `feature-pr.md`) vieram do `/agents-protocol` em 2026-10-10 — todos existentes e linkados acima.

## Atalhos por cenário

| Cenário | Comece por |
|---|---|
| **Número errado / série quebrada** | `/fast-fix` se A/B sem camada canônica → [runbooks/](./runbooks/) + `log.md` |
| **Fonte não responde, ou responde lixo com HTTP 200** | [runbooks/fonte-fora-do-ar.md](./runbooks/fonte-fora-do-ar.md) |
| **Regenerar `data/canonical/`** | [runbooks/reconstruir-dataset.md](./runbooks/reconstruir-dataset.md) |
| **Novo extrator de fonte** | `modules/<fonte>.md` → `research/` da fonte → `/wiki context F-NNN` |
| **Schema canônico, alinhamento temporal ou cálculo de retorno** | **classe C** — pause, Feature Contract, diff numérico |
| **Mandar resultado ao Alexandre/Comitê** | **classe D** — revisão humana + dataset congelado + linha no log |
| **Passar tarefa a outro subagente** | `/wiki context <F-NNN>` antes de encerrar |
| **Decisão grande** (armazenamento, lente de regime) | ADR em [`decisions/adr/`](../decisions/adr/), não wiki |
| **Substituição de fonte / convenção de trimestre** | [`plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md), não wiki |

## Sinais de que a wiki precisa de `/wiki lint`

`log.md` passou de 200 linhas · módulo cita endpoint que não existe mais · runbook de reconstrução com mais de 3 meses sem revisar · context pack sem feature correspondente no `TODO.md` · decisão no `DECISIONS_LOG` que contradiz `architecture.md` · número citado na wiki que não bate com o canônico atual.

*Mantida pela IA; o humano só dispara comandos. Se a wiki virar atrito, corte.*
