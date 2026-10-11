"""Schema de `internacional_por_regime` e `internacional_pesos` — F-026, item **C1** do e-mail.

Fonte de verdade do contrato (SPEC RF-038, RF-039; CA-104..107 + CA-108/109 e o gate CA-090).
Base de desenho: `docs/research/metodologia-regimes-macro.md §4` · `ADR-003` (Proposta, **D6**).

**Classe C.** Duas tabelas, duas perguntas:

- **`internacional_por_regime`** — *em quais regimes o internacional em BRL bate CDI e IBOV, e por
  quanto* (RF-038/CA-104). PK `(lente, regime, asset_id)`, **o mesmo arcabouço** de
  `RegimeAssetMetricsSchema`: as colunas de retorno são produzidas pela **mesma** função de F-022
  (`metricas_regime.metricas_da_celula`), e há teste que compara célula a célula. O que esta tabela
  acrescenta são as duas colunas de **correlação condicional** (`corr_ibov`, `corr_imab`) que
  CA-105 pede, com o `n` de **pares** de cada uma — que não é o `n` da célula.
- **`internacional_pesos`** — a **variância mínima** com shrinkage de `§4.3` item 1, long-only e
  soma 1, em dois escopos (`POR_REGIME` descritivo e `EXPANDING` sem look-ahead), com o peso
  internacional **truncado na banda tática** de ADR-003 em `peso_na_banda`.

> ⚠️ **`internacional_pesos` não é publicável na entrega de 2026-10-14.** A Anti-SPEC **§10.3.16**
> e **§10.5** põem "variância mínima por regime" e "fronteira eficiente" **fora da v1**, e o
> `TODO.md` de F-026 repete ("Excluído: variância mínima por regime e fronteira eficiente →
> F-035"). A tabela existe como **material de apoio interno**, com `especificacao_congelada=False`
> em toda linha e o bloqueio declarado em `relatorio_internacional.json`. Quem a publicar sem
> resolver ADR-003/Anti-SPEC está violando a seção sagrada.

**Por que `lente` tem 3 valores aqui e não os 3 de `RegimeAssetMetricsSchema`.** Lá o enum é
`{V1, V2, V3}` e a **materialização** (`revised` × `asof`) vira nome de arquivo (F-022 §"Por que
TRÊS Parquets"). Aqui as três leituras que RF-038 pede — V1 `revised`, V1 `asof` e V3 em T+1 —
cabem numa tabela só porque `lente` distingue `V1` de `V1_ASOF`. Não é a mesma coluna da outra
tabela e por isso não é alteração de contrato nenhum: é schema **novo** (`AGENTS.md §7`).
"""

from __future__ import annotations

import pandera as pa
from pandera.typing import Series

from packages.shared.schemas.asset_returns_quarterly import ASSET_IDS_VALIDOS

QUARTER_REGEX = r"^(200[6-9]|20[1-2][0-9])Q[1-4]$"

# ─────────────────────────────────────────────────────────────────────────────
# Universo: quem é "o internacional" nesta entrega
# ─────────────────────────────────────────────────────────────────────────────

ATIVO_INTERNACIONAL_REPRESENTATIVO = "ACWI_BRL"
"""O internacional da carteira de variância mínima — e **não** é o `SP500_BRL` de ADR-003 §1.

Motivo medido, não preferência: em `asset_returns_quarterly` (F-017) `ACWI_BRL` tem
`is_total_return = True` e `SP500_BRL` tem `is_total_return = False` (price return). `IBOV`,
`IMAB` e `CDI` são total return. Montar covariância misturando total return doméstico com price
return internacional é exatamente o que a **Anti-SPEC §10.2.12 / CA-064** proíbe. `SP500_BRL`
continua na tabela de retornos por regime, com a flag visível e **nunca somado** com os outros.
"""

ATIVO_INTERNACIONAL_ALTERNATIVO = "SP500_BRL"
"""A linha que ADR-003 §1 nomeia. Fica no `internacional_por_regime` com `is_total_return=False`
e entra em `internacional_pesos` **apenas** como carteira de sensibilidade separada, nunca na
mesma matriz de covariância que os total-return."""

ATIVO_CAMBIO = "USDBRL"
"""O caixa em dólar — o único ativo que a evidência FGVcef aponta como diversificação genuína."""

CARTEIRA_VARIANCIA_MINIMA: tuple[str, ...] = (
    "CDI",
    "IMAB",
    "IBOV",
    ATIVO_INTERNACIONAL_REPRESENTATIVO,
)
"""O conjunto **pequeno** de `metodologia §4.3` item 1, menos o `IFIX` (só 63 dos 83 trimestres,
começa em 2010Q4 — L1): CDI, IMA-B, IBOV e o internacional em BRL. Com `n ≈ 13..19` por regime e
`p = 4`, a covariância é ruidosa e o shrinkage é obrigatório (CA-084 é de F-021, a razão é a
mesma)."""

