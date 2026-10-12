# Log — estrategia-macro-ldc-dados

> **Histórico cronológico vivo.** Complementa `git log` (granular demais) e `DECISIONS_LOG.md` (só decisão).
> **Aqui entra:** ingest de fonte bruta, release, bugfix notável, validação/QA, mudança de escopo, marco.
> **Aqui NÃO entra:** o "porquê" de cada decisão (vai para `DECISIONS_LOG.md` ou ADR).
> **Quem escreve:** o agente em todo `/wiki ingest` e ao fim de feature/fast-fix relevante.
> **Quem lê:** todo agente no início de sessão, e ao tentar entender comportamento estranho.
> **Tamanho-alvo:** ≤ 200 linhas. Se passar, `/wiki repair` condensa ou arquiva as mais antigas.

---

## Formato

`- [YYYY-MM-DD] [TIPO] descrição curta — ref: F-NNN / PR / commit / fonte`. **Tipos** (para grep):
`KICKOFF` · `INGEST` · `SOURCE` · `DATASET` (canônico reconstruído, com hash e intervalo) ·
`RELEASE` · `BUGFIX` · `RUNBOOK` · `DECISION` (aponta para o `DECISIONS_LOG`/ADR) · `RECLASSIFY` ·
`BLOQUEADO` · `VALIDATION` · `WIKI` · `HOUSEKEEPING` · `HARNESS` · `SDD`/`PRD` · `IMPLEMENTADO`.

---

## 2026 — entradas atuais

> Entradas mais novas no topo.

- [2026-10-11] [RELEASE] **Relatório executivo do Comitê — um HTML que abre no celular, sem
  servidor e sem JavaScript** em `apps/analysis/entrega/relatorio_executivo.py` (2.225 linhas, 60
  testes) → `data/canonical/entrega/RELATORIO-ALEXANDRE-2026-10-14.html`, **775.932 bytes**, 11
  seções, abas em `input[type=radio]` + CSS, acordeão `<details>`, as 2 figuras **inline** em SVG e
  folha A4. Todo número cita uma das 6 fontes `relatorio_*.json`; **toda célula de desempenho
  carrega o seu `n`**; a guarda de linguagem roda **dentro** do gerador e a montagem **falha** se um
  texto reprovar; nada `publicavel: false` é nomeado (D-af). Gate lido do ADR em disco ⇒ abre com
  **"MATERIAL DE DISCUSSÃO"**. Determinístico. Gerado **depois** do `freeze`, o que exigiu **D-ah**
  — ref: `TODO.md §1`, `DECISIONS_LOG §2.3` (D-ah), `modules/analysis.md`

- [2026-10-11] [RELEASE] **F-W001 — `apps/web_export/`, a ponte do dataset congelado para o
  portal** (4 módulos + `packages/shared/schemas/web_views.py`; **44** testes de unidade + **17** de
  contrato). Um comando lê `data/canonical/`, **aplica o gate** e escreve `<tag>/meta.json` + as **6
  views** + `schema.d.ts` **gerado** dos modelos pydantic + `current.json` **no pai, por último** (é
  o que dá rollback por um arquivo). Tag `dev-2026-10-11`: **367.184 / 400.000 bytes** de views, 2
  exportações **byte-idênticas**. 4 travas recusam a exportação (artefato `publicavel: false`,
  artefato proibido, hash divergente, gate sem o ADR) e `n < 5` sai **com o valor e com a flag**.
  Espelho em **`CONTRACTS.md §10`**; `data/web/*` no `.gitignore`. **QA pendente** — ref:
  `TODO.md §1`, `CONTRACTS.md §10`, `ADR-008`, `DECISIONS_LOG §2.3` (D-ai, D-aj, D-W1..D-W6)

