# Escopo de origem — e-mail de Alexandre Kaercher (recebido out/2026)

> **Fonte de verdade do escopo.** Este arquivo é a transcrição integral do e-mail que originou o projeto.
> Toda feature, PRD, SPEC ou decisão deve ser checada contra este documento. Não editar a seção
> "Transcrição integral"; mudanças de escopo vão em `docs/plans/DECISIONS_LOG.md` ou ADR.
>
> Transcrito a partir de print de tela em 2026-10-10 por Claude (Fable 5.1), a pedido de Eduardo (Edu).
> Prazo mencionado: "próxima quarta-feira" = **2026-10-14** (reunião do Comitê de Alocação).

---

## Transcrição integral

Fala Edu, tudo certo?

Em linha com o que conversamos esta semana, estamos desenvolvendo um modelo de alocação macro doméstica e tamanho da alocação internacional. O objetivo é fundamentar nossas decisões com bases estatísticas, verificando como cada classe de ativo e até setores performaram em momentos semelhantes.

O período analisado seria dos últimos 20 anos, idealmente com dados trimestrais, para observar o comportamento de cada ativo nesses intervalos. As principais variáveis e dados mapeados seriam **(fique a vontade para ajustes caso não localize estes dados ou alguma idéia)**:

A. Dados dos Indicadores Macroeconômicos

- SGS (Sistema Gerenciador de Séries Temporais do Banco Central):
  - PIB: Série do IBC-Br (Prévia do PIB do BCB) ou **PIB mensal/trimestral do IBGE.**
  - Inflação: **IPCA mensal (Série 433) e Expectativas do Relatório Focus.**
  - Juros: **Histórico da taxa Selic Over (Série 11) e taxas dos títulos públicos (Tesouro Direto / ANBIMA).**
- ANBIMA (DataFit / ANBIMA Feed): Dados históricos da estrutura a termo da curva de juros (ETTJ) — fundamentais para extrair a inclinação da curva (diferença entre DI de curto e longo prazo).
- IBGE (SIDRA): Histórico completo do IPCA.

B. Dados de Desempenho dos Ativos e Subsetores

- Renda Fixa (Índices ANBIMA):
  - **IMA-B / IMA-B 5 / IMA-B 5+: Desempenho do IPCA+.**
  - **IRF-M / IRF-M 1 / IRF-M 1+: Desempenho dos Pré-fixados.**
  - **CDI: Taxa diária acumulada.**
- **Ações (Setoriais B3 & Índices Amplos):**
  - **Indices setoriais oficiais: INDX (Industrial), ICON (Consumo), IMAT (Materiais Básicos/Commodities), IEEX/IEE (Energia Elétrica), IMOB (Imobiliário/Construção), IFNC (Financeiro), SMLL (Small Caps), além de IDIV e IBOV.**
- **Fundos Imobiliários:**
  - **IFIX (Geral) e segmentações específicas (Tijolo vs. Papel, Logística, Shoppings).**

***Gostaria de pedir teu auxílio para estruturar a busca e extração dessas informações via IA.*** Temos uma reunião do Comitê de Alocação agendada para a próxima quarta-feira, então caso consiga me ajudar com o levantamento desses dados, o quanto antes, conseguirei modelar a estratégia a tempo para o encontro.

Desde já, caso queira marcar um call para falarmos me fala, desde já agradeço a ajuda e fico à disposição

Abraço,
Alexandre Kaercher

---

## Checklist de escopo derivado (para verificação contínua)

Objetivo: **modelo de alocação macro doméstica + tamanho da alocação internacional**, com base estatística
em "como cada classe de ativo e setores performaram em momentos semelhantes" (regimes macro).

Parâmetros: janela de **20 anos** (≈ 2006 → 2026), frequência **trimestral** (ideal), dados brutos podem ser diários/mensais e agregados.

| # | Bloco | Item | Fonte sugerida no e-mail | Status |
|---|---|---|---|---|
| A1 | Macro | PIB: IBC-Br (BCB) ou PIB mensal/trimestral IBGE | SGS / IBGE | pendente |
| A2 | Macro | IPCA mensal (SGS 433) | SGS | pendente |
| A3 | Macro | Expectativas Focus (IPCA, Selic, PIB, câmbio) | BCB Focus / Olinda | pendente |
| A4 | Macro | Selic Over (SGS 11) | SGS | pendente |
| A5 | Macro | Taxas títulos públicos (Tesouro Direto / ANBIMA) | Tesouro / ANBIMA | pendente |
| A6 | Macro | ETTJ histórica → inclinação da curva (DI curto vs longo) | ANBIMA (DataFit / Feed) | pendente |
| A7 | Macro | IPCA histórico completo (SIDRA) | IBGE SIDRA | pendente |
| B1 | RF | IMA-B, IMA-B 5, IMA-B 5+ | ANBIMA | pendente |
| B2 | RF | IRF-M, IRF-M 1, IRF-M 1+ | ANBIMA | pendente |
| B3 | RF | CDI acumulado | B3 / SGS 12 | pendente |
| B4 | Ações | INDX, ICON, IMAT, IEE, IMOB, IFNC, SMLL, IDIV, IBOV | B3 | pendente |
| B5 | FII | IFIX + segmentações (Tijolo vs Papel, Logística, Shoppings) | B3 / fontes alternativas | pendente |
| C1 | Internacional | Proxies para "tamanho da alocação internacional" (câmbio, S&P 500, etc.) — **não listado explicitamente, mas implícito no objetivo** | a definir | pendente |

Entregável pedido: **estrutura de busca e extração dos dados via IA** + base pronta para Alexandre modelar
a estratégia antes do Comitê de Alocação (2026-10-14). Alexandre autorizou ajustes/substituições quando um
dado não for localizável.
