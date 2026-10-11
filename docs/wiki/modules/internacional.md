# Módulo `internacional` — Yahoo, MSCI, FRED (bloco C) + o dimensionamento de F-026

> Verdade: `apps/pipeline/extract/{yahoo,msci}.py` + `apps/pipeline/transform/cambio.py` +
> `research/fontes-de-dados.md §C10-C11`. **Estado (2026-10-11): Yahoo e MSCI implementados**
> (F-007, aguardando QA da Onda 1); **FRED bloqueado nesta máquina** (F-011). Responde ao item **C1**
> do e-mail, com as séries na moeda original e as versões em BRL como séries **derivadas separadas**.
> **F-026 (implementada em 2026-10-11)** usa essas séries para responder ao *tamanho* da alocação:
> `stress_flag`, correlações condicionais e a **faixa** de D6 — ver a seção final deste arquivo.

| `series_id` | linhas | janela | nulos | canário (2006-01-31) |
|---|---|---|---|---|
| `YAHOO_GSPC` | 5.729 | 2004-01-02 → 2026-10-09 | 0,00% | **1280,079956** |
| `YAHOO_TNX` · `VIX` · `DXY` | 5.729 · 5.941 · 6.952 | idem | 0,09% · 3,53% · **17,41%** | 4,527 · 12,95 · 88,96 |
| `MSCI_ACWI_NETR` | 6.726 | **2000-12-29** → 2026-10-09 | 0,00% | **121,3858** |
| `MSCI_WORLD_NETR` · `USA` · `EM` | 6.726 cada | idem | 0,00% | 2.895,0792 · 2.802,4606 · 266,2901 |
| `SP500_BRL` · `ACWI_BRL` (derivadas) | 5.572 · 5.719 | 2004-01-02 → 2026-10-09 | 0,00% | 157 · 1.007 dias sem PTAX |

Todas com as duas pontas do 1T2006 (62-78 obs), monotônicas, sem data repetida. A janela começa em
**2004-01-01** de propósito: folga de 2 anos para a variação de 12 meses e mesma borda da PTAX de
F-003. MSCI `NETR` começa em 2000-12-29 com `level_eod = 100,0` no ACWI e no EM (base); `STRD`
começaria em 1997 e **não** é a usada. Canários conferidos contra **outra superfície** da mesma fonte
(diário × `interval=1mo`; diário × `END_OF_MONTH`), não contra o mesmo payload.

## As decisões que mudam número

- **A série fica na moeda original (USD); BRL é série derivada separada** (`fonte=DERIVADO`), nunca
  coluna nem substituição — §10.4.28 vale para moeda como para frequência. Catálogo: 132 → **134** (D-d).
- **`is_total_return` mora no catálogo**, porque `ProcessedSeriesSchema` não tem essa flag.
  `SP500_BRL` é **price return** declarado; o comparável de total return do IMA-B/IFIX é `ACWI_BRL`
  (NETR) e, para os EUA, `MSCI_USA_NETR`. A conversão **levanta** se a flag vier `None`.
- **Conversão = `nivel_usd × PTAX(mesmo dia)`, `inner join` exato** (PTAX venda `BCB_SGS_1`, F-003):
  sem `ffill`, sem interpolação, sem `0`. Dia sem PTAX **sai** da série e a contagem vai no relatório
  — 157 no `SP500_BRL` (feriado brasileiro com pregão em NY) e 1.007 no `ACWI_BRL` (os mesmos **mais**
  os ~785 dias antes do início da PTAX). Mora em `transform/cambio.py` (D-g); a derivada **herda**
  `collected_at`/`vintage` da série em USD.
- **`^FVX`, `^IRX`, `MSCI_BRAZIL` e `GOLD_BRL` ficam fora:** `TICKERS` só tem séries `status=ok` e
  acrescentar ticker é F-011. `MSCI_BRAZIL` (`705000`) devolve lista vazia (`a_confirmar`);
  `GOLD_BRL` segue `BLOQUEADO — FONTE INDISPONÍVEL` (G-03).

## Armadilhas

- **Yahoo sem UA → 429** (retry com backoff). **`range=max` trunca e rebaixa** (169 pontos contra 490
  com `period1`/`period2`) e a fonte respondeu `dataGranularity="3mo"` **ignorando o `interval=1mo`**
  → nenhuma função emite `range`, e o parser recusa granularidade ≠ `1d`. **200 com 1 ponto**
  (`SMLL.SA`) é pego pela contagem de não nulos.
- **`timestamp` não é data:** a data de pregão é `timestamp + meta.gmtoffset`. **`adjclose` ≠ `close`
  = provento:** idênticos nos índices, 126,83 contra 86,78 no `IVV` real de 03/01/2006 → **levanta**.
