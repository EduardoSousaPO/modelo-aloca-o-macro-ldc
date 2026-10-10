# Metodologia de regimes macro — desenho para o modelo de alocação LDC

> **Status:** pesquisa concluída em 2026-10-10. Documento de desenho metodológico, insumo para PRD e SPEC.
> **Escopo de origem:** `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` (não alterar). **Prazo:** Comitê de Alocação 2026-10-14 (3 dias úteis).
> **Convenção de confiança:** `[V]` verificado nesta pesquisa com URL acessada · `[G]` conhecimento geral, **precisa checagem antes de virar número em slide** · `[A]` suposição/decisão de desenho nossa.

## 0. Resumo executivo

1. **Não tente achar "o" regime verdadeiro.** Em 83 trimestres não há graus de liberdade. Entregue **três lentes paralelas** (V1 quadrantes, V2 quadrantes × ciclo Selic, V3 vizinhos mais próximos) e mostre onde concordam. Concordância entre lentes é o sinal real.
2. **V1 é o produto principal** do Comitê: 4 quadrantes crescimento × inflação, replicável em planilha, auditável, ~20 trimestres por célula.
3. **V3 (similaridade) responde literalmente ao pedido do Alexandre** — "como cada classe performou em momentos semelhantes". É o diferencial e é barato.
4. **V2 é a ponte para a decisão tática** (ciclo Selic é o que o Comitê debate), mas sofre de n pequeno. Corte secundário, nunca célula única de decisão.
5. **Internacional entra como classe em BRL dentro do mesmo arcabouço**, não como anexo. "Quanto no exterior" vira: em quais regimes S&P 500 / Treasury / ouro em BRL ganham do CDI e do IBOV, e qual a variância mínima naquele regime.
6. **Armazene mensal/diário, agregue para trimestral.** Trimestral como dado primário é erro irreversível.
7. **Trate `vintage` desde o dia 1.** Sem esse campo, o look-ahead bias fica invisível e indefensável diante do Comitê.
8. **O entregável é descritivo ("como performou"), não preditivo ("quanto renderia").** Confundir os dois é o maior risco reputacional do projeto.

---

## 1. Frameworks de regimes macro usados por alocadores

### 1.1 Quadrantes crescimento × inflação (Bridgewater / All Weather)
Bridgewater organiza o mundo por **quatro ambientes**: inflação subindo, inflação caindo, crescimento subindo, crescimento caindo — sempre **relativo às expectativas embutidas nos preços**, não ao nível absoluto. A All Weather aloca risco igual aos quatro ambientes em vez de prever qual virá. `[V]`
- **Variáveis:** proxy de crescimento (PIB real, IBC-Br), proxy de inflação (IPCA), e — na versão fiel — proxy de expectativa (Focus, implícita NTN-B vs pré).
- **Classificação:** dois sinais binários (acima/abaixo da tendência ou da expectativa) → 4 células.
- **Prós:** simples, interpretável, ~20 obs por célula; mapeamento direto para classes (ações ↔ crescimento alto; pré ↔ inflação caindo; IPCA+/commodities ↔ inflação subindo) `[V]`.
- **Contras:** binarizar perde intensidade; "relativo à expectativa" é mais difícil de operacionalizar que "relativo à tendência" e **muda o resultado**; não captura crise de liquidez/risco-país, que no Brasil é eixo próprio.

### 1.2 Investment Clock (Merrill Lynch / Trevor Greetham)
Mesmos dois eixos, nomeados como **fases sequenciais**, cada uma definida pela *direção* de crescimento e inflação **relativa às suas tendências**. `[V]`

| Fase | Crescimento | Inflação | Leitura clássica de ativos `[V]` |
|---|---|---|---|
| Reflation | abaixo da tendência | caindo | Bonds/pré longo; ações em bear |
| Recovery | acima da tendência | ainda baixa | "Goldilocks" — ações é a melhor classe |
| Overheat | acima, desacelerando | subindo | Commodities, inflação-linkados |
| Stagflation | abaixo da tendência | alta | Caixa, ouro; pior fase para ações |

- **Prós:** narrativa que gestor entende sem treinamento; a ideia de *ciclo* permite falar de "próxima fase".
- **Contras:** a sequência é empiricamente frouxa (fases pulam etapas); no Brasil o ciclo é frequentemente interrompido por choque cambial/fiscal exógeno.

### 1.3 Regimes por ciclo de política monetária (ciclo Selic)
Classificar o trimestre pelo que o Copom faz: **cortando / subindo / parado**, eventualmente cruzado com juro real (Selic − Focus IPCA 12m).
- **Variáveis:** Selic Over (SGS 11) ou Selic meta (SGS 432); IPCA 12m (SGS 433); Focus IPCA 12m.
- **Classificação:** Δ Selic meta no trimestre < −0,25 pp = cortando; > +0,25 pp = subindo; else parada. Melhor para alocação: usar a **direção do ciclo já iniciado**, não o Δ isolado — pausa dentro de ciclo de corte é "cortando" `[A]`.
- **Prós:** é a linguagem real do Comitê brasileiro; driver dominante de IRF-M, IMA-B e small caps. A XP publica leitura neste eixo — "inflação baixa, juros caindo" como o melhor regime histórico para risco no Brasil, com risco de migração para "inflação baixa, juros subindo" ou "inflação alta, juros caindo" `[V-parcial — via busca; a página bloqueia fetch (HTTP 403), confirmar no navegador]`.
- **Contras:** **endógeno** — o Copom reage a crescimento e inflação, então o regime Selic é em parte *função* de V1 (não é informação nova); **quebra estrutural severa** — ciclos de 2006-2008 com Selic a 13-19% não são comparáveis a 2019-2020 com Selic a 2%.

