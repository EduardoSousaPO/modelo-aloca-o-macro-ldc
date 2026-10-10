"""Cliente HTTP da extração: User-Agent de browser, timeout, retry com backoff e guarda de shape.

Todo extrator deste projeto fala com a fonte por aqui. Os quatro comportamentos não negociáveis,
cada um amarrado a um risco **medido** em `docs/research/fontes-de-dados.md`:

1. **User-Agent de browser em toda requisição** (R4, CA-045). Yahoo sem UA → HTTP 429;
   `dadosabertos.bcb.gov.br` sem UA → página de erro; `api.investing.com` → 403 do Cloudflare.
   O cliente **levanta `UserAgentObrigatorio`** antes de despachar uma requisição sem UA — é
   asserção, não aviso.
2. **HTTP 200 não é sucesso** (R1, CA-003, Anti-SPEC §10.1.5). O SGS devolve
   `{"error": "...no máximo, 10 anos em séries de periodicidade diária"}` com status 200, e série
   inexistente devolve HTML com status 200. `validar_corpo_json_array` recusa os dois.
3. **Timeout e retry com backoff** por `ExtractorConfig` (`timeout_s`, `max_retries`). Só repete o
   que vale repetir: falha de transporte e status transitório (429/5xx). 404 não é retentado.
4. **Nada de rede em teste** (CA-123, Anti-SPEC §10.4.23). A rede entra por um `Transporte`
   injetável; o transporte real (`requests`) só é importado quando de fato se vai à rede, então o
   teste unitário com transporte falso nunca abre socket.

Mais duas guardas de apoio: `exigir_contagem_minima` (R2 — truncamento silencioso do Olinda, do
Yahoo e do FRED) e `fatiar_janela` (pegadinha nº 1 do SGS: série diária rejeita janela > ~10 anos).

Cache condicional (`If-None-Match` / `If-Modified-Since`) está aqui como **primitiva**: o
`ExtractorConfig.cache_condicional` já existe no contrato e o CSV do Tesouro tem 14,6 MB
re-baixados por dia (R21). A política por fonte — quando revalidar, quando forçar — é F-030.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

from apps.pipeline.common.errors import (
    FalhaDeTransporte,
    FonteIndisponivel,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    UserAgentObrigatorio,
)
from apps.pipeline.common.logging_setup import obter_logger
from apps.pipeline.common.parsing import FormatoDetectado, detectar_formato, ler_texto

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Callable, Mapping

    from packages.shared.schemas import ExtractorConfig

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Cabeçalhos (R4)
# ─────────────────────────────────────────────────────────────────────────────

#: UA de browser real. Não é cosmético: é a diferença entre 200 e 429 no Yahoo, e entre o JSON e a
#: página "Requisição Inválida" no portal de dados abertos do BCB (R4).
USER_AGENT_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CABECALHOS_DE_BROWSER: dict[str, str] = {
    "User-Agent": USER_AGENT_BROWSER,
    "Accept": "application/json, text/csv, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

#: Chaves que, num corpo JSON com HTTP 200, significam erro (R1). `message` e `syntax` acompanham
#: o `error` do SGS; `erro`/`mensagem` cobrem as variantes em português de outros endpoints.
CHAVES_DE_ERRO: frozenset[str] = frozenset({"error", "erro", "errors", "erros"})

#: Status que valem retry. 404/403/400 não valem: a URL está errada ou a fonte nos bloqueou.
STATUS_RETENTAVEIS: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

BACKOFF_BASE_S = 1.0
BACKOFF_MAXIMO_S = 30.0

#: Janela máxima aceita pelo SGS em série **diária** (R/A1 pegadinha nº 1): 10 anos funcionou,
#: 11 anos devolveu erro com HTTP 200. `RECOMENDADA` é a margem que a pesquisa sugere usar.
JANELA_SGS_DIARIA_DIAS = 3650
JANELA_SGS_RECOMENDADA_DIAS = 1826  # ~5 anos


class _DoContrato:
    """Sentinela de `json_array(minimo=...)`: "use o que o `ExtractorConfig` declarou"."""

    def __repr__(self) -> str:
        return "DO_CONTRATO"


#: Default de `ClienteHTTP.json_array(minimo=...)`. Distingue "não disse nada" (usa o contrato) de
#: `None` ("não checar aqui", caso da janela fatiada) e de um inteiro explícito.
DO_CONTRATO = _DoContrato()


def cabecalhos_de_browser(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Cabeçalhos de browser, com `extra` sobrescrevendo chave a chave (ex.: `Referer` da B3)."""
    cabecalhos = dict(CABECALHOS_DE_BROWSER)
    if extra:
        cabecalhos.update(extra)
    return cabecalhos


