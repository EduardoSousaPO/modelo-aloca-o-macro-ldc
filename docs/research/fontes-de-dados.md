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

## A4.1 Tesouro Direto — preços e taxas históricos (CKAN do Tesouro Transparente)

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

## A4.2 ANBIMA — taxas indicativas de títulos públicos (mercado secundário)

### Acesso **[CONFIRMADO-SUB]**

```
# arquivo por data — ATENÇÃO: o padrão é ms{AAMMDD}.txt, NÃO ms{ddmmaa}.txt
https://www.anbima.com.br/informacoes/merc-sec/arqs/ms{AAMMDD}.txt
  ex.: ms261008.txt  → HTTP 200, 6.740 B, e o campo interno "Data Referencia" = 20261008

# arquivo do último dia útil, URL estável (ideal para job diário idempotente)
https://www.anbima.com.br/informacoes/merc-sec/arqs/Msec_txt.txt
```

- **Autenticação:** nenhuma; **custo:** zero; **sem Cloudflare, sem 403**. **[CONFIRMADO-SUB]**
- `ms081026.txt` (padrão `ddmmaa`) → **404**. O exemplo `ms160118.txt` que aparece *hardcoded* na página
  `merc-sec/default.asp` também dá **404** — não use como prova de histórico. **[CONFIRMADO-SUB]**

### ⛔ Pegadinha que muda o projeto: o histórico é uma janela rolante de ~20 dias úteis

Varredura de status em 10/10/2026 **[CONFIRMADO-SUB]**:
- **HTTP 200:** `ms260911` … `ms261009` (de 11/09/2026 a 09/10/2026).
- **404:** `ms260910`, `ms260901`, `ms260801`, `ms260101`, `ms250101`, `ms200102`, `ms160104`,
  `ms061010`, `ms060103`, `ms040105`, `ms021002`.

→ **Não existe absolutamente nada de 2006** nesse diretório. Histórico longo de taxas indicativas
**só no ANBIMA Feed (pago)**. **Implicação de arquitetura: o extrator precisa rodar diariamente e
acumular em banco próprio a partir de hoje.** Para a base de 20 anos, use o **Tesouro Direto (A4.1)**.

### Layout do `ms*.txt` **[CONFIRMADO-SUB — lido byte a byte]**

- Encoding **ISO-8859-1 / latin-1**; line endings **CRLF**; separador **`@`**.
- Linha 1 = cabeçalho institucional · linha 2 = **vazia** · linha 3 = header · linhas 4+ = dados (~53 linhas).
- Header:
  `Titulo@Data Referencia@Codigo SELIC@Data Base/Emissao@Data Vencimento@Tx. Compra@Tx. Venda@Tx. Indicativas@PU@Desvio padrao@Interv. Ind. Inf. (D0)@Interv. Ind. Sup. (D0)@Interv. Ind. Inf. (D+1)@Interv. Ind. Sup. (D+1)@Criterio`
- Exemplo: `LTN@20261008@100000@20250110@20270401@13,1364@13,0888@13,1049@944,429057@...@Calculado`
- Datas **`AAAAMMDD`** (inteiro); decimal **vírgula**, sem separador de milhar.
- `Titulo` ∈ {`LTN`, `LFT`, `NTN-B`, `NTN-C`, `NTN-F`}; `Codigo SELIC`: LTN 100000 · LFT 210100 ·
  NTN-B 760199 · NTN-C 770100 · NTN-F 950199.
- Parse: `pd.read_csv(url, sep="@", skiprows=2, encoding="latin-1", decimal=",")`
- ⚠️ **Aviso vigente na página** (10/03/2026): atraso na apuração das taxas indicativas por questões
  operacionais na divulgação de dados pela B3 → trate arquivo ausente/atrasado como caso **normal**,
  com retry. **[CONFIRMADO-SUB]**

### Fallback
Tesouro Direto (A4.1, 2004→) · ANBIMA Feed (pago) · lib `pyield`.

---

## A5. ETTJ / inclinação da curva de juros

### A5.1 ANBIMA Curva Zero (parâmetros Svensson) — **é um POST, não um `CZ{ddmmaa}.csv`**

**[CONFIRMADO-SUB]**

```
POST https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp
body (form-urlencoded): Idioma=PT&Dt_Ref=dd/mm/aaaa&saida=csv
Referer: https://www.anbima.com.br/informacoes/est-termo/CZ.asp
(GET sem body também funciona e devolve o último dia)
```

- **Sem cadastro, sem login, sem Cloudflare.** **[CONFIRMADO-SUB]**
- Páginas: `https://www.anbima.com.br/informacoes/est-termo/CZ.asp` (200) e `.../est-termo/default.asp` (200).
- Metodologia (PDF): `https://www.anbima.com.br/data/files/9A/F4/E3/1F/4805B710B0F024B7882BA2A8/est-termo_metodologia_v2021.pdf`
- ⛔ **`CZ{ddmmaa}.csv` / `cz{ddmmaa}.txt` em `/est-termo/arqs/` NÃO EXISTEM → 404.** **[CONFIRMADO-SUB]**

**Conteúdo do `saida=csv`** (ISO-8859-1, separador `;`, decimal vírgula, notação científica `E-02`,
**três blocos no mesmo arquivo**) **[CONFIRMADO-SUB]**:

```
09/10/2026;Beta 1;Beta 2;Beta 3;Beta 4;Lambda 1;Lambda 2
PREFIXADOS;0,11977147726174;0,018489961961487;-4,58301615075328E-02;3,58319281748558E-02;0,887669138508503;0,377434237188519
IPCA;6,32419992460024E-02;-3,77397467369023E-02;4,83634862722349E-02;1,01668003510658E-02;2,13286645425394;0,210836740714491

ETTJ Inflação Implicita (IPCA)
Vertices;ETTJ IPCA;ETTJ PREF;Inflação Implícita
252;6,2834;12,5792;5,9235
...
6.930;6,5140;;
```

- Vértices em **dias úteis**, de 252 a 6.930, passo 126. ⚠️ a coluna `Vertices` usa **ponto como separador
  de milhar** (`1.008`, `6.930`) → limpe antes de converter.
- `ETTJ PREF` vai só até o vértice 2.520; `ETTJ IPCA` vai até 6.930.
- `saida=txt` → mesmo conteúdo com separador `@` e ID de bloco (header legado "ANDIMA").
- ⚠️ `saida=xls` **não é Excel**: é **HTML `<table>`** em ISO-8859-1 servido com
  `Content-Type: application/vnd.ms-excel`. Use `csv` ou `txt`.

### ⛔ A5.2 Também aqui o histórico é janela rolante (~20 dias úteis)

Medido por tamanho do corpo retornado em 10/10/2026 (**0 bytes = sem dados**) **[CONFIRMADO-SUB]**:

| `Dt_Ref` | resultado |
|---|---|
| 09/10/2026 · 08/10 · 07/10 · 05/10 · 02/10 · 01/10 · 30/09 · 15/09 | com dados (≈2.9 KB) |
| **14/09/2026** | **mais antigo com dados** |
| 11/09/2026 · 10/09 · 04/09 · 01/09 · 01/08/2026 · 02/01/2026 · 02/01/2020 · **02/01/2006** | **0 bytes** |

Também foram testados e **não existem**: `s3-data-prd-use1-precos/arquivos/ettj-historico/` e
`.../curva-zero-historico/` → **403**. O portal `data.anbima.com.br` **não tem página de ETTJ**
(menu lido de `data-strapi.prd.anbima.com.br/api/menu-anbima-data`: há `/titulos-publicos`,
`/debentures`, `/indices` — nenhum ETTJ). CKAN do Tesouro: busca `curva juros` → **0 resultados**. **[CONFIRMADO-SUB]**

→ **ETTJ histórica da ANBIMA com 20 anos: só no ANBIMA Feed (pago).** Isso é restrição de produto,
não bug de extração.

### A5.3 Outras rotas para inclinação da curva, avaliadas

| Rota | Cobre 2006-2026? | Veredito |
|---|---|---|
| **SGS 7801-7806 / 7816-7827** (swap DI × pré 30…360 dias) | ❌ | **Descontinuadas em set/2019** (7801-7806 diárias terminam 30/09/2019; 7816-7827 mensais em 01/08/2019). **[CONFIRMADO]** Era a rota sugerida no e-mail — está morta |
| **ANBIMA `ms*.txt`** | ❌ | janela rolante de ~20 d.u. **[CONFIRMADO-SUB]** |
| **ANBIMA Curva Zero (CZ)** | ❌ | janela rolante de ~20 d.u. **[CONFIRMADO-SUB]** |
| **ANBIMA Feed / API `api.anbima.com.br/feed/...`** | ✅ (presumido) | **PAGO**, OAuth2. Paths retornam **401** sem token (confirmando existência). Doc: `https://developers.anbima.com.br/pt/documentacao/precos-indices/` **[CONFIRMADO-SUB]** |
| **Ipeadata `ANBIMA366_TJTLN{1,3,6,12}366`** | ✅ parcial | ETTJ prefixada de **1/3/6/12 meses**, diária, **2000-04-04 → 2026-10-08, 8.404 pontos não nulos**. **[CONFIRMADO]** Resolve só a **ponta curta** |
| **Tesouro Direto (`precotaxatesourodireto.csv`)** | ✅ | **2004-12-31 → hoje, num único CSV de 14,6 MB.** **[CONFIRMADO]** Cobre toda a janela |
| **B3 DI futuro (arquivos de ajustes/derivativos)** | ✅ (presumido) | Reconstrução via arquivos diários da B3; a lib **`pyield`** cobre DI futuro e ANBIMA. **[NÃO VERIFICADO]** |

### ✅ A5.4 Recomendação explícita para 20 anos de inclinação curto × longo

**Use o CSV do Tesouro Direto como fonte primária da curva.** Razões, todas medidas:

1. É **um único arquivo** com 2004-12-31 → 2026-10-09 e **248 dias úteis já em 2006**.
2. A **curva real** é completa desde 2006: havia 10 vencimentos de NTN-B, do curto até **15/05/2045**.
   → inclinação real (NTN-B curta × NTN-B longa) é **robusta em toda a janela**.
3. A **curva nominal** tem ponta longa mais curta nos primeiros anos: em 2006 a LTN mais longa vencia em
   **01/01/2009** e a NTN-F mais longa em **01/01/2014** (≈8 anos). Portanto:
   - construa **vértices fixos por interpolação** (ex.: 1 ano, 3 anos, 5 anos) a partir dos vencimentos
     disponíveis em cada data;
   - **documente que o vértice nominal de 10 anos não existe antes de ~2010**;
   - para a medida "longo prazo" na janela inteira, prefira **5 anos** como ponta longa nominal, ou use a
     **inclinação real (NTN-B)** como variável principal de regime.
4. **Inflação implícita (breakeven)** = `(1+taxa NTN-F)/(1+taxa NTN-B) − 1` para prazos comparáveis — sai
   do mesmo arquivo, sem fonte adicional.
5. Ressalva: são taxas do **Tesouro Direto (varejo)**, com pequeno spread vs. secundário puro. Para o
   período recente, cruze com `ms*.txt`/CZ acumulados diariamente e com a lib `pyield`.

**Plano de dois trilhos:**
- **Trilho histórico (entrega agora):** Tesouro Direto 2004→2026 + Ipeadata ANBIMA 1-12 meses para a ponta curta.
- **Trilho incremental (começa hoje):** job diário gravando `Msec_txt.txt` e `CZ-down.asp` num banco
  próprio, para que em 12 meses a casa tenha série de ETTJ Svensson proprietária.

---

# BLOCO B — DESEMPENHO DE ATIVOS E SETORES

## B6. Índices ANBIMA IMA — ✅ histórico diário completo, grátis, sem cadastro

**Este é o achado mais importante da pesquisa.** Existe um **bucket S3 público da ANBIMA** com o
número-índice diário desde 2000/2003, baixável por `curl`/`requests`, **sem token, sem reCAPTCHA,
sem cadastro, sem custo**. Descoberto pelo agente auxiliar e **re-baixado e parseado por mim**.

### Acesso

```
https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/arquivos/indices-historico/{SLUG}-HISTORICO.xls
```

### Tabela verificada (baixei os 10 arquivos e li a 1ª e a última linha de cada) **[CONFIRMADO]**

