"""As **6 views** do portal, montadas dos Parquet congelados — zero metodologia recalculada.

Regra única deste módulo (P4 do PRD): **ler e reformatar, nunca recalcular**. Nenhuma média,
mediana, correlação, Mahalanobis ou razão-vs-subtração acontece aqui — todas já estão no
`data/canonical/`, produzidas pela feature dona. Se um número está errado numa tela, o bug é da
feature do pipeline, nunca desta ponte. O que este módulo faz, e só:

1. **seleciona** colunas que estão no contrato de `packages/shared/schemas/web_views.py`;
2. **normaliza** `NaN`/`pd.NA`/`numpy` para JSON (`null`, `int`, `float`, `bool`);
3. **arredonda** com casas fixas por unidade declarada (`CASAS_POR_UNIDADE`);
4. **normaliza** a forma (agrupa vizinhos por referência, indexa quadrante por trimestre) — isso é
   normalização relacional, **não** agregação: nenhum valor é combinado com outro.

As duas flags de `n` vêm do Parquet **e** são reconferidas contra `regimes_v1.alerta_n_baixo` /
`regimes_v1.conclusao_suprimida` (importadas, nunca reimplementadas). Divergência levanta: é o
sinal de que o limiar mudou no pipeline e a ponte ficou para trás.

| View | Tela | Artefatos lidos |
|---|---|---|
| `ranking_atual` | T-01 | `tabelas/ranking_regime_atual`, `tabelas/concordancia_lentes`,
`regimes_v1{,_asof}`, `regime_neighbors_v3`, `relatorio_metricas` |
| `heatmap_regime_ativo` | T-02 | `figuras/heatmap_dados` |
| `vizinhos` | T-03 | `regime_neighbors_v3`, `regimes_v1`, `relatorio_regimes_v3` |
| `regimes_timeline` | T-04 | `figuras/timeline_regimes_dados`, `relatorio_regimes_v1` |
| `internacional` | T-06 | `internacional_por_regime`, `relatorio_internacional` |
| `catalogo` | T-07 | `series_catalog`, `MANIFEST.json`, caderno (10 limitações),
`LIMITACOES-COMITE.md §7`, os 7 ADRs |
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from apps.analysis.entrega.montar_pacote import (
    artefatos_do_manifesto,
    decisoes_a_ratificar,
    limitacoes_do_notebook,
)
from apps.pipeline.canonical.metricas_regime import LENTE_V1
from apps.pipeline.canonical.regimes_v1 import alerta_n_baixo, conclusao_suprimida
from apps.pipeline.canonical.regimes_v3 import FEATURES_USADAS, QUARTER_DO_COMITE, Lente
from apps.pipeline.common.errors import SerieInconsistente
from apps.pipeline.common.io_layers import caminho_canonical, raiz_repo
from packages.shared.schemas.regimes import MetricaDistancia
from packages.shared.schemas.web_views import (
    CASAS_PADRAO,
    CASAS_POR_UNIDADE,
    UNIDADE_POR_CAMPO,
)

METRICA_MAHALANOBIS = MetricaDistancia.MAHALANOBIS.value
"""A métrica da lente canônica — do enum do contrato, nunca da string literal."""

# ─────────────────────────────────────────────────────────────────────────────
# Artefatos lidos — lista fechada, conferida contra o `publicavel` do manifesto
# ─────────────────────────────────────────────────────────────────────────────

NOME_RANKING = "tabelas/ranking_regime_atual.parquet"
NOME_CONCORDANCIA = "tabelas/concordancia_lentes.parquet"
NOME_HEATMAP = "figuras/heatmap_dados.parquet"
NOME_TIMELINE = "figuras/timeline_regimes_dados.parquet"
NOME_REGIMES_V1 = "regimes_v1.parquet"
NOME_REGIMES_V1_ASOF = "regimes_v1_asof.parquet"
NOME_NEIGHBORS_V3 = "regime_neighbors_v3.parquet"
NOME_INTERNACIONAL = "internacional_por_regime.parquet"
NOME_SERIES_CATALOG = "series_catalog.parquet"
NOME_RELATORIO_METRICAS = "relatorio_metricas.json"
NOME_RELATORIO_V1 = "relatorio_regimes_v1.json"
NOME_RELATORIO_V3 = "relatorio_regimes_v3.json"
NOME_RELATORIO_INTERNACIONAL = "relatorio_internacional.json"

ARTEFATOS_LIDOS: tuple[str, ...] = (
    NOME_CONCORDANCIA,
    NOME_HEATMAP,
    NOME_INTERNACIONAL,
    NOME_NEIGHBORS_V3,
    NOME_RANKING,
    NOME_REGIMES_V1,
    NOME_REGIMES_V1_ASOF,
    NOME_RELATORIO_INTERNACIONAL,
    NOME_RELATORIO_METRICAS,
    NOME_RELATORIO_V1,
    NOME_RELATORIO_V3,
    NOME_SERIES_CATALOG,
    NOME_TIMELINE,
)
"""Tudo que o exportador abre. Nada fora desta lista é lido — e a lista **não vence o manifesto**.

O princípio é o de F-031: se o `MANIFEST.json` marcar qualquer um destes como `publicavel: false`,
o exportador **recusa rodar** em vez de omitir a view em silêncio.
"""

ARTEFATOS_PROIBIDOS: tuple[str, ...] = (
    "alinhado_trimestral.parquet",
    "internacional_pesos.parquet",
    "ldc.duckdb",
    "macro_quarterly_asof_provenance.parquet",
    "macro_quarterly_provenance.parquet",
    "raw_series.parquet",
    "regime_neighbors.parquet",
)
"""RF-W015: o portal não consome estes. `internacional_pesos` por `publicavel: false` (**D-af**);
`regime_neighbors` por ser **variante de contrato** (perde 4 dos 8 vizinhos de `2026Q3`);
`ldc.duckdb` por ser `determinista: false`; `raw_series`, `alinhado_trimestral` e os `*_provenance`
por volume e por não alimentarem nenhuma das 7 telas.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Reduções declaradas — omissão declarada nunca é omissão
# ─────────────────────────────────────────────────────────────────────────────

