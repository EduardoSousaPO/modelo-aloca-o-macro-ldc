"""Schemas de `regimes` e `regime_neighbors` — classificação macro por três lentes.

Fonte de verdade do contrato (SPEC RF-027..RF-031, RF-036, RF-039; CA-078..091, CA-101..107).
Base de desenho: `docs/research/metodologia-regimes-macro.md §2 e §6.4`.

**Classe C.** A especificação de V1/V2/V3 é **congelada em ADR antes de rodar sobre os retornos**
(RF-031). Enquanto `ADR-001` estiver com status *Proposta*, o número não é publicável.

`[PROVISÓRIO D1]` V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário.
`[PROVISÓRIO D3]` eixo inflação = **aceleração** (delta do IPCA 12m), não desvio da meta.
"""

from __future__ import annotations

from enum import StrEnum

import pandera as pa
from pandera.typing import Series

QUARTER_REGEX = r"^(200[6-9]|20[1-2][0-9])Q[1-4]$"

K_VIZINHOS_PADRAO = 8
K_VIZINHOS_SENSIBILIDADE: tuple[int, ...] = (5, 8, 12)
N_TRIMESTRES_EXCLUIDOS_VIZINHANCA = 2
LIMIAR_SELIC_PP = 0.25
N_ALERTA = 8
N_SUPRESSAO = 5
LIMIAR_TROCA_REGIME_INOPERANTE = 0.25


class RegimeV1(StrEnum):
    """Quadrantes crescimento x inflação (RF-027)."""

    RECUPERACAO = "RECUPERACAO"
    EXPANSAO_INFL = "EXPANSAO_INFL"
    ESTAGFLACAO = "ESTAGFLACAO"
    DESACELERACAO = "DESACELERACAO"


class CicloSelic(StrEnum):
    """Camada de política monetária (RF-028)."""

    CORTE = "CORTE"
    ALTA = "ALTA"
    NEUTRO = "NEUTRO"


class MetricaDistancia(StrEnum):
    """Métrica da V3 (RF-029)."""

    MAHALANOBIS = "mahalanobis"
    EUCLIDIANA = "euclidiana"


FEATURES_V3: tuple[str, ...] = (
    "z_ibcbr_gap",
    "z_ipca_desvio_meta",
    "z_juro_real_exante",
    "z_inclinacao",
    "z_usdbrl_var_12m",
    "z_termos_troca_yoy",
)


class RegimesSchema(pa.DataFrameModel):
    """Rótulos e escores por trimestre. PK: `quarter`."""

    quarter: Series[str] = pa.Field(nullable=False, unique=True, str_matches=QUARTER_REGEX)
    regime_v1: Series[str] = pa.Field(nullable=False, isin=tuple(r.value for r in RegimeV1))
    regime_v1b: Series[str] = pa.Field(
        nullable=True,
        description="Versão vs. Focus — fase 2 (D2); nulo na v1, nunca copiado de regime_v1.",
    )
    ciclo_selic: Series[str] = pa.Field(nullable=False, isin=tuple(c.value for c in CicloSelic))
    regime_v2: Series[str] = pa.Field(
        nullable=False, description="regime_v1 + '_' + ciclo_selic — corte secundário (CA-083)."
    )
    stress_flag: Series[bool] = pa.Field(
        nullable=False,
        description="Inclinação cai > 1 d.p. OU USDBRL sobe > 10% no trimestre (RF-039).",
    )
    g_score: Series[float] = pa.Field(nullable=True)
    pi_score: Series[float] = pa.Field(nullable=True)
    n_obs_regime_v1: Series[int] = pa.Field(
        nullable=False, ge=1, description="`n` do quadrante — vai para toda célula de toda tabela."
    )
    alerta_n_baixo: Series[bool] = pa.Field(nullable=False)
    lag_adjusted: Series[bool] = pa.Field(
        nullable=False, description="True = classificado sobre `macro_quarterly_asof` (CA-072)."
    )
    trocou_vs_revised: Series[bool] = pa.Field(
        nullable=True,
        description="True = o rótulo difere da variante `revised`; a média alimenta CA-073/074.",
    )
    especificacao_congelada: Series[bool] = pa.Field(
        nullable=False, description="False enquanto ADR-001 estiver em status Proposta (CA-090)."
    )
    versao_especificacao: Series[str] = pa.Field(
        nullable=False, description="'V1' | 'V1.1' — mudança posterior nunca sobrescreve (CA-091)."
    )
    fonte_versao: Series[str] = pa.Field(
        nullable=False, description="Hash do código que gerou a classificação (CA-088)."
    )

    class Config:
        """Configuração do schema."""

        name = "regimes"
        strict = True
        coerce = True
        unique = ["quarter"]

    @pa.dataframe_check(name="todos_os_quadrantes_povoados")
    def _quadrantes_povoados(cls, df: object) -> bool:  # noqa: N805
        """Os 4 quadrantes da V1 existem na amostra (CA-078/080)."""
        return int(df["regime_v1"].nunique()) == len(RegimeV1)  # type: ignore[index]