| Índice | SLUG | bytes | linhas | 1ª data | última data | Nº-índice inicial → final | Cobre 2006? |
|---|---|---|---|---|---|---|---|
| **IMA-Geral** | `IMAGERAL` | 387.774 | 6.237 | **2001-12-04** | 2026-10-09 | 532,62 → 10.784,85 | ✅ |
| IMA-Geral ex-C | `IMAGERALEXC` | 359.730 | 5.407 | 2005-03-31 | 2026-10-09 | 1.000,00 → 10.635,33 | ✅ |
| **IMA-B** | `IMAB` | 393.685 | 5.795 | **2003-09-16** | 2026-10-09 | 723,07 → 12.656,54 | ✅ |
| **IMA-B 5** | `IMAB5` | 388.472 | 5.795 | 2003-09-16 | 2026-10-09 | 775,88 → 12.107,19 | ✅ |
| **IMA-B 5+** | `IMAB5MAIS` | 397.399 | 5.795 | 2003-09-16 | 2026-10-09 | 715,68 → 14.075,87 | ✅ |
| **IRF-M** | `IRFM` | 426.663 | 6.700 | **2000-02-01** | 2026-10-09 | 863,15 → 24.498,77 | ✅ |
| **IRF-M 1** | `IRFM1` | 383.537 | 6.488 | 2000-12-01 | 2026-10-09 | 1.000,00 → 21.220,07 | ✅ |
| **IRF-M 1+** | `IRFM1MAIS` | 389.527 | 6.488 | 2000-12-01 | 2026-10-09 | 1.000,00 → 26.818,31 | ✅ |
| **IMA-S** | `IMAS` | 379.261 | 6.245 | 2001-12-03 | 2026-10-09 | 550,49 → 9.029,69 | ✅ |
| IMA-C | `IMAC` | 290.614 | 4.850 | 2001-12-03 | **2021-04-01** | 428,27 → 10.301,15 | ✅ (descontinuado em 2021) |
| IHFA (bônus) | `IHFA` | 261.650 | 4.766 | 2007-09-28 | 2026-10-06 | — | parcial |
| IDA-Geral / IDA-DI / IDkA IPCA 2A (bônus) | `IDAGERAL`, `IDADI`, `IDKAIPCA2A` | — | — | — | — | — | não perfilado |

→ **Os 8 índices pedidos no e-mail (IMA-B, IMA-B 5, IMA-B 5+, IRF-M, IRF-M 1, IRF-M 1+, IMA-Geral, IMA-S)
cobrem 2006 com folga.** Esforço: **baixo** — um GET por índice.

### Formato e pegadinhas **[CONFIRMADO]**

- ⚠️ **A extensão é `.xls` mas o arquivo é XLSX (OOXML/ZIP).** Magic bytes = `50 4B 03 04` (`PK..`).
  Use `pd.read_excel(..., engine="openpyxl")`. `xlrd` falha.
  ⚠️ Se salvar em disco com extensão `.xls`, o **openpyxl recusa pela extensão** —
  carregue de `io.BytesIO(resp.content)` ou salve como `.xlsx`.
- **10 colunas**, header na linha 1:
  `Índice | Data de Referência | Número Índice | Variação Diária (%) | Variação no Mês (%) |
  Variação no Ano (%) | Variação 12 Meses (%) | Variação 24 Meses (%) | Duration (d.u.) | PMR`
- `Data de Referência` já vem como `datetime`; `Número Índice` como `float` (6 decimais). Sem vírgula
  decimal, sem problema de encoding (OOXML é UTF-8).
- ⚠️ **A coluna `Índice` tem rótulos inconsistentes ao longo do tempo** — confirmei em todos os arquivos:
  `'IMA-B'` nas linhas antigas e `'IMA - B'` nas recentes; `'IMA-GERAL'` → `'IMA - Geral'`;
  `'IRF-M 1+'` → `'IRF - M 1+'`; `'IMA-GERAL-EX-C'` → `'IMA - Geral ex-C'`.
  **Normalize com `re.sub(r'\s+', '', s)`** antes de agrupar.
- Nulos esperados: `Variação no Mês/Ano/12M/24M` vazios nas ~1.664 primeiras linhas; `PMR` em ~3.433;
  `Duration` em 388.
- `Last-Modified` observado `Fri, 09 Oct 2026 21:52:48 GMT` → **atualização diária ~18:50 BRT**.
  Há `ETag` → use download condicional (`If-None-Match`). **[CONFIRMADO-SUB]**
- ⚠️ **A listagem do bucket é bloqueada** (`GET /?list-type=2&prefix=...` → `AccessDenied`). Só objetos
  diretos → **os SLUGs precisam ser hard-coded**. Note que "5+" vira `5MAIS` (não `+`, `P` nem `PLUS`). **[CONFIRMADO-SUB]**
- Página de referência: `https://data.anbima.com.br/indices/consulta/ima/resultados-diarios/ima-b-5`
  (o link "Histórico (XLS)" aponta para o S3 acima). **[CONFIRMADO-SUB]**

### Append diário (alternativa ao re-download) **[CONFIRMADO-SUB]**

```
https://www.anbima.com.br/informacoes/ima/arqs/ima_completo.txt   (30.809 B)
https://www.anbima.com.br/informacoes/ima/arqs/ima_completo.xls   (249.344 B)
https://www.anbima.com.br/informacoes/ima/arqs/ima_completo.xml   (87.352 B)
# .csv → 404 (não existe)
```
`ima_completo.txt`: separador **`@`**, encoding **ISO-8859-1**, CRLF, **1ª coluna é um ID de bloco**
(`0@` cabeçalho, `1@` TOTAIS, `2@` COMPOSIÇÃO DE CARTEIRA). Datas `dd/mm/yyyy`, decimal **vírgula**,
`--` = missing. No TXT **não há separador de milhar** (no CSV há) → **prefira o TXT**.
O bloco `2@` traz a **carteira por título** com `Código SELIC`, `Código ISIN`, `Taxa Indicativa (% a.a.)`,
`PU`, `Peso (%)`, `Duration` — útil para decompor os índices.

⚠️ O formulário por data (`ima-geral-down.asp`, `ima-carteira-down.asp`) tem **limite duro de 5 dias úteis
também no servidor** (testado: `09/10`, `05/10`, `02/10/2026` retornam dados; `01/10/2026`, `30/09`,
`15/09`, `02/01/2020` retornam `"Não há dados disponíveis para [data]!"`). **Não serve para backfill.**
Não existe `/informacoes/ima/arqs/<DATA>.xls` nem `ima_historico.xls` (404). **[CONFIRMADO-SUB]**

### Resposta sobre "ANBIMA Data / ANBIMA Feed / DataFit"

| Produto | Situação |
|---|---|
| **ANBIMA Data** (`data.anbima.com.br`) | Portal **aberto e gratuito, sem cadastro** para navegar. Para **preços** o histórico é de apenas 5 dias úteis; para **índices** há o download histórico (= o S3 acima). **[CONFIRMADO-SUB]** |
| **API interna do portal** (`data-api.prd.anbima.com.br/web-bff/*`) | ⛔ **Inviável para script.** Exige header `g-google-authorization` (JWT com token reCAPTCHA) **de uso único**: sem ele → `401 "token cannot be blank"`; reusando um capturado → **`418 "token timed out or duplicated"`**. **[CONFIRMADO-SUB]** |
| **ANBIMA Feed** (`feed.anbima.com.br`) | **PAGO, com contrato.** Faixas citadas na página: ~R$ 686,50/mês (usuário final, pacote Títulos Públicos) a ~R$ 8.238/mês (parceiro). Associados ANBIMA têm acesso gratuito a alguns pacotes. **[NÃO VERIFICADO — leitura de página, sem tabela oficial em PDF]** |
| **API REST documentada** (`api.anbima.com.br/feed/...`) | Existe, **OAuth2 (`client_id` + `access_token`)**. Doc: `https://developers.anbima.com.br/pt/documentacao/precos-indices/`. Sem credencial os paths retornam **401** (confirmando que existem). Inclui a API "IMA para ETFs" (`/feed/precos-indices/v2/ima-etf/`). **[CONFIRMADO-SUB]** |
| **"ANBIMA DataFit"** | ⚠️ **Não encontrado em nenhuma propriedade da ANBIMA.** Provável confusão de nome no e-mail. O produto existente é **ANBIMA Data** (grátis) + **ANBIMA Feed** (pago). **[CONFIRMADO-SUB]** |

### Fallback: o SGS **tem** séries de IMA — mas descontinuadas em 22/05/2023

Eu havia concluído o contrário a partir do catálogo CKAN do BCB (que é um subconjunto); **o agente auxiliar
achou os códigos e eu os re-testei na API** — existem e cobrem 2006. **[CONFIRMADO]**

| SGS | Índice | 1ª data | Última data | Valor em 02/01/2006 |
|---|---|---|---|---|
| **12461** | IRF-M | 02/01/2003 | **22/05/2023** | 2.554,550434 |
| **12462** | IMA-S | 30/04/2004 | **22/05/2023** | 1.147,988972 |
| **12463** | IMA-C | 30/04/2004 | 22/05/2023 (último valor `0.000000`) | 1.044,095395 |
| 12464 / 12465 | IMA-C 5 / IMA-C 5+ | 30/04/2004 | 01/03/2011 | — |
| **12466** | IMA-B | 30/04/2004 | **22/05/2023** | 1.108,830531 |
| **12467** | IMA-B 5 | 30/04/2004 | **22/05/2023** | 1.102,270604 |
| **12468** | IMA-B 5+ | 30/04/2004 | **22/05/2023** | 1.107,295415 |
| **12469** | IMA-Geral | 30/04/2004 | **22/05/2023** | 1.137,405183 |
| 12470 / 12471 | **não existem** (corpo vazio / HTML de erro com HTTP 200) | — | — | — |

- **Não existem séries SGS para IRF-M 1, IRF-M 1+ nem IMA-Geral ex-C.** **[CONFIRMADO-SUB]**
- Os valores do SGS são **número-índice** (não rentabilidade) e **batem com 6 decimais exatos** contra os
  XLS do S3 na data de corte 22/05/2023. **[CONFIRMADO-SUB]**
- **Veredito:** use o **S3 da ANBIMA como primário** (cobre mais, e continua atualizando) e o
  **SGS 12461-12469 apenas como reconciliação/cross-check** de 2003/2004→2023.

### Outros fallbacks
- Fundos indexados via CVM informe diário (`inf_diario_fi_{YYYY}.zip`, 2000→) — proxy caro e enviesado por taxa.
- ETFs: `IMAB11`, `IB5M11`, `FIXA11` (prazos curtos, [NÃO VERIFICADO]).
- `pyield` reconstrói carteiras de NTN-B/LTN a partir de taxas — alto esforço.

---

## B7. CDI acumulado — SGS 12 / 4389 e a fórmula

### Séries
| Código | Conteúdo | Unidade | Freq. | Início | Cobre 2006? |
|---|---|---|---|---|---|
| **12** | CDI — taxa diária | **% ao dia** (`0.050788` = 0,050788 %) | diária | ≤ 2005 | **Sim** **[CONFIRMADO]** |
| **4389** | CDI anualizado base 252 | **% a.a.** (`13.65`) | diária | ≤ 2005 | **Sim** **[CONFIRMADO]** |
| 11 | Selic over diária | % ao dia | diária | ≤ 2005 | **Sim** **[CONFIRMADO]** |
| 1178 | Selic over anualizada base 252 | % a.a. | diária | ≤ 2005 | **Sim** **[CONFIRMADO]** |

### Fórmula de acumulação — validada contra o CDI oficial **[CONFIRMADO]**

```python
# série 12 (ou 11): valores em PERCENTUAL DIÁRIO
fator_acumulado = prod(1 + valor/100 for valor in serie)      # <- divide por 100
retorno_pct = (fator_acumulado - 1) * 100
```

Validação que rodei:

| Ano | SGS 12 (CDI) | SGS 11 (Selic over) | nº dias úteis |
|---|---|---|---|
| **2006** | **15,0271 %** | 15,0768 % | 249 |
| **2015** | **13,2392 %** | 13,2682 % | 250 |

Esses números batem com o CDI anual publicado (15,03 % em 2006; 13,24 % em 2015) → **fórmula e dados
confirmados**. Para agregação trimestral, basta aplicar o mesmo produtório dentro de cada trimestre.

