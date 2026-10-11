"""F-016 — curva de juros: vértices fixos interpolados, inclinação e breakeven. **Classe C.**

O que este módulo faz, e **só** isto, a partir de `data/processed/tesouro-direto/td_painel.parquet`
(F-005, a fonte primária da curva por **ADR-004**):

1. **Remonta a seção transversal** de cada data base: para cada família de título
   (`REAL` = Tesouro IPCA+ = `NTNB` + `NTNBP`; `NOMINAL` = Prefixado = `LTN` + `NTNF`), os pares
   `(prazo até o vencimento, taxa)` daquele dia, usando `TAXA_VENDA` (§ "Decisões" abaixo).
2. **Interpola linearmente no prazo** para os vértices fixos de **1, 3 e 5 anos** (CA-023),
   **sem nenhuma extrapolação**: quando o vértice cai fora do intervalo de vencimentos vivos
   naquele dia, o valor é **`None` com o motivo registrado** — nunca um número inventado
   (Anti-SPEC §10.1.1, CA-023/CA-024).
3. **Deriva** as 4 inclinações `INCLINACAO_{REAL,NOMINAL}_5A_{1A,3A}` (vértice longo − curto, em
   `pp`) e `BREAKEVEN_5A` **por razão** `(1+nominal)/(1+real) − 1`, nunca por subtração
   (Anti-SPEC §10.2.13, CA-026).
4. **Grava as 11 séries** do `series_catalog` em `data/processed/curva/<series_id>.parquet`, cada
   uma validada por `ProcessedSeriesSchema` **antes** da escrita, para o build de F-013 as absorver
   na próxima rodada (ele varre `data/processed/*/*.parquet`). Este módulo **não** toca
   `data/canonical/` nem `build_raw_series.py`.
5. **Registra** em `data/processed/curva/relatorio_curva.json` o que o Parquet de 8 colunas não tem
   como carregar: a flag `vertice_extrapolado` de CA-023, o motivo de cada ausência, o `%` de nulos
   por série e por ano, a largura do intervalo de interpolação e os canários conferíveis à mão.

O que este módulo **não** faz: não agrega para trimestral em disco (Anti-SPEC §10.4.28 — a
granularidade nativa é a verdade; `agregar_para_trimestre` existe como função pública, é o que
CA-026 exige, e quem materializa é F-015), não preenche lacuna, não faz `ffill`, não extrapola,
não vai à rede.

Decisões desta feature (detalhe e medição em `docs/wiki/context/F-016.md`)
-------------------------------------------------------------------------
- **Métrica = `TAXA_VENDA`.** É a taxa de recompra do Tesouro: existe e é `> 0` em **todas** as
  observações de `LTN`/`NTNF`/`NTNB`/`NTNBP` do arquivo completo, enquanto `TAXA_COMPRA` traz
  `0,00` quando o título **não está à venda** (14 observações de `NTNF`; 7.747 de `LFT`) — e `0,00`
  ali é ausência disfarçada de número, o modo de falha que a Anti-SPEC §10.1.4 proíbe de propagar.
  Taxas **negativas** de `NTNB`/`NTNBP` são valores reais (juro real negativo em 2020-2021) e
  passam intactas.
- **Prazo em dias corridos (`ACT`): 1 ano = 365,25 d, 3 anos = 1.095,75 d, 5 anos = 1.826,25 d.** O
  briefing pedia dias úteis ANBIMA; a contagem em dias úteis está implementada
  (`MetricaPrazo.DIAS_UTEIS`, vértices de 252, 756 e 1.260 d.u.) e é usada na sensibilidade,
  mas **não pode ser o padrão**: o calendário de F-008 cobre `2001-01-01..2030-12-31` e os
  vencimentos do painel chegam a **2060**, logo o vértice de 5 anos das datas base de 2026 e todo
  par que envolva título longo ficariam sem contagem. Construir feriado por regra está **recusado
  por decisão do projeto** (`DECISIONS_LOG` D-f: "dado inventado"), e devolver `None` por limite do
  nosso calendário — e não por ausência de título — seria mentir sobre o suporte do dado.
  A diferença medida entre os dois métodos está no relatório e no context pack.
- **Família, não título isolado.** `REAL` = `NTNB` + `NTNBP` e `NOMINAL` = `LTN` + `NTNF`, como o
  `identificador` do catálogo descreve ("Tesouro IPCA+", "Prefixado"). Dois títulos da mesma
  família com o **mesmo vencimento** (LTN × NTN-F e NTN-B × NTN-B Principal existem em 14 e 8
  vencimentos) viram **um ponto com a média das taxas**: a diferença medida entre eles é de
  **mediana 0 bps** (média 1-3 bps), de modo que a escolha não move o vértice, e a média é a única
  regra simétrica. O número de pontos agregados vai no relatório.
- **`vintage` e `collected_at` são herdados do painel**, por data base — nada aqui lê o relógio, e é
  isso que faz duas rodadas produzirem `sha256` idêntico.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    caminho_processed,
    garantir_diretorio,
    gravar_processado_parquet,
    sha256_de,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from apps.pipeline.extract.calendario_anbima import Calendario
from apps.pipeline.extract.tesouro_direto import (
    NOME_PROCESSADO as NOME_PAINEL_TESOURO,
)
from apps.pipeline.extract.tesouro_direto import (
    decompor_series_id,
)
from packages.shared.schemas import ProcessedSeriesSchema, load_catalog

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Iterable, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────

#: Subpasta de `data/processed/` desta feature. O build de F-013 varre `*/*.parquet`.
PASTA_CURVA = "curva"

NOME_RELATORIO = "relatorio_curva.json"

#: Métrica do painel usada como taxa da curva — ver "Decisões" no topo do módulo.
METRICA_TAXA = "TAXA_VENDA"

FREQ = "D"
FONTE = "DERIVADO"
UNIDADE_TAXA = "%a.a."
UNIDADE_INCLINACAO = "pp"

#: Convenção de ano para o prazo em dias corridos (ACT): 365,25 absorve o ano bissexto sem
#: depender da data de aniversário (e `5 anos` = 1.826,25 d, não `5 × 365`).
DIAS_CORRIDOS_POR_ANO = 365.25

#: Convenção ANBIMA/B3 de ano em dias úteis — a mesma dos vértices da Curva Zero (252, 504, …).
DIAS_UTEIS_POR_ANO = 252


class MetricaPrazo(StrEnum):
    """Como o prazo até o vencimento é medido na interpolação."""

    DIAS_CORRIDOS = "dias_corridos"
    DIAS_UTEIS = "dias_uteis"

    @property
    def dias_por_ano(self) -> float:
        """Quantos dias desta métrica equivalem a 1 ano de vértice."""
        return DIAS_CORRIDOS_POR_ANO if self is MetricaPrazo.DIAS_CORRIDOS else DIAS_UTEIS_POR_ANO


class Familia(StrEnum):
    """As duas curvas que o painel do Tesouro Direto sustenta."""

    REAL = "REAL"
    NOMINAL = "NOMINAL"


#: Siglas de `montar_series_id` que compõem cada curva (nome comercial no comentário).
SIGLAS_DA_FAMILIA: dict[Familia, tuple[str, ...]] = {
    Familia.REAL: ("NTNB", "NTNBP"),  # Tesouro IPCA+ (com juros semestrais e Principal)
    Familia.NOMINAL: ("LTN", "NTNF"),  # Tesouro Prefixado (e com juros semestrais)
}


class Motivo(StrEnum):
    """Por que um vértice ficou sem valor. Toda ausência tem **um** destes, nunca nenhum."""

    SEM_TITULO = "sem_titulo_vivo_na_data"
    SEM_SUPORTE_CURTO = "sem_vencimento_abaixo_do_vertice"
    SEM_SUPORTE_LONGO = "sem_vencimento_acima_do_vertice"
    SEM_CALENDARIO = "prazo_fora_da_cobertura_do_calendario"
    VERTICE_AUSENTE = "vertice_de_origem_ausente"


@dataclass(frozen=True, slots=True)
class Vertice:
    """Um vértice fixo da curva: a série do catálogo, a família e o prazo-alvo em anos."""

    series_id: str
    familia: Familia
    anos: int

    def alvo(self, metrica: MetricaPrazo) -> float:
        """Prazo-alvo na métrica escolhida (365,25 × anos, ou 252 × anos)."""
        return self.anos * metrica.dias_por_ano


#: Os 6 vértices que o `series_catalog` declara (`CURVA_*`) — os "1, 3 e 5 anos" de CA-023, em
#: `dict` para a ordem ser estável. Os de **3 anos** entraram em 2026-10-11 por **D-i** (decisão
#: provisória do orquestrador, aguarda aval do Edu): é o vértice curto que dá suporte à ponta real
#: em 95,25% das datas base de 2006 em diante, contra 60,53% do de 1 ano.
VERTICES: dict[str, Vertice] = {
    v.series_id: v
    for v in (
        Vertice("CURVA_REAL_1A", Familia.REAL, 1),
        Vertice("CURVA_REAL_3A", Familia.REAL, 3),
        Vertice("CURVA_REAL_5A", Familia.REAL, 5),
        Vertice("CURVA_NOMINAL_1A", Familia.NOMINAL, 1),
        Vertice("CURVA_NOMINAL_3A", Familia.NOMINAL, 3),
        Vertice("CURVA_NOMINAL_5A", Familia.NOMINAL, 5),
    )
}

#: Vértices **medidos e não gravados**: não têm entrada no `series_catalog` e CA-055 exige que toda
#: linha do canônico resolva nele, então ninguém grava Parquet deles. Existem porque o vértice de
#: 10 anos é o caso de CA-024 (não existe em 2006: a NTN-F mais longa vencia em 01/01/2014) e medir
#: a cobertura dele é o que transforma "não dá" em número — 36,81% das datas base de 2006 em diante
#: no nominal, contra 100% no real. Entram só no `cobertura_por_vertice` do relatório.
VERTICES_FORA_DO_CATALOGO: dict[str, Vertice] = {
    v.series_id: v
    for v in (
        Vertice("CURVA_REAL_10A", Familia.REAL, 10),
        Vertice("CURVA_NOMINAL_10A", Familia.NOMINAL, 10),
    )
}

#: `INCLINACAO_REAL_5A_3A` é a **variável principal de regime** desde D-i (provisória); a 5a-1a
#: continua publicada como secundária, porque é a que ADR-004 §3 nomeia e tem 20 anos de leitura
#: histórica — as duas convivem, com a cobertura de cada uma declarada no relatório.
SERIE_INCLINACAO_REAL = "INCLINACAO_REAL_5A_1A"
SERIE_INCLINACAO_NOMINAL = "INCLINACAO_NOMINAL_5A_1A"
SERIE_INCLINACAO_REAL_3A = "INCLINACAO_REAL_5A_3A"
SERIE_INCLINACAO_NOMINAL_3A = "INCLINACAO_NOMINAL_5A_3A"
SERIE_BREAKEVEN = "BREAKEVEN_5A"

#: `(derivada, vértice longo, vértice curto)` — a aritmética de cada série derivada de 2º nível.
INCLINACOES: tuple[tuple[str, str, str], ...] = (
    (SERIE_INCLINACAO_REAL_3A, "CURVA_REAL_5A", "CURVA_REAL_3A"),
    (SERIE_INCLINACAO_NOMINAL_3A, "CURVA_NOMINAL_5A", "CURVA_NOMINAL_3A"),
    (SERIE_INCLINACAO_REAL, "CURVA_REAL_5A", "CURVA_REAL_1A"),
    (SERIE_INCLINACAO_NOMINAL, "CURVA_NOMINAL_5A", "CURVA_NOMINAL_1A"),
)

BREAKEVEN = (SERIE_BREAKEVEN, "CURVA_NOMINAL_5A", "CURVA_REAL_5A")

#: As 11 séries de `fonte=DERIVADO` que F-016 acrescenta a `raw_series`, na ordem de gravação.
SERIES_DE_F016: tuple[str, ...] = (
    *VERTICES,
    *(derivada for derivada, _, _ in INCLINACOES),
    SERIE_BREAKEVEN,
)

#: `series_id` → `unit` que esta feature grava. É o que `conferir_catalogo` confronta com o
#: catálogo **antes** de gravar: inclinação é diferença (`pp`), vértice e breakeven são taxa.
UNIDADE_POR_SERIE: dict[str, str] = {
    **{sid: UNIDADE_TAXA for sid in VERTICES},
    **{derivada: UNIDADE_INCLINACAO for derivada, _, _ in INCLINACOES},
    SERIE_BREAKEVEN: UNIDADE_TAXA,
}

#: As 8 colunas de `ProcessedSeriesSchema`, nesta ordem (`strict=True`: nada mais entra).
COLUNAS_PROCESSADAS: tuple[str, ...] = (
    "series_id",
    "date",
    "value",
    "source",
    "freq",
    "vintage",
    "unit",
    "collected_at",
)

#: Colunas do quadro de diagnóstico que `serie_do_vertice` devolve (não vão para o Parquet).
COLUNAS_DIAGNOSTICO: tuple[str, ...] = (
    "date",
    "value",
    "motivo",
    "vertice_extrapolado",
    "exato",
    "prazo_curto",
    "prazo_longo",
    "taxa_curta",
    "taxa_longa",
    "titulo_curto",
    "titulo_longo",
    "peso",
    "n_pontos",
    "n_pontos_agregados",
)


class CurvaInconsistente(ErroDeExtracao):
    """O painel abriu, mas não sustenta a curva (métrica ausente, família vazia, prazo inválido)."""


# ─────────────────────────────────────────────────────────────────────────────
# O núcleo: interpolação linear sem extrapolação
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Ponto:
    """Um ponto observado da curva num dia: prazo, taxa e qual título o produziu."""

    prazo: float
    taxa: float
    titulo: str


@dataclass(frozen=True, slots=True)
class Interpolacao:
    """Resultado de um vértice num dia — com o rastro de **como** o número saiu.

    `valor is None` ⇔ `motivo is not None` ⇔ `vertice_extrapolado is True`: as três formas de
    dizer a mesma coisa andam juntas por construção, e há teste disso. É o que CA-023/CA-024
    pedem: o vértice fora do intervalo de vencimentos **não** vira número.
    """

    valor: float | None
    motivo: Motivo | None
    vertice_extrapolado: bool
    exato: bool = False
    ponto_curto: Ponto | None = None
    ponto_longo: Ponto | None = None
    peso: float | None = None
    n_pontos: int = 0

    @property
    def largura(self) -> float | None:
        """Distância, na métrica do prazo, entre os dois títulos usados (qualidade do vértice)."""
        if self.ponto_curto is None or self.ponto_longo is None:
            return None
        return self.ponto_longo.prazo - self.ponto_curto.prazo


def _ausente(motivo: Motivo, *, n_pontos: int = 0) -> Interpolacao:
    return Interpolacao(valor=None, motivo=motivo, vertice_extrapolado=True, n_pontos=n_pontos)


def interpolar(pontos: Sequence[Ponto], alvo: float) -> Interpolacao:
    """Interpola linearmente no prazo para `alvo`. **Jamais extrapola.**

    Regras, nesta ordem:

    1. sem nenhum ponto → `SEM_TITULO`;
    2. algum ponto com `prazo == alvo` → o valor **é** a taxa daquele título (`exato=True`),
       sem nenhuma aritmética — é o caso de borda que CA-023 usa para provar que a interpolação
       não introduz viés;
    3. `alvo` abaixo do menor prazo → `SEM_SUPORTE_CURTO`; acima do maior → `SEM_SUPORTE_LONGO`.
       Nos dois casos `valor=None` e `vertice_extrapolado=True` (Anti-SPEC §10.1.1);
    4. caso geral: `peso = (alvo − p_curto) / (p_longo − p_curto)` e
       `valor = taxa_curta + peso × (taxa_longa − taxa_curta)` — por construção **entre** as duas
       taxas, com `0 <= peso <= 1`.

    `pontos` com prazo repetido levanta: agregar dois títulos de mesmo vencimento é decisão de
    `pontos_da_data`, não deste núcleo.
    """
    if alvo <= 0:
        msg = f"prazo-alvo inválido: {alvo}"
        raise CurvaInconsistente(msg)
    if not pontos:
        return _ausente(Motivo.SEM_TITULO)

    ordenados = sorted(pontos, key=lambda p: p.prazo)
    prazos = [p.prazo for p in ordenados]
    if len(set(prazos)) != len(prazos):
        msg = f"prazos repetidos na seção transversal: {sorted(prazos)}"
        raise SerieInconsistente(msg)
    n = len(ordenados)

    for ponto in ordenados:
        if ponto.prazo == alvo:
            return Interpolacao(
                valor=ponto.taxa,
                motivo=None,
                vertice_extrapolado=False,
                exato=True,
                ponto_curto=ponto,
                ponto_longo=ponto,
                peso=0.0,
                n_pontos=n,
            )

    if alvo < prazos[0]:
        return _ausente(Motivo.SEM_SUPORTE_CURTO, n_pontos=n)
    if alvo > prazos[-1]:
        return _ausente(Motivo.SEM_SUPORTE_LONGO, n_pontos=n)

    posicao = int(np.searchsorted(prazos, alvo))
    curto, longo = ordenados[posicao - 1], ordenados[posicao]
    peso = (alvo - curto.prazo) / (longo.prazo - curto.prazo)
    valor = curto.taxa + peso * (longo.taxa - curto.taxa)
    return Interpolacao(
        valor=float(valor),
        motivo=None,
        vertice_extrapolado=False,
        ponto_curto=curto,
        ponto_longo=longo,
        peso=float(peso),
        n_pontos=n,
    )


def inclinacao(longo: float | None, curto: float | None) -> float | None:
    """`longo − curto` em `pp`. Qualquer ponta ausente → `None`, nunca "a ponta que existe"."""
    if longo is None or curto is None:
        return None
    return float(longo - curto)


def breakeven(nominal: float | None, real: float | None) -> float | None:
    """Inflação implícita **por razão**: `((1+n)/(1+r) − 1)`, com `n`/`r` em `%a.a.`.

    Subtração (`n − r`) é o erro que a Anti-SPEC §10.2.13 proíbe: com `n=12,5%` e `r=6,3%` ela dá
    `6,20` e a razão dá `5,8326` — 37 bps de diferença, que crescem com o nível de juros.
    """
    if nominal is None or real is None:
        return None
    return float(((1.0 + nominal / 100.0) / (1.0 + real / 100.0) - 1.0) * 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# Painel → seções transversais
# ─────────────────────────────────────────────────────────────────────────────


def carregar_painel(*, raiz: Path | None = None, caminho: Path | None = None) -> pd.DataFrame:
    """Lê e **valida** `td_painel.parquet` com `ProcessedSeriesSchema`.

    `caminho` existe para o teste apontar para o recorte de `tests/fixtures/processed/`; em
    produção quem manda é `data/processed/tesouro-direto/td_painel.parquet`.
    """
    alvo = caminho or caminho_processed(NOME_PAINEL_TESOURO, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: painel do Tesouro ausente em {alvo}. Rode "
            f"`uv run python -m apps.pipeline.extract.tesouro_direto --offline` antes."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return ProcessedSeriesSchema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não é processed_series válido: {erro}"
        raise SerieInconsistente(msg) from erro


def _contagem_de_dias_uteis(cal: Calendario) -> pd.Series:
    """Contagem **acumulada** de dias úteis por data civil do calendário.

    Existe por desempenho: `Calendario.dias_uteis_entre` é O(dias) por chamada e a curva precisa
    de ~160 mil prazos. `du(a, b) = acumulado[b] − acumulado[a]` é a contagem do intervalo
    **semiaberto** `[a, b)`, e há teste de que ela concorda com `dias_uteis_entre` ponto a ponto.
    """
    grade = cal.para_quadro()
    return pd.Series(
        grade["dia_util"].astype("int64").cumsum().shift(1, fill_value=0).to_numpy(),
        index=pd.DatetimeIndex(grade["data"]),
    )


def _prazo_em_dias_uteis(datas: pd.Series, vencimentos: pd.Series, *, cal: Calendario) -> pd.Series:
    """Dias úteis em `[data, vencimento)` — `NaN` fora da cobertura do calendário.

    Fora da cobertura é `NaN` **declarado** (e o ponto cai com `SEM_CALENDARIO`), não zero e não
    "presuma que não há feriado": é a mesma recusa de `ForaDaCoberturaDoCalendario`.
    """
    acumulado = _contagem_de_dias_uteis(cal)
    # `reset_index` antes do `map` e `set_axis` depois: o índice do recorte do painel não é
    # 0..n-1, e deixar o pandas alinhar por índice devolveria `NaN` em tudo (bug encontrado na
    # primeira rodada — por isso há teste comparando com `Calendario.dias_uteis_entre`).
    inicio = pd.Series(datas.to_numpy()).map(acumulado)
    fim = pd.Series(vencimentos.to_numpy()).map(acumulado)
    return (fim - inicio).astype("float64").set_axis(datas.index)


def pontos_do_painel(
    painel: pd.DataFrame,
    *,
    metrica: MetricaPrazo = MetricaPrazo.DIAS_CORRIDOS,
    cal: Calendario | None = None,
) -> pd.DataFrame:
    """Painel longo → `(date, familia, prazo, taxa, titulo)`, um ponto por título vivo.

    Faz, nesta ordem: decompõe o `series_id` composto de F-005 com a função pública do extrator
    (nunca um `split` reimplementado); fica só com `TAXA_VENDA` e com as famílias da curva;
    descarta título já vencido (`prazo <= 0`) e prazo sem calendário; e **agrega por média** os
    títulos de mesmo vencimento na mesma família (ver "Decisões" no topo).
    """
    if painel.empty:
        msg = "painel vazio: nada para interpolar"
        raise CurvaInconsistente(msg)

    siglas_uteis = {s for siglas in SIGLAS_DA_FAMILIA.values() for s in siglas}
    por_sigla = {s: f for f, siglas in SIGLAS_DA_FAMILIA.items() for s in siglas}

    decomposto = {sid: decompor_series_id(str(sid)) for sid in painel["series_id"].unique()}
    alvo = [
        sid
        for sid, (sigla, _, met) in decomposto.items()
        if met == METRICA_TAXA and sigla in siglas_uteis
    ]
    if not alvo:
        msg = (
            f"nenhuma série {METRICA_TAXA} das famílias {sorted(siglas_uteis)} no painel — "
            f"a curva não tem insumo"
        )
        raise CurvaInconsistente(msg)

    quadro = painel.loc[painel["series_id"].isin(alvo), ["series_id", "date", "value"]].copy()
    quadro["sigla"] = [decomposto[s][0] for s in quadro["series_id"]]
    quadro["vencimento"] = pd.to_datetime([decomposto[s][1] for s in quadro["series_id"]])
    quadro["familia"] = quadro["sigla"].map(por_sigla).astype(str)
    quadro["titulo"] = quadro["sigla"] + "_" + quadro["vencimento"].dt.strftime("%Y%m%d")

    if metrica is MetricaPrazo.DIAS_CORRIDOS:
        quadro["prazo"] = (quadro["vencimento"] - quadro["date"]).dt.days.astype("float64")
    else:
        calendario = cal or Calendario.do_parquet()
        quadro["prazo"] = _prazo_em_dias_uteis(quadro["date"], quadro["vencimento"], cal=calendario)

    vivos = quadro["prazo"] > 0
    sem_calendario = quadro["prazo"].isna()
    descartados = int((~vivos & ~sem_calendario).sum())
    if descartados:
        _log.info("%d pontos descartados por prazo <= 0 (título vencido na data base)", descartados)
    if int(sem_calendario.sum()):
        _log.info(
            "%d pontos sem prazo em dias úteis (vencimento fora de %s..%s)",
            int(sem_calendario.sum()),
            (cal or Calendario.do_parquet()).cobertura_inicio.isoformat(),
            (cal or Calendario.do_parquet()).cobertura_fim.isoformat(),
        )

    pontos = quadro.loc[vivos, ["date", "familia", "prazo", "value", "titulo"]].rename(
        columns={"value": "taxa"}
    )
    agregado = (
        pontos.groupby(["date", "familia", "prazo"], sort=True)
        .agg(
            taxa=("taxa", "mean"),
            titulo=("titulo", lambda s: "+".join(sorted(s))),
            n=("taxa", "size"),
        )
        .reset_index()
    )
    agregado["agregado"] = agregado["n"] > 1
    return agregado.drop(columns="n").sort_values(["date", "familia", "prazo"], ignore_index=True)


def pontos_da_data(pontos: pd.DataFrame, quando: pd.Timestamp, familia: Familia) -> list[Ponto]:
    """A seção transversal de uma data e família, como `list[Ponto]` para `interpolar`."""
    recorte = pontos[(pontos["date"] == quando) & (pontos["familia"] == familia.value)]
    return [
        Ponto(prazo=float(linha.prazo), taxa=float(linha.taxa), titulo=str(linha.titulo))
        for linha in recorte.itertuples()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Séries
# ─────────────────────────────────────────────────────────────────────────────


def serie_do_vertice(
    pontos: pd.DataFrame,
    vertice: Vertice,
    *,
    metrica: MetricaPrazo = MetricaPrazo.DIAS_CORRIDOS,
    datas: Sequence[pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """Quadro de **diagnóstico** do vértice: uma linha por data base, com valor e rastro.

    Toda data base do painel aparece, inclusive as sem suporte — com `value = NaN`, `motivo`
    preenchido e `vertice_extrapolado = True`. Ausência omitida é indistinguível de ausência
    esquecida, e é o que CA-024 proíbe.
    """
    alvo = vertice.alvo(metrica)
    todas = list(datas) if datas is not None else sorted(pontos["date"].unique())
    da_familia = pontos[pontos["familia"] == vertice.familia.value]
    por_data = {quando: grupo for quando, grupo in da_familia.groupby("date", sort=True)}

    linhas: list[dict[str, Any]] = []
    for quando in todas:
        grupo = por_data.get(quando)
        if grupo is None or grupo.empty:
            resultado = _ausente(Motivo.SEM_TITULO)
            agregados = 0
        else:
            pontos_dia = [
                Ponto(prazo=float(linha.prazo), taxa=float(linha.taxa), titulo=str(linha.titulo))
                for linha in grupo.itertuples()
            ]
            resultado = interpolar(pontos_dia, alvo)
            agregados = int(grupo["agregado"].sum())
        curto, longo = resultado.ponto_curto, resultado.ponto_longo
        linhas.append(
            {
                "date": quando,
                "value": np.nan if resultado.valor is None else resultado.valor,
                "motivo": None if resultado.motivo is None else resultado.motivo.value,
                "vertice_extrapolado": resultado.vertice_extrapolado,
                "exato": resultado.exato,
                "prazo_curto": None if curto is None else curto.prazo,
                "prazo_longo": None if longo is None else longo.prazo,
                "taxa_curta": None if curto is None else curto.taxa,
                "taxa_longa": None if longo is None else longo.taxa,
                "titulo_curto": None if curto is None else curto.titulo,
                "titulo_longo": None if longo is None else longo.titulo,
                "peso": resultado.peso,
                "n_pontos": resultado.n_pontos,
                "n_pontos_agregados": agregados,
            }
        )
    return pd.DataFrame(linhas, columns=list(COLUNAS_DIAGNOSTICO))


def _procedencia_do_painel(painel: pd.DataFrame) -> pd.DataFrame:
    """`(date, vintage, collected_at)` herdados do painel — o `vintage` mais novo por data base."""
    por_data = (
        painel.groupby("date", sort=True)
        .agg(vintage=("vintage", "max"), collected_at=("collected_at", "max"))
        .reset_index()
    )
    return por_data


def como_processed(
    valores: pd.DataFrame, *, series_id: str, procedencia: pd.DataFrame, unit: str
) -> pd.DataFrame:
    """`(date, value)` + procedência do painel → as 8 colunas de `ProcessedSeriesSchema`."""
    quadro = valores[["date", "value"]].merge(procedencia, on="date", how="left", validate="1:1")
    faltando = int(quadro["collected_at"].isna().sum())
    if faltando:
        msg = f"{series_id}: {faltando} datas sem procedência no painel — vintage não inventado"
        raise SerieInconsistente(msg)
    quadro["series_id"] = series_id
    quadro["source"] = FONTE
    quadro["freq"] = FREQ
    quadro["unit"] = unit
    return quadro[list(COLUNAS_PROCESSADAS)].sort_values("date", ignore_index=True)


def construir_series(
    painel: pd.DataFrame,
    *,
    metrica: MetricaPrazo = MetricaPrazo.DIAS_CORRIDOS,
    cal: Calendario | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Painel → `({series_id: processed_series}, {series_id: diagnóstico})` das 11 séries.

    As derivadas de 2º nível (`INCLINACAO_*`, `BREAKEVEN_5A`) saem dos **vértices já calculados**,
    não de uma segunda interpolação: é o que garante que `INCLINACAO_REAL_5A_3A` é exatamente
    `CURVA_REAL_5A − CURVA_REAL_3A` célula a célula, conferível por quem revisa.
    """
    pontos = pontos_do_painel(painel, metrica=metrica, cal=cal)
    datas = sorted(painel["date"].unique())
    procedencia = _procedencia_do_painel(painel)

    diagnostico = {
        series_id: serie_do_vertice(pontos, vertice, metrica=metrica, datas=datas)
        for series_id, vertice in VERTICES.items()
    }
    series: dict[str, pd.DataFrame] = {
        series_id: como_processed(
            quadro,
            series_id=series_id,
            procedencia=procedencia,
            unit=UNIDADE_POR_SERIE[series_id],
        )
        for series_id, quadro in diagnostico.items()
    }

    for derivada, id_longo, id_curto in INCLINACOES:
        quadro = _combinar(
            diagnostico[id_longo],
            diagnostico[id_curto],
            operacao=inclinacao,
            origem=(id_longo, id_curto),
        )
        diagnostico[derivada] = quadro
        series[derivada] = como_processed(
            quadro,
            series_id=derivada,
            procedencia=procedencia,
            unit=UNIDADE_POR_SERIE[derivada],
        )

    derivada, id_nominal, id_real = BREAKEVEN
    quadro = _combinar(
        diagnostico[id_nominal],
        diagnostico[id_real],
        operacao=breakeven,
        origem=(id_nominal, id_real),
    )
    diagnostico[derivada] = quadro
    series[derivada] = como_processed(
        quadro, series_id=derivada, procedencia=procedencia, unit=UNIDADE_POR_SERIE[derivada]
    )

    return series, diagnostico


