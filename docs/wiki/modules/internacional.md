# Módulo `internacional` — Yahoo, MSCI, FRED (bloco C)

> Síntese — fonte de verdade: `docs/research/fontes-de-dados.md §C10-C11`. **Status: nenhum extrator implementado** (2026-10-10). **O FRED está bloqueado nesta máquina.**

## Propósito

Montar o lado internacional do dataset — a resposta ao item **C1** do e-mail ("tamanho da alocação
internacional") — convertendo tudo para **BRL** pela PTAX, para que entre no mesmo arcabouço de regimes
dos ativos domésticos. Arquivos previstos: `extract/yahoo.py`, `msci.py`, `fred.py`.

## Séries / RFs cobertos

| Série | Identificador | RF |
|---|---|---|
| S&P 500 → `SP500_BRL` | Yahoo **`^GSPC`** (1927→) ou MSCI USA `984000` | RF-016 |
| MSCI ACWI / World, **NETR** | MSCI `892400` / `990100` (29/12/2000→) | RF-016 |
| UST 10y/5y, VIX, DXY | Yahoo `^TNX`, `^FVX`, `^VIX`, `DX-Y.NYB` (plano B do FRED) | RF-017 |
| Treasury 10y/2y/spread, Fed Funds | FRED `DGS10`, `DGS2`, `T10Y2Y`, `DFF` — **bloqueado** | RF-017 |
| Risco-país (fase 2) | Ipeadata `JPM366_EMBI366` — **morre em 30/07/2024** | — |

**Valor-canário:** MSCI ACWI NETR 31/01/2006 = **121,3858**.

## Fonte primária e fallback

- **Primária:** `query1.finance.yahoo.com/v8/finance/chart/{t}` (UA de browser obrigatório) · endpoint JSON público da MSCI (`app2.msci.com`) · PTAX pelo **SGS 1/10813**.
- **Fallback:** o FRED **era** a primária de C3-C5/C7 e foi substituído (**S-09** no `DECISIONS_LOG`): `DGS10`→`^TNX`, `DGS2`/`DGS5`→`^FVX`, `VIXCLS`→`^VIX`, `DTWEXBGS`→`DX-Y.NYB`, `DEXBZUS`→PTAX, `T10Y2Y`→proxy 10y−5y. **`DFF`/`FEDFUNDS` não tem substituto gratuito equivalente** → lacuna declarada.

## Armadilhas conhecidas (pesquisa)

- **R5 · FRED bloqueado nesta máquina:** TCP:443 conecta em 0,04 s e o TLS completa, mas a resposta HTTP dá ReadTimeout e, no retry, `ConnectionReset(10054)` — **3/3 tentativas**, em `fred.stlouisfed.org` e `api.stlouisfed.org`. É bloqueio na **camada de aplicação**, não lentidão. **F-011 começa por um teste de conectividade** e falha explícita (`BLOQUEADO — FONTE INDISPONÍVEL`), nunca fallback silencioso.
- **R2 · truncamento:** `SP500` e `DJIA` no FRED são **janela rolante de 10 anos** (não cobrem 2006 — S-10); `fredgraph.csv` sem `cosd` trunca; `range=max` do Yahoo trunca mensais → usar `period1/period2`.
- **R4 · anti-bot:** Yahoo sem UA → **429**; o v7 CSV → 401. `yfinance` disfarça rate limit como "possibly delisted" e mudou o default de `auto_adjust` para `True`.
- **Total return × price return:** MSCI **NETR** é total return, `^GSPC` é price return. Nunca comparar sem `is_total_return` (Anti-SPEC §10) — e `T10Y2Y` como 10y−5y **muda o nível do spread**, tem de ser declarado.
- **R18 · endpoint não documentado** (`app2.msci.com`) → teste de contrato com valor-canário no CI. Ipeadata **ignora `$filter`/`$top`** em `ValoresSerie` → baixar inteiro e filtrar em pandas (R3).

**Features do TODO:** **F-001** · **F-007** (Yahoo + MSCI) · **F-011** (FRED + conectividade, `should`) ·
**F-026** (dimensionamento internacional, C) · **F-030** (canário) · **F-036** (risco-país, fase 2).
