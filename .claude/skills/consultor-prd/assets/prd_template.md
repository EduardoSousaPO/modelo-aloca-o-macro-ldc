# PRD — [Nome do Projeto]

> Product Requirements Document — o quê e por quê.
> Versão: 1.0 — Data: YYYY-MM-DD — Autor: [Nome]

---

## 1. Visão Geral

### Problema
<!-- Problema REAL, não sintoma. "Não conseguem decidir com dados porque métricas estão em 5 ferramentas" > "preciso de um dashboard". -->

### Solução proposta
<!-- Em 2-3 frases: o que será construído e como resolve. -->

### Objetivo principal
<!-- Uma frase mensurável. Se não pode ser medido, refine. -->

---

## 2. Contexto e motivação

- **Situação atual:**
- **Por que agora:**
- **Impacto esperado:**

---

## 3. Usuários e personas

### Persona principal
- **Quem é:**
- **O que precisa:**
- **Frustração atual:**
- **Frequência de uso:**
- **Contexto de uso:** desktop / mobile / campo

### Anti-persona
<!-- Quem o produto NÃO atende — previne scope creep. -->

---

## 4. Funcionalidades (alto nível)

> Mapeie em features macro. Detalhes vêm na SPEC.

| # | Feature | Prioridade | Justificativa |
|---|---|---|---|
| F-001 | [ex: Login com e-mail/senha] | Alta | Pré-requisito de qualquer feature autenticada |
| F-002 | [ex: Dashboard de métricas] | Alta | Principal jornada de valor |
| F-003 | [ex: Exportar relatório PDF] | Média | Demanda recorrente dos usuários |

---

## 5. Fora de escopo (v1)

> Tão importante quanto o que está dentro. Previne scope creep.

- [ex: App mobile]
- [ex: Integração Stripe]
- [ex: i18n]

---

## 6. Métricas de sucesso

| Métrica | Meta | Como medir |
|---|---|---|
| [ex: Taxa de conclusão do onboarding] | > 80% | Analytics + funnel |
| [ex: p95 API] | < 500ms | APM |
| [ex: NPS após 30 dias] | > 40 | Survey in-app |

---

## 7. Restrições e premissas

### Restrições (não-negociáveis)
- [ex: LGPD — dados não podem sair do Brasil]
- [ex: Orçamento infra ≤ R$ 200/mês]

### Premissas (assumidas como verdadeiras)
- [ex: Usuário tem internet estável]
- [ex: API externa Y mantém compatibilidade]

---

## 8. Dependências externas

| Dependência | Tipo | Criticidade | Fallback |
|---|---|---|---|
| [ex: Google OAuth] | Serviço | Alta | e-mail/senha |
| [ex: Resend] | Serviço | Média | SendGrid |

---

## 9. Jornadas de alto nível

### Jornada 1 — [Primeiro acesso]
1. Usuário descobre via [canal]
2. [Ação]
3. [Resultado]
4. Momento "aha": [quando]

---

## 10. Hipóteses, gaps e decisões pendentes

### Hipóteses críticas
- H-001 — [o que estamos assumindo sem validar]

### Gaps (o que não sabemos)
- G-001 — [pergunta em aberto]

### Decisões pendentes
- D-001 — [precisa de resposta do stakeholder]

---

## 11. Aprovação

- [ ] Problema real identificado
- [ ] Personas definidas
- [ ] Features priorizadas
- [ ] Fora de escopo explícito
- [ ] Métricas de sucesso mensuráveis
- [ ] Restrições documentadas
- [ ] Gaps e decisões pendentes listados
- [ ] PRD aprovado pelo responsável

---

*Próximo passo: criar `docs/specs/SPEC.md` via `/SDD-avancado`.*
