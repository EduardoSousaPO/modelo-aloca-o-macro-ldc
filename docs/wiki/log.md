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

- [2026-10-11] [VALIDATION] **QA independente da Onda 2 concluído em dois lotes — F-014, F-015,
  F-016, F-017 e F-010 APROVADAS, 0 × P0** (`docs/plans/qa/ONDA-2-QA-A.md` = F-014/F-015 ·
  `ONDA-2-QA-B.md` = F-016/F-017). Dois subagentes distintos, nenhum deles implementador, e o
  método que a classe C exige: **reimplementar a régua do zero, sem importar o módulo sob teste**.
  Resultado: F-014 com **4.038 células conferidas, 0 divergências** e build em scratch
  **byte-idêntico**; F-015 com **22 colunas** recalculadas por fora e `max |dif| = 0,0` (igualdade
  exata em float64), procedência bidirecional **0/0** e anti-look-ahead **0** em 2.515 `date_obs`
  reconstruídas; F-016 com **11 séries × 5.436 datas** recalculadas do **CSV bruto** com igualdade
  exata, as duas coberturas de D-i ao centésimo e validação **externa** contra a Curva Zero da
  ANBIMA (o breakeven **por razão** reproduz a "Inflação Implícita" oficial a **0,010 bp**; a
  subtração erra até **37,2 bps**); F-017 com `ret_tri`/CDI/IPCA/excesso/real/vol/dd reproduzidos
  por fora com igualdade exata, canário CDI 2006 = **15,027140%** e **2ª fonte** (SGS 4389) a
  **2,8e-05 pp**. **6 × P1**, todos absorvidos neste fechamento (D-s, D-t, D-v) — ref:
  `docs/plans/qa/ONDA-2-QA-{A,B}.md`, `TODO.md §3`, `DECISIONS_LOG §2.3`
- [2026-10-11] [DATASET] **`data/canonical/` reconstruído de árvore limpa em cadeia completa, com
  as duas materializações e as duas lentes de regime** — ordem obrigatória, todos `--offline`:
  `build_raw_series` → `alinhamento` → `macro_quarterly` → `asof` → `retornos` → `regimes_v1`
  (`revised` **e** `asof`) → `regimes_v3` (a `curva` de F-016 roda antes de tudo, porque escreve em
  `data/processed/`). **2 rodadas com hashes idênticos nos 20 artefatos.** `raw_series` **278.439**
  linhas / 62 séries (`0d23df7a…`, **inalterado**) · `series_catalog` **138 × 26** (`f56f207e…`,
  **inalterado**) · `alinhado_trimestral` **4.038** (`c66f09a5…`) · `macro_quarterly` **83 × 42**
  (`bcb31e92…`) + provenance **2.548** (`aa8d427a…`) · `macro_quarterly_asof` **83 × 42**
  (`85e8ec67…`) + provenance **2.552** com `date_obs`/`lag_dias` (`a5b2eaef…`) ·
  `asset_returns_quarterly` **1.963** / 24 ativos (`c055ac81…`) · `regimes_v1` **83 × 18**
  (`b74f8d67…`) e `regimes_v1_asof` (`6e922165…`) · `regime_neighbors_v3` **9.692 × 21**
  (`5241f275…`) e `regime_neighbors` **5.500 × 11** (`eb101c5a…`). **Os hashes mudaram por dois
  motivos, os dois declarados:** **D-s** (média do trimestre no IBC-Br → 3 colunas de
  `macro_quarterly`) e **D-v b** (`versao_build` passou a normalizar o fim de linha → `fonte_versao`
  de toda a camada). `raw_series` e `series_catalog` **não** têm coluna de versão e saíram
  byte-idênticos — é a contraprova de que o dado bruto não se moveu. `ruff` limpo e **1.416 passed,
  6 skipped, 17 deselected, 1 xfailed, 0 failed** em `tests/unit tests/contract -m "not network"` — ref:
  `TODO.md §1`, `CONTRACTS.md §3/§3.1/§5`, `modules/canonical.md`, `modules/regimes.md`
