"""Extrator Yahoo Finance `chart/v8` — `^GSPC` e o plano B do FRED (F-007, SPEC RF-016/RF-017).

Fonte: `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1=&period2=&interval=1d`
— grátis, sem chave, **não documentada** (`docs/research/fontes-de-dados.md §C10.2-C10.3`). É a rota
do S&P 500 porque o FRED `SP500` é janela rolante de 10 anos (L11, Anti-SPEC §10.1.3) e porque o
FRED está **bloqueado nesta máquina** (`skills-manifest.md §3`): `DGS10`→`^TNX`, `VIXCLS`→`^VIX`,
`DTWEXBGS`→`DX-Y.NYB` (S-09 no `DECISIONS_LOG`).

Caminho: `ClienteHTTP` → parse → `arquivar_bruto` (`data/raw/yahoo/`, idempotente, com manifesto) →
`gravar_processado_parquet` (`data/processed/yahoo/<series_id>.parquet`), na **frequência nativa
diária** e na **moeda original** da fonte (Anti-SPEC §10.4.28: trimestral e BRL são derivações).

As cinco pegadinhas medidas desta fonte, e onde cada uma é tratada:

1. **Sem `User-Agent` de browser a resposta é HTTP 429** `Edge: Too Many Requests` (CA-045, R4).
   Quem garante o UA é o `ClienteHTTP` (`requer_user_agent_browser=True`): ele **levanta** antes de
   despachar uma requisição sem UA, e 429 entra no retry com backoff.
2. **`range=max` trunca em silêncio.** Medido em 2026-10-10: `^GSPC` com `range=max&interval=1mo`
   devolve **169** pontos; com `period1`/`period2` em epoch, **490**. Nenhuma função deste módulo
   emite `range` — só `period1`/`period2` (CA-045, R2). Há teste que varre os parâmetros.
3. **Ticker inexistente ou sem histórico devolve HTTP 200 com UM ponto** (o do dia), não erro:
   é o caso de `SMLL.SA` registrado no catálogo. A guarda é `contagem_minima_esperada` sobre o
   número de fechamentos **não nulos** (R2, Anti-SPEC §10.1.1).
4. **`timestamp` é epoch UTC do pregão, não a data.** A data de pregão sai de
   `timestamp + meta.gmtoffset`, que é o fuso da bolsa (`America/New_York` no `^GSPC`,
   `America/Sao_Paulo` no `^BVSP`) — converter em UTC puro acerta por acidente nestes tickers e
   erra em qualquer praça a leste de Greenwich.
5. **`adjclose` ≠ `close` significa provento.** Para índice (`^GSPC`, `^VIX`, `DX-Y.NYB`) os dois
   vetores são idênticos — conferido byte a byte na rodada ao vivo — e o `close` é o nível de
   **price return**. Num ETF (`IVV`: 126,83 contra 86,78 em 03/01/2006) eles divergem, e usar
   `close` ali subestimaria o retorno total. O parser **levanta** quando divergem, em vez de
   gravar série que depois seria comparada com o IMA-B (Anti-SPEC §10.2.12).
6. **A resposta não é byte-estável, mesmo com a série idêntica.** Medido em 2026-10-10: três GETs
   seguidos do `^GSPC` com os mesmos parâmetros deram `sha256` `d37691c48436`, `d37691c48436` e
   `9a4193bcbc4c` — 615.027 bytes nos três, `timestamp` e `close` idênticos, e o primeiro byte
   divergente dentro de `meta.currentTradingPeriod.pre`, onde a fonte alterna a ordem das chaves
   `start`/`end`. A idempotência (CA-027) por isso é verificada **na série**, não nos bytes:
   `_arquivar_retrato` mantém o retrato já arquivado quando a série reparseada é igual, e só
   relevanta `ConteudoDivergente` quando algum `(date, value)` mudou de fato — que é a revisão
   que R8 manda não apagar.

Uso:

```bash
uv run python -m apps.pipeline.extract.yahoo                       # GSPC TNX VIX DXY, ao vivo
uv run python -m apps.pipeline.extract.yahoo --tickers GSPC        # só o S&P 500
uv run python -m apps.pipeline.extract.yahoo --offline             # relê data/raw, sem rede
```
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pandas as pd

from apps.pipeline.common import (
    DO_CONTRATO,
    SUFIXO_MANIFESTO,
    ClienteHTTP,
    ConteudoDivergente,
    ErroDeExtracao,
    FormatoDetectado,
    RespostaDeErroComStatus200,
    ResultadoArquivamento,
    SerieInconsistente,
    arquivar_bruto,
    caminho_destino_raw,
    collected_at_do_bruto,
    configurar_logging,
    exigir_contagem_minima,
    exigir_formato,
    gravar_processado_parquet,
    ler_texto,
    nome_arquivo_raw,
    obter_logger,
    para_float_ponto_decimal,
    sha256_de,
)
from apps.pipeline.transform import carregar_ptax, converter_para_brl
from packages.shared.schemas import ExtractorConfig, Fonte, Freq, load_catalog

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from apps.pipeline.common import Transporte
    from packages.shared.schemas import SeriesCatalogEntry

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Catálogo local: tickers, janela e pisos de contagem
# ─────────────────────────────────────────────────────────────────────────────

URL_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

#: `chave do extrator -> ticker na fonte`. A chave é o sufixo do `series_id` do catálogo
#: (`GSPC` → `YAHOO_GSPC`); o ticker é o `identificador`, conferido contra o catálogo na
#: importação deste módulo. Só entram séries com `status = ok`: `ACWI`, `URTH`, `IVVB11`,
#: `XFIX11` e `SETORIAIS_B3_SA` estão `descartada` no catálogo (não cobrem 2006 ou devolvem
#: 1 ponto) e por isso **não** têm chave aqui.
TICKERS: dict[str, str] = {
    "GSPC": "^GSPC",
    "TNX": "^TNX",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "BRLX": "BRL=X",
    "BVSP": "^BVSP",
}

#: O que a CLI extrai por default: o `^GSPC` do item **C1** (RF-016) mais os três substitutos do
#: FRED que a conectividade desta máquina obriga (RF-017 / S-09). `^FVX` e `^IRX`, citados na
#: pesquisa §C10.3 como plano B de `DGS2`/`DGS5`, **não estão no catálogo** — entram quando F-011
#: acrescentar a entrada, não por hard-code aqui.
TICKERS_PADRAO: tuple[str, ...] = ("GSPC", "TNX", "VIX", "DXY")

#: Tudo que este módulo sabe baixar. `BRLX` e `BVSP` são **cross-check** (a primária do câmbio é a
#: PTAX do SGS 1/10813, F-003; a do Ibovespa é a API da B3, F-006), e ficam fora do default.
TICKERS_SUPORTADOS: tuple[str, ...] = tuple(TICKERS)

#: Janela pedida à fonte. 2004-01-01 dá dois anos de folga antes de 2006-01 (a variação de 12
#: meses do 1T2006 precisa de 2005) e casa com a janela que F-003 usou na PTAX, o que mantém a
#: conversão a BRL sem borda. `fim` é resolvido para "hoje" em tempo de execução.
INICIO_PADRAO = date(2004, 1, 1)

#: Piso anti-truncamento (R2): fechamentos **não nulos** medidos ao vivo em 2026-10-10 na janela
#: `INICIO_PADRAO -> 2026-10-10`. A série só cresce; vir menos é truncamento, ticker trocado ou a
#: armadilha do "HTTP 200 com 1 ponto".
FECHAMENTOS_MINIMOS: dict[str, int] = {
    "GSPC": 5729,
    "TNX": 5724,
    "VIX": 5731,
    "DXY": 5742,
    "BRLX": 5491,
    "BVSP": 5643,
}

#: `(data ISO, fechamento)` conferido em 2026-10-10 contra **outra superfície da fonte**
#: (`interval=1mo`, requisição e payload distintos do diário) para `GSPC`; para os demais, contra
#: o próprio fechamento do último pregão de janeiro/2006.
VALORES_CANARIO: dict[str, tuple[str, float]] = {
    "GSPC": ("2006-01-31", 1280.0799560546875),
    "TNX": ("2006-01-31", 4.5269999504089355),
    "VIX": ("2006-01-31", 12.949999809265137),
    "DXY": ("2006-01-31", 88.95999908447266),
    "BRLX": ("2006-03-31", 2.1672000885009766),
    "BVSP": ("2006-01-31", 38383.0),
}

#: Moeda que a fonte declara em `meta.currency`. Guarda de escala: `^BVSP` em `USD` ou `^GSPC` em
#: `BRL` significa que a fonte trocou o ticker por baixo, e aí a série não é a que se pediu.
MOEDA_ESPERADA: dict[str, str] = {
    "GSPC": "USD",
    "TNX": "USD",
    "VIX": "USD",
    "DXY": "USD",
    "BRLX": "BRL",
    "BVSP": "BRL",
}

DESTINO_RAW = "data/raw/yahoo"
SUBPASTA_PROCESSED = "yahoo"
EXTENSAO_RAW = "json"
INTERVALO_DIARIO = "1d"
ENCODING = "utf-8"

#: Pausa entre tickers. A fonte não publica rate limit; 429 é o modo de falha dela (R4) e o retry
#: com backoff do `ClienteHTTP` é a rede de segurança, não a estratégia.
PAUSA_ENTRE_TICKERS_S = 1.0

#: Nomes de parâmetro **proibidos** na querystring: `range` trunca séries longas em silêncio
#: (169 contra 490 pontos no `^GSPC` mensal, medido em 2026-10-10). CA-045 / R2.
PARAMETROS_PROIBIDOS: frozenset[str] = frozenset({"range"})


def series_id_de(chave: str) -> str:
    """`YAHOO_GSPC` — o `series_id` do catálogo, derivado da chave e nunca do `meta.symbol`."""
    return f"YAHOO_{chave}"


def _catalogo_yahoo() -> dict[str, SeriesCatalogEntry]:
    """Entradas do catálogo das chaves suportadas, conferidas na importação do módulo.

    Falha ruidosamente se uma chave daqui não existir no catálogo ou se o `identificador` lá não
    for o ticker daqui: o catálogo é a fonte de verdade de `series_id`, `unit` e `data_inicio`;
    este módulo só sabe o layout da resposta.
    """
    catalogo = {e.series_id: e for e in load_catalog()}
    resolvido: dict[str, SeriesCatalogEntry] = {}
    for chave, ticker in TICKERS.items():
        entrada = catalogo.get(series_id_de(chave))
        if entrada is None:
            msg = (
                f"{series_id_de(chave)} não está em packages/shared/schemas/series_catalog_data.py"
            )
            raise ErroDeExtracao(msg)
        if entrada.identificador != ticker:
            msg = (
                f"{entrada.series_id}: catálogo diz identificador={entrada.identificador!r}, "
                f"o extrator usa {ticker!r}"
            )
            raise ErroDeExtracao(msg)
        resolvido[chave] = entrada
    return resolvido


CATALOGO: dict[str, SeriesCatalogEntry] = _catalogo_yahoo()


def entrada_do_ticker(chave: str) -> SeriesCatalogEntry:
    """Entrada do catálogo da chave — de onde saem `unit`, `data_inicio` e `is_total_return`."""
    if chave not in CATALOGO:
        msg = f"ticker {chave!r} não suportado; use um de {list(TICKERS_SUPORTADOS)}"
        raise ErroDeExtracao(msg)
    return CATALOGO[chave]


def entrada_do_catalogo(series_id: str) -> SeriesCatalogEntry:
    """Qualquer entrada do catálogo por `series_id` — usada pelas séries derivadas em BRL."""
    for entrada in load_catalog():
        if entrada.series_id == series_id:
            return entrada
    msg = f"{series_id} não está em packages/shared/schemas/series_catalog_data.py"
    raise ErroDeExtracao(msg)


def config_do_ticker(chave: str) -> ExtractorConfig:
    """`ExtractorConfig` do ticker: o contrato é a configuração, nada aqui é hard-code solto."""
    entrada = entrada_do_ticker(chave)
    return ExtractorConfig(
        nome=f"yahoo_{chave.lower()}",
        fonte=Fonte.YAHOO,
        series_ids=(entrada.series_id,),
        base_url=URL_CHART.format(ticker=TICKERS[chave]),
        formato="json",
        encoding=ENCODING,
        # CA-045: a diferença entre HTTP 200 e HTTP 429 nesta fonte é o User-Agent.
        requer_user_agent_browser=True,
        janela_maxima_dias=None,  # a fonte serve 20 anos de diário num GET só
        contagem_minima_esperada=FECHAMENTOS_MINIMOS[chave],
        valor_canario=VALORES_CANARIO[chave],
        destino_raw=DESTINO_RAW,
        timeout_s=120.0,  # ~600 KB por ticker
    )


# ─────────────────────────────────────────────────────────────────────────────
# Janela (CA-045: period1/period2, nunca range)
# ─────────────────────────────────────────────────────────────────────────────


def epoch_utc(dia: date) -> int:
    """Meia-noite UTC do dia, em epoch seconds — a unidade de `period1`/`period2`."""
    return calendar.timegm(dia.timetuple())


def parametros_janela(
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    *,
    intervalo: str = INTERVALO_DIARIO,
) -> dict[str, Any]:
    """Querystring da janela: `period1`/`period2` em epoch, **nunca** `range` (CA-045, R2).

    `period2` é exclusivo na prática (é a meia-noite do dia seguinte a `fim`), então o dia `fim`
    entra inteiro. `fim=None` resolve para hoje em UTC.
    """
    termino = fim or datetime.now(tz=UTC).date()
    if termino < inicio:
        msg = f"janela invertida: inicio={inicio.isoformat()} > fim={termino.isoformat()}"
        raise ValueError(msg)
    return {
        "period1": epoch_utc(inicio),
        "period2": epoch_utc(termino + timedelta(days=1)),
        "interval": intervalo,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parse
# ─────────────────────────────────────────────────────────────────────────────


def _corpo_json(conteudo: bytes, *, origem: str) -> dict[str, Any]:
    """Bytes → `dict`, recusando corpo vazio, HTML, texto e array (R1, Anti-SPEC §10.1.5).

    `ClienteHTTP.json_array` não serve aqui: a resposta do `chart/v8` é um **objeto**
    (`{"chart": {...}}`) e o corpo de erro vem com `chart.error` preenchido, não com a chave
    `error` no topo que `validar_corpo_json_array` reconhece.
    """
    exigir_formato(conteudo, FormatoDetectado.JSON, origem=origem)
    try:
        corpo = json.loads(ler_texto(conteudo, ENCODING))
    except json.JSONDecodeError as exc:
        msg = f"{origem}: corpo não é JSON válido ({exc})"
        raise RespostaDeErroComStatus200(msg) from exc
    if not isinstance(corpo, dict):
        msg = f"{origem}: esperado objeto JSON com a chave 'chart', veio {type(corpo).__name__}"
        raise RespostaDeErroComStatus200(msg)
    return corpo


def _resultado_do_chart(corpo: dict[str, Any], *, origem: str) -> dict[str, Any]:
    """`chart.result[0]`, recusando o corpo de erro da fonte."""
    chart = corpo.get("chart")
    if not isinstance(chart, dict):
        msg = f"{origem}: resposta sem a chave 'chart' (chaves vistas: {sorted(corpo)})"
        raise RespostaDeErroComStatus200(msg)
    erro = chart.get("error")
    if erro:
        detalhe = erro if isinstance(erro, str) else json.dumps(erro, ensure_ascii=False)
        msg = f"{origem}: corpo de ERRO da fonte (Anti-SPEC §10.1.5). chart.error={detalhe}"
        raise RespostaDeErroComStatus200(msg)
    resultado = chart.get("result")
    if not isinstance(resultado, list) or not resultado:
        msg = f"{origem}: chart.result vazio ou ausente ({resultado!r}) com chart.error nulo"
        raise RespostaDeErroComStatus200(msg)
    primeiro = resultado[0]
    if not isinstance(primeiro, dict):
        msg = f"{origem}: chart.result[0] não é objeto ({type(primeiro).__name__})"
        raise RespostaDeErroComStatus200(msg)
    return primeiro


def datas_de_pregao(timestamps: Sequence[int], *, gmtoffset: int) -> list[date]:
    """Epoch UTC + offset da bolsa → data de pregão (pegadinha nº 4 do docstring do módulo).

    `meta.gmtoffset` é o deslocamento da praça (`-14400` em `America/New_York`, `-10800` em
    `America/Sao_Paulo`, `+3600` na praça do `BRL=X`). Sem ele, uma bolsa a leste de Greenwich
    cujo pregão abre antes das 00:00 UTC cairia na data errada.
    """
    return [datetime.fromtimestamp(int(ts) + int(gmtoffset), tz=UTC).date() for ts in timestamps]


def _fechamentos(resultado: dict[str, Any], *, origem: str) -> list[Any]:
    """Vetor `close`, com a guarda de provento (`adjclose` ≠ `close` → Anti-SPEC §10.2.12)."""
    indicadores = resultado.get("indicators")
    if not isinstance(indicadores, dict):
        msg = f"{origem}: chart.result[0] sem 'indicators'"
        raise SerieInconsistente(msg)
    cotacoes = indicadores.get("quote")
    if not isinstance(cotacoes, list) or not cotacoes or not isinstance(cotacoes[0], dict):
        msg = f"{origem}: indicators.quote ausente ou vazio"
        raise SerieInconsistente(msg)
    fechamento = cotacoes[0].get("close")
    if not isinstance(fechamento, list):
        msg = f"{origem}: indicators.quote[0].close ausente ou não é lista"
        raise SerieInconsistente(msg)

    ajustado = indicadores.get("adjclose")
    if isinstance(ajustado, list) and ajustado and isinstance(ajustado[0], dict):
        vetor = ajustado[0].get("adjclose")
        if isinstance(vetor, list) and vetor != fechamento:
            msg = (
                f"{origem}: adjclose difere de close — o ticker paga provento, então 'close' é "
                f"price return e comparar essa série com retorno total (IMA-B, IFIX, MSCI NETR) "
                f"viola a Anti-SPEC §10.2.12. Este extrator só serve índice sem provento; para "
                f"retorno total use MSCI NETR (apps/pipeline/extract/msci.py)"
            )
            raise SerieInconsistente(msg)
    return fechamento


def parse_chart(
    conteudo: bytes,
    *,
    chave: str,
    origem: str,
    collected_at: datetime,
    minimo: int | None | object = DO_CONTRATO,
) -> pd.DataFrame:
    """Bytes da resposta `chart/v8` → DataFrame no contrato `ProcessedSeriesSchema`.

    Não grava nada: validar antes de escrever é o que CA-003 pede, e quem escreve é
    `gravar_processado_parquet`. Levanta em vez de devolver série com ticker trocado, moeda
    trocada, série curta (a armadilha do "HTTP 200 com 1 ponto"), data duplicada, fora de ordem
    ou no futuro.

    `minimo` segue o idioma de `ClienteHTTP.json_array`: default = o
    `contagem_minima_esperada` do contrato (fechamentos **não nulos**); `None` desliga a guarda,
    que é o que a fixture — um recorte de 1 ano, limitado a 200 KB — precisa.
    """
    config = config_do_ticker(chave)
    entrada = entrada_do_ticker(chave)
    corpo = _corpo_json(conteudo, origem=origem)
    resultado = _resultado_do_chart(corpo, origem=origem)
    meta = resultado.get("meta")
    if not isinstance(meta, dict):
        msg = f"{origem}: chart.result[0] sem 'meta'"
        raise SerieInconsistente(msg)

    simbolo = str(meta.get("symbol", ""))
    if simbolo != TICKERS[chave]:
        msg = (
            f"{origem}: meta.symbol={simbolo!r}, esperado {TICKERS[chave]!r} — a fonte devolveu "
            f"outro papel; o series_id vem do catálogo e não pode descrever outra série"
        )
        raise SerieInconsistente(msg)
    moeda = str(meta.get("currency", ""))
    if moeda != MOEDA_ESPERADA[chave]:
        msg = (
            f"{origem}: meta.currency={moeda!r}, esperado {MOEDA_ESPERADA[chave]!r} — mudança de "
            f"moeda é erro de escala silencioso, não detalhe de metadado"
        )
        raise SerieInconsistente(msg)
    granularidade = str(meta.get("dataGranularity", ""))
    if granularidade != INTERVALO_DIARIO:
        msg = (
            f"{origem}: meta.dataGranularity={granularidade!r}, esperado "
            f"{INTERVALO_DIARIO!r} — a granularidade nativa desta série é diária "
            f"(Anti-SPEC §10.4.28)"
        )
        raise SerieInconsistente(msg)

    timestamps = resultado.get("timestamp")
    if not isinstance(timestamps, list):
        msg = f"{origem}: chart.result[0].timestamp ausente ou não é lista"
        raise SerieInconsistente(msg)
    fechamento = _fechamentos(resultado, origem=origem)
    if len(timestamps) != len(fechamento):
        msg = (
            f"{origem}: {len(timestamps)} timestamps contra {len(fechamento)} fechamentos — "
            f"vetores desalinhados, a data de cada ponto ficaria errada"
        )
        raise SerieInconsistente(msg)

    datas = datas_de_pregao(timestamps, gmtoffset=meta.get("gmtoffset", 0))
    # Ausência é `None`, nunca `0` (Anti-SPEC §10.1.4): o `DX-Y.NYB` traz ~17% de fechamentos
    # nulos e o `BRL=X` ~8%. **Não** são feriados: medido nas 1.210 linhas nulas do `YAHOO_DXY`,
    # 1.188 (98,2%) são DOMINGO e as 22 restantes se espalham em segunda/terça/quinta/sexta — o
    # Yahoo emite o timestamp da semana de futuros, inclusive o dia sem sessão. A convenção
    # aqui é registrar o nulo em vez de omitir a linha (F-006 omite, CA-037); quem for agregar
    # precisa descartar `value.isna()`, nunca interpretá-lo como 0 nem como pregão.
    valores = [para_float_ponto_decimal(v, origem=origem) for v in fechamento]

    quadro = pd.DataFrame(
        {
            "series_id": entrada.series_id,
            "date": pd.to_datetime(pd.Series(datas, dtype="object")),
            "value": pd.Series(valores, dtype="float64"),
            "source": Fonte.YAHOO.value,
            "freq": Freq.DIARIA.value,
            # D-b: `vintage` = data (sem hora) de `collected_at`, que sai do manifesto do bruto.
            "vintage": pd.Timestamp(collected_at).tz_localize(None).normalize(),
            "unit": entrada.unit.value,
            "collected_at": pd.Timestamp(collected_at).tz_localize(None),
        }
    )
    piso = config.contagem_minima_esperada if minimo is DO_CONTRATO else minimo
    _validar(quadro, chave=chave, origem=origem, minimo=piso)  # type: ignore[arg-type]
    return quadro.reset_index(drop=True)


def _validar(quadro: pd.DataFrame, *, chave: str, origem: str, minimo: int | None) -> None:
    """Guardas de conteúdo: contagem de não nulos, duplicata, ordem e data futura."""
    nao_nulos = int(quadro["value"].notna().sum())
    exigir_contagem_minima(nao_nulos, minimo=minimo, origem=f"{chave} @ {origem}")

    if quadro["date"].isna().any():
        msg = f"{origem}: {int(quadro['date'].isna().sum())} ponto(s) sem data de pregão"
        raise SerieInconsistente(msg)
    duplicadas = quadro.loc[quadro["date"].duplicated(keep=False), "date"]
    if not duplicadas.empty:
        amostra = sorted({d.date().isoformat() for d in duplicadas})[:5]
        msg = (
            f"{origem}: data de pregão repetida (amostra: {amostra}) — provável mistura de "
            f"granularidades na mesma resposta"
        )
        raise SerieInconsistente(msg)
    if not quadro["date"].is_monotonic_increasing:
        msg = f"{origem}: datas de pregão fora de ordem crescente"
        raise SerieInconsistente(msg)
    futuras = quadro.loc[quadro["date"] > quadro["collected_at"], "date"]
    if not futuras.empty:
        msg = f"{origem}: data futura na série (máx {futuras.max().date().isoformat()})"
        raise SerieInconsistente(msg)


def conferir_canario(quadro: pd.DataFrame, *, chave: str, origem: str) -> tuple[str, float] | None:
    """Confere o `valor_canario` do contrato, se a janela extraída o cobre.

    Devolve o par conferido, ou `None` quando a janela não alcança a data do canário (caso da
    fixture recortada). Divergência levanta: é o teste de contrato contra endpoint não
    documentado (R18) rodando também em produção.
    """
    config = config_do_ticker(chave)
    if config.valor_canario is None:
        return None
    dia, esperado = config.valor_canario
    alvo = pd.Timestamp(dia)
    linha = quadro.loc[quadro["date"] == alvo, "value"]
    if linha.empty:
        return None
    obtido = float(linha.to_numpy()[0])
    if obtido != esperado:
        msg = (
            f"{origem}: valor-canário de {chave} em {dia} é {esperado!r}, a fonte devolveu "
            f"{obtido!r} — endpoint não documentado mudou ou o ticker é outro (R18)"
        )
        raise SerieInconsistente(msg)
    return (dia, esperado)


#: Séries derivadas em BRL produzidas por este módulo: `chave do ticker -> series_id do catálogo`.
#: `SP500_BRL` sai do `^GSPC`, que é **price return** — a entrada do catálogo marca
#: `is_total_return=False` e nada aqui finge o contrário.
SERIES_BRL: dict[str, str] = {"GSPC": "SP500_BRL"}


# ─────────────────────────────────────────────────────────────────────────────
# Extração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoSerie:
    """Evidência de dados de um ticker — o que vai para o relatório do Feature Contract."""

    chave: str
    ticker: str
    series_id: str
    linhas: int
    data_inicio: date
    data_fim: date
    pct_nulos_value: float
    valor_minimo: float
    valor_maximo: float
    valor_final: float
    canario: tuple[str, float] | None
    sha256_raw: str
    bytes_raw: int
    caminho_raw: Path | None
    raw_idempotente: bool
    caminho_processed: Path | None
    is_total_return: bool | None
    series_id_brl: str | None = None
    linhas_brl: int | None = None
    dias_sem_ptax: int | None = None
    caminho_processed_brl: Path | None = None

    def resumo(self) -> str:
        """Uma linha para o log e para a CLI, **só em ASCII**.

        O `stdout` do terminal do Windows é cp1252 e `print` de `->` com seta Unicode levanta
        `UnicodeEncodeError` depois de a série já ter sido gravada (mesma raiz do
        Anti-SPEC §10.4.26, do outro lado do pipe).
        """
        raw = "idempotente" if self.raw_idempotente else "novo"
        canario = f"{self.canario[0]}={self.canario[1]:.6f}" if self.canario else "fora da janela"
        brl = ""
        if self.series_id_brl:
            brl = f", {self.series_id_brl}: {self.linhas_brl} linhas ({self.dias_sem_ptax} s/PTAX)"
        return (
            f"{self.series_id} [{self.ticker}]: {self.linhas} linhas, "
            f"{self.data_inicio} -> {self.data_fim}, min={self.valor_minimo:.4f} "
            f"max={self.valor_maximo:.4f} fim={self.valor_final:.4f}, "
            f"nulos={self.pct_nulos_value:.2%}, canario {canario}, "
            f"raw {raw} sha256={self.sha256_raw[:12]}...{brl}"
        )


def nome_processado(series_id: str) -> str:
    """`yahoo/YAHOO_GSPC.parquet` — caminho relativo dentro de `data/processed/`."""
    return f"{SUBPASTA_PROCESSED}/{series_id}.parquet"


def mesma_serie(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    """`True` se os pares `(date, value)` dos dois quadros são idênticos (nulo = nulo)."""
    if len(a) != len(b):
        return False
    colunas = ["date", "value"]
    return bool(a[colunas].reset_index(drop=True).equals(b[colunas].reset_index(drop=True)))


def _arquivar_retrato(
    conteudo: bytes,
    *,
    config: ExtractorConfig,
    nome: str,
    origem: str,
    obtido_em: datetime,
    cabecalhos: dict[str, str],
    quadro: pd.DataFrame,
    chave: str,
    raiz: Path | None,
) -> ResultadoArquivamento:
    """Arquiva o bruto tolerando a **serialização instável** da fonte (pegadinha nº 6).

    `arquivar_bruto` recusa conteúdo diferente no mesmo nome determinístico, e com razão (R8).
    Mas aqui a divergência pode ser só a ordem das chaves de `meta.currentTradingPeriod`, com
    `timestamp` e `close` idênticos. Então, diante de `ConteudoDivergente`:

    - reparseia o **bruto já arquivado** e compara a série `(date, value)` com a de agora;
    - série igual → **mantém o retrato original** (nada escrito, `idempotente is True`), e o
      `sha256` do manifesto continua apontando para o primeiro retrato do dia;
    - série diferente → **relevanta**. Revisão retroativa não é ruído de serialização, é dado
      novo que não pode apagar o anterior.
    """
    destino = caminho_destino_raw(config, raiz=raiz)
    try:
        return arquivar_bruto(
            conteudo,
            destino=destino,
            nome=nome,
            origem=origem,
            obtido_em=obtido_em,
            cabecalhos=cabecalhos,
        )
    except ConteudoDivergente:
        alvo = destino / nome
        arquivado = alvo.read_bytes()
        anterior = parse_chart(
            arquivado, chave=chave, origem=str(alvo), collected_at=obtido_em, minimo=None
        )
        if not mesma_serie(anterior, quadro):
            raise
        _log.warning(
            "%s: bytes diferentes do arquivado, mas a serie (date, value) e identica em %d "
            "pontos -- retrato original mantido (a fonte alterna a ordem das chaves de "
            "meta.currentTradingPeriod)",
            nome,
            len(quadro),
        )
        return ResultadoArquivamento(
            caminho=alvo,
            sha256=sha256_de(arquivado),
            bytes_gravados=len(arquivado),
            ja_existia=True,
            escreveu=False,
        )


def _resultado(
    quadro: pd.DataFrame,
    *,
    chave: str,
    canario: tuple[str, float] | None,
    sha256_raw: str,
    bytes_raw: int,
    caminho_raw: Path | None,
    raw_idempotente: bool,
    caminho_processed_: Path | None,
) -> ResultadoSerie:
    entrada = entrada_do_ticker(chave)
    return ResultadoSerie(
        chave=chave,
        ticker=TICKERS[chave],
        series_id=entrada.series_id,
        linhas=len(quadro),
        data_inicio=quadro["date"].min().date(),
        data_fim=quadro["date"].max().date(),
        pct_nulos_value=float(quadro["value"].isna().mean()),
        valor_minimo=float(quadro["value"].min()),
        valor_maximo=float(quadro["value"].max()),
        valor_final=float(quadro["value"].dropna().iloc[-1]),
        canario=canario,
        sha256_raw=sha256_raw,
        bytes_raw=bytes_raw,
        caminho_raw=caminho_raw,
        raw_idempotente=raw_idempotente,
        caminho_processed=caminho_processed_,
        is_total_return=entrada.is_total_return,
    )


def _gravar_brl(
    quadro: pd.DataFrame,
    *,
    chave: str,
    raiz: Path | None,
    gravar: bool,
) -> tuple[str, int, int, Path | None] | None:
    """Deriva e grava a série em BRL do ticker, se houver uma declarada e a PTAX existir."""
    series_id_brl = SERIES_BRL.get(chave)
    if series_id_brl is None:
        return None
    destino = entrada_do_catalogo(series_id_brl)
    try:
        ptax = carregar_ptax(raiz=raiz)
    except ErroDeExtracao as exc:
        _log.warning("%s nao produzida: %s", series_id_brl, exc)
        return None
    conversao = converter_para_brl(
        quadro,
        series_id_destino=series_id_brl,
        ptax=ptax,
        is_total_return=destino.is_total_return,
        unit=destino.unit.value,
        origem=series_id_brl,
    )
    caminho = (
        gravar_processado_parquet(conversao.quadro, nome=nome_processado(series_id_brl), raiz=raiz)
        if gravar
        else None
    )
    return (series_id_brl, conversao.linhas, conversao.dias_sem_ptax, caminho)


def extrair_ticker(
    chave: str,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
    com_brl: bool = True,
    minimo: int | None | object = DO_CONTRATO,
) -> ResultadoSerie:
    """Baixa, parseia, arquiva o bruto e grava o processado de **um** ticker.

    A ordem é download → parse → `arquivar_bruto` → `gravar_processado_parquet`: o nome do bruto
    carrega a **última data de pregão** do histórico (não "hoje"), que é o que torna a segunda
    rodada do mesmo dia byte-idêntica e idempotente (CA-027) e o que faz uma republicação
    diferente do mesmo retrato bater em `ConteudoDivergente` em vez de apagar o anterior (R8).
    """
    config = config_do_ticker(chave)
    cliente = ClienteHTTP(config, transporte=transporte)
    parametros = parametros_janela(inicio, fim)
    proibidos = PARAMETROS_PROIBIDOS.intersection(parametros)
    if proibidos:  # pragma: no cover - guarda estrutural de CA-045
        msg = f"{config.nome}: parâmetro proibido na querystring: {sorted(proibidos)}"
        raise ErroDeExtracao(msg)
    resposta = cliente.get(params=parametros)
    conteudo = resposta.conteudo

    quadro = parse_chart(
        conteudo,
        chave=chave,
        origem=resposta.url,
        collected_at=resposta.obtida_em,
        minimo=minimo,
    )
    canario = conferir_canario(quadro, chave=chave, origem=resposta.url)
    data_ref = quadro["date"].max().date()

    arquivado = _arquivar_retrato(
        conteudo,
        config=config,
        nome=nome_arquivo_raw(TICKERS[chave], data_ref=data_ref, extensao=EXTENSAO_RAW),
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
        quadro=quadro,
        chave=chave,
        raiz=raiz,
    )
    destino = (
        gravar_processado_parquet(quadro, nome=nome_processado(config.series_ids[0]), raiz=raiz)
        if gravar
        else None
    )
    resultado = _resultado(
        quadro,
        chave=chave,
        canario=canario,
        sha256_raw=arquivado.sha256,
        bytes_raw=arquivado.bytes_gravados,
        caminho_raw=arquivado.caminho,
        raw_idempotente=arquivado.idempotente,
        caminho_processed_=destino,
    )
    if com_brl:
        brl = _gravar_brl(quadro, chave=chave, raiz=raiz, gravar=gravar)
        if brl is not None:
            resultado = replace_brl(resultado, *brl)
    _log.info("%s", resultado.resumo())
    return resultado


def replace_brl(
    resultado: ResultadoSerie,
    series_id_brl: str,
    linhas_brl: int,
    dias_sem_ptax: int,
    caminho: Path | None,
) -> ResultadoSerie:
    """Cópia do resultado com os campos da série derivada em BRL preenchidos."""
    return replace(
        resultado,
        series_id_brl=series_id_brl,
        linhas_brl=linhas_brl,
        dias_sem_ptax=dias_sem_ptax,
        caminho_processed_brl=caminho,
    )


def _bruto_arquivado(chave: str, *, raiz: Path | None) -> Path:
    """O bruto mais recente do ticker em `data/raw/yahoo/` (modo `--offline`)."""
    pasta = caminho_destino_raw(config_do_ticker(chave), raiz=raiz)
    # Mesmo nome determinístico que `arquivar_bruto` gravou — `^`, `=` e `.` sobrevivem ao slug
    # de `nome_arquivo_raw` e nenhum deles é metacaractere de glob. O filtro do manifesto não é
    # cosmético: `*` casa com ponto, então `^GSPC__*.json` pegaria também
    # `^GSPC__2026-10-09.json.meta.json` — que ordena **depois** e seria o "mais recente".
    padrao = f"{TICKERS[chave]}__*.{EXTENSAO_RAW}"
    candidatos = sorted(
        (c for c in pasta.glob(padrao) if not c.name.endswith(SUFIXO_MANIFESTO)), reverse=True
    )
    if not candidatos:
        msg = f"modo offline: nenhum bruto de {TICKERS[chave]} em {pasta}"
        raise ErroDeExtracao(msg)
    return candidatos[0]


def extrair_ticker_offline(
    chave: str,
    *,
    raiz: Path | None = None,
    gravar: bool = True,
    com_brl: bool = True,
    caminho: Path | None = None,
    minimo: int | None | object = DO_CONTRATO,
    collected_at: datetime | None = None,
) -> ResultadoSerie:
    """Reprocessa um ticker do bruto já arquivado — sem rede, sem reescrever `data/raw/`.

    `collected_at` só é aceito **explícito**: sem ele e sem manifesto do bruto, recusa
    (`ManifestoAusente`) em vez de datar o Parquet pelo relógio da rodada (D-b, CA-121).
    """
    alvo = caminho or _bruto_arquivado(chave, raiz=raiz)
    conteudo = alvo.read_bytes()
    # D-b: `collected_at` (e portanto `vintage`) sai do manifesto do bruto, não do relógio.
    quadro = parse_chart(
        conteudo,
        chave=chave,
        origem=str(alvo),
        collected_at=collected_at_do_bruto(alvo, collected_at=collected_at),
        minimo=minimo,
    )
    canario = conferir_canario(quadro, chave=chave, origem=str(alvo))
    destino = (
        gravar_processado_parquet(quadro, nome=nome_processado(series_id_de(chave)), raiz=raiz)
        if gravar
        else None
    )
    resultado = _resultado(
        quadro,
        chave=chave,
        canario=canario,
        sha256_raw=sha256_de(conteudo),
        bytes_raw=len(conteudo),
        caminho_raw=alvo,
        raw_idempotente=True,
        caminho_processed_=destino,
    )
    if com_brl:
        brl = _gravar_brl(quadro, chave=chave, raiz=raiz, gravar=gravar)
        if brl is not None:
            resultado = replace_brl(resultado, *brl)
    _log.info("[offline] %s", resultado.resumo())
    return resultado


def extrair(
    chaves: Sequence[str] | None = None,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    offline: bool = False,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
    com_brl: bool = True,
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, ResultadoSerie]:
    """Roda os tickers pedidos (default: `TICKERS_PADRAO`) e devolve a evidência por chave."""
    alvos = tuple(chaves) if chaves else TICKERS_PADRAO
    resultados: dict[str, ResultadoSerie] = {}
    for posicao, chave in enumerate(alvos):
        if offline:
            resultados[chave] = extrair_ticker_offline(
                chave, raiz=raiz, gravar=gravar, com_brl=com_brl
            )
            continue
        if posicao:
            dormir(PAUSA_ENTRE_TICKERS_S)
        resultados[chave] = extrair_ticker(
            chave,
            inicio=inicio,
            fim=fim,
            transporte=transporte,
            raiz=raiz,
            gravar=gravar,
            com_brl=com_brl,
        )
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.yahoo",
        description="Extrai séries do Yahoo chart/v8 (F-007, SPEC RF-016/RF-017).",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        metavar="CHAVE",
        choices=TICKERS_SUPORTADOS,
        help=f"subconjunto a extrair (default: {' '.join(TICKERS_PADRAO)})",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reprocessa o bruto já em data/raw/yahoo/, sem tocar a rede",
    )
    parser.add_argument(
        "--sem-gravar",
        action="store_true",
        help="não escreve em data/processed/ (só confere e imprime a evidência)",
    )
    parser.add_argument(
        "--sem-brl",
        action="store_true",
        help="não deriva a série em BRL (que depende da PTAX de F-003)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` em sucesso, `1` em qualquer `ErroDeExtracao`."""
    args = _parser().parse_args(list(argv) if argv is not None else None)
    configurar_logging()
    try:
        resultados = extrair(
            args.tickers,
            offline=args.offline,
            gravar=not args.sem_gravar,
            com_brl=not args.sem_brl,
        )
    except ErroDeExtracao as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for resultado in resultados.values():
        print(resultado.resumo())
    cobrem_2006 = sum(1 for r in resultados.values() if r.data_inicio <= date(2006, 1, 31))
    print(f"{len(resultados)} serie(s); {cobrem_2006} com data_inicio <= 2006-01-31")
    return 0


def _main_cli() -> None:  # pragma: no cover - invocado só por `python -m`
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _main_cli()
