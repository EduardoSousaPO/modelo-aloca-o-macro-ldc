"""Extrator BCB SGS — IPCA, IBC-Br, Selic, CDI, PTAX e PIB (F-003).

Cobre RF-001 (IPCA 433/13522), RF-003 (IBC-Br 24364/24363), RF-005 (Selic 11/1178/432/4390/4189),
RF-006 (CDI 12/4389), RF-015 (PTAX 1/10813) e o espelho de PIB (22109/22099).

```bash
python -m apps.pipeline.extract.bcb_sgs                        # as 15 séries do pacote mínimo
python -m apps.pipeline.extract.bcb_sgs --series BCB_SGS_433    # uma série
python -m apps.pipeline.extract.bcb_sgs --offline               # relê o bruto já arquivado
```

O que este módulo **não** faz: nenhuma agregação para a grade trimestral e nenhuma acumulação
geométrica de CDI/Selic (é F-017 / camada canônica, classe C). Aqui a série sai na **frequência
nativa** em `data/processed/sgs/<series_id>.parquet`, validada por `ProcessedSeriesSchema`.

Duas convenções vêm da consolidação da Onda 1 (`docs/plans/DECISIONS_LOG.md §2`, D-a e D-b):

- **`date` = fim de período** em série mensal/trimestral. O SGS devolve o 1º dia (`01/09/2026`
  para o IPCA de setembro) e `fim_do_periodo` converte para `30/09/2026`, que é o que a camada
  canônica usa e o que o SIDRA (F-004) já gravava — sem isso, SGS 433 e SIDRA `t/1737 v/63`,
  que são a mesma série, não casam por `date`.
- **`vintage` = a data (sem hora) de `collected_at`**, e `collected_at` sai do **manifesto** do
  bruto (`obtido_em_arquivado`), não do relógio da rodada. É o que identifica a safra de
  extração numa fonte que revisa o passado sem acrescentar ponto (IBC-Br) e o que mantém
  `--offline` byte-idêntico entre rodadas.

Armadilhas que o código abaixo trata, em ordem de risco (`docs/research/fontes-de-dados.md §A1`):

1. **HTTP 200 com corpo de erro** — série diária rejeita janela > 10 anos devolvendo
   `{"error": "..."}` com status 200. Quem faz `json.loads` direto grava lixo. Tudo passa por
   `validar_corpo_json_array` (CA-003).
2. **Fatiamento** — série diária é pedida em blocos de `JANELA_SGS_RECOMENDADA_DIAS` (~5 anos);
   mensal/trimestral em uma fatia só. A guarda de contagem mínima vale para o **total**
   concatenado, não para a fatia (`minimo=None` no laço) — CA-011.
3. **Ponto decimal** — o JSON do SGS traz `"valor": "0.82"`, ponto decimal. É
   `para_float_ponto_decimal`; `para_float_ptbr` leria `"0.82"` como erro (e `"6.930"` como 6930).
4. **Data `dd/mm/aaaa`** — `01/02/2006` é 1º de fevereiro aqui e 2 de janeiro na PTAX do Olinda.
   O formato é declarado (`FormatoData.DD_MM_AAAA`), nunca inferido.
5. **Meta Selic (432) vem com data futura** — a última linha reflete a meta vigente até a próxima
   reunião do Copom. Truncada em `fim` antes de chegar a `data/processed/` (CA-013).
6. **User-Agent de browser** — o backend do SGS passou a recusar cliente sem UA; é o default do
   `ClienteHTTP` (`requer_user_agent_browser=True`).
7. **Mês/trimestre corrente, ainda aberto** — em série `M`/`Q` o SGS já publica o período em
   curso (4390 traz `01/10/2026 = 0.36`, os 7 dias úteis decorridos de outubro). É acumulação
   **parcial** com cara de período fechado; `descartar_periodo_aberto` recusa por critério
   explícito ("fim de período > data de coleta"), não por efeito colateral de `--fim`.
"""

from __future__ import annotations

import argparse
import calendar
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from apps.pipeline.common import (
    JANELA_SGS_RECOMENDADA_DIAS,
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    ManifestoAusente,
    RespostaBruta,
    RespostaDeErroComStatus200,
    Transporte,
    arquivar_bruto,
    caminho_destino_raw,
    collected_at_do_bruto,
    exigir_contagem_minima,
    fatiar_janela,
    gravar_processado_parquet,
    nome_arquivo_raw,
    obter_logger,
    obtido_em_arquivado,
    para_data,
    para_float_ponto_decimal,
    validar_corpo_json_array,
)
from packages.shared.schemas import (
    ExtractorConfig,
    Fonte,
    Freq,
    SeriesCatalogEntry,
    StatusSerie,
    load_catalog,
)

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Parâmetros da fonte
# ─────────────────────────────────────────────────────────────────────────────

FONTE_SLUG = "sgs"
"""Subpasta de `data/raw/` e de `data/processed/` — a mesma de `tests/fixtures/sgs/`."""

DESTINO_RAW = f"data/raw/{FONTE_SLUG}"
URL_BASE_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}"
CAMINHO_DADOS = "/dados"

INICIO_PADRAO = date(2004, 1, 1)
"""Dois anos antes de 1T2006: a janela do e-mail são 20 anos, e a folga cobre a defasagem de
divulgação, a média móvel de 20 trimestres (RF-003) e a variação 12m do primeiro trimestre."""

GAP_MAXIMO_DIARIO_DIAS = 12
"""Maior intervalo de dias corridos aceitável entre dois pontos de série diária.

Carnaval (sáb→qua) e a emenda de Natal/Ano Novo produzem vãos de até ~6 dias corridos. Doze dias
é frouxo de propósito: a função serve para pegar **fatia perdida**, não feriado."""

