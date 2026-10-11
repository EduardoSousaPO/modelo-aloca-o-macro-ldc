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
> e o mesmo vale para as 8 decisões de convenção da **§2.1** (D-a..D-h, consolidação da Onda 1) e
> para as da **§2.3** (D-i e D-j da Onda 2; **D-s, D-t e D-u** da Onda 3, parte 3 — as três mudam
> número publicado).
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

  **RESOLVIDA em 2026-10-11 por F-014: escolhida a (a)** — grade bancária única, com 1 d.u. de ffill
  nas séries da B3 no 4T; **provisória, aval de Edu pendente** (é a parte (b) de ADR-006, que segue
  em `Proposta`). **O custo, medido no acervo e não estimado:** **215** células com
  `ffill_dias_uteis = 1` de **4.038** (**5,325%**), `distribuicao_ffill_dias_uteis = {0: 3.823,
  1: 215}` — **nenhuma** célula com ffill 2..5 —, em **11** séries, **todas** `source = B3_API`
  (IBOV, ICON, IDIV, IEEX, IFIX, IFNC, IMAT, IMOB, INDX, SMLL, UTIL) e **20** trimestres,
  exatamente `2006Q4..2025Q4`; **0** séries da B3 com ffill em 1T/2T/3T e **0** séries não-B3 com
  ffill em qualquer trimestre. A contagem por série e por trimestre está **no dado**
  (`relatorio_alinhamento.json → ffill_por_serie`, `→ ffill_por_trimestre`, `→ decisao_d_h`).
  **Por que (a):** (b) criaria **duas réguas de tempo** no mesmo dataset — toda tabela e toda figura
  passariam a declarar qual grade a linha usa, e o `join` entre `macro_quarterly` e
  `asset_returns_quarterly` deixaria de ser por `quarter_end` —, trocando um erro de **1 dia útil,
  medido e visível por linha**, por uma ambiguidade estrutural **invisível**; o efeito no retorno é
  **nulo em T, não deslocado** (o 4T usa o mesmo fechamento nas duas pontas do ano); e a direção do
  achado permite (a), porque **B3 ⊂ ANBIMA, nunca o inverso**, então (a) nunca precisa de ffill
  "para frente" nem olha o futuro. A escolha está **travada no contrato** pelo check
  `quarter_end_unico_por_trimestre` de `AlinhadoTrimestralSchema`: virar para (b) exige mudar o
  schema, não só o código — que é o comportamento desejado. Os 215 ffill vão para a página de
  limitações (F-028) — ref: F-014 §4, `CONTRACTS.md §8`, ADR-006 §(b).2/§(b).8, CA-066

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

### 2.3 Consolidação da Onda 2 — camada canônica (2026-10-11)

> Decisões tomadas ao fechar a Onda 2, em duas partes: **parte 1** (F-013 `raw_series` + catálogo
> materializado, F-014 alinhamento trimestral, F-016 curva) → **D-i, D-j** e as 5 de
> organização/contrato; **parte 2** (F-015, F-017, F-010) → **D-k a D-q**, mais abaixo.
> **D-i e D-j são provisórias — aval de Edu pendente.**
> As demais são de organização/contrato e foram **aceitas pelo orquestrador**. Nenhuma toca SPEC,
> PRD, Anti-SPEC ou o e-mail de escopo; onde o dado real contradiz a SPEC (**D-i**, CA-025), a
> decisão foi **registrar e medir**, não editar.

- [2026-10-11] [spec/catálogo] **D-i · CA-025 não fecha com o vértice curto de 1 ano; catálogo
  134 → 138 e a inclinação real **5a−3a** passa a ser a variável principal de regime —
  PROVISÓRIA, aguarda o aval do Edu; SPEC NÃO EDITADA** — motivo: CA-025 pede valor para **≥ 95%**
  dos dias úteis de 2006→2026 na inclinação real, e F-016 mediu **60,53%** em
  `INCLINACAO_REAL_5A_1A` sobre as 5.184 datas base de 2006-01-01 a 2026-10-09. **Nenhuma
  implementação chega a 95% com o vértice de 1 ano:** a grade de vencimentos da NTN-B é 15/05 e
  15/08 de anos **alternados**, há períodos longos em que o título mais curto vence em mais de 1 ano,
  e **2021 e 2022 inteiros** não tiveram nenhum. Chegar a 95% exigiria extrapolar, o que a Anti-SPEC
  §10.1.1 proíbe. A premissa do CA olha a **ponta longa** (de fato 100%); o que limita é a **curta**
  — impacto: **4 entradas novas** em `packages/shared/schemas/series_catalog_data.py` (`CURVA_REAL_3A`,
  `CURVA_NOMINAL_3A`, `INCLINACAO_REAL_5A_3A`, `INCLINACAO_NOMINAL_5A_3A`; catálogo **134 → 138**,
  `DERIVADO` 9 → **13**, `N_SERIES_ESPERADAS = 138`), F-016 passa de 7 para **11** séries gravadas em
  `data/processed/curva/`, e **`INCLINACAO_REAL_5A_3A` (95,25% ✔ CA-025)** é a **variável principal
  de regime, em caráter provisório**. As duas **5a−1a continuam publicadas como secundárias com a
  cobertura declarada** (60,53% e 97,57%) — são as que ADR-004 §3 nomeia e têm a leitura histórica de
  20 anos. **O vértice de 3 anos não é escopo novo:** CA-023 já diz "interpola para 1, 3 e 5 anos", e
  o escopo incluído de F-016 no `TODO.md` também. Os vértices de **10 anos** entraram como
  medidos-e-**não**-gravados (`VERTICES_FORA_DO_CATALOGO`), para deixar CA-024 quantificado (nominal
  10a: **36,81%** das datas base de 2006+) sem violar CA-055. **Efeito nas 7 séries que já existiam:
  nenhum** — os 7 Parquets saíram com `sha256` idêntico ao da rodada anterior a D-i, zero célula
  alterada. Os dois números estão **travados por teste**
  (`test_cobertura_da_inclinacao_real_1a_e_a_medida_e_nao_atinge_os_95_de_ca025` e
  `test_inclinacao_real_5a_3a_e_a_que_fecha_ca025`, medido na série **gravada**). Mesmo caminho de
  **D-e**: mediu, registrou, travou no teste, não editou a SPEC (`AGENTS.md §8`). **Pendência do
  Edu:** ratificar D-i **e** a nota editorial em **ADR-004 §3**, que ainda nomeia a 5a−1a como
  principal. O `obs` de `INCLINACAO_REAL_5A_1A` foi reescrito no fechamento para dizer que a série é
  secundária desde D-i (era a única linha do catálogo que contradizia a decisão) — ref: F-016 §0/§4.3,
  CA-023/CA-024/CA-025, ADR-004, `TODO.md §4`
