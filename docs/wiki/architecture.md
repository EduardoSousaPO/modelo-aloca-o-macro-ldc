# Architecture — estrategia-macro-ldc-dados

> **Arquitetura técnica viva.** Síntese do SPEC + realidade do código.
>
> **Fonte de verdade:** `docs/specs/SPEC.md` + `packages/shared/schemas/`.
> Esta página existe para que qualquer agente entenda a topologia em < 5 min sem ler todo o SPEC.

**Última revisão:** 2026-10-11 (**fechamento da Onda 4**: F-022..F-026, F-028 e F-029 entregues; a camada `apps/analysis/` existe)
**Versão do SPEC refletida:** **v1.0** (52 RFs → 128 CAs + Anti-SPEC §10, sagrada)
**Status do código (2026-10-11, pós-Onda 4):** contratos escritos
(`packages/shared/schemas/`, **9** módulos + catálogo de **138** séries, com
`MacroQuarterlyAsofProvenanceSchema`, `RegimesV1Schema`, `RegimeNeighborsV3Schema` e o novo
`internacional.py` — **sempre por acréscimo**, nenhuma coluna existente alterada em nenhuma onda);
**camada de extração pronta e aprovada** — `apps/pipeline/common/` (infra), `extract/` (**9**
extratores), `jobs/` (job diário), `transform/cambio.py`; **camada canônica completa** —
`apps/pipeline/canonical/` com `build_raw_series.py` (F-013), `alinhamento.py` (F-014), `curva.py`
(F-016), `macro_quarterly.py` (F-015), `retornos.py` (F-017), `asof.py` (F-018), `regimes_v1.py`
(F-019), `regimes_v3.py` (F-021), **`metricas_regime.py` (F-022)** e **`internacional.py` (F-026)**;
o **orquestrador** em **`apps/pipeline/run.py`** + `__main__.py` (F-029); e a **camada de análise**,
que deixou de estar vazia — **`apps/analysis/`** com `_linguagem.py` (a guarda única de linguagem
descritiva), `figuras/_comum.py`, `figuras/heatmap_regime_ativo.py` (F-023),
`figuras/timeline_regimes.py` (F-025) e `tabelas/ranking_regime_atual.py` (F-024).
**Nota de caminho (D-x, estendida na Onda 4):** `apps/pipeline/analysis/` **não existe** — as
features de cálculo moram em `canonical/` e as de apresentação em `apps/analysis/`; são **7**
divergências de path, todas de path e não de escopo, listadas no `TODO.md §4` para ratificação.

`data/processed/` tem **69** Parquets e `data/canonical/`, **48** artefatos conferidos pelo
`MANIFEST.json` (**47** determinísticos + o `ldc.duckdb`, fora do agregado por decisão declarada).
**Um comando reconstrói tudo:** `python -m apps.pipeline run --offline` → **13 etapas** na ordem
`curva → build_raw_series → alinhamento → macro_quarterly → asof → retornos → regimes_v1 →
regimes_v1_asof → regimes_v3 → metricas_regime → internacional → figuras → tabelas`, sem rede;
`python -m apps.pipeline verify` → `rc != 0` se um byte divergir; `freeze --tag` congela.
**Rebuild final: 2 execuções byte-idênticas, `verify` rc 0,
`DATASET_SHA256 = fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`.**

Ondas 0 a **3 fechadas e aprovadas** (`docs/plans/qa/ONDA-0-QA.md`, `ONDA-1-QA-{A,B}.md`, `ONDA-2-QA-{A,B}.md`, `ONDA-3-QA.md`, **0 × P0** e **0 divergência numérica**); **Onda 4 implementada, com o QA (`ONDA-4-QA.md`) rodado e as mudanças aplicadas** — F-022..F-026, F-028 e F-029; **F-020 (V2) e F-030 cortadas da v1**. As convenções (`date` em fim de período, `vintage` do manifesto, grade bancária única de D-h, vértice de 3 anos de D-i, prazo em dias corridos de D-j, Focus fora de `raw_series` de D-k, `USDBRL` no universo de D-l, unidade por cento × fração de D-o, **IBC-Br pela média do trimestre de D-s**, **ciclo Selic com desigualdade não estrita de D-t**, **eixo da V3 em `focus_pib_ano` de D-u**) estão em `docs/plans/DECISIONS_LOG.md §2.1/§2.3`, ainda **provisórias**. ⚠️ **Gate de publicação fechado:** ADR-001 em `Proposta` ⇒ `especificacao_congelada = False` nas 83 linhas de F-019/F-021 ⇒ nenhum número de regime é publicável (CA-090).

