# Overview — estrategia-macro-ldc-dados

> **O que este projeto entrega hoje em 1 página.** Leitura em 60s.
>
> **Fonte de verdade do escopo:** [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
> (imutável). **Fonte de verdade do produto:** [`docs/product/PRD.md`](../product/PRD.md) (v1.0, 2026-10-10).
> Esta página **resume** o PRD — não o duplica. Em conflito, vale o PRD; em conflito de escopo, vale o e-mail.

**Última revisão:** 2026-10-11 (§8 atualizada para a **Onda 3, parte 1** — F-018/F-019/F-021 implementadas, QA pendente)
**Versão refletida:** PRD v1.0 + SPEC v1.0 (gerados em modo autônomo; **aprovação do Edu pendente**)

---

## 1. Em 1 frase

> Ferramenta interna de dados/quant da LDC Capital que monta a base estatística trimestral de 20 anos
> (macro brasileiro + desempenho de ativos e subsetores) e classifica regimes macro, para fundamentar o
> modelo de alocação macro doméstica e o tamanho da alocação internacional do Comitê de Alocação.

## 2. Problema e objetivo (do PRD §1)

O Comitê decide alocação com leitura qualitativa. Não existe base que responda **"em trimestres parecidos com
o atual, como cada classe de ativo e cada setor performou?"**. Os dados existem em 8+ fontes incompatíveis, e
rotas óbvias estão mortas (swap DI×pré do SGS parou em set/2019; ETTJ histórica da ANBIMA é paga).

**Objetivo da v1:** até **2026-10-13**, dataset canônico trimestral regenerável com um comando, cobrindo
**≥ 90% das séries pedidas** em 2006→2026, com **3 valores por série conferidos na fonte**, mais o heatmap
regime × ativo e a tabela "regime atual → ranking".

**O produto é descritivo, não preditivo.** Confundir os dois é o maior risco reputacional.

## 3. Para quem

- **Alexandre Kaercher** (gestor, cliente interno) — consome dataset + heatmap para modelar; não roda o pipeline.
- **Eduardo (Edu)** — dono do projeto, orquestra os agentes, roda o pipeline local, aprova classe D.
- **Comitê de Alocação** — consome só o material sintetizado.
- **Anti-persona:** cliente final, trader intradiário, compliance, e quem quer "o número previsto".

## 4. Escopo da v1 (PRD §4)

Blocos **A** (macro), **B** (ativos/subsetores) e **C** (internacional) do e-mail, janela **1T2006 → 3T2026**
(≈ 83 trimestres), análise trimestral com armazenamento na granularidade nativa. Regimes por **V1**
(quadrantes crescimento × inflação, lente principal), **V3** (vizinhos mais próximos — responde literalmente
ao e-mail) e **V2** (ciclo Selic, corte secundário). = "pacote mínimo" da §7 da metodologia.

**O escopo implícito virou explícito:** "tamanho da alocação internacional" (item **C1**) é entregue como
internacional em BRL dentro do mesmo arcabouço de regimes, respondido por **faixa estrutural + banda tática
por regime** — não por número pontual.

**Fora de escopo:** backtest de estratégia, previsão, interface web/API/deploy, dados pagos (ANBIMA Feed,
Bloomberg), IFIX sintético pré-2011, FII segmentado pré-2016.

**Fase 2:** V1b vs. Focus, V2 completa, setoriais completos, EMBI/CDS, variância mínima por regime,
dupla materialização `asof`×`revised`, clustering, HMM mensal, dashboard.

## 5. O que o PRD exige (resumo, sem duplicar)

**52 requisitos funcionais** em 6 grupos — extração por fonte (RF-001..019), camada canônica (020..026),
regimes (027..031), análise e visualização (032..040), entrega ao Comitê (041..045), reprodutibilidade
(046..052). Cada RF cita o item do e-mail (A1–A7, B1–B5, C1) e a fonte primária + fallback.
**10 RNFs:** reprodutibilidade por um comando, rastreabilidade (origem + vintage), sem dado inventado,
local em Windows/Python 3.11+, sem rede no CI, sem credencial/fonte paga no caminho crítico.

**Fontes escolhidas (as decisivas):** IMA via **bucket S3 público da ANBIMA**; índices B3 via **API
`indexStatisticsProxy`**; curva/inclinação via **Tesouro Direto interpolado** (porque o SGS de swaps morreu e
a ETTJ ANBIMA só tem ~20 d.u.); macro via **SGS + SIDRA**; Focus via **Olinda OData**; internacional via
**Yahoo `^GSPC` + MSCI `892400` NETR + PTAX**; FII segmentado via **Teva** (2019+, best-effort).

## 6. Restrições conhecidas (base da Anti-SPEC)

- **Não inventar dado.** Lacuna sem substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`.
- **Não é SaaS/web.** Sem auth, pagamento, deploy ou frontend. Roda local.
- **`data/` não é versionado** e não é fonte de verdade — o script que produz o dado é.
- **Camada canônica é classe C**; publicar para o Comitê é **classe D**.
- Excesso sobre CDI e retorno real **sempre por razão** `(1+r)/(1+b)−1`; trimestre = último dia útil.
- Fontes revisam números retroativamente (PIB do IBGE) → pipeline idempotente, com `vintage`.
- Séries que não cobrem 20 anos têm a janela real **declarada**: ICON (2007+), IMOB (2008+), IFIX (2011+),
  FII segmentado (2019+), ponta longa nominal da curva (~2010+).

## 7. Riscos dominantes (PRD §12 — 8 priorizados)

Look-ahead bias (revisão e defasagem do PIB/IBC-Br) · n pequeno (~20 por regime; diferenças < 5 pp são
ruído) · quebra estrutural 2006-2008 vs pós-2016 · **falha silenciosa de extração** (erro com HTTP 200,
truncamento sem aviso, filtros ignorados) · janela rolante e descontinuações · endpoints não documentados e
anti-bot (FRED pode estar bloqueado) · unidade/escala/formato mentirosos · overfitting e confusão
descritivo × preditivo.

## 8. Estado atual (2026-10-11, Onda 3 parte 1 implementada — QA pendente)

- **Fase:** **Ondas 0, 1 e 2 completas e aprovadas; Onda 3 parte 1 implementada, aguardando QA** —
  escopo → pesquisa → PRD v1.0 → SPEC v1.0 + Anti-SPEC → contratos → TODO (40 features) → PLAN
  (ondas) → Onda 0 (F-001, F-009) → Onda 1 (F-002..F-008) → **Onda 2 (F-013..F-017 + F-010)**,
  **todas com QA independente aprovado** (`docs/plans/qa/`, **0 × P0**, com a revisão numérica da
  classe C reconstruindo as camadas por fora e achando **igualdade exata em float64**) → **Onda 3
  parte 1: F-018 (`asof`), F-019 (V1) e F-021 (V3) implementadas** e aguardando QA/revisão numérica.
  **Aprovação do Edu ainda pendente** no PRD e na SPEC.
- **Pipeline implementado:** **9** extratores em `apps/pipeline/extract/` (o 9º é o Focus/Olinda) +
  job diário em `jobs/` + infra em `common/` + `transform/cambio.py` + **`apps/pipeline/canonical/`**
  (`build_raw_series.py`, `alinhamento.py`, `curva.py`, `macro_quarterly.py`, `retornos.py`,
  **`asof.py`**, **`regimes_v1.py`**, **`regimes_v3.py`**); `apps/analysis/` segue vazio. Contratos
  em `packages/shared/schemas/` (8 módulos pandera/pydantic + **138** séries), com
  `RegimesV1Schema` e `RegimeNeighborsV3Schema` **acrescentados** (nunca alterados) em `regimes.py`.
- **Dataset canônico: completo, com as duas materializações e as duas lentes de regime.**
  `data/canonical/` tem **20** artefatos: `raw_series.parquet` (**278.439** linhas, **62** séries,
  1979-12-31 → 2026-10-10), `series_catalog.parquet` materializado (**138 × 26**),
  `alinhado_trimestral.parquet` (**4.038**), **`macro_quarterly.parquet` (83 × 42, `revised`)** +
  procedência (**2.548**), **`macro_quarterly_asof.parquet` (83 × 42, `asof` — a materialização de
  decisão)** + procedência (**2.552**, com `date_obs`/`lag_dias` em todas e **0** células com
  look-ahead), **`asset_returns_quarterly.parquet` (1.963, 24 ativos)**,
  **`regimes_v1{,_asof}.parquet` (83 × 18)**, **`regime_neighbors_v3.parquet` (9.692 × 21)** e
  `regime_neighbors.parquet` (5.500 × 11), mais 8 relatórios e o `ldc.duckdb` derivado.
  `data/processed/` tem **69 Parquets**, todos reconstruíveis sem rede com `--offline` e
  byte-idênticos entre rodadas. **Falta a junção das lentes (F-022) e a V2 (F-020).**
- **Pesquisa:** concluída — fontes (`fontes-de-dados.md`) e metodologia (`metodologia-regimes-macro.md`).
- **Decisões de fonte e convenção:** 12 substituições + as **8 convenções da Onda 1** (D-a..D-h:
  `date` em fim de período, `vintage` do manifesto, catálogo 134, calendário por HTML, grade bancária
  única) + as **7 + 2 da Onda 2**: **D-i** (vértice de 3 anos, catálogo **138**), **D-j** (prazo em
  dias corridos), **D-k** (Focus fora de `raw_series`), **D-l** (`USDBRL` no universo de retornos),
  **D-m** (CA-007 não satisfazível — 16 nulos em `ibcbr_gap`), **D-n** (inclinação 5a−3a sem coluna),
  **D-o** (unidade: por cento × fração), **D-p** (`FOCUS_PIB_TOTAL` descartada) e **D-q** (achados do
  Focus: G-04, G-05, exceção a D-a, `%20` × `+`) + as **7 da Onda 3 parte 1**: **D-r**
  (`RegimesV1Schema`, junção em F-022), **D-s** (IBC-Br pela **média do trimestre** — superou
  D-q(e); 7 trimestres trocam de quadrante), **D-t** (ciclo Selic: `|Δ| >= 0,25 pp` é movimento),
  **D-u** (eixo da V3 = `focus_pib_ano`; F-022/F-024 leem `regime_neighbors_v3`), **D-v** (as 3
  correções dos P1 do QA), **D-w** (`CONTRACTS.md` com o estado medido) e **D-x** (paths em
  `canonical/`). Todas **provisórias** em
  [`docs/plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md); **ADR-001..006 em Proposta**.
