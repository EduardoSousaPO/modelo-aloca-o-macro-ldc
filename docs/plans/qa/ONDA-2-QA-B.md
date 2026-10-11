# QA independente + revisão numérica — Onda 2, lote B · **F-016** e **F-017**

> **Validation Mode** (`AGENTS.md §15`), subagente **distinto** de quem implementou (`AGENTS.md §14`).
> **2026-10-11** · `main` · commit `fcdfaeb` · `uv run`, **sem rede**, `data/` **não reconstruído**.
> Lote A (`ONDA-2-QA-A.md`) revisa F-014/F-015. F-018/F-019/F-021 em implementação — ignorados.
>
> **Veredito: F-016 APROVADO · F-017 APROVADO · 0 × P0 · 1 × P1 · 8 × P2.**
> Condição conhecida do briefing: **ADR-004, ADR-005 e ADR-006 em `Proposta`** — libera implementar e
> mergear (decisão do orquestrador), **não** libera publicar (gate classe D, §14).

---

## 1. CI real (colado)

```
$ uv run ruff check .                     -> All checks passed!
$ uv run ruff format --check .            -> 67 files already formatted
$ uv run pytest tests/unit tests/contract -m "not network"
   -> 1141 passed, 5 skipped, 17 deselected, 1 xfailed in 63.23s (0:01:03)

$ uv run pytest tests/unit/test_canonical_curva.py tests/contract/test_curva_contract.py
   -> 103 passed, 3 skipped in 35.09s
$ uv run pytest tests/unit/test_canonical_retornos.py tests/contract/test_asset_returns_contract.py
   -> 93 passed in 3.48s
$ LDC_IGNORAR_DATA=1 uv run pytest <os 4 arquivos>   -> 167 passed, 16 skipped in 5.00s
```

**As 2 falhas de `test_canonical_raw_series.py` que F-017 §7.5 reportava não existem mais** (D-k + rebuild).
N2 segue **parcial**: `tests/integration/` vazio e o marker `integration` não existe em `pyproject.toml`
(`--strict-markers`) — mesmo padrão aceito em F-013/F-014, **declarado**.

---

## 2. Arquivos vs. contrato · catálogo · `obs` alterado

| Item | Verificado | Resultado |
|---|---|---|
| `canonical/curva.py` (1.100 L) + `test_canonical_curva.py` (766 L) + `test_curva_contract.py` (309 L) | existem | ✔ caminhos do **briefing**; divergência do Feature Contract **sancionada** em `TODO.md` |
| `canonical/retornos.py` (1.096 L) + `test_canonical_retornos.py` (1.200 L) + `test_asset_returns_contract.py` (419 L) | existem | ✔ idem; **93** testes = 56 + 37, exatamente o declarado |
| Catálogo **134 → 138**, só acréscimo | `len(SERIES_CATALOG)=138`, 138 ids únicos, materializado **138 × 26**; `git show 3265499 -- …series_catalog_data.py` → **+66 / −0** | ✔ **nenhuma entrada existente alterada** por F-016 |
| `obs` de `INCLINACAO_REAL_5A_1A` (autorizado) | `git show fcdfaeb` → **só o campo `obs`**; `series_id`, `unit` (`pp`), `identificador`, `transformacao_padrao` intactos | ✔ feito pelo **orquestrador**; texto correto ("SECUNDARIA desde D-i", 60,53 %) |
| As 11 séries no catálogo e em `raw_series` | 11/11, `presente_no_processed=True`, `fonte=DERIVADO`, `confianca=NAO_VERIFICADO`; `pp` nas 4 inclinações e `%a.a.` nos 6 vértices + breakeven, igual em catálogo **e** `raw_series` | ✔ |
| `CURVA_*_10A` fora do catálogo e não gravadas | 0 entradas, 0 Parquets | ✔ CA-055 |
| Dívida "134 séries" de F-016 §7 | `CONTRACTS.md §2.1`, `README.md`, `AUDITORIA-HARNESS.md` já dizem **138** | ✔ fechada |
| `sha256` em disco vs. `TODO.md §1` | `raw_series 0d23df7a` · `series_catalog f56f207e` · `alinhado ac0d9842` · `macro dcded731` · `asset_returns ab61eeca` | ✔ **5/5** |
| 11 Parquets de curva vs. `relatorio_curva.json` **e** vs. F-016 §4.1/§4.7 | 11/11 idênticos, inclusive os **7 pré-D-i** | ✔ D-i não mexeu em número publicado |
| `relatorio_retornos.json → sha256` vs. Parquet em disco | `ab61eeca36a96b6b…` = `ab61eeca36a96b6b…`; `cdi_tri` de `bases_por_trimestre` == linha `CDI` da tabela | ✔ |
| Fora de escopo | árvore suja só em `schemas/{__init__,macro_quarterly,regimes}.py` + `asof.py`/`regimes_v*.py` — **F-018/F-019/F-021 em paralelo**, não F-016/F-017 | ✔ |

