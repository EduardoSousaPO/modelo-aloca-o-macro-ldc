# infra-ops.md — operações de classe D e rotinas de dados

> **Substitui o `cursor-brief.md`** do Harness genérico. Aqui **não há deploy, servidor, staging, migration
> nem env de produção**: o pipeline roda na máquina do Edu. O que existe de "produção" neste projeto é a
> **publicação de números para o Comitê de Alocação** (F-031) e o **job diário de arquivamento da ANBIMA**
> (F-009), cuja janela de dados é rolante e irrecuperável.
>
> **Regra:** uma seção por operação. Toda operação de **classe D** tem **Rollback** obrigatório — sem ele,
> não sai. Ver `AGENTS.md §2` (classes), `§14` (gate de 8 passos), `docs/plans/risk-classification.md`.
>
> **Versão:** 1.0 · **Data:** 2026-10-10 · **Entrega alvo:** Comitê de Alocação em **2026-10-14**.

---

## 0. Pré-requisitos de ambiente (uma vez, antes de qualquer classe D)

- [x] **Repositório git existe** (`git init` feito; 3 commits de documentação em 2026-10-10). Sem git não
      haveria tag, `git diff` nem rastreabilidade de versão — e **nenhuma classe D seria possível**.
- [x] **Branch padrão é `main`** — resolvido em 2026-10-10 (renomeada de `master`;
      `git branch --show-current` → `main`). Alinhada ao CI (`.github/workflows/ci.yml`) e a
      `AGENTS.md §10`.
- [ ] `uv sync` (ou venv + `pip install -e ".[dev]"`) com CI N1 verde localmente.
- [ ] `.gitignore` cobrindo `data/`, `*.parquet`, `*.duckdb`, `.env`.
- [ ] `docs/plans/DECISIONS_LOG.md` existente (F-032) — o pacote é enviado **com** o texto das
      substituições de fonte.

---

## 1. Operação D-1 — Publicação do pacote ao Comitê (F-031)

**Feature:** F-031 — Pacote de entrega ao Comitê · **Classe:** D · **CI alvo:** N3
**Destinatário:** Alexandre Kaercher (stakeholder) · **Executa:** Edu (humano), com um subagente Opus
preparando os artefatos e **outro** fazendo o QA.
**Depende de:** F-001…F-030 verdes + **ADR-001 aceito**.

### 1.1 Contexto

O entregável é um diretório versionado contendo: `macro_quarterly`, `asset_returns_quarterly`, `regimes` e
`regime_neighbors` em **Parquet + CSV/XLSX**; as figuras (heatmap regime × ativo, timeline de regimes); as
duas tabelas de 1 página; a página de limitações; e um `README` com **versão + hash**. Tudo gerado por
`apps/pipeline/deliver/pacote.py` — **nenhum arquivo do pacote é editado à mão** (CA-114).

### 1.2 Dataset congelado (hash)

O pacote só existe amarrado a um estado imutável de `data/canonical/`. Congelar = calcular e registrar o
hash de **cada** arquivo + um hash agregado, e nunca mais tocar naquele diretório.

```bash
# hash por arquivo + hash agregado do diretório canônico (ordem estável)
find data/canonical -type f | sort | xargs sha256sum > entrega/HASHES.txt
sha256sum entrega/HASHES.txt | cut -d' ' -f1 > entrega/DATASET_SHA256.txt

# reprodutibilidade (requisito N3 / CA-121): duas execuções do zero → mesmo agregado
python -m pipeline.build_canonical --out /tmp/run1 && python -m pipeline.build_canonical --out /tmp/run2
diff <(find /tmp/run1 -type f | sort | xargs sha256sum | sed 's|/tmp/run1||') \
     <(find /tmp/run2 -type f | sort | xargs sha256sum | sed 's|/tmp/run2||')
```

