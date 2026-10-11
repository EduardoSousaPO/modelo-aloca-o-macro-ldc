# QA independente + revisão numérica — Onda 4 (F-022..F-029)

**Agente:** subagente Opus de QA (Prompt 3 / Validation Mode, `AGENTS.md §14-§15`) — **não** implementei
nada desta onda. **Data:** 2026-10-11, janela **07:10 → 07:30 (-03:00)**. **Base:** `main` @ `10e6e66`.

> ⚠️ **Alvo móvel, registrado.** O fechamento da Onda 4 e F-027 rodaram **em paralelo** a este QA.
> Às **07:11** `data/canonical/` estava sendo reescrito (`macro_quarterly*` às 07:07-07:08, F-026 às
> 06:48, figuras às 06:34, tabelas às 06:35, F-022 às 06:20). **Congelei um snapshot do canônico às
> 07:11:40** e toda a revisão numérica abaixo é sobre esse snapshot — internamente consistente.
> Às **07:17** o *working tree* já tinha 5 arquivos modificados não commitados (`heatmap_regime_ativo.py`,
> `schemas/asset_returns_quarterly.py`, `schemas/regimes.py` e 2 testes). As 2 falhas de CI (§1) são
> **consequência direta** disso e **não** de defeito numérico — ver §1.1.
> Builds de ataque rodaram **só em scratch** (`--raiz`); `data/canonical/` **não** foi reconstruído.

---

## 1. CI real (colado)

```
$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
98 files already formatted

$ uv run pytest tests/unit tests/contract -m "not network" -q      # 07:15, exit 1
tests=1933  failures=2  errors=0  skipped=7  time=103.5s
  FAIL tests/unit/test_tabela_ranking.py::test_acervo_arquivos_gravados_batem_com_o_recalculo
  FAIL tests/contract/test_metricas_regime_contract.py::test_acervo_fonte_versao_e_o_mesmo_nas_tres_tabelas

$ uv run pytest tests/e2e -q                                       # 07:28, exit 0
tests=6  failures=0  errors=0  skipped=0  time=4.7s
```

> Nota de método: `pytest ... | tail` devolve o `rc` do `tail`, **não** o do pytest — foi assim que as
> 2 falhas passaram batido numa primeira medição minha. Os números acima vêm de `--junitxml`.

### 1.1 As 2 falhas são deriva de `versao_build`, com **zero** deriva numérica (provado)

Ambas comparam o `fonte_versao`/`versao_build` **gravado no artefato** com o **recalculado agora**:
`ea2f4d31…` (em disco) × `fc5414fd…` (agora) e `dc02ba5e…` × `22040310…`. `versao_build` é o `sha256`
do **conjunto de módulos**, que inclui `packages/shared/schemas/{asset_returns_quarterly,regimes}.py`
— exatamente os arquivos que o fechamento paralelo está editando. Confirmei a causa por outro caminho:
regerei `timeline_regimes_revised.svg` em scratch e o **único** texto diferente do publicado é
`versao_build 9d557ace249f → d5de3c3bceb5`; os 3 `sha256` dos insumos são **idênticos**.
⇒ **nenhuma célula se moveu.** Consequência: a onda **só fecha** com rebuild encadeado final + re-run
destes 2 testes. Os testes estão **certos** — são detectores de artefato defasado, e detectaram.

## 2. Arquivos vs. contrato · schemas só por acréscimo

`git diff 83143db..HEAD`: 33 arquivos, +19.201/−26. **`packages/shared/schemas/` só cresceu:** 1 arquivo
**novo** (`internacional.py`, 294 l.) + 59 linhas **aditivas** em `__init__.py` (imports/`__all__`).
Nenhuma declaração de coluna existente foi alterada. O acréscimo de D-ac no *working tree*
(`@pa.parser` + `@pa.check` em 2+3 flags booleanas) também é **puro acréscimo**.

