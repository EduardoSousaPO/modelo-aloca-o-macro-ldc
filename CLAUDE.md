# CLAUDE.md — Instruções específicas do Claude Code (Harness v3.2)

> Projeto de **dados/quant** da LDC Capital: pipeline Python de séries macro + índices de ativos BR para o
> modelo de alocação do Comitê. Roda **local**, sem auth/pagamento/deploy. Tudo que vale para qualquer
> agente está em `AGENTS.md`. **Máximo: ~140 linhas.**

---

## 1. Leitura inicial obrigatória (nesta ordem)

1. `docs/wiki/index.md` → mapa da memória sintetizada
2. `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` → **fonte de verdade do escopo** (imutável)
3. `TODO.md` → estado + Feature Contract do item ativo
4. `AGENTS.md` → papéis, A/B/C/D, autonomia/pausa, wiki, Fast Fix

Depois, conforme a tarefa: `docs/research/` (pesquisa de fontes e metodologia, feita em paralelo por
outros agentes), `docs/specs/SPEC.md`, `packages/shared/schemas/`, `docs/wiki/context/<F-NNN>.md`,
`docs/wiki/log.md` (últimos 7 dias), `git status && git log --oneline -5`. Ao final: reporte fase + classe
da feature + DoR completa? + pode continuar autônomo?

---

## 2. Mapa rápido

- `packages/shared/schemas/` — **source of truth** dos contratos de dados (Pydantic + pandera);
  `docs/contracts/CONTRACTS.md` — espelho legível dos schemas
- `apps/pipeline/` — extração, transformação, carga; `apps/analysis/` — notebooks, regimes, relatórios
- `docs/plans/risk-classification.md` — referência quente A/B/C/D; `docs/plans/_templates/` —
  FEATURE-CONTRACT, VALIDATION-MATRIX, CURRENT_REALITY, DECISIONS_LOG
- `docs/wiki/runbooks/` — reconstruir dataset, série fora do ar, fechar relatório do Comitê

---

## 3. Convenções Python

- **Ambiente:** `uv sync` (preferido) ou `venv` local + `pip install -e .[dev]`. Nunca instalar global;
  nunca instalar sem pedir.
- **Lint/format:** `ruff check .` e `ruff format --check .` (sem ESLint/Prettier/tsc neste repo).
- **Testes:** `pytest`, um por critério de aceite. Fonte externa só via fixture gravada em
  `tests/fixtures/`; rede apenas sob `@pytest.mark.network` (não roda no CI).
- **Contratos:** `pydantic` para config/env/payload; `pandera` para schema de DataFrame. Todo DataFrame que
  entra ou sai de `data/canonical/` passa por schema pandera.
- **Type hints** em toda função pública. Datas em ISO-8601. Trimestre = **fim de período**, salvo decisão
  em `DECISIONS_LOG.md`. **Notebooks** não contêm lógica de negócio — importam de `apps/pipeline/` e vão
  para o commit com outputs limpos.

```bash
ruff check . && ruff format --check .                  # lint
pytest tests/unit                                       # N1
pytest tests/integration tests/contract                 # N2
pytest tests/e2e                                        # N3  (-m "not network" pula rede)
```

---

## 4. Camadas de dados

| Camada | Onde | O que é |
|---|---|---|
| **Bruto** | `data/raw/<fonte>/` | resposta crua da fonte (JSON/CSV/XLS), **imutável**, 1 subpasta por fonte (`sgs/`, `sidra/`, `anbima/`, `b3/`) |
| **Processado** | `data/processed/` | limpo, tipado e validado por fonte — ainda na frequência nativa |
| **Canônico** | `data/canonical/` | dataset-base trimestral alinhado (macro + ativos), insumo único da análise |

**Regras:**
- `data/` é **reconstruível**. A fonte de verdade é o script que produz o dado, não o arquivo.
- **Nunca commitar dado bruto > 5 MB.** Use `.gitignore` + script reprodutível: o dataset tem de ser
  regenerável com um comando, a partir de zero. Nenhuma edição manual em `data/` — só via script
  versionado em `apps/pipeline/`.
