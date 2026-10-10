# Runbook — Job diário de arquivamento ANBIMA (F-009 / operação R-1)

**Última execução verificada:** 2026-10-10 — 41 arquivos de dados arquivados (toda a janela rolante
disponível), exit code 0
**Tempo:** < 1 min para 1 dia; ~90 s para `--backfill 20`
**Risco:** B · **operação crítica** — dia não arquivado é **dado perdido para sempre**
**Fonte de verdade da operação:** [`docs/plans/infra-ops.md` §2](../../plans/infra-ops.md) ·
pesquisa: [`docs/research/fontes-de-dados.md`](../../research/fontes-de-dados.md) §A4.2 e §A5

## 1. O que o job faz e por que ele é urgente

As duas séries abaixo vivem numa **janela rolante de ~20 dias úteis** no site da ANBIMA. Fora dela não
existe backfill gratuito (o histórico longo só no **ANBIMA Feed, pago**) — e usar janela rolante como
fonte de histórico é proibido (**Anti-SPEC §10.1.3**). Em 12 meses de job rodando, a casa passa a ter
ETTJ própria; só se começar hoje.

| Série | Requisição | Destino | Arquivo |
|---|---|---|---|
| Taxas indicativas do secundário | `GET https://www.anbima.com.br/informacoes/merc-sec/arqs/ms{AAMMDD}.txt` | `data/raw/anbima-ms/` | `ms_AAMMDD.txt` |
| Curva Zero (Svensson) | `POST https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp` (`Idioma=PT&Dt_Ref=dd/mm/aaaa&saida=csv`) | `data/raw/anbima-ettj/` | `cz_AAMMDD.csv` |

Cada arquivo tem um **manifest** ao lado (`<arquivo>.manifest.json`) com `url`, `data_ref`, `sha256`,
`bytes`, `collected_at` + formato, encoding, nº de registros e veredito. Cada execução anexa 1 linha por
fonte × dia em `data/raw/anbima-daily-job.log`. Nada em `data/` vai para o git.

**Garantias:** idempotente (mesmo `sha256` → "já arquivado", nada reescrito); **nunca sobrescreve**
(conteúdo diferente para a mesma data vira vintage novo, `ms_AAMMDD__v2.txt`); **ausência é sucesso**
(feriado / dia sem publicação / 0 bytes / 404 → registra e sai 0); corpo inválido (HTML de erro com
HTTP 200, ZIP, truncado, **eco de outro dia útil**) → **nada é gravado** e exit code 1.

## 2. Comandos

```bash
# dia de hoje (as duas fontes)
python -m apps.pipeline.jobs.anbima_daily

# recuperação: últimos N dias úteis, do mais antigo ao mais novo (é o modo do agendador)
python -m apps.pipeline.jobs.anbima_daily --backfill 3

# um dia específico
python -m apps.pipeline.jobs.anbima_daily --date 2026-10-09

# só uma das fontes
python -m apps.pipeline.jobs.anbima_daily --fonte cz --backfill 5
```

`--backfill` acima de 40 é recusado (exit 2): fora da janela rolante o dado **não existe** na fonte, e
`--backfill` não é backfill de histórico.

## 3. Como agendar no Windows (Task Scheduler via `schtasks`)

A ANBIMA fecha as taxas indicativas no fim da tarde e tem **atraso declarado de apuração** (aviso de
10/03/2026). Rode **19:30**, dias úteis, com `--backfill 3` — assim uma falha de ontem ou de um fim de
semana se conserta sozinha no dia seguinte, sem intervenção.

Copie e cole **uma linha** no PowerShell ou no `cmd` (não precisa de admin; a tarefa roda como o usuário
logado):

```bat
schtasks /Create /TN "LDC\ANBIMA job diario" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30 /RL LIMITED /F /TR "cmd /c cd /d C:\Users\edusp\Projetos_App_Desktop\estrategia-macro-ldc-dados && .venv\Scripts\python.exe -m apps.pipeline.jobs.anbima_daily --backfill 3 >> data\raw\anbima-daily-job-stdout.log 2>&1"
```

- **Enquanto o `.venv` não existir** (F-001 o cria com `uv sync`), troque
  `.venv\Scripts\python.exe` por `python` — o job só usa `pandas` e `requests`.
- O `cd /d` é obrigatório: `python -m apps.pipeline...` resolve o pacote a partir da raiz do repo, e os
  caminhos de `data/raw/` são relativos a ela.
- **Sem `/RU`**, a tarefa roda **apenas com o usuário logado** — que é o caso da máquina do Edu. Para
  rodar com a máquina ligada e ninguém logado, use um shell **como administrador**:
  `... /RU SYSTEM /RL HIGHEST ...` (mesmo `/TR`).
- `/F` sobrescreve a tarefa se ela já existir — é o comando de (re)instalação.

### Verificar

```bat
schtasks /Query /TN "LDC\ANBIMA job diario" /V /FO LIST
```

