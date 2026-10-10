# Skills Manifest — estrategia-macro-ldc-dados

> Output do `/skill-scout` (Harness v3.2). Capacidades do projeto, como cada uma é resolvida, risco
> operacional — **mais a checagem real do ambiente desta máquina em 2026-10-10**.

**Data:** 2026-10-10 · **Versão:** 1.0 · **Referência:** PRD §9/§12, `docs/research/fontes-de-dados*.md`
**Veredito em 1 frase:** zero skill nova, zero MCP novo; o único bloqueio real da máquina é o **FRED**
(R5 **CONFIRMADO**), e o setup se resolve com **um comando** (`uv sync --extra dev`) — as 3 deps que
faltavam no `pyproject` (`openpyxl`, `lxml`, `matplotlib`) **já foram adicionadas em 2026-10-10**.

---

## 1. Capacidades → cobertura → decisão

| # | Capacidade | Cobertura | Recurso concreto | Classe | Risco operacional |
|---|---|---|---|---|---|
| 1 | HTTP REST/JSON (SGS, SIDRA, B3, MSCI, Yahoo, Teva) | **nativo** | `httpx` / `requests` + UA de browser | B | nenhum segredo; R1 (erro com HTTP 200) e R4 exigem assert de shape + contagem mínima |
| 2 | OData v4 (Olinda/Focus, Ipeadata) | **nativo** | `httpx` + paginação `$skip` | B | R2: **nunca** usar `$top=20000` (trunca sem `nextLink`) |
| 3 | Download de arquivo grande (TD 14,6 MB; S3 ANBIMA) | **nativo** | `requests` com `stream=True` | B | latin-1 explícito; `data/raw/` imutável |
| 4 | Parse de **XLSX disfarçado de `.xls`** (ANBIMA IMA) | **nativo** | `openpyxl` via `pandas.read_excel(engine="openpyxl")` + checagem de magic bytes `PK\x03\x04` | B | **`xlrd` não é necessário** no caminho crítico (ver §6) |
| 5 | Parse de **HTML `<table>` disfarçado de `.xls`** (ANBIMA Curva Zero) | **nativo** | `pandas.read_html` + `lxml` | B | R7; sniff de magic bytes antes de escolher o leitor |
| 6 | CSV pt-BR (`;`, decimal vírgula, latin-1) | **nativo** | `pandas.read_csv` + normalizador único de número pt-BR | B | R7 — um só normalizador, testado com datas-armadilha |
| 7 | Armazenamento **Parquet** | **nativo** | `pyarrow` (via pandas) | C em `data/canonical/` | — |
| 8 | Consulta analítica / **DuckDB** | **nativo** | `duckdb` | C | **decidido:** ADR-006 = Parquet por camada + DuckDB **só como engine de consulta** (derivado e descartável). `duckdb` fica no `pyproject` |
| 9 | Validação de schema de DataFrame | **nativo** | `pandera` (obrigatório em tudo que entra/sai de `data/canonical/`) | **C** | é o gate técnico contra dado errado; sem pandera não há classe C aprovável |
| 10 | Contrato de config/payload | **nativo** | `pydantic` v2 | B | `python-dotenv` para `.env` (nenhuma key obrigatória hoje) |
| 11 | Notebook reprodutível (RF-041) | **nativo** | `jupyterlab` 4.4.7 (instalado, **fora do PATH** — usar `python -m jupyter lab`) | B | outputs limpos no commit; sem lógica de negócio |
| 12 | **Heatmap regime × ativo** (RF-033, entregável central) | **nativo + skill existente** | `matplotlib` + skill **`dataviz`** (paleta/escala divergente centrada em 0, `n` por célula) | **D** | vai ao Comitê → revisão humana; escala divergente e `n` anotado são requisito, não estética |
| 13 | Export **XLSX** para o Alexandre (RF-043) | **nativo + skill existente** | `pandas.to_excel` (`openpyxl`) + skill **`anthropic-skills:xlsx`** se precisar formatação/abas | **D** | dataset congelado + 3 valores conferidos + linha em `wiki/log.md` |
| 14 | Export **PPTX / PDF** | **skill existente — fora do escopo atual** | `anthropic-skills:pptx` / `:pdf` / `:docx` | D se usada | **RF-043/P-12 define a entrega como Parquet + CSV/XLSX + figuras + notebook.** Não instalar `python-pptx`/`reportlab`; se o Comitê pedir slide, a skill resolve com zero dependência nova |
| 15 | Varredura web quando a API falhar | **MCP existente** | **Playwright MCP** (+ `playwright` 1.58 e Chromium já no disco) | B (diagnóstico) / C se virar fonte | ⚠️ **nunca no pipeline.** As páginas da B3 são shells Angular (2.333 B, só `<app-root>`) → scraping de HTML **não funciona**; o caminho é a API. Uso: inspecionar endpoint novo, capturar headers, confirmar que uma fonte caiu |
| 16 | Job diário de arquivamento ANBIMA (L6/R3/RF-010) | **nativo** | script em `apps/pipeline/` + Agendador de Tarefas do Windows | B | cada dia sem rodar é dado perdido para sempre — **ligar no dia 1** |
| 17 | Lint / format / testes | **nativo** | `ruff` 0.16.4, `pytest` 8.4.0 | A | rede só sob `@pytest.mark.network` |
| 18 | Testes de contrato com valor-canário (R4/RF-050) | **nativo** | `pytest` + fixtures gravadas em `tests/fixtures/` | **C** | IBOV 01/02/2006 = 38.484,84 · IMA-B 16/09/2003 = 723,070317 · MSCI ACWI NETR 31/01/2006 = 121,3858 |