ATIVOS_DA_TABELA_POR_REGIME: tuple[str, ...] = (
    "CDI",
    "IMAB",
    "IBOV",
    ATIVO_INTERNACIONAL_REPRESENTATIVO,
    ATIVO_INTERNACIONAL_ALTERNATIVO,
    ATIVO_CAMBIO,
)
"""As linhas de `internacional_por_regime`: **todas em BRL**. `SP500_USD` fica fora de propósito —
é a mesma série em outra moeda, e uma coluna de retorno que mistura moedas não tem leitura. A
decomposição `(1+SP500_BRL) = (1+SP500_USD)(1+USDBRL)` é conferida no relatório, não na tabela."""

ATIVOS_SEM_FONTE: tuple[str, ...] = ("GOLD_BRL", "UST10_BRL", "SP500_HEDGE")
"""O que ADR-003 §1/§4 pede e **não existe** em `asset_returns_quarterly`: ouro (gap **G-03**),
Treasury 10a em BRL e a versão **hedgeada** (D7). Saem como `BLOQUEADO — FONTE INDISPONÍVEL` no
relatório — nunca com proxy silencioso, nunca somados com a versão sem hedge."""

# ─────────────────────────────────────────────────────────────────────────────
# A regra de risk-off (RF-039 / CA-106)
# ─────────────────────────────────────────────────────────────────────────────

SERIE_INCLINACAO_DO_STRESS = "INCLINACAO_REAL_5A_3A"
"""Qual inclinação fecha a disjunção de CA-106: a **real 5a−3a**, de `raw_series` via
`alinhar_series` — a principal provisória de **D-i** (95,25% de cobertura, a que fecha CA-025;
79/83 trimestres). A 5a−1a tem 50/83 e é secundária desde D-i. **D-n** mantém a 5a−3a fora de
`MacroQuarterlySchema`, então ela é lida pela função que F-021 já publica."""

LIMIAR_QUEDA_INCLINACAO_DP = 1.0
""""a inclinação cai > 1 desvio-padrão" (RF-039): `Δincl(T) < −1 × σ_expanding(Δincl até T−1)`."""

LIMIAR_USDBRL_VAR_TRI_PCT = 10.0
""""USDBRL sobe > 10% no trimestre" (RF-039). `usdbrl_var_tri` está em **por cento** (D-o)."""

MIN_OBS_DESVIO_EXPANDING = 8
"""Mínimo de observações **anteriores a T** para o desvio expanding ser estimável. Abaixo disso o
ramo da inclinação é `avaliavel=False` — não `False` disfarçado de "sem stress"."""

RAMO_EMBI_FORA = (
    "O terceiro ramo de metodologia §4.3 (EMBI sobe > 1 d.p.) fica DECLARADAMENTE fora (L8, "
    "CA-106): o EMBI+ morre em 30/07/2024 e `macro_quarterly.embi_delta_tri` tem 0 valores "
    "nao nulos nos 83 trimestres. Fase 2."
)

# ─────────────────────────────────────────────────────────────────────────────
# A faixa de ADR-003 (D6, Proposta)
# ─────────────────────────────────────────────────────────────────────────────

PISO_ESTRUTURAL_MIN = 0.16
PISO_ESTRUTURAL_MAX = 0.20
"""O piso estrutural de ADR-003: 16-20% (FGVcef: 16-18% para neutralizar o câmbio sobre o padrão
de consumo; ADR-003 arredonda o teto para 20%)."""

BANDA_TATICA_MIN = 0.15
BANDA_TATICA_MAX = 0.35
"""A banda tática por regime de ADR-003: 15%-35% (faixa ótima FGVcef 20-35%, piso tático 15%)."""

CAP_POR_ATIVO = 0.40
"""O cap por ativo de `metodologia §4.3` item 1 — a restrição que a pesquisa manda usar.

**O que o cap muda, medido no acervo real** (e não o que se esperaria): sem cap a carteira **não**
degenera em 100% CDI — o shrinkage de Ledoit-Wolf (`rho` de 0,25 a 0,60 por regime) puxa a
covariância para a esfera e o CDI fica em 37%-50%. O efeito real está no **expanding**: o peso
internacional médio de 2006-2026 cai de **19,6%** (cap 0,40) para **10,4%** (sem cap). Por regime
a diferença é menor (15,9% → 14,8% na estagflação; 23,6% → 23,0% na recuperação). O relatório
publica as duas versões justamente para que essa sensibilidade seja **visível** — é ela, e não a
convicção de quem escreve, que justifica entregar faixa e não ponto (CA-107)."""