class RegimeNeighborsSchema(pa.DataFrameModel):
    """Saída da V3: os k trimestres mais parecidos. PK: (quarter_ref, rank, metrica)."""

    quarter_ref: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    rank: Series[int] = pa.Field(nullable=False, ge=1, le=12)
    quarter_neighbor: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    distancia: Series[float] = pa.Field(nullable=False, ge=0)
    metrica: Series[str] = pa.Field(nullable=False, isin=tuple(m.value for m in MetricaDistancia))
    k_usado: Series[int] = pa.Field(nullable=False, isin=K_VIZINHOS_SENSIBILIDADE)
    # Piso 3, não 5: o `ge=5` rejeitava o único cenário de corte que o `PLAN.md §5` prevê como
    # aceitável. Os cortes 4 (F-010/Focus → cai `z_juro_real_exante`) e 5 (F-016/curva → cai
    # `z_inclinacao`) são independentes e podem acontecer juntos, sobrando 4 das 6 features; com
    # G-02 (`ipca_meta`, "fora do caminho crítico" na `SPEC.md §13`) ainda aberto, cai também
    # `z_ipca_desvio_meta` e sobram 3. 3 é o piso: abaixo disso a V3 não é "momentos semelhantes",
    # é ruído — aí o caminho é `BLOQUEADO`, não um número com 2 features.
    n_features: Series[int] = pa.Field(
        nullable=False,
        ge=3,
        le=6,
        description="< 6 = feature cortada (CA-086, PLAN §5) — declarado no output, nunca "
        "silencioso. 5 sem a curva; 4 sem Focus e curva; 3 com G-02 também aberto.",
    )
    regime_v1_neighbor: Series[str] = pa.Field(
        nullable=False, isin=tuple(r.value for r in RegimeV1)
    )
    shrinkage: Series[str] = pa.Field(
        nullable=False, description="'ledoit_wolf' obrigatório em mahalanobis (CA-084)."
    )
    restrito_pos_2016: Series[bool] = pa.Field(
        nullable=False, description="True = variante V3-pos2016 (robustez a quebra estrutural)."
    )
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "regime_neighbors"
        strict = True
        coerce = True
        unique = ["quarter_ref", "rank", "metrica", "k_usado", "restrito_pos_2016"]

    @pa.dataframe_check(name="exclui_vizinhos_adjacentes")
    def _exclui_adjacentes(cls, df: object) -> bool:  # noqa: N805
        """O trimestre de referência não é vizinho de si mesmo.

        **O que este check NÃO faz:** a exclusão dos 2 trimestres imediatamente anteriores
        (`N_TRIMESTRES_EXCLUIDOS_VIZINHANCA`) que CA-085 exige. Isso é verificado no teste da
        feature F-019, não aqui — ver `CONTRACTS.md §5.2`.
        """
        return bool((df["quarter_ref"] != df["quarter_neighbor"]).all())  # type: ignore[index]


