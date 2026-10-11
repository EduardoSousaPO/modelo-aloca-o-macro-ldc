# `tests/fixtures/processed/` — recortes reais de `data/processed/`

Único diretório de fixture que guarda **Parquet**, e a única exceção à regra "nenhum `.parquet` no
git" (`.gitignore`, linha `!tests/fixtures/**/*.parquet`). Ele existe por um motivo só: fazer as
varreduras de camada rodarem no CI.

## Por que existe

`tests/unit/test_processed_layer_conventions.py` e `tests/unit/test_contract_sgs_sidra.py` são a
**única** trava regressível de D-a (`date` em fim de período), D-b (`vintage` = data do
`collected_at` do manifesto), PK `(series_id, date, vintage)` única e da reconciliação SGS × SIDRA
com `max|dif| == 0`. Até 2026-10-11 as duas liam só `data/processed/` e **pulavam** sem Parquet.
`data/` não está no git e o job `n1-basic` faz `checkout` + `pip install` + `pytest`, sem passo que
reconstrua a camada — então num `actions/checkout` limpo o QA da Onda 1 mediu
`9 skipped` (`docs/plans/qa/ONDA-1-QA-A.md §4.6`, P1-4): **a evidência central da consolidação não
era verificada por nenhum CI**, e D-a/D-b podiam regredir verde.

Com estes recortes versionados, as duas varreduras rodam **sempre** sobre a fixture e, **além**
disso, sobre `data/processed/` quando ela existe (parametrização por "acervo"). Recorte ausente é
**falha**, não skip.

## O que está aqui

Recorte por série: **2006-01-01 .. 2006-06-30** (a janela que o PRD §7 exige cobrir — é onde um
erro de convenção de data aparece) **+ os últimos 3 meses** (a ponta viva, onde aparece período
parcial e `vintage` do dia errado). Nada é recalculado, reescalado ou preenchido: cada linha é,
valor a valor, o que o extrator gravou — as 8 colunas de `ProcessedSeriesSchema`, os mesmos
dtypes, o mesmo `vintage`.

| Arquivo | Linhas na origem | Linhas no recorte | Janela do recorte | `freq` | `vintage` | Bytes | `sha256` (12) |
|---|---|---|---|---|---|---|---|
| `sgs/BCB_SGS_433.parquet` | 273 | 9 | 2006-01-31 .. 2026-09-30 | M | 2026-10-10 | 5.059 | `861a03dc8eff` |
| `sidra/SIDRA_1737_V63.parquet` | 562 | 9 | 2006-01-31 .. 2026-09-30 | M | 2026-10-11 | 5.090 | `fa38380b1ba4` |
| `sgs/BCB_SGS_22109.parquet` | 90 | 4 | 2006-03-31 .. 2026-06-30 | Q | 2026-10-11 | 5.002 | `68a17d66e37b` |
| `sidra/SIDRA_1621_V584_90707.parquet` | 122 | 4 | 2006-03-31 .. 2026-06-30 | Q | 2026-10-11 | 5.058 | `d7451a08afe1` |
| `anbima-ima/ANBIMA_IMAB.parquet` | 5.795 | 189 | 2006-01-02 .. 2026-10-09 | D | 2026-10-10 | 8.302 | `a85c436f2c78` |
| `b3/B3_IBOV.parquet` | 5.147 | 188 | 2006-01-02 .. 2026-10-09 | D | 2026-10-10 | 7.908 | `f18d58749ed2` |
| `yahoo/YAHOO_GSPC.parquet` | 5.729 | 190 | 2006-01-03 .. 2026-10-09 | D | 2026-10-11 | 7.856 | `0197d3fd901c` |
| `tesouro-direto/td_painel.parquet` | 886.300 | 1.545 | 2006-01-02 .. 2026-10-09 | D | 2026-10-11 | 17.869 | `d28345fe60e0` |

**Por que estas 7 séries + o painel.** São 5 fontes independentes e os 2 pares de reconciliação:
`BCB_SGS_433 × SIDRA_1737_V63` (IPCA mensal) e `BCB_SGS_22109 × SIDRA_1621_V584_90707` (PIB
trimestral) — sem os dois pares, `test_contract_sgs_sidra.py` não tem o que comparar. `ANBIMA_IMAB`,
`B3_IBOV` e `YAHOO_GSPC` dão três convenções diárias diferentes (XLSX da S3, API interna da B3 em
pt-BR, chart do Yahoo) e três `vintage` distintos. `td_painel` é o único arquivo com `series_id`
composto, e o contrato dele é o mesmo `ProcessedSeriesSchema`.