---

## 3. Revisão numérica independente — **meu código, não o deles**

Scripts próprios que **não importam** `curva.py` nem `retornos.py`.

### 3.1 F-016 — recálculo do **CSV bruto** (`precotaxatesourodireto__2026-10-10.csv`, `sha256 75d297b4…`)

Regra que eu reimplementei: famílias `NTNB+NTNBP` / `LTN+NTNF`, `Taxa Venda Manha`, prazo em dias
corridos, `prazo > 0`, **média** em vencimento duplicado, interpolação linear nos alvos 365,25 /
1.095,75 / 1.826,25 d; inclinações por subtração, breakeven por **razão**.

**Igualdade EXATA (`==`, sem tolerância) nas 11 séries × 5.436 datas base — 0 divergências, `max|dif| = 0,0`,
0 divergências de nulidade.** Nulos meus = gravados, um a um: `REAL_1A` 2.202 · `REAL_3A` 246 · `REAL_5A` 0 ·
`NOM_1A` 126 · `NOM_3A` 141 · `NOM_5A` 219 · `INCL_REAL_5A_1A` 2.202 · `_5A_3A` 246 ·
`INCL_NOM_5A_1A` 345 · `_5A_3A` 219 · `BREAKEVEN_5A` 219.

**As 5 datas base pedidas, recalculadas à mão** (todas `OK (exato)`):

| data base | série | curto (prazo, taxa) | longo (prazo, taxa) | peso | meu = gravado |
|---|---|---|---|---|---|
| 2006-01-02 | `NOMINAL_5A` | NTNF 01/01/2010 (1.460 d, 15,79) | NTNF 01/01/2012 (2.190 d, 15,78) | 0,5017123 | **15,784983** |
| 2006-01-02 | `REAL_1A` | NTNB 15/08/2006 (225 d, 12,57) | NTNB 15/05/2007 (498 d, 11,49) | 0,5137363 | **12,015165** |
| 2010-06-30 | `REAL_5A` | 15/05/2015 (1.780 d, **média 6,705**) | 15/05/2017 (2.511 d, 6,52) | 0,0632695 | **6,693295** |
| 2016-01-04 | `NOMINAL_1A` | 01/01/2017 (363 d, **média 15,81**) | LTN 01/01/2018 (728 d, 16,53) | 0,0061644 | **15,814438** |
| 2022-03-31 | `REAL_3A` | 15/08/2024 (868 d, média 5,285) | 15/08/2026 (1.598 d, média 5,245) | 0,3119863 | **5,272521** |
| 2026-10-09 | `REAL_5A` | NTNB 15/08/2030 (1.406 d, 6,78) | 15/08/2032 (2.137 d, **média 6,765**) | 0,5748974 | **6,771377** |
| 2026-10-09 | `REAL_3A` | NTNBP 15/05/2029 (949 d, 6,74) | NTNB 15/08/2030 (1.406 d, 6,78) | 0,3211160 | **6,752845** |

Derivadas nas mesmas datas: `10,370282 − 11,027857 = −0,657575` = `INCLINACAO_REAL_5A_3A` de 02/01/2006;
`((1,15784983/1,10370282) − 1)×100 = 4,905941` = `BREAKEVEN_5A` da mesma data. Em 2016/2022/2026 o
`REAL_1A` sai `NULL` por `sem_vencimento_abaixo_do_vertice` e as duas 5a−1a **herdam** o nulo — confere.

