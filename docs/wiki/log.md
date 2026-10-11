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

- [2026-10-11] [DATASET] **`data/canonical/` reconstruído com UM comando, 2 execuções
  byte-idênticas, `verify` rc 0.** `python -m apps.pipeline run --offline` duas vezes seguidas →
  **47 artefatos determinísticos** com o mesmo `sha256` e `MANIFEST.json` byte-idêntico;
  `python -m apps.pipeline verify` → **48 conferidos, VERIFY OK, rc 0** (1 linha `INFO` do
  `ldc.duckdb`, fora do agregado por **D-ad (b)**).
  **`DATASET_SHA256 = fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`.**
  Os 13 passos da ordem agora incluem `internacional` (F-026) e `tabelas` (F-024), que **faltavam**
  — antes "um comando" entregava ~2/3 do canônico com `rc = 0` (P1-2 do QA da Onda 4). Quase todo
  hash mudou **sem que uma célula de dado mudasse**: `versao_build` hasheia o conjunto de módulos, e
  este fechamento editou 2 schemas (**D-ac**), 2 módulos canônicos e os 3 da camada de análise
  (**D-z**). Contraprova: `raw_series` e `series_catalog`, que não têm coluna de versão, saíram
  **byte-idênticos**. Canários reconferidos e idênticos aos do QA: V1 19/19/16/13 + 16 ·
  `rho = 0,25987390740181016` · `INDX` em T+1 `= 0,05043012628905601` · ciclo Selic 34/23/26 ·
  `corr(USDBRL, IBOV)` em `RECUPERACAO` `= −0,7974364631220996` · stress em **20 de 83** — ref:
  `TODO.md §1`, `MANIFEST.json`, `runbooks/reconstruir-dataset.md`

- [2026-10-11] [VALIDATION] **Os dois QAs independentes — Onda 3 e Onda 4 — fechados: 0 × P0, 0
  divergência numérica, 8 × P1 todos de declaração ou de orquestração.** Onda 3
  (`qa/ONDA-3-QA.md`): reconstrução por fora de 5 colunas × 83 × 2 materializações, 83 × 2 rótulos,
  `rho` + 16 distâncias e 24 médias de ativo — **0 divergências**; os 5 P1 eram contrato espelho
  errado, leitura de um número de robustez, uma premissa factual errada num texto que vai ao
  decisor, CI sem N2/N3 e a safra `revised` não declarada. Onda 4 (`qa/ONDA-4-QA.md`): **120 células
  × 17 métricas** reconferidas com `max abs dif = 0,0` (`1,1e-16` em `beta_ibov`), `stress_flag`
  refeito do zero com **lista idêntica**, variância mínima conferida por **Ledoit-Wolf com laço
  explícito + busca em grade + KKT à mão** (dif **0,0** nos 4 pesos) e a identidade de moeda com
  resíduo **2,2e-16**; os 3 P1 eram `verify` estourando em Parquet corrompido, o orquestrador sem as
  etapas de F-026/F-024 e o não publicável viajando no dataset congelado. **Todos aplicados neste
  fechamento** (D-y, D-z, D-ab, D-ac, D-af) — ref: `docs/plans/qa/ONDA-{3,4}-QA.md`, `TODO.md §4`

- [2026-10-11] [DECISION] **D-y..D-af** registradas em `DECISIONS_LOG §2.3` (parte 4), no
  fechamento da Onda 4. **Aguardam Edu:** **D-aa (c)** (qual lente abre a página = D1) e a
  ratificação de **D6** (ADR-003, que governa a faixa do internacional). **Aceitas pelo
  orquestrador:** **D-y** (os 5 P1 da Onda 3, inclusive **a correção de fato de D-t: `2024Q3` é
  ALTA, não corte** — os 7 trimestres no limiar exato são 5 CORTE e 2 ALTA), **D-z** (renomeação da
  vista + `SP500_USD` fora do heatmap + cromo e guarda de linguagem unificados), **D-ab** (D6-a..d
  de F-026; `regimes.parquet` segue não gravado, agora por **um** motivo), **D-ac** (parser + check
  de não-nulidade em 5 colunas `bool`), **D-ad** (as 7 decisões de F-029), **D-ae** (dívidas de
  contrato numa lista única em `TODO.md §6`) e **D-af** (`publicavel` no manifesto) — ref:
  `DECISIONS_LOG §2.3`, `TODO.md §4/§6`

