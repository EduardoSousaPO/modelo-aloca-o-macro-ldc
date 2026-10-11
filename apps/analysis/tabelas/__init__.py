"""Tabelas do entregável, uma por módulo, todas geradas por código versionado.

| Módulo | Tabela | RF / CA | Feature |
|---|---|---|---|
| `ranking_regime_atual` | "regime atual → ranking" + concordância | RF-034/037 | **F-024** |

Convenções comuns a toda tabela desta pasta — as mesmas de `apps/analysis/figuras/`, pelos mesmos
motivos:

- **Três formatos, uma verdade.** `.parquet` é o dado conferível, `.csv` é o mesmo dado para quem
  abre no Excel e `.md` é a leitura de 1 página. O Markdown é **derivado** do DataFrame, nunca
  escrito à mão: tabela que divergir do Parquet é bug, não formatação.
- **Determinística**: nenhum valor sai do relógio, da rede ou de variável de ambiente. O rodapé
  carrega `versao_build` (hash do código) e o `sha256` de cada insumo lido, que é o que torna "a
  tabela mudou porque o código mudou" distinguível de "mudou porque o dado mudou" (RF-047/CA-121).
- **`n` em toda célula** (Anti-SPEC §10.2.8), com símbolo para `n < 8` e `n < 5`; `n < 5` nunca
  recebe afirmação conclusiva (CA-099/CA-109).
- **Linguagem descritiva** (Anti-SPEC §10.2.10): "neste regime o ativo rendeu X, n = Y". Nunca
  "vai render". Há guarda executável — `conferir_linguagem_descritiva`.
- **Marca de gate**: `especificacao_congelada=False` ⇒ a tabela nasce com
  `ESPECIFICAÇÃO NÃO CONGELADA — não publicável` (CA-090).
- **Nada de ranking reimplementado.** A ordenação, as métricas e a concordância vêm de
  `apps.pipeline.canonical.metricas_regime` (F-022), que por sua vez importa F-019/F-021. Esta
  camada **lê, compara e apresenta**; quem calcula é o canônico.
"""
