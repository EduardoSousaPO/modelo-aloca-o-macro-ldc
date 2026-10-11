# QA independente — Onda 1, lote A (F-002, F-003, F-004, F-008)

**Agente:** subagente de QA Opus, Validation Mode de dados (`AGENTS.md §14/§15`, Prompt 3)
**Data:** 2026-10-11 · **Commit sob revisão:** `e215dbf` (`main`) · **Base:** `70b0cb8`
**Eu não implementei nada.** Todo número abaixo foi recalculado por **código meu** (scripts no scratchpad)
ou medido em **requisição minha** à fonte viva. Lote B e F-013 são de outros agentes.

> **Veredito:** F-002 **APROVADO** · F-003 **MUDANÇAS_SOLICITADAS (P1)** ·
> F-004 **MUDANÇAS_SOLICITADAS (P1 — ação do humano)** · F-008 **APROVADO**.
> **P0 = nenhum; merge não está bloqueado.** Os P1 bloqueiam o **consumo pela Onda 2**.

## 1. CI N1 real, rodado por mim

```
$ uv run ruff check .           -> All checks passed!              (exit 0)
$ uv run ruff format --check .  -> 48 files already formatted       (exit 0)
$ uv run pytest tests/unit -m "not network"
   535 passed, 15 deselected, 1 xfailed, 1 warning in 5.86s        (exit 0)
$ uv run pytest tests/unit/test_extract_{anbima_s3,bcb_sgs,ibge_sidra,calendario_anbima}.py -m network
   7 passed, 177 deselected (1 ANBIMA + 2 SGS + 2 SIDRA + 2 calendario)  37.82s  (exit 0)
```

**Anti-SPEC §10.4.23 verificada por execução, não por leitura:** rodei a suíte com um plugin meu que
monkeypatcha `socket.socket.connect`/`create_connection` para levantar → `535 passed, 15 deselected,
1 xfailed`. **Nenhum teste sem o marker abre socket.**

**`1 xfailed` não é desta onda:** `test_toda_serie_ok_tem_data_inicio_medido`
(`test_schemas_smoke.py:170`) já existia em `70b0cb8` (linha 164), de `373267c`. **Nenhum `.skip`/`xfail`
novo** nos 4 arquivos do lote; os `pytest.skip` novos são condicionais (§4.6).

## 2. Arquivos alterados vs. permitidos

`git show --stat e215dbf` → **113 arquivos, +26.244 / −684**. `grep -E 'data/canonical|SPEC\.md|PRD\.md|ESCOPO-EMAIL|docs/research/'`
sobre `--name-only`: **nada**. `git ls-files data/` → só os 3 `.gitkeep`.

**Schemas existentes:** `git diff 70b0cb8..e215dbf -- packages/shared/schemas/` → **+114 / −0**, ou seja
**só acréscimo**: `calendario.py` (novo), 2 exports em `__init__.py`, 39 linhas no fim de
`series_catalog_data.py` (`ACWI_BRL`/`SP500_BRL`, D-d). **`raw_series.py` NÃO foi tocado** (último commit
que o altera é `5a36035`) → `ProcessedSeriesSchema` segue o contrato da Onda 0. ✅ **Dependência nova:**
`git diff … -- pyproject.toml uv.lock` → **vazio** (§10.4.25 ✅; D-f existe para não exigir `xlrd`).

**Desvios declarados — aceitáveis?** Sim, com a ressalva P2-5: (a) `tests/unit/test_extract_*.py` +
`tests/fixtures/<fonte-com-hifen>/` no lugar de `tests/contract/` — nota nos 4 blocos do `TODO.md`, não
muda CA; (b) F-003 sem `transform/acumulacao.py` (→ F-017), declarado, e eu reproduzi CA-014/015 sobre o
Parquet; (c) F-008 em `extract/` **e rota HTML no lugar do `.xls` da SPEC RF-018** — ratificado em
`DECISIONS_LOG §2.1 D-f`; é o único desvio que troca a **fonte efetiva**; (d)
`packages/shared/schemas/calendario.py` fora do contrato original, mas é acréscimo de contrato (§18).