- [2026-10-11] [RELEASE] **F-029 — orquestrador "um comando" + idempotência e hash** em
  `apps/pipeline/run.py` (+ `__main__.py`, 42 testes unit e 6 e2e). `run` (13 etapas, `--offline`
  sem rede), `verify` (recalcula todo `sha256` contra o `MANIFEST.json`, `rc != 0` se divergir) e
  `freeze --tag` (`MANIFEST.json` + `FROZEN.txt`, **sem executar git**). Nada lê o relógio:
  `data_do_dado` vem dos relatórios das features, e é isso que faz o manifesto sair byte-idêntico.
  Neste fechamento ganhou as etapas **`internacional`** e **`tabelas`** (P1-2), deixou de **estourar
  traceback** em Parquet ilegível (P1-1: agora `rc = 1` nomeando arquivo e agregado) e passou a
  marcar artefato **não publicável** (**D-af**) — ref: `TODO.md §2` F-029, `modules/canonical.md`

- [2026-10-11] [RELEASE] **F-028 — página de limitações do Comitê** em
  `docs/product/LIMITACOES-COMITE.md` (**8 blocos, 249 linhas**) + `test_limitacoes_documento.py`
  (30 testes, com uma seção que **reabre os `relatorio_*.json` e exige a string na página** — número
  que muda de rodada derruba o teste, de propósito). **QA APROVADO.** Neste fechamento ganhou a
  §3.1 com os achados de F-026 (14 trimestres não avaliáveis pelo ramo da inclinação, a
  sensibilidade de 10,4% × 19,7% ao cap, 3 ativos sem fonte) e a nota do heatmap **sem `SP500_USD`**
  — ref: `TODO.md §2` F-028, RF-042/CA-112

- [2026-10-11] [RELEASE] **F-026 — alocação internacional + regra de risk-off** em
  `apps/pipeline/canonical/internacional.py` + `packages/shared/schemas/internacional.py` (2 schemas
  **novos**, 112 testes). Fecha o item **C1** do e-mail e **resolve o bloqueio de `stress_flag`** que
  F-022 deixou: a regra de **D6-a** marca **20 de 83** trimestres (7 inclinação, 11 câmbio, 2 ambos;
  14 não avaliáveis, nomeados; ramo EMBI fora com **0** valores não nulos). O achado central:
  `corr(USDBRL, IBOV)` é **−0,795** no stress contra **−0,418** fora dele — **o dólar paga *durante*
  o evento, não depois** (em T+1 após stress tudo subiu, e o IBOV quase tanto quanto o
  internacional). `internacional_pesos.parquet` é **não publicável** (Anti-SPEC §10.5 → F-035, D-af)
  — ref: `TODO.md §2` F-026, `modules/internacional.md`, CONTRACTS §6a

- [2026-10-11] [RELEASE] **F-025 — timeline de regimes 2006→2026 sobre IBOV e Selic** em
  `apps/analysis/figuras/timeline_regimes.py` (50 testes): o *sanity check* visual do Comitê, 83
  trimestres **sem buraco** (`INDETERMINADO` é cinza hachurado, nunca uma 5ª cor), 2 painéis
  empilhados em vez de eixo y duplo, e marcadores que separam as **22** trocas de rótulo das **2**
  trocas de status. **QA APROVADO** (166 linhas com dif 0,0, 4 canários até o bruto). Em **D-z**
  passou a importar o cromo de `_comum.py` — ref: `TODO.md §2` F-025, `modules/analysis.md`

- [2026-10-11] [RELEASE] **F-024 — tabela "regime atual → ranking de ativos" + concordância** em
  `apps/analysis/tabelas/ranking_regime_atual.py` (86 testes): responde "em que regime estamos?"
  **três vezes** (V1 `revised` com fallback declarado, V1 `asof`, V3) e **não escolhe** — a escolha é
  **D1**, do Edu. Spearman em numpy puro mostra a divergência mais forte: **−0,748** entre V1
  `revised` e V1 `asof`, mesma lente e mesmo método, só mudando a safra. Traz uma **guarda executável
  de linguagem descritiva**, que em **D-z** virou a guarda **única** da camada
  (`apps/analysis/_linguagem.py`) — ref: `TODO.md §2` F-024, `modules/analysis.md`

- [2026-10-11] [RELEASE] **F-023 — heatmap regime × ativo, o entregável visual central** em
  `apps/analysis/figuras/heatmap_regime_ativo.py` + `_comum.py` (71 testes): escala divergente
  **derivada e validada** (sem verde, que colapsa em protanopia), **3 estados de confiança em dois
  canais cada** (`n >= 8`, borda tracejada em `n < 8`, cinza hachurado + `prelim.` em `n < 5`) e
  tooltip no SVG. Em **D-z**: a vista `v3_t1` virou **`horizonte_cruzado`** e **`SP500_USD` saiu da
  figura** (mistura moedas), deixando **23 × 5 = 115** células na vista principal, com a exclusão
  **nomeada no rodapé** — ref: `TODO.md §2` F-023, ADR-002, `modules/analysis.md`