# ─────────────────────────────────────────────────────────────────────────────
# V1 isolada (F-019) — ACRÉSCIMO, nada acima foi alterado
#
# `RegimesSchema` é o contrato da tabela **completa** `regimes`, e exige as três lentes na mesma
# linha: `ciclo_selic`, `regime_v2` e `stress_flag` são `nullable=False` e são de **F-020/F-021**,
# e `regime_v1` é `nullable=False` no enum de 4 rótulos. F-019 entrega só a V1 e, por **D-m**, 16
# dos 83 trimestres não têm `ibcbr_gap` — logo não têm quadrante. Satisfazer `RegimesSchema` hoje
# exigiria (a) inventar `ciclo_selic`/`stress_flag`, (b) inventar um quadrante para os 16 nulos, ou
# (c) **alterar** `RegimesSchema` — e as três são proibidas (Anti-SPEC §10.1.1, `AGENTS.md §9`:
# alterar schema existente é pausa).
#
# Saída: `RegimesV1Schema` valida o **subconjunto V1** de `RegimesSchema`, materializado em
# `data/canonical/regimes_v1.parquet`. A junção das três lentes numa tabela `regimes` que satisfaça
# `RegimesSchema` é de **F-022**, que é quem tem as três na mão. `COLUNAS_V1_DE_REGIMES` nomeia
# exatamente o que vem daqui, e há teste de que todas existem em `RegimesSchema` com o mesmo nome.
# ─────────────────────────────────────────────────────────────────────────────

LIMIAR_CRESCIMENTO_PP = 0.0
"""`g_T > 0` separa crescimento acima/abaixo da tendência (ADR-001 §4, metodologia §2)."""

LIMIAR_ACELERACAO_PP = 0.0
"""`pi_T > 0` separa inflação acelerando/desacelerando (ADR-001 §4 — eixo = aceleração, D3)."""

SENSIBILIDADE_ACELERACAO_PP = 0.1
"""Deslocamento do limiar de aceleração reportado como sensibilidade (±0,1 pp)."""

N_QUADRANTE_MINIMO_CA080 = 10
N_QUADRANTE_MAXIMO_CA080 = 35
"""Faixa de `n` por quadrante que CA-080 aceita sem alerta de desbalanceamento."""

VERSAO_ESPECIFICACAO_V1 = "V1"
VERSAO_ESPECIFICACAO_V1_1 = "V1.1"
"""CA-091: ajuste posterior nasce como `V1.1` e **nunca** sobrescreve a `V1`."""


class StatusRegimeV1(StrEnum):
    """O trimestre tem quadrante, ou não tem — e nunca uma estimativa no lugar."""

    CLASSIFICADO = "CLASSIFICADO"
    INDETERMINADO = "INDETERMINADO"


class MotivoIndeterminado(StrEnum):
    """Por que o trimestre ficou sem quadrante. Vai **no dado**, não só no relatório."""

    GAP_AUSENTE = "GAP_AUSENTE"
    ACELERACAO_AUSENTE = "ACELERACAO_AUSENTE"
    AMBOS_AUSENTES = "AMBOS_AUSENTES"
    EMPATE_SEM_SINAL_ANTERIOR = "EMPATE_SEM_SINAL_ANTERIOR"


#: O subconjunto de `RegimesSchema` que F-019 preenche. Toda coluna aqui existe lá com o mesmo
#: nome; F-022 junta este bloco ao de F-020/F-021 para montar a tabela `regimes` completa.
COLUNAS_V1_DE_REGIMES: tuple[str, ...] = (
    "quarter",
    "regime_v1",
    "g_score",
    "pi_score",
    "n_obs_regime_v1",
    "alerta_n_baixo",
    "lag_adjusted",
    "trocou_vs_revised",
    "especificacao_congelada",
    "versao_especificacao",
    "fonte_versao",
)


