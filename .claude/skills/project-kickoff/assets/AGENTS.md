# AGENTS.md — Harness v3.2 · Project Wiki + Fast Fix

> Contrato universal de agentes. Lido por Claude Code, Cursor Agent, Codex, Copilot ou qualquer agente de IA que toque este repositório.
> **Máximo: ~410 linhas.** Detalhes vivem em `docs/`, `TODO.md`, `docs/wiki/` e nos templates de referência (`risk-classification.md`, `FEATURE-CONTRACT-template.md`, `VALIDATION-MATRIX-template.md`, `DECISIONS_LOG-template.md`).
>
> **v3.2 (Project Wiki):** wiki viva em `docs/wiki/` como memória sintetizada entre fontes brutas e agente; modo **Fast Fix** para bug urgente (Project Quick); continuidade real entre Claude/Codex/Cursor via `wiki/context/<F-NNN>.md`.

---

## 1. Papéis

| Papel | Agente | Escopo | Quando usar |
|---|---|---|---|
| **Gerador** | Claude Code (Opus) | Código, testes, refactors, autorrevisão, Feature Contract | Sempre o ponto de partida |
| **Infra (opcional)** | Cursor Agent + MCPs | Migrations Supabase, deploy Vercel, GitHub Actions, envs | Apenas quando há operação via MCP em serviço externo |
| **Avaliador** | CI (`.github/workflows/ci.yml`) + testes | Lint, typecheck, unit, integration, e2e, build, smoke | Automático em todo push/PR |

> **Regra estrutural:** quem gera código nunca é quem valida. A separação Generator ↔ Evaluator é mantida pelo CI, não por um segundo agente de LLM.

---

## 2. Classificação de risco (obrigatória por feature)

Toda feature é classificada **antes** de começar. Ver `templates/risk-classification.md` (ou `docs/plans/risk-classification.md` se copiado para o projeto).

| Classe | Exemplos | CI alvo | Feature Contract | Staging/Rollback |
|---|---|---|---|---|
| **A** Trivial | typo, layout, ajuste sem contrato | N1 | opcional | não |
| **B** Normal | CRUD simples, endpoint não crítico | N1 + matriz | obrigatório (inline no TODO) | não |
| **C** Crítica | auth, pagamento, permissões, dados sensíveis | N2 | obrigatório (detalhado) | recomendado |
| **D** Produção/Infra | migration, RLS, deploy, env, Stripe/MP | N3 | obrigatório + cursor-brief | **obrigatório** |

Em dúvida entre duas classes, escolha a mais alta.

---

## 3. Onde vai cada coisa

```
projeto/
├── AGENTS.md                          ← este arquivo
├── CLAUDE.md                          ← ajustes específicos do Claude Code (opcional)
├── TODO.md                            ← lista viva de features + Feature Contract inline
├── README.md
├── docs/
│   ├── product/PRD.md                 ← o quê e por quê
│   ├── specs/SPEC.md                  ← o que o sistema faz + Anti-SPEC (sagrada)
│   ├── contracts/CONTRACTS.md         ← espelho legível de packages/shared/types/
│   ├── plans/
│   │   ├── PLAN.md                    ← ondas (opcional)
│   │   ├── CURRENT_REALITY.md         ← estado real do repo (projetos existentes)
│   │   ├── DECISIONS_LOG.md           ← decisões operacionais que voltam ao debate
│   │   ├── skills-manifest.md         ← output do /skill-scout (opcional)
│   │   ├── cursor-brief.md            ← brief de infra MCP (opcional)
│   │   └── feature-contracts/         ← só para contratos que não cabem no TODO
│   ├── wiki/                          ← Project Wiki (v3.2) — memória sintetizada
│   │   ├── index.md                   ← mapa principal (lido primeiro)
│   │   ├── log.md                     ← histórico cronológico vivo
│   │   ├── overview.md                ← o projeto em 1 página
│   │   ├── architecture.md            ← arquitetura técnica viva
│   │   ├── modules/                   ← 1 página por módulo (auth, db, payments, ...)
│   │   ├── features/                  ← resumo curto após merge (C/D)
│   │   ├── runbooks/                  ← deploy, rollback, smoke, bug recorrente
│   │   └── context/                   ← Context Packs por tarefa ativa (descartáveis)
│   └── decisions/adr/                 ← 1 arquivo por decisão arquitetural
├── apps/                              ← código das aplicações
├── packages/shared/types/             ← FONTE DE VERDADE dos contratos (Zod/TS)
├── tests/unit|integration|e2e|contract/
├── infra/                             ← migrations, configs de deploy
└── .github/workflows/ci.yml
```

