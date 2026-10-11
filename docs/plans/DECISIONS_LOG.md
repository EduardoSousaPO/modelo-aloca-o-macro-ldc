# DECISIONS_LOG — estrategia-macro-ldc-dados

> **Memória operacional leve.** Registra decisões menores que provavelmente voltarão ao debate e, se não
> forem documentadas, custam tempo ou geram retrabalho. Complementa os ADRs — **não substitui**.
>
> **Neste projeto o uso dominante é um só:** registrar **substituição de fonte de dados**. O e-mail do
> Alexandre autorizou ajustar a fonte quando o dado pedido não for localizável, mas a substituição
> **não pode ser silenciosa** (`CLAUDE.md §5`, `AGENTS.md §17`, Anti-SPEC §10 — "não substituir fonte em
> silêncio"). Cada linha carrega os 4 campos obrigatórios: **fonte pedida · fonte usada · por quê ·
> impacto na comparabilidade** — mais a referência (ADR / lacuna da pesquisa / feature).
>
> **Criado por:** F-032 (classe A) em 2026-10-10 · **Cobre:** RF-052, RF-045 (parcial) · **CA:** CA-128

> ⚠️ **TODAS as 12 linhas da §1 estão marcadas `PROVISÓRIA — aguardando aval de Edu/Alexandre`** —
> e o mesmo vale para as 8 decisões de convenção da **§2.1** (D-a..D-h, consolidação da Onda 1).
> Nenhuma foi confirmada por humano: são a recomendação da pesquisa (`docs/research/`) adotada como
> padrão para destravar a construção. Aval = 1 linha de "aceito" aqui e, nas que têm ADR, mudança do
> status de **Proposta** para **Aceito**. Até lá, **nenhum número derivado destas trocas é publicável**
> fora do fluxo classe D, e RF-045 (comunicação escrita ao Alexandre) continua aberto.

---

## 1. Substituições de fonte (todas PROVISÓRIAS)

| # | Fonte pedida no e-mail | Fonte usada | Por quê | Impacto na comparabilidade | Status | Ref. |
|---|---|---|---|---|---|---|
| **S-01** | **ETTJ ANBIMA** (item A6: "DataFit / ANBIMA Feed" — curva Svensson histórica) | **Tesouro Direto** (`precotaxatesourodireto.csv`, 31/12/2004→hoje), vértices interpolados | histórico da ETTJ só existe no **ANBIMA Feed, pago** (≈R$ 686–8.238/mês) e a Curva Zero pública é **janela rolante de ~20 d.u.** (`Dt_Ref=02/01/2006` devolve 0 bytes) | atende ao objetivo (inclinação curto × longo com 20 anos), mas **não é a curva Svensson oficial da ANBIMA**: é taxa de título do varejo, interpolada. Números não batem na casa decimal com a ETTJ oficial | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | **ADR-004** (Proposta) · L4 · F-005, F-016 |
| **S-02** | **Swap DI × pré do SGS** (séries **7801-7806**; mensais 7816-7827) — a rota literal sugerida no e-mail | **Tesouro Direto** (mesma de S-01); DI futuro via `pyield` como checagem | as séries **morreram**: diárias param em **30/09/2019**, mensais em **01/08/2019** — não há como cobrir 2019→2026 | **nenhum**, se S-01 for aceita: a variável de regime passa a vir de uma fonte única e contínua, em vez de emendar duas | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | **ADR-004** (Proposta) · L7 · F-016 |
| **S-03** | **Inclinação nominal** ("diferença entre DI de curto e longo prazo") | **Inclinação real** (NTN-B curta × NTN-B longa) como variável principal; nominal só até ~5 anos | a **ponta longa nominal não existia** antes de ~2010 (em 2006 a LTN mais longa vencia em 2009) | **mudança conceitual, não só de fonte**: a variável de regime passa a ser **real**, não nominal. Tem de ser declarada em toda tabela/figura que a use | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | **ADR-004** (Proposta) · L5 · F-016 |
| **S-04** | **Índices IMA via SGS** (12461-12469) — rota óbvia para quem já usa o SGS | **Bucket S3 público da ANBIMA** (`IMAB`, `IMAB5`, `IMAB5MAIS`, `IRFM`, `IRFM1`, `IRFM1MAIS`, `IMAGERAL`, `IMAS`) | as séries de IMA no SGS foram **descontinuadas em 22/05/2023**; o S3 é grátis, sem cadastro, diário e começa em **01/02/2000 / 16/09/2003** | **melhora**: série mais longa e sem emenda. Único cuidado é formato (`.xls` que é XLSX) e rótulo instável (`IMA-B` vs `IMA - B`) | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | L-pesquisa §B6 · F-002 |
| **S-05** | **"ANBIMA DataFit"** (nome citado no item A6 do e-mail) | **ANBIMA Data** (portal grátis) + **S3 público** + **ANBIMA Feed** (pago, não contratado) | **o produto "DataFit" não existe.** O que existe é ANBIMA Data (grátis, com API interna protegida por reCAPTCHA de uso único → HTTP 418 no reuso) e ANBIMA Feed (pago) | **nenhum** — o S3 resolve os índices e o Tesouro resolve a curva. É correção de nomenclatura, mas precisa ir ao Alexandre para não virar expectativa frustrada | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | L12 · F-002, F-009 |
| **S-06** | **IFIX com 20 anos** (item B5) | **IFIX com janela própria 2011-2026**; IMOB (2008+) como proxy imperfeito antes disso. **Sem IFIX sintético** | a data-base do IFIX é **30/12/2010 = 1.000,00** — não existe IFIX antes de 2011, em nenhuma fonte | **alto**: FII **não entra** no painel balanceado de 20 anos e cobre ~2,5 ciclos macro. Toda célula envolvendo FII precisa de `n` e `data_inicio` visíveis | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | **ADR-005** (Proposta) · L1 · F-006, F-017, F-022, F-028 |
| **S-07** | **ICON e IMOB com 20 anos** (item B4) | **Janela própria por índice**: ICON de **2007**, IMOB de **2008** — painel desbalanceado, sem forçar janela comum | data-base medida na própria API da B3: ICON 28/12/2006 = 1.000,00; IMOB 28/12/2007 = 1.000,00 | baixo-médio: esses 2 setoriais entram com 1-2 anos menos que os demais. Exige **nota de rodapé** e `n` por célula; nenhuma comparação direta entre setores pode ignorar a janela | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | **ADR-005** (Proposta) · L3 · F-006, F-022 |
| **S-08** | **FII por segmento** (Tijolo, Papel, Logística, Shoppings, Lajes — item B5) | **Índices Teva** (GCS público): `3.2.2`, `3.2.1`, `3.3.1`, `3.3.3`, `3.3.2`, desde **02/01/2019** | a **B3 não tem** índice setorial de FII (o `IFIL` é filtro de liquidez, não segmento). A Teva é grátis e programática — mas é **provedor privado sem licença comercial explícita** | **o mais severo da lista**: ~2 ciclos macro, **insuficiente para inferência estatística**. Uso restrito a **dispersão setorial qualitativa**, nunca como linha de heatmap com conclusão. Risco de licença (R20) é decisão do Edu | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | **ADR-005** (Proposta) · L2 · F-012 |
| **S-09** | **FRED** (Treasury 10y/2y, VIX, DXY, Fed Funds — bloco C) | **Yahoo** (`^TNX`, `^FVX`, `^VIX`, `DX-Y.NYB`, `^GSPC`) + **MSCI** (`892400`/`984000` NETR) + **BCB SGS 1/10813 (PTAX)** | `fred.stlouisfed.org` está **bloqueado nesta máquina** na camada de aplicação: TCP+TLS completam em 0,04 s, mas a resposta HTTP dá ReadTimeout e, no retry, `ConnectionReset(10054)` — **3/3 tentativas** | médio e desigual por série: `DGS10`→`^TNX` é quase equivalente; **`T10Y2Y` passa a ser proxy 10y−5y** (`^TNX`−`^FVX`), o que muda o nível do spread; **`DFF`/`FEDFUNDS` não tem substituto gratuito equivalente** → fica como lacuna declarada ou exige outra rede | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | R5/G-06 · `skills-manifest §3` · F-011, F-007 |
| **S-10** | **S&P 500 do FRED** (`SP500`) | **Yahoo `^GSPC`** (desde 1927) ou **MSCI USA `984000`** | a série `SP500` do FRED tem **janela rolante de 10 anos** — não cobre 2006 nem com conectividade | **nenhum** — não é lacuna real, é escolha de rota. `^GSPC` é price return; MSCI NETR é total return: declarar qual foi usada em cada tabela (`is_total_return`) | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | L11 · F-007 |
| **S-11** | **Risco-país / CDS Brasil 5y** (contexto do bloco C) | **EMBI+ (Ipeadata `JPM366_EMBI366`) até 30/07/2024**, depois proxy (cupom cambial DDI/FRC − UST, ou splice com ICE BofA LatAm) | o **EMBI+ foi descontinuado em 30/07/2024**; não existe fonte gratuita, programática e contínua de CDS/risco-país com 20 anos | **série emendada → quebra metodológica em 2024.** Usar com cautela e **nunca** em regressão sem dummy de quebra. Fora do pacote mínimo | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | L8 · F-036 (pacote estendido) |
| **S-12** | **Dívida bruta do governo geral** (SGS 13762) | **DLSP — dívida líquida do setor público** (SGS 4513) | a série de dívida **bruta começa em 2008**; a líquida cobre 2006 | **troca de conceito fiscal** (líquida ≠ bruta): nível e dinâmica diferem, especialmente 2015-2017. Declarar no rótulo da variável; não comparar com números de dívida bruta publicados | **PROVISÓRIA** — aguardando aval de Edu/Alexandre | L10 · variável macro auxiliar |

**12 linhas · 12 provisórias · 0 confirmadas por humano.** As que têm ADR (**S-01, S-02, S-03, S-06,
S-07, S-08**) dependem de **L4, L1, L2, L3** nos bloqueios do `TODO.md §4`; as demais (**S-04, S-05,
S-09, S-10, S-11, S-12**) são operacionais e podem ser aceitas por e-mail, sem ADR.

---

## 2. Decisões operacionais (não são troca de fonte)

- [2026-10-10] [deps] **`xlrd` dispensado; leitor escolhido por magic bytes** — motivo: o `.xls` do S3 da
  ANBIMA é XLSX (`PK\x03\x04`) e o `.xls` da Curva Zero é HTML `<table>`; nenhum arquivo é XLS/BIFF real
  — impacto: `pandas.read_excel(engine="openpyxl")` para o primeiro e `read_html`+`lxml` para o segundo,
  sempre **sniffando os 4 primeiros bytes** antes de escolher; se aparecer XLS legado, volta ao debate —
  ref: `skills-manifest §4` / F-001, F-002
- [2026-10-10] [deps] **`seaborn` não entra** — motivo: o heatmap de RF-033 é `matplotlib` puro com a
  paleta da skill `dataviz`; nenhum doc exige seaborn — impacto: uma dep menos no `uv sync` — ref: F-023
- [2026-10-10] [deps] **`openpyxl`, `lxml` e `matplotlib` adicionados ao `pyproject`** — motivo: eram
  caminho crítico (ANBIMA IMA, Curva Zero, heatmap) e só funcionavam por existirem no Python global —
  impacto: `uv sync --extra dev` passa a entregar ambiente completo — ref: `skills-manifest §4`
- [2026-10-10] [deps] **`yfinance>=0.2.50` adicionado ao `pyproject` — DECIDIDO** — motivo: **FRED
  bloqueado nesta máquina, confirmado 3/3** nos testes de conectividade, e o Yahoo é o plano B do
  contexto externo (`^TNX`, `^FVX`, `^VIX`, `DX-Y.NYB`, `^GSPC`) — impacto: a lib é frágil (rate limit
  disfarçado, `auto_adjust` mudou de default), então F-007/F-011 mantêm a chamada direta ao `chart/v8`
  com UA de browser como fallback e passam `auto_adjust` explicitamente — ref: `skills-manifest §4` /
  F-007, F-011
- [2026-10-10] [repo] **Repositório remoto no GitHub conectado** — motivo: o Edu criou
  `https://github.com/EduardoSousaPO/modelo-aloca-o-macro-ldc.git` e o orquestrador fez o push da
  **`main`** (até então o repo era só local, 7+ commits) — impacto: histórico passa a ter backup fora da
  máquina e o CI do GitHub Actions (N1) passa a rodar de fato; **nada muda nas regras de dado**: `data/`
  segue fora do git e nenhum `.parquet`/`.duckdb`/`.env` pode ser commitado (`CLAUDE.md §6`, RNF-009) —
  ref: `README.md`, `.github/workflows/ci.yml`
- [2026-10-10] [arquitetura] **Supabase descartado na v1 — DECIDIDO pelo Edu** — motivo: o Edu perguntou
  se o projeto precisa de banco; avaliação do orquestrador foi **não na v1** — pipeline local, usuário
  único, sem web/auth/deploy (PRD §4.4), volume pequeno (~130 séries, 83 trimestres) e ADR-006 já define
  Parquet por camada + DuckDB derivado; Supabase adicionaria **credencial** (classe D por `AGENTS.md §2`,
  contra RNF-006), dependência de rede, custo, migration e um risco novo (dado errado persistido
  remotamente) sem benefício para 14/10 — impacto: persistência segue integralmente o ADR-006; o
  compartilhamento com o Alexandre continua pelo **pacote de entrega** (XLSX/Parquet/figuras, F-031,
  classe D). Reavaliar na fase 2 **só** com dashboard multiusuário, atualização automática consumida por
  terceiros ou histórico de vintages consultável por terceiros — e então como classe D, com ADR próprio,
  **nunca** substituindo o Parquet como fonte reconstruível — ref: **ADR-007** (Aceita), ADR-006 (alt. D)
- [2026-10-10] [processo] **Edu autorizou seguir as ondas com os padrões provisórios** — motivo: pedido
  explícito de abrir a Onda 0 e seguir as demais em loop com subagentes Opus, em vez de esperar as 8
  decisões (D1, D3, D5, D6, D12, L1, L2, L4) — impacto: **desenvolvimento liberado** sobre as
  recomendações já registradas neste log e no ADR-006; as 8 decisões **seguem abertas** e podem ser
  viradas pelo Edu a qualquer momento (quem virar paga a reconstrução, classe C); o gate de
  **publicação** permanece **duro**: nenhum número vai ao Comitê/Alexandre sem **ADR-001 aceito**
  (`AGENTS.md §14` passo 2, CA-090) — em `Proposta` o veredito é `BLOQUEADO — ESPECIFICAÇÃO NÃO
  CONGELADA` — ref: `TODO.md §4`, `docs/plans/PLAN.md §6`, `AGENTS.md §14`
- [2026-10-10] [parsing] **Dois normalizadores de número, não um** — motivo: o Feature Contract de F-001
  pedia "normalizador único de número pt-BR", mas as fontes se dividem em dois mundos incompatíveis:
  vírgula decimal com ponto de milhar (B3 `"38.484,84"`, ANBIMA, Tesouro, Curva Zero) e ponto decimal
  (JSON do SGS `"0.82"`, Yahoo, MSCI). Um normalizador "esperto" teria de adivinhar se `"6.930"` é
  `6,93` ou `6930` — e `6.930` é justamente um vértice da Curva Zero em dias — impacto:
  `apps.pipeline.common.parsing` exporta `para_float_ptbr` **e** `para_float_ponto_decimal`, cada um
  **levantando** na convenção do outro em vez de errar a escala por 1000x em silêncio; cada extrator
  declara qual usa — ref: F-001, `docs/wiki/context/F-001.md §3`, CA-035
- [2026-10-10] [repo] **`uv.lock` versionado no git** — motivo: reprodutibilidade do ambiente (RNF de
  reprodutibilidade); o pacote do Comitê tem de poder ser refeito com as **mesmas** versões de pandas,
  pandera e openpyxl, e `uv sync` sem lock resolve de novo a cada máquina e a cada dia — impacto:
  `uv.lock` entra no repo e **não** vai para o `.gitignore`; bump de dependência vira diff revisável, e
  divergência entre lock e `pyproject` é falha de CI em vez de surpresa de execução — ref:
  `pyproject.toml`, `.gitignore`, RNF-009, CA-121
- [2026-10-10] [fontes] **Playwright é diagnóstico, nunca fonte de pipeline** — motivo: as páginas da B3 e
  do ANBIMA Data são shells Angular (~2 KB, só `<app-root>`) — impacto: scraping de HTML não funciona; o
  caminho é sempre a API. Virar fonte → pausa + ADR — ref: `skills-manifest §1` cap. 15, RO-7

---

### 2.1 Consolidação da Onda 1 — convenções da camada processada (2026-10-11)

> As 8 linhas abaixo são decisões **do orquestrador** tomadas ao fechar a Onda 1, para que os 7
> extratores (F-002..F-008) não entregassem três convenções diferentes à camada canônica. Todas
> estão **provisórias — aval de Edu pendente**. Nenhuma toca SPEC, PRD, Anti-SPEC ou o e-mail de
> escopo; onde o dado real contradiz a SPEC (D-e), a decisão foi **registrar**, não editar.

- [2026-10-11] [convenção] **D-a · `date` de série mensal e trimestral = fim de período civil —
  PROVISÓRIA, aval de Edu pendente** — motivo: `CLAUDE.md §3` já diz "trimestre = fim de período",
  mas F-003 (SGS) gravava o **1º dia** do período porque é o que a API devolve (`01/09/2026` para o
  IPCA de setembro, `01/04/2026` para o PIB do 2T) e F-004 (SIDRA) gravava o **último**. As duas
  séries de IPCA são idênticas valor a valor e **nenhuma linha casava por `date`** — a
  reconciliação de F-004 teve de ser feita por `Period`, o que é uma muleta que a camada canônica
  não pode herdar — impacto: `apps/pipeline/extract/bcb_sgs.py` ganhou `fim_do_periodo(quando,
  freq=)` e converte **antes** de qualquer guarda; os valores-canário mensais/trimestrais mudaram de
  data (não de valor): 433 e 13522 → `2026-09-30`, 24364/24363 → `2006-01-31`, 22109/22099 →
  `2006-03-31`. Fim de período **civil**, não dia útil (ajuste para dia útil é alinhamento, F-014).
  **Efeito colateral medido e aceito:** séries SGS 4390 e 4189 (Selic acumulada no mês / taxa
  anualizada) publicam o **mês corrente parcial** — 01/10/2026 = 0,36% contra ~1,08% de um mês
  cheio. Com fim de período, essa linha vira `2026-10-31`, cai no truncamento de data futura
  (`truncar_em`, CA-013) e é **descartada com log e contagem** (`fut=1`), em vez de entrar na série
  como se fosse o valor do mês. É o comportamento certo: mês incompleto não é observação mensal —
  ref: `CLAUDE.md §3`, F-003, F-004, `tests/unit/test_contract_sgs_sidra.py`
- [2026-10-11] [convenção] **D-b · `vintage` = a data (ISO, sem hora) do `collected_at` registrado
  no manifesto do bruto — PROVISÓRIA, aval de Edu pendente** — motivo: a onda produziu **três**
  convenções: "última data do histórico" (F-002, F-004, F-007), `collected_at` com hora
  (F-003, F-005) e **nulo** (F-006). Duas séries no mesmo canônico com convenções diferentes tornam
  a PK `(series_id, date, vintage)` incomparável entre fontes (RF-025 / CA-122). "Última data do
  histórico" tem um furo pior: quando o IBGE revisa o PIB de trimestres passados **sem acrescentar
  trimestre novo** — e o IBC-Br faz isso todo mês —, a última data não muda, as duas safras colidem
  na PK e a revisão **sobrescreve** o retrato anterior, que é exatamente o que o `vintage` existe
  para evitar — impacto: `vintage = Timestamp(collected_at).normalize()` nos 7 extratores, e
  `collected_at` passa a sair do **manifesto** (`obtido_em_arquivado`, novo em
  `apps/pipeline/common/io_layers.py`), nunca do relógio da rodada. Consequência prática: `--offline`
  é idempotente de verdade — 2 rodadas dos 8 extratores produziram **hash idêntico nos 53 Parquets**.
  A série derivada em BRL herda `collected_at`/`vintage` da série em USD. `data_ref` do **nome** do
  arquivo bruto continua sendo a última data do histórico (é o retrato, não a safra) — ref: F-002
  §2.3, F-004 §6, F-007 §5, `CONTRACTS.md §1`
- [2026-10-11] [bug] **D-c · o glob do `--offline` filtra `*.meta.json` em todo extrator —
  PROVISÓRIA (é correção, não escolha)** — motivo: F-004 mediu que
  `x__2026-06-30.json.meta.json` **casa** com `glob("x__*.json")` e, em ordenação reversa, vem
  **antes** do dado: `--offline` parsearia o manifesto. Vale para toda fonte cuja camada bruta é
  `.json` — impacto: filtro de `SUFIXO_MANIFESTO` auditado nos 8 extratores. F-004 e F-007 já
  tinham; F-002, F-005 e F-008 ganharam por disciplina (extensão `.xlsx`/`.csv`/`.html` não casa
  hoje, mas a regra não pode ter exceção); F-003 e F-006 não usam glob (reencontram o bruto pelo
  nome determinístico) e ganharam **teste de regressão** afirmando isso. Há teste em cada um — ref:
  F-004 §4.6
- [2026-10-11] [catálogo] **D-d · catálogo de 132 → 134 séries (`ACWI_BRL`, `SP500_BRL`,
  `fonte=DERIVADO`) — ACEITO pelo orquestrador, PROVISÓRIO para o Edu** — motivo: F-007 precisava
  registrar `is_total_return` das séries em BRL, e `ProcessedSeriesSchema` tem 8 colunas, nenhuma
  delas essa flag: o lugar da flag de CA-047 é o **catálogo** — impacto: duas entradas novas em
  `packages/shared/schemas/series_catalog_data.py`, `N_SERIES_ESPERADAS = 134` em
  `tests/unit/test_schemas_smoke.py`, e o número atualizado em `docs/contracts/CONTRACTS.md §2.1`,
  `README.md` e `docs/plans/AUDITORIA-HARNESS.md` (nota, sem reescrever o laudo). `SP500_BRL` é
  **price return** declarado (`is_total_return=False`); o comparável de total return é `ACWI_BRL`
  (NETR) — ref: F-007 §2.1, CA-047
- [2026-10-11] [spec] **D-e · CA-004 (monotonia >= 99%) e CA-005 (tolerância 1e-6) não fecham no
  dado real — AGUARDA EDU; SPEC NÃO EDITADA** — motivo: medido por F-004 na série real
  `SIDRA_1737_V2266`: monotonia de **0,9626** no histórico completo (21 meses de **deflação de
  verdade**, 199708→202608) e **0,9435** de 2006 em diante; e **3,52e-04 pp** de divergência máxima
  entre a razão do número-índice e o encadeamento de `v/63` em 83 trimestres, contra um limite
  **analítico** de 3,97e-04 pp que decorre das **2 casas decimais** com que o IBGE publica o
  número-índice (`0,005 / 7.695,82` já é 6,5e-7 em cada ponta) — impacto: **proposta** de trocar
  99% por **90%** e 1e-6 por **1e-3 pp**; nada foi alterado em `docs/specs/SPEC.md` (`AGENTS.md §8`
  proíbe). O código de F-004 usa `MONOTONIA_MINIMA = 0,90` (que ainda discrimina com folga um
  número-índice de uma série de variação: `v/63` fica em ~0,5, com teste) e exige, além de
  `<= 1e-3`, que a divergência seja `<= 2×` o limite do arredondamento — é o que prova que as duas
  séries são a mesma coisa em vez de só parecidas. Item aberto em `TODO.md §4` — ref: F-004 §5,
  CA-004, CA-005
- [2026-10-11] [fontes] **D-f · calendário de feriados pela rota HTML da ANBIMA, não pelo `.xls` que
  a SPEC nomeia — RATIFICADO pelo orquestrador, PROVISÓRIO para o Edu** — duas linhas, que são as
  do relatório de F-008:
  1. **O `.xls` de RF-018 é XLS/BIFF de verdade.** `feriados_nacionais.xls` responde HTTP 200 /
     111.104 bytes com magic bytes `D0 CF 11 E0 A1 B1 1A E1` (OLE2) — **não** é o XLSX disfarçado do
     S3 da ANBIMA (F-002). Isso **contradiz parcialmente** a linha de 2026-10-10 deste log ("nenhum
     arquivo é XLS/BIFF real"), que já previa o reencontro: "se aparecer XLS legado, volta ao
     debate". Ele apareceu. Lê-lo exigiria `xlrd` ou `python-calamine` no `pyproject` — dependência
     nova, que pede ADR.
  2. **A mesma lista está em HTML na mesma fonte.** `https://www.anbima.com.br/feriados/
     fer_nacionais/<ano>.asp`, ano a ano, em `<table>`, linkada pela própria página que oferece a
     planilha. É de lá que o calendário vem: `latin-1` + `<table>`, **zero dependência nova, zero
     feriado construído por regra**. Não é troca de fonte (ANBIMA continua ANBIMA, item A4 do
     e-mail), é troca de **formato**. A planilha continua sendo baixada e arquivada como **fonte de
     registro**, e `arquivar_fonte_de_registro` emite WARNING se um dia virar XLSX — o gatilho para
     reabrir o debate. Alternativas recusadas: `bizdays` (dependência nova **e** dado empacotado por
     terceiro em vez da fonte) e construir feriado por regra (**dado inventado**, proibido por
     `CLAUDE.md §4`).

  Validação: o conjunto de dias úteis derivado do HTML é **idêntico, dia a dia, em 2006-2025**, ao
  do CDI (SGS 12, Banco Central) e ao do IMA-B (bucket S3, outro produto da ANBIMA) — 5.022 × 5.022,
  zero diferença nas duas pontas. Na mesma decisão, `CalendarioDiasUteisSchema` **migrou** do
  extrator para `packages/shared/schemas/calendario.py` (+ export no `__init__.py` + espelho em
  `CONTRACTS.md §7`): é contrato de dado, e F-014/F-017 têm de importá-lo sem depender do extrator —
  ref: SPEC RF-018, CA-051/052, F-008 §2.1/§4.1/§5, linha `[deps]` de 2026-10-10 deste log
- [2026-10-11] [arquitetura] **D-g · `converter_para_brl`/`carregar_ptax` desceram para
  `apps/pipeline/transform/cambio.py` — PROVISÓRIA (organização de código, sem efeito em dado)** —
  motivo: as duas nasceram em `extract/yahoo.py` porque o Feature Contract de F-007 só abria dois
  arquivos, e `extract/msci.py` passou a **importar um extrator** só por causa delas. Conversão a
  BRL não é extração: é derivação sobre `data/processed/` — impacto: nasce
  `apps/pipeline/transform/` (`__init__.py` + `cambio.py`), que é onde **F-017** (acumulação de
  CDI/Selic, retornos trimestrais) vai morar — está escrito no `__init__`. `SerieInconsistente` subiu
  para `apps/pipeline/common/errors.py` no caminho, para a camada de transformação não importar
  exceção de extrator. Nenhum número muda: os 10 Parquets de F-007 saem idênticos, com os mesmos
  157 dias sem PTAX em `SP500_BRL` e 1.007 em `ACWI_BRL` — ref: F-007 §5, F-017
- [2026-10-11] [canônico] **D-h · B3 ⊂ ANBIMA em 69 datas: todo 4T de série da B3 precisa de 1 d.u.
  de ffill — vira item de DoR de F-014, não decisão desta consolidação** — motivo: achado de F-008
  contra 20 anos de série. O calendário da ANBIMA concorda **exatamente** com o CDI e com o IMA-B em
  2006-2025, mas o IBOV tem 4.953 dos 5.022 dias úteis: as 69 ausências são feriados
  municipais/estaduais de São Paulo (25/01, 09/07, 20/11 antes de ser nacional) e a emenda de fim de
  ano (24/12, 29, 30 e 31/12). A direção importa: **B3 ⊂ ANBIMA, nunca o inverso** — impacto: em
  **20 dos 83 trimestres** (todos os 4ºs trimestres de 2006 a 2025) o último dia útil bancário não
  tem fechamento da B3, então **toda série da B3 carrega `ffill_dias_uteis = 1` em todo 4T**. É o
  caso que ADR-006 §(b).8 / CA-066 resolvem, mas tem de ser **escolhido** (grade única bancária com
  ffill, ou grade própria da B3 com duas réguas de fim de trimestre), e escolher a segunda é
  **classe C**. Registrado na DoR de F-014 no `TODO.md` e em `docs/wiki/modules/canonical.md` —
  ref: F-008 §6, ADR-006, CA-066

### 2.2 Achados medidos na Onda 1 (comportamento de fonte, não decisão)

> Ficam aqui porque vão voltar ao debate: são coisas que a pesquisa (`docs/research/`) registrou
> diferente, ou que nenhuma documentação previa, e que custariam horas a quem reencontrasse.

- [2026-10-11] [fontes] **SGS: o erro de janela de 10 anos virou HTTP 406 (era 200)** —
  `docs/research/fontes-de-dados.md §A1` mediu **HTTP 200** com corpo de erro; em 2026-10-10 a mesma
  requisição (série 11, 1980→1990) responde **406** com corpo idêntico. Não é regressão (o pipeline
  falha alto pelas duas rotas: 406 cai em `FonteIndisponivel`, 200 cairia em
  `RespostaDeErroComStatus200`), mas é mudança de comportamento da fonte. **O risco R1 continua real
  por outro caminho:** série inexistente (`99999999`) devolve **XHTML com HTTP 200**, e é essa a
  fixture que prova CA-003 — ref: F-003 §2.2
- [2026-10-11] [fontes] **SGS: a meta Selic (432) é série de calendário corrido, não de dia útil** —
  publica o mesmo valor **todos** os dias, inclusive sábado e domingo: 8.319 pontos de 2004-01-01 a
  2026-10-10, com vão de exatamente 1 dia em 100% dos pares. A guarda "série diária só tem dia útil"
  acusava 2.377 datas legítimas. Registrada em `SERIES_DIARIAS_DE_CALENDARIO = {432}`, onde a
  continuidade exigida é **mais forte**: nenhum dia corrido ausente. A data futura (meta vigente até
  a próxima reunião do Copom) só aparece com `dataFinal` futuro e é truncada por `truncar_em`
  (CA-013) — ref: F-003 §2.1/§2.3
- [2026-10-11] [fontes] **Tesouro Direto: o download do recurso NÃO exige User-Agent de browser** —
  `GET` com `Session.headers.clear()` devolveu HTTP 200 e os 14.584.922 B. A exigência de UA que a
  pesquisa registra vale para a **API do CKAN** (`/api/3/action/...`), não para a rota `/download/`.
  `requer_user_agent_browser=True` ficou no contrato de propósito (custa nada e a guarda de CA-045
  continua certa), mas **não é** o que explica uma falha de download. A rota também **ignora o nome
  do arquivo** na URL — só o UUID do recurso importa; UUID errado dá 404 + HTML — ref: F-005 §6.1/6.2
- [2026-10-11] [fontes] **Tesouro Direto: o CSV é 100% ASCII, usa LF e não tem separador de
  milhar** — zero bytes > 127 nas 177.260 linhas, e `"20046,46"` (nunca `"20.046,46"`) em 886.300
  células numéricas. `encoding='latin-1'` continua declarado, mas o "teste de acento" de CA-022
  **não é satisfazível com o dado real de hoje**: quem cobre é uma fixture **sintética nomeada como
  tal**. `para_float_ptbr` cobre o caso do milhar, e nenhum dado desta fonte prova esse caminho —
  ref: F-005 §6.3/6.4, CA-022
- [2026-10-11] [fontes] **Yahoo: a resposta não é byte-estável** — três GETs idênticos deram
  `sha256` `d37691c48436`, `d37691c48436` e `9a4193bcbc4c`, com **os mesmos 615.027 bytes e os
  mesmos `close`**: a fonte alterna a ordem das chaves de `meta.currentTradingPeriod.pre`. Por isso
  o Yahoo usa `_arquivar_retrato`, que reparseia o bruto arquivado, compara a série `(date, value)`
  e **mantém o retrato original** quando ela é a mesma; valor revisado continua levantando
  `ConteudoDivergente` (R8). Duas outras armadilhas da mesma fonte: `range=max` **trunca e rebaixa**
  (169 pontos contra 490 com `period1`/`period2`) e respondeu `dataGranularity="3mo"` **ignorando o
  `interval=1mo` pedido** — nenhuma função emite `range`, e o parser recusa granularidade ≠ `1d` —
  ref: F-007 §4.2/§4.6, CA-045
- [2026-10-11] [fontes] **MSCI: erro com HTTP 200 e chave que a infra não conhece** — a fonte usa
  `error_code`/`error_message`, não `error`, então `validar_corpo_json_array` passaria batido; há
  guarda própria em `_corpo_json`. E **código inexistente devolve 200 com `INDEX_LEVELS: []`**
  (medido em `705000` e `999999`), sem campo de erro nenhum: só a contagem mínima pega — é por isso
  que `MSCI_BRAZIL` continua `a_confirmar` — ref: F-007 §4.7/§4.8
- [2026-10-11] [fontes] **B3: código inexistente devolve o mesmo corpo de ano sem série** — tanto
  um ano anterior ao início do índice quanto um código inválido (`XXXX`) respondem HTTP 200 com
  `{"min":null,"max":null,"results":null}`. **O corpo não distingue**: quem distingue são (a) a
  validação do código contra o catálogo antes da requisição e (b) a guarda de contagem mínima
  baseada no `data_inicio` do catálogo. Erro de verdade vem como HTTP 200 com **0 byte** (payload
  base64 inválido) ou HTML da SPA — ref: F-006 §3
- [2026-10-11] [tooling] **pandera: `isin` de um único valor tem de ser `list`, nunca tupla** —
  `isin=("ANBIMA_WEB",)` **reprova toda linha** nesta versão: a tupla de um elemento é desempacotada
  e o `set` vira o conjunto de *letras* da string. Tupla com 2+ itens funciona, que é por que
  `FONTES_VALIDAS` em `raw_series.py` passa. Medido em 2026-10-10, custou ~1 hora de depuração em
  F-008; está escrito no docstring de `packages/shared/schemas/calendario.py` para não custar de
  novo — ref: F-008 §4.2

---

## 3. Regras deste log

1. **Toda substituição de fonte entra aqui** com os 4 campos. Sem os 4, não é registro — é lembrete.
2. Decisão **arquitetural com trade-off real** → **ADR** em `docs/decisions/adr/`, e aqui só a referência.
3. Mudança de PRD / SPEC / Anti-SPEC / e-mail de escopo → **pausa e autorização humana**, nunca este log.
4. Linha `PROVISÓRIA` que receber aval: troque o marcador por `ACEITA — <quem> em <data>` e, se houver
   ADR, mude o status do ADR também. Nunca apague a linha original.
5. **RF-045:** a comunicação escrita das substituições ao Alexandre é parte da entrega (F-031, classe D).
   Esta seção §1 é o texto-base dessa comunicação.

---

## Links

- Escopo (imutável) → [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
- Lacunas medidas → [`docs/research/fontes-de-dados-RESUMO.md §2`](../research/fontes-de-dados-RESUMO.md)
- ADRs → [`docs/decisions/adr/`](../decisions/adr/) · Bloqueios → [`TODO.md §4`](../../TODO.md)
- Ambiente e conectividade → [`docs/plans/skills-manifest.md`](./skills-manifest.md)

---

*Documento vivo e deliberadamente pequeno — a §2.2 (achados de fonte) é a parte que mais cresce e a
primeira a enxugar. Quando o Edu avaliar D-a..D-h, o que virar permanente sobe para `CONTRACTS.md` /
ADR e sai daqui; o que virar óbvio se apaga. Nunca apague a linha original de uma decisão avaliada:
troque o marcador por `ACEITA — <quem> em <data>`.*
