# ADR-004 — Inclinação da curva via Tesouro Direto em vez da ETTJ ANBIMA

- **Status:** **Proposta** — aguardando decisão de Edu/Alexandre (bloqueante **L4**)
- **Data:** 2026-10-10
- **Autor:** `/SDD-avancado` (modo autônomo)
- **Substitui:** —
- **Decide:** L4 (contratar o ANBIMA Feed ou não) e, por consequência, L5 e L7
- **Cobre:** SPEC RF-008, RF-009, RF-010 · CA-020..029 · item **A6** (e A5) do e-mail

> **Esta decisão troca a fonte de um item pedido explicitamente no e-mail.** Se aceita, exige entrada
> em `docs/plans/DECISIONS_LOG.md` **e** comunicação escrita ao Alexandre (RF-045/RF-052).

---

## Contexto

O e-mail pede, no item A6: *"ANBIMA (DataFit / ANBIMA Feed): dados históricos da estrutura a termo da
curva de juros (ETTJ) — fundamentais para extrair a inclinação da curva (diferença entre DI de curto e
longo prazo)"*.

A pesquisa mediu, endpoint por endpoint:

| Rota | Cobre 2006-2026? | Evidência |
|---|---|---|
| **SGS 7801-7806** (swap DI × pré) — a rota sugerida no e-mail | ❌ | diárias morrem em **30/09/2019**; mensais 7816-7827 em 01/08/2019 |
| **ANBIMA `ms*.txt`** (taxas indicativas) | ❌ | **janela rolante de ~20 dias úteis**; nada de 2006 existe no diretório |
| **ANBIMA Curva Zero (`CZ-down.asp`)** | ❌ | janela rolante; `Dt_Ref=02/01/2006` devolve **0 bytes**; o mais antigo com dados é 14/09/2026 |
| **API interna do portal ANBIMA Data** | ❌ | exige JWT com token reCAPTCHA **de uso único** (reuso → HTTP 418) |
| **ANBIMA Feed** | ✅ (presumido) | **PAGO**, OAuth2; ~R$ 686/mês (usuário final) a ~R$ 8.238/mês (parceiro) |
| **Ipeadata `ANBIMA366_TJTLN{1,3,6,12}366`** | ✅ parcial | ETTJ prefixada, diária, 2000-04-04 → hoje — mas **só a ponta curta** (1 a 12 meses) |
| **Tesouro Direto (`precotaxatesourodireto.csv`)** | ✅ | **um arquivo**, 31/12/2004 → hoje, 177.260 linhas, 248 dias úteis já em 2006 |

Além disso: "ANBIMA DataFit", citado no e-mail, **não existe** em nenhuma propriedade da ANBIMA
(existem ANBIMA Data, gratuito, e ANBIMA Feed, pago) — L12.

Restrição de projeto: **orçamento de dados zero**; nada no caminho crítico depende de fonte paga
(PRD §8). E há uma restrição física: em 2006 a LTN mais longa vencia em **01/01/2009** e a NTN-F mais
longa em **01/01/2014** — o **vértice nominal de 10 anos não existe antes de ~2010** (L5),
independentemente da fonte escolhida.

## Decisão

**Adotar provisoriamente a recomendação da pesquisa: construir a inclinação da curva a partir do
Tesouro Direto, sem contratar o ANBIMA Feed.**

1. Fonte primária da curva: `precotaxatesourodireto.csv` (CKAN do Tesouro Transparente), com
   **User-Agent de browser**, `;`, decimal vírgula, **latin-1**, datas `dd/mm/aaaa`.
2. **Vértices fixos por interpolação** em cada data (1, 3 e 5 anos), com flag
   `vertice_extrapolado = True` quando o prazo-alvo cai fora do intervalo de vencimentos daquele dia.
   Prazo-alvo sem cobertura → **`NULL` + flag**, nunca extrapolação silenciosa.
