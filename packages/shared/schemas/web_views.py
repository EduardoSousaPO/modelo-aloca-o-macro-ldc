"""Contrato das **views web** — o JSON de apresentação que `apps/web_export/` emite (F-W001).

Fonte de verdade do contrato entre **dois repositórios**: este pipeline (produtor) e o portal
LDC Analytics (consumidor, `site-ldc`). Daqui saem, no mesmo comando, (a) a validação pydantic de
cada arquivo emitido e (b) os **tipos TypeScript** de `schema.d.ts` — RF-W013 do
`docs/product/LDC-ANALYTICS-PRD.md`.

Três regras que este módulo faz valer, e que não são negociáveis:

- **`extra="forbid"` em todo modelo.** É a forma executável de "nenhuma view carrega coluna que não
  esteja no contrato" (RF-W015): campo a mais na view ⇒ `ValidationError` nomeando o campo e a
  view, nunca um JSON publicado com coluna que o portal não sabe ler.
- **Toda view carrega o gate** (`GateDaView`): `especificacao_congelada`, o `status` do ADR-001 como
  está **em disco** e o veredito. O gate vive no **exportador**, não no front (`[arq §7.1]`) — o
  front só precisa saber o que renderizar por cima.
- **Toda célula carrega `n`** e as duas flags de `n` (`alerta_n_baixo` em `n < 8`,
  `conclusao_suprimida` em `n < 5`). A supressão sai **com o valor e com a flag**: o número continua
  no JSON, e é a flag que proíbe a conclusão — quem decide a cor é o front, quem decide o estado é
  o pipeline (`regimes_v1.conclusao_suprimida`, importada, nunca reimplementada).

**Unidade por campo** (`UNIDADE_POR_CAMPO`) e **precisão declarada** (`CASAS_POR_UNIDADE`) são parte
do contrato porque o erro de 100× é o modo de falha barato deste dado: `macro_quarterly` publica em
**%/pp** e `asset_returns_quarterly` em **fração**, e as duas têm `cdi_tri`/`ipca_tri` com o mesmo
nome (`LIMITACOES-COMITE.md §4.9`). O exportador **não converte nada**: declara a unidade nativa de
cada campo e arredonda com casas fixas. Nenhuma conversão ⇒ nenhum 100× possível.

Desde 2026-10-11 o contrato declara também **como apresentar** (`APRESENTACAO_POR_UNIDADE` →
`meta.unidade_de_apresentacao` / `fator_de_apresentacao` / `casas_de_apresentacao`, campo a campo).
O valor emitido continua nativo; o que muda é que o fator `100` de `0,0504 → 5,04%` passa a estar
escrito **de um lado só**, e a tela lê a tabela em vez de carregar a regra. Espelho legível:
`docs/contracts/CONTRACTS.md §10`.

| Arquivo emitido | Modelo | Tela do PRD | Slot de `[arq §1.1]` |
|---|---|---|---|
| `meta.json` | `MetaWeb` | todas (rodapé) | `manifest` |
| `ranking_atual.json` | `RankingAtualView` | T-01 | `ranking_atual` |
| `heatmap_regime_ativo.json` | `HeatmapView` | T-02 | `heatmap_regime_ativo` |
| `vizinhos.json` | `VizinhosView` | T-03 | `vizinhos` |
| `regimes_timeline.json` | `TimelineView` | T-04 | `regimes_timeline` |
| `internacional.json` | `InternacionalView` | T-06 | `internacional` |
| `catalogo.json` | `CatalogoView` | T-07 | `macro_series` |
| `current.json` (no pai) | `PonteiroCurrent` | — | `current` |
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────────────────────
# Nomes de arquivo — o contrato é o nome, não a convenção de quem escreve
# ─────────────────────────────────────────────────────────────────────────────

NOME_META = "meta.json"
"""O manifesto da tag. Ocupa o slot `manifest.json` de RF-W009 com o nome do Feature Contract."""

NOME_CURRENT = "current.json"
"""O **único** ponteiro, no diretório **pai** da tag — e o único arquivo com `no-cache`."""

NOME_TIPOS_TS = "schema.d.ts"
"""Os tipos TypeScript gerados destes modelos. É o contrato entre os dois repositórios."""

LIMITE_DE_BYTES = 400_000
"""Orçamento de RNF-W001: o conjunto das views + `schema.d.ts` abaixo de 400 KB não comprimido.

