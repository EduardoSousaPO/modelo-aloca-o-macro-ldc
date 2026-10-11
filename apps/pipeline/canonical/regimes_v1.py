"""F-019 — Regimes V1: quadrantes crescimento x inflação. **Classe C.**

Materializa dois artefatos em `data/canonical/`, por materialização de `macro_quarterly`:

| Artefato | O que é |
|---|---|
| `regimes_v1.parquet` / `regimes_v1_asof.parquet` | 83 linhas, validadas por `RegimesV1Schema` |
| `relatorio_regimes_v1.json` / `..._asof.json` | `n`, timeline, canários, sensibilidade |

## A regra, inteira, em 5 linhas

1. `g_T` = `ibcbr_gap` de T (IBC-Br a/a dessaz. **menos** a média móvel de 20 trimestres de si
   mesma) — já é coluna de `macro_quarterly`, calculada por F-015; esta feature **não recalcula**.
2. `pi_T` = `ipca_12m_delta` de T (IPCA 12m em T **menos** IPCA 12m em T−1) — a **aceleração**,
   `[PROVISÓRIO D3]` do ADR-001 §4. Não é desvio da meta (`ipca_meta` é o gap **G-02**, nulo hoje).
3. `crescimento_acima = g_T > 0` · `inflacao_acelerando = pi_T > 0` (os dois limiares são
   constantes do contrato: `LIMIAR_CRESCIMENTO_PP`, `LIMIAR_ACELERACAO_PP`).
4. Rótulo: `RECUPERACAO` (↑g, ↓π) · `EXPANSAO_INFL` (↑g, ↑π) · `ESTAGFLACAO` (↓g, ↑π) ·
   `DESACELERACAO` (↓g, ↓π) — ADR-001 §5.
5. **Desempate (CA-079):** eixo **exatamente** no limiar herda o sinal **daquele eixo** em `T−1`.
   Estritamente `T−1`: se `T−1` também não tem sinal para aquele eixo, o trimestre fica
   `INDETERMINADO` com motivo `EMPATE_SEM_SINAL_ANTERIOR` — **nunca** se procura um `T−2` ou se
   adota um default, porque "herdar de dois trimestres atrás" é uma regra nova, não a do ADR.

## `INDETERMINADO`: 16 trimestres, e isso é o resultado, não um defeito

`ibcbr_gap` é nulo em `2006Q1..2009Q3` (15) e em `2026Q3` (1) — **D-m** no `DECISIONS_LOG §2.3` e
`TODO.md §4`: o IBC-Br dessazonalizado (SGS 24364) começa em 2003, `ibcbr_yoy` só existe de 2005Q1
e a média móvel de 20 trimestres com **janela cheia** só fecha em 2009Q4. Para ter hiato em 2006Q1
seria preciso IBC-Br desde 2000Q2, e **a série não existe**.

**Decisão desta feature:** esses trimestres recebem `regime_v1 = NULL` +
`status_regime_v1 = INDETERMINADO` + `motivo_indeterminado` preenchido. **Nunca** uma estimativa,
uma interpolação, um quadrante "mais provável" ou um `min_periods` menor escolhido aqui
(Anti-SPEC §10.1.1; a alternativa `min_periods = 8` está **medida** em
`relatorio_macro.json → sensibilidade_ibcbr_gap` e é decisão do Edu, não desta feature).
**Consequência que vai à página de limitações (F-028): a crise de 2008 inteira fica fora do eixo de
crescimento da V1.** A V1 classifica **67** dos 83 trimestres.

`ipca_12m_delta` não tem nulo nenhum nos 83 trimestres, então hoje o conjunto de indeterminados é
exatamente o conjunto de `ibcbr_gap` nulo. O código não assume isso: conta e publica os motivos.

## Por que `regimes_v1.parquet` e não `regimes.parquet`

`RegimesSchema` é o contrato da tabela **completa**: `ciclo_selic`, `regime_v2` e `stress_flag` são
`nullable=False` e pertencem a **F-020**/**F-021**, e `regime_v1` é `nullable=False` no enum de 4
rótulos. Gravar `regimes.parquet` hoje exigiria inventar as colunas de V2 ou inventar um quadrante
para os 16 nulos — as duas proibidas — ou **alterar** `RegimesSchema`, que é pausa
(`AGENTS.md §9`/`§13`). Então F-019 grava o **subconjunto validado** por `RegimesV1Schema`
(acréscimo ao módulo de schema, nada alterado) e **a junção das três lentes numa tabela `regimes`
que satisfaça `RegimesSchema` é de F-022**, que é quem tem as três na mão. `COLUNAS_V1_DE_REGIMES`
nomeia o que vem daqui, e há teste de que toda coluna existe em `RegimesSchema` com o mesmo nome.

## Anti-look-ahead

A classificação de T lê **só a linha T** da materialização recebida (`g_score`, `pi_score`), mais —
e apenas no desempate exato — o sinal já resolvido de `T−1`. Nenhum caminho lê `T+1`: o laço é um
`for` em ordem crescente de `quarter` sobre uma grade validada como ordenada e sem duplicata, e há
teste que **mexe nas linhas futuras** e exige rótulo idêntico. O `n` por regime é, por desenho, uma
estatística **da amostra inteira** (é a leitura descritiva "onde estamos no histórico" que o Comitê
pede, metodologia §2 princípio 4) — não entra na decisão de nenhum T e está declarado como tal.

A escolha entre `revised` (série de hoje) e `asof` (que respeita a defasagem de divulgação,
**F-018**) é parâmetro: `--materializacao`. Quando `macro_quarterly_asof.parquet` existir, a
rodada `asof` preenche `trocou_vs_revised` por trimestre e o relatório publica a **% de
trimestres que trocam de rótulo** (CA-073), com o texto de CA-074 se passar de
`LIMIAR_TROCA_REGIME_INOPERANTE` (25%).

## Publicação: BLOQUEADA, e por quê (CA-090)

`especificacao_congelada` **não** é constante no código: sai do **status do ADR-001 em disco**. Em
`Proposta`, a coluna é `False` nas 83 linhas, o relatório carrega
`veredito_publicacao = "BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA"` e o CLI **avisa**. Falha fechada:
ADR ilegível ou ausente também dá `False`. Desenvolver é permitido; publicar não é (`AGENTS.md §9`).
`versao_especificacao` nasce `V1`; ajuste posterior entra como `V1.1` **sem sobrescrever** (CA-091).

**Sem rede, sem relógio, sem estado.** Entradas: `data/canonical/macro_quarterly*.parquet` e o
status do ADR-001. `fonte_versao` é o `sha256` do **conjunto** `MODULOS_DO_REGIME_V1`, não do
processo — duas rodadas sobre o mesmo dado dão o mesmo Parquet, byte a byte.

Referências: SPEC RF-027 (CA-078..081), RF-030 (CA-088), RF-031 (CA-090/091), RF-040 (CA-108/109),
RF-025 (CA-072..074) · Anti-SPEC §10.1.1, §10.2.7, §10.2.8, §10.2.9, §10.2.10 · ADR-001 (Proposta) ·
`docs/research/metodologia-regimes-macro.md §2`, §5.1, §5.4, §5.5 · `CONTRACTS.md §5` ·
`DECISIONS_LOG §2.3` (D-m) · `docs/wiki/context/F-019.md` (timeline + revisão numérica).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from apps.pipeline.canonical.build_raw_series import (
    caminhos_dos_componentes,
)
from apps.pipeline.canonical.build_raw_series import (
    versao_build as _hash_dos_componentes,
)
from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, raiz_repo, sha256_de
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from packages.shared.schemas.macro_quarterly import (
    MacroQuarterlySchema,
)
from packages.shared.schemas.regimes import (
    LIMIAR_ACELERACAO_PP,
    LIMIAR_CRESCIMENTO_PP,
    LIMIAR_TROCA_REGIME_INOPERANTE,
    N_ALERTA,
    N_QUADRANTE_MAXIMO_CA080,
    N_QUADRANTE_MINIMO_CA080,
    N_SUPRESSAO,
    SENSIBILIDADE_ACELERACAO_PP,
    VERSAO_ESPECIFICACAO_V1,
    MotivoIndeterminado,
    RegimesV1Schema,
    RegimeV1,
    StatusRegimeV1,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Iterable, Sequence

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────

#: A coluna de `macro_quarterly` que é o eixo de crescimento (ADR-001 §4). Em **pp** (D-o).
COLUNA_CRESCIMENTO = "ibcbr_gap"
#: A coluna que é o eixo de inflação — **aceleração**, não nível nem desvio da meta (D3). Em **pp**.
COLUNA_INFLACAO = "ipca_12m_delta"

COLUNAS_EXIGIDAS_NA_ENTRADA: tuple[str, ...] = (
    "quarter",
    COLUNA_CRESCIMENTO,
    COLUNA_INFLACAO,
    "lag_adjusted",
)


class Materializacao(StrEnum):
    """Qual materialização de `macro_quarterly` alimenta a classificação (CA-072)."""

    REVISED = "revised"
    ASOF = "asof"


#: Arquivo de entrada por materialização. `asof` é de **F-018** e pode não existir ainda — a
#: ausência é `FonteIndisponivel` com a instrução, nunca um fallback silencioso para `revised`.
NOME_MACRO_POR_MATERIALIZACAO: dict[str, str] = {
    Materializacao.REVISED.value: "macro_quarterly.parquet",
    Materializacao.ASOF.value: "macro_quarterly_asof.parquet",
}

NOME_REGIMES_POR_MATERIALIZACAO: dict[str, str] = {
    Materializacao.REVISED.value: "regimes_v1.parquet",
    Materializacao.ASOF.value: "regimes_v1_asof.parquet",
}

NOME_RELATORIO_POR_MATERIALIZACAO: dict[str, str] = {
    Materializacao.REVISED.value: "relatorio_regimes_v1.json",
    Materializacao.ASOF.value: "relatorio_regimes_v1_asof.json",
}

#: Os módulos que determinam o conteúdo de `regimes_v1`, **nesta ordem** — base de `versao_build`.
#: Mesmo critério de F-014/F-015: este módulo e o contrato da tabela. Os limiares, o enum dos 4
#: rótulos e os pisos de `n` moram no schema, então editá-lo muda o Parquet sem tocar aqui.
MODULOS_DO_REGIME_V1: tuple[str, ...] = (
    "apps.pipeline.canonical.regimes_v1",
    "packages.shared.schemas.regimes",
)

#: ADR que congela a especificação (D1 + D3). O **status em disco** decide
#: `especificacao_congelada` — ver `status_adr_001`.
CAMINHO_ADR_001 = Path("docs") / "decisions" / "adr" / "ADR-001-lente-de-regime-oficial.md"
STATUS_ADR_ACEITO = "ACEITA"
STATUS_ADR_DESCONHECIDO = "DESCONHECIDO"
VEREDITO_NAO_CONGELADA = "BLOQUEADO - ESPECIFICACAO NAO CONGELADA"
VEREDITO_CONGELADA = "ESPECIFICACAO CONGELADA (ADR-001 aceito)"

_RE_STATUS_ADR = re.compile(r"^-\s*\*\*Status:\*\*\s*(?P<valor>.+)$", re.MULTILINE)


# ─────────────────────────────────────────────────────────────────────────────
# Canários — conferidos à mão contra `macro_quarterly` (classe C, `AGENTS.md §5`)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Canario:
    """Um trimestre com `g`, `pi` e quadrante conferidos à mão, travado por teste."""

    quarter: str
    g_esperado: float | None
    pi_esperado: float
    regime_esperado: str | None
    nota: str


#: 3 canários + 1 quase-empate. Os valores vêm de `data/canonical/macro_quarterly.parquet`
#: (materialização `revised`) e foram lidos célula a célula; o teste de integração exige que a
#: tabela construída os reproduza, com tolerância de 1e-6 pp.
TOLERANCIA_CANARIO_PP = 1e-6
CANARIOS: tuple[Canario, ...] = (
    Canario(
        quarter="2008Q4",
        g_esperado=None,
        pi_esperado=-0.35,
        regime_esperado=None,
        nota=(
            "crise de 2008: ibcbr_gap NULO (D-m, a media movel de 20 trimestres so fecha em "
            "2009Q4), ipca_12m_delta = -0,35 pp (IPCA 12m 5,90 em dez/08 contra 6,25 em set/08). "
            "Um eixo ausente basta: INDETERMINADO, motivo GAP_AUSENTE. E o custo de D-m mais "
            "visivel do projeto e vai a pagina de limitacoes (F-028)."
        ),
    ),
    Canario(
        quarter="2015Q4",
        g_esperado=-6.40468,
        pi_esperado=1.18,
        regime_esperado=RegimeV1.ESTAGFLACAO.value,
        nota=(
            "recessao de 2015 com IPCA em aceleracao para 10,67% em 12m: g = -6,4047 pp (IBC-Br "
            "a/a de -5,9531% contra tendencia de +0,4515%, abaixo da tendencia) e pi = +1,18 pp "
            "(acelerando) -> ESTAGFLACAO. E o quadrante que a leitura economica do periodo exige, "
            "e o canario que pegaria sinal invertido no eixo. g era -7,0433 pp antes de D-s (nivel "
            "de fim de periodo); o rotulo NAO mudou."
        ),
    ),
    Canario(
        quarter="2021Q2",
        g_esperado=12.220736,
        pi_esperado=2.25,
        regime_esperado=RegimeV1.EXPANSAO_INFL.value,
        nota=(
            "reabertura pos-covid contra a base deprimida de 2020Q2: g = +12,2207 pp (o MAIOR da "
            "amostra, contra o menor, -9,609 pp de 2020Q2) e pi = +2,25 pp (IPCA 12m de 6,10 para "
            "8,35) -> EXPANSAO_INFL. Canario do quadrante oposto ao de 2015Q4. g era +7,9144 pp "
            "antes de D-s: a media do trimestre amplia o pico porque abril e maio de 2021 ficaram "
            "acima de junho. O rotulo NAO mudou."
        ),
    ),
    Canario(
        quarter="2023Q3",
        g_esperado=-0.029941,
        pi_esperado=2.03,
        regime_esperado=RegimeV1.ESTAGFLACAO.value,
        nota=(
            "quase-empate deliberado (o menor |g| da amostra desde D-s): g = -0,029941 pp, a 3 "
            "centesimos de pp do limiar. NAO e empate exato, logo NAO aciona CA-079 - classifica "
            "por g < 0. Esta aqui para provar que o desempate e `== 0` exato e nao uma tolerancia "
            "inventada. O papel era de 2024Q1 (g = -0,003228) antes de D-s."
        ),
    ),
    Canario(
        quarter="2024Q1",
        g_esperado=0.893048,
        pi_esperado=-0.69,
        regime_esperado=RegimeV1.RECUPERACAO.value,
        nota=(
            "canario de D-s: era o quase-empate (g = -0,003228 pp -> DESACELERACAO) com o IBC-Br "
            "lido no fim do trimestre; com a media dos 3 meses g = +0,893048 pp e o quadrante vira "
            "RECUPERACAO. E 1 dos 7 trimestres que trocam de quadrante entre as duas reguas "
            "(2013Q2, 2013Q3, 2013Q4, 2020Q1, 2023Q3, 2024Q1, 2025Q2) - exatamente os 7 que o "
            "P1-1 do QA da Onda 2 previu. Existe para que a regua de nivel nao volte em silencio."
        ),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# O núcleo: classificação pura, sem I/O
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Eixo:
    """O sinal resolvido de um eixo em T, e como se chegou nele."""

    #: `True` = acima do limiar · `False` = abaixo · `None` = não resolvido.
    sinal: bool | None
    #: `True` = o valor era **exatamente** o limiar e o sinal veio (ou tentou vir) de `T−1`.
    empate: bool
    #: `True` = o valor em T é nulo (a série não tem o número; D-m).
    ausente: bool


@dataclass(frozen=True)
class Classificacao:
    """O veredito de um trimestre: rótulo, status, motivo e a auditoria dos dois eixos."""

    quarter: str
    regime: str | None
    status: str
    motivo: str | None
    g_score: float | None
    pi_score: float | None
    crescimento_acima: bool | None
    inflacao_acelerando: bool | None
    desempate_aplicado: bool


def rotulo(*, crescimento_acima: bool, inflacao_acelerando: bool) -> RegimeV1:
    """Os 4 quadrantes do ADR-001 §5 — a tabela de verdade, e nada mais.

    >>> rotulo(crescimento_acima=True, inflacao_acelerando=False) is RegimeV1.RECUPERACAO
    True
    >>> rotulo(crescimento_acima=False, inflacao_acelerando=True) is RegimeV1.ESTAGFLACAO
    True
    """
    if crescimento_acima:
        return RegimeV1.EXPANSAO_INFL if inflacao_acelerando else RegimeV1.RECUPERACAO
    return RegimeV1.ESTAGFLACAO if inflacao_acelerando else RegimeV1.DESACELERACAO


def _ausente(valor: float | None) -> bool:
    return valor is None or pd.isna(valor)


def resolver_eixo(valor: float | None, *, limiar: float, sinal_anterior: bool | None) -> Eixo:
    """Resolve um eixo em T: acima, abaixo, ou não resolvido — com o desempate de CA-079.

    Três saídas e só três:

    - valor **nulo** → `sinal=None`, `ausente=True`. Nenhuma estimativa (Anti-SPEC §10.1.1).
    - valor **exatamente** igual ao limiar → herda `sinal_anterior`, que é o sinal **deste eixo**
      em `T−1`. Se `T−1` não tem sinal, devolve `sinal=None` com `empate=True`: o trimestre fica
      `INDETERMINADO`, nunca um default.
    - caso geral → `sinal = valor > limiar`.

    A comparação de empate é `==` exato, de propósito: `2024Q1` tem `g = -0,003228 pp` e **não** é
    empate. Uma tolerância aqui seria um parâmetro novo da especificação, e a especificação está
    congelada no ADR (Anti-SPEC §10.2.9).
    """
    if _ausente(valor):
        return Eixo(sinal=None, empate=False, ausente=True)
    numero = float(valor)  # type: ignore[arg-type]
    if numero == limiar:
        return Eixo(sinal=sinal_anterior, empate=True, ausente=False)
    return Eixo(sinal=numero > limiar, empate=False, ausente=False)


def _motivo(g: Eixo, pi: Eixo) -> str:
    """Por que o trimestre ficou sem quadrante — ausência de dado vem antes do empate."""
    if g.ausente and pi.ausente:
        return MotivoIndeterminado.AMBOS_AUSENTES.value
    if g.ausente:
        return MotivoIndeterminado.GAP_AUSENTE.value
    if pi.ausente:
        return MotivoIndeterminado.ACELERACAO_AUSENTE.value
    return MotivoIndeterminado.EMPATE_SEM_SINAL_ANTERIOR.value


def classificar_trimestres(
    quarters: Sequence[str],
    g: Sequence[float | None],
    pi: Sequence[float | None],
    *,
    limiar_crescimento: float = LIMIAR_CRESCIMENTO_PP,
    limiar_aceleracao: float = LIMIAR_ACELERACAO_PP,
) -> tuple[Classificacao, ...]:
    """A V1 inteira, pura: três sequências alinhadas em ordem crescente de trimestre, dentro.

    **Anti-look-ahead por construção** (CA-072, Anti-SPEC §10.2.7): o laço é para frente e o único
    estado que atravessa iterações é o sinal de cada eixo em `T−1`, usado **só** no empate exato.
    Nada aqui enxerga `T+1`, e o teste `test_classificacao_de_t_nao_muda_quando_t_mais_1_muda`
    mexe nas linhas futuras para provar.

    **Função pura** (CA-081): sem relógio, sem aleatoriedade, sem leitura de disco. Duas chamadas
    com a mesma entrada devolvem a mesma tupla.
    """
    if not (len(quarters) == len(g) == len(pi)):
        msg = f"sequencias de tamanhos diferentes: {len(quarters)}, {len(g)}, {len(pi)}"
        raise SerieInconsistente(msg)
    if list(quarters) != sorted(quarters):
        msg = "quarters precisam estar em ordem crescente: o desempate de CA-079 le T-1"
        raise SerieInconsistente(msg)
    if len(set(quarters)) != len(quarters):
        msg = "quarter duplicado na entrada da classificacao (a PK da tabela e `quarter`)"
        raise SerieInconsistente(msg)

    anterior_g: bool | None = None
    anterior_pi: bool | None = None
    saida: list[Classificacao] = []

    for quarter, valor_g, valor_pi in zip(quarters, g, pi, strict=True):
        eixo_g = resolver_eixo(valor_g, limiar=limiar_crescimento, sinal_anterior=anterior_g)
        eixo_pi = resolver_eixo(valor_pi, limiar=limiar_aceleracao, sinal_anterior=anterior_pi)
        desempate = eixo_g.empate or eixo_pi.empate

        if eixo_g.sinal is None or eixo_pi.sinal is None:
            saida.append(
                Classificacao(
                    quarter=str(quarter),
                    regime=None,
                    status=StatusRegimeV1.INDETERMINADO.value,
                    motivo=_motivo(eixo_g, eixo_pi),
                    g_score=None if eixo_g.ausente else float(valor_g),  # type: ignore[arg-type]
                    pi_score=None if eixo_pi.ausente else float(valor_pi),  # type: ignore[arg-type]
                    crescimento_acima=eixo_g.sinal,
                    inflacao_acelerando=eixo_pi.sinal,
                    desempate_aplicado=desempate,
                )
            )
        else:
            saida.append(
                Classificacao(
                    quarter=str(quarter),
                    regime=rotulo(
                        crescimento_acima=eixo_g.sinal, inflacao_acelerando=eixo_pi.sinal
                    ).value,
                    status=StatusRegimeV1.CLASSIFICADO.value,
                    motivo=None,
                    g_score=float(valor_g),  # type: ignore[arg-type]
                    pi_score=float(valor_pi),  # type: ignore[arg-type]
                    crescimento_acima=eixo_g.sinal,
                    inflacao_acelerando=eixo_pi.sinal,
                    desempate_aplicado=desempate,
                )
            )

        # Estritamente `T−1`: um eixo sem sinal em T apaga a herança para T+1 (ADR-001 §5).
        anterior_g, anterior_pi = eixo_g.sinal, eixo_pi.sinal

    return tuple(saida)


# ─────────────────────────────────────────────────────────────────────────────
# `n` por regime, alertas e supressão (CA-080, CA-108, CA-109)
# ─────────────────────────────────────────────────────────────────────────────


def contagem_por_grupo(classificacoes: Iterable[Classificacao]) -> dict[str, int]:
    """`n` por grupo, onde o grupo é o quadrante ou `INDETERMINADO`.

    O `n` dos indeterminados é contado e publicado em vez de escondido: é o número que torna
    "a V1 classifica 67 dos 83" verificável no dado, e `RegimesV1Schema` exige `n >= 1` em toda
    linha — nenhuma célula desta tabela sai sem `n` (Anti-SPEC §10.2.8).
    """
    contagem: dict[str, int] = {}
    for item in classificacoes:
        chave = item.regime or StatusRegimeV1.INDETERMINADO.value
        contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def alerta_n_baixo(n: int) -> bool:
    """`n < N_ALERTA` (8) — flag `ALERTA_N_BAIXO` de CA-108."""
    return n < N_ALERTA


def conclusao_suprimida(n: int) -> bool:
    """`n < N_SUPRESSAO` (5) — nenhuma conclusão afirmativa sobre a célula (CA-109)."""
    return n < N_SUPRESSAO


def alerta_desbalanceamento(n: int) -> bool:
    """`n` fora de [10, 35] — o alerta de desbalanceamento de CA-080."""
    return not (N_QUADRANTE_MINIMO_CA080 <= n <= N_QUADRANTE_MAXIMO_CA080)


# ─────────────────────────────────────────────────────────────────────────────
# Gate de publicação: o status do ADR-001, lido do disco (CA-090)
# ─────────────────────────────────────────────────────────────────────────────


def status_adr_001(*, raiz: Path | None = None) -> str:
    """O status do ADR-001 como está **em disco**, em maiúsculas (`PROPOSTA`, `ACEITA`, ...).

    Falha fechada: arquivo ausente, ilegível ou sem a linha `- **Status:** ...` devolve
    `DESCONHECIDO`, que **não** congela a especificação. Nunca o contrário.
    """
    alvo = (raiz or raiz_repo()) / CAMINHO_ADR_001
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        _log.warning("ADR-001 ilegivel em %s: especificacao tratada como NAO congelada", alvo)
        return STATUS_ADR_DESCONHECIDO
    achado = _RE_STATUS_ADR.search(texto)
    if achado is None:
        _log.warning("ADR-001 sem linha de Status reconhecivel: tratado como NAO congelado")
        return STATUS_ADR_DESCONHECIDO
    bruto = achado.group("valor").replace("*", " ")
    primeira = re.split(r"[\s—\-:,.]+", bruto.strip(), maxsplit=1)[0]
    return primeira.strip().upper() or STATUS_ADR_DESCONHECIDO


def especificacao_esta_congelada(*, raiz: Path | None = None) -> bool:
    """`True` só se o ADR-001 estiver **Aceita** em disco (CA-090, `AGENTS.md §9`)."""
    return status_adr_001(raiz=raiz) == STATUS_ADR_ACEITO


def veredito_publicacao(congelada: bool) -> str:
    """O texto que vai ao relatório e ao stdout — o `BLOQUEADO` de `AGENTS.md §9` por escrito."""
    return VEREDITO_CONGELADA if congelada else VEREDITO_NAO_CONGELADA


# ─────────────────────────────────────────────────────────────────────────────
# Da classificação para a tabela
# ─────────────────────────────────────────────────────────────────────────────


def exigir_colunas(macro: pd.DataFrame) -> None:
    """As 4 colunas que a V1 consome existem? Senão, falha nomeando o que falta."""
    faltando = [c for c in COLUNAS_EXIGIDAS_NA_ENTRADA if c not in macro.columns]
    if faltando:
        msg = f"entrada sem as colunas que a V1 consome: {faltando}"
        raise SerieInconsistente(msg)


def materializacao_da_entrada(macro: pd.DataFrame) -> Materializacao:
    """Lê `lag_adjusted` da entrada — a tabela nunca mistura as duas (CA-072)."""
    valores = set(macro["lag_adjusted"].astype(bool).unique())
    if len(valores) != 1:
        msg = "entrada mistura `asof` e `revised` na mesma tabela (CA-072)"
        raise SerieInconsistente(msg)
    return Materializacao.ASOF if valores.pop() else Materializacao.REVISED


def classificar(
    macro: pd.DataFrame,
    *,
    limiar_crescimento: float = LIMIAR_CRESCIMENTO_PP,
    limiar_aceleracao: float = LIMIAR_ACELERACAO_PP,
    congelada: bool = False,
    versao_especificacao: str = VERSAO_ESPECIFICACAO_V1,
    fonte_versao: str | None = None,
    rotulos_revised: dict[str, str | None] | None = None,
) -> pd.DataFrame:
    """Classifica uma materialização de `macro_quarterly` e devolve a tabela de `RegimesV1Schema`.

    `rotulos_revised` só é usado na materialização `asof`: `{quarter: regime_v1 da revised}`
    preenche `trocou_vs_revised` por trimestre (CA-073). Em `revised` a coluna fica **nula** — não
    existe "trocou em relação a si mesma", e inventar `False` ali faria a média de CA-073 parecer
    calculada quando não foi.
    """
    exigir_colunas(macro)
    materializacao = materializacao_da_entrada(macro)
    ordenado = macro.sort_values("quarter", kind="stable").reset_index(drop=True)

    classificacoes = classificar_trimestres(
        ordenado["quarter"].astype(str).tolist(),
        [None if pd.isna(v) else float(v) for v in ordenado[COLUNA_CRESCIMENTO]],
        [None if pd.isna(v) else float(v) for v in ordenado[COLUNA_INFLACAO]],
        limiar_crescimento=limiar_crescimento,
        limiar_aceleracao=limiar_aceleracao,
    )
    contagem = contagem_por_grupo(classificacoes)
    versao = fonte_versao if fonte_versao is not None else versao_build()

    def _trocou(item: Classificacao) -> bool | None:
        if materializacao is not Materializacao.ASOF or rotulos_revised is None:
            return None
        if item.quarter not in rotulos_revised:
            return None
        return rotulos_revised[item.quarter] != item.regime

    linhas = []
    for item in classificacoes:
        n = contagem[item.regime or StatusRegimeV1.INDETERMINADO.value]
        linhas.append(
            {
                "quarter": item.quarter,
                "regime_v1": item.regime,
                "status_regime_v1": item.status,
                "motivo_indeterminado": item.motivo,
                "g_score": item.g_score,
                "pi_score": item.pi_score,
                "crescimento_acima": item.crescimento_acima,
                "inflacao_acelerando": item.inflacao_acelerando,
                "desempate_aplicado": item.desempate_aplicado,
                "n_obs_regime_v1": n,
                "alerta_n_baixo": alerta_n_baixo(n),
                "conclusao_suprimida": conclusao_suprimida(n),
                "alerta_desbalanceamento": alerta_desbalanceamento(n),
                "lag_adjusted": materializacao is Materializacao.ASOF,
                "trocou_vs_revised": _trocou(item),
                "especificacao_congelada": congelada,
                "versao_especificacao": versao_especificacao,
                "fonte_versao": versao,
            }
        )

    quadro = pd.DataFrame(linhas)
    for coluna in ("crescimento_acima", "inflacao_acelerando", "trocou_vs_revised"):
        quadro[coluna] = pd.array(quadro[coluna].tolist(), dtype="boolean")
    return RegimesV1Schema.validate(quadro, lazy=True)  # type: ignore[return-value]


def rotulos_de(regimes: pd.DataFrame) -> dict[str, str | None]:
    """`{quarter: regime_v1}` de uma tabela de regimes — nulo preservado como `None`."""
    return {
        str(q): (None if pd.isna(r) else str(r))
        for q, r in zip(regimes["quarter"], regimes["regime_v1"], strict=True)
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sensibilidade e divergência entre materializações
# ─────────────────────────────────────────────────────────────────────────────


def sensibilidade_limiar_aceleracao(
    macro: pd.DataFrame,
    *,
    deslocamento_pp: float = SENSIBILIDADE_ACELERACAO_PP,
) -> dict[str, Any]:
    """Quantos trimestres trocam de rótulo se o limiar da aceleração andar ±`deslocamento_pp`.

    É o teste de robustez do único limiar livre da V1. O eixo de crescimento tem limiar 0 por
    definição do hiato (o hiato **é** o desvio da tendência), mas "aceleração > 0" é uma escolha:
    deslocar para +0,1 pp exige aceleração mínima para contar como acelerando, e para −0,1 pp
    tolera uma desaceleração pequena como aceleração. **Reportado, nunca usado para escolher o
    limiar** (Anti-SPEC §10.2.9 — a especificação está congelada no ADR).
    """
    exigir_colunas(macro)
    ordenado = macro.sort_values("quarter", kind="stable").reset_index(drop=True)
    quarters = ordenado["quarter"].astype(str).tolist()
    g = [None if pd.isna(v) else float(v) for v in ordenado[COLUNA_CRESCIMENTO]]
    pi = [None if pd.isna(v) else float(v) for v in ordenado[COLUNA_INFLACAO]]

    base = {c.quarter: c.regime for c in classificar_trimestres(quarters, g, pi)}
    saida: dict[str, Any] = {
        "limiar_base_pp": LIMIAR_ACELERACAO_PP,
        "deslocamento_pp": deslocamento_pp,
        "trimestres_na_amostra": len(quarters),
        "variantes": {},
    }
    for sinal in (+1.0, -1.0):
        limiar = LIMIAR_ACELERACAO_PP + sinal * deslocamento_pp
        alternativo = classificar_trimestres(quarters, g, pi, limiar_aceleracao=limiar)
        trocas = [
            {"quarter": c.quarter, "de": base[c.quarter], "para": c.regime}
            for c in alternativo
            if base[c.quarter] != c.regime
        ]
        saida["variantes"][f"{limiar:+.2f}"] = {
            "limiar_pp": limiar,
            "trimestres_que_trocam": len(trocas),
            "pct_que_trocam": round(len(trocas) / len(quarters), 6) if quarters else None,
            "trocas": trocas,
            "distribuicao": contagem_por_grupo(alternativo),
        }
    maximo = max(
        (v["trimestres_que_trocam"] for v in saida["variantes"].values()),
        default=0,
    )
    saida["max_trimestres_que_trocam"] = maximo
    saida["max_pct_que_trocam"] = round(maximo / len(quarters), 6) if quarters else None
    return saida


def divergencia_entre_materializacoes(revised: pd.DataFrame, asof: pd.DataFrame) -> dict[str, Any]:
    """% de trimestres que trocam de rótulo entre `revised` e `asof` (CA-073/CA-074).

    Só compara trimestres que as **duas** materializações classificam: um trimestre indeterminado
    de um lado e rotulado do outro é contado em `trocas_com_indeterminado` e fica **fora** do
    percentual, porque "trocou de regime" e "deixou de ter regime" são achados diferentes e
    somá-los inflaria ou deflaria o número de CA-074 sem que ninguém notasse.
    """
    esquerda = rotulos_de(revised)
    direita = rotulos_de(asof)
    comuns = sorted(set(esquerda) & set(direita))

    ambos_rotulados = [q for q in comuns if esquerda[q] is not None and direita[q] is not None]
    trocaram = [
        {"quarter": q, "revised": esquerda[q], "asof": direita[q]}
        for q in ambos_rotulados
        if esquerda[q] != direita[q]
    ]
    com_indeterminado = [
        {"quarter": q, "revised": esquerda[q], "asof": direita[q]}
        for q in comuns
        if (esquerda[q] is None) != (direita[q] is None)
    ]
    pct = len(trocaram) / len(ambos_rotulados) if ambos_rotulados else None
    inoperante = bool(pct is not None and pct > LIMIAR_TROCA_REGIME_INOPERANTE)
    return {
        "trimestres_comparaveis": len(ambos_rotulados),
        "trimestres_que_trocam": len(trocaram),
        "pct_que_trocam": round(pct, 6) if pct is not None else None,
        "limiar_inoperante": LIMIAR_TROCA_REGIME_INOPERANTE,
        "modelo_operacional": None if pct is None else not inoperante,
        "trocas": trocaram,
        "trocas_com_indeterminado": com_indeterminado,
        "texto": (
            "a troca de rotulo entre revised e asof passa de "
            f"{LIMIAR_TROCA_REGIME_INOPERANTE:.0%}: o modelo NAO e operacional nesta forma "
            "(CA-074, hipotese H-03 do PRD caiu)"
            if inoperante
            else (
                "troca de rotulo entre revised e asof dentro do limiar de "
                f"{LIMIAR_TROCA_REGIME_INOPERANTE:.0%} (CA-073)"
                if pct is not None
                else "nenhum trimestre comparavel entre as duas materializacoes"
            )
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Leitura, hash e relatório
# ─────────────────────────────────────────────────────────────────────────────


def versao_build(modulos: Sequence[str] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DO_REGIME_V1` — o `fonte_versao` desta tabela (CA-088).

    Hash de arquivos, não do processo (RF-047/CA-121), reusando o algoritmo de F-013: o conjunto
    inclui o schema porque os limiares, o enum dos 4 rótulos e os pisos de `n` moram lá.
    """
    return _hash_dos_componentes(caminhos_dos_componentes(modulos or MODULOS_DO_REGIME_V1))