SEM_CAP = 1.0
"""`cap = 1.0` é "sem cap": a única restrição é long-only e soma 1."""

LENTE_V1 = "V1"
LENTE_V1_ASOF = "V1_ASOF"
LENTE_V3 = "V3"
LENTES_INTERNACIONAL: tuple[str, ...] = (LENTE_V1, LENTE_V1_ASOF, LENTE_V3)

ESCOPO_POR_REGIME = "POR_REGIME"
ESCOPO_EXPANDING = "EXPANDING"
ESCOPOS_PESOS: tuple[str, ...] = (ESCOPO_POR_REGIME, ESCOPO_EXPANDING)
"""`POR_REGIME`: covariância estimada nos trimestres **daquele regime** (amostra inteira do
regime) — descritivo, é o que `§4.3` item 1 pede. `EXPANDING`: covariância de `T` estimada **só**
com trimestres até `T−1` — a leitura sem look-ahead (`metodologia §5.1`), e a única em que a
palavra "peso de T" tem sentido operacional."""

TOLERANCIA_SOMA_PESOS = 1e-8
"""Soma dos pesos de uma carteira = 1 dentro disso. É folga de ponto flutuante do solver, não de
método: 1e-8 em peso é 1e-6 pp, e qualquer erro de restrição real é ordens de magnitude maior."""

SELO_NAO_RECOMENDACAO = (
    "DESCRITIVO, NAO RECOMENDACAO; ESPECIFICACAO NAO CONGELADA (ADR-003 em Proposta, D6 aberta)"
)
"""O selo que acompanha a tabela regime → peso sugerido em **toda** saída (CA-107, Anti-SPEC
§10.2.10)."""

BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA = (
    "Anti-SPEC 10.3.16 e 10.5 poem variancia minima por regime e fronteira eficiente FORA da v1 "
    "(entrega de 2026-10-14), e o TODO.md de F-026 repete em 'Excluido' (-> F-035). Esta tabela "
    "e material de APOIO INTERNO: especificacao_congelada=False em toda linha, nenhum numero "
    "dela vai ao Comite sem (a) ADR-003 aceito e (b) autorizacao humana explicita para a "
    "Anti-SPEC (AGENTS.md 9/14). O que E publicavel em F-026: os retornos por regime, as "
    "correlacoes (CA-104/105), o stress_flag (CA-106) e a FAIXA de ADR-003 (CA-107)."
)


class InternacionalPorRegimeSchema(pa.DataFrameModel):
    """Retorno em BRL e correlação condicional do internacional, por regime (RF-038)."""

    lente: Series[str] = pa.Field(nullable=False, isin=LENTES_INTERNACIONAL)
    regime: Series[str] = pa.Field(nullable=False)
    asset_id: Series[str] = pa.Field(nullable=False, isin=ASSET_IDS_VALIDOS)

    n_obs: Series[int] = pa.Field(nullable=False, ge=0)
    ret_medio: Series[float] = pa.Field(nullable=True)
    ret_mediana: Series[float] = pa.Field(nullable=True)
    excesso_cdi: Series[float] = pa.Field(
        nullable=True, description="média de (1+r)/(1+cdi)-1 — razão, nunca subtração (CA-069)."
    )
    ret_real: Series[float] = pa.Field(nullable=True)
    hit_ratio_cdi: Series[float] = pa.Field(nullable=True, ge=0, le=1)

    corr_ibov: Series[float] = pa.Field(nullable=True, ge=-1.0, le=1.0)
    n_pares_ibov: Series[int] = pa.Field(nullable=False, ge=0)
    corr_imab: Series[float] = pa.Field(nullable=True, ge=-1.0, le=1.0)
    n_pares_imab: Series[int] = pa.Field(nullable=False, ge=0)

    is_total_return: Series[bool] = pa.Field(
        nullable=True,
        description="Price × total return nunca comparados sem a flag (CA-064/Anti-SPEC §10.2.12).",
    )
    alerta_n_baixo: Series[bool] = pa.Field(nullable=False, description="n_obs < 8 (CA-108).")
    conclusao_suprimida: Series[bool] = pa.Field(nullable=False, description="n_obs < 5 (CA-109).")
    especificacao_congelada: Series[bool] = pa.Field(
        nullable=False, description="Status do ADR-001 em disco (CA-090); False ⇒ não publicável."
    )
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "internacional_por_regime"
        strict = True
        coerce = True
        unique = ["lente", "regime", "asset_id"]

    @pa.dataframe_check(name="pares_de_correlacao_nunca_excedem_n_obs")
    def _pares_coerentes(cls, df: object) -> bool:  # noqa: N805
        """`n_pares_*` é o `n` de pares, e par exige os dois lados: nunca maior que `n_obs`."""
        return bool(
            (df["n_pares_ibov"] <= df["n_obs"]).all()  # type: ignore[index]
            and (df["n_pares_imab"] <= df["n_obs"]).all()  # type: ignore[index]
        )

    @pa.dataframe_check(name="correlacao_exige_pares")
    def _correlacao_exige_pares(cls, df: object) -> bool:  # noqa: N805
        """Correlação não nula exige ao menos 2 pares — nunca correlação de 1 ponto."""
        ibov = df["corr_ibov"].isna() | (df["n_pares_ibov"] >= 2)  # type: ignore[index]
        imab = df["corr_imab"].isna() | (df["n_pares_imab"] >= 2)  # type: ignore[index]
        return bool(ibov.all() and imab.all())


