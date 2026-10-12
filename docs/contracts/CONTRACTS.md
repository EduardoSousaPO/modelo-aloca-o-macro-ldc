# CONTRACTS — Estratégia Macro LDC

> **Espelho legível.** A **fonte de verdade são os schemas em `packages/shared/schemas/`**
> (`pandera` para DataFrame, `pydantic` para catálogo e config de extrator). Este arquivo descreve —
> nunca duplica a definição e nunca a contradiz.
>
> **Versão:** 1.3 (2026-10-11, acréscimo do §10 — as views web de F-W001, com a tabela de
> apresentação e o eixo de cor do acerto com o módulo do portal) · 1.2 (2026-10-11, Onda 2: `raw_series`/`series_catalog` materializados por F-013,
> tabela `alinhado_trimestral` de F-014, catálogo 134 → **138** por D-i/F-016) — **Referência:**
> `docs/specs/SPEC.md` v1.0 (RF-019..RF-032), `docs/research/metodologia-regimes-macro.md §6`.
>
> **Regra absoluta:** se o agente precisa de um tipo/coluna que ainda não existe, ele **cria primeiro
> em `packages/shared/schemas/`** e só depois implementa o extrator ou a transformação.
> Alterar schema canônico é **classe C** (`AGENTS.md §2`).

---

## 0. Mapa dos arquivos

```
packages/shared/schemas/
├── __init__.py                 ← re-export de tudo
├── raw_series.py               ← RawSeriesSchema, ProcessedSeriesSchema            (pandera)
├── series_catalog.py           ← SeriesCatalogEntry, ExtractorConfig, SeriesCatalogSchema,
│                                  SeriesCatalogMaterializedSchema, enums,
│                                  load_catalog()                                   (pydantic+pandera)
├── series_catalog_data.py      ← O CATÁLOGO COMO DADO — 138 séries
├── alinhado_trimestral.py      ← AlinhadoTrimestralSchema (grade trimestral long)  (pandera)
├── macro_quarterly.py          ← MacroQuarterlySchema, MacroQuarterlyProvenanceSchema,
│                                  MacroQuarterlyAsofProvenanceSchema (subclasse)   (pandera)
├── asset_returns_quarterly.py  ← AssetReturnsQuarterlySchema,
│                                  RegimeAssetMetricsSchema                         (pandera)
├── regimes.py                  ← RegimesSchema, RegimeNeighborsSchema,
│                                  RegimesV1Schema, RegimeNeighborsV3Schema, enums  (pandera)
├── internacional.py            ← InternacionalPorRegimeSchema,
│                                  InternacionalPesosSchema (F-026, §6a)            (pandera)
├── calendario.py               ← CalendarioDiasUteisSchema (grade de dias úteis)   (pandera)
└── web_views.py                ← MetaWeb, PonteiroCurrent, as 6 views do portal,
                                   unidades + apresentação, VIEWS (F-W001, §10)     (pydantic)
```

Fronteiras onde a validação é **obrigatória** (`wiki/architecture.md §4`):

| Fronteira | Schema |
|---|---|
| saída de cada extrator → `data/processed/` | `ProcessedSeriesSchema` |
| `data/processed/` → `data/canonical/` | `RawSeriesSchema` + schema da tabela destino |
| `data/canonical/series_catalog.parquet` (catálogo **materializado**, 26 colunas) | `SeriesCatalogMaterializedSchema` (§2.4) |
| `raw_series` → grade trimestral (`data/canonical/alinhado_trimestral.parquet`) | `AlinhadoTrimestralSchema` (§8) |
| regimes + retornos → internacional (`data/canonical/internacional_*.parquet`) | `InternacionalPorRegimeSchema`, `InternacionalPesosSchema` (§6a) |
| entrada e saída de `data/canonical/` | `MacroQuarterlySchema`, `MacroQuarterlyProvenanceSchema`, `MacroQuarterlyAsofProvenanceSchema`, `AssetReturnsQuarterlySchema`, `RegimesSchema`, `RegimesV1Schema`, `RegimeNeighborsSchema`, `RegimeNeighborsV3Schema`, `SeriesCatalogSchema` |
| config de extrator / parâmetros de janela | `ExtractorConfig` (pydantic) |
| catálogo de séries | `SeriesCatalogEntry` (pydantic) |
| `data/canonical/` → JSON do portal (`<destino>/<tag>/*.json`) | `MetaWeb`, `PonteiroCurrent`, as 6 views de `VIEWS` (§10) |

---

## 1. `raw_series` — série na granularidade nativa (RF-020)

`packages/shared/schemas/raw_series.py` → `RawSeriesSchema`

| Coluna | Tipo | Nulo? | Regra |
|---|---|---|---|
| `series_id` | str | não | casa `^[A-Z0-9_\.\^=\-]+$`; existe no `series_catalog` |
| `date` | datetime | não | data de **referência** do dado |
| `value` | float | **sim** | nulo só por ausência esperada (feriado, mês sem divulgação) — nunca interpolado |
| `source` | str | não | enum de 15 fontes (`BCB_SGS`, `IBGE_SIDRA`, `ANBIMA_S3`, `B3_API`, `TEVA_GCS`, `YAHOO`, `MSCI`, `FRED`, `IPEADATA`, `CVM`, `DERIVADO`, `MANUAL`, ...) |
| `freq` | str | não | `D` \| `M` \| `Q` \| `A` — **frequência nativa** |
| `vintage` | datetime | sim | safra da extração: **a data (sem hora) do `collected_at`**, que sai do `obtido_em` do manifesto do bruto (D-b) — nulo só para tabela que não é série |
| `unit` | str | não | `%`, `%/dia`, `%a.a.`, `pp`, `index`, `BRL`, `USD`, `ratio`, `bps`, `R$ milhoes` |
| `collected_at` | datetime | não | quando o pipeline baixou |

- **PK:** `(series_id, date, vintage)` → duas extrações do mesmo ponto coexistem como vintages (CA-056).
- **Convenções da camada processada** (consolidação da Onda 1, `DECISIONS_LOG §2.1`, provisórias):
  **(a)** `date` de série **mensal/trimestral** é o **fim de período civil** (`2026-09-30` para o
  IPCA de setembro), o que faz duas fontes da mesma série casarem por `date` — SGS 433 × SIDRA
  `t/1737 v/63` em 273 meses e SGS 22109 × SIDRA `t/1621 v/584` em 90 trimestres, `max|dif| = 0`;
  **(b)** `collected_at` e `vintage` saem do **manifesto do bruto**, não do relógio da rodada, o
  que torna o reprocessamento `--offline` byte-idêntico; **(c)** `vintage` é a **data** desse
  `collected_at`, sem hora, porque identifica a *safra* — é o que mantém a PK única quando a
  fonte revisa o passado **sem** acrescentar ponto novo (IBGE/IBC-Br).
- **Check de DataFrame:** `sem_data_futura` — `date <= collected_at` (pega a meta Selic com data futura).
- `strict=True`: coluna fora do schema **falha**. É o que impede DataFrame ad hoc (Anti-SPEC §10.4.24).
- `ProcessedSeriesSchema` herda o mesmo contrato para `data/processed/`.

### 1.1 Materialização — `data/canonical/raw_series.parquet` e `relatorio_build.json` (F-013)

`apps/pipeline/canonical/build_raw_series.py` (CLI
`python -m apps.pipeline.canonical.build_raw_series [--offline] [--sem-duckdb]`) é o único produtor
desta camada. **O que o contrato precisa dizer sobre a materialização:**

- **`raw_series` é um *union* validado de `data/processed/`, e nada mais** — zero agregação,
  reamostragem, `ffill` ou arredondamento. Cada série do canônico é idêntica, **célula a célula**,
  ao Parquet de origem (teste `test_real_cada_serie_e_identica_linha_a_linha_a_sua_origem`).
- **O Parquet é reescrito inteiro a cada build; não há `append`.** Série nova em `data/processed/`
  (F-010, F-011, F-012, F-016) só aparece em `raw_series` **e** no catálogo materializado depois de
  **reexecutar o build**. É item de DoR de toda feature que publica em `data/processed/`.
- **Sete tabelas de `data/processed/` ficam fora, declaradas no dado** (`tabelas_excluidas` do
  relatório), por **dois** motivos distintos:
  1. **schema próprio** — `calendario/dias_uteis_anbima.parquet` (§7, não é série de valores);
  2. **`series_id` composto que não é entrada do catálogo** — `tesouro-direto/td_painel.parquet`
     (**750** compostos `TD_<SIGLA>_<AAAAMMDD>_<METRICA>`) e as **5** fatias de `focus/`
     (`FOCUS_ANUAIS`, `FOCUS_MENSAIS`, `FOCUS_TRIMESTRAIS`, `FOCUS_SELIC`, `FOCUS_INFLACAO_12M`,
     juntas **197** compostos `FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>`), acrescentadas por **D-k**.
     Admiti-los violaria CA-055/CA-120.

  Nos dois casos de (2) o catálogo registra a **fonte** e as séries canônicas derivadas vêm de outra
  feature: do painel do Tesouro nascem os vértices de F-016 (`CURVA_*`, `INCLINACAO_*`,
  `BREAKEVEN_5A`, `fonte=DERIVADO`, em `data/processed/curva/`); o Focus é consumido **direto de
  `data/processed/focus/`** por F-015, pelo mesmo `ProcessedSeriesSchema`, e a procedência de
  `macro_quarterly` aponta para o **EntitySet**, não para o `series_id` por horizonte.
- **Quatro guardas públicas** rodam entre o concatenado e a escrita, porque o pandera não cobre
  nenhuma delas: `validar_procedencia` (CA-055/CA-120 — `series_id` existe no catálogo e
  `source`/`unit`/`freq` da linha são os declarados), `validar_frequencia_nativa` (CA-058),
  `validar_sem_mistura_de_fontes` (CA-077) e `exigir_series` (CA-076 →
  `BLOQUEADO — FONTE INDISPONÍVEL`). São reutilizadas por F-014..F-017, **não** reimplementadas.
- **Idempotência sem relógio:** nada no build lê a hora — `collected_at`/`vintage` vêm do manifesto
  do bruto (D-b) e o relatório **não tem** campo de hora de geração. Duas rodadas dão Parquet e
  relatório byte-idênticos (CA-121).

`relatorio_build.json` é parte do contrato de saída (RF-026/RF-047) e tem os campos:

| Campo | O que registra |
|---|---|
| `feature`, `arquivos_lidos`, `linhas_dedup` | qual build, quantos Parquets de `data/processed/` entraram, quantas linhas de PK duplicada **idêntica** foram colapsadas (hoje `0`) |
| `versao_build` · `versao_build_componentes` | `sha256` do **conjunto** de módulos que decidem o artefato (`build_raw_series` + `raw_series` + `series_catalog` + `series_catalog_data`), e a lista ordenada deles |
| `catalogo_sha256` | hash do catálogo **como dado**; é o que detecta artefato publicado com catálogo mais novo que o build |
| `raw_series` / `series_catalog` | por artefato: `arquivo`, `bytes`, `sha256`, `linhas`, `series`, `date_min`/`date_max`, `collected_at_max` (**com hora**), `vintages`, `linhas_por_source`, `linhas_por_freq`, `n_nulos_value`/`pct_nulos_value`, `presentes_no_processed`, `cobrem_1t2006`, `colunas_observadas` |
| `series` | **1 bloco por série**: `n_obs`, `n_nulos`, `pct_nulos`, janela, `freq`, `unit`, `source`, `vintages`, `value_min`/`value_max` |
| `tabelas_excluidas` · `catalogo_ok_ausente_no_processed` · `series_sem_cobertura_1t2006` | o que ficou fora e **por quê**, série a série — a ausência está no dado, não só na documentação |
| `duckdb` | nome do arquivo derivado e as **views** criadas (nunca tabelas — ver ADR-006 §(a).2) |