def ler_macro(
    *,
    materializacao: Materializacao = Materializacao.REVISED,
    raiz: Path | None = None,
) -> pd.DataFrame:
    """Lê e **valida** `macro_quarterly` da materialização pedida. Ausente = falha explícita."""
    nome = NOME_MACRO_POR_MATERIALIZACAO[Materializacao(materializacao).value]
    alvo = caminho_canonical(nome, raiz=raiz)
    if not alvo.is_file():
        como = (
            "rode `uv run python -m apps.pipeline.canonical.macro_quarterly` (F-015)"
            if materializacao is Materializacao.REVISED
            else "a materializacao `asof` e de F-018 e ainda nao existe em disco"
        )
        msg = f"BLOQUEADO — FONTE INDISPONÍVEL: {alvo} não existe. {como}."
        raise FonteIndisponivel(msg)
    quadro = pd.read_parquet(alvo)
    try:
        return MacroQuarterlySchema.validate(quadro, lazy=True)  # type: ignore[return-value]
    except Exception as erro:  # pandera: SchemaError/SchemaErrors
        msg = f"{alvo.name} não satisfaz macro_quarterly: {erro}"
        raise SerieInconsistente(msg) from erro


def macro_asof_disponivel(*, raiz: Path | None = None) -> bool:
    """`macro_quarterly_asof.parquet` (F-018) já existe em disco?"""
    nome = NOME_MACRO_POR_MATERIALIZACAO[Materializacao.ASOF.value]
    return caminho_canonical(nome, raiz=raiz).is_file()


