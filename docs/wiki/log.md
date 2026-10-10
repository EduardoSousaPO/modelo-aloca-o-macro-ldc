# Log — estrategia-macro-ldc-dados

> **Histórico cronológico vivo.** Complementa `git log` (que é granular demais) e `DECISIONS_LOG.md` (que é só decisão).
>
> **Aqui entra:** ingest de fontes brutas, releases, bug fixes notáveis, validações de produção, mudanças de escopo, marcos.
> **Aqui NÃO entra:** o "porquê" de cada decisão (vai para `DECISIONS_LOG.md` ou ADR).
>
> **Quem escreve:** o agente em todo `/wiki ingest` e ao fim de feature/fast-fix relevante.
> **Quem lê:** todo agente no início de sessão; e ao tentar entender comportamento estranho.
>
> **Tamanho-alvo:** ≤ 200 linhas. Se passar, rode `/wiki repair` para arquivar entradas antigas em `wiki/log-archive-YYYY-MM.md`.

---

## Formato

Uma linha por evento. Frase curta com data ISO, tipo, contexto, link com fonte (PR / ADR / arquivo / F-NNN).

```
- [YYYY-MM-DD HH:MM] [TIPO] descrição curta — ref: F-NNN / PR #NN / commit / fonte bruta
```

**Tipos válidos** (use para grep):

- `KICKOFF` — criação/estruturação inicial do projeto
- `INGEST` — fonte bruta processada (print, log, transcript, resposta de outro agente)
- `SOURCE` — nova fonte de dados mapeada, extrator criado ou fonte substituída (ref: DECISIONS_LOG)
- `DATASET` — dataset canônico reconstruído / congelado (com hash + intervalo de datas)
- `RELEASE` — versão liberada (com SHA + ambiente)
- `BUGFIX` — bug corrigido (com gravidade + classe)
- `RUNBOOK` — runbook criado/atualizado
- `DECISION` — referência a entrada nova no DECISIONS_LOG ou ADR
- `RECLASSIFY` — feature mudou de classe durante execução
- `BLOQUEADO` — agente retornou BLOQUEADO; resolvido em… 
- `VALIDATION` — validação de produção (smoke, staging, migration)
- `WIKI` — manutenção da própria wiki (lint, repair, mover página)

---

## 2026 — entradas atuais

> Entradas mais novas no topo.

2026-10-10 | PRD | docs/product/PRD.md v1 gerado em modo autônomo a partir do e-mail + research; 8 decisões pendentes
2026-10-10 | KICKOFF | estrutura Harness v3.2 criada; e-mail de escopo arquivado

- [2026-10-10] [INGEST] PRD v1.0 gerado em **modo autônomo** por `/consultor-prd` (sem discovery humano): 52 RFs, 10 RNFs, 15 premissas marcadas `[PREMISSA]`, 8 riscos priorizados; **8 decisões bloqueiam implementação** (D1, D3, D5, D6, D12, L1, L2, L4) e foram registradas em `TODO.md §4` — ref: `docs/product/PRD.md`, `docs/research/fontes-de-dados.md`, `docs/research/metodologia-regimes-macro.md`
- [2026-10-10] [WIKI] `wiki/overview.md` reescrito para refletir o PRD v1.0 (síntese, sem duplicar) — ref: `docs/wiki/overview.md`
- [2026-10-10] [KICKOFF] estrutura Harness v3.2 criada e adaptada a projeto de dados/quant (AGENTS/CLAUDE/TODO/README/CI Python, `apps/pipeline` + `apps/analysis`, `packages/shared/schemas`, `data/raw|processed|canonical`) — ref: `docs/wiki/index.md`, `AGENTS.md`
- [2026-10-10] [INGEST] e-mail de escopo do Alexandre Kaercher transcrito e arquivado como fonte de verdade imutável — ref: `docs/product/ESCOPO-EMAIL-ALEXANDRE.md`
- [2026-10-10] [WIKI] wiki inicial populada (index, overview) — pesquisa de fontes em andamento em `docs/research/` por agentes paralelos — ref: `docs/wiki/overview.md`

---

## Entradas anteriores

*(vazio)*

---

## Regras

1. **Uma linha por evento.** Se precisa de parágrafo, vira ADR ou runbook.
2. **Sempre com referência verificável.** Sem ref, não é log — é opinião.
3. **Nunca apague entradas com ref a PR/ADR.** Se ficou irrelevante, mova para `log-archive-YYYY-MM.md`.
4. **Não duplique DECISIONS_LOG aqui.** Linka para a linha lá (`ref: DECISIONS_LOG L42`).
5. **`/wiki ingest` cria a entrada automaticamente** — não escreva manualmente se vai usar a skill.

---

*Este arquivo é o `git log` humano. Curto, indexável, confiável.*
