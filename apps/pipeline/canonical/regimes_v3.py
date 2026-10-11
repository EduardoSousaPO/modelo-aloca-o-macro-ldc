"""F-021 — Regimes V3: vizinhos mais próximos ("momentos semelhantes") + retorno em T+1.

**Classe C.** É a lente que responde **literalmente** ao e-mail do Alexandre: "verificando como
cada classe de ativo e até setores performaram em momentos semelhantes". Não binariza nada, não
treina nada, tem um só hiperparâmetro (`k`) e é auditável na planilha.

## O que o módulo faz, e só isto

1. **Monta o vetor de features por trimestre** — 5 features (ver `FEATURES_USADAS`), cada uma com
   origem declarada. `inclinacao_real_5a_3a` **não é coluna** de `macro_quarterly` (**D-n**): sai
   de `raw_series` via `alinhar_series` de F-014, a mesma régua de todo o canônico.
2. **Padroniza** em z-score, em duas janelas que nunca se misturam: `amostra_completa` (versão
   **descritiva**, metodologia §2 princípio 4 e `TODO.md` de F-021) e `expanding_ate_T` (média e
   desvio **só até T**, metodologia §5.1 — a variante sem nenhum caminho de look-ahead).
3. **Estima a covariância com shrinkage de Ledoit-Wolf** (CA-084), implementado **à mão em numpy**
   porque `scipy`/`scikit-learn` **não estão no ambiente** e dependência nova exigiria ADR
   (`AGENTS.md §12`, Anti-SPEC §10.4.25) — ver `ledoit_wolf`.
4. **Calcula a distância** de cada `T` aos candidatos: **Mahalanobis** (principal) e **Euclidiana**
   em paralelo, como sanity check. Exclui `T` e os trimestres a `<= 2` trimestres de distância
   (`N_TRIMESTRES_EXCLUIDOS_VIZINHANCA`, CA-085) e desempata pelo **mais recente**.
5. **Grava os k vizinhos** (k = 5, 8, 12; CA-087) com `distancia`, rótulo V1 de cada (CA-101) e o
   trimestre **seguinte** a cada vizinho (CA-102) — e, no relatório, o retorno de cada ativo
   naquele `T+1`, nunca no próprio vizinho.

## O que ele **não** faz

- **nenhuma previsão.** O output é descritivo: "em momentos parecidos, o ativo X rendeu Y em
  média, com n = 8". Nunca "vai render" (Anti-SPEC §10.2.10).
- **nenhuma escolha de `k` pelo resultado.** `k = 8` vem do contrato (`K_VIZINHOS_PADRAO`, fixado
  antes de olhar retorno) e 5/12 saem como sensibilidade (Anti-SPEC §10.2.9).
- **nenhuma feature inventada.** Feature sem fonte é **cortada e declarada**, nunca preenchida
  (CA-086 + Anti-SPEC §10.1.1). Trimestre sem o vetor completo fica **fora** da lente, nomeado no
  relatório — nunca entra com uma feature imputada.
- **nenhuma publicação.** `ADR-001` está em **Proposta**, então `especificacao_congelada = False`
  e o número **não vai ao Comitê** sem o fluxo de classe D (CA-090, `AGENTS.md §14`).

## Os dois artefatos de vizinhos, e por que são dois

| Artefato | Schema | Conjunto de vizinhos |
|---|---|---|
| `regime_neighbors.parquet` | `RegimeNeighborsSchema` (CA-089) | só vizinho **com** V1 |
| `regime_neighbors_v3.parquet` | `RegimeNeighborsV3Schema` | **completo** — o entregável |

`RegimeNeighborsSchema.regime_v1_neighbor` é `nullable=False`, e por **D-m** 16 trimestres não têm
`ibcbr_gap`, logo não têm quadrante V1. Medido na rodada real: **4 dos 8** vizinhos de `2026Q3`
são de 2006-2007, sem V1 — a tabela de contrato tem de excluí-los, e isso **muda a resposta**. Em
vez de esconder a troca, os dois conjuntos são materializados e a divergência vai no relatório
(`divergencia_contrato_vs_completo`). A saída permanente é tornar a coluna anulável, que é
**alteração** de schema, logo feature classe C própria — ver `packages/shared/schemas/regimes.py`.

**Sem rede, sempre.** Entradas: `macro_quarterly.parquet` (F-015), `raw_series.parquet` +
`series_catalog.parquet` (F-013), `asset_returns_quarterly.parquet` (F-017),
`data/processed/calendario/` (F-008) e, **se existir**, `regimes_v1.parquet` (F-019), usado só
para **conferir** o rótulo de anotação calculado aqui.

**Idempotente por construção:** nada lê o relógio; o relatório carrega `versao_build` (`sha256` do
conjunto de módulos), não hora de geração.

Referências: SPEC RF-029 (CA-084..087), RF-030 (CA-088/089), RF-031 (CA-090/091), RF-036
(CA-101/102) · ADR-001 (Proposta) · `docs/research/metodologia-regimes-macro.md §2 (V3)`, §3, §5.1,
§5.3, §6.4 · `docs/contracts/CONTRACTS.md §5` · `docs/wiki/context/F-021.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from apps.pipeline.canonical.alinhamento import (
    alinhar_series,
    grade_de_trimestres,
    inicio_observado_por_serie,
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
from apps.pipeline.canonical.macro_quarterly import NOME_MACRO, fatiar_curva
from apps.pipeline.canonical.retornos import NOME_RETORNOS
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel
from apps.pipeline.common.io_layers import (
    caminho_canonical,
    garantir_diretorio,
    raiz_repo,
    sha256_de,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from apps.pipeline.extract.calendario_anbima import Calendario
from packages.shared.schemas import (
    FEATURES_V3,
    AssetReturnsQuarterlySchema,
    MacroQuarterlySchema,
    RawSeriesSchema,
    SeriesCatalogMaterializedSchema,
    quarters_da_janela,
)
from packages.shared.schemas.regimes import (
    JANELA_AMOSTRA_COMPLETA,
    JANELA_EXPANDING,
    K_VIZINHOS_PADRAO,
    K_VIZINHOS_SENSIBILIDADE,
    N_ALERTA,
    N_SUPRESSAO,
    N_TRIMESTRES_EXCLUIDOS_VIZINHANCA,
    SEPARADOR_DE_FEATURES,
    SHRINKAGE_LEDOIT_WOLF,
    SHRINKAGE_NAO_SE_APLICA,
    VERSAO_ESPECIFICACAO_V3,
    MetricaDistancia,
    RegimeNeighborsSchema,
    RegimeNeighborsV3Schema,
    RegimeV1,
    StatusRegimeV1,
    indice_do_quarter,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Iterable, Mapping, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes
# ─────────────────────────────────────────────────────────────────────────────

NOME_NEIGHBORS = "regime_neighbors.parquet"
NOME_NEIGHBORS_V3 = "regime_neighbors_v3.parquet"
NOME_RELATORIO = "relatorio_regimes_v3.json"
NOME_REGIMES_V1 = "regimes_v1.parquet"

#: Os módulos que determinam o conteúdo da V3, **nesta ordem** — base de `versao_build`. Mesmo
#: critério de F-014/F-015 (P1-1 do QA da Onda 2): este módulo, o contrato das duas tabelas de
#: vizinhos, a régua temporal de onde sai a inclinação, o produtor das features, o produtor dos
#: retornos de T+1 e o calendário que decide todo `quarter_end`. Mudar qualquer um muda o Parquet.
MODULOS_DA_V3: tuple[str, ...] = (
    "apps.pipeline.canonical.regimes_v3",
    "packages.shared.schemas.regimes",
    "apps.pipeline.canonical.macro_quarterly",
    "apps.pipeline.canonical.retornos",
    "apps.pipeline.canonical.alinhamento",
    "packages.shared.schemas.macro_quarterly",
    "packages.shared.schemas.asset_returns_quarterly",
    "apps.pipeline.extract.calendario_anbima",
)

ESPECIFICACAO_CONGELADA = False
"""CA-090: `ADR-001` está em **Proposta** — o número não é publicável (gate da classe D).

Não é configurável por parâmetro de propósito: virar `True` é **editar o ADR** e este arquivo no
mesmo commit, o que deixa rastro no `fonte_versao`.
"""

ADR_DA_ESPECIFICACAO = "ADR-001"
STATUS_DO_ADR = "Proposta"

LAG_ADJUSTED = False
"""Esta é a lente sobre a materialização **`revised`** de F-015. A `asof` é F-018."""

QUARTER_DO_COMITE = "2026Q3"
"""O trimestre de referência do entregável de 2026-10-14 — o último da janela de 83."""

PRIMEIRO_TRIMESTRE_POS_2016 = "2017Q1"
"""Variante `V3-pos2016` (metodologia §5.3): busca restrita a `>= 1T2017`.

