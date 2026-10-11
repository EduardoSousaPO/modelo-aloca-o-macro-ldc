# `tests/fixtures/msci/` — procedência

Respostas **reais** do endpoint público `getLevelDataForGraph` da app web da MSCI, gravadas em
**2026-10-10** por script de sessão (a flag `--record` ainda não existe — ver
`tests/fixtures/README.md`). Nenhuma foi editada: onde um teste precisa de um campo diferente, ele
altera o JSON **em memória** e diz por quê. Usadas por `tests/unit/test_extract_msci.py`
(F-007, SPEC RF-016, CA-046/CA-047).

Base: `https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph`
Parâmetros comuns: `currency_symbol=USD`, `index_variant=NETR`, `baseValue=false`.
Cabeçalho obrigatório: `User-Agent` de browser (`USER_AGENT_BROWSER` de
`apps/pipeline/common/http.py`).

| Arquivo | Parâmetros específicos | HTTP | Bytes | O que prova |
|---|---|---|---|---|
| `892400_NETR__2026-10-10.json` | `index_codes=892400`, `data_frequency=DAILY`, `start_date=20060101`, `end_date=20061231` | 200 | 14.095 | **CA-046**: 260 níveis de 2006 e o valor-canário `calc_date=20060131`, `level_eod=121.38580887703861` → 121,3858. Também: `calc_date` em `AAAAMMDD` inteiro, `level_eod` com ponto decimal, 65 pontos no 1T2006 |
| `892400_NETR__end-of-month.json` | `index_codes=892400`, `data_frequency=END_OF_MONTH`, `start_date=19970101`, `end_date=20261010` | 200 | 16.663 | **superfície independente** para reconciliar o canário: 310 pontos mensais, com 20060131 = 121,38580887703861 e 20060331 = 123,7572663279524 — os mesmos números do diário, por outra requisição |
| `892400_NETR__erro_start-date.json` | `start_date=19960101` | **200** | 203 | R1 / Anti-SPEC §10.1.5: erro servido com **HTTP 200** e nas chaves `error_code`/`error_message` (não `error`), logo invisível para `validar_corpo_json_array` da infra. Mensagem: `Calculation date cannot be earlier than 19970101` |
| `705000_NETR__vazio.json` | `index_codes=705000` (o MSCI Brazil `a_confirmar` do catálogo) | **200** | 114 | R2: código inexistente devolve `{"indexes":{"INDEX_LEVELS":[]}}` com HTTP 200 e **nenhum** campo de erro — só a guarda de contagem mínima pega |

## Como regravar

```python
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
r = requests.get(
    "https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph",
    params={"currency_symbol": "USD", "index_variant": "NETR", "data_frequency": "DAILY",
            "baseValue": "false", "start_date": "20060101", "end_date": "20061231",
            "index_codes": "892400"},
    headers=UA, timeout=120)
open("tests/fixtures/msci/892400_NETR__2026-10-10.json", "wb").write(r.content)
```

A resposta desta fonte **é** byte-estável entre chamadas (conferido na rodada ao vivo: 2 GETs
idênticos, mesmo `sha256`). O endpoint, porém, **não é documentado** (R18): se o canário
121,3858 deixar de bater, isso é mudança da fonte e vai para `docs/plans/DECISIONS_LOG.md`
antes de qualquer ajuste de teste.