**Contexto:** o tree sujou durante a auditoria com o trabalho em voo do terceiro agente
(`?? apps/pipeline/canonical/`, ` M series_catalog.py`) — **meu veredito é sobre `e215dbf`**; registro que F-013 altera um schema **existente**, o que é do QA dele.

## 3. Evidências reproduzidas com código meu

### 3.1 Varredura dos 31 Parquets (`anbima-ima` 9 · `sgs` 15 · `sidra` 6 · `calendario` 1)

As 8 colunas de `ProcessedSeriesSchema` em **30/30** séries; **PK `(series_id,date)` única em 30/30**; `date` monotônica em 30/30; 1 só `freq`/`unit`/`source` por série;
`vintage` **datetime sem hora e constante na série** em 30/30; **M/Q em fim de período civil em 30/30** (D-a/D-b ✅).

| fonte | séries | linhas | janela | % nulos em `value` |
|---|---|---|---|---|
| `anbima-ima` | 9 | 5.407–6.700 | 2000-02-01 → 2026-10-09 | **0,00 em todas** |
| `sgs` | 15 | 90–8.319 (44.447 total) | 2004-01-01 → 2026-10-10 | **0,00 em todas** |
| `sidra` | 6 | 122–562 | 1979-12-31 → 2026-09-30 | 2,14 / 0,18 / 0,82 nas 3 com nulo |

Os nulos do SIDRA estão **todos fora da janela**: `V2265` 12 em 1979-12..1980-11, `V63` 1 em 1979-12-31, `5932` 1 em 1996T1 (`"..."` real).
**`nulos >= 2006-01-01 = 0` nas três** — ausência da fonte como `None`, nunca `0` (§10.1.4 ✅).

### 3.2 Canários — conferidos por mim na **fonte viva** e no Parquet

**Fonte viva ≡ Parquet em 9 canários — bateu em todos:** IMA-B 16/09/2003 `723.070317` (CA-031; o
arquivo que baixei agora tem magic bytes `PK` (XLSX), 393.685 B, última data 2026-10-09) · IPCA SGS 433
set/2026 `0.82` **e** SIDRA v63 202609 `0.82` (CA-002) · IBC-Br 24364 jan/2006 `79.44731`, com catálogo
`data_inicio="2003-01-01"` (CA-006) · Selic over 11 03/01/2005 `0.064826` (CA-012) · PTAX 1 09/10/2026
`4.9892` (CA-043) · PIB 1621 2006T1/T2/T3 `131.74`/`132.14`/`134.36`, 1ª linha `V='Valor'` (CA-008) ·
2006 = **249 d.u.** recontados por mim de `fer_nacionais/2006.asp` (CA-051) · 12/10/2026 na lista da
fonte como `Nossa Sr.a Aparecida` e `dia_util=False` no Parquet. **Recalculado por mim do Parquet:**
CDI 2006 = **15,027140 %** em **249 obs** (`prod(1+v/100)`, CA-014); produto dos 4 trimestres
`1.150271403941` vs anual `1.150271403941`, dif **4,4e-16** (CA-015).

**Reconciliação por `date`, merge direto nos Parquets (código meu):**
IPCA `SGS 433 × SIDRA 1737 v63` → **273 meses, `max|dif| = 0.0`**;
PIB `SGS 22109 × SIDRA 1621 v584` → **90 trimestres, `max|dif| = 0.0`**. ✅

**Além do CA:** recontei d.u. do calendário × nº de obs do CDI (SGS 12) **ano a ano, 2006→2025** —
**casam nos 20 anos** (249, 250, 254, 250, 251, 251, 251, 253, 253, 250, 251, 249, 250, 253, 251, 251,
251, 249, 253, 252).

## 4. Tentativas de quebra (Validation Mode §15)

### 4.1 Idempotência — passou

