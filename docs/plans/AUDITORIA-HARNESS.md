# AUDITORIA DO HARNESS — estrategia-macro-ldc-dados

> **Auditor independente** (não participou da construção) · **Data:** 2026-10-10 · **Modo:** somente
> leitura, exceto este arquivo. **Gabarito:** `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` (imutável).
>
> **Fora do escopo desta auditoria** (já em correção por outro agente, em paralelo): dias da semana no
> `PLAN.md`, termos de stack web em `risk-classification.md` / templates, `TODO §1` vazio, branch `main`,
> `yfinance`. Essas quatro não são reportadas aqui.
>
> **Método:** leitura integral de ESCOPO-EMAIL, README, wiki/index, CLAUDE, AGENTS, PRD, SPEC (incl. §10,
> §11, §13), CONTRACTS, os 6 schemas, TODO, PLAN, 6 ADRs, DECISIONS_LOG, prompts-cheatsheet, infra-ops,
> skills-manifest, research (RESUMO + seções conferidas de `fontes-de-dados.md` + metodologia §2/§7/§8);
> validação **executada** do catálogo (132 entradas, contagens por fonte/status/item) e execução real de
> `ruff check`, `ruff format --check` e `pytest tests/unit`.

---

## A. Rastreabilidade de escopo — os 13 itens do e-mail

Séries = contagem no `series_catalog_data.py` por `item_email`, com os status (`ok` / `a_confirmar` /
`descontinuada` / `descartada` / `paga`) verificados por execução.

| # | Item do e-mail | RF (PRD §5) | CAs (SPEC) | Feature(s) | Séries no catálogo (status) | Veredito |
|---|---|---|---|---|---|---|
| **A1** | PIB: IBC-Br **ou** PIB mensal/trimestral IBGE | RF-003, RF-004 | CA-006..010 | F-003, F-004 | 10 (9 ok · 1 a_confirmar) | **coberto** |
| **A2** | IPCA mensal (SGS 433) + Focus | RF-001 (+RF-007) | CA-001..003 | F-003 | 4 (4 ok) | **coberto** |
| **A3** | Expectativas Focus | RF-007 | CA-017..019 | F-010 | 7 (6 ok · 1 a_confirmar) | **coberto** (mas F-010 é corte nº 4 do PLAN §5) |
| **A4** | Selic Over (SGS 11) | RF-005 | CA-011..013 | F-003 | 7 (7 ok) | **coberto** |
| **A5** | Taxas de títulos públicos (Tesouro / ANBIMA) | RF-008 | CA-020..022 | F-005, F-009 | 2 (2 ok) | **coberto** |
| **A6** | ETTJ histórica ANBIMA → inclinação | RF-009 (+RF-010) | CA-023..029 | F-016, F-009 | 12 (10 ok · 1 paga · 1 descontinuada) | **parcial com substituição registrada** — S-01/S-02/S-03 → ADR-004 |
| **A7** | IPCA histórico completo (SIDRA) | RF-002 | CA-004, CA-005 | F-004 | 3 (3 ok) | **coberto** |
| **B1** | IMA-B / 5 / 5+ | RF-011 | CA-030..033 | F-002 | 6 (3 ok · 3 descontinuadas) | **coberto** (S-04 = S3 em vez de SGS) |
| **B2** | IRF-M / 1 / 1+ | RF-011 | CA-030..033 | F-002 | 10 (6 ok · 4 descontinuadas) | **coberto** |
| **B3** | CDI acumulado | RF-006 | CA-014..016 | F-003 | 2 (2 ok) | **coberto** |
| **B4** | INDX, ICON, IMAT, IEE, IMOB, IFNC, SMLL, IDIV, IBOV | RF-012 | CA-034..037 | F-006 | 13 (11 ok · 2 descartadas) | **parcial com substituição registrada** — S-07 (ICON 2007+, IMOB 2008+) → ADR-005 |
| **B5** | IFIX + segmentações (Tijolo/Papel/Logística/Shoppings) | RF-013, RF-014 | CA-038..042 | F-006, F-012 | 11 (7 ok · 4 descartadas) | **parcial com substituição registrada** — S-06 (IFIX 2011+) e S-08 (Teva 2019+) → ADR-005 |
| **C1** | Proxies internacionais (implícito no objetivo) | RF-015..017, RF-038, RF-039 | CA-043..050, CA-104..107 | F-007, F-011, F-026 | 29 (21 ok · 2 a_confirmar · 1 descontinuada · 5 descartadas) | **coberto** — implícito virado explícito em PRD §4.2 (`PRD.md:102-107`) |

