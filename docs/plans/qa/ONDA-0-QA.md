# QA independente — Onda 0 (F-001 + F-009)

> **Prompt 3 — Validation Mode de dados** (`AGENTS.md §14-§15`, `CLAUDE.md §9`). Subagente Opus de QA,
> **distinto** de quem implementou. Toda evidência abaixo foi **produzida por mim**, não copiada do
> relatório do implementador. Árvore de trabalho, `main`, nada commitado. **Data:** 2026-10-10.

## 0. Veredito

| Feature | Veredito | Bloqueador |
|---|---|---|
| **F-001** infra de extração | **MUDANÇAS_SOLICITADAS** | **QA-01 (P0)** — `para_float_ptbr` com entrada numérica nativa produz erro de escala 1000× **silencioso** |
| **F-009** job diário ANBIMA | **APROVADO** | nenhum P0/P1. 3 CAs reproduzidos com evidência própria, janela rolante **100% coberta**, idempotência real confirmada ao vivo |

## 1. CI N1 real (saída colada)

```
$ uv run ruff check .          →  All checks passed!
$ uv run ruff format --check . →  26 files already formatted
$ uv run pytest tests/unit -m "not network"
                               →  161 passed, 1 deselected, 1 xfailed in 1.18s
```

Coleta: `test_common_parsing` 49 · `test_common_http` 32 · `test_anbima_daily` 30 (1 `network`,
deselecionado) · `test_common_io_layers` 27 · `test_canonical_guards` 12 · `test_schemas_smoke` 12.
Confere com o auto-relato (108 de F-001, 29+1 de F-009). O único `xfail` é **pré-existente e commitado**
(`373267c`, `test_schemas_smoke.py:164`, motivo declarado): **nenhum `.skip`/`xfail` novo**.
**CA-123 verificado à parte:** rodei a suíte N1 com `socket.socket.connect`, `connect_ex`,
`create_connection` e `getaddrinfo` substituídos por função que levanta → `161 passed`. Zero rede no CI.

## 2. Arquivos alterados vs. Feature Contract

Só `apps/pipeline/{common,jobs}/`, `apps/{,pipeline/}__init__.py`, `tests/unit/test_{common_*,anbima_daily}.py`,
`tests/fixtures/{common,anbima-ms,anbima-ettj}/`, `docs/wiki/context/F-00{1,9}.md`,
`docs/wiki/runbooks/job-diario-anbima.md`, `pyproject.toml`, `uv.lock`. **Intactos** (`git status` vazio):
`docs/specs/`, `docs/product/`, `docs/research/`, `packages/`, `.github/`, `tests/conftest.py`.

| Desvio | Aceitável? | Por quê |
|---|---|---|
| F-001 em `common/` em vez de `extract/{http,parsing,io_layers}.py` | **Sim** | §18: justificativa puramente operacional — não toca camada canônica, credencial, escopo nem entregável. Mantém `extract/` livre e **disjunto** para F-002…F-008 (`AGENTS.md §13`) e é o caminho que o `# TODO(F-001)` de F-009 já assume. Ação: 1 linha no Feature Contract. |
| `errors.py`, `logging_setup.py`, `__init__.py` extras | **Sim** | coesos com o escopo "guardas"; `errors.py` é o que faz "levantar ruidosamente" existir. |
| Testes `test_common_*.py` em vez de `test_http.py`/`test_parsing.py` | **Sim** | mesmo escopo; `test_common_io_layers.py` cobre `io_layers.py`, que o contrato listou sem teste. |
| **F-001 alterou `pyproject.toml`** (fora da lista; Context Pack de F-009 o declara "do orquestrador") | **Sim, mas não declarado** | diff de 4 linhas: `packages=["packages"]` → `["packages","apps"]` + comentário. **Sem isso o `pip install -e .` do CI não embarca `apps` e o import quebra.** Nenhuma dependência nova. → P2: registrar no contrato. |
| F-009 em `jobs/anbima_daily.py` em vez de `extract/anbima_diario.py` | **Sim** | é **job de arquivamento**, não extrator para o canônico (o contrato exclui o uso canônico). Libera `extract/`. |
| Fixtures `anbima-ms/`+`anbima-ettj/` (6 arquivos) em vez de `anbima/ms261008.txt`+`cz.csv` | **Sim, e melhor** | são **duas** fontes; CA-124 pede fixture por fonte e há **3 de caminho de erro**. O contrato subdimensionou. |
| Runbook `job-diario-anbima.md` em vez de `arquivamento-diario-anbima.md` | **Sim** | cosmético. |
| Contrato diz `Msec_txt.txt`; implementação usa `ms{AAMMDD}.txt` | **Sim** | URL datada é melhor: permite a guarda de eco de data. A DoR já confirmou `ms{AAMMDD}.txt`. |

