"""F-017 — retornos trimestrais: razão de níveis, CDI acumulado, excesso e real. **Classe C.**

Cinco seções, com fontes de verdade diferentes de propósito:

- **A — aritmética**, sobre números **conhecidos à mão** (`100 → 110`, `r=0,10` e `cdi=0,0325`,
  três taxas diárias de valor fechado). É onde CA-069 (razão, não subtração), CA-070
  (geométrico, não soma), CA-071 (IPCA uma vez só) e CA-016 (o `/100`) têm os seus testes
  **negativos**: cada um afirma que o jeito errado dá um número diferente, e qual.
- **B — CDI e IPCA trimestrais sobre dado REAL versionado**: a fixture `sgs/12__…__2006.json`
  (os 249 dias úteis de 2006) e os recortes de `tests/fixtures/processed/`. Reproduz o
  valor-canário **CDI 2006 = 15,0271 %** (CA-014), o encadeamento dos 4 trimestres (CA-015) e o
  retorno do **IBOV em 2T2006** com excesso e real — tudo sem `data/` e sem rede.
- **C — painel desbalanceado e o 1º trimestre** (CA-062, CA-063): série que começa no meio, ativo
  fora do contrato, universo incompleto.
- **D — o build de ponta a ponta** em `tmp_path`, com o universo **inteiro** em série sintética
  nomeada (o schema exige >= 18 `asset_id`), inclusive idempotência por `sha256`.
- **E — o acervo real** de `data/canonical/`, por acréscimo: é onde está o **diff numérico da
  classe C** (`test_acervo_ret_tri_e_exatamente_a_razao_dos_niveis_do_alinhado`), recalculado a
  partir de `alinhado_trimestral` sem passar pelo módulo. `LDC_IGNORAR_DATA=1` desliga a seção.

Dado sintético existe **só** nas seções A, C e D, e é nomeado como tal (Anti-SPEC §10.1.2).
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from apps.pipeline.canonical.alinhamento import (
    NOME_ALINHADO,
    alinhar_series,
    grade_de_trimestres,
)
from apps.pipeline.canonical.alinhamento import (
    construir as construir_alinhado,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    materializar_catalogo,
)
from apps.pipeline.canonical.retornos import (
    DERIVADAS_ALINHADAS_AQUI,
    MODULOS_DOS_RETORNOS,
    NOME_RELATORIO,
    NOME_RETORNOS,
    SERIE_CDI,
    SERIE_CDI_CONFERENCIA,
    SERIE_IPCA,
    UNIVERSO,
    AtivoForaDoContrato,
    Metodo,
    MotivoNulo,
    UnidadeInesperada,
    UniversoIncompleto,
    acumular_taxa_diaria,
    cdi_trimestral,
    construir,
    excesso_por_razao,
    exigir_universo,
    ipca_trimestral,
    is_total_return_declarado,
    metricas_intra_trimestre,
    razao_de_niveis,
    versao_build,
)
from apps.pipeline.canonical.retornos import (
    Ativo as AtivoDoUniverso,
)
from apps.pipeline.common.errors import FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import Camada, caminho_camada, caminho_canonical, sha256_de
from apps.pipeline.extract.bcb_sgs import quadro_de_observacoes
from apps.pipeline.extract.calendario_anbima import Calendario, parse_feriados_do_ano
from packages.shared.schemas import (
    ASSET_IDS_VALIDOS,
    N_MINIMO_ATIVOS,
    AssetReturnsQuarterlySchema,
    load_catalog,
)

RAIZ_TESTES = Path(__file__).resolve().parents[1]
FIXTURES_FERIADOS = RAIZ_TESTES / "fixtures" / "anbima-feriados"
FIXTURES_PROCESSED = RAIZ_TESTES / "fixtures" / "processed"
FIXTURES_SGS = RAIZ_TESTES / "fixtures" / "sgs"
FIXTURE_CDI_2006 = "12__2026-10-10__2006.json"

VAR_IGNORAR_DATA = "LDC_IGNORAR_DATA"
"""Liga o modo "árvore limpa": só os acervos versionados entram, `data/` é ignorado."""

COLUNAS_RAW = ("series_id", "date", "value", "source", "freq", "vintage", "unit", "collected_at")

CATALOGO = {entrada.series_id: entrada for entrada in load_catalog()}

# ── Valores-canário, todos conferidos fora deste arquivo ─────────────────────

CDI_2006_PCT = 15.0271
"""O CDI publicado de 2006 (`fontes-de-dados.md §B7`, SPEC CA-014)."""

IBOV_2006Q1 = 37951.97
IBOV_2006Q2 = 36630.66
"""Fechamentos do IBOV no último dia útil de 1T e 2T de 2006 (`alinhado_trimestral`, F-014 §5.3)."""

IMAB_2006Q4 = 1353.153246
IMAB_2007Q1 = 1422.243664

IFIX_2010Q4 = 1000.00
IFIX_2011Q1 = 1028.25
"""O IFIX nasce em 30/12/2010 na base 1.000 — 2010Q4 é parcial e 2011Q1 é o 1º retorno."""


# ─────────────────────────────────────────────────────────────────────────────
# Infra de fixture
# ─────────────────────────────────────────────────────────────────────────────


def calendario_real_de(*anos: int) -> Calendario:
    """Calendário da ANBIMA reconstruído das páginas HTML **reais** versionadas em fixtures."""
    feriados = []
    for ano in anos:
        paginas = sorted(FIXTURES_FERIADOS.glob(f"{ano}__*.html"))
        assert paginas, f"fixture do ano {ano} ausente em {FIXTURES_FERIADOS}"
        feriados.extend(
            parse_feriados_do_ano(paginas[0].read_bytes(), ano=ano, origem=paginas[0].name)
        )
    return Calendario.de_feriados(feriados, ano_inicio=min(anos), ano_fim=max(anos))


def calendario_sintetico(ano_inicio: int, ano_fim: int) -> Calendario:
    """Calendário **sintético** (sem feriado) — existe para controlar a contagem de dias úteis."""
    return Calendario(
        feriados={},
        cobertura_inicio=date(ano_inicio, 1, 1),
        cobertura_fim=date(ano_fim, 12, 31),
    )


def serie_sintetica(
    series_id: str, pontos: Iterable[tuple[str, float | None]], *, vintage: str = "2026-10-10"
) -> pd.DataFrame:
    """Uma série **sintética** no contrato de `raw_series`, com metadado do catálogo real.

    `source`/`freq`/`unit` vêm da entrada do catálogo para que as guardas públicas de F-013 e a
    trava de unidade de F-017 rodem sobre ela de verdade.
    """
    entrada = CATALOGO[series_id]
    quando = pd.Timestamp(vintage)
    return pd.DataFrame(
        {
            "series_id": series_id,
            "date": [pd.Timestamp(d) for d, _ in pontos],
            "value": [v for _, v in pontos],
            "source": entrada.fonte.value,
            "freq": entrada.freq.value,
            "vintage": quando,
            "unit": entrada.unit.value,
            "collected_at": quando,
        }
    ).loc[:, list(COLUNAS_RAW)]


def cdi_2006_do_bruto() -> pd.DataFrame:
    """A série 12 de 2006 **real**, do JSON bruto versionado, no contrato de `raw_series`.

    Usa o `quadro_de_observacoes` de produção (F-003) em vez de reparsear aqui: o que esta seção
    quer provar é a **acumulação**, não o parse.
    """
    alvo = FIXTURES_SGS / FIXTURE_CDI_2006
    assert alvo.is_file(), f"fixture ausente: {alvo}"
    observacoes = json.loads(alvo.read_text(encoding="utf-8"))
    quadro = quadro_de_observacoes(
        CATALOGO[SERIE_CDI], observacoes, collected_at=pd.Timestamp("2026-10-10")
    )
    return quadro.loc[:, list(COLUNAS_RAW)]


def processed_fixtures(*series_ids: str) -> pd.DataFrame:
    """Os recortes **reais** de `tests/fixtures/processed/` das séries pedidas."""
    pedacos = []
    for caminho in sorted(FIXTURES_PROCESSED.glob("*/*.parquet")):
        quadro = pd.read_parquet(caminho)
        recorte = quadro[quadro["series_id"].isin(series_ids)]
        if len(recorte):
            pedacos.append(recorte)
    assert pedacos, f"nenhum recorte versionado para {series_ids}"
    return pd.concat(pedacos, ignore_index=True).loc[:, list(COLUNAS_RAW)]


def inicio_de(raw: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """`{series_id: min(date)}` — o início observado, como o catálogo materializado o mede."""
    return {str(k): pd.Timestamp(v) for k, v in raw.groupby("series_id")["date"].min().items()}


def alinhar(raw: pd.DataFrame, *, calendario: Calendario, quarters: Sequence[str]) -> pd.DataFrame:
    """Atalho: alinha `raw` nos `quarters` pedidos, com o início medido no próprio dado."""
    return alinhar_series(
        raw,
        calendario=calendario,
        inicio_por_serie=inicio_de(raw),
        trimestres=grade_de_trimestres(calendario, quarters=quarters),
        fonte_versao="f" * 64,
    )


def linha(tabela: pd.DataFrame, asset_id: str, quarter: str) -> pd.Series:
    """A única linha de `(asset_id, quarter)` — levanta se houver zero ou duas."""
    recorte = tabela[(tabela["asset_id"] == asset_id) & (tabela["quarter"] == quarter)]
    assert len(recorte) == 1, f"{asset_id} {quarter}: {len(recorte)} linha(s)"
    return recorte.iloc[0]


# ═════════════════════════════════════════════════════════════════════════════
# A — aritmética sobre números conhecidos à mão
# ═════════════════════════════════════════════════════════════════════════════


def test_ret_tri_e_a_razao_de_dois_niveis_conhecidos() -> None:
    """`100 → 110` é 10 % exato; e o par real do IBOV em 2T2006 bate com a divisão à mão."""
    assert razao_de_niveis(110.0, 100.0) == pytest.approx(0.10, abs=1e-15)
    assert razao_de_niveis(IBOV_2006Q2, IBOV_2006Q1) == IBOV_2006Q2 / IBOV_2006Q1 - 1
    assert razao_de_niveis(IMAB_2007Q1, IMAB_2006Q4) == pytest.approx(0.05105882737, abs=1e-10)
    assert razao_de_niveis(IFIX_2011Q1, IFIX_2010Q4) == pytest.approx(0.02825, abs=1e-12)


def test_ret_tri_com_ponta_ausente_e_nulo_e_nunca_zero() -> None:
    """Anti-SPEC §10.1.4: nível ausente em qualquer ponta ⇒ `None`, não `0` nem `P/P`."""
    assert razao_de_niveis(110.0, None) is None
    assert razao_de_niveis(None, 100.0) is None
    assert razao_de_niveis(None, None) is None


def test_nivel_inicial_nao_positivo_levanta_em_vez_de_devolver_infinito() -> None:
    """`P_ini = 0` devolveria `inf`; `P_ini < 0`, retorno de sinal invertido. Os dois param."""
    for base in (0.0, -1.0):
        with pytest.raises(SerieInconsistente):
            razao_de_niveis(110.0, base)


def test_ca069_excesso_sobre_cdi_e_por_razao() -> None:
    """**CA-069.** `r=0,10` e `cdi=0,0325` ⇒ `(1,10/1,0325)−1`, o número da SPEC."""
    excesso = excesso_por_razao(0.10, 0.0325)
    assert excesso is not None
    assert excesso == pytest.approx(1.10 / 1.0325 - 1.0, abs=1e-15)
    assert excesso == pytest.approx(0.0653753, abs=1e-7)


def test_ca069_negativo_a_subtracao_da_um_numero_diferente() -> None:
    """**Teste negativo de CA-069.** `r − cdi = 0,0675` ≠ `0,06537…` — 0,21 pp de viés.

    O teste existe para falhar se alguém trocar a razão pela subtração: a diferença não é
    arredondamento (Anti-SPEC §10.2.13).
    """
    por_razao = excesso_por_razao(0.10, 0.0325)
    por_subtracao = 0.10 - 0.0325
    assert por_subtracao == pytest.approx(0.0675, abs=1e-15)
    assert por_razao is not None
    assert por_razao != por_subtracao
    assert abs(por_razao - por_subtracao) == pytest.approx(0.0021247, abs=1e-6)


def test_excesso_e_deflacao_sao_a_mesma_funcao_com_bases_diferentes() -> None:
    """Uma fórmula, dois usos: não há caminho em que só uma das duas vire subtração."""
    assert excesso_por_razao(0.10, 0.0325) == excesso_por_razao(0.10, 0.0325)
    assert excesso_por_razao(0.08, 0.02) == pytest.approx(1.08 / 1.02 - 1.0, abs=1e-15)


def test_ca071_ret_real_deflaciona_pelo_ipca_do_trimestre() -> None:
    """**CA-071.** `r=0,08` com `ipca_tri=0,02` ⇒ `(1,08/1,02)−1 = 0,058823…`."""
    real = excesso_por_razao(0.08, 0.02)
    assert real == pytest.approx(0.05882352941176472, abs=1e-15)


def test_ca071_negativo_dupla_deflacao_da_um_numero_diferente() -> None:
    """**Teste negativo de CA-071.** Aplicar o IPCA duas vezes muda o número — e muito.

    `((1+r)/(1+pi))/(1+pi) − 1` é o erro clássico de deflacionar um retorno já real. Com
    `pi = 2 %` o viés é de ~1,9 pp em um trimestre.
    """
    uma_vez = excesso_por_razao(0.08, 0.02)
    duas_vezes = excesso_por_razao(uma_vez, 0.02)
    assert uma_vez is not None and duas_vezes is not None
    assert uma_vez != duas_vezes
    assert abs(uma_vez - duas_vezes) == pytest.approx(0.0207, abs=1e-3)


def test_base_de_excesso_de_menos_cem_por_cento_levanta() -> None:
    """`1 + base <= 0` não é deflator — é divisão por zero disfarçada."""
    for base in (-1.0, -1.5):
        with pytest.raises(SerieInconsistente):
            excesso_por_razao(0.10, base)


def test_excesso_com_base_ausente_e_nulo() -> None:
    """Sem CDI (ou sem IPCA) do trimestre não há excesso: `None`, nunca o retorno nominal."""
    assert excesso_por_razao(0.10, None) is None
    assert excesso_por_razao(None, 0.03) is None


def test_ca070_acumulacao_de_tres_taxas_diarias_conhecidas_e_geometrica() -> None:
    """**CA-070 + CA-016.** `0,1 % · 0,2 % · 0,3 %` acumulam `1,001·1,002·1,003 − 1`.

    O resultado é `0,006011006` — a **soma** daria `0,006` exato. A diferença de 1,1e-5 num
    trimestre de 3 dias vira pontos percentuais em 83 trimestres encadeados.
    """
    taxas = [0.1, 0.2, 0.3]
    acumulado = acumular_taxa_diaria(taxas)
    assert acumulado == pytest.approx(1.001 * 1.002 * 1.003 - 1.0, abs=1e-15)
    assert acumulado == pytest.approx(0.006011006, abs=1e-12)
    soma = sum(t / 100 for t in taxas)
    assert soma == pytest.approx(0.006, abs=1e-15)
    assert acumulado != soma


def test_ca016_negativo_esquecer_o_dividir_por_100_da_numero_absurdo() -> None:
    """**Teste negativo de CA-016.** A série 12 é percentual: sem o `/100`, 2006 explode.

    Com as 249 taxas reais de 2006, `prod(1+v)` passa de `1e5`; `prod(1+v/100)` dá 1,15. Este
    teste é o que torna impossível "arrumar" a escala e continuar verde.
    """
    taxas = [float(v) for v in cdi_2006_do_bruto()["value"]]
    certo = acumular_taxa_diaria(taxas)
    errado = math.prod(1.0 + v for v in taxas) - 1.0
    assert certo == pytest.approx(CDI_2006_PCT / 100, abs=1e-6)
    assert errado > 1e5
    assert errado / (1 + certo) > 1e5


def test_metricas_intra_trimestre_de_caminho_conhecido() -> None:
    """`vol` é desvio amostral × `sqrt(n)`; `dd` é a pior queda contra o pico até ali.

    Caminho `100 → 110 → 99 → 110`: retornos diários `+10 %`, `−10 %`, `+11,11…%`; o pico é 110
    e o fundo 99, então `dd = 99/110 − 1 = −10 %` exato.
    """
    vol, queda = metricas_intra_trimestre([110.0, 99.0, 110.0], preco_inicial=100.0)
    assert queda == pytest.approx(-0.10, abs=1e-15)
    retornos = [0.10, -0.10, 110.0 / 99.0 - 1.0]
    media = sum(retornos) / 3
    esperado = math.sqrt(sum((r - media) ** 2 for r in retornos) / 2) * math.sqrt(3)
    assert vol == pytest.approx(esperado, abs=1e-15)


def test_drawdown_de_caminho_so_de_alta_e_zero_e_nunca_positivo() -> None:
    """`dd_intra_tri <= 0` por contrato: trimestre só de alta tem queda **medida** de 0."""
    vol, queda = metricas_intra_trimestre([101.0, 102.0, 103.0], preco_inicial=100.0)
    assert queda == 0.0
    assert vol is not None and vol >= 0


def test_vol_exige_dois_retornos_diarios_e_nao_vira_zero() -> None:
    """Com 1 retorno o desvio amostral não existe: `None`, nunca `0` (que diria "sem risco")."""
    vol, queda = metricas_intra_trimestre([110.0], preco_inicial=100.0)
    assert vol is None
    assert queda == 0.0


def test_caminho_diario_vazio_nao_tem_metrica_intra() -> None:
    """Sem caminho não há desvio nem drawdown — e nenhum dos dois é 0."""
    assert metricas_intra_trimestre([], preco_inicial=100.0) == (None, None)


# ═════════════════════════════════════════════════════════════════════════════
# B — CDI e IPCA trimestrais sobre dado REAL versionado (roda sempre no CI)
# ═════════════════════════════════════════════════════════════════════════════

QUARTERS_2006 = ("2006Q1", "2006Q2", "2006Q3", "2006Q4")


@pytest.fixture(scope="module")
def calendario_2006() -> Calendario:
    """O calendário real de 2006, da página de feriados da ANBIMA versionada."""
    return calendario_real_de(2006)


@pytest.fixture(scope="module")
def trimestres_2006(calendario_2006: Calendario) -> tuple[Any, ...]:
    return grade_de_trimestres(calendario_2006, quarters=QUARTERS_2006)


@pytest.fixture(scope="module")
def cdi_de_2006(trimestres_2006: tuple[Any, ...]) -> dict[str, dict[str, Any]]:
    return cdi_trimestral(cdi_2006_do_bruto(), trimestres_2006)


def test_ca014_cdi_2006_acumulado_e_15_0271_pct() -> None:
    """**CA-014.** Os 249 dias úteis de 2006 acumulam **15,0271 %** — o valor-canário."""
    taxas = [float(v) for v in cdi_2006_do_bruto()["value"]]
    assert len(taxas) == 249, "2006 tem 249 dias úteis na série 12"
    assert acumular_taxa_diaria(taxas) * 100 == pytest.approx(CDI_2006_PCT, abs=1e-4)


def test_ca015_os_quatro_trimestres_de_2006_encadeiam_no_fator_anual(
    cdi_de_2006: dict[str, dict[str, Any]],
) -> None:
    """**CA-015 + o canário pedido pelo Feature Contract.** 63+61+64+61 = 249 dias úteis.

    O produto dos 4 fatores trimestrais reproduz o fator anual com erro de ponto flutuante
    (<= 1e-9) **e** reproduz os 15,0271 % publicados. É o que prova que a janela trimestral não
    perde nem repete dia — o erro que faz um retorno trimestral parecer plausível e estar errado.
    """
    por_trimestre = [cdi_de_2006[q] for q in QUARTERS_2006]
    assert [b["n_dias_uteis"] for b in por_trimestre] == [63, 61, 64, 61]
    assert sum(b["n_dias_uteis"] for b in por_trimestre) == 249

    encadeado = 1.0
    for bloco in por_trimestre:
        encadeado *= 1.0 + bloco["cdi_tri"]
    anual = 1.0 + acumular_taxa_diaria([float(v) for v in cdi_2006_do_bruto()["value"]])
    assert encadeado == pytest.approx(anual, abs=1e-9)
    assert (encadeado - 1.0) * 100 == pytest.approx(CDI_2006_PCT, abs=1e-4)


def test_cdi_trimestral_nunca_usa_taxa_publicada_depois_do_fim_do_trimestre(
    calendario_2006: Calendario, cdi_de_2006: dict[str, dict[str, Any]]
) -> None:
    """Anti-SPEC §10.2.7 na janela do CDI: a última taxa de `T` não passa de `quarter_end(T)`."""
    for tri in grade_de_trimestres(calendario_2006, quarters=QUARTERS_2006):
        bloco = cdi_de_2006[tri.quarter]
        assert bloco["ultima"] <= pd.Timestamp(tri.quarter_end), tri.quarter
        assert str(bloco["primeira"].to_period("Q")) == tri.quarter


def test_cdi_com_unidade_diferente_de_pct_dia_para_o_build(
    trimestres_2006: tuple[Any, ...],
) -> None:
    """A trava de escala: série de CDI em `% a.a.` não é acumulável por `prod(1+v/100)`.

    É o caso real de confundir a série **12** (`%/dia`) com a **4389** (`% a.a.` base 252) — o
    build para em vez de produzir um CDI absurdo que passaria pelo schema.
    """
    quadro = cdi_2006_do_bruto().assign(unit="%a.a.")
    with pytest.raises(UnidadeInesperada) as erro:
        cdi_trimestral(quadro, trimestres_2006)
    assert SERIE_CDI in str(erro.value)


def test_cdi_trimestral_sem_a_serie_bloqueia(trimestres_2006: tuple[Any, ...]) -> None:
    """Sem CDI não há métrica primária do heatmap (ADR-002/D5): `BLOQUEADO`, não coluna nula."""
    vazio = cdi_2006_do_bruto().iloc[0:0]
    with pytest.raises(FonteIndisponivel):
        cdi_trimestral(vazio, trimestres_2006)


def test_ipca_trimestral_acumula_os_tres_meses_reais_de_2t2006(
    trimestres_2006: tuple[Any, ...],
) -> None:
    """IPCA de abr/mai/jun de 2006 (`0,21 · 0,10 · −0,21`), do recorte real do SGS 433."""
    ipca = ipca_trimestral(processed_fixtures(SERIE_IPCA), trimestres_2006)
    bloco = ipca["2006Q2"]
    assert bloco["n_meses"] == 3
    assert bloco["ipca_tri"] == pytest.approx(1.0021 * 1.0010 * 0.9979 - 1.0, abs=1e-15)


def test_ipca_trimestral_com_menos_de_tres_meses_e_nulo(
    calendario_2006: Calendario,
) -> None:
    """Deflacionar por 2 meses seria inventar número plausível: `None` (CA-071/§10.1.1)."""
    parcial = serie_sintetica(SERIE_IPCA, [("2006-01-31", 0.59), ("2006-02-28", 0.41)])
    ipca = ipca_trimestral(parcial, grade_de_trimestres(calendario_2006, quarters=["2006Q1"]))
    assert ipca["2006Q1"] == {"ipca_tri": None, "n_meses": 2}


def test_canario_ibov_2t2006_com_excesso_e_real_de_fixture_versionada(
    calendario_2006: Calendario,
    trimestres_2006: tuple[Any, ...],
    cdi_de_2006: dict[str, dict[str, Any]],
) -> None:
    """O canário completo do 2T2006, **só** com dado real versionado — roda no CI sem `data/`.

    `36.630,66 / 37.951,97 − 1 = −3,4815 %`; com o CDI do trimestre (3,5775 %) o excesso por
    razão é **−6,8152 %**, e a **subtração** daria −7,0590 % — 0,24 pp de viés em **um**
    trimestre. O retorno real usa o IPCA de abr/mai/jun do mesmo trimestre.
    """
    raw = processed_fixtures("B3_IBOV", SERIE_IPCA)
    niveis = alinhar(raw, calendario=calendario_2006, quarters=QUARTERS_2006)
    ibov = niveis[niveis["series_id"] == "B3_IBOV"].set_index("quarter")
    assert ibov.loc["2006Q1", "value"] == IBOV_2006Q1
    assert ibov.loc["2006Q2", "value"] == IBOV_2006Q2

    ret = razao_de_niveis(ibov.loc["2006Q2", "value"], ibov.loc["2006Q1", "value"])
    assert ret == pytest.approx(-0.0348153205, abs=1e-10)

    cdi_tri = cdi_de_2006["2006Q2"]["cdi_tri"]
    assert cdi_tri == pytest.approx(0.0357746220, abs=1e-10)
    excesso = excesso_por_razao(ret, cdi_tri)
    assert excesso == pytest.approx(-0.0681518364, abs=1e-10)
    assert excesso != pytest.approx(ret - cdi_tri, abs=1e-6)

    ipca_tri = ipca_trimestral(raw, trimestres_2006)["2006Q2"]["ipca_tri"]
    real = excesso_por_razao(ret, ipca_tri)
    assert real == pytest.approx(-0.0357752888, abs=1e-10)


def test_fixture_versionada_do_cdi_de_2006_nao_mudou() -> None:
    """A fixture é a âncora dos canários: se ela mudar, os números de B deixam de significar.

    `sha256` do JSON bruto, medido em 2026-10-11. Não é teste de lógica — é a trava de que o
    valor-canário continua sendo conferido contra o **mesmo** corpo de resposta.
    """
    corpo = (FIXTURES_SGS / FIXTURE_CDI_2006).read_bytes()
    assert len(json.loads(corpo.decode("utf-8"))) == 249
    assert sha256_de(corpo).startswith("01f7a139963b"), sha256_de(corpo)


# ═════════════════════════════════════════════════════════════════════════════
# C — painel desbalanceado, 1º trimestre e guardas de universo
# ═════════════════════════════════════════════════════════════════════════════


def test_universo_com_serie_ausente_bloqueia() -> None:
    """**CA-076.** Série de um ativo do universo sem nível alinhado para o build."""
    cal = calendario_sintetico(2020, 2021)
    raw = serie_sintetica("B3_IBOV", [("2020-12-31", 1.0), ("2021-03-31", 2.0)])
    niveis = alinhar(raw, calendario=cal, quarters=["2020Q4", "2021Q1"])
    with pytest.raises(UniversoIncompleto) as erro:
        exigir_universo(niveis, UNIVERSO)
    assert "BLOQUEADO — FONTE INDISPONÍVEL" in str(erro.value)
    assert "ANBIMA_IMAB" in str(erro.value)


def test_universo_com_asset_id_fora_do_contrato_levanta() -> None:
    """Anti-SPEC §10.4.24: `asset_id` que não está no enum de 32 não entra na tabela."""
    cal = calendario_sintetico(2020, 2021)
    raw = serie_sintetica("B3_IBOV", [("2020-12-31", 1.0), ("2021-03-31", 2.0)])
    niveis = alinhar(raw, calendario=cal, quarters=["2020Q4", "2021Q1"])
    inventado = (AtivoDoUniverso("IBOVESPA_TOTAL", "B3_IBOV", "acoes_b3"),)
    with pytest.raises(AtivoForaDoContrato) as erro:
        exigir_universo(niveis, inventado)
    assert "IBOVESPA_TOTAL" in str(erro.value)


def test_universo_com_asset_id_repetido_levanta() -> None:
    """PK `(quarter, asset_id)`: o mesmo ativo duas vezes viraria linha duplicada."""
    cal = calendario_sintetico(2020, 2021)
    raw = serie_sintetica("B3_IBOV", [("2020-12-31", 1.0), ("2021-03-31", 2.0)])
    niveis = alinhar(raw, calendario=cal, quarters=["2020Q4", "2021Q1"])
    duplicado = (
        AtivoDoUniverso("IBOV", "B3_IBOV", "acoes_b3"),
        AtivoDoUniverso("IBOV", "B3_IBOV", "acoes_b3"),
    )
    with pytest.raises(AtivoForaDoContrato) as erro:
        exigir_universo(niveis, duplicado)
    assert "IBOV" in str(erro.value)


def test_universo_do_modulo_cabe_no_contrato_e_passa_do_minimo() -> None:
    """**CA-062.** Os 23 ativos do universo estão no enum, sem repetição, e >= 18."""
    assert len(UNIVERSO) >= N_MINIMO_ATIVOS
    ids = [a.asset_id for a in UNIVERSO]
    assert len(set(ids)) == len(ids)
    assert set(ids) <= set(ASSET_IDS_VALIDOS)
    assert sum(1 for a in UNIVERSO if a.metodo is Metodo.ACUMULACAO_DE_TAXA_DIARIA) == 1


def test_is_total_return_vem_do_catalogo_e_none_nao_e_false() -> None:
    """**CA-064 / G-01.** Os setoriais da B3 entram `None`; IBOV e IFIX, `True`; GSPC, `False`."""
    bandeiras = is_total_return_declarado()
    assert bandeiras["B3_IBOV"] is True
    assert bandeiras["B3_IFIX"] is True
    assert bandeiras["ANBIMA_IMAB"] is True
    assert bandeiras["ACWI_BRL"] is True
    assert bandeiras["YAHOO_GSPC"] is False
    assert bandeiras["SP500_BRL"] is False
    for setorial in ("B3_IDIV", "B3_SMLL", "B3_INDX", "B3_ICON", "B3_IMAT", "B3_IEEX"):
        assert bandeiras[setorial] is None, setorial


# ═════════════════════════════════════════════════════════════════════════════
# D — o build de ponta a ponta em tmp_path, com o universo inteiro
# ═════════════════════════════════════════════════════════════════════════════

QUARTERS_DO_BUILD = ("2020Q3", "2020Q4", "2021Q1")
TAXA_CDI_SINTETICA = 0.01
"""`%/dia` constante — faz `cdi_tri` ser `1,0001**n − 1`, conferível à mão no teste."""

PASSO_SINTETICO = 0.001
"""Retorno diário constante do caminho de preço sintético: `100 · 1,001**i`."""

SERIES_EXTRA_DO_ESQUELETO = ("BCB_SGS_1", "BCB_SGS_432", "BCB_SGS_433", "SIDRA_1737_V63")
"""O que `SERIES_EXIGIDAS` de F-014 pede e o universo de F-017 não cobre."""


def _dias_uteis_sinteticos(inicio: str, fim: str) -> list[pd.Timestamp]:
    """Dias de semana entre as duas datas — o calendário sintético não tem feriado."""
    return [d for d in pd.date_range(inicio, fim) if d.weekday() < 5]


def _caminho_de_preco(dias: Sequence[pd.Timestamp]) -> list[tuple[str, float]]:
    """`100 · 1,001**i` — monótono, então `dd_intra_tri` é exatamente 0 e conferível."""
    return [
        (d.strftime("%Y-%m-%d"), 100.0 * (1.0 + PASSO_SINTETICO) ** i) for i, d in enumerate(dias)
    ]


def acervo_sintetico_em_disco(raiz: Path) -> pd.DataFrame:
    """Monta `data/canonical/{raw_series,series_catalog}.parquet` **sintéticos** em `raiz`.

    Traz as 24 séries do universo de F-017 (o schema exige >= 18 `asset_id`) + as do portão
    `SERIES_EXIGIDAS` de F-014 que **não** estão no universo — `BCB_SGS_1` está nos dois desde
    **D-l** (é a PTAX, insumo do alinhamento **e** o `asset_id` USDBRL), e gravá-la duas vezes
    duplicaria a PK de `raw_series`. O IBOV fica **sem** o último dia útil de 2020, que é o caso
    D-h e o que faz `ffill_dias_uteis = 1` chegar à tabela de retornos.
    """
    dias = _dias_uteis_sinteticos("2020-06-01", "2021-03-31")
    precos = _caminho_de_preco(dias)
    sem_o_fim_do_ano = [p for p in precos if p[0] != "2020-12-31"]
    mensais = [
        (d.strftime("%Y-%m-%d"), 0.30) for d in pd.date_range("2020-06-30", "2021-03-31", freq="ME")
    ]

    pedacos: list[pd.DataFrame] = []
    for ativo in UNIVERSO:
        if ativo.series_id == SERIE_CDI:
            pedacos.append(
                serie_sintetica(
                    SERIE_CDI, [(d.strftime("%Y-%m-%d"), TAXA_CDI_SINTETICA) for d in dias]
                )
            )
        elif ativo.series_id == "B3_IBOV":
            pedacos.append(serie_sintetica("B3_IBOV", sem_o_fim_do_ano))
        else:
            pedacos.append(serie_sintetica(ativo.series_id, precos))
    do_universo = {ativo.series_id for ativo in UNIVERSO}
    for series_id in SERIES_EXTRA_DO_ESQUELETO:
        if series_id in do_universo:
            continue
        if CATALOGO[series_id].freq.value == "D":
            if CATALOGO[series_id].calendario == "corrido":
                pedacos.append(
                    serie_sintetica(
                        series_id,
                        [
                            (d.strftime("%Y-%m-%d"), 2.0)
                            for d in pd.date_range("2020-06-01", "2021-03-31")
                        ],
                    )
                )
            else:
                pedacos.append(serie_sintetica(series_id, precos))
        else:
            pedacos.append(serie_sintetica(series_id, mensais))

    raw = pd.concat(pedacos, ignore_index=True).sort_values(["series_id", "date"], kind="mergesort")
    destino = caminho_camada(Camada.CANONICAL, raiz=raiz)
    destino.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(destino / NOME_RAW_SERIES, index=False)
    materializar_catalogo(load_catalog(), raw).to_parquet(destino / NOME_CATALOGO, index=False)
    return raw


def _build_sintetico(raiz: Path) -> Any:
    """Monta o acervo, roda F-014 e depois F-017, nos 3 trimestres sintéticos."""
    acervo_sintetico_em_disco(raiz)
    cal = calendario_sintetico(2020, 2021)
    construir_alinhado(raiz=raiz, calendario=cal, quarters=QUARTERS_DO_BUILD)
    return construir(raiz=raiz, calendario=cal, quarters=QUARTERS_DO_BUILD)


@pytest.fixture(scope="module")
def build_sintetico(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """O build sintético, uma vez por módulo (monta 27 séries e roda dois builds)."""
    return _build_sintetico(tmp_path_factory.mktemp("f017"))


def test_build_sintetico_grava_os_dois_artefatos_validados(build_sintetico: Any) -> None:
    """O build escreve o Parquet + o relatório, e o Parquet passa no schema do contrato."""
    assert build_sintetico.caminho_retornos.name == NOME_RETORNOS
    assert build_sintetico.caminho_retornos.is_file()
    assert build_sintetico.caminho_relatorio.name == NOME_RELATORIO
    gravado = pd.read_parquet(build_sintetico.caminho_retornos)
    AssetReturnsQuarterlySchema.validate(gravado, lazy=True)
    assert gravado["asset_id"].nunique() == len(UNIVERSO)
    assert set(gravado["quarter"]) == set(QUARTERS_DO_BUILD)
    assert not gravado.duplicated(subset=["quarter", "asset_id"]).any()


def test_build_sintetico_alinha_as_derivadas_que_f014_deixa_fora(build_sintetico: Any) -> None:
    """`SP500_BRL`/`ACWI_BRL` são `DERIVADO`: F-014 não as alinha, F-017 as alinha (F-014 §4.3)."""
    alinhado = pd.read_parquet(
        caminho_canonical(NOME_ALINHADO, raiz=build_sintetico.caminho_retornos.parents[2])
    )
    assert not set(DERIVADAS_ALINHADAS_AQUI) & set(alinhado["series_id"])
    tabela = build_sintetico.retornos
    for asset_id in ("SP500_BRL", "ACWI_BRL"):
        assert linha(tabela, asset_id, "2021Q1")["ret_tri"] is not None


def test_build_sintetico_nenhum_ativo_de_preco_tem_retorno_no_primeiro_trimestre(
    build_sintetico: Any,
) -> None:
    """O 1º trimestre da grade não tem `T−1`: `ret_tri` nulo em todos, **menos** no CDI."""
    tabela = build_sintetico.retornos
    primeiro = tabela[tabela["quarter"] == QUARTERS_DO_BUILD[0]]
    sem_cdi = primeiro[primeiro["asset_id"] != "CDI"]
    assert sem_cdi["ret_tri"].isna().all()
    assert sem_cdi["ret_excesso_cdi"].isna().all()
    assert sem_cdi["ret_real"].isna().all()
    assert sem_cdi["price_ini"].isna().all()
    assert sem_cdi["price_fim"].notna().all(), "o nível de T existe e não é apagado junto"
    assert linha(primeiro, "CDI", QUARTERS_DO_BUILD[0])["ret_tri"] is not None


def test_build_sintetico_cdi_e_a_acumulacao_conferivel_a_mao(build_sintetico: Any) -> None:
    """`0,01 %/dia` em `n` dias úteis ⇒ `1,0001**n − 1`, e o excesso do CDI sobre si é **0**."""
    cdi = build_sintetico.retornos[build_sintetico.retornos["asset_id"] == "CDI"]
    for _, item in cdi.iterrows():
        n = int(item["n_dias_uteis"])
        assert item["ret_tri"] == pytest.approx(
            (1.0 + TAXA_CDI_SINTETICA / 100) ** n - 1.0, abs=1e-15
        )
        assert item["ret_excesso_cdi"] == 0.0
        assert item["dd_intra_tri"] == 0.0
        assert pd.isna(item["price_ini"]) and pd.isna(item["price_fim"])


def test_build_sintetico_retorno_de_preco_e_o_passo_elevado_aos_dias(build_sintetico: Any) -> None:
    """Caminho `1,001**i` ⇒ `ret_tri = 1,001**n − 1` e `dd_intra_tri = 0` exato."""
    item = linha(build_sintetico.retornos, "IMAB", "2021Q1")
    n = int(item["n_dias_uteis"])
    assert item["ret_tri"] == pytest.approx((1.0 + PASSO_SINTETICO) ** n - 1.0, abs=1e-12)
    assert item["dd_intra_tri"] == 0.0
    assert item["vol_intra_tri"] == pytest.approx(0.0, abs=1e-12)


def test_build_sintetico_propaga_o_ffill_da_ponta_de_fechamento(build_sintetico: Any) -> None:
    """O IBOV sem 31/12/2020 fecha 2020Q4 com `ffill = 1`; as demais séries diárias, com 0."""
    tabela = build_sintetico.retornos
    assert linha(tabela, "IBOV", "2020Q4")["ffill_dias_uteis"] == 1
    assert linha(tabela, "IMAB", "2020Q4")["ffill_dias_uteis"] == 0
    com_ffill = tabela[tabela["ffill_dias_uteis"] > 0]
    assert set(com_ffill["asset_id"]) == {"IBOV"}
    assert set(com_ffill["quarter"]) == {"2020Q4"}


def test_build_sintetico_is_total_return_e_nulo_exatamente_nos_setoriais_e_no_cdi(
    build_sintetico: Any,
) -> None:
    """G-01 no artefato: a coluna é nula só onde o catálogo diz "a confirmar"."""
    tabela = build_sintetico.retornos
    nulos = set(tabela.loc[tabela["is_total_return"].isna(), "asset_id"])
    assert nulos == {
        "CDI",
        "ICON",
        "IDIV",
        "IEEX",
        "IFNC",
        "IMAT",
        "IMOB",
        "INDX",
        "SMLL",
        "UTIL",
    }
    assert bool(linha(tabela, "SP500_USD", "2021Q1")["is_total_return"]) is False
    assert bool(linha(tabela, "IBOV", "2021Q1")["is_total_return"]) is True


def test_relatorio_tem_cobertura_por_ativo_e_motivo_de_cada_nulo(build_sintetico: Any) -> None:
    """O relatório é o insumo da revisão independente: nulo sem motivo nomeado é bug."""
    relatorio = json.loads(build_sintetico.caminho_relatorio.read_text(encoding="utf-8"))
    bloco = relatorio["asset_returns_quarterly"]
    assert bloco["ativos"] == len(UNIVERSO)
    assert bloco["sha256"] == sha256_de(build_sintetico.caminho_retornos.read_bytes())
    for coluna in bloco["nulos_por_coluna"]:
        assert coluna in bloco["nulos_por_coluna_com_motivo"], coluna
        total = sum(bloco["nulos_por_coluna_com_motivo"][coluna].values())
        assert total == bloco["nulos_por_coluna"][coluna], coluna
    por_ativo = {b["asset_id"]: b for b in relatorio["ativos"]}
    assert por_ativo["IBOV"]["primeiro_trimestre_com_retorno"] == "2020Q4"
    assert por_ativo["CDI"]["primeiro_trimestre_com_retorno"] == QUARTERS_DO_BUILD[0]
    assert por_ativo["CDI"]["metodo"] == "acumulacao_de_taxa_diaria"
    assert set(relatorio["universo"]["fora_do_universo"]) and all(
        motivo for motivo in relatorio["universo"]["fora_do_universo"].values()
    )
    assert "hora" not in json.dumps(relatorio).lower()


def test_relatorio_declara_as_convencoes_de_razao_e_de_acumulacao(build_sintetico: Any) -> None:
    """Quem abre o Parquet sem ler o código tem de achar a convenção no próprio artefato."""
    convencoes = json.loads(build_sintetico.caminho_relatorio.read_text(encoding="utf-8"))[
        "convencoes"
    ]
    assert "razao" in convencoes["ret_excesso_cdi"]
    assert "nunca subtracao" in convencoes["ret_excesso_cdi"]
    assert "prod(1 + v/100)" in convencoes["cdi_tri"]
    assert "NULL" in convencoes["primeiro_trimestre_da_serie"]


def test_build_e_idempotente_por_hash(tmp_path: Path) -> None:
    """RF-048/CA-121: duas rodadas sobre a mesma entrada dão Parquet e relatório byte-idênticos."""
    acervo_sintetico_em_disco(tmp_path)
    cal = calendario_sintetico(2020, 2021)
    construir_alinhado(raiz=tmp_path, calendario=cal, quarters=QUARTERS_DO_BUILD)
    hashes = []
    for _ in range(2):
        resultado = construir(raiz=tmp_path, calendario=cal, quarters=QUARTERS_DO_BUILD)
        hashes.append(
            (
                sha256_de(resultado.caminho_retornos.read_bytes()),
                sha256_de(resultado.caminho_relatorio.read_bytes()),
            )
        )
    assert hashes[0] == hashes[1]


def test_versao_build_cobre_os_seis_componentes_e_nao_so_este_arquivo() -> None:
    """Hash **do conjunto**: editar o alinhamento, o contrato ou o catálogo muda esta tabela."""
    assert len(MODULOS_DOS_RETORNOS) == 6
    assert "apps.pipeline.canonical.alinhamento" in MODULOS_DOS_RETORNOS
    assert "packages.shared.schemas.asset_returns_quarterly" in MODULOS_DOS_RETORNOS
    assert "packages.shared.schemas.series_catalog_data" in MODULOS_DOS_RETORNOS
    completo = versao_build()
    assert len(completo) == 64
    for fora in MODULOS_DOS_RETORNOS:
        parcial = tuple(m for m in MODULOS_DOS_RETORNOS if m != fora)
        assert versao_build(parcial) != completo, fora


def test_build_sem_alinhado_trimestral_bloqueia(tmp_path: Path) -> None:
    """Sem a régua de F-014 não há nível trimestral — e a mensagem diz o comando que falta."""
    acervo_sintetico_em_disco(tmp_path)
    with pytest.raises(FonteIndisponivel) as erro:
        construir(
            raiz=tmp_path,
            calendario=calendario_sintetico(2020, 2021),
            quarters=QUARTERS_DO_BUILD,
        )
    assert "BLOQUEADO — FONTE INDISPONÍVEL" in str(erro.value)
    assert "alinhamento" in str(erro.value)


def test_build_sem_serie_do_universo_bloqueia(tmp_path: Path) -> None:
    """**CA-062/CA-076.** Falta o IFIX: o build para em vez de entregar 22 ativos em silêncio."""
    raw = acervo_sintetico_em_disco(tmp_path)
    cal = calendario_sintetico(2020, 2021)
    construir_alinhado(raiz=tmp_path, calendario=cal, quarters=QUARTERS_DO_BUILD)
    destino = caminho_camada(Camada.CANONICAL, raiz=tmp_path)
    alinhado = pd.read_parquet(destino / NOME_ALINHADO)
    alinhado[alinhado["series_id"] != "B3_IFIX"].to_parquet(destino / NOME_ALINHADO, index=False)
    del raw
    with pytest.raises(UniversoIncompleto) as erro:
        construir(raiz=tmp_path, calendario=cal, quarters=QUARTERS_DO_BUILD)
    assert "B3_IFIX" in str(erro.value)


# ═════════════════════════════════════════════════════════════════════════════
# E — o acervo real de data/canonical/ (por acréscimo; `LDC_IGNORAR_DATA=1` desliga)
# ═════════════════════════════════════════════════════════════════════════════


def ignorar_data_real() -> bool:
    """`LDC_IGNORAR_DATA` ligada? (vazio, `0`, `false` e `nao` contam como desligada)."""
    return os.environ.get(VAR_IGNORAR_DATA, "").strip().lower() not in {
        "",
        "0",
        "false",
        "nao",
        "no",
    }


def acervo_disponivel() -> bool:
    """Os três Parquets de que a seção E depende existem nesta máquina?"""
    return all(
        caminho_canonical(nome).is_file()
        for nome in (NOME_RETORNOS, NOME_ALINHADO, NOME_RAW_SERIES)
    )


pulo_do_acervo = pytest.mark.skipif(
    ignorar_data_real() or not acervo_disponivel(),
    reason=(
        "seção E roda sobre data/canonical/. Ligue com "
        "`uv run python -m apps.pipeline.canonical.retornos --offline` e "
        f"{VAR_IGNORAR_DATA} desligada."
    ),
)


@pytest.fixture(scope="module")
def acervo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """`(retornos, alinhado, raw)` do acervo real, sem recalcular nada."""
    return (
        pd.read_parquet(caminho_canonical(NOME_RETORNOS)),
        pd.read_parquet(caminho_canonical(NOME_ALINHADO)),
        pd.read_parquet(caminho_canonical(NOME_RAW_SERIES)),
    )


def _niveis_do_acervo(alinhado: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Os níveis trimestrais **recalculados à mão** aqui: o alinhado + as duas derivadas.

    O recálculo das derivadas é o "último dia útil <= `quarter_end`" escrito no próprio teste, sem
    importar o módulo — é o que faz a comparação de `ret_tri` ser um diff, não uma tautologia.
    """
    fins = alinhado.groupby("quarter")["quarter_end"].first()
    extra: list[dict[str, Any]] = []
    for series_id in DERIVADAS_ALINHADAS_AQUI:
        serie = raw[(raw["series_id"] == series_id) & raw["value"].notna()].sort_values("date")
        for quarter, fim in fins.items():
            ate = serie[serie["date"] <= fim]
            if ate.empty:
                continue
            extra.append(
                {
                    "series_id": series_id,
                    "quarter": quarter,
                    "date_obs": ate["date"].iloc[-1],
                    "value": ate["value"].iloc[-1],
                }
            )
    colunas = ["series_id", "quarter", "date_obs", "value"]
    return pd.concat([alinhado[colunas], pd.DataFrame(extra)], ignore_index=True)


