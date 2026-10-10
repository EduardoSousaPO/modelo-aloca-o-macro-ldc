"""F-001 — cliente HTTP: User-Agent, shape de resposta, retry, janela e ausência de rede.

CAs cobertos aqui: **CA-003** (HTTP 200 com corpo de erro → levanta e não grava),
**CA-045** (requisição sem UA é bloqueada por asserção do cliente), **CA-123** (nenhuma chamada de
rede no CI). Riscos: R1, R2, R4, R5, R21. Anti-SPEC: §10.1.5, §10.4.23.

A rede entra no `ClienteHTTP` por um `Transporte` injetado. Todo teste deste arquivo usa um
transporte falso que devolve **fixture gravada** — e um dos testes prova, bloqueando
`socket.socket`, que nenhum socket chega a ser aberto.
"""

from __future__ import annotations

import ast
import re
import socket
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from apps.pipeline.common import io_layers
from apps.pipeline.common.errors import (
    FalhaDeTransporte,
    FonteIndisponivel,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    UserAgentObrigatorio,
)
from apps.pipeline.common.http import (
    BACKOFF_BASE_S,
    JANELA_SGS_DIARIA_DIAS,
    JANELA_SGS_RECOMENDADA_DIAS,
    USER_AGENT_BROWSER,
    ClienteHTTP,
    RespostaBruta,
    cabecalhos_de_browser,
    exigir_contagem_minima,
    fatiar_janela,
    validar_corpo_json_array,
)
from packages.shared.schemas import ExtractorConfig, Fonte

# ─────────────────────────────────────────────────────────────────────────────
# Infra do teste — transporte falso, nunca rede
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixtures_common(dir_fixtures: Path) -> Path:
    """`tests/fixtures/common/` — procedência de cada arquivo no README da pasta."""
    return dir_fixtures / "common"


@pytest.fixture
def config_sgs() -> ExtractorConfig:
    """`ExtractorConfig` do SGS — o mesmo contrato que os extratores de Onda 1 vão usar."""
    return ExtractorConfig(
        nome="bcb_sgs_ipca",
        fonte=Fonte.BCB_SGS,
        series_ids=("IPCA_MENSAL",),
        base_url="https://api.bcb.gov.br/dados/serie/bcdata.sgs.433",
        formato="json",
        encoding="utf-8",
        janela_maxima_dias=JANELA_SGS_RECOMENDADA_DIAS,
        contagem_minima_esperada=249,
        destino_raw="data/raw/sgs",
        timeout_s=30.0,
        max_retries=2,
    )


class TransporteGravado:
    """Transporte falso: devolve respostas pré-definidas e registra o que recebeu."""

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
        self.chamadas.append(
            {
                "metodo": metodo,
                "url": url,
                "params": params,
                "dados": dados,
                "cabecalhos": dict(cabecalhos),
                "timeout_s": timeout_s,
            }
        )
        proxima = self._respostas.pop(0) if self._respostas else None
        if proxima is None:
            msg = f"transporte falso sem resposta programada para {metodo} {url}"
            raise AssertionError(msg)
        if isinstance(proxima, Exception):
            raise proxima
        return proxima


