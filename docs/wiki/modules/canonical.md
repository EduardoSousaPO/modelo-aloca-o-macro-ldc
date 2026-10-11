# Módulo `canonical` — camada canônica trimestral (**classe C**)

> Verdade: `docs/specs/SPEC.md` RF-019..RF-026 + `packages/shared/schemas/` + **ADR-006** (em
> `Proposta`) + `docs/contracts/CONTRACTS.md §1.1/§2.4/§8`.
> **Estado (2026-10-11): a camada está completa e com as DUAS materializações.** F-013, F-014,
> F-016, F-015 e F-017 **aprovadas no QA independente** (`docs/plans/qa/ONDA-2-QA-{A,B}.md`,
> 0 × P0); **F-018** entregou a materialização **`asof`** (QA pendente). O Focus (F-010) é consumido
> direto de `data/processed/focus/`. Tudo aqui é **classe C** (`AGENTS.md §2`):
> um trimestre desalinhado contamina retorno, regime e heatmap **sem levantar exceção**.

| Tabela / artefato | Schema | Estado medido em 2026-10-11 |
|---|---|---|
| `raw_series.parquet` (nativa, PK `series_id,date,vintage`) | `raw_series.py` | **278.439** linhas · **62** séries · 1979-12-31 → 2026-10-10 · `linhas_dedup = 0` |
| `series_catalog.parquet` materializado | `series_catalog.py` (`SeriesCatalogMaterializedSchema`) | **138 × 26** (20 declaradas + 6 observadas) · 62 presentes · 59 cobrem 1T2006 |
| `alinhado_trimestral.parquet` (PK `series_id,quarter`) | `alinhado_trimestral.py` | **4.038** linhas · 49 séries · 83 trimestres · 215 ffill · 7 nulos · `c66f09a5…` |
| `relatorio_build.json` · `relatorio_alinhamento.json` | — | `versao_build 6989371e…` / `120550ea…` · hashes, 1 bloco por série, ausências com motivo |
| `ldc.duckdb` (derivado, descartável) | — | **views** `raw_series` e `series_catalog` sobre os Parquet |
| `macro_quarterly.parquet` (PK `quarter`) | `macro_quarterly.py` | **83 × 42** · 2006Q1..2026Q3 · `revised` · **5** colunas 100% nulas, todas por gap declarado · 16 nulos em `ibcbr_gap` (**D-m**) · `bcb31e92…` |
| `macro_quarterly_provenance.parquet` (PK `quarter,column`) | `macro_quarterly.py` | **2.548** linhas · **32** colunas rastreáveis · **20** séries de origem · CA-120 por anti-join nas 2 direções · `aa8d427a…` |
| `macro_quarterly_asof.parquet` (PK `quarter`) | `macro_quarterly.py` (mesmo schema) | **83 × 42** · `asof` (`lag_adjusted=True` nas 83) · **27** colunas idênticas à `revised`, **10** mudam · `85e8ec67…` |
| `macro_quarterly_asof_provenance.parquet` (PK `quarter,column`) | `MacroQuarterlyAsofProvenanceSchema` (**subclasse**) | **2.552** linhas · **+ `date_obs` + `lag_dias` em todas** · **0** células com divulgação depois do fim de T · `a5b2eaef…` |
| `asset_returns_quarterly.parquet` (PK `quarter,asset_id`) | `asset_returns_quarterly.py` | **1.963** linhas · **24** ativos (USDBRL entrou por **D-l**) · 83 trimestres · 215 ffill · 820 `is_total_return` nulos (G-01) · `c055ac81…` |
| `relatorio_macro.json` · `relatorio_retornos.json` · `relatorio_asof.json` | — | `versao_build 6367b761…` / `707438bc…` / `ced73173…` · nulos **por coluna com motivo**, unidades, canários, anti-look-ahead, `bases_por_trimestre`, lag por coluna, % de troca |
| `calendario_dias_uteis` (grade de dias úteis) | `calendario.py` | 10.957 dias, 2001→2030 (F-008) |