> **Estado medido em 2026-10-11** (rebuild sincronizado da Onda 2 completa, com o Focus em disco):
> **62** Parquets lidos → `raw_series` com **278.439** linhas e **62** séries,
> 1979-12-31 → 2026-10-10, `linhas_dedup = 0`, `sha256 0d23df7a…`,
> `versao_build = 6989371e…`; `series_catalog.parquet` com **138 × 26** (`sha256 f56f207e…`), 62
> presentes no processado, 59 cobrindo 1T2006, **7** tabelas excluídas, 33 séries `ok` do pacote
> mínimo ainda ausentes (F-011/F-012 e as demais). O número vivo é o próprio relatório, não esta
> linha.

---

## 2. `series_catalog` — procedência de cada série (RF-019)

`packages/shared/schemas/series_catalog.py` → `SeriesCatalogEntry` (pydantic, `frozen`, `extra="forbid"`)

| Campo | Tipo | Papel |
|---|---|---|
| `series_id` | str | chave |
| `nome` | str | nome legível |
| `item_email` | str | item do e-mail que justifica a série (`A1`..`A7`, `B1`..`B5`, `C1`, ou `-`) |
| `fonte` | `Fonte` | enum de 15 valores |
| `identificador` | str | código SGS, `t/NNNN v/NN`, slug do S3, código B3, ticker, FRED ID, SERCODIGO… **nunca vazio, nunca inventado** |
| `fonte_url` | str | URL (ou template) de onde o dado sai |
| `freq` | `Freq` | `D`/`M`/`Q`/`A` |
| `data_inicio` | date \| None | início **medido na pesquisa**; `None` = não medido (ver `obs`) — nunca um palpite |
| `data_fim` | date \| None | `None` = viva; data = descontinuada |
| `unit` | `Unidade` | unidade e natureza do número |
| `transformacao_padrao` | `Transformacao` | como virar trimestral (ver §2.2) |
| `lag_divulgacao_dias` | int (0..400) | **insumo da regra anti-look-ahead** (RF-025) |
| `confianca` | `Confianca` | `CONFIRMADO` \| `CONFIRMADO_SUB` \| `NAO_VERIFICADO` — **copiada de `docs/research/`** |
| `status` | `StatusSerie` | `ok` \| `a_confirmar` \| `descontinuada` \| `descartada` \| `paga` |
| `is_total_return` | bool \| None | `None` = a confirmar (gap G-01, setoriais da B3) |
| `calendario` | `"dias_uteis"` \| `"corrido"` \| None | grade de publicação de série `freq=D`; `None` = não medido (ou série não diária) |
| `janela_rolante` | bool | `True` = a fonte apaga o passado → **nunca** usar para backfill |
| `fonte_instavel` | bool | endpoint não documentado ou conectividade incerta (B3, MSCI, Yahoo, FRED) |
| `licenca_restrita` | bool | terceiro sem licença comercial explícita (Teva) |
| `obs` | str | pegadinha de parse, valor-canário, motivo do status |

**Validações que o modelo impõe:**
- `identificador` vazio/`-`/`?`/`TODO` → erro. Placeholder legítimo é a string literal `a_confirmar`.
- `identificador == "a_confirmar"` exige `status = a_confirmar` (CA-054).
- `status = descontinuada` exige `data_fim`.
- `data_fim < data_inicio` → erro.
- `series_id` duplicado no catálogo → `load_catalog()` falha.
- `calendario` preenchido em série **não** diária → erro (`_coerencia_status`): dia útil versus dia
  corrido só faz sentido em `freq=D`.

> **Nota sobre `calendario` (acréscimo de 2026-10-11, P1-2 do QA da Onda 2).** O campo nasceu para
> resolver um achado da Onda 1: a **meta Selic (SGS 432) publica em dia corrido** — o mesmo valor em
> sábado, domingo e feriado —, e **2.377 dos seus 8.319 pontos (28,6%) caem em fim de semana**. A
> distinção vivia só na constante `SERIES_DIARIAS_DE_CALENDARIO` dentro de
> `apps/pipeline/extract/bcb_sgs.py`, e quem consome o catálogo (alinhamento trimestral, qualquer
> contagem de dias úteis) não tinha como sabê-la: uma média sobre `freq='D'` sairia enviesada em
> 28,6% dos pontos. Agora a grade é **declarada no dado**. Hoje **7** séries `freq=D` a declaram —
> `BCB_SGS_432 = corrido` e as seis de dia útil (Selic over 11/1178, CDI 12/4389, PTAX 1/10813); nas
> demais o campo é nulo, **nunca** a string `"None"`. É de `calendario` que F-014 **deriva** a régua
> de cada série (`series_de_calendario_corrido()`, §8), em vez de manter uma segunda lista — e um
> teste de contrato afirma que as **três** declarações (catálogo, derivação de F-014 e a constante do
> extrator) coincidem. O campo entrou também em `SeriesCatalogSchema` (§2.4): sem isso, `strict=True`
> o mantinha fora do tabular e o artefato publicava 25 colunas sem ele.

**Propriedades derivadas:**

| Propriedade | Regra | Por quê |
|---|---|---|
| `cobre_2006` | `data_inicio <= LIMIAR_COBERTURA_2006` (**2006-01-31**); `None` quando o início não foi medido | é o limiar da métrica de cobertura do **PRD §7** — o schema segue o PRD. `None` é "não medido", nunca "não cobre" |
| `usavel_no_pacote_minimo` | `status = ok` **e** `fonte` fora de `FONTES_BLOQUEADAS_NO_PACOTE_MINIMO` (hoje: `FRED`) | `status` descreve o **identificador**; esta propriedade responde "dá para extrair até 14/10?". O FRED está bloqueado na camada de aplicação nesta máquina, 3/3 tentativas (`skills-manifest.md §3`) |

As 13 séries FRED (10 delas `ok`) continuam no catálogo com identificador confirmado pela pesquisa —
e **não** contam no pacote mínimo. O plano B é Yahoo/MSCI/PTAX (S-09 no `DECISIONS_LOG.md`).

### 2.1 Estado do catálogo em 2026-10-11 (**138** séries, validadas por pydantic)

> **132 → 134 → 138, as duas mudanças de 2026-10-11** (`DECISIONS_LOG §2.1`):
> **D-d** — F-007 acrescentou `ACWI_BRL` e `SP500_BRL`, as séries em BRL derivadas de MSCI ACWI
> (NETR) e `^GSPC`, com `fonte=DERIVADO` e **`is_total_return` explícito em cada uma**:
> `ProcessedSeriesSchema` tem 8 colunas e nenhuma é essa flag, então o lugar dela (CA-047) é o
> catálogo.
> **D-i** — F-016 acrescentou **4** entradas (`CURVA_REAL_3A`, `CURVA_NOMINAL_3A`,
> `INCLINACAO_REAL_5A_3A`, `INCLINACAO_NOMINAL_5A_3A`) porque CA-025 **não fecha** com o vértice
> curto de 1 ano: a inclinação real 5a−1a existe em 60,53% das datas base de 2006 em diante (a grade
> de vencimentos da NTN-B é alternada e 2021-2022 não tiveram título vencendo em menos de 1 ano),
> enquanto a **5a−3a cobre 95,25%** e passa a ser a **variável principal de regime, em caráter
> provisório**. O vértice de 3 anos já era nomeado por CA-023; as duas séries 5a−1a continuam
> publicadas como **secundárias e declaradas**.
> Com isso `DERIVADO` vai de 7 para **13** entradas (**2** em BRL + **11** da curva) e as `ok` de 99
> para **105** (pacote mínimo: de 89 para **95**). O número vivo é `N_SERIES_ESPERADAS` em
> `tests/unit/test_schemas_smoke.py`. **D-i é provisória: aguarda o aval do Edu** e uma nota em
> ADR-004 §3, que ainda nomeia a 5a−1a como principal.
>
> **A alteração de 2026-10-11 (parte 2 da onda) não mexe na contagem:** **D-p** só muda **1**
> entrada (`FOCUS_PIB_TOTAL`: `a_confirmar` → `descartada`, com `identificador` real e `obs` nova) e
> **D-l** só acrescenta `is_total_return = False` a `BCB_SGS_1` (a PTAX, que virou o `asset_id`
> `USDBRL` em §4). O catálogo segue com **138** entradas e `N_SERIES_ESPERADAS` não mudou.

| Status | n | Leitura |
|---|---|---|
| `ok` | **105** | identificador real e série serve; **95** entram no pacote mínimo (as 10 FRED `ok` saem — fonte bloqueada). 76 cobrem 1T2006 com início medido, 12 não cobrem e **17 seguem sem início medido** (C-2 da auditoria, teste `xfail` declarado em `tests/unit/`) |
| `a_confirmar` | **7** | identificador não confirmado pela pesquisa — **fora do caminho crítico** |
| `descontinuada` | **10** | morreram numa data (swap DI×pré, IMA no SGS, IMA-C, EMBI+, `DTWEXM`) |
| `descartada` | **15** | existem mas não servem (janela curta, não cobrem 2006, fora do escopo mínimo, armadilha) — **+1 em D-p**: `FOCUS_PIB_TOTAL`, que ficou redundante quando G-04 fechou (o dado sai como `FOCUS_A_PIB_TOTAL_H0/H1` dentro de `FOCUS_ANUAIS`) |
| `paga` | **1** | ANBIMA Feed (ETTJ histórica) — fora de escopo por decisão L4 |

| Fonte | n | | Fonte | n |
|---|---|---|---|---|
| `BCB_SGS` | 36 | | `YAHOO` | 12 |
| `B3_API` | 13 | | `ANBIMA_S3` | 11 |
| `FRED` | 13 | | `IBGE_SIDRA` | 9 |
| `DERIVADO` | **13** | | `IPEADATA` | 7 |
| `TEVA_GCS` | 6 | | `BCB_OLINDA` | 6 |
| `MSCI` | 5 | | `ANBIMA_WEB` | 4 |
| `TESOURO_CKAN` | 1 | | `CVM` / `MANUAL` | 1 / 1 |

As **13** entradas `DERIVADO`: **2** em BRL (`ACWI_BRL`, `SP500_BRL`, D-d) e **11** da curva
(`CURVA_REAL_1A/3A/5A`, `CURVA_NOMINAL_1A/3A/5A`, `INCLINACAO_REAL_5A_3A`,
`INCLINACAO_NOMINAL_5A_3A`, `INCLINACAO_REAL_5A_1A`, `INCLINACAO_NOMINAL_5A_1A`, `BREAKEVEN_5A`) —
as 11 produzidas por F-016 em `data/processed/curva/`, 5.436 linhas cada.

Confiança: `CONFIRMADO` 79 · `CONFIRMADO_SUB` 40 · `NAO_VERIFICADO` **19** (são, na maioria, as
**séries derivadas por nós** — curva interpolada, inclinações e breakeven — que exigem conferência
numérica classe C antes de virar número em slide).

As 8 `a_confirmar`: `BCB_SGS_DBGG_PRE2008` (G-07), `BCB_SGS_21619` (rótulo Euro),
`BCB_SGS_4192` (agregado monetário), `FOCUS_PIB_TOTAL` (G-04), `SIDRA_IPCA_GRUPOS_2006_2011` (L13),
`MSCI_BRAZIL`, `GOLD_SPOT_USD` (G-03), `IPEA_SCN104_PIB_SETORIAL`.

