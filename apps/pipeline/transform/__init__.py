"""Camada de transformação: lê `data/processed/` e produz série **derivada**.

Regra da camada: nada aqui toca a rede nem escreve em `data/raw/`. Entrada é Parquet já validado
por `ProcessedSeriesSchema`; saída é Parquet no mesmo contrato, com `source = DERIVADO` quando a
série não existe em nenhuma fonte (`SP500_BRL`, `ACWI_BRL`) — nunca uma coluna nova numa série
existente, nunca substituição silenciosa da original (Anti-SPEC §10.4.28 vale para moeda como
vale para frequência).

| Módulo | O que faz | Feature |
|---|---|---|
| `cambio` | série em USD × PTAX do mesmo dia útil → série em BRL (CA-047) | F-007 (D-g) |

**O que ainda não está aqui e vai chegar em F-017:** acumulação geométrica de CDI/Selic
(CA-014/015/016), retorno trimestral por ativo a partir de nível de índice (razão, nunca
subtração — §10.2.13) e a agregação para a grade trimestral. Nada disso existe hoje: nenhum
extrator da Onda 1 agrega nada, e trimestral primário é proibido (Anti-SPEC §10.4.28). O
alinhamento de calendário que esses cálculos exigem é **F-014**, que consome
`data/processed/calendario/dias_uteis_anbima.parquet` (F-008).
"""

from __future__ import annotations

from apps.pipeline.transform.cambio import (
    PTAX_SUBPASTA,
    PTAX_VENDA,
    ResultadoConversao,
    caminho_ptax,
    carregar_ptax,
    converter_para_brl,
)

__all__ = [
    "PTAX_SUBPASTA",
    "PTAX_VENDA",
    "ResultadoConversao",
    "caminho_ptax",
    "carregar_ptax",
    "converter_para_brl",
]
