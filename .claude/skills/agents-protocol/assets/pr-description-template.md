# PR Description Template

> Cole como corpo do PR. Mantenha curto. Se o PR precisa de mais explicação que isto, provavelmente deveria ser quebrado em dois.

---

## Resumo

[1–2 frases: o quê mudou e por quê.]

Referências:
- Feature: F-NNN — [nome no TODO.md]
- SPEC: RF-NNN ([link relativo, se houver âncora])
- Contratos afetados: `packages/shared/types/[arquivo].ts` ([sim/não])

---

## O que foi feito

- [mudança observável 1]
- [mudança observável 2]
- [mudança observável 3]

---

## Critérios de aceite (evidências)

- [ ] CA-NNN: [descrição] — coberto por `tests/[caminho]/[arquivo].test.ts`
- [ ] CA-NNN: [descrição] — coberto por `tests/[caminho]/[arquivo].test.ts`

---

## Contratos (se aplicável)

- [ ] Nenhum contrato foi alterado, **OU**
- [ ] Contratos alterados refletidos em `CONTRACTS.md`:
  - [schema/tipo + resumo da mudança]

---

## Anti-SPEC

- [ ] Verificado — nada listado em SPEC §6 foi introduzido.

---

## Infra (se aplicável)

- [ ] Sem mudanças de infra, **OU**
- [ ] Migration aplicada via Cursor Agent (tarefa N do `cursor-brief.md`) — confirmada em staging.
- [ ] Envs novas adicionadas no Vercel (preview + produção).

---

## Checklist final

- [ ] `npm run lint` verde
- [ ] `npm run typecheck` verde
- [ ] `npm test` verde
- [ ] CI do GitHub Actions verde
- [ ] `TODO.md` atualizado com PR/SHA
