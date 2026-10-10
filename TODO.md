# TODO — estrategia-macro-ldc-dados

> Estado vivo do projeto. Substitui `state/project-state.json`, `progress.jsonl` e `handoffs/`.
> Atualize ao iniciar, ao terminar uma feature e ao fim do dia.
>
> **v3.2 — Feedback Hardened + Project Wiki:** cada feature B/C/D traz o **Feature Contract inline**
> (DoR + escopo + arquivos + CAs + testes + matriz). Features A podem ter apenas a descrição mínima.

**Última revisão:** 2026-10-10
**Fase:** SPEC + Anti-SPEC + contratos (pandera/pydantic) prontos · **40 features mapeadas** ·
execução pode começar pelos extratores (classe B) sem esperar as 8 decisões bloqueantes
**Tipo:** ferramenta interna (dados / quant — não SaaS, não web, roda local)
**Foco atual:** §1 Em andamento = **F-009** (job diário ANBIMA — cada dia sem ele é série perdida)
e **F-001** (infra de extração, pré-requisito de todos os extratores). Em seguida, **F-002 → F-008**
(extratores de esforço baixo, caminho crítico de 2026-10-14)

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

### [ ] F-009 — Job diário de arquivamento ANBIMA (`Msec_txt.txt` + Curva Zero) — **URGENTE, HOJE**

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/anbima-arquivamento`
- **Cobre:** RF-010 · e-mail: **A5, A6**
- **CAs da SPEC:** CA-027, CA-028, CA-029
- **Por que é a primeira:** a janela é **rolante (~20 dias úteis)**. Cada dia sem o job é um dia de série
  proprietária **perdido para sempre** (riscos L6/R3). Não depende de nenhuma decisão humana.

**DoR específica** — [x] URLs e formatos confirmados (`ms{AAMMDD}.txt`, POST `CZ-down.asp`);
[x] `ausencia_e_caso_normal = True` previsto no `ExtractorConfig`; [x] sem bloqueio.

**Escopo incluído:** download idempotente diário, gravação versionada por data em
`data/raw/anbima-ms/` e `data/raw/anbima-ettj/`, parse mínimo de validação, log de dia ausente.
**Excluído:** uso dessas séries no canônico (a curva histórica vem do Tesouro — ADR-004);
agendador do sistema (o Edu dispara; não há cron no projeto).

**Arquivos:** `apps/pipeline/extract/anbima_diario.py`, `tests/unit/test_anbima_diario.py`,
`tests/fixtures/anbima/ms261008.txt`, `tests/fixtures/anbima/cz.csv`,
`docs/wiki/runbooks/arquivamento-diario-anbima.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| rodar 2x no mesmo dia não duplica nem sobrescreve diferente | integration | CA-027 |
| resposta de 0 bytes / 404 → sucesso com registro | unit negativo | CA-028 |
| parse do `ms*.txt` (`@`, `skiprows=2`, latin-1, 5 títulos) | contract | CA-029 |
| `saida=xls` do CZ é HTML → rejeitado por magic bytes | unit negativo | CA-029 |

**Anti-SPEC específica:** §10.1.3 (janela rolante nunca é backfill), base.

---

### [ ] F-001 — Infra de extração (cliente HTTP, parsing e guardas)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `feat/infra-extracao`
- **Cobre:** RF-049 (e é pré-requisito dos riscos R1, R2, R4, R10-R13 da pesquisa) · e-mail: base de A/B/C
- **CAs da SPEC:** CA-003, CA-022, CA-035, CA-045, CA-123, CA-124

**DoR específica** — [x] fontes e pegadinhas levantadas em `docs/research/fontes-de-dados.md`;
[x] `ExtractorConfig` já existe em `packages/shared/schemas/series_catalog.py`; [x] sem bloqueio humano.

**Escopo incluído:** cliente HTTP com **User-Agent de browser** em toda requisição, retry com backoff,
timeout; **validador de shape** (corpo é JSON array? tem chave `error`/`erro`? começa com `<`?);
**normalizador único de número pt-BR** (`"38.484,84"` → `38484.84`); leitor com **encoding explícito**
por fonte; checagem de **magic bytes** (`PK` = XLSX, `<` = HTML); helper de fatiamento de janela
(≤ 10 anos); gravação em `data/raw/<fonte>/` e `data/processed/`.
**Excluído:** cache condicional por ETag (→ F-030); qualquer extrator concreto.