**A partir de 4389 (% a.a. base 252)** a conversão é `fator_dia = (1 + taxa/100) ** (1/252)`. Resultado
equivalente, mas com erro de arredondamento maior — **prefira a série 12**.

### Pegadinhas
- A série 12 **já vem só com dias úteis** (249 registros em 2006) — não precisa de calendário próprio para
  acumular, mas precisa dele para reindexar/alinhar com outras séries. **[CONFIRMADO]**
- Calendário de feriados ANBIMA (para `bizdays`/alinhamento):
  `https://www.anbima.com.br/feriados/arqs/feriados_nacionais.xls` → **HTTP 200, 111.104 bytes,
  `application/vnd.ms-excel`, sem autenticação**. **[CONFIRMADO]**
- O valor da série 12 é **percentual**, não fator. Esquecer o `/100` é o erro clássico.

### Fallback
Ipeadata tem `BM12_TJOVER12` (Selic acumulada no mês) e `BM366_TJOVER366` (Selic Copom diária,
1996-07-01 → 2026-10-09, 11.058 pontos sem nulos). **[CONFIRMADO]**

---

## B8. Índices B3 (IBOV, SMLL, IDIV, IFNC, IMOB, IMAT, INDX, ICON, IEEX, IFIX, UTIL…)

### A fonte que resolve: API interna da B3 (sem chave, sem custo)

```
GET https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{payload_b64}

payload_b64 = base64( json.dumps({"language":"pt-br","index":"IBOV","year":"2006"}) )
Headers recomendados: User-Agent de browser + Referer: https://sistemaswebb3-listados.b3.com.br/
```

**Re-testei este endpoint eu mesmo, de forma independente. [CONFIRMADO]**

**Formato da resposta:** `{"min":{...},"max":{...},"results":[ ... ]}`. `results` tem **31 itens** (um por
dia do mês, campo `day` = 1..31) e cada item traz `rateValue1`..`rateValue12` = **janeiro..dezembro**.
É uma **matriz dia × mês** → precisa de *unpivot*. Valores são **strings em formato pt-BR**
(`"38.484,84"` = 38484,84). **Só fechamento — não há OHLC.** Células inexistentes (feriados, 31 de fevereiro)
vêm nulas/vazias.

Exemplo medido: `IBOV`/2006 → 31 results, **246 pontos não nulos**, `day=1, rateValue2 = "38.484,84"`
(= fechamento de 01/02/2006). **[CONFIRMADO]**

**Endpoints irmãos** **[CONFIRMADO-SUB]**:

| Endpoint | Payload | Retorna |
|---|---|---|
| `indexStatisticsProxy/IndexCall/GetDownloadPortfolioDay/` | `{language,index,year}` | a mesma série, **em CSV codificado em base64** |
| `indexProxy/indexCall/GetPortfolioDay/` | `{language,index,segment:"1"}` | carteira teórica vigente (código, participação %, qtde teórica) |
| `indexProxy/indexCall/GetTheoricalPortfolio/` | idem | carteira teórica |
| `indexProxy/indexCall/GetStockIndex/` | `{language}` | **469 ativos × índices a que pertencem** — ótimo para montar o mapa ativo→índice |

**404 confirmados (não existem):** `GetIndexStatistics`, `GetMonthlyVariation`, `GetAnnualVariation`,
`GetPortfolioYear`, `GetIndexDesc`, `GetSegment`. `GetYearlyVariation` existe mas volta vazio. **[CONFIRMADO-SUB]**

⚠️ **As páginas web da B3 são shells Angular** (`.../indexStatisticsPage/day/IBOV` = 2.333 bytes, só
`<app-root>`). **Scraping de HTML não funciona** — tem que ser a API. **[CONFIRMADO-SUB]**

### Data-base e cobertura de 2006 — medido índice a índice

Busca binária por ano na própria API (1968→2026) **[CONFIRMADO-SUB]**, com os casos críticos para 2006
**re-verificados por mim**.

| Índice | Código na API | 1º ponto | Cobre 2006? | Nota |
|---|---|---|---|---|
| **IBOV** | `IBOV` | 1968-01-02 (=100,00) | ✅ | 246 pontos em 2006 **[CONFIRMADO]** |
| **IEE (Energia Elétrica)** | **`IEEX`** | 1994-01-03 (80,02) | ✅ | 246 pontos em 2006 **[CONFIRMADO]**. ⚠️ o código é `IEEX`, não `IEE` |
| IBrX-100 | `IBXX` | 1994-12-29 | ✅ | |
| IBrX-50 | `IBXL` | 1997-12-30 | ✅ | |
| **INDX (Industrial)** | `INDX` | 1999-12-30 (1.000,00) | ✅ | 246 pontos em 2006 **[CONFIRMADO]** |
| IVBX-2 | `IVBX` | 1999-12-30 | ✅ | |
| IGC | `IGCX` | 2001-08-01 | ✅ | |
| ITAG | `ITAG` | 2002-12-30 | ✅ | |
| **IFNC (Financeiro)** | `IFNC` | 2004-12-30 (858,40) | ✅ | 246 pontos em 2006 **[CONFIRMADO]** |
| **SMLL (Small Caps)** | `SMLL` | 2005-08-31 (517,94) | ✅ | 246 pontos em 2006 **[CONFIRMADO]** |
| MLCX (Mid-Large) | `MLCX` | 2005-08-31 | ✅ | |
| ISE | `ISEE` | 2005-12-01 | ✅ | |
| **IDIV (Dividendos)** | `IDIV` | **2005-12-29 = 1.000,00** | ✅ (exatos 20 anos) | 246 pontos em 2006 **[CONFIRMADO]** |
| **IMAT (Materiais Básicos)** | `IMAT` | **2005-12-29 = 1.000,00** | ✅ (exatos 20 anos) | 246 pontos em 2006 **[CONFIRMADO]** |
| **UTIL (Utilidade Pública)** | `UTIL` | **2005-12-29 = 1.000,00** | ✅ (exatos 20 anos) | 246 pontos em 2006 **[CONFIRMADO]** |
| IBrA | `IBRA` | 2005-12-29 | ✅ | |
| IGCT | `IGCT` | 2005-12-29 | ✅ | |
| **ICON (Consumo)** | `ICON` | **2006-12-28 = 1.000,00** | ❌ **NÃO** | Em 2006 só existe **o ponto-base de 28/12**; série efetiva **a partir de 2007** (245 pontos) **[CONFIRMADO]** |
| IGNM | `IGNM` | 2006-12-28 | ❌ | |
| **IMOB (Imobiliário)** | `IMOB` | **2007-12-28 = 1.000,00** | ❌ **NÃO** | Em 2007 só o ponto-base; série efetiva **a partir de 2008** (249 pontos) **[CONFIRMADO]** |
| ICO2 | `ICO2` | 2010-08-31 | ❌ | |
| BDRX | `BDRX` | 2010-11-01 | ❌ | |
| **IFIX** | `IFIX` | **2010-12-30 = 1.000,00** | ❌ **NÃO** | Série efetiva **a partir de 2011** (249 pontos em 2011) **[CONFIRMADO]** |
| IBEW | `IBEW` | 2012-02-01 | ❌ | |
| **IFIX-L** | **`IFIL`** | 2017-12-28 = 1.000,00 | ❌ | ⚠️ na API o código é `IFIL` |
| IBEE / IBEP | | 2018-02-01 | ❌ | |
| AGFS, GPTW, IBSD, IDVR | | 2019-02-01 | ❌ | |
| IBBC / IBBE / IBBR | | 2020-04-01 | ❌ | |
| BNCO, IBST, IFES, SCSR | | 2026-07-01 | ❌ | índices novíssimos |

**Lista completa dos 40 códigos vivos** **[CONFIRMADO-SUB]**: AGFS, BDRX, BNCO, GPTW, IBBC, IBBE, IBBR,
IBEE, IBEP, IBEW, IBHB, IBLV, IBOV, IBRA, IBSD, IBST, IBXL, IBXX, ICO2, ICON, IDIV, IDVR, IEEX, IFES,
IFIL, IFIX, IFNC, IGCT, IGCX, IGNM, IMAT, IMOB, INDX, ISEE, ITAG, IVBX, MLCX, SCSR, SMLL, UTIL.

### ⚠️ Quais índices do e-mail NÃO têm 20 anos — resposta direta

| Índice pedido | Veredito |
|---|---|
| IBOV, SMLL, IDIV, IFNC, IMAT, INDX, IEEX (IEE), UTIL | ✅ **têm 2006 completo** |
| **ICON (Consumo)** | ❌ **começa em 2007** — perde 2006 |
| **IMOB (Imobiliário)** | ❌ **começa em 2008** — perde 2006-2007 |
| **IFIX** | ❌ **começa em 2011** — perde 2006-2010 (metade da janela) |

### Yahoo Finance — o que funciona e o que é armadilha **[CONFIRMADO-SUB]**

Teste em `https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=max&interval=1mo`:

| Ticker | Resultado |
|---|---|
| `^BVSP` | ✅ histórico desde **1993-04-27** |
| `^IBX50` | ✅ desde **2012-12-13** |
| `SMLL.SA`, `IFIX.SA`, `IDIV.SA`, `IFNC.SA`, `IMOB.SA`, `IMAT.SA`, `INDX.SA`, `ICON.SA`, `UTIL.SA`, `IBXX.SA` | ⚠️ **HTTP 200, quote existe, mas devolve 1 único ponto (hoje)** em qualquer `range`. **Inútil — e falha silenciosamente.** |
| `^IBX`, `^IFIX`, `^SMLL`, `^IDIV`, `IEEX.SA`, `IEE.SA`, `IBXL.SA`, `IBOV.SA` | ❌ 404 |

→ **`yfinance` NÃO serve para índices setoriais da B3** (usa esse mesmo backend). Valide sempre `len(df) > 1`.

**ETFs como fallback (price return, não total return)** **[CONFIRMADO-SUB]** — `firstTradeDate`:
`BOVA11.SA` 2008-11-28 · `SMAL11.SA` 2008-11-28 · `PIBB11.SA` 2008-01-02 · `FIND11.SA` 2011-04-01 ·
`GOVE11.SA` 2011-11-03 · `ISUS11.SA` 2011-10-31 · `DIVO11.SA` 2012-01-31 · `MATB11.SA` 2012-01-31 ·
`ECOO11.SA` 2012-06-15 · `XBOV11.SA` 2012-11-12 · `IVVB11.SA` 2014-04-29 (S&P 500) · `BOVV11.SA` 2016-07-29 ·
`SMAC11.SA` 2020-01-31 · `IFRA11.SA` 2020-12-11 · `XFIX11.SA` 2020-11-27 (IFIX) · `TECK11.SA` 2021-04-28 ·
`ITIT11.SA` 2022-03-21 (Teva FII Tijolo) · `ITIP11.SA` 2024-01-30 (Teva FII Papel).

⚠️ Dois riscos: (a) ETF distribui rendimento → **subestima** o retorno de um índice de retorno total
(crítico para IFIX); (b) o Yahoo **troca a granularidade silenciosamente** — pedido `interval=1mo` retornou
`dataGranularity: "1wk"` em XFIX11/SMAC11/TECK11/IFRA11. **Peça sempre `interval=1d` e reamostre.** **[CONFIRMADO-SUB]**

### B3 COTAHIST — cotações de todos os papéis (para construção própria) **[CONFIRMADO-SUB]**

```
https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{YYYY}.ZIP      # anual
https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_M{MMYYYY}.ZIP    # mensal
https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{DDMMYYYY}.ZIP  # diário
# espelho: https://www.b3.com.br/pesquisapregao/download?filelist=COTAHIST_A2025.ZIP
```
- Anual **1986 → 2026** (1985 = 404). Tamanhos: 2006 = 9,3 MB · 2024 = 79 MB · 2026 parcial = 91 MB.
- ⚠️ **use sempre `https://`** — `http://` no ano corrente devolveu **520 (Cloudflare)**.
- ZIP com 1 membro `.TXT`: **largura fixa 245**, **latin-1**, **CRLF**, header `00` / dados `01` / trailer `99`.
- Campos-chave (1-indexado): `DATA` 3-10 (`YYYYMMDD`) · `CODBDI` 11-12 · `CODNEG` 13-24 (ticker) ·
  `TPMERC` 25-27 (`010` = à vista) · `PREABE/PREMAX/PREMIN/PREMED/PREULT` 57-69 / 70-82 / 83-95 / 96-108 / 109-121
  (**inteiros — dividir por 100**) · `TOTNEG` 148-152 · `QUATOT` 153-170 · `VOLTOT` 171-188 (**÷100**) ·
  `FATCOT` 211-217 · **`CODISI` 231-242 (ISIN)**.
