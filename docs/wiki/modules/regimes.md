# Módulo `regimes` — classificação de regimes macro e métricas (**classe C**)

> Síntese — fonte de verdade: `docs/research/metodologia-regimes-macro.md` + `SPEC.md` RF-027..RF-040 + **ADR-001/002/003** + `CONTRACTS.md §5`. **Estado (2026-10-11, pós-Onda 4): V1 (F-019), V3 (F-021), as métricas por regime × ativo (F-022), o heatmap (F-023), o ranking (F-024), a timeline (F-025) e o internacional (F-026) estão IMPLEMENTADOS e materializados.** V2 (F-020) foi **cortada** da onda e `regimes.parquet` **não é gravado** (**D-r**/**D-ab**: resta um bloqueio, `regime_v1` não anulável). **Gate de publicação FECHADO:** ADR-001 em `Proposta` ⇒ `especificacao_congelada = False` ⇒ **nenhum número daqui é publicável** (CA-090).

## Propósito

Responder à pergunta literal do e-mail — *"como cada classe de ativo e setor performou em **momentos
semelhantes**"* — classificando os 83 trimestres e medindo retorno por regime × ativo. Entrega **lentes
paralelas**, não uma verdade: com `n ≈ 20` por célula não há graus de liberdade para achar "o" regime.

## Lentes / RFs cobertos

| Lente / saída | O que é | RF | Estado |
|---|---|---|---|
| **V1** — quadrantes crescimento × inflação | 4 células; `g = ibcbr_gap`, `pi = ipca_12m_delta`, limiares `0.0` | RF-027, RF-030, RF-031 | **F-019 implementada** |
| **V2** — V1 × ciclo Selic | 12 estados teóricos, ~7-8 povoados; linguagem do Comitê, mas **endógena** | RF-028 | **F-020 CORTADA da v1** — `ciclo_selic` existe em `macro_quarterly.py` (**importe, não reimplemente**) e a distribuição 34/23/26 já é publicada, mas **nenhuma** linha de nenhuma tabela tem `lente = V2`; onde CA-098 dizia "V1 e V2", a entrega é **V1 `revised` + V1 `asof` + V3** (**D-aa**) |
| **V3** — vizinhos mais próximos (Mahalanobis + Ledoit-Wolf, k=8) | responde **literalmente** ao e-mail, sem binarizar | RF-029, RF-036 | **F-021 implementada** |
| `regimes.parquet` (as 3 lentes numa tabela) | `RegimesSchema` | — | **NÃO GRAVADO** (**D-r**/**D-ab**) — F-026 resolveu `stress_flag`; resta `regime_v1` não anulável (**D-m**), que é dívida de contrato (`TODO.md §6`) |
| Métricas por regime × ativo · heatmap · timeline · ranking | média, mediana, `n`, dispersão | RF-032..RF-035, RF-037, RF-040 | **F-022..F-025 implementadas** — ver `modules/analysis.md` para figuras e tabelas |
| Dimensionamento internacional + regra de risk-off | piso estrutural + banda tática por regime | RF-038, RF-039 | **F-026 implementada** — ver `modules/internacional.md` |

## O que está materializado em `data/canonical/` (2026-10-11, pós-rebuild)

| Artefato | Schema | Estado medido |
|---|---|---|
| `regimes_v1.parquet` | `RegimesV1Schema` | **83 × 18** · `revised` · **67** classificados / **16** `INDETERMINADO` · `sha256 76512d8d…` |
| `regimes_v1_asof.parquet` | `RegimesV1Schema` | **83 × 18** · `asof` · **67** classificados · `sha256 cabdc272…` |
| `regime_neighbors_v3.parquet` | `RegimeNeighborsV3Schema` | **9.692 × 21** · 77 referências · **a lente principal** · `sha256 a17d9288…` |
| `regime_neighbors.parquet` | `RegimeNeighborsSchema` | **5.500 × 11** · pool restrito de CA-089 · **não é a resposta** · `sha256 a5d7d127…` |
| `regime_asset_metrics.parquet` | `RegimeAssetMetricsSchema` | **120** células · V1 `revised` em **T0** + V3 em **T+1** · **o entregável** · `sha256 549a1e90…` |
| `regime_asset_metrics_asof.parquet` | idem | **96** · V1 `asof` em T0 — a V3 **não tem** variante `asof` · `sha256 407df0f3…` |
| `regime_asset_metrics_horizonte_cruzado.parquet` | idem | **120** · V1 em T+1 + V3 em T0 — isola o efeito do **horizonte** do efeito da **lente** · `sha256 4b8d393e…` |
| `relatorio_metricas.json` | — | as 17 métricas por célula, `sharpe` nas 2 fórmulas, razão × subtração, a concordância por referência e o bloqueio de `regimes.parquet` |
| `relatorio_regimes_v1{,_asof}.json` · `relatorio_regimes_v3.json` | — | `versao_build 5b747508…` / `b3b81d75…` · distribuição, `n`, flags, sensibilidade, divergência `asof` × `revised`, 8 vizinhos, ranking, gate |