DIAS_DE_FIM_DE_SEMANA = 5
"""`weekday() >= 5` é sábado ou domingo — série diária **de mercado** não tem ponto aí."""

SERIES_DIARIAS_DE_CALENDARIO: frozenset[int] = frozenset({432})
"""**Fallback** de `SeriesCatalogEntry.calendario` — a verdade está no catálogo desde 2026-10-11.

Séries `freq=D` que publicam em **dia corrido**, não em dia útil — medido na extração ao vivo.

A meta Selic (432) não é uma cotação: é a taxa *vigente* até a próxima reunião do Copom, então o
SGS repete o mesmo valor todos os dias, inclusive sábado, domingo e feriado (5 fatias de
2004-01-01 a 2026-10-10 vieram com vão de exatamente 1 dia em 100% dos pares). Tratá-la como
série de dia útil acusaria 2.377 "datas em fim de semana" que são dado legítimo — e, pior, o
contrário (aceitar vão de 12 dias) deixaria passar semana faltando. Para estas, a continuidade
exigida é mais forte: **nenhum dia corrido ausente**.

Esta constante ficou aqui enquanto a informação era privada do extrator — e era o P1-2 do QA:
F-014/F-017 leem o **catálogo** e o Parquet, não o módulo de extração, então 28,6 % dos pontos da
432 (fins de semana) entrariam numa contagem de dias úteis. A distinção agora é campo de catálogo
(`calendario`); esta constante só responde por série SGS cujo catálogo ainda não declarou nada."""


_RE_CODIGO = re.compile(r"bcdata\.sgs\.(\d+)")

SERIES_PACOTE_MINIMO: tuple[str, ...] = (
    # inflação (RF-001 · e-mail A2)
    "BCB_SGS_433",
    "BCB_SGS_13522",
    # atividade (RF-003 · e-mail A1)
    "BCB_SGS_24364",
    "BCB_SGS_24363",
    # juros (RF-005 · e-mail A4)
    "BCB_SGS_11",
    "BCB_SGS_1178",
    "BCB_SGS_432",
    "BCB_SGS_4390",
    "BCB_SGS_4189",
    # CDI (RF-006 · e-mail B3)
    "BCB_SGS_12",
    "BCB_SGS_4389",
    # câmbio (RF-015 · e-mail C1)
    "BCB_SGS_1",
    "BCB_SGS_10813",
    # espelho de PIB (e-mail A1)
    "BCB_SGS_22109",
    "BCB_SGS_22099",
)
"""As 15 séries que o Feature Contract de F-003 põe no caminho crítico de 2026-10-14.

O catálogo tem mais entradas `BCB_SGS` com `status=ok` (núcleos do IPCA, IGP, DLSP, IC-Br, PIB
mensal, valor adicionado): elas são extraíveis por `--todas`, mas não são o pacote mínimo."""

VALORES_CANARIO: Mapping[int, tuple[str, float]] = {
    # (data ISO, valor) — todos medidos em `docs/research/fontes-de-dados.md §A1/§B7`.
    # Série mensal/trimestral: a data é o **fim do período** (`CLAUDE.md §3`, D-a da consolidação
    # da Onda 1), que é a data que vai para `data/processed/`. O SGS devolve o 1º dia do período
    # (`01/09/2026` para o IPCA de setembro) e `fim_do_periodo` converte antes de qualquer guarda.
    433: ("2026-09-30", 0.82),  # CA-002 (idêntico a SIDRA 1737 v63)
    13522: ("2026-09-30", 4.58),
    24364: ("2006-01-31", 79.44731),  # CA-006
    24363: ("2006-01-31", 75.88784),
    11: ("2005-01-03", 0.064826),  # CA-012
    1178: ("2026-10-09", 13.65),
    432: ("2006-01-02", 18.00),  # "2006 = 18.00" na pesquisa; medido dia a dia na extração
    12: ("2005-01-03", 0.064893),
    4389: ("2026-10-08", 13.65),
    1: ("2026-10-09", 4.9892),  # CA-043
    10813: ("2026-10-09", 4.9886),
    22109: ("2006-03-31", 131.74),  # = SIDRA 1621/v584/90707 (CA-009)
    22099: ("2006-03-31", 128.18),
}

TOLERANCIA_CANARIO = 1e-6


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo → configuração
# ─────────────────────────────────────────────────────────────────────────────


def codigo_sgs(entrada: SeriesCatalogEntry) -> int:
    """Código numérico da série no SGS, lido do catálogo (nunca hard-coded no extrator)."""
    try:
        return int(entrada.identificador)
    except ValueError as exc:
        msg = f"{entrada.series_id}: identificador {entrada.identificador!r} não é código SGS"
        raise ErroDeExtracao(msg) from exc


def calendario_corrido(entrada: SeriesCatalogEntry) -> bool:
    """A série publica em **dia corrido** (sábado, domingo e feriado inclusive)?

    Lê `SeriesCatalogEntry.calendario` — o catálogo é a fonte de verdade, porque é o que a camada
    canônica e as features de alinhamento consultam. `SERIES_DIARIAS_DE_CALENDARIO` só entra
    quando o catálogo cala (`calendario=None`), para que nenhuma série SGS perca a guarda de
    continuidade que já tinha.
    """
    if entrada.calendario is not None:
        return entrada.calendario == "corrido"
    return codigo_sgs(entrada) in SERIES_DIARIAS_DE_CALENDARIO