class InternacionalPesosSchema(pa.DataFrameModel):
    """Pesos de variância mínima long-only por regime e por trimestre (apoio de RF-038/RF-039).

    **Não publicável na v1** — ver `BLOQUEIO_ANTI_SPEC_VARIANCIA_MINIMA` e o aviso do módulo.
    """

    escopo: Series[str] = pa.Field(nullable=False, isin=ESCOPOS_PESOS)
    chave: Series[str] = pa.Field(
        nullable=False, description="Rótulo do regime (POR_REGIME) ou `quarter` (EXPANDING)."
    )
    carteira: Series[str] = pa.Field(
        nullable=False, description="Os ativos da matriz de covariância, unidos por `+`."
    )
    asset_id: Series[str] = pa.Field(nullable=False, isin=ASSET_IDS_VALIDOS)

    peso: Series[float] = pa.Field(nullable=False, ge=0.0, le=1.0, description="Long-only.")
    cap: Series[float] = pa.Field(nullable=False, gt=0.0, le=1.0)
    peso_na_banda: Series[float] = pa.Field(
        nullable=True,
        ge=BANDA_TATICA_MIN,
        le=BANDA_TATICA_MAX,
        description="Só no ativo internacional representativo: `peso` truncado na banda ADR-003.",
    )

    n_obs: Series[int] = pa.Field(nullable=False, ge=0)
    rho_shrinkage: Series[float] = pa.Field(nullable=False, ge=0.0, le=1.0)
    alerta_n_baixo: Series[bool] = pa.Field(nullable=False)
    conclusao_suprimida: Series[bool] = pa.Field(nullable=False)
    especificacao_congelada: Series[bool] = pa.Field(
        nullable=False,
        description="Sempre False enquanto ADR-003 estiver em Proposta (D6) — CA-090/CA-107.",
    )
    fonte_versao: Series[str] = pa.Field(nullable=False)

    class Config:
        """Configuração do schema."""

        name = "internacional_pesos"
        strict = True
        coerce = True
        unique = ["escopo", "chave", "cap", "carteira", "asset_id"]

    @pa.dataframe_check(name="pesos_somam_um_por_carteira")
    def _soma_um(cls, df: object) -> bool:  # noqa: N805
        """Soma 1 em **cada** `(escopo, chave, cap, carteira)` — a restrição, verificada no dado."""
        somas = df.groupby(["escopo", "chave", "cap", "carteira"])["peso"].sum()  # type: ignore[index]
        return bool(((somas - 1.0).abs() <= TOLERANCIA_SOMA_PESOS).all())

    @pa.dataframe_check(name="peso_respeita_o_cap")
    def _respeita_cap(cls, df: object) -> bool:  # noqa: N805
        """Nenhum peso acima do `cap` declarado na própria linha."""
        return bool((df["peso"] <= df["cap"] + TOLERANCIA_SOMA_PESOS).all())  # type: ignore[index]

    @pa.dataframe_check(name="banda_so_no_ativo_internacional")
    def _banda_so_no_internacional(cls, df: object) -> bool:  # noqa: N805
        """`peso_na_banda` só existe na linha do internacional: a banda é sobre **ele** (CA-107)."""
        fora = df.loc[df["asset_id"] != ATIVO_INTERNACIONAL_REPRESENTATIVO]  # type: ignore[index]
        return bool(fora["peso_na_banda"].isna().all())


PK_POR_REGIME: tuple[str, ...] = ("lente", "regime", "asset_id")
PK_PESOS: tuple[str, ...] = ("escopo", "chave", "cap", "carteira", "asset_id")