- [2026-10-11] [método] **D-j · prazo da interpolação da curva em **dias corridos** (ACT), não em
  dias úteis — PROVISÓRIA, aval de Edu pendente** — motivo: o briefing pedia dias úteis pelo
  calendário ANBIMA, e **os dois métodos estão implementados** (`MetricaPrazo.DIAS_CORRIDOS`, com
  alvos de 365,25 / 1.095,75 / 1.826,25 dias, e `MetricaPrazo.DIAS_UTEIS`, com 252 / 756 / 1.260
  d.u. contados pelo calendário de F-008). O padrão é ACT por **cobertura**, não por preferência: o
  calendário de F-008 cobre **2001-01-01..2030-12-31** e consulta fora disso **levanta**
  (`ForaDaCoberturaDoCalendario`), enquanto os vencimentos do painel chegam a **2060** e o vértice de
  5 anos de qualquer data base de 2026 cai em ~2031. Devolver `NULL` por limite do **nosso**
  calendário — e não por ausência de título — seria mentir sobre o suporte do dado, o oposto do que
  CA-024 quer; e construir feriado por regra está recusado por **D-f** ("dado inventado") — impacto:
  o custo da escolha é **mediana de 0,14 a 0,41 bps** de diferença entre as duas métricas (p95 até
  1,87 bps, máximo 4,60 bps), contra as **dezenas de bps** de spread de varejo que ADR-004 já
  declara: a métrica de prazo **não é o que limita a precisão** destas séries. Em dias úteis as duas
  séries de 1 ano ganhariam 2 a 11 datas base e as de 5 anos **perderiam 298 a 700** — exatamente as
  datas cujo vértice ou cujo título de borda cai depois de 2030-12-31. Travado em
  `test_metrica_em_dias_uteis_produz_o_mesmo_vertice_a_menos_de_poucos_bps`. **Armadilha
  operacional:** `--metrica-prazo dias_uteis` grava **nos mesmos 11 nomes de arquivo**; o que
  distingue é o campo `metrica_prazo` do `relatorio_curva.json` — conferir antes de qualquer build do
  canônico — ref: F-016 §3.3, ADR-004, D-f
- [2026-10-11] [canônico] **O painel do Tesouro Direto fica **fora** de `raw_series`, declarado no
  dado — ACEITO pelo orquestrador (confirmado pelo QA de F-013)** — motivo:
  `data/processed/tesouro-direto/td_painel.parquet` tem o mesmo `ProcessedSeriesSchema`, mas seus
  **750 `series_id` compostos** (`TD_<SIGLA>_<AAAAMMDD>_<METRICA>`) **não são entradas do catálogo**:
  o catálogo tem `TESOURO_TD_PRECOTAXA` para a **fonte** e `CURVA_*`/`INCLINACAO_*`/`BREAKEVEN_5A`
  (`fonte=DERIVADO`) para as séries que dela nascem. Admitir os 750 violaria **CA-055/CA-120** (toda
  linha resolve para uma URL do catálogo) ou exigiria 750 entradas novas — mudança de **contrato**,
  não de implementação — e levaria `raw_series` de 218.643 para 1.104.943 linhas de insumo que
  nenhuma tabela canônica consome direto — impacto: a exclusão está **no dado**
  (`relatorio_build.json → tabelas_excluidas`, com o motivo por arquivo), não só na documentação;
  `calendario/dias_uteis_anbima.parquet` sai pelo mesmo mecanismo e por motivo óbvio
  (`CalendarioDiasUteisSchema`, 4 colunas, não é série de valores). **Consequência para F-016:** o
  insumo dela continua sendo `data/processed/tesouro-direto/`, e é **ela** que acrescenta as 11
  séries da curva a `raw_series` publicando em `data/processed/curva/` — e **reexecutando o build de
  F-013 depois**, porque `raw_series.parquet` é **reescrito inteiro** a cada build, sem `append`
  (vale igual para F-010/F-011/F-012) — ref: F-013 §2.2/§6.1, `ONDA-2-QA-F013.md §4.6`,
  `CONTRACTS.md §1.1`, CA-055/CA-120
- [2026-10-11] [canônico] **`data/canonical/ldc.duckdb` mantido; ADR-006 §(a).2 (que escreve
  `macro.duckdb`) recebe a correção **editorial** quando for aceito — DECIDIDO pelo orquestrador** —
  motivo: ADR-006 §(a).2 nomeia `data/canonical/macro.duckdb`, o briefing da Onda 2 pediu
  `ldc.duckdb` e F-013 implementou `ldc.duckdb` (constante `NOME_DUCKDB`, um lugar só). É divergência
  de **nome**, **zero semântica** — e não se renomeia um artefato vivo para casar com um ADR que
  ainda está em `Proposta` — impacto: nenhum em dado; o arquivo é **derivado e descartável** (só
  views `CREATE OR REPLACE VIEW ... SELECT * FROM read_parquet(<caminho absoluto>)`, nunca tabelas,
  então não há segunda cópia que possa divergir do Parquet e apagá-lo não perde nada). Fica como
  **pendência editorial do aceite do ADR-006**, registrada em `TODO.md §4` e §6 — ref: F-013 §8.2,
  `ONDA-2-QA-F013.md` P2-6, ADR-006 §(a).2