| Feature | Contrato (`TODO.md`) | Realidade | Veredito |
|---|---|---|---|
| F-022 | `apps/pipeline/analysis/metricas_regime.py` | `apps/pipeline/canonical/metricas_regime.py` | path divergente, **declarado** |
| F-023 | `apps/pipeline/analysis/figuras.py`, `tests/unit/test_heatmap.py` | `apps/analysis/figuras/heatmap_regime_ativo.py`, `test_figura_heatmap.py` | idem |
| F-024 | `apps/pipeline/analysis/tabelas.py` | `apps/analysis/tabelas/ranking_regime_atual.py` | idem |
| F-025 | `apps/pipeline/analysis/figuras.py` | `apps/analysis/figuras/timeline_regimes.py` | idem |
| F-026 | `apps/pipeline/analysis/internacional.py`, `tests/integration/test_risk_off.py` | `apps/pipeline/canonical/internacional.py`, sem `tests/integration/` | idem |
| F-028 | `docs/plans/limitacoes-comite-2026-10-14.md`, `tests/unit/test_limitacoes.py` | `docs/product/LIMITACOES-COMITE.md`, `test_limitacoes_documento.py` | idem |
| F-029 | `apps/pipeline/pipeline.py`, `tests/e2e/test_pipeline_completo.py`, `tests/integration/test_idempotencia.py` | `apps/pipeline/run.py`, `tests/e2e/test_reprodutibilidade.py`, `tests/unit/test_pipeline_run.py` | idem |

Todas as 7 divergências estão escritas no context pack da feature e são **de path, não de escopo**.
Mesmo assim são **7 linhas de `TODO.md` a ratificar** — hoje o contrato não descreve a árvore real.

## 3. Revisão numérica independente (meu código, `groupby`/numpy puros, zero import da feature)

### 3.1 F-022 — **120 células × 17 métricas reconferidas, 0 divergência**

Reconstruí a lente V1 a partir de `regimes_v1.parquet` (`status = CLASSIFICADO`) e a lente V3 a partir
de `regime_neighbors_v3.parquet` (`mahalanobis`, `k=8`, `somente_passado=False`, `restrito_pos_2016=False`),
e recalculei **todas** as 120 células de `regime_asset_metrics.parquet`:

`max abs dif` = **0,000e+00** em `n_obs`, `ret_medio`, `ret_mediana`, `ret_desvio`, `erro_padrao_media`,
`hit_ratio`, `excesso_cdi`, `hit_ratio_cdi`, `ret_real`, `sharpe_tri`, `pior_tri`, `melhor_tri`; e
**1,110e-16** em `beta_ibov` (ordem de soma em ponto flutuante). `pior_tri_quarter`/`melhor_tri_quarter`
(string) e as 2 flags (bool): **idênticos**.

**6 células-amostra** conferidas uma a uma (V1/`ESTAGFLACAO`/`SP500_BRL`, V1/`DESACELERACAO`/`UTIL`,
V1/`RECUPERACAO`/`IMOB`, V1/`EXPANSAO_INFL`/`IFIX`, V3/`INDX`, V3/`IFIX`): média, mediana, hit ratio,
excesso **por razão**, Sharpe do excesso e pior tri + data — todos exatos.

- **`n` por célula = distribuição de F-019:** `DES 13 · EST 16 · EXP 19 · REC 19` (recontado por mim no
  próprio `regimes_v1`), com as exceções de janela própria de **CA-093**: `IFIX` 17 em `EXPANSAO_INFL` e
  16 em `RECUPERACAO`. V3: `n` de 4 a 8.
- **V3 em T+1 × F-021:** `INDX 0,050430126289056007`, `ACWI_BRL 0,037762812139204904`,
  `IMAT 0,035954586119567686` — **byte-idênticos** nos três caminhos (meu cálculo ×
  `relatorio_regimes_v3.json → ranking_ativos_t_mais_1` × `regime_asset_metrics.parquet`). Idem
  `SP500_BRL`, `IFIX` (−0,055978836808139865, n=4) e `IMOB` (−0,064993743604103177, n=4).
- **Flags:** `alerta_n_baixo` = 3 (`ICON` n=6, `IFIX` n=4, `IMOB` n=4 — todos V3) e
  `conclusao_suprimida` = 2 (`IFIX`, `IMOB`). `(n<8)==alerta` e `(n<5)==suprimida` em **336/336** células
  das 3 tabelas.
