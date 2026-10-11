# Log — arquivo de 2026-10 (entradas de 2026-10-10)

> Arquivado de `docs/wiki/log.md` em 2026-10-11, no fechamento da Onda 3 parte 1, para manter
> o log vivo em ≤ 200 linhas (regra do cabeçalho de `log.md`). **Nada foi apagado:** são as
> 22 entradas de 2026-10-10 (kickoff, PRD, SDD, wiki inicial, housekeeping do harness e as
> duas decisões de infraestrutura), na ordem original — mais novas no topo.
> O que delas continua valendo está sintetizado em `overview.md`, `architecture.md` e
> `DECISIONS_LOG.md`; aqui é só a cronologia.

---

## Onda 1 e Onda 2 — entradas integrais de 2026-10-11

> Condensadas em `log.md` em 2026-10-11 (fechamento da Onda 3 parte 1). O conteúdo permanente
> está em `wiki/modules/` e em `TODO.md §3`; aqui fica a redação original.

- [2026-10-11] [DATASET] **`data/canonical/` reconstruído em sequência fechada depois de F-010,
  F-015 e F-017** — a ordem é obrigatória e é parte da garantia: `build_raw_series` → `alinhamento` →
  `macro_quarterly` → `retornos`, todos `--offline` (a `curva` de F-016 roda **antes** de tudo, porque
  escreve em `data/processed/`). Resultado, **2 rodadas com hashes idênticos**: `raw_series` **278.439**
  linhas / **62** séries (`0d23df7a…`) com **7** tabelas excluídas — as 2 antigas + as **5** do Focus
  (**D-k**); `series_catalog` **138 × 26** (`f56f207e…`); `alinhado_trimestral` **4.038**
  (`ac0d9842…`); `macro_quarterly` **83 × 42** (`dcded731…`) + `macro_quarterly_provenance` **2.548**
  (`4a582c1d…`); `asset_returns_quarterly` **1.963** linhas / **24** ativos (`ab61eeca…`). Os 4
  `relatorio_*.json` têm `versao_build` conferido **contra o código em disco** (`e48262bb…`,
  `ae18c930…`, `5cd7bdaf…`, `20b812f2…`) — hash de código igual com Parquet diferente seria bug.
  `ruff` limpo e **1.141 passed, 5 skipped, 1 xfailed, 0 failed** em
  `tests/unit tests/contract -m "not network"` — ref: `TODO.md §1`, `CONTRACTS.md §1.1/§3/§4`,
  `modules/canonical.md`, `DECISIONS_LOG §2.3`
- [2026-10-11] [RELEASE] **F-015 — `macro_quarterly` com 83 trimestres** em
  `apps/pipeline/canonical/macro_quarterly.py`: nasce a tabela **wide** do canônico — **83 × 42**
  (`2006Q1..2026Q3`, `revised`) — mais a companheira `macro_quarterly_provenance` com **2.548**
  linhas (**32** colunas rastreáveis, **20** séries, **CA-120 por anti-join nas duas direções**) e
  `relatorio_macro.json` com nulos **por coluna com motivo**, unidades, 4 canários, anti-look-ahead
  e a sensibilidade do hiato. **Só 5 colunas são 100% nulas**, todas por gap declarado (G-02, L8,
  termos de troca sem fonte). O que carrega o número: **todo nível é a célula de F-014 bit a bit**;
  grade de **apoio** `2001Q1..2005Q4` que reexpressa a régua de F-014 e é conferida célula a célula
  (**913 células, 0 divergências**, e divergir **para o build**); acumulação **geométrica** só com
  trimestre completo (**0** incompletos); Focus de `data/processed/focus/` pela régua "coleta do
  início de T" com troca `H0`→`H1` no 1º trimestre (canário `focus_ipca_12m` 2026Q3 = **4,19**);
  `ciclo_selic` é **função publicada, não coluna**. **CA-007 não é satisfazível** com o IBC-Br real,
  que começa em 2003: `ibcbr_gap` com **16** nulos e a V1 classificará **67** dos 83 — **D-m**, SPEC
  **não** editada, alternativa (`min_periods = 8`) **medida**. `INCLINACAO_REAL_5A_3A` **não** ganhou
  coluna (**D-n**). 137 testes; 2 rodadas byte-idênticas. **QA + revisão numérica pendentes** — ref:
  F-015, `CONTRACTS.md §3/§3.1`, `DECISIONS_LOG §2.3` (D-m/n/o), CA-059/060/061/120, ADR-006