- [2026-10-11] [catálogo] **Campo `calendario` (`dias_uteis` | `corrido` | nulo) acrescentado ao
  catálogo — ACEITO pelo orquestrador (P1-2 do QA da Onda 1 e P1-2 do QA de F-013)** — motivo: a
  meta Selic (SGS 432) publica em **dia corrido** e **2.377 dos seus 8.319 pontos (28,6%) caem em fim
  de semana**, mas a distinção vivia só na constante `SERIES_DIARIAS_DE_CALENDARIO` dentro de
  `apps/pipeline/extract/bcb_sgs.py`: quem lê catálogo e Parquet — F-014, F-017, qualquer contagem ou
  média sobre `freq='D'` — não tinha como saber, e sairia enviesado em 28,6% dos pontos — impacto: o
  campo entrou em `SeriesCatalogEntry` (pydantic, com validator que recusa `calendario` em série não
  diária) **e** em `SeriesCatalogSchema` (pandera) — sem o segundo, `strict = True` o mantinha fora
  do tabular e o artefato materializado publicava **25** colunas sem ele, que é exatamente o P1-2 do
  QA de F-013. Hoje **7** séries `freq=D` o declaram (`BCB_SGS_432 = corrido`; Selic over 11/1178,
  CDI 12/4389 e PTAX 1/10813 = `dias_uteis`); nas demais é **nulo**, nunca a string `"None"`. É de
  `calendario` que F-014 **deriva** a régua `corrido` (`series_de_calendario_corrido()`), em vez de
  manter uma segunda lista — e um teste de contrato afirma que as **três** declarações (catálogo,
  derivação e a constante do extrator) coincidem. Série nova de dia corrido cai na régua certa **sem**
  editar F-014 — ref: `ONDA-1-QA-A.md §4.5`, `ONDA-2-QA-F013.md` P1-2, `CONTRACTS.md §2/§2.4`,
  F-014 §2.2
