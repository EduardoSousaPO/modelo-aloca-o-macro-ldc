# Módulo `sidra` — IBGE (SIDRA)

> Verdade: `apps/pipeline/extract/ibge_sidra.py` + `research/fontes-de-dados.md §A3`.
> **Estado (2026-10-11): implementado** (F-004, aguardando QA da Onda 1). Entrega o que o SGS não dá
> com abertura: **IPCA em número-índice** e **PIB trimestral** (abertura setorial = fase 2).

## `data/processed/sidra/` — 6 séries, `p/all` (histórico completo, ≤ 170 KB por série)

| `series_id` | identificador | freq · linhas | janela | % nulos | canário |
|---|---|---|---|---|---|
| `SIDRA_1737_V63` | `t/1737 v/63` | M · 562 | 1979-12-31 → 2026-09-30 | 0,18 | set/2026 = **0,82** |
| `SIDRA_1737_V2265` | `v/2265` (12m) | M · 562 | idem | 2,14 | 4,58 |
| `SIDRA_1737_V2266` | `v/2266` (nº-índice) | M · 562 | idem | **0,00** | 7.695,82 |
| `SIDRA_1621_V584_90707` | `t/1621 v/584` dessaz. | Q · 122 | 1996-03-31 → 2026-06-30 | **0,00** | 2006T1 = **131,74** |
| `SIDRA_1620_V583_90707` | `t/1620 v/583` s/ ajuste | Q · 122 | idem | **0,00** | 2006T1 = 128,18 |
| `SIDRA_5932_V6564_90707` | `t/5932 v/6564` T/T−1 | Q · 122 | idem | 0,82 | 2006T1 = **1,6%** |

Nulos são **todos explicados e todos `None`, nunca `0`**: 1 em `v/63` (197912 não tem mês anterior),
12 em `v/2265` (não há acumulado de 12m nos 12 primeiros meses), 1 em `v/6564` (1996T1). Por `date`:
`v/63` × SGS 433 casa em **273 meses** e `t/1621` × SGS 22109 em **90 trimestres**, `max|dif| = 0` —
SGS 22109 **é** `t/1621 v/584 c11255/90707`.

## Convenções, bordas e armadilhas

- **`date` = fim de período:** `"200601"` é **2006-01-31** em `t/1737` (mensal) e **2006-03-31** em
  `t/1621` (trimestral). Os dois têm 6 dígitos e o texto não distingue — `fim_do_periodo` **recebe**
  o `freq` do catálogo, não adivinha.
- **`vintage` = data do `collected_at` do manifesto** (D-b). Aqui isso importa: o IBGE revisa
  trimestres passados **sem acrescentar trimestre novo**, e a convenção antiga ("última data do
  histórico") faria a revisão colidir na PK e sobrescrever o retrato anterior.
- **Escopo = o catálogo, não lista local:** `_conferir_catalogo()` exige igualdade de conjuntos no
  `import` — série nova no catálogo sem extrator **quebra o import** em vez de ficar sem extrair.
- **CA-004 e CA-005 não fecham no número que a SPEC escreve:** monotonia real 0,9626 (21 meses de
  deflação de verdade) e 3,52e-04 pp de divergência, contra um limite **analítico** de 3,97e-04 pp
  que vem das 2 casas decimais do nº-índice publicado. Medição, proposta e motivo em
  `DECISIONS_LOG §2.1` (D-e) e `TODO.md §4` — não é defeito do extrator.
- **A 1ª linha do array é cabeçalho**, não dado — `descartar_cabecalho` **exige** `V == "Valor"` e
  levanta se a fonte parar de mandá-la.
- **Resposta vazia vem com HTTP 200:** `p/197001` em `t/1737` devolve `[{cabeçalho}]`, zero dado →
  `RespostaTruncada` **antes** de tocar `data/raw/` ou `data/processed/` (CA-003).
- **Tabela/variável trocada é o erro mais provável e não levanta sozinho:** `t/1620` (sem ajuste) e
  `t/1621` (com) têm a mesma forma. Cada linha é conferida contra `D2C`, `D4C` e `NC == "1"`.
- **`V` é string com ponto decimal** → `para_float_ponto_decimal` (`para_float_ptbr` leria
  `"7695.82"` como 769.582). `AUSENCIAS_SIDRA` cobre `""`, `"-"`, `".."`, `"..."` e **`"X"`** (sigilo).
- **Look-ahead:** o PIB sai ~60 dias após o fim do trimestre (`lag_divulgacao_dias = 60` no
  catálogo); a materialização `asof` é **F-018**, não daqui.

**Features:** **F-004** (implementado) · **F-015** · **F-018** · **F-019** · setorial: fase 2.