**Sem extrapolação, em toda a série (5.436 × 6 vértices):** peso fora de `[0,1]` → **0**; valor fora do
intervalo das duas taxas → **0**; **`value` nulo ⇔ motivo preenchido ⇔ sem par de vencimentos em volta**
→ verdadeiro em **100 %** das linhas. Meus motivos batem com o relatório um a um
(`sem_titulo_vivo_na_data` = **0**).

**Coberturas recalculadas** nas **5.184** datas base de 2006-01-01 a 2026-10-09: real 5a−1a = **60,53 %** ·
real 5a−3a = **95,25 %** · nominal 5a−1a = 97,57 % · nominal 5a−3a = 100,00 % · `BREAKEVEN_5A` = 100,00 %.
**Os dois números de D-i reproduzem ao centésimo.**

**Breakeven: razão, não subtração.** Nas 5.217 datas com valor, `gravado == razão` é exato
(`max|dif| = 0,0`) e `== subtração` é falso; `|razão − subtração|` média **0,3268 pp**, máx **0,7636 pp**.
Validação **externa** minha, nos **19** vértices da Curva Zero ANBIMA de 09/10/2026: a razão reproduz a
coluna "Inflação Implícita" **da própria ANBIMA** com erro máx **0,010 bp**; a subtração erra até **37,2 bps**.

**Sanity vs. Curva Zero ANBIMA 09/10/2026** (`data/raw/anbima-ettj/cz_261009.csv`, lido por mim):
252 d.u. PREF **+20,3 bps** · 756 IPCA **+5,8** · 756 PREF **+10,0** · 1.260 IPCA **+7,4** ·
1.260 PREF **+15,2** · implícita 5 a **+7,0** · 252 IPCA = `CURVA_REAL_1A` **NULL** (sem suporte).
**Diferenças de 5,8 a 20,3 bps, todas no mesmo sinal (nossa taxa mais alta)** — compatível com spread de
varejo + YTM interpolada ≠ spot de Svensson. Nenhuma igualdade forçada. ✔

### 3.2 F-017 — recálculo próprio dos níveis / `raw_series`

**`ret_tri` de 6 ativos × 83 trimestres — igualdade exata, 0 divergências** (níveis de
`alinhado_trimestral`; para `SP500_BRL`, `DERIVADO`, apliquei **minha** regra "último d.u. ≤ `quarter_end`"
sobre `raw_series`): `IBOV` 82/82 · `IMAB` 82/82 · `IFIX` 63/63 · `SP500_BRL` 82/82 · `IMOB` 75/75 ·
`USDBRL` 82/82 — `max|dif| = 0,0`, 0 divergências de nulidade.

**CDI por produto dos fatores diários da SGS 12** (`%/dia`, 5.718 obs; janela = pertencimento ao trimestre
com corte em `quarter_end`): **igualdade exata nos 83 trimestres** e `n_dias_uteis` **idêntico**.
2006: `4,036907 · 3,577462 · 3,511687 · 3,123641 %` em `63+61+64+61 = **249**` d.u. →
**encadeado = 15,027140 %** (vs. 15,03 % publicado). ✔ CA-014/015

**2ª fonte, SGS 4389** (`% a.a.`, base 252 — outro código, outra unidade), `fator=(1+t/100)^(1/252)`:
**83** trimestres, `max|dif| = **2,80e-05 pp**` (2024Q3) ≤ 3e-5 ✔, média 9,11e-06; 4T2008 3,316678 % vs.
3,316673 % (**4,8e-06 pp**). Contraste: a **SGS 4390** (Selic acumulada no mês) daria **15,0807 %** em 2006
— número diferente, confirma que não houve troca de série.

**IPCA trimestral = 3 meses da SGS 433 encadeados:** **83/83** trimestres com exatamente **3** meses,
nenhum parcial. 2006Q2 = `(1,0021 · 1,0010 · 0,9979) − 1` = **0,099559 %** de `0,21 / 0,10 / −0,21`. ✔

