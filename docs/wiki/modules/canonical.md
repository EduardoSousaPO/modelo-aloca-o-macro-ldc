# Módulo `canonical` — camada canônica trimestral (**classe C**)

> Verdade: `docs/specs/SPEC.md` RF-019..RF-026 + `packages/shared/schemas/` + **ADR-006**.
> **Estado (2026-10-11): nada implementado** — mas os **insumos existem**: a Onda 1 entregou 53
> Parquets em `data/processed/` (F-002..F-008, aguardando QA). Transformar frequência nativa no
> **dataset-base trimestral alinhado** é o coração do risco: tudo aqui é **classe C** (`AGENTS.md §2`).

| Tabela | Schema | RF |
|---|---|---|
| `raw_series` (nativa, PK `series_id,date,vintage`) | `raw_series.py` | RF-019, RF-020 |
| `series_catalog` materializado (**134** séries) | `series_catalog.py` | RF-047 |
| Alinhamento trimestral (último d.u., `ffill ≤ 5 d.u.`) | — | RF-023 |
| `macro_quarterly` (**exatamente 83 linhas**) · `asset_returns_quarterly` (**≥ 18 ativos**) | `macro_quarterly.py` · `asset_returns_quarterly.py` | RF-021, RF-022, RF-024 |
| Inclinação da curva · materializações `asof`/`revised` | — | RF-009, RF-025 |
| `calendario_dias_uteis` (grade de dias úteis) | `calendario.py` | RF-018 |

## O que a Onda 1 fixou e esta camada herda (`DECISIONS_LOG §2.1`, provisório)

- **`date` de série M/Q = fim de período civil** (D-a), igual em SGS e SIDRA: o `join` por `date`
  casa — 273 meses de IPCA e 90 trimestres de PIB com `max|dif| = 0`
  (`tests/unit/test_contract_sgs_sidra.py`). Ajuste para **dia útil** é F-014, não extração.
- **`vintage` = data (sem hora) do `collected_at` do manifesto do bruto** (D-b), uniforme nas 51
  séries de `processed_series`: é o que faz uma revisão do IBGE/IBC-Br **coexistir** com o retrato
  anterior em vez de sobrescrevê-lo, sem depender de a fonte acrescentar ponto novo.
- **Série derivada é série, não coluna:** `SP500_BRL`/`ACWI_BRL` têm `fonte=DERIVADO`, entrada própria
  no catálogo e `is_total_return` explícito (D-d).
- **`data/processed/` tem duas tabelas de schema próprio** que **não** são `processed_series`:
  `calendario/dias_uteis_anbima.parquet` (4 colunas) e `tesouro-direto/td_painel.parquet` (painel de
  750 `series_id` compostos). Varredura genérica tem de tratá-las à parte.

## Armadilhas

- **Trimestral como dado primário é erro irreversível:** armazenar na granularidade nativa e **agregar
  por função**; trimestre = **último dia útil**, salvo decisão no `DECISIONS_LOG`.
- **D-h · a B3 fecha em dia útil bancário.** O calendário da ANBIMA é **idêntico** ao do CDI e do
  IMA-B em 20 anos, mas **B3 ⊂ ANBIMA em 69 datas** (feriados de São Paulo + emenda de fim de ano),
  nunca o inverso. Em **20 dos 83 trimestres — todos os 4ºs trimestres de 2006 a 2025** — o último
  dia útil bancário não tem fechamento da B3, então **toda série da B3 carrega `ffill_dias_uteis = 1`
  em todo 4T**. É o caso de ADR-006 §(b).8 / CA-066, mas F-014 tem de **escolher** entre (a) grade
  bancária única com ffill e (b) última negociação da B3 para séries da B3 — que cria **duas grades**
  e exige declarar a grade em toda tabela e figura. (b) é classe C. Detalhe em `calendario.md §B`.
- **Excesso sobre CDI e retorno real sempre por razão** `(1+r)/(1+b)−1`, nunca subtração: com Selic a
  14% a diferença não é arredondamento. Teste anti-subtração é obrigatório.
- **Look-ahead é o risco dominante:** PIB e IBC-Br são **revisados retroativamente** e divulgados com
  defasagem (`lag_divulgacao_dias = 60` no PIB) → nenhum T pode ser classificado com dado publicado
  depois do fim de T sem a flag `asof` (RF-025).
- **Painel desbalanceado é a regra:** ICON 2007+, IMOB 2008+, IFIX 2011+, FII segmentado 2019+,
  `EDUCA`/`RENDA` 2023+ → **nenhuma linha antes do início real da série**, e `n` + `data_inicio`
  visíveis em toda tabela (S-06/S-07). A **quebra estrutural da Selic** (19% → 2% → 14%) torna
  retorno nominal incomparável entre épocas — daí a métrica primária ser excesso sobre CDI (ADR-002).
- **`strict=True` nos schemas:** nenhuma coluna ad hoc. Idempotência: duas rodadas do mesmo `raw/`
  têm de dar o **mesmo hash** (RF-048) — verificado nos 53 Parquets, em 2 rodadas `--offline`.

**Features:** **F-013** · **F-014** (leia D-h) · **F-015** · **F-016** · **F-017** · **F-018** ·
**F-029** — **todas classe C**.
