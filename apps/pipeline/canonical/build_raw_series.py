"""F-013 — materializa `raw_series` e `series_catalog` em `data/canonical/`. **Classe C.**

O que este módulo faz, e **só** isto:

1. **Descobre** os Parquet de série em `data/processed/*/` (`data/` nunca é lido por glob na mão em
   outro lugar), deixando de fora as tabelas que não entram no canônico —
   `calendario/dias_uteis_anbima.parquet` (não é série de valores),
   `tesouro-direto/td_painel.parquet` e as **5** fatias de `focus/` (painéis de `series_id`
   compostos que não são entradas do catálogo; ver `TABELAS_FORA_DO_RAW_SERIES`, cada uma com o
   motivo no próprio dado).
2. **Valida a entrada** com `ProcessedSeriesSchema`, arquivo por arquivo: Parquet que não é
   `processed_series` derruba o build em vez de entrar no canônico (CA-057, CA-075).
3. **Guarda procedência e fonte única no concatenado**, *antes* de qualquer dedup: procedência
   resolvível no catálogo (CA-055/CA-120), uma fonte por série (CA-077) e nenhuma série
   `a_confirmar` no caminho crítico (CA-054). A ordem é parte da garantia — dedup primeiro
   apagaria a linha que prova a mistura.
4. **Consolida** numa tabela longa: dedup pela PK `(series_id, date, vintage)` só quando a linha é
   idêntica nas **8 colunas** — e **levanta** se divergir em qualquer uma, em vez de escolher uma
   —, ordenação determinística e ordem de coluna do schema. Em seguida valida a frequência
   **nativa** declarada (CA-058), que é a invariante que precisa do dedup já feito.
5. **Materializa o catálogo** com o observado (`SeriesCatalogMaterializedSchema`, CA-053).
6. **Grava** `raw_series.parquet` + `series_catalog.parquet` (portão `RawSeriesSchema` /
   `SeriesCatalogMaterializedSchema` **antes** da escrita), o `relatorio_build.json` e o
   `ldc.duckdb` derivado (ADR-006 §(a).2).

O que este módulo **não** faz: nenhuma agregação, nenhuma reamostragem, nenhuma interpolação,
nenhum `ffill`, nenhum valor novo. `raw_series` tem exatamente os mesmos números que
`data/processed/` — é o que permite ao QA conferir linha a linha contra a origem (Anti-SPEC
§10.1.1, §10.1.2, §10.4.28).

**Sem rede, sempre.** `--offline` existe para simetria com os extratores e é o único
comportamento: a fonte deste build é o disco.

**Idempotente por construção.** Dois builds sobre o mesmo `data/processed/` produzem Parquet e
relatório byte-idênticos, porque nada aqui depende do relógio: `collected_at`/`vintage` vêm do
manifesto do bruto (D-b) e o relatório não carrega hora de geração — carrega `versao_build`
(`sha256` do conjunto `MODULOS_DO_BUILD`: este arquivo + os dois schemas + o catálogo como dado),
`catalogo_sha256` e o `collected_at` máximo do dado. O `.duckdb` é a exceção declarada:
é binário derivado, recriado a cada build, e **não** entra na conferência por hash.

Referências: SPEC RF-019/RF-020/RF-026/RF-047 (CA-053..058, CA-075..077, CA-120) ·
ADR-006 §(a) · `docs/contracts/CONTRACTS.md §1, §2` · `docs/wiki/modules/canonical.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from apps.pipeline.common.errors import ErroDeExtracao, FonteIndisponivel, SerieInconsistente
from apps.pipeline.common.io_layers import (
    Camada,
    caminho_camada,
    caminho_canonical,
    garantir_diretorio,
    raiz_repo,
    sha256_de,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from packages.shared.schemas import (
    LIMIAR_COBERTURA_2006,
    ProcessedSeriesSchema,
    RawSeriesSchema,
    SeriesCatalogMaterializedSchema,
    StatusSerie,
    load_catalog,
)

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Iterable, Sequence

    from packages.shared.schemas import SeriesCatalogEntry

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Nomes e constantes do contrato
# ─────────────────────────────────────────────────────────────────────────────

NOME_RAW_SERIES = "raw_series.parquet"
NOME_CATALOGO = "series_catalog.parquet"
NOME_RELATORIO = "relatorio_build.json"
NOME_DUCKDB = "ldc.duckdb"

#: As 8 colunas de `RawSeriesSchema`, **nesta ordem** — a ordem é parte do artefato.
COLUNAS_RAW_SERIES: tuple[str, ...] = (
    "series_id",
    "date",
    "value",
    "source",
    "freq",
    "vintage",
    "unit",
    "collected_at",
)

#: PK lógica de `raw_series` (CONTRACTS.md §1). Também a chave de ordenação.
PK_RAW_SERIES: tuple[str, ...] = ("series_id", "date", "vintage")

#: Módulo que carrega o catálogo **como dado** — hasheado sozinho em `catalogo_sha256`.
MODULO_CATALOGO_DADOS = "packages.shared.schemas.series_catalog_data"

#: Os módulos que determinam o conteúdo dos artefatos, **nesta ordem** — base de `versao_build`.
#: Não é "o pipeline inteiro": é este builder + os dois schemas que ele usa como portão + o dado
#: do catálogo. Mudar qualquer um muda o Parquet, então tem de mudar a versão (P1-1, Onda 2).
MODULOS_DO_BUILD: tuple[str, ...] = (
    "apps.pipeline.canonical.build_raw_series",
    "packages.shared.schemas.raw_series",
    "packages.shared.schemas.series_catalog",
    MODULO_CATALOGO_DADOS,
)

#: Tabelas de `data/processed/` que **não** são `processed_series` e por quê.
#: A chave é o sufixo do caminho POSIX relativo a `data/processed/`.
#: Motivo das 5 tabelas do Focus (F-010), por EntitySet. É o mesmo caso de `td_painel.parquet`:
#: o catálogo registra a **fonte** (o EntitySet), e os `series_id` gravados são compostos.
_MOTIVO_FOCUS = (
    "Fatia do painel do Focus (F-010) com {n} series_id compostos "
    "FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE> que NAO sao entradas do series_catalog: o catalogo "
    "registra o EntitySet ({es}) como fonte, e a serie canonica derivada e de F-015, que consome "
    "o Focus direto de data/processed/focus/ (mesmo ProcessedSeriesSchema). Admitir os 197 aqui "
    "violaria CA-055/CA-120 — mesma situacao de td_painel.parquet. Ver D-k."
)

TABELAS_FORA_DO_RAW_SERIES: dict[str, str] = {
    "calendario/dias_uteis_anbima.parquet": (
        "CalendarioDiasUteisSchema (4 colunas): grade de datas com dois atributos, não série de "
        "valores — não tem value/unit/freq/vintage/collected_at. Consumida por F-014/F-017 "
        "direto de data/processed/ (CONTRACTS.md §7, D-f)."
    ),
    "tesouro-direto/td_painel.parquet": (
        "Painel com 750 series_id compostos (TD_<SIGLA>_<AAAAMMDD>_<METRICA>) que NÃO são "
        "entradas do series_catalog: o catálogo tem uma entrada só para a fonte "
        "(TESOURO_TD_PRECOTAXA) e as séries canônicas dela são os vértices interpolados "
        "(CURVA_REAL_1A/5A, CURVA_NOMINAL_1A/5A, INCLINACAO_*, BREAKEVEN_5A), produzidos por "
        "F-016. Admitir os 750 aqui violaria CA-055/CA-120 — toda linha do canônico tem de "
        "resolver para uma URL do catálogo."
    ),
    "focus/FOCUS_ANUAIS.parquet": _MOTIVO_FOCUS.format(es="FOCUS_ANUAIS", n=8),
    "focus/FOCUS_MENSAIS.parquet": _MOTIVO_FOCUS.format(es="FOCUS_MENSAIS", n=2),
    "focus/FOCUS_TRIMESTRAIS.parquet": _MOTIVO_FOCUS.format(es="FOCUS_TRIMESTRAIS", n=3),
    "focus/FOCUS_SELIC.parquet": _MOTIVO_FOCUS.format(es="FOCUS_SELIC", n=182),
    "focus/FOCUS_INFLACAO_12M.parquet": _MOTIVO_FOCUS.format(es="FOCUS_INFLACAO_12M", n=2),
}

#: Colunas acrescentadas ao catálogo materializado (`SeriesCatalogMaterializedSchema`).
COLUNAS_OBSERVADAS: tuple[str, ...] = (
    "presente_no_processed",
    "data_inicio_observada",
    "data_fim_observada",
    "n_obs",
    "pct_nulos",
    "cobre_1t2006",
)

_FIM_DE_PERIODO: dict[str, Any] = {
    "M": pd.offsets.MonthEnd(0),
    "Q": pd.offsets.QuarterEnd(0),
    "A": pd.offsets.YearEnd(0),
}
"""D-a: `date` de série não diária é o **fim de período civil** (`DECISIONS_LOG §2.1`)."""


# ─────────────────────────────────────────────────────────────────────────────
# Exceções próprias da camada
# ─────────────────────────────────────────────────────────────────────────────


class ErroCanonico(ErroDeExtracao):
    """Base das falhas da camada canônica — herda de `ErroDeExtracao` para o CLI tratar uma só."""


class ProcedenciaNaoResolvida(ErroCanonico):
    """Linha de `raw_series` cujo `series_id`/`source` não resolve no `series_catalog` (CA-055)."""


class FrequenciaNaoNativa(ErroCanonico):
    """A série foi gravada em frequência diferente da nativa declarada no catálogo (CA-058).

    É o erro que a Anti-SPEC §10.4.28 chama de irreversível: IPCA mensal reamostrado como
    trimestral, ou série trimestral espalhada em datas mensais, não tem como ser desfeito depois
    porque a informação de qual ponto era real se perde.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Descoberta dos insumos
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TabelaExcluida:
    """Parquet de `data/processed/` deixado fora de `raw_series`, com o motivo registrado.

    Vai para o `relatorio_build.json`: tabela omitida em silêncio é indistinguível de tabela
    esquecida, e esta camada tem de ser auditável por quem não escreveu o código.
    """

    arquivo: str
    motivo: str

    def como_dict(self) -> dict[str, str]:
        """Forma serializável para o relatório."""
        return {"arquivo": self.arquivo, "motivo": self.motivo}