---

## 1. Topologia

```
  FONTES (12, todas gratuitas)        EXTRAÇÃO (B)        NORMALIZAÇÃO        CANÔNICO (C)        ANÁLISE
  ────────────────────────────        ────────────        ────────────        ────────────        ───────
  BCB SGS      433·13522·11·1178·432
               ·12·4389·24364·1·10813 ─┐
  BCB Olinda   Focus (5 EntitySets)   ─┤
  IBGE SIDRA   t/1737 · t/1621        ─┤  apps/pipeline/   apps/pipeline/     data/canonical/    apps/analysis/
  Tesouro CKAN precotaxatesouro.csv   ─┼─► extract    ──►  transform    ──►   raw_series         notebook
  ANBIMA S3    IMAB·IRFM·IMAS (8)     ─┤  data/raw/<f>/    data/processed/    macro_quarterly     heatmap
  ANBIMA web   Msec·CZ (job diário)   ─┤  (cru, imutável)  (freq. nativa)     asset_returns_q.    timeline
  B3 API       IBOV·IDIV·SMLL·…·IFIX  ─┤                                      regimes             ranking
  Teva GCS     FII por segmento       ─┤        │                 │           regime_neighbors        │
  Yahoo        ^GSPC·^VIX·^TNX        ─┤        │                 │           series_catalog          │
  MSCI         892400 NETR            ─┤        └─ pandera ───────┴─ pandera ──────┘                  ▼
  FRED         DGS10·VIXCLS·DFF       ─┤           (packages/shared/schemas/)              Comitê (classe D)
  Ipeadata     GM366_IBVSP366 · …     ─┘
```

Fluxo **unidirecional**. Cada seta é um comando reprodutível: rodar duas vezes a partir do mesmo `raw/`
produz o mesmo **hash** (RF-048). Nada volta para a esquerda. Persistência: **Parquet por camada**,
**DuckDB derivado** e descartável (ADR-006).

## 2. Stack

| Camada | Tech | Notas |
|---|---|---|
| Linguagem | Python ≥ 3.11 | `uv` ou venv local; nunca global |
| Dados | pandas ≥ 2.2 + pyarrow | datas ISO-8601, `DatetimeIndex` tz-naive, trimestre = **último dia útil** |
| HTTP | requests / httpx | **UA de browser sempre**, retry com backoff, cache por `ETag` |
| Contratos | pydantic ≥ 2.7 (catálogo/config) + pandera ≥ 0.20 (DataFrame) | fonte de verdade em `packages/shared/schemas/` |
| Armazenamento | Parquet (fonte) + DuckDB (consulta) | ADR-006; `data/` **não versionado** e reconstruível |
| Análise | Jupyter | notebook **sem lógica de negócio** — importa de `apps/pipeline/` |
| Qualidade | pytest + ruff (line-length 100) | N1 lint+unit · N2 +integration/contract+build canônico · N3 +e2e+hash |
| Execução | local (Windows, máquina do Edu) | **sem** servidor, deploy, auth, cloud |

## 3. Módulos (previstos; `common/`, `extract/`, `jobs/` e `canonical/` implementados)

