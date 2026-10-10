# Inventário operacional de fontes de dados — Estratégia Macro LDC

> **Objetivo deste documento.** Servir de especificação de entrada para quem vai codar os extratores
> Python. Para cada item do escopo (`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`) registra-se: fonte oficial,
> endpoint exato, identificador da série, frequência nativa, início do histórico, autenticação/custo,
> limites, formato de resposta, pegadinhas e fallback.
>
> **Janela-alvo:** 2006-01-01 → 2026-10-10, agregável em trimestres.
> **Data da pesquisa:** 2026-10-10.

## Convenção de confiança (ler antes de usar)

| Marca | Significado |
|---|---|
| **[CONFIRMADO]** | Acessei o endpoint nesta pesquisa: HTTP 200 + conteúdo inspecionado. Valores e datas citados foram lidos da resposta real. |
| **[CONFIRMADO-SUB]** | Confirmado por acesso real, porém por agente de pesquisa auxiliar desta mesma sessão (não re-testado por mim, salvo onde indicado). |
| **[NÃO VERIFICADO]** | Conhecimento de fundo / inferência. **Validar antes de codar.** |
| **a confirmar** | Não consegui confirmar. Não inventei código/URL. |

---

# BLOCO A — INDICADORES MACROECONÔMICOS

## A1. BCB SGS — API REST de séries temporais

### Acesso

```
GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
      ?formato=json|csv
      &dataInicial=dd/mm/aaaa
      &dataFinal=dd/mm/aaaa

GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}?formato=json
```

- **Autenticação:** nenhuma. **Custo:** zero. **[CONFIRMADO]**
- **Formato JSON:** `[{"data":"01/09/2026","valor":"0.82"}, ...]` — `data` em `dd/mm/aaaa`, `valor` **string** com
  **ponto** decimal. **[CONFIRMADO]**
- **Formato CSV:** separador `;`, campos entre aspas duplas, decimal **vírgula**:
  `"data";"valor"` / `"01/01/2006";"0,59"`. **[CONFIRMADO]** — prefira JSON, é menos ambíguo.
- **Limite de taxa:** não documentado. Teste real: **40 requisições em paralelo (20 threads) → 40× HTTP 200
  em 1,38 s**, sem throttling. **[CONFIRMADO]** Ainda assim, implemente retry com backoff: o serviço é
  conhecido por instabilidades intermitentes (502/503) fora do horário comercial. **[NÃO VERIFICADO]**

### Pegadinha nº 1 — janela de 10 anos em séries diárias **[CONFIRMADO]**

Séries de periodicidade **diária** rejeitam janelas acima de ~10 anos com HTTP 200 + corpo de erro
(não é status de erro! o extrator precisa checar o shape da resposta):

```json
{"error":"O sistema aceita uma janela de consulta de, no máximo, 10 anos em séries de periodicidade diária",
 "message":"...é necessário informar a dataInicial...","syntax":"..."}
```

Testes feitos:
- `11` com `01/01/2006`→`31/12/2015` (10 anos) → **OK, 2.512 observações**.
- `11` com `01/01/2006`→`01/01/2016` (10 anos + 1 dia) → **OK**.
- `11` com `01/01/1980`→`31/12/1990` (11 anos) → **erro acima**.

→ **Regra de implementação:** fatiar séries diárias em blocos de **≤ 10 anos** (use 5 anos por segurança) e
concatenar. Séries mensais/trimestrais **não** têm esse limite: `433` sem parâmetros devolveu a série
completa, **561 observações de 01/1980 a 09/2026**. **[CONFIRMADO]**

### Pegadinha nº 2 — não existe endpoint de metadados **[CONFIRMADO]**

- `https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/metadados` → **404**.
- `https://www3.bcb.gov.br/sgspub/...` (a interface de consulta do SGS) → **HTTP 502 para `curl`**, mesmo com
  User-Agent de browser. **Não é scrapável.**
