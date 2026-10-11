"""Testes do extrator Yahoo `chart/v8` (F-007, SPEC RF-016/RF-017, CA-045 e CA-047).

Nenhum teste aqui toca a rede: tudo vem de `tests/fixtures/yahoo/`, que é **resposta real** da
fonte (janela recortada para caber nos 200 KB) mais os dois corpos de erro reais — o 404 de
ticker inexistente e o 429 que a fonte devolve sem `User-Agent`. O único teste que vai à fonte
viva está marcado `@pytest.mark.network` e o CI N1 o exclui com `-m "not network"`
(Anti-SPEC §10.4.23).

Onde a fixture é um recorte (1 ano), o parse roda com `minimo=None`; o piso real do contrato
(`FECHAMENTOS_MINIMOS`, 5.729 pontos no `^GSPC`) é exercitado nos testes de truncamento e no
teste de rede.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from apps.pipeline.common import (
    ConteudoDivergente,
    FormatoInesperado,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    UserAgentObrigatorio,
    cabecalhos_de_browser,
    caminho_processed,
    sha256_de,
)
from apps.pipeline.extract import yahoo
from apps.pipeline.extract.yahoo import (
    FECHAMENTOS_MINIMOS,
    INICIO_PADRAO,
    MOEDA_ESPERADA,
    PARAMETROS_PROIBIDOS,
    SERIES_BRL,
    TICKERS,
    TICKERS_PADRAO,
    TICKERS_SUPORTADOS,
    VALORES_CANARIO,
    ClienteHTTP,
    SerieInconsistente,
    conferir_canario,
    config_do_ticker,
    datas_de_pregao,
    extrair_ticker,
    extrair_ticker_offline,
    parametros_janela,
    parse_chart,
    series_id_de,
)
from apps.pipeline.transform import carregar_ptax, converter_para_brl
from packages.shared.schemas import ProcessedSeriesSchema, load_catalog

if TYPE_CHECKING:
    from pathlib import Path

COLETA = datetime(2026, 10, 10, 23, 0, tzinfo=UTC)

#: `tests/fixtures/yahoo/` — nomes pela convenção de `tests/fixtures/README.md`.
FIXTURA_GSPC = "^GSPC__2026-10-10.json"
FIXTURA_ERRO_404 = "^GSPC__erro_404_delisted.json"
FIXTURA_ERRO_429 = "^GSPC__erro_429_sem-ua.txt"
FIXTURA_RANGE_MAX = "^GSPC__range-max-1mo.json"
FIXTURA_UM_PONTO = "SMLL.SA__armadilha-1-ponto.json"
FIXTURA_IVV = "IVV__adjclose-difere.json"


# ─────────────────────────────────────────────────────────────────────────────
# Infra do teste
# ─────────────────────────────────────────────────────────────────────────────


class TransporteGravado:
    """Transporte falso (modelo copiado de `tests/unit/test_common_http.py`)."""

    def __init__(self, *respostas: RespostaBruta | Exception) -> None:
        self._respostas = list(respostas)
        self.chamadas: list[dict[str, Any]] = []

    def __call__(
        self,
        metodo: str,
        url: str,
        *,
        params: Any = None,
        dados: Any = None,
        cabecalhos: Any,
        timeout_s: float,
    ) -> RespostaBruta:
        self.chamadas.append(
            {
                "metodo": metodo,
                "url": url,
                "params": dict(params or {}),
                "cabecalhos": dict(cabecalhos),
            }
        )
        proxima = self._respostas.pop(0) if self._respostas else None
        if proxima is None:
            msg = f"transporte falso sem resposta programada para {metodo} {url}"
            raise AssertionError(msg)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


class TransporteSensivelAoUserAgent:
    """Reproduz o comportamento medido da fonte: sem UA → 429; com UA → 200 (CA-045)."""

    def __init__(self, corpo_ok: bytes, corpo_429: bytes) -> None:
        self._ok = corpo_ok
        self._429 = corpo_429
        self.chamadas: list[bool] = []

    def __call__(
        self,
        metodo: str,
        url: str,
        *,
        params: Any = None,
        dados: Any = None,
        cabecalhos: Any,
        timeout_s: float,
    ) -> RespostaBruta:
        tem_ua = bool(dict(cabecalhos).get("User-Agent", "").strip())
        self.chamadas.append(tem_ua)
        if not tem_ua:
            return RespostaBruta(url=url, status=429, conteudo=self._429, obtida_em=COLETA)
        return RespostaBruta(url=url, status=200, conteudo=self._ok, obtida_em=COLETA)


@pytest.fixture
def dir_yahoo() -> Path:
    """`tests/fixtures/yahoo/`."""
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"


@pytest.fixture
def gspc(dir_yahoo: Path) -> bytes:
    """Resposta real do `^GSPC` para 2006 inteiro (251 pregões)."""
    return (dir_yahoo / FIXTURA_GSPC).read_bytes()


def _quadro_gspc(conteudo: bytes) -> pd.DataFrame:
    return parse_chart(conteudo, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None)


def _ptax_sintetica(datas: pd.Series, valor: float = 2.2) -> pd.DataFrame:
    """PTAX **sintética** (nome explícito, `CLAUDE.md §4`) para os testes de conversão."""
    return pd.DataFrame({"date": pd.to_datetime(datas), "ptax": valor})


# ─────────────────────────────────────────────────────────────────────────────
# CA-045 — User-Agent, 429 com retry e `period1`/`period2` em vez de `range`
# ─────────────────────────────────────────────────────────────────────────────


def test_ca045_sem_user_agent_a_fonte_devolve_429_e_com_ua_devolve_200(
    dir_yahoo: Path, gspc: bytes
) -> None:
    """A fixture de erro é o corpo real do 429, e o cliente só é 200 porque manda UA de browser."""
    corpo_429 = (dir_yahoo / FIXTURA_ERRO_429).read_bytes()
    assert corpo_429 == b"Edge: Too Many Requests"

    transporte = TransporteSensivelAoUserAgent(corpo_ok=gspc, corpo_429=corpo_429)
    config = config_do_ticker("GSPC")

    sem_ua = ClienteHTTP(config, transporte=transporte, cabecalhos_base={}, dormir=lambda _: None)
    with pytest.raises(UserAgentObrigatorio):
        sem_ua.get(params=parametros_janela(date(2006, 1, 1), date(2006, 12, 31)))
    assert transporte.chamadas == [], "requisicao sem UA nao deve nem ser despachada"

    com_ua = ClienteHTTP(config, transporte=transporte, dormir=lambda _: None)
    resposta = com_ua.get(params=parametros_janela(date(2006, 1, 1), date(2006, 12, 31)))
    assert resposta.status == 200
    assert transporte.chamadas == [True]


def test_ca045_user_agent_do_cliente_e_de_browser_em_toda_requisicao(gspc: bytes) -> None:
    """O UA que vai no cabeçalho é o de browser da infra, não um default de biblioteca."""
    transporte = TransporteGravado(
        RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA)
    )
    ClienteHTTP(config_do_ticker("GSPC"), transporte=transporte).get(params=parametros_janela())
    enviado = transporte.chamadas[0]["cabecalhos"]["User-Agent"]
    assert enviado == cabecalhos_de_browser()["User-Agent"]
    assert "Mozilla/5.0" in enviado


def test_ca045_429_entra_no_retry_com_backoff_e_a_segunda_tentativa_vence(gspc: bytes) -> None:
    """429 é transitório: o cliente repete com backoff em vez de abortar a extração."""
    corpo_429 = b"Edge: Too Many Requests"
    transporte = TransporteGravado(
        RespostaBruta(url="https://x", status=429, conteudo=corpo_429, obtida_em=COLETA),
        RespostaBruta(url="https://x", status=429, conteudo=corpo_429, obtida_em=COLETA),
        RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA),
    )
    atrasos: list[float] = []
    cliente = ClienteHTTP(config_do_ticker("GSPC"), transporte=transporte, dormir=atrasos.append)
    resposta = cliente.get(params=parametros_janela())
    assert resposta.status == 200
    assert len(transporte.chamadas) == 3
    assert atrasos == [1.0, 2.0], "backoff exponencial entre as tentativas"


def test_ca045_janela_usa_period1_period2_e_nunca_range() -> None:
    """`range=max` trunca série longa em silêncio — nenhuma função emite `range` (R2)."""
    parametros = parametros_janela(date(2004, 1, 1), date(2026, 10, 10))
    assert set(parametros) == {"period1", "period2", "interval"}
    assert PARAMETROS_PROIBIDOS.isdisjoint(parametros)
    assert parametros["interval"] == "1d"
    # epoch seconds, não milissegundos nem ISO
    assert parametros["period1"] == 1072915200
    assert parametros["period2"] == 1791676800
    assert parametros["period1"] < parametros["period2"]


def test_ca045_range_max_mensal_e_recusado_pela_granularidade_e_pelo_piso(
    dir_yahoo: Path,
) -> None:
    """A resposta real de `range=max&interval=1mo` é truncada **e** rebaixada (R2).

    É a prova da pegadinha inteira, com dado real gravado em 2026-10-10: a fonte devolve
    HTTP 200, `chart.error` nulo, uma série plausível — e **169** pontos, contra 490 na mesma
    janela pedida com `period1`/`period2`. Pior: ela ignorou o `interval=1mo` e respondeu
    `dataGranularity="3mo"`, ou seja, trocou a frequência nativa sem avisar. As duas guardas
    pegam: a de granularidade primeiro, a de contagem mínima depois.
    """
    conteudo = (dir_yahoo / FIXTURA_RANGE_MAX).read_bytes()
    corpo = json.loads(conteudo.decode("utf-8"))
    resultado = corpo["chart"]["result"][0]
    assert corpo["chart"]["error"] is None
    assert len(resultado["timestamp"]) == 169
    assert resultado["meta"]["range"] == "max"
    assert resultado["meta"]["dataGranularity"] == "3mo", "pediu 1mo, a fonte devolveu 3mo"

    with pytest.raises(SerieInconsistente, match="dataGranularity"):
        parse_chart(conteudo, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None)

    # Com a granularidade corrigida à mão, o piso de contagem ainda barra os 169 pontos.
    resultado["meta"]["dataGranularity"] = "1d"
    with pytest.raises(RespostaTruncada):
        parse_chart(
            json.dumps(corpo).encode("utf-8"),
            chave="GSPC",
            origem="fixture",
            collected_at=COLETA,
        )


def test_ca045_janela_invertida_levanta() -> None:
    """Pedir `fim < inicio` é erro de chamada, não série vazia."""
    with pytest.raises(ValueError, match="janela invertida"):
        parametros_janela(date(2026, 1, 1), date(2025, 1, 1))


# ─────────────────────────────────────────────────────────────────────────────
# Parse da resposta real
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_do_gspc_produz_o_contrato_processed_series(gspc: bytes) -> None:
    """A resposta real de 2006 vira 251 linhas válidas por `ProcessedSeriesSchema`."""
    quadro = _quadro_gspc(gspc)
    ProcessedSeriesSchema.validate(quadro, lazy=True)

    assert len(quadro) == 251
    assert list(quadro.columns) == [
        "series_id",
        "date",
        "value",
        "source",
        "freq",
        "vintage",
        "unit",
        "collected_at",
    ]
    assert quadro["series_id"].unique().tolist() == ["YAHOO_GSPC"]
    assert quadro["source"].unique().tolist() == ["YAHOO"]
    assert quadro["freq"].unique().tolist() == ["D"]
    assert quadro["unit"].unique().tolist() == ["index"]
    assert quadro["value"].isna().sum() == 0
    assert quadro["date"].is_monotonic_increasing
    assert not quadro["date"].duplicated().any()


def test_vintage_e_a_data_do_collected_at_e_e_constante(gspc: bytes) -> None:
    """D-b: `vintage` = a data (sem hora) de `collected_at`; PK `(series_id, date, vintage)`."""
    quadro = _quadro_gspc(gspc)
    assert (quadro["vintage"] == quadro["vintage"].iloc[0]).all(), "vintage tem de ser constante"
    assert quadro["vintage"].iloc[0] == pd.Timestamp(COLETA.date())
    assert (quadro["vintage"] == quadro["vintage"].dt.normalize()).all(), "vintage não tem hora"
    assert quadro["date"].max() == pd.Timestamp("2006-12-29")
    assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any()


def test_timestamp_utc_vira_data_de_pregao_pelo_fuso_da_bolsa(gspc: bytes) -> None:
    """`timestamp + meta.gmtoffset` → data de pregão; UTC puro acertaria por acidente.

    O primeiro ponto da fixture é `1136298600` = 2006-01-03 **14:30 UTC** (9h30 em Nova York).
    Com o offset da praça (`-18000` em janeiro, EST) a data é 2006-01-03, e é a data que entra na
    série — nunca a do relógio de quem roda o extrator.
    """
    corpo = json.loads(gspc.decode("utf-8"))
    resultado = corpo["chart"]["result"][0]
    primeiro = resultado["timestamp"][0]
    assert datetime.fromtimestamp(primeiro, tz=UTC) == datetime(2006, 1, 3, 14, 30, tzinfo=UTC)

    quadro = _quadro_gspc(gspc)
    assert quadro["date"].min() == pd.Timestamp("2006-01-03")
    assert quadro["date"].max() == pd.Timestamp("2006-12-29")

    # Uma praça a leste de Greenwich: 23h00 UTC de 02/01 é pregão de 03/01 em Tóquio (+09:00).
    assert datas_de_pregao([1136242800], gmtoffset=32400) == [date(2006, 1, 3)]
    assert datas_de_pregao([1136242800], gmtoffset=0) == [date(2006, 1, 2)]


def test_valor_canario_do_gspc_confere_com_a_fonte(gspc: bytes) -> None:
    """31/01/2006 = 1280,079956, reconferido contra `interval=1mo` na rodada ao vivo."""
    quadro = _quadro_gspc(gspc)
    conferido = conferir_canario(quadro, chave="GSPC", origem="fixture")
    assert conferido == VALORES_CANARIO["GSPC"]
    valor = quadro.loc[quadro["date"] == pd.Timestamp("2006-01-31"), "value"].to_numpy()[0]
    assert valor == pytest.approx(1280.0799560546875, abs=1e-10)


def test_canario_divergente_levanta(gspc: bytes) -> None:
    """Endpoint não documentado que muda de série é pego pelo canário, não descoberto no slide."""
    quadro = _quadro_gspc(gspc)
    adulterado = quadro.copy()
    adulterado.loc[adulterado["date"] == pd.Timestamp("2006-01-31"), "value"] = 1.0
    with pytest.raises(SerieInconsistente, match="valor-can"):
        conferir_canario(adulterado, chave="GSPC", origem="fixture")


def test_cobertura_de_1t2006_na_fixture(gspc: bytes) -> None:
    """A janela 2006-01-01..2006-03-31 tem 62 pregões — o 1T2006 que o projeto exige."""
    quadro = _quadro_gspc(gspc)
    t1 = quadro[
        (quadro["date"] >= pd.Timestamp("2006-01-01"))
        & (quadro["date"] <= pd.Timestamp("2006-03-31"))
    ]
    assert len(t1) == 62
    assert t1["date"].min() == pd.Timestamp("2006-01-03")
    assert t1["date"].max() == pd.Timestamp("2006-03-31")


# ─────────────────────────────────────────────────────────────────────────────
# Caminhos de erro (R1, R2) — fixtura de erro obrigatória (CA-124)
# ─────────────────────────────────────────────────────────────────────────────


def test_corpo_de_erro_404_e_recusado_pelo_parser(dir_yahoo: Path) -> None:
    """`chart.result=null` + `chart.error` preenchido nunca vira série (Anti-SPEC §10.1.5)."""
    conteudo = (dir_yahoo / FIXTURA_ERRO_404).read_bytes()
    assert b"symbol may be delisted" in conteudo
    with pytest.raises(RespostaDeErroComStatus200, match="chart.error"):
        parse_chart(conteudo, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None)


def test_corpo_429_nao_e_json_e_e_recusado_pelos_magic_bytes(dir_yahoo: Path) -> None:
    """`Edge: Too Many Requests` é texto puro: o leitor decide por magic bytes, não por URL."""
    conteudo = (dir_yahoo / FIXTURA_ERRO_429).read_bytes()
    with pytest.raises(FormatoInesperado, match="texto"):
        parse_chart(conteudo, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None)


def test_http_200_com_um_ponto_e_rejeitado_pela_contagem_minima(dir_yahoo: Path) -> None:
    """A armadilha do catálogo: `SMLL.SA` responde 200, com quote válido e **1** ponto (R2).

    Sem `contagem_minima_esperada` isso grava uma série de 1 linha e o pipeline segue adiante.
    """
    conteudo = (dir_yahoo / FIXTURA_UM_PONTO).read_bytes()
    corpo = json.loads(conteudo.decode("utf-8"))
    resultado = corpo["chart"]["result"][0]
    assert corpo["chart"]["error"] is None
    assert len(resultado["timestamp"]) == 1
    assert resultado["meta"]["symbol"] == "SMLL.SA"
    assert resultado["meta"]["firstTradeDate"] is None
    assert len(resultado["indicators"]["quote"][0]["close"]) == 1

    # `SMLL.SA` está `descartada` no catálogo e por isso não tem chave neste extrator. Para que a
    # guarda seja exercitada sobre este corpo real, o símbolo é apontado para o ticker suportado:
    # é exatamente o cenário "pedi 20 anos de ^GSPC e a fonte devolveu 1 ponto com HTTP 200".
    resultado["meta"]["symbol"] = "^GSPC"
    resultado["meta"]["currency"] = "USD"
    with pytest.raises(RespostaTruncada, match="truncamento"):
        parse_chart(
            json.dumps(corpo).encode("utf-8"),
            chave="GSPC",
            origem="fixture",
            collected_at=COLETA,
        )


def test_piso_do_contrato_recusa_a_fixtura_recortada(gspc: bytes) -> None:
    """A fixture é 1 ano; o contrato exige 5.729 pontos. Rodar com o piso real levanta."""
    assert FECHAMENTOS_MINIMOS["GSPC"] == 5729
    with pytest.raises(RespostaTruncada):
        parse_chart(gspc, chave="GSPC", origem="fixture", collected_at=COLETA)


def test_ticker_trocado_pela_fonte_levanta(gspc: bytes) -> None:
    """`meta.symbol` diferente do pedido: o `series_id` descreveria outra série."""
    with pytest.raises(SerieInconsistente, match="meta.symbol"):
        parse_chart(gspc, chave="VIX", origem="fixture", collected_at=COLETA, minimo=None)


def test_moeda_trocada_levanta(gspc: bytes) -> None:
    """Mudança de moeda é erro de escala silencioso, não detalhe de metadado."""
    corpo = json.loads(gspc.decode("utf-8"))
    corpo["chart"]["result"][0]["meta"]["currency"] = "BRL"
    adulterado = json.dumps(corpo).encode("utf-8")
    with pytest.raises(SerieInconsistente, match="meta.currency"):
        parse_chart(adulterado, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None)


def test_vetores_desalinhados_levantam(gspc: bytes) -> None:
    """Menos `close` que `timestamp` deslocaria a data de cada ponto."""
    corpo = json.loads(gspc.decode("utf-8"))
    corpo["chart"]["result"][0]["indicators"]["quote"][0]["close"].pop()
    corpo["chart"]["result"][0]["indicators"].pop("adjclose", None)
    adulterado = json.dumps(corpo).encode("utf-8")
    with pytest.raises(SerieInconsistente, match="desalinhados"):
        parse_chart(adulterado, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None)


def test_fechamento_nulo_vira_none_e_nunca_zero(gspc: bytes) -> None:
    """Ausência é `None` (Anti-SPEC §10.1.4) — o `DX-Y.NYB` real tem 17% de nulos."""
    corpo = json.loads(gspc.decode("utf-8"))
    corpo["chart"]["result"][0]["indicators"]["quote"][0]["close"][5] = None
    corpo["chart"]["result"][0]["indicators"].pop("adjclose", None)
    adulterado = json.dumps(corpo).encode("utf-8")
    quadro = parse_chart(
        adulterado, chave="GSPC", origem="fixture", collected_at=COLETA, minimo=None
    )
    assert quadro["value"].isna().sum() == 1
    assert (quadro["value"].dropna() > 0).all()
    assert quadro["value"].iloc[5] != 0


def test_data_futura_levanta(gspc: bytes) -> None:
    """`date > collected_at` é o que `RawSeriesSchema.sem_data_futura` proíbe."""
    with pytest.raises(SerieInconsistente, match="data futura"):
        parse_chart(
            gspc,
            chave="GSPC",
            origem="fixture",
            collected_at=datetime(2006, 6, 1, tzinfo=UTC),
            minimo=None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Anti-SPEC §10.2.12 — price return × total return
# ─────────────────────────────────────────────────────────────────────────────


def test_adjclose_diferente_de_close_levanta(dir_yahoo: Path) -> None:
    """ETF com provento: a resposta real do `IVV` dá 126,83 em `close` e 86,78 em `adjclose`.

    Gravar `close` ali e comparar com IMA-B/IFIX (retorno total) é exatamente o que a
    Anti-SPEC §10.2.12 proíbe. O parser levanta em vez de produzir a série.
    """
    conteudo = (dir_yahoo / FIXTURA_IVV).read_bytes()
    corpo = json.loads(conteudo.decode("utf-8"))
    resultado = corpo["chart"]["result"][0]
    close = resultado["indicators"]["quote"][0]["close"]
    adj = resultado["indicators"]["adjclose"][0]["adjclose"]
    assert close[0] == pytest.approx(126.83000183105469)
    assert adj[0] == pytest.approx(86.78004455566406)
    assert close != adj

    # Mesmo renomeando o símbolo para um ticker suportado, a guarda de provento barra.
    resultado["meta"]["symbol"] = "^GSPC"
    with pytest.raises(SerieInconsistente, match="adjclose difere de close"):
        parse_chart(
            json.dumps(corpo).encode("utf-8"),
            chave="GSPC",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_adjclose_igual_a_close_passa_no_gspc(gspc: bytes) -> None:
    """Índice não paga provento: nos dados reais do `^GSPC` os dois vetores são idênticos."""
    corpo = json.loads(gspc.decode("utf-8"))
    indicadores = corpo["chart"]["result"][0]["indicators"]
    assert indicadores["adjclose"][0]["adjclose"] == indicadores["quote"][0]["close"]
    assert len(_quadro_gspc(gspc)) == 251


# ─────────────────────────────────────────────────────────────────────────────
# CA-047 — conversão a BRL pela PTAX do mesmo dia útil
# ─────────────────────────────────────────────────────────────────────────────


def test_ca047_conversao_usa_a_ptax_do_mesmo_dia_util(gspc: bytes) -> None:
    """`nivel_brl = nivel_usd * ptax(mesmo dia)` — ponto a ponto, nunca por subtração."""
    quadro = _quadro_gspc(gspc)
    ptax = pd.DataFrame(
        {
            "date": quadro["date"],
            # PTAX sintética que varia no tempo: se a conversão usasse um câmbio só, ou o do dia
            # errado, o teste não distinguiria nada.
            "ptax": [2.0 + i / 1000 for i in range(len(quadro))],
        }
    )
    conversao = converter_para_brl(
        quadro,
        series_id_destino="SP500_BRL",
        ptax=ptax,
        is_total_return=False,
        origem="teste",
    )
    assert conversao.linhas == 251
    assert conversao.dias_sem_ptax == 0
    assert conversao.is_total_return is False

    esperado = quadro["value"].to_numpy() * ptax["ptax"].to_numpy()
    assert conversao.quadro["value"].to_numpy() == pytest.approx(esperado, rel=1e-12)
    assert conversao.quadro["series_id"].unique().tolist() == ["SP500_BRL"]
    assert conversao.quadro["source"].unique().tolist() == ["DERIVADO"]
    ProcessedSeriesSchema.validate(conversao.quadro, lazy=True)


def test_ca047_dia_sem_ptax_sai_da_serie_sem_ffill_nem_zero(gspc: bytes) -> None:
    """Feriado brasileiro com pregão americano **sai**; não herda o câmbio de ontem (§10.1.1)."""
    quadro = _quadro_gspc(gspc)
    sem_feriado = quadro.loc[quadro["date"] != pd.Timestamp("2006-02-27")]
    ptax = _ptax_sintetica(sem_feriado["date"], valor=2.2)

    conversao = converter_para_brl(
        quadro, series_id_destino="SP500_BRL", ptax=ptax, is_total_return=False
    )
    assert conversao.dias_sem_ptax == 1
    assert conversao.linhas == 250
    assert pd.Timestamp("2006-02-27") not in set(conversao.quadro["date"])
    assert conversao.quadro["value"].isna().sum() == 0
    assert (conversao.quadro["value"] > 0).all()


def test_ca047_price_return_sem_flag_falha(gspc: bytes) -> None:
    """`is_total_return=None` levanta: série internacional sem a flag não entra no heatmap."""
    quadro = _quadro_gspc(gspc)
    ptax = _ptax_sintetica(quadro["date"])
    with pytest.raises(SerieInconsistente, match="is_total_return"):
        converter_para_brl(quadro, series_id_destino="SP500_BRL", ptax=ptax, is_total_return=None)


def test_ca047_janelas_disjuntas_levantam(gspc: bytes) -> None:
    """Nenhum dia em comum com a PTAX é falha, não série vazia gravada em silêncio."""
    quadro = _quadro_gspc(gspc)
    ptax = _ptax_sintetica(pd.Series(pd.to_datetime(["2030-01-02", "2030-01-03"])))
    with pytest.raises(SerieInconsistente, match="nenhum dia em comum"):
        converter_para_brl(quadro, series_id_destino="SP500_BRL", ptax=ptax, is_total_return=False)


def test_series_brl_declaram_a_flag_no_catalogo() -> None:
    """A flag de CA-047 vive no catálogo (o schema processado tem 8 colunas, sem espaço pra ela)."""
    catalogo = {e.series_id: e for e in load_catalog()}
    assert catalogo["SP500_BRL"].is_total_return is False
    assert catalogo["SP500_BRL"].fonte.value == "DERIVADO"
    assert catalogo["ACWI_BRL"].is_total_return is True
    assert set(SERIES_BRL.values()) == {"SP500_BRL"}


def test_ptax_ausente_nao_produz_serie_em_brl_e_nao_estima_cambio(tmp_path: Path) -> None:
    """Sem `data/processed/sgs/BCB_SGS_1.parquet` a série em BRL simplesmente não sai."""
    from apps.pipeline.common import ErroDeExtracao

    with pytest.raises(ErroDeExtracao, match="PTAX não encontrada"):
        carregar_ptax(raiz=tmp_path)
    assert yahoo._gravar_brl(pd.DataFrame(), chave="GSPC", raiz=tmp_path, gravar=False) is None


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo, contrato e idempotência
# ─────────────────────────────────────────────────────────────────────────────


def test_tickers_vem_do_catalogo_e_nenhum_e_descartado() -> None:
    """`series_id` e `identificador` são do catálogo; nada aqui é inventado (CA-053)."""
    catalogo = {e.series_id: e for e in load_catalog()}
    for chave, ticker in TICKERS.items():
        entrada = catalogo[series_id_de(chave)]
        assert entrada.identificador == ticker
        assert entrada.status.value == "ok", f"{chave} nao deveria estar em TICKERS"
        assert entrada.fonte.value == "YAHOO"
        assert entrada.freq.value == "D"
    assert set(TICKERS_PADRAO) <= set(TICKERS_SUPORTADOS)
    assert "ACWI" not in TICKERS, "ETF ACWI nao cobre 2006 (descartada no catalogo)"


def test_config_declara_as_guardas_do_contrato() -> None:
    """Sem UA obrigatório e sem piso de contagem, as duas pegadinhas da fonte passam."""
    for chave in TICKERS_SUPORTADOS:
        config = config_do_ticker(chave)
        assert config.requer_user_agent_browser is True
        assert config.contagem_minima_esperada == FECHAMENTOS_MINIMOS[chave]
        assert config.valor_canario == VALORES_CANARIO[chave]
        assert config.destino_raw == "data/raw/yahoo"
        assert config.formato == "json"
        assert config.encoding == "utf-8"
        assert config.janela_maxima_dias is None
        assert TICKERS[chave] in config.base_url
        assert MOEDA_ESPERADA[chave] in {"USD", "BRL"}


def test_ticker_nao_suportado_levanta() -> None:
    from apps.pipeline.common import ErroDeExtracao

    with pytest.raises(ErroDeExtracao, match="não suportado"):
        config_do_ticker("PETR4")


def test_extracao_arquiva_bruto_e_grava_processado(gspc: bytes, tmp_path: Path) -> None:
    """Fluxo completo com transporte falso: bruto com manifesto + parquet validado."""
    transporte = TransporteGravado(
        RespostaBruta(
            url="https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC",
            status=200,
            conteudo=gspc,
            cabecalhos={"Content-Type": "application/json"},
            obtida_em=COLETA,
        )
    )
    resultado = extrair_ticker(
        "GSPC", transporte=transporte, raiz=tmp_path, com_brl=False, minimo=None
    )
    assert resultado.linhas == 251
    assert resultado.data_inicio == date(2006, 1, 3)
    assert resultado.data_fim == date(2006, 12, 29)
    assert resultado.sha256_raw == sha256_de(gspc)
    assert resultado.raw_idempotente is False

    bruto = tmp_path / "data" / "raw" / "yahoo" / "^GSPC__2006-12-29.json"
    assert bruto.is_file()
    assert bruto.with_name(bruto.name + ".meta.json").is_file()

    processado = caminho_processed("yahoo/YAHOO_GSPC.parquet", raiz=tmp_path)
    assert processado.is_file()
    ProcessedSeriesSchema.validate(pd.read_parquet(processado), lazy=True)


def test_segunda_rodada_com_bytes_diferentes_mas_serie_igual_mantem_o_retrato(
    gspc: bytes, tmp_path: Path
) -> None:
    """Pegadinha nº 6: a fonte alterna a ordem das chaves de `meta.currentTradingPeriod`.

    Bytes diferentes com `(date, value)` idêntico **não** é revisão: o retrato original é mantido
    e a rodada é idempotente.
    """
    corpo = json.loads(gspc.decode("utf-8"))
    periodo = corpo["chart"]["result"][0]["meta"].get("currentTradingPeriod")
    assert periodo is not None, "a fixture precisa ter o campo volatil para o teste valer"
    reordenado = json.dumps(corpo, sort_keys=True).encode("utf-8")
    assert reordenado != gspc
    assert json.loads(reordenado.decode("utf-8")) == corpo

    primeiro = extrair_ticker(
        "GSPC",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    segundo = extrair_ticker(
        "GSPC",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=reordenado, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    assert segundo.raw_idempotente is True
    assert segundo.sha256_raw == primeiro.sha256_raw == sha256_de(gspc)


def test_segunda_rodada_com_valor_revisado_levanta(gspc: bytes, tmp_path: Path) -> None:
    """Revisão retroativa de verdade continua batendo em `ConteudoDivergente` (R8)."""
    extrair_ticker(
        "GSPC",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    corpo = json.loads(gspc.decode("utf-8"))
    corpo["chart"]["result"][0]["indicators"]["quote"][0]["close"][10] = 1.0
    corpo["chart"]["result"][0]["indicators"].pop("adjclose", None)
    with pytest.raises(ConteudoDivergente):
        extrair_ticker(
            "GSPC",
            transporte=TransporteGravado(
                RespostaBruta(
                    url="https://x",
                    status=200,
                    conteudo=json.dumps(corpo).encode("utf-8"),
                    obtida_em=COLETA,
                )
            ),
            raiz=tmp_path,
            com_brl=False,
            minimo=None,
        )


def test_modo_offline_reprocessa_sem_rede(gspc: bytes, tmp_path: Path) -> None:
    """`--offline` relê `data/raw/` e regrava o processado, sem transporte nenhum."""
    extrair_ticker(
        "GSPC",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    offline = extrair_ticker_offline("GSPC", raiz=tmp_path, com_brl=False, minimo=None)
    assert offline.linhas == 251
    assert offline.raw_idempotente is True
    assert offline.sha256_raw == sha256_de(gspc)


def test_db_offline_tira_o_vintage_do_manifesto_e_e_idempotente(
    gspc: bytes, tmp_path: Path
) -> None:
    """D-b: duas rodadas `--offline` sobre o mesmo bruto dão o mesmo Parquet e o mesmo `vintage`.

    O `vintage` sai do `obtido_em` do manifesto; se saísse do relógio, cada reprocessamento
    criaria uma safra nova e a PK `(series_id, date, vintage)` duplicaria a série.
    """
    extrair_ticker(
        "GSPC",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    hashes = set()
    for _ in range(2):
        offline = extrair_ticker_offline("GSPC", raiz=tmp_path, com_brl=False, minimo=None)
        assert offline.caminho_processed is not None
        quadro = pd.read_parquet(offline.caminho_processed)
        assert (quadro["vintage"] == pd.Timestamp(COLETA.date())).all()
        hashes.add(sha256_de(offline.caminho_processed.read_bytes()))
    assert len(hashes) == 1


def test_dc_offline_ignora_o_manifesto_no_glob(gspc: bytes, tmp_path: Path) -> None:
    """D-c: `^GSPC__2026-10-09.json.meta.json` casa com `^GSPC__*.json` e ordena **depois**."""
    extrair_ticker(
        "GSPC",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=gspc, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    pasta = tmp_path / "data" / "raw" / "yahoo"
    nomes = sorted(a.name for a in pasta.iterdir())
    assert len(nomes) == 2 and nomes[1].endswith(".json.meta.json")
    offline = extrair_ticker_offline("GSPC", raiz=tmp_path, com_brl=False, minimo=None)
    assert offline.caminho_raw is not None
    assert offline.caminho_raw.name == nomes[0]


def test_offline_sem_bruto_levanta(tmp_path: Path) -> None:
    from apps.pipeline.common import ErroDeExtracao

    with pytest.raises(ErroDeExtracao, match="modo offline"):
        extrair_ticker_offline("GSPC", raiz=tmp_path)


def test_linha_de_evidencia_e_ascii(gspc: bytes) -> None:
    """A saída da CLI é ASCII: o `stdout` do Windows é cp1252 e `print` de seta Unicode quebra."""
    quadro = _quadro_gspc(gspc)
    linha = yahoo._resultado(
        quadro,
        chave="GSPC",
        canario=VALORES_CANARIO["GSPC"],
        sha256_raw="0" * 64,
        bytes_raw=1,
        caminho_raw=None,
        raw_idempotente=False,
        caminho_processed_=None,
    ).resumo()
    assert linha.isascii(), linha
    assert "YAHOO_GSPC" in linha
    assert "2006-01-03 -> 2006-12-29" in linha


def test_inicio_padrao_da_janela_cobre_2006_com_folga() -> None:
    """A janela pedida começa em 2004 para que a variação de 12 meses do 1T2006 exista."""
    assert INICIO_PADRAO.isoformat() == "2004-01-01"
    assert INICIO_PADRAO.year < 2006


# ─────────────────────────────────────────────────────────────────────────────
# Fonte viva — fora do CI N1
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_fonte_viva_gspc_tras_o_canario_e_o_historico_completo(tmp_path: Path) -> None:
    """Confere a fixture contra a fonte real: canário, piso de contagem e cobertura de 2006."""
    resultado = extrair_ticker("GSPC", raiz=tmp_path, gravar=False, com_brl=False)
    assert resultado.data_inicio <= date(2004, 1, 2)
    assert resultado.data_fim >= date(2026, 10, 9)
    assert resultado.linhas >= FECHAMENTOS_MINIMOS["GSPC"]
    assert resultado.canario == VALORES_CANARIO["GSPC"]
    assert resultado.pct_nulos_value == 0.0