### 1.4 Regimes por inclinação da curva
A inclinação resume simultaneamente expectativa de juros, prêmio de risco e stress fiscal. É um dos poucos sinais verdadeiramente *forward-looking* e diário.
- **Variáveis:** DI futuro (B3) ou ETTJ ANBIMA. Definição sugerida: **DI 5 anos − DI 3 meses**. A literatura brasileira usa exatamente "taxa de cinco anos menos taxa de um mês" em regressões contra índices de atividade `[V]`.
- **Nota crítica Brasil:** a curva embute prêmio de risco fiscal grande e **variante no tempo** → inclinação ≠ só expectativa de juros. Decompor em expectativa + prêmio exige modelo afim gaussiano (Insper/BCB fizeram com DI da B3, jan/2005–out/2016) `[V]`. Para nosso prazo: **usar inclinação crua e declarar a limitação** `[A]`.
- **Prós:** diário, sem revisão, sem defasagem → **zero look-ahead bias**. Complemento ideal aos dados macro atrasados.
- **Contras:** interpretação ambígua — curva íngreme = recuperação esperada *ou* prêmio fiscal explodindo (2015 e 2021 confundem).

### 1.5 Regimes por surpresa (realizado vs expectativa Focus)
O que move preço não é o nível, é o **erro vs o esperado**. Índices de surpresa (Citi CESI) são **desvios-padrão históricos ponderados das surpresas** (realizado − mediana de pesquisa), janela móvel de 3 meses, com decaimento temporal `[V]`.
Versão brasileira factível, por trimestre: `surpresa_ipca = IPCA 12m realizado (fim de T) − Focus IPCA 12m (coleta do início de T)`; idem para PIB e Selic; z-score de cada; o sinal define o regime.
- **Prós:** conceitualmente o mais correto (é a definição Bridgewater de "relativo à expectativa"); **o Focus é o dado mais honesto contra look-ahead** — a mediana da semana X é conhecida na semana X `[V]`; série longa via API Olinda.
- **Contras:** montar o histórico Focus por data de coleta dá trabalho (é um vintage por semana); o horizonte das expectativas muda ao longo da série. A AQR usa três métricas complementares — performance sob inflação inesperada, performance em regimes de inflação subindo/caindo, e correlação com inflação futura — justamente porque "inflação inesperada" é sensível à definição `[V]`.

### 1.6 Abordagens estatísticas
**(a) HMM / Markov-switching.** Hamilton (1989) introduziu o paradigma de *Markov switching*; o achado central da literatura é que permitir mudança de regime melhora materialmente o resultado de carteira vs média-variância estática `[V]`. **Prós:** dá **probabilidade de regime** (não rótulo duro) e matriz de transição → permite falar de "chance de mudar no próximo trimestre". **Contras:** com 83 obs e ~5 variáveis, 3+ estados é overfitting quase garantido; estados saem **sem rótulo econômico**; sensível a inicialização. **Veredito: fora dos 3 dias; fase 2 com dados mensais (240 obs)** `[A]`.

**(b) k-means / clustering.** A **Verdad** aplica **Gaussian Mixture Model** a dados macro diários de 1962-2024 e encontra **4 regimes** — Growth, Inflation, Precarious, Crisis — usando crescimento do PIB, inflação, inclinação da curva, volatilidade, spreads de high yield e correlação ação-bond. Retornos anualizados 1970-2024: Growth → ações, crédito, petróleo; Inflation → petróleo e S&P; Precarious → crédito e ouro; Crisis → Treasuries e ouro `[V]`. Paper acadêmico de 2026 usa **127 variáveis FRED-MD → 61 componentes → k-means em dois estágios (ℓ₂ k=2 isolando crise; cosseno k=5) = 6 regimes**, janela móvel de 48 meses e backtest walk-forward; a conclusão mais útil para nós: **"especificações mais simples capturam a dinâmica fundamental melhor"** e long-only bateu long-short consistentemente `[V]`. **Contras:** rótulos exigem interpretação humana post-hoc; resultado muda com k, variáveis e padronização — e o Comitê vai perguntar "por que 4 e não 5?"; com quebra estrutural, os clusters tendem a virar "antes de 2016" vs "depois de 2016" (exatamente nosso caso). **Veredito: validação cruzada da V1, não entregável principal** `[A]`.

**(c) Nearest-neighbors / "momentos semelhantes".** É literalmente o pedido do e-mail. A Man Group chama de **MacroScope**: arcabouço sistemático que **identifica períodos históricos similares ao atual** e toma posições em indústrias e fatores que performaram bem **depois de ambientes macro similares**, com abordagem multivariada por instrumentos negociáveis, evitando redundância entre fatores `[V]`. Método: vetor padronizado por trimestre → distância ao trimestre atual → k vizinhos → olhar o retorno **dos trimestres seguintes** aos vizinhos. **Mahalanobis** é preferível a Euclidiana porque captura correlação entre variáveis `[V]` — relevante: Selic, IPCA e câmbio são correlacionados no Brasil. **Prós:** sem treino, um único hiperparâmetro (k), **não binariza nada**, narrativa poderosa ("o trimestre atual se parece com 4T2016, 1T2017, 3T2019…"), auditável linha por linha. **Contras:** k pequeno = ruído, k grande = dilui; a covariância de Mahalanobis em 83 obs é instável (regra prática: ≤ 6 variáveis); vizinho pode ser de regime estrutural diferente — mitigar com variante restrita a pós-2016.

### 1.7 Adaptação ao Brasil — o que muda

| Eixo global | Adaptação Brasil | Por quê |
|---|---|---|
| Crescimento | IBC-Br (mensal, ~45 dias de defasagem) + PIB IBGE trimestral (~60 dias) `[V]` | IBC-Br é prévia e chega antes; PIB é a verdade, mas atrasada e revisada |
| Inflação | IPCA 12m (SGS 433) **e** IPCA − centro da meta | Regime de metas: importa o desvio da meta, não o nível |
| Juros | Selic Over (SGS 11) + **juro real ex-ante** (pré 12m − Focus IPCA 12m) | Juro real ex-ante é o driver de IMA-B e bolsa |
| Curva | DI 5a − DI 3m, via ETTJ ANBIMA ou DI futuro | Carrega prêmio fiscal, não só expectativa `[V]` |
| Câmbio | USDBRL variação trimestral e 12m | No Brasil o câmbio é eixo próprio, não variável derivada |
| Termos de troca | Índice de termos de troca (Funcex/BCB) ou proxy CRB / minério+soja+petróleo | Define o ciclo de IMAT e do real |
| Risco-país | EMBI+ Brasil (JPM) ou CDS 5 anos | Captura "Crisis/Precarious" à la Verdad, que quadrantes não captam `[V]` |

