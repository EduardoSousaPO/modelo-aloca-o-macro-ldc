# SPEC — Estratégia Macro LDC · base estatística de regimes e alocação

> Especificação técnica. **O que o pipeline faz, de forma verificável** — e, na §10 (Anti-SPEC, sagrada),
> o que ele **nunca** faz.
>
> **Versão:** 1.0 — **Data:** 2026-10-10 — **Referência:** `docs/product/PRD.md` v1.0 (52 RFs),
> `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` (imutável), `docs/research/metodologia-regimes-macro.md`,
> `docs/research/fontes-de-dados.md` + `-RESUMO.md`.
> **Gerada por:** `/SDD-avancado` em **modo autônomo** (sem resposta humana às 8 decisões bloqueantes).
> **Prazo duro:** Comitê de Alocação **2026-10-14**.
>
> **Regra de precedência.** Em conflito vale, nesta ordem: `ESCOPO-EMAIL-ALEXANDRE.md` → `PRD.md` →
> este SPEC → `packages/shared/schemas/` → `docs/contracts/CONTRACTS.md` → wiki.
> **Nenhum agente altera este arquivo** (nem a Anti-SPEC) sem autorização humana explícita — `AGENTS.md §8`.

---

## 1. Como ler esta SPEC

- **RF-NNN** são os 52 requisitos funcionais do PRD §5, aqui traduzidos em **comportamento verificável**.
- **CA-NNN** são critérios de aceite numerados, em Given/When/Then compacto. **Cada CA vira ao menos um
  teste automatizado** (`pytest`), com fonte externa sempre via **fixture gravada** em `tests/fixtures/`.
- **Valor-canário** = valor conhecido da fonte usado como assert de contrato (detecta mudança de layout
  silenciosa em endpoint não documentado).
- Toda feature que implementa um RF está na tabela de rastreabilidade (§13) com **classe A/B/C/D** e
  **CI alvo** (N1/N2/N3), conforme `AGENTS.md §2` e `docs/plans/risk-classification.md`.
- **`[PROVISÓRIO Dx]`** marca comportamento que depende de uma das 8 decisões bloqueantes sem resposta
  humana (§11). O valor adotado é **a recomendação da pesquisa**, e cada um pode ser virado sem
  retrabalho estrutural — a §11 diz exatamente o que muda.

---

## 2. Definições operacionais (valem para toda a SPEC)

| Termo | Definição operacional |
|---|---|
| **Janela** | 1T2006 → 3T2026 = **83 trimestres** (`quarter` de `2006Q1` a `2026Q3`) |
| **Trimestre** | fecha no **último dia útil** (calendário B3/ANBIMA) de mar/jun/set/dez |
| **Retorno de T** | `P(último DU de T) / P(último DU de T-1) - 1` |
| **Excesso sobre CDI** | `(1 + r_ativo) / (1 + r_cdi) - 1` — **sempre razão, nunca subtração** |
| **Retorno real** | `(1 + r_ativo) / (1 + ipca_tri) - 1` |
| **`asof`** | materialização que respeita a defasagem de divulgação (só informação conhecida até o último DU de T) |
| **`revised`** | materialização com a série vigente hoje (revisada), sem defasagem |
| **`vintage`** | data em que o valor foi conhecido/baixado; `NULL` = série não revisável |
| **Granularidade nativa** | diário para preços/câmbio/curva, mensal para IPCA/IBC-Br, trimestral para PIB |
| **Camadas** | `data/raw/<fonte>/` (cru, imutável) → `data/processed/` (tipado, freq. nativa) → `data/canonical/` (trimestral alinhado) |
| **Classe C** | qualquer mudança em schema canônico, alinhamento temporal, cálculo de retorno ou definição de regime |
| **Classe D** | publicação para o Comitê, credencial/API paga, alteração de número já apresentado |

---

## 3. RFs de extração por fonte (RF-001 → RF-019)

> Fonte primária e fallback vêm de `docs/research/fontes-de-dados.md`. **Nenhum identificador é inventado:**
> o que a pesquisa marca "a confirmar" entra no catálogo com `status: a_confirmar` e **não** vai para o
> caminho crítico. Cada extrator grava bruto em `data/raw/<fonte>/`, tipado em `data/processed/`,
> e valida o output contra o schema pandera correspondente.

### RF-001 — IPCA variação mensal e acumulado 12m (e-mail A2, A7)

Extrai IPCA mensal (SGS **433**) e acumulado 12m (SGS **13522**), 01/2006 → 09/2026, sem buraco,
e reconcilia contra SIDRA `t/1737` `v/63` e `v/2265`.

- **CA-001** — *Given* o extrator SGS com fixture de `bcdata.sgs.433`; *When* roda para 2006-01→2026-09;
  *Then* devolve >= 249 observações mensais contíguas (sem mês faltando), todas com `source='BCB_SGS'`,
  `freq='M'`, `unit='%'`.
- **CA-002** — *Given* as fixtures de SGS 433 e SIDRA `t/1737 v/63` para ago/2026 e set/2026;
  *When* reconcilia; *Then* os valores são **idênticos** (`-0.32` e `0.82`); qualquer divergência falha.
- **CA-003** — *Given* uma resposta do SGS com HTTP **200** e corpo `{"error": ...}`; *When* o extrator
  parseia; *Then* levanta erro explícito e **não grava nada** em `data/processed/`.

### RF-002 — IPCA número-índice para deflação (e-mail A7)

Número-índice base dez/1993 = 100 via SIDRA `t/1737` `v/2266`, mensal, 2006→2026.

- **CA-004** — *Given* fixture de `t/1737 v/2266`; *When* extrai; *Then* a série é monotônica não
  decrescente em >= 99% dos meses, `unit='index'`, e a **primeira linha da resposta é tratada como
  cabeçalho** (não como dado).
- **CA-005** — *Given* o número-índice; *When* calcula o IPCA trimestral por razão `(I_fim/I_ini - 1)`;
  *Then* o resultado bate com o encadeamento geométrico de SGS 433 no mesmo trimestre, tolerância <= 1e-6.

### RF-003 — IBC-Br com ajuste sazonal (e-mail A1)

SGS **24364** (dessazonalizado), mensal, 01/2006 → 2026. Série começa em 2003.

- **CA-006** — *Given* fixture de SGS 24364; *When* extrai; *Then* jan/2006 = `79.44731` (valor-canário)
  e o `data_inicio` registrado no catálogo é 2003, não 2006.
- **CA-007** — *Given* a série; *When* calcula variação a/a e média móvel de 20 trimestres;
  *Then* o `ibcbr_gap` existe para todos os 83 trimestres **ou** o trimestre é marcado `is_estimated=True`.

### RF-004 — PIB trimestral, índice de volume dessazonalizado (e-mail A1)

SIDRA `t/1621` `v/584` `c11255/90707`, 1T2006 → 2T2026; espelho SGS **22109**.

- **CA-008** — *Given* fixture SIDRA `t/1621`; *When* extrai; *Then* 2006T1 = `131.74`, 2006T2 = `132.14`,
  2006T3 = `134.36` (valores-canário).
- **CA-009** — *Given* as fixtures de SIDRA `t/1621/v584/90707` e SGS 22109; *When* reconcilia;
  *Then* os valores são idênticos trimestre a trimestre.
- **CA-010** — *Given* que o PIB tem ~60 dias de defasagem; *When* materializa `asof`; *Then* o PIB usado
  para classificar T é o de **T-1** e a coluna `lag_adjusted=True`.

### RF-005 — Selic Over e Selic meta (e-mail A4)

SGS **11** (%/dia), **1178** (% a.a. base 252) e **432** (meta), diárias, 2006→2026, **fatiando em
blocos <= 10 anos**.

- **CA-011** — *Given* que o SGS rejeita janela > 10 anos em série diária com HTTP 200 + corpo de erro;
  *When* o extrator pede 2006→2026; *Then* ele fatia em blocos <= 10 anos, concatena, e o resultado não
  tem data duplicada nem lacuna de dia útil.
- **CA-012** — *Given* fixture de SGS 11; *When* extrai; *Then* 03/01/2005 = `0.064826` (valor-canário).
- **CA-013** — *Given* que SGS 432 devolve a meta vigente com **data futura**; *When* extrai hoje;
  *Then* a série é truncada em `today` e nenhuma linha com `date > today` chega a `data/processed/`.

