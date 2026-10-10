# `tests/fixtures/` — respostas gravadas das fontes

Único lugar de onde um teste pode ler dado de fonte externa. **Nenhum teste do CI chama a rede**
(`AGENTS.md §6`): fonte viva só sob `@pytest.mark.network`, que roda local e é excluída com
`-m "not network"`.

## Convenção de nome

```
tests/fixtures/<fonte>/<serie>__<data>.json      # ou .csv / .txt / .xlsx
tests/fixtures/<fonte>/<serie>__erro.json        # fixture de erro (obrigatória por extrator)
```

- `<fonte>` em minúsculas, igual ao enum `Fonte` do catálogo: `sgs`, `sidra`, `olinda`, `anbima_s3`,
  `anbima_web`, `tesouro`, `b3`, `teva`, `yahoo`, `msci`, `fred`, `ipeadata`.
- `<serie>` é o `identificador` na fonte, não o nome bonito: `433`, `t1737_v2266`, `IMAB`, `IFIX`,
  `^GSPC`, `892400_NETR`.
- `<data>` é a data de **coleta** em ISO (`2026-10-10`) — a mesma que vai para `collected_at`.

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

A gravação é feita pelo próprio teste de rede, com a flag `--record`:

```bash
pytest tests/contract/test_<fonte>.py -m network --record    # grava/atualiza a fixture
pytest tests/unit tests/contract -m "not network"            # usa a fixture gravada (o que o CI roda)
```

O extrator que criar a primeira fixture de uma fonte implementa também a opção `--record` em
`conftest.py` (`pytest_addoption`) — ainda **não existe**: é parte de F-001 (infra de extração).

## Versionamento

`.gitignore` já abre exceção para `tests/fixtures/**/*.csv|json|xlsx`. **`*.xls` continua ignorado
globalmente** (linha `*.xls`), e os arquivos da ANBIMA S3 têm essa extensão mesmo sendo XLSX
(magic `PK\x03\x04`) — grave-os como `.xlsx`, que é o formato real, ou peça a exceção no
`.gitignore` antes de commitar.
