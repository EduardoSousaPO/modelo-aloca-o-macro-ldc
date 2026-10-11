"""Extrator dos índices ANBIMA IMA a partir do bucket S3 público (F-002, SPEC RF-011).

Fonte: `https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/arquivos/indices-historico/
{SLUG}-HISTORICO.xls` — grátis, sem cadastro, sem token (`docs/research/fontes-de-dados.md §B6`).
É a **única** fonte gratuita do número-índice diário de IRF-M 1 e IRF-M 1+, e a única viva de IMA
desde que as séries SGS 12461-12469 morreram em 22/05/2023 (Anti-SPEC §10.1.6: aquelas séries
servem para reconciliação, nunca como fonte).

Caminho: `ClienteHTTP` → `arquivar_bruto` (`data/raw/anbima-ima/`, idempotente, com manifesto) →
parse → `gravar_processado_parquet` (`data/processed/anbima-ima/<series_id>.parquet`), na
**frequência nativa diária** (Anti-SPEC §10.4.28: trimestral é agregação derivada, feita adiante).

As quatro pegadinhas medidas desta fonte, e onde cada uma é tratada:

1. **A extensão mente.** `*-HISTORICO.xls` é XLSX (magic `PK\\x03\\x04`). `exigir_formato` recusa
   qualquer outra coisa antes do parse (CA-030) e o arquivo é lido de `io.BytesIO`, nunca do disco
   com extensão `.xls` — `openpyxl.load_workbook` **recusa pela extensão** (`.xls`), mesmo quando o
   conteúdo é OOXML válido. Por isso o bruto é arquivado como `.xlsx`, que é o formato real.
2. **O rótulo da coluna `Índice` é instável** ao longo da série: `IMA-B` nas linhas antigas e
   `IMA - B` nas recentes (idem `IMA-GERAL`/`IMA - Geral`, `IRF-M 1+`/`IRF - M 1+`).
   `normalizar_rotulo` colapsa os dois e o `series_id` vem do **SLUG do catálogo**, não do rótulo —
   um `asset_id` por índice (CA-032). O mapa `ROTULOS_ESPERADOS` é a guarda contra o arquivo trazer
   um índice diferente do pedido (SPEC CB-015: normalizador **mais** mapa explícito de códigos).
3. **A listagem do bucket responde `AccessDenied`** — os SLUGs são hard-coded aqui e no catálogo,
   e conferidos contra ele na importação do módulo (CA-033). "5+" é `5MAIS`, não `+`/`P`/`PLUS`.
4. **O número já vem como `float` nativo** do `openpyxl` (6 decimais, sem vírgula decimal). Ainda
   assim passa por `para_float_ptbr`, que trata número tipado como número (era o bug QA-01 de
   F-001) e devolve `None` — nunca `0` — para ausência (Anti-SPEC §10.1.4).

Uso:

```bash
uv run python -m apps.pipeline.extract.anbima_s3                      # os 9 índices, ao vivo
uv run python -m apps.pipeline.extract.anbima_s3 --indices IMAB IRFM  # só dois
uv run python -m apps.pipeline.extract.anbima_s3 --offline            # relê data/raw, sem rede
```
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pandas as pd

from apps.pipeline.common import (
    DO_CONTRATO,
    SUFIXO_MANIFESTO,
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    FormatoDetectado,
    arquivar_bruto,
    caminho_destino_raw,
    configurar_logging,
    exigir_contagem_minima,
    exigir_formato,
    gravar_processado_parquet,
    nome_arquivo_raw,
    normalizar_rotulo,
    obter_logger,
    obtido_em_arquivado,
    para_data,
    para_float_ptbr,
    sha256_de,
)
from packages.shared.schemas import ExtractorConfig, Fonte, Freq, Unidade, load_catalog

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from collections.abc import Sequence
    from pathlib import Path

    from apps.pipeline.common import Transporte

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Catálogo local: SLUGs, rótulos e pisos de contagem
# ─────────────────────────────────────────────────────────────────────────────

URL_S3 = (
    "https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/"
    "arquivos/indices-historico/{slug}-HISTORICO.xls"
)

#: Os 8 índices pedidos no e-mail do Alexandre (itens **B1** e **B2**). `IMAC` (descontinuado em
#: 2021) e `IHFA` (fora do e-mail) estão deliberadamente fora — ver `TODO.md` F-002.
SLUGS_EMAIL: tuple[str, ...] = (
    "IMAB",
    "IMAB5",
    "IMAB5MAIS",
    "IRFM",
    "IRFM1",
    "IRFM1MAIS",
    "IMAGERAL",
    "IMAS",
)

#: O que o extrator sabe baixar: os 8 do e-mail + `IMAGERALEXC`, que o Feature Contract inclui
#: como complemento do IMA-Geral (o "ex-C" é o IMA-Geral sem a parcela IGP-M descontinuada).
SLUGS_SUPORTADOS: tuple[str, ...] = (*SLUGS_EMAIL, "IMAGERALEXC")

#: Rótulos **normalizados** (`normalizar_rotulo`) aceitos na coluna `Índice` de cada arquivo.
#: Medidos nos 11 arquivos reais em 2026-10-10. A remoção de espaços colapsa `IMA-B`/`IMA - B`
#: num rótulo só (CA-032); onde a fonte também move o hífen (`IMA-GERAL-EX-C` × `IMA - Geral ex-C`)
#: o mapa explícito faz o resto — o `series_id` nunca sai do rótulo, sempre do SLUG.
ROTULOS_ESPERADOS: dict[str, frozenset[str]] = {
    "IMAB": frozenset({"IMA-B"}),
    "IMAB5": frozenset({"IMA-B5"}),
    "IMAB5MAIS": frozenset({"IMA-B5+"}),
    "IRFM": frozenset({"IRF-M"}),
    "IRFM1": frozenset({"IRF-M1"}),
    "IRFM1MAIS": frozenset({"IRF-M1+"}),
    "IMAGERAL": frozenset({"IMA-GERAL"}),
    "IMAS": frozenset({"IMA-S"}),
    "IMAGERALEXC": frozenset({"IMA-GERAL-EX-C", "IMA-GERALEX-C"}),
}

#: Piso anti-truncamento (R2): nº de linhas medido em 2026-10-10. A série só cresce; vir menos é
#: truncamento silencioso ou arquivo trocado, e tem de levantar em vez de gravar série curta.
LINHAS_MINIMAS: dict[str, int] = {
    "IMAB": 5795,
    "IMAB5": 5795,
    "IMAB5MAIS": 5795,
    "IRFM": 6700,
    "IRFM1": 6488,
    "IRFM1MAIS": 6488,
    "IMAGERAL": 6237,
    "IMAS": 6245,
    "IMAGERALEXC": 5407,
}

#: `(data ISO, número-índice)` da **primeira** observação de cada série, conferido contra o
#: arquivo da fonte. O de `IMAB` é o valor-canário da SPEC (CA-031).
VALORES_CANARIO: dict[str, tuple[str, float]] = {
    "IMAB": ("2003-09-16", 723.070317),
    "IMAB5": ("2003-09-16", 775.879343),
    "IMAB5MAIS": ("2003-09-16", 715.675793),
    "IRFM": ("2000-02-01", 863.150015),
    "IRFM1": ("2000-12-01", 1000.0),
    "IRFM1MAIS": ("2000-12-01", 1000.0),
    "IMAGERAL": ("2001-12-04", 532.621995),
    "IMAS": ("2001-12-03", 550.485024),
    "IMAGERALEXC": ("2005-03-31", 1000.0),
}

DESTINO_RAW = "data/raw/anbima-ima"
SUBPASTA_PROCESSED = "anbima-ima"
#: `.xlsx` e não `.xls`: é o formato real (OOXML) e é a extensão que o `openpyxl` aceita abrir.
EXTENSAO_RAW = "xlsx"

# Nomes das 3 colunas usadas, já normalizados — a planilha tem 10 e o acento/espaçamento do
# cabeçalho não é contrato. As outras 7 (variações, Duration, PMR) são derivadas e ficam fora:
# `processed_series` é uma tabela longa de uma métrica por série (`ProcessedSeriesSchema`).
COL_INDICE = "ÍNDICE"
COL_DATA = "DATADEREFERÊNCIA"
COL_NUMERO_INDICE = "NÚMEROÍNDICE"


class HistoricoInconsistente(ErroDeExtracao):
    """O XLSX abriu, mas o conteúdo não é o histórico esperado do índice pedido."""


def series_id_de(slug: str) -> str:
    """`ANBIMA_IMAB` — o `series_id` do catálogo, derivado do SLUG e nunca do rótulo da planilha."""
    return f"ANBIMA_{slug}"


def config_do_indice(slug: str) -> ExtractorConfig:
    """`ExtractorConfig` do índice: o contrato é a configuração, nada aqui é hard-code solto."""
    if slug not in SLUGS_SUPORTADOS:
        msg = f"SLUG {slug!r} não suportado; use um de {list(SLUGS_SUPORTADOS)}"
        raise ErroDeExtracao(msg)
    return ExtractorConfig(
        nome=f"anbima_s3_{slug.lower()}",
        fonte=Fonte.ANBIMA_S3,
        series_ids=(series_id_de(slug),),
        base_url=URL_S3.format(slug=slug),
        formato="xlsx",
        # OOXML é UTF-8 internamente; o `openpyxl` cuida disso, mas o contrato declara (CA-022).
        encoding="utf-8",
        requer_user_agent_browser=True,
        janela_maxima_dias=None,  # o arquivo é o histórico inteiro, num GET
        contagem_minima_esperada=LINHAS_MINIMAS[slug],
        valor_canario=VALORES_CANARIO[slug],
        destino_raw=DESTINO_RAW,
        timeout_s=120.0,  # ~400 KB por arquivo; o S3 responde rápido, mas sem pressa
    )


def _conferir_catalogo() -> None:
    """Falha na importação se um SLUG daqui não existir em `series_catalog_data` (CA-033).

    É o que impede este módulo e o catálogo de divergirem em silêncio: o catálogo é a fonte de
    verdade de `series_id`, `data_inicio` e `fonte_url`; aqui ficam só os SLUGs e o layout.
    """
    catalogo = {e.series_id: e for e in load_catalog()}
    for slug in SLUGS_SUPORTADOS:
        entrada = catalogo.get(series_id_de(slug))
        if entrada is None:
            msg = f"{series_id_de(slug)} não está em packages/shared/schemas/series_catalog_data.py"
            raise ErroDeExtracao(msg)
        if entrada.identificador != slug:
            msg = f"{entrada.series_id}: catálogo diz identificador={entrada.identificador!r}"
            raise ErroDeExtracao(msg)


_conferir_catalogo()


# ─────────────────────────────────────────────────────────────────────────────
# Parse
# ─────────────────────────────────────────────────────────────────────────────


def _coluna(bruto: pd.DataFrame, normalizada: str, *, origem: str) -> str:
    """Nome real da coluna cujo rótulo normalizado é `normalizada`."""
    for coluna in bruto.columns:
        if normalizar_rotulo(coluna) == normalizada:
            return str(coluna)
    vistas = [normalizar_rotulo(c) for c in bruto.columns]
    msg = f"{origem}: coluna {normalizada!r} ausente; a planilha traz {vistas}"
    raise HistoricoInconsistente(msg)


def parse_historico(
    conteudo: bytes,
    *,
    slug: str,
    origem: str,
    collected_at: datetime,
    minimo: int | None | object = DO_CONTRATO,
) -> pd.DataFrame:
    """Bytes do `*-HISTORICO.xls` → DataFrame no contrato `ProcessedSeriesSchema`.

    Não grava nada: validar antes de escrever é o que CA-003 pede, e quem escreve é
    `gravar_processado_parquet`. Levanta em vez de devolver série curta, com data duplicada,
    fora de ordem, com rótulo de outro índice ou com número-índice nulo.

    `minimo` segue o idioma de `ClienteHTTP.json_array`: por default usa
    `ExtractorConfig.contagem_minima_esperada` (o piso real da série, ~5.795 linhas no IMA-B);
    `None` desliga a guarda, que é o que a fixture — um recorte das primeiras e últimas linhas,
    limitado a 200 KB — precisa para exercitar o parse sem carregar 20 anos de série.
    """
    config = config_do_indice(slug)
    # CA-030: o leitor é escolhido pelos magic bytes, nunca pela extensão `.xls` da URL.
    exigir_formato(conteudo, FormatoDetectado.XLSX, origem=origem)
    bruto = pd.read_excel(io.BytesIO(conteudo), engine="openpyxl")

    col_indice = _coluna(bruto, COL_INDICE, origem=origem)
    col_data = _coluna(bruto, COL_DATA, origem=origem)
    col_valor = _coluna(bruto, COL_NUMERO_INDICE, origem=origem)

    # CA-032: `IMA-B` e `IMA - B` colapsam; rótulo de outro índice no arquivo é erro ruidoso.
    rotulos = {normalizar_rotulo(v) for v in bruto[col_indice].dropna().tolist()}
    inesperados = sorted(rotulos - ROTULOS_ESPERADOS[slug])
    if inesperados:
        msg = (
            f"{origem}: coluna Índice traz rótulo inesperado {inesperados} para o SLUG {slug}; "
            f"esperado (normalizado) um de {sorted(ROTULOS_ESPERADOS[slug])}"
        )
        raise HistoricoInconsistente(msg)

    datas = [para_data(v, FormatoData.DD_MM_AAAA, origem=origem) for v in bruto[col_data].tolist()]
    valores = [para_float_ptbr(v, origem=origem) for v in bruto[col_valor].tolist()]

    quadro = pd.DataFrame(
        {
            "series_id": series_id_de(slug),
            "date": pd.to_datetime(pd.Series(datas, dtype="object")),
            "value": pd.Series(valores, dtype="float64"),
            "source": Fonte.ANBIMA_S3.value,
            "freq": Freq.DIARIA.value,
            # `vintage` = a **data** (sem hora) de `collected_at`, que sai do manifesto do bruto
            # (D-b da consolidação da Onda 1). Identifica a safra de extração — é o que torna uma
            # revisão retroativa da ANBIMA visível em vez de silenciosa (RF-025 / Anti-SPEC
            # §10.2.7) mesmo quando ela não acrescenta ponto novo ao histórico.
            "vintage": pd.Timestamp(collected_at).tz_localize(None).normalize(),
            "unit": Unidade.INDEX.value,
            "collected_at": pd.Timestamp(collected_at).tz_localize(None),
        }
    )
    piso = config.contagem_minima_esperada if minimo is DO_CONTRATO else minimo
    _validar(quadro, slug=slug, origem=origem, minimo=piso)  # type: ignore[arg-type]
    return quadro.reset_index(drop=True)


def _validar(quadro: pd.DataFrame, *, slug: str, origem: str, minimo: int | None) -> None:
    """Guardas de conteúdo: contagem, nulo, duplicata, ordem e data futura."""
    exigir_contagem_minima(len(quadro), minimo=minimo, origem=f"{slug} @ {origem}")

    if quadro["date"].isna().any():
        msg = f"{origem}: {int(quadro['date'].isna().sum())} linha(s) sem Data de Referência"
        raise HistoricoInconsistente(msg)
    # `value` nulo é legítimo em `processed_series` quando a ausência é esperada (feriado, mês sem
    # divulgação). Aqui não é: o número-índice é a razão de ser do arquivo, e nulo nele só sai de
    # falha de parse. Nunca preencher com `0` (Anti-SPEC §10.1.4) — levantar.
    if quadro["value"].isna().any():
        msg = f"{origem}: {int(quadro['value'].isna().sum())} linha(s) com Número Índice nulo"
        raise HistoricoInconsistente(msg)

    duplicadas = quadro.loc[quadro["date"].duplicated(keep=False), "date"]
    if not duplicadas.empty:
        amostra = sorted({d.date().isoformat() for d in duplicadas})[:5]
        msg = f"{origem}: data repetida no histórico (amostra: {amostra})"
        raise HistoricoInconsistente(msg)
    if not quadro["date"].is_monotonic_increasing:
        msg = f"{origem}: Data de Referência fora de ordem crescente"
        raise HistoricoInconsistente(msg)

    futuras = quadro.loc[quadro["date"] > quadro["collected_at"], "date"]
    if not futuras.empty:
        msg = f"{origem}: data futura no histórico (máx {futuras.max().date().isoformat()})"
        raise HistoricoInconsistente(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Extração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoIndice:
    """Evidência de dados de um índice — o que vai para o relatório do Feature Contract."""

    slug: str
    series_id: str
    linhas: int
    data_inicio: date
    data_fim: date
    pct_nulos_value: float
    valor_inicial: float
    valor_final: float
    sha256_raw: str
    bytes_raw: int
    caminho_raw: Path | None
    raw_idempotente: bool
    caminho_processed: Path | None

    def resumo(self) -> str:
        """Uma linha para o log e para a saída da CLI, **só em ASCII**.

        O `stdout` do terminal do Windows é cp1252 e `print` de `→` ("->") levanta
        `UnicodeEncodeError` no meio de uma execução que já gravou tudo. Mesma raiz do
        Anti-SPEC §10.4.26: nunca confiar no encoding do locale, nem na saída.
        """
        raw = "idempotente" if self.raw_idempotente else "novo"
        return (
            f"{self.series_id}: {self.linhas} linhas, {self.data_inicio} -> {self.data_fim}, "
            f"{self.valor_inicial:.6f} -> {self.valor_final:.6f}, "
            f"nulos={self.pct_nulos_value:.2%}, raw {raw} sha256={self.sha256_raw[:12]}..."
        )


def _resultado(
    quadro: pd.DataFrame,
    *,
    slug: str,
    sha256_raw: str,
    bytes_raw: int,
    caminho_raw: Path | None,
    raw_idempotente: bool,
    caminho_processed: Path | None,
) -> ResultadoIndice:
    return ResultadoIndice(
        slug=slug,
        series_id=series_id_de(slug),
        linhas=len(quadro),
        data_inicio=quadro["date"].min().date(),
        data_fim=quadro["date"].max().date(),
        pct_nulos_value=float(quadro["value"].isna().mean()),
        valor_inicial=float(quadro["value"].iloc[0]),
        valor_final=float(quadro["value"].iloc[-1]),
        sha256_raw=sha256_raw,
        bytes_raw=bytes_raw,
        caminho_raw=caminho_raw,
        raw_idempotente=raw_idempotente,
        caminho_processed=caminho_processed,
    )


def nome_processado(slug: str) -> str:
    """`anbima-ima/ANBIMA_IMAB.parquet` — caminho relativo dentro de `data/processed/`."""
    return f"{SUBPASTA_PROCESSED}/{series_id_de(slug)}.parquet"


def extrair_indice(
    slug: str,
    *,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
) -> ResultadoIndice:
    """Baixa, arquiva o bruto, parseia e grava o processado de **um** índice.

    A `data_ref` do nome do arquivo bruto é a **última data do histórico**, não "hoje": é o que
    torna o segundo download do mesmo dia byte-idêntico e idempotente (CA-027) e o que faz uma
    revisão retroativa do mesmo retrato bater em `ConteudoDivergente` em vez de sobrescrever
    dado de janela rolante (R8).
    """
    config = config_do_indice(slug)
    cliente = ClienteHTTP(config, transporte=transporte)
    resposta = cliente.get()
    conteudo = resposta.conteudo

    quadro = parse_historico(
        conteudo, slug=slug, origem=resposta.url, collected_at=resposta.obtida_em
    )
    data_ref = quadro["date"].max().date()

    arquivado = arquivar_bruto(
        conteudo,
        destino=caminho_destino_raw(config, raiz=raiz),
        nome=nome_arquivo_raw(slug, data_ref=data_ref, extensao=EXTENSAO_RAW),
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
    )
    destino_processed = (
        gravar_processado_parquet(quadro, nome=nome_processado(slug), raiz=raiz) if gravar else None
    )
    resultado = _resultado(
        quadro,
        slug=slug,
        sha256_raw=arquivado.sha256,
        bytes_raw=arquivado.bytes_gravados,
        caminho_raw=arquivado.caminho,
        raw_idempotente=arquivado.idempotente,
        caminho_processed=destino_processed,
    )
    _log.info("%s", resultado.resumo())
    return resultado


def _bruto_arquivado(slug: str, *, raiz: Path | None) -> Path:
    """O arquivo bruto mais recente do índice em `data/raw/anbima-ima/` (modo `--offline`).

    Aceita tanto o nome determinístico (`IMAB__2026-10-09.xlsx`) quanto a amostra manual
    (`IMAB.xls`) que a pesquisa deixou na pasta.
    """
    pasta = caminho_destino_raw(config_do_indice(slug), raiz=raiz)
    # O filtro do manifesto é defensivo: aqui a extensão é `.xlsx` e o `.meta.json` não casa com
    # o glob, mas em fonte JSON casa (`x__2026-10-09.json.meta.json` bate em `x__*.json`) e
    # ordenaria **antes** do dado. Mesmo filtro em todo extrator, para a regra não ter exceção.
    candidatos = sorted(
        (
            c
            for c in pasta.glob(f"{slug}__*.{EXTENSAO_RAW}")
            if not c.name.endswith(SUFIXO_MANIFESTO)
        ),
        reverse=True,
    )
    candidatos += [p for p in (pasta / f"{slug}.xls", pasta / f"{slug}.xlsx") if p.is_file()]
    if not candidatos:
        msg = f"modo offline: nenhum bruto de {slug} em {pasta}"
        raise ErroDeExtracao(msg)
    return candidatos[0]


def extrair_indice_offline(
    slug: str,
    *,
    raiz: Path | None = None,
    gravar: bool = True,
    caminho: Path | None = None,
) -> ResultadoIndice:
    """Reprocessa um índice do bruto já arquivado — sem rede, sem reescrever `data/raw/`."""
    alvo = caminho or _bruto_arquivado(slug, raiz=raiz)
    conteudo = alvo.read_bytes()
    # D-b: `collected_at` vem do manifesto do bruto, não do relógio — é o que faz duas rodadas
    # `--offline` sobre o mesmo arquivo produzirem o mesmo Parquet.
    quadro = parse_historico(
        conteudo,
        slug=slug,
        origem=str(alvo),
        collected_at=obtido_em_arquivado(alvo) or datetime.now(tz=UTC),
    )
    destino_processed = (
        gravar_processado_parquet(quadro, nome=nome_processado(slug), raiz=raiz) if gravar else None
    )
    resultado = _resultado(
        quadro,
        slug=slug,
        sha256_raw=sha256_de(conteudo),
        bytes_raw=len(conteudo),
        caminho_raw=alvo,
        raw_idempotente=True,
        caminho_processed=destino_processed,
    )
    _log.info("[offline] %s", resultado.resumo())
    return resultado


def extrair(
    slugs: Sequence[str] | None = None,
    *,
    offline: bool = False,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
) -> dict[str, ResultadoIndice]:
    """Roda os índices pedidos (default: `SLUGS_SUPORTADOS`) e devolve a evidência por SLUG."""
    alvos = tuple(slugs) if slugs else SLUGS_SUPORTADOS
    resultados: dict[str, ResultadoIndice] = {}
    for slug in alvos:
        if offline:
            resultados[slug] = extrair_indice_offline(slug, raiz=raiz, gravar=gravar)
        else:
            resultados[slug] = extrair_indice(slug, transporte=transporte, raiz=raiz, gravar=gravar)
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.anbima_s3",
        description="Extrai os índices ANBIMA IMA do bucket S3 público (F-002, SPEC RF-011).",
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        metavar="SLUG",
        choices=SLUGS_SUPORTADOS,
        help=f"subconjunto a extrair (default: todos — {' '.join(SLUGS_SUPORTADOS)})",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reprocessa o bruto já em data/raw/anbima-ima/, sem tocar a rede",
    )
    parser.add_argument(
        "--sem-gravar",
        action="store_true",
        help="não escreve em data/processed/ (só confere e imprime a evidência)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` em sucesso, `1` em qualquer `ErroDeExtracao`."""
    args = _parser().parse_args(list(argv) if argv is not None else None)
    configurar_logging()
    try:
        resultados = extrair(args.indices, offline=args.offline, gravar=not args.sem_gravar)
    except ErroDeExtracao as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for resultado in resultados.values():
        print(resultado.resumo())
    cobrem_2006 = sum(1 for r in resultados.values() if r.data_inicio <= date(2006, 1, 2))
    print(f"{len(resultados)} índice(s); {cobrem_2006} com data_inicio <= 2006-01-02")
    return 0


def _main_cli() -> None:  # pragma: no cover - invocado só por `python -m`
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _main_cli()
