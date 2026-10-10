# Log — [Nome do Projeto]

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

- `INGEST` — fonte bruta processada (print, log, transcript, resposta de outro agente)
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

- [YYYY-MM-DD HH:MM] [WIKI] wiki inicial criada via `/project-kickoff` — ref: commit `<sha>`

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
