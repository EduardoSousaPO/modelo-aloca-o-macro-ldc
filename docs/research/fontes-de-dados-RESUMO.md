# Fontes de dados — resumo executivo (leitura de 5 min)

**Para:** Edu e Alexandre · **Data:** 2026-10-10 · **Janela-alvo:** 2006 → 2026, agregável em trimestres.
**Anexo técnico:** [`fontes-de-dados.md`](./fontes-de-dados.md) — endpoints exatos, formatos, parsing e
pegadinhas. As referências `§A1`…`§C11` abaixo são as seções desse anexo.

Confiança: **[CONFIRMADO]** = endpoint acessado e conteúdo lido nesta pesquisa · **[CONFIRMADO-SUB]** =
acesso real, por agente auxiliar · **[NÃO VERIFICADO]** = conhecimento de fundo, validar antes de codar.

**Veredito em uma frase:** dá para montar a base de 20 anos **sem custo e sem cadastro** para quase tudo —
as três exceções são **ETTJ histórica da ANBIMA** (só paga), **FII por segmento** (só desde 2019) e
**CDS/risco-país** (sem fonte gratuita contínua).

---

## 1. Tabela-resumo: item do e-mail → fonte

| # | Item | Fonte primária | Identificador | Início | 2006? | Esforço | Fallback | § |
|---|---|---|---|---|---|---|---|---|
| A1 | PIB — IBC-Br | BCB SGS | **24364** (dessaz.) | 2003 | Sim | baixo | Ipeadata | A1 |
| A1b | PIB trimestral IBGE | IBGE SIDRA | **t/1621 v/584 c11255/90707** | 1996T1 | Sim | baixo | SGS **22109** (idêntico) | A3 |
| A1c | PIB var. T/T-1 dessaz. | IBGE SIDRA | t/5932 v/**6564** | 1996T1 | Sim | baixo | calcular de 1621 | A3 |
| A2 | IPCA mensal | BCB SGS | **433** | 01/1980 | Sim | baixo | SIDRA t/1737 v/63 | A1 |
| A2b | IPCA 12 meses | BCB SGS | **13522** | 12/1980 | Sim | baixo | SIDRA t/1737 v/2265 | A1 |
| A2c | IPCA nº-índice e núcleos | SIDRA / SGS | t/1737 v/2266 · SGS 4466, 11426-11428 | 1979/2000 | Sim | baixo | — | A1, A3 |
| A3 | Expectativas Focus | BCB Olinda OData | `ExpectativasMercadoAnuais`, `...Mensais`, `...Trimestrais`, `...Selic` | 1999-2004 | Sim | médio | `python-bcb` | A2 |
| A4 | Selic Over | BCB SGS | **11** (%/dia) · **1178** (% a.a.) | ≤2005 | Sim | baixo | Ipeadata `BM366_TJOVER366` | A1 |
| A4b | Selic meta / mensal | BCB SGS | **432** · **4189** · 4390 | 1986/1999 | Sim | baixo | — | A1 |
| A5 | Taxas de títulos públicos | **Tesouro Transparente** | `precotaxatesourodireto.csv` | **31/12/2004** | Sim | baixo | ANBIMA `ms*.txt` (só ~20 d.u.) | A4.1 |
| A6 | Inclinação da curva | **Tesouro Direto interpolado** | idem A5 | 31/12/2004 | Sim (real) / parcial (nominal) | médio | `pyield` (DI futuro) | A5 |
| A6b | ETTJ Svensson (betas) | ANBIMA `CZ-down.asp` | POST `saida=csv` | **14/09/2026** | **NÃO** | baixo | ANBIMA Feed (pago) | A5 |
| A7 | IPCA histórico completo | IBGE SIDRA | **t/1737** | 12/1979 | Sim | baixo | SGS 433/13522 | A3 |
| B1 | IMA-B / 5 / 5+ | **ANBIMA S3 (grátis)** | `IMAB`, `IMAB5`, `IMAB5MAIS` | **16/09/2003** | Sim | **baixo** | SGS 12466/12467/12468 (→2023) | B6 |
| B2 | IRF-M / 1 / 1+ | **ANBIMA S3** | `IRFM`, `IRFM1`, `IRFM1MAIS` | **01/02/2000** | Sim | **baixo** | SGS 12461 (só IRF-M, →2023) | B6 |
| B2b | IMA-Geral / IMA-S | **ANBIMA S3** | `IMAGERAL`, `IMAS` | 12/2001 | Sim | **baixo** | SGS 12469 / 12462 | B6 |
| B3 | CDI acumulado | BCB SGS | **12** (%/dia) · 4389 | ≤2005 | Sim | baixo | Ipeadata `BM12_TJOVER12` | B7 |
| B4 | IBOV | **API B3** `indexStatisticsProxy` | `IBOV` | 02/01/1968 | Sim | médio | Yahoo `^BVSP` (1993) | B8 |
| B4b | SMLL, IDIV, IFNC, IMAT, INDX, IEEX, UTIL | **API B3** | mesmos códigos (energia = **`IEEX`**) | 2004-2005 | **Sim** | médio | ETFs (2008-2012) | B8 |
| B4c | **ICON** | API B3 | `ICON` | base 28/12/2006 | **NÃO** (de 2007) | médio | — | B8 |
| B4d | **IMOB** | API B3 | `IMOB` | base 28/12/2007 | **NÃO** (de 2008) | médio | — | B8 |
| B5 | **IFIX** | API B3 | `IFIX` | base 30/12/2010 | **NÃO** (de 2011) | médio | XFIX11 (2020) | B9 |
| B5b | FII Tijolo/Papel/Logística/Shoppings/Lajes | **Teva (GCS público)** | `3.2.2`, `3.2.1`, `3.3.1`, `3.3.3`, `3.3.2` | **02/01/2019** | **NÃO** | baixo | COTAHIST + CVM (alto) | B9 |
| B5c | IFIX-L | API B3 | **`IFIL`** | 28/12/2017 | **NÃO** | médio | — | B9 |
| C1 | S&P 500 | **Yahoo `^GSPC`** | `^GSPC` | 1927 | Sim | baixo | MSCI USA `984000` · `IVV` | C10 |
| C2 | MSCI ACWI / World | **MSCI endpoint público** | `892400` / `990100`, `NETR` | **29/12/2000** | Sim | baixo | ETFs ACWI (2008) / URTH (2012) | C10 |
| C3 | Treasury 10y/2y/spread | FRED CSV | `DGS10`, `DGS2`, `T10Y2Y` | 1962-1976 | Sim | baixo | Yahoo `^TNX`, `^FVX` | C10 |
| C4 | DXY | FRED | **`DTWEXBGS`** | **02/01/2006** | Sim (no limite) | baixo | Yahoo `DX-Y.NYB` (1971) | C10 |
| C5 | VIX | FRED `VIXCLS` | `VIXCLS` | 02/01/1990 | Sim | baixo | Yahoo `^VIX` | C10 |
| C6 | Câmbio BRL/USD | **BCB SGS 1 / 10813** (PTAX) | 1 · 10813 | ≤2005 | Sim | baixo | FRED `DEXBZUS` (1995) | A1 |
| C7 | Fed Funds | FRED | `DFF` / `FEDFUNDS` | 1954 | Sim | baixo | — | C10 |
| C8 | **CDS Brasil 5y / EMBI+** | Ipeadata `JPM366_EMBI366` | `JPM366_EMBI366` | 29/04/1994 | **Parcial** (morre 30/07/2024) | **alto** | splice + cupom cambial B3 | C10 |
| C9 | Agregador | Ipeadata OData4 | ver anexo | varia | varia | baixo | — | C11 |

---

## 2. As 13 lacunas e o que muda na comparabilidade

| # | Lacuna | Substituição recomendada | Impacto na comparabilidade |
|---|---|---|---|
| L1 | **IFIX só desde 2011** (perde metade da janela) | Rodar FII em 2011-2026; usar IMOB (2008+) como proxy imperfeito antes | FII **não entra** no painel balanceado de 20 anos; cobre ~2,5 ciclos |
| L2 | **FII por segmento só desde 2019** | Teva 2019-2026 para dispersão setorial; IFIX para o agregado | Segmentação cobre **~2 ciclos** — insuficiente para inferência estatística; tratar como **qualitativo** |
| L3 | **ICON de 2007, IMOB de 2008** | Janela própria por setor, sem forçar painel balanceado | Esses 2 setores entram com 1-2 anos menos; nota de rodapé no output |
| L4 | **ETTJ ANBIMA histórica não é gratuita** | Inclinação construída do Tesouro Direto (2004→) | Atende ao objetivo; **não** é a curva Svensson oficial da ANBIMA |
| L5 | **Ponta longa nominal inexiste antes de ~2010** (em 2006 a LTN mais longa vencia em 2009) | Usar **inclinação real** (NTN-B curta × NTN-B 2045) como variável principal; 5 anos (não 10) na nominal | Variável de regime passa a ser **real**, não nominal — mudança conceitual, declarar |
| L6 | **ANBIMA `ms*.txt` e Curva Zero: janela rolante de ~20 d.u.** | Ligar **hoje** job diário de arquivamento | Zero impacto no backfill; em 12 meses a casa tem série proprietária |
| L7 | **SGS de swap DI×pré morto desde set/2019** (era a rota do e-mail, série 7806) | Tesouro Direto + DI futuro via `pyield` | Nenhum, se L5 for aceito |
| L8 | **CDS/EMBI+ sem fonte gratuita contínua** (EMBI+ morre 30/07/2024) | (1) cupom cambial DDI/FRC da B3 menos UST; (2) splice EMBI+ × ICE BofA LatAm | Série **emendada** → quebra metodológica em 2024; usar com cautela em regressão |
| L9 | **Desemprego sem série única** (PNADC de 2012; PME até 02/2016) | Emendar PME (SIDRA t/2176) + PNADC (t/4099), calibrando no overlap 2012-2016 | Série emendada; nível não é estritamente comparável antes/depois |
| L10 | **Dívida bruta (SGS 13762) começa em 2008** | Usar **DLSP (SGS 4513)**, que cobre 2006 | Troca de conceito fiscal (líquida vs bruta) — declarar |
| L11 | **S&P 500 no FRED só tem 10 anos** | Yahoo `^GSPC` ou MSCI USA `984000` | **Nenhum** — resolvido, não é lacuna real |
| L12 | **"ANBIMA DataFit" não existe** | O que existe é ANBIMA Data (grátis) + ANBIMA Feed (pago) | Nenhum — o S3 resolve os índices |
| L13 | **IPCA por grupos sem série única** (t/1419 2012-2019; t/7060 2020+) | Fora do escopo mínimo; tabela de 2006-2011 **a confirmar** | Nenhum no escopo atual |

---

## 3. As 5 decisões de fonte que precisam de aval humano

1. **Inclinação da curva: real (NTN-B) em vez de nominal/DI.** O e-mail pedia "diferença entre DI de curto e
   longo prazo". A rota do SGS (swaps) **morreu em set/2019** [CONFIRMADO] e a ETTJ ANBIMA histórica é paga.
   Proposta: inclinação **real** via Tesouro Direto, completa desde 2006. → *Aceitar a troca de nominal
   para real como variável de regime principal?* (§A5)
2. **Contratar o ANBIMA Feed?** É a única forma de ter a ETTJ Svensson oficial com histórico
   (~R$ 686/mês usuário final a ~R$ 8.238/mês parceiro) [NÃO VERIFICADO — leitura de página].
   → *Vale o custo, ou a inclinação via Tesouro Direto é suficiente para o Comitê?* (§A5, §B6)
3. **FII por segmento só desde 2019 (Teva).** A B3 **não tem** índice setorial de FII [CONFIRMADO-SUB].
   A Teva é gratuita e programática, mas é **provedor privado sem licença explícita de uso comercial**.
   → *Usar a Teva na análise, e aceitar janela de 2019-2026 para Tijolo/Papel/Logística/Shoppings?* (§B9)
4. **Risco-país sem fonte gratuita contínua.** EMBI+ encerra em 30/07/2024 [CONFIRMADO].
   → *Aceitar série emendada (EMBI+ até 2024 + proxy depois), ou tirar risco-país do modelo?* (§C10.5)
5. **Setores sem 2006 (ICON, IMOB) e FII sem 2006-2010 (IFIX).**
   → *Rodar painel desbalanceado com janelas por ativo, ou restringir toda a análise à janela comum
   (2011-2026) para manter comparabilidade estrita?* (§B8, §B9) — **esta é a decisão de maior impacto
   metodológico.**

---

## 4. Os 5 riscos de extração mais graves

| # | Risco | Por que é grave | Mitigação |
|---|---|---|---|
| R1 | **Erro com HTTP 200** — o SGS devolve o erro de "janela de 10 anos" e séries inexistentes como **HTML, com status 200** [CONFIRMADO] | O extrator "funciona" e grava lixo silenciosamente | Validar que o corpo é JSON *array*; checar chaves `error`/`erro` |
| R2 | **Truncamento silencioso** — `$top=20000` no Olinda devolve 20.000 linhas **sem `nextLink`**; `range=max` no Yahoo trunca mensais; `fredgraph.csv` sem `cosd` trunca [CONFIRMADO] | Série incompleta sem nenhum sinal de erro | Omitir `$top`/paginar com `$skip`; usar `period1/period2`; sempre `cosd=1900-01-01`; **assert de contagem mínima** |
| R3 | **Janela rolante que apaga o passado** — ANBIMA `ms*.txt` e Curva Zero (~20 d.u.), ICE BofA no FRED (3 anos), `SP500`/`DJIA` (10 anos) [CONFIRMADO] | Cada dia sem arquivar é dado perdido para sempre | **Ligar o job diário hoje**; nunca tratar como fonte de backfill |
| R4 | **Endpoints internos não documentados** — API B3 `indexStatisticsProxy`, MSCI `app2.msci.com`, ANBIMA S3 [CONFIRMADO] | São o caminho crítico de 3 blocos e podem mudar sem aviso | **Testes de contrato no CI** com valor-canário (IBOV 01/02/2006 = 38.484,84; IMA-B 16/09/2003 = 723,070317; MSCI ACWI NETR 31/01/2006 = 121,3858) |
| R5 | **FRED inacessível desta máquina** — `curl` → `http=000`; `urllib` com UA de browser → **10/10 IDs falharam** (8 timeout, 2 `ConnectionResetError(10054)`) [CONFIRMADO]; outro caminho de rede funcionou | Bloco internacional pode simplesmente não rodar em produção | **Testar conectividade antes de depender do FRED.** Plano B pronto: Yahoo (`^TNX`, `^VIX`, `DX-Y.NYB`) + MSCI + BCB PTAX |

Riscos adicionais (anti-bot, encoding latin-1 vs UTF-8, formatos mentirosos, quebra de taxonomia da CVM em
2025, descontinuações): **22 riscos catalogados** na seção "Riscos de extração" do anexo.

---

## 5. Amostras já baixadas e verificadas (`data/raw/`)

Fora do git (`data/raw/*` está no `.gitignore`). Detalhe por arquivo na seção "Amostras baixadas em
2026-10-10" do anexo.

| Pasta | Arquivos | O que contém |
|---|---|---|
| `data/raw/anbima-ima/` | `IMAB`, `IMAB5`, `IMAB5MAIS`, `IRFM`, `IRFM1`, `IRFM1MAIS`, `IMAGERAL`, `IMAGERALEXC`, `IMAS`, `IMAC`, `IHFA` (`.xls`, ~3,9 MB) | **Número-índice diário dos 10 índices ANBIMA**, de 2000-02-01/2003-09-16 até 2026-10-09. ⚠️ são XLSX apesar da extensão [CONFIRMADO] |
| `data/raw/tesouro-direto/` | `td.csv` (14,6 MB) | 177.260 linhas, **31/12/2004 → 09/10/2026**, 8 tipos de título, taxas e PUs diários [CONFIRMADO] |
| `data/raw/anbima-ettj/` | `cz.xls` (14,6 KB) | Parâmetros Svensson (PREFIXADOS e IPCA) + vértices 252→6.930 d.u. ⚠️ é **HTML `<table>`**, não Excel [CONFIRMADO] |
| `data/raw/anbima-ms/` | `ms.txt` (6,7 KB) | Taxas indicativas do secundário em 08/10/2026 — LTN, LFT, NTN-B, NTN-C, NTN-F [CONFIRMADO] |

**Próximo passo sugerido:** atacar primeiro os extratores de esforço **baixo** (ANBIMA S3, SGS, SIDRA,
Tesouro Direto, API B3, Yahoo/MSCI) — eles já entregam a base para o Comitê — e, no mesmo dia, ligar o
job diário de arquivamento da ANBIMA (L6/R3).
