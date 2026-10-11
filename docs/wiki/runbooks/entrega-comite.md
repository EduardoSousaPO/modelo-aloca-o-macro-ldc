# Runbook — Fechar e enviar o pacote de entrega ao Comitê (F-031, classe D)

**Estado em 2026-10-11:** o pacote está **montado e verificado**, e **não sai**.
`ADR-001` está em **`Proposta`** em disco ⇒ `especificacao_congelada = False` (CA-090) ⇒ passo 2 do
gate **reprovado**.

> # ENQUANTO ADR-001 ESTIVER EM PROPOSTA, O PACOTE NÃO SAI.
>
> Vale para o pacote completo **e** para "só esse número do heatmap no WhatsApp": **não existe
> classe A/B para publicação** (`AGENTS.md §14`, Anti-SPEC §10.3.18).

**Quem executa:** o **Edu** (humano). Os subagentes preparam e conferem; **o envio é ato humano.**
**Tempo estimado:** 15 min se o canônico já está verde · 50 min do zero com extração.
**Risco:** o mais alto do projeto — o que sai daqui pode virar decisão de alocação.
**Operação correspondente:** `docs/plans/infra-ops.md §1` (Operação D-1), que tem o contexto, o
dataset congelado e o rollback canônico. Este runbook é a **sequência executável** dele.

---

## 1. Os 8 passos do gate (`AGENTS.md §14`) — na ordem, sem atalho

Faltando **qualquer um** → não envia. Todo comando abaixo roda da raiz do repositório.

> ## ⚠️ A ordem importa — interação F-031 × F-029, **resolvida em D-ag**
>
> O pacote é montado **dentro** de `data/canonical/entrega/`, e
> `python -m apps.pipeline verify` cobre `data/canonical/` **recursivamente**. Até 2026-10-11 isso
> fazia o `verify` reprovar os 42 arquivos do pacote como *"nao listado no manifesto"* **e** acusar
> agregado divergente — e um `freeze` novo incluiria o próprio pacote no `DATASET_SHA256`
> (circular). **Era medido, não hipótese.**
>
> **Resolvido por `D-ag`:** `inventariar()` ignora o prefixo `entrega/pacote_comite_` (diretório e
> `.zip`), porque o pacote é **cópia** de artefato já manifestado e reconstruível por um comando
> (CA-114). **Conferido com o pacote em disco:** `VERIFY OK`, 48 artefatos, agregado `fc233118…`
> **inalterado**, `rc 0`. O HTML executado do caderno (`entrega/entrega_comite_*.html`) **continua**
> artefato e continua protegido pelo `verify`.
>
> **A ordem segue a mesma**, por outro motivo: `run --offline` → `verify` → `freeze --tag` →
> `montar_pacote --smoke`. O pacote **copia** o `MANIFEST.json` e o cita no `README-COMITE.md`,
> então ele precisa do manifesto **já congelado** — montar antes do `freeze` produz um pacote que
> cita um dataset que ainda vai mudar.
>
> ```bash
> uv run python -m apps.analysis.entrega.montar_pacote --limpar   # conveniência, não obrigação
> uv run python -m apps.pipeline verify                           # VERIFY OK com ou sem o pacote
> ```

### Passo 1 — CI N3 verde: e2e + duas execuções com `sha256` idêntico

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit tests/contract -m "not network" -q
uv run pytest tests/e2e -q