> **Decisão de desenho `[A]`:** incluir **câmbio** e **risco-país** como *eixos de contexto* (reportados ao lado do regime) e **não** como definidores do regime na V1 — senão o número de células explode.

---

## 2. Definição operacional recomendada

### Princípios comuns
1. **Universo:** 1T2006 → 3T2026 ≈ **83 trimestres**.
2. **Calendário:** trimestre fecha no **último dia útil** de mar/jun/set/dez. Retorno de T = `P(último DU de T)/P(último DU de T−1) − 1`.
3. **Regra anti-look-ahead (crítica):** o regime de T usa apenas dados **conhecidos até o último dia útil de T**. Como IBC-Br tem ~45 dias de defasagem e o PIB ~60 `[V]`:
   - PIB/IBC-Br para classificar T → referentes a **T−1** (ou meses de T já divulgados).
   - IPCA: divulgado em meados de M+1 → o mais recente conhecido em T é o do **penúltimo mês de T**.
   - Focus, Selic, DI, câmbio: **sem defasagem**, usar à vontade.
   - **Variante "oracle"** (revisado, sem defasagem) calculada em paralelo, com a **diferença reportada**. Se divergirem muito, o modelo não é operacionalizável.
4. **Padronização:** z-score com média/desvio da **amostra completa** na versão descritiva (é o que o Comitê quer: "onde estamos no histórico") e **expanding window** em qualquer versão que vire backtest. Nunca misturar no mesmo gráfico.

### V1 — Quadrantes crescimento × inflação (ENTREGÁVEL PRINCIPAL)

| Componente | Especificação |
|---|---|
| Eixo crescimento | `g_T` = IBC-Br var. a/a (média do trimestre, dessaz.) **menos** tendência = média móvel 20 trimestres de si mesma |
| Eixo inflação | `pi_T` = IPCA 12m no fim de T **menos** IPCA 12m em T−1 (aceleração) |
| Classificação | `CRESC = (g_T > 0)` × `INFL = (pi_T > 0)` → 4 quadrantes |
| Rótulos | `RECUPERACAO` (↑g,↓π) · `EXPANSAO_INFL` (↑g,↑π) · `ESTAGFLACAO` (↓g,↑π) · `DESACELERACAO` (↓g,↓π) |
| Dados | SGS 24364/24363 (IBC-Br dessaz.); SGS 433 (IPCA mensal) encadeado em 12m |
| Desempate | `g_T` ou `pi_T` exatamente 0: herda o sinal do trimestre anterior |
| n esperado | ~20 por quadrante — **aceitável** |

**V1b (mais fiel ao Bridgewater, opcional):** trocar "vs tendência" por "vs Focus": `g_T = PIB a/a realizado − Focus PIB mediana`, `pi_T = IPCA 12m realizado − Focus IPCA 12m (coleta do início de T)`. Conceitualmente mais correto `[V]`, mais caro (exige série Focus por data de coleta). **Fazer V1 primeiro; V1b se sobrar tempo** `[A]`.

### V2 — Quadrantes × ciclo Selic

| Componente | Especificação |
|---|---|
| Regime base | V1 (4 quadrantes) |
| Camada Selic | `Δ Selic meta no trimestre`: `< −0,25 pp` → `CORTE`; `> +0,25 pp` → `ALTA`; else `NEUTRO` |
| Refinamento `[A]` | Δ=0 após 2 trimestres de CORTE sem alta → classificar como `CORTE` (pausa dentro de ciclo) |
| Estados | 4 × 3 = 12 teóricos; na prática ~7-8 povoados |
| n esperado | **5-15 por estado — ALERTA de n pequeno em metade das células** |

**Uso recomendado:** **não** como célula de decisão. Reportar como **corte secundário** ("dentro de DESACELERACAO, os 6 trimestres com Selic em corte tiveram X; os 9 com Selic em alta, Y"), com `n` sempre visível. Avaliar também a versão de **2 estados** (`CORTE` vs `NAO_CORTE`), que dobra o n por célula.

### V3 — Vizinhos mais próximos ("momentos semelhantes") — DIFERENCIAL

| Componente | Especificação |
|---|---|
| Features (6) | `z1` IBC-Br a/a − tendência · `z2` IPCA 12m − centro da meta · `z3` juro real ex-ante (pré 12m − Focus IPCA 12m) · `z4` inclinação (DI 5a − DI 3m) · `z5` USDBRL var. 12m · `z6` termos de troca a/a (ou proxy CRB a/a) |
| Transformação | z-score de cada feature na amostra completa |
| Distância | **Mahalanobis** com covariância *shrinkage* (Ledoit-Wolf) — a covariância amostral em 83×6 é instável. Reportar **Euclidiana em paralelo** como sanity check |
| k | **k = 8** (≈10% da amostra), com k=5 e k=12 como sensibilidade |
| Exclusão | Excluir os 2 trimestres imediatamente anteriores ao atual (autocorrelação trivial) |
| Saída A | Tabela dos 8 trimestres mais parecidos, com distância e rótulo V1 de cada |
| Saída B | **Retorno médio de cada ativo nos trimestres SEGUINTES aos vizinhos** — é o que tem valor preditivo e é o que o MacroScope faz `[V]` |
| Variante | `V3-pos2016`: busca restrita a ≥ 1T2017, controlando a quebra estrutural de Selic |
| Desempate | Distâncias empatadas: prevalece o trimestre mais recente |

> **Por que V3 é o melhor custo-benefício:** sem treino, sem hiperparâmetro escondido, auditável na mão pelo Alexandre, e responde à pergunta do e-mail no mesmo vocabulário em que ela foi feita.

**Fora de escopo para 2026-10-14 `[A]`:** HMM/Markov-switching, GMM à la Verdad, qualquer otimização com backtest walk-forward. Registrar como backlog fase 2.

---

## 3. Métricas de desempenho por regime

Para cada `(regime, ativo)`, sobre os trimestres daquele regime:

| Métrica | Fórmula / observação |
|---|---|
| `n_obs` | nº de trimestres. **Flag `ALERTA_N_BAIXO` se n < 8; suprimir conclusão se n < 5** |
| `ret_medio` / `ret_mediana` | média aritmética e mediana dos retornos trimestrais. **Reportar as duas lado a lado** — divergência grande = outlier dominando |
| `ret_desvio` | desvio-padrão amostral dos retornos trimestrais |
| `hit_ratio` | % de trimestres com retorno > 0 |
| `excesso_cdi` | média de `(1+r_ativo)/(1+r_cdi) − 1` (geométrico, nunca subtração) |
| `hit_ratio_cdi` | % de trimestres em que bateu o CDI — **a métrica que o Comitê brasileiro de fato usa** |
| `ret_real` | média de `(1+r_ativo)/(1+ipca_T) − 1` |
| `sharpe_tri` | `(ret_medio − cdi_medio)/ret_desvio` trimestral; anualizar só por ×√4 e **dizendo que anualizou** |
| `drawdown_max` | max drawdown dentro dos trimestres contíguos do regime; para regimes não contíguos usar `pior_tri` (mínimo) — mais honesto |
| `pior_tri` / `melhor_tri` | valor e data |
| `beta_ibov` | opcional: beta vs IBOV no regime — mostra mudança de correlação por regime `[V — a Verdad explora exatamente correlação por fase do ciclo]` |

**Regras de apresentação (não negociáveis) `[A]`:** `n` aparece em **toda** célula de **toda** tabela, sem exceção; célula com `n < 8` recebe hachura/cinza no heatmap; nenhuma afirmação do tipo "X é o melhor em Y" com `n < 8` — usar "indicação preliminar, n=6".

**Nota de potência estatística:** com n=20 e desvio trimestral de 12% (típico de bolsa), o erro-padrão da média é **~2,7 pp por trimestre** — diferenças de retorno médio menores que ~5 pp trimestrais **não são distinguíveis de ruído**. Reportar erro-padrão ou intervalo de confiança `[A — cálculo nosso]`.

### Visualizações
- **(a) Heatmap regime × ativo.** Linhas = ~18 ativos (IBOV, IDIV, SMLL, INDX, ICON, IMAT, IEE, IMOB, IFNC, IFIX, IMA-B, IMA-B 5, IMA-B 5+, IRF-M, IRF-M 1, IRF-M 1+, CDI + internacionais em BRL). Colunas = regimes. Valor = **`excesso_cdi` médio trimestral** — melhor que retorno nominal porque neutraliza a mudança de patamar da Selic entre 2006 e 2026. Escala divergente centrada em 0, `n` anotado em cada célula.
- **(b) Tabela "regime atual → ranking".** Uma página: regime atual por V1, por V2 e os 8 vizinhos da V3; abaixo, ativos ordenados por `excesso_cdi` com `hit_ratio_cdi`, `n` e semáforo de confiança.
- **(c) Tabela de concordância entre lentes.** 1 linha por lente, coluna "top-3 ativos". Se as três concordam, essa é a recomendação. Se divergem, **isso** é a mensagem.
- **(d) Timeline de regimes.** Faixa colorida 2006→2026 com o regime V1, sobreposta a IBOV e Selic. Sanity check visual indispensável para o Comitê validar se a classificação "faz sentido".

---

## 4. Tamanho da alocação internacional

### 4.1 Abordagem recomendada: internacional como classe em BRL no mesmo arcabouço

| Ativo | Série em BRL |
|---|---|
| `SP500_BRL` | S&P 500 **total return** (ou IVVB11 a partir de 2014) × USDBRL |
| `SP500_HEDGE` | S&P 500 em USD + CDI − custo de hedge ≈ S&P 500 USD + CDI − Fed Funds `[A, aproximação]` |
| `UST10_BRL` | Treasury 10y total return index × USDBRL |
| `GOLD_BRL` | ouro spot USD × USDBRL |
| `USD_BRL` | USDBRL puro (caixa em dólar); versão com juros: `USDBRL × (1+SOFR)` |
| `MSCI_EM_BRL` | opcional |

Com isso, a leitura cai no mesmo heatmap: *em quais regimes o internacional em BRL bate CDI e IBOV, e por quanto.*

### 4.2 Papel do câmbio como hedge — evidência brasileira
- **FGVcef / Centro de Estudos em Finanças (Prof. William Eid Jr.)**, apresentado no Avenue Connection: **21.000 janelas móveis entre 2005 e 2026**; ativos domésticos (CDI, renda fixa, multimercado) correlacionam **~0,50 entre si** e **nenhum par é negativo** — **só o dólar funcionou como diversificação genuína** `[V]`.
- Mesmo estudo: **o CDI ganhou poder de compra em dólar em apenas 49,4% dos períodos**, contra **90,1% do S&P 500**; e o CDI teve **volatilidade maior em dólar** que a bolsa americana `[V]`.
- Piso de **16% a 18% no exterior** para neutralizar o impacto do câmbio sobre o padrão de consumo do brasileiro; faixa ótima **20%-35%** conforme fase da vida (mais na acumulação, menos no usufruto) `[V]`.
- Dos **R$ 19,4 trilhões** declarados no IR em 2024, só **6,3%** está no exterior; no núcleo (imóveis + aplicações + fundos) a parcela externa cai a **2,2%** `[V]`.
- Correlação **dólar comercial × Ibovespa de −0,76** em estudo acadêmico brasileiro `[V-parcial — reportado em busca, janela não confirmada; validar antes de citar]`.
- **XP:** exposição ideal a *global hedgeado* por perfil — conservador ~2,5%, moderado ~5%, sofisticado até 7% `[V-parcial — via busca]`. **Atenção:** isso é *global com hedge*, categoria diferente de exposição cambial, e por isso os números são muito menores que os 20-35% do FGV. **Essa distinção precisa estar explícita no material do Comitê.**
- **BTG (Portfolio Solutions):** adicionar ativos globais melhora a relação risco-retorno com praticamente a mesma volatilidade `[V-parcial]`. **Kinea:** nos fundos de renda fixa, **mais de 50% do risco** em mercados internacionais `[V-parcial]`.
- A citação de "~40% da carteira no exterior" vem de material de distribuidor — `[G]`, **não usar como âncora**.

