# PLAN — Estratégia Macro LDC · ondas até o Comitê de 2026-10-14

> Plano de execução por **dia**, com paralelismo entre subagentes Opus, dependências e a lista de corte
> se atrasar.
>
> **Versão:** 1.0 — **Data:** 2026-10-10 (sábado) — **Referência:** `docs/specs/SPEC.md` v1.0,
> `TODO.md` (40 features), `docs/plans/risk-classification.md`.
> **Prazo duro:** Comitê **2026-10-14 (quarta)**. Heatmap para revisão do Edu em **2026-10-13 (terça)**.

---

## 1. Stack e topologia

- **Python 3.11+**, ambiente local (`uv` ou venv). Roda **só na máquina do Edu** — sem servidor, deploy,
  auth ou cloud.
- **Extração:** `requests`/`httpx` com UA de browser, retry e cache condicional → `data/raw/<fonte>/`.
- **Contratos:** `pydantic` (catálogo, config) + `pandera` (DataFrame) em `packages/shared/schemas/`.
- **Persistência:** **Parquet por camada**; **DuckDB derivado** para consulta (ADR-006).
- **Análise:** notebook em `apps/analysis/`, **sem lógica de negócio** (importa de `apps/pipeline/`).
- **Qualidade:** `ruff` + `pytest`; N1 = lint + unit · N2 = + integration/contract + build do canônico ·
  N3 = + e2e + reprodutibilidade (2 execuções → mesmo hash).

```
fontes públicas ─► apps/pipeline/extract ─► data/raw ─► data/processed ─► data/canonical ─► apps/analysis
   (12 fontes)        (classe B)            (imutável)    (freq. nativa)    (trimestral, C)     (figuras)
                                                   │              │                │                │
                                                   └── pandera ───┴── pandera ─────┘         Comitê (D)
```

---

## 2. Ondas

Uma onda só começa quando a anterior está **verde no CI** no nível alvo. Dentro da onda, as features
marcadas `‖` podem rodar **em paralelo** (subagentes Opus independentes, arquivos disjuntos).

### Onda 0 — HOJE, sábado 2026-10-10 (2-3 h) · fundação + o job que não pode esperar

**Objetivo:** ligar o arquivamento que perde dado a cada dia e ter a infra de extração pronta.

| Feature | Classe | Por que agora |
|---|---|---|
| **F-009** job diário ANBIMA (`Msec_txt.txt` + Curva Zero) | B | **janela rolante de ~20 d.u.**: cada dia sem o job é série proprietária perdida para sempre (L6/R3). Não depende de nenhuma decisão |
| **F-001** infra de extração (HTTP+UA, retry, shape, número pt-BR, encoding, magic bytes) | B | é pré-requisito de todos os extratores; concentra as mitigações de R1, R2, R4, R10-R13 |
| **F-032** `DECISIONS_LOG` inicial com as substituições já conhecidas | A | 20 min, destrava a comunicação ao Alexandre e fecha RF-052 |

**Critério de saída:** `pytest tests/unit` verde; `data/raw/anbima-ms/` e `data/raw/anbima-ettj/` com o
arquivo do dia; `DECISIONS_LOG.md` com **12** substituições registradas (S-01..S-12 — F-032 já concluída).

---

### Onda 1 — domingo 2026-10-11, manhã/tarde (até ~6 h) · **todos os extratores de esforço baixo, em paralelo**

**Objetivo:** ter **todas as séries do pacote mínimo em `data/processed/`**, conferidas contra a fonte.

| ‖ | Feature | Classe | Fonte | Esforço |
|---|---|---|---|---|
| ‖ | **F-002** ANBIMA S3 (8 índices IMA) | B | S3 público | baixo |
| ‖ | **F-003** BCB SGS (IPCA, IBC-Br, Selic, CDI, PTAX) | B | SGS REST | baixo |
| ‖ | **F-004** IBGE SIDRA (IPCA nº-índice, PIB trimestral) | B | apisidra | baixo |
| ‖ | **F-005** Tesouro Direto (1 CSV de 14,6 MB) | B | CKAN | baixo |
| ‖ | **F-006** API B3 (11 índices, incl. IFIX) | B | `indexStatisticsProxy` | médio |
| ‖ | **F-007** Yahoo `^GSPC` + MSCI ACWI NETR → BRL | B | Yahoo/MSCI | baixo |
| ‖ | **F-008** calendário de dias úteis ANBIMA | B | arquivo | baixo |

