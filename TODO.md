# TODO — estrategia-macro-ldc-dados

> Estado vivo do projeto. Substitui `state/project-state.json`, `progress.jsonl` e `handoffs/`.
> Atualize ao iniciar, ao terminar uma feature e ao fim do dia.
>
> **v3.2 — Feedback Hardened + Project Wiki:** cada feature B/C/D traz o **Feature Contract inline**
> (DoR + escopo + arquivos + CAs + testes + matriz). Features A podem ter apenas a descrição mínima.

**Última revisão:** 2026-10-11 (fechamento da **Onda 3, parte 1**: F-018, F-019, F-021 + os P1 dos
dois QAs da Onda 2)
**Fase:** **Onda 3 — regimes (classe C)**, parte 1 fechada. Ondas 0, 1 e 2 **aprovadas** no QA
(F-013..F-017 e F-010 com QA independente, 0 × P0) · **40 features mapeadas** · publicação segue
travada por ADR-001
**Tipo:** ferramenta interna (dados / quant — não SaaS, não web, roda local)
**Foco atual:** §1 Em andamento = **F-018, F-019, F-021** implementadas e aguardando QA/revisão
numérica independente. `data/canonical/` tem **20** artefatos: 62 séries, 278.439 linhas, catálogo
de 138 séries, as **duas** materializações de `macro_quarterly` e as **duas** lentes de regime
(V1 e V3)
**Próximo:** **F-022** (métricas regime × ativo — a junção em `RegimesSchema`, D-r) e a **Onda 4**
(F-020 V2, F-023 heatmap, F-024 ranking, F-028 limitações)

---

## 0. Contexto do projeto

**Objetivo.** Dar base estatística ao **modelo de alocação macro doméstica** e ao **dimensionamento da
alocação internacional** da LDC Capital. O projeto extrai, normaliza e alinha num dataset canônico
trimestral de **20 anos** (≈ 2006 → 2026): (A) indicadores macroeconômicos brasileiros — PIB/IBC-Br, IPCA,
expectativas do Focus, Selic Over, taxas de títulos públicos, estrutura a termo da curva de juros (ETTJ) —
e (B) desempenho de ativos e subsetores — índices ANBIMA de renda fixa (IMA-B, IRF-M), CDI, índices amplos e
setoriais da B3 (IBOV, IDIV, SMLL, INDX, ICON, IMAT, IEE, IMOB, IFNC) e FIIs (IFIX e segmentações) — mais
(C) proxies para a alocação internacional. Sobre essa base se identificam **regimes macro** e se mede como
cada classe de ativo e setor performou em momentos semelhantes.

**Entregável pedido.** Estrutura de busca e extração desses dados + base pronta para o Alexandre modelar a
estratégia.

**Prazo duro.** Reunião do **Comitê de Alocação: 2026-10-14**. Publicar resultado para o Comitê é operação
**classe D** (revisão humana + dataset congelado + registro em `wiki/log.md`).

**Fonte de verdade do escopo.** [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](docs/product/ESCOPO-EMAIL-ALEXANDRE.md)
— imutável. Toda feature se justifica ali; o que estiver fora exige pausa e registro.
Substituição de fonte (autorizada pelo Alexandre quando um dado não for localizável) vai para
`docs/plans/DECISIONS_LOG.md` com: fonte pedida, fonte usada, por quê, impacto na comparabilidade.

**Pesquisa concluída.** [`docs/research/`](docs/research/) — fontes de dados (132 séries catalogadas) e
metodologia de regimes. Leia antes de escrever extrator. **Nunca** apague nem sobrescreva arquivo alheio.

**Engenharia.** [`docs/specs/SPEC.md`](docs/specs/SPEC.md) (52 RFs → 128 CAs + **Anti-SPEC §10, sagrada**) ·
[`docs/contracts/CONTRACTS.md`](docs/contracts/CONTRACTS.md) (espelho) ·
[`packages/shared/schemas/`](packages/shared/schemas/) (**fonte de verdade** dos contratos) ·
[`docs/plans/PLAN.md`](docs/plans/PLAN.md) (ondas por dia) ·
[`docs/decisions/adr/`](docs/decisions/adr/) (ADR-001..006, todos em **Proposta**).

**Risco dominante.** Não é indisponibilidade: é **número errado chegando ao comitê sem levantar exceção**
(trimestre desalinhado, retorno acumulado errado, IPCA aplicado duas vezes). Daí a classe C ampla para
qualquer mudança na camada canônica — ver `AGENTS.md §2`.

---

## 1. Em andamento

> Máximo 2 itens simultâneos. Se tiver mais, você está dispersando.

**Onda 3 parte 1 IMPLEMENTADA, QA pendente (2026-10-11).** A **Onda 2 está completa e aprovada**:
QA independente em dois lotes (`docs/plans/qa/ONDA-2-QA-A.md` = F-014/F-015,
`ONDA-2-QA-B.md` = F-016/F-017), **0 × P0**, com a revisão numérica reconstruindo as camadas por
fora e achando **igualdade exata em float64**. As 6 features da Onda 2 estão registradas em
**§3 Concluído**; o Feature Contract de cada uma fica em §2 como referência de CAs e testes. As **3** features da Onda 3 parte 1 estão **implementadas e aguardando QA**:

| Feature | O que entregou | Estado |
|---|---|---|
| **F-018** | `macro_quarterly_asof` **83 × 42** + `macro_quarterly_asof_provenance` (**2.552**, com `date_obs`/`lag_dias`) + `relatorio_asof.json` | QA + **revisão numérica** pendentes · acréscimo de schema (**D-w**) |
| **F-019** | `regimes_v1{,_asof}.parquet` **83 × 18**, 67 classificados, 16 `INDETERMINADO` | QA + **revisão numérica** pendentes · **D-r**, **D-s** |
| **F-021** | `regime_neighbors_v3.parquet` **9.692 × 21** + `regime_neighbors.parquet` **5.500 × 11** | QA + **revisão numérica** pendentes · **D-u** |

**Os 5 P1 dos QAs da Onda 2 foram absorvidos neste fechamento** (todos em **D-s/D-t/D-v**):
QA-A P1-1 (IBC-Br média do trimestre → **D-s**, 7 quadrantes trocam) · QA-A P1-2 (borda do limiar
da Selic → **D-t**, 7 trimestres) · QA-A P1-3 (`exigir_series` cego a `alinhado_trimestral` →
corrigido + teste) · QA-A P1-4 (`versao_build` dependia do fim de linha → normalizado + 2 testes) ·
QA-B P1-1 (janela do CDI ≠ caminho do ativo → **limitação declarada**, cálculo intacto). QA-A P1-5
(`macro_quarterly` reescrito durante o QA) está resolvido: o rebuild abaixo é de **árvore limpa**.

**Próximo passo: F-022** (métricas regime × ativo + a junção em `RegimesSchema`, que **D-r**
delegou) e a **Onda 4** (F-020 V2, F-023 heatmap, F-024 ranking, F-028 limitações). Os insumos de
F-022 são `regime_neighbors_v3.parquet` (lente principal, **D-u**), `regimes_v1.parquet` e
`asset_returns_quarterly.parquet`; ver `docs/wiki/modules/regimes.md`.

**`data/canonical/` depois do rebuild encadeado de árvore limpa de 2026-10-11** (ordem obrigatória,
todos `--offline`: `build_raw_series` → `alinhamento` → `macro_quarterly` → `asof` → `retornos` →
`regimes_v1` (revised **e** asof) → `regimes_v3`; `curva` roda **antes de tudo**, porque escreve em
`data/processed/`), **2 rodadas com hashes idênticos nos 20 artefatos**:

| Artefato | Estado medido | `sha256` |
|---|---|---|
| `raw_series.parquet` | **278.439** linhas · **62** séries · 1979-12-31 → 2026-10-10 · **7** tabelas excluídas (D-k) | `0d23df7a…` *(inalterado)* |
| `series_catalog.parquet` | **138 × 26** · 62 presentes · 59 cobrem 1T2006 | `f56f207e…` *(inalterado)* |
| `alinhado_trimestral.parquet` | **4.038** linhas · 49 séries · 83 trimestres · 215 ffill · 7 nulos | `c66f09a5…` |
| `macro_quarterly.parquet` | **83 × 42** · `revised` · 5 colunas 100% nulas · 16 nulos em `ibcbr_gap` · **D-s** | `bcb31e92…` |
| `macro_quarterly_provenance.parquet` | **2.548** linhas · 32 colunas · 20 séries | `aa8d427a…` |
| `macro_quarterly_asof.parquet` | **83 × 42** · `asof` · 27 colunas idênticas / 10 mudam | `85e8ec67…` |
| `macro_quarterly_asof_provenance.parquet` | **2.552** linhas · 32 colunas · `date_obs`+`lag_dias` em todas · **0** com look-ahead | `a5b2eaef…` |
| `asset_returns_quarterly.parquet` | **1.963** linhas · **24** ativos · 83 trimestres | `c055ac81…` |
| `regimes_v1.parquet` | **83 × 18** · `revised` · 67 classificados · REC 19 · EXP 19 · EST 16 · DES 13 | `b74f8d67…` |
| `regimes_v1_asof.parquet` | **83 × 18** · `asof` · 67 classificados · EXP 21 · REC 17 · EST 16 · DES 13 | `6e922165…` |
| `regime_neighbors_v3.parquet` | **9.692 × 21** · 77 referências · lente principal (**D-u**) | `5241f275…` |
| `regime_neighbors.parquet` | **5.500 × 11** · pool restrito de CA-089 · **não** é a resposta | `eb101c5a…` |

> **Os hashes de `alinhado_trimestral`, `macro_quarterly*` e `asset_returns_quarterly` mudaram sem
> que uma célula de dado mudasse por outro motivo que D-s.** `versao_build` passou a normalizar o
> fim de linha (**D-v b**, P1-4 do QA), então `fonte_versao` mudou em **toda** a camada canônica.
> `raw_series` e `series_catalog` **não** têm coluna de versão e saíram byte-idênticos — é a
> contraprova de que o dado bruto não se moveu. `asset_returns_quarterly`: só `fonte_versao`
> (valores conferidos). `alinhado_trimestral`: só `fonte_versao`. `macro_quarterly`: `fonte_versao`
> **+ as 3 colunas de `ibcbr_*`** (D-s).

Os 8 `relatorio_*.json` carregam `versao_build` conferido contra o código em disco. Decisões da
onda anterior: **D-h (a)**, **D-i**, **D-j**, **D-k..D-q**; desta: **D-r..D-x** — todas em
`DECISIONS_LOG §2.3`, **provisórias onde mudam número**, com o que precisa de ratificação do Edu
tabulado em **§4**.

**Consolidação da Onda 1 — o que mudou depois dos 7 relatórios** (decisões D-a..D-h, todas
registradas em `docs/plans/DECISIONS_LOG.md §2.1` como **provisórias, aval de Edu pendente**):

| # | Decisão | Onde pegou |
|---|---|---|
| D-a | `date` de série **mensal/trimestral** = **fim de período** civil | F-003 corrigido (`fim_do_periodo`); F-004 já era assim |
| D-b | `vintage` = **data (sem hora) do `collected_at` do manifesto do bruto**, uniforme | F-002, F-003, F-004, F-005, F-006, F-007 |
| D-c | glob do `--offline` filtra `*.meta.json` em **todo** extrator | F-002, F-005, F-008 (defensivo); F-003/F-006 não usam glob; F-004/F-007 já filtravam |
| D-d | catálogo **132 → 134** (`ACWI_BRL`, `SP500_BRL`, `fonte=DERIVADO`) aceito | `CONTRACTS.md §2.1`, `README.md`, `AUDITORIA-HARNESS.md` |
| D-e | CA-004/CA-005 da SPEC não fecham no dado real → proposta registrada, **SPEC intocada** | §4 deste arquivo |
| D-f | formato HTML da fonte do calendário **ratificado** + schema migrado para `packages/shared/schemas/calendario.py` | F-008 |
| D-g | `converter_para_brl`/`carregar_ptax` → `apps/pipeline/transform/cambio.py` | F-007 |
| D-h | B3 ⊂ ANBIMA em 69 datas (todo 4T precisa 1 d.u. de ffill) | DoR de **F-014** |

**Evidência da consolidação:** `ruff check` e `ruff format --check` limpos e **535 testes unitários
verdes** sem rede; 2 rodadas `--offline` de todos os 8 extratores com **hash idêntico** nos 53
Parquets; 51 Parquets de `processed_series` com as 8 colunas, `vintage` em formato data uniforme, M/Q
em fim de período e PK única; SGS 433 × SIDRA `t/1737 v/63` passam a casar por `date` em **273 meses**
com `max|dif| = 0`, e SGS 22109 × SIDRA `t/1621 v/584` em **90 trimestres** com `max|dif| = 0`
(antes, 0 linhas casavam por `date`). Os dois últimos deixaram de ser script de sessão e viraram
teste: **`tests/unit/test_contract_sgs_sidra.py`** (reconciliação entre fontes) e
**`tests/unit/test_processed_layer_conventions.py`** (varredura de toda série em `data/processed/`).
Os dois **pulam** quando `data/processed/` está vazio, porque `data/` é reconstruível e fica fora do
git — é o que permite ao QA rodá-los sem rede e ao CI N1 ignorá-los.

---

## 2. Backlog (próximas features)

> Ordem é o **caminho crítico de 2026-10-14**: primeiro os extratores de esforço baixo (ANBIMA S3, SGS,
> SIDRA, Tesouro Direto, API B3, Yahoo/MSCI), depois a camada canônica, depois regimes V1, depois
> heatmap/notebook, depois a entrega. Cada feature cita **RFs** e **item do e-mail** (A1..A7, B1..B5, C1).
>
> **Fronteira:** `F-001` … `F-032` = **PACOTE MÍNIMO** (comprometido para o Comitê).
> `F-033` … `F-040` = **PACOTE ESTENDIDO** (fase 2, semanas seguintes).

### 2.0 Regras comuns a TODO Feature Contract (herdadas, não repetidas em cada item)

> Os contratos inline abaixo seguem `docs/plans/_templates/FEATURE-CONTRACT-template.md` (identificação →
> DoR → escopo incluído/excluído → arquivos → CAs → testes → Anti-SPEC → matriz/evidência). Esta seção
> concentra o que é **igual em todas as features**, para que cada item traga só o que é específico.
> A matriz de validação (`CA | teste | tipo | status | evidência`) é preenchida no **QA do PR**, não agora
> — modelo em `docs/plans/_templates/VALIDATION-MATRIX-template.md`. Contrato que passar de ~40 linhas
> migra para `docs/plans/feature-contracts/F-NNN.md`.

**Arquivos que NUNCA podem ser alterados sem pausa + confirmação humana:**
`docs/product/ESCOPO-EMAIL-ALEXANDRE.md` · `docs/product/PRD.md` · `docs/specs/SPEC.md` (inclusive a
**Anti-SPEC §10**) · arquivos de outros agentes em `docs/research/` · ADR já aceito ·
**schema canônico e regras de alinhamento/retorno** (mudança vira feature classe C própria).

**Arquivos sempre permitidos** (dentro do escopo da feature): `apps/pipeline/**`, `apps/analysis/**`,
`packages/shared/schemas/**` (acréscimo de schema), `tests/**`, `tests/fixtures/**`,
`docs/contracts/CONTRACTS.md` (espelho), `TODO.md`, `docs/wiki/log.md`, `docs/wiki/modules/*.md`,
`docs/plans/DECISIONS_LOG.md`.

**DoR base** (vale para toda feature B/C/D, além dos itens específicos):
- [ ] Item do escopo do e-mail identificado (A1..C1) e justificado
- [ ] Critérios de aceite = os CAs da SPEC listados no item (não inventar CA novo sem pausa)
- [ ] Escopo incluído/excluído explícito · risco confirmado · arquivos listados
- [ ] Testes mapeados + **fixture da fonte gravada** em `tests/fixtures/`
- [ ] Schemas de `packages/shared/schemas/` identificados (nunca DataFrame ad hoc)
- [ ] Altera schema canônico / alinhamento / cálculo de retorno? (se sim → **classe C**)
- [ ] Usa credencial ou API paga? (se sim → **classe D**)

**Anti-SPEC base** (verificar explicitamente no QA de toda feature B/C/D):
§10.1.1 não inventar/interpolar dado · §10.1.2 não misturar real e sintético · §10.1.5 não aceitar
HTTP 200 sem validar shape · §10.3.14 nenhuma fonte paga no caminho crítico · §10.4.21 não commitar dado ·
§10.4.22 não editar `data/` à mão · §10.4.23 nenhuma rede em teste de CI · §10.4.26 encoding explícito.

**Evidência de dados obrigatória** (além do teste verde — `AGENTS.md §5`):
nº de linhas + `min`/`max` de data · % de nulos por coluna crítica · **3 valores conferidos contra a
fonte original** (print/link) · classe C: **diff numérico** vs. versão anterior do canônico, cada
divergência explicada + reconstrução completa de `data/canonical/`.

---

## PACOTE MÍNIMO — caminho crítico para 2026-10-14

> **F-002..F-008 (os 7 extratores da Onda 1) saíram desta seção em 2026-10-11:** o QA independente
> foi concluído (`docs/plans/qa/ONDA-1-QA-A.md` e `docs/plans/qa/ONDA-1-QA-B.md`) e as 7 desceram
> para **§3 Concluído**, cada uma com o veredito e o que ficou pendente. O Feature Contract inline
> de cada uma — inclusive as notas de ajuste de caminho/nome de arquivo — fica no histórico do git
> (até o commit `3265499`); o conhecimento permanente está em `docs/wiki/modules/`.

### [x] F-010 — Extrator Focus (BCB Olinda / OData v4) — **QA APROVADO (ver §3)**

