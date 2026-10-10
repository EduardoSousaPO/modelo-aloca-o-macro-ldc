# Fast Fix — Antipadrões

> Casos reais (genéricos) onde "fast fix" escalou para incidente. Use como filtro mental.

---

## 1. "Só vou ajustar essa query, é rápido"

A query estava em endpoint de billing. Tocar billing é classe **C**, não B.

**Lição:** auth, payment, dados sensíveis NUNCA são fast-fix. Mesmo que o diff seja de 1 linha.

---

## 2. "O typo está na chave do JWT"

Mudar nome de chave em token de produção quebra sessões em uso.

**Lição:** se o fix muda comportamento observável de auth, escale para Production (classe D).

---

## 3. "É só null check"

Null check em um lugar revelou que o tipo Zod estava errado em outros 5 endpoints.

**Lição:** se o fix escala para tipo em `packages/shared/types/`, escale o fluxo. Mude tipo é mudar contrato → no mínimo classe B com Feature Contract.

---

## 4. "Vou comentar o teste que está flaky"

Teste flaky pode estar denunciando bug real intermitente.

**Lição:** comentar/.skip teste exige ADR. Não é fast-fix nunca.

---

## 5. "Apenas troco a env var"

Trocar env em produção sem rollback é classe D, exige cursor-brief + staging.

**Lição:** env vars são SEMPRE classe D, mesmo que o "fix" seja 1 caractere.

---

## 6. "Adicionei um console.log para debugar"

Console.log em produção vaza dados; o "fast fix" virou incidente de privacidade.

**Lição:** logs em produção exigem revisão de PII. Se vai logar, é Standard.

---

## 7. "Mexi em 2 arquivos só, mas em módulos diferentes"

Cross-module fix indica acoplamento que merece análise, não fast-fix.

**Lição:** > 1 módulo tocado → escale.

---

## 8. "Rodei o teste local e passou"

Teste local sem CI verde não conta. Fast Fix tem **CI N1 obrigatório**.

**Lição:** sem CI verde, fast-fix não está pronto.

---

## 9. "Esqueci de atualizar o log"

Sem entrada em `wiki/log.md`, ninguém sabe que o fix existiu — e na próxima ocorrência o agente refaz tudo do zero.

**Lição:** memória é parte do fast-fix, não opcional.

---

## 10. "É a quarta vez que esse bug aparece"

Bug recorrente tem causa profunda. Quarta tentativa de fast-fix vai falhar de novo.

**Lição:** ≥ 2 ocorrências passadas → Deep Work, com tempo de investigação real.

---

*Em dúvida, escale. Fast-fix é uma exceção, não a norma.*