## UM comando reconstrói a camada (F-029)

```bash
python -m apps.pipeline run --offline     # 13 etapas na ordem; sem rede, de data/processed/
python -m apps.pipeline verify            # recalcula todo sha256 x MANIFEST.json; rc != 0 se divergir
python -m apps.pipeline freeze --tag comite-2026-10-14   # MANIFEST.json + FROZEN.txt
python -m apps.pipeline run --offline --listar-etapas    # a ordem, sem rodar
python -m apps.pipeline run --offline --so regimes_v3    # retoma uma etapa
python -m apps.pipeline run --offline --sem-duckdb       # diretório 100% determinístico
```

**A ordem é o contrato da feature**, fixada por teste: `curva` (F-016, escreve em
`data/processed/`) → `build_raw_series` → `alinhamento` → `macro_quarterly` → `asof` → `retornos` →
`regimes_v1` → `regimes_v1_asof` → `regimes_v3` → `metricas_regime` (F-022) → `internacional`
(F-026) → `figuras` (F-023/F-025) → `tabelas` (F-024). As 4 últimas são **opcionais**: pulam com
aviso se o módulo não existir — mas falha **dentro** de um `construir()` **para** o pipeline.
`figuras` e `tabelas` descobrem submódulos por `pkgutil` (nome com `_` é privado e não é varrido),
então figura ou tabela nova entra sem tocar `run.py`.
**Nenhuma etapa reimplementa cálculo:** cada uma chama o `construir(raiz=...)` da feature dona — se
um número está errado, o bug é da feature dona.

> ⚠️ **As etapas `internacional` e `tabelas` faltavam até 2026-10-11** (P1-2 do QA da Onda 4): o
> manifesto tinha 30 artefatos e o diretório, 44, e "um comando" entregava ~2/3 do canônico com
> `rc = 0`. Hoje são **48** conferidos.

### `MANIFEST.json` e `FROZEN.txt` — o que o gate da classe D consulta

Todo `run` grava o `MANIFEST.json`: por artefato, `sha256` + bytes + linhas + colunas + coluna de
data com min/max + **% de nulos por coluna** (CA-118), mais `versao_build` de cada relatório,
`data_do_dado` e o **agregado**. O agregado é no formato `sha256sum` — `sha256` do corpo
`"<sha256>  <arquivo>\n"` dos artefatos determinísticos, ordenados por nome, terminador LF —, logo
**reproduzível na linha de comando** (`infra-ops.md §1.2`). Nome no manifesto é caminho relativo
POSIX (`figuras/heatmap_dados.parquet`), para a ordem ser a mesma no Windows e no Linux.

Dois campos que mudam o que vai ao Comitê:

- **`determinista: false`** — só o `ldc.duckdb`: **medido** que em diretório criado do zero duas
  escritas dão o mesmo tamanho (274.432 B) e `sha256` **diferente** (reescrita sobre arquivo
  existente sai idêntica). Ele entra no manifesto com `sha256: null` e o motivo escrito, fica
  **fora** do agregado e o `verify` o reporta como `INFO` — é derivado e descartável
  (**ADR-006 §(a).2**: *views* sobre o Parquet). **Congele o pacote da classe D com
  `--sem-duckdb`**: aí `data/canonical/` é integralmente determinístico.
- **`publicavel: false`** (**D-af**) — artefato que é construído e conferido, mas **não vai ao
  Comitê**. Hoje: `internacional_pesos.parquet` (variância mínima, Anti-SPEC §10.3.16/§10.5 →
  F-035). O `FROZEN.txt` abre a seção `EXCLUIDOS DO PACOTE DE ENTREGA` e **F-031 lê esse campo**,
  não o nome do arquivo. Ele **continua** no `DATASET_SHA256`, de propósito: o agregado descreve o
  que foi **construído**, e tirá-lo confundiria reprodutibilidade com publicabilidade.