- [2026-10-11] [RELEASE] **F-017 — `asset_returns_quarterly`: retorno, excesso sobre CDI e retorno
  real** em `apps/pipeline/canonical/retornos.py`: **1.963 linhas** × **24** ativos × 83 trimestres
  + `relatorio_retornos.json` (cobertura por ativo, nulos nomeados, `bases_por_trimestre` com CDI e
  IPCA dos 83, as 11 convenções em texto). **`USDBRL` entrou por D-l** (+83 linhas,
  `is_total_return=False` — câmbio não tem carrego), que é o que **RF-038** precisa. Convenções que
  carregam o número: níveis **sempre** de `alinhado_trimestral`; **1º trimestre de cada série sem
  retorno** (23 `NULL` com motivo, mas **com** `price_fim`); **CDI por acumulação diária** da SGS 12,
  por isso é o **único** ativo com retorno em `2006Q1`; excesso e real pela **mesma** função de razão
  `(1+r)/(1+b)−1` — no acervo a subtração erraria **0,138 pp por trimestre** (máx. **1,495 pp**);
  `ret_real` pelo IPCA dos 3 meses de **referência**, uma vez; `is_total_return` **propagado do
  catálogo** (820 nulos — G-01 + CDI); painel **desbalanceado**. Evidência: `ret_tri` recalculado
  **fora do pytest**, sem importar o módulo, em
  **1.858** linhas → **0 divergências, `max|dif| = 0.0` sem tolerância**; CDI de 2006 encadeado =
  **15,027140 %** em **249** d.u., de fixture versionada; conferência do CDI contra a **SGS 4389**
  (outra série, outra unidade) com `dif = 4,8e-6 pp`; produto dos fatores diários == `ret_tri`
  (erro ≤ 1e-15), enquanto a **soma** erraria 4,25 pp em 4T2008. 93 testes; 2 rodadas byte-idênticas.
  **QA + revisão numérica pendentes; ADR-006 e ADR-005 seguem em `Proposta`** — ref: F-017,
  `CONTRACTS.md §4`, `DECISIONS_LOG §2.3` (D-l, D-o), CA-062..064/069..071/014..016, ADR-002/005/006
- [2026-10-11] [RELEASE] **F-010 — extrator Focus (BCB Olinda / OData v4)** em
  `apps/pipeline/extract/bcb_focus.py`: **5 EntitySets**, **197 `series_id`**, **150.120 linhas**,
  **0,00%** de nulos, 2004-01-02 → **2026-10-02**, em `data/processed/focus/`. É a **única** fonte do
  projeto **sem look-ahead**, e a convenção foi desenhada para não destruir isso: `date` é o **dia da
  pesquisa** (exceção explícita a **D-a**) e o horizonte vive no `series_id`
  (`FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>`). **G-04 e G-05 resolvidos:** o rótulo é **`PIB Total`** e
  `baseCalculo=1` **só existe de 2014 em diante** (medido ano a ano), logo `0` é a única base com os
  20 anos do e-mail — sem o filtro a série **dobra**. Achados que custam caro: no `$filter`/`$orderby`
  o espaço tem de ser **`%20`, nunca `+`** (`params=` devolve HTTP 400); **`$top=20000` trunca em
  silêncio, sem `@odata.nextLink`** (32.582 → 20.000, CA-018), com 3 camadas de defesa; o corpo de
  erro é JSON **dentro de comentário** `/*{…}*/` sem `Content-Type`, e a resposta **boa** não é array
  — `validar_corpo_json_array` a recusaria. Contagem: **5.710** observações contra **5.714** dias
  úteis da ANBIMA, as 4 ausências todas de 2004 e **nenhuma** data fora do calendário. **O Focus fica
  fora de `raw_series`** (**D-k**, 5 exclusões, precedente do painel do Tesouro) e
  **`FOCUS_PIB_TOTAL` virou `descartada`** (**D-p**). 70 testes (68 sem rede); 2 rodadas
  byte-idênticas. **QA pendente** — ref: F-010, `modules/focus.md`, `DECISIONS_LOG §2.3`
  (D-k, D-p, D-q), CA-017/018/019