Nenhum arquivo proibido tocado. **Nenhuma dependência nova** (diff do `pyproject.toml` conferido linha a linha).

## 3. Evidências de dados reproduzidas por mim

### F-009 — `data/raw/anbima-ms/` e `data/raw/anbima-ettj/`

| Medida | `anbima-ms` | `anbima-ettj` |
|---|---|---|
| dados / manifests | **21 / 21** | **20 / 20** |
| `data_ref` min → max | **2026-09-11 → 2026-10-09** | **2026-09-14 → 2026-10-09** |
| datas distintas / lacunas | 21 / **0** | 20 / **0** |
| `sha256` manifesto × disco · `bytes` × tamanho real | **21/21 OK**, 0 divergem | **20/20 OK**, 0 divergem |
| arquivo sem manifesto | 0 | 0 |

**Cobertura total da janela rolante.** `research/fontes-de-dados.md §A4.2` mediu que o `ms*.txt` responde
200 exatamente de `ms260911` a `ms261009` (404 antes), e §A5 que o `CZ-down.asp` começa em **14/09/2026**.
O job arquivou **exatamente** esses dois intervalos, inteiros: nada do que existia na fonte foi perdido.

**3 valores conferidos contra a fonte original** — `GET .../merc-sec/arqs/ms261009.txt` com UA de browser,
HTTP 200, 6.683 B, baixado por mim agora:

| Título | Vencimento | Tx. Indicativas | PU | Vivo = arquivado? |
|---|---|---|---|---|
| LTN | 2027-04-01 | `13,0937` | `944,93376` | **sim** |
| LFT | 2031-09-01 | `0,0905` | `19970,166022` | **sim** |
| NTN-B | 2035-05-15 | `6,6922` | `4682,087021` | **sim** |

Mais forte que 3 valores: `diff` do corpo vivo contra `data/raw/anbima-ms/ms_261009.txt` → **byte a byte
idêntico**, `sha256 = 82c4353…13fe9a0` (= o do manifesto). 50 registros, 5 títulos (LFT 18, LTN 11,
NTN-B 14, NTN-C 1, NTN-F 6), `Data Referencia` única `20261009` — bate com o `detalhe` do manifesto.
As fixtures `ms__2026-10-09.txt` e `cz__2026-10-09.csv` são **byte-idênticas** aos arquivos reais: fixture
real, não sintética.

### F-001 — infra sobre `data/raw/anbima-ima/IMAB.xls`

```
detectar_formato(IMAB.xls) -> xlsx            (extensão mente; exigir_formato(XLSX) passa)
LINHAS DE DADO = 5795                          (shape bruto 5796x10, 1 linha de cabeçalho)
DATA MIN = 2003-09-16    DATA MAX = 2026-10-09
1ª linha: índice='IMA-B' data=2003-09-16 valor=723.070317   <- valor-canário CA-031 confirmado
última  : data=2026-10-09 valor=12656.536776
nulos: data=0 (0,00%)  valor=0 (0,00%)   duplicadas=0   ordem crescente=True
```

CA-035: `para_float_ptbr("38.484,84") == 38484.84` **True** · `para_float_ptbr("0.82")` **levanta
`NumeroNaoReconhecido`** · `para_float_ponto_decimal("0.82") == 0.82` · `"6.930"` → `6930.0` ·
`""`/`"-"`/`"ND"` → `None` (nunca `0`) · `normalizar_rotulo("IMA - B") == normalizar_rotulo("IMA-B")`.
CA-022: `ler_texto(ms,"latin-1")` decodifica; com `"utf-8"` levanta `UnicodeDecodeError` no byte `0xe7`.
**Todos os números declarados pelo implementador foram reproduzidos.**

## 4. Tentativas de quebrar (Validation Mode)

