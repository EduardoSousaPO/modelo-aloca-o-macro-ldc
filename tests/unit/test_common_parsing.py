"""F-001 — normalizadores: número pt-BR, data, encoding e magic bytes.

CAs cobertos aqui: **CA-035** (número pt-BR com ponto de milhar), **CA-030 (pré)** (`.xls` que é
XLSX detectado por magic bytes), **CA-022** (encoding explícito em todo leitor).
Riscos: R10, R11, R12, R13, R14. Anti-SPEC: §10.1.4 (ausência não é `0`), §10.4.26 (encoding).

Nenhum teste deste arquivo toca a rede: tudo vem de `tests/fixtures/common/`, cujas procedências
estão no `README.md` da pasta.
"""

from __future__ import annotations

import ast
import io
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from apps.pipeline.common import parsing
from apps.pipeline.common.errors import (
    DataNaoReconhecida,
    FormatoInesperado,
    NumeroNaoReconhecido,
)
from apps.pipeline.common.parsing import (
    FormatoData,
    FormatoDetectado,
    detectar_formato,
    exigir_formato,
    ler_texto,
    normalizar_rotulo,
    para_data,
    para_float_ponto_decimal,
    para_float_ptbr,
)


@pytest.fixture
def fixtures_common(dir_fixtures: Path) -> Path:
    """`tests/fixtures/common/` — fixtures da infra (procedência no README da pasta)."""
    return dir_fixtures / "common"


# ─────────────────────────────────────────────────────────────────────────────
# CA-035 — número pt-BR com ponto de milhar converte certo
# ─────────────────────────────────────────────────────────────────────────────


def test_ca035_numero_ptbr_com_ponto_de_milhar_converte_certo() -> None:
    """CA-035: `"38.484,84"` → `38484.84`, nunca `38.48` (R13).

    O valor é o canário do IBOV em 01/02/2006 (`SPEC CA-034`, API da B3
    `indexStatisticsProxy`, campo `rateValue2` com `day=1`).
    """
    assert para_float_ptbr("38.484,84") == 38484.84
    # O erro que o normalizador existe para evitar: perder o milhar e virar 38,48.
    assert para_float_ptbr("38.484,84") != 38.48


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("38.484,84", 38484.84),  # IBOV 01/02/2006 — B3 (CA-034)
        ("723,070317", 723.070317),  # IMA-B 16/09/2003 — ANBIMA S3 (CA-031)
        ("1.000,00", 1000.0),  # data-base de ICON/IMOB — B3 (CA-036)
        ("6.930", 6930.0),  # vértice da Curva Zero em dias corridos (R13)
        ("6,5140", 6.514),  # taxa do mesmo vértice
        ("0,59", 0.59),  # IPCA 01/2006 no CSV do SGS
        ("13,1364", 13.1364),  # Tx. Compra de LTN no ms*.txt
        ("-4,58301615075328E-02", -0.0458301615075328),  # Beta 3 Svensson do CZ
        ("1.234.567,89", 1234567.89),  # dois grupos de milhar
        ("-1.500,5", -1500.5),
    ],
)
def test_numeros_reais_das_fontes_convertem(bruto: str, esperado: float) -> None:
    """Cada entrada é um valor **lido de uma resposta real**, não inventado para o teste."""
    assert para_float_ptbr(bruto) == pytest.approx(esperado, abs=1e-12)


def test_milhar_do_cz_e_decimal_do_cz_saem_do_arquivo_real(fixtures_common: Path) -> None:
    """Lê `6.930` e `6,5140` do HTML real da Curva Zero e converte com o normalizador único."""
    html = ler_texto((fixtures_common / "anbima_cz__2026-10-09.html").read_bytes(), parsing.LATIN_1)
    linha = re.search(r">6\.930</td>\s*<td\s*>([\d,]+)</td>", html, flags=re.DOTALL)
    assert linha is not None, "o vértice 6.930 deveria estar na fixture real do CZ"
    assert para_float_ptbr("6.930") == 6930.0
    assert para_float_ptbr(linha.group(1)) == pytest.approx(6.5140)