# reprodutibilidade (CA-121): reconstruir e reconferir o hash de cada artefato
uv run python -m apps.pipeline run --offline
uv run python -m apps.pipeline verify            # rc != 0 se um byte divergir
uv run python -m apps.pipeline run --offline     # a segunda rodada
uv run python -m apps.pipeline verify
```

**Critério:** `verify` com `rc = 0` nas duas vezes e o **mesmo** `DATASET_SHA256`.

> **Pegadinha medida (D-v b):** `pytest ... | tail` devolve o `rc` do `tail`, não o do pytest — foi
> assim que 2 falhas passaram batido no QA da Onda 4. **Confira o `rc` de verdade** (`echo $?`,
> `$LASTEXITCODE` no PowerShell, ou `--junitxml`).
>
> **Segunda pegadinha, também medida:** `versao_build` hasheia o **módulo**, então editar um `.py`
> de `apps/` ou `packages/` no meio da medição muda o `sha256` **sem** o dado se mover. Congele o
> código antes de medir.

### Passo 2 — `ADR-001` aceito (D1 + D3 respondidos) · **O GATE DURO**

```bash
# o que o pipeline lê, literalmente:
grep -n "Status" docs/decisions/adr/ADR-001-lente-de-regime-oficial.md
```

- `- **Status:** Proposta` → **`BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA`**. **Pare aqui.**
- `- **Status:** Aceita` → siga. Um `run --offline` depois do aceite reescreve as 83 linhas e
  derruba o selo em **toda** figura e tabela — **zero linha de código**.

**Como destravar:** o Edu responde **D1** (qual lente é a oficial) e **D3** (eixo de inflação da
V1) no próprio ADR e muda o `Status` para `Aceita`. "Aceito as recomendações" em cada um já basta
(`TODO.md §4`). O status é lido do disco com **falha fechada**: arquivo ausente ou ilegível conta
como **não** congelado, nunca o contrário.

### Passo 3 — Revisão humana do número pelo Edu, com 3 valores por série

É o §2 deste runbook (checklist com caixas). **Não** é dispensável e **não** é delegável a agente:
é a assinatura humana no número.

### Passo 4 — Dataset congelado: versão + `sha256` + tag git

```bash
uv run python -m apps.pipeline freeze --tag comite-2026-10-14
# grava data/canonical/MANIFEST.json + data/canonical/FROZEN.txt com a tag, o commit e o rollback

cat data/canonical/FROZEN.txt                       # confira a tag e o DATASET_SHA256
git tag -a comite-2026-10-14 -m "Pacote de entrega ao Comite - v1.0 - DATASET_SHA256=<hash>"
git tag -n comite-2026-10-14                        # confirme ANTES de enviar qualquer arquivo
```

`freeze` **não executa git** de propósito (decisão (e) de F-029): ele lê o commit de `.git/HEAD` e
**imprime** a instrução da tag. A tag é ato humano. Correção pós-envio gera **tag nova**
(`comite-2026-10-14-v1.1`), **nunca** `git tag -f`.

### Passo 5 — Rollback escrito para esta entrega

Já está escrito: `docs/plans/infra-ops.md §1.6` e o §3 deste runbook. **Leia antes de enviar**, não
depois — o item "rollback lido e viável" do checklist é literal.

### Passo 6 — Smoke test do pacote

```bash
uv run python -m apps.analysis.entrega.montar_pacote --smoke
```

Monta `data/canonical/entrega/pacote_comite_2026-10-14/` + o `.zip` determinístico e roda as ~93
checagens de `infra-ops.md §1.5`: abre cada CSV e cada Parquet, confere nº de linhas e `sha256`
contra o `MANIFEST.json`, `min`/`max` de data, **zero nulos nas colunas críticas** (com as
contagens de nulo legítimo travadas), abre o XLSX com `openpyxl` e confere **abas e dimensões**,
confirma que o HTML cita `DATASET_SHA256`, que **nenhum** artefato `publicavel: false` entrou e que
o texto do gate está no README, no XLSX e no notebook. **`rc != 0` em qualquer falha.**

```bash
# idempotência do pacote (duas montagens -> mesmo sha256 do zip):
uv run python -m apps.analysis.entrega.montar_pacote | grep SHA256
uv run python -m apps.analysis.entrega.montar_pacote | grep SHA256