Não inclui `meta.json` nem `current.json`: `meta.json` publica o `sha256` e os bytes de cada view,
então somar-se a si mesmo seria circular. O total dos 9 arquivos vai ao relatório do CLI.
"""

CABECALHO_NO_CACHE = "no-cache"
POLITICA_IMMUTABLE = "immutable"

# ─────────────────────────────────────────────────────────────────────────────
# Unidades e precisão — declaradas, nunca convertidas
# ─────────────────────────────────────────────────────────────────────────────

UNIDADE_FRACAO = "fracao"
UNIDADE_PERCENTUAL = "percentual_a_a"
UNIDADE_INDICE = "indice"
UNIDADE_ADIMENSIONAL = "adimensional"
UNIDADE_CONTAGEM = "contagem"
UNIDADE_PP = "pontos_percentuais"

UNIDADE_POR_CAMPO: dict[str, str] = {
    "banda_tatica_max": UNIDADE_FRACAO,
    "banda_tatica_min": UNIDADE_FRACAO,
    "cap_usado": UNIDADE_FRACAO,
    "corr_ibov": UNIDADE_ADIMENSIONAL,
    "corr_imab": UNIDADE_ADIMENSIONAL,
    "corr": UNIDADE_ADIMENSIONAL,
    "desbalanceamento": UNIDADE_ADIMENSIONAL,
    "distancia": UNIDADE_ADIMENSIONAL,
    "erro_padrao_media": UNIDADE_FRACAO,
    "excesso_cdi": UNIDADE_FRACAO,
    "excesso_em_erros_padrao": UNIDADE_ADIMENSIONAL,
    "hit_ratio_cdi": UNIDADE_FRACAO,
    "ibov_nivel": UNIDADE_INDICE,
    "limiar_pct": UNIDADE_FRACAO,
    "melhor_tri": UNIDADE_FRACAO,
    "n_obs": UNIDADE_CONTAGEM,
    "n_pares": UNIDADE_CONTAGEM,
    "n_pares_ibov": UNIDADE_CONTAGEM,
    "n_pares_imab": UNIDADE_CONTAGEM,
    "pct": UNIDADE_FRACAO,
    "pct_nulos": UNIDADE_PERCENTUAL,
    "pior_tri": UNIDADE_FRACAO,
    "piso_estrutural_max": UNIDADE_FRACAO,
    "piso_estrutural_min": UNIDADE_FRACAO,
    "ret_ibov": UNIDADE_FRACAO,
    "ret_mediana": UNIDADE_FRACAO,
    "ret_medio": UNIDADE_FRACAO,
    "ret_real": UNIDADE_FRACAO,
    "ret_usdbrl": UNIDADE_FRACAO,
    "selic_meta_pct": UNIDADE_PERCENTUAL,
    "valor_num": UNIDADE_ADIMENSIONAL,
}
"""Unidade **nativa** de cada campo numérico publicado. O exportador não converte: declara.

`excesso_cdi`, `ret_*`, `erro_padrao_media` e `hit_ratio_cdi` vêm de `asset_returns_quarterly` e são
**fração** (`0,0520` = 5,20%). `selic_meta_pct` vem de `macro_quarterly` e é **% a.a.** (`14,75`).
Cruzar os dois sem ler isto erra por **100×** — daí `<UnidadeBadge/>` em todo eixo (RF-W014).
"""

CASAS_POR_UNIDADE: dict[str, int] = {
    UNIDADE_ADIMENSIONAL: 6,
    UNIDADE_CONTAGEM: 0,
    UNIDADE_FRACAO: 4,
    UNIDADE_INDICE: 2,
    UNIDADE_PERCENTUAL: 4,
    UNIDADE_PP: 4,
}
"""Casas decimais por unidade — **fixas e declaradas** (CA-121 aplicado ao JSON).

**4 casas em fração são 2 casas em pontos percentuais** (`0,0504` = 5,04%) — exatamente a precisão
que as telas do PRD exibem (`+5,04%`, `erro-padrão 2,54 pp`). É uma **redução declarada** para caber
em `LIMITE_DE_BYTES`, e a declaração vive em `meta.casas_por_unidade`: quem precisar de mais casas
lê
o Parquet, que é a fonte. Distância e correlação ficam em 6 casas (`UNIDADE_ADIMENSIONAL`) porque
não
têm leitura em pp e são poucas.

Sem casas fixas o `repr` do float vazaria para o JSON e duas exportações da mesma tag poderiam
divergir no byte — que é o que CA-121 proíbe.
"""

CASAS_PADRAO = 6
"""Campo numérico sem unidade declarada arredonda aqui. Nenhum campo publicado está nesse caso."""

UNIDADE_PERCENTUAL_DO_PERIODO = "percentual"
"""`%` do **período da série** (trimestre), que é o que `fracao` vira na tela: `0,0504` → `5,04`.