### RF-006 — CDI diário e acumulação trimestral (e-mail B3)

SGS **12** (%/dia). Acumulação **geométrica**: `prod(1 + v/100)`.

- **CA-014** — *Given* fixture de SGS 12 para 2006 (249 dias úteis); *When* acumula o ano inteiro;
  *Then* o resultado é **15,0271%** com tolerância <= 1e-4 (valor-canário contra o CDI publicado).
- **CA-015** — *Given* a mesma fixture; *When* acumula por trimestre; *Then* o produto dos 4 trimestres
  de 2006 reproduz o fator anual com tolerância <= 1e-9.
- **CA-016** — *Given* que a série 12 é **percentual** e não fator; *When* o código acumula;
  *Then* existe teste que falha se o `/100` for omitido (o fator anual sairia absurdo, > 1e5).

### RF-007 — Expectativas Focus por data de coleta (e-mail A3)

Olinda OData v4, EntitySets `ExpectativasMercadoAnuais`, `ExpectativaMercadoMensais`,
`ExpectativasMercadoTrimestrais`, `ExpectativasMercadoSelic`, `ExpectativasMercadoInflacao12Meses`,
2006→2026, **filtrando `baseCalculo` por um único valor**.

- **CA-017** — *Given* fixture do Olinda com `baseCalculo` 0 e 1 para a mesma `Data`+`DataReferencia`;
  *When* extrai; *Then* o output tem **uma** linha por (`Indicador`,`Data`,`DataReferencia`) e o
  `baseCalculo` usado está registrado no catálogo.
- **CA-018** — *Given* que `$top=20000` trunca sem `nextLink`; *When* o extrator consulta;
  *Then* ele **omite `$top`** ou pagina com `$skip`, e um assert de contagem mínima falha se vierem
  exatamente 20.000 linhas.
- **CA-019** — *Given* capitalização de campo variável entre EntitySets; *When* normaliza;
  *Then* o output usa nomes canônicos (`indicador`, `data`, `data_referencia`, `mediana`, ...) para
  todos os 5 EntitySets.

### RF-008 — Taxas e PUs de títulos públicos (e-mail A5)

Tesouro Transparente CKAN, `precotaxatesourodireto.csv` (um arquivo, 14,6 MB), 31/12/2004 → hoje,
`;` + decimal vírgula + **latin-1** + datas `dd/mm/aaaa`, **User-Agent de browser obrigatório**.

- **CA-020** — *Given* fixture com 200 linhas do CSV; *When* parseia; *Then* reconhece os 8 tipos de
  título, converte decimal vírgula corretamente e nenhuma taxa fica `NaN` por erro de parse.
- **CA-021** — *Given* o arquivo completo; *When* extrai; *Then* cobre 2006 com >= 240 dias úteis e
  `min(Data Base)` <= 2005-01-03.
- **CA-022** — *Given* leitura com encoding default do Windows (cp1252); *When* o teste força o default;
  *Then* o extrator **declara `encoding='latin-1'` explicitamente** e o teste de acento passa.

### RF-009 — Inclinação da curva por vértices fixos interpolados (e-mail A6) `[PROVISÓRIO L4]`

Constrói, a partir do Tesouro Direto (RF-008): **inclinação real** (NTN-B curta x longa) como variável
principal e **nominal 1a x 5a** como secundária, por **interpolação para prazos fixos** em cada data,
com flag `vertice_extrapolado`. Motivo: SGS 7801-7806 morreu em 30/09/2019 e a ETTJ ANBIMA histórica é paga.

- **CA-023** — *Given* as taxas de uma data com os vencimentos disponíveis; *When* interpola para 1, 3 e 5
  anos; *Then* cada vértice traz `vertice_extrapolado=True` quando o prazo-alvo está fora do intervalo
  de vencimentos daquela data.
- **CA-024** — *Given* 2006 (LTN mais longa vence 01/01/2009; NTN-F mais longa 01/01/2014);
  *When* pede o vértice nominal de **10 anos**; *Then* o resultado é `NULL` + flag, **nunca extrapolação
  silenciosa**.
- **CA-025** — *Given* a curva real de 2006 (10 vencimentos de NTN-B até 15/05/2045); *When* calcula a
  inclinação real; *Then* existe valor para >= 95% dos dias úteis de 2006→2026.
- **CA-026** — *Given* a série de inclinação; *When* agrega para trimestral; *Then* o valor do trimestre é
  o do **último dia útil** e a coluna documenta que a curva é do **Tesouro Direto (varejo)**, não a ETTJ
  Svensson oficial da ANBIMA.

### RF-010 — Job diário de arquivamento ANBIMA (e-mail A6)

Arquiva `Msec_txt.txt` (taxas indicativas) e o POST `CZ-down.asp` (Svensson) em `data/raw/anbima-*/`,
**idempotente**, tratando ausência/atraso como caso normal. Motivo: janela rolante de ~20 dias úteis —
cada dia sem arquivar é série proprietária perdida para sempre.

- **CA-027** — *Given* que o arquivo do dia já foi arquivado; *When* o job roda de novo;
  *Then* não duplica, não sobrescreve com conteúdo diferente, e retorna "já arquivado".
- **CA-028** — *Given* resposta de 0 bytes ou HTTP 404 (dia sem divulgação / atraso declarado);
  *When* o job roda; *Then* registra o evento e **termina com sucesso** (não é falha).
- **CA-029** — *Given* o `ms*.txt`; *When* parseia; *Then* usa separador `@`, `skiprows=2`,
  `encoding='latin-1'`, decimal vírgula, e reconhece os 5 títulos (LTN, LFT, NTN-B, NTN-C, NTN-F).

### RF-011 — Índices ANBIMA IMA (e-mail B1, B2)

Bucket S3 público
`https://s3-data-prd-use1-precos.s3.us-east-1.amazonaws.com/arquivos/indices-historico/{SLUG}-HISTORICO.xls`
para `IMAB`, `IMAB5`, `IMAB5MAIS`, `IRFM`, `IRFM1`, `IRFM1MAIS`, `IMAGERAL`, `IMAS`
(+ `IMAGERALEXC`; `IMAC` descontinuado em 2021).

- **CA-030** — *Given* o arquivo `.xls` do S3; *When* lê; *Then* detecta magic bytes `PK` (é **XLSX**),
  usa `engine="openpyxl"` a partir de `io.BytesIO`, e **não** tenta `xlrd`.
- **CA-031** — *Given* a fixture de `IMAB`; *When* extrai; *Then* 16/09/2003 = **723,070317**
  (valor-canário) e a última data é >= 2026-10-09.
- **CA-032** — *Given* a coluna `Índice` com rótulos inconsistentes (`IMA-B` x `IMA - B`);
  *When* normaliza; *Then* a remoção de espaços colapsa os rótulos e o agrupamento devolve **um**
  `asset_id` por índice.
- **CA-033** — *Given* os 8 índices pedidos no e-mail; *When* o extrator roda; *Then* todos têm
  `data_inicio <= 2006-01-02` e o `series_catalog` registra os SLUGs **hard-coded** (a listagem do
  bucket responde `AccessDenied`).

### RF-012 — Índices B3 amplos e setoriais (e-mail B4)

API interna `indexStatisticsProxy/IndexCall/GetPortfolioDay/{payload_b64}` com
`{"language":"pt-br","index":"<COD>","year":"<AAAA>"}`, UA de browser + `Referer`. Códigos: `IBOV`,
`IDIV`, `SMLL`, `INDX`, `IMAT`, **`IEEX`** (não `IEE`), `IFNC`, `UTIL`, `ICON` (2007+), `IMOB` (2008+).

- **CA-034** — *Given* a resposta matriz dia x mês (`results[].rateValue1..12`); *When* faz o unpivot;
  *Then* `IBOV`/2006 devolve **246 pontos não nulos** e `day=1, rateValue2 = "38.484,84"` vira
  2006-02-01 = `38484.84` (valor-canário).
