"""Catálogo de séries **como dado** — uma entrada por série, validada por `series_catalog.py`.

Toda linha vem de `docs/research/fontes-de-dados.md` (+ `-RESUMO.md`), com a **tag de confiança
copiada de lá**:

- `CONFIRMADO`     = endpoint acessado e conteúdo lido na pesquisa
- `CONFIRMADO_SUB` = acesso real, por agente auxiliar
- `NAO_VERIFICADO` = conhecimento de fundo **ou série derivada por nós** — validar antes de usar

**Nenhum identificador é inventado.** Onde a pesquisa diz "a confirmar", a entrada traz
`identificador = "a_confirmar"` + `status = "a_confirmar"` e **não** pode estar no caminho crítico
do pacote mínimo de 2026-10-14 (SPEC CA-053/054).

`status`: `ok` (usável) · `a_confirmar` · `descontinuada` (morreu numa data) · `descartada`
(existe mas não serve — janela curta, não cobre 2006, fora do escopo mínimo) · `paga`.
"""

from __future__ import annotations

from typing import Any

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados?formato=json"
URL_OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/{es}"
URL_SIDRA = "https://apisidra.ibge.gov.br/values/t/{t}/n1/all/v/{v}/p/200601-202609"
URL_SIDRA_C = (
    "https://apisidra.ibge.gov.br/values/t/{t}/n1/all/v/{v}/p/200601-202602/c11255/{c}"
)
URL_TESOURO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)
URL_ANBIMA_S3 = (
    "https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/"
    "arquivos/indices-historico/{slug}-HISTORICO.xls"
)
URL_B3 = (
    "https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/"
    "IndexCall/GetPortfolioDay/{payload_b64}"
)
URL_TEVA = (
    "https://storage.googleapis.com/storage/v1/b/teva-indices-public/o"
    "?prefix=quotations-download-file/"
)
URL_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
URL_MSCI = (
    "https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph"
    "?index_codes={cod}&index_variant={variant}&data_frequency=DAILY"
)
URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}&cosd=1900-01-01"
URL_IPEA = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{cod}')"


def _sgs(cod: int, nome: str, item: str, freq: str, unit: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"BCB_SGS_{cod}",
        "nome": nome,
        "item_email": item,
        "fonte": "BCB_SGS",
        "identificador": str(cod),
        "fonte_url": URL_SGS.format(cod=cod),
        "freq": freq,
        "unit": unit,
        "confianca": "CONFIRMADO",
    }
    base.update(kw)
    return base


def _s3(slug: str, nome: str, item: str, inicio: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"ANBIMA_{slug}",
        "nome": nome,
        "item_email": item,
        "fonte": "ANBIMA_S3",
        "identificador": slug,
        "fonte_url": URL_ANBIMA_S3.format(slug=slug),
        "freq": "D",
        "unit": "index",
        "data_inicio": inicio,
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
        "is_total_return": True,
        "obs": "XLSX apesar da extensao .xls (magic bytes PK); rotulo da coluna Indice e instavel.",
    }
    base.update(kw)
    return base


def _b3(cod: str, nome: str, item: str, base_date: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"B3_{cod}",
        "nome": nome,
        "item_email": item,
        "fonte": "B3_API",
        "identificador": cod,
        "fonte_url": URL_B3.format(payload_b64="base64({language,index,year})"),
        "freq": "D",
        "unit": "index",
        "data_inicio": base_date,
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
        "fonte_instavel": True,
        "obs": "API interna nao documentada; matriz dia x mes (unpivot); valores em pt-BR.",
    }
    base.update(kw)
    return base


def _teva(cod: str, sid: str, nome: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"TEVA_{sid}",
        "nome": nome,
        "item_email": "B5",
        "fonte": "TEVA_GCS",
        "identificador": cod,
        "fonte_url": URL_TEVA,
        "freq": "D",
        "unit": "index",
        "data_inicio": "2019-01-02",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "is_total_return": True,
        "licenca_restrita": True,
        "obs": "Nome do arquivo tem versao embutida (v0.27): listar bucket e casar por regex. "
        "Provedor privado sem licenca comercial explicita; cobre ~2 ciclos macro (L2).",
    }
    base.update(kw)
    return base


def _yahoo(sid: str, ticker: str, nome: str, item: str, inicio: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"YAHOO_{sid}",
        "nome": nome,
        "item_email": item,
        "fonte": "YAHOO",
        "identificador": ticker,
        "fonte_url": URL_YAHOO.format(ticker=ticker),
        "freq": "D",
        "unit": "index",
        "data_inicio": inicio,
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "fonte_instavel": True,
        "obs": "API nao oficial: sem User-Agent de browser devolve 429; range=max trunca series "
        "mensais (usar period1/period2 em epoch).",
    }
    base.update(kw)
    return base


def _fred(fid: str, nome: str, item: str, freq: str, unit: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"FRED_{fid}",
        "nome": nome,
        "item_email": item,
        "fonte": "FRED",
        "identificador": fid,
        "fonte_url": URL_FRED.format(fid=fid),
        "freq": freq,
        "unit": unit,
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "fonte_instavel": True,
        "obs": "fredgraph.csv sem cosd trunca a serie; fred.stlouisfed.org ficou INACESSIVEL na "
        "maquina da pesquisa (R5/G-06): testar conectividade antes de depender.",
    }
    base.update(kw)
    return base


def _ipea(cod: str, nome: str, item: str, freq: str, unit: str, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "series_id": f"IPEA_{cod}",
        "nome": nome,
        "item_email": item,
        "fonte": "IPEADATA",
        "identificador": cod,
        "fonte_url": URL_IPEA.format(cod=cod),
        "freq": freq,
        "unit": unit,
        "confianca": "CONFIRMADO",
        "obs": "ValoresSerie ignora $filter/$top/$orderby: baixar inteiro e filtrar em pandas; "
        "fins de semana vem como null.",
    }
    base.update(kw)
    return base


# ============================================================================================
# BLOCO A — MACRO (itens A1..A7 do e-mail)
# ============================================================================================