Unidade diferente de `UNIDADE_PERCENTUAL` (`percentual_a_a`, que é **ao ano**): são dois eixos que
não se somam, e o nome separado é o que impede somá-los por engano.
"""

APRESENTACAO_POR_UNIDADE: dict[str, tuple[str, float, int]] = {
    UNIDADE_FRACAO: (UNIDADE_PERCENTUAL_DO_PERIODO, 100.0, 2),
    UNIDADE_PP: (UNIDADE_PP, 1.0, 2),
    UNIDADE_PERCENTUAL: (UNIDADE_PERCENTUAL, 1.0, 2),
    UNIDADE_INDICE: (UNIDADE_INDICE, 1.0, 2),
    UNIDADE_ADIMENSIONAL: (UNIDADE_ADIMENSIONAL, 1.0, 3),
    UNIDADE_CONTAGEM: (UNIDADE_CONTAGEM, 1.0, 0),
}
"""`unidade nativa → (unidade de apresentação, fator, casas de apresentação)`.

**Por que isto existe, e por que fica aqui.** O exportador continua **sem converter nada** (D-W4):
o JSON sai na unidade nativa, com as casas nativas. O que esta tabela acrescenta é a *instrução* de
apresentação, declarada no `meta.json` **campo a campo** — e com isso o front deixa de ter regra de
conversão escrita em código e passa a ter uma leitura de tabela. O modo de falha que isto fecha é o
de sempre: `fracao` e `percentual_a_a` têm nomes parecidos e diferem por 100×
(`LIMITACOES-COMITE.md §4.9`), e `0,0504 fracao` impresso numa célula é correto e ilegível.

Quem apresenta continua sendo o front; quem **declara o fator** passa a ser o contrato. O rótulo
tipográfico (`%`, `p.p.`, `% a.a.`) segue do lado da tela: é texto de interface, não unidade.
"""


def apresentacao_do_campo(campo: str) -> tuple[str, float, int]:
    """`(unidade_de_apresentacao, fator_de_apresentacao, casas_de_apresentacao)` de um campo.

    Campo sem unidade nativa declarada sai `adimensional`, fator `1,0` — nunca um fator inventado.
    """
    nativa = UNIDADE_POR_CAMPO.get(campo, UNIDADE_ADIMENSIONAL)
    return APRESENTACAO_POR_UNIDADE.get(nativa, (nativa, 1.0, CASAS_PADRAO))


def unidade_de_apresentacao_por_campo() -> dict[str, str]:
    """`campo → unidade de apresentação`, para `meta.unidade_de_apresentacao`."""
    return {campo: apresentacao_do_campo(campo)[0] for campo in sorted(UNIDADE_POR_CAMPO)}


def fator_de_apresentacao_por_campo() -> dict[str, float]:
    """`campo → fator`, para `meta.fator_de_apresentacao`. O único número da conversão."""
    return {campo: apresentacao_do_campo(campo)[1] for campo in sorted(UNIDADE_POR_CAMPO)}


def casas_de_apresentacao_por_campo() -> dict[str, int]:
    """`campo → casas na tela`. Acompanha o fator: 4 casas em fração são 2 casas em `%`."""
    return {campo: apresentacao_do_campo(campo)[2] for campo in sorted(UNIDADE_POR_CAMPO)}


# ─────────────────────────────────────────────────────────────────────────────
# Gate e envelope
# ─────────────────────────────────────────────────────────────────────────────


class GateDaView(BaseModel):
    """O estado do gate de publicação, lido do **ADR-001 em disco**, em toda view (RF-W002)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    especificacao_congelada: bool = Field(
        description="False enquanto o ADR-001 não estiver ACEITA em disco (CA-090)."
    )
    status_adr_001: str = Field(description="PROPOSTA | ACEITA | DESCONHECIDO — falha fechada.")
    veredito_publicacao: str = Field(description="O texto de AGENTS.md §9 por escrito.")
    marca: str = Field(description="A faixa fixa do topo de toda tela. Vazia quando congelada.")
    publicavel: bool = Field(
        description="Espelha especificacao_congelada — nunca um terceiro valor."
    )


class EnvelopeDaView(BaseModel):
    """O que **toda** view carrega antes do seu payload. Herdado, nunca copiado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    view: str = Field(description="O nome do arquivo sem extensão.")
    tela: str = Field(description="A tela do PRD §4 que consome esta view (T-01..T-07).")
    pergunta: str = Field(description="A frase de abertura da tela (P7 / RF-W035).")
    tag: str
    dataset_sha256: str = Field(min_length=64, max_length=64)
    gate: GateDaView
    fontes: list[str] = Field(description="Artefatos do MANIFEST.json lidos para montar esta view.")


# ─────────────────────────────────────────────────────────────────────────────
# meta.json
# ─────────────────────────────────────────────────────────────────────────────


class AgregadoDoDataset(BaseModel):
    """O bloco `agregado` do `MANIFEST.json`, copiado sem recálculo."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str = Field(min_length=64, max_length=64)
    n_artefatos: int
    n_artefatos_fora_do_agregado: int
    bytes: int
    linhas: int


