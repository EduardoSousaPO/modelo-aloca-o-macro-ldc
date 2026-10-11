# `tests/fixtures/sidra/` — procedência

Respostas **reais** do `apisidra.ibge.gov.br`, coletadas em **2026-10-10 ~21:08 BRT** pelo
subagente executor de **F-004**. Convenção de nome: `tests/fixtures/README.md`. Fonte da verdade do
endpoint: `docs/research/fontes-de-dados.md §A3`.

**Nenhuma fixture aqui foi cortada à mão.** O recorte é feito **pela própria fonte**, pelo parâmetro
de período (`p/200601-202609`, `p/200601-202602`): o JSON é exatamente o que a API devolve para
aquela consulta, cabeçalho inclusive. Isso importa porque o parser valida continuidade de
mês/trimestre — uma fixture montada juntando "primeiras + últimas linhas" teria uma lacuna
artificial e falharia por um motivo que não existe na fonte.

| Arquivo | URL exata | HTTP | bytes | linhas de dado | O que prova |
|---|---|---|---|---|---|
| `t1737_v63__2026-10-10.json` | `https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/63/p/200601-202609` | 200 | 60.988 | 249 | IPCA variação mensal; **canário 202609 = 0,82** (CA-002/CA-004); acento em `"IPCA - Variação mensal"` (R10); continuidade de 249 meses |
| `t1737_v2266__2026-10-10.json` | `https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/200601-202609` | 200 | 75.914 | 249 | IPCA **número-índice** (CA-004): `unit=index`, 1ª obs 2006-01-31 = 2.550,36; monotonia medida 0,9435; base da razão trimestral de CA-005 |
| `t1621_v584_c90707__2026-10-10.json` | `https://apisidra.ibge.gov.br/values/t/1621/n1/all/v/584/p/200601-202602/c11255/90707` | 200 | 33.074 | 82 | PIB volume dessaz.; **canários 2006T1/T2/T3 = 131,74 / 132,14 / 134,36** (CA-008); `D4C=90707` e `D2C=584` (guarda de tabela trocada) |
| `t5932_v6564_c90707__2026-10-10.json` | `https://apisidra.ibge.gov.br/values/t/5932/n1/all/v/6564/p/199601-202602/c11255/90707` | 200 | 42.187 | 122 | PIB T/T−1 dessaz.; **`V = "..."` real em 1996T1** → `None`, nunca `0` (Anti-SPEC §10.1.4); canário 2006T1 = 1,6 % |
| `t1737_v63__erro-so-cabecalho.json` | `https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/63/p/197001` | **200** | 346 | **0** | **O modo de falha silenciosa desta fonte (R1/R2):** período fora do intervalo da tabela devolve HTTP 200, `application/json` válido, array com **só o cabeçalho**. Sem a guarda, série vazia entraria como sucesso |
| `t99999_v584__erro-400-tabela-invalida.txt` | `https://apisidra.ibge.gov.br/values/t/99999/n1/all/v/584/p/all` | **400** | 30 | — | Tabela inexistente responde `text/plain` `Tabela 99999: Tabela inválida` com status 400 → `FonteIndisponivel` antes de qualquer parse |
| `apisidra__erro-html-404.html` | `https://apisidra.ibge.gov.br/naoexiste` | **404** | 1.894 | — | O host serve **HTML** (`<!DOCTYPE html>`, ASP.NET "The resource cannot be found.") em caminho inválido. Usada nos dois sentidos: status 404 → `FonteIndisponivel`; o **mesmo corpo com status 200 forçado** → `RespostaDeErroComStatus200` (R1, Anti-SPEC §10.1.5) |

Todas ≤ 200 KB (`tests/fixtures/README.md`), e há um teste que afirma isso.

## Como regravar

Sem rede nenhum teste daqui roda; para regravar, repita a consulta da coluna "URL exata" com um
User-Agent de browser e grave o corpo cru com o mesmo nome. Se a fonte mudou, **não edite a
fixture**: grave de novo, atualize os números das tabelas deste README e registre em
`docs/plans/DECISIONS_LOG.md`.

```bash
curl -s -A "Mozilla/5.0" "<URL exata>" -o tests/fixtures/sidra/<nome>
```

Ao regravar os recortes de 2006+, os números-canário **não devem mudar** — o IPCA é definitivo e o
PIB é revisado (`t/1621` muda retroativamente). Canário de PIB que muda é revisão do IBGE, não bug:
o `vintage` do extrator existe exatamente para isso.

## Adulteração em memória

Os caminhos de erro que **não** têm fixture própria (mês faltando, trimestre faltando, período
repetido, fora de ordem, categoria `c11255` trocada, nível territorial de UF) são exercitados
alterando a fixture real **em memória**, via `_reescrever` em
`tests/unit/test_extract_ibge_sidra.py`. O layout continua o real do apisidra e só o campo sob
teste muda — nada disso é gravado no repo, e nenhuma fixture sintética existe aqui.
