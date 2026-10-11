"""Testes do extrator IBGE SIDRA (F-004, SPEC RF-002/RF-004, CA-004, CA-005, CA-008..010).

Nenhum teste aqui toca a rede: tudo vem de `tests/fixtures/sidra/`, que é **resposta real** do
apisidra recortada **pela própria fonte** (parâmetro `p/200601-202609`, não por corte manual do
arquivo), mais os três corpos de erro reais do host. O único teste que vai à fonte viva está
marcado `@pytest.mark.network` e o CI N1 o exclui com `-m "not network"` (CA-123).

Onde a fixture é um recorte, o parse roda com `minimo=None` — o piso real do contrato
(`LINHAS_MINIMAS`: 562 no IPCA, 122 no PIB) é exercitado no teste de truncamento e no de rede.

Duas CAs da SPEC **não fecham no número que elas escrevem**, e os testes abaixo registram a
medição real em vez de afrouxar em silêncio (ver `docs/wiki/context/F-004.md §5`):

- **CA-004** pede número-índice "monotônico não decrescente em >= 99 % dos meses". A série real
  `t/1737 v/2266` tem **0,9626** no histórico completo e **0,9435** de 2006 em diante — 21 meses
  de deflação de verdade. O teste afirma o valor medido e o piso de `MONOTONIA_MINIMA` (0,90).
- **CA-005** pede tolerância `<= 1e-6` entre a razão do número-índice e o encadeamento de `v/63`.
  O número-índice é publicado com **2 casas decimais**, então o arredondamento sozinho impõe um
  piso de ~4e-4 pp. O teste afirma `<= 1e-3 pp` **e** que a divergência fica dentro do limite
  analítico do arredondamento — é isso que prova que as duas séries são a mesma coisa.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import pytest

from apps.pipeline.common import (
    SUFIXO_MANIFESTO,
    ErroDeExtracao,
    FonteIndisponivel,
    NumeroNaoReconhecido,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    caminho_processed,
    ler_texto,
)
from apps.pipeline.extract import ibge_sidra
from apps.pipeline.extract.ibge_sidra import (
    AUSENCIAS_SIDRA,
    LINHAS_MINIMAS,
    MONOTONIA_MINIMA,
    SERIES_SUPORTADAS,
    VALORES_CANARIO,
    ConsultaSidra,
    RespostaSidraInconsistente,
    config_de,
    consulta_de,
    descartar_cabecalho,
    entrada_de,
    extrair_serie,
    extrair_serie_offline,
    fim_do_periodo,
    fracao_nao_decrescente,
    nome_processado,
    parse_valores,
    valor_sidra,
    variacao_no_trimestre_por_razao,
)
from packages.shared.schemas import (
    Fonte,
    Freq,
    ProcessedSeriesSchema,
    StatusSerie,
    Unidade,
    load_catalog,
)

if TYPE_CHECKING:
    from pathlib import Path

COLETA = datetime(2026, 10, 10, 21, 0, tzinfo=UTC)

#: `tests/fixtures/sidra/`. Nome pela convenção de `tests/fixtures/README.md`.
#: Recorte feito **pela fonte** (`p/200601-202609` e `p/200601-202602`), não por corte do arquivo.
FIXTURAS: dict[str, str] = {
    "SIDRA_1737_V63": "t1737_v63__2026-10-10.json",
    "SIDRA_1737_V2266": "t1737_v2266__2026-10-10.json",
    "SIDRA_1621_V584_90707": "t1621_v584_c90707__2026-10-10.json",
    # Esta é o histórico inteiro (199601-202602): é onde vive o `"..."` real de 1996T1.
    "SIDRA_5932_V6564_90707": "t5932_v6564_c90707__2026-10-10.json",
}
FIXTURA_ERRO_SO_CABECALHO = "t1737_v63__erro-so-cabecalho.json"
FIXTURA_ERRO_400 = "t99999_v584__erro-400-tabela-invalida.txt"
FIXTURA_ERRO_HTML = "apisidra__erro-html-404.html"

#: Linhas de dado de cada fixture (sem o cabeçalho), medidas na gravação de 2026-10-10.
LINHAS_DA_FIXTURA: dict[str, int] = {
    "SIDRA_1737_V63": 249,  # 200601..202609
    "SIDRA_1737_V2266": 249,
    "SIDRA_1621_V584_90707": 82,  # 200601..202602
    "SIDRA_5932_V6564_90707": 122,  # 199601..202602
}

#: Tolerância de CA-005 em pontos percentuais. Ver docstring do módulo.
TOLERANCIA_CA005_PP = 1e-3


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
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": dict(cabecalhos)})
        proxima = self._respostas.pop(0) if self._respostas else None
        if proxima is None:
            msg = f"transporte falso sem resposta programada para {metodo} {url}"
            raise AssertionError(msg)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


@pytest.fixture
def dir_sidra(dir_fixtures: Path) -> Path:
    """`tests/fixtures/sidra/`."""
    return dir_fixtures / "sidra"


@pytest.fixture
def piso_de_recorte(monkeypatch: pytest.MonkeyPatch) -> None:
    """Baixa `LINHAS_MINIMAS` ao tamanho da fixture nos testes de caminho completo.

    O piso real (562 linhas no IPCA) vale para a série inteira; a fixture é o recorte de 2006+.
    Quem testa o piso é `test_truncamento_abaixo_do_piso_do_contrato_e_recusado`, que **não** usa
    esta fixture.
    """
    for series_id, linhas in LINHAS_DA_FIXTURA.items():
        monkeypatch.setitem(LINHAS_MINIMAS, series_id, linhas)


def corpo(dir_sidra: Path, series_id: str) -> bytes:
    """Bytes crus da fixture da série."""
    return (dir_sidra / FIXTURAS[series_id]).read_bytes()


def _resposta(conteudo: bytes, *, series_id: str, status: int = 200) -> RespostaBruta:
    return RespostaBruta(
        url=consulta_de(series_id).url,
        status=status,
        conteudo=conteudo,
        cabecalhos={"Content-Type": "application/json; charset=utf-8"},
        obtida_em=COLETA,
    )


def _reescrever(original: bytes, transformar: Any) -> bytes:
    """Reescreve a fixture com uma alteração — **adulteração em memória**, nunca gravada no repo.

    É como se testa o caminho de erro sem inventar fixture: o layout continua o real do apisidra
    (cabeçalho inclusive) e só o campo sob teste muda.
    """
    bruto = json.loads(ler_texto(original, "utf-8"))
    return json.dumps(transformar(bruto), ensure_ascii=False).encode("utf-8")


def parsear(dir_sidra: Path, series_id: str, **kwargs: Any) -> pd.DataFrame:
    """Parse da fixture com o piso desligado (ela é recorte)."""
    kwargs.setdefault("minimo", None)
    return parse_valores(
        corpo(dir_sidra, series_id),
        series_id=series_id,
        origem=FIXTURAS[series_id],
        collected_at=COLETA,
        **kwargs,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CA-004 — a primeira linha é cabeçalho, não dado
# ─────────────────────────────────────────────────────────────────────────────


def test_ca004_primeira_linha_e_cabecalho_e_nao_entra_como_dado(dir_sidra: Path) -> None:
    """A linha 1 do array é descartada: 250 linhas no JSON, 249 observações no quadro."""
    bruto = json.loads(ler_texto(corpo(dir_sidra, "SIDRA_1737_V2266"), "utf-8"))
    assert len(bruto) == LINHAS_DA_FIXTURA["SIDRA_1737_V2266"] + 1
    assert bruto[0]["V"] == "Valor"
    assert bruto[0]["D3C"] == "Mês (Código)"  # o período do cabeçalho é um rótulo, não AAAAMM

    quadro = parsear(dir_sidra, "SIDRA_1737_V2266")
    assert len(quadro) == LINHAS_DA_FIXTURA["SIDRA_1737_V2266"]
    # Se o cabeçalho tivesse entrado, a 1ª data seria irreparável e o 1º valor viria da string
    # "Valor" — o quadro começa em janeiro de 2006, fim de período.
    assert quadro["date"].iloc[0] == pd.Timestamp("2006-01-31")
    assert quadro["value"].iloc[0] == pytest.approx(2550.36, abs=1e-9)
    assert quadro["value"].notna().all()


def test_ca004_array_sem_cabecalho_levanta_em_vez_de_virar_dado(dir_sidra: Path) -> None:
    """Se a fonte parar de mandar o cabeçalho, o parser recusa em vez de perder a 1ª observação."""
    bruto = json.loads(ler_texto(corpo(dir_sidra, "SIDRA_1737_V63"), "utf-8"))
    sem_cabecalho = bruto[1:]
    with pytest.raises(RespostaSidraInconsistente, match="1ª linha deveria ser o cabeçalho"):
        descartar_cabecalho(sem_cabecalho, origem="fixtura adulterada")


def test_ca004_numero_indice_e_quase_monotonico_e_vem_como_index(dir_sidra: Path) -> None:
    """Medição real da monotonia + `unit='index'`. Registra que os 99 % da SPEC não se cumprem."""
    quadro = parsear(dir_sidra, "SIDRA_1737_V2266")
    assert quadro["unit"].unique().tolist() == [Unidade.INDEX.value]
    assert quadro["freq"].unique().tolist() == [Freq.MENSAL.value]

    fracao = fracao_nao_decrescente(quadro)
    assert fracao == pytest.approx(0.943548, abs=1e-6)  # medido em 2026-10-10, janela 2006+
    assert fracao >= MONOTONIA_MINIMA
    # CA-004 escreve ">= 99 %": a série real NÃO cumpre, e afrouxar sem registrar seria o pior
    # dos mundos. A medição acima é a evidência que vai para o Feature Contract.
    assert fracao < 0.99


def test_ca004_serie_de_variacao_nao_passa_pela_guarda_de_numero_indice(dir_sidra: Path) -> None:
    """A guarda de monotonia existe para pegar `v/63` entrando no lugar de `v/2266`."""
    variacao = parsear(dir_sidra, "SIDRA_1737_V63")
    assert fracao_nao_decrescente(variacao) < MONOTONIA_MINIMA


def test_ca004_encoding_utf8_explicito_nao_corrompe_acento(dir_sidra: Path) -> None:
    """R10 / Anti-SPEC §10.4.26: `Variação mensal` só sobrevive com `encoding='utf-8'`."""
    bytes_crus = corpo(dir_sidra, "SIDRA_1737_V63")
    assert "Variação mensal" in ler_texto(bytes_crus, "utf-8")
    # Com o default do locale no Windows (cp1252) o mesmo byte vira "Variação".
    assert "Variação mensal" not in bytes_crus.decode("cp1252")
    assert config_de("SIDRA_1737_V63").encoding == "utf-8"


# ─────────────────────────────────────────────────────────────────────────────
# CA-008 / CA-009 — valores-canário do PIB e espelho do SGS
# ─────────────────────────────────────────────────────────────────────────────


def test_ca008_valores_canario_do_pib_2006(dir_sidra: Path) -> None:
    """`t/1621 v/584 c11255/90707`: 2006T1 = 131.74, 2006T2 = 132.14, 2006T3 = 134.36."""
    quadro = parsear(dir_sidra, "SIDRA_1621_V584_90707").set_index("date")
    esperado = {"2006-03-31": 131.74, "2006-06-30": 132.14, "2006-09-30": 134.36}
    for dia, valor in esperado.items():
        assert float(quadro.loc[dia, "value"]) == pytest.approx(valor, abs=1e-9)
    assert quadro.index[0] == pd.Timestamp("2006-03-31")  # 1T2006 coberto, fim de período


def test_ca009_catalogo_declara_sgs_22109_como_espelho_e_lag_de_60_dias() -> None:
    """CA-009/CA-010: o espelho e o lag vêm do catálogo; quem materializa `asof` é F-018."""
    pib = entrada_de("SIDRA_1621_V584_90707")
    assert pib.identificador == "t/1621 v/584 c11255/90707"
    assert pib.freq is Freq.TRIMESTRAL
    assert pib.unit is Unidade.INDEX
    # CA-010 depende deste número: sem `lag_divulgacao_dias` a regra anti-look-ahead (o PIB de T
    # só é conhecido ~60 dias depois do fim de T) não é implementável em F-018.
    assert pib.lag_divulgacao_dias == 60
    assert "22109" in pib.obs
    espelho = {e.series_id for e in load_catalog() if e.series_id == "BCB_SGS_22109"}
    assert espelho == {"BCB_SGS_22109"}


# ─────────────────────────────────────────────────────────────────────────────
# CA-005 — IPCA trimestral por razão do número-índice
# ─────────────────────────────────────────────────────────────────────────────


def test_ca005_razao_do_numero_indice_bate_com_encadeamento_de_v63(dir_sidra: Path) -> None:
    """`I_fim/I_ini - 1` ≡ encadeamento geométrico de `v/63` no mesmo trimestre.

    `v/63` é idêntico a SGS 433 (CA-002, conferido no teste de rede), então isto também é a
    reconciliação do número-índice contra o SGS. A tolerância é 1e-3 pp e não os 1e-6 da SPEC
    porque o número-índice é publicado com 2 decimais — o segundo `assert` prova que a divergência
    é exatamente o arredondamento e nada mais.
    """
    indice = parsear(dir_sidra, "SIDRA_1737_V2266")
    variacao = parsear(dir_sidra, "SIDRA_1737_V63")

    razao = variacao_no_trimestre_por_razao(indice)
    razao["q"] = razao["date"].dt.to_period("Q")

    mensal = variacao.dropna(subset=["value"]).copy()
    mensal["q"] = mensal["date"].dt.to_period("Q")
    encadeado = (
        mensal.groupby("q")["value"]
        .apply(lambda s: (np.prod(1.0 + s / 100.0) - 1.0) * 100.0)
        .reset_index(name="encadeado")
    )

    junto = razao.merge(encadeado, on="q", how="inner")
    assert len(junto) == 82  # 2006T2..2026T3 (o 1º trimestre não tem base anterior na fixture)
    diferenca = (junto["value"] - junto["encadeado"]).abs()
    assert diferenca.max() == pytest.approx(3.523e-4, rel=0.05)
    assert diferenca.max() <= TOLERANCIA_CA005_PP

    # Limite analítico do arredondamento de 2 casas do número-índice, trimestre a trimestre.
    fim = indice.set_index("date")["value"].resample("QE").last()
    junto["I_fim"] = junto["date"].map(fim)
    junto["I_ini"] = junto["date"].map(fim.shift(1))
    limite = (0.005 / junto["I_ini"] + 0.005 / junto["I_fim"]) * 100.0
    # Folga de 2x: `v/63` também é publicado com 2 decimais e soma o seu próprio arredondamento.
    assert (diferenca <= limite * 2.0).all()


# ─────────────────────────────────────────────────────────────────────────────
# Ausência é None, nunca 0 (Anti-SPEC §10.1.4)
# ─────────────────────────────────────────────────────────────────────────────


def test_marcador_de_ausencia_vira_none_e_nunca_zero(dir_sidra: Path) -> None:
    """`"..."` real de `t/5932` em 1996T1 → `None`. Zero ali afirmaria PIB parado."""
    quadro = parsear(dir_sidra, "SIDRA_5932_V6564_90707").set_index("date")
    primeiro = quadro.loc["1996-03-31", "value"]
    assert pd.isna(primeiro)
    assert primeiro != 0
    # O resto da série não é nulo: o nulo é a exceção documentada, não o default do parser.
    assert quadro["value"].isna().sum() == 1
    assert float(quadro.loc["2006-03-31", "value"]) == pytest.approx(1.6, abs=1e-9)


@pytest.mark.parametrize("marcador", sorted(AUSENCIAS_SIDRA))
def test_todo_marcador_documentado_do_sidra_vira_none(marcador: str) -> None:
    """`""`, `"-"`, `".."`, `"..."` e `"X"` (sigilo) são ausência — nenhum deles é `0`."""
    assert valor_sidra(marcador, origem="teste") is None


def test_valor_com_virgula_levanta_em_vez_de_mudar_de_escala() -> None:
    """O SIDRA usa ponto decimal. Vírgula aqui é fonte trocada, não número a reinterpretar."""
    assert valor_sidra("7695.82", origem="teste") == pytest.approx(7695.82)
    with pytest.raises(NumeroNaoReconhecido):
        valor_sidra("7.695,82", origem="teste")


# ─────────────────────────────────────────────────────────────────────────────
# Período → data de fim de período
# ─────────────────────────────────────────────────────────────────────────────


def test_mesmo_codigo_de_periodo_da_duas_datas_conforme_a_freq_do_catalogo() -> None:
    """`"200601"` é 2006-01-31 em `t/1737` (M) e 2006-03-31 em `t/1621` (Q). R12 puro."""
    assert fim_do_periodo("200601", freq=Freq.MENSAL, origem="t") == date(2006, 1, 31)
    assert fim_do_periodo("200601", freq=Freq.TRIMESTRAL, origem="t") == date(2006, 3, 31)


@pytest.mark.parametrize(
    ("codigo", "freq", "esperado"),
    [
        ("202609", Freq.MENSAL, date(2026, 9, 30)),
        ("200602", Freq.MENSAL, date(2006, 2, 28)),  # fevereiro não-bissexto
        ("200802", Freq.MENSAL, date(2008, 2, 29)),  # fevereiro bissexto
        ("200612", Freq.MENSAL, date(2006, 12, 31)),
        ("202602", Freq.TRIMESTRAL, date(2026, 6, 30)),
        ("200604", Freq.TRIMESTRAL, date(2006, 12, 31)),
    ],
)
def test_periodo_vira_ultimo_dia_do_periodo(codigo: str, freq: Freq, esperado: date) -> None:
    """Fim de período, sempre (`CLAUDE.md §3`) — nunca o 1º dia nem a data de divulgação."""
    assert fim_do_periodo(codigo, freq=freq, origem="t") == esperado


@pytest.mark.parametrize("codigo", ["20260", "2026091", "20261a", "202613", "", "Mês (Código)"])
def test_periodo_malformado_levanta(codigo: str) -> None:
    """Código fora de `AAAAMM`/`AAAAT` levanta — inclusive o rótulo do cabeçalho."""
    with pytest.raises(RespostaSidraInconsistente):
        fim_do_periodo(codigo, freq=Freq.MENSAL, origem="t")


def test_trimestre_5_levanta() -> None:
    """`200605` não existe como trimestre: é tabela mensal lida como trimestral."""
    with pytest.raises(RespostaSidraInconsistente, match="trimestre 5"):
        fim_do_periodo("200605", freq=Freq.TRIMESTRAL, origem="t")


# ─────────────────────────────────────────────────────────────────────────────
# Continuidade: nenhum mês/trimestre faltando
# ─────────────────────────────────────────────────────────────────────────────


def test_serie_mensal_da_fonte_nao_tem_mes_faltando(dir_sidra: Path) -> None:
    """249 meses contíguos de 2006-01 a 2026-09, sem lacuna e sem repetição."""
    quadro = parsear(dir_sidra, "SIDRA_1737_V63")
    periodos = quadro["date"].dt.to_period("M")
    assert len(periodos) == len(set(periodos)) == 249
    assert set(periodos) == set(pd.period_range("2006-01", "2026-09", freq="M"))


def test_mes_faltando_no_meio_levanta(dir_sidra: Path) -> None:
    """Lacuna não se preenche por interpolação (`CLAUDE.md §4`): levanta."""
    adulterado = _reescrever(
        corpo(dir_sidra, "SIDRA_1737_V63"),
        lambda b: [linha for linha in b if linha.get("D3C") != "201003"],
    )
    with pytest.raises(RespostaSidraInconsistente, match="mes\\(es\\) faltando"):
        parse_valores(
            adulterado,
            series_id="SIDRA_1737_V63",
            origem="fixtura com buraco",
            collected_at=COLETA,
            minimo=None,
        )


def test_trimestre_faltando_no_meio_levanta(dir_sidra: Path) -> None:
    """Mesma guarda na grade trimestral — trimestre sem divulgação não passa calado."""
    adulterado = _reescrever(
        corpo(dir_sidra, "SIDRA_1621_V584_90707"),
        lambda b: [linha for linha in b if linha.get("D3C") != "201502"],
    )
    with pytest.raises(RespostaSidraInconsistente, match="trimestre\\(s\\) faltando"):
        parse_valores(
            adulterado,
            series_id="SIDRA_1621_V584_90707",
            origem="fixtura com buraco",
            collected_at=COLETA,
            minimo=None,
        )


def test_periodo_repetido_levanta(dir_sidra: Path) -> None:
    """Duas linhas para o mesmo trimestre quebrariam a PK antes do parquet."""
    adulterado = _reescrever(
        corpo(dir_sidra, "SIDRA_1621_V584_90707"),
        lambda b: [b[0], b[1], dict(b[1]), *b[2:]],
    )
    with pytest.raises(RespostaSidraInconsistente, match="período repetido"):
        parse_valores(
            adulterado,
            series_id="SIDRA_1621_V584_90707",
            origem="fixtura duplicada",
            collected_at=COLETA,
            minimo=None,
        )


def test_periodo_fora_de_ordem_levanta(dir_sidra: Path) -> None:
    """Ordem crescente é contrato: índice temporal desordenado estraga toda agregação adiante."""
    adulterado = _reescrever(
        corpo(dir_sidra, "SIDRA_1621_V584_90707"),
        lambda b: [b[0], b[2], b[1], *b[3:]],
    )
    with pytest.raises(RespostaSidraInconsistente, match="fora de ordem"):
        parse_valores(
            adulterado,
            series_id="SIDRA_1621_V584_90707",
            origem="fixtura desordenada",
            collected_at=COLETA,
            minimo=None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tabela/variável trocada (a pegadinha mais provável desta fonte)
# ─────────────────────────────────────────────────────────────────────────────


def test_resposta_de_1621_parseada_como_1620_levanta(dir_sidra: Path) -> None:
    """`t/1620` é volume SEM ajuste sazonal e `t/1621` COM: trocar muda o eixo de crescimento.

    Sem a conferência de `D2C` o quadro sairia com o `series_id` de 1620 e os números de 1621 —
    erro que nenhum schema pega, porque as duas séries têm a mesma forma.
    """
    with pytest.raises(RespostaSidraInconsistente, match="variável D2C='584'"):
        parse_valores(
            corpo(dir_sidra, "SIDRA_1621_V584_90707"),
            series_id="SIDRA_1620_V583_90707",
            origem="fixtura trocada",
            collected_at=COLETA,
            minimo=None,
        )


def test_categoria_de_c11255_trocada_levanta(dir_sidra: Path) -> None:
    """Agropecuária (`90687`) no lugar do PIB (`90707`) é outra série, não outra linha."""
    adulterado = _reescrever(
        corpo(dir_sidra, "SIDRA_1621_V584_90707"),
        lambda b: [b[0], *({**linha, "D4C": "90687"} for linha in b[1:])],
    )
    with pytest.raises(RespostaSidraInconsistente, match="categoria D4C='90687'"):
        parse_valores(
            adulterado,
            series_id="SIDRA_1621_V584_90707",
            origem="fixtura trocada",
            collected_at=COLETA,
            minimo=None,
        )


def test_nivel_territorial_diferente_de_brasil_levanta(dir_sidra: Path) -> None:
    """`n1/all` é Brasil. Linha de UF entrando no agregado nacional é erro, não detalhe."""
    adulterado = _reescrever(
        corpo(dir_sidra, "SIDRA_1737_V63"),
        lambda b: [b[0], {**b[1], "NC": "3"}, *b[2:]],
    )
    with pytest.raises(RespostaSidraInconsistente, match="nível territorial"):
        parse_valores(
            adulterado,
            series_id="SIDRA_1737_V63",
            origem="fixtura trocada",
            collected_at=COLETA,
            minimo=None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Caminhos de erro reais da fonte (CA-003, CA-124, R1)
# ─────────────────────────────────────────────────────────────────────────────


def test_resposta_so_com_cabecalho_e_recusada_como_truncada(dir_sidra: Path) -> None:
    """Corpo real de `p/197001`: HTTP 200, JSON válido, zero linha de dado. É o R1 desta fonte."""
    bruto = (dir_sidra / FIXTURA_ERRO_SO_CABECALHO).read_bytes()
    with pytest.raises(RespostaTruncada):
        parse_valores(
            bruto,
            series_id="SIDRA_1737_V63",
            origem=FIXTURA_ERRO_SO_CABECALHO,
            collected_at=COLETA,
            minimo=None,
        )


def test_so_cabecalho_nao_deixa_rastro_em_processed(dir_sidra: Path, tmp_path: Path) -> None:
    """CA-003: resposta inválida não grava nada em `data/processed/`.

    Validar vem antes de escrever — é o que torna a CA estrutural em vez de promessa.
    """
    bruto = (dir_sidra / FIXTURA_ERRO_SO_CABECALHO).read_bytes()
    transporte = TransporteGravado(_resposta(bruto, series_id="SIDRA_1737_V63"))
    with pytest.raises(RespostaTruncada):
        extrair_serie("SIDRA_1737_V63", transporte=transporte, raiz=tmp_path)
    destino = caminho_processed(nome_processado("SIDRA_1737_V63"), raiz=tmp_path)
    assert not destino.exists()
    # Nem o bruto: o arquivamento vem depois do parse, de propósito.
    assert not (tmp_path / "data" / "raw" / "sidra").exists()


def test_html_de_erro_com_http_200_e_recusado(dir_sidra: Path, tmp_path: Path) -> None:
    """R1 / Anti-SPEC §10.1.5: HTML com status 200 é página de erro, não série.

    O corpo é o 404 real que `apisidra.ibge.gov.br` serve num caminho inválido; o status 200 é
    forçado no teste para exercitar a guarda do caminho em que a fonte mente sobre o sucesso —
    é o modo de falha de metade das fontes do projeto.
    """
    html = (dir_sidra / FIXTURA_ERRO_HTML).read_bytes()
    assert html.lstrip().startswith(b"<!DOCTYPE html")
    transporte = TransporteGravado(_resposta(html, series_id="SIDRA_1737_V63", status=200))
    with pytest.raises(RespostaDeErroComStatus200, match="corpo HTML"):
        extrair_serie("SIDRA_1737_V63", transporte=transporte, raiz=tmp_path)
    assert not (tmp_path / "data").exists()


def test_html_de_erro_com_http_404_vira_fonte_indisponivel(dir_sidra: Path, tmp_path: Path) -> None:
    """Com o status verdadeiro (404), a falha é de transporte e para antes de qualquer parse."""
    html = (dir_sidra / FIXTURA_ERRO_HTML).read_bytes()
    transporte = TransporteGravado(_resposta(html, series_id="SIDRA_1737_V63", status=404))
    with pytest.raises(FonteIndisponivel, match="404"):
        extrair_serie("SIDRA_1737_V63", transporte=transporte, raiz=tmp_path)


def test_corpo_400_de_tabela_invalida_e_texto_plano_da_fonte(dir_sidra: Path) -> None:
    """`t/99999` responde HTTP 400 `text/plain` — tabela inexistente não vira série vazia."""
    texto = ler_texto((dir_sidra / FIXTURA_ERRO_400).read_bytes(), "utf-8")
    assert texto.strip() == "Tabela 99999: Tabela inválida"
    transporte = TransporteGravado(
        _resposta(texto.encode("utf-8"), series_id="SIDRA_1737_V63", status=400)
    )
    with pytest.raises(FonteIndisponivel, match="400"):
        extrair_serie("SIDRA_1737_V63", transporte=transporte)


def test_ca124_fixtures_de_erro_existem(dir_sidra: Path) -> None:
    """CA-124: fixture de caminho de erro é obrigatória por extrator. Aqui são três, reais."""
    for nome in (FIXTURA_ERRO_SO_CABECALHO, FIXTURA_ERRO_400, FIXTURA_ERRO_HTML):
        assert (dir_sidra / nome).is_file(), nome
    assert sorted(p.name for p in dir_sidra.glob("*__erro*")) == sorted(
        [FIXTURA_ERRO_HTML, FIXTURA_ERRO_400, FIXTURA_ERRO_SO_CABECALHO]
    )


def test_toda_fixture_cabe_no_limite_de_200kb(dir_sidra: Path) -> None:
    """`tests/fixtures/README.md`: fixture é amostra, não espelho da fonte."""
    grandes = {p.name: p.stat().st_size for p in dir_sidra.iterdir() if p.stat().st_size > 200_000}
    assert grandes == {}


def test_truncamento_abaixo_do_piso_do_contrato_e_recusado(dir_sidra: Path) -> None:
    """Sem `minimo=None`, a fixture de 249 linhas bate no piso de 562 do contrato (R2)."""
    assert LINHAS_MINIMAS["SIDRA_1737_V63"] == 562
    with pytest.raises(RespostaTruncada, match="mínimo esperado 562"):
        parse_valores(
            corpo(dir_sidra, "SIDRA_1737_V63"),
            series_id="SIDRA_1737_V63",
            origem=FIXTURAS["SIDRA_1737_V63"],
            collected_at=COLETA,
        )


def test_data_futura_levanta(dir_sidra: Path) -> None:
    """Coleta anterior ao último período significa relógio ou tabela errados (CA-013 análogo)."""
    with pytest.raises(RespostaSidraInconsistente, match="período futuro"):
        parse_valores(
            corpo(dir_sidra, "SIDRA_1737_V63"),
            series_id="SIDRA_1737_V63",
            origem="coleta antiga",
            collected_at=datetime(2010, 1, 1, tzinfo=UTC),
            minimo=None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Contrato de saída, vintage e idempotência
# ─────────────────────────────────────────────────────────────────────────────


def test_quadro_respeita_processed_series_schema(dir_sidra: Path) -> None:
    """As 8 colunas de `ProcessedSeriesSchema`, nada mais (`strict=True`)."""
    quadro = parsear(dir_sidra, "SIDRA_1621_V584_90707")
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
    validado = ProcessedSeriesSchema.validate(quadro, lazy=True)
    assert len(validado) == len(quadro)
    assert quadro["source"].unique().tolist() == [Fonte.IBGE_SIDRA.value]


def test_series_id_vem_do_catalogo_e_nao_do_rotulo_da_fonte(dir_sidra: Path) -> None:
    """O `D2N` da fonte é prosa; o `series_id` vem do catálogo e nunca do rótulo."""
    quadro = parsear(dir_sidra, "SIDRA_5932_V6564_90707")
    assert quadro["series_id"].unique().tolist() == ["SIDRA_5932_V6564_90707"]
    bruto = json.loads(ler_texto(corpo(dir_sidra, "SIDRA_5932_V6564_90707"), "utf-8"))
    assert "Taxa trimestre" in bruto[1]["D2N"]  # o rótulo existe e não entra em lugar nenhum


def test_vintage_e_a_data_do_collected_at_e_a_pk_e_unica(dir_sidra: Path) -> None:
    """D-b: `vintage` = a **data** (sem hora) de `collected_at`, constante na série.

    Não é a última data do histórico: o IBGE revisa o PIB de trimestres passados **sem**
    acrescentar trimestre novo, e nesse caso "última data" não mudaria — as duas safras
    colidiriam na PK `(series_id, date, vintage)` e a revisão sobrescreveria o retrato anterior.
    """
    quadro = parsear(dir_sidra, "SIDRA_1621_V584_90707")
    assert (quadro["vintage"] == quadro["vintage"].iloc[0]).all()
    assert quadro["vintage"].iloc[0] == pd.Timestamp(COLETA.date())
    assert quadro["vintage"].iloc[0] != quadro["date"].max() == pd.Timestamp("2026-06-30")
    assert (quadro["vintage"] == quadro["vintage"].dt.normalize()).all(), "vintage não tem hora"
    chave = quadro[["series_id", "date", "vintage"]]
    assert not chave.duplicated().any()


def test_idempotencia_segunda_rodada_nao_reescreve_o_bruto(
    dir_sidra: Path, tmp_path: Path, piso_de_recorte: None
) -> None:
    """CA-027: mesmo retrato ⇒ mesmo nome ⇒ nada escrito na 2ª vez, mesmo `sha256`."""
    bruto = corpo(dir_sidra, "SIDRA_1621_V584_90707")
    series_id = "SIDRA_1621_V584_90707"

    primeiro = extrair_serie(
        series_id,
        transporte=TransporteGravado(_resposta(bruto, series_id=series_id)),
        raiz=tmp_path,
    )
    assert not primeiro.raw_idempotente
    assert primeiro.caminho_raw is not None
    assert primeiro.caminho_raw.name == "t1621_v584_c90707__2026-06-30.json"
    parquet_1 = primeiro.caminho_processed
    assert parquet_1 is not None
    conteudo_1 = parquet_1.read_bytes()

    segundo = extrair_serie(
        series_id,
        transporte=TransporteGravado(_resposta(bruto, series_id=series_id)),
        raiz=tmp_path,
    )
    assert segundo.raw_idempotente
    assert segundo.sha256_raw == primeiro.sha256_raw
    assert parquet_1.read_bytes() == conteudo_1
    # Um arquivo de dado + um manifesto, nada duplicado.
    pasta = primeiro.caminho_raw.parent
    assert sorted(p.name for p in pasta.iterdir()) == [
        "t1621_v584_c90707__2026-06-30.json",
        "t1621_v584_c90707__2026-06-30.json" + SUFIXO_MANIFESTO,
    ]


def test_offline_le_o_dado_e_nao_o_manifesto(
    dir_sidra: Path, tmp_path: Path, piso_de_recorte: None
) -> None:
    """`*.meta.json` também casa com `*__*.json`: sem filtro, `--offline` parsearia o manifesto."""
    series_id = "SIDRA_1621_V584_90707"
    bruto = corpo(dir_sidra, series_id)
    extrair_serie(
        series_id,
        transporte=TransporteGravado(_resposta(bruto, series_id=series_id)),
        raiz=tmp_path,
    )
    resultado = extrair_serie_offline(series_id, raiz=tmp_path)
    assert resultado.caminho_raw is not None
    assert not resultado.caminho_raw.name.endswith(SUFIXO_MANIFESTO)
    assert resultado.linhas == LINHAS_DA_FIXTURA[series_id]


def test_offline_sem_bruto_arquivado_levanta(tmp_path: Path) -> None:
    """Modo offline não inventa série quando `data/raw/sidra/` está vazio."""
    with pytest.raises(ErroDeExtracao, match="modo offline"):
        extrair_serie_offline("SIDRA_1737_V63", raiz=tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo, configuração e Validation Mode (AGENTS.md §15)
# ─────────────────────────────────────────────────────────────────────────────


def test_todas_as_series_ibge_sidra_ok_do_catalogo_tem_extrator() -> None:
    """O Feature Contract cobre **todas** as entradas `ok` da fonte — em igualdade de conjuntos."""
    do_catalogo = {
        e.series_id
        for e in load_catalog()
        if e.fonte is Fonte.IBGE_SIDRA and e.status is StatusSerie.OK
    }
    assert do_catalogo == set(SERIES_SUPORTADAS)
    assert len(SERIES_SUPORTADAS) == 6


def test_series_descartadas_ou_a_confirmar_ficam_fora() -> None:
    """Desemprego (L9) e IPCA por grupos (L13) estão fora do escopo mínimo, por decisão."""
    fora = {
        e.series_id
        for e in load_catalog()
        if e.fonte is Fonte.IBGE_SIDRA and e.status is not StatusSerie.OK
    }
    assert fora == {
        "SIDRA_2176_DESOCUPACAO_PME",
        "SIDRA_4099_DESOCUPACAO_PNADC",
        "SIDRA_IPCA_GRUPOS_2006_2011",
    }
    assert not fora & set(SERIES_SUPORTADAS)


@pytest.mark.parametrize("series_id", SERIES_SUPORTADAS)
def test_config_de_cada_serie_declara_o_que_a_infra_exige(series_id: str) -> None:
    """Encoding explícito, piso de contagem, canário, destino e URL montada do catálogo."""
    config = config_de(series_id)
    assert config.fonte is Fonte.IBGE_SIDRA
    assert config.encoding == "utf-8"
    assert config.formato == "json"
    assert config.destino_raw == "data/raw/sidra"
    assert config.contagem_minima_esperada == LINHAS_MINIMAS[series_id]
    assert config.valor_canario == VALORES_CANARIO[series_id]
    assert config.base_url.startswith("https://apisidra.ibge.gov.br/values/t/")
    assert config.base_url.endswith(
        "/p/all" if consulta_de(series_id).classificacao is None else "/c11255/90707"
    )


@pytest.mark.parametrize("series_id", SERIES_SUPORTADAS)
def test_identificador_montado_bate_com_o_catalogo(series_id: str) -> None:
    """Divergência entre módulo e catálogo quebra no import; aqui fica explícita por série."""
    assert consulta_de(series_id).identificador == entrada_de(series_id).identificador


def test_serie_de_outra_fonte_nao_e_aceita() -> None:
    """Pedir SGS ao extrator do SIDRA é erro de chamada, não série vazia."""
    with pytest.raises(ErroDeExtracao, match="não é do SIDRA"):
        consulta_de("BCB_SGS_433")


def test_url_da_consulta_e_montada_e_nao_colada() -> None:
    """A URL sai da `ConsultaSidra`: trocar tabela/variável não exige editar string."""
    assert ConsultaSidra(tabela=1737, variavel=2266).url == (
        "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/all"
    )
    assert ConsultaSidra(tabela=1621, variavel=584, classificacao=11255, categoria=90707).url == (
        "https://apisidra.ibge.gov.br/values/t/1621/n1/all/v/584/p/all/c11255/90707"
    )


def test_resumo_da_evidencia_e_somente_ascii(
    dir_sidra: Path, tmp_path: Path, piso_de_recorte: None
) -> None:
    """`print` de caractere fora do cp1252 derruba o job no Windows **depois** de gravar tudo."""
    series_id = "SIDRA_1621_V584_90707"
    resultado = extrair_serie(
        series_id,
        transporte=TransporteGravado(_resposta(corpo(dir_sidra, series_id), series_id=series_id)),
        raiz=tmp_path,
        gravar=False,
    )
    linha = resultado.resumo()
    assert linha.isascii(), linha
    assert series_id in linha


def test_cli_offline_devolve_zero_e_imprime_so_ascii(
    dir_sidra: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """A CLI é o contrato de uso; `--offline` fecha o ciclo sem rede."""
    series_id = "SIDRA_1621_V584_90707"
    monkeypatch.setitem(LINHAS_MINIMAS, series_id, LINHAS_DA_FIXTURA[series_id])
    monkeypatch.setattr(ibge_sidra, "caminho_destino_raw", lambda c, raiz=None: tmp_path)
    extrair_serie(
        series_id,
        transporte=TransporteGravado(_resposta(corpo(dir_sidra, series_id), series_id=series_id)),
        raiz=tmp_path,
        gravar=False,
    )
    capsys.readouterr()
    codigo = ibge_sidra.main(["--series", series_id, "--offline", "--sem-gravar"])
    saida = capsys.readouterr().out
    assert codigo == 0
    assert saida.isascii(), saida
    assert series_id in saida


# ─────────────────────────────────────────────────────────────────────────────
# Contrato contra a fonte viva — fora do CI N1
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_fonte_viva_entrega_as_6_series_com_os_canarios(tmp_path: Path) -> None:
    """Contrato vivo: shape + canário + piso + continuidade nas 6 séries (CA-004/005/008)."""
    resultados = ibge_sidra.extrair(raiz=tmp_path, gravar=False)
    assert set(resultados) == set(SERIES_SUPORTADAS)
    for series_id, resultado in resultados.items():
        dia, valor = VALORES_CANARIO[series_id]
        assert resultado.linhas >= LINHAS_MINIMAS[series_id]
        assert resultado.data_inicio <= date(2006, 3, 31)
        assert resultado.vintage >= resultado.data_fim, "vintage = safra da coleta (D-b)"
        quadro = extrair_serie_offline(series_id, raiz=tmp_path, gravar=False)
        assert quadro.linhas == resultado.linhas, series_id
        assert valor is not None, (series_id, dia)


@pytest.mark.network
def test_fonte_viva_reconcilia_com_o_sgs(tmp_path: Path) -> None:
    """CA-002 e CA-009 contra a fonte viva: `v/63` ≡ SGS 433 e `t/1621` ≡ SGS 22109."""
    from apps.pipeline.common import ClienteHTTP

    sidra = parse_valores(
        ClienteHTTP(config_de("SIDRA_1737_V63")).get().conteudo,
        series_id="SIDRA_1737_V63",
        origem="live",
        collected_at=datetime.now(tz=UTC),
    )
    sgs = pd.DataFrame(
        ClienteHTTP(
            config_de("SIDRA_1737_V63").model_copy(
                update={
                    "base_url": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json",
                    "contagem_minima_esperada": 249,
                }
            )
        ).json_array()
    )
    sgs["k"] = pd.to_datetime(sgs["data"], format="%d/%m/%Y").dt.to_period("M")
    sgs["sgs"] = sgs["valor"].astype(float)
    sidra["k"] = sidra["date"].dt.to_period("M")
    junto = sidra.merge(sgs[["k", "sgs"]], on="k", how="inner").dropna()
    assert len(junto) >= 540
    assert (junto["value"] - junto["sgs"]).abs().max() == pytest.approx(0.0, abs=1e-9)