class DataDoDado(BaseModel):
    """A data **do dado**, nunca a do relógio (`run.py:data_do_dado`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    date_min_raw_series: str | None
    date_max_raw_series: str | None
    vintage_max: str | None
    primeiro_trimestre_macro: str | None
    ultimo_trimestre_macro: str | None


class CongelamentoDoDataset(BaseModel):
    """O bloco `congelamento` do `MANIFEST.json` + se o `FROZEN.txt` existe em disco."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: str | None
    git_commit: str | None
    git_ref: str | None
    frozen_txt_presente: bool
    dataset_congelado: bool = Field(
        description="True só com MANIFEST.congelamento E FROZEN.txt em disco."
    )


class IndiceDaView(BaseModel):
    """Uma entrada do índice de views — com `sha256` e bytes, para RF-W012 ser verificável."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    arquivo: str
    view: str
    tela: str
    slot_arquitetura: str = Field(
        description="O slot em docs/research/ldc-analytics-arquitetura.md §1.1."
    )
    bytes: int
    sha256: str = Field(min_length=64, max_length=64)
    n_registros: int = Field(description="Linhas do payload principal da view.")


class LimitacaoChave(BaseModel):
    """Uma das 10 limitações, com o número medido que a abre (RF-W034)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    numero: int
    texto: str


class ReducaoDeclarada(BaseModel):
    """O que **não** foi exportado nesta tag, e por quê. Omissão declarada nunca é omissão."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    o_que: str
    artefato: str | None
    por_que: str


class OrcamentoDoConjunto(BaseModel):
    """RNF-W001 medido, não estimado."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    limite_bytes: int
    bytes_das_views: int
    ok: bool
    arquivos_contados: int


class MetaWeb(BaseModel):
    """`meta.json` — o manifesto da tag. **Nenhum campo vem do relógio** (CA-121)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_versao: int
    feature: str
    tag: str
    dataset_sha256: str = Field(min_length=64, max_length=64)
    dataset_sha256_curto: str = Field(min_length=12, max_length=12)
    agregado: AgregadoDoDataset
    data_do_dado: DataDoDado
    congelamento: CongelamentoDoDataset
    versao_build: dict[str, str] = Field(
        description="`versao_build` por relatorio_*.json — a etapa do pipeline que gerou o dado."
    )
    web_export_versao_build: str = Field(description="sha256 dos módulos deste exportador.")
    gate: GateDaView
    views: list[IndiceDaView]
    contagens: dict[str, int]
    limitacoes: list[LimitacaoChave]
    n_decisoes_pendentes: int
    unidade_por_campo: dict[str, str]
    casas_por_unidade: dict[str, int]
    unidade_de_apresentacao: dict[str, str] = Field(
        description="campo -> unidade na TELA. O JSON continua na nativa: aqui só a instrução."
    )
    fator_de_apresentacao: dict[str, float] = Field(
        description="campo -> fator (fracao->percentual = 100). O unico numero da conversao."
    )
    casas_de_apresentacao: dict[str, int] = Field(
        description="campo -> casas na tela. 4 casas em fracao sao 2 casas em percentual."
    )
    reducoes: list[ReducaoDeclarada]
    orcamento: OrcamentoDoConjunto
    artefatos_nao_publicaveis: list[str] = Field(
        description="Nome dos artefatos com publicavel:false. Nenhum valor deles é lido ou emitido."
    )
    politica_de_cache: dict[str, str]


class PonteiroCurrent(BaseModel):
    """`current.json` — o **único** arquivo com `no-cache`, no diretório pai da tag (RF-W011)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: str
    dataset_sha256: str = Field(min_length=64, max_length=64)
    meta: str = Field(description="Caminho relativo do meta.json da tag.")
    arquivos: dict[str, str] = Field(
        description="view -> caminho relativo, para o front não adivinhar o nome."
    )
    especificacao_congelada: bool
    cache_control: Literal["no-cache"]
    cache_control_da_tag: Literal["immutable"]


# ─────────────────────────────────────────────────────────────────────────────
# T-01 · ranking_atual.json
# ─────────────────────────────────────────────────────────────────────────────


