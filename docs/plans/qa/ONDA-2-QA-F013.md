# QA independente — Onda 2 · F-013 (`raw_series` + `series_catalog` materializados)

**Classe:** C · **Commit:** `65d2fb9` (`main`, árvore limpa) · **Data:** 2026-10-11 · **Modo:**
Validation Mode (`AGENTS.md §15`), `uv run`, sem rede · **Revisor:** subagente de QA + revisão
numérica independente (não implementou nada; código de conferência próprio, zero reuso das funções
do build para os números)
**Veredito: `MUDANÇAS_SOLICITADAS`** — 3 × P1, 7 × P2, 0 × P0. O **código está correto**; o
**artefato publicado em `data/canonical/` não é reproduzível a partir do código commitado**.

> **Não reconstruí `data/canonical/`.** A CLI não tem `--saída`, mas `construir()` aceita `raiz=` +
> `raiz_processed=`: rodei o build 2× num diretório de scratch lendo o `data/processed/` real
> (somente leitura). `sha256` dos 3 artefatos conferido antes e depois de cada experimento —
> inalterados. F-014/F-016 não foram tocados.

---

## 1. CI real (colado)

```
$ uv run ruff check .                 -> All checks passed!
$ uv run ruff format --check .        -> 52 files already formatted
$ uv run pytest tests/unit tests/contract -m "not network" -q
                                      -> 619 passed, 15 deselected, 1 xfailed in 8.87s
  tests/unit isolado -> 594 passed, 15 deselected, 1 xfailed
  só F-013 (test_canonical_raw_series.py + test_raw_series_schema.py) -> 59 passed in 3.15s
```

CI verde. Nota: `F-013.md §7` reporta "594 passed" como se fosse o portão inteiro — 594 é
`tests/unit` **sozinho**; o portão `tests/unit tests/contract` dá **619**. Erro de redação, não
de código (**P2-5**).

## 2. Arquivos alterados vs. permitidos

| Desvio | Veredito |
|---|---|
| `canonical/build_raw_series.py` em vez de `load/{raw_series,catalog}.py` | **Aceitável.** O briefing da onda fixou `canonical/` + a CLI `python -m apps.pipeline.canonical.build_raw_series`; a pasta casa com a saída e com `wiki/modules/canonical.md`. Um módulo só é justificado (o catálogo materializado reusa o mesmo DataFrame; separar = 2ª travessia de `data/processed/`). Nenhum CA muda. |
| marker `integration` não criado; `tests/integration/test_camada_raw.py` → seção C de `tests/unit/` | **Aceitável.** Confirmado: `pyproject.toml` tem `addopts = "-q --strict-markers"` e `markers = [network, slow]` — `@pytest.mark.integration` **falharia a coleta**. Não tocar o `pyproject` congelado foi certo; o débito (1 linha + mover a seção C) é do orquestrador. |
| `ldc.duckdb` vs. `macro.duckdb` (ADR-006 §(a).2) | **Aceitável, mas pendura o ADR.** Confirmado `macro.duckdb` no ADR-006 linha 36 e `NOME_DUCKDB = "ldc.duckdb"`. Zero semântica; 1 linha editorial resolve (**P2-6**). |

**Schema existente alterado?** `SeriesCatalogSchema` (pandera) e `RawSeriesSchema`: **intocados** —
confirmado no diff; `series_catalog.py` ganhou `SeriesCatalogMaterializedSchema` (+78 linhas, puro
acréscimo). **Mas o diff do commit não é só `+`:** `SeriesCatalogEntry` ganhou o campo `calendario`
+ validator, e `series_catalog_data.py` ganhou 7 edições (`calendario=…`, `is_total_return=False`
em `YAHOO_GSPC`, textos de `obs`) — correções de **P1-2 da Onda 1**, legítimas, porém
**misturadas no mesmo commit** (20 arquivos fora do escopo de F-013). Commit não atômico
(**P2-5**) — e é a causa raiz de **P1-1**.

## 3. Revisão numérica independente (código próprio)

51 parquets descobertos por mim em `data/processed/*/` (53 − `td_painel` − calendário).
**49 conferências OK, 0 divergências de dado.**