`verify` detecta byte alterado, artefato ausente, artefato novo não listado, agregado divergente
**e Parquet ilegível** — este último desde 2026-10-11 (P1-1 do QA da Onda 4: antes, `pd.read_parquet`
estourava `OSError`/`ArrowInvalid` **dentro** do inventário, isto é, antes de qualquer comparação, e
a saída era um traceback que não nomeava arquivo nem agregado; hoje o perfil sai vazio com
`ilegivel` e a divergência é reportada com `rc = 1`). `freeze` **não executa git**: o commit vem de
`.git/HEAD` + `refs/` por leitura pura, e a tag continua ato humano.

**Rebuild final da Onda 4 (2026-10-11), 2 rodadas byte-idênticas, `verify` rc 0, 47 artefatos
determinísticos:** `DATASET_SHA256 = fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`.
`raw_series 0d23df7a…` · `series_catalog f56f207e…` ·
`alinhado c66f09a5…` · `macro 2b8b65f4…` +
`provenance f3068b98…` ·
`asof 5c4854f2…` +
`asof_provenance 319312fb…` ·
`asset_returns 2798b5c1…`.

> **Por que todo hash mudou nos rebuilds das Ondas 3 e 4, sem o dado se mover.** `versao_build` é
> o `sha256` do **conjunto de módulos** de cada feature, e tanto o fechamento da Onda 3 quanto o da
> Onda 4 editaram módulos e schemas: na Onda 4, `packages/shared/schemas/{asset_returns_quarterly,
> regimes}.py` (**D-ac**, a guarda de não-nulidade nas flags `bool`) e
> `apps/pipeline/canonical/{macro_quarterly,metricas_regime}.py` (**D-y** P1-3 e **D-ab**).
> `raw_series` e `series_catalog` seguiram byte-idênticos nas duas ondas. As duas causas da Onda 3,
> as duas declaradas:
> **(1) D-v (b)** — `versao_build` passou a **normalizar o fim de linha** antes de hashear
> (`normalizar_fim_de_linha`, P1-4 do QA: o mesmo commit dava `fonte_versao` diferente num checkout
> CRLF e num LF, e 2 dos 7 módulos já estavam em LF no disco). Isso move `fonte_versao` de **toda**
> a camada, de uma vez; **(2) D-s** — o nível trimestral do IBC-Br passou a ser a **média dos 3
> meses**, o que move as **3** colunas de `ibcbr_*`. `raw_series` e `series_catalog` **não** têm
> coluna de versão e saíram **byte-idênticos** — é a contraprova de que o dado bruto não se moveu.

**Unidade — a diferença que mais pode machucar (D-o):** `macro_quarterly` está em **por cento/pp**
e `asset_returns_quarterly` em **fração**. As duas publicam `cdi_tri` e `ipca_tri`, com o **mesmo
nome em escalas diferentes** — quem cruzar sem ler a unidade erra por 100x. Não há bug hoje porque
F-017 calcula as duas por conta própria e **nunca** lê `macro_quarterly`; a reprodução cruzada deu
`max |macro − 100 × retornos| = 0,0` nos 83 trimestres. Ver `CONTRACTS.md §3/§4`.

## O que esta camada fixou (e que F-015/F-017 herdam)

- **`raw_series` é um *union* validado, e nada mais.** Zero agregação, reamostragem, `ffill` ou
  arredondamento: cada série é idêntica **célula a célula** à origem em `data/processed/`. O Parquet
  é **reescrito inteiro** a cada build — **não há `append`**, então série nova só aparece depois de
  **reexecutar** o build (item de DoR de F-010/F-011/F-012/F-016).
- **Quatro guardas públicas** que o pandera não cobre: `validar_procedencia` (CA-055/CA-120),
  `validar_frequencia_nativa` (CA-058), `validar_sem_mistura_de_fontes` (CA-077) e `exigir_series`
  (CA-076 → `BLOQUEADO — FONTE INDISPONÍVEL`). **Importe-as**, não reimplemente.