- [2026-10-11] [DATASET] **`data/canonical/` reconstruído depois de F-014/F-016** (condensado;
  **superseded** pelo rebuild no topo): 62 Parquets → 278.439 linhas / 62 séries — ref: F-013
- [2026-10-11] [RELEASE] **F-016 — curva: vértices fixos interpolados + inclinação** em
  `apps/pipeline/canonical/curva.py`: do painel do Tesouro (886.300 linhas) saem **11 séries** em
  `data/processed/curva/` (5.436 linhas cada, `fonte=DERIVADO`) — vértices real e nominal de 1, 3 e 5
  anos, 4 inclinações em `pp` e o breakeven de 5 anos. Decisões que carregam o número: `TAXA_VENDA`,
  **família** em vez de título, **dias corridos** (**D-j**), **sem extrapolação** e **breakeven por
  razão** (reproduz a "Inflação Implícita" da ANBIMA com erro de **0,01 bp**; a subtração erra ~37
  bps). **CA-025 não fechava** com o vértice de 1 ano (**60,53%**) → **D-i**: catálogo 134 → **138** e
  **`INCLINACAO_REAL_5A_3A` (95,25%)** passa a ser a variável principal de regime, com as 5a−1a
  secundárias e declaradas; as 7 séries pré-D-i saíram com `sha256` **idêntico**. Contra a Curva Zero
  ANBIMA a diferença é de **6 a 20 bps**, no mesmo sinal: **nenhuma figura pode chamar isto de curva
  ANBIMA**. 90 casos; 2 rodadas byte-idênticas. **QA pendente** — ref: F-016, `DECISIONS_LOG §2.3`,
  ADR-004, `modules/tesouro.md`
- [2026-10-11] [RELEASE] **F-014 — alinhamento trimestral (fim de período, ffill <= 5 d.u.)** em
  `apps/pipeline/canonical/alinhamento.py` + `packages/shared/schemas/alinhado_trimestral.py`: nasce
  a tabela **`alinhado_trimestral`** — **4.038 linhas** (49 séries × 83 trimestres − 29 do painel
  desbalanceado), 18 colunas, PK `(series_id, quarter)`, 11 checks. **Três réguas, uma grade:**
  `quarter_end` é sempre o último dia útil bancário e `date_alvo` varia por série (`bancaria` 2.793 ·
  `civil` 1.162 · `corrido` 83), com as duas divergindo em **24 dos 83** trimestres — a Sexta-feira
  Santa de 2013 e 2024 é o caso que proíbe reimplementar a regra. **D-h, opção (a)**:
  `ffill_dias_uteis = {0: 3.823, 1: 215}`, **nenhum** valor 2..5. **7** células nulas, nenhuma
  herdando o período anterior; **4.031/4.031** células com valor são idênticas a `raw_series`
  (`max|dif| = 0.0`). 106 testes; 2 rodadas byte-idênticas. **QA pendente** — ref: F-014,
  `CONTRACTS.md §8`, `DECISIONS_LOG §2.1` (D-h), ADR-006 §(b)
