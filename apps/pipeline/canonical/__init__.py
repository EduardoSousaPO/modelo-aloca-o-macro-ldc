"""Camada canônica (`data/canonical/`) — **classe C** em todo arquivo deste pacote.

Começa em F-013, com as duas tabelas que todas as demais consomem:

| Tabela | Schema | O que é |
|---|---|---|
| `raw_series.parquet` | `RawSeriesSchema` | **toda** série de `data/processed/` numa tabela
longa, na granularidade **nativa** |
| `series_catalog.parquet` | `SeriesCatalogMaterializedSchema` | as 134 entradas do catálogo
**enriquecidas com o observado** |

Mais dois artefatos **derivados e descartáveis**: `relatorio_build.json` (linhas por série, janela,
nulos, `sha256` de cada Parquet, versão do build) e `ldc.duckdb` (views sobre os Parquet, ADR-006
§(a).2 — nunca fonte de verdade).

**O que esta camada não faz**, por contrato: não agrega para trimestre (F-014/F-015), não calcula
retorno (F-017), não interpola vértice (F-016), não preenche lacuna (Anti-SPEC §10.1.1) e não
reamostra frequência (§10.4.28). `raw_series` é um *union* validado, ordenado e deduplicado — nada
mais. Qualquer número novo nasce a jusante, em feature própria.

Entrada única — importe do **módulo**, não do pacote (o pacote é só docstring, como
`apps/pipeline/extract/`, para que `python -m` não reimporte o módulo já carregado):

```python
from apps.pipeline.canonical.build_raw_series import construir

resultado = construir()          # lê data/processed/, grava data/canonical/
print(resultado.relatorio["raw_series"]["sha256"])
```

CLI: `python -m apps.pipeline.canonical.build_raw_series [--offline] [--sem-duckdb]`
(`--offline` é o default efetivo: esta camada **nunca** toca a rede).
"""