- `CODBDI`: `02` ações lote padrão · **`12` FII** · **`13` FIAGRO** · `14` ETF · `34`/`36` BDR · `96` fracionário.
- ⚠️ **Não é ajustado** por desdobramento/amortização e **não traz proventos**.

### Fallback para índices B3
1. `indexStatisticsProxy` (primário, acima).
2. Lib **`mercados`** (PythonicCafe) — scrapers B3+CVM, inclui valores históricos de índices. **[CONFIRMADO-SUB]**
3. ETFs via `yfinance` (só sanity check).
4. Reconstrução própria a partir de COTAHIST + carteiras teóricas — **alto esforço**, e as carteiras
   históricas não são servidas pela API (só a vigente).

---

## B9. IFIX e segmentações de FII (Tijolo × Papel, Logística, Shoppings)

### Confirmação: a B3 **não** tem índice de FII por segmento **[CONFIRMADO-SUB]**

Varredura dos 40 códigos de índice da B3 → só existem dois índices de FII:

| Índice | Código API | Base | Metodologia (HTTP 200) |
|---|---|---|---|
| **IFIX** | `IFIX` | **30/12/2010 = 1.000,00**, 99 ativos hoje | `https://www.b3.com.br/data/files/2A/56/E3/DD/A3943710DB551337AC094EA8/IFIX-Metodologia-pt-br.pdf` — **retorno total**, ponderado por valor de mercado, teto de 20 % por fundo, corte em 95 % do Índice de Negociabilidade |
| **IFIX-L** | **`IFIL`** | 28/12/2017 = 1.000,00, 58 ativos | `https://www.b3.com.br/data/files/2F/B7/B9/BA/C1AC77101FCDCB77AC094EA8/IFIX%20L%20-%20Metodologia.pdf` — subconjunto de alta liquidez (corte em 85 % do IN), rebalanceamento quadrimestral |

→ **Sim, o IFIX-L existe** (desde 2018) — mas **não** é segmentação setorial, é filtro de liquidez.
Manual de procedimentos dos índices (onde ficam as data-base oficiais):
`https://www.b3.com.br/data/files/D5/70/03/E6/D3E7A9105B12E5A9AC094EA8/Manual-de-procedimentos-pt-br%20_Modelo%20Novo_%20nov25.pdf` **[CONFIRMADO-SUB]**

### Opção recomendada nº 1: índices Teva — públicos, gratuitos e programáticos **[CONFIRMADO-SUB]**

O site da Teva Indices serve os dados de um **bucket do Google Cloud Storage público e listável**:

```
# listar (JSON API, sem auth)
GET https://storage.googleapis.com/storage/v1/b/teva-indices-public/o?prefix=quotations-download-file/&maxResults=1000
# baixar
GET https://storage.googleapis.com/teva-indices-public/quotations-download-file/{nome-urlencoded}
```

**290 objetos** (132 `.parquet` + 157 `.xlsx`), atualizados em **2026-10-10**. Índices de FII disponíveis:

| Prefixo do arquivo | Segmento |
|---|---|
| `3.1.1 Índice de Fundos Imobiliários` | geral |
| `3.1.3 / 3.1.4 / 3.1.5` | TOP 40 / TOP 30 / TOP 15 (liquidez) |
| **`3.2.1 Índice Teva de Fundos Imobiliários de Papel`** | **Papel / CRI** |
| **`3.2.2 Índice Teva de Fundos Imobiliários de Tijolo`** | **Tijolo** |
| **`3.3.1 … de Logística`** | **Logística** |
| **`3.3.2 … de Lajes Corporativas`** | **Lajes** |
| **`3.3.3 … de Shoppings`** | **Shoppings** |
| `3.5.1 / 3.5.2` | fator Dividendos / Valor |

Conteúdo: 2 colunas — `Data de referência` (`dd/mm/yyyy`) e **`Cotação do Índice Retorno Total`**.
**Todos começam em 02/01/2019 = 100**, ~1.937 linhas, último ponto **09/10/2026**.
Valores em 09/10/2026: Tijolo 160,76 · Papel 199,98 · Logística 192,65 · Shoppings 184,98 · **Lajes 116,73**
— a dispersão setorial é grande, que é justamente o sinal procurado.

**Carteiras (classificação pronta por segmento)** — bucket `teva-downloads`, também listável:
```
https://storage.googleapis.com/teva-downloads/rebalanced_portfolios/carteira-indice-teva-de-fundos-imobiliarios-de-tijolo.xlsx
https://storage.googleapis.com/teva-downloads/rebalanced_portfolios/carteira-indice-teva-de-fundos-imobiliarios-de-papel.xlsx
```
Colunas: `Data de rebalanceamento`, `Ativo`, `Nome do Fundo`, `Peso no rebalanceamento`. Só a carteira
**corrente** (rebal. 2026-09-01), não histórica.

⚠️ **Riscos:** (a) o nome do arquivo tem **versão embutida** (`v0.27`) e vai mudar — **não hardcode**:
liste o bucket e faça match por regex no prefixo numérico; (b) **só 2019→**, cobre ~37 %
da janela de 20 anos; (c) é provedor privado, sem garantia de permanência nem licença explícita.

### Opção recomendada nº 2 (para estender antes de 2019): construção própria

1. **Cotações**: COTAHIST (`CODBDI` em `12`/`13` e `TPMERC` = `010`), anual desde 1986.
2. **Classificação de segmento**: CVM, informe mensal de FII —
   `https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{YYYY}.zip`,
   anos **2016 → 2026** **[CONFIRMADO-SUB]**. (Também `INF_TRIMESTRAL`, `INF_ANUAL`, `DFIN`.
   ⚠️ **não existe** `FII/CAD/cad_fii.csv` → 404.)
   Cada ZIP tem 3 CSVs (`;`, **latin-1**): `_geral_`, `_ativo_passivo_`, `_complemento_`.
3. **Join**: `COTAHIST.CODISI` (pos. 231-242) ≡ `inf_mensal_fii_geral.Codigo_ISIN`.
   Taxa de match medida no pregão de 09/10/2026: **237 de 277 tickers (85,5 %)**. **[CONFIRMADO-SUB]**
   Use CNPJ/nome como fallback para o resto.
4. **Dividendos** (para total return próprio):
   `https://sistemaswebb3-listados.b3.com.br/fundsProxy/fundsCall/GetListedSupplementFunds/{b64}` com
   payload `{"cnpj":"...","identifierFund":"HGLG","typeFund":7}` → `cashDividends[]` com `paymentDate`,
   `rate`, `relatedTo`. **[CONFIRMADO-SUB]** (⚠️ `GetListedFundsSIG` devolve `totalRecords: 0` — a listagem
   está quebrada; alimente CNPJ + código a partir da CVM.)

⚠️ **Quebra de série crítica na CVM (medida mês a mês) [CONFIRMADO-SUB]:**
- Coluna `Mandato` preenchida **até 2025-07**; em 2025-08 cai para 5 linhas e **de 2025-09 em diante é 100 %
  vazia**. Vocabulário antigo: `Renda`, `Híbrido`, `Títulos e Valores Mobiliários`, `Desenvolvimento para
  Renda`, `Desenvolvimento para Venda`.
- `Segmento_Atuacao` **mudou de taxonomia** na mesma virada (Res. CVM 175): antes `Híbrido`,
  `Lajes Corporativas`, `Títulos e Val. Mob.`, `Shoppings`, `Logística`, `Residencial`, `Outros`, `Hospital`,
  `Hotel`; em 2026 `Multicategoria` (46 %), `Outros` (26 %), `Logística`, `Residencial`, `Shoppings`,
  **`Escritórios`** (substitui "Lajes Corporativas"), `Hospital`, `Varejo`, `Hotel`, `Educacional`.
- **No formato novo não dá para separar Tijolo × Papel pelo `Segmento_Atuacao`** (fundos de CRI caem em
  `Outros`/`Multicategoria`) e `Mandato` está vazio. **É a razão prática para usar a Teva.**
- Nomes de coluna também mudaram: 2016 usa `CNPJ_Fundo`/`Nome_Fundo`; de 2021 em diante
  `CNPJ_Fundo_Classe`/`Nome_Fundo_Classe` + `Tipo_Fundo_Classe`. O parser precisa de *alias*.

**Classificador robusto, imune à taxonomia** — usar o balanço (`inf_mensal_fii_ativo_passivo_YYYY.csv`):
```
tijolo_share = (Direitos_Bens_Imoveis + Terrenos + Imoveis_Renda_* + Imoveis_Venda_* + Outros_Direitos_Reais) / Total_Investido
papel_share  = (CRI + CRI_CRA + LCI + LCI_LCA + LIG + Letras_Hipotecarias + Debentures + Cedulas_Debentures) / Total_Investido
```
Mensal, orientado a dado, sobrevive à mudança de 2025. **Recomendo como classificador primário, com a Teva
como validação cruzada.** **[CONFIRMADO-SUB — colunas lidas do header]**
`inf_mensal_fii_complemento_YYYY.csv` dá `Patrimonio_Liquido`, `Valor_Patrimonial_Cotas`,
`Percentual_Dividend_Yield_Mes`, `Total_Numero_Cotistas` → P/VP e DY por fundo.

Nota adicional: os informes **diários de fundos em geral** (que permitem proxy de IMA via fundo indexado)
estão em `https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{YYYY}.zip` —
**anos 2000 a 2020 no diretório HIST** (2006 = 30,98 MB, HTTP 200) e mensais
`inf_diario_fi_{YYYYMM}.zip` de 2021 em diante. Cadastro de fundos:
`https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv` (17,9 MB, HTTP 200). **[CONFIRMADO]**

### Sites terciários de FII (todos responderam 200 com UA de browser) **[CONFIRMADO-SUB]**
`fundsexplorer.com.br/ranking` (HTML com dados, WordPress, `wp-json` exposto) ·
`fundamentus.com.br/fii_resultado.php` (tabela HTML com coluna `Segmento` — o mais fácil de raspar) ·
`investidor10.com.br/fiis/` · `statusinvest.com.br/fundos-imobiliarios/busca-avancada` · `clubefii.com.br`.
Nenhum 403 nesta sessão, mas todos atrás de Cloudflare e **sem licença de uso** → fonte terciária apenas.

### Veredito do item 9
1. **IFIX** (B3 API, 2011→) para o agregado. Antes de 2011 **não existe** benchmark de FII — lacuna real.
2. **Teva** (2019→) para Tijolo/Papel/Logística/Shoppings/Lajes — pronto e gratuito. **Recomendado.**
3. **Construção própria** (COTAHIST + CVM, classificação desde 2016) se precisar estender a segmentação
   para 2016-2019. Antes de 2016 o mercado de FII era pequeno e ilíquido — **recomendo não tentar**.

---

# BLOCO C — INTERNACIONAL (item 10) E IPEADATA (item 11)

## C10. Fontes internacionais para "tamanho da alocação internacional"

### C10.1 FRED — CSV sem chave (rota recomendada)

```
# SEM chave, CSV direto:
https://fred.stlouisfed.org/graph/fredgraph.csv?id={ID}&cosd=1900-01-01&coed=2026-12-31
# agregação: &fq=Monthly&fam=avg

# COM chave (gratuita):
https://api.stlouisfed.org/fred/series/observations?series_id={ID}&api_key={KEY}&file_type=json
```

- **Chave gratuita** em `https://fredaccount.stlouisfed.org/apikeys` (requer conta). Sem chave a API REST
  devolve **HTTP 400** `"Variable api_key is not set"`. **[CONFIRMADO-SUB]**