- [2026-10-11] [bug] **`ManifestoAusente`: bruto arquivado sem `.meta.json` passa a ser **recusado**,
  em vez de datar o Parquet pelo relógio da rodada — DECIDIDO (é correção, não escolha)** — motivo:
  o P1-1 do lote B do QA da Onda 1. O padrão `obtido_em_arquivado(...) or datetime.now(tz=UTC)` era
  comum aos 8 extratores, mas **só F-005 tinha caminho que chegava nele** —
  `caminho_bruto_mais_recente()` aceitava de propósito `data/raw/tesouro-direto/td.csv`, a amostra da
  pesquisa, que existe e **não tem manifesto**. Efeito reproduzido pelo revisor: duas execuções
  `--offline` do **mesmo** bruto produziam Parquets **diferentes**, com `collected_at` em
  microssegundos, e `vintage` deixava de ser a safra do dado (quebra D-b, CA-121, Anti-SPEC §10.4.22)
  — impacto: a guarda subiu para `apps/pipeline/common/` (`ManifestoAusente` em `errors.py`,
  levantada por `io_layers.py`), com a mensagem dizendo o que fazer ("rode a extração **online** uma
  vez, o manifesto nasce aí, ou passe `collected_at=` explicitamente"); os 8 extratores a usam e há
  teste de regressão em cada um. **Recusar é mais barato do que gravar um número plausível e errado**
  — ref: `ONDA-1-QA-B.md` P1-1, D-b, CA-121
- [2026-10-11] [repo] **Exceção no `.gitignore`: `.parquet` em `tests/fixtures/` é versionado —
  DECIDIDO pelo orquestrador** — motivo: a regra "nenhum `.parquet` no git" (`CLAUDE.md §6`,
  RNF-009) deixava as duas varreduras da consolidação — `tests/unit/test_contract_sgs_sidra.py` e
  `tests/unit/test_processed_layer_conventions.py`, a **única** trava regressível de D-a, D-b, PK
  única e da reconciliação SGS × SIDRA — **pulando no CI**, porque `data/` não está no git e o
  `actions/checkout` entrega a árvore sem ele (9 skipped, medido no P1-4 do lote A do QA) — impacto:
  `!tests/fixtures/**/*.parquet` no `.gitignore`, e `tests/fixtures/processed/` guarda **recortes
  reais** de `data/processed/` (≤ 20 KB cada, 6 fontes) com procedência em
  `tests/fixtures/processed/README.md`. É a **única** exceção à regra, e vale só para fixture: dado
  de pipeline continua fora do git, e nada em `data/` é versionado. Os recortes também são o segundo
  acervo da parametrização de F-014 (é o que permite ao teste do limite de ffill usar um buraco
  **real**, não sintético) — ref: `ONDA-1-QA-A.md §4.6` (P1-4), `.gitignore`,
  `tests/fixtures/processed/README.md`, F-014 §5.7

> **Parte 2 da Onda 2** (F-015 `macro_quarterly`, F-017 `asset_returns_quarterly`, F-010 Focus),
> fechada em 2026-10-11. **D-k a D-q são provisórias — aguardam Edu**, exceto onde o item diz
> "é correção". Nenhuma toca SPEC, PRD, Anti-SPEC ou o e-mail; onde o dado real contradiz a SPEC
> (**D-m**, CA-007) a decisão foi **registrar e medir**, como em D-e e D-i.

- [2026-10-11] [canônico] **D-k · as 5 tabelas do Focus ficam **fora** de `raw_series`, pelo
  precedente do painel do Tesouro Direto — ACEITO pelo orquestrador, aguarda Edu só como
  ratificação de contrato** — motivo: F-010 grava `data/processed/focus/` com **197 `series_id`
  compostos** (`FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>`, p.ex. `FOCUS_A_IPCA_H0`,
  `FOCUS_RCOPOM_SELIC_R1-2027`) que **não são entradas do `series_catalog`**: o catálogo registra o
  **EntitySet** (`FOCUS_ANUAIS`, `FOCUS_MENSAIS`, `FOCUS_TRIMESTRAIS`, `FOCUS_SELIC`,
  `FOCUS_INFLACAO_12M`) como fonte. Admitir os 197 violaria **CA-055/CA-120** (toda linha do
  canônico resolve para uma URL do catálogo) ou exigiria 197 entradas novas — mudança de
  **contrato**, não de implementação. É literalmente o caso de `td_painel.parquet` (750 compostos),
  já excluído com motivo registrado — impacto: **5 entradas novas** em
  `TABELAS_FORA_DO_RAW_SERIES` (`apps/pipeline/canonical/build_raw_series.py`), cada uma com o
  motivo **no dado** (`relatorio_build.json → tabelas_excluidas`, agora com **7** arquivos), e a
  fixture `processed_minimo` + o teste de conjunto exato
  (`test_descoberta_exclui_calendario_painel_do_tesouro_e_focus`, renomeado) passam a gravar as 5
  fatias como `processed_series` **válidas** — o que as exclui é o `series_id`, não o schema.
  `tests/contract/test_curva_contract.py` afirma o mesmo conjunto exato, e foi atualizado.
  **F-015 consome o Focus direto de `data/processed/focus/`** (mesmo `ProcessedSeriesSchema`), como
  F-014/F-017 já fazem com o calendário, e a **procedência aponta para o EntitySet**, não para o
  `series_id` por horizonte. Sem D-k, 2 testes de F-013 ficavam vermelhos (`62 == 259` é
  `62 + 197`) — ref: F-010 §6, F-015 §3.5/§7.4, F-017 §7.5, CA-055/CA-120, `CONTRACTS.md §1.1`
- [2026-10-11] [canônico] **D-l · `USDBRL` entra no universo de `asset_returns_quarterly`
  (24 ativos, 1.963 linhas) com `is_total_return = False` — PROVISÓRIA, aguarda Edu** — motivo:
  **RF-038** (dimensionamento da alocação internacional) e `metodologia §4.2` (câmbio como hedge)
  pedem o retorno trimestral do dólar, e a PTAX (`BCB_SGS_1`) já tem os **83** trimestres em
  `alinhado_trimestral` — ficar fora era escolha de briefing ("câmbio não é ativo do bloco B"), não
  ausência de dado. `is_total_return = False` porque **câmbio não tem carrego**: o cupom cambial
  ficaria de fora de qualquer construção, e `None` ("a confirmar", o gap G-01) diria que falta medir
  algo que **não se aplica** — impacto: 1 linha em `UNIVERSO` (`apps/pipeline/canonical/retornos.py`,
  `Ativo("USDBRL", "BCB_SGS_1", "internacional")`), 1 campo no catálogo (`is_total_return=False` em
  `BCB_SGS_1`, acréscimo puro) e `USDBRL` sai de `ATIVOS_FORA_DO_UNIVERSO` (9 → **8** motivos
  declarados). Medido: `asset_returns_quarterly` **1.880 → 1.963** linhas (+83) e **23 → 24**
  ativos; `ret_tri` do USDBRL vai de **−15,70 %** a **+28,98 %**, 1 nulo (2006Q1, sem `T−1`);
  `is_total_return` segue com **820** nulos (os 9 setoriais da B3 + CDI — o USDBRL não acrescenta
  nulo). **Zero mudança de schema e de regra**: `USDBRL` já era um dos 32 `asset_id` de
  `ASSET_IDS_VALIDOS`. Nenhum teste fixava 23/1.880 (as asserções são contra `len(UNIVERSO)`); o
  único ajuste de teste foi deduplicar `BCB_SGS_1` no acervo sintético, que agora está no universo
  **e** no portão `SERIES_EXIGIDAS` de F-014 — ref: F-017 §7.2/§3, RF-038, CA-062, ADR-006 §(b)
- [2026-10-11] [spec] **D-m · CA-007 não é satisfazível com o IBC-Br real; os 16 nulos de
  `ibcbr_gap` são aceitos — PROVISÓRIA, aguarda Edu; SPEC NÃO EDITADA** — motivo: CA-007 pede
  `ibcbr_gap` nos 83 trimestres **ou** `is_estimated=True`, e CA-060 permite `is_estimated=True`
  **só** em `2026Q3` — as duas não podem valer juntas. A aritmética: SGS 24364 começa em **2003**
  (o extrator pega de 2004) → `ibcbr_yoy` só existe de **2005Q1** → a média móvel de **20**
  trimestres com janela cheia só fecha em **2009Q4**. Para hiato em `2006Q1` seria preciso IBC-Br
  desde **2000Q2**, e a série **não existe** antes de 2003; nenhuma grade de apoio resolve —
  impacto: `ibcbr_yoy_trend`/`ibcbr_gap` ficam nulos em `2006Q1..2009Q3` (15) e em `2026Q3` (**16**
  no total), com o motivo publicado em `relatorio_macro.json`. A **V1 de F-019 classifica 67 dos
  83 trimestres** — 2006-2009, inclusive a crise de 2008, fica fora do eixo de crescimento.
  A alternativa está **medida** no relatório (`sensibilidade_ibcbr_gap`): `min_periods = 8`
  recuperaria **12** trimestres com `max |diferença| = 0,0 pp` no trecho comum, e **não** foi
  adotada porque média de janela parcial é outro estimador, cujo significado muda ao longo do tempo
  (o hiato de 2006 deixaria de ser comparável ao de 2015). Mesmo tratamento de **D-e** e **D-i**:
  mediu, registrou, travou em teste, não editou a SPEC (`AGENTS.md §8`) — ref: F-015 §3.3/§7.1,
  CA-007, CA-060, `TODO.md §4`
- [2026-10-11] [contrato] **D-n · `INCLINACAO_REAL_5A_3A` **não** ganha coluna em
  `MacroQuarterlySchema` nesta onda; F-019/F-021 leem a série alinhada direto — DECIDIDO pelo
  orquestrador, com dívida de schema registrada** — motivo: a principal provisória de **D-i** é a
  5a−3a (**95,25 %** de cobertura, a que fecha CA-025), mas o schema só prevê
  `inclinacao_real_5a_1a` / `inclinacao_nominal_5a_1a`. Acrescentar coluna a uma tabela canônica é
  **alteração de schema classe C**, logo pausa (`AGENTS.md §9/§13`) — e a onda não tem folga para
  isso antes de 2026-10-14 — impacto: `macro_quarterly` publica a 5a−1a com **33 nulos (39,8 %)**
  e declarados, e a 5a−3a continua disponível em `raw_series`/`data/processed/curva/`, de onde
  F-019/F-021 a lêem via `alinhar_series` (é o mesmo caminho que F-017 usa para as derivadas de
  F-007, que F-014 deixa fora de propósito). **Dívida:** acrescentar `inclinacao_real_5a_3a` (e
  provavelmente `inclinacao_nominal_5a_3a`) a `MacroQuarterlySchema` como feature C própria, depois
  do Comitê — ref: F-015 §7.2, D-i, CA-025, `TODO.md §6`
- [2026-10-11] [contrato] **D-o · unidade: `macro_quarterly` em **por cento/pp**,
  `asset_returns_quarterly` em **fração** — REGISTRADO (é o estado medido, não uma escolha nova)** —
  motivo: `macro_quarterly` está em por cento porque é o vocabulário do projeto (`UNIDADES_VALIDAS`
  tem `%`, `%a.a.`, `pp` e nenhuma fração), é o que `LIMIAR_SELIC_PP = 0,25` pressupõe e é o que os
  canários exigem (`ipca_12m` de `2006Q1` **tem** de ser `5,32`, o número que o SGS publica);
  `asset_returns_quarterly` está em fração porque `(1+r)/(1+b) − 1` é a conta de ADR-006 §(b).5 e
  misturar escala ali **produziria número errado**, não só confuso — impacto: as duas tabelas
  publicam **`cdi_tri` e `ipca_tri` com o mesmo nome em escalas diferentes**. Hoje **não há bug**:
  F-017 calcula as duas por conta própria e **nunca** lê `macro_quarterly`, e a reprodução cruzada
  por dois agentes/dois caminhos de código deu `max |macro − 100 × retornos| = 0,0` nos 83
  trimestres — o que é exatamente a prova de que a razão de 100 é a única diferença. Mas quem
  cruzar as duas sem ler a unidade **erra por 100x** — por isso a nota entrou em
  `CONTRACTS.md §3` e **§4**, e o mapa de unidades já vai no dado
  (`relatorio_macro.json → unidades`, `relatorio_retornos.json → convencoes`). **Dívida da fase 2:**
  consumidor único, ou prefixo de escala no nome da coluna — ref: F-015 §2/§5.2, F-017 §2, ADR-006
- [2026-10-11] [catálogo] **D-p · `FOCUS_PIB_TOTAL` do catálogo passa a `status: descartada` —
  ACEITO pelo orquestrador** — motivo: a entrada existia com `status=a_confirmar` e
  `identificador='a_confirmar'` **porque G-04 estava aberto** (o rótulo do indicador na fonte era
  desconhecido). **G-04 está resolvido** — o rótulo é `PIB Total`, enumerado por F-010 em
  `INDICADORES_ENUMERADOS` — e o dado **já sai** como `FOCUS_A_PIB_TOTAL_H0`/`_H1` dentro do
  EntitySet `FOCUS_ANUAIS`. Manter `a_confirmar` publicaria um gap que não existe mais — impacto:
  **1 entrada alterada** (nenhuma acrescentada, nenhuma removida): `status` → `descartada`, `obs`
  com o motivo e `identificador` → `ExpectativasMercadoAnuais (Indicador eq 'PIB Total')`, porque o
  `SeriesCatalogEntry` recusa `identificador='a_confirmar'` com `status != a_confirmar` (é o
  validator fazendo o trabalho dele). Catálogo segue com **138** entradas; `descartada` vai de 14
  para **15** e `a_confirmar` de 8 para **7**. `test_schemas_smoke` verde (`N_SERIES_ESPERADAS`
  **não** mudou) — ref: F-010 §3.5/§6, G-04, `CONTRACTS.md §2.1`
- [2026-10-11] [achado/método] **D-q · os achados do Focus que valem registro permanente —
  REGISTRADO (comportamento de fonte e convenção, não escolha reversível)**:
  **(a) G-04 resolvido** — o rótulo do indicador de PIB na fonte é **`PIB Total`** (não "PIB", não
  "PIB Total (%)"), presente em `ExpectativasMercadoAnuais` e `ExpectativasMercadoTrimestrais`
  **desde 2006**; o conjunto de indicadores **muda ao longo da série** (`IPCA Livres`,
  `IPCA Serviços`, `Taxa de desocupação` e `Dívida bruta` não existiam em 2006) e pedir indicador
  inexistente devolve **HTTP 200 com `{"value":[]}`** — vazio silencioso, não erro.
  **(b) G-05 resolvido** — `baseCalculo=0` (todas as instituições dos últimos 30 dias) é a **única**
  base com os 20 anos do e-mail: medido ano a ano, `baseCalculo=1` (últimos 5 dias úteis) **só
  existe de 2014 em diante** (vazio em 2006, 2010, 2011, 2012 e 2013). Filtrar é **obrigatório**:
  sem filtro a série **dobra** de 2014 em diante. Em 2026-10-01, IPCA/2026: `bc=0` → mediana 5,0
  com 144 respondentes; `bc=1` → 5,1 com 61.
  **(c) O Focus é exceção explícita a D-a** — `date` é o **dia da pesquisa**, não fim de período
  civil, e o **horizonte vive no `series_id`** (`H0`/`H1`/`HM1`/`S`/`N`/`R<n>-<ano>`), nunca na
  data. Converter para fim de período colapsaria `H0` e `H1` na mesma data e **mentiria sobre
  quando o número era conhecido** — e é essa propriedade (a única fonte do projeto **sem**
  look-ahead) que `metodologia §1.5/§5.1` pede para preservar. Quem alinha decide a régua; a
  de F-015 é a **última coleta até o último dia útil de `T−1`** ("a coleta do início de T" de
  `metodologia §2`), com troca de `H0` para `H1` quando `T` é 1º trimestre — sem a troca,
  `focus_pib_ano` de **1/4 das linhas** traria a expectativa do ano que acabou.
  **(d) `%20` e não `+`** — espaço no `$filter`/`$orderby` do OData tem de ser `%20`; `requests`
  com `params=` (e `urlencode`) manda `+` e o backend responde **HTTP 400**
  (`"The system query option '$orderby' has the not-allowed value 'Data+asc'."`). Daí `montar_url`
  + `quote(..., safe="$,'/:()")` e a proibição de `params=` nesta fonte.
  **(e) `ibcbr_yoy` em fim de período** (decisão 6 de F-015) — ~~`metodologia §2` diz "média do
  trimestre"; o projeto usa **fim de período**, que é a convenção única do canônico (ADR-006,
  **D-a**) e o que preserva "nível ≡ célula de F-014" bit a bit. Trocar é 1 linha e **muda os 83
  `ibcbr_gap`**~~ → **SUPERADA POR D-s em 2026-10-11** (linha original preservada pela regra 4
  deste log). O QA da Onda 2 (lote A, **P1-1**) quantificou o que faltava: não eram "os 83
  `ibcbr_gap`", eram **7 dos 67 trimestres trocando de quadrante na V1**. Ver **D-s** abaixo —
  ref: F-010 §2/§3.1/§3.4/§3.5, F-015 §3.5/§7.6, D-a, ADR-006, `modules/focus.md`