def _resposta(
    conteudo: bytes, *, status: int = 200, url: str = "https://exemplo.invalid/dados", **cabecalhos
) -> RespostaBruta:
    return RespostaBruta(
        url=url,
        status=status,
        conteudo=conteudo,
        cabecalhos=cabecalhos,
        obtida_em=datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CA-045 — requisição sem UA é bloqueada por asserção do cliente
# ─────────────────────────────────────────────────────────────────────────────


def test_ca045_requisicao_sem_user_agent_e_bloqueada_pelo_cliente(
    config_sgs: ExtractorConfig,
) -> None:
    """CA-045: sem UA o cliente **levanta antes de despachar** (R4: Yahoo responde 429).

    O teste não pode provar o 429 do Yahoo sem rede (Anti-SPEC §10.4.23); prova a asserção que
    torna o 429 inalcançável — nenhuma requisição sai sem UA.
    """
    transporte = TransporteGravado(_resposta(b"[]"))
    cliente = ClienteHTTP(config_sgs, transporte=transporte, cabecalhos_base={})

    with pytest.raises(UserAgentObrigatorio, match="sem User-Agent"):
        cliente.get("/dados")

    assert transporte.chamadas == [], "nada deveria ter sido despachado"


def test_ca045_user_agent_em_branco_tambem_e_bloqueado(config_sgs: ExtractorConfig) -> None:
    """UA presente mas vazio é o mesmo que UA ausente para o Yahoo e para o CKAN do BCB."""
    transporte = TransporteGravado(_resposta(b"[]"))
    cliente = ClienteHTTP(config_sgs, transporte=transporte, cabecalhos_base={"User-Agent": "   "})
    with pytest.raises(UserAgentObrigatorio):
        cliente.get("/dados")
    assert transporte.chamadas == []


def test_ca045_cliente_padrao_manda_user_agent_de_browser(config_sgs: ExtractorConfig) -> None:
    """O outro lado do CA-045: por default, toda requisição leva UA de browser."""
    transporte = TransporteGravado(_resposta(b"[]"))
    cliente = ClienteHTTP(config_sgs, transporte=transporte)
    cliente.get("/dados")

    enviado = transporte.chamadas[0]["cabecalhos"]["User-Agent"]
    assert enviado == USER_AGENT_BROWSER
    assert "Mozilla/5.0" in enviado and "Chrome/" in enviado
    assert transporte.chamadas[0]["timeout_s"] == config_sgs.timeout_s


def test_cabecalho_extra_nao_apaga_o_user_agent() -> None:
    """A B3 exige `Referer` além do UA: somar cabeçalho não pode remover o que já havia."""
    cabecalhos = cabecalhos_de_browser({"Referer": "https://sistemaswebb3-listados.b3.com.br/"})
    assert cabecalhos["User-Agent"] == USER_AGENT_BROWSER
    assert cabecalhos["Referer"].startswith("https://sistemaswebb3-listados")


def test_fonte_que_dispensa_ua_nao_e_bloqueada(config_sgs: ExtractorConfig) -> None:
    """`requer_user_agent_browser=False` desliga a asserção: a decisão é do contrato."""
    config = config_sgs.model_copy(update={"requer_user_agent_browser": False})
    transporte = TransporteGravado(_resposta(b"[]"))
    cliente = ClienteHTTP(config, transporte=transporte, cabecalhos_base={})
    assert cliente.get("/dados").status == 200


# ─────────────────────────────────────────────────────────────────────────────
# CA-003 — HTTP 200 com corpo de erro → levanta e não grava
# ─────────────────────────────────────────────────────────────────────────────


def test_ca003_http200_com_corpo_de_erro_levanta_e_nao_grava_nada(
    config_sgs: ExtractorConfig,
    fixtures_common: Path,
    tmp_path: Path,
) -> None:
    """CA-003 / Anti-SPEC §10.1.5: corpo de erro com status 200 levanta e nada é gravado.

    Fixture: `sgs_433__erro.json` — o corpo verbatim que o SGS devolve quando a janela de série
    diária passa de 10 anos (R1). O status é **200**: nenhum `raise_for_status` pegaria isto.
    """
    corpo = (fixtures_common / "sgs_433__erro.json").read_bytes()
    transporte = TransporteGravado(_resposta(corpo, status=200))
    cliente = ClienteHTTP(config_sgs, transporte=transporte)

    processed = io_layers.caminho_camada(io_layers.Camada.PROCESSED, raiz=tmp_path)
    raw = io_layers.caminho_destino_raw(config_sgs, raiz=tmp_path)

    with pytest.raises(RespostaDeErroComStatus200, match="janela de consulta"):
        cliente.json_array("/dados")

    assert transporte.chamadas[0]["metodo"] == "GET"  # a requisição aconteceu
    assert not processed.exists(), "nada pode ter sido gravado em data/processed/"
    assert not raw.exists(), "nem em data/raw/ — o corpo de erro não é dado bruto da série"


def test_ca003_caminho_feliz_devolve_as_observacoes(
    config_sgs: ExtractorConfig, fixtures_common: Path
) -> None:
    """Contraprova do CA-003: o mesmo caminho aceita a resposta boa e devolve o array.

    Fixture `sgs_433__2026-10-10.json` com os valores de IPCA confirmados em CA-002
    (ago/2026 = -0,32 · set/2026 = 0,82). A fixture é uma **amostra de 2 linhas** (limite de
    200 KB do `tests/fixtures/README.md`), então aqui a guarda de contagem fica desligada
    explicitamente — com o mínimo do contrato ela levantaria, e deve (ver QA-02 abaixo).
    """
    corpo = (fixtures_common / "sgs_433__2026-10-10.json").read_bytes()
    cliente = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(corpo)))

    observacoes = cliente.json_array("/dados", minimo=None)
    assert [o["data"] for o in observacoes] == ["01/08/2026", "01/09/2026"]
    assert [o["valor"] for o in observacoes] == ["-0.32", "0.82"]