_BCB_SGS: list[dict[str, Any]] = [
    # --- inflação ---------------------------------------------------------------------------
    _sgs(
        433,
        "IPCA — variacao mensal",
        "A2",
        "M",
        "%",
        data_inicio="1980-01-01",
        transformacao_padrao="acumulacao_geometrica_no_trimestre",
        lag_divulgacao_dias=10,
        obs="Identico a SIDRA 1737 v63 (ago/26 -0.32; set/26 0.82). Serie completa sem parametros.",
    ),
    _sgs(
        13522,
        "IPCA — acumulado em 12 meses",
        "A2",
        "M",
        "%",
        data_inicio="1980-12-01",
        transformacao_padrao="ultimo_dia_util_do_trimestre",
        lag_divulgacao_dias=10,
        obs="Identico a SIDRA 1737 v2265 (ago/26 4.22; set/26 4.58).",
    ),
    _sgs(
        4466,
        "IPCA — nucleo medias aparadas com suavizacao",
        "A2",
        "M",
        "%",
        lag_divulgacao_dias=10,
        obs="Existencia e cobertura de 2006 confirmadas; nome oficial via CKAN do BCB.",
    ),
    _sgs(
        11427,
        "IPCA — nucleo por exclusao (sem monitorados e alimentos no domicilio)",
        "A2",
        "M",
        "%",
        lag_divulgacao_dias=10,
        obs="Existencia e cobertura de 2006 confirmadas.",
    ),
    _sgs(
        189,
        "IGP-M — variacao mensal",
        "-",
        "M",
        "%",
        obs="jan/06 = 0.92. Rotulo exato [NAO VERIFICADO]; fora do escopo minimo.",
    ),
    _sgs(
        190,
        "IGP-DI — variacao mensal",
        "-",
        "M",
        "%",
        obs="jan/06 = 0.72. Rotulo exato [NAO VERIFICADO]; fora do escopo minimo.",
    ),
    # --- juros ------------------------------------------------------------------------------
    _sgs(
        11,
        "Selic over — taxa diaria",
        "A4",
        "D",
        "%/dia",
        transformacao_padrao="acumulacao_geometrica_no_trimestre",
        obs="Primeiro ponto medido 03/01/2005 = 0.064826; inicio real anterior, nao medido. "
        "Serie diaria: fatiar em blocos <= 10 anos (o SGS devolve erro com HTTP 200).",
    ),
    _sgs(
        1178,
        "Selic over anualizada base 252",
        "A4",
        "D",
        "%a.a.",
        transformacao_padrao="ultimo_dia_util_do_trimestre",
        obs="09/10/2026 = 13.65. Use esta para Selic over em % a.a.",
    ),
    _sgs(
        432,
        "Meta Selic definida pelo Copom",
        "A4",
        "D",
        "%a.a.",
        transformacao_padrao="ultimo_dia_util_do_trimestre",
        obs="2006 = 18.00. ATENCAO: ultimo ponto vem com DATA FUTURA (meta vigente): truncar.",
    ),
    _sgs(
        4390,
        "Selic acumulada no mes",
        "A4",
        "M",
        "%",
        data_inicio="1986-08-01",
        transformacao_padrao="acumulacao_geometrica_no_trimestre",
    ),
    _sgs(
        4189,
        "Selic acumulada no mes anualizada base 252",
        "A4",
        "M",
        "%a.a.",
        data_inicio="1986-08-01",
        obs="E a 'Selic mensal' citada no e-mail.",
    ),
    _sgs(
        12,
        "CDI — taxa diaria",
        "B3",
        "D",
        "%/dia",
        transformacao_padrao="acumulacao_geometrica_no_trimestre",
        obs="Primeiro ponto medido 03/01/2005 = 0.064893. VALOR E PERCENTUAL, NAO FATOR: "
        "prod(1+v/100) em 2006 (249 d.u.) = 15,0271% — valor-canario do pipeline.",
    ),
    _sgs(
        4389,
        "CDI anualizado base 252",
        "B3",
        "D",
        "%a.a.",
        transformacao_padrao="ultimo_dia_util_do_trimestre",
        obs="08/10/2026 = 13.65. Converter para fator diario introduz erro de arredondamento: "
        "prefira a serie 12.",
    ),
    # --- atividade --------------------------------------------------------------------------
    _sgs(
        24364,
        "IBC-Br — com ajuste sazonal",
        "A1",
        "M",
        "index",
        data_inicio="2003-01-01",
        transformacao_padrao="desvio_da_media_movel_20_trimestres",
        lag_divulgacao_dias=45,
        obs="jan/06 = 79.44731 (valor-canario). E a serie usada no eixo de crescimento da V1.",
    ),
    _sgs(
        24363,
        "IBC-Br — sem ajuste sazonal",
        "A1",
        "M",
        "index",
        data_inicio="2003-01-01",
        lag_divulgacao_dias=45,
        obs="jan/06 = 75.88784. Fallback de 24364.",
    ),
    _sgs(
        22109,
        "PIB trimestral — indice de volume com ajuste sazonal",
        "A1",
        "Q",
        "index",
        data_inicio="1996-01-01",
        transformacao_padrao="variacao_12_meses",
        lag_divulgacao_dias=60,
        obs="2006T1 = 131.74; identico a SIDRA 1621/v584/c11255=90707 valor a valor. "
        "Atalho de uma chamada para o PIB agregado.",
    ),
    _sgs(
        22099,
        "PIB trimestral — indice de volume sem ajuste sazonal",
        "A1",
        "Q",
        "index",
        data_inicio="1996-01-01",
        lag_divulgacao_dias=60,
        obs="2006T1 = 128.18 = SIDRA 1620/v583/90707.",
    ),
    _sgs(
        22108,
        "Valor adicionado a precos basicos — indice com ajuste sazonal",
        "A1",
        "Q",
        "index",
        data_inicio="1996-01-01",
        lag_divulgacao_dias=60,
        obs="2006T1 = 131.59 = SIDRA 1621/v584/90705.",
    ),
    _sgs(
        4380,
        "PIB mensal — valores correntes",
        "A1",
        "M",
        "R$ milhoes",
        lag_divulgacao_dias=60,
        obs="jan/06 = 181707.7. Nominal — nao usar como proxy de volume.",
    ),
    # --- câmbio -----------------------------------------------------------------------------
    _sgs(
        1,
        "Taxa de cambio livre — dolar americano (venda) — PTAX",
        "C1",
        "D",
        "BRL",
        transformacao_padrao="ultimo_dia_util_do_trimestre",
        obs="09/10/2026 = 4.9892 (valor-canario). Fonte primaria do USDBRL (nao FRED/Yahoo).",
    ),
    _sgs(
        10813,
        "Taxa de cambio livre — dolar americano (compra) — PTAX",
        "C1",
        "D",
        "BRL",
        transformacao_padrao="ultimo_dia_util_do_trimestre",
        obs="09/10/2026 = 4.9886.",
    ),
    # --- fiscal e commodities ---------------------------------------------------------------
    _sgs(
        4513,
        "Divida liquida do setor publico (% PIB) — consolidado",
        "-",
        "M",
        "%",
        lag_divulgacao_dias=30,
        obs="jan/06 = 47.82. Escolhida em vez da DBGG porque cobre 2006 (L10).",
    ),
    _sgs(
        27574,
        "Indice de Commodities Brasil (IC-Br) — geral",
        "-",
        "M",
        "index",
        obs="jan/06 = 101.81. Proxy candidata de termos de troca (feature z6 da V3).",
    ),
    _sgs(
        27575,
        "Indice de Commodities Brasil (IC-Br) — agropecuaria",
        "-",
        "M",
        "index",
        obs="jan/06 = 104.78.",
    ),
    # --- não servem (documentadas para evitar retrabalho) -----------------------------------
    _sgs(
        13762,
        "Divida bruta do governo geral (% PIB) — metodologia a partir de 2008",
        "-",
        "M",
        "%",
        data_inicio="2008-01-01",
        status="descartada",
        obs="404 em 2006. Para a janela usar DLSP (4513) — L10.",
    ),
    _sgs(
        24369,
        "Taxa de desocupacao — PNAD Continua (via BCB)",
        "-",
        "M",
        "%",
        data_inicio="2012-01-01",
        status="descartada",
        obs="404 em 2006 (PNADC comeca em 2012). Desemprego fica fora do escopo minimo (L9).",
    ),
    _sgs(
        7806,
        "Taxa referencial de swap DI x pre 360 dias",
        "A6",
        "D",
        "%a.a.",
        data_fim="2019-09-30",
        status="descontinuada",
        obs="ERA A ROTA SUGERIDA NO E-MAIL. 7801-7806 (diarias) morrem em 30/09/2019 e 7816-7827 "
        "(mensais) em 01/08/2019. Substituida pelo Tesouro Direto (L7): ver DECISIONS_LOG.",
    ),
    # --- a confirmar ------------------------------------------------------------------------
    {
        "series_id": "BCB_SGS_DBGG_PRE2008",
        "nome": "Divida bruta do governo geral — serie antiga (2006-2007)",
        "item_email": "-",
        "fonte": "BCB_SGS",
        "identificador": "a_confirmar",
        "fonte_url": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados",
        "freq": "M",
        "unit": "%",
        "confianca": "NAO_VERIFICADO",
        "status": "a_confirmar",
        "obs": "Gap G-07: a pesquisa sugere 4537/serie antiga, sem confirmar. Fora do critico.",
    },
    _sgs(
        21619,
        "Euro — taxa de cambio (venda ou compra, a confirmar qual)",
        "-",
        "D",
        "BRL",
        status="a_confirmar",
        confianca="CONFIRMADO",
        obs="Existencia e cobertura de 2006 confirmadas; qual serie e venda e qual e compra: "
        "a confirmar. Fora do escopo minimo.",
    ),
    _sgs(
        4192,
        "Agregado monetario (identificacao exata a confirmar)",
        "-",
        "M",
        "R$ milhoes",
        status="a_confirmar",
        obs="Existencia confirmada; qual agregado exatamente: a confirmar. Fora do escopo minimo.",
    ),
    # --- índices ANBIMA no SGS: só reconciliação (descontinuados em 22/05/2023) --------------
    _sgs(
        12466,
        "IMA-B (numero-indice) via SGS — descontinuado",
        "B1",
        "D",
        "index",
        data_inicio="2004-04-30",
        data_fim="2023-05-22",
        status="descontinuada",
        is_total_return=True,
        obs="02/01/2006 = 1108.830531. Uso: reconciliacao com o S3 (bate com 6 decimais).",
    ),
    _sgs(
        12467,
        "IMA-B 5 (numero-indice) via SGS — descontinuado",
        "B1",
        "D",
        "index",
        data_inicio="2004-04-30",
        data_fim="2023-05-22",
        status="descontinuada",
        is_total_return=True,
        obs="02/01/2006 = 1102.270604. Uso: reconciliacao.",
    ),
    _sgs(
        12468,
        "IMA-B 5+ (numero-indice) via SGS — descontinuado",
        "B1",
        "D",
        "index",
        data_inicio="2004-04-30",
        data_fim="2023-05-22",
        status="descontinuada",
        is_total_return=True,
        obs="02/01/2006 = 1107.295415. Uso: reconciliacao.",
    ),
    _sgs(
        12461,
        "IRF-M (numero-indice) via SGS — descontinuado",
        "B2",
        "D",
        "index",
        data_inicio="2003-01-02",
        data_fim="2023-05-22",
        status="descontinuada",
        is_total_return=True,
        obs="02/01/2006 = 2554.550434. NAO existem series SGS para IRF-M 1 nem IRF-M 1+.",
    ),
    _sgs(
        12469,
        "IMA-Geral (numero-indice) via SGS — descontinuado",
        "B2",
        "D",
        "index",
        data_inicio="2004-04-30",
        data_fim="2023-05-22",
        status="descontinuada",
        is_total_return=True,
        obs="02/01/2006 = 1137.405183. Uso: reconciliacao.",
    ),
    _sgs(
        12462,
        "IMA-S (numero-indice) via SGS — descontinuado",
        "B2",
        "D",
        "index",
        data_inicio="2004-04-30",
        data_fim="2023-05-22",
        status="descontinuada",
        is_total_return=True,
        obs="02/01/2006 = 1147.988972. Uso: reconciliacao.",
    ),
]