- **Concordância por referência, recalculada de ponta a ponta:** 77 referências na lente, **61
  comparáveis**, **16 fora** — e as 16 são exatamente `2006Q1..2009Q3` + **`2026Q3`** (D-m).
  Distribuição do Jaccard V1 × V3: mín **0,0** · Q1 **0,0** · **mediana 0,1111** · média **0,1621** ·
  Q3 **0,2500** · máx **0,6667** · **17 de 61 zeros** · **0** iguais a 1,0. Reproduz §6.1 do pack.
- **Razão × subtração** (96 células V1, meu cálculo): média **0,0516 pp**, máx **0,2156 pp** (pack: 0,052
  / 0,216). `CDI` com excesso identicamente **0,0**.
- `data/canonical/regimes.parquet` **não existe** em disco. ✓
### 3.2 F-026 — `stress_flag`, correlações, variância mínima e identidade de moeda

- **`stress_flag` refeito pela regra declarada, do zero** (inclinação real 5a−3a de
  `data/processed/curva/INCLINACAO_REAL_5A_3A.parquet` alinhada por mim ao fim do trimestre; Δ sobre a
  variação; σ **expanding até T−1** com mínimo de 8 observações; **ou** `usdbrl_var_tri > 10%`):
  **20 de 83** trimestres, **lista idêntica** — `2008Q2 · 2008Q3 · 2008Q4 · 2011Q3 · 2011Q4 · 2012Q2 ·
  2013Q2 · 2014Q3 · 2014Q4 · 2015Q1 · 2015Q3 · 2018Q2 · 2018Q4 · 2019Q2 · 2020Q1 · 2021Q4 · 2022Q2 ·
  2024Q2 · 2024Q4 · 2025Q1`. Decomposição **7 / 11 / 2** e os **14** não avaliáveis pelo ramo 1
  (`2006Q1..2008Q1` + `2020Q3..2021Q3`) também idênticos.
- **`corr(USDBRL, IBOV)` por Pearson escrito à mão:** stress **−0,795057** (n=20) · não stress
  **−0,417495** (n=62) · janela inteira **−0,709595** (n=82) · 10 piores do IBOV **−0,625039** (n=10).
  Bate com −0,795 / −0,418 / −0,710 / −0,625.
- **Variância mínima de `ESTAGFLACAO` (cap 0,40, n=16), por caminho independente:** Ledoit-Wolf com
  **laço explícito em k** → `rho = 0,407234286` (relatório: `0,407234286`); **busca em grade** na simplex
  (passo 0,25 pp) → `var 5,07686577e-04`; **conjunto ativo + KKT resolvido à mão** →
  `{CDI 0,400000, IMAB 0,335586, IBOV 0,105269, ACWI_BRL 0,159145}`, `var 5,07681581e-04`,
  `λ = 5,427573e-04`. **`max abs dif` dos 4 pesos contra o publicado = 0,0.** Gradiente `Σw − λ`:
  **−8,769e-05** no `CDI` (no cap, sinal correto) e **±1,08e-19** nos 3 livres. As condições de primeira
  ordem fecham.
- **Retornos em T+1 após stress** (excesso por razão), recalculados: `SP500_BRL +2,30%` ·
  `IBOV +2,26%` · `ACWI_BRL +1,62%` · `IMAB +1,17%` · `USDBRL +0,32%` · `CDI 0,00%` (n=20) contra
  `+0,83 / −0,42 / +0,72 / +0,20 / −1,46 / 0,00` (n=62). Idêntico. A leitura "o dólar paga **durante**
  o stress, não depois" é sustentada pelo dado.
- **Identidade de moeda:** `(1+SP500_BRL) − (1+SP500_USD)(1+USDBRL)`, resíduo máximo **2,220e-16** em
  82 trimestres, pior em **`2008Q4`**. Idêntico ao publicado.
- **Neutralização:** `r_IBOV = −8,07%`, `r_USDBRL = +10,68%` ⇒ **x = 43,0%** (n=20). Confere.