def test_ca003_html_com_status_200_e_recusado(fixtures_common: Path) -> None:
    """Série inexistente no SGS devolve **HTML** com status 200 (R1).

    A fixture usada é o HTML real da Curva Zero da ANBIMA: serve como corpo HTML servido onde se
    esperava dado, que é exatamente a classe de falha. Não fabriquei um HTML de erro do SGS — a
    pesquisa não gravou esse corpo.
    """
    corpo = (fixtures_common / "anbima_cz__2026-10-09.html").read_bytes()
    with pytest.raises(RespostaDeErroComStatus200, match="corpo HTML"):
        validar_corpo_json_array(_resposta(corpo, status=200))


@pytest.mark.parametrize(
    "corpo",
    [
        b"",
        b'{"erro":"serie nao encontrada"}',
        b'{"errors":["x"]}',
        b'{"data":"01/09/2026","valor":"0.82"}',  # objeto, não array
        b'"so uma string"',
        b"[{truncado",
    ],
)
def test_corpos_invalidos_nao_viram_dado(corpo: bytes) -> None:
    """Payload vazio, truncado, objeto no lugar de array: tudo levanta, nada é parseado."""
    with pytest.raises(RespostaDeErroComStatus200):
        validar_corpo_json_array(_resposta(corpo, status=200))


# ─────────────────────────────────────────────────────────────────────────────
# CA-123 — nenhuma chamada de rede
# ─────────────────────────────────────────────────────────────────────────────


