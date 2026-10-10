# Log — estrategia-macro-ldc-dados

> **Histórico cronológico vivo.** Complementa `git log` (que é granular demais) e `DECISIONS_LOG.md` (que é só decisão).
>
> **Aqui entra:** ingest de fontes brutas, releases, bug fixes notáveis, validações de produção, mudanças de escopo, marcos.
> **Aqui NÃO entra:** o "porquê" de cada decisão (vai para `DECISIONS_LOG.md` ou ADR).
>
> **Quem escreve:** o agente em todo `/wiki ingest` e ao fim de feature/fast-fix relevante.
> **Quem lê:** todo agente no início de sessão; e ao tentar entender comportamento estranho.
>
> **Tamanho-alvo:** ≤ 200 linhas. Se passar, rode `/wiki repair` para arquivar entradas antigas em `wiki/log-archive-YYYY-MM.md`.

---

## Formato

Uma linha por evento. Frase curta com data ISO, tipo, contexto, link com fonte (PR / ADR / arquivo / F-NNN).

```
- [YYYY-MM-DD HH:MM] [TIPO] descrição curta — ref: F-NNN / PR #NN / commit / fonte bruta
```

**Tipos válidos** (use para grep):

- `KICKOFF` — criação/estruturação inicial do projeto
- `INGEST` — fonte bruta processada (print, log, transcript, resposta de outro agente)
- `SOURCE` — nova fonte de dados mapeada, extrator criado ou fonte substituída (ref: DECISIONS_LOG)
- `DATASET` — dataset canônico reconstruído / congelado (com hash + intervalo de datas)
- `RELEASE` — versão liberada (com SHA + ambiente)
- `BUGFIX` — bug corrigido (com gravidade + classe)
- `RUNBOOK` — runbook criado/atualizado
- `DECISION` — referência a entrada nova no DECISIONS_LOG ou ADR
- `RECLASSIFY` — feature mudou de classe durante execução
- `BLOQUEADO` — agente retornou BLOQUEADO; resolvido em… 
- `VALIDATION` — validação de publicação (smoke do pacote, dataset congelado, reprodutibilidade)
- `WIKI` — manutenção da própria wiki (lint, repair, mover página)
- `HOUSEKEEPING` — manutenção do repo fora da wiki (deps, README, docs de plano)
- `HARNESS` — marco de fase do harness (kickoff, research, PRD, SDD, agents-protocol)
- `SDD` / `PRD` — marcos de documentação (usados nas entradas de 2026-10-10)

---

## 2026 — entradas atuais

> Entradas mais novas no topo.

- [2026-10-10] [HOUSEKEEPING] `pyproject.toml` corrigido — `openpyxl>=3.1` (os `.xls` da ANBIMA são XLSX), `lxml>=5.0` (`read_html` na Curva Zero) e `matplotlib>=3.8` (heatmap RF-033) adicionados às deps principais; `duckdb` mantido por **ADR-006**; `seaborn` dispensado (nenhum doc exige); `yfinance` segue como única dep pendente. Arquivo revalidado com `tomllib` — ref: `pyproject.toml`, `docs/plans/skills-manifest.md §4`
- [2026-10-10] [HOUSEKEEPING] `skills-manifest.md` corrigido — a afirmação de que "o diretório não é repo git / `git init` pendente" era **falsa**: o repo existe desde o kickoff (7 commits, `143d936` → `5a36035`). Ajustados §2 (linha do `git`, deps presentes), §4 (setup com as deps já corrigidas), §5 (DuckDB resolvido por ADR-006), RO-8 e §7 — ref: `docs/plans/skills-manifest.md`
- [2026-10-10] [DECISION] **F-032 concluída** — `docs/plans/DECISIONS_LOG.md` criado a partir do template com **12 substituições de fonte** (S-01 a S-12: ETTJ ANBIMA→Tesouro Direto, swaps SGS mortos em 2019, IMA via S3, "DataFit" inexistente, IFIX 2011+, ICON/IMOB janela própria, FII via Teva 2019+, FRED→Yahoo/MSCI/PTAX, S&P 500, EMBI+ inativo desde 30/07/2024, dívida bruta→DLSP) + 5 decisões operacionais. **Todas provisórias, aguardando aval de Edu/Alexandre** — ref: `docs/plans/DECISIONS_LOG.md`, `TODO.md §3`, RF-052/CA-128
- [2026-10-10] [HOUSEKEEPING] `README.md` reescrito para o estado real (149 linhas): o que é o projeto, prazo 2026-10-14, estrutura de pastas conferida no disco, setup (`uv sync --extra dev`; jupyter via `python -m jupyter lab`), ondas do PLAN, mapa de 10 documentos, as 8 decisões pendentes com link ao `TODO.md §4` e o estado "harness estruturado; nenhum extrator implementado" — ref: `README.md`
- [2026-10-10] [WIKI] `/wiki lint` → **amarelo**: `modules/` e `runbooks/` prometidos no índice estavam **vazios**; `index.md` não linkava SPEC, CONTRACTS, PLAN, ADRs, skills-manifest nem DECISIONS_LOG (que não existia); `overview.md §8` ainda dizia "próximo passo: `/SDD-avancado`" (já feito) e marcava a SPEC como "a criar"; `index.md` com 103 linhas (alvo ≤ 80). Nenhuma página órfã; único link quebrado era o placeholder `ADR-NNN-...` de `runbooks/_TEMPLATE.md` (esperado) — ref: lint 2026-10-10
- [2026-10-10] [WIKI] `/wiki repair` aplicado — criadas 7 páginas em `modules/` (`sgs`, `sidra`, `anbima`, `b3`, `internacional`, `canonical`, `regimes`, ≤ 39 linhas cada) com propósito, séries/RFs, fonte primária e fallback, armadilhas da pesquisa e features do TODO; criados `runbooks/reconstruir-dataset.md` (60) e `runbooks/fonte-fora-do-ar.md` (60); `index.md` reduzido a 78 linhas com todos os links conferidos; `overview.md §8` e seção de links atualizadas — ref: `docs/wiki/`
2026-10-10 | CONSOLIDAÇÃO | inconsistências pós-agents-protocol corrigidas (PLAN dias da semana, branch main, risk-classification e templates adaptados a dados, TODO §1 populado, yfinance)
2026-10-10 | HARNESS | estruturação completa: kickoff → research → PRD → SDD → agents-protocol; 0 código de pipeline; aguardando 8 decisões
2026-10-10 | SDD | SPEC + Anti-SPEC + contratos pandera/pydantic + TODO com 40 features + 6 ADRs propostos
2026-10-10 | PRD | docs/product/PRD.md v1 gerado em modo autônomo a partir do e-mail + research; 8 decisões pendentes
2026-10-10 | KICKOFF | estrutura Harness v3.2 criada; e-mail de escopo arquivado

