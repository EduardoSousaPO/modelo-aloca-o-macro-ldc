# Limitações do levantamento de dados — o que o número sustenta e o que não sustenta

**Para:** Alexandre Kaercher e o Comitê de Alocação da LDC Capital
**De:** Eduardo (Edu) · **Data:** 2026-10-11 · **Reunião:** 2026-10-14
**Cobre:** RF-042 / CA-112 · **Base:** 83 trimestres, 2006Q1 → 2026Q3

> ## ⚠️ Leia isto primeiro: a especificação **não está congelada**
>
> A regra que define os regimes macro (quais eixos, quantos quadrantes, qual lente é a oficial) está
> registrada em **ADR-001, com status "Proposta"** — ainda não aceita por ninguém. O próprio pipeline
> sabe disso e publica, em cada rodada, `especificacao_congelada = false` e `publicavel = false`
> (`relatorio_regimes_v1.json → especificacao`; `relatorio_regimes_v3.json → gate_de_publicacao`).
>
> **Consequência prática:** todo número deste pacote é **material de discussão, não insumo de decisão
> de alocação**. O dia em que o Comitê ratificar as regras, uma única reconstrução do dataset refaz
> os 83 trimestres — sem uma linha de código nova.
>
> **E, por construção, nada aqui é previsão.** O entregável responde "em que quadrante cada trimestre
> do histórico caiu" e "em momentos parecidos, como cada classe rendeu, com quantas observações".
> Nunca "quanto vai render".

## 1. O que foi pedido no e-mail × o que foi entregue

Base medida: **24 ativos · 1.963 linhas · 83 trimestres** (`relatorio_retornos.json →
asset_returns_quarterly`) e **42 variáveis macro × 83 trimestres** (`relatorio_macro.json → macro_quarterly`).

| Item | Pedido | Status | Fonte efetivamente usada |
|---|---|---|---|
| **A1** | PIB (IBC-Br ou PIB IBGE) | **entregue, com ressalva** | IBC-Br dessaz. do BCB + PIB trimestral do IBGE. O IBC-Br **começa em 2003**, e o hiato de atividade só existe a partir de 2009Q4 — ver §5 |
| **A2 · A4 · A7** | IPCA mensal e 12 meses · Selic Over e meta · IPCA histórico completo | **entregues** | BCB (séries 433, 13522, 11, 432) e IBGE/SIDRA |
| **A3** | Expectativas do Focus | **entregue** | BCB/Olinda: **28.182 coletas, 5 séries, 2004 → 2026** (`relatorio_macro.json → focus`) |
| **A5** | Taxas de títulos públicos | **entregue** | Tesouro Direto (base pública, 2004 → hoje) |
| **A6** | Curva de juros (ETTJ ANBIMA) | **substituída** | Curva construída das taxas do **Tesouro Direto**, interpolada para 1, 3 e 5 anos. A ETTJ oficial com histórico só existe no produto **pago** da ANBIMA |
| **B1 · B2** | IMA-B / 5 / 5+ e IRF-M / 1 / 1+ | **entregues** | Repositório público da ANBIMA (melhor que a rota pedida — §2) |
| **B3** | CDI acumulado | **entregue** | BCB |
| **B4** | Setoriais e índices amplos da B3 | **entregue** | API da B3: IBOV, IDIV, SMLL, INDX, ICON, IMAT, IEEX, IMOB, IFNC e UTIL — os 9 pedidos + 1. **ICON e IMOB com janela menor** (§3) |
| **B5a** | IFIX | **entregue, janela curta** | API da B3, **a partir de 2011** (§3) |
| **B5b** | FII por segmento (Tijolo, Papel, Logística, Shoppings) | **FORA do pacote** | A B3 **não publica** índice setorial de FII; o provedor privado identificado começa em 2019 e a extração **não foi executada** (`relatorio_retornos.json → universo.fora_do_universo`) |
| **C1** | Dimensionamento da alocação internacional | **entregue em parte** | Dólar (PTAX), S&P 500 em dólar e em reais, MSCI ACWI em reais. **Fora:** ouro, versão com hedge cambial e Treasury em retorno total |

