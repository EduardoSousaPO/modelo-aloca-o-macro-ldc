# ONDA-2-QA-A — QA independente + revisão numérica de **F-014** e **F-015**

> **Subagente de QA (classe C), lote A da Onda 2.** Não implementei nenhuma das duas features e não
> corrigi nada. **2026-10-11** · `main` · commits **`3265499`** (F-014) e **`fcdfaeb`** (F-015) ·
> Prompt 3, `AGENTS.md §14–§15`, `CLAUDE.md §9`. **Método:** toda conferência numérica é de **código
> meu**, escrito do zero neste QA, que **não importa** `alinhamento.py` nem `macro_quarterly.py` —
> lê o calendário ANBIMA de F-008, `raw_series` e `data/processed/focus/` e reexpressa as regras do
> ADR-006 sozinho. `data/canonical/` **não** foi reconstruído: os builds de ataque usaram
> `raiz=<scratch>`.

## 1. CI real, rodado por mim (N1 + contract)

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
67 files already formatted

$ uv run pytest tests/unit tests/contract -m "not network"
1141 passed, 5 skipped, 17 deselected, 1 xfailed in 61.38s (0:01:01)
```

Só os 4 arquivos das duas features: **241 passed, 2 skipped** (skips declarados: "acervo contínuo,
não há buraco de recorte" e "a conferência equivalente é o diff numérico"). F-014 53 + 30 funções ·
F-015 57 + 33. Os **2 testes de F-013** que `F-015.md §8` dava vermelhos estão **verdes** (D-k).
**Ressalva (P2-5):** `ci.yml` roda **só `pytest tests/unit`** (job de `tests/contract` comentado) e
`data/canonical/*` é `.gitignore`d → o **N2 declarado não existe no GitHub** e os **32** testes de
acervo (14 F-014 + 18 F-015) **pulam** lá.

## 2. Arquivos vs. Feature Contract
| Desvio | Veredito |
|---|---|
| F-014/F-015: `transform/*` → `canonical/*` | **aceitável** — declarado em `TODO.md` e nas fichas §7.1, aceito pelo orquestrador; é onde F-013 mora e de onde `alinhar_series` é importado |
| nomes dos testes (`test_canonical_*`, `*_contract`) e `tests/integration/*` → seções D/E e C/D do unit | **aceitável** — marker `integration` inexistente com `--strict-markers` |
| F-014: **artefato novo** `alinhado_trimestral.parquet` + `CONTRACTS.md §8` | **aceitável** — justificado (o diff de classe C passa a ser igualdade) e aceito |

**Schemas — só acréscimo, confirmado no diff:** `alinhado_trimestral.py` é **módulo novo** (18
colunas, 11 checks); `series_catalog.py` ganhou **1 coluna nullable** (`calendario`) sem mudar
tipo/nome/nulidade de nenhuma existente; `series_catalog_data.py` **+4 entradas** (D-i);
`__init__.py` só imports/`__all__`; F-015 **não alterou schema nenhum**. ✔

## 3. Revisão numérica independente — F-014
Reimplementei a régua inteira (grade, 3 calendários, ffill em dias úteis, limite de 5, painel
desbalanceado) e comparei **célula a célula, sem tolerância**:

| Conferência (código meu) | Resultado |
|---|---|
| grade dos **83** últimos dias úteis vs. `quarter_end` publicado | **0 divergências**; **24/83** com `quarter_end` ≠ fim civil, lista idêntica, incluindo as duas **Sextas-feiras Santas** (2013-03-28, 2024-03-28) |
| **todas as 49 séries × 83 trimestres** (não só as 10 sorteadas, seed 20261011): `value`, `date_obs`, `ffill_dias_uteis`, `lacuna_dias_uteis`, `date_ultima_obs`, `date_alvo` | **4.038 células conferidas, 0 erros** (a amostra de 10 × 83 = 830, 0 erros) |
| células com `ffill = 1` | **215**, **100% `B3_API`**, **11** séries, **20** trimestres, **todos 4T** (`2006Q4..2025Q4`); recontei a distância e é **exatamente 1 d.u.** nas 215; **zero** ffill 2..5 |
| nulos | **7**, todos **2026Q3**: PIB SGS 22099/22109 e SIDRA 1620/1621/5932 com lacuna **65** d.u.; IBC-Br 24363/24364 com **42**; todos `lacuna_acima_do_limite_de_ffill`, `date_obs` nulo, **nenhum** herdou o período anterior |
| nenhuma linha antes do início da série | ICON **80** (1º = 2006Q4, raw min 2006-12-28), IMOB **76** (2007Q4, 2007-12-28), IFIX **64** (2010Q4, 2010-12-30); as 46 restantes têm 83; **nenhuma** série tem linha com observação disponível e sem publicação |
| PK `(series_id, quarter)` · `quarter_end` único por trimestre · nulos nas outras 15 colunas · `date_obs` apontando linha `NaN` | 0 duplicadas · **True** (opção (a) de D-h travada no dado) · **0** (`motivo_nulo` em exatamente 7) · **0** |

**Canários (6), recalculados por mim e cruzados com `raw_series[date_obs]`:** IBOV 2006Q1
**37.951,97** (ffill 0) · IMA-B 2006Q1 **1.193,861827** · IPCA 2006Q1 **0,43** por **duas fontes
independentes** (SGS 433 e SIDRA 1737 V63) · IBOV **2006Q4** = **44.473,71** em **28/12** com ffill
**1** (confirmei que **29/12/2006 não existe** na série do IBOV) · meta Selic **2006Q3** = **14,25**
em **30/09/2006**, um **sábado** (confirmei que a data existe na série `corrido`).
**Reconstrução do zero (classe C):** build em scratch com os mesmos insumos →
`alinhado_trimestral.parquet` **byte-idêntico** ao publicado (`ac0d9842…`, 55.813 B); **2 rodadas
seguidas = hashes idênticos** nos 5 artefatos; `fonte_versao` único nas 4.038 linhas e **igual** ao
`versao_build` do relatório; `relatorio.sha256` bate com o Parquet em disco.

## 4. Revisão numérica independente — F-015
Reconstruí por conta própria a grade de apoio `2001Q1..2005Q4` **e** a janela dos 83, e recalculei
**22 colunas** (as 9 pedidas + 13 de controle) de `raw_series` / `data/processed/focus/`:

| Coluna | n comparável | `max|dif|` | padrão de nulos |
|---|---|---|---|
| `ipca_12m` · `ipca_12m_delta` (aceleração) · `selic_meta_fim` · `selic_meta_delta` | 83 cada | **0,0** | idêntico |
| `pib_yoy` (v/583, **sem** ajuste sazonal) · `ibcbr_yoy` · `ibcbr_yoy_trend` · `ibcbr_gap` | 82 · 82 · 67 · 67 | **0,0** | idêntico (1 e 16 nulos) |
| `usdbrl_var_12m` · `usdbrl_var_tri` (por razão) | 83 · 83 | **0,0** | idêntico |
| `cdi_tri` · `selic_over_tri` · `ipca_tri` (produto geométrico, janela semiaberta, completude exigida) | 83 cada | **0,0** | idêntico |
| `curva_real_1a/5a`, `curva_nominal_1a/5a`, `inclinacao_*_5a_1a`, `breakeven_5a`, `ust10_fim`, `vix_fim` | 50..83 | **0,0** | idêntico |
| `focus_ipca_12m` · `focus_pib_ano` · `focus_selic_fim` · `surpresa_ipca/pib/selic` · `juro_real_exante` (Fisher por razão) | 80..83 | **0,0** | idêntico |
| `vertice_extrapolado` (True ⇔ algum dos 4 vértices nulo) | 83 | **0 divergências** (33 True) | — |

`max|dif| = 0,0` é **igualdade exata em float64**, não tolerância. Régua que tive de descobrir
sozinho: as 7 séries da curva e as 2 do Focus **não** estão em `alinhado_trimestral` (F-014 deixa
`source=DERIVADO` fora), então F-015 as alinha internamente e trata linha com `value` nulo como
**ausente** (ffill do último valor real, ≤ 5 d.u.) — é por isso que `curva_nominal_1a` de **2017Q4**
= **6,921301…** vem de **27/12/2017** (28 e 29/12 estão `NaN`). Correto, **não documentado** (P2-4).

**4 canários:** `ipca_12m` 2006Q1 = **5,32** ✔ · `selic_meta_fim` 2008Q4 = **13,75** ✔ ·
`pib_yoy` 2010Q1 = **9,207417484069612** ✔ de **152,53 / 139,67** (`v/583`), com a contraprova de que
o **dessazonalizado `v/584` daria 9,115561** · `focus_ipca_12m` 2026Q3 = **4,19**, recuperado como a
**última coleta de `FOCUS_I12_IPCA_N` até 30/06/2026** ✔.

**Anti-look-ahead:** reconstruí a `date_obs` de **2.515 das 2.548** linhas de procedência (as 33 que
faltam são `vertice_extrapolado = True`, cuja série apontada é o vértice que faltou) → **0 células**
de `T` com `date_obs` posterior ao **fim civil de T**. As com `date_obs > quarter_end` são **230**,
todas de grade `civil`/`corrido` nas 24 datas em que o fim civil passa do último dia útil (D-a).

**Procedência bidirecional (CA-120):** 2.548 linhas · PK `(quarter, column)` sem duplicata · **32**
colunas rastreáveis · **20** séries, todas resolvíveis no catálogo · **0** células não nulas sem
linha · **0** linhas para célula nula · **0** apontando coluna inexistente. As 10 colunas fora da
procedência são `quarter`, `quarter_end`, `is_estimated`, `lag_adjusted`, `fonte_versao` e as **5
100% nulas declaradas** (`ipca_meta`, `ipca_desvio_meta`, `embi_br_fim`, `embi_delta_tri`,
`termos_troca_yoy`). **`is_estimated` True só em `2026Q3`** ✔ · `lag_adjusted = False` nas 83 ·
**unidades** (D-o): 14 `%`, 9 `%a.a.`, 9 `pp`, 2 `bps`, 1 `BRL`, 1 `index`, 1 `bool`, **nenhuma
fração** — coerente com `LIMIAR_SELIC_PP = 0,25` e com o canário 5,32 · **2 rodadas = mesmo hash**.

## 5. Ataque (Validation Mode)
| Vetor | O que fiz | Resultado |
|---|---|---|
| **ciclo Selic ±0,25 pp** | apliquei a regra publicada em 3 trimestres conhecidos | **2008Q4 NÃO é corte: é `NEUTRO`** (Δ = **0,0**; a alta para 13,75 foi **2008Q3**, Δ +1,50 = ALTA; os cortes começam em **2009Q1**, Δ −2,50 = CORTE). **2015Q3 = `ALTA`** (Δ +0,50). **2020Q2 = `CORTE`** (Δ −1,50). Distribuição bate: CORTE 29 · NEUTRO 30 · ALTA 24 |
| **borda do limiar** | procurei `|Δ| = 0,25` exato | **7 trimestres** (2011Q3, 2012Q4, 2014Q2, 2020Q3, **2024Q2**, **2024Q3**, 2026Q1) saem `NEUTRO` pela desigualdade estrita. É **literalmente** o que `metodologia §2` manda (`< −0,25` / `> +0,25`), mas significa que um corte real de 25 bps (2024Q2/Q3) é publicado como "parada", e dos 30 `NEUTRO` só **23** são pausa de fato (Δ = 0). O refinamento `[A]` da metodologia (pausa dentro de ciclo) **não** está implementado — é F-019 → **P1-2** |
| **`ibcbr_yoy` fim de período vs. média (D-q)** | calculei a alternativa (média dos 3 meses do IBC-Br dessaz.) e propaguei até o hiato | `ibcbr_yoy`: **max|dif| 4,2646 pp** (média 0,86) · `ibcbr_gap`: **max|dif| 4,3064 pp** · e **7 dos 67 trimestres TROCAM O SINAL do hiato** (**2013Q2, 2013Q3, 2013Q4, 2020Q1, 2023Q3, 2024Q1, 2025Q2**) → trocam de quadrante na V1. D-q(e) registra a escolha mas diz só "muda os 83 `ibcbr_gap`"; o número que importa é **7 quadrantes** → **P1-1** |
| **régua do Focus** | reconstruí a coleta e o horizonte em 4 trimestres | corte = último d.u. de **T−1** em todos: 2026Q3 ← 30/06/2026 (**4,19**) · 2020Q2 ← 31/03/2020 (3,17; PIB `H0` = −0,9) · **2006Q1 ← 30/12/2005 com `H1` = 3,5** · **2015Q1 ← 31/12/2014 com `H1` = 0,5**. Contraprova da troca: usar `H0` no 1T daria **0,15** (2015Q1), **2,4** (2006Q1) e **2,9221** (2024Q1) contra 0,5 / 3,5 / **1,5198** publicados — a troca H0→H1 é indispensável e está certa |
| **`min_periods = 20` vs. 8** | recalculei as duas | 67 → **79** não nulos (**12 recuperados**, exatamente `2006Q4..2009Q3`, **incluindo toda a crise de 2008**), **max|dif| = 0,0 pp** no trecho comum. O relatório está **exato** |
| **grade de apoio 2001–2005** | construí a minha e usei nos `T−4` | as **913** células (11 séries × 83) do apoio conferidas contra F-014 batem com a minha reconstrução; e 913 + 415 (curva) = **1.328**, o diff publicado. **0 divergências** |
| **`alinhado_trimestral` com uma série a menos** | removi `BCB_SGS_13522` (e depois `BCB_SGS_24364`) do artefato de F-014 e rodei o build em scratch | **NÃO bloqueia — e isso é o achado.** O build **conclui**, publica `ipca_12m` com **83 valores não nulos** e **`max|dif| = 0,0` vs. o baseline**: a reexpressão interna da régua cobre a ausência. O **único** sinal é o contador do relatório caindo de **1.328 → 1.245** células conferidas, que **nenhum teste afirma**. `SERIES_EXIGIDAS` (8 séries) é checado contra **`raw_series`**, nunca contra `alinhado_trimestral` → **P1-3** |
| **célula adulterada no alinhado** | troquei `ipca_12m` 2006Q1 por 99,9 | **`ApoioDivergente` para o build** com a mensagem exata da célula ✔ |
| **CA-068 duplicidade/ordem** | injetei data duplicada com valor divergente, duplicada idêntica e série invertida | divergente e idêntica → **`SerieInconsistente` ruidoso** (barrado pelo `RawSeriesSchema` na entrada da camada, antes do dedup interno); invertida → ordena e produz o **mesmo** número ✔ |
| **CA-122 revisão retroativa (vintage novo)** | republiquei `SIDRA_1620_V583_90707` inteira com `vintage` 2026-10-20 e PIB revisado | **`FrequenciaNaoNativa`** — a guarda de F-013 roda **antes** de `selecionar_vintage`, então o caminho multi-vintage que D-b descreve como projeto ("safras lado a lado") é **inalcançável**. Hoje é latente: medi **1 vintage por série** em `raw_series` → **P2-2** |
| **idempotência / reprodutibilidade** | 2 rodadas em scratch; e reproduzi `versao_build` na mão | 2 rodadas → hashes idênticos ✔. **Mas** `versao_build` hasheia os **bytes crus** dos módulos: reproduzi o publicado `5cd7bdaf…` **só** com os arquivos do disco **em CRLF**; os mesmos blobs de `fcdfaeb` em **LF** dão `54c841bb…` (F-014: disco `ae18c930…` ✔ vs. LF `4741dbc4…`). Não há `.gitattributes` e **2 dos 7 módulos já estão em LF no disco** → **P1-4** |
| **fora de escopo / integridade do acervo** | hashei `data/canonical/` no fim | `alinhado_trimestral.parquet` intacto (`ac0d9842…`, mtime 01:14). **`macro_quarterly.parquet` foi reescrito às 02:11, durante este QA, por outro agente** (junto de `macro_quarterly_asof`, `regimes_v1`, `regime_neighbors*`): `dcded731… → c9bdc3ed…`. Conferi coluna a coluna: as **41 colunas de dado são idênticas**, só `fonte_versao` muda (`5cd7bdaf… → f56e6066…`), porque a árvore está **suja** (+38 linhas não commitadas em `packages/shared/schemas/macro_quarterly.py`, que é módulo de `MODULOS_DO_MACRO`) → **P1-5** |

**Anti-SPEC, item por item dos declarados — nenhuma violação.** **§10.1.1** respeitada (nada
inventado/interpolado: 7 nulos com motivo em F-014, 5 colunas 100% nulas em F-015, `is_estimated` só
em 2026Q3; minha reconstrução prova que **toda** célula de F-014 é observação real e toda derivada é
função de observações reais) · **§10.1.4** (nulo é `NaN` com motivo, nunca 0) · **§10.2.7** com a
ressalva certa (0 células com `date_obs` > fim civil de T, `lag_adjusted=False`, divulgação adiada
para F-018) · **§10.2.13** (`usdbrl_var_*`, `breakeven_5a`, `juro_real_exante` por **razão**) ·
**§10.4.24** (nenhuma coluna fora de `packages/shared/schemas/`) · **§10.4.28** (granularidade nativa
é `raw_series`; as duas tabelas são derivadas, com `date_obs` apontando de volta).

**Teste fake detectado:** nenhum. Os `skip` são condicionais a acervo e declarados; o único
`len(...) > 0` (`test_canonical_alinhamento.py:874`) é sanidade **dentro** de um teste que depois
compara 4.031 células contra a origem; comparações de acervo são `==` sem tolerância; os canários
vêm da fonte, não da fórmula reimplementada.

## 6. Matriz de validação

### F-014 (`alinhado_trimestral`)
| CA | Teste / conferência | Tipo | Status | Evidência (minha) |
|---|---|---|---|---|
| CA-065 | 83 `quarter_end` em dia útil + armadilhas | unit + meu recálculo | ✔ | 83/83, 0 divergências; 24 ≠ fim civil, **2 Sextas-feiras Santas** |
| CA-066 | ffill ≤ 5 d.u. registrado por célula | unit + recálculo | ✔ | 215 células, todas B3, todas 4T, distância **exatamente 1 d.u.** |
| CA-067 | lacuna > 5 → `NULL`, nunca preenchida | unit negativo + acervo | ✔ | 7 nulos (lacunas 65/42 d.u.), `date_obs` nulo, nada herdado |
| CA-068 | data duplicada divergente / fora de ordem | unit negativo + **meu ataque** | ✔ | `SerieInconsistente` ruidoso nas duas duplicatas; invertida → mesmo número |
| CA-061/063 | painel desbalanceado e nulo declarado | contract | ✔ | 80/76/64 trimestres = raw min de ICON/IMOB/IFIX |
| CA-076/077 | séries exigidas / uma fonte por série | contract | ✔ (escopo) | só **9** exigidas — limitação declarada em `F-014.md §6.4` |
| CA-120 | procedência por linha | contract | ✔ | `source`/`vintage`/`collected_at`/`fonte_versao` nas 4.038 linhas, `fonte_versao` único = `versao_build` |
| **diff C** | valor alinhado ≡ bruto em `date_obs` | **minha reimplementação** | ✔ | **4.038/4.038 células, 0 erros**; reconstrução byte-idêntica |

### F-015 (`macro_quarterly` + provenance)
| CA | Teste / conferência | Tipo | Status | Evidência (minha) |
|---|---|---|---|---|
| CA-059 | 83 linhas, `2006Q1..2026Q3`, sem repetir | contract | ✔ | 83 × 42, PK única, `quarter_end` 2006-03-31..2026-09-30 |
| CA-060 | `is_estimated` só em `2026Q3` | unit + acervo | ✔ | 1 True, 82 False |
| CA-061 | coluna sem cobertura → `NULL` | unit negativo | ✔ | 5 colunas 100% nulas, todas com motivo; nulos de `pib_*`/`ibcbr_*` todos 2026Q3 |
| CA-007 | `ibcbr_gap` nos 83 **ou** `is_estimated` | unit | **não fecha — D-m** | 16 nulos; confirmei a aritmética (IBC-Br 2004 → yoy 2005Q1 → mm20 **2009Q4**): **não é satisfazível**; `min_periods=8` recupera 12 com `max|dif| = 0,0` |
| CA-044 | variação por **razão** | unit negativo | ✔ | `usdbrl_var_tri/12m` reproduzidos por razão, `max|dif| = 0,0` |
| CA-070 | acumulação geométrica ≠ soma | unit negativo | ✔ | `cdi_tri`/`ipca_tri`/`selic_over_tri` reproduzidos pelo produto, 83/83 exatos |
| CA-120 | procedência da tabela wide | contract | ✔ | anti-join **0/0** nas duas direções, 2.548 linhas, 32 colunas, 20 séries |
| CA-121 | 2 rodadas, mesmo hash | unit | ✔ **na mesma máquina** | 5 artefatos idênticos em 2 rodadas; **P1-4** para outro ambiente |
| **diff C** | nível ≡ célula de F-014; derivadas por conta independente | **minha reimplementação** | ✔ | **22 colunas, `max|dif| = 0,0`**, padrão de nulos idêntico; 4 canários; apoio 913/1.328 com 0 divergências |
| **anti-look-ahead** | nenhuma célula de T com `date_obs` > fim civil de T | acervo + **minha reconstrução** | ✔ | 0 violações em 2.515 `date_obs` reconstruídas de 2.548 |

**As 5 evidências de dados:** (1) pytest em §1 · (2) F-014 **4.038** linhas, `date_obs`
2006-03-31..2026-09-30; F-015 **83 × 42**, `2006Q1..2026Q3` · (3) nulos: F-014 `value` **0,1734%**,
**0** nas outras 15 colunas; F-015 `ipca_12m`/`selic_meta_fim`/`cdi_tri`/`ipca_tri`/`usdbrl_fim`/
`focus_ipca_12m` **0%**, `pib_yoy` **1,20%**, `ibcbr_gap` **19,28%**, `curva_real_1a` **39,76%** ·
(4) **10 valores** conferidos (6 + 4 canários), recalculados por mim e cruzados com
`raw_series[date_obs]`; **sem rede**, logo a conferência externa é **indireta**: IPCA mar/2006 =
**0,43** por **duas fontes independentes** (SGS 433 e SIDRA 1737 V63) e `pib_yoy` 2010Q1 dos níveis
**152,53/139,67** com a contraprova do `v/584` · (5) diff de classe C em §3-§4, **max|dif| = 0,0** em
4.038 células + 22 colunas; a única divergência de hash está explicada (P1-5) e **não é de dado**.

## 7. Veredito

### **F-014 — APROVADO** · **F-015 — APROVADO** · classe **C** mantida nas duas · CI exigido N2 / rodado **N2 local** (N1 no GitHub)

**F-014:** reconstruí a camada inteira com código independente e não achei **uma única** divergência
numérica em 4.038 células; os 215 ffill, os 7 nulos e os 3 inícios de série são exatamente o que a
ficha declara. **F-015:** 22 colunas recalculadas por conta própria batem com **igualdade exata em
float64**; procedência bidirecional 0/0; anti-look-ahead 0 em 2.515 células reconstruídas; os 4
canários batem, inclusive a contraprova `v/583` × `v/584` e a troca `H0`→`H1`. Nenhum dos 13
critérios de bloqueio do Prompt 3 foi acionado. **ADR-006/ADR-001 em `Proposta` é condição conhecida
e não bloqueia** — mas trava a publicação de **número de regime** (critério 7), e é exatamente aonde
P1-1 e P1-2 precisam chegar antes.

### Pendências
**P1-1 — D-q(e) está registrada mas não quantificada, e o custo é de quadrante.** `ibcbr_yoy` em fim
de período vs. média do trimestre: `max|dif|` **4,31 pp** no hiato e **7 dos 67 trimestres trocam o
sinal** (2013Q2-Q4, 2020Q1, 2023Q3, 2024Q1, 2025Q2). Ação: levar o número ao Edu junto de ADR-001,
**antes** de F-019/F-021 publicarem regime. Não é bug de F-015.

**P1-2 — borda do limiar da Selic esconde o corte de 25 bps.** `|Δ| = 0,25` exato → `NEUTRO` em **7**
trimestres, incluindo **2024Q2 e 2024Q3** (cortes reais). A função é **fiel à `metodologia §2`** e o
refinamento `[A]` (pausa dentro de ciclo) é de F-019 — mas a decisão tem de ser **escolhida** antes de
o rótulo ir ao Comitê, não descoberta depois.

**P1-3 — bug de guarda, ≤ 10 linhas (NÃO corrigi).** `macro_quarterly` aceita **em silêncio** um
`alinhado_trimestral` sem a série de que depende. *Reprodução:* copiar `data/` para scratch, remover
`BCB_SGS_13522` de `{scratch}/data/canonical/alinhado_trimestral.parquet`, `construir(raiz=scratch)`.
*Esperado:* parar (a feature afirma "todo nível é a célula de F-014"). *Obtido:* build conclui,
`ipca_12m` com 83 valores não nulos e `max|dif| = 0,0` vs. baseline; só
`diff_vs_alinhado_trimestral.celulas_conferidas` cai **1.328 → 1.245**, e nada falha. *Caminho:*
exigir `SERIES_EXIGIDAS` presentes **em `alinhado_trimestral`** (hoje só em `raw_series`,
`macro_quarterly.py:1592`), ou afirmar o total de células conferidas por `ORIGENS`.

**P1-4 — `versao_build` depende do fim de linha do checkout, não do commit.** `versao_build`
(`build_raw_series.py:584`) hasheia `read_bytes()`. O `fonte_versao` publicado (`5cd7bdaf…` F-015,
`ae18c930…` F-014) só reproduz com os arquivos **em CRLF**; com os blobs de `fcdfaeb` em LF dá
`54c841bb…` / `4741dbc4…`. Sem `.gitattributes`, **2 dos 7 módulos já estão em LF** no disco. Quebra
o passo **4 do gate da classe D** (`AGENTS.md §14`: dataset congelado por `sha256` + tag git) e
CA-121 entre ambientes. *Caminho (≤ 10 linhas):* normalizar `\r\n` → `\n` antes do hash, ou
`.gitattributes` com `* text eol=lf`. O arquivo é de **F-013** e afeta F-014..F-019 — decisão do
orquestrador.

**P1-5 — `data/canonical/macro_quarterly.parquet` foi reescrito durante este QA** (02:11) pelos
agentes de F-018/F-019, com `fonte_versao` de **árvore suja**: `dcded731… → c9bdc3ed…`
(`versao_build 5cd7bdaf… → f56e6066…`, por +38 linhas não commitadas em
`packages/shared/schemas/macro_quarterly.py`, que é módulo de `MODULOS_DO_MACRO`). Conferi: as **41
colunas de dado são idênticas**, nenhum número mudou — mas o `sha256` de `TODO.md` / `F-015.md §9` já
não é o do disco e `AGENTS.md §13` congela o compartilhado na onda. Ação: rebuild sincronizado de
**árvore limpa** antes de qualquer congelamento. `alinhado_trimestral.parquet` está intacto.

**P2-1 — hashes de `F-014.md §5.5` velhos:** a ficha lista `bb08d473…` / `bf9014a4…`; disco e
relatório têm `ac0d9842…` / `ae18c930…`. A §5.5 explica o mecanismo; a tabela não foi atualizada.

**P2-2 — `selecionar_vintage` é inalcançável.** `validar_frequencia_nativa` (guarda de F-013) roda
antes, então `raw_series` com 2 safras da mesma série levanta `FrequenciaNaoNativa` em vez de escolher
a `revised` — contraria o que **D-b** descreve como projeto. Latente (medi **1 vintage por série**).
*Reprodução:* republicar `SIDRA_1620_V583_90707` inteira com `vintage` 2026-10-20.

**P2-3 — métrica de anti-look-ahead divergiu da ficha.** O relatório publica
`celulas_com_data_medida = 2.548` e `date_obs > quarter_end = 302`; `F-015.md §4` diz **1.937** /
**230** e o §9 afirma que §0-§5 continuam válidos. Minha reconstrução dá **230** (10 colunas × 24
trimestres); os **72** restantes são `surpresa_*` × 24, que o relatório conta pelo insumo macro
enquanto a procedência aponta para o Focus. **Nenhum erro de número** — a ficha ficou atrás.

**P2-4 — tratamento de `value` nulo não documentado.** `raw_series` tem **7.604** linhas com `value`
nulo (curva, `YAHOO_DXY`, 3 do SIDRA); as duas features **pulam** a linha e dão ffill do último valor
real (`alinhamento.py:400`) — correto, e é o que produz `curva_nominal_1a` 2017Q4 de 27/12/2017. Mas
**nenhuma célula de fim de trimestre das 49 séries alinhadas exercita o caminho** (medi **0** casos):
a regra só vive em fixture e em nenhuma das duas fichas. **P2-5 — N2 só existe localmente** e os
**32** testes de acervo pulam no GitHub (§1): dívida já declarada em `TODO.md §6`, repetida aqui
porque é o que separa "verde no CI" de "verde de verdade".

**DECISIONS_LOG consultado:** D-a (fim de período civil), D-b (vintage), D-h (opção (a), 215 ffill),
D-k/D-p (Focus fora de `raw_series`), D-m (CA-007, 16 nulos), D-n (sem 5a−3a), D-o (por cento/pp),
D-q(e) (fim de período no IBC-Br). Nenhum achado acima acusa de bug algo já decidido: P1-1 e P1-2 são
**o número que falta** em decisões registradas.
