"""F-018 — materialização **`asof`** de `macro_quarterly`: a regra anti-look-ahead. **Classe C.**

`macro_quarterly.parquet` (F-015) é a materialização **`revised`**: cada coluna do trimestre `T`
traz o valor que a série **de hoje** tem para `T`, sem perguntar quando aquele valor foi
**divulgado**. É legítimo para descrever a história e é **proibido** usar como operacional
(Anti-SPEC §10.2.7). Esta feature produz a outra metade do par:

| Artefato | O que é |
|---|---|
| `macro_quarterly_asof.parquet` | 83 × 42, mesmo `MacroQuarterlySchema`, `lag_adjusted=True` |
| `macro_quarterly_asof_provenance.parquet` | *long*, 1 linha por célula + `date_obs` e `lag_dias` |
| `relatorio_asof.json` | lag por coluna, % de trimestres com `asof != revised`, `max abs dif` |

## A regra, em uma linha

> O valor de `(T, coluna)` é o da **última observação cuja data de divulgação
> (`date_obs + lag_divulgacao_dias`) é menor ou igual ao `quarter_end` de `T`** — o último dia
> **útil** de `T`, que é quando a decisão é tomada.

Três consequências, que são exatamente os exemplos da metodologia §5.1:

- **PIB** (`lag = 60`, trimestral): o PIB de `T` só sai ~60 dias depois do fim de `T`, então a
  linha `T` carrega o **nível de `T-1`** — e, porque a mesma regra vale para `T-4`, o `pib_yoy`
  de `T` em `asof` é o `pib_yoy` de `T-1` em `revised`. É o canário 1.
- **IPCA** (`lag = 10`, mensal): o IPCA de setembro sai em meados de outubro, então `3T2026`
  carrega o acumulado 12 meses de **agosto/2026**, não o de setembro. É o canário 2 — e é por
  isso que a regra tem de ser aplicada **observação a observação**, não trimestre a trimestre:
  "o IPCA de agosto" não é célula de nenhum trimestre da grade.
- **Focus** (`lag = 0`, diário): a mediana da coleta da semana X é conhecida na semana X. As
  colunas `focus_*` saem **idênticas** às de `revised`. É o canário 3.

## O que é reaproveitado de F-015, e por quê

`apps/pipeline/canonical/macro_quarterly.py` está **congelado** nesta onda (`AGENTS.md §13`) e sua
assinatura não aceita um parâmetro de materialização — `LAG_ADJUSTED` é constante de módulo. Em vez
de alterá-lo, este módulo **importa as funções puras** dele e aplica a defasagem **antes**:

1. `observacoes_asof` (aqui) escolhe, por `(trimestre, série)`, a observação divulgada em tempo —
   é a **única** peça nova de régua, e ela é conferida contra a de F-015 em
   `tests/unit/test_canonical_asof.py` (`lag = 0` + alvo no fim de `T` reproduz
   `observacoes_de_fim_de_periodo` célula a célula);
2. `deslocar_acumulados` (aqui) faz o mesmo para os **fluxos** (`ipca_tri`, `cdi_tri`,
   `selic_over_tri`), que não são leitura de fim de período: a acumulação de `T` só é conhecida
   quando o último mês/dia de `T` é publicado;
3. **`montar_macro` de F-015 é chamada sem adaptação**, com os níveis deslocados. É o que garante
   que **toda derivada é recalculada** sobre o nível defasado — a/a por razão, aceleração,
   tendência de 20 trimestres, hiato, `juro_real_exante` por Fisher, surpresas — e **nenhuma** é
   copiada da tabela `revised`. Copiar derivada seria o bug silencioso desta feature: `pib_yoy`
   de `T` em `asof` tem de ser `v[T-1]/v[T-5] - 1`, nunca `v[T]/v[T-4] - 1` deslocado de lugar.

A mesma montagem é rodada **duas vezes** na mesma rodada — sem defasagem e com — e a versão sem
defasagem é conferida **célula a célula contra `macro_quarterly.parquet` em disco**
(`conferir_contra_revised_em_disco`). É o diff numérico de classe C na direção que importa: se a
reprodução do `revised` bate bit a bit com o artefato de F-015, a **única** diferença entre as duas
materializações publicadas é a defasagem de divulgação, e não um caminho de código diferente.

## O que esta feature **não** faz

- **não classifica regime.** O % de trimestres que trocam de **rótulo** (CA-073/CA-074) é de
  **F-019**, que roda a V1 sobre as duas materializações. O relatório daqui publica um **proxy
  diagnóstico** do eixo da V1 (sinal de `ibcbr_gap` × sinal de `ipca_12m_delta`, ADR-001 §4),
  rotulado como proxy, para que o teste de sanidade obrigatório da metodologia §5.1 exista desde
  já — e com o texto de CA-074 quando passa de 25%;
- **não escolhe safra (`vintage`).** `asof` tem duas pernas: a defasagem de **divulgação** e a
  **revisão** retroativa da fonte (o IBGE revisa o PIB). `raw_series` hoje tem **uma** safra por
  série (medido: 0 de 62 séries com mais de um `vintage`), então a perna de revisão é
  **degenerada** — não há retrato antigo para escolher. Está declarado no relatório
  (`limitacoes.vintage_unico`) em vez de ser apresentado como resolvido;
- **não toca `macro_quarterly.parquet`** nem a procedência de F-015: grava arquivos de nome
  próprio, ao lado.

**Sem rede, sem relógio, idempotente.** Entradas: `raw_series.parquet` e `series_catalog.parquet` de
`data/canonical/`, mais `data/processed/{calendario,focus}/`. `versao_build` é o `sha256` do
**conjunto** `MODULOS_DO_ASOF`.

Referências: SPEC RF-025 (CA-072, CA-073, CA-074), CA-010 · Anti-SPEC §10.2.7 ·
`docs/contracts/CONTRACTS.md §3`, §3.1 · `docs/research/metodologia-regimes-macro.md §5.1`, §2 ·
`docs/wiki/context/F-015.md §4` · `docs/wiki/context/F-018.md` (regra por coluna + revisão).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.canonical.alinhamento import (
    Trimestre,
    dias_uteis_de_lacuna,
    fatiar_para_alinhamento,
    grade_da_serie,
    inicio_observado_por_serie,
    selecionar_vintage,
    validar_indice_temporal,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    ErroCanonico,
    caminhos_dos_componentes,
    exigir_series,
    validar_procedencia,
)
from apps.pipeline.canonical.build_raw_series import (
    versao_build as _hash_dos_componentes,
)
from apps.pipeline.canonical.macro_quarterly import (
    ACUMULADAS,
    CATALOGO_DO_FOCUS,
    MODULOS_DO_MACRO,
    NOME_MACRO,
    ORIGENS,
    SERIES_EXIGIDAS,
    UNIDADES,
    Acumulado,
    acumular_por_trimestre,
    carregar_focus,
    fatiar_curva,
    grade_estendida,
    insumos_da_coluna,
    metadado_de_procedencia,
    montar_macro,
    observacoes_de_fim_de_periodo,
    series_de_nivel,
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
    COLUNAS_RASTREAVEIS,
    LIMIAR_ACELERACAO_PP,
    LIMIAR_CRESCIMENTO_PP,
    LIMITE_FFILL_DIAS_UTEIS,
    MacroQuarterlyAsofProvenanceSchema,
    MacroQuarterlySchema,
    RawSeriesSchema,
    RegimeV1,
    load_catalog,
    quarters_da_janela,
)
from packages.shared.schemas.regimes import LIMIAR_TROCA_REGIME_INOPERANTE

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Iterable, Mapping, Sequence

    from packages.shared.schemas import SeriesCatalogEntry

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────

NOME_ASOF = "macro_quarterly_asof.parquet"
NOME_ASOF_PROVENANCE = "macro_quarterly_asof_provenance.parquet"
NOME_RELATORIO_ASOF = "relatorio_asof.json"

#: Esta é a materialização **`asof`** — a de decisão. A `revised` é F-015.
LAG_ADJUSTED = True
MATERIALIZACAO = "asof"

#: Os módulos que determinam o conteúdo da `asof`, **nesta ordem** — base de `versao_build`.
#: É o conjunto de F-015 (de onde vem toda a montagem e todo o contrato) **mais este arquivo**,
#: que é quem decide a defasagem. Mudar qualquer um muda o Parquet, logo tem de mudar a versão.
MODULOS_DO_ASOF: tuple[str, ...] = ("apps.pipeline.canonical.asof", *MODULOS_DO_MACRO)

#: Quantos dias **úteis** separam, tipicamente, duas observações consecutivas de cada frequência.
#: Entra na tolerância de frescor: com defasagem de divulgação, a publicação mais recente
#: disponível no fim de `T` pode ser de até **um período** atrás — o que, sem esta folga, o limite
#: de 5 d.u. de F-014 recusaria, zerando colunas inteiras em silêncio.
PASSO_EM_DIAS_UTEIS: dict[str, int] = {"D": 1, "M": 21, "Q": 63, "A": 252}

#: Teto do deslocamento de um **fluxo** (`ipca_tri`, `cdi_tri`, `selic_over_tri`). Na prática é 0
#: ou 1; o teto existe para que uma série morta não seja arrastada por anos como se fosse
#: "a última conhecida".
MAX_DESLOCAMENTO_TRIMESTRES = 4

MOTIVO_NADA_DIVULGADO = "nada_divulgado_ate_o_fim_do_trimestre"
MOTIVO_DIVULGACAO_VELHA = "ultima_divulgacao_fora_da_tolerancia_de_frescor"

#: Comparação `asof` × `revised` é **exata**: as duas saem das mesmas funções sobre os mesmos
#: números, então "igual" aqui quer dizer bit a bit, não "igual dentro de 1e-9".
TOLERANCIA_IGUALDADE = 0.0


class LagDesconhecido(ErroCanonico):
    """Série consumida sem `lag_divulgacao_dias` resolvível no catálogo.

    Não é caso de default: assumir `lag = 0` para uma série que não se sabe quando é divulgada
    produziria exatamente o look-ahead silencioso que esta feature existe para eliminar
    (Anti-SPEC §10.2.7). O build para.
    """


class ReproducaoDivergente(ErroCanonico):
    """A reprodução do `revised` não bate com `macro_quarterly.parquet` em disco.

    Se a mesma montagem, sobre as mesmas entradas e sem defasagem, não reproduz o artefato de
    F-015 célula a célula, então a diferença entre as duas materializações publicadas **não** é só
    a defasagem de divulgação — e nada do que este módulo diria sobre o `asof` seria verificável.
    O build para (classe C).
    """


# ─────────────────────────────────────────────────────────────────────────────
# A defasagem: do catálogo, nunca digitada
# ─────────────────────────────────────────────────────────────────────────────


def lags_de_divulgacao(
    catalogo: Iterable[SeriesCatalogEntry] | None = None, *, series: Sequence[str] | None = None
) -> dict[str, int]:
    """`{series_id: lag_divulgacao_dias}` — a tabela de defasagem desta feature.

    Sai **inteira** do `series_catalog` (`SeriesCatalogEntry.lag_divulgacao_dias`): PIB 60,
    IBC-Br 45, IPCA 10, Focus/Selic/curva/câmbio 0. Nenhum número de defasagem é escrito neste
    módulo — mudar a defasagem de uma série é editar o catálogo, que está em `MODULOS_DO_ASOF` e
    por isso muda `versao_build`.

    As séries materializadas do Focus (`FOCUS_I12_IPCA_N`, `FOCUS_A_SELIC_H0`, …) **não** são
    entradas do catálogo por decisão de F-010 (**D-k**): herdam o lag do *EntitySet* que as
    registra (`CATALOGO_DO_FOCUS`). `series`, quando passado, exige que **todas** tenham lag — é
    assim que uma série nova entra no `asof` pela porta da frente ou para o build.
    """
    entradas = list(catalogo) if catalogo is not None else list(load_catalog())
    mapa = {e.series_id: int(e.lag_divulgacao_dias) for e in entradas}
    for subserie, entrada in CATALOGO_DO_FOCUS.items():
        if entrada in mapa:
            mapa.setdefault(subserie, mapa[entrada])
    if series is None:
        return mapa
    faltando = sorted({str(s) for s in series} - mapa.keys())
    if faltando:
        msg = (
            f"{len(faltando)} série(s) sem `lag_divulgacao_dias` resolvível no catálogo: "
            f"{faltando[:10]}. `asof` não assume 0 por omissão — assumir seria reintroduzir o "
            f"look-ahead que a materialização existe para eliminar (Anti-SPEC §10.2.7)."
        )
        raise LagDesconhecido(msg)
    return {sid: mapa[sid] for sid in sorted({str(s) for s in series})}


def data_de_divulgacao(date_obs: date, lag_dias: int) -> date:
    """`date_obs + lag_divulgacao_dias` — a data em que a observação passou a ser conhecida.

    Dias **civis**, não úteis: é como a defasagem é publicada pela fonte ("o PIB sai ~60 dias após
    o fim do trimestre", "o IPCA sai em meados do mês seguinte") e como o catálogo a registra. É
    uma aproximação declarada — o calendário real de divulgação do IBGE/BCB por release não está
    no projeto —, e é **conservadora** no que importa: arredondar o lag para cima nunca cria
    look-ahead, só pode descartar informação que já era conhecida.
    """
    if lag_dias < 0:
        msg = f"lag_divulgacao_dias negativo ({lag_dias}): divulgação antes da referência"
        raise ValueError(msg)
    return date_obs + timedelta(days=lag_dias)


def tolerancia_de_frescor(freq: str) -> int:
    """Quantos dias úteis de "velhice" de **divulgação** uma célula `asof` pode ter.

    `LIMITE_FFILL_DIAS_UTEIS` (5, a regra de F-014) **mais** um período da série. O termo do
    período não é folga: com defasagem, a publicação mais recente que existe no fim de `T` é, por
    construção, de até um período atrás (o IBC-Br de julho é o mais novo que se conhece no fim de
    setembro). Sem ele, `ibcbr_*` sairia 100% nula — e nula por regra de frescor, não por ausência
    de dado, que é a pior forma de errar: silenciosa e com cara de ausência legítima.
    """
    if freq not in PASSO_EM_DIAS_UTEIS:
        msg = f"freq={freq!r} sem passo declarado em PASSO_EM_DIAS_UTEIS"
        raise SerieInconsistente(msg)
    return LIMITE_FFILL_DIAS_UTEIS + PASSO_EM_DIAS_UTEIS[freq]


# ─────────────────────────────────────────────────────────────────────────────
# A régua `asof`: observação a observação
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CelulaAsof:
    """Uma célula `asof`: o valor, a observação de onde veio e a data em que ela foi divulgada."""

    quarter: str
    series_id: str
    date_alvo: date
    date_obs: date | None
    value: float | None
    lag_dias: int
    date_divulgacao: date | None
    lacuna_dias_uteis: int
    deslocamento_dias: int | None
    motivo_nulo: str | None


def observacoes_asof(
    raw: pd.DataFrame,
    *,
    calendario: Calendario,
    trimestres: Sequence[Trimestre],
    inicio_por_serie: Mapping[str, Any],
    lags: Mapping[str, int],
) -> pd.DataFrame:
    """A régua de F-014/F-015 reexpressa com **data de divulgação** no lugar de data de referência.

    Para cada `(trimestre, série)`, escolhe a **última** observação com
    `date + lag_divulgacao_dias <= quarter_end` — o último dia **útil** de `T`, que é o momento em
    que a decisão é tomada (SPEC §2: "`asof` = só informação conhecida até o último DU de T").

    Três diferenças de `observacoes_de_fim_de_periodo`, e nenhuma a mais:

    1. **o alvo é sempre `quarter_end`**, nunca o fim civil. Na `revised`, série mensal/trimestral
       mira o último dia **civil** (D-a), o que em 24 dos 83 trimestres é 1 a 3 dias depois do
       último dia útil; F-015 declarou essa folga como data de *referência*, não look-ahead. Aqui
       ela simplesmente deixa de existir: o corte é o dia da decisão;
    2. **o corte é sobre a divulgação**, não sobre a referência;
    3. **a tolerância de frescor** é `tolerancia_de_frescor(freq)` e não os 5 d.u. secos — ver a
       docstring daquela função.

    Com `lags` todo zero e séries de grade bancária, esta função **reproduz**
    `observacoes_de_fim_de_periodo` célula a célula; é o que
    `test_lag_zero_reproduz_a_regua_de_f015` trava.

    Devolve um quadro *long* com `(quarter, series_id, date_alvo, date_obs, value, lag_dias,
    date_divulgacao, lacuna_dias_uteis, deslocamento_dias, motivo_nulo)` — superconjunto do que
    `montar_macro` consome (`quarter`, `series_id`, `value`, `date_obs`).
    """
    faltando = [c for c in RawSeriesSchema.to_schema().columns if c not in raw.columns]
    if faltando:
        msg = f"colunas ausentes para a régua asof: {faltando}"
        raise SerieInconsistente(msg)

    preparado = validar_indice_temporal(selecionar_vintage(raw))
    linhas: list[CelulaAsof] = []
    for series_id, grupo in preparado.groupby("series_id", sort=True):
        sid = str(series_id)
        if sid not in inicio_por_serie:
            msg = f"{sid}: sem `data_inicio_observada` em inicio_por_serie"
            raise SerieInconsistente(msg)
        if sid not in lags:
            msg = f"{sid}: sem `lag_divulgacao_dias` em lags"
            raise LagDesconhecido(msg)
        lag = int(lags[sid])
        freq = str(grupo["freq"].iloc[0])
        grade_da_serie(sid, freq)  # valida a grade declarada (levanta GradeIndefinida)
        tolerancia = tolerancia_de_frescor(freq)
        inicio = pd.Timestamp(inicio_por_serie[sid])
        com_valor = grupo.loc[grupo["value"].notna()]
        datas = pd.DatetimeIndex(com_valor["date"]).to_numpy()
        valores = com_valor["value"].to_numpy()

        for tri in trimestres:
            corte = tri.quarter_end
            # `date + lag <= corte` <=> `date <= corte - lag`: o limite é o corte trazido para
            # trás pela defasagem, e a busca segue sendo um `searchsorted` sobre as datas de
            # referência (nada é reindexado nem reordenado).
            limite = corte - timedelta(days=lag)
            limite_ts = pd.Timestamp(limite)
            if inicio > limite_ts:
                continue
            posicao = int(np.searchsorted(datas, np.datetime64(limite_ts), side="right")) - 1
            if posicao < 0:
                linhas.append(
                    CelulaAsof(
                        tri.quarter,
                        sid,
                        corte,
                        None,
                        None,
                        lag,
                        None,
                        0,
                        None,
                        MOTIVO_NADA_DIVULGADO,
                    )
                )
                continue
            observada = pd.Timestamp(datas[posicao]).date()
            divulgada = data_de_divulgacao(observada, lag)
            lacuna = dias_uteis_de_lacuna(calendario, divulgada, corte)
            if lacuna > tolerancia:
                linhas.append(
                    CelulaAsof(
                        tri.quarter,
                        sid,
                        corte,
                        None,
                        None,
                        lag,
                        divulgada,
                        lacuna,
                        None,
                        MOTIVO_DIVULGACAO_VELHA,
                    )
                )
                continue
            linhas.append(
                CelulaAsof(
                    tri.quarter,
                    sid,
                    corte,
                    observada,
                    float(valores[posicao]),
                    lag,
                    divulgada,
                    lacuna,
                    (corte - observada).days,
                    None,
                )
            )

    quadro = pd.DataFrame([asdict(c) for c in linhas])
    if quadro.empty:
        msg = "nenhuma observação divulgada em tempo na grade pedida"
        raise FonteIndisponivel(f"BLOQUEADO — FONTE INDISPONÍVEL: {msg}")
    return quadro.sort_values(["series_id", "quarter"], kind="mergesort").reset_index(drop=True)


def deslocar_acumulados(
    acumulados: Mapping[str, Mapping[str, Acumulado]],
    *,
    lags: Mapping[str, int],
    trimestres: Sequence[Trimestre],
    maximo: int = MAX_DESLOCAMENTO_TRIMESTRES,
) -> dict[str, dict[str, Acumulado]]:
    """A mesma regra, aplicada aos **fluxos** — que não são leitura de fim de período.

    `ipca_tri`, `cdi_tri` e `selic_over_tri` são o produto geométrico **dentro** do trimestre
    (F-015 §3.4): a acumulação de `T'` só passa a ser conhecida quando a **última** observação de
    `T'` é divulgada, isto é em `date_obs_max(T') + lag`. Então a célula `asof` de `T` é a
    acumulação do **último** `T' <= T` cuja divulgação cabe até `quarter_end(T)`.

    Efeito medido com o catálogo de hoje: `cdi_tri` e `selic_over_tri` (diárias, `lag = 0`) **não
    deslocam**; `ipca_tri` (mensal, `lag = 10`) desloca **um** trimestre — o IPCA de março só sai
    em abril, logo a inflação do trimestre que se conhece no fim de `T` é a de `T-1`.

    Deslocar é diferente de copiar: o `Acumulado` devolvido continua sendo o do trimestre de
    **origem** (com o seu `quarter`, as suas contagens e o seu `date_obs_max`), apenas indexado no
    trimestre de **destino**. É isso que mantém a procedência honesta — a célula diz de que
    trimestre ela veio.
    """
    rotulos = [t.quarter for t in trimestres]
    fim_de = {t.quarter: t.quarter_end for t in trimestres}
    saida: dict[str, dict[str, Acumulado]] = {}
    for series_id, por_quarter in acumulados.items():
        if series_id not in lags:
            msg = f"{series_id}: sem `lag_divulgacao_dias` em lags"
            raise LagDesconhecido(msg)
        lag = int(lags[series_id])
        mapa: dict[str, Acumulado] = {}
        for indice, rotulo in enumerate(rotulos):
            corte = fim_de[rotulo]
            for passos in range(min(maximo, indice) + 1):
                candidato = por_quarter.get(rotulos[indice - passos])
                if candidato is None or candidato.value is None:
                    continue
                if candidato.date_obs_max is None:
                    continue
                if data_de_divulgacao(candidato.date_obs_max, lag) <= corte:
                    mapa[rotulo] = candidato
                    break
        saida[series_id] = mapa
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# Lag por coluna: derivado dos insumos de F-015, nunca digitado
# ─────────────────────────────────────────────────────────────────────────────


def lag_da_coluna(coluna: str, lags: Mapping[str, int]) -> int:
    """O `lag_divulgacao_dias` que **manda** na coluna: o maior entre os seus insumos.

    Uma coluna derivada de duas séries só é conhecida quando a **mais lenta** das duas é
    divulgada: `surpresa_pib` (PIB, 60) contra Focus (0) é conhecida 60 dias depois do trimestre,
    não no dia. Pegar o máximo é o limite **superior** correto — e é o número que a procedência
    publica em `lag_dias`, para que `date_obs + lag_dias <= quarter_end` seja uma conta
    conservadora e verificável no Parquet.

    Coluna sem fonte (`ipca_meta`, `embi_br_fim`, `termos_troca_yoy`) devolve `0`: não há célula,
    logo não há defasagem a declarar.
    """
    valores = [int(lags[i.series_id]) for i in insumos_da_coluna(coluna) if i.series_id in lags]
    if coluna in ACUMULADAS:
        series_id = ACUMULADAS[coluna]
        if series_id in lags:
            valores.append(int(lags[series_id]))
    return max(valores) if valores else 0


def lags_por_coluna(lags: Mapping[str, int]) -> dict[str, int]:
    """`{coluna: lag que manda}` para todas as `COLUNAS_RASTREAVEIS` — o mapa do relatório."""
    return {coluna: lag_da_coluna(coluna, lags) for coluna in COLUNAS_RASTREAVEIS}


# ─────────────────────────────────────────────────────────────────────────────
# Comparação `asof` × `revised`
# ─────────────────────────────────────────────────────────────────────────────


def _como_float(serie: pd.Series) -> pd.Series:
    """A coluna em `float64` — booleana inclusive, para comparar `vertice_extrapolado`."""
    if serie.dtype == bool:
        return serie.astype("float64")
    return pd.to_numeric(serie, errors="coerce").astype("float64")


def comparar_materializacoes(
    revised: pd.DataFrame, asof: pd.DataFrame, *, lags: Mapping[str, int]
) -> pd.DataFrame:
    """Coluna a coluna: lag aplicado, quantos trimestres diferem, `max abs dif`, se é idêntica.

    "Diferem" inclui **trocar de nulo para valor e vice-versa**: é a diferença mais fácil de
    perder de vista e a mais consequente (o `asof` de `2026Q3` tem PIB — o de `2026Q2` — onde o
    `revised` tem nulo, e o `revised` tem `ipca_tri` de `2026Q3` onde o `asof` ainda não pode
    ter). Comparação **exata** (`TOLERANCIA_IGUALDADE = 0`): as duas tabelas saem das mesmas
    funções sobre os mesmos números.
    """
    if list(revised["quarter"]) != list(asof["quarter"]):
        msg = "as duas materializações não têm a mesma grade de trimestres"
        raise ReproducaoDivergente(msg)
    por_coluna = lags_por_coluna(lags)
    linhas: list[dict[str, Any]] = []
    for coluna in COLUNAS_RASTREAVEIS:
        esquerda = _como_float(revised[coluna])
        direita = _como_float(asof[coluna])
        ambos_nulos = esquerda.isna() & direita.isna()
        diferenca = (direita - esquerda).abs()
        diferem = ~ambos_nulos & ~(diferenca <= TOLERANCIA_IGUALDADE)
        linhas.append(
            {
                "column": coluna,
                "lag_dias": por_coluna[coluna],
                "unidade": UNIDADES[coluna],
                "series_id": ORIGENS[coluna].series_id,
                "n_trimestres": int(len(revised)),
                "n_diferentes": int(diferem.sum()),
                "pct_diferentes": round(100.0 * float(diferem.sum()) / len(revised), 2),
                "max_abs_dif": (
                    round(float(diferenca[~ambos_nulos].max()), 9)
                    if bool(diferenca[~ambos_nulos].notna().any())
                    else None
                ),
                "nulos_revised": int(esquerda.isna().sum()),
                "nulos_asof": int(direita.isna().sum()),
                "identica": bool(not diferem.any()),
            }
        )
    return pd.DataFrame(linhas)


def conferir_contra_revised_em_disco(
    revised_reproduzido: pd.DataFrame, *, raiz: Path | None = None
) -> dict[str, Any]:
    """Confere a reprodução do `revised` contra `macro_quarterly.parquet`, célula a célula.

    É o **diff numérico de classe C** desta feature. Sem esta conferência, "a única diferença
    entre `asof` e `revised` é a defasagem" seria uma afirmação sobre dois caminhos de código
    diferentes; com ela, é uma medida. Divergência numérica levanta `ReproducaoDivergente`.

    `fonte_versao` é ignorado de propósito (o conjunto de módulos da `asof` inclui este arquivo,
    logo o hash é **outro** por construção) e `lag_adjusted` também (é a flag que distingue as
    duas). Artefato ausente devolve `{"conferido": False}` com o motivo — é o caminho do CI em
    árvore limpa, não um erro.
    """
    alvo = caminho_canonical(NOME_MACRO, raiz=raiz)
    if not alvo.is_file():
        return {
            "conferido": False,
            "motivo": f"{alvo.name} não existe nesta árvore (rode F-015); nada a conferir",
        }
    em_disco = MacroQuarterlySchema.validate(pd.read_parquet(alvo), lazy=True)
    if list(em_disco["quarter"]) != list(revised_reproduzido["quarter"]):
        msg = "a grade de trimestres do artefato de F-015 difere da reproduzida aqui"
        raise ReproducaoDivergente(msg)

    problemas: list[str] = []
    maior = 0.0
    conferidas = 0
    for coluna in COLUNAS_RASTREAVEIS:
        disco = _como_float(em_disco[coluna])
        meu = _como_float(revised_reproduzido[coluna])
        ambos_nulos = disco.isna() & meu.isna()
        diferenca = (meu - disco).abs()
        ruins = ~ambos_nulos & ~(diferenca <= TOLERANCIA_IGUALDADE)
        conferidas += int(len(disco))
        if bool(diferenca[~ambos_nulos].notna().any()):
            maior = max(maior, float(diferenca[~ambos_nulos].max()))
        if bool(ruins.any()):
            quais = list(em_disco.loc[ruins.to_numpy(), "quarter"].head(3))
            problemas.append(f"{coluna}: {int(ruins.sum())} célula(s), ex. {quais}")
    if problemas:
        msg = (
            f"a reprodução do `revised` não bate com {alvo.name} em "
            f"{len(problemas)} coluna(s): {problemas[:5]}. Sem reprodução bit a bit, a diferença "
            f"entre `asof` e `revised` não é atribuível à defasagem — o build para (classe C)."
        )
        raise ReproducaoDivergente(msg)
    return {
        "conferido": True,
        "reproduz_bit_a_bit": True,
        "celulas_conferidas_sem_tolerancia": conferidas,
        "divergencias": 0,
        "max_abs_dif": round(maior, 12),
        "sha256_revised_em_disco": sha256_de(alvo.read_bytes()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# O teste de sanidade da metodologia §5.1 (proxy do eixo da V1)
# ─────────────────────────────────────────────────────────────────────────────


def quadrante_proxy(gap: float | None, aceleracao: float | None) -> str | None:
    """O quadrante da V1 pelos dois eixos de ADR-001 §4 — **proxy diagnóstico**, não rótulo.

    `g = ibcbr_gap` (crescimento vs. tendência) e `pi = ipca_12m_delta` (aceleração da inflação),
    com os limiares do contrato (`LIMIAR_CRESCIMENTO_PP`, `LIMIAR_ACELERACAO_PP`) e os 4 rótulos
    de `RegimeV1`. **Não implementa a V1**: a V1 oficial é de **F-019** e tem desempate por
    herança do trimestre anterior, `n` por quadrante, `especificacao_congelada` e
    `RegimesV1Schema`. Aqui o proxy serve a um propósito só: dar número ao **teste de sanidade
    obrigatório** da metodologia §5.1 (quantos trimestres trocam de quadrante entre as duas
    materializações) sem que F-018 toque os arquivos de F-019.

    Eixo ausente → `None`: trimestre sem hiato ou sem aceleração não tem quadrante, e chamá-lo de
    qualquer coisa inventaria classificação.
    """
    if gap is None or pd.isna(gap) or aceleracao is None or pd.isna(aceleracao):
        return None
    cresce = float(gap) > LIMIAR_CRESCIMENTO_PP
    acelera = float(aceleracao) > LIMIAR_ACELERACAO_PP
    if cresce:
        return str(RegimeV1.EXPANSAO_INFL if acelera else RegimeV1.RECUPERACAO)
    return str(RegimeV1.ESTAGFLACAO if acelera else RegimeV1.DESACELERACAO)


def trocas_de_quadrante(revised: pd.DataFrame, asof: pd.DataFrame) -> dict[str, Any]:
    """% de trimestres que trocam de quadrante entre `revised` e `asof` (CA-073/CA-074).

    Denominador: os trimestres com quadrante **nas duas** materializações — comparar com um lado
    indeterminado mediria ausência de dado, não troca de regime. Os trimestres em que só um lado
    classifica são contados e publicados à parte.

    Passar de `LIMIAR_TROCA_REGIME_INOPERANTE` (25%) acende `operacional = False` e o texto que
    CA-074 exige: nessa forma o modelo **não é operacional**, e isso tem de ser dito ao Comitê
    (hipótese H-03 do PRD cai).
    """
    de_revised = [
        quadrante_proxy(g, p)
        for g, p in zip(revised["ibcbr_gap"], revised["ipca_12m_delta"], strict=True)
    ]
    de_asof = [
        quadrante_proxy(g, p)
        for g, p in zip(asof["ibcbr_gap"], asof["ipca_12m_delta"], strict=True)
    ]
    pares = [
        (q, a, b)
        for q, a, b in zip(revised["quarter"], de_revised, de_asof, strict=True)
        if a is not None and b is not None
    ]
    trocaram = [q for q, a, b in pares if a != b]
    comparaveis = len(pares)
    pct = round(100.0 * len(trocaram) / comparaveis, 2) if comparaveis else None
    acima = pct is not None and pct > 100.0 * LIMIAR_TROCA_REGIME_INOPERANTE
    texto_inoperante = (
        "ACIMA DO LIMITE: mais de 25% dos trimestres trocam de quadrante entre a materialização "
        "revisada e a defasada. Nesta forma o modelo NAO E OPERACIONAL — a classificação depende "
        "de informação que não estava disponível na data da decisão, e isso tem de ser dito ao "
        "Comitê (CA-074; hipótese H-03 do PRD cai)."
    )
    return {
        "proxy": (
            "sinal de `ibcbr_gap` x sinal de `ipca_12m_delta` (ADR-001 §4), sem o desempate por "
            "herança da V1 oficial. O rótulo oficial e o % definitivo são de F-019, que roda a V1 "
            "sobre as duas materializações e preenche `trocou_vs_revised` em `RegimesV1Schema`"
        ),
        "trimestres_comparaveis": comparaveis,
        "trimestres_que_trocam": len(trocaram),
        "pct_que_trocam": pct,
        "limiar_pct": 100.0 * LIMIAR_TROCA_REGIME_INOPERANTE,
        "operacional": None if pct is None else not acima,
        "texto": texto_inoperante
        if acima
        else (
            "Abaixo do limite de 25% de CA-074: a classificação é majoritariamente a mesma com e "
            "sem defasagem de divulgação. O número definitivo é de F-019."
        ),
        "so_em_revised": int(
            sum(1 for a, b in zip(de_revised, de_asof, strict=True) if a is not None and b is None)
        ),
        "so_em_asof": int(
            sum(1 for a, b in zip(de_revised, de_asof, strict=True) if a is None and b is not None)
        ),
        "trimestres": trocaram,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entradas do build
# ─────────────────────────────────────────────────────────────────────────────


def _ler_raw(*, raiz: Path | None) -> pd.DataFrame:
    """`raw_series.parquet`, validado por `RawSeriesSchema` antes de qualquer uso."""
    alvo = caminho_canonical(NOME_RAW_SERIES, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.build_raw_series --offline` (F-013)."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return RawSeriesSchema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz raw_series: {erro}"
        raise SerieInconsistente(msg) from erro


def _ler_catalogo(*, raiz: Path | None) -> pd.DataFrame:
    """`series_catalog.parquet` com as colunas que a régua consome (mesma política de F-015)."""
    alvo = caminho_canonical(NOME_CATALOGO, raiz=raiz)
    if not alvo.is_file():
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe (rode F-013)."
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    faltando = [
        c
        for c in ("series_id", "presente_no_processed", "data_inicio_observada")
        if c not in quadro.columns
    ]
    if faltando:
        msg = f"{alvo.name} sem as colunas que o asof consome: {faltando}"
        raise SerieInconsistente(msg)
    return quadro


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DO_ASOF` — o `fonte_versao` desta materialização.

    Diferente do de F-015 **por construção**: este arquivo entra no conjunto. É o que faz "mudei a
    regra de defasagem" ser distinguível de "mudou o dado" (RF-047/CA-121).
    """
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DO_ASOF))


