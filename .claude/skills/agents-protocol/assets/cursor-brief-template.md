# Cursor Brief — [Nome do Projeto] (Harness v3.1)

> **Para que serve este arquivo:** instruções curtas para o Cursor Agent executar tarefas de **infra via MCP** (Supabase, Vercel, GitHub) — exclusivamente features classe **D** (produção/infra). Cada seção abaixo é copiada (Ctrl+L) para o chat do Cursor quando necessário.
>
> **Regra:** uma seção por operação. Toda seção tem **Rollback** obrigatório. Se a seção passa de 40 linhas, provavelmente é feature de código — deveria ir para o Claude Code.
>
> **Staging antes de produção:** para qualquer operação com efeito em produção, valide primeiro em staging. Sem exceção.

**Versão:** 1.1 — v3.1 Feedback Hardened
**Data:** YYYY-MM-DD

---

## Como usar

1. Localize a seção da tarefa que precisa executar (ex: "Migration inicial").
2. Abra o Cursor com o repositório. Confirme que os MCPs necessários estão ativos (`.cursor/mcp.json`).
3. Cole a seção inteira no chat do Cursor Agent (Ctrl+L).
4. Aguarde execução e valide o critério de aceite.
5. Volte ao Claude Code e marque a feature correspondente como concluída no `TODO.md`.

---

## Tarefa 1 — Migration inicial (Supabase)

**Feature associada:** F-001 — Estrutura do monorepo
**MCP:** Supabase MCP
**Pré-requisitos:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` no `.env.local` do Cursor.

**Contexto:**
Estamos iniciando o projeto. A tabela `users` precisa ser criada espelhando `packages/shared/types/user.ts`. Policy RLS: cada usuário só enxerga o próprio registro.

**Operação:**

```
Usando Supabase MCP, crie uma migration chamada "0001_init_users" com:

- Tabela `users` (id uuid pk default gen_random_uuid(), email text unique not null,
  created_at timestamptz default now())
- RLS habilitado
- Policy: "users can read own row" — select using (auth.uid() = id)
- Policy: "users can update own row" — update using (auth.uid() = id)

Aplique na database de desenvolvimento e rode a verificação de schema.
```

**Critério de aceite:**
- `select * from users` retorna vazio sem erro.
- Tentativa de select sem auth retorna 0 linhas (RLS ativa).
- Schema bate com `packages/shared/types/user.ts`.

**Rollback (obrigatório):**
1. Apague a migration 0001 da pasta `infra/supabase/migrations/`.
2. Rode `supabase db reset` (development only).
3. Em staging, gere migration reversa `0002_drop_users` com `DROP TABLE users CASCADE`.
4. Se aplicado em produção por engano: **pare tudo**, avise humano, NÃO tente reverter automaticamente.

**Staging:** obrigatório antes de produção. Valide que RLS está ativa sem auth.

---

## Tarefa 2 — Deploy preview (Vercel)

**Feature associada:** F-005 — Dashboard vazio pós-login
**MCP:** Vercel MCP
**Pré-requisitos:** `VERCEL_TOKEN` ativo. Projeto já vinculado ao repo.

**Contexto:**
Primeiro deploy de preview após login funcionar localmente.

**Operação:**

```
Usando Vercel MCP:

1. Configure as env vars no ambiente Preview:
   - SUPABASE_URL=<valor>
   - SUPABASE_ANON_KEY=<valor>
   - NEXT_PUBLIC_APP_URL=<preview url pattern>

2. Trigger um deploy do branch atual.
3. Retorne a URL de preview.
```

**Critério de aceite:**
- Deploy concluído sem erro.
- URL acessível retorna 200.
- Login no preview funciona ponta a ponta.

**Rollback:**
1. `vercel rollback <deployment-id-anterior>` se o preview quebrar.
2. Remover envs novas do preview via `vercel env rm NOME preview`.

**Smoke test pós-deploy:** `curl https://<preview-url>/api/healthcheck` deve retornar 200 e `{ status: "ok" }`.

---

## Tarefa 3 — Workflow CI (GitHub Actions)

**Feature associada:** F-001 — CI verde em push
**MCP:** GitHub MCP (ou `gh` CLI direto)
**Pré-requisitos:** nenhum.

**Contexto:**
O workflow `.github/workflows/ci.yml` já existe no repo. Precisamos garantir que as secrets `SUPABASE_URL` e `SUPABASE_ANON_KEY` estão disponíveis em Actions para o job de integration.

**Operação:**

```
Usando GitHub MCP:

1. Liste os secrets ativos em Actions deste repositório.
2. Se faltar SUPABASE_URL ou SUPABASE_ANON_KEY de teste, adicione-os
   (valores vêm do painel do Supabase, ambiente de teste).
3. Dispare o workflow manualmente ("Run workflow" em main).
4. Reporte status final.
```

**Critério de aceite:**
- Secrets listados incluem os necessários.
- Workflow roda e termina verde.

**Rollback:**
1. Remover secret com `gh secret remove NOME`.
2. Se workflow ficou vermelho e bloqueou main: acionar override manual apenas com aprovação humana.

---

## Template para novas tarefas

> Copie e adapte. Mantenha curto — 40 linhas ou menos por seção.

```markdown
## Tarefa N — [Nome]

**Feature associada:** F-XXX (classe D)
**MCP:** [Supabase / Vercel / GitHub]
**Pré-requisitos:** [envs, tokens, permissões]

**Contexto:**
[2–3 frases explicando o porquê + o arquivo de tipos Zod relacionado, se aplicável]

**Operação:**
[bloco de instrução direta para o Cursor Agent — use listas numeradas]

**Critério de aceite:**
- [afirmação verificável 1]
- [afirmação verificável 2]

**Rollback (obrigatório):**
1. [passo reverso]
2. [passo reverso]
3. Se rollback não for possível automaticamente, pare e avise humano.

**Staging:** [sim — validar X antes de aplicar em produção | N/A]

**Smoke test pós-execução:** [comando ou passo + resultado esperado]
```

---

## Regras deste arquivo (v3.1)

- **Curto acima de tudo.** Se uma seção cresce, é sinal de que a tarefa não é infra — repasse para o Claude Code.
- **Uma seção = uma operação atômica.** Nunca combine "migration + deploy + env" em uma seção.
- **Rollback é obrigatório em todas as seções.** Sem rollback, a operação não entra em staging.
- **Staging antes de produção.** Toda operação com efeito em produção passa por staging primeiro.
- **Smoke test pós-execução.** Defina o teste concreto que comprova que a operação funcionou.
- **Tipos Zod são a fonte de verdade.** Toda migration deve espelhar um arquivo de `packages/shared/types/`.
- **Sem segredos em texto claro.** Cole placeholders `<valor>`; o próprio Cursor Agent lê do `.env.local`.
- **Cursor Agent NUNCA toca código de `apps/` ou `packages/`.** Se o brief pede, refatore para passar ao Claude Code.
- **Operações destrutivas em banco real exigem aprovação humana explícita.** DROP, TRUNCATE, ALTER TYPE incompatível — nunca automático.