def timeline(regimes: pd.DataFrame) -> list[dict[str, Any]]:
    """`ano-trimestre -> regime` em ordem, com os dois escores — a timeline legível de RF-035."""
    ordenado = regimes.sort_values("quarter", kind="stable")
    return [
        {
            "quarter": str(linha.quarter),
            "regime": None if pd.isna(linha.regime_v1) else str(linha.regime_v1),
            "status": str(linha.status_regime_v1),
            "g_score": None if pd.isna(linha.g_score) else round(float(linha.g_score), 6),
            "pi_score": None if pd.isna(linha.pi_score) else round(float(linha.pi_score), 6),
        }
        for linha in ordenado.itertuples(index=False)
    ]


def trimestres_por_regime(regimes: pd.DataFrame) -> dict[str, list[str]]:
    """`{regime: [quarters]}`, com os indeterminados sob a chave `INDETERMINADO`."""
    saida: dict[str, list[str]] = {}
    ordenado = regimes.sort_values("quarter", kind="stable")
    for linha in ordenado.itertuples(index=False):
        chave = (
            StatusRegimeV1.INDETERMINADO.value if pd.isna(linha.regime_v1) else str(linha.regime_v1)
        )
        saida.setdefault(chave, []).append(str(linha.quarter))
    return saida