- **Declarado × observado coexistem no catálogo:** `data_inicio` (pesquisa) ao lado de
  `data_inicio_observada` (disco). A divergência **é informação**, e 3 checks impedem copiar um no
  outro. `calendario` (`dias_uteis`/`corrido`) é de onde F-014 deriva a régua da série.
- **Uma régua só, em 3 grades.** `quarter_end` é **sempre** o último dia útil bancário (chave de
  junção); `date_alvo` varia por série (`bancaria`/`corrido`/`civil`) e em **24 dos 83** trimestres
  as duas datas divergem — legível em **duas colunas**, não deduzido do código.
- **ffill em duas colunas:** `lacuna_dias_uteis` é medida **sempre**; `ffill_dias_uteis` só quando o
  valor foi aproveitado. Acima de **5 d.u.** a célula é `NULL` com `motivo_nulo` e a lacuna
  **registrada** (CA-067). Mês/trimestre não divulgado cai na **mesma** regra, não numa exceção.
- **Materialização `revised`, declarada:** só o último `vintage` por série (D-b); **nenhuma linha
  é `is_estimated`** (a flag de 3T2026 é de F-015, CA-060). **Séries `DERIVADO` ficam fora do
  alinhamento genérico** (9 hoje), porque a derivação tem convenção própria de data e de lacuna:
  quem chama `alinhar_series` é a feature dona (F-016, F-017).
- **A `asof` (F-018) é a materialização de DECISÃO** (SPEC §2, Anti-SPEC §10.2.7); a `revised` é
  legítima para descrição histórica e **sempre rotulada**. As duas têm o **mesmo**
  `MacroQuarterlySchema` e a mesma grade: trocar de materialização é trocar o caminho do Parquet, e
  `lag_adjusted` da linha diz qual foi lida. A regra, por coluna: o valor de `(T, coluna)` é o da
  última observação cuja **divulgação** (`date_obs + lag_divulgacao_dias`, lag **inteiro do
  `series_catalog`**: PIB 60, IBC-Br 45, IPCA 10, Focus/Selic/CDI/curva/câmbio 0) é
  `<= quarter_end(T)`, e **toda derivada é recalculada** sobre os níveis deslocados pelas funções
  puras de F-015 — nenhuma é copiada da revisada. Série sem lag resolvível **para** o build
  (`LagDesconhecido`): assumir 0 reintroduziria o look-ahead que a materialização existe para
  eliminar. `cdi_tri`/`selic_over_tri` (diárias, lag 0) **não deslocam**; `ipca_tri` desloca 1
  trimestre; `ibcbr_*` carrega a média de `T-1` (**D-s**); `pib_yoy` de `T` é o de `T-1`.
- **A `asof` tem 4 linhas de procedência A MAIS, e isso é correto:** em `2026Q3` a `revised` não
  tem PIB nem IBC-Br (a série não cobre o trimestre), e a `asof` — que por regra usa o último
  **divulgado** — carrega o PIB de `2026Q2` e a média do IBC-Br de `2026Q2`. Não é estimativa: é o
  dado que estava na mesa em 30/09.
- **O que sustenta o número da `asof`:** o módulo monta a `revised` **na mesma rodada**, com as
  mesmas entradas e sem defasagem, e a confere **célula a célula e sem tolerância** contra
  `macro_quarterly.parquet` em disco — **3.071 células, 0 divergências, `max |dif| = 0,0`**. Sem
  isso, as duas tabelas sairiam de caminhos de código diferentes e nada do relatório seria
  atribuível ao lag. Divergência **para** o build.