Registre no `README` do pacote: **versão** (`v1.0`), **data/hora**, **`DATASET_SHA256`**, **commit SHA**,
**tag git** e a lista de séries com `min`/`max` de data. Versão nova **nunca** sobrescreve a anterior:
`entrega/v1.0/`, `entrega/v1.1/`.

### 1.3 Tag git

```bash
git tag -a comite-2026-10-14 -m "Pacote de entrega ao Comitê — v1.0 — DATASET_SHA256=<hash>"
git tag -n comite-2026-10-14        # confirmar antes de enviar qualquer arquivo
```

A tag é o ponto de retorno do rollback: **o que foi enviado é exatamente o que essa tag reconstrói.**
Correção pós-envio gera **tag nova** (`comite-2026-10-14-v1.1`), nunca `git tag -f`.

### 1.4 Checklist de revisão humana (Edu) — antes do envio

Nenhum item é dispensável. Cada caixa marcada precisa de evidência colada no PR ou no `wiki/log.md`.

- [ ] **ADR-001 aceito** (D1 + D3 respondidos). Em `Proposta` → `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA`
      e **nenhum número de regime sai**.
- [ ] CI **N3** verde: `pytest tests/e2e -m "not network"` + duas execuções com `sha256` idêntico.
- [ ] **3 valores conferidos na fonte por série** (print/link), não contra o teste.
- [ ] `macro_quarterly` com o nº de trimestres esperado (**83**) e `min`/`max` coerentes com a janela.
- [ ] `asset_returns_quarterly` com ≥ 18 ativos e painel desbalanceado correto — **nenhuma linha antes do
      início real de cada série** (IFIX não começa em 2006).
- [ ] **`n` visível em toda célula** de toda tabela; nenhuma célula com `n < 5` apresentada como conclusão.
- [ ] Nenhuma linguagem preditiva nos textos ("vai render", "deve subir") — o produto é **descritivo**.
- [ ] **Página de limitações** (F-028) incluída, com as séries que não cobrem 20 anos.
- [ ] **Texto das substituições de fonte** anexado (DECISIONS_LOG / F-032): fonte pedida, fonte usada,
      por quê, impacto na comparabilidade.
- [ ] Nenhum arquivo do pacote editado à mão (hash do script confere — CA-114).
- [ ] Smoke test do pacote executado e colado (§1.5).
- [ ] Rollback (§1.6) lido e viável **antes** do envio.
- [ ] QA (Prompt 3) por subagente **distinto** do que gerou: `APROVADO`.
- [ ] Linha `[RELEASE]` em `docs/wiki/log.md` com versão, hash e tag + resumo em `wiki/features/F-031.md`.

### 1.5 Smoke test do pacote (obrigatório, antes do envio)

O smoke test aqui não é "o endpoint responde 200" — é **o Alexandre consegue abrir e os números fazem
sentido**. Rode e cole a saída.

1. **Abre no Excel.** Cada `.xlsx` abre sem aviso de arquivo corrompido; cada `.csv` abre com as colunas
   separadas corretamente (separador e encoding declarados no `README` do pacote).
2. **Contagem de linhas** por arquivo, comparada com o esperado:
   ```bash
   for f in entrega/v1.0/*.csv; do echo -n "$f: "; python -c "import pandas as pd,sys; d=pd.read_csv(sys.argv[1]); print(len(d), d.columns.tolist())" "$f"; done
   ```
   `macro_quarterly` = 83 · `regimes` = 83 · `asset_returns_quarterly` = 83 × nº de ativos menos os
   trimestres anteriores ao início de cada série.
3. **Datas min/max** por arquivo e por série — e conferência de que o último trimestre é o esperado.
4. **Nulos nas colunas críticas = 0.** Colunas críticas: `quarter`, `asset_id`, `regime_v1`,
   `ret_tri`, `excesso_cdi`, `n_obs_regime_v1`, `source`/`series_id`, `fonte_versao`.
   ```bash
   python -c "import pandas as pd; d=pd.read_parquet('entrega/v1.0/asset_returns_quarterly.parquet'); print(d[['quarter','asset_id','ret_tri','excesso_cdi']].isna().sum())"
   ```
   Qualquer nulo em coluna crítica → **não envia**. Nulo legítimo (série que ainda não começou) tem de
   estar **ausente como linha**, não presente como `NaN`.