Controla a quebra estrutural da Selic (19% em 2006 → 2% em 2020 → 14% em 2026) e dos arcabouços
(teto de gastos 2016, autonomia do BCB 2021, novo arcabouço 2023). A restrição é da **busca**:
a padronização e a covariância continuam estimadas na janela declarada em `janela_padronizacao`.
"""

MIN_OBS_PADRONIZACAO_EXPANDING = 20
"""Mínimo de trimestres até `T` para a variante `expanding_ate_T` existir.

**Escolha deste módulo, declarada:** 20 trimestres é a mesma janela que ADR-001 §4 usa para a
tendência do IBC-Br — "história suficiente" já tem precedente no projeto — e dá 4 observações por
feature. Abaixo disso a média, o desvio **e** a covariância são estimados em tão pouca amostra que
a distância deixa de medir semelhança e passa a medir o estimador. Referência sem isso não produz
linha, e o relatório nomeia quais ficaram de fora.
"""

ORIGEM_MACRO = "macro_quarterly"
ORIGEM_RAW_ALINHADA = "raw_series+alinhar_series"


@dataclass(frozen=True)
class Feature:
    """Uma feature da V3: de onde sai, o que é, e — se for o caso — o que ela substitui."""

    nome: str
    origem: str
    chave: str
    descricao: str
    unidade: str
    substitui: str | None = None
    motivo_da_substituicao: str | None = None


#: As **5** features da V3 desta rodada. `n_features = 5`, **declarado** no dado
#: (`features_usadas`, `n_features`), no `fonte_versao` e no relatório — CA-086.
#:
#: O mapa contra as 6 de `FEATURES_V3`/metodologia §2, uma linha por decisão:
#:
#: | Contrato | Aqui | Por quê |
#: |---|---|---|
#: | `z_ibcbr_gap` | `z_crescimento_esperado` | `ibcbr_gap` é **nulo em 2026Q3** (D-m), e
#:   2026Q3 é a referência do Comitê — ver `motivo_da_substituicao` da feature |
#: | `z_ipca_desvio_meta` | `z_ipca_12m_delta` | `ipca_meta` é 100% nula (**G-02**); ADR-001 §4
#:   já decidiu **aceleração** como eixo de inflação (D3) |
#: | `z_juro_real_exante` | igual | — |
#: | `z_inclinacao` | `z_inclinacao_real_5a_3a` | **D-i**: a 5a−3a é a principal (79/83 =
#:   95,2%) contra 50/83 da 5a−1a; **D-n**: sai de `raw_series`, não de coluna |
#: | `z_usdbrl_var_12m` | igual | — |
#: | `z_termos_troca_yoy` | **cortada** | 100% nula, sem fonte (IC-Br é F-037); preencher
#:   seria dado inventado |
FEATURES_USADAS: tuple[Feature, ...] = (
    Feature(
        nome="z_crescimento_esperado",
        origem=ORIGEM_MACRO,
        chave="focus_pib_ano",
        descricao=(
            "PIB do ano de T na mediana do Focus, coleta do início de T (F-015 §3.5) — o eixo de "
            "crescimento desta lente"
        ),
        unidade="%",
        substitui="z_ibcbr_gap",
        motivo_da_substituicao=(
            "ibcbr_gap e ibcbr_yoy sao nulos em 2026Q3 (IBC-Br vai ate jul/2026 e a lacuna "
            "passa de 5 d.u.), e 2026Q3 e o trimestre de referencia do Comite: com o gap como "
            "feature, a V3 nao tem vetor para a pergunta que foi feita. Alem disso o gap e nulo "
            "em 2006Q1..2009Q3 (D-m), o que tiraria a crise de 2008 do conjunto de vizinhos. "
            "focus_pib_ano e dado real, 83/83, sem defasagem de divulgacao (metodologia 5.1: "
            "'Focus e o dado limpo') e e o eixo de crescimento da V1b na metodologia 2."
        ),
    ),
    Feature(
        nome="z_ipca_12m_delta",
        origem=ORIGEM_MACRO,
        chave="ipca_12m_delta",
        descricao="aceleracao do IPCA 12m: `ipca_12m[T] - ipca_12m[T-1]` (ADR-001 §4, D3)",
        unidade="pp",
        substitui="z_ipca_desvio_meta",
        motivo_da_substituicao=(
            "ipca_meta e ipca_desvio_meta sao 100% nulas no canonico (G-02, serie de metas do "
            "CMN a confirmar). ADR-001 §4 ja decidiu aceleracao como eixo de inflacao."
        ),
    ),
    Feature(
        nome="z_juro_real_exante",
        origem=ORIGEM_MACRO,
        chave="juro_real_exante",
        descricao="Fisher por razao: pre de 1 ano contra o Focus de IPCA 12m (F-015)",
        unidade="%a.a.",
    ),
    Feature(
        nome="z_inclinacao_real_5a_3a",
        origem=ORIGEM_RAW_ALINHADA,
        chave="INCLINACAO_REAL_5A_3A",
        descricao="inclinacao real 5a menos 3a, vertices interpolados do Tesouro Direto (F-016)",
        unidade="pp",
        substitui="z_inclinacao",
        motivo_da_substituicao=(
            "D-i: a inclinacao principal e a 5a-3a (79/83 = 95,2% de cobertura) e nao a 5a-1a "
            "(50/83 = 60,2%). D-n: a 5a-3a nao tem coluna em MacroQuarterlySchema, e lida de "
            "raw_series com alinhar_series (a mesma regua de F-014)."
        ),
    ),
    Feature(
        nome="z_usdbrl_var_12m",
        origem=ORIGEM_MACRO,
        chave="usdbrl_var_12m",
        descricao="PTAX de venda, variacao de 12 meses por razao (CA-044)",
        unidade="%",
    ),
)

#: O que ficou **fora** — nomeado, porque "não está na lente" tem de ter causa, igual a célula
#: nula (F-017 §3). Nenhuma delas foi substituída por valor plausível.
FEATURES_DESCARTADAS: tuple[tuple[str, str], ...] = (
    (
        "z_termos_troca_yoy",
        "termos_troca_yoy e 100% nula em macro_quarterly: nenhum indice de termos de troca foi "
        "extraido. O proxy IC-Br do BCB (SGS 27574/27575) e escopo de F-037. Preencher seria "
        "dado inventado (Anti-SPEC 10.1.1).",
    ),
)

MOTIVO_SEM_VETOR = "feature_ausente_no_trimestre"
MOTIVO_POOL_VAZIO = "nenhum_candidato_apos_exclusao"
MOTIVO_HISTORIA_CURTA = "menos_de_20_trimestres_ate_T"


class FeaturesInsuficientes(ErroCanonico):
    """Menos de 3 features disponíveis — piso do contrato (`n_features >= 3`).

    Abaixo de 3 a V3 não é "momentos semelhantes", é ruído: o caminho é `BLOQUEADO`, nunca um
    número com 2 features (comentário do `n_features` em `RegimeNeighborsSchema`).
    """


class CovarianciaSingular(ErroCanonico):
    """A covariância encolhida ainda não é inversível — a Mahalanobis não existe."""


# ─────────────────────────────────────────────────────────────────────────────
# Grade de trimestres (aritmética de trimestre, sem data)
# ─────────────────────────────────────────────────────────────────────────────


def janela() -> tuple[str, ...]:
    """Os 83 trimestres do contrato, em ordem. É a única grade desta feature."""
    return tuple(quarters_da_janela())


def quarter_seguinte(quarter: str) -> str | None:
    """`T` → `T+1`, ou `None` se `T+1` está fora da janela de 83 (CA-102).

    É a função que materializa "o trimestre **seguinte** ao vizinho". `None` não é falha: o
    último trimestre da janela não tem seguinte, e a linha carrega `quarter_t_mais_1` nulo em vez
    de apontar para um trimestre que não existe.
    """
    grade = janela()
    posicao = grade.index(quarter) if quarter in grade else -1
    if posicao < 0 or posicao + 1 >= len(grade):
        return None
    return grade[posicao + 1]


def distancia_em_trimestres(a: str, b: str) -> int:
    """Quantos trimestres separam `a` de `b`, em valor absoluto."""
    return abs(indice_do_quarter(a) - indice_do_quarter(b))


# ─────────────────────────────────────────────────────────────────────────────
# Álgebra: padronização, shrinkage, distância
# ─────────────────────────────────────────────────────────────────────────────


def padronizar(
    matriz: pd.DataFrame, *, ate: str | None = None
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """z-score de cada coluna, com média e desvio estimados **até `ate`** (ou na amostra toda).

    `ate = None` é a versão **descritiva** (`JANELA_AMOSTRA_COMPLETA`): é o que o Comitê pede —
    "onde estamos no histórico" — e é explicitamente sancionada pela metodologia §2 (princípio 4)
    e pelo escopo de F-021 no `TODO.md`.

    `ate = "2019Q4"` usa **só** as linhas até `2019Q4` para estimar média e desvio, e aplica esses
    parâmetros a **todas** as linhas. É a janela `expanding_ate_T` (metodologia §5.1): nenhum
    número posterior a `T` entra na padronização de `T`. Mexer numa linha futura **não** muda o
    z-score de `T` — e isso é teste, não promessa.

    Desvio **amostral** (`ddof=1`). Coluna com desvio zero levanta: z-score de constante é 0/0, e
    uma feature constante não separa momento nenhum.
    """
    base = matriz if ate is None else matriz.loc[[q for q in matriz.index if q <= ate]]
    if len(base) < 2:
        msg = f"padronizacao com {len(base)} observacoes: z-score exige pelo menos 2"
        raise FeaturesInsuficientes(msg)
    media = base.mean()
    desvio = base.std(ddof=1)
    zeradas = [c for c in matriz.columns if not np.isfinite(desvio[c]) or desvio[c] == 0]
    if zeradas:
        msg = f"desvio-padrao zero ou nao finito em {zeradas}: feature constante nao padroniza"
        raise FeaturesInsuficientes(msg)
    parametros = {
        str(c): {"media": float(media[c]), "desvio": float(desvio[c]), "n": int(len(base))}
        for c in matriz.columns
    }
    return (matriz - media) / desvio, parametros


@dataclass(frozen=True)
class Shrinkage:
    """O resultado do encolhimento: a matriz usada, a intensidade e os números que a justificam."""

    sigma: np.ndarray
    intensidade: float
    n: int
    p: int
    cond_amostral: float
    cond_encolhida: float


def covariancia_amostral(x: np.ndarray) -> np.ndarray:
    """A covariância amostral **crua** (`ddof=0`, centrada na própria média).

    Existe para ser o **negativo** de CA-084: o teste a usa para mostrar que ela é instável em
    83×5 e que o módulo de produção não a usa em lugar nenhum da Mahalanobis.
    """
    centrada = x - x.mean(axis=0)
    return centrada.T @ centrada / x.shape[0]


def ledoit_wolf(x: np.ndarray) -> Shrinkage:
    """Covariância com shrinkage de **Ledoit-Wolf** (2004), em numpy puro.

    `Sigma = rho * mu * I + (1 - rho) * S`, com `S` a covariância amostral, `mu = tr(S)/p` (o
    alvo é a esfera de mesma variância média) e

        rho = min(b2, d2) / d2,
        d2  = ||S - mu*I||_F^2,
        b2  = (1/n^2) * sum_k ||x_k x_k' - S||_F^2.

    A identidade que faz `b2` caber em duas linhas de numpy, sem laço sobre `k`:

        sum_k ||x_k x_k' - S||_F^2 = sum_k |x_k|^4 - n * ||S||_F^2,

    porque `sum_k x_k' S x_k = n * tr(S S) = n * ||S||_F^2`. Há teste que confere as duas formas
    contra o laço explícito (`assert` com `1e-12`).

    **Por que à mão.** CA-084 exige shrinkage, e `scipy`/`scikit-learn` **não estão** no `.venv`
    (`uv run python -c "import sklearn"` falha). Instalar é **dependência nova** → ADR
    (`AGENTS.md §12`, Anti-SPEC §10.4.25) → pausa, e a entrega é 2026-10-14. O estimador original
    tem ~30 linhas e é fechado: implementado, testado contra as propriedades que o definem
    (`rho` em [0,1]; matriz singular vira inversível; `rho = 0` quando `S` já é isotrópica) e
    registrado aqui como decisão.

    `rho` é **medido, nunca escolhido**: não há parâmetro de intensidade na assinatura.
    """
    if x.ndim != 2 or x.shape[0] < 2:
        msg = f"shrinkage exige matriz (n, p) com n >= 2; recebi {x.shape}"
        raise FeaturesInsuficientes(msg)
    n, p = x.shape
    centrada = x - x.mean(axis=0)
    amostral = centrada.T @ centrada / n
    mu = float(np.trace(amostral)) / p
    d2 = float(((amostral - mu * np.eye(p)) ** 2).sum())
    quartas = ((centrada**2).sum(axis=1)) ** 2
    b2 = float(quartas.sum()) / n**2 - float((amostral**2).sum()) / n
    b2 = min(max(b2, 0.0), d2)
    intensidade = 0.0 if d2 == 0.0 else b2 / d2
    sigma = intensidade * mu * np.eye(p) + (1.0 - intensidade) * amostral
    return Shrinkage(
        sigma=sigma,
        intensidade=float(intensidade),
        n=int(n),
        p=int(p),
        cond_amostral=float(np.linalg.cond(amostral)),
        cond_encolhida=float(np.linalg.cond(sigma)),
    )


def inverter(sigma: np.ndarray) -> np.ndarray:
    """Inversa de uma covariância, por Cholesky — e erro nomeado se ela não for inversível."""
    try:
        fator = np.linalg.cholesky(sigma)
    except np.linalg.LinAlgError as erro:  # pragma: no cover - só com shrinkage degenerado
        msg = f"covariancia nao e definida positiva (cond = {np.linalg.cond(sigma):.3e})"
        raise CovarianciaSingular(msg) from erro
    identidade = np.eye(sigma.shape[0])
    inversa_fator = np.linalg.solve(fator, identidade)
    return inversa_fator.T @ inversa_fator


def distancias_mahalanobis(
    referencia: np.ndarray, candidatos: np.ndarray, inversa: np.ndarray
) -> np.ndarray:
    """`sqrt((u - v)' Sigma^-1 (u - v))` de `referencia` a cada linha de `candidatos`.

    Com `Sigma = I` a função **é** a Euclidiana — e isso é teste, não observação: é o que prova
    que a diferença entre as duas métricas publicadas está na covariância e não no código.
    """
    delta = candidatos - referencia
    formas = np.einsum("ij,jk,ik->i", delta, inversa, delta)
    return np.sqrt(np.maximum(formas, 0.0))


def distancias_euclidianas(referencia: np.ndarray, candidatos: np.ndarray) -> np.ndarray:
    """Euclidiana no espaço dos z-scores — o sanity check que a metodologia §2 pede em paralelo."""
    return distancias_mahalanobis(referencia, candidatos, np.eye(candidatos.shape[1]))


@dataclass(frozen=True)
class Vizinho:
    """Um vizinho da V3: quem, a que distância, em que posição."""

    rank: int
    quarter: str
    distancia: float


def vizinhos_mais_proximos(
    quarter_ref: str,
    candidatos: Sequence[str],
    distancias: np.ndarray,
    *,
    k: int,
    excluir_a_menos_de: int = N_TRIMESTRES_EXCLUIDOS_VIZINHANCA,
) -> tuple[Vizinho, ...]:
    """Os `k` candidatos mais próximos, com as duas regras de CA-085.

    1. **Exclusão de vizinhança temporal:** sai todo candidato a `<= excluir_a_menos_de`
       trimestres da referência — o próprio `T`, `T±1` e `T±2` com o padrão do contrato
       (`N_TRIMESTRES_EXCLUIDOS_VIZINHANCA = 2`). A exclusão é **simétrica** porque a
       autocorrelação é: na variante descritiva o candidato pode estar no futuro, e `T+1` é tão
       trivialmente parecido com `T` quanto `T-1`. Na variante `somente_passado` o conjunto já é
       `T' < T`, então a regra se reduz exatamente ao enunciado de CA-085 ("os 2 trimestres
       imediatamente anteriores").
    2. **Desempate pelo mais recente:** distâncias iguais (ao bit) ordenam pelo trimestre de
       índice **maior**. É determinístico e não depende da ordem de entrada.

    Devolve menos de `k` elementos quando o conjunto é menor — e é o chamador que **declara**
    `n_vizinhos` na linha, nunca preenche o que falta.
    """
    if len(candidatos) != len(distancias):
        msg = f"{len(candidatos)} candidatos para {len(distancias)} distancias"
        raise FeaturesInsuficientes(msg)
    elegiveis = [
        (float(d), -indice_do_quarter(q), q)
        for q, d in zip(candidatos, distancias, strict=True)
        if distancia_em_trimestres(q, quarter_ref) > excluir_a_menos_de
    ]
    elegiveis.sort()
    return tuple(
        Vizinho(rank=i + 1, quarter=q, distancia=d)
        for i, (d, _, q) in enumerate(elegiveis[: max(int(k), 0)])
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rótulo V1 de anotação (CA-101) — F-019 é o dono
# ─────────────────────────────────────────────────────────────────────────────

_ROTULOS_V1: dict[tuple[bool, bool], str] = {
    (True, False): RegimeV1.RECUPERACAO.value,
    (True, True): RegimeV1.EXPANSAO_INFL.value,
    (False, True): RegimeV1.ESTAGFLACAO.value,
    (False, False): RegimeV1.DESACELERACAO.value,
}


def rotulos_v1_de_anotacao(macro: pd.DataFrame) -> pd.Series:
    """O quadrante V1 por trimestre, **para anotar** o vizinho (CA-101). `None` = sem quadrante.

    Reimplementa ADR-001 §4/§5 em 15 linhas — `g_T = ibcbr_gap`, `pi_T = ipca_12m_delta`, empate
    exato herda o sinal do trimestre anterior — porque **F-019 ainda não existe em disco** e a
    V3 não pode esperar por ela para rodar. Três salvaguardas contra isso virar uma segunda
    verdade:

    1. **F-019 é o dono.** Quando `regimes_v1.parquet` existir, `conferir_v1_contra_f019` compara
       os 83 rótulos e o relatório publica as divergências (esperado: 0). Se divergir, é a tabela
       de F-019 que manda e esta função é o bug.
    2. **Nulo é nulo.** `ibcbr_gap` nulo (16 trimestres, **D-m**) → `None`, nunca um quadrante
       inventado. O vizinho sai com `status_regime_v1_neighbor = INDETERMINADO`.
    3. **Não entra na distância.** O rótulo é anotação; nenhuma feature da V3 o usa.
    """
    anterior: tuple[bool, bool] | None = None
    rotulos: dict[str, str | None] = {}
    for quarter in macro.index:
        g = macro.loc[quarter, "ibcbr_gap"]
        pi = macro.loc[quarter, "ipca_12m_delta"]
        if pd.isna(g) or pd.isna(pi):
            rotulos[str(quarter)] = None
            continue
        cresce = bool(g > 0) if float(g) != 0.0 else (anterior[0] if anterior else None)
        acelera = bool(pi > 0) if float(pi) != 0.0 else (anterior[1] if anterior else None)
        if cresce is None or acelera is None:
            rotulos[str(quarter)] = None
            continue
        rotulos[str(quarter)] = _ROTULOS_V1[(cresce, acelera)]
        anterior = (cresce, acelera)
    return pd.Series(rotulos, dtype="object")


def conferir_v1_contra_f019(rotulos: pd.Series, *, raiz: Path | None = None) -> dict[str, Any]:
    """Compara o rótulo de anotação com `regimes_v1.parquet` (F-019), se ele existir."""
    alvo = caminho_canonical(NOME_REGIMES_V1, raiz=raiz)
    if not alvo.is_file():
        return {
            "conferido": False,
            "motivo": f"{NOME_REGIMES_V1} nao existe: F-019 ainda nao rodou nesta arvore",
            "divergencias": None,
        }
    tabela = pd.read_parquet(alvo).set_index("quarter")

    # `NaN` e `None` dizem a **mesma** coisa aqui ("sem quadrante") e não são iguais em Python:
    # `float("nan") or None` é `nan`, porque `nan` é *truthy*. Normalizar os dois lados para
    # `None` antes de comparar é o que faz esta conferência medir divergência de **rótulo** em
    # vez de divergência de representação de ausência.
    def _ou_none(valor: Any) -> str | None:
        return None if valor is None or pd.isna(valor) else str(valor)

    deles = tabela["regime_v1"]
    comuns = [q for q in rotulos.index if q in deles.index]
    divergentes = [
        {"quarter": q, "aqui": _ou_none(rotulos[q]), "f019": _ou_none(deles[q])}
        for q in comuns
        if _ou_none(rotulos[q]) != _ou_none(deles[q])
    ]
    return {
        "conferido": True,
        "trimestres_comparados": len(comuns),
        "divergencias": len(divergentes),
        "detalhe": divergentes[:10],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entradas
# ─────────────────────────────────────────────────────────────────────────────


def _ler_canonical(nome: str, *, schema: Any, raiz: Path | None) -> pd.DataFrame:
    """Lê um Parquet de `data/canonical/` e **valida** com o schema dele antes de usar."""
    alvo = caminho_canonical(nome, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. Rode os builds da camada "
            f"canônica (F-013 → F-014 → F-015 → F-017) antes."
        )
        raise FonteIndisponivel(msg)
    return schema.validate(pd.read_parquet(alvo), lazy=True)


def inclinacao_real_5a_3a(
    raw: pd.DataFrame,
    catalogo: pd.DataFrame,
    *,
    calendario: Calendario,
    fonte_versao: str,
) -> pd.Series:
    """A inclinação real 5a−3a por trimestre, lida de `raw_series` pela régua de F-014.

    **D-n:** a série **não tem coluna** em `MacroQuarterlySchema` (acrescentar é alteração de
    schema, logo feature classe C própria), e **D-i** diz que ela, e não a 5a−1a, é a inclinação
    principal: 79/83 contra 50/83 de cobertura. Então ela sai de `raw_series` por
    `alinhar_series` — a **mesma** função que F-015 usa para a curva, com o mesmo calendário e o
    mesmo `inicio_por_serie`, de modo que o valor é idêntico ao que a coluna teria se existisse.
    """
    curva = fatiar_curva(raw)
    if curva.empty:
        msg = (
            "BLOQUEADO — FONTE INDISPONÍVEL: nenhuma série de curva em raw_series; a feature de "
            "inclinação da V3 não tem fonte (plano B: rodar com 4 features, declarado)"
        )
        raise FonteIndisponivel(msg)
    alinhada = alinhar_series(
        curva,
        calendario=calendario,
        inicio_por_serie=inicio_observado_por_serie(catalogo, raw),
        trimestres=grade_de_trimestres(calendario),
        fonte_versao=fonte_versao,
    )
    serie = alinhada.loc[alinhada["series_id"] == "INCLINACAO_REAL_5A_3A"]
    if serie.empty:
        msg = "BLOQUEADO — FONTE INDISPONÍVEL: INCLINACAO_REAL_5A_3A não está em raw_series"
        raise FonteIndisponivel(msg)
    return serie.set_index(serie["quarter"].astype(str))["value"].astype("float64")


def matriz_de_features(
    macro: pd.DataFrame,
    *,
    inclinacao: pd.Series,
    features: Sequence[Feature] = FEATURES_USADAS,
) -> pd.DataFrame:
    """A matriz `trimestre × feature` em **unidade original** (por cento/pp — F-015 §2, D-o).

    Sem z-score e sem recorte: a seleção dos trimestres com vetor completo é do chamador, para
    que o relatório possa nomear **quais** ficaram de fora e **por qual** feature.
    """
    if len(features) < 3:
        msg = f"{len(features)} features: o piso do contrato e 3 (n_features >= 3)"
        raise FeaturesInsuficientes(msg)
    if len(features) > 6:
        msg = f"{len(features)} features: o teto do contrato e 6 (n_features <= 6)"
        raise FeaturesInsuficientes(msg)
    colunas: dict[str, pd.Series] = {}
    for feature in features:
        if feature.origem == ORIGEM_MACRO:
            if feature.chave not in macro.columns:
                msg = f"{feature.chave} nao e coluna de macro_quarterly"
                raise FeaturesInsuficientes(msg)
            colunas[feature.nome] = macro[feature.chave].astype("float64")
        else:
            colunas[feature.nome] = inclinacao.reindex(macro.index).astype("float64")
    return pd.DataFrame(colunas, index=macro.index)


def trimestres_com_vetor_completo(matriz: pd.DataFrame) -> tuple[list[str], list[dict[str, Any]]]:
    """Separa quem tem o vetor cheio de quem não tem — e **por qual** feature não tem."""
    completos = [str(q) for q in matriz.index if bool(matriz.loc[q].notna().all())]
    faltando = [
        {
            "quarter": str(q),
            "motivo": MOTIVO_SEM_VETOR,
            "features_ausentes": sorted(c for c in matriz.columns if pd.isna(matriz.loc[q, c])),
        }
        for q in matriz.index
        if not bool(matriz.loc[q].notna().all())
    ]
    return completos, faltando


# ─────────────────────────────────────────────────────────────────────────────
# A lente
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Lente:
    """Uma variante da V3 — tudo que muda a resposta, declarado na linha do Parquet."""

    somente_passado: bool
    restrito_pos_2016: bool

    @property
    def janela_padronizacao(self) -> str:
        """`expanding_ate_T` na variante sem look-ahead, `amostra_completa` na descritiva."""
        return JANELA_EXPANDING if self.somente_passado else JANELA_AMOSTRA_COMPLETA


LENTES: tuple[Lente, ...] = (
    Lente(somente_passado=False, restrito_pos_2016=False),
    Lente(somente_passado=False, restrito_pos_2016=True),
    Lente(somente_passado=True, restrito_pos_2016=False),
    Lente(somente_passado=True, restrito_pos_2016=True),
)


@dataclass(frozen=True)
class Candidatura:
    """O conjunto de candidatos de uma referência numa lente, e o espaço onde ela foi medida."""

    quarter_ref: str
    candidatos: tuple[str, ...]
    z_referencia: np.ndarray
    z_candidatos: np.ndarray
    shrinkage: Shrinkage


def _pool(
    lente: Lente, quarter_ref: str, completos: Sequence[str], pool: Sequence[str]
) -> list[str]:
    """Quem pode ser vizinho de `quarter_ref` nesta lente, antes da exclusão de vizinhança."""
    elegiveis = [q for q in pool if q in set(completos)]
    if lente.restrito_pos_2016:
        elegiveis = [q for q in elegiveis if q >= PRIMEIRO_TRIMESTRE_POS_2016]
    if lente.somente_passado:
        elegiveis = [q for q in elegiveis if q < quarter_ref]
    return elegiveis


def montar_candidatura(
    matriz: pd.DataFrame,
    *,
    lente: Lente,
    quarter_ref: str,
    completos: Sequence[str],
    pool: Sequence[str],
) -> Candidatura | None:
    """Padroniza, encolhe a covariância e devolve o espaço de busca — ou `None` se não há busca.

    A ordem importa e é a de §5.1: **primeiro** decide-se a janela de estimação (só passado, ou
    amostra toda), **depois** se padroniza, **depois** se encolhe a covariância **na mesma
    janela**. Nenhum número posterior a `T` entra em nada disso na variante `somente_passado`.
    """
    candidatos = _pool(lente, quarter_ref, completos, pool)
    if not candidatos:
        return None
    base = matriz.loc[list(completos)]
    if lente.somente_passado:
        ate = max(q for q in completos if q <= quarter_ref)
        historico = [q for q in completos if q <= quarter_ref]
        if len(historico) < MIN_OBS_PADRONIZACAO_EXPANDING:
            return None
        z, _ = padronizar(base, ate=ate)
        amostra = z.loc[historico]
    else:
        z, _ = padronizar(base, ate=None)
        amostra = z
    return Candidatura(
        quarter_ref=quarter_ref,
        candidatos=tuple(candidatos),
        z_referencia=z.loc[quarter_ref].to_numpy(dtype="float64"),
        z_candidatos=z.loc[list(candidatos)].to_numpy(dtype="float64"),
        shrinkage=ledoit_wolf(amostra.to_numpy(dtype="float64")),
    )


def vizinhos_da_candidatura(
    candidatura: Candidatura, *, metrica: str, k: int
) -> tuple[Vizinho, ...]:
    """Os `k` vizinhos de uma candidatura numa métrica. Mahalanobis usa a covariância encolhida."""
    if metrica == MetricaDistancia.MAHALANOBIS.value:
        distancias = distancias_mahalanobis(
            candidatura.z_referencia,
            candidatura.z_candidatos,
            inverter(candidatura.shrinkage.sigma),
        )
    else:
        distancias = distancias_euclidianas(candidatura.z_referencia, candidatura.z_candidatos)
    return vizinhos_mais_proximos(candidatura.quarter_ref, candidatura.candidatos, distancias, k=k)


def montar_vizinhos(
    matriz: pd.DataFrame,
    *,
    rotulos: pd.Series,
    completos: Sequence[str],
    pool: Sequence[str],
    fonte_versao: str,
    n_features: int,
    features_usadas: str,
    lentes: Sequence[Lente] = LENTES,
    ks: Sequence[int] = K_VIZINHOS_SENSIBILIDADE,
) -> pd.DataFrame:
    """A tabela longa da V3 — uma linha por `(ref, rank, métrica, k, pos2016, somente_passado)`.

    `k = 5` e `k = 12` saem do **mesmo** ordenamento de `k = 8` (são prefixos da mesma lista):
    a sensibilidade de CA-087 mede o efeito de **cortar** a lista, não de recalcular distância.
    """
    linhas: list[dict[str, Any]] = []
    for lente in lentes:
        for quarter_ref in completos:
            if lente.restrito_pos_2016 and quarter_ref < PRIMEIRO_TRIMESTRE_POS_2016:
                continue
            candidatura = montar_candidatura(
                matriz,
                lente=lente,
                quarter_ref=quarter_ref,
                completos=completos,
                pool=pool,
            )
            if candidatura is None:
                continue
            for metrica in (MetricaDistancia.MAHALANOBIS.value, MetricaDistancia.EUCLIDIANA.value):
                ordenados = vizinhos_da_candidatura(candidatura, metrica=metrica, k=max(ks))
                for k in ks:
                    recorte = ordenados[:k]
                    if not recorte:
                        continue
                    for vizinho in recorte:
                        rotulo = rotulos.get(vizinho.quarter) or None
                        linhas.append(
                            {
                                "quarter_ref": quarter_ref,
                                "rank": vizinho.rank,
                                "quarter_neighbor": vizinho.quarter,
                                "distancia": vizinho.distancia,
                                "metrica": metrica,
                                "k_usado": int(k),
                                "n_vizinhos": len(recorte),
                                "n_features": int(n_features),
                                "features_usadas": features_usadas,
                                "regime_v1_neighbor": rotulo,
                                "status_regime_v1_neighbor": (
                                    StatusRegimeV1.CLASSIFICADO.value
                                    if rotulo
                                    else StatusRegimeV1.INDETERMINADO.value
                                ),
                                "quarter_t_mais_1": quarter_seguinte(vizinho.quarter),
                                "shrinkage": (
                                    SHRINKAGE_LEDOIT_WOLF
                                    if metrica == MetricaDistancia.MAHALANOBIS.value
                                    else SHRINKAGE_NAO_SE_APLICA
                                ),
                                "janela_padronizacao": lente.janela_padronizacao,
                                "somente_passado": lente.somente_passado,
                                "restrito_pos_2016": lente.restrito_pos_2016,
                                "alerta_n_baixo": len(recorte) < N_ALERTA,
                                "especificacao_congelada": ESPECIFICACAO_CONGELADA,
                                "versao_especificacao": VERSAO_ESPECIFICACAO_V3,
                                "lag_adjusted": LAG_ADJUSTED,
                                "fonte_versao": fonte_versao,
                            }
                        )
    if not linhas:
        msg = "BLOQUEADO — FONTE INDISPONÍVEL: nenhuma referência produziu vizinho"
        raise FonteIndisponivel(msg)
    tabela = pd.DataFrame(linhas)
    chave = [
        "somente_passado",
        "restrito_pos_2016",
        "metrica",
        "k_usado",
        "quarter_ref",
        "rank",
    ]
    tabela = tabela.sort_values(by=chave, kind="mergesort").reset_index(drop=True)
    tabela["regime_v1_neighbor"] = tabela["regime_v1_neighbor"].astype("string")
    tabela["quarter_t_mais_1"] = tabela["quarter_t_mais_1"].astype("string")
    return RegimeNeighborsV3Schema.validate(tabela, lazy=True)


def projetar_no_contrato(v3: pd.DataFrame) -> pd.DataFrame:
    """A fatia de `regime_neighbors_v3` que `RegimeNeighborsSchema` aceita (CA-089).

    Duas restrições, as duas por causa do contrato de hoje e **nenhuma** por causa do método:

    - só a variante **descritiva** (`somente_passado = False`), porque a PK do contrato não tem
      coluna que distinga as duas janelas de padronização e elas colidiriam;
    - só vizinho com **rótulo V1**, porque `regime_v1_neighbor` é `nullable=False` (**D-m**).

    O `rank` é **recalculado** no conjunto restrito — não se filtra um ranking, porque "rank 3"
    com o 1 e o 2 removidos seria mentira. É por isso que `construir` chama `montar_vizinhos` uma
    segunda vez com o pool restrito, em vez de usar esta função como filtro; esta função só
    projeta as colunas.
    """
    colunas = list(RegimeNeighborsSchema.to_schema().columns)
    descritiva = v3.loc[~v3["somente_passado"].astype(bool)].copy()
    tabela = descritiva.loc[:, colunas].copy()
    tabela["regime_v1_neighbor"] = tabela["regime_v1_neighbor"].astype(str)
    chave = ["quarter_ref", "metrica", "k_usado", "restrito_pos_2016", "rank"]
    tabela = tabela.sort_values(by=chave, kind="mergesort").reset_index(drop=True)
    return RegimeNeighborsSchema.validate(tabela, lazy=True)


# ─────────────────────────────────────────────────────────────────────────────
# Retorno em T+1 (RF-036 / CA-102) — o que o Comitê olha
# ─────────────────────────────────────────────────────────────────────────────


def retornos_em_t_mais_1(
    vizinhos: Iterable[Vizinho],
    retornos: pd.DataFrame,
    *,
    coluna: str = "ret_excesso_cdi",
) -> pd.DataFrame:
    """O retorno de cada ativo nos trimestres **seguintes** aos vizinhos — nunca neles.

    `quarter` da linha devolvida é sempre `vizinho + 1` (`quarter_seguinte`). Vizinho no fim da
    janela não contribui: `T+1` não existe, e a ausência fica visível no `n` do ranking em vez de
    virar um retorno do próprio vizinho (que é exatamente o erro que CA-102 proíbe).
    """
    alvos = [
        (v.quarter, quarter_seguinte(v.quarter))
        for v in vizinhos
        if quarter_seguinte(v.quarter) is not None
    ]
    if not alvos:
        return retornos.iloc[0:0].assign(quarter_vizinho=pd.Series(dtype="object"))
    mapa = {seguinte: vizinho for vizinho, seguinte in alvos}
    fatia = retornos.loc[retornos["quarter"].isin(mapa)].copy()
    fatia["quarter_vizinho"] = fatia["quarter"].map(mapa)
    return fatia.loc[:, ["asset_id", "quarter_vizinho", "quarter", coluna]]


def ranking_de_ativos(
    observado: pd.DataFrame, *, coluna: str = "ret_excesso_cdi"
) -> list[dict[str, Any]]:
    """O ranking de ativos pelo retorno médio em `T+1` dos vizinhos, com `n` em **toda** linha.

    Métricas, todas da metodologia §3: média **e** mediana lado a lado (divergência grande = um
    trimestre dominando), desvio amostral, **erro-padrão** = desvio/√n (com n = 8 e desvio de 12%
    o erro-padrão é ~4 p.p.: diferenças menores que isso não se distinguem de ruído) e
    `hit_ratio_cdi`, que é a métrica que o Comitê brasileiro de fato usa.

    `alerta_n_baixo` com `n < 8` e `conclusao_suprimida` com `n < 5` (CA-108/109, Anti-SPEC
    §10.2.8): a linha continua no ranking, com a flag — suprimir a **conclusão** não é apagar o
    dado.
    """
    if observado.empty:
        return []
    ranking: list[dict[str, Any]] = []
    for asset_id, grupo in observado.groupby("asset_id", sort=True):
        validos = grupo.loc[grupo[coluna].notna(), coluna].astype(float)
        n = int(len(validos))
        if n == 0:
            ranking.append(
                {
                    "asset_id": str(asset_id),
                    "n": 0,
                    "media": None,
                    "mediana": None,
                    "desvio": None,
                    "erro_padrao": None,
                    "hit_ratio_cdi": None,
                    "alerta_n_baixo": True,
                    "conclusao_suprimida": True,
                    "trimestres": [],
                }
            )
            continue
        desvio = float(validos.std(ddof=1)) if n > 1 else None
        ranking.append(
            {
                "asset_id": str(asset_id),
                "n": n,
                "media": float(validos.mean()),
                "mediana": float(validos.median()),
                "desvio": desvio,
                "erro_padrao": None if desvio is None else desvio / np.sqrt(n),
                "hit_ratio_cdi": float((validos > 0).mean()),
                "alerta_n_baixo": n < N_ALERTA,
                "conclusao_suprimida": n < N_SUPRESSAO,
                "trimestres": sorted(str(q) for q in grupo.loc[validos.index, "quarter"]),
            }
        )
    ranking.sort(key=lambda linha: -(linha["media"] if linha["media"] is not None else -9e9))
    return ranking


# ─────────────────────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────────────────────


def _lista_de_vizinhos(
    v3: pd.DataFrame,
    *,
    quarter_ref: str,
    metrica: str = MetricaDistancia.MAHALANOBIS.value,
    k: int = K_VIZINHOS_PADRAO,
    somente_passado: bool = False,
    restrito_pos_2016: bool = False,
) -> pd.DataFrame:
    """A fatia de uma única lente — a forma em que o relatório e o CLI leem a tabela."""
    alvo = v3.loc[
        (v3["quarter_ref"] == quarter_ref)
        & (v3["metrica"] == metrica)
        & (v3["k_usado"] == k)
        & (v3["somente_passado"].astype(bool) == somente_passado)
        & (v3["restrito_pos_2016"].astype(bool) == restrito_pos_2016)
    ]
    return alvo.sort_values("rank", kind="mergesort")


def _vizinhos_como_dicionario(fatia: pd.DataFrame, matriz: pd.DataFrame) -> list[dict[str, Any]]:
    """Os vizinhos com distância, rótulo, `T+1` e **o que cada um tinha de macro**."""
    saida: list[dict[str, Any]] = []
    for _, linha in fatia.iterrows():
        vizinho = str(linha["quarter_neighbor"])
        saida.append(
            {
                "rank": int(linha["rank"]),
                "quarter_neighbor": vizinho,
                "distancia": float(linha["distancia"]),
                "regime_v1_neighbor": (
                    None
                    if pd.isna(linha["regime_v1_neighbor"])
                    else str(linha["regime_v1_neighbor"])
                ),
                "status_regime_v1_neighbor": str(linha["status_regime_v1_neighbor"]),
                "quarter_t_mais_1": (
                    None if pd.isna(linha["quarter_t_mais_1"]) else str(linha["quarter_t_mais_1"])
                ),
                "macro": {
                    str(c): (
                        None if pd.isna(matriz.loc[vizinho, c]) else float(matriz.loc[vizinho, c])
                    )
                    for c in matriz.columns
                },
            }
        )
    return saida


def _sobreposicao(a: Sequence[str], b: Sequence[str]) -> dict[str, Any]:
    """Quantos vizinhos duas lentes têm em comum — a forma de reportar divergência (CA-087)."""
    conjunto_a, conjunto_b = set(a), set(b)
    uniao = conjunto_a | conjunto_b
    return {
        "n_a": len(conjunto_a),
        "n_b": len(conjunto_b),
        "em_comum": len(conjunto_a & conjunto_b),
        "jaccard": (len(conjunto_a & conjunto_b) / len(uniao)) if uniao else None,
        "so_em_a": sorted(conjunto_a - conjunto_b),
        "so_em_b": sorted(conjunto_b - conjunto_a),
    }


def montar_relatorio(
    *,
    v3: pd.DataFrame,
    contrato: pd.DataFrame,
    matriz: pd.DataFrame,
    completos: Sequence[str],
    faltando: Sequence[dict[str, Any]],
    shrinkage: Shrinkage,
    parametros_z: Mapping[str, Mapping[str, float]],
    ranking: list[dict[str, Any]],
    rankings_alternativos: Mapping[str, list[dict[str, Any]]],
    conferencia_v1: Mapping[str, Any],
    hashes: Mapping[str, Any],
) -> dict[str, Any]:
    """`relatorio_regimes_v3.json` — **sem relógio**, para que dois builds sejam idênticos.

    O bloco que o Comitê olha é `vizinhos_do_comite` + `ranking_ativos_t_mais_1`; o bloco que a
    revisão numérica independente olha é `shrinkage`, `padronizacao` e `sensibilidade`.
    """
    principal = _lista_de_vizinhos(v3, quarter_ref=QUARTER_DO_COMITE)
    sensibilidade: dict[str, Any] = {}
    base = [str(q) for q in principal["quarter_neighbor"]]
    for k in K_VIZINHOS_SENSIBILIDADE:
        if k == K_VIZINHOS_PADRAO:
            continue
        outra = _lista_de_vizinhos(v3, quarter_ref=QUARTER_DO_COMITE, k=k)
        sensibilidade[f"k_{k}_vs_k_{K_VIZINHOS_PADRAO}"] = {
            **_sobreposicao([str(q) for q in outra["quarter_neighbor"]], base),
            "vizinhos": [str(q) for q in outra["quarter_neighbor"]],
        }
    for nome, kwargs in (
        ("euclidiana_vs_mahalanobis", {"metrica": MetricaDistancia.EUCLIDIANA.value}),
        ("somente_passado_vs_descritiva", {"somente_passado": True}),
        ("pos2016_vs_janela_cheia", {"restrito_pos_2016": True}),
    ):
        outra = _lista_de_vizinhos(v3, quarter_ref=QUARTER_DO_COMITE, **kwargs)  # type: ignore[arg-type]
        sensibilidade[nome] = {
            **_sobreposicao([str(q) for q in outra["quarter_neighbor"]], base),
            "vizinhos": [str(q) for q in outra["quarter_neighbor"]],
        }

    do_contrato = contrato.loc[
        (contrato["quarter_ref"] == QUARTER_DO_COMITE)
        & (contrato["metrica"] == MetricaDistancia.MAHALANOBIS.value)
        & (contrato["k_usado"] == K_VIZINHOS_PADRAO)
        & (~contrato["restrito_pos_2016"].astype(bool))
    ].sort_values("rank", kind="mergesort")

    sem_v1 = sorted(
        {
            str(q)
            for q in v3.loc[
                v3["status_regime_v1_neighbor"] == StatusRegimeV1.INDETERMINADO.value,
                "quarter_neighbor",
            ]
        }
    )
    n_por_lente = {
        f"somente_passado={bool(sp)}|pos2016={bool(pos)}": int(len(grupo["quarter_ref"].unique()))
        for (sp, pos), grupo in v3.groupby(["somente_passado", "restrito_pos_2016"], sort=True)
    }
    return {
        "feature": "F-021",
        "lente": "V3",
        "versao_especificacao": VERSAO_ESPECIFICACAO_V3,
        "gate_de_publicacao": {
            "especificacao_congelada": ESPECIFICACAO_CONGELADA,
            "adr": ADR_DA_ESPECIFICACAO,
            "status_do_adr": STATUS_DO_ADR,
            "publicavel": False,
            "motivo": (
                "CA-090: enquanto ADR-001 estiver em Proposta, o cruzamento regime x retorno "
                "nao e publicavel. O numero so vai ao Comite pelo fluxo de classe D "
                "(AGENTS.md 14): revisao humana + dataset congelado + hash + linha no log."
            ),
            "linguagem": (
                "Saida descritiva (Anti-SPEC 10.2.10): 'em momentos parecidos o ativo rendeu X, "
                "n = 8'. Nunca 'vai render'."
            ),
        },
        "features": {
            "n_features": len(FEATURES_USADAS),
            "usadas": [
                {
                    "nome": f.nome,
                    "origem": f.origem,
                    "chave": f.chave,
                    "unidade": f.unidade,
                    "descricao": f.descricao,
                    "substitui": f.substitui,
                    "motivo_da_substituicao": f.motivo_da_substituicao,
                    "cobertura": int(matriz[f.nome].notna().sum()),
                }
                for f in FEATURES_USADAS
            ],
            "descartadas": [{"nome": n, "motivo": m} for n, m in FEATURES_DESCARTADAS],
            "contrato_FEATURES_V3": list(FEATURES_V3),
        },
        "cobertura": {
            "trimestres_na_janela": len(janela()),
            "com_vetor_completo": len(completos),
            "primeiro": completos[0] if completos else None,
            "ultimo": completos[-1] if completos else None,
            "sem_v3_por_falta_de_feature": list(faltando),
            "referencias_por_lente": n_por_lente,
            "referencias_sem_somente_passado": {
                "motivo": MOTIVO_HISTORIA_CURTA,
                "min_obs": MIN_OBS_PADRONIZACAO_EXPANDING,
                "quarters": [
                    q
                    for q in completos
                    if len([x for x in completos if x <= q]) < MIN_OBS_PADRONIZACAO_EXPANDING
                ],
            },
        },
        "padronizacao": {
            "janela_da_tabela_principal": JANELA_AMOSTRA_COMPLETA,
            "ddof": 1,
            "parametros_amostra_completa": {k: dict(v) for k, v in parametros_z.items()},
            "nota": (
                "metodologia 2 (principio 4): z-score na amostra completa na versao descritiva, "
                "expanding em qualquer versao que vire backtest. As duas nunca se misturam na "
                "mesma leitura — a coluna janela_padronizacao diz qual e."
            ),
        },
        "shrinkage": {
            "estimador": SHRINKAGE_LEDOIT_WOLF,
            "implementacao": "numpy puro neste modulo (sem scipy/sklearn no ambiente)",
            "intensidade_rho": shrinkage.intensidade,
            "n": shrinkage.n,
            "p": shrinkage.p,
            "cond_covariancia_amostral": shrinkage.cond_amostral,
            "cond_covariancia_encolhida": shrinkage.cond_encolhida,
            "nota": (
                "CA-084: a covariancia amostral crua em 83x5 e instavel; o shrinkage e medido, "
                "nunca escolhido (nao ha parametro de intensidade na assinatura)."
            ),
        },
        "exclusao_de_vizinhanca": {
            "trimestres_excluidos": N_TRIMESTRES_EXCLUIDOS_VIZINHANCA,
            "simetrica": True,
            "nota": (
                "CA-085 enuncia 'os 2 trimestres imediatamente anteriores'. A exclusao aqui e "
                "simetrica (T, T+-1, T+-2) porque na variante descritiva o candidato pode estar "
                "no futuro e T+1 e tao trivialmente parecido com T quanto T-1. Na variante "
                "somente_passado a regra se reduz exatamente ao enunciado."
            ),
            "desempate": "distancias iguais: prevalece o trimestre mais recente",
        },
        "vizinhos_do_comite": {
            "quarter_ref": QUARTER_DO_COMITE,
            "lente": {
                "metrica": MetricaDistancia.MAHALANOBIS.value,
                "k": K_VIZINHOS_PADRAO,
                "somente_passado": False,
                "restrito_pos_2016": False,
                "janela_padronizacao": JANELA_AMOSTRA_COMPLETA,
            },
            "macro_da_referencia": {
                str(c): (
                    None
                    if pd.isna(matriz.loc[QUARTER_DO_COMITE, c])
                    else float(matriz.loc[QUARTER_DO_COMITE, c])
                )
                for c in matriz.columns
            },
            "vizinhos": _vizinhos_como_dicionario(principal, matriz),
        },
        "ranking_ativos_t_mais_1": {
            "metrica_do_ranking": "ret_excesso_cdi (razao, nunca subtracao — CA-069)",
            "o_que_e_medido": (
                "retorno de cada ativo no trimestre SEGUINTE a cada vizinho (CA-102), nunca no "
                "proprio vizinho"
            ),
            "trimestres_t_mais_1": [
                v["quarter_t_mais_1"] for v in _vizinhos_como_dicionario(principal, matriz)
            ],
            "limiares": {"alerta_n_baixo": N_ALERTA, "conclusao_suprimida": N_SUPRESSAO},
            "ativos": ranking,
            "alternativas": {
                nome: [
                    {"asset_id": linha["asset_id"], "n": linha["n"], "media": linha["media"]}
                    for linha in lista[:5]
                ]
                for nome, lista in rankings_alternativos.items()
            },
        },
        "sensibilidade": sensibilidade,
        "divergencia_contrato_vs_completo": {
            "motivo": (
                "RegimeNeighborsSchema.regime_v1_neighbor e nullable=False e, por D-m, 16 "
                "trimestres nao tem quadrante V1. A tabela de contrato so pode conter vizinho "
                "com rotulo, e o ranking e recalculado nesse pool restrito."
            ),
            "pool_completo": len(completos),
            "pool_com_rotulo_v1": len([q for q in completos if q not in set(sem_v1)]),
            "vizinhos_sem_rotulo_v1_na_tabela_completa": sem_v1,
            "2026Q3": _sobreposicao(
                [str(q) for q in do_contrato["quarter_neighbor"]],
                base,
            ),
            "recomendacao": (
                "tornar regime_v1_neighbor anulavel em RegimeNeighborsSchema (alteracao de "
                "schema = feature classe C propria) e colapsar os dois artefatos num so."
            ),
        },
        "conferencia_v1_vs_f019": dict(conferencia_v1),
        "regime_neighbors_v3": {
            "linhas": int(len(v3)),
            "colunas": int(v3.shape[1]),
            "referencias": int(v3["quarter_ref"].nunique()),
            "sha256": hashes["sha256_v3"],
            "bytes": hashes["bytes_v3"],
        },
        "regime_neighbors": {
            "linhas": int(len(contrato)),
            "colunas": int(contrato.shape[1]),
            "referencias": int(contrato["quarter_ref"].nunique()),
            "sha256": hashes["sha256_contrato"],
            "bytes": hashes["bytes_contrato"],
        },
        "versao_build": hashes["versao_build"],
        "fonte_versao": hashes["fonte_versao"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DA_V3` — a mesma convenção de F-014/F-015 (CA-121)."""
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DA_V3))