def _combinar(
    esquerda: pd.DataFrame,
    direita: pd.DataFrame,
    *,
    operacao: Any,
    origem: tuple[str, str],
) -> pd.DataFrame:
    """Aplica `operacao(valor_esq, valor_dir)` data a data, propagando a ausência."""
    juntos = esquerda[["date", "value"]].merge(
        direita[["date", "value"]],
        on="date",
        how="outer",
        suffixes=("_esq", "_dir"),
        validate="1:1",
    )
    valores: list[float] = []
    motivos: list[str | None] = []
    for linha in juntos.itertuples():
        a = None if pd.isna(linha.value_esq) else float(linha.value_esq)
        b = None if pd.isna(linha.value_dir) else float(linha.value_dir)
        resultado = operacao(a, b)
        valores.append(np.nan if resultado is None else resultado)
        if resultado is None:
            ausentes = [nome for nome, v in zip(origem, (a, b), strict=True) if v is None]
            motivos.append(f"{Motivo.VERTICE_AUSENTE.value}: {'+'.join(ausentes)}")
        else:
            motivos.append(None)
    quadro = pd.DataFrame(
        {
            "date": juntos["date"],
            "value": valores,
            "motivo": motivos,
            "vertice_extrapolado": [m is not None for m in motivos],
            "exato": False,
            "prazo_curto": None,
            "prazo_longo": None,
            "taxa_curta": juntos["value_dir"],
            "taxa_longa": juntos["value_esq"],
            "titulo_curto": origem[1],
            "titulo_longo": origem[0],
            "peso": None,
            "n_pontos": 0,
            "n_pontos_agregados": 0,
        },
        columns=list(COLUNAS_DIAGNOSTICO),
    )
    return quadro.sort_values("date", ignore_index=True)