- **A resposta do Yahoo não é byte-estável** (ordem das chaves de `meta.currentTradingPeriod` alterna
  com `close` idêntico) → `_arquivar_retrato` compara a série `(date, value)` e **mantém o retrato
  original**; valor revisado continua levantando `ConteudoDivergente`.
- **MSCI erra com 200 e chave que a infra não conhece** (`error_code`, não `error`) → guarda própria;
  **código inexistente → 200 com `INDEX_LEVELS: []`**; `start_date` < 1997-01-01 é recusado com 200 →
  validado **antes** de ir à rede. **`^TNX` veio em % a.a. direto** (5,244 em 09/10/2026) — o erro
  clássico do ticker é o ×10; reconferir em F-011 contra `DGS10` se o FRED voltar.
- **R5 · FRED bloqueado na camada de aplicação** (TLS completa, HTTP dá ReadTimeout e
  `ConnectionReset`, 3/3): F-011 começa por teste de conectividade e falha explícita, nunca fallback
  silencioso (S-09; `DFF`/`FEDFUNDS` sem substituto equivalente).

---

## F-026 — o dimensionamento: `stress_flag`, correlações e a faixa (RF-038/039)

`apps/pipeline/canonical/internacional.py` + `packages/shared/schemas/internacional.py`
(`CONTRACTS.md §6a`). Build: `python -m apps.pipeline.canonical.internacional --offline`, ou a etapa
`internacional` de `python -m apps.pipeline run --offline`. Saídas:
`internacional_por_regime.parquet` (**54 × 18**), `internacional_pesos.parquet` (**624 × 13**,
⚠️ **não publicável**) e `relatorio_internacional.json`.

**CA-104 é cumprido por `import`, não por texto:** as colunas de retorno saem **inteiras** de
`metricas_regime.metricas_da_celula` (F-022), com o **mesmo** mapa regime → trimestres e os
**mesmos** vizinhos. Resíduo medido contra `regime_asset_metrics.parquet`: **0,0 em 24 células**, e
há teste de acervo que **falha** se alguém reimplementar o cálculo aqui.

### A regra de `stress_flag` (D6-a) — a definição que RF-039/CA-106 não fechava

```
stress(T) =  Δincl(T) < −1 × σ_expanding(Δincl até T−1)      ← ramo 1 (min. 8 obs. anteriores)
          OU usdbrl_var_tri(T) > +10,0 %                     ← ramo 2
          [OU EMBI sobe > 1 d.p.]                            ← ramo 3: DECLARADAMENTE FORA
```

Três ambiguidades, três escolhas declaradas: a inclinação é a **`INCLINACAO_REAL_5A_3A`** (a
principal de **D-i**, 95,25% de cobertura, lida de `raw_series` pela função que **F-021 publica**);
o desvio é **expanding até T−1** (com amostra cheia a regra "saberia" a volatilidade de 2026 ao
marcar 2008 — look-ahead na própria marcação do evento); e "cai" é sobre a **variação**, não o
nível (nível baixo não é evento; achatamento abrupto é). **Ramo EMBI fora com o número que prova:**
`embi_delta_tri` tem **0** valores não nulos nos 83 trimestres (o EMBI+ morreu em 30/07/2024), e a
coluna `ramo_embi` existe e é sempre `False` para que a ausência seja **visível**.

**Medido:** `stress_flag = 1` em **20 de 83** (24,1%) — 7 só pelo ramo da inclinação, 11 só pelo do
câmbio, 2 pelos dois (`2015Q1`, `2020Q1`). **14 não avaliáveis** pelo ramo 1 (`2006Q1..2008Q1`, o
aquecimento do expanding; `2020Q3..2021Q3`, o buraco da 5a−3a) — e **trimestre não avaliável ≠
trimestre sem stress**, o que a saída nomeia um por um. Validação externa que **não** calibrou a
regra: **9 dos 10 piores trimestres do IBOV** estão marcados; o único que escapa é `2010Q2` (IBOV
−13,4% com USDBRL +1,2%). Isto **destrava** `RegimesSchema.stress_flag`
(`serie_de_stress_flag` devolve a `Series` que `montar_regimes` espera) — resta `regime_v1` não
anulável (**D-m**), e por isso `regimes.parquet` segue não gravado.

### O achado central (CA-105): o dólar paga **durante** o stress, não depois

| `corr(USDBRL, IBOV)` em `ret_tri` | valor | `n` |
|---|---|---|
| trimestres de **stress** | **−0,795** | 20 |
| trimestres de **não stress** | **−0,418** | 62 |
| janela inteira 2006-2026 | −0,710 | 82 |
| 10 piores trimestres do IBOV | −0,625 | 10 |

