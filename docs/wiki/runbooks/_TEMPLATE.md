# Runbook — [TÍTULO CURTO E ACIONÁVEL]

> **Receita operacional repetível.** Crie quando: (a) operação repetida ≥ 2 vezes; (b) bug de dado recorrente identificado; (c) procedimento crítico de publicação ou de arquivamento.
>
> **Onde vive:** `docs/wiki/runbooks/<slug>.md`.
> **Naming:** `reconstruir-dataset.md`, `fonte-fora-do-ar.md`, `arquivamento-diario-anbima.md`, `fechar-pacote-comite.md`.

**Última execução verificada:** YYYY-MM-DD
**Tempo médio:** [ex: 5 min | 30 min]
**Risco:** [baixo | médio | alto — exige humano]

---

## 1. Quando usar

> Em 1-3 frases. Quando dispara este runbook?

`[Ex: quando a API da B3 passa a devolver HTTP 200 com corpo de erro e o extrator grava lixo.]`

## 2. Pré-requisitos

- [ ] Ambiente pronto (`uv sync --extra dev`) e CI N1 verde localmente
- [ ] `data/raw/` presente (ou ciência de que a reconstrução vai rebaixar a fonte)
- [ ] Branch `main` atualizada localmente

## 3. Passos

> Numerados, idempotentes quando possível, com comando exato.

```bash
# 1. Diagnóstico — a fonte responde o que se espera?
python -m pipeline.extract.<fonte> --diagnostico

# 2. Aplicar o fix / reexecutar a etapa
python -m pipeline.extract.<fonte> --data hoje

# 3. Verificar o que ficou gravado
ls -la data/raw/<fonte>/ | tail -5
```

## 4. Validação (smoke)

> Como saber que funcionou. Comando + saída esperada.

```bash
pytest tests/unit tests/contract -q
python -c "import pandas as pd; d=pd.read_parquet('data/processed/<serie>.parquet'); print(len(d), d['data'].min(), d['data'].max(), d.isna().mean().round(3).to_dict())"
# esperado: nº de linhas >= o mínimo conhecido, min/max coerentes, 0% de nulos em coluna crítica
```

## 5. Se falhar

> Caminhos de escape. Cada um leva a outro runbook ou pausa para humano.

| Sintoma | Ação |
|---|---|
| A fonte devolve HTML/corpo de erro com HTTP 200 | `runbooks/fonte-fora-do-ar.md` |
| O número mudou sem mudança de código | **pare**: diff numérico + `runbooks/reconstruir-dataset.md` |
| Validação falha e o número já foi enviado | Rollback de publicação em `docs/plans/infra-ops.md §1.6` |

## 6. Rollback (obrigatório se classe D)

```bash
# Como desfazer se este runbook quebrar mais que conserta
git revert HEAD --no-edit
# reconstrua a partir de data/raw/ (imutável), nunca do canônico suspeito
python -m pipeline.build_canonical --out data/canonical
```

> Se o número já saiu para o Alexandre/Comitê, o rollback é de **comunicação + versão**:
> siga `docs/plans/infra-ops.md §1.6` (avisar, revogar a versão no `wiki/log.md`, reconstruir do
> `raw/`, diff numérico v1.0 → v1.1, reenviar com nova tag e hash).

## 7. Histórico de execução

| Data | Quem | Resultado | Notas |
|---|---|---|---|
| YYYY-MM-DD | dev solo | OK em 4 min | sem incidente |
| YYYY-MM-DD | dev solo | falhou no passo 3 | precisei rotar key |

---

## Links

- Issue/incident relacionado: [link]
- ADR/decisão: [`DECISIONS_LOG L42`](../../plans/DECISIONS_LOG.md) ou [ADR-NNN](../../decisions/adr/ADR-NNN-...)
- Runbooks correlacionados: [...]

---

*Atualize após cada execução. Se este runbook não foi usado em 6 meses, marque como "verificar" — pode estar desatualizado.*