> **Estado (2026-10-11):** implementada, **QA pendente**. `data/processed/focus/` com **5
> EntitySets**, **197 `series_id`**, **150.120 linhas**, **0,00%** de nulos, 2004-01-02 →
> **2026-10-02** (a fonte publica com defasagem; o máximo de `Data` não é "hoje"). As 11 séries
> densas têm **5.710** observações contra **5.714** dias úteis da ANBIMA, com as 4 ausências todas
> em 2004 e **nenhuma** data fora do calendário de dia útil — é a conferência de contagem mais forte
> que esta fonte permite. **G-04 e G-05 resolvidos** (ver `DECISIONS_LOG` **D-q**): o rótulo é
> `PIB Total` e `baseCalculo=1` **só existe de 2014 em diante**, logo `0` é a única base com os 20
> anos do e-mail. **O Focus fica fora de `raw_series`** (**D-k**, 5 entradas em
> `TABELAS_FORA_DO_RAW_SERIES`): os 197 `series_id` são **compostos**
> (`FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>`) e não são entradas do catálogo — o catálogo registra o
> EntitySet, exatamente como no painel do Tesouro. F-015 o consome direto de
> `data/processed/focus/`. **`FOCUS_PIB_TOTAL` do catálogo virou `descartada`** (**D-p**), porque
> ficou redundante com G-04 resolvido. 2 rodadas `--offline` byte-idênticas.

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/focus`
- **Cobre:** RF-007 · e-mail: **A3**
- **CAs da SPEC:** CA-017, CA-018, CA-019

**DoR específica** — [x] 5 EntitySets confirmados com data de início; [x] pegadinhas mapeadas
(`$top` trunca, `$apply`/`$count` ignorados, capitalização variável); [x] **G-05** (`baseCalculo=0`,
porque `1` só existe desde 2014) e **G-04** (`PIB Total`, enumerado em `INDICADORES_ENUMERADOS`)
**resolvidos nesta feature** — D-q.

**Escopo incluído:** `ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`,
`ExpectativasMercadoTrimestrais`, `ExpectativasMercadoSelic`, `ExpectativasMercadoInflacao12Meses`;
filtro de `baseCalculo` único; normalização de nomes de campo; enumeração dos valores de `Indicador`
(resolve G-04).
**Excluído:** Top5; V1b vs. Focus (→ F-033); surpresa como feature de regime (fica em F-015/F-021).

**Arquivos (reais, como implementado):** `apps/pipeline/extract/bcb_focus.py`,
**`tests/unit/test_extract_bcb_focus.py`** (68 testes sem rede, 2 sob `-m network`),
`tests/fixtures/focus/` (12 fixturas reais + `README.md`),
**`docs/wiki/modules/focus.md`** (página própria, ≤ 60 linhas),
`apps/pipeline/canonical/build_raw_series.py` (+5 entradas de exclusão, D-k),
`tests/unit/test_canonical_raw_series.py` (fixture + teste de conjunto exato, renomeado),
`tests/contract/test_curva_contract.py` (o mesmo conjunto exato),
`packages/shared/schemas/series_catalog_data.py` (**1** entrada alterada, D-p).
**Saída:** `data/processed/focus/<EntitySet>.parquet` (5 arquivos, 628 KB) +
`data/raw/focus/` (184 páginas + 184 manifestos, 66 MB, no `.gitignore`).
**Comando:** `python -m apps.pipeline.extract.bcb_focus [--offline] [--series <EntitySet>] [--detalhar-series]`
**Doc do orquestrador:** `docs/wiki/modules/focus.md`, `DECISIONS_LOG §2.3` (D-k, D-p, D-q).

> **Ajuste do Feature Contract — caminhos e nomes (2026-10-11).** O contrato pedia
> `tests/contract/test_bcb_focus.py` e uma **seção Focus** em `docs/wiki/modules/sgs.md`; o briefing
> da onda mandou `tests/unit/test_extract_bcb_focus.py` + `tests/fixtures/focus/` + context pack, e
> **congelou** `docs/wiki/modules/`. Seguiu o briefing; no fechamento o conteúdo permanente foi para
> **`modules/focus.md`** (página nova, não seção da `sgs.md`, que ficou grande demais) e `sgs.md`
> passou a só apontar para ela. Nenhum CA mudou de enunciado.
>
> **Três acréscimos sancionados no fechamento:** as 5 entradas de `TABELAS_FORA_DO_RAW_SERIES`
> (**D-k**), `FOCUS_PIB_TOTAL` → `descartada` (**D-p**) e a renomeação de
> `test_descoberta_exclui_calendario_e_painel_do_tesouro` → `..._painel_do_tesouro_e_focus`, que é o
> teste do conjunto **exato** de exclusões (o nome mentia depois de D-k).

| Teste | Tipo | Cobre CA |
|---|---|---|
| `baseCalculo` 0 e 1 na mesma data → 1 linha no output | unit (seção de parse) | CA-017 |
| exatamente 20.000 linhas → `recusar_truncamento_silencioso` levanta | unit negativo | CA-018 |
| nomes de campo normalizados nos 5 EntitySets (`CAMPOS_CANONICOS`) | unit | CA-019 |
| `Indicador` enumerado e registrado (`INDICADORES_ENUMERADOS`, G-04) | unit + `network` | CA-019 |
| `$orderby` com `+` → HTTP 400 (fixture real do erro) | unit negativo | base |
| corpo `/*{erro}*/` sem `Content-Type` recusado por `validar_corpo_odata` | unit negativo | base |

**Anti-SPEC específica:** §10.1.5, base.

---

### [ ] F-011 — Contexto externo (FRED com fallback Yahoo) + teste de conectividade

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/contexto-externo` · prioridade **`should`**
- **Cobre:** RF-017 · e-mail: **C1**
- **CAs da SPEC:** CA-048, CA-049, CA-050

**DoR específica** — [x] IDs do FRED verificados; [x] fallback Yahoo mapeado (`^TNX`, `^VIX`,
`DX-Y.NYB`); [ ] **G-06** — conectividade do ambiente do Edu com o FRED **a testar antes de codar**
(na máquina da pesquisa 10/10 IDs falharam).

**Escopo incluído:** teste de conectividade como **primeiro passo** da feature; `DGS10`, `VIXCLS`,
`DFF`, `DTWEXBGS`, `T10YIE` com `cosd=1900-01-01`; fallback automático para Yahoo + registro em
`DECISIONS_LOG`; `UST10_BRL` convertido pela PTAX.
**Excluído:** ouro (**G-03**, sem fonte → `BLOQUEADO — FONTE INDISPONÍVEL`); risco-país (→ F-036);
`SP500`/`DJIA` do FRED (janela rolante de 10 anos, `descartada`).

**Arquivos:** `apps/pipeline/extract/fred.py`, `tests/contract/test_fred.py`,
`tests/unit/test_fallback_externo.py`, `tests/fixtures/fred/*.csv`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| conectividade falha → fallback Yahoo + registro | integration | CA-048 |
| `fredgraph.csv` sem `cosd` trunca (comprovado na fixture) | unit | CA-049 |
| ID inexistente devolve HTML → detectado por `<` | unit negativo | CA-049 |
| `GOLD_BRL` sem fonte → `BLOQUEADO — FONTE INDISPONÍVEL` | unit negativo | CA-050 |

**Anti-SPEC específica:** §10.1.1 (nenhum proxy silencioso para ouro), §10.1.3, base.

---

### [ ] F-012 — Extrator Teva: FII por segmento (Tijolo, Papel, Logística, Shoppings, Lajes)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/teva-fii` · prioridade **`should`**
- **Cobre:** RF-014 · e-mail: **B5**
- **CAs da SPEC:** CA-040, CA-041, CA-042
- **Decisão provisória que carrega:** `[PROVISÓRIO L2, D12]` — ADR-005 (uso qualitativo, 2019+,
  sem redistribuição). **Item de DoR: se L2 for negado, esta feature é cortada inteira.**

**DoR específica** — [x] bucket GCS listável e segmentos confirmados; [x] janela real 2019-01-02;
[ ] **L2 em aberto** (provedor privado sem licença comercial explícita) — padrão provisório em ADR-005.

**Escopo incluído:** listagem do bucket + **match por regex** no prefixo numérico (`3.2.2`, `3.2.1`,
`3.3.1`, `3.3.3`, `3.3.2`), download, parse (2 colunas), rótulo qualitativo e `licenca_restrita`.
**Excluído:** construção própria COTAHIST + CVM (→ F-038); redistribuição de qualquer forma.

**Arquivos:** `apps/pipeline/extract/teva.py`, `tests/contract/test_teva.py`,
`tests/fixtures/teva/*.parquet`, `docs/wiki/modules/b3.md` (seção FII).

| Teste | Tipo | Cobre CA |
|---|---|---|
| nome com versão (`v0.27`) é casado por regex, não hard-coded | contract | CA-040 |
| 02/01/2019 = 100 e ~1.937 linhas | contract | CA-041 |
| output carrega `data_inicio`, rótulo qualitativo e licença | unit | CA-042 |

**Anti-SPEC específica:** §10.3.15 (não redistribuir dado de terceiro), §10.2.8 (`n` sempre visível), base.

---

### [x] F-013 — Camada `raw_series` + `series_catalog` materializado — **classe C** — **QA APROVADO (ver §3)**

> **Estado (2026-10-11):** implementada; o QA independente deu **`MUDANÇAS_SOLICITADAS`**
> (`docs/plans/qa/ONDA-2-QA-F013.md`: 3 × P1, 7 × P2, **0 × P0**, com o número central confirmado) e
> as **MUDANÇAS_SOLICITADAS foram atendidas no commit `3265499`** — P1-1 (`versao_build` cego ao
> catálogo → hash do **conjunto** `MODULOS_DO_BUILD` + `versao_build_componentes` +
> `catalogo_sha256`), P1-2 (`calendario` fora do materializado → coluna no `SeriesCatalogSchema`,
> artefato com **26** colunas), P1-3 (dedup cegando CA-077 → divergência medida nas **8** colunas e
> guardas antes do dedup) e P2-1/P2-2/P2-3/P2-7, cada um com teste de regressão. `data/canonical/`
> foi **reconstruído** depois de F-014/F-016: **62** séries, **278.439** linhas,
> `versao_build 867ecc90…`. **Falta o re-QA** (os números de `docs/plans/qa/ONDA-2-QA-F013.md` são do
> acervo de 51 séries) e a P2-4 (limiar de `pct_nulos`) segue aberta em §6.

- **Risco:** **C** · **CI alvo:** N2 (parcial — marker `integration` inexistente, ver §6) · **Branch:** `feat/camada-raw-series`
- **Cobre:** RF-019, RF-020, RF-026, RF-047 · e-mail: todos
- **CAs da SPEC:** CA-053..058, CA-075..077, CA-120

**DoR específica** — [x] schemas prontos (`raw_series.py`, `series_catalog.py`, `series_catalog_data.py`
— **138** séries validadas na reconstrução de 2026-10-11); [x] ADR-006 (Parquet + DuckDB) proposto;
[ ] ADR-006 **validado pelo Edu** antes do merge (é a base da camada canônica) — **desenvolvimento
liberado, aceite formal pendente** (§4).

**Escopo incluído:** carga de todos os `data/processed/` para `raw_series` (Parquet) na granularidade
nativa; materialização do `series_catalog`; portão pandera na entrada/saída de `data/canonical/`;
coluna de origem obrigatória; DuckDB derivado (opcional, regenerável).
**Excluído:** qualquer agregação trimestral (→ F-014/F-015).

**Arquivos (reais, como implementado):** `apps/pipeline/canonical/__init__.py`,
`apps/pipeline/canonical/build_raw_series.py` (o build inteiro: descoberta, carga, consolidação, as
4 guardas, catálogo materializado, escrita, DuckDB, relatório, CLI),
`packages/shared/schemas/series_catalog.py` (**+`SeriesCatalogMaterializedSchema`** e **+ coluna
`calendario`** em `SeriesCatalogSchema`; `RawSeriesSchema` intocado),
`packages/shared/schemas/__init__.py` (+1 export), `tests/unit/test_canonical_raw_series.py`
(34 testes em 3 seções + regressões pós-QA), `tests/contract/test_raw_series_schema.py` (25 testes —
**primeiro** arquivo de `tests/contract/` do projeto), `tests/fixtures/canonical/README.md`.
**Saída:** `data/canonical/{raw_series.parquet, series_catalog.parquet, relatorio_build.json,
ldc.duckdb}` — 278.439 linhas / 62 séries / 1979-12-31 → 2026-10-10; catálogo **138 × 26**; DuckDB
com as **views** `raw_series` e `series_catalog`.
**Comando:** `python -m apps.pipeline.canonical.build_raw_series [--offline] [--sem-duckdb]`
**Doc do orquestrador:** `docs/contracts/CONTRACTS.md §1.1/§2.4`, `docs/wiki/modules/canonical.md`.

> **Ajuste do Feature Contract — caminhos (2026-10-11).** O contrato pedia
> `apps/pipeline/load/raw_series.py` + `apps/pipeline/load/catalog.py`; o briefing da onda fixou
> `apps/pipeline/canonical/` e a CLI `python -m apps.pipeline.canonical.build_raw_series` — a pasta
> casa com a saída e com `docs/wiki/modules/canonical.md`. **Um** módulo, não dois, porque a
> materialização do catálogo lê o **mesmo** DataFrame consolidado (separar criaria uma segunda
> travessia de `data/processed/`). `tests/integration/test_camada_raw.py` virou a **seção C** de
> `tests/unit/test_canonical_raw_series.py`: o marker `integration` não existe em `pyproject.toml`
> (congelado nesta onda, com `--strict-markers`) e `@pytest.mark.integration` falharia a coleta —
> dívida em §6. Nenhum CA muda; o QA da Onda 2 aceitou os três desvios.

| Teste | Tipo | Cobre CA |
|---|---|---|
| duas extrações coexistem como `vintage` distintos | integration | CA-056 |
| linha sem `source`/`series_id` → `SchemaError` | contract negativo | CA-057 |
| série trimestral não pode ser gravada fora da freq nativa | unit negativo | CA-058 |
| catálogo valida: 0 identificador vazio; `a_confirmar` ⇒ status | contract | CA-053, CA-054 |
| procedência de toda linha longa (`source`/`series_id`/`vintage`/`collected_at`) resolve para a URL do catálogo | integration | CA-055, CA-120 |
| lacuna sem substituto → `BLOQUEADO — FONTE INDISPONÍVEL` | unit negativo | CA-076 |

**Anti-SPEC específica:** §10.1.1, §10.1.2, §10.4.24 (sem coluna ad hoc), §10.4.28 (nativa, não trimestral).
**Extra de classe C:** diff numérico vs. versão anterior + reconstrução completa + **revisão numérica
independente** (quem escreveu não confere).

---

### [x] F-014 — Alinhamento trimestral (fim de período, ffill <= 5 d.u.) — **classe C** — **QA APROVADO (ver §3)**

> **Estado (2026-10-11):** implementada, **QA pendente**. Materializa a tabela intermediária
> **`alinhado_trimestral`** (`data/canonical/alinhado_trimestral.parquet`, **4.038** linhas · 49
> séries · 83 trimestres) + `relatorio_alinhamento.json`. **D-h decidida: opção (a)** — grade
> bancária única, com **215** células de `ffill_dias_uteis = 1` (5,325% de 4.038), todas em séries
> `B3_API`, nos 20 quartos trimestres de 2006 a 2025, **nenhuma** com ffill 2..5. **7** células
> nulas (PIB SGS/SIDRA e IBC-Br em 3T2026), todas com `motivo_nulo` e a lacuna registrada. O
> contrato novo está em `docs/contracts/CONTRACTS.md §8`.

- **Risco:** **C** · **CI alvo:** N2 (parcial — ver §6) · **Branch:** `feat/alinhamento-trimestral`
- **Cobre:** RF-023 · e-mail: base de A/B/C
- **CAs da SPEC:** CA-065..068 **+** CA-061/063/076/077/120 **por tabela** (nenhum CA novo criado)
- **Depende de:** F-008 (calendário), F-013 (raw_series)

**DoR específica** — [x] convenção congelada em ADR-006 (último dia útil, ffill <= 5, encadeamento
geométrico); [x] calendário ANBIMA disponível (`data/processed/calendario/dias_uteis_anbima.parquet`,
F-008: 2001→2030, 7.530 d.u.); [ ] ADR-006 validado pelo Edu — **desenvolvimento liberado, aceite
formal pendente** (§4), e **esta feature é a parte (b) do ADR**; **[x] decisão explícita sobre a
grade das séries da B3 (D-h): escolhida a opção (a)**, registrada em `DECISIONS_LOG §2.1` e no dado
(`relatorio_alinhamento.json → decisao_d_h`).

> **D-h — a B3 fecha em dias que o calendário bancário considera úteis.** Medido por F-008 contra
> 20 anos de série: o conjunto de dias úteis da ANBIMA é **idêntico** ao do CDI (SGS 12) e ao do
> IMA-B em 2006-2025 (5.022 × 5.022, zero diferença nas duas pontas), mas o IBOV tem **4.953** —
> **B3 ⊂ ANBIMA em 69 datas**, nunca o contrário. As 69 são feriados municipais/estaduais de São
> Paulo e os dias de emenda de fim de ano: 24/12 (14×), 31/12 (14×), 25/01 Aniversário de SP (12×),
> 20/11 (11×, antes de ser nacional), 09/07 Revolução Constitucionalista (11×), 29 e 30/12 (3×
> cada) e 12/06/2014.
>
> **Consequência:** em **20 dos 83 trimestres** — **todos os 4ºs trimestres de 2006 a 2025** — o
> último dia útil pela ANBIMA **não tem observação da B3**. Nenhum outro trimestre tem o problema,
> e o CDI tem observação nos 83. Então **toda série da B3 vai carregar `ffill_dias_uteis = 1` em
> todo 4T** — é o caso que ADR-006 §(b).8 / CA-066 já resolvem, mas tem de ser **escolhido**, não
> descoberto no meio do cálculo:
>
> - **(a) default do ADR-006:** manter o fim de período bancário e aceitar 1 d.u. de ffill nas
>   séries da B3 no 4T. Uma grade só para macro e ativos; o ffill fica registrado em
>   `macro_quarterly_provenance` e aparece na página de limitações.
> - **(b) grade própria da B3:** usar a última negociação da B3 para séries da B3. Elimina o ffill
>   e cria **duas grades** de fim de trimestre — o que exige declarar, em toda tabela e figura, qual
>   grade cada linha usa.
>
> Escolher **(b) é decisão de alinhamento, classe C, e não é do extrator**. O calendário entrega as
> duas: `ajustar_para_tras` dá a grade bancária e `dia_util_anterior(d, 1)` dá o passo de ffill.
> Detalhe completo em `docs/wiki/modules/calendario.md` e `docs/wiki/modules/canonical.md`.
>
> **RESOLVIDO em 2026-10-11 — escolhida a (a)** (orquestrador, provisória, aval do Edu pendente;
> `DECISIONS_LOG §2.1`). Custo medido no acervo: **215** células com `ffill_dias_uteis = 1` de 4.038
> (**5,325%**), em **11** séries `B3_API` e **20** trimestres (`2006Q4..2025Q4`); **zero** célula com
> ffill 2..5, **zero** série não-B3 com ffill. (b) trocaria um erro de **1 dia útil, medido e visível
> por linha**, por **duas réguas de tempo** no mesmo dataset — toda tabela e toda figura passariam a
> ter de declarar qual grade a linha usa, e o `join` entre `macro_quarterly` e
> `asset_returns_quarterly` deixaria de ser por `quarter_end`. O check
> `quarter_end_unico_por_trimestre` de `AlinhadoTrimestralSchema` **trava** a escolha no contrato:
> virar para (b) exige mudar o schema, não só o código. Os 215 ffill vão para a página de limitações
> (F-028).

**Escopo incluído:** cálculo do `quarter_end` dos 83 trimestres; reindexação de séries diárias/mensais
para a grade; `ffill_dias_uteis`; `NULL` registrado acima de 5 d.u.; detecção de data duplicada/fora
de ordem.
**Excluído:** cálculo de retorno (→ F-017); regra anti-look-ahead (→ F-018).

**Arquivos (reais, como implementado):** `apps/pipeline/canonical/alinhamento.py` (grade, as 3
réguas, ffill, painel desbalanceado, guardas, relatório, CLI),
`packages/shared/schemas/alinhado_trimestral.py` (**+1 módulo**: `AlinhadoTrimestralSchema`, 18
colunas, 11 checks de DataFrame), `packages/shared/schemas/__init__.py` (+1 import / +12 `__all__`),
`tests/unit/test_canonical_alinhamento.py` (**72** testes em 5 seções),
`tests/contract/test_alinhamento_schema.py` (**34** testes — 1 regra quebrada por teste).
**Saída:** `data/canonical/alinhado_trimestral.parquet` (4.038 linhas, 55.813 B) +
`data/canonical/relatorio_alinhamento.json` (grade dos 83, ffill por série **e** por trimestre,
1 bloco por série, `decisao_d_h`).
**Comando:** `python -m apps.pipeline.canonical.alinhamento [--offline]`
**Doc do orquestrador:** `docs/contracts/CONTRACTS.md §8`, `docs/wiki/modules/canonical.md`.

> **Ajuste do Feature Contract — caminhos, nomes e artefato novo (2026-10-11).** (i) O contrato
> pedia `apps/pipeline/transform/alinhamento.py`; implementado em
> `apps/pipeline/canonical/alinhamento.py`, que é onde F-013 mora e de onde `alinhar_series` é
> importado (`transform/` ficou com `cambio.py`, D-g). (ii) `tests/unit/test_alinhamento.py` →
> **`tests/unit/test_canonical_alinhamento.py`**, casando com `test_canonical_raw_series.py` (F-013)
> e `test_canonical_curva.py` (F-016). (iii) `tests/integration/test_grade_trimestral.py` virou as
> seções D e E do teste unitário — mesma causa de F-013 (marker `integration` inexistente, §6).
> (iv) **A tabela `alinhado_trimestral` é nova no contrato:** o `TODO.md` descrevia F-014 como
> "reindexação", sem nomear artefato. Materializá-la (em vez de alinhar dentro de F-015/F-017) foi
> escolha do implementador, por três motivos — o diff numérico de classe C passa a ser uma
> **igualdade** verificável célula a célula contra `raw_series`; F-015/F-016/F-017 consomem **a
> mesma** régua em vez de três cópias da regra; e o `ffill` fica auditável **por célula** antes de
> virar retorno (é o que a página de limitações de F-028 precisa citar). Custo: 55 KB em
> `data/canonical/` e a §8 nova em `CONTRACTS.md`. **Aceito pelo orquestrador.** Se algum dia
> preferir a tabela só em memória, basta não gravar: `alinhar_series` já é pura.