**Excesso e real por razão:** nas **1.940** linhas com valor, `ret_excesso_cdi == (1+r)/(1+cdi)−1` e
`ret_real == (1+r)/(1+ipca)−1` são **exatos** (`max|dif| = 0,0`); `== subtração` é **falso**, exceto nas
**83** linhas do próprio **CDI** (as duas dão 0). `|razão − subtração|`: média **0,139375 pp**, máx
**1,495181 pp**. Dupla deflação: `|ret_real − deflacionado 2×|` chega a **0,0439** → não houve. ✔ CA-069/071

**Encadeamento geométrico (CA-070), do caminho diário:**

| caso | n | produto − 1 | `ret_tri` | dif | **soma** |
|---|---|---|---|---|---|
| IBOV 4T2008 | 62 | −0,24203981851898393 | −0,24203981851898426 | 3,3e-16 | **4,25 pp fora** |
| IMAB 3T2015 | 65 | −0,04475473916865380 | −0,04475473916865480 | 1,0e-15 | 0,14 pp |
| IFIX 1T2020 | 62 | −0,22000387793268594 | −0,22000387793268661 | 6,7e-16 | 0,92 pp |
| USDBRL 1T2020 | 62 | +0,28977596943458828 | +0,28977596943458939 | 1,1e-15 | 3,06 pp |
| SMLL 2T2009 | 61 | +0,49551643972102410 | +0,49551643972102299 | 1,1e-15 | **8,13 pp fora** |

`vol_intra_tri` (desvio **amostral** × `√n`) e `dd_intra_tri` (pico em `P_ini`) reproduzem nos 5 casos com
dif ≤ 5,6e-17; `dd ≤ 0` em **todas** as linhas (máx 0,0), `vol ≥ 0` com 23 nulos.

**Totais e bordas:** 1.963 linhas · **24** ativos · 83 trimestres (`2006Q1..2026Q3`) · PK duplicada **0** ·
nulos `is_total_return` **820** / `price_ini` 106 / `price_fim` 83 / as 6 irmãs **23** cada ·
`ffill_dias_uteis = {0: 1.748, **1: 215**}`, nenhum 2..5, e os **215 só** em série da B3 (20 cada em
IBOV/ICON/IDIV/IEEX/IFNC/IMAT/INDX/SMLL/UTIL, IMOB 19, IFIX 16) · `n_dias_uteis` **58..66** ·
`ret_tri ∈ [−45,46 % IMOB 2020Q1, +61,67 % IMOB 2009Q2]` ⊂ `[−1, 5]`.
**`USDBRL`: 83 linhas, 82 retornos, 1º em 2006Q2, `is_total_return=False`** ✔ D-l.
**1º trimestre sem retorno em 23 de 24 ativos** (todos menos o CDI), sempre **com** `price_fim`.
`IFIX`: 2010Q4 `price_ini NULL` / `price_fim 1000,0` / `ret_tri NULL` / `data_inicio_serie 2010-12-30`;
**2011Q1 = primeiro retorno**, `1028,25/1000,0 − 1 = +2,825 %` ✔ CA-063.
`is_total_return`: `SP500_USD`/`SP500_BRL`/`USDBRL` = **False**; IBOV/IFIX/IMA/IRF-M/`ACWI_BRL` = **True**;
9 setoriais da B3 + CDI = **None** (820 = 83×8 + 80 ICON + 76 IMOB) ✔ CA-064/G-01.

---

## 4. Ataque (`AGENTS.md §15`) — o que tentei quebrar

