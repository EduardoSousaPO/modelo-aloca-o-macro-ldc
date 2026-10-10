# Checklist por feature / PR — estrategia-macro-ldc-dados

> Rigor por classe A/B/C/D (`AGENTS.md §2`). DoD em `TODO.md §7`, prompts em `prompts-cheatsheet.md`.
> Bug urgente A/B que não toca canônico/credencial/Comitê: `/fast-fix`.

## Antes de começar (Feed Forward)

- [ ] Li **nesta ordem**: `wiki/index.md` → `ESCOPO-EMAIL-ALEXANDRE.md` → **F-NNN** no `TODO.md` (+ `§2.0`)
      → `AGENTS.md` → **só os CAs do item** na `SPEC.md` + **Anti-SPEC §10** → `CONTRACTS.md` +
      `schemas/` → **a seção da fonte** em `research/fontes-de-dados.md` → `wiki/context/`.
- [ ] Classe confirmada (`risk-classification.md §"Exemplos concretos deste projeto"`) + risco de
      reclassificação. Item do e-mail (A1..C1) identificado — fora do e-mail, **pausa**.
- [ ] **DoR completa**; incompleta em domínio sensível → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`.
      Schemas existem; campo novo **acrescentado antes** (alterar existente = pausa, classe C própria).
      **Fixture gravada** em `tests/fixtures/<fonte>/` com caminho de erro; branch criada.

## Durante a implementação

- [ ] Teste falhando por CA **antes** do código; nenhum teste fake de dados (`len(df) > 0` sem contagem
      mínima, mock com valor inventado, comparação com a própria fórmula, tolerância larga demais).
- [ ] Só os arquivos permitidos; fora da lista → justificativa de 7 itens (`AGENTS.md §18`) ou
      `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT`. Em onda: **não** editei `TODO.md`, `PLAN.md`,
      `wiki/log.md`, `CONTRACTS.md` — devolvi o texto no relatório.
- [ ] Encoding explícito, número pt-BR pelo normalizador único, datas ISO-8601, trimestre = fim de período,
      coluna de origem presente. Nada inventado/interpolado/estimado → `FONTE INDISPONÍVEL`. Decisão
      operacional → `DECISIONS_LOG.md`; arquitetural → ADR; produto/escopo → pausa.

## Antes do PR — por classe

- [ ] **A** — N1 verde (`ruff check` + `ruff format --check` + `pytest tests/unit -m "not network"`) ·
      teste cobre o CA (alterou valor de output? virou **B**).
- [ ] **B** (+A) — Feature Contract + matriz `CA | teste | tipo | status | evidência` · ≥ 1 teste por CA,
      1 negativo de fonte (HTTP 200 com corpo de erro) e 1 de idempotência · **as 5 evidências de dados**
      (`AGENTS.md §5`): log do pytest, nº de linhas + `min`/`max`, % de nulos nas colunas críticas,
      **3 valores conferidos na fonte** · `CONTRACTS.md` se os schemas mudaram · linha em `wiki/log.md`.
- [ ] **C** (+B) — CI **N2** verde (integration + contract/pandera + build do canônico por fixtures) ·
      **reconstrução completa de `data/canonical/` do zero** · **diff numérico vs. a versão anterior, cada
      divergência explicada** · casos-armadilha (feriado, 31/12 em fim de semana, série que começa depois
      de 2006, revisão retroativa, idempotência por hash) · Anti-SPEC §10 item por item · **revisão
      numérica independente** · ADR/`DECISIONS_LOG` se houve decisão ou troca de fonte · revisão humana.
- [ ] **D** (+C) — CI **N3** verde (e2e + 2 execuções → mesmo `sha256`) · **ADR-001 aceito** (em
      `Proposta` → `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA`) · os **8 passos do gate** de
      `AGENTS.md §14`, na ordem · seção em `infra-ops.md` com **Rollback** · dataset congelado (versão +
      hash) + tag git · smoke test do pacote (`infra-ops.md §1.5`) · substituições de fonte anexadas ·
      revisão humana do número · nenhuma credencial no repo.

## No PR e após o merge

- [ ] Título Conventional Commits referenciando o item (`feat(sgs): extrator IPCA/Selic (F-003)`); matriz
      + 5 evidências no corpo; CI verde no nível da classe; nenhum `data/raw`, `*.parquet`, `*.duckdb` ou
      `.env` no diff; **Prompt 3** por subagente **distinto** do que implementou.
- [ ] Pós-merge: `TODO.md` → Concluído com SHA · branch deletada · onda fechada no `PLAN.md`? · linha
      `[RELEASE]`/`[BUGFIX]` em `wiki/log.md` · C/D: `wiki/features/F-NNN.md` · `wiki/modules/<fonte>.md`
      atualizado · Context Pack deletado.

**Pare e repense se:** PR > 800 linhas ou teste cobrindo > 1 CA · classe B passou a agregar para
trimestral, mexer em calendário, calcular retorno, deflacionar, ou foi "só um ajustinho" no `ffill`/limiar
de ΔSelic/`k` da V3 → **C** · pediram "me manda só esse número do heatmap" → **D** · CI vermelho e pensou
em `.skip`/`xfail` → arrume (ou ADR) · editar `ESCOPO-EMAIL`/`PRD`/`SPEC`/Anti-SPEC → confirme com o
humano. Gatilhos completos de reclassificação: `AGENTS.md §16`.