| Teste | Tipo | Cobre CA |
|---|---|---|
| os 83 `quarter_end` caem em dia útil (inclui casos-armadilha) | unit | CA-065 |
| ativo sem negociação no fechamento → ffill <= 5 d.u. registrado | unit | CA-066 |
| lacuna > 5 d.u. → `NULL`, nunca preenchida | unit negativo | CA-067 |
| datas duplicadas com valor divergente → falha ruidosa | unit negativo | CA-068 |

**Anti-SPEC específica:** §10.1.1, §10.4.28, §10.2.7 (base do `asof`).
**Extra de classe C:** diff numérico + reconstrução + revisão independente.

---

### [x] F-015 — `macro_quarterly` com 83 trimestres — **classe C** — **QA APROVADO (ver §3)**

> **Estado (2026-10-11):** implementada, **QA e revisão numérica independente pendentes**.
> `macro_quarterly.parquet` com **83 × 42** (`2006Q1..2026Q3`, materialização **`revised`**,
> `sha256 bcb31e92…` depois do rebuild de fechamento da Onda 3; era `dcded731…`), a companheira `macro_quarterly_provenance.parquet` com **2.548** linhas
> (**32** colunas rastreáveis, **20** séries de origem, CA-120 por anti-join nas **duas** direções)
> e `relatorio_macro.json` com nulos **por coluna com motivo**, unidades, 4 canários, bloco
> anti-look-ahead e a sensibilidade do hiato. 2 rodadas byte-idênticas.
> **Só 5 colunas são 100% nulas**, todas por gap declarado: `ipca_meta`/`ipca_desvio_meta` (G-02),
> `embi_br_fim`/`embi_delta_tri` (L8) e `termos_troca_yoy` (sem fonte; proxy IC-Br em §6).
> **CA-007 não é satisfazível** com o IBC-Br real (começa em 2003): `ibcbr_gap` fica com **16**
> nulos e a V1 de F-019 classifica **67** dos 83 trimestres — **D-m**, SPEC **não** editada, a
> alternativa (`min_periods = 8`, recupera 12) está **medida** no relatório. Decisões que carregam
> número: grade de **apoio** `2001Q1..2005Q4` conferida célula a célula contra F-014 (**913
> células, 0 divergências**); **todo nível é a célula de F-014 bit a bit**; acumulação **geométrica**
> e só com trimestre completo (**0** incompletos nos 83); Focus lido de `data/processed/focus/` com
> a régua "coleta do início de T" e troca `H0`→`H1` no 1º trimestre; `ciclo_selic` é **função
> publicada, não coluna**. **`INCLINACAO_REAL_5A_3A` não ganhou coluna** (**D-n**) — F-019/F-021
> leem a série. **Unidade: por cento/pp** (**D-o**), contra a fração de F-017.
> **Evidência cruzada mais forte:** F-017 recalculou `cdi_tri` e `ipca_tri` em **outro módulo, por
> outro agente**, sem ler esta tabela → `max |macro − 100 × retornos| = 0,0` nos **83** trimestres.

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/macro-quarterly`
- **Cobre:** RF-021 · e-mail: **A1-A7**
- **CAs da SPEC:** CA-059, CA-060, CA-061, **CA-120** (+ CA-007, CA-044)
- **Depende de:** F-003, F-004, F-010, F-013, F-014, F-016

**DoR específica** — [x] schema `MacroQuarterlySchema` pronto; [x] todas as colunas com série de origem
mapeada no catálogo; [x] colunas que dependem de gap aberto (`ipca_meta` → G-02; `embi_br_fim` → L8;
`termos_troca_yoy` → proxy IC-Br) entraram **nulas e declaradas**, nunca estimadas — são as 5 colunas
100% nulas, cada uma com o motivo no `relatorio_macro.json`.

**Escopo incluído:** montagem das ~40 colunas; `ibcbr_gap` (desvio da média móvel de 20 trimestres);
`ipca_12m_delta`; `selic_meta_delta`; `juro_real_exante`; `is_estimated` para `2026Q3`; `fonte_versao`;
**materialização da tabela companheira `macro_quarterly_provenance`** (PK `(quarter, column)`), que é
como CA-120 é cumprido numa tabela wide (`CONTRACTS.md §3.1`).
**Excluído:** classificação de regime (→ F-019); materialização `asof` (→ F-018).

**Arquivos (reais, como implementado):** `apps/pipeline/canonical/macro_quarterly.py` (a feature
inteira: transformações puras, grade de apoio, acumulação, procedência, relatório, CLI),
`tests/unit/test_canonical_macro_quarterly.py` (4 seções → **68** testes),
`tests/contract/test_macro_quarterly_contract.py` (3 seções → **69** testes).
**Nenhum schema alterado** (`MacroQuarterlySchema` e `MacroQuarterlyProvenanceSchema` já estavam
exportados e nenhuma constante nova foi necessária).
**Saída:** `data/canonical/macro_quarterly.parquet` (83 × 42) +
`macro_quarterly_provenance.parquet` (2.548 × 8) + `relatorio_macro.json`.
**Comando:** `python -m apps.pipeline.canonical.macro_quarterly --offline`
**Doc do orquestrador:** `docs/contracts/CONTRACTS.md §3/§3.1`, `docs/wiki/modules/canonical.md`,
`DECISIONS_LOG §2.3` (D-m, D-n, D-o).

> **Ajuste do Feature Contract — caminhos e nomes (2026-10-11).** O contrato pedia
> `apps/pipeline/transform/macro_quarterly.py`, `tests/contract/test_macro_quarterly.py` e
> `tests/integration/test_build_macro.py`; o briefing da onda mandou `apps/pipeline/canonical/`
> (onde F-013/F-014/F-016 moram e de onde `alinhar_series` é importado) e os nomes
> `test_canonical_macro_quarterly.py` / `test_macro_quarterly_contract.py`. A cobertura de
> integração está nas seções C (build e2e em `tmp_path`) e D (acervo real) do teste unitário —
> `tests/integration/` segue vazio e o marker `integration` **não existe** em `pyproject.toml`
> (congelado, com `--strict-markers`): é a mesma nota de F-013 §7, F-014 §7.1 e F-017.
> Nenhum CA mudou de enunciado.

| Teste | Tipo | Cobre CA | Resultado |
|---|---|---|---|
| exatamente 83 linhas, `2006Q1`..`2026Q3`, sem repetir | contract | CA-059 | ✔ |
| `2026Q3` com `is_estimated=True`, demais `False` | unit | CA-060 | ✔ |
| coluna sem cobertura → `NULL`, nunca interpolada | unit negativo | CA-061 | ✔ (5 colunas) |
| `ibcbr_gap` existe nos 83 trimestres ou marca `is_estimated` | unit | CA-007 | **não fecha — D-m**, 16 nulos aceitos e medidos; a aritmética está travada em teste |
| toda célula não nula de coluna rastreável tem linha em `macro_quarterly_provenance` (anti-join vazio) | contract | CA-120 | ✔ nas 2 direções |
| variação por **razão** difere da diferença de níveis | unit negativo | CA-044 | ✔ |
| acumulação geométrica **não** é soma (`ipca_tri`, `cdi_tri`) | unit negativo | CA-070 | ✔ |
| média móvel de 20 exige **janela cheia** (`min_periods`) | unit negativo | CA-007 | ✔ |
| o módulo de produção **não lê o relógio** | unit | CA-121 | ✔ |
| apoio divergente de `alinhado_trimestral` **para o build** | unit negativo | CA-061 | ✔ (`ApoioDivergente`) |

**Anti-SPEC específica:** §10.1.1, §10.4.24.
**Extra de classe C:** diff numérico + reconstrução + revisão independente — **o material da revisão
está no `ONDA-2-QA-A.md` e no relatório** (4 canários conferidos na fonte, diff numérico por conta
independente, reprodução cruzada por F-017, hashes de 2 rodadas).

---

### [x] F-016 — Curva: vértices fixos interpolados + inclinação — **classe C** — **QA APROVADO (ver §3)**

> **Estado (2026-10-11):** implementada, **QA pendente**. Grava **11** séries em
> `data/processed/curva/` (5.436 linhas cada, `fonte=DERIVADO`) + `relatorio_curva.json`, e já entrou
> no rebuild do canônico (62 séries). **CA-025 não fechava** com o vértice curto de 1 ano (60,53% das
> datas base de 2006 em diante, contra os ≥ 95% do CA) — resolvido por **D-i**: o catálogo foi de
> **134 → 138** (`CURVA_REAL_3A`, `CURVA_NOMINAL_3A`, `INCLINACAO_REAL_5A_3A`,
> `INCLINACAO_NOMINAL_5A_3A`) e **`INCLINACAO_REAL_5A_3A` (95,25%) passa a ser a variável principal
> de regime**, com as duas 5a−1a publicadas como **secundárias e declaradas**. Os dois números estão
> **travados por teste**; a SPEC **não** foi editada. **D-i é provisória: aguarda o Edu** e uma nota
> em ADR-004 §3 (§4). As 7 séries que já existiam saíram com `sha256` **idêntico** — o acréscimo não
> mexeu em nenhum número publicado.

- **Risco:** **C** · **CI alvo:** N2 (parcial — ver §6) · **Branch:** `feat/curva-inclinacao`
- **Cobre:** RF-009 · e-mail: **A6**
- **CAs da SPEC:** CA-023..026 — **CA-023 cumprido na íntegra** (os 6 vértices de 1, 3 e 5 anos no
  catálogo e gravados), **CA-024 quantificado** (nominal 10a: 36,81% das datas base de 2006+, medido
  e **não** gravado, `VERTICES_FORA_DO_CATALOGO`), **CA-025 fechado pela série nova de D-i**
- **Decisão provisória que carrega:** `[PROVISÓRIO L4]` — ADR-004 (Tesouro Direto em vez de ETTJ ANBIMA).
  **Item de DoR:** se o Edu optar por contratar o ANBIMA Feed, esta feature vira **classe D**
  (credencial/API paga) e a implementação da fonte muda.
- **Depende de:** F-005

**DoR específica** — [x] método definido (A5.4 da pesquisa); [x] limitação L5 (sem vértice nominal de
10 anos antes de ~2010) registrada e **quantificada**; [ ] **L4 em aberto** — ADR-004 em Proposta,
**desenvolvimento liberado, aceite formal pendente** (§4). **Depois de gravar `data/processed/curva/`,
reexecutar o build de F-013** — `raw_series.parquet` é reescrito inteiro, não há `append` (feito em
2026-10-11).

**Escopo incluído:** interpolação para 1, 3 e 5 anos (real e nominal) por data; flag
`vertice_extrapolado`; `NULL` quando o prazo-alvo não existe; `inclinacao_real_5a_3a` (**principal
desde D-i**), `inclinacao_real_5a_1a` e `inclinacao_nominal_5a_1a` (secundárias),
`inclinacao_nominal_5a_3a`, `breakeven_5a` (por razão); agregação para o último dia útil do trimestre.
**Excluído:** curva Svensson oficial da ANBIMA (paga); DI futuro via `pyield` (fase 2 — exige Python 3.12);
vértices de **10 anos** (medidos, **não** gravados — CA-024/CA-055).

**Arquivos (reais, como implementado):** `apps/pipeline/canonical/curva.py` (núcleo `interpolar`,
famílias, derivadas, CLI), `tests/unit/test_canonical_curva.py` (36 funções → **59** casos),
`tests/contract/test_curva_contract.py` (13 funções → **31** casos: schema, catálogo e **as 4 guardas
de F-013**), `packages/shared/schemas/series_catalog_data.py` (**+4 entradas**, D-i — só acréscimo;
mais a substituição do `obs` de `INCLINACAO_REAL_5A_1A`, feita pelo orquestrador no fechamento),
`tests/unit/test_schemas_smoke.py` (`N_SERIES_ESPERADAS` 134 → **138**).
**Saída:** `data/processed/curva/<series_id>.parquet` (11 séries × 5.436 linhas) +
`data/processed/curva/relatorio_curva.json` (flag `vertice_extrapolado`, motivos, `%` de nulos por
ano, cobertura, canários).
**Comando:** `python -m apps.pipeline.canonical.curva [--offline] [--metrica-prazo dias_uteis]`
**Doc do orquestrador:** `docs/contracts/CONTRACTS.md §2.1`, `docs/wiki/modules/tesouro.md`.

> **Ajuste do Feature Contract — caminhos e nomes (2026-10-11).** O contrato pedia
> `apps/pipeline/transform/curva.py`, `tests/unit/test_curva.py` e
> `tests/contract/test_curva_vertices.py`; o briefing da onda mandou
> `apps/pipeline/canonical/curva.py`, `tests/unit/test_canonical_curva.py` e
> `tests/contract/test_curva_contract.py` — é onde F-013 vive e onde o build varre. Seguiu o
> briefing. Dois acréscimos **sancionados**: as 4 entradas de catálogo de D-i (acréscimo puro) e o
> bump de `N_SERIES_ESPERADAS`. Nenhum CA muda de enunciado.
>
> **Prazo em dias corridos (ACT), não em dias úteis — decisão de método, registrada como D-j.** Os
> dois métodos estão implementados (`MetricaPrazo`); o padrão é ACT por **cobertura**, não por
> preferência: o calendário de F-008 cobre 2001→2030 e **levanta** fora disso, enquanto os
> vencimentos do painel chegam a 2060 — devolver `NULL` por limite do *nosso* calendário, e não por
> ausência de título, seria mentir sobre o suporte do dado. Custo medido: mediana de **0,14 a 0,41
> bps** de diferença entre as duas métricas, contra **dezenas** de bps de spread de varejo que
> ADR-004 já declara; em dias úteis as séries de 5 anos **perderiam 298 a 700 datas base**.

| Teste | Tipo | Cobre CA |
|---|---|---|
| vértice fora do intervalo de vencimentos → flag `True` | unit | CA-023 |
| vértice nominal de 10 anos em 2006 → `NULL` + flag | unit negativo | CA-024 |
| inclinação real existe em >= 95% dos d.u. de 2006-2026 | integration | CA-025 |
| valor trimestral é o do último dia útil | unit | CA-026 |
| breakeven por razão, não por subtração | unit negativo | CA-026 |

**Anti-SPEC específica:** §10.1.1 (sem extrapolação silenciosa), §10.2.13 (razão), §10.3.19 (registrar
substituição de fonte), §10.3.14 (nada pago).
**Extra de classe C:** diff numérico + reconstrução + revisão independente + entrada no `DECISIONS_LOG`.

---

### [x] F-017 — `asset_returns_quarterly`: retornos, excesso sobre CDI e real — **classe C** — **QA APROVADO (ver §3)**

> **Estado (2026-10-11):** implementada, **QA e revisão numérica independente pendentes**.
> `asset_returns_quarterly.parquet` com **1.963 linhas** · **24** ativos · 83 trimestres
> (`sha256 c055ac81…` depois do rebuild de fechamento da Onda 3; era `ab61eeca…`, e só `fonte_versao` mudou) + `relatorio_retornos.json` (cobertura por ativo, nulos **por coluna com
> motivo**, CDI e IPCA por trimestre em `bases_por_trimestre`, as 11 convenções em texto).
> **`USDBRL` entrou por D-l** (+83 linhas, `is_total_return = False` declarado no catálogo — câmbio
> não tem carrego): é o que RF-038 precisa, e a PTAX já tinha os 83 trimestres alinhados. Os **8**
> `asset_id` que seguem fora têm motivo nomeado em `ATIVOS_FORA_DO_UNIVERSO`, publicado no
> relatório. Decisões que carregam número: níveis **sempre** de `alinhado_trimestral` (nunca
> relidos de `raw_series`); **1º trimestre de cada série sem retorno** (23 linhas, `NULL` com motivo,
> mas **com** `price_fim`); **CDI por acumulação diária** da SGS 12, por isso é o **único** ativo com
> retorno em `2006Q1`; excesso e real pela **mesma** função de razão `(1+r)/(1+b)−1`; `ret_real`
> pelo IPCA dos 3 meses de **referência**, aplicado uma vez; `is_total_return` **propagado do
> catálogo, nunca inferido** (820 nulos nomeados — G-01 + CDI); painel **desbalanceado** (ICON
> 2006Q4, IMOB 2007Q4, IFIX 2010Q4). **Unidade: fração** (**D-o**), contra o por cento de F-015.
> 2 rodadas byte-idênticas. **Pendência que bloqueia merge, não implementação: ADR-006 e ADR-005
> seguem em `Proposta`** (§4).

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/asset-returns`
- **Cobre:** RF-022, RF-024, RF-026 · e-mail: **B1-B5, C1**
- **CAs da SPEC:** CA-062..064, CA-069..071
- **Depende de:** F-002, F-003, F-006, F-007, F-012, F-013, F-014

**DoR específica** — [x] schema pronto com 32 `asset_id`; [x] CDI trimestral validado (F-003);
[x] convenção de razão congelada em ADR-006 (**mas o ADR segue em `Proposta`** — §4);
[x] `is_total_return` dos setoriais da B3 = **G-01**, entrou `None` e declarado (820 linhas, motivo
nomeado no relatório).

**Escopo incluído:** `ret_tri` por razão de preços no último DU; `ret_excesso_cdi` e `ret_real` **por
razão**; `vol_intra_tri` e `dd_intra_tri` do diário; `n_dias_uteis`; `ffill_dias_uteis`;
`data_inicio_serie`; painel **desbalanceado** (sem linha antes do início da série); **`USDBRL`
(D-l)**. `SP500_BRL`/`ACWI_BRL` são alinhadas **aqui**, porque F-014 deixa `source=DERIVADO` fora do
build dela de propósito e quem alinha é a feature dona da derivação.
**Excluído:** métricas por regime (→ F-022); hedge cambial detalhado (D7 → fase 2 parcial em F-026);
anualização e Sharpe (Anti-SPEC §10.2.11).

**Arquivos (reais, como implementado):** `apps/pipeline/canonical/retornos.py` (universo, razão de
níveis, CDI por acumulação, excesso/real por razão, métricas intra, relatório, CLI),
`tests/unit/test_canonical_retornos.py` (**56** testes em 5 seções),
`tests/contract/test_asset_returns_contract.py` (**37** testes — 1 regra quebrada por teste),
`packages/shared/schemas/__init__.py` (**acréscimo** de 5 nomes já definidos em
`asset_returns_quarterly.py`: `ATIVOS_*`, `N_MINIMO_ATIVOS` — **nenhum schema alterado**),
`packages/shared/schemas/series_catalog_data.py` (`is_total_return=False` em `BCB_SGS_1`, D-l).
**Saída:** `data/canonical/asset_returns_quarterly.parquet` (1.963 × 16) +
`relatorio_retornos.json`.
**Comando:** `python -m apps.pipeline.canonical.retornos --offline`
**Doc do orquestrador:** `docs/contracts/CONTRACTS.md §4`, `docs/wiki/modules/canonical.md`,
`DECISIONS_LOG §2.3` (D-l, D-o).

