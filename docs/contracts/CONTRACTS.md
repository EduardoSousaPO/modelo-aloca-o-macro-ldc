# CONTRACTS — Estratégia Macro LDC

> **Espelho legível.** A **fonte de verdade são os schemas em `packages/shared/schemas/`**
> (`pandera` para DataFrame, `pydantic` para catálogo e config de extrator). Este arquivo descreve —
> nunca duplica a definição e nunca a contradiz.
>
> **Versão:** 1.0 — **Data:** 2026-10-10 — **Referência:** `docs/specs/SPEC.md` v1.0 (RF-019..RF-032),
> `docs/research/metodologia-regimes-macro.md §6`.
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
├── series_catalog.py           ← SeriesCatalogEntry, ExtractorConfig,
│                                  SeriesCatalogSchema, enums, load_catalog()       (pydantic+pandera)
├── series_catalog_data.py      ← O CATÁLOGO COMO DADO — 132 séries
├── macro_quarterly.py          ← MacroQuarterlySchema                              (pandera)
├── asset_returns_quarterly.py  ← AssetReturnsQuarterlySchema,
│                                  RegimeAssetMetricsSchema                         (pandera)
└── regimes.py                  ← RegimesSchema, RegimeNeighborsSchema, enums       (pandera)
```

Fronteiras onde a validação é **obrigatória** (`wiki/architecture.md §4`):

| Fronteira | Schema |
|---|---|
| saída de cada extrator → `data/processed/` | `ProcessedSeriesSchema` |
| `data/processed/` → `data/canonical/` | `RawSeriesSchema` + schema da tabela destino |
| entrada e saída de `data/canonical/` | `MacroQuarterlySchema`, `AssetReturnsQuarterlySchema`, `RegimesSchema`, `RegimeNeighborsSchema`, `SeriesCatalogSchema` |
| config de extrator / parâmetros de janela | `ExtractorConfig` (pydantic) |
| catálogo de séries | `SeriesCatalogEntry` (pydantic) |

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
| `vintage` | datetime | sim | data em que o valor foi conhecido; nulo = série não revisável |
| `unit` | str | não | `%`, `%/dia`, `%a.a.`, `pp`, `index`, `BRL`, `USD`, `ratio`, `bps`, `R$ milhoes` |
| `collected_at` | datetime | não | quando o pipeline baixou |

- **PK:** `(series_id, date, vintage)` → duas extrações do mesmo ponto coexistem como vintages (CA-056).
- **Check de DataFrame:** `sem_data_futura` — `date <= collected_at` (pega a meta Selic com data futura).
- `strict=True`: coluna fora do schema **falha**. É o que impede DataFrame ad hoc (Anti-SPEC §10.4.24).
- `ProcessedSeriesSchema` herda o mesmo contrato para `data/processed/`.

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

**Propriedades derivadas:** `cobre_2006` (`None` quando o início não foi medido) e
`usavel_no_pacote_minimo` (só `status = ok`).

### 2.1 Estado do catálogo em 2026-10-10 (132 séries, validadas por pydantic)

| Status | n | Leitura |
|---|---|---|
| `ok` | **99** | usáveis; 63 delas cobrem 1T2006 com início medido |
| `a_confirmar` | **8** | identificador não confirmado pela pesquisa — **fora do caminho crítico** |
| `descontinuada` | **10** | morreram numa data (swap DI×pré, IMA no SGS, IMA-C, EMBI+, `DTWEXM`) |
| `descartada` | **14** | existem mas não servem (janela curta, não cobrem 2006, fora do escopo mínimo, armadilha) |
| `paga` | **1** | ANBIMA Feed (ETTJ histórica) — fora de escopo por decisão L4 |

| Fonte | n | | Fonte | n |
|---|---|---|---|---|
| `BCB_SGS` | 36 | | `YAHOO` | 12 |
| `B3_API` | 13 | | `ANBIMA_S3` | 11 |
| `FRED` | 13 | | `IBGE_SIDRA` | 9 |
| `DERIVADO` | 7 | | `IPEADATA` | 7 |
| `TEVA_GCS` | 6 | | `BCB_OLINDA` | 6 |
| `MSCI` | 5 | | `ANBIMA_WEB` | 4 |
| `TESOURO_CKAN` | 1 | | `CVM` / `MANUAL` | 1 / 1 |

Confiança: `CONFIRMADO` 79 · `CONFIRMADO_SUB` 40 · `NAO_VERIFICADO` 13 (os 13 são, na maioria, as
**séries derivadas por nós** — curva interpolada e inclinação — que exigem conferência numérica
classe C antes de virar número em slide).

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

**Duas materializações:** `macro_quarterly_asof` (`lag_adjusted=True`, para decisão) e
`macro_quarterly_revised` (`lag_adjusted=False`, para descrição histórica). Na v1 a divergência de
classificação entre as duas é **reportada** (RF-025); a dupla materialização completa é fase 2.

Colunas nulas são **legítimas e informativas**: `ipca_meta` (série de metas é gap G-02),
`embi_br_fim` após 30/07/2024, `curva_nominal_*` onde o vértice não existe. Nulo **nunca** é
preenchido para "fechar" a linha.

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
`sem_trimestre_antes_do_inicio_da_serie` (**proíbe backfill sintético** — CA-063).

### 4.1 `RegimeAssetMetricsSchema` — métricas por regime × ativo (RF-032/040)

PK `(lente, regime, asset_id)`, com `lente ∈ {V1, V2, V3}`.
Colunas: `n_obs`, `ret_medio`, `ret_mediana`, `ret_desvio`, `erro_padrao_media`, `hit_ratio`,
`excesso_cdi`, `hit_ratio_cdi`, `ret_real`, `sharpe_tri`, `pior_tri(_quarter)`,
`melhor_tri(_quarter)`, `beta_ibov`, `alerta_n_baixo` (`n < 8`), `conclusao_suprimida` (`n < 5`),
`data_inicio_serie`, `fonte_versao`.

> `n_obs` é obrigatório e não anulável **por contrato**: é o que garante "`n` em toda célula de toda
> tabela" (RN-04).

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

### 5.2 `RegimeNeighborsSchema` — PK `(quarter_ref, rank, metrica, k_usado, restrito_pos_2016)`

`distancia` ≥ 0 · `metrica` ∈ {`mahalanobis`, `euclidiana`} · `k_usado` ∈ {5, 8, 12} ·
`n_features` ∈ {5, 6} (**5 quando a curva não ficou pronta — declarado, não silencioso**) ·
`regime_v1_neighbor` · `shrinkage` (`ledoit_wolf` obrigatório em Mahalanobis) ·
`restrito_pos_2016` (variante de robustez) · `fonte_versao`.

**Check:** `exclui_vizinhos_adjacentes` — o trimestre de referência não é vizinho de si mesmo; a
exclusão dos 2 trimestres anteriores é verificada no teste da feature (CA-085).

### 5.3 Constantes do contrato (não números soltos no código)

`K_VIZINHOS_PADRAO = 8` · `K_VIZINHOS_SENSIBILIDADE = (5, 8, 12)` ·
`N_TRIMESTRES_EXCLUIDOS_VIZINHANCA = 2` · `LIMIAR_SELIC_PP = 0.25` · `N_ALERTA = 8` ·
`N_SUPRESSAO = 5` · `LIMIAR_TROCA_REGIME_INOPERANTE = 0.25` ·
`FEATURES_V3 = (z_ibcbr_gap, z_ipca_desvio_meta, z_juro_real_exante, z_inclinacao,
z_usdbrl_var_12m, z_termos_troca_yoy)`.

---

## 6. O que estes contratos deliberadamente **não** permitem

| Tentativa | O que acontece |
|---|---|
| gravar DataFrame com coluna extra | `strict=True` → `SchemaError` |
| linha canônica sem `source`/`series_id`/`fonte_versao` | `nullable=False` → `SchemaError` |
| trimestre antes do início da série do ativo | check `sem_trimestre_antes_do_inicio_da_serie` falha |
| grade com 82 ou 84 trimestres | check `janela_de_83_trimestres` falha |
| misturar `asof` e `revised` na mesma tabela | check `lag_adjusted_homogeneo` falha |
| célula de métrica sem `n` | `n_obs` é `nullable=False` |
| identificador de série inventado ou vazio | validator do pydantic recusa |
| série "a confirmar" entrando como `ok` | `model_validator` recusa |
| `ffill` de 10 dias úteis | `le=5` no campo recusa |
| excesso sobre CDI por subtração | não é contrato de schema: é **teste obrigatório** (CA-069) |

---

## 7. Como evoluir um contrato

1. Feature Contract **classe C** no `TODO.md` (schema canônico = classe C, `AGENTS.md §2`).
2. Altere o schema em `packages/shared/schemas/` **primeiro**.
3. Atualize este espelho na mesma PR.
4. Rode o CI N2: `pytest tests/contract tests/integration` + build do canônico sobre fixtures.
5. **Diff numérico** vs. a versão anterior do canônico, com cada divergência explicada.
6. Reconstrução completa de `data/canonical/` a partir de zero.
7. Revisão numérica independente (quem calculou não confere) + 1 linha em `docs/wiki/log.md`.
8. Se houve trade-off arquitetural → ADR. Se houve troca de fonte → `DECISIONS_LOG.md`.

---

*Divergência entre este arquivo e `packages/shared/schemas/` é bug deste arquivo. Corrija aqui, não lá.*