**Arquivos:** `apps/pipeline/extract/http.py`, `.../parsing.py`, `.../io_layers.py`,
`tests/unit/test_http.py`, `tests/unit/test_parsing.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| HTTP 200 com corpo de erro → levanta e não grava | unit negativo | CA-003 |
| número pt-BR com ponto de milhar converte certo | unit | CA-035 |
| `.xls` que é XLSX é detectado por magic bytes | unit | CA-030 (pré) |
| leitor sem `encoding` explícito falha no lint do próprio teste | unit | CA-022 |
| requisição sem UA é bloqueada por asserção do cliente | unit | CA-045 |

**Anti-SPEC específica:** §10.1.5 (HTTP 200 ≠ sucesso), §10.4.26 (encoding), §10.4.23 (sem rede no CI).

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

### [ ] F-002 — Extrator ANBIMA S3: índices IMA (esforço baixo, maior valor/hora)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/anbima-ima`
- **Cobre:** RF-011 · e-mail: **B1, B2**
- **CAs da SPEC:** CA-030, CA-031, CA-032, CA-033

**DoR específica** — [x] SLUGs confirmados e hard-coded no catálogo (listagem do bucket é `AccessDenied`);
[x] amostras já baixadas em `data/raw/anbima-ima/`; [x] sem decisão humana pendente.

**Escopo incluído:** `IMAB`, `IMAB5`, `IMAB5MAIS`, `IRFM`, `IRFM1`, `IRFM1MAIS`, `IMAGERAL`, `IMAS`
(+ `IMAGERALEXC`); leitura via `io.BytesIO` com `engine="openpyxl"`; normalização do rótulo da coluna
`Índice`; output em `ProcessedSeriesSchema`.
**Excluído:** `IMAC` (descontinuado 2021) e `IHFA` (fora do e-mail); reconciliação com SGS 12461-12469
(fica em F-030 como teste de contrato opcional).

**Arquivos:** `apps/pipeline/extract/anbima_s3.py`, `tests/contract/test_anbima_s3.py`,
`tests/fixtures/anbima_s3/*.xlsx`, `docs/wiki/modules/anbima.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| magic bytes `PK` → lê com openpyxl | contract | CA-030 |
| **valor-canário IMA-B 16/09/2003 = 723,070317** | contract | CA-031 |
| rótulos `IMA-B` e `IMA - B` colapsam em 1 `asset_id` | unit | CA-032 |
| os 8 índices do e-mail têm `data_inicio <= 2006-01-02` | unit | CA-033 |

**Anti-SPEC específica:** §10.1.6 (não usar o SGS descontinuado como se vivo), base.

---

### [ ] F-003 — Extrator BCB SGS: IPCA, IBC-Br, Selic, CDI, PTAX

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/bcb-sgs`
- **Cobre:** RF-001, RF-003, RF-005, RF-006, RF-015 · e-mail: **A1, A2, A4, B3, C1**
- **CAs da SPEC:** CA-001..003, CA-006, CA-007, CA-011..016, CA-043, CA-044

**DoR específica** — [x] 36 séries SGS no catálogo com código, início e pegadinha;
[x] fatiamento ≤ 10 anos definido em F-001; [x] sem decisão humana pendente.

**Escopo incluído:** séries 433, 13522, 24364, 24363, 11, 1178, 432, 4390, 4189, 12, 4389, 1, 10813
(+ 22109, 22099 como espelho de PIB); fatiamento de séries diárias; truncamento da série 432 em `today`;
acumulação geométrica do CDI/Selic por trimestre.
**Excluído:** séries `a_confirmar` (21619, 4192, DBGG pré-2008) e `descartada` (13762, 24369);
Focus (→ F-010).

