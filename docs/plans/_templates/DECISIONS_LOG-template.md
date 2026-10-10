# DECISIONS_LOG — estrategia-macro-ldc-dados

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

- Fatos óbvios do código ou da stack ("usamos pandas").
- Coisas que pertencem ao PRD, SPEC ou Anti-SPEC — **essas continuam protegidas**, só mudam com autorização humana.
- Decisões arquiteturais com trade-off real → **ADR**, não log.
- Bugs, TODOs, ideias — vão no `TODO.md`.
- Detalhes de implementação que a leitura do código resolve.

Se o log começar a parecer um diário, corte.

---

## Formato

Uma linha por decisão. Frase curta com data (ISO), contexto mínimo, decisão, motivo, impacto, e link com feature/PR.

```
- 2026-10-10 [contexto curto] decisão — motivo — impacto — ref: F-NNN / PR #NN
```

### Exemplo

## Decisões operacionais

- [2026-10-10] [fontes] série pedida X substituída por Y — motivo: a fonte pedida não é localizável/é paga — impacto: comparabilidade (declarar na página de limitações) — ref: F-0NN / PR #NN
- [2026-10-10] [deps] não adicionamos `seaborn` — motivo: o heatmap é `matplotlib` puro — impacto: uma dep menos no `uv sync` — ref: F-023
- [2026-10-10] [schema] coluna `fonte_versao` continua opcional em `data/processed/` — motivo: só o canônico exige — impacto: cobrir o default em teste `pandera` — ref: F-013
- [2026-10-10] [convenção] trimestre = **fim de período** (último dia útil) — motivo: alinha macro e ativos sem look-ahead — impacto: toda agregação nova segue; mudar exige classe C — ref: F-014

---

## Regras

1. **Não registrar tudo.** O valor do log é ser curto e confiável.
2. **Se a decisão muda PRD/SPEC/Anti-SPEC, não registre aqui — peça autorização humana e edite o artefato certo.**
3. **Se é arquitetural com trade-off real, crie ADR.**
4. O agente pode propor linhas novas; sempre marque qual feature/PR originou.
5. Revise a cada ~2 semanas para apagar linhas que viraram óbvias ou irrelevantes.

---

*Este arquivo é documento vivo e deliberadamente pequeno. Se passar de ~100 linhas, revise o que virou permanente (vai para ADR/SPEC) e o que virou obsoleto (apague).*
