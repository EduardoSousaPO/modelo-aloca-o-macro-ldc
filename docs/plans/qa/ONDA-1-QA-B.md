# Onda 1 — QA independente, lote B (F-005, F-006, F-007)

> **Validation Mode de dados** (`AGENTS.md §15`, Prompt 3). Subagente Opus **que não implementou**
> nenhuma das três features. Commit `e215dbf` (base `70b0cb8`), `main`, 2026-10-11. Lote A
> (F-002/003/004/008) em `ONDA-1-QA-A.md`. Toda evidência abaixo foi **produzida por este agente**
> rodando o código do repo — nada copiado de `context/F-00{5,6,7}.md` nem de `modules/`.

## 0. Veredito

| Feature | Veredito | Classe | P0 | P1 | P2 |
|---|---|---|---|---|---|
| **F-005** Tesouro Direto | **MUDANÇAS_SOLICITADAS** | B → B (mantém) | 0 | **1** | 3 |
| **F-006** B3 índices | **APROVADO** | B → B (mantém) | 0 | 0 | 2 |
| **F-007** Yahoo + MSCI + câmbio | **APROVADO** | B → B (mantém) | 0 | 0 | 2 |

Nenhuma das 13 condições de bloqueio do Prompt 3 foi acionada: DoR completa (os `[ ]` restantes são
D6/D12/L1, declarados **não bloqueantes da extração**), nenhum arquivo fora do contrato sem
justificativa registrada, nenhuma Anti-SPEC violada, nenhum dado inventado/interpolado/`0.0` em
lacuna, CI N1 verde, 5 valores conferidos contra a fonte original.

---

## 1. CI rodado por mim (N1 real, `uv run`)

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
48 files already formatted

$ uv run pytest tests/unit -m "not network" -q
535 passed, 15 deselected, 1 xfailed in 6.06s