class RegimesV1Schema(pa.DataFrameModel):
    """Só a V1, por trimestre. PK: `quarter`. Materializa `regimes_v1.parquet` (F-019).

    Diferenças deliberadas frente a `RegimesSchema`, cada uma com motivo:

    - `regime_v1` é **anulável** aqui: nulo = sem quadrante, e `status_regime_v1` diz
      `INDETERMINADO` com `motivo_indeterminado` preenchido. Em `RegimesSchema` é `nullable=False`
      de propósito — é lá que a junção de F-022 tem de resolver o que fazer com os 16 trimestres
      sem `ibcbr_gap` (**D-m**), e é bom que o contrato da tabela final recuse o nulo em silêncio.
    - não traz `ciclo_selic`/`regime_v2`/`stress_flag` (F-020/F-021) nem `regime_v1b` (fase 2).
    - acrescenta `conclusao_suprimida` (CA-109), `alerta_desbalanceamento` (CA-080),
      `desempate_aplicado` (CA-079) e os dois sinais booleanos de eixo, que são a auditoria do
      rótulo célula a célula.
    """

    quarter: Series[str] = pa.Field(nullable=False, unique=True, str_matches=QUARTER_REGEX)
    regime_v1: Series[str] = pa.Field(
        nullable=True,
        isin=tuple(r.value for r in RegimeV1),
        description="Nulo = INDETERMINADO; nunca uma estimativa (Anti-SPEC §10.1.1).",
    )
    status_regime_v1: Series[str] = pa.Field(
        nullable=False, isin=tuple(s.value for s in StatusRegimeV1)
    )
    motivo_indeterminado: Series[str] = pa.Field(
        nullable=True, isin=tuple(m.value for m in MotivoIndeterminado)
    )
    g_score: Series[float] = pa.Field(nullable=True, description="`ibcbr_gap` de T, em pp.")
    pi_score: Series[float] = pa.Field(nullable=True, description="`ipca_12m_delta` de T, em pp.")
    crescimento_acima: Series[bool] = pa.Field(nullable=True, description="`g_T > limiar`.")
    inflacao_acelerando: Series[bool] = pa.Field(nullable=True, description="`pi_T > limiar`.")
    desempate_aplicado: Series[bool] = pa.Field(
        nullable=False,
        description="True = algum eixo era exatamente o limiar e herdou T-1 (CA-079).",
    )
    n_obs_regime_v1: Series[int] = pa.Field(
        nullable=False, ge=1, description="`n` do grupo desta linha — vai para toda célula."
    )
    alerta_n_baixo: Series[bool] = pa.Field(nullable=False, description="`n < N_ALERTA` (CA-108).")
    conclusao_suprimida: Series[bool] = pa.Field(
        nullable=False, description="`n < N_SUPRESSAO` — nenhuma conclusão afirmativa (CA-109)."
    )
    alerta_desbalanceamento: Series[bool] = pa.Field(
        nullable=False, description="`n` fora de [10, 35] — alerta de CA-080."
    )
    lag_adjusted: Series[bool] = pa.Field(
        nullable=False, description="True = classificado sobre `macro_quarterly_asof` (CA-072)."
    )
    trocou_vs_revised: Series[bool] = pa.Field(
        nullable=True,
        description="Só na materialização `asof`; nulo em `revised` (não há com o que comparar).",
    )
    especificacao_congelada: Series[bool] = pa.Field(
        nullable=False, description="False enquanto ADR-001 estiver em Proposta (CA-090)."
    )
    versao_especificacao: Series[str] = pa.Field(
        nullable=False, isin=(VERSAO_ESPECIFICACAO_V1, VERSAO_ESPECIFICACAO_V1_1)
    )
    fonte_versao: Series[str] = pa.Field(
        nullable=False, str_matches=r"^[0-9a-f]{64}$", description="Hash do código (CA-088)."
    )

    class Config:
        """Configuração do schema."""

        name = "regimes_v1"
        strict = True
        coerce = True
        unique = ["quarter"]

    @pa.dataframe_check(name="status_coerente_com_o_rotulo")
    def _status_coerente(cls, df: object) -> bool:  # noqa: N805
        """`CLASSIFICADO` ⇔ `regime_v1` preenchido ⇔ `motivo_indeterminado` nulo."""
        classificado = df["status_regime_v1"] == StatusRegimeV1.CLASSIFICADO.value  # type: ignore[index]
        tem_rotulo = df["regime_v1"].notna()  # type: ignore[index]
        tem_motivo = df["motivo_indeterminado"].notna()  # type: ignore[index]
        return bool((classificado == tem_rotulo).all() and (classificado == ~tem_motivo).all())

    @pa.dataframe_check(name="eixos_presentes_se_classificado")
    def _eixos_presentes(cls, df: object) -> bool:  # noqa: N805
        """Trimestre classificado tem os dois sinais de eixo; indeterminado nunca os tem ambos."""
        classificado = df["status_regime_v1"] == StatusRegimeV1.CLASSIFICADO.value  # type: ignore[index]
        sinais = df["crescimento_acima"].notna() & df["inflacao_acelerando"].notna()  # type: ignore[index]
        return bool((classificado == sinais).all())

    @pa.dataframe_check(name="lag_adjusted_homogeneo")
    def _lag_homogeneo(cls, df: object) -> bool:  # noqa: N805
        """Uma materialização não mistura `asof` e `revised` na mesma tabela (CA-072)."""
        return int(df["lag_adjusted"].nunique()) == 1  # type: ignore[index]


