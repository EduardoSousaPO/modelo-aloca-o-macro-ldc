# Feature Contract — F-NNN [Nome da feature]

> Contrato operacional da feature. Obrigatório para classes **B, C, D**. Opcional para **A**.
>
> **Onde vive:** preferencialmente como bloco dentro do próprio item no `TODO.md`. Só extraia para `docs/plans/feature-contracts/F-NNN.md` se o bloco passar de ~40 linhas (típico em C e D).
>
> **Quando criar:** antes da primeira linha de código. Gerado pelo agente no Prompt 2 quando ainda não existe.
>
> **Quem atualiza:** o agente ao longo da implementação, se o escopo mudar — mas mudança de escopo exige **pausa** e confirmação humana.

---

## Identificação

- **ID:** F-NNN
- **Nome:** [curto]
- **Risco:** [A | B | C | D]  — ver `risk-classification.md`
- **Cobre:** RF-NNN, RF-NNN (referência ao `SPEC.md`)
- **Branch proposta:** `feat/<slug>`
- **Data:** YYYY-MM-DD

---

## Objetivo

[1–3 frases. O que esta feature entrega e para quem.]

---

## Definition of Ready (DoR)

> Marque todos antes de começar a implementar. Se algum está em branco → **pausa**, resolva antes.

- [ ] Há RFs ou justificativa clara para a feature.
- [ ] Critérios de aceite explícitos (lista abaixo).
- [ ] Escopo **incluído** descrito (o que será feito).
- [ ] Escopo **excluído** descrito (o que não será feito).
- [ ] Classificação de risco A/B/C/D confirmada.
- [ ] Arquivos prováveis de alteração listados.
- [ ] Testes esperados listados (unit / integration / e2e / smoke).
- [ ] Contratos `pydantic` + `pandera` necessários identificados (ou decisão explícita de que não precisa).
- [ ] Fontes externas identificadas, com **fixture gravada** em `tests/fixtures/`.
- [ ] Impacto na **camada canônica** avaliado (altera schema, alinhamento temporal ou cálculo de retorno? → classe C).
- [ ] Impacto em **publicação** avaliado (número sai para o Comitê? exige dataset congelado + Rollback em `docs/plans/infra-ops.md`? → classe D).

---

## Critérios de aceite

- **CA-NNN:** [Given/When/Then ou prosa curta e testável]
- **CA-NNN:** ...

---

## Escopo incluído

- [bullet concreto: "extrator do BCB SGS gravando IPCA, Selic e CDI em `data/raw/sgs/`, validado por pandera"]
- ...

## Escopo excluído (não será feito nesta feature)

- [bullet concreto: "Não agrega para trimestral nem entra no canônico — fica para F-014"]
- ...

---

## Arquivos

### Arquivos que podem ser alterados

- `apps/pipeline/extract/sgs.py`
- `apps/pipeline/transform/alinhamento.py`
- `packages/shared/schemas/series_catalog.py` (**acréscimo** de campo; alteração de schema existente = pausa)
- `tests/unit/test_sgs.py` · `tests/fixtures/sgs/ipca.json`

### Arquivos que NÃO podem ser alterados

- `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` (imutável)
- `docs/specs/SPEC.md` (sem autorização humana), inclusive a **Anti-SPEC §10**
- `docs/product/PRD.md`
- `docs/research/*` (arquivos de outros agentes)
- Arquivos fora do escopo listado acima

> **Regra v3.1 Validation Mode Patch:** qualquer alteração fora da lista "podem ser alterados" resulta em `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT` no QA, exceto se o agente apresentar **justificativa aceita** com 7 itens (arquivo, motivo, impacto, escopo, contrato, testes, reclassificação — ver `AGENTS.md §18`).
>
> Se a justificativa toca **produto, camada canônica, credencial/fonte paga ou entregável do Comitê**, o agente pausa e pede confirmação humana. Nunca prossegue automaticamente.

---

## Contratos

- [ ] Contratos já existem em `packages/shared/schemas/` — **sim**, especificamente: `ExtractorConfig` (pydantic), `RawSeriesSchema` (pandera).
- [ ] Contratos a **criar/atualizar**: [lista]
- [ ] `CONTRACTS.md` precisa ser atualizado? **[sim/não]** — justifique.

---

## Testes obrigatórios

> Mapear **antes** de implementar. Se não há teste proposto para um CA, o CA não está pronto.
>
> **Mínimos por classe** (fonte única em `risk-classification.md §Testes mínimos`):
>
> - **A:** teste opcional se a mudança é realmente isolada; senão vira B.
> - **B:** ≥1 teste por CA (unit ou integration).
> - **C:** ≥1 teste por CA crítico + ≥1 edge case + ≥1 teste negativo + integration/contract obrigatório sobre fixture + **diff numérico** vs. o canônico anterior + reconstrução completa.
> - **D:** integration quando aplicável + **smoke do pacote** + **dataset congelado** (versão + hash) + Rollback em `docs/plans/infra-ops.md` + duas execuções com o mesmo hash + e2e/manual evidenciado.
>
> Testes "fake" (`assert True`, teste que só confirma que a função rodou, teste que mocka a regra sob validação, `len(df) > 0` sem contagem esperada) **não contam** — o Prompt 3 rejeita.

