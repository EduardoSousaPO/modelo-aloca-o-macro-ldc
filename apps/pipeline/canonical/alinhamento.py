"""F-014 — alinhamento trimestral de `raw_series`: fim de período + ffill <= 5 d.u. **Classe C.**

Materializa `data/canonical/alinhado_trimestral.parquet`: uma linha por `(series_id, quarter)`
dizendo **qual observação da série representa aquele trimestre** e, quando nenhuma representa,
**por quê**. É a régua temporal de todo o canônico — `macro_quarterly` (F-015), a curva (F-016) e
`asset_returns_quarterly` (F-017) saem daqui, não de `raw_series` direto.

O que este módulo faz, e **só** isto:

1. **Monta a grade** dos 83 trimestres `2006Q1..2026Q3`: `quarter_end` = **último dia útil**
   pelo calendário ANBIMA (ADR-006 §(b).2, CA-065), com os casos-armadilha vindos do calendário
   e não de regra reimplementada (3T2006 cai em 29/09 porque 30/09 é sábado; 1T2013 cai em 28/03
   porque 29/03 é Sexta-feira Santa).
2. **Escolhe a régua por série** (`grade`): `bancaria` para série diária de dia útil, `corrido`
   para série diária de calendário corrido (SGS 432, a meta Selic, que publica todo dia civil) e
   `civil` para série mensal/trimestral, cujo `date` já é o **fim de período civil** (convenção
   D-a). A grade é **uma só** — `quarter_end` é idêntico para todas as linhas do trimestre; é a
   **opção (a) de D-h**, registrada em `docs/wiki/context/F-014.md §4`.
3. **Pega a observação**: a última com `date <= date_alvo` e `value` não nulo.
4. **Mede o forward-fill** em dias úteis da ANBIMA e o aplica **até 5** (ADR-006 §(b).8, CA-066).
   Acima de 5, a célula vira `NULL` com `motivo_nulo` e a lacuna fica **registrada** em
   `date_ultima_obs`/`lacuna_dias_uteis` (CA-067) — nunca interpolada, nunca `0`.
5. **Respeita o painel desbalanceado**: nenhuma linha antes do `data_inicio_observada` do
   `series_catalog` materializado (CA-063) — ICON não existe em 1T2006, IFIX não existe antes de
   4T2010.
6. **Falha ruidosamente** em data duplicada com valor divergente ou série com mais de uma
   frequência (CA-068), em vez de escolher uma das duas em silêncio.

O que este módulo **não** faz: nenhum retorno (F-017), nenhuma deflação, nenhuma interpolação de
vértice (F-016), nenhuma coluna wide (F-015) e nenhuma regra de lag de divulgação — esta tabela é
a materialização **`revised`** (último `vintage` de cada série); o `asof` é F-018.

**Séries fora deste build, por decisão:** toda série `source=DERIVADO` (`SP500_BRL`, `ACWI_BRL` e,
quando F-016 as produzir, `CURVA_*`/`INCLINACAO_*`/`BREAKEVEN_5A`). Elas nascem de uma derivação
que tem a sua própria convenção de alinhamento e **chamam `alinhar_series` depois** — a função é
pública exatamente para isso. O motivo fica no `relatorio_alinhamento.json`, não só aqui.

**Sem rede, sempre.** As entradas são `data/canonical/raw_series.parquet`,
`data/canonical/series_catalog.parquet` e `data/processed/calendario/dias_uteis_anbima.parquet`.

**Idempotente por construção.** Nada aqui lê o relógio: `vintage`/`collected_at` vêm do dado
(D-b) e o relatório carrega `versao_build` (`sha256` deste arquivo), não hora de geração. Duas
rodadas sobre a mesma entrada produzem Parquet e relatório byte-idênticos (RF-048/CA-121).

Referências: SPEC RF-023 (CA-065..068) + RF-026/RF-047 · ADR-006 §(b).2/§(b).8 ·
`docs/contracts/CONTRACTS.md §8` · `docs/wiki/modules/calendario.md §B` (D-h) ·
`docs/wiki/modules/canonical.md` · `DECISIONS_LOG §2.1` (D-a, D-b, D-h).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    ErroCanonico,
    caminhos_dos_componentes,
    exigir_series,
    validar_frequencia_nativa,
    validar_procedencia,
    validar_sem_mistura_de_fontes,
)
from apps.pipeline.canonical.build_raw_series import (
    versao_build as _hash_dos_componentes,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import (
    caminho_canonical,
    garantir_diretorio,
    raiz_repo,
    sha256_de,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from apps.pipeline.extract.calendario_anbima import Calendario
from packages.shared.schemas import (
    COLUNAS_ALINHADO,
    GRADE_BANCARIA,
    GRADE_CIVIL,
    GRADE_CORRIDO,
    LIMITE_FFILL_DIAS_UTEIS,
    MOTIVO_LACUNA_ACIMA_DO_LIMITE,
    MOTIVO_SEM_OBSERVACAO,
    PK_ALINHADO,
    AlinhadoTrimestralSchema,
    RawSeriesSchema,
    load_catalog,
    quarters_da_janela,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────

NOME_ALINHADO = "alinhado_trimestral.parquet"
NOME_RELATORIO = "relatorio_alinhamento.json"

#: Os módulos que determinam o conteúdo de `alinhado_trimestral`, **nesta ordem** — base de
#: `versao_build`. Não é "o pipeline inteiro": é este módulo + o contrato da tabela + o builder de
#: onde vêm as quatro guardas + o calendário (que decide todo `quarter_end`) + o catálogo como
#: dado (que decide `grade`, `source` e `unit`). Mudar qualquer um muda o Parquet, então tem de
#: mudar a versão — é a correção P1-1 do QA da Onda 2, aplicada aqui desde o dia 1.
MODULOS_DO_ALINHAMENTO: tuple[str, ...] = (
    "apps.pipeline.canonical.alinhamento",
    "packages.shared.schemas.alinhado_trimestral",
    "apps.pipeline.canonical.build_raw_series",
    "apps.pipeline.extract.calendario_anbima",
    "packages.shared.schemas.series_catalog_data",
)

CALENDARIO_CORRIDO = "corrido"
"""Valor de `SeriesCatalogEntry.calendario` que manda alinhar no último dia **civil**."""


@lru_cache(maxsize=1)
def series_de_calendario_corrido() -> frozenset[str]:
    """As séries `freq=D` que o **catálogo** declara `calendario='corrido'` — nada hard-coded.

    A coluna `calendario` entrou no catálogo em 2026-10-11 (P1-2 do QA da Onda 2) exatamente para
    que esta decisão não fosse uma lista digitada aqui: hoje a única é `BCB_SGS_432` (a meta Selic
    publica o mesmo valor todos os dias, sábado e domingo inclusive — `DECISIONS_LOG §2.2`), e uma
    série nova de calendário corrido passa a cair na grade certa **sem** mudança neste módulo.
    O teste de contrato confere que esta derivação, a coluna do catálogo e
    `SERIES_DIARIAS_DE_CALENDARIO` do extrator (F-003) continuam dizendo a mesma coisa.
    """
    return frozenset(
        entrada.series_id for entrada in load_catalog() if entrada.calendario == CALENDARIO_CORRIDO
    )


#: `source` que este build **não** alinha, com o motivo (vai para o relatório).
FONTES_FORA_DO_ALINHAMENTO: dict[str, str] = {
    "DERIVADO": (
        "Série derivada (SP500_BRL/ACWI_BRL por PTAX; CURVA_*/INCLINACAO_*/BREAKEVEN_5A por "
        "interpolação de vértice). A derivação tem convenção própria de data e de lacuna, e é a "
        "feature dona dela (F-016 para a curva, F-017 para os retornos em BRL) que chama "
        "`alinhar_series` sobre o seu resultado. Alinhar aqui fixaria a régua antes da derivação "
        "existir."
    ),
}

#: O esqueleto que esta grade precisa para ser útil — ausência para o build com
#: `BLOQUEADO — FONTE INDISPONÍVEL` (CA-076) em vez de entregar painel mais magro em silêncio.
SERIES_EXIGIDAS: tuple[str, ...] = (
    "ANBIMA_IMAB",
    "ANBIMA_IMAGERAL",
    "ANBIMA_IRFM",
    "B3_IBOV",
    "BCB_SGS_1",
    "BCB_SGS_12",
    "BCB_SGS_432",
    "BCB_SGS_433",
    "SIDRA_1737_V63",
)


class GradeIndefinida(ErroCanonico):
    """A série não se encaixa em nenhuma das três grades (`freq` desconhecida)."""


class DatasDuplicadasNaSerie(ErroCanonico):
    """Mesma `(series_id, date)` com `value` divergente no mesmo `vintage` (CA-068)."""


class InicioDeSerieIncoerente(ErroCanonico):
    """O `data_inicio_observada` do catálogo não bate com o que `raw_series` tem em disco.

    Catálogo dizendo um início **posterior** ao dado real esconderia trimestres legítimos do
    painel; dizendo um início anterior, deixaria entrar linha sem observação nenhuma. As duas
    coisas são bug de materialização do catálogo (F-013), não dado — e param o build.
    """


# ─────────────────────────────────────────────────────────────────────────────
# A grade dos 83 trimestres
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Trimestre:
    """Um trimestre da janela, com as duas datas de fim de período que o projeto usa.

    `quarter_end` é o **último dia útil bancário** (ANBIMA) — a grade única de ADR-006 §(b).2 e a
    chave de junção de `macro_quarterly`/`asset_returns_quarterly`. `fim_civil` é o último dia
    civil, que é o alvo das grades `corrido` e `civil`. Nos 24 trimestres em que as duas datas
    divergem, a diferença é de 1 a 3 dias civis e **nunca** de dia útil.
    """

    quarter: str
    quarter_end: date
    fim_civil: date

    def alvo(self, grade: str) -> date:
        """A data que uma série daquela `grade` busca neste trimestre."""
        if grade == GRADE_BANCARIA:
            return self.quarter_end
        if grade in (GRADE_CORRIDO, GRADE_CIVIL):
            return self.fim_civil
        msg = f"grade desconhecida: {grade!r}"
        raise GradeIndefinida(msg)


def grade_de_trimestres(
    calendario: Calendario, *, quarters: Sequence[str] | None = None
) -> tuple[Trimestre, ...]:
    """Os 83 `Trimestre` da janela (ou os `quarters` pedidos), com o fim de período medido.

    O último dia útil vem de `Calendario.ultimo_dia_util_do_trimestre`, que anda **para trás** a
    partir do último dia civil: nenhuma regra de feriado é reimplementada aqui (CA-065).
    """
    rotulos = tuple(quarters) if quarters is not None else quarters_da_janela()
    saida: list[Trimestre] = []
    for rotulo in rotulos:
        periodo = pd.Period(rotulo, freq="Q")
        fim_civil = periodo.end_time.date()
        saida.append(
            Trimestre(
                quarter=str(periodo),
                quarter_end=calendario.ultimo_dia_util_do_trimestre(periodo.year, periodo.quarter),
                fim_civil=fim_civil,
            )
        )
    return tuple(saida)


def grade_da_serie(series_id: str, freq: str, *, corridos: frozenset[str] | None = None) -> str:
    """Qual régua a série usa: `bancaria`, `corrido` ou `civil` (ver docstring do módulo).

    `corridos` existe para o teste cravar o conjunto; em produção quem manda é o catálogo.
    """
    if freq == "D":
        declarados = corridos if corridos is not None else series_de_calendario_corrido()
        return GRADE_CORRIDO if series_id in declarados else GRADE_BANCARIA
    if freq in ("M", "Q", "A"):
        return GRADE_CIVIL
    msg = (
        f"{series_id}: freq={freq!r} não tem grade trimestral definida; as grades são "
        f"D (bancaria/corrido) e M/Q/A (civil)"
    )
    raise GradeIndefinida(msg)


def dias_uteis_de_lacuna(calendario: Calendario, origem: date, alvo: date) -> int:
    """Dias úteis no intervalo **semiaberto** `(origem, alvo]` — o passo de forward-fill.

    Semiaberto porque é o que "quantos dias úteis andei para trás" significa: observação **no**
    alvo dá `0`; a véspera útil dá `1` (o caso D-h da B3 no 4º trimestre); e alvo em fim de semana
    com observação na sexta também dá `0`, porque nenhum dia útil foi pulado — a data real fica em
    `date_obs` de qualquer jeito.

    Quando `origem` é anterior à cobertura do calendário, a contagem começa na cobertura: o número
    passa a ser um **piso** da lacuna, e um piso já muito acima de 5 é tudo de que a regra de
    ADR-006 §(b).8 precisa para decidir `NULL`. É o único caminho em que a coluna não é exata, e
    só existe para série cujo histórico morre antes de 2001.
    """
    if origem >= alvo:
        return 0
    inicio = max(origem + timedelta(days=1), calendario.cobertura_inicio)
    if inicio > alvo:
        return 0
    return calendario.dias_uteis_entre(inicio, alvo)


# ─────────────────────────────────────────────────────────────────────────────
# Preparação da entrada: vintage e índice temporal
# ─────────────────────────────────────────────────────────────────────────────


def selecionar_vintage(quadro: pd.DataFrame) -> pd.DataFrame:
    """Mantém, por série, só o **último** `vintage` — a materialização `revised`.

    `raw_series` guarda as safras lado a lado de propósito (D-b): é o que faz uma revisão do
    IBGE coexistir com o retrato anterior. Alinhar sem escolher a safra criaria duas linhas para a
    mesma `(series_id, quarter)` e quebraria a PK; escolher a **mais recente** é a definição de
    `revised`, e a variante `asof` (que escolhe por data de divulgação) é F-018.
    """
    if quadro.empty:
        return quadro
    vintages = quadro.groupby("series_id")["vintage"].transform("max")
    manter = quadro["vintage"].isna() | (quadro["vintage"] == vintages) | vintages.isna()
    descartadas = int((~manter).sum())
    if descartadas:
        _log.info(
            "vintage: %d linha(s) de safra anterior fora da materializacao revised", descartadas
        )
    return quadro.loc[manter].copy()


def validar_indice_temporal(quadro: pd.DataFrame) -> pd.DataFrame:
    """CA-068: ordena, remove duplicata **idêntica** e **levanta** na divergente.

    Também exige uma única `freq` por série: série que muda de frequência no meio não tem grade
    definida, e escolher uma delas em silêncio é como um trimestre inteiro sairia errado.
    """
    if quadro.empty:
        return quadro

    multiplas = quadro.groupby("series_id")["freq"].nunique()
    confusas = sorted(str(s) for s in multiplas[multiplas > 1].index)
    if confusas:
        msg = f"{len(confusas)} série(s) com mais de uma freq: {confusas[:10]}"
        raise SerieInconsistente(msg)

    chave = ["series_id", "date"]
    duplicadas = quadro.duplicated(subset=chave, keep=False)
    if bool(duplicadas.any()):
        candidatas = quadro.loc[duplicadas]
        divergentes = candidatas.groupby(chave, dropna=False)["value"].nunique(dropna=False)
        conflito = divergentes[divergentes > 1]
        if len(conflito) > 0:
            amostra = [f"{a} {pd.Timestamp(b).date()}" for a, b in list(conflito.index)[:5]]
            msg = (
                f"{len(conflito)} data(s) duplicada(s) com `value` divergente no mesmo vintage — "
                f"amostra: {amostra}. Escolher uma em silêncio esconderia revisão de fonte ou bug "
                f"de extrator (CA-068)."
            )
            raise DatasDuplicadasNaSerie(msg)
        _log.info(
            "dedup: %d data(s) repetida(s) e idêntica(s) removida(s)", int(duplicadas.sum()) // 2
        )

    ordenado = quadro.drop_duplicates(subset=chave, keep="first")
    if not bool(ordenado.sort_values(chave, kind="mergesort").index.equals(ordenado.index)):
        _log.info("entrada fora de ordem: reordenando por (series_id, date)")
    return ordenado.sort_values(chave, kind="mergesort").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# O alinhamento
# ─────────────────────────────────────────────────────────────────────────────


def alinhar_series(
    raw: pd.DataFrame,
    *,
    calendario: Calendario,
    inicio_por_serie: Mapping[str, Any],
    trimestres: Sequence[Trimestre] | None = None,
    fonte_versao: str | None = None,
) -> pd.DataFrame:
    """Alinha uma tabela longa no contrato de `raw_series` para a grade trimestral.

    É a **função pública** que F-015/F-016/F-017 chamam: recebe `raw_series` (ou a fatia dela que
    interessa, ou uma série derivada já no mesmo contrato), devolve `AlinhadoTrimestralSchema`
    validado. Não escreve nada em disco.

    `inicio_por_serie` é o início real de cada série (`data_inicio_observada` do catálogo
    materializado): é ele que mantém o painel **desbalanceado** em vez de inventar linha antes do
    início (CA-063). Série ausente do mapa levanta — "não sei quando começa" nunca pode virar
    "começa em 2006".
    """
    faltando = [c for c in RawSeriesSchema.to_schema().columns if c not in raw.columns]
    if faltando:
        msg = f"colunas ausentes para alinhar: {faltando}"
        raise SerieInconsistente(msg)

    grade_tri = tuple(trimestres) if trimestres is not None else grade_de_trimestres(calendario)
    versao = fonte_versao if fonte_versao is not None else versao_build()
    preparado = validar_indice_temporal(selecionar_vintage(raw))

    linhas: list[dict[str, Any]] = []
    for series_id, grupo in preparado.groupby("series_id", sort=True):
        sid = str(series_id)
        if sid not in inicio_por_serie:
            msg = (
                f"{sid}: sem `data_inicio_observada` em inicio_por_serie — o painel desbalanceado "
                f"depende dele (CA-063); materialize o series_catalog antes (F-013)"
            )
            raise InicioDeSerieIncoerente(msg)
        inicio = pd.Timestamp(inicio_por_serie[sid])
        freq = str(grupo["freq"].iloc[0])
        grade = grade_da_serie(sid, freq)
        metadado = {
            "series_id": sid,
            "grade": grade,
            "freq": freq,
            "unit": str(grupo["unit"].iloc[0]),
            "source": str(grupo["source"].iloc[0]),
            "vintage": grupo["vintage"].max(),
            "collected_at": grupo["collected_at"].max(),
            "data_inicio_serie": inicio,
            "fonte_versao": versao,
        }

        com_valor = grupo.loc[grupo["value"].notna()]
        datas = pd.DatetimeIndex(com_valor["date"]).to_numpy()
        valores = com_valor["value"].to_numpy()

        for tri in grade_tri:
            alvo = tri.alvo(grade)
            alvo_ts = pd.Timestamp(alvo)
            if inicio > alvo_ts:
                continue  # painel desbalanceado: a série ainda não existia (CA-063)

            posicao = int(np.searchsorted(datas, np.datetime64(alvo_ts), side="right")) - 1
            if posicao < 0:
                ultima_obs: pd.Timestamp | Any = pd.NaT
                lacuna = 0
                date_obs: pd.Timestamp | Any = pd.NaT
                valor: float | None = None
                ffill = 0
                motivo: str | None = MOTIVO_SEM_OBSERVACAO
            else:
                ultima_obs = pd.Timestamp(datas[posicao])
                lacuna = dias_uteis_de_lacuna(calendario, ultima_obs.date(), alvo)
                if lacuna > LIMITE_FFILL_DIAS_UTEIS:
                    date_obs, valor, ffill = pd.NaT, None, 0
                    motivo = MOTIVO_LACUNA_ACIMA_DO_LIMITE
                else:
                    date_obs, valor, ffill = ultima_obs, float(valores[posicao]), lacuna
                    motivo = None

            linhas.append(
                {
                    **metadado,
                    "quarter": tri.quarter,
                    "quarter_end": pd.Timestamp(tri.quarter_end),
                    "date_alvo": alvo_ts,
                    "date_obs": date_obs,
                    "value": valor,
                    "ffill_dias_uteis": ffill,
                    "date_ultima_obs": ultima_obs,
                    "lacuna_dias_uteis": lacuna,
                    "motivo_nulo": motivo,
                }
            )

    if not linhas:
        msg = (
            "nenhuma linha alinhada: nenhuma série tem observação dentro da janela "
            f"{quarters_da_janela()[0]}..{quarters_da_janela()[-1]}"
        )
        raise FonteIndisponivel(f"BLOQUEADO — FONTE INDISPONÍVEL: {msg}")

    tabela = pd.DataFrame(linhas).loc[:, list(COLUNAS_ALINHADO)]
    tabela["motivo_nulo"] = tabela["motivo_nulo"].astype("string")
    tabela = tabela.sort_values(by=list(PK_ALINHADO), kind="mergesort").reset_index(drop=True)
    return AlinhadoTrimestralSchema.validate(tabela, lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# Entradas do build
# ─────────────────────────────────────────────────────────────────────────────


def _ler_canonical(nome: str, *, schema: Any, raiz: Path | None) -> pd.DataFrame:
    """Lê um Parquet de `data/canonical/` e **valida** com o seu schema antes de usar."""
    alvo = caminho_canonical(nome, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.build_raw_series --offline` antes (F-013)."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return schema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz {schema.Config.name}: {erro}"
        raise SerieInconsistente(msg) from erro


COLUNAS_DO_CATALOGO_CONSUMIDAS: tuple[str, ...] = (
    "series_id",
    "presente_no_processed",
    "data_inicio_observada",
)
"""O que esta camada lê do catálogo materializado — e **só** isto.

