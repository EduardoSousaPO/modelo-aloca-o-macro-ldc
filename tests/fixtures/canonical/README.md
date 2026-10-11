# `tests/fixtures/canonical/` — fixturas da camada canônica (F-013)

**Esta pasta não guarda Parquet.** É a exceção deliberada à convenção de
[`tests/fixtures/README.md`](../README.md), e o motivo está na regra que a própria convenção
estabelece: *fixture é dado **real da fonte**, nunca gerado à mão*. A camada canônica não tem
fonte — o insumo dela é `data/processed/`, que já é produto de outro código deste repositório e
já tem fixture própria por fonte (`sgs/`, `b3/`, `anbima-ima/`, …).

## Onde estão as fixturas, então

Geradas **dentro do teste**, em `tmp_path`, por
[`tests/unit/test_canonical_raw_series.py`](../../unit/test_canonical_raw_series.py):

| Helper | O que produz |
|---|---|
| `mini_serie(series_id, datas, valores, …)` | um mini `processed_series` de uma série **real do catálogo** — `source`, `freq` e `unit` são lidos de `load_catalog()`, nunca digitados |
| `painel_de_controle()` | 3 séries válidas (uma `D`, uma `M`, uma `Q`): o controle de todo teste de rejeição |
| `processed_minimo` (fixture pytest) | um `data/processed/` completo em `tmp_path`, com 3 Parquet de série + as 2 tabelas de schema próprio que o build tem de ignorar (`calendario/dias_uteis_anbima.parquet`, `tesouro-direto/td_painel.parquet`) |

**Por que derivar do catálogo e não escrever os valores no teste.** Se a fixture trouxesse
`source="BCB_SGS"` e `unit="%"` digitados, uma mudança no catálogo passaria pelo teste sem ser
notada — e `validar_procedencia` existe justamente para comparar a linha com o catálogo. Lendo de
`load_catalog()`, a fixture não pode divergir do contrato sem o teste quebrar.

## Dado sintético e a Anti-SPEC

Os valores das mini-séries são sintéticos e **só existem em `tmp_path`**: nenhum chega a
`data/`, nenhum é commitado (`CLAUDE.md §4`, Anti-SPEC §10.1.2, §10.4.21). Os três números
reais que aparecem nos testes são os **valores-canário** já conferidos na fonte por F-002, F-003 e
F-006 (IMA-B 16/09/2003 = 723,070317 · IBOV 01/02/2006 = 38.484,84 · IPCA 09/2026 = 0,82) e são
lidos do `data/processed/` real na seção C do arquivo de teste, que **pula** quando não há dado em
disco.

## Se um dia precisar de Parquet aqui

Só com um insumo que não seja reproduzível por `mini_serie` — por exemplo, um `data/processed/`
gravado por uma versão antiga do extrator, guardado para testar migração de schema. Nesse caso
vale a convenção da pasta-mãe: ≤ 200 KB, nome com `__<data>`, procedência neste README.
