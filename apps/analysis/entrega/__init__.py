"""F-031 — montagem do pacote de entrega ao Comitê de Alocação (classe **D**).

**Este pacote PREPARA. Ele não publica.** O envio ao Alexandre/Comitê é ato humano e só acontece
depois dos **8 passos** de `AGENTS.md §14`, com o passo 2 (ADR-001 aceito) resolvido. Enquanto o
ADR-001 estiver em `Proposta`, `especificacao_congelada = False` (CA-090) e todo artefato montado
aqui nasce com o selo `ESPECIFICAÇÃO NÃO CONGELADA — não publicável`, **lido do disco**, nunca
digitado.

| Módulo | O que faz |
|---|---|
| `montar_pacote` | monta `data/canonical/entrega/pacote_comite_2026-10-14/` + `.zip`
  determinístico e roda o **smoke test** do pacote (`infra-ops.md §1.5`) |

Três regras estruturais desta camada:

1. **Nada é calculado aqui.** O módulo copia artefato do canônico, converte formato (Parquet → CSV
   pt-BR, Parquet → aba de XLSX) e hasheia. Nenhuma média, nenhum regime, nenhum retorno nasce
   neste pacote — se um número está errado, o bug é da feature dona (F-015..F-029).
2. **Lista de inclusão fechada, exclusão lida do `MANIFEST.json`.** Entra o que está na lista; é
   recusado o que o manifesto marca `publicavel: false` (**D-af**) e ignorado tudo o que não está
   listado.
3. **Determinismo.** Nada lê o relógio: o `.zip` sai com `sha256` idêntico em duas montagens
   (timestamps fixos, ordem fixa), que é o que amarra o pacote ao dataset congelado do gate.

Cobre: RF-043 (CA-113, CA-114), RF-044 (CA-115, CA-116), RF-045 (CA-117) · Anti-SPEC §10.3.18
(nada ao Comitê fora da classe D), §10.3.16, §10.2.10, §10.3.19 · `infra-ops.md §1`.
"""

from __future__ import annotations
