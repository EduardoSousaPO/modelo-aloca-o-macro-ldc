# Módulo `anbima` — ANBIMA + Tesouro Direto (renda fixa pública)

> Síntese — fonte de verdade: `docs/research/fontes-de-dados.md §A4, §A5, §B6`. **Estado (2026-10-10): só o job diário F-009 está implementado** (`apps/pipeline/jobs/anbima_daily.py`, aguardando QA); nenhum extrator de histórico.

## Propósito

Cobrir a renda fixa pública: **índices IMA** (benchmark de RF do heatmap), **taxas de títulos públicos** e a **inclinação da curva**. O **Tesouro Direto** entra aqui por ser o substituto aceito da ETTJ histórica da ANBIMA (S-01/S-02 no `DECISIONS_LOG`); o **calendário de dias úteis** também, por ser insumo de todo o alinhamento trimestral.

## Séries / RFs cobertos

| Série | Identificador | RF |
|---|---|---|
| IMA-B · 5 · 5+ | S3 `IMAB`, `IMAB5`, `IMAB5MAIS` (16/09/2003→) | RF-011 |
| IRF-M · 1 · 1+ · IMA-Geral · IMA-S | S3 `IRFM`, `IRFM1`, `IRFM1MAIS`, `IMAGERAL`, `IMAS` (01/02/2000→) | RF-011 |
| Taxas e PUs de títulos públicos | Tesouro Transparente `precotaxatesourodireto.csv` (31/12/2004→) | RF-008 |
| Vértices interpolados + inclinação real/nominal | derivado do Tesouro Direto | RF-009 |
| Job diário: taxas indicativas + Curva Zero | `ms{AAMMDD}.txt` · `CZ-down.asp` (**POST**, `saida=csv`) | RF-010 |
| Calendário de dias úteis / feriados | arquivo ANBIMA | RF-018 |

## Fonte primária e fallback

- **Primária:** bucket **S3 público da ANBIMA** (`*-HISTORICO.xls`, grátis, sem cadastro) · CKAN do Tesouro Transparente · `anbima.com.br/informacoes/...` para o job diário. **Valor-canário:** IMA-B 16/09/2003 = **723,070317**.
- **Fallback:** SGS 12461-12469 (IMA) — **descontinuadas em 22/05/2023**, só conferência cruzada; ANBIMA Feed (**pago**, fora do caminho crítico); `pyield` para DI futuro.

## Job diário (F-009) — medido em 2026-10-10

- **Bordas reais da janela rolante:** `ms*.txt` só tem dado desde **2026-09-11** (09 e 10/09 → HTTP **404**); Curva Zero desde **2026-09-14** (11/09 e antes → HTTP **200 com 0 bytes**). Mais novo nas duas: 09/10. São ~20-21 d.u. e a borda **anda todo dia útil**.
- **Formato real da Curva Zero:** usar **`saida=csv`** (CSV latin-1: betas Svensson + 65 vértices). **`saida=xls` devolve HTML `<table>`**, não planilha — decidir o leitor pelo magic byte, nunca pela extensão.
- **Convenção de arquivo:** `data/raw/anbima-ms/ms_AAMMDD.txt` e `data/raw/anbima-ettj/cz_AAMMDD.csv`, cada um com **manifest sidecar** `<arquivo>.manifest.json` (`url`, `data_ref`, `sha256`, `bytes`, `collected_at`, formato, encoding, nº de registros, veredito). Republicação da mesma data com conteúdo diferente vira **vintage novo** (`__v2`), nunca sobrescrita. `Msec_txt.txt` (URL do último dia útil) veio byte a byte idêntico a `ms_261009.txt`.

## Armadilhas conhecidas (pesquisa)

- **R11 · formatos mentirosos:** o `.xls` do S3 **é XLSX** (magic `PK`) → `engine="openpyxl"` a partir de `BytesIO` (openpyxl recusa a extensão `.xls`); o `.xls` da Curva Zero **é HTML `<table>`** → `read_html` + `lxml`. Sniffar os 4 primeiros bytes sempre.
- **R8 · janela rolante de ~20 d.u.:** `ms*.txt` e Curva Zero apagam o passado (`Dt_Ref=02/01/2006` → 0 bytes). Nunca usar como backfill; **o job F-009 tem de estar ligado** — cada dia sem ele é série proprietária perdida para sempre.
- **R14 · rótulos instáveis / R7 · R12:** a coluna `Índice` alterna `IMA-B`/`IMA - B`, `IMA-GERAL`/`IMA - Geral` → normalizar removendo todo espaço antes de agrupar, e o slug de "5+" é `5MAIS`; listagem do bucket bloqueada (`AccessDenied`) → slugs hard-coded + teste de disponibilidade; o arquivo é `ms{AAMMDD}.txt`, **não** `ms{ddmmaa}.txt`; encoding **latin-1** em `ms`/`CZ`/CSV do Tesouro.
- **R6/L5/R17:** não usar `data-api.prd.anbima.com.br` (JWT com reCAPTCHA de uso único → 418); sem ponta longa nominal antes de ~2010, a inclinação principal é **real** (S-03); arquivo atrasado é caso **normal** → retry + registro, nunca falha.

**Features do TODO:** **F-001** · **F-002** (S3 IMA) · **F-005** (Tesouro) · **F-008** (calendário) ·
**F-009** (job diário, implementado) · **F-016** (curva, C) · **F-017** (retornos de RF) · **F-030** (canário).
