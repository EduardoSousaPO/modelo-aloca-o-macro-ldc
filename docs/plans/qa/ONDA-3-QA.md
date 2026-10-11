# QA independente + revisão numérica — Onda 3, parte 1 (F-018 · F-019 · F-021 + fechamento)

- **Subagente:** QA independente (classe C), Opus. **Não implementou nada** desta onda.
- **Commit avaliado:** `83143db` (sobre `53af94e`, base de comparação `fcdfaeb`) · branch `main` · 2026-10-11
- **Modo:** Prompt 3 / Validation Mode (`AGENTS.md §15`), sem rede, `uv run`
- **Método da revisão numérica:** scripts próprios em scratch, lendo **só Parquet/JSON/calendário**.
  **Nenhum módulo sob revisão foi importado** — `asof.py`, `regimes_v1.py`, `regimes_v3.py` e
  `macro_quarterly.py` não aparecem em nenhum `import` dos scripts de conferência.
  `data/canonical/` **não foi reconstruído** em disco.

## 0. Veredito

| Feature | Veredito | Observação |
|---|---|---|
| **F-018** `canonical/asof.py` | **APROVADO** | reconstrução independente bate **bit a bit**; CA-074 acionado é **achado**, não defeito |
| **F-019** `regimes_v1.py` | **APROVADO** | 83 × 2 materializações reclassificadas sem divergência; 2 afirmações de doc erradas (P2) |
| **F-021** `regimes_v3.py` | **MUDANÇAS_SOLICITADAS** | números corretos; **3 P1 de declaração** (contrato espelho errado, Jaccard 1,0 vácuo, safra `revised`) |
| **Fechamento** (D-s, D-t, hash sem CRLF) | **MUDANÇAS_SOLICITADAS** | D-s correto e confirmado; **justificativa de D-t é factualmente errada** (P1) |

**Gate de publicação:** `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA` em todas as 83 linhas das duas
materializações e em `gate_de_publicacao.publicavel = False` da V3. ADR-001 em `Proposta` está
corretamente lido do disco com falha fechada. Isso é **gate conhecido**, não defeito.

---

## 1. CI real (executado nesta máquina)

```
$ uv run ruff check .
All checks passed!
$ uv run ruff format --check .
76 files already formatted
$ uv run pytest -m "not network"
==== 1416 passed, 6 skipped, 17 deselected, 1 xfailed in 80.99s (0:01:20) =====
```

Por pasta: `tests/unit` e `tests/contract` verdes. Em `83143db`, **`tests/integration/` e
`tests/e2e/` estão VAZIOS**.

**P1-4 — o nível de CI da classe C não existe no CI.** `.github/workflows/ci.yml` mantém `n2-integration`
e `n3-e2e-repro` **comentados**. `AGENTS.md §6` diz que descomentá-los "é parte da feature que os cria"
e `tests/contract` já existe. Para classe C, N2 é obrigatório; para C crítica/D, N3
(**duas execuções → mesmo `sha256`**) também. Hoje toda a evidência de N2 é **local** e a de N3
**não existe**. Sem rebuild, conferi o possível: os **7 `sha256`** publicados nos relatórios batem
com os bytes em disco — mas isso é 1 execução, não 2.

## 2. Arquivos vs. contrato; schemas só por acréscimo

`git diff --stat fcdfaeb..HEAD`: 38 arquivos, +11.935/−2.736. Arquivos de código **dentro** dos
Feature Contracts reais (paths sancionados em **D-x**): `canonical/asof.py`, `canonical/regimes_v1.py`,
`canonical/regimes_v3.py`, `canonical/macro_quarterly.py`, `canonical/build_raw_series.py`, os 6
arquivos de teste, `schemas/{regimes,macro_quarterly,__init__}.py`.