**13/13 itens mapeados; 0 descobertos.** Todas as 3 substituições que afetam item do e-mail têm linha no
`DECISIONS_LOG` **e** ADR: S-01/02/03 → ADR-004 (`DECISIONS_LOG.md:26-28`), S-06/S-07/S-08 → ADR-005
(`DECISIONS_LOG.md:31-33`). As 6 restantes (S-04, S-05, S-09, S-10, S-11, S-12) estão no log sem ADR, o
que o próprio log declara e justifica como "operacionais" (`DECISIONS_LOG.md:39-41`).

**Ressalva (A-1).** **S-09** (FRED → Yahoo + MSCI + PTAX) é tratada como operacional, mas tem trade-off
real e desigual por série — o próprio log diz que `T10Y2Y` passa a ser proxy 10y−5y e que `DFF`/`FEDFUNDS`
**não tem substituto gratuito equivalente** (`DECISIONS_LOG.md:34`). Isso é mudança de fonte primária de um
RF (`PRD.md:154` ainda lista FRED como primária de RF-017). **Recomendo ADR-007 para S-09.**

---

## B. Scope creep — o que não deriva do e-mail nem do objetivo implícito

| O que | Onde | Classificação |
|---|---|---|
| Infra de extração, cache, calendário, orquestrador, testes de contrato, idempotência (F-001, F-008, F-029, F-030) | `TODO.md:114-141`, `:327-350`, `:966-1023` | **justificado** — reprodutibilidade (RNF-001/005) e mitigação de R1/R4 da pesquisa |
| Camada canônica, anti-look-ahead, página de limitações, DECISIONS_LOG (F-013..F-018, F-028, F-032) | `TODO.md:472-663`, `:939-962` | **justificado** — sem eles o número não é auditável; e-mail pede "estrutura de busca e extração" |
| Regimes V1/V2/V3 e métricas (F-019..F-022) | `TODO.md:667-795` | **justificado** — é a tradução direta de "como performaram em momentos semelhantes" |
| **IGP-M e IGP-DI** (SGS 189/190), `item_email = "-"`, `status = ok` | `series_catalog_data.py:236-252` | **expansão a cortar** — nenhum RF, CA, feature ou linha de DECISIONS_LOG; a própria `obs` diz "fora do escopo mínimo", mas o status continua `ok` |
| **IHFA** (ANBIMA S3), `item_email = "-"`, `status = ok` | `series_catalog_data.py:991` | **expansão a cortar** — contradiz `TODO.md:157`, que exclui IHFA explicitamente ("fora do e-mail") |
| **DLSP (SGS 4513)** + DBGG (13762, `descartada`) + `BCB_SGS_DBGG_PRE2008` — variável fiscal | `series_catalog_data.py:404`, S-12 em `DECISIONS_LOG.md:37` | **expansão a cortar** — dívida pública **não está no e-mail**; S-12 registra substituição de uma série que ninguém pediu e `macro_quarterly` **não tem coluna fiscal** (`macro_quarterly.py:31-95`): substituição sem consumidor |
| **IC-Br (27574/27575)**, `item_email = "-"` | `series_catalog_data.py:413` | **justificado** — é a feature `z_termos_troca_yoy` da V3 (`regimes.py:55-62`); recomendo trocar `item_email` de `-` para marcação de derivada metodológica |
| **UTIL** (B3), não pedido no e-mail, marcado `B4` | `series_catalog_data.py:1012` | **justificado (custo zero)** — mesma chamada do mesmo extrator; declarar como extra |
| **Núcleos do IPCA (4466, 11427)** e **valor adicionado (22108)** marcados `A2`/`A1` | `series_catalog_data.py:220`, `:229`, `:365` | **expansão a cortar / erro de etiqueta** — não são o que A1/A2 pedem; etiquetar item do e-mail em série não pedida **inflaciona artificialmente a cobertura** medida por `item_email` |
| **11 séries FRED com `status = ok`** (DGS10, DGS2, T10Y2Y, T10Y3M, VIXCLS, DFF, FEDFUNDS, DTWEXBGS, DEXBZUS, T10YIE) | `series_catalog_data.py:1204-1216` | **expansão a cortar enquanto o FRED estiver bloqueado** — ver C-3 |
| **Fonte `MANUAL`** no enum, único uso `GOLD_SPOT_USD` (a_confirmar, bloqueada por G-03) | `series_catalog.py:45`, `series_catalog_data.py:1231` | **justificado com ressalva** — `MANUAL` como fonte válida convive mal com Anti-SPEC §10.4.22 ("nunca editar `data/` à mão"); restringir o uso no schema ou documentar o único caso permitido |
| CVM, COTAHIST, EMBI+, ICE BofA, ETFs, PME/PNADC | catálogo, status `descartada`/`descontinuada` | **justificado** — registrados como rotas avaliadas e **não** usadas; não entram no pacote mínimo |
| Pacote estendido F-033..F-040 | `TODO.md:1064-1100` | **justificado** — fora do compromisso, fronteira explícita em `TODO.md:69-70` |