| Conferência | Resultado |
|---|---|
| linhas / séries / 8 colunas na ordem do contrato | **218.643** / **51** ✅ |
| cada série **idêntica linha a linha** à origem (`assert_frame_equal`, `check_exact=True`, 8 col.) | **51/51 idênticas, 0 divergentes**; soma das origens 218.643 = canônico ✅ |
| PK `(series_id,date,vintage)` única · `date <= collected_at` | 0 duplicata ✅ · ✅ |
| nulos: `value` **1.439** (0,658151%); demais 7 colunas **0** | ✅ 6 séries: `YAHOO_DXY` 1.210, `YAHOO_VIX` 210, `SIDRA_1737_V2265` 12, `YAHOO_TNX` 5, `SIDRA_1737_V63` 1, `SIDRA_5932_V6564_90707` 1 |
| janela 1979-12-31 → 2026-10-10 | ✅ (mín. = número-índice do IPCA, SIDRA t/1737 — não é bug de janela) |
| `vintage` sem hora | ✅ (`2026-10-10` 21 séries, `2026-10-11` 30 séries) |
| M/Q em **fim de período civil** (D-a) | 3.866 linhas M+Q, **0 fora** de fim de mês; `Q` só em mar/jun/set/dez ✅ |
| `freq` · `source` | D 214.777 · M 3.320 · Q 546 ✅ — ANBIMA_S3 54.950 · B3_API 54.650 · BCB_SGS 44.445 · MSCI 26.904 · YAHOO 24.351 · DERIVADO 11.291 · IBGE_SIDRA 2.052 ✅ |
| 0 `series_id` fora do catálogo (134); `source`/`unit`/`freq` = catálogo; `fonte_url` http | ✅ 51/51 (CA-055/CA-120) |
| `series_catalog.parquet` **134 × 25**; `presente_no_processed`, `data_inicio_observada`, `data_fim_observada`, `n_obs`, `cobre_1t2006` recalculados | ✅ coluna a coluna, 134/134 |
| `pct_nulos` recalculado | ✅ **= `round(meu, 6)`** nas 51; arredondamento não documentado (**P2-3**) |
| 51 presentes / 83 ausentes (sem observação: `n_obs=0`, janela NULL); 48 das 51 cobrem 1T2006 | ✅ (não cobrem: `B3_ICON` 2006-12-28, `B3_IMOB` 2007-12-28, `B3_IFIX` 2010-12-30 — pontos-base; Anti-SPEC §10.1.1 proíbe backfill) |
| **3 canários** | `ANBIMA_IMAB` 2003-09-16 = **723.070317** (`index`/ANBIMA_S3) ✅ · `B3_IBOV` 2006-02-01 = **38484.84** (`index`/B3_API) ✅ · `BCB_SGS_433` 2026-09-30 = **0.82** (`%`/BCB_SGS) ✅ |
| DuckDB | `count(*) = 218643` **=** pandas · `count(distinct series_id) = 51` **=** pandas · `series_catalog = 134`; os 2 objetos são **VIEW** ✅ |
| relatório: `arquivos_lidos=51`, `series=51`, 2 excluídas com motivo, 40 ausentes, sem hora de geração | ✅ |

### Hashes — onde quebra

| Artefato | em disco | `relatorio_build.json` | **rebuild 2× em scratch** |
|---|---|---|---|
| `raw_series.parquet` | `79edba9a…` | `79edba9a…` ✅ | `79edba9a…` ✅ **reproduz** |
| `series_catalog.parquet` | `c38a3218…` | `c38a3218…` ✅ | `69c34073…` ❌ **não reproduz** |
| `relatorio_build.json` | `c207c7b5…` | (auto) ✅ | `282143ec…` ❌ **não reproduz** |
| `versao_build` | `2df867d6…` = `sha256(build_raw_series.py)` ✅ | igual nas duas rodadas |

As duas rodadas em scratch deram hashes **idênticos entre si** → o build é idempotente (CA-121 vale
para o build). Falha a **correspondência entre artefato publicado e código commitado** (P1-1).

## 4. Pontos cegos atacados (os 5 declarados + os meus)

1. **Duplicata idêntica vs. divergente** (§6.5). Fixtura própria em `tmp_path`: PK ×2 idêntica →
   **removida**, build segue, `_log.info`; `value` divergente → **`SerieInconsistente`** ✅;
   `value=100` vs `NaN` → recusa ✅; build e2e com um processed idêntico e um divergente → recusa o
   divergente ✅. **Mas o caminho "idêntico" tem dois defeitos: P1-3 e P2-1.**
