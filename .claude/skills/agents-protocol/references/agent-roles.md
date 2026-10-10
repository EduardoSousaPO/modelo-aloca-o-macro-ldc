# Papéis detalhados do Harness v3.1 (Feedback Hardened)

> Referência para desambiguar "quem faz o quê" no fluxo solo. Todo agente que tocar o repo deve ser classificável em um destes papéis.

---

## 1. Gerador — Claude Code (Opus)

**Missão:** converter item do `TODO.md` em código + testes + evidência objetiva, com PR mergeável em CI verde no nível correspondente à classe (A/B/C/D).

**Responsabilidades:**

- Ler `TODO.md`, `SPEC.md`, `CONTRACTS.md`, `packages/shared/types/`, Feature Contract e (se existir) `CURRENT_REALITY.md` antes de escrever código.
- Confirmar classificação A/B/C/D e validar Definition of Ready.
- Criar/validar Feature Contract para B/C/D.
- Escrever testes **primeiro**, cobrindo cada CA.
- Implementar respeitando a lista de arquivos permitidos no Feature Contract.
- Rodar CI local no nível da classe (N1 para A/B, N2 para C, N3 para D).
- Preencher a matriz de validação (CA → teste → tipo → status → evidência).
- Criar branch, commit atômico, abrir PR (ou merge direto em `main` para classe A trivial).
- Atualizar `TODO.md` após merge.
- Executar autorrevisão do PR (Prompt 3) antes do merge — retorno APROVADO/MUDANÇAS_SOLICITADAS/BLOQUEADO.
- Pausar e pedir confirmação humana nos marcos definidos em `AGENTS.md §9`.

**Limites (o que NÃO faz):**

- Não edita arquivos em `docs/` sem pedido explícito do humano.
- Não faz deploy — encaminha para o Cursor Agent via brief.
- Não cria pastas `state/`, `handoffs/`, nem arquivos JSON de estado.
- Não introduz comportamento listado na `Anti-SPEC` (SPEC §6).
- Não adiciona dependência externa nova sem ADR.

**Interface:** sessão única do Claude Code, lendo e escrevendo no repositório. O humano conduz com prompts curtos (ver os 3 prompts prontos no SKILL.md principal).

---

## 2. Infra (opcional) — Cursor Agent + MCPs

**Missão:** executar operações de infra — **exclusivamente classe D** — que exigem integração com serviços externos via MCP, sempre com plano de Rollback.

**Quando é ativado:**

- Migration SQL / RLS em Supabase (Supabase MCP).
- Deploy / configuração de envs no Vercel (Vercel MCP).
- Criação/edição de secrets ou workflow complexo em GitHub Actions (GitHub MCP).
- Qualquer operação destrutiva em banco real — aprovação humana explícita antes.

**Quando NÃO é ativado:**

- Escrever código de aplicação — isso é papel do Gerador.
- Escrever ou editar testes — Gerador.
- Tomar decisões de arquitetura — humano, registrado em ADR.

**Fluxo de interação:**

1. Claude Code detecta que a feature exige operação de infra.
2. Gera ou atualiza a seção correspondente de `docs/plans/cursor-brief.md`.
3. Humano copia a seção (Ctrl+L no Cursor IDE) e cola no chat do Cursor Agent.
4. Cursor Agent executa via MCP e retorna evidência do critério de aceite.
5. Humano confirma no Claude Code, que retoma o fluxo normal de PR/merge.

**Limites:**

- Não toca código de `apps/` nem `packages/`.
- Não toca `docs/` nem `TODO.md` — só arquivos de infra (`infra/`, `.github/workflows/`, `supabase/migrations/`).
- Não decide políticas (ex: nome de tabela, política RLS). Isso vem do brief escrito pelo Claude Code.

---

## 3. Avaliador — CI do GitHub Actions

**Missão:** prova independente de que o código do Gerador está correto. Rodando em níveis N1 / N2 / N3 conforme classe da feature.

**Rodadas por nível:**

- **N1 (classe A/B):** `lint`, `typecheck`, `unit`, opcional `build`.
- **N2 (classe B relevante / C):** N1 + `integration`, `contract`, `build`, validação de DB quando aplicável.
- **N3 (classe C crítica / D):** N2 + `e2e`, `smoke`, validação de migration, preview deploy check.

**Extras opcionais:** `npm audit`, lint de commit, size-limit.

**Gate de merge:**

- Sem CI verde, **não há merge**. Isso é estrutural: o separador Generator ↔ Evaluator vive aqui.
- Repositório configurado para exigir checks obrigatórios na branch `main`.

**O que o Avaliador NÃO é:**

- Não é um LLM. Sem "revisor IA" fazendo o papel do CI.
- Não decide se o código é "bom o suficiente" — decide apenas se atende aos contratos executáveis (lint, tipos, testes).

---

## 4. Humano — desenvolvedor solo

**Missão:** conduzir o projeto, aprovar contratos, dar contexto quando os agentes empacarem.

**Responsabilidades:**

- Escrever/aprovar `PRD.md`, `SPEC.md`, `CONTRACTS.md` (com ajuda do `/consultor-prd` e `/SDD-avancado`).
- Manter `TODO.md` limpo no fim de cada dia.
- Decidir quando quebrar uma feature que cresceu.
- Aprovar ADRs.
- Disparar o Cursor Agent quando o Claude Code gera brief.
- Revisar PRs (mesmo os próprios gerados pelo Claude Code) antes do merge quando tocam dados ou contratos sensíveis.

**O que NÃO deve fazer:**

- Escrever código direto sem rastro no `TODO.md` — isso vira dívida invisível.
- Ignorar a Anti-SPEC porque "agora seria mais fácil".
- Abrir 3 sessões de Claude Code em paralelo — elas se atropelam.

---

## Matriz de responsabilidades

| Atividade | Gerador (Claude Code) | Infra (Cursor Agent) | Avaliador (CI) | Humano |
|---|---|---|---|---|
| Escrever código de app | ✅ | — | — | revisa |
| Escrever testes | ✅ | — | — | revisa |
| Migration SQL / RLS | gera brief | ✅ executa | verifica schema | aprova |
| Deploy staging | gera brief | ✅ executa | — | aprova |
| Deploy produção | gera brief | ✅ executa | — | ✅ aprova |
| Atualizar TODO.md | ✅ | — | — | revisa no fim do dia |
| Atualizar docs/ | — | — | — | ✅ |
| Rodar lint/type/testes | local | — | ✅ autoritativo | — |
| Decidir arquitetura | sugere | — | — | ✅ (ADR) |
| Escrever PRD/SPEC | — | — | — | ✅ (com /consultor-prd, /SDD-avancado) |

---

## Invariantes

- Um gerador, um avaliador — **não se misturam**.
- O estado do projeto mora em `TODO.md` + git log, **não** em arquivos JSON paralelos.
- Contrato vive em `packages/shared/types/`, espelhado em `CONTRACTS.md`.
- Quando um agente falha, **pare** e ajuste o prompt/contexto — não adicione um "agente revisor" para contornar.
