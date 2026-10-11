"""F-001 — camadas `raw/processed/canonical`: caminhos, nome determinístico, hash e arquivamento.

CA coberto aqui: **CA-124** (existe fixture gravada correspondente). Apoia **CA-003** (nada entra
em `data/processed/` sem passar por pandera) e **CA-121** (reprodutibilidade por hash).
Riscos: R8 (janela rolante — sobrescrever apaga o passado), R21 (arquivo grande → cache
condicional). Anti-SPEC: §10.4.21, §10.4.22.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
from pandera.errors import SchemaErrors

from apps.pipeline.common.errors import ConteudoDivergente, ManifestoAusente
from apps.pipeline.common.io_layers import (
    MARCADORES_DA_RAIZ,
    SUFIXO_MANIFESTO,
    Camada,
    arquivar_bruto,
    caminho_camada,
    caminho_canonical,
    caminho_destino_raw,
    caminho_processed,
    caminho_raw,
    collected_at_do_bruto,
    gravar_processado_parquet,
    ler_manifesto,
    nome_arquivo_raw,
    sha256_de,
    validadores_condicionais,
)
from apps.pipeline.common.io_layers import raiz_repo as raiz_repo_io
from packages.shared.schemas import ExtractorConfig, Fonte

LIMITE_FIXTURE_BYTES = 200 * 1024


@pytest.fixture
def fixtures_common(dir_fixtures: Path) -> Path:
    """`tests/fixtures/common/`."""
    return dir_fixtures / "common"


@pytest.fixture
def config_anbima() -> ExtractorConfig:
    """Config com `destino_raw` real, para exercitar a resolução de caminho."""
    return ExtractorConfig(
        nome="anbima_ima_s3",
        fonte=Fonte.ANBIMA_S3,
        series_ids=("IMAB",),
        base_url="https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/arquivos",
        formato="xlsx",
        encoding="utf-8",
        destino_raw="data/raw/anbima-ima",
        valor_canario=("2003-09-16", 723.070317),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CA-124 — fixture gravada correspondente
# ─────────────────────────────────────────────────────────────────────────────


def test_ca124_fixtures_da_infra_existem_com_fixture_de_erro_obrigatoria(
    fixtures_common: Path,
) -> None:
    """CA-124: F-001 tem fixtures gravadas, incluindo a de **erro**, que não é opcional.

    `tests/fixtures/README.md`: "o modo de falha dominante das fontes deste projeto é erro com
    HTTP 200 (R1) — cada extrator precisa de uma fixture que prove que o parser recusa esse corpo".
    """
    assert fixtures_common.is_dir()
    arquivos = {p.name for p in fixtures_common.iterdir() if p.is_file()}

    esperadas = {
        "README.md",
        "sgs_433__erro.json",
        "sgs_433__2026-10-10.json",
        "anbima_cz__2026-10-09.html",
        "anbima_ms__2026-10-08.txt",
        "anbima_imab__2026-10-09__janela-truncada.xlsx",
    }
    assert esperadas <= arquivos, f"faltando: {sorted(esperadas - arquivos)}"
    assert any(nome.endswith("__erro.json") for nome in arquivos), "fixture de erro é obrigatória"


def test_ca124_toda_fixture_respeita_o_limite_de_200kb(fixtures_common: Path) -> None:
    """Fixture é amostra, não espelho da fonte (`tests/fixtures/README.md`)."""
    grandes = {
        p.name: p.stat().st_size
        for p in fixtures_common.iterdir()
        if p.is_file() and p.stat().st_size > LIMITE_FIXTURE_BYTES
    }
    assert not grandes, f"fixtures acima de 200 KB: {grandes}"


def test_ca124_nenhuma_fixture_usa_extensao_xls_ignorada_pelo_git(fixtures_common: Path) -> None:
    """`*.xls` é ignorado pelo `.gitignore`: fixture com essa extensão não seria versionada."""
    xls = [p.name for p in fixtures_common.iterdir() if p.suffix.lower() == ".xls"]
    assert xls == [], f"renomeie para a extensão do conteúdo real: {xls}"


def test_ca124_fixtures_declaram_procedencia_no_readme(fixtures_common: Path) -> None:
    """Fixture sem procedência documentada é fixture que ninguém sabe regravar."""
    readme = (fixtures_common / "README.md").read_text(encoding="utf-8")
    for arquivo in fixtures_common.iterdir():
        if arquivo.is_file() and arquivo.name != "README.md":
            assert arquivo.name in readme, f"{arquivo.name} não está documentado no README"


# ─────────────────────────────────────────────────────────────────────────────
# Resolução de caminhos
# ─────────────────────────────────────────────────────────────────────────────


def test_raiz_repo_bate_com_a_fixture_da_suite(raiz_repo: Path) -> None:
    """`io_layers.raiz_repo()` e a fixture `raiz_repo` do `conftest` têm de concordar.

    A raiz vem dos marcadores no disco, subindo de `__file__` — não do `cwd`. É o que faz o job
    diário, o `uv run pytest` da raiz e um notebook em `apps/analysis/` gravarem no mesmo lugar.
    """
    assert raiz_repo_io() == raiz_repo
    for marcador in MARCADORES_DA_RAIZ:
        assert (raiz_repo / marcador).is_file()


def test_raiz_repo_e_cacheada_e_absoluta() -> None:
    """`lru_cache`: resolver a raiz é I/O e acontece uma vez por processo."""
    assert raiz_repo_io() is raiz_repo_io()
    assert raiz_repo_io().is_absolute()


@pytest.mark.parametrize(
    ("camada", "pasta"),
    [(Camada.RAW, "raw"), (Camada.PROCESSED, "processed"), (Camada.CANONICAL, "canonical")],
)
def test_caminho_de_cada_camada(camada: Camada, pasta: str, tmp_path: Path) -> None:
    """As três camadas de `CLAUDE.md §4`, sempre sob `data/`."""
    assert caminho_camada(camada, raiz=tmp_path) == tmp_path / "data" / pasta


def test_caminho_raw_tem_uma_subpasta_por_fonte(tmp_path: Path) -> None:
    """`data/raw/<fonte>/` — uma subpasta por fonte, como manda `CLAUDE.md §4`."""
    assert caminho_raw("sgs", raiz=tmp_path) == tmp_path / "data" / "raw" / "sgs"


def test_caminho_destino_raw_usa_o_contrato(config_anbima: ExtractorConfig, tmp_path: Path) -> None:
    """O destino vem do `ExtractorConfig`, nunca de string montada no extrator."""
    assert caminho_destino_raw(config_anbima, raiz=tmp_path) == (
        tmp_path / "data" / "raw" / "anbima-ima"
    )


def test_caminhos_de_processed_e_canonical(tmp_path: Path) -> None:
    """Resolução das duas camadas derivadas."""
    assert caminho_processed("sgs_433.parquet", raiz=tmp_path).parent.name == "processed"
    assert caminho_canonical("macro_quarterly.parquet", raiz=tmp_path).parent.name == "canonical"


# ─────────────────────────────────────────────────────────────────────────────
# Nome determinístico e hash
# ─────────────────────────────────────────────────────────────────────────────


def test_nome_deterministico_depende_so_de_identificador_e_data() -> None:
    """Mesmo identificador + mesma data de referência ⇒ mesmo nome (base da idempotência)."""
    primeiro = nome_arquivo_raw("IMAB", data_ref=date(2026, 10, 9), extensao="xlsx")
    segundo = nome_arquivo_raw("IMAB", data_ref=date(2026, 10, 9), extensao=".XLSX")
    assert primeiro == segundo == "IMAB__2026-10-09.xlsx"


def test_nome_deterministico_preserva_ticker_com_simbolo() -> None:
    """`^GSPC` e `BRL=X` são identificadores reais: não podem virar `-GSPC` nem `BRL-X`."""
    assert nome_arquivo_raw("^GSPC", data_ref=date(2026, 10, 9), extensao="json") == (
        "^GSPC__2026-10-09.json"
    )
    assert nome_arquivo_raw("BRL=X", data_ref=date(2026, 10, 9), extensao="json") == (
        "BRL=X__2026-10-09.json"
    )


def test_nome_deterministico_sanitiza_separador_de_caminho() -> None:
    """Identificador com `/` (tabela SIDRA `t/1737`) não pode criar subpasta por acidente."""
    assert nome_arquivo_raw("t/1737 v/63", data_ref=date(2026, 10, 9), extensao="json") == (
        "t-1737-v-63__2026-10-09.json"
    )


def test_sha256_e_estavel_e_sensivel(fixtures_common: Path) -> None:
    """Hash do corpo bruto: igual para bytes iguais, diferente para 1 byte trocado (CA-121)."""
    conteudo = (fixtures_common / "anbima_ms__2026-10-08.txt").read_bytes()
    assert sha256_de(conteudo) == sha256_de(bytes(conteudo))
    assert sha256_de(conteudo) != sha256_de(conteudo + b" ")
    assert len(sha256_de(conteudo)) == 64


# ─────────────────────────────────────────────────────────────────────────────
# Arquivamento idempotente + manifesto
# ─────────────────────────────────────────────────────────────────────────────


def test_arquivar_duas_vezes_nao_duplica_nem_reescreve(
    config_anbima: ExtractorConfig, fixtures_common: Path, tmp_path: Path
) -> None:
    """Rodar o download duas vezes no mesmo dia é idempotente: nada muda em disco.

    É o comportamento que CA-027 pede do job diário da ANBIMA e o que CA-121 exige do pipeline.
    """
    conteudo = (fixtures_common / "anbima_imab__2026-10-09__janela-truncada.xlsx").read_bytes()
    destino = caminho_destino_raw(config_anbima, raiz=tmp_path)
    nome = nome_arquivo_raw("IMAB", data_ref=date(2026, 10, 9), extensao="xlsx")

    primeiro = arquivar_bruto(conteudo, destino=destino, nome=nome, origem="https://s3/IMAB.xls")
    assert primeiro.escreveu and not primeiro.ja_existia
    mtime = primeiro.caminho.stat().st_mtime_ns

    segundo = arquivar_bruto(conteudo, destino=destino, nome=nome, origem="https://s3/IMAB.xls")
    assert segundo.idempotente
    assert segundo.sha256 == primeiro.sha256
    assert segundo.caminho.stat().st_mtime_ns == mtime, "não deveria ter reescrito o arquivo"
    assert len(list(destino.glob("IMAB__*.xlsx"))) == 1


def test_conteudo_diferente_no_mesmo_nome_levanta_em_vez_de_sobrescrever(tmp_path: Path) -> None:
    """R8: a janela rolante da ANBIMA não volta — sobrescrever em silêncio perde o dado."""
    destino = tmp_path / "data" / "raw" / "anbima-ms"
    nome = "ms__2026-10-08.txt"
    arquivar_bruto(b"primeira versao", destino=destino, nome=nome)

    with pytest.raises(ConteudoDivergente, match="conteúdo diferente"):
        arquivar_bruto(b"segunda versao", destino=destino, nome=nome)
    assert (destino / nome).read_bytes() == b"primeira versao"


def test_sobrescrever_e_possivel_quando_explicitamente_pedido(tmp_path: Path) -> None:
    """A decisão de sobrescrever é de quem chama, nunca default — e fica no log."""
    destino = tmp_path / "data" / "raw" / "sgs"
    nome = "433__2026-10-10.json"
    arquivar_bruto(b"[]", destino=destino, nome=nome)
    resultado = arquivar_bruto(
        b'[{"data":"01/09/2026"}]',
        destino=destino,
        nome=nome,
        sobrescrever_se_diferente=True,
    )
    assert resultado.escreveu and resultado.ja_existia
    assert not resultado.idempotente


def test_manifesto_guarda_hash_origem_e_validadores_condicionais(tmp_path: Path) -> None:
    """O manifesto é o insumo do cache condicional (R21) e da conferência por hash (CA-121)."""
    destino = tmp_path / "data" / "raw" / "tesouro-direto"
    resultado = arquivar_bruto(
        b'"Data Base";"Taxa"\r\n"02/01/2006";"8,42"',
        destino=destino,
        nome="td__2026-10-09.csv",
        origem="https://www.tesourotransparente.gov.br/ckan/.../td.csv",
        obtido_em=datetime(2026, 10, 10, 15, 30, tzinfo=UTC),
        cabecalhos={
            "ETag": 'W/"abc123"',
            "Last-Modified": "Fri, 09 Oct 2026 03:00:00 GMT",
            "Content-Type": "text/csv",
        },
    )
    manifesto = ler_manifesto(resultado.caminho)
    assert manifesto is not None
    assert manifesto["sha256"] == resultado.sha256
    assert manifesto["bytes"] == resultado.bytes_gravados
    assert manifesto["etag"] == 'W/"abc123"'
    assert manifesto["obtido_em"] == "2026-10-10T15:30:00+00:00"
    assert validadores_condicionais(resultado.caminho) == (
        'W/"abc123"',
        "Fri, 09 Oct 2026 03:00:00 GMT",
    )


def test_manifesto_e_byte_identico_entre_execucoes(tmp_path: Path) -> None:
    """Chaves ordenadas: o manifesto não muda de bytes só porque rodou de novo (CA-121)."""
    destino = tmp_path / "data" / "raw" / "sgs"
    comum = {
        "destino": destino,
        "nome": "433__2026-10-10.json",
        "origem": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados",
        "obtido_em": datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
    }
    primeiro = arquivar_bruto(b"[]", **comum)  # type: ignore[arg-type]
    bytes_1 = primeiro.caminho.with_name(primeiro.caminho.name + SUFIXO_MANIFESTO).read_bytes()
    segundo = arquivar_bruto(b"[]", **comum)  # type: ignore[arg-type]
    bytes_2 = segundo.caminho.with_name(segundo.caminho.name + SUFIXO_MANIFESTO).read_bytes()
    assert bytes_1 == bytes_2
    assert json.loads(bytes_1.decode("utf-8"))["origem"].endswith("/dados")


def test_ler_manifesto_de_arquivo_sem_manifesto_e_none(tmp_path: Path) -> None:
    """Primeira execução: não há manifesto, e isso não é erro."""
    assert ler_manifesto(tmp_path / "inexistente.json") is None
    assert validadores_condicionais(tmp_path / "inexistente.json") == (None, None)


def test_collected_at_do_bruto_sai_do_manifesto(tmp_path: Path) -> None:
    """D-b: a safra da camada processada é o `obtido_em` do manifesto, sempre."""
    coleta = datetime(2026, 10, 10, 23, 49, tzinfo=UTC)
    resultado = arquivar_bruto(
        b"[]",
        destino=tmp_path / "data" / "raw" / "sgs",
        nome="433__2026-10-10.json",
        obtido_em=coleta,
    )
    assert collected_at_do_bruto(resultado.caminho) == coleta


def test_collected_at_do_bruto_sem_manifesto_recusa_em_vez_de_usar_o_relogio(
    tmp_path: Path,
) -> None:
    """Bruto posto à mão não tem safra — e inventar uma quebra a idempotência (CA-121).

    Era o P1 de F-005 no QA da Onda 1: `obtido_em_arquivado(...) or datetime.now(tz=UTC)` fazia
    `vintage` virar a hora do reprocessamento, então duas rodadas `--offline` sobre o **mesmo**
    bruto gravavam Parquets diferentes (Anti-SPEC §10.4.22).
    """
    orfao = tmp_path / "td.csv"
    orfao.write_bytes(b"a;b\n1;2\n")
    assert ler_manifesto(orfao) is None

    with pytest.raises(ManifestoAusente, match="bruto sem manifesto legível"):
        collected_at_do_bruto(orfao)

    # A saída é declarar a safra por escrito, não afrouxar a guarda.
    declarada = datetime(2026, 10, 10, 23, 0, tzinfo=UTC)
    assert collected_at_do_bruto(orfao, collected_at=declarada) == declarada


def test_collected_at_explicito_tem_precedencia_sobre_o_manifesto(tmp_path: Path) -> None:
    """Reprocessamento deliberado assume a safra; o manifesto é o default, não uma trava."""
    resultado = arquivar_bruto(
        b"[]",
        destino=tmp_path / "data" / "raw" / "sgs",
        nome="433__2026-10-10.json",
        obtido_em=datetime(2026, 10, 10, 23, 49, tzinfo=UTC),
    )
    declarada = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    assert collected_at_do_bruto(resultado.caminho, collected_at=declarada) == declarada


def test_corpo_vazio_e_arquivavel_porque_ausencia_pode_ser_normal(tmp_path: Path) -> None:
    """R17 / `ausencia_e_caso_normal`: dia sem divulgação da ANBIMA chega como 0 bytes."""
    resultado = arquivar_bruto(
        b"", destino=tmp_path / "data" / "raw" / "anbima-ms", nome="ms__2026-10-11.txt"
    )
    assert resultado.bytes_gravados == 0
    assert resultado.caminho.is_file()


def test_arquivamento_nao_deixa_temporario_para_tras(tmp_path: Path) -> None:
    """Escrita atômica: nenhum `.tmp` sobra em `data/raw/` depois do sucesso."""
    destino = tmp_path / "data" / "raw" / "sgs"
    arquivar_bruto(b"[]", destino=destino, nome="433__2026-10-10.json")
    assert [p.name for p in destino.iterdir() if p.name.endswith(".tmp")] == []


# ─────────────────────────────────────────────────────────────────────────────
# data/processed/ — nada entra sem pandera (apoia CA-003)
# ─────────────────────────────────────────────────────────────────────────────


def _quadro_valido() -> pd.DataFrame:
    """Duas observações reais de IPCA (SGS 433) no formato de `ProcessedSeriesSchema`.

    Valores confirmados em `SPEC CA-002`: ago/2026 = -0,32 · set/2026 = 0,82.
    """
    return pd.DataFrame(
        {
            "series_id": ["IPCA_MENSAL", "IPCA_MENSAL"],
            "date": pd.to_datetime(["2026-08-01", "2026-09-01"]),
            "value": [-0.32, 0.82],
            "source": ["BCB_SGS", "BCB_SGS"],
            "freq": ["M", "M"],
            "vintage": pd.to_datetime(["2026-10-10", "2026-10-10"]),
            "unit": ["%", "%"],
            "collected_at": pd.to_datetime(["2026-10-10", "2026-10-10"]),
        }
    )


def test_gravar_processado_valida_com_pandera_antes_de_escrever(tmp_path: Path) -> None:
    """Caminho feliz: valida e grava Parquet legível com as mesmas 8 colunas do contrato."""
    destino = gravar_processado_parquet(_quadro_valido(), nome="sgs_433.parquet", raiz=tmp_path)
    assert destino.is_file()
    relido = pd.read_parquet(destino)
    assert len(relido) == 2
    assert list(relido.columns) == list(_quadro_valido().columns)
    assert relido["value"].to_list() == [-0.32, 0.82]


def test_quadro_invalido_nao_deixa_nada_em_processed(tmp_path: Path) -> None:
    """Tradução de CA-003 para a camada processada: falha de contrato ⇒ pasta intacta.

    Aqui a violação é `source='INVENTADA'`, que não está em `FONTES_VALIDAS` — o mesmo guarda
    que impede uma resposta de erro parseada "na mão" de virar linha de série.
    """
    invalido = _quadro_valido().assign(source=["INVENTADA", "INVENTADA"])
    with pytest.raises(SchemaErrors):
        gravar_processado_parquet(invalido, nome="sgs_433.parquet", raiz=tmp_path)
    assert not caminho_processed("sgs_433.parquet", raiz=tmp_path).exists()


def test_data_futura_em_relacao_a_coleta_e_rejeitada(tmp_path: Path) -> None:
    """`date > collected_at` é a meta Selic com data futura — `RawSeriesSchema` já proíbe."""
    invalido = _quadro_valido().assign(date=pd.to_datetime(["2027-01-01", "2027-02-01"]))
    with pytest.raises(SchemaErrors):
        gravar_processado_parquet(invalido, nome="sgs_433.parquet", raiz=tmp_path)
    assert not caminho_processed("sgs_433.parquet", raiz=tmp_path).exists()
