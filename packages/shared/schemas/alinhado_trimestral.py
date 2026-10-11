"""Schema de `alinhado_trimestral` — a grade trimestral *long*, antes de qualquer cálculo (RF-023).

Fonte de verdade do contrato (SPEC RF-023, CA-065..068; ADR-006 §(b).2 e §(b).8). Espelho legível
em `docs/contracts/CONTRACTS.md §8`. Produzido por `apps/pipeline/canonical/alinhamento.py`
(F-014) e consumido por **F-015** (`macro_quarterly`), **F-016** (curva) e **F-017**
(`asset_returns_quarterly`).

**Classe C.** Esta tabela é a régua temporal de todo o canônico: um trimestre desalinhado aqui
contamina retorno, regime e heatmap sem levantar exceção. Alterar coluna, unidade ou regra exige
Feature Contract classe C, diff numérico e reconstrução completa (`AGENTS.md §2`, Anti-SPEC
§10.3.17).

## O que a tabela é

Uma linha por `(quarter, series_id)` dizendo **qual observação da série representa aquele
trimestre** — e, quando nenhuma representa, **por quê**. Nada é calculado: `value` é, bit a bit, o
valor que `raw_series` tem em `date_obs`. Não há interpolação, média de período, reescala nem
preenchimento com `0` (Anti-SPEC §10.1.1, §10.1.4).

## As três grades (coluna `grade`)

| `grade` | Quem usa | `date_alvo` |
|---|---|---|
| `bancaria` | série `freq=D` de calendário de dia útil | **último dia útil** (ANBIMA) |
| `corrido` | série `freq=D` de **calendário corrido** (SGS 432, meta Selic) | último dia civil |
| `civil` | séries `freq=M`/`Q`/`A` (o `date` já é fim de período, D-a) | último dia civil |

`quarter_end` é **sempre** o último dia útil bancário: é a grade única de ADR-006 e a chave com
que `macro_quarterly` e `asset_returns_quarterly` se juntam. `date_alvo` é o alvo **daquela
linha** e pode ser até 2 dias civis depois de `quarter_end` nas grades `corrido`/`civil` (ex.:
3T2006 → `quarter_end = 2006-09-29`, `date_alvo = 2006-09-30`). As duas colunas existem
justamente para que a diferença seja legível no dado, não deduzida do código.

## Forward-fill: o que `ffill_dias_uteis` e `lacuna_dias_uteis` significam

`lacuna_dias_uteis` = quantos **dias úteis** (ANBIMA) há no intervalo semiaberto
`(date_ultima_obs, date_alvo]` — a distância da última observação disponível até o alvo,
**medida sempre**, tenha ela sido usada ou não. `ffill_dias_uteis` = a mesma distância **quando o
valor foi aproveitado**, e `0` quando a célula é nula.

- `lacuna <= LIMITE_FFILL_DIAS_UTEIS` (5, ADR-006 §(b).8) → o valor é usado e
  `ffill_dias_uteis == lacuna_dias_uteis`;
- `lacuna > 5` → `value = NULL`, `date_obs = NULL`, `ffill = 0`, `motivo_nulo` preenchido e
  `date_ultima_obs`/`lacuna_dias_uteis` **registrando a lacuna** (CA-067) — nunca preenchida;
- nenhuma observação até o alvo → tudo nulo, `lacuna = 0`, `date_ultima_obs = NULL`.

O caso que esta contagem existe para registrar é **D-h**: a B3 não negocia no último dia útil
bancário do ano, então toda série da B3 carrega `ffill_dias_uteis = 1` em todo 4º trimestre
(`docs/wiki/modules/calendario.md §B`).

## Painel desbalanceado

`data_inicio_serie` vem do `series_catalog` materializado (`data_inicio_observada`) e a tabela
**não tem linha** com `date_alvo < data_inicio_serie` — ICON não existe em 1T2006, IMOB não existe
em 2006, IFIX não existe antes de 4T2010 (CA-063, Anti-SPEC §10.1.1). O check
`sem_linha_antes_do_inicio_da_serie` é o que impede o backfill sintético de voltar por descuido.
"""

from __future__ import annotations

import pandas as pd
import pandera as pa
from pandera.typing import Series

from packages.shared.schemas.raw_series import FONTES_VALIDAS, FREQS_VALIDAS, UNIDADES_VALIDAS

QUARTER_REGEX = r"^(200[6-9]|20[1-2][0-9])Q[1-4]$"
"""Mesmo regex de `macro_quarterly` e `asset_returns_quarterly` — a janela é a mesma."""

PRIMEIRO_TRIMESTRE = "2006Q1"
ULTIMO_TRIMESTRE = "2026Q3"
N_TRIMESTRES_JANELA = 83

LIMITE_FFILL_DIAS_UTEIS = 5
"""ADR-006 §(b).8: forward-fill de no máximo 5 dias úteis; acima disso `NULL` registrado."""