_BCB_FOCUS: list[dict[str, Any]] = [
    {
        "series_id": "FOCUS_ANUAIS",
        "nome": "Expectativas de mercado anuais (IPCA, Selic, PIB, cambio) por data de coleta",
        "item_email": "A3",
        "fonte": "BCB_OLINDA",
        "identificador": "ExpectativasMercadoAnuais",
        "fonte_url": URL_OLINDA.format(es="ExpectativasMercadoAnuais"),
        "freq": "D",
        "unit": "%",
        "data_inicio": "1999-04-30",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
        "obs": "Filtrar baseCalculo por um unico valor (0 ou 1), senao duplica linha (G-05). "
        "$top=20000 trunca sem nextLink: omitir $top ou paginar com $skip.",
    },
    {
        "series_id": "FOCUS_MENSAIS",
        "nome": "Expectativas de mercado mensais por data de coleta",
        "item_email": "A3",
        "fonte": "BCB_OLINDA",
        "identificador": "ExpectativaMercadoMensais",
        "fonte_url": URL_OLINDA.format(es="ExpectativaMercadoMensais"),
        "freq": "D",
        "unit": "%",
        "data_inicio": "2000-01-03",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
        "obs": "Nome do EntitySet tem singular/plural trocado vs. EntityType — nao normalizar "
        "por conta.",
    },
    {
        "series_id": "FOCUS_TRIMESTRAIS",
        "nome": "Expectativas de mercado trimestrais por data de coleta",
        "item_email": "A3",
        "fonte": "BCB_OLINDA",
        "identificador": "ExpectativasMercadoTrimestrais",
        "fonte_url": URL_OLINDA.format(es="ExpectativasMercadoTrimestrais"),
        "freq": "D",
        "unit": "%",
        "data_inicio": "2001-11-06",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
    },
    {
        "series_id": "FOCUS_SELIC",
        "nome": "Expectativa de Selic por reuniao do Copom",
        "item_email": "A3",
        "fonte": "BCB_OLINDA",
        "identificador": "ExpectativasMercadoSelic",
        "fonte_url": URL_OLINDA.format(es="ExpectativasMercadoSelic"),
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-11-18",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
        "obs": "Campo Reuniao no formato 'R1/2026'.",
    },
    {
        "series_id": "FOCUS_INFLACAO_12M",
        "nome": "Expectativa de inflacao para os proximos 12 meses",
        "item_email": "A3",
        "fonte": "BCB_OLINDA",
        "identificador": "ExpectativasMercadoInflacao12Meses",
        "fonte_url": URL_OLINDA.format(es="ExpectativasMercadoInflacao12Meses"),
        "freq": "D",
        "unit": "%",
        "data_inicio": "2001-11-07",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO",
        "obs": "Campo Suavizada (S/N): escolher e declarar. Insumo do juro real ex-ante (z3).",
    },
    {
        "series_id": "FOCUS_PIB_TOTAL",
        "nome": "Expectativa de PIB total — rotulo do indicador a confirmar",
        "item_email": "A3",
        "fonte": "BCB_OLINDA",
        "identificador": "a_confirmar",
        "fonte_url": URL_OLINDA.format(es="ExpectativasMercadoAnuais"),
        "freq": "D",
        "unit": "%",
        "confianca": "NAO_VERIFICADO",
        "status": "a_confirmar",
        "obs": "Gap G-04: enumerar os valores de 'Indicador' baixando um ano e fazendo set(). "
        "Confirmados: IPCA, Cambio, Selic, PIB Agropecuaria, IGP-DI, IGP-M, IPC-Fipe.",
    },
]

