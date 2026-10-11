# Módulo `sgs` — BCB (SGS + Olinda/Focus)

> Verdade: `apps/pipeline/extract/bcb_sgs.py` + `research/fontes-de-dados.md §A1-A2`.
> **Estado (2026-10-11): SGS implementado** (F-003, aguardando QA da Onda 1); **Focus não** (F-010).
> Núcleo macro dos 20 anos — inflação, atividade, juros, câmbio. Maior cobertura, menor esforço.

## `data/processed/sgs/` — 15 séries, 44.447 linhas, 0,00% de nulos, todas cobrindo 1T2006

| Série | Código | freq · linhas | janela | canário |
|---|---|---|---|---|
| IPCA mensal · 12m | **433** · **13522** | M · 273 | 2004-01-31 → 2026-09-30 | set/2026 = **0,82** · 4,58 |
| IBC-Br dessaz. · bruto | **24364** · **24363** | M · 271 | → 2026-07-31 (lag ~45 d) | jan/2006 = **79,44731** · 75,88784 |
| Selic over %/dia · % a.a. | **11** · **1178** | D · 5.719 | 2004-01-02 → 2026-10-09 | 03/01/2005 = **0,064826** |
| Meta Selic | **432** | D · **8.319** | 2004-01-01 → 2026-10-10 | 02/01/2006 = 18,00 |
| Selic acum. mês · % a.a. | **4390** · **4189** | M · 273 | → 2026-09-30 | — |
| CDI %/dia · acumulado | **12** · **4389** | D · 5.718 | → 2026-10-08 | 03/01/2005 = **0,064893** |
| PTAX venda · compra | **1** · **10813** | D · 5.719 | → 2026-10-09 | 09/10/2026 = **4,9892** · 4,9886 |
| PIB volume dessaz. · bruto | **22109** · **22099** | Q · 90 | 2004-03-31 → 2026-06-30 | 2006T1 = **131,74** · 128,18 |

Reconciliado: CDI 2006 = **15,0271%** (249 d.u.) e 2015 = 13,2392% por `prod(1+v/100)`; IPCA 433 ×
SIDRA `v/63` casa em **273 meses** e PIB 22109 × SIDRA `t/1621` em **90 trimestres**, `max|dif| = 0`
(`tests/unit/test_contract_sgs_sidra.py`). `--todas` traz mais 9 séries `ok` (núcleos do IPCA, IGP,
DLSP, IC-Br) **nunca rodadas ao vivo** e sem canário declarado.

## Convenções, bordas e armadilhas (medidas, não herdadas)

- **`date` de série M/Q = fim de período civil** (`fim_do_periodo`, D-a) — a API devolve o 1º dia.
  Efeito medido: a linha do **mês corrente parcial** de 4390/4189 (01/10/2026 = 0,36% contra ~1,08%
  de mês cheio) vira `2026-10-31`, cai no truncamento de data futura e é **descartada com log**.
- **`vintage` = data do `collected_at` do manifesto do bruto** (D-b) → `--offline` byte-idêntico.
- **`para_float_ponto_decimal`, nunca `para_float_ptbr`:** o JSON usa ponto decimal e trocar não
  explode — muda a escala em silêncio (`"6.930"` → 6930,0). Travado em teste.
- **`janela_maxima_dias` é o que liga o fatiamento** (diária ~5 anos → 5 fatias; M/Q = 1 fatia); o
  piso de contagem vale para o **total**, não para a fatia, e é folgado de propósito.
- **O erro de janela de 10 anos virou HTTP 406** (a pesquisa mediu 200), e **série inexistente devolve
  XHTML com HTTP 200** — é essa a fixture de CA-003. Tudo passa por `validar_corpo_json_array`.
- **Meta Selic (432) é série de calendário corrido:** mesmo valor em sábado, domingo e feriado
  (`SERIES_DIARIAS_DE_CALENDARIO`), com continuidade **mais forte** — nenhum dia corrido ausente. Com
  `dataFinal` futuro devolve até a próxima reunião do Copom; `truncar_em` corta (CA-013).
- `/metadados` → 404 e `sgspub` → 502: códigos versionados no catálogo. Rate limit (429) existe.
- **R16 · descontinuadas:** swaps 7801-7806 (2019) e IMA 12461-12469 (22/05/2023) **não entram**
  (S-02, S-04); o portão é `status=ok` no catálogo, com teste.

**Features:** **F-003** (implementado) · **F-010** · **F-011** · **F-013**/**F-015**/**F-017**.
