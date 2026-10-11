# Guia de revisão — Edu, terça 13/10, 30 minutos

**Para:** Eduardo (Edu) · **De:** o orquestrador · **Data:** 2026-10-11 · **Comitê:** 2026-10-14
**O pacote está montado, verificado e selado. Ele não sai sem você.**

> # ENQUANTO ADR-001 ESTIVER EM `Proposta`, NADA SAI — NEM UM NÚMERO POR WHATSAPP.
> Vale para o pacote inteiro **e** para "só essa célula do heatmap". **Não existe classe A/B para
> publicação** (`AGENTS.md §14`, Anti-SPEC §10.3.18). O pipeline sabe disso: ele lê o `Status` do
> ADR em disco e publica `especificacao_congelada = false` em cada rodada.

---

## 1. Ordem de leitura — 30 minutos, nesta sequência

| # | O quê | Onde | Tempo | O que você responde |
|---|---|---|---|---|
| 1 | **§0 (o aviso do topo) e §7 (as 12 decisões)** da página de limitações | `docs/product/LIMITACOES-COMITE.md` | 8 min | aceito as recomendações, ou viro alguma? |
| 2 | **A timeline dos 83 trimestres** | `data/canonical/figuras/timeline_regimes_revised.png` | 5 min | a história que ela conta é a que você viveu? |
| 3 | **"Em que regime estamos" + o ranking** | `data/canonical/tabelas/ranking_regime_atual.md` | 7 min | as 3 lentes divergindo é aceitável no slide? |
| 4 | **O mapa de calor, vista principal** | `data/canonical/figuras/heatmap_v1_revised.svg` | 5 min | alguma célula contradiz o que você sabe? |
| 5 | **O caderno executado, de cabo a rabo** | `data/canonical/entrega/entrega_comite_2026-10-14.html` | 5 min | falta alguma coisa que o Alexandre vai perguntar? |

**Leia o SVG, não o PNG, no item 4:** o SVG tem *tooltip* por célula com erro-padrão, `n`,
`hit_ratio_cdi` e mediana. O PNG não tem.

**Dois achados que você vai encontrar, e que não são bug:** (1) a V1 troca de rótulo entre `revised`
e `asof` em **33,33%** dos trimestres comparáveis, acima dos 25% de CA-074 — pelo critério escrito,
a V1 **não é operacional na forma `asof`**; (2) em `3T2026` a **interseção dos top-5 das três lentes
é VAZIA**, e a ordem do topo **não é distinguível de ruído** (erro-padrão de 2 a 5 pp, `n` de 4 a
19). Os dois são resultado, e vão ao slide — não a nota de pé.

## 2. As 12 decisões — a recomendação e o custo de discordar

Nenhuma destas respostas veio de uma pessoa: todas são a recomendação da pesquisa, aplicada como
padrão provisório. Virar qualquer uma é legítimo e previsto. Integral em `LIMITACOES-COMITE.md §7`.

| # | Decisão | Recomendação adotada | Custo de discordar |
|---|---|---|---|
| **D1** | qual lente é a oficial | V1 oficial · V3 como leitura central · V2 secundária | V2 oficial ⇒ 12 estados com 5 a 15 obs. e metade das células em alerta; V3 oficial ⇒ o entregável central passa a ser a lista de vizinhos |
| **D3** | eixo de inflação da V1 | **aceleração** do IPCA (Δ da taxa de 12m) | "nível vs. meta" exige a série de metas do CMN, que **não está na base**, e **os 83 rótulos mudam** |
| **D5** | métrica do heatmap | **excesso sobre o CDI** | nominal torna 2006 (Selic 19%) e 2020 (Selic 2%) incomparáveis; real muda a leitura. As 3 já são colunas: é trocar 1 parâmetro |
| **D6** | internacional | piso **16-20%** + banda tática **15-35%** por regime | "100% tático" exigiria otimizar com ~20 obs. por regime e dar número pontual, que esta base não sustenta |
| **D12** | setoriais e FII no pacote mínimo | *best effort*, com `n` e data de início visíveis | "completo" acrescenta extratores ao caminho crítico; "fora" reduz o heatmap |
| **L1** | IFIX só desde 2011 | janela própria 2011-2026 + IMOB (2008+) como proxy imperfeito. **Sem IFIX sintético** | painel balanceado restringe **toda** a análise a 2011-2026 e a janela de 20 anos do e-mail cai |
| **L2** | FII por segmento (provedor privado, 2019+) | só como leitura qualitativa — e **não foi extraído** | se autorizado, entra com ~2 ciclos macro e sem valor inferencial; se negado, o item **B5b** fica formalmente não atendido |
| **L4** | curva oficial da ANBIMA é paga | **não contratar**; usar a curva do Tesouro Direto | contratar (R$ 686-8.238/mês) dá a curva oficial, recalcula a inclinação histórica e **passa a envolver credencial** (vira classe D) |
| **D-i** | qual inclinação é a variável de regime | **5 anos − 3 anos** (95,25% de cobertura) | a 5a−1a tem **60,53%**: ~40% dos trimestres cairiam num dia sem valor |
| **D-s** | nível trimestral do IBC-Br | **média dos 3 meses** | voltar ao último mês faz **7 trimestres** mudarem de quadrante de volta |
| **D-t** | movimento de 25 pb na Selic | é **ciclo** (corte/alta), nos dois sentidos | com a regra estrita, os **7** movimentos de exatamente 25 pb voltam a ser "parada" — **5 cortes e 2 altas**, entre elas a alta de set/2024 que abriu o aperto |
| **D-u** | eixo de crescimento da lente de "momentos semelhantes" | **expectativa de PIB do Focus** | sem o Focus a lente **não tem vetor para 2026Q3** — justamente o trimestre da pergunta — e perde 2006-2009 |