2. **`versao_build` não muda quando `series_catalog_data.py` muda** (§6.4). **Risco real e já
   realizado** — é o P1-1. Proposta: `versao_build` = hash do **conjunto** (`build_raw_series.py` +
   `raw_series.py` + `series_catalog.py` + `series_catalog_data.py`) em ordem fixa, gravado como
   `versao_build_componentes`. ~6 linhas; torna "artefato velho" detectável.
3. **`freq=D` com buracos de meses** (§6.2). Confirmado: buraco de 5 meses numa série D **passa**
   `validar_frequencia_nativa`. **Deve passar** — buraco é dado; quem julga é F-014. Sem ação.
4. **`pct_nulos` sem limiar** (§6.3). Confirmado: série **100% nula** passa o build inteiro com
   `pct_nulos = 100.0`, sem aviso. Máximo real 17,41% (`YAHOO_DXY`, fora do pacote mínimo). **P2-4**.
5. **`cobre_1t2006` vs. IBOV começando 2006-01-02.** Bool **correto**: `B3_IBOV`
   `data_inicio_observada = 2006-01-02` → `True` ✅ (idem `BCB_SGS_433`, `ANBIMA_IMAB`). Limiar
   inclusivo; `2006-02-01` daria `False` — semântica certa. Sem ação.
6. **Painel do Tesouro fora de `raw_series` (CA-055/§6.1).** Decisão **bem fundamentada** e
   registrada no dado (`relatorio_build.json → tabelas_excluidas`): os 750 `series_id` compostos
   (`TD_<SIGLA>_<AAAAMMDD>_<METRICA>`) **não existem no catálogo**, então admiti-los violaria
   CA-055/CA-120 ou exigiria 750 entradas novas — mudança de contrato, não de implementação. O
   catálogo já tem `CURVA_*`/`INCLINACAO_*`/`BREAKEVEN_5A` (`fonte=DERIVADO`). **Conclusão: F-016
   deve mesmo acrescentá-las** lendo `data/processed/tesouro-direto/` e publicando
   `data/processed/curva/` com `series_id` do catálogo — F-013 não muda. Ajuste: F-016 precisa
   reexecutar este build para reescrever `raw_series` (não há append) — pôr na DoR.
7. **Meus, extra.** CA-057/CA-075 fora do pytest: coluna ausente **e** valor `None` em
   `source`/`series_id` → `SchemaError` nos 4 casos ✅. `collected_at` tem hora real
   (`00:28:03.041031`) e `vintage` é data pura — correto (vem do manifesto), mas o relatório trunca
   `collected_at_max` a data (**P2-7**). Nenhuma série real tem 2 `vintage` → **CA-056 só em
   fixtura** (aceitável: é CA de schema/PK).

## 5. Achados

### P1-1 — `series_catalog.parquet` e `relatorio_build.json` publicados estão **obsoletos**
O build rodou às 22:40; `series_catalog_data.py` foi editado depois (correções da Onda 1) e
commitado às 23:13 — o artefato em disco **não** é o que o código commitado produz. Reprodução (não
escreve em `data/`): `construir(raiz=<tmp>, raiz_processed=<repo>/data/processed, com_duckdb=False)`
→ `sha256(series_catalog.parquet) = 69c34073…` ≠ `c38a3218…` em disco. Divergem **2 células**:
| Série | Coluna | em disco | código commitado |
|---|---|---|---|
| `YAHOO_GSPC` | `is_total_return` | `NULL` | `False` |
| `BCB_SGS_432` | `obs` | sem a nota | `… Publica em DIA CORRIDO … 2.377 dos 8.319 pontos (28,6%) caem em fim de semana` |

Impacto: (i) os hashes de `F-013.md §5.4` e do relatório não reproduzem — CA-118/CA-119 sem lastro;
(ii) quem ler o materializado vê `is_total_return = NULL` para o S&P 500 onde o catálogo declara
`False` — a flag de Anti-SPEC §10.2.12; (iii) `versao_build` é **idêntico**, então a regra de
diagnóstico do próprio pack ("código igual + relatório diferente = bug") dispara.
**Ação:** rebuild depois que F-014/F-016 liberarem o arquivo, atualizar os 3 hashes de
`F-013.md §5.4`, e implementar a proposta do item 4.2.

