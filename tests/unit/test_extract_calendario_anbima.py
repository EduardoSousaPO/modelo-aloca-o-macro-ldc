"""F-008 — calendário de dias úteis da ANBIMA: um teste por CA + os negativos da classe B.

Fonte dos testes: `tests/fixtures/anbima-feriados/` — páginas **reais** de
`https://www.anbima.com.br/feriados/fer_nacionais/<ano>.asp`, gravadas em 2026-10-10
(procedência em `tests/fixtures/anbima-feriados/README.md`). Nenhum teste deste arquivo toca a
rede; o contrato contra a fonte viva está em `@pytest.mark.network` no fim.

Mapa CA → teste:

- **CA-051** — `test_ca051_*`: 2006 tem exatamente 249 dias úteis.
- **CA-052** — `test_ca052_*`: fim de trimestre em feriado ou fim de semana cai no dia útil
  **anterior**, nunca no dia civil.

Os demais são as guardas que o Validation Mode (`AGENTS.md §15`) exige de um extrator de fonte:
corpo de erro, planilha BIFF no lugar do HTML, data fora da cobertura, idempotência, ordenação e
duplicidade, saída só em ASCII.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from apps.pipeline.common import (
    FormatoInesperado,
    RespostaBruta,
    sha256_de,
)
from apps.pipeline.extract import calendario_anbima as mod
from apps.pipeline.extract.calendario_anbima import (
    ANO_FIM,
    ANO_INICIO,
    ANO_INICIO_FONTE,
    FERIADOS_MINIMOS_POR_ANO,
    SERIES_ID,
    URL_XLS_REGISTRO,
    Calendario,
    CalendarioDiasUteisSchema,
    CalendarioInconsistente,
    Feriado,
    ForaDaCoberturaDoCalendario,
    parse_feriados_do_ano,
)
from packages.shared.schemas import load_catalog

if TYPE_CHECKING:
    from pathlib import Path

#: Anos cujas páginas reais estão gravadas em `tests/fixtures/anbima-feriados/`.
ANOS_FIXTURE: tuple[int, ...] = (2006, 2024, 2025, 2026)
DATA_COLETA_FIXTURE = "2026-10-10"


# ─────────────────────────────────────────────────────────────────────────────
# Infra do teste — fixtures e transporte falso (sem rede, CA-123)
# ─────────────────────────────────────────────────────────────────────────────


class TransporteGravado:
    """Transporte falso: devolve as páginas gravadas e registra o que recebeu.

    Copiado de `tests/unit/test_common_http.py` em vez de importado — a convenção de F-001 §2 é
    que teste não importa de outro arquivo de teste.
    """

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


def _resposta(conteudo: bytes, *, url: str, status: int = 200) -> RespostaBruta:
    return RespostaBruta(
        url=url,
        status=status,
        conteudo=conteudo,
        cabecalhos={"Content-Type": "text/html"},
        obtida_em=datetime(2026, 10, 10, 21, 0, tzinfo=UTC),
    )


@pytest.fixture(scope="session")
def dir_feriados(dir_fixtures: Path) -> Path:
    """`tests/fixtures/anbima-feriados/` — páginas reais da ANBIMA."""
    return dir_fixtures / "anbima-feriados"


@pytest.fixture(scope="session")
def paginas(dir_feriados: Path) -> dict[int, bytes]:
    """Bytes crus das páginas de ano gravadas."""
    return {
        ano: (dir_feriados / f"{ano}__{DATA_COLETA_FIXTURE}.html").read_bytes()
        for ano in ANOS_FIXTURE
    }


@pytest.fixture(scope="session")
def feriados_fixture(paginas: dict[int, bytes]) -> tuple[Feriado, ...]:
    """Todos os feriados dos anos gravados, já parseados."""
    return tuple(
        f
        for ano, corpo in paginas.items()
        for f in parse_feriados_do_ano(corpo, ano=ano, origem=f"fixture {ano}")
    )


@pytest.fixture(scope="session")
def cal_2006(paginas: dict[int, bytes]) -> Calendario:
    """Calendário de 2006 isolado — o ano de CA-051."""
    return Calendario.de_feriados(
        parse_feriados_do_ano(paginas[2006], ano=2006, origem="fixture 2006"),
        ano_inicio=2006,
        ano_fim=2006,
    )


@pytest.fixture(scope="session")
def cal_recente(feriados_fixture: tuple[Feriado, ...]) -> Calendario:
    """Calendário de 2024..2026 — os anos com 13 feriados e as armadilhas de trimestre."""
    return Calendario.de_feriados(feriados_fixture, ano_inicio=2024, ano_fim=2026)


# ─────────────────────────────────────────────────────────────────────────────
# CA-051 — contagem de dias úteis
# ─────────────────────────────────────────────────────────────────────────────


def test_ca051_2006_tem_exatamente_249_dias_uteis(cal_2006: Calendario) -> None:
    """CA-051: 249 dias úteis em 2006 — o mesmo número de observações do CDI (SGS 12).

    Contagem exata, não `> 0`: 248 ou 250 significa feriado a mais ou a menos, que é o erro
    silencioso que estraga toda acumulação trimestral.
    """
    assert cal_2006.dias_uteis_entre(date(2006, 1, 1), date(2006, 12, 31)) == 249


def test_ca051_dias_uteis_entre_e_fechado_nas_duas_pontas(cal_2006: Calendario) -> None:
    """A semântica do intervalo é parte do contrato: `[inicio, fim]`, pontas inclusive.

    2006-01-02 (segunda) e 2006-01-06 (sexta) são dias úteis: a semana inteira conta 5, não 3
    nem 4. Sem este teste, F-014 herdaria um off-by-one no forward-fill de 5 DU.
    """
    assert cal_2006.dias_uteis_entre(date(2006, 1, 2), date(2006, 1, 6)) == 5
    assert cal_2006.dias_uteis_entre(date(2006, 1, 2), date(2006, 1, 2)) == 1
    assert cal_2006.dias_uteis(date(2006, 1, 2), date(2006, 1, 4)) == (
        date(2006, 1, 2),
        date(2006, 1, 3),
        date(2006, 1, 4),
    )


def test_ca051_carnaval_e_corpus_christi_de_2006_nao_sao_dias_uteis(cal_2006: Calendario) -> None:
    """Os móveis da fonte: Carnaval (27 e 28/02), Paixão (14/04) e Corpus Christi (15/06).

    São os feriados que nenhuma regra de "dia fixo" pega — e o motivo de o calendário vir da
    fonte em vez de ser construído.
    """
    moveis = {
        date(2006, 2, 27): "Carnaval",
        date(2006, 2, 28): "Carnaval",
        date(2006, 4, 14): "Paix",
        date(2006, 6, 15): "Corpus Christi",
    }
    for quando, pedaco in moveis.items():
        assert not cal_2006.e_dia_util(quando), quando
        nome = cal_2006.nome_do_feriado(quando)
        assert nome is not None and pedaco in nome


def test_ca051_2006_03_31_e_sexta_e_dia_util(cal_2006: Calendario) -> None:
    """Caso-controle: 31/03/2006 é sexta e **é** dia útil — o calendário não "fecha" demais."""
    assert date(2006, 3, 31).weekday() == 4
    assert cal_2006.e_dia_util(date(2006, 3, 31))
    assert cal_2006.nome_do_feriado(date(2006, 3, 31)) is None


def test_ca051_2026_10_12_e_feriado(cal_recente: Calendario) -> None:
    """12/10/2026 é segunda-feira e feriado (Aparecida): dia de semana não implica dia útil."""
    assert date(2026, 10, 12).weekday() == 0
    assert cal_recente.e_feriado(date(2026, 10, 12))
    assert not cal_recente.e_dia_util(date(2026, 10, 12))
    assert cal_recente.proximo_dia_util(date(2026, 10, 9)) == date(2026, 10, 13)
    assert cal_recente.dia_util_anterior(date(2026, 10, 13)) == date(2026, 10, 9)


@pytest.mark.parametrize(
    ("ano", "esperado"),
    [(2006, 12), (2024, 13), (2025, 13), (2026, 13)],
)
def test_ca051_feriados_por_ano_medidos_na_fonte(
    paginas: dict[int, bytes], ano: int, esperado: int
) -> None:
    """12 feriados/ano até 2023 e 13 de 2024 em diante (Consciência Negra, Lei 14.759/23).

    Contagem exata por ano é a guarda anti-truncamento (R2) desta fonte: a página não tem
    paginação, então "veio menos" só pode ser corpo cortado ou layout trocado.
    """
    assert len(parse_feriados_do_ano(paginas[ano], ano=ano, origem="fixture")) == esperado


# ─────────────────────────────────────────────────────────────────────────────
# CA-052 — fim de trimestre em feriado ou fim de semana
# ─────────────────────────────────────────────────────────────────────────────


def test_ca052_fim_de_trimestre_em_fim_de_semana_usa_o_dia_util_anterior(
    cal_2006: Calendario,
) -> None:
    """CA-052: 30/09/2006 é sábado → 29/09; 31/12/2006 é domingo → 29/12 (sexta)."""
    assert date(2006, 9, 30).weekday() == 5
    assert cal_2006.ultimo_dia_util_do_trimestre(2006, 3) == date(2006, 9, 29)
    assert date(2006, 12, 31).weekday() == 6
    assert cal_2006.ultimo_dia_util_do_trimestre(2006, 4) == date(2006, 12, 29)


def test_ca052_fim_de_trimestre_em_feriado_pula_o_feriado_e_o_fim_de_semana(
    cal_recente: Calendario,
) -> None:
    """A armadilha composta: 31/03/2024 é domingo, 30/03 sábado e **29/03 é Paixão de Cristo**.

    O último dia útil de 1T2024 é 28/03 (quinta). Um `ajustar_para_tras` que só soubesse de fim
    de semana devolveria 29/03 — um feriado — e todo retorno de 1T2024 sairia errado.
    """
    assert date(2024, 3, 31).weekday() == 6
    assert cal_recente.e_feriado(date(2024, 3, 29))
    assert cal_recente.ultimo_dia_util_do_trimestre(2024, 1) == date(2024, 3, 28)


def test_ca052_4t2025_fecha_em_31_de_dezembro(cal_recente: Calendario) -> None:
    """31/12/2025 é quarta-feira e **não** está na lista da ANBIMA: é dia útil bancário.

    A nota 4 da própria página diz que a listagem "não inclui [...] o último dia do ano", e a
    série SGS 12 tem observação em 2025-12-31 — logo 4T2025 fecha em 31/12, não em 30/12. É a
    pergunta que o briefing de F-008 deixou aberta, respondida pela fonte.
    """
    assert date(2025, 12, 31).weekday() == 2
    assert cal_recente.e_dia_util(date(2025, 12, 31))
    assert cal_recente.ultimo_dia_util_do_trimestre(2025, 4) == date(2025, 12, 31)


def test_ca052_fim_de_trimestre_em_dia_util_nao_se_move(cal_recente: Calendario) -> None:
    """Caso-controle: 31/03/2025 é segunda e dia útil — `ajustar_para_tras` é identidade aí."""
    assert cal_recente.ultimo_dia_util_do_trimestre(2025, 1) == date(2025, 3, 31)
    assert cal_recente.ultimo_dia_util_do_trimestre(2025, 2) == date(2025, 6, 30)
    assert cal_recente.ultimo_dia_util_do_trimestre(2025, 3) == date(2025, 9, 30)


def test_ca052_todo_fim_de_trimestre_cai_em_dia_util(cal_recente: Calendario) -> None:
    """Invariante de CA-052 em 2024..2026: nenhum trimestre fecha em feriado ou fim de semana."""
    for ano in (2024, 2025, 2026):
        for tri in (1, 2, 3, 4):
            quando = cal_recente.ultimo_dia_util_do_trimestre(ano, tri)
            assert cal_recente.e_dia_util(quando), (ano, tri, quando)
            assert quando.month == {1: 3, 2: 6, 3: 9, 4: 12}[tri]


def test_ca052_trimestre_invalido_levanta(cal_recente: Calendario) -> None:
    """`tri` fora de 1..4 é erro de programação, não um trimestre "mais próximo"."""
    for tri in (0, 5, -1):
        with pytest.raises(ValueError, match="trimestre"):
            cal_recente.ultimo_dia_util_do_trimestre(2025, tri)


def test_ultimo_e_primeiro_dia_util_do_mes(cal_recente: Calendario) -> None:
    """A API nomeada em SPEC RF-018 (`ultimo_dia_util(ano, mes)`), com os dois casos de borda."""
    assert cal_recente.ultimo_dia_util(2026, 10) == date(2026, 10, 30)  # 31/10 é sábado
    assert cal_recente.ultimo_dia_util(2026, 2) == date(2026, 2, 27)  # 28/02 é sábado
    assert cal_recente.primeiro_dia_util(2026, 1) == date(2026, 1, 2)  # 01/01 é feriado
    with pytest.raises(ValueError, match="mês"):
        cal_recente.ultimo_dia_util(2026, 13)


# ─────────────────────────────────────────────────────────────────────────────
# Caminho de erro da fonte (obrigatório por extrator — CA-124)
# ─────────────────────────────────────────────────────────────────────────────


def test_pagina_404_da_anbima_nao_vira_calendario_vazio(dir_feriados: Path) -> None:
    """A ANBIMA responde o ano inexistente (2000) com HTML de erro, não com tabela vazia.

    O corpo passa pelo teste de magic bytes (é HTML de verdade), então a guarda que vale é a
    ausência de `<table class="interna">` — sem ela, 2000 entraria no calendário como um ano
    inteiro sem feriado nenhum, o pior resultado possível.
    """
    corpo = (dir_feriados / "2000__erro_404.html").read_bytes()
    with pytest.raises(CalendarioInconsistente, match="table"):
        parse_feriados_do_ano(corpo, ano=2001, origem="fixture 404")


def test_planilha_biff_e_recusada_pelos_magic_bytes(dir_feriados: Path) -> None:
    """`feriados_nacionais.xls` é XLS/BIFF real (`D0 CF 11 E0`) — o parser recusa antes de tentar.

    É a pegadinha que define o desenho de F-008: a planilha da SPEC não é XLSX disfarçado como a
    do S3 (F-002), é OLE2 legado, e `xlrd` está dispensado do projeto (`DECISIONS_LOG §2`).
    A fixture são os **512 primeiros bytes reais** do arquivo baixado em 2026-10-10.
    """
    cabecalho = (dir_feriados / "feriados_nacionais__erro_biff_cabecalho.bin").read_bytes()
    assert cabecalho.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    with pytest.raises(FormatoInesperado, match="xls_biff"):
        parse_feriados_do_ano(cabecalho, ano=2006, origem="fixture biff")


def test_corpo_vazio_com_http_200_levanta(dir_feriados: Path) -> None:
    """R1: HTTP 200 com corpo vazio é o modo de falha dominante das fontes do projeto."""
    with pytest.raises(FormatoInesperado):
        parse_feriados_do_ano(b"", ano=2006, origem="corpo vazio")


def test_pagina_de_outro_ano_levanta(paginas: dict[int, bytes]) -> None:
    """Página de 2006 pedida como 2025: a conferência de ano impede o calendário cruzado.

    Sem isso, um redirect da ANBIMA (ou um `--anos` errado) encheria 2025 com os feriados de 2006
    e todo trimestre de 2025 sairia deslocado.
    """
    with pytest.raises(CalendarioInconsistente, match="ano errado|ano 2025"):
        parse_feriados_do_ano(paginas[2006], ano=2025, origem="fixture trocada")


def test_dia_da_semana_divergente_levanta(paginas: dict[int, bytes]) -> None:
    """A página traz o dia da semana; o parser confere contra `date.weekday()`.

    O teste muda `domingo` para `segunda-feira` na **fixture real em memória** (nunca em disco) e
    espera exceção: é o que provaria dia e mês trocados em `1/1/06`.
    """
    corpo = paginas[2006].replace(b">domingo<", b">segunda-feira<", 1)
    assert corpo != paginas[2006]
    with pytest.raises(CalendarioInconsistente, match="calendário civil"):
        parse_feriados_do_ano(corpo, ano=2006, origem="fixture adulterada")


def test_tabela_truncada_levanta(paginas: dict[int, bytes]) -> None:
    """Menos que o piso de feriados por ano = página truncada, e tem de levantar (R2)."""
    corpo = paginas[2006].decode("latin-1")
    linhas = re.findall(r"<tr align=\"left\">.*?</tr>", corpo, re.DOTALL)
    assert len(linhas) >= FERIADOS_MINIMOS_POR_ANO
    for linha in linhas[3:]:
        corpo = corpo.replace(linha, "", 1)
    with pytest.raises(CalendarioInconsistente, match="mínimo esperado"):
        parse_feriados_do_ano(corpo.encode("latin-1"), ano=2006, origem="fixture truncada")


def test_data_repetida_na_tabela_levanta(paginas: dict[int, bytes]) -> None:
    """Data duplicada é inconsistência da fonte, não feriado que vale dobrado.

    A linha do Carnaval é **duplicada inteira** (data e dia da semana coerentes entre si), para
    que a guarda exercitada seja a de duplicidade e não a de dia da semana.
    """
    corpo = paginas[2006].decode("latin-1")
    linhas = re.findall(r'<tr align="left">.*?</tr>', corpo, re.DOTALL)
    corpo = corpo.replace(linhas[1], linhas[1] + linhas[1], 1)
    with pytest.raises(CalendarioInconsistente, match="repetida"):
        parse_feriados_do_ano(corpo.encode("latin-1"), ano=2006, origem="fixture duplicada")


def test_cabecalho_trocado_levanta(paginas: dict[int, bytes]) -> None:
    """Redesenho da tabela (coluna renomeada) para o parse em vez de virar dado torto."""
    corpo = paginas[2006].replace(b"<b>Feriado</b>", b"<b>Observacao</b>", 1)
    with pytest.raises(CalendarioInconsistente, match="cabe"):
        parse_feriados_do_ano(corpo, ano=2006, origem="fixture redesenhada")


# ─────────────────────────────────────────────────────────────────────────────
# Cobertura — nunca adivinhar feriado
# ─────────────────────────────────────────────────────────────────────────────


def test_data_fora_da_cobertura_levanta_em_vez_de_supor_dia_util(cal_2006: Calendario) -> None:
    """2005 e 2007 estão fora de um calendário só de 2006: a resposta é exceção, não palpite.

    É a diferença entre "não sei" e "não tem feriado" — e é o que impede F-014 de alinhar um
    trimestre contra um calendário que não cobre o período.
    """
    for quando in (date(2005, 12, 30), date(2007, 1, 2)):
        with pytest.raises(ForaDaCoberturaDoCalendario, match="fora da cobertura"):
            cal_2006.e_dia_util(quando)


def test_a_fonte_comeca_em_2001_e_2000_nao_e_inventado() -> None:
    """A ANBIMA publica de 2001 a 2099; pedir 2000 é erro, não "ano sem feriado"."""
    assert ANO_INICIO_FONTE == 2001
    assert ANO_INICIO == 2001
    with pytest.raises(Exception, match="fora da publicação"):
        mod.config_do_ano(2000)


def test_caminhada_fora_da_cobertura_levanta(cal_2006: Calendario) -> None:
    """`proximo_dia_util` perto da borda não "sai" do calendário em silêncio."""
    with pytest.raises(ForaDaCoberturaDoCalendario):
        cal_2006.proximo_dia_util(date(2006, 12, 29), 3)
    with pytest.raises(ValueError, match="n=0"):
        cal_2006.proximo_dia_util(date(2006, 6, 1), 0)


def test_calendario_sem_feriado_em_um_ano_da_janela_levanta() -> None:
    """Construir 2006..2007 só com feriados de 2006 é cobertura incompleta, não ano vazio."""
    with pytest.raises(CalendarioInconsistente, match="cobertura incompleta"):
        Calendario.de_feriados(
            [Feriado(data=date(2006, 1, 1), nome="Confraternizacao")],
            ano_inicio=2006,
            ano_fim=2007,
        )


def test_intervalo_invertido_levanta(cal_2006: Calendario) -> None:
    """`dias_uteis(fim, inicio)` é erro de chamada, não intervalo vazio silencioso."""
    with pytest.raises(ValueError, match="invertido"):
        cal_2006.dias_uteis(date(2006, 6, 30), date(2006, 1, 2))


# ─────────────────────────────────────────────────────────────────────────────
# Contrato do DataFrame e idempotência
# ─────────────────────────────────────────────────────────────────────────────


def test_quadro_respeita_o_schema_e_a_grade_e_civil_sem_lacuna(cal_recente: Calendario) -> None:
    """A grade tem **todo** dia civil de 2024-01-01 a 2026-12-31 (1.096 linhas, 2024 bissexto)."""
    quadro = cal_recente.para_quadro()
    CalendarioDiasUteisSchema.validate(quadro, lazy=True)
    assert list(quadro.columns) == ["data", "dia_util", "feriado", "fonte"]
    assert len(quadro) == 366 + 365 + 365
    assert quadro["data"].min().date() == date(2024, 1, 1)
    assert quadro["data"].max().date() == date(2026, 12, 31)
    assert quadro["data"].is_monotonic_increasing
    assert not quadro["data"].duplicated().any()
    assert quadro["dia_util"].dtype == bool


def test_schema_recusa_feriado_marcado_como_dia_util(cal_recente: Calendario) -> None:
    """A checagem de coerência do schema não é decorativa: feriado + `dia_util=True` reprova."""
    import pandera.errors

    quadro = cal_recente.para_quadro().copy()
    alvo = quadro.index[quadro["feriado"].notna()][0]
    quadro.loc[alvo, "dia_util"] = True
    with pytest.raises(pandera.errors.SchemaErrors):
        CalendarioDiasUteisSchema.validate(quadro, lazy=True)


def test_schema_recusa_sabado_como_dia_util(cal_recente: Calendario) -> None:
    """Sábado marcado como dia útil reprova — a guarda do fim de semana vive no contrato."""
    import pandera.errors

    quadro = cal_recente.para_quadro().copy()
    alvo = quadro.index[quadro["data"].dt.weekday == 5][0]
    quadro.loc[alvo, "dia_util"] = True
    with pytest.raises(pandera.errors.SchemaErrors):
        CalendarioDiasUteisSchema.validate(quadro, lazy=True)


def test_schema_recusa_lacuna_na_grade(cal_recente: Calendario) -> None:
    """Dia civil faltando na grade reprova: a tabela é calendário, não lista de dias úteis."""
    import pandera.errors

    quadro = cal_recente.para_quadro().drop(index=10).reset_index(drop=True)
    with pytest.raises(pandera.errors.SchemaErrors):
        CalendarioDiasUteisSchema.validate(quadro, lazy=True)


def test_roundtrip_quadro_calendario_preserva_os_feriados(cal_recente: Calendario) -> None:
    """`para_quadro` → `do_quadro` devolve o mesmo calendário (é o que o parquet carrega)."""
    recarregado = Calendario.do_quadro(cal_recente.para_quadro())
    assert recarregado.feriados == dict(cal_recente.feriados)
    assert recarregado.cobertura_inicio == cal_recente.cobertura_inicio
    assert recarregado.cobertura_fim == cal_recente.cobertura_fim


def test_hash_do_conteudo_e_estavel_e_sensivel(cal_recente: Calendario) -> None:
    """Duas construções independentes dão o mesmo `sha256`; mudar um feriado muda o hash."""
    quadro = cal_recente.para_quadro()
    assert mod.hash_do_conteudo(quadro) == mod.hash_do_conteudo(cal_recente.para_quadro())
    adulterado = quadro.copy()
    alvo = adulterado.index[adulterado["feriado"].notna()][0]
    adulterado.loc[alvo, "feriado"] = pd.NA
    assert mod.hash_do_conteudo(adulterado) != mod.hash_do_conteudo(quadro)


def test_extrair_com_transporte_falso_grava_parquet_idempotente(
    paginas: dict[int, bytes], tmp_path: Path
) -> None:
    """Fluxo completo sem rede: duas execuções → parquet **byte-idêntico** (RF-048).

    O `collected_at` fica fora do parquet de propósito (vai para o manifesto de `data/raw/`), e é
    isso que torna a reprodutibilidade por hash verificável em vez de "quase igual".
    """
    anos = (2024, 2025, 2026)
    hashes = []
    for _ in range(2):
        transporte = TransporteGravado(
            *[_resposta(paginas[ano], url=mod.URL_PAGINA_ANO.format(ano=ano)) for ano in anos]
        )
        resultado = mod.extrair(anos, transporte=transporte, raiz=tmp_path, com_registro=False)
        assert resultado.caminho_processed is not None
        hashes.append(sha256_de(resultado.caminho_processed.read_bytes()))
        assert resultado.linhas == 366 + 365 + 365
        assert resultado.dias_uteis == 253 + 252 + 249
        assert resultado.feriados == 13 * 3
    assert hashes[0] == hashes[1]


def test_extrair_arquiva_o_bruto_com_data_ref_do_conteudo(
    paginas: dict[int, bytes], tmp_path: Path
) -> None:
    """`data_ref` do bruto = última data do conteúdo (Natal), não "hoje" — convenção da Onda 1.

    Rodar de novo no dia seguinte cai no mesmo nome e `arquivar_bruto` fica idempotente; se a
    ANBIMA mudar o conteúdo do mesmo ano, bate em `ConteudoDivergente` em vez de sobrescrever.
    """
    transporte = TransporteGravado(
        _resposta(paginas[2026], url=mod.URL_PAGINA_ANO.format(ano=2026))
    )
    resultado = mod.extrair_ano(2026, transporte=transporte, raiz=tmp_path)
    assert resultado.caminho_raw is not None
    assert resultado.caminho_raw.name == "2026__2026-12-25.html"
    assert resultado.caminho_raw.with_suffix(".html.meta.json").is_file()
    assert not resultado.raw_idempotente

    transporte2 = TransporteGravado(
        _resposta(paginas[2026], url=mod.URL_PAGINA_ANO.format(ano=2026))
    )
    de_novo = mod.extrair_ano(2026, transporte=transporte2, raiz=tmp_path)
    assert de_novo.raw_idempotente
    assert de_novo.sha256_raw == resultado.sha256_raw


def test_offline_reprocessa_o_bruto_sem_rede(paginas: dict[int, bytes], tmp_path: Path) -> None:
    """`--offline` relê `data/raw/` e dá o mesmo resultado, sem transporte nenhum."""
    transporte = TransporteGravado(
        _resposta(paginas[2026], url=mod.URL_PAGINA_ANO.format(ano=2026))
    )
    online = mod.extrair_ano(2026, transporte=transporte, raiz=tmp_path)
    offline = mod.extrair_ano_offline(2026, raiz=tmp_path)
    assert offline.feriados == online.feriados
    assert offline.sha256_raw == online.sha256_raw


def test_do_parquet_sem_arquivo_levanta_em_vez_de_calendario_vazio(tmp_path: Path) -> None:
    """Calendário é dado extraído: sem o parquet, erro ruidoso — nunca default embutido."""
    with pytest.raises(Exception, match="calendário ausente"):
        Calendario.do_parquet(raiz=tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Guardas de Validation Mode (§15) e de catálogo
# ─────────────────────────────────────────────────────────────────────────────


def test_series_id_vem_do_catalogo_e_nao_do_conteudo() -> None:
    """A convenção da Onda 1: `series_id` do catálogo. Divergência quebra na importação (CA-033)."""
    entrada = {e.series_id: e for e in load_catalog()}[SERIES_ID]
    assert entrada.fonte_url == URL_XLS_REGISTRO
    assert entrada.item_email == "A4"
    mod._conferir_catalogo()  # noqa: SLF001 — é o portão do módulo, testado de propósito


def test_resumo_e_somente_ascii(paginas: dict[int, bytes], tmp_path: Path) -> None:
    """O `stdout` do Windows é cp1252: `print` com `→` ou acento levanta depois de gravar tudo.

    Mesma raiz do Anti-SPEC §10.4.26, do outro lado do pipe (ver F-002 §4.3).
    """
    transporte = TransporteGravado(
        _resposta(paginas[2026], url=mod.URL_PAGINA_ANO.format(ano=2026))
    )
    ano = mod.extrair_ano(2026, transporte=transporte, raiz=tmp_path)
    assert ano.resumo().isascii(), ano.resumo()

    transporte2 = TransporteGravado(
        *[_resposta(paginas[a], url=mod.URL_PAGINA_ANO.format(ano=a)) for a in (2024, 2025, 2026)]
    )
    total = mod.extrair(
        (2024, 2025, 2026), transporte=transporte2, raiz=tmp_path, com_registro=False
    )
    assert total.resumo().isascii(), total.resumo()


def test_cobertura_do_projeto_cobre_a_janela_de_macro_quarterly() -> None:
    """A janela canônica é 2006Q1→2026Q3; o calendário tem de cobri-la com folga de 1 trimestre."""
    from packages.shared.schemas import N_TRIMESTRES_JANELA

    assert N_TRIMESTRES_JANELA == 83
    assert ANO_INICIO <= 2005  # 4T2005 é o denominador do retorno de 1T2006
    assert ANO_FIM >= 2027


def test_feriado_em_fim_de_semana_nao_muda_a_contagem(cal_2006: Calendario) -> None:
    """01/01/2006 é domingo: o feriado existe, mas não "consome" dia útil nenhum.

    Erro clássico de calendário caseiro: subtrair 12 feriados de 251 dias de semana. Em 2006, 1
    dos 12 cai no fim de semana, e a contagem certa é 249, não 239.
    """
    assert cal_2006.e_feriado(date(2006, 1, 1))
    em_fim_de_semana = sum(1 for d in cal_2006.feriados if d.weekday() >= 5)
    assert em_fim_de_semana == 1
    assert len(cal_2006.feriados) == 12
    assert cal_2006.dias_uteis_entre(date(2006, 1, 1), date(2006, 12, 31)) == 249


# ─────────────────────────────────────────────────────────────────────────────
# Contrato contra a fonte viva — só local (`-m network`), nunca no CI
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_network_fixture_de_2006_continua_igual_a_fonte(paginas: dict[int, bytes]) -> None:
    """A fixture é um retrato: se a ANBIMA mudar a página, este teste avisa (e só este)."""
    from apps.pipeline.common import ClienteHTTP

    resposta = ClienteHTTP(mod.config_do_ano(2006)).get()
    vivos = parse_feriados_do_ano(resposta.conteudo, ano=2006, origem=resposta.url)
    gravados = parse_feriados_do_ano(paginas[2006], ano=2006, origem="fixture")
    assert vivos == gravados


@pytest.mark.network
def test_network_planilha_da_spec_continua_sendo_biff() -> None:
    """A decisão de usar a rota HTML depende de o `.xls` ser BIFF. Se virar XLSX, reabrir."""
    from apps.pipeline.common import ClienteHTTP, FormatoDetectado, detectar_formato

    resposta = ClienteHTTP(mod.config_do_registro()).get()
    assert resposta.status == 200
    assert detectar_formato(resposta.conteudo) is FormatoDetectado.XLS_BIFF
