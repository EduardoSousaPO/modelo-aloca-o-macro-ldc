"""Calendário de dias úteis da ANBIMA (F-008, SPEC RF-018, CA-051/CA-052).

Base de **toda** acumulação e alinhamento do projeto: o trimestre fecha no **último dia útil** de
mar/jun/set/dez (ADR-006 §(b).2, SPEC §2) e o forward-fill de F-014 é contado em dias úteis. Quem
consome: F-014 (alinhamento temporal), F-017 (retornos trimestrais) e qualquer agregação que
precise saber se uma data existe no mercado.

Fonte (ANBIMA, `docs/research/fontes-de-dados.md §B7`): a lista oficial de feriados nacionais
bancários, publicada em `https://www.anbima.com.br/feriados/`. **Dois formatos, um só dado:**

- `arqs/feriados_nacionais.xls` — a planilha encadeada 2001→2099 citada na SPEC. Medida em
  2026-10-10: HTTP 200, 111.104 bytes, e os magic bytes são `D0 CF 11 E0` = **XLS/BIFF legado
  de verdade** (OLE2), não o XLSX disfarçado do S3. `xlrd` está **dispensado** do projeto
  (`DECISIONS_LOG §2`) e nenhum leitor instalado abre BIFF, então esta planilha **não** é o
  caminho de dado. Ela continua sendo baixada e arquivada como **fonte de registro** (hash em
  `data/raw/anbima-feriados/*.meta.json`), e `arquivar_fonte_de_registro` avisa em WARNING se um
  dia ela virar XLSX — momento de reabrir a decisão.
- `fer_nacionais/<ano>.asp` — **a mesma lista**, ano a ano, em HTML `<table>`, linkada pela própria
  página índice da ANBIMA. É daqui que o calendário é construído, com o `latin-1` que
  `ENCODING_POR_FONTE` já declara para `ANBIMA_WEB`. A tabela é extraída
  da `<table class="interna">` com `re` + `html.unescape` (a página abre com prólogo XML, que faz
  `lxml` recusar a string — por isso não é `read_html`). Nenhuma dependência nova, nenhum feriado
  construído por regra ("Lei 662/49 + móveis") — **dado da fonte**, só em outro formato.

Validação independente da rota HTML (rodada de 2026-10-10): o conjunto de dias úteis derivado
destas páginas é **idêntico, dia a dia**, ao conjunto de observações da série **SGS 12 (CDI)** em
`data/processed/sgs/BCB_SGS_12.parquet` para **todos os 20 anos de 2006 a 2025** — 5.022 dias úteis,
zero data só no calendário, zero data só no CDI. O mesmo vale contra o IMA-B do S3 (F-002).
2006 fecha em **249 dias úteis**, o número que CA-051 exige.

As quatro armadilhas desta fonte, e onde cada uma é tratada:

1. **A planilha é BIFF.** `exigir_formato(..., HTML)` recusa o corpo da planilha antes de qualquer
   parse, e o teste negativo usa o cabeçalho real do arquivo. Nada de `read_excel` adivinhando.
2. **A data vem como `1/1/06`** — dia/mês sem zero e ano com 2 dígitos. `FormatoData.DD_MM_AA`
   declara o formato (R12: `01/02` é 1º/fev aqui e 2/jan na PTAX) e o ano parseado é **conferido
   contra o ano da página**: página de 2006 com data de 2025 levanta.
3. **A própria página traz o dia da semana** (`domingo`, `terça-feira`). O parser **confere** o
   rótulo contra `date.weekday()`: se dia e mês fossem trocados, a conferência quebraria. É a
   guarda que torna o parse auto-verificável, sem fórmula reimplementada no teste.
4. **31/12 é dia útil aqui.** A nota 4 da página da ANBIMA diz que a listagem "não inclui os
   feriados municipais, eleições e o último dia do ano" — e a série do CDI confirma: 2025-12-31
   tem observação. Logo o último dia útil de 4T2025 é **2025-12-31**, não 30/12. Há teste.

Cobertura entregue: **2001-01-01 → 2030-12-31**. A fonte começa em **2001** — não há feriado de
2000 para extrair e nenhum é inventado, então data fora da cobertura levanta
`ForaDaCoberturaDoCalendario` em vez de devolver palpite. A janela do projeto (2006Q1→2026Q3,
`macro_quarterly`) está inteiramente dentro da cobertura, com 2005 de folga para o retorno de
1T2006.

Uso:

```bash
uv run python -m apps.pipeline.extract.calendario_anbima              # ao vivo, 2001..2030
uv run python -m apps.pipeline.extract.calendario_anbima --offline    # relê data/raw, sem rede
uv run python -m apps.pipeline.extract.calendario_anbima --anos 2006 2026
```
"""

from __future__ import annotations

import argparse
import html as _html
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING

import pandas as pd

