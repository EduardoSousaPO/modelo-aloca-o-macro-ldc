# Módulo `regimes` — classificação de regimes macro e métricas (**classe C**)

> Síntese — fonte de verdade: `docs/research/metodologia-regimes-macro.md` + `SPEC.md` RF-027..RF-040 + **ADR-001/002/003**. **Status (2026-10-11): nada implementado, mas os insumos estão prontos** — a Onda 3 começa aqui.

## Propósito

Responder à pergunta literal do e-mail — *"como cada classe de ativo e setor performou em **momentos
semelhantes**"* — classificando os 83 trimestres e medindo retorno por regime × ativo. Entrega **lentes
paralelas**, não uma verdade: com `n ≈ 20` por célula não há graus de liberdade para achar "o" regime.

## Lentes / RFs cobertos

| Lente / saída | O que é | RF |
|---|---|---|
| **V1** — quadrantes crescimento × inflação | 4 células, ~20 trimestres cada; replicável em planilha | RF-027, RF-030, RF-031 |
| **V2** — V1 × ciclo Selic | 12 estados teóricos, ~7-8 povoados; linguagem do Comitê, mas **endógena** | RF-028 |
| **V3** — vizinhos mais próximos (Mahalanobis + shrinkage, k=8) | responde **literalmente** ao e-mail, sem binarizar | RF-029, RF-036 |
| `regimes` / `regime_neighbors` | rótulos + escores contínuos · saída da V3 | `regimes.py` |
| Métricas por regime × ativo · heatmap · timeline · ranking | média, mediana, `n`, dispersão | RF-032..RF-035, RF-037, RF-040 |
| Dimensionamento internacional + regra de risk-off | piso estrutural + banda tática por regime | RF-038, RF-039 |

## Fonte primária e fallback

- **Primária:** `macro_quarterly` + `asset_returns_quarterly` da camada canônica — **as duas existem desde 2026-10-11** e são o insumo único: `macro_quarterly` com **83 × 42** (+ `macro_quarterly_provenance`, 2.548 linhas) e `asset_returns_quarterly` com **1.963** linhas / **24** ativos (USDBRL incluído por **D-l**, que é o que RF-038 precisa). Métrica primária do heatmap: **excesso sobre CDI** (ADR-002). Eixo inflação da V1: **aceleração do IPCA 12m** (ADR-001) — a coluna é `ipca_12m_delta`.
- **A inclinação principal (`INCLINACAO_REAL_5A_3A`, D-i) não é coluna de `macro_quarterly`** (**D-n**): leia a **série** de `raw_series`/`data/processed/curva/` via `alinhar_series`, como F-017 faz com as derivadas de F-007. `macro_quarterly` publica a 5a−1a com **33 nulos (39,8%)** e declarados.
- **Unidade (D-o):** `macro_quarterly` em **por cento/pp**, `asset_returns_quarterly` em **fração**. As duas têm `cdi_tri`/`ipca_tri` com o mesmo nome em escalas diferentes — ver `CONTRACTS.md §3/§4`.
- **Fallback:** F-016 (curva) e F-010 (Focus) **chegaram**, então o corte de features por fonte ausente não se aplica; `RegimeNeighborsSchema.n_features` aceita `>= 3` e a redução, se houver, é declarada (CA-086). Clustering (GMM/k-means) e HMM mensal ficam para a fase 2 (**F-039**) como validação independente.

## Armadilhas conhecidas (pesquisa)

- **`n` pequeno:** ~20 trimestres por regime; **diferença < 5 pp entre células é ruído**. `n` em **toda** célula, e célula com `n < 5` nunca vira conclusão publicada.
- **A V1 classifica 67 dos 83 trimestres, não 83** (**D-m**): `ibcbr_gap` tem **16** nulos porque a média móvel de 20 trimestres só fecha em **2009Q4** e o IBC-Br não existe antes de 2003. 2006-2009, **inclusive a crise de 2008**, fica fora do eixo de crescimento com a regra estrita. Vai à página de limitações (F-028).
- **Overfitting:** ajustar a especificação de regime **depois** de ver os retornos é proibido (Anti-SPEC §10). Enquanto **ADR-001 estiver em Proposta**, `especificacao_congelada = False` e **nada é publicável** (RF-031/CA-090).
- **Descritivo ≠ preditivo.** É o maior risco reputacional: nenhuma saída deste módulo é previsão.
- **V2 é endógena** (o Copom reage a crescimento e inflação) → corte secundário, nunca lente única.
- **Quebra estrutural 2006-2008 vs. pós-2016** e janelas desiguais por ativo → a timeline sobre IBOV e Selic é o **sanity check** com quem viveu o período, entregue **antes** do pacote final.
- **Concordância entre lentes é o sinal**: quando V1, V2 e V3 apontam o mesmo ativo, a leitura é robusta; quando divergem, a divergência é o resultado (RF-034/RF-037).

**Features do TODO:** **F-019** (V1) · **F-020** (V2, `should`) · **F-021** (V3) · **F-022** (métricas) ·
**F-023** (heatmap) · **F-024** (ranking) · **F-025** (timeline) · **F-026** (internacional) · **F-033**/**F-035**/**F-039** (fase 2).
