# Módulo `sgs` — BCB (SGS + Olinda/Focus)

> Síntese — fonte de verdade: `docs/research/fontes-de-dados.md §A1-A2` + `SPEC.md`. **Status: nenhum extrator implementado** (2026-10-10).

## Propósito

Extrair do Banco Central o núcleo macro dos 20 anos — inflação, atividade, juros e câmbio
(`apps/pipeline/extract/bcb_sgs.py`) — e as expectativas do Focus pela API Olinda/OData v4
(`bcb_focus.py`). É a fonte de maior cobertura e menor esforço do projeto.

## Séries / RFs cobertos

| Série | Código | RF |
|---|---|---|
| IPCA mensal · IPCA 12m | SGS **433** · **13522** | RF-001 |
| IBC-Br dessazonalizado | SGS **24364** | RF-003 |
| Selic Over %/dia · % a.a. · meta | SGS **11** · **1178** · **432** | RF-005 |
| CDI %/dia · acumulado | SGS **12** · **4389** | RF-006 |
| PTAX BRL/USD venda | SGS **1** · **10813** | RF-015 |
| Focus — IPCA, Selic, PIB, câmbio | Olinda `ExpectativasMercado*` (5 EntitySets) | RF-007 |

## Fonte primária e fallback

- **Primária:** `api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados?formato=json` · `olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/...`
- **Fallback:** Ipeadata (`BM366_TJOVER366`, `BM12_TJOVER12`, `BM12_IPCAEXP1212`), SIDRA `t/1737` para IPCA, `python-bcb` (mas `sgs.search` **não existe**).

## Armadilhas conhecidas (pesquisa)

- **R1 · erro com HTTP 200:** série diária rejeita janela > 10 anos devolvendo JSON de erro com status 200, e série inexistente devolve HTML com 200. Fatiar diárias em ≤ 5 anos e validar que o corpo é *array*.
- **R2 · truncamento no Olinda:** `$top=20000` devolve 20.000 linhas **sem `nextLink`**; `$count` e `$apply` são ignorados sem erro. Omitir `$top` ou paginar com `$skip`.
- **Formatos/datas:** `$format=text/csv` do Olinda tem separador **e** decimal vírgula → usar JSON; PTAX no Olinda vem em `MM-DD-YYYY`, o SGS em `dd/mm/aaaa` (R12).
- **Sem metadados:** `/metadados` → 404 e `www3.bcb.gov.br/sgspub` → 502 → códigos versionados em `packages/shared/schemas/series_catalog_data.py`. Rate limit existe (429).
- **R16 · descontinuadas:** swaps 7801-7806/7816-7827 (set/2019) e IMA 12461-12469 (22/05/2023) **não servem** → ver S-02 e S-04 no `DECISIONS_LOG`.

**Features do TODO:** **F-001** (infra) · **F-003** (SGS) · **F-010** (Focus) · **F-011** (conectividade) ·
**F-013**/**F-015** (consomem na camada canônica).
