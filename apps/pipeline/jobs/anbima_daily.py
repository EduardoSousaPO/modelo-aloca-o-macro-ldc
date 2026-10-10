"""Job diário de arquivamento das séries de janela rolante da ANBIMA (F-009 / RF-010).

As duas séries abaixo vivem numa **janela rolante de ~20 dias úteis** no site da ANBIMA — fora
dela não existe backfill gratuito (`docs/research/fontes-de-dados.md` §A4.2 e §A5). Cada dia não
arquivado é série perdida para sempre, e usar janela rolante como fonte de histórico é proibido
(Anti-SPEC §10.1.3). Daí este job: roda todo dia útil, grava o bruto versionado por data e trata
ausência como **caso normal** (CA-028), nunca como falha.

- taxas indicativas: ``GET  .../merc-sec/arqs/ms{AAMMDD}.txt`` → ``data/raw/anbima-ms/``
- Curva Zero (Svensson):        ``POST .../est-termo/CZ-down.asp`` → ``data/raw/anbima-ettj/``

CLI::

    python -m apps.pipeline.jobs.anbima_daily [--date AAAA-MM-DD] [--backfill N]

Exit code 0 = tudo arquivado, já arquivado ou ausente (caso normal). ≠ 0 = corpo inválido, eco de
outra data, truncamento ou rede fora — sempre com mensagem acionável e **sem gravar nada**.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import io
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Final

import pandas as pd
import requests

# TODO(F-001): migrar para apps.pipeline.common.http (cliente HTTP comum: UA de browser, retry com
# backoff, timeout, validador de shape e checagem de magic bytes). Enquanto F-001 está sendo
# implementada em paralelo (Onda 0), este módulo carrega a sua própria camada HTTP mínima — o
# `_sessao`/`baixar`/`detectar_corpo_suspeito` abaixo saem daqui quando o módulo comum existir.

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: UA de browser é obrigatório em toda requisição deste projeto (`AGENTS.md §19`, risco R5/R12).
USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

#: Os 5 títulos públicos que o `ms*.txt` tem de reconhecer (CA-029).
TITULOS_ESPERADOS: Final[frozenset[str]] = frozenset({"LTN", "LFT", "NTN-B", "NTN-C", "NTN-F"})

#: Colunas sem as quais o `ms*.txt` não é o arquivo esperado.
MS_COLUNAS_MINIMAS: Final[tuple[str, ...]] = (
    "Titulo",
    "Data Referencia",
    "Tx. Indicativas",
    "PU",
)

#: Tamanho medido da janela rolante das duas fontes em 2026-10-10 (§A4.2 / §A5.2).
JANELA_ROLANTE_DIAS_UTEIS: Final[int] = 20

LOG_RELATIVO: Final[str] = "data/raw/anbima-daily-job.log"

# ── vereditos possíveis de um dia × fonte ────────────────────────────────────────────────────────
ARQUIVADO: Final[str] = "arquivado"
JA_ARQUIVADO: Final[str] = "ja_arquivado"
REVISAO_ARQUIVADA: Final[str] = "revisao_arquivada"
AUSENTE: Final[str] = "ausente"
REJEITADO: Final[str] = "rejeitado"
ERRO_REDE: Final[str] = "erro_rede"

#: Vereditos que **não** fazem o job falhar: ausência é caso normal (CA-028).
STATUS_OK: Final[frozenset[str]] = frozenset({ARQUIVADO, JA_ARQUIVADO, REVISAO_ARQUIVADA, AUSENTE})


class CorpoInvalido(ValueError):
    """O corpo recebido não é o arquivo esperado da fonte (HTML de erro, truncado, outro layout)."""


class ErroDeRede(RuntimeError):
    """A fonte não respondeu depois de todas as tentativas."""


@dataclass(frozen=True)
class Resposta:
    """Resposta crua da fonte, isolada do cliente HTTP para o job ser testável sem rede."""

    url: str
    http_status: int
    corpo: bytes


@dataclass(frozen=True)
class Parsed:
    """Resultado do parse mínimo de validação — não é a camada `processed`."""

    data_ref: date
    n_registros: int
    detalhe: str


@dataclass(frozen=True)
class FonteDiaria:
    """Uma das duas séries de janela rolante arquivadas por este job."""

    nome: str
    destino_raw: str
    prefixo: str
    extensao: str
    formato: str
    encoding: str
    metodo: str
    url: str
    contagem_minima: int
    parser: Callable[[bytes], Parsed]
    referer: str | None = None
    corpo_form: Callable[[date], dict[str, str]] | None = None
    timeout_s: float = 60.0
    max_retries: int = 3

    def url_para(self, dia: date) -> str:
        """URL final do dia (o `ms*.txt` é `AAMMDD`, não `ddmmaa` — §A4.2)."""
        return self.url.format(aammdd=f"{dia:%y%m%d}")

    def nome_arquivo(self, dia: date, vintage: int = 1) -> str:
        """`ms_261009.txt`; a partir do 2º vintage do mesmo dia, `ms_261009__v2.txt`."""
        sufixo = "" if vintage <= 1 else f"__v{vintage}"
        return f"{self.prefixo}_{dia:%y%m%d}{sufixo}.{self.extensao}"

    def diretorio(self, raiz: Path) -> Path:
        return raiz / self.destino_raw


@dataclass(frozen=True)
class ResultadoDia:
    """Veredito de uma fonte num dia — é o que vai para o log de execução e para o relatório."""

    fonte: str
    dia: date
    status: str
    mensagem: str
    arquivo: Path | None = None
    bytes_recebidos: int = 0
    sha256: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in STATUS_OK


# ── parsers de validação mínima ───────────────────────────────────────────────────────────────────


def _para_float_br(texto: str) -> float | None:
    """Número pt-BR da ANBIMA (`13,1049`, `-4,58E-02`) → float. Campo vazio → ``None``."""
    limpo = texto.strip().replace(".", "").replace(",", ".")
    if not limpo:
        return None
    try:
        return float(limpo)
    except ValueError as exc:
        raise CorpoInvalido(f"valor não numérico onde se esperava número pt-BR: {texto!r}") from exc


def _data_br(texto: str) -> date:
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except ValueError as exc:
        raise CorpoInvalido(f"data fora do padrão dd/mm/aaaa: {texto!r}") from exc


def parse_ms(corpo: bytes) -> Parsed:
    """Parse de validação do `ms{AAMMDD}.txt` (CA-029).

    Separador ``@``, ``skiprows=2``, ``encoding='latin-1'``, decimal vírgula, e os 5 títulos
    (LTN, LFT, NTN-B, NTN-C, NTN-F) presentes. Levanta `CorpoInvalido` em qualquer desvio —
    nunca "conserta" o arquivo.
    """
    try:
        tabela = pd.read_csv(
            io.BytesIO(corpo),
            sep="@",
            skiprows=2,
            encoding="latin-1",
            decimal=",",
            dtype={"Titulo": "string"},
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise CorpoInvalido(f"não é um ms*.txt separado por '@': {exc}") from exc

    faltando_col = [c for c in MS_COLUNAS_MINIMAS if c not in tabela.columns]
    if faltando_col:
        raise CorpoInvalido(f"colunas ausentes no ms*.txt: {faltando_col}")

    titulos = {t.strip() for t in tabela["Titulo"].dropna().tolist()}
    faltando_tit = sorted(TITULOS_ESPERADOS - titulos)
    if faltando_tit:
        raise CorpoInvalido(f"títulos esperados ausentes: {faltando_tit} (achei {sorted(titulos)})")
    estranhos = sorted(titulos - TITULOS_ESPERADOS)
    if estranhos:
        raise CorpoInvalido(f"títulos desconhecidos no ms*.txt: {estranhos}")

    datas = {int(v) for v in tabela["Data Referencia"].dropna().tolist()}
    if len(datas) != 1:
        raise CorpoInvalido(f"ms*.txt deveria ter 1 'Data Referencia', achei {sorted(datas)}")
    bruta = str(datas.pop())
    try:
        data_ref = datetime.strptime(bruta, "%Y%m%d").date()
    except ValueError as exc:
        raise CorpoInvalido(f"'Data Referencia' fora do padrão AAAAMMDD: {bruta!r}") from exc

    return Parsed(
        data_ref=data_ref,
        n_registros=len(tabela),
        detalhe=f"{len(tabela)} vencimentos, títulos {sorted(titulos)}",
    )


def _vertices_ettj(linhas: Sequence[str]) -> list[int]:
    """Vértices em dias úteis do bloco "ETTJ Inflação Implicita" (ponto = separador de milhar)."""
    vertices: list[int] = []
    dentro = False
    for linha in linhas:
        if linha.lower().startswith("vertices;ettj"):
            dentro = True
            continue
        if not dentro:
            continue
        if not linha.strip():
            break
        bruto = linha.split(";")[0].strip().replace(".", "")
        if not bruto.isdigit():
            break
        vertices.append(int(bruto))
    return vertices


def parse_curva_zero(corpo: bytes) -> Parsed:
    """Parse de validação do `saida=csv` do `CZ-down.asp` (§A5.1).

    ISO-8859-1, separador ``;``, decimal vírgula, notação científica `E-02`, três blocos no mesmo
    arquivo. Exige os betas de PREFIXADOS **e** IPCA e a curva de vértices.
    """
    try:
        texto = corpo.decode("latin-1")
    except UnicodeDecodeError as exc:  # pragma: no cover - latin-1 aceita qualquer byte
        raise CorpoInvalido(f"corpo não decodifica em latin-1: {exc}") from exc

    linhas = [linha.rstrip() for linha in texto.splitlines()]
    if not linhas or ";" not in linhas[0]:
        raise CorpoInvalido(
            "primeira linha não é o cabeçalho `dd/mm/aaaa;Beta 1;...` da Curva Zero"
        )

    cabecalho = linhas[0].split(";")
    data_ref = _data_br(cabecalho[0])
    rotulos = [c.strip() for c in cabecalho[1:5]]
    if rotulos != ["Beta 1", "Beta 2", "Beta 3", "Beta 4"]:
        raise CorpoInvalido(f"cabeçalho de betas inesperado: {rotulos}")

    betas: dict[str, list[float | None]] = {}
    for linha in linhas[1:]:
        if not linha.strip():
            break
        campos = linha.split(";")
        grupo = campos[0].strip().upper()
        if grupo in {"PREFIXADOS", "IPCA"}:
            betas[grupo] = [_para_float_br(c) for c in campos[1:7]]

    faltando = sorted({"PREFIXADOS", "IPCA"} - betas.keys())
    if faltando:
        raise CorpoInvalido(f"blocos de parâmetros Svensson ausentes: {faltando}")
    for grupo, valores in betas.items():
        if len(valores) != 6 or any(v is None for v in valores):
            raise CorpoInvalido(f"bloco {grupo} sem os 6 parâmetros (4 betas + 2 lambdas)")

    vertices = _vertices_ettj(linhas)
    if len(vertices) < 20:
        raise CorpoInvalido(f"só {len(vertices)} vértices de ETTJ — esperado >= 20 (252..6930+)")

    return Parsed(
        data_ref=data_ref,
        n_registros=len(vertices),
        detalhe=(
            f"betas PREFIXADOS+IPCA, {len(vertices)} vértices "
            f"de {vertices[0]} a {vertices[-1]} dias úteis"
        ),
    )


# ── as duas fontes ────────────────────────────────────────────────────────────────────────────────

FONTE_MS: Final[FonteDiaria] = FonteDiaria(
    nome="anbima_ms",
    destino_raw="data/raw/anbima-ms",
    prefixo="ms",
    extensao="txt",
    formato="txt",
    encoding="latin-1",
    metodo="GET",
    url="https://www.anbima.com.br/informacoes/merc-sec/arqs/ms{aammdd}.txt",
    referer="https://www.anbima.com.br/informacoes/merc-sec/default.asp",
    contagem_minima=20,
    parser=parse_ms,
)

FONTE_CZ: Final[FonteDiaria] = FonteDiaria(
    nome="anbima_ettj_cz",
    destino_raw="data/raw/anbima-ettj",
    prefixo="cz",
    # `saida=xls` NÃO é Excel: é HTML <table> servido como application/vnd.ms-excel (§A5.1).
    extensao="csv",
    formato="csv",
    encoding="latin-1",
    metodo="POST",
    url="https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp",
    referer="https://www.anbima.com.br/informacoes/est-termo/CZ.asp",
    contagem_minima=20,
    parser=parse_curva_zero,
    corpo_form=lambda dia: {"Idioma": "PT", "Dt_Ref": f"{dia:%d/%m/%Y}", "saida": "csv"},
)

FONTES: Final[tuple[FonteDiaria, ...]] = (FONTE_MS, FONTE_CZ)
FONTES_POR_APELIDO: Final[dict[str, FonteDiaria]] = {"ms": FONTE_MS, "cz": FONTE_CZ}


def extractor_configs() -> tuple[Any, ...]:
    """Espelha as duas fontes no `ExtractorConfig` de `packages/shared/schemas/`.

    Import preguiçoso: `series_catalog` importa **pandera**, que não precisa estar instalado para
    o job rodar. Serve de teste de contrato (`ausencia_e_caso_normal=True`) e de ponto único de
    verdade quando F-001 generalizar a configuração dos extratores.
    """
    from packages.shared.schemas.series_catalog import ExtractorConfig, Fonte

    return tuple(
        ExtractorConfig(
            nome=fonte.nome,
            fonte=Fonte.ANBIMA_WEB,
            series_ids=(fonte.nome,),
            base_url=fonte.url,
            formato=fonte.formato,
            encoding=fonte.encoding,
            requer_user_agent_browser=True,
            contagem_minima_esperada=fonte.contagem_minima,
            destino_raw=fonte.destino_raw,
            ausencia_e_caso_normal=True,
            timeout_s=fonte.timeout_s,
            max_retries=fonte.max_retries,
        )
        for fonte in FONTES
    )


# ── camada HTTP mínima (temporária, ver TODO(F-001) no topo) ─────────────────────────────────────


def _sessao() -> requests.Session:
    sessao = requests.Session()
    sessao.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return sessao


def baixar(fonte: FonteDiaria, dia: date, sessao: requests.Session | None = None) -> Resposta:
    """GET/POST com UA de browser, timeout e retry simples com backoff."""
    cliente = sessao or _sessao()
    url = fonte.url_para(dia)
    cabecalhos = {"Referer": fonte.referer} if fonte.referer else {}
    ultimo = "nenhuma tentativa"
    for tentativa in range(1, fonte.max_retries + 1):
        try:
            if fonte.metodo == "POST":
                corpo_form = fonte.corpo_form(dia) if fonte.corpo_form else None
                resposta = cliente.post(
                    url, data=corpo_form, headers=cabecalhos, timeout=fonte.timeout_s
                )
            else:
                resposta = cliente.get(url, headers=cabecalhos, timeout=fonte.timeout_s)
        except requests.RequestException as exc:
            ultimo = f"{type(exc).__name__}: {exc}"
        else:
            if resposta.status_code < 500:
                return Resposta(url=url, http_status=resposta.status_code, corpo=resposta.content)
            ultimo = f"HTTP {resposta.status_code}"
        if tentativa < fonte.max_retries:
            time.sleep(min(2**tentativa, 8))
    raise ErroDeRede(
        f"{url} não respondeu em {fonte.max_retries} tentativas — último erro: {ultimo}"
    )


def detectar_corpo_suspeito(corpo: bytes) -> str | None:
    """Guarda contra "HTTP 200 com corpo errado" (Anti-SPEC §10.1.5), por magic bytes.

    Devolve a descrição do problema, ou ``None`` se o corpo parece o arquivo de texto esperado.
    """
    if corpo[:4] == b"PK\x03\x04":
        return "corpo é ZIP/OOXML (magic bytes 'PK'), não o arquivo de texto esperado"
    cabeca = corpo[:600].lstrip(b"\xef\xbb\xbf").lstrip()
    if cabeca[:1] == b"<":
        return "corpo começa com '<' — é HTML/XML (página de erro, ou `saida=xls`, que é HTML)"
    minuscula = cabeca.lower()
    for marca in (b"<html", b"<table", b"<!doctype", b"<script"):
        if marca in minuscula:
            return f"corpo contém {marca.decode()!r} — é HTML, não o arquivo de dados"
    return None


# ── arquivamento ──────────────────────────────────────────────────────────────────────────────────


def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def caminho_manifest(alvo: Path) -> Path:
    """`ms_261009.txt` → `ms_261009.txt.manifest.json`."""
    return alvo.with_name(alvo.name + ".manifest.json")


def _gravar_atomico(alvo: Path, dados: bytes) -> None:
    temporario = alvo.with_name(alvo.name + ".tmp")
    temporario.write_bytes(dados)
    os.replace(temporario, alvo)


def _gravar_manifest(alvo: Path, manifest: dict[str, Any]) -> None:
    destino = caminho_manifest(alvo)
    texto = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _gravar_atomico(destino, texto.encode("utf-8"))


def _resultado(
    fonte: FonteDiaria, dia: date, status: str, mensagem: str, **extra: Any
) -> ResultadoDia:
    return ResultadoDia(fonte=fonte.nome, dia=dia, status=status, mensagem=mensagem, **extra)


def arquivar_dia(
    fonte: FonteDiaria,
    dia: date,
    raiz: Path = REPO_ROOT,
    buscar: Callable[[FonteDiaria, date], Resposta] = baixar,
) -> ResultadoDia:
    """Baixa, valida e arquiva um dia de uma fonte. Idempotente (CA-027); ausência é ok (CA-028)."""
    try:
        resposta = buscar(fonte, dia)
    except ErroDeRede as exc:
        return _resultado(
            fonte,
            dia,
            ERRO_REDE,
            f"{exc}. Ação: confira a conectividade e rode de novo HOJE — "
            f"a janela rolante é de ~{JANELA_ROLANTE_DIAS_UTEIS} dias úteis.",
        )

    bytes_recebidos = len(resposta.corpo)

    # Ausência: feriado, dia sem divulgação, atraso declarado da ANBIMA, ou dia fora da janela.
    if resposta.http_status == 404 or not resposta.corpo.strip():
        return _resultado(
            fonte,
            dia,
            AUSENTE,
            f"sem divulgação (HTTP {resposta.http_status}, {bytes_recebidos} B) — "
            "caso normal (feriado, atraso da apuração ou dia fora da janela rolante)",
            bytes_recebidos=bytes_recebidos,
        )

    if resposta.http_status != 200:
        return _resultado(
            fonte,
            dia,
            REJEITADO,
            f"HTTP {resposta.http_status} em {resposta.url} com corpo de {bytes_recebidos} B. "
            "Ação: abra a URL no browser; se o endpoint mudou, atualize `FONTE_*` e a fixture.",
            bytes_recebidos=bytes_recebidos,
        )

    suspeito = detectar_corpo_suspeito(resposta.corpo)
    if suspeito is not None:
        return _resultado(
            fonte,
            dia,
            REJEITADO,
            f"corpo inválido com HTTP 200: {suspeito}. Nada foi gravado. "
            f"Ação: confira {resposta.url} com UA de browser; se a ANBIMA trocou o formato, "
            "atualize o parser e grave nova fixture (runbook job-diario-anbima.md).",
            bytes_recebidos=bytes_recebidos,
        )

    try:
        analisado = fonte.parser(resposta.corpo)
    except CorpoInvalido as exc:
        return _resultado(
            fonte,
            dia,
            REJEITADO,
            f"parse de validação falhou: {exc}. Nada foi gravado. "
            "Ação: compare com a fixture em tests/fixtures/ e abra /fast-fix classe B.",
            bytes_recebidos=bytes_recebidos,
        )

    if analisado.data_ref != dia:
        return _resultado(
            fonte,
            dia,
            REJEITADO,
            f"a fonte devolveu data de referência {analisado.data_ref.isoformat()} para o pedido "
            f"de {dia.isoformat()} — eco de outro dia útil, não o dia pedido. Nada foi gravado.",
            bytes_recebidos=bytes_recebidos,
        )

    if analisado.n_registros < fonte.contagem_minima:
        return _resultado(
            fonte,
            dia,
            REJEITADO,
            f"apenas {analisado.n_registros} registros (mínimo esperado {fonte.contagem_minima}) — "
            "truncamento silencioso. Nada foi gravado; repita mais tarde.",
            bytes_recebidos=bytes_recebidos,
        )

    sha = _sha256(resposta.corpo)
    diretorio = fonte.diretorio(raiz)
    diretorio.mkdir(parents=True, exist_ok=True)

    vintage = 1
    alvo = diretorio / fonte.nome_arquivo(dia, vintage)
    while alvo.exists():
        if _sha256(alvo.read_bytes()) == sha:
            return _resultado(
                fonte,
                dia,
                JA_ARQUIVADO,
                f"já arquivado em {alvo.name} com o mesmo sha256 — nada reescrito",
                arquivo=alvo,
                bytes_recebidos=bytes_recebidos,
                sha256=sha,
            )
        vintage += 1
        alvo = diretorio / fonte.nome_arquivo(dia, vintage)

    status = ARQUIVADO if vintage == 1 else REVISAO_ARQUIVADA
    _gravar_atomico(alvo, resposta.corpo)
    _gravar_manifest(
        alvo,
        {
            "url": resposta.url,
            "data_ref": dia.isoformat(),
            "sha256": sha,
            "bytes": bytes_recebidos,
            "collected_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "fonte": fonte.nome,
            "arquivo": alvo.name,
            "formato": fonte.formato,
            "encoding": fonte.encoding,
            "http_status": resposta.http_status,
            "metodo": fonte.metodo,
            "registros": analisado.n_registros,
            "detalhe": analisado.detalhe,
            "status": status,
            "vintage": vintage,
            "janela_rolante_dias_uteis": JANELA_ROLANTE_DIAS_UTEIS,
        },
    )
    mensagem = (
        f"arquivado {alvo.name} ({bytes_recebidos} B, {analisado.detalhe})"
        if status == ARQUIVADO
        else (
            f"a fonte revisou {dia.isoformat()}: conteúdo diferente do já arquivado — "
            f"gravado como vintage {vintage} em {alvo.name}, original intacto"
        )
    )
    return _resultado(
        fonte,
        dia,
        status,
        mensagem,
        arquivo=alvo,
        bytes_recebidos=bytes_recebidos,
        sha256=sha,
    )


def dias_uteis_retroativos(referencia: date, quantos: int) -> list[date]:
    """Os `quantos` dias de semana até `referencia` (inclusive), do mais antigo ao mais novo.

    Feriado não é modelado de propósito: ausência é caso normal (CA-028) e um calendário de feriados
    errado esconderia dia publicado. A ANBIMA não publica em fim de semana, então sábado e domingo
    são descartados para não gastar requisição.
    """
    if quantos < 1:
        raise ValueError("`quantos` deve ser >= 1")
    dias: list[date] = []
    cursor = referencia
    while len(dias) < quantos:
        if cursor.weekday() < 5:
            dias.append(cursor)
        cursor -= timedelta(days=1)
    return sorted(dias)


def registrar_log(resultados: Sequence[ResultadoDia], raiz: Path = REPO_ROOT) -> Path:
    """Anexa 1 linha por fonte × dia ao log de execução (`infra-ops.md` §2.2)."""
    destino = raiz / LOG_RELATIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    agora = datetime.now(UTC).isoformat(timespec="seconds")
    linhas = [
        f"{agora}\t{r.fonte}\t{r.dia.isoformat()}\t{r.status}\t{r.bytes_recebidos}B\t{r.mensagem}\n"
        for r in resultados
    ]
    with destino.open("a", encoding="utf-8") as arquivo:
        arquivo.writelines(linhas)
    return destino


def executar(
    dias: Sequence[date],
    fontes: Sequence[FonteDiaria] = FONTES,
    raiz: Path = REPO_ROOT,
    buscar: Callable[[FonteDiaria, date], Resposta] | None = None,
) -> list[ResultadoDia]:
    """Arquiva `fontes` × `dias`, do dia mais antigo ao mais novo (modo recuperação do runbook)."""
    if buscar is None:
        buscar = functools.partial(baixar, sessao=_sessao())
    resultados: list[ResultadoDia] = []
    for dia in sorted(dias):
        for fonte in fontes:
            resultados.append(arquivar_dia(fonte, dia, raiz=raiz, buscar=buscar))
    return resultados


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.jobs.anbima_daily",
        description=(
            "Arquiva as séries de janela rolante da ANBIMA (taxas indicativas `ms*.txt` e "
            "Curva Zero Svensson) em data/raw/, de forma idempotente."
        ),
    )
    parser.add_argument(
        "--date",
        dest="data",
        default=None,
        help="data de referência AAAA-MM-DD (default: hoje). Dia sem divulgação é caso normal.",
    )
    parser.add_argument(
        "--backfill",
        type=int,
        default=1,
        metavar="N",
        help=(
            "arquiva os N dias úteis até --date, do mais antigo ao mais novo. "
            f"A janela da ANBIMA é de ~{JANELA_ROLANTE_DIAS_UTEIS} dias úteis; acima disso o dado "
            "não existe mais na fonte (não é backfill de histórico — Anti-SPEC §10.1.3)."
        ),
    )
    parser.add_argument(
        "--fonte",
        choices=("ms", "cz", "todas"),
        default="todas",
        help="limita a execução a uma das fontes (default: todas).",
    )
    parser.add_argument(
        "--out-root",
        default=None,
        help="raiz onde `data/raw/...` é criado (default: raiz do repositório).",
    )
    return parser


def _console_tolerante_a_acento() -> None:
    """O console do Windows abre em cp1252: sem isto, um acento no log derruba o job agendado."""
    for fluxo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada do CLI. 0 = ok (inclui ausência); 1 = falha acionável; 2 = uso inválido."""
    _console_tolerante_a_acento()
    args = _construir_parser().parse_args(argv)

    if args.backfill < 1:
        print("ERRO: --backfill precisa ser >= 1", file=sys.stderr)
        return 2
    if args.backfill > 40:
        print(
            "ERRO: --backfill > 40 dias úteis não faz sentido — a janela da ANBIMA é de ~20 d.u. e "
            "fora dela o dado não existe (Anti-SPEC §10.1.3: janela rolante não é backfill).",
            file=sys.stderr,
        )
        return 2
    try:
        referencia = date.fromisoformat(args.data) if args.data else date.today()
    except ValueError:
        print(f"ERRO: --date inválida: {args.data!r} (use AAAA-MM-DD)", file=sys.stderr)
        return 2

    raiz = Path(args.out_root).resolve() if args.out_root else REPO_ROOT
    fontes = FONTES if args.fonte == "todas" else (FONTES_POR_APELIDO[args.fonte],)
    dias = dias_uteis_retroativos(referencia, args.backfill)

    print(
        f"ANBIMA job diario: {len(dias)} dia(s) util(eis) de {dias[0].isoformat()} a "
        f"{dias[-1].isoformat()} x {len(fontes)} fonte(s) -> {raiz / 'data/raw'}"
    )
    resultados = executar(dias, fontes=fontes, raiz=raiz)
    registrar_log(resultados, raiz=raiz)

    for resultado in resultados:
        print(
            f"  {resultado.dia.isoformat()}  {resultado.fonte:<14} {resultado.status:<18} "
            f"{resultado.mensagem}"
        )

    contagem: dict[str, int] = {}
    for resultado in resultados:
        contagem[resultado.status] = contagem.get(resultado.status, 0) + 1
    print("RESUMO: " + ", ".join(f"{k}={v}" for k, v in sorted(contagem.items())))

    falhas = [r for r in resultados if not r.ok]
    if falhas:
        print(
            f"FALHA: {len(falhas)} de {len(resultados)} verificações não arquivaram. "
            "Resolva HOJE — runbook: docs/wiki/runbooks/job-diario-anbima.md",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
