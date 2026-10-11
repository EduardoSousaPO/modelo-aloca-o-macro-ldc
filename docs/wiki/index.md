# Wiki — estrategia-macro-ldc-dados

> **Mapa principal da Project Wiki** — primeira leitura de qualquer agente. A wiki é a **memória
> sintetizada**: não substitui ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR, referencia e resume.
> Mantida via `/wiki ingest · context · lint · repair`.

**Última revisão:** 2026-10-11 (fechamento da **Onda 4** — F-022..F-026, F-028, F-029; antes:
Onda 3 parte 1 = F-018/F-019/F-021)
**Saúde da wiki:** verde — `modules/` com **11** páginas (`analysis.md` **nova**: figuras, tabelas,
determinismo e a guarda de linguagem); `log.md` em **197** linhas, com o bloco da Onda 3 arquivado
em `log-archive-2026-10.md`; índice alinhado aos arquivos que existem

## O projeto em 3 linhas

Ferramenta interna de dados/quant da **LDC Capital**: pipeline Python que extrai e alinha 20 anos de séries
macro brasileiras e de desempenho de ativos/subsetores num dataset canônico **trimestral** (83 trimestres),
para identificar **regimes macro** e medir como cada classe de ativo performou em momentos semelhantes.
Alimenta o modelo de alocação macro doméstica + o dimensionamento da alocação internacional.
**Prazo:** Comitê de Alocação em **2026-10-14**. Roda local — sem auth, pagamento ou deploy.
**Estado (2026-10-11):** **Ondas 0 a 3 completas e aprovadas** no QA independente (F-001, F-009, os 7 extratores, as 6 features da camada canônica e as 3 lentes de regime — `docs/plans/qa/`, **0 × P0** e **0 divergência numérica** nas reconstruções independentes) e **Onda 4 IMPLEMENTADA, QA rodado com mudanças já aplicadas**: **F-022** (métricas regime × ativo), **F-023** (heatmap), **F-024** (ranking + concordância), **F-025** (timeline), **F-026** (internacional + risk-off), **F-028** (limitações) e **F-029** (orquestrador `python -m apps.pipeline`). **Um comando reconstrói tudo**, em 13 etapas, e `verify` confere: **47 artefatos determinísticos**, 2 execuções byte-idênticas, `DATASET_SHA256 = fc2331183b9355e6…`. Entre eles: `raw_series` **278.439** linhas / **62** séries, catálogo de **138**, `alinhado_trimestral` **4.038**, `macro_quarterly` **83 × 42** nas **duas** materializações + as 2 procedências, `asset_returns_quarterly` **1.963 / 24 ativos**, `regimes_v1{,_asof}` **83 × 18**, `regime_neighbors_v3` **9.692 × 21**, as 3 tabelas `regime_asset_metrics*` (**120/96/120**), o internacional (**54** + **624**), 12 figuras e as 6 tabelas do Comitê. **O que falta:** **F-027** (notebook de entrega, em curso) e **F-031** (pacote ao Comitê, **classe D** — exige ADR-001/002/003 **Aceitos** e revisão humana registrada); **F-020** (V2) e **F-030** foram **cortadas da v1**. Decisões provisórias abertas: as 8 de Edu/Alexandre (gate de **publicação**, inclusive **D1** e **D6**) + **D-a..D-af**. ⚠️ **Dois achados para o Comitê:** a V1 troca de rótulo entre `revised` e `asof` em **33,33%** dos trimestres comparáveis — acima dos 25% de CA-074 ⇒ **não é operacional na forma `asof`**; e em `3T2026` a **interseção dos top-5 das três lentes é VAZIA** (concordância V1 × V3 com mediana **0,111** em 61 referências). Ver `modules/regimes.md` e `modules/analysis.md`.

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
| [modules/](./modules/) | [`sgs`](./modules/sgs.md) · [`focus`](./modules/focus.md) · [`sidra`](./modules/sidra.md) · [`anbima`](./modules/anbima.md) · [`tesouro`](./modules/tesouro.md) · [`b3`](./modules/b3.md) · [`internacional`](./modules/internacional.md) (fontes **+ F-026**) · [`calendario`](./modules/calendario.md) · [`canonical`](./modules/canonical.md) (**+ o comando único e o `MANIFEST.json`**) · [`regimes`](./modules/regimes.md) · [**`analysis`**](./modules/analysis.md) (**nova** — figuras, tabelas, determinismo, guarda de linguagem) | **antes de tocar o módulo** |
| [runbooks/](./runbooks/) | [reconstruir-dataset](./runbooks/reconstruir-dataset.md) · [fonte-fora-do-ar](./runbooks/fonte-fora-do-ar.md) | emergência ou operação repetida |
| [features/](./features/) | resumo de 1 parágrafo por feature C/D mergeada | *(vazio — nenhuma C/D mergeada ainda; o permanente das 5 C da Onda 2 já foi para `modules/canonical.md` e os packs de F-013..F-017 foram apagados)* |
| [context/](./context/) | Context Packs temporários (**F-018..F-026, F-028, F-029** — material da revisão numérica de classe C). Os de F-002..F-008, **F-010** e F-013..F-017 foram apagados nos fechamentos, com o conteúdo permanente em `modules/` | início de feature/fix · **QA de classe C** |

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