### 2.2 Transformações padrão (enum `Transformacao`)

`nenhuma` · `ultimo_dia_util_do_trimestre` · `media_do_trimestre` ·
`acumulacao_geometrica_no_trimestre` · `razao_de_numero_indice` · `variacao_12_meses` ·
`delta_no_trimestre_em_pp` · `desvio_da_media_movel_20_trimestres` ·
`interpolacao_para_vertice_fixo`.

> O nome é parte do contrato: ele diz **como** a série vira trimestral. Trocar a transformação de uma
> série é mudança de alinhamento → **classe C**.

### 2.3 `ExtractorConfig` — config de extrator (pydantic, `frozen`)

`nome` (snake_case) · `fonte` · `series_ids` (≥ 1) · `base_url` · `formato`
(`json|csv|xlsx|txt|html|parquet|zip`) · `encoding` (**sempre explícito**; o default do locale no
Windows corrompe acento) · `requer_user_agent_browser` (default `True`) · `janela_maxima_dias`
(SGS diário: ≤ ~10 anos) · `pagina_com_skip` (Olinda trunca em `$top=20000`) · `cache_condicional`
(ETag/Last-Modified) · `contagem_minima_esperada` (**assert anti-truncamento silencioso**) ·
`valor_canario` (`(data ISO, valor)`) · `destino_raw` (`data/raw/<fonte>/`) ·
`ausencia_e_caso_normal` (job diário da ANBIMA) · `timeout_s` · `max_retries`.

Cada campo existe por causa de um risco catalogado em `docs/research/fontes-de-dados.md`
(R1 erro com HTTP 200, R2 truncamento silencioso, R4 anti-bot, R8 janela rolante, R10 encoding,
R21 tamanho de arquivo).

### 2.4 Forma tabular: `SeriesCatalogSchema` (**20** colunas) × `SeriesCatalogMaterializedSchema` (**26**)

São **dois** contratos, e a diferença é o que separa o **declarado** do **medido**:

| Schema | O que é | Onde vale |
|---|---|---|
| `SeriesCatalogSchema` | o catálogo *declarado* — as **20** colunas de `SeriesCatalogEntry` em forma tabular (as 19 originais **+ `calendario`**, acrescentada em 2026-10-11) | qualquer leitura do catálogo como DataFrame |
| `SeriesCatalogMaterializedSchema` | **subtipo** (acréscimo, não alteração): herda as 20 e soma **6** colunas do observado em disco → **26** no artefato | `data/canonical/series_catalog.parquet`, escrito por F-013 |

As **6 colunas observadas**:

| Coluna | Tipo | Regra |
|---|---|---|
| `presente_no_processed` | bool, não nulo | existe ≥ 1 linha desta série em `raw_series` |
| `data_inicio_observada` | datetime, nulo | `min(date)` **medido**; nulo ⇔ série ausente |
| `data_fim_observada` | datetime, nulo | `max(date)` medido; nulo ⇔ ausente |
| `n_obs` | int ≥ 0, não nulo | linhas em `raw_series`; `0` ⇔ ausente |
| `pct_nulos` | float 0..100, não nulo | % de `value` nulo **dentro da série**, gravado com `round(x, 6)` |
| `cobre_1t2006` | bool, não nulo | `data_inicio_observada <= LIMIAR_COBERTURA_2006` (2006-01-31, PRD §7) |

**Declarado e observado coexistem, nunca se sobrescrevem:** `data_inicio` (medido na pesquisa) e
`data_inicio_observada` (medido em disco) ficam lado a lado, porque a **divergência é informação** —
é assim que se vê que o IFIX começa em 2010-12-30 e que 33 séries `ok` do pacote mínimo ainda não
têm extrator rodado. Três checks de DataFrame impedem o atalho de copiar um no outro:
`ausente_nao_tem_observacao` (série ausente não carrega janela, contagem nem cobertura),
`cobre_1t2006_derivado_do_observado` (a coluna é **derivada**, nunca digitada) e
`janela_observada_coerente` (`fim >= inicio`).

`cobre_1t2006` é **booleano**, diferente da propriedade `cobre_2006` de `SeriesCatalogEntry`, que é
tri-estado (`None` = "início não medido"): aqui o início é sempre medido **ou** a série está
ausente — e ausente é `False` com `presente_no_processed = False` ao lado, para que "não cobre"
nunca se confunda com "não veio".

> **O portão de schema é a escrita, não a leitura.** F-014 lê o materializado pelas **3 colunas que
> consome** (`series_id`, `freq`, `data_inicio_observada`) em vez de revalidar as 26 — revalidar na
> leitura transformaria um acréscimo legítimo de coluna numa falha de feature a jusante. O que
> protege o alinhamento é mais específico: as 3 colunas existem, `series_id` é único e
> `data_inicio_observada` é conferida **linha a linha** contra `raw_series`.

---

## 3. `macro_quarterly` — 83 trimestres (RF-021) · **classe C**

`packages/shared/schemas/macro_quarterly.py` → `MacroQuarterlySchema`. PK `quarter` (`2006Q1`..`2026Q3`).

| Grupo | Colunas |
|---|---|
| chave | `quarter`, `quarter_end` (último dia útil) |
| crescimento | `pib_yoy`, `pib_qoq_sa`, `ibcbr_yoy`, `ibcbr_yoy_trend`, `ibcbr_gap` |
| inflação | `ipca_12m`, `ipca_12m_delta`, `ipca_tri`, `ipca_meta`, `ipca_desvio_meta` |
| juros | `selic_meta_fim`, `selic_meta_delta`, `selic_over_tri`, `cdi_tri`, `juro_real_exante` |
| curva | `curva_real_1a`, `curva_real_5a`, `curva_nominal_1a`, `curva_nominal_5a`, `inclinacao_real_5a_1a`, `inclinacao_nominal_5a_1a`, `breakeven_5a`, `vertice_extrapolado` |
| câmbio/externo | `usdbrl_fim`, `usdbrl_var_tri`, `usdbrl_var_12m`, `termos_troca_yoy`, `embi_br_fim`, `embi_delta_tri`, `ust10_fim`, `vix_fim` |
| expectativas | `focus_ipca_12m`, `focus_pib_ano`, `focus_selic_fim`, `surpresa_ipca`, `surpresa_pib`, `surpresa_selic` |
| auditoria | `is_estimated`, `lag_adjusted`, `fonte_versao` |

**Checks de DataFrame:**
- `janela_de_83_trimestres` — exatamente 83 linhas, de `2006Q1` a `2026Q3` (CA-059).
- `lag_adjusted_homogeneo` — uma materialização nunca mistura `asof` e `revised`.

**Duas materializações, as duas em disco desde F-018:** `data/canonical/macro_quarterly.parquet`
(`lag_adjusted=False`, **`revised`**, F-015) e `data/canonical/macro_quarterly_asof.parquet`
(`lag_adjusted=True`, **`asof`**, F-018 — a materialização **de decisão**, SPEC §2). As duas têm o
**mesmo** `MacroQuarterlySchema` e a mesma grade: trocar de materialização é trocar o caminho do
Parquet, e `lag_adjusted` da linha diz qual foi lida. A `asof` sai do **mesmo** `montar_macro`, com
os níveis deslocados pela divulgação (`date_obs + lag_divulgacao_dias <= quarter_end`, lag inteiro
do `series_catalog`) e **toda derivada recalculada**, nunca copiada da revisada. A divergência de
classificação entre as duas é **reportada** (RF-025, CA-073/074) e hoje está **acima** do limiar —
ver §5.1a.

> **Nível trimestral do IBC-Br = média dos 3 meses do trimestre (`obs = media_3m`, D-s).**
> `metodologia §2` diz "IBC-Br: média do trimestre"; até 2026-10-11 a implementação lia o **fim de
> período** (D-q(e)). O QA da Onda 2 mediu a diferença: `max |dif|` **4,2646 pp** em `ibcbr_yoy`,
> **4,3064 pp** no hiato e **7 dos 67 trimestres trocando de quadrante na V1**. A média exige os **3**
> meses (2 → `NULL` com motivo, nunca média parcial), e a procedência registra a **última** das 3
> observações — o limite superior que mantém `date_obs <= quarter_end` verificável no Parquet.
> `pib_yoy` **não** muda (o PIB do SIDRA já é trimestral na fonte).

Colunas nulas são **legítimas e informativas**: `ipca_meta` (série de metas é gap G-02),
`embi_br_fim` após 30/07/2024, `curva_nominal_*` onde o vértice não existe. Nulo **nunca** é
preenchido para "fechar" a linha.

> **Unidade — `macro_quarterly` está em POR CENTO / pontos percentuais, nunca em fração** (**D-o**).
> `ipca_tri = 1,4367` significa 1,4367 %. É o vocabulário do projeto (`UNIDADES_VALIDAS` tem `%`,
> `%a.a.`, `pp` e nenhuma fração), é o que `LIMIAR_SELIC_PP = 0,25` pressupõe e é o que o canário
> exige (`ipca_12m` de `2006Q1` **tem** de ser `5,32`, o número que o SGS publica). O mapa completo
> por coluna vai no dado, em `relatorio_macro.json → unidades`. **`asset_returns_quarterly` (§4)
> está em FRAÇÃO**, e as duas tabelas publicam `cdi_tri` e `ipca_tri` — mesmo nome, escalas
> diferentes. Quem cruzar as duas sem ler a unidade erra por **100x**; a conversão é exatamente
> `macro = 100 × retornos` (medido: `max |dif| = 0,0` nos 83 trimestres).

> **Estado medido em 2026-10-11, depois do rebuild de fechamento da Onda 3 parte 1** (F-015 +
> D-s/D-v, `python -m apps.pipeline.canonical.macro_quarterly --offline`): **83 × 42**,
> `2006Q1..2026Q3`, materialização **`revised`** (`lag_adjusted=False` nas 83),
> `sha256 bcb31e92…`. A companheira `asof` (F-018): **83 × 42**, `lag_adjusted=True` nas 83,
> `sha256 85e8ec67…`; **27** das 37 colunas rastreáveis são **idênticas** às da `revised` e **10**
> mudam (lag > 0), e a reprodução da `revised` na mesma rodada confere **3.071 células, 0
> divergências, `max |dif| = 0,0`** contra o Parquet em disco. **5** colunas 100% nulas, **todas**
> por gap declarado: `ipca_meta` e
> `ipca_desvio_meta` (G-02), `embi_br_fim` e `embi_delta_tri` (L8) e `termos_troca_yoy` (nenhum
> índice de termos de troca foi extraído — proxy IC-Br em `TODO.md §6`). `ibcbr_yoy_trend` e
> `ibcbr_gap` têm **16** nulos (`2006Q1..2009Q3` + `2026Q3`): **CA-007 não é satisfazível** com o
> IBC-Br real, que começa em 2003 — ver **D-m**. `curva_real_1a` e `inclinacao_real_5a_1a` têm **33**
> nulos (39,8%), e a inclinação **principal** de D-i (`INCLINACAO_REAL_5A_3A`, 95,25%) **não é
> coluna** deste schema (**D-n**): F-019/F-021 leem a série. `is_estimated = True` só em `2026Q3`
> (CA-060). Os 4 canários publicados: `ipca_12m` 2006Q1 = **5,32**, `selic_meta_fim` 2008Q4 =
> **13,75**, `pib_yoy` 2010Q1 = **9,207417**, `focus_ipca_12m` 2026Q3 = **4,19**. **Ciclo Selic
> (D-t):** `|Δ| >= 0,25 pp` conta como movimento (desigualdade **não** estrita), distribuição
> medida **CORTE 34 · NEUTRO 23 · ALTA 26** nos 83 — era 29/30/24 com a desigualdade estrita, que
> punha os cortes reais de 25 bps de **2024Q2 e 2024Q3** em `NEUTRO`.

