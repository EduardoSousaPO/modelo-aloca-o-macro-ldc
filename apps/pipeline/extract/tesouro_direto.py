"""Extrator Tesouro Direto — taxas e PUs diários de títulos públicos (F-005).

Cobre RF-008 (CA-020, CA-021, CA-022) e o item **A5** do e-mail do Alexandre. É também a fonte
primária da curva de juros de 20 anos, por **ADR-004** (a ETTJ histórica da ANBIMA é paga e o
`ms*.txt` gratuito é janela rolante de ~20 dias úteis).

```bash
python -m apps.pipeline.extract.tesouro_direto            # baixa (ou revalida) e processa
python -m apps.pipeline.extract.tesouro_direto --offline  # relê o bruto já arquivado, sem rede
python -m apps.pipeline.extract.tesouro_direto --forcar   # ignora o cache condicional
```

O que este módulo **não** faz: nenhuma interpolação de vértice, nenhuma inclinação de curva e
nenhum breakeven de inflação — isso é **F-016, classe C**. Aqui sai o **dado bruto limpo**, na
granularidade nativa (diária, por título × vencimento), em
`data/processed/tesouro-direto/td_painel.parquet`, validado por `ProcessedSeriesSchema`.

## O dataset é um painel, e o schema é longo

A fonte é um painel `(tipo de título × vencimento × data base)` com 5 métricas por linha, e
`ProcessedSeriesSchema` é longo `(series_id, date, value, …)`. A ponte é um **`series_id`
composto**, documentado uma vez aqui e consumido por F-016:

```
TD_<SIGLA>_<AAAAMMDD do vencimento>_<METRICA>
     ex.: TD_NTNB_20450515_TAXA_VENDA   (NTN-B 15/05/2045, taxa de venda da manhã)
          TD_LTN_20090101_PU_BASE       (LTN 01/01/2009, PU base da manhã)
```

- `SIGLA` ∈ `LTN`, `NTNF`, `NTNB`, `NTNBP`, `NTNC`, `LFT`, `EDUCA`, `RENDA` — ver `SIGLA_POR_TIPO`.
  É a sigla tradicional do título, não o nome comercial: o nome comercial mudou ("Tesouro IPCA+"
  era "NTN-B Principal") e o `series_id` não pode mudar com ele.
- `METRICA` ∈ `TAXA_COMPRA`, `TAXA_VENDA`, `PU_COMPRA`, `PU_VENDA`, `PU_BASE` — ver
  `METRICA_POR_COLUNA`. `TAXA_*` sai em `%a.a.`; `PU_*` em `BRL`.
- `date` é a **`Data Base`** (o dia da cotação), nunca o vencimento. O vencimento vive no
  `series_id` e é recuperável por `decompor_series_id`.
- Uma série por `(título, vencimento, métrica)`: 150 pares título × vencimento no arquivo de
  2026-10-09 ⇒ 750 `series_id` possíveis. Nenhum deles entra no `series_catalog`: o catálogo
  registra a **fonte** (`TESOURO_TD_PRECOTAXA`), e as séries derivadas (`CURVA_*`, `INCLINACAO_*`)
  são de F-016.

## Armadilhas que o código abaixo trata (`docs/research/fontes-de-dados.md §A4.1`, §A5)

1. **CSV pt-BR**: separador `;`, decimal **vírgula**, datas `dd/mm/aaaa`. Tudo passa por
   `para_float_ptbr` e `para_data(…, FormatoData.DD_MM_AAAA)`; nada é inferido.
2. **Encoding `latin-1` declarado** (CA-022, Anti-SPEC §10.4.26). O arquivo medido em 2026-10-10 é
   100% ASCII — o que torna o default do locale *invisivelmente* inofensivo **hoje** e um bug
   adormecido no dia em que o Tesouro acentuar um nome de título. O encoding é argumento, não
   default.
3. **Arquivo único de 14,6 MB re-publicado todo dia** (R21). O servidor manda `ETag` e
   `Last-Modified` e **responde 304** a `If-None-Match`/`If-Modified-Since` (medido ao vivo em
   2026-10-10), então a revalidação condicional é o caminho normal e o download completo é a
   exceção.
4. **HTTP 200/404 com corpo HTML**: o CKAN serve a página de erro em HTML. `exigir_formato` por
   magic bytes recusa antes de qualquer `read_csv` (R1, Anti-SPEC §10.1.5).
5. **Taxa `0,00` e negativa são valores reais** do Tesouro Selic (`-0,02` em 02/01/2006), não
   ausência. `0` nunca substitui ausência, e ausência nunca vira `0` (Anti-SPEC §10.1.4).
6. **Menu de vencimentos curto nos primeiros anos** (ADR-004): em 2006 a LTN mais longa vencia em
   **01/01/2009** e a NTN-F mais longa em **01/01/2014**; a NTN-B já ia a **15/05/2045**. O
   extrator não corrige isso — só entrega o que existe. Quem interpola é F-016, com flag.
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from apps.pipeline.common import (
    SUFIXO_MANIFESTO,
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    FormatoDetectado,
    FormatoInesperado,
    RespostaDeErroComStatus200,
    arquivar_bruto,
    caminho_destino_raw,
    collected_at_do_bruto,
    configurar_logging,
    detectar_formato,
    exigir_contagem_minima,
    exigir_formato,
    gravar_processado_parquet,
    nome_arquivo_raw,
    normalizar_rotulo,
    obter_logger,
    para_data,
    para_float_ptbr,
    sha256_de,
    validadores_condicionais,
)
from packages.shared.schemas import ExtractorConfig, Fonte, Unidade

if TYPE_CHECKING:  # pragma: no cover - só para type checker
    from collections.abc import Sequence

    from apps.pipeline.common import Transporte

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Contrato da fonte
# ─────────────────────────────────────────────────────────────────────────────

URL_TESOURO = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)
"""Mesma URL de `series_catalog_data.URL_TESOURO` — repetida aqui, não importada, porque o
catálogo é dado e este módulo precisa do endereço mesmo que a entrada do catálogo mude de nome."""

#: `series_id` da **fonte** no catálogo (`series_catalog_data._TESOURO_E_CURVA`). Não é o
#: `series_id` das linhas gravadas: essas são compostas (ver docstring do módulo).
SERIE_CATALOGO = "TESOURO_TD_PRECOTAXA"

#: Linhas do arquivo completo em 2026-10-10: 177.260. O mínimo é deliberadamente folgado em
#: relação a isso (a fonte só cresce) e apertado em relação a zero: corpo truncado não passa (R2).
CONTAGEM_MINIMA_LINHAS = 170_000

#: `Data Base` mais antiga medida: 2004-12-31. CA-021 exige `min <= 2005-01-03`.
DATA_BASE_MAIS_ANTIGA_ACEITA = date(2005, 1, 3)

#: Dias úteis de 2006 medidos no arquivo completo: **248**. CA-021 exige `>= 240`.
MINIMO_DIAS_UTEIS_2006 = 240

CONFIG = ExtractorConfig(
    nome="tesouro_direto",
    fonte=Fonte.TESOURO_CKAN,
    series_ids=(SERIE_CATALOGO,),
    base_url=URL_TESOURO,
    formato="csv",
    encoding="latin-1",
    requer_user_agent_browser=True,
    cache_condicional=True,
    contagem_minima_esperada=CONTAGEM_MINIMA_LINHAS,
    # NTN-B 15/05/2045, taxa de venda da manhã em 09/10/2026. Conferido na ANBIMA do mesmo dia
    # (`data/raw/anbima-ms/ms_261009.txt`: taxa indicativa 6,606) como ordem de grandeza — são
    # taxas diferentes (varejo x secundário), não é igualdade.
    valor_canario=("2026-10-09", 6.65),
    destino_raw="data/raw/tesouro-direto",
    timeout_s=180.0,
)

#: Nome do recurso no CKAN; vira o prefixo determinístico do arquivo em `data/raw/`.
IDENTIFICADOR_RAW = "precotaxatesourodireto"
EXTENSAO_RAW = "csv"

#: Nome do Parquet processado, relativo a `data/processed/`.
NOME_PROCESSADO = "tesouro-direto/td_painel.parquet"

# ─────────────────────────────────────────────────────────────────────────────
# Layout do CSV
# ─────────────────────────────────────────────────────────────────────────────

COLUNA_TIPO = "Tipo Titulo"
COLUNA_VENCIMENTO = "Data Vencimento"
COLUNA_DATA_BASE = "Data Base"

#: Nome comercial do título (como a fonte escreve) → sigla tradicional usada no `series_id`.
#: A chave é o rótulo **normalizado** (`normalizar_rotulo`: sem espaço, maiúsculas), porque
#: "Tesouro IPCA+  com Juros Semestrais" e "Tesouro IPCA+ com Juros Semestrais" são o mesmo
#: título (R14).
SIGLA_POR_TIPO: dict[str, str] = {
    normalizar_rotulo("Tesouro Prefixado"): "LTN",
    normalizar_rotulo("Tesouro Prefixado com Juros Semestrais"): "NTNF",
    normalizar_rotulo("Tesouro IPCA+ com Juros Semestrais"): "NTNB",
    normalizar_rotulo("Tesouro IPCA+"): "NTNBP",
    normalizar_rotulo("Tesouro IGPM+ com Juros Semestrais"): "NTNC",
    normalizar_rotulo("Tesouro Selic"): "LFT",
    normalizar_rotulo("Tesouro Educa+"): "EDUCA",
    normalizar_rotulo("Tesouro Renda+ Aposentadoria Extra"): "RENDA",
}
"""Os 8 tipos de título medidos no arquivo completo (CA-020). Tipo novo **levanta**: um título
que o Tesouro lance amanhã tem de entrar aqui por decisão, não ser absorvido em silêncio."""

#: Coluna numérica do CSV → (sufixo de métrica no `series_id`, unidade).
METRICA_POR_COLUNA: dict[str, tuple[str, Unidade]] = {
    "Taxa Compra Manha": ("TAXA_COMPRA", Unidade.PCT_AA),
    "Taxa Venda Manha": ("TAXA_VENDA", Unidade.PCT_AA),
    "PU Compra Manha": ("PU_COMPRA", Unidade.BRL),
    "PU Venda Manha": ("PU_VENDA", Unidade.BRL),
    "PU Base Manha": ("PU_BASE", Unidade.BRL),
}

COLUNAS_ESPERADAS: tuple[str, ...] = (
    COLUNA_TIPO,
    COLUNA_VENCIMENTO,
    COLUNA_DATA_BASE,
    *METRICA_POR_COLUNA,
)
"""As 8 colunas do CSV, na ordem em que a fonte as serve. Divergência = mudança de layout."""

#: Colunas do painel tipado que `parse_painel` devolve (ordem estável).
COLUNAS_PAINEL: tuple[str, ...] = (
    "tipo_titulo",
    "sigla",
    "data_vencimento",
    "data_base",
    *(metrica for metrica, _ in METRICA_POR_COLUNA.values()),
)

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

PREFIXO_SERIES_ID = "TD"
FREQ = "D"

# ─────────────────────────────────────────────────────────────────────────────
# series_id composto — a convenção que F-016 consome
# ─────────────────────────────────────────────────────────────────────────────


def montar_series_id(sigla: str, vencimento: date, metrica: str) -> str:
    """`TD_<SIGLA>_<AAAAMMDD>_<METRICA>` — ex.: `TD_NTNB_20450515_TAXA_VENDA`.

    Determinístico e reversível (`decompor_series_id`). Casa com o padrão de `series_id` do
    schema (`^[A-Z0-9_\\.\\^=\\-]+$`), por isso a sigla vai sem hífen: `NTNB`, não `NTN-B`.
    """
    if sigla not in set(SIGLA_POR_TIPO.values()):
        msg = f"sigla desconhecida {sigla!r}; conhecidas: {sorted(set(SIGLA_POR_TIPO.values()))}"
        raise ErroDeExtracao(msg)
    metricas = {m for m, _ in METRICA_POR_COLUNA.values()}
    if metrica not in metricas:
        msg = f"métrica desconhecida {metrica!r}; conhecidas: {sorted(metricas)}"
        raise ErroDeExtracao(msg)
    return f"{PREFIXO_SERIES_ID}_{sigla}_{vencimento:%Y%m%d}_{metrica}"


def decompor_series_id(series_id: str) -> tuple[str, date, str]:
    """Inverso de `montar_series_id`: `(sigla, vencimento, metrica)`.

    É o que permite a F-016 remontar o painel `(vencimento × data)` a partir da tabela longa sem
    reabrir o CSV nem reimplementar a convenção.
    """
    partes = series_id.split("_")
    minimo_de_partes = 4
    if len(partes) < minimo_de_partes or partes[0] != PREFIXO_SERIES_ID:
        msg = f"{series_id!r} não é series_id do Tesouro Direto (esperado TD_<SIGLA>_<AAAAMMDD>_…)"
        raise ErroDeExtracao(msg)
    sigla = partes[1]
    vencimento = para_data(partes[2], FormatoData.AAAAMMDD, origem=series_id)
    if vencimento is None:
        msg = f"{series_id!r}: vencimento vazio"
        raise ErroDeExtracao(msg)
    metrica = "_".join(partes[3:])
    if sigla not in set(SIGLA_POR_TIPO.values()):
        msg = f"{series_id!r}: sigla desconhecida {sigla!r}"
        raise ErroDeExtracao(msg)
    if metrica not in {m for m, _ in METRICA_POR_COLUNA.values()}:
        msg = f"{series_id!r}: métrica desconhecida {metrica!r}"
        raise ErroDeExtracao(msg)
    return sigla, vencimento, metrica


# ─────────────────────────────────────────────────────────────────────────────
# Leitura e parse
# ─────────────────────────────────────────────────────────────────────────────


def ler_csv_bruto(conteudo: bytes, *, encoding: str = CONFIG.encoding) -> pd.DataFrame:
    """Bytes → DataFrame de **strings**, sem nenhuma conversão de tipo.

    Duas guardas antes do `read_csv`, nesta ordem:

    1. **magic bytes** — a página de erro do CKAN é HTML (`<!DOCTYPE html>`, medido: 404 com
       17.124 bytes). `read_csv` engoliria isso e devolveria um quadro de uma coluna (R1/R11);
    2. **cabeçalho** — as 8 colunas de `COLUNAS_ESPERADAS`, nos nomes exatos da fonte.

    `encoding` é argumento explícito (CA-022) e `dtype=str`/`keep_default_na=False` garantem que
    nenhuma string vire `NaN` por conta do pandas: quem decide o que é ausência é
    `para_float_ptbr` (Anti-SPEC §10.1.4).
    """
    if detectar_formato(conteudo) is FormatoDetectado.VAZIO:
        msg = f"{CONFIG.nome}: corpo vazio onde se esperava o CSV de 14,6 MB"
        raise RespostaDeErroComStatus200(msg)
    exigir_formato(conteudo, FormatoDetectado.TEXTO, origem=f"{CONFIG.nome} ({CONFIG.base_url})")
    quadro = pd.read_csv(
        io.BytesIO(conteudo),
        sep=";",
        dtype=str,
        encoding=encoding,
        keep_default_na=False,
    )
    _exigir_cabecalho(tuple(quadro.columns))
    return quadro


def _exigir_cabecalho(colunas: Sequence[str]) -> None:
    if tuple(colunas) == COLUNAS_ESPERADAS:
        return
    faltando = [c for c in COLUNAS_ESPERADAS if c not in colunas]
    sobrando = [c for c in colunas if c not in COLUNAS_ESPERADAS]
    msg = (
        f"{CONFIG.nome}: cabeçalho inesperado. Faltando {faltando}, sobrando {sobrando}. "
        f"Recebido {list(colunas)}"
    )
    raise FormatoInesperado(msg)


def parse_painel(conteudo: bytes, *, encoding: str = CONFIG.encoding) -> pd.DataFrame:
    """CSV cru → painel tipado `(tipo, sigla, vencimento, data base, 5 métricas)`.

    Conversões, todas com o formato **declarado**: datas por `para_data(…, DD_MM_AAAA)`, números
    por `para_float_ptbr`. A conversão é feita sobre os **valores distintos** de cada coluna e
    depois mapeada — mesma semântica do normalizador, uma fração das chamadas (o arquivo completo
    tem 886.300 células numéricas e 268.569 valores distintos).
    """
    bruto = ler_csv_bruto(conteudo, encoding=encoding)
    painel = pd.DataFrame(index=bruto.index)

    painel["tipo_titulo"] = bruto[COLUNA_TIPO].str.strip()
    painel["sigla"] = _siglas(painel["tipo_titulo"])
    painel["data_vencimento"] = _coluna_de_data(bruto[COLUNA_VENCIMENTO], COLUNA_VENCIMENTO)
    painel["data_base"] = _coluna_de_data(bruto[COLUNA_DATA_BASE], COLUNA_DATA_BASE)
    for coluna, (metrica, _unidade) in METRICA_POR_COLUNA.items():
        painel[metrica] = _coluna_de_numero(bruto[coluna], coluna)

    painel = painel[list(COLUNAS_PAINEL)]
    painel = _exigir_datas_presentes(painel)
    painel, descartadas = deduplicar_painel(painel)
    if descartadas:
        _log.info(
            "%s: %d linha(s) duplicada(s) idêntica(s) descartada(s)", CONFIG.nome, descartadas
        )
    return painel.sort_values(["data_base", "sigla", "data_vencimento"]).reset_index(drop=True)


def _siglas(tipos: pd.Series) -> pd.Series:
    """Nome comercial → sigla. Tipo desconhecido **levanta** (CA-020), nunca é descartado."""
    rotulos = {valor: normalizar_rotulo(valor) for valor in tipos.unique()}
    desconhecidos = sorted(
        valor for valor, rotulo in rotulos.items() if rotulo not in SIGLA_POR_TIPO
    )
    if desconhecidos:
        msg = (
            f"{CONFIG.nome}: tipo de título desconhecido {desconhecidos}. A fonte tinha 8 tipos em "
            f"2026-10-10; título novo entra em SIGLA_POR_TIPO por decisão, não em silêncio"
        )
        raise FormatoInesperado(msg)
    return tipos.map({valor: SIGLA_POR_TIPO[rotulo] for valor, rotulo in rotulos.items()})


def _coluna_de_data(coluna: pd.Series, nome: str) -> pd.Series:
    """`dd/mm/aaaa` → `date` pelo mapa dos valores distintos (5.436 datas base, 177.260 linhas)."""
    mapa = {
        valor: para_data(valor, FormatoData.DD_MM_AAAA, origem=f"{CONFIG.nome}.{nome}")
        for valor in coluna.unique()
    }
    return coluna.map(mapa)


def _coluna_de_numero(coluna: pd.Series, nome: str) -> pd.Series:
    """Decimal vírgula → `float`; ausência → `None` (nunca `0`, Anti-SPEC §10.1.4)."""
    mapa = {
        valor: para_float_ptbr(valor, origem=f"{CONFIG.nome}.{nome}") for valor in coluna.unique()
    }
    return coluna.map(mapa).astype("float64")


def _exigir_datas_presentes(painel: pd.DataFrame) -> pd.DataFrame:
    """`Data Base` ou `Data Vencimento` vazia é linha sem identidade — levanta, não descarta."""
    sem_data = painel["data_base"].isna() | painel["data_vencimento"].isna()
    if bool(sem_data.any()):
        msg = (
            f"{CONFIG.nome}: {int(sem_data.sum())} linha(s) sem Data Base ou Data Vencimento — "
            f"a fonte não faz isso; é mudança de layout ou corpo corrompido"
        )
        raise FormatoInesperado(msg)
    return painel


def deduplicar_painel(painel: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Uma linha por `(sigla, vencimento, data base)`.

    O arquivo medido em 2026-10-10 tem **zero** duplicatas — e é justamente por isso que a guarda
    existe: se amanhã aparecer uma, ou é republicação idêntica (descartável) ou é revisão de valor
    (**não** descartável, porque escolher uma das duas em silêncio é inventar número).
    """
    chave = ["sigla", "data_vencimento", "data_base"]
    duplicadas = painel.duplicated(subset=chave, keep=False)
    if not bool(duplicadas.any()):
        return painel, 0

    conflitantes = painel.loc[duplicadas].duplicated(subset=list(COLUNAS_PAINEL), keep=False)
    divergentes = painel.loc[duplicadas].loc[~conflitantes]
    if len(divergentes):
        amostra = divergentes.head(4).to_dict(orient="records")
        msg = (
            f"{CONFIG.nome}: {len(divergentes)} linha(s) com a mesma chave "
            f"(sigla, vencimento, data base) e valores DIFERENTES. Amostra: {amostra}"
        )
        raise FormatoInesperado(msg)

    limpo = painel.drop_duplicates(subset=chave, keep="first")
    return limpo, len(painel) - len(limpo)


