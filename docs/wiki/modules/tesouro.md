# Módulo `tesouro` — Tesouro Direto (taxas e PUs de títulos públicos)

> Verdade: `apps/pipeline/extract/tesouro_direto.py` + `research/fontes-de-dados.md §A4.1`.
> **Estado (2026-10-11): implementado** (F-005, aguardando QA da Onda 1). É a fonte **primária da
> curva de 20 anos** (ADR-004 / S-01, S-02): taxa e PU limpos desde 31/12/2004, insumo de **F-016**
> (vértices, inclinação, breakeven). **Nada é interpolado aqui.**

## `td_painel.parquet` — a convenção de `series_id` que F-016 consome

```
TD_<SIGLA>_<AAAAMMDD do vencimento>_<METRICA>        # TD_NTNB_20450515_TAXA_VENDA
SIGLA   ∈ LTN · NTNF · NTNB · NTNBP · NTNC · LFT · EDUCA · RENDA   (tradicional, sem hífen)
METRICA ∈ TAXA_COMPRA · TAXA_VENDA · PU_COMPRA · PU_VENDA · PU_BASE
```

Sigla **tradicional**, não o nome comercial (que já mudou: "Tesouro IPCA+" é a antiga NTN-B
Principal). `date` é a **Data Base** (dia da cotação); o prazo até o vencimento **não** é
materializado — F-016 calcula. Use `montar_series_id`/`decompor_series_id`, não reimplemente o split.
**Um** Parquet de painel, não 750 de 5 KB (melhor para o DuckDB — ADR-006 — e para o join), e
**nenhum** dos 750 `series_id` entra no `series_catalog`: lá ficam a *fonte* (`TESOURO_TD_PRECOTAXA`)
e as *derivadas* (`CURVA_*`, `INCLINACAO_*`, `BREAKEVEN_*`), de F-016.

**Medido no arquivo completo (2026-10-10):** 177.260 linhas de painel → **886.300 linhas longas, 750
`series_id`**; Data Base **2004-12-31** → 2026-10-09; 5.436 dias úteis distintos; 125 vencimentos;
**0 nulos** nas 8 colunas; **0 duplicatas** em `(sigla, vencimento, data base)`; **248 dias úteis em
2006** (CA-021 pede ≥ 240). `vintage` = data do `collected_at` do manifesto (D-b).

## A ponta longa de 2006 — o número de que ADR-004 depende

**NTNB:** 10 vencimentos em 2006, o mais longo **2045-05-15** → curva **real** completa desde 2006.
**LTN:** 11, o mais longo 2009-01-01 (~3 anos). **NTNF:** 4, o mais longo 2014-01-01 (~8 anos).
NTNC 2031-01-01 · LFT 2012-03-07 · NTNBP 2024-08-15. → **o vértice nominal de 10 anos não existe em
2006**, o que confirma ADR-004: inclinação **real** é a variável principal, nominal 5a×1a é
secundária, e nada de extrapolar a ponta nominal antes de ~2010. `EDUCA` (2023-08-01) e `RENDA`
(2023-01-30) entram porque estão no arquivo, mas são séries curtas — quem usar no modelo filtra; não
há flag de "série curta" na camada processada.

## Armadilhas (as 4 primeiras corrigem a pesquisa)

1. **O download NÃO exige User-Agent de browser:** `Session.headers.clear()` devolveu 200 e os
   14.584.922 B — a exigência de UA vale para a **API do CKAN**, não para `/download/`.
2. **A rota ignora o nome do arquivo na URL**; só o **UUID do recurso** importa (errado → 404 + HTML).
3. **O arquivo é 100% ASCII e usa LF:** o "teste de acento" de CA-022 **não é satisfazível com o dado
   real** — quem cobre é fixture **sintética nomeada como tal**.
4. **Não há separador de milhar** (`"20046,46"`) em nenhuma das 886.300 células numéricas.
5. **Taxa `0,00` e negativa são valores reais** da LFT (`-0,02` em 02/01/2006): nunca tratar como
   ausência, nunca substituir por `0` o que falta.
6. **Cache condicional funciona:** `ETag` + HTTP **304 com 0 byte** nas duas variantes — o fluxo
   normal **não** transfere 14,6 MB. A *política* de quando revalidar é F-030.
7. **Convenção invertida vs. ANBIMA:** aqui `Taxa Compra < Taxa Venda`, na ANBIMA o contrário. NTN-B
   2045 em 09/10/2026: TD 6,53/6,65 contra indicativa ANBIMA 6,606 (~4 bps de spread de varejo). Em
   toda figura: *taxas do Tesouro Direto (varejo), não a curva Svensson oficial*.

**Features:** **F-005** (implementado) · **F-016** (curva, classe C) · **F-030** (cache/canário).