**Paralelismo:** 7 subagentes Opus, **um por fonte** — arquivos disjuntos
(`apps/pipeline/extract/<fonte>.py`, `tests/.../test_<fonte>.py`, `tests/fixtures/<fonte>/`), nenhum toca
`packages/shared/schemas/` além de **acrescentar** campo (se precisar alterar schema existente → pausa).
Cada subagente recebe: objetivo, seção da pesquisa, CAs da SPEC, valor-canário, arquivos permitidos e o
que devolver (matriz + evidência de dados).

**Onda 1b — domingo, fim do dia (paralelo, prioridade menor):**

| ‖ | Feature | Classe | Nota |
|---|---|---|---|
| ‖ | **F-010** Focus (Olinda) | B | resolve os gaps G-04 e G-05 |
| ‖ | **F-011** FRED + fallback Yahoo | B | **primeiro passo = teste de conectividade** (G-06) |
| ‖ | **F-012** Teva FII segmentado | B | `should`; cortável (decisão L2) |

**Critério de saída da Onda 1:** cada série do pacote mínimo em `data/processed/`, com fixture gravada,
valor-canário verde e **3 valores conferidos contra a fonte** registrados na matriz de validação.

---

### Onda 2 — domingo à noite e segunda 2026-10-12, manhã · **camada canônica (classe C)**

**Objetivo:** `macro_quarterly` com 83 trimestres e `asset_returns_quarterly` com ≥ 18 ativos, validados
por pandera e com diff numérico explicado.

| Ordem | Feature | Classe | Depende de |
|---|---|---|---|
| 1 | **F-013** `raw_series` + `series_catalog` materializado | C | Onda 1 |
| 2 | **F-014** alinhamento trimestral (último DU, ffill ≤ 5) | C | F-008, F-013 |
| 3 ‖ | **F-016** curva: vértices interpolados + inclinação | C | F-005 |
| 4 ‖ | **F-017** retornos: `ret_tri`, excesso CDI, real | C | F-014 + extratores de ativos |
| 5 | **F-015** `macro_quarterly` (83 linhas) | C | F-014, F-016, F-003/004/010 |
| 6 | **F-018** anti-look-ahead + `asof`/`revised` + % de troca | C | F-015 |

**Paralelismo:** F-016 e F-017 são disjuntas (curva × retornos) e podem rodar em dois subagentes; F-015
costura. **Classe C = pausa antes de começar**, Feature Contract detalhado, diff numérico vs. a versão
anterior, reconstrução completa e **revisão numérica independente** (quem calculou não confere).

**Critério de saída:** CI **N2** verde; `macro_quarterly` com exatamente 83 linhas; retornos com ≥ 18
ativos; painel desbalanceado correto (nenhuma linha antes do início de cada série); CDI 2006 =
15,0271% reproduzido; excesso sobre CDI por razão com o teste anti-subtração verde.

---

### Onda 3 — terça 2026-10-13, manhã · **regimes V1 + V3 (classe C)**

**Objetivo:** cada um dos 83 trimestres classificado e os vizinhos calculados.

| Ordem | Feature | Classe | Nota |
|---|---|---|---|
| 1 | **F-019** V1 (quadrantes) | C | **`especificacao_congelada=False` enquanto ADR-001 estiver em Proposta** |
| 2 ‖ | **F-020** V2 (ciclo Selic, corte secundário) | C | `should` |
| 3 ‖ | **F-021** V3 (Mahalanobis + shrinkage, k=8) | C | roda com 5 features se F-016 atrasar |
| 4 | **F-022** métricas por regime × ativo | C | insumo do heatmap |

**Gate importante:** o número só é **publicável** com **ADR-001 aceito** (RF-031/CA-090). Sem resposta de
D1/D3 até terça, a execução segue com o padrão provisório e o pacote vai ao Edu marcado
"especificação não congelada".

---

### Onda 4 — terça 2026-10-13, tarde · **visualização + revisão do Edu**

| Ordem | Feature | Classe |
|---|---|---|
| 1 ‖ | **F-023** heatmap regime × ativo (`n` em toda célula) | B |
| 2 ‖ | **F-024** tabela "regime atual → ranking" + concordância | B |
| 3 ‖ | **F-025** timeline de regimes sobre IBOV e Selic | B |
| 4 | **F-026** internacional: retornos por regime + risk-off | C |
| 5 | **F-029** orquestrador "um comando" + idempotência | C |
| 6 | **F-030** testes de contrato com valor-canário + cache | B |