**Arquivos:** `apps/pipeline/extract/bcb_sgs.py`, `apps/pipeline/transform/acumulacao.py`,
`tests/contract/test_bcb_sgs.py`, `tests/unit/test_acumulacao.py`, `tests/fixtures/bcb_sgs/*.json`,
`docs/wiki/modules/sgs.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| série diária > 10 anos é fatiada, sem duplicata nem lacuna | integration | CA-011 |
| **valor-canário Selic over 03/01/2005 = 0.064826** | contract | CA-012 |
| **CDI 2006 acumulado = 15,0271%** (249 d.u.) | unit | CA-014 |
| esquecer o `/100` da série 12 faz o teste falhar | unit negativo | CA-016 |
| SGS 432 com data futura é truncada em `today` | unit | CA-013 |
| IPCA 433 bate com SIDRA 1737 v63 em ago e set/2026 | contract | CA-002 |
| **valor-canário PTAX 09/10/2026 = 4.9892** | contract | CA-043 |

**Anti-SPEC específica:** §10.1.4 (não preencher com `0`), §10.1.5, base.

---

### [ ] F-004 — Extrator IBGE SIDRA: IPCA número-índice e PIB trimestral

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/ibge-sidra`
- **Cobre:** RF-002, RF-004 · e-mail: **A1, A7**
- **CAs da SPEC:** CA-004, CA-005, CA-008, CA-009, CA-010

**DoR específica** — [x] tabelas/variáveis confirmadas (`t/1737` v63/v2265/v2266; `t/1621` v584
`c11255/90707`; `t/5932` v6564); [x] encoding UTF-8 declarado; [x] sem decisão humana pendente.

**Escopo incluído:** IPCA número-índice (deflator), IPCA mensal e 12m (reconciliação com SGS),
PIB índice de volume dessazonalizado e variação T/T−1; tratamento da **primeira linha como cabeçalho**.
**Excluído:** abertura setorial do PIB por `c11255` (fase 2); IPCA por grupos (L13, `a_confirmar`);
desemprego (L9).

**Arquivos:** `apps/pipeline/extract/ibge_sidra.py`, `tests/contract/test_ibge_sidra.py`,
`tests/fixtures/ibge_sidra/*.json`, `docs/wiki/modules/sidra.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| primeira linha é cabeçalho, não dado | unit | CA-004 |
| **valores-canário PIB 2006T1/T2/T3 = 131.74 / 132.14 / 134.36** | contract | CA-008 |
| SIDRA `t/1621` ≡ SGS 22109 trimestre a trimestre | contract | CA-009 |
| IPCA trimestral por razão do nº-índice ≡ encadeamento de 433 | unit | CA-005 |
| acento não corrompe com `encoding="utf-8"` explícito | unit | CA-004 |

**Anti-SPEC específica:** §10.4.26 (encoding), base.

---

### [ ] F-005 — Extrator Tesouro Direto (taxas e PUs de títulos públicos)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/tesouro-direto`
- **Cobre:** RF-008 · e-mail: **A5**
- **CAs da SPEC:** CA-020, CA-021, CA-022

**DoR específica** — [x] URL do recurso CKAN confirmada e arquivo já baixado (14,6 MB, 177.260 linhas);
[x] formato medido (`;`, decimal vírgula, latin-1, `dd/mm/aaaa`); [x] UA de browser obrigatório.

**Escopo incluído:** download do CSV único, parse tipado, split por tipo de título e vencimento,
gravação em `data/processed/tesouro/`.
**Excluído:** interpolação de vértices e inclinação (→ **F-016, classe C**); ANBIMA `ms*.txt` (→ F-009).

**Arquivos:** `apps/pipeline/extract/tesouro_direto.py`, `tests/contract/test_tesouro_direto.py`,
`tests/fixtures/tesouro/td_amostra.csv`, `docs/wiki/modules/tesouro.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| parse de 200 linhas: 8 tipos, nenhuma taxa `NaN` | contract | CA-020 |
| cobertura de 2006 >= 240 dias úteis e `min(data) <= 2005-01-03` | integration | CA-021 |
| encoding latin-1 explícito (acento em "Tesouro Prefixado") | unit | CA-022 |
| CKAN sem UA → erro tratado | unit negativo | CA-020 |

**Anti-SPEC específica:** §10.4.26, base.

---

### [ ] F-006 — Extrator API B3: índices amplos, setoriais e IFIX

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/b3-indices`
- **Cobre:** RF-012, RF-013 · e-mail: **B4, B5**
- **CAs da SPEC:** CA-034..039
- **Decisão provisória que carrega:** `[PROVISÓRIO D12, L1]` — best-effort, janelas próprias (ADR-005)

**DoR específica** — [x] endpoint `indexStatisticsProxy` re-testado na pesquisa; [x] códigos confirmados
(**`IEEX`**, não `IEE`); [x] data-base medida índice a índice; [ ] **D12/L1 em aberto** — o padrão
provisório (best-effort + janela própria) está em ADR-005 e **não bloqueia** a extração.