### P1-2 — o campo `calendario` não chega ao catálogo materializado
`SeriesCatalogSchema` tem `strict = True` e 19 colunas fixas; `calendario` entrou em
`SeriesCatalogEntry` (pydantic) mas **não** na classe pandera, então o materializado publica 25
colunas **sem** `calendario` (verifiquei: a coluna não existe no Parquet). O consumidor nomeado na
própria docstring do campo ("a camada canônica, o alinhamento trimestral, qualquer contagem de
dias") continua sem saber que 28,6% dos pontos de `BCB_SGS_432` caem em fim de semana — e, por
P1-1, a nota em `obs` também está ausente do artefato. F-014 é justamente quem precisa disso.
**Ação:** +1 linha (`calendario: Series[str] = pa.Field(nullable=True, isin=(…))`) + rebuild.

### P1-3 — o dedup por PK **cega** `validar_sem_mistura_de_fontes` (CA-077/CA-055)
`consolidar()` compara **só `value`** para decidir se a duplicata é divergente, e remove com
`keep="first"`; as guardas rodam **depois**. Logo, duas linhas com mesma PK, mesmo `value` e
`source` **diferente** colapsam em silêncio e CA-077 nunca vê a mistura. Reprodução em scratch
(5 linhas de `B3_IBOV` duplicadas com `source="YAHOO"`): `BUILD PASSOU: 5 linhas,
sources=['B3_API']` — a linha YAHOO foi apagada sem log e sem registro no relatório. É o cenário
"substituição de fonte em silêncio" de Anti-SPEC §10.3.19. **Correção sugerida (não aplicada):**
a checagem de divergência deve usar as 8 colunas (ou ao menos `value, source, unit, freq`).

### P2
- **P2-1 — contagem errada no log do dedup (bug ≤ 10 linhas, NÃO corrigido).**
  `build_raw_series.py:269` → `_log.info("dedup: %d linha(s) …", int(duplicadas.sum()) // 2)`. O
  `// 2` presume 2 cópias por PK. Medido: 3 cópias → removeu 2, logou **1**; 5 → removeu 4, logou
  **2**; 3 PK×2 + 1 PK×3 → removeu 5, logou **2**. Correto:
  `len(saida) - len(saida.drop_duplicates(subset=list(PK_RAW_SERIES)))`.
- **P2-2 — dedup sem rastro no dado:** só `_log.info`; `relatorio_build.json` não tem
  `linhas_dedup`. Em classe C cujo contrato é "a procedência está no dado", é lacuna.
- **P2-3** — `pct_nulos` é `round(x, 6)`, não declarado em `F-013.md §4` nem em `CONTRACTS.md`.
- **P2-4** — `pct_nulos` sem limiar: série 100% nula passa (confirmado em `tmp_path`).
- **P2-5** — commit não atômico (F-013 + 20 arquivos da Onda 1) e `F-013.md §7` reporta 594 (só
  `tests/unit`) como se fosse o portão (619).
- **P2-6** — `ldc.duckdb` vs. `macro.duckdb` (ADR-006 linha 36): decidir qual lado corrige.
- **P2-7** — `CONTRACTS.md` não cita `SeriesCatalogMaterializedSchema`, as 6 colunas observadas nem
  `calendario` (0 ocorrências de `data_inicio_observada`); e o relatório trunca `collected_at_max`
  a data enquanto a coluna tem hora. Doc do orquestrador (`AGENTS.md §13`).

**Condição conhecida, não bloqueia:** ADR-006 está em **`Proposta`** (confirmado no arquivo); o Edu
autorizou desenvolver com padrões provisórios (`DECISIONS_LOG §2`, 2026-10-10). **Registrado, não
bloqueado.** O gate de **publicação** segue duro (`AGENTS.md §14` passo 2 / ADR-001).

## 6. Matriz `CA | teste | tipo | status | evidência`

| CA | Teste | Tipo | Status | Evidência minha |
|---|---|---|---|---|
| CA-053 | `test_catalogo_valida_e_nenhum_identificador_e_vazio` | contract | ✅ | 134 entradas, 0 identificador vazio/branco, `confianca` em todas — recalculado sobre `SERIES_CATALOG` |
| CA-054 | `test_identificador_a_confirmar_implica_status_a_confirmar` | contract | ✅ | `identificador == "a_confirmar"` ⇒ `status == "a_confirmar"`; nenhuma delas em `raw_series` |
| CA-055 | `validar_procedencia` + `test_real_todas_as_guardas_passam_no_dado_em_disco` | integration | ⚠️ | 51/51 no catálogo, `source`/`unit`/`freq` batem, 51/51 com `fonte_url` http — **P1-3** fura a guarda num caso construível |
| CA-056 | `test_duas_extracoes_coexistem_como_vintages_distintos` | contract | ✅ (fixtura) | PK única 0 dup; 2 `vintage` no dado real, mas **nenhuma série tem 2** → só fixtura |
| CA-057 | `test_linha_sem_{source,series_id}_e_rejeitada` | contract neg. | ✅ | fora do pytest: coluna ausente **e** valor `None` → `SchemaError` nos 4 casos |
| CA-058 | `test_serie_mensal_reamostrada_para_trimestral_e_rejeitada` (+3) | unit neg. | ✅ | 3.866 linhas M/Q 100% em fim de mês civil; `Q` só mar/jun/set/dez; `freq` nativa em 51/51 |
| CA-075 | `test_coluna_de_origem_ausente_e_rejeitada` | contract neg. | ✅ | validate sem `source` → `SchemaError`; nada gravado (`test_nada_e_gravado_quando_o_portao_recusa`) |
| CA-076 | `test_exigir_serie_ausente_devolve_bloqueado_fonte_indisponivel` | unit neg. | ✅ | `BLOQUEADO — FONTE INDISPONÍVEL`; 40 ausentes relatadas, **0 preenchida** (83/83 com `n_obs=0`, janela NULL) |
| CA-077 | `test_mistura_de_fontes_na_mesma_serie_e_rejeitada` | contract | ⚠️ | funciona quando a mistura sobrevive ao dedup; **P1-3**: mesma PK + mesmo `value` + `source` diferente é apagada antes |
| CA-120 | `test_toda_serie_do_materializado_tem_fonte_url` | integration | ✅ | 0 nulos nas 7 colunas de procedência; toda linha resolve até a URL |
| CA-121 | `test_build_e_idempotente_mesmo_sha256_em_duas_execucoes` | unit | ⚠️ | 2 rodadas em scratch → hashes idênticos ✅; **`raw_series` reproduz o publicado, catálogo e relatório não** (P1-1) |
| Anti-SPEC §10.1.1/.2 | `test_catalogo_materializado_nao_herda_janela_declarada_para_serie_ausente` | contract | ✅ | 0 valor inventado: 51/51 idênticas célula a célula (`check_exact`); 3 séries sem 1T2006 sem backfill |
| Anti-SPEC §10.4.24/.28 | `strict=True` + `test_coluna_ad_hoc_e_rejeitada` | contract neg. | ✅ | exatamente as 8 colunas; freq nativa preservada (D/M/Q) |
| Anti-SPEC §10.4.21/.23 | `.gitignore` + `-m "not network"` | CI | ✅ | nenhum `.parquet`/`.duckdb` no commit (só fixturas <18 KB); 15 testes de rede deselecionados |

## 7. Veredito

**`MUDANÇAS_SOLICITADAS`.** O desenho é sólido e o número central é **confirmado de forma
independente**: 218.643 linhas, 51 séries, 51/51 idênticas célula a célula à origem, 3 canários
exatos, catálogo materializado recalculado coluna a coluna, DuckDB = pandas. Não aprovo porque
(a) o artefato publicado não é reproduzível a partir do código commitado (P1-1, 2 células) —
`AGENTS.md §15.9` e `CLAUDE.md §9` mandam `MUDANÇAS_SOLICITADAS` em divergência no artefato;
(b) a correção P1-2 da Onda 1 não chega ao consumidor (P1-2); (c) uma guarda de Anti-SPEC é
contornável por construção (P1-3).

**Para liberar:** corrigir P1-2 (+1 linha no schema) e P1-3 (divergência pelas 8 colunas); rebuild
de `data/canonical/` **depois** que F-014/F-016 soltarem o arquivo; atualizar os 3 hashes de
`F-013.md §5.4`; endereçar P2-1. P2-2..P2-7 vão para a onda seguinte. **ADR-006 em `Proposta`:
registrado, não bloqueia** — publicação segue gated.
