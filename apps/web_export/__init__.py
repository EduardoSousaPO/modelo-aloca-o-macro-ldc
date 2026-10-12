"""`apps/web_export/` — a ponte **única** do dataset congelado para o portal LDC Analytics.

Feature **F-W001**, classe **C**: altera nada no canônico e **lê** o canônico já congelado, mas o
que ela publica é número de regime indo para uma tela — então vale a disciplina da classe C
(contrato primeiro, gate lido do disco, determinismo por hash, teste por critério).

O comando é um só:

```bash
python -m apps.web_export exportar --tag comite-2026-10-14
python -m apps.web_export exportar --tag dev-2026-10-11 --destino data/web
```

Três coisas que este pacote **é**, e que o resto do projeto depende que continuem verdadeiras:

- **o lugar do gate.** `publicavel: false` no `MANIFEST.json` recusa a exportação; o
  `especificacao_congelada` do ADR-001 em disco viaja em toda view; `n < 5` sai com o valor **e**
  com `conclusao_suprimida: true`. O front não tem gate — ele não pode ter: o bundle já desceu.
- **a única fronteira de contrato entre os dois repositórios.** `packages/shared/schemas/
  web_views.py` é a fonte; `schema.d.ts`, gerado no mesmo comando, é o que o portal importa.
- **determinística e sem rede.** Duas exportações da mesma tag produzem o mesmo `sha256` em todos
  os arquivos. Nada aqui lê o relógio nem abre socket.

O que este pacote **não** é: não recalcula metodologia (P4 do PRD — média, mediana, Mahalanobis e
Ledoit-Wolf já estão no Parquet), não converte unidade (declara a nativa de cada campo), não escreve
em `data/canonical/` e não cria tag git. Publicar é ato humano.

| Módulo | Papel |
|---|---|
| `exportar.py` | gate, `verify`, `meta.json`, orçamento, `current.json`, CLI |
| `views.py` | as 6 views: ler Parquet, selecionar colunas do contrato, normalizar forma |
| `tipos_ts.py` | `pydantic → JSON Schema → schema.d.ts` |
"""

from __future__ import annotations

from apps.web_export.exportar import (
    FEATURE,
    ErroDeExportacao,
    ResultadoExportacao,
    ler_gate,
    main,
    versao_build,
)

__all__ = [
    "FEATURE",
    "ErroDeExportacao",
    "ResultadoExportacao",
    "ler_gate",
    "main",
    "versao_build",
]

# A função `exportar` NÃO é reexportada aqui de propósito: ela se chama como o módulo
# (`apps.web_export.exportar`), e reexportá-la sombrearia o submódulo — `from apps.web_export
# import exportar` devolveria a função, e `exportar.ler_manifesto` quebraria. Quem precisa da
# função a importa de `apps.web_export.exportar`, que é onde ela mora.