#### Parte 3 — Onda 3, parte 1: materialização `asof` + lentes de regime (2026-10-11)

> Decisões tomadas ao **fechar** F-018 (`asof`), F-019 (V1) e F-021 (V3) e ao absorver os P1 dos
> dois QAs da Onda 2. **D-s, D-t e D-u são PROVISÓRIAS — aguardam Edu** (mudam número publicado).
> **D-r, D-v, D-w e D-x** são de organização/contrato e foram **aceitas pelo orquestrador**.
> Nenhuma toca SPEC, PRD, Anti-SPEC ou o e-mail de escopo. ADR-001 segue em `Proposta`, logo
> **nada daqui é publicável** (CA-090, `AGENTS.md §14`).

- [2026-10-11] [regimes] **D-r · F-019 grava `regimes_v1.parquet` validado por `RegimesV1Schema`
  (acréscimo), não `regimes.parquet`; a junção em `RegimesSchema` é delegada a F-022 — ACEITA pelo
  orquestrador** — motivo: `RegimesSchema` é o contrato da tabela **completa** (`ciclo_selic`,
  `regime_v2`, `stress_flag` são `nullable=False` e pertencem a F-020/F-021, e `regime_v1` é
  `nullable=False` num enum de 4 rótulos). Gravar `regimes.parquet` hoje exigiria **uma** de três
  coisas, todas recusadas: inventar colunas de outra lente (Anti-SPEC §10.1.2), inventar quadrante
  para os 16 `INDETERMINADO` (§10.1.1) ou **alterar** schema existente (pausa, `AGENTS.md §9/§13`)
  — impacto: `RegimesV1Schema` + `COLUNAS_V1_DE_REGIMES` acrescentados ao fim de
  `packages/shared/schemas/regimes.py`; `regime_v1` **nulo** + `status_regime_v1 = INDETERMINADO` +
  `motivo_indeterminado = GAP_AUSENTE` nos 16 trimestres sem `ibcbr_gap` (D-m), nunca estimativa.
  **Achado que sobe ao Comitê, não decisão:** a V1 troca de rótulo entre `revised` e `asof` em
  **22 de 66 trimestres = 33,33%** (era 29,85% antes de D-s), **acima** dos 25% de **CA-074** ⇒
  pelo critério escrito a V1 **não é operacional na forma `asof`** (a leitura descritiva, sim) e a
  hipótese **H-03 do PRD cai**. Vai à página de limitações (F-028) e ao slide, não a nota de pé —
  ref: F-019 §3.1/§7, CA-073/074/090, `modules/regimes.md`