LENTE_CANONICA = Lente(somente_passado=True, restrito_pos_2016=False)
"""A lente exportada na view de vizinhos: `somente_passado`, janela cheia, Mahalanobis."""

KS_EXPORTADOS: tuple[int, ...] = (5, 8, 12)
"""Os 3 `k` que a T-03 oferece como filtro."""

K_COMPLETO = max(KS_EXPORTADOS)
"""O `k` cujo ranking é emitido. Os outros dois são **prefixo** dele — conferido, não suposto."""

REGRA_DE_TRUNCAMENTO = (
    "O ranking emitido e o de k=12. O ranking de k=5 e de k=8 e o PREFIXO de tamanho k deste "
    "mesmo ranking: na lente canonica, as 58 referencias tem a sequencia de vizinhos identica "
    "nos tres k (conferido em 58/58, zero divergencias, em tests/unit/test_web_export.py). "
    "Truncar nao e recalcular: a distancia de cada vizinho vem do Parquet, linha a linha."
)

ASSET_FORA_DA_FIGURA = "SP500_USD"
MOTIVO_FORA_DA_FIGURA = (
    "retorno em USD contra o CDI em BRL mistura duas moedas na mesma celula e a celula deixa de "
    "ter leitura (Anti-SPEC 10.2.12). A linha NAO foi apagada do dado: segue nas tabelas de "
    "metricas por regime."
)

ESCALA_DO_HEATMAP = (
    "divergente SIMETRICA em +/- extremo: o cinza do meio significa 'empatou com o CDI'. "
    "Escala assimetrica e proibida (PRD T-02)."
)

PERGUNTA_POR_VIEW: dict[str, str] = {
    "ranking_atual": "Em que regime estamos - tres vezes - e por que as lentes discordam?",
    "heatmap_regime_ativo": (
        "Em cada regime, qual classe bateu o CDI e por quanto, com quantas observacoes?"
    ),
    "vizinhos": (
        "Quais trimestres se parecem com este, e o que rendeu no trimestre SEGUINTE a cada um?"
    ),
    "regimes_timeline": (
        "A classificacao faz sentido para quem viveu o periodo, e onde asof e revised discordam?"
    ),
    "internacional": (
        "O internacional em BRL rendeu o que em cada regime, o cambio protege quando doi, e que "
        "FAIXA o dado sustenta?"
    ),
    "catalogo": "De onde veio cada numero, o que ele nao sustenta, e o que ainda nao foi decidido?",
}

TELA_POR_VIEW: dict[str, str] = {
    "ranking_atual": "T-01",
    "heatmap_regime_ativo": "T-02",
    "vizinhos": "T-03",
    "regimes_timeline": "T-04",
    "internacional": "T-06",
    "catalogo": "T-07",
}

ADRS_DO_PORTAL: tuple[tuple[str, str], ...] = (
    ("ADR-001", "ADR-001-lente-de-regime-oficial.md"),
    ("ADR-002", "ADR-002-metrica-primaria-do-heatmap.md"),
    ("ADR-003", "ADR-003-abordagem-alocacao-internacional.md"),
    ("ADR-004", "ADR-004-inclinacao-curva-via-tesouro-direto.md"),
    ("ADR-005", "ADR-005-janelas-proprias-e-fii-segmentado.md"),
    ("ADR-006", "ADR-006-armazenamento-e-convencao-de-retornos.md"),
    ("ADR-007", "ADR-007-sem-supabase-na-v1.md"),
)
"""Os 7 ADRs que a T-07 mostra (RF-W033). O portal **mostra** o status; mudar é editar o arquivo."""

PASTA_DOS_ADRS = Path("docs") / "decisions" / "adr"
_RE_STATUS_DE_ADR = re.compile(r"^-\s*\*\*Status:\*\*\s*(?P<valor>.+)$", re.MULTILINE)
STATUS_DESCONHECIDO = "DESCONHECIDO"


# ─────────────────────────────────────────────────────────────────────────────
# Normalização de valor — o único lugar onde float vira texto JSON
# ─────────────────────────────────────────────────────────────────────────────


def casas_do_campo(campo: str) -> int:
    """Casas decimais declaradas para o campo, pela unidade dele. Sem adivinhação por valor."""
    unidade = UNIDADE_POR_CAMPO.get(campo)
    if unidade is None:
        return CASAS_PADRAO
    return CASAS_POR_UNIDADE.get(unidade, CASAS_PADRAO)


def escalar(valor: Any, *, campo: str) -> Any:
    """Um valor do Parquet como JSON: `null` para ausente, casas fixas para float.

    `campo` é o nome **emitido**, não o da coluna de origem: é por ele que `UNIDADE_POR_CAMPO`
    decide as casas, e um teste de contrato exige que todo campo numérico publicado esteja lá.
    Passar o nome da fonte faria o campo arredondar pelo padrão sem ninguém notar.

    `-0.0` é normalizado para `0.0`: o sinal do zero muda o byte do JSON sem mudar o número, e
    duas exportações da mesma tag têm de ser byte-idênticas (CA-121).
    """
    if valor is None or valor is pd.NA:
        return None
    if isinstance(valor, float | int) and not isinstance(valor, bool) and pd.isna(valor):
        return None
    if isinstance(valor, bool):
        return valor
    if hasattr(valor, "item") and not isinstance(valor, str):
        valor = valor.item()
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            return None
        arredondado = round(valor, casas_do_campo(campo))
        return 0.0 if arredondado == 0 else arredondado
    if isinstance(valor, pd.Timestamp):
        return valor.date().isoformat()
    texto = str(valor)
    return None if texto in {"nan", "NaT", "<NA>"} else texto


def registro(linha: pd.Series, campos: tuple[str, ...]) -> dict[str, Any]:
    """Uma linha do Parquet nos campos do contrato, nessa ordem. Campo ausente levanta."""
    faltando = [c for c in campos if c not in linha.index]
    if faltando:
        msg = f"a tabela de origem nao tem as colunas do contrato da view: {faltando}"
        raise SerieInconsistente(msg)
    return {campo: escalar(linha[campo], campo=campo) for campo in campos}


def registros(quadro: pd.DataFrame, campos: tuple[str, ...]) -> list[dict[str, Any]]:
    """A tabela inteira nos campos do contrato, na ordem em que o Parquet está."""
    return [registro(linha, campos) for _, linha in quadro.iterrows()]


