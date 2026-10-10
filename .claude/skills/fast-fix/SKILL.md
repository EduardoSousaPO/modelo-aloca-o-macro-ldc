---
name: fast-fix
description: >
  Modo de correção rápida (Project Quick) para BUG URGENTE em produção ou desenvolvimento, classe A ou B sem auth/payment/dados sensíveis/banco real, deploy < 30 min do diagnóstico ao PR. Bypassa o Feature Contract completo. Use SEMPRE que o usuário disser: "fast fix", "bug urgente", "tá quebrado em produção", "corrige rápido", "hot fix", "fix de 5 minutos", "tá travado", "preciso corrigir agora", "production down", "emergência". Se durante a execução o agente identificar que toca auth, pagamento, dados sensíveis, banco real, env ou deploy, ELE SAI do modo Fast Fix e escala para Standard/Production.
---

# /fast-fix — Harness v3.2 · Project Quick

Você ativou o **Fast Fix** (Project Quick). Modo enxuto para correção urgente. Objetivo: **do diagnóstico ao PR pronto em < 30 min**, sem Feature Contract completo, mas **com gates objetivos** que protegem produção.

> Este modo NÃO substitui o fluxo Standard/Deep Work/Production. Ele é exceção justificada.

---

## Quando USAR fast-fix

Reúna **TODOS** os critérios:

- [ ] Bug confirmado (não suspeita, não suposição).
- [ ] Classe **A ou B** (ver `risk-classification.md`).
- [ ] **Não toca:** auth, autorização, pagamento/billing, webhook financeiro, dados sensíveis/financeiros, RLS, migration, env vars, deploy, integração externa crítica.
- [ ] Estimativa < 30 min do diagnóstico ao PR.
- [ ] Você (humano) confirma a urgência (cliente travado, demo em N minutos, etc.).

Se qualquer item falha → **NÃO use fast-fix**. Vai para Standard ou Production via Prompt 2.

---

## Quando NÃO usar fast-fix

- Bug que toca auth/payment/dados sensíveis → Standard ou Deep Work (classe C).
- Bug que exige migration/rollback/deploy → Production (classe D).
- "Acho que é fácil" — fast-fix não é palpite, é diagnóstico confirmado.
- Quando você não tem teste reproduzindo o bug (ainda) — vá em Standard, escreva o teste primeiro.
- Bug que envolve mudança de SPEC, PRD ou Anti-SPEC → Standard com pausa para humano.
- Bug recorrente que já teve 2+ tentativas de fix → tem causa profunda, vai em Deep Work.

---

## Processo (Prompt 0 embutido)

Cole o bloco abaixo no Claude Code. O agente executa o Fast Fix end-to-end.