> **Ajuste do Feature Contract — caminhos, nomes e colunas (2026-10-11).** O contrato pedia
> `apps/pipeline/transform/retornos.py`, `tests/unit/test_retornos.py`,
> `tests/contract/test_asset_returns.py` e `tests/integration/test_build_retornos.py`; o briefing da
> onda mandou `apps/pipeline/canonical/retornos.py`, `test_canonical_retornos.py` e
> `test_asset_returns_contract.py`, e a cobertura de integração está nas seções D (build e2e em
> `tmp_path`, com as **27 séries sintéticas** necessárias para os ≥ 18 `asset_id`) e E (acervo real)
> — `tests/integration/` segue vazio e o marker `integration` **não existe** em `pyproject.toml`.
> **Coluna:** o contrato citava `excesso_cdi` / `ret_cdi_tri`; o schema é `strict` com 16 colunas
> fixas e a coluna é **`ret_excesso_cdi`** — **`ret_cdi_tri` não existe**, porque o CDI do trimestre
> é uma **linha** (o `asset_id` CDI) e também está no relatório (`bases_por_trimestre`).
> **CAs:** os 6 do contrato **+** CA-014/015/016, reaproveitados sobre a acumulação de produção do
> CDI. Nenhum CA mudou de enunciado, e **nenhuma edição de contrato foi necessária** em
> `CONTRACTS.md §4` além da nota de unidade e do estado medido, acrescentados no fechamento.
>
> **Acréscimo sancionado no fechamento: D-l** — `USDBRL` no universo (23 → **24** ativos,
> 1.880 → **1.963** linhas) com `is_total_return=False` no catálogo. Zero mudança de schema e de
> regra; o único ajuste de teste foi deduplicar `BCB_SGS_1` no acervo sintético, que agora está no
> universo **e** no portão `SERIES_EXIGIDAS` de F-014.

| Teste | Tipo | Cobre CA | Resultado |
|---|---|---|---|
| >= 18 `asset_id` distintos, todos no catálogo | contract | CA-062 | ✔ 24 |
| nenhuma linha antes de `data_inicio_serie` (IFIX, ICON, IMOB) | contract negativo | CA-063 | ✔ |
| **excesso por razão: r=0,10 e cdi=0,0325 → 0,06538**, não 0,0675 | unit | CA-069 | ✔ |
| subtração no lugar da razão **faz o teste falhar** | unit negativo | CA-069 | ✔ (no acervo: 0,138 pp médios, 1,495 pp máx.) |
| acumulação intra-trimestre é geométrica, não soma | unit | CA-070 | ✔ (produto dos fatores diários == `ret_tri`, erro ≤ 1e-15) |
| IPCA aplicado uma única vez (teste de dupla deflação) | unit negativo | CA-071 | ✔ |
| price x total return sem flag → falha | unit negativo | CA-064 | ✔ |
| CDI de 2006 encadeado = **15,027140 %** em **249** d.u. | unit (fixture versionada) | CA-014/015 | ✔ bate com os 15,03 % publicados |
| CDI 4T2008 pela **SGS 4389** (outra série, outra unidade) | unit | CA-016 | ✔ `dif = 4,8e-6 pp` |
| janela do CDI == `(quarter_end(T−1), quarter_end(T)]` | unit (acervo) | CA-070 | ✔ 82/82, 0 divergências |

**Anti-SPEC específica:** §10.2.13 (razão), §10.2.12 (TR vs. PR), §10.1.1, §10.2.11 (Sharpe não é
implementável).
**Extra de classe C:** diff numérico + reconstrução + revisão independente — **o material da revisão
está no `ONDA-2-QA-B.md` e no relatório**, que listam onde o cálculo pode estar errado **sem o teste
pegar** (9 itens, para o Validation Mode).

---

### [~] F-018 — Regra anti-look-ahead + materializações `asof` / `revised` — **classe C** — **implementada — QA pendente**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/anti-look-ahead`
- **Cobre:** RF-025 · e-mail: base metodológica
- **CAs da SPEC:** CA-072, CA-073, CA-074 (+ CA-010)
- **Depende de:** F-015
- **Context pack (vivo até o QA aprovar):** `docs/wiki/context/F-018.md`

**DoR específica** — [x] `lag_divulgacao_dias` no catálogo para todas as séries; [x] regra definida
(PIB/IBC-Br de T−1; IPCA do penúltimo mês de T; Focus/Selic/curva/câmbio livres);
[x] colunas `lag_adjusted` e `trocou_vs_revised` no schema.

**Escopo incluído:** materialização `macro_quarterly_asof` (default para decisão) e
`macro_quarterly_revised`; cálculo e **publicação** do % de trimestres que trocam de regime; aviso
explícito se > 25%.
**Excluído:** relatório completo de divergência de classificação (→ F-034, fase 2).

**Arquivos REAIS** (os do contrato eram `apps/pipeline/transform/asof.py`,
`tests/unit/test_asof.py`, `tests/integration/test_divergencia_lookahead.py` — divergência
sancionada em **D-x**, `apps/pipeline/transform/` não existe na árvore):
`apps/pipeline/canonical/asof.py` (1.353 L) · `tests/unit/test_canonical_asof.py` (**35** testes) ·
`tests/contract/test_asof_contract.py` (**22** testes) ·
`packages/shared/schemas/macro_quarterly.py` (**acréscimo** de
`MacroQuarterlyAsofProvenanceSchema`, subclasse) · `packages/shared/schemas/__init__.py` (1 export).

**Notas do fechamento:**
- **a regra:** o valor de `(T, coluna)` é o da última observação cuja **divulgação**
  (`date_obs + lag_divulgacao_dias`, lag **inteiro do `series_catalog`**: PIB 60, IBC-Br 45, IPCA 10,
  resto 0) é `<= quarter_end(T)`. Série sem lag resolvível **para** o build (`LagDesconhecido`) —
  assumir 0 reintroduziria o look-ahead que a materialização existe para eliminar.
- **duas peças novas de código e só duas** (`observacoes_asof` e `deslocar_acumulados`); todo o
  resto é **importado de F-015 sem adaptação**, e é isso que faz a reprodução da `revised` na mesma
  rodada conferir **3.071 células, 0 divergências, `max |dif| = 0,0`** contra o Parquet em disco.
- **CA-072 é verificável no Parquet publicado**, não só no código: a procedência `asof` publica
  `date_obs` e `lag_dias`, e o teste de acervo junta as duas tabelas e exige
  `date_obs + lag_dias <= quarter_end` nas **2.552** linhas. O build **para** se uma violar.
- **CA-074 acionado:** o proxy de quadrante troca em **22 de 66** trimestres = **33,33%** (era
  29,85%/20-67 antes de **D-s**), acima dos 25%. O número **oficial** é o de F-019 e é o mesmo.
- **D-s chegou depois:** o nível trimestral do IBC-Br é a média dos 3 meses, e média de trimestre é
  deslocada por `deslocar_acumulados` (a régua dos fluxos, reusada) — não por `observacoes_asof`.
  Consequência medida e **afirmada em teste**: `ibcbr_yoy` da `asof` em `T` **é** o da `revised` em
  `T-1`, por construção.
- **acréscimo de schema** (`MacroQuarterlyAsofProvenanceSchema`): subclasse, nunca alteração — o
  schema de F-015 é `strict=True`. Registrado em `CONTRACTS.md §3.1` (**D-w**).

| Teste | Tipo | Cobre CA |
|---|---|---|
| nenhuma coluna de `asof` usa dado divulgado após o fim de T | integration | CA-072 |
| % de troca de regime é calculado e exposto | integration | CA-073 |
| % > 25% → texto afirma que o modelo não é operacional | unit | CA-074 |
| tabela nunca mistura `asof` e `revised` | contract negativo | CA-072 |
| `lag = 0` reproduz a régua de F-015 célula a célula | unit | CA-072 |
| série sem `lag_divulgacao_dias` **para** o build | unit negativo | CA-072 |
| derivada é **recalculada**, não a coluna do `revised` deslocada | unit negativo | CA-072 |
| `ibcbr_yoy` da `asof` = o do `revised` de `T-1` (consequência de **D-s**) | unit | CA-072 |
| 2 rodadas → `sha256` idêntico nos 3 artefatos | unit | CA-121 |
| o módulo de produção **não lê o relógio** | unit | CA-121 |

**Anti-SPEC específica:** §10.2.7 (look-ahead sem flag é proibido).
**Extra de classe C:** diff numérico + reconstrução + revisão independente — **feito**: a
reconstrução da `revised` na mesma rodada é conferida **célula a célula e sem tolerância** contra o
artefato de F-015 em disco (`conferir_contra_revised_em_disco`), e divergência **para** o build.

---

### [~] F-019 — Regimes V1 (quadrantes crescimento × inflação) — **classe C** — **implementada — QA pendente**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/regimes-v1`
- **Cobre:** RF-027, RF-030, RF-031 · e-mail: **A1, A2** + objetivo
- **CAs da SPEC:** CA-078..081, CA-088, CA-090, CA-091 (+ CA-072/073/074 na parte que vem de F-018,
  + CA-108/109)
- **Context pack (vivo até o QA aprovar):** `docs/wiki/context/F-019.md`
- **Decisão provisória que carrega:** `[PROVISÓRIO D1, D3]` — ADR-001.
  **Item de DoR bloqueante da publicação:** enquanto ADR-001 estiver em **Proposta**,
  `especificacao_congelada = False` e o número **não vai ao Comitê** (gate da classe D).
- **Depende de:** F-015, F-018

**DoR específica** — [x] especificação escrita em ADR-001; [ ] **D1 e D3 respondidos** e ADR-001
**aceito** — exigência de RF-031 antes de cruzar com retornos; [x] schema `RegimesSchema` pronto.

**Escopo incluído:** `g_T` (gap do IBC-Br), `pi_T` (aceleração do IPCA 12m), 4 rótulos, desempate por
herança do trimestre anterior, `n_obs_regime_v1`, `alerta_n_baixo`, `fonte_versao` (hash do código),
`versao_especificacao`.
**Excluído:** V1b vs. Focus (→ F-033); V2 (→ F-020); V3 (→ F-021).

**Arquivos REAIS** (o contrato dizia `apps/pipeline/analysis/regimes_v1.py`,
`tests/unit/test_regimes_v1.py`, `tests/contract/test_regimes_schema.py` — divergência sancionada
em **D-x**): `apps/pipeline/canonical/regimes_v1.py` (1.142 L) ·
`tests/unit/test_canonical_regimes_v1.py` (**84** testes) ·
`tests/contract/test_regimes_v1_contract.py` (**39** testes) ·
`packages/shared/schemas/regimes.py` (**acréscimo** ao fim: `RegimesV1Schema`, `StatusRegimeV1`,
`MotivoIndeterminado`, 7 constantes, `COLUNAS_V1_DE_REGIMES`) ·
`packages/shared/schemas/__init__.py` (10 nomes) · `docs/wiki/modules/regimes.md`.

**Notas do fechamento:**
- **grava `regimes_v1.parquet`, não `regimes.parquet`** (**D-r**): `RegimesSchema` é o contrato da
  tabela completa e exigiria inventar coluna de outra lente, inventar quadrante, ou **alterar**
  schema (pausa). A junção é **F-022**, e há teste que existe só para avisar
  (`test_regimes_schema_continua_recusando_regime_v1_nulo`).
- **67 classificados / 16 `INDETERMINADO`** (`2006Q1..2009Q3` + `2026Q3`, todos `GAP_AUSENTE` por
  **D-m** — a crise de 2008 inteira fica fora do eixo de crescimento, e isso vai à F-028).
  `regime_v1` **nulo** + `status_regime_v1` + `motivo_indeterminado`, nunca estimativa.
- **distribuição pós-D-s: REC 19 · EXP 19 · EST 16 · DES 13** (era EXP 20 · REC 17 · EST 15 · DES
  15 com o IBC-Br em fim de período). CA-080 fecha: 4 quadrantes povoados, todos em [10, 35],
  desbalanceamento **1,46×**, nenhuma flag de `n` acesa. **7** trimestres mudaram de quadrante com
  D-s, e exatamente os 7 que o QA previu: 2013Q2, 2013Q3, 2013Q4, 2020Q1, 2023Q3, 2024Q1, 2025Q2.
- **0 desempates na rodada real** — nenhum eixo é exatamente 0 nos 83, então CA-079 é hoje só uma
  regra de borda coberta por teste sintético. Sensibilidade ±0,1 pp no limiar: **1** trimestre
  (1,20%) na `revised`, 4 (4,82%) na `asof`.
- ⚠️ **CA-074 acionado — é o achado que sobe ao Comitê:** **22 de 66 trimestres = 33,33%** trocam
  de rótulo entre `revised` e `asof` (era 29,85%), acima do limiar de **25%**. Pelo critério
  escrito a V1 **não é operacional na forma `asof`** e **H-03 do PRD cai**; a leitura descritiva
  (RF-027) segue válida. Vai à **página de limitações (F-028)** e ao slide, não a nota de pé.
- **`especificacao_congelada = False` nas 83 linhas**, lido do **status do ADR-001 em disco** com
  falha fechada: nada daqui é publicável (CA-090).

| Teste | Tipo | Cobre CA |
|---|---|---|
| 83 trimestres rotulados, 4 quadrantes povoados, sem `NULL` | contract | CA-078, CA-080 |
| `g_T = 0` herda o sinal do trimestre anterior | unit | CA-079 |
| rodar 2x dá classificação idêntica (função pura) | unit | CA-081 |
| `n` por quadrante entre 10 e 35, senão alerta | unit | CA-080 |
| ADR-001 em Proposta ⇒ `especificacao_congelada=False` | unit | CA-090 |
| ajuste posterior nasce como `V1.1`, sem sobrescrever | unit | CA-091 |
| classificação de `T` não muda quando **todo** o futuro muda | unit | CA-078 |
| entrada fora de ordem é **recusada** (a herança de CA-079 lê `T-1`) | unit negativo | CA-079 |
| tabela nunca mistura `asof` e `revised` | contract negativo | CA-072 |
| os 4 canários do acervo, conferidos à mão contra `macro_quarterly` | unit (acervo) | CA-078 |
| eixo de crescimento invertido **erraria** 2015Q4 | unit negativo | CA-078 |

**Anti-SPEC específica:** §10.2.9 (não ajustar a especificação depois de ver os retornos), §10.2.10
(descritivo, não preditivo).
**Extra de classe C:** diff numérico + reconstrução + revisão independente — **parcial**: não há
versão anterior de `regimes_v1` para diferenciar (é a 1ª materialização), e `g_score`/`pi_score`
são a célula de `macro_quarterly` **bit a bit**. O diff que existe é `revised` × `asof` (22/66) e o
diff **vs. a régua anterior do IBC-Br** (7 quadrantes, D-s). A reconstrução independente é do QA.

---

### [ ] F-020 — Camada `ciclo_selic` (V2) como corte secundário — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/regimes-v2` · prioridade **`should`**
- **Cobre:** RF-028, RF-030 · e-mail: **A4**
- **CAs da SPEC:** CA-082, CA-083
- **Decisão provisória que carrega:** `[PROVISÓRIO D1]` — ADR-001 (V2 nunca é célula única de decisão)
- **Depende de:** F-015, F-019

**DoR específica** — [x] limiar ±0,25 pp e regra de pausa definidos; [ ] D1 respondido (se V2 virar
oficial, muda o entregável principal, não o cálculo).

**Escopo incluído:** `CORTE`/`ALTA`/`NEUTRO` por ΔSelic meta no trimestre; pausa dentro de ciclo de
corte conta como `CORTE`; `regime_v2` = `v1 + "_" + ciclo`; `n` visível em toda célula; variante de
2 estados (`CORTE` vs. `NAO_CORTE`).
**Excluído:** teste de robustez completo da V2 (→ fase 2).

**Arquivos:** `apps/pipeline/analysis/regimes_v2.py`, `tests/unit/test_regimes_v2.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| 2 trimestres de CORTE + Δ=0 → `CORTE` (pausa no ciclo) | unit | CA-082 |
| toda célula da tabela V2 exibe `n`; output declara "secundário" | unit | CA-083 |
| estados com `n < 5` não geram conclusão | unit negativo | CA-083 |

**Anti-SPEC específica:** §10.2.8 (`n` em toda célula), §10.2.9.
**Extra de classe C:** diff numérico + revisão independente.

---

### [~] F-021 — Regimes V3 (vizinhos mais próximos) + retorno em T+1 — **classe C** — **implementada — QA pendente**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/regimes-v3`
- **Cobre:** RF-029, RF-030, RF-031, RF-036 · e-mail: objetivo literal ("momentos semelhantes")
- **CAs da SPEC:** CA-084..087, CA-088/089, CA-090/091, CA-101, CA-102
- **Decisão provisória que carrega:** `[PROVISÓRIO D1]` — ADR-001 (V3 é o diferencial) · **D-u**
- **Depende de:** F-015, F-016 (curva), F-017
- **Context pack (vivo até o QA aprovar):** `docs/wiki/context/F-021.md`

**DoR específica** — [x] 6 features definidas (`FEATURES_V3` no schema); [x] k=8 + sensibilidade
(5, 12); [x] plano B se a curva não ficar pronta (5 features, declarado);
[x] `scipy`/`scikit-learn` para Ledoit-Wolf: **não há** no ambiente e **nenhuma dependência foi
adicionada** — o estimador foi implementado **à mão em numpy** no próprio módulo, o que dispensa o
ADR de §10.4.25 e mantém o shrinkage **medido** (`rho = 0,259874`) em vez de parametrizado.

**Escopo incluído:** z-score na amostra completa; Mahalanobis com shrinkage Ledoit-Wolf; Euclidiana em
paralelo; exclusão dos 2 trimestres anteriores; desempate pelo mais recente; variante `V3-pos2016`;
saída `regime_neighbors` + retorno de cada ativo nos trimestres **seguintes** aos vizinhos.
**Excluído:** clustering/HMM (→ F-039); otimização de carteira (fora de escopo, D11).

**Arquivos REAIS** (o contrato dizia `apps/pipeline/analysis/regimes_v3.py`,
`tests/unit/test_regimes_v3.py`, `tests/contract/test_regime_neighbors.py` — divergência sancionada
em **D-x**): `apps/pipeline/canonical/regimes_v3.py` (1.565 L) ·
`tests/unit/test_canonical_regimes_v3.py` (**45** testes) ·
`tests/contract/test_regimes_v3_contract.py` (**39** testes) ·
`packages/shared/schemas/regimes.py` (**acréscimo** ao fim: `RegimeNeighborsV3Schema`, 6
constantes, `indice_do_quarter`) · `packages/shared/schemas/__init__.py` (3 nomes).

**Notas do fechamento:**
- **5 features em z-score, não 6** (`FEATURES_V3` tem 6 declaradas): `focus_pib_ano` (substitui
  `z_ibcbr_gap`, **D-u**), `ipca_12m_delta`, `juro_real_exante`, `inclinacao_real_5a_3a` (D-i/D-n),
  `usdbrl_var_12m`; **`termos_troca_yoy` cortada** porque é 100% nula (G-02 / F-037) — preencher
  seria dado inventado. O de/para está em `CONTRACTS.md §5.3` e em
  `relatorio_regimes_v3.json → features`, para a comparação ser automática.
- **o eixo de crescimento é `focus_pib_ano`** (**D-u**, ratificado provisoriamente): `ibcbr_gap` é
  nulo em `2026Q3` **por construção**, e `2026Q3` é a pergunta do Comitê. Nenhuma alternativa
  (D-m `min_periods=8`, `ibcbr_yoy` sem tendência) resolve `2026Q3`.
- **dois artefatos de vizinhos, e F-022/F-024 leem o `_v3`** (**D-u**):
  `regime_neighbors.parquet` (5.500 × 11) satisfaz CA-089 mas perde **4 dos 8** vizinhos de
  `2026Q3` porque `regime_v1_neighbor` é `nullable=False` e 16 trimestres não têm quadrante (D-m).
  Dívida de schema em **§6**.
- **os 8 vizinhos de `2026Q3`:** `2006Q3 · 2006Q4 · 2006Q1 · 2024Q3 · 2014Q4 · 2007Q1 · 2024Q2 ·
  2014Q3`. A variante **sem nenhum look-ahead** dá a **mesma lista** (Jaccard 1,0) — o achado mais
  forte da feature. **D-s não mudou nada aqui**: lista, distâncias e ranking byte-idênticos.
