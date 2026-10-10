# Checklist de entrega por feature (v3.1)

> Referência consultada pelo Claude Code ao finalizar uma feature, antes de fazer merge ou abrir PR. A granularidade depende da classe A/B/C/D.

---

## Antes de começar (Feed Forward)

- [ ] Li o item no `TODO.md` (RFs + CAs + dependências + Feature Contract inline).
- [ ] Confirmei a classe A/B/C/D (se mudou, reclassifiquei e atualizei o Feature Contract).
- [ ] Validei a Definition of Ready — se incompleta, pausei e resolvi antes.
- [ ] Para B/C/D, Feature Contract está presente (inline ou em `docs/plans/feature-contracts/`).
- [ ] Li as seções relevantes do `SPEC.md` + Anti-SPEC.
- [ ] Verifiquei `packages/shared/types/` — se faltam tipos, vou adicionar **antes** de implementar.
- [ ] Criei branch `feat/<slug>` (classe A pode ir em `main` direto).

---

## Durante a implementação

- [ ] Escrevi teste falhando para cada CA **antes** da implementação.
- [ ] Implementação usa exclusivamente tipos de `packages/shared/types/` — sem interfaces paralelas.
- [ ] Só alterei arquivos listados em "podem ser alterados" no Feature Contract. Fora da lista → pausei.
- [ ] Cruzei com `SPEC.md §6 (Anti-SPEC)` — nada proibido foi introduzido.
- [ ] Commits atômicos referenciando o TODO (`feat(auth): login PKCE (TODO #3)`).

---

## Antes de abrir PR / merge — por classe

### Classe A
- [ ] `npm run lint && npm run typecheck && npm test` verde.
- [ ] Teste cobre o CA.

### Classe B
- [ ] Tudo de A +
- [ ] Feature Contract preenchido + matriz de validação com status em todos CAs.
- [ ] `CONTRACTS.md` atualizado se contratos mudaram.

### Classe C
- [ ] Tudo de B +
- [ ] Integration + contract tests verdes.
- [ ] Build verde.
- [ ] Anti-SPEC verificada explicitamente no Prompt 3 (lista de itens relevantes marcada).
- [ ] ADR criado se houve decisão arquitetural ou dependência nova.

### Classe D
- [ ] Tudo de C +
- [ ] `docs/plans/cursor-brief.md` com seção Rollback preenchida.
- [ ] Staging validado (log/print anexado ao PR).
- [ ] Smoke test pós-deploy planejado e executado.
- [ ] Feature flag configurada se altera contrato público.
- [ ] Backup plan descrito se migration é destrutiva.

---

## No PR

- [ ] Título claro: `feat(<escopo>): <resumo curto>`.
- [ ] Corpo segue `assets/pr-description-template.md`.
- [ ] Ligação com item do `TODO.md` explícita.
- [ ] Matriz de validação anexada (B/C/D).
- [ ] CI do GitHub Actions verde no nível correspondente (N1/N2/N3).
- [ ] Autorrevisão feita (Prompt 3 — **APROVADO** com evidência).

---

## Após merge

- [ ] `TODO.md` atualizado: item movido para "Concluído" com SHA/PR.
- [ ] Branch deletada (local e remoto).
- [ ] Se fechou uma onda: marquei no `PLAN.md`.
- [ ] Bugs/ideias surgidos registrados no `TODO.md`.
- [ ] Classe D: smoke test pós-deploy em produção confirmado.

---

## Sinais de alerta — pare e repense

- PR com > 800 linhas → quebre em dois.
- Teste cobrindo > 1 CA de uma vez → fragmente.
- Precisou editar `docs/product/PRD.md` ou `docs/specs/SPEC.md` sem autorização → pare.
- CI vermelho e pensou em desabilitar teste → não. Arrume.
- Feature cresceu → volte ao `TODO.md`, reclassifique, talvez divida.
- Classe B começou a tocar banco/auth/env → reclassifique para C ou D **antes** de continuar.
- Cursor Agent pedido para editar código de `apps/` ou `packages/` → repasse ao Claude Code.
