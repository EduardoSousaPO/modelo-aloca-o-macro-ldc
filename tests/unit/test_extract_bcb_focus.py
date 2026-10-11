"""Testes do extrator BCB Focus (F-010) — um por critério de aceite, sobre fixture gravada.

Nenhum teste deste arquivo abre socket, exceto os marcados `@pytest.mark.network` (que o CI N1
exclui com `-m "not network"`). O transporte é injetado: `TransporteDeFixture` devolve o corpo
real gravado em `tests/fixtures/focus/`, com o **status HTTP que a fonte devolveu de verdade**.

Procedência de cada fixture: `tests/fixtures/focus/README.md`.

Cobertura por CA:

- **CA-017** (`baseCalculo` único) — `test_basecalculo_0_e_1_na_mesma_data_viram_uma_linha`,
  `test_filtro_declara_basecalculo_unico`, `test_basecalculo_usado_esta_registrado_no_catalogo`,
  `test_base_calculo_divergente_e_contado_nao_silenciado`.
- **CA-018** (truncamento silencioso / paginação) —
  `test_pagina_com_20000_linhas_e_recusada`, `test_pagina_maior_que_o_top_e_recusada`,
  `test_montar_url_recusa_top_acima_da_pagina_maxima`,
  `test_paginacao_segue_enquanto_a_pagina_vem_cheia`, `test_pagina_curta_encerra_a_fatia`,
  `test_url_pagina_com_skip_e_sem_count_nem_apply`,
  `test_vazio_com_http_200_nao_passa_pela_contagem`.
- **CA-019** (nomes de campo canônicos) — `test_nomes_de_campo_normalizados_nos_5_entitysets`,
  `test_capitalizacao_minuscula_do_top5_tambem_normaliza`, `test_campo_desconhecido_levanta`,
  `test_indicador_enumerado_inclui_pib_total`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from apps.pipeline.common import (
    ClienteHTTP,
    ErroDeExtracao,
    FonteIndisponivel,
    ManifestoAusente,
    NumeroNaoReconhecido,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    arquivar_bruto,
    exigir_contagem_minima,
)
from apps.pipeline.extract.bcb_focus import (
    BASE_CALCULO,
    CAMPOS_CANONICOS,
    CANARIOS,
    GAP_MAXIMO_FOCUS_DIAS,
    INDICADORES_ENUMERADOS,
    LINHAS_SUSPEITAS_DE_TRUNCAMENTO,
    PAGINA_MAXIMA,
    PLANO,
    SERIES_PACOTE_MINIMO,
    URL_BASE_OLINDA,
    Escopo,
    catalogo_focus,
    chave_de_reuniao,
    chave_de_suavizada,
    conferir_canarios,
    config_para,
    decompor_series_id,
    deduplicar,
    descrever_url,
    extrair_serie,
    fatiar_por_ano,
    horizonte_anual,
    horizonte_mensal,
    horizonte_trimestral,
    montar_filtro,
    montar_series_id,
    montar_url,
    nome_bruto,
    normalizar_linha,
    plano_de,
    quadro_de_linhas,
    recusar_truncamento_silencioso,
    slug_indicador,
    transporte_do_bruto_arquivado,
    truncar_em,
    validar_continuidade,
    validar_corpo_odata,
)
from packages.shared.schemas import Fonte, Freq, StatusSerie, load_catalog

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "focus"
AGORA = datetime(2026, 10, 11, 3, 25, tzinfo=UTC)
FIM = date(2026, 10, 11)

PAGINAS_DE_40 = (
    "ExpectativasMercadoAnuais__2026-10-11__pagina-1-de-3.json",
    "ExpectativasMercadoAnuais__2026-10-11__pagina-2-de-3.json",
    "ExpectativasMercadoAnuais__2026-10-11__pagina-3-de-3.json",
)
"""As 3 páginas reais de `$top=40` (40 + 40 + 35 = 115 linhas) — o cenário de CA-018."""

QUATRO_INDICADORES = "ExpectativasMercadoAnuais__2026-10-11__quatro-indicadores.json"
"""Os 4 indicadores do plano anual (IPCA, Selic, PIB Total, Câmbio) em 2026-10-01/02, `bc=0`."""


# ─────────────────────────────────────────────────────────────────────────────
# Transporte falso (modelo de tests/unit/test_common_http.py, por desenho de F-001)
# ─────────────────────────────────────────────────────────────────────────────


class TransporteDeFixture:
    """Devolve o corpo gravado, opcionalmente por página e/ou recortado por `Indicador`.

    - `por_pagina` exercita o laço de paginação real de `baixar_indicador` com fixtures pequenas:
      a chave é o número de página (`$skip // $top`) lido da URL que o extrator montou;
    - `recortar_por_indicador=True` imita o `$filter=Indicador eq '…'` do Olinda sobre uma fixture
      que traz vários indicadores — é o que permite rodar `extrair_serie` ponta a ponta no
      EntitySet anual, que pede 4 indicadores em 4 requisições.
    """

    def __init__(
        self,
        conteudo: bytes | None = None,
        *,
        status: int = 200,
        por_pagina: Mapping[int, bytes] | None = None,
        recortar_por_indicador: bool = False,
    ) -> None:
        self._conteudo = conteudo
        self._status = status
        self._por_pagina = dict(por_pagina) if por_pagina else None
        self._recortar = recortar_por_indicador
        self.urls: list[str] = []

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
        del metodo, params, dados, cabecalhos, timeout_s
        self.urls.append(url)
        pedida = descrever_url(url)
        if self._por_pagina is not None:
            corpo = self._por_pagina.get(pedida.pagina, b'{"value":[]}')
        else:
            assert self._conteudo is not None
            corpo = self._conteudo if pedida.pagina == 0 else b'{"value":[]}'
        if self._recortar and pedida.indicador is not None:
            valores = json.loads(corpo.decode("utf-8"))["value"]
            do_indicador = [v for v in valores if v.get("Indicador") == pedida.indicador]
            corpo = json.dumps({"value": do_indicador}, ensure_ascii=False).encode("utf-8")
        return RespostaBruta(
            url=url,
            status=self._status,
            conteudo=corpo,
            cabecalhos={"Content-Type": "application/json"},
            obtida_em=AGORA,
        )


def ler(nome: str) -> bytes:
    """Corpo bruto da fixture, byte a byte."""
    return (FIXTURES / nome).read_bytes()


def linhas(nome: str) -> list[dict[str, Any]]:
    """`value` da fixture, sem passar pelo extrator (para montar entradas de teste)."""
    return list(json.loads(ler(nome).decode("utf-8"))["value"])


def resposta(nome: str, *, status: int = 200) -> RespostaBruta:
    return RespostaBruta(
        url=f"file://{nome}",
        status=status,
        conteudo=ler(nome),
        cabecalhos={},
        obtida_em=AGORA,
    )


def entrada_do_catalogo(series_id: str):  # noqa: ANN201 - SeriesCatalogEntry
    """Entrada do catálogo real — nunca um `SeriesCatalogEntry` montado à mão."""
    return catalogo_focus([series_id])[0]


# ─────────────────────────────────────────────────────────────────────────────
# CA-019 — nomes de campo canônicos
# ─────────────────────────────────────────────────────────────────────────────

FIXTURES_DOS_5 = {
    "FOCUS_ANUAIS": "ExpectativasMercadoAnuais__2026-10-11__2006-01.json",
    "FOCUS_MENSAIS": "ExpectativaMercadoMensais__2026-10-11.json",
    "FOCUS_TRIMESTRAIS": "ExpectativasMercadoTrimestrais__2026-10-11.json",
    "FOCUS_SELIC": "ExpectativasMercadoSelic__2026-10-11.json",
    "FOCUS_INFLACAO_12M": "ExpectativasMercadoInflacao12Meses__2026-10-11.json",
}
"""Uma fixture real por EntitySet em escopo — os "5 EntitySets" de CA-019."""


@pytest.mark.parametrize("series_id", sorted(FIXTURES_DOS_5))
def test_nomes_de_campo_normalizados_nos_5_entitysets(series_id: str) -> None:
    """CA-019: os 5 EntitySets saem com nome canônico em `snake_case`, nenhum nome cru."""
    canonicos = set(CAMPOS_CANONICOS.values())
    for crua in linhas(FIXTURES_DOS_5[series_id]):
        normalizada = normalizar_linha(crua, origem=series_id)
        assert set(normalizada) <= canonicos
        assert "indicador" in normalizada
        assert "data" in normalizada
        assert "mediana" in normalizada
        assert "base_calculo" in normalizada
        # nenhum nome da fonte sobreviveu
        assert not any(c[0].isupper() for c in normalizada)
        assert "numeroRespondentes" not in normalizada
        assert "numero_respondentes" in normalizada


def test_capitalizacao_minuscula_do_top5_tambem_normaliza() -> None:
    """`ExpectativasMercadoTop5Selic` traz `indicador`/`reuniao`/`mediana` em caixa baixa.

    Entrada em memória de propósito: é a forma documentada em `fontes-de-dados.md §A2` para os
    EntitySets Top5, que estão **fora** do escopo de F-010 — não há dado nosso para virar fixture,
    e a tabela de normalização tem de aguentar a variação de qualquer jeito.
    """
    normalizada = normalizar_linha(
        {
            "indicador": "Selic",
            "Data": "2026-10-02",
            "reuniao": "R1/2027",
            "tipoCalculo": "C",
            "media": 11.7,
            "mediana": 11.75,
            "desvioPadrao": 0.7,
        },
        origem="top5",
    )
    assert normalizada["indicador"] == "Selic"
    assert normalizada["reuniao"] == "R1/2027"
    assert normalizada["mediana"] == 11.75
    assert normalizada["desvio_padrao"] == 0.7


def test_campo_desconhecido_levanta() -> None:
    """Campo novo no EntitySet é falha, não coluna fantasma com nome cru."""
    with pytest.raises(RespostaDeErroComStatus200, match="CAMPOS_CANONICOS"):
        normalizar_linha({"Indicador": "IPCA", "CampoNovoDoBacen": 1}, origem="x")


def test_dois_campos_que_colapsam_no_mesmo_canonico_levantam() -> None:
    """`Mediana` e `mediana` na mesma linha seria ambiguidade silenciosa."""
    with pytest.raises(RespostaDeErroComStatus200, match="colapsam"):
        normalizar_linha({"Mediana": 1.0, "mediana": 2.0}, origem="x")


def test_indicador_enumerado_inclui_pib_total() -> None:
    """G-04 resolvido: o rótulo é `PIB Total`, nos EntitySets anual e trimestral."""
    assert "PIB Total" in INDICADORES_ENUMERADOS["ExpectativasMercadoAnuais"]
    assert "PIB Total" in INDICADORES_ENUMERADOS["ExpectativasMercadoTrimestrais"]
    assert INDICADORES_ENUMERADOS["ExpectativasMercadoSelic"] == ("Selic",)
    # o plano só pede indicador que a enumeração conhece
    for series_id, plano in PLANO.items():
        conhecidos = INDICADORES_ENUMERADOS[plano.entityset]
        for pedido in plano.pedidos:
            assert pedido.indicador in conhecidos, f"{series_id}: {pedido.indicador}"


def test_slug_do_indicador_tira_acento_e_nao_cria_hifen() -> None:
    """`series_id` é `^[A-Z0-9_\\.\\^=\\-]+$`, e o hífen é reservado à chave de reunião."""
    assert slug_indicador("Câmbio") == "CAMBIO"
    assert slug_indicador("PIB Total") == "PIB_TOTAL"
    assert slug_indicador("IPC-Fipe") == "IPC_FIPE"
    assert "-" not in slug_indicador("PIB Agropecuária")


# ─────────────────────────────────────────────────────────────────────────────
# CA-017 — `baseCalculo` único
# ─────────────────────────────────────────────────────────────────────────────


def test_basecalculo_0_e_1_na_mesma_data_viram_uma_linha() -> None:
    """CA-017: a fixture tem `bc` 0 **e** 1 para a mesma `Data`+`DataReferencia`; sai 1 linha."""
    cruas = linhas("ExpectativasMercadoAnuais__2026-10-11__basecalculo-0-e-1.json")
    bases = {linha["baseCalculo"] for linha in cruas}
    assert bases == {0, 1}, "a fixture deixou de exercitar o caso"
    duplicadas = [
        linha
        for linha in cruas
        if linha["Data"] == "2026-10-01" and linha["DataReferencia"] == "2026"
    ]
    assert len(duplicadas) == 2  # noqa: PLR2004 - é literalmente o par 0/1 do CA

    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    quadro, descartes = quadro_de_linhas(entrada, plano_de(entrada), cruas, collected_at=AGORA)
    assert not quadro.duplicated(subset=["series_id", "date"]).any()
    do_dia = quadro.loc[
        (quadro["series_id"] == "FOCUS_A_IPCA_H0") & (quadro["date"] == pd.Timestamp("2026-10-01"))
    ]
    assert len(do_dia) == 1
    # a linha que ficou é a de baseCalculo=0 (mediana 5.0), não a de bc=1 (5.1)
    assert float(do_dia["value"].iloc[0]) == pytest.approx(5.0)
    assert descartes.base_calculo_divergente == len(
        [linha for linha in cruas if linha["baseCalculo"] != BASE_CALCULO]
    )


def test_base_calculo_divergente_e_contado_nao_silenciado() -> None:
    """A linha de `bc=1` descartada aparece no relatório — descarte contado, nunca invisível."""
    cruas = linhas("ExpectativasMercadoAnuais__2026-10-11__basecalculo-0-e-1.json")
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    _, descartes = quadro_de_linhas(entrada, plano_de(entrada), cruas, collected_at=AGORA)
    assert descartes.base_calculo_divergente > 0


def test_filtro_declara_basecalculo_unico() -> None:
    """CA-017 no `$filter`: a cláusula pede um `baseCalculo` só, e `Data` é string com aspas."""
    filtro = montar_filtro(indicador="IPCA", inicio=date(2006, 1, 1), fim=date(2006, 12, 31))
    assert f"baseCalculo eq {BASE_CALCULO}" in filtro
    assert "Indicador eq 'IPCA'" in filtro
    assert "Data ge '2006-01-01'" in filtro
    assert "Data le '2006-12-31'" in filtro
    assert "datetime" not in filtro


def test_basecalculo_usado_esta_registrado_no_catalogo() -> None:
    """CA-017 pede que o `baseCalculo` usado esteja **registrado**; o catálogo o registra."""
    assert BASE_CALCULO == 0
    obs = (entrada_do_catalogo("FOCUS_ANUAIS").obs or "").lower()
    assert "basecalculo" in obs.replace(" ", "")


# ─────────────────────────────────────────────────────────────────────────────
# CA-018 — truncamento silencioso e paginação
# ─────────────────────────────────────────────────────────────────────────────


def test_pagina_com_20000_linhas_e_recusada() -> None:
    """CA-018 (negativo): exatamente 20.000 linhas é o corte sem `nextLink` — recusa, não concat.

    A fixture correspondente teria ~1,5 MB e o diretório é limitado a 200 KB
    (`tests/fixtures/README.md`), então a guarda é exercitada direto. A medição ao vivo que a
    justifica está repetida em `test_top_20000_trunca_sem_nextlink` (`@pytest.mark.network`).
    """
    with pytest.raises(RespostaTruncada, match="truncamento silencioso"):
        recusar_truncamento_silencioso(
            LINHAS_SUSPEITAS_DE_TRUNCAMENTO, top=PAGINA_MAXIMA, origem="teste"
        )


def test_pagina_maior_que_o_top_e_recusada() -> None:
    """Se o Olinda ignorar o `$top` (como já ignora `$count`/`$apply`), `$skip` não é confiável."""
    with pytest.raises(RespostaTruncada, match="ignorou o \\$top"):
        recusar_truncamento_silencioso(41, top=40, origem="teste")


def test_pagina_dentro_do_top_passa() -> None:
    """O caminho normal: página curta e página cheia (mas ≤ `$top`) são aceitas."""
    assert recusar_truncamento_silencioso(35, top=40, origem="t") == 35  # noqa: PLR2004
    assert recusar_truncamento_silencioso(40, top=40, origem="t") == 40  # noqa: PLR2004


def test_montar_url_recusa_top_acima_da_pagina_maxima() -> None:
    """Ninguém consegue pedir `$top=20000` por este módulo — é erro de programação."""
    with pytest.raises(ErroDeExtracao, match="PAGINA_MAXIMA"):
        montar_url(
            "ExpectativasMercadoAnuais",
            indicador="IPCA",
            inicio=date(2006, 1, 1),
            fim=date(2006, 12, 31),
            pagina=0,
            top=LINHAS_SUSPEITAS_DE_TRUNCAMENTO,
        )


def test_url_pagina_com_skip_e_sem_count_nem_apply() -> None:
    """A URL pagina com `$skip`/`$top` e não usa o que a fonte ignora em silêncio."""
    url = montar_url(
        "ExpectativasMercadoAnuais",
        indicador="Câmbio",
        inicio=date(2006, 1, 1),
        fim=date(2006, 12, 31),
        pagina=3,
        top=10000,
    )
    assert url.startswith(f"{URL_BASE_OLINDA}/ExpectativasMercadoAnuais?")
    assert "$top=10000" in url
    assert "$skip=30000" in url
    assert "$count" not in url
    assert "$apply" not in url
    # pegadinha nº 2: espaço vira %20, nunca '+'
    assert "%20" in url
    assert "+" not in url
    # acento percent-encodado em UTF-8
    assert "C%C3%A2mbio" in url


def test_paginacao_segue_enquanto_a_pagina_vem_cheia(tmp_path: Path) -> None:
    """CA-018: 3 páginas reais (40 + 40 + 35) viram 115 linhas e **3** requisições.

    É o cenário que `$top=20000` quebra: se o laço tratasse página cheia como última, pararia em
    40 linhas sem nenhum sinal de erro.
    """
    from apps.pipeline.extract.bcb_focus import baixar_indicador

    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    plano = plano_de(entrada)
    pedido = next(p for p in plano.pedidos if p.indicador == "Selic")
    transporte = TransporteDeFixture(
        por_pagina={i: ler(nome) for i, nome in enumerate(PAGINAS_DE_40)}
    )
    cliente = ClienteHTTP(config_para(entrada, fim=FIM), transporte=transporte)

    cruas, paginas = baixar_indicador(
        plano,
        pedido,
        cliente=cliente,
        destino=tmp_path,
        inicio=date(2026, 9, 1),
        fim=date(2026, 10, 2),
        top=40,
    )
    assert len(transporte.urls) == 3  # noqa: PLR2004
    assert [p.linhas for p in paginas] == [40, 40, 35]
    assert len(cruas) == 115  # noqa: PLR2004
    assert all((tmp_path / p.arquivo).is_file() for p in paginas)


def test_pagina_curta_encerra_a_fatia(tmp_path: Path) -> None:
    """Página curta é o **único** sinal de fim que esta fonte dá — e basta uma requisição."""
    from apps.pipeline.extract.bcb_focus import baixar_indicador

    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    plano = plano_de(entrada)
    pedido = next(p for p in plano.pedidos if p.indicador == "Selic")
    transporte = TransporteDeFixture(por_pagina={0: ler(PAGINAS_DE_40[2])})
    cliente = ClienteHTTP(config_para(entrada, fim=FIM), transporte=transporte)

    cruas, paginas = baixar_indicador(
        plano,
        pedido,
        cliente=cliente,
        destino=tmp_path,
        inicio=date(2026, 9, 1),
        fim=date(2026, 10, 2),
        top=40,
    )
    assert len(transporte.urls) == 1
    assert len(cruas) == 35  # noqa: PLR2004
    assert len(paginas) == 1


def test_vazio_com_http_200_nao_passa_pela_contagem() -> None:
    """`{"value":[]}` com HTTP 200 é o vazio silencioso do Olinda (R2) — a contagem o pega."""
    corpo = validar_corpo_odata(resposta("ExpectativasMercadoAnuais__vazio.json"))
    assert corpo == []
    with pytest.raises(RespostaTruncada, match="truncamento silencioso"):
        exigir_contagem_minima(len(corpo), minimo=100, origem="focus vazio")


def test_config_liga_pagina_com_skip_e_declara_piso() -> None:
    """O `ExtractorConfig` carrega a pegadinha: `pagina_com_skip` e piso de contagem."""
    config = config_para(entrada_do_catalogo("FOCUS_ANUAIS"), fim=FIM)
    assert config.pagina_com_skip is True
    assert config.janela_maxima_dias is None
    assert config.fonte is Fonte.BCB_OLINDA
    assert config.contagem_minima_esperada is not None
    assert config.contagem_minima_esperada > 10_000  # 8 séries densas × 20+ anos de dia útil
    assert config.destino_raw == "data/raw/focus"


# ─────────────────────────────────────────────────────────────────────────────
# Guardas de resposta (R1, Anti-SPEC §10.1.5)
# ─────────────────────────────────────────────────────────────────────────────


def test_corpo_de_erro_embrulhado_em_comentario_e_recusado() -> None:
    """O erro do Olinda é `/*{...}*/` — não é JSON válido nem HTML, e tem mensagem própria."""
    with pytest.raises(RespostaDeErroComStatus200, match="embrulhado em comentário"):
        validar_corpo_odata(resposta("ExpectativasMercadoAnuais__erro.json", status=400))


def test_erro_do_orderby_com_mais_e_recusado() -> None:
    """Registra a pegadinha do `+`: espaço codificado como `+` devolve 400 com corpo `/*…*/`."""
    bruto = ler("ExpectativasMercadoAnuais__erro_orderby_mais.json")
    assert b"Data+asc" in bruto
    with pytest.raises(RespostaDeErroComStatus200, match="ERRO do Olinda"):
        validar_corpo_odata(
            resposta("ExpectativasMercadoAnuais__erro_orderby_mais.json", status=400)
        )


def test_corpo_html_e_recusado() -> None:
    """Página de erro em HTML/XML servida no lugar do JSON (R1)."""
    html = RespostaBruta(
        url="x", status=200, conteudo=b"<html><body>Requisicao Invalida</body></html>"
    )
    with pytest.raises(RespostaDeErroComStatus200, match="HTML/XML"):
        validar_corpo_odata(html)


def test_corpo_vazio_e_recusado() -> None:
    with pytest.raises(RespostaDeErroComStatus200, match="corpo vazio"):
        validar_corpo_odata(RespostaBruta(url="x", status=200, conteudo=b"   "))


def test_array_no_topo_e_recusado() -> None:
    """A resposta de sucesso do Olinda é objeto com `value`, não array — array é outra coisa."""
    with pytest.raises(RespostaDeErroComStatus200, match="esperado objeto OData"):
        validar_corpo_odata(RespostaBruta(url="x", status=200, conteudo=b"[]"))


def test_objeto_sem_value_e_recusado() -> None:
    with pytest.raises(RespostaDeErroComStatus200, match="sem lista em 'value'"):
        validar_corpo_odata(RespostaBruta(url="x", status=200, conteudo=b'{"@odata.context":"x"}'))


def test_json_invalido_e_recusado() -> None:
    with pytest.raises(RespostaDeErroComStatus200, match="não é JSON válido"):
        validar_corpo_odata(RespostaBruta(url="x", status=200, conteudo=b'{"value": [,]}'))


def test_http_400_nao_e_retentado_e_falha_alto() -> None:
    """HTTP 400 do Olinda não é transitório: `ClienteHTTP` levanta sem repetir."""
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    transporte = TransporteDeFixture(ler("ExpectativasMercadoAnuais__erro.json"), status=400)
    cliente = ClienteHTTP(config_para(entrada, fim=FIM), transporte=transporte)
    with pytest.raises(FonteIndisponivel, match="HTTP 400"):
        cliente.get(
            montar_url(
                "ExpectativasMercadoAnuais",
                indicador="IPCA",
                inicio=date(2006, 1, 1),
                fim=date(2006, 12, 31),
                pagina=0,
                top=40,
            )
        )
    assert len(transporte.urls) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Data da pesquisa, ponto decimal e horizonte
# ─────────────────────────────────────────────────────────────────────────────


def test_date_e_a_data_da_pesquisa_nao_fim_de_periodo() -> None:
    """A convenção do Focus: `date` = `Data` (dia da pesquisa), `freq=D`, horizonte no `series_id`.

    É o oposto de D-a de propósito (`bcb_sgs.fim_do_periodo`): converter para fim de período
    destruiria a propriedade de §1.5 (a mediana do dia X era conhecida no dia X) e colapsaria H0 e
    H1 na mesma data.
    """
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    quadro, _ = quadro_de_linhas(
        entrada,
        plano_de(entrada),
        linhas("ExpectativasMercadoAnuais__2026-10-11__2006-01.json"),
        collected_at=AGORA,
    )
    assert set(quadro["freq"]) == {Freq.DIARIA.value}
    assert set(quadro["source"]) == {Fonte.BCB_OLINDA.value}
    # 2006-01-02 é dia 2, não 31/01 nem 31/12
    # a fonte publica a pesquisa todo dia útil, e cada dia é uma observação própria:
    # 02, 03, 04 e 05 de janeiro de 2006 estão todos ali, nenhum colapsado em 31/01
    assert {pd.Timestamp(d) for d in ("2006-01-02", "2006-01-03", "2006-01-04", "2006-01-05")} <= (
        set(quadro["date"])
    )
    assert quadro["date"].nunique() == 22  # noqa: PLR2004 - os 22 dias úteis de jan/2006
    # e o par (H0, H1) existe na MESMA data — o que fim de período impossibilitaria
    do_dia = quadro.loc[quadro["date"] == pd.Timestamp("2006-01-02"), "series_id"]
    assert {"FOCUS_A_IPCA_H0", "FOCUS_A_IPCA_H1"} <= set(do_dia)


def test_mediana_do_primeiro_dia_util_de_2006_bate_com_a_fonte() -> None:
    """Canário de 1T2006: IPCA ano-corrente em 2006-01-02 = 4,50 (ponto decimal, não 450)."""
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    quadro, _ = quadro_de_linhas(
        entrada,
        plano_de(entrada),
        linhas("ExpectativasMercadoAnuais__2026-10-11__2006-01.json"),
        collected_at=AGORA,
    )
    valor = quadro.loc[
        (quadro["series_id"] == "FOCUS_A_IPCA_H0") & (quadro["date"] == pd.Timestamp("2006-01-02")),
        "value",
    ]
    assert float(valor.iloc[0]) == pytest.approx(4.50)


def test_mediana_com_virgula_decimal_levanta() -> None:
    """O JSON do Olinda usa **ponto** decimal e número tipado; vírgula aqui é pt-BR mal lido.

    `para_float_ptbr` leria `"4.50"` como 450 — a troca não explode, muda a escala em silêncio.
    Este teste trava o lado certo: entrada com vírgula tem de falhar.
    """
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    crua = dict(
        next(
            linha
            for linha in linhas("ExpectativasMercadoAnuais__2026-10-11__2006-01.json")
            if linha["Data"] == "2006-01-02" and linha["DataReferencia"] == "2006"
        )
    )
    crua["Mediana"] = "4,50"
    with pytest.raises(NumeroNaoReconhecido):
        quadro_de_linhas(entrada, plano_de(entrada), [crua], collected_at=AGORA)


def test_horizonte_anual_mensal_e_trimestral() -> None:
    """Horizonte = `DataReferencia` − `Data`, calculado **da data da pesquisa** (sem look-ahead)."""
    assert horizonte_anual(date(2026, 10, 2), "2026") == 0
    assert horizonte_anual(date(2026, 10, 2), "2027") == 1
    assert horizonte_anual(date(2006, 1, 2), "2005") == -1
    assert horizonte_mensal(date(2026, 10, 2), "10/2026") == 0
    assert horizonte_mensal(date(2026, 10, 2), "11/2026") == 1
    assert horizonte_mensal(date(2026, 10, 2), "09/2028") == 23  # noqa: PLR2004
    # trimestral vem sem zero à esquerda: '3/2026' é o 3º trimestre
    assert horizonte_trimestral(date(2026, 10, 2), "4/2026") == 0
    assert horizonte_trimestral(date(2026, 10, 2), "3/2026") == -1
    assert horizonte_trimestral(date(2006, 1, 2), "4/2005") == -1


@pytest.mark.parametrize(
    ("funcao", "referencia"),
    [
        (horizonte_anual, "26"),
        (horizonte_mensal, "2026-10"),
        (horizonte_trimestral, "9/2026"),
        (horizonte_trimestral, "09/2026"),
    ],
)
def test_data_referencia_fora_do_formato_levanta(funcao, referencia: str) -> None:  # noqa: ANN001
    """Formato de `DataReferencia` é declarado por escopo, nunca inferido (R12)."""
    with pytest.raises(RespostaDeErroComStatus200, match="DataReferencia"):
        funcao(date(2026, 10, 2), referencia)


def test_chave_de_reuniao_e_de_suavizada() -> None:
    """`R1/2027` → `R1-2027` (absoluta) e `Suavizada` S/N tal e qual."""
    assert chave_de_reuniao("R1/2027") == "R1-2027"
    assert chave_de_reuniao("R10/2027") == "R10-2027"
    assert chave_de_suavizada("S") == "S"
    assert chave_de_suavizada("n") == "N"
    with pytest.raises(RespostaDeErroComStatus200, match="Reuniao"):
        chave_de_reuniao("1/2027")
    with pytest.raises(RespostaDeErroComStatus200, match="Suavizada"):
        chave_de_suavizada("X")


def test_series_id_composto_vai_e_volta() -> None:
    """`decompor_series_id` é o inverso exato — é o que F-015 usa para ler o horizonte."""
    for escopo, indicador, chave in [
        (Escopo.ANUAL, "IPCA", "H0"),
        (Escopo.ANUAL, "PIB Total", "H1"),
        (Escopo.TRIMESTRAL, "PIB Total", "HM1"),
        (Escopo.INFLACAO_12M, "IPCA", "S"),
        (Escopo.REUNIAO_COPOM, "Selic", "R1-2027"),
    ]:
        series_id = montar_series_id(escopo, indicador, chave)
        assert decompor_series_id(series_id) == (escopo, slug_indicador(indicador), chave)


def test_chave_com_underscore_e_recusada() -> None:
    """`_` na chave quebraria `decompor_series_id` — é erro de programação, não dado."""
    with pytest.raises(ErroDeExtracao, match="decompor_series_id"):
        montar_series_id(Escopo.REUNIAO_COPOM, "Selic", "R1_2027")


def test_series_id_fora_da_gramatica_levanta() -> None:
    with pytest.raises(ErroDeExtracao, match="não é series_id do Focus"):
        decompor_series_id("BCB_SGS_433")
    with pytest.raises(ErroDeExtracao, match="escopo desconhecido"):
        decompor_series_id("FOCUS_XX_IPCA_H0")


def test_horizonte_fora_do_pacote_e_descartado_e_contado() -> None:
    """A fonte entrega até 23 meses de horizonte; o pacote usa H0/H1 e **conta** o resto."""
    entrada = entrada_do_catalogo("FOCUS_MENSAIS")
    cruas = linhas("ExpectativaMercadoMensais__2026-10-11.json")
    quadro, descartes = quadro_de_linhas(entrada, plano_de(entrada), cruas, collected_at=AGORA)
    assert set(quadro["series_id"]) == {"FOCUS_M_IPCA_H0", "FOCUS_M_IPCA_H1"}
    assert descartes.fora_do_horizonte == len(cruas) - len(quadro)
    assert descartes.fora_do_horizonte > 0


def test_trimestral_grava_o_horizonte_negativo_sistematico() -> None:
    """`HM1` = trimestre encerrado e ainda não divulgado — é o insumo de surpresa de PIB (§1.5)."""
    entrada = entrada_do_catalogo("FOCUS_TRIMESTRAIS")
    quadro, _ = quadro_de_linhas(
        entrada,
        plano_de(entrada),
        linhas("ExpectativasMercadoTrimestrais__2026-10-11.json"),
        collected_at=AGORA,
    )
    assert "FOCUS_Q_PIB_TOTAL_HM1" in set(quadro["series_id"])
    do_hm1 = quadro.loc[
        (quadro["series_id"] == "FOCUS_Q_PIB_TOTAL_HM1")
        & (quadro["date"] == pd.Timestamp("2026-10-02")),
        "value",
    ]
    assert float(do_hm1.iloc[0]) == pytest.approx(1.8)


def test_selic_vira_painel_por_reuniao_do_copom() -> None:
    """Uma série por reunião, chave absoluta; canário de 1T2006 `R1-2007` em 2006-01-02 = 15,0."""
    entrada = entrada_do_catalogo("FOCUS_SELIC")
    quadro, descartes = quadro_de_linhas(
        entrada,
        plano_de(entrada),
        linhas("ExpectativasMercadoSelic__2026-10-11.json"),
        collected_at=AGORA,
    )
    assert descartes.fora_do_horizonte == 0  # o painel aceita toda reunião
    assert all(s.startswith("FOCUS_RCOPOM_SELIC_R") for s in quadro["series_id"])
    valor = quadro.loc[
        (quadro["series_id"] == "FOCUS_RCOPOM_SELIC_R1-2007")
        & (quadro["date"] == pd.Timestamp("2006-01-02")),
        "value",
    ]
    assert float(valor.iloc[0]) == pytest.approx(15.0)


def test_inflacao_12m_gera_as_duas_series_de_suavizacao() -> None:
    """S e N são dado real, as duas; a escolha entre elas é de F-015, declarada, não aqui."""
    entrada = entrada_do_catalogo("FOCUS_INFLACAO_12M")
    quadro, _ = quadro_de_linhas(
        entrada,
        plano_de(entrada),
        linhas("ExpectativasMercadoInflacao12Meses__2026-10-11.json"),
        collected_at=AGORA,
    )
    assert set(quadro["series_id"]) == {"FOCUS_I12_IPCA_S", "FOCUS_I12_IPCA_N"}
    for series_id, esperado in (("FOCUS_I12_IPCA_S", 4.5905), ("FOCUS_I12_IPCA_N", 4.8741)):
        valor = quadro.loc[
            (quadro["series_id"] == series_id) & (quadro["date"] == pd.Timestamp("2026-10-02")),
            "value",
        ]
        assert float(valor.iloc[0]) == pytest.approx(esperado)


def test_unidade_por_indicador_vem_do_plano() -> None:
    """Câmbio é `BRL`, Selic é `%a.a.`, IPCA e PIB são `%` — escala declarada, não inferida."""
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    quadro, _ = quadro_de_linhas(
        entrada,
        plano_de(entrada),
        linhas("ExpectativasMercadoAnuais__2026-10-11__basecalculo-0-e-1.json"),
        collected_at=AGORA,
    )
    assert set(quadro["unit"]) == {"%"}  # a fixture é só de IPCA
    unidades = {p.indicador: p.unit.value for p in plano_de(entrada).pedidos}
    assert unidades == {"IPCA": "%", "Selic": "%a.a.", "PIB Total": "%", "Câmbio": "BRL"}


# ─────────────────────────────────────────────────────────────────────────────
# Dedup, continuidade, truncamento de data e canários
# ─────────────────────────────────────────────────────────────────────────────


def test_duplicata_com_mesmo_valor_e_removida_e_com_valor_diferente_levanta() -> None:
    """Página repetida é ruído; dois valores para o mesmo dia é erro que ninguém escolhe por nós."""
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    cruas = linhas("ExpectativasMercadoAnuais__2026-10-11__2006-01.json")
    quadro, _ = quadro_de_linhas(entrada, plano_de(entrada), cruas + cruas, collected_at=AGORA)
    limpo, removidas = deduplicar(quadro)
    assert removidas == len(quadro) // 2
    assert not limpo.duplicated(subset=["series_id", "date"]).any()

    conflito = pd.concat([limpo, limpo.head(1).assign(value=999.0)], ignore_index=True)
    with pytest.raises(ErroDeExtracao, match="valor DIFERENTE"):
        deduplicar(conflito)


def test_data_em_fim_de_semana_levanta() -> None:
    """A pesquisa Focus é de dia útil — sábado no índice é campo errado lido como `Data`."""
    quadro = pd.DataFrame(
        {
            "series_id": ["FOCUS_A_IPCA_H0", "FOCUS_A_IPCA_H0"],
            "date": pd.to_datetime(["2026-10-02", "2026-10-03"]),  # 03/10/2026 é sábado
            "value": [5.0, 5.0],
        }
    )
    with pytest.raises(ErroDeExtracao, match="fim de semana"):
        validar_continuidade(quadro)


def test_vao_maior_que_o_tolerado_levanta_e_vao_natural_passa() -> None:
    """A guarda pega **fatia de ano perdida**, não janela estrutural nem feriado."""
    base = pd.DataFrame(
        {
            "series_id": ["FOCUS_Q_PIB_TOTAL_HM1"] * 2,
            "date": pd.to_datetime(["2026-01-02", "2026-03-02"]),  # 59 dias
            "value": [1.0, 1.1],
        }
    )
    assert validar_continuidade(base) == 59  # noqa: PLR2004 - janela natural do HM1
    perdida = pd.DataFrame(
        {
            "series_id": ["FOCUS_A_IPCA_H0"] * 2,
            "date": pd.to_datetime(["2006-01-02", "2007-01-02"]),
            "value": [4.5, 4.1],
        }
    )
    with pytest.raises(ErroDeExtracao, match="fatia de ano perdida"):
        validar_continuidade(perdida, gap_maximo=GAP_MAXIMO_FOCUS_DIAS)


def test_quadro_vazio_levanta_na_continuidade() -> None:
    with pytest.raises(ErroDeExtracao, match="quadro vazio"):
        validar_continuidade(pd.DataFrame({"series_id": [], "date": [], "value": []}))


def test_data_futura_e_truncada_com_aviso() -> None:
    """O `$filter` pede `Data le fim`; se a fonte ignorar, a linha sai contada, não pelo schema."""
    quadro = pd.DataFrame(
        {
            "series_id": ["FOCUS_A_IPCA_H0"] * 2,
            "date": pd.to_datetime(["2026-10-02", "2026-12-31"]),
            "value": [5.0, 5.1],
        }
    )
    limpo, truncadas = truncar_em(quadro, date(2026, 10, 11))
    assert truncadas == 1
    assert len(limpo) == 1


def test_canario_ausente_na_data_levanta() -> None:
    """Dentro da janela, canário sem linha é falha; fora da janela, é ignorado."""
    quadro = pd.DataFrame(
        {
            "series_id": ["FOCUS_A_IPCA_H0"] * 3,
            "date": pd.to_datetime(["2026-10-01", "2026-10-05", "2026-10-06"]),
            "value": [5.0, 5.0, 5.0],
        }
    )
    with pytest.raises(ErroDeExtracao, match="valor-canário de 2026-10-02 ausente"):
        conferir_canarios(quadro)
    # fora da janela: nenhuma conferência, nenhuma falha
    antigo = quadro.assign(date=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]))
    assert conferir_canarios(antigo) == ()


def test_canario_com_valor_divergente_levanta() -> None:
    quadro = pd.DataFrame(
        {
            "series_id": ["FOCUS_A_IPCA_H0"] * 2,
            "date": pd.to_datetime(["2026-10-01", "2026-10-02"]),
            "value": [5.0, 9.99],
        }
    )
    with pytest.raises(ErroDeExtracao, match="valor-canário 2026-10-02"):
        conferir_canarios(quadro)


def test_todo_canario_declarado_aponta_para_serie_do_plano() -> None:
    """Canário de série que o `PLANO` não produz nunca seria conferido — seria falsa segurança."""
    produziveis = set()
    for plano in PLANO.values():
        for pedido in plano.pedidos:
            for chave in sorted(pedido.chaves or ()):
                produziveis.add(montar_series_id(plano.escopo, pedido.indicador, chave))
    for series_id in CANARIOS:
        escopo, _, _ = decompor_series_id(series_id)
        assert series_id in produziveis or escopo is Escopo.REUNIAO_COPOM, series_id


def test_serie_declarada_que_nao_aparece_levanta() -> None:
    """Rótulo de `Indicador` renomeado na fonte derruba a extração, não some do output."""
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    cruas = [
        dict(linha, Indicador="IPCA Renomeado")
        for linha in linhas("ExpectativasMercadoAnuais__2026-10-11__2006-01.json")
    ]
    quadro, descartes = quadro_de_linhas(entrada, plano_de(entrada), cruas, collected_at=AGORA)
    assert quadro.empty
    assert descartes.fora_do_horizonte == len(cruas)


# ─────────────────────────────────────────────────────────────────────────────
# Fatiamento por ano, nome do bruto e modo offline (D-b, CA-121)
# ─────────────────────────────────────────────────────────────────────────────


def test_fatiar_por_ano_e_contiguo_e_alinhado() -> None:
    """Ano-calendário: ano encerrado não muda, então a fatia é byte-idêntica a cada rodada."""
    fatias = fatiar_por_ano(date(2004, 1, 1), date(2026, 10, 11))
    assert len(fatias) == 23  # noqa: PLR2004 - 2004..2026
    assert fatias[0] == (date(2004, 1, 1), date(2004, 12, 31))
    assert fatias[-1] == (date(2026, 1, 1), date(2026, 10, 11))
    for (_, fim_anterior), (inicio_seguinte, _) in zip(fatias, fatias[1:], strict=False):
        assert (inicio_seguinte - fim_anterior).days == 1
    assert fatiar_por_ano(date(2006, 3, 1), date(2006, 4, 1)) == (
        (date(2006, 3, 1), date(2006, 4, 1)),
    )
    with pytest.raises(ValueError, match="janela invertida"):
        fatiar_por_ano(date(2026, 1, 1), date(2025, 1, 1))


def test_descrever_url_e_o_inverso_de_montar_url() -> None:
    """O `--offline` reencontra a página lendo a própria URL — `$skip` // `$top`."""
    for indicador in ("PIB Total", "Câmbio", None):
        url = montar_url(
            "ExpectativasMercadoAnuais",
            indicador=indicador,
            inicio=date(2006, 1, 1),
            fim=date(2006, 12, 31),
            pagina=2,
            top=10000,
        )
        pedida = descrever_url(url)
        assert pedida.entityset == "ExpectativasMercadoAnuais"
        assert pedida.indicador == indicador
        assert pedida.inicio == date(2006, 1, 1)
        assert pedida.fim == date(2006, 12, 31)
        assert pedida.pagina == 2  # noqa: PLR2004