class RespostaDeRegimeWeb(BaseModel):
    """Uma das **três** respostas a "em que regime estamos" — nenhuma escolhida (RF-W019)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lente_rotulo: str
    lente: str
    lente_titulo: str
    regime: str | None = Field(
        description="O regime da CÉLULA de onde o ranking saiu. Com `e_fallback`, não é 2026Q3."
    )
    status_regime_v1: str | None = Field(
        description="O status do trimestre PERGUNTADO (V1): INDETERMINADO é resposta, não erro."
    )
    motivo_indeterminado: str | None = Field(
        description="Por que o trimestre perguntado não tem quadrante (D-m). Nunca preenchido."
    )
    materializacao: str
    horizonte: str
    quarter_perguntado: str
    quarter_da_celula: str
    e_fallback: bool
    n_obs: int
    alerta_n_baixo: bool
    conclusao_suprimida: bool
    tabela_de_origem: str


class LinhaDeRanking(BaseModel):
    """Uma linha do ranking de ativos de uma lente. `n` e as 2 flags em **toda** linha."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lente_rotulo: str
    lente: str
    regime: str
    asset_id: str
    posicao: int
    n_obs: int
    excesso_cdi: float | None
    ret_medio: float | None
    ret_mediana: float | None
    hit_ratio_cdi: float | None
    erro_padrao_media: float | None
    excesso_em_erros_padrao: float | None
    distinguivel_de_ruido: bool | None
    alerta_n_baixo: bool
    conclusao_suprimida: bool


class LinhaDeConcordancia(BaseModel):
    """Uma linha de `concordancia_lentes.parquet` — Jaccard, Spearman e a distribuição."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    secao: str
    chave: str
    metrica: str
    valor_num: float | None
    valor_texto: str | None


class VizinhoDoQuarter(BaseModel):
    """Um vizinho do trimestre corrente, com o quadrante V1 ou o motivo de não ter (RF-W026)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: int
    quarter_neighbor: str
    distancia: float | None
    quarter_t_mais_1: str | None
    regime_v1_neighbor: str | None
    status_regime_v1_neighbor: str | None


class RankingAtualView(EnvelopeDaView):
    """T-01 — as 3 respostas lado a lado, os 3 rankings e a concordância entre as lentes."""

    quarter_perguntado: str
    respostas: list[RespostaDeRegimeWeb]
    rankings: list[LinhaDeRanking]
    concordancia: list[LinhaDeConcordancia]
    vizinhos_do_quarter: list[VizinhoDoQuarter]
    n_vizinhos: int
    intersecao_dos_top5: list[str] = Field(
        description="Interseção dos top-5 das 3 lentes. Vazia em 3T2026 — primeiro plano (P9)."
    )
    top5_por_lente: dict[str, list[str]]


# ─────────────────────────────────────────────────────────────────────────────
# T-02 · heatmap_regime_ativo.json
# ─────────────────────────────────────────────────────────────────────────────


class CelulaDoHeatmap(BaseModel):
    """Uma célula do mapa de calor, **como plotada** — com `n` no corpo, nunca só no tooltip.

    A célula não repete o que a chave já determina: `(vista, regime)` dá lente, materialização,
    horizonte, tabela de origem e coluna (em `HeatmapView.eixos`), e `asset_id` dá grupo, linha e
    `data_inicio_serie` (em `HeatmapView.ativos`). É **normalização**, não agregação: nenhum valor
    é combinado com outro, e o exportador reprova se a dependência funcional não valer no Parquet.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vista: str
    regime: str
    asset_id: str
    n_obs: int
    excesso_cdi: float | None
    ret_medio: float | None
    ret_mediana: float | None
    erro_padrao_media: float | None
    hit_ratio_cdi: float | None
    pior_tri: float | None
    pior_tri_quarter: str | None
    alerta_n_baixo: bool
    conclusao_suprimida: bool
    hachura: str | None = Field(
        description="Canal SEM cor da supressao (CA-109). Nao e paleta: e o segundo canal."
    )


class EixoDoHeatmap(BaseModel):
    """O que `(vista, regime)` determina: a coluna da grade e de que tabela a célula saiu."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vista: str
    regime: str
    tabela: str
    lente: str
    materializacao: str
    horizonte: str
    coluna: int


class AtivoDoHeatmap(BaseModel):
    """O que `asset_id` determina: o grupo, a linha na ordem **declarada** e a janela própria."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str
    grupo: str
    linha: int
    data_inicio_serie: str | None


class LimiaresDeN(BaseModel):
    """Os dois limiares de `n`, lidos de `regimes_v1`, nunca digitados na tela."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alerta_abaixo_de: int
    supressao_abaixo_de: int
    legenda: dict[str, str]