### 4.3 Medidas quantitativas, em ordem de implementação
1. **Variância mínima por regime (recomendado).** Em cada regime, covariância dos retornos trimestrais em BRL de um conjunto **pequeno** (CDI, IMA-B, IBOV, IFIX, SP500_BRL) e min-variância **long-only com cap de 40% por ativo**. O peso de `SP500_BRL` é a resposta "quanto no exterior naquele regime". **Caveat obrigatório:** com n≈20 e 5 ativos a covariância é ruidosa — usar shrinkage (Ledoit-Wolf) e **reportar sensibilidade** `[A]`.
2. **Regra de "risk-off" (mais robusta e mais vendável).** `stress = 1` quando (inclinação cai > 1 d.p.) OU (EMBI sobe > 1 d.p.) OU (USDBRL sobe > 10% no trimestre). Medir o retorno de cada ativo nesses trimestres e **quanto de USD neutraliza a queda do IBOV**. Vira uma regra simples: "X% em dólar cobre Y% da queda esperada da renda variável doméstica".
3. **Correlação condicional.** Reportar `corr(USDBRL, IBOV)` por regime e, separadamente, nos 10 piores trimestres do IBOV. Se o hedge só funciona no stress (esperado), esse é o argumento central para dolarizar `[A]`.
4. **Fronteira eficiente por regime.** Só se sobrar tempo — é bonito e é o mais frágil estatisticamente.

> **Decisão humana (ver §8):** a recomendação final é **estrutural** (piso 16-20%, à la FGV) com **banda tática por regime** (ex.: 15%-35%), ou puramente tática derivada da otimização? **Recomendação: estrutural com banda tática** — a otimização em n≈20 não sustenta um número pontual `[A]`.

---

## 5. Armadilhas

### 5.1 Look-ahead bias

| Fonte | Problema | Mitigação |
|---|---|---|
| Revisões do PIB | Contas Nacionais Trimestrais são **revisadas uma vez por ano**, após as contas anuais `[V]`. A série de hoje para 2008 não é a que o gestor via em 2008 | Campo `vintage`; na V1 usar série atual mas **calcular e reportar** a variante defasada |
| Defasagem de divulgação | PIB trimestral ~**60 dias** após o fim do trimestre; IBC-Br ~**45 dias** após o mês de referência `[V]` | Regra do §2: classificar T com macro de T−1 |
| IPCA | Divulgado em meados do mês seguinte | Último IPCA conhecido em T = o do penúltimo mês de T |
| Focus | **É o dado "limpo"** — mediana da semana X conhecida na semana X `[V]` | Preferir Focus ao realizado sempre que possível |
| Preços de ativos | Sem defasagem | Livres |

> **Teste de sanidade obrigatório:** rodar V1 nas duas versões (revisado-sem-defasagem vs defasado) e reportar a **% de trimestres que trocam de regime**. Se > 25%, o modelo não é operacional — e isso precisa ser dito ao Comitê.

### 5.2 Survivorship e histórico de índices
- Os setoriais da B3 **não começam todos na mesma data** → a matriz regime × ativo terá **n diferente por linha**. Registrar `data_inicio` por série e exibi-la no rodapé do heatmap.
- O **IFIX** tem carteira revisada **a cada quatro meses**, ponderação por valor de mercado × free float e cap de 20% por fundo `[V]`; o mercado de FIIs em 2006-2010 era minúsculo. **Qualquer conclusão sobre IFIX pré-2012 é frágil.**
- Segmentações de FII (Tijolo/Papel/Logística/Shoppings) **não são índices oficiais da B3 com 20 anos** — dependem de provedor terceiro ou construção própria. Tratar como "best effort" e marcar no PRD `[A]`.
- Carteira teórica revisada significa que o índice **não é ativo investível com custo zero** — não reportar Sharpe como se fosse implementável sem fricção.

### 5.3 Quebra estrutural 2006-2008 vs pós-2016
A Selic foi de ~19% (2006) a 2% (2020) e voltou a dois dígitos. Consequências:
- **Retorno nominal não é comparável entre épocas** → métricas primárias são **excesso sobre CDI** e **retorno real**; nominal apenas como coluna informativa.
- "Nível de juros" como feature confunde época com regime → preferir **juro real ex-ante** e **Δ Selic** ao nível de Selic.
- Mudanças de arcabouço: tripé macro (2006-2014), nova matriz econômica (2012-2015), teto de gastos (2016), autonomia do BCB (2021), novo arcabouço fiscal (2023). Rodar **V3-pos2016** como variante e comparar.
- As metas de inflação mudaram de patamar e a meta passou a ser **contínua** `[G — confirmar data exata com o agente de dados]` → a feature "IPCA − meta" exige a **série de metas**, não uma constante.

### 5.4 n pequeno
83 trimestres / 4 regimes ≈ **20 por célula (OK-ish)**; / 8 estados ≈ **10 (ruim)**; / 12 estados ≈ **7 (inutilizável)**. Daí V1 ser a principal. Ver a nota de potência estatística em §3.

### 5.5 Overfitting
- **Fixar as regras antes de olhar os retornos.** Congelar a especificação de V1/V2/V3 em ADR e **não ajustar** depois de ver o heatmap. Se ajustar, registrar como V1.1 e **reportar as duas**.
- Não escolher k, número de clusters ou limiar de Δ Selic "porque o resultado fica melhor".
- Lembrar o achado do paper de TAA: **especificações simples capturaram a dinâmica melhor** `[V]`.
- **Nenhum backtest de estratégia nesta fase.** O entregável é descritivo.

### 5.6 Trimestral vs mensal/diário
**Recomendação firme:** armazenar na **granularidade nativa** (diário para preços/câmbio/DI, mensal para IPCA e IBC-Br, trimestral para PIB) e **agregar por view/função**. Razões: (a) permite migrar para regimes mensais (240 obs) na fase 2 sem recoletar; (b) permite mudar o calendário de agregação (trimestre civil vs 3 meses móveis) sem retrabalho; (c) drawdown intra-trimestre só é calculável com dado diário; (d) o alinhamento "último dia útil" exige o calendário diário de todo modo.

---

## 6. Desenho de dataset canônico