- **Rate limit: 120 req/min por chave**, excesso → 429. **[NÃO VERIFICADO — número de fonte secundária]**
- ⚠️ **Pegadinha crítica:** `fredgraph.csv` **sem `cosd` aplica a janela-padrão do gráfico**, não a série
  inteira (ex.: `BAMLEMCBPIOAS` sem `cosd` começava em 2023-10-10). **Sempre passe `cosd=1900-01-01`.** **[CONFIRMADO-SUB]**
- ⚠️ ID inexistente → **404 com HTML**; detecte checando se a 1ª linha começa com `<`. **[CONFIRMADO-SUB]**
- ⚠️ **Latência:** `fred.stlouisfed.org` respondeu muito lentamente / com corpo vazio nas minhas tentativas
  desta sessão (timeout de 120 s estourado em lote de 4 IDs). Trate como fonte lenta: serialize,
  `timeout` alto, retry. **[CONFIRMADO por mim — comportamento de rede, não refuta os IDs]**

### IDs verificados (com `cosd=1900-01-01`) **[CONFIRMADO-SUB]**

| Série | ID | Início real | Fim | N | Cobre 2006? |
|---|---|---|---|---|---|
| **S&P 500** | `SP500` | **2016-10-10** | 2026-10-09 | 2.611 | ❌ **SÓ 10 ANOS (janela rolante, licença S&P)** |
| Dow Jones | `DJIA` | 2016-10-10 | 2026-10-09 | 2.611 | ❌ **só 10 anos** |
| Nasdaq Composite | `NASDAQCOM` | 1971-02-05 | 2026-10-09 | 14.526 | ✅ |
| Nasdaq 100 | `NASDAQ100` | 1986-01-02 | 2026-10-09 | 10.637 | ✅ |
| **Treasury 10y** | `DGS10` | 1962-01-02 | 2026-10-08 | 16.899 | ✅ |
| Treasury 2y | `DGS2` | 1976-06-01 | 2026-10-08 | 13.139 | ✅ |
| **Spread 10y-2y** | `T10Y2Y` | 1976-06-01 | 2026-10-09 | 13.140 | ✅ |
| Spread 10y-3m | `T10Y3M` | 1982-01-04 | 2026-10-09 | 11.681 | ✅ |
| **Dólar índice (broad)** | `DTWEXBGS` | **2006-01-02** | 2026-10-02 | 5.416 | ✅ (começa exatamente em 2006) |
| Dólar vs av./emerg. | `DTWEXAFEGS` / `DTWEXEMEGS` | 2006-01-02 | 2026-10-02 | 5.416 | ✅ |
| **DXY antigo** | `DTWEXM` | 1973-01-02 | **2019-12-31** | 12.262 | ⚠️ **DESCONTINUADO** |
| Fed Funds diário / mensal | `DFF` / `FEDFUNDS` | 1954-07-01 | 2026-10-08 / 2026-09-01 | 26.399 / 868 | ✅ |
| **VIX** | `VIXCLS` | 1990-01-02 | 2026-10-08 | 9.594 | ✅ |
| VIX 3 meses | `VXVCLS` | 2007-12-04 | 2026-10-08 | — | ⚠️ só 2007+ |
| **BRL/USD** | `DEXBZUS` | 1995-01-02 | 2026-10-02 | 8.286 | ✅ |
| **Breakeven 10y EUA** | `T10YIE` | 2003-01-02 | 2026-10-09 | 6.203 | ✅ |
| SOFR | `SOFR` | 2018-04-03 | — | — | ⚠️ só 2018+ |
| REER Brasil (BIS) | `RBBRBIS` | 1994-01-01 | 2026-07-01 | 392 (mensal) | ✅ |
| Ibovespa (OECD) | `SPASTT01BRM661N` | 1980-01-01 | 2026-08-01 | mensal | ✅ |

**404 confirmados:** `WILL5000IND`, `WILL5000PR`, `WILLLRGCAP`, `SP500INDX`, `GOLDAMGBD228NLBM`,
`CBBRBIS`, `BAMLEM1BRRBCRPITRIV`, `BRAIRLTLT01STM`. **[CONFIRMADO-SUB]**

⚠️ **Séries ICE BofA de OAS de crédito têm janela rolante de 3 anos** (`BAMLEMCBPIOAS`,
`BAMLEMRLCRPILAOAS`, `BAMLEMRACRPIASIAOAS`, `BAMLEMHBHYCRPIOAS`, `BAMLHE00EHYIOAS`): todas começam em
**2023-10-10**. Restrição de licença ICE. **[CONFIRMADO-SUB]**

### C10.2 ⚠️ S&P 500 no FRED **não serve** — alternativas

1. **Yahoo `^GSPC`** — grátis, diário desde 1927, mensal desde 1985-01.
2. **MSCI USA oficial** (código `984000`) — diário desde 1997-01-01, grátis.
3. **ETF `IVV`** (Yahoo) — desde **2000-05-19**, com dividendos via `auto_adjust`.

### C10.3 Yahoo Finance **[CONFIRMADO-SUB]**

```
https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={epoch}&period2={epoch}&interval=1d
```
- 🚨 **Sem `User-Agent` → HTTP 429** `"Edge: Too Many Requests"`. Com UA de browser → 200 em 100 % dos
  20+ tickers testados.
- ⛔ O endpoint CSV v7 (`/v7/finance/download/...`) está **morto: HTTP 401**.
- ⚠️ **`range=max&interval=1mo` trunca silenciosamente**: `^GSPC` deu **169 pontos** (1984-12→2026-10) em
  vez de ~502. Com `period1`/`period2` em epoch seconds deu **502**. **Nunca use `range=max` para
  séries mensais longas.** O comportamento é inconsistente entre tickers.

| Ticker | firstTradeDate | Cobre 2006? |
|---|---|---|
| `^GSPC` | 1927-12-30 | ✅ |
| `^VIX` | 1990-01-02 | ✅ |
| `^TNX` / `^FVX` / `^IRX` (UST 10y/5y/13w) | 1962-01-02 / 1962-01-02 / 1960-01-04 | ✅ |
| `DX-Y.NYB` (DXY) | 1971-01-04 | ✅ |
| `^DJI` / `^IXIC` | 1992-01-02 / 1971-02-05 | ✅ |
| `BRL=X` / `USDBRL=X` | **2003-12-01** | ✅ (mas prefira PTAX/`DEXBZUS`) |
| `IVV` | 2000-05-19 | ✅ |
| `EEM` | 2003-04-14 | ✅ |
| **`ACWI`** | **2008-03-28** | ❌ |
| **`URTH`** | **2012-01-12** | ❌ |
| `VT` | 2008-06-26 | ❌ |

### C10.4 🏆 MSCI oficial — endpoint JSON público, gratuito, sem chave **[CONFIRMADO-SUB]**

```
https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph
  ?currency_symbol=USD
  &index_variant=STRD          # STRD=preço | NETR=net total return
  &start_date=19970101&end_date=20261009
  &data_frequency=DAILY        # DAILY | END_OF_MONTH | ANNUAL
  &baseValue=false&index_codes=892400
```
Exige `User-Agent` de browser. Resposta: `{"indexes":{"INDEX_LEVELS":[{"level_eod":…,"calc_date":20060102},…]}}`

| Índice | `index_codes` | STRD início | NETR início | N (diário) | Cobre 2006? |
|---|---|---|---|---|---|
| **MSCI ACWI** | **892400** | 1997-01-01 | 2000-12-29 | 7.768 | ✅ |
| **MSCI World** | **990100** | 1997-01-01 | 2000-12-29 | 7.768 | ✅ |
| MSCI EM | 891800 | 1997-01-01 | 2000-12-29 | 7.768 | ✅ |
| MSCI USA | 984000 | 1997-01-01 | 2000-12-29 | 7.768 | ✅ |
| MSCI Brazil | `705000` → lista vazia | — | — | — | código **a confirmar** |

- `start_date` < 1997-01-01 → erro `"Calculation date cannot be earlier than 19970101"`.
- `END_OF_MONTH` → 357 pontos; `ANNUAL` → 29. `MONTHLY`/`WEEKLY` dão erro.
- ⚠️ **Endpoint não documentado da app web do MSCI: pode quebrar sem aviso.** Mantenha `ACWI`/`URTH`
  (Yahoo) como fallback, aceitando o início em 2008/2012.
- **Recomendação:** use **MSCI ACWI `892400` variante `NETR`** (retorno total, desde 2000-12-29) para o
  bloco internacional — cobre 2006 com folga e é o índice de verdade, não um ETF com tracking error.

### C10.5 🔴 CDS Brasil 5 anos / EMBI+ — **não existe fonte gratuita, programática, com 20 anos**

Diagnóstico, todo verificado:

| Fonte | Resultado |
|---|---|
| **Ipeadata `JPM366_EMBI366`** | **1994-04-29 → 2024-07-30**, `SERSTATUS: "I"` = **INATIVA**. 10.126 linhas, 7.756 não nulas; último valor 228,0. **[CONFIRMADO por mim]** É a **única** série de risco-país em todo o Ipeadata (varri os 3.606 metadados). |
| Motivo | **EMBI+ descontinuado pelo JP Morgan em julho/2024** — consistente com o fim da série. **[NÃO VERIFICADO]** |
| **World Bank** | ⛔ Listados os **36 indicadores** do Global Economic Monitor: **nenhum** EMBI/spread/risco-país. **[CONFIRMADO-SUB]** |
| **FRED** | ⛔ Sem série Brasil-CDS. ICE BofA de EM/LatAm têm janela rolante de 3 anos. **[CONFIRMADO-SUB]** |
| **Investing.com** | ⛔ **HTTP 403 Cloudflare** em `api.investing.com`. É a razão da morte do `investpy`. **[CONFIRMADO-SUB]** |
| worldgovernmentbonds.com | HTML sem histórico (está em JS/chart). Não é scraping viável. **[CONFIRMADO-SUB]** |
| **CRP by SPA** (Saint Paul Advisors) | Substituto "oficial" do EMBI+. Oferece **só o valor corrente** (225 bps em jun/2026), um PDF e um Excel com o histórico **do EMBI+** (não do CRP). **Sem API.** **[CONFIRMADO-SUB]** |
| MacroMicro / Cbonds | Têm CDS 5y Brasil, **exigem login/assinatura**. **[NÃO VERIFICADO]** |

#### ✅ Recomendação: splice de duas pernas + proxy de mercado

```
risco_brasil(t) =
  perna A  1994-04-29 → 2024-07-30   Ipeadata JPM366_EMBI366            [grátis, CONFIRMADO]
  perna B  2023-10-10 → hoje         FRED BAMLEMRLCRPILAOAS             [grátis, janela rolante 3 anos]
                                     (ICE BofA LatAm EM Corporate OAS, diário)
  overlap  2023-10-10 .. 2024-07-30 (~200 obs) → calibre nível e escala por OLS e encadeie
```
⚠️ A perna B **rola**: em 2027 o início de 2023 desaparece. **Arquive diariamente desde já.**

**Proxy tecnicamente melhor (recomendação do documento):** **cupom cambial (DDI/FRC) da B3 menos UST** —
market-implied, diário, gratuito, histórico longo, acessível via `pyield` (`yd.futuro`, `yd.di1`).
É literalmente o preço do risco Brasil em dólar. **[NÃO VERIFICADO — avaliar na implementação]**
Outros: Damodaran/NYU Stern `pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html`
(grátis, mas **semestral/anual, planilha, sem API**); NTN-B/NTN-F vs UST ajustado por inflação;
`RBBRBIS` (REER Brasil, mensal, 1994→).

### C10.6 World Bank e OECD — vale como fallback? **[CONFIRMADO-SUB]**

| API | Endpoint | Veredito |
|---|---|---|
| **World Bank v2** | `https://api.worldbank.org/v2/country/BRA/indicator/{IND}?format=json&date=2000:2026` | ✅ sem chave, dados até 2025, 92 fontes. ❌ **frequência anual** (WDI) e **sem risco-país**. ⚠️ resposta é **array de 2 elementos** `[{paginação},[dados]]`; `per_page` default baixíssimo. **Só para contexto macro anual.** |
| **OECD SDMX** | `https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/BRA.M.IRLT......?startPeriod=2006-01&format=csvfile` | ✅ sem chave, CSV nativo, mensal, cobre Brasil. ❌ **sintaxe SDMX hostil** (chave posicional, a contagem de pontos tem que bater). ⚠️ **as linhas NÃO vêm em ordem cronológica** — ordene. **Fallback para métricas harmonizadas cross-country.** |