def test_ponto_decimal_do_sgs_nao_e_lido_como_ptbr() -> None:
    """`"0.82"` (JSON do SGS) levanta em vez de virar `82.0` — guarda contra erro de escala."""
    with pytest.raises(NumeroNaoReconhecido, match="para_float_ponto_decimal"):
        para_float_ptbr("0.82")
    assert para_float_ponto_decimal("0.82") == 0.82
    assert para_float_ponto_decimal("-0.32") == -0.32


def test_ptbr_e_ponto_decimal_nao_se_confundem_no_sentido_inverso() -> None:
    """Simetria: número com vírgula não passa por `para_float_ponto_decimal`."""
    with pytest.raises(NumeroNaoReconhecido, match="para_float_ptbr"):
        para_float_ponto_decimal("38.484,84")


@pytest.mark.parametrize("ausencia", ["", "-", "--", "ND", "n/d", "N/A", "null", "  "])
def test_ausencia_vira_none_nunca_zero(ausencia: str) -> None:
    """Anti-SPEC §10.1.4: célula ausente (feriado, mês sem divulgação) **nunca** é `0`."""
    assert para_float_ptbr(ausencia) is None
    assert para_float_ponto_decimal(ausencia) is None


def test_none_continua_none() -> None:
    """`None` entra e sai `None`: nenhum `0` aparece por conveniência de tipo."""
    assert para_float_ptbr(None) is None


def test_booleano_nao_e_numero_de_serie() -> None:
    """`True` é `1` em Python; aceitar isso deixaria passar erro de coluna."""
    with pytest.raises(NumeroNaoReconhecido):
        para_float_ptbr(True)
    with pytest.raises(NumeroNaoReconhecido):
        para_float_ponto_decimal(False)


# ─────────────────────────────────────────────────────────────────────────────
# QA-01 (P0) — entrada numérica nativa não passa pelo parser de string
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "nativo",
    [723.070317, 38484.84, 5.0, 0.82, 1.234, 12.345, 7, 0, -1.5, -0.32, 1e-6],
)
def test_qa01_entrada_numerica_nativa_volta_igual(nativo: float) -> None:
    """QA-01 (P0): número **já tipado** entra e sai igual, nas duas convenções.

    Regressão de um erro de escala de 1000x **silencioso**: `_normalizar_entrada` convertia
    `int|float` por `repr(float(v))`, e a string com ponto decimal era então lida como milhar.
    `para_float_ptbr(1.234)` devolvia `1234.0`; `para_float_ptbr(723.070317)` levantava.
    """
    assert para_float_ptbr(nativo) == pytest.approx(float(nativo), rel=0, abs=0)
    assert para_float_ponto_decimal(nativo) == pytest.approx(float(nativo), rel=0, abs=0)


@pytest.mark.parametrize(("nativo", "errado"), [(1.234, 1234.0), (12.345, 12345.0)])
def test_qa01_float_nativo_nao_e_lido_como_milhar(nativo: float, errado: float) -> None:
    """O valor específico que o QA reproduziu: `1.234` é 1,234 — não 1234."""
    assert para_float_ptbr(nativo) == nativo
    assert para_float_ptbr(nativo) != errado


def test_qa01_escalar_do_numpy_tambem_passa_direto() -> None:
    """`pandas` e `openpyxl` entregam `numpy.float64`/`float32`/`int64`, que não são `float`."""
    np = pytest.importorskip("numpy")
    assert para_float_ptbr(np.float64(1.234)) == pytest.approx(1.234)
    assert para_float_ptbr(np.float32(2.5)) == pytest.approx(2.5)
    assert para_float_ptbr(np.int64(7)) == 7.0


