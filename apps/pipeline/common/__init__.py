"""Infra de extração (F-001) — a base compartilhada por **todos** os extratores.

Entrada única para o que não deve ser reimplementado por fonte. Cada peça existe por causa de um
risco medido em `docs/research/fontes-de-dados.md §RISCOS DE EXTRAÇÃO`:

- **`http`** — `ClienteHTTP` (UA de browser, timeout, retry com backoff, cache condicional),
  `validar_corpo_json_array`, `exigir_contagem_minima`, `fatiar_janela`.
  *R1, R2, R4 · CA-003, CA-045*
- **`parsing`** — `para_float_ptbr`, `para_float_ponto_decimal`, `para_data`, `detectar_formato`,
  `ler_texto`, `normalizar_rotulo`. *R10..R14 · CA-022, CA-030, CA-035*
- **`io_layers`** — `raiz_repo`, `caminho_raw/processed/canonical`, `nome_arquivo_raw`,
  `arquivar_bruto`, `sha256_de`, `gravar_processado_parquet`. *R8, R21 · CA-121*
- **`logging_setup`** — `configurar_logging`, `obter_logger` (namespace `pipeline.*`). *R17*
- **`errors`** — hierarquia de exceções, uma por modo de falha catalogado. *Anti-SPEC §10.1.5*

Receita mínima de um extrator:

```python
from apps.pipeline.common import ClienteHTTP, arquivar_bruto, caminho_destino_raw, para_float_ptbr

cliente = ClienteHTTP(CONFIG)                 # CONFIG: ExtractorConfig da fonte
resposta = cliente.get(params={...})          # UA, timeout e retry já aplicados
arquivar_bruto(                               # bruto imutável + sha256 + manifesto
    resposta.conteudo,
    destino=caminho_destino_raw(CONFIG),
    nome=nome_arquivo_raw(CONFIG.series_ids[0], data_ref=hoje, extensao="json"),
    origem=resposta.url,
    obtido_em=resposta.obtida_em,
    cabecalhos=dict(resposta.cabecalhos),
)
```

Context Pack para quem vai escrever extrator: `docs/wiki/context/F-001.md`.
"""

from __future__ import annotations

from apps.pipeline.common.errors import (
    ConteudoDivergente,
    DataNaoReconhecida,
    ErroDeExtracao,
    FalhaDeTransporte,
    FonteIndisponivel,
    FormatoInesperado,
    NumeroNaoReconhecido,
    RespostaDeErroComStatus200,
    RespostaTruncada,
    UserAgentObrigatorio,
)
from apps.pipeline.common.http import (
    CABECALHOS_DE_BROWSER,
    DO_CONTRATO,
    JANELA_SGS_DIARIA_DIAS,
    JANELA_SGS_RECOMENDADA_DIAS,
    USER_AGENT_BROWSER,
    ClienteHTTP,
    RespostaBruta,
    Transporte,
    cabecalhos_de_browser,
    exigir_contagem_minima,
    fatiar_janela,
    transporte_requests,
    validar_corpo_json_array,
)
from apps.pipeline.common.io_layers import (
    MARCADORES_DA_RAIZ,
    SUFIXO_MANIFESTO,
    Camada,
    ResultadoArquivamento,
    arquivar_bruto,
    caminho_camada,
    caminho_canonical,
    caminho_destino_raw,
    caminho_processed,
    caminho_raw,
    garantir_diretorio,
    gravar_processado_parquet,
    ler_manifesto,
    nome_arquivo_raw,
    raiz_repo,
    sha256_de,
    validadores_condicionais,
)
from apps.pipeline.common.logging_setup import configurar_logging, obter_logger
from apps.pipeline.common.parsing import (
    AUSENCIAS,
    ENCODING_POR_FONTE,
    LATIN_1,
    UTF_8,
    FormatoData,
    FormatoDetectado,
    detectar_formato,
    exigir_formato,
    ler_texto,
    ler_texto_de_arquivo,
    normalizar_rotulo,
    para_data,
    para_float_ponto_decimal,
    para_float_ptbr,
)

__all__ = [
    "AUSENCIAS",
    "CABECALHOS_DE_BROWSER",
    "DO_CONTRATO",
    "ENCODING_POR_FONTE",
    "JANELA_SGS_DIARIA_DIAS",
    "JANELA_SGS_RECOMENDADA_DIAS",
    "LATIN_1",
    "MARCADORES_DA_RAIZ",
    "SUFIXO_MANIFESTO",
    "USER_AGENT_BROWSER",
    "UTF_8",
    "Camada",
    "ClienteHTTP",
    "ConteudoDivergente",
    "DataNaoReconhecida",
    "ErroDeExtracao",
    "FalhaDeTransporte",
    "FonteIndisponivel",
    "FormatoData",
    "FormatoDetectado",
    "FormatoInesperado",
    "NumeroNaoReconhecido",
    "RespostaBruta",
    "RespostaDeErroComStatus200",
    "RespostaTruncada",
    "ResultadoArquivamento",
    "Transporte",
    "UserAgentObrigatorio",
    "arquivar_bruto",
    "cabecalhos_de_browser",
    "caminho_camada",
    "caminho_canonical",
    "caminho_destino_raw",
    "caminho_processed",
    "caminho_raw",
    "configurar_logging",
    "detectar_formato",
    "exigir_contagem_minima",
    "exigir_formato",
    "fatiar_janela",
    "garantir_diretorio",
    "gravar_processado_parquet",
    "ler_manifesto",
    "ler_texto",
    "ler_texto_de_arquivo",
    "nome_arquivo_raw",
    "normalizar_rotulo",
    "obter_logger",
    "para_data",
    "para_float_ponto_decimal",
    "para_float_ptbr",
    "raiz_repo",
    "sha256_de",
    "transporte_requests",
    "validadores_condicionais",
    "validar_corpo_json_array",
]
