"""F-017 — `asset_returns_quarterly`: retorno trimestral, excesso sobre CDI e retorno real.

**Classe C.** Materializa `data/canonical/asset_returns_quarterly.parquet`: uma linha por
`(quarter, asset_id)` com o retorno do trimestre, o excesso sobre o CDI e o retorno real — e,
quando o retorno **não** é calculável, `NULL` com o motivo registrado no relatório, nunca `0`
nem valor herdado.

## As seis convenções que este módulo materializa

1. **`ret_tri = P_fim / P_ini − 1`** (ADR-006 §(b).3), com `P_fim` = nível do ativo no trimestre
   `T` e `P_ini` = nível no trimestre `T−1`, **os dois lidos de `alinhado_trimestral`** (F-014).
   Nenhum nível é relido de `raw_series` aqui: a régua temporal é a de F-014, uma só para todo o
   canônico.
2. **O 1º trimestre de cada série não tem retorno.** Sem linha em `T−1` não há `P_ini`, e
   `ret_tri` é `NULL` — jamais `0`, jamais `P_fim/P_fim`, jamais backfill (Anti-SPEC §10.1.1,
   §10.1.4). Como `alinhado_trimestral` começa em `2006Q1`, **nenhum** ativo tem retorno em
   `2006Q1`; o IFIX, cuja série nasce em 30/12/2010, tem a linha de `2010Q4` (parcial, aceita
   pelo contrato) e o **primeiro retorno em `2011Q1`**.
3. **O CDI trimestral vem da acumulação diária, não de um nível.** `prod(1 + v/100) − 1` sobre as
   observações da série **SGS 12** (`%/dia`, percentual e **não** fator) do trimestre
   (ADR-006 §(b).6, `docs/research/fontes-de-dados.md §B7`). Valor-canário: os 249 dias úteis de
   2006 acumulam **15,027140 %**, e o produto dos 4 trimestres de 2006 reproduz esse fator.
   Por isso o CDI **tem** retorno em `2006Q1`: a acumulação é intra-trimestre e não precisa de
   `T−1` — é a única assimetria do universo, e é declarada.
4. **Excesso e retorno real são sempre razão:** `(1+r)/(1+b) − 1`, nunca `r − b`
   (ADR-006 §(b).5, Anti-SPEC §10.2.13, CA-069). As duas colunas chamam **a mesma** função
   (`excesso_por_razao`), com bases diferentes — não existe caminho no código em que uma delas
   possa virar subtração sem a outra virar também, e o teste negativo cobre as duas.
5. **`ret_real` usa o IPCA do próprio trimestre, aplicado uma única vez** (CA-071): o IPCA
   trimestral é `prod(1 + v/100) − 1` sobre os **3 meses de referência** de `T` da série
   **SGS 433** (`IPCA — variação mensal`). Os meses são os do trimestre (`2006Q1` = jan+fev+mar),
   pela data de **referência**, não de divulgação — a variante por data de divulgação é F-018.
   Trimestre sem os 3 meses ⇒ `ret_real = NULL`, nunca deflação parcial.
6. **`is_total_return` é propagado do catálogo declarado, não inferido.** IMA/IRF-M, IBOV e IFIX
   são `True`; os setoriais da B3 (IDIV, SMLL, INDX, ICON, IMAT, IEEX, IMOB, IFNC, UTIL) são
   `None` — o gap **G-01**, que segue "a confirmar" índice por índice. `SP500_USD` e `SP500_BRL`
   são `False` (índice de preço) e `ACWI_BRL` é `True` (net total return): é exatamente o par que
   CA-064 proíbe comparar sem a flag. `USDBRL` é `False` por **D-l** — câmbio não tem carrego, e
   `None` ali diria "a confirmar" sobre uma pergunta que não se aplica.

## O que mais fica em cada linha

`vol_intra_tri` e `dd_intra_tri` saem do **caminho diário** do trimestre, definido como as
observações da série em `(date_obs(T−1), date_obs(T)]` — as datas que `alinhado_trimestral`
registra, de modo que o **produto dos fatores diários é idêntico a `ret_tri`** (encadeamento
geométrico, CA-070; nunca soma de retornos). `n_dias_uteis` é o tamanho desse caminho — para o
CDI, o número de taxas diárias acumuladas. `ffill_dias_uteis` é o forward-fill da **ponta de
fechamento** (`P_fim`); o do `P_ini` está na linha de `T−1`, na própria tabela.

## O que este módulo **não** faz

Nenhuma métrica por regime (F-022/`RegimeAssetMetricsSchema`), nenhum hedge cambial
(D7 → F-026), nenhuma anualização (o dado é trimestral e fica trimestral), nenhum Sharpe
(Anti-SPEC §10.2.11) e nenhuma variante `asof` (F-018). Também não inventa ativo: o universo é a
constante `UNIVERSO`, e série pedida que não esteja em `alinhado_trimestral` para o build com
`BLOQUEADO — FONTE INDISPONÍVEL` em vez de entregar painel mais magro em silêncio.

**Sem rede, sempre.** As entradas são `data/canonical/alinhado_trimestral.parquet`,
`data/canonical/raw_series.parquet`, `data/canonical/series_catalog.parquet` e
`data/processed/calendario/dias_uteis_anbima.parquet`.

**Idempotente por construção.** Nada aqui lê o relógio; `fonte_versao` é o `sha256` do
**conjunto** `MODULOS_DOS_RETORNOS` (RF-047/CA-121). Duas rodadas sobre a mesma entrada produzem
Parquet e relatório byte-idênticos (RF-048).

Referências: SPEC RF-022 (CA-062..064), RF-023, RF-024 (CA-069..071), RF-006 (CA-014..016),
RF-026/RF-047 · ADR-002 (D5: excesso sobre CDI como métrica primária) · ADR-005 (janelas
próprias) · ADR-006 §(b) · `docs/contracts/CONTRACTS.md §4` ·
`docs/research/metodologia-regimes-macro.md §3`, §6.3, §6.5 ·
`docs/research/fontes-de-dados.md §B7` · `docs/wiki/context/F-017.md`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from apps.pipeline.canonical.alinhamento import (
    NOME_ALINHADO,
    alinhar_series,
    grade_de_trimestres,
    inicio_observado_por_serie,
    selecionar_vintage,
    validar_indice_temporal,
)
from apps.pipeline.canonical.build_raw_series import (
    NOME_CATALOGO,
    NOME_RAW_SERIES,
    ErroCanonico,
    caminhos_dos_componentes,
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
    ASSET_IDS_VALIDOS,
    N_MINIMO_ATIVOS,
    AlinhadoTrimestralSchema,
    AssetReturnsQuarterlySchema,
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

NOME_RETORNOS = "asset_returns_quarterly.parquet"
NOME_RELATORIO = "relatorio_retornos.json"

#: Os módulos que determinam o conteúdo de `asset_returns_quarterly`, **nesta ordem** — base de
#: `versao_build`. Mesmo critério de F-014: este módulo + o contrato da tabela + a camada que
#: produz os níveis (o alinhamento) + o builder de onde vem o catálogo materializado + o
#: calendário (que decide todo `quarter_end`) + o catálogo como **dado** (que decide
#: `is_total_return`, `source` e `unit`). Mudar qualquer um muda o Parquet, então tem de mudar a
#: versão.
MODULOS_DOS_RETORNOS: tuple[str, ...] = (
    "apps.pipeline.canonical.retornos",
    "packages.shared.schemas.asset_returns_quarterly",
    "apps.pipeline.canonical.alinhamento",
    "apps.pipeline.canonical.build_raw_series",
    "apps.pipeline.extract.calendario_anbima",
    "packages.shared.schemas.series_catalog_data",
)

SERIE_CDI = "BCB_SGS_12"
"""CDI — taxa diária, **percentual ao dia** (`0.065500` = 0,0655 %/dia). ADR-006 §(b).6."""

UNIDADE_CDI = "%/dia"
"""A unidade que `SERIE_CDI` tem de declarar. É a trava de escala: a série 12 é percentual e não
fator, e esquecer o `/100` é o erro clássico (`fontes-de-dados.md §B7`, CA-016). Unidade diferente
para o build em vez de produzir um CDI 100x errado que ninguém nota."""

SERIE_IPCA = "BCB_SGS_433"
"""IPCA — variação **mensal** em %. Deflator de `ret_real` (CA-071)."""

UNIDADE_IPCA = "%"

SERIE_CDI_CONFERENCIA = "BCB_SGS_4389"
"""CDI anualizado base 252 (`% a.a.`) — **segunda fonte** do mesmo CDI, usada só na conferência
numérica (`fator_dia = (1 + taxa/100) ** (1/252)`, §B7). Não entra no cálculo de produção: a
pesquisa mede que o arredondamento é maior que na série 12."""

MESES_POR_TRIMESTRE = 3
"""O IPCA trimestral exige os **3** meses de referência. Menos que isso ⇒ `NULL`, nunca deflação
parcial (CA-071 / Anti-SPEC §10.1.1)."""

MINIMO_RETORNOS_DIARIOS_PARA_VOL = 2
"""Desvio amostral (`ddof=1`) exige 2 observações. Com 1, `vol_intra_tri` é `NULL`."""


class Metodo(StrEnum):
    """Como o retorno trimestral do ativo é obtido. São **dois**, e a diferença é declarada."""

    RAZAO_DE_NIVEIS = "razao_de_niveis"
    """`P_fim/P_ini − 1` sobre número-índice (ou nível, no caso do câmbio). Exige `T−1`."""

    ACUMULACAO_DE_TAXA_DIARIA = "acumulacao_de_taxa_diaria"
    """`prod(1 + v/100) − 1` sobre a taxa diária do trimestre. **Não** exige `T−1`."""


@dataclass(frozen=True, slots=True)
class Ativo:
    """Uma linha do universo: o `asset_id` do contrato, a série que o alimenta e o método."""

    asset_id: str
    series_id: str
    bloco: str
    metodo: Metodo = Metodo.RAZAO_DE_NIVEIS


#: **O universo desta materialização** — 24 `asset_id` do enum de 32 de
#: `docs/contracts/CONTRACTS.md §4`, que são os que têm série em `raw_series` hoje. O mínimo do
#: contrato é 18 (CA-062). O que ficou fora, e por quê, está em `ATIVOS_FORA_DO_UNIVERSO`.
UNIVERSO: tuple[Ativo, ...] = (
    # Renda fixa — e-mail B1/B2/B3
    Ativo("CDI", SERIE_CDI, "renda_fixa", Metodo.ACUMULACAO_DE_TAXA_DIARIA),
    Ativo("IMAB", "ANBIMA_IMAB", "renda_fixa"),
    Ativo("IMAB5", "ANBIMA_IMAB5", "renda_fixa"),
    Ativo("IMAB5P", "ANBIMA_IMAB5MAIS", "renda_fixa"),
    Ativo("IRFM", "ANBIMA_IRFM", "renda_fixa"),
    Ativo("IRFM1", "ANBIMA_IRFM1", "renda_fixa"),
    Ativo("IRFM1P", "ANBIMA_IRFM1MAIS", "renda_fixa"),
    Ativo("IMAGERAL", "ANBIMA_IMAGERAL", "renda_fixa"),
    Ativo("IMAS", "ANBIMA_IMAS", "renda_fixa"),
    # Ações B3 — e-mail B4
    Ativo("IBOV", "B3_IBOV", "acoes_b3"),
    Ativo("IDIV", "B3_IDIV", "acoes_b3"),
    Ativo("SMLL", "B3_SMLL", "acoes_b3"),
    Ativo("INDX", "B3_INDX", "acoes_b3"),
    Ativo("ICON", "B3_ICON", "acoes_b3"),
    Ativo("IMAT", "B3_IMAT", "acoes_b3"),
    Ativo("IEEX", "B3_IEEX", "acoes_b3"),
    Ativo("IMOB", "B3_IMOB", "acoes_b3"),
    Ativo("IFNC", "B3_IFNC", "acoes_b3"),
    Ativo("UTIL", "B3_UTIL", "acoes_b3"),
    # FII — e-mail B5
    Ativo("IFIX", "B3_IFIX", "fii"),
    # Internacional — e-mail C1
    Ativo("SP500_BRL", "SP500_BRL", "internacional"),
    Ativo("SP500_USD", "YAHOO_GSPC", "internacional"),
    Ativo("ACWI_BRL", "ACWI_BRL", "internacional"),
    # Câmbio — entrou por **D-l**, porque RF-038 (dimensionamento da alocação internacional) e
    # `metodologia §4.2` (câmbio como hedge) precisam do retorno trimestral do dólar. A PTAX
    # (`BCB_SGS_1`) já tem os 83 trimestres em `alinhado_trimestral`; a razão de níveis é a mesma
    # dos demais. `is_total_return` vem do catálogo e é **False** (D-l): câmbio não tem carrego —
    # o cupom cambial ficaria de fora de qualquer forma, e dizer `None` ("a confirmar") seria
    # confundir "não se aplica" com "não medimos".
    Ativo("USDBRL", "BCB_SGS_1", "internacional"),
)

#: Os 8 `asset_id` do enum que **não** entram, com o motivo. Fica no relatório: "não está na
#: tabela" tem de ter causa nomeada, igual a célula nula (Anti-SPEC §10.1.1).
ATIVOS_FORA_DO_UNIVERSO: dict[str, str] = {
    "FII_TIJOLO": "Segmentação de FII via Teva (ADR-005 §4, `should`) — F-012 ainda não rodou.",
    "FII_PAPEL": "Idem FII_TIJOLO.",
    "FII_LOGISTICA": "Idem FII_TIJOLO.",
    "FII_SHOPPINGS": "Idem FII_TIJOLO.",
    "FII_LAJES": "Idem FII_TIJOLO.",
    "SP500_HEDGE": (
        "Exige Fed Funds (custo de hedge, `metodologia §4.1`) e o FRED está bloqueado nesta "
        "máquina (`skills-manifest.md §3`). D7 → fase 2 parcial em F-026."
    ),
    "UST10_BRL": (
        "`YAHOO_TNX` é **taxa** (`% a.a.`), não número-índice de retorno total: não há nível de "
        "preço para razão. Construir o total return do Treasury é fase 2."
    ),
    "GOLD_BRL": "Série de ouro não extraída no pacote mínimo (RF-017, prioridade `should`).",
}

#: Séries `source=DERIVADO` que **esta** feature alinha, porque F-014 as deixa fora de propósito
#: (`FONTES_FORA_DO_ALINHAMENTO`): a derivação tem convenção própria e quem a alinha é a feature
#: dona dela. São as duas em BRL de F-007 (índice internacional × PTAX).
DERIVADAS_ALINHADAS_AQUI: tuple[str, ...] = ("ACWI_BRL", "SP500_BRL")


class MotivoNulo(StrEnum):
    """Por que uma célula de métrica é nula. Toda ausência tem causa **nomeada** no relatório.

    A taxonomia vive aqui e não numa coluna porque `AssetReturnsQuarterlySchema` é `strict` e
    acrescentar coluna ao contrato de outra feature seria alteração de schema, não acréscimo
    (`AGENTS.md §13`). O relatório carrega a contagem por `(coluna, motivo)` e por ativo.
    """

    PRIMEIRO_TRIMESTRE_SEM_T_MENOS_1 = "primeiro_trimestre_da_serie_sem_t_menos_1"
    NIVEL_AUSENTE_EM_T = "nivel_ausente_em_t"
    NIVEL_AUSENTE_EM_T_MENOS_1 = "nivel_ausente_em_t_menos_1"
    SEM_RETORNO_CALCULAVEL = "sem_retorno_calculavel_no_trimestre"
    CDI_INDISPONIVEL = "cdi_do_trimestre_indisponivel"
    IPCA_INDISPONIVEL = "ipca_do_trimestre_indisponivel"
    ATIVO_SEM_NIVEL_DE_PRECO = "ativo_sem_nivel_de_preco_e_uma_taxa_acumulada"
    SERIE_SEM_DIARIO_NO_TRIMESTRE = "sem_caminho_diario_no_trimestre"
    DIARIO_CURTO_PARA_DESVIO = "menos_de_dois_retornos_diarios_no_trimestre"
    IS_TOTAL_RETURN_A_CONFIRMAR = "is_total_return_a_confirmar_g01"


class UniversoIncompleto(ErroCanonico):
    """Série de um `asset_id` do universo ausente dos níveis alinhados (CA-062/CA-076)."""


class UnidadeInesperada(ErroCanonico):
    """Série de CDI ou IPCA com unidade diferente da declarada — trava de escala (CA-016)."""


class AtivoForaDoContrato(ErroCanonico):
    """`asset_id` que não existe no enum de `AssetReturnsQuarterlySchema`."""


# ─────────────────────────────────────────────────────────────────────────────
# Aritmética — as três fórmulas, cada uma em um só lugar
# ─────────────────────────────────────────────────────────────────────────────


def razao_de_niveis(preco_fim: float | None, preco_ini: float | None) -> float | None:
    """`P_fim/P_ini − 1` (ADR-006 §(b).3). Ponta ausente ⇒ `None`, nunca `0`.

    `P_ini <= 0` levanta: número-índice não é zero nem negativo, e dividir por ele devolveria
    `inf` ou um retorno de sinal invertido — o tipo de número que passa por schema e contamina a
    média do regime.
    """
    if preco_fim is None or preco_ini is None:
        return None
    if not math.isfinite(preco_fim) or not math.isfinite(preco_ini):
        return None
    if preco_ini <= 0:
        msg = f"nível inicial não positivo ({preco_ini!r}): razão de retorno indefinida"
        raise SerieInconsistente(msg)
    return preco_fim / preco_ini - 1.0


def acumular_taxa_diaria(valores: Sequence[float]) -> float:
    """`prod(1 + v/100) − 1` sobre taxas em **percentual ao dia** (ADR-006 §(b).6, §B7).

    O `/100` é o ponto todo: a série SGS 12 é percentual, não fator. Sem ele, 2006 daria um fator
    acima de `1e5` em vez de 1,15 (CA-016). A acumulação é **geométrica** — produto de fatores,
    nunca soma de taxas (CA-070).
    """
    fator = 1.0
    for valor in valores:
        fator *= 1.0 + float(valor) / 100.0
    return fator - 1.0


def excesso_por_razao(retorno: float | None, base: float | None) -> float | None:
    """`(1 + r)/(1 + b) − 1` — **a** função de excesso e de deflação (ADR-006 §(b).5).

    Excesso sobre CDI e retorno real são a **mesma** operação com bases diferentes, e por isso
    são a mesma função: não existe caminho em que uma seja razão e a outra subtração. Com `r=0,10`
    e `b=0,0325` o resultado é `0,065375…`, **não** `0,0675` (CA-069, Anti-SPEC §10.2.13).

    `1 + base <= 0` levanta: base de −100 % ou menos não é deflator, é divisão por zero disfarçada.
    """
    if retorno is None or base is None:
        return None
    fator_base = 1.0 + base
    if fator_base <= 0:
        msg = f"base de excesso/deflação inviável ({base!r}): 1+base <= 0"
        raise SerieInconsistente(msg)
    return (1.0 + retorno) / fator_base - 1.0


def metricas_intra_trimestre(
    caminho: Sequence[float], *, preco_inicial: float
) -> tuple[float | None, float | None]:
    """`(vol_intra_tri, dd_intra_tri)` do caminho diário do trimestre.

    `caminho` são os níveis **dentro** do trimestre, em ordem; `preco_inicial` é o nível de
    fechamento de `T−1`, que é ao mesmo tempo a base do 1º retorno diário e o **primeiro pico**
    do drawdown (um trimestre que só cai tem `dd < 0` desde o 1º dia, como deve).

    - `vol_intra_tri` = desvio amostral dos retornos diários × `sqrt(n)` — a convenção de
      `metodologia-regimes-macro.md §6.3`. Com menos de 2 retornos, `None` (não `0`).
    - `dd_intra_tri` = `min(P_t / max(P_0..P_t) − 1)`, sempre `<= 0`.
    """
    if not caminho or preco_inicial <= 0:
        return None, None
    retornos: list[float] = []
    anterior = float(preco_inicial)
    pico = float(preco_inicial)
    queda = 0.0
    for nivel in caminho:
        atual = float(nivel)
        retornos.append(atual / anterior - 1.0)
        anterior = atual
        pico = max(pico, atual)
        queda = min(queda, atual / pico - 1.0)
    if len(retornos) < MINIMO_RETORNOS_DIARIOS_PARA_VOL:
        return None, min(queda, 0.0)
    media = sum(retornos) / len(retornos)
    variancia = sum((r - media) ** 2 for r in retornos) / (len(retornos) - 1)
    return math.sqrt(variancia) * math.sqrt(len(retornos)), min(queda, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Entradas: níveis alinhados, CDI e IPCA
# ─────────────────────────────────────────────────────────────────────────────


def _ler_canonical(nome: str, *, schema: Any, raiz: Path | None) -> pd.DataFrame:
    """Lê um Parquet de `data/canonical/` e **valida** com o seu schema antes de usar."""
    alvo = caminho_canonical(nome, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode "
            f"`uv run python -m apps.pipeline.canonical.build_raw_series --offline` e "
            f"`uv run python -m apps.pipeline.canonical.alinhamento --offline` antes."
        )
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return schema.validate(quadro, lazy=True)
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz {schema.Config.name}: {erro}"
        raise SerieInconsistente(msg) from erro


def niveis_alinhados(
    alinhado: pd.DataFrame,
    raw: pd.DataFrame,
    *,
    calendario: Calendario,
    inicio_por_serie: Mapping[str, Any],
    trimestres: Sequence[Any],
    fonte_versao: str,
    derivadas: Sequence[str] = DERIVADAS_ALINHADAS_AQUI,
) -> pd.DataFrame:
    """Os níveis trimestrais de **todas** as séries do universo, numa só tabela alinhada.

    `alinhado_trimestral` cobre as 49 séries de fonte primária; as `DERIVADO` ficaram fora do
    build de F-014 de propósito (`FONTES_FORA_DO_ALINHAMENTO`), e é aqui que `SP500_BRL` e
    `ACWI_BRL` passam por `alinhar_series` — a função pública existe exatamente para isso
    (`F-014.md §4.3`). O resultado volta a passar por `AlinhadoTrimestralSchema`: a concatenação
    tem de continuar satisfazendo o contrato da régua, inclusive `quarter_end` único por
    trimestre.
    """
    if not derivadas:
        return AlinhadoTrimestralSchema.validate(alinhado, lazy=True)
    faltam = [s for s in derivadas if s not in set(raw["series_id"])]
    if faltam:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: séries derivadas ausentes de raw_series: {faltam}. "
            f"Rode F-007 (conversão a BRL) e o build de F-013 antes."
        )
        raise FonteIndisponivel(msg)
    fatia = raw.loc[raw["series_id"].isin(derivadas)].copy()
    alinhadas = alinhar_series(
        fatia,
        calendario=calendario,
        inicio_por_serie=inicio_por_serie,
        trimestres=trimestres,
        fonte_versao=fonte_versao,
    )
    junto = pd.concat([alinhado, alinhadas], ignore_index=True)
    junto = junto.sort_values(by=["series_id", "quarter"], kind="mergesort").reset_index(drop=True)
    return AlinhadoTrimestralSchema.validate(junto, lazy=True)


def exigir_universo(niveis: pd.DataFrame, universo: Sequence[Ativo] = UNIVERSO) -> None:
    """Toda série do universo existe nos níveis alinhados, e todo `asset_id` está no contrato.

    Duas guardas em uma: série faltando para o build com `BLOQUEADO — FONTE INDISPONÍVEL`
    (CA-076) em vez de entregar menos ativos em silêncio, e `asset_id` fora do enum de 32 do
    contrato levanta antes de o pandera ver a tabela (CA-062).
    """
    fora = [a.asset_id for a in universo if a.asset_id not in ASSET_IDS_VALIDOS]
    if fora:
        msg = f"asset_id fora do enum de AssetReturnsQuarterlySchema: {fora}"
        raise AtivoForaDoContrato(msg)
    vistos = Counter(a.asset_id for a in universo)
    repetidos = sorted(asset_id for asset_id, n in vistos.items() if n > 1)
    if repetidos:
        msg = f"asset_id repetido no universo: {repetidos}"
        raise AtivoForaDoContrato(msg)
    presentes = set(niveis["series_id"])
    ausentes = sorted({a.series_id for a in universo if a.series_id not in presentes})
    if ausentes:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {len(ausentes)} série(s) do universo de F-017 sem "
            f"nível alinhado: {ausentes}"
        )
        raise UniversoIncompleto(msg)
    if len(universo) < N_MINIMO_ATIVOS:
        msg = f"universo com {len(universo)} ativos; o contrato exige >= {N_MINIMO_ATIVOS}"
        raise UniversoIncompleto(msg)


def _serie_diaria(raw: pd.DataFrame, series_id: str, *, unidade: str | None = None) -> pd.DataFrame:
    """A série de `raw_series`, uma safra, ordenada e sem nulo — com a unidade conferida."""
    fatia = raw.loc[raw["series_id"] == series_id]
    if fatia.empty:
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {series_id} ausente de raw_series"
        raise FonteIndisponivel(msg)
    if unidade is not None:
        declaradas = sorted(set(fatia["unit"]))
        if declaradas != [unidade]:
            msg = (
                f"{series_id}: unidade {declaradas} != {unidade!r} esperada. Esta é a trava de "
                f"escala do cálculo (CA-016): a série é percentual, não fator."
            )
            raise UnidadeInesperada(msg)
    fatia = validar_indice_temporal(selecionar_vintage(fatia))
    return fatia.loc[fatia["value"].notna(), ["date", "value"]].reset_index(drop=True)


def cdi_trimestral(
    raw: pd.DataFrame, trimestres: Sequence[Any], *, series_id: str = SERIE_CDI
) -> dict[str, dict[str, Any]]:
    """`{quarter: {"cdi_tri": …, "n_dias_uteis": …, "primeira": …, "ultima": …}}`.

    A janela de `T` são as observações cuja **data cai no trimestre `T`** e não passa de
    `quarter_end(T)`. É a mesma janela que `(quarter_end(T−1), quarter_end(T)]` enquanto o
    calendário de publicação do CDI e o calendário bancário da ANBIMA coincidirem — e a
    equivalência é afirmada por teste sobre o acervo real, nos 82 trimestres que têm `T−1`. Esta
    forma é a que vale também para `2006Q1`, o primeiro da janela, e é o que permite reproduzir o
    valor-canário de 2006 encadeando os 4 trimestres.

    O corte em `quarter_end(T)` é a guarda anti-look-ahead: nenhuma taxa publicada depois do
    fechamento do trimestre entra no CDI daquele trimestre (Anti-SPEC §10.2.7).
    """
    serie = _serie_diaria(raw, series_id, unidade=UNIDADE_CDI)
    por_trimestre = serie["date"].dt.to_period("Q").astype(str)
    saida: dict[str, dict[str, Any]] = {}
    for tri in trimestres:
        limite = pd.Timestamp(tri.quarter_end)
        janela = serie.loc[(por_trimestre == tri.quarter) & (serie["date"] <= limite)]
        if janela.empty:
            saida[tri.quarter] = {
                "cdi_tri": None,
                "n_dias_uteis": 0,
                "primeira": None,
                "ultima": None,
                "taxas": (),
            }
            continue
        taxas = tuple(float(v) for v in janela["value"])
        saida[tri.quarter] = {
            "cdi_tri": acumular_taxa_diaria(taxas),
            "n_dias_uteis": int(len(taxas)),
            "primeira": pd.Timestamp(janela["date"].iloc[0]),
            "ultima": pd.Timestamp(janela["date"].iloc[-1]),
            "taxas": taxas,
        }
    return saida


def ipca_trimestral(
    raw: pd.DataFrame, trimestres: Sequence[Any], *, series_id: str = SERIE_IPCA
) -> dict[str, dict[str, Any]]:
    """`{quarter: {"ipca_tri": …, "n_meses": …}}` — acumulação dos **3 meses de referência**.

    `date` de série mensal é o **fim de período civil** (convenção D-a do `DECISIONS_LOG §2.1`),
    então `2006Q1` é jan+fev+mar de 2006 por pertencimento de período, sem aritmética de data.
    Trimestre com menos de 3 meses ⇒ `ipca_tri = None`: deflacionar por 2 meses seria inventar
    um número plausível (Anti-SPEC §10.1.1), e aplicar o IPCA de outro trimestre seria dupla
    deflação (CA-071).
    """
    serie = _serie_diaria(raw, series_id, unidade=UNIDADE_IPCA)
    por_trimestre = serie["date"].dt.to_period("Q").astype(str)
    saida: dict[str, dict[str, Any]] = {}
    for tri in trimestres:
        janela = serie.loc[por_trimestre == tri.quarter]
        n_meses = int(len(janela))
        completo = n_meses == MESES_POR_TRIMESTRE
        saida[tri.quarter] = {
            "ipca_tri": acumular_taxa_diaria(janela["value"].tolist()) if completo else None,
            "n_meses": n_meses,
        }
    return saida


def is_total_return_declarado(
    catalogo: Sequence[Any] | None = None,
) -> dict[str, bool | None]:
    """`{series_id: is_total_return}` do catálogo **declarado** (`series_catalog_data.py`).

    Propagado, nunca inferido: `None` é "a confirmar" (G-01 dos setoriais da B3) e **não** é
    `False`. Comparar price return com total return sem a flag é proibido (CA-064, §10.2.12).
    """
    entradas = catalogo if catalogo is not None else load_catalog()
    return {e.series_id: e.is_total_return for e in entradas}


# ─────────────────────────────────────────────────────────────────────────────
# O cálculo
# ─────────────────────────────────────────────────────────────────────────────


def _caminho_diario(
    serie: pd.DataFrame, de: pd.Timestamp | None, ate: pd.Timestamp | None
) -> list[float]:
    """Os níveis da série em `(de, ate]` — o caminho intra-trimestre, em ordem de data.

    O intervalo é semiaberto à esquerda porque `de` é o fechamento de `T−1`, que já é a **base**
    do 1º retorno diário e não um ponto do trimestre. É o que faz o produto dos fatores diários
    ser idêntico a `ret_tri` (CA-070).
    """
    if de is None or ate is None:
        return []
    janela = serie.loc[(serie["date"] > de) & (serie["date"] <= ate)]
    return [float(v) for v in janela["value"]]


def _desvio_amostral_anualizado_no_trimestre(retornos: Sequence[float]) -> float | None:
    """Desvio **amostral** dos retornos diários × `sqrt(n)` (§6.3); `None` se houver n < 2."""
    if len(retornos) < MINIMO_RETORNOS_DIARIOS_PARA_VOL:
        return None
    media = sum(retornos) / len(retornos)
    variancia = sum((r - media) ** 2 for r in retornos) / (len(retornos) - 1)
    return math.sqrt(variancia) * math.sqrt(len(retornos))


def _sem_metricas(
    motivo: MotivoNulo, *, preco_ini: float | None, preco_fim: float | None
) -> dict[str, Any]:
    """Linha sem retorno em `T`: toda métrica nula, com o motivo, e os preços que **existem**.

    Os níveis não são apagados junto com o retorno: `price_fim` do 1º trimestre da série é dado
    real e fica na tabela — é o que deixa visível que a célula é nula por falta de `T−1`, não por
    falta de preço.
    """
    motivos: dict[str, MotivoNulo] = {
        "ret_tri": motivo,
        "ret_excesso_cdi": MotivoNulo.SEM_RETORNO_CALCULAVEL,
        "ret_real": MotivoNulo.SEM_RETORNO_CALCULAVEL,
        "vol_intra_tri": MotivoNulo.SEM_RETORNO_CALCULAVEL,
        "dd_intra_tri": MotivoNulo.SEM_RETORNO_CALCULAVEL,
        "n_dias_uteis": MotivoNulo.SEM_RETORNO_CALCULAVEL,
    }
    if preco_ini is None:
        motivos["price_ini"] = motivo
    if preco_fim is None:
        motivos["price_fim"] = motivo
    return {
        "ret_tri": None,
        "vol_intra_tri": None,
        "dd_intra_tri": None,
        "n_dias_uteis": None,
        "price_ini": preco_ini,
        "price_fim": preco_fim,
        "motivos": motivos,
    }


def _metricas_de_razao(
    linha: pd.Series, anterior: pd.Series | None, diario: pd.DataFrame
) -> dict[str, Any]:
    """`ret_tri` + métricas intra de um ativo de **nível**, no trimestre da `linha`."""
    preco_fim = None if pd.isna(linha["value"]) else float(linha["value"])
    preco_ini = None if anterior is None or pd.isna(anterior["value"]) else float(anterior["value"])
    if anterior is None:
        return _sem_metricas(
            MotivoNulo.PRIMEIRO_TRIMESTRE_SEM_T_MENOS_1, preco_ini=None, preco_fim=preco_fim
        )
    if preco_fim is None:
        return _sem_metricas(MotivoNulo.NIVEL_AUSENTE_EM_T, preco_ini=preco_ini, preco_fim=None)
    if preco_ini is None:
        return _sem_metricas(
            MotivoNulo.NIVEL_AUSENTE_EM_T_MENOS_1, preco_ini=None, preco_fim=preco_fim
        )

    ret = razao_de_niveis(preco_fim, preco_ini)
    de = None if pd.isna(anterior["date_obs"]) else pd.Timestamp(anterior["date_obs"])
    ate = None if pd.isna(linha["date_obs"]) else pd.Timestamp(linha["date_obs"])
    caminho = _caminho_diario(diario, de, ate)
    vol, queda = metricas_intra_trimestre(caminho, preco_inicial=preco_ini)
    motivos: dict[str, MotivoNulo] = {}
    if not caminho:
        motivos["vol_intra_tri"] = MotivoNulo.SERIE_SEM_DIARIO_NO_TRIMESTRE
        motivos["dd_intra_tri"] = MotivoNulo.SERIE_SEM_DIARIO_NO_TRIMESTRE
        motivos["n_dias_uteis"] = MotivoNulo.SERIE_SEM_DIARIO_NO_TRIMESTRE
    elif vol is None:
        motivos["vol_intra_tri"] = MotivoNulo.DIARIO_CURTO_PARA_DESVIO
    return {
        "ret_tri": ret,
        "vol_intra_tri": vol,
        "dd_intra_tri": queda,
        "n_dias_uteis": float(len(caminho)) if caminho else None,
        "motivos": motivos,
        "price_ini": preco_ini,
        "price_fim": preco_fim,
    }


def _metricas_de_taxa(cdi_do_trimestre: Mapping[str, Any]) -> dict[str, Any]:
    """`ret_tri` de um ativo de **taxa** (o CDI): acumulação diária, sem `T−1` e sem preço.

    `price_ini`/`price_fim` ficam `NULL` com motivo declarado: a série 12 é `%/dia`, não
    número-índice, e fabricar um nível acumulado (base arbitrária) seria inventar coluna de preço
    que a fonte não tem (Anti-SPEC §10.1.1). Por não depender de `T−1`, **o CDI tem retorno no
    1º trimestre da janela** — a única assimetria do universo, e a que permite reproduzir o
    valor-canário de 2006 encadeando os 4 trimestres.
    """
    motivos: dict[str, MotivoNulo] = {
        "price_ini": MotivoNulo.ATIVO_SEM_NIVEL_DE_PRECO,
        "price_fim": MotivoNulo.ATIVO_SEM_NIVEL_DE_PRECO,
    }
    ret = cdi_do_trimestre.get("cdi_tri")
    if ret is None:
        bloco = _sem_metricas(MotivoNulo.CDI_INDISPONIVEL, preco_ini=None, preco_fim=None)
        bloco["motivos"].update(motivos)
        return bloco
    diarios = [taxa / 100.0 for taxa in cdi_do_trimestre["taxas"]]
    vol = _desvio_amostral_anualizado_no_trimestre(diarios)
    if vol is None:
        motivos["vol_intra_tri"] = MotivoNulo.DIARIO_CURTO_PARA_DESVIO
    return {
        "ret_tri": ret,
        "vol_intra_tri": vol,
        # A taxa diária do CDI nunca é negativa: o caminho acumulado é monótono crescente e o
        # drawdown intra-trimestre é exatamente 0 — medido, não "não medido".
        "dd_intra_tri": 0.0,
        "n_dias_uteis": float(cdi_do_trimestre["n_dias_uteis"]),
        "motivos": motivos,
        "price_ini": None,
        "price_fim": None,
    }


def calcular_retornos(
    niveis: pd.DataFrame,
    raw: pd.DataFrame,
    *,
    cdi: Mapping[str, Mapping[str, Any]],
    ipca: Mapping[str, Mapping[str, Any]],
    total_return: Mapping[str, bool | None],
    fonte_versao: str,
    universo: Sequence[Ativo] = UNIVERSO,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """`(asset_returns_quarterly validado, motivos por célula nula)`.

    Uma linha por `(quarter, asset_id)`, só nos trimestres em que a série do ativo **existe** nos
    níveis alinhados — painel desbalanceado por desenho (CA-063/ADR-005 §1).
    """
    exigir_universo(niveis, universo)
    por_serie = {str(sid): grupo for sid, grupo in niveis.groupby("series_id", sort=True)}
    linhas: list[dict[str, Any]] = []
    motivos_por_celula: list[dict[str, str]] = []

    for ativo in universo:
        grupo = por_serie[ativo.series_id].sort_values("quarter").reset_index(drop=True)
        diario = _serie_diaria(raw, ativo.series_id)
        bandeira = total_return.get(ativo.series_id)
        for posicao in range(len(grupo)):
            linha = grupo.iloc[posicao]
            anterior = grupo.iloc[posicao - 1] if posicao > 0 else None
            if ativo.metodo is Metodo.ACUMULACAO_DE_TAXA_DIARIA:
                bloco = _metricas_de_taxa(cdi.get(str(linha["quarter"]), {}))
            else:
                bloco = _metricas_de_razao(linha, anterior, diario)

            quarter = str(linha["quarter"])
            cdi_tri = cdi.get(quarter, {}).get("cdi_tri")
            ipca_tri = ipca.get(quarter, {}).get("ipca_tri")
            ret = bloco["ret_tri"]
            excesso = excesso_por_razao(ret, cdi_tri)
            real = excesso_por_razao(ret, ipca_tri)
            motivos = dict(bloco["motivos"])
            if ret is not None and excesso is None:
                motivos["ret_excesso_cdi"] = MotivoNulo.CDI_INDISPONIVEL
            if ret is not None and real is None:
                motivos["ret_real"] = MotivoNulo.IPCA_INDISPONIVEL
            if bandeira is None:
                motivos["is_total_return"] = MotivoNulo.IS_TOTAL_RETURN_A_CONFIRMAR

            linhas.append(
                {
                    "quarter": quarter,
                    "asset_id": ativo.asset_id,
                    "price_ini": bloco.get("price_ini"),
                    "price_fim": bloco.get("price_fim"),
                    "ret_tri": ret,
                    "ret_excesso_cdi": excesso,
                    "ret_real": real,
                    "vol_intra_tri": bloco["vol_intra_tri"],
                    "dd_intra_tri": bloco["dd_intra_tri"],
                    "is_total_return": bandeira,
                    "n_dias_uteis": bloco["n_dias_uteis"],
                    "ffill_dias_uteis": int(linha["ffill_dias_uteis"]),
                    "data_inicio_serie": pd.Timestamp(linha["data_inicio_serie"]),
                    "source": str(linha["source"]),
                    "series_id": ativo.series_id,
                    "fonte_versao": fonte_versao,
                }
            )
            motivos_por_celula.extend(
                {
                    "quarter": quarter,
                    "asset_id": ativo.asset_id,
                    "coluna": coluna,
                    "motivo": str(motivo),
                }
                for coluna, motivo in sorted(motivos.items())
            )

    tabela = pd.DataFrame(linhas)
    tabela["is_total_return"] = tabela["is_total_return"].astype("boolean")
    tabela = tabela.sort_values(by=["asset_id", "quarter"], kind="mergesort").reset_index(drop=True)
    validado = AssetReturnsQuarterlySchema.validate(tabela, lazy=True)
    return validado, {"celulas": motivos_por_celula}


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DOS_RETORNOS` — o `fonte_versao` desta tabela.

    Hash de arquivos, não do processo (RF-047/CA-121): é o que distingue "o artefato mudou porque
    o código mudou" de "mudou porque o dado mudou". Reusa o algoritmo de F-013/F-014.
    """
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DOS_RETORNOS))