### 3.1 `macro_quarterly_provenance` — procedência por célula (RF-047 / CA-120)

`packages/shared/schemas/macro_quarterly.py` → `MacroQuarterlyProvenanceSchema`.
PK `(quarter, column)`. Materializada em `data/canonical/macro_quarterly_provenance.parquet`,
**junto** com a tabela wide, pela mesma feature (F-015).

> **São DUAS materializações de procedência, uma por materialização da tabela wide** (F-018 §2/§9.1):
>
> | Artefato | Schema | Colunas | Quem escreve |
> |---|---|---|---|
> | `macro_quarterly_provenance.parquet` | `MacroQuarterlyProvenanceSchema` | **8** | F-015 (`revised`) |
> | `macro_quarterly_asof_provenance.parquet` | `MacroQuarterlyAsofProvenanceSchema` | **10** (+ `date_obs`, + `lag_dias`) | F-018 (`asof`) |
>
> `MacroQuarterlyAsofProvenanceSchema` é **subclasse** (acréscimo, nunca alteração: o schema de
> F-015 é `strict=True` e alterá-lo é pausa). As duas colunas novas são o que torna **CA-072
> verificável no Parquet publicado** e não só no código: `date_obs + lag_dias <= quarter_end` é
> consultável, e `lag_dias` é o **maior** lag entre os insumos da coluna — limite superior
> conservador (`surpresa_pib` = max(PIB 60, Focus 0) = 60). Sem elas, "qual observação foi usada"
> só existiria no relatório. Guardar `date_obs` apenas no relatório foi a alternativa descartada.

| Coluna | Tipo | Nulo? | Regra |
|---|---|---|---|
| `quarter` | str | não | mesmo domínio de `macro_quarterly.quarter` |
| `column` | str | não | uma das `COLUNAS_RASTREAVEIS` — derivadas do próprio schema wide, menos chave e auditoria (`COLUNAS_SEM_PROCEDENCIA`) |
| `series_id` | str | não | série de origem; existe em `series_catalog`, que carrega a `fonte_url` |
| `source` | str | não | mesmo enum de 15 fontes de `raw_series` |
| `vintage` | datetime | **sim** | nulo = série não revisável (igual a `raw_series`) |
| `collected_at` | datetime | não | quando o pipeline baixou o dado que gerou a célula |
| `lag_adjusted` | bool | não | a qual materialização (`asof` / `revised`) esta procedência pertence |
| `fonte_versao` | str | não | mesmo hash de código da linha wide correspondente |

**Checks:** `vintage_nao_posterior_a_coleta` (`vintage <= collected_at`) e `lag_adjusted_homogeneo`.

**Por que uma tabela companheira e não 4 colunas por linha.** `macro_quarterly` é **wide**: a linha é
um trimestre, e cada uma das ~40 colunas vem de uma série diferente. Colocar
`source`/`series_id`/`vintage`/`collected_at` na linha responderia "de onde veio o trimestre?", que
não é a pergunta de CA-120. A alternativa — 4 colunas de procedência por variável — multiplicaria a
tabela por 5 e ainda assim só valeria para o wide. O long resolve as duas coisas e é consultável
(`WHERE column = 'ipca_12m'`). CA-120 foi **reescrito** na SPEC para exigir exatamente isto
(2026-10-10, E-1 da auditoria; ver `docs/wiki/log.md`).

`asset_returns_quarterly` **não** precisa da companheira: é long por natureza e já carrega `source` e
`series_id` na linha. `vintage`/`collected_at` de um retorno ficam em `raw_series`, pela PK
`(series_id, date, vintage)`.

> **Estado medido em 2026-10-11 (pós-rebuild):** `revised` com **2.548** linhas (1 por célula
> rastreável **preenchida**), cobrindo **32** das 37 `COLUNAS_RASTREAVEIS` e **20** séries de origem
> distintas, `sha256 aa8d427a…`; `asof` com **2.552** linhas, **32** colunas, **`date_obs` e
> `lag_dias` em todas**, `sha256 a5b2eaef…`, e **0** células com divulgação posterior ao fim do
> trimestre (CA-072 — o build **para** se houver uma). A `asof` tem 4 linhas **a mais** porque usa
> o último dado **divulgado**: em `2026Q3` a `revised` não tem PIB nem IBC-Br e a `asof` carrega o
> PIB de `2026Q2` e a média do IBC-Br de `2026Q2`, que é o que estava na mesa em 30/09.
> CA-120 verificado por **anti-join nas duas direções**: nenhuma célula
> preenchida sem procedência e **nenhuma procedência para célula nula** (procedência de nulo seria
> afirmação sobre dado que não existe). Todo `series_id` resolve em `series_catalog` — e para o
> Focus a linha aponta para o **EntitySet** (`FOCUS_ANUAIS`, `FOCUS_INFLACAO_12M`), **não** para o
> `series_id` por horizonte (`FOCUS_A_SELIC_H0`), que não é entrada do catálogo (**D-k**). O
> horizonte fica na fórmula de `ORIGENS` e no relatório.

---

## 4. `asset_returns_quarterly` — retorno por ativo (RF-022/023/024) · **classe C**

`packages/shared/schemas/asset_returns_quarterly.py` → `AssetReturnsQuarterlySchema`.
PK `(quarter, asset_id)`.

`asset_id` vem de um enum explícito de 32 valores, em 4 blocos:

- **Renda fixa (9):** `CDI`, `IMAB`, `IMAB5`, `IMAB5P`, `IRFM`, `IRFM1`, `IRFM1P`, `IMAGERAL`, `IMAS`
- **Ações B3 (10):** `IBOV`, `IDIV`, `SMLL`, `INDX`, `ICON`, `IMAT`, `IEEX`, `IMOB`, `IFNC`, `UTIL`
- **FII (6):** `IFIX`, `FII_TIJOLO`, `FII_PAPEL`, `FII_LOGISTICA`, `FII_SHOPPINGS`, `FII_LAJES`
- **Internacional (7):** `SP500_BRL`, `SP500_USD`, `SP500_HEDGE`, `ACWI_BRL`, `UST10_BRL`, `GOLD_BRL`, `USDBRL`

| Coluna | Regra |
|---|---|
| `price_ini`, `price_fim` | > 0; do último DU de T−1 e de T |
| `ret_tri` | `price_fim/price_ini − 1`, em [−1, 5] |
| `ret_excesso_cdi` | `(1+ret)/(1+cdi) − 1` — **razão, nunca subtração** |
| `ret_real` | `(1+ret)/(1+ipca_tri) − 1`, IPCA do mesmo trimestre, aplicado **uma** vez |
| `vol_intra_tri`, `dd_intra_tri` | ≥ 0 e ≤ 0 respectivamente (exigem dado diário) |
| `is_total_return` | `None` = a confirmar (G-01); comparação price × total return sem flag falha |
| `n_dias_uteis` | 0..70 |
| `ffill_dias_uteis` | 0..5 — acima de 5 DU o valor vira `NULL` (CA-067) |
| `data_inicio_serie` | janela própria do ativo; vai ao rodapé das figuras |
| `source`, `series_id`, `fonte_versao` | rastreabilidade por linha (RF-047) |

**Checks:** `minimo_de_ativos` (≥ 18 `asset_id` distintos) e
`sem_trimestre_antes_do_inicio_da_serie` (**proíbe backfill sintético** — CA-063). O segundo compara
**ano e trimestre** de `data_inicio_serie`, não só o ano: comparar o ano deixava passar `2010Q1..Q3`
do IFIX, `2007Q1..Q3` do IMOB e `2006Q1..Q3` do ICON — justamente os casos nomeados na Anti-SPEC
§10.1.1 (corrigido em 2026-10-10, E-2 da auditoria). O trimestre que **contém** o início (2010Q4 do
IFIX) é aceito pelo schema: é parcial, não anterior — quem o anula é a regra de `price_ini` em F-014.

> **Unidade — `asset_returns_quarterly` está em FRAÇÃO** (**D-o**): `ret_tri = 0,0404` significa
> +4,04 %. É a escala em que `(1+r)/(1+b) − 1` é a conta certa (ADR-006 §(b).5), e misturar escala
> ali **produz número errado**, não só confuso. **`macro_quarterly` (§3) está em por cento**, e as
> duas tabelas têm `cdi_tri`/`ipca_tri` com o mesmo nome: `macro = 100 × retornos`. As 11 fórmulas
> vão no próprio artefato, em `relatorio_retornos.json → convencoes`, e o CDI/IPCA de cada trimestre
> em `bases_por_trimestre` — dá para refazer qualquer linha com uma calculadora.

> **Estado medido em 2026-10-11** (F-017, `python -m apps.pipeline.canonical.retornos --offline`):
> **1.963** linhas · **24** `asset_id` dos 32 do enum · 83 trimestres (`2006Q1..2026Q3`) ·
> `sha256 c055ac81…` (era `ab61eeca…` antes de **D-v b**: só `fonte_versao` mudou, nenhum valor). `USDBRL` entrou por **D-l** (+83 linhas; `is_total_return = False`, porque
> câmbio não tem carrego) e os **8** que seguem fora têm motivo nomeado em
> `ATIVOS_FORA_DO_UNIVERSO`, publicado no relatório: os 5 `FII_*` (Teva/F-012 não rodou),
> `SP500_HEDGE` (exige Fed Funds, FRED bloqueado), `UST10_BRL` (`YAHOO_TNX` é **taxa**, não
> número-índice) e `GOLD_BRL` (não extraída). Nulos, todos com motivo: `is_total_return` **820**
> (9 setoriais da B3 — G-01 — + CDI, para quem a flag não se aplica), `price_ini` **106**,
> `price_fim` **83** (o CDI não tem nível de preço), e `ret_tri`/`ret_excesso_cdi`/`ret_real`/
> `vol_intra_tri`/`dd_intra_tri`/`n_dias_uteis` **23** cada (o 1º trimestre de cada ativo de preço,
> sem `T−1`). `ffill_dias_uteis = {0: 1.748, 1: 215}` — **nenhum** valor 2..5; `n_dias_uteis` entre
> **58 e 66**. **O CDI é o único ativo com retorno em `2006Q1`**, porque a acumulação diária não
> precisa de `T−1` — assimetria declarada. A tabela **não tem** flag de trimestre corrente
> incompleto (`is_estimated` é de §3): ver `TODO.md §6`.

### 4.1 `RegimeAssetMetricsSchema` — métricas por regime × ativo (RF-032/040)

PK `(lente, regime, asset_id)`, com `lente ∈ {V1, V2, V3}`.
Colunas: `n_obs`, `ret_medio`, `ret_mediana`, `ret_desvio`, `erro_padrao_media`, `hit_ratio`,
`excesso_cdi`, `hit_ratio_cdi`, `ret_real`, `sharpe_tri`, `pior_tri(_quarter)`,
`melhor_tri(_quarter)`, `beta_ibov`, `alerta_n_baixo` (`n < 8`), `conclusao_suprimida` (`n < 5`),
`data_inicio_serie`, `fonte_versao`.

> `n_obs` é obrigatório e não anulável **por contrato**: é o que garante "`n` em toda célula de toda
> tabela" (RN-04).

