# Módulo `analysis` — figuras e tabelas do Comitê (**classe B**)

> Verdade: `apps/analysis/**` + `docs/specs/SPEC.md` RF-033..RF-037 + **ADR-002** + a skill
> `dataviz`. **Estado (2026-10-11): F-023 (heatmap), F-024 (ranking + concordância) e F-025
> (timeline) implementadas e materializadas**; F-027 (notebook) em curso.
> **Gate FECHADO:** ADR-001 em `Proposta` ⇒ `especificacao_congelada = False` ⇒ **toda figura e toda
> tabela nasce com a marca `ESPECIFICAÇÃO NÃO CONGELADA — não publicável`** (CA-090). Desenvolver é
> liberado; publicar, não.

## A regra que define a camada

**Esta camada LÊ o canônico e não recalcula nada.** `excesso_cdi`, `n_obs` e as flags vêm de F-022;
os rótulos de regime, de F-019; os vizinhos, de F-021. As flags são **reconferidas** contra
`alerta_n_baixo(n)`/`conclusao_suprimida(n)` e a divergência é **erro**, não aviso — é o que impede
uma figura de hachurar por conta própria, ou de deixar de hachurar. Corolário operacional: **se um
número está errado na figura, o bug é da feature dona**, não daqui.

| Arquivo | O que é | Saída em `data/canonical/` |
|---|---|---|
| `apps/analysis/_linguagem.py` | a guarda **única** de linguagem descritiva (§10.2.10) | — |
| `apps/analysis/figuras/_comum.py` | cromo, escala divergente derivada, contraste, procedência, gravação determinística, gate, tooltip SVG | — |
| `figuras/heatmap_regime_ativo.py` (F-023) | heatmap regime × ativo, 3 vistas | `figuras/heatmap_{v1_revised,v1_asof,horizonte_cruzado}.{png,svg}` + `heatmap_dados.parquet` (**322 × 32**) |
| `figuras/timeline_regimes.py` (F-025) | timeline dos 83 trimestres sobre IBOV e Selic | `figuras/timeline_regimes_{revised,asof}.{png,svg}` + `timeline_regimes_dados.parquet` (**166 × 14**) |
| `tabelas/ranking_regime_atual.py` (F-024) | "em que regime estamos?" × 3 + ranking + concordância | `tabelas/ranking_regime_atual.{parquet,csv,md}` (**72**) + `concordancia_lentes.{parquet,csv,md}` |

```bash
python -m apps.pipeline run --offline                              # tudo, nas etapas 12 e 13
python -m apps.analysis.figuras.heatmap_regime_ativo               # as 3 vistas
python -m apps.analysis.figuras.heatmap_regime_ativo --vista v1_revised
python -m apps.analysis.figuras.timeline_regimes --materializacao asof
python -m apps.analysis.tabelas.ranking_regime_atual
```

> `figuras` e `tabelas` são descobertas por `pkgutil` em `run.py`: submódulo que expõe
> `construir(raiz=...)` entra **sem tocar o orquestrador**. Nome começando com `_` é
> infraestrutura (`_comum`, `_linguagem`) e **não** é varrido.

## As três vistas do heatmap — e o nome que mudou

| slug | tabela de F-022 | V1 | V3 |
|---|---|---|---|
| **`v1_revised`** | `regime_asset_metrics.parquet` | `revised`, **T0** | **T+1** |
| `v1_asof` | `regime_asset_metrics_asof.parquet` | `asof`, T0 | — (a V3 **não tem** `asof`) |
| **`horizonte_cruzado`** | `regime_asset_metrics_horizonte_cruzado.parquet` | `revised`, **T+1** | **T0** |

**`horizonte_cruzado` chamava-se `v3_t1` até D-z** (2026-10-11). O slug antigo dizia o **oposto** da
vista: nela a V3 é medida em **T0**, não em T+1 — ela existe para isolar o efeito do **horizonte** do
efeito da **lente**. Os artefatos `heatmap_v3_t1.*` foram removidos do disco.

## Decisões de desenho que não são de gosto

1. **Escala divergente azul ↔ cinza ↔ vermelho, simétrica em `±extremo`.** Azul = bateu o CDI,
   vermelho = perdeu. A simetria é obrigatória: sem ela o cinza do meio deixa de significar
   "empatou" (ADR-002 §3). **Verde está deliberadamente fora** — verde × vermelho é o par que
   colapsa em protanopia/deuteranopia, e é justamente a convenção que o mercado usaria por reflexo.