5. **Figuras abrem** (PNG/PDF), legíveis, com `n` anotado e legenda de unidade.
6. **Paridade Parquet × CSV/XLSX:** mesma contagem de linhas e mesmos valores em 3 amostras aleatórias.
7. **`README` do pacote** cita versão, hash, tag, commit e a página de limitações.

### 1.6 Rollback — retirar ou corrigir um número já enviado ao Alexandre

> Aqui não existe `vercel rollback`. O "deploy" é um e-mail com números que uma mesa de alocação pode já
> ter usado. **O rollback é de comunicação + versão.** Velocidade importa menos que clareza.

**Se o pacote AINDA NÃO foi enviado:** não envie. Corrija, regenere, refaça o gate de 8 passos. Fim.

**Se JÁ foi enviado:**

1. **Pare a propagação (minutos).** Avise o Edu imediatamente. O Edu manda **uma mensagem curta ao
   Alexandre**: "o pacote `v1.0` (hash `<8 primeiros>`) tem um problema em `<tabela/coluna>`; **não use
   para decisão** até a versão corrigida; envio em `<prazo>`". Não explique a causa nesta mensagem — ela
   serve para parar o uso.
2. **Marque a versão como revogada** em `docs/wiki/log.md`, na mesma ordem cronológica:
   `[YYYY-MM-DD HH:MM] [REVOKED] entrega v1.0 (DATASET_SHA256=<hash>, tag comite-2026-10-14) — motivo:
   <1 linha> — substituída por v1.1`. A linha original `[RELEASE]` **não é apagada nem editada**.
3. **Reconstrua do `raw/` arquivado**, não do canônico suspeito: `data/raw/` é imutável e versionado por
   data — é exatamente para isto que existe. Reconstrução completa a partir de zero, CI N3 verde.
4. **Diff numérico v1.0 → v1.1, célula por célula**, com **cada** divergência explicada (não basta
   "corrigido"). Este diff vai **anexado** à versão corrigida.
5. **Envie a versão corrigida** com: nova tag (`comite-2026-10-14-v1.1`), novo hash, o diff do item 4 e
   uma nota de 1 parágrafo dizendo **o que estava errado, desde quando, o que muda na leitura** e se alguma
   conclusão do material anterior se inverte.
6. **Registre a causa** em `docs/plans/DECISIONS_LOG.md` (se foi decisão/fonte) ou em um **ADR** (se foi
   arquitetura) e crie/atualize `docs/wiki/runbooks/` se o erro pode voltar.
7. **Teste de regressão:** o bug que causou a correção vira **teste permanente** (classe C: teste de
   contrato com o valor certo). Sem esse teste, o rollback não está fechado.

**Nunca:** reenviar o arquivo "silenciosamente corrigido" com o mesmo nome/versão; apagar a linha de
`[RELEASE]` do log; usar `git tag -f`; corrigir o número no canônico à mão para "fechar rápido".

---

## 2. Operação R-1 — Job diário de arquivamento da ANBIMA (F-009)

**Feature:** F-009 · **Classe:** B (mas **operação crítica**) · **Executa:** Agendador de Tarefas do
Windows, na máquina do Edu · **Frequência:** todo dia útil, após o fechamento da ANBIMA.

### 2.1 Por que é a operação mais urgente do projeto

As séries proprietárias da ANBIMA — `ms{AAMMDD}.txt` (taxas indicativas do secundário) e a **Curva Zero**
(parâmetros Svensson, via `POST CZ-down.asp`) — têm **janela rolante de ~20 dias úteis**. Dia não baixado é
**dado perdido para sempre**: não existe backfill, e usar janela rolante como fonte de histórico é proibido
(Anti-SPEC §10.1.3). Em 12 meses de job rodando, a casa passa a ter ETTJ própria — mas só se começar hoje.