def distribuicao(regimes: pd.DataFrame) -> dict[str, Any]:
    """`n` por regime + os três alertas por célula (CA-080, CA-108, CA-109)."""
    por_regime = trimestres_por_regime(regimes)
    quadrantes = {k: v for k, v in por_regime.items() if k != StatusRegimeV1.INDETERMINADO.value}
    blocos = {
        nome: {
            "n": len(quarters),
            "alerta_n_baixo": alerta_n_baixo(len(quarters)),
            "conclusao_suprimida": conclusao_suprimida(len(quarters)),
            "alerta_desbalanceamento": alerta_desbalanceamento(len(quarters)),
        }
        for nome, quarters in sorted(por_regime.items())
    }
    ns = [len(v) for v in quadrantes.values()]
    return {
        "por_grupo": blocos,
        "quadrantes_povoados": len(quadrantes),
        "quadrantes_esperados": len(RegimeV1),
        "n_minimo_quadrante": min(ns) if ns else None,
        "n_maximo_quadrante": max(ns) if ns else None,
        "faixa_ca080": [N_QUADRANTE_MINIMO_CA080, N_QUADRANTE_MAXIMO_CA080],
        "desbalanceamento_ca080": any(alerta_desbalanceamento(len(v)) for v in quadrantes.values()),
        "desbalanceamento_relativo": (round(max(ns) / min(ns), 4) if ns and min(ns) > 0 else None),
    }


