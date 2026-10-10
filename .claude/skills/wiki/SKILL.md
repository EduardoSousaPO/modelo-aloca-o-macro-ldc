---
name: wiki
description: >
  Mantém a Project Wiki (docs/wiki/) — camada de memória sintetizada entre as fontes brutas do projeto e o agente. Modos: ingest | context | lint | repair. Use SEMPRE que o usuário disser: "atualiza a wiki", "ingest este log/print/erro/transcrição", "gera context pack para feature X", "auditar wiki", "wiki está bagunçada", "wiki tem contradição", "wiki incompleta", "criar runbook", "fechar wiki", "atualizar log", "atualizar overview", ou ao iniciar/encerrar sessão de uma feature B/C/D. Também ative se o usuário pedir continuidade entre Claude/Codex/Cursor.
---

# /wiki — Harness v3.2 · Project Wiki

Você ativou a skill **wiki**. Esta skill mantém `docs/wiki/` viva: índice, log cronológico, overview, architecture, módulos, features (resumos), runbooks, context packs.

A wiki é **memória sintetizada**, NUNCA fonte de verdade. Para cada operação, valide contra as fontes:

| Domínio | Fonte de verdade |
|---|---|
| Produto | `docs/product/PRD.md` |
| Comportamento + Anti-SPEC | `docs/specs/SPEC.md` |
| Contratos | `packages/shared/types/` |
| Decisões arquiteturais | `docs/decisions/adr/` |
| Decisões operacionais | `docs/plans/DECISIONS_LOG.md` |
| Estado vivo | `TODO.md` + `git log` |

---

## Modos

A skill aceita um modo como argumento: `/wiki <modo> [contexto adicional]`.

| Modo | Quando usar | Saída |
|---|---|---|
| **ingest** | quando o usuário traz uma fonte bruta (print, log, erro, resposta de outro agente, escopo, decisão) | atualiza páginas relevantes + linha em `wiki/log.md` com tipo `INGEST` |
| **context** | antes de iniciar feature/fix significativo; ou para passar tarefa para outro agente | cria/atualiza `wiki/context/<F-NNN-slug>.md` |
| **lint** | início de projeto bagunçado, antes de refactor grande, antes de produção, ou quando algo "parece estranho" | relatório curto com contradições, páginas órfãs, lacunas, runbooks faltando |
| **repair** | depois de um lint, para aplicar correções da wiki | edita páginas + arquiva `log.md` se >200 linhas |

Se o usuário não especificou o modo, **pergunte uma vez** qual aplicar antes de agir.

---

## Modo INGEST

**Entrada:** uma fonte bruta colada pelo usuário. Pode ser:
- Print de erro / stacktrace.
- Log de build/CI.
- Trecho de resposta de Cursor/Codex.
- Decisão verbal ("a partir de agora vamos usar X").
- Escopo solto ("preciso adicionar Y").
- Output de validação manual.

**Processo:**

1. Identifique o **tipo** da fonte (erro, log, decisão, escopo, transcript, validação).
2. Identifique o **destino certo** na wiki:
   - Erro/bug recorrente → criar/atualizar `wiki/runbooks/bug-<slug>.md`.
   - Decisão arquitetural com trade-off → propor ADR (NÃO criar sozinho — pause).
   - Decisão operacional que volta ao debate → linha em `docs/plans/DECISIONS_LOG.md`.
   - Mudança de produto → pause: PRD/SPEC só com autorização humana.
   - Mudança técnica em módulo → atualizar `wiki/modules/<mod>.md`.
   - Validação executada → linha em `wiki/log.md` tipo `VALIDATION`.
   - Resposta de outro agente que muda contexto → atualizar `wiki/context/<F-NNN>.md` se há tarefa ativa.
3. **Sempre** crie linha em `wiki/log.md` com formato:
   ```
   - [YYYY-MM-DD HH:MM] [INGEST] <tipo da fonte> — <onde foi processado> — ref: <link/PR/ADR/F-NNN>
   ```
4. Se o ingest gerar conflito com algo existente na wiki, **pause** e relate o conflito antes de gravar.
5. Se a fonte sugerir mudança de PRD/SPEC/Anti-SPEC, **pause** e peça autorização.

**Saída:** lista do que foi atualizado + linha de log + perguntas pendentes.

---

## Modo CONTEXT

**Entrada:** ID/nome da feature ou tarefa (ex.: `F-007`, `bug-jwt-logout`, `migration-supabase-0018`).

**Processo:**

1. Leia `TODO.md` e localize a feature/tarefa.
2. Leia `docs/specs/SPEC.md` nas seções dos RFs cobertos.
3. Leia Feature Contract (inline ou em `docs/plans/feature-contracts/`).
4. Leia `wiki/modules/<modulo>.md` se houver módulo afetado.
5. Leia `docs/plans/DECISIONS_LOG.md` por menções ao domínio.
6. Leia `wiki/log.md` últimos eventos relacionados.
7. Crie ou atualize `wiki/context/<F-NNN-slug>.md` usando `templates/wiki/context-pack-template.md`.
8. Preencha campos obrigatórios:
   - Objetivo, motivação, estado atual, arquivos relevantes, restrições, próximos passos, decisões abertas, handoff.