# ─────────────────────────────────────────────────────────────────────────────
# Resposta e transporte
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RespostaBruta:
    """Resposta crua: bytes + metadados. Nenhuma decodificação implícita.

    `texto(encoding)` exige o encoding porque a resposta não diz a verdade sobre ele: o `ms*.txt`
    da ANBIMA é latin-1 e não manda `charset` (R10, Anti-SPEC §10.4.26).
    """

    url: str
    status: int
    conteudo: bytes
    cabecalhos: Mapping[str, str] = field(default_factory=dict)
    obtida_em: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def nao_modificada(self) -> bool:
        """HTTP 304 — o arquivado continua válido (cache condicional, R21)."""
        return self.status == 304

    @property
    def etag(self) -> str | None:
        """`ETag` da resposta, se houver."""
        return self._cabecalho("etag")

    @property
    def last_modified(self) -> str | None:
        """`Last-Modified` da resposta, se houver."""
        return self._cabecalho("last-modified")

    @property
    def formato(self) -> FormatoDetectado:
        """Formato pelos magic bytes do corpo — a extensão da URL é irrelevante (R11)."""
        return detectar_formato(self.conteudo)

    def texto(self, encoding: str) -> str:
        """Decodifica o corpo com `encoding` **explícito**, em modo `strict`."""
        return ler_texto(self.conteudo, encoding)

    def _cabecalho(self, nome: str) -> str | None:
        for chave, valor in self.cabecalhos.items():
            if chave.lower() == nome:
                return valor
        return None


class Transporte(Protocol):
    """Camada que de fato fala TCP. Injetável para que o teste unitário não abra socket (CA-123)."""

    def __call__(
        self,
        metodo: str,
        url: str,
        *,
        params: Mapping[str, Any] | None,
        dados: Mapping[str, Any] | None,
        cabecalhos: Mapping[str, str],
        timeout_s: float,
    ) -> RespostaBruta:
        """Executa a requisição ou levanta `FalhaDeTransporte` em falha de rede."""
        ...