**Pastas que NUNCA existem:** `state/`, `handoffs/`, `AGENT-BRIEFS/`, `progress.jsonl`, `scripts/` genérico na raiz.

---

## 4. Feed Forward — o que orienta o agente ANTES da execução

Antes de escrever qualquer linha, o agente lê:

1. **`docs/wiki/index.md`** — mapa da Project Wiki + atalhos por cenário. (v3.2)
2. **`docs/wiki/context/<F-NNN>.md`** — Context Pack se a tarefa já foi iniciada. (v3.2)
3. `TODO.md` — item da feature + Feature Contract (inline ou em `docs/plans/feature-contracts/`).
4. `docs/specs/SPEC.md` — RFs, CAs, **Anti-SPEC (§6)**.
5. `docs/contracts/CONTRACTS.md` + `packages/shared/types/` — contratos (fonte em Zod).
6. `docs/plans/CURRENT_REALITY.md` — se o projeto já existia.
7. `docs/wiki/log.md` — últimos eventos relevantes ao domínio. (v3.2)
8. Definition of Ready do item — deve estar completa; senão, **pausa** e resolve primeiro.

> A wiki é **memória sintetizada**, NUNCA fonte de verdade. Em conflito, valem as fontes (PRD/SPEC/Zod/ADR).

---

## 5. Feedback — o que valida DEPOIS da execução

Toda feature B/C/D precisa de **evidência objetiva** por CA antes do merge:

- Matriz CA → teste → tipo → status → evidência (no Feature Contract ou `templates/VALIDATION-MATRIX-template.md`).
- CI por nível correspondente à classe (ver §6).
- Autorrevisão do agente no **Prompt 3 — QA do PR**: retorna **APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO**.

**Nunca APROVADO sem evidência.**

---

## 6. CI por níveis

| Nível | Contém | Obrigatório para |
|---|---|---|
| **N1** | lint, typecheck, unit tests (+ build se rápido) | A, B |
| **N2** | N1 + integration tests + contract tests + database validation + build | B relevante, C |
| **N3** | N2 + e2e + smoke + migration validation + staging + preview deploy check | C crítica, D |

Cada projeto mapeia os scripts reais (`npm run ...`). Comandos genéricos são substituíveis — o que importa é o **escopo do gate**, não o comando.

---

## 7. Protocolo de geração de código

Ao implementar uma feature, o agente:

1. **Valida a classificação** (A/B/C/D). Se estimativa mudar, reclassifica antes de codar.
2. **Valida a Definition of Ready** do item. Incompleta → **pausa**.
3. Para B/C/D, **cria ou valida o Feature Contract** (inline no TODO).
4. **Usa os tipos de `packages/shared/types/`** — nunca inventa interfaces paralelas. Se faltar tipo, adiciona lá primeiro.
5. **Escreve testes falhando** para cada CA antes do código.
6. **Implementa** respeitando os arquivos permitidos no Feature Contract.
7. **Respeita a Anti-SPEC**.
8. **Roda o CI local** no nível correspondente à classe da feature.
9. **Preenche a matriz de validação** (CA → teste → evidência).
10. **Atualiza `TODO.md`** com PR/SHA.

Se encontrar algo fora do Feature Contract, **pausa** e consulta antes.

---

## 8. O que o agente gerador PODE e NÃO PODE editar (sem autorização)

