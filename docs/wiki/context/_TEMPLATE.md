# Context Pack — [F-NNN ou TAREFA]

> **Pacote de contexto reutilizável** para uma tarefa ativa. Reduz alucinação no início e permite que **outro agente** (Codex/Cursor) continue de onde Claude parou.
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
**Agente atual:** [Claude Code | Codex | Cursor]

---

## 1. O que estamos fazendo

> 1-3 frases. Objetivo da tarefa em linguagem humana.

`...`

## 2. Por que (motivação)

> O bug que dói, o cliente que pediu, o roadmap que exige. Curto.

`...`

## 3. Estado atual

> O que já foi feito **nesta tarefa**. Não duplique git log; resuma.

- [x] Schema Zod criado em `packages/shared/types/auth.ts`
- [x] Teste falhando para CA-001
- [ ] Implementação de `apps/api/src/auth/login.ts`
- [ ] Smoke test em staging

**Branch:** `feat/<slug>` (commit atual: `<sha>`)

## 4. Arquivos relevantes (mapa rápido)

| Arquivo | Por que importa nesta tarefa |
|---|---|
| `packages/shared/types/auth.ts` | schema Zod canônico |
| `apps/api/src/auth/login.ts` | implementação principal |
| `tests/integration/auth.login.test.ts` | testes obrigatórios |
| `docs/specs/SPEC.md §3.1` | RF-001 e RF-002 |
| `wiki/modules/auth.md` | módulo de auth |
| `docs/decisions/adr/ADR-002` | cookie httpOnly |

## 5. Restrições desta tarefa

- Anti-SPEC relevante: NÃO logar senhas/tokens; NÃO armazenar senha em texto claro.
- Arquivos proibidos: `docs/specs/SPEC.md`, tabela `users` (migration).
- Decisões operacionais aplicáveis (DECISIONS_LOG): L12, L18.

## 6. Próximos passos concretos

> Em ordem. O agente que pegar pode executar.

1. Rodar `npm test -- auth.login` e confirmar que CA-001 falha do jeito esperado.
2. Implementar `apps/api/src/auth/login.ts` usando schema de `auth.ts`.
3. Atualizar matriz de validação no Feature Contract.
4. Rodar CI N2 local (`npm run ci:n2`).
5. Abrir PR + Prompt 3 (QA Validation Mode).

## 7. Decisões abertas (precisa humano)

> Se vazio, agente pode continuar sozinho conforme regras de autonomia (AGENTS.md §9).

- [ ] (vazio)

## 8. Handoff entre agentes

> Para passar de Claude → Codex → Cursor sem perder contexto.

- **De:** Claude Code (sessão YYYY-MM-DD HH:MM)
- **Para:** [Codex | Cursor | Claude Code amanhã]
- **Última ação:** [ex: criei Zod schema, abri branch, escrevi teste falhando]
- **O que NÃO fiz e o próximo deveria evitar:** [ex: não tentei subir em staging — tem env faltando; não mexi em `users.ts` — escopo proíbe]

---

## Links

- Feature Contract → bloco inline em [`TODO.md`](../../../TODO.md) ou [`docs/plans/feature-contracts/F-NNN.md`](../../plans/feature-contracts/)
- Wiki módulo → [`wiki/modules/<modulo>.md`](../modules/)
- SPEC → [`docs/specs/SPEC.md`](../../specs/SPEC.md)

---

*Este pack é descartável. Quando a tarefa fechar, mover resumo curto (≤ 5 linhas) para `wiki/features/F-NNN.md` e deletar este arquivo.*