- [2026-10-11] [RELEASE] **F-021 — Regimes V3 (vizinhos mais próximos) + retorno em T+1** em
  `apps/pipeline/canonical/regimes_v3.py`: é **o objetivo literal do e-mail** ("como cada classe de
  ativo e até setores performaram em momentos semelhantes"). **5 features** em z-score, Mahalanobis
  com shrinkage de **Ledoit-Wolf implementado à mão em numpy** (`rho = 0,259874`, condicionamento
  8,26 → 3,97 — **nenhuma dependência nova**, logo nenhum ADR de §10.4.25), `k = 8` com 5 e 12 de
  sensibilidade, Euclidiana em paralelo, exclusão **simétrica** de `T±1`/`T±2` e desempate pelo mais
  recente. **77 dos 83** trimestres têm vetor completo. Dois artefatos: `regime_neighbors_v3`
  (**9.692 × 21**, a lente principal e a que **F-022/F-024 devem ler**) e `regime_neighbors`
  (**5.500 × 11**, o pool restrito de CA-089, que perde 4 dos 8 vizinhos de `2026Q3` porque
  `regime_v1_neighbor` é `nullable=False` — **D-u**, dívida em `TODO.md §6`). Os **8 vizinhos de
  `2026Q3`**: `2006Q3 · 2006Q4 · 2006Q1 · 2024Q3 · 2014Q4 · 2007Q1 · 2024Q2 · 2014Q3` — e a
  variante **sem nenhum look-ahead** dá a **mesma lista** (Jaccard 1,0), o achado mais forte da
  feature. O eixo de crescimento é `focus_pib_ano` e **não** `ibcbr_gap`, porque o hiato é nulo em
  `2026Q3` por construção (**D-u**); `termos_troca_yoy` foi **cortada** (100% nula, G-02) e
  `n_features = 5` é declarado **na linha**. **84 testes** (45 unit + 39 contract), com a distância
  recalculada em numpy puro **dentro** do teste de acervo. `ranking` em **fração**, linguagem
  **descritiva** por contrato, e o gate de publicação é `False` (ADR-001 em Proposta) — ref:
  `TODO.md §2 F-021`, `CONTRACTS.md §5.2a/§5.3`, `wiki/context/F-021.md`, CA-084..087/089/101/102
- [2026-10-11] [RELEASE] **F-019 — Regimes V1 (quadrantes crescimento × inflação)** em
  `apps/pipeline/canonical/regimes_v1.py`: `regimes_v1{,_asof}.parquet` **83 × 18** +
  `relatorio_regimes_v1{,_asof}.json`. **67** trimestres classificados e **16** `INDETERMINADO`
  (`2006Q1..2009Q3` + `2026Q3`, todos `GAP_AUSENTE` por **D-m** — a crise de 2008 inteira fica fora
  do eixo de crescimento, e isso vai à F-028). Distribuição **RECUPERACAO 19 · EXPANSAO_INFL 19 ·
  ESTAGFLACAO 16 · DESACELERACAO 13**: CA-080 fecha (4 quadrantes povoados, todos em [10, 35]),
  desbalanceamento 1,46×, **0 desempates** no dado real. Grava `regimes_v1.parquet` e **não**
  `regimes.parquet` (**D-r**: a junção em `RegimesSchema` é de F-022), com `regime_v1` **nulo** +
  `status_regime_v1` + `motivo_indeterminado` em vez de quadrante inventado. **123 testes** (84
  unit + 39 contract). ⚠️ **CA-074 ACIONADO:** a V1 troca de rótulo entre `revised` e `asof` em
  **22 de 66 trimestres = 33,33%**, acima do limiar de **25%** ⇒ pelo critério escrito a V1 **não é
  operacional na forma `asof`** e a hipótese **H-03 do PRD cai** (a leitura descritiva, RF-027,
  segue válida). `especificacao_congelada = False` nas 83 linhas, lido do **status do ADR-001 em
  disco** com falha fechada: **nada daqui é publicável** (CA-090) — ref: `TODO.md §2 F-019/§4`,
  `CONTRACTS.md §5.1a`, `wiki/context/F-019.md`, CA-078..081/088/090/091
- [2026-10-11] [RELEASE] **F-018 — regra anti-look-ahead + materialização `asof`** em
  `apps/pipeline/canonical/asof.py`: `macro_quarterly_asof.parquet` **83 × 42**
  (`lag_adjusted=True` nas 83) + `macro_quarterly_asof_provenance.parquet` **2.552** linhas com
  **`date_obs` e `lag_dias` em todas** + `relatorio_asof.json`. A regra: o valor de `(T, coluna)` é
  o da última observação cuja **divulgação** (`date_obs + lag_divulgacao_dias`, lag **inteiro do
  `series_catalog`**) é `<= quarter_end(T)`, com **toda derivada recalculada** sobre os níveis
  deslocados — nenhuma copiada da revisada. Série sem lag resolvível **para** o build. **27** das 37
  colunas rastreáveis são idênticas à `revised` e **10** mudam. O que sustenta o número: o módulo
  monta a `revised` **na mesma rodada** e a confere célula a célula contra o Parquet de F-015 em
  disco — **3.071 células, 0 divergências, `max |dif| = 0,0`** —, e CA-072 é verificável **no
  Parquet publicado** (`date_obs + lag_dias <= quarter_end` nas 2.552 linhas, **0** violações; o
  build para se houver uma). **57 testes** (35 unit + 22 contract). Acréscimo de schema
  (`MacroQuarterlyAsofProvenanceSchema`, subclasse — nunca alteração) registrado em
  `CONTRACTS.md §3.1` — ref: `TODO.md §2 F-018`, `wiki/context/F-018.md`, RF-025, CA-072/073/074
- [2026-10-11] [DECISION] **D-r..D-x** registradas em `DECISIONS_LOG §2.3` (parte 3), no fechamento
  da Onda 3 parte 1. As três que mudam número publicado e **aguardam o Edu**: **D-s** (`ibcbr_yoy`
  passa a usar a **média dos 3 meses** do trimestre, como `metodologia §2` escreve — `max |dif|`
  4,2646 pp no a/a, 4,3064 pp no hiato e **7 dos 67 trimestres trocando de quadrante**, exatamente
  os 7 que o QA previu; a troca `asof` × `revised` **sobe** de 29,85% para 33,33%, e o número foi
  **reportado, não ajustado**), **D-t** (ciclo Selic: `|Δ| >= 0,25 pp` é movimento, não parada —
  distribuição de CORTE 29/NEUTRO 30/ALTA 24 para **CORTE 34 · NEUTRO 23 · ALTA 26**, porque os
  cortes reais de 25 bps de 2024Q2/Q3 saíam `NEUTRO`) e **D-u** (eixo da V3 = `focus_pib_ano`;
  `regime_v1_neighbor` segue `nullable=False` e F-022/F-024 leem o `_v3`). As de organização, aceitas
  pelo orquestrador: **D-r** (`RegimesV1Schema`, junção em F-022), **D-v** (as 3 correções dos P1 do
  QA: `exigir_series` também contra `alinhado_trimestral`; `versao_build` normaliza o fim de linha;
  janela do CDI vira limitação declarada), **D-w** (`CONTRACTS.md` com o estado medido) e **D-x**
  (paths em `canonical/`). **D-q(e) foi SUPERADA por D-s**, com a linha original preservada — ref:
  `DECISIONS_LOG §2.3`, `TODO.md §4/§6`
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
  divergentes dos 7 extratores foram alinhadas numa rodada só (`date` de série mensal/trimestral em
  **fim de período** civil — D-a; `vintage` = data do `collected_at` do manifesto — D-b; glob do
  `--offline` filtrando `*.meta.json` — D-c; catálogo 132 → **134** com `SP500_BRL`/`ACWI_BRL`
  `fonte=DERIVADO` — D-d; `transform/cambio.py` — D-g), e as duas reconciliações entre fontes que
  eram script de sessão viraram **teste**: `tests/unit/test_contract_sgs_sidra.py` (SGS 433 ×
  SIDRA `t/1737 v/63` em **273 meses** e SGS 22109 × SIDRA `t/1621 v/584` em **90 trimestres**,
  `max |dif| = 0` nos dois) e `tests/unit/test_processed_layer_conventions.py` (varredura de toda
  série em `data/processed/`). Os dois **pulam** quando `data/processed/` está vazia — é o que
  permite rodar sem rede, e é a dívida de CI em `TODO.md §6`. 2 rodadas `--offline` dos 8
  extratores com **hash idêntico** nos 53 Parquets — ref: `TODO.md §3/§6`,
  `DECISIONS_LOG §2.1/§2.2`, `modules/`
- [2026-10-10] **as 22 entradas de 2026-10-10 foram arquivadas em [`log-archive-2026-10.md`](./log-archive-2026-10.md)** — kickoff do harness, ingest do e-mail de escopo, PRD v1.0, `/SDD-avancado` (SPEC 52 RFs → 128 CAs + Anti-SPEC, CONTRACTS, 6 ADRs em Proposta, catálogo de 132 séries), wiki inicial + `/wiki lint`/`repair`, F-032 (`DECISIONS_LOG` com as 12 substituições de fonte), housekeeping do `pyproject.toml`/CI N1, repo GitHub conectado e **Supabase descartado na v1** (ADR-007, Aceita). Nada apagado.

---

*`wiki/log-archive-2026-10.md` guarda, **integrais**, as 22 entradas de 2026-10-10 e as 11
entradas de 2026-10-11 das Ondas 0/1/2 — arquivadas e condensadas aqui em 2026-10-11, no fechamento
da Onda 3 parte 1, para manter este arquivo em ≤ 200 linhas (hoje: 173). Nada foi apagado. O
próximo `/wiki repair` que precisar de espaço arquiva o bloco da Onda 3.*

---

## Regras

1. **Uma entrada por evento, com `ref` verificável.** Sem ref não é log — é opinião.
2. **Nunca apague entrada com ref a PR/ADR:** condense ou mova para `log-archive-YYYY-MM.md`.
3. **Não duplique o `DECISIONS_LOG`:** linke a linha de lá. `/wiki ingest` cria a entrada.

*Este arquivo é o `git log` humano. Curto, indexável, confiável.*
