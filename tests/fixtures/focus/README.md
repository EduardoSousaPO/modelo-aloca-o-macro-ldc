# `tests/fixtures/focus/` — respostas reais do BCB Focus (Olinda / OData v4)

Procedência de cada fixture de F-010. **Todas gravadas em 2026-10-11**, em requisição real a
`https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/`, com o
`User-Agent` de browser de `apps/pipeline/common/http.py` e **sem recorte manual** — o que está no
arquivo é o corpo byte a byte que a fonte devolveu, inclusive o status HTTP. Nenhuma foi editada.

Convenção de nome: `tests/fixtures/README.md`. Aqui `<serie>` é o **nome do EntitySet** (é o
`identificador` do catálogo), `<data>` é `2026-10-11` (a data da coleta, = `collected_at`), e o
sufixo descreve a borda que a fixture prova.

> **Como regravar:** monte a URL com espaço em **`%20`** (`quote(valor, safe="$,'/:()")`) — com
> `+` (o default de `urlencode`/`params=` do `requests`) o backend responde **HTTP 400**. É a
> pegadinha que `ExpectativasMercadoAnuais__erro_orderby_mais.json` registra.

Prefixo comum de toda URL abaixo:

```
BASE = https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata
```

| Fixture | HTTP | Linhas | Requisição (`$format=json` sempre) | O que prova |
|---|---|---|---|---|
| `ExpectativasMercadoAnuais__2026-10-11__basecalculo-0-e-1.json` | 200 | 20 | `BASE/ExpectativasMercadoAnuais?$filter=Indicador eq 'IPCA' and Data ge '2026-10-01' and Data le '2026-10-02'` — **sem** filtro de `baseCalculo` | **CA-017**: `baseCalculo` 0 e 1 coexistem na mesma `Data`+`DataReferencia` (2026-10-01, IPCA/2026: `bc=0` mediana **5,0** com 144 respondentes; `bc=1` mediana **5,1** com 61). O parser tem de devolver **uma** linha |
| `ExpectativasMercadoAnuais__2026-10-11__2006-01.json` | 200 | 110 | `…/ExpectativasMercadoAnuais?$filter=Indicador eq 'IPCA' and Data ge '2006-01-01' and Data le '2006-01-31' and baseCalculo eq 0&$orderby=Data asc,DataReferencia asc` | cobertura de **1T2006** e horizonte negativo real: em 2006-01-02 há `DataReferencia` **2005** (H−1, o IPCA do ano encerrado e ainda não divulgado), **2006** (H0, mediana **4,50**) e **2007** (H1). `numeroRespondentes` vem `null` no histórico antigo |
| `ExpectativasMercadoAnuais__2026-10-11__quatro-indicadores.json` | 200 | 40 | `…/ExpectativasMercadoAnuais?$filter=(Indicador eq 'IPCA' or Indicador eq 'Selic' or Indicador eq 'PIB Total' or Indicador eq 'Câmbio') and Data ge '2026-10-01' and Data le '2026-10-02' and baseCalculo eq 0&$orderby=Data asc,DataReferencia asc` | os 4 indicadores do plano anual juntos, com `DataReferencia` 2026..2030 — é a fixture do teste ponta a ponta de `extrair_serie` (4 requisições, 8 `series_id`, 3 unidades: `%`, `%a.a.`, `BRL`) |
| `ExpectativasMercadoAnuais__2026-10-11__pagina-1-de-3.json` | 200 | **40** | `…/ExpectativasMercadoAnuais?$filter=Indicador eq 'Selic' and Data ge '2026-09-01' and Data le '2026-10-02' and baseCalculo eq 0&$orderby=Data asc,DataReferencia asc&$top=40&$skip=0` | **CA-018**: página **cheia** (40 = `$top`) — não é a última, e não há `@odata.nextLink` para dizer isso |
| `ExpectativasMercadoAnuais__2026-10-11__pagina-2-de-3.json` | 200 | **40** | idem, `$skip=40` | 2ª página cheia: a paginação por `$skip` continua |
| `ExpectativasMercadoAnuais__2026-10-11__pagina-3-de-3.json` | 200 | **35** | idem, `$skip=80` | página **curta** — o único sinal de fim que esta fonte dá. 40+40+35 = 115 |
| `ExpectativaMercadoMensais__2026-10-11.json` | 200 | 50 | `…/ExpectativaMercadoMensais?$filter=Indicador eq 'IPCA' and Data ge '2026-10-01' and Data le '2026-10-02' and baseCalculo eq 0&$orderby=Data asc,DataReferencia asc` | **CA-019** no EntitySet mensal (nome em singular/plural trocado vs. EntityType) e `DataReferencia` no formato **`MM/AAAA`** (`09/2028`) |
| `ExpectativasMercadoTrimestrais__2026-10-11.json` | 200 | 26 | `…/ExpectativasMercadoTrimestrais?$filter=Indicador eq 'PIB Total' and ((Data ge '2026-10-01' and Data le '2026-10-02') or (Data ge '2006-01-02' and Data le '2006-01-03')) and baseCalculo eq 0&$orderby=Data asc,DataReferencia asc` | `DataReferencia` trimestral é **`T/AAAA` sem zero à esquerda** (`3/2026`, `4/2005`) e o horizonte **HM1** é sistemático: em 2026-10-02 o trimestre mais antigo ofertado é `3/2026`, já encerrado e não divulgado |
| `ExpectativasMercadoSelic__2026-10-11.json` | 200 | 50 | `…/ExpectativasMercadoSelic?$filter=((Data ge '2026-10-01' and Data le '2026-10-02') or (Data ge '2006-01-02' and Data le '2006-01-03')) and baseCalculo eq 0&$orderby=Data asc,Reuniao asc` | campo **`Reuniao`** no formato `R<n>/<ano>` (e não `DataReferencia`); canário de 1T2006: `R1/2007` em 2006-01-02 = **15,0** |
| `ExpectativasMercadoInflacao12Meses__2026-10-11.json` | 200 | 8 | `…/ExpectativasMercadoInflacao12Meses?$filter=Indicador eq 'IPCA' and ((Data ge '2026-10-01' and Data le '2026-10-02') or (Data ge '2006-01-02' and Data le '2006-01-03')) and baseCalculo eq 0&$orderby=Data asc,Suavizada asc` | campo **`Suavizada`** (`S`/`N`) e as duas séries que ele gera. 2026-10-02: `S` = **4,5905**, `N` = **4,8741** |
| `ExpectativasMercadoAnuais__vazio.json` | **200** | **0** | `…/ExpectativasMercadoAnuais?$filter=Indicador eq 'IndicadorInexistente'` | indicador inexistente devolve **HTTP 200 com `{"value":[]}`** — vazio silencioso, não erro. Quem recusa é a contagem mínima (R2) |
| `ExpectativasMercadoAnuais__erro.json` | **400** | — | `BASE/EntitySetQueNaoExiste?$top=1` | corpo de erro do Olinda: JSON **embrulhado em comentário** (`/*{ "codigo": 400, "mensagem": … }*/`), **sem** `Content-Type`. Não é JSON válido nem HTML — é o caso que `validar_corpo_odata` tem de recusar com mensagem própria |
| `ExpectativasMercadoAnuais__erro_orderby_mais.json` | **400** | — | `…/ExpectativasMercadoAnuais?%24top=1&%24orderby=Data+asc` (query via `urlencode`, espaço como `+`) | achado **novo** de 2026-10-11, ausente da pesquisa: `"The system query option '$orderby' has the not-allowed value 'Data+asc'."` O espaço **tem** de ser `%20` |

## O que estas fixtures deliberadamente **não** cobrem

- **O corte em exatamente 20.000 linhas** (`$top=20000` sem `@odata.nextLink`). O corpo tem ~1,5 MB
  e a regra do diretório é ≤ 200 KB. A guarda é pura (`recusar_truncamento_silencioso`) e está
  testada direto, com `n = 20000`; a medição ao vivo que a justifica (IPCA anual `baseCalculo=0`
  tem **32.582** linhas; `$top=20000` devolve **20.000** e nenhum `nextLink`; 4 páginas de
  `$top=10000` reproduzem as 32.582) está em `docs/wiki/modules/focus.md` e repetida sob
  `@pytest.mark.network` em `tests/unit/test_extract_bcb_focus.py`.
- **`$count=true` e `$apply=groupby(...)`** — são ignorados sem erro, e o extrator nunca os manda;
  o teste que importa é o que afirma que a URL montada não os contém.
- **Os 8 EntitySets fora de escopo** (Top5, 24 meses, `DatasReferencia`, `Instituicoes`). A tabela
  de normalização de campo (`CAMPOS_CANONICOS`) cobre a capitalização minúscula deles por desenho,
  e isso é testado com entrada em memória — não com fixture, porque não é dado que o pipeline usa.