**Veredito B:** não há expansão estrutural (nenhuma feature fora do e-mail no caminho crítico). O creep é
**no catálogo**, não no plano: ~7 séries `ok` sem item do e-mail e sem RF, mais 11 FRED `ok` numa fonte
sabidamente bloqueada. Custo baixo, mas contaminam toda métrica calculada sobre `status = ok`.

---

## C. Consistência numérica

| Contagem alegada | Verificação | Resultado |
|---|---|---|
| **52 RFs** | `RF-001..RF-052`, sem buraco, extraídos da SPEC | ✅ bate (PRD `:220`, SPEC `:840`) |
| **128 CAs** | `CA-001..CA-128`, 128 únicos, 0 duplicados, 0 faltando | ✅ bate (SPEC `:840`) |
| **40 features** | 39 cabeçalhos `### [ ] F-NNN` + F-032 em §3 Concluído (`TODO.md:1113`) | ✅ bate |
| **132 séries** | `load`/contagem executada em `SERIES_CATALOG`: 132, 0 `series_id` duplicado | ✅ bate |
| **8 decisões bloqueantes** | D1, D3, D5, D6, D12, L1, L2, L4 (`TODO.md:1124-1155` ≡ `PRD.md:385-397` ≡ `SPEC.md:745-754`) | ✅ bate |
| **6 ADRs** | ADR-001..006, **todos em `Proposta`** (linha 3 de cada arquivo) | ✅ bate |
| **12 substituições S-01..S-12** | `DECISIONS_LOG.md:26-37`, 12 linhas, 12 provisórias, 0 confirmadas | ✅ bate |
| Catálogo por status | ok 99 · a_confirmar 8 · descontinuada 10 · descartada 14 · paga 1 = 132 | ✅ bate `CONTRACTS.md:103-109` |
| Catálogo por fonte | SGS 36 · B3 13 · FRED 13 · Yahoo 12 · S3 11 · SIDRA 9 · DERIVADO 7 · Ipeadata 7 · Olinda 6 · Teva 6 · MSCI 5 · ANBIMA_WEB 4 · Tesouro 1 · CVM 1 · MANUAL 1 | ✅ bate `CONTRACTS.md:111-119` |
| "63 cobrem 1T2006" | contagem executada: 63 entradas `ok` com `data_inicio <= 2006-01-02` | ✅ bate `CONTRACTS.md:105` |
| SPEC §13 cobre features | F-001..F-032 (32) — pacote mínimo; F-033..F-040 sem CA (fase 2) | ✅ coerente com `TODO.md:69-70` |

**Divergências encontradas**

| # | Divergência | Evidência |
|---|---|---|
| **C-1** | PLAN manda a Onda 0 fechar com "`DECISIONS_LOG.md` com **8** substituições registradas" — o log tem **12** e F-032 já está concluída | `PLAN.md:48` vs `DECISIONS_LOG.md:39`, `TODO.md:1113` |
| **C-2** | Métrica de sucesso do PRD é **não calculável** como está escrita: "séries com `data_inicio ≤ 2006-01-31` ÷ total pedido". **24 das 99 séries `ok`** têm `data_inicio = None` (entre elas SGS 11, 12, 432, 1178, 1, 10813 — o núcleo do caminho crítico). Lida ao pé da letra, a cobertura sai 63/99 = 64% e "falha" a meta de 90% por falta de medição, não por falta de dado. Agrava: PRD usa limiar `2006-01-31`, o schema usa `2006-01-02` | `PRD.md:245` vs `series_catalog.py:175-180`; contagem executada |
| **C-3** | `usavel_no_pacote_minimo` = `status is OK` ignora `fonte_instavel`. Resultado: as 11 séries FRED contam como usáveis no pacote mínimo, enquanto `skills-manifest §3` declara "**nenhum requisito pode depender do FRED nesta máquina**" (bloqueio em camada de aplicação, 3/3 tentativas) e as IGP-M/IGP-DI contam como usáveis com `obs` dizendo "fora do escopo mínimo" | `series_catalog.py:182-185`; `skills-manifest.md:85-101`; `series_catalog_data.py:243`, `:251` |
| **C-4** | `RegimeNeighborsSchema` tem PK de **5** colunas (`+ k_usado, restrito_pos_2016`), mas CA-089 especifica PK `(quarter_ref, rank, metrica)`. O desvio é **tecnicamente correto** (as variantes coexistem) e está documentado no espelho, mas a SPEC tem precedência sobre o schema (`SPEC.md:12-13`) e não foi atualizada | `regimes.py:153` vs `SPEC.md:449-450`; `CONTRACTS.md:242` |
| **C-5** | `infra-ops §0` diz "3 commits de documentação"; `skills-manifest §2` diz 7; o repositório tem **8** | `infra-ops.md:17` vs `skills-manifest.md:48`; `git rev-list --count HEAD` = 8 |
| **C-6** | O erro de dia da semana do PLAN **também está no README** (fora do arquivo que o outro agente está corrigindo): "Comitê de Alocação: 2026-10-14 (terça)" e a tabela de ondas "3/4 = seg 13/10", "5 = ter 14/10". 2026-10-10 é sábado → 13/10 é terça e 14/10 é quarta (coerente com "próxima quarta-feira" do e-mail) | `README.md:20`, `:113-120`; `ESCOPO-EMAIL-ALEXANDRE.md:8` |
| **C-7** | `pyproject.toml:35-37` afirma "nenhum pacote Python existe em `apps/` ou `packages/`" — mas `packages/shared/schemas/` já é pacote, com `__init__.py` e imports absolutos `from packages.shared.schemas...` | `pyproject.toml:35-38` vs `packages/shared/schemas/__init__.py:20-40` |

