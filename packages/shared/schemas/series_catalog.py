"""Catálogo de séries e configuração de extratores — contratos pydantic + schema pandera.

Fonte de verdade do contrato (SPEC RF-019, CA-053..055). Os **dados** do catálogo vivem em
`series_catalog_data.py` (uma entrada por série, com a tag de confiança copiada de
`docs/research/`). Este módulo só define a forma e valida.

Regras que este contrato faz valer:
- **nenhum identificador inventado**: o que a pesquisa marca "a confirmar" entra com
  `status = A_CONFIRMAR` e identificador literal `a_confirmar`, e não pode estar no caminho crítico;
- toda série carrega `confianca` (CONFIRMADO | CONFIRMADO_SUB | NAO_VERIFICADO) — a mesma convenção
  de `docs/research/fontes-de-dados.md`;
- toda série carrega `lag_divulgacao_dias`, sem o qual a regra anti-look-ahead (RF-025) não é
  implementável;
- série de janela rolante, fonte instável ou licença restrita é marcada como tal.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

import pandera as pa
from pandera.typing import Series
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Fonte(StrEnum):
    """Fonte de dados. Espelha `source` em `raw_series`."""

    BCB_SGS = "BCB_SGS"
    BCB_OLINDA = "BCB_OLINDA"
    IBGE_SIDRA = "IBGE_SIDRA"
    ANBIMA_S3 = "ANBIMA_S3"
    ANBIMA_WEB = "ANBIMA_WEB"
    TESOURO_CKAN = "TESOURO_CKAN"
    B3_API = "B3_API"
    TEVA_GCS = "TEVA_GCS"
    YAHOO = "YAHOO"
    MSCI = "MSCI"
    FRED = "FRED"
    IPEADATA = "IPEADATA"
    CVM = "CVM"
    DERIVADO = "DERIVADO"
    MANUAL = "MANUAL"


class Freq(StrEnum):
    """Frequência nativa da série."""

    DIARIA = "D"
    MENSAL = "M"
    TRIMESTRAL = "Q"
    ANUAL = "A"


class Unidade(StrEnum):
    """Unidade e natureza do número — explicitar evita o erro clássico de escala."""

    PCT = "%"
    PCT_DIA = "%/dia"
    PCT_AA = "%a.a."
    PP = "pp"
    INDEX = "index"
    BRL = "BRL"
    USD = "USD"
    RATIO = "ratio"
    BPS = "bps"
    BRL_MILHOES = "R$ milhoes"


class Transformacao(StrEnum):
    """Transformação padrão aplicada para levar a série à grade trimestral."""

    NENHUMA = "nenhuma"
    ULTIMO_DIA_UTIL_TRI = "ultimo_dia_util_do_trimestre"
    MEDIA_TRIMESTRE = "media_do_trimestre"
    ACUMULACAO_GEOMETRICA = "acumulacao_geometrica_no_trimestre"
    RAZAO_INDICE = "razao_de_numero_indice"
    VARIACAO_12M = "variacao_12_meses"
    DELTA_TRIMESTRE = "delta_no_trimestre_em_pp"
    GAP_VS_TENDENCIA = "desvio_da_media_movel_20_trimestres"
    INTERPOLACAO_VERTICE_FIXO = "interpolacao_para_vertice_fixo"


class Confianca(StrEnum):
    """Tag de confiança, copiada de `docs/research/` — não inferida aqui."""

    CONFIRMADO = "CONFIRMADO"
    CONFIRMADO_SUB = "CONFIRMADO_SUB"
    NAO_VERIFICADO = "NAO_VERIFICADO"


class StatusSerie(StrEnum):
    """Situação da série no projeto."""

    OK = "ok"
    A_CONFIRMAR = "a_confirmar"
    DESCONTINUADA = "descontinuada"
    DESCARTADA = "descartada"
    PAGA = "paga"


IDENTIFICADOR_A_CONFIRMAR = "a_confirmar"

# Limiar da métrica de cobertura do PRD §7: "séries com `data_inicio <= 2006-01-31`
# dividido pelo total pedido".
# O schema segue o PRD: o 2006-01-02 que estava aqui media outra coisa (1º dia útil de 2006) e fazia
# a métrica divergir do documento que a define.
LIMIAR_COBERTURA_2006 = date(2006, 1, 31)

# Fonte que existe, responde e tem identificador confirmado, mas **não é alcançável nesta máquina**:
# `docs/plans/skills-manifest.md §3` mediu bloqueio na camada de aplicação (ReadTimeout + RST,
# 3/3 tentativas) em `fred.stlouisfed.org` e `api.stlouisfed.org`, e conclui que "nenhum requisito
# pode depender do FRED nesta máquina". `status = ok` descreve o identificador; o pacote mínimo é
# outra pergunta — ver `usavel_no_pacote_minimo`.
FONTES_BLOQUEADAS_NO_PACOTE_MINIMO: frozenset[Fonte] = frozenset({Fonte.FRED})


class SeriesCatalogEntry(BaseModel):
    """Uma linha do `series_catalog`: o que é a série, de onde vem e como virar trimestral."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)

    series_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9_\.\^=\-]+$")
    nome: str = Field(min_length=3, max_length=200)
    item_email: str = Field(
        description="Item do checklist de ESCOPO-EMAIL-ALEXANDRE.md (A1..A7, B1..B5, C1) ou '-'",
        max_length=16,
    )
    fonte: Fonte
    identificador: str = Field(
        min_length=1,
        max_length=300,
        description="Código/tabela/slug/ticker na fonte. Nunca vazio, nunca inventado.",
    )
    fonte_url: str = Field(min_length=8, max_length=500)
    freq: Freq
    data_inicio: date | None = Field(
        default=None,
        description="Início medido na pesquisa. None = não medido (ver obs); nunca um palpite.",
    )
    data_fim: date | None = Field(
        default=None, description="None = série viva. Data = descontinuada nesse ponto."
    )
    unit: Unidade
    transformacao_padrao: Transformacao = Transformacao.NENHUMA
    lag_divulgacao_dias: int = Field(default=0, ge=0, le=400)
    confianca: Confianca
    status: StatusSerie = StatusSerie.OK
    is_total_return: bool | None = Field(
        default=None, description="None = a confirmar (gap G-01 para setoriais da B3)."
    )
    janela_rolante: bool = Field(
        default=False, description="True = a fonte apaga o passado; nunca usar para backfill."
    )
    fonte_instavel: bool = Field(
        default=False,
        description="True = endpoint não documentado ou conectividade incerta (FRED, B3, MSCI).",
    )
    licenca_restrita: bool = Field(
        default=False, description="True = terceiro sem licença comercial explícita (Teva e afins)."
    )
    obs: str = Field(default="", max_length=600)

    @field_validator("identificador")
    @classmethod
    def _identificador_nao_placeholder_silencioso(cls, v: str) -> str:
        if v.strip() in {"", "-", "?", "TODO"}:
            msg = "identificador vazio ou placeholder: use 'a_confirmar' com status=A_CONFIRMAR"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _coerencia_status(self) -> SeriesCatalogEntry:
        placeholder = self.identificador == IDENTIFICADOR_A_CONFIRMAR
        if placeholder and self.status is not StatusSerie.A_CONFIRMAR:
            msg = f"{self.series_id}: identificador 'a_confirmar' exige status=a_confirmar"
            raise ValueError(msg)
        if self.status is StatusSerie.DESCONTINUADA and self.data_fim is None:
            msg = f"{self.series_id}: série descontinuada precisa de data_fim"
            raise ValueError(msg)
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            msg = f"{self.series_id}: data_fim anterior a data_inicio"
            raise ValueError(msg)
        return self

    @property
    def cobre_2006(self) -> bool | None:
        """True se a série cobre 1T2006: `data_inicio <= LIMIAR_COBERTURA_2006` (PRD §7).

        `None` quando o início não foi medido na pesquisa — e `None` **não é** `False`: é "não
        medido". Quem calcula a métrica de cobertura precisa decidir o que fazer com esses casos em
        vez de contá-los como falha silenciosa.
        """
        if self.data_inicio is None:
            return None
        return self.data_inicio <= LIMIAR_COBERTURA_2006

    @property
    def usavel_no_pacote_minimo(self) -> bool:
        """Entra no caminho crítico de 2026-10-14? `ok` **e** fonte alcançável nesta máquina.

        `status = ok` responde "o identificador é real e a série serve"; esta propriedade responde
        "dá para extrair até o Comitê". São perguntas diferentes: as 13 séries FRED têm
        identificador confirmado (`docs/research/fontes-de-dados.md §C10`) e continuam `ok`, mas o
        FRED está bloqueado nesta máquina (`skills-manifest.md §3`), então **não** contam no pacote
        mínimo — o plano B é Yahoo/MSCI/PTAX (S-09 no `DECISIONS_LOG.md`).
        """
        if self.fonte in FONTES_BLOQUEADAS_NO_PACOTE_MINIMO:
            return False
        return self.status is StatusSerie.OK