```
[FAST FIX — HARNESS v3.2 PROJECT QUICK]

Bug: [1 frase]
Onde dói: [arquivo/módulo/rota suspeita ou "investigar"]
Repro: [comando exato | passos UI | "ainda não tenho"]
Urgência: [demo em N min | cliente parado | produção quebrada | dev travado]

Execute, NA ORDEM. PARE em qualquer ■ e escale para Prompt 2 (Standard).

1. SCREEN — 60s
   - Lê wiki/index.md.
   - Lê wiki/runbooks/ — algum runbook cobre este bug? Se sim, SIGA O RUNBOOK e pule para passo 7.
   - Lê wiki/log.md últimos 30 dias — bug recorrente? Se 2+ ocorrências passadas, ■ ESCALE para Deep Work.
   - Lê TODO.md §5 Bugs abertos — já está listado?

2. GATE DE CLASSE — 30s
   - Confirme: classe A ou B? (typo, layout, lógica isolada sem contrato, fix de UI, off-by-one, null check, validação faltante)
   - ■ Se toca: auth, autorização, pagamento, billing, webhook financeiro, dados sensíveis/financeiros, RLS, migration, env vars, deploy, integração externa crítica → SAIR do fast-fix. Reportar:
     "FAST FIX ABORTADO — feature de classe C/D. Use Prompt 2 com Feature Contract."
   - ■ Se diagnóstico revelou que NÃO sabe a causa raiz (palpite) → SAIR. Faça teste falhando primeiro (Prompt 2).

3. REPRODUÇÃO — 5 min
   - Escreva (ou rode) UM teste que reproduz o bug. Falhe localmente.
   - Se não consegue reproduzir em < 5 min, ■ SAIR. O bug é mais profundo do que parece.

4. FIX — 10–15 min
   - Diff mínimo. Sem refactor adjacente.
   - Sem mudar tipos em packages/shared/types/ (a menos que esteja consertando o tipo errado em si).
   - Sem mudar SPEC/PRD/Anti-SPEC.
   - Sem mexer em arquivo fora do escopo do bug. Se precisar mexer → ■ ESCALE para Standard.

5. VALIDAÇÃO — 3 min
   - Teste do passo 3 passa.
   - npm run lint && npm run typecheck && npm test (CI N1).
   - Se algum quebrou, conserte ou ESCALE.

6. WIKI MEMORY — 1 min
   - Adicione 1 linha em wiki/log.md:
     - [YYYY-MM-DD HH:MM] [BUGFIX] <descrição em 1 frase> — classe <A|B> — ref: PR #<N> ou commit <sha>
   - Se este bug já apareceu antes (passo 1) ou parece capaz de voltar:
     - Crie/atualize wiki/runbooks/bug-<slug>.md com o template.
     - Adicione linha em log.md tipo [RUNBOOK].

7. PR / COMMIT
   - Classe A: commit em main com mensagem "fix(<area>): <descrição>" + body com 1-2 linhas sobre causa.
   - Classe B: branch fix/<slug>, PR aberto com:
     - Causa raiz (1 frase)
     - O que foi mudado (1 parágrafo)
     - Como validou (comando + saída)
     - Referência ao runbook se criou um
   - CI verde no PR antes de merge.

8. FECHAMENTO — 30s
   - Atualizar TODO.md §5 (mover bug para "Resolvido" ou Concluído).
   - Reportar: "FAST FIX OK em <T min> — PR #<N> — runbook: <sim/não>".

REGRAS DURAS:
- ■ Tocou auth/payment/dados sensíveis → SAIR e escalar.
- ■ Diff > 50 linhas → SAIR. Não é fix, é feature.
- ■ Tempo > 30 min sem terminar → SAIR. Vire Standard.
- ■ Apareceu necessidade de migration/env/deploy → SAIR. Vire Production.
- Sem teste reproduzindo → não é fix, é tentativa. SAIR.
- Sem entrada em wiki/log.md → não terminou.
- Sem CI N1 verde → não terminou.

REGRAS BRANDAS:
- Pode mexer em ≤ 3 arquivos do mesmo módulo.
- Pode adicionar 1 teste novo curto.
- Pode atualizar 1 runbook se padrão se repete.
```

---

## Fluxo de escape — quando Fast Fix vira Standard/Production

Se durante a execução você (agente) identificar que **escalar é necessário**, **pare imediatamente** e responda neste formato:

```
FAST FIX → ESCALADO

Motivo: [auth tocada | payment tocado | migration necessária | tempo > 30min | diff > 50 linhas | causa raiz mais profunda]

Onde escalar:
- [ ] Standard (Prompt 2 — Feature Contract inline classe B/C)
- [ ] Production (Prompt 2 — Feature Contract + cursor-brief + rollback classe D)
- [ ] Deep Work (Prompt 2 + revisão humana — bug recorrente)

Próxima ação para o humano:
1. Abrir TODO.md, criar item F-NNN
2. Rodar Prompt 2 com classe correta
3. Continuar daqui: <descrição do estado atual + arquivos tocados se já houve diff>
```

Não tente forçar Fast Fix em algo que cresceu.

---

## Gates objetivos (cole também isso se quiser)

| Gate | Pergunta | Se NÃO |
|---|---|---|
| Classe | É A ou B sem auth/payment/db? | escalar |
| Reprodução | Tenho teste que falha do jeito esperado? | escalar (escrever teste primeiro) |
| Diff | Vou tocar ≤ 3 arquivos e ≤ 50 linhas? | escalar |
| Tempo | Estou em < 30 min total? | escalar |
| Validação | CI N1 verde? | continuar até verde |
| Memória | Linha em wiki/log.md? | adicionar |
| Recorrência | Bug já apareceu? | criar runbook |

---

## Relação com a wiki

- Fast Fix **lê** `wiki/runbooks/` e `wiki/log.md` antes de tocar código.
- Fast Fix **escreve** 1 linha em `wiki/log.md` ao terminar.
- Fast Fix **cria runbook** se o bug parece capaz de voltar.
- Fast Fix **NÃO atualiza** overview/architecture/modules (escopo de Standard/Deep Work).

---

## Relação com o Validation Mode (Prompt 3)

Em Fast Fix, **não roda Prompt 3 completo**. Em vez disso:

- Classe A: nada além do CI N1 verde.
- Classe B: 1 teste reproduzindo o bug + CI N1 verde + 1 negativo se aplicável (ex.: garantir que o cenário inverso continua ok).

Se quer rigor maior → não é Fast Fix, é Standard.

---

## Referências

- `references/anti-patterns.md` — armadilhas comuns (fast-fix que viraram desastre).
