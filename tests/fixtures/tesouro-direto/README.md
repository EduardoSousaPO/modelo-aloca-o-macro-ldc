# `tests/fixtures/tesouro-direto/` — Tesouro Direto / CKAN (F-005)

Convenção de nome, limite de 200 KB e a regra de "dado real, nunca inventado":
`tests/fixtures/README.md`. A fonte e as pegadinhas estão em
`docs/research/fontes-de-dados.md §A4.1`; o módulo que lê estas fixtures é
`apps/pipeline/extract/tesouro_direto.py`.

Recurso: `GET https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv`
— arquivo único, **14.584.922 B**, 177.260 linhas + cabeçalho,
`sha256 75d297b48b6ab5b76a35f665e995a764d00d81ff09c78447f71469c26386bc28` em 2026-10-10,
`ETag "1791627731.36-14584922"`, `Last-Modified Sat, 10 Oct 2026 10:22:11 GMT`.

| Arquivo | Procedência | O que prova | Risco / CA |
|---|---|---|---|
| `precotaxatesourodireto__2026-10-10.csv` | **recorte real** do arquivo completo arquivado em `data/raw/tesouro-direto/precotaxatesourodireto__2026-10-10.csv` (sha256 acima): cabeçalho + **todas** as linhas das 4 datas-base `31/12/2004`, `02/01/2006`, `02/01/2026` e `09/10/2026` = 171 linhas, 13.864 B. Nenhum valor alterado; só a ordem é por data-base (do mais antigo ao mais recente) | os **8 tipos de título**; decimal **vírgula** (`6,65`, `20046,46`); datas **`dd/mm/aaaa`**; taxa **negativa** (`-0,02`) e **zero** (`0,00`) como valores reais; line ending **LF**; `Data Base` mais antiga ≤ 2005-01-03 | R13, R12 · **CA-020**, CA-021 |
| `precotaxatesourodireto__erro_html.html` | resposta **real** de `GET .../resource/00000000-0000-0000-0000-000000000000/download/precotaxatesourodireto.csv` (UUID de recurso inexistente) em 2026-10-10 com UA de browser: **HTTP 404**, `text/html; charset=utf-8`, 17.124 B | o CKAN serve erro como **HTML**; `read_csv` engoliria isso como uma coluna só. O parser recusa por **magic bytes** antes de qualquer leitura, inclusive se vier com HTTP 200 | R1, R11 · CA-003 · Anti-SPEC §10.1.5 |
| `precotaxatesourodireto__sintetico_acento_latin1.csv` | **SINTÉTICA** (o nome diz, por `CLAUDE.md §4`): 2 linhas reais de `09/10/2026` com o `Tipo Titulo` da primeira trocado por `Tesouro Educação+`, gravado em **latin-1** (`\xe7\xe3`) | o arquivo real é **100% ASCII hoje** (zero bytes > 127 nas 177.260 linhas) — sem esta fixture não existe prova de que o `encoding='latin-1'` declarado importa. Em latin-1 o acento volta certo; os mesmos bytes em utf-8 levantam `UnicodeDecodeError` em vez de virar mojibake | R10 · **CA-022** · Anti-SPEC §10.4.26 |

## Como regravar

O recorte e o HTML de erro foram gravados por script de sessão (a flag `--record` do
`conftest.py` segue pendente — `TODO.md §6`). Para refazer:

```python
# recorte real, a partir do bruto já arquivado
from apps.pipeline.extract import tesouro_direto as td
linhas = td.caminho_bruto_mais_recente().read_bytes().split(b"\n")
datas = {b"31/12/2004", b"02/01/2006", b"02/01/2026", b"09/10/2026"}
corpo = [l for l in linhas[1:] if l.strip() and l.split(b";")[2] in datas]
alvo.write_bytes(b"\n".join([linhas[0], *corpo]) + b"\n")
```

```python
# pagina de erro real do CKAN
ruim = td.CONFIG.base_url.replace(
    "796d2059-14e9-44e3-80c9-2d9e30b405c1", "00000000-0000-0000-0000-000000000000"
)
```

Se a fonte mudar o layout, **grave de novo e registre em `docs/plans/DECISIONS_LOG.md`** — nunca
edite a fixture para o teste passar.