def descobrir_parquets_de_serie(
    *, raiz: Path | None = None, raiz_processed: Path | None = None
) -> tuple[list[Path], list[TabelaExcluida]]:
    """`(parquets de série, tabelas excluídas)` em `data/processed/`, em ordem determinística.

    `raiz_processed` existe para o teste apontar para um `tmp_path`; em produção quem manda é
    `caminho_camada(Camada.PROCESSED)`, ancorado na raiz do repositório (nunca no `cwd`).
    """
    base = raiz_processed or caminho_camada(Camada.PROCESSED, raiz=raiz)
    if not base.is_dir():
        msg = (
            f"{base} não existe. Rode os extratores antes: "
            f"`python -m apps.pipeline.extract.<fonte> --offline`"
        )
        raise FonteIndisponivel(f"BLOQUEADO — FONTE INDISPONÍVEL: {msg}")

    alvos: list[Path] = []
    excluidas: list[TabelaExcluida] = []
    for caminho in sorted(base.glob("*/*.parquet")):
        relativo = caminho.relative_to(base).as_posix()
        motivo = TABELAS_FORA_DO_RAW_SERIES.get(relativo)
        if motivo is None:
            alvos.append(caminho)
        else:
            excluidas.append(TabelaExcluida(arquivo=relativo, motivo=motivo))
    return alvos, excluidas