- **exclusão de vizinhança simétrica** (`T±1`, `T±2`): CA-085 fala só dos anteriores, mas sem a
  simetria o vizinho rank 1 de quase todo trimestre seria `T+1` — autocorrelação trivial.
  Declarado em `relatorio_regimes_v3.json → exclusao_de_vizinhanca.simetrica`.
- **`n = 8` não distingue quase nada**: erro-padrão de 2,5 a 5 pp, e só `INDX` (+5,04%) chega perto
  de 2 ep. `IFIX` e `IMOB` têm `n = 4` ⇒ `conclusao_suprimida` (CA-109). A linguagem é
  **descritiva** por contrato (§10.2.10) e o gate de publicação é `False` (ADR-001 em Proposta).

| Teste | Tipo | Cobre CA |
|---|---|---|
| covariância amostral crua (sem shrinkage) → teste falha | unit negativo | CA-084 |
| os 2 trimestres anteriores não aparecem; empate pelo recente | unit | CA-085 |
| curva ausente → roda com 5 features e **declara** | unit | CA-086 |
| k=5, 8 e 12 produzidos; divergência reportada | integration | CA-087 |
| PK de `regime_neighbors` e `metrica` no enum | contract | CA-089 |
| retorno medido em **T+1** dos vizinhos, não nos vizinhos | unit | CA-102 |
| distância recalculada em **numpy puro dentro do teste**, no acervo real | unit (acervo) | CA-084 |
| variante `somente_passado` não usa nenhuma informação futura | unit | CA-101 |
| ADR-001 em Proposta ⇒ gate de publicação `False` | contract | CA-090 |

**Anti-SPEC específica:** §10.2.9 (não escolher k pelo resultado), §10.2.10, §10.4.25 (dependência nova
exige ADR — **nenhuma foi adicionada**).
**Extra de classe C:** diff numérico + revisão independente — **feito em parte**: o rótulo V1 de
anotação é conferido contra `regimes_v1.parquet` de F-019 (**83 trimestres, 0 divergências**) e as
24 combinações de lente são o diff interno. A reconstrução independente é do QA.

---

### [ ] F-022 — Métricas por regime × ativo — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/metricas-regime`
- **Cobre:** RF-032, RF-040 · e-mail: **B1-B5, C1**
- **CAs da SPEC:** CA-092..094, CA-108, CA-109
- **Depende de:** F-017, F-019, F-020, F-021

**DoR específica** — [x] `RegimeAssetMetricsSchema` pronto, com `n_obs` não anulável;
[x] limiares `n < 8` (alerta) e `n < 5` (supressão) definidos (D10, não bloqueante).

**Escopo incluído:** as 13 métricas por `(lente, regime, asset_id)`, incluindo média **e** mediana lado
a lado, erro-padrão da média, `hit_ratio_cdi`, `pior_tri`/`melhor_tri` com data, `beta_ibov`;
flags `alerta_n_baixo` e `conclusao_suprimida`.
**Excluído:** figuras (→ F-023..F-025); variância mínima por regime (→ F-035).

**Arquivos:** `apps/pipeline/analysis/metricas_regime.py`, `tests/unit/test_metricas_regime.py`,
`tests/contract/test_metricas_schema.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| média e mediana presentes; erro-padrão = desvio/√n | unit | CA-092 |
| ativo com janela própria tem `n_obs` só dos seus trimestres | unit | CA-093 |
| `sharpe_tri` anualizado declara a anualização | unit | CA-094 |
| `n < 8` → `alerta_n_baixo`; `n < 5` → `conclusao_suprimida` | unit | CA-108, CA-109 |
| célula sem `n` é impossível (schema) | contract negativo | CA-095 (pré) |

**Anti-SPEC específica:** §10.2.8, §10.2.11.
**Extra de classe C:** diff numérico + revisão independente.

---

### [ ] F-023 — Heatmap regime × ativo (entregável visual central)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `feat/heatmap`
- **Cobre:** RF-033, RF-040 · e-mail: **B1-B5, C1**
- **CAs da SPEC:** CA-095, CA-096, CA-097
- **Decisão provisória que carrega:** `[PROVISÓRIO D5]` — ADR-002 (métrica = excesso sobre CDI).
  **Item de DoR:** virar D5 = trocar 1 parâmetro da figura.
- **Depende de:** F-022

**DoR específica** — [x] métrica provisória decidida em ADR-002; [x] regras de apresentação
(`n` em toda célula, hachura `n < 8`, rodapé com `data_inicio`); [ ] D5 respondido (não bloqueia a
implementação).

**Escopo incluído:** figura com >= 18 linhas × regimes, escala divergente centrada em 0, `n` anotado,
hachura, rodapé com `data_inicio` por série e nome explícito da métrica; export PNG + dados em CSV.
**Excluído:** dashboard interativo (fora de escopo).

**Arquivos:** `apps/pipeline/analysis/figuras.py`, `tests/unit/test_heatmap.py`,
`apps/analysis/notebooks/` (consumo).

| Teste | Tipo | Cobre CA |
|---|---|---|
| toda célula tem `n` anotado (0 células sem anotação) | unit | CA-095 |
| `n < 8` recebe hachura/cinza | unit | CA-096 |
| rodapé lista `data_inicio` e nomeia a métrica | unit | CA-097 |
| linha `CDI` é identicamente 0 (sanity check da métrica) | unit | CA-095 |

**Anti-SPEC específica:** §10.2.8, §10.2.10 (linguagem descritiva no título e na legenda).

---

### [ ] F-024 — Tabela "regime atual → ranking de ativos" + concordância entre lentes

- **Risco:** B · **CI alvo:** N1 · **Branch:** `feat/tabela-ranking`
- **Cobre:** RF-034, RF-037 · e-mail: objetivo
- **CAs da SPEC:** CA-098, CA-099, CA-103
- **Depende de:** F-022, F-021

**DoR específica** — [x] semáforo de confiança definido pelos limiares de `n`; [ ] D1 respondido define
qual lente abre a página (não bloqueia).

**Escopo incluído:** 1 página com regime corrente por V1 e V2, os 8 vizinhos da V3, ativos ordenados por
`excesso_cdi` com `hit_ratio_cdi`, `n` e semáforo; tabela de concordância (1 linha por lente, top-3).
**Excluído:** recomendação de alocação (é do Alexandre); qualquer linguagem preditiva.

**Arquivos:** `apps/pipeline/analysis/tabelas.py`, `tests/unit/test_tabela_ranking.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| página traz V1, V2, 8 vizinhos e ranking com `n` | unit | CA-098 |
| ativo com `n < 5` aparece sem afirmação conclusiva | unit negativo | CA-099 |
| divergência entre lentes é reportada, não omitida | unit | CA-103 |

**Anti-SPEC específica:** §10.2.8, §10.2.10.

---

### [ ] F-025 — Timeline de regimes 2006→2026 sobre IBOV e Selic

- **Risco:** B · **CI alvo:** N1 · **Branch:** `feat/timeline-regimes`
- **Cobre:** RF-035 · e-mail: **A1, A2, A4, B4**
- **CAs da SPEC:** CA-100
- **Depende de:** F-019

**DoR específica** — [x] séries de IBOV e Selic disponíveis (F-003, F-006); [x] rótulos V1 definidos.

**Escopo incluído:** faixa colorida dos 83 trimestres sobre IBOV e Selic; export PNG.
**Excluído:** interatividade; anotação de eventos políticos.

**Arquivos:** `apps/pipeline/analysis/figuras.py` (extensão), `tests/unit/test_timeline.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| faixa cobre os 83 trimestres sem buraco não explicado | unit | CA-100 |
| legenda com os 4 rótulos e a janela de cada série | unit | CA-100 |

**Anti-SPEC específica:** §10.2.10. **Nota:** é o **sanity check visual** do Comitê — se a classificação
"não fizer sentido" para quem viveu o período, a hipótese H-02 do PRD cai e **isso** é resultado.

---

### [ ] F-026 — Dimensionamento da alocação internacional + regra de risk-off — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/internacional`
- **Cobre:** RF-038, RF-039 · e-mail: **C1** (escopo implícito virando explícito)
- **CAs da SPEC:** CA-104..107
- **Decisão provisória que carrega:** `[PROVISÓRIO D6]` — ADR-003 (piso 16-20% + banda 15-35%).
  **Item de DoR:** a formulação da recomendação depende de D6; os números por regime não.
- **Depende de:** F-007, F-011, F-016, F-017, F-019

**DoR específica** — [x] universo internacional definido (P-03); [x] gatilho de stress definido
(inclinação < −1 d.p. **ou** USDBRL > +10%); [ ] **D6 respondido**; [ ] `GOLD_BRL` depende de G-03 —
se não houver fonte, a linha sai com `BLOQUEADO — FONTE INDISPONÍVEL`.

**Escopo incluído:** linhas internacionais no **mesmo** heatmap; `corr(USDBRL, IBOV)` por regime e nos
10 piores trimestres do IBOV; `stress_flag`; medida de quanto de USD neutraliza a queda do IBOV;
entrega como **faixa estrutural + banda tática por regime**; versões com e sem hedge (D7).
**Excluído:** variância mínima por regime e fronteira eficiente (→ F-035); ramo EMBI do gatilho (L8).

**Arquivos:** `apps/pipeline/analysis/internacional.py`, `tests/unit/test_internacional.py`,
`tests/integration/test_risk_off.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| internacional no mesmo arcabouço (mesma métrica/regimes) | integration | CA-104 |
| `corr(USDBRL, IBOV)` por regime e nos 10 piores do IBOV, com `n` | unit | CA-105 |
| `stress_flag` pela disjunção definida; trimestres listados | unit | CA-106 |
| saída é faixa; número pontual é rejeitado com justificativa | unit negativo | CA-107 |
| hedgeado x sem hedge nunca somados nem confundidos | unit negativo | CA-104 |

**Anti-SPEC específica:** §10.2.10, §10.2.12, §10.3.16 (sem otimização/backtest na v1).
**Extra de classe C:** diff numérico + revisão independente.

---

### [ ] F-027 — Notebook de entrega (reprodutível, sem lógica de negócio)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `feat/notebook-entrega`
- **Cobre:** RF-041 · e-mail: entregável
- **CAs da SPEC:** CA-110, CA-111
- **Depende de:** F-022..F-026

**DoR específica** — [x] todas as funções de cálculo em `apps/pipeline/`; [x] canônico construído.

**Escopo incluído:** 1 notebook que carrega → classifica → calcula métricas → gera as figuras,
**importando** de `apps/pipeline/`, com outputs limpos no commit.
**Excluído:** qualquer definição de cálculo dentro do notebook (seria violação do `AGENTS.md §19`).

**Arquivos:** `apps/analysis/notebooks/comite_2026_10_14.ipynb`, `tests/unit/test_notebook_imports.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| notebook não define cálculo de retorno/regime/alinhamento | unit (AST) | CA-110 |
| outputs limpos no commit | unit | CA-111 |
| roda ponta a ponta sobre o canônico de fixtures | integration | CA-111 |

**Anti-SPEC específica:** base + `AGENTS.md §19` (notebook sem lógica de negócio).

---

### [ ] F-028 — Página de limitações (blinda a reunião)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `feat/pagina-limitacoes`
- **Cobre:** RF-042 · e-mail: — (exigência metodológica)
- **CAs da SPEC:** CA-112
- **Depende de:** F-018 (número do look-ahead), F-022 (n por célula)

**DoR específica** — [x] conteúdo obrigatório listado na SPEC; [ ] número real do teste de look-ahead
(vem de F-018) e `n` por regime (vem de F-022).

**Escopo incluído:** 1 página com: `n` pequeno e erro-padrão (~2,7 pp/tri com n=20, σ=12%); quebra
estrutural 2006-2008 × pós-2016; resultado do teste de look-ahead; séries com janela curta (ICON,
IMOB, IFIX, FII segmentado, ponta longa nominal); aviso de que índice não é investível sem fricção;
substituições de fonte; gaps abertos (G-01..G-07).
**Excluído:** defesa de tese metodológica (é a pesquisa, já escrita).

**Arquivos:** `docs/plans/limitacoes-comite-2026-10-14.md`, `tests/unit/test_limitacoes.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| a página contém os 6 blocos obrigatórios | unit | CA-112 |
| o número do look-ahead citado é o calculado por F-018 | unit | CA-112 |

**Anti-SPEC específica:** §10.2.10 (descritivo), §10.3.19 (substituição declarada).

---

### [ ] F-029 — Orquestrador "um comando" + idempotência e hash — **classe C**

- **Risco:** **C** · **CI alvo:** N2 (N3 na entrega) · **Branch:** `feat/pipeline-orquestrador`
- **Cobre:** RF-046, RF-048 · e-mail: entregável ("estrutura de busca e extração")
- **CAs da SPEC:** CA-118, CA-119, CA-121, CA-122
- **Depende de:** F-001..F-026

**DoR específica** — [x] camadas e formatos congelados em ADR-006; [x] runbook de reconstrução previsto;
[ ] tempo-alvo de 30 min a frio (RNF-008) a medir.

**Escopo incluído:** CLI única `raw → processed → canonical`; relatório de saída (linhas, min/max de
data, % de nulos por coluna crítica, hash); idempotência (2 execuções → mesmo hash); tratamento de
revisão retroativa (novo `vintage`, sem duplicar); runbook.
**Excluído:** agendador, serviço, container.

**Arquivos:** `apps/pipeline/__main__.py`, `apps/pipeline/pipeline.py`,
`tests/e2e/test_pipeline_completo.py`, `tests/integration/test_idempotencia.py`,
`docs/wiki/runbooks/reconstruir-dataset.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| `data/` vazio → canônico completo, sem passo manual | e2e | CA-118 |
| 2 execuções sobre o mesmo `raw/` → **mesmo hash** | integration | CA-121 |
| revisão retroativa atualiza a linha, não duplica | integration | CA-122 |
| relatório de saída traz linhas, min/max, % de nulos, hash | integration | CA-118 |

**Anti-SPEC específica:** §10.4.22 (nada manual em `data/`), §10.4.21 (nada commitado).
**Extra de classe C:** reconstrução completa + diff numérico + revisão independente.

---

### [ ] F-030 — Testes de contrato com valor-canário + cache condicional

- **Risco:** B · **CI alvo:** N1 (contrato em N2) · **Branch:** `feat/testes-contrato`
- **Cobre:** RF-049, RF-050, RF-051 · e-mail: — (proteção dos 3 endpoints não documentados)
- **CAs da SPEC:** CA-123..127
- **Depende de:** F-002, F-006, F-007

**DoR específica** — [x] os 3 valores-canário definidos (IBOV 38.484,84; IMA-B 723,070317;
MSCI ACWI NETR 121,3858); [x] fixtures gravadas nas features de extração.

**Escopo incluído:** testes de contrato (shape + valor-canário) para B3 `indexStatisticsProxy`, MSCI
`app2.msci.com` e S3 da ANBIMA, sobre **fixture**; versão `@pytest.mark.network` contra a fonte viva,
fora do CI; cache condicional por `ETag`/`Last-Modified` para Tesouro e arquivos grandes;
reconciliação ANBIMA S3 × SGS 12461-12469 na data de corte 22/05/2023.
**Excluído:** monitoramento contínuo/alerta (fase 2).

**Arquivos:** `tests/contract/test_endpoints_canario.py`, `tests/integration/test_cache.py`,
`apps/pipeline/extract/cache.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| shape + valor-canário dos 3 endpoints sobre fixture | contract | CA-125 |
| versão viva marcada `network`, excluída do CI | contract | CA-126, CA-123 |
| todo extrator tem fixture correspondente | unit | CA-124 |
| segundo download no mesmo dia usa cache (ETag) | integration | CA-127 |

**Anti-SPEC específica:** §10.4.23 (sem rede no CI), §10.4.25 (sem `.skip` sem ADR).

---

### [ ] F-031 — Pacote de entrega ao Comitê — **classe D**

- **Risco:** **D** · **CI alvo:** N3 · **Branch:** `feat/entrega-comite`
- **Cobre:** RF-043, RF-044, RF-045 · e-mail: entregável final
- **CAs da SPEC:** CA-113..117
- **Depende de:** **tudo** (F-001..F-030) + **ADR-001 aceito** (RF-031/CA-090)

**DoR específica** — [ ] **ADR-001 aceito** (sem isso `especificacao_congelada=False` e o número não é
publicável); [ ] revisão humana do número pelo Edu agendada; [ ] 3 valores conferidos por série;
[ ] `docs/plans/infra-ops.md` com **Rollback** escrito; [ ] dataset congelado (versão + hash);
[ ] texto de substituições de fonte pronto (F-032).

**Escopo incluído:** `macro_quarterly`, `asset_returns_quarterly`, `regimes`, `regime_neighbors` em
**Parquet + CSV/XLSX**; figuras (heatmap, timeline); as duas tabelas de 1 página; página de limitações;
`README` do pacote com versão + hash; comunicação escrita das substituições e das séries sem 20 anos.
**Excluído:** qualquer recomendação de alocação assinada pela LDC; material de distribuição; backtest.

**Arquivos:** `apps/pipeline/deliver/pacote.py`, `docs/plans/infra-ops.md`,
`docs/wiki/runbooks/fechar-relatorio-comite.md`, `docs/wiki/log.md`, `docs/wiki/features/F-031.md`,
`tests/e2e/test_pacote_entrega.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| pacote tem as 4 tabelas nos 2 formatos + figuras + 1-páginas | e2e | CA-113 |
| nenhum arquivo do pacote foi editado à mão (hash do script) | e2e | CA-114 |
| sem revisão/hash/log/rollback → `BLOQUEADO` | e2e negativo | CA-115, CA-116 |
| acompanha o texto de substituições de fonte | unit | CA-117 |
| reprodutibilidade: rodar 2x → mesmo hash | e2e | CA-121 |

**Anti-SPEC específica:** §10.3.18 (nada ao Comitê fora da classe D), §10.3.16 (sem backtest),
§10.2.10 (descritivo), §10.3.19 (substituição declarada).
**Rollback (obrigatório em D):** 1) não enviar; 2) se já enviado, e-mail de correção citando versão e
hash do dataset substituído; 3) marcar a versão como revogada em `wiki/log.md`; 4) reconstruir do
`raw/` arquivado; 5) rodar o diff numérico vs. a versão enviada e comunicar cada divergência.

---

## PACOTE ESTENDIDO — fase 2 (depois de 2026-10-14)

> Não comprometido com o Comitê. Entram só depois de o pacote mínimo estar entregue e conferido.
> Feature Contract completo é escrito ao mover para "Em andamento".

### [ ] F-033 — V1b: eixos vs. Focus (surpresa em vez de tendência) — **classe C**
Cobre RF-027 (variante), decisão **D2**. Requer Focus por data de coleta (F-010) e muda o rótulo dos 83
trimestres → nasce como **lente paralela**, nunca sobrescrevendo V1. CI N2.

### [ ] F-034 — Dupla materialização `asof` × `revised` com relatório de divergência — **classe C**
Cobre RF-025 (completo), decisão **D4**. Na v1 só o percentual é reportado (F-018); aqui vira relatório
por trimestre, com a classificação lado a lado. CI N2.

### [ ] F-035 — Variância mínima por regime (Ledoit-Wolf) + fronteira eficiente — **classe C**
Cobre RF-038 (aprofundamento). Conjunto pequeno (CDI, IMA-B, IBOV, IFIX, SP500_BRL), long-only, cap de
40% por ativo, **com sensibilidade reportada**. Atenção: continua **proibido** apresentar como backtest
ou previsão (Anti-SPEC §10.3.16). CI N2.