---

## C11. Ipeadata como agregador (item 11)

```
GET http://www.ipeadata.gov.br/api/odata4/$metadata
GET http://www.ipeadata.gov.br/api/odata4/Metadados                      # catálogo inteiro
GET http://www.ipeadata.gov.br/api/odata4/Metadados('{SERCODIGO}')       # metadado de 1 série
GET http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{COD}')
```

- **Autenticação:** nenhuma. **Custo:** zero. **[CONFIRMADO]**
- Catálogo: **3.606 séries, 7,36 MB** no `Metadados` completo. Campos: `SERCODIGO, SERNOME,
  SERCOMENTARIO, SERATUALIZACAO, BASNOME, FNTSIGLA, FNTNOME, FNTURL, PERNOME, UNINOME, MULNOME,
  SERSTATUS, TEMCODIGO, PAICODIGO, SERNUMERICA`. **[CONFIRMADO]**
- `ValoresSerie` devolve `SERCODIGO, VALDATA` (ISO com fuso `-03:00`), `VALVALOR`, `NIVNOME`, `TERCODIGO`.

### ⚠️⚠️ Pegadinhas graves, confirmadas por mim

| Recurso | Comportamento |
|---|---|
| `$filter` em `ValoresSerie` | ⛔ **IGNORADO silenciosamente.** Pedi `VALDATA ge 2006-01-01` e recebi a série desde **1994-04-29**. **[CONFIRMADO]** |
| `$top` / `$orderby` em `ValoresSerie` | ⛔ **IGNORADOS.** **[CONFIRMADO-SUB]** |
| `contains(SERNOME,'EMBI')` em `Metadados` | ⛔ **HTTP 400** `"The query specified in the URI is not valid"`. **[CONFIRMADO]** |
| `Metadados('CODIGO')` | ✅ funciona |
| Valores nulos | abundantes: `JPM366_EMBI366` tem 10.126 linhas e só **7.756 não nulas** (fins de semana vêm como `null`). **Filtre `VALVALOR is not None`.** **[CONFIRMADO]** |
| Encoding | JSON com `\uXXXX` escapado — seguro. **[CONFIRMADO]** |
| Protocolo | o `@odata.context` volta como `http://` (sem TLS). **[CONFIRMADO]** |

→ **Padrão de uso correto: baixe a série inteira e filtre em pandas.** Não tente paginar/filtrar na API.

### O que o Ipeadata realmente simplifica **[CONFIRMADO — lido do catálogo]**

| Série | SERCODIGO | Freq. | Faixa verificada | Por que vale |
|---|---|---|---|---|
| **Ibovespa fechamento** | `GM366_IBVSP366` | diária | **1993-04-27 → 2026-10-08**, 8.317 não nulos | histórico mais longo que o Yahoo, fonte BM&FBovespa |
| Ibovespa acum. no mês | `GM12_IBVSP12` | mensal | — | fonte ANBIMA |
| **ETTJ prefixada LTN 1/3/6/12 meses** | `ANBIMA366_TJTLN{1,3,6,12}366` | diária | **2000-04-04 → 2026-10-08**, 8.404 não nulos | **única fonte gratuita de ETTJ ANBIMA com histórico longo** (só ponta curta) |
| Mesmas, mensais | `ANBIMA12_TJTLN{1,3,6,12}12` | mensal | — | |
| **Selic Copom diária** | `BM366_TJOVER366` | diária | **1996-07-01 → 2026-10-09**, 11.058 **sem nulos** | sem o limite de 10 anos do SGS |
| Selic over mensal / trimestral / anual | `BM12_TJOVER12` · `PAN4_TJOVER4` · `PAN_TJOVER` | mensal/trim./anual | — | agregação pronta |
| **EMBI+ Risco-Brasil** | `JPM366_EMBI366` | diária | 1994-04-29 → **2024-07-30 (INATIVA)** | ver C10.5 |
| Expectativa IPCA 12m | `BM12_IPCAEXP1212` | mensal | — | alternativa ao Focus |
| Núcleos e aberturas do IPCA | `BM12_IPCA*` (36 séries) | mensal | — | livres/monitorados, comercializáveis, serviços, duráveis |
| **PIB trimestral IBGE** | família `SCN104_*` (**121 séries**) | trimestral | — | abertura setorial pronta, inclui `*AS104` dessazonalizadas |
| Câmbio R$/US$ | `BM12_ERV12`, `BM12_ERVF12`, `BM_ERV`… (64 séries de "Taxa de câmbio") | anual/mensal/diária | — | médias e fins de período já calculados |
| Nasdaq / Dow Jones | `SGS366_NASDAQ366`, `GM366_DOW366` | diária | — | |

### ⛔ O que o Ipeadata **NÃO** tem (varri os 3.606 nomes) **[CONFIRMADO]**
- **Nenhuma série de IMA / IRF-M** (0 ocorrências) → use o S3 da ANBIMA (B6).
- **Nenhum IFIX** nem índice setorial da B3 (só Ibovespa) → use a API da B3 (B8).
- **Nenhum CDS** (0 ocorrências).
- **Swaps DI × pré (`BMF12_SWAPDI*`) estão INATIVOS** — mesma morte do SGS 7801-7806.
- Séries com sufixo `- INATIVA` no `SERNOME` e `SERSTATUS = "I"`: **sempre checar antes de usar.**

---

# TABELA-RESUMO: item do e-mail → fonte → esforço → fallback

Esforço: **baixo** = 1 GET/arquivo pronto · **médio** = paginação/parse não trivial · **alto** = reconstrução.