def conferir_flags_de_n(quadro: pd.DataFrame, *, de_onde: str) -> None:
    """As 2 flags do Parquet batem com os limiares que `regimes_v1` publica? Senão, levanta.

    É a trava contra o pior erro desta ponte: limiar de `n` mudar no pipeline e o JSON publicar a
    flag antiga. As funções vêm importadas — reimplementá-las aqui criaria uma segunda verdade.
    """
    for _, linha in quadro.iterrows():
        n = int(linha["n_obs"])
        if bool(linha["alerta_n_baixo"]) != alerta_n_baixo(n):
            msg = (
                f"{de_onde}: alerta_n_baixo={linha['alerta_n_baixo']} com n={n}, mas "
                f"regimes_v1.alerta_n_baixo({n})={alerta_n_baixo(n)}"
            )
            raise SerieInconsistente(msg)
        if bool(linha["conclusao_suprimida"]) != conclusao_suprimida(n):
            msg = (
                f"{de_onde}: conclusao_suprimida={linha['conclusao_suprimida']} com n={n}, mas "
                f"regimes_v1.conclusao_suprimida({n})={conclusao_suprimida(n)}"
            )
            raise SerieInconsistente(msg)


def exigir_dependencia_funcional(
    quadro: pd.DataFrame, *, chave: tuple[str, ...], dependentes: tuple[str, ...], de_onde: str
) -> None:
    """`chave` determina `dependentes`? É o que autoriza tirar a coluna da célula e indexá-la.

    Sem esta trava, "normalizar para caber no orçamento" poderia **perder** informação em silêncio
    no dia em que o pipeline passasse a ter dois `grupo` para o mesmo ativo. Com ela, a exportação
    para e nomeia a coluna.
    """
    contagem = quadro.groupby(list(chave), dropna=False)[list(dependentes)].nunique()
    quebradas = [coluna for coluna in dependentes if int(contagem[coluna].max()) > 1]
    if quebradas:
        msg = (
            f"{de_onde}: {chave} nao determina {quebradas} - a view indexa essas colunas por "
            f"{chave} e normalizar perderia informacao. Corrija o Parquet ou a view."
        )
        raise SerieInconsistente(msg)


def primeiros_por(
    quadro: pd.DataFrame, *, chave: tuple[str, ...], campos: tuple[str, ...]
) -> list[dict[str, Any]]:
    """Uma linha por `chave`, com `chave + campos`, ordenada pela chave. Nada é combinado."""
    exigir_dependencia_funcional(quadro, chave=chave, dependentes=campos, de_onde="normalizacao")
    achados: list[dict[str, Any]] = []
    for valores, grupo in quadro.groupby(list(chave), dropna=False, sort=True):
        tupla = valores if isinstance(valores, tuple) else (valores,)
        linha = grupo.iloc[0]
        achados.append(
            {
                **{
                    nome: escalar(valor, campo=nome)
                    for nome, valor in zip(chave, tupla, strict=True)
                },
                **{campo: escalar(linha[campo], campo=campo) for campo in campos},
            }
        )
    return achados


# ─────────────────────────────────────────────────────────────────────────────
# Leitura
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Contexto:
    """O que toda view precisa saber antes de montar o seu payload."""

    raiz: Path | None
    tag: str
    dataset_sha256: str
    gate: dict[str, Any]
    manifesto: dict[str, Any]

    def ler_parquet(self, nome: str) -> pd.DataFrame:
        if nome not in ARTEFATOS_LIDOS:
            msg = (
                f"{nome} nao esta em ARTEFATOS_LIDOS: o exportador nao abre artefato fora da lista"
            )
            raise SerieInconsistente(msg)
        return pd.read_parquet(caminho_canonical(nome, raiz=self.raiz))

    def ler_relatorio(self, nome: str) -> dict[str, Any]:
        if nome not in ARTEFATOS_LIDOS:
            msg = (
                f"{nome} nao esta em ARTEFATOS_LIDOS: o exportador nao abre artefato fora da lista"
            )
            raise SerieInconsistente(msg)
        alvo = caminho_canonical(nome, raiz=self.raiz)
        return json.loads(alvo.read_text(encoding="utf-8"))

    def envelope(self, view: str, *, fontes: tuple[str, ...]) -> dict[str, Any]:
        return {
            "view": view,
            "tela": TELA_POR_VIEW[view],
            "pergunta": PERGUNTA_POR_VIEW[view],
            "tag": self.tag,
            "dataset_sha256": self.dataset_sha256,
            "gate": dict(self.gate),
            "fontes": sorted(fontes),
        }


def status_dos_adrs(*, raiz: Path | None = None) -> list[dict[str, str]]:
    """O `Status` dos 7 ADRs como está em disco. Falha fechada: ausente ⇒ `DESCONHECIDO`.

    O **gate** nunca passa por aqui: ele usa `regimes_v1.status_adr_001` (importada). Esta lista é
    o conteúdo informativo da T-07, e o teste de contrato exige que as duas concordem no ADR-001.
    """
    base = (raiz or raiz_repo()) / PASTA_DOS_ADRS
    achados: list[dict[str, str]] = []
    for identificador, arquivo in ADRS_DO_PORTAL:
        alvo = base / arquivo
        status = STATUS_DESCONHECIDO
        try:
            texto = alvo.read_text(encoding="utf-8")
        except OSError:
            texto = ""
        encontrado = _RE_STATUS_DE_ADR.search(texto) if texto else None
        if encontrado is not None:
            bruto = encontrado.group("valor").replace("*", " ")
            primeira = re.split(r"[\s—\-:,.]+", bruto.strip(), maxsplit=1)[0]
            status = primeira.strip().upper() or STATUS_DESCONHECIDO
        achados.append({"id": identificador, "arquivo": arquivo, "status": status})
    return achados


# ─────────────────────────────────────────────────────────────────────────────
# T-01 · ranking_atual
# ─────────────────────────────────────────────────────────────────────────────

CAMPOS_DA_RESPOSTA: tuple[str, ...] = (
    "lente_rotulo",
    "lente",
    "lente_titulo",
    "regime",
    "materializacao",
    "horizonte",
    "quarter_perguntado",
    "quarter_da_celula",
    "e_fallback",
    "n_obs",
    "alerta_n_baixo",
    "conclusao_suprimida",
    "tabela_de_origem",
)

