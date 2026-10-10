"""Testes de F-009 — job diário de arquivamento ANBIMA (CA-027, CA-028, CA-029).

Todos os testes rodam sobre **fixtures gravadas** da fonte (`tests/fixtures/anbima-ms/` e
`tests/fixtures/anbima-ettj/`), sem rede — Anti-SPEC §10.4.23. O único teste que chama a ANBIMA viva
está marcado `@pytest.mark.network` e é excluído do CI N1 com `-m "not network"`.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from apps.pipeline.jobs import anbima_daily as job

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MS_DIR = FIXTURES / "anbima-ms"
CZ_DIR = FIXTURES / "anbima-ettj"

DIA = date(2026, 10, 9)
DIA_ANTERIOR = date(2026, 10, 8)


def ler(caminho: Path) -> bytes:
    return caminho.read_bytes()


@pytest.fixture
def ms_bytes() -> bytes:
    return ler(MS_DIR / "ms__2026-10-09.txt")


@pytest.fixture
def cz_bytes() -> bytes:
    return ler(CZ_DIR / "cz__2026-10-09.csv")


Buscar = Callable[[job.FonteDiaria, date], job.Resposta]


def buscador(corpo: bytes, http_status: int = 200) -> Buscar:
    """Fetcher determinístico: devolve sempre o mesmo corpo, sem tocar a rede."""

    def _buscar(fonte: job.FonteDiaria, dia: date) -> job.Resposta:
        return job.Resposta(url=fonte.url_para(dia), http_status=http_status, corpo=corpo)

    return _buscar


# ── CA-029 — parse do ms*.txt ────────────────────────────────────────────────────────────────────


def test_parse_ms_le_separador_arroba_skiprows2_latin1(ms_bytes: bytes) -> None:
    resultado = job.parse_ms(ms_bytes)
    assert resultado.data_ref == DIA
    # Contagem mínima real (50 vencimentos em 09/10/2026) — não `> 0`, que deixa passar truncamento.
    assert resultado.n_registros == 50


def test_parse_ms_reconhece_os_cinco_titulos(ms_bytes: bytes) -> None:
    tabela = pd.read_csv(io.BytesIO(ms_bytes), sep="@", skiprows=2, encoding="latin-1", decimal=",")
    titulos = {t.strip() for t in tabela["Titulo"]}
    assert titulos == {"LTN", "LFT", "NTN-B", "NTN-C", "NTN-F"}
    assert job.parse_ms(ms_bytes).detalhe.startswith("50 vencimentos")


def test_parse_ms_decimal_virgula_e_valores_canario(ms_bytes: bytes) -> None:
    """3 valores-canário de 09/10/2026 conferidos na fonte (ms261009.txt + merc-sec/default.asp)."""
    tabela = pd.read_csv(io.BytesIO(ms_bytes), sep="@", skiprows=2, encoding="latin-1", decimal=",")
    chave = tabela.set_index(["Titulo", "Data Vencimento"])
    assert chave.loc[("LTN", 20270401), "Tx. Indicativas"] == pytest.approx(13.0937, abs=1e-4)
    assert chave.loc[("NTN-B", 20450515), "Tx. Indicativas"] == pytest.approx(6.6060, abs=1e-4)
    assert chave.loc[("NTN-C", 20310101), "PU"] == pytest.approx(7887.26375, abs=1e-5)


def test_parse_ms_encoding_explicito_preserva_acento(ms_bytes: bytes) -> None:
    """O cabeçalho institucional tem 'Associação': latin-1 explícito, nunca o default do locale."""
    assert "Associação" in ms_bytes.decode("latin-1").splitlines()[0]


def test_parse_ms_truncado_e_rejeitado(ms_bytes: bytes) -> None:
    truncado = ms_bytes[:900]  # recorte da fixture real, não dado sintético
    with pytest.raises(job.CorpoInvalido):
        job.parse_ms(truncado)


# ── CA-029 — parse da Curva Zero ─────────────────────────────────────────────────────────────────


def test_parse_curva_zero_betas_e_vertices(cz_bytes: bytes) -> None:
    resultado = job.parse_curva_zero(cz_bytes)
    assert resultado.data_ref == DIA
    assert resultado.n_registros == 65  # vértices de 252 a 8.316 dias úteis, passo 126
    assert "PREFIXADOS+IPCA" in resultado.detalhe


def test_parse_curva_zero_valores_canario(cz_bytes: bytes) -> None:
    """3 valores-canário de 09/10/2026 conferidos na fonte (CZ-down.asp, saidas csv e xls)."""
    linhas = cz_bytes.decode("latin-1").splitlines()
    prefixados = next(ln for ln in linhas if ln.startswith("PREFIXADOS;")).split(";")
    assert job._para_float_br(prefixados[1]) == pytest.approx(0.11977147726174, rel=1e-12)
    vertice_252 = next(ln for ln in linhas if ln.startswith("252;")).split(";")
    assert job._para_float_br(vertice_252[1]) == pytest.approx(6.2834, abs=1e-4)  # ETTJ IPCA
    assert job._para_float_br(vertice_252[2]) == pytest.approx(12.5792, abs=1e-4)  # ETTJ PREF


def test_parse_curva_zero_vertice_com_ponto_de_milhar(cz_bytes: bytes) -> None:
    """A coluna `Vertices` usa ponto como separador de milhar (`1.008`) — tem de virar 1008."""
    vertices = job._vertices_ettj(cz_bytes.decode("latin-1").splitlines())
    assert vertices[0] == 252
    assert 1008 in vertices
    assert vertices[-1] == 8316


def test_parse_curva_zero_notacao_cientifica() -> None:
    assert job._para_float_br("-4,58301615075328E-02") == pytest.approx(-0.0458301615075328)


# ── CA-029 / Anti-SPEC §10.1.5 — erro silencioso com HTTP 200 ────────────────────────────────────


def test_saida_xls_do_cz_e_html_e_rejeitada_por_magic_bytes() -> None:
    corpo = ler(CZ_DIR / "cz__saida_xls_e_html.html")
    assert corpo[:1] == b"<"
    problema = job.detectar_corpo_suspeito(corpo)
    assert problema is not None
    assert "HTML" in problema


def test_html_de_erro_com_corpo_grande_nao_e_gravado(tmp_path: Path) -> None:
    html_erro = ler(MS_DIR / "ms__erro_html.txt")
    resultado = job.arquivar_dia(
        job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(html_erro, http_status=200)
    )
    assert resultado.status == job.REJEITADO
    assert "HTML" in resultado.mensagem
    assert not list(tmp_path.rglob("ms_*"))


def test_zip_xlsx_onde_se_espera_texto_e_rejeitado() -> None:
    assert job.detectar_corpo_suspeito(b"PK\x03\x04qualquercoisa") is not None


def test_resposta_de_outra_data_e_rejeitada(tmp_path: Path, cz_bytes: bytes) -> None:
    """Pedir 08/10 e receber o arquivo de 09/10 (eco do último dia útil) → rejeita e não grava."""
    resultado = job.arquivar_dia(
        job.FONTE_CZ, DIA_ANTERIOR, raiz=tmp_path, buscar=buscador(cz_bytes)
    )
    assert resultado.status == job.REJEITADO
    assert "2026-10-09" in resultado.mensagem
    assert not list(tmp_path.rglob("cz_*"))


def test_contagem_minima_barra_truncamento_silencioso(tmp_path: Path, cz_bytes: bytes) -> None:
    fonte_exigente = replace(job.FONTE_CZ, contagem_minima=999)
    resultado = job.arquivar_dia(fonte_exigente, DIA, raiz=tmp_path, buscar=buscador(cz_bytes))
    assert resultado.status == job.REJEITADO
    assert "truncamento" in resultado.mensagem
    assert not list(tmp_path.rglob("cz_*"))


# ── CA-028 — ausência é caso normal ──────────────────────────────────────────────────────────────


def test_corpo_de_zero_bytes_e_sucesso_com_registro(tmp_path: Path) -> None:
    vazio = ler(CZ_DIR / "cz__vazio.csv")
    assert vazio == b""
    resultado = job.arquivar_dia(job.FONTE_CZ, DIA, raiz=tmp_path, buscar=buscador(vazio))
    assert resultado.status == job.AUSENTE
    assert resultado.ok is True
    assert "caso normal" in resultado.mensagem
    assert not list(tmp_path.rglob("cz_*"))


def test_http_404_e_sucesso_com_registro(tmp_path: Path) -> None:
    html_404 = ler(MS_DIR / "ms__erro_html.txt")
    resultado = job.arquivar_dia(
        job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(html_404, http_status=404)
    )
    assert resultado.status == job.AUSENTE
    assert resultado.ok is True
    assert not list(tmp_path.rglob("ms_*"))


def test_cli_sai_com_zero_quando_o_dia_esta_ausente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        job,
        "baixar",
        lambda fonte, dia, sessao=None: job.Resposta(
            url=fonte.url_para(dia), http_status=404, corpo=b""
        ),
    )
    codigo = job.main(["--date", "2026-10-09", "--out-root", str(tmp_path)])
    assert codigo == 0
    assert "ausente" in capsys.readouterr().out


def test_cli_sai_com_codigo_nao_zero_em_corpo_invalido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    html_erro = ler(MS_DIR / "ms__erro_html.txt")
    monkeypatch.setattr(
        job,
        "baixar",
        lambda fonte, dia, sessao=None: job.Resposta(
            url=fonte.url_para(dia), http_status=200, corpo=html_erro
        ),
    )
    codigo = job.main(["--date", "2026-10-09", "--fonte", "ms", "--out-root", str(tmp_path)])
    assert codigo == 1
    capturado = capsys.readouterr()
    assert "FALHA" in capturado.err
    assert "runbook" in capturado.err


def test_erro_de_rede_nao_grava_e_falha(tmp_path: Path) -> None:
    def cai(fonte: job.FonteDiaria, dia: date) -> job.Resposta:
        raise job.ErroDeRede("timeout de propósito")

    resultado = job.arquivar_dia(job.FONTE_MS, DIA, raiz=tmp_path, buscar=cai)
    assert resultado.status == job.ERRO_REDE
    assert resultado.ok is False
    assert "janela rolante" in resultado.mensagem


# ── CA-027 — idempotência ────────────────────────────────────────────────────────────────────────


def test_rodar_duas_vezes_nao_duplica_nem_reescreve(tmp_path: Path, ms_bytes: bytes) -> None:
    primeiro = job.arquivar_dia(job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(ms_bytes))
    assert primeiro.status == job.ARQUIVADO
    assert primeiro.arquivo is not None
    mtime_antes = primeiro.arquivo.stat().st_mtime_ns

    segundo = job.arquivar_dia(job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(ms_bytes))
    assert segundo.status == job.JA_ARQUIVADO
    assert segundo.ok is True
    assert segundo.sha256 == primeiro.sha256
    assert primeiro.arquivo.stat().st_mtime_ns == mtime_antes
    arquivos = sorted(p.name for p in (tmp_path / "data/raw/anbima-ms").glob("ms_*"))
    assert arquivos == ["ms_261009.txt", "ms_261009.txt.manifest.json"]


def test_revisao_da_fonte_vira_vintage_novo_sem_sobrescrever(
    tmp_path: Path, ms_bytes: bytes
) -> None:
    job.arquivar_dia(job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(ms_bytes))
    # mesma data de referência, conteúdo diferente (a ANBIMA republica taxa revisada)
    revisado = ms_bytes.replace(b"13,0937", b"13,0940", 1)
    assert revisado != ms_bytes
    segundo = job.arquivar_dia(job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(revisado))
    assert segundo.status == job.REVISAO_ARQUIVADA
    destino = tmp_path / "data/raw/anbima-ms"
    assert (destino / "ms_261009.txt").read_bytes() == ms_bytes  # original intacto
    assert (destino / "ms_261009__v2.txt").read_bytes() == revisado

    terceiro = job.arquivar_dia(job.FONTE_MS, DIA, raiz=tmp_path, buscar=buscador(revisado))
    assert terceiro.status == job.JA_ARQUIVADO  # o vintage também é idempotente


def test_executar_e_idempotente_para_as_duas_fontes(
    tmp_path: Path, ms_bytes: bytes, cz_bytes: bytes
) -> None:
    corpos = {job.FONTE_MS.nome: ms_bytes, job.FONTE_CZ.nome: cz_bytes}

    def buscar(fonte: job.FonteDiaria, dia: date) -> job.Resposta:
        return job.Resposta(url=fonte.url_para(dia), http_status=200, corpo=corpos[fonte.nome])

    primeira = job.executar([DIA], raiz=tmp_path, buscar=buscar)
    segunda = job.executar([DIA], raiz=tmp_path, buscar=buscar)
    assert [r.status for r in primeira] == [job.ARQUIVADO, job.ARQUIVADO]
    assert [r.status for r in segunda] == [job.JA_ARQUIVADO, job.JA_ARQUIVADO]
    assert len(list(tmp_path.rglob("*.manifest.json"))) == 2


# ── nome de arquivo por data e manifest ──────────────────────────────────────────────────────────


def test_nome_de_arquivo_usa_aammdd_nao_ddmmaa() -> None:
    assert job.FONTE_MS.nome_arquivo(DIA) == "ms_261009.txt"
    assert job.FONTE_CZ.nome_arquivo(DIA) == "cz_261009.csv"
    assert job.FONTE_MS.nome_arquivo(date(2026, 1, 2)) == "ms_260102.txt"
    assert job.FONTE_MS.nome_arquivo(DIA, vintage=3) == "ms_261009__v3.txt"


def test_url_do_ms_usa_aammdd() -> None:
    assert job.FONTE_MS.url_para(DIA).endswith("/ms261009.txt")
    assert job.FONTE_CZ.corpo_form is not None
    assert job.FONTE_CZ.corpo_form(DIA) == {
        "Idioma": "PT",
        "Dt_Ref": "09/10/2026",
        "saida": "csv",
    }


def test_manifest_tem_os_campos_obrigatorios(tmp_path: Path, cz_bytes: bytes) -> None:
    resultado = job.arquivar_dia(job.FONTE_CZ, DIA, raiz=tmp_path, buscar=buscador(cz_bytes))
    assert resultado.arquivo is not None
    manifest = json.loads(job.caminho_manifest(resultado.arquivo).read_text(encoding="utf-8"))
    for campo in ("url", "data_ref", "sha256", "bytes", "collected_at"):
        assert campo in manifest, campo
    assert manifest["data_ref"] == "2026-10-09"
    assert manifest["bytes"] == len(cz_bytes)
    assert manifest["sha256"] == job._sha256(resultado.arquivo.read_bytes())
    assert manifest["url"].endswith("CZ-down.asp")


def test_log_de_execucao_recebe_uma_linha_por_fonte_dia(tmp_path: Path, ms_bytes: bytes) -> None:
    resultados = job.executar(
        [DIA], fontes=(job.FONTE_MS,), raiz=tmp_path, buscar=buscador(ms_bytes)
    )
    caminho = job.registrar_log(resultados, raiz=tmp_path)
    linhas = caminho.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 1
    assert "anbima_ms\t2026-10-09\tarquivado" in linhas[0]


# ── janela de dias úteis ─────────────────────────────────────────────────────────────────────────


def test_dias_uteis_retroativos_pula_fim_de_semana() -> None:
    # 2026-10-10 é sábado; 11 é domingo.
    dias = job.dias_uteis_retroativos(date(2026, 10, 10), 3)
    assert dias == [date(2026, 10, 7), date(2026, 10, 8), date(2026, 10, 9)]
    assert all(d.weekday() < 5 for d in job.dias_uteis_retroativos(date(2026, 10, 10), 20))


def test_dias_uteis_retroativos_rejeita_zero() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        job.dias_uteis_retroativos(date(2026, 10, 9), 0)


def test_cli_rejeita_backfill_maior_que_a_janela(tmp_path: Path) -> None:
    assert job.main(["--backfill", "99", "--out-root", str(tmp_path)]) == 2
    assert job.main(["--backfill", "0", "--out-root", str(tmp_path)]) == 2
    assert job.main(["--date", "09/10/2026", "--out-root", str(tmp_path)]) == 2


# ── contrato com packages/shared/schemas ─────────────────────────────────────────────────────────


def test_extractor_config_declara_ausencia_como_caso_normal() -> None:
    pytest.importorskip("pandera", reason="pandera só existe no .venv (uv sync)")
    configs = job.extractor_configs()
    assert len(configs) == 2
    for config in configs:
        assert config.ausencia_e_caso_normal is True
        assert config.requer_user_agent_browser is True
        assert config.encoding == "latin-1"
        assert config.destino_raw.startswith("data/raw/anbima-")


# ── único teste que toca a fonte viva ────────────────────────────────────────────────────────────


@pytest.mark.network
def test_live_anbima_responde_e_arquiva(tmp_path: Path) -> None:
    """Teste live para o Edu conferir a fonte à mão. Não roda no CI (`-m "not network"`)."""
    dia = job.dias_uteis_retroativos(date.today(), 2)[0]
    resultados = job.executar([dia], raiz=tmp_path)
    assert [r.status for r in resultados] != []
    for resultado in resultados:
        assert resultado.ok, resultado.mensagem
