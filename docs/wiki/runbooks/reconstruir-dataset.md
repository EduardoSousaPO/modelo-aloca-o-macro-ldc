# Runbook — Reconstruir o dataset canônico do zero

**Última execução verificada:** — (**nunca executado**: nenhum extrator existe em 2026-10-10)
**Tempo estimado:** 20-40 min · **Risco:** médio; **alto** se a saída for ao Comitê → vira **classe D**

> ⚠️ Esboço escrito a partir das pegadinhas de `docs/research/fontes-de-dados*.md` e do **ADR-006**. Todo comando abaixo é **placeholder** até `apps/pipeline/` existir (F-001, F-029).

## 1. Quando usar

`data/canonical/` precisa ser regenerado: schema alterado, extrator corrigido, série ressincronizada, máquina nova — ou **antes de qualquer entrega ao Comitê** (classe D exige dataset congelado + hash).

## 2. Pré-requisitos

- [ ] `uv sync --extra dev` rodado; `ruff check .` e `pytest tests/unit` verdes
- [ ] Rede liberada para SGS, SIDRA, ANBIMA S3, Tesouro, B3, Yahoo, MSCI, Teva. **FRED é esperado falhar
      nesta máquina** (R5) → o pipeline segue pelo plano B (S-09)
- [ ] `data/raw/` preservado — é **imutável** e é o que garante reconstrução sem rede

## 3. Passos

```bash
# 1. Extracao -> data/raw/<fonte>/   (idempotente, cache por ETag/Last-Modified)
python -m pipeline.extract --todas --desde 2006-01-01       # placeholder (F-001..F-012)
# 2. Transformacao -> data/processed/  (frequencia nativa, validada por pandera)
python -m pipeline.transform                                 # placeholder (F-013)
# 3. Canonico trimestral -> data/canonical/
python -m pipeline.build-canonical                           # placeholder (F-014..F-018)
# 4. Regimes + metricas + figuras
python -m pipeline.regimes && python -m pipeline.figuras      # placeholder (F-019..F-025)
```

**Nunca** editar `data/` à mão nem reconstruir sem `data/raw/` arquivado: o job diário da ANBIMA (F-009) é a única cópia da janela rolante de ~20 d.u.

## 4. Validação (smoke)

```bash
python -m pipeline.report                                    # placeholder (RF-046)
# esperado: macro_quarterly = 83 linhas · asset_returns_quarterly >= 18 ativos · n_obs nunca nulo
#   nenhuma linha antes do inicio real da serie · CDI 2006 = 15,0271% · IBOV 01/02/2006 = 38.484,84
pytest tests/contract                                        # valores-canario
```

Rodar **duas vezes** do mesmo `raw/` tem de dar o **mesmo hash** (RF-048 / CI N3).

## 5. Se falhar

| Sintoma | Ação |
|---|---|
| Lixo gravado com HTTP 200 (SGS/Olinda) ou fonte inacessível | [`fonte-fora-do-ar.md`](./fonte-fora-do-ar.md) — é R1/R2, não queda |
| `pandera` reprova schema | **pare**: é classe C — Feature Contract + diff numérico antes de mexer |
| 83 linhas não fecham / linha antes do início da série | revisar F-014; nunca "preencher" (Anti-SPEC §10) |
| Hash difere entre duas execuções | fonte mudou no meio ou há não-determinismo → **não publicar** |

## 6. Rollback (obrigatório em classe D)

1. **Não enviar.** Se já enviado: e-mail de correção citando versão e hash do dataset substituído.
2. Marcar a versão como **revogada** em `log.md`; restaurar a versão anterior de `data/canonical/`.
3. Reconstruir do `raw/` arquivado e rodar o **diff numérico** vs. a versão enviada, comunicando cada divergência (F-031). Histórico de execuções: registrar aqui na primeira reconstrução real.

**Links:** [`ADR-006`](../../decisions/adr/ADR-006-armazenamento-e-convencao-de-retornos.md) · [`DECISIONS_LOG`](../../plans/DECISIONS_LOG.md) · [`PLAN`](../../plans/PLAN.md) · [`modules/canonical.md`](../modules/canonical.md)
