"""Camada de análise: figuras, tabelas e relatórios derivados de `data/canonical/`.

**Não contém extração nem transformação canônica** — essas são de `apps/pipeline/`. Aqui mora o
que *lê* o canônico e produz entregável visual ou tabular para o Comitê de Alocação.

Duas regras herdadas de `CLAUDE.md §3` e `AGENTS.md §7`:

1. **Notebook não tem lógica de negócio.** Todo cálculo e todo desenho vive num módulo
   importável daqui; o notebook de entrega (F-027) só chama função e mostra resultado.
2. **Nada aqui publica.** Enquanto `ADR-001` estiver em `Proposta`,
   `especificacao_congelada = False` e toda figura/tabela nasce com a marca
   `ESPECIFICAÇÃO NÃO CONGELADA — não publicável` (CA-090, `AGENTS.md §9`).
"""
