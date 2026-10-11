"""Testes do extrator Tesouro Direto (F-005) — um por CA, todos sobre fixture gravada.

Nenhum teste deste arquivo abre socket, exceto os marcados `@pytest.mark.network` (CA-123,
Anti-SPEC §10.4.23) — o CI roda com `-m "not network"`.

As fixtures são **recorte real** do `precotaxatesourodireto.csv` baixado em 2026-10-10 e a
**página de erro real** do CKAN (HTTP 404 em HTML). Procedência em
`tests/fixtures/tesouro-direto/README.md`. A única fixture sintética diz isso no nome
(`__sintetico_acento_latin1.csv`) e existe porque o arquivo real é 100% ASCII hoje: sem ela não
há como provar que o encoding declarado importa (CA-022).
"""

from __future__ import annotations

import inspect
import locale
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from apps.pipeline.common import (
    ErroDeExtracao,
    FormatoInesperado,
    ManifestoAusente,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    UserAgentObrigatorio,
    arquivar_bruto,
    caminho_destino_raw,
    caminho_processed,
    sha256_de,
)
from apps.pipeline.extract import tesouro_direto as td
from packages.shared.schemas import ProcessedSeriesSchema

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

COLETA = datetime(2026, 10, 10, 23, 0, tzinfo=UTC)
"""`collected_at` fixo: é o que faz o Parquet ser byte-determinístico entre execuções."""


# ─────────────────────────────────────────────────────────────────────────────
# Transporte falso (modelo copiado de tests/unit/test_common_http.py, F-001 §2)
# ─────────────────────────────────────────────────────────────────────────────


class TransporteGravado:
    """Transporte falso: devolve respostas pré-definidas e registra o que recebeu."""

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
                "params": params,
                "dados": dados,
                "cabecalhos": dict(cabecalhos),
                "timeout_s": timeout_s,
            }
        )
        proxima = self._respostas.pop(0) if self._respostas else None
        if proxima is None:
            msg = f"transporte falso sem resposta programada para {metodo} {url}"
            raise AssertionError(msg)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