**Decisão agregada:** 18 capacidades · **16 nativas** · **1 MCP existente** (Playwright) · **3 skills
existentes** (`dataviz`, `xlsx`, e `pptx`/`pdf` em standby) · **0 skills novas** · **0 MCPs novos**.

---

## 2. Ambiente real desta máquina (diagnóstico, nada instalado)

| Ferramenta | Status | Versão / observação |
|---|---|---|
| `python` / `py` | ✅ | **3.13.3** em `C:\Python313\python.exe` (pyproject pede ≥ 3.11 — ok) |
| `uv` | ✅ | **0.11.25** → caminho preferido |
| `pip` | ✅ | 25.2 (user site em `%APPDATA%\Python\Python313`) |
| `git` | ✅ | 2.46.0.windows.1 — repo **já inicializado desde o kickoff** (`git log`: 7 commits, de `143d936` a `5a36035`); `.gitignore` em vigor |
| `jupyter` (CLI) | ⚠️ | pacote instalado (`jupyter` 1.1.1, `jupyterlab` 4.4.7) mas **`Scripts/` fora do PATH** → usar `python -m jupyter` |
| Playwright + Chromium | ✅ | `playwright` 1.58.0 + browsers em `%LOCALAPPDATA%\ms-playwright` |

**Deps do `pyproject` no Python padrão (sem venv):**

| Dep | Importa? | Versão |
|---|---|---|
| `pandas` | ✅ | 2.3.0 |
| `requests` | ✅ | 2.32.3 |
| `httpx` | ✅ | 0.28.1 |
| `pydantic` | ✅ | 2.13.4 |
| `python-dotenv` | ✅ | — |
| `jupyter` | ✅ | 1.1.1 |
| **`pyarrow`** | ❌ | **ausente** — sem ele não há Parquet |
| **`pandera`** | ❌ | **ausente** — sem ele não há gate de schema (classe C travada) |
| **`duckdb`** | ❌ | ausente — **entra no `uv sync`**: ADR-006 manteve `duckdb` como engine de consulta |

**Fora do `pyproject`, mas presentes e usados pelo plano (medido de manhã):** `openpyxl` 3.1.5,
`lxml` 6.0.0 e `matplotlib` 3.10.3 — **os três entraram no `pyproject` à tarde**. Seguem fora:
`bs4` 4.13.4, `yfinance` 0.2.61 (decisão aberta), `ruff` 0.16.4, `pytest` 8.4.0, `numpy` 2.4.6.
**Ausentes e desnecessários:** `xlrd`, `xlsxwriter`, `python-pptx`, `html5lib`, `odfpy`.

---

## 3. Conectividade real (GET leve, timeout 20 s, UA de browser, 2026-10-10)

| Fonte | HTTP | Tempo | Resposta | Veredito |
|---|---|---|---|---|
| BCB SGS 433 | **200** | 0,39 s | 38 B JSON array | ✅ roda |
| BCB Olinda Focus (OData) | **200** | 3,47 s | 334 B JSON | ✅ roda (o mais lento dos BR) |
| IBGE SIDRA t/1737 | **200** | 0,25 s | 591 B JSON | ✅ roda |
| ANBIMA S3 `IMAB-HISTORICO.xls` | **200** | 1,28 s | **393.685 B**, magic `PK\x03\x04` | ✅ roda — e **confirma que é XLSX**, não XLS |
| Tesouro Direto `precotaxatesourodireto.csv` | **200** | 0,51 s | `text/csv`, 400 KB lidos do início (arquivo ~14,6 MB) | ✅ roda (header confere) |
| API B3 `indexStatisticsProxy` IBOV/2006 | **200** | 0,20 s | 9.494 B, `min.rateValue1="33.507,27"` | ✅ roda (com `Referer` da B3) |
| Yahoo `^GSPC` | **200** | 0,42 s | 1.704 B JSON | ✅ roda |
| MSCI ACWI `892400` NETR | **200** | 1,76 s | 1.647 B JSON | ✅ roda |
| **FRED `fredgraph.csv?id=DGS10`** | **—** | 20,6 s | **ReadTimeout**; retry 1 = ReadTimeout, retry 2 = **ConnectionReset(10054)** | 🚨 **BLOQUEADO** |
| **`api.stlouisfed.org`** (sem key) | **—** | 21,7 s | redireciona para `www.stlouisfed.org` → **ReadTimeout** | 🚨 **BLOQUEADO** |
| Teva GCS `teva-indices-public` (list) | **200** | 0,37 s | 6.269 B JSON | ✅ roda |
| *extra:* Yahoo `^TNX`, `^VIX`, `DX-Y.NYB`, `^FVX`, `^BVSP` | **200** | 0,24–0,28 s | dados presentes nos 5 | ✅ **plano B do FRED funciona** |
| *extra:* Ipeadata OData4 | **200** | 0,26 s | 2.072 B | ✅ roda |
| *extra:* ANBIMA `CZ-down.asp` (GET da página) | **200** | 0,43 s | 2.905 B | ✅ host alcançável (o download real é **POST**, não testado aqui) |