def agregar_para_trimestre(serie: pd.DataFrame, *, cal: Calendario | None = None) -> pd.DataFrame:
    """Valor trimestral = o do **último dia útil** do trimestre (CA-026), nunca a média.

    Não grava nada: a granularidade nativa é diária (Anti-SPEC §10.4.28) e quem materializa a
    grade trimestral é F-014/F-015. Esta função existe para que a convenção fique **testada**
    onde a curva é construída, e para o QA conferir um trimestre à mão.

    Se o último dia útil do trimestre não tem observação na série, a linha sai com `value` nulo —
    nunca com o valor de outro dia (isso é `ffill`, decisão de F-014, não desta feature).
    """
    calendario = cal or Calendario.do_parquet()
    por_data = serie.set_index("date")["value"]
    trimestres = pd.PeriodIndex(pd.DatetimeIndex(serie["date"]), freq="Q").unique().sort_values()
    linhas = [
        {
            "quarter": str(tri),
            "quarter_end": pd.Timestamp(
                calendario.ultimo_dia_util_do_trimestre(tri.year, tri.quarter)
            ),
        }
        for tri in trimestres
    ]
    quadro = pd.DataFrame(linhas)
    quadro["value"] = quadro["quarter_end"].map(por_data)
    return quadro


# ─────────────────────────────────────────────────────────────────────────────
# Gravação e relatório
# ─────────────────────────────────────────────────────────────────────────────


