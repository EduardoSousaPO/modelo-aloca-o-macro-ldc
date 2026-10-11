# Módulo `canonical` — camada canônica trimestral (**classe C**)

> Verdade: `docs/specs/SPEC.md` RF-019..RF-026 + `packages/shared/schemas/` + **ADR-006** (em
> `Proposta`) + `docs/contracts/CONTRACTS.md §1.1/§2.4/§8`.
> **Estado (2026-10-11): a camada está completa.** F-013, F-014, F-016, **F-015** e **F-017**
> entregues (QA/revisão numérica pendente); o Focus (F-010) é consumido direto de
> `data/processed/focus/`. Tudo aqui é **classe C** (`AGENTS.md §2`):
> um trimestre desalinhado contamina retorno, regime e heatmap **sem levantar exceção**.

| Tabela / artefato | Schema | Estado medido em 2026-10-11 |
|---|---|---|
| `raw_series.parquet` (nativa, PK `series_id,date,vintage`) | `raw_series.py` | **278.439** linhas · **62** séries · 1979-12-31 → 2026-10-10 · `linhas_dedup = 0` |
| `series_catalog.parquet` materializado | `series_catalog.py` (`SeriesCatalogMaterializedSchema`) | **138 × 26** (20 declaradas + 6 observadas) · 62 presentes · 59 cobrem 1T2006 |
| `alinhado_trimestral.parquet` (PK `series_id,quarter`) | `alinhado_trimestral.py` | **4.038** linhas · 49 séries · 83 trimestres · 215 ffill · 7 nulos |
| `relatorio_build.json` · `relatorio_alinhamento.json` | — | `versao_build e48262bb…` / `ae18c930…` · hashes, 1 bloco por série, ausências com motivo |
| `ldc.duckdb` (derivado, descartável) | — | **views** `raw_series` e `series_catalog` sobre os Parquet |
| `macro_quarterly.parquet` (PK `quarter`) | `macro_quarterly.py` | **83 × 42** · 2006Q1..2026Q3 · `revised` · **5** colunas 100% nulas, todas por gap declarado · 16 nulos em `ibcbr_gap` (**D-m**) |
| `macro_quarterly_provenance.parquet` (PK `quarter,column`) | `macro_quarterly.py` | **2.548** linhas · **32** colunas rastreáveis · **20** séries de origem · CA-120 por anti-join nas 2 direções |
| `asset_returns_quarterly.parquet` (PK `quarter,asset_id`) | `asset_returns_quarterly.py` | **1.963** linhas · **24** ativos (USDBRL entrou por **D-l**) · 83 trimestres · 215 ffill · 820 `is_total_return` nulos (G-01) |
| `relatorio_macro.json` · `relatorio_retornos.json` | — | nulos **por coluna com motivo**, unidades, canários, anti-look-ahead, `bases_por_trimestre` |
| `calendario_dias_uteis` (grade de dias úteis) | `calendario.py` | 10.957 dias, 2001→2030 (F-008) |

Os **quatro** builds, **nesta ordem** e nenhum deles lendo o relógio (idempotentes, CA-121):
`build_raw_series` (F-013) → `alinhamento` (F-014) → `macro_quarterly` (F-015) → `retornos`
(F-017), todos `python -m apps.pipeline.canonical.<módulo> --offline`. `curva` (F-016) escreve em
`data/processed/` e por isso roda **antes** do primeiro. Rebuild de 2026-10-11, 2 rodadas com
hashes idênticos: `raw_series 0d23df7a…` · `alinhado ac0d9842…` · `macro dcded731…` +
`provenance 4a582c1d…` · `asset_returns ab61eeca…`.

**Unidade — a diferença que mais pode machucar (D-o):** `macro_quarterly` está em **por cento/pp**
e `asset_returns_quarterly` em **fração**. As duas publicam `cdi_tri` e `ipca_tri`, com o **mesmo
nome em escalas diferentes** — quem cruzar sem ler a unidade erra por 100x. Não há bug hoje porque
F-017 calcula as duas por conta própria e **nunca** lê `macro_quarterly`; a reprodução cruzada deu
`max |macro − 100 × retornos| = 0,0` nos 83 trimestres. Ver `CONTRACTS.md §3/§4`.

## O que esta camada fixou (e que F-015/F-017 herdam)

- **`raw_series` é um *union* validado, e nada mais.** Zero agregação, reamostragem, `ffill` ou
  arredondamento: cada série é idêntica **célula a célula** à origem em `data/processed/`. O Parquet
  é **reescrito inteiro** a cada build — **não há `append`**, então série nova só aparece depois de
  **reexecutar** o build (item de DoR de F-010/F-011/F-012/F-016).
