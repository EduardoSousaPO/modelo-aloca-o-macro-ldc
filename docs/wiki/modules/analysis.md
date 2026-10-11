# Módulo `analysis` — figuras e tabelas do Comitê (**classe B**)

> Verdade: `apps/analysis/**` + `docs/specs/SPEC.md` RF-033..RF-037 e RF-041..RF-045 + **ADR-002**
> + a skill `dataviz`. **Estado (2026-10-11): a camada está COMPLETA** — F-023 (heatmap), F-024
> (ranking + concordância), F-025 (timeline), **F-027 (caderno de entrega)** e **F-031 (pacote ao
> Comitê, classe D)** implementadas e materializadas. F-027 e F-031 aguardam QA independente.
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
| `notebooks/entrega_comite_2026-10-14.ipynb` (F-027) | o **caderno** do Comitê: 11 seções, 34 células, **zero cálculo** | `entrega/entrega_comite_2026-10-14.html` (executado, ~2,0 MiB) + `entrega/_executado.ipynb` |
| `entrega/montar_pacote.py` (F-031) | o **pacote** classe D: copia, converte formato e hasheia — **não publica** | `entrega/pacote_comite_2026-10-14/` (**41 arquivos + `HASHES.txt`**) + o `.zip` determinístico |

```bash
python -m apps.pipeline run --offline                              # tudo, nas etapas 12 e 13
python -m apps.analysis.figuras.heatmap_regime_ativo               # as 3 vistas
python -m apps.analysis.figuras.heatmap_regime_ativo --vista v1_revised
python -m apps.analysis.figuras.timeline_regimes --materializacao asof
python -m apps.analysis.tabelas.ranking_regime_atual
python -m apps.analysis.entrega.montar_pacote --smoke         # monta + 93 checagens, rc != 0 se falhar
python -m apps.analysis.entrega.montar_pacote --so-smoke      # confere o pacote em disco
python -m apps.analysis.entrega.montar_pacote --limpar        # apaga o pacote
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

## O caderno (F-027) — a regra "sem cálculo" é um teste, não um pedido de revisão

`apps/analysis/notebooks/entrega_comite_2026-10-14.ipynb`: **34 células** (15 markdown + 19 de
código), **11 seções** na ordem em que a reunião precisa delas — gate e `DATASET_SHA256`, pedido do
e-mail × entregue, as 4 camadas de dado com amostras e os 3 canários, os regimes (timeline,
distribuição, indeterminados, defasagem), os "momentos semelhantes" de 2026Q3 com `n` e erro-padrão,
o mapa de calor, "em que regime estamos" respondida **três** vezes, o internacional, as limitações,
as 12 decisões e como reproduzir.

**O caderno não calcula.** Ele abre arquivo (`pd.read_parquet`, `json.loads`), recorta (`loc`,
`head`, `isin`), formata chamando função pública de `apps/` (`pct`, `pp`, `num` passados ao
`Styler.format`) e mostra. É `CLAUDE.md §3` / `AGENTS.md §19`, e aqui é **executável** — teste de AST
em `tests/unit/test_notebook_entrega.py` (35 testes) reprova:

1. `def`, `async def`, `lambda`, `class`;
2. **todo operador aritmético** (`+ - * / // % ** @` e as formas compostas). Comparação (`==`, `<`)
   e combinação booleana de máscara (`&`, `|`, `~`) passam: **recortar linha não é calcular**.
   Consequência prática: `Path / "x"` é `ast.Div` e por isso o caminho sai de
   `caminho_canonical("figuras/…")`; e percentual é `Styler.format({"media": pct})`, nunca `x 100`;
3. **29** métodos de agregação/transformação do pandas (`sum`, `mean`, `corr`, `groupby`, `apply`,
   `rolling`, `pct_change`, `quantile`, `resample`, …);
4. escrita em `data/` (`to_parquet`, `to_csv`, `write_text`, `write_bytes`, `mkdir`, `savefig`);
5. relógio e aleatoriedade (`datetime.now`, `time.time`, `random`, `uuid`, `os.environ`, `getenv`) e
   `metadata.execution` nas células — relógio dentro de arquivo versionado;
6. output sujo (`execution_count` diferente de 0) e **CRLF** (o `nbconvert` no Windows grava CRLF:
   conteúdo idêntico, `sha256` diferente — é o problema de **D-v**).

**Toda célula tem `id` explícito.** Sem isso o `nbformat` sorteia um novo a cada gravação, o arquivo
muda de bytes sem mudar de conteúdo e o diff do `.ipynb` deixa de servir para revisão. Com os `id`
fixos: **3 gerações -> mesmo `sha256`**. **O gerador do caderno não está versionado** (dívida em
`TODO.md §6`): manutenção é direto no `.ipynb` (JSON legível), **mantendo o `id`**, com
`nbconvert --clear-output` antes do commit. Ver `apps/analysis/notebooks/README.md`.

**Export** — `python -m nbconvert`, **não** `jupyter nbconvert`: nesta máquina o despachante
`jupyter` resolve pelo `PATH` e cai num Python 3.12 global que levanta
`ModuleNotFoundError: notebook.services` antes de converter nada. E o kernel roda com o **diretório
do notebook** como `cwd`, por isso a cópia executada vive dentro da árvore do repositório. O
procedimento está em `apps/analysis/notebooks/README.md` e em `wiki/context/F-027.md §14`.

## O pacote (F-031) — prepara, não publica