def test_qa01_float_nativo_do_openpyxl_preserva_o_canario(fixtures_common: Path) -> None:
    """Por que QA-01 era P0: `openpyxl` devolve **float nativo** no `.xls` do S3 da ANBIMA.

    Lê a 1ª célula de valor da fixture real e confirma que o canário de CA-031 sobrevive ao
    normalizador — é o caminho que F-002 vai percorrer.
    """
    load_workbook = pytest.importorskip("openpyxl").load_workbook
    arquivo = fixtures_common / "anbima_imab__2026-10-09__janela-truncada.xlsx"
    aba = load_workbook(io.BytesIO(arquivo.read_bytes()), data_only=True, read_only=True).active
    linhas = list(aba.iter_rows(min_row=2, max_row=2, values_only=True))
    rotulo, data_ref, numero_indice = linhas[0][0], linhas[0][1], linhas[0][2]

    assert isinstance(numero_indice, float), "openpyxl entrega float nativo, não string"
    assert normalizar_rotulo(rotulo) == "IMA-B"
    assert para_data(data_ref, FormatoData.ISO) == date(2003, 9, 16)
    assert para_float_ptbr(numero_indice) == pytest.approx(723.070317, abs=1e-12)


def test_qa01_nan_do_pandas_vira_none_nunca_zero() -> None:
    """`NaN` é a ausência do pandas: `None`, nunca `0` (Anti-SPEC §10.1.4)."""
    assert para_float_ptbr(float("nan")) is None
    assert para_float_ponto_decimal(float("nan")) is None


def test_qa01_infinito_levanta() -> None:
    """`inf` não é observação de série — vem de divisão por zero em cálculo, não da fonte."""
    with pytest.raises(NumeroNaoReconhecido, match="infinito"):
        para_float_ptbr(float("inf"))


def test_qa01_tipo_nao_suportado_levanta_em_vez_de_ser_estringificado() -> None:
    """`Decimal` não é `numbers.Real`: antes virava `str` em silêncio e caía no parser errado."""
    with pytest.raises(NumeroNaoReconhecido, match="aceita str, int, float ou None"):
        para_float_ptbr(Decimal("1.234"))
    with pytest.raises(NumeroNaoReconhecido):
        para_float_ptbr(b"1,234")


def test_qa01_data_numerica_do_openpyxl_funciona() -> None:
    """`Data Referencia` como número (`20261008`) é o que `openpyxl`/`pandas` entregam."""
    assert para_data(20261008, FormatoData.AAAAMMDD) == date(2026, 10, 8)
    with pytest.raises(DataNaoReconhecida, match="casa decimal"):
        para_data(2026.5, FormatoData.AAAAMMDD)


# ─────────────────────────────────────────────────────────────────────────────
# CA-030 (pré) — `.xls` que é XLSX detectado por magic bytes
# ─────────────────────────────────────────────────────────────────────────────


def test_ca030_pre_xls_que_e_xlsx_e_detectado_por_magic_bytes(
    fixtures_common: Path, tmp_path: Path
) -> None:
    """CA-030 (pré): o arquivo servido como `.xls` pelo S3 da ANBIMA é XLSX (`PK\\x03\\x04`).

    O teste copia a fixture real para `tmp_path` **com a extensão mentirosa** `.xls`, como a fonte
    serve, e confirma que a decisão de formato ignora a extensão (R11). `exigir_formato` com o
    esperado errado levanta — é o que impede `xlrd` de ser chamado para um OOXML.
    """
    real = fixtures_common / "anbima_imab__2026-10-09__janela-truncada.xlsx"
    mentiroso = tmp_path / "IMAB-HISTORICO.xls"
    mentiroso.write_bytes(real.read_bytes())

    conteudo = mentiroso.read_bytes()
    assert conteudo.startswith(b"PK\x03\x04")
    assert mentiroso.suffix == ".xls"  # a extensão mente
    assert detectar_formato(conteudo) is FormatoDetectado.XLSX  # os bytes não

    assert exigir_formato(conteudo, FormatoDetectado.XLSX, origem=str(mentiroso))
    with pytest.raises(FormatoInesperado, match="xlsx"):
        exigir_formato(conteudo, FormatoDetectado.XLS_BIFF, origem=str(mentiroso))


def test_xls_da_curva_zero_e_html(fixtures_common: Path) -> None:
    """A outra metade do R11: o `saida=xls` do `CZ-down.asp` é HTML `<table>`, não planilha."""
    conteudo = (fixtures_common / "anbima_cz__2026-10-09.html").read_bytes()
    assert detectar_formato(conteudo) is FormatoDetectado.HTML
    with pytest.raises(FormatoInesperado, match="html"):
        exigir_formato(conteudo, FormatoDetectado.XLSX, origem="CZ-down.asp")