_IBGE_SIDRA: list[dict[str, Any]] = [
    {
        "series_id": "SIDRA_1737_V63",
        "nome": "IPCA — variacao mensal (SIDRA)",
        "item_email": "A7",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/1737 v/63",
        "fonte_url": URL_SIDRA.format(t=1737, v=63),
        "freq": "M",
        "unit": "%",
        "data_inicio": "1979-12-01",
        "transformacao_padrao": "acumulacao_geometrica_no_trimestre",
        "lag_divulgacao_dias": 10,
        "confianca": "CONFIRMADO",
        "obs": "Primeira linha da resposta e CABECALHO. UTF-8: declarar encoding no Windows.",
    },
    {
        "series_id": "SIDRA_1737_V2265",
        "nome": "IPCA — acumulado em 12 meses (SIDRA)",
        "item_email": "A7",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/1737 v/2265",
        "fonte_url": URL_SIDRA.format(t=1737, v=2265),
        "freq": "M",
        "unit": "%",
        "data_inicio": "1979-12-01",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "lag_divulgacao_dias": 10,
        "confianca": "CONFIRMADO",
    },
    {
        "series_id": "SIDRA_1737_V2266",
        "nome": "IPCA — numero-indice (base dez/1993 = 100)",
        "item_email": "A7",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/1737 v/2266",
        "fonte_url": URL_SIDRA.format(t=1737, v=2266),
        "freq": "M",
        "unit": "index",
        "data_inicio": "1979-12-01",
        "transformacao_padrao": "razao_de_numero_indice",
        "lag_divulgacao_dias": 10,
        "confianca": "CONFIRMADO",
        "obs": "Base da deflacao (ret_real) e do IPCA trimestral por razao.",
    },
    {
        "series_id": "SIDRA_1621_V584_90707",
        "nome": "PIB a precos de mercado — indice de volume com ajuste sazonal",
        "item_email": "A1",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/1621 v/584 c11255/90707",
        "fonte_url": URL_SIDRA_C.format(t=1621, v=584, c=90707),
        "freq": "Q",
        "unit": "index",
        "data_inicio": "1996-01-01",
        "transformacao_padrao": "variacao_12_meses",
        "lag_divulgacao_dias": 60,
        "confianca": "CONFIRMADO",
        "obs": "2006T1 = 131.74; 2006T2 = 132.14; 2006T3 = 134.36 (valores-canario). "
        "Espelho exato de SGS 22109. Use SIDRA quando precisar da abertura setorial (c11255).",
    },
    {
        "series_id": "SIDRA_1620_V583_90707",
        "nome": "PIB a precos de mercado — indice de volume sem ajuste sazonal",
        "item_email": "A1",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/1620 v/583 c11255/90707",
        "fonte_url": URL_SIDRA_C.format(t=1620, v=583, c=90707),
        "freq": "Q",
        "unit": "index",
        "data_inicio": "1996-01-01",
        "lag_divulgacao_dias": 60,
        "confianca": "CONFIRMADO",
    },
    {
        "series_id": "SIDRA_5932_V6564_90707",
        "nome": "PIB — taxa de variacao T/T-1 dessazonalizada",
        "item_email": "A1",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/5932 v/6564 c11255/90707",
        "fonte_url": URL_SIDRA_C.format(t=5932, v=6564, c=90707),
        "freq": "Q",
        "unit": "%",
        "data_inicio": "1996-01-01",
        "lag_divulgacao_dias": 60,
        "confianca": "CONFIRMADO",
        "obs": "1T06 = 1.6%. Variacao pronta, evita recalcular de 1621.",
    },
    {
        "series_id": "SIDRA_2176_DESOCUPACAO_PME",
        "nome": "PME — taxa de desocupacao (ponte 2006-2011)",
        "item_email": "-",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/2176",
        "fonte_url": URL_SIDRA.format(t=2176, v="all"),
        "freq": "M",
        "unit": "%",
        "data_inicio": "2002-03-01",
        "data_fim": "2016-02-01",
        "status": "descartada",
        "confianca": "CONFIRMADO",
        "obs": "Fora do escopo minimo (L9): emendar com PNADC t/4099 exige calibrar overlap.",
    },
    {
        "series_id": "SIDRA_4099_DESOCUPACAO_PNADC",
        "nome": "PNAD Continua trimestral — taxa de desocupacao",
        "item_email": "-",
        "fonte": "IBGE_SIDRA",
        "identificador": "t/4099",
        "fonte_url": URL_SIDRA.format(t=4099, v="all"),
        "freq": "Q",
        "unit": "%",
        "data_inicio": "2012-01-01",
        "status": "descartada",
        "confianca": "CONFIRMADO",
        "obs": "Nao cobre 2006 (L9).",
    },
    {
        "series_id": "SIDRA_IPCA_GRUPOS_2006_2011",
        "nome": "IPCA por grupos — tabela que cobre 2006-2011",
        "item_email": "-",
        "fonte": "IBGE_SIDRA",
        "identificador": "a_confirmar",
        "fonte_url": "https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all",
        "freq": "M",
        "unit": "%",
        "confianca": "NAO_VERIFICADO",
        "status": "a_confirmar",
        "obs": "L13: t/1419 cobre 201201-201912 e t/7060 so 202001+. Nao existe tabela unica "
        "2006-2026; a de 2006-2011 e a confirmar. Fora do escopo minimo.",
    },
]

