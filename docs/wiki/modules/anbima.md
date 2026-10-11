# Módulo `anbima` — índices IMA (bucket S3) + job diário de janela rolante

> Verdade: `apps/pipeline/extract/anbima_s3.py`, `apps/pipeline/jobs/anbima_daily.py` +
> `research/fontes-de-dados.md §A4, §A5, §B6`. **Estado (2026-10-11): F-002 e F-009 implementados**
> (F-009 com QA aprovado; F-002 aguardando QA da Onda 1). Curva do Tesouro →
> [`tesouro.md`](./tesouro.md); calendário de dias úteis → [`calendario.md`](./calendario.md).
> Entrega o benchmark de RF do heatmap (IMA, diário, desde 2000) e **arquiva** as duas séries de
> janela rolante da ANBIMA, que se perdem para sempre se o job não rodar.

## `data/processed/anbima-ima/` — 9 séries, 0,00% de nulos, `freq=D`, `unit=index`

| `series_id` | linhas | janela | 1º valor | último |
|---|---|---|---|---|
| `ANBIMA_IMAB` · `IMAB5` · `IMAB5MAIS` | 5.795 | **2003-09-16** → 2026-10-09 | **723,070317** · 775,879343 · 715,675793 | 12.656,5 · 12.107,2 · 14.075,9 |
| `ANBIMA_IRFM` | 6.700 | **2000-02-01** → 2026-10-09 | 863,150015 | 24.498,8 |
| `ANBIMA_IRFM1` · `IRFM1MAIS` | 6.488 | 2000-12-01 → 2026-10-09 | 1.000,000000 | 21.220,1 · 26.818,3 |
| `ANBIMA_IMAGERAL` · `IMAS` | 6.237 · 6.245 | 2001-12 → 2026-10-09 | 532,621995 · 550,485024 | 10.784,9 · 9.029,7 |
| `ANBIMA_IMAGERALEXC` | 5.407 | 2005-03-31 → 2026-10-09 | 1.000,000000 | 10.635,3 |

As 9 têm **63 observações no 1T2006**, pontas inclusive. Reconciliação independente: IRF-M em
2006-01-02 = **2.554,550434** e IMA-S = **1.147,988972**, idênticos às séries SGS 12461/12462 da
pesquisa — duas fontes, o mesmo número. `IMAC` (descontinuado 2021) e `IHFA` (fora do e-mail) não
entram. `vintage` = data do `collected_at` do manifesto (D-b); `--offline` reproduz tudo.

## Job diário (F-009) — bordas reais medidas

`ms*.txt` tinha dado desde **2026-09-11** (09 e 10/09 → HTTP **404**); Curva Zero desde **2026-09-14**
(11/09 e antes → HTTP **200 com 0 bytes**). ~20-21 d.u., e a borda **anda todo dia útil**. Na Curva
Zero use **`saida=csv`**: `saida=xls` devolve HTML `<table>`. Republicação da mesma data com conteúdo
diferente vira **vintage novo** (`__v2`), nunca sobrescrita.

## Armadilhas

- **O `.xls` do S3 é XLSX** (magic `PK\x03\x04`) → `exigir_formato` + `read_excel(BytesIO,
  engine="openpyxl")`. O mesmo conteúdo salvo como `.xls` faz o openpyxl recusar **pela extensão**:
  é por isso que o bruto é arquivado como `.xlsx`.
- **`series_id` vem do SLUG do catálogo, nunca do rótulo da planilha.** O rótulo é **guarda**
  (`ROTULOS_ESPERADOS`): a fonte **move o hífen** (`IMA - Geral ex-C` → `IMA-GERALEX-C` vs
  `IMA-GERAL-EX-C`), então normalizar espaço não basta — precisa de mapa explícito (CB-015).
- **Erro é HTTP 403 com XML `AccessDenied`**, tanto para SLUG inexistente quanto para listagem do
  bucket — daí os SLUGs hard-coded, conferidos contra o catálogo no `import`.
- **`data_ref` do bruto = última data do histórico**, não "hoje": rodar duas vezes no mesmo dia é
  byte-idêntico, e uma republicação com números diferentes bate em `ConteudoDivergente` (R8).
- **`print` de seta Unicode quebra no Windows** (cp1252): os `resumo()` são **só ASCII**, com teste.
- **Duration (d.u.), PMR e as variações da planilha não são extraídas:** `processed_series` é uma
  métrica por série. Se F-016 pedir Duration do IMA, é **série nova no catálogo**, não coluna extra.

**Features:** **F-002** e **F-009** (implementados) · **F-016** (curva, C) · **F-017** · **F-030**.