**Schemas existentes: acréscimo puro, confirmado por diff.** `regimes.py` `+357/−0`, tudo **depois**
da linha 166 (`RegimeNeighborsSchema`), nenhuma linha anterior tocada. `macro_quarterly.py` `+38/−0`,
com `MacroQuarterlyAsofProvenanceSchema` como **subclasse** (+ `date_obs`, `lag_dias`).
`__init__.py` `+30/−1` — a única remoção é **1 linha de docstring**, não código.

**Fora dos 3 contratos (P2-6):** `canonical/retornos.py` (+14 L, texto de limitação do CDI) e
`README.md` — sancionados em **D-v (c)**/**D-w**, mas sem o registro do fluxo de `AGENTS.md §18` em
nenhum dos 3 Feature Contracts. `docs/wiki/context/F-013..F-017.md` apagados (−2.363 L): legítimo
(context pack vive "até o QA aprovar"), com `log-archive-2026-10.md` criado — o rastro só existe no git.

## 3. Revisão numérica independente

### (a) F-018 — reconstrução da `asof` célula a célula

Reconstruí a régua do zero: calendário ANBIMA → `quarter_end` = último dia útil (**0 divergências**
contra `alinhado_trimestral`); grade estendida 2001Q1–2026Q3; nível por `searchsorted` sobre
`date <= quarter_end − lag`; frescor `5 + passo(freq)`; média de 3 meses do IBC-Br e acumulação
geométrica do IPCA deslocadas pela divulgação do **último mês do trimestre de origem**; derivadas
recalculadas. `lag_divulgacao_dias` **do catálogo** (PIB 60 · IBC-Br 45 · IPCA 10 · Focus 0).

| coluna | `pib_yoy` | `ibcbr_yoy` | `ibcbr_gap` | `ipca_12m` | `ipca_tri` | `focus_ipca_12m` |
|---|---|---|---|---|---|---|
| células divergentes (83) | **0** | **0** | **0** (16 nulos nos dois) | **0** | **0** | **0** (= `revised`, lag 0) |
| `max abs dif` | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 | 0,0 |

**Controle:** a mesma reconstrução com lag desligado reproduz `macro_quarterly.parquet` (`revised`)
nas 5 colunas com **0 divergências** — então a única diferença entre as duas materializações é a
defasagem, e não um caminho de código diferente.

**Anti-look-ahead (CA-072/CA-010), provado no Parquet publicado:** juntei
`macro_quarterly_asof_provenance` (2.552 linhas, **todas** com `date_obs`) com o `quarter_end` que
eu mesmo calculei: **0 células com `date_obs + lag_dias > quarter_end`**. `lag_dias` nunca é menor
que o do catálogo; as 166 linhas em que difere são `surpresa_ipca`/`surpresa_pib`, onde o módulo
publica o **máximo** entre os insumos (10 e 60) em vez do 0 do Focus — conservador e correto.

**Canários:** `pib_yoy` asof 2010Q1 = **5,329431** = `revised` 2009Q4 (idem, `date_obs` 2009-12-31);
`ipca_12m` asof 2026Q3 = **4,22** = IPCA 12m de **ago/2026** (`revised` = 4,58, de setembro);
`focus_ipca_12m` idêntica em 83/83. Todos batem.

### (b) F-019 — reclassificação pela tabela de verdade do ADR-001

Reimplementei a classificação (quadrantes + desempate `== limiar` exato herdando o sinal do
**mesmo** eixo em T−1) e rodei sobre `macro_quarterly` e `macro_quarterly_asof`:

**0/83 divergências em cada materialização**, em rótulo, `status`, `motivo_indeterminado`,
`desempate_aplicado` e nos dois sinais de eixo.

- **Distribuição `revised`: REC 19 · EXP 19 · EST 16 · DES 13** + 16 `INDETERMINADO` — bate.
  `asof`: EXP 21 · REC 17 · EST 16 · DES 13.
- **16 indeterminados == exatamente os nulos de `ibcbr_gap`** nas duas materializações (`ipca_12m_delta`
  tem **0** nulos). Todos `GAP_AUSENTE`.
- `g_score`/`pi_score` são a célula de `macro_quarterly` **bit a bit**; `n_obs_regime_v1` == contagem
  do grupo em 83/83; `especificacao_congelada = False` em **83/83** nas duas; `lag_adjusted` homogêneo.
- **CA-073/074:** 66 comparáveis, **22 trocam = 33,333%** — reproduzido independentemente, igual ao
  publicado. O limiar de 25% é ultrapassado: **CA-074 acionado**, texto presente, H-03 cai.
- **Sensibilidade ±0,1 pp:** `revised` 1 trimestre (1,20%) em cada direção (`2013Q4` / `2009Q4`);
  `asof` 4 (4,82%) em `+0,1` e 1 em `−0,1`. Idênticas às publicadas.

### (c) F-021 — z-score, Ledoit-Wolf, distâncias e ranking em numpy puro

Reconstruí a matriz 5 × 77 do zero (4 colunas de `macro_quarterly` + `INCLINACAO_REAL_5A_3A` lida
de `raw_series` pela régua de F-014 que eu mesmo escrevi):

- **Cobertura: 77 de 83** trimestres com vetor completo — e os 6 ausentes são exatamente os
  declarados (2020Q3–2021Q2 por `z_inclinacao_real_5a_3a`; 2023Q1–Q2 por `z_juro_real_exante`).
- **Parâmetros do z-score** (média/desvio, `ddof=1`, n=77): batem nas 5 features até a 12ª casa.
- **Ledoit-Wolf pela definição, com laço explícito sobre `k`** (sem a identidade algébrica usada no
  módulo): `rho = 0,2598739074018101` contra `0,25987390740181016` publicado — igual a `1e-16`.
  `cond(S) = 8,2611 → cond(Σ) = 3,9747`, idênticos.
- **8 distâncias de 2026Q3** (Mahalanobis, `Σ⁻¹` por `inv`, exclusão ±2): ordem e valor **idênticos
  nas 8**, até `1e-12` — `2006Q3 (0,961632) · 2006Q4 (0,983195) · 2006Q1 (1,324948) ·
  2024Q3 (1,348194) · 2014Q4 (1,409745) · 2007Q1 (1,419520) · 2024Q2 (1,504094) · 2014Q3 (1,506140)`.
- **Euclidiana:** meu top-8 idêntico ao publicado, `max abs dif` de distância `2,2e-16`.
- **Exclusão ±2:** em **todas as 9.692 linhas** a distância temporal mínima é **3**; 0 violações.
  `somente_passado` nunca traz vizinho `>= ref` (0 linhas). `rank <= n_vizinhos` sempre.
- **Ranking em T+1 por `groupby` independente** sobre `asset_returns_quarterly` nos 8 `T+1`
  (`2006Q2, 2006Q4, 2007Q1, 2007Q2, 2014Q4, 2015Q1, 2024Q3, 2024Q4`):
  `INDX 0,050430 · ACWI_BRL 0,037763 · IMAT 0,035955` (n=8, desvios 0,0718/0,0833/0,1047) —
  **iguais aos publicados**. **Sanity do CDI: `ret_excesso_cdi` = 0,0 exato** (média, mediana e
  desvio) em todos os 8 trimestres e `max |·| = 0,0` nas 83 linhas do ativo.
- **Rótulo V1 de anotação:** 0 divergências contra `regimes_v1.parquet`. **`n_vizinhos < k_usado`**
  em 208 linhas, todas na lente `somente_passado & pos2016` — declarado, nunca preenchido.
  **Contagem total:** `(77+33+58+30)·2·25 − 208 = 9.692` linhas. Fecha.

### (d) D-s — IBC-Br como média do trimestre

Recalculei de `raw_series` (SGS 24364, 271 obs, jan/2004–jul/2026): média aritmética dos 3 meses na
janela `(fim civil T−1, fim civil T]`, exigindo 3 observações.

- `ibcbr_yoy` e `ibcbr_gap` reconstruídos batem `macro_quarterly.parquet` **em 83/83** (`allclose`
  exato, mesmos nulos).
- Contra a régua antiga (fim de período): `max abs dif` **4,2646 pp** em `ibcbr_yoy` e **4,3064 pp**
  no hiato; **7 trimestres trocam o sinal do gap** — e são **exatamente**
  `2013Q2 · 2013Q3 · 2013Q4 · 2020Q1 · 2023Q3 · 2024Q1 · 2025Q2`, os 7 declarados.
- `2026Q3` fica nulo porque o trimestre tem **1 de 3** meses (IBC-Br vai até jul/2026) — correto,
  nenhuma média parcial.

### (e) D-t — ciclo Selic com desigualdade não estrita

Recalculei `ciclo_selic` de `selic_meta_delta`: **CORTE 34 · NEUTRO 23 · ALTA 26**, 0 sem delta —
bate o publicado. `2008Q4 = NEUTRO` (Δ = 0,00) ✓. Dos 23 `NEUTRO`, **23 têm Δ = 0 exato** ✓.
Com a desigualdade estrita: CORTE 29 · NEUTRO 30 · ALTA 24; os 7 trimestres com `|Δ| = 0,25` exato
são `2011Q3 · 2012Q4 · 2014Q2 · 2020Q3 · 2024Q2 · 2024Q3 · 2026Q1`.

> **P1-3 — a justificativa de D-t está factualmente errada.** `2024Q2` é `CORTE` (Δ = **−0,25**,
> 10,75 → 10,50 em mai/2024), mas **`2024Q3` é `ALTA`** (Δ = **+0,25**, 10,50 → 10,75 em set/2024 —
> a **alta** que abriu o ciclo de aperto). O *dado* está certo; o *texto* chama os dois de "cortes
> reais de 25 bps do Copom" em **3 lugares**: `macro_quarterly.py` (docstring de `ciclo_selic`),
> `relatorio_macro.json → ciclo_selic.decisao` e `TODO.md §4` (linha **D-t** da tabela de aceites).
> **D-t é uma decisão que aguarda ratificação do Edu e muda número publicado** — ele vai ler uma
> premissa errada. A decisão em si continua defensável (25 bps é o menor passo do Copom, **em
> qualquer direção**), só a frase precisa trocar. **Não corrigi** (≤ 10 linhas, mas é doc em arquivo
> do orquestrador). Reprodução: `macro_quarterly.parquet → selic_meta_delta['2024Q3'] == +0.25`.

> **P2-5** — a distribuição 34/23/26 **não** implementa CA-082 (pausa dentro de ciclo de corte conta
> como `CORTE`). Isso é F-020, mas o número já está publicado em `relatorio_macro.json` e **vai
> mudar** quando F-020 aplicar a persistência. Declarar.

### Fechamento — hash sem CRLF (D-v b)

`normalizar_fim_de_linha` (`\r\n`/`\r` → `\n`) entra em `versao_build` antes do `sha256`, e todos os
`MODULOS_*` passam por lá. Confirmado: é a única mudança em `build_raw_series.py` fora de docstring,
e `+25/−2` linhas. Efeito declarado (toda a camada mudou `fonte_versao` uma vez, sem mudança de dado).

## 4. Ataque (Validation Mode §15)

| Vetor de ataque | Resultado |
|---|---|
| **Look-ahead escondido na V3 — a covariância usa T?** | **Usa até T inclusive**, não T−1: `montar_candidatura` faz `ate = max(q <= quarter_ref)` e `ledoit_wolf` roda em `completos <= quarter_ref`. **Não é defeito**: o contrato (`metodologia §2`, princípio 4) exige "expanding window", e janela expanding que termina em T inclui T. **Provei**: perturbei **todo** o futuro de 2019Q4 (`×7,3 + 100`) e o z de T e o `rho` ficaram **idênticos ao bit**. Controle: em `amostra_completa` o z de T **muda** — como deve. |
| **`MIN_OBS = 20` nos primeiros trimestres** | `somente_passado` só para **58** referências, a partir de **2010Q4** (histórico = 20); as **19** de 2006Q1–2010Q3 são omitidas com motivo `menos_de_20_trimestres_ate_T`, declarado em `cobertura`. Correto e sem silêncio. |
| **Adjacentes ±2 nas duas direções** | 0 violações em 9.692 linhas (mínimo = 3). Simetria **mais estrita** que CA-085 e declarada em `exclusao_de_vizinhanca.simetrica`. |
| **`k = 8` com menos candidatos** | 208 linhas com `n_vizinhos < k_usado`, todas na lente mais restrita, com `n_vizinhos` e `alerta_n_baixo` na linha. Nenhum preenchimento. |
| **`regime_v1_neighbor` não-nulo elimina 4 dos 8 vizinhos (D-u)** | **Confirmado**: contrato = `2024Q3 · 2014Q4 · 2024Q2 · 2014Q3 · 2025Q3 · 2024Q1 · 2014Q1 · 2022Q4`; em comum 4, **Jaccard 0,333**; os 4 perdidos são exatamente os sem rótulo V1. **Documentado** em `CONTRACTS.md §5.2a`, no docstring do schema, em `relatorio_regimes_v3.json` e em `TODO.md §6`, com encaminhamento. |
| **`asof` com `vintage` único degenera — declarado?** | **Sim**: `limitacoes.vintage_unico` diz que a perna de revisão é **degenerada** e que o número é um **piso** do look-ahead. Confere: 0 de 62 séries com mais de um `vintage`. |
| **Desempate `== 0` exato — ocorre?** | **1 vez em dado real**: `regimes_v1_asof` 2007Q1, `ipca_12m_delta = 0,00` exato. Ver **P2-1**. |
| **Proxy de F-018 vs. oficial de F-019 — mesmos 22/66?** | **Sim, e os mesmos trimestres.** 66 comparáveis / 22 trocas / 33,3333% nos dois; `set(proxy) == set(oficial)`. A ressalva de `limitacoes.quadrante_e_proxy` é correta e, nesta rodada, inócua. |
| **Idempotência · unidade · buracos** | 7 `sha256` publicados == disco (1 execução, P1-4). `ret_excesso_cdi` por **razão**, CDI = 0,0 exato (teste de escala). 16 nulos de `ibcbr_gap`, 33 de `curva_real_1a`, 3 colunas 100% nulas — todas com motivo; `termos_troca_yoy` **cortada** da V3 em vez de imputada. |

### P1 de declaração em F-021

> **P1-1 — `CONTRACTS.md §5.2a` descreve colunas que NÃO existem.** O texto diz que
> `RegimeNeighborsV3Schema` tem "as de `RegimeNeighborsSchema` mais `quarter_t_mais_1`,
> `somente_passado`, `status_regime_v1_neighbor`, **`rho_shrinkage`**, **as 5 features em unidade
> original**". No schema e no Parquet (21 colunas) **não há `rho_shrinkage` e não há nenhuma coluna
> `z_*`**. O que existe no lugar: `n_vizinhos`, `features_usadas`, `janela_padronizacao`,
> `alerta_n_baixo`, `especificacao_congelada`, `versao_especificacao`, `lag_adjusted`. `CONTRACTS.md`
> é o **espelho legível dos schemas** (`AGENTS.md §3`) e **F-022 está sendo implementada agora
> lendo este parágrafo** — quem confiar nele vai buscar a feature do vizinho numa coluna inexistente.
> Reprodução: `set(pd.read_parquet('data/canonical/regime_neighbors_v3.parquet').columns)`.

> **P1-2 — "a variante sem nenhum look-ahead dá a mesma lista (Jaccard 1,0)" é VÁCUO.** O número é
> medido **só em 2026Q3**, que é o **último** trimestre da janela: não existe futuro para a variante
> descritiva escolher, então as duas lentes coincidem **por construção**. Medi o Jaccard
> `somente_passado` × descritiva nas **58** referências que têm as duas lentes: **mediana 0,455 ·
> média 0,461 · p25 0,231 · mínimo 0,000**, e **só 7 de 58** dão 1,0 (2011Q3 = **0,000**,
> 2012Q1 = 0,000, 2015Q4 = 0,143, 2024Q4 = 0,333). E **2.751 das 5.500 linhas (50,0%)** da variante
> descritiva têm vizinho **no futuro** da referência.
> `TODO.md §F-021` chama o 1,0 de "**o achado mais forte da feature**" e `CONTRACTS.md §5.2a`
> repete — é o oposto: a lente descritiva muda o conjunto de vizinhos em ~55% dos casos, e isso
> precisa ser requalificado antes de ir ao slide. O **dado** está certo; a **leitura** não.

> **P1-5 — a V3 roda sobre `revised`, e 1 das 5 features não era conhecida no fim do trimestre.**
> `LAG_ADJUSTED = False` nas 9.692 linhas (declarado), mas o docstring de
> `JANELA_EXPANDING`/`somente_passado` vende a variante como "**sem nenhum caminho de look-ahead**".
> Medi: `focus_pib_ano`, `juro_real_exante` e `usdbrl_var_12m` são idênticas em `revised` e `asof`
> (lag 0, 0/83), mas **`ipca_12m_delta` difere em 83/83** (`max abs dif` 1,98 pp); em 2026Q3,
> `revised = −0,06` contra `asof = −0,50`. `somente_passado` elimina look-ahead de **seleção** e de
> **padronização**, **não de safra** — enquadrar como tal, ou rodar a V3 também sobre `..._asof`.

### P2

- **P2-1 — "0 desempates na rodada real" é falso.** `TODO.md §F-019` e `CONTRACTS.md §5.1a` afirmam
  "nenhum eixo é exatamente 0 nos 83, então CA-079 é hoje só uma regra de borda coberta por teste
  sintético". `regimes_v1_asof.parquet` tem **1** desempate real (2007Q1, `pi_score = 0,00` exato) e
  o próprio relatório publica `desempates_aplicados: 1`. E o desempate caiu no eixo de **inflação**,
  enquanto **CA-079 fala só de `g_T`** — a extensão ao eixo `pi` é deliberada (`CONTRACTS.md §5.1a`:
  "herda o sinal **daquele** eixo") mas não é coberta por CA. Deve entrar no aceite do ADR-001.
- **P2-2 — `trocou_vs_revised` não é a métrica de CA-073.** A coluna é `True` em **24 de 83** linhas
  de `regimes_v1_asof` (0 nulos), porque compara `None != rótulo` nos 2 pares com `INDETERMINADO`
  (2009Q4 e 2026Q3). Quem agregar a coluna chega a **28,9%**, não aos **33,33% (22/66)** publicados.
  Declarar a diferença na docstring da coluna.
- **P2-3 — `alerta_n_baixo` mede a escolha de `k`, não pool pequeno.** Dispara em **2.072** linhas
  porque `N_ALERTA = 8` e toda linha `k = 5` tem `n_vizinhos = 5 < 8` — aceso por construção na
  sensibilidade, o que o esvazia como sinal.
- **P2-4 — CA-078 não é satisfeito como escrito.** "Os 83 trimestres recebem um dos 4 rótulos, **sem
  `NULL`**" contra 16 `NULL` por **D-m**. A escolha do implementador é a **certa** (Anti-SPEC §10.1.1
  proíbe estimativa, e o nulo vem com `status` + `motivo`), mas a SPEC é sagrada e o agente não pode
  editá-la: a emenda de CA-078 tem de entrar no aceite do ADR-001, não ficar como divergência tácita.
- **P2-5** (§3e) `ciclo_selic` publicado sem a persistência de CA-082 · **P2-6** (§2) `retornos.py`
  fora dos 3 Feature Contracts · **P2-7** `CONTRACTS.md §5.1a` diz "PK `(quarter, lag_adjusted)`"
  mas `RegimesV1Schema` tem `Config.unique = ["quarter"]` — texto ou schema, um dos dois.

## 5. Matriz de validação — `CA | teste | tipo | status | evidência`

| F | CA | Teste do QA | Tipo | St. | Evidência |
|---|---|---|---|---|---|
| 018 | CA-010 | `pib_yoy` asof de T = `revised` de T−1 | revisão numérica | ✅ | 2010Q1 = 5,329431 = `revised` 2009Q4; `date_obs` 2009-12-31; `lag_adjusted=True` |
| 018 | CA-072 | `date_obs + lag_dias <= quarter_end` | join no Parquet | ✅ | **0 violações em 2.552 linhas**; `lag_dias >= catálogo` sempre |
| 018 | CA-072 | reconstrução das 6 colunas célula a célula | revisão numérica | ✅ | **0 divergências**, `max abs dif = 0,0` em `asof` **e** `revised` |
| 018 | CA-072 | tabela não mistura `asof`/`revised` | contrato | ✅ | `lag_adjusted` homogêneo nos 2 Parquet |
| 018 | CA-073 | % de troca calculado e exposto | recálculo | ✅ | 22/66 = 33,3333%, igual ao proxy e ao oficial de F-019 |
| 018 | CA-074 | texto afirma "não operacional" | leitura do JSON | ✅ | `operacional = false` + texto "ACIMA DO LIMITE" |
| 018 | — | `vintage` único degenerado · hash | ataque | ⚠️ | declarado em `limitacoes`; hash bate, mas 1 execução (**P1-4**) |
| 019 | CA-078 | 4 quadrantes povoados, rótulo por trimestre | reclassificação | ⚠️ | 0/83 divergências, mas 16 `NULL` (D-m) ≠ letra do CA — **P2-4** |
| 019 | CA-079 | desempate `== 0` herda T−1 | ataque + recálculo | ⚠️ | reproduzido (2007Q1 `asof`), mas no eixo `pi`, fora do CA — **P2-1** |
| 019 | CA-080 | `n` ∈ [10, 35] por quadrante | recontagem | ✅ | 19/19/16/13 e 21/17/16/13; desbalanceamento 1,46× |
| 019 | CA-081 | função pura, 2 execuções iguais | determinismo | ✅ | minha reimplementação (sem relógio/aleatório) dá o mesmo rótulo em 166 linhas |
| 019 | CA-088 | `fonte_versao` = hash do código, `quarter` PK | contrato | ✅ | 64 hex; `quarter` único; `sha256` do Parquet bate |
| 019 | CA-090 | ADR em `Proposta` ⇒ não publicável | leitura do disco | ✅ | `especificacao_congelada=False` em **83/83** nas duas; veredito `BLOQUEADO` |
| 019 | CA-091 | ajuste nasce `V1.1` | contrato | ✅ | `isin=(V1, V1.1)`; hoje `V1` em 83/83 |
| 019 | CA-108/109 | flags de `n` | recálculo | ✅ | `n_obs` == contagem do grupo em 83/83; nenhuma acesa (mín. 13) |
| 019 | — | 16 indeterminados == nulos de `ibcbr_gap` | revisão numérica | ✅ | conjuntos idênticos; `ipca_12m_delta` com 0 nulos |
| 019 | — | sensibilidade ±0,1 pp | recálculo | ✅ | 1/1 (`revised`), 4/1 (`asof`) — iguais às publicadas |
| 019 | — | `trocou_vs_revised` | ataque | ⚠️ | 24/83 `True` vs 22/66 publicado — **P2-2** |
| 021 | CA-084 | shrinkage obrigatório e **medido** | Ledoit-Wolf pela definição, laço explícito | ✅ | `rho = 0,2598739074018101` (igual a `1e-16`); `cond` 8,2611 → 3,9747 |
| 021 | CA-085 | adjacentes fora; desempate pelo recente | ataque em 9.692 linhas | ✅ | distância temporal mínima **3**; 0 empates de distância (desempate não exercitado) |
| 021 | CA-086 | 5 features declaradas, nunca silencioso | contrato + JSON | ✅ | `n_features=5`, `features_usadas` na linha, de/para em `CONTRACTS §5.3` |
| 021 | CA-087 | k = 5/8/12 + divergência reportada | recálculo | ✅ | prefixos do mesmo ordenamento; Jaccard 0,625 (k5) e 0,667 (k12) |
| 021 | CA-089 | PK, `metrica` no enum, `rank` ≤ k | contrato | ✅ | `rank <= n_vizinhos` sempre; 2 artefatos, custo medido (Jaccard 0,33) |
| 021 | CA-090 | gate de publicação | JSON | ✅ | `publicavel=false`, `especificacao_congelada=false` |
| 021 | CA-101 | 8 vizinhos com distância e rótulo V1 | **numpy puro** | ✅ | 8/8 idênticos até `1e-12`; rótulo V1 com 0 divergências vs F-019 |
| 021 | CA-102 | retorno em **T+1**, não no vizinho | `groupby` independente | ✅ | `quarter_t_mais_1 = vizinho + 1` em 100%; `INDX/ACWI_BRL/IMAT` reproduzidos; CDI = 0,0 |
| 021 | CA-108/109 | flags de `n` | recálculo | ⚠️ | corretas por definição, mas `alerta_n_baixo` aceso em 2.072 linhas — **P2-3** |
| 021 | — | contrato espelho correto | leitura | ❌ | `rho_shrinkage` e colunas `z_*` **não existem** — **P1-1** |
| 021 | — | variante sem look-ahead | ataque | ❌ | Jaccard 1,0 só em 2026Q3; mediana 0,455 em 58 refs — **P1-2** |
| 021 | — | safra das features | ataque | ❌ | `ipca_12m_delta` difere de `asof` em 83/83 — **P1-5** |
| 021 | — | expanding não lê T+1 | ataque | ✅ | perturbar todo o futuro não muda z nem `rho` de T |

## 6. O que fazer

**P1 (antes do merge):** P1-1 corrigir `CONTRACTS.md §5.2a` para as 21 colunas reais (**F-022
depende**); P1-2 requalificar o "Jaccard 1,0" em `TODO.md §F-021` e `CONTRACTS.md §5.2a` com a
mediana de 0,455 nas 58 referências; P1-3 corrigir a frase de D-t nos 3 lugares (2024Q3 é **alta**)
**antes** de pedir a ratificação do Edu; P1-4 habilitar `n2-integration` no `ci.yml` e registrar por
que N3 não roda; P1-5 reescrever a promessa de "sem nenhum look-ahead" da V3 ou rodá-la também sobre
`macro_quarterly_asof`. **P2** → aceite do ADR-001 / dívida em `TODO.md §6`.

**Nada em P0.** Nenhum número reconstruído divergiu: 5 colunas × 83 × 2 materializações em F-018,
83 × 2 rótulos em F-019, `rho` + 16 distâncias + 24 médias de ativo em F-021, `ibcbr_*` e
`ciclo_selic` no fechamento — **0 divergências numéricas**. Os 4 P1 são de **declaração**: contrato
espelho, leitura de um número de robustez e uma premissa factual errada num texto que vai ao
decisor. O gate de publicação segue correto e fechado.
