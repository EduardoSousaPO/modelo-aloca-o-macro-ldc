"""Testes do extrator MSCI `indexmaster` (F-007, SPEC RF-016, CA-046 e CA-047).

Nenhum teste aqui toca a rede: tudo vem de `tests/fixtures/msci/`, que é **resposta real** da
fonte (janela de 2006 inteiro, para caber nos 200 KB), mais os dois corpos reais de caminho de
erro — o `error_message` servido com HTTP 200 e o `INDEX_LEVELS: []` de código inexistente,
também com HTTP 200. O teste que vai à fonte viva está marcado `@pytest.mark.network` e o CI N1 o
exclui com `-m "not network"` (Anti-SPEC §10.4.23).

O valor-canário da SPEC (**ACWI NETR 31/01/2006 = 121,3858**) está dentro da fixture, então
CA-046 é verificado sem rede.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from apps.pipeline.common import (
    ErroDeExtracao,
    FormatoInesperado,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    UserAgentObrigatorio,
    caminho_processed,
    sha256_de,
)
from apps.pipeline.extract import msci
from apps.pipeline.extract.msci import (
    CHAVES_DE_ERRO_MSCI,
    DATA_INICIO_NETR,
    DATA_MINIMA_FONTE,
    INDICES,
    INDICES_PADRAO,
    INDICES_SUPORTADOS,
    MOEDA,
    NIVEIS_MINIMOS,
    SERIES_BRL,
    VALORES_CANARIO,
    VARIANTE,
    ClienteHTTP,
    SerieInconsistente,
    codigo_de,
    conferir_canario,
    config_do_indice,
    extrair_indice,
    extrair_indice_offline,
    parametros_janela,
    parse_niveis,
    series_id_de,
)
from apps.pipeline.transform import converter_para_brl
from packages.shared.schemas import ProcessedSeriesSchema, load_catalog

if TYPE_CHECKING:
    from pathlib import Path

COLETA = datetime(2026, 10, 10, 23, 0, tzinfo=UTC)

#: `tests/fixtures/msci/` — nomes pela convenção de `tests/fixtures/README.md`
#: (`<identificador>__<data>.json`, com `<identificador>` = `892400_NETR`).
FIXTURA_ACWI = "892400_NETR__2026-10-10.json"
FIXTURA_ACWI_EOM = "892400_NETR__end-of-month.json"
FIXTURA_ERRO_START = "892400_NETR__erro_start-date.json"
FIXTURA_VAZIA = "705000_NETR__vazio.json"


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


@pytest.fixture
def dir_msci() -> Path:
    """`tests/fixtures/msci/`."""
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "fixtures" / "msci"


@pytest.fixture
def acwi(dir_msci: Path) -> bytes:
    """Resposta real do ACWI `NETR` para 2006 inteiro (260 níveis)."""
    return (dir_msci / FIXTURA_ACWI).read_bytes()


def _quadro_acwi(conteudo: bytes) -> pd.DataFrame:
    return parse_niveis(conteudo, chave="ACWI", origem="fixture", collected_at=COLETA, minimo=None)


# ─────────────────────────────────────────────────────────────────────────────
# CA-046 — valor-canário e data de início
# ─────────────────────────────────────────────────────────────────────────────


def test_ca046_valor_canario_acwi_netr_31_01_2006(acwi: bytes) -> None:
    """31/01/2006 = **121,3858**, o valor-canário da SPEC, lido da resposta real da fonte."""
    quadro = _quadro_acwi(acwi)
    valor = quadro.loc[quadro["date"] == pd.Timestamp("2006-01-31"), "value"].to_numpy()[0]
    assert round(valor, 4) == 121.3858
    assert valor == pytest.approx(121.38580887703861, abs=1e-12)
    assert conferir_canario(quadro, chave="ACWI", origem="fixture") == VALORES_CANARIO["ACWI"]


def test_ca046_canario_confere_contra_outra_superficie_da_fonte(dir_msci: Path) -> None:
    """O mesmo 121,3858 vem de `data_frequency=END_OF_MONTH` — requisição e payload distintos.

    Não é o mesmo arquivo relido: é outra chamada, com outra frequência, que a fonte calcula por
    um caminho diferente. Duas superfícies, o mesmo número (`CLAUDE.md §9`).
    """
    eom = json.loads((dir_msci / FIXTURA_ACWI_EOM).read_bytes().decode("utf-8"))
    niveis = {e["calc_date"]: e["level_eod"] for e in eom["indexes"]["INDEX_LEVELS"]}
    assert niveis[20060131] == pytest.approx(121.38580887703861, abs=1e-12)
    assert niveis[20060331] == pytest.approx(123.7572663279524, abs=1e-12)
    # E o diário da outra fixture dá exatamente os mesmos valores nesses dois dias.
    quadro = _quadro_acwi((dir_msci / FIXTURA_ACWI).read_bytes()).set_index("date")["value"]
    assert quadro[pd.Timestamp("2006-01-31")] == pytest.approx(niveis[20060131], abs=1e-12)
    assert quadro[pd.Timestamp("2006-03-31")] == pytest.approx(niveis[20060331], abs=1e-12)


def test_ca046_data_inicio_da_variante_netr_e_2000_12_29() -> None:
    """`NETR` começa em 2000-12-29 (a `STRD` em 1997-01-01) — é o que o catálogo declara."""
    assert DATA_INICIO_NETR.isoformat() == "2000-12-29"
    catalogo = {e.series_id: e for e in load_catalog()}
    for chave in INDICES_SUPORTADOS:
        assert catalogo[series_id_de(chave)].data_inicio == DATA_INICIO_NETR
    assert DATA_INICIO_NETR.isoformat() < "2006-01-31", "precisa cobrir o 1T2006"


def test_canario_divergente_levanta(acwi: bytes) -> None:
    """Endpoint não documentado (R18) que muda de série é pego pelo canário em produção."""
    quadro = _quadro_acwi(acwi).copy()
    quadro.loc[quadro["date"] == pd.Timestamp("2006-01-31"), "value"] = 999.0
    with pytest.raises(SerieInconsistente, match="valor-can"):
        conferir_canario(quadro, chave="ACWI", origem="fixture")


# ─────────────────────────────────────────────────────────────────────────────
# Parse da resposta real
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_produz_o_contrato_processed_series(acwi: bytes) -> None:
    """260 níveis de 2006 viram DataFrame válido por `ProcessedSeriesSchema`."""
    quadro = _quadro_acwi(acwi)
    ProcessedSeriesSchema.validate(quadro, lazy=True)

    assert len(quadro) == 260
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
    assert quadro["series_id"].unique().tolist() == ["MSCI_ACWI_NETR"]
    assert quadro["source"].unique().tolist() == ["MSCI"]
    assert quadro["freq"].unique().tolist() == ["D"], "frequencia nativa e diaria"
    assert quadro["unit"].unique().tolist() == ["index"]
    assert quadro["value"].isna().sum() == 0
    assert quadro["date"].is_monotonic_increasing
    assert not quadro["date"].duplicated().any()


def test_calc_date_aaaammdd_vira_data_civil(acwi: bytes) -> None:
    """`20060102` é 2 de janeiro, declarado como `AAAAMMDD` — nunca inferido (R12)."""
    corpo = json.loads(acwi.decode("utf-8"))
    primeiro = corpo["indexes"]["INDEX_LEVELS"][0]
    assert primeiro["calc_date"] == 20060102
    assert isinstance(primeiro["calc_date"], int), "a fonte manda inteiro, nao string"

    quadro = _quadro_acwi(acwi)
    assert quadro["date"].min() == pd.Timestamp("2006-01-02")
    assert quadro["date"].max() == pd.Timestamp("2006-12-29")


def test_level_eod_usa_o_normalizador_de_ponto_decimal(acwi: bytes) -> None:
    """`115.81778327574106` é ponto decimal: lido como pt-BR daria erro de escala de 1000x."""
    quadro = _quadro_acwi(acwi)
    assert quadro["value"].iloc[0] == pytest.approx(115.81778327574106, abs=1e-12)
    assert 50.0 < quadro["value"].min() < 1000.0
    assert 50.0 < quadro["value"].max() < 1000.0


def test_vintage_e_a_data_do_collected_at_e_e_constante(acwi: bytes) -> None:
    """D-b: `vintage` = a data (sem hora) de `collected_at`; PK `(series_id, date, vintage)`."""
    quadro = _quadro_acwi(acwi)
    assert (quadro["vintage"] == quadro["vintage"].iloc[0]).all(), "vintage tem de ser constante"
    assert quadro["vintage"].iloc[0] == pd.Timestamp(COLETA.date())
    assert (quadro["vintage"] == quadro["vintage"].dt.normalize()).all(), "vintage não tem hora"
    assert quadro["date"].max() == pd.Timestamp("2006-12-29")
    assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any()


def test_cobertura_de_1t2006(acwi: bytes) -> None:
    """O 1T2006 tem 65 níveis — a MSCI calcula em todo dia de semana, inclusive feriado local."""
    quadro = _quadro_acwi(acwi)
    t1 = quadro[
        (quadro["date"] >= pd.Timestamp("2006-01-01"))
        & (quadro["date"] <= pd.Timestamp("2006-03-31"))
    ]
    assert len(t1) == 65
    assert t1["date"].min() == pd.Timestamp("2006-01-02")
    assert t1["date"].max() == pd.Timestamp("2006-03-31")


# ─────────────────────────────────────────────────────────────────────────────
# Caminhos de erro (R1, R2) — fixtura de erro obrigatória (CA-124)
# ─────────────────────────────────────────────────────────────────────────────


def test_erro_com_http_200_e_recusado_e_a_chave_nao_e_error(dir_msci: Path) -> None:
    """`error_code`/`error_message` com HTTP 200: a guarda da infra não cobre, esta cobre (R1).

    `CHAVES_DE_ERRO` de `apps/pipeline/common/http.py` reconhece `error`/`erro`/`errors`/`erros`.
    A MSCI usa **outros nomes**, então usar `json_array` aqui deixaria o corpo de erro passar.
    """
    conteudo = (dir_msci / FIXTURA_ERRO_START).read_bytes()
    corpo = json.loads(conteudo.decode("utf-8"))
    assert set(corpo) == {"timestamp", "user", "error_code", "error_message"}
    assert "error" not in corpo
    assert "Calculation date cannot be earlier than 19970101" in corpo["error_message"]
    assert CHAVES_DE_ERRO_MSCI.intersection(corpo) == {"error_code", "error_message"}

    with pytest.raises(RespostaDeErroComStatus200, match="corpo de ERRO"):
        parse_niveis(conteudo, chave="ACWI", origem="fixture", collected_at=COLETA, minimo=None)


def test_index_levels_vazio_com_http_200_e_rejeitado_pela_contagem_minima(
    dir_msci: Path,
) -> None:
    """Código inexistente devolve 200 com `INDEX_LEVELS: []` e **nenhum** sinal de erro (R2)."""
    conteudo = (dir_msci / FIXTURA_VAZIA).read_bytes()
    corpo = json.loads(conteudo.decode("utf-8"))
    assert corpo["indexes"]["INDEX_LEVELS"] == []
    assert corpo["msci_index_code"] == "705000"
    assert not CHAVES_DE_ERRO_MSCI.intersection(corpo)

    # O código 705000 nem está em `INDICES` (é o MSCI Brazil `a_confirmar`); apontando a resposta
    # para o ACWI, a guarda de código pega antes — e é o diagnóstico certo.
    with pytest.raises(SerieInconsistente, match="msci_index_code"):
        parse_niveis(conteudo, chave="ACWI", origem="fixture", collected_at=COLETA)

    corpo["msci_index_code"] = "892400"
    with pytest.raises(RespostaTruncada, match="truncamento"):
        parse_niveis(
            json.dumps(corpo).encode("utf-8"),
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
        )


def test_piso_do_contrato_recusa_a_fixtura_recortada(acwi: bytes) -> None:
    """A fixture é 1 ano; o contrato exige 6.726 níveis. Rodar com o piso real levanta."""
    assert NIVEIS_MINIMOS["ACWI"] == 6726
    with pytest.raises(RespostaTruncada):
        parse_niveis(acwi, chave="ACWI", origem="fixture", collected_at=COLETA)


def test_variante_trocada_levanta(acwi: bytes) -> None:
    """`STRD` é preço e `NETR` é retorno total: trocar a variante troca a série (§10.2.12)."""
    corpo = json.loads(acwi.decode("utf-8"))
    corpo["index_variant_type"] = "STRD"
    with pytest.raises(SerieInconsistente, match="index_variant_type"):
        parse_niveis(
            json.dumps(corpo).encode("utf-8"),
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_codigo_trocado_levanta(acwi: bytes) -> None:
    """A resposta ecoa `msci_index_code`: índice diferente do pedido é erro, não detalhe."""
    with pytest.raises(SerieInconsistente, match="msci_index_code"):
        parse_niveis(acwi, chave="WORLD", origem="fixture", collected_at=COLETA, minimo=None)


def test_moeda_trocada_levanta(acwi: bytes) -> None:
    """Moeda diferente de USD mudaria a escala da série inteira."""
    corpo = json.loads(acwi.decode("utf-8"))
    corpo["ISO_currency_symbol"] = "EUR"
    with pytest.raises(SerieInconsistente, match="ISO_currency_symbol"):
        parse_niveis(
            json.dumps(corpo).encode("utf-8"),
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_nivel_nulo_levanta_em_vez_de_virar_zero(acwi: bytes) -> None:
    """`level_eod` nulo só sai de falha de parse — levantar, nunca preencher com `0` (§10.1.4)."""
    corpo = json.loads(acwi.decode("utf-8"))
    corpo["indexes"]["INDEX_LEVELS"][3]["level_eod"] = None
    with pytest.raises(SerieInconsistente, match="level_eod nulo"):
        parse_niveis(
            json.dumps(corpo).encode("utf-8"),
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_calc_date_repetido_levanta(acwi: bytes) -> None:
    """Data repetida quebraria a PK `(series_id, date, vintage)`."""
    corpo = json.loads(acwi.decode("utf-8"))
    niveis = corpo["indexes"]["INDEX_LEVELS"]
    niveis.insert(2, dict(niveis[1]))
    with pytest.raises(SerieInconsistente, match="calc_date repetido"):
        parse_niveis(
            json.dumps(corpo).encode("utf-8"),
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_calc_date_fora_de_ordem_levanta(acwi: bytes) -> None:
    """A fonte entrega cronológico; fora de ordem é sinal de resposta remontada."""
    corpo = json.loads(acwi.decode("utf-8"))
    niveis = corpo["indexes"]["INDEX_LEVELS"]
    niveis[0], niveis[5] = niveis[5], niveis[0]
    with pytest.raises(SerieInconsistente, match="fora de ordem"):
        parse_niveis(
            json.dumps(corpo).encode("utf-8"),
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_data_futura_levanta(acwi: bytes) -> None:
    """`date > collected_at` é o que `RawSeriesSchema.sem_data_futura` proíbe."""
    with pytest.raises(SerieInconsistente, match="data futura"):
        parse_niveis(
            acwi,
            chave="ACWI",
            origem="fixture",
            collected_at=datetime(2006, 6, 1, tzinfo=UTC),
            minimo=None,
        )


def test_corpo_html_e_recusado_pelos_magic_bytes() -> None:
    """Endpoint não documentado pode virar página de login: o leitor decide por magic bytes."""
    with pytest.raises(FormatoInesperado, match="html"):
        parse_niveis(
            b"<html><body>Sign in</body></html>",
            chave="ACWI",
            origem="fixture",
            collected_at=COLETA,
            minimo=None,
        )


def test_start_date_anterior_a_1997_levanta_antes_de_ir_a_rede() -> None:
    """A fonte recusaria com HTTP 200; levantar aqui dá o diagnóstico certo."""
    assert DATA_MINIMA_FONTE.isoformat() == "1997-01-01"
    with pytest.raises(ValueError, match="anterior ao mínimo da fonte"):
        parametros_janela("ACWI", date(1996, 1, 1))


# ─────────────────────────────────────────────────────────────────────────────
# Querystring, catálogo e contrato
# ─────────────────────────────────────────────────────────────────────────────


def test_querystring_declara_variante_moeda_e_frequencia() -> None:
    """Os três parâmetros que mudam a série inteira são explícitos, nunca default da fonte."""
    parametros = parametros_janela("ACWI", date(1997, 1, 1), date(2026, 10, 10))
    assert parametros == {
        "currency_symbol": "USD",
        "index_variant": "NETR",
        "start_date": "19970101",
        "end_date": "20261010",
        "data_frequency": "DAILY",
        "baseValue": "false",
        "index_codes": "892400",
    }


def test_janela_invertida_levanta() -> None:
    with pytest.raises(ValueError, match="janela invertida"):
        parametros_janela("ACWI", date(2026, 1, 1), date(2025, 1, 1))


def test_indices_vem_do_catalogo_e_todos_sao_retorno_total() -> None:
    """`series_id`, `identificador` e `is_total_return` são do catálogo, não daqui (CA-053)."""
    catalogo = {e.series_id: e for e in load_catalog()}
    for chave, (codigo, series_id) in INDICES.items():
        entrada = catalogo[series_id]
        assert entrada.identificador == f"{codigo} / {VARIANTE}"
        assert entrada.status.value == "ok"
        assert entrada.fonte.value == "MSCI"
        assert entrada.freq.value == "D"
        assert entrada.is_total_return is True
        assert entrada.fonte_instavel is True, "endpoint nao documentado (R18)"
        assert codigo_de(chave) == codigo
    assert set(INDICES_PADRAO) == set(INDICES_SUPORTADOS)
    assert "BRAZIL" not in INDICES, "MSCI Brazil esta a_confirmar (705000 devolve lista vazia)"


def test_config_declara_as_guardas_do_contrato() -> None:
    for chave in INDICES_SUPORTADOS:
        config = config_do_indice(chave)
        assert config.requer_user_agent_browser is True
        assert config.contagem_minima_esperada == NIVEIS_MINIMOS[chave]
        assert config.valor_canario == VALORES_CANARIO[chave]
        assert config.destino_raw == "data/raw/msci"
        assert config.formato == "json"
        assert config.encoding == "utf-8"
        assert config.janela_maxima_dias is None
        assert config.fonte.value == "MSCI"


def test_indice_nao_suportado_levanta() -> None:
    with pytest.raises(ErroDeExtracao, match="não suportado"):
        config_do_indice("JAPAN")


def test_requisicao_sem_user_agent_nao_e_despachada(acwi: bytes) -> None:
    """A app web da MSCI também exige UA de browser (R4)."""
    transporte = TransporteGravado(
        RespostaBruta(url="https://x", status=200, conteudo=acwi, obtida_em=COLETA)
    )
    cliente = ClienteHTTP(config_do_indice("ACWI"), transporte=transporte, cabecalhos_base={})
    with pytest.raises(UserAgentObrigatorio):
        cliente.get(params=parametros_janela("ACWI"))
    assert transporte.chamadas == []


# ─────────────────────────────────────────────────────────────────────────────
# CA-047 — ACWI_BRL pela PTAX do mesmo dia útil
# ─────────────────────────────────────────────────────────────────────────────


def test_ca047_acwi_brl_e_retorno_total_e_usa_ptax_do_mesmo_dia(acwi: bytes) -> None:
    """A série derivada é `nivel_netr * ptax(mesmo dia)` e carrega `is_total_return=True`."""
    quadro = _quadro_acwi(acwi)
    ptax = pd.DataFrame(
        {"date": quadro["date"], "ptax": [2.1 + i / 10000 for i in range(len(quadro))]}
    )
    destino = {e.series_id: e for e in load_catalog()}["ACWI_BRL"]
    assert destino.is_total_return is True

    conversao = converter_para_brl(
        quadro,
        series_id_destino="ACWI_BRL",
        ptax=ptax,
        is_total_return=destino.is_total_return,
        unit=destino.unit.value,
        origem="teste",
    )
    assert conversao.is_total_return is True
    assert conversao.linhas == 260
    assert conversao.dias_sem_ptax == 0
    esperado = quadro["value"].to_numpy() * ptax["ptax"].to_numpy()
    assert conversao.quadro["value"].to_numpy() == pytest.approx(esperado, rel=1e-12)
    ProcessedSeriesSchema.validate(conversao.quadro, lazy=True)
    assert set(SERIES_BRL.values()) == {"ACWI_BRL"}


def test_ca047_misturar_price_e_total_return_sem_flag_falha(acwi: bytes) -> None:
    """Sem `is_total_return` explícito a conversão levanta (Anti-SPEC §10.2.12)."""
    quadro = _quadro_acwi(acwi)
    ptax = pd.DataFrame({"date": quadro["date"], "ptax": 2.2})
    with pytest.raises(SerieInconsistente, match="is_total_return"):
        converter_para_brl(quadro, series_id_destino="ACWI_BRL", ptax=ptax, is_total_return=None)


def test_ca047_feriado_brasileiro_sai_da_serie(acwi: bytes) -> None:
    """A MSCI calcula em 27/02/2006 (Carnaval); sem PTAX do dia, o ponto sai, não é preenchido."""
    quadro = _quadro_acwi(acwi)
    assert pd.Timestamp("2006-02-27") in set(quadro["date"])
    ptax = pd.DataFrame(
        {
            "date": quadro.loc[quadro["date"] != pd.Timestamp("2006-02-27"), "date"],
            "ptax": 2.2,
        }
    )
    conversao = converter_para_brl(
        quadro, series_id_destino="ACWI_BRL", ptax=ptax, is_total_return=True
    )
    assert conversao.dias_sem_ptax == 1
    assert pd.Timestamp("2006-02-27") not in set(conversao.quadro["date"])
    assert conversao.quadro["value"].isna().sum() == 0


def test_ptax_ausente_nao_produz_acwi_brl(tmp_path: Path) -> None:
    """Sem a PTAX de F-003 a derivação não acontece — nenhum câmbio é estimado (§10.1.1)."""
    assert msci._gravar_brl(pd.DataFrame(), chave="ACWI", raiz=tmp_path, gravar=False) is None


# ─────────────────────────────────────────────────────────────────────────────
# Fluxo completo e idempotência
# ─────────────────────────────────────────────────────────────────────────────


def test_extracao_arquiva_bruto_e_grava_processado(acwi: bytes, tmp_path: Path) -> None:
    """Fluxo completo com transporte falso: bruto com manifesto + parquet validado."""
    transporte = TransporteGravado(
        RespostaBruta(
            url="https://app2.msci.com/...",
            status=200,
            conteudo=acwi,
            cabecalhos={"Content-Type": "application/json"},
            obtida_em=COLETA,
        )
    )
    resultado = extrair_indice(
        "ACWI", transporte=transporte, raiz=tmp_path, com_brl=False, minimo=None
    )
    assert resultado.linhas == 260
    assert resultado.data_inicio == date(2006, 1, 2)
    assert resultado.data_fim == date(2006, 12, 29)
    assert resultado.is_total_return is True
    assert resultado.canario == VALORES_CANARIO["ACWI"]
    assert resultado.sha256_raw == sha256_de(acwi)
    assert resultado.raw_idempotente is False

    bruto = tmp_path / "data" / "raw" / "msci" / "892400_NETR__2006-12-29.json"
    assert bruto.is_file()
    assert bruto.with_name(bruto.name + ".meta.json").is_file()

    processado = caminho_processed("msci/MSCI_ACWI_NETR.parquet", raiz=tmp_path)
    assert processado.is_file()
    ProcessedSeriesSchema.validate(pd.read_parquet(processado), lazy=True)


def test_segunda_rodada_e_idempotente(acwi: bytes, tmp_path: Path) -> None:
    """Resposta byte-idêntica: a 2ª rodada não escreve nada em `data/raw/` (CA-027)."""
    for _ in range(2):
        resultado = extrair_indice(
            "ACWI",
            transporte=TransporteGravado(
                RespostaBruta(url="https://x", status=200, conteudo=acwi, obtida_em=COLETA)
            ),
            raiz=tmp_path,
            com_brl=False,
            minimo=None,
        )
    assert resultado.raw_idempotente is True
    assert resultado.sha256_raw == sha256_de(acwi)
    # O parquet regravado é idêntico ao da 1ª rodada (mesma série, mesmo vintage).
    quadro = pd.read_parquet(caminho_processed("msci/MSCI_ACWI_NETR.parquet", raiz=tmp_path))
    assert len(quadro) == 260
    assert (quadro["vintage"] == quadro["vintage"].iloc[0]).all()


def test_db_offline_tira_o_vintage_do_manifesto_e_e_idempotente(
    acwi: bytes, tmp_path: Path
) -> None:
    """D-b: `vintage` = data do `obtido_em` do manifesto; duas rodadas offline, mesmo Parquet."""
    extrair_indice(
        "ACWI",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=acwi, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    hashes = set()
    for _ in range(2):
        offline = extrair_indice_offline("ACWI", raiz=tmp_path, com_brl=False, minimo=None)
        assert offline.caminho_processed is not None
        quadro = pd.read_parquet(offline.caminho_processed)
        assert (quadro["vintage"] == pd.Timestamp(COLETA.date())).all()
        hashes.add(sha256_de(offline.caminho_processed.read_bytes()))
    assert len(hashes) == 1


def test_modo_offline_reprocessa_sem_rede(acwi: bytes, tmp_path: Path) -> None:
    """`--offline` relê `data/raw/msci/` e ignora o `.meta.json` do manifesto no glob."""
    extrair_indice(
        "ACWI",
        transporte=TransporteGravado(
            RespostaBruta(url="https://x", status=200, conteudo=acwi, obtida_em=COLETA)
        ),
        raiz=tmp_path,
        com_brl=False,
        minimo=None,
    )
    offline = extrair_indice_offline("ACWI", raiz=tmp_path, com_brl=False, minimo=None)
    assert offline.linhas == 260
    assert offline.sha256_raw == sha256_de(acwi)
    assert offline.caminho_raw is not None
    assert offline.caminho_raw.name == "892400_NETR__2006-12-29.json"


def test_offline_sem_bruto_levanta(tmp_path: Path) -> None:
    with pytest.raises(ErroDeExtracao, match="modo offline"):
        extrair_indice_offline("ACWI", raiz=tmp_path)


def test_linha_de_evidencia_e_ascii(acwi: bytes) -> None:
    """A saída da CLI é ASCII: o `stdout` do Windows é cp1252 (Anti-SPEC §10.4.26)."""
    quadro = _quadro_acwi(acwi)
    linha = msci._resultado(
        quadro,
        chave="ACWI",
        canario=VALORES_CANARIO["ACWI"],
        sha256_raw="0" * 64,
        bytes_raw=1,
        caminho_raw=None,
        raw_idempotente=False,
        caminho_processed_=None,
    ).resumo()
    assert linha.isascii(), linha
    assert "MSCI_ACWI_NETR" in linha
    assert "892400/NETR" in linha
    assert "total_return=True" in linha
    assert "2006-01-02 -> 2006-12-29" in linha


def test_moeda_do_modulo_e_usd() -> None:
    """A série processada fica em **moeda original** — BRL é derivação (Anti-SPEC §10.4.28)."""
    assert MOEDA == "USD"
    assert VARIANTE == "NETR"


# ─────────────────────────────────────────────────────────────────────────────
# Fonte viva — fora do CI N1
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_fonte_viva_acwi_tras_o_canario_e_o_historico_completo(tmp_path: Path) -> None:
    """Confere a fixture contra a fonte real: canário CA-046, piso e início da `NETR`."""
    resultado = extrair_indice("ACWI", raiz=tmp_path, gravar=False, com_brl=False)
    assert resultado.data_inicio == DATA_INICIO_NETR
    assert resultado.data_fim >= date(2026, 10, 9)
    assert resultado.linhas >= NIVEIS_MINIMOS["ACWI"]
    assert resultado.canario == VALORES_CANARIO["ACWI"]
    assert resultado.pct_nulos_value == 0.0
    assert resultado.is_total_return is True