| # | Ataque | Medido por mim | Veredito |
|---|---|---|---|
| 1 | `TAXA_VENDA` zero/`0,00` propagada | `== 0` nas 4 siglas da curva: **0**. Os `0,00` estão em `Tesouro Selic` (1.151) e 1 de `IGPM+`, **fora** da curva. `TAXA_COMPRA == 0`: 14 NTN-F + 7.747 Selic — métrica **não** usada | ✔ imune |
| 2 | Vencimento exatamente no vértice | com ACT o alvo é **fracionário** → **0** coincidências no painel; `n_exatos = 0` é informação, não falha. Há 25/11/12 vencimentos em 365/1.096/1.826 d inteiros (o caso que aparece na métrica `dias_uteis`) | ✔ coerente |
| 3 | Dia com só 1 título na família | **0** casos `(data, família)` em 5.436 × 2; `sem_titulo_vivo_na_data` existe e nunca dispara | ✔ guarda inerte |
| 4 | **Par degenerado** (2 títulos, MESMO vencimento) | 29.289 linhas agregadas (REAL 16.406 / NOM 12.883; 8 e 14 vencimentos distintos). A **média por vencimento antes** da interpolação faz com que nunca existam 2 pontos com o mesmo prazo: **0** casos → **divisão por zero impossível** | ✔ imune por construção |
| 5 | Título que vence na própria data base | `prazo == 0`: **0** · `< 0`: **0**; guarda `prazo > 0` fica | ✔ |
| 6 | Taxas negativas de NTN-B | **141** na família REAL (104 `IPCA+ c/ juros` + **37** `Principal`); passam intactas — juro real negativo de 2020-21 é dado real | ✔ (P2-3) |
| 7 | `price_fim` com `ffill=1` (4T da B3): o `ret_tri` seguinte usa o **mesmo** nível como `price_ini`? | **Sim, e está certo:** nos 20 (IBOV) / 16 (IFIX) / 19 (IMOB) trimestres com `ffill=1`, `price_ini(T+1) == price_fim(T)` em **100 %** → cadeia contínua, **nenhum dia perdido nem contado 2×**. Ex.: 2006Q4 `date_obs = 28/12`, `quarter_end = 29/12` | ✔ (gera o **P1-1**) |
| 8 | CDI de trimestre com feriado no último d.u. | **todos** os 83 `quarter_end` são dia útil ANBIMA e em **83/83** a última observação da SGS 12 **é** o `quarter_end` — nenhum trimestre fecha num buraco | ✔ |
| 9 | Janela do CDI == `(quarter_end(T−1), quarter_end(T)]` | minha reimplementação por pertencimento é **idêntica** ao intervalo semiaberto em **82/82** trimestres com T−1 — **0** divergências | ✔ |
| 10 | `n_dias_uteis` 58..66 coerente com o calendário | d.u. ANBIMA/trimestre = **60..66** (60:1, 61:24, 62:18, 63:13, 64:9, 65:11, 66:6). **Acima:** 33 linhas, **todas** `SP500_USD` (calendário EUA, máx +2). **Abaixo:** 566, máx −3, todas B3 ou `SP500_*` → é **B3 ⊂ ANBIMA** (D-h); mínimo 58 = `SP500_BRL`. **Nenhuma data de série doméstica fora do calendário ANBIMA** (0 em `B3_IBOV`, `B3_IFIX`, `ANBIMA_IMAB`, `BCB_SGS_12`, `BCB_SGS_1`) | ✔ banda explicada |
| 11 | CA-024 reconstruído por mim (10 anos) | `CURVA_NOMINAL_10A` = **36,81 %** (1.908/5.184) e **0/248 em 2006** → `NULL` em todo 2006, sem extrapolação; `CURVA_REAL_10A` = 100,00 %. **Nenhuma gravada** | ✔ CA-024 + CA-055 |
| 12 | Idempotência / revisão retroativa | não reconstruí `data/` (instrução). Confirmei **16 `sha256`** de disco contra relatórios e packs, incl. os **7 pré-D-i inalterados**; `relatorio_curva.json → metrica_prazo = dias_corridos` (não ficou rodada de `dias_uteis` em cima) | ✔ coerente |

---

## 5. Matriz de CAs