- **Nível trimestral do IBC-Br = média dos 3 meses (`obs = media_3m`, D-s).** `metodologia §2` diz
  "IBC-Br: média do trimestre"; até 2026-10-11 lia-se o **fim de período**. O custo medido da
  leitura antiga: `max |dif|` **4,2646 pp** em `ibcbr_yoy`, **4,3064 pp** no hiato e **7 dos 67
  trimestres trocando de quadrante na V1**. A média exige os **3** meses (2 → `NULL` com motivo,
  nunca média parcial — é o que mantém `2026Q3` nulo), e a procedência registra a **última** das 3
  observações: o limite superior que mantém `date_obs <= quarter_end` verificável no Parquet.
  `pib_yoy` **não** muda (o PIB do SIDRA já é trimestral na fonte).

## Armadilhas

- **Trimestral como dado primário é erro irreversível:** granularidade nativa + **agregação por
  função**; trimestre = **último dia útil**.
- **D-h está decidida: opção (a)** — grade bancária única. O calendário da ANBIMA é **idêntico** ao do
  CDI e do IMA-B em 20 anos, mas **B3 ⊂ ANBIMA em 69 datas**, nunca o inverso: toda série da B3 leva
  `ffill_dias_uteis = 1` em todo 4T — **215** células de 4.038 (5,325%), 11 séries, 20 trimestres,
  **zero** ffill de 2..5. Travado pelo check `quarter_end_unico_por_trimestre`; (b) é mudança de
  **schema**. Vai à página de limitações (F-028).
- **Excesso sobre CDI e retorno real sempre por razão** `(1+r)/(1+b)−1`: com Selic a 14% a diferença
  não é arredondamento. Teste anti-subtração é obrigatório.
- **LIMITAÇÃO DECLARADA — a janela do CDI NÃO é a janela do caminho do ativo** (**D-v c**, P1-1 do
  QA-B; `relatorio_retornos.json → convencoes.janela_do_cdi_vs_caminho_do_ativo`). A janela do CDI
  é `(quarter_end(T-1), quarter_end(T)]`; o caminho de cada ativo é `(date_obs(T-1), date_obs(T)]`.
  Com `ffill = 1 d.u.` (**D-h**: a B3 não publica no último d.u. ANBIMA de 20 dos 4os trimestres)
  `date_obs ≠ quarter_end`, e as duas janelas diferem de **1 a 3 d.u.** em **599 das 1.857** linhas
  com excesso (`-3: 98, -2: 120, -1: 348, 0: 1.258, +1: 22, +2: 11`). Viés implícito no
  `ret_excesso_cdi`: média **0,0185 pp**, p95 0,0984, **máx 0,1575 pp**; nas **212** linhas com
  `ffill = 1`, média **0,0827 pp**. **O cálculo NÃO foi alterado:** é ~8× menor que o efeito
  razão-vs-subtração (0,139 pp), a cadeia de preços é contínua (`price_ini(T+1) == price_fim(T)` em
  **100%** dos casos com ffill, então nenhum dia é perdido nem contado duas vezes) e corrigir
  exigiria reconstruir o CDI por ativo. É **condição do gate classe D** (`AGENTS.md §14.7` pede
  comunicação escrita das limitações) e afeta a métrica-cabeça de ADR-002 — vai à F-028.
- **Look-ahead é o risco dominante, e a `asof` cobre METADE dele.** A `asof` respeita a
  **divulgação** (`lag_divulgacao_dias`), e CA-072 é verificável no Parquet publicado
  (`date_obs + lag_dias <= quarter_end` nas 2.552 linhas, **0** violações; o build para se houver
  uma). Mas a perna de **`vintage`** é **degenerada**: `raw_series` tem **1 safra por série**
  (medido: 0 de 62 com mais de um `vintage`), então a `asof` usa a série **revisada de hoje** — o
  efeito de look-ahead publicado é um **piso**, não o total, e a revisão anual do PIB não está nele.
  Declarado em `relatorio_asof.json → limitacoes.vintage_unico`. Agrava: `lag_divulgacao_dias` é
  defasagem **típica em dias civis** e **não** foi auditada release a release — se o IBGE atrasar um
  release específico, a `asof` daquele trimestre é otimista (arredondar para cima é conservador:
  descarta informação, nunca cria look-ahead). As duas dívidas estão em `TODO.md §6`.