**Escopo incluído:** `IBOV`, `IDIV`, `SMLL`, `INDX`, `IMAT`, `IEEX`, `IFNC`, `UTIL`, `ICON`, `IMOB`,
`IFIX`; **unpivot** da matriz dia×mês; normalização de número pt-BR; `data_inicio` por série no catálogo.
**Excluído:** `IFIL` (não é segmento, é liquidez); COTAHIST (fase 2); FII por segmento (→ F-012);
confirmação de retorno total índice a índice (gap **G-01**, fica como pendência declarada).

**Arquivos:** `apps/pipeline/extract/b3_indices.py`, `tests/contract/test_b3_indices.py`,
`tests/fixtures/b3/*.json`, `docs/wiki/modules/b3.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| unpivot: **IBOV 01/02/2006 = 38.484,84**, 246 pontos em 2006 | contract | CA-034 |
| `"38.484,84"` nunca vira `38.48` | unit | CA-035 |
| `ICON`/`IMOB` em 2006/2007 trazem só o ponto-base | contract | CA-036 |
| célula vazia → omitida ou `NULL`, nunca `0` | unit negativo | CA-037 |
| `IFIX` 2010 só ponto-base; 2011 com 249 pontos | contract | CA-038 |

**Anti-SPEC específica:** §10.1.1 (sem backfill sintético de IFIX/ICON/IMOB), §10.1.4, §10.4.27 (não
scrapear o shell Angular), base.

---

### [ ] F-007 — Extrator internacional: Yahoo `^GSPC` + MSCI ACWI (NETR) em BRL

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/internacional`
- **Cobre:** RF-016 · e-mail: **C1**
- **CAs da SPEC:** CA-045, CA-046, CA-047

**DoR específica** — [x] endpoints confirmados; [x] PTAX disponível via F-003; [x] proibição do FRED
`SP500` registrada no catálogo (`status: descartada`); [ ] **D6 em aberto** — não bloqueia a extração
(só a formulação da recomendação, F-026).

**Escopo incluído:** `^GSPC` (com `period1`/`period2` em epoch), MSCI `892400` variante `NETR`
(+ `990100`, `984000` como alternativas), conversão a BRL pela PTAX do **mesmo dia útil**,
marcação de `is_total_return`.
**Excluído:** ouro (`GOLD_BRL` depende do gap **G-03** — sem fonte confirmada, retorna
`BLOQUEADO — FONTE INDISPONÍVEL`); ETFs `ACWI`/`URTH`/`IVVB11` (não cobrem 2006); FRED (→ F-011).

**Arquivos:** `apps/pipeline/extract/yahoo.py`, `apps/pipeline/extract/msci.py`,
`tests/contract/test_msci.py`, `tests/contract/test_yahoo.py`, `tests/fixtures/{yahoo,msci}/*.json`,
`docs/wiki/modules/internacional.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| sem UA → 429 (documentado); com UA → 200 | unit negativo | CA-045 |
| **valor-canário MSCI ACWI NETR 31/01/2006 = 121,3858** | contract | CA-046 |
| `range=max` mensal trunca → usar `period1/period2` | unit | CA-045 |
| conversão a BRL usa PTAX do mesmo dia útil | unit | CA-047 |
| price return x total return sem flag → falha | unit negativo | CA-047 |

**Anti-SPEC específica:** §10.2.12 (não misturar total e price return), §10.1.3 (janela rolante), base.

---

### [ ] F-008 — Calendário de dias úteis (ANBIMA)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/calendario`
- **Cobre:** RF-018 · e-mail: **A4, B3**
- **CAs da SPEC:** CA-051, CA-052

**DoR específica** — [x] arquivo confirmado (HTTP 200, 111.104 bytes, sem auth); [x] fallback `bizdays`
mapeado; [x] sem decisão humana pendente.

**Escopo incluído:** carga do `feriados_nacionais.xls`, API `ultimo_dia_util(ano, mes)` e
`dias_uteis(inicio, fim)`, usada por **toda** acumulação e alinhamento.
**Excluído:** calendário de outras praças; feriados estaduais.

