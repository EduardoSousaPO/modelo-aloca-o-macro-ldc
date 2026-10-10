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

> ⚠️ **TODAS as 12 linhas abaixo estão marcadas `PROVISÓRIA — aguardando aval de Edu/Alexandre`.**
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

*Documento vivo e deliberadamente pequeno. Se passar de ~120 linhas, promova o que virou permanente
(ADR/SPEC) e apague o que virou óbvio.*