def _iso(valor: Any) -> str | None:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)) or pd.isna(valor):
        return None
    return str(pd.Timestamp(valor).date())


def _num(valor: Any) -> float | None:
    if valor is None or pd.isna(valor):
        return None
    return float(valor)


def _contagem_de_motivos(motivos: Sequence[Mapping[str, str]]) -> dict[str, dict[str, int]]:
    """`{coluna: {motivo: n}}` — a razão de **cada** nulo, agregada."""
    saida: dict[str, dict[str, int]] = {}
    for item in motivos:
        saida.setdefault(item["coluna"], {}).setdefault(item["motivo"], 0)
        saida[item["coluna"]][item["motivo"]] += 1
    return {coluna: dict(sorted(v.items())) for coluna, v in sorted(saida.items())}


def _bloco_por_ativo(
    retornos: pd.DataFrame, motivos: Sequence[Mapping[str, str]], universo: Sequence[Ativo]
) -> list[dict[str, Any]]:
    """Um bloco por ativo: cobertura, 1º trimestre com retorno e nulos com motivo."""
    por_ativo: dict[str, list[Mapping[str, str]]] = {}
    for item in motivos:
        por_ativo.setdefault(item["asset_id"], []).append(item)
    indice = {a.asset_id: a for a in universo}
    blocos: list[dict[str, Any]] = []
    for asset_id, grupo in retornos.groupby("asset_id", sort=True):
        ativo = indice[str(asset_id)]
        com_retorno = grupo.loc[grupo["ret_tri"].notna()]
        blocos.append(
            {
                "asset_id": str(asset_id),
                "series_id": ativo.series_id,
                "bloco": ativo.bloco,
                "metodo": str(ativo.metodo),
                "source": str(grupo["source"].iloc[0]),
                "is_total_return": (
                    None
                    if pd.isna(grupo["is_total_return"].iloc[0])
                    else bool(grupo["is_total_return"].iloc[0])
                ),
                "data_inicio_serie": _iso(grupo["data_inicio_serie"].iloc[0]),
                "n_linhas": int(len(grupo)),
                "primeiro_trimestre": str(grupo["quarter"].min()),
                "ultimo_trimestre": str(grupo["quarter"].max()),
                "primeiro_trimestre_com_retorno": (
                    str(com_retorno["quarter"].min()) if len(com_retorno) else None
                ),
                "n_retornos": int(len(com_retorno)),
                "n_excesso_cdi": int(grupo["ret_excesso_cdi"].notna().sum()),
                "n_real": int(grupo["ret_real"].notna().sum()),
                "ret_tri_min": _num(grupo["ret_tri"].min()),
                "ret_tri_max": _num(grupo["ret_tri"].max()),
                "n_dias_uteis_min": _num(grupo["n_dias_uteis"].min()),
                "n_dias_uteis_max": _num(grupo["n_dias_uteis"].max()),
                "distribuicao_ffill_dias_uteis": {
                    str(k): int(v)
                    for k, v in sorted(grupo["ffill_dias_uteis"].value_counts().items())
                },
                "nulos_por_coluna_com_motivo": _contagem_de_motivos(
                    por_ativo.get(str(asset_id), [])
                ),
            }
        )
    return blocos


