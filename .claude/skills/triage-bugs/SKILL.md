---
name: triage-bugs
description: >
  Triagem em lote de bugs reportados (clientes, usuários, equipe). Recebe uma lista colada de bugs em texto livre e devolve, em < 5 minutos: classificação A/B/C/D por bug, modo recomendado (fast-fix | standard | deep-work | production), prioridade (urgência × impacto × esforço), atualização estruturada do TODO.md §5, criação de runbook se bug recorrente, e plano de ataque para o dia. Use SEMPRE que o usuário disser: "triagem de bugs", "triar esses bugs", "recebi N bugs do cliente", "bugs do dia", "tenho uma lista de bugs", "tem vários bugs aberto", "preciso priorizar bugs", "qual bug atacar primeiro", "inbox de bugs", ou colar uma lista de 2+ bugs sem pedir fix imediato.
---

# /triage-bugs — Harness v3.2 · Bug Triage em Lote

Você ativou o **Triage Bugs**. Esta skill resolve a realidade real do dev solo: o cliente envia 5 bugs em uma manhã e você precisa decidir **o que atacar agora, o que vai pro backlog, o que vira fast-fix, o que precisa de Feature Contract**, sem virar reunião com você mesmo.

> **Tempo-alvo:** ≤ 5 minutos do "colei a lista" ao "vou começar pelo bug #2 via /fast-fix, depois #4 standard, #1 e #3 backlog, #5 escala produção".

---

## Quando usar

- Cliente / usuário / equipe enviaram **2 ou mais bugs** na mesma janela.
- Você precisa decidir **a ordem** e **o modo** de cada um.
- Você tem **menos de 1 dia útil** disponível e precisa caber o que dá.

## Quando NÃO usar

- 1 bug só → vá direto para `/fast-fix` (ou `Prompt 2` se classe C/D).
- Bug que você ainda **não sabe se é bug** → use `/wiki ingest` primeiro (registra a fonte) e investigue depois.
- Refatoração / feature pedida pelo cliente disfarçada de bug → não é bug; vira feature no backlog (não use esta skill).

---

## Processo (Prompt 4 — embutido)

Cole no Claude Code junto com a lista de bugs:

```
[TRIAGE BUGS — HARNESS v3.2]

Lista de bugs (texto livre, 1 por bloco — pode ser cópia de Slack, e-mail, GitHub, WhatsApp):

<<<
[BUG 1] login da Maria não funciona, ela tenta entrar e fica em loop
[BUG 2] cor do botão "Salvar" está errada na tela de perfil (azul, era pra ser verde)
[BUG 3] export de PDF está demorando 30s para 1000 linhas, antes era 5s
[BUG 4] cliente João disse que o webhook do Stripe não confirmou o pagamento dele
[BUG 5] menu mobile sumiu no Safari iOS
>>>

Tempo disponível hoje: [ex: 4 horas | 1 dia útil | só fim de tarde]
Prioridade declarada pelo usuário (se houve): [ex: BUG 4 é P0 — é dinheiro real | "pra mim todos" = sem prioridade declarada]

Execute, NA ORDEM:

1. SCREEN — 60s
   - Para cada bug, leia wiki/runbooks/ — algum cobre? (anote)
   - Leia wiki/log.md últimos 30 dias — algum bug é recorrência? (anote)
   - Leia TODO.md §5 — algum bug já está listado? (anote)

2. CLASSIFICAÇÃO POR BUG
   Para cada bug, devolva:
   - ID interno: BUG-001, BUG-002, ... (ou reusar ID existente se já estiver no TODO)
   - Frase curta normalizada (sem grito do cliente)
   - Repro estimada: "tenho" / "preciso pedir mais info" / "óbvia pelo contexto"
   - Classe A/B/C/D (use risk-classification.md, regra "em dúvida, suba")
   - Domínios tocados: [auth | payment | billing | webhook | dados sensíveis | ui | layout | performance | infra | env | deploy | banco | rls | jobs | outro]
   - Modo recomendado: [fast-fix | standard | deep-work | production | NÃO É BUG]
   - Recorrência: [primeira vez | já vi N vezes — runbook em wiki/runbooks/X.md ou criar]

3. PRIORIDADE — matriz urgência × impacto × esforço
   Para cada bug:
   - Urgência: [P0 imediato | P1 hoje | P2 esta semana | P3 backlog]
   - Impacto: [crítico (dinheiro/dados) | alto (bloqueia uso) | médio (atrito) | baixo (cosmético)]
   - Esforço estimado: [< 30 min | 30 min - 2 h | 2 h - 1 dia | > 1 dia]
   - Score = (urgência) × (impacto) ÷ (esforço)

4. PLANO DE ATAQUE PARA HOJE
   Dado o tempo disponível:
   - Lista ordenada de QUAIS bugs cabem hoje, em qual ordem.
   - Para cada um: comando exato (ex: "rodar /fast-fix com BUG-002").
   - Resto vai para backlog ordenado (não jogue tudo aleatoriamente).

5. ATUALIZAR TODO.md §5
   - Acrescente os bugs novos com formato:
     | ID | Descrição | Repro | Classe | Domínio | Urgência | Impacto | Esforço | Modo | Status | Notas |
     | BUG-NNN | ... | ... | C | auth | P0 | crítico | < 30min | standard | TRIADO | runbook? recorrência? |
   - Não duplique bugs já listados — só atualize colunas.

6. WIKI MEMORY
   - 1 linha em wiki/log.md tipo [INGEST]:
     - [YYYY-MM-DD HH:MM] [INGEST] triagem de N bugs (M novos, K já listados) — plano: <bugs-do-dia> | backlog: <resto> — ref: TODO.md
   - Para cada bug com recorrência ≥ 2: criar/atualizar wiki/runbooks/bug-<slug>.md (stub se ainda sem causa).

7. ESCALATION CHECKS
   - Algum bug é classe D? → reportar SEPARADAMENTE: precisa Production mode (cursor-brief + rollback + staging).
   - Algum bug requer mudança de PRD/SPEC/Anti-SPEC? → reportar como pausa para humano.
   - Algum bug indica vulnerabilidade ativa de auth/dados? → reportar como P0-emergência (mesmo que tempo do usuário não permita: humano decide).

Responda EXATAMENTE neste formato:

TRIAGE — YYYY-MM-DD HH:MM

| ID | Bug (curto) | Classe | Domínio | Urgência | Impacto | Esforço | Modo | Recorrência | Score |
| BUG-NNN | ... | ... | ... | ... | ... | ... | ... | ... | ... |

PLANO DE HOJE (caber em [tempo disponível]):
1. [BUG-NNN] — [comando] — [tempo estimado]
2. [BUG-NNN] — [comando] — [tempo estimado]
3. ...

BACKLOG (ordenado, não cabe hoje):
- [BUG-NNN] — [motivo de adiar]
- ...

ESCALATIONS (precisam atenção humana antes de eu tocar):
- [BUG-NNN] — [motivo: classe D / mudança SPEC / vulnerabilidade / ...]

WIKI ATUALIZAÇÕES:
- TODO.md §5: N linhas adicionadas/atualizadas
- wiki/log.md: 1 linha [INGEST]
- wiki/runbooks/: <stubs criados ou "nenhum">

PRÓXIMA AÇÃO IMEDIATA:
→ [comando exato para começar agora]

Regras:
- Se algum bug envolve auth/payment/dados sensíveis e tempo declarado é "só fim de tarde": MARCAR como P0 e pedir reprorização ao humano antes de começar.
- Se a lista tem ≥ 8 bugs: avisar que solo dev não consome > 5-7 contextos no mesmo dia sem perda de qualidade; sugerir partir em 2 sessões.
- Se algum item da lista NÃO é bug (é feature pedida) → marcar como "NÃO É BUG — abrir como feature em TODO §2 Backlog".
- Nunca começar fix automaticamente após triage — sempre devolver o plano e esperar o usuário disparar.
```

---

## Saídas típicas

### Caso 1 — Lista de 5 bugs, 4h disponíveis