---

## D. Consistência de identificadores (amostra de 15 séries)

Conferidas uma a uma contra `docs/research/fontes-de-dados.md` (seções A1, A3, B6, B8, B9, C10).

| # | `series_id` | Identificador no catálogo | `data_inicio` | `confianca` | Fonte na pesquisa | Resultado |
|---|---|---|---|---|---|---|
| 1 | `BCB_SGS_433` | 433 | 1980-01-01 | CONFIRMADO | `fontes-de-dados.md:86` (01/1980) | ✅ |
| 2 | `BCB_SGS_11` | 11 | *None* | CONFIRMADO | `:88` (canário 03/01/2005 = 0.064826) | ⚠️ identificador e tag ok; **início não medido** (ver C-2) |
| 3 | `BCB_SGS_24364` | 24364 | 2003-01-01 | CONFIRMADO | `:96` (jan/06 = 79.44731, início 2003) | ✅ |
| 4 | `BCB_SGS_22109` | 22109 | 1996-01-01 | CONFIRMADO | `:101` (2006T1 = 131.74) | ✅ |
| 5 | `BCB_SGS_7806` | 7806 · `data_fim` 2019-09-30 | — | CONFIRMADO / descontinuada | `:117` (swap DI×pré morre 30/09/2019) | ✅ |
| 6 | `SIDRA_1737_V2266` | `t/1737 v/2266` | 1979-12-01 | CONFIRMADO | `:251-271` | ✅ |
| 7 | `SIDRA_1621_V584_90707` | `t/1621 v/584 c11255/90707` | 1996-01-01 | CONFIRMADO | `:101`, `:296` | ✅ |
| 8 | `ANBIMA_IMAB` | `IMAB` | 2003-09-16 | CONFIRMADO | `:563` (1ª data 2003-09-16; 723,07) | ✅ |
| 9 | `ANBIMA_IRFM1MAIS` | `IRFM1MAIS` | 2000-12-01 | CONFIRMADO | `:567` | ✅ (inclusive a pegadinha `5MAIS`/`1MAIS`) |
| 10 | `ANBIMA_IMAC` | `IMAC` · `data_fim` 2021-04-01 | 2001-12-03 | CONFIRMADO / descontinuada | `:570` | ✅ |
| 11 | `B3_IEEX` | `IEEX` (não `IEE`) | 1994-01-03 | CONFIRMADO | `:749` | ✅ |
| 12 | `B3_IFIX` | `IFIX` | 2010-12-30 | CONFIRMADO · `is_total_return=True` | `:769` | ✅ |
| 13 | `YAHOO_GSPC` | `^GSPC` | 1927-12-30 | CONFIRMADO_SUB | `:1041` | ✅ |
| 14 | `MSCI_ACWI_NETR` | `892400 / NETR` | 2000-12-29 | CONFIRMADO_SUB | `:1066` (NETR início 2000-12-29) | ✅ |
| 15 | `TEVA_FII_TIJOLO` | `3.2.2` | 2019-01-02 | CONFIRMADO_SUB · `licenca_restrita=True` | `:872-884` | ✅ |