- [2026-10-11] [metodologia/regimes] **D-s · `ibcbr_yoy` passa a usar a MÉDIA DOS 3 MESES do
  trimestre, não o nível de fim de período — PROVISÓRIA, aguarda o aval do Edu; SPEC NÃO EDITADA**
  — motivo: `docs/research/metodologia-regimes-macro.md §2` diz, literalmente, **"IBC-Br: média do
  trimestre"**, e a implementação de F-015 lia o último mês. **D-q(e)** registrou a escolha, mas
  mediu o custo errado ("muda os 83 `ibcbr_gap`"); o QA da Onda 2 (lote A, **P1-1**) mediu o custo
  que importa: `max |dif|` **4,2646 pp** em `ibcbr_yoy`, **4,3064 pp** no hiato e **7 dos 67
  trimestres trocando o sinal do hiato** — logo **de quadrante na V1**. Um índice de atividade
  mensal lido num único mês é o nível **daquele mês**, não do trimestre, e carrega o ruído do mês
  para o eixo de crescimento. Impacto medido no rebuild (as duas materializações):
  **(i)** nova régua = média aritmética dos 3 meses, janela `(fim de T-1, fim de T]`, com
  **completude obrigatória** (2 meses → `NULL` com motivo, nunca média parcial);
  **(ii)** padrão de nulos **idêntico** ao anterior (`ibcbr_yoy` 82/83, `ibcbr_gap` 67/83, `2026Q3`
  nulo porque o IBC-Br vai até jul/2026 — 1 de 3 meses);
  **(iii)** os **7** trimestres previstos pelo QA trocam de quadrante, **e só eles**: 2013Q2
  (EST→EXP), 2013Q3 (REC→DES), 2013Q4 (EXP→EST), 2020Q1 (DES→REC), 2023Q3 (EXP→EST), 2024Q1
  (DES→REC), 2025Q2 (DES→REC);
  **(iv)** distribuição V1 `revised` de **EXP 20 · REC 17 · EST 15 · DES 15** para **REC 19 ·
  EXP 19 · EST 16 · DES 13** (CA-080 continua fechando: 4 quadrantes povoados, todos em [10, 35];
  desbalanceamento sobe de 1,33× para 1,46×);
  **(v)** a troca `asof` × `revised` **sobe** de 29,85% (20/67) para **33,33% (22/66)** — não
  "ajustei" nada para passar: o número foi medido e piorou, e é esse que vai ao Comitê;
  **(vi)** `pib_yoy` fica como está (`max |dif| = 8,9e-16`, ruído de float): o PIB do SIDRA já é
  trimestral na fonte, não há o que mediar;
  **(vii)** a V3 de F-021 **não muda em nada** — os 8 vizinhos de `2026Q3`, as distâncias e o
  ranking de ativos são byte-idênticos, porque o eixo de crescimento da V3 é `focus_pib_ano`
  (**D-u**) e nenhuma das 5 features passa pelo IBC-Br.
  **Procedência (`obs = media_3m`):** 3 observações por trimestre e PK `(quarter, column)` admite
  **uma** linha por célula → a escolha registrada é a **última das 3** (`date_obs_max`), igual ao
  que `ACUMULADAS` já fazia, porque é o limite **superior** que torna `date_obs <= quarter_end`
  (e, na `asof`, `date_obs + lag_dias <= quarter_end`) verificável no Parquet. As outras duas são
  derivação determinística da grade; a regra vai em `relatorio_macro.json → medias_no_trimestre` —
  ref: metodologia §2, QA-A P1-1, `macro_quarterly.MEDIAS`/`media_por_trimestre`, D-q(e) (superada)

