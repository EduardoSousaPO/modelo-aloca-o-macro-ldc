# Runbook — [TÍTULO CURTO E ACIONÁVEL]

> **Receita operacional repetível.** Crie quando: (a) operação repetida ≥ 2 vezes; (b) bug recorrente identificado; (c) procedimento de produção crítico.
>
> **Onde vive:** `docs/wiki/runbooks/<slug>.md`.
> **Naming:** `deploy-staging.md`, `rollback-vercel.md`, `bug-jwt-logout.md`, `env-supabase.md`, `smoke-checkout.md`.

**Última execução verificada:** YYYY-MM-DD
**Tempo médio:** [ex: 5 min | 30 min]
**Risco:** [baixo | médio | alto — exige humano]

---

## 1. Quando usar

> Em 1-3 frases. Quando dispara este runbook?

`[Ex: quando o webhook do Stripe começa a retornar 4xx em massa após deploy.]`

## 2. Pré-requisitos

- [ ] Acesso a [serviço/console]
- [ ] Variável `XYZ` carregada no shell
- [ ] Branch `main` atualizada localmente

## 3. Passos

> Numerados, idempotentes quando possível, com comando exato.

```bash
# 1. Diagnóstico
curl -sS https://api.exemplo.com/health | jq .

# 2. Aplicar fix
npm run script:reset-webhooks

# 3. Verificar
curl -sS https://api.exemplo.com/webhooks/stripe/status
```

## 4. Validação (smoke)

> Como saber que funcionou. Comando + saída esperada.

```bash
npm run smoke:webhooks
# esperado: "OK 200 — last_event 30s ago"
```

## 5. Se falhar

> Caminhos de escape. Cada um leva a outro runbook ou pausa para humano.

| Sintoma | Ação |
|---|---|
| Comando 1 retorna 500 | abrir incidente; pular para `runbooks/incidente-api.md` |
| Comando 3 retorna 401 | rotacionar key (`runbooks/rotate-stripe-key.md`) |
| Validação falha após 5 min | rollback (`runbooks/rollback-vercel.md`) |

## 6. Rollback (obrigatório se classe D)

```bash
# Como desfazer se este runbook quebrar mais que conserta
git revert HEAD --no-edit
vercel rollback
```

## 7. Histórico de execução

| Data | Quem | Resultado | Notas |
|---|---|---|---|
| YYYY-MM-DD | dev solo | OK em 4 min | sem incidente |
| YYYY-MM-DD | dev solo | falhou no passo 3 | precisei rotar key |

---

## Links

- Issue/incident relacionado: [link]
- ADR/decisão: [`DECISIONS_LOG L42`](../../plans/DECISIONS_LOG.md) ou [ADR-NNN](../../decisions/adr/ADR-NNN-...)
- Runbooks correlacionados: [...]

---

*Atualize após cada execução. Se este runbook não foi usado em 6 meses, marque como "verificar" — pode estar desatualizado.*