**15/15 identificadores corretos; 14/15 `data_inicio` corretas; 15/15 tags de confiança coerentes com a
convenção da pesquisa** (`CONFIRMADO` para acesso próprio, `CONFIRMADO_SUB` para agente auxiliar,
`NAO_VERIFICADO` para as 7 séries `DERIVADO`). Os 3 valores-canário da SPEC (IBOV 38.484,84; IMA-B
723,070317; MSCI ACWI NETR 121,3858) e o CDI 2006 = 15,0271% (249 d.u.) foram localizados na pesquisa
(`fontes-de-dados.md:725`, `:683`, `fontes-de-dados-RESUMO.md:104`). **Nenhum identificador inventado:**
as 8 entradas sem confirmação usam a string literal `a_confirmar` com `status = a_confirmar`, como o
validador exige (`series_catalog.py:153-166`). Única divergência da amostra: item 2 (D-1, mesma causa de C-2).

---

## E. Look-ahead e Anti-SPEC

| Pergunta | Resposta | Evidência |
|---|---|---|
| A Anti-SPEC proíbe classificar T com dado publicado depois do fim de T sem flag? | **Sim**, item 7 da §10.2, com a `revised` declarada legítima mas obrigatoriamente rotulada | `SPEC.md:679-681` |
| `macro_quarterly` tem campo de `asof`/lag? | **Parcial** — tem `lag_adjusted` (bool) + `is_estimated` + `fonte_versao`, e um check que impede misturar `asof` e `revised` na mesma tabela | `macro_quarterly.py:86-95`, `:115-118` |
| `regimes` tem campo de lag/divergência? | **Sim** — `lag_adjusted`, `trocou_vs_revised`, `especificacao_congelada`, `versao_especificacao` | `regimes.py:88-100` |
| Existe `vintage`? | **Sim, mas só em `raw_series`** (`vintage`, `collected_at`, PK `(series_id, date, vintage)`) | `raw_series.py:55-70` |
| CA correspondente existe? | **Sim** — CA-072 (nenhuma coluna `asof` usa dado divulgado após o fim de T), CA-073 (% de troca de rótulo), CA-074 (> 25% ⇒ "modelo não operacional"); insumo garantido por `lag_divulgacao_dias` obrigatório no catálogo | `SPEC.md:378-383`, `series_catalog.py:135` |

**E-1 (lacuna real).** RF-047/CA-120 exigem que **qualquer** valor do canônico responda "de onde veio?" via
`source`, `series_id`, `vintage` e `collected_at` (`SPEC.md:596-597`). `macro_quarterly` **não tem nenhuma
das quatro colunas** — só `fonte_versao` (hash do código). `asset_returns_quarterly` tem `source` e
`series_id`, mas não `vintage` nem `collected_at` (`asset_returns_quarterly.py:102-104`). Consequência: a
rastreabilidade coluna→série existe no código e no catálogo, **não no dado**, e CA-120 não é satisfazível
como escrito para `macro_quarterly`. Decidir: (a) acrescentar `vintage_max`/`collected_at_max` por linha,
ou (b) reescrever CA-120 restringindo-o a `raw_series` + mapa de colunas versionado. **Qualquer das duas
exige autorização humana** (altera SPEC ou schema canônico = classe C).

**E-2 (guarda mais fraca que o CA que ela alega cobrir).** O check `sem_trimestre_antes_do_inicio_da_serie`
compara **apenas o ano** (`q_ano >= ini_ano`), logo aceita `2010Q1..Q3` para o IFIX (início 2010-12-30),
`2007Q1..Q3` para o IMOB (2007-12-28) e `2006Q1..Q3` para o ICON (2006-12-28) — exatamente os três casos
que a Anti-SPEC §10.1.1 nomeia como backfill proibido. O docstring afirma cobrir CA-063.
Evidência: `asset_returns_quarterly.py:119-124` vs `SPEC.md:339-341` e `SPEC.md:665-667`.

**E-3.** O check `exclui_vizinhos_adjacentes` só verifica `quarter_ref != quarter_neighbor`, não a exclusão
dos 2 trimestres anteriores que o docstring cita (`regimes.py:155-158`). O `CONTRACTS.md:249-250` **declara
honestamente** essa limitação ("verificada no teste da feature"); o defeito é só o docstring enganoso.

---

## F. Executabilidade — subagente Opus com o Prompt 4 para F-002

O Prompt 4 (`prompts-cheatsheet.md:390-471`) é, no conteúdo, suficiente: ordem de leitura, arquivos
permitidos/proibidos, 3 valores-canário com o do IMA-B explícito, fixture de erro obrigatória, teste de
contagem mínima, critério de `BLOQUEADO — FONTE INDISPONÍVEL`, formato do relatório. A pesquisa §B6 traz
endpoint, SLUGs, magic bytes, colunas e rótulos instáveis. A amostra real já está no disco
(`data/raw/anbima-ima/IMAB.xls`, 393.685 B). **Ainda assim, o subagente trava ou improvisa em 6 pontos:**