- **Ambiente:** `uv sync --extra dev` entrega o ambiente completo (deps corrigidas em 2026-10-10).
  **FRED bloqueado nesta máquina** → bloco internacional pelo plano B (Yahoo + MSCI + PTAX).
- **CI:** N1 configurado; N2/N3 comentados aguardando testes reais.
- **Bloqueios:** **8 decisões** travam a publicação — ver `TODO.md §4`, PRD §13.2 e SPEC §11
  (**D1** lente oficial, **D3** eixo inflação, **D5** métrica do heatmap, **D6** forma do internacional,
  **D12** setoriais/FII no pacote mínimo, **L1** IFIX 2011+, **L2** FII segmentado via terceiro, **L4**
  contratar ANBIMA Feed ou não). **Extração e camada canônica não estão bloqueadas.**
- **Próximo passo: F-022** (métricas por regime × ativo + a junção das lentes em `RegimesSchema`,
  que **D-r** delegou) **e a Onda 4** (F-020 V2, F-023 heatmap, F-024 ranking, F-025 timeline,
  F-028 limitações). Os insumos de F-022 estão em disco: `regime_neighbors_v3.parquet` (lente
  principal — **D-u**), `regimes_v1.parquet` e `asset_returns_quarterly.parquet`. Em paralelo:
  **QA/revisão numérica de F-018/F-019/F-021**, responder as 8 decisões e ratificar D-h..D-x (as que
  precisam do Edu estão tabuladas em `TODO.md §4`).