Builds (idempotentes, **2 rodadas = hashes idênticos**), depois de `macro_quarterly` e `asof`:

```bash
uv run python -m apps.pipeline run --offline      # TUDO, 13 etapas na ordem (F-029) - prefira este
# ou, etapa por etapa:
uv run python -m apps.pipeline.canonical.regimes_v1                        # revised
uv run python -m apps.pipeline.canonical.regimes_v1 --materializacao asof  # asof
uv run python -m apps.pipeline.canonical.regimes_v3 --offline
uv run python -m apps.pipeline.canonical.metricas_regime --offline         # as 3 tabelas de F-022
```

## V1 — a distribuição medida (`revised`)

| regime | `n` | % dos 67 |
|---|---|---|
| RECUPERACAO | **19** | 28,4% |
| EXPANSAO_INFL | **19** | 28,4% |
| ESTAGFLACAO | **16** | 23,9% |
| DESACELERACAO | **13** | 19,4% |
| *(INDETERMINADO)* | *16* | — |

**CA-080 fecha:** 4 quadrantes povoados, todos em [10, 35], desbalanceamento **1,46×**, nenhuma
flag de `n` acesa, **0 desempates** (nenhum eixo é exatamente `0.0` no dado real, então CA-079 só é
exercitado em sintético). Na `asof`: **EXP 21 · REC 17 · EST 16 · DES 13**.

A distribuição mudou com **D-s** (o nível trimestral do IBC-Br passou a ser a **média dos 3 meses**,
como `metodologia §2` escreve): era `EXP 20 · REC 17 · EST 15 · DES 15` com o fim de período, e
**7** trimestres mudaram de quadrante — **2013Q2, 2013Q3, 2013Q4, 2020Q1, 2023Q3, 2024Q1, 2025Q2**,
exatamente os 7 que o QA da Onda 2 previu. **Sensibilidade do limiar da aceleração (±0,1 pp):** no
máximo **1** trimestre troca na `revised` (1,20%) e 4 na `asof` (4,82%) — o eixo não está empilhado
em torno de zero.

## As 17 métricas por `(lente, regime, asset_id)` — e as 3 que divergem da letra

`asset_returns_quarterly` está em **fração** (**D-o**), e as 3 colunas de retorno têm o **mesmo**
padrão de nulo (23 nulos, o 1º trimestre de cada série) — é isso que torna `n_obs` não ambíguo.
`n_obs` · `ret_medio` · `ret_mediana` · `ret_desvio` (`ddof=1`) · `erro_padrao_media` ·
`hit_ratio` · **`excesso_cdi`** · `hit_ratio_cdi` · `ret_real` · `sharpe_tri` ·
`pior_tri`/`melhor_tri` (+ `_quarter`) · `beta_ibov` · `alerta_n_baixo` · `conclusao_suprimida`.

| Escolha | O que foi feito | Por quê |
|---|---|---|
| **`sharpe_tri`** | `média(ret_excesso_cdi) / desvio(ret_excesso_cdi)` | a fórmula literal de `metodologia §3` é **subtração de médias**, que CA-069/Anti-SPEC §10.2.13 proíbe. Divergência **medida** em 92 células: média 0,039, **máximo 0,695** em `RECUPERACAO/IMAS` — o `IMAS` segue o CDI, então o desvio **nominal** dele é quase todo variação do patamar da Selic |
| **`pior_tri`/`melhor_tri` com data, não max-drawdown** | é a instrução da metodologia para regime **não contíguo** | a contiguidade está medida: `RECUPERACAO` são 19 trimestres em **11 blocos** (maior = 4). Encadear drawdown sobre blocos descolados produziria número que nenhuma carteira viveu |
| **Sharpe trimestral, anualização declarada e NÃO aplicada** (CA-094) | fator `√4 = 2` publicado no relatório | índice não é implementável sem fricção (Anti-SPEC §10.2.11) |