class ExtractorConfig(BaseModel):
    """Configuração de um extrator. Um extrator serve 1..N séries da mesma fonte."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nome: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9_]+$")
    fonte: Fonte
    series_ids: tuple[str, ...] = Field(min_length=1)
    base_url: str = Field(min_length=8, max_length=500)
    formato: str = Field(description="json | csv | xlsx | txt | html | parquet | zip")
    encoding: str = Field(
        default="utf-8",
        description="Sempre explícito: o default do locale (cp1252 no Windows) corrompe acento.",
    )
    requer_user_agent_browser: bool = Field(
        default=True, description="Yahoo/CKAN/B3/MSCI retornam 429/erro sem UA de browser."
    )
    janela_maxima_dias: int | None = Field(
        default=None, description="SGS diário rejeita > ~10 anos com HTTP 200 + corpo de erro."
    )
    pagina_com_skip: bool = Field(
        default=False, description="Olinda trunca em $top=20000 sem nextLink."
    )
    cache_condicional: bool = Field(
        default=False, description="Usa ETag/Last-Modified (Tesouro 14,6 MB, COTAHIST até 91 MB)."
    )
    contagem_minima_esperada: int | None = Field(
        default=None, ge=1, description="Assert anti-truncamento silencioso."
    )
    valor_canario: tuple[str, float] | None = Field(
        default=None, description="(data ISO, valor) conhecido da fonte, para teste de contrato."
    )
    destino_raw: str = Field(pattern=r"^data/raw/[a-z0-9\-/]+$")
    ausencia_e_caso_normal: bool = Field(
        default=False, description="True para o job diário da ANBIMA (dia sem divulgação)."
    )
    timeout_s: float = Field(default=60.0, gt=0, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)

    @field_validator("formato")
    @classmethod
    def _formato_suportado(cls, v: str) -> str:
        suportados = {"json", "csv", "xlsx", "txt", "html", "parquet", "zip"}
        if v not in suportados:
            msg = f"formato '{v}' não suportado; use um de {sorted(suportados)}"
            raise ValueError(msg)
        return v


class SeriesCatalogSchema(pa.DataFrameModel):
    """Forma tabular do catálogo, materializada em `data/canonical/series_catalog.parquet`."""

    series_id: Series[str] = pa.Field(nullable=False, unique=True)
    nome: Series[str] = pa.Field(nullable=False)
    item_email: Series[str] = pa.Field(nullable=False)
    fonte: Series[str] = pa.Field(nullable=False, isin=tuple(f.value for f in Fonte))
    identificador: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1})
    fonte_url: Series[str] = pa.Field(nullable=False)
    freq: Series[str] = pa.Field(nullable=False, isin=tuple(f.value for f in Freq))
    data_inicio: Series[pa.DateTime] = pa.Field(nullable=True)
    data_fim: Series[pa.DateTime] = pa.Field(nullable=True)
    unit: Series[str] = pa.Field(nullable=False, isin=tuple(u.value for u in Unidade))
    transformacao_padrao: Series[str] = pa.Field(
        nullable=False, isin=tuple(t.value for t in Transformacao)
    )
    lag_divulgacao_dias: Series[int] = pa.Field(nullable=False, ge=0, le=400)
    confianca: Series[str] = pa.Field(nullable=False, isin=tuple(c.value for c in Confianca))
    status: Series[str] = pa.Field(nullable=False, isin=tuple(s.value for s in StatusSerie))
    is_total_return: Series[bool] = pa.Field(nullable=True)
    janela_rolante: Series[bool] = pa.Field(nullable=False)
    fonte_instavel: Series[bool] = pa.Field(nullable=False)
    licenca_restrita: Series[bool] = pa.Field(nullable=False)
    obs: Series[str] = pa.Field(nullable=True)

    class Config:
        """Configuração do schema."""

        name = "series_catalog"
        strict = True
        coerce = True


def load_catalog(entradas: list[dict[str, Any]] | None = None) -> tuple[SeriesCatalogEntry, ...]:
    """Valida o catálogo (default: `series_catalog_data.SERIES_CATALOG`) e devolve as entradas.

    Levanta `pydantic.ValidationError` na primeira entrada inválida — é o portão que impede
    identificador inventado ou status incoerente de entrar no pipeline.
    """
    if entradas is None:
        from packages.shared.schemas.series_catalog_data import SERIES_CATALOG

        entradas = list(SERIES_CATALOG)
    catalogo = tuple(SeriesCatalogEntry(**e) for e in entradas)
    ids = [e.series_id for e in catalogo]
    duplicados = sorted({i for i in ids if ids.count(i) > 1})
    if duplicados:
        msg = f"series_id duplicado no catálogo: {duplicados}"
        raise ValueError(msg)
    return catalogo


def resumo_catalogo(catalogo: tuple[SeriesCatalogEntry, ...]) -> dict[str, int]:
    """Contagem por status — usada na evidência de dados do Feature Contract."""
    resumo: dict[str, int] = {"total": len(catalogo)}
    for status in StatusSerie:
        resumo[status.value] = sum(1 for e in catalogo if e.status is status)
    resumo["cobre_2006"] = sum(1 for e in catalogo if e.cobre_2006 is True)
    resumo["inicio_nao_medido"] = sum(1 for e in catalogo if e.data_inicio is None)
    resumo["usavel_no_pacote_minimo"] = sum(1 for e in catalogo if e.usavel_no_pacote_minimo)
    return resumo