- [2026-10-11] [RELEASE] **F-013 — camada `raw_series` + `series_catalog` materializado (corrigido
  pós-QA)** em `apps/pipeline/canonical/build_raw_series.py`: o build inteiro (descoberta, carga,
  consolidação, 4 guardas públicas, catálogo materializado, escrita, DuckDB, relatório, CLI) +
  `SeriesCatalogMaterializedSchema` (26 colunas). As **3 MUDANÇAS_SOLICITADAS do QA foram atendidas em
  `3265499`**, cada uma com teste de regressão: **P1-1** `versao_build` passou a ser o `sha256` do
  **conjunto** `MODULOS_DO_BUILD` (o artefato publicado ficava obsoleto com hash **idêntico**);
  **P1-2** `calendario` entrou no `SeriesCatalogSchema` (o materializado publicava 25 colunas sem ele);
  **P1-3** a divergência de duplicata passou a ser medida nas **8** colunas e as guardas rodam no
  concatenado **antes** do dedup — a linha que prova mistura de fontes não é mais apagada antes de
  CA-077 vê-la. Mais P2-1/2/3/7. **Re-QA pendente**; P2-4 (limiar de `pct_nulos`) segue em
  `TODO.md §6` — ref: F-013, `qa/ONDA-2-QA-F013.md`, `CONTRACTS.md §1.1/§2.4`, ADR-006 §(a)
- [2026-10-11] [VALIDATION] **QA independente da Onda 1 concluído, em dois lotes e por dois
  subagentes distintos** — `qa/ONDA-1-QA-A.md` (F-002, F-003, F-004, F-008) e `ONDA-1-QA-B.md`
  (F-005, F-006, F-007), sobre `e215dbf`. **0 × P0 nos dois lotes.** Vereditos: **F-002, F-006,
  F-007, F-008 APROVADO**; **F-003 e F-005 APROVADO após as correções em `65d2fb9`** (mês/trimestre
  **parcial** entrava como período fechado; o `calendario` da 432 não chegava ao catálogo;
  `--offline` sobre bruto **sem manifesto** datava o Parquet pelo relógio → `ManifestoAusente`);
  **F-004 APROVADO com D-e pendente do Edu** (CA-004/CA-005 **medidamente** não fecham e a SPEC
  **não** foi editada). Evidência produzida pelos revisores: idempotência byte a byte nos 31 + 22
  Parquets, Anti-SPEC §10.4.23 verificada por **execução** (socket monkeypatchado), ~20 payloads
  adversariais recusados, 249 d.u. de 2006 por **3** caminhos independentes e 14 canários conferidos
  na **fonte viva**. P1/P2 remanescentes em `TODO.md §6` — ref: `qa/ONDA-1-QA-A.md`,
  `qa/ONDA-1-QA-B.md`, `TODO.md §3`
- [2026-10-11] [CONSOLIDAÇÃO] **Onda 1 fechada: convenções divergentes dos 7 extratores alinhadas
  antes do QA e do canônico** (D-a..D-h, em `DECISIONS_LOG §2.1`, **provisórias, aval de Edu
  pendente**). **D-a** `date` de série M/Q = **fim de período civil** (F-003 corrigido; mês corrente
  **parcial** de SGS 4390/4189 passa a ser descartado com log) · **D-b** `vintage` = **data do
  `collected_at` do manifesto do bruto**, uniforme nos 7 (eram 3 convenções) e nunca do relógio ·
  **D-c** filtro de `*.meta.json` no glob do `--offline` nos 8 extratores · **D-d** catálogo 132 →
  **134** (`ACWI_BRL`, `SP500_BRL`) · **D-e** CA-004/CA-005 não fecham no dado real, **SPEC
  intocada** · **D-f** rota HTML do calendário ratificada + schema migrado para
  `schemas/calendario.py` · **D-g** câmbio → `apps/pipeline/transform/cambio.py` · **D-h** B3 ⊂
  ANBIMA em 69 datas → DoR de **F-014**. **Evidência:** `ruff` limpo, **531 testes verdes** sem rede,
  2 rodadas `--offline` dos 8 extratores com **hash idêntico nos 53 Parquets**, e as reconciliações
  SGS × SIDRA (**273 meses** e **90 trimestres**, `max|dif| = 0`) viraram teste — ref:
  `DECISIONS_LOG §2.1`, `TODO.md §1`, `docs/wiki/modules/`