**Por que 3 tabelas e não 1 com coluna de materialização:** a PK é `(lente, regime, asset_id)` e
`strict=True`; as três leituras **colidiriam** na mesma tabela, e acrescentar coluna a schema
existente é **alteração** ⇒ pausa (`AGENTS.md §9`). As 2 colunas que colapsariam tudo
(`materializacao`, `horizonte`) estão na lista de dívidas de `TODO.md §6`.

### O que as métricas dizem — e a frase que vai ao slide

**Os 3 extremos** (tabela principal): `DESACELERACAO`/`UTIL` **+8,23%** (`n = 13`, `hit_ratio_cdi`
0,85) · `DESACELERACAO`/`IEEX` +6,31% · `RECUPERACAO`/`IMOB` +6,30% (`n = 19`, mas
`pior_tri = −45,46%` em `2020Q1`). **Os 3 piores:** `ESTAGFLACAO`/`IMOB` **−6,90%** ·
V3/`IMOB` −6,50% (`n = 4`, **conclusão suprimida**) · `ESTAGFLACAO`/`SMLL` −5,69%. O **IMOB**
aparece nos dois extremos — é o ativo mais sensível a regime da amostra.
**Mas o erro-padrão da média é de 0,4 a 5 pp e `n` vai de 4 a 19: a ordem do topo não é
distinguível de ruído**, e é essa a frase que acompanha a figura.

## V3 — os 8 vizinhos de `2026Q3` (o entregável do Comitê)

Lente principal: **Mahalanobis + Ledoit-Wolf** (`rho = 0,259874`, condicionamento 8,26 → 3,97,
implementado em numpy puro), `k = 8`, amostra completa, janela cheia.
**Linguagem obrigatória: descritiva.** "Em momentos parecidos, o ativo rendeu X, com n = 8" —
nunca "vai render" (Anti-SPEC §10.2.10).

| rank | vizinho | distância | `T+1` | V1 do vizinho |
|---|---|---|---|---|
| 1 | **2006Q3** | 0,9616 | 2006Q4 | *(indeterminado, D-m)* |
| 2 | **2006Q4** | 0,9832 | 2007Q1 | *(indeterminado)* |
| 3 | **2006Q1** | 1,3249 | 2006Q2 | *(indeterminado)* |
| 4 | **2024Q3** | 1,3482 | 2024Q4 | `EXPANSAO_INFL` |
| 5 | **2014Q4** | 1,4097 | 2015Q1 | `DESACELERACAO` |
| 6 | **2007Q1** | 1,4195 | 2007Q2 | *(indeterminado)* |
| 7 | **2024Q2** | 1,5041 | 2024Q3 | `EXPANSAO_INFL` |
| 8 | **2014Q3** | 1,5061 | 2014Q4 | `ESTAGFLACAO` |

A V3 agrupou `2026Q3` com **2006-2007** (juro real de 8-10%, inflação desacelerando, real se
valorizando — o tripé no fim do ciclo de aperto) e com **2024** (juro real de 7-8%, inflação
acelerando de leve). **D-s não mudou nada aqui:** lista, distâncias e ranking saíram
byte-idênticos, porque nenhuma das 5 features passa pelo IBC-Br.

> ⚠️ **A sobreposição entre a lente descritiva e a `somente_passado` é uma DISTRIBUIÇÃO, não o
> número de `2026Q3`** (**D-y**, P1-2 do QA da Onda 3). Em `2026Q3` o Jaccard é 1,0, mas isso é
> **vácuo**: `2026Q3` é o **último** trimestre da janela, não existe futuro para a lente descritiva
> escolher, então as duas coincidem **por construção**. Medido nas **58** referências que têm as
> duas lentes: **mediana 0,455** · média 0,461 · Q1 0,231 · Q3 0,600 · mínimo **0,000**, e **só 7
> de 58** dão 1,0 (`2011Q3` e `2012Q1` dão **zero**). E **2.751 das 5.500 linhas (50,0%)** da
> variante descritiva têm vizinho **no futuro** da referência. A leitura correta é o **oposto** da
> que estava escrita aqui: a lente descritiva muda o conjunto de vizinhos em cerca de **55%** dos
> casos. O texto antigo chamava o 1,0 de "o achado mais forte da feature" — era escolher a
> evidência depois de ver o resultado (Anti-SPEC §10.2.9).

### Concordância entre as lentes (CA-103) — também uma distribuição