### 6.1 `raw_series` — tabela longa de séries brutas
```
raw_series(
  series_id TEXT NOT NULL,   -- 'BCB_SGS_433', 'ANBIMA_IMAB', 'B3_IFIX', 'FOCUS_IPCA_12M'
  date      DATE NOT NULL,   -- data de referência do dado
  value     REAL,            -- NULL permitido (feriado, sem divulgação)
  source    TEXT NOT NULL,   -- 'BCB_SGS'|'IBGE_SIDRA'|'ANBIMA'|'B3'|'FRED'|'YAHOO'|'MANUAL'
  freq      TEXT NOT NULL,   -- 'D'|'M'|'Q'
  vintage   DATE,            -- data em que o valor foi conhecido/baixado; NULL = série não revisável
  unit      TEXT,            -- '%'|'index'|'BRL'|'pp'
  collected_at TIMESTAMP NOT NULL,
  PRIMARY KEY (series_id, date, vintage)
)
```
Tabela de apoio `series_catalog(series_id, nome, descricao, fonte_url, data_inicio, data_fim, freq, unit, transformacao_padrao, obs)` — **essencial** para o handoff com o agente de fontes de dados.

### 6.2 `macro_quarterly`
```
macro_quarterly(
  quarter TEXT PK,                 -- '2026Q3'
  quarter_end DATE,                -- último dia útil
  -- crescimento
  pib_yoy, pib_qoq_sa,
  ibcbr_yoy, ibcbr_yoy_trend, ibcbr_gap,        -- gap = yoy - trend
  -- inflação
  ipca_12m, ipca_12m_delta, ipca_meta, ipca_desvio_meta,
  -- juros
  selic_meta_fim, selic_meta_delta, selic_over_tri, juro_real_exante,
  -- curva
  di_3m, di_1a, di_5a, inclinacao_5a_3m,
  -- câmbio e externo
  usdbrl_fim, usdbrl_var_tri, usdbrl_var_12m,
  termos_troca_yoy, embi_br_fim, embi_delta_tri,
  -- expectativas (Focus, coleta do 1º dia útil do trimestre)
  focus_ipca_12m, focus_pib_ano, focus_selic_fim,
  surpresa_ipca, surpresa_pib, surpresa_selic,
  -- auditoria
  is_estimated BOOLEAN,            -- trimestre corrente incompleto
  lag_adjusted BOOLEAN             -- TRUE = respeita a regra anti-look-ahead
)
```
Gerar **duas materializações**: `macro_quarterly_asof` (`lag_adjusted = TRUE`, para decisão) e `macro_quarterly_revised` (`FALSE`, para descrição histórica).

### 6.3 `asset_returns_quarterly`
```
asset_returns_quarterly(
  quarter TEXT, asset_id TEXT,     -- 'IBOV','IDIV','SMLL','INDX','ICON','IMAT','IEE','IMOB','IFNC',
                                   -- 'IFIX','IMAB','IMAB5','IMAB5P','IRFM','IRFM1','IRFM1P','CDI',
                                   -- 'SP500_BRL','SP500_USD','UST10_BRL','GOLD_BRL','USDBRL'
  price_ini, price_fim,
  ret_tri,                         -- (price_fim/price_ini) - 1
  ret_excesso_cdi,                 -- (1+ret)/(1+cdi) - 1
  ret_real,                        -- (1+ret)/(1+ipca_tri) - 1
  vol_intra_tri,                   -- desvio dos retornos diários * sqrt(dias úteis)
  dd_intra_tri,                    -- max drawdown dentro do trimestre
  is_total_return BOOLEAN, n_dias_uteis REAL,
  PRIMARY KEY (quarter, asset_id)
)
```

### 6.4 `regimes` e `regime_neighbors`
```
regimes(
  quarter TEXT PK,
  regime_v1 TEXT,     -- RECUPERACAO|EXPANSAO_INFL|ESTAGFLACAO|DESACELERACAO
  regime_v1b TEXT,    -- versão vs Focus
  ciclo_selic TEXT,   -- CORTE|ALTA|NEUTRO
  regime_v2 TEXT,     -- regime_v1 || '_' || ciclo_selic
  stress_flag BOOLEAN,
  g_score REAL, pi_score REAL,     -- valores contínuos, para gráfico de dispersão
  fonte_versao TEXT                -- hash/versão do código que gerou
)
regime_neighbors(                  -- saída da V3
  quarter_ref TEXT, rank INT, quarter_neighbor TEXT,
  distancia REAL, metrica TEXT,    -- 'mahalanobis'|'euclidiana'
  PRIMARY KEY (quarter_ref, rank, metrica)
)
```

### 6.5 Convenções de retorno — confirmações
- **Ibovespa é índice de retorno total** `[V]` — confirmado: o objetivo é refletir não só a variação de preços, mas o impacto da distribuição de proventos; dividendos, JCP e rendimentos são incorporados à carteira (pelo valor **líquido de imposto**).
- **IFIX é índice de retorno total** `[V]` — considera variação das cotas **e** rendimentos distribuídos.
- **Índices IMA (ANBIMA) são de retorno total** `[V]` — encadeados pelo método de Laspeyres; **cupons de juros e resgates são levados em conta na apuração do valor do índice**. Atenção à vigência da carteira teórica: IRF-M/IMA-C/IMA-S do 2º DU ao 1º DU do mês seguinte; **IMA-B do dia 16 ao dia 15** `[V]`.
- **Demais setoriais B3** (IDIV, SMLL, INDX, ICON, IMAT, IEE, IMOB, IFNC): a família segue o manual de definições e procedimentos e a maioria é retorno total, mas **o agente de dados deve confirmar índice por índice** antes de fechar o dataset `[G — confirmar]`.
- **S&P 500:** usar a versão **total return** (`^SP500TR`), não o índice de preço. Misturar total return doméstico com price return internacional viesa a comparação em ~2 pp/ano `[A]`.
- **Encadeamento sempre geométrico.** Excesso sobre CDI e retorno real **sempre por razão** `(1+r)/(1+b) − 1`, nunca por subtração — com Selic a 14% a diferença é material.
- **Calendário:** último dia útil da B3 de mar/jun/set/dez. Ativo que não negociou nesse dia: forward fill de no máximo 5 dias úteis; acima disso, `NULL` e registrar.

---

## 7. Entregável para o Comitê de 2026-10-14

