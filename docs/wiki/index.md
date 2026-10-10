# Wiki — estrategia-macro-ldc-dados

> **Mapa principal da Project Wiki.** Primeira leitura de qualquer agente (orquestrador Fable, subagentes
> Opus, sessão interativa) ao abrir o projeto.
>
> A wiki é a **memória sintetizada** do projeto. Não substitui ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR —
> referencia e resume. Mantida via `/wiki ingest`, `/wiki context`, `/wiki lint`, `/wiki repair`.

**Última revisão:** 2026-10-10
**Saúde da wiki:** verde (recém-criada no kickoff)

---

## O projeto em 3 linhas

Ferramenta interna de dados/quant da **LDC Capital**: pipeline Python que extrai e alinha 20 anos de séries
macroeconômicas brasileiras e de desempenho de ativos/subsetores em um dataset canônico **trimestral**, para
identificar **regimes macro** e medir como cada classe de ativo performou em momentos semelhantes.
Alimenta o **modelo de alocação macro doméstica + dimensionamento da alocação internacional**.
**Prazo:** Comitê de Alocação em **2026-10-14**. Roda local — sem auth, sem pagamento, sem deploy.

---

## Leitura inicial obrigatória

1. **este arquivo** (`docs/wiki/index.md`)
2. [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md) — **fonte de verdade do
   escopo**, imutável (e-mail do Alexandre Kaercher, out/2026)
3. [`TODO.md`](../../TODO.md) — estado vivo + Feature Contract do item ativo
4. [`AGENTS.md`](../../AGENTS.md) — papéis, classificação A/B/C/D, autonomia/pausa, Fast Fix

---

## Páginas vivas

| Página | O que tem | Quando ler |
|---|---|---|
| [overview.md](./overview.md) | O que o projeto entrega hoje em 1 página | toda nova sessão |
| [architecture.md](./architecture.md) | Arquitetura do pipeline (fontes → raw → processed → canonical → análise) | antes de mexer em módulo novo |
| [log.md](./log.md) | Histórico cronológico (ingests, releases, fixes, validações) | abertura de sessão; quando um número "parece estranho" |
| [modules/](./modules/) | Memória por área (`sgs`, `sidra`, `anbima`, `b3`, `canonical`, `regimes`) | antes de tocar o módulo |
| [features/](./features/) | Resumo de 1 parágrafo por feature mergeada (C/D) | ao consultar histórico de uma feature |
| [runbooks/](./runbooks/) | Reconstruir dataset, atualizar série, fonte fora do ar, fechar relatório do Comitê | em emergência ou operação repetida |
| [context/](./context/) | Context Packs temporários por tarefa ativa | início de feature/fix |

## Fontes externas de contexto (fora da wiki)

| Pasta | O que tem | Regra |
|---|---|---|
| [`docs/research/`](../research/) | Pesquisas de **fontes de dados e metodologia** — endpoints, formatos, limites, cobertura temporal, pegadinhas; **em andamento, escrito em paralelo por vários agentes** | leia antes de escrever extrator; **nunca apague nem sobrescreva** arquivo de outro agente |
| [`docs/product/`](../product/) | E-mail de escopo (imutável) + PRD | escopo se checa aqui |
| `data/` | Dados brutos/processados/canônicos — **não versionados**, reconstruíveis | nunca editar à mão |

---

## Atalhos por cenário

| Cenário | Comece por |
|---|---|
| **Número errado / série quebrada** | `/fast-fix` se A/B sem camada canônica → lê `wiki/runbooks/` + `log.md` |
| **Vários problemas para triar** | `/triage-bugs` (lista colada) → plano de ataque do dia |
| **Novo extrator de fonte** | `docs/research/` da fonte → `/wiki context F-NNN` → Prompt 2 (classe B) |
| **Mexer em schema canônico, alinhamento temporal ou cálculo de retorno** | **classe C** — pause, Feature Contract detalhado, diff numérico obrigatório |
| **Mandar resultado para o Alexandre/Comitê** | **classe D** — revisão humana + dataset congelado + linha no log |
| **Sondagem exploratória de uma fonte (notebook descartável)** | modo **MVP Lite** — não produz dado canônico |
| **Passar tarefa para outro subagente Opus** | `/wiki context <F-NNN>` antes de encerrar |
| **Projeto bagunçado / wiki contraditória** | `/wiki lint` → `/wiki repair` antes de codar |
| **Decisão grande** (DuckDB vs. Parquet, lib de HTTP) | ADR em `docs/decisions/adr/` (não wiki) |
| **Substituição de fonte / convenção de trimestre** | linha em `docs/plans/DECISIONS_LOG.md` (não wiki) |

---

## Fonte de verdade vs. wiki

A wiki **nunca** é fonte de verdade. Sintetiza. Quando há conflito, valem:

| Domínio | Fonte de verdade | Espelho na wiki |
|---|---|---|
| Escopo pedido | `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` | citado em `wiki/overview.md` |
| Produto | `docs/product/PRD.md` | `wiki/overview.md` |
| Comportamento + Anti-SPEC | `docs/specs/SPEC.md` | `wiki/architecture.md` (resumo) |
| Contratos de dados | `packages/shared/schemas/` (Pydantic + pandera) | `docs/contracts/CONTRACTS.md` (espelho legível) |
| Dados | o **script** que produz o dataset | `wiki/modules/<fonte>.md` |
| Decisão arquitetural | `docs/decisions/adr/ADR-NNN.md` | citada em `wiki/architecture.md` |
| Decisão operacional / troca de fonte | `docs/plans/DECISIONS_LOG.md` | linha em `wiki/log.md` |
| Estado vivo | `TODO.md` + `git log` | resumo em `wiki/log.md` |

---

## Saúde da wiki

A wiki é **viva mas pequena**. Sinais de que precisa de `/wiki lint`:

- `log.md` passou de 200 linhas sem revisão.
- Módulo em `modules/` cita fonte/endpoint que não existe mais.
- Runbook de reconstrução do dataset com data > 3 meses sem revisar.
- Context pack ativo sem feature correspondente em `TODO.md`.
- Decisão em `DECISIONS_LOG` que contradiz `architecture.md` (ex.: convenção de trimestre).
- Número citado na wiki que não bate com o dataset canônico atual.

---

*Esta wiki é mantida pela IA. O humano só dispara comandos. Se a wiki virar atrito, corte.*
