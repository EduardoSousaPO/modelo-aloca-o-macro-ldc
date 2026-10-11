"""Testes de F-006 — extrator dos índices da B3 (`apps/pipeline/extract/b3_indices.py`).

Um teste por CA da SPEC (CA-034..039), todos sobre as fixtures reais de `tests/fixtures/b3/`
(procedência em `tests/fixtures/b3/README.md`). **Nenhum teste deste arquivo abre socket**: o
transporte do `ClienteHTTP` é injetado e devolve a fixture gravada. A conferência contra a fonte
viva fica nos dois testes marcados `@pytest.mark.network`, excluídos do CI por
`-m "not network"`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from apps.pipeline.common import (
    ErroDeExtracao,
    FonteIndisponivel,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    ler_manifesto,
)
from apps.pipeline.extract.b3_indices import (
    ANO_INICIAL,
    PONTOS_MINIMOS_ANO_COMPLETO,
    ResultadoIndice,
    _anos_do_cli,
    config_extrator,
    desempacotar_matriz,
    exigir_datas_crescentes_e_unicas,
    extrair,
    extrair_indice,
    indices_do_catalogo,
    payload_b64,
    pontos_minimos_do_ano,
    validar_corpo_matriz,
)
from packages.shared.schemas import Fonte, StatusSerie, load_catalog

# ─────────────────────────────────────────────────────────────────────────────
# Infra do teste: transporte falso que devolve a fixture gravada
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dir_b3(dir_fixtures: Path) -> Path:
    """`tests/fixtures/b3/` — única origem de resposta da B3 neste arquivo."""
    return dir_fixtures / "b3"


def _corpo(dir_b3: Path, nome: str) -> bytes:
    return (dir_b3 / nome).read_bytes()


#: `(codigo, ano)` → nome do arquivo de fixture. O que não está aqui responde "ano sem série",
#: que é exatamente o que a B3 devolve para ano anterior ao início do índice.
FIXTURE_POR_ANO: dict[tuple[str, int], str] = {
    ("IBOV", 2006): "ibov_2006__2026-10-10.json",
    ("ICON", 2006): "icon_2006__2026-10-10.json",
    ("ICON", 2007): "icon_2007__2026-10-10.json",
    ("IMOB", 2007): "imob_2007__2026-10-10.json",
    ("IFIX", 2009): "ifix_2009__sem_serie__2026-10-10.json",
    ("IFIX", 2010): "ifix_2010__2026-10-10.json",
    ("IFIX", 2011): "ifix_2011__2026-10-10.json",
}

SEM_SERIE = b'{"min":null,"max":null,"results":null}'


class TransporteDeFixture:
    """Transporte falso: decodifica o payload da URL e devolve a fixture correspondente.

    Modelado no `TransporteGravado` de `tests/unit/test_common_http.py` (copiado, não importado:
    arquivo de teste não é módulo de infra). Registra as URLs pedidas para que o teste possa
    afirmar **quantas** requisições o extrator fez.
    """

    def __init__(self, dir_b3: Path, *, corpo_fixo: bytes | None = None) -> None:
        self._dir = dir_b3
        self._corpo_fixo = corpo_fixo
        self.chamadas: list[str] = []

    def __call__(
        self,
        metodo: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        dados: Mapping[str, Any] | None = None,
        cabecalhos: Mapping[str, str],
        timeout_s: float,
    ) -> RespostaBruta:
        import base64

        self.chamadas.append(url)
        assert metodo == "GET"
        assert "User-Agent" in cabecalhos, "a B3 exige UA de browser"
        assert cabecalhos.get("Referer", "").startswith("https://sistemaswebb3-listados.b3.com.br")
        if self._corpo_fixo is not None:
            conteudo = self._corpo_fixo
        else:
            pedido = json.loads(base64.b64decode(url.rsplit("/", 1)[-1]))
            chave = (pedido["index"], int(pedido["year"]))
            nome = FIXTURE_POR_ANO.get(chave)
            conteudo = _corpo(self._dir, nome) if nome else SEM_SERIE
        return RespostaBruta(
            url=url,
            status=200,
            conteudo=conteudo,
            cabecalhos={"Content-Type": "application/json; charset=utf-8"},
            obtida_em=datetime(2026, 10, 10, 20, 49, tzinfo=UTC),
        )


def _resposta(conteudo: bytes, *, url: str = "https://b3/teste") -> RespostaBruta:
    return RespostaBruta(url=url, status=200, conteudo=conteudo)


def _results(dir_b3: Path, nome: str) -> list[dict[str, Any]]:
    resultados = validar_corpo_matriz(_resposta(_corpo(dir_b3, nome)))
    assert resultados is not None
    return resultados


def _extrair_do_catalogo(
    codigo: str,
    anos: list[int],
    *,
    dir_b3: Path,
    raiz: Path,
    hoje: date = date(2026, 10, 10),
    gravar: bool = True,
) -> ResultadoIndice:
    """Roda `extrair_indice` para um código, com transporte de fixture e raiz temporária."""
    from apps.pipeline.common import ClienteHTTP

    entrada = next(e for e in indices_do_catalogo() if e.identificador == codigo)
    config = config_extrator([entrada])
    cliente = ClienteHTTP(
        config,
        transporte=TransporteDeFixture(dir_b3),
        cabecalhos_base={
            "User-Agent": "teste",
            "Referer": "https://sistemaswebb3-listados.b3.com.br/",
        },
        dormir=lambda _: None,
    )
    return extrair_indice(
        entrada,
        config=config,
        anos=anos,
        cliente=cliente,
        raiz=raiz,
        hoje=hoje,
        dormir=lambda _: None,
        pausa_s=0.0,
        gravar=gravar,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CA-034 — unpivot da matriz dia × mês
# ─────────────────────────────────────────────────────────────────────────────


def test_ca034_unpivot_ibov_2006_tem_246_pontos_e_o_canario_de_01_02(dir_b3: Path) -> None:
    """`IBOV`/2006: 246 pontos e `day=1, rateValue2 = "38.484,84"` → 2006-02-01 = 38484.84."""
    pontos = desempacotar_matriz(
        _results(dir_b3, "ibov_2006__2026-10-10.json"), codigo="IBOV", ano=2006
    )
    assert len(pontos) == 246
    por_data = dict(pontos)
    assert por_data[date(2006, 2, 1)] == pytest.approx(38484.84)
    assert min(por_data) == date(2006, 1, 2)
    assert max(por_data) == date(2006, 12, 28)


def test_ca034_rate_value_m_e_o_mes_m_nao_o_dia(dir_b3: Path) -> None:
    """`rateValue3` do `day=1` é 01/03, não 03/01 — trocar os eixos embaralharia a série toda."""
    resultados = _results(dir_b3, "ibov_2006__2026-10-10.json")
    dia1 = next(item for item in resultados if item["day"] == 1)
    assert dia1["rateValue3"] == "39.177,87"
    por_data = dict(desempacotar_matriz(resultados, codigo="IBOV", ano=2006))
    assert por_data[date(2006, 3, 1)] == pytest.approx(39177.87)
    assert date(2006, 1, 3) in por_data
    assert por_data[date(2006, 1, 3)] != pytest.approx(39177.87)


def test_ca034_serie_long_tem_as_8_colunas_do_contrato_e_passa_no_pandera(
    dir_b3: Path, tmp_path: Path
) -> None:
    """A gravação é feita por `gravar_processado_parquet` → `ProcessedSeriesSchema` validou."""
    import pandas as pd

    resultado = _extrair_do_catalogo("IBOV", [2006], dir_b3=dir_b3, raiz=tmp_path)
    assert resultado.caminho_parquet is not None
    quadro = pd.read_parquet(resultado.caminho_parquet)
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
    assert len(quadro) == 246
    assert set(quadro["series_id"]) == {"B3_IBOV"}
    assert set(quadro["source"]) == {Fonte.B3_API.value}
    assert set(quadro["freq"]) == {"D"}
    assert set(quadro["unit"]) == {"index"}
    # D-b: `vintage` = a data (sem hora) do `collected_at` do manifesto daquele ano. A B3 não
    # revisa fechamento de índice, mas a coluna segue a convenção única da camada processada.
    assert (quadro["vintage"] == pd.Timestamp("2026-10-10")).all()
    assert (quadro["vintage"] == quadro["vintage"].dt.normalize()).all(), "vintage não tem hora"
    assert (quadro["collected_at"] == pd.Timestamp("2026-10-10 20:49")).all()


# ─────────────────────────────────────────────────────────────────────────────
# CA-035 — número pt-BR
# ─────────────────────────────────────────────────────────────────────────────


def test_ca035_ponto_de_milhar_nunca_vira_decimal(dir_b3: Path) -> None:
    """`"38.484,84"` → `38484.84`. Se virasse `38.48`, o retorno de 2006 sairia 1000x errado."""
    por_data = dict(
        desempacotar_matriz(_results(dir_b3, "ibov_2006__2026-10-10.json"), codigo="IBOV", ano=2006)
    )
    valor = por_data[date(2006, 2, 1)]
    assert valor == pytest.approx(38484.84)
    assert valor > 1_000, f"escala errada: {valor}"
    # e o mesmo vale para o ponto-base, onde "1.000,00" poderia virar 1,0
    base = dict(
        desempacotar_matriz(_results(dir_b3, "ifix_2010__2026-10-10.json"), codigo="IFIX", ano=2010)
    )
    assert base[date(2010, 12, 30)] == pytest.approx(1000.00)


def test_ca035_todos_os_246_valores_de_2006_ficam_na_faixa_do_ibov(dir_b3: Path) -> None:
    """Guarda de escala sobre a série inteira: o IBOV de 2006 oscilou entre 32 mil e 45 mil."""
    valores = [
        v
        for _, v in desempacotar_matriz(
            _results(dir_b3, "ibov_2006__2026-10-10.json"), codigo="IBOV", ano=2006
        )
    ]
    assert len(valores) == 246
    assert min(valores) > 30_000
    assert max(valores) < 45_000


# ─────────────────────────────────────────────────────────────────────────────
# CA-036 — janela própria de ICON e IMOB (ADR-005)
# ─────────────────────────────────────────────────────────────────────────────


def test_ca036_icon_2006_traz_so_o_ponto_base_e_2007_a_serie(dir_b3: Path, tmp_path: Path) -> None:
    """ICON em 2006 é **um** ponto (28/12 = 1.000,00); a série efetiva começa em 2007."""
    so_2006 = dict(
        desempacotar_matriz(_results(dir_b3, "icon_2006__2026-10-10.json"), codigo="ICON", ano=2006)
    )
    assert list(so_2006) == [date(2006, 12, 28)]
    assert so_2006[date(2006, 12, 28)] == pytest.approx(1000.00)

    resultado = _extrair_do_catalogo("ICON", [2006, 2007], dir_b3=dir_b3, raiz=tmp_path)
    assert resultado.pontos_por_ano == {2006: 1, 2007: 245}
    assert resultado.data_inicio_observada == date(2006, 12, 28)
    assert resultado.primeiro_ano_efetivo == 2007, "ADR-005: janela própria, série de 2007"
    assert resultado.data_inicio_observada == resultado.data_inicio_catalogo


def test_ca036_imob_2007_traz_so_o_ponto_base(dir_b3: Path) -> None:
    """IMOB: base 28/12/2007 = 1.000,00 — 2006 e 2007 não têm série (ADR-005)."""
    so_2007 = dict(
        desempacotar_matriz(_results(dir_b3, "imob_2007__2026-10-10.json"), codigo="IMOB", ano=2007)
    )
    assert list(so_2007) == [date(2007, 12, 28)]
    assert so_2007[date(2007, 12, 28)] == pytest.approx(1000.00)


def test_ca036_nenhuma_linha_antes_do_data_inicio_mesmo_pedindo_2006(
    dir_b3: Path, tmp_path: Path
) -> None:
    """Pedir 2006-2010 para o IFIX **não** produz linha pré-2010 (Anti-SPEC §10.1.1)."""
    resultado = _extrair_do_catalogo(
        "IFIX", [2006, 2007, 2008, 2009, 2010, 2011], dir_b3=dir_b3, raiz=tmp_path
    )
    assert resultado.anos_sem_dado == (2006, 2007, 2008, 2009)
    assert resultado.data_inicio_observada == date(2010, 12, 30)
    assert resultado.linhas == 1 + 249


def test_ca036_pontos_minimos_do_ano_segue_o_data_inicio_do_catalogo() -> None:
    """A guarda anti-truncamento é o `data_inicio` do catálogo, não um número solto no código."""
    catalogo = {e.identificador: e for e in indices_do_catalogo()}
    icon, ibov = catalogo["ICON"], catalogo["IBOV"]
    hoje = date(2026, 10, 10)
    assert pontos_minimos_do_ano(2005, entrada=icon, hoje=hoje) == 0  # não existia
    assert pontos_minimos_do_ano(2006, entrada=icon, hoje=hoje) == 1  # ano-base
    assert pontos_minimos_do_ano(2007, entrada=icon, hoje=hoje) == PONTOS_MINIMOS_ANO_COMPLETO
    assert pontos_minimos_do_ano(2006, entrada=ibov, hoje=hoje) == PONTOS_MINIMOS_ANO_COMPLETO
    assert pontos_minimos_do_ano(2026, entrada=ibov, hoje=hoje) == 15 * 9  # 9 meses fechados
    assert pontos_minimos_do_ano(2027, entrada=ibov, hoje=hoje) == 0  # futuro


# ─────────────────────────────────────────────────────────────────────────────
# CA-037 — célula vazia é omitida, nunca zero
# ─────────────────────────────────────────────────────────────────────────────


def test_ca037_celula_nula_de_feriado_e_omitida_nunca_zero(dir_b3: Path) -> None:
    """Fevereiro tem 28 dias e 2006-01-01 foi domingo: nenhuma linha, nenhum `0.0`."""
    pontos = desempacotar_matriz(
        _results(dir_b3, "ibov_2006__2026-10-10.json"), codigo="IBOV", ano=2006
    )
    por_data = dict(pontos)
    dias_de_fevereiro = sorted(d.day for d in por_data if d.month == 2)
    assert max(dias_de_fevereiro) <= 28, "29/02 e 31/02 não existem em 2006 e não podem aparecer"
    assert date(2006, 1, 1) not in por_data, "feriado vem null → linha omitida"
    assert date(2006, 12, 25) not in por_data, "Natal vem null → linha omitida"
    assert all(v != 0.0 for _, v in pontos), "Anti-SPEC §10.1.4: ausência nunca é zero"
    assert len(pontos) == 246 < 365


def test_ca037_marcadores_de_ausencia_textual_tambem_somem() -> None:
    """`""`, `"-"`, `"ND"`, `"N/A"` → linha omitida (é o mapa `AUSENCIAS` da infra de F-001)."""
    sintetico = [
        {
            "day": 2,
            "rateValue1": "1.000,00",
            "rateValue2": "",
            "rateValue3": "-",
            "rateValue4": "ND",
            "rateValue5": "N/A",
            **{f"rateValue{m}": None for m in range(6, 13)},
        }
    ]
    pontos = desempacotar_matriz(sintetico, codigo="SINTETICO", ano=2020)
    assert pontos == [(date(2020, 1, 2), 1000.0)]


def test_ca037_valor_em_data_inexistente_levanta_em_vez_de_virar_linha_errada() -> None:
    """31 de fevereiro **com** valor é contradição da fonte: levanta, não arredonda para 28/02."""
    sintetico = [{"day": 31, "rateValue2": "1.234,56"}]
    with pytest.raises(ErroDeExtracao, match="data inexistente"):
        desempacotar_matriz(sintetico, codigo="SINTETICO", ano=2020)


# ─────────────────────────────────────────────────────────────────────────────
# CA-038 / CA-039 — IFIX com janela declarada
# ─────────────────────────────────────────────────────────────────────────────


def test_ca038_ifix_2010_so_ponto_base_e_2011_com_249_pontos(dir_b3: Path) -> None:
    """CA-038 literal: 2010 traz só 30/12 = 1.000,00; 2011 traz 249 pontos."""
    de_2010 = dict(
        desempacotar_matriz(_results(dir_b3, "ifix_2010__2026-10-10.json"), codigo="IFIX", ano=2010)
    )
    assert list(de_2010) == [date(2010, 12, 30)]
    assert de_2010[date(2010, 12, 30)] == pytest.approx(1000.00)

    de_2011 = desempacotar_matriz(
        _results(dir_b3, "ifix_2011__2026-10-10.json"), codigo="IFIX", ano=2011
    )
    assert len(de_2011) == 249
    assert de_2011[0][0] == date(2011, 1, 3)


def test_ca038_data_inicio_do_catalogo_do_ifix_e_2010_12_30() -> None:
    """O catálogo registra `data_inicio = 2010-12-30` — é o que F-017/ADR-005 consomem."""
    ifix = next(e for e in indices_do_catalogo() if e.identificador == "IFIX")
    assert ifix.data_inicio == date(2010, 12, 30)
    assert ifix.is_total_return is True
    assert ifix.item_email == "B5"


def test_ca039_resultado_declara_a_janela_observada_por_serie(dir_b3: Path, tmp_path: Path) -> None:
    """Quem for montar tabela/figura recebe `data_inicio_observada` e o 1º ano efetivo."""
    resultado = _extrair_do_catalogo("IFIX", [2009, 2010, 2011], dir_b3=dir_b3, raiz=tmp_path)
    assert resultado.data_inicio_observada == date(2010, 12, 30)
    assert resultado.data_fim_observada == date(2011, 12, 29)
    assert resultado.primeiro_ano_com_dado == 2010
    assert resultado.primeiro_ano_efetivo == 2011, "a janela honesta do IFIX começa em 2011"
    assert resultado.anos_sem_dado == (2009,)
    assert resultado.pct_nulos == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# HTTP 200 que não é sucesso (Anti-SPEC §10.1.5) e §10.4.27
# ─────────────────────────────────────────────────────────────────────────────


def test_corpo_vazio_com_http_200_e_recusado(dir_b3: Path) -> None:
    """Fixture real: payload base64 inválido → HTTP 200 com **zero** byte."""
    vazio = _corpo(dir_b3, "ibov__erro_corpo_vazio.json")
    assert vazio == b""
    with pytest.raises(RespostaDeErroComStatus200, match="corpo vazio"):
        validar_corpo_matriz(_resposta(vazio))


def test_html_da_spa_e_recusado_nao_scrapeado(dir_b3: Path) -> None:
    """Anti-SPEC §10.4.27: a página da B3 é shell Angular; o parser recusa em vez de raspar."""
    html = _corpo(dir_b3, "ibov__erro_html.txt")
    assert b"<!doctype html>" in html.lower()
    with pytest.raises(RespostaDeErroComStatus200, match="10.4.27"):
        validar_corpo_matriz(_resposta(html))


def test_results_null_e_ausencia_legitima_nao_erro(dir_b3: Path) -> None:
    """`{"results":null}` com HTTP 200 = ano sem série (IFIX/2009). Devolve `None`, não levanta."""
    corpo = _corpo(dir_b3, "ifix_2009__sem_serie__2026-10-10.json")
    assert validar_corpo_matriz(_resposta(corpo)) is None


def test_corpo_de_erro_json_sintetico_e_recusado() -> None:
    """Corpo `{"error": ...}` nunca foi observado na B3 — é a forma genérica de R1, sintética."""
    with pytest.raises(RespostaDeErroComStatus200, match="corpo de ERRO"):
        validar_corpo_matriz(_resposta(b'{"error":"invalid request","results":null}'))


def test_json_sem_a_chave_results_e_recusado() -> None:
    """Objeto JSON válido mas sem `results` é mudança de contrato, não série vazia."""
    with pytest.raises(RespostaDeErroComStatus200, match="sem a chave 'results'"):
        validar_corpo_matriz(_resposta(b'{"min":null,"max":null}'))


def test_json_invalido_e_recusado() -> None:
    """Corpo que não é JSON → recusa com diagnóstico, nunca parse parcial."""
    with pytest.raises(RespostaDeErroComStatus200, match="não é JSON válido"):
        validar_corpo_matriz(_resposta(b'{"results": [,,,'))


def test_indice_inexistente_devolve_o_mesmo_corpo_de_ano_sem_serie(dir_b3: Path) -> None:
    """Pegadinha medida: `XXXX` responde igual a um ano sem série — o corpo não distingue.

    Quem distingue é o catálogo: `extrair` recusa código desconhecido **antes** da requisição, e
    a guarda de contagem mínima mataria um código que devolvesse série vazia em todo ano.
    """
    corpo = _corpo(dir_b3, "xxxx_2006__erro_indice_inexistente.json")
    assert validar_corpo_matriz(_resposta(corpo)) is None
    assert corpo == _corpo(dir_b3, "ifix_2009__sem_serie__2026-10-10.json")
    with pytest.raises(ErroDeExtracao, match="não estão no catálogo"):
        extrair(codigos=["XXXX"], anos=[2006], offline=True)


def test_ano_que_deveria_ter_serie_e_volta_vazio_levanta_truncada(
    dir_b3: Path, tmp_path: Path
) -> None:
    """2012 do IFIX sem fixture → o transporte responde "sem série" e a guarda R2 dispara."""
    with pytest.raises(RespostaTruncada, match="'results: null'"):
        _extrair_do_catalogo("IFIX", [2011, 2012], dir_b3=dir_b3, raiz=tmp_path)


def test_ano_com_poucos_pontos_levanta_truncada(dir_b3: Path, tmp_path: Path) -> None:
    """ICON/2006 pedido como se fosse ano completo (hoje em 2008) → 1 ponto < 240 → levanta."""
    from apps.pipeline.common import ClienteHTTP

    entrada = next(e for e in indices_do_catalogo() if e.identificador == "ICON")
    config = config_extrator([entrada])
    cliente = ClienteHTTP(
        config,
        transporte=TransporteDeFixture(
            dir_b3, corpo_fixo=_corpo(dir_b3, "icon_2006__2026-10-10.json")
        ),
        cabecalhos_base={
            "User-Agent": "teste",
            "Referer": "https://sistemaswebb3-listados.b3.com.br/",
        },
        dormir=lambda _: None,
    )
    with pytest.raises(RespostaTruncada, match="mínimo esperado 240"):
        extrair_indice(
            entrada,
            config=config,
            anos=[2007],
            cliente=cliente,
            raiz=tmp_path,
            hoje=date(2008, 1, 10),
            dormir=lambda _: None,
            pausa_s=0.0,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Ordenação, duplicidade e idempotência (AGENTS.md §15.6/§15.7)
# ─────────────────────────────────────────────────────────────────────────────


def test_datas_repetidas_ou_fora_de_ordem_levantam() -> None:
    """A guarda que protege a concatenação dos 21 anos."""
    with pytest.raises(ErroDeExtracao, match="repetida"):
        exigir_datas_crescentes_e_unicas(
            [(date(2006, 1, 2), 1.0), (date(2006, 1, 2), 2.0)], origem="t"
        )
    with pytest.raises(ErroDeExtracao, match="fora de ordem"):
        exigir_datas_crescentes_e_unicas(
            [(date(2006, 1, 3), 1.0), (date(2006, 1, 2), 2.0)], origem="t"
        )


def test_serie_de_dois_anos_sai_ordenada_e_sem_duplicata(dir_b3: Path, tmp_path: Path) -> None:
    """A matriz chega fora de ordem (dia × mês); a série sai estritamente crescente."""
    import pandas as pd

    resultado = _extrair_do_catalogo("ICON", [2006, 2007], dir_b3=dir_b3, raiz=tmp_path)
    quadro = pd.read_parquet(resultado.caminho_parquet)
    assert quadro["date"].is_monotonic_increasing
    assert quadro["date"].is_unique
    assert len(quadro) == 246


def test_idempotencia_rodar_duas_vezes_da_o_mesmo_parquet_e_o_mesmo_raw(
    dir_b3: Path, tmp_path: Path
) -> None:
    """`AGENTS.md §15.6`: segunda rodada → bytes idênticos no bruto **e** no processado.

    O que faz isso valer é `collected_at` sair do manifesto do bruto, não do relógio da rodada.
    """
    from apps.pipeline.common import sha256_de

    primeiro = _extrair_do_catalogo("IBOV", [2006], dir_b3=dir_b3, raiz=tmp_path)
    assert primeiro.caminho_parquet is not None
    hash_parquet_1 = sha256_de(primeiro.caminho_parquet.read_bytes())
    bruto = tmp_path / "data" / "raw" / "b3" / "IBOV" / "2006.json"
    hash_bruto_1 = sha256_de(bruto.read_bytes())
    manifesto_1 = ler_manifesto(bruto)

    segundo = _extrair_do_catalogo("IBOV", [2006], dir_b3=dir_b3, raiz=tmp_path)
    assert sha256_de(segundo.caminho_parquet.read_bytes()) == hash_parquet_1  # type: ignore[union-attr]
    assert sha256_de(bruto.read_bytes()) == hash_bruto_1
    assert ler_manifesto(bruto) == manifesto_1
    assert segundo.linhas == primeiro.linhas == 246
    assert segundo.sha256_por_ano == primeiro.sha256_por_ano


def test_offline_relê_o_bruto_sem_tocar_a_rede(dir_b3: Path, tmp_path: Path) -> None:
    """`--offline` reconstrói a mesma série do bruto arquivado, com transporte ausente."""
    from apps.pipeline.common import sha256_de

    online = _extrair_do_catalogo("IFIX", [2010, 2011], dir_b3=dir_b3, raiz=tmp_path)
    entrada = next(e for e in indices_do_catalogo() if e.identificador == "IFIX")
    offline = extrair_indice(
        entrada,
        config=config_extrator([entrada]),
        anos=[2010, 2011],
        cliente=None,
        offline=True,
        raiz=tmp_path,
        hoje=date(2026, 10, 10),
    )
    assert offline.linhas == online.linhas == 250
    assert offline.sha256_por_ano == online.sha256_por_ano
    assert sha256_de(offline.caminho_parquet.read_bytes()) == sha256_de(  # type: ignore[union-attr]
        online.caminho_parquet.read_bytes()  # type: ignore[union-attr]
    )


def test_dc_offline_le_o_ano_e_nao_o_manifesto(dir_b3: Path, tmp_path: Path) -> None:
    """D-c: `<ano>.json.meta.json` convive com `<ano>.json` e o offline lê o dado, não o meta.

    A B3 reencontra o bruto pelo nome exato (`2011.json`), então não há glob a envenenar — o
    teste trava isso, e trava também que o `vintage` do offline sai do manifesto (D-b): duas
    rodadas sobre o mesmo bruto dão o mesmo Parquet.
    """
    import pandas as pd

    from apps.pipeline.common import sha256_de

    online = _extrair_do_catalogo("IFIX", [2010, 2011], dir_b3=dir_b3, raiz=tmp_path)
    pasta = tmp_path / "data" / "raw" / "b3" / "IFIX"
    assert sorted(a.name for a in pasta.iterdir()) == [
        "2010.json",
        "2010.json.meta.json",
        "2011.json",
        "2011.json.meta.json",
    ]
    entrada = next(e for e in indices_do_catalogo() if e.identificador == "IFIX")
    esperado = sha256_de(online.caminho_parquet.read_bytes())  # type: ignore[union-attr]
    for _ in range(2):
        offline = extrair_indice(
            entrada,
            config=config_extrator([entrada]),
            anos=[2010, 2011],
            cliente=None,
            offline=True,
            raiz=tmp_path,
            hoje=date(2026, 10, 10),
        )
        quadro = pd.read_parquet(offline.caminho_parquet)
        assert (quadro["vintage"] == pd.Timestamp("2026-10-10")).all()
        assert sha256_de(offline.caminho_parquet.read_bytes()) == esperado  # type: ignore[union-attr]


def test_offline_sem_bruto_de_ano_que_deveria_existir_levanta(tmp_path: Path) -> None:
    """Offline não é licença para série curta: bruto faltando em ano com série → erro."""
    entrada = next(e for e in indices_do_catalogo() if e.identificador == "IBOV")
    with pytest.raises(FonteIndisponivel, match="--offline"):
        extrair_indice(
            entrada,
            config=config_extrator([entrada]),
            anos=[2006],
            cliente=None,
            offline=True,
            raiz=tmp_path,
            hoje=date(2026, 10, 10),
        )


def test_uma_requisicao_por_indice_e_ano(dir_b3: Path, tmp_path: Path) -> None:
    """11 índices × 21 anos = 231 chamadas; aqui 1 índice × 3 anos = 3, uma por ano."""
    from apps.pipeline.common import ClienteHTTP

    entrada = next(e for e in indices_do_catalogo() if e.identificador == "IFIX")
    config = config_extrator([entrada])
    transporte = TransporteDeFixture(dir_b3)
    cliente = ClienteHTTP(
        config,
        transporte=transporte,
        cabecalhos_base={
            "User-Agent": "teste",
            "Referer": "https://sistemaswebb3-listados.b3.com.br/",
        },
        dormir=lambda _: None,
    )
    extrair_indice(
        entrada,
        config=config,
        anos=[2009, 2010, 2011],
        cliente=cliente,
        raiz=tmp_path,
        hoje=date(2026, 10, 10),
        dormir=lambda _: None,
        pausa_s=0.0,
    )
    assert len(transporte.chamadas) == 3
    assert len(set(transporte.chamadas)) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo, payload e CLI
# ─────────────────────────────────────────────────────────────────────────────


def test_universo_do_extrator_sai_do_catalogo_e_exclui_ifil_e_cotahist() -> None:
    """11 índices `ok`; `IFIL` (liquidez, não segmento) e `COTAHIST` (fase 2) ficam fora."""
    codigos = [e.identificador for e in indices_do_catalogo()]
    assert codigos == [
        "IBOV",
        "IDIV",
        "SMLL",
        "INDX",
        "IMAT",
        "IEEX",
        "IFNC",
        "UTIL",
        "ICON",
        "IMOB",
        "IFIX",
    ]
    assert "IEE" not in codigos, "R14: o código da energia elétrica é IEEX"
    assert "IFIL" not in codigos
    descartadas = {
        e.identificador
        for e in load_catalog()
        if e.fonte is Fonte.B3_API and e.status is not StatusSerie.OK
    }
    assert "IFIL" in descartadas
    assert any(d.startswith("COTAHIST") for d in descartadas)


def test_payload_b64_reproduz_o_payload_do_portal() -> None:
    """O base64 tem de decodificar exatamente para `{"language","index","year"}` com `year` str."""
    import base64

    bruto = base64.b64decode(payload_b64("IBOV", 2006)).decode("utf-8")
    assert json.loads(bruto) == {"language": "pt-br", "index": "IBOV", "year": "2006"}
    assert bruto == '{"language":"pt-br","index":"IBOV","year":"2006"}'


def test_config_do_extrator_declara_ua_de_browser_e_o_canario() -> None:
    """O contrato, não o código, diz UA obrigatório, destino do bruto e valor-canário."""
    config = config_extrator(indices_do_catalogo())
    assert config.requer_user_agent_browser is True
    assert config.destino_raw == "data/raw/b3"
    assert config.formato == "json"
    assert config.encoding == "utf-8"
    assert config.valor_canario == ("2006-02-01", 38484.84)
    assert config.contagem_minima_esperada == PONTOS_MINIMOS_ANO_COMPLETO
    assert len(config.series_ids) == 11


def test_anos_do_cli_aceita_ano_e_intervalo() -> None:
    """`--anos 2006 2011-2013` → `(2006, 2011, 2012, 2013)`; lixo levanta."""
    assert _anos_do_cli(["2006", "2011-2013"]) == (2006, 2011, 2012, 2013)
    assert _anos_do_cli(None) is None
    assert _anos_do_cli(["2006", "2006"]) == (2006,)
    with pytest.raises(ErroDeExtracao, match="AAAA"):
        _anos_do_cli(["ontem"])
    with pytest.raises(ErroDeExtracao, match="invertido"):
        _anos_do_cli(["2013-2011"])
    assert ANO_INICIAL == 2006


# ─────────────────────────────────────────────────────────────────────────────
# Rede — conferência da fixture contra a fonte viva (fora do CI)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_network_canario_ibov_01_02_2006_na_api_viva() -> None:
    """Valor-canário direto na B3: `IBOV`/2006, `day=1`, `rateValue2` = `"38.484,84"`."""
    from apps.pipeline.common import ClienteHTTP

    entrada = next(e for e in indices_do_catalogo() if e.identificador == "IBOV")
    config = config_extrator([entrada])
    cliente = ClienteHTTP(config)
    resposta = cliente.get(
        payload_b64("IBOV", 2006),
        cabecalhos_extra={"Referer": "https://sistemaswebb3-listados.b3.com.br/"},
    )
    resultados = validar_corpo_matriz(resposta, encoding=config.encoding)
    assert resultados is not None
    pontos = dict(desempacotar_matriz(resultados, codigo="IBOV", ano=2006))
    assert len(pontos) == 246
    assert pontos[date(2006, 2, 1)] == pytest.approx(38484.84)


@pytest.mark.network
def test_network_fixtures_continuam_batendo_com_a_fonte(dir_b3: Path) -> None:
    """Se a B3 mudar a resposta, é aqui que se descobre — não num número errado no relatório."""
    from apps.pipeline.common import ClienteHTTP, sha256_de

    casos = [
        ("IBOV", 2006, "ibov_2006__2026-10-10.json"),
        ("IFIX", 2011, "ifix_2011__2026-10-10.json"),
    ]
    entradas = indices_do_catalogo()
    config = config_extrator(entradas)
    cliente = ClienteHTTP(config)
    for codigo, ano, nome in casos:
        resposta = cliente.get(
            payload_b64(codigo, ano),
            cabecalhos_extra={"Referer": "https://sistemaswebb3-listados.b3.com.br/"},
        )
        assert sha256_de(resposta.conteudo) == sha256_de(_corpo(dir_b3, nome)), (
            f"{codigo}/{ano}: a resposta da B3 mudou — regrave a fixture e registre no "
            f"DECISIONS_LOG antes de seguir"
        )
