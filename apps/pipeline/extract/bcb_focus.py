"""Extrator BCB Focus — expectativas de mercado via API Olinda / OData v4 (F-010).

Cobre RF-007 (CA-017, CA-018, CA-019) e o item **A3** do e-mail do Alexandre. Cinco EntitySets:
`ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`, `ExpectativasMercadoTrimestrais`,
`ExpectativasMercadoSelic` e `ExpectativasMercadoInflacao12Meses`.

```bash
python -m apps.pipeline.extract.bcb_focus                        # os 5 EntitySets do catálogo
python -m apps.pipeline.extract.bcb_focus --series FOCUS_ANUAIS   # um EntitySet
python -m apps.pipeline.extract.bcb_focus --offline               # relê o bruto já arquivado
```

O que este módulo **não** faz: nenhuma escolha de "última pesquisa do trimestre", nenhuma
agregação para a grade trimestral, nenhuma surpresa (realizado − esperado). Isso é alinhamento
(F-014/F-015). Aqui a série sai na **frequência nativa da fonte** — uma observação por **data da
pesquisa**, `freq=D` — em `data/processed/focus/<series_id do catálogo>.parquet`, validada por
`ProcessedSeriesSchema`.

## Por que o Focus é diferente de toda outra fonte do projeto

É o único dado macro **sem look-ahead** (`docs/research/metodologia-regimes-macro.md §1.5, §5.1`):
a mediana da pesquisa do dia X era conhecida no dia X. Por isso a convenção de data aqui é
deliberadamente **diferente** de D-a (fim de período), e precisa estar explícita para F-015:

- **`date` = `Data` da fonte = o dia da pesquisa.** Não é o período de referência da expectativa.
  Converter para fim de período destruiria exatamente a propriedade que torna o Focus útil.
- **o horizonte vai para o `series_id`**, não para a data. `FOCUS_A_IPCA_H0` é "o que o mercado
  esperava, no dia da pesquisa, para o IPCA do **ano-calendário corrente**"; `H1`, para o ano
  seguinte. Assim cada `series_id` é uma série temporal honesta, diária, de 20+ anos.
- **`freq=D`** — é o que o catálogo declara para os 5 EntitySets, e é a frequência nativa medida
  (IPCA anual em 2006: **249 observações**, os 249 dias úteis do ano).
- **`vintage` = data (sem hora) de `collected_at`**, e `collected_at` sai do **manifesto** do bruto
  (D-b), nunca do relógio. Note que `vintage` aqui é a safra de *extração* (quando baixamos), e é
  diferente do `date` (quando o mercado respondeu) — no Focus os dois não se confundem, porque a
  fonte **não revisa** pesquisa passada.

## `series_id` composto — a convenção que F-015 consome

O catálogo registra o **EntitySet** (`FOCUS_ANUAIS`, `FOCUS_MENSAIS`, …), não a série: um
EntitySet traz dezenas de indicadores × dezenas de horizontes. A ponte para o schema longo é um
`series_id` **composto**, exatamente como o painel do Tesouro Direto faz em F-005:

```
FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>
     ex.: FOCUS_A_IPCA_H0            IPCA do ano-calendário corrente
          FOCUS_A_SELIC_H1           Selic de fim do ano seguinte
          FOCUS_Q_PIB_TOTAL_HM1      PIB Total do trimestre já encerrado e ainda não divulgado
          FOCUS_I12_IPCA_S           IPCA 12 meses à frente, série suavizada
          FOCUS_RCOPOM_SELIC_R1-2027 Selic esperada para a 1ª reunião do Copom de 2027
```

- `ESCOPO` ∈ `A` (anuais), `M` (mensais), `Q` (trimestrais), `I12` (inflação 12 meses),
  `RCOPOM` (por reunião do Copom) — ver `ESCOPO_POR_ENTITYSET`.
- `INDICADOR` é o rótulo da fonte sem acento e sem espaço: `IPCA`, `SELIC`, `PIB_TOTAL`, `CAMBIO`.
- `CHAVE` é o horizonte, **relativo à data da pesquisa** e portanto conhecido no dia:
  `H0` = período corrente, `H1` = o seguinte, `HM1` = o anterior (H menos 1); `S`/`N` para a
  suavização da inflação 12 meses; `R<n>-<ano>` para a reunião do Copom, que é **absoluta** porque
  o horizonte relativo exigiria o calendário do Copom (que esta fonte não entrega).
- Nenhum deles entra no `series_catalog`: o catálogo registra a fonte, e `decompor_series_id`
  recupera `(escopo, indicador, chave)` sem reabrir o JSON.

## Armadilhas que o código abaixo trata (`docs/research/fontes-de-dados.md §A2` + medições de hoje)

1. **`$top` alto trunca em silêncio** (CA-018, R2). Medido ao vivo em 2026-10-11: `IPCA` anual com
   `baseCalculo=0` tem **32.582 linhas**; com `$top=20000` a resposta vem com **exatamente 20.000**
   linhas e **nenhum `@odata.nextLink`**. Aqui a paginação é explícita (`$skip`/`$top` ≤
   `PAGINA_MAXIMA`), **página cheia nunca é tratada como última** e `recusar_truncamento_silencioso`
   levanta se uma página vier com `LINHAS_SUSPEITAS_DE_TRUNCAMENTO` linhas.
2. **Espaço no `$filter`/`$orderby` tem de ser `%20`, não `+`** — achado **novo** de 2026-10-11, que
   não está na pesquisa. `requests` codifica espaço como `+` em `params=`, e o backend responde
   **HTTP 400** com `"The system query option '$orderby' has the not-allowed value 'Data+asc'."`.
   Por isso a URL é montada por `montar_url` com `quote(..., safe=CARACTERES_SEGUROS_ODATA)` e
   passada **inteira** ao `ClienteHTTP`; nunca via `params=`.
3. **O corpo de erro é JSON dentro de comentário** — `/*{ "codigo": 400, "mensagem": "…" }*/`, sem
   `Content-Type`. Não é JSON válido e não é HTML, então nenhuma das duas guardas genéricas o
   descreve: `validar_corpo_odata` recusa pelo prefixo `/*` com mensagem própria.
4. **A resposta de sucesso é um objeto, não um array** — `{"@odata.context": …, "value": [...]}`.
   `validar_corpo_json_array` (do `common`) recusaria a resposta **boa**; a guarda daqui extrai
   `value` e exige que seja lista.
5. **`baseCalculo` 0 e 1 coexistem na mesma `Data`+`DataReferencia`** (CA-017, gap **G-05**).
   Medido: em 2026-10-01, IPCA/2026 tem `bc=0` (mediana 5,0, 144 respondentes) **e** `bc=1`
   (mediana 5,1, 61 respondentes). `bc=1` só existe **a partir de 2014** — em 2006 e 2010 só há
   `bc=0`. Logo **`baseCalculo=0` é a única escolha com os 20 anos**, e é filtrada no `$filter`
   *e* reconferida no parse.
6. **`$count=true` e `$apply=groupby(...)` são ignorados sem erro.** Não há como pedir contagem à
   fonte: o piso anti-truncamento é declarado por nós (`contagem_minima_esperada`).
7. **`Indicador` inexistente devolve HTTP 200 com `{"value":[]}`** — vazio silencioso, não erro.
   É o que `exigir_contagem_minima` pega.
8. **Capitalização dos campos varia entre EntitySets** (CA-019): `Indicador`/`indicador`,
   `Mediana`/`mediana`, `Reuniao`/`reuniao`, e `numeroRespondentes`/`baseCalculo` em camelCase
   minúsculo nos 5 em escopo. `normalizar_linha` leva tudo para nome canônico em `snake_case`.
9. **Número vem tipado com ponto decimal** (`"Mediana": 15.7000`), não string pt-BR — é
   `para_float_ponto_decimal`. `Minimo`, `Maximo` e `numeroRespondentes` vêm `null` no histórico
   antigo (até ~2010); `Mediana` **nunca** veio nula em 2026-10-11 (consulta `Mediana eq null`
   devolveu vazio), e nulo nela seria ausência de verdade — nunca `0` (Anti-SPEC §10.1.4).
10. **A última pesquisa disponível não é "hoje"**: em 2026-10-11 (domingo) o máximo de `Data` nos
    5 EntitySets é **2026-10-02**. A fonte publica com defasagem; o extrator não a esconde.

**G-04 resolvido nesta feature:** o rótulo exato é **`PIB Total`**, presente em
`ExpectativasMercadoAnuais` e `ExpectativasMercadoTrimestrais` desde 2006. A enumeração completa
dos valores de `Indicador` está em `INDICADORES_ENUMERADOS`.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import pandas as pd

from apps.pipeline.common import (
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    ManifestoAusente,
    RespostaBruta,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    Transporte,
    arquivar_bruto,
    caminho_destino_raw,
    collected_at_do_bruto,
    exigir_contagem_minima,
    gravar_processado_parquet,
    ler_texto,
    nome_arquivo_raw,
    obter_logger,
    obtido_em_arquivado,
    para_data,
    para_float_ponto_decimal,
)
from packages.shared.schemas import (
    ExtractorConfig,
    Fonte,
    Freq,
    SeriesCatalogEntry,
    StatusSerie,
    Unidade,
    load_catalog,
)

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Parâmetros da fonte
# ─────────────────────────────────────────────────────────────────────────────

FONTE_SLUG = "focus"
"""Subpasta de `data/raw/` e de `data/processed/` — a mesma de `tests/fixtures/focus/`."""

DESTINO_RAW = f"data/raw/{FONTE_SLUG}"
URL_BASE_OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"

INICIO_PADRAO = date(2004, 1, 1)
"""Dois anos antes de 1T2006 — a mesma folga de F-003, pelos mesmos motivos (defasagem de
divulgação, média móvel longa e variação 12m do primeiro trimestre)."""

BASE_CALCULO = 0
"""**G-05 resolvido.** `0` = todas as instituições que responderam nos últimos 30 dias;
`1` = só os últimos 5 dias úteis.

