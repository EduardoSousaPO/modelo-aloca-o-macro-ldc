# Runbook — Reconstruir o dataset canônico do zero

**Última execução verificada:** 2026-10-11 — `python -m apps.pipeline run --offline`, **duas
rodadas seguidas**, 11 etapas, 29 artefatos determinísticos **byte-idênticos**,
`DATASET_SHA256 = 0d8b62397a30de857482d68bfe7fb711c9af990018284a8c0ea7f501c395b603`
(commit `83143db`, F-029). **Tempo medido do trecho offline: 39-45 s**, dos quais ~31 s são a
etapa `curva`. O tempo **a frio, com extração**, continua **não medido** (RNF-008 / CA-119).
**Tempo estimado:** 1 min offline · 20-40 min online · **Risco:** médio; **alto** se a saída for ao
Comitê → vira **classe D**

> O comando é **um só** e vive em `apps/pipeline/run.py` (F-029). Todo comando abaixo é real e foi
> executado; nenhum é placeholder. A fonte de verdade da ordem das etapas é
> `python -m apps.pipeline run --offline --listar-etapas`.

## 1. Quando usar

`data/canonical/` precisa ser regenerado: schema alterado, extrator corrigido, série ressincronizada, máquina nova — ou **antes de qualquer entrega ao Comitê** (classe D exige dataset congelado + hash).

## 2. Pré-requisitos

- [ ] `uv sync --extra dev` rodado; `ruff check .` e `pytest tests/unit` verdes
- [ ] **Offline:** `data/processed/` presente (é a fonte do modo offline). **Online:** rede liberada
      para SGS, SIDRA, ANBIMA S3, Tesouro, B3, Yahoo, MSCI. **FRED é esperado falhar nesta
      máquina** (R5) → o pipeline segue pelo plano B (S-09)
- [ ] `data/raw/` preservado — é **imutável** e é o que garante reconstrução sem rede

## 3. Passos — um comando

```bash
# A. Reconstrução sem rede (o caso normal): data/processed/ -> data/canonical/
python -m apps.pipeline run --offline

# B. Do zero, com extração (data/ vazio): os 9 extratores + as 11 etapas
python -m apps.pipeline run --online

# C. Reprocessar o bruto arquivado sem rede (data/raw/ -> data/processed/ -> canonico)
python -m apps.pipeline run --offline --reprocessar

# Controle fino (o que a mensagem de falha sugere):
python -m apps.pipeline run --offline --listar-etapas       # a ordem, sem rodar nada
python -m apps.pipeline run --offline --ate macro_quarterly # para no ponto pedido
python -m apps.pipeline run --offline --so regimes_v3       # retoma uma etapa
python -m apps.pipeline run --offline --sem-duckdb          # pula o derivado nao reproduzivel
python -m apps.pipeline run --offline --sem-opcionais       # pula metricas_regime e figuras
```

**Ordem das etapas** (a de `--listar-etapas`): extração (`extract_sgs`, `extract_sidra`,
`extract_focus`, `extract_calendario`, `extract_anbima`, `extract_tesouro`, `extract_b3`,
`extract_yahoo`, `extract_msci`) → `curva` (grava em `data/processed/curva/`) → `build_raw_series`
→ `alinhamento` → `macro_quarterly` → `asof` → `retornos` → `regimes_v1` → `regimes_v1_asof` →
`regimes_v3` → `metricas_regime` (F-022) → `figuras` (F-025). As duas últimas são **opcionais**:
se o módulo não existir, a etapa é **pulada** e isso aparece no resumo.

**Nunca** editar `data/` à mão nem reconstruir sem `data/raw/` arquivado: o job diário da ANBIMA (F-009) é a única cópia da janela rolante de ~20 d.u.

## 4. Validação (smoke)

O próprio `run` imprime o smoke no final: etapa por etapa com situação e tempo, e artefato por
artefato com **linhas, bytes, `sha256`, min/max de data e % de nulos por coluna** (CA-118). Depois:

```bash
python -m apps.pipeline verify      # recalcula o sha256 e compara com data/canonical/MANIFEST.json
pytest tests/contract -m "not network"               # valores-canario
pytest tests/e2e                                     # reprodutibilidade (N3) sobre fixture
```

Esperado no acervo de 2026-10-11: `macro_quarterly` **83 × 42** · `asset_returns_quarterly`
**1.963 linhas / 24 ativos** · `raw_series` **278.439 linhas / 62 séries** · `series_catalog`
**138** · nenhuma linha antes do início real da série · CDI 2006 = 15,0271% · IBOV 01/02/2006 =
38.484,84 · `verify` com **`rc = 0`** e 1 linha `INFO` do `ldc.duckdb`.