def bloco_indeterminados(regimes: pd.DataFrame) -> dict[str, Any]:
    """Quem ficou sem quadrante, e por quê — o custo de D-m, publicado."""
    fatia = regimes.loc[regimes["regime_v1"].isna()].sort_values("quarter", kind="stable")
    motivos: dict[str, list[str]] = {}
    for linha in fatia.itertuples(index=False):
        motivos.setdefault(str(linha.motivo_indeterminado), []).append(str(linha.quarter))
    return {
        "n": int(len(fatia)),
        "pct_da_amostra": round(len(fatia) / len(regimes), 6) if len(regimes) else None,
        "trimestres": [str(q) for q in fatia["quarter"]],
        "por_motivo": {k: v for k, v in sorted(motivos.items())},
        "motivo_de_fundo": (
            "D-m (DECISIONS_LOG 2.3, TODO.md 4): ibcbr_gap e nulo em 2006Q1..2009Q3 e 2026Q3 "
            "porque a media movel de 20 trimestres com janela cheia so fecha em 2009Q4 e o "
            "IBC-Br dessaz. (SGS 24364) comeca em 2003; 2026Q3 e nulo porque a media do trimestre "
            "(D-s) exige 3 meses e o IBC-Br vai ate jul/2026. Nenhuma estimativa no lugar "
            "(Anti-SPEC 10.1.1). Consequencia: a crise de 2008 fica fora do eixo de crescimento "
            "da V1 — vai a pagina de limitacoes (F-028)."
        ),
    }