def nome_do_parquet(series_id: str) -> str:
    """Caminho relativo a `data/processed/` da série — `curva/<series_id>.parquet`."""
    return f"{PASTA_CURVA}/{series_id}.parquet"


def gravar_series(
    series: dict[str, pd.DataFrame], *, raiz: Path | None = None
) -> dict[str, tuple[Path, str]]:
    """Grava as 7 séries validadas por `ProcessedSeriesSchema` e devolve `{id: (caminho, sha256)}`.

    A validação acontece dentro de `gravar_processado_parquet` — **antes** da escrita: série fora
    do contrato não deixa rastro em `data/processed/`.
    """
    gravados: dict[str, tuple[Path, str]] = {}
    for series_id in SERIES_DE_F016:
        quadro = series[series_id]
        destino = gravar_processado_parquet(quadro, nome=nome_do_parquet(series_id), raiz=raiz)
        gravados[series_id] = (destino, sha256_de(destino.read_bytes()))
    return gravados


def conferir_catalogo(series: Iterable[str]) -> None:
    """As 11 séries existem no `series_catalog` com `fonte`, `freq` e `unit` que vamos gravar.

    É a mesma checagem que `build_raw_series.validar_procedencia` faz depois (CA-055/CA-120);
    fazê-la aqui transforma "o build do canônico quebrou" em "a curva não casa com o catálogo",
    com o nome da série na mensagem.
    """
    catalogo = {e.series_id: e for e in load_catalog()}
    problemas: list[str] = []
    for series_id in series:
        entrada = catalogo.get(series_id)
        if entrada is None:
            problemas.append(f"{series_id}: sem entrada no series_catalog")
            continue
        esperado = UNIDADE_POR_SERIE.get(series_id)
        if esperado is None:
            problemas.append(f"{series_id}: não é série desta feature (sem unidade declarada)")
            continue
        if entrada.fonte.value != FONTE:
            problemas.append(f"{series_id}: fonte={entrada.fonte.value} != {FONTE}")
        if entrada.freq.value != FREQ:
            problemas.append(f"{series_id}: freq={entrada.freq.value} != {FREQ}")
        if entrada.unit.value != esperado:
            problemas.append(
                f"{series_id}: unit={entrada.unit.value} != {esperado} (o que gravamos)"
            )
    if problemas:
        msg = "curva incoerente com o series_catalog:\n  - " + "\n  - ".join(problemas)
        raise CurvaInconsistente(msg)