# ─────────────────────────────────────────────────────────────────────────────
# V3 isolada (F-021) — ACRÉSCIMO, nada acima foi alterado
#
# `RegimeNeighborsSchema` (acima) é o contrato da tabela `regime_neighbors` e é a que CA-089
# valida. Ele tem `regime_v1_neighbor` **`nullable=False`**, e isso colide com **D-m**: por falta
# de `ibcbr_gap`, 16 dos 83 trimestres não têm quadrante V1 (`RegimesV1Schema`, F-019, publica
# `regime_v1` anulável com `status_regime_v1 = INDETERMINADO`). A colisão **não é teórica**: na
# rodada real, 4 dos 8 vizinhos de `2026Q3` são de 2006-2007, justamente trimestres sem V1 — a
# tabela de contrato, para ter `regime_v1_neighbor` preenchido, teria de excluí-los do conjunto
# de vizinhos **em silêncio**, trocando a resposta do Comitê sem avisar.
#
# Saída de F-021, então, em dois artefatos com papéis distintos:
#
# | Artefato | Schema | Conjunto de vizinhos |
# |---|---|---|
# | `regime_neighbors.parquet` | `RegimeNeighborsSchema` (contrato, CA-089) | só vizinho **com**
#   rótulo V1 — restrição declarada, com o custo medido no relatório |
# | `regime_neighbors_v3.parquet` | `RegimeNeighborsV3Schema` (aqui) | **completo**: todo
#   trimestre com vetor de features cheio. É o entregável de "momentos semelhantes" |
#
# Tornar `regime_v1_neighbor` anulável resolveria os dois num só artefato e é a recomendação a
# quem for decidir — mas é **alteração** de schema existente, logo feature classe C própria
# (`AGENTS.md §9`), não acréscimo. Por isso o acréscimo.
# ─────────────────────────────────────────────────────────────────────────────

JANELA_AMOSTRA_COMPLETA = "amostra_completa"
JANELA_EXPANDING = "expanding_ate_T"
JANELAS_DE_PADRONIZACAO: tuple[str, ...] = (JANELA_AMOSTRA_COMPLETA, JANELA_EXPANDING)
"""Onde a média/desvio do z-score (e a covariância) são estimados.

`amostra_completa` é a versão **descritiva**, que a metodologia §2 (princípio 4) sanciona
explicitamente e que o `TODO.md` de F-021 pede ("z-score na amostra completa");
`expanding_ate_T` usa **só** o passado de cada `T` e é a variante sem nenhum caminho de
look-ahead (metodologia §5.1). As duas nunca se misturam na mesma leitura: `somente_passado` e
esta coluna andam juntas.
"""

SHRINKAGE_LEDOIT_WOLF = "ledoit_wolf"
"""CA-084: em `mahalanobis` a covariância é **sempre** encolhida. Travado em check de schema."""

SHRINKAGE_NAO_SE_APLICA = "nao_se_aplica"
"""Valor de `shrinkage` na métrica euclidiana, que não usa covariância nenhuma."""

VERSAO_ESPECIFICACAO_V3 = "V3"
VERSAO_ESPECIFICACAO_V3_1 = "V3.1"
"""CA-091, para a V3: ajuste posterior nasce como `V3.1` e nunca sobrescreve a `V3`."""

SEPARADOR_DE_FEATURES = "|"
"""`features_usadas` é a lista declarada, junta por este separador (CA-086, nunca silencioso)."""