A escolha não é de gosto: `baseCalculo=1` **só existe a partir de 2014** (medido ao vivo em
2026-10-11: `bc=1` em 2014/2015/…/2026, ausente em 2006, 2010, 2011, 2012 e 2013). Pedir `1`
cortaria 10 dos 20 anos do e-mail. `0` é também a base mais estável (144 respondentes contra 61 em
2026-10-01), ao custo de reagir mais devagar — que é irrelevante numa grade trimestral."""

PAGINA_MAXIMA = 10000
"""`$top` por página. Dez mil está confortavelmente abaixo do ponto de truncamento silencioso
(20.000) e foi verificado ao vivo: 4 páginas de `$top=10000` reproduzem exatamente as 32.582
linhas que a consulta sem `$top` devolve."""

LINHAS_SUSPEITAS_DE_TRUNCAMENTO = 20000
"""O número exato em que o Olinda corta sem `@odata.nextLink` (CA-018, CB-002). Página com
exatamente este tamanho é **recusada**, nunca concatenada."""

CARACTERES_SEGUROS_ODATA = "$,'/:()"
"""Não percent-encodar o que o OData usa como sintaxe. O espaço **tem** de virar `%20`: com `+`
(o default de `urlencode`) o backend responde HTTP 400 — pegadinha nº 2 do docstring."""

PREFIXO_ERRO_OLINDA = b"/*"
"""O corpo de erro do Olinda é JSON **embrulhado em comentário** (`/*{...}*/`)."""

GAP_MAXIMO_FOCUS_DIAS = 120
"""Maior vão de dias corridos tolerado numa série densa do Focus.

Deliberadamente frouxo. A série não é contínua por natureza: `FOCUS_Q_PIB_TOTAL_HM1` existe só
enquanto o PIB do trimestre encerrado não saiu, e some por algumas semanas depois da divulgação.
A guarda existe para pegar **fatia de ano perdida** (que abriria um vão > 300 dias), não feriado
nem janela estrutural."""

DIAS_DE_FIM_DE_SEMANA = 5
"""`weekday() >= 5` é sábado ou domingo — a pesquisa Focus é de dia útil."""


class Escopo(StrEnum):
    """Primeiro campo do `series_id` composto: qual EntitySet originou a série."""

    ANUAL = "A"
    MENSAL = "M"
    TRIMESTRAL = "Q"
    INFLACAO_12M = "I12"
    REUNIAO_COPOM = "RCOPOM"


ESCOPO_POR_ENTITYSET: Mapping[str, Escopo] = {
    "ExpectativasMercadoAnuais": Escopo.ANUAL,
    "ExpectativaMercadoMensais": Escopo.MENSAL,
    "ExpectativasMercadoTrimestrais": Escopo.TRIMESTRAL,
    "ExpectativasMercadoInflacao12Meses": Escopo.INFLACAO_12M,
    "ExpectativasMercadoSelic": Escopo.REUNIAO_COPOM,
}
"""O nome do EntitySet **não** segue o do EntityType (singular/plural trocados) e não é
normalizável por conta — é literal, copiado do `$metadata` (`fontes-de-dados.md §A2`)."""

INDICADORES_ENUMERADOS: Mapping[str, tuple[str, ...]] = {
    "ExpectativasMercadoAnuais": (
        "Balança comercial",
        "Conta corrente",
        "Câmbio",
        "Dívida bruta do governo geral",
        "Dívida líquida do setor público",
        "IGP-DI",
        "IGP-M",
        "INPC",
        "IPA-DI",
        "IPA-M",
        "IPC-Fipe",
        "IPCA",
        "IPCA Administrados",
        "IPCA Alimentação no domicílio",
        "IPCA Bens industrializados",
        "IPCA Livres",
        "IPCA Serviços",
        "IPCA-15",
        "Investimento direto no país",
        "PIB Agropecuária",
        "PIB Despesa de consumo da administração pública",
        "PIB Despesa de consumo das famílias",
        "PIB Exportação de bens e serviços",
        "PIB Formação Bruta de Capital Fixo",
        "PIB Importação de bens e serviços",
        "PIB Indústria",
        "PIB Serviços",
        "PIB Total",
        "Produção industrial",
        "Resultado nominal",
        "Resultado primário",
        "Selic",
        "Taxa de desocupação",
    ),
    "ExpectativaMercadoMensais": (
        "Câmbio",
        "IGP-DI",
        "IGP-M",
        "INPC",
        "IPA-DI",
        "IPA-M",
        "IPC-Fipe",
        "IPCA",
        "IPCA Administrados",
        "IPCA Alimentação no domicílio",
        "IPCA Bens industrializados",
        "IPCA Livres",
        "IPCA Serviços",
        "IPCA-15",
        "Produção industrial",
        "Taxa de desocupação",
    ),
    "ExpectativasMercadoTrimestrais": (
        "Câmbio",
        "IPCA",
        "IPCA Administrados",
        "IPCA Alimentação no domicílio",
        "IPCA Bens industrializados",
        "IPCA Livres",
        "IPCA Serviços",
        "PIB Agropecuária",
        "PIB Indústria",
        "PIB Serviços",
        "PIB Total",
        "Taxa de desocupação",
    ),
    "ExpectativasMercadoInflacao12Meses": (
        "IGP-DI",
        "IGP-M",
        "INPC",
        "IPA-DI",
        "IPA-M",
        "IPC-Fipe",
        "IPCA",
        "IPCA Administrados",
        "IPCA Alimentação no domicílio",
        "IPCA Bens industrializados",
        "IPCA Livres",
        "IPCA Serviços",
        "IPCA-15",
    ),
    "ExpectativasMercadoSelic": ("Selic",),
}
"""**G-04 resolvido** — `set(Indicador)` medido ao vivo em 2026-10-11 sobre 2006 e 2026 inteiros.

O rótulo de PIB agregado é **`PIB Total`** (não "PIB", não "PIB total"), e existe desde 2006 nos
EntitySets anual e trimestral. A união dos dois anos está aqui porque o conjunto **muda ao longo
da série**: `IPCA Livres`, `Taxa de desocupação` e `Dívida bruta do governo geral` não existiam em
2006; `INPC`, `IPA-DI`, `IPA-M`, `IPC-Fipe` e `IPCA-15` saíram do anual depois. Pedir um indicador
que não existe na janela devolve HTTP 200 com `{"value":[]}` — por isso a contagem mínima existe."""


# ─────────────────────────────────────────────────────────────────────────────
# `series_id` composto
# ─────────────────────────────────────────────────────────────────────────────

PREFIXO_SERIES_ID = "FOCUS"

_SEM_ACENTO = re.compile(r"[^A-Z0-9]+")


def slug_indicador(indicador: str) -> str:
    """`'PIB Total'` → `'PIB_TOTAL'`, `'Câmbio'` → `'CAMBIO'`.

    Sem acento e sem espaço porque `series_id` é `^[A-Z0-9_\\.\\^=\\-]+$` no schema. Sem **hífen**
    porque o hífen é o separador interno da chave de reunião (`R1-2027`), e trocar os dois faria
    `decompor_series_id` devolver silenciosamente a série errada.
    """
    sem_acento = unicodedata.normalize("NFKD", indicador).encode("ascii", "ignore").decode("ascii")
    limpo = _SEM_ACENTO.sub("_", sem_acento.upper()).strip("_")
    if not limpo:
        msg = f"indicador {indicador!r} não produz slug utilizável"
        raise ErroDeExtracao(msg)
    return limpo


def montar_series_id(escopo: Escopo, indicador: str, chave: str) -> str:
    """`FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>` — ex.: `FOCUS_A_PIB_TOTAL_H0`."""
    if "_" in chave:
        msg = f"chave {chave!r} não pode conter '_': quebraria decompor_series_id"
        raise ErroDeExtracao(msg)
    return f"{PREFIXO_SERIES_ID}_{escopo.value}_{slug_indicador(indicador)}_{chave}"


def decompor_series_id(series_id: str) -> tuple[Escopo, str, str]:
    """Inverso de `montar_series_id`: `(escopo, slug do indicador, chave)`.

    É o que permite a F-015 saber **qual horizonte** uma série carrega sem reabrir o JSON bruto
    nem reimplementar a convenção. A chave é o último campo; o indicador é tudo entre o escopo e
    ela (pode ter `_`, como `PIB_TOTAL`).
    """
    partes = series_id.split("_")
    minimo_de_partes = 4
    if len(partes) < minimo_de_partes or partes[0] != PREFIXO_SERIES_ID:
        msg = (
            f"{series_id!r} não é series_id do Focus (esperado FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>)"
        )
        raise ErroDeExtracao(msg)
    try:
        escopo = Escopo(partes[1])
    except ValueError as exc:
        msg = (
            f"{series_id!r}: escopo desconhecido {partes[1]!r}; "
            f"use um de {[e.value for e in Escopo]}"
        )
        raise ErroDeExtracao(msg) from exc
    return escopo, "_".join(partes[2:-1]), partes[-1]


# ─────────────────────────────────────────────────────────────────────────────
# Normalização de campo (CA-019)
# ─────────────────────────────────────────────────────────────────────────────

CAMPOS_CANONICOS: Mapping[str, str] = {
    "indicador": "indicador",
    "indicadordetalhe": "indicador_detalhe",
    "data": "data",
    "datareferencia": "data_referencia",
    "reuniao": "reuniao",
    "suavizada": "suavizada",
    "media": "media",
    "mediana": "mediana",
    "desviopadrao": "desvio_padrao",
    "minimo": "minimo",
    "maximo": "maximo",
    "numerorespondentes": "numero_respondentes",
    "basecalculo": "base_calculo",
    "tipocalculo": "tipo_calculo",
    "periodicidade": "periodicidade",
}
"""Nome do campo na fonte (minúsculo, sem separador) → nome canônico em `snake_case` (CA-019).