def test_ca123_cliente_com_transporte_falso_nao_abre_socket(
    config_sgs: ExtractorConfig,
    fixtures_common: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-123 / Anti-SPEC §10.4.23: com `socket.socket` proibido, o fluxo completo ainda passa.

    Se alguma parte do cliente tentasse resolver DNS ou abrir conexão, o teste quebraria aqui —
    e não no CI, dias depois, com a fonte fora do ar.
    """

    def socket_proibido(*_args: object, **_kwargs: object) -> None:
        msg = "teste unitário tentou abrir socket (Anti-SPEC §10.4.23)"
        raise AssertionError(msg)

    monkeypatch.setattr(socket, "socket", socket_proibido)
    monkeypatch.setattr(socket, "create_connection", socket_proibido)
    monkeypatch.setattr(socket, "getaddrinfo", socket_proibido)

    corpo = (fixtures_common / "sgs_433__2026-10-10.json").read_bytes()
    cliente = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(corpo)))
    assert len(cliente.json_array("/dados", minimo=None)) == 2


def test_ca123_modulo_http_nao_importa_requests_no_topo(raiz_repo: Path) -> None:
    """`import requests` vive dentro de `transporte_requests`, não no topo do módulo.

    É o que garante que importar a infra num teste unitário não arraste a pilha de rede.
    """
    arquivo = raiz_repo / "apps" / "pipeline" / "common" / "http.py"
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    topo = {
        alias.name.split(".")[0]
        for no in arvore.body
        if isinstance(no, ast.Import)
        for alias in no.names
    } | {
        no.module.split(".")[0]
        for no in arvore.body
        if isinstance(no, ast.ImportFrom) and no.module
    }
    assert "requests" not in topo
    assert "httpx" not in topo


def test_ca123_ci_e_pytest_excluem_a_marca_network(raiz_repo: Path) -> None:
    """O contrato do CI: marca `network` declarada e job N1 rodando com `-m "not network"`."""
    pyproject = (raiz_repo / "pyproject.toml").read_text(encoding="utf-8")
    assert '"network: teste que faz chamada real' in pyproject
    assert "--strict-markers" in pyproject

    ci = (raiz_repo / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'pytest tests/unit -m "not network"' in ci


def test_ca123_nenhum_teste_deste_arquivo_precisa_de_rede() -> None:
    """Esta suíte de F-001 roda inteira com `-m "not network"`: nada aqui é deselecionado.

    A guarda é escopada a este arquivo de propósito. Marcar um teste como `network` é legítimo
    (`AGENTS.md §6` — ele roda local e o CI o exclui); o que não é legítimo é a infra **precisar**
    de rede para ser testada.
    """
    conteudo = Path(__file__).read_text(encoding="utf-8")
    decorados = re.findall(r"^\s*@pytest\.mark\.network\b", conteudo, flags=re.MULTILINE)
    assert decorados == [], "a infra de extração não pode depender de rede para ser testada"


# ─────────────────────────────────────────────────────────────────────────────
# Retry com backoff e timeout (R5, R22)
# ─────────────────────────────────────────────────────────────────────────────


def test_retry_com_backoff_exponencial_recupera_na_terceira_tentativa(
    config_sgs: ExtractorConfig,
) -> None:
    """Falha de transporte e 502 são retentados; o backoff dobra a cada tentativa.

    R5 mediu no FRED exatamente esta sequência (`ReadTimeout`, depois `ConnectionReset`) e o SGS
    é conhecido por 502 intermitente (R22).
    """
    transporte = TransporteGravado(
        FalhaDeTransporte("ReadTimeout"),
        _resposta(b"", status=502),
        _resposta(b"[]"),
    )
    dormidas: list[float] = []
    cliente = ClienteHTTP(config_sgs, transporte=transporte, dormir=dormidas.append)

    assert cliente.get("/dados").status == 200
    assert len(transporte.chamadas) == 3
    assert dormidas == [BACKOFF_BASE_S, BACKOFF_BASE_S * 2]


def test_retry_esgotado_vira_fonte_indisponivel(config_sgs: ExtractorConfig) -> None:
    """Esgotado o retry, o erro é explícito — nenhum extrator "completa" a série sozinho."""
    transporte = TransporteGravado(*[_resposta(b"", status=503)] * 3)
    cliente = ClienteHTTP(config_sgs, transporte=transporte, dormir=lambda _: None)

    with pytest.raises(FonteIndisponivel, match="esgotadas 3 tentativas"):
        cliente.get("/dados")
    assert len(transporte.chamadas) == config_sgs.max_retries + 1


def test_404_nao_e_retentado(config_sgs: ExtractorConfig) -> None:
    """404 é URL errada: repetir só gasta tempo e esconde o bug."""
    transporte = TransporteGravado(_resposta(b"nao encontrado", status=404))
    cliente = ClienteHTTP(config_sgs, transporte=transporte, dormir=lambda _: None)

    with pytest.raises(FonteIndisponivel, match="não retentável"):
        cliente.get("/dados")
    assert len(transporte.chamadas) == 1


def test_429_e_retentado(config_sgs: ExtractorConfig) -> None:
    """429 é o que o Yahoo devolve sob pressão (R4): vale esperar e repetir."""
    transporte = TransporteGravado(_resposta(b"", status=429), _resposta(b"[]"))
    cliente = ClienteHTTP(config_sgs, transporte=transporte, dormir=lambda _: None)
    assert cliente.get("/dados").status == 200


# ─────────────────────────────────────────────────────────────────────────────
# Cache condicional (R21) — primitiva; a política por fonte é F-030
# ─────────────────────────────────────────────────────────────────────────────


def test_cache_condicional_manda_validadores_e_entende_304() -> None:
    """R21: o CSV do Tesouro tem 14,6 MB e é re-baixado por dia — 304 evita o download inteiro."""
    config = ExtractorConfig(
        nome="tesouro_direto",
        fonte=Fonte.TESOURO_CKAN,
        series_ids=("NTNB_TAXAS",),
        base_url="https://www.tesourotransparente.gov.br/ckan/dataset/download/td.csv",
        formato="csv",
        encoding="latin-1",
        cache_condicional=True,
        destino_raw="data/raw/tesouro-direto",
    )
    transporte = TransporteGravado(_resposta(b"", status=304))
    cliente = ClienteHTTP(config, transporte=transporte)

    resposta = cliente.get(etag='W/"abc123"', last_modified="Fri, 09 Oct 2026 03:00:00 GMT")
    enviados = transporte.chamadas[0]["cabecalhos"]
    assert enviados["If-None-Match"] == 'W/"abc123"'
    assert enviados["If-Modified-Since"] == "Fri, 09 Oct 2026 03:00:00 GMT"
    assert resposta.nao_modificada


def test_sem_cache_condicional_nao_manda_validadores(config_sgs: ExtractorConfig) -> None:
    """`cache_condicional=False` no contrato ⇒ nenhum `If-*` sai, mesmo se quem chama insistir."""
    transporte = TransporteGravado(_resposta(b"[]"))
    cliente = ClienteHTTP(config_sgs, transporte=transporte)
    cliente.get("/dados", etag='W/"abc123"')
    assert "If-None-Match" not in transporte.chamadas[0]["cabecalhos"]


def test_etag_e_last_modified_saem_da_resposta() -> None:
    """Os validadores lidos da resposta são o que vai para o manifesto em `data/raw/`."""
    cabecalhos = {"ETag": 'W/"xyz"', "Last-Modified": "Thu, 08 Oct 2026 03:00:00 GMT"}
    resposta = _resposta(b"[]", **cabecalhos)
    assert resposta.etag == 'W/"xyz"'
    assert resposta.last_modified == "Thu, 08 Oct 2026 03:00:00 GMT"


# ─────────────────────────────────────────────────────────────────────────────
# R2 — truncamento silencioso
# ─────────────────────────────────────────────────────────────────────────────


def test_contagem_minima_pega_truncamento_silencioso() -> None:
    """R2: Olinda devolve 20.000 linhas sem `nextLink`; sem contagem mínima, ninguém percebe."""
    assert exigir_contagem_minima(249, minimo=249, origem="sgs.433") == 249
    with pytest.raises(RespostaTruncada, match="truncamento silencioso"):
        exigir_contagem_minima(20_000, minimo=20_001, origem="olinda")


def test_contagem_minima_desligada_quando_o_contrato_nao_declara() -> None:
    """`contagem_minima_esperada=None` não inventa um mínimo — só não checa."""
    assert exigir_contagem_minima(3, minimo=None, origem="qualquer") == 3


# ─────────────────────────────────────────────────────────────────────────────
# QA-02 (P1) — json_array aplica a contagem mínima do contrato
# ─────────────────────────────────────────────────────────────────────────────


def _corpo_com(n: int) -> bytes:
    """Corpo JSON do SGS com `n` observações, no shape verbatim de `research §A1`."""
    itens = ",".join(f'{{"data":"01/0{m % 9 + 1}/2026","valor":"0.82"}}' for m in range(n))
    return f"[{itens}]".encode()


@pytest.mark.parametrize("quantidade", [0, 1, 200, 248])
def test_qa02_json_array_levanta_quando_fica_abaixo_do_minimo_do_contrato(
    config_sgs: ExtractorConfig, quantidade: int
) -> None:
    """QA-02 (P1): corpo curto com HTTP 200 e mínimo 249 declarado **levanta**.

    O furo era este: `exigir_contagem_minima` existia, funcionava e **nunca era chamada** no
    caminho padrão, então `[]` com status 200 passava como sucesso num contrato que declara 249
    observações (R2 — truncamento silencioso de Olinda/Yahoo/FRED).
    """
    assert config_sgs.contagem_minima_esperada == 249
    cliente = ClienteHTTP(
        config_sgs, transporte=TransporteGravado(_resposta(_corpo_com(quantidade)))
    )
    with pytest.raises(RespostaTruncada, match="truncamento silencioso"):
        cliente.json_array("/dados")


def test_qa02_json_array_passa_quando_atinge_o_minimo(config_sgs: ExtractorConfig) -> None:
    """Exatamente no mínimo (249) passa: a guarda é `<`, não `<=`."""
    cliente = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(_corpo_com(249))))
    assert len(cliente.json_array("/dados")) == 249


def test_qa02_minimo_none_desliga_a_guarda_para_janela_fatiada(
    config_sgs: ExtractorConfig,
) -> None:
    """Em janela fatiada o mínimo do contrato é o **total**, não o da fatia.

    Por isso `minimo=None` existe: quem fatia checa o total concatenado uma vez, depois do laço.
    """
    cliente = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(_corpo_com(60))))
    assert len(cliente.json_array("/dados", minimo=None)) == 60


def test_qa02_minimo_explicito_sobrepoe_o_contrato(config_sgs: ExtractorConfig) -> None:
    """`minimo=<int>` é o esperado **daquela** requisição — mais apertado ou mais frouxo."""
    cliente = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(_corpo_com(60))))
    assert len(cliente.json_array("/dados", minimo=60)) == 60

    outro = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(_corpo_com(60))))
    with pytest.raises(RespostaTruncada):
        outro.json_array("/dados", minimo=61)


def test_qa02_contrato_sem_minimo_nao_inventa_um(config_sgs: ExtractorConfig) -> None:
    """`contagem_minima_esperada=None` no contrato ⇒ `json_array` não checa contagem."""
    config = config_sgs.model_copy(update={"contagem_minima_esperada": None})
    cliente = ClienteHTTP(config, transporte=TransporteGravado(_resposta(b"[]")))
    assert cliente.json_array("/dados") == []


def test_qa02_corpo_de_erro_tem_precedencia_sobre_a_contagem(
    config_sgs: ExtractorConfig, fixtures_common: Path
) -> None:
    """Ordem importa: shape primeiro, contagem depois.

    Um corpo de erro com HTTP 200 tem de levantar `RespostaDeErroComStatus200` (diagnóstico certo),
    não `RespostaTruncada` ("série curta", que mandaria o leitor caçar paginação inexistente).
    """
    corpo = (fixtures_common / "sgs_433__erro.json").read_bytes()
    cliente = ClienteHTTP(config_sgs, transporte=TransporteGravado(_resposta(corpo)))
    with pytest.raises(RespostaDeErroComStatus200):
        cliente.json_array("/dados")


# ─────────────────────────────────────────────────────────────────────────────
# Pegadinha nº 1 do SGS — janela de 10 anos em série diária
# ─────────────────────────────────────────────────────────────────────────────


def test_fatiar_janela_de_20_anos_respeita_o_limite_do_sgs() -> None:
    """A janela 2006→2026 em série diária precisa virar fatias ≤ 10 anos (`§A1` pegadinha nº 1)."""
    inicio, fim = date(2006, 1, 1), date(2026, 9, 30)
    fatias = fatiar_janela(inicio, fim, janela_maxima_dias=JANELA_SGS_RECOMENDADA_DIAS)

    assert fatias[0][0] == inicio
    assert fatias[-1][1] == fim
    assert all((f - i).days + 1 <= JANELA_SGS_RECOMENDADA_DIAS for i, f in fatias), (
        "nenhuma fatia pode passar da janela declarada"
    )
    assert all((f - i).days + 1 <= JANELA_SGS_DIARIA_DIAS for i, f in fatias)


def test_fatias_sao_contiguas_e_sem_sobreposicao() -> None:
    """Concatenar as fatias não pode duplicar nem perder um único dia."""
    fatias = fatiar_janela(date(2006, 1, 1), date(2026, 9, 30), janela_maxima_dias=1826)
    for (_, fim_anterior), (inicio_seguinte, _) in zip(fatias, fatias[1:], strict=False):
        assert (inicio_seguinte - fim_anterior).days == 1


def test_serie_mensal_nao_e_fatiada() -> None:
    """Séries mensais/trimestrais não têm o limite: `None` ⇒ uma requisição só (`§A1`)."""
    fatias = fatiar_janela(date(2006, 1, 1), date(2026, 9, 1), janela_maxima_dias=None)
    assert fatias == ((date(2006, 1, 1), date(2026, 9, 1)),)


def test_janela_invertida_levanta() -> None:
    """`fim < inicio` é erro de chamada, não uma janela vazia aceitável."""
    with pytest.raises(ValueError, match="janela invertida"):
        fatiar_janela(date(2026, 1, 1), date(2006, 1, 1), janela_maxima_dias=365)


def test_janela_de_um_dia_devolve_uma_fatia() -> None:
    """Caso-limite do job diário: início igual ao fim."""
    dia = date(2026, 10, 8)
    assert fatiar_janela(dia, dia, janela_maxima_dias=1826) == ((dia, dia),)