> ⚠️ **`erro_padrao_media` é o erro-padrão do retorno NOMINAL** — `desvio(ret_tri)/√n`, **não** o do
> excesso sobre CDI. É a dívida registrada por F-024 (item (b), **D-aa**): quem lê a coluna ao lado
> de `excesso_cdi` supõe que ela é o erro-padrão **daquela** métrica, e não é. Medido: para `INDX`
> na V3 a coluna publica **2,54 pp** enquanto o erro-padrão do excesso que F-021 publica é
> **2,60 pp**. A página de F-024 declara qual mostra e trata `|excesso|/ep` como **semáforo**, nunca
> como estatística de teste. Acrescentar `erro_padrao_excesso` é **alteração** de schema ⇒ feature
> classe C própria; está na lista única de dívidas de `TODO.md §6`.

> **Acréscimo de D-ac (2026-10-11):** as 2 colunas `bool` `nullable=False` (`alerta_n_baixo`,
> `conclusao_suprimida`) ganharam **parser + check** que recusam `None`/`NaN`/`pd.NA`. Sem eles,
> `coerce=True` fazia `astype(bool)` **antes** dos checks e em pandas `None → False` — flag ausente
> entrava como "não há alerta" com o selo do pandera. Nenhuma coluna foi alterada; é acréscimo.
> Travado por `tests/contract/test_metricas_regime_contract.py`.

---

## 5. `regimes` e `regime_neighbors` (RF-027..031, RF-036) · **classe C**

`packages/shared/schemas/regimes.py`.

### 5.1 `RegimesSchema` — PK `quarter`

`regime_v1` ∈ {`RECUPERACAO`, `EXPANSAO_INFL`, `ESTAGFLACAO`, `DESACELERACAO`} ·
`regime_v1b` (nulo na v1 — fase 2, nunca copiado de `regime_v1`) ·
`ciclo_selic` ∈ {`CORTE`, `ALTA`, `NEUTRO`} · `regime_v2` (`v1 + "_" + ciclo`) ·
`stress_flag` · `g_score`, `pi_score` (contínuos, para o gráfico de dispersão) ·
`n_obs_regime_v1` (≥ 1, não anulável) · `alerta_n_baixo` · `lag_adjusted` ·
`trocou_vs_revised` (alimenta CA-073/074) · `especificacao_congelada`
(**`False` enquanto ADR-001 estiver em Proposta** — gate de publicação, CA-090) ·
`versao_especificacao` (`V1` | `V1.1`) · `fonte_versao` (hash do código).

**Check:** `todos_os_quadrantes_povoados` — os 4 rótulos existem na amostra.

> **`regimes.parquet` NÃO EXISTE** — e o motivo encurtou para **um** (**D-ab**, 2026-10-11).
> `RegimesSchema` é o contrato da tabela **completa**. Em F-022 (**D-r**) havia **dois** bloqueios:
> `stress_flag` sem definição e `regime_v1` não anulável com 16 trimestres `INDETERMINADO`.
> **F-026 resolveu o primeiro** (`D6-a`: a regra de stress, 20 de 83 trimestres), e
> `internacional.serie_de_stress_flag` entrega exatamente a `Series` que
> `metricas_regime.montar_regimes(stress_flag=...)` espera. **Medido em 2026-10-11** com a série
> real de F-026: `montar_regimes` devolve `gravavel = False` com **um** bloqueio de contrato —
> `regime_v1` é `nullable=False` no enum de 4 rótulos e **16 dos 83** trimestres são
> `INDETERMINADO` (**D-m**).
>
> As três saídas seguem proibidas sem decisão humana: preencher = quadrante inventado (Anti-SPEC
> §10.1.1); excluir as linhas = tirar do canônico `2006Q1..2009Q3` (a crise de 2008) **e** `2026Q3`
> (o trimestre do Comitê) sem a tabela dizer que tirou; tornar `regime_v1` anulável ou acrescentar
> `INDETERMINADO` ao enum (o que quebraria `todos_os_quadrantes_povoados`) = **alteração de schema
> existente ⇒ pausa**. **O schema não foi alterado**; a fonte autoritativa da V1 segue
> `regimes_v1.parquet`, e há teste de contrato que **falha** se `regimes.parquet` aparecer em disco.

> **Acréscimo de D-ac (2026-10-11):** `stress_flag`, `alerta_n_baixo` e `especificacao_congelada`
> — as 3 colunas `bool` `nullable=False` que o achado de F-022 §8.3 nomeia — ganharam
> **parser + check** que recusam `None`/`NaN`/`pd.NA`. O caso fechado era grave: `stress_flag =
> None` nas 83 linhas **validava**, declarando que nenhum trimestre dos 20 anos foi de stress.
> `lag_adjusted` também é `bool`/`nullable=False` e **não** está coberta — é a 4ª, e está na lista
> única de dívidas de `TODO.md §6`. Nenhuma coluna foi alterada; é acréscimo.

### 5.1a `RegimesV1Schema` — a V1 isolada, PK `(quarter, lag_adjusted)` (F-019, **D-r**)

Acrescentado ao fim de `packages/shared/schemas/regimes.py` (nada acima foi alterado). Valida o
**subconjunto V1** de `RegimesSchema` — toda coluna de `COLUNAS_V1_DE_REGIMES` existe em
`RegimesSchema` com o **mesmo nome**, e há teste de contrato para isso — mais 4 colunas de
auditoria próprias:

`regime_v1` (**anulável**, ao contrário de `RegimesSchema`) · `status_regime_v1` ∈
{`CLASSIFICADO`, `INDETERMINADO`} · `motivo_indeterminado` ∈ {`GAP_AUSENTE`, `ACELERACAO_AUSENTE`,
`AMBOS_AUSENTES`, `EMPATE_SEM_SINAL_ANTERIOR`} · `desempate_aplicado` ·
`g_score`/`pi_score` · `n_obs_regime_v1` · as 3 flags de `n` · `lag_adjusted` ·
`trocou_vs_revised` (**nulo** na própria `revised`: não existe "trocou em relação a si mesma") ·
`especificacao_congelada` · `versao_especificacao` · `fonte_versao`.

**Checks:** `status_coerente_com_o_rotulo` e `eixos_presentes_se_classificado` — não dá para ter
`regime_v1` nulo sem `status = INDETERMINADO` com motivo, nem o contrário. `lag_adjusted_homogeneo`.

> **Estado medido em 2026-10-11 (pós-D-s), materialização `revised`:** `regimes_v1.parquet`
> **83 × 18**, `sha256 b74f8d67…`; **67** classificados e **16** `INDETERMINADO`
> (`2006Q1..2009Q3` + `2026Q3`, todos `GAP_AUSENTE` por **D-m** — a crise de 2008 inteira fica fora
> do eixo de crescimento). Distribuição **RECUPERACAO 19 · EXPANSAO_INFL 19 · ESTAGFLACAO 16 ·
> DESACELERACAO 13**: CA-080 fecha (4 quadrantes povoados, todos em [10, 35]), desbalanceamento
> **1,46×**, nenhuma flag de `n` acesa, **0 desempates** (nenhum eixo é exatamente 0 no dado real,
> então CA-079 só é exercitado em sintético). Companheira `regimes_v1_asof.parquet`
> (`sha256 6e922165…`): **67** classificados, **EXP 21 · REC 17 · EST 16 · DES 13**.
>
> ⚠️ **CA-074 ACIONADO:** a V1 troca de rótulo entre `revised` e `asof` em **22 de 66 trimestres =
> 33,33%**, acima do limiar de **25%**. Pelo critério escrito em `metodologia §5.1` a V1 **não é
> operacional na forma `asof`** e a hipótese **H-03 do PRD cai**; a leitura **descritiva** segue
> válida e é o entregável de RF-027. Mecanicamente: `ibcbr_gap` é um hiato pequeno (mediana
> `|g| ≈ 2 pp`) sobre média móvel de 20 trimestres, e deslocar o IBC-Br de um trimestre troca o
> sinal com facilidade. Vai à página de limitações (F-028) e ao slide do Comitê.
>
> **`especificacao_congelada = False` nas 83 linhas**, lido do **status do ADR-001 em disco**
> (`Proposta`), com falha fechada: **nenhum número daqui é publicável** (CA-090, `AGENTS.md §14`).

### 5.2 `RegimeNeighborsSchema` — PK `(quarter_ref, rank, metrica, k_usado, restrito_pos_2016)`

`distancia` ≥ 0 · `metrica` ∈ {`mahalanobis`, `euclidiana`} · `k_usado` ∈ {5, 8, 12} ·
`n_features` ∈ **{3, 4, 5, 6}** (6 = tudo pronto · 5 = sem a curva, CA-086 · 4 = sem Focus **e**
sem curva, cortes 4 e 5 do `PLAN.md §5` · 3 = com G-02/`ipca_meta` também aberto; **sempre declarado,
nunca silencioso**. O `ge=5` anterior rejeitava o único cenário de corte que o PLAN prevê como
aceitável — P1-10 da auditoria) ·
`regime_v1_neighbor` · `shrinkage` (`ledoit_wolf` obrigatório em Mahalanobis) ·
`restrito_pos_2016` (variante de robustez) · `fonte_versao`.

**Check:** `exclui_vizinhos_adjacentes` — o trimestre de referência não é vizinho de si mesmo; a
exclusão dos 2 trimestres anteriores é verificada no teste da feature (CA-085).

### 5.2a `RegimeNeighborsV3Schema` — a lente completa (F-021, **D-u**)

Acrescentado ao fim de `packages/shared/schemas/regimes.py`. PK
`(quarter_ref, rank, metrica, k_usado, restrito_pos_2016, somente_passado)`, **21** colunas.

> ⚠️ **Corrigido em 2026-10-11 (QA Onda 3, P1-1 / decisão D-y).** A redação anterior desta seção
> dizia que o schema tem `rho_shrinkage` e "as 5 features em unidade original". **Nenhuma das duas
> existe** — nem no schema, nem no Parquet. Quem confiasse no parágrafo iria buscar a feature do
> vizinho numa coluna inexistente. O `rho` de Ledoit-Wolf mora em
> `relatorio_regimes_v3.json → shrinkage.intensidade_rho`; as features em unidade original **não
> são publicadas** em tabela nenhuma. Abaixo, as 21 colunas reais, lidas do schema.

As **6** herdadas de `RegimeNeighborsSchema` sem mudança: `quarter_ref`, `rank`,
`quarter_neighbor`, `distancia`, `metrica`, `k_usado`. As **3** herdadas que a V3 preenche com
outro sentido: `n_features` (= 5, ver §5.3), `shrinkage` (o **nome** do estimador, `ledoit_wolf`,
não a intensidade), `restrito_pos_2016`. A **1** herdada que a V3 relaxa: `regime_v1_neighbor`,
aqui **anulável** (D-m/D-u). E as **11 novas**:

| coluna | tipo | o que é |
|---|---|---|
| `n_vizinhos` | `int` | quantos vizinhos a linha de fato achou — pode ser `< k_usado` (208 linhas) |
| `features_usadas` | `str` | as 5 features **nomeadas na linha**, nunca só no relatório |
| `status_regime_v1_neighbor` | `str` | por que o rótulo V1 do vizinho é nulo, quando é |
| `quarter_t_mais_1` | `str`, anulável | o trimestre **seguinte** ao vizinho — a chave de CA-102 |
| `janela_padronizacao` | `str` | `expanding` × `amostra_completa` |
| `somente_passado` | `bool` | a lente sem look-ahead de seleção/padronização (parte da PK) |
| `alerta_n_baixo` | `bool` | `n_vizinhos < N_ALERTA` (CA-108) |
| `especificacao_congelada` | `bool` | o gate de CA-090 **na linha** |
| `versao_especificacao` | `str` | `V1`/`V1.1` da especificação de regime |
| `lag_adjusted` | `bool` | `False` nas 9.692 linhas: a V3 roda sobre `revised` (ver abaixo) |
| `fonte_versao` | `str` | hash do código (CA-088) |