**Atalho:** responder **"aceito as recomendações"** destrava as 12 de uma vez.

## 3. Como destravar — trocar `Status:` por `Aceita`

O gate é lido do disco, com falha fechada. Em **cada** arquivo abaixo, na linha 3, troque
`- **Status:** **Proposta** — …` por `- **Status:** **Aceita** — Edu em 2026-10-13`. Nenhuma linha de
código muda: um rebuild refaz os 83 trimestres e o selo cai sozinho do README, do XLSX, das figuras,
das tabelas e do caderno.

| ADR | Arquivo | Responde |
|---|---|---|
| **ADR-001** ⬅ **o gate duro** | `docs/decisions/adr/ADR-001-lente-de-regime-oficial.md` | **D1** e **D3** |
| ADR-002 | `docs/decisions/adr/ADR-002-metrica-primaria-do-heatmap.md` | **D5** |
| ADR-003 | `docs/decisions/adr/ADR-003-abordagem-alocacao-internacional.md` | **D6** |
| ADR-004 | `docs/decisions/adr/ADR-004-inclinacao-curva-via-tesouro-direto.md` | **L4** |
| ADR-005 | `docs/decisions/adr/ADR-005-janelas-proprias-e-fii-segmentado.md` | **L1**, **L2**, **D12** |
| ADR-006 | `docs/decisions/adr/ADR-006-armazenamento-e-convencao-de-retornos.md` | fim de período + ffill ≤ 5 d.u. + a opção (a) de D-h |

> **Só o ADR-001 bloqueia a publicação.** Os outros cinco são o aceite formal do que já está
> construído; sem eles o número sai com a convenção declarada como provisória.

## 4. Os comandos, na ordem

```bash
uv run python -m apps.pipeline run --offline                        # 13 etapas, sem rede, ~1 min
uv run python -m apps.pipeline verify                               # confira o rc, nao o tail
uv run python -m apps.pipeline freeze --tag comite-2026-10-14       # MANIFEST.json + FROZEN.txt
uv run python -m apps.analysis.entrega.montar_pacote --smoke        # 41 arquivos + 93 checagens
git tag -a comite-2026-10-14 -m "Pacote ao Comite - DATASET_SHA256=<hash do FROZEN.txt>"
```

**A ordem importa:** o pacote **copia** o `MANIFEST.json`, então ele precisa do `freeze` antes —
montar primeiro produz um pacote que cita um dataset que ainda vai mudar. `freeze` **não executa
git** de propósito: a tag é ato humano. Correção pós-envio gera tag **nova**, nunca `git tag -f`.

## 5. A checklist de 19 caixas

Está escrita em **`docs/wiki/runbooks/entrega-comite.md §2`**: os 14 itens de `infra-ops §1.4` + os
3 canários + os 2 de leitura (item 18 = a timeline faz sentido? · item 19 = as 12 decisões estão
respondidas?). **Cada caixa precisa de evidência colada** no PR ou em `wiki/log.md` — "conferi" sem
evidência não conta. **Marcou as 19?** O envio é seu. **Falta uma?** Não envia.

Duas caixas só você consegue fechar, porque nenhuma máquina deste projeto tem o que elas pedem:
**abrir o `PACOTE-COMITE.xlsx` no Excel de verdade** (não há Excel nem LibreOffice aqui) e **conferir
os 3 canários na fonte viva**.

## 6. Os 3 canários — na fonte viva, não no Parquet

São os três valores que atravessam o pipeline inteiro. Hoje estão conferidos contra
`raw_series.parquet`, **não** contra a fonte — e é essa conferência que falta.

| Valor esperado | Série e data | Onde conferir |
|---|---|---|
| **38.484,84** | IBOV, **01/02/2006** | portal de índices da B3 → `https://sistemaswebb3-listados.b3.com.br/indexStatisticsPage/` (API: `.../indexStatisticsProxy/IndexCall/GetPortfolioDay/{base64 de {"language":"pt-br","index":"IBOV","year":"2006"}}`) |
| **723,070317** | IMA-B, **16/09/2003** (1º dia da série) | `https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/arquivos/indices-historico/IMAB-HISTORICO.xls` (é XLSX, a extensão mente) |
| **121,3858** | MSCI ACWI **NETR**, **31/01/2006** | `https://www.msci.com/end-of-day-data-search` → ACWI, variante **NETR** (API: `https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph`, `index_code 892400`) |

⚠️ **Variante errada = série errada.** `STRD` é preço e começa em 1997; `NETR` é retorno total e
começa em 2000-12-29. É o `NETR` que está na base.

---

**Links:** o gate inteiro → `docs/wiki/runbooks/entrega-comite.md` · o que só você pode fazer, em
tabela → `TODO.md §4` · rollback → `docs/plans/infra-ops.md §1.6` · substituições de fonte →
`docs/plans/DECISIONS_LOG.md §1` · como reproduzir → `LIMITACOES-COMITE.md §8`.

*Linguagem descritiva por contrato (Anti-SPEC §10.2.10): este documento, como todo o pacote, descreve
o que o histórico mostra. Nunca o que vai render.*