GRADE_BANCARIA = "bancaria"
GRADE_CORRIDO = "corrido"
GRADE_CIVIL = "civil"

GRADES_VALIDAS: list[str] = [GRADE_BANCARIA, GRADE_CORRIDO, GRADE_CIVIL]
"""**Lista**, nunca tupla: `isin` de um único valor em tupla reprova toda linha nesta versão do
pandera (armadilha medida em F-008 e documentada em `calendario.py`)."""

MOTIVO_LACUNA_ACIMA_DO_LIMITE = "lacuna_acima_do_limite_de_ffill"
MOTIVO_SEM_OBSERVACAO = "sem_observacao_ate_a_data_alvo"

MOTIVOS_VALIDOS: list[str] = [MOTIVO_LACUNA_ACIMA_DO_LIMITE, MOTIVO_SEM_OBSERVACAO]
"""Os dois únicos motivos de célula nula. Qualquer outro é bug: ausência tem causa nomeada."""

#: As 18 colunas de `AlinhadoTrimestralSchema`, **nesta ordem** — a ordem é parte do artefato.
COLUNAS_ALINHADO: tuple[str, ...] = (
    "quarter",
    "quarter_end",
    "series_id",
    "grade",
    "date_alvo",
    "date_obs",
    "value",
    "ffill_dias_uteis",
    "date_ultima_obs",
    "lacuna_dias_uteis",
    "motivo_nulo",
    "freq",
    "unit",
    "source",
    "vintage",
    "collected_at",
    "data_inicio_serie",
    "fonte_versao",
)

#: PK lógica de `alinhado_trimestral` — também a chave de ordenação determinística.
PK_ALINHADO: tuple[str, ...] = ("series_id", "quarter")


def quarters_da_janela() -> tuple[str, ...]:
    """Os 83 rótulos `AAAAQN` de `2006Q1` a `2026Q3`, derivados — nunca digitados."""
    periodos = pd.period_range(PRIMEIRO_TRIMESTRE, ULTIMO_TRIMESTRE, freq="Q")
    return tuple(str(p) for p in periodos)