- **Caminho que funciona para resolver NOMES de série:** o portal de dados abertos do BCB (CKAN), que
  **exige User-Agent de browser** (sem UA devolve "Requisição Inválida"):
  ```
  GET https://dadosabertos.bcb.gov.br/api/3/action/package_list
  GET https://dadosabertos.bcb.gov.br/api/3/action/package_search?q={texto}&rows=10
  ```
  Os nomes dos pacotes são `"{codigoSGS}-{nome-da-serie-slug}"`. **4.261 pacotes** — é um **subconjunto** do
  SGS (não tem 433, 12, 13522 etc.), então serve para confirmar nomes, **não** para provar ausência. **[CONFIRMADO]**

### Séries confirmadas

Todas as linhas abaixo foram testadas por requisição real. "Nome oficial" marcado [CKAN] veio do
`package_list` do portal de dados abertos do BCB.

| Código | Nome | Freq. | Cobre 2006? | Verificação |
|---|---|---|---|---|
| **433** | IPCA — variação mensal (%) | mensal | **Sim** (série de 01/1980) | **[CONFIRMADO]** Idêntico a SIDRA 1737 v63: ago/26 `-0.32`, set/26 `0.82` em ambas as fontes |
| **13522** | IPCA — acumulado em 12 meses (%) | mensal | **Sim** (12/1980) | **[CONFIRMADO]** Idêntico a SIDRA 1737 v2265: ago/26 `4.22`, set/26 `4.58` |
| **11** | "Taxa de juros — Selic" [CKAN] — Selic over **% ao dia** | diária | **Sim** | **[CONFIRMADO]** 03/01/2005 = `0.064826` |
| **1178** | "Taxa de juros — Selic anualizada base 252" [CKAN] | diária | **Sim** | **[CONFIRMADO]** 09/10/2026 = `13.65` ← **use esta para Selic over em % a.a.** |
| **432** | "Taxa de juros — Meta Selic definida pelo Copom" [CKAN] | diária | **Sim** | **[CONFIRMADO]** 2006 = `18.00`. ⚠️ Último ponto vem **com data futura** (`04/11/2026`) porque reflete a meta vigente até a próxima reunião — truncar no `today` |
| **4390** | "Taxa de juros — Selic acumulada no mês" [CKAN] (%) | mensal | **Sim** (08/1986) | **[CONFIRMADO]** |
| **4189** | "Taxa de juros — Selic acumulada no mês anualizada base 252" [CKAN] | mensal | **Sim** (08/1986) | **[CONFIRMADO]** ← **esta é a "Selic mensal" do e-mail** |
| **12** | CDI — % ao dia | diária | **Sim** | **[CONFIRMADO]** 03/01/2005 = `0.064893`. Nome não confirmável via CKAN (fora do subconjunto) |
| **4389** | CDI anualizado base 252 (% a.a.) | diária | **Sim** | **[CONFIRMADO]** 08/10/2026 = `13.65`. Nome [NÃO VERIFICADO] |
| **24363** | "Índice de Atividade Econômica do Banco Central — IBC-Br" [CKAN] | mensal | **Sim** | **[CONFIRMADO]** jan/06 = `75.88784`. **Início é 2003**, não há 2005-01 → série começa depois de 1990 |
| **24364** | "IBC-Br — **com ajuste sazonal**" [CKAN] | mensal | **Sim** | **[CONFIRMADO]** jan/06 = `79.44731` ← **use esta para regimes** |
| **1** | "Taxa de câmbio — Livre — Dólar americano (**venda**) — diário" [CKAN] (PTAX) | diária | **Sim** | **[CONFIRMADO]** 09/10/2026 = `4.9892` |
| **10813** | "Taxa de câmbio — Livre — Dólar americano **compra**" [CKAN] | diária | **Sim** | **[CONFIRMADO]** 09/10/2026 = `4.9886` |
| **21619 / 21620** | Euro — venda / compra (a confirmar qual é qual) | diária | **Sim** | **[CONFIRMADO]** existência e 2006; rótulo **a confirmar** |
| **22099** | PIB trimestral — índice de volume, **sem** ajuste sazonal | trimestral | **Sim** | **[CONFIRMADO]** 2006T1 = `128.18` = SIDRA **1620/v583/c11255=90707** exato |
| **22109** | PIB trimestral — índice de volume **com ajuste sazonal** | trimestral | **Sim** | **[CONFIRMADO]** 2006T1 = `131.74` = SIDRA **1621/v584/c11255=90707** exato ← **melhor atalho para PIB trimestral** |
| **22108** | Valor adicionado a preços básicos — índice com ajuste sazonal | trimestral | **Sim** | **[CONFIRMADO]** 2006T1 = `131.59` = SIDRA 1621/v584/c11255=**90705** |
| **4380** | PIB mensal — valores correntes (R$ milhões) | mensal | **Sim** | **[CONFIRMADO]** jan/06 = `181707.7` |
| **4513** | "Dívida líquida do setor público (% PIB) — total — setor público consolidado" [CKAN] | mensal | **Sim** | **[CONFIRMADO]** jan/06 = `47.82` |
| **13762** | "Dívida bruta do governo geral (% PIB) — metodologia a partir de 2008" [CKAN] | mensal | **NÃO** | **[CONFIRMADO]** 404 em 2006. Para 2006-2007 usar `4537`/série antiga — **a confirmar** |
| **27574 / 27575** | Índice de Commodities Brasil (IC-Br) geral / agropecuária | mensal | **Sim** | **[CONFIRMADO]** jan/06 = `101.81` / `104.78` |
| **24369** | Taxa de desocupação — PNAD Contínua (via BCB) | mensal | **NÃO** | **[CONFIRMADO]** 404 em 2006 (PNADC começa 2012) |
| **4466** | "IPCA — núcleo médias aparadas com suavização" [CKAN] | mensal | **Sim** | **[CONFIRMADO]** |
| **11427** | "IPCA — núcleo por exclusão — sem monitorados e alimentos no domicílio" [CKAN] | mensal | **Sim** | **[CONFIRMADO]** |
| **11426 / 11428 / 16121 / 16122** | Outros núcleos do IPCA (16122 = "núcleo de dupla ponderação" [CKAN]) | mensal | **Sim** | **[CONFIRMADO]** existência + 2006 |
| **189 / 190** | IGP-M / IGP-DI — variação mensal | mensal | **Sim** | **[CONFIRMADO]** jan/06 = `0.92` / `0.72`. Rótulos [NÃO VERIFICADO] |
| **1619** | Salário mínimo nominal (R$) | mensal | **Sim** | **[CONFIRMADO]** valor 2006 = `300.00` |
| **4192** | Agregado monetário (R$ milhões) — identificação exata **a confirmar** | mensal | Sim | **[CONFIRMADO]** existência |

