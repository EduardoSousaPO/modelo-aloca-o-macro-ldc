# Módulo `canonical` — camada canônica trimestral (**classe C**)

> Síntese — fonte de verdade: `docs/specs/SPEC.md` RF-019..RF-026 + `packages/shared/schemas/` + **ADR-006**. **Status: nada implementado** (2026-10-10).

## Propósito

Transformar o que cada extrator deixou em `data/processed/` (frequência nativa) no **dataset-base
trimestral alinhado** de `data/canonical/` — insumo único da análise. É o **coração do risco** do
projeto: `transform/`, `load/` e tudo que toca esta camada é **classe C** (`AGENTS.md §2`).

## Tabelas / RFs cobertos

| Tabela | Schema | RF |
|---|---|---|
| `raw_series` (granularidade nativa, PK `series_id,date,vintage`) | `raw_series.py` | RF-019, RF-020 |
| `series_catalog` materializado (132 séries, procedência) | `series_catalog.py` | RF-047 |
| Alinhamento trimestral (último d.u., `ffill ≤ 5 d.u.`) | — | RF-023 |
| `macro_quarterly` (**exatamente 83 linhas**, PK `quarter`) | `macro_quarterly.py` | RF-021 |
| `asset_returns_quarterly` (**≥ 18 ativos**, nominal/excesso CDI/real) | `asset_returns_quarterly.py` | RF-022, RF-024 |
| Inclinação da curva (vértices interpolados) · materializações `asof`/`revised` | — | RF-009, RF-025 |

## Fonte primária e fallback

- **Primária:** **Parquet por camada**; **DuckDB só como engine de consulta**, derivado e descartável (ADR-006). Validação obrigatória com **pandera** em toda fronteira de entrada/saída.
- **Fallback:** não há. `data/` é **reconstruível** e a fonte de verdade é o script que produz o dado. Lacuna sem substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`, nunca interpolação.

## Armadilhas conhecidas (pesquisa)

- **Trimestral como dado primário é erro irreversível.** Armazenar na granularidade nativa e **agregar por função**; trimestre = **último dia útil** (fim de período), salvo decisão no `DECISIONS_LOG`.
- **Excesso sobre CDI e retorno real sempre por razão** `(1+r)/(1+b)−1`, nunca subtração: com Selic a 14 % a diferença não é arredondamento. Teste anti-subtração é obrigatório.
- **Look-ahead é o risco dominante:** PIB e IBC-Br são **revisados retroativamente** e divulgados com defasagem → nenhum T pode ser classificado com dado publicado depois do fim de T sem a flag `asof` (RF-025).
- **Painel desbalanceado é a regra, não exceção:** ICON 2007+, IMOB 2008+, IFIX 2011+, FII segmentado 2019+ → **nenhuma linha antes do início real da série**, e `n` + `data_inicio` visíveis em toda tabela (S-06/S-07).
- **Quebra estrutural da Selic** (19 % → 2 % → 14 %) torna retorno nominal incomparável entre épocas — daí a métrica primária ser excesso sobre CDI (ADR-002).
- **`strict=True` nos schemas:** nenhuma coluna ad hoc. Idempotência: rodar duas vezes do mesmo `raw/` tem de dar o **mesmo hash** (RF-048).

**Features do TODO:** **F-013** (`raw_series` + catálogo) · **F-014** (alinhamento) · **F-015** (`macro_quarterly`) ·
**F-016** (curva) · **F-017** (retornos) · **F-018** (`asof`) · **F-029** (orquestrador) — **todas classe C**.