**Arquivos:** `apps/pipeline/transform/calendario.py`, `tests/unit/test_calendario.py`,
`tests/fixtures/anbima/feriados.xls`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| 2006 tem **249 dias úteis** (confere com a contagem do CDI) | unit | CA-051 |
| fim de trimestre em feriado → dia útil anterior | unit | CA-052 |
| datas-armadilha (01/02 vs 02/01, Carnaval, 31/12 no fim de semana) | unit | CA-052 |

**Anti-SPEC específica:** base.

---

### [ ] F-010 — Extrator Focus (BCB Olinda / OData v4)

- **Risco:** B · **CI alvo:** N1 · **Branch:** `data/focus`
- **Cobre:** RF-007 · e-mail: **A3**
- **CAs da SPEC:** CA-017, CA-018, CA-019

**DoR específica** — [x] 5 EntitySets confirmados com data de início; [x] pegadinhas mapeadas
(`$top` trunca, `$apply`/`$count` ignorados, capitalização variável); [ ] **G-05** (convenção de
`baseCalculo`) e **G-04** (rótulo de `PIB Total`) a confirmar — resolvê-los é parte desta feature.

**Escopo incluído:** `ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`,
`ExpectativasMercadoTrimestrais`, `ExpectativasMercadoSelic`, `ExpectativasMercadoInflacao12Meses`;
filtro de `baseCalculo` único; normalização de nomes de campo; enumeração dos valores de `Indicador`
(resolve G-04).
**Excluído:** Top5; V1b vs. Focus (→ F-033); surpresa como feature de regime (fica em F-015/F-021).

**Arquivos:** `apps/pipeline/extract/bcb_focus.py`, `tests/contract/test_bcb_focus.py`,
`tests/fixtures/focus/*.json`, `docs/wiki/modules/sgs.md` (seção Focus).

| Teste | Tipo | Cobre CA |
|---|---|---|
| `baseCalculo` 0 e 1 na mesma data → 1 linha no output | contract | CA-017 |
| exatamente 20.000 linhas → assert de truncamento falha | unit negativo | CA-018 |
| nomes de campo normalizados nos 5 EntitySets | unit | CA-019 |
| `Indicador` enumerado e registrado (G-04) | integration | CA-019 |

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

### [ ] F-013 — Camada `raw_series` + `series_catalog` materializado — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/camada-raw-series`
- **Cobre:** RF-019, RF-020, RF-026, RF-047 · e-mail: todos
- **CAs da SPEC:** CA-053..058, CA-075..077, CA-120

**DoR específica** — [x] schemas prontos (`raw_series.py`, `series_catalog.py`, `series_catalog_data.py`
com 132 séries validadas); [x] ADR-006 (Parquet + DuckDB) proposto; [ ] ADR-006 **validado pelo Edu**
antes do merge (é a base da camada canônica).

**Escopo incluído:** carga de todos os `data/processed/` para `raw_series` (Parquet) na granularidade
nativa; materialização do `series_catalog`; portão pandera na entrada/saída de `data/canonical/`;
coluna de origem obrigatória; DuckDB derivado (opcional, regenerável).
**Excluído:** qualquer agregação trimestral (→ F-014/F-015).

**Arquivos:** `apps/pipeline/load/raw_series.py`, `apps/pipeline/load/catalog.py`,
`packages/shared/schemas/*` (acréscimos), `tests/contract/test_raw_series_schema.py`,
`tests/integration/test_camada_raw.py`, `docs/contracts/CONTRACTS.md`, `docs/wiki/modules/canonical.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| duas extrações coexistem como `vintage` distintos | integration | CA-056 |
| linha sem `source`/`series_id` → `SchemaError` | contract negativo | CA-057 |
| série trimestral não pode ser gravada fora da freq nativa | unit negativo | CA-058 |
| catálogo valida: 0 identificador vazio; `a_confirmar` ⇒ status | contract | CA-053, CA-054 |
| toda linha canônica resolve para URL do catálogo | integration | CA-055, CA-120 |
| lacuna sem substituto → `BLOQUEADO — FONTE INDISPONÍVEL` | unit negativo | CA-076 |

**Anti-SPEC específica:** §10.1.1, §10.1.2, §10.4.24 (sem coluna ad hoc), §10.4.28 (nativa, não trimestral).
**Extra de classe C:** diff numérico vs. versão anterior + reconstrução completa + **revisão numérica
independente** (quem escreveu não confere).

---

### [ ] F-014 — Alinhamento trimestral (fim de período, ffill <= 5 d.u.) — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/alinhamento-trimestral`
- **Cobre:** RF-023 · e-mail: base de A/B/C
- **CAs da SPEC:** CA-065..068
- **Depende de:** F-008 (calendário), F-013 (raw_series)