@pytest.mark.parametrize(
    ("conteudo", "esperado"),
    [
        (b"", FormatoDetectado.VAZIO),
        (b"   \r\n ", FormatoDetectado.VAZIO),
        (b"PK\x03\x04qualquer", FormatoDetectado.XLSX),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest", FormatoDetectado.XLS_BIFF),
        (b"  \n<html>", FormatoDetectado.HTML),
        (b'[{"data":"01/09/2026"}]', FormatoDetectado.JSON),
        (b'{"error":"x"}', FormatoDetectado.JSON),
        (b"%PDF-1.4", FormatoDetectado.PDF),
        (b'"data";"valor"\r\n"01/01/2006";"0,59"', FormatoDetectado.TEXTO),
    ],
)
def test_deteccao_de_formato_por_assinatura(conteudo: bytes, esperado: FormatoDetectado) -> None:
    """Matriz de magic bytes que o pipeline pode encontrar nas 13 fontes."""
    assert detectar_formato(conteudo) is esperado


def test_resposta_de_zero_bytes_e_vazio_nao_texto(fixtures_common: Path) -> None:
    """Dia sem divulgação da ANBIMA chega como 0 bytes (R17) — tem de ser classificável."""
    assert fixtures_common.is_dir()
    assert detectar_formato(b"") is FormatoDetectado.VAZIO


# ─────────────────────────────────────────────────────────────────────────────
# CA-022 — encoding explícito em todo leitor
# ─────────────────────────────────────────────────────────────────────────────

_FUNCOES_QUE_EXIGEM_ENCODING = {
    "open",
    "read_text",
    "write_text",
    "read_csv",
    "read_table",
    "read_fwf",
    "to_csv",
}