def _iso(valor: Any) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    return pd.Timestamp(valor).date().isoformat()


def resumo_da_serie(quadro: pd.DataFrame, diagnostico: pd.DataFrame) -> dict[str, Any]:
    """Linhas, janela, `%` de nulos, motivos e `%` de nulos **por ano** de uma série."""
    n = len(quadro)
    nulos = int(quadro["value"].isna().sum())
    com_valor = quadro.loc[quadro["value"].notna(), "value"]
    por_ano = (
        quadro.assign(ano=pd.DatetimeIndex(quadro["date"]).year, nulo=quadro["value"].isna())
        .groupby("ano")["nulo"]
        .mean()
        .mul(100)
        .round(2)
    )
    motivos = diagnostico["motivo"].dropna()
    largura = (diagnostico["prazo_longo"] - diagnostico["prazo_curto"]).dropna()
    return {
        "n_linhas": n,
        "data_min": _iso(quadro["date"].min()),
        "data_max": _iso(quadro["date"].max()),
        "n_nulos": nulos,
        "pct_nulos": round(nulos / n * 100, 4) if n else None,
        "valor_min": None if com_valor.empty else round(float(com_valor.min()), 6),
        "valor_max": None if com_valor.empty else round(float(com_valor.max()), 6),
        "motivos": {str(k): int(v) for k, v in motivos.value_counts().sort_index().items()},
        "pct_nulos_por_ano": {str(ano): float(p) for ano, p in por_ano.items()},
        "n_exatos": int(diagnostico["exato"].sum()),
        "n_pontos_agregados": int(diagnostico["n_pontos_agregados"].sum()),
        "largura_interpolacao_dias": (
            None
            if largura.empty
            else {
                "mediana": round(float(largura.median()), 2),
                "maxima": round(float(largura.max()), 2),
            }
        ),
    }


