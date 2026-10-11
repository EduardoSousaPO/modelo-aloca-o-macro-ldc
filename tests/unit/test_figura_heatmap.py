"""F-023 — testes do heatmap regime × ativo. **RF-033 / CA-095, CA-096, CA-097** (+ CA-090).

Organização, e o motivo de cada bloco:

| Bloco | O que trava | CA |
|---|---|---|
| 1 | a paleta divergente: derivada, centrada em 0, simétrica, sem verde | CA-095 |
| 2 | a grade: 24 ativos por classe × colunas na ordem do enum, **sem buraco** | CA-095 |
| 3 | os três estados de confiança: `n >= 8`, `5 <= n < 8`, `n < 5` | CA-096, CA-108/109 |
| 4 | o desenho: célula, `n`, cabeçalho, título, e **nada preditivo** | CA-095, §10.2.10 |
| 5 | o rodapé: `data_inicio` de **cada** série e a métrica **nomeada** | CA-097 |
| 6 | o gate: rodapé e marca d'água com `especificacao_congelada=False` | CA-090 |
| 7 | determinismo: 2 rodadas, mesmos bytes; dados == Parquet; tooltip no SVG | CA-121 |
| 8 | **acervo real** — 24 × (4+1), valores idênticos ao Parquet de F-022 | todos |

Os blocos 1-7 rodam sobre uma **fixture sintética** de 24 ativos × 5 colunas, nomeada como
sintética (Anti-SPEC §10.1.2), e **nunca pulam**: rodam no CI sem `data/`. O bloco 8 segue o
padrão `Acervo` de `test_figura_timeline_regimes.py §7` — entra por acréscimo quando os Parquets
existem em disco e é desligado por `LDC_IGNORAR_DATA=1`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from matplotlib.colors import to_rgba
from matplotlib.patches import Rectangle

from apps.analysis.figuras import _comum
from apps.analysis.figuras import heatmap_regime_ativo as H
from apps.analysis.figuras import timeline_regimes as T
from apps.pipeline.canonical.regimes_v1 import N_ALERTA, N_SUPRESSAO
from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical
from packages.shared.schemas.asset_returns_quarterly import RegimeAssetMetricsSchema
from packages.shared.schemas.regimes import RegimeV1

COMO_GERAR = "rode `uv run python -m apps.analysis.figuras.heatmap_regime_ativo`"
VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"

FONTE_VERSAO_SINTETICA = "0" * 64
REGIME_V3_SINTETICO = "VIZINHOS_2026Q3"

#: `n` sintético por coluna: o 6 e o 3 existem para exercitar os dois limiares de RF-040.
N_POR_COLUNA: dict[tuple[str, str], int] = {
    (H.LENTE_V1, RegimeV1.RECUPERACAO.value): 19,
    (H.LENTE_V1, RegimeV1.EXPANSAO_INFL.value): 19,
    (H.LENTE_V1, RegimeV1.ESTAGFLACAO.value): 16,
    (H.LENTE_V1, RegimeV1.DESACELERACAO.value): 13,
    (H.LENTE_V3, REGIME_V3_SINTETICO): 8,
}

#: Ativos que recebem `n` reduzido na coluna da V3 — a janela própria de CA-093, em sintético.
N_REDUZIDO_NA_V3: dict[str, int] = {"ICON": 6, "IFIX": 3}

TRIMESTRES_POR_REGIME_SINTETICO: dict[str, int] = {
    regime: n for (lente, regime), n in N_POR_COLUNA.items() if lente == H.LENTE_V1
}


def _excesso_sintetico(ativo: str, indice_coluna: int) -> float:
    """Valor de célula **sintético e determinístico**. `CDI` é zero por construção da métrica."""
    if ativo == "CDI":
        return 0.0
    base = (H.ORDEM_DOS_ATIVOS.index(ativo) - 11) / 180.0
    return round(base * (1 if indice_coluna % 2 == 0 else -1) + indice_coluna / 400.0, 6)


def metricas_sinteticas(*, com_v3: bool = True) -> pd.DataFrame:
    """Uma tabela no formato de `regime_asset_metrics`. **Sintética, não é dado real.**"""
    colunas = [c for c in N_POR_COLUNA if com_v3 or c[0] != H.LENTE_V3]
    registros: list[dict[str, object]] = []
    for indice, (lente, regime) in enumerate(colunas):
        for ativo in H.ORDEM_DOS_ATIVOS:
            n = N_POR_COLUNA[(lente, regime)]
            if lente == H.LENTE_V3:
                n = N_REDUZIDO_NA_V3.get(ativo, n)
            excesso = _excesso_sintetico(ativo, indice)
            registros.append(
                {
                    "lente": lente,
                    "regime": regime,
                    "asset_id": ativo,
                    "n_obs": n,
                    "ret_medio": excesso + 0.02,
                    "ret_mediana": excesso + 0.01,
                    "ret_desvio": 0.08,
                    "erro_padrao_media": round(0.08 / n**0.5, 6),
                    "hit_ratio": 0.55,
                    "excesso_cdi": excesso,
                    "hit_ratio_cdi": 0.5,
                    "ret_real": excesso - 0.01,
                    "sharpe_tri": 0.2,
                    "pior_tri": -0.3,
                    "pior_tri_quarter": "2020Q1",
                    "melhor_tri": 0.3,
                    "melhor_tri_quarter": "2020Q2",
                    "beta_ibov": 1.0,
                    "alerta_n_baixo": n < N_ALERTA,
                    "conclusao_suprimida": n < N_SUPRESSAO,
                    "data_inicio_serie": pd.Timestamp("2006-01-02"),
                    "fonte_versao": FONTE_VERSAO_SINTETICA,
                }
            )
    return pd.DataFrame.from_records(registros)


def dados_sinteticos(*, com_v3: bool = True) -> pd.DataFrame:
    """Os dados plotados da vista principal, a partir da tabela sintética."""
    return H.dados_plotados(
        metricas_sinteticas(com_v3=com_v3),
        vista=H.VISTA_PRINCIPAL,
        trimestres_por_regime=TRIMESTRES_POR_REGIME_SINTETICO,
    )


@pytest.fixture
def dados() -> pd.DataFrame:
    """Dados plotados sintéticos da vista principal (24 ativos × 5 colunas)."""
    return dados_sinteticos()


@pytest.fixture
def colunas() -> tuple[H.ColunaDoHeatmap, ...]:
    """As colunas da vista principal sintética, na ordem do contrato."""
    return H.ordem_das_colunas(
        metricas_sinteticas(), H.VISTA_PRINCIPAL, TRIMESTRES_POR_REGIME_SINTETICO
    )


def figura_sintetica(
    dados: pd.DataFrame,
    colunas: tuple[H.ColunaDoHeatmap, ...],
    *,
    congelada: bool = False,
):  # noqa: ANN201 - Figure, só para o teste
    """A figura da vista principal sintética, sem tocar o disco."""
    return H.desenhar(
        dados,
        vista=H.VISTA_PRINCIPAL,
        colunas=colunas,
        extremo=H.extremo_simetrico(dados["excesso_cdi"].tolist()),
        janela=("2006Q1", "2026Q3"),
        versao="a" * 64,
        hashes_dos_insumos={"regime_asset_metrics.parquet": "c" * 64},
        congelada=congelada,
    )


def textos_da_figura(figura) -> list[str]:  # noqa: ANN001
    """Todo texto de nível de figura (título, subtítulo, rodapé, marca d'água)."""
    return [t.get_text() for t in figura.texts]


def todos_os_textos(figura) -> list[str]:  # noqa: ANN001
    """Texto de figura **e** de eixo — é o que o leitor vê, e o que §10.2.10 governa."""
    saida = textos_da_figura(figura)
    for eixo in figura.axes:
        saida += [t.get_text() for t in eixo.texts]
        saida += [t.get_text() for t in eixo.get_xticklabels()]
        saida += [t.get_text() for t in eixo.get_yticklabels()]
        if eixo.get_title():
            saida.append(eixo.get_title())
    for legenda in figura.legends:
        saida += [t.get_text() for t in legenda.get_texts()]
    return saida


def celulas_desenhadas(figura) -> list[Rectangle]:  # noqa: ANN001
    """Os retângulos de célula (os que carregam `gid` de célula)."""
    return [
        artista
        for eixo in figura.axes
        for artista in eixo.patches
        if isinstance(artista, Rectangle) and str(artista.get_gid() or "").startswith("celula-")
    ]


# ═════════════════════════════════════════════════════════════════════════════
# 1 — A paleta divergente: derivada, centrada em zero, simétrica, sem verde
# ═════════════════════════════════════════════════════════════════════════════


def test_arco_quente_congelado_e_exatamente_o_derivado() -> None:
    """A constante do módulo **é** o que a derivação produz — ninguém escolheu vermelho a olho."""
    assert _comum.arco_quente_derivado() == _comum.ARCO_QUENTE


def test_arcos_tem_o_mesmo_numero_de_passos_e_luminancias_espelhadas() -> None:
    """ "Passos iguais por arco" (`dataviz`): mesma contagem e mesma luminância passo a passo."""
    assert len(_comum.ARCO_FRIO) == len(_comum.ARCO_QUENTE)
    for frio, quente in zip(_comum.ARCO_FRIO, _comum.ARCO_QUENTE, strict=True):
        assert _comum.luminancia_relativa(frio) == pytest.approx(
            _comum.luminancia_relativa(quente), abs=2e-3
        )


def test_cada_arco_escurece_monotonamente_do_centro_para_o_polo() -> None:
    """Magnitude é lida como escuridão: a luminância tem de cair do neutro até o polo."""
    for arco in (_comum.ARCO_FRIO, _comum.ARCO_QUENTE):
        luminancias = [_comum.luminancia_relativa(c) for c in (_comum.NEUTRO_DIVERGENTE, *arco)]
        assert luminancias == sorted(luminancias, reverse=True)


def test_ponto_medio_e_cinza_neutro_e_nao_um_matiz() -> None:
    """O meio tem de ler como "nada" — canal máximo e mínimo quase iguais (`dataviz`)."""
    canais = [int(_comum.NEUTRO_DIVERGENTE[i : i + 2], 16) for i in (1, 3, 5)]
    assert max(canais) - min(canais) <= 6


def test_nenhum_passo_da_escala_e_verde() -> None:
    """Verde × vermelho colapsa em protanopia/deuteranopia — fora por decisão, não por acaso."""
    for cor in (*_comum.ARCO_FRIO, *_comum.ARCO_QUENTE):
        vermelho, verde, azul = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
        assert not (verde > vermelho and verde > azul), f"{cor} é um verde"


def test_polos_contrastam_com_a_superficie() -> None:
    """Os extremos têm de passar 3:1 contra a superfície do gráfico (check 5 da `dataviz`)."""
    for polo in (_comum.ARCO_FRIO[-1], _comum.ARCO_QUENTE[-1]):
        assert _comum.contraste(polo, _comum.SUPERFICIE) >= 3.0


def test_escala_e_simetrica_e_o_zero_cai_no_meio_exato() -> None:
    """**CA-095/ADR-002 §3:** sem simetria o cinza do meio deixaria de significar "empatou"."""
    norma = _comum.normalizacao_centrada_em_zero(0.085)
    assert float(norma(0.0)) == pytest.approx(0.5)
    assert float(norma(0.085)) == pytest.approx(1.0)
    assert float(norma(-0.085)) == pytest.approx(0.0)
    mapa = _comum.mapa_divergente()
    assert mapa(0.5) == pytest.approx(to_rgba(_comum.NEUTRO_DIVERGENTE), abs=0.02)


def test_extremo_simetrico_cobre_o_maior_valor_absoluto() -> None:
    """A escala nunca corta uma célula: o extremo é >= |v| máximo, arredondado para cima."""
    assert H.extremo_simetrico([0.0823, -0.069]) == pytest.approx(0.085)
    assert H.extremo_simetrico([-0.069, 0.01]) == pytest.approx(0.07)
    with pytest.raises(SerieInconsistente):
        H.extremo_simetrico([float("nan")])


def test_tinta_do_texto_sai_de_conta_de_contraste() -> None:
    """Sobre o polo escuro, tinta inversa; sobre o neutro claro, tinta primária."""
    assert _comum.tinta_legivel_sobre(_comum.ARCO_FRIO[-1]) == _comum.TINTA_INVERSA
    assert _comum.tinta_legivel_sobre(_comum.NEUTRO_DIVERGENTE) == _comum.TINTA_PRIMARIA


def test_tokens_de_cromo_batem_com_os_de_f025() -> None:
    """`timeline_regimes` está congelado e declara os mesmos tokens: não podem divergir calados."""
    for nome in _comum.TOKENS_COMPARTILHADOS_COM_F025:
        assert getattr(_comum, nome) == getattr(T, nome), nome


def test_cinza_de_supressao_nao_e_o_neutro_da_escala() -> None:
    """Se fossem a mesma cor, "sem conclusão" leria como "empatou com o CDI" — uma afirmação."""
    assert _comum.CINZA_SUPRIMIDO != _comum.NEUTRO_DIVERGENTE


# ═════════════════════════════════════════════════════════════════════════════
# 2 — A grade: 24 ativos por classe × colunas na ordem do enum, sem buraco
# ═════════════════════════════════════════════════════════════════════════════


def test_sao_24_ativos_sem_repeticao_e_acima_do_minimo_do_contrato() -> None:
    """RF-033 pede >= 18 linhas; o acervo tem 24 e nenhuma linha aparece duas vezes."""
    assert len(H.ORDEM_DOS_ATIVOS) == 24
    assert len(set(H.ORDEM_DOS_ATIVOS)) == 24


def test_ordem_das_linhas_e_por_classe_na_ordem_declarada() -> None:
    """A ordem é a de `GRUPOS`, **nunca** por desempenho: ranking mudaria a figura a cada rodada."""
    esperado = [ativo for grupo in H.GRUPOS for ativo in grupo.ativos]
    assert list(H.ORDEM_DOS_ATIVOS) == esperado
    assert [g.nome for g in H.GRUPOS][-1] == "Referencia da metrica"
    assert H.GRUPOS[-1].ativos == ("CDI",)


def test_cada_ativo_esta_em_exatamente_um_grupo() -> None:
    """Ativo em dois grupos sairia duas vezes na figura e uma vez no `n` — erro silencioso."""
    contagem: dict[str, int] = {}
    for grupo in H.GRUPOS:
        for ativo in grupo.ativos:
            contagem[ativo] = contagem.get(ativo, 0) + 1
    assert set(contagem.values()) == {1}


def test_posicoes_das_linhas_sao_crescentes_e_separam_os_grupos() -> None:
    """Vão entre grupos: o salto entre a última linha de um grupo e a 1ª do seguinte é maior."""
    posicoes = H.posicoes_das_linhas()
    valores = [posicoes[a] for a in H.ORDEM_DOS_ATIVOS]
    assert valores == sorted(valores)
    saltos = [b - a for a, b in zip(valores, valores[1:], strict=False)]
    assert max(saltos) == pytest.approx(1.0 + H.VAO_ENTRE_GRUPOS)
    assert min(saltos) == pytest.approx(1.0)


def test_colunas_seguem_a_ordem_do_enum_e_a_v3_vem_depois(
    colunas: tuple[H.ColunaDoHeatmap, ...],
) -> None:
    """**A ordem é do contrato, não do dado** — senão duas vistas deixam de ser comparáveis."""
    assert [c.regime for c in colunas[:4]] == [r.value for r in RegimeV1]
    assert all(c.lente == H.LENTE_V1 for c in colunas[:4])
    assert colunas[4].lente == H.LENTE_V3
    assert colunas[4].regime == REGIME_V3_SINTETICO


def test_horizonte_de_cada_coluna_vem_da_tabela_de_f022(
    colunas: tuple[H.ColunaDoHeatmap, ...],
) -> None:
    """Na vista principal a V1 é T0 e a V3 é T+1 — e isso aparece coluna a coluna."""
    assert {c.horizonte for c in colunas[:4]} == {"T0"}
    assert colunas[4].horizonte == "T+1"


def test_vista_asof_nao_ganha_coluna_v3() -> None:
    """A V3 **não tem** variante `asof`: inventar a coluna seria inventar dado."""
    colunas = H.ordem_das_colunas(metricas_sinteticas(com_v3=False), H.VISTA_ASOF)
    assert len(colunas) == 4
    assert all(c.lente == H.LENTE_V1 for c in colunas)


def test_grade_tem_uma_celula_por_ativo_e_coluna(dados: pd.DataFrame) -> None:
    """**CA-095:** 24 × 5 = 120 células, nenhuma faltando, nenhuma repetida."""
    assert len(dados) == len(H.ORDEM_DOS_ATIVOS) * len(N_POR_COLUNA)
    assert not dados.duplicated(subset=["asset_id", "coluna"]).any()
    H.exigir_grade_completa(dados, n_colunas=len(N_POR_COLUNA))


def test_ativo_faltando_na_tabela_falha_em_vez_de_deixar_buraco() -> None:
    """Célula ausente apareceria como superfície branca e seria lida como "não houve"."""
    recorte = metricas_sinteticas()
    mutilada = recorte[
        ~((recorte["asset_id"] == "IBOV") & (recorte["regime"] == RegimeV1.ESTAGFLACAO.value))
    ]
    with pytest.raises(SerieInconsistente, match="grade incompleta"):
        H.dados_plotados(mutilada, vista=H.VISTA_PRINCIPAL)


def test_grade_com_contagem_errada_e_recusada(dados: pd.DataFrame) -> None:
    """`exigir_grade_completa` é a guarda final antes de desenhar."""
    with pytest.raises(SerieInconsistente, match="células"):
        H.exigir_grade_completa(dados.iloc[:-1], n_colunas=len(N_POR_COLUNA))


def test_toda_celula_tem_n_anotado_e_nenhuma_fica_sem_anotacao(dados: pd.DataFrame) -> None:
    """**CA-095 literal:** zero células sem `n`, e o `n` do rótulo é o `n_obs` da tabela."""
    assert dados["n_obs"].notna().all()
    assert (dados["rotulo_n"].str.startswith("n=")).all()
    extraido = dados["rotulo_n"].str.extract(r"n=(\d+)")[0].astype(int)
    pd.testing.assert_series_equal(extraido, dados["n_obs"], check_names=False)


def test_contrato_de_colunas_exato_e_na_ordem(dados: pd.DataFrame) -> None:
    """O Parquet de dados plotados tem contrato próprio, travado aqui."""
    assert list(dados.columns) == list(H.COLUNAS_DADOS_PLOTADOS)


def test_colunas_de_metrica_mantem_o_nome_de_regime_asset_metrics(dados: pd.DataFrame) -> None:
    """Nome herdado é **literal** — renomear aqui quebraria a conferência contra F-022."""
    metricas = metricas_sinteticas()
    for nome in H.COLUNAS_HERDADAS_DE_METRICAS:
        assert nome in metricas.columns
        assert nome in dados.columns


def test_a_figura_nao_recalcula_o_excesso(dados: pd.DataFrame) -> None:
    """O valor plotado **é** o valor de F-022, célula a célula (nenhuma transformação)."""
    metricas = metricas_sinteticas().set_index(["lente", "regime", "asset_id"])
    for linha in dados.itertuples():
        esperado = metricas.loc[(linha.lente, linha.regime, linha.asset_id), "excesso_cdi"]
        assert linha.excesso_cdi == pytest.approx(float(esperado))


def test_dados_plotados_nao_mutam_a_entrada() -> None:
    """A tabela de métricas que entrou continua a mesma depois de montar os dados."""
    entrada = metricas_sinteticas()
    copia = entrada.copy(deep=True)
    H.dados_plotados(entrada, vista=H.VISTA_PRINCIPAL)
    pd.testing.assert_frame_equal(entrada, copia)


def test_fixture_sintetica_satisfaz_o_schema_de_f022() -> None:
    """Sintética, mas no **mesmo** contrato do dado real — senão o teste prova outra coisa."""
    RegimeAssetMetricsSchema.validate(metricas_sinteticas(), lazy=True)


# ═════════════════════════════════════════════════════════════════════════════
# 3 — Os três estados de confiança (CA-096, CA-108/109)
# ═════════════════════════════════════════════════════════════════════════════


def celula(dados: pd.DataFrame, ativo: str, regime: str) -> pd.Series:
    """Uma célula dos dados plotados, por ativo e regime."""
    recorte = dados[(dados["asset_id"] == ativo) & (dados["regime"] == regime)]
    assert len(recorte) == 1, f"{ativo}/{regime} não é única"
    return recorte.iloc[0]


def test_celula_cheia_usa_a_cor_divergente_sem_borda_nem_hachura(dados: pd.DataFrame) -> None:
    """`n >= 8`: cor, número em destaque, nenhum sinal de ressalva."""
    alvo = celula(dados, "IBOV", RegimeV1.RECUPERACAO.value)
    assert alvo["n_obs"] >= N_ALERTA
    assert alvo["hachura"] == ""
    assert not alvo["borda"]
    assert alvo["cor_hex"] != _comum.CINZA_SUPRIMIDO
    assert H.MARCA_ALERTA not in alvo["rotulo_valor"]


def test_n_entre_5_e_7_mantem_a_cor_mas_ganha_borda_e_asterisco(dados: pd.DataFrame) -> None:
    """**CA-096/CA-108:** dois canais além da cor — borda tracejada e `*` no número e no `n`."""
    alvo = celula(dados, "ICON", REGIME_V3_SINTETICO)
    assert int(alvo["n_obs"]) == N_REDUZIDO_NA_V3["ICON"]
    assert alvo["alerta_n_baixo"] and not alvo["conclusao_suprimida"]
    assert alvo["borda"]
    assert alvo["cor_hex"] != _comum.CINZA_SUPRIMIDO
    assert alvo["rotulo_valor"].endswith(H.MARCA_ALERTA)
    assert alvo["rotulo_n"].endswith(H.MARCA_ALERTA)


def test_n_abaixo_de_5_perde_a_cor_e_o_numero_sai_de_destaque(dados: pd.DataFrame) -> None:
    """**CA-109:** cinza hachurado, `prelim.` e **nenhum número em destaque** — e o valor fica."""
    alvo = celula(dados, "IFIX", REGIME_V3_SINTETICO)
    assert int(alvo["n_obs"]) == N_REDUZIDO_NA_V3["IFIX"]
    assert alvo["conclusao_suprimida"]
    assert alvo["cor_hex"] == _comum.CINZA_SUPRIMIDO
    assert alvo["hachura"] == _comum.HACHURA_SUPRIMIDO
    assert alvo["rotulo_valor"].startswith(H.PREFIXO_PRELIMINAR)
    assert not alvo["borda"], "a borda de alerta não se acumula com a supressão"
    assert alvo["rotulo_n"] == f"n={int(alvo['n_obs'])}"


def test_celula_suprimida_desenha_o_numero_em_fonte_menor_e_sem_negrito(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """ "Sem número de destaque" tem de ser verdade **no desenho**, não só no dado."""
    figura = figura_sintetica(dados, colunas)
    textos = {t.get_text(): t for eixo in figura.axes for t in eixo.texts if t.get_text().strip()}
    suprimida = celula(dados, "IFIX", REGIME_V3_SINTETICO)["rotulo_valor"]
    cheia = celula(dados, "IBOV", RegimeV1.RECUPERACAO.value)["rotulo_valor"]
    assert textos[suprimida].get_fontsize() == pytest.approx(H.FONTE_PRELIM)
    assert textos[suprimida].get_fontweight() == "normal"
    assert textos[cheia].get_fontsize() == pytest.approx(H.FONTE_VALOR)
    assert textos[cheia].get_fontweight() == "bold"
    assert textos[suprimida].get_fontsize() < textos[cheia].get_fontsize()


def test_flags_que_discordam_do_n_sao_recusadas() -> None:
    """Hachurar por conta própria (ou deixar de hachurar) é o modo de falha caro desta figura."""
    adulterada = metricas_sinteticas()
    adulterada.loc[adulterada["asset_id"] == "IFIX", "conclusao_suprimida"] = False
    with pytest.raises(SerieInconsistente, match="não batem com n"):
        H.dados_plotados(adulterada, vista=H.VISTA_PRINCIPAL)


def test_excesso_nulo_e_recusado_em_vez_de_virar_cor() -> None:
    """Célula sem valor não vira cinza "neutro" — vira falha (Anti-SPEC §10.1.1)."""
    adulterada = metricas_sinteticas()
    adulterada.loc[adulterada.index[0], "excesso_cdi"] = None
    with pytest.raises(SerieInconsistente, match="excesso_cdi nulo"):
        H.dados_plotados(adulterada, vista=H.VISTA_PRINCIPAL)


def test_linha_do_cdi_e_zero_e_cai_no_neutro_da_escala(dados: pd.DataFrame) -> None:
    """O *sanity check* da própria métrica (ADR-002): `CDI` empata consigo mesmo em todo regime."""
    cdi = dados[dados["asset_id"] == "CDI"]
    assert len(cdi) == len(N_POR_COLUNA)
    assert (cdi["excesso_cdi"] == 0.0).all()
    for cor in cdi["cor_hex"]:
        assert to_rgba(cor) == pytest.approx(to_rgba(_comum.NEUTRO_DIVERGENTE), abs=0.02)


def test_contagem_de_flags_fecha_com_o_total(dados: pd.DataFrame) -> None:
    """A legenda carrega `n` de cada estado — e a soma tem de ser o total de células (§10.2.8)."""
    flags = H.contagem_de_flags(dados)
    assert flags["celulas"] == len(dados)
    assert flags["plenas"] + flags["alerta_n_baixo"] + flags["conclusao_suprimida"] == len(dados)
    assert flags["conclusao_suprimida"] == len(N_REDUZIDO_NA_V3) - 1  # só o IFIX tem n < 5
    assert flags["alerta_n_baixo"] == 1  # o ICON, com n = 6


# ═════════════════════════════════════════════════════════════════════════════
# 4 — O desenho
# ═════════════════════════════════════════════════════════════════════════════


def test_uma_celula_desenhada_por_linha_dos_dados(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """A figura desenha exatamente o que está no Parquet — nem mais, nem menos."""
    figura = figura_sintetica(dados, colunas)
    desenhadas = celulas_desenhadas(figura)
    assert len(desenhadas) == len(dados)
    assert {r.get_gid() for r in desenhadas} == set(dados["gid"])


def test_cor_de_cada_celula_desenhada_bate_com_os_dados_plotados(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Se o desenho pudesse escolher outra cor, o Parquet deixaria de ser evidência."""
    figura = figura_sintetica(dados, colunas)
    por_gid = {r.get_gid(): r for r in celulas_desenhadas(figura)}
    for linha in dados.itertuples():
        assert por_gid[linha.gid].get_facecolor() == pytest.approx(to_rgba(linha.cor_hex))
        assert (por_gid[linha.gid].get_hatch() or "") == linha.hachura


def test_o_n_de_toda_celula_aparece_no_desenho(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """**CA-095 no desenho:** os 120 rótulos de `n` estão lá, um por célula."""
    figura = figura_sintetica(dados, colunas)
    desenhados = [t.get_text() for eixo in figura.axes for t in eixo.texts]
    for rotulo in dados["rotulo_n"]:
        assert rotulo in desenhados
    assert sum(1 for t in desenhados if t.startswith("n=")) == len(dados)


def test_cabecalho_nomeia_regime_lente_e_horizonte(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Quem olha a coluna tem de saber de que lente e de que horizonte ela é."""
    figura = figura_sintetica(dados, colunas)
    texto = " ".join(todos_os_textos(figura))
    for coluna in colunas:
        assert coluna.regime.split("_")[0] in texto
        assert f"lente {coluna.lente} · horizonte {coluna.horizonte}" in texto


def test_todo_ativo_tem_rotulo_de_linha_e_todo_grupo_tem_titulo(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Identidade nunca é só posição: cada linha é nomeada e cada classe é nomeada."""
    figura = figura_sintetica(dados, colunas)
    textos = [t.get_text() for eixo in figura.axes for t in eixo.texts]
    for ativo in H.ORDEM_DOS_ATIVOS:
        esperado = ativo + (H.MARCA_MOEDA if ativo in H.ATIVOS_FORA_DA_MOEDA else "")
        assert esperado in textos
    for grupo in H.GRUPOS:
        assert grupo.nome.upper() in textos


def test_titulo_traz_materializacao_e_janela(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """**Anti-SPEC §10.2.7:** a materialização é sempre rotulada, e a janela vem junto."""
    figura = figura_sintetica(dados, colunas)
    texto = " ".join(textos_da_figura(figura))
    assert "materializacao revised" in texto
    assert "2006Q1-2026Q3" in texto
    assert f"{len(H.ORDEM_DOS_ATIVOS)} ativos x {len(colunas)} regimes" in texto


def test_nenhum_texto_da_figura_e_preditivo(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """**Anti-SPEC §10.2.10:** nada de projeção, em texto nenhum da figura."""
    figura = figura_sintetica(dados, colunas)
    corpo = " ".join(todos_os_textos(figura)).lower()
    for proibido in H.VOCABULARIO_PREDITIVO:
        assert proibido not in corpo, proibido
    assert "leitura descritiva" in corpo


def test_vista_sem_linha_nos_dados_falha(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Pedir uma vista que não está nos dados é erro, nunca uma figura vazia."""
    with pytest.raises(SerieInconsistente, match="nenhuma linha da vista"):
        H.desenhar(
            dados,
            vista=H.VISTA_ASOF,
            colunas=colunas,
            extremo=0.09,
            janela=("2006Q1", "2026Q3"),
            versao="a" * 64,
            hashes_dos_insumos={},
            congelada=False,
        )


# ═════════════════════════════════════════════════════════════════════════════
# 5 — O rodapé (CA-097)
# ═════════════════════════════════════════════════════════════════════════════


def test_rodape_lista_data_inicio_de_cada_serie(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """**CA-097 literal:** `data_inicio` de **cada** uma das 24 séries está no rodapé."""
    figura = figura_sintetica(dados, colunas)
    rodape = " ".join(textos_da_figura(figura))
    inicios = H.inicio_das_series(dados)
    assert len(inicios) == len(H.ORDEM_DOS_ATIVOS)
    for ativo, data in inicios.items():
        assert f"{ativo} {data}" in rodape


def test_rodape_nomeia_a_metrica_explicitamente(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """**CA-097:** "excesso sobre CDI médio trimestral", escrito, com a fórmula e o ADR."""
    figura = figura_sintetica(dados, colunas)
    rodape = " ".join(textos_da_figura(figura))
    assert H.NOME_DA_METRICA in rodape
    assert "(1+r_ativo)/(1+r_cdi)-1" in rodape
    assert "ADR-002" in rodape
    assert "CA-069" in rodape


def test_rodape_declara_os_limiares_de_n(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """A legenda visual não basta: os limiares de RF-040 estão escritos."""
    figura = figura_sintetica(dados, colunas)
    rodape = " ".join(textos_da_figura(figura))
    assert "ALERTA_N_BAIXO" in rodape
    assert f"n < {N_ALERTA}" in rodape
    assert f"n < {N_SUPRESSAO}" in rodape
    assert "CA-109" in rodape


def test_rodape_declara_o_erro_padrao(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Com `n` de 3 a 19, a ordem do topo não é distinguível de ruído — e a figura diz isso."""
    figura = figura_sintetica(dados, colunas)
    rodape = " ".join(textos_da_figura(figura))
    assert "erro-padrao da media" in rodape
    assert "ruido" in rodape


def test_rodape_traz_versao_build_e_hash_dos_insumos(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Procedência no pé: o hash do código e o de cada insumo lido (RF-047/CA-121)."""
    figura = figura_sintetica(dados, colunas)
    rodape = " ".join(textos_da_figura(figura))
    assert "versao_build " + "a" * 12 in rodape
    assert "regime_asset_metrics.parquet " + "c" * 12 in rodape
    assert FONTE_VERSAO_SINTETICA[:12] in rodape


def test_rodape_declara_a_mistura_de_moeda(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """`SP500_USD` é retorno em USD contra CDI em BRL — declarado, não escondido nem apagado."""
    figura = figura_sintetica(dados, colunas)
    rodape = " ".join(textos_da_figura(figura))
    for ativo in H.ATIVOS_FORA_DA_MOEDA:
        assert ativo in rodape
    assert "mistura moedas" in rodape


def test_rodape_da_vista_asof_repete_o_achado_de_ca_074() -> None:
    """CA-074 não some da figura: a V1 `asof` troca de rótulo em 1/3 dos trimestres."""
    assert "33,33%" in H.VISTA_ASOF.ressalva
    assert "CA-074" in H.VISTA_ASOF.ressalva


# ═════════════════════════════════════════════════════════════════════════════
# 6 — CA-090: o gate de publicação na figura
# ═════════════════════════════════════════════════════════════════════════════


def test_marca_do_gate_aparece_quando_a_especificacao_nao_esta_congelada(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """**CA-090:** `especificacao_congelada=False` ⇒ a figura diz que não é publicável."""
    textos = textos_da_figura(figura_sintetica(dados, colunas, congelada=False))
    assert _comum.MARCA_NAO_CONGELADA in textos
    assert textos.count(_comum.MARCA_NAO_CONGELADA) == 2  # rodapé + marca d'água diagonal


def test_sem_a_marca_quando_o_adr_esta_aceito(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...]
) -> None:
    """Com o ADR-001 aceito a marca some — senão ela seria decoração, não gate."""
    textos = textos_da_figura(figura_sintetica(dados, colunas, congelada=True))
    assert _comum.MARCA_NAO_CONGELADA not in textos


# ═════════════════════════════════════════════════════════════════════════════
# 7 — Determinismo, Parquet e o tooltip do SVG
# ═════════════════════════════════════════════════════════════════════════════


def test_duas_chamadas_com_a_mesma_entrada_dao_o_mesmo_dataframe() -> None:
    """Função pura: nada de relógio, nada de ordenação instável."""
    pd.testing.assert_frame_equal(dados_sinteticos(), dados_sinteticos())


def test_parquet_gravado_e_identico_ao_dataframe_plotado(
    dados: pd.DataFrame, tmp_path: Path
) -> None:
    """**A figura é a leitura; o Parquet é a evidência** — e os dois têm de ser a mesma coisa."""
    destino = H.gravar_dados(dados, raiz=tmp_path)
    assert destino.name == H.NOME_DADOS_PLOTADOS
    pd.testing.assert_frame_equal(dados.reset_index(drop=True), pd.read_parquet(destino))


def test_parquet_de_duas_rodadas_tem_os_mesmos_bytes(tmp_path: Path) -> None:
    """Idempotência por hash (`AGENTS.md §15.6`): 2 rodadas, mesmo arquivo byte a byte."""
    primeiro = H.gravar_dados(dados_sinteticos(), raiz=tmp_path).read_bytes()
    segundo = H.gravar_dados(dados_sinteticos(), raiz=tmp_path).read_bytes()
    assert primeiro == segundo


def test_figura_gravada_em_png_e_svg_e_determinista(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...], tmp_path: Path
) -> None:
    """PNG e SVG saem byte-idênticos em rodadas distintas: nenhum metadado sai do relógio."""
    tooltips = dict(zip(dados["gid"], dados["tooltip"], strict=True))
    impressoes: list[dict[str, bytes]] = []
    for _ in range(2):
        figura = figura_sintetica(dados, colunas)
        caminhos = H.gravar_figura(
            figura, vista=H.VISTA_PRINCIPAL, versao="a" * 64, tooltips=tooltips, raiz=tmp_path
        )
        assert set(caminhos) == set(_comum.FORMATOS)
        impressoes.append({f: c.read_bytes() for f, c in caminhos.items()})
    for formato in _comum.FORMATOS:
        assert impressoes[0][formato] == impressoes[1][formato], f"{formato} nao e determinista"


def test_svg_gravado_nao_carrega_data(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...], tmp_path: Path
) -> None:
    """Sem `<dc:date>` no SVG: data embutida faria o arquivo mudar sem o dado mudar."""
    figura = figura_sintetica(dados, colunas)
    caminhos = H.gravar_figura(figura, vista=H.VISTA_PRINCIPAL, versao="a" * 64, raiz=tmp_path)
    assert "<dc:date>" not in caminhos["svg"].read_text(encoding="utf-8")


def test_svg_ganha_um_tooltip_por_celula_com_erro_padrao(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...], tmp_path: Path
) -> None:
    """O `<title>` do SVG carrega o que não cabe na célula — e existe para **toda** célula."""
    tooltips = dict(zip(dados["gid"], dados["tooltip"], strict=True))
    figura = figura_sintetica(dados, colunas)
    caminhos = H.gravar_figura(
        figura, vista=H.VISTA_PRINCIPAL, versao="a" * 64, tooltips=tooltips, raiz=tmp_path
    )
    corpo = caminhos["svg"].read_text(encoding="utf-8")
    # +1: o `<title>` do próprio documento, que o metadado `Title` de `savefig` escreve.
    assert corpo.count("<title>") == len(dados) + 1
    assert "erro-padrao da media" in corpo
    assert "hit_ratio_cdi" in corpo
    assert all(_comum.escapar_xml(t) in corpo for t in dados["tooltip"])
    suprimida = celula(dados, "IFIX", REGIME_V3_SINTETICO)
    assert "CONCLUSAO SUPRIMIDA" in suprimida["tooltip"]


def test_tooltip_escapa_xml(tmp_path: Path) -> None:
    """Texto com `<`/`&` não pode quebrar o SVG — é string injetada em documento XML."""
    alvo = tmp_path / "x.svg"
    alvo.write_text('<svg><g id="celula-A-V1-X"><path/></g></svg>', encoding="utf-8")
    assert _comum.injetar_tooltips_svg(alvo, {"celula-A-V1-X": "a < b & c"}) == 1
    assert "<title>a &lt; b &amp; c</title>" in alvo.read_text(encoding="utf-8")


def test_nomes_dos_arquivos_por_vista(
    dados: pd.DataFrame, colunas: tuple[H.ColunaDoHeatmap, ...], tmp_path: Path
) -> None:
    """As três vistas nunca se sobrescrevem: o nome do arquivo carrega o slug."""
    figura = figura_sintetica(dados, colunas)
    nomes = set()
    for slug in H.VISTAS:
        caminhos = H.gravar_figura(figura, vista=H.VISTAS[slug], versao="a" * 64, raiz=tmp_path)
        nomes |= {c.name for c in caminhos.values()}
    assert nomes == {
        f"heatmap_{slug}.{formato}" for slug in H.VISTAS for formato in _comum.FORMATOS
    }
    assert set(H.VISTAS) == {"v1_revised", "v1_asof", "v3_t1"}


# ═════════════════════════════════════════════════════════════════════════════
# 8 — Acervo real `data/canonical/` (padrão `Acervo`; desligado por LDC_IGNORAR_DATA=1)
# ═════════════════════════════════════════════════════════════════════════════

N_ATIVOS_REAIS = 24
N_COLUNAS_PRINCIPAL = 5
N_SUPRIMIDAS_PRINCIPAL = 2  # IFIX e IMOB na V3, n = 4 (F-022 §7.1)
N_ALERTA_PRINCIPAL = 1  # ICON na V3, n = 6


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
    """Os Parquets que a figura lê existem nesta máquina?"""
    alvos = [v.tabela.nome_arquivo for v in H.VISTAS.values()] + [
        "regimes_v1.parquet",
        "regimes_v1_asof.parquet",
    ]
    return all(caminho_canonical(nome).is_file() for nome in alvos)


acervo_real = pytest.mark.skipif(
    ignorar_data_real() or not canonical_disponivel(),
    reason=f"data/canonical/ ausente ou {VAR_IGNORAR_DATA} ligada — {COMO_GERAR}",
)


@pytest.fixture(scope="module")
def resultado_real():  # noqa: ANN201 - ResultadoHeatmap
    """O heatmap recalculado do acervo real, **sem gravar** (o teste não mexe em `data/`)."""
    if ignorar_data_real() or not canonical_disponivel():
        pytest.skip("acervo real indisponível")
    return H.construir(gravar=False)


@acervo_real
def test_acervo_vista_principal_e_24_por_5(resultado_real) -> None:  # noqa: ANN001
    """**CA-095 no dado real:** 24 ativos × (4 quadrantes V1 + 1 coluna V3) = 120 células."""
    bloco = resultado_real.dados[resultado_real.dados["vista"] == H.VISTA_PRINCIPAL.slug]
    assert bloco["asset_id"].nunique() == N_ATIVOS_REAIS
    assert bloco["coluna"].nunique() == N_COLUNAS_PRINCIPAL
    assert len(bloco) == N_ATIVOS_REAIS * N_COLUNAS_PRINCIPAL
    assert bloco["n_obs"].notna().all()


@acervo_real
def test_acervo_valores_sao_identicos_aos_de_regime_asset_metrics(resultado_real) -> None:  # noqa: ANN001
    """Célula a célula, o valor plotado **é** o de F-022 — nenhuma transformação pelo caminho."""
    for vista in H.VISTAS.values():
        origem = pd.read_parquet(caminho_canonical(vista.tabela.nome_arquivo)).set_index(
            ["lente", "regime", "asset_id"]
        )
        bloco = resultado_real.dados[resultado_real.dados["vista"] == vista.slug]
        assert len(bloco) == len(H.ORDEM_DOS_ATIVOS) * bloco["coluna"].nunique()
        for linha in bloco.itertuples():
            chave = (linha.lente, linha.regime, linha.asset_id)
            assert linha.excesso_cdi == pytest.approx(
                float(origem.loc[chave, "excesso_cdi"]), abs=0.0, rel=0.0
            )
            assert int(linha.n_obs) == int(origem.loc[chave, "n_obs"])


@acervo_real
def test_acervo_colunas_sao_os_4_quadrantes_mais_a_v3(resultado_real) -> None:  # noqa: ANN001
    """A coluna da V3 é a dos **vizinhos de 2026Q3**, e vem depois dos 4 quadrantes."""
    bloco = resultado_real.dados[resultado_real.dados["vista"] == H.VISTA_PRINCIPAL.slug]
    por_coluna = bloco.sort_values("coluna").drop_duplicates("coluna")
    assert list(por_coluna["regime"])[:4] == [r.value for r in RegimeV1]
    assert list(por_coluna["lente"]) == [H.LENTE_V1] * 4 + [H.LENTE_V3]
    assert list(por_coluna["regime"])[4].startswith("VIZINHOS_")
    assert list(por_coluna["horizonte"]) == ["T0"] * 4 + ["T+1"]


@acervo_real
def test_acervo_n_por_coluna_reproduz_a_distribuicao_de_f019(resultado_real) -> None:  # noqa: ANN001
    """DES 13 · EST 16 · EXP 19 · REC 19 — a cadeia F-019 → F-022 → figura fecha."""
    bloco = resultado_real.dados[resultado_real.dados["vista"] == H.VISTA_PRINCIPAL.slug]
    maximos = bloco.groupby("regime")["n_obs"].max().to_dict()
    assert maximos[RegimeV1.DESACELERACAO.value] == 13
    assert maximos[RegimeV1.ESTAGFLACAO.value] == 16
    assert maximos[RegimeV1.EXPANSAO_INFL.value] == 19
    assert maximos[RegimeV1.RECUPERACAO.value] == 19


@acervo_real
def test_acervo_flags_sao_as_3_celulas_de_f022(resultado_real) -> None:  # noqa: ANN001
    """3 células com `alerta_n_baixo` e 2 com `conclusao_suprimida` — os mesmos de F-021/F-022."""
    bloco = resultado_real.dados[resultado_real.dados["vista"] == H.VISTA_PRINCIPAL.slug]
    flags = H.contagem_de_flags(bloco)
    assert flags["conclusao_suprimida"] == N_SUPRIMIDAS_PRINCIPAL
    assert flags["alerta_n_baixo"] == N_ALERTA_PRINCIPAL
    suprimidas = bloco[bloco["conclusao_suprimida"]]
    assert set(suprimidas["asset_id"]) == {"IFIX", "IMOB"}
    assert set(suprimidas["lente"]) == {H.LENTE_V3}
    assert (suprimidas["cor_hex"] == _comum.CINZA_SUPRIMIDO).all()


@acervo_real
def test_acervo_linha_do_cdi_e_zero_em_toda_coluna(resultado_real) -> None:  # noqa: ANN001
    """O *sanity check* da métrica no dado real: `|excesso_cdi| < 1e-9` nas 14 células do CDI."""
    cdi = resultado_real.dados[resultado_real.dados["asset_id"] == "CDI"]
    assert len(cdi) > 0
    assert cdi["excesso_cdi"].abs().max() < 1e-9


@acervo_real
def test_acervo_gate_fechado_e_marca_na_figura(resultado_real) -> None:  # noqa: ANN001
    """**CA-090:** com ADR-001 em `Proposta`, nenhuma das 3 figuras nasce publicável."""
    espec = resultado_real.relatorio["especificacao"]
    assert espec["especificacao_congelada"] is False
    assert espec["marca_na_figura"] == _comum.MARCA_NAO_CONGELADA
    for figura in resultado_real.figuras.values():
        assert _comum.MARCA_NAO_CONGELADA in [t.get_text() for t in figura.texts]


@acervo_real
def test_acervo_tres_vistas_com_as_tabelas_certas(resultado_real) -> None:  # noqa: ANN001
    """Cada vista lê **a sua** tabela de F-022 — trocar a fonte mudaria o número em silêncio."""
    por_vista = resultado_real.relatorio["por_vista"]
    assert set(por_vista) == set(H.VISTAS)
    assert por_vista["v1_revised"]["tabela"] == "regime_asset_metrics.parquet"
    assert por_vista["v1_asof"]["tabela"] == "regime_asset_metrics_asof.parquet"
    assert por_vista["v3_t1"]["tabela"] == "regime_asset_metrics_horizonte_cruzado.parquet"
    assert por_vista["v1_asof"]["materializacao"] == "asof"
    assert len(por_vista["v1_asof"]["colunas"]) == 4


@acervo_real
def test_acervo_janela_e_a_dos_83_trimestres(resultado_real) -> None:  # noqa: ANN001
    """A janela do escopo (2006Q1→2026Q3) vem de `regimes_v1`, não de um literal da figura."""
    for bloco in resultado_real.relatorio["por_vista"].values():
        assert bloco["janela"] == ["2006Q1", "2026Q3"]


@acervo_real
def test_acervo_data_inicio_bate_com_regime_asset_metrics(resultado_real) -> None:  # noqa: ANN001
    """**CA-097:** o `data_inicio` do rodapé é o da tabela, série por série."""
    origem = pd.read_parquet(caminho_canonical("regime_asset_metrics.parquet"))
    esperado = {
        str(a): str(pd.Timestamp(d).date())
        for a, d in origem.groupby("asset_id")["data_inicio_serie"].first().items()
    }
    obtido = H.inicio_das_series(resultado_real.dados)
    assert obtido == {a: esperado[a] for a in H.ORDEM_DOS_ATIVOS}


@acervo_real
def test_acervo_artefatos_em_disco_batem_com_o_recalculo(resultado_real) -> None:  # noqa: ANN001
    """O Parquet gravado em `data/canonical/figuras/` é o mesmo que esta rodada recalcula."""
    alvo = _comum.caminho_figuras() / H.NOME_DADOS_PLOTADOS
    if not alvo.is_file():
        pytest.skip(f"{alvo.name} ainda não materializado — {COMO_GERAR}")
    pd.testing.assert_frame_equal(
        pd.read_parquet(alvo).reset_index(drop=True),
        resultado_real.dados.reset_index(drop=True),
    )