A capitalização varia entre EntitySets — `Reuniao` no `ExpectativaMercadoSelic` e `reuniao` no
`ExpectativasMercadoSelicTop5`, `Mediana` contra `mediana`, `Indicador` contra `indicador`. A
chave aqui é a forma **caixa-baixa sem separador**, então a mesma tabela serve aos 13 EntitySets
e nada é inferido: campo que não está nesta tabela levanta, em vez de entrar com nome cru."""


def normalizar_linha(linha: Mapping[str, Any], *, origem: str = "") -> dict[str, Any]:
    """Uma linha da resposta → nomes canônicos (CA-019). Campo desconhecido **levanta**.

    Levantar (em vez de passar o nome cru adiante) é o que faz a fonte mudar de forma aparecer
    como falha em vez de coluna fantasma: se o Olinda acrescentar `coeficienteVariacao` aos 5
    EntitySets em escopo, esta função acusa e alguém decide o que fazer com o campo.
    """
    saida: dict[str, Any] = {}
    for bruto, valor in linha.items():
        if bruto.startswith("@odata"):
            continue
        canonico = CAMPOS_CANONICOS.get(bruto.replace("_", "").lower())
        if canonico is None:
            msg = (
                f"{origem}: campo {bruto!r} não está em CAMPOS_CANONICOS — o EntitySet mudou de "
                f"forma. Conhecidos: {sorted(set(CAMPOS_CANONICOS.values()))}"
            )
            raise RespostaDeErroComStatus200(msg)
        if canonico in saida:
            msg = f"{origem}: dois campos da fonte colapsam em {canonico!r} ({bruto!r})"
            raise RespostaDeErroComStatus200(msg)
        saida[canonico] = valor
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# Horizonte: da linha para a chave do `series_id`
# ─────────────────────────────────────────────────────────────────────────────

CHAVE_POR_HORIZONTE: Mapping[int, str] = {-1: "HM1", 0: "H0", 1: "H1", 2: "H2"}
"""Horizonte **relativo à data da pesquisa** → token da chave. `HM1` é "H menos 1": o período já
encerrado e ainda não divulgado (o único horizonte negativo que é sistemático, no PIB trimestral).
O hífen não entra aqui porque confundiria com a chave de reunião (`R1-2027`)."""

_RE_REUNIAO = re.compile(r"^R(\d{1,2})/(\d{4})$")
_RE_MES_ANO = re.compile(r"^(\d{1,2})/(\d{4})$")
_RE_TRI_ANO = re.compile(r"^([1-4])/(\d{4})$")


def horizonte_anual(quando: date, data_referencia: str, *, origem: str = "") -> int:
    """`DataReferencia` anual (`'2026'`) → horizonte em **anos-calendário** a partir da pesquisa."""
    if not re.fullmatch(r"\d{4}", data_referencia.strip()):
        msg = f"{origem}: DataReferencia anual inesperada {data_referencia!r} (esperado 'AAAA')"
        raise RespostaDeErroComStatus200(msg)
    return int(data_referencia) - quando.year


def horizonte_mensal(quando: date, data_referencia: str, *, origem: str = "") -> int:
    """`DataReferencia` mensal (`'09/2028'`) → horizonte em **meses** a partir da pesquisa."""
    casado = _RE_MES_ANO.fullmatch(data_referencia.strip())
    if not casado:
        msg = f"{origem}: DataReferencia mensal inesperada {data_referencia!r} (esperado 'MM/AAAA')"
        raise RespostaDeErroComStatus200(msg)
    mes, ano = int(casado.group(1)), int(casado.group(2))
    if not 1 <= mes <= 12:  # noqa: PLR2004
        msg = f"{origem}: mês {mes} fora de 1..12 em {data_referencia!r}"
        raise RespostaDeErroComStatus200(msg)
    return (ano * 12 + mes) - (quando.year * 12 + quando.month)


def horizonte_trimestral(quando: date, data_referencia: str, *, origem: str = "") -> int:
    """`DataReferencia` trimestral (`'3/2026'`) → horizonte em **trimestres** a partir da pesquisa.

    Sem zero à esquerda na fonte (`'3/2001'`, não `'03/2001'`) — por isso o regex é próprio e não
    o mensal: `'09/2028'` casaria como trimestre 9 se os dois compartilhassem padrão.
    """
    casado = _RE_TRI_ANO.fullmatch(data_referencia.strip())
    if not casado:
        msg = (
            f"{origem}: DataReferencia trimestral inesperada {data_referencia!r} "
            f"(esperado 'T/AAAA' com T em 1..4)"
        )
        raise RespostaDeErroComStatus200(msg)
    tri, ano = int(casado.group(1)), int(casado.group(2))
    atual = (quando.month - 1) // 3 + 1
    return (ano * 4 + tri) - (quando.year * 4 + atual)


def chave_de_reuniao(reuniao: str, *, origem: str = "") -> str:
    """`'R1/2027'` → `'R1-2027'`. A chave é **absoluta**, não relativa.

    O horizonte relativo ("a próxima reunião") precisaria do calendário do Copom, que este
    EntitySet não entrega: o único jeito de inferir seria olhar as datas de reunião, e inventar
    isso aqui esconderia uma suposição numa chave de série. F-015 escolhe a reunião que quiser.
    """
    casado = _RE_REUNIAO.fullmatch(reuniao.strip())
    if not casado:
        msg = f"{origem}: Reuniao inesperada {reuniao!r} (esperado 'R<n>/AAAA')"
        raise RespostaDeErroComStatus200(msg)
    return f"R{int(casado.group(1))}-{casado.group(2)}"


def chave_de_suavizada(suavizada: object, *, origem: str = "") -> str:
    """`'S'`/`'N'` do campo `Suavizada`, tal e qual — a escolha entre as duas é de F-015."""
    texto = str(suavizada).strip().upper()
    if texto not in ("S", "N"):
        msg = f"{origem}: Suavizada inesperada {suavizada!r} (esperado 'S' ou 'N')"
        raise RespostaDeErroComStatus200(msg)
    return texto


# ─────────────────────────────────────────────────────────────────────────────
# O pacote de séries de cada EntitySet
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PedidoDeIndicador:
    """Um indicador a baixar de um EntitySet, com os horizontes que entram no pacote mínimo."""

    indicador: str
    unit: Unidade
    #: Chaves aceitas. `None` = todas (é o painel de reuniões do Copom).
    chaves: frozenset[str] | None
    #: Séries que devem ter um ponto em (quase) todo dia útil da janela — ganham piso de contagem.
    densa: bool = True
    descricao: str = ""


@dataclass(frozen=True, slots=True)
class PlanoDoEntitySet:
    """O que baixar de um EntitySet e como virar `series_id`."""

    entityset: str
    escopo: Escopo
    pedidos: tuple[PedidoDeIndicador, ...]
    #: `True` quando o `$filter` traz `Indicador eq '…'`. `ExpectativasMercadoSelic` só tem Selic,
    #: e filtrar por ele ali seria ruído na URL (e um arquivo bruto a mais para conferir).
    filtra_indicador: bool = True


def _chaves(*valores: str) -> frozenset[str]:
    return frozenset(valores)


PLANO: Mapping[str, PlanoDoEntitySet] = {
    "FOCUS_ANUAIS": PlanoDoEntitySet(
        entityset="ExpectativasMercadoAnuais",
        escopo=Escopo.ANUAL,
        pedidos=(
            PedidoDeIndicador(
                "IPCA", Unidade.PCT, _chaves("H0", "H1"), descricao="IPCA do ano-calendário"
            ),
            PedidoDeIndicador(
                "Selic", Unidade.PCT_AA, _chaves("H0", "H1"), descricao="Selic de fim de ano"
            ),
            PedidoDeIndicador(
                "PIB Total", Unidade.PCT, _chaves("H0", "H1"), descricao="PIB Total do ano"
            ),
            PedidoDeIndicador(
                "Câmbio", Unidade.BRL, _chaves("H0", "H1"), descricao="USDBRL de fim de ano"
            ),
        ),
    ),
    "FOCUS_MENSAIS": PlanoDoEntitySet(
        entityset="ExpectativaMercadoMensais",
        escopo=Escopo.MENSAL,
        pedidos=(
            PedidoDeIndicador(
                "IPCA", Unidade.PCT, _chaves("H0", "H1"), descricao="IPCA do mês de referência"
            ),
        ),
    ),
    "FOCUS_TRIMESTRAIS": PlanoDoEntitySet(
        entityset="ExpectativasMercadoTrimestrais",
        escopo=Escopo.TRIMESTRAL,
        pedidos=(
            PedidoDeIndicador(
                "PIB Total",
                Unidade.PCT,
                _chaves("HM1", "H0", "H1"),
                densa=False,
                descricao="PIB Total do trimestre (HM1 = trimestre encerrado e não divulgado)",
            ),
        ),
    ),
    "FOCUS_SELIC": PlanoDoEntitySet(
        entityset="ExpectativasMercadoSelic",
        escopo=Escopo.REUNIAO_COPOM,
        pedidos=(
            PedidoDeIndicador(
                "Selic",
                Unidade.PCT_AA,
                None,
                densa=False,
                descricao="painel: uma série por reunião do Copom (R<n>-<ano>)",
            ),
        ),
        filtra_indicador=False,
    ),
    "FOCUS_INFLACAO_12M": PlanoDoEntitySet(
        entityset="ExpectativasMercadoInflacao12Meses",
        escopo=Escopo.INFLACAO_12M,
        pedidos=(
            PedidoDeIndicador(
                "IPCA",
                Unidade.PCT,
                _chaves("S", "N"),
                descricao="IPCA 12 meses à frente (S = suavizada, N = não suavizada)",
            ),
        ),
    ),
}
"""`series_id` do catálogo → o que baixar daquele EntitySet.