#: Início da janela de 20 anos do projeto (PRD §7) — é sobre ela que CA-025 mede a cobertura.
INICIO_DA_JANELA = pd.Timestamp("2006-01-01")


def cobertura(serie: pd.DataFrame, *, inicio: pd.Timestamp = INICIO_DA_JANELA) -> dict[str, Any]:
    """`%` de datas base com valor, de `inicio` em diante — a medida que CA-025 cobra.

    Mede sobre as datas base **do painel** (os dias em que o Tesouro publicou preço), não sobre
    todos os dias úteis do calendário: a diferença entre as duas grades é assunto de F-014, e
    misturar as duas aqui esconderia qual das duas causas tirou o valor.
    """
    recorte = serie[pd.DatetimeIndex(serie["date"]) >= inicio]
    n = len(recorte)
    com_valor = int(recorte["value"].notna().sum())
    return {
        "inicio": _iso(inicio),
        "n_datas_base": n,
        "n_com_valor": com_valor,
        "pct_com_valor": round(com_valor / n * 100, 2) if n else None,
    }


def cobertura_por_vertice(
    painel: pd.DataFrame,
    *,
    metrica: MetricaPrazo = MetricaPrazo.DIAS_CORRIDOS,
    cal: Calendario | None = None,
) -> dict[str, Any]:
    """Cobertura dos vértices do catálogo (1, 3 e 5 anos) **mais** os de 10 anos, não gravados.

    É a tabela que responde, com número, qual vértice curto satisfaz CA-025 ("inclinação real em
    >= 95% dos dias úteis de 2006-2026"): a 5a-3a cobre 95,25% e a 5a-1a, 60,53%. Foi ela que
    sustentou **D-i**. Nada aqui é gravado como série — é medição; os 10 anos entram só para deixar
    o caso de CA-024 quantificado em vez de apenas afirmado.
    """
    pontos = pontos_do_painel(painel, metrica=metrica, cal=cal)
    datas = sorted(painel["date"].unique())
    todos = {**VERTICES, **VERTICES_FORA_DO_CATALOGO}
    quadros = {
        sid: serie_do_vertice(pontos, v, metrica=metrica, datas=datas) for sid, v in todos.items()
    }
    vertices = {
        sid: {
            "familia": todos[sid].familia.value,
            "anos": todos[sid].anos,
            "no_catalogo": sid in VERTICES,
            **cobertura(quadro),
        }
        for sid, quadro in quadros.items()
    }
    inclinacoes: dict[str, Any] = {}
    for familia in Familia:
        longo = f"CURVA_{familia.value}_5A"
        for anos in (1, 3):
            curto = f"CURVA_{familia.value}_{anos}A"
            quadro = _combinar(
                quadros[longo], quadros[curto], operacao=inclinacao, origem=(longo, curto)
            )
            inclinacoes[f"INCLINACAO_{familia.value}_5A_{anos}A"] = cobertura(quadro)
    return {"vertices": vertices, "inclinacoes": inclinacoes}