9. Acrescente linha em `wiki/log.md`:
   ```
   - [YYYY-MM-DD HH:MM] [WIKI] context pack criado/atualizado para <F-NNN> — ref: TODO.md
   ```

**Saída:** caminho do context pack + resumo de 3-5 linhas. O usuário pode colar isto direto em outro agente.

---

## Modo LINT

**Entrada:** nada (varredura completa) ou alvo específico (`/wiki lint runbooks`, `/wiki lint modules`).

**Processo (somente leitura — não altera nada):**

1. **Páginas órfãs:** arquivos em `docs/wiki/**` que `index.md` não referencia.
2. **Páginas inalcançáveis:** referenciadas em `index.md` mas inexistentes.
3. **Contradições explícitas:** procure pares como (overview vs PRD), (architecture vs SPEC), (modules vs código real). Use `git ls-files` ou Glob para confirmar arquivos citados existem.
4. **Decisões conflitantes:** entradas em `DECISIONS_LOG` que invalidem outra entrada antiga sem cancelamento explícito.
5. **Runbooks faltando:** bugs em `TODO.md §5` com gravidade alta sem runbook correspondente em `wiki/runbooks/`.
6. **Features sem documentação:** features mergeadas (em `TODO.md §3 Concluído`) sem resumo em `wiki/features/F-NNN.md` (apenas para classe C/D — B é opcional).
7. **`log.md` inchado:** se passou de 200 linhas, marcar para arquivamento.
8. **Context packs órfãos:** arquivos em `wiki/context/` cuja feature já foi mergeada (TODO §3) ou abandonada.

**Saída:** relatório enxuto neste formato:

```
WIKI LINT — YYYY-MM-DD

SAÚDE: [verde | amarelo | vermelho]

ÓRFÃS: <lista ou "nenhuma">
INALCANÇÁVEIS: <lista>
CONTRADIÇÕES: <lista — sempre com fonte>
DECISÕES CONFLITANTES: <lista>
RUNBOOKS FALTANDO: <lista de bugs>
FEATURES C/D SEM RESUMO: <lista>
LOG > 200 LINHAS: [sim/não]
CONTEXT PACKS ÓRFÃOS: <lista>

RECOMENDAÇÃO: rodar `/wiki repair` | seguro continuar | exige humano para X
```

**Lint nunca altera arquivos.** Só relata.

---

## Modo REPAIR

**Entrada:** tipicamente roda depois de lint. Aceita `/wiki repair` (tudo) ou `/wiki repair <categoria>`.

**Processo:**

1. **Para cada item do lint, decida:**
   - **Pode auto-corrigir** (página órfã: adicionar ao index; runbook faltante: criar com template; log inchado: mover entradas anteriores ao mês corrente para `wiki/log-archive-YYYY-MM.md`; context pack órfão: deletar).
   - **Precisa de humano** (contradição entre wiki e SPEC; decisão conflitante entre ADRs; mudança de PRD/Anti-SPEC).
2. **Pause antes de:**
   - Apagar runbook (mesmo desatualizado).
   - Editar overview/architecture quando o conflito é com PRD/SPEC.
   - Apagar entradas antigas do `log.md` com ref a PR/ADR (só arquive, nunca delete).
3. **Sempre** registre cada operação em `wiki/log.md` tipo `WIKI`:
   ```
   - [YYYY-MM-DD HH:MM] [WIKI] repair: <ação> — <detalhe> — ref: lint YYYY-MM-DD
   ```

**Saída:** lista do que foi alterado + lista do que requer humano + nova rodada de lint sugerida.

---

## Regras gerais (todos os modos)

- **A wiki é viva, não burocrática.** Se uma página cresce demais, divida ou arquive. Tamanho-alvo:
  - `index.md` ≤ 80 linhas.
  - `log.md` ≤ 200 linhas.
  - `overview.md` / `architecture.md` ≤ 150 linhas cada.
  - `modules/<mod>.md` ≤ 200 linhas.
  - `runbooks/<slug>.md` ≤ 150 linhas.
  - `context/<F-NNN>.md` ≤ 150 linhas e descartável.
- **Nunca duplique conteúdo entre wiki e docs/.** Wiki sintetiza e linka.
- **Nunca altere PRD/SPEC/Anti-SPEC.** Se o ingest sugerir mudança, pause.
- **Nunca crie ADR sozinho.** Proponha ADR e pause para humano confirmar.
- **Sempre tipo + ref** em entradas de `log.md`.
- **Sempre verifique** que arquivos citados existem (`Glob` ou `git ls-files`) antes de afirmar que algo é órfão.

---

## Quando NÃO usar `/wiki`

- Para registrar bug aberto → vai em `TODO.md §5`.
- Para escrever Feature Contract → bloco inline no `TODO.md` ou `docs/plans/feature-contracts/`.
- Para registrar decisão arquitetural com trade-off → ADR.
- Para escrever PRD/SPEC → use `/consultor-prd` ou `/SDD-avancado`.
- Para urgência absoluta com bug em produção → use `/fast-fix`.

---

## Assets

- Templates da wiki em `templates/wiki/` (raiz do pacote Harness): `index.md`, `log.md`, `overview-template.md`, `architecture-template.md`, `runbook-template.md`, `context-pack-template.md`.

## Referências

- `references/wiki-flows.md` — fluxos detalhados de cada modo, com exemplos.