def _resposta(
    conteudo: bytes,
    *,
    status: int = 200,
    cabecalhos: Mapping[str, str] | None = None,
) -> RespostaBruta:
    return RespostaBruta(
        url=td.CONFIG.base_url,
        status=status,
        conteudo=conteudo,
        cabecalhos=dict(cabecalhos or {}),
        obtida_em=COLETA,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def dir_td(dir_fixtures: Path) -> Path:
    """`tests/fixtures/tesouro-direto/`."""
    caminho = dir_fixtures / "tesouro-direto"
    assert caminho.is_dir(), f"fixture de F-005 ausente em {caminho}"
    return caminho


@pytest.fixture(scope="session")
def csv_real(dir_td: Path) -> bytes:
    """Recorte real: 171 linhas, 4 datas-base, os 8 tipos de título."""
    return (dir_td / "precotaxatesourodireto__2026-10-10.csv").read_bytes()


@pytest.fixture(scope="session")
def html_de_erro(dir_td: Path) -> bytes:
    """Página de erro real do CKAN (HTTP 404, `text/html`, 17 KB)."""
    return (dir_td / "precotaxatesourodireto__erro_html.html").read_bytes()


@pytest.fixture(scope="session")
def csv_com_acento(dir_td: Path) -> bytes:
    """Sintética e nomeada como tal: latin-1 com `ç`/`ã` (o arquivo real é ASCII hoje)."""
    return (dir_td / "precotaxatesourodireto__sintetico_acento_latin1.csv").read_bytes()


@pytest.fixture
def painel_real(csv_real: bytes) -> pd.DataFrame:
    return td.parse_painel(csv_real)


# ─────────────────────────────────────────────────────────────────────────────
# CA-020 — parse pt-BR: 8 tipos, decimal vírgula, nenhuma taxa NaN por parse
# ─────────────────────────────────────────────────────────────────────────────


def test_ca020_reconhece_os_8_tipos_de_titulo(painel_real: pd.DataFrame) -> None:
    """Os 8 tipos medidos no arquivo completo aparecem no recorte e viram sigla tradicional."""
    assert sorted(painel_real["sigla"].unique()) == [
        "EDUCA",
        "LFT",
        "LTN",
        "NTNB",
        "NTNBP",
        "NTNC",
        "NTNF",
        "RENDA",
    ]
    assert len(td.SIGLA_POR_TIPO) == 8
    assert len(painel_real) == 171


def test_ca020_nenhuma_metrica_fica_nan_por_erro_de_parse(painel_real: pd.DataFrame) -> None:
    """`Taxa`/`PU` nulos no recorte real: zero. Nulo aqui seria falha de parse, não ausência."""
    metricas = [metrica for metrica, _ in td.METRICA_POR_COLUNA.values()]
    nulos = painel_real[metricas].isna().sum()
    assert nulos.to_dict() == dict.fromkeys(metricas, 0)
    assert painel_real[["data_base", "data_vencimento"]].notna().to_numpy().all()


@pytest.mark.parametrize(
    ("sigla", "vencimento", "data_base", "metrica", "esperado"),
    [
        # NTN-B 15/05/2045 em 09/10/2026 — o valor-canário do ExtractorConfig.
        ("NTNB", date(2045, 5, 15), date(2026, 10, 9), "TAXA_VENDA", 6.65),
        ("NTNB", date(2045, 5, 15), date(2026, 10, 9), "PU_VENDA", 4573.25),
        # LTN 01/01/2007 no primeiro dia útil de 2006: juro nominal de 16,68% a.a.
        ("LTN", date(2007, 1, 1), date(2006, 1, 2), "TAXA_VENDA", 16.68),
        # NTN-B 15/05/2045 em 02/01/2006 — a ponta longa real já existia (ADR-004).
        ("NTNB", date(2045, 5, 15), date(2006, 1, 2), "TAXA_VENDA", 9.15),
        # LFT com taxa NEGATIVA: -0,02 é valor real da fonte, não ausência (Anti-SPEC §10.1.4).
        ("LFT", date(2006, 1, 18), date(2006, 1, 2), "TAXA_COMPRA", -0.02),
        # ... e taxa ZERO, que também é valor real.
        ("LFT", date(2007, 1, 17), date(2006, 1, 2), "TAXA_COMPRA", 0.0),
        # PU de 5 dígitos: 20046,46 é 20 mil e pouco, não 2.004.646 (erro de escala pt-BR).
        ("LFT", date(2029, 3, 1), date(2026, 10, 9), "PU_COMPRA", 20046.46),
    ],
)
def test_ca020_decimal_virgula_sem_erro_de_escala(
    painel_real: pd.DataFrame,
    sigla: str,
    vencimento: date,
    data_base: date,
    metrica: str,
    esperado: float,
) -> None:
    """Valores conferidos linha a linha no CSV da fonte — inclui negativo, zero e 5 dígitos."""
    linha = painel_real.loc[
        (painel_real["sigla"] == sigla)
        & (painel_real["data_vencimento"] == vencimento)
        & (painel_real["data_base"] == data_base)
    ]
    assert len(linha) == 1, f"{sigla} {vencimento} {data_base} deveria existir uma vez"
    assert float(linha[metrica].iloc[0]) == pytest.approx(esperado, abs=1e-9)


def test_ca020_data_dd_mm_aaaa_nao_e_inferida(painel_real: pd.DataFrame) -> None:
    """`02/01/2006` é 2 de janeiro (DD_MM_AAAA declarado), não 1 de fevereiro (R12)."""
    assert date(2006, 1, 2) in set(painel_real["data_base"])
    assert date(2006, 2, 1) not in set(painel_real["data_base"])


def test_ca020_tipo_de_titulo_novo_levanta(csv_real: bytes) -> None:
    """Título que o Tesouro lance amanhã não pode ser absorvido em silêncio."""
    mutado = csv_real.replace(b"Tesouro Educa+", b"Tesouro Quantico+", 1)
    assert mutado != csv_real
    with pytest.raises(FormatoInesperado, match="tipo de título desconhecido"):
        td.parse_painel(mutado)


def test_ca020_cabecalho_diferente_levanta(csv_real: bytes) -> None:
    """Renomear coluna na fonte é mudança de layout: para antes de `read_csv` virar dado."""
    mutado = csv_real.replace(b"Taxa Venda Manha", b"Taxa Venda", 1)
    with pytest.raises(FormatoInesperado, match="cabeçalho inesperado"):
        td.parse_painel(mutado)


# ─────────────────────────────────────────────────────────────────────────────
# CA-021 — cobertura histórica (2006 >= 240 dias úteis, min <= 2005-01-03)
# ─────────────────────────────────────────────────────────────────────────────


def test_ca021_limiares_sao_os_medidos_na_fonte() -> None:
    """Os limiares do contrato, não um número arredondado por conveniência."""
    assert td.MINIMO_DIAS_UTEIS_2006 == 240
    assert date(2005, 1, 3) == td.DATA_BASE_MAIS_ANTIGA_ACEITA
    assert td.CONTAGEM_MINIMA_LINHAS == 170_000
    assert td.CONFIG.contagem_minima_esperada == td.CONTAGEM_MINIMA_LINHAS


def test_ca021_recorte_sem_2006_completo_e_recusado(painel_real: pd.DataFrame) -> None:
    """A fixture tem 1 dia útil de 2006. A guarda tem de recusá-la — é o teste da guarda."""
    assert td.resumo_cobertura(painel_real)["dias_uteis_2006"] == 1
    with pytest.raises(RespostaDeErroComStatus200, match="dias úteis em 2006"):
        td.exigir_cobertura_historica(painel_real)


def test_ca021_historico_encurtado_e_recusado(painel_real: pd.DataFrame) -> None:
    """Se a fonte passar a começar depois de 2005-01-03, o pipeline para aqui."""
    recente = painel_real.loc[painel_real["data_base"] >= date(2006, 1, 1)]
    with pytest.raises(RespostaDeErroComStatus200, match="Data Base mais antiga"):
        td.exigir_cobertura_historica(recente)


def test_ca021_resumo_de_cobertura_bate_com_a_fixture(painel_real: pd.DataFrame) -> None:
    resumo = td.resumo_cobertura(painel_real)
    assert resumo["data_base_min"] == date(2004, 12, 31)
    assert resumo["data_base_max"] == date(2026, 10, 9)


def test_ca021_contagem_minima_recusa_corpo_truncado(csv_real: bytes, tmp_path: Path) -> None:
    """171 linhas com os defaults do contrato = truncamento (R2), não série."""
    _arquivar_fixture(csv_real, raiz=tmp_path)
    with pytest.raises(RespostaTruncada, match="mínimo esperado 170000"):
        td.extrair(offline=True, raiz=tmp_path, collected_at=COLETA, exigir_cobertura=False)


# ─────────────────────────────────────────────────────────────────────────────
# CA-022 — encoding explícito (latin-1), nunca o default do locale
# ─────────────────────────────────────────────────────────────────────────────


def test_ca022_encoding_declarado_e_latin1() -> None:
    """O contrato declara o encoding medido da fonte; o mapa de F-001 concorda."""
    from apps.pipeline.common import ENCODING_POR_FONTE

    assert td.CONFIG.encoding == "latin-1"
    assert ENCODING_POR_FONTE["TESOURO_CKAN"] == "latin-1"
    assert inspect.signature(td.ler_csv_bruto).parameters["encoding"].default == "latin-1"


def test_ca022_acento_latin1_sobrevive_e_utf8_levanta(csv_com_acento: bytes) -> None:
    """`Educação+` em latin-1 lê certo; o mesmo byte em utf-8 **levanta**, não vira mojibake."""
    quadro = td.ler_csv_bruto(csv_com_acento)
    assert quadro[td.COLUNA_TIPO].iloc[0] == "Tesouro Educação+"
    with pytest.raises(UnicodeDecodeError):
        td.ler_csv_bruto(csv_com_acento, encoding="utf-8")


def test_ca022_parse_nao_consulta_o_locale(
    csv_real: bytes, painel_real: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com o default do locale forçado a cp1252/ascii, o resultado tem de ser idêntico."""
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: "cp1252")  # noqa: ARG005
    sob_cp1252 = td.parse_painel(csv_real)
    monkeypatch.setattr(locale, "getpreferredencoding", lambda do_setlocale=True: "ascii")  # noqa: ARG005
    sob_ascii = td.parse_painel(csv_real)
    pd.testing.assert_frame_equal(sob_cp1252, painel_real)
    pd.testing.assert_frame_equal(sob_ascii, painel_real)


# ─────────────────────────────────────────────────────────────────────────────
# Painel → tabela longa e a convenção de `series_id` (insumo de F-016)
# ─────────────────────────────────────────────────────────────────────────────


def test_long_tem_as_8_colunas_do_schema_e_5_linhas_por_linha_do_painel(
    painel_real: pd.DataFrame,
) -> None:
    longo = td.para_long(painel_real, collected_at=COLETA)
    assert tuple(longo.columns) == td.COLUNAS_PROCESSADAS
    assert len(longo) == len(painel_real) * len(td.METRICA_POR_COLUNA) == 855
    assert longo["source"].unique().tolist() == ["TESOURO_CKAN"]
    assert longo["freq"].unique().tolist() == ["D"]
    assert not longo.duplicated(subset=["series_id", "date"]).any()


def test_long_passa_por_pandera(painel_real: pd.DataFrame) -> None:
    """`ProcessedSeriesSchema` com `strict=True`: coluna a mais ou a menos reprova o quadro."""
    longo = td.para_long(painel_real, collected_at=COLETA)
    validado = ProcessedSeriesSchema.validate(longo, lazy=True)
    assert len(validado) == len(longo)


def test_unidade_por_metrica(painel_real: pd.DataFrame) -> None:
    """Taxa em `%a.a.`, PU em `BRL` — unidade trocada é o erro de escala que não levanta sozinho."""
    longo = td.para_long(painel_real, collected_at=COLETA)
    unidades = longo.groupby(longo["series_id"].str.split("_").str[3:].str.join("_"))["unit"]
    assert unidades.unique().map(list).to_dict() == {
        "PU_BASE": ["BRL"],
        "PU_COMPRA": ["BRL"],
        "PU_VENDA": ["BRL"],
        "TAXA_COMPRA": ["%a.a."],
        "TAXA_VENDA": ["%a.a."],
    }


def test_series_id_composto_segue_a_convencao_documentada() -> None:
    """`TD_<SIGLA>_<AAAAMMDD>_<METRICA>` — é o contrato que F-016 vai consumir."""
    venc = date(2045, 5, 15)
    assert td.montar_series_id("NTNB", venc, "TAXA_VENDA") == "TD_NTNB_20450515_TAXA_VENDA"
    assert td.montar_series_id("LTN", date(2009, 1, 1), "PU_BASE") == "TD_LTN_20090101_PU_BASE"
    assert td.decompor_series_id("TD_NTNB_20450515_TAXA_VENDA") == (
        "NTNB",
        date(2045, 5, 15),
        "TAXA_VENDA",
    )


def test_series_id_do_painel_e_reversivel(painel_real: pd.DataFrame) -> None:
    """Todo `series_id` gravado volta a `(sigla, vencimento, métrica)` — sem perda."""
    longo = td.para_long(painel_real, collected_at=COLETA)
    for series_id in longo["series_id"].unique():
        sigla, vencimento, metrica = td.decompor_series_id(series_id)
        assert td.montar_series_id(sigla, vencimento, metrica) == series_id


@pytest.mark.parametrize(
    "ruim", ["NTNB_20450515_TAXA_VENDA", "TD_XPTO_20450515_TAXA_VENDA", "TD_NTNB_20450515_PRECO"]
)
def test_series_id_invalido_levanta(ruim: str) -> None:
    with pytest.raises(ErroDeExtracao):
        td.decompor_series_id(ruim)


# ─────────────────────────────────────────────────────────────────────────────
# Duplicidade e ordenação do índice temporal
# ─────────────────────────────────────────────────────────────────────────────


def test_duplicata_identica_e_descartada_e_contada(painel_real: pd.DataFrame) -> None:
    """Republicação byte-idêntica da mesma chave é ruído: descarta e conta."""
    dobrado = pd.concat([painel_real, painel_real], ignore_index=True)
    limpo, descartadas = td.deduplicar_painel(dobrado)
    assert descartadas == len(painel_real)
    assert len(limpo) == len(painel_real)


def test_duplicata_com_valor_divergente_levanta(painel_real: pd.DataFrame) -> None:
    """Mesma chave com taxa diferente é revisão: escolher uma das duas em silêncio é inventar."""
    conflito = painel_real.head(1).copy()
    conflito.loc[:, "TAXA_VENDA"] = 99.99
    with pytest.raises(FormatoInesperado, match="valores DIFERENTES"):
        td.deduplicar_painel(pd.concat([painel_real, conflito], ignore_index=True))


def test_painel_sai_ordenado_por_data_base(painel_real: pd.DataFrame) -> None:
    assert painel_real["data_base"].is_monotonic_increasing


# ─────────────────────────────────────────────────────────────────────────────
# Cache condicional / 304 (R21) — transporte falso, nenhuma rede
# ─────────────────────────────────────────────────────────────────────────────


def _arquivar_fixture(conteudo: bytes, *, raiz: Path, quando: date = date(2026, 10, 10)) -> Path:
    """Põe a fixture em `<raiz>/data/raw/tesouro-direto/` com manifesto, como o extrator faria."""
    from apps.pipeline.common import nome_arquivo_raw

    destino = caminho_destino_raw(td.CONFIG, raiz=raiz)
    resultado = arquivar_bruto(
        conteudo,
        destino=destino,
        nome=nome_arquivo_raw(td.IDENTIFICADOR_RAW, data_ref=quando, extensao=td.EXTENSAO_RAW),
        origem=td.CONFIG.base_url,
        obtido_em=COLETA,
        cabecalhos={"ETag": '"abc-123"', "Last-Modified": "Sat, 10 Oct 2026 10:22:11 GMT"},
    )
    return resultado.caminho


def test_config_declara_cache_condicional() -> None:
    """Sem `cache_condicional=True` o cliente ignora os validadores e baixa 14,6 MB por dia."""
    assert td.CONFIG.cache_condicional is True
    assert td.CONFIG.formato == "csv"
    assert td.CONFIG.destino_raw == "data/raw/tesouro-direto"


def test_304_reaproveita_o_arquivado_e_manda_os_dois_validadores(
    csv_real: bytes, tmp_path: Path
) -> None:
    """O caminho normal da fonte: revalida, recebe 304 e **não** transfere o arquivo."""
    arquivado = _arquivar_fixture(csv_real, raiz=tmp_path)
    transporte = TransporteGravado(_resposta(b"", status=304))

    resultado = td.baixar(
        transporte=transporte, data_ref=date(2026, 10, 11), raiz=tmp_path, forcar=False
    )

    enviados = transporte.chamadas[0]["cabecalhos"]
    assert enviados["If-None-Match"] == '"abc-123"'
    assert enviados["If-Modified-Since"] == "Sat, 10 Oct 2026 10:22:11 GMT"
    assert resultado.nao_modificada is True
    assert resultado.idempotente is True
    assert resultado.caminho == arquivado
    assert resultado.sha256 == sha256_de(csv_real)
    # Nada de novo em disco: o 304 não cria arquivo com a data de hoje.
    assert td.arquivos_arquivados(raiz=tmp_path) == [arquivado]


def test_forcar_ignora_os_validadores_condicionais(csv_real: bytes, tmp_path: Path) -> None:
    """`--forcar` existe para o dia em que o `ETag` mentir: baixa de novo, sem condicional."""
    _arquivar_fixture(csv_real, raiz=tmp_path)
    transporte = TransporteGravado(_resposta(csv_real, cabecalhos={"ETag": '"def-456"'}))

    resultado = td.baixar(
        transporte=transporte, data_ref=date(2026, 10, 11), raiz=tmp_path, forcar=True
    )

    enviados = transporte.chamadas[0]["cabecalhos"]
    assert "If-None-Match" not in enviados
    assert "If-Modified-Since" not in enviados
    assert resultado.nao_modificada is False
    assert len(td.arquivos_arquivados(raiz=tmp_path)) == 2


def test_primeiro_download_nao_manda_condicional(csv_real: bytes, tmp_path: Path) -> None:
    """Sem nada arquivado não há validador para mandar — e o arquivo tem de ser gravado."""
    transporte = TransporteGravado(_resposta(csv_real, cabecalhos={"ETag": '"abc-123"'}))
    resultado = td.baixar(transporte=transporte, data_ref=date(2026, 10, 10), raiz=tmp_path)
    assert "If-None-Match" not in transporte.chamadas[0]["cabecalhos"]
    assert resultado.caminho.read_bytes() == csv_real
    assert resultado.caminho.name == "precotaxatesourodireto__2026-10-10.csv"


def test_segundo_download_do_mesmo_dia_e_idempotente(csv_real: bytes, tmp_path: Path) -> None:
    """Conteúdo byte-idêntico no mesmo nome determinístico: não reescreve (CA-027 do F-001)."""
    transporte = TransporteGravado(
        _resposta(csv_real, cabecalhos={"ETag": '"abc-123"'}),
        _resposta(csv_real, cabecalhos={"ETag": '"abc-123"'}),
    )
    primeiro = td.baixar(transporte=transporte, data_ref=date(2026, 10, 10), raiz=tmp_path)
    segundo = td.baixar(
        transporte=transporte, data_ref=date(2026, 10, 10), raiz=tmp_path, forcar=True
    )
    assert primeiro.idempotente is False
    assert segundo.idempotente is True
    assert segundo.sha256 == primeiro.sha256


def test_ca045_sem_user_agent_nada_e_despachado(tmp_path: Path) -> None:
    """O CKAN é fonte que exige UA de browser no contrato: a guarda é asserção, não aviso."""
    from apps.pipeline.common import ClienteHTTP

    transporte = TransporteGravado(_resposta(b"Tipo Titulo;"))
    cliente = ClienteHTTP(td.CONFIG, transporte=transporte, cabecalhos_base={})
    with pytest.raises(UserAgentObrigatorio, match="sem User-Agent"):
        td.baixar(cliente=cliente, data_ref=date(2026, 10, 10), raiz=tmp_path)
    assert transporte.chamadas == []
    assert td.arquivos_arquivados(raiz=tmp_path) == []


# ─────────────────────────────────────────────────────────────────────────────
# Caminho de erro da fonte (R1 / CA-003) — nada chega a data/processed/
# ─────────────────────────────────────────────────────────────────────────────


def test_html_de_erro_do_ckan_e_recusado(html_de_erro: bytes) -> None:
    """A página de erro real do CKAN é HTML; `read_csv` a engoliria como uma coluna só."""
    assert html_de_erro.lstrip().startswith(b"<!DOCTYPE html>")
    with pytest.raises(FormatoInesperado, match="magic bytes indicam 'html'"):
        td.parse_painel(html_de_erro)


def test_html_de_erro_com_status_200_nao_grava_nada(html_de_erro: bytes, tmp_path: Path) -> None:
    """Corpo de erro com HTTP 200 é o modo de falha dominante do projeto (Anti-SPEC §10.1.5)."""
    transporte = TransporteGravado(_resposta(html_de_erro, status=200))
    with pytest.raises(FormatoInesperado):
        td.extrair(transporte=transporte, data_ref=date(2026, 10, 10), raiz=tmp_path)
    assert not caminho_processed(td.NOME_PROCESSADO, raiz=tmp_path).exists()
    assert td.arquivos_arquivados(raiz=tmp_path) == []


def test_corpo_vazio_e_recusado() -> None:
    """0 bytes onde se espera 14,6 MB não é 'dia sem divulgação': é falha."""
    with pytest.raises(RespostaDeErroComStatus200, match="corpo vazio"):
        td.parse_painel(b"")


def test_csv_sem_linha_de_dado_e_recusado() -> None:
    """Só o cabeçalho = painel vazio. Nada a gravar, e isso é erro, não sucesso vazio."""
    so_cabecalho = (";".join(td.COLUNAS_ESPERADAS) + "\n").encode("latin-1")
    painel = td.parse_painel(so_cabecalho)
    assert painel.empty
    with pytest.raises(RespostaDeErroComStatus200, match="painel vazio"):
        td.para_long(painel, collected_at=COLETA)


def test_offline_sem_bruto_arquivado_levanta(tmp_path: Path) -> None:
    """`--offline` numa máquina limpa não tem licença para inventar série."""
    with pytest.raises(ErroDeExtracao, match="sem bruto arquivado"):
        td.extrair(offline=True, raiz=tmp_path, collected_at=COLETA)


def test_p1_offline_sobre_bruto_orfao_e_recusado(csv_real: bytes, tmp_path: Path) -> None:
    """P1 de F-005: bruto **sem manifesto** é recusado, não datado pelo relógio da rodada.

    O caminho era alcançável de verdade, não hipotético: `caminho_bruto_mais_recente` aceita de
    propósito a amostra `data/raw/tesouro-direto/td.csv` deixada pela pesquisa — que existe na
    máquina e **não** tem `.meta.json`. Com o fallback antigo
    (`obtido_em_arquivado(...) or datetime.now(tz=UTC)`), `collected_at` saía do relógio **com
    microssegundos** e `vintage` deixava de ser a safra do dado: duas rodadas `--offline` sobre o
    mesmo bruto gravavam Parquets diferentes (D-b, CA-121, Anti-SPEC §10.4.22).

    Reprodução do QA em `ONDA-1-QA-B.md §6 (P1-1)`, agora como regressão: um `td.csv` órfão em
    `tmp_path`, nenhum `precotaxatesourodireto__*.csv` arquivado.
    """
    orfao = caminho_destino_raw(td.CONFIG, raiz=tmp_path)
    orfao.mkdir(parents=True)
    (orfao / "td.csv").write_bytes(csv_real)
    assert not list(orfao.glob("*.meta.json")), "o cenário é justamente o bruto sem manifesto"

    with pytest.raises(ManifestoAusente, match="bruto sem manifesto"):
        td.extrair(offline=True, raiz=tmp_path, minimo_linhas=150, exigir_cobertura=False)

    assert not caminho_processed("", raiz=tmp_path).exists(), (
        "a recusa não pode deixar rastro em data/processed/"
    )


def test_bruto_orfao_e_reprocessavel_com_collected_at_declarado(
    csv_real: bytes, tmp_path: Path
) -> None:
    """A recusa não é um beco sem saída: quem assume a safra por escrito reprocessa.

    É a diferença entre "o extrator inventou uma data" e "o operador declarou uma data" — e o
    Parquet continua byte-determinístico, porque `collected_at` passou a ser dado de entrada.
    """
    orfao = caminho_destino_raw(td.CONFIG, raiz=tmp_path)
    orfao.mkdir(parents=True)
    (orfao / "td.csv").write_bytes(csv_real)

    hashes = set()
    for _ in range(2):
        resultado = td.extrair(
            offline=True,
            raiz=tmp_path,
            collected_at=COLETA,
            minimo_linhas=150,
            exigir_cobertura=False,
        )
        quadro = pd.read_parquet(resultado.caminho_processado)
        assert (quadro["vintage"] == pd.Timestamp(COLETA.date())).all()
        hashes.add(sha256_de(resultado.caminho_processado.read_bytes()))
    assert len(hashes) == 1, "duas rodadas sobre o mesmo bruto têm de dar o mesmo Parquet"


# ─────────────────────────────────────────────────────────────────────────────
# Ponta a ponta sobre a fixture + idempotência do Parquet
# ─────────────────────────────────────────────────────────────────────────────


def test_defaults_de_extrair_sao_os_do_contrato() -> None:
    """Os afrouxamentos usados no teste e2e são **argumentos**, nunca o default do extrator."""
    parametros = inspect.signature(td.extrair).parameters
    assert parametros["minimo_linhas"].default is None
    assert parametros["exigir_cobertura"].default is True
    assert parametros["offline"].default is False


def test_extrair_offline_grava_parquet_validado(csv_real: bytes, tmp_path: Path) -> None:
    """Caminho completo sobre o recorte real: bruto → painel → longo → Parquet com pandera."""
    _arquivar_fixture(csv_real, raiz=tmp_path)
    resultado = td.extrair(
        offline=True,
        raiz=tmp_path,
        collected_at=COLETA,
        minimo_linhas=150,
        exigir_cobertura=False,
    )
    assert resultado.linhas_painel == 171
    assert resultado.linhas_long == 855
    assert resultado.series == 490
    assert resultado.data_base_min == date(2004, 12, 31)
    assert resultado.data_base_max == date(2026, 10, 9)
    assert resultado.caminho_processado == caminho_processed(td.NOME_PROCESSADO, raiz=tmp_path)

    relido = pd.read_parquet(resultado.caminho_processado)
    ProcessedSeriesSchema.validate(relido, lazy=True)
    canario = relido.loc[
        (relido["series_id"] == "TD_NTNB_20450515_TAXA_VENDA")
        & (relido["date"] == pd.Timestamp("2026-10-09"))
    ]
    assert float(canario["value"].iloc[0]) == pytest.approx(6.65)
    assert canario["unit"].iloc[0] == "%a.a."


def test_extrair_duas_vezes_produz_parquet_identico(csv_real: bytes, tmp_path: Path) -> None:
    """Idempotência (AGENTS §15.6): mesmo bruto + mesmo `collected_at` ⇒ mesmo sha256."""
    _arquivar_fixture(csv_real, raiz=tmp_path)
    argumentos = {
        "offline": True,
        "raiz": tmp_path,
        "collected_at": COLETA,
        "minimo_linhas": 150,
        "exigir_cobertura": False,
    }
    primeiro = td.extrair(**argumentos)  # type: ignore[arg-type]
    hash_1 = sha256_de(primeiro.caminho_processado.read_bytes())
    segundo = td.extrair(**argumentos)  # type: ignore[arg-type]
    hash_2 = sha256_de(segundo.caminho_processado.read_bytes())
    assert hash_1 == hash_2
    assert primeiro.linhas_long == segundo.linhas_long


def test_cli_aceita_offline_e_forcar() -> None:
    assert td._argumentos([]).offline is False
    assert td._argumentos(["--offline"]).offline is True
    assert td._argumentos(["--forcar"]).forcar is True


# ─────────────────────────────────────────────────────────────────────────────
# Rede / arquivo completo — fora do CI (`-m "not network"`)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_network_arquivo_completo_cobre_2006_e_2005() -> None:
    """CA-021 contra o arquivo real de 14,6 MB já arquivado em `data/raw/tesouro-direto/`."""
    conteudo = td.caminho_bruto_mais_recente().read_bytes()
    painel = td.parse_painel(conteudo)
    assert len(painel) >= td.CONTAGEM_MINIMA_LINHAS
    cobertura = td.exigir_cobertura_historica(painel)
    assert int(cobertura["dias_uteis_2006"]) >= 248  # type: ignore[arg-type]
    assert cobertura["data_base_min"] <= date(2005, 1, 3)  # type: ignore[operator]


@pytest.mark.network
def test_network_fonte_viva_responde_304_na_revalidacao() -> None:
    """Prova ao vivo de R21: com `If-None-Match` do manifesto, o CKAN devolve 304 e 0 byte."""
    from apps.pipeline.common import ClienteHTTP, validadores_condicionais

    arquivado = td.caminho_bruto_mais_recente()
    etag, last_modified = validadores_condicionais(arquivado)
    if not etag and not last_modified:
        pytest.skip(f"{arquivado.name} sem ETag/Last-Modified no manifesto")
    resposta = ClienteHTTP(td.CONFIG).get(etag=etag, last_modified=last_modified)
    assert resposta.nao_modificada is True
    assert resposta.conteudo == b""


@pytest.mark.network
def test_network_ponta_longa_nominal_de_2006_e_curta() -> None:
    """ADR-004 / L5, contra o arquivo completo: em 2006 a LTN ia a 2009 e a NTN-F a 2014."""
    painel = td.parse_painel(td.caminho_bruto_mais_recente().read_bytes())
    de_2006 = painel.loc[
        (painel["data_base"] >= date(2006, 1, 1)) & (painel["data_base"] <= date(2006, 12, 31))
    ]
    assert de_2006.loc[de_2006["sigla"] == "LTN", "data_vencimento"].max() == date(2009, 1, 1)
    assert de_2006.loc[de_2006["sigla"] == "NTNF", "data_vencimento"].max() == date(2014, 1, 1)
    assert de_2006.loc[de_2006["sigla"] == "NTNB", "data_vencimento"].max() == date(2045, 5, 15)
    assert de_2006.loc[de_2006["sigla"] == "NTNB", "data_vencimento"].nunique() == 10
