# `tests/fixtures/anbima-feriados/` — calendário de feriados nacionais da ANBIMA (F-008)

Procedência de cada arquivo. Convenção em `tests/fixtures/README.md`: `<serie>__<data de coleta>`,
e a pasta espelha `data/raw/anbima-feriados/`. Tudo aqui é **dado real da fonte**, baixado em
**2026-10-10, ~21h BRT**, sem autenticação. Nenhum arquivo foi editado para fazer teste passar.

## Por que HTML, e não a planilha da SPEC

A SPEC RF-018 cita `https://www.anbima.com.br/feriados/arqs/feriados_nacionais.xls`. Esse arquivo
responde HTTP 200 com 111.104 bytes e `Content-Type: application/vnd.ms-excel`, mas os magic bytes
são `D0 CF 11 E0 A1 B1 1A E1` — **XLS/BIFF legado (OLE2) de verdade**, não o XLSX disfarçado do S3
da ANBIMA (F-002). Nenhum leitor instalado no projeto abre BIFF e `xlrd` está dispensado
(`DECISIONS_LOG §2`).

A **mesma lista**, ano a ano, é publicada em HTML pela própria ANBIMA em
`https://www.anbima.com.br/feriados/fer_nacionais/<ano>.asp` — são os links da página índice
`feriados.asp`, que também oferece a planilha. É daí que vêm as fixtures: mesma fonte, mesmo dado,
formato legível com as dependências que o projeto já tem (`latin-1` + `<table>`).

## Arquivos

| Arquivo | URL / payload exato | Bytes | O que prova |
|---|---|---|---|
| `2006__2026-10-10.html` | `GET https://www.anbima.com.br/feriados/fer_nacionais/2006.asp` | 6.518 | o ano de **CA-051**: 12 feriados, 249 dias úteis; 30/09 sábado e 31/12 domingo (CA-052); Carnaval em 27-28/02 |
| `2024__2026-10-10.html` | `GET .../fer_nacionais/2024.asp` | 6.845 | primeiro ano com **13** feriados (20/11, Lei 14.759/23) e a armadilha composta de 1T2024: 31/03 domingo, 30/03 sábado, **29/03 Paixão de Cristo** → último DU = 28/03 |
| `2025__2026-10-10.html` | `GET .../fer_nacionais/2025.asp` | 6.832 | 4T2025 fecha em **31/12** (quarta, fora da lista da ANBIMA); 252 dias úteis |
| `2026__2026-10-10.html` | `GET .../fer_nacionais/2026.asp` | 6.846 | **12/10/2026 é feriado** numa segunda-feira; 249 dias úteis; Carnaval em 16-17/02 |
| `2000__erro_404.html` | `GET .../fer_nacionais/2000.asp` → **HTTP 404** | 1.245 | **fixture de erro obrigatória** (CA-124): a fonte não cobre 2000 e responde HTML de erro, não tabela vazia. O corpo *é* HTML válido, então a guarda que vale é a ausência de `<table class="interna">` |
| `feriados_nacionais__erro_biff_cabecalho.bin` | **512 primeiros bytes** de `GET .../arqs/feriados_nacionais.xls` (arquivo completo: 111.104 bytes, `sha256 e3070152bfbd…`) | 512 | segunda fixture de erro: prova que a planilha da SPEC é BIFF e que o parser a recusa por magic bytes antes de qualquer `read_excel`. Recortado porque `*.xls` é ignorado pelo `.gitignore` e a regra de 200 KB vale por arquivo |

## Notas

- **`.html` e `.bin`** em vez de `.xls`: `.xls` é ignorado globalmente pelo `.gitignore` (linha
  `*.xls`), como `tests/fixtures/README.md` avisa.
- As páginas de ano trazem **três colunas**: `Data` (`1/1/06`, dia/mês sem zero e ano com 2
  dígitos), `Dia da Semana` (`domingo`, `terça-feira`) e `Feriado`. O parser confere o dia da
  semana contra `date.weekday()` — é o que tornaria visível uma troca de dia por mês.
- Encoding da página: **`iso-8859-1`** (declarado no prólogo XML e confirmado nos acentos de
  "Confraternização"), que é o `ANBIMA_WEB` de `ENCODING_POR_FONTE`. Ler como UTF-8 levanta.
- O arquivo bruto completo de cada ano vive em `data/raw/anbima-feriados/<ano>__<data do Natal>.html`
  com manifesto `.meta.json` (hash, URL, hora, cabeçalhos). Para regravar as fixtures, copie de lá.
- **Regravação:** `curl -A "Mozilla/5.0" https://www.anbima.com.br/feriados/fer_nacionais/2006.asp`.
  Se o conteúdo mudar, o teste `@pytest.mark.network` de
  `tests/unit/test_extract_calendario_anbima.py` acusa antes de qualquer outro.