`apps/analysis/entrega/montar_pacote.py` **copia artefato, converte formato e hasheia**. Não envia,
não roda `freeze`, não cria `git tag`, não reconstrói o canônico e **não calcula um único número**:
se um número está errado, o bug é da feature dona (F-015..F-029). **41 arquivos + `HASHES.txt`**,
10,9 MB soltos / 3,7 MB no `.zip`, em `data/canonical/entrega/pacote_comite_2026-10-14/`. Conteúdo:
**10** tabelas em Parquet e CSV pt-BR, 5 figuras em PNG e SVG, as 2 tabelas do Comitê em `.md` e
`.csv`, o caderno (`.ipynb` + HTML executado), `README-COMITE.md`, `LIMITACOES-COMITE.md`,
`SUBSTITUICOES-DE-FONTE.md` (CA-117), `PACOTE-COMITE.xlsx` de **8 abas** e `MANIFEST.json`.

Cinco coisas que quem mexer aqui precisa saber:

1. **O selo do gate é lido do ADR em disco, sempre**, por `status_adr_001()` de F-019 — a mesma
   função das figuras e das tabelas —, com **falha fechada** (ADR ausente ou ilegível ⇒
   `DESCONHECIDO` ⇒ **não** congelado). O dia em que o Edu virar o `Status` para `Aceita`, o selo cai
   sozinho do README, do XLSX e do `HASHES.txt`: **zero linha de código.**
2. **Parquet entra por cópia byte a byte, nunca reserializado.** `read_parquet` + `to_parquet`
   produziria **outros bytes** e o `sha256` deixaria de bater com o `MANIFEST.json` — a amarra do
   dataset congelado morreria em silêncio. O CSV é derivado; o Parquet é cópia.
3. **Duas convenções de CSV convivem, declaradas.** `dados/*.csv` sai em pt-BR (`;`, vírgula
   decimal, UTF-8 **com BOM**, LF) — o que o Excel pt-BR abre sem assistente de importação.
   `tabelas/*.csv` vem de F-024 com `,`, ponto decimal e **sem** BOM, e é **copiado byte a byte**:
   reescrevê-lo criaria uma segunda versão da mesma tabela. As duas estão no README e na aba
   `Leia-me`.
4. **Duas fontes de relógio no XLSX, as duas neutralizadas.** O `zipfile` grava a hora corrente em
   cada entrada **e** o `openpyxl` **sobrescreve** `wb.properties.modified` com o UTC do `save()`,
   ignorando o valor fixado pelo chamador (medido: duas montagens no mesmo minuto diferindo em 1 s).
   `_rezipar_deterministico` corrige as duas. Sem isso CA-121 cai. **Nenhuma célula começa com `=`**
   — há teste que varre as 8 abas: o arquivo descreve um dataset congelado, não recalcula ao abrir.
5. **Nulo legítimo entra com contagem travada**, não com exceção genérica: `ret_tri` nulo em
   exatamente **23** linhas (o primeiro trimestre de cada série; o CDI não tem âncora porque é taxa
   acumulada) e `regime_v1` nulo em exatamente **16** (todas `INDETERMINADO`). Painel que mudar faz
   o smoke **reprovar** em vez de calar.

**O que não entra, e por quê:** `internacional_pesos.parquet`, porque o `MANIFEST.json` o marca
`publicavel: false` (**D-af**) — o módulo **recusa montar** se a lista de inclusão contrariar o
manifesto, e **a lista não vence o manifesto**. Também fora, por omissão: `raw_series`,
`alinhado_trimestral`, `series_catalog`, os `*_provenance`, `regime_neighbors` da V1, `ldc.duckdb` e
os `relatorio_*.json`.

**O pacote não é artefato do manifesto (`D-ag`).** Ele vive dentro de `data/canonical/`, que o
`verify` cobre recursivamente, mas `inventariar()` ignora o prefixo `entrega/pacote_comite_`: o
pacote é **cópia** de artefato já manifestado, montado depois do `freeze` e reconstruível por um
comando (CA-114). **A ordem do gate continua** `run --offline` -> `verify` -> `freeze --tag` ->
`montar_pacote --smoke`, porque o pacote **copia** o `MANIFEST.json` e precisa dele já congelado. E
o `DATASET_SHA256` que o HTML do caderno imprime é, por construção, o da rodada **anterior** à
inclusão do próprio HTML — **a versão que vale é a de `MANIFEST.json`/`HASHES.txt`**.

## Publicar é classe D, e o gate está FECHADO

Nada desta camada vai ao Comitê sem os 8 passos de `AGENTS.md §14`. Hoje o passo 2 está **reprovado**
(ADR-001 em `Proposta`), e isso vale também para "só esse número do heatmap no WhatsApp": **não
existe classe A/B para publicação** (Anti-SPEC §10.3.18). O gate executável é
`docs/wiki/runbooks/entrega-comite.md`; o roteiro humano de 30 minutos é
`docs/product/GUIA-REVISAO-EDU.md`.

**Features:** **F-023** · **F-024** · **F-025** · **F-027** · **F-031** — todas implementadas;
F-027 e F-031 **aguardam QA independente**.
**Ver também:** `modules/regimes.md` (as métricas e as lentes) · `modules/canonical.md` (o comando
único e o `MANIFEST.json`) · `modules/internacional.md` (F-026) · `ADR-002` (métrica do heatmap) ·
`runbooks/entrega-comite.md` (o gate) · `docs/product/GUIA-REVISAO-EDU.md` (a revisão do Edu).