- [2026-10-10] [DECISION] `/SDD-avancado` em **modo autônomo**: `docs/specs/SPEC.md` v1.0 (52 RFs → **128 CAs**, Anti-SPEC §10 com 29 proibições + §11 com as 8 decisões provisórias), `docs/contracts/CONTRACTS.md`, contratos em `packages/shared/schemas/` (6 módulos pandera/pydantic + catálogo de **132 séries**: 99 `ok`, 8 `a_confirmar`, 10 descontinuadas, 14 descartadas, 1 paga), `TODO.md` com **40 features** (1 A · 21 B · 17 C · 1 D; 32 no pacote mínimo), `docs/plans/PLAN.md` (ondas sáb→ter) e **ADR-001..006 em status Proposta** — ref: `docs/specs/SPEC.md`, `docs/decisions/adr/`
- [2026-10-10] [WIKI] `wiki/architecture.md` atualizado para refletir SPEC v1.0 + schemas (147 linhas); `docs/plans/risk-classification.md` ganhou os exemplos concretos deste projeto por classe A/B/C/D — ref: `docs/wiki/architecture.md`
- [2026-10-10] [INGEST] PRD v1.0 gerado em **modo autônomo** por `/consultor-prd` (sem discovery humano): 52 RFs, 10 RNFs, 15 premissas marcadas `[PREMISSA]`, 8 riscos priorizados; **8 decisões bloqueiam implementação** (D1, D3, D5, D6, D12, L1, L2, L4) e foram registradas em `TODO.md §4` — ref: `docs/product/PRD.md`, `docs/research/fontes-de-dados.md`, `docs/research/metodologia-regimes-macro.md`
- [2026-10-10] [WIKI] `wiki/overview.md` reescrito para refletir o PRD v1.0 (síntese, sem duplicar) — ref: `docs/wiki/overview.md`
- [2026-10-10] [KICKOFF] estrutura Harness v3.2 criada e adaptada a projeto de dados/quant (AGENTS/CLAUDE/TODO/README/CI Python, `apps/pipeline` + `apps/analysis`, `packages/shared/schemas`, `data/raw|processed|canonical`) — ref: `docs/wiki/index.md`, `AGENTS.md`
- [2026-10-10] [INGEST] e-mail de escopo do Alexandre Kaercher transcrito e arquivado como fonte de verdade imutável — ref: `docs/product/ESCOPO-EMAIL-ALEXANDRE.md`
- [2026-10-10] [WIKI] wiki inicial populada (index, overview) — pesquisa de fontes em andamento em `docs/research/` por agentes paralelos — ref: `docs/wiki/overview.md`

---

## Entradas anteriores

*(vazio)*

---

## Regras

1. **Uma linha por evento.** Se precisa de parágrafo, vira ADR ou runbook.
2. **Sempre com referência verificável.** Sem ref, não é log — é opinião.
3. **Nunca apague entradas com ref a PR/ADR.** Se ficou irrelevante, mova para `log-archive-YYYY-MM.md`.
4. **Não duplique DECISIONS_LOG aqui.** Linka para a linha lá (`ref: DECISIONS_LOG L42`).
5. **`/wiki ingest` cria a entrada automaticamente** — não escreva manualmente se vai usar a skill.

---

*Este arquivo é o `git log` humano. Curto, indexável, confiável.*