- Sem dado inventado: nada de interpolação, estimativa ou valor "plausível" para fechar série. Lacuna sem
  substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`. Dado sintético só em fixture, nomeado como tal.

---

## 5. Checagem de escopo (fazer sempre, antes de codar)

Toda feature se justifica em `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` — janela de **20 anos**,
frequência **trimestral**, blocos **A** (macro: PIB/IBC-Br, IPCA, Focus, Selic, títulos, ETTJ),
**B** (ativos: IMA-B, IRF-M, CDI, setoriais B3, IFIX) e **C** (proxy internacional).

- Item fora desses blocos → **pausa** e registre a proposta; não implemente por conta.
- Fonte pedida indisponível/paga → proponha substituto e registre em `docs/plans/DECISIONS_LOG.md` (fonte
  pedida, fonte usada, por quê, impacto na comparabilidade). O Alexandre autorizou ajustes — mas a
  substituição precisa ficar registrada, não silenciosa.
- **Prazo duro: Comitê de Alocação em 2026-10-14.** Em dúvida entre perfeição e série entregue e conferida,
  entregue a conferida e registre a dívida no `TODO.md`.

---

## 6. O que NUNCA fazer neste projeto

- Editar `ESCOPO-EMAIL-ALEXANDRE.md`, `PRD.md`, `SPEC.md` ou Anti-SPEC sem autorização humana.
- Apagar, mover ou sobrescrever arquivo de outro agente em `docs/research/`.
- Commitar `data/raw/`, `data/processed/`, `*.parquet`, `*.duckdb`, `.env` ou credencial.
- Inventar número, interpolar sem documentar, ou misturar dado real e sintético sem coluna de origem.
- Alterar schema canônico, alinhamento temporal ou cálculo de retorno sem Feature Contract classe C.
- Mandar resultado para o Alexandre/Comitê sem passar por classe D (revisão humana + dataset congelado).
- Aprovar PR sem matriz de validação preenchida (B/C/D), com CI vermelho, ou desabilitar teste / usar
  `.skip` ou `xfail` sem ADR.
- Criar pasta `scripts/` na raiz, `state/`, `handoffs/` ou arquivos JSON de estado.

---

## 7. Quando pausar e pedir confirmação

- A feature crescer além do Feature Contract, precisar de arquivo fora da lista permitida, ou a classe
  estimada era A/B e virou C/D (toca camada canônica, credencial ou entregável do Comitê).
- Duas fontes divergem materialmente para a mesma série, ou a série não cobre os 20 anos e seria
  necessário emendar fontes diferentes.
- DoR do próximo item estiver incompleta, ou houver conflito entre docs e código.

Regras completas em `AGENTS.md §9`.

---

## 8. Atalhos de delegação

- **Bug urgente:** `/fast-fix` (só A/B sem camada canônica/credencial/entregável; escala sozinho se virar
  C/D). **Vários problemas de uma vez:** `/triage-bugs`.
- **Implementar feature:** Prompt 2 — valida DoR, cria Feature Contract se B/C/D, testa antes, implementa.
- **Revisar PR:** Prompt 3 (Validation Mode de dados — `AGENTS.md §15`); devolve **APROVADO /
  MUDANÇAS_SOLICITADAS / BLOQUEADO**.
- **Wiki:** `/wiki ingest` (print/log/resposta de API colada), `/wiki context F-NNN` (handoff entre
  subagentes), `/wiki lint` → `/wiki repair`.
- **Investigar bug de dado:** primeiro reproduza com um teste falhando sobre fixture; só depois corrija.

---

## 9. Matriz de validação e continuidade

Para B/C/D, ao final do Prompt 3, preencha a matriz `CA | teste | tipo | status | evidência` — e lembre que,
em projeto de dados, teste verde **não basta**. A evidência inclui: log do pytest, nº de linhas e min/max de
data, % de nulos nas colunas críticas, **3 valores conferidos contra a fonte original** e, em classe C, diff
numérico vs. a versão anterior do canônico. Sem isso → `MUDANÇAS_SOLICITADAS`.

Antes de fechar a sessão, rode `/wiki context <F-NNN>` para a tarefa ativa. O próximo subagente Opus abre
`AGENTS.md` + `wiki/index.md` + `wiki/context/<F-NNN>.md` + o e-mail de escopo e continua (`AGENTS.md §22`).

---

*Atualize este arquivo se mudar comandos, paths ou camadas de dados.*