CAMPOS_DO_RANKING: tuple[str, ...] = (
    "lente_rotulo",
    "lente",
    "regime",
    "asset_id",
    "posicao",
    "n_obs",
    "excesso_cdi",
    "ret_medio",
    "ret_mediana",
    "hit_ratio_cdi",
    "erro_padrao_media",
    "excesso_em_erros_padrao",
    "distinguivel_de_ruido",
    "alerta_n_baixo",
    "conclusao_suprimida",
)

CAMPOS_DA_CONCORDANCIA: tuple[str, ...] = (
    "secao",
    "chave",
    "metrica",
    "valor_num",
    "valor_texto",
)

CAMPOS_DO_VIZINHO_DO_QUARTER: tuple[str, ...] = (
    "rank",
    "quarter_neighbor",
    "distancia",
    "quarter_t_mais_1",
    "regime_v1_neighbor",
    "status_regime_v1_neighbor",
)


def _quadrante_de(regimes: pd.DataFrame, quarter: str) -> dict[str, Any]:
    fatia = regimes.loc[regimes["quarter"] == quarter]
    if fatia.empty:
        return {"status_regime_v1": None, "motivo_indeterminado": None}
    linha = fatia.iloc[0]
    return {
        "status_regime_v1": escalar(linha["status_regime_v1"], campo="status_regime_v1"),
        "motivo_indeterminado": escalar(
            linha["motivo_indeterminado"], campo="motivo_indeterminado"
        ),
    }


def ranking_atual(ctx: Contexto) -> dict[str, Any]:
    """T-01 — as 3 respostas, os 3 rankings, a concordância e os vizinhos do trimestre."""
    ranking = ctx.ler_parquet(NOME_RANKING)
    concordancia = ctx.ler_parquet(NOME_CONCORDANCIA)
    revised = ctx.ler_parquet(NOME_REGIMES_V1)
    asof = ctx.ler_parquet(NOME_REGIMES_V1_ASOF)
    vizinhos = ctx.ler_parquet(NOME_NEIGHBORS_V3)
    metricas = ctx.ler_relatorio(NOME_RELATORIO_METRICAS)
    conferir_flags_de_n(ranking, de_onde=NOME_RANKING)

    quarter = str(ranking["quarter_perguntado"].iloc[0])
    respostas: list[dict[str, Any]] = []
    for rotulo in ranking["lente_rotulo"].drop_duplicates():
        bloco = ranking.loc[ranking["lente_rotulo"] == rotulo]
        base = registro(bloco.iloc[0], CAMPOS_DA_RESPOSTA)
        materializacao = str(base["materializacao"])
        # O quadrante é o do trimestre **perguntado**, não o da célula: a resposta da V1 revised a
        # "em que regime estamos" é `INDETERMINADO` com motivo, e o `2026Q2` do `quarter_da_celula`
        # é o **fallback declarado** de onde o ranking saiu (`e_fallback`). Trocar os dois faria a
        # tela dizer "ESTAGFLACAO" onde o pipeline diz "sem quadrante" — o erro que RF-W019 proíbe.
        quadrante = (
            _quadrante_de(
                asof if materializacao == "asof" else revised, str(base["quarter_perguntado"])
            )
            if base["lente"] == LENTE_V1
            else {"status_regime_v1": None, "motivo_indeterminado": None}
        )
        respostas.append({**base, **quadrante})

    do_comite = vizinhos.loc[
        (vizinhos["quarter_ref"] == QUARTER_DO_COMITE)
        & (vizinhos["metrica"] == METRICA_MAHALANOBIS)
        & (vizinhos["somente_passado"] == LENTE_CANONICA.somente_passado)
        & (vizinhos["restrito_pos_2016"] == LENTE_CANONICA.restrito_pos_2016)
        & (vizinhos["k_usado"] == 8)
    ].sort_values("rank")

    concordancia_entre = metricas.get("concordancia_entre_lentes") or {}
    top_por_lente = {
        str(chave): [str(item) for item in valores]
        for chave, valores in (concordancia_entre.get("top_por_lente") or {}).items()
    }
    return {
        **ctx.envelope(
            "ranking_atual",
            fontes=(
                NOME_RANKING,
                NOME_CONCORDANCIA,
                NOME_REGIMES_V1,
                NOME_REGIMES_V1_ASOF,
                NOME_NEIGHBORS_V3,
                NOME_RELATORIO_METRICAS,
            ),
        ),
        "quarter_perguntado": quarter,
        "respostas": respostas,
        "rankings": registros(ranking, CAMPOS_DO_RANKING),
        "concordancia": registros(concordancia, CAMPOS_DA_CONCORDANCIA),
        "vizinhos_do_quarter": registros(do_comite, CAMPOS_DO_VIZINHO_DO_QUARTER),
        "n_vizinhos": int(len(do_comite)),
        "intersecao_dos_top5": [
            str(item) for item in (concordancia_entre.get("em_todas_as_lentes") or [])
        ],
        "top5_por_lente": top_por_lente,
    }


# ─────────────────────────────────────────────────────────────────────────────
# T-02 · heatmap_regime_ativo
# ─────────────────────────────────────────────────────────────────────────────

#: **Sem `cor_hex`** (D-ai, 2026-10-11): a coluna existe no Parquet da figura (é o hex matplotlib
#: da paleta placeholder da skill `dataviz`) e **não** é emitida. Cor é decisão de apresentação, e
#: o portal pinta com a rampa da LDC — publicar o hex do PDF criava duas verdades de cor sem
#: nenhum consumidor da segunda. O que fica é o que tem significado: `conclusao_suprimida` e
#: `hachura`, que são canais **sem cor** (CA-109) e vêm do pipeline.
CAMPOS_DA_CELULA: tuple[str, ...] = (
    "vista",
    "regime",
    "asset_id",
    "n_obs",
    "excesso_cdi",
    "ret_medio",
    "ret_mediana",
    "erro_padrao_media",
    "hit_ratio_cdi",
    "pior_tri",
    "pior_tri_quarter",
    "alerta_n_baixo",
    "conclusao_suprimida",
    "hachura",
)

