# Módulo `focus` — expectativas de mercado (BCB Olinda / OData v4)

> Verdade: `apps/pipeline/extract/bcb_focus.py` + `research/fontes-de-dados.md §A2`.
> **Estado (2026-10-11): F-010 implementada, QA pendente.** É a **única** fonte do projeto **sem
> look-ahead** — a mediana da pesquisa do dia X era conhecida no dia X
> (`metodologia-regimes-macro.md §1.5`, §5.1: "preferir Focus ao realizado sempre que possível").

## `data/processed/focus/` — 5 EntitySets, **197 `series_id`**, **150.120 linhas**, 0,00% de nulos

| Parquet (= entrada do catálogo) | `series_id` | linhas | janela |
|---|---|---|---|
| `FOCUS_ANUAIS` (`ExpectativasMercadoAnuais`) | 8 | 45.294 | 2004-01-02 → **2026-10-02** |
| `FOCUS_MENSAIS` | 2 | 11.420 | idem |
| `FOCUS_TRIMESTRAIS` | 3 | 15.324 | idem |
| `FOCUS_SELIC` (por reunião do Copom) | **182** | 66.662 | 2004-11-18 → 2026-10-02 |
| `FOCUS_INFLACAO_12M` | 2 | 11.420 | idem |

As 11 séries densas têm **5.710** observações contra **5.714** dias úteis da ANBIMA (F-008): as 4
ausências são **todas de 2004**, e **nenhuma** data do Focus cai fora do calendário de dia útil. 2006
tem **249** observações — o mesmo 249 do CDI. Fora de `raw_series` por **D-k** (`series_id` composto
não é entrada do catálogo, como `td_painel.parquet`); F-015 consome de `data/processed/focus/`.

## A convenção de data e horizonte — **exceção explícita a D-a** (ler antes de alinhar)

- **`date` = o dia da pesquisa**, não fim de período. Converter colapsaria `H0` e `H1` na mesma data
  e mentiria sobre quando o número era conhecido. `freq = D`, `value = Mediana`, `baseCalculo = 0`.
- **O horizonte vive no `series_id`:** `FOCUS_<ESCOPO>_<INDICADOR>_<CHAVE>`, com
  `ESCOPO ∈ {A, M, Q, I12, RCOPOM}` e `CHAVE ∈ {H0, H1, HM1, S, N, R<n>-<ano>}`. Use
  `decompor_series_id`, **nunca** `split("_")`.
- **Régua de F-015: a última coleta até o último dia útil de `T−1`** ("a coleta do início de T",
  `metodologia §2`), com **troca de `H0` para `H1` quando `T` é 1º trimestre** — a coleta cai em
  dezembro do ano anterior, e sem a troca `focus_pib_ano` de 1/4 das linhas traria o ano que acabou.
  Canário: `focus_ipca_12m` de `2026Q3` = **4,19** (coleta de 30/06/2026).
- **Procedência aponta para o EntitySet** (`FOCUS_ANUAIS`), não para `FOCUS_A_SELIC_H0` — é o que
  mantém CA-120 resolvível no catálogo.

## Armadilhas (medidas, não herdadas)

- **Espaço no `$filter`/`$orderby` tem de ser `%20`, nunca `+`** — `params=`/`urlencode` manda `+` e o
  backend responde **HTTP 400**. Use `montar_url`; **nunca** passe `params=` ao `ClienteHTTP` aqui.
- **`$top=20000` trunca em silêncio, sem `@odata.nextLink`** (CA-018): 32.582 linhas viram 20.000.
  Três camadas de defesa; nunca aumente o `$top` "para ir mais rápido".
- **Erro é JSON dentro de comentário `/*{...}*/`, sem `Content-Type`**, e o sucesso **não é array**
  (`{"@odata.context":…, "value":[…]}`) — `validar_corpo_json_array` recusaria a resposta **boa**;
  use `validar_corpo_odata`.
- **G-05:** `baseCalculo=1` (5 dias úteis) **só existe de 2014 em diante** — `0` é a única base com
  os 20 anos, e sem o filtro a série **dobra** de 2014 em diante.
- **G-04:** o rótulo do PIB é **`PIB Total`**; o conjunto de indicadores **muda ao longo da série**, e
  indicador inexistente devolve **HTTP 200 com `{"value":[]}`** — vazio silencioso, não erro.
- **`DataReferencia` troca de formato por EntitySet** e **sem** zero à esquerda no trimestral
  (`'2026'`, `'09/2028'`, `'3/2026'`, `'R1/2027'`) — regexes separados; fora do padrão levanta.
- **Horizonte negativo é real:** `HM1` trimestral é estrutural e **está** no pacote; o anual é
  sazonal (começo de janeiro) e **não** é gravado, só contado em `fora_do_horizonte`.
- **Janela estrutural ≠ lacuna:** `FOCUS_Q_PIB_TOTAL_HM1` (3.904 linhas, vão 39 d) e
  `FOCUS_A_SELIC_H0` (5.342, vão 40 d) têm buraco **por desenho** — `GAP_MAXIMO_FOCUS_DIAS = 120` é
  frouxo de propósito, pega fatia de ano perdida e não feriado.
- **`fatiar_por_ano`, não `fatiar_janela`** (torna 20 das 23 fatias byte-idênticas por rodada);
  `para_float_ponto_decimal`, nunca `para_float_ptbr`; `data/raw/focus/` tem 66 MB; e a última
  pesquisa **não é "hoje"** — o máximo de `Data` é **2026-10-02**.

**Fora de escopo hoje:** `ExpectativasMercadoInflacao24Meses`, Top5/V1b (F-033) e os indicadores além
do pacote mínimo — cada um é **1 linha em `PLANO`**, enumerados em `INDICADORES_ENUMERADOS`.

**Features:** **F-010** (extrator) · **F-015** (consumo e régua) · F-021/F-033 (surpresa, V1b).
