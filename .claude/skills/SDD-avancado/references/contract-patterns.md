# Padrões de Contrato como Código (Harness Solo)

> Coletânea de padrões para `packages/shared/types/` usando Zod + TypeScript.

---

## 1. Envelope de response

Defina **uma vez** em `packages/shared/types/api.ts`:

```ts
export const ApiSuccess = <T extends z.ZodTypeAny>(data: T) => z.object({ data });

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

export const ApiError = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.unknown()).optional(),
  }),
});
```

**Use em todo endpoint.** Consistência = menos código no frontend.

---

## 2. Views públicas vs internas

Nunca expose `password_hash`, `internal_notes`, etc. Separe:

```ts
// packages/shared/types/user.ts
const UserInternal = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  password_hash: z.string(),
  role: z.enum(["user", "admin"]),
  created_at: z.string().datetime(),
});

export const UserPublic = UserInternal.omit({ password_hash: true });
export type UserPublic = z.infer<typeof UserPublic>;
```

Regra: a API **nunca** retorna `UserInternal`; só `UserPublic`.

---

## 3. Branding para IDs

Evite trocar IDs de entidades diferentes. Use brand:

```ts
export const UserId = z.string().uuid().brand<"UserId">();
export const OrderId = z.string().uuid().brand<"OrderId">();

// UserId e OrderId são tipos distintos no TS, mesmo sendo string no runtime.
```

---

## 4. Discriminated unions para eventos / commands

```ts
export const UserEvent = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("user.created"),
    at: z.string().datetime(),
    data: UserPublic,
  }),
  z.object({
    type: z.literal("user.login"),
    at: z.string().datetime(),
    data: z.object({ user_id: UserId, ip: z.string() }),
  }),
]);
export type UserEvent = z.infer<typeof UserEvent>;
```

O consumer faz `switch (event.type)` com exhaustiveness check.

---

## 5. Env como contrato

Valide variáveis de ambiente no boot:

```ts
// apps/api/env.ts
import { z } from "zod";

export const env = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]),
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  RATE_LIMIT_PER_MIN: z.coerce.number().int().positive().default(60),
}).parse(process.env);
```

Boot falha cedo se algo estiver faltando. Sem "undefined em produção às 3h da manhã".

---

## 6. Paginação consistente

```ts
export const PaginationQuery = z.object({
  page: z.coerce.number().int().min(1).default(1),
  limit: z.coerce.number().int().min(1).max(100).default(20),
  sort: z.string().optional(),
  order: z.enum(["asc", "desc"]).default("desc"),
});
```

Toda listagem parseia a query com este schema. Nada de "cada endpoint tem um jeito".

---

## 7. Datas e dinheiros

- **Datas na API:** ISO 8601 string (`z.string().datetime()`). Conversão para `Date` só no client/server quando necessário.
- **Dinheiro:** armazene em inteiros na menor unidade (centavos). Nunca float. Tipo: `z.number().int().nonnegative().brand<"Cents">()`.

---

## 8. Erros de validação tipados

Quando a validação Zod falha, devolva `details.fields`:

```ts
const parsed = LoginInput.safeParse(body);
if (!parsed.success) {
  return Response.json({
    error: {
      code: "VALIDATION_ERROR",
      message: "Dados inválidos",
      details: { fields: parsed.error.flatten().fieldErrors },
    },
  }, { status: 400 });
}
```

Frontend renderiza erros campo a campo direto do response.

---

## 9. Regras de evolução

| Mudança | É breaking? | Ação |
|---|---|---|
| Novo endpoint | Não | Adicione direto |
| Novo campo opcional em response | Não | Adicione + atualize schema |
| Novo valor em enum | Depende | Frontend aceita? Se sim, OK. Senão, breaking. |
| Remover campo | **Sim** | ADR + nova versão da API |
| Tornar campo opcional → obrigatório | **Sim** | ADR + nova versão |
| Mudar tipo | **Sim** | ADR + nova versão |

**Processo de breaking change:**

1. Atualize schema em `packages/shared/types/` com versão nova (`UserPublicV2`).
2. Mantenha o antigo funcional por pelo menos uma release.
3. Crie ADR em `docs/decisions/adr/`.
4. Atualize `CONTRACTS.md` documentando as duas versões e o prazo de deprecação.
5. Remova o antigo só depois do prazo de migração.

---

## 10. Regra de ouro

> Se um tipo/schema cruza mais de um módulo (app web ↔ api, api ↔ service worker, server ↔ client), ele **tem que** viver em `packages/shared/types/`. Sem exceção.

Quando o agente de IA ficar tentado a "só copiar o tipo aqui rapidinho", responda NÃO — o drift começa exatamente aí.