## 2. Substituições de fonte e o efeito na comparabilidade

As 12 estão registradas com motivo e impacto em `docs/plans/DECISIONS_LOG.md §1`, e **todas as 12 são provisórias** — nenhuma recebeu aval. As cinco que mudam o que se pode afirmar:

1. **Curva de juros: Tesouro Direto no lugar da ETTJ oficial da ANBIMA (A6).** O histórico da curva
   oficial existe apenas no produto pago da ANBIMA (R$ 686 a R$ 8.238/mês) e a versão gratuita é uma
   janela de ~20 dias úteis, que não serve para 20 anos. A curva do pacote vem de **taxas de varejo**,
   interpoladas; contra a curva oficial de 09/10/2026 as diferenças são de **6 a 20 pontos-base, sempre no
   mesmo sentido**. Suficiente para medir **inclinação** (curto × longo), que é o uso pretendido;
   insuficiente para bater na casa decimal — e **nenhuma figura pode chamar isso de "curva ANBIMA"**.
2. **A rota literal do e-mail está morta.** As séries de swap DI × pré do BCB foram descontinuadas
   (diárias em 30/09/2019, mensais em 01/08/2019). O efeito da troca é **positivo**: fonte única e
   contínua em vez de duas emendadas.
3. **A inclinação publicada é a real (títulos indexados ao IPCA), não a nominal** — em 2006 o prefixado
   mais longo vencia em 2009, a ponta longa nominal **não existia**. É mudança de conceito, não só de
   fonte. A cobertura manda no vértice: **5 anos − 3 anos** tem valor em **95,25%** dos dias úteis desde
   2006 e é a principal; **5 anos − 1 ano** tem **60,53%** e fica secundária, com a cobertura declarada.
4. **Índices IMA pelo repositório público da ANBIMA, não pelo BCB** — as séries de IMA no BCB foram
   **descontinuadas em 22/05/2023**; a troca é melhora: série mais longa e sem emenda.
5. **Bloco internacional por Yahoo + MSCI, não pelo FRED**, que está **bloqueado nesta máquina**
   (3 de 3 tentativas). O Treasury de 10 anos tem substituto praticamente equivalente; o **Fed Funds
   não tem**, e é por isso que a versão **com hedge cambial** do S&P 500 ficou fora.

Mais três correções de expectativa, que não mudam número mas evitam mal-entendido na reunião:
**"ANBIMA DataFit" não existe** como produto (existem o portal ANBIMA Data, grátis, e o ANBIMA Feed, pago
e não contratado); **risco-país ficou fora**, porque o EMBI+ foi descontinuado em 30/07/2024 e não há
fonte gratuita e contínua com 20 anos; e **a série de dívida usada é a líquida, não a bruta** (a bruta
começa em 2008) — conceito fiscal diferente, não comparar com dívida bruta publicada.

## 3. Janelas próprias: o painel é desbalanceado de propósito

Não existe IFIX antes de 2011, nem ICON antes de 2007, nem IMOB antes de 2008. A alternativa a aceitar
janelas diferentes seria **cortar toda a análise em 2011** — e aí a janela de 20 anos do e-mail cai. A
escolha foi manter 2006 → 2026 e **declarar a janela de cada linha** (`relatorio_retornos.json →
ativos[].primeiro_trimestre` e `n_retornos`).

| Linha | Primeiro trimestre com retorno | Trimestres com retorno | O que isso impede |
|---|---|---|---|
| IBOV, IDIV, SMLL, INDX, IMAT, IEEX, IFNC, UTIL, IMA-*, IRF-M*, dólar, S&P, ACWI | 2006Q2 | **82** | nada |
| **ICON** | 2007Q1 | **79** | comparação direta com os demais setoriais sem nota de janela |
| **IMOB** | 2008Q1 | **75** | leitura do índice em 2006-2007; perde o pré-crise |
| **IFIX** | 2011Q1 | **63** | **qualquer afirmação sobre FII em 2006-2010**, inclusive na crise de 2008 |


