"""F-016 — testes da curva: interpolação de vértice fixo, inclinação e breakeven. **Classe C.**

Três blocos, nesta ordem de força:

1. **Casos sintéticos nomeados** do núcleo `interpolar` — os únicos valores inventados desta
   feature vivem aqui, e cada um tem o nome do que prova (interpolação exata conhecida, vértice
   fora do suporte, um único título, prazo coincidente com o título). Nenhum deles reimplementa a
   fórmula do módulo: o resultado esperado está escrito como **número literal**, conferível à mão.
2. **Invariantes sobre o dado real** — as duas afirmações que a revisão numérica independente
   precisa: todo vértice interpolado fica **entre** as duas taxas usadas, e quando o prazo
   coincide com um título o vértice **é** a taxa dele. Rodam sobre o recorte versionado de
   `tests/fixtures/processed/` (obrigatório, nunca pula) e **também** sobre `data/processed/`
   quando existe — o padrão `Acervo` de `tests/unit/test_contract_sgs_sidra.py`.
3. **Canários externos** — o breakeven por razão é conferido contra a **Inflação Implícita
   publicada pela ANBIMA** na Curva Zero de 09/10/2026 (`tests/fixtures/anbima-ettj/`), que é a
   única fonte independente desta conta no repositório.

`LDC_IGNORAR_DATA=1` desliga o acervo de `data/processed/` (simula a árvore limpa do CI).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

import pandas as pd
import pytest

from apps.pipeline.canonical import curva as C
from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import Camada, caminho_camada
from apps.pipeline.extract.calendario_anbima import Calendario
from apps.pipeline.extract.tesouro_direto import NOME_PROCESSADO as NOME_PAINEL

RAIZ_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PAINEL_FIXTURE = RAIZ_FIXTURES / "processed" / NOME_PAINEL
CZ_FIXTURE = RAIZ_FIXTURES / "anbima-ettj" / "cz__2026-10-09.csv"

COMO_GERAR = "rode `uv run python -m apps.pipeline.extract.tesouro_direto --offline`"

#: O que `construir_series` devolve: `(séries em processed_series, quadros de diagnóstico)`.
Construido = tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (mesma semântica de `test_contract_sgs_sidra.py`)."""
    return os.environ.get("LDC_IGNORAR_DATA", "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


@dataclass(frozen=True)
class Acervo:
    """Um painel do Tesouro em disco, com o piso de linhas que cabe no seu recorte."""

    rotulo: str
    caminho: Path
    minimo_datas: int
    #: `True` = ausência é **falha** (está no git); `False` = skip com motivo.
    obrigatorio: bool


def _acervos() -> tuple[Acervo, ...]:
    acervos = [Acervo("fixtures", PAINEL_FIXTURE, minimo_datas=8, obrigatorio=True)]
    disco = caminho_camada(Camada.PROCESSED) / NOME_PAINEL
    if not ignorar_data_real():
        acervos.append(Acervo("data/processed", disco, minimo_datas=5000, obrigatorio=False))
    return tuple(acervos)


ACERVOS = _acervos()
IDS = [a.rotulo for a in ACERVOS]


@cache
def _painel(acervo: Acervo) -> pd.DataFrame:
    if not acervo.caminho.is_file():
        if acervo.obrigatorio:
            pytest.fail(
                f"{acervo.rotulo}: falta {acervo.caminho} — este acervo está no git e a trava "
                f"da curva não pode pular. Regenere com o script de "
                f"tests/fixtures/processed/README.md."
            )
        pytest.skip(f"{acervo.rotulo}: painel do Tesouro ausente — {COMO_GERAR}")
    return C.carregar_painel(caminho=acervo.caminho)


@cache
def _construido(acervo: Acervo, metrica: C.MetricaPrazo) -> Construido:
    """`construir_series` memoizado por acervo e métrica.

    O painel completo tem 886.300 linhas e a construção leva ~12 s: sem cache, a suíte rodaria a
    mesma conta 20 vezes. O cache é só de leitura — nenhum teste muda os quadros devolvidos.
    """
    cal = Calendario.do_parquet() if metrica is C.MetricaPrazo.DIAS_UTEIS else None
    return C.construir_series(_painel(acervo), metrica=metrica, cal=cal)


@cache
def _cobertura(acervo: Acervo) -> dict[str, object]:
    """`cobertura_por_vertice` memoizado — recalcula os 6 vértices, não é para rodar 2x."""
    return C.cobertura_por_vertice(_painel(acervo))


@pytest.fixture(params=ACERVOS, ids=IDS)
def acervo(request: pytest.FixtureRequest) -> Acervo:
    """Um acervo por vez — a fixture versionada sempre, `data/processed/` por acréscimo."""
    return request.param


@pytest.fixture
def painel(acervo: Acervo) -> pd.DataFrame:
    """O painel do acervo em teste, já validado por `ProcessedSeriesSchema`."""
    return _painel(acervo)


@pytest.fixture
def construido(acervo: Acervo) -> Construido:
    """`(séries, diagnóstico)` do acervo em teste, em dias corridos (o padrão)."""
    return _construido(acervo, C.MetricaPrazo.DIAS_CORRIDOS)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Núcleo: casos sintéticos nomeados (CA-023, CA-024)
# ─────────────────────────────────────────────────────────────────────────────


def _pontos(*pares: tuple[float, float]) -> list[C.Ponto]:
    """Pontos sintéticos `(prazo, taxa)` — **dado inventado, só aqui** (Anti-SPEC §10.1.2)."""
    return [C.Ponto(prazo=p, taxa=t, titulo=f"SINTETICO_{int(p)}") for p, t in pares]


def test_dois_titulos_em_volta_do_vertice_dao_a_interpolacao_exata_conhecida() -> None:
    """300 d a 10,00% e 400 d a 12,00%, alvo 350 d → **11,00%** (ponto médio, conta à mão)."""
    resultado = C.interpolar(_pontos((300.0, 10.0), (400.0, 12.0)), 350.0)

    assert resultado.valor == pytest.approx(11.0, abs=1e-12)
    assert resultado.peso == pytest.approx(0.5, abs=1e-12)
    assert resultado.motivo is None
    assert resultado.vertice_extrapolado is False
    assert resultado.ponto_curto is not None
    assert resultado.ponto_longo is not None
    assert (resultado.ponto_curto.prazo, resultado.ponto_longo.prazo) == (300.0, 400.0)


def test_interpolacao_assimetrica_bate_com_a_conta_manual() -> None:
    """1.460 d a 15,79% e 2.190 d a 15,78%, alvo 1.826,25 d → 15,784983% (canário de 02/01/2006).

    É a conta do vértice `CURVA_NOMINAL_5A` de 02/01/2006 com os dois NTN-F que o CSV bruto traz
    (01/01/2010 = 15,79 e 01/01/2012 = 15,78): peso = 366,25/730 = 0,5017123.
    """
    resultado = C.interpolar(_pontos((1460.0, 15.79), (2190.0, 15.78)), 5 * C.DIAS_CORRIDOS_POR_ANO)

    assert resultado.valor == pytest.approx(15.784982876712329, abs=1e-12)
    assert resultado.peso == pytest.approx(366.25 / 730.0, abs=1e-12)


def test_vertice_acima_do_vencimento_mais_longo_nao_extrapola() -> None:
    """Alvo de 10 anos com títulos de 1 e 3 anos → `None` + motivo, nunca reta esticada."""
    resultado = C.interpolar(_pontos((365.0, 10.0), (1095.0, 12.0)), 3652.5)

    assert resultado.valor is None
    assert resultado.motivo is C.Motivo.SEM_SUPORTE_LONGO
    assert resultado.vertice_extrapolado is True


def test_vertice_abaixo_do_vencimento_mais_curto_nao_extrapola() -> None:
    """Alvo de 1 ano com o título mais curto em 2 anos → `None` + motivo (é o caso real da NTN-B).

    É exatamente o que tira 40% das linhas de `CURVA_REAL_1A`: a grade de vencimentos da NTN-B
    (15/05 e 15/08 de anos alternados) deixa longos períodos sem título vencendo em menos de
    1 ano. A alternativa seria esticar a curva para dentro — extrapolação, proibida.
    """
    resultado = C.interpolar(_pontos((730.0, 6.0), (1826.0, 6.5)), 365.25)

    assert resultado.valor is None
    assert resultado.motivo is C.Motivo.SEM_SUPORTE_CURTO
    assert resultado.vertice_extrapolado is True


def test_um_unico_titulo_nao_interpola() -> None:
    """Um ponto só, em prazo diferente do alvo → `None`: não há o que interpolar."""
    resultado = C.interpolar(_pontos((900.0, 11.0)), 365.25)

    assert resultado.valor is None
    assert resultado.motivo is C.Motivo.SEM_SUPORTE_CURTO
    assert resultado.n_pontos == 1


def test_prazo_exatamente_igual_ao_titulo_devolve_a_taxa_do_titulo() -> None:
    """Alvo coincidindo com um vencimento → a taxa **dele**, sem aritmética (`exato=True`)."""
    resultado = C.interpolar(_pontos((252.0, 13.37), (504.0, 12.0)), 252.0)

    assert resultado.valor == 13.37
    assert resultado.exato is True
    assert resultado.peso == 0.0
    assert resultado.ponto_curto == resultado.ponto_longo


def test_um_unico_titulo_no_prazo_exato_devolve_a_taxa_dele() -> None:
    """Caso de borda do anterior: um ponto só, mas no prazo-alvo → vale, e é exato."""
    resultado = C.interpolar(_pontos((1260.0, 9.9)), 1260.0)

    assert resultado.valor == 9.9
    assert resultado.exato is True


def test_sem_nenhum_titulo_vivo_registra_o_motivo() -> None:
    """Data sem título da família → `SEM_TITULO`, não `0` e não omissão da linha."""
    resultado = C.interpolar([], 365.25)

    assert resultado.valor is None
    assert resultado.motivo is C.Motivo.SEM_TITULO
    assert resultado.n_pontos == 0


def test_prazos_repetidos_na_secao_transversal_levantam() -> None:
    """Dois pontos no mesmo prazo é erro de quem montou a seção, não ambiguidade a resolver aqui."""
    with pytest.raises(SerieInconsistente, match="prazos repetidos"):
        C.interpolar(_pontos((365.0, 10.0), (365.0, 11.0)), 365.25)


def test_prazo_alvo_nao_positivo_levanta() -> None:
    """Vértice de 0 ou negativo não existe — falha ruidosa em vez de número silencioso."""
    with pytest.raises(C.CurvaInconsistente, match="prazo-alvo inválido"):
        C.interpolar(_pontos((365.0, 10.0)), 0.0)


@pytest.mark.parametrize("alvo", [301.0, 350.0, 399.0, 300.5, 399.5])
def test_valor_interpolado_fica_sempre_entre_as_duas_taxas(alvo: float) -> None:
    """Invariante do método: o vértice nunca sai do intervalo das duas taxas usadas."""
    resultado = C.interpolar(_pontos((300.0, 10.0), (400.0, 12.0)), alvo)

    assert resultado.valor is not None
    assert 10.0 <= resultado.valor <= 12.0
    assert resultado.peso is not None
    assert 0.0 <= resultado.peso <= 1.0


def test_interpolacao_com_taxa_negativa_nao_e_tratada_como_ausencia() -> None:
    """Juro real negativo (2020-2021) é valor real: interpola e sai negativo (Anti-SPEC §10.1.4)."""
    resultado = C.interpolar(_pontos((300.0, -1.0), (400.0, 1.0)), 350.0)

    assert resultado.valor == pytest.approx(0.0, abs=1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Inclinação e breakeven (CA-026, Anti-SPEC §10.2.13)
# ─────────────────────────────────────────────────────────────────────────────


def test_inclinacao_e_subtracao_em_pp() -> None:
    """`INCLINACAO = longo − curto`, em `pp` — a unidade que o catálogo declara."""
    assert C.inclinacao(12.5, 10.25) == pytest.approx(2.25, abs=1e-12)


@pytest.mark.parametrize(("longo", "curto"), [(None, 10.0), (12.0, None), (None, None)])
def test_inclinacao_com_ponta_ausente_e_nula_nunca_a_ponta_que_existe(
    longo: float | None, curto: float | None
) -> None:
    """Meia inclinação não existe: sem as duas pontas o valor é `None` (CA-024)."""
    assert C.inclinacao(longo, curto) is None


def test_breakeven_e_por_razao_e_a_subtracao_falharia_o_teste() -> None:
    """`(1+12,5792%)/(1+6,2834%) − 1 = 5,9236%`; por subtração daria 6,2958% — 37 bps de erro.

    Os dois números de entrada são os vértices de 252 d.u. da Curva Zero ANBIMA de 09/10/2026.
    """
    valor = C.breakeven(12.5792, 6.2834)

    assert valor == pytest.approx(5.923597, abs=1e-6)
    assert valor != pytest.approx(12.5792 - 6.2834, abs=1e-3)


def test_breakeven_bate_com_a_inflacao_implicita_publicada_pela_anbima() -> None:
    """Canário **externo**: a razão reproduz a coluna "Inflação Implícita" da ANBIMA.

    Em todos os vértices em que a Curva Zero de 09/10/2026 publica IPCA **e** PREF, a nossa
    fórmula cai a menos de **0,1 bp** do número que a ANBIMA calculou — é o que prova que a
    convenção de razão (Anti-SPEC §10.2.13) é a mesma do mercado, sem reimplementar nada nosso.
    """
    vertices = _vertices_da_curva_zero(CZ_FIXTURE)

    assert len(vertices) >= 19
    for du, ipca, pref, implicita in vertices:
        calculado = C.breakeven(pref, ipca)
        assert calculado is not None
        assert calculado == pytest.approx(implicita, abs=1e-3), f"vértice {du} d.u."


def _vertices_da_curva_zero(caminho: Path) -> list[tuple[int, float, float, float]]:
    """`(vértice d.u., ETTJ IPCA, ETTJ PREF, Inflação Implícita)` do `csv` do `CZ-down.asp`.

    Lê só as linhas em que as três colunas existem (a ETTJ PREF para no vértice 2.520). Encoding
    **explícito** `latin-1` e separador de milhar `.` removido do vértice — as duas pegadinhas que
    `research/fontes-de-dados.md §A5.1` registra.
    """
    linhas = caminho.read_text(encoding="latin-1").splitlines()
    saida: list[tuple[int, float, float, float]] = []
    for linha in linhas:
        campos = [c.strip() for c in linha.split(";")]
        bruto = campos[0].replace(".", "")
        if not bruto.isdigit() or len(campos) < 4 or not all(campos[1:4]):
            continue
        numeros = [float(c.replace(",", ".")) for c in campos[1:4]]
        saida.append((int(bruto), numeros[0], numeros[1], numeros[2]))
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sobre o painel real (CA-023, CA-024, CA-025)
# ─────────────────────────────────────────────────────────────────────────────


def test_as_7_series_tem_uma_linha_por_data_base_do_painel(
    painel: pd.DataFrame, construido: Construido
) -> None:
    """Toda data base entra em todas as 7 séries — inclusive as sem suporte, com `value` nulo."""
    datas = painel["date"].nunique()
    series, _ = construido

    assert set(series) == set(C.SERIES_DE_F016)
    for series_id, quadro in series.items():
        assert len(quadro) == datas, series_id
        assert quadro["date"].is_unique
        assert quadro["date"].is_monotonic_increasing


def test_todo_vertice_interpolado_do_dado_real_fica_entre_as_duas_taxas(
    construido: Construido,
) -> None:
    """**A prova numérica de CA-023 no dado real**: zero vértice fora do intervalo dos dois títulos.

    É a afirmação que separa interpolação de extrapolação linha a linha, sem reimplementar a
    fórmula: compara o resultado com as duas taxas que o próprio diagnóstico registra.
    """
    _, diagnostico = construido

    for series_id in C.VERTICES:
        quadro = diagnostico[series_id]
        com_valor = quadro[quadro["value"].notna()]
        assert not com_valor.empty, series_id
        piso = com_valor[["taxa_curta", "taxa_longa"]].min(axis=1)
        teto = com_valor[["taxa_curta", "taxa_longa"]].max(axis=1)
        fora = com_valor[(com_valor["value"] < piso - 1e-9) | (com_valor["value"] > teto + 1e-9)]
        assert fora.empty, f"{series_id}: {len(fora)} vértices fora do intervalo interpolado"
        assert com_valor["peso"].between(0.0, 1.0).all(), series_id


def test_vertice_sem_suporte_e_nulo_com_motivo_e_nunca_tem_valor(construido: Construido) -> None:
    """CA-024: `vertice_extrapolado` ⇔ `value` nulo ⇔ `motivo` preenchido. As três andam juntas."""
    _, diagnostico = construido

    for series_id, quadro in diagnostico.items():
        extrapolado = quadro["vertice_extrapolado"]
        assert (quadro.loc[extrapolado, "value"].isna()).all(), series_id
        assert (quadro.loc[extrapolado, "motivo"].notna()).all(), series_id
        assert (quadro.loc[~extrapolado, "value"].notna()).all(), series_id
        assert (quadro.loc[~extrapolado, "motivo"].isna()).all(), series_id


def test_vertice_nominal_de_10_anos_em_2006_e_nulo(painel: pd.DataFrame) -> None:
    """CA-024, com o número de ADR-004/L5: em 2006 a NTN-F mais longa vence em 01/01/2014.

    O vértice nominal de 10 anos, portanto, **não existe** em 2006 — e o motivo registrado é
    "sem vencimento acima do vértice", não um número extrapolado. O vértice de **5** anos, ao
    contrário, existe: as NTN-F de 2010 e 2012 o cercam (medido, 100% dos dias úteis de 2006).
    """
    pontos = C.pontos_do_painel(painel)
    datas_2006 = [d for d in sorted(painel["date"].unique()) if d.year == 2006]
    if not datas_2006:
        pytest.skip("acervo sem data base de 2006")

    dez_anos = C.Vertice("CURVA_NOMINAL_10A", C.Familia.NOMINAL, 10)
    cinco_anos = C.VERTICES["CURVA_NOMINAL_5A"]

    longo = C.serie_do_vertice(pontos, dez_anos, datas=datas_2006)
    medio = C.serie_do_vertice(pontos, cinco_anos, datas=datas_2006)

    assert longo["value"].isna().all()
    assert set(longo["motivo"]) == {C.Motivo.SEM_SUPORTE_LONGO.value}
    assert longo["vertice_extrapolado"].all()
    assert medio["value"].notna().all()


def test_series_derivadas_sao_exatamente_a_conta_dos_vertices(construido: Construido) -> None:
    """`INCLINACAO` e `BREAKEVEN` saem dos vértices gravados — conferível célula a célula."""
    series, _ = construido
    juntos = (
        series["CURVA_REAL_5A"][["date", "value"]]
        .rename(columns={"value": "real5"})
        .merge(
            series["CURVA_REAL_1A"][["date", "value"]].rename(columns={"value": "real1"}),
            on="date",
        )
        .merge(
            series["CURVA_NOMINAL_5A"][["date", "value"]].rename(columns={"value": "nom5"}),
            on="date",
        )
        .merge(
            series[C.SERIE_INCLINACAO_REAL][["date", "value"]].rename(columns={"value": "incl"}),
            on="date",
        )
        .merge(
            series[C.SERIE_BREAKEVEN][["date", "value"]].rename(columns={"value": "be"}), on="date"
        )
    )
    esperado_incl = juntos["real5"] - juntos["real1"]
    esperado_be = ((1 + juntos["nom5"] / 100) / (1 + juntos["real5"] / 100) - 1) * 100

    pd.testing.assert_series_equal(
        juntos["incl"], esperado_incl, check_names=False, atol=1e-12, rtol=0
    )
    pd.testing.assert_series_equal(juntos["be"], esperado_be, check_names=False, atol=1e-12, rtol=0)


def test_breakeven_nao_e_a_subtracao_no_dado_real(construido: Construido) -> None:
    """Se alguém trocar razão por subtração, este teste cai: a diferença é de dezenas de bps."""
    series, _ = construido
    juntos = (
        series[C.SERIE_BREAKEVEN][["date", "value"]]
        .rename(columns={"value": "be"})
        .merge(
            series["CURVA_NOMINAL_5A"][["date", "value"]].rename(columns={"value": "nom5"}),
            on="date",
        )
        .merge(
            series["CURVA_REAL_5A"][["date", "value"]].rename(columns={"value": "real5"}),
            on="date",
        )
        .dropna()
    )
    diferenca = (juntos["nom5"] - juntos["real5"]) - juntos["be"]

    assert (diferenca.abs() > 0.05).all(), "razão e subtração ficaram indistinguíveis"


def test_pontos_do_painel_usa_so_a_taxa_de_venda_das_familias_da_curva(
    painel: pd.DataFrame,
) -> None:
    """Só `TAXA_VENDA` e só `LTN/NTNF/NTNB/NTNBP` entram na curva (nada de LFT, PU ou taxa 0,00)."""
    pontos = C.pontos_do_painel(painel)

    assert set(pontos["familia"]) <= {f.value for f in C.Familia}
    assert (pontos["prazo"] > 0).all()
    assert not pontos["titulo"].str.startswith(("LFT", "NTNC", "EDUCA", "RENDA")).any()
    chave = pontos[["date", "familia", "prazo"]]
    assert not chave.duplicated().any(), "prazo repetido sobreviveu à agregação por vencimento"


def test_taxa_de_compra_zerada_nao_entra_pela_taxa_de_venda(painel: pd.DataFrame) -> None:
    """Justificativa medida da métrica escolhida: `TAXA_VENDA` nunca é `0` nas 4 siglas da curva.

    `TAXA_COMPRA` traz `0,00` quando o título não está à venda (14 observações de NTN-F no
    arquivo completo) — e `0` ali seria ausência disfarçada de taxa, propagando para o vértice.
    """
    pontos = C.pontos_do_painel(painel)

    assert (pontos["taxa"] != 0).all()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Cobertura (CA-025) — medida, não presumida
# ─────────────────────────────────────────────────────────────────────────────


def test_cobertura_da_inclinacao_nominal_passa_de_95_por_cento(construido: Construido) -> None:
    """CA-025 para a curva **nominal**: >= 95% das datas base de 2006 em diante (medido: 97,57%)."""
    series, _ = construido
    medido = C.cobertura(series[C.SERIE_INCLINACAO_NOMINAL])

    if medido["n_datas_base"] < 100:
        pytest.skip("recorte com poucas datas base de 2006 em diante")
    assert medido["pct_com_valor"] is not None
    assert medido["pct_com_valor"] >= 95.0


def test_cobertura_da_inclinacao_real_1a_e_a_medida_e_nao_atinge_os_95_de_ca025(
    construido: Construido,
) -> None:
    """**CA-025 não é satisfazível com o vértice curto de 1 ano** — e isto trava a medição.

    Medido no painel completo (5.184 datas base de 2006-01-01 a 2026-10-09):
    `INCLINACAO_REAL_5A_1A` existe em **60,53%** das datas, porque `CURVA_REAL_1A` só tem suporte
    em 60,53% delas (a grade de vencimentos da NTN-B não tem título vencendo em menos de 1 ano
    durante anos inteiros — 0% em 2018, 2021 e 2022). Com vértice curto de **3 anos** — que
    CA-023 e o escopo do `TODO.md` já nomeiam ("1, 3 e 5 anos") — a cobertura vai a **95,25%** e
    CA-025 fecha.

    Nada foi "arrumado" para fechar o CA: a SPEC não é editada por agente (`AGENTS.md §8`) e o
    número fica travado aqui. A decisão veio do orquestrador em **D-i** (2026-10-11, provisória,
    aguarda o Edu): `CURVA_REAL_3A`/`CURVA_NOMINAL_3A` e as duas inclinações 5a−3a entraram no
    catálogo, `INCLINACAO_REAL_5A_3A` é a variável principal de regime e **esta série continua
    publicada como secundária** — com a cobertura declarada, que é o que este teste garante.
    Mesmo caminho de D-e no `DECISIONS_LOG`.
    """
    series, _ = construido
    medido = C.cobertura(series[C.SERIE_INCLINACAO_REAL])

    if medido["n_datas_base"] < 5000:
        pytest.skip("cobertura de CA-025 só é mensurável sobre o painel completo")
    assert medido["pct_com_valor"] == pytest.approx(60.53, abs=0.05)
    assert medido["pct_com_valor"] < 95.0


def test_inclinacao_real_5a_3a_e_a_que_fecha_ca025(construido: Construido) -> None:
    """**É assim que CA-025 fecha (D-i):** a inclinação real 5a−3a cobre **95,25%** das datas base.

    Medido na série **gravada**, não numa tabela de diagnóstico: `INCLINACAO_REAL_5A_3A` é a
    variável principal de regime desde D-i e tem de passar o limiar de CA-025 no dado que vai para
    `raw_series`. A 5a−1a continua publicada, com 60,53%, e o teste anterior é o que impede que
    alguém a confunda com esta.
    """
    series, _ = construido
    medido = C.cobertura(series[C.SERIE_INCLINACAO_REAL_3A])

    if medido["n_datas_base"] < 5000:
        pytest.skip("cobertura de CA-025 só é mensurável sobre o painel completo")
    assert medido["pct_com_valor"] == pytest.approx(95.25, abs=0.05)
    assert medido["pct_com_valor"] >= 95.0


def test_as_4_inclinacoes_e_os_6_vertices_sao_gravados_e_so_eles(construido: Construido) -> None:
    """As 11 séries de D-i: 6 vértices (1, 3 e 5 anos × 2 famílias) + 4 inclinações + breakeven.

    O vértice de 10 anos é **medido e não gravado** (não tem entrada no catálogo): é o que
    mantém CA-024 quantificado sem violar CA-055.
    """
    series, _ = construido

    assert len(C.SERIES_DE_F016) == 11
    assert set(series) == set(C.SERIES_DE_F016)
    assert set(C.VERTICES) == {
        "CURVA_REAL_1A",
        "CURVA_REAL_3A",
        "CURVA_REAL_5A",
        "CURVA_NOMINAL_1A",
        "CURVA_NOMINAL_3A",
        "CURVA_NOMINAL_5A",
    }
    assert set(C.VERTICES_FORA_DO_CATALOGO) == {"CURVA_REAL_10A", "CURVA_NOMINAL_10A"}
    assert set(C.VERTICES) & set(C.VERTICES_FORA_DO_CATALOGO) == set()


def test_inclinacao_5a_3a_e_exatamente_a_diferenca_dos_dois_vertices_gravados(
    construido: Construido,
) -> None:
    """Célula a célula: `INCLINACAO_REAL_5A_3A == CURVA_REAL_5A − CURVA_REAL_3A`, em `pp`."""
    series, _ = construido
    juntos = (
        series["CURVA_REAL_5A"][["date", "value"]]
        .rename(columns={"value": "longo"})
        .merge(
            series["CURVA_REAL_3A"][["date", "value"]].rename(columns={"value": "curto"}),
            on="date",
        )
        .merge(
            series[C.SERIE_INCLINACAO_REAL_3A][["date", "value"]].rename(columns={"value": "incl"}),
            on="date",
        )
    )

    pd.testing.assert_series_equal(
        juntos["incl"], juntos["longo"] - juntos["curto"], check_names=False, atol=1e-12, rtol=0
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Calendário: dias úteis e agregação trimestral (CA-026)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def calendario() -> Calendario:
    """O calendário ANBIMA de `data/processed/calendario/` — skip com motivo se não extraído."""
    try:
        return Calendario.do_parquet()
    except Exception:  # noqa: BLE001 - ausência do Parquet é skip, não falha desta feature
        pytest.skip(
            "calendário ausente — rode `uv run python -m apps.pipeline.extract.calendario_anbima`"
        )


@pytest.mark.parametrize(
    ("inicio", "fim"),
    [
        (date(2006, 1, 2), date(2007, 1, 1)),
        (date(2016, 1, 4), date(2017, 1, 1)),
        (date(2026, 10, 9), date(2030, 8, 15)),
        (date(2024, 3, 27), date(2024, 4, 2)),
    ],
)
def test_contagem_acumulada_de_dias_uteis_concorda_com_o_calendario(
    calendario: Calendario, inicio: date, fim: date
) -> None:
    """A contagem vetorizada é a mesma de `Calendario.dias_uteis_entre` (intervalo semiaberto).

    O atalho de desempenho existe porque a curva precisa de ~160 mil prazos; este teste é o que
    impede que ele se descole da API pública do calendário — e foi ele que pegou o
    desalinhamento de índice da primeira rodada.
    """
    acumulado = C._contagem_de_dias_uteis(calendario)
    vetorizado = acumulado[pd.Timestamp(fim)] - acumulado[pd.Timestamp(inicio)]
    fechado = calendario.dias_uteis_entre(inicio, fim)
    esperado = fechado - (1 if calendario.e_dia_util(fim) else 0)

    assert vetorizado == esperado


def test_prazo_em_dias_uteis_fora_da_cobertura_do_calendario_e_nulo(
    calendario: Calendario,
) -> None:
    """Vencimento em 2045 com calendário até 2030 → `NaN` declarado, nunca contagem presumida.

    É o motivo de o padrão ser dias **corridos**: em dias úteis, todo par que envolve título longo
    (e o vértice de 5 anos de qualquer data base de 2026) ficaria sem prazo, e `None` por limite do
    nosso calendário é indistinguível de `None` por ausência de título.
    """
    datas = pd.Series(pd.to_datetime(["2026-10-09", "2026-10-09"]))
    vencimentos = pd.Series(pd.to_datetime(["2030-08-15", "2045-05-15"]))

    prazos = C._prazo_em_dias_uteis(datas, vencimentos, cal=calendario)

    assert prazos.iloc[0] > 0
    assert pd.isna(prazos.iloc[1])


def test_valor_trimestral_e_o_do_ultimo_dia_util_do_trimestre(calendario: Calendario) -> None:
    """CA-026 com caso-armadilha de calendário: 1T2024 fecha em **28/03** (29/03 é Sexta Santa).

    E 3T2006 fecha em **29/09** (30/09 é sábado). A agregação pega o valor **daquele** dia, nunca
    a média do trimestre e nunca o valor de outro dia.
    """
    datas = pd.to_datetime(
        ["2024-03-26", "2024-03-27", "2024-03-28", "2024-04-01", "2006-09-28", "2006-09-29"]
    )
    serie = pd.DataFrame({"date": datas, "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})

    trimestral = C.agregar_para_trimestre(serie, cal=calendario)
    por_trimestre = dict(zip(trimestral["quarter"], trimestral["value"], strict=True))

    assert calendario.ultimo_dia_util_do_trimestre(2024, 1) == date(2024, 3, 28)
    assert por_trimestre["2024Q1"] == 3.0
    assert por_trimestre["2006Q3"] == 6.0
    assert por_trimestre["2024Q2"] != 4.0 or pd.isna(por_trimestre["2024Q2"])


def test_trimestre_sem_observacao_no_ultimo_dia_util_fica_nulo(calendario: Calendario) -> None:
    """Sem observação no último dia útil, o trimestre é nulo — `ffill` é decisão de F-014."""
    serie = pd.DataFrame(
        {"date": pd.to_datetime(["2024-02-01", "2024-03-01"]), "value": [1.0, 2.0]}
    )

    trimestral = C.agregar_para_trimestre(serie, cal=calendario)

    assert pd.isna(trimestral.loc[trimestral["quarter"] == "2024Q1", "value"].iloc[0])


def test_metrica_em_dias_uteis_produz_o_mesmo_vertice_a_menos_de_poucos_bps(
    acervo: Acervo, calendario: Calendario
) -> None:
    """Sensibilidade do método: `dias_uteis` × `dias_corridos` diferem em **frações de bp**.

    Medido no painel completo: mediana de 0,14 a 0,41 bps e máximo de 4,6 bps por série — ordem
    de grandeza muito abaixo do spread de varejo do Tesouro Direto (dezenas de bps). É o que
    sustenta a escolha do padrão: a métrica de prazo não move o número, e dias corridos cobrem
    300 a 700 datas base que o calendário (2001-2030) não alcança.
    """
    del calendario  # o cache monta o seu; o parâmetro é o gate de skip quando falta o Parquet
    corridos, _ = _construido(acervo, C.MetricaPrazo.DIAS_CORRIDOS)
    uteis, _ = _construido(acervo, C.MetricaPrazo.DIAS_UTEIS)

    for series_id in C.VERTICES:
        juntos = (
            corridos[series_id][["date", "value"]]
            .rename(columns={"value": "act"})
            .merge(uteis[series_id][["date", "value"]].rename(columns={"value": "du"}), on="date")
            .dropna()
        )
        if juntos.empty:
            continue
        diferenca_bps = (juntos["act"] - juntos["du"]).abs() * 100
        assert diferenca_bps.median() < 3.0, series_id
        assert diferenca_bps.max() < 25.0, series_id


# ─────────────────────────────────────────────────────────────────────────────
# 6. Gravação, idempotência e canários (CI N3 local)
# ─────────────────────────────────────────────────────────────────────────────


def test_duas_rodadas_gravam_parquet_byte_identico(tmp_path: Path) -> None:
    """Idempotência por hash: nada aqui lê o relógio (`vintage` vem do painel, D-b)."""
    destino = tmp_path / "data" / "processed" / NOME_PAINEL
    destino.parent.mkdir(parents=True)
    destino.write_bytes(PAINEL_FIXTURE.read_bytes())

    primeira = C.construir(raiz=tmp_path, caminho_painel=destino)
    segunda = C.construir(raiz=tmp_path, caminho_painel=destino)

    assert {sid: h for sid, (_, h) in primeira.series.items()} == {
        sid: h for sid, (_, h) in segunda.series.items()
    }
    assert len(primeira.series) == len(C.SERIES_DE_F016)
    assert primeira.caminho_relatorio is not None
    assert primeira.caminho_relatorio.read_bytes() == segunda.caminho_relatorio.read_bytes()  # type: ignore[union-attr]


def test_painel_ausente_bloqueia_com_fonte_indisponivel(tmp_path: Path) -> None:
    """Sem painel, `BLOQUEADO — FONTE INDISPONÍVEL` — nunca uma curva vazia gravada."""
    with pytest.raises(Exception, match="FONTE INDISPONÍVEL"):
        C.construir(raiz=tmp_path)


def test_canarios_do_relatorio_tem_a_conta_aberta(
    painel: pd.DataFrame, construido: Construido
) -> None:
    """O relatório carrega os dois títulos, os dois prazos, as duas taxas e o peso de cada canário.

    É o que permite à revisão numérica independente reproduzir o vértice numa planilha a partir
    do CSV bruto, sem ler este código.
    """
    _, diagnostico = construido
    datas = [d for d in C.DATAS_CANARIO if pd.Timestamp(d) in set(painel["date"])]
    if not datas:
        pytest.skip("acervo sem nenhuma das datas de canário")

    canarios = C.canarios_conferiveis(diagnostico, datas=datas, series=list(C.VERTICES))
    com_valor = [c for c in canarios if c["value"] is not None]

    assert com_valor
    for canario in com_valor:
        assert canario["titulo_curto"] and canario["titulo_longo"]
        assert canario["prazo_curto"] is not None
        assert canario["taxa_curta"] is not None
        assert canario["peso"] is not None


def test_canario_de_02_01_2006_do_vertice_nominal_de_5_anos(
    painel: pd.DataFrame, construido: Construido
) -> None:
    """Canário conferido à mão no CSV bruto: NTN-F 2010 = 15,79 e NTN-F 2012 = 15,78 → 15,784983.

    `grep "^Tesouro Prefixado com Juros Semestrais;01/01/2010;02/01/2006;"` no bruto devolve
    `15,73;15,79` (compra;venda). O vértice usa a **venda**.
    """
    dia = pd.Timestamp("2006-01-02")
    if dia not in set(painel["date"]):
        pytest.skip("acervo sem a data base de 02/01/2006")

    _, diagnostico = construido
    linha = diagnostico["CURVA_NOMINAL_5A"].set_index("date").loc[dia]

    assert linha["titulo_curto"] == "NTNF_20100101"
    assert linha["titulo_longo"] == "NTNF_20120101"
    assert linha["taxa_curta"] == pytest.approx(15.79)
    assert linha["taxa_longa"] == pytest.approx(15.78)
    assert linha["value"] == pytest.approx(15.784982876712329, abs=1e-9)
