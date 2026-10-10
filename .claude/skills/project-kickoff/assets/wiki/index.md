# Wiki — [Nome do Projeto]

> **Mapa principal da Project Wiki.** Primeira leitura de qualquer agente (Claude Code, Codex, Cursor) ao abrir o projeto.
>
> A wiki é a **memória sintetizada** do projeto. Não substitui PRD/SPEC/CONTRACTS/ADR — referencia e resume.
> Mantida pelo agente via `/wiki ingest`, `/wiki context`, `/wiki lint`, `/wiki repair`.

**Última revisão:** YYYY-MM-DD
**Saúde da wiki:** [verde | amarelo — ver `/wiki lint` | vermelho]

---

## Páginas vivas

| Página | O que tem | Quando ler |
|---|---|---|
| [overview.md](./overview.md) | O que o projeto entrega hoje em 1 página | toda nova sessão |
| [architecture.md](./architecture.md) | Arquitetura técnica viva (stack + módulos + fronteiras) | antes de mexer em módulo novo |
| [log.md](./log.md) | Histórico cronológico (ingests, releases, bug fixes, validações) | abertura de sessão; quando algo "parece estranho" |
| [modules/](./modules/) | Memória por área técnica (auth, db, frontend, payments, deploy) | antes de tocar o módulo |
| [features/](./features/) | Resumo de 1 parágrafo por feature mergeada | ao consultar histórico de uma feature |
| [runbooks/](./runbooks/) | Passos para deploy, rollback, smoke, bug recorrente, env setup | em emergência ou operação repetida |
| [context/](./context/) | Context Packs temporários por tarefa ativa | início de feature/fix |

---

## Atalhos por cenário

| Cenário | Comece por |
|---|---|
| **Bug urgente em produção** | `/fast-fix` → lê `wiki/runbooks/` + `wiki/log.md` recente |
| **Vários bugs do cliente para triar** | `/triage-bugs` (lista colada) → plano de ataque do dia |
| **Nova feature** | `/wiki context F-NNN` → cria pack em `wiki/context/F-NNN.md` → Prompt 2 |
| **MVP / validação de ideia (< 1 semana, sem produção)** | modo **MVP Lite** — só TODO.md + classe + commit + teste no caminho crítico |
| **Continuar tarefa em outro agente (Codex/Cursor)** | abrir `wiki/index.md` + `wiki/context/<tarefa-ativa>.md` |
| **Projeto bagunçado / em produção sem docs** | `/wiki lint` → `/wiki repair` antes de codar |
| **Decisão grande** | ADR em `docs/decisions/adr/` (não wiki) |
| **Decisão operacional pequena** | linha em `docs/plans/DECISIONS_LOG.md` (não wiki) |

---

## Fonte de verdade vs. wiki

A wiki **nunca** é fonte de verdade. Sintetiza. Quando há conflito, valem:

| Domínio | Fonte de verdade | Espelho na wiki |
|---|---|---|
| Produto | `docs/product/PRD.md` | `wiki/overview.md` |
| Comportamento + Anti-SPEC | `docs/specs/SPEC.md` | `wiki/architecture.md` (resumo) |
| Contratos | `packages/shared/types/` (Zod) | `docs/contracts/CONTRACTS.md` (espelho legível) |
| Decisão arquitetural | `docs/decisions/adr/ADR-NNN.md` | citada em `wiki/architecture.md` |
| Decisão operacional | `docs/plans/DECISIONS_LOG.md` | linha em `wiki/log.md` quando relevante |
| Estado vivo | `TODO.md` + `git log` | resumo em `wiki/log.md` |

---

## Saúde da wiki

A wiki é **viva mas pequena**. Sinais de que precisa de `/wiki lint`:

- `log.md` passou de 200 linhas sem revisão.
- Módulo em `modules/` cita arquivo que não existe mais.
- Runbook com data > 6 meses sem revisar.
- Context pack ativo sem feature correspondente em `TODO.md`.
- Decisão em `DECISIONS_LOG` que contradiz `architecture.md`.

---

*Esta wiki é mantida pela IA. O dev solo só dispara comandos. Se a wiki virar atrito, corte.*
