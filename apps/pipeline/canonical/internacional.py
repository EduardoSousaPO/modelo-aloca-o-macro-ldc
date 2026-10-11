"""F-026 — Dimensionamento da alocação internacional + regra de risk-off. **Classe C.**

Responde ao item **C1** do e-mail do Alexandre ("tamanho da alocação internacional"), que é a
metade do pedido que os blocos A/B do e-mail não listam nenhuma série para atender. RF-038
(CA-104/105) e RF-039 (CA-106/107).

## O que materializa em `data/canonical/`

- **`internacional_por_regime.parquet`** — retorno em BRL e correlação condicional do internacional
  por regime, nas **três** leituras de RF-038: `V1` (`revised`, T0), `V1_ASOF` (materialização
  `asof` de F-018, T0) e `V3` (vizinhos de `2026Q3` medidos em **T+1**, CA-102).
- **`internacional_pesos.parquet`** — variância mínima long-only com shrinkage, por regime
  (descritivo) e expanding por trimestre (sem look-ahead), com o peso internacional truncado na
  banda de ADR-003. **NÃO PUBLICÁVEL na v1** — ver o bloqueio de Anti-SPEC abaixo.
- **`relatorio_internacional.json`** — a regra de stress trimestre a trimestre, as correlações de
  CA-105, a tabela regime → peso sugerido com o selo de CA-107, a leitura de risk-off e os hashes.

## CA-104: "no mesmo arcabouço", literalmente — a mesma função

`internacional_por_regime` **não recalcula** retorno médio, mediana, excesso sobre CDI, retorno
real nem hit ratio: chama `metricas_regime.metricas_da_celula` (F-022), com o **mesmo** mapa
regime → trimestres (`trimestres_por_regime_v1`) e os **mesmos** vizinhos (`vizinhos_da_lente_
canonica`). Há teste que compara, célula a célula, as colunas comuns com
`regime_asset_metrics.parquet` e exige igualdade exata. É o que torna "não em anexo separado"
verificável no dado em vez de prometido no texto.

O que esta tabela **acrescenta** são as duas colunas que CA-105 pede e que F-022 não tem:
`corr_ibov` e `corr_imab`, cada uma com o seu **`n` de pares** — que não é o `n_obs` da célula
(par exige os dois lados, e `ACWI_BRL` e `IBOV` têm padrões de nulo diferentes).

## CA-106: a regra de `stress_flag`, fechada aqui

F-022 deixou `RegimesSchema.stress_flag` **bloqueado** por três ambiguidades de RF-039 ("a
inclinação cai > 1 desvio-padrão **ou** USDBRL sobe > 10% no trimestre"): *qual* inclinação, em
*que amostra* o desvio é estimado, e se "cai" é sobre o nível ou sobre a variação. As três são
decididas aqui, de forma declarada (**D6-a**, registrada em `docs/wiki/context/F-026.md`):

- **Qual inclinação** → a **real 5a−3a** (`INCLINACAO_REAL_5A_3A`): é a principal provisória de
  **D-i** (95,25% de cobertura, a que fecha CA-025; a 5a−1a tem 60,53%). **D-n** a mantém fora de
  `MacroQuarterlySchema`, então ela vem da função que F-021 já publica — mesmo número da feature
  de curva da V3, não uma segunda leitura da mesma coisa.
- **Em que amostra o desvio é estimado** → **expanding até `T−1`**, mínimo de 8 observações
  (`metodologia §5.1`). Com amostra cheia, a regra "sabe" a volatilidade de 2026 ao marcar 2008 —
  é look-ahead na própria marcação do evento.
- **"Cai" sobre o quê** → sobre a **variação**: `Δincl(T) = incl(T) − incl(T−1)`. "Cai mais de 1
  desvio" é afirmação sobre a **queda**; nível baixo não é evento de stress, achatamento abrupto é.

`stress = (Δincl(T) < −1 × σ_exp(Δincl até T−1)) OU (usdbrl_var_tri(T) > +10%)`. A disjunção é a
de RF-039 palavra por palavra. O **ramo EMBI** de `metodologia §4.3` fica **declaradamente fora**
(CA-106, L8): o EMBI+ morre em 30/07/2024 e `macro_quarterly.embi_delta_tri` tem **0** valores não
nulos nos 83 trimestres — o ramo não tem fonte, e preenchê-lo seria inventar dado.

Trimestre em que o ramo da inclinação não é avaliável (sem 8 observações anteriores, ou sem
`Δincl`) sai com `avaliavel_inclinacao=False` e o ramo contribui `False` — mas o relatório diz
**quais** são, para que "não houve stress" nunca se confunda com "não foi possível avaliar".

**Isto destrava `RegimesSchema.stress_flag`:** `stress_por_trimestre().set_index("quarter")
["stress_flag"]` é exatamente a `pd.Series` que `metricas_regime.montar_regimes(stress_flag=...)`
espera, e há teste que passa a série real e verifica que o bloqueio de `stress_flag` desaparece da
junção de **D-r** (o de `regime_v1` nulo, que é **D-m**, continua — não é desta feature).

## CA-107: o output é uma FAIXA, e a variância mínima é apoio — não é a resposta

A tradução para a regra provisória **D6** de ADR-003 é: **piso estrutural de 16-20%** (FGVcef)
**+ banda tática de 15-35% por regime**, e o peso de variância mínima do regime entra **truncado
na banda** (`peso_na_banda`). Nunca um número pontual: com `n` de 13 a 19 por regime e `p = 4`
ativos, o peso muda materialmente com o cap, com o conjunto de ativos e com a janela — e o
relatório publica as três sensibilidades para que isso seja visível, não afirmado.

> ⚠️ **BLOQUEIO DE ANTI-SPEC — `internacional_pesos.parquet` não é publicável na v1.**
> Anti-SPEC **§10.3.16** e **§10.5** põem "variância mínima por regime" e "fronteira eficiente"
> **fora da entrega de 2026-10-14**, e o `TODO.md` de F-026 repete em *Excluído* (→ **F-035**).
> A tabela é calculada porque o orquestrador desta feature a pediu explicitamente como insumo da
> tradução de D6, e sai com `especificacao_congelada=False` em **toda** linha, com
> `BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA` no relatório e `WARNING` no log. Publicá-la exige
> autorização humana explícita sobre a seção sagrada (`AGENTS.md §9`/`§14`). O que **é**
> publicável aqui (depois de ADR-001/ADR-003 aceitos) são os retornos por regime, as correlações
> de CA-104/105, o `stress_flag` de CA-106 e a **faixa** de CA-107.

## O que este módulo não faz

- **nenhuma previsão** (Anti-SPEC §10.2.10): "nos trimestres de stress o USDBRL rendeu X, n = Y",
  nunca "vai render".
- **nenhuma subtração** onde há excesso ou retorno real (Anti-SPEC §10.2.13): toda razão vem da
  coluna que F-017 já calculou por razão, e `excesso_por_razao` é importada de F-022.
- **nenhuma mistura de hedgeado com sem hedge** (D7/CA-104): `SP500_HEDGE`, `GOLD_BRL` e
  `UST10_BRL` **não existem** em `asset_returns_quarterly` e saem como `BLOQUEADO — FONTE
  INDISPONÍVEL` no relatório, nunca com proxy silencioso e nunca somados com a versão sem hedge.
- **nenhuma mistura de total return com price return** na covariância (Anti-SPEC §10.2.12): o
  internacional da carteira é `ACWI_BRL` (`is_total_return=True`), não `SP500_BRL` (`False`).
- **nenhum backtest** (Anti-SPEC §10.3.16): não há posição, rebalanceamento nem série de retorno
  de carteira em lugar nenhum — só pesos descritivos de uma covariância amostral.

**Sem rede, sem relógio, sem estado.** Entradas: `regimes_v1{,_asof}.parquet` (F-019/F-018),
`regime_neighbors_v3.parquet` (F-021), `asset_returns_quarterly.parquet` (F-017),
`macro_quarterly.parquet` (F-015), `raw_series`/`series_catalog` (F-013) e o calendário (F-008).
`fonte_versao` = `sha256` do conjunto `MODULOS_DO_INTERNACIONAL` — duas rodadas sobre o mesmo dado
dão Parquet byte-idêntico (RF-047/CA-121).

Referências: SPEC RF-038 (CA-104/105), RF-039 (CA-106/107), RF-040 (CA-108/109), RF-031 (CA-090)
· Anti-SPEC §10.1.1, §10.2.8, §10.2.10, §10.2.12, §10.2.13, §10.3.16, §10.5 · **ADR-003**
(Proposta, D6) · ADR-001 (Proposta) · ADR-004 (inclinação construída) ·
`docs/research/metodologia-regimes-macro.md §4` · `DECISIONS_LOG §2.3` (D-i, D-n, D-o, D-r) ·
`docs/wiki/context/F-022.md §4` · `docs/wiki/context/F-026.md`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    caminhos_dos_componentes,
)
from apps.pipeline.canonical.build_raw_series import (
    versao_build as _hash_dos_componentes,
)
from apps.pipeline.canonical.metricas_regime import (
    COLUNA_NOMINAL,
    COLUNA_PRIMARIA,
    Horizonte,
    conferir_gate,
    ler_neighbors_v3,
    ler_regimes_v1,
    ler_retornos,
    metricas_da_celula,
    montar_regimes,
    nome_do_regime_v3,
    observacoes_dos_vizinhos,
    quarter_do_horizonte,
    trimestres_por_regime_v1,
    vizinhos_da_lente_canonica,
)
from apps.pipeline.canonical.regimes_v1 import (
    Materializacao,
    alerta_n_baixo,
    conclusao_suprimida,
    especificacao_esta_congelada,
    ler_macro,
    status_adr_001,
    veredito_publicacao,
)
from apps.pipeline.canonical.regimes_v3 import (
    QUARTER_DO_COMITE,
    inclinacao_real_5a_3a,
    ledoit_wolf,
    quarter_seguinte,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, raiz_repo, sha256_de
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from apps.pipeline.extract.calendario_anbima import Calendario
from packages.shared.schemas.internacional import (
    ATIVO_CAMBIO,
    ATIVO_INTERNACIONAL_ALTERNATIVO,
    ATIVO_INTERNACIONAL_REPRESENTATIVO,
    ATIVOS_DA_TABELA_POR_REGIME,
    ATIVOS_SEM_FONTE,
    BANDA_TATICA_MAX,
    BANDA_TATICA_MIN,
    BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA,
    CAP_POR_ATIVO,
    CARTEIRA_VARIANCIA_MINIMA,
    ESCOPO_EXPANDING,
    ESCOPO_POR_REGIME,
    LENTE_V1,
    LENTE_V1_ASOF,
    LENTE_V3,
    LIMIAR_QUEDA_INCLINACAO_DP,
    LIMIAR_USDBRL_VAR_TRI_PCT,
    MIN_OBS_DESVIO_EXPANDING,
    PISO_ESTRUTURAL_MAX,
    PISO_ESTRUTURAL_MIN,
    RAMO_EMBI_FORA,
    SELO_NAO_RECOMENDACAO,
    SEM_CAP,
    SERIE_INCLINACAO_DO_STRESS,
    InternacionalPesosSchema,
    InternacionalPorRegimeSchema,
)
from packages.shared.schemas.raw_series import RawSeriesSchema
from packages.shared.schemas.series_catalog import SeriesCatalogMaterializedSchema

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Mapping, Sequence

    from apps.pipeline.canonical.regimes_v3 import Vizinho

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes
# ─────────────────────────────────────────────────────────────────────────────

NOME_POR_REGIME = "internacional_por_regime.parquet"
NOME_PESOS = "internacional_pesos.parquet"
NOME_RELATORIO = "relatorio_internacional.json"
NOME_MACRO = "macro_quarterly.parquet"

#: Os módulos que determinam o conteúdo destas tabelas, **nesta ordem** — base de `versao_build`.
#: Mesmo critério de F-014/F-015/F-019/F-021/F-022: este módulo, o contrato das duas tabelas que
#: ele escreve, e os produtores de **todas** as entradas. Mudar qualquer um muda o Parquet.
MODULOS_DO_INTERNACIONAL: tuple[str, ...] = (
    "apps.pipeline.canonical.internacional",
    "packages.shared.schemas.internacional",
    "packages.shared.schemas.asset_returns_quarterly",
    "packages.shared.schemas.regimes",
    "apps.pipeline.canonical.metricas_regime",
    "apps.pipeline.canonical.regimes_v1",
    "apps.pipeline.canonical.regimes_v3",
    "apps.pipeline.canonical.retornos",
    "apps.pipeline.canonical.macro_quarterly",
)

CAMINHO_ADR_003 = Path("docs") / "decisions" / "adr" / "ADR-003-abordagem-alocacao-internacional.md"
STATUS_ADR_ACEITO = "ACEITA"
STATUS_ADR_DESCONHECIDO = "DESCONHECIDO"
_RE_STATUS_ADR = re.compile(r"^-\s*\*\*Status:\*\*\s*(?P<valor>.+)$", re.MULTILINE)

ASSET_ID_IBOV = "IBOV"
ASSET_ID_IMAB = "IMAB"
ASSET_ID_CDI = "CDI"

COLUNA_USDBRL_VAR = "usdbrl_var_tri"
COLUNA_EMBI_DELTA = "embi_delta_tri"

N_PIORES_DO_IBOV = 10
"""Os "10 piores trimestres do IBOV" de CA-105, literalmente."""

MIN_PARES_CORRELACAO = 2
"""Correlação exige 2 pares. Com 1, `pandas` devolve `NaN`; com 0, nada — os dois saem `None`."""

MIN_OBS_COVARIANCIA = 4
"""`p = 4` ativos: menos de 4 observações não dá nem para a covariância amostral ter rank. O
shrinkage ainda a torna inversível, mas o número não teria leitura — a célula sai sem pesos."""

TOLERANCIA_KKT = 1e-10
"""Folga de viabilidade do enumerador de conjunto ativo (caixa e soma), em peso."""


class AlocacaoInviavel(ErroDeExtracao):
    """A restrição pedida não tem solução (ex.: `cap × p < 1`)."""


# ─────────────────────────────────────────────────────────────────────────────
# A regra de risk-off (RF-039 / CA-106)
# ─────────────────────────────────────────────────────────────────────────────


def desvio_expanding_ate_t_menos_1(serie: pd.Series, *, min_obs: int) -> pd.Series:
    """`σ` amostral de `serie` usando **só** observações anteriores a cada índice.

    `shift(1)` antes de `expanding()` é o que torna a afirmação verificável: o desvio da linha `T`
    é calculado sobre `T−1, T−2, ...` e **nenhuma** linha `>= T` entra. Mexer num valor futuro não
    muda o desvio de `T` — e isso é teste (`test_expanding_nao_usa_o_futuro`), não promessa.

    Menos de `min_obs` observações anteriores ⇒ `NaN`, que o chamador traduz em
    `avaliavel_inclinacao=False`. Nunca 0, nunca o desvio da amostra cheia.
    """
    anteriores = serie.shift(1)
    desvio = anteriores.expanding(min_periods=min_obs).std(ddof=1)
    contagem = anteriores.expanding(min_periods=1).count()
    return desvio.where(contagem >= min_obs)


def stress_por_trimestre(
    *,
    inclinacao: pd.Series,
    usdbrl_var_tri: pd.Series,
    limiar_dp: float = LIMIAR_QUEDA_INCLINACAO_DP,
    limiar_usdbrl_pct: float = LIMIAR_USDBRL_VAR_TRI_PCT,
    min_obs: int = MIN_OBS_DESVIO_EXPANDING,
) -> pd.DataFrame:
    """A disjunção de RF-039/CA-106, trimestre a trimestre, com os dois ramos **separados**.

    `stress = (Δincl < −limiar_dp × σ_exp(Δincl até T−1)) OU (usdbrl_var_tri > limiar_usdbrl_pct)`.

    As duas entradas vêm indexadas por `quarter` (string ordenável), `inclinacao` em pp e
    `usdbrl_var_tri` em **por cento** (D-o). O ramo EMBI fica fora e declarado
    (`RAMO_EMBI_FORA`). A saída tem uma linha por trimestre — inclusive os não avaliáveis, que são
    nomeados em vez de silenciosamente `False`.
    """
    quarters = sorted(set(inclinacao.index) | set(usdbrl_var_tri.index))
    incl = inclinacao.reindex(quarters).astype("float64")
    cambio = usdbrl_var_tri.reindex(quarters).astype("float64")

    delta = incl.diff()
    desvio = desvio_expanding_ate_t_menos_1(delta, min_obs=min_obs)
    limiar_queda = -limiar_dp * desvio

    avaliavel = delta.notna() & desvio.notna()
    ramo_incl = (delta < limiar_queda) & avaliavel
    ramo_cambio = cambio > limiar_usdbrl_pct

    return pd.DataFrame(
        {
            "quarter": quarters,
            "inclinacao": incl.to_numpy(),
            "delta_inclinacao": delta.to_numpy(),
            "desvio_expanding": desvio.to_numpy(),
            "limiar_queda": limiar_queda.to_numpy(),
            "avaliavel_inclinacao": avaliavel.to_numpy(),
            "ramo_inclinacao": ramo_incl.to_numpy(),
            "usdbrl_var_tri": cambio.to_numpy(),
            "ramo_usdbrl": ramo_cambio.fillna(False).to_numpy(),
            "ramo_embi": False,
            "stress_flag": (ramo_incl | ramo_cambio.fillna(False)).to_numpy(),
        }
    )


def serie_de_stress_flag(stress: pd.DataFrame) -> pd.Series:
    """A `pd.Series` indexada por `quarter` que `montar_regimes(stress_flag=...)` espera.

    É o ponto de contato com **D-r**: F-022 deixou `RegimesSchema.stress_flag` bloqueado por falta
    de definição e recebe a definição **daqui**, sem que nenhuma das duas features reimplemente a
    outra.
    """
    return pd.Series(
        stress["stress_flag"].astype(bool).to_numpy(),
        index=stress["quarter"].astype(str),
        name="stress_flag",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Correlação condicional (RF-038 / CA-105)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Correlacao:
    """Uma correlação de Pearson com o `n` de **pares** que a produziu. `n` em toda célula."""

    valor: float | None
    n_pares: int

    def como_dicionario(self, rotulo: str = "") -> dict[str, Any]:
        """Formato do relatório: sempre o par `(correlacao, n)`, nunca a correlação sozinha."""
        saida: dict[str, Any] = {"correlacao": self.valor, "n_pares": self.n_pares}
        if rotulo:
            saida["rotulo"] = rotulo
        return saida


def correlacao_de_pares(a: pd.Series, b: pd.Series) -> Correlacao:
    """Pearson entre duas séries **alinhadas por índice**, com o `n` de pares completos.

    Alinhamento por índice (`quarter`), nunca por posição: `ACWI_BRL` e `IBOV` têm padrões de nulo
    diferentes, e correlacionar por posição casaria trimestres distintos. Desvio zero de qualquer
    lado devolve `None` em vez de `NaN` (é o caso do `CDI`, cuja variância trimestral é quase 0 —
    mas não exatamente 0, então a guarda é sobre o valor não finito, não sobre o ativo).
    """
    par = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    n = int(len(par))
    if n < MIN_PARES_CORRELACAO:
        return Correlacao(None, n)
    esquerda = par["a"].astype("float64")
    direita = par["b"].astype("float64")
    desvios = (float(esquerda.std(ddof=1)), float(direita.std(ddof=1)))
    if any(not np.isfinite(d) or d == 0.0 for d in desvios):
        return Correlacao(None, n)
    valor = float(esquerda.corr(direita))
    if not np.isfinite(valor):  # pragma: no cover - guarda dupla
        return Correlacao(None, n)
    return Correlacao(float(np.clip(valor, -1.0, 1.0)), n)


def serie_por_quarter(
    retornos: pd.DataFrame, asset_id: str, *, quarters: Sequence[str], coluna: str = COLUNA_NOMINAL
) -> pd.Series:
    """`coluna` de um ativo nos `quarters` pedidos, indexada por `quarter`."""
    fatia = retornos.loc[
        (retornos["asset_id"] == asset_id) & (retornos["quarter"].isin(list(quarters)))
    ]
    return pd.Series(
        fatia[coluna].to_numpy(dtype="float64"), index=fatia["quarter"].astype(str), name=asset_id
    )


def piores_trimestres_do_ibov(
    retornos: pd.DataFrame, *, n: int = N_PIORES_DO_IBOV, quarters: Sequence[str] | None = None
) -> list[str]:
    """Os `n` trimestres de **pior** `ret_tri` do IBOV (CA-105), em ordem crescente de retorno.

    Empate resolve pelo trimestre mais antigo, para o resultado ser determinístico.
    """
    todos = sorted(str(q) for q in retornos["quarter"].unique())
    alvo = list(quarters) if quarters is not None else todos
    serie = serie_por_quarter(retornos, ASSET_ID_IBOV, quarters=alvo).dropna()
    ordem = pd.DataFrame(
        {"valor": serie.to_numpy(dtype="float64"), "quarter": [str(q) for q in serie.index]}
    ).sort_values(by=["valor", "quarter"], kind="mergesort")
    return [str(q) for q in ordem["quarter"].head(n)]


def hedge_no_stress(
    retornos: pd.DataFrame, stress: pd.DataFrame, *, par: tuple[str, str] = (ATIVO_CAMBIO, "IBOV")
) -> dict[str, Any]:
    """`corr(USDBRL, IBOV)` nos trimestres de **stress** × **não** stress, com `n` nos dois.

    É o argumento central de `metodologia §4.3` item 3: *se o hedge só funciona no stress, esse é
    o argumento para dolarizar*. A comparação só tem leitura com os dois `n` ao lado — uma
    correlação de 8 pares e outra de 70 não são a mesma medida.
    """
    a, b = par
    marcados = stress.loc[stress["stress_flag"].astype(bool), "quarter"].astype(str).tolist()
    nao = stress.loc[~stress["stress_flag"].astype(bool), "quarter"].astype(str).tolist()
    piores = piores_trimestres_do_ibov(retornos)
    blocos = {
        "stress": marcados,
        "nao_stress": nao,
        "todos": sorted(str(q) for q in retornos["quarter"].unique()),
        "dez_piores_do_ibov": piores,
    }
    saida: dict[str, Any] = {"par": f"{a} x {b}", "blocos": {}}
    for rotulo, quarters in blocos.items():
        correlacao = correlacao_de_pares(
            serie_por_quarter(retornos, a, quarters=quarters),
            serie_por_quarter(retornos, b, quarters=quarters),
        )
        saida["blocos"][rotulo] = {
            **correlacao.como_dicionario(),
            "n_trimestres_do_bloco": len(quarters),
            "alerta_n_baixo": alerta_n_baixo(correlacao.n_pares),
            "conclusao_suprimida": conclusao_suprimida(correlacao.n_pares),
        }
    saida["neutralizacao_usd"] = neutralizacao_do_usd(retornos, marcados)
    saida["leitura"] = (
        "Descritivo (Anti-SPEC 10.2.10): a correlacao MEDIDA nos trimestres marcados, com n. "
        "Nao e previsao de correlacao futura, e correlacao condicional a um evento estimada em "
        f"{len(marcados)} trimestres tem erro-padrao largo."
    )
    return saida


def neutralizacao_do_usd(retornos: pd.DataFrame, quarters: Sequence[str]) -> dict[str, Any]:
    """ "Quanto de USD neutraliza a queda do IBOV" nos trimestres dados (RF-039), com `n`.

    A fração `x` de `USDBRL` numa mistura `x·USDBRL + (1−x)·IBOV` cujo retorno médio **nos
    trimestres dados** é zero:  `x = −r_ibov / (r_usd − r_ibov)`.

    É aritmética sobre dois retornos médios já medidos — **não** é otimização, não é backtest e
    não é recomendação: não há rebalanceamento, custo nem posição em lugar nenhum. `None` quando
    o IBOV não caiu em média (não há o que neutralizar) ou quando o denominador é ~0.
    """
    ibov = serie_por_quarter(retornos, ASSET_ID_IBOV, quarters=quarters).dropna()
    usd = serie_por_quarter(retornos, ATIVO_CAMBIO, quarters=quarters).dropna()
    par = pd.concat([ibov.rename("ibov"), usd.rename("usd")], axis=1, join="inner").dropna()
    n = int(len(par))
    if n < MIN_PARES_CORRELACAO:
        return {"fracao_usd": None, "n": n, "motivo": "menos de 2 pares"}
    r_ibov = float(par["ibov"].mean())
    r_usd = float(par["usd"].mean())
    denominador = r_usd - r_ibov
    if r_ibov >= 0.0:
        return {
            "fracao_usd": None,
            "n": n,
            "ret_medio_ibov": r_ibov,
            "ret_medio_usdbrl": r_usd,
            "motivo": "IBOV nao caiu em media nestes trimestres: nao ha queda a neutralizar",
        }
    if abs(denominador) <= TOLERANCIA_KKT:
        return {"fracao_usd": None, "n": n, "motivo": "denominador ~0"}
    return {
        "fracao_usd": float(-r_ibov / denominador),
        "n": n,
        "ret_medio_ibov": r_ibov,
        "ret_medio_usdbrl": r_usd,
        "alerta_n_baixo": alerta_n_baixo(n),
        "conclusao_suprimida": conclusao_suprimida(n),
        "formula": "x = -r_ibov / (r_usd - r_ibov), com r_* a media simples no bloco",
        "leitura": (
            "x% em dolar zera o retorno MEDIO da mistura nos trimestres marcados. Media de "
            "retornos, nao garantia trimestre a trimestre: a dispersao esta em pior_tri."
        ),
    }


def risk_off_em_t_mais_1(
    retornos: pd.DataFrame,
    stress: pd.DataFrame,
    *,
    ativos: Sequence[str] = ATIVOS_DA_TABELA_POR_REGIME,
) -> dict[str, Any]:
    """O que o dado diz sobre reduzir/aumentar internacional **depois** de um trimestre de stress.

    Para cada ativo: retorno médio (nominal e excesso sobre CDI, por razão) no trimestre
    **seguinte** aos trimestres de stress, contra o seguinte aos de não stress, com `n` em cada.
    O mapeamento `T → T+1` usa `quarter_seguinte` de F-021 — stress no último trimestre da janela
    não contribui, e a ausência aparece no `n`, nunca como retorno do próprio `T`.

    Descritivo: a pergunta "dolarizar depois do stress funcionou nos últimos 20 anos?" tem
    resposta medida. A pergunta "vai funcionar" **não é desta entrega** (Anti-SPEC §10.2.10).
    """
    marcados = stress.loc[stress["stress_flag"].astype(bool), "quarter"].astype(str).tolist()
    nao = stress.loc[~stress["stress_flag"].astype(bool), "quarter"].astype(str).tolist()

    def _seguintes(quarters: Sequence[str]) -> list[str]:
        disponiveis = {str(q) for q in retornos["quarter"].unique()}
        seguintes = [quarter_seguinte(q) for q in quarters]
        return sorted({s for s in seguintes if s is not None and s in disponiveis})

    blocos = {"apos_stress": _seguintes(marcados), "apos_nao_stress": _seguintes(nao)}
    por_ativo: dict[str, Any] = {}
    for asset_id in ativos:
        linha: dict[str, Any] = {}
        for rotulo, quarters in blocos.items():
            nominal = serie_por_quarter(retornos, asset_id, quarters=quarters).dropna()
            excesso = serie_por_quarter(
                retornos, asset_id, quarters=quarters, coluna=COLUNA_PRIMARIA
            ).dropna()
            n = int(len(nominal))
            linha[rotulo] = {
                "n": n,
                "ret_medio": None if n == 0 else float(nominal.mean()),
                "ret_mediana": None if n == 0 else float(nominal.median()),
                "excesso_cdi_medio": None if excesso.empty else float(excesso.mean()),
                "hit_ratio": None if n == 0 else float((nominal > 0).mean()),
                "alerta_n_baixo": alerta_n_baixo(n),
                "conclusao_suprimida": conclusao_suprimida(n),
            }
        por_ativo[asset_id] = linha
    return {
        "trimestres_de_stress": marcados,
        "n_stress": len(marcados),
        "t_mais_1_de_stress": blocos["apos_stress"],
        "t_mais_1_de_nao_stress": blocos["apos_nao_stress"],
        "por_ativo": por_ativo,
        "nota_look_ahead": (
            "T+1 e look-ahead POR DESENHO e declarado (mesma natureza de CA-102 em F-022): a "
            "pergunta e sobre o trimestre SEGUINTE ao evento. O stress_flag de T, porem, usa "
            "desvio expanding ate T-1 — a MARCACAO nao conhece o futuro."
        ),
        "leitura": (
            "Descritivo. Com n de stress na casa das dezenas e desvio trimestral de 10-20 pp, "
            "diferencas menores que ~2x o erro-padrao nao se distinguem de ruido."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Variância mínima long-only (apoio de D6 — NÃO publicável, ver o aviso do módulo)
# ─────────────────────────────────────────────────────────────────────────────


def variancia_minima(sigma: np.ndarray, *, cap: float = SEM_CAP) -> np.ndarray:
    """`argmin w'Σw` sujeito a `1'w = 1` e `0 <= w_i <= cap`, **exato**, por conjunto ativo.

    Sem solver externo e sem iteração: para `p` ativos, enumera as `3^p` partições
    (livre / no piso 0 / no teto `cap`); em cada uma resolve o sistema KKT linear das variáveis
    livres, descarta o que não é viável (caixa ou soma) e devolve a viável de **menor** variância.
    Com `Σ` definida positiva o problema é estritamente convexo, logo a solução é única, e a
    partição ótima está entre as enumeradas — então o mínimo sobre as candidatas viáveis **é** o
    ótimo. Com `p = 4` são 81 sistemas 5×5: microssegundos.

    **Por que não gradiente projetado.** O teste de 2 ativos compara com a forma fechada
    `w1 = (σ22 − σ12)/(σ11 + σ22 − 2σ12)` com `1e-12`; iteração não entrega isso sem tuning, e
    tuning de tolerância em cima de um número que vai a comitê é exatamente o que não se faz.
    `scipy` não está no `.venv` e instalar é dependência nova ⇒ ADR (`AGENTS.md §12`).

    O sistema de cada partição, com `F` livre e `U` no teto:
    `[[Σ_FF, −1], [1', 0]] · [w_F, λ] = [−Σ_FU·w_U, 1 − cap·|U|]`.
    """
    sigma = np.asarray(sigma, dtype="float64")
    if sigma.ndim != 2 or sigma.shape[0] != sigma.shape[1] or sigma.shape[0] < 1:
        msg = f"variancia_minima exige matriz quadrada (p, p); recebi {sigma.shape}"
        raise AlocacaoInviavel(msg)
    p = int(sigma.shape[0])
    if not 0.0 < cap <= 1.0:
        msg = f"cap deve estar em (0, 1]; recebi {cap}"
        raise AlocacaoInviavel(msg)
    if cap * p < 1.0 - TOLERANCIA_KKT:
        msg = f"cap={cap} com p={p} nao alcanca soma 1 (cap*p = {cap * p})"
        raise AlocacaoInviavel(msg)

    melhor: tuple[float, tuple[float, ...]] | None = None
    for estados in itertools.product((0, 1, 2), repeat=p):
        livres = [i for i, e in enumerate(estados) if e == 0]
        teto = [i for i, e in enumerate(estados) if e == 2]
        w = np.zeros(p)
        w[teto] = cap
        resto = 1.0 - cap * len(teto)
        if livres:
            if resto < -TOLERANCIA_KKT:
                continue
            k = len(livres)
            matriz = np.zeros((k + 1, k + 1))
            matriz[:k, :k] = sigma[np.ix_(livres, livres)]
            matriz[:k, k] = -1.0
            matriz[k, :k] = 1.0
            lado = np.zeros(k + 1)
            if teto:
                lado[:k] = -sigma[np.ix_(livres, teto)] @ w[teto]
            lado[k] = resto
            try:
                solucao = np.linalg.solve(matriz, lado)
            except np.linalg.LinAlgError:
                continue
            w[livres] = solucao[:k]
        elif abs(resto) > TOLERANCIA_KKT:
            continue
        if w.min() < -TOLERANCIA_KKT or w.max() > cap + TOLERANCIA_KKT:
            continue
        if abs(float(w.sum()) - 1.0) > TOLERANCIA_KKT:
            continue
        candidata = np.clip(w, 0.0, cap)
        candidata = candidata / candidata.sum()
        variancia = float(candidata @ sigma @ candidata)
        chave = (variancia, tuple(candidata.tolist()))
        if melhor is None or chave < melhor:
            melhor = chave
    if melhor is None:  # pragma: no cover - só com Σ degenerada em toda partição
        msg = f"nenhuma carteira viavel com cap={cap} e p={p}"
        raise AlocacaoInviavel(msg)
    return np.array(melhor[1], dtype="float64")


@dataclass(frozen=True)
class Pesos:
    """Os pesos de uma carteira, com tudo que a revisão numérica precisa para refazê-los."""

    ativos: tuple[str, ...]
    pesos: tuple[float, ...]
    n_obs: int
    rho: float
    cap: float
    variancia: float

    @property
    def internacional(self) -> float | None:
        """O peso do internacional representativo — a resposta "quanto no exterior"."""
        if ATIVO_INTERNACIONAL_REPRESENTATIVO not in self.ativos:
            return None
        return self.pesos[self.ativos.index(ATIVO_INTERNACIONAL_REPRESENTATIVO)]

    def como_dicionario(self) -> dict[str, Any]:
        """Formato do relatório: pesos nomeados, `n`, `rho` e a variância da carteira."""
        return {
            "carteira": list(self.ativos),
            "pesos": dict(zip(self.ativos, self.pesos, strict=True)),
            "peso_internacional": self.internacional,
            "n_obs": self.n_obs,
            "rho_shrinkage": self.rho,
            "cap": self.cap,
            "variancia_trimestral": self.variancia,
            "alerta_n_baixo": alerta_n_baixo(self.n_obs),
            "conclusao_suprimida": conclusao_suprimida(self.n_obs),
        }


def matriz_de_retornos(
    retornos: pd.DataFrame,
    *,
    quarters: Sequence[str],
    ativos: Sequence[str] = CARTEIRA_VARIANCIA_MINIMA,
    coluna: str = COLUNA_NOMINAL,
) -> pd.DataFrame:
    """A matriz `quarter × ativo` de retornos, **só** com trimestres de vetor completo.

    `dropna()` em vez de imputação: trimestre sem o retorno de um dos ativos não entra na
    covariância (Anti-SPEC §10.1.1). Quantos ficaram de fora é o `n_obs` da célula, que vai à
    tabela — nunca escondido.
    """
    disponiveis = {str(a) for a in retornos["asset_id"].unique()}
    faltando = [a for a in ativos if a not in disponiveis]
    if faltando:
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {faltando} nao estao em asset_returns_quarterly"
        raise FonteIndisponivel(msg)
    colunas = {
        str(a): serie_por_quarter(retornos, str(a), quarters=quarters, coluna=coluna)
        for a in ativos
    }
    larga = pd.concat(colunas, axis=1, join="outer")
    return larga.loc[:, [str(a) for a in ativos]].dropna().sort_index()


def pesos_de_amostra(
    amostra: pd.DataFrame, *, cap: float = CAP_POR_ATIVO, min_obs: int = MIN_OBS_COVARIANCIA
) -> Pesos | None:
    """Variância mínima sobre a covariância **encolhida** (Ledoit-Wolf) de `amostra`.

    `ledoit_wolf` é **importada** de F-021 (`regimes_v3.py`), não reimplementada: é a mesma
    estimativa que a Mahalanobis da V3 usa, com `rho` **medido** e não escolhido. `None` quando a
    amostra tem menos de `min_obs` trimestres completos — a célula aparece na tabela sem pesos, em
    vez de com pesos de 2 observações.
    """
    if len(amostra) < min_obs:
        return None
    shrinkage = ledoit_wolf(amostra.to_numpy(dtype="float64"))
    w = variancia_minima(shrinkage.sigma, cap=cap)
    return Pesos(
        ativos=tuple(str(c) for c in amostra.columns),
        pesos=tuple(float(x) for x in w),
        n_obs=int(len(amostra)),
        rho=float(shrinkage.intensidade),
        cap=float(cap),
        variancia=float(w @ shrinkage.sigma @ w),
    )


def truncar_na_banda(
    peso: float | None, *, minimo: float = BANDA_TATICA_MIN, maximo: float = BANDA_TATICA_MAX
) -> float | None:
    """O peso de variância mínima **truncado na banda tática** de ADR-003 (CA-107).

    É a tradução de D6: a otimização informa **onde na banda**, nunca se sai dela. Com `n ≈ 15` e
    `p = 4`, o peso cru varia de 0% a 60% conforme o cap e o conjunto — a banda é o que impede
    que essa variação chegue ao slide como precisão.
    """
    if peso is None:
        return None
    return float(min(max(float(peso), minimo), maximo))


def pesos_expanding(
    retornos: pd.DataFrame,
    *,
    ativos: Sequence[str] = CARTEIRA_VARIANCIA_MINIMA,
    cap: float = CAP_POR_ATIVO,
    min_obs: int = MIN_OBS_DESVIO_EXPANDING,
) -> dict[str, Pesos]:
    """`{quarter: Pesos}` com a covariância de `T` estimada **só** com trimestres até `T−1`.

    É a única leitura em que "o peso de `T`" tem sentido operacional (`metodologia §5.1`): nada
    posterior a `T−1` entra, inclusive o próprio `T`. Mexer numa linha futura não muda nenhum peso
    anterior — e isso é teste (`test_pesos_expanding_nao_usam_o_futuro`).
    """
    larga = matriz_de_retornos(
        retornos,
        quarters=sorted(str(q) for q in retornos["quarter"].unique()),
        ativos=ativos,
    )
    saida: dict[str, Pesos] = {}
    indices = [str(q) for q in larga.index]
    for posicao, quarter in enumerate(indices):
        anteriores = larga.iloc[:posicao]
        pesos = pesos_de_amostra(anteriores, cap=cap, min_obs=min_obs)
        if pesos is not None:
            saida[quarter] = pesos
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# A tabela por regime (RF-038 / CA-104 / CA-105)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Lente:
    """Uma das três leituras de RF-038: que regimes, que materialização, que horizonte."""

    rotulo: str
    materializacao: Materializacao
    horizonte: Horizonte
    por_que: str


LENTES: tuple[Lente, ...] = (
    Lente(
        rotulo=LENTE_V1,
        materializacao=Materializacao.REVISED,
        horizonte=Horizonte.CONTEMPORANEO,
        por_que="a leitura descritiva de RF-038: neste quadrante, o internacional em BRL rendeu X",
    ),
    Lente(
        rotulo=LENTE_V1_ASOF,
        materializacao=Materializacao.ASOF,
        horizonte=Horizonte.CONTEMPORANEO,
        por_que=(
            "a leitura operacional (F-018/CA-072): quadrante de T com o que se sabia no fim de T. "
            "CA-074 esta acionado (33,33% de troca de rotulo) — nao e operacional pelo criterio "
            "escrito, e por isso a lente aparece COM o rotulo, nunca fundida com a revised"
        ),
    ),
    Lente(
        rotulo=LENTE_V3,
        materializacao=Materializacao.REVISED,
        horizonte=Horizonte.T_MAIS_1,
        por_que=(
            "momentos semelhantes a 2026Q3 medidos no trimestre SEGUINTE (CA-102) — look-ahead "
            "por desenho e declarado, como em F-022"
        ),
    ),
)


def _celula_internacional(
    observacoes: pd.DataFrame,
    *,
    lente: str,
    regime: str,
    asset_id: str,
    retornos: pd.DataFrame,
    quarters_do_regime: Sequence[str],
    is_total_return: bool | None,
    congelada: bool,
    fonte_versao: str,
) -> dict[str, Any]:
    """Uma célula de `internacional_por_regime` — retornos de F-022 + as 2 correlações de CA-105.

    As colunas de retorno saem **inteiras** de `metricas_regime.metricas_da_celula`: é a mesma
    função, com a mesma fatia, no mesmo horizonte. Nada é recalculado aqui (CA-104).
    """
    base = metricas_da_celula(
        observacoes,
        lente=lente,
        regime=regime,
        asset_id=asset_id,
        data_inicio_serie=pd.Timestamp("2006-01-01"),
        referencia_beta=pd.Series(dtype="float64"),
        fonte_versao=fonte_versao,
    )
    propria = serie_por_quarter(retornos, asset_id, quarters=quarters_do_regime)
    contra_ibov = correlacao_de_pares(
        propria, serie_por_quarter(retornos, ASSET_ID_IBOV, quarters=quarters_do_regime)
    )
    contra_imab = correlacao_de_pares(
        propria, serie_por_quarter(retornos, ASSET_ID_IMAB, quarters=quarters_do_regime)
    )
    n = int(base["n_obs"])
    return {
        "lente": lente,
        "regime": regime,
        "asset_id": asset_id,
        "n_obs": n,
        "ret_medio": base["ret_medio"],
        "ret_mediana": base["ret_mediana"],
        "excesso_cdi": base["excesso_cdi"],
        "ret_real": base["ret_real"],
        "hit_ratio_cdi": base["hit_ratio_cdi"],
        "corr_ibov": contra_ibov.valor,
        "n_pares_ibov": min(contra_ibov.n_pares, n),
        "corr_imab": contra_imab.valor,
        "n_pares_imab": min(contra_imab.n_pares, n),
        "is_total_return": is_total_return,
        "alerta_n_baixo": alerta_n_baixo(n),
        "conclusao_suprimida": conclusao_suprimida(n),
        "especificacao_congelada": congelada,
        "fonte_versao": fonte_versao,
    }


def _flag_total_return(retornos: pd.DataFrame) -> dict[str, bool | None]:
    """`{asset_id: is_total_return}` — a flag de CA-064, uma por ativo, sem inventar `False`."""
    saida: dict[str, bool | None] = {}
    for asset_id, grupo in retornos.groupby("asset_id"):
        valores = grupo["is_total_return"].dropna().unique()
        saida[str(asset_id)] = None if len(valores) == 0 else bool(valores[0])
    return saida


def montar_por_regime(
    *,
    regimes: Mapping[str, pd.DataFrame],
    retornos: pd.DataFrame,
    vizinhos: Sequence[Vizinho],
    congelada: bool,
    fonte_versao: str,
    ativos: Sequence[str] = ATIVOS_DA_TABELA_POR_REGIME,
    quarter_ref_v3: str = QUARTER_DO_COMITE,
) -> pd.DataFrame:
    """`internacional_por_regime` nas três lentes, validada por `InternacionalPorRegimeSchema`."""
    flags = _flag_total_return(retornos)
    linhas: list[dict[str, Any]] = []
    for lente in LENTES:
        if lente.rotulo == LENTE_V3:
            regime_v3 = nome_do_regime_v3(quarter_ref_v3)
            observadas = observacoes_dos_vizinhos(vizinhos, retornos, horizonte=lente.horizonte)
            alvos = sorted(str(q) for q in observadas["quarter"].unique())
            grupos = {regime_v3: alvos}
            fonte_das_obs: dict[str, pd.DataFrame] = {regime_v3: observadas}
        else:
            grupos_regime = trimestres_por_regime_v1(regimes[lente.materializacao.value])
            grupos = {
                rotulo: [quarter_do_horizonte(q, lente.horizonte) for q in quarters]
                for rotulo, quarters in grupos_regime.items()
            }
            fonte_das_obs = {}
        for regime, alvos in grupos.items():
            janela = fonte_das_obs.get(regime)
            if janela is None:
                janela = retornos.loc[retornos["quarter"].isin(alvos)]
            for asset_id in ativos:
                linhas.append(
                    _celula_internacional(
                        janela.loc[janela["asset_id"] == asset_id],
                        lente=lente.rotulo,
                        regime=regime,
                        asset_id=asset_id,
                        retornos=retornos,
                        quarters_do_regime=alvos,
                        is_total_return=flags.get(asset_id),
                        congelada=congelada,
                        fonte_versao=fonte_versao,
                    )
                )
    quadro = pd.DataFrame(linhas).sort_values(by=["lente", "regime", "asset_id"], kind="mergesort")
    return InternacionalPorRegimeSchema.validate(  # type: ignore[return-value]
        quadro.reset_index(drop=True), lazy=True
    )


def montar_pesos(
    *,
    regimes_v1: pd.DataFrame,
    retornos: pd.DataFrame,
    fonte_versao: str,
    ativos: Sequence[str] = CARTEIRA_VARIANCIA_MINIMA,
    caps: Sequence[float] = (CAP_POR_ATIVO, SEM_CAP),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """`internacional_pesos` nos dois escopos e nos dois caps + o resumo para o relatório.

    **NÃO publicável** (Anti-SPEC §10.3.16/§10.5): `especificacao_congelada` sai `False` em toda
    linha, por construção, e o relatório carrega `BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA`.
    """
    carteira = "+".join(ativos)
    grupos = trimestres_por_regime_v1(regimes_v1)
    linhas: list[dict[str, Any]] = []
    resumo: dict[str, Any] = {"por_regime": {}, "expanding": {}, "carteira": list(ativos)}

    for cap in caps:
        rotulo_cap = f"cap_{cap:.2f}"
        resumo["por_regime"].setdefault(rotulo_cap, {})
        for regime, quarters in grupos.items():
            amostra = matriz_de_retornos(retornos, quarters=quarters, ativos=ativos)
            pesos = pesos_de_amostra(amostra, cap=cap)
            if pesos is None:
                resumo["por_regime"][rotulo_cap][regime] = {
                    "pesos": None,
                    "n_obs": int(len(amostra)),
                    "motivo": f"menos de {MIN_OBS_COVARIANCIA} trimestres completos",
                }
                continue
            resumo["por_regime"][rotulo_cap][regime] = {
                **pesos.como_dicionario(),
                "peso_na_banda": truncar_na_banda(pesos.internacional),
                "selo": SELO_NAO_RECOMENDACAO,
            }
            linhas.extend(
                _linhas_de_pesos(
                    pesos,
                    escopo=ESCOPO_POR_REGIME,
                    chave=regime,
                    carteira=carteira,
                    fonte_versao=fonte_versao,
                )
            )

        por_quarter = pesos_expanding(retornos, ativos=ativos, cap=cap)
        for quarter, pesos in por_quarter.items():
            linhas.extend(
                _linhas_de_pesos(
                    pesos,
                    escopo=ESCOPO_EXPANDING,
                    chave=quarter,
                    carteira=carteira,
                    fonte_versao=fonte_versao,
                )
            )
        internacionais = [
            p.internacional for p in por_quarter.values() if p.internacional is not None
        ]
        ultimo = max(por_quarter) if por_quarter else None
        resumo["expanding"][rotulo_cap] = {
            "n_trimestres_com_peso": len(por_quarter),
            "primeiro_quarter": min(por_quarter) if por_quarter else None,
            "ultimo_quarter": ultimo,
            "peso_internacional_no_ultimo": (
                None if ultimo is None else por_quarter[ultimo].internacional
            ),
            "peso_internacional_medio_2006_2026": (
                float(np.mean(internacionais)) if internacionais else None
            ),
            "peso_internacional_minimo": min(internacionais) if internacionais else None,
            "peso_internacional_maximo": max(internacionais) if internacionais else None,
            "peso_na_banda_no_ultimo": (
                None if ultimo is None else truncar_na_banda(por_quarter[ultimo].internacional)
            ),
            "selo": SELO_NAO_RECOMENDACAO,
            "sem_look_ahead": "a covariancia de T usa somente trimestres <= T-1",
        }

    quadro = pd.DataFrame(linhas).sort_values(
        by=["escopo", "chave", "cap", "carteira", "asset_id"], kind="mergesort"
    )
    validada = InternacionalPesosSchema.validate(quadro.reset_index(drop=True), lazy=True)
    return validada, resumo  # type: ignore[return-value]


def _linhas_de_pesos(
    pesos: Pesos, *, escopo: str, chave: str, carteira: str, fonte_versao: str
) -> list[dict[str, Any]]:
    """Uma linha por ativo, com o `peso_na_banda` **só** na linha do internacional (CA-107)."""
    return [
        {
            "escopo": escopo,
            "chave": chave,
            "carteira": carteira,
            "asset_id": asset_id,
            "peso": float(peso),
            "cap": pesos.cap,
            "peso_na_banda": (
                truncar_na_banda(peso) if asset_id == ATIVO_INTERNACIONAL_REPRESENTATIVO else None
            ),
            "n_obs": pesos.n_obs,
            "rho_shrinkage": pesos.rho,
            "alerta_n_baixo": alerta_n_baixo(pesos.n_obs),
            "conclusao_suprimida": conclusao_suprimida(pesos.n_obs),
            "especificacao_congelada": False,
            "fonte_versao": fonte_versao,
        }
        for asset_id, peso in zip(pesos.ativos, pesos.pesos, strict=True)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# A tradução para D6 (CA-107)
# ─────────────────────────────────────────────────────────────────────────────


def tabela_de_faixa(
    resumo_pesos: Mapping[str, Any], *, cap: float = CAP_POR_ATIVO
) -> dict[str, Any]:
    """A tradução de ADR-003: piso estrutural + banda tática por regime, como **faixa** (CA-107).

    A saída é um intervalo por regime, nunca um ponto: o piso é o de ADR-003 (16-20%, FGVcef) e o
    teto do regime é o peso de variância mínima **truncado na banda** [15%, 35%]. Quando o peso
    cru fica **abaixo** do piso estrutural, o regime não "pede menos que o piso" — o piso é
    estrutural, e o que a banda diz é *onde dentro dela*; isso vai escrito em `leitura` de cada
    linha, com o `n`.
    """
    rotulo_cap = f"cap_{cap:.2f}"
    por_regime = dict(resumo_pesos.get("por_regime", {}).get(rotulo_cap, {}))
    linhas: list[dict[str, Any]] = []
    for regime in sorted(por_regime):
        bloco = por_regime[regime]
        cru = bloco.get("peso_internacional")
        n = int(bloco.get("n_obs", 0))
        na_banda = truncar_na_banda(cru)
        linhas.append(
            {
                "regime": regime,
                "n_obs": n,
                "peso_variancia_minima": cru,
                "peso_sugerido_na_banda": na_banda,
                "piso_estrutural": [PISO_ESTRUTURAL_MIN, PISO_ESTRUTURAL_MAX],
                "banda_tatica": [BANDA_TATICA_MIN, BANDA_TATICA_MAX],
                "faixa_sugerida": (
                    None
                    if na_banda is None
                    else [min(PISO_ESTRUTURAL_MIN, na_banda), max(PISO_ESTRUTURAL_MAX, na_banda)]
                ),
                "truncado": None
                if cru is None
                else not (BANDA_TATICA_MIN <= cru <= BANDA_TATICA_MAX),
                "alerta_n_baixo": alerta_n_baixo(n),
                "conclusao_suprimida": conclusao_suprimida(n),
                "leitura": (
                    f"Indicacao com n = {n}: a variancia minima aponta "
                    f"{'None' if cru is None else format(cru, '.1%')} de "
                    f"{ATIVO_INTERNACIONAL_REPRESENTATIVO}; a entrega e a FAIXA, nao esse ponto."
                ),
            }
        )
    return {
        "decisao": "D6 (ADR-003, Proposta)",
        "forma": "piso estrutural + banda tatica por regime — NUNCA numero pontual (CA-107)",
        "piso_estrutural": {"min": PISO_ESTRUTURAL_MIN, "max": PISO_ESTRUTURAL_MAX},
        "banda_tatica": {"min": BANDA_TATICA_MIN, "max": BANDA_TATICA_MAX},
        "ativo_representativo": ATIVO_INTERNACIONAL_REPRESENTATIVO,
        "cap_usado": cap,
        "linhas": linhas,
        "selo": SELO_NAO_RECOMENDACAO,
        "numero_pontual_rejeitado": (
            "Pedido de 'um numero' e respondido com a faixa e a justificativa de n: por regime o "
            f"n vai de {min((linha['n_obs'] for linha in linhas), default=0)} a "
            f"{max((linha['n_obs'] for linha in linhas), default=0)} trimestres com p = 4 ativos, "
            "e o peso muda materialmente com o cap (o relatorio publica cap 0.40 e sem cap). "
            "Precisao pontual nessa amostra e falsa."
        ),
        "distincao_obrigatoria": (
            "Exposicao CAMBIAL (FGV: 16-35%) e categoria DIFERENTE de global HEDGEADO (XP: 2,5-7% "
            "por perfil). Os numeros desta faixa sao de exposicao cambial (ACWI_BRL em BRL, sem "
            "hedge). Comparar com os da XP e erro de leitura — ADR-003 Contexto."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entradas e gate
# ─────────────────────────────────────────────────────────────────────────────


def _ler_canonical(nome: str, *, schema: Any, raiz: Path | None, como: str) -> pd.DataFrame:
    """Lê um Parquet de `data/canonical/` e **valida** com o schema dele antes de usar."""
    alvo = caminho_canonical(nome, raiz=raiz)
    if not alvo.is_file():
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. {como}."
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return schema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz {schema.Config.name}: {erro}"
        raise SerieInconsistente(msg) from erro


def status_adr_003(*, raiz: Path | None = None) -> str:
    """O status do **ADR-003** (D6) como está em disco, em maiúsculas. Falha fechada.

    Mesma leitura que `regimes_v1.status_adr_001` faz do ADR-001 — e há teste que confere que as
    duas funções dão a mesma resposta quando apontadas para o mesmo arquivo.
    """
    alvo = (raiz or raiz_repo()) / CAMINHO_ADR_003
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        _log.warning("ADR-003 ilegivel em %s: D6 tratada como NAO congelada", alvo)
        return STATUS_ADR_DESCONHECIDO
    achado = _RE_STATUS_ADR.search(texto)
    if achado is None:  # pragma: no cover - guarda de formato
        _log.warning("ADR-003 sem linha de Status reconhecivel: tratado como NAO congelado")
        return STATUS_ADR_DESCONHECIDO
    bruto = achado.group("valor").replace("*", " ")
    primeira = re.split(r"[\s—\-:,.]+", bruto.strip(), maxsplit=1)[0]
    return primeira.strip().upper() or STATUS_ADR_DESCONHECIDO


def d6_esta_congelada(*, raiz: Path | None = None) -> bool:
    """`True` só se o ADR-003 estiver **Aceita** em disco (CA-107, `AGENTS.md §9`)."""
    return status_adr_003(raiz=raiz) == STATUS_ADR_ACEITO


def ler_inclinacao_do_stress(*, raiz: Path | None = None, fonte_versao: str) -> pd.Series:
    """`INCLINACAO_REAL_5A_3A` por trimestre — a função de F-021, não uma reimplementação.

    **D-n**: a série não tem coluna em `MacroQuarterlySchema`, e `regimes_v3.inclinacao_real_5a_3a`
    já a tira de `raw_series` pela régua de F-014. Usar a mesma função é o que garante que o
    `stress_flag` e a feature de curva da V3 falam do **mesmo** número.
    """
    raw = _ler_canonical(
        NOME_RAW_SERIES,
        schema=RawSeriesSchema,
        raiz=raiz,
        como="rode `uv run python -m apps.pipeline.canonical.build_raw_series` (F-013)",
    )
    catalogo = _ler_canonical(
        NOME_CATALOGO,
        schema=SeriesCatalogMaterializedSchema,
        raiz=raiz,
        como="rode `uv run python -m apps.pipeline.canonical.build_raw_series` (F-013)",
    )
    calendario = Calendario.do_parquet(raiz=raiz)
    return inclinacao_real_5a_3a(raw, catalogo, calendario=calendario, fonte_versao=fonte_versao)


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DO_INTERNACIONAL` — o `fonte_versao` destas tabelas."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DO_INTERNACIONAL))


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────

DICIONARIO_DE_COLUNAS: dict[str, str] = {
    "n_obs": "trimestres do regime COM observacao daquele ativo. Nunca nulo (Anti-SPEC 10.2.8).",
    "ret_medio/ret_mediana": "media e mediana de ret_tri (fracao, BRL), lado a lado (CA-092).",
    "excesso_cdi": "media de (1+r)/(1+cdi)-1 — RAZAO, nunca subtracao (Anti-SPEC 10.2.13).",
    "ret_real": "media de (1+r)/(1+ipca_T)-1, IPCA do mesmo trimestre.",
    "hit_ratio_cdi": "fracao de trimestres em que o ativo bateu o CDI.",
    "corr_ibov/corr_imab": "Pearson de ret_tri contra IBOV e IMA-B nos trimestres do regime, "
    "alinhado por quarter. CA-105.",
    "n_pares_ibov/n_pares_imab": "n de PARES completos de cada correlacao — nao e o n_obs da "
    "celula: par exige os dois lados.",
    "is_total_return": "flag de CA-064. ACWI_BRL=True, SP500_BRL=False, USDBRL=False. Price e "
    "total return nunca comparados sem ela (Anti-SPEC 10.2.12).",
    "peso": "peso de variancia minima long-only, soma 1, com o cap da propria linha.",
    "peso_na_banda": "peso truncado na banda tatica [15%, 35%] de ADR-003 — so na linha do "
    "internacional representativo (CA-107).",
    "rho_shrinkage": "intensidade de Ledoit-Wolf MEDIDA (nao escolhida) na amostra da celula.",
}


def _decomposicao_sp500(retornos: pd.DataFrame) -> dict[str, Any]:
    """`(1+SP500_BRL)` × `(1+SP500_USD)(1+USDBRL)` — a conferência que justifica "em BRL".

    Não é cosmético: se a composição não fechar, a série em BRL não é a série em USD convertida, e
    todo o argumento de "internacional em BRL no mesmo arcabouço" cai. É verificação **de dado**,
    com o resíduo medido no relatório.
    """
    necessarios = ["SP500_BRL", "SP500_USD", ATIVO_CAMBIO]
    disponiveis = {str(a) for a in retornos["asset_id"].unique()}
    faltando = [c for c in necessarios if c not in disponiveis]
    if faltando:
        return {"conferido": False, "motivo": f"ausentes: {faltando}"}
    todos = sorted(str(q) for q in retornos["quarter"].unique())
    fatia = matriz_de_retornos(retornos, quarters=todos, ativos=necessarios)
    composto = (1.0 + fatia["SP500_USD"]) * (1.0 + fatia[ATIVO_CAMBIO]) - 1.0
    residuo = (fatia["SP500_BRL"] - composto).abs()
    pior = residuo.idxmax()
    return {
        "conferido": True,
        "n": int(len(fatia)),
        "max_abs_residuo": float(residuo.max()),
        "media_abs_residuo": float(residuo.mean()),
        "pior_quarter": str(pior),
        "identidade": "(1+SP500_BRL) = (1+SP500_USD)*(1+USDBRL)",
        "leitura": (
            "Residuo na ordem de 1e-16 significa que SP500_BRL E a serie em USD convertida pelo "
            "mesmo USDBRL — nao duas series independentes que por acaso se parecem."
        ),
    }


def _conferencia_contra_f022(
    por_regime: pd.DataFrame, *, raiz: Path | None, lente: str = LENTE_V1
) -> dict[str, Any]:
    """CA-104 medido: as colunas comuns batem com `regime_asset_metrics.parquet` célula a célula?

    O teste unitário faz a mesma comparação e **falha** se divergir; aqui o número vai ao
    relatório, para que a próxima pessoa veja o resíduo em vez de confiar no teste.
    """
    alvo = caminho_canonical("regime_asset_metrics.parquet", raiz=raiz)
    if not alvo.is_file():
        return {"conferido": False, "motivo": f"{alvo.name} ausente (rode F-022)"}
    f022 = pd.read_parquet(alvo)
    comuns = ["ret_medio", "ret_mediana", "excesso_cdi", "ret_real", "hit_ratio_cdi", "n_obs"]
    esquerda = por_regime.loc[por_regime["lente"] == lente].set_index(["regime", "asset_id"])
    direita = f022.loc[f022["lente"] == "V1"].set_index(["regime", "asset_id"])
    indice = esquerda.index.intersection(direita.index)
    residuos: dict[str, float] = {}
    for coluna in comuns:
        a = esquerda.loc[indice, coluna].astype("float64")
        b = direita.loc[indice, coluna].astype("float64")
        diferenca = (a - b).abs()
        residuos[coluna] = float(diferenca.max()) if len(diferenca) else 0.0
    return {
        "conferido": True,
        "lente_aqui": lente,
        "lente_la": "V1",
        "celulas_comparadas": int(len(indice)),
        "max_abs_residuo_por_coluna": residuos,
        "max_abs_residuo": max(residuos.values()) if residuos else 0.0,
        "leitura": (
            "CA-104: as colunas de retorno vem da MESMA funcao de F-022 "
            "(metricas_regime.metricas_da_celula) sobre a MESMA fatia — residuo exatamente 0 e o "
            "esperado, nao uma coincidencia numerica."
        ),
    }


def montar_relatorio(
    *,
    por_regime: pd.DataFrame,
    pesos: pd.DataFrame,
    resumo_pesos: Mapping[str, Any],
    stress: pd.DataFrame,
    retornos: pd.DataFrame,
    macro: pd.DataFrame,
    vizinhos: Sequence[Vizinho],
    congelada: bool,
    status_adr: str,
    status_d6: str,
    juncao_com_stress: Any,
    raiz: Path | None,
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    """O relatório de F-026 — o material da revisão numérica de classe C, em JSON."""
    marcados = stress.loc[stress["stress_flag"].astype(bool)]
    nao_avaliaveis = stress.loc[~stress["avaliavel_inclinacao"].astype(bool), "quarter"]
    quarters = sorted(str(q) for q in retornos["quarter"].unique())

    correlacoes_por_regime = [
        {
            "lente": str(linha["lente"]),
            "regime": str(linha["regime"]),
            "asset_id": str(linha["asset_id"]),
            "corr_ibov": None if pd.isna(linha["corr_ibov"]) else float(linha["corr_ibov"]),
            "n_pares_ibov": int(linha["n_pares_ibov"]),
            "corr_imab": None if pd.isna(linha["corr_imab"]) else float(linha["corr_imab"]),
            "n_pares_imab": int(linha["n_pares_imab"]),
            "alerta_n_baixo": bool(linha["alerta_n_baixo"]),
            "conclusao_suprimida": bool(linha["conclusao_suprimida"]),
        }
        for _, linha in por_regime.loc[por_regime["asset_id"] == ATIVO_CAMBIO].iterrows()
    ]

    return {
        "feature": "F-026",
        "classe": "C",
        "pergunta": "item C1 do e-mail: tamanho da alocacao internacional",
        "cobre": {
            "RF-038": "CA-104 (mesmo arcabouco), CA-105 (corr(USDBRL, IBOV) por regime e nos 10 "
            "piores do IBOV, com n)",
            "RF-039": "CA-106 (stress_flag pela disjuncao), CA-107 (faixa, nunca ponto)",
            "RF-040": "CA-108/109 (alerta n < 8, supressao n < 5) em toda celula",
            "RF-031": "CA-090 (gate de publicacao)",
        },
        "artefatos": {
            "internacional_por_regime": {
                "arquivo": NOME_POR_REGIME,
                "linhas": int(len(por_regime)),
                "lentes": sorted(str(x) for x in por_regime["lente"].unique()),
                "ativos": sorted(str(x) for x in por_regime["asset_id"].unique()),
                "publicavel_apos_adr": True,
            },
            "internacional_pesos": {
                "arquivo": NOME_PESOS,
                "linhas": int(len(pesos)),
                "escopos": sorted(str(x) for x in pesos["escopo"].unique()),
                "caps": sorted(float(x) for x in pesos["cap"].unique()),
                "publicavel_na_v1": False,
                "bloqueio": BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA,
            },
        },
        "universo": {
            "representativo_na_carteira": ATIVO_INTERNACIONAL_REPRESENTATIVO,
            "por_que": (
                "ACWI_BRL tem is_total_return=True e SP500_BRL tem False; IBOV/IMAB/CDI sao total "
                "return. Montar covariancia misturando os dois viola Anti-SPEC 10.2.12 / CA-064."
            ),
            "alternativo_reportado": ATIVO_INTERNACIONAL_ALTERNATIVO,
            "carteira_variancia_minima": list(CARTEIRA_VARIANCIA_MINIMA),
            "ifix_fora": "IFIX comeca em 2010Q4 (63 de 83 trimestres, L1): entraria mudando o n "
            "de todas as celulas pre-2011. Fora da carteira, declarado.",
            "bloqueados_sem_fonte": {
                ativo: "BLOQUEADO — FONTE INDISPONIVEL: nao existe em asset_returns_quarterly"
                for ativo in ATIVOS_SEM_FONTE
            },
            "hedge_d7": (
                "SP500_HEDGE nao existe em disco: a versao HEDGEADA de D7 nao e produzida nem "
                "aproximada. Hedgeado e sem hedge sao categorias diferentes e NUNCA somados nem "
                "confundidos (ADR-003 Contexto; XP 2,5-7% hedgeado x FGV 16-35% cambial)."
            ),
            "flags_total_return": _flag_total_return(retornos),
            "decomposicao_sp500": _decomposicao_sp500(retornos),
        },
        "regra_de_stress": {
            "ca": "CA-106",
            "formula": (
                "stress = (delta_inclinacao(T) < -1 * desvio_expanding(delta, ate T-1)) OU "
                f"(usdbrl_var_tri(T) > {LIMIAR_USDBRL_VAR_TRI_PCT}%)"
            ),
            "serie_de_inclinacao": SERIE_INCLINACAO_DO_STRESS,
            "por_que_essa_inclinacao": (
                "principal provisoria de D-i: 95,25% de cobertura (a que fecha CA-025) contra "
                "60,53% da 5a-1a. D-n a mantem fora de MacroQuarterlySchema, entao vem de "
                "raw_series pela funcao que F-021 publica (mesmo numero da feature de curva da V3)."
            ),
            "amostra_do_desvio": (
                f"expanding ate T-1, minimo de {MIN_OBS_DESVIO_EXPANDING} observacoes anteriores. "
                "Nenhum valor >= T entra no desvio de T (metodologia 5.1)."
            ),
            "cai_sobre": (
                "a VARIACAO: delta(T) = incl(T) - incl(T-1). 'Cai mais de 1 desvio' e afirmacao "
                "sobre a queda; nivel baixo nao e evento, achatamento abrupto e."
            ),
            "limiares": {
                "queda_em_desvios": LIMIAR_QUEDA_INCLINACAO_DP,
                "usdbrl_var_tri_pct": LIMIAR_USDBRL_VAR_TRI_PCT,
            },
            "ramo_embi_fora": RAMO_EMBI_FORA,
            "embi_delta_tri_nao_nulos": int(macro[COLUNA_EMBI_DELTA].notna().sum()),
            "n_trimestres": int(len(stress)),
            "n_stress": int(len(marcados)),
            "n_so_pelo_ramo_inclinacao": int(
                (stress["ramo_inclinacao"] & ~stress["ramo_usdbrl"]).sum()
            ),
            "n_so_pelo_ramo_usdbrl": int(
                (stress["ramo_usdbrl"] & ~stress["ramo_inclinacao"]).sum()
            ),
            "n_pelos_dois_ramos": int((stress["ramo_inclinacao"] & stress["ramo_usdbrl"]).sum()),
            "trimestres_de_stress": [
                {
                    "quarter": str(linha["quarter"]),
                    "ramo_inclinacao": bool(linha["ramo_inclinacao"]),
                    "ramo_usdbrl": bool(linha["ramo_usdbrl"]),
                    "delta_inclinacao": (
                        None
                        if pd.isna(linha["delta_inclinacao"])
                        else float(linha["delta_inclinacao"])
                    ),
                    "limiar_queda": (
                        None if pd.isna(linha["limiar_queda"]) else float(linha["limiar_queda"])
                    ),
                    "usdbrl_var_tri": (
                        None if pd.isna(linha["usdbrl_var_tri"]) else float(linha["usdbrl_var_tri"])
                    ),
                }
                for _, linha in marcados.iterrows()
            ],
            "nao_avaliaveis_pelo_ramo_inclinacao": sorted(str(q) for q in nao_avaliaveis),
            "nota_nao_avaliavel": (
                "Trimestre sem delta ou sem 8 observacoes anteriores NAO e 'sem stress': o ramo "
                "da inclinacao nao e avaliavel ali, e esta nomeado. O ramo do cambio vale sempre."
            ),
            "destrava_regimes_schema": {
                "decisao": "D-r",
                "bloqueio_de_stress_flag_resolvido": not any(
                    "stress_flag" in b for b in juncao_com_stress.bloqueios
                ),
                "bloqueios_restantes": list(juncao_com_stress.bloqueios),
                "leitura": (
                    "Com a serie desta feature injetada em metricas_regime.montar_regimes, o "
                    "bloqueio de stress_flag desaparece. O de regime_v1 nulo (16 trimestres "
                    "INDETERMINADO, D-m) continua e NAO e de F-026."
                ),
            },
        },
        "hedge_cambial": {
            "ca": "CA-105",
            "stress_vs_nao_stress": hedge_no_stress(retornos, stress),
            "por_regime": correlacoes_por_regime,
            "dez_piores_trimestres_do_ibov": [
                {
                    "quarter": q,
                    "ret_ibov": float(
                        serie_por_quarter(retornos, ASSET_ID_IBOV, quarters=[q]).iloc[0]
                    ),
                    "ret_usdbrl": float(
                        serie_por_quarter(retornos, ATIVO_CAMBIO, quarters=[q]).iloc[0]
                    ),
                    "stress_flag": bool(
                        stress.loc[stress["quarter"] == q, "stress_flag"].astype(bool).any()
                    ),
                }
                for q in piores_trimestres_do_ibov(retornos)
            ],
            "evidencia_de_referencia": (
                "FGVcef (21.000 janelas 2005-2026): so o dolar funcionou como diversificacao "
                "genuina entre ativos acessiveis ao brasileiro; nenhum par domestico e negativo. "
                "A correlacao de -0,76 citada em estudo academico esta [V-parcial] na pesquisa — "
                "o numero desta tabela e o MEDIDO aqui, nos 82 trimestres do canonico."
            ),
        },
        "risk_off": risk_off_em_t_mais_1(retornos, stress),
        "variancia_minima": {
            "metodo": (
                "covariancia com shrinkage de Ledoit-Wolf (IMPORTADA de regimes_v3.ledoit_wolf, "
                "F-021 — rho medido, nao escolhido) e minimizacao exata de w'Sigma w sujeito a "
                "1'w = 1 e 0 <= w <= cap, por enumeracao de conjunto ativo (3^p particoes)."
            ),
            "cap_principal": CAP_POR_ATIVO,
            "por_que_cap": (
                "metodologia 4.3 item 1 manda cap de 40% por ativo. MEDIDO: sem cap a carteira "
                "NAO degenera em 100% CDI (o shrinkage, rho de 0,25 a 0,60, segura o CDI em "
                "37-50%); o efeito aparece no expanding, onde o peso internacional medio de "
                "2006-2026 cai de 19,6% (cap 0,40) para 10,4% (sem cap). As duas versoes vao no "
                "relatorio para a sensibilidade ficar visivel, nao afirmada."
            ),
            "resumo": dict(resumo_pesos),
            "sensibilidade": (
                "Compare cap_0.40 com cap_1.00: se o peso internacional muda materialmente entre "
                "os dois, o numero NAO e robusto e a entrega e a faixa (CA-107)."
            ),
            "bloqueio_anti_spec": BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA,
        },
        "faixa_de_d6": tabela_de_faixa(resumo_pesos),
        "lentes": [
            {
                "rotulo": lente.rotulo,
                "materializacao": lente.materializacao.value,
                "horizonte": lente.horizonte.value,
                "por_que": lente.por_que,
            }
            for lente in LENTES
        ],
        "vizinhos_v3": [
            {
                "rank": v.rank,
                "quarter_neighbor": v.quarter,
                "distancia": v.distancia,
                "quarter_t_mais_1": quarter_do_horizonte(v.quarter, Horizonte.T_MAIS_1),
            }
            for v in vizinhos
        ],
        "dicionario_de_colunas": dict(DICIONARIO_DE_COLUNAS),
        "consistencia": {
            "ca_104_contra_f022": _conferencia_contra_f022(por_regime, raiz=raiz),
            "n_trimestres_do_canonico": len(quarters),
            "primeiro_quarter": quarters[0] if quarters else None,
            "ultimo_quarter": quarters[-1] if quarters else None,
        },
        "gate_de_publicacao": {
            "adr_001": {
                "status": status_adr,
                "especificacao_congelada": congelada,
                "veredito": veredito_publicacao(congelada),
            },
            "adr_003_d6": {
                "status": status_d6,
                "d6_congelada": status_d6 == STATUS_ADR_ACEITO,
                "consequencia": (
                    "Em Proposta, a FORMULACAO da recomendacao nao esta congelada: a faixa sai "
                    "com o selo de nao-recomendacao e nenhuma linha vai ao Comite sem classe D."
                ),
            },
            "anti_spec": {
                "variancia_minima_fora_da_v1": True,
                "secoes": ["10.3.16", "10.5"],
                "todo_f026": "Excluido: variancia minima por regime e fronteira eficiente (F-035)",
                "motivo": BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA,
            },
            "publicavel": False,
            "selo": SELO_NAO_RECOMENDACAO,
            "linguagem": (
                "Saida DESCRITIVA (Anti-SPEC 10.2.10): 'nos trimestres de stress o USDBRL rendeu "
                "X, n = Y'. Nunca 'vai render'. Com n < 5, 'indicacao preliminar, n = Y' (CA-109)."
            ),
        },
        **dict(hashes),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResultadoInternacional:
    """O que `construir` devolve — para o teste, para F-023/F-027 e para o relatório."""

    por_regime: pd.DataFrame
    pesos: pd.DataFrame
    stress: pd.DataFrame
    relatorio: dict[str, Any]
    caminhos: dict[str, Path]
    caminho_relatorio: Path | None


def construir(*, raiz: Path | None = None, gravar: bool = True) -> ResultadoInternacional:
    """Reconstrói F-026 de ponta a ponta. Sem rede, sem relógio, sem estado.

    `gravar=False` existe para o teste rodar o build real sobre o acervo em disco sem tocar o
    disco de volta — o mesmo contrato de F-022.
    """
    congelada = especificacao_esta_congelada(raiz=raiz)
    status = status_adr_001(raiz=raiz)
    status_d6 = status_adr_003(raiz=raiz)
    if not congelada:
        _log.warning(
            "%s: ADR-001 esta em '%s' — nenhum numero de regime x retorno desta feature e "
            "publicavel (CA-090, AGENTS.md 9/14)",
            veredito_publicacao(congelada),
            status,
        )
    if status_d6 != STATUS_ADR_ACEITO:
        _log.warning(
            "ADR-003 (D6) esta em '%s': a faixa sai com o selo '%s'",
            status_d6,
            SELO_NAO_RECOMENDACAO,
        )
    _log.warning("%s NAO e publicavel na v1 — %s", NOME_PESOS, BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA)

    regimes = {
        m.value: ler_regimes_v1(materializacao=m, raiz=raiz)
        for m in (Materializacao.REVISED, Materializacao.ASOF)
    }
    for quadro in regimes.values():
        conferir_gate(quadro, congelada=congelada)

    retornos = ler_retornos(raiz=raiz)
    neighbors = ler_neighbors_v3(raiz=raiz)
    vizinhos = vizinhos_da_lente_canonica(neighbors)
    macro = ler_macro(materializacao=Materializacao.REVISED, raiz=raiz).set_index("quarter")

    fonte_versao = versao_build()
    inclinacao = ler_inclinacao_do_stress(raiz=raiz, fonte_versao=fonte_versao)
    stress = stress_por_trimestre(
        inclinacao=inclinacao,
        usdbrl_var_tri=macro[COLUNA_USDBRL_VAR].astype("float64"),
    )
    _log.info(
        "stress_flag (CA-106): %d de %d trimestres — %d so pela inclinacao, %d so pelo cambio",
        int(stress["stress_flag"].sum()),
        len(stress),
        int((stress["ramo_inclinacao"] & ~stress["ramo_usdbrl"]).sum()),
        int((stress["ramo_usdbrl"] & ~stress["ramo_inclinacao"]).sum()),
    )

    por_regime = montar_por_regime(
        regimes=regimes,
        retornos=retornos,
        vizinhos=vizinhos,
        congelada=congelada,
        fonte_versao=fonte_versao,
    )
    pesos, resumo_pesos = montar_pesos(
        regimes_v1=regimes[Materializacao.REVISED.value],
        retornos=retornos,
        fonte_versao=fonte_versao,
    )

    juncao = montar_regimes(
        regimes_v1=regimes[Materializacao.REVISED.value],
        macro=macro.reset_index(),
        stress_flag=serie_de_stress_flag(stress),
    )

    caminhos: dict[str, Path] = {}
    corpos: dict[str, bytes] = {}
    for nome, quadro in ((NOME_POR_REGIME, por_regime), (NOME_PESOS, pesos)):
        if gravar:
            alvo = caminho_canonical(nome, raiz=raiz)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            quadro.to_parquet(alvo, index=False)
            caminhos[nome] = alvo
            corpos[nome] = alvo.read_bytes()
        else:
            corpos[nome] = quadro.to_parquet(index=False)

    relatorio = montar_relatorio(
        por_regime=por_regime,
        pesos=pesos,
        resumo_pesos=resumo_pesos,
        stress=stress,
        retornos=retornos,
        macro=macro,
        vizinhos=vizinhos,
        congelada=congelada,
        status_adr=status,
        status_d6=status_d6,
        juncao_com_stress=juncao,
        raiz=raiz,
        hashes={
            "versao_build": fonte_versao,
            "fonte_versao": fonte_versao,
            "hashes": {
                nome: {"arquivo": nome, "sha256": sha256_de(corpo), "bytes": len(corpo)}
                for nome, corpo in corpos.items()
            },
        },
    )

    caminho_relatorio: Path | None = None
    if gravar:
        caminho_relatorio = caminho_canonical(NOME_RELATORIO, raiz=raiz)
        caminho_relatorio.write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _log.info(
            "gravados %s (%d linhas), %s (%d linhas) + %s",
            NOME_POR_REGIME,
            len(por_regime),
            NOME_PESOS,
            len(pesos),
            NOME_RELATORIO,
        )

    return ResultadoInternacional(
        por_regime=por_regime,
        pesos=pesos,
        stress=stress,
        relatorio=relatorio,
        caminhos=caminhos,
        caminho_relatorio=caminho_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.internacional",
        description=(
            "Materializa internacional_por_regime.parquet, internacional_pesos.parquet e "
            "relatorio_internacional.json (F-026, item C1 do e-mail). Nunca toca a rede. "
            "internacional_pesos NAO e publicavel na v1 (Anti-SPEC 10.3.16/10.5) e, enquanto "
            "ADR-001/ADR-003 estiverem em Proposta, nenhum numero daqui vai ao Comite (CA-090)."
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
        _log.error("%s", erro)
        return 1
    for nome, bloco in resultado.relatorio["hashes"].items():
        _log.info("%s: sha256=%s...", nome, bloco["sha256"][:12])
    faixa = resultado.relatorio["faixa_de_d6"]
    for linha in faixa["linhas"]:
        _log.info(
            "%s: variancia minima %s -> banda %s (n = %d)",
            linha["regime"],
            (
                "None"
                if linha["peso_variancia_minima"] is None
                else format(linha["peso_variancia_minima"], ".1%")
            ),
            (
                "None"
                if linha["peso_sugerido_na_banda"] is None
                else format(linha["peso_sugerido_na_banda"], ".1%")
            ),
            linha["n_obs"],
        )
    _log.info("gate: %s", resultado.relatorio["gate_de_publicacao"]["selo"])
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script
    sys.exit(main())