def test_descrever_url_recusa_url_que_nao_e_de_pagina() -> None:
    with pytest.raises(ErroDeExtracao, match="não consigo deduzir a página"):
        descrever_url(f"{URL_BASE_OLINDA}/ExpectativasMercadoAnuais?$format=json")


def test_nome_bruto_e_deterministico() -> None:
    """Mesma fatia ⇒ mesmo nome ⇒ segundo download não duplica arquivo."""
    comum = {"inicio": date(2006, 1, 1), "fim": date(2006, 12, 31), "pagina": 0}
    assert (
        nome_bruto("ExpectativasMercadoAnuais", indicador="PIB Total", **comum)
        == "ExpectativasMercadoAnuais_PIB_TOTAL_2006_p0__2006-12-31.json"
    )
    assert (
        nome_bruto("ExpectativasMercadoSelic", indicador=None, **comum)
        == "ExpectativasMercadoSelic_TODOS_2006_p0__2006-12-31.json"
    )


def test_offline_sem_manifesto_recusa_em_vez_de_usar_o_relogio(tmp_path: Path) -> None:
    """D-b/CA-121: bruto posto à mão não data o Parquet pelo relógio do reprocessamento."""
    nome = nome_bruto(
        "ExpectativasMercadoAnuais",
        indicador="IPCA",
        inicio=date(2006, 1, 1),
        fim=date(2006, 12, 31),
        pagina=0,
    )
    (tmp_path / nome).write_bytes(ler("ExpectativasMercadoAnuais__2026-10-11__2006-01.json"))
    transporte = transporte_do_bruto_arquivado(tmp_path)
    url = montar_url(
        "ExpectativasMercadoAnuais",
        indicador="IPCA",
        inicio=date(2006, 1, 1),
        fim=date(2006, 12, 31),
        pagina=0,
        top=40,
    )
    with pytest.raises(ManifestoAusente, match="sem manifesto legível"):
        transporte("GET", url, params=None, dados=None, cabecalhos={}, timeout_s=1.0)