Olhe `Status`, `Last Run Time`, **`Last Result`** (`0` = ok) e `Next Run Time`.

```bat
schtasks /Run /TN "LDC\ANBIMA job diario"
```

Dispara agora, sem esperar o horário — é o teste de fumaça da instalação.

```bash
# 30 segundos de verificação diária
ls -la data/raw/anbima-ms/   | tail -5
ls -la data/raw/anbima-ettj/ | tail -5
tail -4 data/raw/anbima-daily-job.log
```

Esperado: arquivo com a data de hoje (ou do último dia útil) e tamanho > 0 — `ms_*.txt` ≈ 6,6 KB,
`cz_*.csv` ≈ 2,9 KB. Veredito `arquivado`, `ja_arquivado` ou `ausente` no log.

### Remover

```bat
schtasks /Delete /TN "LDC\ANBIMA job diario" /F
```

## 4. Se o job falhar — sintoma → ação

| Sintoma | Causa provável | Ação |
|---|---|---|
| **Nenhum arquivo do dia**, job não rodou | máquina desligada, tarefa desabilitada, usuário sem sessão | rode **à mão hoje mesmo**: `python -m apps.pipeline.jobs.anbima_daily --backfill 3`. O dia ainda está na janela |
| `Last Result` ≠ 0 no `schtasks /Query` | o job saiu com exit 1 (corpo inválido) ou 2 (uso) | leia `data/raw/anbima-daily-job-stdout.log` — a mensagem já diz a ação |
| veredito `ausente` | feriado, dia sem publicação, atraso de apuração da B3/ANBIMA | **normal** (CA-028). Registre e **tente de novo no fim da tarde**. Não preencha nada |
| veredito `rejeitado` com "é HTML" | `saida=xls` do CZ sempre devolve HTML; ou página de erro da ANBIMA com HTTP 200 | o parser recusa por magic byte e **não grava**. Se for página de erro, repita mais tarde; se a ANBIMA trocou o formato, `/fast-fix` classe B + nova fixture |
| veredito `rejeitado` com "eco de outro dia útil" | a fonte devolveu o último dia publicado no lugar da data pedida | **não é dado do dia pedido** — nada foi gravado, e está certo. Não force |
| veredito `rejeitado` com "truncamento silencioso" | resposta cortada | repita mais tarde; se persistir, compare com a fixture |
| `erro_rede` | rede/WAF | retry automático já ocorreu (3 tentativas, backoff). Confira conectividade e **rode de novo hoje** |
| `revisao_arquivada` | a ANBIMA republicou a mesma data com conteúdo diferente | **esperado e tratado**: o original fica intacto e o novo vira `__v2`. Vintage é dado, não bug |
| Falhou **1 a 3 dias** | janela de ~20 d.u. ainda cobre | `--backfill 5` resolve; confira os tamanhos |
| Falhou **> 20 dias úteis** | **dado perdido definitivamente** | registre `[DATA-LOSS]` em [`wiki/log.md`](../log.md) com o intervalo exato; declare a lacuna na página de limitações. **Não** interpole, **não** reconstrua, **não** emende outra fonte sem `DECISIONS_LOG`. A curva histórica do pacote mínimo vem do **Tesouro Direto** (ADR-004), então a perda **não** bloqueia 2026-10-14 — bloqueia a série proprietária futura |
| URL/formato mudou | ANBIMA alterou o endpoint | [`runbooks/fonte-fora-do-ar.md`](./fonte-fora-do-ar.md); atualize `FONTE_MS`/`FONTE_CZ` em `apps/pipeline/jobs/anbima_daily.py`, grave nova fixture e atualize [`modules/anbima.md`](../modules/anbima.md) |

**Regra de ouro:** falha de arquivamento se resolve **no mesmo dia**, e cada falha deixa 1 linha em
`wiki/log.md` — a lacuna tem de ser visível depois, quando alguém perguntar por que a série tem buraco.

## 5. Cobertura medida em 2026-10-10 (bordas da janela)

| Fonte | Mais antigo com dado | Mais novo | Dias arquivados |
|---|---|---|---|
| `ms*.txt` | **2026-09-11** (09/09 e 10/09 → HTTP 404) | 2026-10-09 | 21 |
| Curva Zero | **2026-09-14** (11/09 e antes → HTTP 200 com 0 bytes) | 2026-10-09 | 20 |

Bate com a varredura da pesquisa (§A4.2 e §A5.2). `Msec_txt.txt` (URL estável do último dia útil) veio
**byte a byte idêntico** a `ms_261009.txt` — mesmo `sha256`.

**Links:** [`infra-ops.md` §2](../../plans/infra-ops.md) ·
[`modules/anbima.md`](../modules/anbima.md) · [`runbooks/fonte-fora-do-ar.md`](./fonte-fora-do-ar.md) ·
[`context/F-009.md`](../context/F-009.md)