| Módulo | Responsabilidade | Classe | Features |
|---|---|---|---|
| `extract/http`, `parsing` | UA, retry, shape, número pt-BR, magic bytes, encoding | B | F-001 |
| `extract/bcb_sgs` · `extract/bcb_focus` | SGS (IPCA, Selic, CDI, IBC-Br, PTAX) + Focus/Olinda (5 EntitySets, 197 séries) | B | F-003, **F-010** |
| `extract/ibge_sidra` | IPCA nº-índice, PIB trimestral | B | F-004 |
| `extract/anbima_s3`, `anbima_diario` | índices IMA; arquivamento de janela rolante | B | F-002, F-009 |
| `extract/tesouro_direto` | taxas e PUs de títulos públicos | B | F-005 |
| `extract/b3_indices` | índices amplos, setoriais e IFIX | B | F-006 |
| `extract/yahoo`, `msci`, `fred` | bloco internacional | B | F-007, F-011 |
| `extract/teva` | FII por segmento (2019+) | B | F-012 |
| `extract/calendario_anbima` · `canonical/alinhamento` | dias úteis, fim de trimestre, ffill ≤ 5 d.u. | **C** | F-008, F-014 |
| `canonical/curva` | vértices interpolados + inclinação | **C** | F-016 |
| `canonical/retornos` | `ret_tri`, excesso CDI, real (sempre razão) — **em fração** (D-o) | **C** | **F-017** |
| `canonical/macro_quarterly` · `asof` | 83 trimestres + procedência por célula — **em por cento/pp** (D-o); `asof` é F-018 | **C** | **F-015**, F-018 |
| `canonical/build_raw_series` | camada canônica + catálogo materializado + DuckDB | **C** | F-013 |
| `canonical/regimes_v1`, `regimes_v3` | V1 quadrantes, V3 vizinhos (**V2 cortada da v1**) | **C** | F-019, F-021 |
| `canonical/metricas_regime` | métricas por regime × ativo — **3** tabelas nomeadas | **C** | **F-022** |
| `canonical/internacional` | `stress_flag`, correlações por regime, faixa de D6 | **C** | **F-026** |
| `analysis/figuras/{_comum,heatmap_regime_ativo,timeline_regimes}` | heatmap e timeline, determinísticos | B | **F-023**, **F-025** |
| `analysis/tabelas/ranking_regime_atual` | "em que regime estamos?" × 3 + concordância | B | **F-024** |
| `analysis/_linguagem` | a guarda **única** de linguagem descritiva (§10.2.10) | B | F-023/024/025 |
| `pipeline/run` (CLI `run`/`verify`/`freeze`) | um comando + `MANIFEST.json` + `FROZEN.txt` | **C** | **F-029** |
| `deliver/pacote` | pacote do Comitê — lê `publicavel` do manifesto (**D-af**) | **D** | F-031 |

`canonical/` e `transform/` são o coração do risco: **classe C** (`AGENTS.md §2`). `apps/analysis/`
é **classe B** — lê o canônico e **não recalcula nada** (as flags de `n` são reconferidas e a
divergência é erro); se um número está errado na figura, o bug é da feature dona.
Nota de caminho (**D-x**): as features de cálculo moram em **`apps/pipeline/canonical/`** e as de
apresentação em **`apps/analysis/`**, não em `load/`/`transform/`/`analysis/` como o `TODO.md`
previa — são 7 divergências de path, registradas no Feature Contract de cada uma e tabuladas no
`TODO.md §4`, sem efeito em CA nenhum.

## 4. Fronteiras de validação (onde o pandera **tem** que estar)

| Fronteira | Schema |
|---|---|
| saída de cada extrator → `data/processed/` | `ProcessedSeriesSchema` |
| `data/processed/` → `data/canonical/` | `RawSeriesSchema` + schema da tabela destino |
| catálogo materializado · grade trimestral | `SeriesCatalogMaterializedSchema` · `AlinhadoTrimestralSchema` |
| entrada/saída de `data/canonical/` | `MacroQuarterlySchema`, `AssetReturnsQuarterlySchema`, `RegimeAssetMetricsSchema`, `RegimesSchema`, `RegimeNeighborsSchema`, `SeriesCatalogSchema` |
| config de extrator / janela | `ExtractorConfig` (pydantic) |
| catálogo de séries | `SeriesCatalogEntry` (pydantic) + `series_catalog_data.py` (**138** séries) |

**Regra:** para documentar um contrato em `docs/contracts/CONTRACTS.md`, **primeiro** crie o schema em
`packages/shared/schemas/`. O CONTRACTS.md é espelho legível, não fonte.

Invariantes que os schemas impõem (e que nenhum código contorna): 83 trimestres exatos ·
≥ 18 ativos · nenhuma linha antes do início real da série · `n_obs` nunca nulo ·
`ffill ≤ 5 d.u.` · `strict=True` (sem coluna ad hoc) · `date ≤ collected_at` ·
`a_confirmar` ⇒ `status = a_confirmar`.

## 5. Decisões arquiteturais (ADRs)