def versao_curva() -> str:
    """`sha256` deste arquivo — o `fonte_versao` desta camada (RF-048/CA-121)."""
    return sha256_de(Path(__file__).read_bytes())


@dataclass(frozen=True, slots=True)
class ResultadoCurva:
    """Resumo de uma execução — alimenta a evidência de dados do Feature Contract."""

    metrica: MetricaPrazo
    caminho_painel: Path
    sha256_painel: str
    series: dict[str, tuple[Path, str]] = field(default_factory=dict)
    resumos: dict[str, dict[str, Any]] = field(default_factory=dict)
    cobertura: dict[str, Any] = field(default_factory=dict)
    caminho_relatorio: Path | None = None

    def resumo(self) -> str:
        """Uma linha ASCII para o stdout da CLI (o console do Windows é cp1252)."""
        partes = [
            f"{sid}: {r['n_linhas']} linhas {r['data_min']}->{r['data_max']} "
            f"nulos={r['pct_nulos']}%"
            for sid, r in self.resumos.items()
        ]
        return f"metrica={self.metrica.value} | " + " | ".join(partes)


def montar_relatorio(
    resultado: ResultadoCurva, *, canarios: list[dict[str, Any]]
) -> dict[str, Any]:
    """O JSON auditável de `data/processed/curva/`. **Sem relógio** — hash estável entre rodadas."""
    return {
        "feature": "F-016",
        "versao_curva": versao_curva(),
        "metrica_prazo": resultado.metrica.value,
        "dias_por_ano": resultado.metrica.dias_por_ano,
        "metrica_taxa": METRICA_TAXA,
        "familias": {f.value: list(s) for f, s in SIGLAS_DA_FAMILIA.items()},
        "painel": {
            "arquivo": resultado.caminho_painel.name,
            "sha256": resultado.sha256_painel,
        },
        "series": {
            sid: {
                "sha256": resultado.series[sid][1] if sid in resultado.series else None,
                **resultado.resumos[sid],
            }
            for sid in resultado.resumos
        },
        "cobertura_de_2006_em_diante": resultado.cobertura,
        "canarios": canarios,
    }