`--offline` nos 4 módulos, **2 rodadas**, `sha256` dos 31 Parquets: `diff h0 h1` **idêntico**, `diff h1 h2`
**idêntico** — byte a byte, inclusive contra o estado que o implementador deixou (RF-048 ✅; `vintage` sai
do manifesto, não do relógio, e é o que faz isso valer).

### 4.2 Manifesto como dado — não acontece, e o filtro é load-bearing

Provei que o filtro **importa**: em `data/raw/sidra/`, `sorted(glob('t1737_v63__*.json'), reverse=True)[0]`
é **`…json.meta.json`** sem o filtro e **`…json`** com ele. Os 3 globs (`anbima_s3:452`, `ibge_sidra:714`,
`calendario_anbima:735`) filtram `SUFIXO_MANIFESTO` (D-c ✅); `bcb_sgs` não usa glob. E, se o manifesto
chegasse ao parser: *"esperado array JSON, veio objeto com chaves ['bytes','obtido_em','origem','sha256']"*.

### 4.3 Payloads adversariais meus — todos recusados, nada gravado

**SGS:** `{"error": …}` 200, XHTML 200 (o caso real de CA-003), corpo vazio e array truncado →
`RespostaDeErroComStatus200` nos 4. **ANBIMA:** `AccessDenied` XML, HTML e vazio → `FormatoInesperado …
esperado um de [xlsx]`; fixture recortada com o piso de produção → `RespostaTruncada: 80 registros,
mínimo 5795`. **SIDRA:** `erro-html-404` e `erro-400` recusados; array **sem** cabeçalho →
`RespostaSidraInconsistente: a 1ª linha deveria ser o cabeçalho (V='Valor'), veio V='0.82'`. **F-008:**
404 real servido como ano válido → `nenhuma <table class='interna'>`; planilha BIFF → `magic 'xls_biff',
esperado [html]`; página de 2026 rotulada 2025 → `traz data 2026-01-01`; dia da semana que **eu**
adulterei → `2026-02-16 é SEGUNDA-FEIRA … a página diz 'QUARTA-FEIRA'`. `git status` depois: nada
gravado em `data/processed/`. **200 com corpo de erro tem guarda nos 4 extratores**; nenhum leitor em
`apps/` sem `encoding=` (o manifesto, `io_layers.py:274`, declara `utf-8`) — §10.4.26 ✅.

### 4.4 **Mês parcial do SGS — BUG LATENTE (P1-1), reproduzido**

Resposta à pergunta do briefing: **descartado, mas por acidente**. O bruto de 4390 tem **274** obs e a
última é **`{'data': '01/10/2026', 'valor': '0.36'}`** — outubro **aberto**. O Parquet tem 273 linhas e
termina em `2026-09-30`, **certo** — mas o descarte não vem de guarda de período parcial: vem de
`fim_do_periodo(2026-10-01, M) = 2026-10-31` ficar `> date.today()` e cair em `truncar_em`. Reprodução
minha, com as funções do próprio módulo:

```
bruto 4390: 274 obs; ultima = {'data': '01/10/2026', 'valor': '0.36'}
quadro apos fim_do_periodo:  2026-09-30 -> 1.08 | 2026-10-31 -> 0.36
--fim 2026-10-11: truncadas=1  ultima=2026-09-30 valor=1.08   <- hoje, certo
--fim 2026-10-31: truncadas=0  ultima=2026-10-31 valor=0.36   <- PARCIAL COMO MES FECHADO
--fim 2026-11-30: truncadas=0  ultima=2026-10-31 valor=0.36
```

Basta `--fim <último dia civil do mês>` — ou **rodar o extrator no último dia civil do mês, sem flag** —
para gravar acumulação parcial como período fechado. Varredura minha de todos os brutos M/Q: afeta
**2 séries**, `4390` (`0.36`) e `4189` (`13.65`). **SIDRA não é afetado** (só publica período fechado:
`t1737` 202609, `t1621`/`t5932` 2026T2). Risco de Anti-SPEC §10.1.1. **Não corrigi** (≤ 10 linhas).

