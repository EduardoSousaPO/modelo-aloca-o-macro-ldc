# estrategia-macro-ldc-dados

Ferramenta interna da **LDC Capital** que monta a base estatística do **modelo de alocação macro
doméstica** e do **dimensionamento da alocação internacional** do Comitê de Alocação. O pipeline extrai,
normaliza e alinha 20 anos (**1T2006 → 3T2026 ≈ 83 trimestres**) de (A) macro brasileiro — PIB/IBC-Br,
IPCA, expectativas do Focus, Selic, taxas de títulos públicos e inclinação da curva de juros —, (B)
desempenho de ativos e subsetores — índices ANBIMA de renda fixa (IMA-B, IRF-M, IMA-S), CDI, índices
amplos e setoriais da B3, IFIX e FII por segmento — e (C) proxies internacionais (S&P 500, MSCI ACWI,
UST, VIX, DXY, PTAX), num **dataset canônico trimestral** sobre o qual se classificam **regimes macro** e
se mede como cada classe de ativo performou em momentos semelhantes.

Não é SaaS, web nem serviço: é um pipeline Python que roda **local**, na máquina do Edu, sem auth,
pagamento, deploy ou cloud. O produto é **descritivo, não preditivo** — confundir os dois é o maior risco
reputacional do projeto. O escopo de origem é o e-mail do Alexandre Kaercher, arquivado em
[`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](docs/product/ESCOPO-EMAIL-ALEXANDRE.md): **fonte de verdade
imutável**. Toda feature se justifica ali; o que estiver fora exige pausa e registro.

## Prazo

**Comitê de Alocação: 2026-10-14 (quarta-feira).** Heatmap para revisão do Edu em **2026-10-13 (terça)**. Publicar
qualquer número para o Comitê é operação **classe D** (revisão humana + dataset congelado + 3 valores por
série conferidos na fonte + linha em `docs/wiki/log.md`).

## Estado atual (2026-10-11)

**Ondas 0 a 3 completas e aprovadas no QA; Onda 4 (métricas regime × ativo, heatmap, ranking, timeline, internacional, limitações e o orquestrador de um comando) IMPLEMENTADA, com o QA rodado e as mudanças aplicadas. Falta: F-027 (notebook, em curso) e F-031 (pacote do Comitê, classe D).**

- Documentação completa: escopo → pesquisa → PRD → SPEC/Anti-SPEC → contratos → TODO (40 features) → PLAN.
- Contratos de dados em `packages/shared/schemas/` (**9** módulos pandera/pydantic + catálogo de
  **138** séries), sempre por **acréscimo**: nenhuma declaração de coluna existente foi alterada
  em nenhuma onda. Espelho legível em `docs/contracts/CONTRACTS.md`.
- **Onda 0 e Onda 1 — 9 features com QA aprovado:** F-001 (infra), F-009 (job diário) e os 7
  extratores F-002..F-008 (ANBIMA IMA, BCB SGS, IBGE SIDRA, Tesouro Direto, API B3, Yahoo/MSCI,
  calendário de dias úteis). QA independente em `docs/plans/qa/` (`ONDA-0-QA.md`, `ONDA-1-QA-A.md`,
  `ONDA-1-QA-B.md`), **0 × P0**; F-004 fica com **D-e pendente do Edu** (dois CAs da SPEC não fecham
  no dado real) e as pendências P1/P2 estão em `TODO.md §6`.
- **Onda 2 (classe C) — as 6 features da camada canônica, com QA aprovado:** **F-013**
  (`raw_series` + catálogo materializado), **F-014** (`alinhado_trimestral`), **F-016** (curva: 11
  séries interpoladas), **F-010** (Focus/Olinda: 5 EntitySets, 197 séries, 150.120 linhas), **F-015**
  (`macro_quarterly` **83 × 42** + `macro_quarterly_provenance` **2.548**) e **F-017**
  (`asset_returns_quarterly` **1.963** linhas, **24** ativos). QA independente em
  `docs/plans/qa/ONDA-2-QA-{A,B}.md`, **0 × P0**, com a revisão numérica da classe C reconstruindo
  as camadas **por fora** e achando **igualdade exata em float64** (4.038 células em F-014; 22
  colunas em F-015; 11 séries × 5.436 datas do CSV bruto em F-016; e validação **externa** do
  breakeven contra a Curva Zero da ANBIMA, a 0,010 bp). Os **6 × P1** levantados foram absorvidos no
  fechamento da Onda 3 (**D-s, D-t, D-v** em `DECISIONS_LOG §2.3`).
- **Onda 3 (classe C) — 3 features com QA aprovado:** **F-018** (regra anti-look-ahead +
  materialização **`asof`**: `macro_quarterly_asof` **83 × 42** + procedência **2.552** com
  `date_obs`/`lag_dias` em todas e **0** células com look-ahead), **F-019** (regimes **V1**,
  quadrantes crescimento × inflação: `regimes_v1{,_asof}` **83 × 18**, 67 classificados e 16
  `INDETERMINADO` **declarados**) e **F-021** (regimes **V3**, vizinhos mais próximos com
  Mahalanobis + Ledoit-Wolf em numpy puro: `regime_neighbors_v3` **9.692 × 21** — **a resposta
  literal ao e-mail**). QA em `docs/plans/qa/ONDA-3-QA.md`: **0 × P0** e **0 divergência numérica**;
  os 5 × P1 eram de declaração e foram aplicados em **D-y**.
- **Onda 4 — 7 features implementadas (QA rodado, mudanças aplicadas):** **F-022** (métricas por
  regime × ativo: **17** métricas em **3** tabelas nomeadas, **120/96/120** células), **F-023**
  (heatmap regime × ativo, **23 × 5** na vista principal, escala divergente derivada e validada),
  **F-024** (a página "em que regime estamos?" × **3** lentes + concordância, **72** linhas),
  **F-025** (timeline dos 83 trimestres sobre IBOV e Selic), **F-026** (internacional: `stress_flag`
  em **20 de 83** trimestres, correlações condicionais e a **faixa** de D6), **F-028** (a página de
  limitações do Comitê) e **F-029** (o orquestrador de **um comando**). QA em
  `docs/plans/qa/ONDA-4-QA.md`: **0 × P0**, **120 células × 17 métricas** reconferidas com
  `max abs dif = 0,0`; os 3 × P1 eram `verify` estourando em Parquet corrompido, o orquestrador sem
  as etapas de F-026/F-024 e o não publicável viajando no dataset congelado — **todos corrigidos**.
  **F-020 (V2) e F-030 foram cortadas da v1**, com justificativa escrita no `TODO.md`.
- **Um comando reconstrói a camada canônica inteira** (F-029):

  ```bash
  python -m apps.pipeline run --offline     # 13 etapas, na ordem, sem rede
  python -m apps.pipeline verify            # recalcula todo sha256 x MANIFEST.json; rc != 0 se divergir
  python -m apps.pipeline freeze --tag comite-2026-10-14
  ```

  **Rebuild final de 2026-10-11: 2 execuções byte-idênticas, 47 artefatos determinísticos,
  `verify` rc 0, `DATASET_SHA256 = fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`.**
- `data/processed/` tem **69 Parquets** reconstruíveis com um comando por fonte: ~219 mil linhas de
  `processed_series` em 51 arquivos, as **11** séries da curva (F-016), as **5** fatias do Focus
  (F-010), o painel do Tesouro Direto (886.300 linhas, 750 `series_id`) e o calendário de dias úteis
  (10.957 dias, 2001→2030). `data/canonical/` tem **48** artefatos conferidos pelo `MANIFEST.json`:
  `raw_series.parquet` (**278.439** linhas, **62** séries, 1979-12-31 → 2026-10-10),
  `series_catalog.parquet` (**138 × 26**), `alinhado_trimestral.parquet` (**4.038**),
  `macro_quarterly.parquet` + a companheira de procedência, `macro_quarterly_asof.parquet` + a dela,
  `asset_returns_quarterly.parquet` (**1.963**, 24 ativos), `regimes_v1{,_asof}.parquet`,
  `regime_neighbors_v3.parquet` e `regime_neighbors.parquet`, as **3** tabelas
  `regime_asset_metrics*`, `internacional_por_regime.parquet` (**54**) e
  `internacional_pesos.parquet` (**624**, marcado **`publicavel: false`** — ver abaixo), **12
  figuras** PNG/SVG + 2 Parquet de dados plotados, as **6** tabelas do Comitê, **10** relatórios de
  build e o `ldc.duckdb` derivado (fora do hash agregado, declarado). `data/raw/` tem o bruto de cada
  fonte com manifesto (`sha256`, URL, hora da coleta) e a janela rolante arquivada pelo job F-009.
  **Nada de `data/` vai para o git** — a fonte de verdade é o script.
- Reprodutível sem rede: `python -m apps.pipeline.extract.<fonte> --offline` reconstrói o Parquet a
  partir do bruto arquivado, byte a byte (verificado em 2 rodadas dos 8 extratores).
- **7 ADRs** (ADR-001..006 em **Proposta**; **ADR-007 Aceita** — Supabase descartado na v1);
  12 substituições de fonte registradas como **provisórias** em
  [`docs/plans/DECISIONS_LOG.md`](docs/plans/DECISIONS_LOG.md).
- CI: **N1, N2 e N3 habilitados** em `.github/workflows/ci.yml` — N2 = `tests/contract` + build do
  canônico a partir das fixtures versionadas + `verify`; N3 = `tests/e2e` + **duas árvores
  independentes** com `diff` do `MANIFEST.json`. Os dois foram executados localmente antes de
  serem escritos (agregado `f9214b8e…`, `verify` rc 0). O passo de `tests/integration` fica
  comentado e nomeado: a pasta está **vazia** e `pytest` nela sairia com código 5.
- **8 decisões de Edu/Alexandre bloqueiam a publicação** (não o desenvolvimento) — ver abaixo; e as
  decisões provisórias das Ondas 1-4 (**D-a..D-af**, com **D-h..D-m**, **D-s/D-t/D-u** e, da Onda
  4, **D-aa (c)** e a ratificação de **D6** à espera de aval) estão tabuladas em
  [`TODO.md §4`](TODO.md). Quatro delas mudam o que se pode afirmar:
  **D-m** (a V1 classifica **67** dos 83 trimestres, não 83, porque o IBC-Br começa em 2003 — a
  crise de 2008 fica fora do eixo de crescimento), **D-o** (unidade: `macro_quarterly` em por cento,
  `asset_returns_quarterly` em fração), **D-s** (o IBC-Br trimestral é a **média dos 3 meses**, como
  a metodologia escreve — **7** trimestres mudam de quadrante) e **D-t** (um movimento de 25 bps na
  Selic é **ciclo**, não parada).
- ⚠️ **Dois achados que vão ao Comitê, e que não são bug de ninguém.** **(1)** Rodando a V1 nas duas
  materializações, **22 de 66 trimestres (33,33%) trocam de rótulo** entre `revised` e `asof` —
  acima dos **25%** que a metodologia e **CA-074** fixam como limite. Pelo critério escrito, a
  leitura **operacional** da V1 ("em que quadrante estamos agora, com o que se sabia na época")
  **não é operacional nesta forma**, e com ela cai a hipótese **H-03** do PRD; a leitura
  **descritiva** continua válida e é o entregável. **(2)** Em `3T2026` a **interseção dos top-5 das
  três lentes é VAZIA**, e sobre as 61 referências comparáveis a concordância V1 × V3 tem **mediana
  0,111** — **nenhuma** referência em 20 anos tem o top-5 idêntico. Com erro-padrão de 2 a 5 pp e
  `n` de 4 a 19, **a ordem do topo não é distinguível de ruído**. Os dois vão à página de limitações
  (F-028) e ao slide, não a nota de pé.
- ⚠️ **Um artefato é construído e NÃO vai ao Comitê:** `internacional_pesos.parquet` (variância
  mínima por regime) está fora desta versão por **Anti-SPEC §10.3.16/§10.5** → F-035. Ele entra no
  `MANIFEST.json` com **`publicavel: false`** e motivo escrito, o `FROZEN.txt` o lista como excluído
  do pacote, e **F-031 lê esse campo** — não uma convenção de nome de arquivo.

## Como configurar o ambiente

```bash
# caminho preferido (uv já instalado nesta máquina)
uv sync --extra dev

# alternativa
python -m venv .venv && .venv\Scripts\activate && pip install -e ".[dev]"

# Jupyter: os Scripts/ do Python global estão fora do PATH — use o módulo
python -m jupyter lab            # ou: uv run python -m jupyter lab

# qualidade
ruff check . && ruff format --check .      # lint + format
pytest tests/unit                          # N1
pytest tests/integration tests/contract    # N2
pytest tests/e2e                           # N3
pytest -m "not network"                    # pula o que toca fonte externa
```

Nenhuma credencial é necessária — todas as fontes do caminho crítico são públicas e gratuitas. Exceção:
**`fred.stlouisfed.org` está bloqueado nesta máquina** (camada de aplicação, 3/3 tentativas) → o bloco
internacional usa Yahoo + MSCI + PTAX (S-09 no `DECISIONS_LOG`).

## Estrutura do repositório

```
AGENTS.md · CLAUDE.md · TODO.md · README.md · pyproject.toml · .gitignore
.github/workflows/ci.yml        ← CI N1 ativo; N2/N3 comentados
apps/pipeline/                  ← common/ · extract/ · canonical/ · transform/ · jobs/
apps/analysis/                  ← notebooks, regimes, figuras           (vazio)
packages/shared/schemas/        ← FONTE DE VERDADE dos contratos (pandera + pydantic, 138 séries)
data/raw/<fonte>/               ← resposta crua da fonte, imutável      (não versionado)
data/processed/                 ← 69 Parquets, frequência nativa        (não versionado)
                                  (inclui curva/ — 11 séries de F-016 — e focus/ — 5 de F-010)
data/canonical/                 ← raw_series · series_catalog · alinhado_trimestral
                                  macro_quarterly (+ _provenance) · asset_returns_quarterly · ldc.duckdb
tests/unit|integration|contract|e2e/
infra/                          ← scripts auxiliares de ambiente
docs/product/                   ← ESCOPO-EMAIL-ALEXANDRE.md (imutável) + PRD.md
docs/research/                  ← fontes-de-dados.md · -RESUMO.md · metodologia-regimes-macro.md
docs/specs/SPEC.md              ← comportamento + Anti-SPEC §10 (sagrada)
docs/contracts/CONTRACTS.md     ← espelho legível dos schemas
docs/plans/                     ← PLAN.md · DECISIONS_LOG.md · skills-manifest.md ·
                                  risk-classification.md · infra-ops.md · prompts-cheatsheet.md ·
                                  checklists/ · feature-contracts/ · _templates/
docs/decisions/adr/             ← ADR-001..006 (em Proposta) + ADR-007 (Aceita)
docs/wiki/                      ← index · log · overview · architecture + modules/ features/
                                  runbooks/ context/   (memória sintetizada entre sessões)
```

**Dados não são versionados.** `data/` é reconstruível e a fonte de verdade é o **script que produz o
dado**, não o arquivo. Dado bruto > 5 MB nunca entra no git. Se um dataset só existe no disco de alguém,
ele não existe.

## Mapa de documentos (ordem de leitura)

| # | Documento | O que responde |
|---|---|---|
| 1 | [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](docs/product/ESCOPO-EMAIL-ALEXANDRE.md) | o que foi pedido — **imutável** |
| 2 | [`docs/research/`](docs/research/) | qual fonte tem cada série, endpoint, formato, cobertura, pegadinhas |
| 3 | [`docs/product/PRD.md`](docs/product/PRD.md) | o quê e por quê (52 RFs, personas, riscos) |
| 4 | [`docs/specs/SPEC.md`](docs/specs/SPEC.md) | comportamento verificável (52 RFs → 128 CAs) + **Anti-SPEC §10** |
| 5 | [`docs/contracts/CONTRACTS.md`](docs/contracts/CONTRACTS.md) | espelho legível de [`packages/shared/schemas/`](packages/shared/schemas/) |
| 6 | [`TODO.md`](TODO.md) | estado vivo: 40 features classificadas A/B/C/D + Feature Contract inline |
| 7 | [`docs/plans/PLAN.md`](docs/plans/PLAN.md) | ondas de execução até 2026-10-14 + dependências + lista de corte |
| 8 | [`docs/decisions/adr/`](docs/decisions/adr/) | decisões arquiteturais (ADR-001..006 em Proposta; ADR-007 Aceita) |
| 9 | [`docs/plans/DECISIONS_LOG.md`](docs/plans/DECISIONS_LOG.md) | substituições de fonte e decisões operacionais |
| 10 | [`docs/wiki/index.md`](docs/wiki/index.md) | memória sintetizada — **primeira leitura de qualquer agente** |

Contrato com agentes de IA: [`AGENTS.md`](AGENTS.md) (papéis, A/B/C/D, autonomia/pausa, Validation Mode)
e [`CLAUDE.md`](CLAUDE.md) (convenções Python, camadas de dados, o que nunca fazer).

## Fluxo de execução (Harness)

Detalhe em [`docs/plans/PLAN.md`](docs/plans/PLAN.md); uma onda só começa com a anterior verde no CI.

| Onda | Quando | O que entrega |
|---|---|---|
| **0** | sáb 10/10 | job diário de arquivamento ANBIMA (janela rolante de ~20 d.u.) · infra de extração · `DECISIONS_LOG` |
| **1** | dom 11/10 | todos os extratores de esforço baixo em paralelo (ANBIMA S3, SGS, SIDRA, Tesouro, B3, Yahoo/MSCI, calendário) + Focus, FRED-fallback, Teva |
| **2** | dom/seg 11-12/10 | camada canônica — `raw_series`, alinhamento trimestral, curva, retornos, `macro_quarterly` (**classe C**) · **fechada e aprovada no QA** |
| **3** | ter 13/10 | anti-look-ahead/`asof` + regimes V1 (quadrantes) + V3 (vizinhos) (**classe C**) · **fechada e aprovada no QA: F-018, F-019, F-021** · **F-020 (V2) cortada da v1** |
| **4** | ter 13/10 | métricas regime × ativo, heatmap, timeline, ranking, internacional, limitações, orquestrador · **implementada; QA rodado** — **marco de revisão humana do Edu** |
| **5** | qua 14/10 | notebook de entrega (**F-027, em curso**) e **pacote do Comitê (F-031, classe D)** |

Ciclo por feature: pegar o item do `TODO.md` → confirmar classe e Definition of Ready → checar contra o
e-mail de escopo → teste falhando sobre fixture gravada → implementar → CI no nível da classe → PR com
matriz de validação e **evidência de dados** (linhas, min/max de data, % de nulos, 3 valores conferidos na
fonte; classe C: diff numérico vs. a versão anterior do canônico) → merge → `TODO.md` + `docs/wiki/log.md`.

## Decisões pendentes (gate de publicação)

8 decisões de **Edu/Alexandre** — detalhe, recomendação e features afetadas em
**[`TODO.md §4`](TODO.md)**. Responder "aceito a recomendação" destrava e muda os ADRs para Aceito.

> **Estado em 2026-10-10 (noite):** o Edu autorizou **desenvolver** as ondas sobre os padrões provisórios
> destas 8 decisões e do ADR-006 (aceite formal pendente); as 8 seguem abertas e o único gate que
> permanece duro é a **publicação** — nenhum número vai ao Comitê sem **ADR-001 aceito** (`AGENTS.md §14`).
> Nesta data também: repo GitHub conectado (`main`) e **Supabase descartado na v1** (ADR-007, Aceita).

| # | Decisão | ADR |
|---|---|---|
| **D1** | qual lente de regime é a oficial do Comitê (V1 / V2 / V3 / as três) | ADR-001 |
| **D3** | eixo inflação da V1: nível vs. meta ou aceleração do IPCA 12m | ADR-001 |
| **D5** | métrica primária do heatmap: nominal, excesso sobre CDI ou real | ADR-002 |
| **D6** | internacional: piso estrutural, 100% tático por regime ou híbrido | ADR-003 |
| **D12** | setoriais da B3 e FII segmentado entram no pacote mínimo? | ADR-005 |
| **L1** | aceitar IFIX com janela própria 2011-2026 (metade da janela) | ADR-005 |
| **L2** | autorizar FII segmentado via Teva (2019+, provedor privado sem licença explícita) | ADR-005 |
| **L4** | contratar o ANBIMA Feed (≈R$ 686–8.238/mês) ou aceitar a curva via Tesouro Direto | ADR-004 |

**Não bloqueado** (desenvolvimento): extração, camada canônica, figuras e tabelas — F-001 a F-011,
F-013 a F-019, F-021 a F-026, F-028, F-029. **Bloqueado de verdade:** a **publicação** (F-031,
classe D) e qualquer número de `internacional_pesos.parquet`, que exige ADR-003 aceito **e**
autorização escrita sobre a Anti-SPEC.

## Licença

Interno — LDC Capital. Não distribuir; dados de terceiros (Teva, B3, ANBIMA, MSCI) não são
redistribuíveis (riscos R19/R20 em `docs/research/fontes-de-dados.md`).