def transporte_requests(
    metodo: str,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    dados: Mapping[str, Any] | None = None,
    cabecalhos: Mapping[str, str],
    timeout_s: float,
) -> RespostaBruta:
    """Transporte real sobre `requests`. Importado aqui dentro, nunca no topo do módulo.

    Assim `import apps.pipeline.common.http` não arrasta `requests` nem abre sessão — o teste
    unitário com transporte falso jamais chega perto da rede (Anti-SPEC §10.4.23).
    """
    import requests

    try:
        resposta = requests.request(
            metodo,
            url,
            params=dict(params) if params else None,
            data=dict(dados) if dados else None,
            headers=dict(cabecalhos),
            timeout=timeout_s,
            allow_redirects=True,
        )
    except requests.RequestException as exc:  # timeout, reset, DNS — tudo retentável
        msg = f"{metodo} {url}: falha de transporte ({type(exc).__name__}: {exc})"
        raise FalhaDeTransporte(msg) from exc
    return RespostaBruta(
        url=resposta.url,
        status=resposta.status_code,
        conteudo=resposta.content,
        cabecalhos=dict(resposta.headers),
        obtida_em=datetime.now(tz=UTC),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cliente
# ─────────────────────────────────────────────────────────────────────────────


class ClienteHTTP:
    """Cliente de extração parametrizado por `ExtractorConfig`.

    ```python
    cliente = ClienteHTTP(config)                      # config é o ExtractorConfig da fonte
    dados = cliente.json_array("/dados", params={...})  # valida shape antes de devolver
    ```

    Nada de `requests.get` solto em extrator: UA, timeout e retry vivem aqui para que a
    correção de um deles valha para as 13 fontes de uma vez.
    """

    def __init__(
        self,
        config: ExtractorConfig,
        *,
        transporte: Transporte | None = None,
        cabecalhos_base: Mapping[str, str] | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._transporte: Transporte = transporte or transporte_requests
        self._cabecalhos_base = dict(
            cabecalhos_base if cabecalhos_base is not None else cabecalhos_de_browser()
        )
        self._dormir = dormir

    # ---------------------------------------------------------------- público

    def get(
        self,
        url: str | None = None,
        *,
        params: Mapping[str, Any] | None = None,
        cabecalhos_extra: Mapping[str, str] | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> RespostaBruta:
        """GET com UA, timeout, retry e (opcionalmente) revalidação condicional.

        `url` ausente ou relativa é resolvida contra `config.base_url`. Passar `etag` ou
        `last_modified` liga `If-None-Match`/`If-Modified-Since` quando
        `config.cache_condicional` é `True`; a resposta pode então vir com `nao_modificada`.
        """
        condicionais: dict[str, str] = {}
        if self.config.cache_condicional:
            if etag:
                condicionais["If-None-Match"] = etag
            if last_modified:
                condicionais["If-Modified-Since"] = last_modified
        elif etag or last_modified:
            _log.warning(
                "%s: etag/last_modified ignorados: cache_condicional=False no ExtractorConfig",
                self.config.nome,
            )
        extra = {**(cabecalhos_extra or {}), **condicionais}
        return self._requisitar("GET", self._resolver(url), params=params, cabecalhos_extra=extra)

    def post(
        self,
        url: str | None = None,
        *,
        dados: Mapping[str, Any] | None = None,
        cabecalhos_extra: Mapping[str, str] | None = None,
    ) -> RespostaBruta:
        """POST de formulário — é como a Curva Zero da ANBIMA (`CZ-down.asp`) é consultada."""
        return self._requisitar(
            "POST", self._resolver(url), dados=dados, cabecalhos_extra=cabecalhos_extra
        )

    def json_array(
        self,
        url: str | None = None,
        *,
        params: Mapping[str, Any] | None = None,
        cabecalhos_extra: Mapping[str, str] | None = None,
        minimo: int | None | _DoContrato = DO_CONTRATO,
    ) -> list[dict[str, Any]]:
        """GET + validação de shape + **guarda de contagem mínima** (R1 e R2 num passo).

        Por default o mínimo é `config.contagem_minima_esperada` — era o furo QA-02: a guarda
        existia e não era chamada, então corpo `[]` com HTTP 200 passava como sucesso num contrato
        que declarava 249 observações (R2: truncamento silencioso de Olinda/Yahoo/FRED).

        Em janela fatiada (`fatiar_janela`), o mínimo do contrato é o **total** da série, não o da
        fatia: passe `minimo=None` dentro do laço e chame `exigir_contagem_minima` uma vez no
        total concatenado, ou `minimo=<esperado da fatia>` se souber o número.
        """
        resposta = self.get(url, params=params, cabecalhos_extra=cabecalhos_extra)
        observacoes = validar_corpo_json_array(resposta, encoding=self.config.encoding)
        efetivo = (
            self.config.contagem_minima_esperada if isinstance(minimo, _DoContrato) else minimo
        )
        exigir_contagem_minima(
            len(observacoes),
            minimo=efetivo,
            origem=f"{self.config.nome} @ {resposta.url}",
        )
        return observacoes

    # ------------------------------------------------------------- interno

    def _resolver(self, url: str | None) -> str:
        if not url:
            return self.config.base_url
        if url.startswith(("http://", "https://")):
            return url
        return f"{self.config.base_url.rstrip('/')}/{url.lstrip('/')}"

    def _montar_cabecalhos(self, extra: Mapping[str, str] | None) -> dict[str, str]:
        cabecalhos = dict(self._cabecalhos_base)
        if extra:
            cabecalhos.update(extra)
        return cabecalhos

    def _exigir_user_agent(self, cabecalhos: Mapping[str, str], url: str) -> None:
        """Asserção de CA-045: fonte que exige UA de browser não recebe requisição sem UA."""
        if not self.config.requer_user_agent_browser:
            return
        agente = next(
            (v for k, v in cabecalhos.items() if k.lower() == "user-agent"),
            "",
        )
        if not agente.strip():
            msg = (
                f"{self.config.nome}: requisição a {url} sem User-Agent, e o ExtractorConfig "
                f"declara requer_user_agent_browser=True (R4: Yahoo responde 429, o CKAN do BCB "
                f"devolve página de erro). Use cabecalhos_de_browser()"
            )
            raise UserAgentObrigatorio(msg)

    def _requisitar(
        self,
        metodo: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        dados: Mapping[str, Any] | None = None,
        cabecalhos_extra: Mapping[str, str] | None = None,
    ) -> RespostaBruta:
        cabecalhos = self._montar_cabecalhos(cabecalhos_extra)
        self._exigir_user_agent(cabecalhos, url)

        tentativas = self.config.max_retries + 1
        ultimo_motivo = ""
        for tentativa in range(tentativas):
            if tentativa:
                atraso = min(BACKOFF_BASE_S * 2 ** (tentativa - 1), BACKOFF_MAXIMO_S)
                _log.warning(
                    "%s: tentativa %d/%d em %.1fs — %s",
                    self.config.nome,
                    tentativa + 1,
                    tentativas,
                    atraso,
                    ultimo_motivo,
                )
                self._dormir(atraso)
            try:
                resposta = self._transporte(
                    metodo,
                    url,
                    params=params,
                    dados=dados,
                    cabecalhos=cabecalhos,
                    timeout_s=self.config.timeout_s,
                )
            except FalhaDeTransporte as exc:
                ultimo_motivo = str(exc)
                continue

            if resposta.status in STATUS_RETENTAVEIS:
                ultimo_motivo = f"HTTP {resposta.status}"
                continue
            if resposta.status >= 400 and not resposta.nao_modificada:
                msg = f"{metodo} {url}: HTTP {resposta.status} (não retentável)"
                raise FonteIndisponivel(msg)
            return resposta

        msg = (
            f"{metodo} {url}: esgotadas {tentativas} tentativas (último motivo: "
            f"{ultimo_motivo}). Nenhum extrator tem licença para estimar a série no lugar disto"
        )
        raise FonteIndisponivel(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Guardas de shape e de contagem
# ─────────────────────────────────────────────────────────────────────────────


def validar_corpo_json_array(
    resposta: RespostaBruta,
    *,
    encoding: str = "utf-8",
) -> list[dict[str, Any]]:
    """Recusa o corpo de erro servido com HTTP 200 e devolve o array JSON (R1, CA-003).

    Recusa, em ordem: corpo vazio; corpo que começa com `<` (HTML de erro do SGS); JSON que é
    objeto com chave `error`/`erro`; JSON que não é lista. Só então devolve a lista — por isso
    um extrator que use este caminho não consegue gravar lixo em `data/processed/`.
    """
    origem = resposta.url
    formato = resposta.formato
    if formato is FormatoDetectado.VAZIO:
        msg = f"{origem}: HTTP {resposta.status} com corpo vazio — resposta não utilizável"
        raise RespostaDeErroComStatus200(msg)
    if formato is FormatoDetectado.HTML:
        amostra = resposta.conteudo[:160].decode(encoding, errors="replace")
        msg = (
            f"{origem}: HTTP {resposta.status} com corpo HTML, não JSON — é a página de erro da "
            f"fonte (R1). Amostra: {amostra!r}"
        )
        raise RespostaDeErroComStatus200(msg)

    texto = ler_texto(resposta.conteudo, encoding)
    try:
        corpo = json.loads(texto)
    except json.JSONDecodeError as exc:
        msg = f"{origem}: HTTP {resposta.status} com corpo que não é JSON válido ({exc})"
        raise RespostaDeErroComStatus200(msg) from exc

    if isinstance(corpo, dict):
        encontradas = sorted(CHAVES_DE_ERRO.intersection(k.lower() for k in corpo))
        if encontradas:
            detalhe = "; ".join(f"{k}={corpo.get(k)!r}" for k in encontradas)
            msg = (
                f"{origem}: HTTP {resposta.status} com corpo de ERRO (Anti-SPEC §10.1.5). {detalhe}"
            )
            raise RespostaDeErroComStatus200(msg)
        msg = f"{origem}: esperado array JSON, veio objeto com chaves {sorted(corpo)}"
        raise RespostaDeErroComStatus200(msg)
    if not isinstance(corpo, list):
        msg = f"{origem}: esperado array JSON, veio {type(corpo).__name__}"
        raise RespostaDeErroComStatus200(msg)
    return corpo


def exigir_contagem_minima(
    quantidade: int,
    *,
    minimo: int | None,
    origem: str,
) -> int:
    """Guarda anti-truncamento silencioso (R2). `minimo=None` desliga a checagem.

    Olinda devolve 20.000 linhas sem `nextLink`, `range=max` do Yahoo trunca série mensal e
    `fredgraph.csv` sem `cosd` trunca: em nenhum dos três há sinal de erro. O único jeito de
    perceber é a fonte ter dito antes quantas linhas, no mínimo, se espera
    (`ExtractorConfig.contagem_minima_esperada`).
    """
    if minimo is None:
        return quantidade
    if quantidade < minimo:
        msg = (
            f"{origem}: {quantidade} registros, mínimo esperado {minimo} — provável truncamento "
            f"silencioso (R2). Não complete a série: confira a paginação/janela da fonte"
        )
        raise RespostaTruncada(msg)
    return quantidade


def fatiar_janela(
    inicio: date,
    fim: date,
    *,
    janela_maxima_dias: int | None,
) -> tuple[tuple[date, date], ...]:
    """Fatia `[inicio, fim]` em blocos contíguos de no máximo `janela_maxima_dias` dias.

    Pegadinha nº 1 do SGS (`fontes-de-dados.md §A1`): série **diária** rejeita janela acima de
    ~10 anos com HTTP 200 + corpo de erro. 2006→2026 em uma requisição falha; em fatias de
    `JANELA_SGS_RECOMENDADA_DIAS` (~5 anos), não. Séries mensais/trimestrais não têm o limite —
    nelas `janela_maxima_dias=None` e o resultado é uma fatia só.

    As fatias são contíguas e sem sobreposição, então concatenar não duplica observação.
    """
    if fim < inicio:
        msg = f"janela invertida: inicio={inicio.isoformat()} > fim={fim.isoformat()}"
        raise ValueError(msg)
    if janela_maxima_dias is None:
        return ((inicio, fim),)
    if janela_maxima_dias < 1:
        msg = f"janela_maxima_dias deve ser >= 1, recebido {janela_maxima_dias}"
        raise ValueError(msg)

    fatias: list[tuple[date, date]] = []
    atual = inicio
    while atual <= fim:
        termino = min(atual + timedelta(days=janela_maxima_dias - 1), fim)
        fatias.append((atual, termino))
        atual = termino + timedelta(days=1)
    return tuple(fatias)