**Em `3T2026` a interseção dos top-5 das três lentes é VAZIA**, e isso **é** o resultado: o par
V1 `revised` × V1 `asof` tem Jaccard **0,0** com a **mesma** lente e o **mesmo** método — só muda a
defasagem de divulgação; é CA-074 traduzido em ranking de ativos. Sobre **todas** as referências
(**61** comparáveis de 77; as 16 fora são as de **D-m**, `2026Q3` inclusive): Jaccard V1 × V3 com
mínimo **0,0**, **mediana 0,111**, média 0,162, Q3 0,250, máximo 0,667, **17 de 61 zeros** e
**0 referências** com top-5 idêntico em 20 anos. Ou seja: a concordância típica é de **1 ativo em
5**, e o 0,25 do trimestre do Comitê fica no **terceiro quartil** — citá-lo sozinho **superestima**
o acordo entre as lentes. **Spearman** da ordem inteira (F-024, numpy puro): V1 `revised` × V1
`asof` = **−0,748**.

**Ranking no `T+1` dos 8, por `ret_excesso_cdi` (em fração; aqui × 100):** `INDX` **+5,04%**
(ep 2,54) · `ACWI_BRL` +3,78 · `IMAT` +3,60 (ep **3,70** — indistinguível de zero) · `SP500_BRL`
+3,41 · … · `IFIX` **−5,60% com n = 4** e `IMOB` **−6,50% com n = 4**, as duas com
`conclusao_suprimida = True` (CA-109). **Com `ep` de 2,5 a 5 pp, só `INDX` chega perto de 2
erros-padrão** — e média × mediana divergem muito em 6 ativos, sinal de um trimestre dominando.

## Fonte primária e fallback

- **Primária:** `macro_quarterly` (ou `macro_quarterly_asof`) + `asset_returns_quarterly` +
  `raw_series` para a inclinação. Métrica primária do heatmap: **excesso sobre CDI** (ADR-002).
  Eixo inflação da V1: **aceleração do IPCA 12m** (ADR-001) — a coluna é `ipca_12m_delta`.
- **F-022/F-024 leem `regime_neighbors_v3.parquet`**, lente `metrica=mahalanobis`, `k_usado=8`,
  `somente_passado=False`, `restrito_pos_2016=False` (**D-u**). As outras 23 combinações são
  **sensibilidade**. `regime_neighbors.parquet` existe para CA-089 e perde **4 dos 8** vizinhos de
  `2026Q3` porque `regime_v1_neighbor` é `nullable=False` — ver `CONTRACTS.md §5.2a`.
- **O retorno de `T+1` não está em nenhum dos dois schemas:** junte `quarter_t_mais_1` com
  `asset_returns_quarterly.quarter` — ou **importe** `retornos_em_t_mais_1` e `ranking_de_ativos`
  de `regimes_v3.py`, que já fazem isso com `n`, mediana, erro-padrão e as duas flags.
- **A inclinação principal (`INCLINACAO_REAL_5A_3A`, D-i) não é coluna de `macro_quarterly`**
  (**D-n**): leia a **série** de `raw_series`/`data/processed/curva/` via `alinhar_series`.
  `macro_quarterly` publica a 5a−1a com **33 nulos (39,8%)** e declarados.
- **Unidade (D-o):** `macro_quarterly` em **por cento/pp**, `asset_returns_quarterly` em **fração**.
  O ranking da V3 está em **fração**.
- **Fallback:** F-016 (curva) e F-010 (Focus) chegaram, então o corte por fonte ausente não se
  aplica — mas `FEATURES_V3` roda com **5 das 6** features declaradas (`termos_troca_yoy` é 100%
  nula, G-02 / F-037) e `n_features = 5` é declarado **na linha**. Clustering (GMM/k-means) e HMM
  mensal ficam para a fase 2 (**F-039**) como validação independente.

## Armadilhas conhecidas

