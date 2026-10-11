"""F-022 — Métricas por regime × ativo. **Classe C.**

O insumo direto do heatmap do Comitê (F-023), da tabela "regime atual → ranking" (F-024) e da
página de limitações (F-028). Responde, com `n` em **toda** célula, à pergunta literal do e-mail
do Alexandre: *"como cada classe de ativo e até setores performaram em momentos semelhantes"*.

## O que materializa em `data/canonical/`

- **`regime_asset_metrics.parquet`** — `V1` (`revised`) em `T0` + `V3` (vizinhos de `2026Q3`)
  em `T+1`. **É a tabela que F-023/F-024 leem.**
- **`regime_asset_metrics_asof.parquet`** — `V1` sobre a materialização `asof` (F-018), em `T0`.
- **`regime_asset_metrics_horizonte_cruzado.parquet`** — `V1` em `T+1` + `V3` em `T0`.
- **`relatorio_metricas.json`** — dicionário de métricas, rankings, concordância, gate.

### Por que TRÊS Parquets e não uma coluna de lente/horizonte

`RegimeAssetMetricsSchema` tem PK `(lente, regime, asset_id)`, `lente ∈ {V1, V2, V3}` e
`strict=True`. Não existe coluna para a **materialização** (`revised` × `asof`) nem para o
**horizonte** (retorno **no** trimestre do regime × retorno em **T+1**). As três leituras são
necessárias — a `asof` é a leitura operacional de CA-072/074, e o horizonte T+1 é o que a V3 mede
por CA-102 —, e as três colidiriam na PK na mesma tabela.

Acrescentar coluna a schema existente é **alteração**, logo **pausa** (`AGENTS.md §9`, Anti-SPEC
§10.4.24). Então cada combinação `(materialização, horizonte)` é uma **tabela nomeada**, validada
pelo **mesmo** schema, com o nome do arquivo dizendo qual é. O par canônico — V1 no horizonte
contemporâneo, V3 em T+1 — fica em `regime_asset_metrics.parquet`, que é o que F-023/F-024 leem.
A dívida ("uma coluna `materializacao` + uma coluna `horizonte` em `RegimeAssetMetricsSchema`")
é feature classe C própria.

## As métricas, e sobre qual coluna cada uma é medida

A tabela de `metodologia-regimes-macro.md §3`, célula a célula. `asset_returns_quarterly` está em
**fração** (D-o), e as três colunas de retorno têm **o mesmo** padrão de nulo (23 nulos, o
primeiro trimestre de cada série) — então `n_obs` não é ambíguo.

| Coluna da saída | Fórmula | Medida sobre |
|---|---|---|
| `n_obs` | trimestres do regime **com observação daquele ativo** (CA-093) | `ret_tri` não-nulo |
| `ret_medio` / `ret_mediana` | média aritmética e mediana, **lado a lado** (CA-092) | `ret_tri` |
| `ret_desvio` | desvio-padrão **amostral** (`ddof=1`); `None` com `n < 2` | `ret_tri` |
| `erro_padrao_media` | `ret_desvio / sqrt(n)` (CA-092) | `ret_tri` |
| `hit_ratio` | % de trimestres com retorno > 0 | `ret_tri` |
| **`excesso_cdi`** | **média de `(1+r)/(1+cdi)-1`**, **primária** (D5) | `ret_excesso_cdi` |
| `hit_ratio_cdi` | % de trimestres em que bateu o CDI | `ret_excesso_cdi > 0` |
| `ret_real` | média de `(1+r)/(1+ipca_T)-1` | `ret_real` |
| `sharpe_tri` | `média(excesso) / desvio(excesso)`, **trimestral** | `ret_excesso_cdi` |
| `pior_tri` / `melhor_tri` (+ `_quarter`) | mínimo e máximo, com a data | `ret_tri` |
| `beta_ibov` | `cov(ativo, IBOV) / var(IBOV)` nos trimestres da célula | `ret_tri` |
| `alerta_n_baixo` / `conclusao_suprimida` | `n < 8` / `n < 5` (CA-108/109) | `n_obs` |

**O excesso sobre CDI é sempre por razão, nunca subtração** (Anti-SPEC §10.2.13, CA-069): a média
de `(1+r)/(1+cdi)-1` **não** é a média de `r - cdi`, e há teste unitário que falha se alguém
trocar. A diferença é material com Selic de dois dígitos.

**`sharpe_tri` usa o excesso, não a subtração de médias.** `metodologia §3` escreve
`(ret_medio − cdi_medio)/ret_desvio`; isso é uma **subtração** de médias de retorno, que é
exatamente o que a Anti-SPEC §10.2.13 proíbe para "excesso sobre CDI". Este módulo usa
`média(ret_excesso_cdi) / desvio(ret_excesso_cdi)` — numerador e denominador na mesma grandeza,
e a grandeza é a do excesso por razão. O desvio do excesso **zero** (célula de `n = 1`, ou o
próprio `CDI`, cujo excesso é identicamente ~0) devolve `None`, não infinito. O relatório publica
a divergência medida entre as duas fórmulas. **CA-094:** a coluna é **trimestral**; a anualização
é `× sqrt(4) = 2` e está **declarada no relatório**, não aplicada na coluna — e o relatório
carrega a ressalva de que índice não é implementável sem fricção (Anti-SPEC §10.2.11).

**`drawdown`:** `metodologia §3` manda usar `pior_tri` (o mínimo) quando o regime **não é
contíguo**, por ser mais honesto que um max-drawdown montado sobre trimestres descolados no
tempo. Os 4 quadrantes da V1 são fortemente **não** contíguos (e os vizinhos da V3, por
construção, nem são adjacentes), então `pior_tri`/`melhor_tri` com a data **é** o drawdown desta
tabela. O relatório diz isso e publica a contiguidade medida de cada regime.

## O regime de `3T2026` é INDETERMINADO na `revised` — e isso é o resultado

`regimes_v1.parquet` (F-019, **D-m**) dá `regime_v1 = NULL` /
`status_regime_v1 = INDETERMINADO` / `motivo = GAP_AUSENTE` em `2006Q1..2009Q3` + **`2026Q3`**:
`ibcbr_gap` precisa de média móvel de 20 trimestres e o IBC-Br dessaz. do trimestre corrente ainda
não fechou. Então **a V1 `revised` não tem quadrante para o trimestre que o Comitê pergunta.**

Este módulo **não** inventa um. Faz três coisas, todas declaradas no relatório:
1. diz `INDETERMINADO` para `2026Q3` na `revised`, com o motivo;
2. publica o ranking do **último trimestre classificado** (`2026Q2`, `ESTAGFLACAO`) como
   referência explicitamente rotulada de *fallback* — nunca como "o regime atual";
3. publica o ranking do regime que a materialização **`asof`** dá para `2026Q3`
   (`DESACELERACAO`) — e lembra que **CA-074 está acionado** (a V1 troca de rótulo em 33,33% dos
   trimestres entre `revised` e `asof`, acima do limiar de 25%), logo a leitura `asof` **não é
   operacional** pelo critério escrito.

Os **16 trimestres `INDETERMINADO` ficam fora** das células da V1 — a crise de 2008 inteira. Não
viram um quinto rótulo (seria regime inventado) nem entram em outro quadrante. O relatório conta
quantos trimestres e quantas observações de retorno saíram por isso.

## `regimes.parquet` (a junção de **D-r**): machinery pronta, escrita BLOQUEADA

**D-r** delegou a esta feature a junção das três lentes numa tabela que satisfaça
`RegimesSchema`. `montar_regimes` faz a junção inteira e mede, coluna por coluna, o que é
derivável. O resultado medido:

- as **10** colunas de `COLUNAS_V1_DE_REGIMES` vêm de `regimes_v1.parquet` (F-019);
- `regime_v1b` (anulável) fica **nulo** — fase 2 (D2), nunca copiado de `regime_v1`;
- `ciclo_selic` (`nullable=False`) é **derivável**: `ciclo_selic(selic_meta_delta)` de
  `macro_quarterly.py` (**D-t**, importada — não reimplementada), e `selic_meta_delta` tem
  **0 nulos** nos 83 trimestres;
- `regime_v2` (`nullable=False`) é **derivável**: `regime_v1 + "_" + ciclo_selic`, que é a
  definição escrita no próprio contrato;
- `regime_v1` (`nullable=False`, enum de 4) é **BLOQUEIO**: 16 trimestres são `INDETERMINADO`
  por **D-m**;
- `stress_flag` (`nullable=False`) é **BLOQUEIO**: RF-039/CA-106 diz "inclinação cai > 1
  desvio-padrão **ou** USDBRL sobe > 10% no trimestre", mas **não** diz qual inclinação
  (nominal ou real, 5a−1a ou 5a−3a — D-i/D-n), em que amostra o desvio-padrão é estimado, nem
  se o "cai" é sobre o nível ou sobre a variação. É escopo de **F-026**.

Pela regra do `AGENTS.md §9` (inventar dado e alterar schema são as duas proibidas), a saída é a
terceira: **`regimes.parquet` NÃO é gravado**, a fonte autoritativa da V1 continua
`regimes_v1.parquet`, e o relatório publica exatamente os dois bloqueios acima com o que
destravaria cada um. A junção **é** testada: com `stress_flag` injetado e restrita aos 67
trimestres classificados, a tabela **valida** contra `RegimesSchema` — o que prova que o que falta
é dado (de F-026) e contrato (`regime_v1` anulável), não implementação.

## Idempotência, anti-look-ahead e gate de publicação

**Sem rede, sem relógio, sem estado.** Entradas: `regimes_v1{,_asof}.parquet`,
`regime_neighbors_v3.parquet`, `asset_returns_quarterly.parquet`, `macro_quarterly.parquet` e o
**status do ADR-001 em disco**. `fonte_versao` = `sha256` do **conjunto** `MODULOS_DAS_METRICAS`
(RF-047/CA-121) — duas rodadas sobre o mesmo dado dão Parquet byte-idêntico.

Nenhuma métrica desta tabela entra na classificação de nenhum trimestre: o sentido é só
regime → retorno. O horizonte **T+1** é look-ahead **por desenho e declarado** (é o que CA-102
pede), e por isso vive numa tabela com `horizonte` no nome, nunca misturada com a contemporânea.

`especificacao_congelada` sai do status do ADR-001 (**`Proposta` ⇒ `False`**), com falha fechada,
é **conferida contra as linhas de `regimes_v1.parquet`** e vai ao relatório: **nada daqui é
publicável** (CA-090, `AGENTS.md §9`/`§14`). `RegimeAssetMetricsSchema` não tem coluna para o
gate (`strict=True`), então ele é propagado no relatório e no log — não numa coluna inventada.

Referências: SPEC RF-032 (CA-092..094), RF-033 (CA-095..097, consumidor), RF-034 (CA-098/099),
RF-037 (CA-103), RF-040 (CA-108/109), RF-024 (CA-069..071), RF-036 (CA-102) · Anti-SPEC §10.1.1,
§10.2.8, §10.2.10, §10.2.11, §10.2.13, §10.4.24 · ADR-002 (Proposta, D5) · ADR-001 (Proposta) ·
`metodologia-regimes-macro.md §3` · `CONTRACTS.md §4.1`, `§5`, `§5.1a`, `§5.2a` ·
`DECISIONS_LOG §2.3` (D-m, D-o, D-r, D-t, D-u) · `docs/wiki/context/F-022.md`.
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

from apps.pipeline.canonical.build_raw_series import (
    caminhos_dos_componentes,
)
from apps.pipeline.canonical.build_raw_series import (
    versao_build as _hash_dos_componentes,
)
from apps.pipeline.canonical.macro_quarterly import ciclo_selic
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
    Vizinho,
    ranking_de_ativos,
    retornos_em_t_mais_1,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, sha256_de
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from packages.shared.schemas.asset_returns_quarterly import (
    ASSET_IDS_VALIDOS,
    AssetReturnsQuarterlySchema,
    RegimeAssetMetricsSchema,
)
from packages.shared.schemas.regimes import (
    K_VIZINHOS_PADRAO,
    N_ALERTA,
    N_SUPRESSAO,
    MetricaDistancia,
    RegimeNeighborsV3Schema,
    RegimesSchema,
    RegimesV1Schema,
    RegimeV1,
    indice_do_quarter,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Iterable, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes
# ─────────────────────────────────────────────────────────────────────────────

NOME_RETORNOS = "asset_returns_quarterly.parquet"
NOME_NEIGHBORS_V3 = "regime_neighbors_v3.parquet"
NOME_REGIMES_JUNTOS = "regimes.parquet"
NOME_RELATORIO = "relatorio_metricas.json"

NOME_REGIMES_V1_POR_MATERIALIZACAO: dict[str, str] = {
    Materializacao.REVISED.value: "regimes_v1.parquet",
    Materializacao.ASOF.value: "regimes_v1_asof.parquet",
}

#: Os módulos que determinam o conteúdo desta tabela, **nesta ordem** — base de `versao_build`.
#: Mesmo critério de F-014/F-015/F-019/F-021 (P1-1 do QA da Onda 2): este módulo, o contrato das
#: duas tabelas que ele escreve e lê, os produtores das três entradas e o schema dos regimes (onde
#: moram `N_ALERTA`/`N_SUPRESSAO` e o enum dos 4 rótulos). Mudar qualquer um muda o Parquet.
MODULOS_DAS_METRICAS: tuple[str, ...] = (
    "apps.pipeline.canonical.metricas_regime",
    "packages.shared.schemas.asset_returns_quarterly",
    "packages.shared.schemas.regimes",
    "apps.pipeline.canonical.regimes_v1",
    "apps.pipeline.canonical.regimes_v3",
    "apps.pipeline.canonical.retornos",
    "apps.pipeline.canonical.macro_quarterly",
)

LENTE_V1 = "V1"
LENTE_V2 = "V2"
LENTE_V3 = "V3"
"""Os três valores que `RegimeAssetMetricsSchema.lente` aceita. **V2 não é produzida aqui**:
F-020 foi cortada da onda e `ciclo_selic` sozinho não é lente — é corte secundário (CA-083)."""

PREFIXO_REGIME_V3 = "VIZINHOS_"

COLUNA_PRIMARIA = "ret_excesso_cdi"
"""A métrica primária do heatmap (**ADR-002 / D5**, provisória): excesso sobre CDI, por razão."""

COLUNA_NOMINAL = "ret_tri"
COLUNA_REAL = "ret_real"
COLUNAS_DE_RETORNO: tuple[str, ...] = (COLUNA_NOMINAL, COLUNA_PRIMARIA, COLUNA_REAL)

ASSET_ID_REFERENCIA_BETA = "IBOV"
"""`beta_ibov` é medido contra este ativo; para ele próprio o beta é 1 por construção."""

FATOR_ANUALIZACAO_SHARPE = 2.0
"""`sqrt(4)`: CA-094 exige que a anualização seja **dita**, não embutida na coluna trimestral."""

MIN_OBS_DISPERSAO = 2
"""Desvio amostral (`ddof=1`), erro-padrão, Sharpe e beta precisam de 2 observações."""

TOLERANCIA_RECALCULO_FLOAT = 1e-12
"""Tolerância do recálculo independente — **ordem de soma em ponto flutuante**, não método.

