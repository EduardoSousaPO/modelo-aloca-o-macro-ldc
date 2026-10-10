"""Normalizadores de texto, número, data e formato binário — **um** de cada, para todo o pipeline.

Existe porque a pesquisa catalogou quatro pegadinhas que, repetidas extrator a extrator, viram
número errado no comitê (`docs/research/fontes-de-dados.md §RISCOS DE EXTRAÇÃO`):

- **R10** — latin-1 (ANBIMA `ms`/`CZ`, Tesouro, CVM, COTAHIST) contra UTF-8 (IBGE, Olinda, XLSX
  do S3) → `ler_texto` com `encoding` **obrigatório** + `ENCODING_POR_FONTE`.
- **R11** — o `.xls` do S3 da ANBIMA é **XLSX** e o `.xls` do `CZ-down.asp` é **HTML `<table>`** →
  `detectar_formato` / `exigir_formato` por magic bytes.
- **R12** — `ms{AAMMDD}`, PTAX do Olinda em `MM-DD-YYYY`, SGS em `dd/mm/aaaa`, COTAHIST em
  `AAAAMMDD` → `para_data` com `FormatoData` explícito.
- **R13** — `"38.484,84"` (B3), `6.930` (vértice do `CZ`), `"0.82"` (JSON do SGS, ponto decimal) →
  `para_float_ptbr` / `para_float_ponto_decimal`.
- **R14** — a coluna `Índice` do S3 alterna `IMA-B` e `IMA - B` → `normalizar_rotulo`.

Regras que o módulo faz valer, e que nenhum extrator deve reimplementar:

- **encoding nunca tem default.** Anti-SPEC §10.4.26: o default do locale (cp1252 no Windows)
  corrompe acento em silêncio. `ler_texto(conteudo, encoding)` exige o argumento, e lê em modo
  `strict` — mojibake vira exceção, não dado.
- **célula ausente é `None`, nunca `0`.** Anti-SPEC §10.1.4.
- **número em convenção errada levanta.** `para_float_ptbr("0.82")` não devolve `82.0`: levanta
  `NumeroNaoReconhecido`. É o guarda contra o erro de escala, que passa por qualquer teste de
  "o script rodou".
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from enum import StrEnum
from numbers import Real
from pathlib import Path

from apps.pipeline.common.errors import (
    DataNaoReconhecida,
    ErroDeExtracao,
    FormatoInesperado,
    NumeroNaoReconhecido,
)

# ─────────────────────────────────────────────────────────────────────────────
# Encoding (R10) — Anti-SPEC §10.4.26
# ─────────────────────────────────────────────────────────────────────────────

LATIN_1 = "latin-1"
UTF_8 = "utf-8"

#: Encoding **medido** por fonte na pesquisa (`fontes-de-dados.md` R10). Serve como default do
#: `ExtractorConfig.encoding` de cada extrator — não como fallback em tempo de leitura.
#: Exceção conhecida fora do enum `Fonte`: o COTAHIST da B3 (arquivo ZIP/TXT posicional) é
#: latin-1, embora a API JSON da B3 (`B3_API`) seja UTF-8.
ENCODING_POR_FONTE: dict[str, str] = {
    "BCB_SGS": UTF_8,
    "BCB_OLINDA": UTF_8,
    "IBGE_SIDRA": UTF_8,
    "ANBIMA_S3": UTF_8,  # XLSX (OOXML) — o XML interno é UTF-8
    "ANBIMA_WEB": LATIN_1,  # ms*.txt e CZ-down.asp
    "TESOURO_CKAN": LATIN_1,
    "B3_API": UTF_8,
    "TEVA_GCS": UTF_8,
    "YAHOO": UTF_8,
    "MSCI": UTF_8,
    "FRED": UTF_8,
    "IPEADATA": UTF_8,
    "CVM": LATIN_1,
}


def ler_texto(conteudo: bytes, encoding: str) -> str:
    """Decodifica bytes com `encoding` **explícito** e em modo `strict`.

    `encoding` é posicional e sem default de propósito: é o que torna impossível herdar o default
    do locale (Anti-SPEC §10.4.26). Modo `strict` transforma encoding errado em
    `UnicodeDecodeError` em vez de mojibake silencioso.
    """
    return conteudo.decode(encoding, errors="strict")


def ler_texto_de_arquivo(caminho: Path, *, encoding: str) -> str:
    """Lê um arquivo de texto com `encoding` obrigatório (keyword-only, sem default)."""
    return ler_texto(Path(caminho).read_bytes(), encoding)


# ─────────────────────────────────────────────────────────────────────────────
# Formato por magic bytes (R11)
# ─────────────────────────────────────────────────────────────────────────────


class FormatoDetectado(StrEnum):
    """O que os primeiros bytes dizem que o arquivo é — independente da extensão."""

    VAZIO = "vazio"
    XLSX = "xlsx"  # PK\x03\x04 — OOXML (o `.xls` do S3 da ANBIMA cai aqui)
    ZIP = "zip"  # PK, mas vazio/spanned (COTAHIST, pacotes da CVM)
    XLS_BIFF = "xls_biff"  # OLE2 — XLS legado de verdade; nenhuma fonte do projeto usa
    HTML = "html"  # `<` — o `.xls` do CZ-down.asp e as páginas de erro do SGS
    JSON = "json"  # `[` ou `{`
    PDF = "pdf"
    TEXTO = "texto"  # CSV / TXT posicional / TSV


_ASSINATURAS: tuple[tuple[bytes, FormatoDetectado], ...] = (
    (b"PK\x03\x04", FormatoDetectado.XLSX),
    (b"PK\x05\x06", FormatoDetectado.ZIP),
    (b"PK\x07\x08", FormatoDetectado.ZIP),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", FormatoDetectado.XLS_BIFF),
    (b"%PDF-", FormatoDetectado.PDF),
)

_ESPACOS = b" \t\r\n\x0b\x0c\xef\xbb\xbf"  # inclui BOM de UTF-8


def detectar_formato(conteudo: bytes) -> FormatoDetectado:
    """Classifica o corpo pelos magic bytes — **a extensão do arquivo é ignorada** (R11).

    Dois arquivos deste projeto mentem na extensão: `IMAB-HISTORICO.xls` do S3 da ANBIMA é XLSX
    (`PK\\x03\\x04`) e o `saida=xls` do `CZ-down.asp` é HTML `<table>`. Decidir o leitor por
    extensão é o caminho curto para `xlrd` quebrando ou `read_excel` engolindo HTML.
    """
    if not conteudo:
        return FormatoDetectado.VAZIO
    for assinatura, formato in _ASSINATURAS:
        if conteudo.startswith(assinatura):
            return formato
    inicio = conteudo.lstrip(_ESPACOS)
    if not inicio:
        return FormatoDetectado.VAZIO
    if inicio.startswith(b"<"):
        return FormatoDetectado.HTML
    if inicio[:1] in (b"[", b"{"):
        return FormatoDetectado.JSON
    return FormatoDetectado.TEXTO


def exigir_formato(
    conteudo: bytes,
    esperado: FormatoDetectado | tuple[FormatoDetectado, ...],
    *,
    origem: str,
) -> FormatoDetectado:
    """Levanta `FormatoInesperado` quando os magic bytes não batem com o esperado.

    `origem` entra na mensagem (URL ou caminho) para o log não ficar com "formato errado" sem
    dizer de quê.
    """
    aceitos = (esperado,) if isinstance(esperado, FormatoDetectado) else esperado
    detectado = detectar_formato(conteudo)
    if detectado not in aceitos:
        nomes = ", ".join(sorted(f.value for f in aceitos))
        msg = (
            f"{origem}: magic bytes indicam '{detectado.value}', esperado um de [{nomes}] "
            f"(primeiros bytes: {conteudo[:8]!r})"
        )
        raise FormatoInesperado(msg)
    return detectado


# ─────────────────────────────────────────────────────────────────────────────
# Número (R13)
# ─────────────────────────────────────────────────────────────────────────────

#: Marcadores de ausência usados pelas fontes. Viram `None` — **nunca** `0` (Anti-SPEC §10.1.4).
AUSENCIAS: frozenset[str] = frozenset(
    {"", "-", "--", "...", "..", ".", "nd", "n/d", "n/a", "na", "nan", "null", "none", "s/i"}
)

# pt-BR: milhar com ponto em grupos de 3, decimal com vírgula, expoente opcional (o `CZ` da ANBIMA
# serve Svensson como `-4,58301615075328E-02`).
_PTBR = re.compile(r"^[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?(?:[Ee][+-]?\d+)?$")
# Ponto decimal (JSON do SGS, Yahoo, MSCI, FRED): vírgula é proibida aqui.
_PONTO_DECIMAL = re.compile(r"^[+-]?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?$")


def _e_numero_nativo(valor: object) -> bool:
    """`True` para número já tipado (`int`, `float`, escalar do numpy) — **nunca** para `bool`.

    `numbers.Real` cobre `int`, `float` e os escalares do numpy (`float32/64`, `int32/64`), que
    `pandas` e `openpyxl` entregam. `bool` é `Real` em Python e é excluído de propósito: `True`
    valendo `1.0` numa série é sempre erro de coluna.
    """
    return isinstance(valor, Real) and not isinstance(valor, bool)


def _numero_nativo(valor: object) -> float | None:
    """Converte número **já tipado** direto em `float`, sem passar por texto (QA-01).

    Este é o caminho obrigatório para o que vem de `openpyxl` e de `pandas`: ali o número já está
    tipado e **nenhuma convenção textual se aplica**. Mandar um `float` pelo parser de string era o
    bug QA-01: `repr(1.234)` é `'1.234'`, que em pt-BR se lê como milhar e devolvia `1234.0` — erro
    de escala de 1000x, silencioso. `NaN` (ausência do pandas) vira `None`, nunca `0`
    (Anti-SPEC §10.1.4); infinito levanta, porque não é observação de série.
    """
    numero = float(valor)  # type: ignore[arg-type]
    if math.isnan(numero):
        return None
    if math.isinf(numero):
        msg = f"valor infinito não é observação de série: {valor!r}"
        raise NumeroNaoReconhecido(msg)
    return numero


def _texto_de_entrada(
    valor: object,
    *,
    funcao: str,
    erro: type[ErroDeExtracao] = NumeroNaoReconhecido,
) -> str | None:
    """String limpa, ou `None` quando o valor representa ausência.

    Só aceita `str`: qualquer outro tipo levanta em vez de ser convertido por `str(valor)`. A
    conversão implícita é o que permitia um número tipado chegar ao parser textual (QA-01), e vale
    para `Decimal` e companhia — que não são `numbers.Real` e seriam estringificados em silêncio.
    """
    if isinstance(valor, bool):  # bool é int em Python; aqui é sempre erro de chamada
        msg = f"valor booleano não é número de série: {valor!r}"
        raise NumeroNaoReconhecido(msg)
    if not isinstance(valor, str):
        msg = (
            f"{funcao} aceita str, int, float ou None — recebeu {type(valor).__name__} "
            f"({valor!r}). Converta explicitamente, para a conversão não escolher a convenção "
            f"numérica por você"
        )
        raise erro(msg)
    texto = valor.strip().replace("\xa0", "").replace(" ", "")
    if texto.lower() in AUSENCIAS:
        return None
    return texto


def para_float_ptbr(valor: object, *, origem: str = "") -> float | None:
    """**O** normalizador de número pt-BR do projeto (R13, CA-035).

    `"38.484,84"` → `38484.84` · `"6.930"` → `6930.0` · `"0,59"` → `0.59` ·
    `"-4,58301615075328E-02"` → `-0.0458...` · `""`/`"-"`/`"ND"` → `None`.

    Convenção: **todo ponto é separador de milhar** e a vírgula é o decimal. É o que a fonte quer
    dizer — o vértice `6.930` da Curva Zero é 6.930 dias corridos, não 6,93. A consequência é que
    um valor pt-BR sem casa decimal e com milhar é indistinguível de um decimal en-US: por isso
    `"0.82"` (JSON do SGS) **levanta** em vez de virar `82.0`, e séries com ponto decimal usam
    `para_float_ponto_decimal`.

    **Número já tipado passa direto**: `para_float_ptbr(1.234)` é `1.234`, não `1234.0`. A
    convenção pt-BR descreve *texto*; quando `openpyxl` ou `pandas` já entregaram um `float`, não
    há convenção a interpretar (QA-01).
    """
    if valor is None:
        return None
    if _e_numero_nativo(valor):
        return _numero_nativo(valor)
    texto = _texto_de_entrada(valor, funcao="para_float_ptbr")
    if texto is None:
        return None
    if not _PTBR.fullmatch(texto):
        sufixo = f" ({origem})" if origem else ""
        msg = (
            f"{texto!r} não é número pt-BR{sufixo}: esperado milhar com '.' em grupos de 3 e "
            f"decimal com ','. Fonte com ponto decimal usa para_float_ponto_decimal()"
        )
        raise NumeroNaoReconhecido(msg)
    return float(texto.replace(".", "").replace(",", "."))


def para_float_ponto_decimal(valor: object, *, origem: str = "") -> float | None:
    """Número com **ponto decimal e sem milhar** — JSON do SGS, Yahoo, MSCI, FRED.

    `"0.82"` → `0.82`. Vírgula levanta: quem tem vírgula é pt-BR e usa `para_float_ptbr`.
    Número já tipado passa direto, igual a `para_float_ptbr` (QA-01).
    """
    if valor is None:
        return None
    if _e_numero_nativo(valor):
        return _numero_nativo(valor)
    texto = _texto_de_entrada(valor, funcao="para_float_ponto_decimal")
    if texto is None:
        return None
    if not _PONTO_DECIMAL.fullmatch(texto):
        sufixo = f" ({origem})" if origem else ""
        msg = (
            f"{texto!r} não é número com ponto decimal{sufixo}: separador de milhar e vírgula "
            f"não são aceitos aqui. Fonte pt-BR usa para_float_ptbr()"
        )
        raise NumeroNaoReconhecido(msg)
    return float(texto)


# ─────────────────────────────────────────────────────────────────────────────
# Data (R12)
# ─────────────────────────────────────────────────────────────────────────────


class FormatoData(StrEnum):
    """Formato de data **por fonte** — nunca inferido, sempre declarado (R12).

    `01/02/2006` é 1º de fevereiro no SGS (`dd/mm/aaaa`) e 2 de janeiro na PTAX do Olinda
    (`MM-DD-YYYY`). Inferir é escolher silenciosamente entre duas respostas certas.
    """

    DD_MM_AAAA = "%d/%m/%Y"  # BCB SGS (json e csv), ANBIMA S3 (coluna Data)
    DD_MM_AA = "%d/%m/%y"
    AAAAMMDD = "%Y%m%d"  # ANBIMA ms*.txt (Data Referencia/Base/Vencimento), COTAHIST
    AAMMDD = "%y%m%d"  # nome do arquivo ms{AAMMDD}.txt
    MM_DD_AAAA = "%m-%d-%Y"  # PTAX via Olinda
    ISO = "%Y-%m-%d"
    ISO_DATETIME = "%Y-%m-%dT%H:%M:%S"


def para_data(valor: object, formato: FormatoData, *, origem: str = "") -> date | None:
    """Converte para `date` com o formato **declarado**; ausência vira `None`, nunca "hoje".

    Levanta `DataNaoReconhecida` quando a string não casa — inclusive quando casaria em outro
    formato, que é exatamente a armadilha `01/02` × `02/01` do R12.

    Aceita número **inteiro** tipado (`openpyxl` e `pandas` entregam `20261008` como número numa
    coluna `Data Referencia`); fração levanta, porque não existe data com casa decimal.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if valor is None:
        return None
    if _e_numero_nativo(valor):
        numero = float(valor)  # type: ignore[arg-type]
        if math.isnan(numero):
            return None
        if not numero.is_integer():
            msg = f"{valor!r} não é data: número com casa decimal, formato {formato.name}"
            raise DataNaoReconhecida(msg)
        texto: str | None = str(int(numero))
    else:
        texto = _texto_de_entrada(valor, funcao="para_data", erro=DataNaoReconhecida)
    if texto is None:
        return None
    try:
        # Data civil, sem fuso: o índice temporal do projeto é tz-naive (`AGENTS.md §19`).
        return datetime.strptime(texto, formato.value).date()
    except ValueError as exc:
        sufixo = f" ({origem})" if origem else ""
        msg = f"{texto!r} não é data no formato {formato.name} = '{formato.value}'{sufixo}"
        raise DataNaoReconhecida(msg) from exc


# ─────────────────────────────────────────────────────────────────────────────
# Rótulo (R14)
# ─────────────────────────────────────────────────────────────────────────────

_ESPACOS_TEXTO = re.compile(r"\s+")


def normalizar_rotulo(valor: object) -> str:
    """Colapsa rótulo instável da fonte: `"IMA - B"` e `"IMA-B"` → `"IMA-B"` (R14, CA-032).

    Remove **todo** espaço em branco (inclusive interno e no-break space) e põe em maiúsculas.
    Não remove hífen nem ponto: `IMA-B 5+` e `IMAB5MAIS` são rótulos diferentes de propósito.
    """
    texto = str(valor).replace("\xa0", " ")
    return _ESPACOS_TEXTO.sub("", texto).upper()