- [2026-10-11] [regimes] **D-t · ciclo Selic: movimento de `|Δ| >= 0,25 pp` conta como CORTE/ALTA
  (desigualdade NÃO estrita) — PROVISÓRIA, aguarda o aval do Edu; metodologia NÃO EDITADA** —
  motivo: a leitura literal de `metodologia §2` (`< -0,25` / `> +0,25`) punha **7** trimestres com
  `|Δ| = 0,25` **exato** em `NEUTRO`, entre eles **2024Q2 e 2024Q3**, que são cortes reais de 25
  bps do Copom (QA-A **P1-2**). 25 pb é o **menor passo que o Copom dá**: chamá-lo de "parada"
  rotula como pausa justamente o início e o fim dos ciclos — e, dos 30 `NEUTRO` da régua antiga,
  só 23 eram `Δ = 0` de fato. Impacto medido: distribuição de **CORTE 29 · NEUTRO 30 · ALTA 24**
  para **CORTE 34 · NEUTRO 23 · ALTA 26** (os 7 trimestres de borda: 5 viram CORTE, 2 viram ALTA);
  `LIMIAR_SELIC_PP = 0,25` **não muda** (continua no schema), muda só a desigualdade.
  `ciclo_selic` ainda **não é coluna publicada** — mora em `RegimesSchema` e é de F-020, então a
  mudança atinge hoje só a distribuição de `relatorio_macro.json` e a função pública — ref:
  metodologia §2 (V2), QA-A P1-2, `macro_quarterly.ciclo_selic`, CONTRACTS §5.3

- [2026-10-11] [regimes/contrato] **D-u · F-021: o eixo de crescimento da V3 é `focus_pib_ano`
  (substitui `z_ibcbr_gap`), e `regime_v1_neighbor` `nullable=False` fica como está — V3
  RATIFICADA PROVISORIAMENTE pelo orquestrador; dívida de schema registrada** — motivo: duas
  coisas, decididas juntas. **(a) O eixo:** `ibcbr_gap` é nulo em `2026Q3` **por construção** (o
  IBC-Br vai até jul/2026) e `2026Q3` é exatamente o trimestre da pergunta do Comitê — com o hiato
  como feature a V3 **não tem vetor para a pergunta que foi feita**; e o gap é nulo em
  `2006Q1..2009Q3` (D-m), o que tiraria a crise de 2008 do conjunto de vizinhos. Nenhuma das duas
  alternativas resolve `2026Q3` (`min_periods = 8` de D-m recupera 12 trimestres mas não 2026Q3;
  `ibcbr_yoy` sem tendência tem o mesmo problema). `focus_pib_ano` é dado real, 83/83, **sem**
  defasagem de divulgação (metodologia §5.1: "o Focus é o dado limpo") e é o eixo de crescimento da
  V1b na metodologia §2. **(b) O schema:** `RegimeNeighborsSchema.regime_v1_neighbor` é
  `nullable=False` e, por **D-m**, 16 trimestres não têm quadrante V1 — então a tabela de contrato
  (`regime_neighbors.parquet`, 5.500 × 11) perde **4 dos 8** vizinhos de `2026Q3` (Jaccard 0,33
  contra a lente completa). Tornar a coluna anulável é **alteração de schema existente** ⇒ feature
  classe C própria, e **não foi feita**. Decisão: os **dois** artefatos ficam, e **F-022/F-024 leem
  `regime_neighbors_v3.parquet`** (9.692 × 21, 77 referências, lente `mahalanobis`, `k = 8`,
  `somente_passado=False`, `restrito_pos_2016=False`) — regra escrita em `CONTRACTS.md §5` e a
  perda do pool restrito na página de limitações (F-028). Impacto: nenhuma linha de código muda;
  a **dívida** `regime_v1_neighbor nullable` entra em `TODO.md §6` — ref: F-021 §2.1/§3.1/§7.1/§7.2,
  D-m, D-i (mesma classe de decisão), CA-089