### 3.3 F-029 — reprodutibilidade, `verify`, `freeze`, ordem

- **2 árvores independentes em scratch** (`data/processed/` copiado de `tests/fixtures/processed/`,
  `run --offline --ate build_raw_series --sem-duckdb --raiz <tmp>`): **`MANIFEST.json` byte-idêntico**,
  agregado `f9214b8e2a3ea502cc1f234cbaf8459857a5a4821fd6b0ec25bd7b3e109644fd` (3 artefatos). Bate com o
  pack. `verify` na árvore limpa: **rc 0**, `VERIFY OK`.
- **`verify` detecta** artefato ausente (`FALHA … ausente em disco` + agregado), arquivo não listado,
  e **1 célula alterada** mantendo o Parquet legível (`FALHA series_catalog.parquet: sha256 divergente`
  + agregado, **rc 1**). **Mas** ver **P1-1**: com o Parquet **corrompido** ele estoura.
- **`freeze` determinístico:** 2 execuções seguidas → `MANIFEST.json` **e** `FROZEN.txt` byte-idênticos.
  `--saida` fora de `data/` é **recusado** com mensagem acionável (rc 1).
- **Ordem das etapas** (`--listar-etapas`, modo offline): `curva → build_raw_series → alinhamento →
  macro_quarterly → asof → retornos → regimes_v1 → regimes_v1_asof → regimes_v3 → metricas_regime
  (opcional) → figuras (opcional)` — igual ao declarado.
- `run --online --so extract_sgs --raiz <tmp>` → **recusado** (rc 1). `run --offline --ate alinhamento`
  sobre `processed/` vazio → **para** na etapa, nomeia-a, lista as 10 que não rodaram e imprime o `--so`.

### 3.4 F-023/F-024/F-025 — valores plotados/tabelados, `n`, gate, determinismo

- **Tolerância 0:** `figuras/heatmap_dados.parquet` (**336 × 32**) × as 3 tabelas de F-022, nas 12
  colunas numéricas + `pior_tri_quarter` + 2 flags + `data_inicio_serie` → **0 divergências**.
  `figuras/timeline_regimes_dados.parquet` (**166 = 2 × 83**) × `regimes_v1{,_asof}` + IBOV/Selic de
  `alinhado_trimestral` → **0 divergências**. `tabelas/ranking_regime_atual.parquet` (**72**) ×
  `regime_asset_metrics{,_asof}` → **0 divergências**, ordenação desc. por `excesso_cdi` com célula vazia
  no fim nas 3 lentes.
- **`n` em toda célula:** heatmap 0/336 sem `rotulo_n` e 0 `n_obs` nulo; timeline 0 `n_obs_regime_v1`
  nulo e **0 buracos** (todo regime nulo tem `status = INDETERMINADO`); ranking 0 `n_obs` nulo.
- **Marca do gate (CA-090):** as **5** SVG publicadas carregam `ESPECIFICAÇÃO NÃO CONGELADA — não
  publicável` no texto renderizado; os 2 `.md` de F-024 e a página de F-028 também. Em scratch, com o
  ADR-001 ilegível, o módulo **falha fechado** (`especificacao tratada como NAO congelada`). ✓
- **Nada preditivo, em substância:** varri o texto **renderizado** das 5 SVG (matplotlib emite o texto
  como comentário XML; `<text>` não existe por `fonttype=path`), os 2 `.md` de F-024 e
  `LIMITACOES-COMITE.md`. Todas as ocorrências de termo preditivo estão sob negação explícita — ver
  **P2-1**.
- **Determinismo:** regerei timeline + heatmap **3 ×** em scratch → **12/12 artefatos byte-idênticos**
  entre as rodadas. `timeline_regimes_dados.parquet` saiu **`362f87373a0db2e9`**, igual ao publicado;
  `markdown_ranking`/`markdown_concordancia` de F-024 idênticos em 2 construções. As imagens diferem do
  publicado **somente** no `versao_build` do rodapé (§1.1) — figura reprodutível, selo defasado.