def indice_do_quarter(quarter: str) -> int:
    """`2006Q1` → 8025. Índice absoluto de trimestre, para distância temporal em trimestres.

    É o que faz "os 2 trimestres imediatamente anteriores" (`N_TRIMESTRES_EXCLUIDOS_VIZINHANCA`,
    CA-085) ser verificável **dentro do schema**, sem depender da grade da feature.
    """
    ano, tri = quarter.split("Q")
    return int(ano) * 4 + int(tri)


class RegimeNeighborsV3Schema(pa.DataFrameModel):
    """V3 com o conjunto **completo** de vizinhos. Materializa `regime_neighbors_v3.parquet`.

    PK: `(quarter_ref, rank, metrica, k_usado, restrito_pos_2016, somente_passado)`.

    Toda coluna que existe em `RegimeNeighborsSchema` tem aqui o **mesmo nome e o mesmo
    significado**; o que muda é o que o contrato de hoje não suporta:

    - `regime_v1_neighbor` é **anulável**, com `status_regime_v1_neighbor` dizendo
      `INDETERMINADO` — é o rótulo de F-019 (`RegimesV1Schema`), não um rótulo novo;
    - `somente_passado` + `janela_padronizacao` distinguem a variante descritiva da variante sem
      look-ahead, que na tabela de contrato colidiriam na PK;
    - `quarter_t_mais_1` nomeia, **no dado**, o trimestre **seguinte** ao vizinho — o que CA-102
      exige que seja medido (e não o retorno do próprio vizinho);
    - `n_vizinhos` e `features_usadas` deixam `n < k` e o corte de feature declarados na linha.
    """

    quarter_ref: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    rank: Series[int] = pa.Field(nullable=False, ge=1, le=max(K_VIZINHOS_SENSIBILIDADE))
    quarter_neighbor: Series[str] = pa.Field(nullable=False, str_matches=QUARTER_REGEX)
    distancia: Series[float] = pa.Field(nullable=False, ge=0)
    metrica: Series[str] = pa.Field(nullable=False, isin=tuple(m.value for m in MetricaDistancia))
    k_usado: Series[int] = pa.Field(nullable=False, isin=K_VIZINHOS_SENSIBILIDADE)
    n_vizinhos: Series[int] = pa.Field(
        nullable=False,
        ge=1,
        le=max(K_VIZINHOS_SENSIBILIDADE),
        description="Quantos vizinhos a lente achou. `< k_usado` = pool pequeno, declarado.",
    )
    n_features: Series[int] = pa.Field(nullable=False, ge=3, le=6)
    features_usadas: Series[str] = pa.Field(
        nullable=False, description="Nomes das features, juntos por `|` (CA-086)."
    )
    regime_v1_neighbor: Series[str] = pa.Field(
        nullable=True,
        isin=tuple(r.value for r in RegimeV1),
        description="Rótulo V1 do vizinho (CA-101). Nulo = INDETERMINADO por D-m.",
    )
    status_regime_v1_neighbor: Series[str] = pa.Field(
        nullable=False, isin=tuple(s.value for s in StatusRegimeV1)
    )
    quarter_t_mais_1: Series[str] = pa.Field(
        nullable=True,
        str_matches=QUARTER_REGEX,
        description="O trimestre SEGUINTE ao vizinho (CA-102). Nulo só no fim da janela.",
    )
    shrinkage: Series[str] = pa.Field(
        nullable=False, isin=(SHRINKAGE_LEDOIT_WOLF, SHRINKAGE_NAO_SE_APLICA)
    )
    janela_padronizacao: Series[str] = pa.Field(nullable=False, isin=JANELAS_DE_PADRONIZACAO)
    somente_passado: Series[bool] = pa.Field(
        nullable=False, description="True = candidato só entre trimestres anteriores (sem futuro)."
    )
    restrito_pos_2016: Series[bool] = pa.Field(nullable=False)
    alerta_n_baixo: Series[bool] = pa.Field(
        nullable=False, description="`n_vizinhos < N_ALERTA` (Anti-SPEC §10.2.8)."
    )
    especificacao_congelada: Series[bool] = pa.Field(
        nullable=False, description="False enquanto ADR-001 estiver em Proposta (CA-090)."
    )
    versao_especificacao: Series[str] = pa.Field(
        nullable=False, isin=(VERSAO_ESPECIFICACAO_V3, VERSAO_ESPECIFICACAO_V3_1)
    )
    lag_adjusted: Series[bool] = pa.Field(nullable=False)
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "regime_neighbors_v3"
        strict = True
        coerce = True
        unique = [
            "quarter_ref",
            "rank",
            "metrica",
            "k_usado",
            "restrito_pos_2016",
            "somente_passado",
        ]

    @pa.dataframe_check(name="exclui_vizinhos_adjacentes")
    def _exclui_adjacentes(cls, df: object) -> bool:  # noqa: N805
        """CA-085, de verdade: nem o próprio T, nem T±1, nem T±2 aparecem no ranking.

        O check homônimo de `RegimeNeighborsSchema` só garante que a referência não é vizinha de
        si mesma, e diz na docstring que a exclusão dos 2 adjacentes fica "no teste da feature".
        Aqui ela é **contrato**.
        """
        ref = df["quarter_ref"].map(indice_do_quarter)  # type: ignore[index]
        viz = df["quarter_neighbor"].map(indice_do_quarter)  # type: ignore[index]
        return bool(((ref - viz).abs() > N_TRIMESTRES_EXCLUIDOS_VIZINHANCA).all())

    @pa.dataframe_check(name="somente_passado_nao_olha_para_frente")
    def _somente_passado(cls, df: object) -> bool:  # noqa: N805
        """`somente_passado=True` implica vizinho anterior à referência. É o anti-look-ahead."""
        passado = df["somente_passado"].astype(bool)  # type: ignore[index]
        ref = df["quarter_ref"].map(indice_do_quarter)  # type: ignore[index]
        viz = df["quarter_neighbor"].map(indice_do_quarter)  # type: ignore[index]
        return bool((~passado | (viz < ref)).all())

    @pa.dataframe_check(name="t_mais_1_e_o_seguinte_do_vizinho")
    def _t_mais_1(cls, df: object) -> bool:  # noqa: N805
        """CA-102 no dado: `quarter_t_mais_1` é o vizinho + 1 trimestre, nunca o próprio vizinho."""
        viz = df["quarter_neighbor"].map(indice_do_quarter)  # type: ignore[index]
        seguinte = df["quarter_t_mais_1"]  # type: ignore[index]
        tem = seguinte.notna()
        if not bool(tem.any()):
            return True
        return bool((seguinte[tem].map(indice_do_quarter) - viz[tem] == 1).all())

    @pa.dataframe_check(name="mahalanobis_exige_shrinkage")
    def _shrinkage_obrigatorio(cls, df: object) -> bool:  # noqa: N805
        """CA-084: covariância amostral crua em `mahalanobis` é recusada pelo contrato."""
        maha = df["metrica"] == MetricaDistancia.MAHALANOBIS.value  # type: ignore[index]
        encolhida = df["shrinkage"] == SHRINKAGE_LEDOIT_WOLF  # type: ignore[index]
        return bool((maha == encolhida).all())

    @pa.dataframe_check(name="status_coerente_com_o_rotulo_do_vizinho")
    def _status_coerente(cls, df: object) -> bool:  # noqa: N805
        """`CLASSIFICADO` equivale a `regime_v1_neighbor` preenchido (o nulo nunca é mudo)."""
        classificado = df["status_regime_v1_neighbor"] == StatusRegimeV1.CLASSIFICADO.value  # type: ignore[index]
        return bool((classificado == df["regime_v1_neighbor"].notna()).all())  # type: ignore[index]

    @pa.dataframe_check(name="janela_coerente_com_somente_passado")
    def _janela_coerente(cls, df: object) -> bool:  # noqa: N805
        """Padronização `expanding` equivale à variante `somente_passado` — nunca cruzadas."""
        passado = df["somente_passado"].astype(bool)  # type: ignore[index]
        expanding = df["janela_padronizacao"] == JANELA_EXPANDING  # type: ignore[index]
        return bool((passado == expanding).all())

    @pa.dataframe_check(name="rank_nao_passa_de_n_vizinhos")
    def _rank_coerente(cls, df: object) -> bool:  # noqa: N805
        """`rank` vai de 1 a `n_vizinhos` (que é no máximo `k_usado`) — CA-089."""
        return bool((df["rank"] <= df["n_vizinhos"]).all())  # type: ignore[index]
