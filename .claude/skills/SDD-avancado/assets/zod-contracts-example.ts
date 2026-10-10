/**
 * Exemplo canônico de contratos como código para Harness Solo.
 * Copie este arquivo para `packages/shared/types/` e adapte aos domínios do seu projeto.
 *
 * Regras:
 * 1. Todo input/output de API passa por Zod.
 * 2. Tipos TS são DERIVADOS dos schemas via z.infer — nunca escritos manualmente.
 * 3. `CONTRACTS.md` é espelho desses schemas, nunca fonte alternativa.
 */

import { z } from "zod";

// -----------------------------------------------------------------------------
// packages/shared/types/api.ts — envelopes compartilhados
// -----------------------------------------------------------------------------

export const ApiSuccess = <T extends z.ZodTypeAny>(data: T) =>
  z.object({ data });

export const PaginationMeta = z.object({
  page: z.number().int().min(1),
  limit: z.number().int().min(1).max(100),
  total: z.number().int().min(0),
  total_pages: z.number().int().min(0),
});
export type PaginationMeta = z.infer<typeof PaginationMeta>;

export const ApiPaginated = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    data: z.array(item),
    meta: PaginationMeta,
  });

export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.unknown()).optional(),
  }),
});
export type ApiError = z.infer<typeof ApiErrorSchema>;

// Códigos de erro padronizados. Evolução: adicionar nunca é breaking; remover sim.
export const ErrorCodes = z.enum([
  "VALIDATION_ERROR",
  "UNAUTHENTICATED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONFLICT",
  "RATE_LIMITED",
  "INVALID_CREDENTIALS",
  "TOO_MANY_ATTEMPTS",
  "INTERNAL_ERROR",
]);
export type ErrorCode = z.infer<typeof ErrorCodes>;

// -----------------------------------------------------------------------------
// packages/shared/types/user.ts — entidades e views
// -----------------------------------------------------------------------------

export const UserRole = z.enum(["user", "admin"]);
export type UserRole = z.infer<typeof UserRole>;

export const UserPublic = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  nome: z.string().min(2).max(100),
  role: UserRole,
  created_at: z.string().datetime(),
});
export type UserPublic = z.infer<typeof UserPublic>;

// -----------------------------------------------------------------------------
// packages/shared/types/auth.ts — inputs/outputs de auth
// -----------------------------------------------------------------------------

export const LoginInput = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
});
export type LoginInput = z.infer<typeof LoginInput>;

export const LoginResponse = z.object({
  user: UserPublic,
  token: z.string(),
  expires_at: z.string().datetime(),
});
export type LoginResponse = z.infer<typeof LoginResponse>;

export const SignupInput = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
  nome: z.string().min(2).max(100),
});
export type SignupInput = z.infer<typeof SignupInput>;

// -----------------------------------------------------------------------------
// Uso (server-side, ex: Next.js Route Handler)
// -----------------------------------------------------------------------------
//
// import { LoginInput, LoginResponse, ApiSuccess, ApiErrorSchema } from "@shared/types";
//
// export async function POST(req: Request) {
//   const parsed = LoginInput.safeParse(await req.json());
//   if (!parsed.success) {
//     return Response.json(
//       { error: { code: "VALIDATION_ERROR", message: "invalid body", details: parsed.error.flatten() } },
//       { status: 400 }
//     );
//   }
//   const { email, password } = parsed.data;
//   // ... lógica ...
//   const body = { user, token, expires_at };
//   const validated = ApiSuccess(LoginResponse).parse({ data: body });
//   return Response.json(validated);
// }
