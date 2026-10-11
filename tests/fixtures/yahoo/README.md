# `tests/fixtures/yahoo/` — procedência

Respostas **reais** do endpoint `chart/v8` do Yahoo Finance, gravadas em **2026-10-10** por script
de sessão (a flag `--record` ainda não existe — ver `tests/fixtures/README.md`). Nenhuma foi
editada: onde um teste precisa de um campo diferente, ele altera o JSON **em memória** e diz por
quê. Usadas por `tests/unit/test_extract_yahoo.py` (F-007, SPEC RF-016/RF-017).

Cabeçalhos de todas as chamadas: `User-Agent` de browser (`USER_AGENT_BROWSER` de
`apps/pipeline/common/http.py`), `Accept: application/json, text/csv, text/plain, */*`,
`Accept-Language: pt-BR,pt;q=0.9,en;q=0.8`. **Exceção:** `^GSPC__erro_429_sem-ua.txt` foi
gravada deliberadamente **sem nenhum cabeçalho**.

| Arquivo | URL / parâmetros | HTTP | Bytes | O que prova |
|---|---|---|---|---|
| `^GSPC__2026-10-10.json` | `.../chart/%5EGSPC?period1=1136073600&period2=1167609600&interval=1d` (2006-01-01 → 2007-01-01) | 200 | 28.826 | parse completo: 251 pregões de 2006, `adjclose == close`, `meta.gmtoffset`, canário 31/01/2006 = 1280,079956, 62 pontos no 1T2006 |
| `^GSPC__erro_404_delisted.json` | `.../chart/ZZZZNOPE.XX?period1=…&period2=…&interval=1d` | **404** | 108 | corpo de erro real: `{"chart":{"result":null,"error":{"code":"Not Found","description":"No data found, symbol may be delisted"}}}` — o parser recusa em vez de gravar lixo (CA-124) |
| `^GSPC__erro_429_sem-ua.txt` | mesma URL do `^GSPC`, **sem `User-Agent`** | **429** | 23 | CA-045: corpo literal `Edge: Too Many Requests`, texto puro (não JSON) |
| `^GSPC__range-max-1mo.json` | `.../chart/%5EGSPC?range=max&interval=1mo` | 200 | 19.890 | CA-045 / R2: truncamento silencioso — **169** pontos contra 490 na mesma janela com `period1`/`period2`, e a fonte **rebaixou** `interval=1mo` para `dataGranularity="3mo"` sem avisar |
| `SMLL.SA__armadilha-1-ponto.json` | `.../chart/SMLL.SA?period1=1136073600&period2=1791676800&interval=1d` (2006 → 2026) | 200 | 1.232 | a armadilha registrada no catálogo (`YAHOO_SETORIAIS_B3_SA`, `status: descartada`): HTTP 200, `chart.error` nulo, `firstTradeDate` nulo e **1** ponto para 20 anos de janela pedida |
| `IVV__adjclose-difere.json` | `.../chart/IVV?period1=1136073600&period2=1167609600&interval=1d` | 200 | 28.080 | Anti-SPEC §10.2.12: num ETF com provento `close` (126,83 em 03/01/2006) e `adjclose` (86,78) divergem — o parser levanta em vez de gravar price return onde se esperaria retorno total |

## Como regravar

```python
import calendar, requests
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Accept": "application/json, text/csv, text/plain, */*",
      "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
ep = lambda d: calendar.timegm(d.timetuple())
r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC",
                 params={"period1": ep(date(2006, 1, 1)), "period2": ep(date(2007, 1, 1)),
                         "interval": "1d"}, headers=UA, timeout=60)
open("tests/fixtures/yahoo/^GSPC__2026-10-10.json", "wb").write(r.content)
```

A resposta **não é byte-estável** entre chamadas (a fonte alterna a ordem das chaves de
`meta.currentTradingPeriod`), então um `sha256` novo após regravar não significa que a série
mudou — compare `timestamp` e `indicators.quote[0].close`. Se um **valor** mudar, registre em
`docs/plans/DECISIONS_LOG.md` antes de ajustar teste nenhum.