```
TRIAGE — 2026-05-08 09:30

| ID | Bug | Classe | Domínio | Urg | Imp | Esf | Modo | Rec | Score |
| BUG-001 | login Maria em loop | C | auth | P0 | crítico | 2h | standard | 1ª | 8 |
| BUG-002 | cor botão Salvar errada | A | ui | P3 | baixo | 5min | fast-fix | 1ª | 1 |
| BUG-003 | export PDF lento (30s) | B | performance | P2 | médio | 1h | standard | 1ª | 4 |
| BUG-004 | webhook Stripe não confirmou João | D | payment+webhook | P0 | crítico | 1d | production | 1ª | 9 |
| BUG-005 | menu mobile sumiu Safari iOS | B | ui | P1 | alto | 1h | fast-fix→standard | 1ª | 5 |

PLANO DE HOJE (4 horas):
1. BUG-002 — /fast-fix (5 min) — limpa o cosmético rápido, ganha momentum
2. BUG-005 — /fast-fix (1h) — alto impacto, escopo limitado, fix de UI
3. BUG-001 — /agents-protocol Prompt 2 standard (2h) — auth = classe C, exige Feature Contract

BACKLOG (não cabe hoje):
- BUG-003 — performance, P2 — agendar para sessão Deep Work amanhã
- BUG-004 — ESCALADO para Production (ver abaixo)

ESCALATIONS:
- BUG-004 — classe D (toca payment+webhook+dinheiro real do João).
  Exige cursor-brief + staging + smoke. NÃO entra em fluxo normal.
  Decidir AGORA: posso pausar BUG-001 e atacar BUG-004 com Production mode? João está sem dinheiro confirmado.

WIKI ATUALIZAÇÕES:
- TODO.md §5: 5 linhas adicionadas
- wiki/log.md: [INGEST] triagem de 5 bugs (5 novos) — plano: 002,005,001 | backlog: 003 | escalado: 004 — ref: TODO.md
- wiki/runbooks/: nenhum (todos primeira vez)

PRÓXIMA AÇÃO IMEDIATA:
→ Decidir BUG-004 (escalation): "atacar BUG-004 antes de BUG-001?"
   Se sim: dispare /agents-protocol Prompt 2 com classe D.
   Se não (João pode esperar 1 dia): dispare /fast-fix BUG-002.
```

### Caso 2 — Recorrência detectada

```
TRIAGE — 2026-06-12 14:00

| ID | Bug | Classe | Domínio | Urg | Imp | Esf | Modo | Rec | Score |
| BUG-014 | export PDF lento de novo (45s) | B | performance | P1 | alto | 1h | DEEP WORK | 4ª vez! | 6 |

ESCALATIONS:
- BUG-014 — 4ª ocorrência do mesmo padrão (BUG-003, BUG-007, BUG-011, BUG-014).
  Runbook wiki/runbooks/bug-pdf-lento.md já existe mas vai para 4ª aplicação.
  RECOMENDO: parar de aplicar runbook e investigar causa raiz em Deep Work
  (Feature Contract: refator do gerador de PDF; CI N2; ADR sobre estratégia).
  O fast-fix recorrente é mais caro que o refator.
```

---

## Relação com outras skills

- **`/fast-fix`** — modo executor para os bugs que a triagem marcou como Fast Fix.
- **`/agents-protocol`** Prompt 2 — modo executor para Standard/Deep Work/Production.
- **`/wiki ingest`** — usar ANTES da triagem se a lista veio em formato cru (transcript de Slack inteiro). Triagem espera lista limpa, 1 bug por bloco.
- **`/wiki context`** — usar DEPOIS da triagem para o bug de classe C/D que vai exigir mais sessões.

## Relação com TODO.md §5

A coluna do TODO ganha mais informação:

```
| ID | Descrição | Repro | Classe | Domínio | Urgência | Impacto | Esforço | Modo | Status | Notas |
```

`Status` evolui: `TRIADO` → `EM FIX` → `EM QA` → `RESOLVIDO` (com SHA/PR).

---

## Antipadrões

1. **Triar 1 bug** — desperdício; vá direto pro fix.
2. **Triar e começar a corrigir o primeiro sem mostrar o plano** — você precisa do plano para decidir; o agente devolve, espera você disparar.
3. **Triar bugs misturados com features** — features vão para `TODO.md §2 Backlog`, não para §5.
4. **Triar > 8 bugs em 1 sessão** — perde qualidade; quebre em 2 sessões.
5. **Ignorar recorrência ≥ 3** — fast-fix repetido é dívida disfarçada; pare e refator.
6. **Aprovar Production via triagem** — triagem só recomenda; execução D exige Prompt 2 + autorização explícita.

---

## Referências

- `references/triage-examples.md` — 5 exemplos completos de triagem (lista in → plano out).