- **CA-035** — *Given* valores em formato pt-BR com ponto de milhar; *When* converte;
  *Then* o normalizador único de número pt-BR é usado e `"38.484,84"` nunca vira `38.48`.
- **CA-036** — *Given* `ICON` e `IMOB`; *When* extrai 2006; *Then* o output traz apenas o ponto-base
  (28/12/2006 = 1.000,00 e 28/12/2007 = 1.000,00) e o catálogo registra `data_inicio` 2006-12-28 e
  2007-12-28, com série efetiva em 2007 e 2008 — **sem preencher 2006**.
- **CA-037** — *Given* célula vazia (feriado, dia inexistente no mês); *When* faz o unpivot; *Then* a
  linha é omitida ou gravada como `NULL`, nunca como `0`.

### RF-013 — IFIX (e-mail B5) `[PROVISÓRIO L1]`

API B3 `IFIX`, **2011→2026**, com a janela real declarada no output (base 30/12/2010 = 1.000,00).

- **CA-038** — *Given* a fixture de `IFIX`; *When* extrai 2010 e 2011; *Then* 2010 traz só o ponto-base e
  2011 traz 249 pontos; `data_inicio` no catálogo = 2010-12-30.
- **CA-039** — *Given* qualquer tabela ou figura que use IFIX; *When* é gerada; *Then* a janela
  2011-2026 aparece explicitamente e **nenhum valor pré-2011 é sintetizado**.

### RF-014 — Índices de FII por segmento (e-mail B5) `[PROVISÓRIO L2, D12]` — prioridade `should`

Bucket GCS público da Teva (`teva-indices-public`, prefixo `quotations-download-file/`), segmentos
`3.2.2` Tijolo, `3.2.1` Papel, `3.3.1` Logística, `3.3.3` Shoppings, `3.3.2` Lajes,
**2019-01-02 → hoje**, retorno total.

- **CA-040** — *Given* que o nome do arquivo traz versão embutida (`v0.27`); *When* o extrator busca;
  *Then* **lista o bucket** e casa por **regex no prefixo numérico** — nenhum nome de arquivo hard-coded.
- **CA-041** — *Given* a fixture de Tijolo; *When* extrai; *Then* 02/01/2019 = `100` e a série tem
  ~1.937 linhas até 2026-10-09.
- **CA-042** — *Given* a janela 2019+; *When* a série entra em qualquer tabela; *Then* carrega
  `n` e `data_inicio` visíveis, o rótulo **qualitativo (~2 ciclos macro)** e a nota de que a Teva é
  provedor privado **sem licença comercial explícita** (sem redistribuição).

### RF-015 — USDBRL PTAX (e-mail C1)

SGS **1** (venda) e **10813** (compra), diárias, 2006→2026.

- **CA-043** — *Given* fixture de SGS 1; *When* extrai; *Then* 09/10/2026 = `4.9892` (valor-canário) e a
  série é fatiada em blocos <= 10 anos.
- **CA-044** — *Given* a série diária; *When* agrega para trimestral; *Then* produz `usdbrl_fim`
  (último DU), `usdbrl_var_tri` e `usdbrl_var_12m`, todas por razão.

### RF-016 — S&P 500 e MSCI ACWI em retorno total, convertidos a BRL (e-mail C1)

Yahoo **`^GSPC`** (com `period1`/`period2` em epoch, **nunca `range=max`** para séries mensais) e MSCI
`index_codes=892400` variante **`NETR`** (`app2.msci.com/.../getLevelDataForGraph`).
Proibido: FRED `SP500` (só 10 anos).

- **CA-045** — *Given* requisição ao Yahoo **sem** User-Agent; *When* roda; *Then* o teste comprova
  HTTP 429 e o extrator usa UA de browser em todas as chamadas.
- **CA-046** — *Given* fixture do MSCI ACWI `NETR`; *When* extrai; *Then* 31/01/2006 = `121,3858`
  (valor-canário) e `data_inicio` = 2000-12-29.
- **CA-047** — *Given* a série em USD e o PTAX; *When* converte para BRL; *Then* a conversão usa a PTAX
  do **mesmo dia útil** e o output marca `is_total_return=True`; misturar total return doméstico com
  price return internacional falha o teste.

### RF-017 — Treasury 10y, VIX, Fed Funds e ouro (e-mail C1) — prioridade `should`

FRED `DGS10`, `VIXCLS`, `DFF` com `cosd=1900-01-01` **sempre**; fallback **obrigatório** Yahoo `^TNX`,
`^VIX` se o teste de conectividade ao FRED falhar (risco R-06 / gap G-06).
**Ouro spot com 20 anos: fonte `a_confirmar`** (os IDs testados no FRED deram 404).

- **CA-048** — *Given* o ambiente de execução; *When* roda o teste de conectividade ao FRED;
  *Then* o resultado é registrado e, em caso de falha, o pipeline **usa o fallback Yahoo
  automaticamente** e registra a substituição em `DECISIONS_LOG`.
- **CA-049** — *Given* `fredgraph.csv` **sem** `cosd`; *When* o teste compara com a versão com
  `cosd=1900-01-01`; *Then* comprova o truncamento e o extrator sempre envia `cosd`.
- **CA-050** — *Given* que não há fonte gratuita confirmada de ouro spot com 20 anos; *When* o pipeline
  precisa de `GOLD_BRL`; *Then* retorna `BLOQUEADO — FONTE INDISPONÍVEL` e a linha **não entra** no
  heatmap — nenhum proxy é adotado em silêncio.

### RF-018 — Calendário de dias úteis (e-mail A4, B3)

`https://www.anbima.com.br/feriados/arqs/feriados_nacionais.xls` carregado e usado em **toda**
acumulação e alinhamento; fallback lib `bizdays`.

- **CA-051** — *Given* o calendário; *When* conta os dias úteis de 2006; *Then* o total é **249**,
  coerente com a contagem de observações do CDI (SGS 12) no mesmo ano.
- **CA-052** — *Given* um trimestre cujo último dia civil é feriado ou fim de semana; *When* alinha;
  *Then* usa o **dia útil anterior**, nunca o dia civil.

### RF-019 — `series_catalog` completo (todos os itens do e-mail)

Catálogo com `series_id, nome, fonte, identificador, fonte_url, freq, data_inicio, data_fim, unit,
transformacao_padrao, lag_divulgacao_dias, confianca, status` para **100% das séries extraídas**.

- **CA-053** — *Given* o catálogo em `packages/shared/schemas/series_catalog_data.py`; *When* valida
  contra o modelo pydantic; *Then* **nenhuma** entrada tem identificador vazio e toda entrada carrega a
  `confianca` copiada da pesquisa (`CONFIRMADO` | `CONFIRMADO_SUB` | `NAO_VERIFICADO`).
- **CA-054** — *Given* uma série que a pesquisa marca "a confirmar"; *When* entra no catálogo;
  *Then* recebe `status='a_confirmar'` e **nenhum extrator do pacote mínimo depende dela**.
- **CA-055** — *Given* qualquer linha de `data/canonical/`; *When* se busca sua origem;
  *Then* o `series_id` existe no catálogo e resolve para uma URL de fonte.

---

## 4. RFs da camada canônica (RF-020 → RF-026) — **classe C**

### RF-020 — `raw_series`: tabela longa na granularidade nativa

`raw_series(series_id, date, value, source, freq, vintage, unit, collected_at)`, PK
`(series_id, date, vintage)`, validada por pandera (`packages/shared/schemas/raw_series.py`).

- **CA-056** — *Given* duas extrações da mesma série em dias diferentes; *When* gravadas;
  *Then* coexistem como `vintage` distintos e a PK não é violada.
- **CA-057** — *Given* uma linha sem `source` ou sem `series_id`; *When* passa pelo schema;
  *Then* o pandera **rejeita** (`SchemaError`) e nada é gravado.
- **CA-058** — *Given* uma série trimestral; *When* alguém tenta gravá-la como primária em frequência
  trimestral inventada (ex.: IPCA mensal reamostrado); *Then* o teste de granularidade falha — a camada
  guarda **sempre** a frequência nativa declarada no catálogo.

### RF-021 — `macro_quarterly` com 83 linhas

Colunas de crescimento, inflação, juros, curva, câmbio e expectativas + `is_estimated` e `lag_adjusted`,
conforme `docs/research/metodologia-regimes-macro.md §6.2`.

