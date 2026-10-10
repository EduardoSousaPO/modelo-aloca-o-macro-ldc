---
name: SDD-avancado
description: >
  Ativa o modo Spec-Driven Development Avançado para engenharia de software sênior no fluxo do Harness v3.1 (Feedback Hardened). Use esta skill SEMPRE que o usuário tiver um PRD aprovado e quiser transformá-lo em SPEC técnica + Anti-SPEC + contratos formais (como código Zod) + TODO inicial com features classificadas A/B/C/D + Definition of Ready por feature + Feature Contract obrigatório para B/C/D. Ative quando o usuário mencionar: "quero criar", "preciso desenvolver", "começar a implementar", "arquitetar", "especificar", "definir contratos", "API-first", "spec-driven", "transformar PRD em código", "SDD retroativo", ou qualquer variação de desejo de sair de documento de produto e ir para engenharia. Também ativar quando o usuário pedir ajuda para estruturar SPEC, CONTRACTS, Anti-SPEC, ADRs, PLAN ou classificação de risco.
---

# /SDD-avancado — Spec-Driven Development para Harness v3.1

Você ativou o **Modo SDD Avançado** adaptado ao Harness v3.1 (Feedback Hardened). A partir de agora, **especificações formais + classificação de risco + Feature Contract são o artefato primário de engenharia**. Toda implementação, testes e documentação derivam desses artefatos.

> **Princípio:** Quando a especificação é precisa, o contexto fica limpo. Quando cada feature tem classificação de risco, a quantidade de validação é proporcional ao risco real. Quando há Feature Contract, o escopo não escorrega.

---

## Diferenças em relação ao SDD-avancado v3.0

| v3.0 | v3.1 | Motivo |
|---|---|---|
| TODO.md com features sem classificação | TODO.md com classe A/B/C/D por feature + DoR + Feature Contract inline (B/C/D) | Risco proporcional → validação proporcional |
| Anti-SPEC "obrigatória" | Anti-SPEC **sagrada**: não alterável sem autorização humana + checagem explícita no Prompt 3 | Prevenir drift silencioso |
| CI único | CI por níveis N1/N2/N3 mapeado à classe | Evitar excesso de CI para classe A e déficit para classe D |
| QA por afirmação | QA por **matriz de evidência** (CA → teste → status → evidência) | Feedback Hardened |
| Sem CURRENT_REALITY | `docs/plans/CURRENT_REALITY.md` obrigatório em projeto existente antes de SDD retroativo | Evita inventar features |

**Preservado:**

- 7 fases do fluxo.
- Contratos como código em `packages/shared/types/`.
- CONTRACTS.md como espelho.
- Rastreabilidade RF ↔ feature.
- ADRs para decisões arquiteturais.

---

## Estrutura de pastas

```
projeto/
├── docs/
│   ├── product/PRD.md                ← INPUT
│   ├── specs/SPEC.md                 ← OUTPUT (com Anti-SPEC sagrada)
│   ├── contracts/CONTRACTS.md        ← OUTPUT (espelho)
│   ├── plans/
│   │   ├── PLAN.md                   ← OUTPUT opcional
│   │   ├── CURRENT_REALITY.md        ← INPUT em modo retroativo
│   │   ├── feature-contracts/        ← OUTPUT: contratos dedicados (C/D)
│   │   │   └── F-NNN.md
│   │   └── risk-classification.md    ← referência A/B/C/D (cópia do template)
│   └── decisions/adr/                ← OUTPUT: ADRs
├── packages/shared/types/            ← OUTPUT: schemas Zod (source of truth)
├── TODO.md                           ← OUTPUT: features com classe + DoR + Feature Contract inline
```

---

## As 7 fases do SDD-avancado v3.1

### FASE 1 — Captura de intenção

Se o projeto é **novo**: conduza discovery curta se `PRD.md` não veio do `/consultor-prd`.
Se o projeto **já existe**: comece por `docs/plans/CURRENT_REALITY.md` — **obrigatório**. Sem ele, o SDD retroativo inventa features. Use `assets/CURRENT_REALITY-template.md` (ou o de consultor-prd).

Mapeie:
1. Problema real.
2. Usuário final.
3. Comportamento esperado.
4. Anti-comportamento.
5. Restrições duras.
6. Greenfield ou brownfield.
7. Escala esperada.

### FASE 2 — PRD

Valide o `docs/product/PRD.md`. Em modo retroativo, o PRD foi derivado lendo `CURRENT_REALITY.md` **primeiro** — respeite o que o código realmente faz hoje.

### FASE 3 — SPEC + Anti-SPEC

Crie `docs/specs/SPEC.md` usando `assets/SPEC-template.md`:

1. RF-NNN numerados
2. RNF-NNN
3. Fluxos principais
4. CA-NNN em Given/When/Then
5. Casos de borda
6. **Anti-SPEC sagrada** (seção 6) — fora de escopo, comportamentos proibidos, padrões proibidos
7. Modelos de dados
8. Limites de escopo
9. Tabela de rastreabilidade **RF ↔ feature ↔ classe ↔ CI alvo** (preenchida na Fase 6)

**Regra nova v3.1:** Anti-SPEC não pode ser alterada por agente sem autorização humana. Toda feature C/D lista explicitamente quais itens são relevantes.