def test_offline_sem_o_arquivo_explica_como_arquivar(tmp_path: Path) -> None:
    transporte = transporte_do_bruto_arquivado(tmp_path)
    url = montar_url(
        "ExpectativasMercadoAnuais",
        indicador="IPCA",
        inicio=date(2006, 1, 1),
        fim=date(2006, 12, 31),
        pagina=0,
        top=40,
    )
    with pytest.raises(ErroDeExtracao, match="Rode sem --offline"):
        transporte("GET", url, params=None, dados=None, cabecalhos={}, timeout_s=1.0)


def test_offline_tira_collected_at_do_manifesto_e_e_idempotente(tmp_path: Path) -> None:
    """Duas rodadas `--offline` sobre o mesmo bruto geram o **mesmo** quadro (D-b, CA-121)."""
    destino = tmp_path / "data" / "raw" / "focus"
    destino.mkdir(parents=True)
    nome = nome_bruto(
        "ExpectativasMercadoAnuais",
        indicador="IPCA",
        inicio=date(2006, 1, 1),
        fim=date(2006, 1, 31),
        pagina=0,
    )
    arquivar_bruto(
        ler("ExpectativasMercadoAnuais__2026-10-11__2006-01.json"),
        destino=destino,
        nome=nome,
        origem="fixture",
        obtido_em=AGORA,
    )
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    transporte = transporte_do_bruto_arquivado(destino)
    cliente = ClienteHTTP(config_para(entrada, fim=date(2006, 1, 31)), transporte=transporte)

    from apps.pipeline.extract.bcb_focus import baixar_indicador

    plano = plano_de(entrada)
    pedido = next(p for p in plano.pedidos if p.indicador == "IPCA")
    quadros = []
    for _ in range(2):
        cruas, paginas = baixar_indicador(
            plano,
            pedido,
            cliente=cliente,
            destino=destino,
            inicio=date(2006, 1, 1),
            fim=date(2006, 1, 31),
            top=200,
        )
        assert all(p.idempotente for p in paginas)
        quadro, _ = quadro_de_linhas(entrada, plano, cruas, collected_at=AGORA)
        quadros.append(quadro)
    pd.testing.assert_frame_equal(quadros[0], quadros[1])
    assert set(quadros[0]["vintage"]) == {pd.Timestamp("2026-10-11")}
    assert set(quadros[0]["collected_at"].dt.tz_localize(None)) == {
        pd.Timestamp(AGORA).tz_localize(None)
    }