def _chamadas_sem_encoding(arquivo: Path) -> list[str]:
    """Varre o AST procurando leitor/escritor de texto sem `encoding=` explícito."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    faltando: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", None)
        if nome not in _FUNCOES_QUE_EXIGEM_ENCODING:
            continue
        if any(palavra.arg == "encoding" for palavra in no.keywords):
            continue
        faltando.append(f"{arquivo.name}:{no.lineno} {nome}()")
    return faltando


def test_ca022_nenhum_leitor_do_pipeline_confia_no_encoding_do_locale(raiz_repo: Path) -> None:
    """CA-022 / Anti-SPEC §10.4.26: lint próprio — `open`/`read_text`/`read_csv` sem `encoding`.

    O default do locale no Windows é cp1252 e corrompe acento em silêncio. Este teste é o lint:
    falha apontando arquivo e linha, para o autor não descobrir pelo dado errado.
    """
    modulos = sorted((raiz_repo / "apps").rglob("*.py"))
    assert modulos, "esperava encontrar módulos em apps/ para auditar"
    faltando = [erro for arquivo in modulos for erro in _chamadas_sem_encoding(arquivo)]
    assert not faltando, "leitor/escritor de texto sem encoding explícito: " + "; ".join(faltando)


def test_ca022_ler_texto_nao_tem_default_de_encoding() -> None:
    """`encoding` é parâmetro obrigatório: não existe caminho que herde o locale."""
    import inspect

    assinatura = inspect.signature(ler_texto)
    assert assinatura.parameters["encoding"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        ler_texto(b"x")  # type: ignore[call-arg]


def test_ca022_acento_do_ms_txt_exige_latin1(fixtures_common: Path) -> None:
    """O `ms*.txt` real é latin-1; lê-lo como UTF-8 levanta, em vez de virar mojibake.

    `Associação` traz `\\xe7\\xe3`, que é sequência inválida em UTF-8 — por isso o modo `strict`
    é uma guarda de verdade e não decoração.
    """
    conteudo = (fixtures_common / "anbima_ms__2026-10-08.txt").read_bytes()
    texto = ler_texto(conteudo, parsing.LATIN_1)
    assert "Associação Brasileira das Entidades dos Mercados Financeiro" in texto
    with pytest.raises(UnicodeDecodeError):
        ler_texto(conteudo, parsing.UTF_8)


def test_encoding_por_fonte_cobre_as_fontes_do_catalogo() -> None:
    """O mapa de encoding medido (R10) não pode esquecer uma fonte que o catálogo usa."""
    from packages.shared.schemas import Fonte

    sem_encoding = {
        fonte.value
        for fonte in Fonte
        if fonte.value not in parsing.ENCODING_POR_FONTE
        and fonte.value not in {"DERIVADO", "MANUAL"}
    }
    assert not sem_encoding, f"fontes sem encoding declarado: {sorted(sem_encoding)}"


# ─────────────────────────────────────────────────────────────────────────────
# R12 — datas traiçoeiras
# ─────────────────────────────────────────────────────────────────────────────


def test_armadilha_01_02_depende_do_formato_declarado() -> None:
    """R12: `01/02/2006` é 1º de fevereiro no SGS e 2 de janeiro na PTAX do Olinda."""
    assert para_data("01/02/2006", FormatoData.DD_MM_AAAA) == date(2006, 2, 1)
    assert para_data("01-02-2006", FormatoData.MM_DD_AAAA) == date(2006, 1, 2)


@pytest.mark.parametrize(
    ("bruto", "formato", "esperado"),
    [
        ("16/09/2003", FormatoData.DD_MM_AAAA, date(2003, 9, 16)),  # ANBIMA S3
        ("20261008", FormatoData.AAAAMMDD, date(2026, 10, 8)),  # ms*.txt
        ("261008", FormatoData.AAMMDD, date(2026, 10, 8)),  # nome ms{AAMMDD}.txt
        ("2026-10-09", FormatoData.ISO, date(2026, 10, 9)),
    ],
)
def test_datas_reais_das_fontes(bruto: str, formato: FormatoData, esperado: date) -> None:
    """Uma linha por padrão de data confirmado na pesquisa."""
    assert para_data(bruto, formato) == esperado


def test_data_em_formato_errado_levanta_em_vez_de_adivinhar() -> None:
    """`20261008` não é `dd/mm/aaaa`: levanta, não tenta o próximo formato."""
    with pytest.raises(DataNaoReconhecida, match="DD_MM_AAAA"):
        para_data("20261008", FormatoData.DD_MM_AAAA)


def test_data_ausente_e_none_nunca_hoje() -> None:
    """Campo de data vazio não vira a data de execução."""
    assert para_data("", FormatoData.DD_MM_AAAA) is None
    assert para_data(None, FormatoData.AAAAMMDD) is None


def test_data_de_referencia_do_ms_txt_sai_do_arquivo_real(fixtures_common: Path) -> None:
    """Fecha o ciclo: `Data Referencia = 20261008` lido do `ms*.txt` real vira `date`."""
    texto = ler_texto((fixtures_common / "anbima_ms__2026-10-08.txt").read_bytes(), parsing.LATIN_1)
    primeira = next(linha for linha in texto.splitlines() if linha.startswith("LTN@"))
    campos = primeira.split("@")
    assert para_data(campos[1], FormatoData.AAAAMMDD) == date(2026, 10, 8)
    assert para_float_ptbr(campos[5]) == pytest.approx(13.1364)


# ─────────────────────────────────────────────────────────────────────────────
# R14 — rótulo instável
# ─────────────────────────────────────────────────────────────────────────────


def test_rotulos_instaveis_do_s3_colapsam(fixtures_common: Path) -> None:
    """R14 (base de CA-032): `IMA-B` e `IMA - B` têm de virar o mesmo rótulo."""
    assert normalizar_rotulo("IMA-B") == normalizar_rotulo("IMA - B") == "IMA-B"
    assert normalizar_rotulo(" ima -\tb ") == "IMA-B"
    # E o rótulo real da fixture já está na forma colapsada.
    assert normalizar_rotulo("IMA-B 5+") == "IMA-B5+"
    assert fixtures_common.is_dir()