_TESOURO_E_CURVA: list[dict[str, Any]] = [
    {
        "series_id": "TESOURO_TD_PRECOTAXA",
        "nome": "Tesouro Direto — taxas e PUs diarios por titulo e vencimento",
        "item_email": "A5",
        "fonte": "TESOURO_CKAN",
        "identificador": "precotaxatesourodireto.csv",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-12-31",
        "confianca": "CONFIRMADO",
        "obs": "Arquivo unico de 14,6 MB com 177.260 linhas; ';' + decimal virgula + latin-1 + "
        "datas dd/mm/aaaa; CKAN exige User-Agent de browser. 8 tipos de titulo. "
        "Em 2006 havia 10 vencimentos de NTN-B (ate 15/05/2045) e a LTN mais longa ia a 2009.",
    },
    {
        "series_id": "CURVA_REAL_1A",
        "nome": "Taxa real (NTN-B) interpolada para o vertice de 1 ano",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "interpolacao de TESOURO_TD_PRECOTAXA (Tesouro IPCA+)",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "interpolacao_para_vertice_fixo",
        "confianca": "NAO_VERIFICADO",
        "obs": "Serie CONSTRUIDA por nos (metodo em fontes-de-dados A5.4). Exige conferencia "
        "numerica classe C antes de virar numero em slide. Flag vertice_extrapolado obrigatoria.",
    },
    {
        "series_id": "CURVA_REAL_5A",
        "nome": "Taxa real (NTN-B) interpolada para o vertice de 5 anos",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "interpolacao de TESOURO_TD_PRECOTAXA (Tesouro IPCA+)",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "interpolacao_para_vertice_fixo",
        "confianca": "NAO_VERIFICADO",
        "obs": "Serie construida por nos; curva real completa desde 2006 (10 NTN-B vivas).",
    },
    {
        "series_id": "CURVA_NOMINAL_1A",
        "nome": "Taxa nominal (LTN/NTN-F) interpolada para o vertice de 1 ano",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "interpolacao de TESOURO_TD_PRECOTAXA (Prefixado)",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "interpolacao_para_vertice_fixo",
        "confianca": "NAO_VERIFICADO",
        "obs": "Serie construida por nos. Ponta curta nominal e robusta em toda a janela.",
    },
    {
        "series_id": "CURVA_NOMINAL_5A",
        "nome": "Taxa nominal (NTN-F) interpolada para o vertice de 5 anos",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "interpolacao de TESOURO_TD_PRECOTAXA (Prefixado c/ juros sem.)",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "interpolacao_para_vertice_fixo",
        "confianca": "NAO_VERIFICADO",
        "obs": "Serie construida por nos. 5 anos e a ponta longa nominal viavel na janela inteira; "
        "o vertice de 10 anos NAO existe antes de ~2010 (L5) e retorna NULL + flag.",
    },
    {
        "series_id": "INCLINACAO_REAL_5A_1A",
        "nome": "Inclinacao real da curva (NTN-B 5a menos 1a)",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "CURVA_REAL_5A - CURVA_REAL_1A",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "pp",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "NAO_VERIFICADO",
        "obs": "VARIAVEL PRINCIPAL DE CURVA na V3 (L4/L5). Nao e a ETTJ Svensson oficial da "
        "ANBIMA: sao taxas do Tesouro Direto (varejo), com pequeno spread vs. secundario.",
    },
    {
        "series_id": "INCLINACAO_NOMINAL_5A_1A",
        "nome": "Inclinacao nominal da curva (5a menos 1a)",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "CURVA_NOMINAL_5A - CURVA_NOMINAL_1A",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "pp",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "NAO_VERIFICADO",
        "obs": "Serie construida por nos; proxy do 'DI curto vs longo' pedido no e-mail.",
    },
    {
        "series_id": "BREAKEVEN_5A",
        "nome": "Inflacao implicita de 5 anos (NTN-F vs NTN-B)",
        "item_email": "A6",
        "fonte": "DERIVADO",
        "identificador": "(1+CURVA_NOMINAL_5A)/(1+CURVA_REAL_5A)-1",
        "fonte_url": URL_TESOURO,
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2004-12-31",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "NAO_VERIFICADO",
        "obs": "Serie construida por nos, do mesmo arquivo. Sempre por razao, nunca por subtracao.",
    },
    {
        "series_id": "ANBIMA_MS_SECUNDARIO",
        "nome": "ANBIMA — taxas indicativas do mercado secundario (trilho incremental)",
        "item_email": "A5",
        "fonte": "ANBIMA_WEB",
        "identificador": "Msec_txt.txt / ms{AAMMDD}.txt",
        "fonte_url": "https://www.anbima.com.br/informacoes/merc-sec/arqs/Msec_txt.txt",
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2026-09-11",
        "transformacao_padrao": "nenhuma",
        "confianca": "CONFIRMADO_SUB",
        "janela_rolante": True,
        "obs": "JANELA ROLANTE DE ~20 DIAS UTEIS: nao existe nada de 2006. Padrao do nome e "
        "ms{AAMMDD}, nao ms{ddmmaa}. Separador '@', skiprows=2, latin-1, CRLF. "
        "Arquivar diariamente desde hoje (L6/R3); ausencia/atraso e caso normal.",
    },
    {
        "series_id": "ANBIMA_CZ_SVENSSON",
        "nome": "ANBIMA Curva Zero — parametros Svensson (trilho incremental)",
        "item_email": "A6",
        "fonte": "ANBIMA_WEB",
        "identificador": "POST CZ-down.asp (Idioma=PT&Dt_Ref=dd/mm/aaaa&saida=csv)",
        "fonte_url": "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp",
        "freq": "D",
        "unit": "%a.a.",
        "data_inicio": "2026-09-14",
        "transformacao_padrao": "nenhuma",
        "confianca": "CONFIRMADO_SUB",
        "janela_rolante": True,
        "obs": "JANELA ROLANTE: 14/09/2026 e o mais antigo com dados; 02/01/2006 devolve 0 bytes. "
        "saida=xls e HTML, nao Excel. Vertices com ponto de milhar. Arquivar diariamente.",
    },
    {
        "series_id": "ANBIMA_FEED_ETTJ_HISTORICA",
        "nome": "ANBIMA Feed — ETTJ Svensson historica (produto pago)",
        "item_email": "A6",
        "fonte": "ANBIMA_WEB",
        "identificador": "api.anbima.com.br/feed/precos-indices (OAuth2)",
        "fonte_url": "https://developers.anbima.com.br/pt/documentacao/precos-indices/",
        "freq": "D",
        "unit": "%a.a.",
        "status": "paga",
        "confianca": "CONFIRMADO_SUB",
        "obs": "L4: unica forma de ter a ETTJ oficial com 20 anos. ~R$ 686/mes (usuario final) a "
        "~R$ 8.238/mes (parceiro) [NAO VERIFICADO]. Fora do caminho critico; uso seria classe D.",
    },
    {
        "series_id": "ANBIMA_FERIADOS_NACIONAIS",
        "nome": "Calendario de feriados nacionais ANBIMA",
        "item_email": "A4",
        "fonte": "ANBIMA_WEB",
        "identificador": "feriados_nacionais.xls",
        "fonte_url": "https://www.anbima.com.br/feriados/arqs/feriados_nacionais.xls",
        "freq": "A",
        "unit": "index",
        "transformacao_padrao": "nenhuma",
        "confianca": "CONFIRMADO",
        "obs": "HTTP 200, 111.104 bytes, sem autenticacao. Base de TODO alinhamento e acumulacao; "
        "2006 tem 249 dias uteis (confere com a contagem do CDI). Fallback: lib bizdays.",
    },
]

# ============================================================================================
# BLOCO B — ATIVOS E SUBSETORES (itens B1..B5)
# ============================================================================================