> **A V3 roda sobre `revised` — safra única, limitação declarada** (QA Onda 3, P1-5 / **D-y**).
> `lag_adjusted = False` nas 9.692 linhas. Das 5 features, 3 (`focus_pib_ano`,
> `juro_real_exante`, `usdbrl_var_12m`) são **idênticas** em `revised` e `asof` (lag 0, 0 de 83
> células diferentes), mas **`ipca_12m_delta` difere em 83/83** (`max abs dif` 1,98 pp; em
> `2026Q3`, `revised = −0,06` contra `asof = −0,50`). Logo: a variante `somente_passado` elimina
> look-ahead de **seleção** (quais trimestres entram) e de **padronização** (média/desvio do
> z-score), **não de safra**. Ler "sem nenhum caminho de look-ahead" como "sem look-ahead de
> safra" é erro. Rodar a V3 também sobre `macro_quarterly_asof` é feature própria, não feita.

> **Por que existem DOIS artefatos de vizinhos — e qual F-022/F-024 devem ler.**
> `RegimeNeighborsSchema.regime_v1_neighbor` é `nullable=False`, e por **D-m** 16 trimestres não
> têm quadrante V1. A tabela de contrato só pode conter vizinho **com rótulo**, e isso custa **4
> dos 8** vizinhos de `2026Q3` (Jaccard **0,33** contra a lente completa) — perde 2006-2009
> inteiro, inclusive a crise, **sem que a tabela diga que perdeu**.
>
> **→ F-022 e F-024 leem `data/canonical/regime_neighbors_v3.parquet`**, lente
> `metrica=mahalanobis`, `k_usado=8`, `somente_passado=False`, `restrito_pos_2016=False`. As outras
> 23 combinações são **sensibilidade**. `data/canonical/regime_neighbors.parquet` existe para
> satisfazer CA-089 e **não** é a resposta. Tornar a coluna anulável é alteração de schema
> existente ⇒ **feature classe C própria**, registrada como dívida em `TODO.md §6` (**D-u**).
>
> O retorno de `T+1` **não** está em nenhum dos dois schemas: junte `quarter_t_mais_1` com
> `asset_returns_quarterly.quarter` — ou, melhor, **importe** `retornos_em_t_mais_1` e
> `ranking_de_ativos` de `regimes_v3.py`, que já fazem isso com `n`, mediana, erro-padrão e as duas
> flags. `asset_returns_quarterly` está em **fração** e `macro_quarterly` em **por cento** (D-o).

> **Estado medido em 2026-10-11:** `regime_neighbors_v3.parquet` **9.692 × 21**, **77**
> referências com vetor completo, `sha256 a17d9288…`; `regime_neighbors.parquet` **5.500 × 11**,
> `sha256 a5d7d127…` (rodada de 2026-10-11 pós-fechamento da Onda 4). Mahalanobis com shrinkage de **Ledoit-Wolf** medido (`rho = 0,259874`,
> condicionamento 8,26 → 3,97), implementado em numpy puro. Exclusão de vizinhança **simétrica**
> (`T±1`, `T±2`) — CA-085 fala só dos anteriores, mas sem a simetria o vizinho rank 1 de quase
> todo trimestre seria `T+1`, autocorrelação trivial. Os **8 vizinhos de `2026Q3`** são
> `2006Q3 · 2006Q4 · 2006Q1 · 2024Q3 · 2014Q4 · 2007Q1 · 2024Q2 · 2014Q3`. **D-s não mudou nada
> aqui** (lista, distâncias e ranking byte-idênticos): nenhuma das 5 features passa pelo IBC-Br.
>
> **A sobreposição entre a lente descritiva e a `somente_passado` é uma DISTRIBUIÇÃO, não o número
> de `2026Q3`** (QA Onda 3, P1-2 / **D-y**). Em `2026Q3` o Jaccard é 1,0, mas isso é **vácuo**:
> `2026Q3` é o **último** trimestre da janela, não existe futuro para a lente descritiva escolher,
> então as duas coincidem **por construção**. Medido nas **58** referências que têm as duas lentes:
> **mediana 0,455 · média 0,461 · Q1 0,231 · Q3 0,600 · mínimo 0,000**, e **só 7 de 58** dão 1,0
> (`2011Q3` = 0,000, `2012Q1` = 0,000, `2015Q4` = 0,143, `2024Q4` = 0,333). E **2.751 das 5.500
> linhas (50,0%)** da variante descritiva têm vizinho **no futuro** da referência. Ou seja: a
> lente descritiva muda o conjunto de vizinhos em cerca de **55%** dos casos. Citar o 1,0 como
> "o achado mais forte" é o oposto do que o dado diz.

### 5.3 Constantes do contrato (não números soltos no código)

`K_VIZINHOS_PADRAO = 8` · `K_VIZINHOS_SENSIBILIDADE = (5, 8, 12)` ·
`N_TRIMESTRES_EXCLUIDOS_VIZINHANCA = 2` · `LIMIAR_SELIC_PP = 0.25` (**D-t:** a desigualdade do
ciclo é **não estrita**, `|Δ| >= 0,25` é movimento) · `N_ALERTA = 8` ·
`N_SUPRESSAO = 5` · `LIMIAR_TROCA_REGIME_INOPERANTE = 0.25` ·
`LIMIAR_CRESCIMENTO_PP = 0.0` · `LIMIAR_ACELERACAO_PP = 0.0` ·
`MIN_OBS_PADRONIZACAO_EXPANDING = 20` (constante **do módulo** `regimes_v3.py`, não deste contrato
— dívida em `TODO.md §6`) ·
`FEATURES_V3 = (z_ibcbr_gap, z_ipca_desvio_meta, z_juro_real_exante, z_inclinacao,
z_usdbrl_var_12m, z_termos_troca_yoy)`.

> **`FEATURES_V3`: 6 declaradas, 5 usadas** — o de/para medido, publicado em
> `relatorio_regimes_v3.json → features` para que a comparação seja automática:
>
> | declarada | o que roda | por quê |
> |---|---|---|
> | `z_ibcbr_gap` | **`focus_pib_ano`** (`z_crescimento_esperado`) | `ibcbr_gap` é nulo em `2026Q3` **por construção** e em `2006Q1..2009Q3` (D-m) — sem vetor para a pergunta do Comitê e sem a crise de 2008. **D-u** |
> | `z_ipca_desvio_meta` | **`ipca_12m_delta`** | `ipca_desvio_meta` é 100% nula (G-02, a série de metas do CMN não existe no projeto); a aceleração é o eixo que ADR-001 §4 adota |
> | `z_juro_real_exante` | `juro_real_exante` | — |
> | `z_inclinacao` | **`inclinacao_real_5a_3a`** | **D-i/D-n**: a 5a−1a tem 39,8% de nulos; a 5a−3a (95,25%) é a principal e é lida de `raw_series` |
> | `z_usdbrl_var_12m` | `usdbrl_var_12m` | — |
> | `z_termos_troca_yoy` | **CORTADA** | `termos_troca_yoy` é **100% nula** em `macro_quarterly`: nenhum índice de termos de troca foi extraído. O proxy IC-Br do BCB (SGS 27574/27575) é escopo de **F-037**. Preencher seria dado inventado (Anti-SPEC §10.1.1) |
>
> `n_features = 5` é publicado na linha (`RegimeNeighborsSchema.n_features ∈ {3,4,5,6}`): o corte é
> **declarado no dado**, nunca silencioso.

---

## 6. O que estes contratos deliberadamente **não** permitem

| Tentativa | O que acontece |
|---|---|
| gravar DataFrame com coluna extra | `strict=True` → `SchemaError` |
| linha canônica sem `source`/`series_id`/`fonte_versao` | `nullable=False` → `SchemaError` |
| célula de `macro_quarterly` sem linha de procedência | `macro_quarterly_provenance` tem PK `(quarter, column)`: a ausência é detectável por anti-join (teste de F-015, CA-120) |
| trimestre antes do início da série do ativo | check `sem_trimestre_antes_do_inicio_da_serie` falha (por **trimestre**, não por ano) |
| grade com 82 ou 84 trimestres | check `janela_de_83_trimestres` falha |
| misturar `asof` e `revised` na mesma tabela | check `lag_adjusted_homogeneo` falha |
| célula de métrica sem `n` | `n_obs` é `nullable=False` |
| identificador de série inventado ou vazio | validator do pydantic recusa |
| série "a confirmar" entrando como `ok` | `model_validator` recusa |
| `ffill` de 10 dias úteis | `le=5` no campo recusa |
| excesso sobre CDI por subtração | não é contrato de schema: é **teste obrigatório** (CA-069) |

---

## 6a. `internacional_por_regime` e `internacional_pesos` (RF-038/039) · **classe C**

`packages/shared/schemas/internacional.py` (**novo** em F-026, 2026-10-11; a edição em
`packages/shared/schemas/__init__.py` foi **aditiva**) · produzido por
`apps/pipeline/canonical/internacional.py` (CLI
`python -m apps.pipeline.canonical.internacional [--offline]`, ou a etapa `internacional` de
`python -m apps.pipeline run --offline`).

> **Numeração:** entra como **§6a**, não como §6, porque `CONTRACTS.md §7` e `§8` são citados de
> dentro do código (`alinhamento.py`, `build_raw_series.py`) e renumerar invalidaria as citações.
> Mesmo recurso já usado em §3.1, §5.1a e §5.2a.

### 6a.1 `InternacionalPorRegimeSchema` — PK `(lente, regime, asset_id)`, 18 colunas

`strict=True`, `coerce=True`. `lente ∈ {V1, V1_ASOF, V3}` — note que **não** é o enum de
`RegimeAssetMetricsSchema` (`{V1, V2, V3}`): aqui a materialização entra como **valor de lente**,
porque esta tabela não tem variante `asof` em arquivo separado. `asset_id` usa o **mesmo**
`ASSET_IDS_VALIDOS` de `asset_returns_quarterly` — nenhum ativo novo foi inventado.

| Coluna | Tipo | Nulo? | Semântica |
|---|---|---|---|
| `lente`, `regime`, `asset_id` | str | não | **PK**. `regime` = os 4 quadrantes da V1 ou `VIZINHOS_2026Q3` |
| `n_obs` | int ≥ 0 | não | `n` em **toda** célula (RN-04 / CA-108/109) |
| `ret_medio`, `ret_mediana`, `excesso_cdi`, `ret_real`, `hit_ratio_cdi` | float | sim | **importadas inteiras** de `metricas_regime.metricas_da_celula` (F-022) — CA-104 cumprido por `import`, não por texto. Resíduo medido contra `regime_asset_metrics.parquet`: **0,0 em 24 células** |
| `corr_ibov`, `corr_imab` | float ∈ [−1, 1] | sim | correlação condicional ao regime (CA-105) |
| `n_pares_ibov`, `n_pares_imab` | int ≥ 0 | não | o `n` **da correlação**, que não é o `n` da célula |
| `is_total_return` | `boolean` | sim | nulável de propósito: 820 linhas de `asset_returns_quarterly` não sabem. É o que separa `ACWI_BRL` (`True`) de `SP500_BRL` (`False`) |
| `alerta_n_baixo`, `conclusao_suprimida` | bool | não | `n < 8` / `n < 5` |
| `especificacao_congelada` | bool | não | o gate de CA-090 **na linha** |
| `fonte_versao` | str | não | hash do código (CA-088) |

