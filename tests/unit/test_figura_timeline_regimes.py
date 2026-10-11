"""F-025 — testes da timeline de regimes sobre IBOV e Selic meta. **RF-035 / CA-100.**

Organização, e o motivo de cada bloco:

| Bloco | O que trava | CA |
|---|---|---|
| 1 | a paleta: 4 cores na ordem do enum, cinza **hachurado** para `INDETERMINADO` | CA-100 |
| 2 | os dados plotados: contrato de colunas, níveis, divergência `asof` × `revised` | CA-100 |
| 3 | as faixas cobrem a janela inteira, contíguas — **o "sem buraco" de CA-100** | CA-100 |
| 4 | o desenho: 2 painéis (nunca eixo duplo), 8 trimestres no eixo, legenda com `n` | CA-100 |
| 5 | o gate: rodapé e marca d'água quando `especificacao_congelada=False` | CA-090 |
| 6 | determinismo: 2 rodadas, mesmo DataFrame e mesmos bytes; dados == Parquet | CA-121 |
| 7 | **acervo real** `data/canonical/` — 83 trimestres, 22+2 trocas, hash estável | todos |

Os blocos 1-6 rodam sobre uma **fixture sintética de 8 trimestres**, nomeada como sintética
(Anti-SPEC §10.1.2), e **nunca pulam**: rodam no CI sem `data/`. O bloco 7 segue o padrão `Acervo`
de `test_canonical_alinhamento.py §E` — entra por acréscimo quando o Parquet existe em disco e é
desligado por `LDC_IGNORAR_DATA=1`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from matplotlib.colors import to_rgba

from apps.analysis.figuras import timeline_regimes as T
from apps.pipeline.canonical.regimes_v1 import Materializacao
from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.regimes import RegimeV1, StatusRegimeV1

COMO_GERAR = "rode `uv run python -m apps.analysis.figuras.timeline_regimes`"
VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

# ─────────────────────────────────────────────────────────────────────────────
# Ajudantes sintéticos — dado nomeado como sintético (Anti-SPEC §10.1.2)
# ─────────────────────────────────────────────────────────────────────────────

QUARTERS_SINTETICOS: tuple[str, ...] = (
    "2006Q1",
    "2006Q2",
    "2006Q3",
    "2006Q4",
    "2007Q1",
    "2007Q2",
    "2007Q3",
    "2007Q4",
)

#: `revised` sintética: os 4 quadrantes + 2 indeterminados. `None` = sem quadrante.
ROTULOS_REVISED: tuple[str | None, ...] = (
    RegimeV1.RECUPERACAO.value,
    RegimeV1.RECUPERACAO.value,
    RegimeV1.EXPANSAO_INFL.value,
    RegimeV1.ESTAGFLACAO.value,
    RegimeV1.DESACELERACAO.value,
    None,
    None,
    RegimeV1.RECUPERACAO.value,
)
#: `asof` sintética: discorda em **2006Q2** (outro quadrante) e **2007Q3** (classifica o que a
#: `revised` deixou indeterminado) — uma troca de `ROTULO` e uma de `STATUS`, de propósito.
ROTULOS_ASOF: tuple[str | None, ...] = (
    RegimeV1.RECUPERACAO.value,
    RegimeV1.EXPANSAO_INFL.value,
    RegimeV1.EXPANSAO_INFL.value,
    RegimeV1.ESTAGFLACAO.value,
    RegimeV1.DESACELERACAO.value,
    None,
    RegimeV1.RECUPERACAO.value,
    RegimeV1.RECUPERACAO.value,
)

FONTE_VERSAO_SINTETICA = "0" * 64


def regimes_sinteticos(
    rotulos: tuple[str | None, ...],
    *,
    asof: bool = False,
    congelada: bool = False,
) -> pd.DataFrame:
    """Uma tabela no formato de `regimes_v1`, com 8 trimestres. **Sintética, não é dado real.**"""
    status = [
        StatusRegimeV1.INDETERMINADO.value if r is None else StatusRegimeV1.CLASSIFICADO.value
        for r in rotulos
    ]
    contagem = {r: rotulos.count(r) for r in set(rotulos)}
    return pd.DataFrame(
        {
            "quarter": list(QUARTERS_SINTETICOS),
            "regime_v1": list(rotulos),
            "status_regime_v1": status,
            "n_obs_regime_v1": [contagem[r] for r in rotulos],
            "lag_adjusted": [asof] * len(rotulos),
            "especificacao_congelada": [congelada] * len(rotulos),
            "versao_especificacao": ["V1"] * len(rotulos),
            "fonte_versao": [FONTE_VERSAO_SINTETICA] * len(rotulos),
        }
    )


def niveis_sinteticos() -> pd.DataFrame:
    """IBOV subindo 5% ao trimestre e Selic caindo 25 bps — **sintético**, só para ter geometria."""
    return pd.DataFrame(
        {
            "quarter": list(QUARTERS_SINTETICOS),
            "quarter_end": pd.to_datetime(
                [
                    "2006-03-31",
                    "2006-06-30",
                    "2006-09-29",
                    "2006-12-29",
                    "2007-03-30",
                    "2007-06-29",
                    "2007-09-28",
                    "2007-12-28",
                ]
            ),
            "ibov_nivel": [40000.0 * 1.05**i for i in range(len(QUARTERS_SINTETICOS))],
            "selic_meta_pct": [16.5 - 0.25 * i for i in range(len(QUARTERS_SINTETICOS))],
        }
    )


def dados_sinteticos(*, congelada: bool = False) -> pd.DataFrame:
    """Os dados plotados das **duas** materializações sintéticas."""
    return T.dados_plotados(
        {
            Materializacao.REVISED.value: regimes_sinteticos(ROTULOS_REVISED, congelada=congelada),
            Materializacao.ASOF.value: regimes_sinteticos(
                ROTULOS_ASOF, asof=True, congelada=congelada
            ),
        },
        niveis_sinteticos(),
    )


@pytest.fixture
def dados() -> pd.DataFrame:
    """Dados plotados sintéticos com o gate **fechado** (o estado real de hoje)."""
    return dados_sinteticos()


def recorte(dados: pd.DataFrame, materializacao: str) -> pd.DataFrame:
    """O bloco de uma materialização, na ordem do eixo x."""
    return (
        dados[dados["materializacao"] == materializacao]
        .sort_values("quarter", kind="stable")
        .reset_index(drop=True)
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1 — Paleta: ordem do enum, 4 cores distintas, cinza hachurado para a ausência
# ═════════════════════════════════════════════════════════════════════════════


def test_cada_quadrante_do_enum_tem_cor_e_na_ordem_de_declaracao() -> None:
    """A cor segue a **entidade** e a ordem do enum — nunca reciclada, nunca por ranking."""
    assert list(T.COR_POR_REGIME) == [r.value for r in RegimeV1]
    assert tuple(T.COR_POR_REGIME.values()) == T.PALETA_CATEGORICA
    assert len(set(T.PALETA_CATEGORICA)) == len(RegimeV1)


def test_indeterminado_nao_usa_cor_de_quadrante() -> None:
    """Se `INDETERMINADO` reusasse um dos 4 hexes, viraria um 5º regime aos olhos de quem lê."""
    assert T.COR_INDETERMINADO not in T.PALETA_CATEGORICA
    assert T.ROTULO_INDETERMINADO not in T.COR_POR_REGIME


def test_cor_e_hachura_de_cada_linha_seguem_o_rotulo(dados: pd.DataFrame) -> None:
    """A cor plotada de cada trimestre é a do seu quadrante; a do indeterminado é o cinza."""
    bloco = recorte(dados, Materializacao.REVISED.value)
    for rotulo, cor, hachura in zip(
        bloco["rotulo_da_faixa"], bloco["cor_hex"], bloco["hachura"], strict=True
    ):
        if rotulo == T.ROTULO_INDETERMINADO:
            assert cor == T.COR_INDETERMINADO
            assert hachura == T.HACHURA_INDETERMINADO
        else:
            assert cor == T.COR_POR_REGIME[rotulo]
            assert hachura == ""


def test_so_o_indeterminado_e_hachurado(dados: pd.DataFrame) -> None:
    """Hachura é o canal de **ausência**, não decoração: nenhum quadrante a usa."""
    hachurados = set(dados.loc[dados["hachura"] != "", "rotulo_da_faixa"])
    assert hachurados == {T.ROTULO_INDETERMINADO}


def test_a_faixa_do_indeterminado_sai_hachurada_no_desenho(dados: pd.DataFrame) -> None:
    """O teste de cor na tabela não basta: o `Polygon` desenhado tem de carregar a hachura."""
    figura = T.desenhar(
        dados, materializacao=Materializacao.REVISED.value, versao="f" * 64, hashes_dos_insumos={}
    )
    hachuras = {p.get_hatch() for p in figura.axes[0].patches}
    assert T.HACHURA_INDETERMINADO in hachuras
    cinzas = [
        p
        for p in figura.axes[0].patches
        if p.get_hatch() == T.HACHURA_INDETERMINADO
        and p.get_facecolor()[:3] == to_rgba(T.COR_INDETERMINADO)[:3]
    ]
    assert cinzas, "nenhuma faixa cinza hachurada no painel do IBOV"


# ═════════════════════════════════════════════════════════════════════════════
# 2 — Dados plotados: contrato de colunas, níveis e divergência entre materializações
# ═════════════════════════════════════════════════════════════════════════════


def test_contrato_de_colunas_exato_e_na_ordem(dados: pd.DataFrame) -> None:
    """`COLUNAS_DADOS_PLOTADOS` é o contrato do Parquet — nem coluna a mais, nem fora de ordem."""
    assert tuple(dados.columns) == T.COLUNAS_DADOS_PLOTADOS


def test_colunas_de_regime_mantem_o_nome_de_regimes_v1(dados: pd.DataFrame) -> None:
    """Nada é renomeado no caminho: quem conferir contra `regimes_v1` acha a coluna pelo nome."""
    origem = regimes_sinteticos(ROTULOS_REVISED)
    for coluna in T.COLUNAS_HERDADAS_DE_REGIMES_V1:
        assert coluna in origem.columns
        assert coluna in dados.columns


def test_uma_linha_por_materializacao_e_trimestre(dados: pd.DataFrame) -> None:
    """A chave é `(materializacao, quarter)`; duplicata aqui seria faixa desenhada duas vezes."""
    assert len(dados) == 2 * len(QUARTERS_SINTETICOS)
    assert not dados.duplicated(subset=["materializacao", "quarter"]).any()


def test_niveis_entram_sem_transformacao(dados: pd.DataFrame) -> None:
    """O IBOV vai em **nível** e a Selic em %a.a. — a figura não calcula retorno nem reindexa."""
    bloco = recorte(dados, Materializacao.REVISED.value)
    esperado = niveis_sinteticos()
    pd.testing.assert_series_equal(bloco["ibov_nivel"], esperado["ibov_nivel"], check_names=False)
    pd.testing.assert_series_equal(
        bloco["selic_meta_pct"], esperado["selic_meta_pct"], check_names=False
    )


def test_troca_de_quadrante_e_troca_de_status_sao_distinguidas(dados: pd.DataFrame) -> None:
    """Trocar de quadrante e deixar de ter quadrante não são a mesma coisa (§10.2.7)."""
    bloco = recorte(dados, Materializacao.REVISED.value).set_index("quarter")
    assert bloco.loc["2006Q2", "tipo_de_troca"] == T.TipoDeTroca.ROTULO.value
    assert bloco.loc["2007Q3", "tipo_de_troca"] == T.TipoDeTroca.STATUS.value
    assert bloco.loc["2006Q1", "tipo_de_troca"] == T.TipoDeTroca.NENHUMA.value
    assert bloco["trocou_vs_outra_materializacao"].sum() == 2


def test_divergencia_e_simetrica_entre_as_duas_materializacoes(dados: pd.DataFrame) -> None:
    """`asof` discordar de `revised` é a mesma afirmação que `revised` discordar de `asof`."""
    esquerda = recorte(dados, Materializacao.REVISED.value)
    direita = recorte(dados, Materializacao.ASOF.value)
    pd.testing.assert_series_equal(
        esquerda["tipo_de_troca"], direita["tipo_de_troca"], check_names=False
    )


def test_materializacao_sozinha_nao_inventa_comparacao() -> None:
    """Sem a outra tabela não há com o que comparar — e o campo sai `NENHUMA`, não `None`."""
    so_revised = T.dados_plotados(
        {Materializacao.REVISED.value: regimes_sinteticos(ROTULOS_REVISED)}, niveis_sinteticos()
    )
    assert (so_revised["tipo_de_troca"] == T.TipoDeTroca.NENHUMA.value).all()
    assert not so_revised["trocou_vs_outra_materializacao"].any()


def test_trimestre_sem_nivel_falha_em_vez_de_plotar_buraco() -> None:
    """Nível ausente é falha explícita: a figura nunca interpola para "fechar" a série (§10.1.1)."""
    incompleto = niveis_sinteticos().iloc[:-1]
    with pytest.raises(SerieInconsistente, match="sem nível"):
        T.dados_plotados(
            {Materializacao.REVISED.value: regimes_sinteticos(ROTULOS_REVISED)}, incompleto
        )


def test_entrada_vazia_e_recusada() -> None:
    """Zero materializações é erro de chamada, não figura em branco."""
    with pytest.raises(SerieInconsistente, match="nenhuma materialização"):
        T.dados_plotados({}, niveis_sinteticos())


def test_niveis_de_recusa_serie_ausente() -> None:
    """Sem IBOV ou sem Selic a figura não existe — `BLOQUEADO — FONTE INDISPONÍVEL`."""
    from apps.pipeline.common.errors import FonteIndisponivel

    alinhado = pd.DataFrame(
        {
            "quarter": ["2006Q1"],
            "quarter_end": pd.to_datetime(["2006-03-31"]),
            "series_id": [T.SERIE_IBOV],
            "value": [40000.0],
        }
    )
    with pytest.raises(FonteIndisponivel, match=T.SERIE_SELIC_META):
        T.niveis_de(alinhado)


# ═════════════════════════════════════════════════════════════════════════════
# 3 — CA-100: a faixa cobre a janela inteira, contígua, sem buraco
# ═════════════════════════════════════════════════════════════════════════════


def test_faixas_cobrem_todos_os_trimestres_sem_buraco(dados: pd.DataFrame) -> None:
    """**CA-100.** Toda posição do eixo está dentro de exatamente uma faixa."""
    bloco = recorte(dados, Materializacao.REVISED.value)
    faixas = T.faixas_de(bloco)
    T.exigir_cobertura_total(faixas, len(bloco))
    assert sum(f.n_trimestres for f in faixas) == len(bloco)
    posicoes = [p for f in faixas for p in range(f.inicio, f.fim + 1)]
    assert posicoes == list(range(len(bloco)))


def test_faixas_agrupam_trimestres_consecutivos_iguais(dados: pd.DataFrame) -> None:
    """2 `RECUPERACAO` seguidos viram 1 faixa; 2 indeterminados seguidos também."""
    faixas = T.faixas_de(recorte(dados, Materializacao.REVISED.value))
    assert [(f.rotulo, f.n_trimestres) for f in faixas] == [
        (RegimeV1.RECUPERACAO.value, 2),
        (RegimeV1.EXPANSAO_INFL.value, 1),
        (RegimeV1.ESTAGFLACAO.value, 1),
        (RegimeV1.DESACELERACAO.value, 1),
        (T.ROTULO_INDETERMINADO, 2),
        (RegimeV1.RECUPERACAO.value, 1),
    ]


def test_buraco_entre_faixas_e_recusado() -> None:
    """O guarda de CA-100 tem de pegar o buraco; senão ele vira superfície branca na figura."""
    com_buraco = [
        T.Faixa(0, 1, RegimeV1.RECUPERACAO.value, T.PALETA_CATEGORICA[0], ""),
        T.Faixa(3, 4, RegimeV1.ESTAGFLACAO.value, T.PALETA_CATEGORICA[2], ""),
    ]
    with pytest.raises(SerieInconsistente, match="buraco"):
        T.exigir_cobertura_total(com_buraco, 5)


def test_faixas_que_param_antes_do_fim_sao_recusadas() -> None:
    """Cobrir 6 de 8 trimestres é o mesmo defeito, só que na ponta."""
    curtas = [T.Faixa(0, 5, RegimeV1.RECUPERACAO.value, T.PALETA_CATEGORICA[0], "")]
    with pytest.raises(SerieInconsistente, match="não cobrem a janela"):
        T.exigir_cobertura_total(curtas, 8)


def test_contagem_por_rotulo_traz_n_de_todo_grupo(dados: pd.DataFrame) -> None:
    """`n` em toda célula (§10.2.8) — inclusive o dos indeterminados."""
    contagem = T.contagem_por_rotulo(recorte(dados, Materializacao.REVISED.value))
    assert contagem == {
        RegimeV1.RECUPERACAO.value: 3,
        RegimeV1.EXPANSAO_INFL.value: 1,
        RegimeV1.ESTAGFLACAO.value: 1,
        RegimeV1.DESACELERACAO.value: 1,
        T.ROTULO_INDETERMINADO: 2,
    }
    assert sum(contagem.values()) == len(QUARTERS_SINTETICOS)


# ═════════════════════════════════════════════════════════════════════════════
# 4 — O desenho: dois painéis, nunca eixo duplo; eixo x com todos os trimestres
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def figura(dados: pd.DataFrame):  # noqa: ANN201 - Figure, só para o teste
    """A figura `revised` da fixture sintética."""
    return T.desenhar(
        dados, materializacao=Materializacao.REVISED.value, versao="a" * 64, hashes_dos_insumos={}
    )


def test_dois_paineis_e_nenhum_eixo_y_gemeo(figura) -> None:  # noqa: ANN001
    """**Nunca eixo duplo.** IBOV (log) e Selic (%a.a.) em painéis próprios, mesmo eixo x."""
    assert len(figura.axes) == 2
    ibov, selic = figura.axes
    assert ibov.get_yscale() == "log"
    assert selic.get_yscale() == "linear"
    assert ibov.get_position().x0 == pytest.approx(selic.get_position().x0)
    assert ibov.get_position().x1 == pytest.approx(selic.get_position().x1)


def test_eixo_x_cobre_todos_os_trimestres(figura) -> None:  # noqa: ANN001
    """O eixo vai de meia posição antes do 1º a meia depois do último — nenhum fica para fora."""
    for eixo in figura.axes:
        assert eixo.get_xlim() == (-0.5, len(QUARTERS_SINTETICOS) - 0.5)


def test_eixo_x_e_rotulado_por_ano(figura) -> None:  # noqa: ANN001
    """Uma marca por ano, no `Q1` — ler "2008" no eixo é o que torna o sanity check possível."""
    rotulos = [t.get_text() for t in figura.axes[1].get_xticklabels()]
    assert rotulos == ["2006", "2007"]


def test_legenda_tem_toda_entidade_com_n(figura) -> None:  # noqa: ANN001
    """Legenda sempre presente, com `n` em cada entrada e os 2 marcadores de divergência."""
    textos = [t.get_text() for t in figura.legends[0].get_texts()]
    assert any(f"{RegimeV1.RECUPERACAO.value} (n=3)" == t for t in textos)
    assert any(T.ROTULO_INDETERMINADO in t and "n=2" in t for t in textos)
    assert all("n=" in t for t in textos)
    assert len(textos) == len(RegimeV1) + 3  # 4 quadrantes + indeterminado + 2 marcadores


def test_marcadores_de_divergencia_sao_desenhados(figura) -> None:  # noqa: ANN001
    """Os trimestres em que a outra materialização discorda ganham marcador em cada painel."""
    for eixo in figura.axes:
        marcadores = [linha for linha in eixo.lines if linha.get_linestyle() == "None"]
        pontos = sorted(x for linha in marcadores for x in linha.get_xdata())
        assert pontos == [1, 6]  # 2006Q2 (rótulo) e 2007Q3 (status)


def test_titulo_nomeia_a_materializacao_e_a_janela(figura) -> None:  # noqa: ANN001
    """`asof` é **sempre rotulada** (§10.2.7) — e a janela está no título, não na legenda."""
    titulo = figura._suptitle.get_text()
    assert Materializacao.REVISED.value in titulo
    assert QUARTERS_SINTETICOS[0] in titulo
    assert QUARTERS_SINTETICOS[-1] in titulo
    assert f"{len(QUARTERS_SINTETICOS)} trimestres" in titulo


def test_nenhum_texto_da_figura_e_preditivo(figura) -> None:  # noqa: ANN001
    """§10.2.10: o entregável é descritivo. "vai render" / "projeção de" não entram na figura."""
    todos = " ".join(t.get_text() for t in figura.texts).lower()
    for proibido in ("vai render", "deve render", "previsão", "projetamos", "tendência futura"):
        assert proibido not in todos


def test_materializacao_inexistente_nos_dados_falha(dados: pd.DataFrame) -> None:
    """Pedir uma materialização que não está nos dados é erro, não figura vazia."""
    so_asof = dados[dados["materializacao"] == Materializacao.ASOF.value]
    with pytest.raises(SerieInconsistente, match="nenhuma linha"):
        T.desenhar(
            so_asof,
            materializacao=Materializacao.REVISED.value,
            versao="a" * 64,
            hashes_dos_insumos={},
        )


# ═════════════════════════════════════════════════════════════════════════════
# 5 — CA-090: o gate de publicação na figura
# ═════════════════════════════════════════════════════════════════════════════


def textos_da_figura(figura) -> list[str]:  # noqa: ANN001
    """Todo texto de nível de figura (título, subtítulo, rodapé, marca d'água)."""
    return [t.get_text() for t in figura.texts]


def test_rodape_traz_a_marca_quando_a_especificacao_nao_esta_congelada(figura) -> None:  # noqa: ANN001
    """**CA-090.** `especificacao_congelada=False` ⇒ a figura diz que não é publicável."""
    textos = textos_da_figura(figura)
    assert T.MARCA_NAO_CONGELADA in textos
    assert textos.count(T.MARCA_NAO_CONGELADA) == 2  # linha de rodapé + marca d'água diagonal


def test_sem_a_marca_quando_o_adr_esta_aceito() -> None:
    """Com o ADR-001 aceito a marca some — senão ela seria decoração, não gate."""
    congelados = dados_sinteticos(congelada=True)
    figura = T.desenhar(
        congelados,
        materializacao=Materializacao.REVISED.value,
        versao="a" * 64,
        hashes_dos_insumos={},
    )
    assert T.MARCA_NAO_CONGELADA not in textos_da_figura(figura)


def test_rodape_traz_versao_build_e_hash_dos_insumos(dados: pd.DataFrame) -> None:
    """Procedência no pé: o hash do código e o de cada insumo lido (RF-047/CA-121)."""
    figura = T.desenhar(
        dados,
        materializacao=Materializacao.REVISED.value,
        versao="b" * 64,
        hashes_dos_insumos={"regimes_v1.parquet": "c" * 64},
    )
    rodape = " ".join(textos_da_figura(figura))
    assert "versao_build " + "b" * 12 in rodape
    assert "regimes_v1.parquet " + "c" * 12 in rodape
    assert FONTE_VERSAO_SINTETICA[:12] in rodape


def test_rodape_declara_a_troca_de_33_por_cento(figura) -> None:  # noqa: ANN001
    """CA-074 não some da figura: quem olhar a timeline lê que a `asof` discorda em 1/3."""
    rodape = " ".join(textos_da_figura(figura))
    assert "33,33%" in rodape
    assert "CA-074" in rodape


# ═════════════════════════════════════════════════════════════════════════════
# 6 — Determinismo e o Parquet dos dados plotados
# ═════════════════════════════════════════════════════════════════════════════


def test_duas_chamadas_com_a_mesma_entrada_dao_o_mesmo_dataframe() -> None:
    """Função pura: nada de relógio, nada de ordenação instável."""
    pd.testing.assert_frame_equal(dados_sinteticos(), dados_sinteticos())


def test_dados_plotados_nao_mutam_a_entrada() -> None:
    """A tabela de regimes que entrou continua a mesma depois de montar os dados."""
    entrada = regimes_sinteticos(ROTULOS_REVISED)
    copia = entrada.copy(deep=True)
    T.dados_plotados({Materializacao.REVISED.value: entrada}, niveis_sinteticos())
    pd.testing.assert_frame_equal(entrada, copia)


def test_parquet_gravado_e_identico_ao_dataframe_plotado(
    dados: pd.DataFrame, tmp_path: Path
) -> None:
    """**A figura é a leitura; o Parquet é a evidência** — e os dois têm de ser a mesma coisa."""
    destino = T.gravar_dados(dados, raiz=tmp_path)
    assert destino.name == T.NOME_DADOS_PLOTADOS
    relido = pd.read_parquet(destino)
    pd.testing.assert_frame_equal(dados.reset_index(drop=True), relido)


def test_parquet_de_duas_rodadas_tem_os_mesmos_bytes(tmp_path: Path) -> None:
    """Idempotência por hash (`AGENTS.md §15.6`): 2 rodadas, mesmo arquivo byte a byte."""
    primeiro = T.gravar_dados(dados_sinteticos(), raiz=tmp_path)
    bytes_1 = primeiro.read_bytes()
    segundo = T.gravar_dados(dados_sinteticos(), raiz=tmp_path)
    assert segundo.read_bytes() == bytes_1


def test_figura_gravada_em_png_e_svg_e_determinista(dados: pd.DataFrame, tmp_path: Path) -> None:
    """PNG e SVG saem byte-idênticos em rodadas distintas: nenhum metadado sai do relógio."""
    impressoes: list[dict[str, bytes]] = []
    for _ in range(2):
        figura = T.desenhar(
            dados,
            materializacao=Materializacao.REVISED.value,
            versao="a" * 64,
            hashes_dos_insumos={},
        )
        caminhos = T.gravar_figura(
            figura, materializacao=Materializacao.REVISED.value, versao="a" * 64, raiz=tmp_path
        )
        assert set(caminhos) == set(T.FORMATOS)
        impressoes.append({f: c.read_bytes() for f, c in caminhos.items()})
    for formato in T.FORMATOS:
        assert impressoes[0][formato] == impressoes[1][formato], f"{formato} nao e determinista"


def test_svg_gravado_nao_carrega_data(dados: pd.DataFrame, tmp_path: Path) -> None:
    """Sem `<dc:date>` no SVG: data embutida faria o arquivo mudar sem o dado mudar."""
    figura = T.desenhar(
        dados, materializacao=Materializacao.ASOF.value, versao="a" * 64, hashes_dos_insumos={}
    )
    caminhos = T.gravar_figura(
        figura, materializacao=Materializacao.ASOF.value, versao="a" * 64, raiz=tmp_path
    )
    corpo = caminhos["svg"].read_text(encoding="utf-8")
    assert "<dc:date>" not in corpo


def test_nomes_dos_arquivos_por_materializacao(dados: pd.DataFrame, tmp_path: Path) -> None:
    """`revised` e `asof` nunca se sobrescrevem: o nome do arquivo carrega a materialização."""
    nomes = set()
    for chave in (Materializacao.REVISED.value, Materializacao.ASOF.value):
        figura = T.desenhar(dados, materializacao=chave, versao="a" * 64, hashes_dos_insumos={})
        caminhos = T.gravar_figura(figura, materializacao=chave, versao="a" * 64, raiz=tmp_path)
        nomes |= {c.name for c in caminhos.values()}
    assert nomes == {
        "timeline_regimes_revised.png",
        "timeline_regimes_revised.svg",
        "timeline_regimes_asof.png",
        "timeline_regimes_asof.svg",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 7 — Acervo real `data/canonical/` (padrão `Acervo`; desligado por LDC_IGNORAR_DATA=1)
# ═════════════════════════════════════════════════════════════════════════════

N_TRIMESTRES_REAIS = 83
N_TROCAS_DE_ROTULO = 22
N_TROCAS_DE_STATUS = 2
N_INDETERMINADOS = 16


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


def canonical_disponivel() -> bool:
    """Os três Parquets que a figura lê existem nesta máquina?"""
    alvos = [T.NOME_ALINHADO, *T.NOME_REGIMES_POR_MATERIALIZACAO.values()]
    return all(caminho_canonical(nome).is_file() for nome in alvos)


acervo_real = pytest.mark.skipif(
    ignorar_data_real() or not canonical_disponivel(),
    reason=f"data/canonical/ ausente ou {VAR_IGNORAR_DATA} ligada — {COMO_GERAR}",
)


@pytest.fixture(scope="module")
def resultado_real():  # noqa: ANN201 - ResultadoTimeline
    """A timeline recalculada do acervo real, **sem gravar** (o teste não mexe em `data/`)."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponível")
    return T.construir(gravar=False)


@acervo_real
def test_acervo_tem_os_83_trimestres_em_cada_materializacao(resultado_real) -> None:  # noqa: ANN001
    """**CA-100 no dado real:** 83 trimestres, 2006Q1→2026Q3, nas duas materializações."""
    for chave in (Materializacao.REVISED.value, Materializacao.ASOF.value):
        bloco = recorte(resultado_real.dados, chave)
        assert len(bloco) == N_TRIMESTRES_REAIS
        assert bloco["quarter"].iloc[0] == "2006Q1"
        assert bloco["quarter"].iloc[-1] == "2026Q3"
        assert bloco["quarter"].is_unique


@acervo_real
def test_acervo_eixo_da_figura_traz_os_83_trimestres(resultado_real) -> None:  # noqa: ANN001
    """O eixo desenhado tem os 83 — não um recorte silencioso dos 67 classificados."""
    figura = resultado_real.figuras[Materializacao.REVISED.value]
    for eixo in figura.axes:
        assert eixo.get_xlim() == (-0.5, N_TRIMESTRES_REAIS - 0.5)
    rotulos = [t.get_text() for t in figura.axes[1].get_xticklabels()]
    assert rotulos == [str(ano) for ano in range(2006, 2027)]


@acervo_real
def test_acervo_faixas_cobrem_os_83_sem_buraco(resultado_real) -> None:  # noqa: ANN001
    """**CA-100.** Nenhuma posição do eixo fica sem faixa, nas duas materializações."""
    for chave in (Materializacao.REVISED.value, Materializacao.ASOF.value):
        bloco = recorte(resultado_real.dados, chave)
        T.exigir_cobertura_total(T.faixas_de(bloco), N_TRIMESTRES_REAIS)


@acervo_real
def test_acervo_colunas_de_regime_sao_identicas_a_regimes_v1(resultado_real) -> None:  # noqa: ANN001
    """**O diff numérico:** cada coluna herdada é o valor de `regimes_v1`, sem transformação."""
    for chave, nome in T.NOME_REGIMES_POR_MATERIALIZACAO.items():
        origem = (
            pd.read_parquet(caminho_canonical(nome))
            .sort_values("quarter", kind="stable")
            .reset_index(drop=True)
        )
        bloco = recorte(resultado_real.dados, chave)
        for coluna in T.COLUNAS_HERDADAS_DE_REGIMES_V1:
            pd.testing.assert_series_equal(
                bloco[coluna].reset_index(drop=True),
                origem[coluna].reset_index(drop=True),
                check_names=False,
                check_dtype=False,
            )


@acervo_real
def test_acervo_niveis_sao_os_de_alinhado_trimestral(resultado_real) -> None:  # noqa: ANN001
    """IBOV e Selic meta vêm de `alinhado_trimestral`, célula a célula, sem recálculo."""
    esperado = T.ler_niveis()
    assert len(esperado) == N_TRIMESTRES_REAIS
    assert not esperado[["ibov_nivel", "selic_meta_pct"]].isna().to_numpy().any()
    bloco = recorte(resultado_real.dados, Materializacao.REVISED.value)
    pd.testing.assert_series_equal(bloco["ibov_nivel"], esperado["ibov_nivel"], check_names=False)
    pd.testing.assert_series_equal(
        bloco["selic_meta_pct"], esperado["selic_meta_pct"], check_names=False
    )


@acervo_real
def test_acervo_divergencia_bate_com_trocou_vs_revised(resultado_real) -> None:  # noqa: ANN001
    """A divergência calculada aqui reproduz `trocou_vs_revised` da `asof` — 22 + 2 = 24."""
    asof = (
        pd.read_parquet(caminho_canonical(T.NOME_REGIMES_POR_MATERIALIZACAO["asof"]))
        .sort_values("quarter", kind="stable")
        .reset_index(drop=True)
    )
    bloco = recorte(resultado_real.dados, Materializacao.ASOF.value)
    assert bloco["trocou_vs_outra_materializacao"].tolist() == asof["trocou_vs_revised"].tolist()
    assert (bloco["tipo_de_troca"] == T.TipoDeTroca.ROTULO.value).sum() == N_TROCAS_DE_ROTULO
    assert (bloco["tipo_de_troca"] == T.TipoDeTroca.STATUS.value).sum() == N_TROCAS_DE_STATUS


@acervo_real
def test_acervo_indeterminados_sao_os_16_de_d_m(resultado_real) -> None:  # noqa: ANN001
    """Os 16 sem `ibcbr_gap` (**D-m**) aparecem como ausência declarada, com `n` na legenda."""
    bloco = recorte(resultado_real.dados, Materializacao.REVISED.value)
    indeterminados = bloco[bloco["rotulo_da_faixa"] == T.ROTULO_INDETERMINADO]
    assert len(indeterminados) == N_INDETERMINADOS
    assert (indeterminados["hachura"] == T.HACHURA_INDETERMINADO).all()
    assert indeterminados["quarter"].tolist()[:15] == [
        q for q in bloco["quarter"] if "2006" <= q[:4] <= "2009" and q <= "2009Q3"
    ]
    assert "2026Q3" in indeterminados["quarter"].tolist()


@acervo_real
def test_acervo_gate_fechado_e_marca_na_figura(resultado_real) -> None:  # noqa: ANN001
    """**CA-090 no dado real:** ADR-001 em `Proposta` ⇒ as duas figuras saem não publicáveis."""
    assert not resultado_real.dados["especificacao_congelada"].any()
    assert resultado_real.relatorio["especificacao"]["marca_na_figura"] == T.MARCA_NAO_CONGELADA
    for figura in resultado_real.figuras.values():
        assert T.MARCA_NAO_CONGELADA in textos_da_figura(figura)


@acervo_real
def test_acervo_relatorio_declara_n_por_rotulo(resultado_real) -> None:  # noqa: ANN001
    """A distribuição `revised` medida: 19/19/16/13 + 16 indeterminados = 83 (§10.2.8)."""
    bloco = resultado_real.relatorio["por_materializacao"][Materializacao.REVISED.value]
    assert bloco["n_por_rotulo"] == {
        RegimeV1.RECUPERACAO.value: 19,
        RegimeV1.EXPANSAO_INFL.value: 19,
        RegimeV1.ESTAGFLACAO.value: 16,
        RegimeV1.DESACELERACAO.value: 13,
        T.ROTULO_INDETERMINADO: 16,
    }
    assert sum(bloco["n_por_rotulo"].values()) == N_TRIMESTRES_REAIS


@acervo_real
def test_acervo_n_da_legenda_reproduz_n_obs_regime_v1(resultado_real) -> None:  # noqa: ANN001
    """O `n` da legenda **é** `n_obs_regime_v1` de `regimes_v1` — não uma contagem paralela.

    Se os dois divergissem, a figura estaria publicando um `n` próprio, e o `n` da tabela e o do
    gráfico contariam histórias diferentes sobre a mesma célula (§10.2.8).
    """
    for chave in (Materializacao.REVISED.value, Materializacao.ASOF.value):
        bloco = recorte(resultado_real.dados, chave)
        contagem = T.contagem_por_rotulo(bloco)
        for rotulo, n in contagem.items():
            do_dado = set(bloco.loc[bloco["rotulo_da_faixa"] == rotulo, "n_obs_regime_v1"])
            assert do_dado == {n}, f"{chave}/{rotulo}: legenda n={n}, dado {do_dado}"
        assert sum(contagem.values()) == N_TRIMESTRES_REAIS


@acervo_real
def test_acervo_artefatos_em_disco_batem_com_o_recalculo(resultado_real) -> None:  # noqa: ANN001
    """O Parquet publicado em `data/canonical/figuras/` é o que esta rodada produziria."""
    alvo = T.caminho_figuras() / T.NOME_DADOS_PLOTADOS
    if not alvo.is_file():
        pytest.skip(f"{alvo.name} ainda não materializado — {COMO_GERAR}")
    pd.testing.assert_frame_equal(pd.read_parquet(alvo), resultado_real.dados)
    for chave in T.NOME_REGIMES_POR_MATERIALIZACAO:
        for formato in T.FORMATOS:
            figura = T.caminho_figuras() / f"timeline_regimes_{chave}.{formato}"
            assert figura.is_file(), f"{figura.name} ausente — {COMO_GERAR}"
            assert figura.stat().st_size > 0