from apps.pipeline.common import (
    ENCODING_POR_FONTE,
    SUFIXO_MANIFESTO,
    ClienteHTTP,
    ErroDeExtracao,
    FormatoData,
    FormatoDetectado,
    arquivar_bruto,
    caminho_destino_raw,
    caminho_processed,
    configurar_logging,
    detectar_formato,
    exigir_formato,
    garantir_diretorio,
    ler_texto,
    nome_arquivo_raw,
    normalizar_rotulo,
    obter_logger,
    para_data,
    sha256_de,
)
from packages.shared.schemas import CalendarioDiasUteisSchema, ExtractorConfig, Fonte, load_catalog

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

    from apps.pipeline.common import Transporte

_log = obter_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes da fonte
# ─────────────────────────────────────────────────────────────────────────────

#: `series_id` do catálogo (`packages/shared/schemas/series_catalog_data.py`). Nunca derivado do
#: conteúdo da página — a convenção da Onda 1 é `series_id` vindo do catálogo.
SERIES_ID = "ANBIMA_FERIADOS_NACIONAIS"

#: A planilha da SPEC: **fonte de registro**, não caminho de dado (é BIFF; ver docstring).
URL_XLS_REGISTRO = "https://www.anbima.com.br/feriados/arqs/feriados_nacionais.xls"
#: A página índice, que lista os links por ano e é a origem da rota usada.
URL_INDICE = "https://www.anbima.com.br/feriados/feriados.asp"
#: A mesma lista, ano a ano, em HTML — o caminho de dado efetivo.
URL_PAGINA_ANO = "https://www.anbima.com.br/feriados/fer_nacionais/{ano}.asp"

#: Primeiro e último ano publicados pela fonte (medido em 2026-10-10: 2001.asp..2099.asp).
ANO_INICIO_FONTE = 2001
ANO_FIM_FONTE = 2099

#: Cobertura que o projeto materializa. 2001 porque é onde a fonte começa; 2030 porque é folga
#: suficiente sobre a janela de `macro_quarterly` (2006Q1→2026Q3) sem baixar 99 páginas.
ANO_INICIO = 2001
ANO_FIM = 2030

#: Piso anti-truncamento por ano (R2). Medido: 12 feriados/ano de 2001 a 2023 e 13 de 2024 em
#: diante (20 de novembro, Consciência Negra, virou feriado nacional em 2024 — Lei 14.759/23).
#: Página com menos que isto é página truncada ou layout trocado, e tem de levantar.
FERIADOS_MINIMOS_POR_ANO = 12
#: Teto de sanidade: nenhum ano tem 25 feriados nacionais. Protege contra a tabela errada.
FERIADOS_MAXIMOS_POR_ANO = 25

DESTINO_RAW = "data/raw/anbima-feriados"
#: `data/processed/calendario/dias_uteis_anbima.parquet`.
NOME_PROCESSADO = "calendario/dias_uteis_anbima.parquet"
EXTENSAO_RAW = "html"
EXTENSAO_RAW_REGISTRO = "xls"

#: `data_ref` do arquivo de registro: a cobertura declarada pela própria fonte ("até 2099"). É
#: constante, então o download de amanhã cai no mesmo nome e `arquivar_bruto` fica idempotente;
#: se a ANBIMA republicar a planilha com conteúdo diferente, bate em `ConteudoDivergente` (R8)
#: em vez de apagar o retrato anterior.
DATA_REF_REGISTRO = date(ANO_FIM_FONTE, 12, 31)

#: Rótulos de dia da semana da página, **normalizados** (`normalizar_rotulo`), por `weekday()`.
#: Servem de conferência do parse de data, não de insumo: o dia da semana é recalculado.
DIAS_DA_SEMANA: dict[int, str] = {
    0: normalizar_rotulo("segunda-feira"),
    1: normalizar_rotulo("terça-feira"),
    2: normalizar_rotulo("quarta-feira"),
    3: normalizar_rotulo("quinta-feira"),
    4: normalizar_rotulo("sexta-feira"),
    5: normalizar_rotulo("sábado"),
    6: normalizar_rotulo("domingo"),
}

#: Cabeçalho esperado da tabela de feriados, normalizado.
CABECALHO_ESPERADO: tuple[str, ...] = (
    normalizar_rotulo("Data"),
    normalizar_rotulo("Dia da Semana"),
    normalizar_rotulo("Feriado"),
)

#: Último dia **civil** de cada trimestre. O último dia **útil** sai daqui andando para trás.
FIM_CIVIL_DO_TRIMESTRE: dict[int, tuple[int, int]] = {
    1: (3, 31),
    2: (6, 30),
    3: (9, 30),
    4: (12, 31),
}

_TABELA = re.compile(r'<table[^>]*class="interna".*?</table>', re.IGNORECASE | re.DOTALL)
_LINHA = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELULA = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")


class CalendarioInconsistente(ErroDeExtracao):
    """A página abriu, mas o conteúdo não é a tabela de feriados do ano pedido."""


class ForaDaCoberturaDoCalendario(ErroDeExtracao):
    """Pediram uma data fora de `[cobertura_inicio, cobertura_fim]` — não se adivinha feriado."""