**PODE** atualizar no fluxo normal:
- `TODO.md` (estado, Feature Contract inline, matriz de validação)
- `CONTRACTS.md` (como espelho dos tipos Zod — quando tipos mudam)
- `PLAN.md` quando fecha onda
- ADRs quando há nova dependência/decisão arquitetural clara
- `cursor-brief.md` quando houver infra
- `CURRENT_REALITY.md` durante diagnóstico de repo existente
- matriz de validação (arquivo separado, se usado)
- **`docs/wiki/log.md`** — sempre que ingest, fix ou release relevante (v3.2)
- **`docs/wiki/runbooks/*.md`** — quando bug recorrente (v3.2)
- **`docs/wiki/context/*.md`** — context packs em tarefas ativas (v3.2)
- **`docs/wiki/modules/*.md`** — quando trabalha no módulo (v3.2)
- **`docs/wiki/features/*.md`** — resumo curto após merge C/D (v3.2)
- código em `apps/`, `packages/`, `tests/`, `infra/`

**NÃO PODE** alterar sem autorização humana explícita:
- `PRD.md`
- `SPEC.md`
- `Anti-SPEC` (seção 6 do SPEC)
- decisões estratégicas já aprovadas
- arquitetura aprovada em ADR
- `docs/wiki/overview.md` quando contradiz PRD (precisa ajustar PRD primeiro)
- `docs/wiki/architecture.md` quando contradiz SPEC (precisa ajustar SPEC primeiro)

---

## 9. Autonomia vs pausa vs BLOQUEADO (Validation Mode Patch)

Três estados possíveis em vez de dois:

**CONTINUE automaticamente quando:**
- A tarefa está dentro do Feature Contract.
- Os arquivos alterados estão na lista "podem ser alterados".
- Os testes necessários existem ou estão sendo criados conforme os CAs.
- Não há alteração destrutiva em banco/arquivos.
- Não há risco de produção (classe A/B).
- Não há mudança estratégica de produto.

**PAUSE e peça confirmação humana quando:**
- Precisar mudar `PRD.md`, `SPEC.md` ou `Anti-SPEC`.
- Precisar alterar escopo da feature (CA novo, arquivo fora da lista com risco).
- Precisar tocar produção (classe D).
- Precisar deletar arquivo importante.
- Precisar criar dependência externa relevante (ADR).
- Precisar alterar banco real (migration fora do plan).
- Encontrar conflito entre documentação e código.
- A feature crescer além do combinado (reclassifique antes).