# ─────────────────────────────────────────────────────────────────────────────
# Guardas do arquivo completo (CA-021 e R2)
# ─────────────────────────────────────────────────────────────────────────────


def resumo_cobertura(painel: pd.DataFrame) -> dict[str, object]:
    """`(dias úteis de 2006, min, max)` da `Data Base` — a evidência de dados, sem julgar."""
    datas = pd.to_datetime(painel["data_base"])
    de_2006 = datas[datas.dt.year == 2006]
    return {
        "dias_uteis_2006": int(de_2006.dt.normalize().nunique()),
        "data_base_min": datas.min().date(),
        "data_base_max": datas.max().date(),
    }


def exigir_cobertura_historica(painel: pd.DataFrame) -> dict[str, object]:
    """CA-021: o arquivo completo cobre 2006 com >= 240 dias úteis e começa até 2005-01-03.

    Não é cosmético: o CKAN já serviu, em outras rotas deste projeto, resposta truncada com
    status 200. Se a janela de 20 anos encurtar, o pipeline tem de parar aqui — e não três
    camadas depois, com um regime macro a menos.
    """
    resumo = resumo_cobertura(painel)
    dias_2006 = int(resumo["dias_uteis_2006"])  # type: ignore[arg-type]
    minimo: date = resumo["data_base_min"]  # type: ignore[assignment]
    if minimo > DATA_BASE_MAIS_ANTIGA_ACEITA:
        msg = (
            f"{CONFIG.nome}: Data Base mais antiga é {minimo.isoformat()}, esperado "
            f"<= {DATA_BASE_MAIS_ANTIGA_ACEITA.isoformat()} (CA-021) — a fonte encurtou o histórico"
        )
        raise RespostaDeErroComStatus200(msg)
    if dias_2006 < MINIMO_DIAS_UTEIS_2006:
        msg = (
            f"{CONFIG.nome}: {dias_2006} dias úteis em 2006, esperado "
            f">= {MINIMO_DIAS_UTEIS_2006} (CA-021) — provável truncamento silencioso (R2)"
        )
        raise RespostaDeErroComStatus200(msg)
    return resumo