def canarios_conferiveis(
    diagnostico: dict[str, pd.DataFrame], *, datas: Sequence[str], series: Sequence[str]
) -> list[dict[str, Any]]:
    """As linhas de diagnóstico de datas escolhidas — a conta da interpolação, aberta.

    É o material da revisão numérica independente: com os dois títulos, os dois prazos, as duas
    taxas e o peso, qualquer pessoa reproduz o vértice numa planilha a partir do CSV bruto.
    """
    saida: list[dict[str, Any]] = []
    for series_id in series:
        quadro = diagnostico[series_id]
        for dia in datas:
            linha = quadro[quadro["date"] == pd.Timestamp(dia)]
            if linha.empty:
                continue
            registro = linha.iloc[0].to_dict()
            registro["date"] = _iso(registro["date"])
            registro["series_id"] = series_id
            saida.append({chave: _serializavel(valor) for chave, valor in registro.items()})
    return saida


def _serializavel(valor: Any) -> Any:
    """`NaN`/`NaT` → `None`; o resto passa. `str` e `bool` saem antes do `isna` de propósito."""
    if isinstance(valor, str | bool):
        return valor
    return None if pd.isna(valor) else valor


#: Datas dos canários do relatório: a primeira base do painel de 2006, uma do meio e a última.
DATAS_CANARIO: tuple[str, ...] = ("2006-01-02", "2016-01-04", "2026-10-09")


def construir(
    *,
    offline: bool = True,
    raiz: Path | None = None,
    caminho_painel: Path | None = None,
    metrica: MetricaPrazo = MetricaPrazo.DIAS_CORRIDOS,
    cal: Calendario | None = None,
    gravar: bool = True,
) -> ResultadoCurva:
    """Caminho completo: painel → vértices → derivadas → 7 Parquets + relatório.

    `offline` existe para simetria com os extratores e é o **único** comportamento: a fonte desta
    camada é o disco (nenhuma chamada de rede em nenhum caminho).
    """
    del offline  # a fonte é sempre o disco; o parâmetro existe para simetria da CLI
    alvo = caminho_painel or caminho_processed(NOME_PAINEL_TESOURO, raiz=raiz)
    painel = carregar_painel(raiz=raiz, caminho=caminho_painel)
    conferir_catalogo(SERIES_DE_F016)

    series, diagnostico = construir_series(painel, metrica=metrica, cal=cal)
    gravados = gravar_series(series, raiz=raiz) if gravar else {}
    resumos = {sid: resumo_da_serie(series[sid], diagnostico[sid]) for sid in SERIES_DE_F016}

    resultado = ResultadoCurva(
        metrica=metrica,
        caminho_painel=alvo,
        sha256_painel=sha256_de(alvo.read_bytes()),
        series=gravados,
        resumos=resumos,
        cobertura=cobertura_por_vertice(painel, metrica=metrica, cal=cal),
    )
    caminho_relatorio: Path | None = None
    if gravar:
        canarios = canarios_conferiveis(diagnostico, datas=DATAS_CANARIO, series=SERIES_DE_F016)
        destino = caminho_camada(Camada.PROCESSED, raiz=raiz) / PASTA_CURVA / NOME_RELATORIO
        garantir_diretorio(destino.parent)
        destino.write_text(
            json.dumps(montar_relatorio(resultado, canarios=canarios), indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        caminho_relatorio = destino
    _log.info("F-016: %s", resultado.resumo())
    return ResultadoCurva(
        metrica=resultado.metrica,
        caminho_painel=resultado.caminho_painel,
        sha256_painel=resultado.sha256_painel,
        series=resultado.series,
        resumos=resultado.resumos,
        cobertura=resultado.cobertura,
        caminho_relatorio=caminho_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    analisador = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.curva",
        description=(
            "F-016: vértices fixos interpolados (1a e 5a, real e nominal), inclinação e "
            "breakeven, de data/processed/tesouro-direto/ para data/processed/curva/."
        ),
    )
    analisador.add_argument(
        "--offline",
        action="store_true",
        help="sem rede (é o único comportamento: a fonte desta camada é o disco)",
    )
    analisador.add_argument(
        "--metrica-prazo",
        choices=[m.value for m in MetricaPrazo],
        default=MetricaPrazo.DIAS_CORRIDOS.value,
        help=(
            "como medir o prazo na interpolação; 'dias_uteis' só cobre vencimento dentro do "
            "calendário ANBIMA (2001-2030) e devolve NULL fora dele"
        ),
    )
    return analisador


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` = 7 séries gravadas; `1` = falha ruidosa, nada gravado."""
    args = _parser().parse_args(argv)
    configurar_logging()
    try:
        resultado = construir(offline=args.offline, metrica=MetricaPrazo(args.metrica_prazo))
    except ErroDeExtracao as exc:
        print(f"FALHA: {exc}", file=sys.stderr)  # noqa: T201 - é a saída da CLI
        return 1
    print(resultado.resumo())  # noqa: T201 - é a saída da CLI
    for series_id, (caminho, digest) in resultado.series.items():
        print(f"{series_id}: {caminho} sha256={digest[:12]}")  # noqa: T201
    if resultado.caminho_relatorio is not None:
        print(f"relatorio: {resultado.caminho_relatorio}")  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