- ⚠️ **A V1 NÃO É OPERACIONAL na forma `asof` — CA-074 acionado.** A troca de rótulo entre
  `revised` e `asof` é **22 de 66 trimestres = 33,33%** (era 29,85% antes de D-s), acima do limiar
  de **25%**. Pelo critério de `metodologia §5.1` a leitura **operacional** ("em que quadrante
  estamos agora, com o que se sabia na época") cai, e com ela a hipótese **H-03 do PRD**; a leitura
  **descritiva** (RF-027) segue válida e é o entregável. Mecanicamente: `ibcbr_gap` é um hiato
  pequeno (mediana `|g| ≈ 2 pp`) sobre média móvel de 20 trimestres, e deslocar o IBC-Br de um
  trimestre troca o sinal com facilidade. **Vai à página de limitações (F-028) e ao slide**, não a
  nota de pé. Saídas possíveis em `TODO.md §4`.
- **O eixo de crescimento é o HIATO, não o crescimento.** `g > 0` significa "cresce **acima da
  tendência**", não "cresce": 2016 inteiro é `DESACELERACAO` e 2021Q4 é `RECUPERACAO`. Quem ler o
  rótulo como "PIB subindo/caindo" lê errado.
- **O eixo de inflação ignora o NÍVEL.** 2022Q3 é `RECUPERACAO` com IPCA 12m a **7,17%**, porque a
  aceleração foi −4,72 pp (desoneração de combustíveis). Se o Comitê ler "inflação baixa", a
  leitura está invertida. É o trade-off que ADR-001 §Consequências registra.
- **A V1 classifica 67 dos 83 trimestres** (**D-m**): `ibcbr_gap` tem **16** nulos porque a média
  móvel de 20 trimestres só fecha em **2009Q4** e o IBC-Br não existe antes de 2003. **2006-2009,
  inclusive a crise de 2008, fica fora do eixo de crescimento.** Qualquer cruzamento regime ×
  retorno (F-022) que faça `dropna()` em silêncio roda sobre 67 trimestres sem dizer — o `n` tem de
  aparecer em **toda** célula, e o `n` dos indeterminados está publicado para isso.
- **`n` pequeno:** ~16-19 trimestres por regime; **diferença < 5 pp entre células é ruído**. Célula
  com `n < 5` nunca vira conclusão publicada (`conclusao_suprimida`).
- **`n_obs_regime_v1` é estatística da AMOSTRA INTEIRA**, de propósito (a leitura é "onde estamos no
  histórico"). Quem usar a tabela para **backtest** precisa recalcular `n` em janela **expanding** —
  e backtest está fora de escopo (Anti-SPEC §10.3.16).
- **Overfitting:** ajustar a especificação **depois** de ver os retornos é proibido (Anti-SPEC §10).
  A sensibilidade é reportada *porque* a especificação está congelada, não para escolhê-la.
- **O gate de publicação depende de um arquivo Markdown.** `especificacao_congelada` é lido do
  `- **Status:**` do `ADR-001`; cabeçalho alterado → `DESCONHECIDO` → **não congela** (falha
  fechada, correto), mas o motivo fica no warning do log.
- **`fonte_versao` muda quando outra lente acrescenta ao schema.** `MODULOS_DO_REGIME_V1` inclui
  `packages/shared/schemas/regimes.py`, e F-020/F-021 acrescentam ao mesmo arquivo: hash diferente
  **não** implica número diferente. Confira contra o `versao_build` do relatório **da mesma
  rodada**.
- **Descritivo ≠ preditivo.** É o maior risco reputacional: nenhuma saída deste módulo é previsão.
- **V2 é endógena** (o Copom reage a crescimento e inflação) → corte secundário, nunca lente única.
  E **D-t** mudou a régua: `|Δ| >= 0,25 pp` é **movimento**, não parada (`CORTE 34 · NEUTRO 23 ·
  ALTA 26`), porque os cortes reais de 25 bps de 2024Q2/Q3 saíam `NEUTRO`.
- **A exclusão de vizinhança da V3 é simétrica (`T±1`, `T±2`)** e CA-085 fala só dos anteriores —
  sem a simetria o vizinho rank 1 de quase todo trimestre seria `T+1`, autocorrelação trivial.
- **Quebra estrutural 2006-2008 vs. pós-2016** e janelas desiguais por ativo → a timeline sobre
  IBOV e Selic é o **sanity check** com quem viveu o período, entregue **antes** do pacote final.
  A variante `pos2016` da V3 **muda a mensagem** (internacional na frente, `INDX` cai a +0,65%)
  porque os vizinhos passam a ser 2022-2025: **a divergência é resultado, não defeito**
  (CA-087/CA-103).
- **Concordância entre lentes é o sinal**: quando V1, V2 e V3 apontam o mesmo ativo, a leitura é
  robusta; quando divergem, a divergência é o resultado (RF-034/RF-037).

**Features do TODO:** **F-019** (V1, implementada) · **F-020** (V2, `should`) · **F-021** (V3,
implementada) · **F-022** (métricas + junção, **D-r**) · **F-023** (heatmap) · **F-024** (ranking) ·
**F-025** (timeline) · **F-026** (internacional) · **F-028** (limitações) ·
**F-033**/**F-035**/**F-039** (fase 2).