CAMPOS_DO_EIXO_DE_COR: tuple[str, ...] = (
    "excesso_cdi",
    "ret_medio",
    "ret_mediana",
    "pior_tri",
)
"""Os campos **divergentes em torno do zero** — os únicos que têm eixo de cor simétrico.

`hit_ratio_cdi` (0 a 1) e `erro_padrao_media` (≥ 0) ficam fora de propósito: forçar simetria em
±extremo numa grandeza que não cruza o zero daria um eixo em que o meio não significa nada.
"""

CHAVE_DO_EIXO: tuple[str, ...] = ("vista", "regime")
CAMPOS_DO_EIXO: tuple[str, ...] = ("tabela", "lente", "materializacao", "horizonte", "coluna")
CHAVE_DO_ATIVO: tuple[str, ...] = ("asset_id",)
CAMPOS_DO_ATIVO: tuple[str, ...] = ("grupo", "linha", "data_inicio_serie")

LEGENDA_DE_N: dict[str, str] = {
    "n_maior_igual_8": "cor divergente + o numero + o n na celula",
    "n_entre_5_e_7": "cor + borda tracejada + '*': alerta, o n continua visivel",
    "n_menor_que_5": (
        "cinza hachurado + 'prelim.': o valor vem no JSON com conclusao_suprimida=true e PERDE a "
        "cor divergente. O numero existe; a conclusao, nao."
    ),
}


def eixos_de_cor(celulas: pd.DataFrame) -> list[dict[str, Any]]:
    """O eixo da escala divergente por `(vista, campo)`: ±`max(|valor|)` da **vista inteira**.

    É extensão de eixo, não estatística: nenhum valor é combinado com outro, o resultado não é um
    achado sobre o dado e não entra em texto nenhum — é o `ylim` da grade de cor, e existe para
    que `-x` e `+x` caiam no mesmo passo (simetria obrigatória, ADR-002 §3).

    Sobre a vista **inteira** e nunca sobre o recorte: extremo que dependesse do filtro repintaria
    as outras classes quando alguém marcasse uma, e duas leituras da mesma tag deixariam de ser
    comparáveis. Em unidade **nativa** (D-W4) e arredondado pelas casas do próprio campo, então o
    valor publicado é exatamente um dos valores que a célula mostra — nunca um número a mais de
    precisão que o JSON não tem.
    """
    achados: list[dict[str, Any]] = []
    for vista in sorted(set(celulas["vista"].astype(str))):
        da_vista = celulas[celulas["vista"].astype(str) == vista]
        for campo in CAMPOS_DO_EIXO_DE_COR:
            if campo not in da_vista.columns:
                msg = f"{NOME_HEATMAP} nao tem a coluna {campo}: o eixo de cor nao pode ser dito"
                raise SerieInconsistente(msg)
            valores = [escalar(valor, campo=campo) for valor in da_vista[campo]]
            presentes = [abs(float(v)) for v in valores if v is not None]
            extremo = escalar(max(presentes), campo=campo) if presentes else None
            achados.append(
                {
                    "vista": vista,
                    "campo": campo,
                    "extremo_simetrico": extremo,
                    "limite_inferior": None if extremo is None else escalar(-extremo, campo=campo),
                    "limite_superior": extremo,
                    "n_celulas_com_valor": len(presentes),
                    "n_celulas": int(len(da_vista)),
                }
            )
    return achados


def heatmap_regime_ativo(ctx: Contexto) -> dict[str, Any]:
    """T-02 — as células como plotadas, com `n`, erro-padrão e as 2 flags em cada uma."""
    celulas = ctx.ler_parquet(NOME_HEATMAP)
    conferir_flags_de_n(celulas, de_onde=NOME_HEATMAP)
    if ASSET_FORA_DA_FIGURA in set(celulas["asset_id"]):
        msg = (
            f"{ASSET_FORA_DA_FIGURA} apareceu em {NOME_HEATMAP}: a figura do Comite o exclui "
            "(Anti-SPEC 10.2.12) e a view nao pode reintroduzi-lo"
        )
        raise SerieInconsistente(msg)
    return {
        **ctx.envelope("heatmap_regime_ativo", fontes=(NOME_HEATMAP,)),
        "celulas": registros(celulas, CAMPOS_DA_CELULA),
        "eixos": primeiros_por(celulas, chave=CHAVE_DO_EIXO, campos=CAMPOS_DO_EIXO),
        "eixos_de_cor": eixos_de_cor(celulas),
        "ativos": primeiros_por(celulas, chave=CHAVE_DO_ATIVO, campos=CAMPOS_DO_ATIVO),
        "vistas": sorted(set(celulas["vista"].astype(str))),
        "regimes": list(dict.fromkeys(celulas["regime"].astype(str))),
        "grupos": list(dict.fromkeys(celulas["grupo"].astype(str))),
        "limiares_de_n": {
            "alerta_abaixo_de": 8,
            "supressao_abaixo_de": 5,
            "legenda": LEGENDA_DE_N,
        },
        "excluidos_da_figura": [
            {"asset_id": ASSET_FORA_DA_FIGURA, "motivo": MOTIVO_FORA_DA_FIGURA}
        ],
        "escala": ESCALA_DO_HEATMAP,
        "metrica_padrao": "excesso_cdi",
    }


# ─────────────────────────────────────────────────────────────────────────────
# T-03 · vizinhos
# ─────────────────────────────────────────────────────────────────────────────

CAMPOS_DO_VIZINHO: tuple[str, ...] = ("rank", "quarter_neighbor", "distancia")

DECLARACOES_DOS_VIZINHOS: tuple[str, ...] = (
    "Rodam 5 features de 6: termos_troca_yoy e 100% nula nos 83 trimestres e foi CORTADA.",
    "somente_passado elimina look-ahead de SELECAO e de PADRONIZACAO - NAO elimina safra "
    "(vintage unico: o look-ahead publicado e um PISO).",
    "O Jaccard de 2026Q3 contra si mesmo e 1,0 por CONSTRUCAO: citar isso como evidencia e vacuo.",
    "Nenhum ativo do ranking em T+1 passa de 2 erros-padrao: a ORDEM nao e distinguivel de ruido.",
    "4 dos 8 vizinhos de 2026Q3 nao tem quadrante V1 na revised (D-m) - a ausencia e rotulada.",
)