**Quantas observações por regime.** Com quatro quadrantes e 83 trimestres, a distribuição medida é
Recuperação **19** · Expansão com inflação **19** · Estagflação **16** · Desaceleração **13**; outros
**16** trimestres ficam **indeterminados** (`relatorio_regimes_v1.json → distribuicao.por_grupo`).

**O que isso custa em precisão.** Com dispersão trimestral de 12% — a premissa de CA-112 —, a margem de
erro da média de uma célula é de cerca de **2,8 pontos percentuais por trimestre** com n = 19, **3,3 pp**
com n = 13 e **4,2 pp** com n = 8. Na lente de "momentos semelhantes" (n = 8), os erros-padrão
**medidos** vão de **0,00 pp** (CDI) a **4,95 pp** (SMLL) entre as linhas publicáveis — e chegam a
**6,01 pp** em IMOB, que por isso sai sem conclusão —, enquanto o primeiro colocado tem média **+5,04%**
e erro-padrão de **2,54 pp** (`relatorio_regimes_v3.json → ranking_ativos_t_mais_1.ativos`). Em palavras:
**a ordem do ranking não é estatisticamente distinguível** — o número sustenta "este grupo rendeu mais
que aquele, com esta incerteza", não "este é o melhor". Daí as duas travas automáticas: **toda célula
mostra o seu `n`**, **n < 8** entra com alerta e **n < 5** sai **sem conclusão** — hoje isso atinge
**IFIX e IMOB** (n = 4, suprimidos) e **ICON** (n = 6, alerta).

**Quebra estrutural: 2006-2008 não é o mesmo país que o pós-2016.** A Selic saiu de ~19% (2006) para 2%
(2020) e voltou a dois dígitos, e o arcabouço mudou várias vezes no caminho (tripé macro, nova matriz
econômica, teto de gastos em 2016, autonomia do BCB em 2021, novo arcabouço fiscal em 2023). Daí três
consequências: **retorno nominal não é comparável entre épocas** — é por isso que a métrica-cabeça é
excesso sobre o CDI; **"nível de juros" como característica de regime confunde época com regime** — daí
usarmos juro real e **variação** da Selic; e **a janela muda o resultado** — restringir ao pós-2016 troca
6 dos 8 "momentos semelhantes" de 2026Q3 (`relatorio_regimes_v3.json →
sensibilidade.pos2016_vs_janela_cheia`). Não é defeito do cálculo: é a informação de que **20 anos de
histórico brasileiro não são 20 anos do mesmo regime institucional**.

**Índice não é ativo investível.** Todas as linhas do pacote são **índices**, de carteira teórica revisada
periodicamente (o IFIX é reponderado a cada quatro meses). Não há taxa de administração, corretagem,
spread, imposto nem custo de rebalanceamento em nenhum número: **nada aqui é retorno líquido de um fundo
ou de uma carteira real**, e Sharpe de índice **não** é Sharpe implementável — a diferença é material
justamente nas linhas mais ilíquidas (small caps, FII, setoriais estreitos).

### 3.1 A parte internacional: três limitações próprias