class ExclusaoDaFigura(BaseModel):
    """O que foi retirado da figura e por quê — a linha segue nas tabelas (Anti-SPEC §10.2.12)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str
    motivo: str


class EixoDeCorDaVista(BaseModel):
    """O **eixo** da escala divergente de uma vista: ±`extremo_simetrico`, por campo pintável.

    **É eixo, não estatística.** Nenhum valor é combinado com outro: `extremo_simetrico` é o
    `max(|valor|)` da vista **inteira**, que é a extensão do eixo de cor — o mesmo papel do
    `ylim` de um gráfico. Não é um achado sobre o dado, não vai a texto do relatório e não entra
    em nenhuma conclusão; serve para que `-x` e `+x` caiam no mesmo passo e o neutro do meio
    signifique "empatou" (ADR-002 §3: simetria obrigatória).

    **Por que vem do exportador, e por vista.** A extensão é sobre a vista inteira, nunca sobre o
    recorte filtrado: se dependesse do filtro, marcar uma classe de ativo repintaria as outras e
    duas leituras da mesma tag deixariam de ser comparáveis. Calculá-la no front obrigava a tela a
    varrer as células a cada requisição e deixava o valor dependente de quem varre; declarada
    aqui, é a mesma para a figura do PDF, para a tela e para qualquer outro consumidor.

    Em unidade **nativa** (D-W4): quem apresenta multiplica pelo `meta.fator_de_apresentacao`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    vista: str
    campo: str
    extremo_simetrico: float | None = Field(
        description="max(|valor|) da vista inteira, unidade nativa. null = nenhum valor na vista."
    )
    limite_inferior: float | None
    limite_superior: float | None
    n_celulas_com_valor: int
    n_celulas: int


class HeatmapView(EnvelopeDaView):
    """T-02 — as **322** células das **3** vistas (115 + 92 + 115), com `n`, erro-padrão e as 2
    flags por célula, mais o eixo de cor de cada vista.

    `v1_revised` e `horizonte_cruzado` têm 115 células (23 ativos × 5 colunas) e `v1_asof` tem 92
    (a V3 não tem materialização `asof`, então falta a coluna de vizinhos) — medido na tag, não
    suposto.
    """

    celulas: list[CelulaDoHeatmap]
    eixos: list[EixoDoHeatmap]
    eixos_de_cor: list[EixoDeCorDaVista]
    ativos: list[AtivoDoHeatmap]
    vistas: list[str]
    regimes: list[str]
    grupos: list[str]
    limiares_de_n: LimiaresDeN
    excluidos_da_figura: list[ExclusaoDaFigura]
    escala: str = Field(description="Divergente SIMÉTRICA em ±extremo — assimétrica é proibida.")
    metrica_padrao: str


# ─────────────────────────────────────────────────────────────────────────────
# T-03 · vizinhos.json
# ─────────────────────────────────────────────────────────────────────────────


class LenteDosVizinhos(BaseModel):
    """A lente exportada, declarada campo a campo — o que muda a resposta está na linha."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metrica: str
    somente_passado: bool
    restrito_pos_2016: bool
    janela_padronizacao: str
    shrinkage: str | None
    n_features: int
    features_usadas: str


class Vizinho(BaseModel):
    """Um vizinho, sem repetir o que já está na chave do grupo (normalização, não agregação)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: int
    quarter_neighbor: str
    distancia: float | None


class RankingDeVizinhos(BaseModel):
    """Os vizinhos de uma referência num `k` — a chave sai do grupo, não de cada linha."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quarter_ref: str
    k_usado: int
    n_vizinhos: int
    vizinhos: list[Vizinho]


class QuadranteDoQuarter(BaseModel):
    """O quadrante V1 de um trimestre — ou o motivo de ele não ter (D-m)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    regime_v1: str | None
    status_regime_v1: str | None


class LinhaDoRankingT1(BaseModel):
    """Uma linha do ranking medido em **T+1** dos vizinhos, com barra de erro (RF-W027)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str
    n_obs: int
    excesso_cdi: float | None
    ret_medio: float | None
    ret_mediana: float | None
    erro_padrao_media: float | None
    hit_ratio_cdi: float | None
    alerta_n_baixo: bool
    conclusao_suprimida: bool


class VizinhosView(EnvelopeDaView):
    """T-03 — "momentos semelhantes": a lente canônica, os 3 `k` e o ranking em T+1."""

    lente: LenteDosVizinhos
    ks: list[int]
    k_completo: int
    regra_de_truncamento: str
    referencias: list[str]
    rankings: list[RankingDeVizinhos]
    quadrante_por_quarter: dict[str, QuadranteDoQuarter]
    t_mais_1_por_quarter: dict[str, str]
    quarter_do_comite: str
    ranking_t_mais_1: list[LinhaDoRankingT1]
    declaracoes: list[str] = Field(
        description="O que a tela diz: 5 features de 6, o que somente_passado não elimina."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-04 · regimes_timeline.json
# ─────────────────────────────────────────────────────────────────────────────


class PontoDaTimeline(BaseModel):
    """Um trimestre × materialização. O rótulo da faixa indexa o estilo **e** o quadrante.

    `regime_v1`, `status_regime_v1` e `hachura` não se repetem 166 vezes: o
    `rotulo_da_faixa` os determina (5 rótulos, conferido pelo exportador) e eles vivem em
    `TimelineView.estilo_por_rotulo`. `quarter_end`, `ibov_nivel` e `selic_meta_pct` são idênticos
    nas duas materializações — são mercado, não regime — e vivem em
    `TimelineView.mercado_por_quarter`, também conferido.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    materializacao: str
    quarter: str
    rotulo_da_faixa: str
    n_obs_regime_v1: int
    trocou_vs_outra_materializacao: bool
    tipo_de_troca: str


