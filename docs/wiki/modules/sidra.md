# Módulo `sidra` — IBGE (SIDRA)

> Síntese — fonte de verdade: `docs/research/fontes-de-dados.md §A3` + `SPEC.md`. **Status: nenhum extrator implementado** (2026-10-10).

## Propósito

Extrair do IBGE o que o SGS não entrega com a abertura necessária: **IPCA em número-índice** e o **PIB
trimestral com abertura setorial** — esta última é o que permite cruzar macro com os setoriais da B3.
Arquivo previsto: `apps/pipeline/extract/ibge_sidra.py`.

## Séries / RFs cobertos

| Série | Identificador SIDRA | RF |
|---|---|---|
| IPCA nº-índice e variações | **t/1737** · `v/2266` (nº-índice), `v/63` (mensal), `v/2265` (12m) | RF-002 |
| PIB trimestral, volume **dessazonalizado** | **t/1621** · `v/584` · `c11255/90707` | RF-004 |
| PIB var. T/T-1 dessazonalizada | **t/5932** · `v/6564` · `c11255/90707` | RF-004 |
| Abertura setorial do PIB | `c11255`, 21 categorias (Agro `90687`, Indústria `90691`, Serviços `90696`, FBCF `93406`…) | RF-004 |

**Referências medidas:** `t/1621` PIB a preços de mercado → 2006T1 = 131,74 · 2006T3 = 134,36; `t/5932 v/6564` 2006T1 = 1,6 %.

## Fonte primária e fallback

- **Primária:** `apisidra.ibge.gov.br/values/t/{tab}/n1/all/v/{var}/p/{per}/c{classif}/{cat}` (sem auth); metadados em `servicodados.ibge.gov.br/api/v3/agregados/{tab}/metadados`.
- **Fallback:** **SGS 22109** é exatamente `t/1621 v/584 c11255/90707` numa chamada (confirmado valor a valor) — serve ao agregado, **não** à abertura setorial. IPCA: SGS 433/13522.

## Armadilhas conhecidas (pesquisa)

- **A primeira linha do array é cabeçalho**, não dado. `V` vem como **string**; `D3C/D3N` é o período (`200601` / "1º trimestre 2006").
- **R10 · encoding:** a API serve UTF-8, mas no Windows o default do locale (cp1252) **corrompe acentos** → declarar `encoding='utf-8'` em todo leitor (já quebrou na pesquisa).
- **Tabela errada é o erro mais provável:** `1620` é volume **sem** ajuste sazonal, `1621` **com** — trocar uma pela outra muda o eixo crescimento da V1 sem levantar exceção.
- **Look-ahead:** o PIB é revisado retroativamente e sai ~60 dias após o fim do trimestre → nenhum T pode ser classificado com PIB de T sem a flag `asof` (RF-025 / Anti-SPEC §10).
- **L13:** IPCA por grupos não tem série única 2006-2026 (`t/1419` 2012-2019, `t/7060` 2020+) → fora do escopo mínimo.

**Features do TODO:** **F-001** (infra) · **F-004** (extrator) · **F-015** (`macro_quarterly`) ·
**F-018** (`asof`×`revised`) · **F-019** (eixo crescimento da V1).