- **CA-059** — *Given* o pipeline completo sobre fixtures; *When* materializa `macro_quarterly`;
  *Then* tem exatamente **83 linhas**, `quarter` de `2006Q1` a `2026Q3`, sem trimestre repetido nem
  faltando.
- **CA-060** — *Given* o trimestre corrente incompleto (`2026Q3`); *When* materializa;
  *Then* `is_estimated=True` nessa linha e `False` nas demais.
- **CA-061** — *Given* qualquer coluna cuja série de origem não cobre 2006; *When* materializa;
  *Then* o valor é `NULL` (nunca interpolado) e a janela real está no `series_catalog`.

### RF-022 — `asset_returns_quarterly` com >= 18 ativos

`(quarter, asset_id)` PK, com `ret_tri`, `ret_excesso_cdi`, `ret_real`, `is_total_return`, `n_dias_uteis`.

- **CA-062** — *Given* o pipeline sobre fixtures; *When* materializa; *Then* há >= 18 `asset_id`
  distintos e todos existem no `series_catalog`.
- **CA-063** — *Given* um ativo cuja série começa depois de 2006 (IFIX, ICON, IMOB, FII segmentado);
  *When* materializa; *Then* os trimestres anteriores ao início **não existem** na tabela (painel
  desbalanceado explícito), em vez de virarem `0` ou valor herdado.
- **CA-064** — *Given* um índice de price return e um de total return; *When* ambos entram na tabela;
  *Then* `is_total_return` distingue os dois e o teste falha se um price return internacional for
  comparado a um total return doméstico sem a flag.

### RF-023 — Alinhamento temporal: último dia útil + forward-fill limitado

Trimestre = último dia útil de mar/jun/set/dez; retorno de T por razão de preços; forward-fill de no
máximo **5 dias úteis**, acima disso `NULL` registrado.

- **CA-065** — *Given* o calendário ANBIMA; *When* calcula o fim de cada um dos 83 trimestres;
  *Then* todos caem em dia útil e o teste cobre os casos-armadilha (31/12 em fim de semana, Carnaval).
- **CA-066** — *Given* um ativo sem negociação no último DU do trimestre; *When* alinha;
  *Then* usa forward-fill de até 5 DU e grava quantos DU foram usados em `n_dias_uteis`.
- **CA-067** — *Given* lacuna > 5 dias úteis; *When* alinha; *Then* o valor é `NULL` e a lacuna fica
  registrada — nunca preenchida.
- **CA-068** — *Given* uma série com datas fora de ordem ou duplicadas; *When* entra no alinhamento;
  *Then* o pipeline ordena, detecta duplicidade e falha ruidosamente se houver valor divergente para a
  mesma data.

### RF-024 — Excesso sobre CDI e retorno real sempre por razão

`(1+r)/(1+b)-1`; encadeamento geométrico; **teste unitário que falha se alguém usar subtração**.

- **CA-069** — *Given* `r=0,10` e `cdi=0,0325`; *When* calcula o excesso; *Then* o resultado é
  `(1,10/1,0325)-1 = 0,06538...`, **diferente** de `0,0675` (subtração), e o teste rejeita a subtração.
- **CA-070** — *Given* retornos diários de um trimestre; *When* acumula; *Then* o resultado é o produto
  dos fatores (geométrico), não a soma.
- **CA-071** — *Given* o retorno real; *When* calculado; *Then* usa `(1+r)/(1+ipca_tri)-1` com o IPCA
  **do mesmo trimestre** e nunca aplica o IPCA duas vezes (teste de dupla deflação).

### RF-025 — Regra anti-look-ahead implementada e reportada

Regime de T usa só o conhecido no último DU de T: PIB/IBC-Br de T-1; IPCA do penúltimo mês de T;
Focus/Selic/curva/câmbio livres. O pipeline **reporta o % de trimestres que trocam de regime** entre a
variante `asof` e a `revised`.

- **CA-072** — *Given* `macro_quarterly_asof`; *When* inspeciona a origem de cada coluna de crescimento;
  *Then* nenhuma usa dado com `data de divulgação > fim do trimestre` e `lag_adjusted=True`.
- **CA-073** — *Given* as duas variantes; *When* classifica V1 em ambas; *Then* o pipeline emite o
  **% de trimestres que trocam de rótulo** e esse número aparece na página de limitações.
- **CA-074** — *Given* que esse percentual passe de **25%**; *When* o relatório é gerado; *Then* o texto
  afirma explicitamente que o modelo **não é operacional** nessa forma (hipótese H-03 do PRD caiu).

### RF-026 — Portão pandera + proibição de dado inventado

Todo DataFrame que entra ou sai de `data/canonical/` passa por schema pandera; coluna de origem
obrigatória; **zero** valor interpolado, estimado ou inventado.

- **CA-075** — *Given* um DataFrame canônico sem coluna de origem; *When* é gravado;
  *Then* o pandera rejeita antes da escrita.
- **CA-076** — *Given* uma lacuna de série sem substituto acordado; *When* o pipeline tenta fechar o
  trimestre; *Then* retorna `BLOQUEADO — FONTE INDISPONÍVEL` em vez de preencher.
- **CA-077** — *Given* um DataFrame com dados reais e sintéticos (fixture); *When* passa pelo schema;
  *Then* a coluna `source` distingue os dois e o teste falha se houver mistura sem distinção.

---

## 5. RFs de regimes (RF-027 → RF-031) — **classe C**

### RF-027 — V1: quadrantes crescimento x inflação `[PROVISÓRIO D1, D2, D3]`

`g_T` = IBC-Br a/a dessaz. menos média móvel de 20 trimestres; `pi_T` = **aceleração** (delta do IPCA 12m);
rótulos `RECUPERACAO`, `EXPANSAO_INFL`, `ESTAGFLACAO`, `DESACELERACAO`; empate herda o sinal do trimestre
anterior.

- **CA-078** — *Given* `macro_quarterly`; *When* classifica V1; *Then* os 83 trimestres recebem um dos 4
  rótulos, sem `NULL`, e nenhum quadrante fica vazio.
- **CA-079** — *Given* `g_T = 0` exatamente; *When* classifica; *Then* o trimestre **herda** o sinal de
  crescimento do trimestre anterior (regra de desempate determinística).
- **CA-080** — *Given* a distribuição final; *When* conta por quadrante; *Then* cada um tem `n` entre 10
  e 35 (ordem de ~20); fora dessa faixa o pipeline emite alerta de desbalanceamento.
- **CA-081** — *Given* a mesma entrada rodada duas vezes; *When* compara; *Then* a classificação é
  **idêntica** (função pura, sem estado nem aleatoriedade).

### RF-028 — V2: camada `ciclo_selic` como corte secundário `[PROVISÓRIO D1]` — `should`

`CORTE` se delta Selic meta < -0,25pp; `ALTA` se > +0,25pp; senão `NEUTRO`; pausa dentro de ciclo de corte
conta como `CORTE`. Publicada **apenas** como corte secundário, com `n` visível.

- **CA-082** — *Given* dois trimestres de `CORTE` seguidos de delta = 0; *When* classifica;
  *Then* o terceiro é `CORTE` (pausa dentro do ciclo), não `NEUTRO`.
- **CA-083** — *Given* a tabela V2 (4 x 3 estados); *When* é publicada; *Then* cada célula mostra `n`
  e nenhuma célula é usada como decisão única — o output declara "corte secundário".

### RF-029 — V3: vizinhos mais próximos `[PROVISÓRIO D1]`

6 features em z-score (gap do IBC-Br, IPCA 12m - meta, juro real ex-ante, inclinação, USDBRL 12m, termos
de troca), distância **Mahalanobis** com shrinkage Ledoit-Wolf, **k=8** (sensibilidade k=5 e k=12),
Euclidiana em paralelo como sanity check, excluindo os 2 trimestres imediatamente anteriores.

- **CA-084** — *Given* as 6 features padronizadas; *When* calcula a distância; *Then* a matriz de
  covariância usa shrinkage e o teste falha se a covariância amostral crua for usada (instável em 83x6).
