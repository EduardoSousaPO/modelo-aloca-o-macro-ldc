# Guia — Como agrupar features em ondas

> Referência auxiliar do `/agents-protocol`. Use apenas se o projeto tem > 6 features ou dependências não triviais.

---

## Princípios

1. **Unidade mínima é feature**, não task. Se você está escrevendo "criar migration X" ou "adicionar botão Y" como item de onda, desça um nível — agrupe como parte de uma feature maior.
2. **Cada onda deve entregar valor observável.** Se no final da onda não há nada novo que o usuário (ou o desenvolvedor) consegue **ver ou usar**, a onda é contábil, não útil.
3. **Entre 3 e 6 features por onda.** Menos que 3 → pode ir junto da onda seguinte. Mais que 6 → quebre.
4. **Duração-alvo: 1 a 5 dias por onda** em solo. Ondas maiores viram projetos mágicos que nunca terminam.

---

## Heurística de agrupamento

Responda "sim" a todas as perguntas antes de colocar duas features na mesma onda:

- As duas compartilham o mesmo objetivo de usuário/negócio?
- Elas tocam os mesmos arquivos de contrato ou o mesmo módulo principal?
- Concluir uma sem a outra deixa o sistema em estado consistente? (Se "não", elas são uma feature só — não duas.)
- A ordem entre elas é flexível ou é uma sequência rígida? Se rígida, marque a dependência.

---

## Exemplo canônico — 3 ondas

```
Onda 1 — Fundação
  F-001 Monorepo + CI
  F-002 Health check
  F-003 Auth: login
  F-004 Auth: signup
  F-005 Dashboard vazio
  → saída: "subo conta, logo, vejo dashboard vazio"

Onda 2 — Core
  F-006 Criar [entidade principal]
  F-007 Listar [entidade]
  F-008 Editar/deletar [entidade]
  F-009 Busca e filtro
  → saída: "faço CRUD do domínio ponta a ponta"

Onda 3 — Polimento
  F-010 Export CSV
  F-011 Observabilidade (Sentry + logs)
  F-012 Página de billing (stub)
  → saída: "beta privado liberado, erros monitorados"
```

---

## Antipadrões de ondas

- **Onda de "setup + tudo"**: colocar infra + auth + domínio em uma única onda de 15 itens. Divida em pelo menos duas.
- **Onda invisível**: "refactor interno" sem nada observável. Se é refactor, costure dentro de uma onda de feature.
- **Onda dependente de decisão**: "F-020 depende de decidirmos framework de pagamento". Isso é ADR, não onda.
- **Onda que nunca fecha**: definir critério de saída vago ("produto melhor"). Sempre escreva uma afirmação verificável.

---

## Relação com o TODO.md

- Se criar `PLAN.md` com ondas, o `TODO.md` ainda é a fonte viva. A seção "Em andamento" do `TODO.md` deve espelhar a **onda atual**.
- Ao fechar uma onda, marque-a como `(fechada, SHA: xxx)` no `PLAN.md` e mova o bloco da seção "Em andamento" do `TODO.md` para "Concluído".

---

## Quando re-planejar

Re-planeje ondas quando:

- Uma feature nova apareceu e muda a ordem das próximas 2+ ondas.
- Uma dependência externa mudou (ex: fornecedor trocado).
- Estimativa errou por > 50% em uma onda inteira.

Não re-planeje a cada sprint/semana — isso vira burocracia. O plano existe para orientar, não para ser recriado.
