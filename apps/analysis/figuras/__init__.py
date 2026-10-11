"""Figuras do entregável, uma por módulo, todas geradas por código versionado.

| Módulo | Figura | RF / CA | Feature |
|---|---|---|---|
| `timeline_regimes` | faixa V1 2006Q1→2026Q3 sobre IBOV e Selic | RF-035 / CA-100 | **F-025** |

Convenções comuns a toda figura desta pasta:

- **Backend `Agg`** e `matplotlib.figure.Figure` direto (sem `pyplot`): nenhuma figura depende de
  estado global do processo, e o módulo é importável de dentro do `pytest` sem abrir janela.
- **Determinística**: nenhum valor sai do relógio. O rodapé carrega `versao_build` (hash do
  código) e o `sha256` de cada insumo lido, que é o que torna "a figura mudou porque o código
  mudou" distinguível de "a figura mudou porque o dado mudou" (RF-047/CA-121).
- **Dados plotados materializados ao lado da figura**, em Parquet: a figura é a leitura, o Parquet
  é a evidência conferível.
- **Marca d'água de gate**: `especificacao_congelada=False` ⇒ a figura carrega
  `ESPECIFICAÇÃO NÃO CONGELADA — não publicável` (CA-090).
- **Paleta validada** (`dataviz`): 4 cores categóricas que passam os seis checks no pairlist
  completo em modo claro, + cinza hachurado para o que não tem rótulo. Identidade nunca é só cor.
"""