# ─────────────────────────────────────────────────────────────────────────────
# Carga e consolidação
# ─────────────────────────────────────────────────────────────────────────────


def carregar_processed(alvos: Sequence[Path]) -> pd.DataFrame:
    """Lê e **valida** cada Parquet com `ProcessedSeriesSchema`, e concatena.

    A validação é por arquivo, não no final, para que a mensagem de erro nomeie o arquivo
    culpado — é o portão `data/processed/` → `data/canonical/` do `CONTRACTS.md §0`.
    """
    if not alvos:
        msg = "nenhum Parquet de série em data/processed/ — rode os extratores primeiro"
        raise FonteIndisponivel(f"BLOQUEADO — FONTE INDISPONÍVEL: {msg}")

    pedacos: list[pd.DataFrame] = []
    for caminho in alvos:
        quadro = pd.read_parquet(caminho)
        try:
            validado = ProcessedSeriesSchema.validate(quadro, lazy=True)
        except Exception as erro:  # pandera: SchemaError/SchemaErrors
            msg = f"{caminho.name} não é processed_series válido: {erro}"
            raise SerieInconsistente(msg) from erro
        pedacos.append(validado)
    return pd.concat(pedacos, ignore_index=True)


def consolidar(quadro: pd.DataFrame) -> pd.DataFrame:
    """Tabela longa final: dedup pela PK, ordenação determinística, ordem de coluna do schema.

    Duplicata **idêntica nas 8 colunas** é removida (dois extratores podem reexportar o mesmo
    ponto); duplicata com qualquer coluna divergente levanta `SerieInconsistente`, porque escolher
    uma das duas em silêncio é o erro que CA-068 e o Validation Mode §7 mandam não cometer.

    A divergência é medida nas **8 colunas**, não só em `value` (P1-3 do QA da Onda 2): comparar
    apenas o valor fazia a mesma PK com `source` diferente colapsar em silêncio, cegando
    `validar_sem_mistura_de_fontes` (CA-077) — é a "substituição de fonte sem rastro" da Anti-SPEC
    §10.3.19. `unit`, `freq` e `collected_at` entram pela mesma razão: mesma data, mesmo número,
    procedência ou escala outra é conflito, não repetição.
    """
    faltando = [c for c in COLUNAS_RAW_SERIES if c not in quadro.columns]
    if faltando:
        msg = f"colunas ausentes para raw_series: {faltando}"
        raise SerieInconsistente(msg)

    saida = quadro.loc[:, list(COLUNAS_RAW_SERIES)].copy()

    antes = len(saida)
    duplicadas = saida.duplicated(subset=list(PK_RAW_SERIES), keep=False)
    if bool(duplicadas.any()):
        candidatas = saida.loc[duplicadas]
        # `drop_duplicates` trata nulo == nulo, então `value=100` vs. `value=NaN` continua sendo
        # duas linhas distintas — e portanto conflito, não repetição.
        distintas = candidatas.drop_duplicates(subset=list(COLUNAS_RAW_SERIES), keep="first")
        divergentes = distintas.groupby(list(PK_RAW_SERIES), dropna=False).size()
        conflito = divergentes[divergentes > 1]
        if len(conflito) > 0:
            amostra = [
                f"{a} {pd.Timestamp(b).date()} vintage={pd.Timestamp(c).date()}"
                for a, b, c in list(conflito.index)[:5]
            ]
            msg = (
                f"{len(conflito)} PK(s) (series_id, date, vintage) com linha divergente em "
                f"value/source/unit/freq/collected_at — amostra: {amostra}. Dedup silencioso aqui "
                f"esconderia revisão de fonte, troca de procedência ou bug de extrator; resolva "
                f"na camada processada."
            )
            raise SerieInconsistente(msg)

    saida = saida.drop_duplicates(subset=list(PK_RAW_SERIES), keep="first")
    removidas = antes - len(saida)
    if removidas:
        # Contagem real de linhas removidas: o `// 2` anterior presumia 2 cópias por PK e
        # subnotificava 3 cópias ou mais (P2-1 do QA da Onda 2).
        _log.info("dedup: %d linha(s) idêntica(s) na PK removida(s)", removidas)
    saida = saida.sort_values(
        by=list(PK_RAW_SERIES), kind="mergesort", na_position="last"
    ).reset_index(drop=True)
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# As quatro invariantes da camada
# ─────────────────────────────────────────────────────────────────────────────