| # | Falta | Evidência | Gravidade |
|---|---|---|---|
| F-1 | `apps/pipeline/` **não existe como pacote** — só `.gitkeep`; sem `apps/__init__.py`, sem `apps/pipeline/extract/`. O Prompt 4 manda "usar o cliente HTTP de F-001" (`:428`), que também não existe. Ordenação resolve (F-001 é Onda 0), mas **nada no harness diz qual é o nome do pacote importável** (`apps.pipeline.extract...`? `pipeline...`?) — e o `ci.yml` comentado usa `python -m pipeline.build_canonical`, incompatível com o layout `apps/pipeline/` | `find apps` → 2 `.gitkeep`; `ci.yml:76`, `:114-116` | **alta** |
| F-2 | **`tests/fixtures/` não existe** e não há `conftest.py` em nenhum nível, embora `AGENTS.md:63`, CLAUDE §3 e RF-049 o tratem como dado | `ls tests/` → só `unit/ integration/ contract/ e2e/` | média (o subagente cria) |
| F-3 | **Import dos schemas não resolve em instalação limpa.** `pyproject` tem `bypass-selection = true` (nenhum pacote no wheel) e o pytest não tem `pythonpath`; sem `conftest.py` na raiz, o modo `prepend` insere `tests/unit`, não a raiz. `from packages.shared.schemas import ...` tende a falhar no CI. Correção determinística: `[tool.pytest.ini_options] pythonpath = ["."]` **ou** declarar `packages = [...]` no hatch | `pyproject.toml:35-38`, `:61-68`; ausência de `conftest.py` | **alta — verificar com 1 comando antes da Onda 0** |
| F-4 | **Conflito de lista de arquivos.** O Feature Contract de F-002 permite `tests/contract/test_anbima_s3.py`, mas a própria tabela de testes do item exige 2 testes `unit` — e `tests/unit/test_anbima_s3.py` **não está na lista**. Por `AGENTS.md §18` o padrão é `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT`; o Prompt 4 permite o arquivo. Um subagente literal pausa | `TODO.md:160-168` vs `prompts-cheatsheet.md:404-408` | média |
| F-5 | Nenhum módulo de **config de paths**: `ExtractorConfig.destino_raw` é relativo (`^data/raw/[a-z0-9\-/]+$`) e não existe `settings`/raiz de projeto. Está no escopo de F-001, mas o Prompt 4 não diz | `series_catalog.py:220` | baixa |
| F-6 | F-005 e F-016 apontam para `docs/wiki/modules/tesouro.md`, que **não existe** (há anbima, b3, canonical, internacional, regimes, sgs, sidra) e não está no índice da wiki | `TODO.md:250`, `:585`; `ls docs/wiki/modules/` | baixa |

**F-7 — o CI N1 está vermelho hoje, antes de qualquer código** (medido nesta auditoria, na raiz do repo):

| Passo do `ci.yml` | Resultado real | Causa |
|---|---|---|
| `ruff check .` | **exit 1 — 96 erros** | `[tool.ruff] exclude` não cobre `.claude/`; todos os 96 erros estão em `.claude/skills/**/*.py` (código de skill vendorizado). Em `packages apps tests infra`: *All checks passed* |
| `ruff format --check .` | **exit 1 — 13 arquivos** | 11 em `.claude/`, **2 do projeto**: `packages/shared/schemas/regimes.py:126` e `series_catalog_data.py:25` |
| `pytest tests/unit -m "not network"` | **exit 5** (`no tests ran`) | suíte vazia; GitHub Actions trata ≠0 como falha |

Como "uma onda só abre com a anterior verde no CI" (`AGENTS.md:212`, `PLAN.md:34`), **o gate do harness
está intransponível por construção**. Correções: (a) `exclude = [..., ".claude"]` no ruff; (b) `ruff
format` nos 2 arquivos do projeto; (c) `--exitfirst`-neutro para suíte vazia (`addopts` com
`--exitcode-on-no-tests` não existe no pytest 8 → usar um teste-sentinela na Onda 0 ou
`|| [ $? -eq 5 ]` no passo). Há também `warning: PD901 removed` no ruff (regra inexistente em
`pyproject.toml:51`) e o lixo não ignorado `grep.exe.stackdump` na raiz.

---

## G. Prazo

