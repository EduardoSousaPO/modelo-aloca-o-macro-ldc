# [Nome do Projeto]

> [Uma frase explicando o que é.]

---

## Stack

- [ex: Next.js 14, TypeScript, Supabase, Vercel]

## Requisitos

- Node ≥ 20
- npm ≥ 10
- Conta Supabase + Vercel (se aplicável)

## Como rodar

```bash
npm install
cp .env.example .env.local   # preencher variáveis
npm run dev
```

## Scripts principais

```bash
npm test           # testes unit + integration
npm run lint
npm run typecheck
npm run build
```

## Estrutura do repositório

Este projeto segue o **Harness v3.1 (Feedback Hardened)**. Veja `AGENTS.md` para a arquitetura, classificação de risco A/B/C/D, Definition of Ready e regras de autonomia/pausa.

```
apps/       ← aplicações (web, api)
packages/   ← código compartilhado (tipos Zod em packages/shared/types/)
tests/      ← unit / integration / e2e
docs/       ← PRD, SPEC, CONTRACTS, ADRs
TODO.md     ← estado vivo do projeto
AGENTS.md   ← contrato com agentes de IA
```

## Como contribuir

1. Pegue o próximo item de `TODO.md` seção "Em andamento" ou "Backlog".
2. Confirme a classe A/B/C/D e valide a Definition of Ready (ou crie/atualize o Feature Contract inline).
3. Crie branch `feat/<slug>` (classe A trivial pode ir direto em `main`).
4. Escreva teste falhando por critério de aceite.
5. Implemente, respeitando os arquivos permitidos no Feature Contract.
6. Rode o CI no nível correspondente: N1 para A/B, N2 para C, N3 para D.
7. Abra PR com matriz de validação preenchida (B/C/D).
8. CI verde no PR + QA APROVADO com evidência → merge. Atualize `TODO.md`.

## Licença

[MIT / Apache-2.0 / outro]
