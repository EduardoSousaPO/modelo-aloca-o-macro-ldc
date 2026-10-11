# Wiki — estrategia-macro-ldc-dados

> **Mapa principal da Project Wiki** — primeira leitura de qualquer agente. A wiki é a **memória
> sintetizada**: não substitui ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR, referencia e resume.
> Mantida via `/wiki ingest · context · lint · repair`.

**Última revisão:** 2026-10-11 (fechamento da **Onda 3, parte 1** — antes: Onda 2 completa, parte 1:
F-013/F-014/F-016; parte 2: F-015/F-017/F-010)
**Saúde da wiki:** verde — `modules/` populado (**10** páginas, `focus.md` nova); `log.md` em 200
linhas (no teto, condensado nesta passada); índice alinhado aos arquivos que existem

## O projeto em 3 linhas

Ferramenta interna de dados/quant da **LDC Capital**: pipeline Python que extrai e alinha 20 anos de séries
macro brasileiras e de desempenho de ativos/subsetores num dataset canônico **trimestral** (83 trimestres),
para identificar **regimes macro** e medir como cada classe de ativo performou em momentos semelhantes.
Alimenta o modelo de alocação macro doméstica + o dimensionamento da alocação internacional.
**Prazo:** Comitê de Alocação em **2026-10-14**. Roda local — sem auth, pagamento ou deploy.
**Estado (2026-10-11):** **Ondas 0, 1 e 2 completas e aprovadas** no QA independente (F-001, F-009, os 7 extratores F-002..F-008 e as 6 features da camada canônica F-013..F-017 + F-010 — `docs/plans/qa/`, **0 × P0**) e **Onda 3 parte 1 IMPLEMENTADA, QA pendente**: **F-018** (materialização `asof`), **F-019** (regimes V1) e **F-021** (regimes V3). `data/canonical/` tem **20** artefatos: `raw_series` **278.439** linhas / **62** séries, catálogo de **138** séries, `alinhado_trimestral` **4.038**, **`macro_quarterly` 83 × 42** nas **duas** materializações (`revised` e `asof`) + as 2 procedências (**2.548** e **2.552**), **`asset_returns_quarterly` 1.963 / 24 ativos**, **`regimes_v1{,_asof}` 83 × 18** e **`regime_neighbors_v3` 9.692 × 21**. **Próximo: F-022** (métricas regime × ativo + a junção em `RegimesSchema`) **e a Onda 4** (F-020 V2, F-023 heatmap, F-024 ranking, F-028 limitações). Decisões provisórias abertas: as 8 de Edu/Alexandre (gate de **publicação**) + **D-a..D-x**. ⚠️ **Achado para o Comitê:** a V1 troca de rótulo entre `revised` e `asof` em **33,33%** dos trimestres comparáveis — acima dos 25% de CA-074 ⇒ **não é operacional na forma `asof`** (ver `modules/regimes.md`).

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
| [modules/](./modules/) | [`sgs`](./modules/sgs.md) · [`focus`](./modules/focus.md) · [`sidra`](./modules/sidra.md) · [`anbima`](./modules/anbima.md) · [`tesouro`](./modules/tesouro.md) · [`b3`](./modules/b3.md) · [`internacional`](./modules/internacional.md) · [`calendario`](./modules/calendario.md) · [`canonical`](./modules/canonical.md) · [`regimes`](./modules/regimes.md) | **antes de tocar o módulo** |
| [runbooks/](./runbooks/) | [reconstruir-dataset](./runbooks/reconstruir-dataset.md) · [fonte-fora-do-ar](./runbooks/fonte-fora-do-ar.md) | emergência ou operação repetida |
| [features/](./features/) | resumo de 1 parágrafo por feature C/D mergeada | *(vazio — nenhuma C/D mergeada ainda; o permanente das 5 C da Onda 2 já foi para `modules/canonical.md` e os packs de F-013..F-017 foram apagados)* |
| [context/](./context/) | Context Packs temporários (**F-013, F-014, F-015, F-016, F-017** — material da revisão numérica de classe C). Os de F-002..F-008 e **F-010** foram apagados no fechamento, com o conteúdo permanente em `modules/` | início de feature/fix · **QA de classe C** |

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
| Decisões arquiteturais | [`decisions/adr/`](../decisions/adr/) — **7 ADRs: ADR-001..006 em Proposta, ADR-007 Aceita** | `architecture.md` §5 |
| Decisão operacional / **troca de fonte** | [`plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md) — 12 substituições + **8 convenções da Onda 1** (§2.1) + a **Onda 2** (§2.3 partes 1-2: D-i, D-j, **D-k..D-q**) + a **Onda 3 parte 1** (§2.3 parte 3: **D-r..D-x**, com **D-s/D-t/D-u** aguardando o Edu e **D-q(e) superada por D-s**); o que precisa do Edu está tabulado em `TODO.md §4` | linha em `log.md` |
| Prompts do dia a dia | [`plans/prompts-cheatsheet.md`](../plans/prompts-cheatsheet.md) | — |
| Rollback / operação | [`plans/infra-ops.md`](../plans/infra-ops.md) | `runbooks/reconstruir-dataset.md` §6 |
| Checklists (daily-ops, feature-PR) | [`plans/checklists/`](../plans/checklists/) | — |
| Estado vivo | [`TODO.md`](../../TODO.md) + `git log` | resumo em `log.md` (≤ 200 linhas; o histórico integral de 2026-10-10 e das Ondas 0/1/2 está em [`log-archive-2026-10.md`](./log-archive-2026-10.md)) |
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
