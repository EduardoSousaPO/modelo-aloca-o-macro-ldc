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

## Estado atual (2026-10-10)

**Camada de extração pronta e conferida; camada canônica não começou.**

- Documentação completa: escopo → pesquisa → PRD → SPEC/Anti-SPEC → contratos → TODO (40 features) → PLAN.
- Contratos de dados em `packages/shared/schemas/` (7 módulos pandera/pydantic + catálogo de **134**
  séries).
- **9 features implementadas:** F-001 (infra) e F-009 (job diário) com **QA aprovado**; F-002..F-008
  (ANBIMA IMA, BCB SGS, IBGE SIDRA, Tesouro Direto, API B3, Yahoo/MSCI, calendário de dias úteis)
  **implementadas e aguardando QA** (`docs/plans/qa/ONDA-1-QA.md`). A camada de transformação nasceu
  com `apps/pipeline/transform/cambio.py`; `apps/analysis/` segue vazio e `data/canonical/` também —
  é tudo **classe C**, de F-013 em diante.
- `data/processed/` tem **53 Parquets** reconstruíveis com um comando por fonte: ~219 mil linhas de
  `processed_series` em 51 arquivos, mais o painel do Tesouro Direto (886.300 linhas, 750 `series_id`)
  e o calendário de dias úteis (10.957 dias, 2001→2030). `data/raw/` tem o bruto de cada fonte com
  manifesto (`sha256`, URL, hora da coleta) e a janela rolante arquivada pelo job F-009. **Nada de
  `data/` vai para o git** — a fonte de verdade é o script.
- Reprodutível sem rede: `python -m apps.pipeline.extract.<fonte> --offline` reconstrói o Parquet a
  partir do bruto arquivado, byte a byte (verificado em 2 rodadas dos 8 extratores).
- **7 ADRs** (ADR-001..006 em **Proposta**; **ADR-007 Aceita** — Supabase descartado na v1);
  12 substituições de fonte registradas como **provisórias** em
  [`docs/plans/DECISIONS_LOG.md`](docs/plans/DECISIONS_LOG.md).
- CI: N1 (lint + unit) configurado em `.github/workflows/ci.yml`; N2/N3 comentados até existirem testes.
- **8 decisões de Edu/Alexandre bloqueiam o início** — ver abaixo.

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
apps/pipeline/                  ← common/ · extract/ · transform/ · jobs/
apps/analysis/                  ← notebooks, regimes, figuras           (vazio)
packages/shared/schemas/        ← FONTE DE VERDADE dos contratos (pandera + pydantic, 134 séries)
data/raw/<fonte>/               ← resposta crua da fonte, imutável      (não versionado)
data/processed/                 ← 53 Parquets, frequência nativa        (não versionado)
data/canonical/                 ← dataset-base trimestral alinhado      (não versionado)
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
| **2** | dom/seg 11-12/10 | camada canônica — `raw_series`, alinhamento trimestral, curva, retornos, `macro_quarterly`, anti-look-ahead (**classe C**) |
| **3** | ter 13/10 | regimes V1 (quadrantes) + V3 (vizinhos) + V2 (ciclo Selic) e métricas por regime × ativo (**classe C**) |
| **4** | ter 13/10 | heatmap, timeline, ranking, internacional, orquestrador — **marco de revisão humana do Edu** |
| **5** | qua 14/10 | limitações, notebook de entrega e **pacote do Comitê (classe D)** |

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

**Não bloqueado** (pode começar agora): extração e camada canônica — F-001 a F-011, F-013 a F-015,
F-017, F-018, F-029, F-030.

## Licença

Interno — LDC Capital. Não distribuir; dados de terceiros (Teva, B3, ANBIMA, MSCI) não são
redistribuíveis (riscos R19/R20 em `docs/research/fontes-de-dados.md`).