2. **A paleta é derivada, não escolhida.** O arco frio são 4 passos documentados da rampa azul da
   `dataviz`; o quente é obtido por **bisseção** sobre `branco → #e34948 → preto`, casando a
   luminância de cada passo frio. `validate_palette.py --mode light --pairs all`: os 4 pares
   espelhados passam os seis checks (pior ΔE protan **14,7**). Há teste que **re-deriva** a paleta e
   compara com a constante congelada.
3. **Três estados de confiança, cada um em DOIS canais** — cor nunca sozinha: `n >= 8` cor + número
   em destaque · `5 <= n < 8` cor + **borda tracejada** + `*` · `n < 5` **perde a cor divergente**
   (cinza hachurado) e o número é rebaixado a `prelim. x,x`. Perder o canal de magnitude **é** o
   ponto de CA-109.
4. **O cinza de supressão ≠ o neutro da escala.** Se fossem o mesmo, "sem conclusão" leria como
   "empatou com o CDI" — que é uma afirmação.
5. **A ordem das linhas é declarada, nunca por ranking** (`GRUPOS`). Ordenar por desempenho mudaria
   a posição de cada linha a cada rodada e destruiria a comparação entre figuras. **`CDI` fecha a
   figura** e sai identicamente zero: é o *sanity check* visual da própria métrica.
6. **Timeline: 2 painéis empilhados, NÃO eixo y duplo.** O contrato original falava em "eixo
   direito" para a Selic; eixo duplo faz a posição relativa das curvas virar artefato da escala.
   CA-100 pede a faixa "sobre as duas séries", e ela está **dentro** de cada painel (lavagem de 14%
   atrás da linha + fita saturada na base). **`INDETERMINADO` é cinza hachurado, nunca uma 5ª cor
   categórica** — é o que impede o "buraco visual não explicado": não há buraco, há **ausência
   rotulada**.
7. **Tooltip textual no SVG** (`<title>` por célula, injetado por `gid`): erro-padrão,
   `hit_ratio_cdi`, mediana, `pior_tri` e flags. O PNG não tem — por isso **o SVG é o artefato de
   conferência**.

## `SP500_USD` saiu do heatmap (D-z)

Retorno em **USD** contra o CDI em **BRL** mistura moedas (Anti-SPEC §10.2.12): a célula não tem
leitura. Pior, a linha ficava sob o cabeçalho de grupo **"INTERNACIONAL (EM BRL)"**, que **afirma**
BRL para uma série em USD. A figura tem agora **23 linhas** (23 ≥ 18 de RF-033) e **115 células** na
vista principal. **A linha não foi apagada do dado** — segue nas 3 tabelas de F-022 —, e a exclusão
é **nomeada no rodapé**. Há teste de acervo que falha nas **duas** direções: se `SP500_USD`
aparecer na figura, ou se **desaparecer** da tabela.

## Determinismo — a obrigação de quem acrescenta figura

`Figure` instanciada direta (**sem `pyplot`**, sem estado global), backend `Agg`, `svg.hashsalt`
fixo, `Date: None` no SVG, `Software` fixo no PNG, e a bisseção da paleta com **iterações fixas**
(não por convergência). Medido: 3 rodadas → artefatos **byte-idênticos**, PNG inclusive. Isso não é
preciosismo: `data/canonical/figuras/` entra no `MANIFEST.json`, logo **figura não determinística
move o `DATASET_SHA256` entre rodadas** e quebra CA-121 para o dataset inteiro. Quem adicionar
figura herda essa obrigação.

Nenhum módulo lê o relógio, a rede ou variável de ambiente. O `versao_build` de cada artefato é o
`sha256` do **conjunto de módulos** que determina o conteúdo — incluindo `_comum` e `_linguagem` —,
então editar o cromo **muda o hash de propósito**, com o dado parado.

## A guarda de linguagem é UMA (`_linguagem.py`)

