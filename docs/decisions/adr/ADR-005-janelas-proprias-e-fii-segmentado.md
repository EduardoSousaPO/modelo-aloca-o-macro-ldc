# ADR-005 — Janelas próprias para índices sem 20 anos e FII segmentado via Teva

- **Status:** **Proposta** — aguardando decisão de Edu/Alexandre (bloqueantes **L1**, **L2**, **D12**)
- **Data:** 2026-10-10
- **Autor:** `/SDD-avancado` (modo autônomo)
- **Substitui:** —
- **Decide:** L1 (IFIX sem 2006-2010), L2 (segmentação de FII via provedor privado), D12 (escopo dos
  setoriais e do FII segmentado no pacote mínimo); absorve L3 (ICON 2007, IMOB 2008)
- **Cobre:** SPEC RF-012, RF-013, RF-014, RF-022, RF-032, RF-033 · CA-036..042, CA-063, CA-093

> **É a decisão de maior impacto metodológico do projeto** (pesquisa, §3 do RESUMO): ela define o
> universo de **todas** as tabelas.

---

## Contexto

O e-mail pede 20 anos (≈ 2006 → 2026) e, no bloco B, nomeia os setoriais da B3 e "IFIX (geral) e
segmentações específicas (Tijolo vs. Papel, Logística, Shoppings)".

A pesquisa mediu índice por índice, na própria API da B3:

| Pedido no e-mail | Veredito medido |
|---|---|
| IBOV, SMLL, IDIV, IFNC, IMAT, INDX, IEEX (IEE), UTIL | ✅ **2006 completo** (246 pontos em 2006) |
| **ICON** | ❌ base 28/12/2006 = 1.000,00 → série efetiva **de 2007** |
| **IMOB** | ❌ base 28/12/2007 = 1.000,00 → série efetiva **de 2008** |
| **IFIX** | ❌ base 30/12/2010 = 1.000,00 → série efetiva **de 2011** (perde metade da janela) |
| **FII por segmento** | ❌ **a B3 não tem** índice setorial de FII; o IFIX-L (`IFIL`) é filtro de liquidez, não segmento |

Para a segmentação há duas rotas: **Teva Indices** (bucket GCS público e listável, retorno total,
todos os segmentos começando em **02/01/2019 = 100**, provedor privado **sem licença comercial
explícita**) ou **construção própria** (COTAHIST + informe mensal de FII da CVM) — que (a) só tem
classificação a partir de 2016, (b) sofre a **quebra de taxonomia da Res. CVM 175** (`Mandato` vazio
desde 2025-09; no formato novo não dá para separar Tijolo × Papel pelo `Segmento_Atuacao`) e
(c) é esforço alto.

A pergunta de fundo: **painel desbalanceado com janelas próprias** ou **janela comum estrita**
(2011-2026, que preserva comparabilidade mas joga fora metade do período pedido)?

## Decisão

**Adotar provisoriamente a recomendação da pesquisa:**

1. **Painel desbalanceado com janela própria por ativo.** Cada série entra com o seu
   `data_inicio_serie`, `n` por célula e `data_inicio` no rodapé de toda figura. O schema
   `asset_returns_quarterly` **proíbe por contrato** linha anterior ao início da série
   (check `sem_trimestre_antes_do_inicio_da_serie`).
2. **IFIX: janela 2011-2026**, declarada. **IMOB (2008+) como proxy imperfeito** do ciclo imobiliário
   antes de 2011, rotulado como proxy. **Nenhum IFIX sintético pré-2011** (seria ruído: o mercado de
   FII em 2006-2010 era minúsculo).
3. **ICON (2007+) e IMOB (2008+)**: janela própria com nota de rodapé; nada de forçar painel
   balanceado.
4. **FII segmentado: Teva (2019+), `should`, best-effort**, para **dispersão setorial**, tratado como
   **qualitativo** — declarando que cobre ~2 ciclos macro, insuficiente para inferência estatística.
   Uso interno de análise, **sem redistribuição** (`licenca_restrita = True` no catálogo).
   Arquivo casado por **regex** no prefixo numérico (o nome traz versão embutida, `v0.27`).
5. **Setoriais da B3 no pacote mínimo: best-effort** — os que têm 2006 entram direto; ICON e IMOB
   entram com janela própria; `IFIL` fica fora.
6. Construção própria de FII (COTAHIST + CVM) e extensão 2016-2019: **fase 2**.
7. **Gap G-01 declarado:** quais setoriais da B3 são de retorno total ainda não foi confirmado índice
   por índice. `is_total_return` fica `None` para eles no catálogo, e isso aparece na página de
   limitações. Confirmados: **IBOV** e **IFIX** são retorno total; **IMA** (ANBIMA) também.

## Alternativas consideradas

- **A — Janela comum estrita 2011-2026.** Prós: painel balanceado, comparabilidade perfeita entre
  linhas, nenhuma nota de rodapé. Contras: **descarta metade da janela pedida no e-mail**, elimina a
  crise de 2008 e todo o ciclo de Selic a 19% — justamente os regimes mais informativos; o `n` por
  regime cai de ~20 para ~15. **Rejeitada**, mas é a alternativa a reavaliar se o Comitê exigir
  comparabilidade estrita (custo de virada **alto**: muda o universo de todas as tabelas).
- **B — Reconstruir IFIX sintético pré-2011.** Rejeitada pela Anti-SPEC (§10.1.1): seria dado
  inventado, com mercado ilíquido e sem benchmark de referência.
- **C — Construção própria de FII desde 2016 (COTAHIST + CVM).** Prós: sem dependência de terceiro,
  classificação por balanço imune à taxonomia. Contras: esforço alto, incompatível com 3 dias úteis;
  85,5% de match por ISIN exige fallback por CNPJ. **Fase 2.**
- **D — FII segmentado fora do escopo.** Prós: elimina o risco de licença. Contras: deixa um item
  explícito do e-mail (B5) sem resposta. **Rejeitada, mas é a virada mais barata se L2 for negado
  (custo baixo: F-012 é isolada e `should`).**

## Consequências

### Positivas
- Mantém os 20 anos pedidos para a maior parte do universo (renda fixa, IBOV e 7 setoriais cobrem
  2006 inteiro).
- Transparência total sobre cobertura: `n` e `data_inicio` em toda célula e rodapé.
- Nenhum dado inventado; nenhuma conclusão sobre FII pré-2011.

### Negativas / trade-offs
- O heatmap tem **linhas com `n` diferentes** — exige leitura cuidadosa e hachura para `n < 8`.
- Comparar IFIX (2011+) com IBOV (2006+) no mesmo quadro é comparar amostras diferentes; a página de
  limitações precisa dizer isso.
- Dependência de provedor privado (Teva) para o item B5, com licença não explícita.

### Neutras
- O schema suporta as três alternativas sem alteração: `data_inicio_serie` e `n_obs` já são
  obrigatórios. Restringir a janela depois é um filtro, não uma migração.

## Referências

- PRD §5.1 (RF-012..014), §13.2 (D12, L1, L2), §13.3 (L3), §12 (R-02)
- SPEC RF-013/014, CA-036..042, CA-063, Anti-SPEC §10.1.1
- `docs/research/fontes-de-dados.md` §B8, §B9
- `docs/research/fontes-de-dados-RESUMO.md` §2 (L1, L2, L3), §3 (decisões 3 e 5)
- `docs/research/metodologia-regimes-macro.md` §5.2
