# Metodologia SDD-avancado (Harness Solo)

> Referência teórica. A skill `SDD-avancado` aplica isso na prática.

---

## Fundamentação

SDD (Spec-Driven Development) coloca a especificação formal como artefato primário de engenharia. Código, testes e documentação são derivados. O ciclo tradicional "código → documentação" é invertido: "spec → código".

No Harness Solo, isso se especializa em três pilares:

1. **PRD** responde "o quê e por quê" — consumido por pessoas.
2. **SPEC + Anti-SPEC** define o comportamento verificável do sistema — consumido por agentes de IA e testes.
3. **Contratos como código** (`packages/shared/types/`) define as fronteiras entre módulos — consumido pelo runtime.

---

## Por que contratos como código (Zod)?

### Problema no v2 tradicional
`CONTRACTS.md` era o documento primário. Agentes liam markdown, implementavam em TypeScript. O drift era inevitável: mudava o código, esquecia de atualizar o markdown; mudava o markdown, esquecia de propagar para o código.

### Solução no Solo
O schema Zod **é** o contrato. O markdown é derivado. Implicações:

- **Runtime validation automática**: `ApiSuccess(LoginResponse).parse(body)` valida na hora.
- **Types derivados sem esforço**: `type LoginResponse = z.infer<typeof LoginResponse>`.
- **Drift impossível**: se o schema muda, o código quebra no typecheck.
- **Revisão cruzada simples**: PR que altera contrato sem atualizar schema é rejeitado no CI (tests quebram).

### Como usar o `CONTRACTS.md` então?

Como espelho legível para humanos. Leitura rápida da arquitetura de endpoints, regras de evolução, padrões de erro. Não é consumido por nenhum agente como fonte.

---

## Anti-SPEC — por que é obrigatória

Agentes de IA alucinam e expandem escopo. Uma feature descrita apenas pelo positivo ("O sistema deve enviar e-mail de boas-vindas") abre brecha para o agente adicionar notificação push, SMS, webhook e outros canais "só por via das dúvidas".

A Anti-SPEC fecha essa brecha:

- **Fora desta versão** — features inteiras que NÃO entram no v1.
- **Comportamentos proibidos** — mesmo que pareçam convenientes (ex: "NÃO logar senhas").
- **Padrões a evitar** — decisões técnicas já rejeitadas (ex: "NÃO usar polling").

Quando o agente for implementar uma feature, ele deve cruzar com a Anti-SPEC antes. Qualquer conflito → para e pergunta ao humano.

---

## Rastreabilidade RF → feature → PR

No Harness Solo a cadeia é:

```
PRD (problema/valor)
  └─> SPEC (RF-NNN verificável)
         └─> TODO.md (F-NNN com CA-NNN)
                └─> Branch feat/<slug>  →  commit(s)  →  PR  →  merge
                        └─> git blame mostra RF/F no commit message
```

Campo obrigatório em commits/PR:
- Mensagem: `feat(auth): login PKCE (F-003, RF-001)`
- Corpo do PR: lista de CAs atendidos com evidência (nome do teste).

Isso elimina a necessidade do campo JSON `spec_refs` em `TASKS.md` do v2 tradicional — a rastreabilidade fica no histórico do git + tabela na seção 9 do SPEC.

---

## Quando PLAN.md é necessário

Crie `docs/plans/PLAN.md` somente se:

- **> 8 features** no backlog.
- **Dependências cruzadas** não-triviais (F-007 precisa de F-004 e F-005).
- **Ondas com critério de saída** (ex: "Onda 1 só acaba quando smoke test da jornada principal passa em staging").

Para projetos pequenos, o `TODO.md` ordenado já comunica a sequência.

---

## ADRs — quando vale a pena

Crie ADR para:

- Escolhas com trade-off real (stack, arquitetura, banco, auth provider).
- Decisões que impactam estrutura de pastas ou deploy.
- Decisões que "parecem óbvias hoje mas em 6 meses ninguém lembra por quê".

NÃO crie ADR para:
- Trivialidades (escolher lodash vs ramda).
- Convenções de código (vão em `AGENTS.md` ou no linter).
- Algo que muda toda sprint (vai em `PLAN.md`/`TODO.md`).

Formato: `docs/decisions/adr/ADR-NNN-slug-curto.md` usando o template.

---

## Context engineering no fluxo Solo

Cada documento é projetado para entrar no contexto do agente **em momentos específicos**:

| Momento | Agente lê |
|---|---|
| Ao começar uma feature | `TODO.md` (item) + `docs/specs/SPEC.md` (RFs cobertas) + `packages/shared/types/*.ts` (contratos relevantes) |
| Ao abrir PR | diff + `CONTRACTS.md` (se mudou contrato) + `docs/specs/SPEC.md#<secao-anti-spec>` |
| Ao debugar | `docs/decisions/adr/` (por que foi assim?) |

O AGENTS.md (≤150 linhas) cabe inteiro no contexto sempre. PRD/SPEC entram sob demanda. `state/` não existe, então não há poluição.

---

## Anti-padrões

- **Escrever contratos só em markdown**: drift garantido. Use Zod primeiro.
- **Spec sem Anti-SPEC**: agente alucina features. Anti-SPEC obrigatória.
- **ADR para tudo**: ruído. Use só quando há trade-off real.
- **TASKS atômicas estilo v2**: overhead para solo. Use features com critérios de aceite.
- **Estado em JSON**: sem time para coordenar, só agrega fricção. `TODO.md` + git já dá rastreabilidade.