**F-001 — BLOQUEOU:** HTTP 200 + `{"error": "…10 anos…"}` (corpo real do SGS) e as variantes `erro`,
`ERROR`, fixture `sgs_433__erro.json`, objeto no lugar de array, corpo `null`, 0 bytes, HTML em
`json_array` → todos `RespostaDeErroComStatus200`. Requisição sem UA → `UserAgentObrigatorio` (CA-045).
HTTP 500 (4 tentativas, backoff) e 404 (sem retry) → `FonteIndisponivel`. `arquivar_bruto` 2× igual →
`idempotente=True`, `mtime_ns` inalterado; conteúdo diferente no mesmo nome → `ConteudoDivergente` (R8).
`gravar_processado_parquet` com coluna inventada → `SchemaErrors` **e não criou o arquivo** (CA-003 é
estrutural, não promessa).
**F-001 — PASSOU (achados):** corpo `[]` com HTTP 200 **e `contagem_minima_esperada=249` no contrato** →
devolveu `[]`; 200 observações com mínimo 249 → devolveu 200 (**QA-02, P1** — a guarda existe mas não é
chamada: `exigir_contagem_minima(0, minimo=249)` à mão levanta corretamente). HTML 200 em `cliente.get()`
cru → devolve `RespostaBruta` com `.formato=="html"` (**QA-03, P2**, por design). **`para_float_ptbr(1.234)`
→ `1234.0`** (**QA-01, P0**).

**F-009 — sobre fixtures reais em `tmp_path`, todos `rejeitado` e nada gravado:** HTML de erro 404 servido
com HTTP 200; `saida=xls` que é HTML `<table>`; corpo XLSX (magic `PK`); corpo JSON `[]`; **data pedida ≠
data interna** nas duas direções (pedi 10-08 e veio 10-09; pedi 10-09 e veio 10-08 → "eco de outro dia
útil"); `ms` truncado a 40% / só cabeçalho / cabeçalho+5 linhas (títulos ausentes); `cz` truncado a 30% (17
< 20 vértices) e só cabeçalho de betas (Svensson ausente). **Ausência = caso normal, exit 0** (CA-028):
0 bytes com HTTP 200, HTTP 404, corpo só de espaços → `ausente`, 1 linha no log, nada gravado.
**Vintage:** 2ª execução com corpo idêntico → `ja_arquivado` e `mtime_ns` inalterado; com corpo diferente
→ `revisao_arquivada` em `ms_261009__v2.txt`, **original intacto**.

**Idempotência real, ao vivo (CA-027/CA-121):** snapshot de `mtime_ns`+tamanho+`sha256` dos **82 arquivos**
de `data/raw/anbima-{ms,ettj}/`, depois `uv run python -m apps.pipeline.jobs.anbima_daily --backfill 2`
**duas vezes** (rede de verdade), depois novo snapshot → **`diff` vazio**. Ambas imprimiram
`RESUMO: ja_arquivado=4`, exit 0. Só o `anbima-daily-job.log` cresceu (log de operação, não dado).

**Varreduras transversais:** (a) **encoding** — varredura AST própria em `apps/`+`packages/`+`tests/` por
`open`/`read_text`/`write_text`/`read_csv`/`to_csv`/`read_table`/`read_fwf` sem `encoding=` (ignorando modo
binário) → **0 achados**; (b) **rede fora de `@pytest.mark.network`** → nenhuma; único marcado é
`test_live_anbima_responde_e_arquiva`, e `transporte_requests` importa `requests` **dentro** da função;
(c) `.skip`/`xfail` novo → nenhum; (d) dependência nova → nenhuma; (e) fixtures = 82 KB totais, nenhuma
> 1 MB, nenhuma sintética, nada de `data/` versionado.

## 5. Matriz de validação

### F-001 — CA-003, CA-022, CA-035, CA-045, CA-123, CA-124 (+ CA-030 pré, CA-121)

| CA | Teste | Tipo | Status | Minha evidência |
|---|---|---|---|---|
| CA-003 | corpo de erro com 200 | unit neg. | ✅ | 6 variantes bloqueadas; `gravar_processado_parquet` recusou e **não criou arquivo** |
| CA-022 | encoding explícito + lint | unit | ✅ | `utf-8` sobre `ms` → `UnicodeDecodeError` 0xe7; varredura AST própria = 0 leitor sem `encoding=` |
| CA-035 | normalizador único pt-BR | unit | ⚠️ | `"38.484,84"`→`38484.84`, `"0.82"` levanta, `"6.930"`→`6930.0` — **mas `para_float_ptbr(1.234)`→`1234.0`** (QA-01) |
| CA-045 | asserção de User-Agent | unit neg. | ✅ | `UserAgentObrigatorio` antes do despacho; só desliga com flag explícita |
| CA-123 | zero rede no CI | unit | ✅ | N1 com `connect`/`getaddrinfo` proibidos → `161 passed` |
| CA-124 | fixture gravada por fonte | contract | ✅ | 5 fixtures reais em `common/` + README de procedência; a de **erro** existe |
| CA-030 (pré) | magic bytes decidem o leitor | unit | ✅ | `IMAB.xls` real → `xlsx`; `cz` → `html`; `exigir_formato` levanta |
| CA-121 (parc.) | arquivamento idempotente | unit | ✅ | `arquivar_bruto` 2× → `mtime_ns` inalterado; divergente → `ConteudoDivergente` |