def montar_relatorio(
    *,
    retornos: pd.DataFrame,
    motivos: Mapping[str, Any],
    cdi: Mapping[str, Mapping[str, Any]],
    ipca: Mapping[str, Mapping[str, Any]],
    hashes: Mapping[str, Any],
    universo: Sequence[Ativo] = UNIVERSO,
) -> dict[str, Any]:
    """O `relatorio_retornos.json`: cobertura por ativo, nulos com motivo e as bases por trimestre.

    Nenhum carimbo de hora: o relatório é função da entrada e do código, o que é o que faz duas
    rodadas darem arquivos byte-idênticos (RF-048).
    """
    celulas = list(motivos.get("celulas", []))
    nulos = {
        coluna: int(retornos[coluna].isna().sum())
        for coluna in retornos.columns
        if bool(retornos[coluna].isna().any())
    }
    return {
        "asset_returns_quarterly": {
            "linhas": int(len(retornos)),
            "ativos": int(retornos["asset_id"].nunique()),
            "trimestres": int(retornos["quarter"].nunique()),
            "primeiro_trimestre": str(retornos["quarter"].min()),
            "ultimo_trimestre": str(retornos["quarter"].max()),
            "minimo_de_ativos_do_contrato": N_MINIMO_ATIVOS,
            "nulos_por_coluna": dict(sorted(nulos.items())),
            "nulos_por_coluna_com_motivo": _contagem_de_motivos(celulas),
            "sha256": hashes.get("sha256"),
            "bytes": hashes.get("bytes"),
        },
        "convencoes": {
            "ret_tri": "P_fim/P_ini - 1 com niveis de alinhado_trimestral em T e T-1",
            "primeiro_trimestre_da_serie": "ret_tri NULL (sem T-1); nunca 0, nunca backfill",
            "cdi_tri": f"prod(1 + v/100) - 1 sobre {SERIE_CDI} ({UNIDADE_CDI}) no trimestre",
            "ret_excesso_cdi": "(1+ret)/(1+cdi) - 1 — razao, nunca subtracao",
            "ret_real": f"(1+ret)/(1+ipca_tri) - 1, ipca_tri = 3 meses de {SERIE_IPCA}",
            "ipca_tri": "meses de REFERENCIA do trimestre (D-a: date = fim de periodo civil)",
            "vol_intra_tri": "desvio amostral dos retornos diarios * sqrt(n)",
            "dd_intra_tri": "min(P_t / max(P_0..P_t) - 1), com P_0 = fechamento de T-1",
            "n_dias_uteis": "tamanho do caminho diario em (date_obs(T-1), date_obs(T)]",
            "ffill_dias_uteis": "forward-fill da ponta de FECHAMENTO (P_fim); o de P_ini, em T-1",
            "is_total_return": "propagado do series_catalog declarado; None = G-01 a confirmar",
            "janela_do_cdi_vs_caminho_do_ativo": (
                "LIMITACAO DECLARADA (P1-1 do QA da Onda 2, lote B; D-v). A janela do CDI e "
                "(quarter_end(T-1), quarter_end(T)]; o caminho de cada ativo e "
                "(date_obs(T-1), date_obs(T)]. Com ffill = 1 d.u. (D-h: a B3 nao publica no "
                "ultimo d.u. ANBIMA de 20 dos 4os trimestres), date_obs != quarter_end e as duas "
                "janelas diferem de 1 a 3 d.u. em 599 das 1.857 linhas com excesso "
                "(-3: 98, -2: 120, -1: 348, 0: 1.258, +1: 22, +2: 11). Vies implicito no "
                "ret_excesso_cdi: media 0,0185 pp, p95 0,0984 pp, MAXIMO 0,1575 pp; nas 212 "
                "linhas com ffill = 1, media 0,0827 pp. E ~8x menor que o efeito razao-vs-"
                "subtracao (0,139 pp) e a cadeia de precos e continua "
                "(price_ini(T+1) == price_fim(T) em 100% dos casos com ffill), por isso o "
                "calculo NAO foi alterado: a correcao exigiria reconstruir o CDI por ativo. "
                "Declarada aqui e em docs/wiki/modules/canonical.md."
            ),
        },
        "universo": {
            "n_ativos": len(universo),
            "ativos": [
                {
                    "asset_id": a.asset_id,
                    "series_id": a.series_id,
                    "bloco": a.bloco,
                    "metodo": str(a.metodo),
                }
                for a in universo
            ],
            "fora_do_universo": dict(sorted(ATIVOS_FORA_DO_UNIVERSO.items())),
        },
        "ativos": _bloco_por_ativo(retornos, celulas, universo),
        "bases_por_trimestre": [
            {
                "quarter": quarter,
                "cdi_tri": _num(cdi.get(quarter, {}).get("cdi_tri")),
                "cdi_n_dias_uteis": int(cdi.get(quarter, {}).get("n_dias_uteis") or 0),
                "ipca_tri": _num(ipca.get(quarter, {}).get("ipca_tri")),
                "ipca_n_meses": int(ipca.get(quarter, {}).get("n_meses") or 0),
            }
            for quarter in quarters_da_janela()
            if quarter in cdi or quarter in ipca
        ],
        "versao_build": {
            "sha256": versao_build(),
            "modulos": list(MODULOS_DOS_RETORNOS),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoRetornos:
    """O que o build produziu — o CLI imprime, o teste inspeciona, o QA confere."""

    retornos: pd.DataFrame
    relatorio: dict[str, Any]
    caminho_retornos: Path
    caminho_relatorio: Path


def construir(
    *,
    raiz: Path | None = None,
    calendario: Calendario | None = None,
    quarters: Sequence[str] | None = None,
    universo: Sequence[Ativo] = UNIVERSO,
) -> ResultadoRetornos:
    """Reconstrói `data/canonical/asset_returns_quarterly.parquet` de ponta a ponta.

    Sem rede, sem estado, sem efeito fora de `data/canonical/`. `calendario`, `quarters` e
    `universo` existem para o teste cravar uma grade pequena; em produção os três saem do disco e
    do contrato.
    """
    alinhado = _ler_canonical(NOME_ALINHADO, schema=AlinhadoTrimestralSchema, raiz=raiz)
    raw = _ler_canonical(NOME_RAW_SERIES, schema=RawSeriesSchema, raiz=raiz)
    catalogo = pd.read_parquet(caminho_canonical(NOME_CATALOGO, raiz=raiz))

    cal = calendario if calendario is not None else Calendario.do_parquet(raiz=raiz)
    trimestres = grade_de_trimestres(cal, quarters=quarters)
    versao = versao_build()

    derivadas = tuple(s for s in DERIVADAS_ALINHADAS_AQUI if s in {a.series_id for a in universo})
    fatia_derivada = raw.loc[raw["series_id"].isin(derivadas)]
    inicio = inicio_observado_por_serie(catalogo, fatia_derivada) if derivadas else {}
    niveis = niveis_alinhados(
        alinhado,
        raw,
        calendario=cal,
        inicio_por_serie=inicio,
        trimestres=trimestres,
        fonte_versao=versao,
        derivadas=derivadas,
    )

    cdi = cdi_trimestral(raw, trimestres)
    ipca = ipca_trimestral(raw, trimestres)
    retornos, motivos = calcular_retornos(
        niveis,
        raw,
        cdi=cdi,
        ipca=ipca,
        total_return=is_total_return_declarado(),
        fonte_versao=versao,
        universo=universo,
    )

    destino = caminho_canonical(NOME_RETORNOS, raiz=raiz)
    garantir_diretorio(destino.parent)
    retornos.to_parquet(destino, index=False)
    corpo = destino.read_bytes()
    _log.info(
        "gravado %s (%d linhas, %d ativos, sha256=%s…)",
        destino.name,
        len(retornos),
        retornos["asset_id"].nunique(),
        sha256_de(corpo)[:12],
    )

    relatorio = montar_relatorio(
        retornos=retornos,
        motivos=motivos,
        cdi=cdi,
        ipca=ipca,
        hashes={"sha256": sha256_de(corpo), "bytes": len(corpo)},
        universo=universo,
    )
    caminho_relatorio = caminho_canonical(NOME_RELATORIO, raiz=raiz)
    caminho_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ResultadoRetornos(
        retornos=retornos,
        relatorio=relatorio,
        caminho_retornos=destino,
        caminho_relatorio=caminho_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.retornos",
        description=(
            "Materializa data/canonical/asset_returns_quarterly.parquet a partir de "
            "alinhado_trimestral + raw_series (CDI SGS 12 e IPCA SGS 433). Nunca toca a rede."
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

    bloco = resultado.relatorio["asset_returns_quarterly"]
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{NOME_RETORNOS}: {bloco['linhas']} linhas | {bloco['ativos']} ativos | "
        f"{bloco['trimestres']} trimestres | {bloco['primeiro_trimestre']}.."
        f"{bloco['ultimo_trimestre']} | sha256 {bloco['sha256']}"
    )
    print(f"nulos por coluna: {bloco['nulos_por_coluna']}")
    for item in resultado.relatorio["ativos"]:
        print(
            f"  {item['asset_id']:<10} {item['series_id']:<18} n={item['n_linhas']:>3} "
            f"ret={item['n_retornos']:>3} 1o_ret={item['primeiro_trimestre_com_retorno']} "
            f"tr={item['is_total_return']}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script
    raise SystemExit(main())
