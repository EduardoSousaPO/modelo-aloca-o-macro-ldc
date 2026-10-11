"""Testes do extrator ANBIMA S3 (F-002, SPEC RF-011, CA-030..033).

Nenhum teste aqui toca a rede: tudo vem de `tests/fixtures/anbima-ima/`, que é **recorte real**
dos arquivos da fonte (primeiras + últimas linhas, para caber no limite de 200 KB) mais o corpo
de erro real que o bucket devolve. O único teste que vai à fonte viva está marcado
`@pytest.mark.network` e o CI N1 o exclui com `-m "not network"` (Anti-SPEC §10.4.23).

Onde a fixture é um recorte, o parse roda com `minimo=None` — o piso real do contrato
(`LINHAS_MINIMAS`, ~5.795 linhas no IMA-B) é exercitado no teste de truncamento e no teste de rede.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest
from openpyxl.utils.exceptions import InvalidFileException

from apps.pipeline.common import (
    ConteudoDivergente,
    FormatoDetectado,
    FormatoInesperado,
    RespostaBruta,
    RespostaTruncada,
    caminho_processed,
    detectar_formato,
    normalizar_rotulo,
    sha256_de,
)
from apps.pipeline.extract import anbima_s3
from apps.pipeline.extract.anbima_s3 import (
    LINHAS_MINIMAS,
    ROTULOS_ESPERADOS,
    SLUGS_EMAIL,
    SLUGS_SUPORTADOS,
    VALORES_CANARIO,
    HistoricoInconsistente,
    config_do_indice,
    extrair_indice,
    extrair_indice_offline,
    parse_historico,
    series_id_de,
)
from packages.shared.schemas import ProcessedSeriesSchema, load_catalog

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

COLETA = datetime(2026, 10, 10, 20, 0, tzinfo=UTC)

#: `tests/fixtures/anbima-ima/`. Nome de arquivo pela convenção de `tests/fixtures/README.md`.
FIXTURAS = {
    "IMAB": "imab__2026-10-10.xlsx",
    "IRFM": "irfm__2026-10-10.xlsx",
    "IMAGERALEXC": "imageralexc__2026-10-10.xlsx",
}
FIXTURA_ERRO = "imab__erro_accessdenied.xml"


# ─────────────────────────────────────────────────────────────────────────────
# Infra do teste
# ─────────────────────────────────────────────────────────────────────────────


class TransporteGravado:
    """Transporte falso (modelo copiado de `tests/unit/test_common_http.py`)."""

    def __init__(self, *respostas: RespostaBruta | Exception) -> None:
        self._respostas = list(respostas)
        self.chamadas: list[dict[str, Any]] = []

    def __call__(
        self,
        metodo: str,
        url: str,
        *,
        params: Any = None,
        dados: Any = None,
        cabecalhos: Any,
        timeout_s: float,
    ) -> RespostaBruta:
        self.chamadas.append({"metodo": metodo, "url": url, "cabecalhos": dict(cabecalhos)})
        proxima = self._respostas.pop(0) if self._respostas else None
        if proxima is None:
            msg = f"transporte falso sem resposta programada para {metodo} {url}"
            raise AssertionError(msg)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


@pytest.fixture
def dir_ima(dir_fixtures: Path) -> Path:
    """`tests/fixtures/anbima-ima/`."""
    return dir_fixtures / "anbima-ima"


@pytest.fixture
def piso_de_recorte(monkeypatch: pytest.MonkeyPatch) -> None:
    """Baixa `LINHAS_MINIMAS` para 1 nos testes de caminho completo.

    O piso real (5.795 linhas no IMA-B) vale para a série de 20 anos; a fixture é um recorte de
    200 KB. Quem testa o piso é `test_truncamento_silencioso_e_recusado_pelo_piso_do_contrato`,
    que **não** usa esta fixture.
    """
    for slug in FIXTURAS:
        monkeypatch.setitem(anbima_s3.LINHAS_MINIMAS, slug, 1)


@pytest.fixture
def imab(dir_ima: Path) -> bytes:
    """Recorte real do `IMAB-HISTORICO.xls`: 40 primeiras + 40 últimas linhas."""
    return (dir_ima / FIXTURAS["IMAB"]).read_bytes()


def _resposta(conteudo: bytes, *, slug: str = "IMAB", status: int = 200) -> RespostaBruta:
    return RespostaBruta(
        url=anbima_s3.URL_S3.format(slug=slug),
        status=status,
        conteudo=conteudo,
        cabecalhos={"ETag": '"d3f0cc0b"', "Content-Type": "application/octet-stream"},
        obtida_em=COLETA,
    )


def _reescrever(original: bytes, transformar: Callable[[pd.DataFrame], pd.DataFrame]) -> bytes:
    """Reescreve a fixture com uma alteração — **adulteração em memória**, nunca gravada no repo.

    É como se testa o caminho de erro sem inventar fixture: o layout continua o real da ANBIMA e
    só o campo sob teste muda.
    """
    quadro = transformar(pd.read_excel(io.BytesIO(original), engine="openpyxl"))
    buffer = io.BytesIO()
    quadro.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# CA-030 — magic bytes `PK`, openpyxl a partir de BytesIO, nunca xlrd
# ─────────────────────────────────────────────────────────────────────────────


def test_ca030_o_xls_da_fonte_e_xlsx_pelos_magic_bytes(dir_ima: Path) -> None:
    """A extensão da URL é `.xls`; os 4 primeiros bytes dizem XLSX (`PK\\x03\\x04`)."""
    for nome in FIXTURAS.values():
        conteudo = (dir_ima / nome).read_bytes()
        assert conteudo[:4] == b"PK\x03\x04", nome
        assert detectar_formato(conteudo) is FormatoDetectado.XLSX, nome


def test_ca030_openpyxl_recusa_a_extensao_xls_mas_o_parse_de_bytes_funciona(
    imab: bytes, tmp_path: Path
) -> None:
    """A pegadinha inteira num teste: mesmo conteúdo, dois caminhos, um só funciona.

    Salvar o corpo com a extensão da fonte (`.xls`) e abrir do disco é o erro natural, e o
    `openpyxl` recusa **pela extensão** antes de olhar o conteúdo. O extrator nunca faz isso:
    lê de `io.BytesIO` e arquiva o bruto como `.xlsx`.
    """
    import openpyxl

    disfarcado = tmp_path / "IMAB-HISTORICO.xls"
    disfarcado.write_bytes(imab)
    with pytest.raises(InvalidFileException):
        openpyxl.load_workbook(disfarcado)

    quadro = parse_historico(imab, slug="IMAB", origem="fixture", collected_at=COLETA, minimo=None)
    assert len(quadro) == 80
    assert anbima_s3.EXTENSAO_RAW == "xlsx"


def test_ca030_corpo_de_erro_real_do_bucket_e_recusado_antes_do_parse(dir_ima: Path) -> None:
    """`AccessDenied` (o corpo real do S3) é XML, não XLSX → `FormatoInesperado`, sem parse.

    Fixture de erro obrigatória do extrator (CA-124): prova que o parser **recusa** o corpo
    errado em vez de gravar lixo. Vale para a listagem do bucket e para SLUG inexistente — o S3
    responde o mesmo XML nos dois casos.
    """
    corpo = (dir_ima / FIXTURA_ERRO).read_bytes()
    assert b"AccessDenied" in corpo
    with pytest.raises(FormatoInesperado, match="esperado um de"):
        parse_historico(corpo, slug="IMAB", origem="fixture-erro", collected_at=COLETA)


def test_ca030_corpo_de_erro_nao_deixa_nada_em_data_processed(
    dir_ima: Path, tmp_path: Path
) -> None:
    """CA-003 na prática: resposta inválida levanta e `data/processed/` fica vazio."""
    transporte = TransporteGravado(_resposta((dir_ima / FIXTURA_ERRO).read_bytes()))
    with pytest.raises(FormatoInesperado):
        extrair_indice("IMAB", transporte=transporte, raiz=tmp_path)
    assert not (tmp_path / "data" / "processed").exists()


# ─────────────────────────────────────────────────────────────────────────────
# CA-031 — valor-canário
# ─────────────────────────────────────────────────────────────────────────────


def test_ca031_valor_canario_imab_16_09_2003(imab: bytes) -> None:
    """IMA-B em 16/09/2003 = **723,070317**, e a última data é >= 2026-10-09."""
    quadro = parse_historico(imab, slug="IMAB", origem="fixture", collected_at=COLETA, minimo=None)
    linha = quadro.loc[quadro["date"] == pd.Timestamp("2003-09-16")]
    assert len(linha) == 1
    assert float(linha["value"].iloc[0]) == 723.070317
    assert quadro["date"].max().date() >= date(2026, 10, 9)
    # O canário do contrato é o mesmo número — se divergir, um dos dois mentiu.
    assert config_do_indice("IMAB").valor_canario == ("2003-09-16", 723.070317)


def test_ca031_canario_de_cada_indice_e_a_primeira_observacao(dir_ima: Path) -> None:
    """O `valor_canario` do contrato bate com a 1ª linha do arquivo real, índice por índice."""
    for slug, nome in FIXTURAS.items():
        quadro = parse_historico(
            (dir_ima / nome).read_bytes(),
            slug=slug,
            origem=nome,
            collected_at=COLETA,
            minimo=None,
        )
        data_esperada, valor_esperado = VALORES_CANARIO[slug]
        assert quadro["date"].iloc[0] == pd.Timestamp(data_esperada), slug
        assert float(quadro["value"].iloc[0]) == valor_esperado, slug


def test_ca031_o_float_nativo_do_openpyxl_nao_perde_escala(imab: bytes) -> None:
    """Regressão de QA-01: `723.070317` tem de sair `723.070317`, não `723070317.0`.

    O `openpyxl` entrega número **já tipado**; estringificar antes de normalizar fazia o ponto
    decimal ser lido como separador de milhar. 6 casas decimais preservadas.
    """
    quadro = parse_historico(imab, slug="IMAB", origem="fixture", collected_at=COLETA, minimo=None)
    assert 700.0 < float(quadro["value"].iloc[0]) < 800.0
    assert 10_000.0 < float(quadro["value"].iloc[-1]) < 20_000.0


# ─────────────────────────────────────────────────────────────────────────────
# CA-032 — rótulo instável
# ─────────────────────────────────────────────────────────────────────────────


def test_ca032_a_fixture_realmente_traz_os_dois_rotulos(imab: bytes) -> None:
    """Sem isto o teste seguinte não prova nada: o recorte tem `IMA-B` **e** `IMA - B`."""
    bruto = pd.read_excel(io.BytesIO(imab), engine="openpyxl")
    assert set(bruto[bruto.columns[0]]) == {"IMA-B", "IMA - B"}


def test_ca032_rotulos_inconsistentes_colapsam_em_um_series_id(imab: bytes) -> None:
    """`IMA-B` e `IMA - B` → um `asset_id` só, e ele vem do SLUG do catálogo."""
    assert normalizar_rotulo("IMA - B") == normalizar_rotulo("IMA-B") == "IMA-B"
    quadro = parse_historico(imab, slug="IMAB", origem="fixture", collected_at=COLETA, minimo=None)
    assert set(quadro["series_id"]) == {"ANBIMA_IMAB"}
    assert quadro["series_id"].iloc[0] == "ANBIMA_IMAB" == series_id_de("IMAB")


def test_ca032_todo_indice_suportado_tem_rotulos_declarados() -> None:
    """Mapa explícito de códigos (SPEC CB-015): nenhum SLUG suportado fica sem rótulo esperado."""
    assert set(ROTULOS_ESPERADOS) == set(SLUGS_SUPORTADOS)
    assert all(ROTULOS_ESPERADOS[s] for s in SLUGS_SUPORTADOS)


def test_ca032_rotulo_de_outro_indice_no_arquivo_levanta(imab: bytes) -> None:
    """Se a ANBIMA trocar o conteúdo do arquivo, o extrator grita em vez de rotular errado."""
    adulterado = _reescrever(imab, lambda df: df.assign(**{str(df.columns[0]): "IFIX"}))
    with pytest.raises(HistoricoInconsistente, match="rótulo inesperado"):
        parse_historico(
            adulterado, slug="IMAB", origem="adulterado", collected_at=COLETA, minimo=None
        )


# ─────────────────────────────────────────────────────────────────────────────
# CA-033 — cobertura de 2006 e SLUGs hard-coded
# ─────────────────────────────────────────────────────────────────────────────


def test_ca033_os_oito_indices_do_email_cobrem_1t2006_no_catalogo() -> None:
    """Os 8 índices de B1/B2 têm `data_inicio <= 2006-01-02` — cobrem o 1T2006 inteiro."""
    catalogo = {e.series_id: e for e in load_catalog()}
    assert len(SLUGS_EMAIL) == 8
    for slug in SLUGS_EMAIL:
        entrada = catalogo[series_id_de(slug)]
        assert entrada.data_inicio is not None, slug
        assert entrada.data_inicio <= date(2006, 1, 2), (slug, entrada.data_inicio)
        assert entrada.item_email in {"B1", "B2"}, slug


def test_ca033_slugs_hard_coded_batem_com_o_catalogo() -> None:
    """A listagem do bucket é `AccessDenied` → SLUG hard-coded, conferido contra o catálogo."""
    catalogo = {e.series_id: e for e in load_catalog()}
    for slug in SLUGS_SUPORTADOS:
        entrada = catalogo[series_id_de(slug)]
        assert entrada.identificador == slug
        assert entrada.fonte_url == anbima_s3.URL_S3.format(slug=slug)
        assert entrada.fonte.value == "ANBIMA_S3"
    # "5+" é `5MAIS` na URL — nunca `+`, `P` nem `PLUS` (a variante errada dá AccessDenied).
    assert "IMAB5MAIS" in SLUGS_SUPORTADOS
    assert "IMAB5PLUS" not in SLUGS_SUPORTADOS


def test_ca033_descontinuado_e_fora_do_email_nao_entram() -> None:
    """`IMAC` morreu em 2021 e `IHFA` não está no e-mail (Anti-SPEC §10.1.6)."""
    assert "IMAC" not in SLUGS_SUPORTADOS
    assert "IHFA" not in SLUGS_SUPORTADOS
    catalogo = {e.series_id: e for e in load_catalog()}
    assert catalogo["ANBIMA_IMAC"].status.value == "descontinuada"


def test_ca033_fixture_real_confirma_o_inicio_do_catalogo(dir_ima: Path) -> None:
    """O recorte preserva a 1ª linha: IRF-M começa em 2000-02-01 e IMA-B em 2003-09-16."""
    irfm = parse_historico(
        (dir_ima / FIXTURAS["IRFM"]).read_bytes(),
        slug="IRFM",
        origem="fixture",
        collected_at=COLETA,
        minimo=None,
    )
    assert irfm["date"].min().date() == date(2000, 2, 1)
    imab = parse_historico(
        (dir_ima / FIXTURAS["IMAB"]).read_bytes(),
        slug="IMAB",
        origem="fixture",
        collected_at=COLETA,
        minimo=None,
    )
    assert imab["date"].min().date() == date(2003, 9, 16)


# ─────────────────────────────────────────────────────────────────────────────
# Contrato de saída e guardas de conteúdo (Validation Mode, AGENTS.md §15)
# ─────────────────────────────────────────────────────────────────────────────


def test_saida_obedece_processed_series_schema(imab: bytes) -> None:
    """As 8 colunas de `ProcessedSeriesSchema`, nada mais, nada menos (`strict=True`)."""
    quadro = parse_historico(imab, slug="IMAB", origem="fixture", collected_at=COLETA, minimo=None)
    assert list(quadro.columns) == [
        "series_id",
        "date",
        "value",
        "source",
        "freq",
        "vintage",
        "unit",
        "collected_at",
    ]
    validado = ProcessedSeriesSchema.validate(quadro, lazy=True)
    assert len(validado) == len(quadro)
    assert quadro["freq"].unique().tolist() == ["D"]  # frequência nativa diária (§10.4.28)
    assert quadro["unit"].unique().tolist() == ["index"]
    assert quadro["source"].unique().tolist() == ["ANBIMA_S3"]


def test_truncamento_silencioso_e_recusado_pelo_piso_do_contrato(imab: bytes) -> None:
    """Recorte de 80 linhas contra um piso de 5.795 → `RespostaTruncada` (R2)."""
    assert LINHAS_MINIMAS["IMAB"] == 5795
    with pytest.raises(RespostaTruncada):
        parse_historico(imab, slug="IMAB", origem="fixture", collected_at=COLETA)


def test_numero_indice_nulo_levanta_em_vez_de_virar_zero(imab: bytes) -> None:
    """Anti-SPEC §10.1.4: ausência nunca é `0`; aqui ela nem é aceita como `None`."""

    def _apagar(df: pd.DataFrame) -> pd.DataFrame:
        copia = df.copy()
        copia.iloc[5, 2] = None
        return copia

    with pytest.raises(HistoricoInconsistente, match="Número Índice nulo"):
        parse_historico(
            _reescrever(imab, _apagar),
            slug="IMAB",
            origem="adulterado",
            collected_at=COLETA,
            minimo=None,
        )


def test_data_repetida_levanta(imab: bytes) -> None:
    """Índice temporal duplicado quebraria a PK `(series_id, date, vintage)`."""

    def _duplicar(df: pd.DataFrame) -> pd.DataFrame:
        copia = df.copy()
        copia.iloc[1, 1] = copia.iloc[0, 1]
        return copia

    with pytest.raises(HistoricoInconsistente, match="data repetida"):
        parse_historico(
            _reescrever(imab, _duplicar),
            slug="IMAB",
            origem="adulterado",
            collected_at=COLETA,
            minimo=None,
        )


def test_data_fora_de_ordem_levanta(imab: bytes) -> None:
    """Ordenação do índice temporal é contrato, não sorte da fonte."""
    with pytest.raises(HistoricoInconsistente, match="fora de ordem"):
        parse_historico(
            _reescrever(imab, lambda df: df.iloc[::-1].reset_index(drop=True)),
            slug="IMAB",
            origem="adulterado",
            collected_at=COLETA,
            minimo=None,
        )


def test_data_futura_levanta(imab: bytes) -> None:
    """`date > collected_at` é relógio ou arquivo errado (o `sem_data_futura` do schema)."""
    with pytest.raises(HistoricoInconsistente, match="data futura"):
        parse_historico(
            imab,
            slug="IMAB",
            origem="fixture",
            collected_at=datetime(2020, 1, 1, tzinfo=UTC),
            minimo=None,
        )


def test_coluna_ausente_levanta_dizendo_o_que_viu(imab: bytes) -> None:
    """Se a ANBIMA renomear `Número Índice`, a mensagem mostra o cabeçalho que chegou."""
    with pytest.raises(HistoricoInconsistente, match="a planilha traz"):
        parse_historico(
            _reescrever(imab, lambda df: df.drop(columns=[df.columns[2]])),
            slug="IMAB",
            origem="adulterado",
            collected_at=COLETA,
            minimo=None,
        )


def test_slug_desconhecido_levanta_em_vez_de_montar_url() -> None:
    """Nenhum SLUG inventado — o catálogo é a fonte de verdade (CA-053)."""
    with pytest.raises(anbima_s3.ErroDeExtracao, match="não suportado"):
        config_do_indice("IMAB5PLUS")


# ─────────────────────────────────────────────────────────────────────────────
# Caminho completo com transporte falso: arquivamento, idempotência, offline
# ─────────────────────────────────────────────────────────────────────────────


def test_extrai_arquiva_e_grava_processado(
    imab: bytes, tmp_path: Path, piso_de_recorte: None
) -> None:
    """Caminho feliz ponta a ponta, sem rede: raw com manifesto + parquet validado."""
    transporte = TransporteGravado(_resposta(imab))
    resultado = extrair_indice("IMAB", transporte=transporte, raiz=tmp_path)

    assert transporte.chamadas[0]["url"].endswith("IMAB-HISTORICO.xls")
    assert "Mozilla/5.0" in transporte.chamadas[0]["cabecalhos"]["User-Agent"]
    # O bruto é arquivado com a extensão real (`.xlsx`) e com a última data do histórico no nome.
    assert resultado.caminho_raw is not None
    assert resultado.caminho_raw.name == "IMAB__2026-10-09.xlsx"
    assert resultado.caminho_raw.with_name(resultado.caminho_raw.name + ".meta.json").is_file()
    assert resultado.caminho_processed == caminho_processed(
        "anbima-ima/ANBIMA_IMAB.parquet", raiz=tmp_path
    )
    assert resultado.caminho_processed.is_file()
    assert resultado.linhas == 80
    assert resultado.pct_nulos_value == 0.0
    assert resultado.valor_inicial == 723.070317


def test_idempotencia_rodar_duas_vezes_nao_muda_nada(
    imab: bytes, tmp_path: Path, piso_de_recorte: None
) -> None:
    """2ª rodada: raw byte-idêntico (não reescreve) e parquet com o mesmo hash (CA-027)."""
    primeiro = extrair_indice("IMAB", transporte=TransporteGravado(_resposta(imab)), raiz=tmp_path)
    assert primeiro.caminho_processed is not None
    parquet_primeiro = primeiro.caminho_processed.read_bytes()

    segundo = extrair_indice("IMAB", transporte=TransporteGravado(_resposta(imab)), raiz=tmp_path)
    assert segundo.raw_idempotente is True
    assert segundo.sha256_raw == primeiro.sha256_raw
    assert segundo.caminho_processed is not None
    assert segundo.caminho_processed.read_bytes() == parquet_primeiro


def test_revisao_retroativa_do_mesmo_retrato_nao_sobrescreve(
    imab: bytes, tmp_path: Path, piso_de_recorte: None
) -> None:
    """Conteúdo diferente no mesmo nome determinístico → `ConteudoDivergente` (R8).

    É a guarda que impede uma republicação da ANBIMA de apagar em silêncio o retrato anterior.
    """
    extrair_indice("IMAB", transporte=TransporteGravado(_resposta(imab)), raiz=tmp_path)
    revisado = _reescrever(
        imab, lambda df: df.assign(**{str(df.columns[2]): df[df.columns[2]] * 1.0001})
    )
    with pytest.raises(ConteudoDivergente):
        extrair_indice("IMAB", transporte=TransporteGravado(_resposta(revisado)), raiz=tmp_path)


def test_offline_reprocessa_o_bruto_sem_tocar_a_rede(
    dir_ima: Path, tmp_path: Path, piso_de_recorte: None
) -> None:
    """`--offline` relê o arquivo arquivado; nenhum transporte é construído."""
    resultado = extrair_indice_offline("IRFM", raiz=tmp_path, caminho=dir_ima / FIXTURAS["IRFM"])
    assert resultado.data_inicio == date(2000, 2, 1)
    assert resultado.raw_idempotente is True
    assert resultado.caminho_processed is not None
    assert resultado.caminho_processed.is_file()


def test_offline_acha_o_bruto_arquivado_pela_convencao_de_nome(
    dir_ima: Path, tmp_path: Path, piso_de_recorte: None
) -> None:
    """Sem `caminho=`, o modo offline procura `<SLUG>__<data>.xlsx` em `data/raw/anbima-ima/`."""
    destino = tmp_path / "data" / "raw" / "anbima-ima"
    destino.mkdir(parents=True)
    (destino / "IRFM__2026-10-09.xlsx").write_bytes((dir_ima / FIXTURAS["IRFM"]).read_bytes())
    resultado = extrair_indice_offline("IRFM", raiz=tmp_path, gravar=False)
    assert resultado.caminho_raw is not None
    assert resultado.caminho_raw.name == "IRFM__2026-10-09.xlsx"
    assert resultado.data_fim == date(2026, 10, 9)


def test_db_offline_tira_o_vintage_do_manifesto_e_e_idempotente(
    dir_ima: Path, tmp_path: Path, piso_de_recorte: None
) -> None:
    """D-b/D-c: `collected_at` sai do manifesto e o glob do offline ignora o `.meta.json`.

    Sem o `vintage` vindo do manifesto, cada reprocessamento do **mesmo** bruto geraria uma
    chave `(series_id, date, vintage)` nova. O `.meta.json` fica deliberadamente na pasta: é a
    armadilha de glob que F-004 mediu (em fonte `.json` ele ordena **antes** do dado).
    """
    bruto = (dir_ima / FIXTURAS["IRFM"]).read_bytes()
    primeiro = extrair_indice(
        "IRFM", transporte=TransporteGravado(_resposta(bruto, slug="IRFM")), raiz=tmp_path
    )
    pasta = tmp_path / "data" / "raw" / "anbima-ima"
    assert any(a.name.endswith(".meta.json") for a in pasta.iterdir()), "manifesto tem de existir"
    assert primeiro.caminho_processed is not None
    esperado = sha256_de(primeiro.caminho_processed.read_bytes())

    for _ in range(2):
        offline = extrair_indice_offline("IRFM", raiz=tmp_path)
        assert offline.caminho_raw is not None
        assert not offline.caminho_raw.name.endswith(".meta.json")
        assert offline.caminho_processed is not None
        quadro = pd.read_parquet(offline.caminho_processed)
        assert (quadro["vintage"] == pd.Timestamp(COLETA.date())).all()
        assert (quadro["vintage"] == quadro["vintage"].dt.normalize()).all()
        assert sha256_de(offline.caminho_processed.read_bytes()) == esperado


def test_cli_rejeita_slug_fora_da_lista() -> None:
    """A CLI não aceita índice que o módulo não sabe baixar."""
    with pytest.raises(SystemExit) as erro:
        anbima_s3.main(["--indices", "IFIX"])
    assert erro.value.code == 2


def test_linha_de_evidencia_e_ascii(dir_ima: Path) -> None:
    """A saída da CLI é ASCII: o `stdout` do Windows é cp1252 e `print` de `->` em Unicode quebra.

    Mesma raiz do Anti-SPEC §10.4.26 (nunca confiar no encoding do locale) — e a falha aparecia
    só **depois** de gravar as 9 séries, que é o pior momento possível.
    """
    quadro = parse_historico(
        (dir_ima / FIXTURAS["IRFM"]).read_bytes(),
        slug="IRFM",
        origem="fixture",
        collected_at=COLETA,
        minimo=None,
    )
    linha = anbima_s3._resultado(
        quadro,
        slug="IRFM",
        sha256_raw="0" * 64,
        bytes_raw=1,
        caminho_raw=None,
        raw_idempotente=False,
        caminho_processed=None,
    ).resumo()
    assert linha.isascii(), linha
    assert "ANBIMA_IRFM" in linha
    assert "2000-02-01 -> 2026-10-09" in linha


# ─────────────────────────────────────────────────────────────────────────────
# Fonte viva — fora do CI N1
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.network
def test_fonte_viva_imab_tras_o_canario_e_o_historico_completo(tmp_path: Path) -> None:
    """Confere a fixture contra a fonte real: canário, piso de contagem e cobertura de 2006."""
    resultado = extrair_indice("IMAB", raiz=tmp_path, gravar=False)
    assert resultado.data_inicio == date(2003, 9, 16)
    assert resultado.valor_inicial == 723.070317
    assert resultado.linhas >= LINHAS_MINIMAS["IMAB"]
    assert resultado.data_fim >= date(2026, 10, 9)
