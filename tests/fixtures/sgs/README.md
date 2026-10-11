# `tests/fixtures/sgs/` — respostas gravadas do BCB SGS

Fixtures do extrator **F-003** (`apps/pipeline/extract/bcb_sgs.py`). Convenção, limites e regras:
[`tests/fixtures/README.md`](../README.md). Todas são **dado real**, gravadas em **2026-10-10**
por script de sessão (a flag `--record` não existe ainda), com `User-Agent` de browser.

Endpoint único, em todos os casos:

```
GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
      ?formato=json&dataInicial={dd/mm/aaaa}&dataFinal={dd/mm/aaaa}
```

## Caminho felizes

| Arquivo | Série | Janela pedida | Obs. | Bytes | O que prova |
|---|---|---|---|---|---|
| `433__2026-10-10.json` | 433 — IPCA var. mensal | 01/01/2004 → 10/10/2026 | 273 | 10.117 | CA-001 (>= 249 meses contíguos, `freq=M`, `unit=%`) e **CA-002**: set/2026 = `0.82` |
| `24364__2026-10-10.json` | 24364 — IBC-Br dessaz. | 01/01/2004 → 10/10/2026 | 271 | 11.195 | **CA-006**: jan/2006 = `79.44731`; último ponto jul/2026 (lag ~45 dias) |
| `11__2026-10-10__2005-2006.json` | 11 — Selic over %/dia | 01/01/2005 → 31/12/2006 | 500 | 20.501 | **CA-012**: 03/01/2005 = `0.064826`; base do teste de fatiamento (CA-011) |
| `12__2026-10-10__2006.json` | 12 — CDI %/dia | 01/01/2006 → 31/12/2006 | 249 | 10.210 | **CA-014/CA-016**: 249 d.u. de 2006 acumulam `15,0271 %` com `prod(1+v/100)` |
| `1__2026-10-10.json` | 1 — PTAX venda | 01/01/2026 → 10/10/2026 | 194 | 7.567 | **CA-043**: 09/10/2026 = `4.9892`; só dia útil |
| `432__2026-10-10__data-futura.json` | 432 — meta Selic | 01/10/2026 → 31/12/2026 | 35 | 1.331 | **CA-013**: última linha é **04/11/2026**, data futura (meta vigente até o próximo Copom) |

> `433__2026-10-10.json` e `24364__2026-10-10.json` são cópias byte-idênticas das fatias
> arquivadas em `data/raw/sgs/` na execução ao vivo de 2026-10-10 — mesmo `sha256` do manifesto.

## Caminhos de erro (obrigatórios por extrator — `tests/fixtures/README.md`)

| Arquivo | Requisição | Status | O que prova |
|---|---|---|---|
| `99999999__erro_html.txt` | série **inexistente** `99999999`, 2006 | **200** | **R1 / CA-003 no estado puro**: XHTML de erro servido com HTTP **200**. `validar_corpo_json_array` recusa pelo magic byte `<`; nada é gravado em `data/processed/` |
| `11__erro.json` | série 11, janela de **11 anos** (01/01/1980 → 31/12/1990) | **406** | o erro de janela de 10 anos. ⚠️ A pesquisa (`§A1`) mediu **HTTP 200** para este corpo; em 2026-10-10 a fonte responde **406**. O corpo é idêntico; só o status mudou |
| `433__erro_404.json` | série 433, janela antes do início (1900-1910) | **404** | `{"erro":{"statusCode":404,...}}` — janela fora da série não devolve array vazio |

**Por que três.** O risco catalogado (R1) é "erro com HTTP 200", e ele continua real — mas agora
pelo caminho da *série inexistente*, não pelo da *janela larga*. Guardar os três mantém o teste
honesto sobre o que a fonte faz hoje e sobre o que ela fazia quando a pesquisa foi escrita.

## Como regravar

```bash
# 1 arquivo, como o script de sessão fez (ajuste codigo/janela/nome):
curl -sS -H "User-Agent: Mozilla/5.0" \
  "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2004&dataFinal=10/10/2026" \
  -o tests/fixtures/sgs/433__2026-10-10.json
```

Se o conteúdo mudar (o BCB revisa IBC-Br e PIB), **regrave e registre em
`docs/plans/DECISIONS_LOG.md`** — nunca edite a fixture para o teste passar.

```bash
uv run pytest tests/unit/test_extract_bcb_sgs.py -m "not network" -q   # usa estas fixtures
uv run pytest tests/unit/test_extract_bcb_sgs.py -m network -q         # confere contra a fonte viva
```
