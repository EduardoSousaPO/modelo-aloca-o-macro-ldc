# PRD — LDC Analytics · portal interno de ferramentas quantitativas

> **Versão:** 0.1 (proposta) — **Data:** 2026-10-11 — **Autor:** agente de desenho de produto
> (Claude), modo autônomo — **aprovação pendente de Eduardo (Edu)**. Estrutura e numeração seguem
> `docs/product/PRD.md`. **Nenhum número foi estimado aqui:** todos vêm de `CONTRACTS.md`, de
> `data/canonical/relatorio_*.json`, de `LIMITACOES-COMITE.md`, dos context packs das features ou
> das duas pesquisas — `docs/research/ldc-analytics-arquitetura.md` (`[arq]`) e
> `ldc-analytics-identidade.md` (`[ident]`), de 2026-10-11. `[apurado]` = verificado por mim.

> # ⚠️ LEIA PRIMEIRO — O PORTAL É FASE 2 E NÃO SUBSTITUI A ENTREGA DE 2026-10-14
>
> O Comitê é **quarta, 14/10**, e o pacote **já está pronto**: 41 arquivos + `HASHES.txt`, XLSX de 8
> abas, 5 figuras em PNG e SVG, as 2 tabelas de 1 página, o caderno executado em HTML e a página de
> limitações — montado, verificado e **selado** em `data/canonical/entrega/pacote_comite_2026-10-14/`.
> O que falta é **humano** (`TODO.md §4`): aceitar o ADR-001, rodar o checklist de 19 caixas,
> conferir os 3 canários na fonte viva, congelar e criar a tag.
>
> **Nada neste PRD entra no caminho crítico de 14/10.** O MVP custa **~25 dias-agente** (13 de
> infraestrutura + 12 do módulo 1) `[arq §8]`. Construí-lo nesta semana trocaria uma entrega
> conferida por uma não conferida, três dias antes da reunião.
>
> **Existe um atalho honesto, e ele é v0, não v1:** publicar o **HTML executado do caderno atrás de
> autenticação** custa **1 a 2 dias**, com zero infraestrutura nova `[arq §8]` — e **mesmo isso só
> depois do ADR-001 aceito**. Enquanto o ADR-001 estiver em `Proposta`, cada tela nasce com a faixa
> fixa `MATERIAL DE DISCUSSÃO — especificação não congelada`, lida do ADR em disco com falha fechada
> (`status_adr_001()`, a mesma função de F-019/F-023/F-031).

---

## 1. Visão geral

### Problema

