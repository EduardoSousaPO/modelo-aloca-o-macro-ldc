# Validation Matrix — F-NNN [Nome da feature]

> **Matriz obrigatória no QA (Prompt 3) de todas as features classe B, C, D.** Relaciona cada critério de aceite com o teste que o cobre, o tipo de teste, o status e a evidência objetiva. No **Validation Mode** (v3.1 patch), o QA não apenas confirma que testes passam — ele **tenta quebrar** a feature antes de aprovar.
>
> **Se algum CA não tem evidência objetiva → resultado final é `MUDANÇAS_SOLICITADAS`. Nunca `APROVADO`.**
>
> **Onde vive:** por padrão, no próprio Feature Contract (bloco final). Só extraia para `docs/plans/validation-matrix/F-NNN.md` se ficar grande ou se quiser preservar evidência fora do TODO.

---

## Identificação

- **Feature:** F-NNN — [nome]
- **Classe de risco:** [A | B | C | D]
- **Branch:** `feat/<slug>`
- **Autor do QA:** [Claude Code + humano revisor]
- **Data:** YYYY-MM-DD

---

## Matriz CA → teste → evidência

| CA | Descrição resumida | Teste que cobre | Tipo | Status | Evidência |
|---|---|---|---|---|---|
| CA-001 | login credenciais válidas retorna 200 + cookie | `auth.login.test.ts::valid_credentials` | integration | passou | `npm test -- auth.login` ver `tests/integration/auth.login.test.ts:42` |
| CA-002 | login senha errada retorna 401 INVALID_CREDENTIALS | `auth.login.test.ts::invalid_password` | integration | passou | idem, log no PR |
| CA-003 | rate limit 5/min/IP | `auth.login.test.ts::rate_limit` | integration | passou | idem |
| CA-004 | fluxo login na UI ponta a ponta | `login.spec.ts::happy_path` | e2e | passou | `npx playwright show-report` artifact no CI |
| CA-005 | erro amigável se Supabase cair | N/A | **não coberto** | **falhou** | precisa criar mock/stub antes do merge |

---

## Resumo

- **CAs totais:** 5
- **Cobertos por teste automatizado:** 4
- **Cobertos por smoke/manual (se inevitável):** 0
- **Não cobertos:** 1 → **CA-005**

---

## Validation Mode — tentativas de quebrar a feature

> Para classe **B** basta revisar mentalmente; para **C/D**, documentar evidências aqui. Sem esta seção, o QA de C/D não pode retornar `APROVADO`.

| Categoria | Cenário exercitado | Evidência / Nota |
|---|---|---|
| Inputs inválidos | payload sem campo obrigatório → 400 | teste `auth.login.test.ts::missing_email` |
| Inputs no limite | senha com 7 caracteres (min=8) → 400 | coberto em `missing_email`-like |
| Ausência de dados | usuário inexistente → 401 genérico (não 404) | coberto em `invalid_password` |
| Permissão errada | tentar `/admin/*` com user não-admin → 403 | teste `admin.guard.test.ts` |
| Idempotência / chamadas repetidas | 6ª tentativa dentro de 1min → 429 | `rate_limit` test |
| Edge case óbvio | email com unicode, timezone estranho | manual: validado em dev |
| UI vazio/loading/erro | dashboard sem dados → empty state | `dashboard.spec.ts::empty` |
| Fora de escopo alterado? | diff só toca arquivos permitidos | `git diff --stat` anexado ao PR |

Se alguma linha está vazia ou marcada como "não exercitado", o agente deve **criar o teste** (A/B) ou **solicitar** (C/D) antes de aprovar.

---

## Tipos de teste aceitos (prioridade decrescente)

1. **unit** — cobre lógica pura, sem IO.
2. **integration** — cobre contratos reais entre módulos, idealmente com DB real ou container.
3. **contract test** — cobre schema Zod vs. payload real (consumer-driven quando aplicável).
4. **e2e** — Playwright/Cypress, cobre fluxo na UI com backend real ou mock determinístico.
5. **smoke test** — verificação curta pós-deploy (health checks, login básico).
6. **manual — só se inevitável** — descreva o passo a passo e anexe print/log como evidência.

---

## O que conta como evidência objetiva

- Saída de `npm test` com teste nomeado passando.
- Playwright HTML report com o cenário verde.
- Log do CI do GitHub Actions com linha final `✔ passed`.
- Migration aplicada em staging com `select` comprovando estado esperado.
- Smoke test script rodado com exit code 0 e output anexado.

**O que NÃO conta:**
- "O agente afirma que funciona."
- "O código parece correto."
- Teste que existe mas está `.skip` ou `.only`.
- Cobertura genérica ("o arquivo está testado") sem amarração ao CA.

---

## Resultado final (v3.1 Validation Mode Patch)

Escolha **um**:

- [ ] **APROVADO** — todos os CAs têm evidência objetiva; Validation Mode exercitado; CI verde no nível da classe; Anti-SPEC respeitada; contratos consistentes; nenhum arquivo fora do contrato alterado (ou justificativa aceita com contrato atualizado).
- [ ] **MUDANÇAS_SOLICITADAS** — há CA sem evidência OU teste falhando OU teste fake (ver `risk-classification.md`) OU teste mínimo por classe ausente OU CI vermelho OU contrato divergente OU Validation Mode pulado em C/D.
- [ ] **BLOQUEADO** — Definition of Ready incompleta em domínio sensível OU Anti-SPEC violada OU arquivo fora do Feature Contract sem justificativa aceita OU reclassificação de risco pendente OU operação classe D sem rollback/staging.

### Issues (se MUDANÇAS_SOLICITADAS ou BLOQUEADO)

1. [problema específico + caminho de fix]
2. ...

---

*Esta matriz é a peça central do Feedback Hardened. A qualidade do produto depende de nunca aprovar sem evidência.*