> **Ondas 0 e 1 — as 9 entradas de feature foram condensadas em 2026-10-11** (`/wiki repair`, para
> manter o log <= 200 linhas). Nenhuma entrada foi apagada: todas seguem com a sua `ref`.

- [2026-10-11] [IMPLEMENTADO] **os 7 extratores da Onda 1 + a infra da Onda 0 — condensados em
  2026-10-11.** Detalhe por fonte em `docs/wiki/modules/`, veredito do QA em `TODO.md §3` +
  `docs/plans/qa/`, Feature Contract completo no git até `3265499`; nenhuma `ref` perdida.
  **F-001** infra em `apps/pipeline/common/`, 108 testes zero rede (`architecture.md`) · **F-002**
  ANBIMA S3, 9 índices IMA, IMA-B 16/09/2003 = **723,070317** · **F-003** BCB SGS, 15 séries /
  **44.447** linhas, CDI 2006 = **15,0271%** · **F-004** SIDRA, 6 séries, CA-002/CA-009 reconciliados,
  CA-004/005 não fecham (**D-e**) · **F-005** Tesouro Direto, **886.300** linhas / 750 `series_id`,
  HTTP **304 com 0 byte** · **F-006** API B3, 11 índices / **54.650** linhas, sem backfill ·
  **F-007** Yahoo + MSCI + câmbio, catálogo → **134** (**D-d**), ACWI 31/01/2006 = **121,3858** ·
  **F-008** calendário ANBIMA, **7.530** d.u. 2001→2030, B3 ⊂ ANBIMA em 69 datas (**D-h**) ·
  **F-009** job diário ANBIMA ao vivo (`runbooks/job-diario-anbima.md`)

---

## 2026-10-10 — entradas integrais