**Entrega do pacote mínimo até 13/10 para revisão do Edu:** sim, **no papel**. A Onda 4 do PLAN entrega
heatmap + timeline + tabela de 1 página + canônico + relatório de saída em 13/10, declarado como "marco de
revisão humana" (`PLAN.md:126-140`), o que casa com PRD §7 ("heatmap pronto até 2026-10-13") e com o
README. A Onda 5 (classe D) fica em 14/10, dia do Comitê.

**Caminho crítico** (`PLAN.md:191`): F-001 → F-003/F-002/F-006 → F-013 → F-014 → F-017 → F-019 → F-022 →
F-023 → F-031. Correto: nenhuma das features declaradas "nunca cortar" (`PLAN.md:222`) está fora dele.

**Risco nº 1 — compressão da classe C em 13/10.** O PLAN coloca **8 features classe C** (F-013..F-022, mais
F-026 e F-029) entre a noite de 11/10 e 13/10, e cada uma exige, por contrato: Feature Contract detalhado,
CI N2 verde, **reconstrução completa de `data/canonical/` a partir de zero**, **diff numérico vs. a versão
anterior** e **revisão numérica independente por um subagente que não calculou**
(`TODO.md:1212-1219`, `AGENTS.md:39`, `PLAN.md:203-205`). Com o limite de "no máximo 2 classe C em
paralelo, nunca na mesma tabela", a cauda da Onda 2 + Onda 3 + Onda 4 disputam o **mesmo dia 13/10** — o
mesmo dia do marco de revisão do Edu. É aqui que o cronograma estoura, não na extração.

**Riscos 2 e 3.** (2) **ADR-006** (armazenamento + convenção de retorno/alinhamento) precisa ser validado
pelo Edu **antes da Onda 2** e está em `Proposta` (`PLAN.md:247`); é DoR aberta de F-013 e F-014
(`TODO.md:479-480`, `:514`), ou seja, a Onda 2 começa com DoR incompleta → `BLOQUEADO` por `AGENTS.md:160`.
(3) **V3 pode cair abaixo do piso contratual de features**: `FEATURES_V3` tem 6 entradas, mas
`z_ipca_desvio_meta` depende de `ipca_meta` (gap **G-02**, declarado "fora do caminho crítico" em
`SPEC.md:759-762`), `z_juro_real_exante` depende do Focus (F-010, corte nº 4) e `z_inclinacao` depende de
F-016 (corte nº 5). Se Focus **e** curva caírem, sobram 3-4 features — e
`RegimeNeighborsSchema.n_features` tem `ge=5` (`regimes.py:130-135`), então o schema **rejeita** o único
cenário de corte que o PLAN prevê como aceitável. O plano B da SPEC (CA-086) cobre 5, não 4.

---

## H. Veredito final

### MUDANÇAS_SOLICITADAS

O harness é, no conteúdo, melhor que a média: escopo rastreado item a item, 128 CAs sem buraco, 132 séries
com identificador real e tag de confiança herdada da pesquisa, Anti-SPEC com 29 proibições que atacam o
modo de falha dominante, valores-canário definidos antes de existir código, substituições registradas com
os 4 campos e ADR nas que afetam o e-mail. **Não encontrei dado inventado, identificador fabricado nem
escopo estrutural fora do e-mail.** O que impede o "pronto para iniciar a Onda 0" é operacional e pequeno:
o gate de CI não passa hoje, o caminho de import não está resolvido e duas guardas de contrato são mais
fracas do que os CAs que dizem cobrir.