3. **Variável principal de regime: inclinação REAL** (NTN-B 5a − 1a) — robusta desde 2006, porque
   já em 2006 havia 10 vencimentos de NTN-B, até 15/05/2045.
4. Inclinação **nominal** 5a − 1a como secundária; **5 anos** é a ponta longa nominal viável na janela
   inteira. O vértice nominal de 10 anos é declaradamente indisponível antes de ~2010.
5. Inflação implícita (breakeven) do mesmo arquivo, por **razão**:
   `(1 + nominal) / (1 + real) − 1`.
6. **Trilho incremental ligado hoje** (RF-010): job diário idempotente arquivando `Msec_txt.txt` e o
   POST `CZ-down.asp` em `data/raw/anbima-*/`. Em 12 meses a casa terá série proprietária de ETTJ
   Svensson; ausência/atraso do arquivo é caso **normal**.
7. Toda figura e tabela que usa a curva declara: **taxas do Tesouro Direto (varejo), interpoladas —
   não é a curva Svensson oficial da ANBIMA.**

## Alternativas consideradas

- **A — Contratar o ANBIMA Feed.** Prós: é literalmente o que o e-mail pede; curva Svensson oficial
  com histórico; encerra a discussão metodológica. Contras: custo recorrente; vira **classe D**
  (credencial/API paga, autorização humana obrigatória, segredo fora do repo); não entrega em 3 dias
  úteis; o preço levantado é leitura de página, `[NÃO VERIFICADO]`. **Em aberto para o Edu** — se
  escolhida, este ADR é substituído.
- **B — DI futuro da B3 via `pyield`.** Prós: é o "DI de curto e longo prazo" do e-mail, market-based.
  Contras: `pyield` 0.59 exige Python ≥ 3.12 e polars (o projeto está em 3.11); reconstrução via
  arquivos diários da B3 **não verificada**. **Candidata de fase 2.**
- **C — Ipeadata ANBIMA (ponta curta) apenas.** Resolve 1 a 12 meses, não dá inclinação longa.
  **Mantida como complemento da ponta curta.**
- **D — Tirar a curva do modelo.** A V3 roda com 5 features e declara (CA-086). **Mantida como plano
  de contingência de prazo, não como decisão.**

## Consequências

### Positivas
- Cobertura completa 2006-2026 sem custo, sem credencial e com um único download.
- Breakeven de inflação sai de graça, do mesmo arquivo.
- O trilho incremental transforma uma limitação em ativo proprietário da casa.

### Negativas / trade-offs
- **Não é a curva oficial da ANBIMA.** São taxas de varejo, com pequeno spread vs. o secundário puro.
- A variável de regime passa a ser **real** em vez de nominal — mudança conceitual que precisa estar
  declarada no material (L5).
- As séries de curva são **construídas por nós**: no catálogo entram com `confianca =
  NAO_VERIFICADO` e exigem conferência numérica classe C antes de virar número em slide.
- Substituição de fonte pedida explicitamente no e-mail → obriga registro + comunicação (RF-045).

### Neutras
- A interface no canônico (`inclinacao_real_5a_1a`, `inclinacao_nominal_5a_1a`, `breakeven_5a`,
  `vertice_extrapolado`) **não muda** se o Feed for contratado depois: troca-se a implementação da
  fonte (custo de virada **médio**, sem mudança de schema).

## Referências

- PRD §5.1 (RF-008, RF-009, RF-010), §13.2 (L4), §13.3 (L5, L6, L7, L12)
- SPEC RF-009, CA-023..029, §11
- `docs/research/fontes-de-dados.md` §A4.1, §A4.2, §A5 (A5.1-A5.4), §C11
- `docs/research/fontes-de-dados-RESUMO.md` §3 (decisões 1 e 2), §4 (R3)
- Contrato: `packages/shared/schemas/series_catalog_data.py` (`CURVA_*`, `INCLINACAO_*`, `ANBIMA_*`)