$ uv run pytest tests/unit/test_extract_{tesouro_direto,b3_indices,yahoo,msci}.py -m network
7 passed, 160 deselected in 7.42s      (td 3 · b3 2 · yahoo 1 · msci 1)
```

- **O `1 xfailed` não é novo:** `test_schemas_smoke.py::test_toda_serie_ok_tem_data_inicio_medido`,
  já em `70b0cb8` (linha 164). Anti-SPEC §10.4.25 (`.skip`/`xfail` sem ADR) **não** violada aqui.
- **Nenhuma dependência nova:** `git diff 70b0cb8..e215dbf -- pyproject.toml uv.lock` = vazio;
  imports de terceiros nos 5 arquivos do lote: só `pandas`.
- **Rede fora do marker: não há.** Reexecutei os 4 arquivos com `socket.socket` e
  `socket.create_connection` trocados por stub que levanta `OSError`: **160 passed** (§10.4.23 ok).

---

## 2. Arquivos alterados vs. permitidos

`git diff 70b0cb8..e215dbf --stat` → 113 arquivos. Recorte do meu lote:

| Arquivo | Feature | Veredito |
|---|---|---|
| `apps/pipeline/extract/tesouro_direto.py` (+769) | F-005 | ✅ no contrato |
| `tests/unit/test_extract_tesouro_direto.py` · `tests/fixtures/tesouro-direto/` (4+README) | F-005 | ✅ (renomeação `tests/contract/`→`tests/unit/` e slug com hífen já sancionados no Feature Contract) |
| `apps/pipeline/extract/b3_indices.py` (+762) · `extract/__init__.py` (+1) | F-006 | ✅ no contrato |
| `tests/unit/test_extract_b3_indices.py` · `tests/fixtures/b3/` (10+README) | F-006 | ✅ |
| `apps/pipeline/extract/{yahoo,msci}.py` (+949/+783) | F-007 | ✅ |
| `apps/pipeline/transform/{__init__,cambio}.py` (+39/+152) | F-007 | ✅ sancionado (D-g) |
| `packages/shared/schemas/series_catalog_data.py` (+39) | F-007 | ✅ sancionado (D-d) |
| `tests/unit/test_extract_{yahoo,msci}.py` · `tests/fixtures/{yahoo,msci}/` | F-007 | ✅ |
| `docs/wiki/modules/{tesouro,b3,internacional}.md` · `context/F-00{5,6,7}.md` | — | ✅ |
| `apps/pipeline/common/{errors,io_layers,__init__}.py` (+11/+25/+7) | compartilhado | ⚠️ **fora** dos 3 contratos, **mas** justificado por D-b (`obtido_em_arquivado`) e D-g (`SerieInconsistente` subiu para `common/errors.py`); organização de código, não toca camada canônica nem credencial → cabe no escape de `AGENTS.md §18` |

**`ACWI_BRL`/`SP500_BRL` é acréscimo puro?** Sim. O hunk do catálogo é `@@ -1387,6 +1387,45 @@`:
**39 linhas, todas `+`**, nenhuma linha existente removida ou alterada. `load_catalog()` devolve
**134** entradas (era 132) e `N_SERIES_ESPERADAS` acompanhou.

**`is_total_return` está correto?** Sim nas duas derivadas: `ACWI_BRL = True` (MSCI **NETR** = *net
total return*) e `SP500_BRL = False` (`^GSPC` é **price return** — o comparável de retorno total para
os EUA é `MSCI_USA_NETR`, como a `obs` da entrada diz). Confere com Anti-SPEC §10.2.12.

**Alteração em schema existente?** Nenhuma. `packages/shared/schemas/raw_series.py` **não aparece no
diff** — `ProcessedSeriesSchema` segue com 8 colunas e PK `(series_id, date, vintage)`. A mudança em
`CONTRACTS.md` é texto (semântica de `vintage` + 132→134), arquivo do orquestrador.

---

## 3. Evidência de dados — reproduzida com o código do repo (4 extratores `--offline`, 22 Parquets)

| Parquet | linhas | min..max `date` | % nulo `value` | PK única | `vintage` |
|---|---|---|---|---|---|
| `tesouro-direto/td_painel` | **886.300** (750 `series_id`) | 2004-12-31 .. 2026-10-09 | 0,000 | ✅ 0 dup | `2026-10-11` uniforme |
| `b3/B3_IBOV,IDIV,SMLL,INDX,IMAT,IEEX,IFNC,UTIL` | 5.147 cada | 2006-01-02 .. 2026-10-09 | 0,00 | ✅ | `2026-10-10` |
| `b3/B3_ICON` | 4.902 | **2006-12-28** .. 2026-10-09 | 0,00 | ✅ | `2026-10-10` |
| `b3/B3_IMOB` | 4.657 | **2007-12-28** .. 2026-10-09 | 0,00 | ✅ | `2026-10-10` |
| `b3/B3_IFIX` | 3.915 | **2010-12-30** .. 2026-10-09 | 0,00 | ✅ | `2026-10-10` |
| `yahoo/YAHOO_GSPC` | 5.729 | 2004-01-02 .. 2026-10-09 | 0,00 | ✅ | `2026-10-11` |
| `yahoo/YAHOO_TNX` · `YAHOO_VIX` · `YAHOO_DXY` | 5.729 · 5.941 · 6.952 | idem | 0,09 · 3,53 · **17,41** | ✅ | `2026-10-11` |
| `yahoo/SP500_BRL` | 5.572 | 2004-01-02 .. 2026-10-09 | 0,00 | ✅ | `2026-10-11` |
| `msci/MSCI_{ACWI,WORLD,USA,EM}_NETR` | 6.726 cada | **2000-12-29** .. 2026-10-09 | 0,00 | ✅ | `2026-10-11` |
| `msci/ACWI_BRL` | 5.719 | 2004-01-02 .. 2026-10-09 | 0,00 | ✅ | `2026-10-11` |

- **`ProcessedSeriesSchema.validate(..., lazy=True)`: 22/22 OK.** `date` monotônica em 22/22;
  **zero** `value == 0` em 22/22 (Anti-SPEC §10.1.4).
- `vintage` **uniforme dentro de cada série** e igual à **data UTC do `obtido_em` do manifesto**
  (D-b): B3 coletado `2026-10-10T23:49Z` → `2026-10-10`; Yahoo/MSCI `2026-10-11T00:14Z` →
  `2026-10-11`. O 1 dia de diferença é a meia-noite UTC no meio da coleta, não bug (ver P2-5).
- `td_painel`: **750 `series_id`**, round-trip `montar_series_id(*decompor_series_id(s)) == s` em
  **750/750**. 8 siglas (`LTN, NTNB, NTNBP, NTNC, NTNF, LFT, EDUCA, RENDA`) × 5 métricas
  (`TAXA_{COMPRA,VENDA}`, `PU_{COMPRA,VENDA,BASE}`). **248 dias úteis distintos em 2006**
  (CA-021 exige ≥ 240) e `min(date) = 2004-12-31` (≤ 2005-01-03).
- **Nenhuma linha antes do início observado** em ICON/IMOB/IFIX (§10.1.1): o primeiro ponto de cada
  um é o ponto-base `1000.0`, e em 2006/2007/2010 há **1 só ponto**.
- **Nenhum `0.0` em feriado**: IBOV não tem linha em 2006-04-14, 2006-09-07, 2006-12-25, 2010-02-15
  nem 2026-01-01. Célula vazia → **linha omitida** (CA-037).
- **Dias sem PTAX saem da série, sem `ffill`** (CA-047): `set(datas MSCI) ∩ set(datas PTAX) ==
  set(datas ACWI_BRL)` é **True** (igualdade exata, não contenção) — 1.007 dias do MSCI sem PTAX,
  **nenhum** deles em `ACWI_BRL`. Idem `^GSPC` → `SP500_BRL` (157 dias fora).

### 3.1 Cinco valores conferidos contra a fonte original

| # | Valor | Obtido no meu Parquet | Na fonte, conferido agora por mim | Fonte |
|---|---|---|---|---|
| 1 | IBOV 2006-02-01 | `38484.84` | `rateValue2 = "38.484,84"` (`day=1`) | `indexStatisticsProxy/.../GetPortfolioDay` ao vivo |
| 2 | `^GSPC` 2006-01-31 | `1280.0799560546875` | `close = 1280.0799560546875` | `chart/v8/^GSPC?interval=1mo` ao vivo |
| 3 | MSCI ACWI NETR 2006-01-31 | `121.38580887703861` | `calc_date 20060131 → level_eod 121.38580887703861` | `app2.msci.com/.../getLevelDataForGraph` ao vivo |
| 4 | NTN-B 15/05/2045, taxa venda 09/10/2026 | `TD_NTNB_20450515_TAXA_VENDA = 6.65` | `Tesouro IPCA+ com Juros Semestrais;15/05/2045;09/10/2026;6,53;**6,65**;4636,15;4573,25;4573,25` | CSV do CKAN arquivado (sha `75d297b48b6a`) |
| 5 | `SP500_BRL` 2006-01-31 | `2836.6571826171876` | `1280.0799560546875 × 2.216` (PTAX venda de `BCB_SGS_1.parquet`) = idêntico bit a bit | derivação própria × F-003 |

Extra: `ACWI_BRL` 2006-01-31 = `268.9909524715176` = `121.38580887703861 × 2.216`, exato. E há
**duas** séries com vencimento 15/05/2045 no CSV (NTN-B e NTN-B Principal, `6,65` e `6,61`) — a
chave `TD_<SIGLA>_…` separa as duas e **não** houve colisão de PK.

### 3.2 Contagens literais dos CAs de F-006

IBOV/2006 = **246** pontos não nulos (CA-034). IFIX 2010 = **1** ponto (30/12 = 1.000,00), 2011 =
**249** (CA-038). ICON 2006 = **1** (28/12 = 1.000,00), 2007 = 245; IMOB 2007 = **1**
(28/12 = 1.000,00), 2008 = 249 (CA-036).

---

## 4. Tentei quebrar (`AGENTS.md §15`)

| Categoria | Cenário que eu rodei | Resultado |
|---|---|---|
| idempotência (hash) | `sha256` dos 22 Parquets → 2 rodadas `--offline` dos 4 extratores → `sha256` de novo | **22/22 byte-idênticos**. Depois de uma 3ª rodada, esta **ao vivo** (Tesouro com 304 real), continuam 22/22 idênticos |
| revisão retroativa (Yahoo não é byte-estável) | `python -m ...yahoo --tickers GSPC --sem-brl` **ao vivo**, 2ª vez no mesmo dia | Levanta `ConteudoDivergente` internamente, reparseia o arquivado, vê que `(date, value)` é idêntica em **5.729** pontos e **mantém o retrato original** (log WARNING; `sha256` do bruto inalterado: `7dc9a82d4304…` antes e depois). **Não** sobrescreve e **não** falha. Série de fato diferente → `raise` (relevanta) |
| fonte vazia / erro com HTTP 200 | 11 fixtures de erro passadas aos parsers reais | `yahoo adjclose≠close (IVV)` → `SerieInconsistente` (symbol trocado) · `yahoo 1 ponto (SMLL.SA)` → `SerieInconsistente` · `^GSPC range=max-1mo` → `SerieInconsistente` (granularidade `3mo` ≠ `1d`) · `404 delisted` → `RespostaDeErroComStatus200` · `b3 corpo vazio` e `b3 HTML` → `RespostaDeErroComStatus200` · `msci vazio (705000)` → `SerieInconsistente` · `msci erro start-date` → `RespostaDeErroComStatus200` · `msci END_OF_MONTH` (310 registros) → `RespostaTruncada` · `td HTML do CKAN` → `FormatoInesperado`. **Nenhum passou** |
| buraco de série | ICON/IMOB/IFIX começando depois de 2006 | Janela própria, zero linha antes do ponto-base, `data_inicio` do catálogo = 2006-12-28 / 2007-12-28 / 2010-12-30 (= o observado). ADR-005 em Proposta não bloqueia extração (DoR diz isso) |
| B3: código inexistente **vs** ano sem série | `XXXX/2006` e `IFIX/2009` ao vivo | A API devolve **a mesma resposta** nos dois: `{"min":null,"max":null,"results":null}`. O extrator resolve isso **fora** do HTTP: o universo vem do catálogo (`--indices XXXX` → `ErroDeExtracao: índice(s) ['XXXX'] não estão no catálogo`, nunca chega à rede) e `results: null` num ano que o catálogo diz ter série → `RespostaTruncada` com a mensagem citando §10.1.1. Ano legítimamente vazio → registrado em `anos_sem_dado`. **Desenho correto** |
| Tesouro 304 real | `python -m ...tesouro_direto` (sem `--offline`) ao vivo | `HTTP 304 — reaproveitando precotaxatesourodireto__2026-10-10.csv (14584922 bytes, nada transferido)`. O teste `@pytest.mark.network` do 304 também passou |
| `.meta.json` lido como dado (D-c) | `arquivos_arquivados()` do Tesouro | Filtra `SUFIXO_MANIFESTO` explicitamente (linha 533), com comentário explicando que hoje `.csv` não casaria mas a regra não tem exceção. B3 não usa glob (nome determinístico `<ano>.json`) |
| unidade e escala | `unit` por série; `"38.484,84"` | `td_painel`: `%a.a.` nas taxas, `BRL` nos PUs; B3/MSCI/Yahoo `index`, `^TNX` `%a.a.` — nenhum `%` onde devia ser fração. `para_float_ptbr` e `para_float_ponto_decimal` separados, cada um levantando na convenção do outro |
| duplicidade/ordem · look-ahead | 22 Parquets | 0 duplicatas em `(series_id, date)`, `date` monotônica em 22/22; guarda de data futura em `_validar`. Look-ahead não se aplica (sem agregação trimestral aqui) |
| encoding | leitores dos 5 arquivos | Único leitor de texto é `pd.read_csv(..., encoding=encoding)` com `CONFIG.encoding = "latin-1"` **explícito** (§10.4.26); fixture sintética de acento nomeada `__sintetico_acento_latin1.csv` |
| teste fake · fora de escopo | leitura dos 4 arquivos de teste + diff completo | **Nenhum teste fake.** A PTAX de teste de CA-047 **varia no tempo** (`2.0 + i/1000`), o que impediria passar usando um câmbio só; tolerância `rel=1e-12`; fixtures são resposta real; caminho de erro com HTTP 200 em 5 fontes. Fora de escopo: só os 3 arquivos de `common/`, justificados (§2) |

---

## 5. Matriz de validação

### F-005 — Tesouro Direto

| CA | Teste | Tipo | Status | Evidência (minha) |
|---|---|---|---|---|
| CA-020 | `test_ca020_*` (8 tipos, vírgula decimal, 0 NaN de parse) | contract | ✅ | 8 siglas no painel; `%nulo` de `value` = **0,000** nas 886.300 linhas |
| CA-021 | `test_network_arquivo_completo_cobre_2006_e_2005` | network | ✅ | **248** dias úteis distintos em 2006; `min(date) = 2004-12-31` |
| CA-022 | `test_ca022_*` + guarda de encoding | unit | ✅ | `read_csv(encoding="latin-1")` explícito (linha 299); fixture de acento passa |
| — | HTML do CKAN / corpo vazio | unit neg. | ✅ | `FormatoInesperado` / `RespostaDeErroComStatus200` rodados por mim |

### F-006 — B3

| CA | Teste | Tipo | Status | Evidência (minha) |
|---|---|---|---|---|
| CA-034 | unpivot IBOV/2006 | contract | ✅ | **246** pontos; 2006-02-01 = `38484.84`; canário conferido **na API viva** |
| CA-035 | `"38.484,84"` → `38484.84` | unit | ✅ | valor exato no Parquet; `para_float_ptbr` levanta em ponto decimal |
| CA-036 | ICON/IMOB só ponto-base | contract | ✅ | ICON 2006 = 1 ponto (1.000,00); IMOB 2007 = 1 ponto (1.000,00); `data_inicio` do catálogo bate |
| CA-037 | célula vazia ≠ `0` | unit neg. | ✅ | **0** valores `== 0` nas 11 séries; 5 feriados testados: nenhuma linha |
| CA-038 | IFIX 2010 base / 2011 = 249 | contract | ✅ | 2010 = 1 ponto (30/12 = 1.000,00); 2011 = **249**; `data_inicio` = 2010-12-30 |
| CA-039 | janela declarada, nada sintetizado | contract | ⚠️ **parcial** | a metade verificável aqui está OK (0 linhas pré-2010-12-30, `data_inicio` no catálogo); "a janela 2011-2026 aparece na tabela/figura" é obrigação de **F-023** |

### F-007 — Yahoo + MSCI + `transform/cambio.py`

| CA | Teste | Tipo | Status | Evidência (minha) |
|---|---|---|---|---|
| CA-045 | UA obrigatório; `period1/period2` em vez de `range` | unit neg. + network | ✅ | fixture real de 429 sem UA + transporte que distingue com/sem UA; `range=max&1mo` → `SerieInconsistente`; teste live traz 5.729 pontos com UA |
| CA-046 | ACWI NETR 31/01/2006 = 121,3858; `data_inicio` 2000-12-29 | contract | ✅ | Parquet `121.38580887703861`; **igual bit a bit** ao `level_eod` da API viva; `min(date) = 2000-12-29` |
| CA-047 | PTAX do mesmo dia útil; `is_total_return` | unit + unit neg. | ✅ | `(datas USD ∩ datas PTAX) == datas BRL`, igualdade exata, 1.007/157 dias fora; `SP500_BRL = GSPC × PTAX` exato; `is_total_return=None` → `SerieInconsistente`; flags no catálogo (`ACWI_BRL` True, `SP500_BRL` False) |

---

## 6. Issues

**P1-1 · F-005 — `--offline` sobre bruto sem manifesto grava `vintage`/`collected_at` do relógio da
rodada, quebrando D-b e a reprodutibilidade byte a byte.** `tesouro_direto.py:701` → `agora =
collected_at or obtido_em_arquivado(bruto.caminho) or datetime.now(tz=UTC)`. O fallback é alcançável
porque `caminho_bruto_mais_recente()` (linha 537) **aceita de propósito**
`data/raw/tesouro-direto/td.csv`, que existe hoje (14.584.922 B) e **não tem manifesto**. Reprodução:

```python
tmp/data/raw/tesouro-direto/td.csv              # cópia do CSV real, SEM .meta.json
td.extrair(offline=True, raiz=tmp, exigir_cobertura=False)
# log → "nenhum precotaxatesourodireto__*.csv arquivado; usando a amostra da pesquisa td.csv"
# vintage → 2026-10-11 · collected_at → 2026-10-11 01:34:59.993450  (relógio, com microssegundos)
```

Efeito: duas execuções `--offline` do **mesmo** bruto produzem Parquets **diferentes** (CA-121 /
`§10.4.22`) e `vintage` deixa de ser a safra do dado. Correção ≤ 10 linhas, **que eu não apliquei**:
recusar (`raise`) bruto sem manifesto em `--offline`, ou derivar `collected_at` do `mtime` — e cobrir
com teste. O padrão `obtido_em_arquivado(...) or datetime.now(tz=UTC)` é **comum aos 8 extratores**
(D-b), mas só F-005 tem caminho que chega nele; vale ao orquestrador decidir se a guarda sobe para
`common/`.

**P2-2 · F-007 — `YAHOO_DXY` leva 1.210 linhas com `value = NULL` (17,41%) e o comentário que as
justifica está factualmente errado.** `yahoo.py:436-437` diz "feriado da praça com timestamp
presente"; medido por mim: **domingo 1.188**, segunda 13, sexta 5, quinta 3, terça 1. Domingo não é
"ausência esperada registrada pelo extrator" no sentido do docstring de `ProcessedSeriesSchema` — é
dia sem sessão, que F-006 na mesma onda **omite** (CA-037). Nada é inventado nem zerado, e `DX-Y.NYB`
é RF-017 (`should`), fora de CA-045..047 — por isso não bloqueia. Caminho: descartar os dias sem
sessão (ou corrigir o comentário e registrar a convenção), antes de F-014.

**P2-3 · F-007 — `YAHOO_GSPC` tem `is_total_return = None` no catálogo, não `False`.** A derivada
`SP500_BRL` declara `False` corretamente, mas a série em USD fica "desconhecida" — e é justamente
por essa flag que Anti-SPEC §10.2.12 funciona. Quem consumir `YAHOO_GSPC` direto em F-016/F-022 não
tem como saber que é price return. Correção: 1 linha no catálogo. (`B3_ICON`/`B3_IMOB` também estão
`None`, mas isso é o gap **G-01**, declarado no Feature Contract de F-006 — não é issue.)

**P2-4 · F-006 — o comando documentado no Feature Contract não existe.** `TODO.md` §F-006 diz
`--codigos IBOV IFIX`; a flag real é `--indices` →
`b3_indices --codigos IBOV --offline` devolve `error: unrecognized arguments`. Correção: 1 palavra no
`TODO.md` (arquivo do orquestrador) ou um alias no parser.

**P2-5 · F-005/F-006/F-007 — `vintage` não é comparável entre features porque é data **UTC** do
fetch.** B3 (`2026-10-10T23:49Z`) e Yahoo/MSCI (`2026-10-11T00:14Z`) foram coletados a 25 min de
distância e ficaram com safras **diferentes**. D-b está cumprida ao pé da letra; falta decidir se a
safra é UTC ou hora local. Vale 1 linha em `DECISIONS_LOG §2.1`.

**P2-6 · F-005 — marker `network` usado para "precisa do bruto local", e um `skip` condicional.**
2 dos 3 testes `@pytest.mark.network` de `test_extract_tesouro_direto.py` (linhas 601 e 626) **não
abrem socket** — leem `data/raw/tesouro-direto/*.csv`. Funciona (fica fora do CI), mas a evidência
de CA-021 fica atrás de um marker que descreve a dependência errada. E a linha 619 (`pytest.skip` se
o manifesto não tiver ETag/Last-Modified) pode apagar em silêncio a única prova viva do 304 — no meu
run não pulou, o manifesto tem ETag `"1791627731.36-14584922"`. Sugestão: marker próprio
(`requires_raw`) e `pytest.fail` em vez de `skip`.

---

## 7. `DECISIONS_LOG` consultado

`§2.1` inteiro antes de acusar qualquer bug: **D-b** (`vintage` = data do `collected_at` do
manifesto) — base do P1-1 e do P2-5; **D-c** (glob filtra `*.meta.json`) — verificado em F-005/F-006;
**D-d** (132 → 134, flag no catálogo) — base do §2; **D-g** (`cambio.py` + `SerieInconsistente` em
`common/errors.py`) — por que 3 arquivos fora dos contratos são aceitáveis; **D-h** (B3 ⊂ ANBIMA em 69
datas, `ffill_dias_uteis = 1` em todo 4T) — vira DoR de F-014, **não** é issue de F-006. `§1`: a
substituição que ADR-004 propõe é do item **A6** (ETTJ → interpolação do Tesouro, F-016); **F-005
entrega o item A5, pedido nominalmente no e-mail** — não é troca de fonte, não dispara §10.3.19.
ADR-004/005 seguem em **Proposta**: pela DoR dos dois itens isso **não bloqueia a extração**; bloqueia
a publicação (`AGENTS.md §14` passo 2), que é F-031.

*QA independente, 2026-10-11. Nenhum arquivo de código, teste ou fixture foi alterado por este
agente; `data/processed/` foi apenas regravado pelas rodadas de reprodução, byte-idêntico.*