| Teste | Tipo | Cobre CA | Arquivo |
|---|---|---|---|
| `extrator devolve as 5 séries com o shape esperado` | unit sobre fixture | CA-001 | `tests/unit/test_sgs.py` |
| `HTTP 200 com corpo de erro levanta e não grava` | unit negativo | CA-002 | idem |
| `valor-canário confere (CDI 2006 = 15,0271%)` | contract | CA-003 | `tests/contract/test_valores_canario.py` |
| `trimestre que termina em feriado usa o último dia útil` | unit edge case | CA-004 | `tests/unit/test_alinhamento.py` |
| `pipeline do zero duas vezes gera o mesmo hash` | e2e (classe C/D) | CA-005 | `tests/e2e/test_reprodutibilidade.py` |

---

## Comandos obrigatórios (CI local)

**Nível CI alvo:** [N1 | N2 | N3] — derivado da classe de risco.

- `ruff check .`
- `ruff format --check .`
- `pytest tests/unit`
- `pytest tests/integration tests/contract`   *(a partir de N2)*
- `pytest tests/e2e -m "not network"`         *(a partir de N3)*
- build do canônico do zero (`python -m pipeline.build_canonical`)  *(a partir de N2)*

---

## Dados / Publicação (só para classes C e D)

- **Altera schema do canônico?** [sim/não] — se sim: qual tabela e quais colunas; o espelho `docs/contracts/CONTRACTS.md` precisa ser atualizado.
- **Exige reconstrução completa de `data/canonical/`?** [sim/não] — para classe C, sempre sim.
- **Diff numérico vs. a versão anterior anexado?** [sim/não] — cada divergência explicada, não só "melhorou".
- **Usa credencial ou fonte paga?** [sim/não] — se sim, **classe D** e seção própria em `docs/plans/infra-ops.md`.
- **Número sai para o Alexandre/Comitê?** [sim/não] — se sim: **dataset congelado** (versão + hash) + revisão humana + linha em `docs/wiki/log.md`.
- **Revisão numérica independente feita por quem?** [subagente/humano — nunca quem calculou]
- **Rollback plan (≤5 linhas, obrigatório em D — espelhado em `docs/plans/infra-ops.md`):**
  1. [passo]
  2. [passo]

---

## Evidência esperada (Matriz de Validação)

> Preencher o status durante o Prompt 3 — QA do PR. Se algum CA não tem evidência objetiva, resultado é **MUDANÇAS_SOLICITADAS**.

| CA | Teste | Tipo | Status | Evidência (comando/arquivo/log) |
|---|---|---|---|---|
| CA-001 | `test_sgs.py::test_shape` | unit | [passou/falhou/não coberto] | `pytest tests/unit/test_sgs.py` log + nº de linhas e `min`/`max` de data |
| CA-002 | idem | unit negativo | — | — |
| CA-003 | `test_valores_canario.py` | contract | — | 3 valores conferidos na fonte (print/link) |

---

## Anti-SPEC — checagem específica

Para classes C e D, o agente **lista explicitamente** quais itens da Anti-SPEC (`SPEC.md §10`) são mais relevantes para esta feature, e confirma no QA que nenhum foi violado.

- [ ] NÃO inventar, interpolar ou estimar dado para fechar série (§10.1.1).
- [ ] NÃO misturar dado real e sintético sem coluna de origem (§10.1.2).
- [ ] NÃO aceitar HTTP 200 sem validar shape (§10.1.5); NÃO usar fonte paga no caminho crítico (§10.3.14).
- [ ] [item específico desta feature]

---

## Gate de autonomia

O agente pode prosseguir automaticamente enquanto:
- Os arquivos alterados estão na lista "podem ser alterados".
- Os CAs sendo implementados são os descritos acima.
- Os testes estão passando localmente.
- Não foi detectada mudança em PRD/SPEC/Anti-SPEC.
- A classe não precisou subir (ver auto-reclassificação em `AGENTS.md §16`).

O agente **deve pausar** se:
- Precisar alterar arquivo fora da lista permitida **e** a alteração toca produto/camada canônica/credencial/entregável do Comitê (se for operacional sem risco, aplica-se o fluxo de justificativa — `AGENTS.md §18`).
- Um CA novo surgir (mudança de escopo).
- Encontrar conflito entre código existente e SPEC.
- Classe estimada era A/B e precisa subir para C/D (reclassifique primeiro).
- Qualquer publicação de número ou uso de credencial (classe D).

O agente **deve retornar BLOQUEADO** se:
- DoR está incompleta e a lacuna toca domínio sensível → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`.
- Arquivo alterado fora da lista sem justificativa aceita → `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT`.
- Reclassificação foi identificada mas o contrato ainda não foi atualizado → `BLOQUEADO — RECLASSIFICAÇÃO PENDENTE`.
- Anti-SPEC violada → `BLOQUEADO — ANTI-SPEC VIOLADA`.

---

## Resultado final

- **Status:** [em andamento | concluído | bloqueado]
- **PR:** [#NNN](link)
- **SHA:** [hash]
- **Data de merge:** YYYY-MM-DD
- **Evidência consolidada:** ver matriz acima + log do CI.

---

*Este contrato é a fonte de verdade da feature. Se o código diverge do contrato, ou o contrato diverge da realidade, corrija o contrato (ou o código) — nunca ignore a divergência.*
