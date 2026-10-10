# Overview — estrategia-macro-ldc-dados

> **O que este projeto entrega hoje em 1 página.** Leitura em 60s.
>
> **Fonte de verdade do escopo:** [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
> (imutável). **Fonte de verdade do produto:** [`docs/product/PRD.md`](../product/PRD.md) (v1.0, 2026-10-10).
> Esta página **resume** o PRD — não o duplica. Em conflito, vale o PRD; em conflito de escopo, vale o e-mail.

**Última revisão:** 2026-10-10
**Versão refletida:** PRD v1.0 (gerado em modo autônomo; **aprovação do Edu pendente**)

---

## 1. Em 1 frase

> Ferramenta interna de dados/quant da LDC Capital que monta a base estatística trimestral de 20 anos
> (macro brasileiro + desempenho de ativos e subsetores) e classifica regimes macro, para fundamentar o
> modelo de alocação macro doméstica e o tamanho da alocação internacional do Comitê de Alocação.

## 2. Problema e objetivo (do PRD §1)

O Comitê decide alocação com leitura qualitativa. Não existe base que responda **"em trimestres parecidos com
o atual, como cada classe de ativo e cada setor performou?"**. Os dados existem em 8+ fontes incompatíveis, e
rotas óbvias estão mortas (swap DI×pré do SGS parou em set/2019; ETTJ histórica da ANBIMA é paga).

**Objetivo da v1:** até **2026-10-13**, dataset canônico trimestral regenerável com um comando, cobrindo
**≥ 90% das séries pedidas** em 2006→2026, com **3 valores por série conferidos na fonte**, mais o heatmap
regime × ativo e a tabela "regime atual → ranking".

**O produto é descritivo, não preditivo.** Confundir os dois é o maior risco reputacional.

## 3. Para quem

- **Alexandre Kaercher** (gestor, cliente interno) — consome dataset + heatmap para modelar; não roda o pipeline.
- **Eduardo (Edu)** — dono do projeto, orquestra os agentes, roda o pipeline local, aprova classe D.
- **Comitê de Alocação** — consome só o material sintetizado.
- **Anti-persona:** cliente final, trader intradiário, compliance, e quem quer "o número previsto".

## 4. Escopo da v1 (PRD §4)

Blocos **A** (macro), **B** (ativos/subsetores) e **C** (internacional) do e-mail, janela **1T2006 → 3T2026**
(≈ 83 trimestres), análise trimestral com armazenamento na granularidade nativa. Regimes por **V1**
(quadrantes crescimento × inflação, lente principal), **V3** (vizinhos mais próximos — responde literalmente
ao e-mail) e **V2** (ciclo Selic, corte secundário). = "pacote mínimo" da §7 da metodologia.

**O escopo implícito virou explícito:** "tamanho da alocação internacional" (item **C1**) é entregue como
internacional em BRL dentro do mesmo arcabouço de regimes, respondido por **faixa estrutural + banda tática
por regime** — não por número pontual.

**Fora de escopo:** backtest de estratégia, previsão, interface web/API/deploy, dados pagos (ANBIMA Feed,
Bloomberg), IFIX sintético pré-2011, FII segmentado pré-2016.

**Fase 2:** V1b vs. Focus, V2 completa, setoriais completos, EMBI/CDS, variância mínima por regime,
dupla materialização `asof`×`revised`, clustering, HMM mensal, dashboard.

## 5. O que o PRD exige (resumo, sem duplicar)

**52 requisitos funcionais** em 6 grupos — extração por fonte (RF-001..019), camada canônica (020..026),
regimes (027..031), análise e visualização (032..040), entrega ao Comitê (041..045), reprodutibilidade
(046..052). Cada RF cita o item do e-mail (A1–A7, B1–B5, C1) e a fonte primária + fallback.
**10 RNFs:** reprodutibilidade por um comando, rastreabilidade (origem + vintage), sem dado inventado,
local em Windows/Python 3.11+, sem rede no CI, sem credencial/fonte paga no caminho crítico.

**Fontes escolhidas (as decisivas):** IMA via **bucket S3 público da ANBIMA**; índices B3 via **API
`indexStatisticsProxy`**; curva/inclinação via **Tesouro Direto interpolado** (porque o SGS de swaps morreu e
a ETTJ ANBIMA só tem ~20 d.u.); macro via **SGS + SIDRA**; Focus via **Olinda OData**; internacional via
**Yahoo `^GSPC` + MSCI `892400` NETR + PTAX**; FII segmentado via **Teva** (2019+, best-effort).

## 6. Restrições conhecidas (base da Anti-SPEC)

- **Não inventar dado.** Lacuna sem substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`.
- **Não é SaaS/web.** Sem auth, pagamento, deploy ou frontend. Roda local.
- **`data/` não é versionado** e não é fonte de verdade — o script que produz o dado é.
- **Camada canônica é classe C**; publicar para o Comitê é **classe D**.
- Excesso sobre CDI e retorno real **sempre por razão** `(1+r)/(1+b)−1`; trimestre = último dia útil.
- Fontes revisam números retroativamente (PIB do IBGE) → pipeline idempotente, com `vintage`.
- Séries que não cobrem 20 anos têm a janela real **declarada**: ICON (2007+), IMOB (2008+), IFIX (2011+),
  FII segmentado (2019+), ponta longa nominal da curva (~2010+).

## 7. Riscos dominantes (PRD §12 — 8 priorizados)

Look-ahead bias (revisão e defasagem do PIB/IBC-Br) · n pequeno (~20 por regime; diferenças < 5 pp são
ruído) · quebra estrutural 2006-2008 vs pós-2016 · **falha silenciosa de extração** (erro com HTTP 200,
truncamento sem aviso, filtros ignorados) · janela rolante e descontinuações · endpoints não documentados e
anti-bot (FRED pode estar bloqueado) · unidade/escala/formato mentirosos · overfitting e confusão
descritivo × preditivo.

## 8. Estado atual

- **Fase:** PRD v1.0 escrito, **aguardando aprovação do Edu** e resposta das decisões bloqueantes.
- **Pipeline implementado:** nenhum — `apps/pipeline/` e `apps/analysis/` vazios.
- **Dataset canônico:** não existe.
- **Pesquisa:** concluída — fontes (`fontes-de-dados.md`) e metodologia (`metodologia-regimes-macro.md`).
- **CI:** N1 configurado; N2/N3 comentados aguardando testes reais.
- **Bloqueios:** **8 decisões** travam implementação — ver `TODO.md §4` e PRD §13.2
  (**D1** lente oficial, **D3** eixo inflação, **D5** métrica do heatmap, **D6** forma do internacional,
  **D12** setoriais/FII no pacote mínimo, **L1** IFIX 2011+, **L2** FII segmentado via terceiro, **L4**
  contratar ANBIMA Feed ou não).
- **Próximo passo:** responder as 8 decisões → aprovar o PRD → `/SDD-avancado`.

## 9. Próximo grande objetivo

Dataset canônico trimestral de 20 anos com blocos A/B/C conferidos contra as fontes originais, + heatmap
regime × ativo, **antes do Comitê de Alocação de 2026-10-14** (heatmap para revisão do Edu em 2026-10-13).

---

## Links

- Escopo de origem (imutável) → [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
- **PRD v1.0** → [`docs/product/PRD.md`](../product/PRD.md)
- Pesquisas → [`docs/research/fontes-de-dados.md`](../research/fontes-de-dados.md) ·
  [`docs/research/metodologia-regimes-macro.md`](../research/metodologia-regimes-macro.md)
- SPEC + Anti-SPEC (a criar) → [`docs/specs/SPEC.md`](../specs/SPEC.md)
- Arquitetura → [`wiki/architecture.md`](./architecture.md) · Histórico → [`wiki/log.md`](./log.md)
- Estado vivo → [`TODO.md`](../../TODO.md) · Contrato com agentes → [`AGENTS.md`](../../AGENTS.md)

---

*Atualize esta página quando: o PRD mudar de versão, uma decisão bloqueante for respondida, a fase mudar, ou
o dataset canônico passar a existir. Não atualize por feature pequena.*