def exigir_prefixo_entre_ks(da_lente: pd.DataFrame) -> None:
    """O ranking de cada `k` é prefixo do de `K_COMPLETO`? Senão, truncar perderia vizinho.

    É a condição que autoriza emitir **um** ranking por referência em vez de três. Verificada a
    cada exportação, sobre o Parquet da própria tag — nunca assumida de uma rodada anterior.
    """
    for quarter_ref, grupo in da_lente.groupby("quarter_ref", sort=True):
        por_k = {
            int(k): list(fatia.sort_values("rank")["quarter_neighbor"].astype(str))
            for k, fatia in grupo.groupby("k_usado")
        }
        completo = por_k.get(K_COMPLETO)
        if completo is None:
            msg = f"{NOME_NEIGHBORS_V3}: {quarter_ref} nao tem k={K_COMPLETO} na lente canonica"
            raise SerieInconsistente(msg)
        for k, sequencia in sorted(por_k.items()):
            if sequencia != completo[: len(sequencia)]:
                msg = (
                    f"{NOME_NEIGHBORS_V3}: em {quarter_ref} o ranking de k={k} NAO e prefixo do de "
                    f"k={K_COMPLETO} ({sequencia} vs {completo[: len(sequencia)]}). "
                    "A view nao pode "
                    "emitir um ranking so."
                )
                raise SerieInconsistente(msg)


def _lente_declarada(vizinhos: pd.DataFrame) -> dict[str, Any]:
    linha = vizinhos.iloc[0]
    n_features = int(linha["n_features"])
    if n_features != len(FEATURES_USADAS):
        msg = (
            f"{NOME_NEIGHBORS_V3} declara n_features={n_features} e regimes_v3.FEATURES_USADAS tem "
            f"{len(FEATURES_USADAS)}: a view diria na tela um numero que a lente nao rodou"
        )
        raise SerieInconsistente(msg)
    return {
        "metrica": METRICA_MAHALANOBIS,
        "somente_passado": LENTE_CANONICA.somente_passado,
        "restrito_pos_2016": LENTE_CANONICA.restrito_pos_2016,
        "janela_padronizacao": escalar(linha["janela_padronizacao"], campo="janela_padronizacao"),
        "shrinkage": escalar(linha["shrinkage"], campo="shrinkage"),
        "n_features": n_features,
        "features_usadas": escalar(linha["features_usadas"], campo="features_usadas"),
    }


def vizinhos(ctx: Contexto) -> dict[str, Any]:
    """T-03 — a lente canônica, os 3 `k`, o quadrante por trimestre e o ranking em T+1."""
    todos = ctx.ler_parquet(NOME_NEIGHBORS_V3)
    regimes = ctx.ler_parquet(NOME_REGIMES_V1)
    relatorio = ctx.ler_relatorio(NOME_RELATORIO_V3)

    da_lente = todos.loc[
        (todos["metrica"] == METRICA_MAHALANOBIS)
        & (todos["somente_passado"] == LENTE_CANONICA.somente_passado)
        & (todos["restrito_pos_2016"] == LENTE_CANONICA.restrito_pos_2016)
        & (todos["k_usado"].isin(KS_EXPORTADOS))
    ]
    if da_lente.empty:
        msg = f"{NOME_NEIGHBORS_V3} nao tem a lente canonica {LENTE_CANONICA} nos k {KS_EXPORTADOS}"
        raise SerieInconsistente(msg)
    exigir_prefixo_entre_ks(da_lente)
    fatia = da_lente.loc[da_lente["k_usado"] == K_COMPLETO]

    rankings: list[dict[str, Any]] = []
    for quarter_ref, grupo in fatia.groupby("quarter_ref", sort=True):
        ordenado = grupo.sort_values("rank")
        rankings.append(
            {
                "quarter_ref": str(quarter_ref),
                "k_usado": K_COMPLETO,
                "n_vizinhos": int(ordenado["n_vizinhos"].iloc[0]),
                "vizinhos": registros(ordenado, CAMPOS_DO_VIZINHO),
            }
        )

    quadrante: dict[str, dict[str, Any]] = {}
    for _, linha in regimes.sort_values("quarter").iterrows():
        quadrante[str(linha["quarter"])] = {
            "regime_v1": escalar(linha["regime_v1"], campo="regime_v1"),
            "status_regime_v1": escalar(linha["status_regime_v1"], campo="status_regime_v1"),
        }

    t_mais_1: dict[str, str] = {}
    for _, linha in fatia.sort_values(["quarter_neighbor"]).iterrows():
        seguinte = escalar(linha["quarter_t_mais_1"], campo="quarter_t_mais_1")
        if seguinte is not None:
            t_mais_1[str(linha["quarter_neighbor"])] = str(seguinte)

    do_ranking = relatorio.get("ranking_ativos_t_mais_1") or {}
    ranking_t1: list[dict[str, Any]] = []
    for item in do_ranking.get("ativos") or ():
        n = int(item["n"])
        ranking_t1.append(
            {
                "asset_id": str(item["asset_id"]),
                "n_obs": n,
                "excesso_cdi": escalar(item.get("media"), campo="excesso_cdi"),
                "ret_medio": escalar(item.get("media"), campo="ret_medio"),
                "ret_mediana": escalar(item.get("mediana"), campo="ret_mediana"),
                "erro_padrao_media": escalar(item.get("erro_padrao"), campo="erro_padrao_media"),
                "hit_ratio_cdi": escalar(item.get("hit_ratio_cdi"), campo="hit_ratio_cdi"),
                "alerta_n_baixo": alerta_n_baixo(n),
                "conclusao_suprimida": conclusao_suprimida(n),
            }
        )
    return {
        **ctx.envelope(
            "vizinhos",
            fontes=(NOME_NEIGHBORS_V3, NOME_REGIMES_V1, NOME_RELATORIO_V3),
        ),
        "lente": _lente_declarada(fatia),
        "ks": list(KS_EXPORTADOS),
        "k_completo": K_COMPLETO,
        "regra_de_truncamento": REGRA_DE_TRUNCAMENTO,
        "referencias": sorted({str(valor) for valor in fatia["quarter_ref"]}),
        "rankings": rankings,
        "quadrante_por_quarter": quadrante,
        "t_mais_1_por_quarter": dict(sorted(t_mais_1.items())),
        "quarter_do_comite": QUARTER_DO_COMITE,
        "ranking_t_mais_1": ranking_t1,
        "declaracoes": list(DECLARACOES_DOS_VIZINHOS),
    }