### 4.5 Série 432 (calendário corrido) com fins de semana — certo no bruto, risco no consumo (P1-2)

Medido: **8.319 linhas, 2.377 em fim de semana (28,6 %)**, `freq='D'`, `max=2026-10-10`. **Para a camada
processada está certo** — granularidade nativa é a verdade (§10.4.28) e o achado está em `DECISIONS_LOG
§2.2`. O problema é o **consumo**: a distinção vive só em `SERIES_DIARIAS_DE_CALENDARIO = {432}` dentro de
`bcb_sgs.py`, e o catálogo (`series_catalog_data.py:272`) declara `freq="D"` com um `obs` que fala **só da
data futura**. F-014/F-017 leem catálogo e Parquet, não a constante — contagem/média sobre `freq='D'` sai enviesada em 28,6 % dos pontos.

### 4.6 As duas varreduras da consolidação **pulam no CI** (P1-4)

`test_contract_sgs_sidra.py` e `test_processed_layer_conventions.py` são a **única** trava regressível de
D-a, D-b, PK única e da reconciliação SGS×SIDRA. Rodei-as num `git archive e215dbf` extraído em `tmp`
(= o que `actions/checkout` entrega, e `data/` não está no git):

```
9 skipped — "data/processed/ tem 0 Parquet(s) de série" / "falta sgs/BCB_SGS_433.parquet ou sidra/..."
```

O job `n1-basic` faz `checkout` + `pip install` + `pytest tests/unit -m "not network"`, **sem passo que
reconstrua `data/`** — e `data/raw/` também não está no git, então nem `--offline` salvaria. **A evidência
central da consolidação não é verificada por nenhum CI.** Hoje está certa (§3), mas D-a/D-b regridem verde.

### 4.7 Rótulo `IMA - B` vs `IMA-B` — resolvido, e a fonte viva confirma que o caso é real

O arquivo que baixei agora traz **os dois**: `rotulos distintos: ['IMA - B', 'IMA-B']`. `normalizar_rotulo`
colapsa (`'IMA - B'`, `' ima  -  b '`, `'IMA  -B'` → `'IMA-B'`) e os 9 Parquets têm **1 `series_id` cada**
(vem do SLUG do catálogo, não do rótulo). CA-032 ✅.

## 5. Matriz `CA | teste | tipo | status | evidência`

### F-002 — ANBIMA S3 (RF-011)

| CA | teste | tipo | status | evidência minha |
|---|---|---|---|---|
| CA-030 | magic `PK` → openpyxl, nunca xlrd | contract | ✅ | fonte viva `magic=b'PK\x03\x04'`, 393.685 B; XML/HTML/vazio → `FormatoInesperado … [xlsx]` |
| CA-031 | canário IMA-B 16/09/2003 | contract | ✅ | `723.070317` na fonte **e** no Parquet; última data `2026-10-09` ≥ 2026-10-09 |
| CA-032 | `IMA-B` ≡ `IMA - B` → 1 `asset_id` | unit | ✅ | fonte viva tem os **dois** rótulos; 1 `series_id` por Parquet em 9/9 (§4.7) |
| CA-033 | 8 índices com `data_inicio <= 2006-01-02` | unit | ✅ | IRFM 2000-02-01 · IRFM1/1MAIS 2000-12-01 · IMAS 2001-12-03 · IMAGERAL 2001-12-04 · IMAB/5/5MAIS 2003-09-16 |

### F-003 — BCB SGS (RF-001/003/005/006/015)