- **3+ canários até o bruto** (`AGENTS.md §15.9`), figura → `alinhado_trimestral` → `raw_series`:
  `2008Q4 IBOV 37.550,31` · `2015Q4 IBOV 43.349,96` · `2026Q3 IBOV 186.340,46` · `2026Q3 Selic 13,75`
  — **idênticos** nos 3 níveis, fontes `B3_API` / `BCB_SGS`.

### 3.5 F-028 — números citados × relatórios

Conferidos na página e no `relatorio_*.json` da mesma rodada: **1.963 linhas / 24 ativos / 83
trimestres** (`relatorio_retornos`) · **19 · 19 · 16 · 13 + 16 indeterminados**
(`relatorio_regimes_v1 → distribuicao.por_grupo`) · **22 de 66 = 33,33%** (`→ divergencia_asof_vs_revised`,
`pct_que_trocam = 0,333333`) · **2.552 células com 0 violações** (`relatorio_asof → anti_look_ahead`) ·
**2,54 pp** de erro-padrão do `INDX` (`relatorio_regimes_v3`) · **215 células de 4.038 com ffill em 11
séries** (`relatorio_alinhamento → decisao_d_h`). Os 8 blocos existem; **249 linhas** (faixa 150-250).
Os 2 números fora de relatório (erros-padrão de referência e o preço do ANBIMA Feed) estão **declarados
como tais**. Aritmética refeita: `12%/√19 = 2,75 → 2,8` · `12%/√13 = 3,33 → 3,3` · `12%/√8 = 4,24 → 4,2`.
Nenhuma afirmação preditiva e nenhum número sem fonte.

## 4. Ataque (Validation Mode) — o que cedeu

| # | Vetor | Resultado |
|---|---|---|
| 1 | `regimes.parquet` não gravado (D-r) | **Justificativa confirmada no dado:** `regime_v1` é `nullable=False` e 16/83 são `INDETERMINADO`. F-026 resolveu `stress_flag`; o bloqueio de `regime_v1` **permanece** e não é de F-026. Decisão correta. Mas `relatorio_metricas.json → juncao_regimes` (06:20) ainda declara `stress_flag` bloqueado → **P2-5** |
| 2 | pandera `bool` + `nullable=False` + `coerce` | **Achado de F-022 §8.3 reproduzido em schema mínimo:** `flag=None` **passa** e vira `False`; `flag=NaN` **passa** e vira `True`. Gravíssimo e real. O acréscimo de D-ac no working tree **fecha**: `RegimeAssetMetricsSchema` com `alerta_n_baixo=None` agora **recusa** (`SchemaError` na coerção) |
| 3 | Variância mínima fora da v1 (Anti-SPEC) | Tabela **de fato isolada**: `internacional_pesos.parquet` separado, `especificacao_congelada = False` em **todas** as 624 linhas, **0** colunas de retorno esperado/recomendação/alvo. **Mas** o arquivo mora em `data/canonical/` e o `MANIFEST`/`freeze` **não têm noção de "não publicável"** → **P1-3** |
| 4 | `SP500_USD` no heatmap | 14 células, marcadas com `‡`, **mas** sob o cabeçalho de grupo **"INTERNACIONAL (EM BRL)"**, e o tooltip da célula não repete a ressalva → **P2-2** |
| 5 | Slug `v3_t1` | **Já resolvido no working tree:** o CLI agora expõe `--vista {v1_revised,v1_asof,horizonte_cruzado,todas}` e grava `heatmap_horizonte_cruzado.*`. Artefatos `heatmap_v3_t1.*` em disco são **defasados** e precisam ser removidos no rebuild |
| 6 | `erro_padrao_media` nominal × excesso (F-024) | **Declarado o suficiente.** O `.md` tem 3 parágrafos nomeando `desvio(ret_tri)/√n`, dizendo que `\|excesso\|/ep` é **semáforo** e não estatística de teste, e que para o `CDI` e os índices que o seguem **subestima** a distância do zero. Travado por teste de acervo |
| 7 | Etapa opcional pulada com aviso | **Não esconde falha de cálculo:** `modulo_disponivel` usa `find_spec` (sem import), e exceção **dentro** de `construir()` sobe. `EtapaNaoChamavel` só dispara sem `construir`/`main`. **Mas** o `rc` é **0** com etapa pulada ⇒ "um comando" pode sair incompleto e verde — agravado por **P1-2** |
| 8 | `ldc.duckdb` não determinístico | Substituí por lixo: `verify` **aprova** com linha `INFO` (decisão (b), declarada, `sha256: null`, fora do agregado). Aceito — mas o pacote classe D deve ser congelado com `--sem-duckdb` |
| 9 | F-028 preditivo / sem fonte | Nada encontrado (§3.5) |