- [2026-10-10] [DECISION] repo GitHub conectado (`main`); **Supabase descartado na v1** (ADR-007, Aceita); ondas autorizadas com os padrões provisórios, com a **publicação** seguindo gated por ADR-001 — ref: `DECISIONS_LOG §2`, `TODO.md §4`
- [2026-10-10] [HOUSEKEEPING] **CI N1 verde antes de código** (P0-1/P0-2 da auditoria): `[tool.ruff] exclude` passou a cobrir `.claude` (96 erros de skill vendorizada), `data`, `venv` e `*.md` (ruff >= 0.14 formata snippets Python dentro de Markdown e reformataria `docs/research/`, que é imutável); `ignore = ["PD901"]` removido (regra extinta no ruff, emitia warning no CI); `ruff format` aplicado em `regimes.py`, `series_catalog_data.py`, `macro_quarterly.py` e `asset_returns_quarterly.py`; `[tool.pytest.ini_options] pythonpath = ["."]` + `tests/conftest.py` resolvem o import `packages.shared.schemas`; `bypass-selection = true` do hatchling trocado por `packages = ["packages"]` (o wheel instalava um pacote vazio). `ruff check .` e `ruff format --check .` verdes; `pytest tests/unit` sai **0** (antes: exit 5, `no tests ran`) — ref: `pyproject.toml`, `docs/plans/AUDITORIA-HARNESS.md §F-7`
- [2026-10-10] [HOUSEKEEPING] `tests/unit/test_schemas_smoke.py` (10 testes) e `tests/unit/test_canonical_guards.py` (9) criados: catálogo carrega com 132 entradas e `series_id` únicos, nenhuma entrada `ok` com identificador `a_confirmar`, nenhuma série FRED usável no pacote mínimo, schemas do canônico importam, backfill sintético rejeitado por trimestre e piso de `n_features`. Os que dependem de `pandera` (não instalada nesta máquina) usam `importorskip`; validados num env isolado `uv run --no-project --with pandera`: **23 passed, 1 xfailed**. `tests/fixtures/` criado com `README.md` de convenção (`<fonte>/<serie>__<data>.ext`, fixture de erro obrigatória, ≤ 200 KB) — ref: `tests/`
- [2026-10-10] [DECISION] **CA-120 reescrito** (E-1 da auditoria, classe C): `macro_quarterly` é wide — a linha é um trimestre, não um valor —, então `source`/`series_id`/`vintage`/`collected_at` por linha não respondiam "de onde veio este número?". A exigência de rastreabilidade **não** mudou; mudou onde é cumprida: nova tabela companheira `macro_quarterly_provenance` (long, PK `(quarter, column)`, com `series_id`, `source`, `vintage`, `collected_at`, `lag_adjusted`, `fonte_versao` + checks `vintage_nao_posterior_a_coleta` e `lag_adjusted_homogeneo`), materializada por F-015 junto com a tabela wide. `SPEC.md §13` passa a mapear RF-047 → F-013 **e** F-015 — ref: `docs/specs/SPEC.md` CA-120, `docs/contracts/CONTRACTS.md §3.1`, `packages/shared/schemas/macro_quarterly.py`, `TODO.md` F-015
- [2026-10-10] [BUGFIX] **Backfill sintético passava pela guarda do CA-063** (E-2 da auditoria, classe C): `sem_trimestre_antes_do_inicio_da_serie` comparava só o **ano**, aceitando `2010Q1..Q3` para o IFIX (início 2010-12-30), `2007Q1..Q3` para o IMOB e `2006Q1..Q3` para o ICON — os três casos que a Anti-SPEC §10.1.1 nomeia. Agora compara ano **e** trimestre; o trimestre que contém o início (2010Q4) segue aceito por desenho (é parcial, não anterior) e quem o anula é `price_ini` em F-014. Provado por teste parametrizado — ref: `packages/shared/schemas/asset_returns_quarterly.py`, `tests/unit/test_canonical_guards.py`
- [2026-10-10] [BUGFIX] `RegimeNeighborsSchema.n_features`: `ge=5` → **`ge=3`** (P1-10 / risco 3 da auditoria). O piso de 5 **rejeitava** o único cenário de corte que o `PLAN.md §5` prevê como aceitável: cortes 4 (F-010/Focus → cai `z_juro_real_exante`) e 5 (F-016/curva → cai `z_inclinacao`) são independentes e podem cair juntos (4 features); com G-02 (`ipca_meta`) aberto, cai também `z_ipca_desvio_meta` (3). Abaixo de 3 a V3 não é "momentos semelhantes" — é `BLOQUEADO`, não número. CA-086 segue cobrindo só o caso de 5 features (nota na auditoria) — ref: `packages/shared/schemas/regimes.py`, `docs/plans/PLAN.md §5`
- [2026-10-10] [DECISION] `usavel_no_pacote_minimo` deixou de ser sinônimo de `status = ok` (P1-9 / C-3 da auditoria): agora exclui `FONTES_BLOQUEADAS_NO_PACOTE_MINIMO` (hoje só `FRED`). `status` descreve o **identificador** (as 13 séries FRED têm ID confirmado na pesquisa §C10 e seguem `ok`); a propriedade responde "dá para extrair até 14/10?", e o FRED está bloqueado na camada de aplicação nesta máquina, 3/3 tentativas. Pacote mínimo: **89** das 99 `ok`. Plano B segue S-09 — ref: `packages/shared/schemas/series_catalog.py`, `docs/plans/skills-manifest.md §3`, `DECISIONS_LOG` S-09
- [2026-10-10] [DECISION] Limiar de cobertura do catálogo alinhado ao PRD: `cobre_2006` passou de `2006-01-02` para a constante `LIMIAR_COBERTURA_2006 = 2006-01-31` — **o schema segue o PRD §7**, que é o documento que define a métrica (o PRD não foi tocado). Efeito numérico zero: nenhuma série começa entre 03/01 e 31/01/2006. `data_inicio` preenchido para 7 séries FRED a partir da coluna "Início real" da pesquisa §C10 (DGS10 1962-01-02, DGS2/T10Y2Y 1976-06-01, T10Y3M 1982-01-04, VIXCLS 1990-01-02, DFF/FEDFUNDS 1954-07-01) → séries `ok` sem início medido caem de **24 para 17**. As 17 restantes **não têm início medido na pesquisa** (ela diz "Cobre 2006: Sim" / "≤2005", não a data) e por isso seguem `None`: preenchê-las seria inventar. Teste `xfail(strict=False)` lista as 17 no CI sem bloquear a onda — exceção declarada ao `CLAUDE.md §6` ("xfail sem ADR"), que fecha quando a pesquisa medir os inícios — ref: `packages/shared/schemas/series_catalog.py`, `series_catalog_data.py`, `docs/research/fontes-de-dados.md §A1/§C10`, `PRD.md:245`
- [2026-10-10] [HOUSEKEEPING] Alinhamentos de documento da auditoria: `PLAN.md:48` "8 substituições" → **12** (C-1, F-032 já concluída com S-01..S-12); dias da semana do `README.md` corrigidos — 2026-10-14 é **quarta** (dia do Comitê, coerente com "próxima quarta-feira" do e-mail) e 13/10 é **terça** (C-6); `CONTRACTS.md` atualizado para v1.1 (propriedades derivadas, contagens do catálogo, §3.1 nova, checks e `n_features`); `TODO.md` F-002 ganhou `tests/unit/test_anbima_s3.py` na lista de arquivos permitidos (F-4: a própria tabela de testes do item exigia 2 testes `unit`) — ref: `docs/plans/AUDITORIA-HARNESS.md §H`
- [2026-10-10] [HOUSEKEEPING] `pyproject.toml` corrigido — `openpyxl>=3.1` (os `.xls` da ANBIMA são XLSX), `lxml>=5.0` (`read_html` na Curva Zero) e `matplotlib>=3.8` (heatmap RF-033) adicionados às deps principais; `duckdb` mantido por **ADR-006**; `seaborn` dispensado (nenhum doc exige); `yfinance` segue como única dep pendente. Arquivo revalidado com `tomllib` — ref: `pyproject.toml`, `docs/plans/skills-manifest.md §4`
- [2026-10-10] [HOUSEKEEPING] `skills-manifest.md` corrigido — a afirmação de que "o diretório não é repo git / `git init` pendente" era **falsa**: o repo existe desde o kickoff (7 commits, `143d936` → `5a36035`). Ajustados §2 (linha do `git`, deps presentes), §4 (setup com as deps já corrigidas), §5 (DuckDB resolvido por ADR-006), RO-8 e §7 — ref: `docs/plans/skills-manifest.md`
- [2026-10-10] [DECISION] **F-032 concluída** — `docs/plans/DECISIONS_LOG.md` criado a partir do template com **12 substituições de fonte** (S-01 a S-12: ETTJ ANBIMA→Tesouro Direto, swaps SGS mortos em 2019, IMA via S3, "DataFit" inexistente, IFIX 2011+, ICON/IMOB janela própria, FII via Teva 2019+, FRED→Yahoo/MSCI/PTAX, S&P 500, EMBI+ inativo desde 30/07/2024, dívida bruta→DLSP) + 5 decisões operacionais. **Todas provisórias, aguardando aval de Edu/Alexandre** — ref: `docs/plans/DECISIONS_LOG.md`, `TODO.md §3`, RF-052/CA-128
- [2026-10-10] [HOUSEKEEPING] `README.md` reescrito para o estado real (149 linhas): o que é o projeto, prazo 2026-10-14, estrutura de pastas conferida no disco, setup (`uv sync --extra dev`; jupyter via `python -m jupyter lab`), ondas do PLAN, mapa de 10 documentos, as 8 decisões pendentes com link ao `TODO.md §4` e o estado "harness estruturado; nenhum extrator implementado" — ref: `README.md`
- [2026-10-10] [WIKI] `/wiki lint` → **amarelo**: `modules/` e `runbooks/` prometidos no índice estavam **vazios**; `index.md` não linkava SPEC, CONTRACTS, PLAN, ADRs, skills-manifest nem DECISIONS_LOG (que não existia); `overview.md §8` ainda dizia "próximo passo: `/SDD-avancado`" (já feito) e marcava a SPEC como "a criar"; `index.md` com 103 linhas (alvo ≤ 80). Nenhuma página órfã; único link quebrado era o placeholder `ADR-NNN-...` de `runbooks/_TEMPLATE.md` (esperado) — ref: lint 2026-10-10
- [2026-10-10] [WIKI] `/wiki repair` aplicado — criadas 7 páginas em `modules/` (`sgs`, `sidra`, `anbima`, `b3`, `internacional`, `canonical`, `regimes`, ≤ 39 linhas cada) com propósito, séries/RFs, fonte primária e fallback, armadilhas da pesquisa e features do TODO; criados `runbooks/reconstruir-dataset.md` (60) e `runbooks/fonte-fora-do-ar.md` (60); `index.md` reduzido a 78 linhas com todos os links conferidos; `overview.md §8` e seção de links atualizadas — ref: `docs/wiki/`
- [2026-10-10] [DECISION] `/SDD-avancado` em **modo autônomo**: `docs/specs/SPEC.md` v1.0 (52 RFs → **128 CAs**, Anti-SPEC §10 com 29 proibições + §11 com as 8 decisões provisórias), `docs/contracts/CONTRACTS.md`, contratos em `packages/shared/schemas/` (6 módulos pandera/pydantic + catálogo de **132 séries**: 99 `ok`, 8 `a_confirmar`, 10 descontinuadas, 14 descartadas, 1 paga), `TODO.md` com **40 features** (1 A · 21 B · 17 C · 1 D; 32 no pacote mínimo), `docs/plans/PLAN.md` (ondas sáb→ter) e **ADR-001..006 em status Proposta** — ref: `docs/specs/SPEC.md`, `docs/decisions/adr/`
- [2026-10-10] [WIKI] `wiki/architecture.md` atualizado para refletir SPEC v1.0 + schemas (147 linhas); `docs/plans/risk-classification.md` ganhou os exemplos concretos deste projeto por classe A/B/C/D — ref: `docs/wiki/architecture.md`
- [2026-10-10] [INGEST] PRD v1.0 gerado em **modo autônomo** por `/consultor-prd` (sem discovery humano): 52 RFs, 10 RNFs, 15 premissas marcadas `[PREMISSA]`, 8 riscos priorizados; **8 decisões bloqueiam implementação** (D1, D3, D5, D6, D12, L1, L2, L4) e foram registradas em `TODO.md §4` — ref: `docs/product/PRD.md`, `docs/research/fontes-de-dados.md`, `docs/research/metodologia-regimes-macro.md`
- [2026-10-10] [WIKI] `wiki/overview.md` reescrito para refletir o PRD v1.0 (síntese, sem duplicar) — ref: `docs/wiki/overview.md`
- [2026-10-10] [KICKOFF] estrutura Harness v3.2 criada e adaptada a projeto de dados/quant (AGENTS/CLAUDE/TODO/README/CI Python, `apps/pipeline` + `apps/analysis`, `packages/shared/schemas`, `data/raw|processed|canonical`) — ref: `docs/wiki/index.md`, `AGENTS.md`
- [2026-10-10] [INGEST] e-mail de escopo do Alexandre Kaercher transcrito e arquivado como fonte de verdade imutável — ref: `docs/product/ESCOPO-EMAIL-ALEXANDRE.md`
- [2026-10-10] [WIKI] wiki inicial populada (index, overview) — pesquisa de fontes em andamento em `docs/research/` por agentes paralelos — ref: `docs/wiki/overview.md`

---

*Para o histórico de 2026-10-11 em diante, ver `docs/wiki/log.md`.*