| CA | teste | tipo | status | evidência minha |
|---|---|---|---|---|
| CA-001 | 433 ≥ 249 meses contíguos | unit | ✅ | 273 obs 2004-01-31→2026-09-30, 0 % nulos, PK única, `BCB_SGS`/`M`/`%` |
| CA-002 | 433 ≡ SIDRA v63 | contract | ✅ | **273 meses, `max|dif| = 0.0`**; set/2026 `0.82` nas duas fontes vivas |
| CA-003 | 200 com corpo de erro → erro, nada gravado | contract | ✅ | 5 payloads meus recusados (§4.3); `git status` limpo |
| CA-006 | IBC-Br jan/2006 + `data_inicio` 2003 | contract | ✅ | `79.44731` fonte+Parquet; catálogo `2003-01-01` |
| CA-011 | fatiamento ≤ 10 anos, sem dup/lacuna | integration | ✅ | teste `-m network` verde; Parquet 11: 5.719 linhas, PK única, ordenada |
| CA-012 · CA-043 | canários Selic over 03/01/2005 e PTAX 09/10/2026 | contract | ✅ | `0.064826` e `4.9892`, fonte+Parquet; as duas séries fatiadas (5.719 linhas cada) |
| CA-013 | 432 truncada em `today` | unit | ✅ | fixture termina `04/11/2026`; **0 linhas `date > 2026-10-11`** em qualquer Parquet do SGS |
| CA-014 · CA-015 | CDI 2006 = 15,0271 %; 4 trimestres ≡ ano | unit | ✅ | **15,027140 %** em 249 obs e dif **4,4e-16** entre o produto dos trimestres e o fator anual — recalculados por mim |
| CA-016 | teste negativo do `/100` | unit neg. | ✅ | `test_ca016_…:478 assert _fator_acumulado(..., dividir_por_100=False) > 1e5` |
| — | período parcial entra como fechado | — | ❌ **P1-1** | §4.4, reproduzido |
| — | 432 calendário corrido sem flag no catálogo | — | ⚠️ **P1-2** | §4.5 |

⚪ **CA-007, CA-010 e CA-044 são de transformação/canônico** (F-016/F-017), declarados fora do escopo nos Feature Contracts — não os avaliei.

### F-004 — IBGE SIDRA (RF-002/004)

| CA | teste | tipo | status | evidência minha |
|---|---|---|---|---|
| CA-004 cabeçalho | 1ª linha é cabeçalho | unit | ✅ | fonte viva `d[0]['V'] == 'Valor'`; array sem cabeçalho → `RespostaSidraInconsistente` |
| CA-004 `unit`/encoding | — | unit | ✅ | `V2266` → `unit='index'`, 562 obs; nenhum leitor sem `encoding=` |
| CA-004 monotonia ≥ 99 % | — | unit | ❌ **não fecha na SPEC** | medido por mim: **0,9626** no histórico, **0,9435** desde 2006 (21 meses de deflação real). Código usa `MONOTONIA_MINIMA = 0,90` com `assert fracao < 0.99` no teste → D-e |
| CA-005 tolerância ≤ 1e-6 | — | unit | ❌ **não fecha na SPEC** | medido por mim: **3,5233e-06** = **3,52e-04 pp** em 82 trimestres (pior caso 2006T4); teto analítico do arredondamento de 2 casas do IBGE 3,97e-04 pp. Código usa 1e-3 pp → D-e |
| CA-008 | PIB 2006T1/T2/T3 | contract | ✅ | `131.74`/`132.14`/`134.36` fonte+Parquet |
| CA-009 | `t/1621` ≡ SGS 22109 | contract | ✅ | **90 trimestres, `max|dif| = 0.0`** |

### F-008 — Calendário ANBIMA (RF-018)

| CA | teste | tipo | status | evidência minha |
|---|---|---|---|---|
| CA-051 | 2006 = 249 d.u., coerente com o CDI | unit | ✅✅ | 249 no Parquet; **249 recontados por mim da página da fonte**; = 249 obs do SGS 12; **e casa nos 20 anos 2006→2025** |
| CA-052 | fim de trimestre em feriado/fds → d.u. anterior | unit | ✅ | recomputado por mim: 2006T3 `09-29`, 2006T4 `12-29`, 2024T1 `03-28`, 2025T4 `12-31`, 2025T1 `03-31` |
| CA-052 | datas-armadilha | unit | ✅ | Carnaval 27–28/02/2006, Paixão 14/04, Corpus 15/06 → `dia_util=False` com nome; 31/12/2025 não é feriado ANBIMA e o SGS 12 tem obs nesse dia |
| — | grade, PK, schema, fonte viva | unit+contract | ✅ | 10.957 dias civis 2001→2030, 7.530 d.u., 367 feriados, PK única; 3 `dataframe_check` (sem lacuna, feriado ≠ d.u., fds ≠ d.u.); `2006.asp`/`2026.asp` HTTP 200 com 12 e 13 feriados |