| Pri | Correção | Onde | Esforço |
|---|---|---|---|
| **P0** | Deixar o CI N1 verde: `exclude` do ruff cobrindo `.claude/`; `ruff format` em `regimes.py` e `series_catalog_data.py`; tratar `pytest` exit 5 (ou nascer com 1 teste na Onda 0) | `pyproject.toml:43-56`, 2 arquivos de schema, `ci.yml:51` | 20 min |
| **P0** | Resolver o import dos schemas: `pythonpath = ["."]` no pytest **ou** `packages = ["packages/shared"]` no hatch; corrigir o comentário obsoleto | `pyproject.toml:35-38`, `:61-68` | 10 min |
| **P0** | Criar `tests/fixtures/` (com `.gitkeep`) e um `conftest.py` na raiz antes de briefar a Onda 1 | `tests/` | 5 min |
| **P0** | Alinhar PLAN × DECISIONS_LOG: "8 substituições" → 12 (C-1) | `PLAN.md:48` | 2 min |
| **P1** | Fechar a DoR da Onda 2: Edu aceita (ou rejeita) **ADR-006** — sem isso F-013/F-014 nascem `BLOQUEADO` | `ADR-006`, `TODO.md:479` | decisão humana |
| **P1** | Endurecer `sem_trimestre_antes_do_inicio_da_serie` para comparar **trimestre**, não ano (E-2) — é a guarda do CA-063 e da Anti-SPEC §10.1.1 | `asset_returns_quarterly.py:119-124` | 15 min (classe C) |
| **P1** | Decidir E-1 (rastreabilidade por linha no canônico): acrescentar `vintage`/`collected_at` ou reescrever CA-120 | `SPEC.md:596`, `macro_quarterly.py` | decisão humana |
| **P1** | Tornar a métrica de cobertura calculável: preencher `data_inicio` das 24 séries `ok` sem início medido (a pesquisa diz "Cobre 2006: Sim" para elas) ou redefinir a métrica; alinhar o limiar 2006-01-31 × 2006-01-02 (C-2) | `series_catalog_data.py`, `PRD.md:245` | 1 h |
| **P1** | Separar "identificador válido" de "entra no pacote mínimo": `usavel_no_pacote_minimo` deve excluir `fonte_instavel` (FRED) e séries com `item_email = "-"`; ou mover IGP-M/IGP-DI/IHFA/DLSP para `descartada` (B, C-3) | `series_catalog.py:182-185`, `series_catalog_data.py` | 30 min |
| **P1** | Resolver o piso de features da V3 antes da Onda 3: ou baixar `n_features` para `ge=4` com declaração explícita, ou promover G-02/`ipca_meta` a item do caminho crítico (risco 3 de G) | `regimes.py:130-135`, `SPEC.md:759-762` | 30 min + decisão |
| **P1** | Resolver o conflito de arquivos permitidos de F-002 (F-4): incluir `tests/unit/test_anbima_s3.py` no Feature Contract | `TODO.md:160` | 2 min |
| **P2** | ADR-007 para S-09 (FRED → Yahoo/MSCI/PTAX): tem trade-off real e muda fonte primária de RF-017 (A-1) | `docs/decisions/adr/` | 30 min |
| **P2** | Corrigir os dias da semana **no README** (C-6), as contagens de commits de `infra-ops`/`skills-manifest` (C-5) e a PK de `regime_neighbors` na SPEC (C-4) | `README.md:20`, `:113-120`; `infra-ops.md:17`; `SPEC.md:449` | 15 min |
| **P2** | Corrigir docstrings que prometem mais do que verificam (E-3) e criar `docs/wiki/modules/tesouro.md` (F-6); remover `grep.exe.stackdump`; limpar o `ignore = ["PD901"]` morto | `regimes.py:157`, wiki, `.gitignore`, `pyproject.toml:51` | 20 min |
| **P2** | Restringir ou documentar o uso de `Fonte.MANUAL` (único caso: `GOLD_SPOT_USD`, bloqueado por G-03) | `series_catalog.py:45` | 10 min |

**Reclassificação se os P0 forem feitos:** APROVADO para iniciar a Onda 0 (F-009 + F-001 + F-032 não
dependem de nenhuma das 8 decisões, conforme `TODO.md:1165-1168`). Os P1 devem estar fechados **antes da
Onda 2** — todos tocam camada canônica, regimes ou a métrica de aceite da entrega.

### O que não consegui verificar

- **Não executei o pipeline** (não existe) nem validei os schemas em runtime: `pandera`, `pyarrow` e
  `duckdb` não estão instalados nesta máquina (confirmado; coerente com `skills-manifest.md:56-60`). A
  validação do catálogo foi feita importando `series_catalog_data.py` isoladamente — portanto as regras
  **pydantic** de `SeriesCatalogEntry` (coerência `a_confirmar`, `data_fim < data_inicio`) **não foram
  executadas**, só lidas.
- **Não conferi valor contra a fonte viva** (nenhuma chamada de rede): os valores-canário foram conferidos
  contra `docs/research/`, não contra BCB/B3/ANBIMA/MSCI.
- **F-3 é inferência do comportamento do pytest/hatchling, não medição** — não instalei o projeto para não
  violar o modo somente-leitura. Verificação em 1 comando:
  `pip install -e . && python -c "import packages.shared.schemas"`.
- Não auditei linha a linha `fontes-de-dados.md` (1.421 linhas) nem `prompts-cheatsheet.md` fora do
  Prompt 4; a amostra de identificadores é de 15 das 132 séries, escolhida para cobrir SGS, SIDRA,
  ANBIMA_S3, B3_API, YAHOO, MSCI e TEVA.

---

*Auditoria produzida por agente independente em 2026-10-10. Este arquivo é o único que a auditoria escreveu;
nenhuma correção foi aplicada. Divergências com o estado do repositório após as correções em curso devem ser
reconferidas antes de usar esta lista como checklist.*