A validação completa com `SeriesCatalogMaterializedSchema` é o portão de **escrita** de F-013
(RF-026/CA-053). Revalidá-la na leitura transformaria um acréscimo legítimo de coluna no catálogo
(como `calendario`, em 2026-10-11) numa falha desta feature, sem que o dado tivesse mudado. O que
protege o alinhamento é mais forte e específico: as três colunas existem, não têm nulo onde não
podem ter, e `data_inicio_observada` é **conferida linha a linha** contra `raw_series` em
`inicio_observado_por_serie`.
"""


def _ler_catalogo_materializado(*, raiz: Path | None) -> pd.DataFrame:
    """Lê `series_catalog.parquet` e exige as colunas que o painel desbalanceado usa."""
    alvo = caminho_canonical(NOME_CATALOGO, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.build_raw_series --offline` antes (F-013)."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    faltando = [c for c in COLUNAS_DO_CATALOGO_CONSUMIDAS if c not in quadro.columns]
    if faltando:
        msg = f"{alvo.name} sem as colunas que o alinhamento consome: {faltando}"
        raise SerieInconsistente(msg)
    if bool(quadro["series_id"].isna().any()) or bool(quadro["series_id"].duplicated().any()):
        msg = f"{alvo.name}: series_id nulo ou repetido — o catálogo não é indexável"
        raise SerieInconsistente(msg)
    return quadro


def fatiar_para_alinhamento(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Separa o que este build alinha do que fica para F-016/F-017, com o motivo registrado."""
    fora = raw["source"].isin(FONTES_FORA_DO_ALINHAMENTO.keys())
    excluidas = [
        {
            "series_id": str(sid),
            "source": str(src),
            "motivo": FONTES_FORA_DO_ALINHAMENTO[str(src)],
        }
        for sid, src in sorted(
            raw.loc[fora, ["series_id", "source"]].drop_duplicates().itertuples(index=False)
        )
    ]
    return raw.loc[~fora].copy(), excluidas


