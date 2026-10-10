# ADR-001 — Lente de regime oficial do Comitê e eixos da V1

- **Status:** **Proposta** — aguardando decisão de Edu/Alexandre (bloqueantes **D1** e **D3**)
- **Data:** 2026-10-10
- **Autor:** `/SDD-avancado` (modo autônomo), a partir de `docs/research/metodologia-regimes-macro.md`
- **Substitui:** —
- **Decide:** D1 (qual lente é oficial) + D3 (eixo inflação da V1)
- **Cobre:** SPEC RF-027, RF-028, RF-029, RF-031 · CA-078..091

> **Este ADR precisa estar ACEITO antes de rodar a classificação sobre os retornos** (RF-031/CA-090).
> Enquanto estiver em Proposta, o schema `regimes` grava `especificacao_congelada = False` e o número
> **não é publicável** (gate da classe D).

---

## Contexto

O e-mail do Alexandre pede "como cada classe de ativo e até setores performaram em **momentos
semelhantes**". A pesquisa metodológica concluiu que, com **83 trimestres**, não existe graus de
liberdade para procurar "o" regime verdadeiro: a entrega honesta são **lentes paralelas** com a
concordância entre elas como sinal.

Três lentes foram desenhadas:

- **V1 — quadrantes crescimento × inflação** (Bridgewater / Investment Clock): 4 células, ~20
  trimestres cada, replicável em planilha, auditável.
- **V2 — V1 × ciclo Selic**: 12 estados teóricos, ~7-8 povoados, `n` de 5 a 15. É a linguagem real do
  Comitê brasileiro, mas é **endógena** (o Copom reage a crescimento e inflação) e sofre com `n`.
- **V3 — vizinhos mais próximos**: responde **literalmente** ao e-mail, sem binarizar nada, com um
  único hiperparâmetro (k).

Para o eixo de inflação da V1 há duas definições possíveis: **nível vs. a meta** (exige a série
histórica de metas do CMN, hoje gap **G-02**) ou **aceleração** (Δ do IPCA 12m, sai do SGS 433).
A escolha **muda o rótulo dos 83 trimestres** — reclassificar depois de ver o heatmap invalidaria o
entregável (risco R-08, overfitting).

Sem decisão humana, a estrutura precisa de um padrão para poder ser construída agora (prazo 2026-10-14).

## Decisão

**Adotar provisoriamente a recomendação da pesquisa:**

1. **V1 é a lente oficial** do Comitê (entregável principal: heatmap e timeline).
2. **V3 é o diferencial** e responde ao pedido do e-mail ("momentos semelhantes"): 8 vizinhos +
   retorno dos ativos nos trimestres **seguintes** aos vizinhos.
3. **V2 é corte secundário**, sempre com `n` visível, **nunca** célula única de decisão.
4. **Eixo inflação da V1 = aceleração** (`pi_T` = IPCA 12m em T − IPCA 12m em T−1).
   Eixo crescimento = `g_T` = IBC-Br a/a dessaz. menos média móvel de 20 trimestres (D2, não
   bloqueante: tendência na v1, surpresa vs. Focus na fase 2).
5. Rótulos: `RECUPERACAO` (↑g, ↓π) · `EXPANSAO_INFL` (↑g, ↑π) · `ESTAGFLACAO` (↓g, ↑π) ·
   `DESACELERACAO` (↓g, ↓π). Empate exato herda o sinal do trimestre anterior.
6. A especificação fica **congelada** neste ADR. Qualquer ajuste posterior nasce como **V1.1** e as
   duas versões são reportadas lado a lado.

## Alternativas consideradas

- **A — V2 como oficial.** Prós: é o eixo que o Comitê debate (ciclo de juros). Contras: 12 estados
  com `n` de 5 a 15 → metade das células entra em `ALERTA_N_BAIXO` e várias em supressão
  (`n < 5`); além disso o ciclo Selic é em parte *função* de V1, não informação nova. **Rejeitada
  como lente principal, mantida como corte.**
- **B — V3 como oficial.** Prós: responde ao e-mail no mesmo vocabulário, não binariza. Contras: a
  covariância de Mahalanobis em 83×6 é instável; o resultado é uma lista de vizinhos, não uma grade
  que o gestor usa para alocar. **Rejeitada como lente principal, mantida como diferencial.**
- **C — Eixo inflação = nível vs. meta.** Prós: conceitualmente aderente ao regime de metas
  brasileiro. Contras: depende da série histórica de metas do CMN e da data exata da meta contínua
  (**G-02, a confirmar**) — hoje `ipca_meta` é nulo no canônico. **Rejeitada por dependência não
  resolvida**, mas o schema já tem a coluna pronta.
- **D — Clustering (GMM/k-means) ou HMM.** Prós: deixa o dado falar; dá probabilidade de regime.
  Contras: 83 observações e 5-6 variáveis → overfitting quase garantido; estados sem rótulo
  econômico; com a quebra estrutural de 2016 os clusters viram "antes/depois de 2016".
  **Fora de escopo da v1** (fase 2, com dados mensais).

## Consequências

### Positivas
- Entregável auditável em planilha pelo próprio Alexandre; ~20 trimestres por célula.
- A concordância entre V1, V2 e V3 (RF-037) vira resultado reportado, não escondido.
- Eixo de aceleração não depende de nenhum gap aberto — é implementável hoje.

### Negativas / trade-offs
- "Aceleração" ignora o **nível** de inflação: um trimestre com IPCA 12m a 10% em desaceleração é
  classificado como "inflação caindo". Precisa estar na página de limitações.
- V1 binariza intensidade (um gap de 0,1 p.p. e de 3 p.p. caem no mesmo quadrante).
- V2 com `n` pequeno pode ser lida como conclusiva por quem olhar só o slide — daí a exigência de `n`
  em toda célula.

### Neutras
- Os três cálculos usam a **mesma** tabela `regimes` + `regime_neighbors`: virar a decisão D1 muda
  qual coluna vira eixo do heatmap, **não** o schema (custo de virada **baixo**).
- Virar D3 para "nível vs. meta" exige resolver G-02 e **re-rodar a classificação** + regenerar
  figuras (custo **médio**), sem mudança estrutural.

## Referências

- PRD §5.3, §13.2 (D1, D3), §12 (R-08)
- SPEC §5 (RF-027..031), §11, Anti-SPEC §10.2.9
- `docs/research/metodologia-regimes-macro.md` §1, §2, §5.5, §8
- Contrato: `packages/shared/schemas/regimes.py` (`RegimeV1`, `especificacao_congelada`)