## 6. Veredito e correções

| Feature | Veredito | Por quê |
|---|---|---|
| **F-002** | **APROVADO** | 4/4 CAs com evidência minha (fonte viva + Parquet). Nenhuma tentativa de quebra passou. Idempotente byte a byte. |
| **F-003** | **MUDANÇAS_SOLICITADAS** | 12/12 CAs no escopo ✅ e nenhum número errado no disco **hoje** — mas P1-1 é caminho reproduzível para gravar período parcial como fechado e P1-2 deixa a Onda 2 sem distinguir a 432. **Não bloqueia merge.** |
| **F-004** | **MUDANÇAS_SOLICITADAS** | **ação do humano.** 2 dos 5 CAs (CA-004 monotonia, CA-005 tolerância) **medidamente não fecham** com o limiar da SPEC. O implementador fez o certo: mediu, registrou D-e, travou o número no teste e **não editou a SPEC** (§8). `AGENTS.md §15.9` me proíbe `APROVADO` com CA que não fecha. |
| **F-008** | **APROVADO** | O lote mais bem fechado: 249 d.u. de 2006 por **3** caminhos independentes e coerência calendário × CDI nos 20 anos; 4 payloads adversariais recusados com mensagem específica. |

**P0 (bloqueia merge): nenhum.**

**P1 — antes de a Onda 2 (F-013/F-014/F-017) consumir:**

1. **F-003 · guarda de período parcial** (§4.4) — em série `M`/`Q`, recusar observação cujo período
   ainda não encerrou em `collected_at`, contando e logando como `truncar_em` já faz. ≤ 10 linhas,
   **não corrigi**: reportado com reprodução.
2. **F-003 · 432 é calendário corrido e nada no dado diz isso** (§4.5) — levar
   `SERIES_DIARIAS_DE_CALENDARIO` para o **catálogo** antes de F-014 alinhar e F-017 contar dias.
3. **F-004 · ratificação de D-e pelo Edu** — ou a SPEC CA-004/CA-005 passa a 90 % e 1e-3 pp, ou a
   implementação muda. O agente **não pode editar a SPEC** (§8); item já aberto em `TODO.md §4`.
4. **CI · a evidência da consolidação pula** (§4.6) — job N2 que monte uma `processed` mínima **das
   fixtures** (que estão no git) e rode as duas varreduras de verdade.

**P2:**

5. **F-008/D-f entra na comunicação escrita de substituições** (RF-045 / F-032) — a SPEC RF-018 nomeia
   `feriados_nacionais.xls` e o dado vem de `fer_nacionais/<ano>.asp`. Mesmo domínio e o `.xls` fica
   arquivado como fonte de registro (é troca de **endpoint**), mas §10.3.19 não distingue.
6. **`dias_uteis_anbima.parquet` sem coluna de proveniência** — deliberado (Parquet byte-idêntico), com
   a proveniência nos `.meta.json`; documentar em `modules/calendario.md`.
7. **Nulos pré-2006 do SIDRA** (12 / 1 / 1) — corretos e fora da janela; o canônico precisa cortar em
   2006 **antes** de qualquer `ffill`.
8. **`xfail` de `test_toda_serie_ok_tem_data_inicio_medido`** segue aberto (C-2 da auditoria, 17 séries
   `ok` sem `data_inicio`) — dívida viva no CI N1, não desta onda.

*Lote A. Não editei nada fora deste arquivo; os scripts da auditoria ficaram no scratchpad da sessão e todos os números acima são reproduzíveis com `uv run`.*