- [2026-10-11] [RELEASE] **F-022 — métricas por regime × ativo** em
  `apps/pipeline/canonical/metricas_regime.py` (122 testes): **17 métricas** por
  `(lente, regime, asset_id)` em **3 tabelas nomeadas** (`revised` T0 + V3 T+1 = o entregável;
  `asof` T0; horizonte cruzado) — 3 tabelas, e não 1 com coluna de materialização, porque a PK
  colidiria e acrescentar coluna a schema existente é **alteração** ⇒ pausa. Dois achados que vão ao
  slide: em `3T2026` a interseção dos top-5 das três lentes é **VAZIA**, e a concordância V1 × V3
  tem **mediana 0,111** nas 61 referências comparáveis (**0** referências com top-5 idêntico em 20
  anos). **`regimes.parquet` não é gravado** (D-r/D-ab) — ref: `TODO.md §2` F-022,
  `modules/regimes.md`

- [2026-10-11] [VALIDATION] **QA independente da Onda 2 — F-010, F-014..F-017 APROVADAS, 0 × P0**
  (condensado; integral em `log-archive-2026-10.md`). Dois subagentes, nenhum implementador,
  reimplementando a régua **sem importar o módulo sob teste**: 4.038 células de `alinhado` com **0
  divergências**, 22 colunas de `macro_quarterly` com `max |dif| = 0,0`, 11 séries de curva
  recalculadas do **CSV bruto** e validadas **contra a Curva Zero oficial da ANBIMA** (o breakeven
  **por razão** reproduz a inflação implícita a **0,010 bp**; a subtração erra até 37,2 bps), e o
  canário do CDI 2006 = **15,027140%** confirmado por 2ª fonte a `2,8e-05 pp`. 6 × P1 absorvidos em
  **D-s/D-t/D-v** — ref: `qa/ONDA-2-QA-{A,B}.md`, `TODO.md §3`
- [2026-10-11] [DATASET] **`data/canonical/` reconstruído de árvore limpa, em cadeia, com as duas
  materializações e as duas lentes** (condensado; integral em `log-archive-2026-10.md`): 2 rodadas
  `--offline` com **hash idêntico nos 20 artefatos** de então — **superado pelo rebuild de 13 etapas
  do fechamento da Onda 4**, no topo deste log — ref: `TODO.md §1`
- [2026-10-11] [RELEASE] **Onda 3 parte 1 — `asof` + as duas lentes de regime, 3 features
  (condensado; integral em `log-archive-2026-10.md`).** **F-018** `macro_quarterly_asof` **83 × 42**
  + procedência **2.552** células com `date_obs`/`lag_dias` e **0** violação de look-ahead, e o
  achado que subiu ao Comitê: a V1 troca de rótulo entre `revised` e `asof` em **22 de 66 =
  33,33%**, acima dos 25% de **CA-074** ⇒ a V1 **não é operacional na forma `asof`** e **H-03 do
  PRD cai** · **F-019** `regimes_v1{,_asof}.parquet` **83 × 18**, 67 classificados e **16
  `INDETERMINADO`** declarados em vez de estimados (**D-m**) · **F-021** `regime_neighbors_v3`
  **9.692 × 21** com Mahalanobis + **Ledoit-Wolf em numpy puro** (`rho = 0,259874`) e o ranking em
  **T+1** dos 8 vizinhos de `2026Q3`. Decisões **D-r..D-x** em `DECISIONS_LOG §2.3` (parte 3), com
  **D-s/D-t/D-u** aguardando Edu e **D-q(e) SUPERADA por D-s** — ref: `TODO.md §3/§4`,
  `DECISIONS_LOG §2.3`, `log-archive-2026-10.md`
