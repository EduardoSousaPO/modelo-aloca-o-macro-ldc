# Módulo `tesouro` — Tesouro Direto (taxas e PUs) + curva interpolada

> Verdade: `extract/tesouro_direto.py` (F-005) · `canonical/curva.py` (F-016) ·
> `research/fontes-de-dados.md §A4.1`. **Estado (2026-10-11):** F-005 **QA APROVADO**; F-016
> **implementada, QA pendente**. **Fonte primária da curva de 20 anos** (ADR-004 / S-01, S-02), taxa
> e PU limpos desde 31/12/2004. **Nada é extrapolado: vértice sem suporte é `NULL` com motivo.**

## `td_painel.parquet` — a convenção de `series_id` que F-016 consome

```
TD_<SIGLA>_<AAAAMMDD do vencimento>_<METRICA>        # TD_NTNB_20450515_TAXA_VENDA
SIGLA   ∈ LTN · NTNF · NTNB · NTNBP · NTNC · LFT · EDUCA · RENDA   (tradicional, sem hífen)
METRICA ∈ TAXA_COMPRA · TAXA_VENDA · PU_COMPRA · PU_VENDA · PU_BASE
```

Sigla **tradicional**, não o nome comercial. `date` é a **Data Base**; o prazo até o vencimento
**não** é materializado — F-016 calcula. Use `montar_series_id`/`decompor_series_id`. **Um** Parquet
de painel, não 750 de 5 KB (melhor para o DuckDB — ADR-006 — e para o join), e **nenhum** dos 750
`series_id` entra no `series_catalog`: lá ficam a *fonte* (`TESOURO_TD_PRECOTAXA`) e as 11
*derivadas* de F-016. **Medido:** 177.260 linhas → **886.300 linhas longas, 750 `series_id`**,
2004-12-31 → 2026-10-09, **5.436** dias úteis distintos, 125 vencimentos, **0 nulos**, **0
duplicatas**, **248 d.u. em 2006** (CA-021 pede ≥ 240). `vintage` = data do `collected_at` do
manifesto (D-b); bruto **sem** manifesto é recusado (`ManifestoAusente`).

## F-016 — as 11 séries da curva, em `data/processed/curva/`

Remonta a seção transversal `(prazo, taxa)` de cada data base por **família** (`REAL` = NTN-B +
NTN-B Principal · `NOMINAL` = LTN + NTN-F), interpola **linearmente no prazo** para **1, 3 e 5
anos**, deriva as 4 inclinações (`5a−3a` e `5a−1a`, em `pp`) e o **breakeven de 5 anos por razão**:
**11 séries × 5.436 linhas**, `fonte=DERIVADO`, 2004-12-31 → 2026-10-09. Cinco escolhas carregam o
número: **`TAXA_VENDA`** (a `TAXA_COMPRA` traz `0,00` quando o título não está à venda — ausência
disfarçada); **família, não título** (dois no mesmo vencimento viram um ponto pela **média**, com
diferença de mediana **0,0 bps**); **prazo em dias corridos** (**D-j** — o calendário de F-008 acaba
em 2030 e os vencimentos chegam a 2060; custo 0,14 a 0,41 bps); **sem extrapolação**
(`vertice_extrapolado` + 1 de 4 motivos); **breakeven por razão**, que reproduz a "Inflação
Implícita" da ANBIMA com erro de **0,01 bp** — a subtração erra ~37 bps. Cobertura de 2006+:
`CURVA_REAL_5A`, `CURVA_NOMINAL_3A` e `CURVA_NOMINAL_5A` 100%, `CURVA_NOMINAL_1A` 97,57%,
**`CURVA_REAL_3A` 95,25%**, `CURVA_REAL_1A` **60,53%** — é o achado de **D-i**:
`INCLINACAO_REAL_5A_3A` (95,25%) é a variável principal de regime e as duas 5a−1a ficam
**secundárias e declaradas**. Contra a Curva Zero ANBIMA de 09/10/2026 as diferenças são de **6 a 20
bps**, todas no mesmo sinal (spread de varejo + YTM interpolado ≠ spot de Svensson): **nenhuma
figura pode chamar isto de curva ANBIMA** (ADR-004 §7, CA-026). **A ponta longa de 2006**, de que
ADR-004 depende: 10 vencimentos de NTN-B (o mais longo **2045-05-15** → real completa desde 2006),
mas LTN até 2009 e NTN-F até 2014 — **o vértice nominal de 10 anos não existe em 2006** (36,81% de
2006+, medido e **não** gravado). `EDUCA`, `RENDA`, `LFT` e `NTNC` ficam fora da curva.

## Armadilhas (as 2 primeiras corrigem a pesquisa)

1. **O download NÃO exige UA de browser** (vale para a **API do CKAN**, não `/download/`) e **a rota
   ignora o nome do arquivo** na URL — só o **UUID** importa (errado → 404 + HTML).
2. **O arquivo é 100% ASCII, usa LF e não tem separador de milhar** (`"20046,46"`): o "teste de
   acento" de CA-022 **não é satisfazível com o dado real** — cobre-o fixture sintética nomeada.
3. **Cache condicional funciona:** `ETag` + HTTP **304 com 0 byte** (política de revalidação é
   F-030). **Taxa `0,00` e negativa são reais** (LFT `-0,02`; NTN-B com juro real negativo em
   2020-21): nunca tratar como ausência.
4. **`NTNBP` é "Tesouro IPCA+" e `NTNB` é "…com Juros Semestrais"** — o comercial está *invertido*
   vs. a sigla (`SIGLA_POR_TIPO` é a verdade). E **`--metrica-prazo dias_uteis` grava em cima das
   séries padrão**: o que distingue é `metrica_prazo` no `relatorio_curva.json`.
5. **Convenção invertida vs. ANBIMA:** aqui `Taxa Compra < Taxa Venda`; NTN-B 2045 em 09/10/2026 é
   6,53/6,65 no TD contra 6,606 na indicativa (~4 bps). Em toda figura: *taxas do TD (varejo), não a
   curva Svensson oficial*.

**Features:** **F-005** (QA aprovado) · **F-016** (curva, classe C, QA pendente) · **F-030**.