**Checks de DataFrame:** `pares_de_correlacao_nunca_excedem_n_obs` e `correlacao_exige_pares` —
correlação sem ao menos 2 pares é **recusada**, nunca publicada como 0.

### 6a.2 `InternacionalPesosSchema` — PK `(escopo, chave, cap, carteira, asset_id)`, 13 colunas

| Coluna | Tipo | Nulo? | Semântica |
|---|---|---|---|
| `escopo` | str | não | `POR_REGIME` \| `EXPANDING` (sem look-ahead: um peso por trimestre) |
| `chave` | str | não | o regime (em `POR_REGIME`) ou o `quarter` (em `EXPANDING`) |
| `carteira` | str | não | a composição usada — `{CDI, IMAB, IBOV, ACWI_BRL}` |
| `asset_id` | str | não | ativo da carteira |
| `peso` | float ∈ [0, 1] | não | variância mínima **long-only** com cap |
| `cap` | float ∈ (0, 1] | não | o cap por ativo; a versão **sem cap** sai ao lado |
| `peso_na_banda` | float ∈ [0,15; 0,35] | sim | **só** no ativo internacional: o peso truncado na banda tática de ADR-003 |
| `n_obs` | int ≥ 0 | não | trimestres que entraram na covariância |
| `rho_shrinkage` | float ∈ [0, 1] | não | intensidade de Ledoit-Wolf **medida** (CA-084), nunca escolhida |
| `alerta_n_baixo`, `conclusao_suprimida`, `especificacao_congelada`, `fonte_versao` | — | não | como acima |

**Checks de DataFrame:** `pesos_somam_um_por_carteira`, `peso_respeita_o_cap`,
`banda_so_no_ativo_internacional`.

> ⚠️ **`internacional_pesos.parquet` está FORA da entrega v1 (`D6-d` / D-ab) e é marcado como NÃO
> PUBLICÁVEL no manifesto (D-af).** A variância mínima por regime é nomeada em **Anti-SPEC
> §10.3.16** e **§10.5** como fora desta versão, e o `TODO.md` de F-026 a manda para **F-035**. A
> tabela **é calculada** (era o insumo pedido para traduzir D6 em faixa), mas:
> `especificacao_congelada = False` em **toda** linha por construção; o relatório carrega
> `BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA` nomeando as duas seções e a feature destino; o CLI emite
> `WARNING` em toda execução; **o schema não tem coluna onde escrever previsão**
> (`retorno_esperado`, `recomendacao`, `alvo`) e há teste de contrato que falha se alguém
> acrescentar uma; e **não há backtest** — nenhuma série de retorno de carteira, nenhuma posição,
> nenhum rebalanceamento.
>
> **D-af, o mecanismo:** `apps/pipeline/run.py` tem a lista `ARTEFATOS_NAO_PUBLICAVEIS`; o
> `MANIFEST.json` grava `publicavel: false` + `motivo_nao_publicavel` **na entrada do artefato**, e
> o `FROZEN.txt` abre uma seção `EXCLUIDOS DO PACOTE DE ENTREGA`. **F-031 lê esse campo**, não uma
> convenção de nome de arquivo. O artefato **continua** no `DATASET_SHA256`: o agregado descreve o
> que foi **construído**, e tirá-lo do hash confundiria reprodutibilidade com publicabilidade.
>
> **`internacional_pesos.parquet` NÃO entra no pacote de F-031.** O que é publicável de F-026
> depois de ADR-001/ADR-003 aceitos: os retornos por regime, as correlações de CA-104/105, o
> `stress_flag` de CA-106 e a **faixa** de CA-107 — nenhum deles depende da tabela de pesos.

> **Estado medido em 2026-10-11:** `internacional_por_regime.parquet` **54 × 18** ·
> `internacional_pesos.parquet` **624 × 13**. `stress_flag = 1` em **20 de 83** trimestres (7 só
> pelo ramo da inclinação, 11 só pelo ramo do câmbio, 2 pelos dois); **14** trimestres **não
> avaliáveis** pelo ramo da inclinação. `corr(USDBRL, IBOV)` = **−0,795** nos 20 de stress contra
> **−0,418** nos 62 de não stress. Variância mínima com `cap = 0,40`: internacional de **15,9% a
> 23,6%** por regime; **sem cap**, o *expanding* médio cai de **19,65%** para **10,41%** — é essa
> sensibilidade que faz CA-107 entregar **faixa**, nunca número pontual.

---

## 7. `calendario_dias_uteis` — grade de dias úteis da ANBIMA (RF-018)

`packages/shared/schemas/calendario.py` · produzido por `apps/pipeline/extract/calendario_anbima.py`
(F-008) · consumido por F-014 (alinhamento) e F-017 (retornos). **Acréscimo de 2026-10-11** (D-f): o
schema nasceu dentro do extrator e migrou para o pacote de schemas, porque é contrato de dado.

| Coluna | Tipo | Nulo? | Semântica |
|---|---|---|---|
| `data` | datetime | não | **PK**, única; a grade é **civil** e contínua (todo dia do intervalo) |
| `dia_util` | bool | não | seg-sex **e** não feriado nacional |
| `feriado` | string | sim | nome do feriado; nulo = não é feriado (independe de ser fim de semana) |
| `fonte` | str | não | `isin=["ANBIMA_WEB"]` — **lista**, nunca tupla de 1 (ver abaixo) |

- **Não é `processed_series`:** não tem `value`/`unit`/`freq`/`vintage`/`collected_at`. Não é uma série
  de valores, é uma grade de datas com dois atributos — a procedência fica no manifesto de cada página
  em `data/raw/anbima-feriados/*.meta.json` (`sha256`, URL, hora da coleta), e é isso que deixa o
  Parquet **byte-idêntico** entre execuções (RF-048 conferível por `sha256`, não por "quase igual").
- **Checks:** `grade_civil_sem_lacuna` (um dia por data, sem buraco, crescente), `feriado_nunca_e_dia_util`
  e `fim_de_semana_nunca_e_dia_util`.
- **Cobertura atual:** 2001-01-01 → 2030-12-31 (10.957 dias, 7.530 úteis, 367 feriados). Consulta fora
  do intervalo **levanta** `ForaDaCoberturaDoCalendario` — "não sei" nunca vira "não tem feriado".
- **Armadilha do pandera (medida):** `isin` de **um** valor tem de ser `list`. `isin=("ANBIMA_WEB",)`
  reprova toda linha nesta versão, porque a tupla de um elemento é desempacotada e o `set` vira o
  conjunto de *letras* da string. Tupla com 2+ itens funciona — é por isso que `FONTES_VALIDAS` em
  `raw_series.py` passa.

---

## 8. `alinhado_trimestral` — a grade trimestral *long*, antes de qualquer cálculo (RF-023) · **classe C**

`packages/shared/schemas/alinhado_trimestral.py` → `AlinhadoTrimestralSchema` · produzido por
`apps/pipeline/canonical/alinhamento.py` (F-014, CLI
`python -m apps.pipeline.canonical.alinhamento [--offline]`) · consumido por **F-015**
(`macro_quarterly`), **F-016** (curva) e **F-017** (`asset_returns_quarterly`).
**PK `(series_id, quarter)`**, 18 colunas em ordem fixa (`COLUNAS_ALINHADO`), 11 checks de DataFrame.

**O que a tabela é.** Uma linha por `(quarter, series_id)` dizendo **qual observação da série
representa aquele trimestre** — e, quando nenhuma representa, **por quê**. Nada é calculado: `value`
é, bit a bit, o valor que `raw_series` tem em `date_obs` (sem interpolação, média de período,
reescala ou preenchimento com `0` — Anti-SPEC §10.1.1/§10.1.4). É ela que dá **uma régua só** a
F-015/F-016/F-017, em vez de três cópias da regra, e deixa o `ffill` **auditável por célula** antes
de virar retorno.

| Coluna | Tipo | Nulo? | Regra |
|---|---|---|---|
| `quarter` | str | não | `2006Q1`..`2026Q3` (mesmo regex de `macro_quarterly`) |
| `quarter_end` | datetime | não | **último dia útil bancário** (ANBIMA) do trimestre — **igual em todas as linhas do trimestre** |
| `series_id` | str | não | existe em `series_catalog` |
| `grade` | str | não | `bancaria` \| `corrido` \| `civil` — a régua **desta** linha |
| `date_alvo` | datetime | não | a data que esta linha buscou, segundo `grade` |
| `date_obs` | datetime | **sim** | data da observação usada; nula ⇔ `value` nulo |
| `value` | float | **sim** | o valor de `raw_series` em `date_obs`, sem transformação |
| `ffill_dias_uteis` | int | não | 0..**5** (ADR-006 §(b).8); dias úteis de ffill **aproveitados**, `0` na célula nula |
| `date_ultima_obs` | datetime | sim | última observação disponível até o alvo, **usada ou não** |
| `lacuna_dias_uteis` | int ≥ 0 | não | dias úteis em `(date_ultima_obs, date_alvo]`, **medidos sempre** |
| `motivo_nulo` | str | sim | `lacuna_acima_do_limite_de_ffill` \| `sem_observacao_ate_a_data_alvo` — os **dois** únicos |
| `freq`, `unit`, `source` | str | não | mesmos enums de `raw_series`; constantes por série |
| `vintage` | datetime | sim | safra usada nesta materialização (a **mais recente** — ver abaixo) |
| `collected_at` | datetime | não | do dado, nunca do relógio da rodada |
| `data_inicio_serie` | datetime | não | `data_inicio_observada` do catálogo materializado (CA-063) |
| `fonte_versao` | str | não | `sha256` do código que alinhou a linha (RF-047/CA-121) |

**As três grades, uma só chave de junção.** `quarter_end` é sempre o último dia útil bancário — é a
grade única de ADR-006 e a chave com que `macro_quarterly` e `asset_returns_quarterly` se juntam. O
que varia por série é `date_alvo`: `bancaria` (série `freq=D` de dia útil → `quarter_end`),
`corrido` (série `freq=D` que o catálogo marca `calendario='corrido'` → último dia **civil**) e
`civil` (`freq=M`/`Q`/`A`, cujo `date` já é fim de período civil por D-a → último dia civil). Em
**24 dos 83** trimestres as duas datas divergem (1 a 3 dias civis, nunca dia útil), e a divergência
fica **legível no dado, em duas colunas**. A régua `corrido` é **derivada de `calendario`** (§2), não
de uma lista dentro do módulo.

**Forward-fill: duas colunas, não uma.** `lacuna <= 5` → o valor é usado e
`ffill_dias_uteis == lacuna_dias_uteis`. `lacuna > 5` → `value = NULL`, `date_obs = NULL`,
`ffill = 0`, `motivo_nulo` preenchido e `date_ultima_obs`/`lacuna_dias_uteis` **registrando a lacuna
rejeitada** (CA-067) — é o que separa "não há dado" de "havia dado longe demais para servir". Mês ou
trimestre não divulgado cai na **mesma** regra, não numa exceção: um mês atrás são ~21 dias úteis e
um trimestre ~65. **Nenhuma linha herda o período anterior.**

**Materialização `revised`, declarada.** `selecionar_vintage` mantém, por série, **só o último
`vintage`** — é o que impede duas linhas para a mesma `(series_id, quarter)` quando o IBGE revisa o
PIB (D-b). A variante `asof` é **F-018** e esta tabela **não** a simula. Também **nenhuma linha é
`is_estimated`**: aqui o trimestre incompleto aparece com `value = NULL` + `motivo_nulo`, e a flag é
de F-015 (CA-060).