### 2.2 O que o job faz

- Baixa os dois arquivos do dia e grava **versionado por data** em `data/raw/anbima-ms/` e
  `data/raw/anbima-ettj/`.
- **Idempotente:** rodar 2x no mesmo dia não duplica nem grava conteúdo diferente.
- Faz um **parse mínimo de validação** (magic bytes: `saida=xls` do CZ vem como **HTML**, não XLS; `ms*.txt`
  é `@`-separado, `skiprows=2`, encoding **latin-1**, 5 títulos) e **rejeita** corpo inválido.
- **Ausência é caso normal:** feriado, dia sem publicação ou resposta de 0 bytes → sucesso **com registro**,
  não exceção (`ausencia_e_caso_normal = True` no `ExtractorConfig`).
- Anexa 1 linha ao log de execução com data, bytes recebidos e veredito.

### 2.3 Verificação diária (30 segundos)

```bash
ls -la data/raw/anbima-ms/ | tail -5
ls -la data/raw/anbima-ettj/ | tail -5
# esperado: um arquivo com a data de hoje (ou de ontem, se hoje não é dia útil) e tamanho > 0
```

### 2.4 Se o job falhar — runbook

> Runbook completo em [`docs/wiki/runbooks/job-diario-anbima.md`](../wiki/runbooks/job-diario-anbima.md).
> Job: `apps/pipeline/jobs/anbima_daily.py`. Resumo operacional:

| Sintoma | Causa provável | Ação |
|---|---|---|
| **Nenhum arquivo do dia** e o job não rodou | máquina desligada, tarefa desabilitada, usuário sem sessão | rode **à mão hoje mesmo**: `python -m apps.pipeline.jobs.anbima_daily --backfill 3` (ou `--date AAAA-MM-DD` para um dia específico); o dia ainda está na janela de 20 d.u. |
| Arquivo com **0 bytes** ou HTTP 404 | feriado, dia sem publicação, publicação atrasada | normal: registre a ausência; **tente de novo no fim da tarde**; não preencha nada |
| Resposta é **HTML** onde se esperava planilha | `saida=xls` do CZ sempre devolve HTML; ou página de erro | parser escolhe pelo **magic byte**; se virou página de erro, repita mais tarde |
| **HTTP 200 com corpo de erro** | fonte instável / bloqueio por User-Agent | confirme UA de browser; repita com backoff; não grave corpo inválido |
| Falhou **1 a 3 dias** | janela de ~20 d.u. ainda cobre | rode em **modo recuperação**, dia a dia, do mais antigo ao mais novo, e confira os tamanhos |
| Falhou **> 20 dias úteis** | **dado perdido definitivamente** | registre `[DATA-LOSS]` em `docs/wiki/log.md` com o intervalo exato; declare a lacuna na **página de limitações**; **não** interpole, **não** reconstrua, **não** emende com outra fonte sem registro em `DECISIONS_LOG.md`. A curva histórica do pacote mínimo vem do **Tesouro Direto** (ADR-004), então a perda **não** bloqueia a entrega de 2026-10-14 — bloqueia a série proprietária futura |
| Fonte mudou de URL/formato | ANBIMA alterou o endpoint | `/triage-bugs` se houver outros sintomas; senão `/fast-fix` classe B; atualize `FONTE_MS`/`FONTE_CZ` em `apps/pipeline/jobs/anbima_daily.py`, `docs/wiki/modules/anbima.md` e a fixture |

**Regra de ouro da operação:** falha de arquivamento se resolve **no mesmo dia**. Uma linha em
`wiki/log.md` por falha, sempre — a lacuna tem de ser visível depois, quando alguém perguntar por que a
série tem buraco.

### 2.5 Agendamento (comando recomendado — executa o Edu, uma vez)