def catalogo_sgs(
    series_ids: Sequence[str] | None = None,
    *,
    todas: bool = False,
) -> tuple[SeriesCatalogEntry, ...]:
    """Entradas `fonte=BCB_SGS` e `status=ok` do catálogo, na ordem pedida.

    Sem argumento: as 15 do `SERIES_PACOTE_MINIMO`. Com `todas=True`: toda série SGS usável.
    `a_confirmar`, `descartada` e `descontinuada` (os swaps 7801-7806) nunca entram — é o portão
    de CA-053/054 e o que impede a rota morta do e-mail de voltar por descuido.
    """
    usaveis = {
        e.series_id: e
        for e in load_catalog()
        if e.fonte is Fonte.BCB_SGS and e.status is StatusSerie.OK
    }
    if series_ids is None:
        pedidas = tuple(usaveis) if todas else SERIES_PACOTE_MINIMO
    else:
        pedidas = tuple(series_ids)

    desconhecidas = [s for s in pedidas if s not in usaveis]
    if desconhecidas:
        msg = f"série fora do catálogo SGS usável: {desconhecidas}. Disponíveis: {sorted(usaveis)}"
        raise ErroDeExtracao(msg)
    return tuple(usaveis[s] for s in pedidas)


def _dias_uteis(inicio: date, fim: date) -> int:
    """Dias de semana (seg-sex) no intervalo fechado — sem calendário de feriados."""
    return sum(
        1
        for n in range((fim - inicio).days + 1)
        if (inicio + timedelta(days=n)).weekday() < DIAS_DE_FIM_DE_SEMANA
    )


def contagem_minima(entrada: SeriesCatalogEntry, *, inicio: date, fim: date) -> int:
    """Piso anti-truncamento silencioso (R2) para o **total** da série na janela pedida.

    Deliberadamente folgado — a guarda existe para pegar corpo `[]`, fatia perdida e paginação
    truncada, não para auditar feriado. Diária desconta 10% (feriados); mensal e trimestral
    descontam a defasagem de divulgação (IPCA ~10 dias, IBC-Br ~45, PIB ~60).
    """
    comeco = max(inicio, entrada.data_inicio or inicio)
    if comeco > fim:
        return 1
    meses = (fim.year - comeco.year) * 12 + (fim.month - comeco.month)
    if entrada.freq is Freq.DIARIA:
        bruto = int(_dias_uteis(comeco, fim) * 0.90)
    elif entrada.freq is Freq.MENSAL:
        bruto = meses + 1 - 3
    elif entrada.freq is Freq.TRIMESTRAL:
        bruto = meses // 3 + 1 - 2
    else:
        bruto = 1
    return max(1, bruto)