def bloco_canarios(regimes: pd.DataFrame) -> dict[str, Any]:
    """Os canários como estão na tabela construída, ao lado do que foi conferido à mão."""
    indexado = regimes.set_index("quarter")
    saida: dict[str, Any] = {}
    for canario in CANARIOS:
        if canario.quarter not in indexado.index:
            saida[canario.quarter] = {"ausente": True, "nota": canario.nota}
            continue
        linha = indexado.loc[canario.quarter]
        saida[canario.quarter] = {
            "g_score": None if pd.isna(linha["g_score"]) else round(float(linha["g_score"]), 6),
            "g_esperado": canario.g_esperado,
            "pi_score": None if pd.isna(linha["pi_score"]) else round(float(linha["pi_score"]), 6),
            "pi_esperado": canario.pi_esperado,
            "regime": None if pd.isna(linha["regime_v1"]) else str(linha["regime_v1"]),
            "regime_esperado": canario.regime_esperado,
            "status": str(linha["status_regime_v1"]),
            "nota": canario.nota,
        }
    return saida


def montar_relatorio(
    *,
    regimes: pd.DataFrame,
    materializacao: Materializacao,
    congelada: bool,
    status_adr: str,
    sensibilidade: dict[str, Any],
    divergencia: dict[str, Any] | None,
    motivo_divergencia: str,
    hashes: dict[str, Any],
) -> dict[str, Any]:
    """O `relatorio_regimes_v1.json` — tudo que a revisão numérica de classe C precisa ler."""
    quarters = sorted(str(q) for q in regimes["quarter"])
    return {
        "regimes_v1": {
            "linhas": int(len(regimes)),
            "colunas": int(regimes.shape[1]),
            "materializacao": Materializacao(materializacao).value,
            "lag_adjusted": bool(regimes["lag_adjusted"].iloc[0]),
            "primeiro_trimestre": quarters[0] if quarters else None,
            "ultimo_trimestre": quarters[-1] if quarters else None,
            "classificados": int(regimes["regime_v1"].notna().sum()),
            "indeterminados": int(regimes["regime_v1"].isna().sum()),
            "desempates_aplicados": int(regimes["desempate_aplicado"].sum()),
            "sha256": hashes["sha256_regimes"],
            "bytes": hashes["bytes_regimes"],
        },
        "especificacao": {
            "adr": "ADR-001 — lente de regime oficial e eixos da V1",
            "adr_status_em_disco": status_adr,
            "especificacao_congelada": congelada,
            "veredito_publicacao": veredito_publicacao(congelada),
            "versao_especificacao": str(regimes["versao_especificacao"].iloc[0]),
            "decisoes_provisorias": ["D1 (lente oficial = V1)", "D3 (eixo inflacao = aceleracao)"],
            "regras": {
                "eixo_crescimento": (
                    f"g_T = macro_quarterly.{COLUNA_CRESCIMENTO} (IBC-Br a/a dessaz. menos media "
                    "movel de 20 trimestres, com o nivel trimestral = MEDIA DOS 3 MESES do "
                    "trimestre desde D-s, nao o fim de periodo), em pp; crescimento_acima = g_T > "
                    f"{LIMIAR_CRESCIMENTO_PP}"
                ),
                "eixo_inflacao": (
                    f"pi_T = macro_quarterly.{COLUNA_INFLACAO} (IPCA 12m em T menos IPCA 12m em "
                    f"T-1 — aceleracao, D3), em pp; inflacao_acelerando = pi_T > "
                    f"{LIMIAR_ACELERACAO_PP}"
                ),
                "quadrantes": {
                    RegimeV1.RECUPERACAO.value: "g acima, pi desacelerando",
                    RegimeV1.EXPANSAO_INFL.value: "g acima, pi acelerando",
                    RegimeV1.ESTAGFLACAO.value: "g abaixo, pi acelerando",
                    RegimeV1.DESACELERACAO.value: "g abaixo, pi desacelerando",
                },
                "desempate": (
                    "eixo exatamente igual ao limiar herda o sinal DAQUELE eixo em T-1 (CA-079); "
                    "se T-1 nao tem sinal, o trimestre e INDETERMINADO com motivo "
                    "EMPATE_SEM_SINAL_ANTERIOR. Comparacao `== limiar` exata, sem tolerancia."
                ),
                "indeterminado": (
                    "eixo nulo em T -> regime_v1 NULL + status INDETERMINADO + motivo. Nunca "
                    "estimativa, interpolacao ou quadrante 'mais provavel' (Anti-SPEC 10.1.1)."
                ),
                "n_por_celula": (
                    f"n < {N_ALERTA} -> alerta_n_baixo (CA-108); n < {N_SUPRESSAO} -> "
                    f"conclusao_suprimida (CA-109); n fora de "
                    f"[{N_QUADRANTE_MINIMO_CA080}, {N_QUADRANTE_MAXIMO_CA080}] -> "
                    "alerta_desbalanceamento (CA-080)"
                ),
            },
        },
        "distribuicao": distribuicao(regimes),
        "trimestres_por_regime": trimestres_por_regime(regimes),
        "indeterminados": bloco_indeterminados(regimes),
        "timeline": timeline(regimes),
        "canarios": bloco_canarios(regimes),
        "sensibilidade_limiar_aceleracao": sensibilidade,
        "divergencia_asof_vs_revised": divergencia,
        "motivo_divergencia": motivo_divergencia,
        "anti_look_ahead": {
            "regra": (
                "a classificacao de T le somente a linha T da materializacao recebida "
                "(g_score, pi_score) e, no empate exato, o sinal ja resolvido de T-1. Nenhum "
                "caminho le T+1."
            ),
            "n_e_estatistica_da_amostra_inteira": True,
            "nota_sobre_n": (
                "n_obs_regime_v1 conta a amostra completa de proposito (leitura descritiva 'onde "
                "estamos no historico', metodologia 2 principio 4). Nao entra na classificacao de "
                "nenhum T; quem fizer backtest precisa de janela expanding (fora de escopo, "
                "Anti-SPEC 10.3.16)."
            ),
            "materializacao_desta_rodada": Materializacao(materializacao).value,
        },
        "descritivo_nao_preditivo": (
            "Anti-SPEC 10.2.10: esta tabela diz em que quadrante cada trimestre CAIU. Nao e "
            "previsao de regime nem de retorno."
        ),
        "modulos_da_versao": list(MODULOS_DO_REGIME_V1),
        "versao_build": hashes["versao_build"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResultadoRegimesV1:
    """O que `construir` devolve: a tabela, o relatório e onde cada coisa foi gravada."""

    regimes: pd.DataFrame
    relatorio: dict[str, Any]
    materializacao: Materializacao
    caminho_regimes: Path | None
    caminho_relatorio: Path | None


def construir(
    *,
    raiz: Path | None = None,
    materializacao: Materializacao = Materializacao.REVISED,
    gravar: bool = True,
) -> ResultadoRegimesV1:
    """Classifica os 83 trimestres e materializa `regimes_v1` + o relatório.

    Sem rede, sem relógio, sem efeito fora de `data/canonical/`. `gravar=False` existe para o
    teste rodar a classificação real sem tocar o disco.
    """
    materializacao = Materializacao(materializacao)
    macro = ler_macro(materializacao=materializacao, raiz=raiz)
    congelada = especificacao_esta_congelada(raiz=raiz)
    status = status_adr_001(raiz=raiz)
    if not congelada:
        _log.warning(
            "%s: ADR-001 esta em '%s' — especificacao_congelada=False e nenhum numero desta "
            "tabela e publicavel (CA-090, AGENTS.md 9/14)",
            VEREDITO_NAO_CONGELADA,
            status,
        )

    rotulos_revised: dict[str, str | None] | None = None
    motivo_divergencia = ""
    outra: pd.DataFrame | None = None
    if materializacao is Materializacao.ASOF:
        base = classificar(
            ler_macro(materializacao=Materializacao.REVISED, raiz=raiz), congelada=congelada
        )
        rotulos_revised = rotulos_de(base)
        outra = base
        motivo_divergencia = "comparado contra a materializacao revised em disco"

    regimes = classificar(macro, congelada=congelada, rotulos_revised=rotulos_revised)

    if materializacao is Materializacao.REVISED:
        if macro_asof_disponivel(raiz=raiz):
            outra = classificar(
                ler_macro(materializacao=Materializacao.ASOF, raiz=raiz), congelada=congelada
            )
            divergencia = divergencia_entre_materializacoes(regimes, outra)
            motivo_divergencia = (
                "macro_quarterly_asof.parquet existe em disco: a divergencia e informativa nesta "
                "rodada e a coluna trocou_vs_revised fica nula (ela so faz sentido nas linhas asof)"
            )
        else:
            divergencia = None
            motivo_divergencia = (
                "macro_quarterly_asof.parquet nao existe: F-018 ainda nao materializou a variante "
                "asof, logo CA-073/CA-074 nao tem numero nesta rodada. Nenhum percentual foi "
                "estimado no lugar."
            )
    else:
        divergencia = (
            divergencia_entre_materializacoes(outra, regimes) if outra is not None else None
        )

    caminho_regimes: Path | None = None
    caminho_relatorio: Path | None = None
    if gravar:
        caminho_regimes = caminho_canonical(
            NOME_REGIMES_POR_MATERIALIZACAO[materializacao.value], raiz=raiz
        )
        caminho_regimes.parent.mkdir(parents=True, exist_ok=True)
        regimes.to_parquet(caminho_regimes, index=False)
        corpo = caminho_regimes.read_bytes()
    else:
        corpo = regimes.to_parquet(index=False)

    relatorio = montar_relatorio(
        regimes=regimes,
        materializacao=materializacao,
        congelada=congelada,
        status_adr=status,
        sensibilidade=sensibilidade_limiar_aceleracao(macro),
        divergencia=divergencia,
        motivo_divergencia=motivo_divergencia,
        hashes={
            "sha256_regimes": sha256_de(corpo),
            "bytes_regimes": len(corpo),
            "versao_build": versao_build(),
        },
    )

    if gravar:
        caminho_relatorio = caminho_canonical(
            NOME_RELATORIO_POR_MATERIALIZACAO[materializacao.value], raiz=raiz
        )
        caminho_relatorio.write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _log.info(
            "gravado %s (%d linhas, %d classificados, sha256=%s...)",
            caminho_regimes.name if caminho_regimes else "-",
            len(regimes),
            relatorio["regimes_v1"]["classificados"],
            sha256_de(corpo)[:12],
        )

    return ResultadoRegimesV1(
        regimes=regimes,
        relatorio=relatorio,
        materializacao=materializacao,
        caminho_regimes=caminho_regimes,
        caminho_relatorio=caminho_relatorio,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.regimes_v1",
        description=(
            "Materializa data/canonical/regimes_v1.parquet + relatorio_regimes_v1.json a partir "
            "de macro_quarterly (F-015). Nunca toca a rede. Enquanto ADR-001 estiver em Proposta, "
            "especificacao_congelada=False e nenhum numero daqui e publicavel (CA-090)."
        ),
    )
    parser.add_argument(
        "--materializacao",
        choices=[m.value for m in Materializacao],
        default=Materializacao.REVISED.value,
        help="revised (default, serie de hoje) ou asof (respeita a defasagem — F-018).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Aceito por simetria com os extratores e sem efeito: esta camada só lê o disco.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = build feito; `1` = falha explícita e nada gravado."""
    args = _parser().parse_args(argv)
    configurar_logging()
    try:
        resultado = construir(materializacao=Materializacao(args.materializacao))
    except ErroDeExtracao as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 1

    relatorio = resultado.relatorio
    bloco = relatorio["regimes_v1"]
    espec = relatorio["especificacao"]
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 (Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{bloco['linhas']} trimestres | {bloco['classificados']} classificados | "
        f"{bloco['indeterminados']} indeterminados | {bloco['materializacao']} | "
        f"sha256 {bloco['sha256']}"
    )
    print(f"ADR-001 em disco: {espec['adr_status_em_disco']} -> {espec['veredito_publicacao']}")
    for nome, celula in relatorio["distribuicao"]["por_grupo"].items():
        flags = [
            rotulo_flag
            for rotulo_flag, ligado in (
                ("alerta_n_baixo", celula["alerta_n_baixo"]),
                ("conclusao_suprimida", celula["conclusao_suprimida"]),
                ("desbalanceado", celula["alerta_desbalanceamento"]),
            )
            if ligado
        ]
        print(f"  {nome}: n={celula['n']}{' [' + ', '.join(flags) + ']' if flags else ''}")
    for quarter, canario in sorted(relatorio["canarios"].items()):
        print(
            f"canario {quarter}: g={canario.get('g_score')} pi={canario.get('pi_score')} "
            f"-> {canario.get('regime')} (esperado {canario.get('regime_esperado')})"
        )
    sens = relatorio["sensibilidade_limiar_aceleracao"]
    print(
        f"sensibilidade +/-{sens['deslocamento_pp']} pp no limiar da aceleracao: no maximo "
        f"{sens['max_trimestres_que_trocam']} trimestres trocam "
        f"({sens['max_pct_que_trocam']:.4%})"
    )
    div = relatorio["divergencia_asof_vs_revised"]
    if div is None:
        print(f"divergencia asof vs revised: nao calculada - {relatorio['motivo_divergencia']}")
    else:
        print(
            f"divergencia asof vs revised: {div['trimestres_que_trocam']}/"
            f"{div['trimestres_comparaveis']} trocam ({div['pct_que_trocam']:.4%}) | "
            f"{div['texto']}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
