# Overview — estrategia-macro-ldc-dados

> **O que este projeto entrega hoje em 1 página.** Leitura em 60s.
>
> **Fonte de verdade do escopo:** [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
> (imutável). **Fonte de verdade do produto:** [`docs/product/PRD.md`](../product/PRD.md) (v1.0, 2026-10-10).
> Esta página **resume** o PRD — não o duplica. Em conflito, vale o PRD; em conflito de escopo, vale o e-mail.

**Última revisão:** 2026-10-11 (§8 e §9 atualizadas para o **fechamento final** — F-027 e F-031 implementadas, pacote montado e selado, envio bloqueado por ADR-001)
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

## 8. Estado atual (2026-10-11, **FECHAMENTO FINAL** — pacote montado, envio bloqueado)

> ### ⛔ O pacote está pronto e NÃO SAI.
> `ADR-001` está em **`Proposta`** em disco ⇒ `especificacao_congelada = False` (CA-090) ⇒ **passo 2
> dos 8 do gate reprovado** (`AGENTS.md §14`) ⇒ **nada vai ao Comitê — nem um número por WhatsApp**
> (Anti-SPEC §10.3.18). **Nada está em implementação; os próximos 10 passos são humanos**, tabulados
> em [`TODO.md §4`](../../TODO.md) ("O que só o Edu pode fazer"), com o roteiro de 30 minutos em
> [`docs/product/GUIA-REVISAO-EDU.md`](../product/GUIA-REVISAO-EDU.md) e o gate executável em
> [`runbooks/entrega-comite.md`](./runbooks/entrega-comite.md).

- **Fase:** **o pacote mínimo está implementado de ponta a ponta** — escopo → pesquisa → PRD v1.0 →
  SPEC v1.0 + Anti-SPEC → contratos → TODO → PLAN → Onda 0 (F-001, F-009) → Onda 1 (F-002..F-008) →
  Onda 2 (F-013..F-017 + F-010) → Onda 3 (F-018 `asof`, F-019 V1, F-021 V3) → **Onda 4 (F-022
  métricas, F-023 heatmap, F-024 ranking, F-025 timeline, F-026 internacional, F-028 limitações,
  F-029 orquestrador)** → **F-027 (caderno de entrega)** → **F-031 (pacote ao Comitê, classe D)**.
  Ondas 0-4 com QA independente: **0 × P0** em todas, e **0 divergência numérica** nas reconstruções
  independentes de classe C (os P1 foram sempre de **declaração** ou de **orquestração**, nunca de
  número). **F-027 e F-031 aguardam QA independente** (Prompt 3, subagente distinto).
  **Aprovação do Edu ainda pendente** no PRD, na SPEC e nos ADRs.
- **A entrega, medida.** O **caderno** (F-027): 34 células em 11 seções, **zero cálculo** — teste de
  AST reprova `def`, operador aritmético e 29 métodos de agregação do pandas; executado em cópia com
  **19/19** células com saída e 0 erros; **3 gerações → mesmo `sha256`**. O **pacote** (F-031): **41
  arquivos + `HASHES.txt`**, 10,9 MB soltos / **3,7 MB** no `.zip` com `sha256` **idêntico em 3
  montagens** (CA-121), 10 tabelas em Parquet (cópia byte a byte) e CSV pt-BR, 5 figuras em PNG e
  SVG, XLSX de **8 abas** sem uma única fórmula, e smoke de **93 checagens — 86 `OK`, 0 `FALHA`, 7
  `INFO`, `rc 0`**. O selo de "não publicável" é **lido do ADR em disco** com falha fechada: aceitar
  o ADR-001 derruba o selo de todo artefato com **zero linha de código**.
  `internacional_pesos.parquet` fica **fora** do pacote por leitura do campo `publicavel` do
  manifesto (**D-af**), não por convenção de nome.
- **Pipeline implementado:** **9** extratores em `apps/pipeline/extract/` + job diário + infra em
  `common/` + `transform/cambio.py` + **`apps/pipeline/canonical/`** (`build_raw_series`,
  `alinhamento`, `curva`, `macro_quarterly`, `retornos`, `asof`, `regimes_v1`, `regimes_v3`,
  **`metricas_regime`**, **`internacional`**) + **`apps/pipeline/run.py`** (o orquestrador) +
  **`apps/analysis/`** (`_linguagem.py`, `figuras/{_comum,heatmap_regime_ativo,timeline_regimes}.py`,
  `tabelas/ranking_regime_atual.py`). Contratos em `packages/shared/schemas/` (**9** módulos
  pandera/pydantic + **138** séries), com `internacional.py` **novo** e tudo o mais só por
  **acréscimo** — nenhuma declaração de coluna existente foi alterada em nenhuma onda.
- **UM comando reconstrói a camada inteira** (F-029): `python -m apps.pipeline run --offline`, **13
  etapas** na ordem, sem rede; `verify` recalcula todo `sha256` contra o `MANIFEST.json` e sai com
  erro se um byte divergir; `freeze --tag` congela com `FROZEN.txt` + rollback. **Rebuild final de
  2026-10-11: 2 execuções byte-idênticas, 47 artefatos determinísticos, `verify` rc 0,
  `DATASET_SHA256 = fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`.**
- **Dataset canônico: completo.** `data/canonical/` tem, além de `raw_series.parquet` (**278.439**
  linhas, **62** séries), `series_catalog` (**138 × 26**), `alinhado_trimestral` (**4.038**),
  `macro_quarterly` nas **duas** materializações (**83 × 42** cada) + as 2 procedências (**2.548** e
  **2.552**, esta com **0** células com look-ahead), `asset_returns_quarterly` (**1.963**, 24
  ativos), `regimes_v1{,_asof}` (**83 × 18**), `regime_neighbors_v3` (**9.692 × 21**) e
  `regime_neighbors` (**5.500 × 11**): as **3** tabelas `regime_asset_metrics*`
  (**120 / 96 / 120** células), `internacional_por_regime` (**54**) e `internacional_pesos`
  (**624**, ⚠️ marcado **`publicavel: false`**), **12 figuras** (PNG + SVG das 3 vistas do heatmap e
  das 2 materializações da timeline) com os 2 Parquet de dados plotados (**322** e **166**), as **6**
  tabelas do Comitê (`ranking_regime_atual` e `concordancia_lentes` em parquet/csv/md), **10**
  relatórios e o `ldc.duckdb` derivado (fora do agregado, declarado).
  **`regimes.parquet` NÃO é gravado** (**D-r**/**D-ab**): F-026 resolveu `stress_flag` e sobrou um
  bloqueio — `regime_v1` é `nullable=False` contra 16 trimestres `INDETERMINADO` (**D-m**), e
  alterar schema existente é pausa.
- **Pesquisa:** concluída — fontes (`fontes-de-dados.md`) e metodologia (`metodologia-regimes-macro.md`).
- **Decisões de fonte e convenção: D-a..D-ag**, todas em
  [`docs/plans/DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md) e **provisórias onde mudam número**.
  As da Onda 4: **D-y** (os 5 P1 do QA da Onda 3 — contrato espelho, a correção de fato de **D-t**,
  a distribuição do Jaccard, N2/N3 no CI, a safra `revised` da V3), **D-z** (renomeação da vista,
  `SP500_USD` fora do heatmap, cromo e guarda de linguagem unificados), **D-aa** (CA-098 "V1 e V2" →
  V1 `revised` + V1 `asof` + V3), **D-ab** (D6-a..d de F-026), **D-ac** (guarda de não-nulidade nas
  flags `bool` — o pandera **não** recusava `None` sob `coerce`), **D-ad** (as 7 de F-029),
  **D-ae** (dívidas de contrato numa lista única), **D-af** (`publicavel` no manifesto) e, no
  fechamento final, **D-ag** — o **pacote de entrega não é artefato do manifesto**
  (`inventariar()` ignora o prefixo `entrega/pacote_comite_`: é cópia de artefato já manifestado,
  montada depois do `freeze` e reconstruível por um comando, CA-114) **e o `DATASET_SHA256` que
  vale é o de `MANIFEST.json`/`HASHES.txt`** — o que o HTML do caderno imprime é, por construção, o
  da rodada anterior à inclusão do próprio HTML, porque um hash não contém a si mesmo.
  **ADR-001..006 em Proposta.**
- **Ambiente:** `uv sync --extra dev`. **FRED bloqueado nesta máquina** → bloco internacional pelo
  plano B (Yahoo + MSCI + PTAX).
- **CI:** **N1, N2 e N3 habilitados** (`.github/workflows/ci.yml`) — N2 = `tests/contract` + build do
  canônico a partir das fixtures + `verify`; N3 = `tests/e2e` + **duas árvores independentes** com
  `diff` do `MANIFEST.json`. O passo de `tests/integration` fica comentado e nomeado: a pasta está
  **vazia** e `pytest` nela sairia com código 5.
- **Bloqueios:** **8 decisões** travam a publicação — `TODO.md §4`, PRD §13.2, SPEC §11 (**D1**
  lente oficial, **D3** eixo inflação, **D5** métrica do heatmap, **D6** forma do internacional,
  **D12** setoriais/FII, **L1** IFIX 2011+, **L2** FII segmentado, **L4** ANBIMA Feed).
  **Desenvolvimento não está bloqueado; publicação está** (CA-090).
- **Próximo passo: humano, não código.** Os 10 itens de `TODO.md §4` — aceitar os ADRs (o **001** é
  o gate duro), responder as 12 decisões da §7 de `LIMITACOES-COMITE.md`, rodar o **checklist de 19
  caixas** do runbook, conferir os **3 canários na fonte viva**, abrir o XLSX no Excel de verdade,
  `freeze --tag` + `git tag -a`, pedir o QA independente e **só então** enviar com a linha
  `[RELEASE]` no log. **F-020** (V2) e **F-030** foram **cortadas da v1** e estão no **backlog
  pós-Comitê** junto com F-033..F-040, 1 linha cada em `TODO.md §2`. Entram no aceite do ADR-001: as
  **7 + 11 linhas de path** e as **emendas de CA** (CA-078, CA-079, CA-098).

## 9. Próximo grande objetivo

**Antes do Comitê (2026-10-14):** o dataset e o pacote **já existem** e estão selados — falta a
revisão humana do Edu na terça **2026-10-13** (roteiro de 30 min em
[`GUIA-REVISAO-EDU.md`](../product/GUIA-REVISAO-EDU.md)), o aceite do ADR-001 e os **3 canários
conferidos na fonte original** (hoje conferidos só contra `raw_series.parquet`).
**Depois do Comitê:** o backlog pós-Comitê, com **F-035** (variância mínima, que destrava
`internacional_pesos`) e **F-040** (atualização trimestral, que transforma o projeto em ativo
reutilizável) como os dois de maior retorno.

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
- **Entrega ao Comitê** → [`wiki/runbooks/entrega-comite.md`](./runbooks/entrega-comite.md) (o gate) ·
  [`docs/product/GUIA-REVISAO-EDU.md`](../product/GUIA-REVISAO-EDU.md) (a revisão do Edu, 30 min) ·
  [`docs/product/LIMITACOES-COMITE.md`](../product/LIMITACOES-COMITE.md) (o que o número sustenta)
- Estado vivo → [`TODO.md`](../../TODO.md) · Contrato com agentes → [`AGENTS.md`](../../AGENTS.md)

---

*Atualize esta página quando: o PRD mudar de versão, uma decisão bloqueante for respondida, a fase mudar, ou
o dataset canônico passar a existir. Não atualize por feature pequena.*
