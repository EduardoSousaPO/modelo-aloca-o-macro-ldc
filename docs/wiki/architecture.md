# Architecture — estrategia-macro-ldc-dados

> **Arquitetura técnica viva.** Síntese do SPEC + realidade do código.
>
> **Fonte de verdade:** `docs/specs/SPEC.md` + `packages/shared/schemas/`.
> Esta página existe para que qualquer agente entenda a topologia em < 5 min sem ler todo o SPEC.

**Última revisão:** 2026-10-11 (consolidação da Onda 1)
**Versão do SPEC refletida:** **v1.0** (52 RFs → 128 CAs + Anti-SPEC §10, sagrada)
**Status do código (2026-10-11):** contratos escritos (`packages/shared/schemas/`, **7** módulos + catálogo de **134** séries) e a **camada de extração pronta** — `apps/pipeline/common/` (infra), `extract/` (8 extratores), `jobs/` (job diário), `transform/cambio.py` (1ª peça da transformação); `data/processed/` tem 53 Parquets reconstruíveis com `--offline`. `data/canonical/` e `apps/analysis/` seguem vazios (classe C, de F-013 em diante).
Ondas 0 e 1 fechadas: F-001 e F-009 com **QA aprovado**, F-002..F-008 **aguardando QA** (`docs/plans/qa/ONDA-1-QA.md`). As convenções da camada processada (`date` em fim de período, `vintage` do manifesto) estão em `docs/plans/DECISIONS_LOG.md §2.1`, ainda **provisórias**.

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

## 3. Módulos (previstos; nenhum implementado)

| Módulo | Responsabilidade | Classe | Features |
|---|---|---|---|
| `extract/http`, `parsing` | UA, retry, shape, número pt-BR, magic bytes, encoding | B | F-001 |
| `extract/bcb_sgs`, `bcb_focus` | SGS (IPCA, Selic, CDI, IBC-Br, PTAX) + Focus | B | F-003, F-010 |
| `extract/ibge_sidra` | IPCA nº-índice, PIB trimestral | B | F-004 |
| `extract/anbima_s3`, `anbima_diario` | índices IMA; arquivamento de janela rolante | B | F-002, F-009 |
| `extract/tesouro_direto` | taxas e PUs de títulos públicos | B | F-005 |
| `extract/b3_indices` | índices amplos, setoriais e IFIX | B | F-006 |
| `extract/yahoo`, `msci`, `fred` | bloco internacional | B | F-007, F-011 |
| `extract/teva` | FII por segmento (2019+) | B | F-012 |
| `transform/calendario`, `alinhamento` | dias úteis, fim de trimestre, ffill ≤ 5 d.u. | **C** | F-008, F-014 |
| `transform/curva` | vértices interpolados + inclinação | **C** | F-016 |
| `transform/retornos` | `ret_tri`, excesso CDI, real (sempre razão) | **C** | F-017 |
| `transform/macro_quarterly`, `asof` | 83 trimestres + anti-look-ahead | **C** | F-015, F-018 |
| `load/raw_series`, `catalog` | camada canônica + catálogo materializado | **C** | F-013 |
| `analysis/regimes_v1|v2|v3` | V1 quadrantes, V2 ciclo Selic, V3 vizinhos | **C** | F-019..021 |
| `analysis/metricas_regime` | métricas por regime × ativo | **C** | F-022 |
| `analysis/figuras`, `tabelas`, `internacional` | heatmap, timeline, ranking, risk-off | B / **C** | F-023..026 |
| `pipeline` (CLI), `deliver/pacote` | um comando + pacote do Comitê | **C** / **D** | F-029, F-031 |

`transform/`, `load/` e `analysis/regimes*` são o coração do risco: **classe C** (`AGENTS.md §2`).

## 4. Fronteiras de validação (onde o pandera **tem** que estar)

| Fronteira | Schema |
|---|---|
| saída de cada extrator → `data/processed/` | `ProcessedSeriesSchema` |
| `data/processed/` → `data/canonical/` | `RawSeriesSchema` + schema da tabela destino |
| entrada/saída de `data/canonical/` | `MacroQuarterlySchema`, `AssetReturnsQuarterlySchema`, `RegimeAssetMetricsSchema`, `RegimesSchema`, `RegimeNeighborsSchema`, `SeriesCatalogSchema` |
| config de extrator / janela | `ExtractorConfig` (pydantic) |
| catálogo de séries | `SeriesCatalogEntry` (pydantic) + `series_catalog_data.py` (**134** séries) |

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