### F-009 — CA-027, CA-028, CA-029

| CA | Teste | Tipo | Status | Minha evidência |
|---|---|---|---|---|
| CA-027 | idempotência real | integration (vivo) | ✅ | 2× `--backfill 2` contra a ANBIMA real → `diff` vazio em `mtime_ns`+tamanho+`sha256` dos 82 arquivos; revisão vai para `__v2`, original intacto |
| CA-028 | 0 bytes / 404 → sucesso | unit neg. | ✅ | `ausente` + exit 0 nos 3 casos; 1 linha no log; nada gravado |
| CA-029 | parse `ms*.txt` e `CZ` | contract | ✅ | `@`+`skiprows=2`+latin-1+decimal vírgula+5 títulos conferidos **contra a fonte viva**; `saida=xls` HTML, truncamento e eco de data → `rejeitado` sem gravar |
| — | cobertura da janela | ev. de dados | ✅ | 21 dias `ms` + 20 dias `cz`, **0 lacunas**, 41/41 `sha256` batendo |

## 6. Correções solicitadas

**P0 — bloqueia o merge de F-001 · QA-01: `para_float_ptbr` com entrada numérica nativa = erro de escala
1000× silencioso.** `_normalizar_entrada` (`parsing.py` ~l.175) converte `int|float` via
`repr(float(valor))`, gerando string com **ponto decimal**, que `_PTBR` então lê como **milhar**.
Reprodução: `para_float_ptbr(1.234) == 1234.0` e `para_float_ptbr(12.345) == 12345.0` (silencioso);
`(723.070317)`, `(38484.84)`, `(5.0)`, `(0.82)`, `(-1.5)` **levantam**. O branch `isinstance(valor,
int | float)` nunca acerta: erra alto ou erra em silêncio. **Por que importa agora:** `openpyxl` devolve
**float nativo** no `.xls` do S3 da ANBIMA — medi `723.070317` em `IMAB.xls` — e F-002 é a próxima feature.
Nenhum teste cobre entrada numérica (`test_common_parsing.py` só cobre `bool`, l.119). É exatamente o modo
de falha que o módulo existe para impedir (CA-035, R13). **Correção ≤ 3 linhas (não apliquei):** devolver
`float(valor)` direto para `int|float` sem passar pelo regex — ou levantar sempre, documentando que a
função só aceita `str`. Com teste parametrizado por entrada numérica.

**P1 — antes da Onda 1 · QA-02: `ClienteHTTP.json_array()` ignora `config.contagem_minima_esperada`.**
Corpo `[]` com 200 e mínimo 249 declarado devolve `[]`; 200 observações com mínimo 249 devolve 200. A
guarda existe, funciona e **nunca é chamada no caminho padrão** (R2 — truncamento silencioso de
Olinda/Yahoo/FRED). Correção ≤ 3 linhas: chamar `exigir_contagem_minima(len(lista),
minimo=self.config.contagem_minima_esperada, origem=…)` dentro de `json_array`, + teste.

**P2 — depois:**
- **QA-03** (F-001): `cliente.get()` não valida shape; `ExtractorConfig.formato` já declara o esperado e
  poderia alimentar um `exigir_formato` automático. Hoje depende de o extrator lembrar.
- **QA-04** (F-009): `_para_float_br` duplicado faz `replace(".","")` sem guarda (`"0.82"` → `82.0`). Só
  roda no parse de **validação** da Curva Zero (pt-BR genuíno) e nada é persistido — dívida que a migração
  `# TODO(F-001)` → `para_float_ptbr` fecha.
- **QA-05** (F-009): feriado não é modelado (decisão documentada). Se num feriado a ANBIMA **ecoar** o dia
  útil anterior em vez de 404, o veredito é `rejeitado` → exit 1 → tarefa agendada reporta FALHA, **sem
  perda de dado**. Verificar em **2026-10-12** (Aparecida) e, se ocorrer, tratar eco em dia não-útil como
  `ausente`.
