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
- `VALIDATION` — validação de publicação (smoke do pacote, dataset congelado, reprodutibilidade)
- `WIKI` — manutenção da própria wiki (lint, repair, mover página)
- `HOUSEKEEPING` — manutenção do repo fora da wiki (deps, README, docs de plano)
- `HARNESS` — marco de fase do harness (kickoff, research, PRD, SDD, agents-protocol)
- `SDD` / `PRD` — marcos de documentação (usados nas entradas de 2026-10-10)

---

## 2026 — entradas atuais

> Entradas mais novas no topo.

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
2026-10-10 | CONSOLIDAÇÃO | inconsistências pós-agents-protocol corrigidas (PLAN dias da semana, branch main, risk-classification e templates adaptados a dados, TODO §1 populado, yfinance)
2026-10-10 | HARNESS | estruturação completa: kickoff → research → PRD → SDD → agents-protocol; 0 código de pipeline; aguardando 8 decisões
2026-10-10 | SDD | SPEC + Anti-SPEC + contratos pandera/pydantic + TODO com 40 features + 6 ADRs propostos
2026-10-10 | PRD | docs/product/PRD.md v1 gerado em modo autônomo a partir do e-mail + research; 8 decisões pendentes
2026-10-10 | KICKOFF | estrutura Harness v3.2 criada; e-mail de escopo arquivado

- [2026-10-10] [DECISION] `/SDD-avancado` em **modo autônomo**: `docs/specs/SPEC.md` v1.0 (52 RFs → **128 CAs**, Anti-SPEC §10 com 29 proibições + §11 com as 8 decisões provisórias), `docs/contracts/CONTRACTS.md`, contratos em `packages/shared/schemas/` (6 módulos pandera/pydantic + catálogo de **132 séries**: 99 `ok`, 8 `a_confirmar`, 10 descontinuadas, 14 descartadas, 1 paga), `TODO.md` com **40 features** (1 A · 21 B · 17 C · 1 D; 32 no pacote mínimo), `docs/plans/PLAN.md` (ondas sáb→ter) e **ADR-001..006 em status Proposta** — ref: `docs/specs/SPEC.md`, `docs/decisions/adr/`
- [2026-10-10] [WIKI] `wiki/architecture.md` atualizado para refletir SPEC v1.0 + schemas (147 linhas); `docs/plans/risk-classification.md` ganhou os exemplos concretos deste projeto por classe A/B/C/D — ref: `docs/wiki/architecture.md`
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