- ⚠️ **O achado que muda a conversa com o Comitê, e que não é bug de ninguém:** rodando a V1 nas
  duas materializações, **22 de 66 trimestres (33,33%) trocam de rótulo** entre `revised` e `asof` —
  acima dos **25%** que `metodologia §5.1` e **CA-074** fixam como limite. Pelo critério escrito, a
  leitura **operacional** da V1 ("em que quadrante estamos agora, com o que se sabia na época")
  **não é operacional nesta forma**, e com ela cai a hipótese **H-03** do PRD. A leitura
  **descritiva** (RF-027) continua válida e é o entregável. Vai à **página de limitações (F-028)** e
  ao slide — junto do lembrete de que a V1 classifica **67** dos 83 trimestres, não 83 (**D-m**: a
  crise de 2008 inteira fica fora do eixo de crescimento).

## 9. Próximo grande objetivo

Dataset canônico trimestral de 20 anos com blocos A/B/C conferidos contra as fontes originais, + heatmap
regime × ativo, **antes do Comitê de Alocação de 2026-10-14** (heatmap para revisão do Edu em 2026-10-13).

---

## Links

- Escopo de origem (imutável) → [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
- **PRD v1.0** → [`docs/product/PRD.md`](../product/PRD.md)
- Pesquisas → [`docs/research/fontes-de-dados.md`](../research/fontes-de-dados.md) ·
  [`docs/research/metodologia-regimes-macro.md`](../research/metodologia-regimes-macro.md)
- **SPEC v1.0 + Anti-SPEC §10** → [`docs/specs/SPEC.md`](../specs/SPEC.md) ·
  contratos → [`docs/contracts/CONTRACTS.md`](../contracts/CONTRACTS.md)
- Plano de ondas → [`docs/plans/PLAN.md`](../plans/PLAN.md) ·
  ADRs → [`docs/decisions/adr/`](../decisions/adr/) ·
  trocas de fonte → [`docs/plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md)
- Arquitetura → [`wiki/architecture.md`](./architecture.md) · Histórico → [`wiki/log.md`](./log.md) ·
  módulos → [`wiki/modules/`](./modules/) · runbooks → [`wiki/runbooks/`](./runbooks/)
- Estado vivo → [`TODO.md`](../../TODO.md) · Contrato com agentes → [`AGENTS.md`](../../AGENTS.md)

---

*Atualize esta página quando: o PRD mudar de versão, uma decisão bloqueante for respondida, a fase mudar, ou
o dataset canônico passar a existir. Não atualize por feature pequena.*