- **CA-085** — *Given* o trimestre de referência; *When* busca vizinhos; *Then* os 2 trimestres
  imediatamente anteriores **não** aparecem no ranking, e distâncias empatadas desempatam pelo mais
  recente.
- **CA-086** — *Given* que a curva (RF-009) não ficou pronta; *When* roda V3; *Then* roda com **5
  features**, declara isso no output e no `fonte_versao`, em vez de usar uma curva inventada.
- **CA-087** — *Given* k=5, 8 e 12; *When* roda a sensibilidade; *Then* as três saídas são produzidas e a
  divergência entre elas é reportada.

### RF-030 — Tabelas `regimes` e `regime_neighbors`

`regimes(quarter, regime_v1, ciclo_selic, regime_v2, stress_flag, g_score, pi_score, fonte_versao)` e
`regime_neighbors(quarter_ref, rank, quarter_neighbor, distancia, metrica)`.

- **CA-088** — *Given* a tabela `regimes`; *When* validada por pandera; *Then* `quarter` é PK,
  `regime_v1` está no enum de 4 rótulos e `fonte_versao` é o **hash do código** que gerou.
- **CA-089** — *Given* `regime_neighbors`; *When* validada; *Then* PK `(quarter_ref, rank, metrica)`,
  `metrica` em {`mahalanobis`, `euclidiana`} e `rank` de 1 a k.

### RF-031 — Especificação de regime congelada em ADR antes de rodar sobre retornos

- **CA-090** — *Given* que `ADR-001` (lente oficial, eixos) está com status **Proposta**; *When* alguém
  tenta rodar o cruzamento regime x retorno do entregável; *Then* o pipeline **avisa** que a
  especificação não está congelada e o número não é publicável (gate da classe D).
- **CA-091** — *Given* uma mudança de especificação depois de ver o heatmap; *When* é aplicada;
  *Then* nasce como **V1.1** e o output reporta **as duas versões** lado a lado.

---

## 6. RFs de análise e visualização (RF-032 → RF-040)

### RF-032 — Métricas por `(regime, ativo)`

`n_obs`, `ret_medio`, `ret_mediana`, `ret_desvio`, `hit_ratio`, `excesso_cdi`, `hit_ratio_cdi`,
`ret_real`, `sharpe_tri`, `pior_tri`, `melhor_tri` e **erro-padrão da média**.

- **CA-092** — *Given* uma célula com n trimestres; *When* calcula; *Then* média **e** mediana aparecem
  lado a lado e o erro-padrão = `desvio/sqrt(n)`.
- **CA-093** — *Given* um ativo com janela própria (IFIX, ICON, IMOB); *When* calcula por regime;
  *Then* `n_obs` reflete só os trimestres existentes daquele ativo.
- **CA-094** — *Given* `sharpe_tri`; *When* anualizado; *Then* o output diz explicitamente que foi
  anualizado por `x sqrt(4)` e não apresenta o índice como implementável sem fricção.

### RF-033 — Heatmap regime x ativo `[PROVISÓRIO D5]`

>= 18 linhas x regimes, valor = **excesso sobre CDI** médio trimestral, escala divergente centrada em 0,
`n` anotado em **toda** célula, `data_inicio` por série no rodapé.

- **CA-095** — *Given* a matriz de métricas; *When* gera a figura; *Then* toda célula exibe `n` e
  nenhuma célula fica sem anotação.
- **CA-096** — *Given* células com `n < 8`; *When* gera; *Then* recebem hachura/cinza e flag
  `ALERTA_N_BAIXO`.
- **CA-097** — *Given* o rodapé; *When* gerado; *Then* lista `data_inicio` de cada série e a métrica
  usada é nomeada explicitamente ("excesso sobre CDI médio trimestral").

### RF-034 — Tabela de 1 página "regime atual → ranking de ativos"

- **CA-098** — *Given* o trimestre corrente; *When* gera a tabela; *Then* mostra o regime por V1, por V2,
  os 8 vizinhos da V3, e os ativos ordenados por `excesso_cdi` com `hit_ratio_cdi`, `n` e semáforo.
- **CA-099** — *Given* um ativo com `n < 5` no regime corrente; *When* aparece na tabela; *Then* não há
  afirmação conclusiva sobre ele — só o número com o alerta.

### RF-035 — Timeline de regimes 2006→2026

- **CA-100** — *Given* `regimes` e as séries de IBOV e Selic; *When* gera a figura; *Then* a faixa
  colorida V1 cobre os 83 trimestres sobre as duas séries, sem buraco visual não explicado.

### RF-036 — Saída da V3: 8 vizinhos + retorno dos trimestres SEGUINTES

- **CA-101** — *Given* o trimestre de referência; *When* gera a saída; *Then* lista os 8 vizinhos com
  distância e rótulo V1 de cada.
- **CA-102** — *Given* os 8 vizinhos; *When* calcula a performance; *Then* reporta o retorno de cada
  ativo nos trimestres **seguintes** aos vizinhos (T+1), não nos próprios vizinhos.

### RF-037 — Tabela de concordância entre lentes — `should`

- **CA-103** — *Given* as três lentes; *When* gera a tabela; *Then* há 1 linha por lente com top-3
  ativos, e a divergência entre lentes é **reportada como resultado**, não omitida.

### RF-038 — Dimensionamento da alocação internacional `[PROVISÓRIO D6]` (e-mail C1)

`SP500_BRL`, `USD_BRL`, `GOLD_BRL`, `UST10_BRL` no mesmo heatmap + `corr(USDBRL, IBOV)` por regime e nos
10 piores trimestres do IBOV.

- **CA-104** — *Given* o heatmap; *When* gerado; *Then* as linhas internacionais aparecem **no mesmo
  arcabouço** (mesma métrica e mesmos regimes), não em anexo separado.
- **CA-105** — *Given* os retornos trimestrais; *When* calcula `corr(USDBRL, IBOV)`; *Then* reporta a
  correlação por regime **e** nos 10 piores trimestres do IBOV, com `n` em cada.

### RF-039 — Regra de risk-off e faixa + banda `[PROVISÓRIO D6]`

`stress = 1` quando a inclinação cai > 1 desvio-padrão **ou** USDBRL sobe > 10% no trimestre; mede quanto
de USD neutraliza a queda do IBOV; entrega **faixa estrutural + banda tática por regime** (não número
pontual).

- **CA-106** — *Given* as séries de inclinação e USDBRL; *When* marca `stress_flag`; *Then* a regra é a
  disjunção acima, os trimestres marcados são listados, e o ramo EMBI fica declaradamente fora (fase 2).
- **CA-107** — *Given* os trimestres de stress; *When* gera a recomendação; *Then* o output é uma
  **faixa** (piso estrutural + banda tática por regime), e qualquer número pontual é rejeitado com a
  justificativa de `n` pequeno.

### RF-040 — Supressão por `n` baixo `[PROVISÓRIO D10 — não bloqueante]`

- **CA-108** — *Given* célula com `n < 8`; *When* publicada; *Then* recebe flag `ALERTA_N_BAIXO`.
- **CA-109** — *Given* célula com `n < 5`; *When* publicada; *Then* **nenhuma conclusão afirmativa** é
  gerada sobre ela (o texto usa "indicação preliminar, n=X").

---

## 7. RFs de entrega para o Comitê (RF-041 → RF-045) — **classe D na publicação**

### RF-041 — 1 notebook reprodutível, sem lógica de negócio

- **CA-110** — *Given* o notebook em `apps/analysis/`; *When* inspecionado; *Then* ele **importa** de
  `apps/pipeline/` e não define cálculo de retorno, regime ou alinhamento.
- **CA-111** — *Given* o notebook; *When* commitado; *Then* está com outputs limpos e roda de ponta a
  ponta sobre o canônico já construído.

### RF-042 — 1 página de limitações

- **CA-112** — *Given* a página; *When* gerada; *Then* contém: `n` pequeno e erro-padrão (~2,7 pp/tri com
  n=20 e sigma=12%), quebra estrutural 2006-2008 x pós-2016, resultado do teste de look-ahead (RF-025),
  séries com janela curta (ICON, IMOB, IFIX, FII segmentado, ponta longa nominal) e o aviso de que
  índice não é ativo investível sem fricção.

