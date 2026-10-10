# Architecture — estrategia-macro-ldc-dados

> **Arquitetura técnica viva.** Síntese do SPEC + realidade do código.
>
> **Fonte de verdade:** `docs/specs/SPEC.md` + `packages/shared/schemas/`.
> Esta página existe para que qualquer agente entenda a topologia em < 5 min sem ler todo o SPEC.

**Última revisão:** 2026-10-10
**Versão do SPEC refletida:** nenhuma — SPEC ainda não existe (a ser gerado por `/SDD-avancado`).
**Status:** esqueleto do kickoff. As seções marcadas `[a definir]` são preenchidas após o SPEC.

---

## 1. Topologia em 1 diagrama (ASCII)

```
  FONTES PÚBLICAS                    EXTRAÇÃO            NORMALIZAÇÃO         CAMADA CANÔNICA        ANÁLISE
  ───────────────                    ─────────           ────────────         ───────────────        ───────
  BCB / SGS  (IPCA 433, Selic 11,
             IBC-Br, CDI 12)   ──┐
  BCB / Focus (expectativas)     ──┤
  IBGE / SIDRA (IPCA, PIB)       ──┤    apps/pipeline/      apps/pipeline/      data/canonical/      apps/analysis/
  ANBIMA (IMA-B, IRF-M, ETTJ)    ──┼──►  extract    ──►     transform    ──►   dataset-base    ──►  regimes macro
  B3 (IBOV, IDIV, SMLL, INDX,    ──┤    data/raw/<fonte>/   data/processed/     trimestral           + performance
     ICON, IMAT, IEE, IMOB,        │    (cru, imutável)     (limpo, tipado,     (macro + ativos      por classe/setor
     IFNC, IFIX)                 ──┤                         freq. nativa)       alinhados)           + relatório
  Tesouro Direto                 ──┘          │                   │                   │                   │
  [internacional: a definir]     ──┘          └── pandera ────────┴── pandera ────────┘                   ▼
                                                    (packages/shared/schemas/)                      Comitê (classe D)
```

Fluxo unidirecional. Cada seta é um comando reprodutível: rodar duas vezes a partir do mesmo `raw/`
produz o mesmo output (hash igual). Nada volta para a esquerda.

## 2. Stack

| Camada | Tech | Versão | Notas |
|---|---|---|---|
| Linguagem | Python | ≥ 3.11 | ambiente local via `uv` (preferido) ou `venv` |
| Dados em memória | pandas + pyarrow | pandas ≥ 2.2 | `DatetimeIndex`; trimestre = fim de período |
| Extração HTTP | requests / httpx | — | escolha final por fonte; registrar em ADR |
| Contratos | pydantic (config/payload) + pandera (DataFrame) | pydantic ≥ 2.7 | fonte de verdade em `packages/shared/schemas/` |
| Armazenamento local | Parquet e/ou DuckDB | duckdb ≥ 1.0 | decisão pendente de ADR-001 |
| Análise | Jupyter | — | notebooks em `apps/analysis/`, sem lógica de negócio |
| Qualidade | pytest + ruff | pytest ≥ 8.2 | N1 = ruff + pytest unit |
| Execução | local (máquina do Edu) | — | **sem** servidor, deploy, auth ou cloud |

## 3. Módulos

> Cada módulo ganha sua página em `wiki/modules/` quando passar a existir de verdade.
> **Não criar módulo vazio.** Hoje nenhum está implementado.

| Módulo (previsto) | Responsabilidade | Página |
|---|---|---|
| `sgs` | séries do BCB (IPCA 433, Selic 11, CDI 12, IBC-Br) + Focus | `modules/sgs.md` |
| `sidra` | IPCA e PIB do IBGE via SIDRA | `modules/sidra.md` |
| `anbima` | IMA-B / IRF-M / ETTJ (inclinação da curva) | `modules/anbima.md` |
| `b3` | índices amplos, setoriais e IFIX | `modules/b3.md` |
| `tesouro` | taxas de títulos públicos | `modules/tesouro.md` |
| `internacional` | proxy para o tamanho da alocação internacional — **escopo a definir** | `modules/internacional.md` |
| `canonical` | alinhamento temporal, agregação trimestral, cálculo de retornos | `modules/canonical.md` |
| `regimes` | classificação de regimes macro + performance por regime | `modules/regimes.md` |