# ─────────────────────────────────────────────────────────────────────────────
# Contrato do DataFrame
# ─────────────────────────────────────────────────────────────────────────────

# `CalendarioDiasUteisSchema` vive em `packages/shared/schemas/calendario.py` desde a
# consolidação da Onda 1 (D-f): é contrato de dado, e contrato de dado mora no pacote de schemas,
# onde F-014/F-017 o importam sem depender deste extrator. Aqui ele é só importado (acima) e
# continua acessível como `calendario_anbima.CalendarioDiasUteisSchema`, que é o que os testes e a
# API pública deste módulo usam.

# ─────────────────────────────────────────────────────────────────────────────
# Configuração do extrator
# ─────────────────────────────────────────────────────────────────────────────


def config_do_ano(ano: int) -> ExtractorConfig:
    """`ExtractorConfig` da página de um ano — o contrato é a configuração."""
    if not ANO_INICIO_FONTE <= ano <= ANO_FIM_FONTE:
        msg = f"ano {ano} fora da publicação da ANBIMA ({ANO_INICIO_FONTE}..{ANO_FIM_FONTE})"
        raise ErroDeExtracao(msg)
    return ExtractorConfig(
        nome=f"anbima_feriados_{ano}",
        fonte=Fonte.ANBIMA_WEB,
        series_ids=(SERIES_ID,),
        base_url=URL_PAGINA_ANO.format(ano=ano),
        formato="html",
        encoding=ENCODING_POR_FONTE[Fonte.ANBIMA_WEB.value],
        requer_user_agent_browser=True,
        janela_maxima_dias=None,
        contagem_minima_esperada=FERIADOS_MINIMOS_POR_ANO,
        destino_raw=DESTINO_RAW,
        timeout_s=60.0,
    )


def config_do_registro() -> ExtractorConfig:
    """`ExtractorConfig` da planilha de registro (BIFF) — baixada, arquivada, nunca parseada."""
    return ExtractorConfig(
        nome="anbima_feriados_planilha_registro",
        fonte=Fonte.ANBIMA_WEB,
        series_ids=(SERIES_ID,),
        base_url=URL_XLS_REGISTRO,
        formato="xlsx",  # é o que a fonte promete; os magic bytes dizem BIFF (R11)
        encoding=ENCODING_POR_FONTE[Fonte.ANBIMA_WEB.value],
        requer_user_agent_browser=True,
        destino_raw=DESTINO_RAW,
        timeout_s=120.0,
    )


def _conferir_catalogo() -> None:
    """Falha na importação se o catálogo e este módulo divergirem (padrão de F-002, CA-033)."""
    catalogo = {e.series_id: e for e in load_catalog()}
    entrada = catalogo.get(SERIES_ID)
    if entrada is None:
        msg = f"{SERIES_ID} não está em packages/shared/schemas/series_catalog_data.py"
        raise ErroDeExtracao(msg)
    if entrada.fonte_url != URL_XLS_REGISTRO:
        msg = f"{SERIES_ID}: catálogo diz fonte_url={entrada.fonte_url!r}, módulo usa "
        raise ErroDeExtracao(msg + repr(URL_XLS_REGISTRO))


_conferir_catalogo()


# ─────────────────────────────────────────────────────────────────────────────
# Parse da página de um ano
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, order=True)
class Feriado:
    """Um feriado nacional, como a ANBIMA publica."""

    data: date
    nome: str


def _celula(bruto: str) -> str:
    """Conteúdo textual de uma célula: tags fora, entidade resolvida, espaço colapsado."""
    return _ESPACOS.sub(" ", _html.unescape(_TAG.sub("", bruto))).strip()


def parse_feriados_do_ano(conteudo: bytes, *, ano: int, origem: str) -> tuple[Feriado, ...]:
    """Bytes de `fer_nacionais/<ano>.asp` → os feriados daquele ano, conferidos.

    Não grava nada. Levanta `CalendarioInconsistente` em vez de devolver lista curta, com data de
    outro ano, com dia da semana que não fecha, com data repetida ou sem nome de feriado — e
    `FormatoInesperado` se o corpo não for HTML (é o que recusa a planilha BIFF e o 404).
    """
    exigir_formato(conteudo, FormatoDetectado.HTML, origem=origem)
    texto = ler_texto(conteudo, config_do_ano(ano).encoding)

    tabela = _TABELA.search(texto)
    if tabela is None:
        msg = (
            f"{origem}: nenhuma <table class='interna'> na página — corpo de erro, "
            f"redesenho do site ou ano inexistente ({len(conteudo)} bytes)"
        )
        raise CalendarioInconsistente(msg)

    linhas = [
        celulas
        for bruto in _LINHA.findall(tabela.group(0))
        if len(celulas := [_celula(c) for c in _CELULA.findall(bruto)]) == 3
    ]
    if not linhas:
        msg = f"{origem}: tabela encontrada mas sem nenhuma linha de 3 colunas"
        raise CalendarioInconsistente(msg)

    cabecalho = tuple(normalizar_rotulo(c) for c in linhas[0])
    if cabecalho != CABECALHO_ESPERADO:
        msg = (
            f"{origem}: cabeçalho inesperado {list(cabecalho)}; esperado {list(CABECALHO_ESPERADO)}"
        )
        raise CalendarioInconsistente(msg)

    feriados = [_feriado_da_linha(linha, ano=ano, origem=origem) for linha in linhas[1:]]
    _validar_feriados(feriados, ano=ano, origem=origem)
    return tuple(feriados)