_ANBIMA_IMA: list[dict[str, Any]] = [
    _s3("IMAB", "IMA-B — numero-indice diario", "B1", "2003-09-16",
        obs="Valor-canario: 16/09/2003 = 723,070317. XLSX apesar da extensao .xls."),
    _s3("IMAB5", "IMA-B 5 — numero-indice diario", "B1", "2003-09-16"),
    _s3("IMAB5MAIS", "IMA-B 5+ — numero-indice diario", "B1", "2003-09-16",
        obs="SLUG usa '5MAIS' (nao '+', nem 'P', nem 'PLUS'). Listagem do bucket e AccessDenied."),
    _s3("IRFM", "IRF-M — numero-indice diario", "B2", "2000-02-01"),
    _s3("IRFM1", "IRF-M 1 — numero-indice diario", "B2", "2000-12-01",
        obs="NAO existe serie equivalente no SGS — o S3 e a unica fonte gratuita."),
    _s3("IRFM1MAIS", "IRF-M 1+ — numero-indice diario", "B2", "2000-12-01",
        obs="NAO existe serie equivalente no SGS — o S3 e a unica fonte gratuita."),
    _s3("IMAGERAL", "IMA-Geral — numero-indice diario", "B2", "2001-12-04"),
    _s3("IMAS", "IMA-S — numero-indice diario", "B2", "2001-12-03"),
    _s3("IMAGERALEXC", "IMA-Geral ex-C — numero-indice diario", "B2", "2005-03-31"),
    _s3("IMAC", "IMA-C — numero-indice diario (descontinuado)", "B2", "2001-12-03",
        data_fim="2021-04-01", status="descontinuada",
        obs="Descontinuado em 01/04/2021; fora do painel de ativos."),
    _s3("IHFA", "IHFA — Indice de Hedge Funds ANBIMA", "-", "2007-09-28",
        obs="Bonus: nao esta no e-mail e nao cobre 2006 inteiro. Fora do escopo minimo."),
]

_B3_INDICES: list[dict[str, Any]] = [
    _b3("IBOV", "Ibovespa", "B4", "1968-01-02", is_total_return=True,
        obs="Valor-canario: 01/02/2006 = 38.484,84 (246 pontos em 2006). "
            "Retorno total CONFIRMADO (proventos incorporados, liquidos de imposto)."),
    _b3("IDIV", "Indice Dividendos (IDIV)", "B4", "2005-12-29",
        obs="Base 29/12/2005 = 1.000,00; 246 pontos em 2006. Retorno total a confirmar (G-01)."),
    _b3("SMLL", "Indice Small Cap (SMLL)", "B4", "2005-08-31",
        obs="Base 31/08/2005 = 517,94; 246 pontos em 2006. Retorno total a confirmar (G-01)."),
    _b3("INDX", "Indice do Setor Industrial (INDX)", "B4", "1999-12-30",
        obs="Base 30/12/1999 = 1.000,00; 246 pontos em 2006. Retorno total a confirmar (G-01)."),
    _b3("IMAT", "Indice Materiais Basicos (IMAT)", "B4", "2005-12-29",
        obs="Base 29/12/2005 = 1.000,00; 246 pontos em 2006. Retorno total a confirmar (G-01)."),
    _b3("IEEX", "Indice de Energia Eletrica (IEE)", "B4", "1994-01-03",
        obs="CODIGO NA API E 'IEEX', NAO 'IEE'. 246 pontos em 2006. "
            "Retorno total a confirmar (G-01)."),
    _b3("IFNC", "Indice Financeiro (IFNC)", "B4", "2004-12-30",
        obs="Base 30/12/2004 = 858,40; 246 pontos em 2006. Retorno total a confirmar (G-01)."),
    _b3("UTIL", "Indice Utilidade Publica (UTIL)", "B4", "2005-12-29",
        obs="Base 29/12/2005 = 1.000,00. Nao citado no e-mail; complementa IEEX. "
            "Retorno total a confirmar (G-01)."),
    _b3("ICON", "Indice de Consumo (ICON)", "B4", "2006-12-28",
        obs="NAO COBRE 2006: em 2006 existe apenas o ponto-base 28/12/2006 = 1.000,00; serie "
            "efetiva a partir de 2007 (245 pontos). Janela propria, sem backfill (L3)."),
    _b3("IMOB", "Indice Imobiliario (IMOB)", "B4", "2007-12-28",
        obs="NAO COBRE 2006-2007: ponto-base 28/12/2007 = 1.000,00; serie efetiva a partir de 2008 "
            "(249 pontos). Usado tambem como proxy imperfeito de FII pre-2011 (L1/L3)."),
    _b3("IFIX", "Indice de Fundos Imobiliarios (IFIX)", "B5", "2010-12-30", is_total_return=True,
        obs="NAO COBRE 2006-2010: ponto-base 30/12/2010 = 1.000,00; efetiva a partir de 2011. "
            "Retorno total CONFIRMADO (cotas + rendimentos). Janela propria 2011-2026 (L1)."),
    _b3("IFIL", "IFIX-L (subconjunto de alta liquidez)", "B5", "2017-12-28",
        status="descartada",
        obs="CODIGO NA API E 'IFIL'. Base 28/12/2017; nao e segmentacao setorial, e filtro de "
            "liquidez. Fora do escopo minimo."),
    {
        "series_id": "B3_COTAHIST",
        "nome": "B3 COTAHIST — cotacoes historicas de todos os papeis",
        "item_email": "B5",
        "fonte": "B3_API",
        "identificador": "COTAHIST_A{YYYY}.ZIP",
        "fonte_url": "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A2006.ZIP",
        "freq": "D",
        "unit": "BRL",
        "data_inicio": "1986-01-01",
        "transformacao_padrao": "nenhuma",
        "confianca": "CONFIRMADO_SUB",
        "status": "descartada",
        "obs": "Fase 2 (construcao propria de FII): largura fixa 245, latin-1, CODBDI 12 = FII, "
        "precos inteiros a dividir por 100, NAO ajustado e SEM proventos. 2026 tem 91 MB. "
        "Fora do pacote minimo (esforco alto).",
    },
]

_TEVA_FII: list[dict[str, Any]] = [
    _teva("3.2.2", "FII_TIJOLO", "Indice Teva de Fundos Imobiliarios de Tijolo",
          obs="02/01/2019 = 100; 09/10/2026 = 160,76. Licenca restrita (L2)."),
    _teva("3.2.1", "FII_PAPEL", "Indice Teva de Fundos Imobiliarios de Papel (CRI)",
          obs="02/01/2019 = 100; 09/10/2026 = 199,98. Licenca restrita (L2)."),
    _teva("3.3.1", "FII_LOGISTICA", "Indice Teva de Fundos Imobiliarios de Logistica",
          obs="02/01/2019 = 100; 09/10/2026 = 192,65. Licenca restrita (L2)."),
    _teva("3.3.3", "FII_SHOPPINGS", "Indice Teva de Fundos Imobiliarios de Shoppings",
          obs="02/01/2019 = 100; 09/10/2026 = 184,98. Licenca restrita (L2)."),
    _teva("3.3.2", "FII_LAJES", "Indice Teva de Fundos Imobiliarios de Lajes Corporativas",
          obs="02/01/2019 = 100; 09/10/2026 = 116,73 (dispersao setorial e o sinal procurado)."),
    _teva("3.1.1", "FII_GERAL", "Indice Teva de Fundos Imobiliarios (geral)",
          obs="Usado apenas como cross-check do IFIX no periodo 2019+."),
    {
        "series_id": "CVM_INF_MENSAL_FII",
        "nome": "CVM — informe mensal de FII (classificacao por segmento e balanco)",
        "item_email": "B5",
        "fonte": "CVM",
        "identificador": "inf_mensal_fii_{YYYY}.zip",
        "fonte_url": "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/"
        "inf_mensal_fii_2019.zip",
        "freq": "M",
        "unit": "BRL",
        "data_inicio": "2016-01-01",
        "transformacao_padrao": "nenhuma",
        "confianca": "CONFIRMADO_SUB",
        "status": "descartada",
        "obs": "Fase 2. QUEBRA DE TAXONOMIA: Mandato vazio desde 2025-09 e Segmento mudou "
        "(Res. CVM 175) — classificar pelo BALANCO (ativo_passivo), nao pela taxonomia. "
        "Nomes de coluna mudaram em 2021 (exige alias). Fora do pacote minimo.",
    },
]