def test_extrair_serie_grava_parquet_validado_pelo_schema(tmp_path: Path) -> None:
    """Ponta a ponta sem rede: 1 página → Parquet com as 8 colunas e PK única."""
    entrada = entrada_do_catalogo("FOCUS_ANUAIS")
    transporte = TransporteDeFixture(ler(QUATRO_INDICADORES), recortar_por_indicador=True)
    resultado = extrair_serie(
        entrada,
        inicio=date(2026, 10, 1),
        fim=date(2026, 10, 11),
        transporte=transporte,
        raiz=tmp_path,
        collected_at=AGORA,
    )
    assert resultado.parquet is not None
    gravado = pd.read_parquet(resultado.parquet)
    assert tuple(gravado.columns) == (
        "series_id",
        "date",
        "value",
        "source",
        "freq",
        "vintage",
        "unit",
        "collected_at",
    )
    assert not gravado.duplicated(subset=["series_id", "date", "vintage"]).any()
    assert (gravado["date"] <= gravado["collected_at"].dt.tz_localize(None)).all()
    assert not resultado.cobre_1t2006  # a fixture é a janela de out/2026, não 2006
    assert resultado.pct_nulos == 0.0
    assert len(transporte.urls) == 4  # noqa: PLR2004 - um pedido por indicador do plano
    assert set(resultado.series_gravadas) == {
        "FOCUS_A_CAMBIO_H0",
        "FOCUS_A_CAMBIO_H1",
        "FOCUS_A_IPCA_H0",
        "FOCUS_A_IPCA_H1",
        "FOCUS_A_PIB_TOTAL_H0",
        "FOCUS_A_PIB_TOTAL_H1",
        "FOCUS_A_SELIC_H0",
        "FOCUS_A_SELIC_H1",
    }
    assert set(gravado["unit"]) == {"%", "%a.a.", "BRL"}


