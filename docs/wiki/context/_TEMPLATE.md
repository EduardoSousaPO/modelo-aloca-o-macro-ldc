# Context Pack — [F-NNN ou TAREFA]

> **Pacote de contexto reutilizável** para uma tarefa ativa. Reduz alucinação no início e permite que **outro subagente Opus** continue de onde o anterior parou (`AGENTS.md §22`).
>
> **Onde vive:** `docs/wiki/context/<F-NNN-slug>.md`.
> **Tempo de vida:** enquanto a feature/tarefa estiver aberta. Após merge, deletar (resumo vai para `wiki/features/F-NNN.md` se relevante).
>
> **Quem cria:** `/wiki context F-NNN` (ou manual em fast-fix).
> **Quem lê:** o agente que vai pegar a tarefa.

**Tarefa:** [F-NNN — nome curto]
**Classe:** [A | B | C | D]
**Modo:** [Fast Fix | Standard | Deep Work | Production | Reorg]
**Criado em:** YYYY-MM-DD HH:MM
**Última atualização:** YYYY-MM-DD HH:MM
**Agente atual:** [Fable (orquestrador) | subagente Opus | Claude Code]

---

## 1. O que estamos fazendo

> 1-3 frases. Objetivo da tarefa em linguagem humana.

`...`

## 2. Por que (motivação)

> O bug que dói, o cliente que pediu, o roadmap que exige. Curto.

`...`

## 3. Estado atual

> O que já foi feito **nesta tarefa**. Não duplique git log; resuma.

- [x] Schema `pandera` identificado em `packages/shared/schemas/raw_series.py`
- [x] Fixture da fonte gravada em `tests/fixtures/sgs/ipca.json`
- [x] Teste falhando para CA-001
- [ ] Implementação de `apps/pipeline/extract/sgs.py`
- [ ] Evidência de dados (linhas, `min`/`max`, % de nulos, 3 valores conferidos na fonte)

**Branch:** `feat/<slug>` (commit atual: `<sha>`)

## 4. Arquivos relevantes (mapa rápido)

| Arquivo | Por que importa nesta tarefa |
|---|---|
| `packages/shared/schemas/raw_series.py` | schema `pandera` canônico |
| `apps/pipeline/extract/sgs.py` | implementação principal |
| `tests/unit/test_sgs.py` · `tests/fixtures/sgs/` | testes obrigatórios + fixture gravada |
| `docs/research/fontes-de-dados.md §X` | pegadinhas da fonte (ler **antes** de codar) |
| `docs/specs/SPEC.md §3.1` | RF-001 e RF-002 |
| `wiki/modules/sgs.md` | módulo da fonte |
| `docs/decisions/adr/ADR-006` | armazenamento e convenção de alinhamento |

## 5. Restrições desta tarefa

- Anti-SPEC relevante: §10.1.1 não inventar/interpolar dado · §10.1.5 HTTP 200 ≠ sucesso · §10.4.23 nenhuma rede em teste de CI.
- Arquivos proibidos: `docs/specs/SPEC.md`, `docs/product/*`, `docs/research/*`, schema canônico já existente.
- Decisões operacionais aplicáveis (DECISIONS_LOG): L12, L18.

## 6. Próximos passos concretos

> Em ordem. O agente que pegar pode executar.

1. Rodar `pytest tests/unit/test_sgs.py` e confirmar que CA-001 falha do jeito esperado.
2. Implementar `apps/pipeline/extract/sgs.py` usando o schema de `packages/shared/schemas/`.
3. Atualizar matriz de validação + evidência de dados no Feature Contract.
4. Rodar o CI local do nível alvo (`ruff check . && ruff format --check . && pytest tests/unit`; N2 inclui `pytest tests/integration tests/contract`).
5. Abrir PR + Prompt 3 (QA Validation Mode de dados).

## 7. Decisões abertas (precisa humano)

> Se vazio, agente pode continuar sozinho conforme regras de autonomia (AGENTS.md §9).

- [ ] (vazio)

## 8. Handoff entre agentes

> Para passar de Claude → Codex → Cursor sem perder contexto.

- **De:** [subagente Opus / Claude Code] (sessão YYYY-MM-DD HH:MM)
- **Para:** [próximo subagente Opus | Fable | a sessão de amanhã]
- **Última ação:** [ex: gravei a fixture da fonte, abri branch, escrevi teste falhando]
- **O que NÃO fiz e o próximo deveria evitar:** [ex: não conferi o valor-canário na fonte; não mexi no schema canônico — escopo proíbe]

---

## Links

- Feature Contract → bloco inline em [`TODO.md`](../../../TODO.md) ou [`docs/plans/feature-contracts/F-NNN.md`](../../plans/feature-contracts/)
- Wiki módulo → [`wiki/modules/<modulo>.md`](../modules/)
- SPEC → [`docs/specs/SPEC.md`](../../specs/SPEC.md)

---

*Este pack é descartável. Quando a tarefa fechar, mover resumo curto (≤ 5 linhas) para `wiki/features/F-NNN.md` e deletar este arquivo.*