# ============================================================================================
# BLOCO C — INTERNACIONAL (item C1) E AGREGADORES
# ============================================================================================

_INTERNACIONAL: list[dict[str, Any]] = [
    _yahoo("GSPC", "^GSPC", "S&P 500 (indice de preco)", "C1", "1927-12-30",
           obs="Rota recomendada para S&P 500 (o FRED 'SP500' tem so 10 anos). Para retorno total "
               "preferir ^SP500TR ou MSCI USA; nunca misturar price e total return (RN-08)."),
    _yahoo("VIX", "^VIX", "VIX — volatilidade implicita S&P 500", "C1", "1990-01-02",
           obs="Fallback do FRED VIXCLS se a conectividade falhar (G-06)."),
    _yahoo("TNX", "^TNX", "Treasury 10 anos (rendimento)", "C1", "1962-01-02", unit="%a.a.",
           obs="Fallback do FRED DGS10 se a conectividade falhar (G-06)."),
    _yahoo("DXY", "DX-Y.NYB", "Dollar Index (DXY)", "C1", "1971-01-04",
           obs="Fallback do FRED DTWEXBGS; DTWEXM foi descontinuado em 2019."),
    _yahoo("BRLX", "BRL=X", "USDBRL (Yahoo)", "C1", "2003-12-01", unit="BRL",
           obs="Preferir PTAX (SGS 1) como primaria; este e so cross-check."),
    _yahoo("IVV", "IVV", "ETF iShares Core S&P 500", "C1", "2000-05-19",
           obs="Fallback com dividendos via auto_adjust; ETF tem tracking error e taxa."),
    _yahoo("ACWI", "ACWI", "ETF iShares MSCI ACWI", "C1", "2008-03-28", status="descartada",
           obs="NAO cobre 2006 (firstTradeDate 2008-03-28). Fallback do MSCI 892400 so a partir "
               "de 2008."),
    _yahoo("URTH", "URTH", "ETF iShares MSCI World", "C1", "2012-01-12", status="descartada",
           obs="NAO cobre 2006 (firstTradeDate 2012-01-12)."),
    _yahoo("IVVB11", "IVVB11.SA", "ETF S&P 500 em BRL (IVVB11)", "C1", "2014-04-29",
           status="descartada",
           obs="NAO cobre 2006; util apenas como sanity check do SP500_BRL a partir de 2014."),
    _yahoo("XFIX11", "XFIX11.SA", "ETF de IFIX (XFIX11)", "B5", "2020-11-27", status="descartada",
           obs="NAO cobre a janela e e price return (subestima o IFIX, que e retorno total)."),
    _yahoo("BVSP", "^BVSP", "Ibovespa (Yahoo)", "B4", "1993-04-27",
           obs="Cross-check do IBOV da API B3; para a serie oficial usar a API da B3."),
    {
        "series_id": "YAHOO_SETORIAIS_B3_SA",
        "nome": "Setoriais da B3 no Yahoo (SMLL.SA, IDIV.SA, IFIX.SA, ...)",
        "item_email": "B4",
        "fonte": "YAHOO",
        "identificador": "SMLL.SA / IDIV.SA / IFIX.SA / IFNC.SA / IMOB.SA / IMAT.SA / INDX.SA",
        "fonte_url": URL_YAHOO.format(ticker="SMLL.SA"),
        "freq": "D",
        "unit": "index",
        "confianca": "CONFIRMADO_SUB",
        "status": "descartada",
        "obs": "ARMADILHA: HTTP 200 e quote existente, mas devolve 1 ponto (hoje) em qualquer "
        "range — falha silenciosa. yfinance usa o mesmo backend. Validar len(df) > 1. "
        "Usar a API da B3.",
    },
    {
        "series_id": "MSCI_ACWI_NETR",
        "nome": "MSCI ACWI — net total return (USD)",
        "item_email": "C1",
        "fonte": "MSCI",
        "identificador": "892400 / NETR",
        "fonte_url": URL_MSCI.format(cod=892400, variant="NETR"),
        "freq": "D",
        "unit": "index",
        "data_inicio": "2000-12-29",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "is_total_return": True,
        "fonte_instavel": True,
        "obs": "Valor-canario: ACWI NETR 31/01/2006 = 121,3858. Endpoint publico nao doc. da "
        "app web do MSCI (exige UA de browser); start_date < 19970101 da erro. "
        "ROTA RECOMENDADA do bloco internacional.",
    },
    {
        "series_id": "MSCI_WORLD_NETR",
        "nome": "MSCI World — net total return (USD)",
        "item_email": "C1",
        "fonte": "MSCI",
        "identificador": "990100 / NETR",
        "fonte_url": URL_MSCI.format(cod=990100, variant="NETR"),
        "freq": "D",
        "unit": "index",
        "data_inicio": "2000-12-29",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "is_total_return": True,
        "fonte_instavel": True,
    },
    {
        "series_id": "MSCI_USA_NETR",
        "nome": "MSCI USA — net total return (USD)",
        "item_email": "C1",
        "fonte": "MSCI",
        "identificador": "984000 / NETR",
        "fonte_url": URL_MSCI.format(cod=984000, variant="NETR"),
        "freq": "D",
        "unit": "index",
        "data_inicio": "2000-12-29",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "is_total_return": True,
        "fonte_instavel": True,
        "obs": "Alternativa de retorno total para os EUA (o ^GSPC do Yahoo e price return).",
    },
    {
        "series_id": "MSCI_EM_NETR",
        "nome": "MSCI Emerging Markets — net total return (USD)",
        "item_email": "C1",
        "fonte": "MSCI",
        "identificador": "891800 / NETR",
        "fonte_url": URL_MSCI.format(cod=891800, variant="NETR"),
        "freq": "D",
        "unit": "index",
        "data_inicio": "2000-12-29",
        "transformacao_padrao": "ultimo_dia_util_do_trimestre",
        "confianca": "CONFIRMADO_SUB",
        "is_total_return": True,
        "fonte_instavel": True,
        "obs": "Opcional (MSCI_EM_BRL).",
    },
    {
        "series_id": "MSCI_BRAZIL",
        "nome": "MSCI Brazil — codigo do indice a confirmar",
        "item_email": "C1",
        "fonte": "MSCI",
        "identificador": "a_confirmar",
        "fonte_url": URL_MSCI.format(cod="{a_confirmar}", variant="NETR"),
        "freq": "D",
        "unit": "index",
        "confianca": "NAO_VERIFICADO",
        "status": "a_confirmar",
        "fonte_instavel": True,
        "obs": "O codigo 705000 testado devolveu lista vazia. Fora do escopo minimo.",
    },
    _fred("DGS10", "Treasury 10 anos — rendimento", "C1", "D", "%a.a."),
    _fred("DGS2", "Treasury 2 anos — rendimento", "C1", "D", "%a.a."),
    _fred("T10Y2Y", "Spread Treasury 10a-2a", "C1", "D", "pp"),
    _fred("T10Y3M", "Spread Treasury 10a-3m", "C1", "D", "pp"),
    _fred("VIXCLS", "VIX (fechamento)", "C1", "D", "index"),
    _fred("DFF", "Fed Funds — taxa efetiva diaria", "C1", "D", "%a.a."),
    _fred("FEDFUNDS", "Fed Funds — media mensal", "C1", "M", "%a.a."),
    _fred("DTWEXBGS", "Dolar index broad (nominal)", "C1", "D", "index",
          data_inicio="2006-01-02",
          obs="Comeca exatamente em 02/01/2006 — cobre a janela no limite. "
              "DTWEXM (o DXY antigo) foi descontinuado em 31/12/2019."),
    _fred("DEXBZUS", "USDBRL (FRED)", "C1", "D", "BRL", data_inicio="1995-01-02",
          obs="Cross-check da PTAX; a primaria e SGS 1."),
    _fred("T10YIE", "Breakeven de inflacao 10 anos (EUA)", "C1", "D", "%a.a.",
          data_inicio="2003-01-02"),
    _fred("SP500", "S&P 500 (FRED)", "C1", "D", "index", data_inicio="2016-10-10",
          status="descartada",
          obs="ARMADILHA: janela rolante de 10 anos por licenca da S&P (comeca em 2016-10-10). "
              "NAO usar. Rota correta: Yahoo ^GSPC ou MSCI USA (L11)."),
    _fred("DTWEXM", "Dolar index antigo (DXY) — descontinuado", "C1", "D", "index",
          data_inicio="1973-01-02", data_fim="2019-12-31", status="descontinuada",
          obs="Descontinuado em 31/12/2019. Usar DTWEXBGS ou DX-Y.NYB."),
    _fred("BAMLEMRLCRPILAOAS", "ICE BofA LatAm EM corporate OAS (perna B do risco-pais)", "-",
          "D", "bps", data_inicio="2023-10-10", status="descartada",
          obs="JANELA ROLANTE DE 3 ANOS por licenca da ICE. Fase 2: splice com EMBI+ no overlap "
              "2023-10-10..2024-07-30. Arquivar diariamente se for usada."),
    {
        "series_id": "GOLD_SPOT_USD",
        "nome": "Ouro spot em USD — fonte gratuita com 20 anos nao localizada",
        "item_email": "C1",
        "fonte": "MANUAL",
        "identificador": "a_confirmar",
        "fonte_url": "a_confirmar — ver docs/research/fontes-de-dados.md secao C10",
        "freq": "D",
        "unit": "USD",
        "confianca": "NAO_VERIFICADO",
        "status": "a_confirmar",
        "obs": "Gap G-03: IDs testados no FRED deram 404. Sem fonte confirmada, GOLD_BRL retorna "
        "BLOQUEADO — FONTE INDISPONIVEL e a linha NAO entra no heatmap (CA-050).",
    },
]