class AlinhadoTrimestralSchema(pa.DataFrameModel):
    """Grade trimestral *long* de `raw_series`. PK: `(series_id, quarter)`. **Classe C.**"""

    quarter: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    quarter_end: Series[pa.DateTime] = pa.Field(
        nullable=False, description="Último dia útil bancário (ANBIMA) do trimestre — grade única."
    )
    series_id: Series[str] = pa.Field(nullable=False, str_matches=r"^[A-Z0-9_\.\^=\-]+$")
    grade: Series[str] = pa.Field(
        nullable=False, isin=GRADES_VALIDAS, description="Régua usada nesta linha (ver docstring)."
    )
    date_alvo: Series[pa.DateTime] = pa.Field(
        nullable=False, description="Data que esta linha buscou, segundo `grade`."
    )
    date_obs: Series[pa.DateTime] = pa.Field(
        nullable=True, description="Data da observação efetivamente usada; nula ⇔ `value` nulo."
    )
    value: Series[float] = pa.Field(
        nullable=True, description="O valor de `raw_series` em `date_obs`, sem transformação."
    )
    ffill_dias_uteis: Series[int] = pa.Field(
        nullable=False,
        ge=0,
        le=LIMITE_FFILL_DIAS_UTEIS,
        description="Dias úteis de forward-fill aproveitados (0..5, ADR-006 §(b).8).",
    )
    date_ultima_obs: Series[pa.DateTime] = pa.Field(
        nullable=True,
        description="Última observação disponível até `date_alvo`, usada ou não — é o que "
        "registra a lacuna rejeitada (CA-067).",
    )
    lacuna_dias_uteis: Series[int] = pa.Field(
        nullable=False,
        ge=0,
        description="Dias úteis entre `date_ultima_obs` e `date_alvo`; > 5 ⇒ célula nula.",
    )
    motivo_nulo: Series[pd.StringDtype] = pa.Field(
        nullable=True,
        isin=MOTIVOS_VALIDOS,
        description="Por que a célula é nula; nulo se há valor.",
    )

    freq: Series[str] = pa.Field(nullable=False, isin=list(FREQS_VALIDAS))
    unit: Series[str] = pa.Field(nullable=False, isin=list(UNIDADES_VALIDAS))
    source: Series[str] = pa.Field(nullable=False, isin=list(FONTES_VALIDAS))
    vintage: Series[pa.DateTime] = pa.Field(
        nullable=True, description="Vintage da série usado nesta materialização (o mais recente)."
    )
    collected_at: Series[pa.DateTime] = pa.Field(nullable=False)
    data_inicio_serie: Series[pa.DateTime] = pa.Field(
        nullable=False, description="`data_inicio_observada` do catálogo materializado (CA-063)."
    )
    fonte_versao: Series[str] = pa.Field(
        nullable=False, description="`sha256` do código que alinhou a linha (RF-047/CA-121)."
    )

    class Config:
        """Configuração do schema."""

        name = "alinhado_trimestral"
        strict = True
        coerce = True
        unique = ["series_id", "quarter"]
        unique_column_names = True
        add_missing_columns = False

    # ------------------------------------------------------------------ checks

    @pa.dataframe_check(name="quarter_dentro_da_janela_de_83")
    def _janela(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """Nenhum trimestre fora de `2006Q1..2026Q3` (CA-059 é de F-015; aqui é o subconjunto)."""
        return set(df["quarter"].unique()) <= set(quarters_da_janela())

    @pa.dataframe_check(name="quarter_end_e_date_alvo_caem_no_trimestre")
    def _datas_do_trimestre(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """`quarter_end` e `date_alvo` pertencem ao trimestre que a linha diz ser (CA-065)."""
        rotulo = df["quarter"].astype(str)
        for coluna in ("quarter_end", "date_alvo"):
            periodo = pd.DatetimeIndex(df[coluna]).to_period("Q").astype(str)
            if not bool((periodo == rotulo.to_numpy()).all()):
                return False
        return True

    @pa.dataframe_check(name="quarter_end_unico_por_trimestre")
    def _grade_unica(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """A grade é **uma**: todas as linhas de um trimestre têm o mesmo `quarter_end`.

        É o que torna a decisão (a) de D-h verificável no dado — grade própria da B3 (opção (b))
        faria este check falhar, que é exatamente o alarme que se quer.
        """
        primeiro = df.groupby("quarter")["quarter_end"].transform("first")
        return bool(primeiro.eq(df["quarter_end"]).all())

    @pa.dataframe_check(name="nulo_tem_motivo_e_nao_tem_data")
    def _nulo_coerente(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """`value` nulo ⇔ `date_obs` nulo ⇔ `motivo_nulo` preenchido, e sem ffill."""
        nulo = df["value"].isna()
        return (
            bool((nulo == df["date_obs"].isna()).all())
            and bool((nulo == df["motivo_nulo"].notna()).all())
            and bool((df.loc[nulo, "ffill_dias_uteis"] == 0).all())
        )

    @pa.dataframe_check(name="ffill_e_a_lacuna_quando_ha_valor")
    def _ffill_coerente(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """Célula com valor: `ffill == lacuna`. Célula sem valor por lacuna: `lacuna > 5`."""
        com_valor = df["value"].notna()
        if not bool(
            (df.loc[com_valor, "ffill_dias_uteis"] == df.loc[com_valor, "lacuna_dias_uteis"]).all()
        ):
            return False
        por_lacuna = df["motivo_nulo"].eq(MOTIVO_LACUNA_ACIMA_DO_LIMITE)
        return bool((df.loc[por_lacuna, "lacuna_dias_uteis"] > LIMITE_FFILL_DIAS_UTEIS).all())

    @pa.dataframe_check(name="lacuna_acima_do_limite_nunca_tem_valor")
    def _limite_respeitado(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """O contrapositivo do check anterior: `lacuna > 5` ⇒ célula nula (CA-067)."""
        acima = df["lacuna_dias_uteis"] > LIMITE_FFILL_DIAS_UTEIS
        return bool(df.loc[acima, "value"].isna().all())

    @pa.dataframe_check(name="observacao_nunca_depois_do_alvo")
    def _sem_look_ahead_de_grade(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """`date_obs` e `date_ultima_obs` nunca passam de `date_alvo` (base do `asof`, §10.2.7)."""
        for coluna in ("date_obs", "date_ultima_obs"):
            presente = df[coluna].notna()
            if not bool((df.loc[presente, coluna] <= df.loc[presente, "date_alvo"]).all()):
                return False
        return True

    @pa.dataframe_check(name="date_obs_e_a_ultima_observacao_disponivel")
    def _obs_e_a_ultima(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """Quando há valor, a observação usada é a última disponível — nunca uma anterior."""
        com_valor = df["value"].notna()
        return bool((df.loc[com_valor, "date_obs"] == df.loc[com_valor, "date_ultima_obs"]).all())

    @pa.dataframe_check(name="sem_linha_antes_do_inicio_da_serie")
    def _painel_desbalanceado(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """Nenhuma linha com `date_alvo` anterior ao início real da série (CA-063)."""
        return bool((df["date_alvo"] >= df["data_inicio_serie"]).all())

    @pa.dataframe_check(name="metadado_constante_por_serie")
    def _metadado_constante(cls, df: pd.DataFrame) -> bool:  # noqa: N805
        """`grade`, `freq`, `unit`, `source` e `data_inicio_serie` são da série, não da linha.

        Duas grades para o mesmo `series_id`, ou duas unidades, é o erro de escala silencioso que
        o Validation Mode §5 manda procurar (`AGENTS.md §15`).
        """
        colunas = ["grade", "freq", "unit", "source", "data_inicio_serie"]
        por_serie = df.groupby("series_id")[colunas]
        return bool(por_serie.transform("first").eq(df[colunas]).all().all())