def inicio_observado_por_serie(
    catalogo: pd.DataFrame, raw: pd.DataFrame
) -> dict[str, pd.Timestamp]:
    """`{series_id: data_inicio_observada}` do catálogo materializado, **conferido** contra o dado.

    A conferência existe porque o catálogo é um artefato derivado: se ele e `raw_series` saírem de
    builds diferentes, o painel desbalanceado passa a ser decidido por um número velho. Divergência
    levanta `InicioDeSerieIncoerente` em vez de alinhar com a régua errada.
    """
    presente = catalogo.loc[catalogo["presente_no_processed"]]
    mapa = {
        str(sid): pd.Timestamp(inicio)
        for sid, inicio in zip(
            presente["series_id"], presente["data_inicio_observada"], strict=True
        )
    }
    medido = raw.groupby("series_id")["date"].min()
    problemas = [
        f"{sid}: catálogo {mapa.get(str(sid))} != raw_series {pd.Timestamp(valor).date()}"
        for sid, valor in medido.items()
        if str(sid) not in mapa or mapa[str(sid)] != pd.Timestamp(valor)
    ]
    if problemas:
        msg = (
            "`data_inicio_observada` do series_catalog divergente de raw_series:\n  - "
            + "\n  - ".join(problemas[:15])
            + "\n  Rode o build de F-013 de novo: os dois artefatos têm de vir da mesma rodada."
        )
        raise InicioDeSerieIncoerente(msg)
    return mapa


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DO_ALINHAMENTO` — o `fonte_versao` desta camada.

    Hash de arquivos, não do processo (RF-047/CA-121): é o que faz "o artefato mudou porque o
    código mudou" ser distinguível de "mudou porque o dado mudou". O conjunto — e não só este
    arquivo — porque editar o calendário, o contrato da tabela ou o catálogo muda o resultado sem
    tocar aqui, e `versao_build` igual com Parquet diferente é o pior dos dois mundos (P1-1 do QA
    da Onda 2). Reusa `caminhos_dos_componentes`/`versao_build` de F-013: um só algoritmo de hash
    de componentes na camada canônica.
    """
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DO_ALINHAMENTO))


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────


def _iso(valor: Any) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    return pd.Timestamp(valor).date().isoformat()


def _contagem(serie: pd.Series) -> dict[str, int]:
    """`value_counts` serializável e ordenado — sem `int64` solto no JSON."""
    return {str(k): int(v) for k, v in serie.value_counts().sort_index().items()}


def montar_relatorio(
    *,
    alinhado: pd.DataFrame,
    trimestres: Sequence[Trimestre],
    hashes: dict[str, Any],
    excluidas: Sequence[dict[str, str]],
) -> dict[str, Any]:
    """`relatorio_alinhamento.json` — **sem relógio**, para que dois builds sejam idênticos.

    O bloco que a revisão numérica independente usa é `ffill_por_serie` + `ffill_por_trimestre`:
    é ali que D-h aparece como número (as 11 séries da B3 com `ffill = 1` nos 20 quartos
    trimestres de 2006 a 2025) em vez de como afirmação.
    """
    com_ffill = alinhado.loc[alinhado["ffill_dias_uteis"] > 0]
    nulos = alinhado.loc[alinhado["value"].isna()]

    ffill_por_serie = {
        str(sid): _contagem(grupo["ffill_dias_uteis"])
        for sid, grupo in com_ffill.groupby("series_id", sort=True)
    }
    ffill_por_trimestre = {
        str(q): {
            "celulas": int(len(grupo)),
            "series": sorted(str(s) for s in grupo["series_id"].unique()),
            "dias_uteis": _contagem(grupo["ffill_dias_uteis"]),
        }
        for q, grupo in com_ffill.groupby("quarter", sort=True)
    }

    por_serie: list[dict[str, Any]] = []
    for sid, grupo in alinhado.groupby("series_id", sort=True):
        nulos_da_serie = grupo.loc[grupo["value"].isna()]
        por_serie.append(
            {
                "series_id": str(sid),
                "grade": str(grupo["grade"].iloc[0]),
                "freq": str(grupo["freq"].iloc[0]),
                "unit": str(grupo["unit"].iloc[0]),
                "source": str(grupo["source"].iloc[0]),
                "data_inicio_serie": _iso(grupo["data_inicio_serie"].iloc[0]),
                "trimestres": int(len(grupo)),
                "primeiro_quarter": str(grupo["quarter"].min()),
                "ultimo_quarter": str(grupo["quarter"].max()),
                "celulas_nulas": int(len(nulos_da_serie)),
                "quarters_nulos": sorted(str(q) for q in nulos_da_serie["quarter"]),
                "motivos_nulos": _contagem(nulos_da_serie["motivo_nulo"].astype(str)),
                "celulas_com_ffill": int((grupo["ffill_dias_uteis"] > 0).sum()),
                "ffill_maximo": int(grupo["ffill_dias_uteis"].max()),
                "lacuna_maxima_dias_uteis": int(grupo["lacuna_dias_uteis"].max()),
            }
        )

    return {
        "feature": "F-014",
        "versao_build": versao_build(),
        "decisao_d_h": {
            "escolha": "(a) grade bancária única com ffill de ate 5 d.u. (default do ADR-006)",
            "efeito_medido": (
                "toda serie da B3 carrega ffill_dias_uteis = 1 no 4o trimestre, porque a B3 nao "
                "negocia no ultimo dia util bancario do ano (B3 subconjunto de ANBIMA em 69 datas)"
            ),
            "celulas_com_ffill": int(len(com_ffill)),
            "trimestres_com_ffill": int(com_ffill["quarter"].nunique()),
            "series_com_ffill": int(com_ffill["series_id"].nunique()),
        },
        "grade": {
            "n_trimestres": len(trimestres),
            "primeiro": trimestres[0].quarter,
            "ultimo": trimestres[-1].quarter,
            "trimestres_em_que_o_dia_util_difere_do_dia_civil": sum(
                1 for t in trimestres if t.quarter_end != t.fim_civil
            ),
            "fins_de_periodo": [
                {
                    "quarter": t.quarter,
                    "quarter_end": t.quarter_end.isoformat(),
                    "fim_civil": t.fim_civil.isoformat(),
                }
                for t in trimestres
            ],
        },
        "alinhado_trimestral": {
            "arquivo": NOME_ALINHADO,
            "linhas": int(len(alinhado)),
            "series": int(alinhado["series_id"].nunique()),
            "trimestres": int(alinhado["quarter"].nunique()),
            "celulas_nulas": int(len(nulos)),
            "pct_celulas_nulas": round(float(alinhado["value"].isna().mean()) * 100.0, 6),
            "linhas_por_grade": _contagem(alinhado["grade"]),
            "linhas_por_freq": _contagem(alinhado["freq"]),
            "linhas_por_source": _contagem(alinhado["source"]),
            "distribuicao_ffill_dias_uteis": _contagem(alinhado["ffill_dias_uteis"]),
            "motivos_nulos": _contagem(nulos["motivo_nulo"].astype(str)),
            "date_obs_min": _iso(alinhado["date_obs"].min()),
            "date_obs_max": _iso(alinhado["date_obs"].max()),
            **hashes,
        },
        "ffill_por_serie": ffill_por_serie,
        "ffill_por_trimestre": ffill_por_trimestre,
        "series": por_serie,
        "series_exigidas": list(SERIES_EXIGIDAS),
        "series_fora_do_alinhamento": list(excluidas),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoAlinhamento:
    """O que o build produziu — o CLI imprime, o teste inspeciona, o QA confere."""

    alinhado: pd.DataFrame
    relatorio: dict[str, Any]
    trimestres: tuple[Trimestre, ...]
    caminho_alinhado: Path
    caminho_relatorio: Path
    excluidas: tuple[dict[str, str], ...] = ()


def construir(
    *,
    raiz: Path | None = None,
    calendario: Calendario | None = None,
    quarters: Sequence[str] | None = None,
) -> ResultadoAlinhamento:
    """Reconstrói `data/canonical/alinhado_trimestral.parquet` de ponta a ponta.

    Sem rede, sem estado, sem efeito fora de `data/canonical/`. `calendario` e `quarters` existem
    para o teste cravar uma grade pequena e um calendário de fixture; em produção os dois saem do
    disco e dos 83 trimestres do contrato.
    """
    raw = _ler_canonical(NOME_RAW_SERIES, schema=RawSeriesSchema, raiz=raiz)
    catalogo = _ler_catalogo_materializado(raiz=raiz)
    declarado = load_catalog()

    alvo, excluidas = fatiar_para_alinhamento(raw)
    # As quatro guardas públicas de F-013, na entrada desta camada: procedência resolvível no
    # catálogo, frequência nativa, uma fonte por série e o pacote mínimo presente (CA-055,
    # CA-058, CA-077, CA-076). Nenhuma é reimplementada aqui.
    validar_procedencia(alvo, declarado)
    validar_frequencia_nativa(alvo, declarado)
    validar_sem_mistura_de_fontes(alvo)
    exigir_series(alvo, declarado, SERIES_EXIGIDAS)

    cal = calendario if calendario is not None else Calendario.do_parquet(raiz=raiz)
    trimestres = grade_de_trimestres(cal, quarters=quarters)
    inicio = inicio_observado_por_serie(catalogo, alvo)

    alinhado = alinhar_series(alvo, calendario=cal, inicio_por_serie=inicio, trimestres=trimestres)

    destino = caminho_canonical(NOME_ALINHADO, raiz=raiz)
    garantir_diretorio(destino.parent)
    alinhado.to_parquet(destino, index=False)
    corpo = destino.read_bytes()
    _log.info(
        "gravado %s (%d linhas, %d series, sha256=%s…)",
        destino.name,
        len(alinhado),
        alinhado["series_id"].nunique(),
        sha256_de(corpo)[:12],
    )

    relatorio = montar_relatorio(
        alinhado=alinhado,
        trimestres=trimestres,
        hashes={"sha256": sha256_de(corpo), "bytes": len(corpo)},
        excluidas=excluidas,
    )
    caminho_relatorio = caminho_canonical(NOME_RELATORIO, raiz=raiz)
    caminho_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ResultadoAlinhamento(
        alinhado=alinhado,
        relatorio=relatorio,
        trimestres=trimestres,
        caminho_alinhado=destino,
        caminho_relatorio=caminho_relatorio,
        excluidas=tuple(excluidas),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.alinhamento",
        description=(
            "Materializa data/canonical/alinhado_trimestral.parquet a partir de "
            "data/canonical/raw_series.parquet + o calendario ANBIMA. Nunca toca a rede."
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Aceito por simetria com os extratores e sem efeito: esta camada só lê o disco e "
            "nunca faz requisição."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = build feito; `1` = falha explícita e nada gravado."""
    _parser().parse_args(argv)
    configurar_logging()
    try:
        resultado = construir()
    except ErroDeExtracao as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 1

    bloco = resultado.relatorio["alinhado_trimestral"]
    ffill = resultado.relatorio["decisao_d_h"]
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{NOME_ALINHADO}: {bloco['linhas']} linhas | {bloco['series']} series | "
        f"{bloco['trimestres']} trimestres | nulos {bloco['celulas_nulas']} "
        f"({bloco['pct_celulas_nulas']}%) | sha256 {bloco['sha256']}"
    )
    print(
        f"grade: {resultado.relatorio['grade']['n_trimestres']} trimestres | "
        f"ffill {bloco['distribuicao_ffill_dias_uteis']}"
    )
    print(
        f"D-h (a): {ffill['celulas_com_ffill']} celulas com ffill em "
        f"{ffill['trimestres_com_ffill']} trimestres, {ffill['series_com_ffill']} series"
    )
    for excluida in resultado.excluidas:
        print(f"fora do alinhamento: {excluida['series_id']} ({excluida['source']})")
    print(f"relatorio: {resultado.caminho_relatorio}")
    print(f"versao_build: {resultado.relatorio['versao_build']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