O pipeline produz **83 trimestres × 42 variáveis macro**, **24 ativos × 1.963 linhas de retorno**,
3 lentes de regime, 120 células de métricas e 5 figuras determinísticas — e entrega **arquivos**.
Isso resolve 14/10 e cria dois problemas: (1) **o dado só responde quem souber abrir Parquet** —
pergunta fora do recorte que o Edu escolheu ("e se eu filtrar pós-2016?", "e com k=12?", "qual o
pior trimestre do IMOB em estagflação?") volta como mensagem para o Edu, que roda o pipeline e
devolve um print: **o gargalo é uma pessoa**; (2) **cada ciclo repete o custo** — o modelo se
atualiza a cada trimestre, o pacote não. E a casa vai querer **outras** ferramentas quant: hoje cada
uma nasceria como outro repositório, outro pacote e outro gargalo.

### Solução proposta

**LDC Analytics** — portal web interno que hospeda ferramentas de análise quantitativa: um ambiente
para **construir ferramentas, alimentar com dados, simular, projetar e validar teses**. O **primeiro
módulo** é o modelo de alocação macro que já existe como pipeline Python. O portal **lê** um dataset
versionado por hash e **não recalcula metodologia**. O dado de apresentação é pequeno — **≈ 610 KB de
Parquet** medidos em disco, tabela principal de **83 linhas** `[arq §0]` —, logo o caminho recomendado
não é consultar Parquet remoto: é **pré-computar um JSON por visão no build**, dos Parquet congelados
por tag `[arq §1.1]`. A complexidade aqui não está em volume, e sim em **versionamento, procedência e
gate de publicação**.

### Objetivo principal

Fazer o **Alexandre responder sozinho**, em menos de 2 minutos e sem pedir nada ao Edu, as 5
perguntas que hoje viram mensagem (§8) — e deixar o caminho pronto para o módulo 2 entrar sem
refazer o portal.

### O que o LDC Analytics **não** é

| Não é | Por quê |
|---|---|
| **Site público** | ferramenta interna, atrás de acesso restrito; sem SEO, sem sitemap, `noindex`. E **não é sistema de ordens**: não há corretora, posição, ordem, custódia ou rebalanceamento |
| **Fonte de verdade** | a fonte é o dataset congelado (`DATASET_SHA256`). Divergência portal × pipeline é bug **do portal**, sempre |
| **Recomendação de investimento** | nenhuma tela diz o que comprar (`LIMITACOES-COMITE.md §6`); não é material de distribuição nem conteúdo regulado; e **nenhuma tela projeta** retorno, probabilidade de regime ou cenário |
| **Ambiente exploratório livre** | 42 variáveis × 24 ativos × 3 lentes × 2 materializações em filtro livre é "um gerador de p-hacking com interface bonita" `[arq §7.4]`. As visões são as que o pipeline emitiu |
| **Substituto do pipeline** | mudar regra é mudança no pipeline (classe C), nunca no front |

---

## 2. Princípios de produto

Os seis primeiros vêm do pipeline e **não são negociáveis** — são o que torna o portal publicável sob
o mesmo gate da classe D.

- **P1 — Todo número carrega `n`.** `n` em toda célula de toda tabela e figura (RN-04). `n<8` →
  alerta; `n<5` → **conclusão suprimida**: perde a cor divergente, vira cinza hachurado, número
  rebaixado a `prelim.`. Hoje atinge `IFIX` e `IMOB` na V3 (`n=4`) e `ICON` (`n=6`). **`n` na célula,
  nunca só no tooltip** `[arq §7.3]`.
- **P2 — Nada preditivo.** Nenhum texto, rótulo, tooltip ou *empty state* usa forma assertiva. A
  guarda executável já existe e é **única** (`apps/analysis/_linguagem.py`): o portal a reusa.
- **P3 — A marca "especificação não congelada" aparece enquanto o gate estiver fechado** — faixa fixa
  no topo de toda tela, **não dispensável por clique** `[arq §6.5]`. Some sozinha no rebuild quando o
  Edu virar o `Status`: **zero linha de código**.
- **P4 — O portal lê um dataset versionado por hash e nunca recalcula metodologia.** Média, mediana,
  Mahalanobis, Ledoit-Wolf, razão-vs-subtração: **nada roda no cliente**. Corolário, igual ao da
  camada `analysis`: **se um número está errado na tela, o bug é da feature dona do pipeline.**
- **P5 — Mudar regra é mudança no pipeline (classe C), não no front.** Regra explícita: **se o portal
  pedir cálculo, o cálculo vai para o pipeline**, nunca para o TypeScript `[arq §7.5]`.
- **P6 — Unidade declarada em toda tela.** `macro_quarterly` em **%/pp**, `asset_returns_quarterly`
  em **fração** (D-o); as duas publicam `cdi_tri`/`ipca_tri` com o mesmo nome. Quem cruzar sem ler
  **erra por 100×**. A conversão existe em **um** lugar (o exportador) e todo eixo carrega o selo.
- **P7 — Uma pergunta por tela**, e ela é a frase de abertura. **P8 — O recorte visível é o recorte
  exportável:** CSV e PNG saem como a tela está, com os mesmos filtros, `n` e hash.
- **P9 — Divergência é conteúdo, não defeito.** Em `3T2026` a interseção dos top-5 das três lentes é
  **vazia**; a V1 troca de rótulo `asof`×`revised` em **33,33%**; a concordância V1×V3 tem **mediana
  0,111** em 61 referências. Primeiro plano, nunca nota de pé.
- **P10 — Ausência é rotulada, nunca preenchida.** 16 dos 83 trimestres são `INDETERMINADO`; 5
  colunas macro são 100% nulas por gap declarado. Cinza hachurado, nunca uma 5ª cor categórica.

---

## 3. Usuários e personas

- **Alexandre Kaercher (gestor) · leitor/explorador — principal.** Desktop antes de modelar e
  **celular minutos antes da reunião**. Não roda pipeline, não abre Parquet. Precisa das 3 respostas
  de regime lado a lado, do heatmap filtrável, dos vizinhos de qualquer trimestre e do `n` em tudo.
- **Eduardo (Edu) · dono.** Publica o dataset, decide o publicável, mantém o portal. Precisa de um
  comando que gere o dataset do portal do `MANIFEST.json` **já congelado** e da certeza de que o
  portal **não pode** mostrar número que o gate bloqueou. Windows, Python 3.11+.
- **Comitê de Alocação · leitor passivo.** Vê o portal projetado; vale o que a tela mostra
  **sozinha**: título, `n`, janela e limitação na mesma dobra. **Analista da casa · autor de módulo
  (futuro):** precisa que o contrato de módulo (§7) seja escrevível sem conhecer o módulo 1.
- **Anti-personas:** cliente final / investidor externo; trader intradiário (a decisão é
  **trimestral**); compliance e relatório regulatório; e quem quer "o número que o modelo prevê".

---

## 4. Módulo 1 — Alocação Macro: as 7 telas

Legenda dos wireframes: `[...]` controle · `#` cor divergente · `//` hachura de supressão ·
`~` faixa do gate. A tabela abaixo é o contrato das 7 telas — **o que responde, de qual tabela e
colunas vem, filtros, e o que é proibido mostrar**; os wireframes vêm depois, um por tela.

| Tela | Responde / Vem de (tabela · colunas) | Filtros | **Proibido mostrar** |
|---|---|---|---|
| **T-01** Visão geral | **em que regime estamos — três vezes — e por que discordam.** `tabelas/ranking_regime_atual.parquet` (**72** linhas = 3 lentes × 24 ativos: `lente`, `regime`, `asset_id`, `excesso_cdi`, `hit_ratio_cdi`, `n_obs`, `erro_padrao_media`, as 2 flags de `n`, `e_fallback`) · `tabelas/concordancia_lentes.parquet` · `regimes_v1{,_asof}.parquet` (`regime_v1`, `status_regime_v1`, `motivo_indeterminado`, `n_obs_regime_v1`) | **nenhum** — esta tela é idêntica para todos | resposta única como "o regime atual"; fallback `2026Q2` sem `e_fallback`; ranking sem `n`; ordenação que sugira escolha de lente (D1 é do Edu) |
| **T-02** Heatmap regime × ativo | **em cada regime, qual classe bateu o CDI e por quanto, com quantas observações.** `figuras/heatmap_dados.parquet` (**322 × 32**, o dado como plotado) + as 3 tabelas `regime_asset_metrics{,_asof,_horizonte_cruzado}.parquet` (**120/96/120**; PK `(lente, regime, asset_id)`; as 17 métricas de `CONTRACTS §4.1` + as 2 flags de `n` + `data_inicio_serie`). **Interação:** *hover* com erro-padrão, `hit_ratio_cdi`, mediana, `pior_tri` e flags (hoje o `<title>` do SVG); **clique abre o detalhe do par** com os trimestres da célula | lente · materialização · horizonte (**T0**/**T+1**) · classe de ativo · métrica (excesso CDI / nominal / real — as três já são colunas) | `SP500_USD` na figura (USD contra CDI em BRL mistura moedas — Anti-SPEC §10.2.12; a linha **continua** nas tabelas); escala divergente **assimétrica** (o cinza do meio deixaria de significar "empatou"); **verde/vermelho** (colapsa em protanopia/deuteranopia); cor divergente com `n<5`; célula sem `n`; **ordenar linhas por desempenho** (a ordem é declarada; `CDI` fecha em zero, como *sanity check*); **ordenar por média sem exibir a dispersão** `[arq §7.3]` |
| **T-03** Momentos semelhantes | **quais trimestres se parecem com este, e o que rendeu no trimestre SEGUINTE a cada um.** `regime_neighbors_v3.parquet` (**9.692 × 21**; PK `(quarter_ref, rank, metrica, k_usado, restrito_pos_2016, somente_passado)`; `quarter_neighbor`, `distancia`, `n_features` (= 5, declarado na linha), `quarter_t_mais_1`, `n_vizinhos`, `regime_v1_neighbor` + `status_`) × `asset_returns_quarterly` por `quarter_t_mais_1` | referência (**qualquer** dos 77 com vetor completo) · `k` em **5/8/12** · **Mahalanobis** (Ledoit-Wolf, `rho=0,259874`) × **Euclidiana** · `somente_passado` · `restrito_pos_2016` | `regime_neighbors.parquet` (variante de contrato) no lugar da lente — perde **4 dos 8** vizinhos de `2026Q3`; dizer "6 features" (rodam **5**: `termos_troca_yoy` é 100% nula e foi **cortada**); dizer que `somente_passado` elimina todo look-ahead (elimina seleção e padronização, **não safra**); citar o Jaccard de `2026Q3` (=1,0) como evidência — é **vácuo** por construção |
| **T-04** Timeline de regimes | **a classificação faz sentido para quem viveu o período, e onde `asof` e `revised` discordam.** `figuras/timeline_regimes_dados.parquet` (**166 × 14** = 83 trimestres × 2 materializações) · `regimes_v1{,_asof}.parquet` (`regime_v1`, `status_regime_v1`, `trocou_vs_revised`) · `macro_quarterly.parquet` (`selic_meta_fim`, em **%**) · `asset_returns_quarterly` (IBOV, em **fração**) | materialização (`revised`/`asof`/as duas) · marcar as divergências | **eixo y duplo** (a posição relativa das curvas viraria artefato da escala — são 2 painéis empilhados, faixa de regime **dentro** de cada painel); `INDETERMINADO` como 5ª cor categórica (é ausência **rotulada**, não buraco); a `asof` sem a ressalva de CA-074 |
| **T-05** Ativo em foco | **como ESTE ativo se comportou em cada regime — distribuição, acerto e pior caso.** `asset_returns_quarterly.parquet` (`ret_tri`, `ret_excesso_cdi`, `ret_real`, `is_total_return`, `ffill_dias_uteis`, `data_inicio_serie`, `source`, `series_id`) × `regimes_v1.parquet` · agregados de `regime_asset_metrics.parquet` | ativo (24) · lente · materialização · métrica · janela (cheia / pós-2016) | Sharpe como implementável (índice não é ativo investível: zero taxa, corretagem, *spread*, imposto, custo de rebalanceamento); **max-drawdown encadeado** — o regime não é contíguo (`RECUPERACAO` são 19 trimestres em **11 blocos**) e encadear daria número que nenhuma carteira viveu; comparar `is_total_return = True` contra `False` sem a flag ao lado (**nula em 820 linhas** — os 9 setoriais da B3, gap G-01, + o CDI) |
| **T-06** Internacional | **o internacional em BRL rendeu o que em cada regime, o câmbio protege quando dói, e que FAIXA o dado sustenta.** `internacional_por_regime.parquet` (**54 × 18**; PK `(lente, regime, asset_id)`, `lente ∈ {V1, V1_ASOF, V3}`; retorno **importado inteiro** de F-022 + 2 correlações + `n_pares`) · `relatorio_internacional.json` | lente · ativo internacional · bloco de correlação (stress / não stress / janela cheia / 10 piores do IBOV) | **a tabela de variância mínima** — `internacional_pesos.parquet` é `publicavel: false` (**D-af**, Anti-SPEC §10.3.16/§10.5 → F-035) e o exportador **não emite a visão**; número **pontual** de alocação (muda de **10,4%** para **19,7%** conforme uma restrição de apresentação — daí a **faixa**); `GOLD_BRL`, `UST10_BRL` e `SP500_HEDGE` com proxy; misturar **hedgeado** com **exposição cambial** (2,5-7% é global hedgeado, 16-35% é cambial) |
| **T-07** Dados e limitações | **de onde veio cada número, o que ele não sustenta, e o que ainda não foi decidido.** `series_catalog.parquet` (**138 × 26**; `series_id`, `fonte_url`, `data_inicio` **declarada** ao lado de `data_inicio_observada`, `freq`, `unit`, `status`, `lag_divulgacao_dias`) · `MANIFEST.json` (por artefato: `sha256`, linhas, colunas, min/max de data, **% de nulos por coluna**, `determinista`, `publicavel`, `motivo_nao_publicavel`) · `FROZEN.txt` · `LIMITACOES-COMITE.md` · status dos 7 ADRs em disco | bloco do e-mail (A1-A7/B1-B5/C1) · status (entregue / com ressalva / substituída / fora) · fonte | série "a confirmar" como `ok`; `data_inicio` declarada **no lugar** da observada (a divergência é informação, e 3 checks impedem copiar uma na outra); limitação em acordeão fechado |

### T-01 · Visão geral — "Em que regime estamos?"

```
+---------------------------------------------------------------------+
| LDC Analytics > Alocacao Macro > Em que regime estamos?             |
| ~ MATERIAL DE DISCUSSAO -- espec. nao congelada (ADR-001) ~         |
| fc233118... | tag comite-2026-10-14 | 83 tri 2006Q1-2026Q3         |
+--------------------+-------------------+----------------------+
| V1 revised 2026Q3  | V1 asof 2026Q3    | V3 VIZINHOS_2026Q3   |
| INDETERMINADO      | DESACELERACAO n13 | 8 vizinhos n = 4 a 8 |
| motivo GAP_AUSENTE | /!\ troca de rot. | retorno medido em    |
| fallback 2026Q2    |  vs revised 33,33%|  T+1                 |
| ESTAGFLACAO n=16   |  (22/66)          |                      |
| top-5: SP500_BRL   | top-5: IDIV +5,95 | top-5: INDX +5,04 n8 |
| +3,60 n16, ACWI_BRL| n13, UTIL +5,74   | (ep 2,54), ACWI_BRL  |
| +3,19 n16, ... (5) | n13, ... (5)      | +3,78 n8, ... (5)    |
+--------------------+-------------------+----------------------+
| INTERSECAO DOS TOP-5 DAS TRES LENTES: [ ] vazia. Jaccard 0,25 /     |
| 0,111 / 0,0 . Spearman V1rev x V1asof -0,748. V1 x V3 nas 61 refs:  |
| mediana 0,111, 17 com zero, NENHUMA identica em 20 anos.            |
+---------------------------------------------------------------------+
```

### T-02 · Heatmap regime × ativo (interativo)

```
+---------------------------------------------------------------------+
| Heatmap regime x ativo  ~espec. nao congelada~  fc233118...         |
| Lente [V1 revised v] Materializ. [revised v] Horizonte [T0 v]      |
| Classe [x]RF [x]Acoes [x]Setoriais [x]FII [x]Intl [x]Cambio [x]CDI |
| Metrica [excesso CDI v]   23 linhas . 115 celulas                  |
+---------------------------------------------------------------------+
|                RECUPER. EXPANSAO ESTAGFL. DESACEL.|VIZINHOS_2026Q3  |
|                  n=19     n=19     n=16    n=13   |   n=8           |
| RF    IMAB      ##+1,05  #-0,83   #+0,13 ##+1,13  | #+0,9  n8       |
| ACOES IBOV       #+0,81  #-1,02 ###-4,56 ###+5,20 | #+1,1  n8       |
| SETOR UTIL         ...      ...      ...####+8,23 |  ...            |
| SETOR IMOB     ###+6,30    ...  ###-6,90   ...    | //prelim -6,5 n4|
| SETOR ICON         ...      ...      ...   ...    | *-0,4  n6 ALERTA|
| FII   IFIX      #+0,3 n16 #+0,2n17   ...   ...    | //prelim     n4 |
| INTL  ACWI/SP500 #+0,22 ##+3,37 ##+3,19 #+1,71    | ##+3,78 n8      |
| CAMB  USDBRL     #-1,63  #+0,28  #+1,94 #-2,56    |  ...            |
| BENCH CDI          0,00    0,00    0,00   0,00    |  0,00           |
+---------------------------------------------------------------------+
| # azul bateu o CDI . # vermelho perdeu . escala simetrica +/-extr.  |
| * 5<=n<8 alerta (tracejado) . // n<5 SEM CONCLUSAO (hachurado)      |
+---------------------------------------------------------------------+
```

### T-03 · Momentos semelhantes

```
+---------------------------------------------------------------------+
| Momentos semelhantes  ~espec. nao congelada~  fc233118...           |
| Referencia [2026Q3 v] k [ 5 (8) 12 ] Metrica [Mahalanobis v]       |
| [x] somente passado [ ] restrito pos-2016  5 features (de 6)       |
+---------------------------------------------------------------------+
| rank| vizinho| distancia| quadrante V1  | T+1   | ret T+1 por ativo |
|  1  | 2006Q3 |   0,91   | INDETERMINADO | 2006Q4| ...               |
|  2  | 2006Q4 |   1,04   | INDETERMINADO | 2007Q1| ...               |
|  3  | 2006Q1 |   1,12   | INDETERMINADO | 2006Q2| ...               |
|  4  | 2024Q3 |   1,20   | (Selic: ALTA) | 2024Q4| ...               |
| 5-8 | 2014Q4 . 2007Q1 . 2024Q2 . 2014Q3 | 1,33 a 1,60 | T+1 idem    |
+---------------------------------------------------------------------+
| Ranking em T+1 (excesso CDI, n, barra de erro): INDX +5,04% n8      |
| |---o---| . ACWI_BRL +3,78% n8 |--o--| . SP500_BRL +3,41% n8 .      |
| IMOB //sem conclusao (n=4). NENHUMA passa de 2 ep: a ORDEM nao e    |
| distinguivel de ruido. 4 dos 8 vizinhos sem quadrante V1 (D-m).     |
+---------------------------------------------------------------------+
```

### T-04 · Timeline de regimes sobre IBOV e Selic

```
+---------------------------------------------------------------------+
| Timeline 2006Q1-2026Q3  Materializ. [as duas v] [x] divergencias   |
| IBOV (fracao, base 2006Q1)                                         |
|   /\     /\        /\       /\      /\                             |
|  /  \/\ /  \/\  /\/  \ /\  /  \/\ //  \/                           |
|  //////|REC|EXP|EST|DES|REC|EXP|///////|REC|EST| <- faixa V1       |
+---------------------------------------------------------------------+
| Selic meta fim de periodo (% a.a.)                                 |
| 19 \__   __/--\__          __/--\___/--\  14%                      |
|     \__/-/      \___2%___/--/                                      |
|  //////|REC|EXP|EST|DES|REC|EXP|///////|REC|EST|                   |
|  2006   2009  2012 2015 2018 2021  2024   2026Q3                   |
+---------------------------------------------------------------------+
| v asof x revised: 22 de 66 = 33,33%, acima do limiar de 25%        |
| // INDETERMINADO: 16 tri (2006Q1-2009Q3 + 2026Q3), hachurados      |
| revised: REC 19 . EXP 19 . EST 16 . DES 13 (desbal. 1,46x)         |
+---------------------------------------------------------------------+
```

### T-05 · Ativo em foco

```
+---------------------------------------------------------------------+
| Ativo em foco [IMOB v] Lente [V1 revised v] Janela [cheia v]       |
| data_inicio 2008Q1 . 75 tri . is_total_return A CONFIRMAR          |
+---------------------------------------------------------------------+
| Retorno trimestral por regime (1 ponto = 1 trimestre)              |
| RECUPERACAO   n19 |   . ..:|::. . | media +6,30%  hit_cdi 0,74     |
| EXPANSAO_INFL n19 | . .:|:. ..    | media  ...    hit_cdi  ...     |
| ESTAGFLACAO   n16 |. .:|:. .      | media -6,90%  hit_cdi 0,31     |
| DESACELERACAO n13 |   ..:|:..     | media  ...    hit_cdi  ...     |
|                   +----0----+ excesso sobre CDI (FRACAO)           |
+---------------------------------------------------------------------+
| Pior tri por regime, com data: RECUPERACAO -45,46% em 2020Q1 |      |
| ESTAGFLACAO -17,69% em 2011Q3. ep 2,1 a 6,01 pp. Em                |
| VIZINHOS_2026Q3 o IMOB tem n=4: SEM CONCLUSAO.                     |
+---------------------------------------------------------------------+
```

### T-06 · Internacional

```
+---------------------------------------------------------------------+
| Internacional ~espec. nao congelada~ (ADR-003 Proposta, D6 aberta) |
| Lente [V1 revised v] Bloco [stress x nao stress v]                 |
+---------------------------------------------------------------------+
| Regime        | n |ACWI_BRL|SP500_BRL|USDBRL| IBOV |corr(USD,IBOV)  |
| RECUPERACAO   |19 | +0,22% | +0,30% |-1,63%|+0,81%|  -0,797        |
| EXPANSAO_INFL |19 | +3,37% | +4,25% |+0,28%|-1,02%|  -0,791        |
| ESTAGFLACAO   |16 | +3,19% | +3,60% |+1,94%|-4,56%|  -0,464        |
| DESACELERACAO |13 | +1,71% | +2,29% |-2,56%|+5,20%|  -0,393        |
+---------------------------------------------------------------------+
| corr(USDBRL,IBOV) com n: stress (20) -0,795 || nao stress (62)     |
| -0,418 || cheia (82) -0,710 || 10 piores do IBOV -0,625 => o hedge |
| vale ~2x mais NO stress. 43,0% de USD zera o retorno MEDIO nos 20  |
| tri de stress (nao e otimizacao nem backtest).                     |
+---------------------------------------------------------------------+
| Faixa de D6 (nunca um ponto): piso 16-20% | banda tatica 15-35%    |
|   [====|##############|==============]                             |
| Stress: 20 de 83 (7 inclinacao . 11 cambio . 2 ambos). 14 tri NAO  |
| AVALIAVEIS pelo ramo 1, nomeados. Ramo risco-pais FORA (0 valores).|
+---------------------------------------------------------------------+
```

### T-07 · Dados e limitações

```
+---------------------------------------------------------------------+
| Dados e limitacoes . DATASET_SHA256 fc2331183b9355e6... .           |
| 48 artefatos . ADR-001 Proposta (GATE FECHADO) . 007 ACEITA         |
+---------------------------------------------------------------------+
| Catalogo [bloco: todos v] [status: todos v]     138 series         |
| serie       | fonte     | inicio decl| inicio obs| freq | unidade  |
| SGS_433 IPCA| BCB SGS   | 2006-01    | 2006-01   |  M   | %        |
| IMAB        | ANBIMA S3 | 2003-09    | 2003-09   |  D   | indice   |
| IBOV / IFIX | API B3    | 2006-01 / 2011-01      |  D   | indice   |
|   62 presentes de 138 . 59 cobrem 1T2006. Pedido x entregue: 11    |
|   entregues . 1 substituida (A6) . 1 fora (B5b) . 1 parcial (C1)   |
+---------------------------------------------------------------------+
| As 10 limitacoes, cada uma abrindo com o numero medido: 1 n pequeno |
| 13-19 obs/regime (erro 2,8-4,2 pp/tri) | 2 look-ahead 22/66 =      |
| 33,33% | 3 janelas proprias ICON 2007, IMOB 2008, IFIX 2011 | 4    |
| quebra estrutural Selic 19%->2%->2 digitos | 5 indice nao e        |
| investivel, zero custo | 6 16 tri sem quadrante, inclusive a crise |
| de 2008 e 2026Q3 | 7 is_total_return indefinido em 820 linhas | 8  |
| janela do CDI difere do ativo em 599/1.857 (max 0,1575 pp) | 9     |
| unidades diferentes, erro de 100x | 10 vintage unico: o look-ahead |
| publicado e um PISO. + as 12 decisoes, com recomendacao e custo.   |
+---------------------------------------------------------------------+
```

---

## 5. Requisitos funcionais

**Pri:** M = must (MVP), S = should (v2).

### 5.1 Shell e catálogo de módulos

| RF | Requisito verificável | Pri |
|---|---|---|
| RF-W001 | Cabeçalho/rodapé em **toda** rota com produto, módulo, tela, `DATASET_SHA256` (12 chars, clicável para o completo), tag e janela do dataset; breadcrumb e rota legível (`/alocacao-macro/heatmap`) | M |
| RF-W002 | **Faixa do gate** fixa no topo de toda tela enquanto `especificacao_congelada = false`, **não dispensável por clique**; some sem alteração de código quando virar `true` | M |
| RF-W003 | **Estado dos filtros na URL**: a URL de uma tela filtrada reproduz a tela — é o que substitui o print no WhatsApp | M |
| RF-W004 | *Empty state* e erro em linguagem descritiva, aprovados pela guarda única (`_linguagem.py`) — **texto de UI também**, não só de dado | M |
| RF-W005 | `<NConclusao/>`, `<UnidadeBadge/>` e barra de erro como **primitivas do shell**, não escolha de cada tela | M |
| RF-W006 | Home = **catálogo de módulos**: por módulo, nome, a pergunta que responde, dataset lido (com hash), data do dado, `versao_build` que o gerou e **status do gate** — para "o portal está desatualizado" ser visível em vez de suposto | M |
| RF-W007 | **Registry declarativo**: acrescentar módulo = manifesto + pasta de rotas, **sem** tocar o shell — o espelho do `pkgutil` que `run.py` já usa para descobrir figuras e tabelas; e cada módulo declara o **seu** gate (ADR em `Proposta` nasce marcado, sem afetar os outros) | M |
| RF-W008 | Tema claro/escuro, busca global (ativo, trimestre, série) e módulo `oculto` no manifesto (sem cartão e sem rota) | S |

### 5.2 Dados e versionamento · **seção técnica**

| RF | Requisito verificável | Pri |
|---|---|---|
| RF-W009 | **`apps/web_export/`**: comando Python que lê o `MANIFEST.json` **já congelado** e emite `public/data/<tag>/` com `manifest.json` + **um JSON por visão** (regimes, heatmap, ranking, vizinhos, internacional, macro). É a **única** ponte pipeline → portal, e tem contrato `[arq §1.1, §6.2]` | M |
| RF-W010 | O exportador **não emite** visão de artefato `publicavel: false`; a lista de inclusão **não vence o manifesto** (o princípio de F-031). **O gate é do exportador, não do front** `[arq §7.1]` | M |
| RF-W011 | Dado sob caminho que **contém a tag**, `immutable`, **nunca** sobrescrito; **um** ponteiro `current.json` com `no-cache`; tag **fixada por sessão**; o portal **recusa renderizar** se o manifest divergir `[arq §7.2]` | M |
| RF-W012 | O portal valida que o hash do dado lido bate com `manifest.json`; divergência é **erro de tela**, não aviso silencioso | M |
| RF-W013 | Contrato de dados em **JSON Schema** gerado dos schemas pydantic do exportador → **tipos TypeScript**; campo ausente ou extra levanta erro nomeando campo e visão | M |
| RF-W014 | **Nenhuma conversão de unidade no front**: conversão só em `web_export`, unidade no JSON **por campo**, `<UnidadeBadge/>` em todo eixo | M |
| RF-W015 | O portal **não** consome `internacional_pesos`, `raw_series`, os `*_provenance`, `regime_neighbors` (variante de contrato) nem `ldc.duckdb` — teste de CI que **falha** se algum aparecer no dataset publicado | M |
| RF-W016 | **Zero cálculo de metodologia no cliente**: teste que varre o código e reprova agregação (`mean`, `sum`, `groupBy`, `corr`, `quantile`, …) sobre campo de retorno — o análogo do teste de AST de F-027 | M |
| RF-W017 | `web_export` **determinístico e sem rede**: duas execuções → mesmos bytes; CI valida schema + hash + ausência de campo não publicável, **offline** | M |
| RF-W018 | Página **"Versões do dataset"** (histórico de tags e hashes, estilo *releases* do BIS `[arq §5]`); dataset antigo acessível mas **marcado em vermelho** | S |

### 5.3 Telas do módulo 1

| RF | Requisito verificável | Tela | Pri |
|---|---|---|---|
| RF-W019 | As **3 respostas de regime** lado a lado, nenhuma escolhida, cada uma com `n` e com a pergunta que responde; fallback `2026Q2` sempre rotulado (`e_fallback`), **nunca** "o regime atual" | T-01 | M |
| RF-W020 | Interseção dos top-5, Jaccard, Spearman e a **distribuição** de concordância nas 61 referências — não só o número do trimestre corrente | T-01 | M |
| RF-W021 | Heatmap com `n` **em toda célula** (não em tooltip), valor dentro da célula, escala divergente **simétrica** em ±extremo, e os 3 estados de confiança cada um em **dois canais** (`n≥8` cor + número; `5≤n<8` cor + borda tracejada + `*`; `n<5` cinza hachurado + `prelim.`) | T-02 | M |
| RF-W022 | Filtros de lente, materialização, horizonte, classe e métrica, todos refletidos na URL | T-02 | M |
| RF-W023 | *Hover* com erro-padrão, `hit_ratio_cdi`, mediana, `pior_tri` e flags; **clique abre o detalhe do par** com os trimestres que compõem a célula | T-02 | M |
| RF-W024 | Rodapé do heatmap com `data_inicio` das 23 séries, a métrica **com a fórmula**, os 2 limiares de `n`, a faixa de erro-padrão e a exclusão de `SP500_USD` nomeada | T-02 | M |
| RF-W025 | Referência livre entre os **77** trimestres com vetor completo; `k` em **5/8/12**; Mahalanobis × Euclidiana; `somente_passado`; `restrito_pos_2016` | T-03 | M |
| RF-W026 | Lista dos k vizinhos com **distância**, quadrante V1 (ou o motivo de não ter) e `quarter_t_mais_1` | T-03 | M |
| RF-W027 | Ranking nos trimestres **seguintes** com `n`, **barra de erro no gráfico** e as 2 flags; agrupamento por faixa em vez de 1º/2º/3º | T-03 | M |
| RF-W028 | Declaração na tela de que rodam **5 features de 6** e do que `somente_passado` **não** elimina (safra) | T-03 | M |
| RF-W029 | Timeline em **2 painéis empilhados**, faixa de regime **dentro** de cada painel, nunca eixo y duplo; `INDETERMINADO` em cinza hachurado, com os 16 trimestres nomeáveis; as **22 divergências** `asof`×`revised` marcadas, com os 33,33% e o limiar de 25% no rodapé | T-04 | M |
| RF-W030 | Distribuição dos retornos **por regime**, ponto a ponto, média e mediana lado a lado; `hit_ratio` e `hit_ratio_cdi`; **pior trimestre com a data**; cabeçalho com `data_inicio_serie`, nº de trimestres, `source`/`series_id` e o estado de `is_total_return` | T-05 | M |
| RF-W031 | Internacional **em BRL** por regime, colunas importadas de F-022, `n` em toda célula; `corr(USDBRL, IBOV)` nos 4 blocos **sempre com `n` de pares** | T-06 | M |
| RF-W032 | Regra de stress aberta: 20 de 83 por ramo, **14 não avaliáveis nomeados**, ramo risco-país declaradamente fora; faixa de D6 como **faixa**, nunca ponto | T-06 | M |
| RF-W033 | Catálogo de séries com cobertura **declarada e observada** em colunas separadas, filtrável por bloco e status; hash, nº de artefatos, `versao_build` e status dos **7 ADRs** lidos do dado | T-07 | M |
| RF-W034 | As **10 limitações** como conteúdo de primeira classe, cada uma abrindo com o número medido; as **12 decisões** com recomendação e custo de discordar; a tabela "pedido × entregue" por item do e-mail | T-07 | M |
| RF-W035 | Toda tela abre com **uma** frase que é a pergunta que ela responde (P7) | T-01..07 | M |
| RF-W036 | **Quadrantes**: dispersão `g_score` × `pi_score` com trilha temporal (o *quadrant chart* do Macrobond `[arq §5]`) — a tela que mostra que o quadrante é **contínuo** antes de ser rótulo | T-08 | S |

### 5.4 Exportação, acesso e observabilidade · **seção técnica**

| RF | Requisito verificável | Pri |
|---|---|---|
| RF-W037 | **CSV do recorte visível**: exatamente as linhas e colunas na tela, com os filtros, `n` incluído, e cabeçalho com `DATASET_SHA256`, tag, filtros e data do dado | M |
| RF-W038 | **PNG do recorte visível**: a figura como está, com título, `n`, rodapé de cobertura e a faixa do gate — tem de ser legível **fora** do portal | M |
| RF-W039 | Nenhum arquivo exportado sai sem `n`, sem janela e sem hash — teste que varre os exportadores; e exportação **não recalcula nada** | M |
| RF-W040 | CSV em **duas convenções declaradas**, como no pacote: `pt-BR` (`;`, vírgula decimal, UTF-8 **com BOM**, LF) por padrão e `en` sob opção; XLSX por tabela | S |
| RF-W041 | O portal **não é público**: toda rota **e todo arquivo de dado** exige acesso autorizado, validado **na edge, antes do cache do CDN**. Proteger a rota e deixar o JSON aberto é o pior dos mundos | M |
| RF-W042 | **MVP: Vercel Authentication (SSO do time)**, projeto privado, `Standard Protection` ou `All Deployments` — **incluída em todos os planos**; revogação = remover a pessoa do time `[arq §3]`. Lista de acesso **explícita e nomeada**, versionada em arquivo: **identidade por pessoa > senha coletiva** | M |
| RF-W043 | Nenhum segredo no cliente; dataset publicado **não versionado** no repo do portal (`data/` segue fora do git) | M |
| RF-W044 | **Guardião de *prebuild*** espelhado no `verificar-identidade.mjs` `[ident §3]`, apontado a segredo/env: recusa o build se um segredo estiver com *placeholder* **e** for consumido por código que vai ao cliente; **falha ruidosamente quando perde a própria âncora**; valida **uso**, não valor; mais duro em produção que em preview | M |
| RF-W045 | **Guarda de rota no roteador**, nunca dentro de cada página. No `site-eduardo` a proteção é feita dentro da página e **4 páginas admin ficaram sem guarda nenhuma** `[ident §6]` — é o erro a não repetir | M |
| RF-W046 | Se houver autorização por papel: **tabela escrita apenas pelo `service_role` + função `SECURITY DEFINER`**, nunca `user_metadata` — gravável pelo próprio usuário via `updateUser` (lição da migration `014` `[ident §6]`) | S |
| RF-W047 | **Não fazer:** auth no front (o bundle já desceu); senha em `vercel.json` ou commitada; Cloudflare laranja na frente da Vercel sem Verified Proxy; montar Supabase/Clerk/Auth0 "já que vamos precisar depois" — põe credencial no caminho crítico e **promove a feature a classe D** sem entregar nada hoje `[arq §3]` | M |
| RF-W048 | *Health check* com hash e tag do dataset, data do dado, nº de artefatos, status do gate e versão do portal; **alerta de dataset envelhecido** quando o dado é de mais de um trimestre atrás | M |
| RF-W049 | Erro de carregamento **visível e nomeado** (qual visão, qual hash esperado), nunca tela em branco; **nenhuma telemetria de terceiro** com dado de alocação | M |
| RF-W050 | Linha em `docs/wiki/log.md` a cada publicação, com hash e tag, no formato da classe D; o rodapé do portal imprime **o mesmo** `DATASET_SHA256` que o `HASHES.txt` do pacote — para caderno e portal não divergirem `[arq §7.7]` | M |
| RF-W051 | *Runbook* de rollback: voltar ao hash anterior é trocar **um ponteiro** (`current.json`), porque o caminho de dado é imutável por tag | M |
| RF-W052 | Registro mínimo de uso (telas abertas, filtros), sem dado pessoal além do e-mail autorizado — é o que mede a métrica de autonomia (§8) | S |

**Total: 52 requisitos funcionais.**

---

## 6. Requisitos não funcionais

| RNF | Requisito | Como se verifica |
|---|---|---|
| RNF-W001 | **Carregamento inicial < 3 s em 4G** até a primeira tela útil (T-01) | orçamento no CI, conexão simulada. O dado de apresentação cabe em **200-400 KB (60-120 KB gzip)** `[arq §1.1]` e T-01 lê só duas visões pequenas |
| RNF-W002 | **Bundle < 1 MB sem os dados** (comprimido), dado carregado por visão | teto que **falha** o CI. É também o motivo de **rejeitar DuckDB-WASM na v1**: ~2,8 MB gzip + extensões, o engine pesando 5× o dataset `[arq §1]` |
| RNF-W003 | **Dataset por tag/hash imutável com cache longo**; ponteiro `current.json` com `no-cache` | RF-W012; conferido no *health check* |
| RNF-W004 | **Funciona offline depois do primeiro load** (opcional, v2) | *service worker* com cache por tag — o caminho imutável é o que torna isso correto |
| RNF-W005 | **Acessibilidade AA**: contraste ≥ 4,5:1 em texto e ≥ 3:1 em elemento gráfico; teclado completo; `n` e confiança **nunca** só por cor | auditoria no CI + o validador de paleta do pipeline (`validate_palette.py`: pior ΔE protan **14,7**) |
| RNF-W006 | **Responsivo**: T-01, T-03 e T-07 úteis em 375 px; heatmap em celular é lista ordenável por regime, não grade apertada | requisito, não cortesia — o Alexandre abre no celular antes da reunião |
| RNF-W007 | **Sem dado sensível em repositório público**; nada > 5 MB versionado; `noindex`, sem sitemap, preview protegido | `git status` limpo após publicar; varredura no CI |
| RNF-W008 | **Determinismo** do dataset publicado | o pipeline já prova 2 rodadas byte-idênticas em 47 artefatos; o exportador herda a obrigação |
| RNF-W009 | **Zero cálculo de metodologia no cliente** (é RNF, não só RF) | RF-W017 + amostra de célula conferida contra o Parquet no CI |
| RNF-W010 | **Degradação honesta**: dado ausente aparece como ausente rotulada; nunca célula vazia renderizada como zero | teste por tela com dataset mutilado |
| RNF-W011 | Publicar um dataset novo ≤ **10 min** do `freeze` ao portal servindo a tag nova, **sem deploy de código** | medido no runbook |
| RNF-W012 | **Custo de infraestrutura ≈ zero** na escala de ~5 leitores: estático + JSON por tag + auth incluída no plano `[arq §3]` | orçamento mensal no runbook |

---

## 7. Modelo de extensão — como entra o módulo 2 · **seção técnica**

**Registry declarativo.** O catálogo é gerado de um registry; acrescentar módulo é acrescentar um
manifesto e uma pasta de rotas, e o shell não muda — o padrão que o pipeline já usa com `pkgutil`
em `run.py`.

| # | O contrato que um módulo precisa cumprir | Por quê |
|---|---|---|
| **1 · Manifesto** | `id`, `nome`, **a pergunta que responde**, telas, visões lidas, **ADR que o governa**, status do gate, `oculto` | é o que o catálogo mostra e o que o teste de contrato verifica |
| **2 · Rotas** | uma por tela, legível, com **filtro na URL**; nada fora do namespace do módulo | link reproduzível é o que substitui o print |
| **3 · Visões** | emitidas por `web_export`, só de artefato `publicavel: true`, com JSON Schema e tipo TS gerados | RF-W010/W011/W014/W016 |
| **4 · Testes** | (a) contrato de campos; (b) **zero cálculo de metodologia** (AST); (c) `n` em toda célula renderizada; (d) guarda de linguagem em **todo** texto; (e) exportador com `n` + janela + hash; (f) amostra conferida contra o Parquet | sem (b) e (c) o módulo pode publicar número que o pipeline não produziu |
| **5 · Gate próprio** | lê o status do **seu** ADR em disco, falha fechada, nasce marcado se `Proposta` | um módulo destravado não destrava os outros |
| **6 · Limitações próprias** | todo módulo tem a sua T-07 | é a condição para ser publicável sob a classe D |

Módulo que não cumpre os 6 entra como `oculto`. **Três ideias de próximos módulos** (5 a 9
dias-agente cada, com a infra paga `[arq §8]`): **M2 · Simulador de carteira por regime** — o usuário
monta uma carteira com os 24 ativos e vê como ela **se comportou** em cada regime, com `n` por
célula; descritivo, sem otimização nem retorno esperado (consumidor natural de F-035). **M3 ·
Projeção de IPCA e Selic a partir do Focus** — mostra o que o **mercado** projeta (28.182 coletas,
5 séries, 2004→2026, já extraídas) e, ao lado, **o quanto essa projeção errou** por horizonte: o
módulo não projeta, publica a projeção de terceiro e mede o erro. **M4 · Validador de tese** — o
usuário escreve uma afirmação testável ("IMA-B bate o CDI em estagflação") e recebe número, `n`,
erro-padrão e veredito, incluindo "**não distinguível de ruído**", que com `n` de 13 a 19 é a
resposta mais frequente e a mais útil.

> **Ressalva estrutural para M2 e M3** `[arq §8]`: eles precisam de **cálculo com input do usuário**,
> e site estático não faz isso. Ordem de preferência: (i) **cálculo no browser** com os parâmetros em
> memória — viável com 83 linhas; (ii) **uma função serverless só para o cálculo**, com o dado ainda
> vindo do CDN, ao custo de auth, *cold start* e um ADR. **Nunca** (iii) o front reimplementando a
> convenção de retorno: isso é **classe C** e mora no pipeline.

---

## 8. Métricas de sucesso

| Métrica | Meta | Como medir |
|---|---|---|
| **Autonomia do Alexandre** | responde **as 5 perguntas abaixo sozinho**, sem pedir nada ao Edu | confirmação explícita dele + registro de uso (RF-W052) |
| **Tempo até a primeira resposta** | **< 2 min** do abrir o portal à resposta da pergunta 1 | cronometrado com o Alexandre, 1 sessão por trimestre |
| **Zero número publicado sem `n`** | **0** células, tabelas, figuras e exports sem `n` | teste que varre toda tela renderizada e todo exportador (RF-W041) |
| Divergência portal × pipeline | **0** números diferentes | amostra de células conferida contra o Parquet no CI |
| Mensagens ao Edu pedindo recorte | queda ≥ 80% vs. o trimestre do Comitê | contagem manual, 1 linha por trimestre em `wiki/log.md` |
| Custo de entrar com o módulo 2 | **0** linha alterada no shell | o PR do módulo 2 não toca o shell |

**As 5 perguntas-chave que o Alexandre precisa responder sozinho:** (1) **em que regime estamos**, e
por que as três lentes discordam? (T-01); (2) **neste regime, o que bateu o CDI e por quanto**, com
quantas observações? (T-02); (3) **quais trimestres se parecem com este, e o que rendeu no trimestre
seguinte a eles?** (T-03); (4) **quanto no exterior**, que faixa o dado sustenta e o câmbio protege
quando dói? (T-06); (5) **em que não se pode confiar** — `n`, janela e limitação? (T-05 + T-07).

---

## 9. Riscos priorizados

| # | Risco | P × I | Mitigação |
|---|---|---|---|
| **RW-01** | **Dado sensível exposto** — portal com alocação da casa vazado por link, por preview indexado ou commitado no git | Média × **Alto** | proteção **na edge, antes do CDN** (RF-W043/W044); o exportador **não emite** o não publicável; dataset fora do repo; guardião de prebuild (RF-W047); `noindex`; sem telemetria de terceiro. **O gate não é do front, é do exportador** |
| **RW-02** | **Leitura errada por `n` pequeno** — o portal torna trivial clicar até achar a célula que confirma a tese; com `n` de 4 a 19 e erro-padrão de 0 a 6,01 pp, quase toda ordem é ruído. "Uma UI com ranking numerado desfaz essa frase em um segundo" `[arq §7.3]` | **Alta** × **Alto** | `n` **na célula**, não em tooltip; **2 canais** por estado; `n<5` perde a cor divergente; **barra de erro no gráfico**; ranking **por faixa**, não 1º/2º/3º; proibido ordenar por média sem exibir dispersão; T-01 abre com a interseção **vazia** dos top-5 |
| **RW-03** | **Portal divergir do pipeline** — número na tela que o pipeline não produziu (arredondamento, recálculo "inofensivo", coluna errada, unidade trocada por 100×) | Média × **Alto** | P4 + RF-W017 (AST) + RF-W013 (hash) + RF-W014 (schema) + RF-W015 (unidade só no exportador) + amostra no CI. O portal lê `erro_padrao_media` **sabendo que ela é do retorno NOMINAL**, não do excesso (`INDX`: 2,54 contra 2,60 pp) — e declara isso, como a página de F-024. **CDN servindo versão velha** (heatmap de uma tag com ranking de outra) é o modo silencioso irmão: caminho por tag + `immutable`, **um** ponteiro `no-cache`, tag fixada por sessão e **recusa de render** se o manifest divergir (RF-W011) |
| **RW-04** | **Custo de manutenção** — portal que exige retrabalho a cada trimestre vira dívida e é abandonado; "só mais um gráfico" é a tentação | Média × Médio | dado separado do código e endereçado por tag: publicar dado **não é deploy** (RNF-W011); exportador determinístico de 1 comando; shell estável por contrato (§7); orçamento de bundle no CI; **nenhum** módulo entra sem o registry |
| **RW-05** | **Dependência de uma pessoa** — o Edu é o único que roda, publica, decide o publicável e manteria o portal. O portal **reduz** o gargalo de leitura e **cria** um de publicação | **Alta** × Médio | runbook com os comandos na ordem (`run → verify → freeze → web_export`); rollback por ponteiro (RF-W051); alerta de dataset envelhecido para a dívida ficar **visível**; contrato de módulo escrito para um segundo autor. **Não resolvido:** só o Edu aceita ADR e decide o publicável — isso é governança, não software |
| **RW-06** | **O portal ser lido como recomendação**, ou convidar a "achar padrão" (p-hacking com interface bonita) | Média × **Alto** | guarda de linguagem em **todo** texto de UI; nenhuma tela ordena por "melhor"; ordem das linhas **declarada**; `CDI` fecha a figura em zero; as visões são as que o pipeline emitiu e **todo corte novo passa por feature de pipeline**, com ADR se mexer na lente; faixa do gate enquanto ADR-001 estiver em `Proposta` |
| **RW-07** | **Reabertura silenciosa do ADR-007** — o portal aciona **2 dos 3** gatilhos de reavaliação ("dashboard multiusuário", "atualização consumida por outras pessoas") `[arq §7.6]` | **Alta** × Médio | escrever **ADR-008 — "LDC Analytics: site estático, dado congelado por tag, sem banco na v1"**, citando ADR-006/007, **antes da primeira linha de código**. Senão a decisão acontece por acidente |

---

## 10. Escopo da v1 (MVP) vs. v2 · e o esforço

**v0 — o atalho honesto (1 a 2 dias)** `[arq §8]`: publicar o **HTML executado do caderno atrás de
autenticação**. Zero infraestrutura nova, zero dependência, zero código de portal. **Se o objetivo
for apenas a reunião, é isto que se faz** — e só depois do ADR-001 aceito. Os 25 dias do MVP só se
justificam se houver módulos 2, 3 e 4.

**MVP — 4 telas, 1 módulo, ~25 dias-agente** (13 de infra reutilizável + 12 do módulo): **T-01**
Visão geral · **T-02** Heatmap com filtros, `n`, *hover* e clique no par · **T-03** Momentos
semelhantes · **T-07** Dados e limitações. Mais: **ADR-008 antes do código**; `apps/web_export/` com
gate, unidades, schemas e CLI; scaffold com **registry de módulos**; `core/dataset` (tag por sessão,
validação de manifest, cache); `core/gate` (faixa, `<NConclusao/>`, `<UnidadeBadge/>`, barras de
erro); wrappers de gráfico; Vercel Authentication + deploy; CI offline de validação do JSON. **Por
que estas 4:** T-01/T-02 são as perguntas 1, 2 e parte da 5; T-03 é a pergunta que o e-mail
literalmente faz; T-07 é a condição para qualquer número ser publicável. T-04, T-05 e T-06
enriquecem, nenhuma é pré-requisito das outras — e as três têm substituto imediato no pacote.

**v2:** **T-04** Timeline · **T-05** Ativo em foco · **T-06** Internacional · **T-08 Quadrantes** ·
offline após o primeiro load · tema escuro e busca global · página de versões do dataset · XLSX e CSV
em duas convenções · registro de uso · **módulo 2**.

**Fora de escopo, explícito — v1 e v2:** qualquer **recálculo de metodologia** no portal (P5);
**variância mínima, fronteira eficiente e otimização** (`internacional_pesos` é `publicavel: false`
por **D-af** + Anti-SPEC §10.3.16/§10.5 → **F-035**); **backtest, previsão, probabilidade de regime,
cenário**; **recomendação de alocação** ou "top 5 para comprar"; qualquer **versão pública**;
**entrada manual de dado** (o portal não tem escrita); **DuckDB-WASM, API serverless lendo Parquet e
banco remoto como fonte** — o dado de apresentação tem **610 KB** e a tabela principal **83 linhas**:
"consultar Parquet remoto sem baixar tudo" é resposta a uma pergunta que este projeto não tem
`[arq §0]`, e ADR-007 segue valendo (banco, se entrar, é materialização **a jusante**, nunca fonte);
**atualização automática do dataset** (publicar é ato humano, como a tag git); e **edição de ADR ou
de decisão pelo portal** (T-07 **mostra** o status; mudar é editar o arquivo).

---

## 11. Decisões pendentes para o Edu

| # | Decisão | Recomendação | Por que bloqueia |
|---|---|---|---|
| **DW-1** | **Nome do produto e domínio** (`LDC Analytics` / outro / subdomínio da casa / domínio próprio) | **`LDC Analytics`** em **subdomínio interno**, sem domínio novo e sem página pública | entra no shell, no cabeçalho de todo export e no manifesto de módulo; trocar depois é renomear em todo artefato exportado. ⚠️ **Divergência de pesquisa a resolver:** `[ident]` auditou o **`site-eduardo`** e concluiu que "não existe identidade visual da LDC". Eu `[apurado]` encontrei o **manual de marca LDC implementado** em `site-ldc/DESIGN.md` — navy `#262d3d`, slate `#577171`, lime `#98ab44`, alerta `#c0584f`, Ivy Mode/Public Sans, com papéis semânticos e lista de "banidos". **São dois repositórios diferentes, e o certo é o `site-ldc`.** Antes de escolher paleta, confirmar a fonte |
| **DW-2** | **Proteção de acesso** (Vercel Authentication / Password Protection / Cloudflare Pages + Access / Clerk, Auth0, Supabase Auth) | **Vercel Authentication no MVP** — incluída em todos os planos, revogação = remover do time. Se um membro do Comitê **não puder** ter conta Vercel, **mover o host para Cloudflare Pages + Access** (free até 50 usuários, identidade real, log) em vez de pagar US$ 20/mês/projeto por **senha coletiva** `[arq §3]` | RF-W043 é *must*: sem isso não há v1. Credencial ⇒ **classe D** por `AGENTS.md §2` |
| **DW-3** | **Dataset em repositório privado ou em blob** (repo privado / JSON por tag no deploy estático / blob dedicado / embutido no bundle) | **JSON por visão, por tag, no deploy estático**, gerado por `web_export` — são **200-400 KB** `[arq §1.1]`. Repo privado violaria RNF-009 do pipeline ("dados fora do git", nada > 5 MB); blob dedicado só se o dado crescer | define a arquitetura de publicação, o custo e o rollback. **Aqui o problema nunca foi volume: é versionamento, procedência e gate** |
| **DW-4** | **Quem mais acessa** (só Edu / Edu + Alexandre / + Comitê / + analistas) | **Edu + Alexandre na v1**; o Comitê entra depois do primeiro ciclo de uso real | define o mecanismo (DW-2 depende disto), a lista nomeada (RF-W045) e se "leitor passivo" é persona de verdade |
| **DW-5** | **O módulo 1 entra antes ou depois do Comitê de 2026-10-14** | **DEPOIS, sem exceção.** O pacote está montado, verificado e selado; o que falta é humano. Se o alvo é a reunião, **v0** (§10) resolve em 1-2 dias | define se este PRD é fase 2 ou caminho crítico. **Recomendação forte:** aprovar este PRD **depois** do Comitê, com o que a reunião ensinar sobre quais perguntas o Alexandre de fato faz |

**Duas decisões a mais que a pesquisa levanta e que valem resposta junto:** escrever o **ADR-008**
antes do código (recomendação: **sim** — o portal reabre o ADR-007 por construção, e deixar isso
implícito contraria o `AGENTS.md`); e **se o portal pode mostrar número enquanto o ADR-001 está em
`Proposta`** — tecnicamente sim, com a faixa de não publicável, **mas é decisão de classe D**. Se a
resposta for "não", o MVP se constrói contra um dataset de exemplo e só aponta para o real depois do
congelamento `[arq §10]`. **Decisões herdadas que o portal não pode responder:** as **12** de
`LIMITACOES-COMITE.md §7` (D1, D3, D5, D6, D12, L1, L2, L4, D-i, D-s, D-t, D-u) continuam do Edu e do
Comitê. Enquanto o **ADR-001** estiver em `Proposta`, o portal nasce marcado e **nada nele é
publicável** — pela mesma regra que trava o pacote hoje (`AGENTS.md §14`, CA-090, Anti-SPEC §10.3.18).

---

## 12. Aprovação

- [x] Problema ancorado no que o pipeline **já produziu**; nenhum número estimado neste documento
- [x] **52 RFs verificáveis** + 12 RNFs; 7 telas com wireframe, fonte de dado, filtros e proibições;
      modelo de extensão com contrato de 6 itens, 3 ideias de módulo e a ressalva de cálculo
- [x] v0 (1-2 dias) × MVP de 4 telas (~25 dias-agente) × v2, com fora-de-escopo explícito; 7 riscos
      com mitigação; 5 decisões para o Edu + 2 levantadas pela pesquisa
- [x] **Declarado que o portal é fase 2 e não substitui a entrega de 2026-10-14**
- [ ] **PRD aprovado por Eduardo (Edu)** · **DW-1..DW-5 respondidas** · **a divergência de identidade
      de DW-1 resolvida** (`site-eduardo` × `site-ldc`) · **ADR-008 escrito e aceito** (pré-requisito
      da primeira linha de código) — todos pendentes

> **Atenção:** este PRD foi gerado em modo autônomo, sem sessão de discovery com humano. Ele **não é
> propriedade do agente**: nenhuma seção pode ser alterada por agente após a aprovação sem nova
> autorização humana (`AGENTS.md §8`).

*Linguagem descritiva por contrato (Anti-SPEC §10.2.10): este documento, como todo o material do
projeto, descreve o que o histórico mostra. Nunca o que vai render.*