### R5 — CONFIRMADO, e agora com a camada identificada

Não é DNS nem firewall de pacote: `fred.stlouisfed.org` resolve (`23.10.51.194`), **TCP:443 conecta em
0,04 s** e o **handshake TLS 1.3 completa em 0,03 s**. O que falha é a resposta HTTP — timeout de leitura
e, no retry, `ConnectionResetError(10054)`. Mesmo padrão em `api.stlouisfed.org`. Isso é **bloqueio na
camada de aplicação** (WAF/CDN rejeitando este egress), não lentidão. **Reproduz 3/3 tentativas.**

**Consequência:** nenhum requisito pode depender do FRED nesta máquina. **Plano B já validado** acima.

---

## 4. Setup recomendado

```bash
cd C:\Users\edusp\Projetos_App_Desktop\estrategia-macro-ldc-dados

# caminho preferido — um comando, uv 0.11.25 já instalado
uv sync --extra dev
uv run python -m jupyter lab          # evita o problema de PATH do jupyter

# alternativa sem uv
python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"
```

**Estado do `pyproject.toml` (corrigido em 2026-10-10) — o `uv sync --extra dev` agora entrega um ambiente
que lê os arquivos da ANBIMA e desenha o heatmap:**

- ✅ **`openpyxl>=3.1`** → **adicionado.** É o leitor dos 10 arquivos IMA (que são XLSX apesar da extensão)
  e o writer do XLSX de entrega (RF-043). Antes só funcionava por acidente (instalado no Python global).
- ✅ **`lxml>=5.0`** → **adicionado.** Obrigatório para `read_html` na Curva Zero da ANBIMA (HTML `<table>`).
- ✅ **`matplotlib>=3.8`** → **adicionado.** Obrigatório para o heatmap (RF-033) e a timeline (RF-035).
- ✅ **`duckdb>=1.0`** → **mantido.** O **ADR-006** decidiu *Parquet por camada + DuckDB apenas como engine
  de consulta*; a dúvida "DuckDB vs. Parquet puro" desta §5 está resolvida lá (status: Proposta).
- **`seaborn`** → **não adicionar.** Nenhum documento do projeto o exige: o heatmap de RF-033 é
  `matplotlib` puro com a paleta da skill `dataviz`.
- **`xlrd`** → **não adicionar.** Nenhum arquivo do projeto é XLS/BIFF real: o magic bytes do S3 da ANBIMA
  veio `PK\x03\x04` nesta sessão. Só entra se aparecer um XLS legado — e aí vira linha no `DECISIONS_LOG`.
- ✅ **`yfinance>=0.2.50`** → **adicionado e decidido** em 2026-10-10. Virou **caminho crítico** (é o
  plano B do FRED): **FRED bloqueado nesta máquina, confirmado 3/3** nos testes de conectividade
  (§3). Entra com piso de versão; a chamada direta ao `chart/v8` com UA de browser continua como
  fallback dentro de F-007/F-011 se a lib falhar (rate limit disfarçado). Registrado em
  `DECISIONS_LOG §2`.

**FRED exige plano B? Sim — obrigatório nesta máquina.** Mapeamento direto:
`DGS10`→`^TNX`, `DGS2`/`DGS5`→`^FVX`, `VIXCLS`→`^VIX`, `DTWEXBGS`→`DX-Y.NYB`, `DEXBZUS`→**BCB SGS 1/10813
(PTAX)**, `SP500`→**Yahoo `^GSPC` ou MSCI USA 984000**, `T10Y2Y`→calcular de `^TNX`−`^FVX` (proxy 10y−5y,
**declarar a troca**), `DFF`/`FEDFUNDS`→**sem substituto gratuito equivalente** → se for requisito, pedir
execução de outra rede ou registrar como lacuna. Toda troca entra em `docs/plans/DECISIONS_LOG.md`.