**O recorte do painel é de datas, não da janela.** Os títulos do Tesouro vencem e nascem, então
nenhuma data única tem as 750 séries: o recorte pega o **primeiro dia útil de cada mês** de
2006-01..2006-06 mais os **2 últimos pregões**, e com isso traz **455** `series_id` em 1.545
linhas. O piso do teste acompanha o acervo (`> 400` na fixture, `> 700` em `data/processed/`).

## Origem e data

`data/processed/`, exatamente como ficou depois da rodada de extração de **2026-10-10/11** da
Onda 1 (commit `e215dbf`, o mesmo estado que o QA auditou). Toda procedência de **fonte** fica nos
`.meta.json` de `data/raw/` e nos READMEs por fonte em `tests/fixtures/<fonte>/`; aqui a
procedência é a camada processada, não a fonte viva.

## Como regenerar

Quando uma convenção mudar de propósito (um novo D-x no `DECISIONS_LOG.md`), regenere os recortes
**da camada** — nunca edite o Parquet para o teste passar. O script abaixo **só lê**
`data/processed/`:

```python
# scripts de sessão não ficam no repo (tests/fixtures/README.md); este é o texto exato
from pathlib import Path
import pandas as pd

ORIGEM, DESTINO = Path("data/processed"), Path("tests/fixtures/processed")
SERIES = (
    "sgs/BCB_SGS_433", "sidra/SIDRA_1737_V63",
    "sgs/BCB_SGS_22109", "sidra/SIDRA_1621_V584_90707",
    "anbima-ima/ANBIMA_IMAB", "b3/B3_IBOV", "yahoo/YAHOO_GSPC",
)
INICIO, FIM, MESES_DE_PONTA = pd.Timestamp("2006-01-01"), pd.Timestamp("2006-06-30"), 3

for rel in SERIES:
    q = pd.read_parquet(ORIGEM / f"{rel}.parquet")
    ponta = q["date"].max() - pd.DateOffset(months=MESES_DE_PONTA)
    corte = ((q["date"] >= INICIO) & (q["date"] <= FIM)) | (q["date"] > ponta)
    alvo = DESTINO / f"{rel}.parquet"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    q.loc[corte].reset_index(drop=True).to_parquet(alvo, index=False)

# painel do Tesouro: recorte de DATAS (1º dia útil de cada mês da janela + 2 últimos pregões),
# para preservar muitos `series_id` sem carregar 886 mil linhas
painel = pd.read_parquet(ORIGEM / "tesouro-direto/td_painel.parquet")
datas = pd.Series(sorted(painel["date"].unique()))
primeiro_do_mes = datas.groupby(datas.dt.to_period("M")).min()
na_janela = primeiro_do_mes[(primeiro_do_mes >= INICIO) & (primeiro_do_mes <= FIM)]
alvo_datas = set(na_janela) | set(datas.iloc[-2:])
recorte = painel[painel["date"].isin(alvo_datas)].reset_index(drop=True)
(DESTINO / "tesouro-direto").mkdir(parents=True, exist_ok=True)
recorte.to_parquet(DESTINO / "tesouro-direto/td_painel.parquet", index=False)
```

Depois de regenerar, atualize a tabela acima (linhas, janela, bytes, `sha256`) e rode:

```bash
uv run pytest tests/unit/test_processed_layer_conventions.py tests/unit/test_contract_sgs_sidra.py -q
LDC_IGNORAR_DATA=1 uv run pytest tests/unit/test_processed_layer_conventions.py tests/unit/test_contract_sgs_sidra.py -q
```

A segunda linha é o que o CI vê: `LDC_IGNORAR_DATA=1` ignora `data/processed/` e deixa só os
recortes. **Tem de passar sem nenhum `skipped`.**

## Limites

- **≤ 30 KB por arquivo** (o maior hoje tem 17,9 KB). Fixture é amostra, não espelho da camada.
- **Nunca sintético.** Se um recorte precisar de linha que a camada não tem, o nome diz
  (`__sintetico`) e a razão vai no `DECISIONS_LOG.md` — mas aqui isso nunca deveria ser preciso:
  a pergunta destes testes é "o que os extratores gravaram segue a convenção?".
- **Não é cache.** Quem quer a série inteira roda os extratores; `data/` continua sendo a camada
  de verdade e continua fora do git.