def config_para(
    entrada: SeriesCatalogEntry,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
) -> ExtractorConfig:
    """`ExtractorConfig` da série — é a configuração que carrega a pegadinha, não o código.

    `janela_maxima_dias` só existe para a série **diária**: é o que liga `fatiar_janela` e
    portanto o que impede o HTTP 200 com corpo de erro da janela de 10 anos.
    """
    fim = fim or date.today()
    codigo = codigo_sgs(entrada)
    return ExtractorConfig(
        nome=f"bcb_sgs_{codigo}",
        fonte=Fonte.BCB_SGS,
        series_ids=(entrada.series_id,),
        base_url=URL_BASE_SGS.format(cod=codigo),
        formato="json",
        encoding="utf-8",
        requer_user_agent_browser=True,
        janela_maxima_dias=(JANELA_SGS_RECOMENDADA_DIAS if entrada.freq is Freq.DIARIA else None),
        contagem_minima_esperada=contagem_minima(entrada, inicio=inicio, fim=fim),
        valor_canario=VALORES_CANARIO.get(codigo),
        destino_raw=DESTINO_RAW,
        timeout_s=90.0,
        max_retries=3,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Download, arquivamento e modo offline
# ─────────────────────────────────────────────────────────────────────────────


def nome_bruto(codigo: int, *, inicio: date, fim: date) -> str:
    """Nome determinístico da fatia bruta: `<codigo>_<inicio>__<fim>.json`.

    Determinístico é o que torna o arquivamento idempotente (mesma janela ⇒ mesmo arquivo ⇒
    `arquivar_bruto` não reescreve) e o que o modo `--offline` usa para reencontrar a fatia.
    """
    return nome_arquivo_raw(f"{codigo}_{inicio.isoformat()}", data_ref=fim, extensao="json")


def _params(inicio: date, fim: date) -> dict[str, str]:
    return {
        "formato": "json",
        "dataInicial": inicio.strftime("%d/%m/%Y"),
        "dataFinal": fim.strftime("%d/%m/%Y"),
    }


def transporte_do_bruto_arquivado(
    destino: Path,
    *,
    agora: datetime | None = None,
) -> Transporte:
    """Transporte que serve `data/raw/sgs/` em vez da rede — é o `--offline`.

    Reaproveita o pipeline inteiro (validação de shape, dedup, continuidade, schema) sobre o
    bruto já arquivado: é o que permite reconstruir `data/processed/` sem fonte viva e o que
    prova que o parse não depende da rede.

    O `obtida_em` de cada fatia sai do **manifesto daquela fatia** (`collected_at_do_bruto`),
    nunca do relógio: é o que faz `--offline` reescrever o manifesto com o mesmo valor e, por
    consequência, produzir o mesmo Parquet em duas rodadas seguidas (D-b). Fatia sem manifesto é
    **recusada** — e a recusa tem de ser aqui, porque `arquivar_bruto` reescreve o manifesto com
    o que este transporte declarar: o relógio entraria pela porta da frente e o manifesto
    recém-criado pareceria legítimo na etapa seguinte (CA-121).

    `agora` é a safra declarada por escrito por quem chama (o `collected_at=` da CLI/do teste) e
    só é usada quando o manifesto não existe.
    """

    def _transporte(
        metodo: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        dados: Mapping[str, Any] | None = None,
        cabecalhos: Mapping[str, str],
        timeout_s: float,
    ) -> RespostaBruta:
        del metodo, dados, cabecalhos, timeout_s
        casado = _RE_CODIGO.search(url)
        if not casado or not params:
            msg = f"offline: não consigo deduzir a fatia de {url} com params={params!r}"
            raise ErroDeExtracao(msg)
        inicio = datetime.strptime(str(params["dataInicial"]), "%d/%m/%Y").date()  # noqa: DTZ007
        fim = datetime.strptime(str(params["dataFinal"]), "%d/%m/%Y").date()  # noqa: DTZ007
        alvo = Path(destino) / nome_bruto(int(casado.group(1)), inicio=inicio, fim=fim)
        if not alvo.is_file():
            msg = (
                f"offline: {alvo} não existe. Rode sem --offline uma vez para arquivar o bruto "
                f"(data/ é reconstruível; a verdade é o script)"
            )
            raise ErroDeExtracao(msg)
        return RespostaBruta(
            url=f"file://{alvo.as_posix()}",
            status=200,
            conteudo=alvo.read_bytes(),
            cabecalhos={"Content-Type": "application/json"},
            obtida_em=collected_at_do_bruto(alvo, collected_at=agora),
        )

    return _transporte


@dataclass(frozen=True, slots=True)
class FatiaBruta:
    """Uma requisição ao SGS: janela pedida, bruto arquivado e nº de observações."""

    inicio: date
    fim: date
    observacoes: int
    arquivo: str
    sha256: str
    idempotente: bool


def baixar_serie(
    entrada: SeriesCatalogEntry,
    *,
    config: ExtractorConfig,
    inicio: date,
    fim: date,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    sobrescrever_raw: bool = False,
) -> tuple[list[dict[str, Any]], tuple[FatiaBruta, ...]]:
    """Baixa a série em fatias, arquiva cada bruto e devolve as observações concatenadas.

    A guarda de contagem mínima é aplicada **uma vez, no total** (`minimo=None` por fatia): o
    piso do contrato descreve a série, não o pedaço — era o furo QA-02 de F-001.
    """
    cliente = ClienteHTTP(config, transporte=transporte)
    destino = caminho_destino_raw(config, raiz=raiz)
    codigo = codigo_sgs(entrada)

    observacoes: list[dict[str, Any]] = []
    fatias: list[FatiaBruta] = []
    janelas = fatiar_janela(inicio, fim, janela_maxima_dias=config.janela_maxima_dias)
    for janela_inicio, janela_fim in janelas:
        resposta = cliente.get(CAMINHO_DADOS, params=_params(janela_inicio, janela_fim))
        da_fatia = validar_corpo_json_array(resposta, encoding=config.encoding)
        exigir_contagem_minima(
            len(da_fatia),
            minimo=None,  # o mínimo do contrato é o TOTAL, conferido depois do laço
            origem=f"{config.nome} fatia {janela_inicio}..{janela_fim}",
        )
        arquivado = arquivar_bruto(
            resposta.conteudo,
            destino=destino,
            nome=nome_bruto(codigo, inicio=janela_inicio, fim=janela_fim),
            origem=resposta.url,
            obtido_em=resposta.obtida_em,
            cabecalhos=dict(resposta.cabecalhos),
            sobrescrever_se_diferente=sobrescrever_raw,
        )
        observacoes += da_fatia
        fatias.append(
            FatiaBruta(
                inicio=janela_inicio,
                fim=janela_fim,
                observacoes=len(da_fatia),
                arquivo=arquivado.caminho.name,
                sha256=arquivado.sha256,
                idempotente=arquivado.idempotente,
            )
        )

    exigir_contagem_minima(
        len(observacoes),
        minimo=config.contagem_minima_esperada,
        origem=f"{config.nome} ({len(janelas)} fatia(s) de {inicio} a {fim})",
    )
    return observacoes, tuple(fatias)


# ─────────────────────────────────────────────────────────────────────────────
# Parse e validação
# ─────────────────────────────────────────────────────────────────────────────


def fim_do_periodo(quando: date, *, freq: Freq) -> date:
    """Data da observação na convenção do projeto: **fim de período** para mensal e trimestral.

    O SGS devolve o **primeiro** dia do período (`01/09/2026` para o IPCA de setembro,
    `01/04/2026` para o PIB do 2º trimestre); `CLAUDE.md §3` e a camada canônica trabalham com
    fim de período, e o SIDRA (F-004) já grava assim. Sem esta conversão, um `join` por `date`
    entre SGS 433 e SIDRA `t/1737 v/63` — que são **a mesma série** — não casaria nenhuma linha
    (medido em F-004: 273 meses sobrepostos, 0 casados por `date`).

    É fim de período **civil**, não dia útil: ajustar para dia útil é alinhamento (F-014), e
    misturar as duas coisas aqui esconderia a regra num extrator.

    Série diária passa inalterada.
    """
    if freq is Freq.MENSAL:
        return date(quando.year, quando.month, calendar.monthrange(quando.year, quando.month)[1])
    if freq is Freq.TRIMESTRAL:
        mes_final = 3 * ((quando.month - 1) // 3 + 1)
        return date(quando.year, mes_final, calendar.monthrange(quando.year, mes_final)[1])
    return quando


COLUNAS_PROCESSADAS: tuple[str, ...] = (
    "series_id",
    "date",
    "value",
    "source",
    "freq",
    "vintage",
    "unit",
    "collected_at",
)
"""As 8 colunas de `ProcessedSeriesSchema`, nesta ordem. `strict=True`: nada mais entra."""


def quadro_de_observacoes(
    entrada: SeriesCatalogEntry,
    observacoes: Sequence[Mapping[str, Any]],
    *,
    collected_at: datetime,
) -> pd.DataFrame:
    """Observações do SGS → as 8 colunas de `ProcessedSeriesSchema`, nada mais.

    `valor` é string com **ponto** decimal (`"0.82"`) e `data` é `dd/mm/aaaa`: os dois formatos
    são declarados, não inferidos. Ausência (`""`, `"-"`, `"ND"`) vira `None`, nunca `0`
    (Anti-SPEC §10.1.4).

    Duas convenções da Onda 1 valem aqui:

    - **`date` = fim de período** em série mensal/trimestral (`fim_do_periodo`, D-a);
    - **`vintage` = a data (sem hora) de `collected_at`**, que por sua vez vem do manifesto do
      bruto (D-b). Identifica a *safra* de extração — o que importa numa fonte que revisa o
      passado sem acrescentar ponto (IBC-Br) — e, por sair do manifesto e não do relógio,
      mantém `--offline` idempotente.
    """
    origem = entrada.series_id
    vintage = pd.Timestamp(collected_at).tz_localize(None).normalize()
    linhas: list[dict[str, Any]] = []
    for i, obs in enumerate(observacoes):
        if "data" not in obs:
            msg = f"{origem}: observação {i} sem campo 'data': {dict(obs)!r}"
            raise RespostaDeErroComStatus200(msg)
        quando = para_data(obs["data"], FormatoData.DD_MM_AAAA, origem=f"{origem}[{i}].data")
        if quando is None:
            msg = f"{origem}: observação {i} com data vazia — o SGS não faz isso: {dict(obs)!r}"
            raise RespostaDeErroComStatus200(msg)
        quando = fim_do_periodo(quando, freq=entrada.freq)
        linhas.append(
            {
                "series_id": entrada.series_id,
                "date": quando,
                "value": para_float_ponto_decimal(obs.get("valor"), origem=f"{origem}[{i}].valor"),
                "source": Fonte.BCB_SGS.value,
                "freq": entrada.freq.value,
                "vintage": vintage,
                "unit": entrada.unit.value,
                "collected_at": collected_at,
            }
        )

    quadro = pd.DataFrame(linhas, columns=list(COLUNAS_PROCESSADAS))
    quadro["date"] = pd.to_datetime(quadro["date"])
    quadro["value"] = pd.to_numeric(quadro["value"], errors="raise")
    return quadro.sort_values("date").reset_index(drop=True)


def truncar_em(quadro: pd.DataFrame, fim: date) -> tuple[pd.DataFrame, int]:
    """Remove linha com `date > fim` — a meta Selic (432) vem com data futura (CA-013).

    Sem isto, `ProcessedSeriesSchema` recusaria o quadro inteiro (`sem_data_futura`); com isto, a
    série fica íntegra e o descarte é contado e logado, em vez de silencioso.
    """
    limite = pd.Timestamp(fim)
    futuras = int((quadro["date"] > limite).sum())
    if not futuras:
        return quadro, 0
    _log.info("truncando %d linha(s) com data > %s (meta vigente do Copom)", futuras, fim)
    return quadro.loc[quadro["date"] <= limite].reset_index(drop=True), futuras


def descartar_periodo_aberto(
    quadro: pd.DataFrame,
    *,
    freq: Freq,
    collected_at: datetime,
) -> tuple[pd.DataFrame, int]:
    """Recusa observação de **período ainda não encerrado** em série mensal/trimestral.

    O SGS publica o mês corrente **em curso**: em 2026-10-11 a série 4390 (Selic acumulada no
    mês) já traz `01/10/2026 = 0.36`, que são os 7 dias úteis decorridos de outubro, e a 4189
    traz `13.65`. São números verdadeiros e **não são o mês de outubro** — tratá-los como mês
    fechado publica acumulação parcial na mesma coluna que 273 meses completos, o que é o
    cenário que Anti-SPEC §10.1.1 proíbe (dado que "parece" a série e não é).

    A guarda é explícita por decisão, não por efeito colateral: até 2026-10-11 a linha caía fora
    só porque `fim_do_periodo(2026-10-01, M) = 2026-10-31` ficava depois de `--fim` e `truncar_em`
    a pegava. Bastava `--fim 2026-10-31` (ou rodar no último dia civil do mês, sem flag) para
    outubro parcial entrar como fechado — medido pelo QA da Onda 1 (`ONDA-1-QA-A.md §4.4`).
    Aqui o critério não depende de `--fim`: **o período encerrou antes da coleta?**

    `date` já é o fim do período (`fim_do_periodo`), e `collected_at` já é a safra do bruto
    (D-b), então a condição é direta: `date > data da coleta` ⇒ período aberto. Série diária
    passa inalterada — o período de um dia encerra no próprio dia, e data futura de verdade
    (meta Selic 432) é assunto de `truncar_em`.
    """
    if freq not in (Freq.MENSAL, Freq.TRIMESTRAL) or quadro.empty:
        return quadro, 0
    coleta = pd.Timestamp(collected_at).tz_localize(None).normalize()
    abertos = quadro["date"] > coleta
    n = int(abertos.sum())
    if not n:
        return quadro, 0
    descartadas = [d.date().isoformat() for d in quadro.loc[abertos, "date"]]
    _log.info(
        "%s: periodo_aberto=%d — descartando %s: período não encerrado "
        "(fim de período > data de coleta %s)",
        quadro["series_id"].iloc[0],
        n,
        descartadas[:5],
        coleta.date().isoformat(),
    )
    return quadro.loc[~abertos].reset_index(drop=True), n


def deduplicar_por_data(quadro: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Uma observação por data. Fatias contíguas não se sobrepõem, mas o SGS já repetiu borda.

    Duplicata com valores **divergentes** é erro de extração, não ruído: levanta em vez de
    escolher uma das duas em silêncio.
    """
    duplicadas = quadro["date"].duplicated(keep=False)
    if not bool(duplicadas.any()):
        return quadro, 0
    por_data = quadro.loc[duplicadas].groupby("date")["value"].nunique(dropna=False)
    conflitos = por_data[por_data > 1]
    if len(conflitos):
        datas = [d.date().isoformat() for d in conflitos.index[:5]]
        msg = (
            f"{quadro['series_id'].iloc[0]}: data duplicada com valor DIFERENTE em {datas} — "
            f"não escolho por você; confira a janela das fatias"
        )
        raise ErroDeExtracao(msg)
    limpo = quadro.drop_duplicates(subset="date", keep="first").reset_index(drop=True)
    removidas = len(quadro) - len(limpo)
    _log.info("removidas %d linha(s) duplicada(s) por data", removidas)
    return limpo, removidas


def validar_continuidade(
    quadro: pd.DataFrame,
    *,
    freq: Freq,
    calendario_corrido: bool = False,
) -> None:
    """Continuidade do índice temporal, por frequência — sem preencher nada.

    - **mensal / trimestral:** nenhum período faltando entre o primeiro e o último ponto;
    - **diária de dia útil** (11, 12, 1178, 4389, 1, 10813): nenhuma data em fim de semana e
      nenhum vão maior que `GAP_MAXIMO_DIARIO_DIAS` dias corridos — é como uma fatia perdida
      apareceria, já que feriado nacional não chega perto desse limite;
    - **diária de calendário** (`calendario_corrido=True`, hoje só a meta Selic 432): nenhum dia
      corrido ausente, nem fim de semana — a checagem mais forte das três.

    Lacuna encontrada é erro: `CLAUDE.md §4` proíbe interpolar para fechar série.
    """
    if quadro.empty:
        msg = "série vazia — nada a validar; a guarda de contagem mínima deveria ter pegado antes"
        raise ErroDeExtracao(msg)
    serie = str(quadro["series_id"].iloc[0])
    datas = pd.DatetimeIndex(quadro["date"])

    if freq in (Freq.MENSAL, Freq.TRIMESTRAL):
        alias = "M" if freq is Freq.MENSAL else "Q"
        periodos = datas.to_period(alias)
        esperados = pd.period_range(periodos.min(), periodos.max(), freq=alias)
        faltando = esperados.difference(periodos)
        if len(faltando):
            msg = (
                f"{serie}: {len(faltando)} período(s) {alias} faltando entre "
                f"{periodos.min()} e {periodos.max()}: {[str(p) for p in faltando[:6]]}"
            )
            raise ErroDeExtracao(msg)
        return

    if freq is Freq.DIARIA:
        if calendario_corrido:
            esperados_dias = pd.date_range(datas.min(), datas.max(), freq="D")
            ausentes = esperados_dias.difference(datas)
            if len(ausentes):
                amostra = [d.date().isoformat() for d in ausentes[:5]]
                msg = (
                    f"{serie}: {len(ausentes)} dia(s) corrido(s) ausente(s) entre "
                    f"{datas.min().date()} e {datas.max().date()}: {amostra}. Série de "
                    f"calendário não tem feriado — isto é fatia perdida"
                )
                raise ErroDeExtracao(msg)
            return

        fim_de_semana = datas[datas.dayofweek >= DIAS_DE_FIM_DE_SEMANA]
        if len(fim_de_semana):
            amostra = [d.date().isoformat() for d in fim_de_semana[:5]]
            msg = (
                f"{serie}: {len(fim_de_semana)} data(s) em fim de semana ({amostra}) — série "
                f"diária do SGS só tem dia útil; suspeite do parse de data (dd/mm vs mm/dd)"
            )
            raise ErroDeExtracao(msg)
        if len(datas) > 1:
            vaos = datas.to_series().diff().dt.days.dropna()
            maior = int(vaos.max())
            if maior > GAP_MAXIMO_DIARIO_DIAS:
                onde = datas[1:][(vaos > GAP_MAXIMO_DIARIO_DIAS).to_numpy()]
                amostra = [d.date().isoformat() for d in onde[:5]]
                msg = (
                    f"{serie}: vão de {maior} dias corridos no índice (antes de {amostra}) — "
                    f"máximo tolerado {GAP_MAXIMO_DIARIO_DIAS}; parece fatia perdida, não feriado"
                )
                raise ErroDeExtracao(msg)


def conferir_canario(quadro: pd.DataFrame, *, config: ExtractorConfig) -> tuple[str, float] | None:
    """Confere o valor-canário do contrato contra o extraído (CA-002, CA-006, CA-012, CA-043).

    Fora da janela extraída o canário é ignorado (não é falha); dentro dela, divergir é.
    """
    if config.valor_canario is None:
        return None
    quando, esperado = config.valor_canario
    alvo = pd.Timestamp(quando)
    if alvo < quadro["date"].min() or alvo > quadro["date"].max():
        return None
    encontrado = quadro.loc[quadro["date"] == alvo, "value"]
    if encontrado.empty:
        msg = f"{config.nome}: valor-canário de {quando} ausente na série extraída"
        raise ErroDeExtracao(msg)
    obtido = float(encontrado.iloc[0])
    if abs(obtido - esperado) > TOLERANCIA_CANARIO:
        msg = (
            f"{config.nome}: valor-canário {quando} = {obtido!r}, esperado {esperado!r} "
            f"(tolerância {TOLERANCIA_CANARIO}). A fonte revisou ou o parse mudou de escala"
        )
        raise ErroDeExtracao(msg)
    return (quando, obtido)


# ─────────────────────────────────────────────────────────────────────────────
# Extração de uma série e do pacote
# ─────────────────────────────────────────────────────────────────────────────


def collected_at_das_fatias(
    destino: Path,
    fatias: Sequence[FatiaBruta],
) -> datetime | None:
    """`collected_at` da série = o `obtido_em` mais recente entre os manifestos das fatias (D-b).

    Uma série diária é montada de 5 fatias arquivadas, cada uma com o seu manifesto; a safra da
    série é a coleta mais recente delas. `None` quando nenhuma fatia tem manifesto legível — aí
    quem chama cai no relógio.
    """
    momentos = [
        m
        for m in (obtido_em_arquivado(Path(destino) / fatia.arquivo) for fatia in fatias)
        if m is not None
    ]
    return max(momentos) if momentos else None


def exigir_collected_at(
    momento: datetime | None,
    *,
    entrada: SeriesCatalogEntry,
    fatias: Sequence[FatiaBruta],
) -> datetime:
    """`collected_at` do manifesto, ou **recusa** — nunca o relógio da rodada.

    O fallback `or datetime.now(tz=UTC)` que estava aqui tornava `vintage` dependente de *quando*
    o reprocessamento aconteceu, e com isso duas rodadas `--offline` sobre o mesmo bruto gravavam
    Parquets diferentes (D-b, CA-121, Anti-SPEC §10.4.22). Fatia arquivada por `arquivar_bruto`
    sempre tem manifesto; sem manifesto, o bruto foi posto ali à mão, e aí a safra tem de ser
    declarada por escrito em `collected_at=`.
    """
    if momento is not None:
        return momento
    arquivos = [f.arquivo for f in fatias]
    msg = (
        f"{entrada.series_id}: nenhuma das {len(fatias)} fatia(s) tem manifesto legível "
        f"({arquivos[:3]}) — sem ele `collected_at`/`vintage` sairiam do relógio desta rodada e o "
        f"Parquet deixaria de ser reproduzível (D-b, CA-121). Rode uma vez **online** (o "
        f"manifesto nasce aí) ou passe `collected_at=` explicitamente."
    )
    raise ManifestoAusente(msg)


@dataclass(frozen=True, slots=True)
class ResultadoExtracao:
    """Evidência de uma série extraída — é o que vai para a matriz de validação."""

    series_id: str
    codigo: int
    freq: str
    unit: str
    linhas: int
    data_min: date
    data_max: date
    pct_nulos: float
    duplicatas_removidas: int
    linhas_futuras_truncadas: int
    #: Observações de período M/Q ainda **não encerrado** na data da coleta, recusadas pela
    #: guarda `descartar_periodo_aberto` (P1-1 do QA da Onda 1).
    linhas_periodo_aberto: int
    canario: tuple[str, float] | None
    fatias: tuple[FatiaBruta, ...]
    parquet: Path | None

    @property
    def cobre_1t2006(self) -> bool:
        """A série alcança o 1º trimestre de 2006 (`data_min <= 2006-03-31`)?"""
        return self.data_min <= date(2006, 3, 31)


def extrair_serie(
    entrada: SeriesCatalogEntry,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    offline: bool = False,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
    sobrescrever_raw: bool = False,
    collected_at: datetime | None = None,
) -> ResultadoExtracao:
    """Baixa → arquiva → parseia → trunca → dedup → valida → grava o Parquet da série.

    `gravar=False` roda tudo menos a escrita (é como o teste confere o parse sem tocar `data/`).
    """
    fim = fim or date.today()
    config = config_para(entrada, inicio=inicio, fim=fim)
    destino_raw = caminho_destino_raw(config, raiz=raiz)
    if offline and transporte is None:
        # `agora=collected_at` (e não um relógio): sem manifesto **e** sem safra declarada, o
        # transporte offline recusa em vez de datar a fatia pela hora do reprocessamento.
        transporte = transporte_do_bruto_arquivado(destino_raw, agora=collected_at)

    observacoes, fatias = baixar_serie(
        entrada,
        config=config,
        inicio=inicio,
        fim=fim,
        transporte=transporte,
        raiz=raiz,
        sobrescrever_raw=sobrescrever_raw,
    )
    # D-b: `collected_at` (e portanto `vintage`) sai do manifesto do bruto, nunca do relógio —
    # `exigir_collected_at` recusa em vez de cair no `datetime.now()` (CA-121).
    agora = exigir_collected_at(
        collected_at or collected_at_das_fatias(destino_raw, fatias), entrada=entrada, fatias=fatias
    )
    quadro = quadro_de_observacoes(entrada, observacoes, collected_at=agora)
    quadro, abertas = descartar_periodo_aberto(quadro, freq=entrada.freq, collected_at=agora)
    quadro, truncadas = truncar_em(quadro, fim)
    quadro, duplicadas = deduplicar_por_data(quadro)
    validar_continuidade(quadro, freq=entrada.freq, calendario_corrido=calendario_corrido(entrada))
    canario = conferir_canario(quadro, config=config)

    destino = None
    if gravar:
        destino = gravar_processado_parquet(
            quadro, nome=f"{FONTE_SLUG}/{entrada.series_id}.parquet", raiz=raiz
        )

    return ResultadoExtracao(
        series_id=entrada.series_id,
        codigo=codigo_sgs(entrada),
        freq=entrada.freq.value,
        unit=entrada.unit.value,
        linhas=len(quadro),
        data_min=quadro["date"].min().date(),
        data_max=quadro["date"].max().date(),
        pct_nulos=round(float(quadro["value"].isna().mean()) * 100, 4),
        duplicatas_removidas=duplicadas,
        linhas_futuras_truncadas=truncadas,
        linhas_periodo_aberto=abertas,
        canario=canario,
        fatias=fatias,
        parquet=destino,
    )


def extrair(
    series_ids: Sequence[str] | None = None,
    *,
    todas: bool = False,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    offline: bool = False,
    raiz: Path | None = None,
    gravar: bool = True,
    sobrescrever_raw: bool = False,
    ao_falhar: Callable[[SeriesCatalogEntry, Exception], None] | None = None,
) -> tuple[ResultadoExtracao, ...]:
    """Extrai as séries pedidas (default: o pacote mínimo de 15).

    `ao_falhar` recebe a exceção e deixa o laço seguir — é o `--continuar` da CLI. Sem ele, a
    primeira falha interrompe tudo: numa fonte que mente com HTTP 200, parar é o default certo.
    """
    resultados: list[ResultadoExtracao] = []
    for entrada in catalogo_sgs(series_ids, todas=todas):
        try:
            resultados.append(
                extrair_serie(
                    entrada,
                    inicio=inicio,
                    fim=fim,
                    offline=offline,
                    raiz=raiz,
                    gravar=gravar,
                    sobrescrever_raw=sobrescrever_raw,
                )
            )
        except ErroDeExtracao as exc:
            if ao_falhar is None:
                raise
            ao_falhar(entrada, exc)
    return tuple(resultados)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.bcb_sgs",
        description="Extrai séries do BCB SGS para data/raw/sgs/ e data/processed/sgs/.",
    )
    p.add_argument(
        "--series",
        nargs="+",
        metavar="SERIES_ID",
        help="series_id do catálogo (ex.: BCB_SGS_433). Default: as 15 do pacote mínimo.",
    )
    p.add_argument(
        "--todas",
        action="store_true",
        help="todas as séries BCB_SGS com status=ok, não só o pacote mínimo.",
    )
    p.add_argument("--inicio", type=date.fromisoformat, default=INICIO_PADRAO, metavar="AAAA-MM-DD")
    p.add_argument("--fim", type=date.fromisoformat, default=None, metavar="AAAA-MM-DD")
    p.add_argument(
        "--offline",
        action="store_true",
        help="relê o bruto já arquivado em data/raw/sgs/ em vez de chamar a fonte.",
    )
    p.add_argument(
        "--sem-gravar",
        dest="gravar",
        action="store_false",
        help="roda o pipeline inteiro sem escrever em data/processed/.",
    )
    p.add_argument(
        "--sobrescrever-raw",
        action="store_true",
        help="aceita bruto divergente no mesmo nome (a fonte republicou dentro da janela).",
    )
    p.add_argument(
        "--continuar",
        action="store_true",
        help="não aborta na primeira série que falhar; reporta no fim.",
    )
    return p


def _linha(r: ResultadoExtracao) -> str:
    canario = f"{r.canario[0]}={r.canario[1]}" if r.canario else "-"
    return (
        f"{r.series_id:<16} {r.freq:<2} {r.unit:<7} {r.linhas:>6} linhas  "
        f"{r.data_min}..{r.data_max}  nulos={r.pct_nulos:>6.2f}%  "
        f"fatias={len(r.fatias)}  dup={r.duplicatas_removidas}  "
        f"fut={r.linhas_futuras_truncadas}  periodo_aberto={r.linhas_periodo_aberto}  "
        f"1T2006={'sim' if r.cobre_1t2006 else 'NAO'}  "
        f"canario={canario}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. Devolve 0 em sucesso, 1 se alguma série falhou."""
    args = _parser().parse_args(argv)
    falhas: list[tuple[str, Exception]] = []

    def _registrar(entrada: SeriesCatalogEntry, exc: Exception) -> None:
        _log.error("%s: %s", entrada.series_id, exc)
        falhas.append((entrada.series_id, exc))

    resultados = extrair(
        args.series,
        todas=args.todas,
        inicio=args.inicio,
        fim=args.fim,
        offline=args.offline,
        gravar=args.gravar,
        sobrescrever_raw=args.sobrescrever_raw,
        ao_falhar=_registrar if args.continuar else None,
    )

    print(f"\n{len(resultados)} serie(s) extraida(s) de {args.inicio} a {args.fim or 'hoje'}:\n")
    for r in resultados:
        print(_linha(r))
    print("\nbrutos arquivados:")
    for r in resultados:
        for f in r.fatias:
            marca = "=" if f.idempotente else "+"
            print(f"  {marca} {f.arquivo:<34} {f.observacoes:>6} obs  sha256={f.sha256[:16]}")
    if falhas:
        print(f"\n{len(falhas)} FALHA(S):")
        for serie, exc in falhas:
            print(f"  ! {serie}: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
