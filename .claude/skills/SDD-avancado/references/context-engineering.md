# Context Engineering para Harness Solo

> Princípios para manter o contexto do agente limpo em cada operação.

---

## Objetivo

No Harness Solo, um único agente (Claude Code) é responsável por gerar código, testes e quase tudo. Se o contexto dele estiver poluído, os outputs degradam. Context engineering é a disciplina de decidir o que entra no contexto, quando entra, e por que.

---

## Três zonas de contexto

### Zona 1 — Sempre no contexto
- `AGENTS.md` (≤150 linhas) — contrato universal
- `TODO.md` (seção "Em andamento") — o que estou fazendo agora

Se qualquer desses dois crescer, o agente começa a errar. **150 linhas é o limite duro do AGENTS.md.**

### Zona 2 — Sob demanda por feature
- `docs/specs/SPEC.md` — trecho dos RFs e CAs que a feature cobre
- `packages/shared/types/<arquivo>.ts` — contratos relevantes
- Arquivos existentes no caminho da feature (`apps/web/auth/...`)

Não carregue a SPEC inteira; peça ao agente para ler seção por seção.

### Zona 3 — Raramente, só quando necessário
- `docs/product/PRD.md` (só se a feature está ambígua e precisa rever intenção)
- `docs/decisions/adr/` (só se a decisão em questão é relevante)
- `docs/contracts/CONTRACTS.md` (espelho — só para humano, raramente para agente)

---

## Regras práticas

### 1. Prefira arquivos pequenos e focados
`packages/shared/types/auth.ts` de 40 linhas > `types.ts` de 400 linhas com tudo.

### 2. Separe template (estável) de preenchimento (muda)
`AGENTS.md` não muda toda semana. Se estiver mudando, provavelmente é conteúdo que devia estar em `TODO.md` ou em ADR.

### 3. Não duplique informação
Se `CONTRACTS.md` e `packages/shared/types/` dizem a mesma coisa (um deriva do outro), não pedimos para o agente ler os dois. Fonte de verdade é o código Zod.

### 4. Estado em markdown, não JSON
Machine-readable só se o consumidor é máquina. Para um agente de IA, markdown com estrutura clara é mais legível. `TODO.md` > `project-state.json`.

### 5. Um sessão = uma feature
Ao terminar, feche a sessão. Começar a próxima feature com contexto limpo evita "ah mas no passo 3 eu fiz X".

---

## O que NÃO carregar nunca

- `node_modules/`, `.next/`, `dist/` (óbvio, mas às vezes o agente tenta)
- Migrations antigas (exceto se a feature explicitamente toca naquele domínio)
- Logs, transcrições de sessões anteriores
- Documentos extensos de cliente (PRD de cliente externo, contratos legais) — resumir em PRD curto

---

## Sinais de contexto poluído

- O agente cita informação que "já vimos antes" mas erra no detalhe → muita coisa no contexto, informação diluída.
- O agente começa a implementar algo que não está no pedido → scope creep = context creep.
- Tempo de primeira resposta muito alto → input gigante.
- Testes escritos cobrem coisas fora da feature atual → contexto de outra feature contaminou.

**Resposta:** limpar contexto, reabrir sessão com apenas `AGENTS.md` + o item do `TODO.md` + `SPEC.md#<secao>` relevante.