**Checks de DataFrame (11).** `quarter_dentro_da_janela_de_83` ·
`quarter_end_e_date_alvo_caem_no_trimestre` (CA-065) · **`quarter_end_unico_por_trimestre`** (é a
opção **(a)** de D-h travada no contrato: virar para duas grades exige mudar o schema, não só o
código) · `nulo_tem_motivo_e_nao_tem_data` · `ffill_e_a_lacuna_quando_ha_valor` ·
`lacuna_acima_do_limite_nunca_tem_valor` (CA-067) · `observacao_nunca_depois_do_alvo` (base do
`asof`, §10.2.7) · `date_obs_e_a_ultima_observacao_disponivel` ·
**`sem_linha_antes_do_inicio_da_serie`** (CA-063 — é o que impede o backfill sintético de voltar por
descuido) · `metadado_constante_por_serie` · unicidade da PK.

**Quem fica fora, e por quê.** Toda série `source = DERIVADO` (`FONTES_FORA_DO_ALINHAMENTO`): a
derivação tem convenção própria de data e de lacuna — um vértice pode ser `NULL` por não existir
vencimento, o que **não** é lacuna de calendário —, então é a feature dona dela (F-016, F-017) que
chama `alinhar_series` sobre o seu próprio resultado. O motivo está no dado
(`relatorio_alinhamento.json → series_fora_do_alinhamento`), série a série.

> **Estado medido em 2026-10-11:** **4.038** linhas (= 49 × 83 − 29 do painel desbalanceado), **49**
> séries, **83** trimestres; por `grade` `bancaria` 2.793 · `civil` 1.162 · `corrido` 83;
> `ffill_dias_uteis = {0: 3.823, 1: 215}` — **nenhum valor 2..5**, e os 215 são exatamente a conta de
> **D-h** (11 séries `B3_API` × 20 quartos trimestres de 2006 a 2025); **7** células nulas (PIB e
> IBC-Br em 3T2026, com `lacuna` 65 e 42); **0** PK duplicada. Companheiro:
> `relatorio_alinhamento.json`, com a grade dos 83, o ffill por série **e** por trimestre, 1 bloco
> por série e a escolha de D-h escrita em `decisao_d_h`.

---

## 9. Como evoluir um contrato

1. Feature Contract **classe C** no `TODO.md` (schema canônico = classe C, `AGENTS.md §2`).
2. Altere o schema em `packages/shared/schemas/` **primeiro**.
3. Atualize este espelho na mesma PR.
4. Rode o CI N2: `pytest tests/contract tests/integration` + build do canônico sobre fixtures.
5. **Diff numérico** vs. a versão anterior do canônico, com cada divergência explicada.
6. Reconstrução completa de `data/canonical/` a partir de zero.
7. Revisão numérica independente (quem calculou não confere) + 1 linha em `docs/wiki/log.md`.
8. Se houve trade-off arquitetural → ADR. Se houve troca de fonte → `DECISIONS_LOG.md`.

---

## 10. `web_views` — as views do portal (F-W001) · **classe C**

> **Fonte de verdade:** `packages/shared/schemas/web_views.py` (pydantic). **Derivado:**
> `schema.d.ts`, gerado por `apps/web_export/tipos_ts.py` no mesmo comando que escreve o JSON —
> **46 interfaces**, nunca escritas à mão. Este bloco é espelho legível dos dois.
>
> Contrato entre **dois repositórios**: este pipeline (produtor) e o portal LDC Analytics
> (consumidor, o módulo `/admin/analytics-macro` em `apps/web_export/modulo-site/`). Quem muda um
> campo aqui muda o `.d.ts` e o `tsc` do outro lado aponta o que quebrou — é a trava desenhada no
> lugar do acordo verbal.

```
packages/shared/schemas/
└── web_views.py                ← MetaWeb, PonteiroCurrent, as 6 views + 38 modelos de apoio,
                                   UNIDADE_POR_CAMPO, CASAS_POR_UNIDADE,
                                   APRESENTACAO_POR_UNIDADE, VIEWS, SCHEMA_VERSAO   (pydantic)
```

### 10.1 Arquivo → modelo → tela

Um comando (`python -m apps.web_export exportar --tag <tag> --destino <dir>`) escreve
`<destino>/<tag>/` + `current.json` **no pai**:

| Arquivo | Modelo | Tela | O que carrega |
|---|---|---|---|
| `meta.json` | `MetaWeb` | todas (rodapé) | tag, `DATASET_SHA256`, `versao_build` das 10 etapas, data **do dado**, gate, `sha256` + bytes de cada view, contagens, limitações, as tabelas de unidade e de apresentação, reduções, orçamento, artefatos não publicáveis |
| `ranking_atual.json` | `RankingAtualView` | T-01 | as **3** respostas de regime (nenhuma escolhida), os 3 rankings, a concordância como distribuição, os vizinhos do trimestre, a interseção dos top-5 |
| `heatmap_regime_ativo.json` | `HeatmapView` | T-02 | as células como plotadas, os eixos `(vista, regime)`, os **eixos de cor** por vista, os ativos na ordem declarada, os 2 limiares de `n`, as exclusões da figura |
| `vizinhos.json` | `VizinhosView` | T-03 | a lente canônica campo a campo, as referências, o ranking em T+1 com erro-padrão, o quadrante por trimestre |
| `regimes_timeline.json` | `TimelineView` | T-04 | trimestre × materialização, o estilo por rótulo de faixa, IBOV e Selic por trimestre, as divergências nomeadas |
| `internacional.json` | `InternacionalView` | T-06 | o internacional em BRL, as correlações **com `n`**, a faixa de D6, os não avaliáveis — **sem** variância mínima nem peso |
| `catalogo.json` | `CatalogoView` | T-07 | as séries com cobertura declarada × observada, os artefatos, as limitações, as decisões, os ADRs |
| `schema.d.ts` | — | — | os tipos TypeScript dos modelos acima |
| `current.json` (no **pai**) | `PonteiroCurrent` | — | o **único** ponteiro: tag, hash, `arquivos` view → caminho. `no-cache`, gravado **por último** |

T-05 (Ativo em foco) **não tem view**: é v2 no PRD §10 e a omissão está declarada em
`meta.reducoes`. `catalogo` ocupa o slot `macro_series` de `[arq §1.1]` (ADR-008).

### 10.2 O envelope comum — `EnvelopeDaView`

Herdado por **todas** as 6 views, nunca copiado:

| Campo | O que é |
|---|---|
| `view` | o nome do arquivo sem extensão |
| `tela` | a tela do PRD §4 que consome (T-01..T-07) |
| `pergunta` | a frase de abertura da tela (P7 / RF-W035) — pergunta, não conclusão |
| `tag` | a tag exportada; a tela recusa se divergir do ponteiro |
| `dataset_sha256` | o agregado do `MANIFEST.json`, repetido em cada arquivo de propósito |
| `gate` | `GateDaView`: `especificacao_congelada`, `status_adr_001`, `veredito_publicacao`, `marca`, `publicavel` |
| `fontes` | os artefatos do `MANIFEST.json` lidos para montar a view |

### 10.3 As cinco regras que o módulo faz valer

1. **`extra="forbid"` em todo modelo.** É a forma executável de "nenhuma view carrega coluna que
   não esteja no contrato" (RF-W015): campo a mais ⇒ `ValidationError` nomeando campo e view, nunca
   um JSON publicado com coluna que o portal não sabe ler. O teste de contrato fecha o triângulo
   nos dois outros sentidos: toda chave emitida existe no `.d.ts`, e o topo de cada arquivo **é** a
   interface dele, campo a campo.
2. **Nullable explícito.** Ausência sai `null`, **nunca `0`** e nunca interpolada
   (Anti-SPEC §10.1.1 / RNF-W010): `NaN`, `inf` e `NaT` viram `null` no único lugar onde valor vira
   JSON (`views.escalar`), e o tipo gerado é `number | null` — então a tela é obrigada pelo `tsc` a
   decidir o que desenhar na ausência. `-0.0` é normalizado para `0.0`, porque o sinal do zero muda
   o byte sem mudar o número.
3. **Unidade por campo, e apresentação declarada.** `UNIDADE_POR_CAMPO` dá a unidade **nativa** de
   cada campo numérico e `CASAS_POR_UNIDADE` as casas com que ele é arredondado — campo numérico
   novo sem unidade **reprova** no CI. O exportador não converte valor (D-W4): `excesso_cdi` e os
   `ret_*` saem em **fração** e `selic_meta_pct` em **% a.a.**, que é o erro de 100× barato deste
   dado (`LIMITACOES-COMITE.md §4.9`). Desde 2026-10-11 o `meta` declara também **como apresentar**,
   campo a campo — `unidade_de_apresentacao`, `fator_de_apresentacao` e `casas_de_apresentacao` —
   para que a conversão da tela (`0,0504` → `+5,04%`) seja leitura de tabela e o fator `100` esteja
   escrito de um lado só.
4. **Gate em toda view, decidido no exportador.** `GateDaView` é lido do **ADR-001 em disco** e
   viaja nas 6 views e no `meta`; com o ADR em `Proposta`, `especificacao_congelada = false` e toda
   tela nasce com a faixa de material de discussão. O gate vive no produtor, não no front
   (`[arq §7.1]`), porque o bundle que desce ao browser é texto baixável: filtro no front seria
   decoração. **Falha fechada** — ADR ausente ou ilegível ⇒ `DESCONHECIDO` e gate fechado. E a
   lista de inclusão **não vence o manifesto**: artefato `publicavel: false` lido ⇒ a exportação
   **recusa** (hoje `internacional_pesos.parquet`, **D-af**).
5. **`n` em toda célula, e `n < 5` sai com o valor E com a flag.** `alerta_n_baixo` em `n < 8` e
   `conclusao_suprimida` em `n < 5` — as duas vindas de `regimes_v1`, **importadas**, nunca
   reimplementadas; se o Parquet trouxer a flag errada para o `n`, a exportação **para**. A
   supressão não esvazia a célula: o número continua no JSON porque a tela mostra "sem conclusão
   (n = 4)", e é a flag que proíbe a conclusão, não a ausência do número (P10 / RNF-W010). Cor
   nunca é o único canal: `hachura` e `conclusao_suprimida` são canais **sem** cor (CA-109).

### 10.4 Cor e eixo de cor

A view publica o **eixo** da escala, não a cor: `eixos_de_cor` traz `extremo_simetrico` =
`max(|valor|)` por `(vista, campo)` sobre a **vista inteira** — extensão de eixo, não estatística —
em unidade nativa, para que `-x` e `+x` caiam no mesmo passo e o neutro do meio signifique
"empatou". Extremo que dependesse do recorte filtrado repintaria as outras classes quando alguém
marcasse uma. Hex **não** é emitido (**D-ai**): a paleta é decisão de apresentação e vive em quem
desenha.

### 10.5 Como evoluir

O §9 vale integralmente, com dois acréscimos: (a) o `schema.d.ts` é **regerado** pelo próprio
comando de exportação — nunca editado —, e a cópia que o módulo do portal carrega em
`_lib/schema.d.ts` tem de voltar byte-idêntica à gerada; (b) **remover** campo sobe
`SCHEMA_VERSAO` (hoje **2**), acrescentar não.
---

*Divergência entre este arquivo e `packages/shared/schemas/` é bug deste arquivo. Corrija aqui, não lá.*