**DoR específica** — [x] convenção congelada em ADR-006 (último dia útil, ffill <= 5, encadeamento
geométrico); [x] calendário ANBIMA disponível; [ ] ADR-006 validado pelo Edu.

**Escopo incluído:** cálculo do `quarter_end` dos 83 trimestres; reindexação de séries diárias/mensais
para a grade; `ffill_dias_uteis`; `NULL` registrado acima de 5 d.u.; detecção de data duplicada/fora
de ordem.
**Excluído:** cálculo de retorno (→ F-017); regra anti-look-ahead (→ F-018).

**Arquivos:** `apps/pipeline/transform/alinhamento.py`, `tests/unit/test_alinhamento.py`,
`tests/integration/test_grade_trimestral.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| os 83 `quarter_end` caem em dia útil (inclui casos-armadilha) | unit | CA-065 |
| ativo sem negociação no fechamento → ffill <= 5 d.u. registrado | unit | CA-066 |
| lacuna > 5 d.u. → `NULL`, nunca preenchida | unit negativo | CA-067 |
| datas duplicadas com valor divergente → falha ruidosa | unit negativo | CA-068 |

**Anti-SPEC específica:** §10.1.1, §10.4.28, §10.2.7 (base do `asof`).
**Extra de classe C:** diff numérico + reconstrução + revisão independente.

---

### [ ] F-015 — `macro_quarterly` com 83 trimestres — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/macro-quarterly`
- **Cobre:** RF-021 · e-mail: **A1-A7**
- **CAs da SPEC:** CA-059, CA-060, CA-061 (+ CA-007, CA-044)
- **Depende de:** F-003, F-004, F-010, F-013, F-014, F-016

**DoR específica** — [x] schema `MacroQuarterlySchema` pronto; [x] todas as colunas com série de origem
mapeada no catálogo; [ ] colunas que dependem de gap aberto (`ipca_meta` → G-02; `embi_br_fim` → L8;
`termos_troca_yoy` → proxy IC-Br) entram **nulas e declaradas**, nunca estimadas.

**Escopo incluído:** montagem das ~40 colunas; `ibcbr_gap` (desvio da média móvel de 20 trimestres);
`ipca_12m_delta`; `selic_meta_delta`; `juro_real_exante`; `is_estimated` para `2026Q3`; `fonte_versao`.
**Excluído:** classificação de regime (→ F-019); materialização `asof` (→ F-018).

**Arquivos:** `apps/pipeline/transform/macro_quarterly.py`, `tests/contract/test_macro_quarterly.py`,
`tests/integration/test_build_macro.py`, `docs/wiki/modules/canonical.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| exatamente 83 linhas, `2006Q1`..`2026Q3`, sem repetir | contract | CA-059 |
| `2026Q3` com `is_estimated=True`, demais `False` | unit | CA-060 |
| coluna sem cobertura → `NULL`, nunca interpolada | unit negativo | CA-061 |
| `ibcbr_gap` existe nos 83 trimestres ou marca `is_estimated` | unit | CA-007 |

**Anti-SPEC específica:** §10.1.1, §10.4.24.
**Extra de classe C:** diff numérico + reconstrução + revisão independente.

---

### [ ] F-016 — Curva: vértices fixos interpolados + inclinação — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/curva-inclinacao`
- **Cobre:** RF-009 · e-mail: **A6**
- **CAs da SPEC:** CA-023..026
- **Decisão provisória que carrega:** `[PROVISÓRIO L4]` — ADR-004 (Tesouro Direto em vez de ETTJ ANBIMA).
  **Item de DoR:** se o Edu optar por contratar o ANBIMA Feed, esta feature vira **classe D**
  (credencial/API paga) e a implementação da fonte muda.
- **Depende de:** F-005

**DoR específica** — [x] método definido (A5.4 da pesquisa); [x] limitação L5 (sem vértice nominal de
10 anos antes de ~2010) registrada; [ ] **L4 em aberto** — ADR-004 em Proposta.