- **A regra de "trimestre de stress" não é avaliável em 14 dos 83 trimestres.** O gatilho é queda forte da inclinação da curva de juros **ou** alta do dólar acima de 10% no trimestre; o primeiro ramo não pode ser avaliado em 2006Q1-2008Q1 (janela de referência ainda se formando) nem em 2020Q3-2021Q3 (buraco na inclinação de 5−3 anos). Nesses 14 o ramo do dólar continua valendo, e a página de números os **nomeia um por um** — *trimestre não avaliável não é trimestre sem stress*. O terceiro ramo previsto (risco-país) está **declaradamente fora**: a série morreu em julho de 2024 e tem **zero** valores no período. Com os dois ramos que existem, **20 dos 83** trimestres são de stress, e **9 dos 10 piores trimestres do IBOV** estão entre eles — conferido **depois** de a regra ser fixada, não usado para calibrá-la.
- **O tamanho do internacional muda de 10,4% para 19,7% por causa de uma restrição de apresentação.** O cálculo de menor variância aponta **15,9% a 23,6%** por regime limitando cada ativo a 40% da carteira; **sem esse limite**, a média da janela inteira cai de **19,7% para 10,4%**. Número que quase dobra conforme uma escolha de apresentação **não é um número** — por isso a entrega é uma **faixa** (piso estrutural 16-20% + banda tática 15-35%), nunca um ponto, com 13 a 19 observações por regime.
- **Três ativos pedidos não têm fonte** — ouro em reais, Treasury de 10 anos em retorno total e S&P com hedge cambial — e saem como indisponíveis, **sem substituto**. E *com hedge* × *sem hedge* são **categorias diferentes**: as referências de 2,5-7% tratam de global hedgeado; as de 16-35%, de exposição cambial.
> **Nota sobre o mapa de calor (regime × ativo):** o S&P em **dólar** foi **retirado** da figura do Comitê — comparar retorno em dólar com o CDI em reais mistura duas moedas na mesma célula, e a célula deixa de ter leitura. O internacional aparece pelas linhas **em reais**. A linha retirada **não** foi apagada do dado: continua na tabela de números, e a figura **diz no rodapé** que foi retirada e por quê.

## 4. Convenções que mudam o número — e que o Comitê deveria conhecer

Nenhuma destas é opinião disfarçada: cada uma está medida e publicada no dado.

1. **Trimestre = último dia útil, não média do período.** Em **24 dos 83** trimestres o último dia útil
   difere do último dia civil (`relatorio_alinhamento.json → grade`). Lacuna de até 5 dias úteis é
   preenchida com o último valor conhecido; acima disso a célula **fica vazia** — hoje **7 células de
   4.038** (0,17%). Nada é estimado ou interpolado.
2. **A B3 não negocia no último dia útil bancário do ano.** Por isso, em **20 trimestres** (todos os 4ºs
   trimestres de 2006 a 2025) as séries da B3 usam o fechamento do dia anterior: **215 células de 4.038
   (5,3%)**, em 11 séries, **nenhuma** com atraso maior que 1 dia útil (`relatorio_alinhamento.json →
   decisao_d_h`). O efeito no retorno do trimestre é nulo — o mesmo fechamento entra nas duas pontas do
   ano —, mas é a origem do item 3 abaixo.
3. **Excesso sobre o CDI é calculado por razão, nunca por subtração** — com Selic de dois dígitos a
   diferença não é arredondamento: **0,139 pp**. Há uma **limitação declarada** aqui: por causa do item
   2, a janela do CDI e o caminho do ativo diferem de 1 a 3 dias úteis em **599 de 1.857** linhas, com
   viés médio de **0,0185 pp** e máximo de **0,1575 pp** (`relatorio_retornos.json →
   convencoes.janela_do_cdi_vs_caminho_do_ativo`). É ~8× menor que o efeito razão-vs-subtração, e por
   isso o cálculo **não** foi alterado: corrigir exigiria reconstruir o CDI ativo por ativo.
4. **O nível trimestral do IBC-Br é a média dos 3 meses**, não o último mês. A correção (11/10) move o
   eixo de crescimento em até **4,3 pp** e faz **7 dos 67 trimestres classificados trocarem de
   quadrante** (`relatorio_macro.json → medias_no_trimestre`). O PIB do IBGE não muda.