Dias úteis às **19:30** com `--backfill 3`: a ANBIMA fecha as indicativas no fim da tarde e tem atraso
declarado de apuração, e o `--backfill 3` faz uma falha de ontem ou de um fim de semana se consertar
sozinha no dia seguinte. Uma linha, sem admin, rodando como o usuário logado:

```bat
schtasks /Create /TN "LDC\ANBIMA job diario" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30 /RL LIMITED /F /TR "cmd /c cd /d C:\Users\edusp\Projetos_App_Desktop\estrategia-macro-ldc-dados && .venv\Scripts\python.exe -m apps.pipeline.jobs.anbima_daily --backfill 3 >> data\raw\anbima-daily-job-stdout.log 2>&1"
```

Verificar / disparar agora / remover:

```bat
schtasks /Query  /TN "LDC\ANBIMA job diario" /V /FO LIST
schtasks /Run    /TN "LDC\ANBIMA job diario"
schtasks /Delete /TN "LDC\ANBIMA job diario" /F
```

No `/Query`, olhe `Status`, `Last Run Time`, **`Last Result`** (`0` = ok) e `Next Run Time`; o `/Run` é o
teste de fumaça da instalação. O `cd /d` é obrigatório (o `-m` resolve o pacote a partir da raiz do repo
e `data/raw/` é relativo a ela). Sem `.venv`, troque `.venv\Scripts\python.exe` por `python`. Para
rodar com a máquina ligada e **ninguém logado**: shell como administrador + `/RU SYSTEM /RL HIGHEST`.
Detalhes e variações: [`runbooks/job-diario-anbima.md`](../wiki/runbooks/job-diario-anbima.md) §3.

### 2.6 Bordas da janela — **medidas** em 2026-10-10

| Fonte | Mais antigo com dado | Fora da borda, a fonte responde | Dias arquivados |
|---|---|---|---|
| `ms_AAMMDD.txt` | **2026-09-11** | HTTP **404** (09/09 e 10/09) | 21 |
| Curva Zero (`cz_AAMMDD.csv`) | **2026-09-14** | HTTP **200 com 0 bytes** (11/09 e antes) | 20 |

Mais novo nas duas: 2026-10-09. A borda **anda todo dia útil** — o que hoje é 11/09, amanhã é 14/09.
Confere com a varredura da pesquisa (§A4.2 e §A5.2). Consequência operacional: `--backfill` acima de
**40** é recusado (exit 2), porque fora da janela o dado **não existe** na fonte — `--backfill` não é
backfill de histórico (Anti-SPEC §10.1.3).

---

## 3. Operação D-2 — Uso de credencial ou API paga (hoje: não autorizado)

**Classe:** D · **Status:** nenhuma fonte paga no caminho crítico (Anti-SPEC §10.3.14).

Se L4 for decidido como "contratar o **ANBIMA Feed**" (≈ R$ 686-8.238/mês), então **F-016 sobe de C para D**
e esta seção precisa ser preenchida **antes** de qualquer requisição autenticada, com: quem autorizou,
onde a credencial vive (fora do repo, em `.env` não versionado), qual escopo de uso, custo e
**Rollback** = revogar a chave, remover de `.env`, confirmar que nenhum arquivo versionado a contém
(`git log -p -S"<prefixo>"`) e registrar em `DECISIONS_LOG.md` que a série volta ao Tesouro Direto.

**Até lá:** nenhum agente usa credencial. Pedido de fonte paga → **pausa** e decisão humana.

---

## 4. O que este arquivo NÃO cobre

Não há deploy, servidor, staging, banco real, migration, env de produção, feature flag, RLS nem rollout
gradual — nada disso existe neste projeto. Pedido de "subir para produção" ou "configurar staging" é sinal
de que alguém trouxe um checklist de SaaS para cá: traduza para **publicação ao Comitê** (classe D, §1) ou
recuse.

---

*Atualize este arquivo sempre que uma nova operação classe D aparecer, e **antes** de executá-la — não
depois. Versão de entrega enviada sem seção aqui é violação do gate de `AGENTS.md §14`.*