---

## 5. ADRs e DECISIONS_LOG

| Item | Onde | Por quê |
|---|---|---|
| ~~ADR — DuckDB vs. Parquet puro~~ — **resolvido** | [`ADR-006`](../decisions/adr/ADR-006-armazenamento-e-convencao-de-retornos.md) | **Parquet por camada + DuckDB só como engine de consulta** (status: Proposta). `duckdb` permanece no `pyproject` |
| **ADR — `httpx` vs `requests` como cliente único** | `docs/decisions/adr/` | os dois estão no `pyproject`; dois clientes = dois lugares para errar UA/timeout/retry |
| **ADR — especificação de regime congelada antes de rodar** (R-08/RF-031) | `docs/decisions/adr/` | evita overfitting ao heatmap |
| **DECISIONS_LOG — FRED substituído por Yahoo+PTAX+MSCI** | `docs/plans/DECISIONS_LOG.md` | fonte pedida indisponível neste ambiente (evidência nesta §3) |
| **DECISIONS_LOG — `xlrd` dispensado; leitor por magic bytes** | `docs/plans/DECISIONS_LOG.md` | decisão operacional pequena que volta ao debate |
| **DECISIONS_LOG — Teva como fonte de FII setorial (2019+)** | `docs/plans/DECISIONS_LOG.md` | provedor privado sem licença explícita |

---

## 6. Riscos operacionais e gates

Não há produção, deploy, staging, auth, pagamento nem credencial. **O risco é dado errado chegar ao
Comitê em 2026-10-14.** O gate é a **classe D**.

| # | Risco operacional | Gate |
|---|---|---|
| RO-1 | **Entregável vai ao Alexandre/Comitê com número errado** | **classe D obrigatória:** revisão humana + dataset congelado + 3 valores por série conferidos contra a fonte + linha em `docs/wiki/log.md`. Seção com **Rollback** em `docs/plans/infra-ops.md`. Nenhum agente envia nada por conta |
| RO-2 | Extrator grava lixo com **HTTP 200** (SGS) ou série truncada (Olinda/Yahoo) | classe B/C: assert de shape + contagem mínima + chave `error` antes do parse; teste de contrato com valor-canário no CI |
| RO-3 | Alteração de schema canônico / alinhamento temporal / cálculo de retorno | **classe C:** Feature Contract + **diff numérico** vs versão anterior + schema pandera. Sem `pandera` instalado, nada classe C é aprovável |
| RO-4 | **FRED bloqueado** derruba o bloco internacional em silêncio | classe C: teste de conectividade no início do pipeline; falha **explícita** (`BLOQUEADO — FONTE INDISPONÍVEL`), nunca fallback silencioso; troca registrada no `DECISIONS_LOG` |
| RO-5 | Endpoint não documentado muda sem aviso (B3, MSCI, S3 ANBIMA) | classe C: teste de contrato com valor-canário; fallback documentado por fonte |
| RO-6 | **Janela rolante apaga o passado** (ANBIMA ~20 d.u.) | classe B, mas **prioridade de dia 1**: ligar o job de arquivamento hoje; alerta quando a última observação envelhecer |
| RO-7 | Playwright MCP vira fonte de dado de produção | gate: **proibido**. Playwright é diagnóstico. Virar fonte → pausa + ADR |
| RO-8 | Dado bruto > 5 MB ou `.parquet`/`.duckdb` commitado | gate: o `.gitignore` do repo (que **existe desde o kickoff**, commit `143d936`) já ignora `data/raw|processed|canonical`, `*.parquet`, `*.duckdb`, `*.xls*` e `.env` — conferir `git status` antes de cada commit |

**Riscos de auto-reclassificação alta:** qualquer feature marcada **B** que toque `data/canonical/` ou
produza figura/tabela do pacote de entrega **é C ou D desde o início** — trate assim e economize o retrabalho.

---

## 7. Aprovação

- [x] Capacidades do PRD/pesquisa mapeadas (18)
- [x] Nenhum MCP novo, nenhuma skill nova
- [x] Classe de risco por capacidade
- [x] ADRs e linhas de DECISIONS_LOG listados
- [x] Ambiente e conectividade medidos nesta máquina (não inferidos)
- [x] `pyproject.toml` corrigido em 2026-10-10 — `openpyxl`, `lxml` e `matplotlib` adicionados; `duckdb`
      mantido por ADR-006; `seaborn` dispensado. **Resta decidir `yfinance`.**
- [ ] `uv sync --extra dev` executado
- [x] Repo git e `.gitignore` conferidos — o repo **existe desde o kickoff**; `git init` não é pendência
- [ ] Próximo passo: `/agents-protocol`
