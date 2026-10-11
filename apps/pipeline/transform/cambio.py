"""Conversão de série internacional para BRL pela PTAX do mesmo dia útil (CA-047).

Esta é a primeira peça da camada de **transformação**: lê `data/processed/` e produz série
derivada, sem tocar a rede e sem tocar `data/raw/`. Nasceu dentro de
`apps/pipeline/extract/yahoo.py` (F-007, cujo Feature Contract só abria os dois extratores) e
desceu para cá na consolidação da Onda 1 (D-g): `msci.py` importava `yahoo.py` só por estas
funções, e extrator importando extrator é acoplamento que não se justifica.

Quem usa: `extract/yahoo.py` (`SP500_BRL`) e `extract/msci.py` (`ACWI_BRL`). Quem vai usar:
**F-017** (retornos trimestrais), que mora nesta mesma camada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from apps.pipeline.common import (
    ErroDeExtracao,
    SerieInconsistente,
    caminho_processed,
    obter_logger,
)
from packages.shared.schemas import Fonte, Freq

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from pathlib import Path

_log = obter_logger(__name__)


#: `series_id` da PTAX usada na conversão: **SGS 1 = dólar venda** (a mesma do valor-canário
#: CA-043), extraída por F-003. `10813` (compra) fica como alternativa explícita.
PTAX_VENDA = "BCB_SGS_1"
PTAX_SUBPASTA = "sgs"


def caminho_ptax(series_id: str = PTAX_VENDA, *, raiz: Path | None = None) -> Path:
    """`data/processed/sgs/BCB_SGS_1.parquet` — a dependência de F-003 para a conversão a BRL."""
    return caminho_processed(f"{PTAX_SUBPASTA}/{series_id}.parquet", raiz=raiz)


def carregar_ptax(series_id: str = PTAX_VENDA, *, raiz: Path | None = None) -> pd.DataFrame:
    """Lê a PTAX já processada por F-003. Levanta se o parquet não existe.

    **Dependência declarada:** a série em BRL de F-007 não é extração, é derivação que precisa de
    `data/processed/sgs/<PTAX>.parquet`. Sem ele, o certo é não produzir a série em BRL (e
    registrar), nunca estimar o câmbio (Anti-SPEC §10.1.1).
    """
    alvo = caminho_ptax(series_id, raiz=raiz)
    if not alvo.is_file():
        msg = (
            f"PTAX não encontrada em {alvo}: a conversão a BRL depende de F-003 "
            f"(`uv run python -m apps.pipeline.extract.bcb_sgs`). Sem PTAX a série em BRL não é "
            f"produzida — nenhum câmbio é estimado"
        )
        raise ErroDeExtracao(msg)
    ptax = pd.read_parquet(alvo)
    faltando = {"date", "value"} - set(ptax.columns)
    if faltando:
        msg = f"{alvo}: PTAX sem as colunas {sorted(faltando)}"
        raise ErroDeExtracao(msg)
    return ptax.loc[ptax["value"].notna(), ["date", "value"]].rename(columns={"value": "ptax"})


@dataclass(frozen=True, slots=True)
class ResultadoConversao:
    """O que a conversão a BRL produziu — evidência de dados da CA-047."""

    quadro: pd.DataFrame
    series_id: str
    linhas: int
    #: Dias do histórico em USD que **não** têm PTAX do mesmo dia útil e por isso saíram.
    dias_sem_ptax: int
    is_total_return: bool


def converter_para_brl(
    serie_usd: pd.DataFrame,
    *,
    series_id_destino: str,
    ptax: pd.DataFrame,
    is_total_return: bool | None,
    unit: str = "index",
    origem: str = "",
) -> ResultadoConversao:
    """Série em USD × PTAX do **mesmo dia útil** → série em BRL (CA-047).

    Três regras, cada uma amarrada a um item da Anti-SPEC:

    1. **Mesmo dia útil, sem `ffill`.** O join é exato por `date`; dia sem PTAX publicada
       (feriado brasileiro em que a bolsa americana abriu, e vice-versa) **sai da série** em vez
       de herdar o câmbio de ontem — interpolar câmbio é inventar dado (§10.1.1) e preencher com
       `0` é pior (§10.1.4). Quantos dias saíram vai no relatório, não em silêncio.
    2. **`is_total_return` é obrigatório.** `None` levanta: comparar price return internacional
       com total return doméstico sem a flag é exatamente o que §10.2.12 proíbe, e o valor fica
       no catálogo da série derivada, não no cabeçalho de um DataFrame de 8 colunas.
    3. **Multiplicação, nunca subtração.** `nivel_brl = nivel_usd * ptax` — a série resultante é
       um nível de índice em reais, e retorno sai dela por **razão** (§10.2.13).

    `collected_at` e `vintage` são **herdados da série em USD** (que os tirou do manifesto do
    bruto, D-b): a derivada não tem coleta própria, e datar pelo relógio da derivação faria a
    mesma entrada produzir safras diferentes a cada reprocessamento.
    """
    if is_total_return is None:
        msg = (
            f"{origem or series_id_destino}: converter_para_brl exige is_total_return explícito. "
            f"Série internacional sem a flag não pode entrar no mesmo heatmap de IMA-B/IFIX "
            f"(Anti-SPEC §10.2.12)"
        )
        raise SerieInconsistente(msg)

    base = serie_usd.loc[serie_usd["value"].notna()].copy()
    juntado = base.merge(ptax, on="date", how="inner", validate="one_to_one")
    dias_sem_ptax = len(base) - len(juntado)
    if juntado.empty:
        msg = (
            f"{origem or series_id_destino}: nenhum dia em comum entre a série em USD "
            f"({len(base)} pontos) e a PTAX — janelas disjuntas, nada a converter"
        )
        raise SerieInconsistente(msg)

    quadro = pd.DataFrame(
        {
            "series_id": series_id_destino,
            "date": juntado["date"],
            "value": juntado["value"].to_numpy() * juntado["ptax"].to_numpy(),
            "source": Fonte.DERIVADO.value,
            "freq": Freq.DIARIA.value,
            # D-b: `vintage` = a data (sem hora) do `collected_at` da série em USD, que por sua
            # vez veio do manifesto do bruto. A derivada herda a safra da série de origem.
            "vintage": juntado["collected_at"].dt.normalize(),
            "unit": unit,
            "collected_at": juntado["collected_at"],
        }
    ).reset_index(drop=True)
    _log.info(
        "%s: %d linhas em BRL, %d dia(s) sem PTAX do mesmo dia util, is_total_return=%s",
        series_id_destino,
        len(quadro),
        dias_sem_ptax,
        is_total_return,
    )
    return ResultadoConversao(
        quadro=quadro,
        series_id=series_id_destino,
        linhas=len(quadro),
        dias_sem_ptax=dias_sem_ptax,
        is_total_return=is_total_return,
    )