### FASE 4 — Contratos como código

Crie schemas Zod em `packages/shared/types/` para inputs/outputs, entidades, envelopes, eventos. Depois, `CONTRACTS.md` como espelho legível.

### FASE 5 — PLAN + ADRs (opcional)

Crie `PLAN.md` se ≥8 features ou dependências não-triviais. ADRs para decisões com trade-off real.

### FASE 6 — TODO inicial com classificação, DoR, Feature Contract e testes mínimos

**Regra nova v3.1 (reforçada pelo Validation Mode Patch):** cada feature do `TODO.md` nasce com:

- **Classe A/B/C/D** (ver `risk-classification.md`).
- **Definition of Ready** embutida no item.
- **Feature Contract inline** para B/C/D (ou referência a `docs/plans/feature-contracts/F-NNN.md` se extenso).
- Arquivos permitidos/proibidos listados.
- **Testes mínimos** alinhados à classe (fonte: `risk-classification.md §Testes mínimos`).
- **CI alvo** (N1/N2/N3) indicado.
- Para D: indicação de necessidade de `cursor-brief` + staging + rollback.
- **Risco de reclassificação** avaliado — marque features cuja natureza pode subir durante a execução (ex.: CRUD simples de usuário → quase sempre vira C quando toca auth; "dashboard inicial" → vira C se consumir dados sensíveis).

Atualize também a tabela da seção 9 do `SPEC.md`:

```
| RF     | Cobre          | Feature | Classe | CI alvo |
|--------|----------------|---------|--------|---------|
| RF-001 | CA-001, CA-002 | F-003   | C      | N2      |
```

### FASE 7 — Context Check + Validação

Checklist:
1. SPEC ↔ CONTRACTS ↔ PLAN ↔ TODO alinhados?
2. Cada RF tem pelo menos uma feature?
3. Cada endpoint/entidade tem schema Zod?
4. `.github/workflows/ci.yml` existe e cobre N1 (mínimo)?
5. Anti-SPEC revisada — nenhuma feature viola?
6. Cada feature B/C/D tem DoR completa e Feature Contract presente?
7. Features D têm rollback previsto + necessidade de cursor-brief mapeada?

Se algo não bater, **volte uma fase**.

Saída final:

```
SDD completo. Artefatos em:
- docs/specs/SPEC.md (com Anti-SPEC sagrada)
- docs/contracts/CONTRACTS.md
- packages/shared/types/*.ts
- docs/decisions/adr/
- TODO.md: N features (a=A, b=B, c=C, d=D) com DoR + Feature Contract inline
- docs/plans/feature-contracts/ (apenas contratos dedicados)

Próximo passo:
→ /skill-scout (opcional) — agora também avalia risco operacional
→ /agents-protocol — prompts v3.1 (DoR + matriz) + atualização AGENTS.md
```

---

## Modo retroativo (projeto existente)

1. **Obrigatório:** gerar ou validar `docs/plans/CURRENT_REALITY.md`.
2. Extrair RFs do que **existe em código**, não do que o README sugere.
3. Separar:
   - Escopo atual (real)
   - Escopo futuro (desejado)
   - Hipóteses (não validadas)
   - Débito técnico
   - Features mencionadas mas inexistentes
4. Anti-SPEC absorve:
   - Tabelas/rotas legadas não alteráveis.
   - Comportamentos conhecidos como proibidos por incidente passado.
5. TODO começa com duas seções principais: Backlog + Débito técnico.
6. Cada feature retroativa classificada A/B/C/D com mesma rigor que greenfield.

---

## Regras desta skill

- **Apresente e aprove cada artefato** antes de seguir.
- **Contratos primeiro em `packages/shared/types/`**, depois espelho em `CONTRACTS.md`.
- **Anti-SPEC é sagrada**: não alterável por agente sem autorização humana.
- **Classificação A/B/C/D é obrigatória** em cada feature do TODO.
- **Definition of Ready** explícita por feature B/C/D.
- **Feature Contract inline** no TODO para B/C/D (ou `docs/plans/feature-contracts/` se extenso).
- **Rastreabilidade RF ↔ feature ↔ classe ↔ CI** obrigatória.
- **CURRENT_REALITY.md obrigatório em projeto existente** antes do SDD retroativo.
- **Não crie `state/`, `handoffs/` ou `progress.jsonl`.**
- **Não crie `TASKS.md`.** Unidade é feature.

---

## Assets desta skill

- `assets/PRD-template.md`
- `assets/SPEC-template.md`
- `assets/CONTRACTS-template.md`
- `assets/PLAN-template.md`
- `assets/ADR-template.md`
- `assets/TODO-template.md` (v3.1 — com classe + DoR + Feature Contract inline)
- `assets/FEATURE-CONTRACT-template.md` (v3.1 Validation Mode — testes mínimos por classe + justificativa)
- `assets/VALIDATION-MATRIX-template.md` (v3.1 Validation Mode — tentativas de quebrar)
- `assets/risk-classification.md` (v3.1 Validation Mode — testes mínimos + teste fake)
- `assets/DECISIONS_LOG-template.md` (v3.1 Validation Mode — memória operacional)
- `assets/zod-contracts-example.ts`

## Referências

- `references/sdd-avancado-methodology.md`
- `references/contract-patterns.md`
- `references/context-engineering.md`