5. **Um movimento de 25 pontos-base na Selic conta como ciclo, não como parada.** Com a leitura estrita,
   7 trimestres com variação de exatamente 0,25 pp cairiam em "neutro" — inclusive os cortes reais de 25
   pb de 2024. Distribuição medida: **corte 34 · neutro 23 · alta 26**; com a regra antiga, 29 · 30 · 24
   (`relatorio_macro.json → ciclo_selic`).
6. **Escalas diferentes em tabelas diferentes:** macro em **por cento / pontos percentuais**, retornos em
   **fração**. Quem cruzar as duas sem olhar a unidade erra por 100× — o mapa de unidades vai no próprio
   dado (`relatorio_macro.json → unidades`).
7. **Parte dos índices entra sem a confirmação de que são retorno total:** a flag está indefinida em
   **820 linhas** — os 9 setoriais da B3 e o CDI (`relatorio_retornos.json →
   asset_returns_quarterly.nulos_por_coluna`). É lacuna aberta: comparar retorno total com retorno de
   preço superestima o segundo. IBOV e IFIX estão confirmados como retorno total; o S&P 500 em reais
   está declarado como retorno de preço.

## 5. Look-ahead: o resultado de 33% e por que ele importa

A pergunta é: **a classificação de regime usa informação que não estava disponível na época?** O
pacote constrói **duas versões** do mesmo histórico e compara — a **descritiva**, que usa a série
como ela é hoje, e a **defasada**, em que o valor do trimestre T é o último que já tinha sido
**divulgado** até o fim de T (o IBC-Br sai ~45 dias depois do mês, o IPCA ~10, o PIB ~60).

**Resultado medido: 22 de 66 trimestres comparáveis trocam de quadrante — 33,33%.** O limite escrito
na metodologia e no critério de aceitação CA-074 é **25%** (`relatorio_regimes_v1.json →
divergencia_asof_vs_revised`). Das 37 variáveis macro, **27 são idênticas** nas duas versões e **10
mudam** (as de atividade e inflação) — `relatorio_asof.json → resumo_da_comparacao`.

**O que isso significa, em uma frase:** a lente V1 é **descritiva, não operacional**. Ela responde bem
"em que quadrante cada trimestre do histórico caiu" — e é esse o entregável — e **não** responde de
forma confiável "em que quadrante estamos agora, com o que se sabe hoje", porque o hiato de atividade é
pequeno (mediana ~2 pp) sobre média móvel de 20 trimestres: deslocar o IBC-Br em um trimestre troca o
sinal com facilidade.

**E é um piso, não o efeito total.** De duas fontes de look-ahead, o pacote corrige uma e declara a
outra. Corrigida: a **defasagem de divulgação** — **0 violações em 2.552 células**, verificado no dado.
Declarada: a **revisão retroativa** — o IBGE revisa o PIB uma vez por ano, e a base tem hoje
**uma única safra por série**, então não existe o retrato antigo para usar (`relatorio_asof.json →
limitacoes.vintage_unico`). A defasagem também é um prazo **típico em dias civis**, não o calendário real
de cada divulgação; arredondar para cima é conservador: descarta informação, nunca cria look-ahead.

**A lente de "momentos semelhantes" passa nesse teste** — é o achado mais forte do levantamento: a lista
dos 8 trimestres mais parecidos com 2026Q3 é **exatamente a mesma** quando se proíbe o sistema de olhar
qualquer trimestre futuro (`relatorio_regimes_v3.json → sensibilidade.somente_passado_vs_descritiva`).
Três ressalvas: roda com **5 variáveis, não 6** (o índice de termos de troca não foi extraído, e
preenchê-lo seria dado inventado); cobre **77 dos 83** trimestres; e a versão que respeita o contrato
formal perde **4 dos 8 vizinhos de 2026Q3**, porque eles caem nos trimestres sem quadrante V1 — a
análise usa a versão completa, e essa diferença está declarada.

