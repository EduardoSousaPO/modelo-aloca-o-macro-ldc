# Módulo `anbima` — ANBIMA + Tesouro Direto (renda fixa pública)

> Síntese — fonte de verdade: `docs/research/fontes-de-dados.md §A4, §A5, §B6`. **Status: nenhum extrator implementado** (2026-10-10); contém o job mais urgente do projeto (**F-009**).

## Propósito

Cobrir a renda fixa pública: **índices IMA** (benchmark de RF do heatmap), **taxas de títulos públicos** e
a **inclinação da curva**. O **Tesouro Direto** entra aqui porque é o substituto aceito da ETTJ histórica
da ANBIMA (S-01/S-02 no `DECISIONS_LOG`); o **calendário de dias úteis** também, por ser insumo de todo o
alinhamento trimestral.

## Séries / RFs cobertos

| Série | Identificador | RF |
|---|---|---|
| IMA-B · 5 · 5+ | S3 `IMAB`, `IMAB5`, `IMAB5MAIS` (16/09/2003→) | RF-011 |
| IRF-M · 1 · 1+ · IMA-Geral · IMA-S | S3 `IRFM`, `IRFM1`, `IRFM1MAIS`, `IMAGERAL`, `IMAS` (01/02/2000→) | RF-011 |
| Taxas e PUs de títulos públicos | Tesouro Transparente `precotaxatesourodireto.csv` (31/12/2004→) | RF-008 |
| Vértices interpolados + inclinação real/nominal | derivado do Tesouro Direto | RF-009 |
| Job diário: taxas indicativas + Curva Zero | `ms{AAMMDD}.txt` · `CZ-down.asp` (**POST**) | RF-010 |
| Calendário de dias úteis / feriados | arquivo ANBIMA | RF-018 |

**Valor-canário:** IMA-B 16/09/2003 = **723,070317**.

## Fonte primária e fallback

- **Primária:** bucket **S3 público da ANBIMA** (`*-HISTORICO.xls`, grátis, sem cadastro) · CKAN do Tesouro Transparente · `anbima.com.br/informacoes/...` para o job diário.
- **Fallback:** SGS 12461-12469 (IMA) — **descontinuadas em 22/05/2023**, só conferência cruzada; ANBIMA Feed (**pago**, fora do caminho crítico); `pyield` para DI futuro.

## Armadilhas conhecidas (pesquisa)

- **R11 · formatos mentirosos:** o `.xls` do S3 **é XLSX** (magic `PK`) → `engine="openpyxl"` a partir de `BytesIO` (openpyxl recusa a extensão `.xls`); o `.xls` da Curva Zero **é HTML `<table>`** → `read_html` + `lxml`. Sniffar os 4 primeiros bytes sempre.
- **R8 · janela rolante de ~20 d.u.:** `ms*.txt` e Curva Zero apagam o passado (`Dt_Ref=02/01/2006` → 0 bytes). Nunca usar como backfill; **o job F-009 tem de estar ligado hoje** — cada dia sem ele é série proprietária perdida para sempre.
- **R14 · rótulos instáveis:** a coluna `Índice` alterna `IMA-B`/`IMA - B`, `IMA-GERAL`/`IMA - Geral` → normalizar removendo todo espaço antes de agrupar. O slug de "5+" é `5MAIS`.
- **R7/R12:** listagem do bucket bloqueada (`AccessDenied`) → slugs hard-coded + teste de disponibilidade; o arquivo é `ms{AAMMDD}.txt`, **não** `ms{ddmmaa}.txt`; encoding **latin-1** em `ms`/`CZ`/CSV do Tesouro.
- **R6/L5/R17:** não usar `data-api.prd.anbima.com.br` (JWT com reCAPTCHA de uso único → 418); sem ponta longa nominal antes de ~2010, a inclinação principal é **real** (S-03); arquivo atrasado é caso **normal** → retry + registro, nunca falha.

**Features do TODO:** **F-001** · **F-002** (S3 IMA) · **F-005** (Tesouro) · **F-008** (calendário) ·
**F-009** (job diário, URGENTE) · **F-016** (curva, C) · **F-017** (retornos de RF) · **F-030** (canário).