def fonte_versao_declarada(versao: str, *, n_features: int = len(FEATURES_USADAS)) -> str:
    """`<sha256>-nf<N>`: CA-086 pede que o corte de feature seja declarado **no `fonte_versao`**.

    Duas rodadas com o mesmo código e feature cortada diferente **não** podem ter o mesmo
    `fonte_versao` — é a mesma lógica do P1-1 do QA da Onda 2, um nível acima.
    """
    return f"{versao}-nf{int(n_features)}"


@dataclass(frozen=True)
class ResultadoV3:
    """O que o build devolve — para o teste e para quem encadeia a V3 em F-022/F-024."""

    v3: pd.DataFrame
    contrato: pd.DataFrame
    matriz: pd.DataFrame
    relatorio: dict[str, Any]
    caminho_v3: Path
    caminho_contrato: Path
    caminho_relatorio: Path


def construir(
    *,
    raiz: Path | None = None,
    calendario: Calendario | None = None,
) -> ResultadoV3:
    """Reconstrói a V3 de ponta a ponta. Sem rede, sem relógio, sem efeito fora de `data/`."""
    macro = (
        _ler_canonical(NOME_MACRO, schema=MacroQuarterlySchema, raiz=raiz)
        .set_index("quarter")
        .sort_index()
    )
    raw = _ler_canonical(NOME_RAW_SERIES, schema=RawSeriesSchema, raiz=raiz)
    catalogo = _ler_canonical(NOME_CATALOGO, schema=SeriesCatalogMaterializedSchema, raiz=raiz)
    retornos = _ler_canonical(NOME_RETORNOS, schema=AssetReturnsQuarterlySchema, raiz=raiz)
    cal = calendario if calendario is not None else Calendario.do_parquet(raiz=raiz)

    versao = versao_build()
    fonte = fonte_versao_declarada(versao)
    inclinacao = inclinacao_real_5a_3a(raw, catalogo, calendario=cal, fonte_versao=versao)
    matriz = matriz_de_features(macro, inclinacao=inclinacao)
    completos, faltando = trimestres_com_vetor_completo(matriz)
    if len(completos) < MIN_OBS_PADRONIZACAO_EXPANDING:
        msg = (
            f"BLOQUEADO — FONTE INDISPONÍVEL: só {len(completos)} trimestres têm o vetor de "
            f"{len(FEATURES_USADAS)} features completo"
        )
        raise FonteIndisponivel(msg)
    _log.info(
        "V3 com %d features (%s): %d dos %d trimestres com vetor completo",
        len(FEATURES_USADAS),
        ", ".join(f.nome for f in FEATURES_USADAS),
        len(completos),
        len(janela()),
    )
    if ESPECIFICACAO_CONGELADA is False:
        _log.warning(
            "CA-090: %s esta em %s — especificacao_congelada=False e NADA daqui e publicavel "
            "fora do fluxo de classe D",
            ADR_DA_ESPECIFICACAO,
            STATUS_DO_ADR,
        )

    rotulos = rotulos_v1_de_anotacao(macro)
    conferencia = conferir_v1_contra_f019(rotulos, raiz=raiz)
    _log.info("rotulo V1 de anotacao conferido contra F-019: %s", conferencia)

    features_declaradas = SEPARADOR_DE_FEATURES.join(f.nome for f in FEATURES_USADAS)
    v3 = montar_vizinhos(
        matriz,
        rotulos=rotulos,
        completos=completos,
        pool=completos,
        fonte_versao=fonte,
        n_features=len(FEATURES_USADAS),
        features_usadas=features_declaradas,
        lentes=LENTES,
    )
    com_rotulo = [q for q in completos if rotulos.get(q)]
    contrato = projetar_no_contrato(
        montar_vizinhos(
            matriz,
            rotulos=rotulos,
            completos=completos,
            pool=com_rotulo,
            fonte_versao=fonte,
            n_features=len(FEATURES_USADAS),
            features_usadas=features_declaradas,
            lentes=(LENTES[0], LENTES[1]),
        )
    )

    principal = _lista_de_vizinhos(v3, quarter_ref=QUARTER_DO_COMITE)
    vizinhos_do_comite = tuple(
        Vizinho(
            rank=int(r["rank"]), quarter=str(r["quarter_neighbor"]), distancia=float(r["distancia"])
        )
        for _, r in principal.iterrows()
    )
    ranking = ranking_de_ativos(retornos_em_t_mais_1(vizinhos_do_comite, retornos))
    alternativos: dict[str, list[dict[str, Any]]] = {}
    for nome, kwargs in (
        ("k_5", {"k": 5}),
        ("k_12", {"k": 12}),
        ("euclidiana", {"metrica": MetricaDistancia.EUCLIDIANA.value}),
        ("somente_passado", {"somente_passado": True}),
        ("pos2016", {"restrito_pos_2016": True}),
    ):
        fatia = _lista_de_vizinhos(v3, quarter_ref=QUARTER_DO_COMITE, **kwargs)  # type: ignore[arg-type]
        alternativos[nome] = ranking_de_ativos(
            retornos_em_t_mais_1(
                [
                    Vizinho(int(r["rank"]), str(r["quarter_neighbor"]), float(r["distancia"]))
                    for _, r in fatia.iterrows()
                ],
                retornos,
            )
        )

    z_completo, parametros = padronizar(matriz.loc[completos], ate=None)
    shrinkage = ledoit_wolf(z_completo.to_numpy(dtype="float64"))

    destino_v3 = caminho_canonical(NOME_NEIGHBORS_V3, raiz=raiz)
    destino_contrato = caminho_canonical(NOME_NEIGHBORS, raiz=raiz)
    garantir_diretorio(destino_v3.parent)
    v3.to_parquet(destino_v3, index=False)
    contrato.to_parquet(destino_contrato, index=False)
    corpo_v3 = destino_v3.read_bytes()
    corpo_contrato = destino_contrato.read_bytes()
    _log.info(
        "gravado %s (%d linhas, sha256=%s...) e %s (%d linhas, sha256=%s...)",
        destino_v3.name,
        len(v3),
        sha256_de(corpo_v3)[:12],
        destino_contrato.name,
        len(contrato),
        sha256_de(corpo_contrato)[:12],
    )

    relatorio = montar_relatorio(
        v3=v3,
        contrato=contrato,
        matriz=matriz,
        completos=completos,
        faltando=faltando,
        shrinkage=shrinkage,
        parametros_z=parametros,
        ranking=ranking,
        rankings_alternativos=alternativos,
        conferencia_v1=conferencia,
        hashes={
            "sha256_v3": sha256_de(corpo_v3),
            "bytes_v3": len(corpo_v3),
            "sha256_contrato": sha256_de(corpo_contrato),
            "bytes_contrato": len(corpo_contrato),
            "versao_build": versao,
            "fonte_versao": fonte,
        },
    )
    destino_relatorio = caminho_canonical(NOME_RELATORIO, raiz=raiz)
    destino_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ResultadoV3(
        v3=v3,
        contrato=contrato,
        matriz=matriz,
        relatorio=relatorio,
        caminho_v3=destino_v3,
        caminho_contrato=destino_contrato,
        caminho_relatorio=destino_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.regimes_v3",
        description=(
            "Materializa data/canonical/regime_neighbors_v3.parquet + regime_neighbors.parquet + "
            "relatorio_regimes_v3.json (V3: vizinhos mais proximos + retorno em T+1). "
            "Nunca toca a rede."
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

    rel = resultado.relatorio
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{NOME_NEIGHBORS_V3}: {rel['regime_neighbors_v3']['linhas']} linhas | "
        f"{rel['regime_neighbors_v3']['referencias']} referencias | "
        f"sha256 {rel['regime_neighbors_v3']['sha256']}"
    )
    print(
        f"{NOME_NEIGHBORS}: {rel['regime_neighbors']['linhas']} linhas | "
        f"{rel['regime_neighbors']['referencias']} referencias | "
        f"sha256 {rel['regime_neighbors']['sha256']}"
    )
    print(
        f"features ({rel['features']['n_features']}): "
        f"{', '.join(f['nome'] for f in rel['features']['usadas'])}"
    )
    print(
        f"cobertura: {rel['cobertura']['com_vetor_completo']}/"
        f"{rel['cobertura']['trimestres_na_janela']} trimestres com vetor completo; "
        f"sem V3: {[f['quarter'] for f in rel['cobertura']['sem_v3_por_falta_de_feature']]}"
    )
    print(
        f"shrinkage ledoit_wolf: rho = {rel['shrinkage']['intensidade_rho']:.6f} | "
        f"cond amostral {rel['shrinkage']['cond_covariancia_amostral']:.3f} -> "
        f"encolhida {rel['shrinkage']['cond_covariancia_encolhida']:.3f}"
    )
    print(f"vizinhos de {QUARTER_DO_COMITE} (mahalanobis, k={K_VIZINHOS_PADRAO}):")
    for vizinho in rel["vizinhos_do_comite"]["vizinhos"]:
        print(
            f"  {vizinho['rank']}. {vizinho['quarter_neighbor']} d={vizinho['distancia']:.4f} "
            f"v1={vizinho['regime_v1_neighbor']} T+1={vizinho['quarter_t_mais_1']}"
        )
    print("ranking de ativos no T+1 dos vizinhos (excesso sobre CDI, media):")
    for linha in rel["ranking_ativos_t_mais_1"]["ativos"]:
        media = "n/d" if linha["media"] is None else f"{100 * linha['media']:+.2f}%"
        alerta = " ALERTA_N_BAIXO" if linha["alerta_n_baixo"] else ""
        print(f"  {linha['asset_id']:12s} n={linha['n']:2d} media={media}{alerta}")
    print(
        f"gate: especificacao_congelada={rel['gate_de_publicacao']['especificacao_congelada']} "
        f"({rel['gate_de_publicacao']['adr']} em {rel['gate_de_publicacao']['status_do_adr']}) "
        "-> NAO PUBLICAVEL"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