**BLOQUEADO — retorne erro objetivo, não tente prosseguir — quando:**
- **Definition of Ready incompleta** → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`. Liste campos faltantes, qual pergunta precisa resposta, se a lacuna é puramente operacional (pode propor preenchimento seguro) ou exige humano.
- **Arquivo alterado fora da lista "podem ser alterados" sem justificativa aceita** → `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT`. Ver §18 para o fluxo de justificativa.
- **Anti-SPEC violada** → `BLOQUEADO — ANTI-SPEC VIOLADA`. Identifique o item exato.
- **Risco reclassificado (A→B ou B→C/D) sem Feature Contract atualizado** → `BLOQUEADO — RECLASSIFICAÇÃO PENDENTE`. Ver §16.

Fail fast na DoR: o Prompt 2 não começa implementação se a DoR estiver incompleta e a lacuna tocar produto, produção, banco, auth, pagamento ou dados sensíveis.

**FAST FIX (v3.2 — Project Quick):** modo enxuto para bug urgente, classe **A ou B**, sem auth/payment/dados sensíveis/banco/env/deploy, < 30 min do diagnóstico ao PR. Usa `/fast-fix` (skill dedicada) com Prompt 0. Se durante o fix algo escalar para C/D, **sai do modo** e vira Standard via Prompt 2. Detalhes em `skills/fast-fix/SKILL.md`.

**MVP LITE (v3.2 — modo entre "pular Harness" e "Standard"):** para validação de ideia, hackathon, protótipo com < 1 semana de vida, **sem produção, sem dinheiro real, sem dados sensíveis**. Mantém apenas: `TODO.md` + classe + branch + 1 teste no caminho crítico + commit + linha em `wiki/log.md`. **Sem** PRD/SPEC/CONTRACTS/Feature Contract/matriz de validação obrigatórios. Se o MVP virar projeto real (≥ 1 semana de uso, ou tocar produção/auth/payment), **migrar para Standard imediatamente** — gerar PRD/SPEC retroativos via cenário B antes da próxima feature relevante. Detalhes em `harness-v3.2-manual.md §14.5`.

**TRIAGE (v3.2 — bugs em lote):** quando ≥ 2 bugs chegam na mesma janela (cliente, suporte, equipe), use `/triage-bugs` antes de qualquer fix. Devolve em < 5 min: classificação por bug, modo recomendado (fast-fix/standard/deep-work/production), prioridade, plano de ataque do dia. **Nunca começa fix automaticamente** — o humano confirma o plano antes da execução.

---

## 10. Branches e PRs

- **Branches por feature**: `feat/<slug>` (ou `fix/<slug>`, `infra/<slug>`, `chore/<slug>`).
- **Classe A** pode ir direto em `main` se <30min, com teste, CI verde local.
- **B, C, D** exigem PR e CI verde antes do merge.
- **C e D** recomendam revisão humana antes do merge; **D** **exige** staging.
- Mensagens de commit: Conventional Commits, referenciando item do TODO.

---

## 11. Quando ativar o Cursor Agent (opcional)

Só entra quando a tarefa é:
- Migration SQL / RLS em Supabase (Supabase MCP).
- Deploy / env no Vercel (Vercel MCP).
- GitHub Actions workflow complexo / secrets (GitHub MCP).

Nestes casos, o Claude Code gera seção em `docs/plans/cursor-brief.md` com **Contexto, Operação, Critério de aceite e Rollback** (para D).

---

## 12. O que o agente NUNCA faz

- Desabilita teste ou `.skip` sem ADR explicando.
- Faz deploy em produção sem passar por staging (classe D).
- Introduz comportamento listado em Anti-SPEC.
- Aprova PR sem matriz de validação preenchida (classes B/C/D).
- Cria pasta `scripts/`, `state/`, `handoffs/` ou arquivos JSON de estado.
- Altera `PRD.md`, `SPEC.md` ou Anti-SPEC sem autorização.
- Adiciona dependência nova sem ADR.

---

## 15. Validation Mode (obrigatório no QA)

No Prompt 3 — QA do PR, o agente opera em **Validation Mode**: assume que a implementação e os testes podem estar incompletos ou errados e **tenta quebrar** a feature de forma controlada antes de aprovar.

**Regras (sempre, para B/C/D):**

1. Antes de aprovar, tente quebrar a feature.
2. Teste inputs inválidos e no limite (string vazia, número fora da range, tipo errado).
3. Teste ausência de dados / estado vazio.
4. Teste permissões incorretas quando aplicável.
5. Teste chamadas repetidas / idempotência.
6. Teste edge cases óbvios (timezone, unicode, concorrência simples).
7. Teste comportamento vazio/loading/erro em UI quando aplicável.
8. Verifique se algo **fora do escopo** foi alterado (diff vs. arquivos permitidos).
9. Se encontrar cenário não coberto, **crie o teste** (classe A/B autônomo) ou **solicite**-o (classe C/D; pause se produção).
10. Sem evidência objetiva para algum CA → `MUDANÇAS_SOLICITADAS`. **Nunca `APROVADO`**.

Testes mínimos obrigatórios por classe + exemplos de "teste fake" proibido vivem em `risk-classification.md` — fonte única.

---

## 16. Auto-reclassificação de risco

Durante a implementação, se a natureza da feature mudar, o agente **reclassifica antes de continuar**. A regra é simples: **suba, nunca desça**.

**Gatilhos de subida:**

- **A → B:** a mudança passa a alterar **comportamento observável** (não é mais "só typo/layout").
- **B → C:** a feature passa a tocar **autenticação, autorização, permissões, pagamento, billing, dados sensíveis/financeiros, webhooks, regra de negócio central ou fluxo principal do usuário**.
- **qualquer → D:** a feature (ou uma subtask) toca **banco real, migration, RLS, env vars, deploy, infraestrutura, staging/produção ou integração externa crítica**.

**Procedimento ao reclassificar:**

1. **Pause** se a nova classe é C/D com risco alto (produção, banco, auth).
2. Atualize o **Feature Contract** (escopo, arquivos, testes mínimos, CI alvo, rollback se D).
3. Recalcule os **testes mínimos** (ver `risk-classification.md`).
4. Atualize o **CI alvo** (N1 → N2 → N3 conforme classe).
5. Atualize a **Matriz de Validação** (entradas novas).
6. Registre no `TODO.md` (linha de nota no item).
7. Continue apenas se a regra de autonomia §9 permitir.

---

## 17. DECISIONS_LOG (memória operacional leve)

`docs/plans/DECISIONS_LOG.md` é opcional mas recomendado. Complementa ADRs sem substituí-los.

- **ADR** → decisão arquitetural com trade-off real (nova dependência crítica, estratégia de auth, stack).
- **DECISIONS_LOG** → decisão operacional que provavelmente voltará ao debate (mantemos comportamento legado, não usamos lib Y, campo Z continua opcional).
- **TODO.md** → estado + Feature Contract + matriz.
- **PRD/SPEC/Anti-SPEC** → produto e comportamento; agente **não edita** sem autorização.

**Prompt 2** propõe linha no DECISIONS_LOG quando surge decisão operacional durante a implementação.
**Prompt 3** consulta o DECISIONS_LOG se encontrar comportamento aparentemente estranho (antes de acusar bug).

Regras completas no template `DECISIONS_LOG-template.md`. Se o log passar de ~100 linhas, o dev revisa e poda.

---

## 18. Arquivo fora do Feature Contract — fluxo de justificativa

Se o agente precisar alterar arquivo **fora** da lista "podem ser alterados":

**Padrão: BLOQUEADO.**

**Caminho de escape (autonomia em A/B sem risco):** o agente apresenta justificativa explícita contendo:

1. **Qual arquivo** foi/será alterado.
2. **Por que** é necessário (falta de um tipo, bug de suporte, etc.).
3. **Qual o impacto** (superfície do diff, módulos tocados).
4. Se **altera escopo** do produto.
5. Se exige **atualizar o Feature Contract** (arquivos permitidos, CAs).
6. Se exige **novos testes**.
7. Se exige **reclassificação de risco** (§16).

Se a justificativa é puramente operacional e **não** toca produto/produção/banco/auth/pagamento/dados sensíveis, o agente:
- Atualiza o Feature Contract (permitidos, testes, matriz).
- Adiciona linha no DECISIONS_LOG se for decisão útil no futuro.
- Continua.

Se toca qualquer desses domínios sensíveis: **pausa** e pede confirmação humana. Nunca simplesmente prossegue.

---

## 19. Convenções de código

- TypeScript com `strict: true`.
- Zod em todos os boundaries (API, env, IPC, storage).
- Testes: Vitest (unit/integration), Playwright (e2e). Um teste por CA (ver `risk-classification.md` para mínimos por classe).
- Prettier + ESLint na raiz. Conventional Commits.

---

## 20. Para o humano (solo dev)

- Uma sessão ativa do Claude Code por vez.
- Revise o `TODO.md` no fim do dia: mova itens, anote Feature Contracts em andamento.
- Não force classe A em algo que toca produção.
- Se o Claude Code pausou pedindo confirmação, **lê o motivo** — essa é a principal proteção contra degradação.
- Se o Claude Code retornou `BLOQUEADO`, ele está te protegendo: resolva a causa, não tente contornar.
- Para bug urgente: `/fast-fix`. Para feature normal: Prompt 2. Para wiki: `/wiki <modo>`.

---

## 21. Project Wiki (v3.2 — memória entre sessões/agentes)

A Project Wiki vive em `docs/wiki/`. É **memória sintetizada** — síntese viva entre fontes brutas (prints, logs, decisões, transcrições) e os agentes (Claude Code, Codex, Cursor).

**Princípio:** a wiki **nunca** substitui PRD/SPEC/CONTRACTS/ADR. Ela referencia, sintetiza e linka.

**Estrutura:**

| Página | Conteúdo |
|---|---|
| `wiki/index.md` | mapa principal — primeira leitura de qualquer agente |
| `wiki/log.md` | histórico cronológico (ingest, releases, bug fixes, validações) — ≤ 200 linhas |
| `wiki/overview.md` | 1 página com o que o projeto é hoje (síntese do PRD) |
| `wiki/architecture.md` | arquitetura técnica viva (síntese do SPEC + código real) |
| `wiki/modules/<mod>.md` | memória por área (auth, db, payments, deploy) |
| `wiki/features/<F-NNN>.md` | resumo de 1 parágrafo após merge (C/D apenas) |
| `wiki/runbooks/<slug>.md` | passos para deploy, rollback, smoke, bug recorrente |
| `wiki/context/<F-NNN>.md` | Context Pack temporário por tarefa ativa (descartável) |

**Skill `/wiki` com modos:**

- `ingest` — processa fonte bruta colada (print/log/decisão/transcript) e atualiza páginas certas + linha em `log.md`.
- `context` — cria Context Pack reusável entre Claude/Codex/Cursor.
- `lint` — audita contradições, órfãos, decisões conflitantes (somente leitura).
- `repair` — aplica correções da wiki, com pausa por mudança que toca PRD/SPEC.

**Quando usar a wiki:**

| Cenário | Comece por |
|---|---|
| Início de sessão | ler `wiki/index.md` + `wiki/context/<atual>.md` |
| Bug urgente | `/fast-fix` (lê `wiki/runbooks/` + `wiki/log.md`) |
| Nova feature B/C/D | `/wiki context F-NNN` antes do Prompt 2 |
| Continuar em outro agente (Codex/Cursor) | abrir `wiki/index.md` + `wiki/context/<atual>.md` |
| Projeto bagunçado / produção sem docs | `/wiki lint` → `/wiki repair` antes de codar |
| Após merge C/D | resumo curto em `wiki/features/F-NNN.md` |
| Bug recorrente | criar `wiki/runbooks/bug-<slug>.md` |

**Regras de manutenção:**

- Toda feature B/C/D termina com 1 linha em `wiki/log.md` tipo `RELEASE` ou `BUGFIX`.
- Toda decisão arquitetural com trade-off → ADR (não wiki).
- Toda decisão operacional que volta ao debate → `DECISIONS_LOG.md` (não wiki).
- Toda fonte bruta colada pelo usuário → `/wiki ingest`.
- A wiki pequena. Se uma página passa do tamanho-alvo, divida ou arquive.

---

## 22. Continuidade entre agentes (Claude ↔ Codex ↔ Cursor)

A wiki resolve a continuidade entre múltiplos agentes IA sem reescrever instruções:

**Quando passar de um agente para outro:**

1. Agente atual: roda `/wiki context <tarefa-ativa>` para gravar estado em `wiki/context/<F-NNN>.md`.
2. Humano abre o próximo agente (Codex / Cursor).
3. Próximo agente: lê `wiki/index.md` + `wiki/context/<F-NNN>.md`. Tem contexto completo: estado, arquivos, restrições, próximos passos, handoff.
4. Próximo agente continua. Ao parar, atualiza o mesmo Context Pack.
5. Quando a tarefa termina, o pack é deletado e um resumo de ≤ 5 linhas vai para `wiki/features/F-NNN.md`.

> O `AGENTS.md` (este arquivo) é o contrato comum entre todos. A wiki é a memória viva. Os dois juntos eliminam "perdi o contexto".

---

*Última revisão: 2026-05-08 — Harness v3.2 · Project Wiki + Fast Fix.*