Rodar **duas vezes** do mesmo `data/processed/` tem de dar o **mesmo `DATASET_SHA256`**
(RF-048 / CI N3). Duas ressalvas medidas, as duas declaradas no `MANIFEST.json`:

- **`ldc.duckdb` não é byte-reproduzível** quando criado do zero (mesmo tamanho, `sha256`
  diferente). É derivado e descartável (ADR-006 §(a).2), então entra no manifesto com
  `sha256: null` e **fora** do agregado; `verify` o reporta como `INFO`. Para um diretório
  integralmente determinístico, `run --offline --sem-duckdb`.
- **`versao_build` hasheia o código**, não só o dado: se um `.py` de `apps/` mudar entre as duas
  rodadas, os relatórios e os artefatos que os citam mudam de hash **sem que uma célula se mova**.
  Antes de concluir "o pipeline não é idempotente", confira `git status`.

## 5. Se falhar

A falha **para** o pipeline na etapa, nomeia a etapa, diz o que **não** rodou e imprime o comando
de retomada (`--so <etapa>`). Leia a etapa antes de procurar a causa.

| Sintoma | Ação |
|---|---|
| `BLOQUEADO — FONTE INDISPONÍVEL: N série(s) exigida(s) ausente(s)` | faltou rodar a extração daquela fonte (ou o `--reprocessar`). **Nunca** "preencher": é CA-076 |
| Lixo gravado com HTTP 200 (SGS/Olinda) ou fonte inacessível | [`fonte-fora-do-ar.md`](./fonte-fora-do-ar.md) — é R1/R2, não queda |
| `pandera` reprova schema | **pare**: é classe C — Feature Contract + diff numérico antes de mexer |
| 83 linhas não fecham / linha antes do início da série | revisar F-014; nunca "preencher" (Anti-SPEC §10) |
| `verify` reprova (`rc != 0`) | **não publicar**. `sha256 divergente` = arquivo editado ou build diferente; `ausente em disco` = artefato apagado; `nao listado no manifesto` = arquivo novo que ninguém declarou. Rode `run --offline` de novo e confira o `diff` |
| Hash difere entre duas execuções | veja as duas ressalvas da §4 antes de tudo; se não for nenhuma, **não publicar** |
| Etapa opcional aparece como `PULADA` | F-022/F-025 ainda não expõem `construir(raiz=...)` — é informação, não erro |

## 6. Congelar o dataset (obrigatório antes da entrega) e rollback

```bash
python -m apps.pipeline freeze --tag comite-2026-10-14
# grava data/canonical/MANIFEST.json (sha256 por artefato + agregado + versao_build de cada
# relatorio + commit lido de .git/HEAD) e data/canonical/FROZEN.txt (tag, DATA DO DADO, rollback).
# NAO executa git: a tag continua ato humano (infra-ops.md 1.3)
git tag -a comite-2026-10-14 -m "Pacote de entrega ao Comite - DATASET_SHA256=<do FROZEN.txt>"
```

`FROZEN.txt` registra a **data do dado** (`date_max` de `raw_series`, `vintage` mais novo, primeiro
e último trimestre do `macro_quarterly`), **não** a hora do congelamento — é a pergunta que o
Alexandre faz. `--saida` permite congelar num diretório de entrega, desde que dentro de `data/`.

**Rollback (obrigatório em classe D — `infra-ops.md §1.6`, repetido no `FROZEN.txt`):**

1. **Não enviar.** Se já enviado: e-mail de correção citando a tag e o `DATASET_SHA256`.
2. Marcar a versão como **revogada** em `log.md` (`[REVOKED]`) e restaurar a versão anterior de
   `data/canonical/`.
3. Reconstruir do `raw/` arquivado: `python -m apps.pipeline run --offline`.
4. Rodar o **diff numérico** vs. a versão enviada e comunicar cada divergência (F-031).
5. `python -m apps.pipeline verify` tem de sair `0` antes de qualquer reenvio.
6. Versão corrigida sai com **tag nova** (nunca `git tag -f`).

**Histórico de execuções:** 2026-10-11 — primeira reconstrução real pelo comando único (F-029),
2 rodadas com `DATASET_SHA256` idêntico; os 20 artefatos que existiam antes saíram com `sha256`
inalterado (zero célula mudou).

**Links:** [`ADR-006`](../../decisions/adr/ADR-006-armazenamento-e-convencao-de-retornos.md) · [`DECISIONS_LOG`](../../plans/DECISIONS_LOG.md) · [`PLAN`](../../plans/PLAN.md) · [`modules/canonical.md`](../modules/canonical.md) · [`context/F-029.md`](../context/F-029.md) · [`infra-ops.md`](../../plans/infra-ops.md)