- **Quatro guardas públicas** que o pandera não cobre: `validar_procedencia` (CA-055/CA-120),
  `validar_frequencia_nativa` (CA-058), `validar_sem_mistura_de_fontes` (CA-077) e `exigir_series`
  (CA-076 → `BLOQUEADO — FONTE INDISPONÍVEL`). **Importe-as**, não reimplemente.
- **Declarado × observado coexistem no catálogo:** `data_inicio` (pesquisa) ao lado de
  `data_inicio_observada` (disco). A divergência **é informação**, e 3 checks impedem copiar um no
  outro. `calendario` (`dias_uteis`/`corrido`) é de onde F-014 deriva a régua da série.
- **Uma régua só, em 3 grades.** `quarter_end` é **sempre** o último dia útil bancário (chave de
  junção); `date_alvo` varia por série (`bancaria`/`corrido`/`civil`) e em **24 dos 83** trimestres
  as duas datas divergem — legível em **duas colunas**, não deduzido do código.
- **ffill em duas colunas:** `lacuna_dias_uteis` é medida **sempre**; `ffill_dias_uteis` só quando o
  valor foi aproveitado. Acima de **5 d.u.** a célula é `NULL` com `motivo_nulo` e a lacuna
  **registrada** (CA-067). Mês/trimestre não divulgado cai na **mesma** regra, não numa exceção.
- **Materialização `revised`, declarada:** só o último `vintage` por série (D-b); `asof` é F-018, e
  **nenhuma linha é `is_estimated`** (a flag de 3T2026 é de F-015, CA-060). **Séries `DERIVADO`
  ficam fora do alinhamento genérico** (9 hoje), porque a derivação tem convenção própria de data e
  de lacuna: quem chama `alinhar_series` é a feature dona (F-016, F-017).

## Armadilhas

- **Trimestral como dado primário é erro irreversível:** granularidade nativa + **agregação por
  função**; trimestre = **último dia útil**.
- **D-h está decidida: opção (a)** — grade bancária única. O calendário da ANBIMA é **idêntico** ao do
  CDI e do IMA-B em 20 anos, mas **B3 ⊂ ANBIMA em 69 datas**, nunca o inverso: toda série da B3 leva
  `ffill_dias_uteis = 1` em todo 4T — **215** células de 4.038 (5,325%), 11 séries, 20 trimestres,
  **zero** ffill de 2..5. Travado pelo check `quarter_end_unico_por_trimestre`; (b) é mudança de
  **schema**. Vai à página de limitações (F-028).
- **Excesso sobre CDI e retorno real sempre por razão** `(1+r)/(1+b)−1`: com Selic a 14% a diferença
  não é arredondamento. Teste anti-subtração é obrigatório.
- **Look-ahead é o risco dominante:** PIB e IBC-Br são **revisados retroativamente** e têm defasagem
  (`lag_divulgacao_dias = 60`) → nenhum T é classificado com dado publicado após o fim de T sem a
  flag `asof` (RF-025).
- **Painel desbalanceado é a regra:** ICON 2007+, IMOB 2008+, IFIX 2011+, FII 2019+ → **nenhuma linha
  antes do início real** (check `sem_linha_antes_do_inicio_da_serie`: **29** linhas que não existem
  em `alinhado_trimestral`), com `n` + `data_inicio` visíveis em toda tabela.
- **`strict=True` nos schemas:** nenhuma coluna ad hoc — **`vertice_extrapolado` de CA-023 não é
  coluna** do canônico (ver `tesouro.md`), e torná-la coluna é feature classe C própria. **O painel
  do Tesouro e o calendário não entram em `raw_series`** (schema próprio, 750 `series_id` fora do
  catálogo): a exclusão está no dado (`relatorio_build.json → tabelas_excluidas`).
- **O Focus também não entra em `raw_series`** (**D-k**, 5 arquivos, mesmo motivo do painel: 197
  `series_id` compostos fora do catálogo) — são **7** tabelas excluídas hoje. F-015 o lê direto de
  `data/processed/focus/`, pelo mesmo `ProcessedSeriesSchema`, e a **procedência aponta para o
  EntitySet** (`FOCUS_ANUAIS`), nunca para `FOCUS_A_SELIC_H0`. Ver `modules/focus.md`.
- **`macro_quarterly` tem grade de apoio `2001Q1..2005Q4`** para as derivadas que precisam de `T−4`
  — reexpressa a régua de F-014 com as peças públicas dela e é conferida célula a célula
  (**913 células, 0 divergências**); uma única divergência **para o build** (`ApoioDivergente`).
- **`INCLINACAO_REAL_5A_3A` não tem coluna** em `MacroQuarterlySchema` (**D-n**): F-019/F-021 leem a
  série alinhada direto. A 5a−1a é publicada com **33 nulos (39,8%)** e declarados.

**Features:** **F-013** · **F-014** (D-h) · **F-015** · **F-016** · **F-017** · **F-018** ·
**F-029** — **todas classe C**.