Até 2026-10-11 havia **três**: uma lista de frases no heatmap, uma tupla de 5 termos dentro de um
**teste** da timeline, e a única executável e reutilizável, em F-024. O QA da Onda 4 (**P2-1**)
mediu a consequência: a de F-024, aplicada aos textos das outras features, **reprovava** material
legítimo — as 5 figuras por *"Nada aqui e projecao"*, e `LIMITACOES-COMITE.md` por
`nunca "quanto vai render"`, *"**Backtest** … não está neste pacote"* e *"a **recomendação** é do
Alexandre"*. O defeito não estava nos textos: a janela de negação só olhava para trás e só via
`não`/`nunca` **colados** ao termo.

O modelo da guarda única, em `apps/analysis/_linguagem.py`:

- **forma assertiva** (`"vai render"`, `"esperamos"`, `"retorno esperado"`) — proibida, com **uma**
  exceção medida: a frase **citada dentro de uma negação curta** (40 caracteres, só para trás), que
  é como os documentos reais dizem o que não fazem;
- **substantivo preditivo** (`"previsão"`, `"backtest"`, `"recomendação"`) — permitido **só sob
  negação**, com janela nos **dois** sentidos (160 antes, 60 depois) e reconhecendo `nada … é`, `≠`,
  `sem`, `proíbe` e **cabeçalho de seção negada** (`O que NÃO está neste pacote` nega tudo abaixo);
- **`descritivo` NÃO conta como negação** — aparece em cabeçalho e selo de quase todo artefato
  desta camada, e aceitá-la absolveria qualquer afirmação na mesma vizinhança: a guarda viraria
  decoração.

As **três** features importam dela, e nas figuras a guarda roda **no desenho** (antes de virar PNG),
não só no teste.

## Armadilhas

- **`NaN is None` é `False`.** Célula sem observação lida do DataFrame como `NaN` iria para o
  **topo** de um ranking ordenado por `excesso_cdi`. É armadilha real, com teste próprio
  (`test_celula_sem_observacao_vai_para_o_fim_nunca_para_o_topo`).
- **O `n` por célula pode ser MENOR que o `n` do regime** (CA-093): o ativo tem janela própria
  (`IFIX` 2011+, `ICON` 2007+, `IMOB` 2008+). Na V3 há célula com `n = 4`. Ler o `n` da coluna como
  se fosse o do ativo superestima a amostra.
- **`erro_padrao_media` é do retorno NOMINAL**, não do excesso (dívida em `TODO.md §6`): a página de
  F-024 declara isso e trata `|excesso|/ep` como **semáforo**, nunca como estatística de teste.
- **Os Parquet de `figuras/` e `tabelas/` não têm schema pandera.** São derivados de figura/tabela,
  não tabela canônica; o contrato é `COLUNAS_DADOS_PLOTADOS` / `COLUNAS_RANKING`, travado por teste.
  Se virarem insumo de modelo, migram para classe C com schema próprio.
- **Acento só no texto renderizado.** Todo `print`/log desta camada é ASCII (Anti-SPEC §10.4.26):
  `BLOQUEADO — FONTE INDISPONÍVEL` com travessão quebra o console em cp1252.

## O que a figura e a tabela dizem ao Comitê

**Em `3T2026` a interseção dos top-5 das três lentes é VAZIA**, e isso **é** o resultado (CA-103),
não um defeito. O par V1 `revised` × V1 `asof` tem Jaccard **0,0** e Spearman **−0,748** com a
**mesma** lente e o **mesmo** método — só muda a safra do dado; é CA-074 traduzido em ranking de
ativos. Sobre as 61 referências comparáveis, a concordância V1 × V3 tem **mediana 0,111** e
**nenhuma** referência em 20 anos tem o top-5 idêntico. Com erro-padrão de 2 a 5 pp e `n` de 4 a 19,
**a ordem do topo não é distinguível de ruído** — e é essa a frase que acompanha a figura.
A página de F-024 **não escolhe** a lente: traz as três com peso igual e diz que escolher é **D1**,
do Edu.

**Features:** **F-023** · **F-024** · **F-025** (implementadas) · **F-027** (notebook, em curso) ·
**F-031** (pacote ao Comitê, classe D).
**Ver também:** `modules/regimes.md` (as métricas e as lentes) · `modules/canonical.md` (o comando
único e o `MANIFEST.json`) · `modules/internacional.md` (F-026) · `ADR-002` (métrica do heatmap).