### Pacote mínimo (realista em 3 dias úteis) — COMPROMETER ISSO
| # | Entregável | Observação |
|---|---|---|
| 1 | `macro_quarterly` com 83 trimestres | IBC-Br, IPCA, Selic, DI 3m/5a, USDBRL, Focus. PIB IBGE se der tempo |
| 2 | `asset_returns_quarterly` | Prioridade: CDI, IBOV, IMA-B, IRF-M, IFIX, SMLL, IDIV + SP500_BRL, USDBRL, GOLD_BRL. Setoriais conforme disponibilidade |
| 3 | `regimes` com V1 (4 quadrantes) | Especificação **congelada em ADR antes de rodar** |
| 4 | **1 notebook** reprodutível | Carrega → classifica → calcula métricas → gera figuras |
| 5 | **Heatmap regime × ativo** (excesso sobre CDI) com `n` em cada célula | Entregável visual central |
| 6 | **Tabela "regime atual → ranking de ativos"** | 1 página, com semáforo de confiança |
| 7 | **Timeline de regimes 2006-2026** sobre IBOV e Selic | Sanity check do Comitê |
| 8 | **V3: os 8 trimestres mais parecidos com 3T2026** + retorno dos ativos nos trimestres seguintes | O diferencial; responde ao e-mail |
| 9 | **1 página de limitações** | n pequeno, quebra estrutural, look-ahead. Blinda a reunião |

### Pacote estendido (semanas seguintes)
V1b (vs Focus) e V2 completas com teste de robustez; setoriais B3 completos + segmentações de FII (fonte terceira); EMBI/CDS e termos de troca na matriz; variância mínima por regime com shrinkage + fronteira eficiente; dupla materialização `asof` vs `revised` com relatório de divergência de classificação; clustering (GMM/k-means) como validação independente da V1; HMM com dados mensais (240 obs) e probabilidades de transição; dashboard que atualiza o regime corrente.

### Riscos de prazo
| Risco | Mitigação |
|---|---|
| ETTJ ANBIMA histórica difícil de obter | Fallback DI futuro (B3) ou pré ANBIMA; se nada, **tirar a curva da V3** e rodar com 5 features |
| Focus histórico por data de coleta demorado | O pacote mínimo usa V1 "vs tendência", que **não depende do Focus** |
| Setoriais B3 com histórico curto | Heatmap com `n` por linha; aceitar linhas incompletas |
| Segmentações de FII inexistentes oficialmente | Declarar fora do pacote mínimo **já na terça** |

---

## 8. Decisões que o humano precisa tomar

| # | Decisão | Opções | Recomendação da pesquisa |
|---|---|---|---|
| D1 | Qual variante é a "oficial" do Comitê | V1 / V2 / V3 / as três | **V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário** |
| D2 | Eixo crescimento | desvio da tendência (barato) / surpresa vs Focus (correto) | **Tendência no mínimo; Focus no estendido** |
| D3 | Eixo inflação | nível vs meta / aceleração (Δ 12m) | **Aceleração** — é o que Investment Clock e Bridgewater usam `[V]` |
| D4 | Respeitar defasagem de divulgação já na V1 | sim (defensável) / não (simples) | **Produzir as duas e reportar a divergência** |
| D5 | Métrica primária do heatmap | nominal / excesso CDI / real | **Excesso sobre CDI** — neutraliza a mudança de patamar da Selic |
| D6 | Internacional: estrutural, tático ou híbrido | piso fixo / 100% por regime / piso + banda | **Piso 16-20% + banda tática 15-35% por regime** |
| D7 | Dólar hedgeado vs sem hedge no estudo | só sem hedge / ambos | **Ambos** — a diferença XP (2,5-7% hedgeado) vs FGV (16-35% cambial) é a essência da discussão `[V]` |
| D8 | Janela: 2006-2026 inteiro ou só pós-2016 | tudo / pós-2016 / tudo + variante | **Tudo, com V3-pos2016 como robustez** |
| D9 | k da V3 | 5 / 8 / 12 | **8, com 5 e 12 como sensibilidade** |
| D10 | Limiar de supressão por n baixo | n<5 / n<8 / n<10 | **Alerta em n<8; supressão de conclusão em n<5** |
| D11 | Incluir backtest de estratégia na quarta | sim / não | **Não.** Entregável é descritivo; backtest é fase 2 e exige walk-forward |
| D12 | Setoriais e FII segmentado no pacote mínimo | completo / best-effort / fora | **Best-effort, com `n` e `data_inicio` visíveis** |

---

## 9. Referências

**Verificadas nesta pesquisa `[V]` — frameworks de gestoras.** Bridgewater, *The All Weather Story*: https://www.bridgewater.com/research-and-insights/the-all-weather-story · PDF: https://www.bridgewater.com/_document/the-all-weather-story?id=00000171-8623-d7de-affd-feaf4ee20000 · SSGA/Bridgewater ALLW: https://www.ssga.com/us/en/intermediary/insights/allw-brings-bridgewaters-all-weather-wisdom-to-etf-investors · Macro Ops, *The Merrill Lynch Investment Clock*: https://macro-ops.com/the-investment-clock/ · TitanFX, *ML Investment Clock — 4 Phases*: https://research.titanfx.com/glossary/merrill-lynch-investment-clock

**Verdad.** *Classifying Economic Regimes* (GMM, 4 regimes): https://verdadcap.com/archive/classifying-economic-regimes · *Diversification, Correlation, and the Business Cycle*: https://verdadcap.com/archive/diversification-correlation-and-the-business-cycle · *The Best Macro Indicator*: https://verdadcap.com/archive/the-best-macro-indicator · *Countercyclical Investing* (PDF): https://static1.squarespace.com/static/5db0a1cf5426707c71b54450/t/60709482d5afd833ede2c38a/1617990804914/Countercyclical+Investing_vF.1.pdf

**Man Group.** *Under the MacroScope*: https://www.man.com/insights/under-the-macroscope · *Regimes, Systematic Models and the Power of Prediction*: https://www.man.com/insights/regimes-systematic-models-power-of-prediction · *Inflation Regime Roadmap* ("Fire and Ice"): https://www.man.com/insights/inflation-regime-roadmap

