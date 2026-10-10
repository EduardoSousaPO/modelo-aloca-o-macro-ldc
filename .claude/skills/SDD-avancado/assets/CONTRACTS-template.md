# CONTRACTS — [Nome do Projeto]

> Espelho **legível** dos contratos. A **fonte de verdade são os schemas Zod/TypeScript** em `packages/shared/types/`.
> Este arquivo apenas **referencia e descreve** — nunca duplica a definição.
>
> Versão: 1.0 — Referência: SPEC v[X]

---

## Como este arquivo funciona

No Harness v3.1, **contratos são código**. Toda mudança em contrato:

1. Acontece **primeiro** em `packages/shared/types/` (Zod + TypeScript).
2. Depois é **refletida** aqui em prosa curta.
3. Gera uma entrada de migração em ADR se for *breaking*.

```
packages/shared/types/
├── api.ts          ← padrões: envelope de response, erros
├── auth.ts         ← LoginInput, LoginResponse, UserSession
├── user.ts         ← User, UserRole
└── index.ts        ← re-export
```

**Regra absoluta:** se o agente gerador precisa de um tipo que não existe ainda, **ele cria em `packages/shared/types/` primeiro** e só depois implementa o endpoint/componente.

---

## 1. Padrões de resposta da API

### Sucesso
```ts
// packages/shared/types/api.ts
import { z } from "zod";
export const ApiSuccess = <T extends z.ZodTypeAny>(data: T) =>
  z.object({ data });
```

### Sucesso paginado
```ts
export const ApiPaginated = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    data: z.array(item),
    meta: z.object({
      page: z.number().int().min(1),
      limit: z.number().int().min(1).max(100),
      total: z.number().int().min(0),
      total_pages: z.number().int().min(0),
    }),
  });
```

### Erro
```ts
export const ApiError = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.unknown()).optional(),
  }),
});
```

---

## 2. Endpoints

### POST `/api/v1/auth/login` — cobre RF-001

- **Input:** `LoginInput` em `packages/shared/types/auth.ts`
- **Output 200:** `ApiSuccess(LoginResponse)`
- **Output 401:** `ApiError` com `code: "INVALID_CREDENTIALS"`
- **Output 429:** `ApiError` com `code: "TOO_MANY_ATTEMPTS"`, campo `details.retry_after` (segundos)
- **Regras:** rate limit 5/min/IP; senha com `bcrypt` cost ≥ 12; cookie `httpOnly` + `SameSite=Lax`.

Schema de referência (reproduza EXATAMENTE no código):
```ts
// packages/shared/types/auth.ts
export const LoginInput = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
});
export const LoginResponse = z.object({
  user: UserPublic,   // vem de user.ts
  token: z.string(),
  expires_at: z.string().datetime(),
});
```

### GET `/api/v1/users/me` — cobre RF-004
- **Auth:** Bearer token obrigatório.
- **Output 200:** `ApiSuccess(UserPublic)`
- **Output 401:** `ApiError` com `code: "UNAUTHENTICATED"`

<!-- Adicione endpoints conforme necessário, sempre apontando para o schema em packages/shared/types/. -->

---

## 3. Entidades do banco

> DDL detalhado vive nas migrations (`infra/supabase/migrations/`). Aqui só a visão lógica.

### User
- Campos: `id UUID PK`, `email text unique not null`, `nome text not null`, `password_hash text not null`, `role text default 'user'`, `created_at timestamptz default now()`.
- RLS: usuário só pode ler/editar o próprio registro; admin pode ler (nunca alterar senha de outros).

---

## 4. Eventos (se aplicável)

### `user.login`
- **Produtor:** auth service.
- **Payload:** `{ user_id: UUID, at: ISO8601, ip: string, user_agent: string }`.
- **Consumidores:** log de auditoria.

---

## 5. Regras de evolução

**Mudança aditiva (OK, sem breaking):**
- Novo endpoint.
- Campo **opcional** em response.
- Novo valor em enum (se clientes toleram desconhecido).

**Mudança breaking (exige ADR + versão nova):**
- Remover endpoint.
- Remover ou renomear campo.
- Tornar campo opcional → obrigatório.
- Mudar tipo ou semântica.

**Processo de mudança:**
1. Atualiza primeiro `packages/shared/types/`.
2. Atualiza `CONTRACTS.md` refletindo.
3. Se breaking: cria ADR + incrementa versão da API.
4. Atualiza testes de contrato em `tests/contracts/`.

---

## 6. Aprovação

- [ ] Todos os endpoints têm schema Zod em `packages/shared/types/`
- [ ] `CONTRACTS.md` reflete fielmente os schemas
- [ ] Padrões de response (sucesso/erro/paginado) consistentes
- [ ] Regras de evolução documentadas
- [ ] Rastreabilidade com RFs da SPEC (campo "cobre")

---

*Próximo passo: popular `TODO.md` com as features baseadas em RFs + CAs + contratos.*