def _feriado_da_linha(linha: Sequence[str], *, ano: int, origem: str) -> Feriado:
    """Uma linha `['1/1/06', 'domingo', 'Confraternização Universal']` → `Feriado`."""
    bruto_data, bruto_dia, bruto_nome = linha
    quando = para_data(bruto_data, FormatoData.DD_MM_AA, origem=origem)
    if quando is None:
        msg = f"{origem}: linha de feriado sem data ({linha!r})"
        raise CalendarioInconsistente(msg)
    if quando.year != ano:
        msg = (
            f"{origem}: página do ano {ano} traz data {quando.isoformat()} "
            f"(bruto {bruto_data!r}) — ano errado ou formato de data trocado"
        )
        raise CalendarioInconsistente(msg)
    esperado = DIAS_DA_SEMANA[quando.weekday()]
    visto = normalizar_rotulo(bruto_dia)
    if visto != esperado:
        msg = (
            f"{origem}: {quando.isoformat()} ({bruto_data!r}) é {esperado} no calendário civil, "
            f"mas a página diz {visto!r} — dia e mês trocados ou linha corrompida"
        )
        raise CalendarioInconsistente(msg)
    nome = bruto_nome.strip()
    if not nome:
        msg = f"{origem}: {quando.isoformat()} sem nome de feriado"
        raise CalendarioInconsistente(msg)
    return Feriado(data=quando, nome=nome)


def _validar_feriados(feriados: Sequence[Feriado], *, ano: int, origem: str) -> None:
    """Guardas de contagem, duplicidade e ordem da lista de um ano."""
    if len(feriados) < FERIADOS_MINIMOS_POR_ANO:
        msg = (
            f"{origem}: {len(feriados)} feriado(s) em {ano}, mínimo esperado "
            f"{FERIADOS_MINIMOS_POR_ANO} — página truncada"
        )
        raise CalendarioInconsistente(msg)
    if len(feriados) > FERIADOS_MAXIMOS_POR_ANO:
        msg = f"{origem}: {len(feriados)} feriado(s) em {ano} — tabela errada?"
        raise CalendarioInconsistente(msg)
    datas = [f.data for f in feriados]
    repetidas = sorted({d.isoformat() for d in datas if datas.count(d) > 1})
    if repetidas:
        msg = f"{origem}: data repetida na tabela de {ano}: {repetidas}"
        raise CalendarioInconsistente(msg)
    if datas != sorted(datas):
        msg = f"{origem}: feriados de {ano} fora de ordem crescente"
        raise CalendarioInconsistente(msg)