**AQR.** *Exploring Macroeconomic Sensitivities*: https://www.aqr.com/-/media/AQR/Documents/Journal-Articles/JPM-Exploring-Macro-Economic-Sensitivities.pdf · *Mapping Investable Return Sources to Macro Environments*: https://www.aqr.com/-/media/AQR/Documents/Insights/Alternative-Thinking/Alternative-Thinking-Mapping-Investable-Return-Sources-to-Macro-Environments.pdf · *Inflation in 2010 and Beyond, Part II*: https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/Inflation-in-2010-and-Beyond--Part-II.pdf · *A Half Century of Macro Momentum*: https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/A-Half-Century-of-Macro-Momentum.pdf

**Estatística de regimes.** *Tactical Asset Allocation with Macroeconomic Regime Detection* (arXiv 2503.11499): https://arxiv.org/html/2503.11499v1 · *Dynamic Asset Allocation with Asset-Specific Regime Forecasts* (arXiv 2406.09578): https://arxiv.org/pdf/2406.09578 · *Downside Risk Reduction Using Regime-Switching Signals: A Statistical Jump Model Approach* (arXiv 2402.05272): https://arxiv.org/pdf/2402.05272 · *A novel dynamic asset allocation system using Feature Saliency HMM*: https://www.sciencedirect.com/science/article/abs/pii/S0957417420305443 · *On the use of Nearest Neighbors in finance*: https://cairn.info/revue-finance-2005-2-page-67.htm · scikit-learn Nearest Neighbors (métrica Mahalanobis): https://scikit-learn.org/stable/modules/neighbors.html

**Brasil — macro e curva de juros.** BCB, *Aspectos metodológicos e comparações dos comportamentos do IBC-Br e do PIB*: https://www.bcb.gov.br/conteudo/relatorioinflacao/estudosespeciais/metodologia_ibc-br_pib_estudos_especiais.pdf · BCB, *Indicadores Antecedentes Extraídos de Preços de Ativos em Corte Transversal* (TD 361): https://www.bcb.gov.br/pec/wps/port/TD361.pdf · BCB, *Previsão da Curva de Juros* (WPS 186): https://www.bcb.gov.br/pec/wps/port/wps186.pdf · BCB, *Determinantes do prêmio de risco nas taxas nominais* (RI jun/2026): https://www.bcb.gov.br/content/ri/relatorioinflacao/202506/rpm202506b7p.pdf · Insper, *Estimação do prêmio de risco da curva de juros no Brasil*: https://repositorio.insper.edu.br/entities/publication/9492ebeb-fb09-4a58-ab7c-854a87c6ec7c · FGV/IBRE, *O que significa a inversão da curva de juros no Brasil?*: https://blogdoibre.fgv.br/posts/o-que-significa-inversao-da-curva-de-juros-no-brasil · IBGE, Contas Nacionais Trimestrais (defasagem e política de revisão): https://www.ibge.gov.br/estatisticas/economicas/comercio/9300-contas-nacionais-trimestrais.html

**Brasil — metodologia de índices.** B3, Metodologia Ibovespa: https://www.b3.com.br/data/files/9C/15/76/F6/3F6947102255C247AC094EA8/IBOV-Metodologia-pt-br__Novo_.pdf · B3, Metodologia IFIX: https://www.b3.com.br/data/files/2A/56/E3/DD/A3943710DB551337AC094EA8/IFIX-Metodologia-pt-br.pdf · B3, Manual de definições e procedimentos dos índices: https://bvmf.bmfbovespa.com.br/indices/download/manual-de-procedimentos-pt-br.pdf · ANBIMA, Metodologia IMA (dez/2023): https://data-strapi.prd.anbima.com.br/uploads/Metodologia_IMA_dez23_714738d8e2.pdf · ANBIMA, página dos índices IMA: https://www.anbima.com.br/pt_br/informar/precos-e-indices/indices/ima.htm

**Internacional em carteira brasileira.** *O número mágico da internacionalização* (estudo FGVcef / Prof. William Eid Jr., 21.000 janelas 2005-2026): https://aftermarketfl.substack.com/p/o-numero-magico-da-internacionalizacao · Avenue Connection, *O que a FGV diz sobre alocação e diversificação internacional*: https://connection.avenue.us/educacional/o-que-a-fgv-diz-sobre-alocacao-e-diversificacao-internacional/ · BTG Pactual, relatório de alocação internacional: https://research-content.btgpactualdigital.com/file/2022-03-09T182436.065_FR_26_Internacional.pdf · Economatica, *Investimentos no Exterior — panorama da indústria de fundos brasileira*: https://www.economatica.com/blog/investimentos-no-exterior-panorama-da-industria-de-fundos-brasileira · Estudo acadêmico de correlação Ibovespa × dólar × risco Brasil (IFSC): https://eventoscientificos.ifsc.edu.br/index.php/sepei/sepei2013/paper/viewFile/30/203

**Surpresa econômica.** Haver Analytics, *The Power of Surprises*: https://www.haver.com/articles/archive-economy-the-power-of-surprises · FP Markets, metodologia do Citigroup Economic Surprise Index: https://www.fpmarkets.com/en-br/education/trading-guides/what-is-the-citigroup-economic-surprise-index/

**Citado por busca, não acessado diretamente `[V-parcial]`.** XP, *O atual regime macroeconômico no Brasil está prestes a mudar?*: https://conteudos.xpi.com.br/estrategia-acoes/o-atual-regime-macroeconomico-no-brasil-esta-prestes-a-mudar/ (**HTTP 403 no fetch automático — abrir no navegador e confirmar antes de citar em slide**) · Greetham & Hartnett, *The Investment Clock* (ML, 2004), cópia não oficial: https://silo.tips/download/the-investment-clock

**Conhecimento geral, não verificado nesta rodada `[G]` — pendências para o agente de fontes de dados.** (1) Datas de início de cada índice setorial da B3 e se cada um é retorno total. (2) Série histórica de metas de inflação do CMN e a data exata da transição para meta contínua. (3) Existência de segmentações oficiais do IFIX (Tijolo/Papel/Logística/Shoppings) com 20 anos. (4) Disponibilidade de ETTJ ANBIMA histórica completa sem contrato de dados. (5) O número "~40% no exterior" atribuído a material de distribuidor — **não usar como âncora**.