| # | Item do e-mail | Fonte primária | Identificador | Início | Cobre 2006? | Esforço | Fallback |
|---|---|---|---|---|---|---|---|
| A1 | PIB — IBC-Br | BCB SGS | **24364** (c/ ajuste sazonal) · 24363 (s/) | 2003 | **Sim** | baixo | Ipeadata |
| A1b | PIB trimestral IBGE | IBGE SIDRA | **t/1621 v/584 c11255/90707** (dessaz.) | 1996T1 | **Sim** | baixo | **SGS 22109** (idêntico) · Ipeadata `SCN104_*` |
| A1c | PIB — variação T/T-1 dessaz. | IBGE SIDRA | t/5932 v/**6564** | 1996T1 | **Sim** | baixo | calcular de 1621 |
| A2 | IPCA mensal | BCB SGS | **433** | 01/1980 | **Sim** | baixo | SIDRA t/1737 v/63 (idêntico) |
| A2b | IPCA 12 meses | BCB SGS | **13522** | 12/1980 | **Sim** | baixo | SIDRA t/1737 v/2265 (idêntico) |
| A2c | IPCA nº-índice e núcleos | IBGE SIDRA / SGS | t/1737 v/2266 · SGS 4466, 11426-11428, 16121-16122 | 1979/2000 | **Sim** | baixo | — |
| A3 | Expectativas Focus | BCB Olinda OData | `ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`, `ExpectativasMercadoTrimestrais`, `ExpectativasMercadoSelic`, `...Inflacao12Meses` | 1999/2000/2001/2004 | **Sim** | médio | `python-bcb` · Ipeadata `BM12_IPCAEXP1212` |
| A4 | Selic Over | BCB SGS | **11** (%/dia) · **1178** (% a.a.) | ≤2005 | **Sim** | baixo (chunks 10a) | Ipeadata `BM366_TJOVER366` |
| A4b | Selic meta / mensal | BCB SGS | **432** · **4189** · 4390 | 1986/1999 | **Sim** | baixo | — |
| A5 | Taxas de títulos públicos | **Tesouro Transparente CKAN** | `precotaxatesourodireto.csv` | **31/12/2004** | **Sim** | baixo | ANBIMA `ms*.txt` (só ~20 d.u.) · `pyield` |
| A6 | ETTJ / inclinação da curva | **Tesouro Direto (interpolado)** | idem A5 | 31/12/2004 | **Sim** (real); **parcial** (nominal longa <2010) | **médio** | Ipeadata `ANBIMA366_TJTLN*366` (só ≤12m) · ANBIMA `CZ-down.asp` (só ~20 d.u.) · **ANBIMA Feed (pago)** · B3 DI futuro via `pyield` |
| A6b | ETTJ Svensson (betas/lambdas) | ANBIMA `CZ-down.asp` | POST `saida=csv` | **14/09/2026** | **NÃO** | baixo | ANBIMA Feed (pago). **Acumular diariamente** |
| A7 | IPCA histórico completo | IBGE SIDRA | **t/1737** | 12/1979 | **Sim** | baixo | SGS 433/13522 |
| B1 | IMA-B / IMA-B 5 / IMA-B 5+ | **ANBIMA S3** | `IMAB`, `IMAB5`, `IMAB5MAIS` | **16/09/2003** | **Sim** | **baixo** | SGS **12466/12467/12468** (até 22/05/2023) |
| B2 | IRF-M / IRF-M 1 / IRF-M 1+ | **ANBIMA S3** | `IRFM`, `IRFM1`, `IRFM1MAIS` | **01/02/2000** / 01/12/2000 | **Sim** | **baixo** | SGS **12461** (só IRF-M, até 2023); IRF-M 1 e 1+ **não existem no SGS** |
| B2b | IMA-Geral / IMA-S | **ANBIMA S3** | `IMAGERAL`, `IMAS` | 04/12/2001 / 03/12/2001 | **Sim** | **baixo** | SGS 12469 / 12462 |
| B3 | CDI acumulado | BCB SGS | **12** (%/dia) · 4389 (% a.a.) | ≤2005 | **Sim** | baixo (chunks 10a) | Ipeadata `BM12_TJOVER12` |
| B4 | IBOV | **API B3 `indexStatisticsProxy`** | `IBOV` | 02/01/1968 | **Sim** | médio (unpivot) | Yahoo `^BVSP` (1993) · Ipeadata `GM366_IBVSP366` |
| B4b | SMLL, IDIV, IFNC, IMAT, INDX, IEEX, UTIL | **API B3** | `SMLL` `IDIV` `IFNC` `IMAT` `INDX` `IEEX` `UTIL` | 2004-2005 | **Sim** | médio | ETFs (SMAL11 2008, DIVO11 2012, FIND11 2011, MATB11 2012) |
| B4c | **ICON** | API B3 | `ICON` | 28/12/2006 (base) | **NÃO** (série de 2007) | médio | — |
| B4d | **IMOB** | API B3 | `IMOB` | 28/12/2007 (base) | **NÃO** (série de 2008) | médio | — |
| B5 | **IFIX** | API B3 | `IFIX` | 30/12/2010 (base) | **NÃO** (série de 2011) | médio | XFIX11 (2020, price return) |
| B5b | FII Tijolo × Papel, Logística, Shoppings, Lajes | **Teva Indices (GCS público)** | `3.2.2`, `3.2.1`, `3.3.1`, `3.3.3`, `3.3.2` | **02/01/2019** | **NÃO** | baixo | Construção própria: COTAHIST + CVM `inf_mensal_fii` (classif. desde 2016) — **alto** |
| B5c | IFIX-L | API B3 | **`IFIL`** | 28/12/2017 | **NÃO** | médio | — |
| C1 | S&P 500 | **Yahoo `^GSPC`** | `^GSPC` | 1927 | **Sim** | baixo | MSCI USA `984000` · ETF `IVV` (2000). ⛔ **FRED `SP500` só 10 anos** |
| C2 | MSCI ACWI / World | **MSCI endpoint público** | `892400` / `990100`, `index_variant=NETR` | **29/12/2000** | **Sim** | baixo | ETFs `ACWI` (2008) / `URTH` (2012) |
| C3 | Treasury 10y / 2y / spread | FRED CSV | `DGS10`, `DGS2`, `T10Y2Y` | 1962/1976/1976 | **Sim** | baixo | Yahoo `^TNX`, `^FVX` |
| C4 | DXY | FRED `DTWEXBGS` | `DTWEXBGS` | **02/01/2006** | **Sim** (no limite) | baixo | Yahoo `DX-Y.NYB` (1971). ⛔ `DTWEXM` morreu em 2019 |
| C5 | VIX | FRED `VIXCLS` | `VIXCLS` | 02/01/1990 | **Sim** | baixo | Yahoo `^VIX` |
| C6 | Câmbio BRL/USD | **BCB SGS 1 / 10813** (PTAX venda/compra) | 1 · 10813 | ≤2005 | **Sim** | baixo | Olinda PTAX · FRED `DEXBZUS` (1995) · Yahoo `BRL=X` (2003) |
| C7 | Fed Funds | FRED | `DFF` / `FEDFUNDS` | 1954 | **Sim** | baixo | — |
| C8 | **CDS Brasil 5y / EMBI+** | Ipeadata `JPM366_EMBI366` | `JPM366_EMBI366` | 29/04/1994 | **Parcial** — morre em **30/07/2024** | **alto** | Splice com FRED `BAMLEMRLCRPILAOAS` (só 2023+) · cupom cambial B3 via `pyield` · Damodaran (anual) |
| C9 | Agregador | Ipeadata OData4 | ver C11 | varia | varia | baixo | — |

---

# LACUNAS E SUBSTITUIÇÕES SUGERIDAS

Alexandre autorizou ajustes quando o dado não for localizável. Estas são as lacunas **reais**, com a
substituição que eu recomendo.

### L1. IFIX não existe antes de 2011 (metade da janela)
**Impacto:** alto — FII é uma das classes pedidas.
**Substituição:** (a) rodar a análise de FII em janela **2011-2026** e deixar isso explícito no output;
(b) para 2006-2010, usar **IMOB (2008+)** como proxy imperfeito de imobiliário listado — é ação, não FII;
(c) **não** reconstruir um IFIX sintético pré-2011: o mercado tinha pouquíssimos fundos e liquidez quase
nula, o resultado seria ruído. **Recomendo (a) + (b).**

### L2. Segmentação de FII (Tijolo/Papel/Logística/Shoppings) só desde 2019
**Impacto:** alto para a granularidade pedida; baixo para a decisão de alocação agregada.
**Substituição:** usar **Teva (2019-2026)** para a dispersão setorial e **IFIX (2011-2026)** para o
agregado. Opcionalmente estender para 2016 com COTAHIST + CVM. **Declarar que a segmentação cobre
apenas ~2 ciclos macro** — é pouco para inferência estatística de regime; trate como qualitativo.

### L3. ICON começa em 2007 e IMOB em 2008
**Impacto:** baixo. **Substituição:** rodar esses dois setores em janela própria (2007+/2008+) e não
forçar painel balanceado; ou substituir ICON por **IBrA/IBrX-100 + abertura de consumo via COTAHIST**.
**Recomendo:** janela própria, com nota de rodapé.

### L4. ETTJ ANBIMA histórica (curva Svensson, 20 anos) não é gratuita
**Impacto:** médio-alto — era o pedido explícito do e-mail (item ANBIMA DataFit/Feed).
**Substituição:** **inclinação construída do Tesouro Direto** (A5.4), que cobre 2004-2026 com dado
oficial. Isso atende ao objetivo ("extrair a inclinação da curva") sem comprar o Feed.
**Decisão a levar ao Alexandre:** se a casa quiser a ETTJ oficial ANBIMA com histórico, é **contratar o
ANBIMA Feed**; senão, a inclinação via Tesouro Direto é tecnicamente defensável.

### L5. Ponta longa **nominal** não existe antes de ~2010 no Tesouro Direto
**Impacto:** médio. Em 2006 a LTN mais longa vencia em 2009 e a NTN-F em 2014.
**Substituição:** usar **inclinação real (NTN-B curta × NTN-B 2045)** como variável de regime principal —
ela é completa desde 2006 — e **5 anos** (não 10) como ponta longa nominal.

### L6. Taxas indicativas ANBIMA e Curva Zero: janela rolante de ~20 dias úteis
**Impacto:** nenhum para o backfill (o Tesouro Direto cobre), **alto para o futuro**.
**Ação:** ligar **hoje** um job diário que grave `Msec_txt.txt` e `CZ-down.asp` num banco próprio.
Em 12 meses a LDC terá série proprietária de ETTJ.

### L7. SGS de swap DI × pré morto desde set/2019
**Impacto:** invalida a rota sugerida no e-mail (série 7806).
**Substituição:** Tesouro Direto + (opcional) DI futuro da B3 via `pyield`.

### L8. CDS Brasil 5y / EMBI+: sem fonte gratuita com 20 anos; EMBI+ morre em 30/07/2024
**Impacto:** médio — é proxy de risco-país, útil mas não central.
**Substituição recomendada (em ordem):** (1) **cupom cambial DDI/FRC da B3 menos UST** via `pyield` —
market-implied, diário, gratuito, histórico longo; (2) splice EMBI+ (até 07/2024) + ICE BofA LatAm OAS
(`BAMLEMRLCRPILAOAS`, 2023+) com calibração no overlap de ~200 observações; (3) Damodaran (anual) só
para checagem de nível.

### L9. Desemprego: não há série única 2006-2026
**Impacto:** baixo-médio (variável de regime útil). PNADC começa 2012; PME termina fev/2016.
**Substituição:** emendar **PME (SIDRA t/2176, 2002-03→2016-02)** com **PNADC (t/4099, 2012T1→)**,
calibrando nível na sobreposição 2012-2016.

### L10. Dívida bruta do governo geral (SGS 13762) começa em 2008
**Substituição:** usar **DLSP (SGS 4513)**, que cobre 2006, como variável fiscal; ou emendar com a série
antiga de DBGG (código **a confirmar**).

### L11. S&P 500 no FRED só tem 10 anos
**Substituição:** Yahoo `^GSPC` (ou MSCI USA `984000`). Já resolvido — **não é lacuna real**.

### L12. "ANBIMA DataFit" não existe
O produto citado no e-mail não foi encontrado. O que existe é **ANBIMA Data** (grátis) e **ANBIMA Feed**
(pago). Nenhum impacto prático — o S3 resolve os índices.

### L13. IPCA por grupos não tem série única 2006-2026
Tabelas SIDRA 1419 (2012-2019) e 7060 (2020+); a de 2006-2011 **a confirmar**. Fora do escopo mínimo.

---

# BIBLIOTECAS PYTHON RECOMENDADAS

Versões e datas lidas de `https://pypi.org/pypi/{nome}/json`. **[CONFIRMADO-SUB]**

### Tier 1 — usar
| PyPI | Versão | Último release | Estado | Cobre |
|---|---|---|---|---|
| **`python-bcb`** | 0.4.0 | **2026-06-15** | **ativa** | SGS, **Expectativas/Focus (OData)**, PTAX (`currency` + OData), `TaxaJuros`, `IFDATA`, economia regional. Import é `from bcb import sgs` |
| **`pyield`** | 0.59.0 | **2026-09-30** | **ativa** (358 releases) | **Renda fixa**: ETTJ (`tpf.curva_pre`, `ntnb.taxas_zero`), taxas indicativas ANBIMA (`tpf.taxas`, `tpf.taxas_historicas`), **DI futuro** (`di1`, `futuro.di1`), PU/duration/DV01 por título, dias úteis (`du`), calendário Copom, PTAX, VNA |
| **`brasa-marketdata`** | 0.4.0 | **2026-08-24** | ativa (nova) | **Pipeline de ingestão** B3 / ANBIMA / Tesouro / CVM → Parquet + DuckDB. Templates `anbima`, `b3`, `bcb`, `cvm` |
| **`yfinance`** | 1.7.0 | **2026-08-26** | **ativa** | `^GSPC`, `^VIX`, `^BVSP`, ETFs. ⛔ **não serve para índices setoriais B3** |
| **`bizdays`** | 1.0.19 | 2026-01-04 | ativa | Calendário de dias úteis ANBIMA/B3 — essencial para acumulação e agregação trimestral |
| **`pyettj`** | 0.4.2 | **2026-09-13** | ativa | ETTJ brasileira (B3/ANBIMA) — vale avaliar junto com `pyield` |
| `pandas-datareader` | 0.11.1 | 2026-06-24 | **ressuscitada** (0.10.0 era de 2021) | FRED, World Bank, OECD. **Sem fonte brasileira** |
| `quantstats` | 0.0.86 | 2026-09-27 | ativa | métricas de performance/regime |
| `basedosdados` | 2.0.3 | 2026-03-03 | ativa | datalake público BR (BigQuery) |

### Tier 2 — funciona, mas estagnada
| PyPI | Versão | Último release | Observação |
|---|---|---|---|
| **`sidrapy`** | 0.1.4 | **2022-09-19** | Wrapper fino do apisidra; a API está viva, então ainda funciona. Alternativa: chamar o apisidra direto |
| **`ipeadatapy`** | 0.1.9 | **2023-02-15** | PyPI estagnado, repo com commits em 2025-12. A API Ipeadata é simples — pode dispensar a lib |
| **`fredapi`** | 0.5.2 | 2024-05-05 | semi-ativa, 36 issues. O truque `fredgraph.csv` dispensa chave e lib |
| **`b3fileparser`** | 0.2.1 | 2024-05-27 | Parser de COTAHIST; layout é fixo → ainda funciona. **Pine** a versão |
| `fundamentus` | 0.3.2 | 2025-06-28 | scraping de fundamentus.com.br |
| **`mercados`** (PythonicCafe) | 0.2.0 | 2025-05-19 (push 2026-09-21) | Scrapers B3+CVM+FundosNet; **inclui valores históricos de índices** — a mais relevante para índices depois da API direta |

### Tier 3 — NÃO USAR
| PyPI | Último release | Motivo |
|---|---|---|
| `investpy` | 2022-01-24 | **morta** — `api.investing.com` → 403 Cloudflare. 244 issues |
| `brfinance` | 2022-01-24 | morta |
| `mt5b3` | 2021-02-18 | morta; exige MetaTrader5 + Windows + corretora |
| `comdinheiro` | 2023-08-30 | exige **conta paga** Comdinheiro |
| `b3parser`, `bolsa` | 2020/2021 | abandonadas |
| `dadosfera` | — | **não é dados financeiros** (ETL da empresa Dadosfera) |

### ⚠️ Armadilhas de nome **[CONFIRMADO-SUB]**
- **`pip install brasa` instala a coisa errada** — é uma ferramenta de MicroPython (ESP32). O pacote
  brasileiro é **`pip install brasa-marketdata`** (import continua `import brasa`).
- **`bcb` não existe no PyPI** — instale `python-bcb`, importe `from bcb import ...`. `rbcb` é o pacote R.
- **Não existem no PyPI (404):** `BETS`, `bcb`, `cvm`, `python-cvm`, `financialdata-net`, `rbcb`,
  `bcbdata`, `python-b3`. **`BETS` é pacote R no CRAN** (v0.4.9, 2018 — parado há 8 anos), sem equivalente Python.

### ⚠️ Gotchas que vão custar tempo
- **`python-bcb`**: timeout default **30 s** (séries longas estouram → passe `timeout=120`); exceção
  **`BCBRateLimitError` (HTTP 429)** existe, logo o SGS **tem** rate limit; `tidy=True` (novo em 0.4.0)
  devolve long-form; em apps async feche com `await bcb.http.aclose_async_client()`.
  **`sgs.search` NÃO EXISTE** (verificado no código-fonte: `bcb/sgs/` só tem `__init__.py` e
  `regional_economy.py`; funções públicas: `get`, `get_json`, `async_get`, `async_get_json`).
  **Mantenha um dicionário de códigos hard-coded.**
- **`pyield` 0.59.0 tem breaking changes**: `ipca.taxas()` → `ipca.taxa_serie()`; `ntnf.premio` removida
  (use `tpf.premios_pre`); `taxa` agora retorna `float` (`nan` em inválidos → use `math.isnan`);
  requer **`polars>=1.39` e Python ≥3.12** (pode conflitar com stack pandas/3.11). **Fixe a versão.**
- **`brasa`**: exige `brasa init` ou `BRASA_DATA_PATH`; é orientado a CLI + templates YAML; retorna pandas.
- **`yfinance`**: default de `auto_adjust` mudou para `True` → seja explícito; `YFRateLimitError` é o erro
  mais comum (workaround: sessão `curl_cffi` com `impersonate="chrome"`); `"possibly delisted"` costuma
  ser rate limit disfarçado.

---

# RISCOS DE EXTRAÇÃO

| # | Risco | Onde | Severidade | Mitigação |
|---|---|---|---|---|
| R1 | **Erro com HTTP 200** — SGS devolve corpo de erro (janela de 10 anos) e séries inexistentes devolvem **HTML com status 200** | BCB SGS | **alta** | Validar que o corpo é JSON *array* antes de parsear; checar chave `error`/`erro` |
| R2 | **Truncamento silencioso** — `$top=20000` no Olinda devolve 20.000 linhas **sem `nextLink`**; `range=max` no Yahoo trunca mensais; `fredgraph.csv` sem `cosd` trunca | Olinda, Yahoo, FRED | **alta** | Omitir `$top` ou paginar com `$skip`; usar `period1/period2`; sempre `cosd=1900-01-01`; **assert de contagem mínima** |
| R3 | **Filtros ignorados** — `$filter`/`$top`/`$orderby` ignorados em `ValoresSerie` do Ipeadata; `$apply`/`$count` ignorados no Olinda | Ipeadata, Olinda | média | Baixar inteiro e filtrar em pandas |
| R4 | **Anti-bot** — Yahoo sem UA → **429**; `dadosabertos.bcb.gov.br` sem UA → página de erro; `api.investing.com` → **403 Cloudflare**; Yahoo v7 CSV → **401** | Yahoo, BCB CKAN, Investing | **alta** | UA de browser em **todas** as requisições; nunca usar Investing/investpy |
| R5 | **`fred.stlouisfed.org` inacessível nesta sessão** (`http=000`, corpo vazio, timeout de 120 s) enquanto o agente auxiliar conseguiu acesso | FRED | **média** | Tratar FRED como fonte lenta/instável: serializar, timeout alto, retry, cache local. Alternativa: Yahoo + MSCI |
| R6 | **reCAPTCHA de uso único** — `data-api.prd.anbima.com.br/web-bff/*` exige JWT com token reCAPTCHA; reuso → **418** | ANBIMA Data (API interna) | **alta** | **Não usar.** Usar o S3 público |
| R7 | **Listagem de bucket bloqueada** — S3 da ANBIMA dá `AccessDenied` em `list-type=2`; nomes de arquivo da Teva têm **versão embutida** (`v0.27`) | ANBIMA S3, Teva | média | ANBIMA: SLUGs hard-coded + teste de disponibilidade no CI. Teva: **listar o bucket GCS e casar por regex** |
| R8 | **Janela rolante que apaga o passado** — ANBIMA `ms*.txt` e `CZ` (~20 d.u.); ICE BofA no FRED (3 anos); `SP500`/`DJIA` (10 anos) | ANBIMA, FRED | **alta** | **Arquivar diariamente desde já**; nunca tratar como fonte de backfill |
| R9 | **Páginas SPA** — B3 (`sistemaswebb3-listados`) e `data.anbima.com.br` servem shell Angular de ~2 KB | B3, ANBIMA | média | Usar as APIs (`indexStatisticsProxy`, S3), não scraping de HTML |
| R10 | **Encoding heterogêneo** — latin-1 (COTAHIST, ANBIMA `ms`/`ima_completo`/`CZ`, CVM, Tesouro) vs UTF-8 (IBGE, Olinda, XLSX do S3) | todas | média | **Declarar encoding explicitamente em cada leitor.** Em Windows nunca confiar no default do locale (cp1252) |
| R11 | **Formatos mentirosos** — `.xls` do S3 ANBIMA é XLSX; `.xls` do `CZ-down.asp` é **HTML `<table>`**; `$format=text/csv` do Olinda tem separador e decimal ambos vírgula | ANBIMA, Olinda | média | Checar magic bytes (`PK` = OOXML, `<` = HTML); preferir JSON/TXT |
| R12 | **Padrões de data traiçoeiros** — `ms{AAMMDD}` (não `ddmmaa`); PTAX Olinda em **MM-DD-YYYY**; SGS em `dd/mm/aaaa`; COTAHIST/ANBIMA `ms` em `AAAAMMDD` | todas | média | Tabela de formatos por fonte, testes unitários com datas-armadilha (01/02 vs 02/01) |
| R13 | **Separador de milhar inconsistente** — vértices do `CZ` (`6.930`), valores pt-BR da API B3 (`"38.484,84"`), CSV da ANBIMA tem milhar e o TXT não | ANBIMA, B3 | média | Normalizador único de número pt-BR |
| R14 | **Rótulos instáveis** — coluna `Índice` do S3 muda de `IMA-B` para `IMA - B`; códigos `IEEX` (não `IEE`) e `IFIL` (não `IFIXL`) | ANBIMA, B3 | média | Normalizar com `re.sub(r'\s+','',s)`; mapa explícito de códigos |
| R15 | **Quebra de taxonomia** — CVM: `Mandato` vazio desde 2025-09, `Segmento_Atuacao` mudou (Res. 175), nomes de coluna mudaram em 2021 | CVM FII | **alta** | Classificador baseado no **balanço** (`ativo_passivo`), não na taxonomia; aliases de coluna |
| R16 | **Descontinuações** — SGS 7801-7806/7816-7827 (set/2019), SGS IMA 12461-12469 (22/05/2023), IMA-C (2021), EMBI+ (30/07/2024), `DTWEXM` (2019), swaps do Ipeadata | todas | **alta** | Monitorar `SERSTATUS`/última data; alerta no pipeline quando a última observação envelhecer |
| R17 | **Atraso operacional declarado** — aviso da ANBIMA (10/03/2026) sobre atraso nas taxas indicativas por problemas de divulgação da B3 | ANBIMA | média | Arquivo ausente/atrasado é caso **normal**: retry + registro, não falha |
| R18 | **Mudança de layout sem aviso** — endpoints internos não documentados (B3 `indexStatisticsProxy`, MSCI `app2.msci.com`, `fundsProxy`) | B3, MSCI | **alta** | Testes de contrato no CI (shape + valor-canário conhecido); fallback documentado para cada um |
| R19 | **Cadastro / custo** — ANBIMA Feed é **pago** (≈R$ 686/mês a R$ 8.238/mês); Comdinheiro, MacroMicro, Cbonds exigem assinatura; FRED API exige chave (gratuita) | ANBIMA, terceiros | média | Decisão de negócio (ver L4). Nada no caminho crítico depende de fonte paga |
| R20 | **Licença / termos de uso** — Teva, fundsexplorer, fundamentus, statusinvest, investidor10 não têm licença explícita para uso comercial | terceiros | média | Teva só para validação cruzada; sites de FII como fonte **terciária**; não redistribuir |
| R21 | **Tamanho de arquivo** — COTAHIST 2026 = 91 MB; `precotaxatesourodireto.csv` = 14,6 MB (re-download diário); CVM `inf_diario_fi_2006.zip` = 31 MB | B3, Tesouro, CVM | baixa | Cache por `ETag`/`Last-Modified`, Parquet local, download incremental |
| R22 | **`www3.bcb.gov.br/sgspub` → HTTP 502** (interface de consulta/metadados do SGS fora do ar) | BCB | baixa | Catálogo de códigos versionado no repositório; CKAN do BCB para nomes (com UA) |

---

# AMOSTRAS BAIXADAS EM 2026-10-10

Arquivos reais, verificados, movidos da raiz do projeto para `data/raw/<fonte>/`.
**`data/raw/*` está no `.gitignore`** — não vão para o git (confirmado com `git status --short` limpo).

| Caminho local | URL de origem | Tamanho | Conteúdo verificado |
|---|---|---|---|
| `data/raw/anbima-ima/IMAB.xls` | `https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/arquivos/indices-historico/IMAB-HISTORICO.xls` | 393.685 B | XLSX (apesar da extensão). 5.795 linhas, 2003-09-16 → 2026-10-09. Nº-índice 723,07 → 12.656,54 |
| `data/raw/anbima-ima/IMAB5.xls` | `.../IMAB5-HISTORICO.xls` | 388.472 B | 5.795 linhas, 2003-09-16 → 2026-10-09; 775,88 → 12.107,19 |
| `data/raw/anbima-ima/IMAB5MAIS.xls` | `.../IMAB5MAIS-HISTORICO.xls` | 397.399 B | 5.795 linhas, 2003-09-16 → 2026-10-09; 715,68 → 14.075,87 |
| `data/raw/anbima-ima/IRFM.xls` | `.../IRFM-HISTORICO.xls` | 426.663 B | 6.700 linhas, **2000-02-01** → 2026-10-09; 863,15 → 24.498,77 |
| `data/raw/anbima-ima/IRFM1.xls` | `.../IRFM1-HISTORICO.xls` | 383.537 B | 6.488 linhas, 2000-12-01 → 2026-10-09; 1.000,00 → 21.220,07 |
| `data/raw/anbima-ima/IRFM1MAIS.xls` | `.../IRFM1MAIS-HISTORICO.xls` | 389.527 B | 6.488 linhas, 2000-12-01 → 2026-10-09; 1.000,00 → 26.818,31 |
| `data/raw/anbima-ima/IMAGERAL.xls` | `.../IMAGERAL-HISTORICO.xls` | 387.774 B | 6.237 linhas, 2001-12-04 → 2026-10-09; 532,62 → 10.784,85 |
| `data/raw/anbima-ima/IMAGERALEXC.xls` | `.../IMAGERALEXC-HISTORICO.xls` | 359.730 B | 5.407 linhas, 2005-03-31 → 2026-10-09; 1.000,00 → 10.635,33 |
| `data/raw/anbima-ima/IMAS.xls` | `.../IMAS-HISTORICO.xls` | 379.261 B | 6.245 linhas, 2001-12-03 → 2026-10-09; 550,49 → 9.029,69 |
| `data/raw/anbima-ima/IMAC.xls` | `.../IMAC-HISTORICO.xls` | 290.614 B | 4.850 linhas, 2001-12-03 → **2021-04-01** (descontinuado) |
| `data/raw/anbima-ima/IHFA.xls` | `.../IHFA-HISTORICO.xls` | 261.650 B | 4.766 linhas, 2007-09-28 → 2026-10-06 (7 colunas) |
| `data/raw/tesouro-direto/td.csv` | `https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv` | 14.584.922 B | 177.260 linhas, `;`/decimal vírgula/latin-1, **31/12/2004 → 09/10/2026**, 8 tipos de título |
| `data/raw/anbima-ettj/cz.xls` | `POST https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp` (`saida=xls`) | 14.566 B | ⚠️ **é HTML `<table>`**, não Excel. Parâmetros Svensson PREFIXADOS e IPCA + vértices 252→6.930 |
| `data/raw/anbima-ms/ms.txt` | `https://www.anbima.com.br/informacoes/merc-sec/arqs/ms261008.txt` | 6.740 B | 53 linhas, `@`/latin-1/CRLF, `Data Referencia = 20261008`, títulos LTN/LFT/NTN-B/NTN-C/NTN-F |

Removido: `IMAB-HISTORICO.xls` (duplicata byte-idêntica de `IMAB.xls`, mesmo MD5 `d3f0cc0b…`) e os
rascunhos de HTML/JSON/binário da raiz (`cz.html`, `fe.html`, `ima.html`, `imash.html`, `m.html`,
`ms_page.html`, `out.bin`, `r.json`, `grep.exe.stackdump`, `.playwright-mcp/`).

---

# PRÓXIMOS PASSOS SUGERIDOS PARA QUEM VAI CODAR

1. **Hoje (caminho crítico para 14/10):** extratores de esforço **baixo** que já entregam a base —
   ANBIMA S3 (10 índices IMA), SGS (IPCA/Selic/CDI/IBC-Br/PTAX), SIDRA (PIB trimestral + IPCA),
   Tesouro Direto (1 CSV), API B3 (índices com 2006 completo), FRED/Yahoo/MSCI (internacional).
2. **Hoje também:** ligar o job diário de arquivamento de `Msec_txt.txt` e `CZ-down.asp` (L6) — cada dia
   que passa sem isso é um dia perdido de série proprietária.
3. **Em seguida:** inclinação da curva interpolada do Tesouro Direto (A5.4), Teva (FII por segmento),
   splice do risco-país (L8).
4. **Testes de contrato no CI** para os 3 endpoints não documentados (B3 `indexStatisticsProxy`,
   MSCI `app2.msci.com`, ANBIMA S3): shape + valor-canário conhecido (ex.: IBOV 01/02/2006 = 38.484,84;
   IMA-B 16/09/2003 = 723,070317; MSCI ACWI NETR 31/01/2006 = 121,3858…).
