---
name: project-kickoff
description: >
  Inicializa um novo projeto com a estrutura mínima do Harness v3.2 (Project Wiki + Fast Fix). Cria: docs/ (com subpastas product, specs, contracts, plans com feature-contracts/ e CURRENT_REALITY/DECISIONS_LOG templates, decisions/adr, **wiki/** com index/log/overview/architecture/runbooks/context/modules/features), apps/, packages/shared/types/, tests/, AGENTS.md v3.2 (com classificação A/B/C/D + autonomia/pausa + Wiki + Fast Fix), TODO.md (com DoR + Feature Contract inline), README.md, .gitignore e .github/workflows/ci.yml com níveis N1/N2/N3 comentados. Nunca cria state/, handoffs/, progress.jsonl nem WAVE-PLAN.md detalhado.
  Use esta skill SEMPRE que um novo projeto for iniciado — antes de /consultor-prd ou /SDD-avancado. Ative quando o usuário mencionar: "novo projeto", "começar projeto", "iniciar desenvolvimento", "setup do projeto", "criar estrutura", "kickoff", ou qualquer variação que indique início de projeto.
---

# /project-kickoff — Harness v3.2

Você ativou o **Project Kickoff** do Harness v3.2. Esta skill cria a estrutura mínima que permite o fluxo enxuto com Feedback Hardened + Project Wiki:

```
/project-kickoff  →  /consultor-prd  →  /SDD-avancado  →  /skill-scout (opcional)
                  →  /agents-protocol  →  execução feature a feature
                  →  /wiki ingest|context|lint|repair (memória viva)
                  →  /fast-fix (bug urgente classe A/B)
```

O Harness v3.2 acrescenta ao v3.1:

- **Project Wiki** em `docs/wiki/` — memória sintetizada entre fontes brutas e agente; continuidade Claude/Codex/Cursor.
- **Fast Fix** (`/fast-fix`) — modo Project Quick para bug urgente A/B sem auth/payment/db, < 30 min.

E preserva tudo do v3.1:

- Classificação A/B/C/D obrigatória.
- Matriz de validação no QA.
- Regras de autonomia/pausa/BLOQUEADO em AGENTS.md.
- Um agente gerador (Claude Code).
- Cursor Agent opcional (classe D, MCP).
- Estado em `TODO.md` + git. Sem `state/`, `handoffs/`.
- Contratos como código em `packages/shared/types/`.

---

## O que esta skill produz

```
[nome-do-projeto]/
├── AGENTS.md                         ← v3.2 (papéis + A/B/C/D + autonomia + Wiki + Fast Fix) ≤360 linhas
├── CLAUDE.md                         ← v3.2 (≤140 linhas)
├── TODO.md                           ← com suporte inline a Feature Contract
├── README.md
├── .gitignore
├── .github/
│   └── workflows/ci.yml              ← CI com N1 ativo + N2/N3 comentados
├── docs/
│   ├── product/                      ← PRD.md em /consultor-prd
│   ├── specs/                        ← SPEC.md em /SDD-avancado (Anti-SPEC sagrada)
│   ├── contracts/                    ← CONTRACTS.md em /SDD-avancado
│   ├── plans/
│   │   ├── feature-contracts/        ← Feature Contracts dedicados (C/D extensos)
│   │   ├── risk-classification.md    ← copiado do template (v3.1)
│   │   ├── FEATURE-CONTRACT-template.md  ← template local (v3.1)
│   │   ├── VALIDATION-MATRIX-template.md ← template local (v3.1)
│   │   ├── CURRENT_REALITY-template.md   ← usado em modo retroativo (v3.1)
│   │   └── DECISIONS_LOG-template.md     ← memória operacional opcional (v3.1)
│   ├── wiki/                         ← Project Wiki (NOVO v3.2)
│   │   ├── index.md                  ← mapa principal (lido primeiro por todo agente)
│   │   ├── log.md                    ← histórico cronológico vivo
│   │   ├── overview.md               ← projeto em 1 página (síntese do PRD)
│   │   ├── architecture.md           ← arquitetura técnica viva (síntese do SPEC)
│   │   ├── modules/                  ← 1 página por módulo significativo
│   │   ├── features/                 ← resumo curto após merge C/D
│   │   ├── runbooks/                 ← deploy, rollback, smoke, bug recorrente
│   │   └── context/                  ← Context Packs por tarefa (descartáveis)
│   └── decisions/adr/
├── apps/
├── packages/
│   └── shared/
│       └── types/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
└── infra/
```

**O que NÃO é criado** (diferenças do Harness v2):
- `state/`, `handoffs/`, `progress.jsonl`, `bugs/`
- `PROCESS.md` voltado a cliente externo
- `.cursor/rules/` — adicionado só se Cursor Agent for usado
- `docs/plans/TASKS.md` — features vivem em TODO.md

---

## Processo — 3 passos

### PASSO 1 — Coletar informações

Pergunte ao usuário:

1. **Nome do projeto** — slug kebab-case
2. **Caminho base**
3. **Tipo** — saas | app | api | landing | ferramenta interna | outro
4. **Stack prevista** (opcional)

### PASSO 2 — Executar o script

```bash
python scripts/init_project.py \
  --name "nome-do-projeto" \
  --path "/caminho/base" \
  --type "saas"
```

O script:
1. Cria a estrutura de pastas acima (incluindo `docs/wiki/` e subpastas v3.2).
2. Escreve os arquivos a partir de `assets/` (AGENTS.md, CLAUDE.md, TODO.md, README.md, .gitignore, ci.yml, ADR-template.md).
3. Copia `FEATURE-CONTRACT-template.md`, `VALIDATION-MATRIX-template.md`, `CURRENT_REALITY-template.md`, `risk-classification.md`, `DECISIONS_LOG-template.md` para `docs/plans/`.
4. Copia `templates/wiki/index.md`, `log.md`, `overview-template.md` (renomeia para `overview.md`), `architecture-template.md` (renomeia para `architecture.md`), `runbook-template.md`, `context-pack-template.md` para `docs/wiki/` (NOVO v3.2).
5. Cria diretórios vazios `docs/wiki/modules/`, `docs/wiki/features/`, `docs/wiki/runbooks/`, `docs/wiki/context/` com `.gitkeep`.
6. Inicializa `git init` + primeiro commit.

### PASSO 3 — Apresentar e orientar

Depois que o script rodar:

1. Liste os arquivos criados.
2. Mostre o conteúdo de `AGENTS.md` e peça confirmação dos papéis.
3. Mostre próximos passos:

```
Projeto criado com Harness v3.2 · Project Wiki + Fast Fix.

Arquivos de referência disponíveis em docs/plans/:
- risk-classification.md — A/B/C/D + testes mínimos por classe + exemplos de teste fake
- FEATURE-CONTRACT-template.md — template por feature B/C/D (justificativa fora-do-contrato)
- VALIDATION-MATRIX-template.md — matriz CA→teste→evidência + Validation Mode
- CURRENT_REALITY-template.md — usar em projetos existentes
- DECISIONS_LOG-template.md — memória operacional leve (opcional)

Project Wiki disponível em docs/wiki/ (NOVO v3.2):
- index.md — mapa principal (seu agente lê primeiro)
- log.md — histórico cronológico vivo
- overview.md — projeto em 1 página (sintetize após PRD aprovado)
- architecture.md — arquitetura técnica viva (sintetize após SPEC aprovado)
- runbooks/, modules/, features/, context/ — populadas no fluxo

Próximos passos:
1. cd [caminho]/[nome-do-projeto]
2. Abrir o Claude Code nesta pasta
3. Rodar /consultor-prd para discovery → docs/product/PRD.md
4. Após PRD/SPEC aprovados, peça ao agente: "atualize wiki/overview.md a partir do PRD" e "atualize wiki/architecture.md a partir do SPEC"
5. Para bug urgente em qualquer momento: /fast-fix (modo Project Quick)
6. Para passar tarefa para Codex/Cursor: /wiki context F-NNN antes de fechar a sessão

Recomendado: renomear DECISIONS_LOG-template.md para DECISIONS_LOG.md quando
surgir a primeira decisão operacional digna de registro. Até lá, deixe como template.
```

---

## Regras desta skill

- **Sempre pergunte o caminho.** Nunca assuma.
- **Pasta existente:** avise e pergunte — adicionar arquivos faltantes ou abortar?
- **Sem gate de faturamento.**
- **CI obrigatório desde o kickoff.** Sem CI, não há evaluator.
- **AGENTS.md ≤180 linhas (v3.1).**
- **Não avance para `/consultor-prd` automaticamente.**
- **v3.1: templates de Feature Contract, Validation Matrix, CURRENT_REALITY e risk-classification são copiados para `docs/plans/`.**

---

## Assets desta skill

- `assets/AGENTS.md` — v3.1
- `assets/CLAUDE.md`
- `assets/TODO.md` — v3.1 com DoR + Feature Contract inline
- `assets/README.md`
- `assets/gitignore`
- `assets/ci.yml` — N1 + N2/N3 comentados
- `assets/ADR-template.md`

(Os templates de FEATURE-CONTRACT, VALIDATION-MATRIX, CURRENT_REALITY e risk-classification vêm de `templates/` da raiz do pacote Harness v3.1 — o script os copia para `docs/plans/` do projeto gerado.)

## Scripts

- `scripts/init_project.py` — inicializa o projeto (deve ser atualizado para também copiar os novos templates para `docs/plans/`)

## Referências

- `references/structure-guide.md`
- `references/differences-from-v2.md`