O caminho do módulo (`Series.mean()` sobre a fatia do ativo) e o caminho de conferência
(`groupby().mean()` sobre a tabela longa) somam os **mesmos** números em ordem diferente, e o
resíduo medido no acervo real é **6,94e-18** numa célula de 19 observações — 16 ordens de
magnitude abaixo do último dígito que qualquer figura mostra. O limite é `1e-12` porque é folgado
o bastante para a ordem de soma e apertado o bastante para que **qualquer** diferença de método
(subtração em vez de razão vale 2e-3; `ddof` errado, mais) estoure.
"""


class Horizonte(StrEnum):
    """Em que trimestre o retorno é medido, relativo ao trimestre do regime.

    `CONTEMPORANEO` é a leitura descritiva de RF-032/RF-033 ("neste regime, o ativo rendeu X").
    `T_MAIS_1` é a de CA-102 ("o retorno dos trimestres **seguintes** aos momentos parecidos") —
    look-ahead **por desenho**, e é por isso que o nome aparece no arquivo e no relatório.
    """

    CONTEMPORANEO = "T0"
    T_MAIS_1 = "T+1"


@dataclass(frozen=True)
class Tabela:
    """Uma das tabelas materializadas: que lentes tem, em que horizonte, em que arquivo."""

    nome_arquivo: str
    rotulo: str
    materializacao: Materializacao
    horizonte_v1: Horizonte
    horizonte_v3: Horizonte | None
    por_que: str


TABELA_PRINCIPAL = Tabela(
    nome_arquivo="regime_asset_metrics.parquet",
    rotulo="principal",
    materializacao=Materializacao.REVISED,
    horizonte_v1=Horizonte.CONTEMPORANEO,
    horizonte_v3=Horizonte.T_MAIS_1,
    por_que=(
        "cada lente no seu horizonte canonico: a V1 descreve o proprio trimestre do regime "
        "(RF-032/RF-033) e a V3 mede o trimestre SEGUINTE aos vizinhos (CA-102). E a tabela "
        "que F-023 (heatmap) e F-024 (ranking) leem."
    ),
)

TABELA_ASOF = Tabela(
    nome_arquivo="regime_asset_metrics_asof.parquet",
    rotulo="asof",
    materializacao=Materializacao.ASOF,
    horizonte_v1=Horizonte.CONTEMPORANEO,
    horizonte_v3=None,
    por_que=(
        "a leitura operacional: quadrante de T com o que se sabia no fim de T (F-018/CA-072). "
        "So V1 — a V3 nao tem variante asof (LAG_ADJUSTED=False em regimes_v3.py), suas 5 "
        "features sao Focus/curva/cambio/IPCA, nenhuma passa pelo IBC-Br revisado."
    ),
)

TABELA_HORIZONTE_CRUZADO = Tabela(
    nome_arquivo="regime_asset_metrics_horizonte_cruzado.parquet",
    rotulo="horizonte_cruzado",
    materializacao=Materializacao.REVISED,
    horizonte_v1=Horizonte.T_MAIS_1,
    horizonte_v3=Horizonte.CONTEMPORANEO,
    por_que=(
        "o cruzamento que isola o efeito do HORIZONTE do efeito da LENTE: V1 medida em T+1 e V3 "
        "medida nos proprios vizinhos. Sem ela, comparar V1 com V3 confunde as duas coisas."
    ),
)

TABELAS: tuple[Tabela, ...] = (TABELA_PRINCIPAL, TABELA_ASOF, TABELA_HORIZONTE_CRUZADO)

#: As colunas de `RegimesSchema` que **esta** feature consegue derivar, e de onde.
DERIVAVEIS_NA_JUNCAO: dict[str, str] = {
    "ciclo_selic": "macro_quarterly.ciclo_selic(selic_meta_delta) — D-t, funcao importada",
    "regime_v2": 'regime_v1 + "_" + ciclo_selic — a definicao esta no proprio contrato',
    "regime_v1b": "nulo (fase 2, D2); nunca copiado de regime_v1",
}

#: Por que `regimes.parquet` não é gravado. Cada entrada é um bloqueio **medido**, não previsto.
MOTIVO_BLOQUEIO_REGIME_V1_NULO = (
    "regime_v1 e nullable=False no enum de 4 rotulos e {n} dos 83 trimestres sao INDETERMINADO "
    "(D-m: ibcbr_gap ausente). Preencher inventaria quadrante; excluir as linhas tiraria do "
    "canonico 2006Q1..2009Q3 (a crise de 2008) e 2026Q3 (o trimestre do Comite) sem que a "
    "tabela diga que tirou; tornar a coluna anulavel e ALTERACAO de schema existente => pausa."
)
MOTIVO_BLOQUEIO_STRESS_FLAG = (
    "stress_flag e nullable=False e RF-039/CA-106 nao fecha a definicao: 'inclinacao cai > 1 "
    "desvio-padrao OU USDBRL sobe > 10% no trimestre' nao diz qual inclinacao (nominal ou real, "
    "5a-1a ou 5a-3a - D-i/D-n), em que amostra o desvio e estimado, nem se 'cai' e sobre o nivel "
    "ou sobre a variacao. Escolher aqui seria especificar regime fora da feature dona (F-026) e "
    "depois de ver os retornos (Anti-SPEC 10.2.9)."
)


class JuncaoBloqueada(ErroDeExtracao):
    """`regimes.parquet` não pode ser gravado sem inventar dado ou alterar schema."""


# ─────────────────────────────────────────────────────────────────────────────
# Métricas de uma célula — cada uma pura, cada uma testável sozinha
# ─────────────────────────────────────────────────────────────────────────────


def excesso_por_razao(retorno: float, benchmark: float) -> float:
    """`(1+r)/(1+b)-1` — a **única** forma de excesso neste projeto (CA-069, Anti-SPEC §10.2.13).

    Existe aqui para o teste poder comparar, no mesmo arquivo, a razão com a subtração: com CDI
    trimestral de 3,25% e retorno de 10%, a razão dá 6,538% e a subtração 6,75% — 0,21 pp de
    diferença numa só célula, que se acumula em 20 trimestres.
    """
    return (1.0 + retorno) / (1.0 + benchmark) - 1.0


def media_do_excesso(excessos: pd.Series) -> float | None:
    """A média dos excessos **já calculados por razão** em `asset_returns_quarterly` (F-017).

    Não recalcula o excesso: a coluna `ret_excesso_cdi` é a razão, trimestre a trimestre, feita
    pela feature dona do cálculo de retorno. Agregar é média aritmética dos excessos — e **não**
    é a subtração da média do ativo pela média do CDI, que é outra coisa e dá outro número.
    """
    validos = excessos.dropna().astype(float)
    return None if validos.empty else float(validos.mean())


def hit_ratio(valores: pd.Series) -> float | None:
    """% de observações estritamente positivas. `None` quando não há observação."""
    validos = valores.dropna().astype(float)
    return None if validos.empty else float((validos > 0.0).mean())


def desvio_amostral(valores: pd.Series) -> float | None:
    """Desvio-padrão **amostral** (`ddof=1`); `None` com menos de 2 observações."""
    validos = valores.dropna().astype(float)
    if len(validos) < MIN_OBS_DISPERSAO:
        return None
    return float(validos.std(ddof=1))


def erro_padrao(desvio: float | None, n: int) -> float | None:
    """`desvio / sqrt(n)` (CA-092). Com `n ≈ 20` e desvio de 12% dá ~2,7 pp por trimestre.

    É o número que diz que diferenças de retorno médio menores que ~5 pp trimestrais **não se
    distinguem de ruído** (`metodologia §3`, nota de potência estatística).
    """
    if desvio is None or n < MIN_OBS_DISPERSAO:
        return None
    return float(desvio / np.sqrt(n))


def sharpe_trimestral(excessos: pd.Series) -> float | None:
    """`média(excesso) / desvio(excesso)`, **trimestral** — nunca anualizado na coluna (CA-094).

    Desvio **zero** devolve `None`, não infinito: é o caso da linha `CDI` (excesso identicamente
    ~0 por construção) e de qualquer célula degenerada. `None` também com `n < 2`.
    """
    validos = excessos.dropna().astype(float)
    if len(validos) < MIN_OBS_DISPERSAO:
        return None
    desvio = float(validos.std(ddof=1))
    if not np.isfinite(desvio) or desvio == 0.0:
        return None
    return float(validos.mean() / desvio)


def sharpe_anualizado(sharpe_tri: float | None) -> float | None:
    """`sharpe_tri × sqrt(4)`. Só para o **relatório**, que diz que anualizou (CA-094)."""
    return None if sharpe_tri is None else float(sharpe_tri * FATOR_ANUALIZACAO_SHARPE)


def pior_e_melhor(valores: pd.Series, quarters: pd.Series) -> dict[str, Any]:
    """Mínimo e máximo com a **data** — o drawdown desta tabela (`metodologia §3`).

    Regime não contíguo não tem max-drawdown honesto: encadear trimestres que não se seguem no
    tempo produz um número que nenhuma carteira viveu. Então é o pior trimestre, com a data.
    Empate no valor resolve pelo trimestre **mais antigo**, para o resultado ser determinístico.
    """
    validos = valores.dropna().astype(float)
    if validos.empty:
        return {
            "pior_tri": None,
            "pior_tri_quarter": None,
            "melhor_tri": None,
            "melhor_tri_quarter": None,
        }
    rotulos = quarters.loc[validos.index].astype(str)
    ordem = pd.DataFrame({"valor": validos, "quarter": rotulos}).sort_values(
        by=["valor", "quarter"], kind="mergesort"
    )
    primeira, ultima = ordem.iloc[0], ordem.iloc[-1]
    return {
        "pior_tri": float(primeira["valor"]),
        "pior_tri_quarter": str(primeira["quarter"]),
        "melhor_tri": float(ultima["valor"]),
        "melhor_tri_quarter": str(ultima["quarter"]),
    }


def beta_vs_referencia(ativo: pd.Series, referencia: pd.Series) -> float | None:
    """`cov(ativo, ref) / var(ref)` nos trimestres em que **os dois** têm observação.

    `None` quando sobram menos de 2 pares ou a variância da referência é zero. As duas séries
    entram indexadas por `quarter`, e o alinhamento é por índice — nunca por posição.
    """
    par = pd.concat([ativo.rename("a"), referencia.rename("b")], axis=1, join="inner").dropna()
    if len(par) < MIN_OBS_DISPERSAO:
        return None
    variancia = float(par["b"].var(ddof=1))
    if not np.isfinite(variancia) or variancia == 0.0:
        return None
    covariancia = float(par["a"].cov(par["b"]))
    return float(covariancia / variancia)


def contiguidade(quarters: Iterable[str]) -> dict[str, Any]:
    """Quantos blocos contíguos os trimestres de um regime formam, e qual o maior.

    É a medida que justifica `pior_tri` em vez de max-drawdown: 4 quadrantes espalhados em 20
    anos dão muitos blocos de 1-3 trimestres, e um drawdown encadeado sobre isso seria ficção.
    """
    indices = sorted(indice_do_quarter(q) for q in quarters)
    if not indices:
        return {"n_trimestres": 0, "n_blocos": 0, "maior_bloco": 0}
    blocos, atual = 1, 1
    maior = 1
    for anterior, seguinte in zip(indices, indices[1:], strict=False):
        if seguinte - anterior == 1:
            atual += 1
        else:
            blocos += 1
            atual = 1
        maior = max(maior, atual)
    return {"n_trimestres": len(indices), "n_blocos": blocos, "maior_bloco": maior}


def metricas_da_celula(
    observacoes: pd.DataFrame,
    *,
    lente: str,
    regime: str,
    asset_id: str,
    data_inicio_serie: pd.Timestamp,
    referencia_beta: pd.Series,
    fonte_versao: str,
) -> dict[str, Any]:
    """As 17 colunas de `RegimeAssetMetricsSchema` para **uma** célula `(lente, regime, ativo)`.

    `observacoes` é a fatia de `asset_returns_quarterly` daquele ativo nos trimestres daquele
    regime (já no horizonte escolhido), com as colunas `quarter` e as 3 de retorno. **A linha
    existe mesmo com `n_obs = 0`**: `n` em toda célula é regra de apresentação (Anti-SPEC
    §10.2.8 / CA-095), e apagar a célula vazia esconderia que o ativo não existia naquele regime.
    """
    nominal = observacoes[COLUNA_NOMINAL] if len(observacoes) else pd.Series(dtype="float64")
    excesso = observacoes[COLUNA_PRIMARIA] if len(observacoes) else pd.Series(dtype="float64")
    real = observacoes[COLUNA_REAL] if len(observacoes) else pd.Series(dtype="float64")
    quarters = observacoes["quarter"] if len(observacoes) else pd.Series(dtype="object")

    validos_nominal = nominal.dropna()
    n = int(len(validos_nominal))
    desvio = desvio_amostral(nominal)
    extremos = pior_e_melhor(nominal, quarters)

    serie_do_ativo = pd.Series(
        validos_nominal.to_numpy(dtype=float),
        index=quarters.loc[validos_nominal.index].astype(str),
    )

    return {
        "lente": lente,
        "regime": regime,
        "asset_id": asset_id,
        "n_obs": n,
        "ret_medio": None if n == 0 else float(validos_nominal.astype(float).mean()),
        "ret_mediana": None if n == 0 else float(validos_nominal.astype(float).median()),
        "ret_desvio": desvio,
        "erro_padrao_media": erro_padrao(desvio, n),
        "hit_ratio": hit_ratio(nominal),
        "excesso_cdi": media_do_excesso(excesso),
        "hit_ratio_cdi": hit_ratio(excesso),
        "ret_real": media_do_excesso(real),
        "sharpe_tri": sharpe_trimestral(excesso),
        "pior_tri": extremos["pior_tri"],
        "pior_tri_quarter": extremos["pior_tri_quarter"],
        "melhor_tri": extremos["melhor_tri"],
        "melhor_tri_quarter": extremos["melhor_tri_quarter"],
        "beta_ibov": (
            1.0
            if asset_id == ASSET_ID_REFERENCIA_BETA and n >= MIN_OBS_DISPERSAO
            else beta_vs_referencia(serie_do_ativo, referencia_beta)
        ),
        "alerta_n_baixo": alerta_n_baixo(n),
        "conclusao_suprimida": conclusao_suprimida(n),
        "data_inicio_serie": data_inicio_serie,
        "fonte_versao": fonte_versao,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Do regime para as observações de retorno
# ─────────────────────────────────────────────────────────────────────────────


def quarter_do_horizonte(quarter: str, horizonte: Horizonte) -> str:
    """`T` no horizonte contemporâneo; `T+1` no horizonte de CA-102. Nunca `T-1`."""
    if Horizonte(horizonte) is Horizonte.CONTEMPORANEO:
        return quarter
    periodo = pd.Period(quarter, freq="Q") + 1
    return f"{periodo.year}Q{periodo.quarter}"


def trimestres_por_regime_v1(regimes: pd.DataFrame) -> dict[str, list[str]]:
    """`{regime: [quarters]}` da V1, **sem** os `INDETERMINADO` (que não são um 5º rótulo).

    A exclusão é o resultado de **D-m**, não um filtro de conveniência: trimestre sem
    `ibcbr_gap` não tem quadrante, e inventar um violaria a Anti-SPEC §10.1.1. Quantos saíram
    vai ao relatório.
    """
    classificados = regimes.loc[regimes["regime_v1"].notna()]
    saida: dict[str, list[str]] = {}
    for rotulo in (r.value for r in RegimeV1):
        quarters = sorted(
            str(q) for q in classificados.loc[classificados["regime_v1"] == rotulo, "quarter"]
        )
        saida[rotulo] = quarters
    return saida


def nome_do_regime_v3(quarter_ref: str = QUARTER_DO_COMITE) -> str:
    """`VIZINHOS_2026Q3` — o "regime" da V3 é o conjunto de momentos parecidos com a referência."""
    return f"{PREFIXO_REGIME_V3}{quarter_ref}"


def vizinhos_da_lente_canonica(
    neighbors: pd.DataFrame,
    *,
    quarter_ref: str = QUARTER_DO_COMITE,
    metrica: str = MetricaDistancia.MAHALANOBIS.value,
    k: int = K_VIZINHOS_PADRAO,
) -> list[Vizinho]:
    """Os `k` vizinhos da **lente principal** de F-021 (`CONTRACTS.md §5.2a`, **D-u**).

    `metrica=mahalanobis`, `k_usado=8`, `somente_passado=False`, `restrito_pos_2016=False`. As
    outras 23 combinações de `regime_neighbors_v3.parquet` são **sensibilidade** e vão ao
    relatório, não à tabela canônica. Lê `regime_neighbors_v3`, **não** `regime_neighbors`: a
    tabela de contrato perde 4 dos 8 vizinhos de `2026Q3` (`regime_v1_neighbor` é
    `nullable=False`) e não diz que perdeu.
    """
    fatia = neighbors.loc[
        (neighbors["quarter_ref"] == quarter_ref)
        & (neighbors["metrica"] == metrica)
        & (neighbors["k_usado"] == k)
        & (~neighbors["somente_passado"].astype(bool))
        & (~neighbors["restrito_pos_2016"].astype(bool))
    ].sort_values("rank", kind="mergesort")
    if fatia.empty:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {NOME_NEIGHBORS_V3} nao tem a lente canonica "
            f"(quarter_ref={quarter_ref}, metrica={metrica}, k={k}, somente_passado=False, "
            f"restrito_pos_2016=False). Rode F-021."
        )
        raise FonteIndisponivel(msg)
    return [
        Vizinho(
            rank=int(linha["rank"]),
            quarter=str(linha["quarter_neighbor"]),
            distancia=float(linha["distancia"]),
        )
        for _, linha in fatia.iterrows()
    ]


def observacoes_dos_vizinhos(
    vizinhos: Sequence[Vizinho],
    retornos: pd.DataFrame,
    *,
    horizonte: Horizonte,
) -> pd.DataFrame:
    """As observações de retorno dos vizinhos, no horizonte pedido, com as 3 colunas.

    No horizonte `T+1` o mapeamento vizinho → trimestre seguinte vem de
    **`regimes_v3.retornos_em_t_mais_1`**, importada de F-021 — é a função que já resolve CA-102
    (vizinho no fim da janela não contribui, e a ausência aparece no `n`, não como retorno do
    próprio vizinho). Ela devolve **uma** coluna por chamada, então as 3 são juntas por
    `(asset_id, quarter)`; o merge é `inner` sobre a mesma fatia, logo não cria nem perde linha.
    """
    if Horizonte(horizonte) is Horizonte.CONTEMPORANEO:
        alvos = [v.quarter for v in vizinhos]
        fatia = retornos.loc[retornos["quarter"].isin(alvos)].copy()
        fatia["quarter_vizinho"] = fatia["quarter"]
        return fatia.loc[:, ["asset_id", "quarter_vizinho", "quarter", *COLUNAS_DE_RETORNO]]

    partes = [
        retornos_em_t_mais_1(vizinhos, retornos, coluna=coluna) for coluna in COLUNAS_DE_RETORNO
    ]
    juntas = partes[0]
    for parte in partes[1:]:
        juntas = juntas.merge(parte, on=["asset_id", "quarter_vizinho", "quarter"], how="inner")
    return juntas.loc[:, ["asset_id", "quarter_vizinho", "quarter", *COLUNAS_DE_RETORNO]]


# ─────────────────────────────────────────────────────────────────────────────
# Montagem da tabela
# ─────────────────────────────────────────────────────────────────────────────


def _inicio_por_ativo(retornos: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """`{asset_id: data_inicio_serie}` — a janela própria de cada ativo (CA-063/CA-097)."""
    por_ativo = retornos.groupby("asset_id")["data_inicio_serie"].min()
    return {str(k): pd.Timestamp(v) for k, v in por_ativo.items()}


def _referencia_beta(retornos: pd.DataFrame, quarters: Sequence[str]) -> pd.Series:
    """A série de `ret_tri` do IBOV nos trimestres da célula, indexada por `quarter`."""
    fatia = retornos.loc[
        (retornos["asset_id"] == ASSET_ID_REFERENCIA_BETA) & (retornos["quarter"].isin(quarters))
    ]
    return pd.Series(
        fatia[COLUNA_NOMINAL].to_numpy(dtype=float), index=fatia["quarter"].astype(str)
    )


def _celulas(
    *,
    lente: str,
    grupos: dict[str, list[str]],
    retornos: pd.DataFrame,
    horizonte: Horizonte,
    ativos: Sequence[str],
    inicio: dict[str, pd.Timestamp],
    fonte_versao: str,
) -> list[dict[str, Any]]:
    """O produto cartesiano `regime × ativo` de uma lente, com a célula vazia preservada."""
    linhas: list[dict[str, Any]] = []
    for regime, quarters_do_regime in grupos.items():
        alvos = [quarter_do_horizonte(q, horizonte) for q in quarters_do_regime]
        janela = retornos.loc[retornos["quarter"].isin(alvos)]
        referencia = _referencia_beta(retornos, alvos)
        for asset_id in ativos:
            observacoes = janela.loc[janela["asset_id"] == asset_id]
            linhas.append(
                metricas_da_celula(
                    observacoes,
                    lente=lente,
                    regime=regime,
                    asset_id=asset_id,
                    data_inicio_serie=inicio[asset_id],
                    referencia_beta=referencia,
                    fonte_versao=fonte_versao,
                )
            )
    return linhas


def montar_tabela(
    tabela: Tabela,
    *,
    regimes_v1: pd.DataFrame,
    retornos: pd.DataFrame,
    vizinhos: Sequence[Vizinho],
    fonte_versao: str,
    quarter_ref_v3: str = QUARTER_DO_COMITE,
) -> pd.DataFrame:
    """Uma das três tabelas de `TABELAS`, validada por `RegimeAssetMetricsSchema`.

    A ordenação é determinística (`lente`, `regime`, `asset_id`) e o índice é descartado — é o
    que faz duas rodadas darem Parquet byte-idêntico (RF-048/CA-121).
    """
    ativos = sorted(str(a) for a in retornos["asset_id"].unique())
    desconhecidos = [a for a in ativos if a not in ASSET_IDS_VALIDOS]
    if desconhecidos:
        msg = f"asset_id fora de ASSET_IDS_VALIDOS em {NOME_RETORNOS}: {desconhecidos}"
        raise SerieInconsistente(msg)
    inicio = _inicio_por_ativo(retornos)

    linhas = _celulas(
        lente=LENTE_V1,
        grupos=trimestres_por_regime_v1(regimes_v1),
        retornos=retornos,
        horizonte=tabela.horizonte_v1,
        ativos=ativos,
        inicio=inicio,
        fonte_versao=fonte_versao,
    )

    if tabela.horizonte_v3 is not None:
        regime_v3 = nome_do_regime_v3(quarter_ref_v3)
        observadas = observacoes_dos_vizinhos(vizinhos, retornos, horizonte=tabela.horizonte_v3)
        referencia = _referencia_beta(retornos, list(observadas["quarter"].unique()))
        for asset_id in ativos:
            linhas.append(
                metricas_da_celula(
                    observadas.loc[observadas["asset_id"] == asset_id],
                    lente=LENTE_V3,
                    regime=regime_v3,
                    asset_id=asset_id,
                    data_inicio_serie=inicio[asset_id],
                    referencia_beta=referencia,
                    fonte_versao=fonte_versao,
                )
            )

    quadro = pd.DataFrame(linhas)
    quadro["data_inicio_serie"] = pd.to_datetime(quadro["data_inicio_serie"])
    quadro = quadro.sort_values(by=["lente", "regime", "asset_id"], kind="mergesort").reset_index(
        drop=True
    )
    return RegimeAssetMetricsSchema.validate(quadro, lazy=True)  # type: ignore[return-value]


# ─────────────────────────────────────────────────────────────────────────────
# A junção de D-r: `regimes.parquet`
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JuncaoRegimes:
    """O que a junção das lentes conseguiu — e, quando não conseguiu, exatamente por quê."""

    tabela: pd.DataFrame | None
    bloqueios: list[str] = field(default_factory=list)
    derivadas: dict[str, str] = field(default_factory=dict)
    trimestres_indeterminados: list[str] = field(default_factory=list)
    distribuicao_ciclo: dict[str, int] = field(default_factory=dict)

    @property
    def gravavel(self) -> bool:
        """`True` só quando **nenhuma** coluna de `RegimesSchema` exigiu dado inventado."""
        return self.tabela is not None and not self.bloqueios


def montar_regimes(
    *,
    regimes_v1: pd.DataFrame,
    macro: pd.DataFrame,
    stress_flag: pd.Series | None = None,
    somente_classificados: bool = False,
) -> JuncaoRegimes:
    """A junção de **D-r**: as lentes numa tabela que satisfaça `RegimesSchema`.

    Deriva o que é derivável e **mede** o que não é. `ciclo_selic` vem da função publicada em
    `macro_quarterly.py` (**D-t**, importada — não reimplementada) e `regime_v2` é
    `regime_v1 + "_" + ciclo_selic`, que é a definição escrita no próprio contrato.

    `stress_flag` entra como **parâmetro** justamente porque não é desta feature: `None` (o caso
    real) produz um bloqueio declarado; uma série indexada por `quarter` produz a tabela. É o que
    permite o teste provar que a junção está correta sem que o módulo escolha uma definição de
    stress que RF-039 não fecha.

    `somente_classificados=True` dropa os `INDETERMINADO`. Não é o default e não é o que o build
    real faz: tirar 2006Q1..2009Q3 e 2026Q3 do canônico em silêncio é pior que não ter a tabela.
    """
    deltas = dict(zip(macro["quarter"].astype(str), macro["selic_meta_delta"], strict=True))
    base = regimes_v1.copy()
    base["quarter"] = base["quarter"].astype(str)

    ciclos = [ciclo_selic(deltas.get(q)) for q in base["quarter"]]
    base["ciclo_selic"] = ciclos

    bloqueios: list[str] = []
    indeterminados = sorted(str(q) for q in base.loc[base["regime_v1"].isna(), "quarter"])

    sem_ciclo = sorted(str(q) for q, c in zip(base["quarter"], ciclos, strict=True) if c is None)
    if sem_ciclo:
        bloqueios.append(
            f"ciclo_selic nulo em {len(sem_ciclo)} trimestres (selic_meta_delta ausente): "
            f"{sem_ciclo[:5]}"
        )

    if somente_classificados:
        base = base.loc[base["regime_v1"].notna()].copy()
    elif indeterminados:
        bloqueios.append(MOTIVO_BLOQUEIO_REGIME_V1_NULO.format(n=len(indeterminados)))

    if stress_flag is None:
        bloqueios.append(MOTIVO_BLOQUEIO_STRESS_FLAG)
        base["stress_flag"] = pd.NA
    else:
        base["stress_flag"] = base["quarter"].map(stress_flag).astype("boolean")
        faltando = sorted(str(q) for q in base.loc[base["stress_flag"].isna(), "quarter"])
        if faltando:
            bloqueios.append(f"stress_flag ausente em {len(faltando)}: {faltando[:5]}")

    base["regime_v1b"] = None
    base["regime_v2"] = [
        None if pd.isna(v1) or c is None else f"{v1}_{c}"
        for v1, c in zip(base["regime_v1"], base["ciclo_selic"], strict=True)
    ]

    distribuicao = {str(k): int(v) for k, v in pd.Series(ciclos).value_counts(dropna=False).items()}

    colunas = list(RegimesSchema.to_schema().columns)
    faltando_coluna = [c for c in colunas if c not in base.columns]
    if faltando_coluna:  # pragma: no cover - guarda de contrato, nao ocorre hoje
        bloqueios.append(f"colunas de RegimesSchema sem origem: {faltando_coluna}")

    tabela: pd.DataFrame | None = None
    if not bloqueios:
        candidata = base.loc[:, colunas].sort_values("quarter", kind="mergesort")
        validada = RegimesSchema.validate(candidata.reset_index(drop=True), lazy=True)
        tabela = validada  # type: ignore[assignment]

    return JuncaoRegimes(
        tabela=tabela,
        bloqueios=bloqueios,
        derivadas=dict(DERIVAVEIS_NA_JUNCAO),
        trimestres_indeterminados=indeterminados,
        distribuicao_ciclo=distribuicao,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entradas
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


def ler_regimes_v1(
    *, materializacao: Materializacao = Materializacao.REVISED, raiz: Path | None = None
) -> pd.DataFrame:
    """Lê e valida `regimes_v1{,_asof}.parquet` (F-019, `RegimesV1Schema`)."""
    nome = NOME_REGIMES_V1_POR_MATERIALIZACAO[Materializacao(materializacao).value]
    return _ler_canonical(
        nome,
        schema=RegimesV1Schema,
        raiz=raiz,
        como="rode `uv run python -m apps.pipeline.canonical.regimes_v1` (F-019)",
    )


def ler_retornos(*, raiz: Path | None = None) -> pd.DataFrame:
    """Lê e valida `asset_returns_quarterly.parquet` (F-017)."""
    return _ler_canonical(
        NOME_RETORNOS,
        schema=AssetReturnsQuarterlySchema,
        raiz=raiz,
        como="rode `uv run python -m apps.pipeline.canonical.retornos` (F-017)",
    )


def ler_neighbors_v3(*, raiz: Path | None = None) -> pd.DataFrame:
    """Lê e valida `regime_neighbors_v3.parquet` — a lente **completa** de F-021 (**D-u**)."""
    return _ler_canonical(
        NOME_NEIGHBORS_V3,
        schema=RegimeNeighborsV3Schema,
        raiz=raiz,
        como="rode `uv run python -m apps.pipeline.canonical.regimes_v3 --offline` (F-021)",
    )


def conferir_gate(regimes_v1: pd.DataFrame, *, congelada: bool) -> None:
    """A entrada concorda com o status do ADR-001 em disco? Senão, falha ruidosamente.

    É a guarda contra o pior modo de falha deste projeto: um Parquet antigo, gerado quando o ADR
    tinha outro status, entrar na tabela publicável sem ninguém notar (CA-090).
    """
    valores = set(bool(v) for v in regimes_v1["especificacao_congelada"].unique())
    if valores != {congelada}:
        msg = (
            f"regimes_v1 diz especificacao_congelada={valores} e o ADR-001 em disco diz "
            f"{congelada}: reconstrua F-019 antes de medir metricas (CA-090)"
        )
        raise SerieInconsistente(msg)


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DAS_METRICAS` — o `fonte_versao` desta tabela."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DAS_METRICAS))


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────

DICIONARIO_DE_METRICAS: dict[str, str] = {
    "n_obs": "numero de trimestres do regime COM observacao daquele ativo (CA-093). Nunca nulo.",
    "ret_medio": "media aritmetica de ret_tri (nominal, fracao).",
    "ret_mediana": "mediana de ret_tri — lado a lado com a media (CA-092); divergencia grande = "
    "um trimestre dominando.",
    "ret_desvio": "desvio-padrao amostral (ddof=1) de ret_tri; None com n < 2.",
    "erro_padrao_media": "ret_desvio / sqrt(n) (CA-092). Diferencas de media menores que ~2x "
    "isso nao se distinguem de ruido.",
    "hit_ratio": "fracao de trimestres com ret_tri > 0.",
    "excesso_cdi": "METRICA PRIMARIA (ADR-002/D5): media de ret_excesso_cdi, que e "
    "(1+r)/(1+cdi)-1 por razao, trimestre a trimestre. NUNCA subtracao (Anti-SPEC 10.2.13).",
    "hit_ratio_cdi": "fracao de trimestres com ret_excesso_cdi > 0 — a metrica que o Comite "
    "brasileiro de fato usa.",
    "ret_real": "media de ret_real, que e (1+r)/(1+ipca_T)-1 com o IPCA do MESMO trimestre.",
    "sharpe_tri": "media(ret_excesso_cdi)/desvio(ret_excesso_cdi), TRIMESTRAL. Desvio zero => "
    "None. Anualizacao declarada em `anualizacao`, nao aplicada na coluna (CA-094).",
    "pior_tri/melhor_tri (+_quarter)": "minimo e maximo de ret_tri com a data. E o `drawdown` "
    "desta tabela: regime nao contiguo nao tem max-drawdown honesto (metodologia 3).",
    "beta_ibov": "cov(ativo, IBOV)/var(IBOV) em ret_tri nos trimestres da celula; 1.0 para o "
    "proprio IBOV; None com menos de 2 pares.",
    "alerta_n_baixo": f"n_obs < {N_ALERTA} (CA-108) — hachura no heatmap.",
    "conclusao_suprimida": f"n_obs < {N_SUPRESSAO} (CA-109) — a linha FICA, a conclusao nao: o "
    "texto diz 'indicacao preliminar, n=X'.",
    "data_inicio_serie": "janela propria do ativo, para o rodape das figuras (CA-097).",
}


def _celula_legivel(linha: pd.Series) -> dict[str, Any]:
    """Uma célula no formato do relatório — sempre com `n`, sempre com as duas flags."""

    def _f(valor: Any) -> float | None:
        return None if pd.isna(valor) else float(valor)

    return {
        "lente": str(linha["lente"]),
        "regime": str(linha["regime"]),
        "asset_id": str(linha["asset_id"]),
        "n_obs": int(linha["n_obs"]),
        "excesso_cdi": _f(linha["excesso_cdi"]),
        "ret_medio": _f(linha["ret_medio"]),
        "ret_mediana": _f(linha["ret_mediana"]),
        "erro_padrao_media": _f(linha["erro_padrao_media"]),
        "hit_ratio_cdi": _f(linha["hit_ratio_cdi"]),
        "sharpe_tri": _f(linha["sharpe_tri"]),
        "sharpe_anualizado": sharpe_anualizado(_f(linha["sharpe_tri"])),
        "pior_tri": _f(linha["pior_tri"]),
        "pior_tri_quarter": (
            None if pd.isna(linha["pior_tri_quarter"]) else str(linha["pior_tri_quarter"])
        ),
        "alerta_n_baixo": bool(linha["alerta_n_baixo"]),
        "conclusao_suprimida": bool(linha["conclusao_suprimida"]),
    }


def ranking_do_regime(
    metricas: pd.DataFrame, *, lente: str, regime: str, top: int | None = None
) -> list[dict[str, Any]]:
    """Os ativos de uma célula ordenados por `excesso_cdi` — a ordem de RF-034/CA-098.

    Célula sem observação vai para o **fim**, nunca para o topo: `None` não é "o melhor". Toda
    linha carrega `n_obs` e as duas flags, porque RF-034 pede semáforo e CA-099 proíbe afirmação
    conclusiva com `n < 5`.
    """
    fatia = metricas.loc[(metricas["lente"] == lente) & (metricas["regime"] == regime)]
    linhas = [_celula_legivel(linha) for _, linha in fatia.iterrows()]
    linhas.sort(
        key=lambda c: (
            c["excesso_cdi"] is None,
            -(c["excesso_cdi"] if c["excesso_cdi"] is not None else 0.0),
            c["asset_id"],
        )
    )
    return linhas if top is None else linhas[:top]


def top_n_de(ranking: Sequence[dict[str, Any]], n: int = 5) -> list[str]:
    """Os `n` primeiros `asset_id` de um ranking, **ignorando** célula sem observação."""
    return [c["asset_id"] for c in ranking if c["excesso_cdi"] is not None][:n]


def concordancia_entre_lentes(
    rankings: dict[str, Sequence[dict[str, Any]]], *, n: int = 5
) -> dict[str, Any]:
    """A tabela de RF-037/CA-103: top-`n` por lente, e a divergência **como resultado**.

    Se as lentes concordam, isso é a mensagem. Se divergem, **isso** é a mensagem — o que a
    tabela nunca faz é escolher uma e omitir as outras.
    """
    tops = {rotulo: top_n_de(ranking, n) for rotulo, ranking in rankings.items()}
    conjuntos = {rotulo: set(valores) for rotulo, valores in tops.items()}
    pares: dict[str, Any] = {}
    rotulos = sorted(tops)
    for i, a in enumerate(rotulos):
        for b in rotulos[i + 1 :]:
            uniao = conjuntos[a] | conjuntos[b]
            pares[f"{a}__x__{b}"] = {
                "em_comum": sorted(conjuntos[a] & conjuntos[b]),
                "n_em_comum": len(conjuntos[a] & conjuntos[b]),
                "jaccard": (len(conjuntos[a] & conjuntos[b]) / len(uniao)) if uniao else None,
                f"so_em_{a}": sorted(conjuntos[a] - conjuntos[b]),
                f"so_em_{b}": sorted(conjuntos[b] - conjuntos[a]),
            }
    intersecao = set.intersection(*conjuntos.values()) if conjuntos else set()
    return {
        "n": n,
        "top_por_lente": tops,
        "pares": pares,
        "em_todas_as_lentes": sorted(intersecao),
        "leitura": (
            "Divergencia entre lentes e RESULTADO, nao erro (CA-103): com n de 8 a 19 por celula "
            "e erro-padrao de 2,5 a 5 pp, a ordem do topo nao e estavel. O que concorda nas tres "
            "e o que tem lastro."
        ),
    }


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float | None:
    """`|A ∩ B| / |A ∪ B|`; `None` quando os dois conjuntos são vazios."""
    ca, cb = set(a), set(b)
    uniao = ca | cb
    return (len(ca & cb) / len(uniao)) if uniao else None


def concordancia_por_referencia(
    *,
    neighbors: pd.DataFrame,
    regimes_v1: pd.DataFrame,
    retornos: pd.DataFrame,
    metricas_v1: pd.DataFrame,
    n: int = 5,
) -> dict[str, Any]:
    """V1 × V3 em **todos** os trimestres de referência, não só no último. Devolve a distribuição.

    **Por que existe (P1 do QA da Onda 3):** afirmar concordância olhando só `2026Q3` é escolher o
    trimestre depois de ver o resultado. O mesmo erro já foi pego em F-021, onde a sobreposição
    `somente_passado` × descritiva é **Jaccard 1,0 em `2026Q3`** mas tem **mediana 0,455** nas 58
    referências comparáveis. Aqui a conta é feita para cada `quarter_ref` da lente canônica:
    top-`n` da **V3 em T+1** dos vizinhos daquele `quarter_ref` contra top-`n` da **V1** no
    quadrante em que aquele mesmo `quarter_ref` caiu.

    Referência sem quadrante V1 (os 16 de **D-m**) **não** entra na distribuição e é contada à
    parte — nunca comparada contra um quadrante escolhido a dedo.
    """
    rotulo_por_quarter = {
        str(q): (None if pd.isna(r) else str(r))
        for q, r in zip(regimes_v1["quarter"], regimes_v1["regime_v1"], strict=True)
    }
    tops_v1 = {
        regime: top_n_de(ranking_do_regime(metricas_v1, lente=LENTE_V1, regime=regime), n)
        for regime in (r.value for r in RegimeV1)
    }

    referencias = sorted(str(q) for q in neighbors["quarter_ref"].unique())
    por_referencia: list[dict[str, Any]] = []
    sem_v1: list[str] = []
    for quarter_ref in referencias:
        regime = rotulo_por_quarter.get(quarter_ref)
        if regime is None:
            sem_v1.append(quarter_ref)
            continue
        vizinhos = vizinhos_da_lente_canonica(neighbors, quarter_ref=quarter_ref)
        observadas = observacoes_dos_vizinhos(vizinhos, retornos, horizonte=Horizonte.T_MAIS_1)
        ranking = ranking_de_ativos(observadas, coluna=COLUNA_PRIMARIA)
        top_v3 = [linha["asset_id"] for linha in ranking if linha["media"] is not None][:n]
        por_referencia.append(
            {
                "quarter_ref": quarter_ref,
                "regime_v1_da_referencia": regime,
                "top_v1": tops_v1[regime],
                "top_v3_t_mais_1": top_v3,
                "em_comum": sorted(set(tops_v1[regime]) & set(top_v3)),
                "jaccard": _jaccard(tops_v1[regime], top_v3),
            }
        )

    valores = pd.Series(
        [linha["jaccard"] for linha in por_referencia if linha["jaccard"] is not None],
        dtype="float64",
    )
    do_comite = next(
        (linha for linha in por_referencia if linha["quarter_ref"] == QUARTER_DO_COMITE), None
    )
    return {
        "n_top": n,
        "referencias_na_lente": len(referencias),
        "referencias_comparadas": int(len(valores)),
        "referencias_sem_quadrante_v1": sem_v1,
        "distribuicao_jaccard": (
            None
            if valores.empty
            else {
                "min": float(valores.min()),
                "q1": float(valores.quantile(0.25)),
                "mediana": float(valores.median()),
                "media": float(valores.mean()),
                "q3": float(valores.quantile(0.75)),
                "max": float(valores.max()),
                "n_zeros": int((valores == 0.0).sum()),
                "n_iguais_a_1": int((valores == 1.0).sum()),
            }
        ),
        "do_quarter_do_comite": do_comite,
        "por_referencia": por_referencia,
        "leitura": (
            "A concordancia V1 x V3 e reportada como DISTRIBUICAO sobre todas as referencias da "
            f"lente, nao como o numero de {QUARTER_DO_COMITE}. Olhar so o ultimo trimestre e "
            "escolher a evidencia depois de ver o resultado (Anti-SPEC 10.2.9). "
            f"{QUARTER_DO_COMITE} nao entra na distribuicao: nao tem quadrante V1 na revised "
            "(D-m), e aparece em `referencias_sem_quadrante_v1`."
        ),
    }


def _tabela_de_n(metricas: pd.DataFrame) -> dict[str, Any]:
    """`n` por `(lente, regime, ativo)` em forma de tabela — CA-095 no dado, antes da figura."""
    pivot = metricas.pivot_table(
        index="asset_id", columns=["lente", "regime"], values="n_obs", aggfunc="first"
    )
    return {
        "por_ativo": {
            str(ativo): {
                f"{lente}:{regime}": int(valor) for (lente, regime), valor in linha.items()
            }
            for ativo, linha in pivot.iterrows()
        },
        "celulas": int(len(metricas)),
        "celulas_sem_observacao": int((metricas["n_obs"] == 0).sum()),
        "celulas_com_alerta_n_baixo": int(metricas["alerta_n_baixo"].sum()),
        "celulas_com_conclusao_suprimida": int(metricas["conclusao_suprimida"].sum()),
        "n_minimo": int(metricas["n_obs"].min()),
        "n_maximo": int(metricas["n_obs"].max()),
    }


def _extremos_de_excesso(metricas: pd.DataFrame, *, quantas: int = 3) -> dict[str, Any]:
    """As `quantas` células de maior e menor `excesso_cdi`, com `n` — a revisão numérica."""
    com_valor = metricas.loc[metricas["excesso_cdi"].notna()].sort_values(
        by=["excesso_cdi", "lente", "regime", "asset_id"], kind="mergesort"
    )
    return {
        "maiores": [
            _celula_legivel(linha) for _, linha in com_valor.tail(quantas).iloc[::-1].iterrows()
        ],
        "menores": [_celula_legivel(linha) for _, linha in com_valor.head(quantas).iterrows()],
    }


def _recalculo_independente(metricas: pd.DataFrame, bloco: pd.DataFrame) -> dict[str, Any]:
    """`excesso_cdi` da tabela × a média recalculada por `groupby` cru — tolerância **zero**.

    O `bloco` é a tabela longa `(regime, asset_id, ret_excesso_cdi)` montada fora de
    `metricas_da_celula`. Se o caminho de agregação do módulo divergir de um `groupby().mean()`
    direto em uma única célula, isto acusa — é o teste de consistência que `AGENTS.md §15 passo 9`
    pede, rodando dentro do próprio build. A tolerância é `TOLERANCIA_RECALCULO_FLOAT`, que é
    ordem de soma em ponto flutuante e nada mais.
    """
    if bloco.empty:
        return {
            "celulas_conferidas": 0,
            "max_abs_diferenca": None,
            "divergencias": [],
            "tolerancia": TOLERANCIA_RECALCULO_FLOAT,
        }
    direto = bloco.groupby(["regime", "asset_id"])[COLUNA_PRIMARIA].mean()
    divergencias: list[dict[str, Any]] = []
    maior = 0.0
    conferidas = 0
    for _, linha in metricas.loc[metricas["lente"] == LENTE_V1].iterrows():
        chave = (str(linha["regime"]), str(linha["asset_id"]))
        if chave not in direto.index:
            continue
        conferidas += 1
        esperado = float(direto.loc[chave])
        obtido = linha["excesso_cdi"]
        if pd.isna(obtido):
            divergencias.append({"celula": list(chave), "tabela": None, "groupby": esperado})
            continue
        diferenca = abs(float(obtido) - esperado)
        maior = max(maior, diferenca)
        if diferenca > TOLERANCIA_RECALCULO_FLOAT:
            divergencias.append(
                {
                    "celula": list(chave),
                    "tabela": float(obtido),
                    "groupby": esperado,
                    "diferenca": diferenca,
                }
            )
    return {
        "celulas_conferidas": conferidas,
        "max_abs_diferenca": maior,
        "divergencias": divergencias[:10],
        "tolerancia": TOLERANCIA_RECALCULO_FLOAT,
    }


def montar_relatorio(
    *,
    tabelas: dict[str, pd.DataFrame],
    regimes: dict[str, pd.DataFrame],
    retornos: pd.DataFrame,
    neighbors: pd.DataFrame,
    vizinhos: Sequence[Vizinho],
    juncao: JuncaoRegimes,
    congelada: bool,
    status_adr: str,
    ranking_v3_t1: Sequence[dict[str, Any]],
    hashes: dict[str, Any],
) -> dict[str, Any]:
    """O `relatorio_metricas.json` inteiro. Nenhum número aqui é inventado nem arredondado."""
    principal = tabelas[TABELA_PRINCIPAL.rotulo]
    asof = tabelas[TABELA_ASOF.rotulo]
    cruzado = tabelas[TABELA_HORIZONTE_CRUZADO.rotulo]

    v1_revised = regimes[Materializacao.REVISED.value]
    v1_asof = regimes[Materializacao.ASOF.value]
    grupos_revised = trimestres_por_regime_v1(v1_revised)

    rotulo_revised = v1_revised.set_index("quarter").loc[QUARTER_DO_COMITE]
    rotulo_asof = v1_asof.set_index("quarter").loc[QUARTER_DO_COMITE]
    regime_comite_revised = (
        None if pd.isna(rotulo_revised["regime_v1"]) else str(rotulo_revised["regime_v1"])
    )
    regime_comite_asof = (
        None if pd.isna(rotulo_asof["regime_v1"]) else str(rotulo_asof["regime_v1"])
    )

    classificados = v1_revised.loc[v1_revised["regime_v1"].notna(), "quarter"]
    ultimo_classificado = str(sorted(classificados.astype(str))[-1])
    regime_do_ultimo = str(v1_revised.set_index("quarter").loc[ultimo_classificado, "regime_v1"])

    regime_v3 = nome_do_regime_v3()
    rankings_para_concordancia: dict[str, Sequence[dict[str, Any]]] = {
        f"V1_revised_{regime_do_ultimo}_{ultimo_classificado}": ranking_do_regime(
            principal, lente=LENTE_V1, regime=regime_do_ultimo
        ),
        "V3_vizinhos_2026Q3_T_mais_1": ranking_do_regime(
            principal, lente=LENTE_V3, regime=regime_v3
        ),
    }
    if regime_comite_asof is not None:
        rankings_para_concordancia[f"V1_asof_{regime_comite_asof}_2026Q3"] = ranking_do_regime(
            asof, lente=LENTE_V1, regime=regime_comite_asof
        )

    bloco_longo = _bloco_longo_v1(v1_revised, retornos, horizonte=Horizonte.CONTEMPORANEO)

    indeterminados = sorted(
        str(q) for q in v1_revised.loc[v1_revised["regime_v1"].isna(), "quarter"]
    )
    obs_fora = int(
        retornos.loc[retornos["quarter"].isin(indeterminados), COLUNA_NOMINAL].notna().sum()
    )

    return {
        "feature": "F-022",
        "lente": {
            "metrica_primaria": COLUNA_PRIMARIA,
            "adr": "ADR-002",
            "status_do_adr_002": "Proposta (D5): virar D5 troca 1 parametro da figura",
            "unidade": "fracao (D-o: asset_returns_quarterly em fracao, macro_quarterly em pp)",
            "v1_lente_de_regime": "regimes_v1.parquet (F-019), quadrantes crescimento x inflacao",
            "v3_lente_de_regime": (
                f"regime_neighbors_v3.parquet (F-021, D-u), mahalanobis, k={K_VIZINHOS_PADRAO}, "
                "somente_passado=False, restrito_pos_2016=False"
            ),
            "v2_ausente": (
                "F-020 nao foi implementada: nenhuma linha com lente=V2. ciclo_selic sozinho e "
                "corte secundario (CA-083), nao lente."
            ),
        },
        "tabelas": {
            t.rotulo: {
                "arquivo": t.nome_arquivo,
                "materializacao": t.materializacao.value,
                "horizonte_v1": t.horizonte_v1.value,
                "horizonte_v3": None if t.horizonte_v3 is None else t.horizonte_v3.value,
                "linhas": int(len(tabelas[t.rotulo])),
                "lentes": sorted(str(x) for x in tabelas[t.rotulo]["lente"].unique()),
                "regimes": sorted(str(x) for x in tabelas[t.rotulo]["regime"].unique()),
                "por_que": t.por_que,
            }
            for t in TABELAS
        },
        "por_que_tres_tabelas": (
            "RegimeAssetMetricsSchema tem PK (lente, regime, asset_id), lente em {V1,V2,V3} e "
            "strict=True: nao ha coluna para materializacao (revised x asof) nem para horizonte "
            "(T0 x T+1), e as combinacoes colidiriam na PK. Acrescentar coluna e ALTERACAO de "
            "schema existente => pausa (AGENTS.md 9). Entao cada combinacao e uma tabela nomeada, "
            "validada pelo MESMO schema. Divida: 2 colunas em RegimeAssetMetricsSchema, classe C."
        ),
        "dicionario_de_metricas": DICIONARIO_DE_METRICAS,
        "anualizacao": {
            "fator": FATOR_ANUALIZACAO_SHARPE,
            "formula": "sharpe_tri * sqrt(4)",
            "aplicada_na_coluna": False,
            "declaracao_ca094": (
                "A coluna sharpe_tri e TRIMESTRAL. O relatorio publica sharpe_anualizado = "
                "sharpe_tri * sqrt(4) em cada celula legivel, e diz que anualizou. Indice NAO e "
                "implementavel sem friccao: carteira teorica e revisada e nao tem custo de "
                "replicacao (Anti-SPEC 10.2.11)."
            ),
            "desvio_vs_metodologia": (
                "metodologia 3 escreve (ret_medio - cdi_medio)/ret_desvio. Isso e subtracao de "
                "medias de retorno, o que a Anti-SPEC 10.2.13 proibe para excesso sobre CDI. Este "
                "modulo usa media(excesso por razao)/desvio(excesso por razao). A divergencia "
                "medida entre as duas formulas esta em `sharpe_duas_formulas`."
            ),
        },
        "drawdown": {
            "escolha": "pior_tri (minimo) + melhor_tri, com a data",
            "por_que": (
                "metodologia 3: max-drawdown so faz sentido em trimestres CONTIGUOS. Os 4 "
                "quadrantes da V1 sao fortemente nao contiguos e os vizinhos da V3 nao sao nem "
                "adjacentes por construcao (exclusao de T+-1/T+-2)."
            ),
            "contiguidade_medida": {
                regime: contiguidade(quarters) for regime, quarters in grupos_revised.items()
            },
            "contiguidade_v3": contiguidade([v.quarter for v in vizinhos]),
        },
        "n": {
            "limiares": {"alerta_n_baixo": N_ALERTA, "conclusao_suprimida": N_SUPRESSAO},
            "principal": _tabela_de_n(principal),
            "asof": _tabela_de_n(asof),
            "horizonte_cruzado": _tabela_de_n(cruzado),
        },
        "extremos_de_excesso": {
            "principal": _extremos_de_excesso(principal),
            "asof": _extremos_de_excesso(asof),
            "horizonte_cruzado": _extremos_de_excesso(cruzado),
        },
        "regime_atual": {
            "quarter": QUARTER_DO_COMITE,
            "v1_revised": {
                "regime": regime_comite_revised,
                "status": str(rotulo_revised["status_regime_v1"]),
                "motivo_indeterminado": (
                    None
                    if pd.isna(rotulo_revised["motivo_indeterminado"])
                    else str(rotulo_revised["motivo_indeterminado"])
                ),
                "declaracao": (
                    "INDETERMINADO: a V1 revised NAO TEM quadrante para 2026Q3 (D-m, ibcbr_gap "
                    "exige media movel de 20 trimestres e o IBC-Br dessaz. do trimestre corrente "
                    "nao fechou). Nenhum quadrante foi estimado no lugar (Anti-SPEC 10.1.1)."
                    if regime_comite_revised is None
                    else "classificado"
                ),
            },
            "v1_asof": {
                "regime": regime_comite_asof,
                "status": str(rotulo_asof["status_regime_v1"]),
                "ressalva_ca074": (
                    "A V1 troca de rotulo entre revised e asof em 33,33% dos trimestres "
                    "comparaveis (F-019), acima do limiar de 25% de CA-074: pelo criterio escrito "
                    "a V1 NAO e operacional na forma asof. Este ranking existe para o Comite ver "
                    "a alternativa, nao como a resposta."
                ),
            },
            "fallback_declarado": {
                "quarter": ultimo_classificado,
                "regime": regime_do_ultimo,
                "por_que": (
                    "ultimo trimestre COM quadrante na V1 revised. E referencia rotulada como "
                    "fallback, nunca 'o regime atual'."
                ),
            },
            "ranking_v1_fallback": ranking_do_regime(
                principal, lente=LENTE_V1, regime=regime_do_ultimo
            ),
            "ranking_v1_asof_2026Q3": (
                None
                if regime_comite_asof is None
                else ranking_do_regime(asof, lente=LENTE_V1, regime=regime_comite_asof)
            ),
        },
        "vizinhos_v3": {
            "quarter_ref": QUARTER_DO_COMITE,
            "k": K_VIZINHOS_PADRAO,
            "lista": [
                {
                    "rank": v.rank,
                    "quarter_neighbor": v.quarter,
                    "distancia": v.distancia,
                    "quarter_t_mais_1": quarter_do_horizonte(v.quarter, Horizonte.T_MAIS_1),
                }
                for v in vizinhos
            ],
            "ranking_t_mais_1_importado_de_f021": list(ranking_v3_t1),
            "ranking_t_mais_1_da_tabela": ranking_do_regime(
                principal, lente=LENTE_V3, regime=regime_v3
            ),
            "ranking_contemporaneo": ranking_do_regime(cruzado, lente=LENTE_V3, regime=regime_v3),
        },
        "concordancia_entre_lentes": concordancia_entre_lentes(rankings_para_concordancia),
        "concordancia_por_referencia": concordancia_por_referencia(
            neighbors=neighbors,
            regimes_v1=v1_revised,
            retornos=retornos,
            metricas_v1=principal,
        ),
        "indeterminados_excluidos": {
            "n_trimestres": len(indeterminados),
            "trimestres": indeterminados,
            "observacoes_de_retorno_fora": obs_fora,
            "consequencia": (
                "A crise de 2008 inteira (2006Q1..2009Q3) e 2026Q3 ficam fora das celulas da V1. "
                "Nao viram um 5o rotulo nem entram em outro quadrante. Vai a F-028."
            ),
        },
        "juncao_regimes": {
            "artefato": NOME_REGIMES_JUNTOS,
            "gravado": juncao.gravavel,
            "decisao": "D-r",
            "derivaveis": juncao.derivadas,
            "bloqueios": juncao.bloqueios,
            "trimestres_indeterminados": juncao.trimestres_indeterminados,
            "distribuicao_ciclo_selic": juncao.distribuicao_ciclo,
            "fonte_autoritativa_da_v1": "regimes_v1.parquet (RegimesV1Schema, F-019)",
            "o_que_destravaria": {
                "regime_v1": "tornar regime_v1 anulavel em RegimesSchema (classe C propria) OU "
                "resolver D-m (min_periods=8 ou outro eixo de crescimento)",
                "stress_flag": "F-026 implementar RF-039/CA-106 escolhendo, em ADR, qual "
                "inclinacao e em que amostra o desvio-padrao e estimado",
            },
        },
        "consistencia": {
            "recalculo_por_groupby_independente": _recalculo_independente(principal, bloco_longo),
        },
        "sharpe_duas_formulas": _sharpe_duas_formulas(v1_revised, retornos),
        "excesso_razao_vs_subtracao": _razao_vs_subtracao(v1_revised, retornos),
        "gate_de_publicacao": {
            "adr": "ADR-001",
            "status_do_adr": status_adr,
            "especificacao_congelada": congelada,
            "publicavel": congelada,
            "veredito": veredito_publicacao(congelada),
            "motivo": (
                "CA-090: enquanto ADR-001 estiver em Proposta, o cruzamento regime x retorno nao "
                "e publicavel. RegimeAssetMetricsSchema nao tem coluna para o gate (strict=True), "
                "entao ele e propagado aqui e no log — nunca numa coluna inventada."
            ),
            "linguagem": (
                "Saida DESCRITIVA (Anti-SPEC 10.2.10): 'neste regime o ativo rendeu X, n = Y'. "
                "Nunca 'vai render'. Com n < 5 o texto e 'indicacao preliminar, n = Y' (CA-109)."
            ),
        },
        **hashes,
    }


def _bloco_longo_v1(
    regimes_v1: pd.DataFrame, retornos: pd.DataFrame, *, horizonte: Horizonte
) -> pd.DataFrame:
    """A tabela longa `(regime, asset_id, quarter, retornos)` da V1 — base do recálculo cru."""
    grupos = trimestres_por_regime_v1(regimes_v1)
    mapa = {
        quarter_do_horizonte(q, horizonte): regime
        for regime, quarters in grupos.items()
        for q in quarters
    }
    fatia = retornos.loc[retornos["quarter"].isin(mapa)].copy()
    fatia["regime"] = fatia["quarter"].map(mapa)
    return fatia.loc[:, ["regime", "asset_id", "quarter", *COLUNAS_DE_RETORNO]]


def _sharpe_duas_formulas(regimes_v1: pd.DataFrame, retornos: pd.DataFrame) -> dict[str, Any]:
    """Quanto o Sharpe muda entre a fórmula desta tabela e a literal de `metodologia §3`."""
    bloco = _bloco_longo_v1(regimes_v1, retornos, horizonte=Horizonte.CONTEMPORANEO)
    cdi = bloco.loc[bloco["asset_id"] == "CDI", ["regime", "quarter", COLUNA_NOMINAL]].rename(
        columns={COLUNA_NOMINAL: "cdi"}
    )
    juntos = bloco.merge(cdi, on=["regime", "quarter"], how="left")
    linhas: list[dict[str, Any]] = []
    for (regime, asset_id), grupo in juntos.groupby(["regime", "asset_id"], sort=True):
        valido = grupo.dropna(subset=[COLUNA_NOMINAL, COLUNA_PRIMARIA, "cdi"])
        if len(valido) < MIN_OBS_DISPERSAO:
            continue
        desvio_nominal = float(valido[COLUNA_NOMINAL].std(ddof=1))
        deste_modulo = sharpe_trimestral(valido[COLUNA_PRIMARIA])
        literal = (
            None
            if desvio_nominal == 0.0
            else float((valido[COLUNA_NOMINAL].mean() - valido["cdi"].mean()) / desvio_nominal)
        )
        if deste_modulo is None or literal is None:
            continue
        linhas.append(
            {
                "regime": str(regime),
                "asset_id": str(asset_id),
                "sharpe_deste_modulo": deste_modulo,
                "sharpe_metodologia_literal": literal,
                "diferenca": deste_modulo - literal,
            }
        )
    diferencas = [abs(linha["diferenca"]) for linha in linhas]
    piores = sorted(linhas, key=lambda linha: -abs(linha["diferenca"]))[:5]
    return {
        "celulas_comparadas": len(linhas),
        "max_abs_diferenca": max(diferencas) if diferencas else None,
        "media_abs_diferenca": (sum(diferencas) / len(diferencas)) if diferencas else None,
        "piores_5": piores,
        "formula_deste_modulo": "media(ret_excesso_cdi)/desvio(ret_excesso_cdi)",
        "formula_metodologia": "(media(ret_tri) - media(cdi))/desvio(ret_tri)",
    }


def _razao_vs_subtracao(regimes_v1: pd.DataFrame, retornos: pd.DataFrame) -> dict[str, Any]:
    """A medida de CA-069 no dado real: média da razão × média da subtração, por célula.

    Não é teste sintético: é quanto a Anti-SPEC §10.2.13 vale em pp nesta tabela. Se um dia
    alguém trocar razão por subtração, este número no relatório é o que denuncia.
    """
    bloco = _bloco_longo_v1(regimes_v1, retornos, horizonte=Horizonte.CONTEMPORANEO)
    cdi = bloco.loc[bloco["asset_id"] == "CDI", ["regime", "quarter", COLUNA_NOMINAL]].rename(
        columns={COLUNA_NOMINAL: "cdi"}
    )
    juntos = bloco.merge(cdi, on=["regime", "quarter"], how="left").dropna(
        subset=[COLUNA_NOMINAL, COLUNA_PRIMARIA, "cdi"]
    )
    juntos["subtracao"] = juntos[COLUNA_NOMINAL] - juntos["cdi"]
    agregado = juntos.groupby(["regime", "asset_id"])[[COLUNA_PRIMARIA, "subtracao"]].mean()
    agregado["diferenca_pp"] = (agregado["subtracao"] - agregado[COLUNA_PRIMARIA]) * 100.0
    piores = agregado.reindex(
        agregado["diferenca_pp"].abs().sort_values(ascending=False).index
    ).head(5)
    return {
        "celulas_comparadas": int(len(agregado)),
        "max_abs_diferenca_pp": float(agregado["diferenca_pp"].abs().max()),
        "media_abs_diferenca_pp": float(agregado["diferenca_pp"].abs().mean()),
        "piores_5": [
            {
                "regime": str(indice[0]),
                "asset_id": str(indice[1]),
                "media_por_razao": float(linha[COLUNA_PRIMARIA]),
                "media_por_subtracao": float(linha["subtracao"]),
                "diferenca_pp": float(linha["diferenca_pp"]),
            }
            for indice, linha in piores.iterrows()
        ],
        "regra": "Anti-SPEC 10.2.13 / CA-069: excesso sobre CDI e SEMPRE razao.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResultadoMetricas:
    """O que `construir` devolve — para o teste, para F-023/F-024 e para o relatório."""

    tabelas: dict[str, pd.DataFrame]
    relatorio: dict[str, Any]
    juncao: JuncaoRegimes
    vizinhos: list[Vizinho]
    caminhos: dict[str, Path]
    caminho_relatorio: Path | None

    @property
    def principal(self) -> pd.DataFrame:
        """A tabela que F-023 e F-024 leem."""
        return self.tabelas[TABELA_PRINCIPAL.rotulo]


def construir(*, raiz: Path | None = None, gravar: bool = True) -> ResultadoMetricas:
    """Reconstrói as métricas de ponta a ponta. Sem rede, sem relógio, sem estado.

    `gravar=False` existe para o teste rodar o build real sobre o acervo em disco sem tocar o
    disco de volta.
    """
    congelada = especificacao_esta_congelada(raiz=raiz)
    status = status_adr_001(raiz=raiz)
    if not congelada:
        _log.warning(
            "%s: ADR-001 esta em '%s' — nenhum numero de regime x retorno desta feature e "
            "publicavel (CA-090, AGENTS.md 9/14)",
            veredito_publicacao(congelada),
            status,
        )

    regimes = {
        m.value: ler_regimes_v1(materializacao=m, raiz=raiz)
        for m in (Materializacao.REVISED, Materializacao.ASOF)
    }
    for quadro in regimes.values():
        conferir_gate(quadro, congelada=congelada)

    retornos = ler_retornos(raiz=raiz)
    neighbors = ler_neighbors_v3(raiz=raiz)
    vizinhos = vizinhos_da_lente_canonica(neighbors)

    fonte_versao = versao_build()

    tabelas = {
        t.rotulo: montar_tabela(
            t,
            regimes_v1=regimes[t.materializacao.value],
            retornos=retornos,
            vizinhos=vizinhos,
            fonte_versao=fonte_versao,
        )
        for t in TABELAS
    }

    juncao = montar_regimes(
        regimes_v1=regimes[Materializacao.REVISED.value],
        macro=ler_macro(materializacao=Materializacao.REVISED, raiz=raiz),
    )
    if juncao.gravavel:  # pragma: no cover - hoje sempre bloqueada (stress_flag e D-m)
        _log.info("juncao de D-r completa: %s pode ser gravada", NOME_REGIMES_JUNTOS)
    else:
        _log.warning(
            "%s NAO gravado (D-r): %d bloqueio(s) — %s",
            NOME_REGIMES_JUNTOS,
            len(juncao.bloqueios),
            " | ".join(b.split(".")[0] for b in juncao.bloqueios),
        )

    observadas_t1 = observacoes_dos_vizinhos(vizinhos, retornos, horizonte=Horizonte.T_MAIS_1)
    ranking_v3_t1 = ranking_de_ativos(observadas_t1, coluna=COLUNA_PRIMARIA)

    caminhos: dict[str, Path] = {}
    corpos: dict[str, bytes] = {}
    for t in TABELAS:
        quadro = tabelas[t.rotulo]
        if gravar:
            alvo = caminho_canonical(t.nome_arquivo, raiz=raiz)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            quadro.to_parquet(alvo, index=False)
            caminhos[t.rotulo] = alvo
            corpos[t.rotulo] = alvo.read_bytes()
        else:
            corpos[t.rotulo] = quadro.to_parquet(index=False)

    relatorio = montar_relatorio(
        tabelas=tabelas,
        regimes=regimes,
        retornos=retornos,
        neighbors=neighbors,
        vizinhos=vizinhos,
        juncao=juncao,
        congelada=congelada,
        status_adr=status,
        ranking_v3_t1=ranking_v3_t1,
        hashes={
            "versao_build": fonte_versao,
            "fonte_versao": fonte_versao,
            "hashes": {
                t.rotulo: {
                    "arquivo": t.nome_arquivo,
                    "sha256": sha256_de(corpos[t.rotulo]),
                    "bytes": len(corpos[t.rotulo]),
                }
                for t in TABELAS
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
            "gravadas %d tabelas (%s linhas) + %s",
            len(TABELAS),
            ", ".join(f"{t.rotulo}={len(tabelas[t.rotulo])}" for t in TABELAS),
            NOME_RELATORIO,
        )

    return ResultadoMetricas(
        tabelas=tabelas,
        relatorio=relatorio,
        juncao=juncao,
        vizinhos=list(vizinhos),
        caminhos=caminhos,
        caminho_relatorio=caminho_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.metricas_regime",
        description=(
            "Materializa as 3 tabelas regime_asset_metrics*.parquet + relatorio_metricas.json a "
            "partir de regimes_v1{,_asof} (F-019), regime_neighbors_v3 (F-021) e "
            "asset_returns_quarterly (F-017). Nunca toca a rede. Enquanto ADR-001 estiver em "
            "Proposta, nenhum numero daqui e publicavel (CA-090)."
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
    gate = resultado.relatorio["gate_de_publicacao"]
    for rotulo, bloco in resultado.relatorio["hashes"].items():
        _log.info(
            "%s: %d linhas, sha256=%s...",
            bloco["arquivo"],
            len(resultado.tabelas[rotulo]),
            bloco["sha256"][:12],
        )
    _log.info("gate de publicacao: %s", gate["veredito"])
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script
    sys.exit(main())