**Escopo incluído:** interpolação para 1, 3 e 5 anos (real e nominal) por data; flag
`vertice_extrapolado`; `NULL` quando o prazo-alvo não existe; `inclinacao_real_5a_1a` (principal),
`inclinacao_nominal_5a_1a`, `breakeven_5a` (por razão); agregação para o último dia útil do trimestre.
**Excluído:** curva Svensson oficial da ANBIMA (paga); DI futuro via `pyield` (fase 2 — exige Python 3.12).

**Arquivos:** `apps/pipeline/transform/curva.py`, `tests/unit/test_curva.py`,
`tests/contract/test_curva_vertices.py`, `docs/wiki/modules/tesouro.md`.

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

### [ ] F-017 — `asset_returns_quarterly`: retornos, excesso sobre CDI e real — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/asset-returns`
- **Cobre:** RF-022, RF-024, RF-026 · e-mail: **B1-B5, C1**
- **CAs da SPEC:** CA-062..064, CA-069..071
- **Depende de:** F-002, F-003, F-006, F-007, F-012, F-013, F-014

**DoR específica** — [x] schema pronto com 32 `asset_id`; [x] CDI trimestral validado (F-003);
[x] convenção de razão congelada em ADR-006; [ ] `is_total_return` dos setoriais da B3 = **G-01**,
entra `None` e declarado.

**Escopo incluído:** `ret_tri` por razão de preços no último DU; `ret_excesso_cdi` e `ret_real` **por
razão**; `vol_intra_tri` e `dd_intra_tri` do diário; `n_dias_uteis`; `ffill_dias_uteis`;
`data_inicio_serie`; painel **desbalanceado** (sem linha antes do início da série).
**Excluído:** métricas por regime (→ F-022); hedge cambial detalhado (D7 → fase 2 parcial em F-026).

**Arquivos:** `apps/pipeline/transform/retornos.py`, `tests/unit/test_retornos.py`,
`tests/contract/test_asset_returns.py`, `tests/integration/test_build_retornos.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| >= 18 `asset_id` distintos, todos no catálogo | contract | CA-062 |
| nenhuma linha antes de `data_inicio_serie` (IFIX, ICON, IMOB) | contract negativo | CA-063 |
| **excesso por razão: r=0,10 e cdi=0,0325 → 0,06538**, não 0,0675 | unit | CA-069 |
| subtração no lugar da razão **faz o teste falhar** | unit negativo | CA-069 |
| acumulação intra-trimestre é geométrica, não soma | unit | CA-070 |
| IPCA aplicado uma única vez (teste de dupla deflação) | unit negativo | CA-071 |
| price x total return sem flag → falha | unit negativo | CA-064 |

**Anti-SPEC específica:** §10.2.13 (razão), §10.2.12 (TR vs. PR), §10.1.1, §10.2.11 (Sharpe não é
implementável).
**Extra de classe C:** diff numérico + reconstrução + revisão independente.

---

### [ ] F-018 — Regra anti-look-ahead + materializações `asof` / `revised` — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/anti-look-ahead`
- **Cobre:** RF-025 · e-mail: base metodológica
- **CAs da SPEC:** CA-072, CA-073, CA-074
- **Depende de:** F-015

**DoR específica** — [x] `lag_divulgacao_dias` no catálogo para todas as séries; [x] regra definida
(PIB/IBC-Br de T−1; IPCA do penúltimo mês de T; Focus/Selic/curva/câmbio livres);
[x] colunas `lag_adjusted` e `trocou_vs_revised` no schema.

**Escopo incluído:** materialização `macro_quarterly_asof` (default para decisão) e
`macro_quarterly_revised`; cálculo e **publicação** do % de trimestres que trocam de regime; aviso
explícito se > 25%.
**Excluído:** relatório completo de divergência de classificação (→ F-034, fase 2).

**Arquivos:** `apps/pipeline/transform/asof.py`, `tests/unit/test_asof.py`,
`tests/integration/test_divergencia_lookahead.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| nenhuma coluna de `asof` usa dado divulgado após o fim de T | integration | CA-072 |
| % de troca de regime é calculado e exposto | integration | CA-073 |
| % > 25% → texto afirma que o modelo não é operacional | unit | CA-074 |
| tabela nunca mistura `asof` e `revised` | contract negativo | CA-072 |

**Anti-SPEC específica:** §10.2.7 (look-ahead sem flag é proibido).
**Extra de classe C:** diff numérico + reconstrução + revisão independente.

---

### [ ] F-019 — Regimes V1 (quadrantes crescimento × inflação) — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/regimes-v1`
- **Cobre:** RF-027, RF-030, RF-031 · e-mail: **A1, A2** + objetivo
- **CAs da SPEC:** CA-078..081, CA-088, CA-090, CA-091
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