Por que só estes indicadores e estes horizontes: é o que o e-mail pede em **A3** (IPCA, Selic, PIB
e câmbio) e o que a metodologia usa (§1.5 surpresa, §1.7 juro real ex-ante). O EntitySet tem
dezenas de indicadores e até 23 meses de horizonte — baixar tudo seria ~700 mil linhas de dado
que ninguém consome antes de 2026-10-14. Acrescentar série aqui é 1 linha; nada no resto do módulo
é específico de indicador."""

CANARIOS: Mapping[str, tuple[str, float]] = {
    # (data da pesquisa em ISO, Mediana) — conferidos em requisição **independente** contra
    # olinda.bcb.gov.br em 2026-10-11, um `$filter` por canário (ver `docs/wiki/modules/focus.md`).
    "FOCUS_A_IPCA_H0": ("2026-10-02", 5.0129),
    "FOCUS_A_SELIC_H0": ("2026-10-02", 13.5),
    "FOCUS_A_PIB_TOTAL_H0": ("2026-10-02", 1.8549),
    "FOCUS_A_CAMBIO_H0": ("2026-10-02", 5.2),
    "FOCUS_Q_PIB_TOTAL_H0": ("2026-10-02", 1.7696),
    "FOCUS_I12_IPCA_S": ("2026-10-02", 4.5905),
    "FOCUS_I12_IPCA_N": ("2026-10-02", 4.8741),
    # 1T2006 — o canário de cobertura: 1º dia útil de 2006.
    "FOCUS_RCOPOM_SELIC_R1-2007": ("2006-01-02", 15.0),
}

TOLERANCIA_CANARIO = 1e-6

CANARIO_POR_ENTITYSET: Mapping[str, str] = {
    "FOCUS_ANUAIS": "FOCUS_A_IPCA_H0",
    "FOCUS_MENSAIS": "FOCUS_M_IPCA_H0",
    "FOCUS_TRIMESTRAIS": "FOCUS_Q_PIB_TOTAL_H0",
    "FOCUS_SELIC": "FOCUS_RCOPOM_SELIC_R1-2007",
    "FOCUS_INFLACAO_12M": "FOCUS_I12_IPCA_S",
}
"""Qual série carrega o `valor_canario` do `ExtractorConfig` de cada EntitySet. As demais são
conferidas por `conferir_canarios`, que percorre `CANARIOS` inteiro."""


# ─────────────────────────────────────────────────────────────────────────────
# Catálogo → configuração
# ─────────────────────────────────────────────────────────────────────────────

SERIES_PACOTE_MINIMO: tuple[str, ...] = (
    "FOCUS_ANUAIS",
    "FOCUS_MENSAIS",
    "FOCUS_TRIMESTRAIS",
    "FOCUS_SELIC",
    "FOCUS_INFLACAO_12M",
)
"""Os 5 EntitySets do Feature Contract de F-010. `FOCUS_PIB_TOTAL` fica fora: está
`status=a_confirmar` no catálogo com `identificador='a_confirmar'` (era o gap G-04), e **G-04 foi
resolvido nesta feature** — o rótulo é `PIB Total`, dentro de `ExpectativasMercadoAnuais`, e já é
extraído como `FOCUS_A_PIB_TOTAL_H0/H1`. A entrada do catálogo ficou redundante; retirá-la ou
marcá-la é do orquestrador (catálogo congelado nesta onda)."""


def entityset_de(entrada: SeriesCatalogEntry) -> str:
    """Nome do EntitySet, lido do `identificador` do catálogo — nunca hard-coded no extrator."""
    identificador = entrada.identificador
    if identificador not in ESCOPO_POR_ENTITYSET:
        msg = (
            f"{entrada.series_id}: identificador {identificador!r} não é EntitySet conhecido do "
            f"Focus. Conhecidos: {sorted(ESCOPO_POR_ENTITYSET)}"
        )
        raise ErroDeExtracao(msg)
    return identificador


def plano_de(entrada: SeriesCatalogEntry) -> PlanoDoEntitySet:
    """`PlanoDoEntitySet` da entrada do catálogo, com o EntitySet conferido contra `PLANO`."""
    plano = PLANO.get(entrada.series_id)
    if plano is None:
        msg = f"{entrada.series_id}: sem plano de extração em PLANO. Conhecidos: {sorted(PLANO)}"
        raise ErroDeExtracao(msg)
    if plano.entityset != entityset_de(entrada):
        msg = (
            f"{entrada.series_id}: catálogo diz EntitySet {entrada.identificador!r} e PLANO diz "
            f"{plano.entityset!r} — os dois têm de concordar"
        )
        raise ErroDeExtracao(msg)
    return plano


def catalogo_focus(series_ids: Sequence[str] | None = None) -> tuple[SeriesCatalogEntry, ...]:
    """Entradas `fonte=BCB_OLINDA` e `status=ok` do catálogo, na ordem pedida.

    É o portão de CA-053/054: `a_confirmar` (o `FOCUS_PIB_TOTAL`, de identificador literal
    `a_confirmar`) nunca entra no caminho crítico, por mais que G-04 já esteja resolvido.
    """
    usaveis = {
        e.series_id: e
        for e in load_catalog()
        if e.fonte is Fonte.BCB_OLINDA and e.status is StatusSerie.OK
    }
    pedidas = tuple(series_ids) if series_ids is not None else SERIES_PACOTE_MINIMO
    desconhecidas = [s for s in pedidas if s not in usaveis]
    if desconhecidas:
        msg = (
            f"série fora do catálogo Focus usável: {desconhecidas}. Disponíveis: {sorted(usaveis)}"
        )
        raise ErroDeExtracao(msg)
    return tuple(usaveis[s] for s in pedidas)


def _dias_uteis(inicio: date, fim: date) -> int:
    return int(len(pd.bdate_range(inicio, fim))) if fim >= inicio else 0


def contagem_minima(
    entrada: SeriesCatalogEntry,
    plano: PlanoDoEntitySet,
    *,
    inicio: date,
    fim: date,
) -> int:
    """Piso anti-truncamento silencioso (R2) para o **total** baixado do EntitySet.

    Deliberadamente folgado, como no SGS: existe para pegar `{"value":[]}` com HTTP 200, fatia de
    ano perdida e página truncada — não para auditar feriado. A conta é
    `dias úteis da janela × séries densas do plano × 0,7`; o painel de reuniões do Copom e o
    `HM1` do PIB trimestral não entram, porque não têm ponto em todo dia útil.
    """
    comeco = max(inicio, entrada.data_inicio or inicio)
    densas = sum(len(p.chaves or ()) for p in plano.pedidos if p.densa)
    if comeco > fim or densas == 0:
        return 1
    return max(1, int(_dias_uteis(comeco, fim) * densas * 0.70))


def config_para(
    entrada: SeriesCatalogEntry,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
) -> ExtractorConfig:
    """`ExtractorConfig` do EntitySet — é a configuração que carrega a pegadinha, não o código.

    `pagina_com_skip=True` é o campo que o contrato já tinha para exatamente esta fonte ("Olinda
    trunca em `$top=20000` sem `nextLink`"); `janela_maxima_dias` fica `None` porque aqui o
    fatiamento é por **ano-calendário** (`fatiar_por_ano`), não por número de dias.
    """
    fim = fim or date.today()
    plano = plano_de(entrada)
    canario = CANARIO_POR_ENTITYSET.get(entrada.series_id)
    return ExtractorConfig(
        nome=f"bcb_focus_{plano.entityset.lower()}",
        fonte=Fonte.BCB_OLINDA,
        series_ids=(entrada.series_id,),
        base_url=f"{URL_BASE_OLINDA}/{plano.entityset}",
        formato="json",
        encoding="utf-8",
        requer_user_agent_browser=True,
        janela_maxima_dias=None,
        pagina_com_skip=True,
        contagem_minima_esperada=contagem_minima(entrada, plano, inicio=inicio, fim=fim),
        valor_canario=CANARIOS.get(canario or "") if canario else None,
        destino_raw=DESTINO_RAW,
        timeout_s=180.0,
        max_retries=3,
    )


# ─────────────────────────────────────────────────────────────────────────────
# URL OData e guardas de resposta
# ─────────────────────────────────────────────────────────────────────────────


def montar_consulta(opcoes: Mapping[str, str]) -> str:
    """Query string OData com espaço em **`%20`**, não `+`.

    Pegadinha nº 2: `requests` (e `urlencode`) codificam espaço como `+` em `params=`, e o backend
    do Olinda responde **HTTP 400** — `"The system query option '$orderby' has the not-allowed
    value 'Data+asc'"`. Medido em 2026-10-11; não está na pesquisa. Por isso a URL é montada aqui
    e passada inteira ao `ClienteHTTP`.
    """
    return "&".join(
        f"{chave}={quote(str(valor), safe=CARACTERES_SEGUROS_ODATA)}"
        for chave, valor in opcoes.items()
    )


def montar_filtro(
    *,
    indicador: str | None,
    inicio: date,
    fim: date,
    base_calculo: int = BASE_CALCULO,
) -> str:
    """`$filter` por `Indicador`, janela de `Data` e `baseCalculo` — a cláusula de CA-017.

    `Data` é **string** `yyyy-MM-dd` no OData do BCB e se compara com string entre aspas simples
    (`Data ge '2006-01-01'`), não com `datetime'...'`. `baseCalculo eq 0` é o que impede a linha
    dobrada de 2014 em diante.
    """
    termos = []
    if indicador is not None:
        termos.append(f"Indicador eq '{indicador}'")
    termos.append(f"Data ge '{inicio.isoformat()}'")
    termos.append(f"Data le '{fim.isoformat()}'")
    termos.append(f"baseCalculo eq {base_calculo}")
    return " and ".join(termos)


def montar_url(
    entityset: str,
    *,
    indicador: str | None,
    inicio: date,
    fim: date,
    pagina: int,
    top: int = PAGINA_MAXIMA,
    ordenacao: str = "Data asc",
) -> str:
    """URL completa de **uma página** — determinística, e é o que o modo `--offline` reconhece."""
    if top > PAGINA_MAXIMA:
        msg = (
            f"$top={top} acima de PAGINA_MAXIMA={PAGINA_MAXIMA}: o Olinda corta em "
            f"{LINHAS_SUSPEITAS_DE_TRUNCAMENTO} linhas **sem** @odata.nextLink (CA-018). "
            f"Pagine com $skip em vez de aumentar $top"
        )
        raise ErroDeExtracao(msg)
    consulta = montar_consulta(
        {
            "$format": "json",
            "$filter": montar_filtro(indicador=indicador, inicio=inicio, fim=fim),
            "$orderby": ordenacao,
            "$top": str(top),
            "$skip": str(pagina * top),
        }
    )
    return f"{URL_BASE_OLINDA}/{entityset}?{consulta}"


def validar_corpo_odata(
    resposta: RespostaBruta,
    *,
    encoding: str = "utf-8",
) -> list[dict[str, Any]]:
    """Recusa o corpo de erro e devolve `value` — o `validar_corpo_json_array` do OData.

    Três diferenças em relação à guarda genérica do `common`, todas medidas em 2026-10-11:

    1. a resposta **boa** é um objeto (`{"@odata.context": …, "value": [...]}`), que a guarda
       genérica recusaria;
    2. o corpo de **erro** é JSON embrulhado em comentário (`/*{"codigo":400,…}*/`), que não é
       JSON válido nem HTML — nenhuma das duas mensagens genéricas o descreveria;
    3. `{"value": []}` com HTTP 200 é a resposta a `Indicador` inexistente. Aqui ela **passa** (é
       lista válida) e quem recusa é `exigir_contagem_minima`, no total — porque uma página vazia
       no fim da paginação é legítima.
    """
    origem = resposta.url
    conteudo = resposta.conteudo
    if not conteudo.strip():
        msg = f"{origem}: HTTP {resposta.status} com corpo vazio — resposta não utilizável"
        raise RespostaDeErroComStatus200(msg)
    enxuto = conteudo.lstrip()
    if enxuto.startswith(PREFIXO_ERRO_OLINDA):
        amostra = enxuto[:200].decode(encoding, errors="replace")
        msg = (
            f"{origem}: HTTP {resposta.status} com corpo de ERRO do Olinda — JSON embrulhado em "
            f"comentário `/*…*/` (Anti-SPEC §10.1.5). Amostra: {amostra!r}"
        )
        raise RespostaDeErroComStatus200(msg)
    if enxuto.startswith(b"<"):
        amostra = enxuto[:160].decode(encoding, errors="replace")
        msg = (
            f"{origem}: HTTP {resposta.status} com corpo HTML/XML, não JSON — página de erro da "
            f"fonte (R1). Amostra: {amostra!r}"
        )
        raise RespostaDeErroComStatus200(msg)

    import json

    try:
        corpo = json.loads(ler_texto(conteudo, encoding))
    except json.JSONDecodeError as exc:
        msg = f"{origem}: HTTP {resposta.status} com corpo que não é JSON válido ({exc})"
        raise RespostaDeErroComStatus200(msg) from exc
    if not isinstance(corpo, dict):
        msg = f"{origem}: esperado objeto OData com 'value', veio {type(corpo).__name__}"
        raise RespostaDeErroComStatus200(msg)
    for chave in ("error", "erro", "codigo", "mensagem"):
        if chave in corpo:
            msg = (
                f"{origem}: HTTP {resposta.status} com corpo de ERRO (Anti-SPEC §10.1.5). "
                f"{chave}={corpo[chave]!r}"
            )
            raise RespostaDeErroComStatus200(msg)
    valores = corpo.get("value")
    if not isinstance(valores, list):
        msg = (
            f"{origem}: objeto OData sem lista em 'value' (chaves {sorted(corpo)}) — "
            f"a resposta de sucesso do Olinda é {{'@odata.context': …, 'value': [...]}}"
        )
        raise RespostaDeErroComStatus200(msg)
    return valores


def recusar_truncamento_silencioso(quantidade: int, *, top: int, origem: str) -> int:
    """CA-018: página com exatamente `LINHAS_SUSPEITAS_DE_TRUNCAMENTO` linhas é **recusada**.

    É a guarda que o §A2 da pesquisa pede literalmente: `$top=20000` devolve 20.000 linhas e
    **nenhum** `@odata.nextLink`, então o corte não tem sinal nenhum na resposta. O único jeito de
    perceber é afirmar que ninguém pede 20.000 e que ninguém aceita receber 20.000.

    Também recusa página **maior** que o `$top` pedido: se isso acontecer, o `$top` foi ignorado
    (como o `$count` e o `$apply` já são) e a paginação por `$skip` deixou de ser confiável.
    """
    if quantidade == LINHAS_SUSPEITAS_DE_TRUNCAMENTO:
        msg = (
            f"{origem}: {quantidade} linhas — exatamente o ponto de truncamento silencioso do "
            f"Olinda, que corta aí **sem** @odata.nextLink (CA-018, CB-002). Não concateno: "
            f"pagine com $skip e $top <= {PAGINA_MAXIMA}"
        )
        raise RespostaTruncada(msg)
    if quantidade > top:
        msg = (
            f"{origem}: {quantidade} linhas para $top={top} — o Olinda ignorou o $top (como já "
            f"ignora $count e $apply) e a paginação por $skip não é mais confiável"
        )
        raise RespostaTruncada(msg)
    return quantidade


# ─────────────────────────────────────────────────────────────────────────────
# Fatiamento, download e modo offline
# ─────────────────────────────────────────────────────────────────────────────


def fatiar_por_ano(inicio: date, fim: date) -> tuple[tuple[date, date], ...]:
    """`[inicio, fim]` em fatias de **ano-calendário**, contíguas e sem sobreposição.

    Ano-calendário em vez de "N dias" (o `fatiar_janela` do `common`) por um motivo prático: ano
    encerrado **não muda mais** nesta fonte, então a fatia de 2006 é byte-idêntica a cada rodada e
    `arquivar_bruto` fica idempotente para 20 das 23 fatias. Fatia de 366 dias atravessaria a
    virada do ano e perderia essa propriedade.
    """
    if fim < inicio:
        msg = f"janela invertida: inicio={inicio.isoformat()} > fim={fim.isoformat()}"
        raise ValueError(msg)
    fatias = []
    for ano in range(inicio.year, fim.year + 1):
        comeco = max(inicio, date(ano, 1, 1))
        termino = min(fim, date(ano, 12, 31))
        fatias.append((comeco, termino))
    return tuple(fatias)


def nome_bruto(
    entityset: str,
    *,
    indicador: str | None,
    inicio: date,
    fim: date,
    pagina: int,
) -> str:
    """Nome determinístico da página bruta: `<entityset>_<indicador>_<ano>_p<N>__<fim>.json`.

    Determinístico é o que torna o arquivamento idempotente e o que `--offline` usa para
    reencontrar a página. `indicador=None` (o EntitySet da Selic, que não filtra) vira `TODOS`.
    """
    alvo = slug_indicador(indicador) if indicador else "TODOS"
    return nome_arquivo_raw(
        f"{entityset}_{alvo}_{inicio.year}_p{pagina}", data_ref=fim, extensao="json"
    )


@dataclass(frozen=True, slots=True)
class PaginaPedida:
    """Uma página identificada **a partir da URL** — é o que o transporte offline precisa saber."""

    entityset: str
    indicador: str | None
    inicio: date
    fim: date
    pagina: int


_RE_ENTITYSET = re.compile(r"/odata/([A-Za-z0-9]+)\?")
_RE_INDICADOR = re.compile(r"Indicador(?:%20|\+| )eq(?:%20|\+| )'([^']+)'")
_RE_DATA_GE = re.compile(r"Data(?:%20|\+| )ge(?:%20|\+| )'(\d{4}-\d{2}-\d{2})'")
_RE_DATA_LE = re.compile(r"Data(?:%20|\+| )le(?:%20|\+| )'(\d{4}-\d{2}-\d{2})'")
_RE_TOP = re.compile(r"\$top=(\d+)")
_RE_SKIP = re.compile(r"\$skip=(\d+)")


def descrever_url(url: str) -> PaginaPedida:
    """URL de página → `PaginaPedida`. É o inverso de `montar_url`, usado pelo `--offline`.

    Lê `$skip`/`$top` em vez de guardar número de página em algum lugar: a URL **é** o estado, e
    assim o bruto arquivado continua reencontrável mesmo que alguém mude `PAGINA_MAXIMA` depois
    (a conta de página usa o `$top` que está na própria URL).
    """
    entityset = _RE_ENTITYSET.search(url)
    inicio = _RE_DATA_GE.search(url)
    fim = _RE_DATA_LE.search(url)
    top = _RE_TOP.search(url)
    skip = _RE_SKIP.search(url)
    if not (entityset and inicio and fim and top and skip):
        msg = (
            f"não consigo deduzir a página de {url!r} — esperava $filter com Data ge/le, "
            f"$top e $skip (é a URL que montar_url produz)"
        )
        raise ErroDeExtracao(msg)
    indicador = _RE_INDICADOR.search(url)
    passo = int(top.group(1))
    if passo < 1:
        msg = f"$top={passo} em {url!r}"
        raise ErroDeExtracao(msg)
    return PaginaPedida(
        entityset=entityset.group(1),
        indicador=unquote(indicador.group(1)) if indicador else None,
        inicio=date.fromisoformat(inicio.group(1)),
        fim=date.fromisoformat(fim.group(1)),
        pagina=int(skip.group(1)) // passo,
    )


def transporte_do_bruto_arquivado(
    destino: Path,
    *,
    agora: datetime | None = None,
) -> Transporte:
    """Transporte que serve `data/raw/focus/` em vez da rede — é o `--offline`.

    Reaproveita o pipeline inteiro (guarda de shape, normalização de campo, horizonte, dedup,
    schema) sobre o bruto arquivado. O `obtida_em` de cada página sai do **manifesto daquela
    página** (`collected_at_do_bruto`), nunca do relógio: é o que mantém D-b e faz duas rodadas
    `--offline` produzirem o mesmo Parquet. Página sem manifesto é **recusada** aqui, porque
    `arquivar_bruto` reescreveria o manifesto com o que este transporte declarasse.
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
        del metodo, params, dados, cabecalhos, timeout_s
        pedida = descrever_url(url)
        alvo = Path(destino) / nome_bruto(
            pedida.entityset,
            indicador=pedida.indicador,
            inicio=pedida.inicio,
            fim=pedida.fim,
            pagina=pedida.pagina,
        )
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
class PaginaBruta:
    """Uma requisição ao Olinda: o que foi pedido, o bruto arquivado e quantas linhas vieram."""

    entityset: str
    indicador: str | None
    inicio: date
    fim: date
    pagina: int
    linhas: int
    arquivo: str
    sha256: str
    idempotente: bool


def baixar_indicador(
    plano: PlanoDoEntitySet,
    pedido: PedidoDeIndicador,
    *,
    cliente: ClienteHTTP,
    destino: Path,
    inicio: date,
    fim: date,
    top: int = PAGINA_MAXIMA,
    sobrescrever_raw: bool = False,
) -> tuple[list[dict[str, Any]], tuple[PaginaBruta, ...]]:
    """Baixa um indicador em fatias de ano × páginas de `$skip`, arquivando cada página.

    O laço de paginação é a defesa de CA-018 e tem **uma** regra: *página cheia nunca é a última*.
    Enquanto a resposta vem com exatamente `top` linhas, pede-se a seguinte; só uma página curta
    (ou vazia) encerra a fatia. Como o Olinda não manda `@odata.nextLink` nem aceita `$count`,
    não existe outro sinal de fim — e tratar página cheia como fim é literalmente o bug que
    `$top=20000` provoca.
    """
    indicador = pedido.indicador if plano.filtra_indicador else None
    linhas: list[dict[str, Any]] = []
    paginas: list[PaginaBruta] = []

    for fatia_inicio, fatia_fim in fatiar_por_ano(inicio, fim):
        pagina = 0
        while True:
            url = montar_url(
                plano.entityset,
                indicador=indicador,
                inicio=fatia_inicio,
                fim=fatia_fim,
                pagina=pagina,
                top=top,
            )
            resposta = cliente.get(url)
            da_pagina = validar_corpo_odata(resposta, encoding=cliente.config.encoding)
            recusar_truncamento_silencioso(
                len(da_pagina),
                top=top,
                origem=f"{plano.entityset}/{indicador or 'TODOS'} {fatia_inicio.year} p{pagina}",
            )
            arquivado = arquivar_bruto(
                resposta.conteudo,
                destino=destino,
                nome=nome_bruto(
                    plano.entityset,
                    indicador=indicador,
                    inicio=fatia_inicio,
                    fim=fatia_fim,
                    pagina=pagina,
                ),
                origem=resposta.url,
                obtido_em=resposta.obtida_em,
                cabecalhos=dict(resposta.cabecalhos),
                sobrescrever_se_diferente=sobrescrever_raw,
            )
            linhas += da_pagina
            paginas.append(
                PaginaBruta(
                    entityset=plano.entityset,
                    indicador=indicador,
                    inicio=fatia_inicio,
                    fim=fatia_fim,
                    pagina=pagina,
                    linhas=len(da_pagina),
                    arquivo=arquivado.caminho.name,
                    sha256=arquivado.sha256,
                    idempotente=arquivado.idempotente,
                )
            )
            if len(da_pagina) < top:
                break
            pagina += 1

    return linhas, tuple(paginas)


# ─────────────────────────────────────────────────────────────────────────────
# Parse: linhas da fonte → as 8 colunas do schema
# ─────────────────────────────────────────────────────────────────────────────

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


def chave_da_linha(
    escopo: Escopo,
    linha: Mapping[str, Any],
    quando: date,
    *,
    origem: str = "",
) -> str:
    """Chave do `series_id` para esta linha — o horizonte, calculado **da data da pesquisa**.

    Nada aqui depende de informação futura: `DataReferencia` e `Data` vêm na mesma linha e o
    horizonte é a diferença entre as duas. É isso que mantém a propriedade de §1.5 (a mediana da
    semana X era conhecida na semana X) depois do parse.
    """
    if escopo is Escopo.REUNIAO_COPOM:
        return chave_de_reuniao(str(linha.get("reuniao")), origem=origem)
    if escopo is Escopo.INFLACAO_12M:
        return chave_de_suavizada(linha.get("suavizada"), origem=origem)

    referencia = linha.get("data_referencia")
    if referencia is None:
        msg = f"{origem}: linha sem DataReferencia: {dict(linha)!r}"
        raise RespostaDeErroComStatus200(msg)
    calculo = {
        Escopo.ANUAL: horizonte_anual,
        Escopo.MENSAL: horizonte_mensal,
        Escopo.TRIMESTRAL: horizonte_trimestral,
    }[escopo]
    horizonte = calculo(quando, str(referencia), origem=origem)
    chave = CHAVE_POR_HORIZONTE.get(horizonte)
    return chave if chave is not None else f"FORA:{horizonte}"


@dataclass(frozen=True, slots=True)
class Descartes:
    """Linhas que a fonte entregou e o pacote mínimo não usa — contadas, nunca silenciadas."""

    fora_do_horizonte: int = 0
    base_calculo_divergente: int = 0


def quadro_de_linhas(
    entrada: SeriesCatalogEntry,
    plano: PlanoDoEntitySet,
    linhas: Sequence[Mapping[str, Any]],
    *,
    collected_at: datetime,
) -> tuple[pd.DataFrame, Descartes]:
    """Linhas do Olinda → as 8 colunas de `ProcessedSeriesSchema`, nada mais.

    Três convenções valem aqui, e as duas primeiras são **específicas do Focus**:

    - **`date` = `Data` = o dia da pesquisa**, sem conversão para fim de período. D-a vale para
      série M/Q cuja observação *é* um período; a observação do Focus é um dia de pesquisa, e o
      período fica no `series_id` (`H0`/`H1`/`HM1`). `freq=D`, como o catálogo declara.
    - **`value` = `Mediana`**, não `Media`: é a estatística que a metodologia usa (§1.5) e a
      menos sensível a respondente extremo. `Media`, `DesvioPadrao`, `Minimo`, `Maximo` e
      `numeroRespondentes` **não** são gravados — `ProcessedSeriesSchema` é longo e `strict`, e o
      bruto fica em `data/raw/focus/` para quem precisar.
    - **`vintage` = a data (sem hora) de `collected_at`**, que vem do manifesto do bruto (D-b).

    `baseCalculo` é reconferido linha a linha mesmo tendo ido no `$filter`: é CA-017, e um filtro
    que a fonte resolvesse ignorar (como ela já ignora `$count` e `$apply`) dobraria a série em
    silêncio a partir de 2014.
    """
    escopo = plano.escopo
    unidades = {slug_indicador(p.indicador): p.unit for p in plano.pedidos}
    chaves_aceitas = {slug_indicador(p.indicador): p.chaves for p in plano.pedidos}
    vintage = pd.Timestamp(collected_at).tz_localize(None).normalize()

    registros: list[dict[str, Any]] = []
    fora = 0
    base_divergente = 0
    for i, crua in enumerate(linhas):
        origem = f"{entrada.series_id}[{i}]"
        linha = normalizar_linha(crua, origem=origem)

        base = linha.get("base_calculo")
        if base is not None and int(base) != BASE_CALCULO:
            base_divergente += 1
            continue

        quando = para_data(linha.get("data"), FormatoData.ISO, origem=f"{origem}.Data")
        if quando is None:
            msg = f"{origem}: Data vazia — o Olinda não faz isso: {dict(linha)!r}"
            raise RespostaDeErroComStatus200(msg)

        indicador = slug_indicador(str(linha.get("indicador") or ""))
        if indicador not in unidades:
            fora += 1
            continue

        chave = chave_da_linha(escopo, linha, quando, origem=origem)
        aceitas = chaves_aceitas[indicador]
        if chave.startswith("FORA:") or (aceitas is not None and chave not in aceitas):
            fora += 1
            continue

        registros.append(
            {
                "series_id": montar_series_id(escopo, indicador, chave),
                "date": quando,
                "value": para_float_ponto_decimal(linha.get("mediana"), origem=f"{origem}.Mediana"),
                "source": Fonte.BCB_OLINDA.value,
                "freq": Freq.DIARIA.value,
                "vintage": vintage,
                "unit": unidades[indicador].value,
                "collected_at": collected_at,
            }
        )

    quadro = pd.DataFrame(registros, columns=list(COLUNAS_PROCESSADAS))
    quadro["date"] = pd.to_datetime(quadro["date"])
    quadro["value"] = pd.to_numeric(quadro["value"], errors="raise")
    quadro = quadro.sort_values(["series_id", "date"]).reset_index(drop=True)
    return quadro, Descartes(fora_do_horizonte=fora, base_calculo_divergente=base_divergente)


def truncar_em(quadro: pd.DataFrame, fim: date) -> tuple[pd.DataFrame, int]:
    """Remove linha com `date > fim`. No Focus não deveria existir — e é por isso que é guarda.

    O `$filter` já limita `Data le fim`, então uma linha futura aqui significa que a fonte ignorou
    a cláusula (ela já ignora `$count` e `$apply` sem avisar). Sem esta guarda, o schema recusaria
    o quadro inteiro por `sem_data_futura` e a mensagem não diria por quê.
    """
    if quadro.empty:
        return quadro, 0
    limite = pd.Timestamp(fim)
    futuras = int((quadro["date"] > limite).sum())
    if not futuras:
        return quadro, 0
    _log.warning(
        "truncando %d linha(s) com date > %s: o $filter pediu 'Data le' e a fonte ignorou",
        futuras,
        fim,
    )
    return quadro.loc[quadro["date"] <= limite].reset_index(drop=True), futuras


def deduplicar(quadro: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Uma observação por (`series_id`, `date`). Fatias de ano não se sobrepõem — mas páginas sim.

    Duplicata com valores **divergentes** é erro de extração, não ruído: levanta em vez de
    escolher uma das duas em silêncio (seria a mesma série com dois números para o mesmo dia).
    """
    if quadro.empty:
        return quadro, 0
    chave = ["series_id", "date"]
    duplicadas = quadro.duplicated(subset=chave, keep=False)
    if not bool(duplicadas.any()):
        return quadro, 0
    conflitos = quadro.loc[duplicadas].groupby(chave)["value"].nunique(dropna=False)
    divergentes = conflitos[conflitos > 1]
    if len(divergentes):
        amostra = [f"{s} @ {d.date().isoformat()}" for s, d in divergentes.index[:5]]
        msg = (
            f"{quadro['series_id'].iloc[0]}: (series_id, date) duplicado com valor DIFERENTE em "
            f"{amostra} — não escolho por você; confira a paginação e o baseCalculo"
        )
        raise ErroDeExtracao(msg)
    limpo = quadro.drop_duplicates(subset=chave, keep="first").reset_index(drop=True)
    removidas = len(quadro) - len(limpo)
    _log.info("removidas %d linha(s) duplicada(s) por (series_id, date)", removidas)
    return limpo, removidas


def validar_continuidade(quadro: pd.DataFrame, *, gap_maximo: int = GAP_MAXIMO_FOCUS_DIAS) -> int:
    """Continuidade por `series_id` — sem preencher nada. Devolve o maior vão medido, em dias.

    Duas afirmações, as únicas que são verdade para **toda** série do Focus:

    - **nenhuma data em fim de semana.** A pesquisa é de dia útil; data de sábado seria parse de
      data errado (e `Data` vem `yyyy-MM-dd`, então o erro viria de troca de campo, não de
      `dd/mm` × `mm/dd`);
    - **nenhum vão maior que `gap_maximo` dias corridos.** Frouxo de propósito: há série que
      *estruturalmente* tem janela (`FOCUS_Q_PIB_TOTAL_HM1` só existe entre o fim do trimestre e a
      divulgação do PIB; cada `FOCUS_RCOPOM_SELIC_R<n>-<ano>` só existe até a reunião acontecer).
      O que a guarda pega é fatia de **ano** perdida, que abriria mais de 300 dias.

    Lacuna não é preenchida: `CLAUDE.md §4` proíbe interpolar para fechar série.
    """
    if quadro.empty:
        msg = "quadro vazio — nada a validar; a guarda de contagem mínima deveria ter pegado antes"
        raise ErroDeExtracao(msg)
    datas = pd.DatetimeIndex(quadro["date"])
    fim_de_semana = datas[datas.dayofweek >= DIAS_DE_FIM_DE_SEMANA]
    if len(fim_de_semana):
        amostra = [d.date().isoformat() for d in fim_de_semana[:5]]
        msg = (
            f"{quadro['series_id'].iloc[0]}: {len(fim_de_semana)} data(s) em fim de semana "
            f"({amostra}) — a pesquisa Focus é de dia útil; suspeite do campo lido como Data"
        )
        raise ErroDeExtracao(msg)

    maior = 0
    for series_id, grupo in quadro.groupby("series_id", sort=False):
        if len(grupo) < 2:  # noqa: PLR2004
            continue
        vaos = pd.DatetimeIndex(grupo["date"]).to_series().diff().dt.days.dropna()
        if vaos.empty:
            continue
        pico = int(vaos.max())
        maior = max(maior, pico)
        if pico > gap_maximo:
            onde = grupo["date"].iloc[1:][(vaos > gap_maximo).to_numpy()]
            amostra = [d.date().isoformat() for d in onde[:3]]
            msg = (
                f"{series_id}: vão de {pico} dias corridos no índice (antes de {amostra}) — "
                f"máximo tolerado {gap_maximo}; parece fatia de ano perdida, não janela natural"
            )
            raise ErroDeExtracao(msg)
    return maior


def exigir_series_esperadas(quadro: pd.DataFrame, plano: PlanoDoEntitySet) -> tuple[str, ...]:
    """Toda série declarada em `PLANO` apareceu? Devolve os `series_id` gravados, ordenados.

    Vale como guarda independente da contagem mínima: o total podia vir inteiro e um horizonte
    inteiro faltar (um `H1` que a fonte parasse de publicar, um rótulo de `Indicador` renomeado).
    """
    presentes = set(quadro["series_id"])
    faltando = []
    for pedido in plano.pedidos:
        if pedido.chaves is None:
            continue
        for chave in sorted(pedido.chaves):
            esperado = montar_series_id(plano.escopo, pedido.indicador, chave)
            if esperado not in presentes:
                faltando.append(esperado)
    if faltando:
        msg = (
            f"{plano.entityset}: série declarada em PLANO sem nenhuma linha no output: "
            f"{faltando}. O rótulo de Indicador mudou, ou o horizonte deixou de ser publicado"
        )
        raise ErroDeExtracao(msg)
    return tuple(sorted(presentes))


def conferir_canarios(quadro: pd.DataFrame) -> tuple[tuple[str, str, float], ...]:
    """Confere todo canário de `CANARIOS` que caia dentro do extraído (CA-017/018/019).

    Fora da janela o canário é ignorado (não é falha); dentro dela, divergir é — e a mensagem
    distingue as duas causas possíveis: a fonte revisou, ou o parse mudou de escala.
    """
    conferidos: list[tuple[str, str, float]] = []
    for series_id, (quando, esperado) in CANARIOS.items():
        do_id = quadro.loc[quadro["series_id"] == series_id]
        if do_id.empty:
            continue
        alvo = pd.Timestamp(quando)
        if alvo < do_id["date"].min() or alvo > do_id["date"].max():
            continue
        encontrado = do_id.loc[do_id["date"] == alvo, "value"]
        if encontrado.empty:
            msg = f"{series_id}: valor-canário de {quando} ausente na série extraída"
            raise ErroDeExtracao(msg)
        obtido = float(encontrado.iloc[0])
        if abs(obtido - esperado) > TOLERANCIA_CANARIO:
            msg = (
                f"{series_id}: valor-canário {quando} = {obtido!r}, esperado {esperado!r} "
                f"(tolerância {TOLERANCIA_CANARIO}). A fonte revisou ou o parse mudou de escala"
            )
            raise ErroDeExtracao(msg)
        conferidos.append((series_id, quando, obtido))
    return tuple(conferidos)


# ─────────────────────────────────────────────────────────────────────────────
# Extração de um EntitySet e do pacote
# ─────────────────────────────────────────────────────────────────────────────


def collected_at_das_paginas(destino: Path, paginas: Sequence[PaginaBruta]) -> datetime | None:
    """`collected_at` do EntitySet = o `obtido_em` mais recente entre os manifestos das páginas."""
    momentos = [
        m
        for m in (obtido_em_arquivado(Path(destino) / p.arquivo) for p in paginas)
        if m is not None
    ]
    return max(momentos) if momentos else None


def exigir_collected_at(
    momento: datetime | None,
    *,
    entrada: SeriesCatalogEntry,
    paginas: Sequence[PaginaBruta],
) -> datetime:
    """`collected_at` do manifesto, ou **recusa** — nunca o relógio da rodada (D-b, CA-121)."""
    if momento is not None:
        return momento
    arquivos = [p.arquivo for p in paginas]
    msg = (
        f"{entrada.series_id}: nenhuma das {len(paginas)} página(s) tem manifesto legível "
        f"({arquivos[:3]}) — sem ele `collected_at`/`vintage` sairiam do relógio desta rodada e o "
        f"Parquet deixaria de ser reproduzível (D-b, CA-121). Rode uma vez **online** (o "
        f"manifesto nasce aí) ou passe `collected_at=` explicitamente."
    )
    raise ManifestoAusente(msg)


@dataclass(frozen=True, slots=True)
class ResultadoExtracao:
    """Evidência de um EntitySet extraído — é o que vai para a matriz de validação."""

    series_id: str
    entityset: str
    escopo: str
    series_gravadas: tuple[str, ...]
    linhas: int
    linhas_brutas: int
    data_min: date
    data_max: date
    pct_nulos: float
    descartes: Descartes
    duplicatas_removidas: int
    linhas_futuras_truncadas: int
    maior_vao_dias: int
    canarios: tuple[tuple[str, str, float], ...]
    paginas: tuple[PaginaBruta, ...]
    parquet: Path | None

    @property
    def cobre_1t2006(self) -> bool:
        """O EntitySet alcança o 1º trimestre de 2006 (`data_min <= 2006-03-31`)?"""
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
    top: int = PAGINA_MAXIMA,
) -> ResultadoExtracao:
    """Baixa → arquiva → normaliza → horizonte → trunca → dedup → valida → grava o Parquet.

    `gravar=False` roda tudo menos a escrita (é como o teste confere o parse sem tocar `data/`).
    """
    fim = fim or date.today()
    plano = plano_de(entrada)
    config = config_para(entrada, inicio=inicio, fim=fim)
    destino_raw = caminho_destino_raw(config, raiz=raiz)
    if offline and transporte is None:
        transporte = transporte_do_bruto_arquivado(destino_raw, agora=collected_at)
    cliente = ClienteHTTP(config, transporte=transporte)

    brutas: list[dict[str, Any]] = []
    paginas: list[PaginaBruta] = []
    for pedido in plano.pedidos:
        linhas, do_pedido = baixar_indicador(
            plano,
            pedido,
            cliente=cliente,
            destino=destino_raw,
            inicio=inicio,
            fim=fim,
            top=top,
            sobrescrever_raw=sobrescrever_raw,
        )
        brutas += linhas
        paginas += do_pedido

    exigir_contagem_minima(
        len(brutas),
        minimo=config.contagem_minima_esperada,
        origem=f"{config.nome} ({len(paginas)} página(s) de {inicio} a {fim})",
    )

    agora = exigir_collected_at(
        collected_at or collected_at_das_paginas(destino_raw, paginas),
        entrada=entrada,
        paginas=paginas,
    )
    quadro, descartes = quadro_de_linhas(entrada, plano, brutas, collected_at=agora)
    quadro, truncadas = truncar_em(quadro, fim)
    quadro, duplicadas = deduplicar(quadro)
    maior_vao = validar_continuidade(quadro)
    gravadas = exigir_series_esperadas(quadro, plano)
    canarios = conferir_canarios(quadro)

    destino = None
    if gravar:
        destino = gravar_processado_parquet(
            quadro, nome=f"{FONTE_SLUG}/{entrada.series_id}.parquet", raiz=raiz
        )

    return ResultadoExtracao(
        series_id=entrada.series_id,
        entityset=plano.entityset,
        escopo=plano.escopo.value,
        series_gravadas=gravadas,
        linhas=len(quadro),
        linhas_brutas=len(brutas),
        data_min=quadro["date"].min().date(),
        data_max=quadro["date"].max().date(),
        pct_nulos=round(float(quadro["value"].isna().mean()) * 100, 4),
        descartes=descartes,
        duplicatas_removidas=duplicadas,
        linhas_futuras_truncadas=truncadas,
        maior_vao_dias=maior_vao,
        canarios=canarios,
        paginas=tuple(paginas),
        parquet=destino,
    )


def extrair(
    series_ids: Sequence[str] | None = None,
    *,
    inicio: date = INICIO_PADRAO,
    fim: date | None = None,
    offline: bool = False,
    raiz: Path | None = None,
    gravar: bool = True,
    sobrescrever_raw: bool = False,
    ao_falhar: Callable[[SeriesCatalogEntry, Exception], None] | None = None,
) -> tuple[ResultadoExtracao, ...]:
    """Extrai os EntitySets pedidos (default: os 5 do pacote mínimo).

    `ao_falhar` recebe a exceção e deixa o laço seguir — é o `--continuar` da CLI. Sem ele, a
    primeira falha interrompe tudo: numa fonte que trunca sem avisar, parar é o default certo.
    """
    resultados: list[ResultadoExtracao] = []
    for entrada in catalogo_focus(series_ids):
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
        prog="python -m apps.pipeline.extract.bcb_focus",
        description=(
            "Extrai as expectativas Focus (Olinda/OData v4) para data/raw/focus/ e "
            "data/processed/focus/."
        ),
    )
    p.add_argument(
        "--series",
        nargs="+",
        metavar="SERIES_ID",
        help="series_id do catálogo (ex.: FOCUS_ANUAIS). Default: os 5 EntitySets do pacote.",
    )
    p.add_argument("--inicio", type=date.fromisoformat, default=INICIO_PADRAO, metavar="AAAA-MM-DD")
    p.add_argument("--fim", type=date.fromisoformat, default=None, metavar="AAAA-MM-DD")
    p.add_argument(
        "--offline",
        action="store_true",
        help="relê o bruto já arquivado em data/raw/focus/ em vez de chamar a fonte.",
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
        help="não aborta no primeiro EntitySet que falhar; reporta no fim.",
    )
    p.add_argument(
        "--detalhar-series",
        action="store_true",
        help="imprime uma linha por series_id gravado, com linhas e min/max.",
    )
    return p


def _linha(r: ResultadoExtracao) -> str:
    return (
        f"{r.series_id:<20} {r.escopo:<6} {len(r.series_gravadas):>4} serie(s) "
        f"{r.linhas:>7} linhas  {r.data_min}..{r.data_max}  "
        f"nulos={r.pct_nulos:>6.2f}%  paginas={len(r.paginas):>3}  "
        f"fora_horizonte={r.descartes.fora_do_horizonte:>7}  "
        f"bc_divergente={r.descartes.base_calculo_divergente:>6}  "
        f"dup={r.duplicatas_removidas}  fut={r.linhas_futuras_truncadas}  "
        f"vao_max={r.maior_vao_dias:>3}d  1T2006={'sim' if r.cobre_1t2006 else 'NAO'}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. Devolve 0 em sucesso, 1 se algum EntitySet falhou."""
    args = _parser().parse_args(argv)
    falhas: list[tuple[str, Exception]] = []

    def _registrar(entrada: SeriesCatalogEntry, exc: Exception) -> None:
        _log.error("%s: %s", entrada.series_id, exc)
        falhas.append((entrada.series_id, exc))

    resultados = extrair(
        args.series,
        inicio=args.inicio,
        fim=args.fim,
        offline=args.offline,
        gravar=args.gravar,
        sobrescrever_raw=args.sobrescrever_raw,
        ao_falhar=_registrar if args.continuar else None,
    )

    print(
        f"\n{len(resultados)} EntitySet(s) do Focus extraido(s) de {args.inicio} a "
        f"{args.fim or 'hoje'} (baseCalculo={BASE_CALCULO}, value=Mediana):\n"
    )
    for r in resultados:
        print(_linha(r))

    if args.detalhar_series:
        print("\nseries gravadas:")
        for r in resultados:
            for series_id in r.series_gravadas:
                print(f"  {r.series_id:<20} {series_id}")

    print("\ncanarios conferidos:")
    for r in resultados:
        for series_id, quando, valor in r.canarios:
            print(f"  {series_id:<30} {quando} = {valor}")

    print("\nbrutos arquivados (por EntitySet):")
    for r in resultados:
        novos = sum(1 for p in r.paginas if not p.idempotente)
        print(
            f"  {r.series_id:<20} {len(r.paginas):>3} pagina(s), {novos} nova(s); "
            f"primeira={r.paginas[0].arquivo if r.paginas else '-'} "
            f"sha256={r.paginas[0].sha256[:16] if r.paginas else '-'}"
        )

    if falhas:
        print(f"\n{len(falhas)} FALHA(S):")
        for serie, exc in falhas:
            print(f"  ! {serie}: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
