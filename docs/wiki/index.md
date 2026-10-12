# Wiki — estrategia-macro-ldc-dados

> **Mapa principal da Project Wiki** — primeira leitura de qualquer agente. A wiki é a **memória
> sintetizada**: não substitui ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR, referencia e resume.
> Mantida via `/wiki ingest · context · lint · repair`.

**Última revisão:** 2026-10-11, noite (**fechamento da frente LDC Analytics** — relatório executivo
+ `apps/web_export/` + módulo do portal + **D-ah..D-aj**; antes: fechamento final = F-027, F-031,
**D-ag**)
**Saúde da wiki:** verde — `modules/` com **11** páginas (`analysis.md` agora cobre figuras,
tabelas, **o caderno de F-027, o pacote de F-031 e a frente web**); `log.md` em **200** linhas, com
as 6 condensações das Ondas 1/2/3-parte-1 devolvidas ao arquivo (integrais lá, nada apagado) para
abrir espaço às 3 entradas novas; índice alinhado aos arquivos que existem

## O projeto em 3 linhas

Ferramenta interna de dados/quant da **LDC Capital**: pipeline Python que extrai e alinha 20 anos de séries
macro brasileiras e de desempenho de ativos/subsetores num dataset canônico **trimestral** (83 trimestres),
para identificar **regimes macro** e medir como cada classe de ativo performou em momentos semelhantes.
Alimenta o modelo de alocação macro doméstica + o dimensionamento da alocação internacional.
**Prazo:** Comitê de Alocação em **2026-10-14**. Roda local — sem auth, pagamento ou deploy.
**Estado (2026-10-11) — FECHAMENTO FINAL.** **O pacote mínimo está implementado de ponta a ponta** (`F-001`..`F-032`, menos F-020 e F-030, cortadas com justificativa escrita): Ondas 0-3 **aprovadas** em QA independente (**0 × P0** e **0 divergência numérica** em todas as reconstruções de classe C — `docs/plans/qa/`), Onda 4 implementada com o QA rodado e aplicado, e **F-027** (caderno de entrega) + **F-031** (pacote ao Comitê, classe D) implementadas e **aguardando QA independente**. **Um comando reconstrói tudo**, em 13 etapas, e `verify` confere: **48 artefatos**, 2 execuções byte-idênticas, `DATASET_SHA256 = fc2331183b9355e6…`. Entre eles: `raw_series` **278.439** linhas / **62** séries, catálogo de **138**, `alinhado_trimestral` **4.038**, `macro_quarterly` **83 × 42** nas **duas** materializações + as 2 procedências, `asset_returns_quarterly` **1.963 / 24 ativos**, `regimes_v1{,_asof}` **83 × 18**, `regime_neighbors_v3` **9.692 × 21**, as 3 tabelas `regime_asset_metrics*` (**120/96/120**), o internacional (**54** + **624**), 12 figuras, as 6 tabelas do Comitê e o HTML executado do caderno. **O pacote de entrega está montado, verificado e selado como não publicável:** 41 arquivos + `HASHES.txt`, 10,9 MB soltos / 3,7 MB no `.zip` com `sha256` idêntico em 3 montagens, XLSX de 8 abas, smoke de 93 checagens `rc 0`.

⛔ **E NÃO SAI.** `ADR-001` está em **`Proposta`** em disco ⇒ `especificacao_congelada = False` (CA-090) ⇒ **passo 2 dos 8 do gate reprovado** (`AGENTS.md §14`) ⇒ **nada vai ao Comitê — nem um número por WhatsApp** (Anti-SPEC §10.3.18). **Nada está em implementação; os próximos 10 passos são humanos**, tabulados em [`TODO.md §4`](../../TODO.md) ("O que só o Edu pode fazer"), com o roteiro de 30 minutos em [`docs/product/GUIA-REVISAO-EDU.md`](../product/GUIA-REVISAO-EDU.md). Decisões provisórias abertas: as 8 de Edu/Alexandre (inclusive **D1** e **D6**) + **D-a..D-aj** + **D-W1..D-W6** + **DW-1..DW-5** (as do portal). **Backlog pós-Comitê:** F-020, F-030, F-033..F-040 (1 linha cada em `TODO.md §2`).

**A frente LDC Analytics (2026-10-11, noite) — 3 entregas, nada instalado.** O mesmo dataset
congelado, apresentado de três formas novas: o **relatório executivo**
(`apps/analysis/entrega/relatorio_executivo.py` → um HTML de **776 KB** que abre no celular sem
servidor, sem rede e sem JavaScript), o **exportador web** (**F-W001**, `apps/web_export/` → `meta.json`
+ as **6** views + o `schema.d.ts` gerado + o `current.json`, contrato em
`packages/shared/schemas/web_views.py` e espelho em `CONTRACTS.md §10`) e o **módulo
`/admin/analytics-macro`** (`apps/web_export/modulo-site/`, 4 telas **prontas e NÃO instaladas** — o
repositório do site não foi tocado e o `next build` dele não foi rodado). Nada publica: o gate do
ADR-001 vale igual, e as 6 views nascem com `publicavel: false`. O que falta é humano — **`ADR-008`
em `Proposta`** e as decisões **DW-1..DW-5** do PRD, mais a de instalar, em `TODO.md §4`. A frente
**não mexeu em nenhuma célula de dado**: `DATASET_SHA256` segue `fc233118…` e o `verify` segue
`rc 0`, com **D-ah** tirando os entregáveis derivados de `entrega/` do manifesto. Detalhe em
`modules/analysis.md` ("A frente web") e em `TODO.md §1/§4/§6`.