## 5. Achados

**P0 — nenhum.**

**P1-1 · `verify` estoura em vez de reportar Parquet corrompido** (F-029). Reprodução (≤10 linhas):

```python
# em árvore de scratch já construída e congelada:
import pathlib
p = pathlib.Path("<raiz>/data/canonical/series_catalog.parquet")
b = bytearray(p.read_bytes()); b[500] ^= 0x01; p.write_bytes(bytes(b))
# $ python -m apps.pipeline verify --raiz <raiz>
# -> OSError: Unexpected end of stream  (traceback cru, rc 1)
# esperado: "FALHA series_catalog.parquet: sha256 divergente ..." + agregado
```
Causa: `inventariar` (`run.py:602`) chama `_perfil_do_parquet` (`run.py:555` → `pd.read_parquet`) **antes**
de qualquer comparação de hash, sem tratamento. Um `*.parquet` que não é Parquet (3 bytes) dá
`ArrowInvalid`. Efeito: no cenário que mais importa — bit-rot / arquivo truncado — o `verify` **não nomeia
o arquivo nem o agregado**, e a saída é um traceback (encosta em Anti-SPEC §10.4.26). Correção ≤ 10 linhas
(`try/except Exception: perfil = {}` e deixar a conferência de hash reportar). **Não corrigi.**
**P1-2 · `run` não reconstrói a camada canônica completa** (F-029 / CA-118). Não existe etapa para
`apps.pipeline.canonical.internacional` (F-026) nem para a camada `apps/analysis/tabelas/` (F-024) — a
etapa `figuras` varre só `apps/analysis/figuras/`. Medido: `MANIFEST.json` tem **30** artefatos e o
diretório tem **44**; `verify` no repo reprova com **14** `nao listado no manifesto`
(3 de F-026, 5 do heatmap, 6 de `tabelas/`). Hoje "um comando" entrega ~2/3 do canônico com `rc = 0`.

**P1-3 · o não publicável viaja no dataset congelado.** `internacional_pesos.parquet` (Anti-SPEC
§10.3.16/§10.5 → F-035) está em `data/canonical/`; o `MANIFEST`/`freeze` cobrem o diretório
**recursivamente** e não têm campo de publicabilidade. Depois do rebuild, o pacote classe D de F-031
conterá fisicamente a tabela de pesos com o selo só dentro das linhas. Precisa de decisão humana
(`AGENTS.md §9`): subdiretório fora do manifesto, exclusão explícita no `freeze`, ou autorização escrita.

**P1-4 · 2 testes de acervo vermelhos** (§1/§1.1) — bloqueiam o merge até o rebuild encadeado final +
re-run. Sem deriva numérica.

**P2-1 · três guardas de linguagem, nenhuma única.** A de F-024 (`conferir_linguagem_descritiva`, a única
reutilizável e executável) **reprova** os textos das outras features: as 5 figuras por "Nada aqui é
**projeção**" e `LIMITACOES-COMITE.md` por `nunca "quanto vai render"`, "**Backtest**, otimização ou
fronteira eficiente — … não está neste pacote" e "a **recomendação** é do Alexandre". Todas são negações
legítimas; o defeito é a janela de negação da guarda (só reconhece `não`/`nunca` adjacentes). Unificar
numa guarda só e incluir `nada ... é` / `nenhum(a)` / cabeçalho "O que **não** está neste pacote".