| CA | Teste (meu) | Tipo | Status | Evidência |
|---|---|---|---|---|
| **CA-023** | 6 vértices no catálogo e gravados; equivalência `nulo ⇔ motivo ⇔ sem par em volta` | pos. + neg. | ✔ | 11 Parquets × 5.436; equivalência **100 %**; flag em 3 lugares (linha nula, `relatorio → motivos`, quadro em memória) |
| **CA-024** | vértice **nominal 10 a em 2006** | negativo | ✔ | **0/248** datas com valor; 2006+ = **36,81 %**; não gravado |
| **CA-025** | inclinação real ≥ 95 % dos d.u. 2006→2026 | integração | ✔ **pela série de D-i** | 5a−3a **95,25 %** (fecha) · 5a−1a **60,53 %** (não fecha, **declarado**, SPEC intocada) |
| **CA-026** | valor trimestral = último d.u.; coluna documenta TD varejo ≠ ETTJ ANBIMA | unit + catálogo | ✔ **parcial** | 4 trimestres conferidos em `macro_quarterly`: 2019Q4 usa **30/12** porque o TD não publica em 31/12 — correto. Ressalva "não é Svensson" em **2 de 11** `obs` → **P2-1** |
| — | breakeven por **razão** | negativo | ✔ | 5.217 linhas exatas; ANBIMA reproduzida a **0,010 bp** vs. **37,2 bps** da subtração |
| **CA-014** | CDI de 2006 pela SGS 12 | canário | ✔ | **15,027140 %** em **249** d.u., recalculado do `raw_series` |
| **CA-015** | 4 trimestres encadeiam no fator anual | unit | ✔ | `63+61+64+61 = 249`; produto dos 4 = o anual, dif 0,0 |
| **CA-016** | série é **percentual**, não fator | unit neg. | ✔ | unidade `%/dia`; `prod(1+v/100)` exato; sem `/100` daria > 1e5 |
| **CA-062** | ≥ 18 `asset_id`, todos no catálogo | contrato | ✔ | **24**; os **8** de fora com motivo em `ATIVOS_FORA_DO_UNIVERSO`, publicado |
| **CA-063** | nenhuma linha antes de `data_inicio_serie` | contrato neg. | ✔ | ICON 80 / IMOB 76 / IFIX 64 linhas; 1º trimestre **parcial** com `price_fim` e `ret_tri` nulo |
| **CA-064** | price × total return distinguidos | contrato | ✔ | `SP500_*`/`USDBRL` False, IBOV/IFIX/IMA True, 820 `None` nomeados (G-01 + CDI) |
| **CA-069** | excesso por **razão** | unit + acervo | ✔ | 1.940 linhas exatas; subtração difere (média 0,139375 pp, máx 1,495181 pp); iguais só nas 83 do CDI |
| **CA-070** | acumulação **geométrica** | unit | ✔ | 5 casos, dif ≤ 1,1e-15; a **soma** erraria 0,14 a **8,13 pp** |
| **CA-071** | IPCA do mesmo trimestre, **uma** vez | unit neg. | ✔ | 83/83 com 3 meses; dupla deflação divergiria em até 0,0439 |

---

## 6. Achados

**P0 — nenhum.**

