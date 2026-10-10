# PRD — Estratégia Macro LDC · base estatística de regimes e alocação

> Product Requirements Document — **o quê e por quê**. O **como** vai para `docs/specs/SPEC.md` (`/SDD-avancado`).
> **Versão:** 1.0 — **Data:** 2026-10-10 — **Autor:** gerado por agente (Claude) em **modo autônomo**, a partir de
> `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` + `docs/research/` — **aprovação pendente de Eduardo (Edu)**.
>
> **Modo autônomo:** não houve sessão de discovery com humano. As 16 etapas da skill `/consultor-prd` foram
> respondidas com o e-mail do Alexandre, as duas pesquisas em `docs/research/` e premissas explícitas. **Toda
> premissa que substitui uma resposta humana está marcada `[PREMISSA]` e consolidada na §13.** Em conflito,
> vale `ESCOPO-EMAIL-ALEXANDRE.md`.

---

## 1. Visão geral

### Problema

O Comitê de Alocação da LDC Capital decide alocação macro doméstica e tamanho de posição internacional com
leitura qualitativa de conjuntura. Não existe hoje uma base que responda à pergunta operacional do gestor:
**"em trimestres macroeconomicamente parecidos com o atual, como cada classe de ativo e cada setor realmente
performou?"**. Os dados existem (BCB, IBGE, ANBIMA, B3, Tesouro), mas em 8+ fontes com formatos, frequências,
encodings e janelas incompatíveis — e várias rotas óbvias estão mortas (swap DI×pré do SGS parou em set/2019;
ETTJ histórica da ANBIMA é paga). Sem essa base, a decisão de alocação não é auditável.

### Solução proposta

Pipeline Python local que extrai, normaliza e alinha 20 anos de séries macro brasileiras e de desempenho de
ativos/subsetores num **dataset canônico trimestral** (≈ 83 trimestres, 1T2006 → 3T2026), classifica cada
trimestre em **regimes macro** por três lentes paralelas (quadrantes, ciclo Selic, vizinhos mais próximos) e
produz as tabelas e o **heatmap regime × ativo** que o Alexandre usa para modelar.

### Objetivo principal

Entregar, **até 2026-10-13** (um dia antes do Comitê de 2026-10-14), um dataset canônico trimestral
regenerável com um comando, cobrindo **≥ 90% das séries pedidas no e-mail na janela 2006→2026**, com
**3 valores por série conferidos contra a fonte original**, mais o heatmap regime × ativo e a tabela
"regime atual → ranking de ativos".

O produto é **descritivo**, não preditivo: mede como cada ativo performou em regimes passados. Não prevê
retorno, não otimiza carteira, não faz backtest. Confundir descritivo com preditivo é o maior risco
reputacional do projeto (`docs/research/metodologia-regimes-macro.md §0.8`).

---

## 2. Contexto e motivação

- **Situação atual.** Alexandre Kaercher (gestor) pediu por e-mail (out/2026) auxílio para **estruturar a
  busca e extração** das séries do seu modelo. Repositório em kickoff: estrutura Harness v3.2 criada, nenhum
  extrator escrito, `data/` vazio; pesquisa de fontes e metodologia concluída em 2026-10-10.