### RF-043 — Pacote de entrega

Parquet **+ CSV/XLSX** de `macro_quarterly`, `asset_returns_quarterly`, `regimes`, `regime_neighbors`,
mais figuras e as duas tabelas de 1 página.

- **CA-113** — *Given* o pacote; *When* montado; *Then* contém as 4 tabelas nos dois formatos, as figuras
  e as tabelas de 1 página, com `README` de versão + hash.
- **CA-114** — *Given* o pacote; *When* conferido; *Then* nenhum arquivo do pacote é editado à mão: todos
  saem de script versionado.

### RF-044 — Publicação tratada como classe D

- **CA-115** — *Given* a intenção de enviar ao Alexandre/Comitê; *When* o fluxo roda; *Then* exige
  revisão humana registrada, dataset congelado (versão + hash), linha em `docs/wiki/log.md` e rollback em
  `docs/plans/infra-ops.md`.
- **CA-116** — *Given* ausência de qualquer um desses itens; *When* se tenta publicar; *Then* o resultado
  é `BLOQUEADO` — não há caminho de publicação sem classe D.

### RF-045 — Comunicação escrita das substituições de fonte

- **CA-117** — *Given* as substituições conhecidas (ETTJ ANBIMA → Tesouro Direto; swap DI x pré morto;
  "ANBIMA DataFit" inexistente; FII segmentado via Teva 2019+; IFIX 2011+); *When* o pacote é enviado;
  *Then* acompanha um texto que lista cada uma com fonte pedida, fonte usada, motivo e impacto na
  comparabilidade.

---

## 8. RFs de reprodutibilidade e rastreabilidade (RF-046 → RF-052)

### RF-046 — Um comando reconstrói tudo

- **CA-118** — *Given* `data/` vazio; *When* roda o comando único; *Then* produz `raw` → `processed` →
  `canonical` sem passo manual, e imprime nº de linhas, min/max de data e % de nulos por coluna crítica.
- **CA-119** — *Given* o runbook de reconstrução; *When* seguido numa máquina limpa; *Then* o dataset é
  reproduzido (meta de tempo: <= 30 min a frio, RNF-008).

### RF-047 — Rastreabilidade por linha

- **CA-120** — *Given* qualquer valor do canônico; *When* se pergunta "de onde veio?"; *Then* `source`,
  `series_id`, `vintage`, `collected_at` e a URL do catálogo respondem sem ambiguidade.

### RF-048 — Idempotência

- **CA-121** — *Given* o mesmo `data/raw/`; *When* roda o pipeline duas vezes; *Then* o hash do canônico
  é **idêntico**.
- **CA-122** — *Given* uma revisão retroativa da fonte (IBGE revisa o PIB); *When* reprocessa;
  *Then* a linha é **atualizada** (novo `vintage`), nunca duplicada na materialização corrente.

### RF-049 — Fixtures e rede

- **CA-123** — *Given* a suíte de testes; *When* roda no CI; *Then* nenhuma chamada de rede acontece
  (tudo marcado `@pytest.mark.network` é excluído).
- **CA-124** — *Given* cada extrator; *When* mergeado; *Then* existe fixture gravada correspondente em
  `tests/fixtures/<fonte>/`.

### RF-050 — Testes de contrato com valor-canário nos 3 endpoints não documentados

- **CA-125** — *Given* B3 `indexStatisticsProxy`, MSCI `app2.msci.com` e o S3 da ANBIMA; *When* o teste
  de contrato roda sobre fixture; *Then* valida **shape + valor-canário** (IBOV 01/02/2006 = 38.484,84;
  IMA-B 16/09/2003 = 723,070317; MSCI ACWI NETR 31/01/2006 = 121,3858).
- **CA-126** — *Given* uma mudança de layout da fonte; *When* o contrato é verificado contra a fonte viva
  (teste `@pytest.mark.network`, fora do CI); *Then* a falha é explícita e nomeia o endpoint.

### RF-051 — Cache condicional — `should`

- **CA-127** — *Given* `ETag`/`Last-Modified` dos arquivos grandes (Tesouro 14,6 MB; COTAHIST até 91 MB);
  *When* roda de novo no mesmo dia; *Then* usa o cache local e não rebaixa o arquivo.

### RF-052 — `DECISIONS_LOG` de substituições

- **CA-128** — *Given* qualquer substituição de fonte; *When* adotada; *Then* existe entrada em
  `docs/plans/DECISIONS_LOG.md` com fonte pedida, fonte usada, por quê e impacto na comparabilidade.

---

## 9. Casos de borda (CB)

| ID | Cenário | Comportamento esperado |
|---|---|---|
| CB-001 | SGS devolve HTTP 200 com corpo de erro (janela > 10 anos, série inexistente) | falha ruidosa, nada gravado (CA-003) |
| CB-002 | Olinda devolve exatamente 20.000 linhas sem `nextLink` | assert de contagem falha; pagina com `$skip` (CA-018) |
| CB-003 | Ipeadata ignora `$filter`/`$top`/`$orderby` | baixa a série inteira e filtra em pandas |
| CB-004 | Yahoo troca a granularidade (`1mo` → `1wk`) silenciosamente | pedir `interval=1d` e reamostrar; validar `len(df) > 1` |
| CB-005 | `.xls` que é XLSX (S3 ANBIMA) ou HTML (`CZ-down.asp`) | checagem de magic bytes antes do parse (CA-030) |
| CB-006 | Arquivo ANBIMA do dia ausente/atrasado | caso **normal**: retry + registro, não falha (CA-028) |
| CB-007 | Trimestre termina em feriado | último dia útil anterior (CA-052) |
| CB-008 | Ativo sem negociação no fim do trimestre | ffill <= 5 DU; acima, `NULL` (CA-066/067) |
| CB-009 | Série que começa depois de 2006 | janela própria declarada; nunca backfill sintético (CA-063) |
| CB-010 | IBGE revisa o PIB | novo `vintage`; materialização atualizada, sem duplicar (CA-122) |
| CB-011 | Meta Selic com data futura (SGS 432) | truncar em `today` (CA-013) |
| CB-012 | FRED inacessível no ambiente | fallback Yahoo automático + registro (CA-048) |
| CB-013 | Ouro spot sem fonte confirmada | `BLOQUEADO — FONTE INDISPONÍVEL`; linha fora do heatmap (CA-050) |
| CB-014 | Nome de arquivo da Teva muda de versão | listar bucket + regex (CA-040) |
| CB-015 | Rótulos instáveis (`IMA-B` x `IMA - B`; `IEEX` x `IEE`; `IFIL` x `IFIXL`) | normalizador + mapa explícito de códigos (CA-032) |
| CB-016 | Número pt-BR com ponto de milhar (`"38.484,84"`) | normalizador único (CA-035) |
| CB-017 | Empate exato em `g_T`/`pi_T` na V1 | herda o sinal do trimestre anterior (CA-079) |
| CB-018 | Quadrante com `n < 5` | nenhuma conclusão afirmativa (CA-109) |

---

## 10. Anti-SPEC — o que o sistema NUNCA faz (seção sagrada)

> **Nenhum agente altera esta seção sem autorização humana explícita.** Toda feature **C** e **D** passa
> item por item por esta lista no QA do PR (`AGENTS.md §15`). Violação → `BLOQUEADO — ANTI-SPEC VIOLADA`.

### 10.1 Integridade do dado (o risco dominante do projeto)