# ─────────────────────────────────────────────────────────────────────────────
# Portão do catálogo
# ─────────────────────────────────────────────────────────────────────────────


def test_catalogo_focus_so_devolve_entityset_confirmado() -> None:
    """`FOCUS_PIB_TOTAL` está `a_confirmar` com identificador literal `a_confirmar` — fica fora."""
    entradas = catalogo_focus()
    assert tuple(e.series_id for e in entradas) == SERIES_PACOTE_MINIMO
    assert all(e.status is StatusSerie.OK for e in entradas)
    assert all(e.fonte is Fonte.BCB_OLINDA for e in entradas)
    assert all(e.freq is Freq.DIARIA for e in entradas)
    a_confirmar = [
        e.series_id
        for e in load_catalog()
        if e.fonte is Fonte.BCB_OLINDA and e.status is not StatusSerie.OK
    ]
    assert "FOCUS_PIB_TOTAL" in a_confirmar
    assert "FOCUS_PIB_TOTAL" not in [e.series_id for e in entradas]


def test_serie_fora_do_catalogo_levanta() -> None:
    with pytest.raises(ErroDeExtracao, match="fora do catálogo Focus"):
        catalogo_focus(["FOCUS_INVENTADO"])
    with pytest.raises(ErroDeExtracao, match="fora do catálogo Focus"):
        catalogo_focus(["FOCUS_PIB_TOTAL"])