- **QA-06** (infra): `uv.lock` é novo e **não** está no `.gitignore` — decidir se entra no commit.
- **QA-07** (doc): registrar `pyproject.toml` no Feature Contract de F-001 (§18) e corrigir a lista de
  arquivos de F-001/F-009 para os caminhos reais.
- **QA-08** (operação): o risco de perda de dado **só fecha quando o Edu criar a tarefa agendada**
  (`runbooks/job-diario-anbima.md` §3). Fora do escopo da feature, dentro do risco do projeto.

---

*QA por subagente Opus independente, 2026-10-10. Nenhuma linha de `apps/` ou `tests/` foi alterada por
mim — este arquivo é a única escrita; os scripts de verificação ficaram no scratchpad da sessão.*

---

## 7. Re-QA de F-001 (2026-10-10, após a correção)

**Veredito final de F-001: APROVADO.** Reproduzi **somente** os casos de QA-01 e QA-02 contra a versão
atual de `parsing.py` e `http.py`. Os dois achados estão fechados e o caminho textual de CA-035 não
regrediu. Nenhum `.skip`/`xfail` novo; nenhuma dependência adicionada (`git diff pyproject.toml` = 4
inserções, nenhuma em `dependencies`).

```
$ uv run ruff check .          →  All checks passed!
$ uv run ruff format --check . →  26 files already formatted
$ uv run pytest tests/unit -m "not network" -q
                               →  189 passed, 1 deselected, 1 xfailed in 1.33s
```

De 161 → **189 testes** (+28): `test_common_parsing` 49→**68**, `test_common_http` 32→**41**.

**QA-01 — fechado.** Os 8 casos exatos do meu QA original, todos corretos (antes: 2 silenciosamente
errados, 6 levantando): `para_float_ptbr(1.234)` = **1.234** (era `1234.0`), `(12.345)` = **12.345** (era
`12345.0`), `(723.070317)`, `(38484.84)`, `(5)`, `(5.0)`, `(0.82)`, `(-1.5)` todos devolvendo o próprio
valor (antes levantavam). Extras conferidos: `np.float64/np.float32/np.int64` passam direto;
`float("nan")`, `np.nan` e `NaN` de `pd.Series` → **`None`** (nunca `0`, §10.1.4); `Decimal("1.234")`,
`float("inf")` e `True` → **`NumeroNaoReconhecido`**. Desenho certo pelo motivo certo: `_e_numero_nativo`
usa `numbers.Real` excluindo `bool`, e `_texto_de_entrada` só aceita `str` — nada mais chega ao parser
textual por `str(valor)` implícito.
**Sem regressão em CA-035:** `"38.484,84"`→`38484.84`; `"0.82"` **levanta**; `"6.930"`→`6930.0`;
`""`/`"-"`/`"ND"`→`None`; `para_float_ponto_decimal("0.82")`=`0.82`, `(1.234)`=`1.234`.
**Arquivo real:** `IMAB.xls` relido com os valores passando **por `para_float_ptbr`** (antes levantava) →
5795 linhas, 2003-09-16 → 2026-10-09, 1ª linha **723.070317** (canário CA-031), última `12656.536776`,
0 nulos. É o caminho que F-002 vai usar, agora liberado.

**QA-02 — fechado.** Mesmos casos, com `origem` identificando contrato + URL:

| Caso | Antes | Agora |
|---|---|---|
| corpo `[]` com `contagem_minima_esperada=249` | passou devolvendo `[]` | **`RespostaTruncada`** ("0 registros") |
| 200 observações com mínimo 249 no contrato | passou devolvendo 200 | **`RespostaTruncada`** ("200 registros") |
| `minimo=DO_CONTRATO` explícito, `[]` e mínimo 249 | — | **`RespostaTruncada`** |
| `minimo=None` (janela fatiada) · `minimo=150` com 200 obs | — | passam — **correto** |
| corpo `[]` **sem** mínimo no contrato | passou | passa — correto, nada foi declarado |

A sentinela `DO_CONTRATO` resolve a ambiguidade real entre "não disse nada" (usa o contrato), `None` ("não
checar aqui") e inteiro explícito; o docstring documenta a receita da janela fatiada, que era onde um
default rígido quebraria F-003.

**Pendências de F-001:** nenhum P0, nenhum P1. Seguem só os P2 do §6 (QA-03, QA-06, QA-07) — nenhum
bloqueia a abertura da Onda 1.