def validar_procedencia(quadro: pd.DataFrame, catalogo: Iterable[SeriesCatalogEntry]) -> None:
    """CA-055 / CA-120: todo `series_id` resolve no catálogo, com `source` e `unit` coerentes.

    Sem isto, "de onde veio este número?" só tem resposta no código — e o CA exige que a resposta
    esteja **no dado**, até a `fonte_url` do catálogo.
    """
    por_id = {e.series_id: e for e in catalogo}
    presentes = set(quadro["series_id"].unique())

    orfas = sorted(presentes - por_id.keys())
    if orfas:
        msg = (
            f"{len(orfas)} series_id sem entrada no series_catalog: {orfas[:10]} — "
            f"CA-055 exige que toda linha do canônico resolva para uma URL de fonte"
        )
        raise ProcedenciaNaoResolvida(msg)

    problemas: list[str] = []
    for series_id, grupo in quadro.groupby("series_id", sort=True):
        entrada = por_id[str(series_id)]
        fontes = sorted({str(v) for v in grupo["source"].unique()})
        if fontes != [entrada.fonte.value]:
            problemas.append(f"{series_id}: source={fontes} != catálogo {entrada.fonte.value}")
        unidades = sorted({str(v) for v in grupo["unit"].unique()})
        if unidades != [entrada.unit.value]:
            problemas.append(f"{series_id}: unit={unidades} != catálogo {entrada.unit.value}")
        if entrada.status is StatusSerie.A_CONFIRMAR:
            problemas.append(
                f"{series_id}: status=a_confirmar no catálogo não pode entrar no canônico (CA-054)"
            )
    if problemas:
        msg = "procedência incoerente com o series_catalog:\n  - " + "\n  - ".join(problemas[:15])
        raise ProcedenciaNaoResolvida(msg)


def validar_frequencia_nativa(quadro: pd.DataFrame, catalogo: Iterable[SeriesCatalogEntry]) -> None:
    """CA-058 / Anti-SPEC §10.4.28: a frequência gravada é a **nativa** declarada no catálogo.

    Três coisas são verificadas por série:

    1. uma única `freq` na série (série que muda de frequência no meio é erro de extrator);
    2. a `freq` é a do catálogo — é isto que pega "IPCA mensal reamostrado como trimestral";
    3. para `M`/`Q`/`A`, as datas são o **fim de período civil** (D-a) e há **no máximo uma**
       observação por período — é isto que pega o inverso, uma série trimestral espalhada em
       datas mensais.
    """
    por_id = {e.series_id: e for e in catalogo}
    problemas: list[str] = []

    for series_id, grupo in quadro.groupby("series_id", sort=True):
        sid = str(series_id)
        freqs = sorted({str(v) for v in grupo["freq"].unique()})
        if len(freqs) != 1:
            problemas.append(f"{sid}: {len(freqs)} freq na mesma série ({freqs})")
            continue
        freq = freqs[0]
        esperada = por_id[sid].freq.value if sid in por_id else None
        if esperada is not None and freq != esperada:
            problemas.append(f"{sid}: freq={freq} != nativa declarada {esperada}")
            continue
        offset = _FIM_DE_PERIODO.get(freq)
        if offset is None:
            continue
        datas = pd.DatetimeIndex(grupo["date"])
        fora = datas[datas != datas + offset]
        if len(fora) > 0:
            amostra = [d.date().isoformat() for d in fora[:3]]
            problemas.append(f"{sid}: freq={freq} com date fora do fim de período civil {amostra}")
        periodos = datas.to_period(freq)
        if periodos.duplicated().any():
            repetidos = sorted({str(p) for p in periodos[periodos.duplicated()]})[:3]
            problemas.append(
                f"{sid}: freq={freq} com mais de uma observação no período {repetidos}"
            )

    if problemas:
        msg = "frequência não nativa:\n  - " + "\n  - ".join(problemas[:15])
        raise FrequenciaNaoNativa(msg)


def validar_sem_mistura_de_fontes(quadro: pd.DataFrame) -> None:
    """CA-077 / Anti-SPEC §10.1.2: a mesma série não pode vir de duas fontes sem distinção.

    `source` é a coluna de origem: se uma série real ganha linhas de outra procedência (um
    `MANUAL`/sintético enxertado num histórico `BCB_SGS`, por exemplo), o `series_id` passa a ter
    duas fontes — e é isso que falha aqui. Misturar é permitido **só** com `series_id` próprio,
    que é como as séries derivadas (`SP500_BRL`, `ACWI_BRL`, `fonte=DERIVADO`) existem (D-d).
    """
    por_serie = quadro.groupby("series_id", sort=True)["source"].nunique()
    misturadas = sorted(str(s) for s in por_serie[por_serie > 1].index)
    if misturadas:
        msg = (
            f"{len(misturadas)} série(s) com mais de um `source` na mesma série: "
            f"{misturadas[:10]} — dado de procedências diferentes exige series_id próprio "
            f"(CA-077)"
        )
        raise SerieInconsistente(msg)