def test_plano_concorda_com_o_identificador_do_catalogo() -> None:
    """O EntitySet vem do catálogo; `PLANO` só pode concordar com ele, nunca divergir."""
    for entrada in catalogo_focus():
        plano = plano_de(entrada)
        assert plano.entityset == entrada.identificador
        assert plano.entityset in INDICADORES_ENUMERADOS
        assert plano.escopo is Escopo(plano.escopo.value)


# ─────────────────────────────────────────────────────────────────────────────
# Rede — não roda no CI (`-m "not network"`)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_canarios_contra_a_fonte_viva() -> None:
    """Confere os canários do contrato contra `olinda.bcb.gov.br`, em requisição independente."""
    from urllib.parse import quote

    import requests

    from apps.pipeline.common import CABECALHOS_DE_BROWSER
    from apps.pipeline.extract.bcb_focus import CARACTERES_SEGUROS_ODATA

    alvos = [
        ("ExpectativasMercadoAnuais", "Indicador eq 'IPCA' and DataReferencia eq '2026'", 5.0129),
        ("ExpectativasMercadoAnuais", "Indicador eq 'Selic' and DataReferencia eq '2026'", 13.5),
        (
            "ExpectativasMercadoAnuais",
            "Indicador eq 'PIB Total' and DataReferencia eq '2026'",
            1.8549,
        ),
    ]
    for entityset, filtro, esperado in alvos:
        consulta = quote(
            f"{filtro} and Data eq '2026-10-02' and baseCalculo eq 0",
            safe=CARACTERES_SEGUROS_ODATA,
        )
        url = f"{URL_BASE_OLINDA}/{entityset}?$format=json&$filter={consulta}"
        corpo = requests.get(url, headers=CABECALHOS_DE_BROWSER, timeout=120).json()["value"]
        assert len(corpo) == 1, url
        assert float(corpo[0]["Mediana"]) == pytest.approx(esperado)