_IPEADATA: list[dict[str, Any]] = [
    _ipea("GM366_IBVSP366", "Ibovespa — fechamento diario (Ipeadata)", "B4", "D", "index",
          data_inicio="1993-04-27",
          obs="8.317 pontos nao nulos ate 08/10/2026; historico maior que o do Yahoo. "
              "Cross-check do IBOV da API B3."),
    _ipea("BM366_TJOVER366", "Selic Copom — diaria (Ipeadata)", "A4", "D", "%a.a.",
          data_inicio="1996-07-01",
          obs="11.058 pontos sem nulos; sem o limite de 10 anos do SGS. Fallback de SGS 11/432."),
    _ipea("ANBIMA366_TJTLN12366", "ETTJ prefixada ANBIMA — 12 meses", "A6", "D", "%a.a.",
          data_inicio="2000-04-04",
          obs="Unica fonte gratuita de ETTJ ANBIMA com historico longo — mas so a PONTA CURTA "
              "(1/3/6/12 meses: TJTLN1/3/6/12). 8.404 pontos nao nulos."),
    _ipea("ANBIMA366_TJTLN1366", "ETTJ prefixada ANBIMA — 1 mes", "A6", "D", "%a.a.",
          data_inicio="2000-04-04", obs="Ponta curta nominal; complementa o Tesouro Direto."),
    _ipea("BM12_IPCAEXP1212", "Expectativa media de IPCA 12 meses (Ipeadata)", "A3", "M", "%",
          obs="Alternativa ao Focus para a expectativa de 12 meses (fonte Bacen/Boletim)."),
    _ipea("JPM366_EMBI366", "EMBI+ Risco-Brasil (JP Morgan) — INATIVA", "-", "D", "bps",
          data_inicio="1994-04-29", data_fim="2024-07-30", status="descontinuada",
          obs="Unica serie de risco-pais em todo o Ipeadata (3.606 metadados varridos). "
              "SERSTATUS='I'; EMBI+ descontinuado pelo JP Morgan em jul/2024 (L8). "
              "Risco-pais fica fora do pacote minimo."),
    {
        "series_id": "IPEA_SCN104_PIB_SETORIAL",
        "nome": "PIB trimestral IBGE por setor (familia SCN104_*) — codigos a confirmar",
        "item_email": "A1",
        "fonte": "IPEADATA",
        "identificador": "a_confirmar",
        "fonte_url": "http://www.ipeadata.gov.br/api/odata4/Metadados",
        "freq": "Q",
        "unit": "index",
        "confianca": "NAO_VERIFICADO",
        "status": "a_confirmar",
        "obs": "121 series trimestrais de PIB confirmadas no catalogo, mas os SERCODIGO exatos por "
        "setor nao foram enumerados. Fora do caminho critico: para a abertura setorial, use "
        "SIDRA t/1621 com c11255.",
    },
]

SERIES_CATALOG: list[dict[str, Any]] = [
    *_BCB_SGS,
    *_BCB_FOCUS,
    *_IBGE_SIDRA,
    *_TESOURO_E_CURVA,
    *_ANBIMA_IMA,
    *_B3_INDICES,
    *_TEVA_FII,
    *_INTERNACIONAL,
    *_IPEADATA,
]
"""Catálogo completo. Ordem: bloco A (macro) → bloco B (ativos) → bloco C (internacional)."""