### [ ] F-036 — Risco-país: splice EMBI+ × ICE BofA (ou cupom cambial DDI/FRC) — **classe B**
Cobre lacuna **L8**. EMBI+ morre em 30/07/2024; perna B (`BAMLEMRLCRPILAOAS`) tem janela rolante de 3
anos → **arquivar diariamente desde já**. Série emendada = quebra metodológica em 2024, declarada. CI N1.

### [ ] F-037 — Termos de troca (IC-Br / Funcex) como feature de regime — **classe B**
Completa a 6ª feature da V3 com fonte própria em vez de proxy. Hoje `termos_troca_yoy` pode entrar nulo
ou via IC-Br (SGS 27574). CI N1.

### [ ] F-038 — Construção própria de FII por segmento (COTAHIST + CVM) — **classe C**
Cobre **L2** sem depender da Teva; estende a segmentação para 2016+. Classificador pelo **balanço**
(`inf_mensal_fii_ativo_passivo`), imune à quebra de taxonomia da Res. CVM 175. Esforço alto. CI N2.

### [ ] F-039 — Validação independente: clustering (GMM/k-means) e HMM mensal — **classe C**
Cobre a hipótese H-01: se os clusters reproduzirem a V1, a lente ganha credibilidade; se virarem
"antes/depois de 2016", **isso** é a mensagem. HMM com dados mensais (240 obs). CI N2.

### [ ] F-040 — Atualização trimestral do regime corrente (uso recorrente) — **classe B**
Transforma o projeto em ativo reutilizável: rodar a cada fechamento de trimestre, com diff vs. o
trimestre anterior. Sem dashboard hospedado (fora de escopo). CI N1.

---

## 3. Concluído

> Movido para cá ao fazer merge. Inclua SHA/PR.

- [x] **Kickoff — estrutura Harness v3.2 adaptada a projeto de dados** — 2026-10-10 (classe A)
- [x] **PRD v1.0** (modo autônomo, 52 RFs) — 2026-10-10 (classe A) — `docs/product/PRD.md`
- [x] **SDD — SPEC + Anti-SPEC + contratos pandera/pydantic + catálogo de 132 séries + 6 ADRs
      propostos** — 2026-10-10 (classe A) — `docs/specs/SPEC.md`, `docs/contracts/CONTRACTS.md`,
      `packages/shared/schemas/`, `docs/decisions/adr/`, `docs/plans/PLAN.md`
- [x] **F-032 — `DECISIONS_LOG` inicial com as 12 substituições de fonte (todas provisórias, aguardando aval de Edu/Alexandre)** — 2026-10-10 (classe A) — `docs/plans/DECISIONS_LOG.md`
- [x] **F-001 — Infra de extração (`apps/pipeline/common/`: cliente HTTP com UA de browser e retry,
      validador de shape, dois normalizadores de número, encoding por fonte, magic bytes,
      fatiamento de janela, camadas `raw`/`processed` com manifesto e hash, primitiva de cache
      condicional)** — 2026-10-10 (classe B) — **QA aprovado** em `docs/plans/qa/ONDA-0-QA.md`;
      o re-QA do fix QA-01 (escala de `para_float_ptbr`) foi verificado pelo orquestrador.
      Renomeação `extract/` → `common/` registrada no contrato. Dívidas remanescentes em §6
      (`--record` em `conftest.py`). Permanente em `docs/wiki/architecture.md`
- [x] **F-009 — Job diário de arquivamento ANBIMA (`ms_AAMMDD.txt` + Curva Zero, janela rolante de
      ~20 d.u.)** — 2026-10-10 (classe B) — **QA aprovado** em `docs/plans/qa/ONDA-0-QA.md`;
      41 arquivos + 41 manifestos arquivados ao vivo, idempotência e dia ausente confirmados na
      fonte. Pendências que não bloqueiam: tarefa agendada (é do Edu, `schtasks` no runbook) e
      migração da camada HTTP para `apps.pipeline.common` (§6). Permanente em
      `docs/wiki/modules/anbima.md` + `docs/wiki/runbooks/job-diario-anbima.md`

**Onda 1 — os 7 extratores (2026-10-11, classe B).** QA independente em dois lotes por **dois
subagentes distintos**, nenhum deles implementador: `docs/plans/qa/ONDA-1-QA-A.md` (F-002, F-003,
F-004, F-008) e `docs/plans/qa/ONDA-1-QA-B.md` (F-005, F-006, F-007). **0 × P0 nos dois lotes.**
Convenções da onda (D-a..D-h) em `DECISIONS_LOG §2.1`; permanente em `docs/wiki/modules/`.

- [x] **F-002 — Extrator ANBIMA S3 (índices IMA)** — `apps/pipeline/extract/anbima_s3.py`: 9 índices,
      5.407-6.700 linhas cada, 2000-02-01→, 0,00% de nulos. **QA: APROVADO** — "o lote mais bem
      fechado" junto com F-008; 4/4 CAs com evidência do revisor (fonte viva **e** Parquet), canário
      IMA-B 16/09/2003 = 723,070317, nenhuma tentativa de quebra passou
- [x] **F-003 — Extrator BCB SGS** — `apps/pipeline/extract/bcb_sgs.py`: 15 séries, 44.447 linhas,
      CDI 2006 = 15,0271% reproduzido do Parquet. **QA: MUDANÇAS_SOLICITADAS → APROVADO após as
      correções em `65d2fb9`** — P1-1 (observação de período **parcial** podia entrar como mês
      fechado com `--fim` no último dia civil) e P1-2 (a 432 é calendário corrido e nada no dado
      dizia isso → campo **`calendario`** no catálogo, `CONTRACTS.md §2`) resolvidos, cada um com
      teste
- [x] **F-004 — Extrator IBGE SIDRA** — `apps/pipeline/extract/ibge_sidra.py`: 6 séries, IPCA
      nº-índice 562 meses e PIB 122 trimestres; reconciliação valor a valor contra SGS 433 e 22109
      (`max|dif| = 0`). **QA: APROVADO, com D-e pendente do Edu** — CA-004 (monotonia ≥ 99%) e CA-005
      (tolerância ≤ 1e-6) **medidamente não fecham** no dado real (0,9626 e 3,52e-04 pp, contra um
      teto analítico de 3,97e-04 pp que vem das 2 casas do IBGE). O implementador fez o certo: mediu,
      registrou **D-e**, travou o número no teste e **não editou a SPEC**. Item aberto em §4
- [x] **F-005 — Extrator Tesouro Direto** — `apps/pipeline/extract/tesouro_direto.py`:
      `td_painel.parquet` com 886.300 linhas e 750 `series_id`, 2004-12-31→2026-10-09, cache
      condicional com HTTP **304 de 0 byte**. **QA: MUDANÇAS_SOLICITADAS → APROVADO após as correções
      em `65d2fb9`** — P1-1 (`--offline` sobre bruto **sem manifesto** caía no relógio da rodada e
      quebrava D-b/CA-121) resolvido
- [x] **F-006 — Extrator API B3** — `apps/pipeline/extract/b3_indices.py`: 11 índices, 54.650 linhas,
      0,00% de nulos (célula vazia é **linha omitida**), janelas próprias de ICON/IMOB/IFIX iguais ao
      catálogo em 100% dos casos. **QA: APROVADO** — 0 P1; **G-01** (`is_total_return` dos 9
      setoriais) segue declarado, não é issue desta feature
- [x] **F-007 — Extrator internacional (Yahoo + MSCI + câmbio)** — `extract/{yahoo,msci}.py` +
      `transform/cambio.py` (D-g): 8 séries + `SP500_BRL`/`ACWI_BRL` pela PTAX do mesmo dia útil, sem
      `ffill` (`(datas USD ∩ datas PTAX) == datas BRL`, igualdade exata). Catálogo 132 → **134**
      (D-d). **QA: APROVADO** — 0 P1
- [x] **F-008 — Calendário de dias úteis (ANBIMA)** — `apps/pipeline/extract/calendario_anbima.py` +
      `packages/shared/schemas/calendario.py` (D-f): 10.957 dias civis 2001→2030, 7.530 úteis, 367
      feriados, Parquet **byte-idêntico** entre execuções. **QA: APROVADO** — 249 d.u. de 2006 por
      **3** caminhos independentes e coerência calendário × CDI nos 20 anos; 4 payloads adversariais
      recusados com mensagem específica. Achado **D-h** (B3 ⊂ ANBIMA em 69 datas) virou DoR de F-014

> **P1/P2 remanescentes do QA da Onda 1, não bloqueantes:** **D-e** aguarda o Edu (§4); o **job N2
> que reconstrói uma `data/processed/` mínima das fixtures** para que `test_contract_sgs_sidra.py` e
> `test_processed_layer_conventions.py` deixem de **pular** no CI (P1-4 do lote A) está em §6;
> `YAHOO_DXY` com 1.210 nulos (17,41%, domingos) e `YAHOO_GSPC` com `is_total_return = None` (P2-2 e
> P2-3 do lote B), `vintage` em data **UTC** não comparável entre features (P2-5) e os markers de
> `tests/` (P2-6) também em §6.

**Onda 2 — a camada canônica (2026-10-11, classe C).** QA independente em dois lotes por **dois
subagentes distintos**, nenhum deles implementador: `docs/plans/qa/ONDA-2-QA-A.md` (F-014, F-015) e
`docs/plans/qa/ONDA-2-QA-B.md` (F-016, F-017). **0 × P0 nos dois lotes.** O método foi o que a
classe C exige: o revisor **reimplementou a régua do zero**, sem importar o módulo sob teste, e
comparou **célula a célula e sem tolerância**. Decisões da onda (D-i..D-q) em `DECISIONS_LOG §2.3`;
permanente em `docs/wiki/modules/canonical.md` e `modules/focus.md`.

- [x] **F-013 — `raw_series` + `series_catalog` materializado** —
      `apps/pipeline/canonical/build_raw_series.py`: 278.439 linhas, 62 séries, catálogo 138 × 26.
      **QA: MUDANÇAS_SOLICITADAS → APROVADO após `3265499`** — P1-1 (`versao_build` era cego ao
      catálogo: editar `series_catalog_data.py` mudava o Parquet sem mudar a versão) e P1-2
      (`calendario` não chegava ao materializado) resolvidos. O **resto do P1-1** — o hash dependia
      do fim de linha do checkout — só foi fechado agora, em **D-v (b)**
- [x] **F-014 — Alinhamento trimestral (fim de período, ffill ≤ 5 d.u.)** —
      `apps/pipeline/canonical/alinhamento.py` + `alinhado_trimestral.parquet` (artefato **novo**,
      `CONTRACTS.md §8`). **QA: APROVADO** — o revisor reconstruiu a régua inteira (grade, 3
      calendários, ffill em dias úteis, limite de 5, painel desbalanceado) e conferiu **4.038
      células com 0 divergências**; build em scratch saiu **byte-idêntico** ao publicado. Os 215
      ffill são **todos** B3, **todos** 4º trimestre, **exatamente 1 d.u.** (D-h); os 7 nulos têm
      lacuna de 65/42 d.u. e `date_obs` nulo
- [x] **F-015 — `macro_quarterly` 83 × 42 + procedência por célula** —
      `apps/pipeline/canonical/macro_quarterly.py`. **QA: APROVADO** — **22 colunas** recalculadas
      por conta independente com **`max |dif| = 0,0`** (igualdade exata em float64, não
      tolerância), padrão de nulos idêntico, procedência bidirecional **0/0**, anti-look-ahead
      **0 violações** em 2.515 `date_obs` reconstruídas, 4 canários conferidos na fonte. **5 P1
      abertos pelo lote A foram absorvidos no fechamento da Onda 3** (D-s, D-t, D-v)
- [x] **F-016 — Curva: vértices fixos interpolados + inclinação (11 séries, D-i)** —
      `apps/pipeline/canonical/curva.py`. **QA: APROVADO** — o revisor recalculou **as 11 séries ×
      5.436 datas a partir do CSV bruto** com igualdade **exata** e 0 divergências de nulidade, as
      duas coberturas de D-i ao centésimo (60,53% e 95,25%), e fez validação **externa**: o
      breakeven **por razão** reproduz a coluna "Inflação Implícita" da **própria ANBIMA** com erro
      máx **0,010 bp**, enquanto a subtração erra até **37,2 bps**
- [x] **F-017 — `asset_returns_quarterly`: retornos, excesso sobre CDI e real** —
      `apps/pipeline/canonical/retornos.py`: 1.963 × 16, 24 ativos. **QA: APROVADO** — `ret_tri`,
      CDI, IPCA, excesso, real, `vol` e `dd` reproduzidos por fora com **igualdade exata**; canário
      CDI 2006 = **15,027140%** em 249 d.u.; **2ª fonte independente** (SGS 4389, outra unidade,
      base 252) a **2,8e-05 pp**; razão ≠ subtração comprovada (média 0,139 pp, máx 1,495 pp).
      1 × P1 (**janela do CDI ≠ caminho do ativo**) virou **limitação declarada** em **D-v (c)**
- [x] **F-010 — Extrator Focus (BCB Olinda / OData v4)** —
      `apps/pipeline/extract/bcb_focus.py`: 5 EntitySets, 197 séries, 150.120 linhas.
      **QA: APROVADO** (lote A da Onda 2, em conjunto com F-015, que é a única consumidora).
      Decisões **D-k** (o Focus fica fora de `raw_series`: os `series_id` são compostos por
      horizonte e não são entradas do catálogo), **D-p** e **D-q**

---

## 4. Bloqueios

### Estado em 2026-10-10 (noite) — execução autorizada, publicação ainda travada

O **Edu autorizou abrir a Onda 0 e seguir as demais ondas em loop**, desenvolvendo sobre os **padrões
provisórios** das 8 decisões abaixo (D1, D3, D5, D6, D12, L1, L2, L4) e do **ADR-006** — em vez de esperar.
O que isso muda e o que **não** muda:

- **Desenvolver: liberado.** As features podem ser implementadas adotando a recomendação registrada em
  cada item e no `DECISIONS_LOG.md`. Para o **ADR-006** (armazenamento Parquet+DuckDB e convenção de
  retorno/alinhamento): **desenvolvimento liberado em caráter provisório; aceite formal pendente** — a
  DoR de F-013/F-014/F-015/F-017/F-029 deixa de nascer `BLOQUEADO` por esse item.
- **As 8 decisões seguem abertas.** Nenhuma foi respondida; o Edu pode virar qualquer uma a qualquer
  momento. Virada em item que já tem código = **classe C** (reconstrução completa de `data/canonical/` +
  diff numérico). Cada feature afetada carrega a decisão como **item de DoR declarado**, não resolvido.
- **O único gate que permanece duro é a PUBLICAÇÃO.** Nenhum número vai ao Comitê/Alexandre sem
  **ADR-001 aceito** (`AGENTS.md §14` passo 2 · CA-090). Em `Proposta`, o veredito é
  `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA`, e isso vale também para "só esse número no WhatsApp":
  **não existe classe A/B para publicação.**
- Registro datado em `docs/plans/DECISIONS_LOG.md §2`. Também nesta data: repositório remoto GitHub
  conectado (`main`) e **Supabase descartado na v1** → **ADR-007 (Aceita)**.

### Itens da SPEC que o dado real não fecha (não editei a SPEC — `AGENTS.md §8`)

- [ ] **SPEC CA-004/CA-005 — limiares irrealistas, proposta em `DECISIONS_LOG §2` (D-e).**
      **CA-004** pede número-índice "monotônico não decrescente em **>= 99%** dos meses"; a série
      real `SIDRA_1737_V2266` tem **0,9626** no histórico completo (21 meses de deflação de
      verdade, 199708→202608) e **0,9435** de 2006 em diante. **CA-005** pede tolerância
      **<= 1e-6** entre a razão do número-índice e o encadeamento geométrico de `v/63`; medido:
      **3,52e-04 pp** em 83 trimestres, contra um limite **analítico** de 3,97e-04 pp que vem das
      **2 casas decimais** com que o IBGE publica o número-índice. Nenhum dos dois é defeito do
      extrator: o código afirma a medição, e o teste de CA-005 exige também `<= 2×` o limite do
      arredondamento, que é o que prova que as duas séries são **a mesma coisa** em vez de só
      "parecidas". **Proposta:** CA-004 → 90% (ou reescrita como "não é série de variação");
      CA-005 → 1e-3 pp. **Quem decide:** Edu. Até lá, `MONOTONIA_MINIMA = 0,90` e a tolerância de
      1e-3 pp estão no código de F-004, com o desvio escrito no docstring e no `DECISIONS_LOG`.

- [ ] **SPEC CA-025 — a inclinação real de 5a−1a não chega a 95% dos dias úteis; resolvido em
      caráter provisório por `D-i` em `DECISIONS_LOG §2.1`.** CA-025 pede valor para **≥ 95%** dos
      dias úteis de 2006→2026 na inclinação real. Medido por F-016 sobre as 5.184 datas base de
      2006-01-01 a 2026-10-09: `INCLINACAO_REAL_5A_1A` existe em **60,53%** — e **nenhuma
      implementação chega a 95%** com o vértice curto de 1 ano, porque a grade de vencimentos da
      NTN-B é de 15/05 e 15/08 de anos **alternados** e **2021 e 2022 inteiros** não tiveram título
      vencendo em menos de 1 ano. Chegar a 95% exigiria extrapolar, o que a Anti-SPEC §10.1.1
      proíbe. A premissa do CA olha a **ponta longa** (de fato 100%); o que limita é a **curta**.
      **Resolução do orquestrador (D-i, provisória):** acrescentar ao catálogo o vértice de **3
      anos** — que **CA-023 já nomeia** ("interpola para 1, 3 e 5 anos"), portanto não é escopo novo
      — e promover **`INCLINACAO_REAL_5A_3A` (95,25% ✔)** a variável principal de regime, mantendo
      as duas 5a−1a publicadas como **secundárias com a cobertura declarada**. Catálogo 134 → **138**.
      Os dois números estão travados por teste
      (`test_cobertura_da_inclinacao_real_1a_e_a_medida_e_nao_atinge_os_95_de_ca025` e
      `test_inclinacao_real_5a_3a_e_a_que_fecha_ca025`) e **a SPEC não foi editada** (`AGENTS.md §8`).
      **Quem decide:** Edu — e **ADR-004 §3 nomeia a 5a−1a como principal**, então o ADR precisa de
      uma **nota editorial** quando for aceito. As duas alternativas recusadas ficam registradas em
      `DECISIONS_LOG §2.3` (D-i): usar a inclinação **nominal** 5a−1a como principal (97,57%,
      mas inverte ADR-004 §3) ou manter como está e declarar que ~40% dos trimestres podem cair num
      dia sem valor.

- [ ] **SPEC CA-007 — o hiato do IBC-Br não pode existir nos 83 trimestres; 16 nulos aceitos por
      `D-m` em `DECISIONS_LOG §2.3`.** CA-007 pede `ibcbr_gap` para **todos** os 83 trimestres **ou**
      o trimestre marcado `is_estimated=True`; CA-060 permite `is_estimated=True` **só** em
      `2026Q3`. As duas não podem valer juntas, e a aritmética mostra por quê: o IBC-Br dessaz.
      (SGS 24364) **começa em 2003** (a série da fonte; o extrator pega de 2004) → `ibcbr_yoy`, que
      precisa de `T−4`, só existe de **2005Q1** → a média móvel de **20 trimestres com janela
      cheia** só fecha em **2009Q4**. Para ter hiato em `2006Q1` seria preciso IBC-Br desde
      **2000Q2**, e **a série não existe**. Nenhuma grade de apoio resolve.
      **Resolução do orquestrador (D-m, provisória):** aceitar `ibcbr_yoy_trend`/`ibcbr_gap` nulos
      em `2006Q1..2009Q3` + `2026Q3` (**16**), com o motivo publicado em `relatorio_macro.json`.
      **Consequência a jusante, que precisa ir à página de limitações (F-028):** a V1 de F-019
      classifica **67** dos 83 trimestres — **2006-2009, inclusive a crise de 2008, fica fora do
      eixo de crescimento** com a regra estrita. A alternativa está **medida** no relatório
      (`sensibilidade_ibcbr_gap`): `min_periods = 8` recuperaria **12** trimestres com
      `max |diferença| = 0,0 pp` no trecho comum, e **não** foi adotada porque média de janela
      parcial é outro estimador, cujo significado muda ao longo do tempo (o hiato de 2006 deixaria
      de ser comparável ao de 2015) — está em §6 como opção, não como dívida.
      **A SPEC não foi editada** (`AGENTS.md §8`). **Quem decide:** Edu — 3 saídas: aceitar os 16
      nulos (o que está publicado), adotar `min_periods = 8`, ou mudar o eixo de crescimento da V1.

