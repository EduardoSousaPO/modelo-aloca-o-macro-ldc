# Runbook — Fonte fora do ar (ou mentindo que está no ar)

**Última execução verificada:** — (esboço; **o caso do FRED já ocorreu** e está documentado abaixo)
**Tempo médio estimado:** 10-20 min de diagnóstico
**Risco:** médio · **alto** se a conclusão for trocar de fonte → exige linha no `DECISIONS_LOG`

> ⚠️ Esboço escrito a partir dos 22 riscos de extração da pesquisa
> (`docs/research/fontes-de-dados.md`, seção "Riscos de extração").

## 1. Quando usar

Quando um extrator falha, trava, devolve menos dado do que devia — **ou devolve dado errado com HTTP 200**.
Neste projeto o modo de falha mais perigoso **não** é a queda: é a **falha silenciosa**.

## 2. Antes de culpar a fonte: as 4 falsas quedas

| Sintoma | Causa provável | Checagem |
|---|---|---|
| JSON "vazio" ou dict em vez de array (SGS) | **R1** — janela > 10 anos em série diária; o erro vem com **status 200** | o corpo tem chave `error`? Fatiar em blocos ≤ 5 anos |
| HTML onde se esperava JSON/CSV | série inexistente (SGS) ou página SPA (**R9**: B3 e ANBIMA Data servem shell Angular de ~2 KB) | sniffar o 1º byte: `<` = HTML, `PK` = OOXML |
| Exatamente 20.000 linhas, sem `nextLink` (Olinda) | **R2** — truncamento silencioso do `$top` | omitir `$top` / paginar com `$skip`; **assert de contagem mínima** |
| 1 único ponto, ou granularidade trocada (Yahoo) | **R2/R4** — `SMLL.SA` & cia. devolvem 200 com 1 ponto; `1mo` virou `1wk` | validar `len(df) > 1` e o `dataGranularity` devolvido |

## 3. Diagnóstico de queda real

```bash
# 1. a fonte responde? UA de browser SEMPRE (sem ele Yahoo da 429 e o CKAN do BCB da erro)
python -m pipeline.healthcheck --fonte <fonte>     # placeholder (F-011/RF-049)
# 2. separar as camadas: DNS -> TCP:443 -> TLS -> HTTP. TCP+TLS OK mas HTTP com
#    ReadTimeout/ConnectionReset(10054) = bloqueio de APLICACAO (WAF/CDN), nao lentidao.
# 3. confirmar com o Playwright MCP (diagnostico APENAS — nunca no pipeline, RO-7)
```

## 4. Decisão

| Veredito | Ação |
|---|---|
| Queda **transitória** | retry com backoff; se a fonte tem atraso declarado (**R17**, ANBIMA), isso é **normal** → registra, não falha |
| Fonte **descontinuada** (**R16**: swaps SGS 2019, IMA SGS 2023, EMBI+ 2024) | **não** usar série morta como se viva → substituir e registrar no `DECISIONS_LOG` |
| **Layout mudou** (**R18**: B3, MSCI, S3) | teste de contrato com valor-canário aponta; corrigir o parser, nunca afrouxar o teste |
| **Bloqueio de ambiente** (**R5**: FRED) | falha **explícita** `BLOQUEADO — FONTE INDISPONÍVEL` + plano B já mapeado (**S-09**) |
| Sem substituto acordado | **pare e escale.** Nunca interpolar, estimar ou inventar (Anti-SPEC §10.1.1) |

**Toda troca de fonte entra em [`docs/plans/DECISIONS_LOG.md`](../../plans/DECISIONS_LOG.md)** com fonte
pedida / fonte usada / por quê / impacto na comparabilidade — e, se chegar ao Comitê, em comunicação
escrita ao Alexandre (RF-045). **Fallback silencioso é proibido.**

## 5. Caso já ocorrido — FRED (R5, 2026-10-10)

`fred.stlouisfed.org` resolve (`23.10.51.194`), TCP:443 conecta em 0,04 s, TLS 1.3 completa em 0,03 s, mas
a resposta HTTP dá **ReadTimeout** e, no retry, **`ConnectionReset(10054)`** — reproduzido **3/3**, idem
`api.stlouisfed.org`. Diagnóstico: bloqueio na camada de aplicação deste egress. Plano B validado na mesma
sessão (Yahoo `^TNX`/`^FVX`/`^VIX`/`DX-Y.NYB` + MSCI + PTAX). Registrado como **S-09** no `DECISIONS_LOG`;
`DFF`/`FEDFUNDS` segue **sem substituto equivalente** → lacuna declarada.

**Histórico:** 2026-10-10 — pesquisa + skill-scout — FRED **BLOQUEADO**, plano B validado (ver §5).

**Links:** [`skills-manifest §3`](../../plans/skills-manifest.md) ·
[`modules/internacional.md`](../modules/internacional.md) ·
[`runbooks/reconstruir-dataset.md`](./reconstruir-dataset.md)