@pulo_do_acervo
def test_acervo_passa_no_schema_do_contrato(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """O artefato em disco satisfaz `AssetReturnsQuarterlySchema`, inclusive os 2 checks."""
    retornos, _, _ = acervo
    AssetReturnsQuarterlySchema.validate(retornos, lazy=True)
    assert retornos["asset_id"].nunique() >= N_MINIMO_ATIVOS
    assert not retornos.duplicated(subset=["quarter", "asset_id"]).any()


@pulo_do_acervo
def test_acervo_ret_tri_e_exatamente_a_razao_dos_niveis_do_alinhado(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**O diff numérico da classe C.** Igualdade **exata** (`==` em `float64`, sem tolerância).

    Cada `ret_tri` da tabela é recalculado aqui a partir de `alinhado_trimestral` — níveis de `T`
    e `T−1` da mesma série — e comparado bit a bit. O CDI fica fora (é acumulação de taxa, não
    razão de níveis) e tem o seu próprio teste.
    """
    retornos, alinhado, raw = acervo
    niveis = _niveis_do_acervo(alinhado, raw)
    mapa = retornos.groupby("asset_id")["series_id"].first().to_dict()
    conferidas = 0
    for asset_id, grupo in retornos.groupby("asset_id"):
        if asset_id == "CDI":
            continue
        serie = niveis[niveis["series_id"] == mapa[asset_id]].sort_values("quarter")
        quarters = list(serie["quarter"])
        valores = list(serie["value"])
        assert quarters == list(grupo.sort_values("quarter")["quarter"]), asset_id
        for posicao, item in enumerate(grupo.sort_values("quarter").itertuples()):
            if posicao == 0 or pd.isna(valores[posicao]) or pd.isna(valores[posicao - 1]):
                assert pd.isna(item.ret_tri), (asset_id, item.quarter)
                continue
            esperado = valores[posicao] / valores[posicao - 1] - 1.0
            assert item.ret_tri == esperado, (asset_id, item.quarter, item.ret_tri, esperado)
            assert item.price_ini == valores[posicao - 1]
            assert item.price_fim == valores[posicao]
            conferidas += 1
    assert conferidas > 1500, conferidas


@pulo_do_acervo
def test_acervo_excesso_e_real_sao_razao_e_a_subtracao_daria_outro_numero(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**CA-069 no dado real + o teste negativo.** O excesso é a razão, e a subtração divergiria.

    O CDI por trimestre é recalculado aqui de `raw_series`, por conta própria. A divergência
    média entre razão e subtração é da ordem de 0,1 pp **por trimestre** — material, não
    arredondamento (Anti-SPEC §10.2.13).
    """
    retornos, _, raw = acervo
    serie = raw[(raw["series_id"] == SERIE_CDI) & raw["value"].notna()].sort_values("date")
    por_trimestre = serie["date"].dt.to_period("Q").astype(str)
    cdi = {
        quarter: math.prod(1 + v / 100 for v in serie.loc[por_trimestre == quarter, "value"]) - 1
        for quarter in retornos["quarter"].unique()
    }
    com_excesso = retornos.dropna(subset=["ret_tri", "ret_excesso_cdi"])
    diferencas = []
    for item in com_excesso.itertuples():
        base = cdi[item.quarter]
        assert item.ret_excesso_cdi == pytest.approx(
            (1 + item.ret_tri) / (1 + base) - 1, abs=1e-12
        ), (item.asset_id, item.quarter)
        diferencas.append(abs(item.ret_excesso_cdi - (item.ret_tri - base)))
    # O CDI é o único ativo em que razão e subtração coincidem (as duas dão 0).
    assert sum(1 for d in diferencas if d < 1e-12) == retornos["quarter"].nunique()
    assert max(diferencas) > 0.01, "a subtração daria o mesmo número — a razão não está em uso"


@pulo_do_acervo
def test_acervo_ret_real_usa_o_ipca_do_proprio_trimestre_uma_unica_vez(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**CA-071 no dado real.** IPCA dos 3 meses de `T`; a dupla deflação daria outro número."""
    retornos, _, raw = acervo
    serie = raw[(raw["series_id"] == SERIE_IPCA) & raw["value"].notna()].sort_values("date")
    por_trimestre = serie["date"].dt.to_period("Q").astype(str)
    ipca: dict[str, float | None] = {}
    for quarter in retornos["quarter"].unique():
        meses = serie.loc[por_trimestre == quarter, "value"]
        ipca[quarter] = math.prod(1 + v / 100 for v in meses) - 1 if len(meses) == 3 else None
    com_real = retornos.dropna(subset=["ret_tri", "ret_real"])
    assert len(com_real) > 1500
    piores = 0.0
    for item in com_real.itertuples():
        base = ipca[item.quarter]
        assert base is not None
        assert item.ret_real == pytest.approx((1 + item.ret_tri) / (1 + base) - 1, abs=1e-12)
        duas_vezes = (1 + item.ret_real) / (1 + base) - 1
        piores = max(piores, abs(item.ret_real - duas_vezes))
    assert piores > 0.005, "deflacionar duas vezes daria o mesmo número — há algo errado"


@pulo_do_acervo
def test_acervo_valores_canario(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Os 3 canários do Feature Contract, lidos do artefato em disco.

    IBOV 2T2006 contra os dois fechamentos do alinhado; IMA-B 1T2007 contra os da ANBIMA; e o
    CDI de 4T2008 contra a **segunda fonte** do mesmo CDI (SGS 4389, `% a.a.` base 252,
    `fator_dia = (1+taxa/100)**(1/252)`) — fonte diferente, mesmo número.
    """
    retornos, _, raw = acervo
    ibov = linha(retornos, "IBOV", "2006Q2")
    assert (ibov["price_ini"], ibov["price_fim"]) == (IBOV_2006Q1, IBOV_2006Q2)
    assert ibov["ret_tri"] == IBOV_2006Q2 / IBOV_2006Q1 - 1

    imab = linha(retornos, "IMAB", "2007Q1")
    assert (imab["price_ini"], imab["price_fim"]) == (IMAB_2006Q4, IMAB_2007Q1)
    assert imab["ret_tri"] == IMAB_2007Q1 / IMAB_2006Q4 - 1

    segunda_fonte = raw[
        (raw["series_id"] == SERIE_CDI_CONFERENCIA) & raw["value"].notna()
    ].sort_values("date")
    do_trimestre = segunda_fonte["date"].dt.to_period("Q").astype(str) == "2008Q4"
    por_4389 = (
        math.prod((1 + v / 100) ** (1 / 252) for v in segunda_fonte.loc[do_trimestre, "value"]) - 1
    )
    cdi = linha(retornos, "CDI", "2008Q4")
    assert cdi["ret_tri"] == pytest.approx(0.0331667786, abs=1e-9)
    assert cdi["ret_tri"] == pytest.approx(por_4389, abs=1e-6)


@pulo_do_acervo
def test_acervo_cdi_de_2006_encadeado_reproduz_o_valor_canario(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """Os 4 trimestres de 2006 **da própria tabela** encadeiam em 15,0271 % (CA-014/CA-015)."""
    retornos, _, _ = acervo
    de_2006 = retornos[
        (retornos["asset_id"] == "CDI") & retornos["quarter"].str.startswith("2006")
    ].sort_values("quarter")
    assert list(de_2006["quarter"]) == list(QUARTERS_2006)
    assert list(de_2006["n_dias_uteis"]) == [63.0, 61.0, 64.0, 61.0]
    encadeado = math.prod(1 + v for v in de_2006["ret_tri"]) - 1
    assert encadeado * 100 == pytest.approx(CDI_2006_PCT, abs=1e-4)


@pulo_do_acervo
def test_acervo_a_janela_do_cdi_e_a_mesma_janela_dos_precos(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """A acumulação do CDI em `T` cobre exatamente `(quarter_end(T−1), quarter_end(T)]`.

    É o que torna `ret_excesso_cdi` uma comparação de janelas iguais. A implementação usa
    pertencimento ao trimestre com corte em `quarter_end(T)`; este teste afirma que as duas
    definições coincidem em todos os trimestres que têm `T−1`.
    """
    _, alinhado, raw = acervo
    fins = alinhado.groupby("quarter")["quarter_end"].first().sort_index()
    serie = raw[(raw["series_id"] == SERIE_CDI) & raw["value"].notna()]
    por_trimestre = serie["date"].dt.to_period("Q").astype(str)
    quarters = list(fins.index)
    for posicao in range(1, len(quarters)):
        quarter = quarters[posicao]
        fim = fins.iloc[posicao]
        anterior = fins.iloc[posicao - 1]
        do_trimestre = (por_trimestre == quarter) & (serie["date"] <= fim)
        por_pertencimento = set(serie.loc[do_trimestre, "date"])
        por_intervalo = set(serie.loc[(serie["date"] > anterior) & (serie["date"] <= fim), "date"])
        assert por_pertencimento == por_intervalo, quarter


@pulo_do_acervo
def test_acervo_produto_dos_fatores_diarios_e_o_ret_tri(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**CA-070 no dado real.** O encadeamento é o produto, e a **soma** daria outro número.

    O caminho diário é `(date_obs(T−1), date_obs(T)]`, o que também confere `n_dias_uteis`.
    """
    retornos, alinhado, raw = acervo
    casos = [("B3_IBOV", "IBOV", "2008Q4"), ("ANBIMA_IMAB", "IMAB", "2015Q3")]
    for series_id, asset_id, quarter in casos:
        grupo = alinhado[alinhado["series_id"] == series_id].sort_values("quarter")
        grupo = grupo.reset_index(drop=True)
        posicao = int(grupo.index[grupo["quarter"] == quarter][0])
        inicio = grupo.loc[posicao - 1, "date_obs"]
        fim = grupo.loc[posicao, "date_obs"]
        serie = raw[(raw["series_id"] == series_id) & raw["value"].notna()].sort_values("date")
        caminho = serie.loc[(serie["date"] > inicio) & (serie["date"] <= fim), "value"].tolist()
        item = linha(retornos, asset_id, quarter)
        produto = 1.0
        anterior = float(grupo.loc[posicao - 1, "value"])
        soma = 0.0
        for nivel in caminho:
            produto *= float(nivel) / anterior
            soma += float(nivel) / anterior - 1.0
            anterior = float(nivel)
        assert produto - 1.0 == pytest.approx(item["ret_tri"], abs=1e-12)
        assert item["n_dias_uteis"] == float(len(caminho))
        assert abs(soma - item["ret_tri"]) > 1e-3, "a soma coincidiria com o produto — suspeito"


@pulo_do_acervo
def test_acervo_nenhum_ativo_de_preco_tem_retorno_no_seu_primeiro_trimestre(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**CA-063.** Sem `T−1` não há retorno — e o CDI é a única exceção, por ser acumulação."""
    retornos, _, _ = acervo
    for asset_id, grupo in retornos.groupby("asset_id"):
        primeiro = grupo.sort_values("quarter").iloc[0]
        if asset_id == "CDI":
            assert pd.notna(primeiro["ret_tri"]), "o CDI acumula dentro de T e não depende de T-1"
            continue
        assert pd.isna(primeiro["ret_tri"]), asset_id
        assert pd.isna(primeiro["price_ini"]), asset_id


@pulo_do_acervo
def test_acervo_ifix_comeca_em_2010q4_sem_retorno_e_2011q1_e_o_primeiro(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """**CA-063 / ADR-005 §2.** Nenhuma linha antes de 2010Q4; 2010Q4 parcial; 2011Q1 o 1º retorno.

    É o caso que a Anti-SPEC §10.1.1 nomeia: IFIX sintético pré-2011 é proibido, e o trimestre que
    **contém** 30/12/2010 é aceito pelo contrato — parcial, não anterior.
    """
    retornos, _, _ = acervo
    ifix = retornos[retornos["asset_id"] == "IFIX"].sort_values("quarter")
    assert ifix["quarter"].min() == "2010Q4"
    assert ifix["data_inicio_serie"].iloc[0] == pd.Timestamp("2010-12-30")
    assert not any(q < "2010Q4" for q in ifix["quarter"])

    base = linha(retornos, "IFIX", "2010Q4")
    assert pd.isna(base["ret_tri"])
    assert base["price_fim"] == IFIX_2010Q4
    primeiro = linha(retornos, "IFIX", "2011Q1")
    assert primeiro["price_ini"] == IFIX_2010Q4
    assert primeiro["price_fim"] == IFIX_2011Q1
    assert primeiro["ret_tri"] == pytest.approx(0.02825, abs=1e-12)
    com_retorno = ifix[ifix["ret_tri"].notna()]
    assert com_retorno["quarter"].min() == "2011Q1"


@pulo_do_acervo
def test_acervo_icon_e_imob_tambem_entram_com_janela_propria(
    acervo: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> None:
    """ICON (2006Q4) e IMOB (2007Q4) são os outros dois casos de janela própria de ADR-005."""
    retornos, _, _ = acervo
    esperado = {"ICON": ("2006Q4", "2007Q1"), "IMOB": ("2007Q4", "2008Q1")}
    for asset_id, (primeiro, primeiro_retorno) in esperado.items():
        grupo = retornos[retornos["asset_id"] == asset_id]
        assert grupo["quarter"].min() == primeiro, asset_id
        assert grupo.loc[grupo["ret_tri"].notna(), "quarter"].min() == primeiro_retorno, asset_id


@pulo_do_acervo
def test_acervo_relatorio_bate_com_o_parquet_em_disco() -> None:
    """O relatório descreve **o** Parquet gravado: `sha256`, linhas e nulos por coluna."""
    relatorio = json.loads(caminho_canonical(NOME_RELATORIO).read_text(encoding="utf-8"))
    bloco = relatorio["asset_returns_quarterly"]
    corpo = caminho_canonical(NOME_RETORNOS).read_bytes()
    assert bloco["sha256"] == sha256_de(corpo)
    assert bloco["bytes"] == len(corpo)
    retornos = pd.read_parquet(caminho_canonical(NOME_RETORNOS))
    assert bloco["linhas"] == len(retornos)
    assert bloco["ativos"] == retornos["asset_id"].nunique()
    assert relatorio["versao_build"]["sha256"] == retornos["fonte_versao"].iloc[0]
    for coluna, n in bloco["nulos_por_coluna"].items():
        assert int(retornos[coluna].isna().sum()) == n, coluna


@pulo_do_acervo
def test_acervo_todo_nulo_de_metrica_tem_motivo_nomeado() -> None:
    """Ausência com causa: cada coluna nula aparece no mapa de motivos, e o total fecha."""
    relatorio = json.loads(caminho_canonical(NOME_RELATORIO).read_text(encoding="utf-8"))
    bloco = relatorio["asset_returns_quarterly"]
    validos = {str(m) for m in MotivoNulo}
    for coluna, n in bloco["nulos_por_coluna"].items():
        motivos = bloco["nulos_por_coluna_com_motivo"][coluna]
        assert set(motivos) <= validos, (coluna, motivos)
        assert sum(motivos.values()) == n, coluna