# ─────────────────────────────────────────────────────────────────────────────
# Painel → tabela longa de ProcessedSeriesSchema
# ─────────────────────────────────────────────────────────────────────────────


def para_long(painel: pd.DataFrame, *, collected_at: datetime) -> pd.DataFrame:
    """Painel → as 8 colunas de `ProcessedSeriesSchema`, uma linha por `(series_id, date)`.

    5 métricas por linha do painel ⇒ 5 linhas longas. **`vintage` = a data (sem hora) de
    `collected_at`** (D-b da consolidação da Onda 1), e `collected_at` vem do manifesto do bruto,
    não do relógio: o Tesouro **não revisa** taxa publicada, então aqui o vintage não carrega
    informação nova — carrega a mesma convenção do resto de `data/processed/`, onde a PK é
    `(series_id, date, vintage)`.
    """
    if painel.empty:
        msg = f"{CONFIG.nome}: painel vazio — nada a gravar (CA-003)"
        raise RespostaDeErroComStatus200(msg)

    vencimentos = pd.to_datetime(painel["data_vencimento"]).dt.strftime("%Y%m%d")
    datas = pd.to_datetime(painel["data_base"])
    momento = pd.Timestamp(collected_at).tz_localize(None)
    vintage = momento.normalize()
    blocos: list[pd.DataFrame] = []
    for metrica, unidade in METRICA_POR_COLUNA.values():
        blocos.append(
            pd.DataFrame(
                {
                    "series_id": PREFIXO_SERIES_ID
                    + "_"
                    + painel["sigla"].astype(str)
                    + "_"
                    + vencimentos
                    + "_"
                    + metrica,
                    "date": datas,
                    "value": painel[metrica].astype("float64"),
                    "source": Fonte.TESOURO_CKAN.value,
                    "freq": FREQ,
                    "vintage": vintage,
                    "unit": unidade.value,
                    "collected_at": momento,
                }
            )
        )
    longo = pd.concat(blocos, ignore_index=True)
    longo = longo[list(COLUNAS_PROCESSADAS)]
    return longo.sort_values(["series_id", "date"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Download com cache condicional (R21)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoDownload:
    """O que o download fez — o extrator loga isto em vez de adivinhar."""

    caminho: Path
    sha256: str
    conteudo: bytes
    #: A fonte respondeu HTTP 304: o arquivado continua válido, nada foi transferido.
    nao_modificada: bool
    #: Nada foi escrito em `data/raw/` nesta execução.
    idempotente: bool


def arquivos_arquivados(*, raiz: Path | None = None) -> list[Path]:
    """Arquivos brutos já baixados, do mais antigo para o mais recente (nome é `…__AAAA-MM-DD`)."""
    destino = caminho_destino_raw(CONFIG, raiz=raiz)
    if not destino.is_dir():
        return []
    # Filtro do manifesto por disciplina: aqui a extensão é `.csv` e o `.meta.json` não casa,
    # mas em fonte JSON casa e ordenaria antes do dado (D-c da consolidação da Onda 1).
    return sorted(
        c
        for c in destino.glob(f"{IDENTIFICADOR_RAW}__*.{EXTENSAO_RAW}")
        if not c.name.endswith(SUFIXO_MANIFESTO)
    )


def caminho_bruto_mais_recente(*, raiz: Path | None = None) -> Path:
    """Último bruto arquivado — a entrada do modo `--offline`.

    Aceita, como último recurso, a amostra `td.csv` deixada pela pesquisa em
    `data/raw/tesouro-direto/` (é dado real da fonte, com procedência em
    `docs/research/fontes-de-dados.md §PROCEDÊNCIA`), avisando no log. Sem nenhum dos dois,
    levanta: `--offline` não tem licença para inventar série.

    Devolver o caminho **não** significa que ele serve: `td.csv` não tem `.meta.json`, e
    `extrair` recusa bruto sem manifesto (`ManifestoAusente`) porque `collected_at`/`vintage`
    sairiam do relógio da rodada. Quem quiser reprocessar a amostra assume a safra por escrito,
    em `collected_at=`.
    """
    arquivados = arquivos_arquivados(raiz=raiz)
    if arquivados:
        return arquivados[-1]
    amostra = caminho_destino_raw(CONFIG, raiz=raiz) / "td.csv"
    if amostra.is_file():
        _log.warning(
            "%s: nenhum %s__*.csv arquivado; usando a amostra da pesquisa %s",
            CONFIG.nome,
            IDENTIFICADOR_RAW,
            amostra.name,
        )
        return amostra
    msg = (
        f"{CONFIG.nome}: --offline sem bruto arquivado em "
        f"{caminho_destino_raw(CONFIG, raiz=raiz)}. Rode uma vez online antes"
    )
    raise ErroDeExtracao(msg)


def baixar(
    *,
    cliente: ClienteHTTP | None = None,
    transporte: Transporte | None = None,
    data_ref: date | None = None,
    raiz: Path | None = None,
    forcar: bool = False,
) -> ResultadoDownload:
    """GET condicional + arquivamento idempotente em `data/raw/tesouro-direto/`.

    O fluxo normal **não** transfere 14,6 MB (R21): lê `ETag`/`Last-Modified` do manifesto do
    último arquivo baixado, manda `If-None-Match`/`If-Modified-Since` e, no 304 (medido ao vivo
    em 2026-10-10), reaproveita o arquivado. `forcar=True` ignora os validadores.
    """
    # Data **local**, não UTC: o arquivo é republicado por dia útil brasileiro, e às 21h de
    # Brasília o UTC já virou — nomear pelo UTC criaria dois arquivos para o mesmo dia de pregão.
    quando = data_ref or date.today()  # noqa: DTZ011 - ver comentário acima
    cliente = cliente or ClienteHTTP(CONFIG, transporte=transporte)
    destino = caminho_destino_raw(CONFIG, raiz=raiz)
    nome = nome_arquivo_raw(IDENTIFICADOR_RAW, data_ref=quando, extensao=EXTENSAO_RAW)
    alvo = destino / nome

    arquivados = arquivos_arquivados(raiz=raiz)
    base_do_cache = alvo if alvo.is_file() else (arquivados[-1] if arquivados else None)
    etag, last_modified = (None, None)
    if base_do_cache is not None and not forcar:
        etag, last_modified = validadores_condicionais(base_do_cache)

    resposta = cliente.get(etag=etag, last_modified=last_modified)

    if resposta.nao_modificada:
        if base_do_cache is None:  # pragma: no cover - a fonte não manda 304 sem validador
            msg = f"{CONFIG.nome}: HTTP 304 sem arquivo arquivado para reaproveitar"
            raise ErroDeExtracao(msg)
        conteudo = base_do_cache.read_bytes()
        _log.info(
            "%s: HTTP 304 — reaproveitando %s (%d bytes, nada transferido)",
            CONFIG.nome,
            base_do_cache.name,
            len(conteudo),
        )
        return ResultadoDownload(
            caminho=base_do_cache,
            sha256=sha256_de(conteudo),
            conteudo=conteudo,
            nao_modificada=True,
            idempotente=True,
        )

    exigir_formato(resposta.conteudo, FormatoDetectado.TEXTO, origem=resposta.url)
    resultado = arquivar_bruto(
        resposta.conteudo,
        destino=destino,
        nome=nome,
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
    )
    return ResultadoDownload(
        caminho=resultado.caminho,
        sha256=resultado.sha256,
        conteudo=resposta.conteudo,
        nao_modificada=False,
        idempotente=resultado.idempotente,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoExtracao:
    """Resumo de uma execução — é o que alimenta a evidência de dados do Feature Contract."""

    caminho_raw: Path
    sha256_raw: str
    caminho_processado: Path
    linhas_painel: int
    linhas_long: int
    series: int
    data_base_min: date
    data_base_max: date
    dias_uteis_2006: int
    nao_modificada: bool

    def resumo(self) -> str:
        """Uma linha para o log/stdout da CLI.

        **Só ASCII**: o console do Windows é cp1252 e `print("→")` levanta `UnicodeEncodeError`
        no fim de uma execução que já gravou tudo — falha ruidosa no lugar errado.
        """
        return (
            f"{self.linhas_painel} linhas de painel -> {self.linhas_long} linhas longas em "
            f"{self.series} series_id | {self.data_base_min.isoformat()} -> "
            f"{self.data_base_max.isoformat()} | {self.dias_uteis_2006} dias uteis em 2006 | "
            f"raw sha256={self.sha256_raw[:12]} ({'304' if self.nao_modificada else 'baixado'})"
        )


def extrair(
    *,
    offline: bool = False,
    cliente: ClienteHTTP | None = None,
    transporte: Transporte | None = None,
    data_ref: date | None = None,
    raiz: Path | None = None,
    forcar: bool = False,
    collected_at: datetime | None = None,
    minimo_linhas: int | None = None,
    exigir_cobertura: bool = True,
) -> ResultadoExtracao:
    """Caminho completo: bruto → painel tipado → tabela longa → Parquet validado.

    `minimo_linhas` e `exigir_cobertura` existem para que o teste de ponta a ponta possa rodar
    sobre o **recorte real** de 171 linhas da fixture sem afrouxar o contrato do arquivo completo
    (os defaults são `CONTAGEM_MINIMA_LINHAS` e `True`, e há teste de que são esses).
    """
    if offline:
        caminho = caminho_bruto_mais_recente(raiz=raiz)
        conteudo = caminho.read_bytes()
        bruto = ResultadoDownload(
            caminho=caminho,
            sha256=sha256_de(conteudo),
            conteudo=conteudo,
            nao_modificada=False,
            idempotente=True,
        )
        _log.info("%s: modo offline sobre %s (%d bytes)", CONFIG.nome, caminho.name, len(conteudo))
    else:
        bruto = baixar(
            cliente=cliente, transporte=transporte, data_ref=data_ref, raiz=raiz, forcar=forcar
        )

    # D-b: `collected_at` (e portanto `vintage`) sai do manifesto do bruto arquivado, não do
    # relógio desta rodada — é o que faz `--offline` reproduzir o mesmo Parquet. Bruto sem
    # manifesto é **recusado** (`ManifestoAusente`): era o P1 de F-005 no QA da Onda 1, alcançável
    # porque `caminho_bruto_mais_recente` aceita a amostra `td.csv`, que não tem manifesto.
    agora = collected_at_do_bruto(bruto.caminho, collected_at=collected_at)

    painel = parse_painel(bruto.conteudo)
    exigir_contagem_minima(
        len(painel),
        minimo=CONTAGEM_MINIMA_LINHAS if minimo_linhas is None else minimo_linhas,
        origem=f"{CONFIG.nome} @ {bruto.caminho.name}",
    )
    medir = exigir_cobertura_historica if exigir_cobertura else resumo_cobertura
    cobertura = medir(painel)

    longo = para_long(painel, collected_at=agora)
    destino = gravar_processado_parquet(longo, nome=NOME_PROCESSADO, raiz=raiz)

    resultado = ResultadoExtracao(
        caminho_raw=bruto.caminho,
        sha256_raw=bruto.sha256,
        caminho_processado=destino,
        linhas_painel=len(painel),
        linhas_long=len(longo),
        series=int(longo["series_id"].nunique()),
        data_base_min=cobertura["data_base_min"],  # type: ignore[arg-type]
        data_base_max=cobertura["data_base_max"],  # type: ignore[arg-type]
        dias_uteis_2006=int(cobertura["dias_uteis_2006"]),  # type: ignore[arg-type]
        nao_modificada=bruto.nao_modificada,
    )
    _log.info("%s: %s", CONFIG.nome, resultado.resumo())
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _argumentos(argv: Sequence[str] | None = None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.tesouro_direto",
        description="Extrai taxas e PUs do Tesouro Direto (F-005) para data/processed/.",
    )
    analisador.add_argument(
        "--offline",
        action="store_true",
        help="não vai à rede: relê o último bruto arquivado em data/raw/tesouro-direto/",
    )
    analisador.add_argument(
        "--forcar",
        action="store_true",
        help="ignora ETag/Last-Modified e baixa os 14,6 MB de novo",
    )
    return analisador.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` = série gravada; `1` = falha ruidosa, nada gravado."""
    args = _argumentos(argv)
    configurar_logging()
    try:
        resultado = extrair(offline=args.offline, forcar=args.forcar)
    except ErroDeExtracao as exc:
        print(f"FALHA: {exc}", file=sys.stderr)  # noqa: T201 - é a saída da CLI
        return 1
    print(resultado.resumo())  # noqa: T201 - é a saída da CLI
    print(f"processado: {resultado.caminho_processado}")  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de processo
    raise SystemExit(main())