**Fim de terça = marco de revisão humana.** O Edu recebe: heatmap, timeline, tabela de 1 página,
`macro_quarterly`/`asset_returns_quarterly` e o relatório de saída do pipeline (linhas, min/max, % de
nulos, hash). **A timeline é o sanity check**: se a classificação não "fizer sentido" para quem viveu o
período, há tempo de corrigir na quarta pela manhã.

---

### Onda 5 — quarta 2026-10-14 · **entrega (classe D)**

| Ordem | Feature | Classe |
|---|---|---|
| 1 | **F-028** página de limitações | B |
| 2 | **F-027** notebook de entrega (outputs limpos) | B |
| 3 | **F-031** pacote de entrega ao Comitê | **D** |

**Sequência obrigatória da classe D:** CI N3 verde (e2e + 2 execuções com o mesmo hash) → revisão humana
do número pelo Edu, com 3 valores conferidos por série → dataset **congelado** (versão + hash) →
`docs/plans/infra-ops.md` com **Rollback** → linha em `docs/wiki/log.md` → **comunicação escrita das
substituições de fonte** (F-032) → envio.

> **Sem ADR-001 aceito, o envio não é liberado pelo gate.** Se até quarta-feira cedo D1/D3 não tiverem
> resposta, a saída é o Edu aceitar formalmente a recomendação da pesquisa (1 linha em cada ADR), o que
> congela a especificação e destrava a publicação.

---

## 3. Dependências

```
F-001 (infra) ──► F-002 ‖ F-003 ‖ F-004 ‖ F-005 ‖ F-006 ‖ F-007 ‖ F-008 ‖ F-010 ‖ F-011 ‖ F-012
F-009 (job diário) ── independente, roda hoje e todos os dias
                                        │
                                        ▼
                                 F-013 (raw_series + catálogo)
                                        │
                        ┌───────────────┼────────────────┐
                        ▼               ▼                ▼
                 F-014 (alinhamento)  F-016 (curva)   F-017 (retornos)
                        │               │                │
                        └──────► F-015 (macro_quarterly) │
                                        │                │
                                   F-018 (asof)          │
                                        │                │
                                   F-019 (V1) ──► F-020 ‖ F-021 (V3)
                                                     │
                                                F-022 (métricas)
                                                     │
                                    F-023 ‖ F-024 ‖ F-025 ‖ F-026
                                                     │
                                          F-029 ‖ F-030 ─► F-027 ‖ F-028
                                                     │
                                               F-031 (entrega, D)
```

**Caminho crítico:** F-001 → F-003/F-002/F-006 → F-013 → F-014 → F-017 → F-019 → F-022 → F-023 → F-031.
Qualquer atraso aqui atrasa o Comitê; o resto tem folga.

---

## 4. Paralelismo — regras para subagentes Opus

1. **Um subagente por fonte** na Onda 1 (evita contenção de arquivo). Máximo prático: 3-4 simultâneos.
2. Cada subagente recebe: objetivo, **seção exata** de `docs/research/fontes-de-dados.md`, CAs da SPEC,
   valor-canário, **arquivos permitidos**, arquivos proibidos e o que devolver (matriz + evidência).
3. **Ninguém altera schema existente** em `packages/shared/schemas/` — só acrescenta. Alteração = pausa.
4. **Ninguém toca `docs/research/`** (arquivos de outros agentes) nem `SPEC.md`/`PRD.md`/`ESCOPO-EMAIL`.
5. Features **classe C rodam no máximo duas em paralelo**, e nunca duas que toquem a mesma tabela.
6. Ao encerrar, cada subagente roda `/wiki context <F-NNN>` e deixa 1 linha em `docs/wiki/log.md`.
7. **Revisão numérica independente** em toda feature C: o subagente que calculou **não** confere.

---

## 5. Riscos de prazo e o que é cortado se atrasar

Ordem de corte (primeiro a cair está no topo). Tudo que cai vira item do pacote estendido no `TODO.md`.