def exigir_series(
    quadro: pd.DataFrame, catalogo: Iterable[SeriesCatalogEntry], exigidas: Iterable[str]
) -> None:
    """CA-076: série exigida que não chegou → `BLOQUEADO — FONTE INDISPONÍVEL`, nunca preenchida.

    O build **não** chama isto com o pacote mínimo inteiro (F-010/F-011/F-012/F-016 ainda não
    rodaram, e o relatório já lista o que falta). A função é o portão que as features a jusante
    usam para fechar o trimestre: quem precisa de uma série declara, e a ausência para o pipeline
    em vez de virar lacuna preenchida.
    """
    por_id = {e.series_id: e for e in catalogo}
    presentes = set(quadro["series_id"].unique())
    faltando = [s for s in sorted(set(exigidas)) if s not in presentes]
    if not faltando:
        return
    detalhe = ", ".join(
        f"{s} ({por_id[s].fonte.value}, item {por_id[s].item_email})" if s in por_id else f"{s} (?)"
        for s in faltando
    )
    msg = (
        f"BLOQUEADO — FONTE INDISPONÍVEL: {len(faltando)} série(s) exigida(s) ausente(s) de "
        f"data/processed/: {detalhe}. Nenhuma estimativa, interpolação ou proxy silencioso "
        f"(Anti-SPEC §10.1.1)."
    )
    raise FonteIndisponivel(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo materializado
# ─────────────────────────────────────────────────────────────────────────────


def _observado_por_serie(quadro: pd.DataFrame) -> pd.DataFrame:
    """`(n_obs, n_nulos, pct_nulos, data_inicio_observada, data_fim_observada)` por `series_id`."""
    agregado = quadro.groupby("series_id", sort=True).agg(
        n_obs=("value", "size"),
        n_nulos=("value", lambda s: int(s.isna().sum())),
        data_inicio_observada=("date", "min"),
        data_fim_observada=("date", "max"),
    )
    agregado["pct_nulos"] = (agregado["n_nulos"] / agregado["n_obs"] * 100.0).round(6)
    return agregado


def materializar_catalogo(
    catalogo: Iterable[SeriesCatalogEntry], quadro: pd.DataFrame
) -> pd.DataFrame:
    """As 134 entradas do catálogo + as 6 colunas do observado, validadas pelo schema novo.

    O catálogo **declarado** nunca é sobrescrito pelo medido: as duas visões ficam lado a lado
    (`data_inicio` vs. `data_inicio_observada`), porque a divergência entre elas é informação —
    é como se vê que o IFIX começa em 2010-12-30 e não em 2006, e que 40 séries `ok` do pacote
    mínimo ainda não têm extrator rodado.
    """
    entradas = list(catalogo)
    if not entradas:
        msg = "catálogo vazio"
        raise SerieInconsistente(msg)

    observado = _observado_por_serie(quadro)
    limiar = pd.Timestamp(LIMIAR_COBERTURA_2006)

    linhas: list[dict[str, Any]] = []
    for entrada in entradas:
        presente = entrada.series_id in observado.index
        medido = observado.loc[entrada.series_id] if presente else None
        inicio = pd.Timestamp(medido["data_inicio_observada"]) if presente else pd.NaT
        fim = pd.Timestamp(medido["data_fim_observada"]) if presente else pd.NaT
        linhas.append(
            {
                "series_id": entrada.series_id,
                "nome": entrada.nome,
                "item_email": entrada.item_email,
                "fonte": entrada.fonte.value,
                "identificador": entrada.identificador,
                "fonte_url": entrada.fonte_url,
                "freq": entrada.freq.value,
                "data_inicio": pd.Timestamp(entrada.data_inicio) if entrada.data_inicio else pd.NaT,
                "data_fim": pd.Timestamp(entrada.data_fim) if entrada.data_fim else pd.NaT,
                "unit": entrada.unit.value,
                "transformacao_padrao": entrada.transformacao_padrao.value,
                "lag_divulgacao_dias": entrada.lag_divulgacao_dias,
                "confianca": entrada.confianca.value,
                "status": entrada.status.value,
                "is_total_return": entrada.is_total_return,
                # `calendario` ("dias_uteis" | "corrido" | nulo) chega ao materializado desde
                # 2026-10-11 (P1-2 do QA da Onda 2): sem ele, F-014 não sabe que 28,6% dos pontos
                # de `BCB_SGS_432` caem em fim de semana.
                "calendario": entrada.calendario,
                "janela_rolante": entrada.janela_rolante,
                "fonte_instavel": entrada.fonte_instavel,
                "licenca_restrita": entrada.licenca_restrita,
                "obs": entrada.obs,
                "presente_no_processed": presente,
                "data_inicio_observada": inicio,
                "data_fim_observada": fim,
                "n_obs": int(medido["n_obs"]) if presente else 0,
                "pct_nulos": float(medido["pct_nulos"]) if presente else 0.0,
                "cobre_1t2006": bool(presente and inicio <= limiar),
            }
        )

    tabela = pd.DataFrame(linhas)
    # `is_total_return` é bool|None: `object` com None não passa por `nullable=True` de bool, e
    # `BooleanDtype` é o tipo que representa "booleano com nulo" sem virar 0/1.
    tabela["is_total_return"] = tabela["is_total_return"].astype("boolean")
    return tabela.sort_values("series_id", kind="mergesort").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Escrita
# ─────────────────────────────────────────────────────────────────────────────


def _gravar_parquet_validado(
    quadro: pd.DataFrame, *, nome: str, schema: Any, raiz: Path | None
) -> tuple[Path, str, int]:
    """Valida com pandera e **só então** grava; devolve `(caminho, sha256, bytes)`.

    A ordem importa: é o portão de RF-026/CA-075 — DataFrame sem coluna de origem é rejeitado
    *antes* da escrita, e nada fica em disco.
    """
    validado = schema.validate(quadro, lazy=True)
    destino = caminho_canonical(nome, raiz=raiz)
    garantir_diretorio(destino.parent)
    validado.to_parquet(destino, index=False)
    corpo = destino.read_bytes()
    digest = sha256_de(corpo)
    _log.info("gravado %s (%d linhas, sha256=%s…)", destino.name, len(validado), digest[:12])
    return destino, digest, len(corpo)


def caminhos_dos_componentes(modulos: Sequence[str] | None = None) -> tuple[Path, ...]:
    """Os arquivos de `MODULOS_DO_BUILD` em disco, na ordem declarada."""
    caminhos: list[Path] = []
    for nome in modulos or MODULOS_DO_BUILD:
        arquivo = import_module(nome).__file__
        if arquivo is None:  # pragma: no cover - módulo sem arquivo não existe aqui
            msg = f"{nome} não tem arquivo em disco para hashear"
            raise SerieInconsistente(msg)
        caminhos.append(Path(arquivo))
    return tuple(caminhos)


def versao_build(componentes: Sequence[Path] | None = None) -> str:
    """`sha256` do **conjunto** `MODULOS_DO_BUILD` — o `fonte_versao` da camada (RF-048/CA-121).

    Hash de arquivos, não do processo: é o que faz "o relatório mudou porque o código mudou" ser
    distinguível de "o relatório mudou porque o dado mudou".

    Era o hash **só deste arquivo** até 2026-10-11, e isso tinha custado um artefato publicado
    obsoleto com `versao_build` idêntico (P1-1 do QA da Onda 2): editar `series_catalog_data.py`
    muda o `series_catalog.parquet` sem tocar o builder. Agora o nome de cada componente entra no
    corpo hasheado antes do conteúdo, então o hash não depende do caminho absoluto (o teste pode
    hashear cópias em `tmp_path`), mas qualquer renomeação conta como mudança.
    """
    caminhos = tuple(componentes) if componentes is not None else caminhos_dos_componentes()
    corpo = b"".join(c.name.encode("utf-8") + b"\n" + c.read_bytes() for c in caminhos)
    return sha256_de(corpo)


def catalogo_sha256(caminho: Path | None = None) -> str:
    """`sha256` de `series_catalog_data.py` — o **dado** do catálogo, isolado do resto da versão.

    Vai ao relatório ao lado de `versao_build` para que "o catálogo mudou" seja diagnosticável sem
    recompor o conjunto: artefato em disco com `catalogo_sha256` diferente do código commitado é
    materializado obsoleto, não divergência de dado.
    """
    alvo = caminho or caminhos_dos_componentes((MODULO_CATALOGO_DADOS,))[0]
    return sha256_de(alvo.read_bytes())


def construir_duckdb(
    *, caminho_raw: Path, caminho_catalogo: Path, raiz: Path | None = None
) -> Path:
    """Recria `data/canonical/ldc.duckdb` com views sobre os Parquet (ADR-006 §(a).2).

    **Derivado e descartável**: apagado e refeito a cada build, nunca fonte de verdade, fora do
    git. Views (não tabelas) para que o banco não guarde uma segunda cópia do dado que pode
    divergir do Parquet.
    """
    import duckdb

    destino = caminho_canonical(NOME_DUCKDB, raiz=raiz)
    garantir_diretorio(destino.parent)
    destino.unlink(missing_ok=True)
    Path(str(destino) + ".wal").unlink(missing_ok=True)

    def _literal(caminho: Path) -> str:
        return "'" + str(caminho.resolve()).replace("'", "''") + "'"

    conexao = duckdb.connect(str(destino))
    try:
        for view, arquivo in (
            ("raw_series", caminho_raw),
            ("series_catalog", caminho_catalogo),
        ):
            conexao.execute(
                f"CREATE OR REPLACE VIEW {view} AS "  # noqa: S608 - nome de view é constante
                f"SELECT * FROM read_parquet({_literal(arquivo)})"
            )
        linhas = conexao.execute("SELECT count(*) FROM raw_series").fetchone()
        _log.info("%s: view raw_series com %s linha(s)", destino.name, linhas[0] if linhas else "?")
    finally:
        conexao.close()
    return destino


# ─────────────────────────────────────────────────────────────────────────────
# Relatório e orquestração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoBuild:
    """O que o build produziu — o CLI imprime, o teste inspeciona, o QA confere."""

    raw_series: pd.DataFrame
    catalogo: pd.DataFrame
    relatorio: dict[str, Any]
    caminho_raw_series: Path
    caminho_catalogo: Path
    caminho_relatorio: Path
    caminho_duckdb: Path | None = None
    excluidas: tuple[TabelaExcluida, ...] = field(default=())


def _iso(valor: Any) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    return pd.Timestamp(valor).date().isoformat()


def _iso_hora(valor: Any) -> str | None:
    """ISO **com hora**: `collected_at` carrega hora real, e truncá-la a data mentia sobre a safra.

    P2-7 do QA da Onda 2 — `date`/`vintage` continuam em `_iso` porque são data pura (D-b).
    """
    if valor is None or pd.isna(valor):
        return None
    return pd.Timestamp(valor).isoformat()


def _resumo_por_serie(quadro: pd.DataFrame) -> list[dict[str, Any]]:
    """Uma linha por série no relatório: contagem, janela, nulos e extremos de `value`."""
    resumo: list[dict[str, Any]] = []
    for series_id, grupo in quadro.groupby("series_id", sort=True):
        valores = grupo["value"]
        n = int(len(grupo))
        nulos = int(valores.isna().sum())
        resumo.append(
            {
                "series_id": str(series_id),
                "source": str(grupo["source"].iloc[0]),
                "freq": str(grupo["freq"].iloc[0]),
                "unit": str(grupo["unit"].iloc[0]),
                "n_obs": n,
                "n_nulos": nulos,
                "pct_nulos": round(nulos / n * 100.0, 6),
                "date_min": _iso(grupo["date"].min()),
                "date_max": _iso(grupo["date"].max()),
                "value_min": (None if valores.isna().all() else float(valores.min())),
                "value_max": (None if valores.isna().all() else float(valores.max())),
                "vintages": sorted({v for v in grupo["vintage"].map(_iso) if v is not None}),
            }
        )
    return resumo


def montar_relatorio(
    *,
    raw: pd.DataFrame,
    catalogo: pd.DataFrame,
    hashes: dict[str, dict[str, Any]],
    excluidas: Sequence[TabelaExcluida],
    n_arquivos: int,
    linhas_dedup: int = 0,
) -> dict[str, Any]:
    """`relatorio_build.json` — **sem relógio**, para que dois builds iguais sejam idênticos."""
    valores = raw["value"]
    ausentes_pacote_minimo = catalogo[
        (~catalogo["presente_no_processed"])
        & (catalogo["status"] == StatusSerie.OK.value)
        & (catalogo["fonte"] != "FRED")
    ]
    sem_1t2006 = catalogo[catalogo["presente_no_processed"] & (~catalogo["cobre_1t2006"])]

    return {
        "feature": "F-013",
        "versao_build": versao_build(),
        "versao_build_componentes": list(MODULOS_DO_BUILD),
        "catalogo_sha256": catalogo_sha256(),
        "arquivos_lidos": n_arquivos,
        # Dedup deixa rastro **no dado**, não só no log (P2-2 do QA da Onda 2): 0 é a afirmação
        # de que nenhuma linha foi descartada na consolidação.
        "linhas_dedup": int(linhas_dedup),
        "tabelas_excluidas": [t.como_dict() for t in excluidas],
        "raw_series": {
            "arquivo": NOME_RAW_SERIES,
            "linhas": int(len(raw)),
            "series": int(raw["series_id"].nunique()),
            "date_min": _iso(raw["date"].min()),
            "date_max": _iso(raw["date"].max()),
            "collected_at_max": _iso_hora(raw["collected_at"].max()),
            "vintages": sorted({v for v in raw["vintage"].map(_iso) if v is not None}),
            "n_nulos_value": int(valores.isna().sum()),
            "pct_nulos_value": round(float(valores.isna().mean()) * 100.0, 6),
            "linhas_por_source": {
                str(k): int(v) for k, v in raw["source"].value_counts().sort_index().items()
            },
            "linhas_por_freq": {
                str(k): int(v) for k, v in raw["freq"].value_counts().sort_index().items()
            },
            **hashes[NOME_RAW_SERIES],
        },
        "series_catalog": {
            "arquivo": NOME_CATALOGO,
            "linhas": int(len(catalogo)),
            "presentes_no_processed": int(catalogo["presente_no_processed"].sum()),
            "cobrem_1t2006": int(catalogo["cobre_1t2006"].sum()),
            "colunas_observadas": list(COLUNAS_OBSERVADAS),
            **hashes[NOME_CATALOGO],
        },
        "duckdb": {"arquivo": NOME_DUCKDB, "views": ["raw_series", "series_catalog"]},
        "series": _resumo_por_serie(raw),
        "catalogo_ok_ausente_no_processed": [
            {"series_id": r.series_id, "fonte": r.fonte, "item_email": r.item_email}
            for r in ausentes_pacote_minimo.itertuples()
        ],
        "series_sem_cobertura_1t2006": [
            {"series_id": r.series_id, "data_inicio_observada": _iso(r.data_inicio_observada)}
            for r in sem_1t2006.itertuples()
        ],
    }


def construir(
    *,
    raiz: Path | None = None,
    raiz_processed: Path | None = None,
    com_duckdb: bool = True,
) -> ResultadoBuild:
    """Reconstrói `data/canonical/raw_series.parquet` + `series_catalog.parquet` de ponta a ponta.

    Sem rede, sem estado, sem efeito fora de `data/canonical/`. Rodar duas vezes sobre o mesmo
    `data/processed/` produz os mesmos dois Parquet e o mesmo relatório, byte a byte.
    """
    alvos, excluidas = descobrir_parquets_de_serie(raiz=raiz, raiz_processed=raiz_processed)
    bruto = carregar_processed(alvos)
    catalogo_declarado = load_catalog()

    # Procedência e mistura de fontes rodam no **concatenado**, antes do dedup (P1-3 do QA da
    # Onda 2): são guardas de conjunto (`series_id`/`source`/`unit` distintos por série), e rodá-las
    # depois de `drop_duplicates` fazia a linha apagada sair da evidência de CA-055/CA-077.
    validar_procedencia(bruto, catalogo_declarado)
    validar_sem_mistura_de_fontes(bruto)

    raw = consolidar(bruto)
    linhas_dedup = len(bruto) - len(raw)

    # Frequência nativa é a única que precisa do dedup feito: antes dele, a cópia idêntica de um
    # ponto mensal apareceria como "duas observações no mesmo período" (CA-058) sem ser.
    validar_frequencia_nativa(raw, catalogo_declarado)

    catalogo = materializar_catalogo(catalogo_declarado, raw)

    caminho_raw, sha_raw, bytes_raw = _gravar_parquet_validado(
        raw, nome=NOME_RAW_SERIES, schema=RawSeriesSchema, raiz=raiz
    )
    caminho_catalogo, sha_cat, bytes_cat = _gravar_parquet_validado(
        catalogo, nome=NOME_CATALOGO, schema=SeriesCatalogMaterializedSchema, raiz=raiz
    )

    relatorio = montar_relatorio(
        raw=raw,
        catalogo=catalogo,
        hashes={
            NOME_RAW_SERIES: {"sha256": sha_raw, "bytes": bytes_raw},
            NOME_CATALOGO: {"sha256": sha_cat, "bytes": bytes_cat},
        },
        excluidas=excluidas,
        n_arquivos=len(alvos),
        linhas_dedup=linhas_dedup,
    )

    caminho_duckdb: Path | None = None
    if com_duckdb:
        caminho_duckdb = construir_duckdb(
            caminho_raw=caminho_raw, caminho_catalogo=caminho_catalogo, raiz=raiz
        )

    caminho_relatorio = caminho_canonical(NOME_RELATORIO, raiz=raiz)
    caminho_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return ResultadoBuild(
        raw_series=raw,
        catalogo=catalogo,
        relatorio=relatorio,
        caminho_raw_series=caminho_raw,
        caminho_catalogo=caminho_catalogo,
        caminho_relatorio=caminho_relatorio,
        caminho_duckdb=caminho_duckdb,
        excluidas=tuple(excluidas),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.canonical.build_raw_series",
        description=(
            "Materializa data/canonical/raw_series.parquet e series_catalog.parquet a partir de "
            "data/processed/. Nunca toca a rede."
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Aceito por simetria com os extratores e sem efeito: esta camada só lê "
            "data/processed/ e nunca faz requisição."
        ),
    )
    parser.add_argument(
        "--sem-duckdb",
        action="store_true",
        help="Pula o ldc.duckdb derivado (ADR-006 §(a).2 — opcional e regenerável).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. `0` = build feito; `1` = falha explícita e nada gravado."""
    args = _parser().parse_args(argv)
    configurar_logging()
    try:
        resultado = construir(com_duckdb=not args.sem_duckdb)
    except ErroDeExtracao as erro:
        print(f"FALHA: {erro}", file=sys.stderr)
        return 1

    raw = resultado.relatorio["raw_series"]
    cat = resultado.relatorio["series_catalog"]
    # ASCII puro nos `print`: o stdout do console no Windows é cp1252 e `->`/`|` evitam o
    # `UnicodeEncodeError` que `→`/`·` causam (mesma família do Anti-SPEC §10.4.26).
    print(f"raiz: {raiz_repo()}")
    print(
        f"{NOME_RAW_SERIES}: {raw['linhas']} linhas | {raw['series']} series | "
        f"{raw['date_min']} -> {raw['date_max']} | nulos em value {raw['pct_nulos_value']}% | "
        f"sha256 {raw['sha256']}"
    )
    print(
        f"{NOME_CATALOGO}: {cat['linhas']} entradas | {cat['presentes_no_processed']} presentes | "
        f"{cat['cobrem_1t2006']} cobrem 1T2006 | sha256 {cat['sha256']}"
    )
    for excluida in resultado.excluidas:
        print(f"fora de raw_series: {excluida.arquivo}")
    ausentes = resultado.relatorio["catalogo_ok_ausente_no_processed"]
    print(f"series `ok` do pacote minimo ainda sem extrator rodado: {len(ausentes)}")
    print(f"relatorio: {resultado.caminho_relatorio}")
    if resultado.caminho_duckdb:
        print(f"duckdb: {resultado.caminho_duckdb}")
    print(f"versao_build: {resultado.relatorio['versao_build']}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    raise SystemExit(main())