# só reconferir o pacote que já está em disco, sem remontar:
uv run python -m apps.analysis.entrega.montar_pacote --so-smoke
```

**Cole a saída** no PR e em `wiki/log.md`. O item 1 de `infra-ops §1.5` — **abrir no Excel de
verdade** — é humano: nenhuma máquina deste projeto tem Excel ou LibreOffice instalado, então
"abre sem aviso de arquivo corrompido" é caixa do §2, não checagem automática.

### Passo 7 — Comunicação escrita das substituições de fonte

O pacote já leva `SUBSTITUICOES-DE-FONTE.md` (cópia da §1 de `DECISIONS_LOG.md`: as **12**
substituições com fonte pedida, fonte usada, por quê e impacto na comparabilidade — CA-117).
**Confirme que o arquivo está no `.zip`** e cite-o no corpo do e-mail: a lista não serve de nada
dentro de um anexo que ninguém abre.

### Passo 8 — Linha `[RELEASE]` em `wiki/log.md` + resumo em `wiki/features/F-031.md`

```
[2026-10-14 HH:MM] [RELEASE] entrega v1.0 (DATASET_SHA256=<hash>, tag comite-2026-10-14,
commit <sha>) - pacote_comite_2026-10-14.zip enviado a Alexandre Kaercher - smoke rc=0,
QA <arquivo>, revisao humana do Edu em <data>
```

E **≤ 5 linhas** em `docs/wiki/features/F-031.md` com o que foi entregue e o hash.

---

## 2. Checklist de revisão humana (Edu) — marque antes do envio

Os 14 itens de `infra-ops.md §1.4` + os 3 canários + a leitura da timeline + as 12 decisões.
**Nenhum item é dispensável.** Cada caixa marcada precisa de evidência colada no PR ou em
`wiki/log.md` — "conferi" sem evidência não conta.

### Os 14 de `infra-ops.md §1.4`

- [ ] **1. `ADR-001` aceito** (D1 + D3 respondidos). Em `Proposta` →
      `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA` e **nenhum número de regime sai**.
- [ ] **2. CI N3 verde:** `pytest tests/e2e -m "not network"` + duas execuções com `sha256`
      idêntico. **Confira o `rc`, não o `tail`.**
- [ ] **3. Três valores conferidos na fonte por série** (print ou link do BCB/IBGE/ANBIMA/B3/
      Tesouro), **não** contra o teste e **não** contra `raw_series.parquet`.
- [ ] **4. `macro_quarterly` com 83 trimestres** e `min`/`max` coerentes
      (`2006Q1 → 2026Q3`).
- [ ] **5. `asset_returns_quarterly` com ≥ 18 ativos** (hoje **24**) e painel desbalanceado
      correto: **nenhuma linha antes do início real de cada série** — IFIX não começa em 2006.
- [ ] **6. `n` visível em toda célula** de toda tabela e figura; nenhuma célula com `n < 5`
      apresentada como conclusão (hoje `IFIX` e `IMOB` na V3, `n = 4`, suprimidos).
- [ ] **7. Nenhuma linguagem preditiva** nos textos ("vai render", "deve subir") — o produto é
      **descritivo** (Anti-SPEC §10.2.10). A guarda roda sobre o README no momento da montagem;
      a leitura do e-mail de envio é sua.
- [ ] **8. Página de limitações incluída** (`LIMITACOES-COMITE.md`), com as séries que não cobrem
      20 anos.
- [ ] **9. Texto das substituições de fonte anexado** (`SUBSTITUICOES-DE-FONTE.md`), com os 4
      campos por item.
- [ ] **10. Nenhum arquivo do pacote editado à mão** (CA-114): `HASHES.txt` fecha com o conteúdo
      do diretório, arquivo por arquivo.
- [ ] **11. Smoke test executado e colado** (passo 6), `rc = 0`.
- [ ] **12. Rollback (§3) lido e viável** **antes** do envio.
- [ ] **13. QA (Prompt 3) por subagente distinto do que gerou:** `APROVADO`.
- [ ] **14. Linha `[RELEASE]` em `docs/wiki/log.md`** com versão, hash e tag + resumo em
      `wiki/features/F-031.md`.

### Os 3 canários — confira **na fonte viva**, não no Parquet

São os três valores que atravessam o pipeline inteiro; se os três batem na fonte, a cadeia
extração → bruto → alinhamento → retorno está de pé.

- [ ] **15. IBOV em 01/02/2006 = 38.484,84** (API de índices da B3).
- [ ] **16. IMA-B em 16/09/2003 = 723,070317** (repositório público da ANBIMA — é o primeiro dia
      da série).
- [ ] **17. MSCI ACWI NETR em 31/01/2006 = 121,3858** (end-of-day da MSCI).

> Os três já foram conferidos contra `raw_series.parquet` (F-027). O que **falta** é a conferência
> na **fonte original**, que é o item 3 da lista acima e pertence a F-002/F-006/F-007.

### Os dois itens de leitura — não são números, são sentido

- [ ] **18. A timeline de regimes faz sentido?** Abra
      `figuras/timeline_regimes_revised.png` e leia a história que ela conta contra o que você
      viveu: 2008-2009 **sem quadrante** (o IBC-Br começa em 2003 e a média móvel de 20 trimestres
      só fecha em 2009Q4 — 16 trimestres indeterminados, `2006Q1..2009Q3` + `2026Q3`), a
      estagflação de 2015, o corte até 2% em 2020, o aperto de 2021-2022, `2026Q3` **sem rótulo**.
      **Se a figura contar uma história que você não reconhece, o problema é a lente, não a
      figura** — e isso é input de D1/D3, não de código.
- [ ] **19. As 12 decisões da §7 de `LIMITACOES-COMITE.md` estão respondidas?** São
      **D1, D3, D5, D6, D12, L1, L2, L4, D-i, D-s, D-t, D-u**. Hoje **nenhuma** tem resposta
      humana: todas carregam a recomendação da pesquisa como padrão provisório. Elas também estão
      na aba **`Decisões`** do XLSX e na seção 9 do caderno. Responder "aceito as recomendações"
      destrava as 12 de uma vez e muda o status dos ADRs.

**Marcou as 19?** Então o gate está cumprido e o envio é seu. **Falta uma?** Não envia.

---

## 3. Rollback — 7 passos

> Aqui não existe `vercel rollback`. O "deploy" é um e-mail com números que uma mesa de alocação
> pode já ter usado. **O rollback é de comunicação + versão.** Clareza importa mais que velocidade.

**Se o pacote AINDA NÃO foi enviado:** não envie. Corrija, regenere, refaça os 8 passos. Fim.

**Se JÁ foi enviado:**

1. **Pare a propagação (minutos).** Uma mensagem curta ao Alexandre: "o pacote `v1.0`
   (hash `<8 primeiros>`) tem um problema em `<tabela/coluna>`; **não use para decisão** até a
   versão corrigida; envio em `<prazo>`". **Não** explique a causa nesta mensagem — ela serve para
   parar o uso.
2. **Marque a versão como revogada** em `docs/wiki/log.md`, na ordem cronológica:
   `[AAAA-MM-DD HH:MM] [REVOKED] entrega v1.0 (DATASET_SHA256=<hash>, tag comite-2026-10-14) —
   motivo: <1 linha> — substituída por v1.1`. A linha `[RELEASE]` original **não** é apagada nem
   editada.
3. **Reconstrua do `raw/` arquivado**, não do canônico suspeito:
   ```bash
   uv run python -m apps.pipeline run --offline --reprocessar   # data/raw -> processed -> canonical
   uv run python -m apps.pipeline verify
   uv run pytest tests/e2e -q
   ```
   `data/raw/` é **imutável** e versionado por data — é exatamente para isto que existe.
4. **Diff numérico v1.0 → v1.1, célula por célula**, com **cada** divergência explicada (não basta
   "corrigido"). O `HASHES.txt` das duas versões dá o mapa de **quais** arquivos mudaram; o diff
   numérico mostra **o que** mudou dentro deles. Este diff vai **anexado** à versão corrigida.
5. **Envie a versão corrigida** com: tag nova (`comite-2026-10-14-v1.1`), hash novo, o diff do
   item 4 e uma nota de 1 parágrafo dizendo **o que estava errado, desde quando, o que muda na
   leitura** e se alguma conclusão do material anterior se inverte.
6. **Registre a causa** em `docs/plans/DECISIONS_LOG.md` (se foi decisão ou fonte) ou em um **ADR**
   (se foi arquitetura), e crie/atualize o runbook se o erro pode voltar.
7. **Teste de regressão:** o bug que causou a correção vira **teste permanente** — em classe C, um
   teste de contrato com o valor certo. **Sem esse teste, o rollback não está fechado.**

**Nunca:** reenviar o arquivo "silenciosamente corrigido" com o mesmo nome e versão; apagar a linha
`[RELEASE]` do log; usar `git tag -f`; corrigir o número no canônico à mão para "fechar rápido".

---

## 4. O que o pacote contém (e o que foi deixado fora de propósito)

`data/canonical/entrega/pacote_comite_2026-10-14/` — 41 arquivos + `HASHES.txt`, 10,9 MB soltos,
3,7 MB no `.zip`:

| Pasta | Conteúdo |
|---|---|
| raiz | `README-COMITE.md` (1 página, com o gate no topo), `LIMITACOES-COMITE.md`, `SUBSTITUICOES-DE-FONTE.md`, `PACOTE-COMITE.xlsx`, `MANIFEST.json`, `FROZEN.txt` (depois do passo 4), `HASHES.txt` |
| `dados/` | **10** tabelas em Parquet (cópia byte a byte) **e** CSV pt-BR (`;`, vírgula decimal, UTF-8 com BOM) |
| `figuras/` | 2 timelines + 3 mapas de calor, em PNG **e** SVG |
| `tabelas/` | ranking e concordância, em `.md` **e** `.csv` (**convenção de CSV diferente**: `,` e sem BOM — declarada no README) |
| `notebook/` | o caderno `.ipynb` limpo + o **HTML executado** |

**Fora, por leitura do `MANIFEST.json` (D-af):** `internacional_pesos.parquet`
(`publicavel: false` — Anti-SPEC §10.3.16/§10.5). O artefato **continua** no `DATASET_SHA256` de
propósito: o agregado descreve o que foi **construído**, não o que foi **publicado**.
**Fora, por omissão:** `raw_series`, `alinhado_trimestral`, `series_catalog`, os `*_provenance`,
`regime_neighbors` da V1, `ldc.duckdb` e os `relatorio_*.json` — todos seguem no repositório para
quem for reproduzir.

---

## 5. Falhas conhecidas e o que fazer

| Sintoma | Causa | Ação |
|---|---|---|
| `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA` | `ADR-001` em `Proposta` (o caso de hoje) | responder **D1** e **D3** no ADR e mudar o `Status` para `Aceita`; depois `run --offline` + remontar. **Não** há bypass |
| `BLOQUEADO — ARTEFATO NÃO PUBLICÁVEL: '<nome>'` | alguém pôs na lista de inclusão um artefato que o manifesto marca `publicavel: false` | não é bug do montador: é a trava funcionando. Tirar da lista, ou obter ADR-003 aceito **e** autorização escrita sobre a Anti-SPEC |
| `BLOQUEADO — FONTE INDISPONÍVEL: MANIFEST.json não existe` | o canônico não foi construído nesta máquina | `uv run python -m apps.pipeline run --offline` |
| Smoke reprova `linhas Parquet == MANIFEST` ou `sha256 ... == MANIFEST` | o `MANIFEST.json` é de outra rodada que o Parquet (rebuild parcial) | `run --offline` **encadeado** (sem `--so`) e depois `verify`; só então remontar o pacote |
| Smoke reprova `nulo de ret_tri so nas 23 ancoras` | o painel mudou (ativo novo, série que passou a ter preço inicial) | **não** relaxe a contagem: investigue qual ativo mudou e atualize `N_ANCORAS_SEM_RETORNO` com a explicação no mesmo PR |
| `INFO` de `FROZEN.txt: ausente` | o passo 4 ainda não foi executado | é esperado antes do congelamento; depois do `freeze` a linha vira `OK` |
| `INFO` de `agregado citado no HTML != MANIFEST` | **estrutural, não defeito**: o HTML executado **é** um artefato do manifesto e entra no agregado, então o hash que o caderno imprime é o da rodada **anterior** à inclusão do próprio HTML | nada a fazer. A versão que vale é o `DATASET_SHA256` de `MANIFEST.json`/`HASHES.txt`, e o README diz isso |
| O `sha256` do `.zip` mudou sem o dado mudar | código de `apps/`/`packages/` editado entre as montagens (`versao_build` hasheia o módulo) | congele o código, `run --offline`, remonte |
| `python -m apps.pipeline verify` reprova 42 arquivos como "nao listado no manifesto" e o agregado divergente | **não deve mais acontecer** (**D-ag**): `inventariar()` ignora `entrega/pacote_comite_`. Se acontecer, você está num checkout anterior a 2026-10-11 | atualize o checkout; como paliativo, `montar_pacote --limpar` + `verify` de novo |

---

**Links:** gate → `AGENTS.md §14` · operação e rollback canônico → `docs/plans/infra-ops.md §1` ·
Feature Contract → `TODO.md` bloco **F-031** · CAs → `docs/specs/SPEC.md` CA-113..117, CA-090,
CA-121 · decisões abertas → `TODO.md §4` e `docs/decisions/adr/` · reconstrução →
`docs/wiki/runbooks/reconstruir-dataset.md` · página do Comitê →
`docs/product/LIMITACOES-COMITE.md` · montador → `apps/analysis/entrega/montar_pacote.py`