### Aceites das decisões da parte 2 da Onda 2 (D-k..D-q, 2026-10-11)

> Registradas em `DECISIONS_LOG §2.3` com data e **"aguarda Edu"** onde couber. Nenhuma toca SPEC,
> PRD, Anti-SPEC ou o e-mail de escopo. O que precisa de ratificação, em uma linha cada:

| # | Decisão | Quem decide | O que acontece se o Edu discordar |
|---|---|---|---|
| **D-k** | Focus **fora** de `raw_series` (5 exclusões, pelo precedente do painel do Tesouro); F-015 o lê de `data/processed/focus/` e a procedência aponta para o EntitySet | ratificação de **contrato** (CA-055/CA-120) | a alternativa é desdobrar os 197 `series_id` compostos no catálogo — mudança de contrato, não de implementação |
| **D-l** | `USDBRL` no universo de `asset_returns_quarterly` (24 ativos, 1.963 linhas), `is_total_return=False` | **Edu** — muda o universo de uma tabela canônica | remover é 1 linha em `UNIVERSO` + rebuild; RF-038 volta a ficar sem o retorno do dólar |
| **D-m** | CA-007 não satisfazível; 16 nulos em `ibcbr_gap`, SPEC intacta | **Edu** | `min_periods = 8` (recupera 12, medido) ou outro eixo de crescimento → re-roda os 83 `ibcbr_gap` |
| **D-n** | `INCLINACAO_REAL_5A_3A` sem coluna em `MacroQuarterlySchema`; F-019/F-021 leem a série | orquestrador, com dívida em §6 | acrescentar a coluna é feature **classe C** própria (alteração de schema) |
| **D-o** | Unidade: `macro_quarterly` em por cento/pp, `asset_returns_quarterly` em fração | registro (é o estado medido) | unificar escala re-roda as duas tabelas e muda todo canário publicado |
| **D-p** | `FOCUS_PIB_TOTAL` → `status: descartada` (G-04 resolvido) | orquestrador | nenhuma consequência numérica: a série nunca foi extraída por essa entrada |
| **D-q** | Achados do Focus registrados: G-04, G-05, exceção a **D-a**, `%20` × `+`, `ibcbr_yoy` em fim de período | registro de **achado**, não escolha | só (e) é reversível: trocar `ibcbr_yoy` para média do trimestre muda os 83 `ibcbr_gap` |

### Aceites das decisões da Onda 3, parte 1 (D-r..D-x, 2026-10-11)

> Registradas em `DECISIONS_LOG §2.3` (parte 3) com data e **"aguarda Edu"** onde couber. Nenhuma
> toca SPEC, PRD, Anti-SPEC ou o e-mail de escopo. **D-s, D-t e D-u mudam número publicado** e são
> as que precisam de ratificação:

| # | Decisão | Quem decide | O que acontece se o Edu discordar |
|---|---|---|---|
| **D-s** | **`ibcbr_yoy` = média dos 3 meses do trimestre**, não fim de período (metodologia §2, QA-A P1-1) | **Edu** — muda o eixo de crescimento da V1 | voltar ao fim de período é 1 linha + rebuild da cadeia; devolve a distribuição EXP 20 · REC 17 · EST 15 · DES 15 e **7 trimestres** mudam de quadrante de volta (2013Q2-Q4, 2020Q1, 2023Q3, 2024Q1, 2025Q2). Travado por teste e canário |
| **D-t** | **ciclo Selic: `\|Δ\| >= 0,25 pp` é movimento** (desigualdade não estrita), QA-A P1-2 | **Edu** | voltar à desigualdade estrita é 2 caracteres + rebuild; devolve CORTE 29 · NEUTRO 30 · ALTA 24 e põe os cortes reais de 25 bps de **2024Q2/Q3** em `NEUTRO`. Travado por 2 testes |
| **D-u** | **eixo de crescimento da V3 = `focus_pib_ano`** (substitui `z_ibcbr_gap`); `regime_v1_neighbor` segue `nullable=False` e **F-022/F-024 leem `regime_neighbors_v3.parquet`** | **Edu** (o eixo) + orquestrador (o schema) | sem o Focus a V3 **não tem vetor para `2026Q3`**, que é a pergunta do Comitê, e perde 2006-2009. Tornar a coluna anulável é feature **classe C** própria (§6) |
| **D-r** | F-019 grava `regimes_v1.parquet` (`RegimesV1Schema`, acréscimo), junção em `RegimesSchema` delegada a **F-022** | orquestrador (**aceita**) | as 3 alternativas são inventar dado ou **alterar** schema ⇒ pausa |
| **D-v** | as 3 correções dos P1 dos QAs: `exigir_series` também contra `alinhado_trimestral`; `versao_build` normaliza o fim de linha; janela do CDI vira **limitação declarada** | orquestrador (**aceita**) | nada a desfazer — são guardas e uma declaração; `fonte_versao` de **toda** a camada mudou uma vez, de propósito |
| **D-w** | `CONTRACTS.md` atualizada com o estado medido (2 materializações de procedência, `RegimesV1Schema`, `RegimeNeighborsV3Schema`, `FEATURES_V3` 6/5) | orquestrador (**aceita**) | só texto |
| **D-x** | paths em `apps/pipeline/canonical/` em vez de `transform/`/`analysis/` | orquestrador (**aceita**) | `git mv` + imports, zero linha de lógica |