- [2026-10-11] [RELEASE] **Onda 2 — a camada canônica, 6 features (condensado; integral em
  `log-archive-2026-10.md`).** **F-013** `raw_series` **278.439** linhas / 62 séries + catálogo
  materializado **138 × 26** (`apps/pipeline/canonical/build_raw_series.py`) · **F-014**
  `alinhado_trimestral` **4.038** linhas, 49 séries × 83 trimestres, **215** ffill de exatamente 1
  d.u. (todos B3, todos 4T — **D-h**) e 7 nulos com motivo; artefato **novo**, `CONTRACTS.md §8` ·
  **F-016** curva com **11** séries interpoladas em 1/3/5 anos, breakeven **por razão**, catálogo
  134 → **138** (**D-i**: `INCLINACAO_REAL_5A_3A`, 95,25%, passa a ser a principal porque a 5a−1a
  tem 60,53% e **CA-025 não fecha** com o vértice curto) · **F-015** `macro_quarterly` **83 × 42**
  + `macro_quarterly_provenance` **2.548** linhas (CA-120 por anti-join nas duas direções), com
  grade de **apoio** `2001Q1..2005Q4` conferida célula a célula contra F-014 (o build **para** se
  divergir) e 5 colunas 100% nulas, todas por gap declarado · **F-017**
  `asset_returns_quarterly` **1.963** linhas / **24** ativos, excesso e real **por razão**,
  encadeamento **geométrico** (a soma erraria até 8,13 pp) · **F-010** extrator Focus (BCB Olinda /
  OData v4), 5 EntitySets, **197** séries, 150.120 linhas, fora de `raw_series` por **D-k**.
  Decisões da onda: **D-i, D-j, D-k..D-q** — ref: `TODO.md §3`, `CONTRACTS.md §1..§4/§8`,
  `modules/canonical.md`, `modules/focus.md`, `DECISIONS_LOG §2.3`
- [2026-10-11] [VALIDATION] **QA independente da Onda 1 concluído em dois lotes — os 7 extratores
  APROVADOS, 0 × P0** (`docs/plans/qa/ONDA-1-QA-A.md` = F-002/F-003/F-004/F-008 ·
  `ONDA-1-QA-B.md` = F-005/F-006/F-007). F-003 e F-005 em `MUDANÇAS_SOLICITADAS` → aprovadas após
  `65d2fb9` (P1-1 de F-003: observação de período **parcial** entrava como mês fechado; P1-2: a SGS
  432 é calendário **corrido** e nada no dado dizia isso → campo `calendario` no catálogo; P1-1 de
  F-005: `--offline` sobre bruto **sem manifesto** caía no relógio da rodada e quebrava
  D-b/CA-121). **D-e** (CA-004/CA-005 da SPEC não fecham no dado real) aberto para o Edu; **D-h**
  (B3 ⊂ ANBIMA em 69 datas) virou DoR de F-014 — ref: `docs/plans/qa/ONDA-1-QA-{A,B}.md`,
  `TODO.md §3/§4`
- [2026-10-11] [CONSOLIDAÇÃO] **Ondas 0 e 1 fechadas: infra de extração + 7 extratores + as 8
  convenções D-a..D-h** (condensado; integral em `log-archive-2026-10.md`). As convenções
  divergentes dos extratores foram alinhadas numa rodada só, e as duas reconciliações entre fontes
  que eram script de sessão viraram **teste** (`test_contract_sgs_sidra.py`,
  `test_processed_layer_conventions.py`, `max |dif| = 0` nos dois). 2 rodadas `--offline` com
  **hash idêntico** nos 53 Parquets — ref: `TODO.md §3/§6`, `DECISIONS_LOG §2.1/§2.2`, `modules/`
- [2026-10-10] **as 22 entradas de 2026-10-10 foram arquivadas em [`log-archive-2026-10.md`](./log-archive-2026-10.md)** — kickoff do harness, ingest do e-mail de escopo, PRD v1.0, `/SDD-avancado` (SPEC 52 RFs → 128 CAs + Anti-SPEC, CONTRACTS, 6 ADRs em Proposta, catálogo de 132 séries), wiki inicial + `/wiki lint`/`repair`, F-032 (`DECISIONS_LOG` com as 12 substituições de fonte), housekeeping do `pyproject.toml`/CI N1, repo GitHub conectado e **Supabase descartado na v1** (ADR-007, Aceita). Nada apagado.

---

*`wiki/log-archive-2026-10.md` guarda, **integrais**, as 22 entradas de 2026-10-10, as 11
entradas das Ondas 0/1/2 e as 4 entradas da Onda 3 parte 1 (F-018, F-019, F-021 e D-r..D-x) —
esta última arquivada em 2026-10-11, no fechamento da Onda 4, para manter este arquivo em
≤ 200 linhas (hoje: 200). Nada foi apagado. O próximo `/wiki repair` que precisar de espaço
arquiva o bloco da Onda 2.*

---

## Regras

1. **Uma entrada por evento, com `ref` verificável.** Sem ref não é log — é opinião.
2. **Nunca apague entrada com ref a PR/ADR:** condense ou mova para `log-archive-YYYY-MM.md`.
3. **Não duplique o `DECISIONS_LOG`:** linke a linha de lá. `/wiki ingest` cria a entrada.

*Este arquivo é o `git log` humano. Curto, indexável, confiável.*