# ─────────────────────────────────────────────────────────────────────────────
# O calendário
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Calendario:
    """Dias úteis do mercado brasileiro, pelos feriados nacionais da ANBIMA.

    É a API que F-014 (alinhamento) e F-017 (retornos trimestrais) consomem. Toda consulta é
    fechada no intervalo `[cobertura_inicio, cobertura_fim]`: data fora dele levanta
    `ForaDaCoberturaDoCalendario` em vez de supor que não há feriado.
    """

    feriados: Mapping[date, str]
    cobertura_inicio: date
    cobertura_fim: date

    # ------------------------------------------------------------- construção

    @classmethod
    def de_feriados(
        cls,
        feriados: Iterable[Feriado],
        *,
        ano_inicio: int = ANO_INICIO,
        ano_fim: int = ANO_FIM,
    ) -> Calendario:
        """Monta o calendário a partir dos feriados extraídos, cobrindo anos civis inteiros."""
        inicio, fim = date(ano_inicio, 1, 1), date(ano_fim, 12, 31)
        mapa = {f.data: f.nome for f in feriados if inicio <= f.data <= fim}
        anos_cobertos = {d.year for d in mapa}
        faltando = sorted(set(range(ano_inicio, ano_fim + 1)) - anos_cobertos)
        if faltando:
            msg = f"calendário sem nenhum feriado nos anos {faltando} — cobertura incompleta"
            raise CalendarioInconsistente(msg)
        return cls(feriados=dict(sorted(mapa.items())), cobertura_inicio=inicio, cobertura_fim=fim)

    @classmethod
    def do_quadro(cls, quadro: pd.DataFrame) -> Calendario:
        """Reconstrói o calendário do DataFrame validado (ou do parquet já lido)."""
        validado = CalendarioDiasUteisSchema.validate(quadro, lazy=True)
        com_feriado = validado.loc[validado["feriado"].notna()]
        return cls(
            feriados={
                linha.date(): str(nome)
                for linha, nome in zip(com_feriado["data"], com_feriado["feriado"], strict=True)
            },
            cobertura_inicio=validado["data"].min().date(),
            cobertura_fim=validado["data"].max().date(),
        )

    @classmethod
    def do_parquet(cls, *, raiz: Path | None = None) -> Calendario:
        """Lê `data/processed/calendario/dias_uteis_anbima.parquet`.

        Levanta se o arquivo não existe: o calendário é dado extraído, não default embutido.
        """
        alvo = caminho_processed(NOME_PROCESSADO, raiz=raiz)
        if not alvo.is_file():
            msg = (
                f"calendário ausente em {alvo}; rode "
                f"`uv run python -m apps.pipeline.extract.calendario_anbima`"
            )
            raise ErroDeExtracao(msg)
        return cls.do_quadro(pd.read_parquet(alvo))

    # ----------------------------------------------------------------- grade

    def para_quadro(self) -> pd.DataFrame:
        """Grade civil `[cobertura_inicio, cobertura_fim]` no contrato do schema."""
        datas = pd.date_range(self.cobertura_inicio, self.cobertura_fim, freq="D")
        nomes = [self.feriados.get(d.date()) for d in datas]
        quadro = pd.DataFrame(
            {
                "data": datas,
                "dia_util": [
                    d.weekday() < 5 and nome is None for d, nome in zip(datas, nomes, strict=True)
                ],
                "feriado": pd.array(nomes, dtype="string"),
                "fonte": Fonte.ANBIMA_WEB.value,
            }
        )
        return CalendarioDiasUteisSchema.validate(quadro, lazy=True)

    # ------------------------------------------------------------- consultas

    def _exigir_cobertura(self, quando: date) -> None:
        if not self.cobertura_inicio <= quando <= self.cobertura_fim:
            msg = (
                f"{quando.isoformat()} está fora da cobertura do calendário "
                f"({self.cobertura_inicio.isoformat()}..{self.cobertura_fim.isoformat()}); "
                f"a ANBIMA publica a partir de {ANO_INICIO_FONTE} — estenda ANO_FIM e reextraia, "
                f"nunca presuma ausência de feriado"
            )
            raise ForaDaCoberturaDoCalendario(msg)

    def e_feriado(self, quando: date) -> bool:
        """`True` se a data é feriado nacional (independente de ser fim de semana)."""
        self._exigir_cobertura(quando)
        return quando in self.feriados

    def nome_do_feriado(self, quando: date) -> str | None:
        """Nome publicado pela ANBIMA, ou `None` se não é feriado."""
        self._exigir_cobertura(quando)
        return self.feriados.get(quando)

    def e_dia_util(self, quando: date) -> bool:
        """Dia útil = de segunda a sexta **e** não feriado nacional."""
        self._exigir_cobertura(quando)
        return quando.weekday() < 5 and quando not in self.feriados

    def ajustar_para_tras(self, quando: date) -> date:
        """A própria data se é dia útil; senão, o dia útil **anterior** (CA-052, CB-007)."""
        self._exigir_cobertura(quando)
        atual = quando
        while not self.e_dia_util(atual):
            atual -= timedelta(days=1)
            self._exigir_cobertura(atual)
        return atual

    def ajustar_para_frente(self, quando: date) -> date:
        """A própria data se é dia útil; senão, o **próximo** dia útil."""
        self._exigir_cobertura(quando)
        atual = quando
        while not self.e_dia_util(atual):
            atual += timedelta(days=1)
            self._exigir_cobertura(atual)
        return atual

    def proximo_dia_util(self, quando: date, n: int = 1) -> date:
        """O `n`-ésimo dia útil **estritamente depois** de `quando` (`n >= 1`).

        Para "esta data, ou a próxima útil", use `ajustar_para_frente` — a ambiguidade de um
        `n=0` que significasse as duas coisas é exatamente o tipo de erro que o alinhamento de
        F-014 não pode ter.
        """
        return self._andar(quando, n, passo=1, nome="proximo_dia_util")

    def dia_util_anterior(self, quando: date, n: int = 1) -> date:
        """O `n`-ésimo dia útil **estritamente antes** de `quando` (`n >= 1`)."""
        return self._andar(quando, n, passo=-1, nome="dia_util_anterior")

    def _andar(self, quando: date, n: int, *, passo: int, nome: str) -> date:
        if n < 1:
            msg = f"{nome}: n={n} inválido; use n >= 1 (ou ajustar_para_frente/ajustar_para_tras)"
            raise ValueError(msg)
        self._exigir_cobertura(quando)
        atual = quando
        restantes = n
        while restantes:
            atual += timedelta(days=passo)
            self._exigir_cobertura(atual)
            if self.e_dia_util(atual):
                restantes -= 1
        return atual

    def dias_uteis(self, inicio: date, fim: date) -> tuple[date, ...]:
        """Os dias úteis do intervalo **fechado** `[inicio, fim]`, em ordem crescente."""
        if fim < inicio:
            msg = f"intervalo invertido: {inicio.isoformat()} > {fim.isoformat()}"
            raise ValueError(msg)
        self._exigir_cobertura(inicio)
        self._exigir_cobertura(fim)
        total = (fim - inicio).days + 1
        return tuple(d for i in range(total) if self.e_dia_util(d := inicio + timedelta(days=i)))

    def dias_uteis_entre(self, inicio: date, fim: date) -> int:
        """Quantos dias úteis há no intervalo **fechado** `[inicio, fim]` — pontas inclusive.

        Fechado nas duas pontas porque é o que CA-051 pede ("os dias úteis de 2006" =
        `dias_uteis_entre(2006-01-01, 2006-12-31)` = 249) e o que a contagem de observações de
        uma série diária significa. Para "quantos dias úteis andei", use a diferença de posições.
        """
        return len(self.dias_uteis(inicio, fim))

    def ultimo_dia_util(self, ano: int, mes: int) -> date:
        """Último dia útil do mês — a API nomeada em SPEC RF-018."""
        if not 1 <= mes <= 12:
            msg = f"mês {mes} inválido; use 1..12"
            raise ValueError(msg)
        proximo = date(ano + (mes == 12), 1 if mes == 12 else mes + 1, 1)
        return self.ajustar_para_tras(proximo - timedelta(days=1))

    def primeiro_dia_util(self, ano: int, mes: int) -> date:
        """Primeiro dia útil do mês (ex.: 1º dia útil de 2006 = 2006-01-02)."""
        return self.ajustar_para_frente(date(ano, mes, 1))

    def ultimo_dia_util_do_trimestre(self, ano: int, tri: int) -> date:
        """Último dia útil de 1T..4T — o fim de período de ADR-006 §(b).2 e de CA-052/CA-065.

        Anda **para trás** a partir do último dia civil do trimestre: 2006-09-30 é sábado → 29/09;
        2024-03-31 é domingo e 29/03 é Sexta-feira Santa → 28/03. 31/12 **é** dia útil na lista da
        ANBIMA, então 4T2025 fecha em 2025-12-31.
        """
        if tri not in FIM_CIVIL_DO_TRIMESTRE:
            msg = f"trimestre {tri} inválido; use 1, 2, 3 ou 4"
            raise ValueError(msg)
        mes, dia = FIM_CIVIL_DO_TRIMESTRE[tri]
        return self.ajustar_para_tras(date(ano, mes, dia))