**Arquivos:** `apps/pipeline/analysis/regimes_v1.py`, `tests/unit/test_regimes_v1.py`,
`tests/contract/test_regimes_schema.py`, `docs/wiki/modules/regimes.md`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| 83 trimestres rotulados, 4 quadrantes povoados, sem `NULL` | contract | CA-078, CA-080 |
| `g_T = 0` herda o sinal do trimestre anterior | unit | CA-079 |
| rodar 2x dá classificação idêntica (função pura) | unit | CA-081 |
| `n` por quadrante entre 10 e 35, senão alerta | unit | CA-080 |
| ADR-001 em Proposta ⇒ `especificacao_congelada=False` | unit | CA-090 |
| ajuste posterior nasce como `V1.1`, sem sobrescrever | unit | CA-091 |

**Anti-SPEC específica:** §10.2.9 (não ajustar a especificação depois de ver os retornos), §10.2.10
(descritivo, não preditivo).
**Extra de classe C:** diff numérico + reconstrução + revisão independente.

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

### [ ] F-021 — Regimes V3 (vizinhos mais próximos) + retorno em T+1 — **classe C**

- **Risco:** **C** · **CI alvo:** N2 · **Branch:** `feat/regimes-v3`
- **Cobre:** RF-029, RF-030, RF-036 · e-mail: objetivo literal ("momentos semelhantes")
- **CAs da SPEC:** CA-084..087, CA-089, CA-101, CA-102
- **Decisão provisória que carrega:** `[PROVISÓRIO D1]` — ADR-001 (V3 é o diferencial)
- **Depende de:** F-015, F-016 (curva), F-017

**DoR específica** — [x] 6 features definidas (`FEATURES_V3` no schema); [x] k=8 + sensibilidade
(5, 12); [x] plano B se a curva não ficar pronta (5 features, declarado);
[ ] `scipy`/`scikit-learn` para Ledoit-Wolf: **confirmar se já há dependência** — se precisar
adicionar, exige **ADR** (`AGENTS.md §12`).

**Escopo incluído:** z-score na amostra completa; Mahalanobis com shrinkage Ledoit-Wolf; Euclidiana em
paralelo; exclusão dos 2 trimestres anteriores; desempate pelo mais recente; variante `V3-pos2016`;
saída `regime_neighbors` + retorno de cada ativo nos trimestres **seguintes** aos vizinhos.
**Excluído:** clustering/HMM (→ F-039); otimização de carteira (fora de escopo, D11).

**Arquivos:** `apps/pipeline/analysis/regimes_v3.py`, `tests/unit/test_regimes_v3.py`,
`tests/contract/test_regime_neighbors.py`.

| Teste | Tipo | Cobre CA |
|---|---|---|
| covariância amostral crua (sem shrinkage) → teste falha | unit negativo | CA-084 |
| os 2 trimestres anteriores não aparecem; empate pelo recente | unit | CA-085 |
| curva ausente → roda com 5 features e **declara** | unit | CA-086 |
| k=5, 8 e 12 produzidos; divergência reportada | integration | CA-087 |
| PK de `regime_neighbors` e `metrica` no enum | contract | CA-089 |
| retorno medido em **T+1** dos vizinhos, não nos vizinhos | unit | CA-102 |

**Anti-SPEC específica:** §10.2.9 (não escolher k pelo resultado), §10.2.10, §10.4.25 (dependência nova
exige ADR).
**Extra de classe C:** diff numérico + revisão independente.

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

---

## 4. Bloqueios

> **8 decisões de Edu/Alexandre bloqueiam o início da implementação.** Origem: `docs/product/PRD.md §13.2`
> (PRD gerado em modo autônomo em 2026-10-10 — nenhuma dessas respostas veio de humano). Enquanto não
> respondidas, as features de regime e os extratores do caminho crítico não têm Definition of Ready completa.
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