| ADR | Decisão | Status |
|---|---|---|
| ADR-001 | lente de regime oficial (V1 + V3 + V2 secundária) e eixos da V1 (aceleração) — D1+D3 | **Proposta** |
| ADR-002 | métrica primária do heatmap = **excesso sobre CDI** — D5 | **Proposta** |
| ADR-003 | internacional = piso 16-20% + banda tática 15-35% por regime — D6 | **Proposta** |
| ADR-004 | inclinação da curva via **Tesouro Direto** (não ETTJ ANBIMA paga) — L4 | **Proposta** |
| ADR-005 | janelas próprias por ativo + FII segmentado via Teva — L1+L2+D12 | **Proposta** |
| ADR-006 | **Parquet por camada + DuckDB para consulta** e convenção de retornos/alinhamento | **Proposta** |

ADR-006 substitui os três ADRs "pendentes" do kickoff (armazenamento, cliente HTTP, convenção de período).
**Duas correções editoriais pendentes para quando ADR-004 e ADR-006 forem aceitos** (nenhuma muda a
decisão): ADR-006 §(a).2 escreve `macro.duckdb` e o implementado é **`ldc.duckdb`** (decisão: mantém
`ldc.duckdb`); e ADR-004 §3 nomeia a inclinação real **5a−1a** como variável principal, papel que
**D-i** passou à **5a−3a** (`DECISIONS_LOG §2.3`).
**ADR-001 é gate de publicação:** enquanto estiver em Proposta, `regimes.especificacao_congelada = False`
e nenhum número vai ao Comitê (RF-031 / CA-090).
Trocas de fonte e convenções operacionais vão para `docs/plans/DECISIONS_LOG.md`, não para ADR.

## 6. Restrições arquiteturais ativas (resumo da Anti-SPEC — `SPEC.md §10`)

- **NÃO inventar, interpolar ou estimar dado.** Lacuna sem substituto → `BLOQUEADO — FONTE INDISPONÍVEL`.
- **NÃO** tratar fonte de janela rolante como backfill; **NÃO** usar série descontinuada como se viva.
- **NÃO** classificar T com dado divulgado após o fim de T **sem a flag `asof`**.
- **NÃO** calcular excesso sobre CDI / retorno real por subtração — sempre razão.
- **NÃO** comparar total return com price return sem `is_total_return`.
- **NÃO** publicar célula com `n < 5` como conclusão; `n` em **toda** célula.
- **NÃO** ajustar a especificação de regime depois de ver os retornos (só V1.1, reportando as duas).
- **NÃO** usar fonte paga/credencial no caminho crítico; **NÃO** fazer backtest na entrega de 14/10.
- **NÃO** alterar schema canônico, alinhamento ou retorno fora de feature **classe C**.
- **NÃO** enviar número ao Comitê fora do fluxo **classe D**; **NÃO** substituir fonte em silêncio.
- **NÃO** commitar dado/credencial, editar `data/` à mão, chamar rede em teste de CI ou confiar no
  encoding default do locale.

## 7. O que NÃO faz parte da arquitetura

Sem frontend, API própria, login, multi-tenant · sem banco servidor, Supabase, RLS ou migration ·
sem deploy, Vercel, Docker em produção, staging · sem pagamento ou e-mail transacional ·
sem fila, cron ou orquestrador (Airflow/Dagster) — o pipeline roda **por comando manual** ·
sem cache distribuído (cache = arquivo local em `data/raw/`) · sem TypeScript, Node, Zod, ESLint.

---

## Links

- SPEC + Anti-SPEC → [`docs/specs/SPEC.md`](../specs/SPEC.md)
- Contratos (espelho) → [`docs/contracts/CONTRACTS.md`](../contracts/CONTRACTS.md) ·
  fonte → [`packages/shared/schemas/`](../../packages/shared/schemas/)
- Plano de ondas → [`docs/plans/PLAN.md`](../plans/PLAN.md) ·
  risco A/B/C/D → [`docs/plans/risk-classification.md`](../plans/risk-classification.md)
- Escopo de origem → [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
- Pesquisa de fontes → [`docs/research/`](../research/) · ADRs → [`docs/decisions/adr/`](../decisions/adr/)

---

*Atualize: ao adicionar/remover módulo, ao trocar lib core, ao aprovar ADR, ao mudar o schema canônico.
Não atualize por refactor interno de módulo.*
