# `tests/fixtures/common/` — fixtures da infra de extração (F-001)

Convenção, limite de 200 KB e regra de "dado real, nunca inventado": `tests/fixtures/README.md`.
Esta pasta não corresponde a uma fonte do enum `Fonte` — ela guarda as respostas que provam o
comportamento da **infra compartilhada** (`apps/pipeline/common/`), e por isso vive em `common/`.
Cada extrator de Onda 1 continua gravando as suas em `tests/fixtures/<fonte>/`.

| Arquivo | Procedência | O que prova | Risco / CA |
|---|---|---|---|
| `anbima_cz__2026-10-09.html` | cópia byte-idêntica da amostra manual `data/raw/anbima-ettj/cz.xls` (apagada em 2026-10-10 por estar fora da convenção; **esta fixture é o único exemplar preservado**), baixada em 2026-10-10 via `POST https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp` com `saida=xls` (`docs/research/fontes-de-dados.md §A5.1` e tabela "Amostras baixadas em 2026-10-10") | o `.xls` da Curva Zero é **HTML `<table>`**: magic byte `<`; vértices com **separador de milhar** (`6.930`) e taxas com **decimal vírgula** (`6,5140`); parâmetros Svensson em notação científica pt-BR (`-4,58301615075328E-02`) | R10, R11, R13 · CA-035 |
| `anbima_ms__2026-10-08.txt` | cópia byte-idêntica de `data/raw/anbima-ms/ms_261008.txt` = `https://www.anbima.com.br/informacoes/merc-sec/arqs/ms261008.txt` (`§A4.2`) | **latin-1** real (`Associação` com `\xe7\xe3`, que é `UnicodeDecodeError` em UTF-8); separador `@`; datas `AAAAMMDD`; decimal vírgula sem milhar | R10, R12 · CA-022 |
| `anbima_imab__2026-10-09__janela-truncada.xlsx` | gerado de `data/raw/anbima-ima/IMAB.xls` (`.../indices-historico/IMAB-HISTORICO.xls`, 393.685 B, 5.795 linhas) mantendo **cabeçalho + as 40 primeiras linhas reais** e re-serializando com `openpyxl` para caber no limite de 200 KB — é a "truncagem de janela" que o README das fixtures recomenda. Valores **não** alterados: a 1ª linha é o valor-canário `IMA-B · 2003-09-16 · 723,070317` | o arquivo servido como `.xls` é **XLSX** (`PK\x03\x04`): o leitor se decide por magic bytes, não por extensão | R11 · CA-030 (pré) |
| `sgs_433__erro.json` | corpo de erro do SGS transcrito **verbatim** de `docs/research/fontes-de-dados.md §A1, "Pegadinha nº 1"` (resposta a `bcdata.sgs.11` com janela de 11 anos). A pesquisa elidiu `message` e `syntax` com `...`; preferi **omitir** essas duas chaves a preencher com texto que não foi medido | **HTTP 200 com corpo de erro**: o validador recusa e nada é gravado | R1 · CA-003 · Anti-SPEC §10.1.5 |
| `sgs_433__2026-10-10.json` | shape verbatim de `§A1` (`[{"data":"01/09/2026","valor":"0.82"}, ...]`) com os dois valores de IPCA mensal **confirmados na SPEC CA-002** (ago/2026 = `-0.32`, set/2026 = `0.82`) | caminho feliz: `valor` é string com **ponto decimal** — `para_float_ptbr` levanta aqui de propósito, é `para_float_ponto_decimal` que serve | R13 · CA-035 |

**Nenhum arquivo desta pasta é sintético.** Se algum dia precisar de um, o nome tem de dizer
(`__sintetico.json`), por `CLAUDE.md §4`.

`anbima_imab__*.xlsx` passa pelo `.gitignore` por causa da exceção `!tests/fixtures/**/*.xlsx`;
`*.xls` continua ignorado globalmente, que é por isso que a fixture leva a extensão real do
conteúdo (XLSX) e o teste é que renomeia para `.xls` em `tmp_path` para simular a mentira da fonte.
