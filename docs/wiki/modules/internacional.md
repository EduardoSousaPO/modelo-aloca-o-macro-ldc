# Módulo `internacional` — Yahoo, MSCI, FRED (bloco C)

> Verdade: `apps/pipeline/extract/{yahoo,msci}.py` + `apps/pipeline/transform/cambio.py` +
> `research/fontes-de-dados.md §C10-C11`. **Estado (2026-10-11): Yahoo e MSCI implementados**
> (F-007, aguardando QA da Onda 1); **FRED bloqueado nesta máquina** (F-011). Responde ao item **C1**
> do e-mail, com as séries na moeda original e as versões em BRL como séries **derivadas separadas**.

| `series_id` | linhas | janela | nulos | canário (2006-01-31) |
|---|---|---|---|---|
| `YAHOO_GSPC` | 5.729 | 2004-01-02 → 2026-10-09 | 0,00% | **1280,079956** |
| `YAHOO_TNX` · `VIX` · `DXY` | 5.729 · 5.941 · 6.952 | idem | 0,09% · 3,53% · **17,41%** | 4,527 · 12,95 · 88,96 |
| `MSCI_ACWI_NETR` | 6.726 | **2000-12-29** → 2026-10-09 | 0,00% | **121,3858** |
| `MSCI_WORLD_NETR` · `USA` · `EM` | 6.726 cada | idem | 0,00% | 2.895,0792 · 2.802,4606 · 266,2901 |
| `SP500_BRL` · `ACWI_BRL` (derivadas) | 5.572 · 5.719 | 2004-01-02 → 2026-10-09 | 0,00% | 157 · 1.007 dias sem PTAX |

Todas com as duas pontas do 1T2006 (62-78 obs), monotônicas, sem data repetida. A janela começa em
**2004-01-01** de propósito: folga de 2 anos para a variação de 12 meses e mesma borda da PTAX de
F-003. MSCI `NETR` começa em 2000-12-29 com `level_eod = 100,0` no ACWI e no EM (base); `STRD`
começaria em 1997 e **não** é a usada. Canários conferidos contra **outra superfície** da mesma fonte
(diário × `interval=1mo`; diário × `END_OF_MONTH`), não contra o mesmo payload.

## As decisões que mudam número

- **A série fica na moeda original (USD); BRL é série derivada separada** (`fonte=DERIVADO`), nunca
  coluna nem substituição — §10.4.28 vale para moeda como para frequência. Catálogo: 132 → **134** (D-d).
- **`is_total_return` mora no catálogo**, porque `ProcessedSeriesSchema` não tem essa flag.
  `SP500_BRL` é **price return** declarado; o comparável de total return do IMA-B/IFIX é `ACWI_BRL`
  (NETR) e, para os EUA, `MSCI_USA_NETR`. A conversão **levanta** se a flag vier `None`.
- **Conversão = `nivel_usd × PTAX(mesmo dia)`, `inner join` exato** (PTAX venda `BCB_SGS_1`, F-003):
  sem `ffill`, sem interpolação, sem `0`. Dia sem PTAX **sai** da série e a contagem vai no relatório
  — 157 no `SP500_BRL` (feriado brasileiro com pregão em NY) e 1.007 no `ACWI_BRL` (os mesmos **mais**
  os ~785 dias antes do início da PTAX). Mora em `transform/cambio.py` (D-g); a derivada **herda**
  `collected_at`/`vintage` da série em USD.
- **`^FVX`, `^IRX`, `MSCI_BRAZIL` e `GOLD_BRL` ficam fora:** `TICKERS` só tem séries `status=ok` e
  acrescentar ticker é F-011. `MSCI_BRAZIL` (`705000`) devolve lista vazia (`a_confirmar`);
  `GOLD_BRL` segue `BLOQUEADO — FONTE INDISPONÍVEL` (G-03).

## Armadilhas

- **Yahoo sem UA → 429** (retry com backoff). **`range=max` trunca e rebaixa** (169 pontos contra 490
  com `period1`/`period2`) e a fonte respondeu `dataGranularity="3mo"` **ignorando o `interval=1mo`**
  → nenhuma função emite `range`, e o parser recusa granularidade ≠ `1d`. **200 com 1 ponto**
  (`SMLL.SA`) é pego pela contagem de não nulos.
- **`timestamp` não é data:** a data de pregão é `timestamp + meta.gmtoffset`. **`adjclose` ≠ `close`
  = provento:** idênticos nos índices, 126,83 contra 86,78 no `IVV` real de 03/01/2006 → **levanta**.
- **A resposta do Yahoo não é byte-estável** (ordem das chaves de `meta.currentTradingPeriod` alterna
  com `close` idêntico) → `_arquivar_retrato` compara a série `(date, value)` e **mantém o retrato
  original**; valor revisado continua levantando `ConteudoDivergente`.
- **MSCI erra com 200 e chave que a infra não conhece** (`error_code`, não `error`) → guarda própria;
  **código inexistente → 200 com `INDEX_LEVELS: []`**; `start_date` < 1997-01-01 é recusado com 200 →
  validado **antes** de ir à rede. **`^TNX` veio em % a.a. direto** (5,244 em 09/10/2026) — o erro
  clássico do ticker é o ×10; reconferir em F-011 contra `DGS10` se o FRED voltar.
- **R5 · FRED bloqueado na camada de aplicação** (TLS completa, HTTP dá ReadTimeout e
  `ConnectionReset`, 3/3): F-011 começa por teste de conectividade e falha explícita, nunca fallback
  silencioso (S-09; `DFF`/`FEDFUNDS` sem substituto equivalente).

**Features:** **F-007** (implementado) · **F-011** · **F-017** · **F-026** · **F-030**.