| # | O que é cortado | Impacto no entregável | Nota |
|---|---|---|---|
| 1 | **F-012** (FII segmentado via Teva) | B5 parcialmente não atendido; declarar | já é `should`; cortada automaticamente se L2 for negado |
| 2 | **F-011** (FRED / contexto externo) | sem `UST10_BRL`, VIX e Fed Funds | `should`; fallback Yahoo já mapeado |
| 3 | **F-020** (V2 ciclo Selic) | perde o corte secundário | `should`; V1 + V3 bastam para o Comitê |
| 4 | **F-010** (Focus) | perde `juro_real_exante` e as surpresas | **a V1 do pacote mínimo não depende do Focus**; a V3 roda com 5 features |
| 5 | **F-016** (curva) | V3 roda com **5 features**, declarado (CA-086) | mitigação já prevista na SPEC. Cortes 4 e 5 **juntos** → 4 features; com G-02 (`ipca_meta`) ainda aberto → 3. `RegimeNeighborsSchema.n_features` aceita de 3 a 6 e obriga a declarar qual é |
| 6 | **F-024/F-025** (ranking e timeline) | fica só o heatmap | a timeline é o sanity check — cortar só em último caso |
| 7 | **F-026** (internacional) | item **C1** do e-mail sem resposta quantitativa | corte doloroso: é metade do pedido original |
| **nunca** | **F-013..F-019, F-022, F-023, F-028, F-031** | — | núcleo do compromisso: canônico, V1, heatmap, limitações, entrega |

**Riscos técnicos com mitigação já definida**

| Risco | Prob. × Impacto | Mitigação |
|---|---|---|
| FRED inacessível no ambiente do Edu (G-06) | Média × Médio | teste de conectividade como 1º passo de F-011; fallback Yahoo automático |
| Endpoint não documentado muda (B3, MSCI, S3) | Média × Alto | testes de contrato com valor-canário (F-030); fallbacks no catálogo |
| Curva interpolada não conferida em tempo | Média × Médio | V3 com 5 features; inclinação fica fora da V1 |
| `n` por quadrante desbalanceado | Alta × Médio | alerta automático (CA-080); `n` em toda célula |
| Classificação "não faz sentido" na revisão de terça | Média × Alto | timeline entregue **antes** do pacote; quarta de manhã reservada para ajuste |
| D1/D3 sem resposta até quarta | Alta × Alto | Edu aceita formalmente a recomendação (1 linha nos ADRs) e o gate destrava |
| Dependência nova (shrinkage Ledoit-Wolf) | Média × Baixo | checar `scipy`/`scikit-learn`; se precisar instalar → **ADR** antes |

---

## 6. ADRs em jogo

| ADR | Decide | Status | Trava o quê |
|---|---|---|---|
| ADR-001 | D1 + D3 (lente oficial, eixos da V1) | **Proposta** | **publicação** (RF-031/CA-090) |
| ADR-002 | D5 (métrica do heatmap) | **Proposta** | 1 parâmetro de F-023 |
| ADR-003 | D6 (abordagem do internacional) | **Proposta** | formulação de F-026 |
| ADR-004 | L4 (curva via Tesouro Direto) | **Proposta** | fonte de F-016 (classe D se o Feed for contratado) |
| ADR-005 | L1 + L2 + D12 (janelas próprias, Teva) | **Proposta** | universo de F-006, F-012, F-017 |
| ADR-006 | armazenamento + convenção de retorno/alinhamento | **Proposta** | base de F-013, F-014, F-017 — **validar antes da Onda 2** |
| ADR-007 | Supabase descartado na v1 (persistência segue o ADR-006) | **Aceita** (Edu, 2026-10-10) | nada — **fecha** o debate de banco; o compartilhamento com o Alexandre segue pelo pacote F-031 |

---

## 7. Depois do Comitê

1. Fechar o pacote estendido na ordem: F-034 (dupla materialização) → F-036 (risco-país) →
   F-037 (termos de troca) → F-033 (V1b) → F-035 (variância mínima) → F-039 (clustering/HMM) →
   F-038 (FII próprio) → F-040 (atualização trimestral).
2. Manter o **job diário da ANBIMA** rodando: em 12 meses a casa tem ETTJ Svensson proprietária.
3. Revisar este plano com o que de fato aconteceu (`CURRENT_REALITY.md`) antes de prometer a fase 2.

---

*Próximo passo: **feito** — **F-009** e **F-001** já estão em `TODO.md §1`; executar a Onda 0 hoje.*
