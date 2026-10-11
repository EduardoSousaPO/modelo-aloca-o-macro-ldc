# Módulo `calendario` — dias úteis e feriados nacionais (ANBIMA)

> Verdade: `apps/pipeline/extract/calendario_anbima.py` + `packages/shared/schemas/calendario.py`.
> **Estado (2026-10-11): implementado** (F-008, aguardando QA da Onda 1). É a grade que **todo**
> alinhamento trimestral e **toda** acumulação de CDI/Selic usam (RF-018, CA-051/052) — sem ela,
> "não sei se é dia útil" vira "não tem feriado" e um trimestre sai errado em silêncio.
> **Leia §B antes de implementar F-014 ou F-017.**

`data/processed/calendario/dias_uteis_anbima.parquet` — **10.957 dias civis, 2001-01-01 → 2030-12-31,
7.530 dias úteis, 367 feriados**. Colunas `data`, `dia_util`, `feriado`, `fonte` — **sem
`collected_at`/`vintage`**: não é `processed_series`, é grade de datas com dois atributos, e a
procedência fica no manifesto de cada página em `data/raw/anbima-feriados/`. É o que deixa o Parquet
**byte-idêntico** entre execuções (RF-048 conferível por `sha256`). Contrato:
`CalendarioDiasUteisSchema` (espelho em `CONTRACTS.md §7`). Consulta fora de `[2001, 2030]`
**levanta** `ForaDaCoberturaDoCalendario`; estender é trocar `ANO_FIM` e reextrair (~8 s).

## A API que F-014 e F-017 consomem

```python
cal = Calendario.do_parquet()                       # ou calendario_padrao(), com lru_cache
cal.ultimo_dia_util_do_trimestre(2025, 4)           # date(2025, 12, 31)
cal.dias_uteis_entre(date(2006, 1, 1), date(2006, 12, 31))   # 249
```

`e_dia_util` · `e_feriado`/`nome_do_feriado` · `ultimo_dia_util`/`primeiro_dia_util(ano, mes)` ·
`ajustar_para_tras`/`ajustar_para_frente` (devolvem **a própria data** se já é dia útil — a operação
de CA-052) · `proximo_dia_util`/`dia_util_anterior(d, n)` (n-ésimo **estritamente** depois/antes;
`n=0` levanta) · `dias_uteis`/`dias_uteis_entre` (intervalo **fechado nas duas pontas**). Todos
existem também como atalho de módulo, delegando a `calendario_padrao()`.

## §A — Por que confiar: 3 fontes independentes, 2006-2025

**SGS 12 (CDI, do BCB) e IMA-B (S3 da ANBIMA): 5.022 × 5.022 dias úteis, zero diferença nas duas
pontas.** IBOV (API da B3): 4.953 — **69 datas só no calendário, nenhuma só na série.**

## §B — Achado que muda F-014/F-017: a B3 fecha em dia útil bancário

As 69 datas são feriados municipais/estaduais de São Paulo e a emenda de fim de ano: 24/12 (14×),
31/12 (14×), 25/01 (12×), 20/11 (11×, antes de ser nacional), 09/07 (11×), 29 e 30/12 (3× cada) e
12/06/2014. **A direção importa: B3 ⊂ ANBIMA, nunca o inverso.** Em **20 dos 83 trimestres** —
**todos os 4ºs trimestres de 2006 a 2025** — o último dia útil pela ANBIMA não tem observação da B3
(o CDI tem nos 83). Logo **toda série da B3 carrega `ffill_dias_uteis = 1` em todo 4T**. É o caso de
ADR-006 §(b).8 / CA-066, mas F-014 tem de **escolher**: (a) grade bancária única com ffill de 1 d.u.
(default do ADR) ou (b) última negociação da B3 para séries da B3 — o que cria **duas grades** de fim
de trimestre. (b) é decisão de alinhamento, **classe C**; está na DoR de F-014 (`TODO.md`, D-h).

## Armadilhas

- **O `.xls` que a SPEC nomeia é XLS/BIFF de verdade** (`D0 CF 11 E0`), não o XLSX disfarçado do S3.
  O dado vem das páginas HTML `fer_nacionais/<ano>.asp` da **mesma** fonte — mesma lista, zero
  dependência nova, zero feriado por regra (D-f). A planilha segue arquivada como **fonte de
  registro**, com WARNING se um dia virar XLSX. A ANBIMA publica 2001→2099; **2000 responde 404**.
- **O parse é auto-verificável:** a página traz o dia da semana por extenso, conferido contra
  `date.weekday()`, e o ano parseado é conferido contra o ano da URL — `1/1/06` com dia e mês
  trocados quebraria as duas checagens. **Nenhuma fórmula de feriado** foi reimplementada.
- **pandera:** `isin` de um único valor tem de ser **lista** — `isin=("ANBIMA_WEB",)` reprova toda
  linha nesta versão (a tupla de 1 é desempacotada e o `set` vira as *letras* da string).

**Features:** **F-008** (implementado) · **F-014** (alinhamento, C — leia §B) · **F-017**.