⚠️ **Dois achados para o Comitê:** a V1 troca de rótulo entre `revised` e `asof` em **33,33%** dos trimestres comparáveis — acima dos 25% de CA-074 ⇒ **não é operacional na forma `asof`**; e em `3T2026` a **interseção dos top-5 das três lentes é VAZIA** (concordância V1 × V3 com mediana **0,111** em 61 referências). Ver `modules/regimes.md` e `modules/analysis.md`.

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
| [modules/](./modules/) | [`sgs`](./modules/sgs.md) · [`focus`](./modules/focus.md) · [`sidra`](./modules/sidra.md) · [`anbima`](./modules/anbima.md) · [`tesouro`](./modules/tesouro.md) · [`b3`](./modules/b3.md) · [`internacional`](./modules/internacional.md) (fontes **+ F-026**) · [`calendario`](./modules/calendario.md) · [`canonical`](./modules/canonical.md) (**+ o comando único e o `MANIFEST.json`**) · [`regimes`](./modules/regimes.md) · [**`analysis`**](./modules/analysis.md) (figuras, tabelas, **o caderno de F-027**, **o pacote de F-031**, **a frente web** = relatório executivo + `apps/web_export/` + o módulo do portal, determinismo, guarda de linguagem) | **antes de tocar o módulo** |
| [runbooks/](./runbooks/) | [reconstruir-dataset](./runbooks/reconstruir-dataset.md) · [fonte-fora-do-ar](./runbooks/fonte-fora-do-ar.md) · [**entrega-comite**](./runbooks/entrega-comite.md) (os 8 passos do gate classe D, o checklist de 19 caixas do Edu e o rollback de 7 passos) | emergência, operação repetida ou **entrega ao Comitê** |
| [features/](./features/) | resumo de 1 parágrafo por feature C/D mergeada | *(vazio — nenhuma C/D mergeada ainda; o permanente das 5 C da Onda 2 já foi para `modules/canonical.md`)* |
| [context/](./context/) | Context Packs temporários (**F-018..F-024, F-026, F-027, F-029, F-031, F-W001** — material da revisão numérica). Os de F-002..F-008, **F-010**, F-013..F-017 e, no fechamento final, **F-025 e F-028** (QA aprovado, sem P1 aberto) foram apagados, com o conteúdo permanente em `modules/` | início de feature/fix · **QA de classe C/D** |

## Fontes de verdade (fora da wiki)

| Domínio | Onde | Espelho na wiki |
|---|---|---|
| Escopo pedido | [`product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md) | citado em `overview.md` |
| Produto (52 RFs) | [`product/PRD.md`](../product/PRD.md) | `overview.md` |
| Produto do portal (RF-W001..W051) | [`product/LDC-ANALYTICS-PRD.md`](../product/LDC-ANALYTICS-PRD.md) · instalação do módulo em [`product/MODULO-ANALYTICS-MACRO.md`](../product/MODULO-ANALYTICS-MACRO.md) | `modules/analysis.md` |
| Comportamento + **Anti-SPEC §10** | [`specs/SPEC.md`](../specs/SPEC.md) | `architecture.md` §6 |
| Contratos de dados | [`packages/shared/schemas/`](../../packages/shared/schemas/) · espelho legível em [`contracts/CONTRACTS.md`](../contracts/CONTRACTS.md) | `modules/canonical.md` |
| Pesquisa de fontes e metodologia | [`research/`](../research/) — **vários agentes escrevem; nunca sobrescrever** | `modules/*.md` |
| Plano de execução (ondas) | [`plans/PLAN.md`](../plans/PLAN.md) | — |
| Risco A/B/C/D | [`plans/risk-classification.md`](../plans/risk-classification.md) | — |
| Capacidades, ambiente e conectividade medidos | [`plans/skills-manifest.md`](../plans/skills-manifest.md) | `runbooks/fonte-fora-do-ar.md` |
| Decisões arquiteturais | [`decisions/adr/`](../decisions/adr/) — **8 ADRs: ADR-001..006 e ADR-008 em Proposta, ADR-007 Aceita** | `architecture.md` §5 |
| Decisão operacional / **troca de fonte** | [`plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md) — 12 substituições + **D-a..D-h** (§2.1) + **D-i..D-q** (§2.3 partes 1-2) + **D-r..D-x** (parte 3) + **D-y..D-af** (parte 4, Onda 4) + **D-ag** (parte 5, fechamento final: o pacote de entrega fora do manifesto e o hash que vale) + **D-ah..D-aj e D-W1..D-W6** (parte 6, frente LDC Analytics: `entrega/` fora do manifesto, sem `cor_hex`, apresentação e eixo de cor declarados, e o contrato das views web). O que precisa do Edu está tabulado em `TODO.md §4` | linha em `log.md` |
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
| **Mandar resultado ao Alexandre/Comitê** | **classe D, e o gate está FECHADO** → [runbooks/entrega-comite.md](./runbooks/entrega-comite.md) + [`GUIA-REVISAO-EDU.md`](../product/GUIA-REVISAO-EDU.md). Com ADR-001 em `Proposta`, **nada sai** |
| **Passar tarefa a outro subagente** | `/wiki context <F-NNN>` antes de encerrar |
| **Decisão grande** (armazenamento, lente de regime) | ADR em [`decisions/adr/`](../decisions/adr/), não wiki |
| **Substituição de fonte / convenção de trimestre** | [`plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md), não wiki |

## Sinais de que a wiki precisa de `/wiki lint`

`log.md` passou de 200 linhas · módulo cita endpoint que não existe mais · runbook de reconstrução com mais de 3 meses sem revisar · context pack sem feature correspondente no `TODO.md` · decisão no `DECISIONS_LOG` que contradiz `architecture.md` · número citado na wiki que não bate com o canônico atual.

*Mantida pela IA; o humano só dispara comandos. Se a wiki virar atrito, corte.*
