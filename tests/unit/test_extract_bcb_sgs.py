"""Testes do extrator BCB SGS (F-003) — um por critério de aceite, sobre fixture gravada.

Nenhum teste deste arquivo abre socket, exceto os marcados `@pytest.mark.network` (que o CI N1
exclui com `-m "not network"`). O transporte é injetado: `TransporteDeFixture` devolve o corpo
real gravado em `tests/fixtures/sgs/`, com o **status HTTP que a fonte devolveu de verdade**.

Procedência de cada fixture: `tests/fixtures/sgs/README.md`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from apps.pipeline.common import (
    JANELA_SGS_RECOMENDADA_DIAS,
    ErroDeExtracao,
    FonteIndisponivel,
    ManifestoAusente,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    obtido_em_arquivado,
    para_float_ponto_decimal,
    para_float_ptbr,
    sha256_de,
)
from apps.pipeline.extract.bcb_sgs import (
    GAP_MAXIMO_DIARIO_DIAS,
    SERIES_DIARIAS_DE_CALENDARIO,
    SERIES_PACOTE_MINIMO,
    Freq,
    calendario_corrido,
    catalogo_sgs,
    config_para,
    deduplicar_por_data,
    descartar_periodo_aberto,
    extrair_serie,
    fim_do_periodo,
    quadro_de_observacoes,
    validar_continuidade,
)
from packages.shared.schemas import SeriesCatalogEntry

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sgs"
AGORA = datetime(2026, 10, 10, 20, 30, tzinfo=UTC)
FIM = date(2026, 10, 10)


# ─────────────────────────────────────────────────────────────────────────────
# Transporte falso (modelo copiado de tests/unit/test_common_http.py, por desenho de F-001)
# ─────────────────────────────────────────────────────────────────────────────


class TransporteDeFixture:
    """Devolve o corpo gravado, opcionalmente recortado pela janela pedida.

    `recortar=True` imita o comportamento do SGS: `dataInicial`/`dataFinal` filtram o array. É o
    que permite exercitar o fatiamento real de `baixar_serie` com uma fixture pequena.
    """

    def __init__(
        self,
        conteudo: bytes,
        *,
        status: int = 200,
        recortar: bool = False,
    ) -> None:
        self._conteudo = conteudo
        self._status = status
        self._recortar = recortar
        self.chamadas: list[dict[str, Any]] = []

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
        self.chamadas.append({"metodo": metodo, "url": url, "params": dict(params or {})})
        corpo = self._conteudo
        if self._recortar and params:
            inicio = datetime.strptime(str(params["dataInicial"]), "%d/%m/%Y").date()  # noqa: DTZ007
            fim = datetime.strptime(str(params["dataFinal"]), "%d/%m/%Y").date()  # noqa: DTZ007
            todas = json.loads(self._conteudo.decode("utf-8"))
            recorte = [
                o
                for o in todas
                if inicio <= datetime.strptime(o["data"], "%d/%m/%Y").date() <= fim  # noqa: DTZ007
            ]
            corpo = json.dumps(recorte, ensure_ascii=False).encode("utf-8")
        return RespostaBruta(
            url=f"https://api.bcb.gov.br{url}",
            status=self._status,
            conteudo=corpo,
            cabecalhos={"Content-Type": "application/json"},
            obtida_em=AGORA,
        )

    @property
    def janelas(self) -> list[tuple[date, date]]:
        """Janelas efetivamente pedidas, em `date` — a evidência do fatiamento."""
        return [
            (
                datetime.strptime(c["params"]["dataInicial"], "%d/%m/%Y").date(),  # noqa: DTZ007
                datetime.strptime(c["params"]["dataFinal"], "%d/%m/%Y").date(),  # noqa: DTZ007
            )
            for c in self.chamadas
        ]


def fixture(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


def entrada(series_id: str):  # noqa: ANN201
    return catalogo_sgs([series_id])[0]


def extrair(
    series_id: str,
    nome_fixture: str,
    *,
    inicio: date,
    fim: date = FIM,
    status: int = 200,
    raiz: Path | None = None,
    gravar: bool = False,
    recortar: bool = False,
):  # noqa: ANN201
    transporte = TransporteDeFixture(fixture(nome_fixture), status=status, recortar=recortar)
    resultado = extrair_serie(
        entrada(series_id),
        inicio=inicio,
        fim=fim,
        transporte=transporte,
        raiz=raiz,
        gravar=gravar,
        collected_at=AGORA,
    )
    return resultado, transporte


def quadro_do_parquet(caminho: Path) -> pd.DataFrame:
    return pd.read_parquet(caminho)


# ─────────────────────────────────────────────────────────────────────────────
# CA-003 — HTTP 200 com corpo de erro: falha ruidosa e nada em data/processed/
# ─────────────────────────────────────────────────────────────────────────────


def test_ca003_corpo_html_com_http_200_falha_e_nao_grava_nada(tmp_path: Path) -> None:
    """Série inexistente devolve **HTML com HTTP 200** — o modo de falha dominante da fonte (R1).

    É a fixture `99999999__erro_html.txt`: 6.255 bytes de XHTML servidos com status 200. Sem a
    guarda de shape, `json.loads` levantaria bem depois (ou, com `formato=csv`, gravaria lixo).
    """
    with pytest.raises(RespostaDeErroComStatus200, match="corpo HTML"):
        extrair_serie(
            entrada("BCB_SGS_433"),
            inicio=date(2006, 1, 1),
            fim=FIM,
            transporte=TransporteDeFixture(fixture("99999999__erro_html.txt")),
            raiz=tmp_path,
            collected_at=AGORA,
        )
    assert not (tmp_path / "data" / "processed").exists(), (
        "CA-003: resposta inválida não pode deixar rastro em data/processed/"
    )
    assert not (tmp_path / "data" / "raw").exists(), "nem bruto deveria ter sido arquivado"


def test_ca003_janela_de_10_anos_falha_ruidosamente(tmp_path: Path) -> None:
    """Janela > 10 anos em série diária: hoje a fonte devolve **HTTP 406** + corpo de erro.

    `docs/research/fontes-de-dados.md §A1` mediu **HTTP 200** para este mesmo corpo. Em
    2026-10-10 o SGS passou a usar 406, e o corpo é idêntico. As duas rotas falham alto — 406 cai
    em `FonteIndisponivel` (status >= 400 não retentável) e 200 cairia em
    `RespostaDeErroComStatus200` — mas o status mudou, e isso está registrado aqui porque é o tipo
    de mudança que uma fonte faz sem avisar.
    """
    corpo = json.loads(fixture("11__erro.json").decode("utf-8"))
    assert "10 anos" in corpo["error"], "a fixture precisa ser o erro de janela, não outro"

    with pytest.raises(FonteIndisponivel, match="HTTP 406"):
        extrair_serie(
            entrada("BCB_SGS_11"),
            inicio=date(1980, 1, 1),
            fim=date(1990, 12, 31),
            transporte=TransporteDeFixture(fixture("11__erro.json"), status=406),
            raiz=tmp_path,
            collected_at=AGORA,
        )
    assert not (tmp_path / "data" / "processed").exists()


def test_ca003_erro_404_com_corpo_json_tambem_para_o_pipeline(tmp_path: Path) -> None:
    """Janela anterior ao início da série: HTTP 404 + `{"erro": {...}}`. Nada é inventado."""
    with pytest.raises(FonteIndisponivel, match="HTTP 404"):
        extrair_serie(
            entrada("BCB_SGS_433"),
            inicio=date(1900, 1, 1),
            fim=date(1910, 12, 31),
            transporte=TransporteDeFixture(fixture("433__erro_404.json"), status=404),
            raiz=tmp_path,
            collected_at=AGORA,
        )
    assert not (tmp_path / "data" / "processed").exists()


def test_ca001_corpo_vazio_com_http_200_e_truncamento_nao_sucesso(tmp_path: Path) -> None:
    """`[]` com HTTP 200 é truncamento silencioso (R2), não série vazia legítima.

    Corpo literal `b"[]"`, não fixture: é a resposta que a guarda de contagem mínima existe para
    recusar, e `contagem_minima_esperada` sai do `ExtractorConfig` da série.
    """
    with pytest.raises(RespostaTruncada, match="mínimo esperado"):
        extrair_serie(
            entrada("BCB_SGS_433"),
            inicio=date(2004, 1, 1),
            fim=FIM,
            transporte=TransporteDeFixture(b"[]"),
            raiz=tmp_path,
            collected_at=AGORA,
        )
    assert not (tmp_path / "data" / "processed").exists()


# ─────────────────────────────────────────────────────────────────────────────
# CA-001 / CA-002 — IPCA mensal contíguo e valor-canário
# ─────────────────────────────────────────────────────────────────────────────


def test_ca001_ipca_mensal_contiguo_com_metadados_do_catalogo(tmp_path: Path) -> None:
    """>= 249 observações mensais contíguas, `source=BCB_SGS`, `freq=M`, `unit=%`."""
    resultado, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    assert resultado.linhas == 273
    assert resultado.linhas >= 249, "CA-001 pede >= 249 observações mensais"
    assert (resultado.data_min, resultado.data_max) == (date(2004, 1, 31), date(2026, 9, 30))
    assert resultado.pct_nulos == 0.0
    assert resultado.cobre_1t2006

    quadro = quadro_do_parquet(resultado.parquet)
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
    assert set(quadro["source"]) == {"BCB_SGS"}
    assert set(quadro["freq"]) == {"M"}
    assert set(quadro["unit"]) == {"%"}
    # contiguidade: 273 meses entre jan/2004 e set/2026, nenhum faltando
    meses = pd.DatetimeIndex(quadro["date"]).to_period("M")
    assert len(meses) == len(set(meses)) == 273


def test_ca002_ipca_setembro_2026_e_0_82(tmp_path: Path) -> None:
    """Valor-canário de CA-002: set/2026 = `0.82`, idêntico a SIDRA `t/1737 v/63`.

    O canário é conferido **dentro** de `extrair_serie` (`conferir_canario`), então este teste
    falharia pela exceção antes de chegar ao `assert` — ele documenta o número, de propósito.
    """
    resultado, _ = extrair("BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1))
    assert resultado.canario == ("2026-09-30", 0.82)


def test_ca002_o_normalizador_errado_muda_a_escala_em_silencio() -> None:
    """O JSON do SGS usa **ponto** decimal: `para_float_ptbr` não serve e é de propósito.

    Em pt-BR todo ponto é separador de milhar, então `"6.930"` vira `6930.0`. Se o extrator
    usasse `para_float_ptbr`, um IPCA de `0.82` não falharia alto — ele viraria outra coisa, ou
    passaria, dependendo do número. O teste trava a escolha do normalizador.
    """
    assert para_float_ponto_decimal("0.82") == 0.82
    assert para_float_ponto_decimal("6.930") == 6.93
    assert para_float_ptbr("6.930") == 6930.0, "em pt-BR o ponto é milhar"
    with pytest.raises(ErroDeExtracao):
        para_float_ptbr("0.82")


def test_ausencia_virou_none_e_nunca_zero() -> None:
    """Anti-SPEC §10.1.4: `""`, `"-"`, `"ND"` → `None`. Zero é um valor, ausência não é."""
    quadro = quadro_de_observacoes(
        entrada("BCB_SGS_433"),
        [
            {"data": "01/01/2006", "valor": "0.59"},
            {"data": "01/02/2006", "valor": ""},
            {"data": "01/03/2006", "valor": "ND"},
        ],
        collected_at=AGORA,
    )
    assert quadro["value"].tolist()[0] == 0.59
    assert quadro["value"].isna().tolist() == [False, True, True]
    assert 0.0 not in quadro["value"].dropna().tolist()


# ─────────────────────────────────────────────────────────────────────────────
# CA-011 / CA-012 — fatiamento de série diária
# ─────────────────────────────────────────────────────────────────────────────


def test_ca011_config_liga_o_fatiamento_so_na_serie_diaria() -> None:
    """A pegadinha de 10 anos vive no `ExtractorConfig`, não num `if` espalhado pelo código."""
    for series_id in ("BCB_SGS_11", "BCB_SGS_12", "BCB_SGS_1", "BCB_SGS_432"):
        cfg = config_para(entrada(series_id), inicio=date(2004, 1, 1), fim=FIM)
        assert cfg.janela_maxima_dias == JANELA_SGS_RECOMENDADA_DIAS, series_id
        assert cfg.janela_maxima_dias < 3650, "a fatia tem de caber na janela de 10 anos"
    for series_id in ("BCB_SGS_433", "BCB_SGS_24364", "BCB_SGS_22109"):
        cfg = config_para(entrada(series_id), inicio=date(2004, 1, 1), fim=FIM)
        assert cfg.janela_maxima_dias is None, f"{series_id}: mensal/trimestral não tem limite"


def test_ca011_serie_diaria_e_fatiada_sem_duplicata_nem_lacuna(tmp_path: Path) -> None:
    """2 anos de SGS 11 pedidos em fatias curtas: concatena, não duplica e não perde dia útil.

    A janela de produção (~5 anos) exigiria uma fixture de 20 anos para gerar mais de uma fatia,
    acima do limite de 200 KB de `tests/fixtures/README.md`. O fatiamento é a mesma função
    (`baixar_serie` → `fatiar_janela`) exercitada com a janela encurtada; o valor de produção é
    travado no teste anterior.
    """
    from apps.pipeline.extract.bcb_sgs import baixar_serie

    e = entrada("BCB_SGS_11")
    cfg = config_para(e, inicio=date(2005, 1, 1), fim=date(2006, 12, 31)).model_copy(
        update={"janela_maxima_dias": 180}
    )
    transporte = TransporteDeFixture(fixture("11__2026-10-10__2005-2006.json"), recortar=True)
    observacoes, fatias = baixar_serie(
        e,
        config=cfg,
        inicio=date(2005, 1, 1),
        fim=date(2006, 12, 31),
        transporte=transporte,
        raiz=tmp_path,
    )

    assert len(fatias) >= 4, "730 dias em fatias de 180 têm de dar mais de uma requisição"
    janelas = transporte.janelas
    assert all((f - i).days + 1 <= 180 for i, f in janelas), janelas
    # contíguas e sem sobreposição: o fim de uma fatia + 1 dia é o início da seguinte
    for (_, fim_a), (inicio_b, _) in zip(janelas, janelas[1:], strict=False):
        assert (inicio_b - fim_a).days == 1

    assert len(observacoes) == 500 == sum(f.observacoes for f in fatias)
    quadro = quadro_de_observacoes(e, observacoes, collected_at=AGORA)
    assert quadro["date"].is_unique, "fatias contíguas não podem duplicar observação"
    assert quadro["date"].is_monotonic_increasing
    validar_continuidade(quadro, freq=Freq.DIARIA)
    assert int(pd.DatetimeIndex(quadro["date"]).to_series().diff().dt.days.max()) <= (
        GAP_MAXIMO_DIARIO_DIAS
    )


def test_ca012_selic_over_03_01_2005_e_0_064826(tmp_path: Path) -> None:
    """Valor-canário de CA-012, no primeiro ponto medido da pesquisa."""
    resultado, _ = extrair(
        "BCB_SGS_11",
        "11__2026-10-10__2005-2006.json",
        inicio=date(2005, 1, 1),
        fim=date(2006, 12, 31),
        raiz=tmp_path,
        gravar=True,
        recortar=True,
    )
    assert resultado.canario == ("2005-01-03", 0.064826)
    quadro = quadro_do_parquet(resultado.parquet)
    alvo = quadro.loc[quadro["date"] == pd.Timestamp("2005-01-03"), "value"]
    assert float(alvo.iloc[0]) == pytest.approx(0.064826, abs=1e-9)
    assert set(quadro["unit"]) == {"%/dia"}, "unidade errada é erro de escala disfarçado"


# ─────────────────────────────────────────────────────────────────────────────
# CA-013 — meta Selic com data futura
# ─────────────────────────────────────────────────────────────────────────────


def test_ca013_meta_selic_com_data_futura_e_truncada_em_hoje(tmp_path: Path) -> None:
    """A fixture real traz dados até **04/11/2026** com `dataFinal=31/12/2026`: meta vigente.

    Nenhuma linha com `date > fim` chega a `data/processed/` — se chegasse, o próprio
    `ProcessedSeriesSchema` recusaria o quadro (`sem_data_futura`), mas aí a série inteira seria
    perdida em vez de truncada.
    """
    bruto = json.loads(fixture("432__2026-10-10__data-futura.json").decode("utf-8"))
    assert bruto[-1]["data"] == "04/11/2026", "a fixture precisa ter a data futura"

    resultado, _ = extrair(
        "BCB_SGS_432",
        "432__2026-10-10__data-futura.json",
        inicio=date(2026, 10, 1),
        fim=FIM,
        raiz=tmp_path,
        gravar=True,
    )
    assert resultado.linhas_futuras_truncadas == 25
    assert resultado.data_max == FIM
    quadro = quadro_do_parquet(resultado.parquet)
    assert quadro["date"].max() == pd.Timestamp(FIM)
    assert (quadro["date"] <= quadro["collected_at"]).all()


def test_meta_selic_e_serie_de_calendario_corrido() -> None:
    """432 publica em dia corrido (sábado inclusive) — medido na extração ao vivo.

    Sem este registro, a regra "série diária só tem dia útil" acusaria 2.377 datas legítimas.
    """
    assert 432 in SERIES_DIARIAS_DE_CALENDARIO
    corrida = pd.DataFrame(
        {
            "series_id": "BCB_SGS_432",
            "date": pd.to_datetime(["2026-10-03", "2026-10-04", "2026-10-05"]),  # sáb, dom, seg
            "value": [13.75, 13.75, 13.75],
        }
    )
    validar_continuidade(corrida, freq=Freq.DIARIA, calendario_corrido=True)
    with pytest.raises(ErroDeExtracao, match="fim de semana"):
        validar_continuidade(corrida, freq=Freq.DIARIA)


def test_p1_2_o_calendario_da_432_vem_do_catalogo_nao_da_constante() -> None:
    """P1-2 do QA: dia útil × dia corrido é **campo de catálogo**, não detalhe do extrator.

    F-014/F-017 leem o catálogo e o Parquet, nunca `SERIES_DIARIAS_DE_CALENDARIO`. Sem a flag no
    catálogo, uma contagem de dias úteis sobre `freq='D'` incluiria 2.377 fins de semana
    legítimos da meta Selic (28,6 % dos 8.319 pontos, medido na extração ao vivo).
    """
    por_id = {e.series_id: e for e in catalogo_sgs(todas=True)}
    assert por_id["BCB_SGS_432"].calendario == "corrido"
    assert calendario_corrido(por_id["BCB_SGS_432"]) is True

    # As 6 demais diárias do pacote mínimo foram medidas em `data/processed/`: 0 fim de semana e
    # vão máximo de 5 dias corridos (emenda de feriado) — dia útil, declarado como tal.
    uteis = (
        "BCB_SGS_11",
        "BCB_SGS_1178",
        "BCB_SGS_12",
        "BCB_SGS_4389",
        "BCB_SGS_1",
        "BCB_SGS_10813",
    )
    for series_id in uteis:
        assert por_id[series_id].calendario == "dias_uteis", series_id
        assert calendario_corrido(por_id[series_id]) is False, series_id

    # `calendario` descreve grade diária: declarar em série M/Q é erro de contrato, não omissão.
    assert por_id["BCB_SGS_433"].calendario is None
    with pytest.raises(ValueError, match="série diária"):
        SeriesCatalogEntry.model_validate(
            por_id["BCB_SGS_433"].model_dump() | {"calendario": "corrido"}
        )


def test_fallback_do_calendario_vale_para_serie_sgs_sem_flag_no_catalogo() -> None:
    """Catálogo calado (`calendario=None`) ⇒ `SERIES_DIARIAS_DE_CALENDARIO` ainda responde.

    O acréscimo do campo não pode fazer série diária nova perder a guarda de continuidade que já
    tinha: enquanto a constante listar o código, `calendario_corrido` continua dizendo `True`.
    """
    sem_flag = catalogo_sgs(["BCB_SGS_432"])[0].model_copy(update={"calendario": None})
    assert sem_flag.calendario is None
    assert calendario_corrido(sem_flag) is True


# ─────────────────────────────────────────────────────────────────────────────
# P1-1 do QA da Onda 1 — mês/trimestre corrente, ainda aberto
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fim",
    [
        date(2026, 10, 10),  # hoje, como a CLI roda sem flag
        date(2026, 10, 31),  # último dia civil do mês: aqui o truncamento NÃO salvava
        date(2026, 12, 31),  # bem depois: nem o truncamento nem o schema salvavam
    ],
    ids=["fim=hoje", "fim=fim-do-mes", "fim=dezembro"],
)
def test_mes_aberto_do_sgs_e_descartado_por_guarda_qualquer_que_seja_o_fim(
    tmp_path: Path, fim: date
) -> None:
    """A acumulação **parcial** do mês corrente nunca entra, independentemente de `--fim`.

    O bruto real da 4390 (Selic acumulada no mês) coletado em 2026-10-10 traz
    `01/10/2026 = 0.36`: os 7 dias úteis **decorridos** de outubro. `fim_do_periodo` leva essa
    linha para `2026-10-31`, que é o fim de um mês que **ainda não encerrou** na data da coleta.

    Antes da guarda, o descarte era efeito colateral: `2026-10-31 > --fim` e `truncar_em` pegava
    a linha. Com `--fim 2026-10-31` (ou rodando no último dia civil do mês, sem flag) outubro
    parcial entrava como mês fechado — reprodução do QA em `ONDA-1-QA-A.md §4.4`. A guarda
    explícita compara o fim do período com a **data da coleta**, então os três `--fim` deste
    teste dão o mesmo resultado.
    """
    bruto = json.loads(fixture("4390__2026-10-10__mes-aberto.json").decode("utf-8"))
    assert bruto[-1] == {"data": "01/10/2026", "valor": "0.36"}, "a fixture precisa do mês aberto"

    resultado, _ = extrair(
        "BCB_SGS_4390",
        "4390__2026-10-10__mes-aberto.json",
        inicio=date(2004, 1, 1),
        fim=fim,
        raiz=tmp_path,
        gravar=True,
    )
    assert resultado.linhas_periodo_aberto == 1, "a guarda conta o descarte, não o esconde"
    assert resultado.linhas == 273
    assert resultado.data_max == date(2026, 9, 30)
    quadro = quadro_do_parquet(resultado.parquet)
    assert pd.Timestamp("2026-10-31") not in set(quadro["date"]), "outubro parcial no Parquet"
    assert float(quadro["value"].iloc[-1]) == pytest.approx(1.08, abs=1e-9)


def test_periodo_fechado_na_vespera_da_coleta_continua_entrando() -> None:
    """A guarda é "período encerrado antes da coleta", não "mês anterior ao da coleta".

    Teste negativo da guarda: setembro fechou em 30/09 e a coleta é 10/10 — a linha entra. Se a
    condição fosse `mês da coleta`, o último mês fechado também cairia e a série perderia o
    ponto mais recente a cada rodada.
    """
    quadro = quadro_de_observacoes(
        entrada("BCB_SGS_4390"),
        [{"data": "01/08/2026", "valor": "1.09"}, {"data": "01/09/2026", "valor": "1.08"}],
        collected_at=AGORA,
    )
    limpo, abertas = descartar_periodo_aberto(quadro, freq=Freq.MENSAL, collected_at=AGORA)
    assert abertas == 0
    assert list(limpo["date"]) == [pd.Timestamp("2026-08-31"), pd.Timestamp("2026-09-30")]


def test_trimestre_aberto_tambem_e_descartado_e_serie_diaria_passa_inteira() -> None:
    """A guarda vale para `Q` (o PIB publica o trimestre em curso) e **não** toca `D`.

    Série diária passa inalterada de propósito: o período de um dia encerra no próprio dia, e
    data futura de verdade (meta Selic 432) é assunto de `truncar_em`, que conta e loga à parte.
    """
    trimestral = quadro_de_observacoes(
        entrada("BCB_SGS_22109"),
        [{"data": "01/07/2026", "valor": "180.0"}, {"data": "01/10/2026", "valor": "181.0"}],
        collected_at=AGORA,
    )
    limpo, abertas = descartar_periodo_aberto(trimestral, freq=Freq.TRIMESTRAL, collected_at=AGORA)
    assert abertas == 1, "4T2026 termina em 31/12 e a coleta é 10/10"
    assert list(limpo["date"]) == [pd.Timestamp("2026-09-30")]

    diaria = quadro_de_observacoes(
        entrada("BCB_SGS_432"),
        [{"data": "09/10/2026", "valor": "13.75"}, {"data": "10/10/2026", "valor": "13.75"}],
        collected_at=AGORA,
    )
    intacta, abertas_d = descartar_periodo_aberto(diaria, freq=Freq.DIARIA, collected_at=AGORA)
    assert abertas_d == 0
    assert len(intacta) == 2


# ─────────────────────────────────────────────────────────────────────────────
# CA-014 / CA-016 — CDI diário: a série é percentual, não fator
# ─────────────────────────────────────────────────────────────────────────────


def _fator_acumulado(valores: Sequence[float], *, dividir_por_100: bool = True) -> float:
    divisor = 100.0 if dividir_por_100 else 1.0
    return math.prod(1 + v / divisor for v in valores)


def test_ca014_cdi_2006_acumulado_e_15_0271_pct(tmp_path: Path) -> None:
    """249 dias úteis de 2006 acumulam **15,0271 %** — o valor-canário do pipeline.

    A acumulação de produção é de F-017 (`transform/`, classe C); aqui ela é calculada no teste
    só para provar que a **série extraída** é a que reproduz o CDI publicado. Se este número
    mudar, o problema está na extração (escala, dia faltando, dedup), não na transformação.
    """
    resultado, _ = extrair(
        "BCB_SGS_12",
        "12__2026-10-10__2006.json",
        inicio=date(2006, 1, 1),
        fim=date(2006, 12, 31),
        raiz=tmp_path,
        gravar=True,
    )
    quadro = quadro_do_parquet(resultado.parquet)
    assert len(quadro) == 249, "2006 tem 249 dias úteis na série 12"
    retorno = (_fator_acumulado(quadro["value"].tolist()) - 1) * 100
    assert retorno == pytest.approx(15.0271, abs=1e-4)


def test_ca016_esquecer_a_divisao_por_100_produz_numero_absurdo(tmp_path: Path) -> None:
    """Teste negativo de CA-016: sem o `/100` o fator anual passa de 1e5 em vez de ~1,15."""
    resultado, _ = extrair(
        "BCB_SGS_12",
        "12__2026-10-10__2006.json",
        inicio=date(2006, 1, 1),
        fim=date(2006, 12, 31),
        raiz=tmp_path,
        gravar=True,
    )
    valores = quadro_do_parquet(resultado.parquet)["value"].tolist()
    assert _fator_acumulado(valores) == pytest.approx(1.150271, abs=1e-6)
    assert _fator_acumulado(valores, dividir_por_100=False) > 1e5


# ─────────────────────────────────────────────────────────────────────────────
# CA-006 / CA-043 — IBC-Br e PTAX
# ─────────────────────────────────────────────────────────────────────────────


def test_ca006_ibcbr_jan_2006_e_79_44731_e_comeca_em_2003(tmp_path: Path) -> None:
    """Valor-canário do IBC-Br dessazonalizado + `data_inicio` do catálogo é 2003, não 2006."""
    resultado, _ = extrair(
        "BCB_SGS_24364", "24364__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path
    )
    assert resultado.canario == ("2006-01-31", 79.44731)
    assert entrada("BCB_SGS_24364").data_inicio == date(2003, 1, 1)
    assert resultado.cobre_1t2006
    assert resultado.linhas == 271, "271 meses de jan/2004 a jul/2026 (lag de ~45 dias)"


def test_ca043_ptax_venda_09_10_2026_e_4_9892(tmp_path: Path) -> None:
    """Valor-canário da PTAX venda (SGS 1) — fonte primária do USDBRL, não FRED/Yahoo."""
    resultado, _ = extrair(
        "BCB_SGS_1", "1__2026-10-10.json", inicio=date(2026, 1, 1), raiz=tmp_path, gravar=True
    )
    assert resultado.canario == ("2026-10-09", 4.9892)
    quadro = quadro_do_parquet(resultado.parquet)
    assert set(quadro["unit"]) == {"BRL"}
    assert pd.DatetimeIndex(quadro["date"]).dayofweek.max() <= 4, "PTAX só tem dia útil"


# ─────────────────────────────────────────────────────────────────────────────
# Deduplicação e continuidade
# ─────────────────────────────────────────────────────────────────────────────


def _quadro_sintetico(datas: Sequence[str], valores: Sequence[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "series_id": "BCB_SGS_11",
            "date": pd.to_datetime(list(datas)),
            "value": list(valores),
        }
    )


def test_dedup_remove_borda_repetida_e_mantem_uma_linha_por_data() -> None:
    """Data repetida com o **mesmo** valor é borda de fatia: fica 1 linha e o descarte é contado."""
    quadro = _quadro_sintetico(
        ["2006-01-02", "2006-01-03", "2006-01-03", "2006-01-04"], [0.0655, 0.0655, 0.0655, 0.0652]
    )
    limpo, removidas = deduplicar_por_data(quadro)
    assert removidas == 1
    assert len(limpo) == 3
    assert limpo["date"].is_unique


def test_dedup_recusa_data_repetida_com_valor_diferente() -> None:
    """Mesma data com valores diferentes não é ruído: é erro de janela. Não escolho por você."""
    quadro = _quadro_sintetico(["2006-01-03", "2006-01-03"], [0.0655, 0.0999])
    with pytest.raises(ErroDeExtracao, match="valor DIFERENTE"):
        deduplicar_por_data(quadro)


def test_continuidade_mensal_recusa_mes_faltando() -> None:
    """Série mensal sem fevereiro: erro, nunca interpolação (`CLAUDE.md §4`)."""
    quadro = _quadro_sintetico(["2006-01-31", "2006-03-31", "2006-04-30"], [0.59, 0.43, 0.21])
    with pytest.raises(ErroDeExtracao, match="período"):
        validar_continuidade(quadro, freq=Freq.MENSAL)
    completa = _quadro_sintetico(["2006-01-31", "2006-02-28", "2006-03-31"], [0.59, 0.41, 0.43])
    validar_continuidade(completa, freq=Freq.MENSAL)


def test_continuidade_trimestral_recusa_trimestre_faltando() -> None:
    """PIB (22109/22099) sem 2T: erro. É assim que uma revisão do IBGE apareceria."""
    quadro = _quadro_sintetico(["2006-03-31", "2006-09-30"], [131.74, 134.36])
    with pytest.raises(ErroDeExtracao, match="período"):
        validar_continuidade(quadro, freq=Freq.TRIMESTRAL)


def test_continuidade_diaria_recusa_vao_de_fatia_perdida() -> None:
    """Feriado longo passa; vão de 20 dias corridos não — é fatia perdida, não Carnaval."""
    carnaval = _quadro_sintetico(["2006-02-24", "2006-03-01"], [0.0652, 0.0652])  # sex → qua
    validar_continuidade(carnaval, freq=Freq.DIARIA)
    buraco = _quadro_sintetico(["2006-02-24", "2006-03-16"], [0.0652, 0.0652])
    with pytest.raises(ErroDeExtracao, match="vão de 20 dias"):
        validar_continuidade(buraco, freq=Freq.DIARIA)


def test_continuidade_de_calendario_recusa_dia_corrido_ausente() -> None:
    """Para 432 a exigência é maior: série de calendário não tem feriado, então não tem vão."""
    quadro = _quadro_sintetico(["2026-10-01", "2026-10-02", "2026-10-05"], [13.75, 13.75, 13.75])
    with pytest.raises(ErroDeExtracao, match="dia\\(s\\) corrido\\(s\\) ausente"):
        validar_continuidade(quadro, freq=Freq.DIARIA, calendario_corrido=True)


# ─────────────────────────────────────────────────────────────────────────────
# Idempotência (CA-121 / AGENTS §15.6) e catálogo
# ─────────────────────────────────────────────────────────────────────────────


def test_idempotencia_duas_execucoes_dao_o_mesmo_hash_e_nao_reescrevem(tmp_path: Path) -> None:
    """Rodar duas vezes: bruto não é reescrito e o Parquet sai byte-idêntico.

    O `collected_at` é fixado porque ele é, por desenho, a única coisa que muda entre execuções —
    com ele preso, qualquer diferença de bytes é bug de extração.
    """
    primeira, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    assert [f.idempotente for f in primeira.fatias] == [False]
    hash_1 = sha256_de(primeira.parquet.read_bytes())

    segunda, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    assert [f.idempotente for f in segunda.fatias] == [True], "o bruto idêntico não é reescrito"
    assert segunda.fatias[0].sha256 == primeira.fatias[0].sha256
    assert sha256_de(segunda.parquet.read_bytes()) == hash_1
    assert segunda.linhas == primeira.linhas == 273


def test_manifesto_do_bruto_e_escrito_ao_lado_da_fatia(tmp_path: Path) -> None:
    """Cada fatia bruta tem `.meta.json` com `sha256` — é o que torna o raw conferível."""
    resultado, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path
    )
    bruto = tmp_path / "data" / "raw" / "sgs" / resultado.fatias[0].arquivo
    manifesto = json.loads(bruto.with_name(bruto.name + ".meta.json").read_text(encoding="utf-8"))
    assert manifesto["sha256"] == resultado.fatias[0].sha256
    assert manifesto["bytes"] == bruto.stat().st_size


def test_catalogo_nao_deixa_entrar_serie_descontinuada_ou_a_confirmar() -> None:
    """Portão de CA-053/054: swap 7806 (morto em 2019) e `a_confirmar` não são extraíveis."""
    assert len(SERIES_PACOTE_MINIMO) == 15
    assert len(catalogo_sgs()) == 15
    for e in catalogo_sgs():
        assert e.identificador.isdigit(), e.series_id
    for proibida in ("BCB_SGS_7806", "BCB_SGS_13762", "BCB_SGS_24369", "BCB_SGS_DBGG_PRE2008"):
        with pytest.raises(ErroDeExtracao, match="fora do catálogo SGS usável"):
            catalogo_sgs([proibida])


def test_pacote_minimo_cobre_os_itens_do_email() -> None:
    """Cada série do pacote mínimo se justifica num item do checklist do e-mail (A1/A2/A4/B3/C1)."""
    itens = {e.item_email for e in catalogo_sgs()}
    assert itens == {"A1", "A2", "A4", "B3", "C1"}


# ─────────────────────────────────────────────────────────────────────────────
# Convenções da consolidação da Onda 1: D-a (`date` = fim de período) e D-b (`vintage`)
# ─────────────────────────────────────────────────────────────────────────────


def test_da_fim_do_periodo_converte_mensal_e_trimestral_e_nao_toca_diaria() -> None:
    """O SGS devolve o 1º dia do período; a camada processada grava o **último** (`CLAUDE.md §3`).

    Fim de período **civil**, não dia útil: 2006-04-30 é domingo e continua sendo a data do mês.
    Ajuste para dia útil é alinhamento (F-014), não extração.
    """
    assert fim_do_periodo(date(2026, 9, 1), freq=Freq.MENSAL) == date(2026, 9, 30)
    assert fim_do_periodo(date(2006, 2, 1), freq=Freq.MENSAL) == date(2006, 2, 28)
    assert fim_do_periodo(date(2004, 2, 1), freq=Freq.MENSAL) == date(2004, 2, 29), "ano bissexto"
    assert fim_do_periodo(date(2006, 4, 1), freq=Freq.MENSAL) == date(2006, 4, 30)
    assert fim_do_periodo(date(2026, 4, 1), freq=Freq.TRIMESTRAL) == date(2026, 6, 30)
    assert fim_do_periodo(date(2006, 1, 1), freq=Freq.TRIMESTRAL) == date(2006, 3, 31)
    assert fim_do_periodo(date(2006, 10, 1), freq=Freq.TRIMESTRAL) == date(2006, 12, 31)
    # série diária passa inalterada — inclusive a de calendário corrido (432)
    assert fim_do_periodo(date(2026, 10, 9), freq=Freq.DIARIA) == date(2026, 10, 9)


def test_da_ipca_de_setembro_fica_em_30_09_e_casa_com_o_sidra(tmp_path: Path) -> None:
    """`date` do IPCA mensal é o fim do mês — é o que faz o `join` com SIDRA `t/1737 v/63` casar.

    Antes da consolidação o SGS gravava `2026-09-01` e o SIDRA `2026-09-30`: as duas séries eram
    idênticas valor a valor e **nenhuma linha** casava por `date` (medido em F-004).
    """
    resultado, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    quadro = quadro_do_parquet(resultado.parquet)
    datas = pd.DatetimeIndex(quadro["date"])
    fins_de_mes = datas + pd.offsets.MonthEnd(0)
    assert (datas == fins_de_mes).all(), "toda data mensal tem de ser o último dia civil do mês"
    assert float(quadro.loc[quadro["date"] == pd.Timestamp("2026-09-30"), "value"].iloc[0]) == 0.82


def test_da_pib_trimestral_fica_no_ultimo_dia_do_trimestre() -> None:
    """O PIB do 2º trimestre é `2026-06-30`, não `2026-04-01` (o que o SGS devolve)."""
    quadro = quadro_de_observacoes(
        entrada("BCB_SGS_22109"),
        [{"data": "01/01/2026", "valor": "197.0"}, {"data": "01/04/2026", "valor": "198.24"}],
        collected_at=AGORA,
    )
    assert [d.date() for d in quadro["date"]] == [date(2026, 3, 31), date(2026, 6, 30)]
    validar_continuidade(quadro, freq=Freq.TRIMESTRAL)


def test_db_vintage_e_a_data_sem_hora_do_collected_at(tmp_path: Path) -> None:
    """D-b: `vintage` = a **data** de `collected_at`, constante na série e sem hora."""
    resultado, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    quadro = quadro_do_parquet(resultado.parquet)
    assert (quadro["vintage"] == pd.Timestamp("2026-10-10")).all()
    assert (quadro["collected_at"] == pd.Timestamp("2026-10-10 20:30")).all()
    assert (quadro["vintage"] == quadro["vintage"].dt.normalize()).all(), "vintage não tem hora"
    assert not quadro.duplicated(subset=["series_id", "date", "vintage"]).any()


def test_db_offline_tira_collected_at_do_manifesto_e_e_idempotente(tmp_path: Path) -> None:
    """D-b: `--offline` reproduz o Parquet byte a byte porque `vintage` sai do manifesto.

    Se `collected_at` viesse do relógio, cada reprocessamento do **mesmo** bruto geraria um
    `vintage` novo e a PK `(series_id, date, vintage)` duplicaria a série a cada rodada.
    """
    primeira, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    esperado = sha256_de(primeira.parquet.read_bytes())
    bruto = tmp_path / "data" / "raw" / "sgs" / primeira.fatias[0].arquivo
    assert obtido_em_arquivado(bruto) == AGORA

    hashes = set()
    for _ in range(2):
        offline = extrair_serie(
            entrada("BCB_SGS_433"),
            inicio=date(2004, 1, 1),
            fim=FIM,
            offline=True,
            raiz=tmp_path,
            gravar=True,
        )
        quadro = quadro_do_parquet(offline.parquet)
        assert (quadro["vintage"] == pd.Timestamp("2026-10-10")).all()
        hashes.add(sha256_de(offline.parquet.read_bytes()))
    assert hashes == {esperado}, "duas rodadas offline têm de dar o mesmo Parquet da rodada online"


def test_dc_offline_nunca_parseia_o_manifesto_do_bruto(tmp_path: Path) -> None:
    """D-c: `<fatia>.json.meta.json` convive com `<fatia>.json` e o offline lê o dado, não o meta.

    O SGS reencontra a fatia pelo nome determinístico, então não há glob a envenenar — este
    teste trava isso: o manifesto está lá, e a série continua com as 273 observações.
    """
    primeira, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    pasta = tmp_path / "data" / "raw" / "sgs"
    assert [p.name for p in sorted(pasta.glob("*.meta.json"))] == [
        primeira.fatias[0].arquivo + ".meta.json"
    ]
    offline = extrair_serie(
        entrada("BCB_SGS_433"),
        inicio=date(2004, 1, 1),
        fim=FIM,
        offline=True,
        raiz=tmp_path,
        gravar=False,
    )
    assert offline.linhas == 273
    assert (offline.data_min, offline.data_max) == (date(2004, 1, 31), date(2026, 9, 30))


def test_db_offline_sobre_fatia_sem_manifesto_e_recusado(tmp_path: Path) -> None:
    """D-b/CA-121: fatia sem `.meta.json` é recusada, não datada pelo relógio da rodada."""
    primeira, _ = extrair(
        "BCB_SGS_433", "433__2026-10-10.json", inicio=date(2004, 1, 1), raiz=tmp_path, gravar=True
    )
    pasta = tmp_path / "data" / "raw" / "sgs"
    (pasta / (primeira.fatias[0].arquivo + ".meta.json")).unlink()

    with pytest.raises(ManifestoAusente, match="manifesto legível"):
        extrair_serie(
            entrada("BCB_SGS_433"),
            inicio=date(2004, 1, 1),
            fim=FIM,
            offline=True,
            raiz=tmp_path,
            gravar=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fonte viva — só local, excluída do CI com -m "not network"
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_live_ipca_e_ibcbr_batem_com_as_fixtures(tmp_path: Path) -> None:
    """Confere a fixture contra a fonte viva (CA-002, CA-006). Não roda no CI N1."""
    ipca = extrair_serie(
        entrada("BCB_SGS_433"), inicio=date(2004, 1, 1), fim=FIM, raiz=tmp_path, gravar=False
    )
    assert ipca.canario == ("2026-09-30", 0.82)
    ibcbr = extrair_serie(
        entrada("BCB_SGS_24364"), inicio=date(2004, 1, 1), fim=FIM, raiz=tmp_path, gravar=False
    )
    assert ibcbr.canario == ("2006-01-31", 79.44731)


@pytest.mark.network
def test_live_selic_diaria_e_fatiada_em_blocos_de_cinco_anos(tmp_path: Path) -> None:
    """CA-011 contra a fonte viva: 20+ anos de SGS 11 em 5 fatias, sem duplicata nem lacuna."""
    resultado = extrair_serie(
        entrada("BCB_SGS_11"), inicio=date(2004, 1, 1), fim=FIM, raiz=tmp_path, gravar=False
    )
    assert len(resultado.fatias) == 5
    assert resultado.duplicatas_removidas == 0
    assert resultado.linhas > 5000
    assert resultado.canario == ("2005-01-03", 0.064826)