**P2-2 · `SP500_USD` sob rótulo de grupo "INTERNACIONAL (EM BRL)"** no heatmap. A linha é dado real,
está marcada com `‡` e tem nota de rodapé, mas o **cabeçalho do grupo afirma BRL** para uma série em USD
e o tooltip da célula não ressalva. Decisão do Edu (encosta em Anti-SPEC §10.2.12): manter marcada,
mover para grupo próprio, ou tirar da figura do Comitê.

**P2-3 · 7 divergências de path contrato × árvore real** (§2) — ratificação de 7 linhas no `TODO.md`.

**P2-4 · `TODO.md` F-028 cita "~2,7 pp/tri com n = 20"**; **nenhum** regime tem n = 20 (máximo 19). A
página corrigiu para 2,8/3,3/4,2 com n = 19/13/8 e a aritmética fecha. Alinhar o texto do contrato.

**P2-5 · relatórios defasados entre si.** `relatorio_metricas.json` (06:20) declara `stress_flag`
bloqueado; `relatorio_internacional.json` (06:48) declara resolvido. O rebuild encadeado resolve — mas
é o tipo de par que, lido fora de ordem, vira afirmação contraditória no Comitê.

**P2-6 · `ldc.duckdb`:** substituição por lixo passa no `verify` (declarado). Congelar com `--sem-duckdb`.

## 6. Matriz `CA | teste | tipo | status | evidência`

| Feature | CA | Teste / verificação do QA | Tipo | Status | Evidência |
|---|---|---|---|---|---|
| F-022 | CA-092/093 | média, mediana, `ep = σ/√n`, `n_obs` por janela própria | revisão numérica | ✅ | 120 células, dif **0,0**; `IFIX` 17/16 × 19; V3 `ICON` 6, `IFIX`/`IMOB` 4 |
| F-022 | CA-094 | Sharpe trimestral, anualização declarada | leitura + unit | ✅ | `anualizacao.aplicada_na_coluna = false` |
| F-022 | CA-095 (pré) / CA-108/109 | célula sem `n` impossível; limiares 8/5 | contract neg. + num. | ✅ | 336/336 com `n` e flags coerentes; 3 alertas, 2 supressões |
| F-022 | CA-069 / CA-102 | excesso por razão; T+1 da V3 | revisão numérica | ✅ | máx **0,2156 pp** × subtração; 6 ativos byte-idênticos a F-021 |
| F-022 | CA-103 | divergência reportada como distribuição | revisão numérica | ✅ | 61 comparáveis, **mediana 0,1111**, 17 zeros |
| F-022 | CA-088/D-r | `regimes.parquet` bloqueado | contract + acervo | ✅ | ausente em disco; bloqueio confirmado no dado |
| F-022 | CA-121 | idempotência | acervo | ⚠️ | §1.1 (`versao_build` defasado) |
| F-023 | CA-095/096 | `n` em toda célula; hachura `n < 8`; `CDI` ≡ 0 | QA próprio | ✅ | 0/336 sem `rotulo_n`; flags = limiares; `max abs = 0,0` |
| F-023 | CA-097 / CA-090 | rodapé com `data_inicio` + métrica; marca do gate | leitura do SVG | ✅ | texto renderizado extraído; 3/3 heatmaps |
| F-024 | CA-098/099 | 3 lentes + 8 vizinhos + ranking com `n`; `n < 5` sem conclusão | QA próprio | ✅ | 72 linhas, 0 `n` nulo; linha mantida com flag |
| F-024 | CA-103 / — | divergência reportada; valores = parquet de origem | QA próprio, tol. 0 | ✅ | Spearman −0,748; 0 divergências |
| F-025 | CA-100 / CA-090 / §15.9 | 83 tri. sem buraco; legenda; gate; canários | QA próprio | ✅ | 166 linhas, 0 buracos; 2/2 figuras; 4 valores até o bruto |
| F-026 | CA-104/105 | mesmo arcabouço; `corr` por bloco com `n` | QA próprio, numpy | ✅ | retorno confere com F-022; −0,795057/−0,417495/−0,709595/−0,625039 |
| F-026 | CA-106/107 | `stress_flag` pela disjunção; saída é faixa | regra refeita | ✅ | 20/83, ramos 7/11/2; piso + banda + truncamento |
| F-026 | — / CA-090 | variância mínima; gate | LW + grade + KKT | ✅ | `rho` e 4 pesos com dif **0,0**, KKT fecha; `congelada = False` |
| F-026 | Anti-SPEC §10.5 | pesos fora da v1 | QA próprio | ⚠️ | isolada, mas entra no manifesto — **P1-3** |
| F-028 | CA-112 | 8 blocos + números dos relatórios | QA próprio | ✅ | 6 números conferidos, 249 linhas |
| F-029 | CA-118 | um comando → canônico completo | build de ataque | ❌ | **P1-2**: sem etapa de F-026/F-024 |
| F-029 | CA-119/122 | relatório de saída; revisão retroativa | leitura | ⚠️ | tempo a frio não medido; CA-122 não observável (1 safra) |
| F-029 | CA-121 | 2 execuções → mesmo hash | 2 árvores em scratch | ✅ | `MANIFEST` byte-idêntico, `f9214b8e…` |
| F-029 | — | `verify` / `freeze` | ataque | ⚠️ | pega ausente/extra/célula alterada; `freeze` determinístico; **P1-1** |