> ⚠️ **ITEM PARA O COMITÊ, não para o Edu decidir: a V1 NÃO É OPERACIONAL na forma `asof`.**
> A troca de rótulo entre `revised` e `asof` é **33,33% (22/66)** — era **29,85% (20/67)** antes de
> D-s —, acima do limiar de **25%** de **CA-074** e de `metodologia §5.1`. Pelo critério escrito, a
> leitura **operacional** ("em que quadrante estamos agora, com o que se sabia na época") cai, e com
> ela a hipótese **H-03 do PRD**; a leitura **descritiva** (RF-027, "em que quadrante cada trimestre
> do histórico caiu") continua válida e é o entregável. Isso **tem** de ir à página de limitações
> (**F-028**) e ao slide do Comitê — não a nota de pé. As saídas possíveis, nenhuma escolhida aqui:
> (a) assumir a V1 como **descritiva** e dizer isso; (b) trocar o eixo de crescimento por um menos
> sensível à defasagem (PIB t/t dessaz., ou surpresa vs. Focus = **V1b/F-033**); (c) regime
> **mensal** na fase 2. Mecanicamente o motivo é conhecido: `ibcbr_gap` é um hiato pequeno (mediana
> `|g| ≈ 2 pp`) sobre média móvel de 20 trimestres, e deslocar o IBC-Br de um trimestre troca o
> sinal com facilidade.

### Aceites formais pendentes dos ADRs da camada canônica (2026-10-11)

> **Desenvolvimento liberado, aceite formal pendente** — a autorização do Edu de 2026-10-10
> (`DECISIONS_LOG §2`) vale para implementar; o **merge** de uma classe C com o ADR em `Proposta` é
> chamada do orquestrador, e a **publicação** segue travada por ADR-001 (`AGENTS.md §14`).

- [ ] **ADR-006 (Parquet por camada + DuckDB + convenção de alinhamento/retorno) — `Proposta`.**
      F-013 depende da parte **(a)** (armazenamento) e **F-014 é a parte (b)** (fim de período +
      ffill ≤ 5), já **materializada** em `alinhado_trimestral`. O que o Edu precisa ratificar, em 3
      perguntas: (1) **último dia útil**, não média de período; (2) ffill ≤ **5** d.u.; (3) a opção
      **(a)** de D-h, com os **215** ffill na página de limitações. Pendência editorial do próprio
      ADR: §(a).2 escreve `data/canonical/macro.duckdb` e o implementado é **`ldc.duckdb`** —
      decisão do orquestrador: **manter `ldc.duckdb` e corrigir o ADR quando for aceito** (§6).
- [ ] **ADR-004 (curva via Tesouro Direto, não ETTJ ANBIMA paga) — `Proposta` (L4).** F-005 e F-016
      implementadas sobre ele. Duas notas a incorporar no aceite: **D-i** (a variável principal passa
      a ser a inclinação **5a−3a**; §3 do ADR ainda diz 5a−1a) e **D-j** (prazo em **dias corridos**,
      com o custo medido em fração de bp). `confianca = NAO_VERIFICADO` nas 11 entradas da curva
      **continua correto** até a revisão numérica independente aprovar, e **nenhum número de F-016 é
      publicável** fora do fluxo classe D.
- [x] **D-h — grade das séries da B3: escolhida a opção (a)** (grade bancária única + 1 d.u. de ffill
      no 4T), **provisória**. Custo medido: **215** células de 4.038 (5,325%), 11 séries `B3_API`, 20
      trimestres, **zero** ffill de 2..5. Travada no contrato pelo check
      `quarter_end_unico_por_trimestre`: virar para (b) é mudança de schema, não de código.
      **Consequência medida depois (QA-B P1-1, D-v c):** é D-h que faz a janela do CDI divergir do
      caminho do ativo em 1 a 3 d.u. em **599 das 1.857** linhas com excesso — viés médio de
      **0,0185 pp** e **máx 0,1575 pp** no `ret_excesso_cdi`. Limitação **declarada**, cálculo
      intacto.
- [ ] **ADR-001 (lente de regime oficial: V1 quadrantes + aceleração) — `Proposta`.** É o **único**
      gate duro de publicação: `especificacao_congelada` é lido do **status do ADR em disco**, com
      falha fechada, então hoje F-019 e F-021 publicam `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA` nas
      83 linhas e **nenhum número de regime é publicável** (CA-090, `AGENTS.md §14`). O dia em que o
      Edu virar **D1/D3** e aceitar o ADR, **um rebuild** muda as 83 linhas — zero linha de código.
      O aceite precisa absorver **três** notas: **D-s** (eixo de crescimento sobre a média do
      trimestre), **D-t** (desigualdade do ciclo Selic) e o achado de **CA-074** acima, que é
      material para o §Consequências do próprio ADR.

> **8 decisões de Edu/Alexandre seguem abertas** (bloqueavam o início da implementação — ver o estado de
> 2026-10-10 acima). Origem: `docs/product/PRD.md §13.2`
> (PRD gerado em modo autônomo em 2026-10-10 — nenhuma dessas respostas veio de humano). Enquanto não
> respondidas, as features de regime e os extratores do caminho crítico carregam a decisão como **item de
> DoR declarado** e nada que derive delas é **publicável**.
> Cada item traz a **recomendação da pesquisa** — responder "aceito a recomendação" já destrava.

- [ ] **D1 — Qual lente de regime é a oficial do Comitê?** (V1 / V2 / V3 / as três). Define o que o notebook
      entrega e o que vai ao slide, e precisa estar congelada em ADR **antes** de rodar sobre os retornos
      (RF-031). *Recomendação: V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário.*
      → **ADR-001** (Proposta) · features afetadas: **F-019, F-020, F-021, F-023, F-024, F-031**
- [ ] **D3 — Eixo inflação da V1: nível vs. meta ou aceleração (Δ IPCA 12m)?** Muda o rótulo dos 83
      trimestres; reclassificar depois invalida o heatmap. *Recomendação: aceleração.*
      → **ADR-001** (Proposta) · features afetadas: **F-015, F-019** (e G-02 se virar "nível vs. meta")
- [ ] **D5 — Métrica primária do heatmap: nominal, excesso sobre CDI ou real?** É a coluna do entregável
      visual central (RF-033). *Recomendação: excesso sobre CDI (neutraliza a Selic de 19% → 2% → 14%).*
      → **ADR-002** (Proposta) · features afetadas: **F-023** (1 parâmetro), **F-022, F-024**
- [ ] **D6 — Internacional: piso estrutural, 100% tático por regime ou híbrido?** Sem isso não se sabe o que
      RF-038/RF-039 devem entregar — e é a resposta ao item C1 do e-mail. *Recomendação: piso 16-20% + banda
      tática 15-35% por regime (n≈20 não sustenta número pontual).*
      → **ADR-003** (Proposta) · features afetadas: **F-026** (formulação), **F-031**
- [ ] **D12 — Setoriais B3 e FII segmentado entram no pacote mínimo?** (completo / best-effort / fora).
      Define quantos extratores entram no caminho crítico de 3 dias. *Recomendação: best-effort, com `n` e
      `data_inicio` visíveis.*
      → **ADR-005** (Proposta) · features afetadas: **F-006, F-012, F-023**
- [ ] **L1 — IFIX só existe de 2011 em diante (metade da janela).** Aceitar janela própria 2011-2026?
      *Recomendação: janela própria + IMOB (2008+) como proxy imperfeito; **não** reconstruir IFIX sintético.*
      → **ADR-005** (Proposta) · features afetadas: **F-006, F-017, F-022, F-028** (virada = painel
      balanceado muda o universo de todas as tabelas)
- [ ] **L2 — Segmentação de FII (Tijolo/Papel/Logística/Shoppings) só desde 2019 e via provedor privado
      (Teva) sem licença comercial explícita.** Autorizar o uso? *Recomendação: usar para dispersão setorial,
      declarando que cobre ~2 ciclos macro; tratar como qualitativo.*
      → **ADR-005** (Proposta) · features afetadas: **F-012** (cortada inteira se negado), **F-038**
- [ ] **L4 — ETTJ oficial da ANBIMA com 20 anos exige contratar o ANBIMA Feed (≈R$ 686–8.238/mês).**
      Contratar ou aceitar a inclinação construída do Tesouro Direto? Era pedido explícito do e-mail (item A6).
      *Recomendação: Tesouro Direto — tecnicamente defensável sem comprar o Feed; registrar em DECISIONS_LOG
      e comunicar ao Alexandre.*
      → **ADR-004** (Proposta) · features afetadas: **F-005, F-016** (vira **classe D** se o Feed for
      contratado), **F-009**

**Não bloqueantes** (17 decisões D2/D4/D7-D11 e lacunas L3/L5-L13 + 7 gaps "a confirmar") estão em
`docs/product/PRD.md §13.3` e §13.4 com a recomendação adotada por padrão — podem ser decididas durante a
execução, sem travar o início.

> Se tiver bloqueio: descreva o problema, o que já foi tentado e o que precisa para destravar.
> **Não pausar trabalho em outra feature para resolver bloqueio** — use o bloqueio como input de conversa
> com o humano/Alexandre e siga em outra coisa.

**O que NÃO está bloqueado** (pode começar agora, sem nenhuma das 8 respostas): **F-001 a F-011** e
**F-013, F-014, F-015, F-017, F-018, F-029, F-030** — extração e camada canônica. As features de
regime/visualização (**F-016, F-019 a F-026**) carregam a decisão como **item de DoR** e podem ser
implementadas com o padrão provisório, mas **não publicadas** sem ADR aceito.

---

## 5. Bugs abertos

| ID | Descrição curta | Repro | Gravidade | Classe se virar feature | Nota |
|---|---|---|---|---|---|
| — | *(vazio)* | — | — | — | — |

> Em projeto de dados, "bug" inclui: série com buraco não explicado, divergência entre fontes, número que
> mudou sem mudança de código, extrator que falha silenciosamente. Use `/triage-bugs` com ≥ 2 itens.

---

## 6. Ideias / parking lot

> Coisas que apareceram mas não devem quebrar o foco. Revisar a cada 2 semanas.

- Monitor de "última observação envelhecida" por série (alerta de descontinuação — riscos R16/R5).
- Reconciliação automática ANBIMA S3 × SGS na data de corte 22/05/2023 como teste de regressão diário.
- Abertura setorial do PIB (SIDRA `c11255`) cruzada com os índices setoriais da B3.
- Cupom cambial (DDI/FRC) como proxy de risco-país market-implied (exige `pyield` / Python 3.12).
- Juro real ex-ante a partir da inflação implícita própria (breakeven de F-016) em vez do Focus.
- **Dívida técnica — migrar F-009 para `apps.pipeline.common`:** o job `apps/pipeline/jobs/anbima_daily.py`
  tem camada HTTP e normalizador de número próprios (`_sessao`/`baixar`/`detectar_corpo_suspeito`/
  `_para_float_br`), anteriores a F-001; o `# TODO(F-001)` já está no módulo. Trocar por `ClienteHTTP` +
  `detectar_formato`/`exigir_formato` + `para_float_ptbr`. **Os testes de parse não devem mudar** — se
  mudarem, a migração regrediu (`docs/wiki/modules/anbima.md`, `docs/wiki/architecture.md`).
- **Decisão aberta — `--record` em `tests/conftest.py`:** `tests/fixtures/README.md` atribuía a flag a
  F-001, mas `conftest.py` é arquivo compartilhado da onda e não estava na lista de arquivos de F-001;
  ficou **não implementada**. Opções: feature A própria, ou `pytest_addoption` acrescentado pelo
  orquestrador. Nada depende disso para gravar fixture (hoje é script de sessão).

**Dívidas remanescentes da Onda 1** (nenhuma bloqueia o QA; levantadas pelos 7 relatórios e
confirmadas na consolidação):

- **Cache condicional por fonte fica em F-030.** A primitiva existe desde F-001 e os manifestos já
  gravam `ETag`/`Last-Modified` onde a fonte os serve (S3 da ANBIMA, CKAN do Tesouro — que responde
  **304 com 0 byte** e evita 14,6 MB por rodada, medido ao vivo; a planilha de feriados). Nenhum
  extrator liga a revalidação: `cache_condicional=False` em todos. A **política** (quem revalida, com
  que frequência, o que fazer com o 304) é F-030. Yahoo, MSCI, B3 e apisidra não serviram validador
  útil nesta sessão.
- **Reextrair 2026 da B3 depois do Comitê.** `data/processed/b3/*.parquet` fecha 2026 com 194 pontos
  (até 09/10). Quem rodar depois de 14/10 precisa reextrair o ano corrente — `--anos 2026` basta.
- **`MSCI_BRAZIL` continua `a_confirmar`:** o código `705000` devolve `INDEX_LEVELS: []` com HTTP 200
  (fixture gravada como caminho de erro). Nenhum identificador foi inventado.
- **`GOLD_BRL` segue `BLOQUEADO — FONTE INDISPONÍVEL`** (gap G-03). Nenhum proxy adotado.
- **Duration (d.u.) e PMR do IMA não são extraídos.** As 7 colunas derivadas da planilha da ANBIMA
  ficaram de fora porque `processed_series` é **uma métrica por série**. Se F-016 pedir Duration do
  IMA, é **série nova no catálogo** (`ANBIMA_<SLUG>_DURATION`), não coluna extra no Parquet.
- **G-01 — retorno total dos 9 setoriais da B3** continua declarado e não resolvido:
  `is_total_return` é `True` só em IBOV e IFIX; nos setoriais segue `None` e tem de ir para a página
  de limitações (F-028).
- **`entrada_do_catalogo` ainda é importada de `extract/yahoo.py` por `extract/msci.py`** (3 linhas
  sobre o catálogo). Com D-g o acoplamento pesado saiu; este resto desce quando F-011 tocar os dois.
- **Retenção de `data/raw/`:** 14,6 MB por download efetivo do Tesouro e 2,2 MB de respostas da B3.
  Sem política de expurgo — também F-030.

**Dívidas levantadas pelo QA da Onda 1** (nenhuma bloqueia a Onda 2):

- **CI · a evidência da consolidação pula no CI** (P1-4 do lote A). `test_contract_sgs_sidra.py` e
  `test_processed_layer_conventions.py` são a **única** trava regressível de D-a, D-b, PK única e da
  reconciliação SGS × SIDRA, e **pulam** no `actions/checkout` porque `data/` não está no git
  (9 skipped, medido pelo revisor). Caminho: job **N2** que monte uma `data/processed/` mínima **das
  fixtures** (que estão no git) e rode as duas varreduras de verdade.
- **`YAHOO_DXY` leva 1.210 linhas com `value = NULL` (17,41%) e o comentário que as justifica está
  errado** (P2-2 do lote B): o revisor mediu **1.188 domingos**, não "feriado da praça". Domingo é
  dia sem sessão, que F-006 na mesma onda **omite** (CA-037). `DX-Y.NYB` é RF-017 (`should`) e não é
  insumo de nenhuma coluna do pacote mínimo. Caminho: descartar os dias sem sessão **ou** corrigir o
  comentário e declarar a convenção — antes de a série entrar em qualquer figura.
- **`YAHOO_GSPC` tem `is_total_return = None`, não `False`** (P2-3 do lote B): a derivada `SP500_BRL`
  declara `False` corretamente, mas quem consumir a série em USD direto não tem como saber que é
  price return — e é por essa flag que a Anti-SPEC §10.2.12 funciona. 1 linha no catálogo.
- **`vintage` é a data **UTC** do fetch, e isso não é comparável entre features** (P2-5 do lote B):
  B3 (`2026-10-10T23:49Z`) e Yahoo/MSCI (`2026-10-11T00:14Z`) foram coletados a 25 min de distância e
  ficaram com safras **diferentes**. D-b está cumprida ao pé da letra; falta decidir se a safra é UTC
  ou hora local — 1 linha em `DECISIONS_LOG §2.1`.
- **Markers de `tests/` descrevem a dependência errada** (P2-6 do lote B): 2 testes
  `@pytest.mark.network` de F-005 **não abrem socket** (leem `data/raw/`), e um `pytest.skip`
  condicional pode apagar em silêncio a única prova viva do HTTP 304. Sugestão do revisor: marker
  próprio (`requires_raw`) e `pytest.fail` em vez de `skip`.

**Dívidas da Onda 2 — F-013, F-014 e F-016** (nenhuma bloqueia o QA; todas são escolha do
orquestrador, não bug):

- **O marker `integration` não existe e `pyproject.toml` está congelado.**
  `[tool.pytest.ini_options] markers` tem só `network` e `slow`, e `addopts` traz `--strict-markers`:
  `@pytest.mark.integration` **falharia a coleta**. Por isso `tests/integration/` segue vazio e a
  cobertura de integração de F-013/F-014 está em seções declaradas dos arquivos de `tests/unit/`
  (padrão já aceito em `test_processed_layer_conventions.py`), que **pulam** sem `data/processed/`.
  Fechar é **1 linha** no `pyproject` + mover as seções — e aí o N2 passa a existir de verdade,
  junto com o job do P1-4 acima.
- **`ldc.duckdb` × `macro.duckdb` — DECIDIDO: manter `ldc.duckdb`.** ADR-006 §(a).2 escreve
  `data/canonical/macro.duckdb`; o briefing da Onda 2 pediu e F-013 implementou **`ldc.duckdb`**
  (constante `NOME_DUCKDB`, um lugar só). É divergência de **nome**, zero semântica. Decisão do
  orquestrador: **fica `ldc.duckdb`**, e o **ADR-006 recebe a correção editorial quando for aceito**
  (§4) — não se renomeia um artefato vivo para casar com um ADR em `Proposta`.
- **`ldc.duckdb` não tem view de `alinhado_trimestral`.** `construir_duckdb` vive em
  `build_raw_series.py` (congelado para o agente de F-014) e cria só as duas views de F-013. É 1
  linha lá, ou um passo novo no build; **zero** efeito em dado, porque as views são `SELECT * FROM
  read_parquet(...)` e o Parquet já está escrito.
- **A flag `vertice_extrapolado` de CA-023 não é coluna do canônico.** `ProcessedSeriesSchema` tem 8
  colunas e nenhuma é booleana, então F-016 materializou a flag em **três** lugares equivalentes: a
  linha existe com `value` nulo (a ausência está no dado), `relatorio_curva.json → motivos` traz a
  contagem por motivo e `pct_nulos_por_ano`, e o quadro de diagnóstico em memória tem a coluna. Se
  F-019/F-026 precisarem dela **como coluna** de `raw_series`, é **alteração** de schema → feature
  **classe C** própria, não acréscimo.
- **A largura do intervalo de interpolação é registrada mas não limita nada.** Medido: mediana 458 d
  e **máximo 1.461 d** em `CURVA_REAL_1A`; mediana 731 d e máximo 2.191 d em `CURVA_REAL_5A`. Um
  vértice interpolado entre títulos de 1 e 5 anos é mais frágil que um entre 11 e 13 meses, e hoje os
  dois saem indistinguíveis no Parquet. Definir um **teto** é escolha metodológica nova — não foi
  implementada por conta própria e precisa de decisão (candidata a nota em ADR-004).
- **`pct_nulos` não tem limiar** (P2-4 do QA de F-013, **em aberto**): uma série 100% nula passa o
  build com `pct_nulos = 100.0` e **sem aviso**. Não corrigido de propósito — um limiar é **check
  novo de schema**, portanto mudança de contrato (classe C), e nenhuma série real passa de 17,41%
  (`YAHOO_DXY`). Se virar risco, o lugar é o schema, nunca o build.

**Dívidas da Onda 2 — F-015, F-017 e F-010** (nenhuma bloqueia o QA; todas são escolha do
orquestrador ou de Edu, não bug):

- **Coluna `inclinacao_real_5a_3a` em `MacroQuarterlySchema` (D-n).** A inclinação **principal** de
  D-i é a 5a−3a (95,25% de cobertura, a que fecha CA-025) e o schema só prevê a 5a−1a, que
  `macro_quarterly` publica com **33 nulos (39,8%)**. Acrescentar coluna a tabela canônica é
  **alteração de schema classe C** → feature própria, depois do Comitê. Até lá F-019/F-021 leem a
  **série** de `raw_series`/`data/processed/curva/` via `alinhar_series`. Provavelmente vai junto a
  `inclinacao_nominal_5a_3a`, para o par ficar simétrico.
- **`termos_troca_yoy` segue 100% nula, sem fonte.** O proxy **IC-Br do BCB** (SGS **27574/27575**)
  resolveria com um extrator de **1 série** — é o escopo de **F-037** (pacote estendido). Hoje a
  coluna existe, é 100% nula e o motivo está no `relatorio_macro.json`; **nada é estimado**. Decidir
  é escolher entre (a) trazer o IC-Br para dentro do pacote mínimo, ou (b) manter a coluna nula e
  declará-la na página de limitações (F-028).
- **`min_periods = 8` no hiato do IBC-Br está MEDIDO e não adotado (D-m).** `relatorio_macro.json →
  sensibilidade_ibcbr_gap` mostra que recuperaria **12** dos 16 trimestres nulos com
  `max |diferença| = 0,0 pp` no trecho comum. Não é dívida de implementação (já está medido) e sim
  **decisão de método do Edu** (§4): média de janela parcial é outro estimador, cujo significado
  muda ao longo do tempo. Adotar é 1 constante + re-rodar os 83 `ibcbr_gap`.
- **`asset_returns_quarterly` não tem flag de trimestre corrente incompleto.** `is_estimated` é de
  `macro_quarterly` (CA-060) e `AssetReturnsQuarterlySchema` é `strict` com 16 colunas — acrescentar
  é alteração de schema. Hoje **nenhuma linha é parcial** (`2026Q3` está fechado: CDI com 65 d.u.,
  IPCA com 3 meses, níveis em 30/09/2026), mas se o acervo for reextraído **no meio** de um
  trimestre o `ret_tri` corrente sai calculado contra o último fechamento, com `n_dias_uteis` baixo
  como **único** sinal. Duas saídas: (a) o build de entrega roda só com trimestre fechado — **regra
  de operação, recomendada para 2026-10-14**, e é a que vai para
  `runbooks/reconstruir-dataset.md`; (b) F-022 junta por `quarter` e filtra pelo `is_estimated` de
  F-015, na fase 2.
- **Top5 e V1b do Focus seguem fora de escopo** (F-033 / SPEC §10.5), como o contrato de F-010
  manda: o extrator traz a **mediana** do consenso, não a distribuição nem o Top5. `surpresa_ipca`,
  `surpresa_pib` e `surpresa_selic` **já existem** em `macro_quarterly` como colunas; o que falta é
  a **lente** V1b que as usa como eixo em vez da tendência.
- **`ExpectativasMercadoInflacao24Meses` não foi extraído** (não está no Feature Contract de F-010).
  É o **mesmo `EntityType`** do de 12 meses: **1 entrada em `PLANO`** + 1 no catálogo. O horizonte
  de 24 meses é o que a metodologia usa para expectativa "ancorada"; com 12 meses o juro real
  ex-ante fica mais sensível ao choque corrente.
- **Indicadores do Focus fora do pacote mínimo:** `IPCA Livres`, `IPCA Serviços`,
  `IPCA Administrados`, `IGP-M`, `Taxa de desocupação`, `PIB Indústria/Serviços/Agropecuária`,
  `Resultado primário`, `Dívida bruta`… Estão **enumerados** em `INDICADORES_ENUMERADOS` e entram com
  **1 linha em `PLANO`** cada. Fora do e-mail A3, logo fora do caminho crítico de 2026-10-14.
- **Horizonte anual `HM1` do Focus existe e não é gravado:** é sazonal (só no começo de janeiro) e
  produziria série com vão de ~11 meses; está **contado** em `fora_do_horizonte`. Se a surpresa de
  IPCA do **ano fechado** virar insumo de regime, é 1 chave em `PLANO` + afrouxar a continuidade
  daquela série.
- **`ldc.duckdb` não tem view de `macro_quarterly` nem de `asset_returns_quarterly`.**
  `construir_duckdb` vive em `build_raw_series.py` e cria só as duas views de F-013 — são 2 linhas
  lá (ou um passo novo no orquestrador de F-029), **zero** efeito em dado, porque as views são
  `SELECT * FROM read_parquet(...)` sobre Parquet já escrito. Mesma dívida de
  `alinhado_trimestral`, acima.
- **`ciclo_selic` é função publicada, não coluna.** O rótulo mora em `RegimesSchema` (F-020) e o
  insumo (`selic_meta_delta`) em `macro_quarterly`; a função `ciclo_selic(delta_pp)` vive no módulo
  de F-015 e o relatório publica a distribuição medida — **`CORTE 34 · NEUTRO 23 · ALTA 26`,
  `sem_delta 0`** desde **D-t** (era 29/30/24 com a desigualdade estrita). Quem implementar F-020
  **importa a função**, não reimplementa o limiar.
- **Limitação medida do schema wide:** `coerce=True` roda **antes** do check de nulidade, então um
  `None` em `vertice_extrapolado` entra como `False` em vez de ser rejeitado — e `False` significa
  "nenhum vértice faltou", o **oposto** da ausência. Está travado em teste
  (`test_vertice_extrapolado_nulo_e_coagido_para_false_e_nao_rejeitado`); a guarda real é o build,
  que sempre calcula a flag dos 4 vértices. Fechar de verdade exige mudar a ordem de validação do
  pandera ou tornar a coluna anulável — alteração de schema.
- **Convenção de unidade duplicada (D-o).** `macro_quarterly` (por cento) e
  `asset_returns_quarterly` (fração) publicam `cdi_tri`/`ipca_tri` com o **mesmo nome**. Não há bug
  hoje (F-017 nunca lê `macro_quarterly`; `max |macro − 100 × retornos| = 0,0`), mas o próximo
  consumidor que cruzar as duas erra por 100x. Caminho da fase 2: consumidor único, ou sufixo de
  escala no nome. **F-021 já é esse consumidor** e resolve na mão: o ranking sai em **fração** e o
  relatório declara.

**Dívidas da Onda 3, parte 1 — F-018, F-019 e F-021** (nenhuma bloqueia o QA; todas são escolha do
orquestrador, não bug):

- **`regime_v1_neighbor` é `nullable=False` e por isso existem DOIS artefatos de vizinhos (D-u).**
  `RegimeNeighborsSchema` só admite vizinho **com rótulo** V1, e por **D-m** 16 trimestres não têm
  quadrante — então `regime_neighbors.parquet` (5.500 × 11, o de contrato) perde **4 dos 8**
  vizinhos de `2026Q3` (Jaccard **0,33**), inclusive 2006-2009 e a crise, **sem que a tabela diga
  que perdeu**. A saída recomendada é tornar a coluna **anulável** com uma coluna de status, como
  F-019 fez em `RegimesV1Schema`: aí os dois artefatos colapsam num só e
  `regime_neighbors_v3.parquet` deixa de existir. É **alteração de schema existente ⇒ feature
  classe C própria**, e não foi feita. Até lá, **F-022/F-024 leem o `_v3`** (regra escrita em
  `CONTRACTS.md §5.2a`) e a perda vai à página de limitações (**F-028**).
- **`MIN_OBS_PADRONIZACAO_EXPANDING = 20` é constante nova do módulo `regimes_v3.py`, não do
  contrato.** Não vem de `CONTRACTS.md §5.3`: é a janela que ADR-001 §4 já usa para tendência,
  reaproveitada como "história suficiente" para a variante `somente_passado` do z-score. Afeta
  **só** essa variante (19 referências a menos); a lente principal não depende dela. Se o
  orquestrador preferir 12 ou 24, é 1 constante — mas o lugar certo é o contrato.
- **`lag_divulgacao_dias` é defasagem típica em DIAS CIVIS e não foi auditado release a release.**
  Os valores do catálogo (PIB 60, IBC-Br 45, IPCA 10) vêm do texto da metodologia, não do
  calendário real de divulgação do IBGE/BCB. Se o IBGE atrasar um release específico, a `asof`
  **daquele** trimestre é otimista. Arredondar para cima é conservador (descarta informação, nunca
  cria look-ahead), mas a auditoria não foi feita. Um extrator do calendário de divulgação
  resolveria — fora do escopo do e-mail.
- **A perna de `vintage` da `asof` é degenerada.** `raw_series` tem **1 safra por série** (medido:
  0 de 62 com mais de um `vintage`), então a `asof` respeita a **divulgação** mas usa a série
  **revisada de hoje**: o efeito de look-ahead publicado é um **piso**, não o total — a revisão
  anual do PIB não está nele. Declarado em `relatorio_asof.json → limitacoes.vintage_unico`.
  Agrava: `selecionar_vintage` é hoje **inalcançável**, porque a guarda `validar_frequencia_nativa`
  de F-013 roda antes e um `raw_series` com 2 safras da mesma série levanta `FrequenciaNaoNativa`
  (P2-2 do QA-A). Capturar safras exige recoleta periódica — fase 2.
- **`catalogo_sha256` NÃO normaliza o fim de linha** (resíduo de **D-v b**). `versao_build` passou a
  normalizar; `catalogo_sha256` continua hasheando `read_bytes()` cru de `series_catalog_data.py`,
  porque é um hash **diagnóstico** de um arquivo só ("o catálogo mudou?") e há teste que o compara
  com o sha do arquivo em disco. Consequência: esse campo do `relatorio_build.json` ainda difere
  entre um checkout CRLF e um LF. Não afeta `fonte_versao` de nenhum Parquet. 2 linhas quando
  alguém for mexer.
- **`n_obs_regime_v1` é estatística da AMOSTRA INTEIRA, de propósito.** A leitura descritiva é
  "onde estamos no histórico" (metodologia §2, princípio 4), e o relatório publica
  `anti_look_ahead.n_e_estatistica_da_amostra_inteira = true`. Quem usar `regimes_v1.parquet` para
  **backtest** precisa recalcular `n` em janela **expanding** — e backtest está fora de escopo
  (Anti-SPEC §10.3.16). Travado por `test_remover_linhas_futuras_muda_n_mas_nao_rotulo`.
- **CA-079 (desempate por herança) só é exercitado em sintético:** **0 desempates** na rodada real,
  porque nenhum eixo é exatamente `0.0` nos 83 trimestres — o que se espera de um float derivado de
  razão. Se alguém mudar a regra de herança, **nenhum número publicado muda** e só o teste
  sintético pega.
- **A exclusão de vizinhança da V3 é simétrica (`T±1`, `T±2`) e CA-085 fala só dos anteriores.**
  Sem a simetria o vizinho rank 1 de quase todo trimestre seria `T+1` — autocorrelação trivial,
  exatamente o que CA-085 quer evitar. Registrado em
  `relatorio_regimes_v3.json → exclusao_de_vizinhanca.simetrica = true`; voltar à leitura literal é
  1 linha, e aí a lente descritiva muda muito.
- **`ldc.duckdb` continua sem view das 7 tabelas novas** (`alinhado_trimestral`, `macro_quarterly*`,
  `asset_returns_quarterly`, `regimes_v1*`, `regime_neighbors*`) — mesma dívida já listada acima,
  agora maior. `construir_duckdb` vive em `build_raw_series.py`; o lugar certo é o orquestrador de
  **F-029**.
- **`FEATURES_V3` tem 6 nomes e a rodada usa 5.** `termos_troca_yoy` é 100% nula (G-02 / F-037) e
  foi **cortada**, com `n_features = 5` declarado **na linha**. O de/para está em
  `CONTRACTS.md §5.3` e em `relatorio_regimes_v3.json → features`, para a comparação ser
  automática. Não há guarda que impeça alguém de reintroduzir a feature nula.

---

## 7. Definition of Done (DoD) — aplica a TODA feature

### Classe A
- [ ] CI N1 local verde (`ruff check . && ruff format --check . && pytest tests/unit`)
- [ ] `TODO.md` atualizado (item → Concluído com SHA)
- [ ] Teste cobre o CA (mesmo que unit simples)

### Classe B
- [ ] Tudo de A +
- [ ] Feature Contract preenchido
- [ ] Matriz de validação com status = passou em todos os CAs
- [ ] Evidências de dados: nº de linhas, intervalo de datas, % de nulos, 3 valores conferidos na fonte
- [ ] CI verde no PR
- [ ] `docs/contracts/CONTRACTS.md` atualizado se os schemas mudaram
- [ ] Fixture da fonte gravada em `tests/fixtures/`
- [ ] 1 linha em `docs/wiki/log.md`

### Classe C
- [ ] Tudo de B +
- [ ] CI N2 verde (integration + contract/pandera + build do canônico)
- [ ] **Reconstrução completa de `data/canonical/` a partir de zero, com sucesso**
- [ ] **Diff numérico vs. versão anterior do canônico, com cada divergência explicada**
- [ ] Anti-SPEC verificada explicitamente no QA
- [ ] Revisão numérica independente (quem calculou não confere)
- [ ] ADR se houve decisão arquitetural; `DECISIONS_LOG` se houve substituição de fonte

### Classe D
- [ ] Tudo de C +
- [ ] CI N3 verde (e2e + reprodutibilidade: rodar 2x → mesmo hash)
- [ ] Rollback documentado em `docs/plans/infra-ops.md`
- [ ] Revisão humana do número antes do envio ao Alexandre/Comitê
- [ ] Dataset congelado (versão + hash) e registrado em `docs/wiki/log.md`
- [ ] Credencial/API paga: uso autorizado e nenhum segredo no repo

---

*Este arquivo substitui `state/project-state.json`, `progress.jsonl`, `handoffs/*.json` e `bugs/*.md`.
O histórico granular vive no `git log`. Feature Contracts vivem aqui inline (ou em
`docs/plans/feature-contracts/F-NNN.md` quando extensos). Decisões operacionais que voltarão ao debate vão
para `docs/plans/DECISIONS_LOG.md`. Escopo e comportamento permanecem em ESCOPO-EMAIL/PRD/SPEC/Anti-SPEC e
só mudam com autorização humana.*
