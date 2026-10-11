# `tests/fixtures/b3/` — respostas reais da API de índices da B3

Procedência das fixtures de **F-006** (`apps/pipeline/extract/b3_indices.py`). Convenção e regras
gerais em [`../README.md`](../README.md). **Toda fixture aqui é resposta real**, gravada numa
chamada única em **2026-10-10, entre 20:49 e 20:54 (UTC-3)**, por script de sessão (não versionado).
Nenhuma foi editada depois de gravada.

## Endpoint

```
GET https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{b64}
b64 = base64(json({"language":"pt-br","index":"<COD>","year":"<AAAA>"}, separators=(",",":")))
Headers: User-Agent de browser + Referer: https://sistemaswebb3-listados.b3.com.br/
```

A resposta é `{"min":{...},"max":{...},"results":[31 itens]}`; cada item tem `day` (1..31) e
`rateValue1..rateValue12` (jan..dez), em **string pt-BR**. É matriz dia × mês — precisa de unpivot.

## Fixtures de caminho feliz

| Arquivo | Payload (`index`/`year`) | Bytes | O que prova |
|---|---|---|---|
| `ibov_2006__2026-10-10.json` | `IBOV` / `2006` | 9 494 | **CA-034/CA-035** — 246 pontos não nulos; `day=1, rateValue2 = "38.484,84"` → 2006-02-01 = `38484.84` (valor-canário) |
| `icon_2006__2026-10-10.json` | `ICON` / `2006` | 7 578 | **CA-036** — ano com **um ponto só** (28/12/2006 = `1.000,00`): matriz cheia de `null` e nenhuma série |
| `icon_2007__2026-10-10.json` | `ICON` / `2007` | 9 122 | **CA-036** — 245 pontos: a série de ICON começa em 2007, não em 2006 |
| `imob_2007__2026-10-10.json` | `IMOB` / `2007` | 7 578 | **CA-036** — ponto-base 28/12/2007 = `1.000,00` |
| `ifix_2011__2026-10-10.json` | `IFIX` / `2011` | 9 204 | **CA-038** — 249 pontos; primeiro ano efetivo do IFIX |
| `ifix_2010__2026-10-10.json` | `IFIX` / `2010` | 7 578 | **CA-038** — ponto-base 30/12/2010 = `1.000,00` e nada mais |

## Fixtures de borda e de erro (obrigatórias — CA-124)

| Arquivo | Como foi provocada | Bytes | O que prova |
|---|---|---|---|
| `ifix_2009__sem_serie__2026-10-10.json` | `IFIX` / `2009` | 38 | **Ausência legítima**: `{"min":null,"max":null,"results":null}` com HTTP 200. O parser devolve "ano sem série" e **não** levanta — e também não inventa ponto (Anti-SPEC §10.1.1) |
| `ibov__erro_corpo_vazio.json` | payload que não é base64 válido (`naoEhBase64Valido!!`) | **0** | **HTTP 200 com corpo vazio** → `RespostaDeErroComStatus200`. É o modo de falha dominante da B3 (R1): sem essa guarda, o extrator gravaria série vazia como sucesso |
| `ibov__erro_html.txt` | `GET /indexPage/day/IBOV?language=pt-br` (a página, não a API) | 2 700 | **Anti-SPEC §10.4.27** — a página da B3 é shell Angular. HTTP 200 + `text/html` → `RespostaDeErroComStatus200`; scrapear isso é proibido |
| `xxxx_2006__erro_indice_inexistente.json` | `XXXX` / `2006` (código que não existe) | 38 | **Pegadinha medida:** código errado devolve o **mesmo** corpo de "ano sem série". O corpo não distingue; quem distingue é o `data_inicio` do catálogo (guarda de contagem mínima) e a validação do código contra o catálogo antes da requisição |

## Como regravar

```bash
# feliz (qualquer índice/ano) — o próprio extrator já arquiva o bruto idêntico em data/raw/b3/
uv run python -m apps.pipeline.extract.b3_indices --indices IBOV --anos 2006
cp data/raw/b3/IBOV/2006.json tests/fixtures/b3/ibov_2006__<hoje>.json

# erro: um GET avulso com o payload da tabela acima, gravando `response.content` cru
```

Se a forma da resposta mudar, **grave de novo e registre em `docs/plans/DECISIONS_LOG.md`** —
nunca edite a fixture para o teste voltar a passar.