**O custo mais visível de tudo isso:** a V1 classifica **67 dos 83 trimestres**. Os 16 restantes são
**2006Q1 a 2009Q3** e **2026Q3** — ou seja, **a crise de 2008 fica fora do eixo de crescimento**, porque
o IBC-Br começa em 2003 e a média móvel de 20 trimestres só fecha em 2009Q4. Para ter hiato em 2006
seria preciso IBC-Br desde 2000, e a série não existe; nada foi estimado no lugar. A alternativa está
**medida**: janela parcial recuperaria **12** trimestres sem diferença no trecho comum, e não foi adotada
porque é outro estimador, cujo significado muda ao longo do tempo (`relatorio_macro.json →
sensibilidade_ibcbr_gap`).

## 6. O que **não** está neste pacote

- **Backtest, otimização ou fronteira eficiente** — decisão explícita de escopo; backtest honesto exige janela móvel e é trabalho de semanas. E **nenhuma previsão**, de regime ou de retorno.
- **Recomendação de alocação, carteira sugerida ou "top 5 para comprar".** O ranking que existe é
  descritivo ("nos trimestres seguintes a momentos parecidos este grupo rendeu X, com n = 8"); a
  recomendação é do Alexandre e do Comitê, não do dado.
- **FII por segmento** (Tijolo/Papel/Logística/Shoppings) e **índice próprio de FII**; **risco-país / CDS** (fonte descontinuada em 2024); **termos de troca** (nenhum índice extraído; a variável existe, está 100% vazia e isso está declarado).
- **A lente V2 completa** (quadrante × ciclo Selic): a regra do ciclo já está calculada, mas 12 estados dariam 5 a 15 observações cada — território onde o pacote **suprime** conclusão.
- **Ouro, S&P com hedge cambial, Treasury em retorno total** e **dashboard / site / atualização
  automática** — a entrega é um pacote de arquivos reproduzíveis.

## 7. Decisões que o Comitê / Alexandre precisam ratificar

Nenhuma destas respostas veio de uma pessoa: todas são a recomendação da pesquisa, aplicada como padrão
provisório para que a estrutura pudesse ser construída. Virar qualquer uma é legítimo e previsto — a
coluna da direita diz o preço.

| # | Decisão | Padrão provisório adotado | O que muda se o Comitê discordar |
|---|---|---|---|
| **D1** | Qual lente é a oficial | V1 (quadrantes) oficial, V3 ("momentos semelhantes") como leitura central, V2 secundária | se a V2 for oficial, a tabela principal passa a ter 12 estados com 5 a 15 observações e metade das células entra em alerta; se a V3 for oficial, o entregável central passa a ser a lista de vizinhos |
| **D3** | Eixo de inflação da V1 | aceleração do IPCA (variação da taxa de 12 meses) | "nível vs. meta" exige a série histórica de metas do CMN, que **não está na base**, e **os 83 rótulos mudam** |
| **D5** | Métrica principal do heatmap | excesso sobre o CDI | nominal torna 2006 (Selic 19%) e 2020 (Selic 2%) incomparáveis; real muda a leitura. As três já existem como colunas: é trocar um parâmetro da figura |
| **D6** | Internacional | piso estrutural de 16-20% + banda tática de 15-35% por regime | "100% tático" exigiria otimizar com ~20 observações por regime e entregar número pontual — que esta base não sustenta |
| **D12** | Setoriais e FII segmentado no pacote mínimo | *best effort*, com `n` e data de início visíveis | "completo" acrescenta extratores ao caminho crítico; "fora" reduz o heatmap |
| **L1** | IFIX só desde 2011 | janela própria 2011-2026, com IMOB (2008+) como aproximação imperfeita antes. **Sem IFIX sintético** | exigir painel balanceado restringe **toda** a análise a 2011-2026 e a janela de 20 anos do e-mail cai |
| **L2** | FII por segmento via provedor privado, desde 2019 | autorizado apenas como leitura qualitativa de dispersão — e **não foi extraído** | se autorizado, entra como linha com ~2 ciclos macro e sem valor inferencial; se negado, o item B5b fica formalmente não atendido |
| **L4** | Curva oficial da ANBIMA é paga | não contratar; usar a curva do Tesouro Direto | contratar o produto pago dá a curva oficial, recalcula a inclinação histórica e muda o tratamento de risco do projeto (passa a envolver credencial) |
| **D-i** | Qual inclinação é a variável de regime | **5 anos − 3 anos** (95,25% de cobertura) | voltar à 5a−1a devolve uma variável com **60,53%** de cobertura: ~40% dos trimestres cairiam num dia sem valor |
| **D-s** | Nível trimestral do IBC-Br | média dos 3 meses | voltar ao último mês devolve a distribuição anterior e **7 trimestres** mudam de quadrante de volta |
| **D-t** | Movimento de 25 pb na Selic | é ciclo (corte/alta), **nos dois sentidos** | com a regra estrita, os **7** movimentos de exatamente 25 pb do período voltam a ser classificados como "parada" — e são **5 cortes e 2 altas**, entre elas a alta de setembro de 2024 que abriu o ciclo de aperto |
| **D-u** | Eixo de crescimento da lente de "momentos semelhantes" | expectativa de PIB do Focus | sem o Focus, a lente **não tem vetor para 2026Q3** — exatamente o trimestre da pergunta do Comitê — e perde 2006-2009 |