- [2026-10-11] [RELEASE] **Módulo `/admin/analytics-macro` — 4 telas prontas para colar, e NÃO
  INSTALADAS** em `apps/web_export/modulo-site/` (23 arquivos; guia em
  `docs/product/MODULO-ANALYTICS-MACRO.md`). T-01 (as 3 respostas de regime, nenhuma escolhida),
  T-02 (heatmap com `n` **dentro** de toda célula), T-03 (momentos semelhantes) e T-07 (dados e
  limitações). Server Components, dataset **fora de `public/`** atrás de `checkAdminAuth()`, SVG
  próprio sem dependência nova, filtro na URL. **O `site-ldc` não foi tocado** — nem branch, nem
  `npm install`, nem build; `tsc --strict` 0 erros e 51 testes `vitest` na rodada do autor, com o
  **`next build` em aberto**. Instalar é copiar a árvore + 3 mudanças fora dela: **classe D**, com
  **P2** (`app_metadata`) e **P3** (`ADR-008`) antes — ref: `TODO.md §1/§4/§6`,
  `MODULO-ANALYTICS-MACRO.md`

- [2026-10-11] [STATE] **Pipeline completo até F-031; gate fechado; aguardando Edu.** O pacote
  mínimo está **implementado de ponta a ponta** — extração → canônico → regimes → métricas →
  figuras e tabelas → limitações → orquestrador de um comando → caderno → **pacote de entrega**. **O
  pacote está montado, verificado e selado como não publicável, e não sai:** `ADR-001` em
  **`Proposta`** ⇒ `especificacao_congelada = False` (CA-090) ⇒ **passo 2 dos 8 do gate reprovado**.
  **Nada em implementação; os próximos 10 passos são humanos**, tabulados em `TODO.md §4` ("O que só
  o Edu pode fazer"), com roteiro de 30 min em `GUIA-REVISAO-EDU.md`. **QA independente pendente:**
  F-027, F-031 e as 3 entregas da frente LDC Analytics. **Backlog pós-Comitê:** F-020, F-030,
  F-033..F-040 — ref: `TODO.md §1/§4`, `runbooks/entrega-comite.md`, `AGENTS.md §14`

- [2026-10-11] [RELEASE] **F-031 — pacote de entrega ao Comitê (classe D), montado e BLOQUEADO** em
  `apps/analysis/entrega/montar_pacote.py` (55 testes, 43 sintéticos + 12 de acervo) + o runbook do
  gate (`runbooks/entrega-comite.md`: 8 passos, checklist de **19** caixas, rollback de 7 passos).
  **41 arquivos + `HASHES.txt`**, 10.881.236 bytes soltos, `.zip` de 3.722.460 bytes com `sha256`
  **idêntico em 3 montagens** (CA-121), XLSX de **8 abas** em pt-BR e **zero fórmula**, smoke de
  **93 checagens — 86 `OK`, 0 `FALHA`, 7 `INFO`, `rc 0`**. O selo do gate é **lido do ADR em disco**
  com falha fechada: aceitar o ADR-001 derruba o selo do README, do XLSX e do `HASHES.txt` com
  **zero linha de código**. Parquet entra por **cópia byte a byte** e `internacional_pesos.parquet`
  fica **fora** por leitura do campo `publicavel` (**D-af**), não por nome. **`D-ag` no mesmo
  fechamento:** `inventariar()` ignora `entrega/pacote_comite_` ⇒ `verify` com o pacote em disco
  volta a **`VERIFY OK`**, agregado `fc233118…` inalterado — ref: `TODO.md §2` F-031,
  `DECISIONS_LOG §2.3` (D-ag)

- [2026-10-11] [RELEASE] **F-027 — caderno de entrega do Comitê, sem uma linha de cálculo** em
  `apps/analysis/notebooks/entrega_comite_2026-10-14.ipynb` (**34 células**, 11 seções, 45.644
  bytes, outputs limpos, LF) + `README.md` da pasta + `tests/unit/test_notebook_entrega.py` (**35
  testes**). A regra de `AGENTS §19` aqui é **executável**: teste de AST reprova `def`/`lambda`/
  `class`, **todo** operador aritmético (`Path / "x"` inclusive — o caminho sai de
  `caminho_canonical`) e **29** métodos de agregação do pandas; percentual é
  `Styler.format({"media": pct})`, não `valor * 100`. **Nenhum número está digitado:** todos saem de
  arquivo em execução, o selo de "não publicável" inclusive. `nbconvert` em cópia: **19/19** células
  com saída, **0** erros, HTML de ~2,0 MiB; **3 gerações → mesmo `sha256`** (`id` explícito por
  célula) — ref: `TODO.md §2` F-027, `modules/analysis.md`, RF-041 (CA-110, CA-111)

- [2026-10-11] [DATASET] **`data/canonical/` reconstruído com UM comando, 2 execuções
  byte-idênticas, `verify` rc 0.** `python -m apps.pipeline run --offline` duas vezes seguidas →
  **47 artefatos determinísticos** com o mesmo `sha256` e `MANIFEST.json` byte-idêntico;
  `verify` → **48 conferidos, VERIFY OK, rc 0** (1 `INFO` do `ldc.duckdb`, fora do agregado por
  **D-ad (b)**).
  **`DATASET_SHA256 = fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`.**
  Os 13 passos passaram a incluir `internacional` e `tabelas`, que **faltavam** — antes "um comando"
  entregava ~2/3 do canônico com `rc = 0` (P1-2 do QA da Onda 4). Quase todo hash
  mudou **sem que uma célula de dado mudasse** (`versao_build` hasheia o conjunto de módulos, e este
  fechamento editou 2 schemas + 2 módulos canônicos + os 3 da análise); contraprova: `raw_series` e
  `series_catalog`, sem coluna de versão, saíram **byte-idênticos**. Canários idênticos aos do QA:
  V1 19/19/16/13 + 16 · `rho = 0,25987390740181016` · `INDX` em T+1 `= 0,05043012628905601` · ciclo
  Selic 34/23/26 · `corr(USDBRL, IBOV)` em `RECUPERACAO` `= −0,7974364631220996` · stress em
  **20 de 83** — ref: `TODO.md §1`, `MANIFEST.json`, `runbooks/reconstruir-dataset.md`

- [2026-10-11] [VALIDATION] **Os dois QAs independentes — Onda 3 e Onda 4 — fechados: 0 × P0, 0
  divergência numérica, 8 × P1 todos de declaração ou de orquestração.** Onda 3
  (`qa/ONDA-3-QA.md`): reconstrução **por fora** de 5 colunas × 83 × 2 materializações, 83 × 2
  rótulos, `rho` + 16 distâncias e 24 médias — **0 divergências**. Onda 4 (`qa/ONDA-4-QA.md`):
  **120 células × 17 métricas** com `max abs dif = 0,0` (`1,1e-16` em `beta_ibov`), `stress_flag`
  refeito do zero com **lista idêntica**, variância mínima por **Ledoit-Wolf com laço explícito +
  grade + KKT à mão** (dif **0,0**) e identidade de moeda com resíduo **2,2e-16**. Os 8 P1 eram de
  declaração ou de orquestração — **todos aplicados** (D-y, D-z, D-ab, D-ac, D-af) — ref:
  `docs/plans/qa/ONDA-{3,4}-QA.md`, `TODO.md §4`

- [2026-10-11] [DECISION] **D-y..D-aj + D-W1..D-W6** em `DECISIONS_LOG §2.3` (partes 4, 5 e 6 — as
  9 da frente LDC Analytics estão na parte 6). **Aguardam Edu:** **D-aa (c)** (qual lente abre a
  página = D1) e a ratificação de **D6** (ADR-003). **Aceitas pelo orquestrador:** **D-y** (os 5 P1
  da Onda 3, inclusive **a correção de fato de D-t: `2024Q3` é ALTA, não corte**), **D-z**
  (renomeação da vista + `SP500_USD` fora do heatmap + guarda de linguagem unificada), **D-ab**
  (D6-a..d), **D-ac** (não-nulidade em 5 colunas `bool`), **D-ad** (as 7 de F-029), **D-ae**
  (dívidas numa lista única), **D-af** (`publicavel` no manifesto), **D-ag**/**D-ah** (entregável
  derivado fora do manifesto; o hash que vale é o de `MANIFEST.json`), **D-ai** (sem `cor_hex`) e
  **D-aj** (apresentação e eixo de cor declarados) — ref: `DECISIONS_LOG §2.3`, `TODO.md §4/§6`

- [2026-10-11] [RELEASE] **F-029 — orquestrador "um comando" + idempotência e hash** em
  `apps/pipeline/run.py` (+ `__main__.py`, 44 testes unit e 6 e2e). `run` (13 etapas, `--offline`
  sem rede), `verify` (recalcula todo `sha256` contra o `MANIFEST.json`, `rc != 0` se divergir) e
  `freeze --tag` (**sem executar git**). Nada lê o relógio: `data_do_dado` vem dos relatórios, e é
  isso que faz o manifesto sair byte-idêntico. Ganhou 2 etapas (P1-2), deixou de **estourar
  traceback** em Parquet ilegível (P1-1), marca artefato **não publicável** (**D-af**) e, em
  **D-ag**/**D-ah**, ignora os entregáveis derivados de `entrega/` — ref: F-029, `modules/canonical.md`

- [2026-10-11] [RELEASE] **F-028 — página de limitações do Comitê** em
  `docs/product/LIMITACOES-COMITE.md` (**8 blocos, 249 linhas**) + `test_limitacoes_documento.py`
  (30 testes, com uma seção que **reabre os `relatorio_*.json` e exige a string na página** — número
  que muda derruba o teste, de propósito). **QA APROVADO** — ref: `TODO.md §2` F-028, RF-042/CA-112

- [2026-10-11] [RELEASE] **F-026 — alocação internacional + regra de risk-off** em
  `apps/pipeline/canonical/internacional.py` + `packages/shared/schemas/internacional.py` (2 schemas
  **novos**, 112 testes). Fecha o item **C1** do e-mail e resolve o bloqueio de `stress_flag`: a
  regra de **D6-a** marca **20 de 83** trimestres (14 não avaliáveis, nomeados). O achado central:
  `corr(USDBRL, IBOV)` é **−0,795** no stress contra **−0,418** fora dele — **o dólar paga *durante*
  o evento, não depois**. `internacional_pesos.parquet` é **não publicável** (§10.5 → F-035, D-af)
  — ref: F-026, `modules/internacional.md`, CONTRACTS §6a

- [2026-10-11] [RELEASE] **F-025 — timeline de regimes 2006→2026 sobre IBOV e Selic** em
  `apps/analysis/figuras/timeline_regimes.py` (50 testes): o *sanity check* visual do Comitê, 83
  trimestres **sem buraco** (`INDETERMINADO` é cinza hachurado, nunca uma 5ª cor) e 2 painéis
  empilhados em vez de eixo y duplo. **QA APROVADO** (166 linhas com dif 0,0, 4 canários até o
  bruto) — ref: `TODO.md §2` F-025, `modules/analysis.md`

- [2026-10-11] [RELEASE] **F-024 — tabela "regime atual → ranking de ativos" + concordância** em
  `apps/analysis/tabelas/ranking_regime_atual.py` (86 testes): responde "em que regime estamos?"
  **três vezes** (V1 `revised`, V1 `asof`, V3) e **não escolhe** — a escolha é **D1**, do Edu.
  Spearman em numpy puro mostra a divergência mais forte: **−0,748** entre V1 `revised` e V1 `asof`,
  mesma lente e mesmo método, só mudando a safra. A guarda de linguagem descritiva nasceu aqui e em
  **D-z** virou a **única** da camada — ref: `TODO.md §2` F-024

- [2026-10-11] [RELEASE] **F-023 — heatmap regime × ativo, o entregável visual central** em
  `apps/analysis/figuras/heatmap_regime_ativo.py` + `_comum.py` (71 testes): escala divergente
  **derivada e validada** (sem verde, que colapsa em protanopia), **3 estados de confiança em dois
  canais cada** e tooltip no SVG. Em **D-z**: `v3_t1` virou **`horizonte_cruzado`** e **`SP500_USD`
  saiu da figura** ⇒ **23 × 5 = 115** células, exclusão **nomeada no rodapé** — ref: F-023, ADR-002

- [2026-10-11] [RELEASE] **F-022 — métricas por regime × ativo** em
  `apps/pipeline/canonical/metricas_regime.py` (122 testes): **17 métricas** por
  `(lente, regime, asset_id)` em **3 tabelas nomeadas** (`revised` T0 + V3 T+1 = o entregável;
  `asof` T0; horizonte cruzado) — 3, e não 1 com coluna de materialização, porque a PK colidiria.
  Dois achados que vão ao slide: em `3T2026` a interseção dos top-5 das três lentes é **VAZIA**, e a
  concordância V1 × V3 tem **mediana 0,111** nas 61 referências. **`regimes.parquet` não é gravado**
  (D-r/D-ab) — ref: `TODO.md §2` F-022, `modules/regimes.md`

- [2026-10-11] **as 6 entradas das Ondas 1, 2 e 3 parte 1 estão INTEGRAIS em
  [`log-archive-2026-10.md`](./log-archive-2026-10.md)** — os 2 QAs independentes (0 × P0 nos dois;
  4.038 células com 0 divergência e a curva validada contra a Curva Zero da ANBIMA a 0,010 bp), a
  camada canônica em 6 features, a Onda 3 parte 1 (`asof` + as 2 lentes, e o achado de **CA-074**:
  a V1 troca de rótulo em 22 de 66 = 33,33% entre `revised` e `asof` ⇒ não é operacional na forma
  `asof`), a consolidação das Ondas 0/1 com **D-a..D-h** e o 1º rebuild de árvore limpa. **A
  condensação que estava aqui saiu para abrir espaço às 3 entradas da frente LDC Analytics; nada
  foi apagado** — ref: `log-archive-2026-10.md`, `TODO.md §3`, `DECISIONS_LOG §2.1/§2.2/§2.3`
- [2026-10-10] **as 22 entradas de 2026-10-10 foram arquivadas em [`log-archive-2026-10.md`](./log-archive-2026-10.md)** — kickoff do harness, ingest do e-mail de escopo, PRD v1.0, `/SDD-avancado` (SPEC 52 RFs → 128 CAs + Anti-SPEC, CONTRACTS, 6 ADRs em Proposta, catálogo de 132 séries), wiki inicial + `/wiki lint`/`repair`, F-032 (`DECISIONS_LOG` com as 12 substituições de fonte), housekeeping do `pyproject.toml`/CI N1, repo GitHub conectado e **Supabase descartado na v1** (ADR-007, Aceita). Nada apagado.

---

*`wiki/log-archive-2026-10.md` guarda, **integrais**, as 22 entradas de 2026-10-10, as 11 entradas
das Ondas 0/1/2 e as 4 da Onda 3 parte 1. No fechamento final de 2026-10-11 as entradas das Ondas
1-4 foram **condensadas** (nenhuma apagada) para abrir espaço às 3 de F-027/F-031/`[STATE]`; no
fechamento da frente LDC Analytics, na mesma noite, as 6 condensações das Ondas 1/2/3-parte-1
saíram de vez — **o integral delas está no arquivo, intocado** — para abrir espaço às 3 entradas da
frente. O próximo `/wiki repair` que precisar de espaço condensa o bloco F-022..F-026.*

---

## Regras

1. **Uma entrada por evento, com `ref` verificável.** Sem ref não é log — é opinião.
2. **Nunca apague entrada com ref a PR/ADR:** condense ou mova para `log-archive-YYYY-MM.md`.
3. **Não duplique o `DECISIONS_LOG`:** linke a linha de lá. `/wiki ingest` cria a entrada.

*Este arquivo é o `git log` humano. Curto, indexável, confiável.*