O hedge funciona **quase o dobro** no stress. Mas em **T+1** depois de um trimestre de stress
**tudo** subiu, e o IBOV subiu quase tanto quanto o internacional (+2,26% contra +2,30% de excesso
do `SP500_BRL`); `USDBRL` é o **único** ativo com excesso **negativo** após não stress (−1,46%) — o
custo de carregar o hedge nos 62 trimestres calmos. **Leitura honesta:** o dado **não** apoia
"aumentar internacional quando `stress_flag=1`" como regra de *timing*; apoia **carregar** a
exposição cambial de forma estrutural. Nos 20 de stress, `r_IBOV = −8,07%` e `r_USDBRL = +10,68%`
⇒ **x = 43,0%** de USD zera o retorno **médio** da mistura — aritmética sobre duas médias medidas,
**não** otimização, **não** backtest, sem posição nem rebalanceamento.

### Universo: por que o representativo é `ACWI_BRL` e não `SP500_BRL` (D6-b)

`IBOV`, `IMAB` e `CDI` são **total return**; `SP500_BRL` é **price return**. Montar covariância
misturando os dois é exatamente o que **Anti-SPEC §10.2.12 / CA-064** proíbe — então a carteira de
variância mínima é `{CDI, IMAB, IBOV, ACWI_BRL}` e `SP500_BRL` fica na tabela de retornos com a
flag visível, **nunca somado**. `SP500_USD` fica fora da tabela de propósito (mesma série em outra
moeda), e a identidade `(1+SP500_BRL) = (1+SP500_USD)(1+USDBRL)` é conferida: resíduo máximo
**2,22e-16** em 82 trimestres. `IFIX` fica fora da carteira (63 de 83 trimestres, L1).
Sem fonte, saem `BLOQUEADO — FONTE INDISPONÍVEL`: `GOLD_BRL` (G-03), `UST10_BRL` e `SP500_HEDGE`
(**D7**) — e *hedgeado* × *sem hedge* são **categorias diferentes**, nunca somadas nem comparadas.

### A faixa de D6 (D6-c) — e por que não é um número

```
piso ESTRUTURAL : 16% – 20%   (FGVcef; independe de regime e de n)
banda TÁTICA    : 15% – 35%   (ADR-003; onde dentro dela, o regime informa)
peso do regime  : variância mínima TRUNCADA na banda
faixa publicada : [ min(piso_min, peso), max(piso_max, peso) ]
```

Com `cap = 0,40` por ativo, o internacional sai entre **15,91%** (`ESTAGFLACAO`) e **23,58%**
(`RECUPERACAO`) — nenhum dos 4 precisou de truncamento. **Sem cap**, o *expanding* médio
2006-2026 cai de **19,65% para 10,41%**. Um número que quase dobra por causa de uma restrição de
apresentação **não é um número** — é por isso que CA-107 entrega **faixa**, com `n` de 13 a 19 por
regime e `p = 4` ativos. Nota que contraria a intuição e está na docstring com o número: **sem cap a
carteira não degenera em 100% CDI** — o shrinkage (ρ de 0,25 a 0,60) puxa a covariância para a
esfera e o CDI fica em 37%-50%.

> ⚠️ **`internacional_pesos.parquet` está FORA da entrega v1 (D6-d) e marcado `publicavel: false`
> no `MANIFEST.json` (D-af).** Variância mínima por regime é nomeada em **Anti-SPEC §10.3.16/§10.5**
> como fora desta versão (→ **F-035**). A tabela é calculada porque é o insumo da faixa, e nasce
> isolada: `especificacao_congelada = False` nas 624 linhas, `WARNING` em toda execução, **nenhuma**
> coluna onde escrever previsão (com teste de contrato que falha se acrescentarem uma) e **nenhum
> backtest**. Publicar qualquer número dela exige ADR-003 aceito **e** autorização escrita sobre a
> Anti-SPEC. **F-031 não a inclui.** O que **é** publicável depois dos ADRs: os retornos por regime,
> as correlações, o `stress_flag` e a **faixa**.

**Método da variância mínima, para quem for revisar:** covariância com shrinkage de Ledoit-Wolf
**importado de F-021** (`rho` medido, não escolhido) + minimização **exata** de `w'Σw` sujeito a
`1'w = 1` e `0 ≤ w ≤ cap`, por **enumeração de conjunto ativo** (`3^p`; com `p = 4` são 81 sistemas
5×5). Sem solver externo, sem iteração, sem tolerância a calibrar. O QA reconferiu por 3 caminhos
independentes (LW com laço explícito, busca em grade na simplex e KKT à mão): **dif 0,0** nos 4
pesos.

**Features:** **F-007** (implementado) · **F-011** (bloqueado) · **F-017** · **F-026** (implementada) · ~~F-030~~ (cortada da v1).