**Atalho:** responder "aceito as recomendações" destrava tudo de uma vez, muda o status dos ADRs de "Proposta" para "Aceito" e torna os números publicáveis pelo fluxo formal de entrega.

## 8. Como reproduzir o que está aqui

Nada neste pacote foi digitado à mão: todo número sai de script versionado, e o bruto de cada fonte fica
arquivado com data, URL e impressão digital (`sha256`) da coleta. **Ambiente:** `uv sync --extra dev` —
nenhuma credencial é necessária, todas as fontes do caminho crítico são públicas e gratuitas.

- **Reconstrução com UM comando** (F-029): `python -m apps.pipeline run --offline` encadeia as 13 etapas na ordem obrigatória — curva → base bruta → alinhamento trimestral → variáveis macro → versão defasada → retornos → regimes → métricas por regime → internacional → figuras → tabelas —, cada uma **sem rede**, a partir do bruto arquivado; a sequência etapa por etapa está em `docs/wiki/runbooks/reconstruir-dataset.md`. `python -m apps.pipeline verify` recalcula a impressão digital de **todos** os arquivos publicados e **sai com erro** se um só byte divergir. **Reprodutibilidade verificada:** duas execuções consecutivas produziram os **47 arquivos byte a byte idênticos**, com o mesmo identificador de conjunto.
- **Como citar uma versão:** cada tabela publica a sua impressão digital no relatório da própria rodada — nesta: macro `2b8b65f4…`, versão defasada `5c4854f2…`, retornos `2798b5c1…`, regimes V1 `76512d8d…`, "momentos semelhantes" `a17d9288…` (campo `sha256` de cada `relatorio_*.json`), e o conjunto inteiro tem um identificador único no arquivo `MANIFEST.json`. **Hash diferente = outro dataset:** nunca comparar números de rodadas diferentes sem conferir.

**Rastreabilidade:** escopo → `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` · substituições de fonte com
os 4 campos obrigatórios → `docs/plans/DECISIONS_LOG.md §1` · decisões e aceites pendentes →
`TODO.md §4` e `docs/decisions/adr/` · lacunas de fonte →
`docs/research/fontes-de-dados-RESUMO.md §2` · armadilhas →
`docs/research/metodologia-regimes-macro.md §5` · números → `data/canonical/relatorio_*.json`.

*Feature F-028 (RF-042 / CA-112). Linguagem descritiva por contrato (Anti-SPEC §10.2.10): enquanto o
ADR-001 estiver em "Proposta", este documento acompanha o pacote como **material de discussão**.*