class EstiloDaFaixa(BaseModel):
    """O que um rótulo de faixa determina — `INDETERMINADO` é hachura, nunca uma 5ª cor (P10).

    **Sem cor** (D-ai): o rótulo e a hachura são semântica do regime, que é do pipeline; o hex é
    decisão de apresentação, que é de quem desenha. Ver `CelulaDoHeatmap`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    regime_v1: str | None
    status_regime_v1: str
    hachura: str | None


class MercadoDoQuarter(BaseModel):
    """O que não depende da materialização: fim do trimestre, IBOV (índice) e Selic (% a.a.)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quarter_end: str | None
    ibov_nivel: float | None
    selic_meta_pct: float | None


class DivergenciaDeMaterializacao(BaseModel):
    """As 22 trocas de rótulo `asof` × `revised` em 66 comparáveis — 33,33% (RF-W029)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_divergencias: int
    n_comparaveis: int
    pct: float | None
    limiar_pct: float | None
    acima_do_limiar: bool | None
    quarters: list[str]


class DistribuicaoDeRegimes(BaseModel):
    """19/19/16/13 + 16 indeterminados — ausência **rotulada**, nunca uma 5ª cor (P10)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    por_grupo: dict[str, int]
    n_indeterminados: int
    quarters_indeterminados: list[str]
    desbalanceamento: float | None


class TimelineView(EnvelopeDaView):
    """T-04 — 83 trimestres × 2 materializações, com IBOV, Selic e as divergências."""

    trimestres: list[PontoDaTimeline]
    estilo_por_rotulo: dict[str, EstiloDaFaixa]
    mercado_por_quarter: dict[str, MercadoDoQuarter]
    materializacoes: list[str]
    divergencia: DivergenciaDeMaterializacao
    distribuicao: DistribuicaoDeRegimes
    n_trimestres: int
    janela: str


# ─────────────────────────────────────────────────────────────────────────────
# T-06 · internacional.json
# ─────────────────────────────────────────────────────────────────────────────


class CelulaInternacional(BaseModel):
    """Uma célula de `internacional_por_regime` — retorno **em BRL**, importado de F-022."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lente: str
    regime: str
    asset_id: str
    n_obs: int
    ret_medio: float | None
    ret_mediana: float | None
    excesso_cdi: float | None
    ret_real: float | None
    hit_ratio_cdi: float | None
    corr_ibov: float | None
    n_pares_ibov: int | None
    corr_imab: float | None
    n_pares_imab: int | None
    is_total_return: bool | None
    alerta_n_baixo: bool
    conclusao_suprimida: bool


class BlocoDeCorrelacao(BaseModel):
    """`corr(USDBRL, IBOV)` num bloco — **sempre** com o `n` de pares (RF-W031)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bloco: str
    corr: float | None
    n_pares: int | None


class FaixaDeD6(BaseModel):
    """A faixa de D6 — **faixa**, nunca ponto (CA-107 / RF-W032)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ativo_representativo: str
    piso_estrutural_min: float | None
    piso_estrutural_max: float | None
    banda_tatica_min: float | None
    banda_tatica_max: float | None
    cap_usado: float | None
    forma: str
    distincao_obrigatoria: str
    decisao: str


class RegraDeStress(BaseModel):
    """20 de 83 por ramo, 14 não avaliáveis **nomeados**, ramo risco-país declaradamente fora."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_stress: int | None
    n_total: int | None
    quarters_nao_avaliaveis: list[str]
    ramo_fora: str
    cai_sobre: str


class PiorTrimestreDoIbov(BaseModel):
    """Um dos 10 piores trimestres do IBOV, com a variação do dólar e a flag de stress."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    quarter: str
    ret_ibov: float | None
    ret_usdbrl: float | None
    stress_flag: bool


class OmissaoDoGate(BaseModel):
    """O que o gate cortou desta view, com o nome do artefato e o motivo do `MANIFEST.json`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artefato: str
    motivo: str


class InternacionalView(EnvelopeDaView):
    """T-06 — o internacional em BRL por regime, as correlações e a faixa. **Sem** variância
    mínima.
    """

    celulas: list[CelulaInternacional]
    lentes: list[str]
    assets: list[str]
    correlacoes: list[BlocoDeCorrelacao]
    faixa_d6: FaixaDeD6
    regra_de_stress: RegraDeStress
    dez_piores_do_ibov: list[PiorTrimestreDoIbov]
    omitido_pelo_gate: list[OmissaoDoGate]
    proxies_indisponiveis: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# T-07 · catalogo.json
