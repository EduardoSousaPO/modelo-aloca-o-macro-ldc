# DECISIONS_LOG — [Nome do Projeto]

> **Memória operacional leve.** Registra decisões menores que provavelmente voltarão ao debate e, se não forem documentadas, custam tempo ou geram retrabalho. Complementa os ADRs — **não substitui**.
>
> **Onde vive:** `docs/plans/DECISIONS_LOG.md`.
>
> **Quem escreve:** o agente durante o Prompt 2 quando surgir decisão operacional relevante. O humano em qualquer momento.
>
> **Quem lê:** o agente no Prompt 1 (se mencionado no TODO ativo) e no Prompt 3 (quando um comportamento aparentemente estranho precisa ser validado).

---

## Quando registrar

Use esta lista como filtro. Se a resposta for "sim" em ≥1 item, registre.

- Decisão que **mantém comportamento aparentemente errado** por razão conhecida (compatibilidade, contrato com cliente, custo).
- Decisão de **não usar** uma biblioteca, padrão ou integração, com motivo.
- Decisão de **não refatorar** agora um trecho específico.
- Decisão de produto **operacional** que foi combinada fora do PRD (ex.: "por ora, o campo X continua opcional").
- Escolha entre 2+ caminhos válidos, onde alguém (agente ou humano) no futuro pode refazer a análise à toa.

## Quando NÃO registrar

- Fatos óbvios do código ou da stack ("usamos TypeScript").
- Coisas que pertencem ao PRD, SPEC ou Anti-SPEC — **essas continuam protegidas**, só mudam com autorização humana.
- Decisões arquiteturais com trade-off real → **ADR**, não log.
- Bugs, TODOs, ideias — vão no `TODO.md`.
- Detalhes de implementação que a leitura do código resolve.

Se o log começar a parecer um diário, corte.

---

## Formato

Uma linha por decisão. Frase curta com data (ISO), contexto mínimo, decisão, motivo, impacto, e link com feature/PR.

```
- [YYYY-MM-DD] [contexto curto] decisão — motivo — impacto — ref: F-NNN / PR #NN
```

### Exemplo

## Decisões operacionais

- [2026-04-12] [auth] mantivemos o endpoint `/v1/login-legacy` — motivo: 2 clientes externos ainda consomem — impacto: não remover sem aviso de 30 dias — ref: F-003 / PR #24
- [2026-04-15] [deps] não adicionamos `zod-to-openapi` — motivo: escopo atual não gera OpenAPI — impacto: se surgir, avaliar reuso do schema — ref: F-005
- [2026-04-18] [schema] campo `users.locale` continua opcional — motivo: decisão de produto (cliente aceita derivar do header `Accept-Language`) — impacto: cobrir fallback em teste de integração — ref: F-007
- [2026-04-20] [ui] não implementamos skeleton loading no dashboard agora — motivo: overengineering para MVP — impacto: revisar depois do beta — ref: F-010

---

## Regras

1. **Não registrar tudo.** O valor do log é ser curto e confiável.
2. **Se a decisão muda PRD/SPEC/Anti-SPEC, não registre aqui — peça autorização humana e edite o artefato certo.**
3. **Se é arquitetural com trade-off real, crie ADR.**
4. O agente pode propor linhas novas; sempre marque qual feature/PR originou.
5. Revise a cada ~2 semanas para apagar linhas que viraram óbvias ou irrelevantes.

---

*Este arquivo é documento vivo e deliberadamente pequeno. Se passar de ~100 linhas, revise o que virou permanente (vai para ADR/SPEC) e o que virou obsoleto (apague).*