# ─────────────────────────────────────────────────────────────────────────────
# T-04 · regimes_timeline
# ─────────────────────────────────────────────────────────────────────────────

CAMPOS_DO_PONTO: tuple[str, ...] = (
    "materializacao",
    "quarter",
    "rotulo_da_faixa",
    "n_obs_regime_v1",
    "trocou_vs_outra_materializacao",
    "tipo_de_troca",
)

#: **Sem `cor_hex`** (D-ai): o rótulo da faixa e a hachura são semântica do regime, que é do
#: pipeline; o hex da figura matplotlib é decisão de apresentação, que é de quem desenha.
CAMPOS_DO_ESTILO: tuple[str, ...] = ("regime_v1", "status_regime_v1", "hachura")
CAMPOS_DO_MERCADO: tuple[str, ...] = ("quarter_end", "ibov_nivel", "selic_meta_pct")


def regimes_timeline(ctx: Contexto) -> dict[str, Any]:
    """T-04 — 83 trimestres × 2 materializações, com IBOV (índice) e Selic (% a.a.)."""
    pontos = ctx.ler_parquet(NOME_TIMELINE)
    relatorio = ctx.ler_relatorio(NOME_RELATORIO_V1)
    divergencia = relatorio.get("divergencia_asof_vs_revised") or {}
    distribuicao = relatorio.get("distribuicao") or {}
    indeterminados = relatorio.get("indeterminados") or {}

    por_grupo = {
        str(nome): int(bloco["n"]) for nome, bloco in (distribuicao.get("por_grupo") or {}).items()
    }
    quarters_indeterminados = [
        str(valor)
        for valor in (indeterminados.get("quarters") or indeterminados.get("lista") or ())
    ]
    quarters = sorted({str(valor) for valor in pontos["quarter"]})
    return {
        **ctx.envelope("regimes_timeline", fontes=(NOME_TIMELINE, NOME_RELATORIO_V1)),
        "trimestres": registros(pontos, CAMPOS_DO_PONTO),
        "estilo_por_rotulo": {
            str(item.pop("rotulo_da_faixa")): item
            for item in primeiros_por(pontos, chave=("rotulo_da_faixa",), campos=CAMPOS_DO_ESTILO)
        },
        "mercado_por_quarter": {
            str(item.pop("quarter")): item
            for item in primeiros_por(pontos, chave=("quarter",), campos=CAMPOS_DO_MERCADO)
        },
        "materializacoes": sorted(set(pontos["materializacao"].astype(str))),
        "divergencia": {
            "n_divergencias": int(divergencia.get("trimestres_que_trocam") or 0),
            "n_comparaveis": int(divergencia.get("trimestres_comparaveis") or 0),
            "pct": escalar(divergencia.get("pct_que_trocam"), campo="pct"),
            "limiar_pct": escalar(divergencia.get("limiar_inoperante"), campo="limiar_pct"),
            "acima_do_limiar": (
                None
                if divergencia.get("modelo_operacional") is None
                else not bool(divergencia["modelo_operacional"])
            ),
            "quarters": [
                str(troca["quarter"])
                for troca in (divergencia.get("trocas") or ())
                if "quarter" in troca
            ],
        },
        "distribuicao": {
            "por_grupo": dict(sorted(por_grupo.items())),
            "n_indeterminados": int(indeterminados.get("n") or len(quarters_indeterminados)),
            "quarters_indeterminados": quarters_indeterminados,
            "desbalanceamento": escalar(
                distribuicao.get("desbalanceamento_relativo"), campo="desbalanceamento"
            ),
        },
        "n_trimestres": len(quarters),
        "janela": f"{quarters[0]}-{quarters[-1]}" if quarters else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# T-06 · internacional
# ─────────────────────────────────────────────────────────────────────────────

CAMPOS_INTERNACIONAIS: tuple[str, ...] = (
    "lente",
    "regime",
    "asset_id",
    "n_obs",
    "ret_medio",
    "ret_mediana",
    "excesso_cdi",
    "ret_real",
    "hit_ratio_cdi",
    "corr_ibov",
    "n_pares_ibov",
    "corr_imab",
    "n_pares_imab",
    "is_total_return",
    "alerta_n_baixo",
    "conclusao_suprimida",
)

MOTIVO_SEM_VARIANCIA_MINIMA = (
    "internacional_pesos.parquet esta marcado publicavel:false no MANIFEST.json (D-af, Anti-SPEC "
    "10.3.16/10.5 -> F-035): o exportador NAO emite a visao de variancia minima nem numero pontual "
    "de alocacao. A entrega de D6 e a FAIXA."
)


def internacional(ctx: Contexto) -> dict[str, Any]:
    """T-06 — o internacional em BRL, as 4 correlações com `n` e a faixa. **Sem** pesos."""
    celulas = ctx.ler_parquet(NOME_INTERNACIONAL)
    relatorio = ctx.ler_relatorio(NOME_RELATORIO_INTERNACIONAL)
    conferir_flags_de_n(celulas, de_onde=NOME_INTERNACIONAL)

    hedge = relatorio.get("hedge_cambial") or {}
    blocos = (hedge.get("stress_vs_nao_stress") or {}).get("blocos") or {}
    correlacoes = [
        {
            "bloco": str(nome),
            "corr": escalar(bloco.get("correlacao"), campo="corr"),
            "n_pares": None if bloco.get("n_pares") is None else int(bloco["n_pares"]),
        }
        for nome, bloco in sorted(blocos.items())
    ]
    faixa = relatorio.get("faixa_de_d6") or {}
    piso = faixa.get("piso_estrutural") or {}
    banda = faixa.get("banda_tatica") or {}
    stress = relatorio.get("regra_de_stress") or {}
    universo = relatorio.get("universo") or {}
    return {
        **ctx.envelope("internacional", fontes=(NOME_INTERNACIONAL, NOME_RELATORIO_INTERNACIONAL)),
        "celulas": registros(celulas, CAMPOS_INTERNACIONAIS),
        "lentes": list(dict.fromkeys(celulas["lente"].astype(str))),
        "assets": list(dict.fromkeys(celulas["asset_id"].astype(str))),
        "correlacoes": correlacoes,
        "faixa_d6": {
            "ativo_representativo": str(faixa.get("ativo_representativo") or ""),
            "piso_estrutural_min": escalar(piso.get("min"), campo="piso_estrutural_min"),
            "piso_estrutural_max": escalar(piso.get("max"), campo="piso_estrutural_max"),
            "banda_tatica_min": escalar(banda.get("min"), campo="banda_tatica_min"),
            "banda_tatica_max": escalar(banda.get("max"), campo="banda_tatica_max"),
            "cap_usado": escalar(faixa.get("cap_usado"), campo="cap_usado"),
            "forma": str(faixa.get("forma") or ""),
            "distincao_obrigatoria": str(faixa.get("distincao_obrigatoria") or ""),
            "decisao": str(faixa.get("decisao") or ""),
        },
        "regra_de_stress": {
            "n_stress": None if stress.get("n_stress") is None else int(stress["n_stress"]),
            "n_total": None if stress.get("n_trimestres") is None else int(stress["n_trimestres"]),
            "quarters_nao_avaliaveis": [
                str(valor) for valor in (stress.get("nao_avaliaveis_pelo_ramo_inclinacao") or ())
            ],
            "ramo_fora": str(stress.get("ramo_embi_fora") or ""),
            "cai_sobre": str(stress.get("cai_sobre") or ""),
        },
        "dez_piores_do_ibov": [
            {
                "quarter": str(item["quarter"]),
                "ret_ibov": escalar(item.get("ret_ibov"), campo="ret_ibov"),
                "ret_usdbrl": escalar(item.get("ret_usdbrl"), campo="ret_usdbrl"),
                "stress_flag": bool(item.get("stress_flag")),
            }
            for item in (hedge.get("dez_piores_trimestres_do_ibov") or ())
        ],
        "omitido_pelo_gate": [
            {"artefato": "internacional_pesos.parquet", "motivo": MOTIVO_SEM_VARIANCIA_MINIMA}
        ],
        "proxies_indisponiveis": sorted(
            str(nome) for nome in (universo.get("bloqueados_sem_fonte") or {})
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# T-07 · catalogo
# ─────────────────────────────────────────────────────────────────────────────

CAMPOS_DA_SERIE: tuple[str, ...] = (
    "series_id",
    "nome",
    "item_email",
    "fonte",
    "freq",
    "unit",
    "status",
    "confianca",
    "lag_divulgacao_dias",
    "data_inicio",
    "data_inicio_observada",
    "data_fim",
    "data_fim_observada",
    "presente_no_processed",
    "cobre_1t2006",
    "n_obs",
    "pct_nulos",
    "fonte_url",
)

CAMPOS_DO_ARTEFATO: tuple[str, ...] = (
    "arquivo",
    "linhas",
    "colunas",
    "bytes",
    "sha256",
    "date_min",
    "date_max",
    "pct_nulos",
    "determinista",
)


def catalogo(ctx: Contexto, *, reducoes: list[dict[str, Any]]) -> dict[str, Any]:
    """T-07 — o catálogo com cobertura declarada × observada, as 10 limitações e as 12 decisões."""
    series = ctx.ler_parquet(NOME_SERIES_CATALOG)
    entradas = artefatos_do_manifesto(ctx.manifesto)
    publicaveis = [
        {campo: escalar(entrada.get(campo), campo=campo) for campo in CAMPOS_DO_ARTEFATO}
        for nome, entrada in sorted(entradas.items())
        if entrada.get("publicavel") is not False
    ]
    nao_publicaveis = [
        {
            "artefato": str(nome),
            "motivo": str(entrada.get("motivo_nao_publicavel") or "publicavel:false no MANIFEST"),
        }
        for nome, entrada in sorted(entradas.items())
        if entrada.get("publicavel") is False
    ]
    limitacoes = [
        {"numero": numero, "texto": texto}
        for numero, texto in enumerate(limitacoes_do_notebook(raiz=ctx.raiz), start=1)
    ]
    decisoes = [dict(item) for item in decisoes_a_ratificar(raiz=ctx.raiz)]
    presentes = int(series["presente_no_processed"].fillna(False).astype(bool).sum())
    cobrem = int(series["cobre_1t2006"].fillna(False).astype(bool).sum())
    return {
        **ctx.envelope("catalogo", fontes=(NOME_SERIES_CATALOG, "MANIFEST.json")),
        "series": registros(series, CAMPOS_DA_SERIE),
        "cobertura": {
            "n_series": int(len(series)),
            "n_presentes": presentes,
            "n_cobrem_1t2006": cobrem,
        },
        "artefatos": publicaveis,
        "artefatos_nao_publicaveis": nao_publicaveis,
        "limitacoes": limitacoes,
        "decisoes_pendentes": decisoes,
        "adrs": status_dos_adrs(raiz=ctx.raiz),
        "reducoes": [dict(item) for item in reducoes],
    }


# ─────────────────────────────────────────────────────────────────────────────
# O índice de construtores
# ─────────────────────────────────────────────────────────────────────────────


def construir_todas(ctx: Contexto, *, reducoes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """As 6 views, por nome de arquivo (sem `.json`), na ordem de `web_views.VIEWS`."""
    return {
        "ranking_atual": ranking_atual(ctx),
        "heatmap_regime_ativo": heatmap_regime_ativo(ctx),
        "vizinhos": vizinhos(ctx),
        "regimes_timeline": regimes_timeline(ctx),
        "internacional": internacional(ctx),
        "catalogo": catalogo(ctx, reducoes=reducoes),
    }


__all__ = [
    "ARTEFATOS_LIDOS",
    "ARTEFATOS_PROIBIDOS",
    "LENTE_CANONICA",
    "METRICA_MAHALANOBIS",
    "Contexto",
    "construir_todas",
    "status_dos_adrs",
]