- [2026-10-11] [canônico/guardas] **D-v · as três correções dos P1 dos QAs da Onda 2 — ACEITAS pelo
  orquestrador** — motivo e impacto, um a um.
  **(a) QA-A P1-3 (bug de guarda, 8 linhas):** `exigir_series` de F-015 rodava **só** contra
  `raw_series`, então um `alinhado_trimestral` **sem** série exigida fazia o build **concluir em
  silêncio** — a régua reexpressa em `observacoes_de_fim_de_periodo` cobria a ausência, `ipca_12m`
  saía com 83 valores não nulos e `max |dif| = 0,0`, e só o contador de células caía de 1.328 para
  1.245, que nenhum teste afirmava. A feature afirma "todo nível é a célula de F-014": agora
  `exigir_series` roda **também** contra `alinhado_trimestral` e a ausência é
  `BLOQUEADO — FONTE INDISPONÍVEL` (CA-076). Teste negativo:
  `test_build_para_se_o_alinhado_nao_tem_serie_exigida`.
  **(b) QA-A P1-4 (`versao_build` dependia do checkout):** `versao_build` hasheava `read_bytes()`
  cru, então o **mesmo commit** dava `fonte_versao` diferente num checkout CRLF (Windows, sem
  `.gitattributes`) e num LF (CI) — `5cd7bdaf…` contra `54c841bb…` em F-015 —, com **2 dos 7**
  módulos de `MODULOS_DO_MACRO` já em LF no disco. Quebrava o passo 4 do gate da classe D (dataset
  congelado por `sha256` + tag git) e CA-121 entre ambientes **sem que uma célula de dado mudasse**.
  Correção: `normalizar_fim_de_linha` (`\r\n` → `\n`) antes do hash, em
  `build_raw_series.versao_build` — **todos** os `MODULOS_*` da camada canônica herdam, porque
  todos passam por ela. Dois testes: a função e a igualdade CRLF ≡ LF ≡ disco. **Resíduo
  declarado:** `catalogo_sha256` (hash diagnóstico de um arquivo só) **não** foi normalizado — vai
  para `TODO.md §6`.
  **(c) QA-B P1-1 (janela do CDI ≠ caminho do ativo):** a janela do CDI é
  `(quarter_end(T-1), quarter_end(T)]` e o caminho de cada ativo é `(date_obs(T-1), date_obs(T)]`;
  com `ffill = 1` (D-h) as duas diferem de 1 a 3 d.u. em **599 das 1.857** linhas com excesso.
  Viés no `ret_excesso_cdi`: média **0,0185 pp**, p95 0,0984, **máx 0,1575 pp** (média 0,0827 pp
  nas 212 linhas com `ffill = 1`). **O cálculo NÃO foi alterado** — é ~8× menor que o efeito
  razão-vs-subtração (0,139 pp), a cadeia de preços é contínua (`price_ini(T+1) == price_fim(T)` em
  100% dos casos com ffill) e corrigir exigiria reconstruir o CDI por ativo. Virou **limitação
  declarada** em `relatorio_retornos.json → convencoes.janela_do_cdi_vs_caminho_do_ativo` e em
  `docs/wiki/modules/canonical.md` — ref: QA-A P1-3/P1-4, QA-B P1-1, D-h, CA-076, CA-121, §14.7

- [2026-10-11] [contrato] **D-w · `CONTRACTS.md` atualizada com o estado MEDIDO da camada: duas
  materializações de procedência (§3.1), `RegimesV1Schema` e `RegimeNeighborsV3Schema` (§5),
  `FEATURES_V3` 6 declaradas / 5 usadas, e as decisões D-s/D-t — ACEITA pelo orquestrador** —
  motivo: `CONTRACTS.md` descrevia uma camada que deixou de existir em três pontos (uma só tabela
  de procedência macro; nenhum schema de regime; 6 features na V3). Contrato que não descreve o
  que roda é pior que contrato ausente, porque a divergência fica invisível. Impacto: texto, zero
  linha de código; `termos_troca_yoy` continua a 6ª feature **declarada e não usada**, com o motivo
  no dado (100% nula em `macro_quarterly`, G-02 / F-037) — ref: F-018 §2/§9.1, F-019 §3.1,
  F-021 §3.1/§7.5, CONTRACTS §3.1/§5

- [2026-10-11] [organização] **D-x · os paths divergentes do `TODO.md` ficam como estão
  (`apps/pipeline/canonical/` em vez de `apps/pipeline/transform|analysis/`) — ACEITA pelo
  orquestrador** — motivo: `apps/pipeline/analysis/` e `apps/pipeline/transform/` **não existem** na
  árvore; `canonical/` é onde F-013..F-017 moram e de onde `alinhar_series`/`montar_macro` são
  importados. Mover seria `git mv` + imports, zero linha de lógica, e quebraria o histórico de 7
  features por estética. Impacto: 1 linha por feature no `TODO.md` (F-014..F-019, F-021) —
  ref: QA-A §2, F-019 §1/§10.4, F-021 §7.6

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
primeira a enxugar. Quando o Edu avaliar D-a..D-x, o que virar permanente sobe para `CONTRACTS.md` /
ADR e sai daqui; o que virar óbvio se apaga. Nunca apague a linha original de uma decisão avaliada:
troque o marcador por `ACEITA — <quem> em <data>`.*