`canonical` e `regimes` são o coração do risco: tudo que entra neles é **classe C** (ver `AGENTS.md §2`).

## 4. Fronteiras (boundaries)

Onde a validação de schema **deve** estar:

- **Saída de cada extrator** (`apps/pipeline/extract/*`) → schema pandera da forma crua esperada.
- **Entrada e saída de `data/canonical/`** → schema pandera do dataset-base. Obrigatório, sem exceção.
- **Config e env** (`.env`, parâmetros de janela/frequência) → modelo pydantic.
- **Payload de resposta das APIs** (SGS, SIDRA) → modelo pydantic antes de virar DataFrame.

Regra: se vai documentar um contrato em `docs/contracts/CONTRACTS.md`, **primeiro** crie o schema em
`packages/shared/schemas/`. O CONTRACTS.md é espelho legível, não fonte.

## 5. Decisões arquiteturais (ADRs ativos)

| ADR | Decisão | Status |
|---|---|---|
| ADR-001 | Armazenamento local: DuckDB vs. Parquet puro | **pendente** |
| ADR-002 | Cliente HTTP: requests vs. httpx (retry/backoff, cache de resposta) | **pendente** |
| ADR-003 | Convenção de período: fim de trimestre, data de referência vs. data de divulgação (lag) | **pendente** |

→ Documentos completos em [`docs/decisions/adr/`](../decisions/adr/).
Trocas de fonte e convenções operacionais vão para [`DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md), não para ADR.

## 6. Restrições arquiteturais ativas (base da Anti-SPEC)

- **NÃO inventar dado.** Lacuna sem substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`.
- **NÃO inventar colunas de DataFrame** fora de `packages/shared/schemas/`.
- **NÃO editar `data/` à mão.** Todo dado vem de script reprodutível e versionado.
- **NÃO commitar dado** (bruto > 5 MB, `*.parquet`, `*.duckdb`) nem credencial.
- **NÃO chamar fonte externa em teste** — só fixture gravada; rede apenas sob `@pytest.mark.network`.
- **NÃO alterar schema canônico, alinhamento temporal ou cálculo de retorno** sem Feature Contract classe C
  com diff numérico vs. versão anterior.

## 7. O que NÃO faz parte da arquitetura

> Coisas que parecem mas não são. Reduz alucinação do agente.

- Não há frontend, API HTTP própria, login, sessão, usuário ou multi-tenant.
- Não há banco de dados servidor, Supabase, RLS ou migration — armazenamento é arquivo local.
- Não há deploy, Vercel, Docker em produção nem ambiente de staging.
- Não há pagamento, Stripe, webhook ou e-mail transacional.
- Não há fila, cron ou orquestrador (Airflow/Dagster): o pipeline roda por comando manual.
- Não há cache distribuído; cache, se houver, é arquivo local em `data/raw/`.
- Não há TypeScript, Node, npm, Zod ou ESLint neste repo.

---

## Links

- SPEC completo (a criar) → [`docs/specs/SPEC.md`](../specs/SPEC.md)
- Escopo de origem → [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
- Pesquisa de fontes → [`docs/research/`](../research/)
- Contratos → [`docs/contracts/CONTRACTS.md`](../contracts/CONTRACTS.md)
- Realidade do código → [`docs/plans/CURRENT_REALITY.md`](../plans/CURRENT_REALITY.md)
- Decisões → [`docs/decisions/adr/`](../decisions/adr/) · [`DECISIONS_LOG.md`](../plans/DECISIONS_LOG.md)

---

*Atualize: ao adicionar/remover módulo, ao trocar lib core, ao aprovar ADR, ao mudar o schema canônico.
Não atualize por refactor interno de módulo.*