### Séries SGS que **NÃO** servem — descontinuadas (achado importante)

| Códigos | O que são | Último dado | Consequência |
|---|---|---|---|
| **7801–7806** | Taxas referenciais de **swap DI × pré** (30/60/90/120/180/**360** dias), diárias | **30/09/2019** | **[CONFIRMADO]** Não dá para montar inclinação de curva 2006-2026 pelo SGS |
| **7816–7827** | Mesmos swaps, séries mensais | **01/08/2019** | **[CONFIRMADO]** idem |
| **7800** | (série mensal diversa) | 01/12/2012 | **[CONFIRMADO]** |

→ O e-mail citava "séries SGS 7806 etc." para inclinação de curva. **Confirmado que essa rota está morta
desde set/2019.** Ver A5 para as alternativas viáveis.

### Fallback do SGS

1. **`python-bcb`** (lib Python, ver seção de bibliotecas) — encapsula paginação e a janela de 10 anos.
2. **Ipeadata** espelha várias séries do BCB sem o limite de 10 anos (ex.: `BM366_TJOVER366` =
   Selic Copom diária, **1996-07-01 → 2026-10-09, 11.058 pontos, sem nulos** **[CONFIRMADO]**).
3. Para IPCA e PIB, o **IBGE/SIDRA é a fonte primária** — o SGS é apenas um espelho (ver A3).

---

## A2. BCB — Expectativas de Mercado (Focus) via API OLINDA / OData v4

### Acesso **[CONFIRMADO]**

```
https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/{EntitySet}?$format=json&...
```

- **Autenticação:** nenhuma. **Custo:** zero. **[CONFIRMADO]**
- `$metadata` funciona e é a documentação viva:
  `https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/$metadata` **[CONFIRMADO]**

### EntitySets existentes (todos os 13, lidos do `$metadata`) **[CONFIRMADO]**

| EntitySet | EntityType subjacente | Campos |
|---|---|---|
| `ExpectativasMercadoAnuais` | `ExpectativaMercadoAnual` | `Indicador, IndicadorDetalhe, Data, DataReferencia, Media, Mediana, DesvioPadrao, Minimo, Maximo, numeroRespondentes, baseCalculo` |
| `ExpectativaMercadoMensais` | `ExpectativaMercadoMensal` | `Indicador, Data, DataReferencia, Media, Mediana, DesvioPadrao, Minimo, Maximo, numeroRespondentes, baseCalculo` |
| `ExpectativasMercadoTrimestrais` | `ExpectativaMercadoTrimestral` | `Indicador, Data, DataReferencia, Media, ...` |
| `ExpectativasMercadoSelic` | `ExpectativaMercadoSelic` | `Indicador, Data, **Reuniao**, Media, Mediana, ...` |
| `ExpectativasMercadoInflacao12Meses` | `ExpectativaMercadoInflacao12Meses` | `Indicador, Data, **Suavizada**, Media, ..., baseCalculo` |
| `ExpectativasMercadoInflacao24Meses` | `ExpectativaMercadoInflacao12Meses` (sic) | idem |
| `ExpectativasMercadoTop5Anuais` | `ExpectativasMercadoTop5Anual` | `..., tipoCalculo, ...` |
| `ExpectativasMercadoTop5Mensais` | `ExpectativasMercadoTop5Mensal` | idem |
| `ExpectativaMercadoTop5Trimestral` | `ExpectativaMercadoTop5Trimestral` | idem |
| `ExpectativasMercadoTop5Selic` | `ExpectativasMercadoSelicTop5` | ⚠️ campos em **camelCase minúsculo**: `indicador, Data, reuniao, tipoCalculo, media, mediana, desvioPadrao, coeficienteVariacao, minimo, maximo` |
| `ExpectativasMercadoTop5Inflacao12Meses` | `ExpectativaMercadoInflacaoH12` | `..., tipoCalculo` |
| `ExpectativasMercadoTop5Inflacao24Meses` | `ExpectativaMercadoInflacaoH24` | idem |
| `DatasReferencia` | `DatasReferencia` | `Indicador, periodo, DataReferencia1, DataReferencia2` |

**Pegadinha:** o nome do EntitySet **não** segue o nome do EntityType (singular/plural trocados,
`ExpectativasMercadoInflacao24Meses` aponta para o tipo `...12Meses`) e a capitalização dos campos
**varia entre endpoints**. Normalize no extrator.

### Início do histórico (medido com `$orderby=Data asc&$top=1`) **[CONFIRMADO]**

| EntitySet | 1ª observação | Exemplo |
|---|---|---|
| `ExpectativasMercadoAnuais` | **1999-04-30** | IGP-DI, DataReferencia `1999`, Mediana 15.70 |
| `ExpectativaMercadoMensais` | **2000-01-03** | IPCA, DataReferencia `04/2000`, Mediana 0.60 |
| `ExpectativasMercadoTrimestrais` | **2001-11-06** | PIB Agropecuária, DataReferencia `3/2001` |
| `ExpectativasMercadoInflacao12Meses` | **2001-11-07** | IGP-DI, Suavizada `N`, Mediana 7.76 |
| `ExpectativasMercadoSelic` | **2004-11-18** | Reuniao `R1/2006`, Mediana 15.50 |

→ **Todos cobrem 2006 com folga.** Checagem pontual: IPCA anual em `2006-01-02` existe, com
`DataReferencia` 2005/2006/2007 (Mediana 4.50 para 2006). **[CONFIRMADO]**

### Como filtrar

```
# IPCA anual, janeiro/2006
.../ExpectativasMercadoAnuais?$format=json
   &$filter=Indicador eq 'IPCA' and Data ge '2006-01-01' and Data le '2006-01-31'

# Selic por reunião do Copom
.../ExpectativasMercadoSelic?$format=json&$filter=Reuniao eq 'R1/2026'
```

- `Data` é **string** `yyyy-MM-dd` — comparar com **string entre aspas simples**, não com `datetime'...'`. **[CONFIRMADO]**
- `DataReferencia` é string: `'2026'` (anual), `'09/2028'` (mensal), `'3/2001'` (trimestral), `Reuniao` = `'R1/2026'`. **[CONFIRMADO]**
- **Indicadores que importam** (vistos em respostas reais): `IPCA`, `Câmbio`, `Selic`, `PIB Agropecuária`,
  `IGP-DI`, `IGP-M`, `IPC-Fipe`, `Balança comercial` (com `IndicadorDetalhe` = `Exportações`). **[CONFIRMADO]**
  Para `PIB Total` o rótulo exato **a confirmar** — enumere `Indicador` baixando um ano e fazendo `set()`.
- **`baseCalculo`**: `0` e `1` coexistem para a mesma `Data`+`DataReferencia` (vi ambos). Convenção do BCB:
  `0` = todas as instituições dos últimos 30 dias, `1` = apenas os últimos 5 dias úteis. **[NÃO VERIFICADO]**
  **Filtre sempre por um dos dois**, senão você duplica linhas.

### Pegadinhas do OData do BCB **[CONFIRMADO]**

| Recurso | Funciona? | Observação |
|---|---|---|
| `$filter` | ✅ | |
| `$orderby` | ✅ | |
| `$select` | ✅ | |
| `$skip` | ✅ | |
| `$top` | ✅ | |
| **sem `$top`** | ✅ | devolve **tudo**: `ExpectativasMercadoAnuais` filtrado por IPCA = **48.592 linhas** num único JSON |
| **`$top=20000`** | ⚠️ | devolve **exatamente 20.000 linhas e NENHUM `@odata.nextLink`** → **truncamento silencioso**. Nunca confie em `$top` alto; ou omita `$top`, ou pagine com `$skip` |
| `$count=true` | ❌ | ignorado, sem erro |
| `$apply=groupby(...)` | ❌ | **ignorado silenciosamente** — devolve as linhas completas e desordenadas |
| `$format=text/csv` | ⚠️ | CSV com separador **vírgula** E decimal **vírgula** entre aspas: `IPCA,null,2018-01-22,2019,"4,19","4,25",...`. Parser frágil — **use JSON** |
| `null` textual | ⚠️ | no CSV, ausência vem como a string `null` |

### Fallback

1. **`python-bcb`** tem módulo `Expectativas` que já encapsula esse OData. **[NÃO VERIFICADO]**
2. Planilhas do **Relatório Focus** no site do BCB (`bcb.gov.br/publicacoes/focus`) — download manual,
   só pontos recentes. **[NÃO VERIFICADO]**
3. Série `BM12_IPCAEXP1212` do Ipeadata — "Expectativa média de Inflação IPCA — acumulada para os próximos
   12 meses", mensal, ativa, fonte Bacen/Boletim. **[CONFIRMADO que a série existe no catálogo]**

---

## A3. IBGE SIDRA — IPCA e PIB trimestral

### Dois endpoints, escolha consciente

```
# (a) API "servicodados" v3 — metadados + dados, JSON estruturado
GET https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados
GET https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos

# (b) API SIDRA clássica — a que o `sidrapy` usa
GET https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variaveis}/p/{periodos}/c{classif}/{categorias}
```

- **Autenticação:** nenhuma. **Custo:** zero. **[CONFIRMADO]**
- **Formato do apisidra:** array JSON em que **a primeira linha é o cabeçalho** (rótulos), e as linhas
  seguintes são os dados. Campos: `V` (valor, **string**), `D1C/D1N` (território), `D2C/D2N` (variável),
  `D3C/D3N` (período, ex. `200601` / `1º trimestre 2006`), `D4C/D4N` (classificação). **[CONFIRMADO]**
- **Encoding:** ambas as APIs servem **UTF-8** (`Content-Type: application/json; charset=utf-8` na v3).
  Em Windows, **declare `encoding='utf-8'` explicitamente** — o default do locale (cp1252) corrompe
  acentos. Foi exatamente o que aconteceu nos meus primeiros testes. **[CONFIRMADO]**
- **Limite de taxa:** não documentado; sem bloqueios observados. **[CONFIRMADO]**
- `p/all` ou faixas `p/200601-202602` funcionam; `d/v584%202` controla nº de decimais. **[CONFIRMADO]**

### IPCA — tabela **1737** **[CONFIRMADO]**

`"IPCA - Série histórica com número-índice, variação mensal e variações acumuladas em 3 meses, em 6 meses,
no ano e em 12 meses (a partir de dezembro/1979)"` — mensal, **197912 → 202609**, 562 períodos,
nível territorial N1 (Brasil), **sem classificações**.

| Variável | id |
|---|---|
| Número-índice (base dez/1993 = 100) | **2266** |
| Variação mensal (%) | **63** |
| Acumulada em 3 meses | 2263 |
| Acumulada em 6 meses | 2264 |
| Acumulada no ano | 69 |
| **Acumulada em 12 meses** | **2265** |

Exemplo validado: `https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/63,2265,2266/p/200601-202609`

→ **1737 é a tabela certa e cobre 2006 com folga.** Cruzamento com SGS 433 e 13522 bateu exatamente.

**IPCA por grupos** (extra, não pedido): tabela **1419** cobre só **201201–201912**, tabela **7060** só
**202001→**. **Não existe tabela única de grupos cobrindo 2006-2026** — a de 2006-2011 **a confirmar**. **[CONFIRMADO]**

### PIB trimestral — qual tabela usa qual **[CONFIRMADO]**

Todas com periodicidade **trimestral**, **199601 → 202602**, nível N1, classificação **`c11255` "Setores e subsetores"**.

| Tabela | Nome | Variável | Uso |
|---|---|---|---|
| **1620** | Série encadeada do índice de volume trimestral (base média 1995 = 100) | **583** | volume **sem** ajuste sazonal |
| **1621** | Série encadeada do índice de volume trimestral **com ajuste sazonal** | **584** | ✅ **é esta que dá o volume trimestral dessazonalizado** |
| **5932** | Taxa de variação do índice de volume trimestral | 6561 (T/T-4), 6562 (acum. 4 trim.), 6563 (acum. ano), **6564 (T/T-1, dessaz.)** | variações prontas |
| **6612 / 6613** | Valores encadeados a preços de 1995 (s/ e c/ ajuste sazonal) | 9318 / 9319 | R$ milhões |
| **1846** | Valores a preços correntes | 585 | R$ milhões nominais |

**Categorias de `c11255`** (lista completa, 21 itens) **[CONFIRMADO]**:
`90687` Agropecuária-total · `90691` Indústria-total · `90692` Extrativas · `90693` Transformação ·
`90695` Eletricidade e gás, água, esgoto · `90694` Construção · `90696` Serviços-total · `90697` Comércio ·
`90698` Transporte/armazenagem/correio · `90699` Informação e comunicação · `90700` Atividades financeiras ·
`90702` Atividades imobiliárias · `90701` Outras atividades de serviços · `90703` Adm./saúde/educação públicas ·
`90705` **Valor adicionado a preços básicos** · **`90707` PIB a preços de mercado** · `93404` Consumo das famílias ·
`93405` Consumo do governo · `93406` **FBCF** · `93407` Exportações · `93408` Importações (−)

**Chamada de referência, testada:**
```
https://apisidra.ibge.gov.br/values/t/1621/n1/all/v/584/p/200601-202602/c11255/90707/d/v584%202
→ 2006T1 = 131.74 ; 2006T2 = 132.14 ; 2006T3 = 134.36
```
E `t/5932/.../v/6564/p/200601/c11255/90707` → **1.6 %** (PIB T/T-1 dessazonalizado no 1T06). **[CONFIRMADO]**

**Atalho:** se você só quer o agregado nacional, **SGS 22109 é exatamente a tabela 1621/v584/90707** e sai
numa única chamada (confirmado valor a valor). Use SIDRA quando precisar da **abertura setorial** —
que é justamente o que interessa para cruzar com índices setoriais da B3.

### Extras úteis do IBGE (confirmados, fora do escopo mínimo)

| Tabela | Conteúdo | Período |
|---|---|---|
| **8888** | Produção Física Industrial (PIM-PF) por seções/atividades | **200201 → 202608** |
| 3653 | PIM-PF — série antiga encerrada | 200201 → 202201 |
| **8880** | PMC — receita nominal e volume de vendas no varejo (2022=100), com e sem ajuste sazonal | **200001 → 202607** |
| **4099** | PNAD Contínua trimestral — taxa de desocupação e subutilização | **201201 → 202602** ⚠️ não cobre 2006 |
| 6381 | Taxa de desocupação — trimestre móvel | 201203 → 202608 |
| **2176** | **PME** — taxa de desocupação (10+ anos), mensal | **200203 → 201602** ← ponte para 2006-2011 |

→ **Desemprego é lacuna:** não há série única 2006-2026. Emende **PME (2176, até fev/2016)** com
**PNADC (4099, desde 2012T1)** usando a sobreposição 2012-2016 para calibrar nível. Ver "Lacunas".

### Fallback

1. **`sidrapy`** (lib) — wrapper fino do apisidra.
2. Download manual na interface `https://sidra.ibge.gov.br/tabela/1621` (XLSX/CSV).
3. SGS 22099/22109/22108 (espelho do BCB, só agregados).
4. Ipeadata, família `SCN104_*` (ex.: `SCN104_PIBAGPAS104` = PIB agropecuária dessazonalizado) —
   **121 séries trimestrais de PIB, fonte IBGE/SCN Trim.** **[CONFIRMADO no catálogo]**

---

## A4b. Tesouro Direto — preços e taxas históricos (CKAN do Tesouro Transparente)

**Esta é a fonte mais prática de taxas de títulos públicos com 20+ anos.** Confirmei baixando o arquivo
completo. **[CONFIRMADO]**

### Acesso

```
# catálogo
GET https://www.tesourotransparente.gov.br/ckan/api/3/action/package_search?q=tesouro+direto
GET https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show?id=taxas-dos-titulos-ofertados-pelo-tesouro-direto

# arquivo único com TODA a série histórica (não é por ano!)
GET https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv
```

- **Autenticação:** nenhuma. **Custo:** zero. **Exige User-Agent de browser** no CKAN (sem UA a API responde
  página de erro). **[CONFIRMADO]**
- Datasets irmãos no mesmo CKAN: `operacoes-do-tesouro-direto`, `estoque-do-tesouro-direto`,
  `investidores-do-tesouro-direto`, `vendas-do-tesouro-direto`, `resgates-do-tesouro-direto`. **[CONFIRMADO]**
- Metadados em PDF: `.../resource/1a8eb2e3-4902-4a38-a1eb-6410f23d90de/download/taxa.pdf` **[CONFIRMADO]**

### Formato do arquivo **[CONFIRMADO — baixado e parseado]**

| Propriedade | Valor |
|---|---|
| Tamanho | **14,58 MB** |
| Linhas | **177.260** + cabeçalho |
| Separador | **`;`** |
| Decimal | **vírgula** (`"0,05"`, `"20046,46"`) |
| Encoding | **latin-1 / ISO-8859-1** |
| Datas | **`dd/mm/aaaa`** |
| Cobertura | **31/12/2004 → 09/10/2026** ✅ cobre 2006 inteiro (248 dias úteis em 2006) |

Colunas: `Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha`

Tipos de título presentes (contagem de linhas): `Tesouro IPCA+ com Juros Semestrais` (44.100, = NTN-B),
`Tesouro Prefixado` (28.200, = LTN), `Tesouro Prefixado com Juros Semestrais` (27.355, = NTN-F),
`Tesouro Selic` (21.453, = LFT), `Tesouro IPCA+` (18.924, = NTN-B Principal),
`Tesouro IGPM+ com Juros Semestrais` (15.810, = NTN-C), `Tesouro Educa+` (14.034),
`Tesouro Renda+ Aposentadoria Extra` (7.384). **[CONFIRMADO]**

### Pegadinha decisiva: o menu de vencimentos era curto nos anos iniciais **[CONFIRMADO — medido]**

| Ano-base | Tipo | Vencimentos disponíveis |
|---|---|---|
| **2006** | Tesouro Prefixado (LTN) | 01/04/2006 → **01/01/2009** (11 vértices) — **ponta longa pré só ~3 anos** |
| **2006** | Prefixado c/ Juros Sem. (NTN-F) | 01/01/2008 → **01/01/2014** (4 vértices) — ponta longa pré ~8 anos |
| **2006** | IPCA+ c/ Juros Sem. (NTN-B) | 15/08/2006 → **15/05/2045** (10 vértices) — ✅ **curva real completa já em 2006** |
| 2026 | NTN-B | 15/08/2026 → 15/08/2060 (10 vértices) |
| 2026 | NTN-F | 01/01/2027 → 01/01/2037 (6 vértices) |

**Implicação prática:** com Tesouro Direto você consegue, para **todo o período 2006-2026**:
- **Inclinação REAL** (NTN-B curta vs NTN-B 2045) → robusta desde 2006.
- **Inclinação NOMINAL** usando LTN curta vs NTN-F mais longa disponível → o vértice longo varia de
  ~8 anos (2006) a ~11 anos (2026). Para consistência, **interpole para prazos fixos** (ex.: 1 ano e 5 anos)
  a partir dos vencimentos disponíveis em cada data e documente que o vértice de 10 anos nominal
  **não existe antes de ~2010**.
- **Inflação implícita (breakeven)** = (1+taxa NTN-F)/(1+taxa NTN-B) − 1, para prazos comparáveis.

Outras ressalvas: são taxas **do Tesouro Direto** (varejo), que embutem pequeno spread vs mercado
secundário puro; e **só os títulos ofertados no programa** aparecem. Para o mercado secundário "limpo",
a referência é a ANBIMA (A4a).

### Fallback
1. ANBIMA mercado secundário (A4a).
2. Lib **`pyield`** (lê ANBIMA + Tesouro + DI futuro).
3. Ipeadata `ANBIMA366_TJTLN{1,3,6,12}366` — ETTJ prefixada de 1/3/6/12 meses, **diária, 2000-04-04 →
   2026-10-08, 8.404 pontos** **[CONFIRMADO]** — resolve só a ponta curta.

---
