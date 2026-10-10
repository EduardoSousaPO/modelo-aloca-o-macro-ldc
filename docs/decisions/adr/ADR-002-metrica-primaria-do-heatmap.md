# ADR-002 — Métrica primária do heatmap regime × ativo

- **Status:** **Proposta** — aguardando decisão de Edu/Alexandre (bloqueante **D5**)
- **Data:** 2026-10-10
- **Autor:** `/SDD-avancado` (modo autônomo)
- **Substitui:** —
- **Decide:** D5
- **Cobre:** SPEC RF-024, RF-032, RF-033, RF-034 · CA-069..071, CA-092..099

---

## Contexto

O heatmap regime × ativo é o **entregável visual central** (≥ 18 ativos × regimes). A célula precisa
de **uma** métrica primária, e a escolha determina a leitura da reunião.

O obstáculo é a **quebra estrutural** da janela: a Selic foi de ~19% (2006) a 2% (2020) e voltou a
dois dígitos. Consequência direta: **retorno nominal não é comparável entre épocas**. Um IMA-B
rendendo 4% no trimestre em 2006 (com CDI de ~3,5%) e 4% em 2020 (com CDI de ~0,5%) são eventos
economicamente opostos, e o nominal não distingue.

Três candidatas: **nominal**, **excesso sobre CDI** e **retorno real** (deflacionado pelo IPCA).

## Decisão

**Adotar provisoriamente a recomendação da pesquisa: `excesso_cdi` como métrica primária do
heatmap**, com nominal e real como colunas informativas disponíveis em toda tabela.

Regras que acompanham a decisão (não negociáveis, já na SPEC):

1. Excesso sobre CDI **sempre por razão**: `(1 + r_ativo) / (1 + r_cdi) − 1`. Nunca subtração — com
   Selic a 14% a diferença é material e existe teste unitário que falha se a subtração for usada.
2. Retorno real idem: `(1 + r) / (1 + ipca_tri) − 1`, com o IPCA do mesmo trimestre, aplicado **uma**
   vez.
3. Escala divergente centrada em **0** (= "empatou com o CDI").
4. `hit_ratio_cdi` (% de trimestres em que bateu o CDI) acompanha a célula — é a métrica que o Comitê
   brasileiro de fato usa.
5. `n` anotado em **toda** célula; `n < 8` hachurado; `n < 5` sem conclusão.
6. O rodapé nomeia a métrica explicitamente: "excesso sobre CDI médio trimestral".

## Alternativas consideradas

- **A — Retorno nominal.** Prós: é o número que o cliente vê no extrato; não depende de outra série.
  Contras: incomparável entre 2006 e 2020 (patamar de Selic); faz renda fixa parecer ótima em toda a
  primeira metade da amostra. **Rejeitada como primária, mantida como coluna informativa.**
- **B — Retorno real (deflacionado pelo IPCA).** Prós: é o que preserva poder de compra; leitura
  natural para o investidor final. Contras: em trimestres de choque de inflação penaliza
  indistintamente todas as classes e confunde "o ativo foi mal" com "a inflação foi alta"; e o
  benchmark implícito (IPCA) não é investível. **Mantida como coluna informativa.**
- **C — Sharpe por regime como célula.** Rejeitada: índice não é ativo investível sem fricção
  (carteira teórica é revisada), e com `n ≈ 20` o desvio é ruidoso. Fica como coluna com aviso.

## Consequências

### Positivas
- Compara 2006 com 2026 sem o viés de patamar de juros.
- Casa com a pergunta operacional do Comitê: "nesse regime, essa classe bateu o CDI? em quantos dos
  trimestres?".
- `CDI` como linha do heatmap fica identicamente 0 — é o sanity check visual da própria métrica.

### Negativas / trade-offs
- Em regimes de Selic muito alta, um ativo com retorno nominal excelente pode aparecer neutro — exige
  uma frase de leitura no material do Comitê.
- Exige o CDI trimestral correto (acumulação geométrica de SGS 12) como pré-requisito de **tudo**:
  um erro no CDI contamina todas as células. Daí o valor-canário CDI 2006 = 15,0271%.

### Neutras
- As três métricas são **colunas do mesmo schema** (`asset_returns_quarterly`): virar D5 é trocar um
  parâmetro da figura (custo **baixo**), sem tocar pipeline nem contrato.

## Referências

- PRD §5.4, §11 (RN-02), §13.2 (D5), §12 (R-03)
- SPEC RF-024, RF-033, Anti-SPEC §10.2.13
- `docs/research/metodologia-regimes-macro.md` §3, §5.3
- Contrato: `packages/shared/schemas/asset_returns_quarterly.py`