1. **NUNCA inventar, interpolar, estimar ou "plausibilizar" dado** para fechar uma série. Lacuna sem
   substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`. Isso inclui backfill sintético de IFIX
   pré-2011, de segmentação de FII pré-2019 e de vértice longo nominal pré-2010.
2. **NUNCA misturar dado real e sintético** no mesmo DataFrame sem coluna de origem. Dado sintético só
   existe em `tests/fixtures/`, nomeado como tal.
3. **NUNCA tratar série de janela rolante como fonte de backfill** (ANBIMA `ms*.txt` e Curva Zero ~20 d.u.;
   FRED `SP500`/`DJIA` 10 anos; ICE BofA 3 anos).
4. **NUNCA preencher com `0`** célula ausente de resposta da fonte (feriado, dia inexistente, truncamento).
5. **NUNCA aceitar HTTP 200 como sucesso** sem validar o shape do corpo.
6. **NUNCA usar série descontinuada como se estivesse viva** (SGS 7801-7806 morto em set/2019; SGS IMA
   em 22/05/2023; IMA-C em 2021; EMBI+ em 30/07/2024; `DTWEXM` em 2019).

### 10.2 Look-ahead e honestidade estatística

7. **NUNCA classificar o trimestre T com dado divulgado depois do fim de T sem a flag `asof`.**
   A materialização `revised` existe, é legítima para descrição histórica, e é **sempre rotulada** —
   usá-la como se fosse operacional é proibido.
8. **NUNCA publicar célula com `n < 5` como conclusão** ("X é o melhor em Y"); e nenhuma célula, em
   nenhuma tabela, sai sem `n`.
9. **NUNCA ajustar a especificação de regime (k, limiar de delta Selic, eixos, nº de quadrantes) depois de
   olhar os retornos.** Mudança posterior nasce como V1.1 e as duas versões são reportadas.
10. **NUNCA apresentar o produto como preditivo.** O entregável é descritivo: "como performou", nunca
    "quanto vai render". Nenhuma linguagem de previsão nos outputs.
11. **NUNCA reportar Sharpe de índice como implementável** sem fricção (carteira teórica é revisada).
12. **NUNCA comparar total return doméstico com price return internacional** sem a flag `is_total_return`.
13. **NUNCA calcular excesso sobre CDI ou retorno real por subtração** — sempre razão.

### 10.3 Escopo e processo

14. **NUNCA usar fonte paga ou credencial** no caminho crítico (ANBIMA Feed, Bloomberg, Comdinheiro,
    MacroMicro, Cbonds). Qualquer uso de credencial/API paga é **classe D** e exige autorização humana.
15. **NUNCA redistribuir dado de terceiro sem licença** (Teva, FundsExplorer, Fundamentus, StatusInvest,
    Investidor10) — uso interno de validação, com a limitação declarada.
16. **NUNCA fazer backtest de estratégia, otimização walk-forward ou fronteira eficiente na entrega de
    2026-10-14.** Decisão D11: fora de escopo da v1.
17. **NUNCA alterar schema canônico, regra de alinhamento temporal ou cálculo de retorno fora de uma
    feature classe C** com Feature Contract, diff numérico vs. a versão anterior e reconstrução completa.
18. **NUNCA enviar qualquer número ao Alexandre/Comitê sem o fluxo classe D** (revisão humana + dataset
    congelado + hash + linha no log + rollback).
19. **NUNCA substituir fonte em silêncio.** Substituição exige `DECISIONS_LOG` **e** comunicação escrita
    ao Alexandre.
20. **NUNCA editar `ESCOPO-EMAIL-ALEXANDRE.md`, `PRD.md`, este SPEC ou esta Anti-SPEC**; nunca apagar ou
    sobrescrever arquivo de outro agente em `docs/research/`.

### 10.4 Padrões técnicos proibidos

21. **NUNCA commitar dado bruto** (> 5 MB, `*.parquet`, `*.duckdb`), `.env` ou credencial.
22. **NUNCA editar `data/` à mão** — todo conteúdo vem de script reprodutível e versionado.
23. **NUNCA chamar fonte externa em teste de CI** — só fixture gravada; rede apenas sob
    `@pytest.mark.network`.
24. **NUNCA inventar coluna de DataFrame** fora de `packages/shared/schemas/`.
25. **NUNCA desabilitar teste, usar `.skip`/`xfail` ou adicionar dependência nova** sem ADR.
26. **NUNCA confiar no encoding default do locale** (cp1252 no Windows): todo leitor declara o encoding.
27. **NUNCA scrapear HTML das páginas SPA** da B3 ou da ANBIMA Data, nem usar a API interna do portal
    ANBIMA protegida por reCAPTCHA de uso único.
28. **NUNCA armazenar trimestral como dado primário** — a granularidade nativa é a verdade; trimestral é
    agregação derivada.
29. **NUNCA criar `scripts/` na raiz, `state/`, `handoffs/` ou JSON de estado.**

### 10.5 Fora desta versão (v1, entrega de 2026-10-14)

- V1b (eixos vs. Focus) e V2 completa com teste de robustez.
- Dupla materialização `asof` x `revised` com relatório completo de divergência (v1 apenas **reporta** o
  percentual).
- EMBI/CDS, termos de troca na matriz, variância mínima por regime, fronteira eficiente.
- Clustering (GMM/k-means), HMM mensal, matriz de transição.
- Construção própria de FII (COTAHIST + CVM), setoriais B3 completos além dos listados.
- Dashboard, interface web, API, deploy, agendador (cron/Airflow).

---

## 11. Decisões provisórias — as 8 que bloqueiam e o valor assumido

> **Nenhuma destas respostas veio de humano.** O valor adotado é a **recomendação da pesquisa**, aplicada
> como padrão provisório para que a estrutura possa ser construída agora. Cada linha diz o que muda se a
> resposta for outra — por construção, **nenhuma exige retrabalho estrutural** (schemas e extratores não
> mudam; muda configuração, rótulo ou figura).
> Responder "aceito a recomendação" congela a decisão e muda o status dos ADRs de **Proposta** para
> **Aceito**.

| # | Decisão | Valor assumido (provisório) | ADR | O que muda se a resposta for outra | Custo da virada |
|---|---|---|---|---|---|
| **D1** | Lente de regime oficial do Comitê | **V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário** | ADR-001 | Se V2 for oficial: a tabela principal passa a ter 12 estados com `n` de 5-15 e metade das células entra em `ALERTA_N_BAIXO`. Se V3 for oficial: o entregável central passa a ser a lista de vizinhos, e o heatmap vira apoio | **baixo** — a mesma tabela `regimes` serve as três lentes; muda qual coluna vira eixo do heatmap (RF-033) e o que vai ao slide |
| **D3** | Eixo inflação da V1 | **aceleração (delta IPCA 12m)** | ADR-001 | Se for "nível vs. meta": precisa da **série histórica de metas do CMN** (gap G-02, hoje `a_confirmar`) e **os 83 rótulos mudam** | **médio** — re-roda a classificação e regenera todas as figuras; o schema não muda (`macro_quarterly` já tem `ipca_desvio_meta` e `ipca_12m_delta`) |
| **D5** | Métrica primária do heatmap | **excesso sobre CDI** | ADR-002 | Se for nominal: a comparação entre 2006 (Selic 19%) e 2020 (Selic 2%) deixa de ser defensável. Se for real: muda a leitura e depende do IPCA trimestral | **baixo** — as 3 métricas já são colunas de `asset_returns_quarterly`; muda 1 parâmetro da figura |
| **D6** | Internacional: estrutural, tático ou híbrido | **piso 16-20% + banda tática 15-35% por regime** | ADR-003 | Se for 100% tático: exige otimização por regime com n~20 (frágil) e a entrega passa a ser número pontual. Se for só piso: a análise por regime vira contexto | **baixo-médio** — RF-038 (retornos por regime) não muda; muda a formulação da recomendação em RF-039 |
| **D12** | Setoriais B3 e FII segmentado no pacote mínimo | **best-effort, com `n` e `data_inicio` visíveis** | ADR-005 | "Completo" acrescenta extratores ao caminho crítico de 3 dias. "Fora" remove F-012 e reduz o heatmap | **baixo** — cada setorial é uma linha a mais do mesmo extrator (RF-012); o corte é de escopo, não de arquitetura |
| **L1** | IFIX só existe de 2011 em diante | **janela própria 2011-2026 + IMOB (2008+) como proxy imperfeito; sem IFIX sintético** | ADR-005 | Se a decisão for painel balanceado estrito: **toda** a análise se restringe a 2011-2026 e a janela de 20 anos do e-mail cai | **alto se virar painel balanceado** (muda o universo de todas as tabelas); **baixo** na direção oposta |
| **L2** | FII segmentado via Teva (2019+, provedor privado sem licença explícita) | **usar para dispersão setorial, declarando ~2 ciclos macro; tratamento qualitativo** | ADR-005 | Se não autorizado: RF-014 sai e o e-mail (B5, segmentações) fica parcialmente não atendido, com justificativa | **baixo** — F-012 é `should` e isolada |
| **L4** | ETTJ oficial da ANBIMA (20 anos) exige o ANBIMA Feed (~R$ 686-8.238/mês) | **inclinação construída do Tesouro Direto; não contratar o Feed** | ADR-004 | Se o Feed for contratado: a curva passa a ser a Svensson oficial, vira **classe D** (credencial/API paga) e a inclinação histórica é recalculada | **médio** — a interface `inclinacao_*` em `macro_quarterly` não muda; muda a implementação da fonte |

**Decisões não bloqueantes** (D2, D4, D7-D11 e lacunas L3, L5-L13) seguem a recomendação do PRD §13.3 por
padrão e estão referenciadas nos RFs com `[PROVISÓRIO]` onde afetam comportamento.

**Gaps ainda abertos que a SPEC trata explicitamente:** G-01 (quais setoriais da B3 são retorno total —
`is_total_return` fica `a_confirmar` por índice), G-02 (série de metas de inflação), G-03 (ouro spot),
G-04 (rótulo de `PIB Total` no Focus), G-05 (convenção de `baseCalculo`), G-06 (conectividade ao FRED),
G-07 (código SGS antigo da DBGG). Nenhum deles está no caminho crítico do pacote mínimo.

---

## 12. Modelos de dados (visão funcional)

> Fonte de verdade: `packages/shared/schemas/` (pandera + pydantic). Espelho legível:
> `docs/contracts/CONTRACTS.md`. Base: `docs/research/metodologia-regimes-macro.md §6`.

| Entidade | Arquivo do schema | PK | Papel |
|---|---|---|---|
| `raw_series` | `raw_series.py` | `(series_id, date, vintage)` | toda série na granularidade nativa |
| `series_catalog` | `series_catalog.py` (+ `series_catalog_data.py`) | `series_id` | metadado e procedência de cada série |
| `ExtractorConfig` | `series_catalog.py` | — | config pydantic de um extrator (fonte, identificador, url, freq, início, unidade, transformação, lag) |
| `macro_quarterly` | `macro_quarterly.py` | `quarter` | 83 trimestres de variáveis macro |
| `asset_returns_quarterly` | `asset_returns_quarterly.py` | `(quarter, asset_id)` | retornos trimestrais por ativo |
| `regimes` | `regimes.py` | `quarter` | rótulos V1/V2 + escores contínuos |
| `regime_neighbors` | `regimes.py` | `(quarter_ref, rank, metrica)` | saída da V3 |

---

## 13. Rastreabilidade RF ↔ CA ↔ feature ↔ classe ↔ CI

| RF | CAs | Feature(s) | Classe | CI alvo | Pacote |
|---|---|---|---|---|---|
| RF-001 | CA-001..003 | F-003 | B | N1 | mínimo |
| RF-002 | CA-004..005 | F-004 | B | N1 | mínimo |
| RF-003 | CA-006..007 | F-003 | B | N1 | mínimo |
| RF-004 | CA-008..010 | F-004 | B | N1 | mínimo |
| RF-005 | CA-011..013 | F-003 | B | N1 | mínimo |
| RF-006 | CA-014..016 | F-003 | B | N1 | mínimo |
| RF-007 | CA-017..019 | F-010 | B | N1 | mínimo |
| RF-008 | CA-020..022 | F-005 | B | N1 | mínimo |
| RF-009 | CA-023..026 | F-016 | C | N2 | mínimo |
| RF-010 | CA-027..029 | F-009 | B | N1 | mínimo (urgente) |
| RF-011 | CA-030..033 | F-002 | B | N1 | mínimo |
| RF-012 | CA-034..037 | F-006 | B | N1 | mínimo |
| RF-013 | CA-038..039 | F-006 | B | N1 | mínimo |
| RF-014 | CA-040..042 | F-012 | B | N1 | mínimo (`should`) |
| RF-015 | CA-043..044 | F-003 | B | N1 | mínimo |
| RF-016 | CA-045..047 | F-007 | B | N1 | mínimo |
| RF-017 | CA-048..050 | F-011 | B | N1 | mínimo (`should`) |
| RF-018 | CA-051..052 | F-008 | B | N1 | mínimo |
| RF-019 | CA-053..055 | F-013 | C | N2 | mínimo |
| RF-020 | CA-056..058 | F-013 | C | N2 | mínimo |
| RF-021 | CA-059..061 | F-015 | C | N2 | mínimo |
| RF-022 | CA-062..064 | F-017 | C | N2 | mínimo |
| RF-023 | CA-065..068 | F-014 | C | N2 | mínimo |
| RF-024 | CA-069..071 | F-017 | C | N2 | mínimo |
| RF-025 | CA-072..074 | F-018 | C | N2 | mínimo |
| RF-026 | CA-075..077 | F-013, F-017 | C | N2 | mínimo |
| RF-027 | CA-078..081 | F-019 | C | N2 | mínimo |
| RF-028 | CA-082..083 | F-020 | C | N2 | mínimo (`should`) |
| RF-029 | CA-084..087 | F-021 | C | N2 | mínimo |
| RF-030 | CA-088..089 | F-019, F-021 | C | N2 | mínimo |
| RF-031 | CA-090..091 | F-019 (+ ADR-001) | C | N2 | mínimo |
| RF-032 | CA-092..094 | F-022 | C | N2 | mínimo |
| RF-033 | CA-095..097 | F-023 | B | N1 | mínimo |
| RF-034 | CA-098..099 | F-024 | B | N1 | mínimo |
| RF-035 | CA-100 | F-025 | B | N1 | mínimo |
| RF-036 | CA-101..102 | F-021 | C | N2 | mínimo |
| RF-037 | CA-103 | F-024 | B | N1 | mínimo (`should`) |
| RF-038 | CA-104..105 | F-026 | C | N2 | mínimo |
| RF-039 | CA-106..107 | F-026 | C | N2 | mínimo |
| RF-040 | CA-108..109 | F-022, F-023 | C/B | N2 | mínimo |
| RF-041 | CA-110..111 | F-027 | B | N1 | mínimo |
| RF-042 | CA-112 | F-028 | B | N1 | mínimo |
| RF-043 | CA-113..114 | F-031 | D | N3 | mínimo |
| RF-044 | CA-115..116 | F-031 | D | N3 | mínimo |
| RF-045 | CA-117 | F-031, F-032 | D/A | N3 | mínimo |
| RF-046 | CA-118..119 | F-029 | C | N2 | mínimo |
| RF-047 | CA-120 | F-013 | C | N2 | mínimo |
| RF-048 | CA-121..122 | F-029 | C | N2/N3 | mínimo |
| RF-049 | CA-123..124 | F-001, F-030 | B | N1 | mínimo |
| RF-050 | CA-125..126 | F-030 | B | N1/N2 | mínimo |
| RF-051 | CA-127 | F-030 | B | N1 | mínimo (`should`) |
| RF-052 | CA-128 | F-032 | A | N1 | mínimo |

**Cobertura: 52/52 RFs com CA e com feature.** 128 CAs. Nenhum RF órfão.

---

## 14. Aprovação

- [x] 52 RFs traduzidos em comportamento verificável, cada um com >= 1 CA numerado
- [x] 128 CAs em Given/When/Then compacto, cada um mapeável a um `pytest`
- [x] 18 casos de borda mapeados
- [x] **Anti-SPEC (§10) escrita — 29 proibições + fora de escopo da v1**
- [x] §11 lista as 8 decisões bloqueantes com valor provisório e custo de virada
- [x] Modelos de dados apontando para `packages/shared/schemas/`
- [x] Rastreabilidade RF ↔ CA ↔ feature ↔ classe ↔ CI completa
- [ ] **SPEC revisada e aprovada por Eduardo (Edu)** — pendente
- [ ] **8 decisões bloqueantes respondidas; ADR-001..006 passam de Proposta a Aceito** — pendente

---

*Próximo passo: `docs/contracts/CONTRACTS.md` (espelho de `packages/shared/schemas/`) e o `TODO.md` com as
features classificadas. Esta SPEC e sua Anti-SPEC só mudam com autorização humana.*