@pytest.mark.network
def test_top_20000_trunca_sem_nextlink() -> None:
    """CA-018 contra a fonte viva: `$top=20000` devolve 20.000 linhas e **nenhum** `nextLink`."""
    from urllib.parse import quote

    import requests

    from apps.pipeline.common import CABECALHOS_DE_BROWSER
    from apps.pipeline.extract.bcb_focus import CARACTERES_SEGUROS_ODATA

    filtro = quote("Indicador eq 'IPCA' and baseCalculo eq 0", safe=CARACTERES_SEGUROS_ODATA)
    base = f"{URL_BASE_OLINDA}/ExpectativasMercadoAnuais?$format=json&$filter={filtro}"
    truncada = requests.get(
        f"{base}&$select=Data&$top={LINHAS_SUSPEITAS_DE_TRUNCAMENTO}",
        headers=CABECALHOS_DE_BROWSER,
        timeout=300,
    ).json()
    assert len(truncada["value"]) == LINHAS_SUSPEITAS_DE_TRUNCAMENTO
    assert "@odata.nextLink" not in truncada

    inteira = requests.get(
        f"{base}&$select=Data", headers=CABECALHOS_DE_BROWSER, timeout=300
    ).json()["value"]
    assert len(inteira) > LINHAS_SUSPEITAS_DE_TRUNCAMENTO
    with pytest.raises(RespostaTruncada):
        recusar_truncamento_silencioso(
            len(truncada["value"]), top=LINHAS_SUSPEITAS_DE_TRUNCAMENTO, origem="live"
        )