@dataclass(frozen=True, slots=True)
class InsumosDoAsof:
    """Tudo que as duas montagens consomem — lido do disco **uma** vez, sem relógio."""

    calendario: Calendario
    trimestres: tuple[Trimestre, ...]
    janela: tuple[str, ...]
    observacoes_revised: pd.DataFrame
    observacoes_asof: pd.DataFrame
    acumulados_revised: dict[str, dict[str, Acumulado]]
    acumulados_asof: dict[str, dict[str, Acumulado]]
    metadado: dict[str, dict[str, Any]]
    lags: dict[str, int]
    versao_asof: str
    versao_revised: str
    motivo_focus: str


def preparar_insumos(
    *,
    raiz: Path | None = None,
    calendario: Calendario | None = None,
    quarters: Sequence[str] | None = None,
) -> InsumosDoAsof:
    """Lê `raw_series`/catálogo/calendário/Focus e monta as **duas** réguas sobre a mesma entrada.

    A simetria é o ponto: as duas materializações saem da mesma fatia de `raw_series`, da mesma
    grade estendida (apoio `2001Q1..2005Q4` + janela) e dos mesmos metadados de procedência. A
    única coisa que difere é a régua — `observacoes_de_fim_de_periodo` (referência) contra
    `observacoes_asof` (divulgação) — e, nos fluxos, `deslocar_acumulados`.

    As 11 séries da curva (`source=DERIVADO`, F-016) entram na **mesma** fatia aqui, em vez de
    passarem por `alinhar_series` como em F-015: são diárias de grade bancária e `lag = 0`, então
    as duas réguas dão a mesma célula — e isso não é suposição, é o que
    `conferir_contra_revised_em_disco` mede célula a célula contra o artefato de F-015.
    """
    raw = _ler_raw(raiz=raiz)
    catalogo = _ler_catalogo(raiz=raiz)
    declarado = load_catalog()

    # As duas guardas de F-013 na entrada desta camada: procedência resolvível (CA-055) e pacote
    # mínimo presente (CA-076). `asof` não relaxa nenhuma das duas.
    validar_procedencia(raw, declarado)
    exigir_series(fatiar_para_alinhamento(raw)[0], declarado, SERIES_EXIGIDAS)

    cal = calendario if calendario is not None else Calendario.do_parquet(raiz=raiz)
    trimestres = grade_estendida(cal, quarters=quarters)
    alvo = set(quarters or quarters_da_janela())
    janela = tuple(t.quarter for t in trimestres if t.quarter in alvo)
    inicio = inicio_observado_por_serie(catalogo, raw)

    consumidas = (*series_de_nivel(), *ACUMULADAS.values())
    fatia = raw.loc[raw["series_id"].isin(consumidas)].copy()
    curva = fatiar_curva(raw)
    if curva.empty:
        _log.warning("nenhuma serie de curva em raw_series: as colunas de curva sairao nulas")
    else:
        fatia = pd.concat([fatia, curva], ignore_index=True)

    focus, motivo_focus = carregar_focus(raiz=raiz)
    if focus is not None:
        fatia = pd.concat([fatia, focus], ignore_index=True)
        inicio = {
            **inicio,
            **{
                str(sid): pd.Timestamp(quando)
                for sid, quando in focus.groupby("series_id")["date"].min().items()
            },
        }
    _log.info("focus: %s", motivo_focus)

    lags = lags_de_divulgacao(declarado, series=sorted(fatia["series_id"].unique()))

    observacoes_revised = observacoes_de_fim_de_periodo(
        fatia, calendario=cal, trimestres=trimestres, inicio_por_serie=inicio
    )
    observacoes_defasadas = observacoes_asof(
        fatia, calendario=cal, trimestres=trimestres, inicio_por_serie=inicio, lags=lags
    )

    acumulados: dict[str, dict[str, Acumulado]] = {}
    for series_id in sorted(set(ACUMULADAS.values())):
        bruto = raw.loc[raw["series_id"] == series_id]
        pontos = validar_indice_temporal(selecionar_vintage(bruto))
        acumulados[series_id] = {
            a.quarter: a
            for a in acumular_por_trimestre(
                pontos, series_id=series_id, calendario=cal, trimestres=trimestres
            )
        }

    metadado = metadado_de_procedencia(raw)
    if focus is not None:
        por_subserie = metadado_de_procedencia(focus)
        for subserie, entrada in CATALOGO_DO_FOCUS.items():
            if subserie in por_subserie:
                metadado.setdefault(entrada, por_subserie[subserie])

    return InsumosDoAsof(
        calendario=cal,
        trimestres=trimestres,
        janela=janela,
        observacoes_revised=observacoes_revised,
        observacoes_asof=observacoes_defasadas,
        acumulados_revised=acumulados,
        acumulados_asof=deslocar_acumulados(acumulados, lags=lags, trimestres=trimestres),
        metadado=metadado,
        lags=lags,
        versao_asof=versao_build(),
        versao_revised=_hash_dos_componentes(caminhos_dos_componentes(MODULOS_DO_MACRO)),
        motivo_focus=motivo_focus,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Montagem das duas materializações
# ─────────────────────────────────────────────────────────────────────────────


def marcar_como_asof(
    macro: pd.DataFrame,
    provenance: pd.DataFrame,
    diagnostico: pd.DataFrame,
    *,
    lags: Mapping[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Acende `lag_adjusted=True` nas duas tabelas e acrescenta `date_obs`/`lag_dias` à procedência.

    `montar_macro` é de F-015 e grava `LAG_ADJUSTED = False` por contrato (é a `revised`). Em vez
    de alterar o módulo congelado, a flag é virada **aqui**, e as duas tabelas são **revalidadas**:
    `MacroQuarterlySchema` tem o check `lag_adjusted_homogeneo`, então uma tabela meio virada
    **não passa** — não existe estado intermediário publicável.

    `date_obs` e `lag_dias` vêm do diagnóstico que `montar_macro` já devolve (a última observação
    consumida por `(quarter, column)`) e do máximo de lag dos insumos da coluna. São as duas
    colunas que tornam CA-072 verificável no Parquet publicado.
    """
    virada = macro.copy()
    virada["lag_adjusted"] = LAG_ADJUSTED
    por_coluna = lags_por_coluna(lags)

    datas = diagnostico.loc[:, ["quarter", "column", "date_obs_max"]].copy()
    com_data = provenance.merge(datas, on=["quarter", "column"], how="left")
    if len(com_data) != len(provenance):
        msg = "o diagnóstico tem mais de uma linha por (quarter, column): a PK não fecha"
        raise SerieInconsistente(msg)
    com_data["lag_adjusted"] = LAG_ADJUSTED
    com_data["date_obs"] = pd.to_datetime(com_data.pop("date_obs_max"))
    com_data["lag_dias"] = [int(por_coluna[c]) for c in com_data["column"]]
    ordem = list(MacroQuarterlyAsofProvenanceSchema.to_schema().columns)
    return (
        MacroQuarterlySchema.validate(virada, lazy=True),
        MacroQuarterlyAsofProvenanceSchema.validate(com_data.loc[:, ordem], lazy=True),
    )


def celulas_com_look_ahead(provenance: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    """As linhas de procedência cuja divulgação cai **depois** do fim do trimestre. Tem de ser 0.

    É CA-072 escrito como consulta sobre os dois artefatos publicados: junta a procedência
    (`date_obs`, `lag_dias`) com `quarter_end` da tabela wide e devolve o que violaria a regra.
    O build levanta se vier alguma linha; o teste central refaz a mesma consulta a partir do
    Parquet em disco, sem importar nada deste módulo.
    """
    fim = macro.loc[:, ["quarter", "quarter_end"]]
    juntos = provenance.merge(fim, on="quarter", how="left")
    com_data = juntos.loc[juntos["date_obs"].notna()].copy()
    com_data["divulgacao"] = pd.to_datetime(com_data["date_obs"]) + pd.to_timedelta(
        com_data["lag_dias"], unit="D"
    )
    return com_data.loc[com_data["divulgacao"] > pd.to_datetime(com_data["quarter_end"])]


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────


def _iso(valor: Any) -> str | None:
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return None
    return pd.Timestamp(valor).date().isoformat()


def _valor(macro: pd.DataFrame, quarter: str, coluna: str) -> float | None:
    """A célula, arredondada em 6 casas — ou `None` se é nula ou o trimestre não existe."""
    indexado = macro.set_index("quarter")
    if quarter not in indexado.index:
        return None
    bruto = indexado.loc[quarter, coluna]
    return None if pd.isna(bruto) else round(float(bruto), 6)


def canarios_do_asof(
    *, macro_asof: pd.DataFrame, macro_revised: pd.DataFrame, observacoes: pd.DataFrame
) -> dict[str, Any]:
    """Os 3 canários conferidos à mão (`AGENTS.md §15.9`), cada um provando uma regra diferente.

    1. **`pib_yoy` de `2010Q1`** em `asof` **é** o de `4T2009` em `revised` — prova o deslocamento
       de um trimestre inteiro de uma série com `lag = 60`, **e** que a derivada foi recalculada
       (um a/a copiado daria outro número);
    2. **`ipca_12m` de `2026Q3`** em `asof` é o acumulado 12 meses de **agosto/2026** — prova a
       regra observação a observação de uma série mensal com `lag = 10` (o de setembro só sai em
       outubro). O canário publica a `date_obs` efetivamente usada, não só o valor;
    3. **`focus_ipca_12m`** é **idêntico** nas duas — prova que `lag = 0` não desloca.
    """
    do_ipca = observacoes.loc[
        (observacoes["series_id"] == "BCB_SGS_13522") & (observacoes["quarter"] == "2026Q3")
    ]
    data_do_ipca = _iso(do_ipca["date_obs"].iloc[0]) if len(do_ipca) else None
    focus_revised = _como_float(macro_revised["focus_ipca_12m"])
    focus_asof = _como_float(macro_asof["focus_ipca_12m"])
    focus_igual = (focus_revised.isna() & focus_asof.isna()) | (focus_revised == focus_asof)
    return {
        "pib_yoy_asof_2010Q1_e_o_revised_de_2009Q4": {
            "asof_2010Q1": _valor(macro_asof, "2010Q1", "pib_yoy"),
            "revised_2009Q4": _valor(macro_revised, "2009Q4", "pib_yoy"),
            "revised_2010Q1": _valor(macro_revised, "2010Q1", "pib_yoy"),
            "bate": _valor(macro_asof, "2010Q1", "pib_yoy")
            == _valor(macro_revised, "2009Q4", "pib_yoy"),
            "regra": "PIB tem lag 60 d: no fim de 1T2010 o último PIB divulgado é o de 4T2009",
        },
        "ipca_12m_asof_2026Q3_e_de_agosto": {
            "asof_2026Q3": _valor(macro_asof, "2026Q3", "ipca_12m"),
            "revised_2026Q3": _valor(macro_revised, "2026Q3", "ipca_12m"),
            "date_obs_usada": data_do_ipca,
            "bate": data_do_ipca == "2026-08-31",
            "regra": "IPCA tem lag 10 d: o de setembro sai em outubro, logo vale o de agosto",
        },
        "focus_ipca_12m_identico": {
            "n_diferentes": int((~focus_igual).sum()),
            "bate": bool(focus_igual.all()),
            "regra": "Focus tem lag 0: a mediana da coleta da semana X é conhecida na semana X",
        },
    }


def montar_relatorio_asof(
    *,
    macro_asof: pd.DataFrame,
    provenance_asof: pd.DataFrame,
    macro_revised: pd.DataFrame,
    comparacao: pd.DataFrame,
    insumos: InsumosDoAsof,
    diff_em_disco: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    """`relatorio_asof.json` — **sem relógio**, para que duas rodadas sejam byte-idênticas."""
    por_coluna = {
        linha["column"]: {
            chave: linha[chave]
            for chave in (
                "lag_dias",
                "unidade",
                "series_id",
                "n_diferentes",
                "pct_diferentes",
                "max_abs_dif",
                "nulos_revised",
                "nulos_asof",
                "identica",
            )
        }
        for linha in comparacao.to_dict("records")
    }
    identicas = sorted(c for c, bloco in por_coluna.items() if bloco["identica"])
    desloca = sorted(c for c, bloco in por_coluna.items() if not bloco["identica"])
    deslocamento = insumos.observacoes_asof.loc[insumos.observacoes_asof["date_obs"].notna()]
    por_serie = deslocamento.groupby("series_id")["deslocamento_dias"]

    return {
        "macro_quarterly_asof": {
            "linhas": int(len(macro_asof)),
            "colunas": int(macro_asof.shape[1]),
            "primeiro_trimestre": str(macro_asof["quarter"].iloc[0]),
            "ultimo_trimestre": str(macro_asof["quarter"].iloc[-1]),
            "materializacao": MATERIALIZACAO,
            "lag_adjusted": LAG_ADJUSTED,
            "is_estimated_em": sorted(macro_asof.loc[macro_asof["is_estimated"], "quarter"]),
            "sha256": hashes["sha256_asof"],
            "bytes": hashes["bytes_asof"],
        },
        "macro_quarterly_asof_provenance": {
            "linhas": int(len(provenance_asof)),
            "colunas_cobertas": int(provenance_asof["column"].nunique()),
            "series_distintas": int(provenance_asof["series_id"].nunique()),
            "celulas_com_date_obs": int(provenance_asof["date_obs"].notna().sum()),
            "sha256": hashes["sha256_provenance"],
            "bytes": hashes["bytes_provenance"],
        },
        "regra": {
            "texto": (
                "o valor de (T, coluna) e o da ultima observacao cuja divulgacao "
                "(`date_obs + lag_divulgacao_dias`) e <= `quarter_end` de T (ultimo dia UTIL). "
                "Derivadas (a/a, aceleracao, tendencia, hiato, Fisher, surpresas) sao "
                "RECALCULADAS sobre os niveis deslocados por `montar_macro` de F-015 — nunca "
                "copiadas da tabela revisada"
            ),
            "corte": "quarter_end (ultimo dia util de T)",
            "tolerancia_de_frescor_dias_uteis": {
                freq: tolerancia_de_frescor(freq) for freq in sorted(PASSO_EM_DIAS_UTEIS)
            },
            "max_deslocamento_de_fluxo_trimestres": MAX_DESLOCAMENTO_TRIMESTRES,
        },
        "lags_do_catalogo": dict(sorted(insumos.lags.items())),
        "deslocamento_medido_por_serie": {
            str(sid): {
                "lag_dias": int(insumos.lags[str(sid)]),
                "deslocamento_dias_mediano": int(grupo.median()),
                "deslocamento_dias_max": int(grupo.max()),
                "celulas": int(grupo.size),
            }
            for sid, grupo in sorted(por_serie)
        },
        "comparacao_por_coluna": dict(sorted(por_coluna.items())),
        "colunas_identicas": identicas,
        "colunas_que_mudam": desloca,
        "resumo_da_comparacao": {
            "colunas_comparadas": int(len(por_coluna)),
            "colunas_identicas": len(identicas),
            "colunas_que_mudam": len(desloca),
            "pct_medio_de_trimestres_diferentes": round(
                float(comparacao["pct_diferentes"].mean()), 2
            ),
            "pct_maximo": round(float(comparacao["pct_diferentes"].max()), 2),
        },
        "troca_de_quadrante_proxy_v1": trocas_de_quadrante(macro_revised, macro_asof),
        "anti_look_ahead": {
            "regra": (
                "nenhuma celula de T usa observacao com `date_obs + lag_divulgacao_dias` depois "
                "do `quarter_end` de T (CA-072). Verificavel no Parquet: a procedencia publica "
                "`date_obs` e `lag_dias`"
            ),
            "celulas_com_divulgacao_depois_do_fim_de_T": int(
                len(celulas_com_look_ahead(provenance_asof, macro_asof))
            ),
            "celulas_com_date_obs": int(provenance_asof["date_obs"].notna().sum()),
            "date_obs_max_por_coluna": {
                str(coluna): _iso(valor)
                for coluna, valor in sorted(
                    provenance_asof.groupby("column")["date_obs"].max().items()
                )
                if pd.notna(valor)
            },
        },
        "canarios": canarios_do_asof(
            macro_asof=macro_asof,
            macro_revised=macro_revised,
            observacoes=insumos.observacoes_asof,
        ),
        "diff_vs_revised_em_disco": dict(diff_em_disco),
        "limitacoes": {
            "vintage_unico": (
                "`asof` tem duas pernas: defasagem de DIVULGACAO (implementada) e revisao "
                "retroativa da fonte (o IBGE revisa o PIB uma vez por ano). `raw_series` tem "
                "hoje uma unica safra por serie, entao a segunda perna e DEGENERADA: nao existe "
                "retrato antigo para escolher. O numero publicado aqui e um PISO do efeito de "
                "look-ahead, nao o efeito total (metodologia §5.1, linha 'Revisoes do PIB')"
            ),
            "lag_em_dias_civis": (
                "`lag_divulgacao_dias` e uma defasagem tipica em dias civis, nao o calendario "
                "real de release por data. Arredondar para cima e conservador: descarta "
                "informacao, nunca cria look-ahead"
            ),
            "quadrante_e_proxy": (
                "o % de troca publicado aqui usa um proxy do eixo da V1 sem desempate por "
                "heranca. O numero oficial de CA-073 e de F-019"
            ),
        },
        "focus": {
            "consumido": bool(macro_asof["focus_ipca_12m"].notna().any()),
            "motivo": insumos.motivo_focus,
        },
        "versao_build": hashes["versao_build"],
        "versao_build_do_revised": hashes["versao_build_revised"],
        "modulos_da_versao": list(MODULOS_DO_ASOF),
        "nota_para_f019": (
            "rode a V1 sobre as DUAS materializacoes (`macro_quarterly.parquet` e "
            "`macro_quarterly_asof.parquet`) e reporte o % de trimestres que trocam de rotulo em "
            "`trocou_vs_revised`; acima de 25% o texto tem de afirmar que o modelo nao e "
            "operacional (CA-073/CA-074). A `asof` e o default para decisao; `lag_adjusted` da "
            "linha diz qual foi usada"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoAsof:
    """O que o build produziu — o CLI imprime, o teste inspeciona, o QA confere."""

    macro_asof: pd.DataFrame
    provenance_asof: pd.DataFrame
    macro_revised: pd.DataFrame
    comparacao: pd.DataFrame
    relatorio: dict[str, Any]
    insumos: InsumosDoAsof
    caminho_asof: Path
    caminho_provenance: Path
    caminho_relatorio: Path


def construir(
    *,
    raiz: Path | None = None,
    calendario: Calendario | None = None,
    quarters: Sequence[str] | None = None,
) -> ResultadoAsof:
    """Materializa a `asof` de ponta a ponta: duas montagens, uma conferência, três artefatos.

    Ordem: ler entradas → montar `revised` (sem defasagem) → **conferir contra o artefato de
    F-015 em disco** → montar `asof` → virar a flag e revalidar → **exigir zero** célula com
    divulgação posterior ao fim do trimestre → comparar coluna a coluna → gravar.

    Sem rede, sem relógio, sem efeito fora de `data/canonical/`. `calendario` e `quarters` existem
    para o teste cravar uma árvore sintética.
    """
    insumos = preparar_insumos(raiz=raiz, calendario=calendario, quarters=quarters)

    macro_revised, _, _ = montar_macro(
        observacoes=insumos.observacoes_revised,
        acumulados=insumos.acumulados_revised,
        metadado=insumos.metadado,
        trimestres=insumos.trimestres,
        quarters=insumos.janela,
        fonte_versao=insumos.versao_revised,
    )
    diff_em_disco = conferir_contra_revised_em_disco(macro_revised, raiz=raiz)
    _log.info("diff vs macro_quarterly.parquet (F-015): %s", diff_em_disco)

    bruto, provenance_bruta, diagnostico = montar_macro(
        observacoes=insumos.observacoes_asof,
        acumulados=insumos.acumulados_asof,
        metadado=insumos.metadado,
        trimestres=insumos.trimestres,
        quarters=insumos.janela,
        fonte_versao=insumos.versao_asof,
    )
    macro_asof, provenance_asof = marcar_como_asof(
        bruto, provenance_bruta, diagnostico, lags=insumos.lags
    )

    violacoes = celulas_com_look_ahead(provenance_asof, macro_asof)
    if not violacoes.empty:
        amostra = [
            f"{r.quarter}/{r.column}: date_obs {r.date_obs} + {r.lag_dias} d > {r.quarter_end}"
            for r in violacoes.head(5).itertuples(index=False)
        ]
        msg = (
            f"{len(violacoes)} célula(s) de `asof` usariam dado divulgado depois do fim do "
            f"trimestre: {amostra}. É exatamente o que CA-072 proíbe — o build para."
        )
        raise ReproducaoDivergente(msg)

    comparacao = comparar_materializacoes(macro_revised, macro_asof, lags=insumos.lags)

    destino_asof = caminho_canonical(NOME_ASOF, raiz=raiz)
    destino_prov = caminho_canonical(NOME_ASOF_PROVENANCE, raiz=raiz)
    garantir_diretorio(destino_asof.parent)
    macro_asof.to_parquet(destino_asof, index=False)
    provenance_asof.to_parquet(destino_prov, index=False)
    corpo_asof = destino_asof.read_bytes()
    corpo_prov = destino_prov.read_bytes()
    _log.info(
        "gravado %s (%d linhas, %d colunas, sha256=%s...) e %s (%d linhas)",
        destino_asof.name,
        len(macro_asof),
        macro_asof.shape[1],
        sha256_de(corpo_asof)[:12],
        destino_prov.name,
        len(provenance_asof),
    )

    relatorio = montar_relatorio_asof(
        macro_asof=macro_asof,
        provenance_asof=provenance_asof,
        macro_revised=macro_revised,
        comparacao=comparacao,
        insumos=insumos,
        diff_em_disco=diff_em_disco,
        hashes={
            "sha256_asof": sha256_de(corpo_asof),
            "bytes_asof": len(corpo_asof),
            "sha256_provenance": sha256_de(corpo_prov),
            "bytes_provenance": len(corpo_prov),
            "versao_build": insumos.versao_asof,
            "versao_build_revised": insumos.versao_revised,
        },
    )
    destino_relatorio = caminho_canonical(NOME_RELATORIO_ASOF, raiz=raiz)
    destino_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ResultadoAsof(
        macro_asof=macro_asof,
        provenance_asof=provenance_asof,
        macro_revised=macro_revised,
        comparacao=comparacao,
        relatorio=relatorio,
        insumos=insumos,
        caminho_asof=destino_asof,
        caminho_provenance=destino_prov,
        caminho_relatorio=destino_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.asof",
        description=(
            "Materializa data/canonical/macro_quarterly_asof.parquet + "
            "macro_quarterly_asof_provenance.parquet + relatorio_asof.json a partir de "
            "raw_series (F-013) e das funcoes puras de F-015. Nunca toca a rede."
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Aceito por simetria com os extratores e sem efeito: esta camada só lê o disco.",
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

    bloco = resultado.relatorio["macro_quarterly_asof"]
    prov = resultado.relatorio["macro_quarterly_asof_provenance"]
    resumo = resultado.relatorio["resumo_da_comparacao"]
    diff = resultado.relatorio["diff_vs_revised_em_disco"]
    troca = resultado.relatorio["troca_de_quadrante_proxy_v1"]
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{NOME_ASOF}: {bloco['linhas']} linhas | {bloco['colunas']} colunas | "
        f"{bloco['primeiro_trimestre']}..{bloco['ultimo_trimestre']} | "
        f"{bloco['materializacao']} | sha256 {bloco['sha256']}"
    )
    print(
        f"{NOME_ASOF_PROVENANCE}: {prov['linhas']} linhas | {prov['colunas_cobertas']} colunas | "
        f"{prov['celulas_com_date_obs']} com date_obs | sha256 {prov['sha256']}"
    )
    print(
        f"reproducao do revised vs disco: conferido={diff.get('conferido')} "
        f"celulas={diff.get('celulas_conferidas_sem_tolerancia')} "
        f"divergencias={diff.get('divergencias')} max_abs_dif={diff.get('max_abs_dif')}"
    )
    print(
        f"colunas: {resumo['colunas_identicas']} identicas, {resumo['colunas_que_mudam']} mudam "
        f"(pct medio de trimestres diferentes {resumo['pct_medio_de_trimestres_diferentes']}%, "
        f"max {resumo['pct_maximo']}%)"
    )
    print(
        f"anti-look-ahead: "
        f"{resultado.relatorio['anti_look_ahead']['celulas_com_divulgacao_depois_do_fim_de_T']} "
        f"celula(s) com divulgacao depois do fim de T (tem de ser 0)"
    )
    print(
        f"troca de quadrante (proxy V1): {troca['trimestres_que_trocam']}/"
        f"{troca['trimestres_comparaveis']} = {troca['pct_que_trocam']}% | "
        f"operacional={troca['operacional']}"
    )
    for nome, canario in sorted(resultado.relatorio["canarios"].items()):
        print(f"canario {nome}: bate={canario['bate']}")
    for linha in (
        resultado.comparacao.sort_values("pct_diferentes", ascending=False)
        .head(8)
        .itertuples(index=False)
    ):
        print(
            f"  {linha.column}: lag {linha.lag_dias} d | {linha.n_diferentes} tri diferentes "
            f"({linha.pct_diferentes}%) | max abs dif {linha.max_abs_dif}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
