# `tests/fixtures/anbima-ima/` — índices ANBIMA IMA do bucket S3 (F-002)

Convenção, limite de 200 KB e regra de "dado real, nunca inventado": `tests/fixtures/README.md`.
Fonte de todos os arquivos: `https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/
arquivos/indices-historico/{SLUG}-HISTORICO.xls` (`docs/research/fontes-de-dados.md §B6`).

| Arquivo | Procedência | O que prova | CA |
|---|---|---|---|
| `imab__2026-10-10.xlsx` | recorte de `data/raw/anbima-ima/IMAB.xls` (= `IMAB-HISTORICO.xls`, 393.685 B, 5.795 linhas, coletado 2026-10-09/10): **40 primeiras + 40 últimas linhas reais**, re-serializadas com `openpyxl`. Nenhum valor alterado | magic bytes `PK\x03\x04` num arquivo servido como `.xls`; o valor-canário `IMA-B · 2003-09-16 · 723,070317` na 1ª linha; a última data 2026-10-09; **os dois rótulos** `IMA-B` (linhas antigas) e `IMA - B` (recentes) no mesmo arquivo | CA-030, CA-031, CA-032 |
| `irfm__2026-10-10.xlsx` | idem, de `IRFM.xls` (426.663 B, 6.700 linhas): 10 primeiras + 10 últimas | o IRF-M começa em **2000-02-01** (cobre 1T2006 com folga); rótulos `IRF-M` × `IRF - M` | CA-032, CA-033 |
| `imageralexc__2026-10-10.xlsx` | idem, de `IMAGERALEXC.xls` (359.730 B, 5.407 linhas): 10 primeiras + 10 últimas | o caso em que a fonte **move o hífen** (`IMA-GERAL-EX-C` × `IMA - Geral ex-C`): remover espaço não colapsa os dois, e é por isso que o `series_id` sai do SLUG e o mapa `ROTULOS_ESPERADOS` é explícito | CA-032 |
| `imab__erro_accessdenied.xml` | corpo **real e byte-idêntico** da resposta do S3, capturada em 2026-10-10 (HTTP **403**, `content-type: application/xml`, 243 B) a `GET .../indices-historico/IMAB5PLUS-HISTORICO.xls` — SLUG inexistente. O bucket responde o mesmo XML à tentativa de listagem (`GET /?list-type=2&prefix=arquivos/indices-historico/`) | o modo de falha real da fonte: `<Error><Code>AccessDenied</Code>`. O parser **recusa pelos magic bytes** (`<` → XML/HTML, não XLSX) antes de abrir a planilha, e nada é gravado em `data/processed/` | CA-030, CA-124 |

**Nenhum arquivo desta pasta é sintético.** Os três `.xlsx` são recorte de janela (o que o README
das fixtures recomenda para não guardar 20 anos de série); o `.xml` é a resposta íntegra.

Dois detalhes de extensão, os dois intencionais:

- a fonte serve `.xls` e o conteúdo é **XLSX**; `*.xls` é ignorado pelo `.gitignore` global e o
  `openpyxl` recusa a extensão `.xls`, então a fixture leva `.xlsx`, que é o formato real. Quem
  simula a mentira da fonte é o teste, renomeando para `.xls` em `tmp_path`;
- as fixtures são **recortes**, então `parse_historico` roda nelas com `minimo=None`. O piso real
  de contagem (`LINHAS_MINIMAS`, 5.795 no IMA-B) é exercitado em
  `test_truncamento_silencioso_e_recusado_pelo_piso_do_contrato` (a fixture de 80 linhas contra o
  piso de 5.795 → `RespostaTruncada`) e no teste `@pytest.mark.network`.

Para regravar: `uv run python -m apps.pipeline.extract.anbima_s3 --indices IMAB IRFM IMAGERALEXC`
reabastece `data/raw/anbima-ima/`; o recorte é `pd.concat([df.head(n), df.tail(n)])` +
`to_excel(..., engine="openpyxl")`. Se os números mudarem, registre em `DECISIONS_LOG.md` — nunca
edite a fixture para o teste passar.