## 7. Veredito por feature

> ADR-001/002/003 em **Proposta** ⇒ **gate conhecido**: nada desta onda é publicável (CA-090). Não conta
> como defeito das features; conta no gate da classe D (`AGENTS.md §14`, itens 2 e 3).

| Feature | Classe | Veredito | Condições |
|---|---|---|---|
| **F-022** | C | **APROVADO com condição** | 120 células × 17 métricas reconferidas com dif 0,0; concordância reproduzida. Condição: rebuild encadeado final para o teste de `fonte_versao` ficar verde (**P1-4**) e para `juncao_regimes` deixar de declarar `stress_flag` bloqueado (**P2-5**) |
| **F-023** | B | **APROVADO com condição** | 0 divergência contra a origem, `n` em 336/336, gate marcado, 3 rodadas idênticas. Condições: concluir o rename `v3_t1 → horizonte_cruzado` e **apagar** os `heatmap_v3_t1.*` defasados; decidir `SP500_USD` (**P2-2**) |
| **F-024** | B | **APROVADO com condição** | 72 linhas com dif 0,0, ordenação correta, `ep` nominal bem declarado, markdown determinístico. Condição: **P1-4** (o teste vermelho é desta feature) |
| **F-025** | B | **APROVADO** | 166 linhas com dif 0,0, 0 buracos, 4 canários até o bruto, determinismo medido. Nada pendente |
| **F-026** | C | **MUDANÇAS_SOLICITADAS** | A matemática é impecável (stress, correlações, LW, KKT, identidade de moeda — tudo reproduzido). Mas: **P1-2** (não há etapa no orquestrador, o artefato não se reconstrói com um comando) e **P1-3** (os pesos não publicáveis entram no dataset congelado). Ambos exigem decisão/ação, não recálculo |
| **F-028** | B | **APROVADO** | 6 números conferidos nos relatórios, 8 blocos, 249 linhas, zero afirmação preditiva. Pendências são de ratificação (**P2-4**) e da leitura do Edu |
| **F-029** | C | **MUDANÇAS_SOLICITADAS** | Idempotência, `freeze` e a ordem das etapas provados em scratch. Mas **P1-1** (`verify` estoura em Parquet corrompido — exatamente o caso que o selo existe para pegar) e **P1-2** (CA-118 não cumprido pós-Onda 4) |

**Para fechar a onda, na ordem:** (1) corrigir `_perfil_do_parquet` (**P1-1**, ≤10 linhas) e acrescentar as
etapas `internacional` e `tabelas` ao `run.py` (**P1-2**); (2) decidir **P1-3** com o Edu; (3) rebuild
encadeado completo + `freeze` novo + re-run dos 2 testes (**P1-4**); (4) ratificar as 7 linhas de path e
os P2 restantes. Nada aqui vai ao Comitê antes dos 8 itens de `AGENTS.md §14`.
