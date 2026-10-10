# SPEC — [Nome do Projeto]

> Especificação funcional. O quê o sistema DEVE (e NÃO DEVE) fazer.
> Versão: 1.0 — Referência: PRD v[X]

---

## 1. Requisitos Funcionais (RF)

> Numerados, verificáveis, testáveis. Cada RF deve estar coberto por **pelo menos uma feature** no `TODO.md` e **pelo menos um critério de aceite (CA)** abaixo.

### RF-001 — [Nome curto]
- **Descrição:** O sistema deve permitir que...
- **Prioridade:** Alta / Média / Baixa
- **Cobre:** CA-001, CA-002
- **Contrato:** `packages/shared/types/<arquivo>.ts` → `<TypeName>` (se aplicável)
- **Notas:** dependências, restrições, referências.

### RF-002 — [Nome curto]
- **Descrição:**
- **Prioridade:**
- **Cobre:**
- **Contrato:**

<!-- Adicione RF-NNN conforme necessário -->

---

## 2. Requisitos Não-Funcionais (RNF)

### RNF-001 — Performance
- Páginas principais carregam em < 2s em conexão 4G.
- API p95 < 500ms.

### RNF-002 — Segurança
- Senhas: bcrypt (cost ≥ 12).
- Rate limit em autenticação: 5/min/IP.
- Headers: CSP, HSTS, X-Frame-Options.
- Zod valida todo input externo.

### RNF-003 — Disponibilidade
- Uptime alvo: 99,5%.
- Deploys zero-downtime.

### RNF-004 — Acessibilidade
- WCAG 2.1 AA para páginas públicas.
- Navegação por teclado em formulários.

---

## 3. Fluxos principais

### Fluxo 1 — [Nome, ex: Login]
**Pré-condição:** usuário com conta existente.
1. Acessa `/login`
2. Preenche e-mail e senha
3. Sistema valida credenciais
4. Gera JWT de 24h, seta cookie httpOnly
5. Redireciona para `/dashboard`

**Pós-condição:** sessão ativa, evento `user.login` registrado.
**Cobre:** RF-001

---

## 4. Critérios de Aceite (CA)

> Formato Given/When/Then. Cada CA vira **pelo menos um teste automatizado**.

### CA-001 — Login com credenciais válidas (cobre RF-001)
```
Given: usuário com conta ativa
When: envia POST /auth/login com e-mail e senha corretos
Then: recebe 200 com token JWT no cookie httpOnly
  And: evento "user.login" é registrado
```

### CA-002 — Login com senha incorreta (cobre RF-001)
```
Given: usuário com conta ativa
When: envia senha incorreta
Then: recebe 401 com code "INVALID_CREDENTIALS"
  And: contador de tentativas é incrementado
  And: após 5 tentativas, retorna 429 até 15min
```

<!-- Adicione CA-NNN conforme necessário -->

---

## 5. Casos de borda

| ID | Cenário | Comportamento esperado | Prioridade |
|---|---|---|---|
| CB-001 | E-mail já cadastrado no signup | 409 + mensagem + sugere login | Alta |
| CB-002 | Token expirado durante uso | 401 + front redireciona preservando estado | Alta |
| CB-003 | API externa fora | fallback + retry 5s + log | Média |

---

## 6. Anti-SPEC (o que o sistema NÃO DEVE fazer)

> **Seção sagrada.** Previne alucinação da IA e scope creep. Nenhum agente pode alterar esta seção sem autorização humana explícita. Toda feature C/D passa explicitamente por esta lista no Prompt 3 (QA do PR).

### Fora desta versão
- NÃO implementar push notifications
- NÃO criar chat entre usuários
- NÃO integrar com redes sociais

### Comportamentos proibidos
- NÃO armazenar dados de cartão de crédito
- NÃO enviar e-mail sem consentimento explícito
- NÃO permitir admin acessar dados de outros usuários
- NÃO logar senhas, tokens ou PII

### Padrões proibidos
- NÃO usar polling para tempo real — usar WebSocket/SSE
- NÃO cache sem estratégia de invalidação
- NÃO endpoint de lista sem paginação

---

## 7. Modelos de dados (visão funcional)

> Semântica; DDL detalhado vive nas migrations. Tipos exatos em `packages/shared/types/`.

### Entidade: User
| Campo | Tipo | Obrigatório | Validação |
|---|---|---|---|
| id | UUID | Sim | auto-gerado |
| email | string | Sim | formato email, único |
| nome | string | Sim | 2–100 chars |
| password_hash | string | Sim | interno, nunca exposto |
| role | enum | Sim | "user" / "admin" (default: "user") |
| created_at | datetime | Sim | auto |

---

## 8. Limites de escopo

| Item | Motivo | Quando |
|---|---|---|
| App mobile | Foco em validar proposta web primeiro | v2 |
| Relatórios avançados | Depende de volume real | v1.1 |

---

## 9. Rastreabilidade (RF ↔ feature ↔ risco)

| RF | Cobre | Feature (TODO.md) | Classe | CI alvo |
|---|---|---|---|---|
| RF-001 | CA-001, CA-002 | F-003 | C | N2 |
| RF-003 | CA-005 | F-004 | C | N2 |
| RF-010 | CA-010 | F-005 | B | N1 |

> Atualize esta tabela ao criar novas features no TODO.md. Serve como check cruzado rápido.
> A classe de risco (A/B/C/D) vem de `risk-classification.md` e determina o nível de CI exigido antes do merge.

---

## 10. Aprovação

- [ ] RFs numerados e verificáveis
- [ ] RNFs documentados com alvos concretos
- [ ] CAs em formato Given/When/Then
- [ ] Casos de borda mapeados
- [ ] Anti-SPEC preenchida
- [ ] Modelos de dados com validações
- [ ] Tabela de rastreabilidade RF ↔ feature
- [ ] SPEC revisada e aprovada

---

*Próximo passo: `docs/contracts/CONTRACTS.md` (espelho dos tipos em `packages/shared/types/`).*