- **Por que agora.** Reunião do **Comitê de Alocação em 2026-10-14** — prazo duro, ~3 dias úteis ("o quanto
  antes, conseguirei modelar a estratégia a tempo para o encontro").
- **Impacto esperado.** A decisão de alocação passa a ter base estatística auditável linha por linha, e a casa
  ganha um ativo reutilizável que se atualiza a cada trimestre.
- **Autorização de ajuste.** O e-mail diz "fique à vontade para ajustes caso não localize estes dados": toda
  substituição de fonte é permitida **desde que registrada** em `docs/plans/DECISIONS_LOG.md` (fonte pedida,
  fonte usada, por quê, impacto na comparabilidade).

---

## 3. Usuários e personas

### Persona principal — Alexandre Kaercher (gestor, cliente interno)

- **Quem é:** gestor/estrategista da LDC, responsável pelo modelo de alocação apresentado ao Comitê.
- **O que precisa:** o **dataset trimestral** (para modelar por conta própria) e o **heatmap regime × ativo**
  + tabela "regime atual → ranking" (para sustentar a recomendação na reunião).
- **Frustração atual:** não consegue afirmar "em regimes como o atual, IMA-B bateu o CDI em X% dos trimestres"
  sem montar a base à mão.
- **Frequência de uso:** intensa até 2026-10-14; depois, trimestral (a cada fechamento).
- **Contexto de uso:** desktop; consome Parquet/CSV/XLSX e figuras. **Não roda o pipeline.** `[PREMISSA]`

### Persona operadora — Eduardo (Edu, dono do projeto)

- **Quem é:** dono do projeto; orquestra os agentes de IA que escrevem o pipeline.
- **O que precisa:** reconstruir o dataset com um comando, saber exatamente qual número veio de onde, e ter
  evidência de conferência antes de mandar qualquer coisa ao Alexandre (operação **classe D**).
- **Contexto de uso:** terminal local, **Windows**, Python 3.11+.

**Consumidor indireto — Comitê de Alocação:** consome o material sintetizado (heatmap, ranking, timeline,
página de limitações). Não acessa dataset nem código.

### Anti-personas (o produto NÃO atende)

Cliente final / investidor externo (não há interface, conta, auth ou publicação web); trader intradiário
(a granularidade de decisão é trimestral); compliance / relatório regulatório (não é fonte oficial de nada);
e quem quer "o número que o modelo prevê" (o produto é descritivo).

---

## 4. Escopo

### 4.1 Dentro do escopo (v1 = "pacote mínimo" da §7 da metodologia) `[PREMISSA]`

Blocos **A** (macro), **B** (ativos e subsetores) e **C** (internacional) do e-mail, na janela
**1T2006 → 3T2026**, análise **trimestral** com armazenamento na granularidade nativa. Regimes pelas lentes
**V1** (quadrantes crescimento × inflação) e **V3** (vizinhos mais próximos); **V2** (ciclo Selic) como corte
secundário. Entregáveis 1–9 da §7 da metodologia. `[PREMISSA]` o "pacote mínimo" da pesquisa foi adotado como
escopo da v1 por ser o único realista em 3 dias úteis; o "pacote estendido" vira **fase 2** (§4.3).

### 4.2 O escopo implícito que vira requisito explícito — **tamanho da alocação internacional**

O e-mail abre com "modelo de alocação macro doméstica **e tamanho da alocação internacional**", mas não lista
nenhuma série internacional nos blocos A/B. O item **C1** do checklist de escopo registra isso como implícito.
**Este PRD o torna explícito:** o internacional entra como **classe de ativo em BRL dentro do mesmo
arcabouço** de regimes (não como anexo), e "quanto no exterior" é respondido por RF-038/RF-039 como
**faixa estrutural + banda tática por regime**, não como número pontual — porque com n≈20 por regime a
otimização não sustenta um ponto. `[PREMISSA]` (decisão **D6**, §13).

### 4.3 Fase 2 (fora da v1, registrado como backlog)

V1b (eixos vs. Focus) e V2 completa com teste de robustez; setoriais B3 completos e FII segmentado estendido;
EMBI/CDS e termos de troca na matriz; variância mínima por regime com shrinkage e fronteira eficiente; dupla
materialização `asof` × `revised` com relatório de divergência; clustering (GMM/k-means) como validação
independente; HMM mensal com matriz de transição; dashboard de regime corrente.

### 4.4 Fora de escopo (explícito, v1 e v2)

- **Backtest de estratégia** e qualquer otimização walk-forward (decisão **D11**).
- **Previsão** / sinal preditivo / probabilidade de regime futuro.
- **Interface web, dashboard hospedado, API, deploy.** Roda local.
- **Dados pagos:** ANBIMA Feed (≈R$ 686–8.238/mês), Bloomberg, Comdinheiro, MacroMicro, Cbonds. Nada no
  caminho crítico depende de fonte paga.
- Reconstrução de IFIX sintético pré-2011 e de segmentação de FII pré-2016 (seria ruído).
- Recomendação de investimento a cliente, material de distribuição, conteúdo regulado.
- Qualquer item não ancorado nos blocos A1–A7, B1–B5 ou C1 do e-mail.

---

## 5. Requisitos funcionais

Numerados e verificáveis. **E-mail** = item que justifica o requisito (A1–A7, B1–B5, C1). Fonte primária e
fallback vêm da tabela-resumo de `docs/research/fontes-de-dados.md`. **Pri:** M = must (v1), S = should.

### 5.1 Extração por fonte

| RF | Requisito verificável | E-mail | Pri | Fonte primária | Fallback |
|---|---|---|---|---|---|
| RF-001 | IPCA variação mensal e acumulado 12m, mensal, 01/2006→09/2026, sem buraco; 3 valores conferidos | A2, A7 | M | BCB SGS **433** e **13522** | IBGE SIDRA t/1737 v/63 e v/2265 (valores idênticos, confirmado) |
| RF-002 | IPCA número-índice (base dez/1993=100) para deflação, mensal, 2006→2026 | A7 | M | IBGE SIDRA **t/1737 v/2266** | SGS 433 encadeado |
| RF-003 | IBC-Br **com ajuste sazonal**, mensal, 01/2006→2026 (série começa em 2003) | A1 | M | BCB SGS **24364** | SGS 24363 (sem ajuste) · Ipeadata |
| RF-004 | PIB trimestral, índice de volume dessazonalizado, 1T2006→2T2026 | A1 | M | IBGE SIDRA **t/1621 v/584 c11255/90707** | **SGS 22109** (idêntico valor a valor) · Ipeadata `SCN104_*` |
| RF-005 | Selic Over diária (%/dia e % a.a.) e Selic **meta** diária, 2006→2026, fatiando em blocos ≤ 10 anos | A4 | M | BCB SGS **11**, **1178**, **432** | Ipeadata `BM366_TJOVER366` (sem limite de janela) |
| RF-006 | CDI diário (%/dia) 2006→2026 e acumulação geométrica por trimestre; CDI 2006 = 15,0271% reproduzido | B3 | M | BCB SGS **12** | SGS 4389 (% a.a. base 252) · Ipeadata `BM12_TJOVER12` |
| RF-007 | Expectativas Focus (IPCA, Selic, PIB, câmbio) por data de coleta, 2006→2026, filtrando `baseCalculo` fixo | A3 | M | BCB **Olinda OData** `Expectativas*` | `python-bcb` módulo Expectativas · Ipeadata `BM12_IPCAEXP1212` |
| RF-008 | Taxas e PUs de títulos públicos (LTN/NTN-B/NTN-F/LFT), diário, 31/12/2004→hoje, por vencimento | A5 | M | **Tesouro Transparente CKAN** `precotaxatesourodireto.csv` | ANBIMA `ms*.txt` (só ~20 d.u.) · lib `pyield` |
| RF-009 | Inclinação da curva por vértices fixos interpolados (real NTN-B curta×longa; nominal 1a e 5a), diário 2006→2026, com flag de vértice extrapolado | A6 | M | **Tesouro Direto interpolado** (RF-008) — porque **SGS 7801-7806 morreu em 30/09/2019** e **ANBIMA ETTJ só tem ~20 d.u.** | Ipeadata `ANBIMA366_TJTLN{1,3,6,12}366` (só ≤12m) · DI futuro B3 via `pyield` · ANBIMA Feed (pago, fora de escopo) |
| RF-010 | Job diário que arquiva `Msec_txt.txt` e o POST `CZ-down.asp` em `data/raw/`, idempotente, tratando ausência como caso normal | A6 | M | ANBIMA mercado secundário + Curva Zero | — (sem fallback: é construção de série proprietária) |
| RF-011 | Número-índice diário de IMA-B, IMA-B 5, IMA-B 5+, IRF-M, IRF-M 1, IRF-M 1+ (e IMA-Geral, IMA-S), 2006→2026; rótulos normalizados; IMA-B 16/09/2003 = 723,070317 como valor-canário | B1, B2 | M | **Bucket S3 público da ANBIMA** `{SLUG}-HISTORICO.xls` (é XLSX apesar da extensão) | SGS **12461/12466/12467/12468/12469/12462** (até 22/05/2023; IRF-M 1 e 1+ **não existem** no SGS) |
| RF-012 | Fechamento diário de IBOV, IDIV, SMLL, INDX, IMAT, IEEX, IFNC, UTIL, ICON, IMOB, 2006→2026, com `data_inicio` por série; IBOV 01/02/2006 = 38.484,84 como valor-canário | B4 | M | **API B3** `indexStatisticsProxy/IndexCall/GetPortfolioDay` (matriz dia×mês, requer unpivot) | `GetDownloadPortfolioDay` (CSV base64) · lib `mercados` · Ipeadata `GM366_IBVSP366` (só IBOV) · ETFs via Yahoo (só sanity check) |
| RF-013 | IFIX diário **2011→2026** com a janela real declarada no output (série começa em 30/12/2010) | B5 | M | API B3 `IFIX` | XFIX11 via Yahoo (2020+, price return — subestima) |
| RF-014 | Índices de FII por segmento (Tijolo, Papel, Logística, Shoppings, Lajes), **2019→2026**, retorno total, casando o arquivo por regex (o nome traz versão embutida) | B5 | S | **Teva Indices** (bucket GCS público listável) | Construção própria COTAHIST + CVM `inf_mensal_fii` com classificador por balanço (esforço alto) |
| RF-015 | USDBRL PTAX diário 2006→2026 (venda e compra) | C1 | M | BCB SGS **1** e **10813** | Olinda PTAX · FRED `DEXBZUS` · Yahoo `BRL=X` |
| RF-016 | S&P 500 e MSCI ACWI em **retorno total**, diário/mensal 2006→2026, convertidos a BRL | C1 | M | Yahoo **`^GSPC`** e MSCI **`892400` variante `NETR`** | ETF `IVV` (2000+) · MSCI USA `984000` · ⛔ FRED `SP500` tem **só 10 anos** |
| RF-017 | Treasury 10y, VIX, Fed Funds e ouro spot, 2006→2026, para o bloco de contexto externo | C1 | S | FRED `DGS10`, `VIXCLS`, `DFF` | Yahoo `^TNX`, `^VIX` — **obrigatório** se o teste de conectividade ao FRED falhar (R-06); ouro: fonte **a confirmar** |
| RF-018 | Calendário de dias úteis ANBIMA carregado e usado em toda acumulação/alinhamento | A4, B3 | M | `anbima.com.br/feriados/arqs/feriados_nacionais.xls` | lib `bizdays` |
| RF-019 | `series_catalog` com `series_id, nome, fonte_url, data_inicio, data_fim, freq, unit, transformacao_padrao` para 100% das séries extraídas | todos | M | gerado pelo pipeline | — |

> Séries do e-mail **sem** cobertura total de 20 anos, com a janela real obrigatoriamente visível no output:
> **ICON** (2007+), **IMOB** (2008+), **IFIX** (2011+), **segmentação de FII** (2019+), **ponta longa nominal
> da curva** (~2010+). Ver lacunas L1, L2, L3 e L5 na §13.

### 5.2 Camada canônica

| RF | Requisito verificável | E-mail | Pri | Observação |
|---|---|---|---|---|
| RF-020 | Tabela longa `raw_series(series_id, date, value, source, freq, vintage, unit, collected_at)` com PK `(series_id, date, vintage)`, validada por pandera | todos | M | Armazena na **granularidade nativa**; trimestral como dado primário é erro irreversível |
| RF-021 | `macro_quarterly` com 83 linhas (1T2006→3T2026), colunas de crescimento, inflação, juros, curva, câmbio e expectativas, mais `is_estimated` e `lag_adjusted` | A1–A7 | M | Schema em `docs/research/metodologia-regimes-macro.md §6.2` |
| RF-022 | `asset_returns_quarterly(quarter, asset_id, …)` com `ret_tri`, `ret_excesso_cdi`, `ret_real`, `is_total_return`, `n_dias_uteis` para ≥ 18 ativos | B1–B5, C1 | M | PK `(quarter, asset_id)` |
| RF-023 | Trimestre = **último dia útil** de mar/jun/set/dez; retorno de T = `P(último DU de T)/P(último DU de T−1) − 1`; forward-fill de no máximo 5 d.u., acima disso `NULL` registrado | — | M | Classe **C** — altera alinhamento temporal |
| RF-024 | Excesso sobre CDI e retorno real **sempre por razão** `(1+r)/(1+b)−1`, nunca por subtração; encadeamento geométrico; teste unitário que falha se alguém usar subtração | — | M | Com Selic a 14% a diferença é material |
| RF-025 | Regra anti-look-ahead implementada e **reportada**: regime de T usa só o que era conhecido no último DU de T (PIB/IBC-Br de T−1; IPCA do penúltimo mês de T; Focus/Selic/DI/câmbio livres), com o **% de trimestres que trocam de regime** vs. a variante revisada | — | M | `[PREMISSA]` v1 reporta o número; a dupla materialização completa é fase 2 (decisão **D4**) |
| RF-026 | Todo DataFrame que entra ou sai de `data/canonical/` passa por schema pandera; coluna de origem obrigatória; **zero** valor interpolado, estimado ou inventado — lacuna sem substituto acordado retorna `BLOQUEADO — FONTE INDISPONÍVEL` | — | M | Anti-SPEC |

### 5.3 Regimes

| RF | Requisito verificável | E-mail | Pri | Observação |
|---|---|---|---|---|
| RF-027 | **V1** — quadrantes: `g_T` = IBC-Br a/a dessaz. menos média móvel de 20 trimestres; `pi_T` = Δ do IPCA 12m; 4 rótulos (`RECUPERACAO`, `EXPANSAO_INFL`, `ESTAGFLACAO`, `DESACELERACAO`); empate herda o sinal do trimestre anterior; ~20 obs por quadrante | A1, A2 | M | Entregável principal `[PREMISSA]` (decisões **D1, D2, D3**) |
| RF-028 | **V2** — camada `ciclo_selic` (`CORTE` se ΔSelic meta < −0,25pp, `ALTA` se > +0,25pp, senão `NEUTRO`; pausa dentro de ciclo de corte conta como `CORTE`), publicada **apenas como corte secundário** com `n` visível | A4 | S | Nunca célula única de decisão (n de 5 a 15) |
| RF-029 | **V3** — 6 features em z-score, distância **Mahalanobis** com shrinkage Ledoit-Wolf, **k=8** (sensibilidade k=5 e k=12), Euclidiana em paralelo como sanity check, excluindo os 2 trimestres imediatamente anteriores | objetivo do e-mail ("momentos semelhantes") | M | Se a curva (RF-009) não ficar pronta, roda com 5 features e declara |
| RF-030 | Tabelas `regimes(quarter, regime_v1, ciclo_selic, regime_v2, stress_flag, g_score, pi_score, fonte_versao)` e `regime_neighbors(quarter_ref, rank, quarter_neighbor, distancia, metrica)` | — | M | `fonte_versao` = hash do código que gerou |
| RF-031 | Especificação de V1/V2/V3 **congelada em ADR antes de rodar** sobre os retornos; ajuste posterior só como V1.1, reportando as duas versões | — | M | Antídoto a overfitting (R-08) |

### 5.4 Análise e visualização

| RF | Requisito verificável | E-mail | Pri | Observação |
|---|---|---|---|---|
| RF-032 | Para cada `(regime, ativo)`: `n_obs`, `ret_medio`, `ret_mediana`, `ret_desvio`, `hit_ratio`, `excesso_cdi`, `hit_ratio_cdi`, `ret_real`, `sharpe_tri`, `pior_tri`, `melhor_tri` e erro-padrão da média | B1–B5, C1 | M | Média e mediana **lado a lado** |
| RF-033 | **Heatmap regime × ativo** (≥ 18 linhas × regimes), valor = `excesso_cdi` médio trimestral, escala divergente centrada em 0, **`n` anotado em toda célula** e `data_inicio` por série no rodapé | B1–B5, C1 | M | Entregável visual central |
| RF-034 | Tabela de 1 página "**regime atual → ranking de ativos**": regime por V1, por V2, os 8 vizinhos da V3, e ativos ordenados por `excesso_cdi` com `hit_ratio_cdi`, `n` e semáforo de confiança | objetivo | M | — |
| RF-035 | **Timeline de regimes 2006→2026** (faixa colorida V1) sobreposta a IBOV e Selic | A1, A2, A4, B4 | M | Sanity check visual do Comitê |
| RF-036 | Saída da V3: os **8 trimestres mais parecidos** com o trimestre de referência, com distância e rótulo V1, **e o retorno de cada ativo nos trimestres SEGUINTES** aos vizinhos | objetivo | M | Responde literalmente ao e-mail |
| RF-037 | Tabela de concordância entre lentes (1 linha por lente, coluna top-3 ativos); divergência entre lentes é reportada como resultado, não escondida | — | S | — |
| RF-038 | **Dimensionamento da alocação internacional:** retorno de `SP500_BRL`, `USD_BRL`, `GOLD_BRL`, `UST10_BRL` por regime no mesmo heatmap, mais `corr(USDBRL, IBOV)` por regime e nos 10 piores trimestres do IBOV | **C1** | M | Escopo implícito virando explícito (§4.2) |
| RF-039 | Regra de risk-off: `stress = 1` quando inclinação cai > 1 d.p. **ou** USDBRL sobe > 10% no trimestre; medir quanto de USD neutraliza a queda do IBOV nesses trimestres, e entregar **faixa estrutural + banda tática por regime** (não número pontual) | **C1** | M | `[PREMISSA]` decisão **D6**; o ramo EMBI do gatilho fica em fase 2 (lacuna L8) |
| RF-040 | Supressão por `n` baixo: célula com `n < 8` recebe flag `ALERTA_N_BAIXO` e hachura; **nenhuma conclusão** afirmativa com `n < 5` | — | M | `[PREMISSA]` decisão **D10** |

### 5.5 Entrega para o Comitê

| RF | Requisito verificável | E-mail | Pri | Observação |
|---|---|---|---|---|
| RF-041 | **1 notebook** reprodutível que carrega → classifica → calcula métricas → gera as figuras, sem lógica de negócio (importa de `apps/pipeline/`), com outputs limpos no commit | entregável do e-mail | M | — |
| RF-042 | **1 página de limitações**: n pequeno e potência estatística (erro-padrão ~2,7 pp/tri com n=20 e σ=12%), quebra estrutural 2006-2008 vs pós-2016, look-ahead, séries com janela curta, índices não investíveis sem fricção | — | M | Blinda a reunião |
| RF-043 | Pacote de entrega ao Alexandre: dataset em Parquet **+ CSV/XLSX** (`macro_quarterly`, `asset_returns_quarterly`, `regimes`, `regime_neighbors`), figuras e as duas tabelas de 1 página | entregável do e-mail | M | `[PREMISSA]` formatos assumidos |
| RF-044 | Publicação tratada como **classe D**: revisão humana do número pelo Edu, dataset congelado com versão + hash, linha em `docs/wiki/log.md`, rollback em `docs/plans/infra-ops.md` | — | M | `AGENTS.md §2` |
| RF-045 | Comunicar ao Alexandre, por escrito, as **substituições de fonte** feitas e as séries sem 20 anos, antes do Comitê | autorização de ajuste no e-mail | M | Substituição silenciosa é proibida |

### 5.6 Reprodutibilidade e rastreabilidade

| RF | Requisito verificável | E-mail | Pri | Observação |
|---|---|---|---|---|
| RF-046 | **Um comando** reconstrói `data/raw` → `processed` → `canonical` a partir de zero, em máquina limpa, documentado em runbook | — | M | `data/` é reconstruível; a fonte de verdade é o script |
| RF-047 | Toda linha canônica rastreável até a origem: `source`, `series_id`, `vintage`, `collected_at` e URL no `series_catalog` | — | M | Sem isso o look-ahead bias fica invisível |
| RF-048 | **Idempotência:** rodar o pipeline duas vezes produz o mesmo hash; revisão retroativa da fonte (IBGE revisa PIB) atualiza a linha, não duplica | — | M | CI N3 |
| RF-049 | Toda fonte externa em teste é **fixture gravada** em `tests/fixtures/`; rede só sob `@pytest.mark.network`, que **não roda no CI** | — | M | — |
| RF-050 | Testes de contrato com **valor-canário** para os 3 endpoints não documentados (B3 `indexStatisticsProxy`, MSCI `app2.msci.com`, S3 da ANBIMA): shape + valor conhecido | — | M | Detecta mudança de layout sem aviso |
| RF-051 | Cache condicional por `ETag`/`Last-Modified` para os arquivos grandes (Tesouro 14,6 MB; COTAHIST até 91 MB) | — | S | — |
| RF-052 | Toda substituição de fonte registrada em `docs/plans/DECISIONS_LOG.md` com fonte pedida, fonte usada, por quê e impacto na comparabilidade | autorização no e-mail | M | — |

**Total: 52 requisitos funcionais.**

---

## 6. Requisitos não funcionais

| RNF | Requisito | Como se verifica |
|---|---|---|
| RNF-001 | **Reprodutibilidade** — dataset inteiro regenerável com um comando, de zero, sem passo manual | CI N3 roda o pipeline sobre fixtures duas vezes e compara hash |
| RNF-002 | **Rastreabilidade** — toda série e toda linha canônica com coluna de origem (`source`, `series_id`) e `vintage`/`collected_at` | schema pandera rejeita linha sem origem |
| RNF-003 | **Sem dado inventado** — nenhuma interpolação, estimativa ou valor plausível para fechar série; dado sintético só em fixture nomeada como tal | revisão de PR + teste que procura preenchimento silencioso |
| RNF-004 | **Execução local em Windows**, Python **3.11+**, ambiente `uv` ou venv (nunca global) | pipeline roda na máquina do Edu; encoding declarado explicitamente em todo leitor (nunca confiar no cp1252) |
| RNF-005 | **Sem rede no CI** — toda fonte externa via fixture; `ruff check` + `ruff format --check` + `pytest` verdes | `.github/workflows/ci.yml` |
| RNF-006 | **Sem credencial e sem fonte paga** no caminho crítico; nenhum segredo no repositório | revisão de PR; `.gitignore` cobre `.env` |
| RNF-007 | **Resiliência de extração** — retry com backoff; corpo de resposta validado antes do parse (fonte que devolve erro com HTTP 200 é a falha dominante); User-Agent de browser em todas as requisições | teste negativo por extrator (resposta vazia, HTML, JSON com `error`) |
| RNF-008 | **Tempo de reconstrução** ≤ 30 min numa execução completa a frio | medido no runbook `[PREMISSA]` |
| RNF-009 | **Dados fora do git** — `data/raw|processed|canonical` não versionados; nada > 5 MB commitado | `git status` limpo após rodar o pipeline |
| RNF-010 | **Legibilidade para o gestor** — toda tabela entregue tem `n` e janela de datas visíveis; nenhuma figura sem rodapé de cobertura | revisão humana classe D |

---

## 7. Métricas de sucesso

| Métrica | Meta | Como medir |
|---|---|---|
| Cobertura temporal | **≥ 90% das séries pedidas** nos blocos A/B/C com dados em 2006→2026 | contagem no `series_catalog`: séries com `data_inicio ≤ 2006-01-31` ÷ total pedido; as exceções conhecidas (ICON, IMOB, IFIX, FII segmentado) são declaradas, não mascaradas |
| Conferência contra a fonte | **3 valores por série** conferidos contra a fonte original, com print/link | matriz de validação do Feature Contract de cada extrator (`AGENTS.md §5`) |
| Entrega do heatmap | **heatmap regime × ativo pronto até 2026-10-13** para revisão do Edu | arquivo gerado + linha em `docs/wiki/log.md` |
| Dataset canônico | `macro_quarterly` com **83 trimestres** e `asset_returns_quarterly` com ≥ 18 ativos | contagem de linhas + min/max de data no QA |
| Reprodutibilidade | **1 comando**, 2 execuções → **mesmo hash** | CI N3 |
| Integridade | **0** valores interpolados/estimados sem registro; 0 linhas sem coluna de origem | schema pandera + revisão de PR |
| Utilidade para o cliente interno | Alexandre consegue modelar a estratégia a tempo do Comitê de 2026-10-14 | confirmação explícita do Alexandre |

---

## 8. Restrições e premissas

### Restrições (não negociáveis)

- **Prazo duro:** Comitê em **2026-10-14**; heatmap para revisão do Edu em **2026-10-13**. Entre perfeição e
  série entregue e conferida, entrega a conferida e registra a dívida no `TODO.md`.
- **Orçamento de dados: zero** (nenhuma fonte paga). **Roda local**, Windows, Python 3.11+, sem auth/deploy.
- **Camada canônica é classe C** e publicação para o Comitê é **classe D** (`AGENTS.md §2`).
- **Escopo fechado nos blocos A/B/C do e-mail.** Item fora disso → pausa e registro, não implementação.
- Teva, FundsExplorer, Fundamentus e similares **sem licença comercial explícita** → fonte de validação /
  terciária, sem redistribuição.

### Premissas

As 15 premissas que substituíram respostas humanas estão rastreadas uma a uma na **§13.1** (P-01 a P-15), com
a fonte de cada uma e o impacto caso esteja errada. Duas premissas adicionais de ambiente: `[PREMISSA]` as
fontes públicas gratuitas usadas (BCB, IBGE, ANBIMA S3, API B3, Tesouro, MSCI, Yahoo) seguem acessíveis e
estáveis durante os 3 dias críticos; e o ambiente de execução tem conectividade com todas elas — **exceto o
FRED, que exige teste prévio** (R-06, G-06).

---

## 9. Dependências externas

| Dependência | Tipo | Criticidade | Fallback |
|---|---|---|---|
| BCB SGS (REST, sem auth) | API pública | **Alta** | Ipeadata OData4 · `python-bcb` |
| BCB Olinda / Expectativas (OData v4) | API pública | Alta | `python-bcb` · Ipeadata `BM12_IPCAEXP1212` |
| IBGE SIDRA / servicodados | API pública | Alta | SGS 22109 (PIB) e 433/13522 (IPCA) como espelhos |
| Bucket S3 público da ANBIMA (índices IMA) | Arquivo HTTP | **Alta** (único caminho grátis com histórico) | SGS 12461-12469 até 22/05/2023 (IRF-M 1 e 1+ sem substituto) |
| API interna da B3 `indexStatisticsProxy` | Endpoint não documentado | **Alta** | `GetDownloadPortfolioDay` · lib `mercados` · Ipeadata (só IBOV) |
| Tesouro Transparente CKAN | Arquivo HTTP (14,6 MB) | **Alta** (base da curva) | ANBIMA `ms*.txt` (só ~20 d.u.) · `pyield` |
| ANBIMA mercado secundário + Curva Zero | Arquivo/POST, janela rolante ~20 d.u. | Média (só trilho incremental) | — |
| MSCI `app2.msci.com` | Endpoint não documentado | Média | ETFs `ACWI` (2008+) / `URTH` (2012+) |
| Yahoo Finance chart v8 | API não oficial | Média | MSCI · FRED (se acessível) |
| FRED | API pública | Média | **Yahoo + BCB PTAX + MSCI cobrem quase tudo** |
| Teva Indices (GCS público) | Terceiro privado, sem licença explícita | Baixa (RF-014 é `should`) | Construção própria COTAHIST + CVM |
| Calendário de feriados ANBIMA | Arquivo HTTP | Média | lib `bizdays` |
| Libs: `python-bcb`, `pyield`, `sidrapy`, `yfinance`, `bizdays`, pandas/pyarrow, pydantic, pandera | PyPI | Média | chamadas HTTP diretas (todas as rotas foram testadas sem lib). ⚠️ `pyield` 0.59 exige Python ≥ 3.12 e polars — **fixar versão ou dispensar** |

---

## 10. Jornadas de alto nível

**J1 — Edu reconstrói o dataset (operação normal).** (1) um comando no terminal; (2) download do bruto com
cache condicional para `data/raw/<fonte>/`; (3) cada extrator tipa, valida contra pandera e grava em
`data/processed/`; (4) a camada canônica alinha ao último dia útil do trimestre e calcula retornos
geométricos; (5) regimes V1/V2/V3 classificados; (6) notebook gera métricas e figuras; (7) saída com nº de
linhas, min/max de data, % de nulos por coluna crítica e hash. **"Aha":** o dataset inteiro sai de uma linha
de comando, com a procedência de cada número.

**J2 — Alexandre modela a estratégia.** (1) recebe o pacote (Parquet + CSV/XLSX + figuras + limitações);
(2) lê no heatmap, por regime, qual classe bateu o CDI e por quanto, com `n` em cada célula; (3) consulta
"regime atual → ranking" e os 8 trimestres mais parecidos; (4) checa a concordância entre as três lentes;
(5) usa `SP500_BRL`/`USD_BRL` por regime e a regra de risk-off para dimensionar o internacional.
**"Aha":** "o trimestre atual se parece com 4T2016 e 1T2017 — e nos trimestres seguintes a esses, X ganhou."

**J3 — Fonte fora do ar ou série incompleta (exceção).** (1) extrator recebe HTTP 200 com corpo de erro,
resposta vazia ou série que não cobre 2006; (2) valida o shape e **falha ruidosamente** — nunca preenche;
(3) havendo fallback mapeado, usa e registra em `DECISIONS_LOG`; (4) não havendo, retorna
`BLOQUEADO — FONTE INDISPONÍVEL`, entra no `TODO.md §4` e segue para outra série; (5) a janela real aparece
no output e no rodapé das figuras.

**J4 — Publicação para o Comitê (classe D).** (1) dataset congelado com versão + hash; (2) revisão humana do
número pelo Edu, com 3 valores conferidos por série; (3) substituições de fonte comunicadas ao Alexandre;
(4) linha em `docs/wiki/log.md` e rollback em `docs/plans/infra-ops.md`; (5) envio.

---

## 11. Regras de negócio

- **RN-01** Trimestre = último dia útil de mar/jun/set/dez (calendário B3/ANBIMA); ativo que não negociou:
  forward-fill de até 5 d.u., acima disso `NULL` registrado (RF-023).
- **RN-02** Excesso sobre CDI e retorno real **sempre** por razão `(1+r)/(1+b)−1`; métrica primária de
  comparação entre épocas é o **excesso sobre CDI**, com o nominal como coluna informativa (RF-024).
- **RN-03** Regime de T usa apenas informação conhecida até o último DU de T (RF-025).
- **RN-04** `n` em **toda** célula de **toda** tabela: `n < 8` → alerta; `n < 5` → conclusão suprimida (RF-040).
- **RN-05** Série que não cobre a janela não é completada — a janela real é declarada (RF-019).
- **RN-06** Especificação de regime congelada em ADR antes de olhar os retornos; mudança posterior gera V1.1
  e as duas versões são reportadas (RF-031).
- **RN-07** Substituição de fonte exige registro em `DECISIONS_LOG` **e** comunicação ao Alexandre (RF-045/052).
- **RN-08** Misturar retorno total doméstico com retorno de preço internacional é proibido (viés ~2 pp/ano);
  índice não é ativo investível sem fricção — não reportar Sharpe como implementável.

---

## 12. Riscos priorizados (os 8 mais relevantes)

Lista completa: 22 riscos de extração em `docs/research/fontes-de-dados.md` (R1–R22) e 5 armadilhas
metodológicas em `docs/research/metodologia-regimes-macro.md §5`.

| # | Risco | Prob. × Impacto | Mitigação |
|---|---|---|---|
| R-01 | **Look-ahead bias** — PIB é revisado anualmente e tem ~60 dias de defasagem; IBC-Br ~45 dias. A série de hoje para 2008 não é a que o gestor via em 2008 | Alta × Alto | Campo `vintage` desde o dia 1; regra anti-look-ahead (RF-025) e **reportar o % de trimestres que trocam de regime**; se > 25%, dizer ao Comitê que o modelo não é operacional |
| R-02 | **n pequeno** — 83 trimestres / 4 regimes ≈ 20 por célula; erro-padrão da média ~2,7 pp/tri com σ=12% → diferenças < ~5 pp não se distinguem de ruído | Alta × Alto | V1 como lente principal (não V2 com 12 estados); `n` em toda célula; alerta < 8 e supressão < 5; reportar erro-padrão (RF-040) |
| R-03 | **Quebra estrutural** 2006-2008 vs pós-2016 (Selic 19% → 2% → dois dígitos; teto de gastos, autonomia do BCB, novo arcabouço) torna retorno nominal incomparável | Alta × Alto | Excesso sobre CDI e retorno real como métricas primárias; preferir juro real ex-ante e ΔSelic ao nível da Selic; variante **V3-pos2016** como robustez |
| R-04 | **Falha silenciosa de extração** — SGS devolve corpo de erro com **HTTP 200** (janela de 10 anos em séries diárias); Olinda com `$top=20000` trunca sem `nextLink`; Yahoo `range=max` trunca mensais; `fredgraph.csv` sem `cosd` trunca; Ipeadata **ignora** `$filter`/`$top`/`$orderby` | Alta × Alto | Validar shape e chave `error` antes do parse; fatiar séries diárias em ≤ 10 anos; omitir `$top` ou paginar com `$skip`; `period1/period2` no Yahoo; **assert de contagem mínima** por série |
| R-05 | **Janela rolante que apaga o passado e descontinuações** — ANBIMA `ms*.txt` e Curva Zero: ~20 d.u.; FRED `SP500`/`DJIA`: 10 anos; ICE BofA: 3 anos; SGS swaps mortos em set/2019; SGS IMA em 22/05/2023; EMBI+ em 30/07/2024; `DTWEXM` em 2019 | Alta × Alto | Nunca tratar fonte de janela rolante como backfill; **ligar o job diário de arquivamento hoje** (RF-010); monitorar última observação e alertar quando envelhecer |
| R-06 | **Endpoints não documentados e anti-bot** — B3 `indexStatisticsProxy`, MSCI `app2.msci.com` e o S3 da ANBIMA podem mudar sem aviso; Yahoo sem User-Agent → 429; CKAN do BCB sem UA → erro; **`fred.stlouisfed.org` ficou inacessível na máquina de pesquisa** (timeout + ConnectionReset) | Média × Alto | Testes de contrato com valor-canário no CI (RF-050); UA de browser em todas as requisições; **testar conectividade ao FRED antes de depender dele**, com Yahoo + MSCI + PTAX como plano B já mapeado |
| R-07 | **Unidade, escala e formato mentirosos** — `.xls` da ANBIMA é XLSX e o do `CZ-down.asp` é HTML; encodings latin-1 vs UTF-8; `ms{AAMMDD}` (não `ddmmaa`); PTAX Olinda em MM-DD-YYYY; separador de milhar inconsistente; rótulos `IMA-B` → `IMA - B`; códigos `IEEX` (não `IEE`) e `IFIL` (não `IFIXL`); série 12 do CDI é **percentual**, não fator | Alta × Médio | Normalizador único de número pt-BR; checagem de magic bytes; encoding declarado por leitor; mapa explícito de códigos; testes com datas-armadilha (01/02 vs 02/01); teste que reproduz CDI 2006 = 15,0271% |
| R-08 | **Overfitting e confusão descritivo × preditivo** — ajustar k, limiar de ΔSelic ou número de regimes depois de ver o heatmap; o Comitê lê "como performou" como "quanto vai render" | Média × Alto | Congelar a especificação em ADR antes de rodar (RF-031); nenhum backtest nesta fase (D11); página de limitações obrigatória (RF-042); linguagem descritiva em todo output |

**Riscos de prazo** (§7 da metodologia): ETTJ ANBIMA indisponível → fallback Tesouro Direto já definido;
Focus por data de coleta demorado → a V1 do pacote mínimo **não depende do Focus**; setoriais com histórico
curto → aceitar linhas incompletas com `n` por linha; FII segmentado → declarar fora do pacote mínimo.

---

## 13. Premissas assumidas e decisões pendentes para Edu/Alexandre

### 13.1 Premissas que substituíram respostas humanas

| # | Premissa adotada | Fonte da premissa | Se estiver errada |
|---|---|---|---|
| P-01 | Entregável de produto da v1 = **pacote mínimo** da §7 da metodologia; pacote estendido = fase 2 | prazo de 3 dias úteis | reescalar escopo da v1 |
| P-02 | Alexandre consome dataset + figuras; **não** roda o pipeline | e-mail ("conseguirei modelar a estratégia") | adicionar requisito de usabilidade/CLI |
| P-03 | Bloco C1 = `SP500_BRL`, `USD_BRL`, `GOLD_BRL`, `UST10_BRL`, MSCI ACWI em BRL | §4 da metodologia | trocar o universo internacional |
| P-04 | "Tamanho da alocação internacional" é entregue como **faixa estrutural + banda tática por regime** | §4.3 da metodologia (n≈20 não sustenta ponto) | ver D6 |
| P-05 | Trimestre = último dia útil de mar/jun/set/dez; janela = 83 trimestres (1T2006→3T2026) | §2 da metodologia + `CLAUDE.md` | reconstruir alinhamento (classe C) |
| P-06 | Métrica primária = **excesso sobre CDI** | D5 | refazer heatmap |
| P-07 | V1 = IBC-Br gap × aceleração do IPCA 12m | D2 + D3 | reclassificar os 83 trimestres |
| P-08 | V3 com k=8, Mahalanobis + shrinkage | D9 | recalcular vizinhos |
| P-09 | Alerta `n < 8`, supressão `n < 5` | D10 | ajustar apresentação |
| P-10 | Inclinação da curva via **Tesouro Direto interpolado** (não ANBIMA ETTJ) | L4 + A5.4 da pesquisa | ver L4 |
| P-11 | Segmentação de FII **best-effort** via Teva (2019+) | D12 + L2 | ver L2 |
| P-12 | Entrega em Parquet + CSV/XLSX + figuras + notebook; sem interface | não especificado no e-mail | ajustar RF-043 |
| P-13 | Heatmap pronto em **2026-10-13** para revisão do Edu | prazo do Comitê | antecipar/atrasar o corte |
| P-14 | v1 **reporta** a divergência look-ahead; dupla materialização `asof`/`revised` é fase 2 | D4 | ver D4 |
| P-15 | Nenhuma fonte paga; ANBIMA Feed fora | restrição de orçamento assumida | ver L4 |

### 13.2 Decisões que **BLOQUEIAM implementação** (precisam de resposta antes de codar/rodar)

| # | Decisão | Opções | Recomendação da pesquisa | Por que bloqueia |
|---|---|---|---|---|
| **D1** | Qual lente é a **oficial** do Comitê | V1 / V2 / V3 / as três | **V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário** | define o que o notebook entrega e o que vai ao slide; precisa estar congelado em ADR **antes** de rodar (RF-031) |
| **D3** | Eixo inflação da V1 | nível vs. meta / **aceleração (Δ12m)** | **aceleração** | muda o rótulo dos 83 trimestres; reclassificar depois invalida todo o heatmap |
| **D5** | Métrica primária do heatmap | nominal / **excesso CDI** / real | **excesso sobre CDI** | é a coluna do entregável visual central (RF-033) |
| **D6** | Internacional: estrutural, tático ou híbrido | piso fixo / 100% por regime / **piso + banda** | **piso 16-20% + banda tática 15-35% por regime** | é a resposta ao item C1; sem ela não se sabe o que RF-038/RF-039 devem entregar |
| **D12** | Setoriais B3 e FII segmentado no pacote mínimo | completo / **best-effort** / fora | **best-effort, com `n` e `data_inicio` visíveis** | define quantos extratores entram no caminho crítico de 3 dias |
| **L1** | IFIX só existe de 2011 em diante (metade da janela) | janela própria 2011-2026 / proxy IMOB / não entregar FII | **janela própria 2011-2026 + IMOB (2008+) como proxy imperfeito; não reconstruir IFIX sintético** | muda o desenho do painel (não balanceado) e o que se pode afirmar sobre FII |
| **L2** | Segmentação de FII (Tijolo/Papel/Logística/Shoppings) só desde 2019, via **provedor privado sem licença explícita** | Teva 2019+ / construção própria desde 2016 / fora | **Teva para dispersão setorial, declarando que cobre ~2 ciclos macro** | decisão de uso de terceiro sem licença comercial + define RF-014 |
| **L4** | ETTJ oficial da ANBIMA com 20 anos exige **contratar o ANBIMA Feed** (≈R$ 686–8.238/mês) | contratar / usar inclinação via Tesouro Direto | **Tesouro Direto — tecnicamente defensável sem comprar o Feed** | decisão de custo que altera a fonte de A6; o e-mail pedia ANBIMA explicitamente |

### 13.3 Decisões que **podem ser tomadas durante a execução**

| # | Decisão | Recomendação adotada por padrão |
|---|---|---|
| D2 | Eixo crescimento: desvio da tendência (barato) × surpresa vs. Focus (correto) | tendência na v1; Focus na fase 2 |
| D4 | Respeitar defasagem de divulgação já na V1 | v1 reporta a divergência; dupla materialização na fase 2 |
| D7 | Dólar hedgeado vs. sem hedge | ambos — a diferença (XP ~2,5-7% hedgeado × FGV 16-35% cambial) é a essência da discussão |
| D8 | Janela 2006-2026 inteira ou só pós-2016 | tudo, com `V3-pos2016` como robustez |
| D9 | k da V3 | 8, com 5 e 12 como sensibilidade |
| D10 | Limiar de supressão por n baixo | alerta `n<8`, supressão `n<5` |
| D11 | Backtest de estratégia na quarta | **não** — entregável é descritivo (já refletido em §4.4) |
| L3 | ICON (2007+) e IMOB (2008+) | janela própria com nota de rodapé, sem forçar painel balanceado |
| L5 | Ponta longa **nominal** da curva não existe antes de ~2010 | inclinação **real** (NTN-B) como variável principal; 5 anos como ponta longa nominal |
| L6 | Taxas indicativas ANBIMA e Curva Zero têm janela rolante de ~20 d.u. | ligar o job diário **hoje** (RF-010); cada dia sem isso é série proprietária perdida |
| L7 | SGS de swap DI×pré morto desde set/2019 (rota sugerida no e-mail) | substituído por Tesouro Direto; registrar em `DECISIONS_LOG` e avisar o Alexandre |
| L8 | CDS Brasil / EMBI+ sem fonte gratuita com 20 anos (EMBI+ morre em 30/07/2024) | fora do pacote mínimo; fase 2 com cupom cambial DDI/FRC via `pyield` ou splice EMBI+ × ICE BofA LatAm |
| L9 | Desemprego sem série única 2006-2026 (PME até 02/2016; PNADC desde 2012) | fora do escopo mínimo; se entrar, emendar com calibração na sobreposição |
| L10 | Dívida bruta (SGS 13762) começa em 2008 | usar DLSP (SGS 4513), que cobre 2006; código da série antiga de DBGG **a confirmar** |
| L11 | S&P 500 no FRED só tem 10 anos | resolvido: Yahoo `^GSPC` / MSCI USA — **não é lacuna real** |
| L12 | "ANBIMA DataFit" citado no e-mail **não existe** | existem ANBIMA Data (grátis) e ANBIMA Feed (pago); o S3 resolve os índices. Apenas comunicar ao Alexandre |
| L13 | IPCA por grupos sem série única 2006-2026 (SIDRA 1419 e 7060; 2006-2011 **a confirmar**) | fora do escopo mínimo |

### 13.4 Gaps — o que ainda não sabemos

- **G-01** Quais setoriais da B3 além de IBOV/IFIX são de **retorno total** — confirmar índice por índice antes de fechar o dataset. **A confirmar.**
- **G-02** Série histórica de **metas de inflação** do CMN e data exata da meta contínua (se a feature "IPCA − meta" entrar). **A confirmar.**
- **G-03** Fonte gratuita de **ouro spot** com 20 anos (IDs testados no FRED deram 404). **A confirmar.**
- **G-04** Rótulo exato do indicador `PIB Total` no Focus (enumerar `Indicador` baixando um ano). **A confirmar.**
- **G-05** Convenção de `baseCalculo` no Olinda (0 = 30 dias, 1 = 5 d.u., `[NÃO VERIFICADO]`); filtrar por um dos dois evita duplicar linha. **A confirmar.**
- **G-06** Conectividade do ambiente do Edu com o FRED (R-06). **A testar antes de codar RF-017.**
- **G-07** Código SGS da série antiga de DBGG para 2006-2007 (L10). **A confirmar.**

### 13.5 Hipóteses críticas

- **H-01** Quatro quadrantes com ~20 trimestres cada bastam para o Comitê decidir. Validação: concordância entre as três lentes (RF-037) — se divergirem muito, a hipótese cai e **isso** é a mensagem.
- **H-02** A classificação V1 "faz sentido" para quem viveu o período. Validação: timeline de regimes (RF-035).
- **H-03** O regime defasado (operacional) e o revisado classificam quase o mesmo. Validação: RF-025 — se > 25% dos trimestres trocam, o modelo não é operacionalizável.
- **H-04** USD/internacional em BRL é o único diversificador genuíno de carteira brasileira (FGVcef, 21.000 janelas 2005-2026). Validação: `corr(USDBRL, IBOV)` por regime e nos 10 piores trimestres (RF-038).

---

## 14. Aprovação

- [x] Problema ancorado no e-mail (não inferido); personas e anti-persona definidas
- [x] **52 RFs verificáveis**, cada um citando o item do e-mail (A1–A7, B1–B5, C1) + fonte primária e fallback
- [x] 10 RNFs; fora de escopo explícito; métricas mensuráveis com prazo; 8 riscos priorizados com mitigação
- [x] 15 premissas rastreadas, 7 gaps, 4 hipóteses, 8 decisões bloqueantes + 17 não bloqueantes
- [ ] **PRD aprovado por Eduardo (Edu)** — pendente
- [ ] **8 decisões bloqueantes (D1, D3, D5, D6, D12, L1, L2, L4) respondidas por Edu/Alexandre** — pendente

> **Atenção:** este PRD foi gerado em modo autônomo. Ele **não é propriedade do agente**: nenhuma seção pode
> ser alterada por agente após a aprovação sem nova autorização humana (`AGENTS.md §8`).

---

*Próximo passo: responder as 8 decisões bloqueantes da §13.2, aprovar este PRD e rodar `/SDD-avancado` para
gerar `docs/specs/SPEC.md` + Anti-SPEC + contratos (Pydantic/pandera) + TODO com classificação A/B/C/D.*