# ─────────────────────────────────────────────────────────────────────────────


class SerieDoCatalogo(BaseModel):
    """Uma série do catálogo, com cobertura **declarada** ao lado da **observada** (RF-W033)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    series_id: str
    nome: str
    item_email: str | None
    fonte: str
    freq: str
    unit: str
    status: str
    confianca: str
    lag_divulgacao_dias: int | None
    data_inicio: str | None
    data_inicio_observada: str | None
    data_fim: str | None
    data_fim_observada: str | None
    presente_no_processed: bool
    cobre_1t2006: bool | None
    n_obs: int | None
    pct_nulos: float | None
    fonte_url: str | None


class ArtefatoPublicado(BaseModel):
    """Um artefato `publicavel: true` do `MANIFEST.json`, com o perfil de CA-118."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    arquivo: str
    linhas: int | None
    colunas: int | None
    bytes: int | None
    sha256: str | None
    date_min: str | None
    date_max: str | None
    pct_nulos: float | None
    determinista: bool


class DecisaoPendente(BaseModel):
    """Uma das 12 decisões da §7 de `LIMITACOES-COMITE.md`, com o custo de discordar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    decisao: str
    padrao_provisorio: str
    se_discordar: str


class StatusDeAdr(BaseModel):
    """O status de um ADR como está **em disco** — o portal mostra, nunca edita."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    arquivo: str
    status: str


class CoberturaDoCatalogo(BaseModel):
    """Quantas séries existem, quantas chegaram e quantas cobrem 1T2006."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_series: int
    n_presentes: int
    n_cobrem_1t2006: int


class CatalogoView(EnvelopeDaView):
    """T-07 — de onde veio cada número, o que ele não sustenta e o que não foi decidido."""

    series: list[SerieDoCatalogo]
    cobertura: CoberturaDoCatalogo
    artefatos: list[ArtefatoPublicado]
    artefatos_nao_publicaveis: list[OmissaoDoGate]
    limitacoes: list[LimitacaoChave]
    decisoes_pendentes: list[DecisaoPendente]
    adrs: list[StatusDeAdr]
    reducoes: list[ReducaoDeclarada]


# ─────────────────────────────────────────────────────────────────────────────
# O índice — uma só definição por conceito
# ─────────────────────────────────────────────────────────────────────────────

VIEWS: dict[str, type[EnvelopeDaView]] = {
    "ranking_atual": RankingAtualView,
    "heatmap_regime_ativo": HeatmapView,
    "vizinhos": VizinhosView,
    "regimes_timeline": TimelineView,
    "internacional": InternacionalView,
    "catalogo": CatalogoView,
}
"""As **6** views de `[arq §1.1]`, por nome de arquivo (sem `.json`). O gate vale para todas."""

SLOT_DA_VIEW: dict[str, str] = {
    "ranking_atual": "ranking_atual",
    "heatmap_regime_ativo": "heatmap_regime_ativo",
    "vizinhos": "vizinhos",
    "regimes_timeline": "regimes_timeline",
    "internacional": "internacional",
    "catalogo": "macro_series",
}
"""De cada view para o slot de `docs/research/ldc-analytics-arquitetura.md §1.1`.

`catalogo` ocupa o slot `macro_series` porque a tela que o MVP precisa é a **T-07** (condição para
qualquer número ser publicável) e as séries macro que alguma tela do MVP consome — Selic e IBOV por
trimestre — viajam dentro de `regimes_timeline`, onde a T-04 as usa. Decisão registrada no ADR-008.
"""

MODELOS_DO_CONTRATO: tuple[type[BaseModel], ...] = (
    MetaWeb,
    PonteiroCurrent,
    RankingAtualView,
    HeatmapView,
    VizinhosView,
    TimelineView,
    InternacionalView,
    CatalogoView,
)
"""A raiz da geração de `schema.d.ts`: tudo alcançável daqui entra no `.d.ts`."""

SCHEMA_VERSAO = 2
"""Versão do contrato das views. Campo novo não quebra o front; remoção de campo sobe isto.

**1 → 2** (2026-10-11, o acerto com o módulo do portal, `MODULO-ANALYTICS-MACRO.md §2`):

- `meta.json` ganhou `unidade_de_apresentacao`, `fator_de_apresentacao` e `casas_de_apresentacao`
  (acréscimo — não quebraria nada por si);
- `heatmap_regime_ativo.json` ganhou `eixos_de_cor` (acréscimo);
- **`cor_hex` saiu** de `CelulaDoHeatmap` e de `EstiloDaFaixa` (**D-ai**) — é *remoção*, e é por
  isso que a versão sobe. Quem lia o campo tem de ler `eixos_de_cor` + a própria rampa.
"""
