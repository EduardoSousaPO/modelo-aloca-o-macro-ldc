# ADR-003 — Abordagem do dimensionamento da alocação internacional

- **Status:** **Proposta** — aguardando decisão de Edu/Alexandre (bloqueante **D6**)
- **Data:** 2026-10-10
- **Autor:** `/SDD-avancado` (modo autônomo)
- **Substitui:** —
- **Decide:** D6
- **Cobre:** SPEC RF-038, RF-039 · CA-104..107 · item **C1** do e-mail

---

## Contexto

O e-mail abre com "modelo de alocação macro doméstica **e tamanho da alocação internacional**", mas
**não lista nenhuma série internacional** nos blocos A/B. O item C1 do checklist de escopo registra
isso como escopo implícito; o PRD §4.2 o torna explícito.

A pergunta operacional é: **quanto no exterior?** Três formas de responder:

- **piso estrutural** (número fixo, à la FGV: 16-18% para neutralizar o efeito do câmbio sobre o
  padrão de consumo do brasileiro; faixa ótima 20-35% conforme a fase da vida);
- **100% tático por regime** (otimização de variância mínima dentro de cada regime → peso de
  `SP500_BRL` por regime);
- **híbrido**: piso estrutural + banda tática por regime.

Restrição estatística dura: com `n ≈ 20` trimestres por regime e 5 ativos, a matriz de covariância é
ruidosa. Otimização nesse regime de amostra **não sustenta um número pontual** — ela produz pesos que
mudam materialmente com shrinkage, com o conjunto de ativos e com a janela.

Há também uma distinção que o material do Comitê precisa carregar: **global hedgeado** (XP: ~2,5% a
7% por perfil) é categoria **diferente** de **exposição cambial** (FGV: 16-35%). Comparar os dois
números como se fossem a mesma coisa é erro de leitura, não de dado.

## Decisão

**Adotar provisoriamente a recomendação da pesquisa: híbrido — piso estrutural de 16-20% + banda
tática de 15-35% por regime**, entregue como **faixa**, nunca como número pontual.

Operacionalmente:

1. O internacional entra como **classe de ativo em BRL dentro do mesmo arcabouço** de regimes
   (mesmo heatmap, mesma métrica, mesmos regimes) — não como anexo:
   `SP500_BRL`, `USD_BRL`, `GOLD_BRL`, `UST10_BRL` (+ `ACWI_BRL`, `SP500_HEDGE` quando possível).
2. Entrega quantitativa de apoio (RF-038): `corr(USDBRL, IBOV)` **por regime** e nos **10 piores
   trimestres do IBOV**.
3. Regra de risk-off (RF-039): `stress = 1` quando a inclinação cai > 1 desvio-padrão **ou** USDBRL
   sobe > 10% no trimestre; medir **quanto de USD neutraliza a queda do IBOV** nesses trimestres.
   O ramo EMBI do gatilho fica em fase 2 (não há fonte gratuita contínua — L8).
4. Reportar **ambas** as versões, hedgeada e sem hedge (D7), com a distinção conceitual explícita.
5. A saída é um **intervalo com justificativa estatística**, acompanhado do `n` de cada regime.
   Variância mínima por regime (com shrinkage) e fronteira eficiente ficam em **fase 2**.

## Alternativas consideradas

- **A — Piso estrutural fixo.** Prós: simples, defensável, independe de `n`. Contras: ignora o
  arcabouço de regimes que é justamente o produto; não responde "e neste trimestre?". **Absorvida
  como o piso do híbrido.**
- **B — 100% tático por regime (otimização).** Prós: usa o modelo até o fim; dá um número.
  Contras: `n ≈ 20` e 5 ativos → pesos instáveis; entrega um ponto com precisão falsa; é o caminho
  mais rápido para o Comitê ler descrição como previsão. **Rejeitada para a v1.**
- **C — Não responder (só mostrar os retornos internacionais por regime).** Contras: deixa sem
  resposta o item C1 do e-mail, que é metade do pedido. **Rejeitada.**

## Consequências

### Positivas
- A resposta ao e-mail é honesta quanto à precisão disponível e ainda assim acionável (faixa + regra
  de risk-off).
- Usa a evidência brasileira já levantada (FGVcef, 21.000 janelas 2005-2026: só o dólar funcionou
  como diversificação genuína; CDI ganhou poder de compra em dólar em 49,4% dos períodos contra
  90,1% do S&P 500).

### Negativas / trade-offs
- "Faixa" pode frustrar quem quer um número para o slide — exige uma frase de enquadramento.
- `GOLD_BRL` depende de fonte de ouro spot **não confirmada** (gap G-03): se não resolver, a linha
  sai do heatmap com `BLOQUEADO — FONTE INDISPONÍVEL`, nunca com proxy silencioso.
- A regra de risk-off usa a inclinação **construída por nós** (ADR-004), com a limitação herdada.

### Neutras
- RF-038 (retornos e correlações por regime) é idêntico nas três alternativas: virar D6 muda apenas a
  **formulação da recomendação** em RF-039 (custo **baixo-médio**).

## Referências

- PRD §4.2, §5.4 (RF-038, RF-039), §13.2 (D6), §13.1 (P-03, P-04), H-04
- SPEC RF-038/039, Anti-SPEC §10.2.10
- `docs/research/metodologia-regimes-macro.md` §4.1, §4.2, §4.3