- **`pib_qoq_sa` na `asof` é a variação de `T-1`, não de `T`.** É nível publicado pelo IBGE
  (variação T/T−1 dessazonalizada) com lag 60, então a linha `T` carrega a variação do trimestre
  anterior. Quem ler a coluna como "variação do trimestre T" sem olhar `lag_adjusted` erra de
  trimestre — é o risco que a flag existe para cobrir.
- **Painel desbalanceado é a regra:** ICON 2007+, IMOB 2008+, IFIX 2011+, FII 2019+ → **nenhuma linha
  antes do início real** (check `sem_linha_antes_do_inicio_da_serie`: **29** linhas que não existem
  em `alinhado_trimestral`), com `n` + `data_inicio` visíveis em toda tabela.
- **`strict=True` nos schemas:** nenhuma coluna ad hoc — **`vertice_extrapolado` de CA-023 não é
  coluna** do canônico (ver `tesouro.md`), e torná-la coluna é feature classe C própria. **O painel
  do Tesouro e o calendário não entram em `raw_series`** (schema próprio, 750 `series_id` fora do
  catálogo): a exclusão está no dado (`relatorio_build.json → tabelas_excluidas`).
- **O Focus também não entra em `raw_series`** (**D-k**, 5 arquivos, mesmo motivo do painel: 197
  `series_id` compostos fora do catálogo) — são **7** tabelas excluídas hoje. F-015 o lê direto de
  `data/processed/focus/`, pelo mesmo `ProcessedSeriesSchema`, e a **procedência aponta para o
  EntitySet** (`FOCUS_ANUAIS`), nunca para `FOCUS_A_SELIC_H0`. Ver `modules/focus.md`.
- **`macro_quarterly` tem grade de apoio `2001Q1..2005Q4`** para as derivadas que precisam de `T−4`
  — reexpressa a régua de F-014 com as peças públicas dela e é conferida célula a célula
  (**913 células, 0 divergências**); uma única divergência **para o build** (`ApoioDivergente`).
- **`INCLINACAO_REAL_5A_3A` não tem coluna** em `MacroQuarterlySchema` (**D-n**): F-019/F-021 leem a
  série alinhada direto. A 5a−1a é publicada com **33 nulos (39,8%)** e declarados.
- **`exigir_series` roda contra `raw_series` E contra `alinhado_trimestral`** (**D-v a**, P1-3 do
  QA-A). Rodava só contra o primeiro, e um `alinhado_trimestral` **sem** série exigida fazia o build
  de F-015 **concluir em silêncio**: a régua reexpressa em `observacoes_de_fim_de_periodo` cobria a
  ausência, `ipca_12m` saía com 83 valores não nulos e `max |dif| = 0,0`, e só o contador de células
  caía de 1.328 para 1.245 — que nenhum teste afirmava. A feature afirma "todo nível é a célula de
  F-014": a série exigida tem de estar **nos dois** artefatos.
- **`versao_build` normaliza o fim de linha** (**D-v b**, P1-4 do QA-A). Hasheava `read_bytes()`
  cru, então o mesmo commit dava `fonte_versao` diferente num checkout CRLF e num LF — quebrando o
  passo 4 do gate da classe D (dataset congelado por `sha256` + tag git) e CA-121 entre ambientes,
  **sem que uma célula de dado mudasse**. Todos os `MODULOS_*` herdam, porque todos passam por
  `versao_build`. **Resíduo:** `catalogo_sha256` (hash diagnóstico de 1 arquivo) **não** foi
  normalizado — `TODO.md §6`.

**Features:** **F-013** · **F-014** (D-h) · **F-015** · **F-016** · **F-017** · **F-018** ·
**F-029** — **todas classe C**.
