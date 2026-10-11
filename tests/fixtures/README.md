# `tests/fixtures/` — respostas gravadas das fontes

Único lugar de onde um teste pode ler dado de fonte externa. **Nenhum teste do CI chama a rede**
(`AGENTS.md §6`): fonte viva só sob `@pytest.mark.network`, que roda local e é excluída com
`-m "not network"`.

## Convenção de nome

```
tests/fixtures/<fonte>/<serie>__<data>.json      # ou .csv / .txt / .xlsx / .html
tests/fixtures/<fonte>/<serie>__erro*.json       # fixture de erro (obrigatória por extrator)
```

- `<fonte>` é o **slug da pasta correspondente em `data/raw/`**, não o enum `Fonte` do catálogo:
  hífen, minúsculas, **um diretório de fixture por pasta de `data/raw/`** — assim a fixture fica a um
  `ls` de distância do dado real que ela imita. Em uso hoje: `anbima-ms`, `anbima-ettj` e `common`
  (fixtures da infra de F-001, que não pertencem a uma fonte só). Na Onda 1: `anbima-ima`, `sgs`,
  `sidra`, `tesouro-direto`, `b3`, `yahoo`, `msci`, `focus`, `fred`, `teva`. Duas pastas **não**
  são fonte e seguem convenção própria, documentada no README delas: `canonical/` e `processed/`
  (recortes da nossa própria camada processada — ver abaixo).
- `<serie>` é o `identificador` na fonte, não o nome bonito: `433`, `t1737_v2266`, `imab`, `ifix`,
  `ms`, `cz`, `^GSPC`, `892400_NETR`.
- `<data>` é a data de **coleta** em ISO (`2026-10-10`) — a mesma que vai para `collected_at`.
- O separador é **`__`** (dois underscores). O sufixo de erro é **`__erro*`** — qualquer nome que comece
  por `__erro` conta como fixture de caminho de erro (`__erro.json`, `__erro_html.txt`); variantes de
  borda seguem o mesmo padrão descritivo (`__vazio.csv`, `__saida_xls_e_html.html`,
  `__janela-truncada.xlsx`).

**A fixture de erro não é opcional.** O modo de falha dominante das fontes deste projeto é erro com
HTTP 200 (R1 da pesquisa: o SGS devolve HTML de erro com status 200; a B3 devolve payload vazio).
Cada extrator precisa de uma fixture que prove que o parser **recusa** esse corpo em vez de gravar
lixo silenciosamente.

## Regras

| Regra | Por quê |
|---|---|
| **≤ 200 KB por arquivo** | fixture é amostra, não espelho da fonte. Trunque a janela (ex.: 2006 + 2026) em vez de guardar 20 anos |
| Dado **real** da fonte, nunca gerado à mão | fixture inventada valida o parser contra a imaginação do autor |
| Dado sintético só quando o nome diz (`__sintetico.json`) | `CLAUDE.md §4`: nunca misturar real e sintético sem marcar |
| Nunca editar a fixture para o teste passar | se a fonte mudou, grave de novo e registre em `DECISIONS_LOG.md` |
| Nada de credencial, cookie ou token no arquivo | fixture vai para o git |

## Como gravar

A flag `--record` **ainda não está implementada** — não entrou em F-001 porque `tests/conftest.py` é
arquivo compartilhado da onda; é decisão aberta, registrada em `TODO.md §6` e
`TODO.md §6` (parking lot).

Até ela existir, a fixture é gravada por **script de sessão**: um trecho avulso que faz a chamada real
uma vez, grava o corpo cru com o nome da convenção e **não** fica no repo. O que fica é a
**procedência** — cada diretório de fonte tem um `README.md` dizendo, por fixture, a URL/payload exato,
a data e a hora da coleta e o que ela prova (`tests/fixtures/common/README.md` é o modelo). Fixture sem
procedência registrada é fixture que ninguém consegue regravar quando a fonte mudar.

```bash
pytest tests/unit tests/contract -m "not network"            # usa a fixture gravada (o que o CI roda)
pytest tests/contract/test_<fonte>.py -m network             # confere a fixture contra a fonte viva (local)
```

## `processed/` — a exceção do Parquet

`tests/fixtures/processed/` não imita uma **fonte**: guarda recortes reais da própria
`data/processed/`, e é o único diretório daqui com `.parquet`. Existe porque as varreduras de
camada (`test_processed_layer_conventions.py`, `test_contract_sgs_sidra.py`) são a única trava
regressível de D-a/D-b/PK e, lendo só `data/` — que não está no git —, **pulavam no CI** (P1-4
do QA da Onda 1). Regras próprias: ≤ 30 KB por arquivo, recorte 2006-01..2006-06 + os últimos
3 meses, e procedência linha a linha em `tests/fixtures/processed/README.md`, com o script de
regeneração.

## Versionamento

`.gitignore` já abre exceção para `tests/fixtures/**/*.csv|json|xlsx|parquet`. **`*.xls` continua ignorado
globalmente** (linha `*.xls`), e os arquivos da ANBIMA S3 têm essa extensão mesmo sendo XLSX
(magic `PK\x03\x04`) — grave-os como `.xlsx`, que é o formato real, ou peça a exceção no
`.gitignore` antes de commitar.