@lru_cache(maxsize=1)
def calendario_padrao() -> Calendario:
    """O calendário do parquet, carregado uma vez por processo. Atalho para F-014/F-017."""
    return Calendario.do_parquet()


def e_dia_util(quando: date) -> bool:
    """Atalho de módulo para `calendario_padrao().e_dia_util`."""
    return calendario_padrao().e_dia_util(quando)


def e_feriado(quando: date) -> bool:
    """Atalho de módulo para `calendario_padrao().e_feriado`."""
    return calendario_padrao().e_feriado(quando)


def proximo_dia_util(quando: date, n: int = 1) -> date:
    """Atalho de módulo para `calendario_padrao().proximo_dia_util`."""
    return calendario_padrao().proximo_dia_util(quando, n)


def dia_util_anterior(quando: date, n: int = 1) -> date:
    """Atalho de módulo para `calendario_padrao().dia_util_anterior`."""
    return calendario_padrao().dia_util_anterior(quando, n)


def dias_uteis(inicio: date, fim: date) -> tuple[date, ...]:
    """Atalho de módulo para `calendario_padrao().dias_uteis`."""
    return calendario_padrao().dias_uteis(inicio, fim)


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Atalho de módulo para `calendario_padrao().dias_uteis_entre`."""
    return calendario_padrao().dias_uteis_entre(inicio, fim)


def ultimo_dia_util(ano: int, mes: int) -> date:
    """Atalho de módulo para `calendario_padrao().ultimo_dia_util`."""
    return calendario_padrao().ultimo_dia_util(ano, mes)


def ultimo_dia_util_do_trimestre(ano: int, tri: int) -> date:
    """Atalho de módulo para `calendario_padrao().ultimo_dia_util_do_trimestre`."""
    return calendario_padrao().ultimo_dia_util_do_trimestre(ano, tri)


# ─────────────────────────────────────────────────────────────────────────────
# Escrita
# ─────────────────────────────────────────────────────────────────────────────


def gravar_calendario_parquet(quadro: pd.DataFrame, *, raiz: Path | None = None) -> Path:
    """Valida com `CalendarioDiasUteisSchema` e **só então** grava (mesma ordem de CA-003)."""
    validado = CalendarioDiasUteisSchema.validate(quadro, lazy=True)
    destino = caminho_processed(NOME_PROCESSADO, raiz=raiz)
    garantir_diretorio(destino.parent)
    validado.to_parquet(destino, index=False)
    _log.info("gravado %s (%d linhas)", destino.name, len(validado))
    return destino


def hash_do_conteudo(quadro: pd.DataFrame) -> str:
    """`sha256` do conteúdo do calendário — a prova de reprodutibilidade (RF-048, CA-121).

    Serializa as colunas em CSV ordenado por data, em UTF-8: duas execuções independentes sobre a
    mesma fonte têm de dar o mesmo dígito.
    """
    ordenado = quadro.sort_values("data").reset_index(drop=True)
    linhas = [
        f"{d.date().isoformat()},{int(u)},{'' if pd.isna(f) else f}"
        for d, u, f in zip(ordenado["data"], ordenado["dia_util"], ordenado["feriado"], strict=True)
    ]
    return sha256_de("\n".join(linhas).encode("utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Extração
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResultadoAno:
    """Evidência de dados de um ano."""

    ano: int
    feriados: tuple[Feriado, ...]
    sha256_raw: str
    bytes_raw: int
    caminho_raw: Path | None
    raw_idempotente: bool

    def resumo(self) -> str:
        """Uma linha para o log e para a CLI, **só em ASCII** (o stdout do Windows e cp1252)."""
        raw = "idempotente" if self.raw_idempotente else "novo"
        return (
            f"{self.ano}: {len(self.feriados)} feriados, "
            f"{self.feriados[0].data.isoformat()} a {self.feriados[-1].data.isoformat()}, "
            f"raw {raw} sha256={self.sha256_raw[:12]}..."
        )


@dataclass(frozen=True, slots=True)
class ResultadoCalendario:
    """Evidência da rodada inteira — o que vai para a matriz de validação."""

    anos: tuple[ResultadoAno, ...]
    linhas: int
    data_inicio: date
    data_fim: date
    dias_uteis: int
    feriados: int
    sha256_conteudo: str
    caminho_processed: Path | None
    sha256_registro: str | None

    def resumo(self) -> str:
        """Uma linha, **só em ASCII**."""
        registro = (
            f", xls de registro sha256={self.sha256_registro[:12]}..."
            if (self.sha256_registro)
            else ""
        )
        return (
            f"calendario ANBIMA: {self.linhas} dias civis "
            f"{self.data_inicio.isoformat()} a {self.data_fim.isoformat()}, "
            f"{self.dias_uteis} dias uteis, {self.feriados} feriados, "
            f"conteudo sha256={self.sha256_conteudo[:12]}...{registro}"
        )


def _data_ref_do_ano(feriados: Sequence[Feriado]) -> date:
    """`data_ref` do bruto = **última data do conteúdo** (convenção da Onda 1, F-002 §2.2)."""
    return feriados[-1].data


def extrair_ano(
    ano: int,
    *,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
) -> ResultadoAno:
    """Baixa a página do ano, parseia e arquiva o bruto (idempotente, com manifesto)."""
    config = config_do_ano(ano)
    resposta = ClienteHTTP(config, transporte=transporte).get()
    feriados = parse_feriados_do_ano(resposta.conteudo, ano=ano, origem=resposta.url)
    arquivado = arquivar_bruto(
        resposta.conteudo,
        destino=caminho_destino_raw(config, raiz=raiz),
        nome=nome_arquivo_raw(str(ano), data_ref=_data_ref_do_ano(feriados), extensao=EXTENSAO_RAW),
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
    )
    resultado = ResultadoAno(
        ano=ano,
        feriados=feriados,
        sha256_raw=arquivado.sha256,
        bytes_raw=arquivado.bytes_gravados,
        caminho_raw=arquivado.caminho,
        raw_idempotente=arquivado.idempotente,
    )
    _log.info("%s", resultado.resumo())
    return resultado


def _bruto_arquivado(ano: int, *, raiz: Path | None) -> Path:
    """A página de um ano já arquivada em `data/raw/anbima-feriados/` (modo `--offline`)."""
    pasta = caminho_destino_raw(config_do_ano(ano), raiz=raiz)
    # Filtro do manifesto por disciplina (D-c): aqui a extensão é `.html` e o `.meta.json` não
    # casa com o glob, mas em fonte JSON casa e ordenaria antes do dado.
    candidatos = sorted(
        (
            c
            for c in pasta.glob(f"{ano}__*.{EXTENSAO_RAW}")
            if not c.name.endswith(SUFIXO_MANIFESTO)
        ),
        reverse=True,
    )
    if not candidatos:
        msg = f"modo offline: nenhum bruto de {ano} em {pasta}"
        raise ErroDeExtracao(msg)
    return candidatos[0]


def extrair_ano_offline(ano: int, *, raiz: Path | None = None) -> ResultadoAno:
    """Reparseia um ano do bruto já arquivado — sem rede, sem reescrever `data/raw/`."""
    alvo = _bruto_arquivado(ano, raiz=raiz)
    conteudo = alvo.read_bytes()
    feriados = parse_feriados_do_ano(conteudo, ano=ano, origem=str(alvo))
    resultado = ResultadoAno(
        ano=ano,
        feriados=feriados,
        sha256_raw=sha256_de(conteudo),
        bytes_raw=len(conteudo),
        caminho_raw=alvo,
        raw_idempotente=True,
    )
    _log.info("[offline] %s", resultado.resumo())
    return resultado


def arquivar_fonte_de_registro(
    *,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
) -> str:
    """Baixa e arquiva `feriados_nacionais.xls` como **registro**, sem parsear.

    O arquivo é XLS/BIFF legado (`D0 CF 11 E0`) e nenhum leitor do projeto abre BIFF
    (`DECISIONS_LOG §2`: `xlrd` dispensado). Guardá-lo com hash é o que permite auditar, mais
    tarde, que a rota HTML descreve a mesma lista. Se um dia vier XLSX, o WARNING aqui é o gatilho
    para reabrir a decisão; se vier HTML (página de erro), levanta.
    """
    config = config_do_registro()
    resposta = ClienteHTTP(config, transporte=transporte).get()
    formato = detectar_formato(resposta.conteudo)
    if formato is FormatoDetectado.XLSX:
        _log.warning(
            "%s agora e XLSX (PK), nao BIFF: reabra a decisao de usar a rota HTML", resposta.url
        )
    elif formato is not FormatoDetectado.XLS_BIFF:
        exigir_formato(
            resposta.conteudo,
            (FormatoDetectado.XLS_BIFF, FormatoDetectado.XLSX),
            origem=resposta.url,
        )
    arquivado = arquivar_bruto(
        resposta.conteudo,
        destino=caminho_destino_raw(config, raiz=raiz),
        nome=nome_arquivo_raw(
            "feriados_nacionais", data_ref=DATA_REF_REGISTRO, extensao=EXTENSAO_RAW_REGISTRO
        ),
        origem=resposta.url,
        obtido_em=resposta.obtida_em,
        cabecalhos=dict(resposta.cabecalhos),
    )
    _log.info(
        "fonte de registro arquivada: %s (%s, %d bytes, sha256=%s...)",
        arquivado.caminho.name,
        formato.value,
        arquivado.bytes_gravados,
        arquivado.sha256[:12],
    )
    return arquivado.sha256


def extrair(
    anos: Sequence[int] | None = None,
    *,
    offline: bool = False,
    transporte: Transporte | None = None,
    raiz: Path | None = None,
    gravar: bool = True,
    com_registro: bool = True,
) -> ResultadoCalendario:
    """Roda os anos pedidos (default: `ANO_INICIO..ANO_FIM`) e grava o calendário."""
    alvos = tuple(anos) if anos else tuple(range(ANO_INICIO, ANO_FIM + 1))
    resultados = tuple(
        extrair_ano_offline(ano, raiz=raiz)
        if offline
        else extrair_ano(ano, transporte=transporte, raiz=raiz)
        for ano in alvos
    )
    calendario = Calendario.de_feriados(
        [f for r in resultados for f in r.feriados],
        ano_inicio=min(alvos),
        ano_fim=max(alvos),
    )
    quadro = calendario.para_quadro()
    destino = gravar_calendario_parquet(quadro, raiz=raiz) if gravar else None
    sha_registro = (
        arquivar_fonte_de_registro(transporte=transporte, raiz=raiz)
        if com_registro and not offline
        else None
    )
    resultado = ResultadoCalendario(
        anos=resultados,
        linhas=len(quadro),
        data_inicio=calendario.cobertura_inicio,
        data_fim=calendario.cobertura_fim,
        dias_uteis=int(quadro["dia_util"].sum()),
        feriados=len(calendario.feriados),
        sha256_conteudo=hash_do_conteudo(quadro),
        caminho_processed=destino,
        sha256_registro=sha_registro,
    )
    _log.info("%s", resultado.resumo())
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.pipeline.extract.calendario_anbima",
        description="Calendario de dias uteis da ANBIMA (F-008, SPEC RF-018).",
    )
    parser.add_argument(
        "--anos",
        nargs="+",
        type=int,
        metavar="ANO",
        help=f"subconjunto de anos (default: {ANO_INICIO}..{ANO_FIM})",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="reparseia o bruto ja em data/raw/anbima-feriados/, sem tocar a rede",
    )
    parser.add_argument(
        "--sem-gravar",
        action="store_true",
        help="nao escreve em data/processed/ (so confere e imprime a evidencia)",
    )
    parser.add_argument(
        "--sem-registro",
        action="store_true",
        help="nao baixa o feriados_nacionais.xls de registro",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Ponto de entrada da CLI. `0` em sucesso, `1` em qualquer `ErroDeExtracao`."""
    args = _parser().parse_args(list(argv) if argv is not None else None)
    configurar_logging()
    try:
        resultado = extrair(
            args.anos,
            offline=args.offline,
            gravar=not args.sem_gravar,
            com_registro=not args.sem_registro,
        )
    except ErroDeExtracao as exc:
        print(f"FALHOU: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    for ano in resultado.anos:
        print(ano.resumo())
    print(resultado.resumo())
    return 0


def _main_cli() -> None:  # pragma: no cover - invocado só por `python -m`
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    _main_cli()