**P1-1 · (F-017) desalinhamento de janela entre o preço e o CDI, não declarado.**
`F-017 §2.4` afirma "a janela do CDI é a mesma janela dos preços" e prova isso **contra `quarter_end`** —
mas o caminho de cada ativo é `(date_obs(T−1), date_obs(T)]`, e com `ffill = 1` (D-h) `date_obs ≠ quarter_end`.
Medido: **599 das 1.857** linhas com excesso comparam janelas que diferem **1 a 3 d.u.** do CDI
(`−3: 98, −2: 120, −1: 348, 0: 1.258, +1: 22, +2: 11`). Viés implícito no `ret_excesso_cdi`: média
**0,0185 pp**, p95 0,0984, **máx 0,1575 pp**; nas **212** linhas com `ffill = 1`, média **0,0827 pp**.
Não é erro de conta (a cadeia de preços é contínua — ataque #7) e é consequência direta de **D-h**, mas
**não está em nenhum dos 9 itens de `F-017 §6`** nem no `relatorio_retornos.json`. É ~8× menor que o efeito
razão-vs-subtração (0,139 pp), logo **não bloqueia o merge** — mas é **condição do gate classe D**
(`§14.7` pede comunicação escrita das limitações) e afeta a métrica-cabeça de ADR-002/D5.
**Ação pedida:** 1 item novo em `F-017 §6` + 1 linha em `convencoes` do relatório. **Não corrigi nada.**

**P2 (8) — nenhum move número publicado:**

1. **(F-016, CA-026)** só as duas `INCLINACAO_REAL_*` trazem no `obs` a ressalva "não é a ETTJ Svensson
   oficial da ANBIMA". Nas outras **9** a origem TD está documentada por `fonte=DERIVADO` +
   `identificador` ("interpolacao de TESOURO_TD_PRECOTAXA") + `fonte_url`, o que satisfaz a 2ª cláusula de
   CA-026 em substância. Sugestão: 1 frase nas 9.
2. **(F-016)** as **3** asserções de cobertura de CA-025 (60,53 % e 95,25 %) só rodam na parametrização
   `data/processed`; **na árvore limpa do CI são `skip`**. Os dois números que sustentam D-i não têm
   evidência reproduzível em CI. Mesmo padrão aceito em F-013/F-014, mas numa classe C vale registrar.
3. **(F-016 §3.1)** o pack diz "104 observações" de NTN-B negativa; o medido na **família** é **141**
   (104 `IPCA+ c/ juros` + 37 `Principal`). Texto, não dado.
4. **(F-016)** `relatorio_curva.json` não tem chave `vertices_fora_do_catalogo` no topo (é `null`); os
   10 anos estão em `cobertura_de_2006_em_diante.vertices` com `no_catalogo: false`. O pack §0 cita o nome
   da constante como se fosse chave do JSON.
5. **(F-016 / D-n)** nenhuma das **4 séries de D-i** está em `alinhado_trimestral` (49 séries, `DERIVADO`
   fora por desenho) nem em `macro_quarterly`, que publica só as **7** pré-D-i com `inclinacao_real_5a_1a`
   em **33 nulos (39,8 %)**. Isso está **decidido e registrado** em **D-n** (F-019/F-021 leem a 5a−3a de
   `raw_series` via `alinhar_series`), mas **não há teste nem guarda** que impeça F-019 de usar a coluna de
   39,8 % de nulos achando que é a principal — exatamente o cenário que a opção 3 de F-016 §4.3 rejeitou.
   Recomendo 1 teste de contrato em F-019 antes do merge dela.
6. **(F-017 §5.5)** números pré-D-l: o pack diz 1.858 linhas e média 0,138154 pp; o medido é **1.940** e
   **0,139375 pp** (o máx 1,495181 pp **confere**). `§10` diz que §5 "continua valendo" sem atualizar estes dois.
7. **(F-017 §5.4)** a nota diz que a SGS 4390 daria "15,0768 %" em 2006; medi **15,0807 %**. A conclusão
   (não é o CDI) está certa; o número, não.
8. **(F-016)** a contagem de casos do pack (59 + 31 = 90) está abaixo do coletado hoje (**106** = 103 + 3
   skip). F-017 confere exatamente (93 = 56 + 37).

---

## 7. Veredito

| Feature | Veredito | Condição |
|---|---|---|
| **F-016** | **APROVADO** | A revisão numérica independente **reproduziu as 11 séries × 5.436 datas com igualdade exata a partir do CSV bruto**, as duas coberturas de D-i ao centésimo, CA-023/024/025/026 com evidência própria e validação **externa** contra a ANBIMA. Os ataques da curva (zero, vértice exato, 1 título, par degenerado) não quebraram nada. Merge liberado; **publicar depende do gate classe D, de ADR-004 sair de `Proposta` e da ratificação de D-i e D-j pelo Edu**. |
| **F-017** | **APROVADO** | `ret_tri`, CDI, IPCA, excesso, real, `vol` e `dd` **reproduzidos por fora com igualdade exata** (0 divergências em 6 ativos × 83 trimestres, 83 trimestres de CDI, 1.940 linhas de excesso/real), canário 2006 = **15,027140 %**, 2ª fonte (SGS 4389) a **2,8e-05 pp**, razão ≠ subtração comprovada. **P1-1 é declaração, não recálculo** — exigível antes do gate classe D, não do merge. ADR-005/ADR-006 em `Proposta` = decisão do orquestrador. |

**Bug ≤ 10 linhas: nenhum encontrado.** Nada foi corrigido por este QA; nenhum arquivo além deste foi escrito.

*Reproduções: 3 scripts próprios no scratchpad da sessão (não versionados), que leem só `data/raw/tesouro-direto/*.csv`, `data/raw/anbima-ettj/cz_261009.csv`, `data/processed/{curva,calendario}/*.parquet` e `data/canonical/*.parquet` — **nenhum import de `curva.py` ou `retornos.py`**.*
