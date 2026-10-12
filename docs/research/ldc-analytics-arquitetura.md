# Pesquisa de arquitetura — **LDC Analytics** (portal interno de ferramentas quant)

**Data:** 2026-10-11 · **Autor:** agente de pesquisa de arquitetura · **Status:** pesquisa, não decisão
**Escopo:** como hospedar o portal interno da LDC Capital que recebe, como **primeiro módulo**, o modelo
de alocação macro (regime × ativo) hoje implementado como pipeline Python neste repositório.
**Irmãos:** `ldc-analytics-identidade.md` e `ldc-analytics-produto.md` (outros agentes — não escrevo neles).

> **Convenção de evidência:** **[✓]** = li a página citada nesta sessão (URLs em §9) ·
> **[~]** = conhecimento geral, não conferido agora (trate como hipótese) ·
> **[⌁]** = número que eu mesmo medi neste repositório.

---

## 0. O fato de partida que muda a resposta inteira

Antes de comparar tecnologia, **medi o dataset**. O enunciado diz "~10 MB"; em disco **[⌁]**:

| Recorte | Tamanho | Observação |
|---|---|---|
| `data/canonical/` inteiro | **26 MB** | inclui `entrega/` (18 MB, pacote do Comitê) e `figuras/` (4,1 MB de PNG+SVG) |
| Todos os Parquet da raiz | **3,02 MB** | **2,45 MB são `raw_series.parquet`** (278.439 linhas, 62 séries) |
| **Parquet que um portal regime × ativo consome** | **≈ 610 KB** | soma abaixo |

Soma do recorte útil **[⌁]**: `macro_quarterly` 44,8 KB + `macro_quarterly_asof` 44,8 + as 2
procedências 20,3 + `asset_returns_quarterly` 133,8 + `regimes_v1` 12,8 + `regimes_v1_asof` 12,8 +
`regime_neighbors_v3` 77,3 + `regime_neighbors` 33,5 + as 3 `regime_asset_metrics*` 74,3 + os 2
`internacional_*` 28,4 + `alinhado_trimestral` 55,8 + `figuras/heatmap_dados` 56,4 +
`figuras/timeline_regimes_dados` 13,5 = **608,5 KB**.

**Consequência dura:** a tabela principal tem **83 linhas** e o dataset de apresentação cabe em
**menos de 1 MB** — menos que o bundle de React + Recharts. Toda a discussão "como consultar Parquet
remoto sem baixar tudo" responde a uma pergunta que este projeto **não tem**. O problema real é
**versionamento, procedência e gate de publicação** — é aí que a arquitetura deve gastar
complexidade. `raw_series.parquet` (2,45 MB) é a única tabela onde consulta parcial começaria a fazer
sentido, e ela não é tela de portal: é insumo de pipeline.

---

## 1. Como servir Parquet a um front estático — 5 opções

| Opção | Bundle extra | Latência | Limite prático | DX | Custo | Adequação a 610 KB / 83 linhas |
|---|---|---|---|---|---|---|
| **(a) DuckDB-WASM + HTTP range** | **~2,8 MB gzip** (~35 MB cru, 4,8 MB brotli) + 1-2 MB de extensões [✓] | cold start **150-300 ms**; 1ª query **~40 ms**, depois **~6 ms** [✓] | GB-TB; teto de **4 GB de RAM**, single-thread por padrão [✓] | SQL completo no browser | zero | **sobredimensionado** — o engine pesa 5× o dado |
| **(b) hyparquet / parquet-wasm** | **hyparquet 9,7 KB min+gz, zero dependência** [✓]; `parquet-wasm` é WASM, muito maior [~] | sem passo de init (JS puro) [✓] | dezenas de MB; **sem SQL** | parser: devolve objetos ou colunas | zero | **adequado** se quiser manter Parquet como contrato |
| **(c) Pré-computar JSON por visão no build** | **0 KB de runtime** | só o CDN (~20-80 ms TTFB) [~] | poucos MB por visão | mais simples; só o build conhece Parquet | zero | **o melhor encaixe** |
| **(d) API serverless lendo Parquet** | 0 no cliente | cold start **sub-100 ms a >1 s**, ∝ bundle [✓] | **payload 4,5 MB**; bundle 250 MB; 2 GB RAM (Pro 4) [✓] | precisa de `pyarrow`/`duckdb` no bundle | invocações do Pro [✓] | **desnecessário e pior** |
| **(e) Banco (Supabase/Postgres, MotherDuck)** | 0 | ~50-200 ms + região [~] | ilimitado | migrations, credencial, backup | Supabase Pro **US$ 25/mês**; MotherDuck free = 3 usuários/10 GB/10 CU-h, degrau seguinte **US$ 250/mês** [✓] | **vetado por ADR-007 (Aceita)** |

**(a) DuckDB-WASM.** Maduro: Arrow como protocolo, `SELECT count(*) FROM 'file.parquet'` respondido
**só com o metadado**, row groups inteiros pulados em query remota [✓]. Limites documentados:
single-thread por padrão, 4 GB de RAM, e "comportamento de leitura parcial em HTTP(S) depende da
implementação" [✓] — e esse último é real: há projetos de 2026 que descobriram o DuckDB-WASM
baixando **45,6 MB onde 7,3 MB bastariam**, por não emitir range requests, com bug aberto
(`duckdb-wasm#2228`) contornado à mão [✓]. **Veredicto:** ferramenta excelente, errada para este
dataset — pagar 2,8-4,8 MB de engine para consultar 610 KB inverte a conta.

**(b) hyparquet.** 9,7 KB min+gzip, zero dependência, JS puro, sem init WASM, range requests e
callbacks de streaming (`onChunk`/`onPage`/`onComplete`) [✓]. **Não faz SQL** — o `group by` é seu.
Snappy e sem-compressão nativos; gzip/brotli/zstd/lz4 via `hyparquet-compressors` [✓]. O README
avisa: Parquet é colunar e transpor para linhas em JS é caro — use os callbacks colunares [✓].
**Veredicto: segunda escolha**, e a ponte natural quando a (c) apertar.

**(c) JSON por visão no build.** Para 83 × 42 e 1.963 linhas de retorno, é o caminho reto: um script
Python lê os Parquet **congelados** e escreve `views/*.json` já no shape da tela. Três vantagens que
importam **aqui**: (1) o front **nunca** vê Parquet, logo nunca reimplementa semântica de coluna — e
`CONTRACTS.md` é explícito que `macro_quarterly` está em **por cento/pp** e
`asset_returns_quarterly` em **fração**, com `cdi_tri`/`ipca_tri` **com o mesmo nome em escalas
diferentes** [⌁]; errar isso no browser é erro de 100×; (2) o gerador é o único lugar onde o **gate**
(`especificacao_congelada`, `publicavel`, travas de `n`) é aplicado, em Python, com o código que já
existe; (3) zero runtime, zero cold start, cacheável como imutável. Custo: toda visão nova exige
regenerar — aceitável quando o dado muda **por trimestre**. **Veredicto: recomendada.**

**(d) API serverless.** Limites [✓]: payload **4,5 MB**, bundle 250 MB, 2 GB RAM (Pro 4 GB), 800 s,
cold start "sub-100 ms a ~1 s" ∝ bundle. Ler Parquet exige `pyarrow`/`duckdb` no bundle (pesado ⇒
cold start pior). E o problema é conceitual: **o dado é imutável e minúsculo**; uma função que o relê
a cada request só adiciona latência e modos de falha sobre algo que o CDN serve de graça. **Não usar
para dado** — reservar serverless para o que só ela faz: sessão/auth, ou (futuro) simulação com input.

**(e) Banco.** Já decidido: **ADR-007 — "Sem Supabase (nem banco remoto) na v1", Aceita** [⌁]. O
portal **aciona 2 dos 3 gatilhos de reavaliação** ("dashboard multiusuário", "atualização consumida
por outras pessoas") — mas reabrir ≠ aceitar: nenhum gatilho pede banco para **servir 610 KB
congelados**; eles pedem banco quando houver **estado de usuário** (carteiras, teses, histórico de
simulações). MotherDuck: o Lite de US$ 25/mês **deixou de existir** (virou free, 3 usuários/10 GB/10 h
de Pulse) e o degrau seguinte é **Business, US$ 250/mês + compute** [✓] — desproporcional para servir
um arquivo de 44 KB a um comitê de poucas pessoas.

### 1.1 Recomendação, e onde ela deixa de servir

> **(c) pré-computar JSON por visão no build, com (b) hyparquet como porta de saída.**

O build gera, a partir dos Parquet **congelados por tag**, `public/data/<tag>/` com `manifest.json`
(tag, `DATASET_SHA256`, `especificacao_congelada`, contagens, data do dado) + um JSON por visão
(`regimes_timeline`, `heatmap_regime_ativo`, `ranking_atual`, `vizinhos`, `internacional`,
`macro_series`). Ordem de grandeza esperada: **200-400 KB, 60-120 KB gzip** [~].

**Deixa de servir quando** (qualquer um basta):
1. **Dado de apresentação > ~20-30 MB** ⇒ Parquet + hyparquet; **> ~200 MB ou consulta ad hoc sobre
   série diária** (backtest, `raw_series` crescendo) ⇒ **DuckDB-WASM**.
2. **O usuário passa a compor a query** ("excesso sobre CDI de qualquer ativo em qualquer
   subconjunto filtrado por 6 variáveis macro") — visões pré-computadas explodem
   combinatorialmente; isso é SQL.
3. **Aparece estado de usuário** ⇒ precisa de escrita ⇒ reabre ADR-007 de verdade, com Postgres como
   **materialização a jusante**, nunca como fonte (o próprio ADR-007 fixa isso).
4. **Atualização intradiária** — o padrão "snapshot imutável por tag" perde sentido e entra API.

---

## 2. Padrão "dataset versionado + site estático"

### 2.1 O que o projeto já tem — e que é melhor que a maioria dos data apps

`apps/pipeline/run.py` já implementa **[⌁]**: `run --offline` (13 etapas, sem rede) → `verify`
(`rc != 0` se um byte divergir; pega byte alterado, artefato ausente, artefato novo não listado,
agregado divergente **e Parquet ilegível**) → `freeze --tag` (`MANIFEST.json` + `FROZEN.txt`). O
manifesto traz, por artefato, `sha256`, bytes, linhas, colunas, min/max da data, **% de nulos por
coluna**, `versao_build`, `data_do_dado` e o agregado `DATASET_SHA256` em formato `sha256sum` —
**reproduzível na linha de comando**. Dois campos valem ouro para o portal: **`determinista: false`**
(só o `ldc.duckdb`) e **`publicavel: false`** (hoje `internacional_pesos.parquet`). Valor atual:
`fc2331183b9355e6424f223085fd501683678d73fc50a9cf2b570376750f17ef`. Isso é, literalmente, um
**content-addressed dataset release**: o portal não precisa inventar versionamento — precisa **não
quebrá-lo**.

### 2.2 Onde hospedar os arquivos

| Onde | Custo | Imutabilidade | Veredicto |
|---|---|---|---|
| **No bundle** (`public/data/<tag>/`) | zero | total: cada deploy Vercel tem URL imutável, e asset com hash leva `Cache-Control: max-age=31536000, immutable` [✓] | **recomendado para o MVP.** 600 KB num repo é nada; dado e código versionam juntos; rollback = redeploy antigo ou `git revert` |
| **Cloudflare R2** | free até **10 GB, 1 M writes, 10 M reads/mês, egress sempre US$ 0** [✓] | boa, chave por tag | **a escolha ao sair do bundle** — egress zero é a diferença contra S3 |
| **Vercel Blob** | **US$ 0,023/GB-mês + US$ 0,05/GB de transferência**; Pro inclui 5 GB e 100 GB [✓] | boa | funciona, mas paga egress onde R2 não paga |
| **GitHub Release por tag** | zero; **2 GB por arquivo, sem limite de total nem de banda** [✓] | **máxima** — a tag git nomeia a versão | **ótimo arquivo morto/auditoria** (anexar o `.zip` do pacote + `HASHES.txt`). Não serve de origem do front (sem CORS garantido nem CDN pensado p/ isso [~]) |

**Padrão recomendado:** dado no bundle sob `public/data/<tag>/`; **`latest` é ponteiro, não
diretório** — `public/data/current.json` com `{ "tag": …, "dataset_sha256": … }`. O front lê
`current.json` (curto, `no-cache`) e só então busca `data/<tag>/*.json` (longo, `immutable`). Isso
mata o problema clássico de CDN servindo versão velha: **um** arquivo pequeno é revalidável; todo o
resto é imutável por construção, porque o caminho contém a tag.

**Regra de coerência, não negociável:** o front **nunca** monta tela com dois `tag`. Carrega
`current.json` uma vez por sessão, **fixa** a tag, e toda requisição daquela sessão usa aquela tag.
Manifest divergente ⇒ banner "a versão mudou, recarregue" e **nada renderizado misturado**.

**Hash visível:** rodapé fixo em **toda** tela —
`dataset comite-2026-10-14 · sha256 fc233118… · dado até 2026-10-10 · 83 trimestres`, com o hash
completo copiável. É o equivalente web do `FROZEN.txt`.

### 2.3 Vale usar um framework de data app em vez de construir em Vite+React?

| Framework | O que é | Prós aqui | Contra decisivo |
|---|---|---|---|
| **Observable Framework** | gerador estático para data apps; **data loaders em qualquer linguagem** rodam no build e salvam arquivo; recomenda bundlar só o subconjunto necessário e combina com DuckDB+Parquet para range requests [✓] | o data loader **é** o padrão §1(c), já resolvido; Observable Plot é muito bom | impõe o runtime reativo do Observable; a stack LDC é Vite+React+TS+Tailwind+Recharts, e o portal receberá **simulação e validação de teses** — apps de formulário e estado, não documentos |
| **Evidence.dev** | Markdown + SQL → site estático; **Universal SQL**: fontes viram cache Parquet e um **DuckDB-WASM no browser** consulta o cache [✓] | fluxo SQL/Markdown produtivo; versionável como software | DuckDB-WASM obrigatório (custo de bundle do §1a por padrão) e paradigma de **relatório** |
| **Quarto dashboards** | documento científico com dashboards como add-on [✓] | ótimo para o **caderno** (que já existe como `.ipynb` + HTML executado) | dashboard é acessório; não é base de portal multi-módulo |
| **Streamlit** | app Python com servidor | zero JS; reusa o Python do pipeline | **servidor sempre ligado**; Community Cloud dorme em 12 h, ~1 GB RAM, **um único app privado**, auth por Google/magic-link [✓]; contradiz `architecture.md §7` ("sem servidor") |
| **Vite+React+TS+Tailwind+Recharts** | a stack que a LDC já roda e deploia | um só modelo mental com o site institucional; liberdade para módulos com formulário e estado | você escreve o pipeline de dados do build à mão — **um script Python de ~100 linhas**, dado o §0 |

**Veredicto: não** adotar framework de data app como base. Motivo em uma frase: os três primeiros são
ótimos **geradores de relatório**, e o LDC Analytics é declaradamente um **portal de ferramentas** —
produto de aplicação, com estado, não documento. **Mas copie a melhor ideia do Observable
Framework**: o *data loader que roda no build, em qualquer linguagem, e cospe arquivo*. Adotar esse
padrão dentro do Vite é de graça.

**Exceção que vale perguntar ao Edu:** se o alvo real do primeiro entregável for **publicar o caderno
do Comitê na web** (e não um portal), **Quarto/Observable com o `.ipynb` executado** é caminho de
dias, não semanas.

---

## 3. Autenticação e proteção de dado interno na Vercel

| Opção | Custo | Esforço | Força | Veredicto |
|---|---|---|---|---|
| **Vercel Authentication** (SSO do time) | **incluído em todos os planos**, inclusive produção [✓] | minutos | só quem está **no time Vercel** entra | **recomendado para o MVP** |
| **Vercel Password Protection** | **US$ 20/mês por projeto** no Pro; incluído no Enterprise; **indisponível no Hobby**. O antigo add-on de **US$ 150/mês** no nível do time segue para quem já tinha, como "Team-level Password Protection" [✓] | minutos | senha única compartilhada | **só se** alguém do Comitê não puder ter conta Vercel. Senha coletiva não tem identidade nem revogação individual |
| **Cloudflare Access (Zero Trust) na frente** | **free até 50 usuários**; US$ 7/usuário acima; log retido 24 h no free [✓] | horas a 1 dia | identidade real (Google Workspace/OTP), política por e-mail/domínio, log de acesso | **tecnicamente o melhor**, mas atrita com Vercel: ela **recomenda não** ativar o proxy laranja em domínios apontados para ela (loop de redirect, domínio inválido); o caminho suportado é **Verified Proxy** [✓]. Faz sentido se o host for **Cloudflare Pages** |
| **Clerk** | free ~50 k MAU (cobra MRU); Pro **US$ 25/mês** [✓] | 1-2 dias | ótimo DX, MFA, organizações | **sobredimensionado** para ≤ 10 pessoas internas |
| **Auth0** | free 25 k MAU; Essentials **US$ 35/mês** a partir de 500 MAU, escala caro [✓] | 2-3 dias | enterprise-grade | **não** — custo e cerimônia sem contrapartida |
| **Supabase Auth** | free 50 k MAU; Pro **US$ 25/mês** [✓] | 1-2 dias + banco | bom se você já tem Supabase | **não na v1** — arrastaria o banco que o ADR-007 veta |
| **Basic auth em middleware** | invocações; no Pro o seat traz **US$ 20 de crédito** e, fora dele, **1 TB de Fast Data Transfer + 10 M de Edge Requests** [✓] | horas (`middleware.ts` na raiz; com Vite via `vite-plugin-vercel`) [✓] | senha em env var validada **na edge, antes do cache** [✓] | **paliativo aceitável, não destino**: sem identidade, sem revogação, sem log |

**Recomendação.** (1) **MVP: Vercel Authentication**, projeto privado, `Standard Protection` ou
`All Deployments` — incluído, auditável no painel, revogação = remover do time; combina com
`Protection Bypass for Automation` (incluído em todos os planos [✓]) se um agente/CI precisar bater
no site. (2) **Quando o Comitê precisar entrar sem conta Vercel:** avaliar mudar o host para
**Cloudflare Pages + Access** (free até 50 usuários, identidade real, log) em vez de pagar
US$ 20/mês por senha coletiva — a decisão é de arquitetura, não de preço: **identidade por pessoa >
senha coletiva** para dado de alocação. (3) **Independente do auth:** nenhum dado "não publicável"
entra no bundle. **Auth protege o portal; o gate protege o número.**

**O que NÃO fazer.** Não confiar em "URL difícil de adivinhar" nem deixar deploy sem proteção — isso
é posicionamento de carteira de uma gestora. Não usar basic auth como solução definitiva, nem com a
senha no `vercel.json`. Não fazer "auth no front" (checar senha em JS e esconder a div — o bundle já
desceu). Não pôr Cloudflare laranja na frente da Vercel sem Verified Proxy: a própria Vercel
documenta que quebra [✓]. Não montar Supabase/Clerk/Auth0 "já que vamos precisar depois": cria
credencial no caminho crítico e, por `AGENTS.md §2`, **promove a feature a classe D** sem entregar
nada hoje.

---

## 4. Pipeline Python → web: como publicar

### A restrição real, não a genérica

O pipeline roda **na máquina do Edu** (Windows), com rede para 12 fontes, e `run --offline`
reconstrói **sem rede** de `data/processed/` [⌁]. A **Anti-SPEC proíbe rede no CI** ("NÃO chamar rede
em teste de CI", `SPEC.md §10` / `architecture.md §6`) [⌁]. E `data/` **não é versionado** (ADR-006
§4) [⌁]. Logo: **o CI não pode gerar o dataset** — ele não tem rede autorizada nem
`data/processed/`. Três desenhos viáveis:

**Desenho 1 — "freeze local + commit do artefato de apresentação" (recomendado para o MVP)**

```
MÁQUINA DO EDU                                       GITHUB / VERCEL
run --offline → verify → freeze --tag <t>
        │
        ▼
python -m apps.web_export --tag <t>
  (lê MANIFEST.json · aplica o gate · escreve
   apps/portal/public/data/<t>/*.json + current.json
   recusa se publicavel=false; marca se especificacao_congelada=false)
        │
        ▼
git add/commit/push  ───────────────────────►  Actions (SEM REDE):
                                               lint · unit · contrato do JSON
                                               (schema · hash == FROZEN ·
                                                nada não-publicável presente)
                                                        │
                                                        ▼
                                                 Vercel build + deploy
```

Por que ganha: o CI faz o que **pode** — validar — e nunca o que **não pode** — buscar dado. O
artefato de apresentação é pequeno (§0), então commitá-lo é honesto: é derivado, hasheado, e o
`current.json` prova de qual tag veio. E dá **rollback trivial** (`git revert` do commit de dado).

**Desenho 2 — runner self-hosted na máquina do Edu.** Actions suporta self-hosted runner [✓], e aí o
workflow roda onde `data/` existe. Prós: um clique dispara tudo. Contras: a máquina precisa estar
ligada com runner instalado, e runner self-hosted em repo privado com a rede de uma máquina pessoal é
superfície de ataque [~]. **Fase 2** (atualização trimestral, F-040), não MVP.

**Desenho 3 — upload manual para R2/Blob.** `apps.web_export --destino r2` sobe `data/<t>/` e
**depois** `current.json` (o ponteiro **sempre por último**). Contras: credencial de R2 no caminho ⇒
classe D, e perde o rollback por git. **Entra quando o payload sair do bundle**, não antes.

**Padrão de referência:** é o *git scraping* / **Flat Data** do Simon Willison **invertido** — em vez
de o CI buscar o dado, o humano o congela e o commita; o CI valida [✓]. É o mesmo espírito do data
loader do Observable Framework: dado gerado no build, salvo em arquivo [✓].

**Teste de CI que eu escreveria primeiro** (barato, pega o pior erro): ler
`public/data/*/manifest.json`, conferir que `dataset_sha256` casa com o `FROZEN.txt` citado, que
**nenhuma** view contém dado vindo de artefato `publicavel: false`, e que `especificacao_congelada`
está refletido no JSON. Isso transforma o gate do pipeline em gate do site.

---

## 5. Modelos e referências de UI para portais analíticos internos

**1. Verdad Capital — "Classifying Economic Regimes"** [✓]. GMM (clustering não supervisionado) sobre
macro diário 1962-2024; 4 regimes (Growth, Inflation, Precarious, Crisis) a partir de PIB, inflação,
inclinação da curva, volatilidade, spread high-yield e correlação ação-bond. *Tela, descrita:*
(i) **faixa temporal 1970-2024 colorida por regime**, lida como código de barras — é a timeline que o
projeto já tem em `timeline_regimes_*.svg`; (ii) **heatmap de caracterização** (regime nas linhas,
sinal nas colunas, célula = média padronizada, divergente azul↔vermelho) — diz *o que é* cada regime,
não só quando ocorreu; (iii) **tabela de retorno anualizado médio por classe e fator dentro de cada
regime**. *Copiar:* o par **"caracterizar o regime" + "medir o ativo no regime"** em telas irmãs — o
projeto tem o segundo e **não tem o primeiro**, e é ele que impede ler o rótulo como caixa-preta.
*Não copiar:* a página **não discute tamanho de amostra nem intervalo de confiança** [✓] — e o LDC
tem n = 13 a 19 por quadrante e erros-padrão medidos de 0 a 6 pp. Copiar o visual sem copiar a
omissão é o ponto inteiro deste projeto.

**2. Man Institute — "The Road Ahead: Regime-Based Investing"** [✓ o link; corpo **[~]**]. Ensaio que
**justifica a lente antes de mostrar o resultado**. *Copiar:* uma tela "Metodologia" de primeira
classe, não um rodapé — o material já existe (`metodologia-regimes-macro.md`, `LIMITACOES-COMITE.md`).

**3. FRED / ALFRED (Fed de St. Louis)** [✓]. 816 mil séries; gráficos customizáveis por unidade,
frequência e cor; dashboards pessoais; **ALFRED guarda os *vintages*** — o dado como era conhecido
numa data passada. *Tela:* gráfico grande, controles de unidade/frequência/transformação acima,
"EDIT GRAPH" em painel lateral, e no pé a **procedência da série com a data da última atualização**.
*Copiar:* o ALFRED é a **referência conceitual exata do par `revised` × `asof`** que este projeto tem
e que quase nenhuma gestora mostra. Uma chave "dado revisado / dado como se sabia na época", com a
consequência impressa — a V1 **troca de rótulo em 33,33% dos trimestres** entre as lentes [⌁] — é a
feature mais honesta que esse portal pode ter.

**4. BIS Data Portal** [✓]. Navegação **Topics → metodologia/metadado/séries**, calendário de
**Releases**, busca por palavra ou ID de série, dashboards por tema (policy rates, central bank total
assets), export em múltiplos formatos. *Tela:* um gráfico dominante, seletor de países/séries à
esquerda, **aba "metadata" com o mesmo peso visual da aba de dados**. *Copiar:* (a) metadado como aba
irmã do gráfico, não tooltip; (b) **página de releases** — "histórico de versões do dataset", com
tag, hash e data do dado; (c) **export em um clique** em toda tabela (o Comitê vai querer o CSV).

**5. Observable Framework (exemplos oficiais)** [✓]. Dashboards estáticos rápidos, com *small
multiples* de primeira classe e o dado já no shape da tela. *Copiar:* o **grid de cards** (um
indicador por card, com sparkline) para a home, e o princípio "o build já entregou o número; o
browser só desenha".

**6. Evidence.dev** [✓]. Markdown com SQL inline; filtros respondem **sem round-trip** porque o
DuckDB-WASM está no cliente. *Copiar:* a **sensação de filtro instantâneo** — com 83 linhas em
memória o portal consegue isso **sem** DuckDB, e deve: filtrar regime/ativo/janela precisa ser
imediato, ou o usuário para de explorar.

**7. Portfolio Visualizer / testfol.io** [✓ os sites; detalhe de tela **[~]**]. Backtest, regressão
de fatores, correlação, fronteira eficiente, Monte Carlo; o testfol.io acrescenta dado diário,
AQR/q-factors, fatores custom e PCA no mesmo fluxo [✓]. *Tela:* formulário denso em cima (ativos,
pesos, janela), **um botão "Analyze"**, e abaixo uma **cascata longa de seções de resultado**, cada
uma com tabela **e** gráfico. *Copiar:* o padrão **"input em cima, resultado em cascata abaixo"** —
exatamente a forma dos módulos futuros (simulação, projeção) — e a disciplina de sempre mostrar
tabela ao lado do gráfico. *Não copiar:* densidade sem hierarquia, e a ausência de aviso de
significância.

**8. Bloomberg / Koyfin / Macrobond** [Koyfin ✓; Macrobond ✓; Bloomberg **[~]**]. Koyfin:
**dashboards customizáveis**, overlays de métricas, layouts por classe de ativo [✓]. Macrobond: tem
**quadrant chart** nativo — scatter de duas séries com linhas horizontal e vertical dividindo em 4
áreas [✓], que é **literalmente a V1 deste projeto**. *Copiar:* o **scatter de quadrantes com trilha
temporal** ("spaghetti" [✓]): cada trimestre é um ponto em (`g_score`, `pi_score`), ligados em ordem,
com o trimestre corrente destacado. É a melhor tela possível para "em que regime estamos" — mostra o
rótulo **e a distância da fronteira**, que o rótulo sozinho esconde. O schema já carrega `g_score` e
`pi_score` contínuos "para o gráfico de dispersão" [⌁ `CONTRACTS.md §5.1`]: a tela está a um gráfico
de distância.

---

## 6. Arquitetura recomendada para o LDC Analytics

### 6.1 Diagrama

```
  MÁQUINA DO EDU (fonte de verdade)                  GIT / CI                 VERCEL (edge)
  ─────────────────────────────────                  ────────                 ─────────────
  12 fontes ─► apps/pipeline (run/verify/freeze)
                   ├─ data/canonical/*.parquet   (48 artefatos, NÃO versionado)
                   ├─ MANIFEST.json  (sha256 · linhas · nulos · publicavel · determinista)
                   └─ FROZEN.txt     (tag · DATASET_SHA256 · commit)
                              │
                              ▼
            ┌───────────────────────────────────────────┐
            │ apps/web_export/  (NOVO · Python · cl. C) │ ← a ÚNICA ponte pipeline→web
            │  lê MANIFEST.json                         │
            │  APLICA O GATE: publicavel=false → corta  │
            │    especificacao_congelada → marca        │
            │    n<5 → sem conclusão · n<8 → alerta     │
            │  converte unidade (pp ↔ fração)           │
            │  escreve views/*.json + manifest.json     │
            └───────────────────────────────────────────┘
                              │  610 KB → ~300 KB JSON (~100 KB gzip)
                              ▼
       public/data/<tag>/*.json  ──push──►  Actions (SEM REDE):      ┌──────────────────────────┐
       public/data/current.json             lint·unit·contrato ────► │ apps/portal              │
                                            hash == FROZEN           │  Vite+React+TS+Tailwind  │
                                            nada não-publicável      │  +Recharts               │
                                                                     │ Vercel Authentication    │
                                                                     │ current.json → no-cache  │
                                                                     │ data/<tag>/* → immutable │
                                                                     │ rodapé: tag+sha256+data  │
                                                                     │ faixa ⛔ NÃO PUBLICÁVEL   │
                                                                     └──────────────────────────┘
```

Fluxo **unidirecional**, como o do pipeline: nada volta para a esquerda. O portal **não calcula** —
é extensão natural de `apps/analysis/` (classe B: "lê o canônico e não recalcula nada").

### 6.2 Estrutura de pastas

```
apps/
  pipeline/                    (existe — intocado)
  analysis/                    (existe — figuras, tabelas, caderno, entrega)
  web_export/                  ← NOVO · Python · classe C
    __main__.py                #  --tag <t> [--destino dir|r2]
    gate.py                    #  ÚNICA implementação do gate para a web (importa o do pipeline)
    unidades.py                #  pp ↔ fração — o erro de 100× mora aqui e SÓ aqui
    views/{regimes_timeline,heatmap_regime_ativo,ranking_atual,vizinhos,internacional,macro_series}.py
    schemas.py                 #  pydantic do JSON — espelho do CONTRACTS para a web
  portal/                      ← NOVO · TS
    public/data/current.json · public/data/<tag>/*.json
    src/app/                   #  shell: layout, nav, auth, erro, rodapé de versão
    src/core/dataset.ts        #  carrega current.json, FIXA a tag da sessão, valida o manifest
    src/core/gate.tsx          #  <GateBanner/> <NConclusao/> <UnidadeBadge/> <BarraDeErro/>
    src/core/charts/           #  wrappers Recharts com os defaults da LDC
    src/core/registry.ts       #  o registro de módulos (§6.3)
    src/modules/alocacao-macro/   module.ts + pages/{Visao,Heatmap,Quadrantes,Vizinhos,
                                  Internacional,Metodologia}.tsx         ← MÓDULO 1 (MVP)
    src/modules/{simulacao,projecao,validacao-teses}/   ← fases 2-4, mesma forma
packages/shared/
  schemas/                     (existe — pandera/pydantic, FONTE DE VERDADE)
  contracts-web/               ← NOVO · JSON Schema gerado de web_export/schemas.py → tipos TS
```

### 6.3 Registry de módulos — como o módulo 2 entra sem reescrever o portal

```ts
export interface ModuleManifest {
  id: string;                  // "alocacao-macro"
  nome: string; descricao: string; icone: ComponentType;
  rotas: RouteObject[];        // lazy() — cada módulo é um chunk próprio
  dados: DatasetRequirement[]; // { view: "heatmap_regime_ativo", minVersao: 1 }
  gate: "pipeline" | "nenhum"; // herda o gate do dataset, ou não depende de dado congelado
  estado: "producao" | "beta" | "rascunho";
}
export const MODULOS: ModuleManifest[] = [alocacaoMacro /*, simulacao, … */];
```

Três regras que fazem o registry valer a pena:
1. **O shell não conhece módulo nenhum** — ele itera `MODULOS` para montar nav, home e rotas. Módulo
   novo = um arquivo + uma linha no array.
2. **`dados` é declarativo:** no boot o shell confere contra o `manifest.json` da tag corrente; se a
   view não existe naquela versão, o módulo aparece **desabilitado com o motivo** — não quebra a tela.
3. **`gate: "pipeline"`** faz o shell injetar automaticamente a faixa de não-publicável e as travas de
   `n`. Módulo novo herda o gate **por omissão**, não por disciplina do programador.

### 6.4 Onde fica o contrato dos dados

**A fonte de verdade continua em `packages/shared/schemas/` (pandera/pydantic)** — a regra do
`CONTRACTS.md` ("primeiro crie o schema, depois documente") não muda. Acrescenta-se
`apps/web_export/schemas.py`, o contrato do **JSON de apresentação** em pydantic, de onde o build
**gera** JSON Schema → tipos TS em `packages/shared/contracts-web/`. Assim existe **uma** definição
por conceito e o front não pode inventar coluna. `docs/contracts/CONTRACTS.md` ganha um
`§10 — views da web`, espelho legível, nunca fonte.

### 6.5 Como o portal herda o gate

| Sinal no pipeline | Como chega | Como aparece na tela |
|---|---|---|
| `especificacao_congelada = false` | campo em `manifest.json` | **faixa fixa no topo de TODA tela**: "⛔ MATERIAL DE DISCUSSÃO — especificação não congelada (ADR-001 em Proposta). Nenhum número desta tela é insumo de decisão de alocação." **Não dispensável por clique** |
| `publicavel = false` | `web_export` **não emite a view** | seção/módulo desabilitado, com o motivo do `MANIFEST.json` |
| `n < 5` | por célula no JSON | renderiza **"sem conclusão (n=4)"**, não o número |
| `n < 8` | por célula | número + alerta, com o `n` sempre visível |
| `DATASET_SHA256`, tag, `data_do_dado` | `manifest.json` | rodapé global, em toda tela |
| `revised` × `asof` (`lag_adjusted`) | duas views | **chave global** de lente, com o % de troca de rótulo ao lado |
| `determinista = false` (`ldc.duckdb`) | ignorado | o portal nunca serve o DuckDB |

---

## 7. Riscos e armadilhas

1. **Dado sensível em bundle público.** O bundle é texto baixável por quem passar do auth — e
   **antes** dele, se a proteção estiver só no front. *Mitigação:* proteção na **edge** (valida antes
   do CDN); `web_export` **não emite** artefato `publicavel: false`; teste de CI que falha se coluna
   proibida aparecer no JSON. **O gate não é do front; é do exportador.**
2. **CDN servindo versão velha** — falha clássica e **silenciosa**: heatmap de uma tag com ranking de
   outra. *Mitigação:* caminho com a tag + `immutable`, **um** ponteiro `current.json` com
   `no-cache`, tag fixada por sessão, recusa de render se o manifest divergir (§2.2). Vercel dá URL
   imutável por deploy e `max-age=31536000, immutable` em asset com hash [✓].
3. **n pequeno virando conclusão errada** — o risco nº 1 deste produto, e já documentado: 4
   quadrantes em 83 trimestres dão 19/19/16/13 + **16 indeterminados**, e os erros-padrão **medidos**
   vão de 0 a **6,01 pp** [⌁ `LIMITACOES-COMITE.md`]. "A ordem do ranking não é estatisticamente
   distinguível" está escrito — e uma UI com ranking numerado desfaz essa frase em um segundo.
   *Mitigação:* `n` em toda célula (**não** em tooltip); barra de erro **no gráfico**, não só na
   tabela; ranking **agrupado por faixa** em vez de 1º/2º/3º; proibido ordenar por média sem exibir
   dispersão.
4. **Dashboard que convida a "achar padrão".** 42 variáveis × 24 ativos × 3 lentes × 2
   materializações num filtro livre é um gerador de p-hacking com interface bonita — e a Anti-SPEC já
   proíbe "ajustar a especificação de regime depois de ver os retornos". *Mitigação:* o portal é
   **descritivo e congelado**; as visões são as que o pipeline emitiu, e corte novo passa por feature
   de pipeline (com ADR se mexer na lente). Toda tela de corte custom avisa que o corte **não** foi
   pré-registrado. A guarda de linguagem (`analysis/_linguagem.py`) vale também para os textos do front.
5. **Custo de manutenção além do pipeline.** Hoje há **um** artefato e **zero** infraestrutura; um
   portal adiciona deploy, auth, domínio, dependências JS que envelhecem e a tentação de "só mais um
   gráfico". *Mitigação:* `web_export` é a **única** ponte e tem contrato; o portal não tem backend;
   nenhum módulo entra sem o registry. Regra: **se o portal pedir cálculo, o cálculo vai para o
   pipeline**, nunca para o TS.
6. **Reabertura silenciosa do ADR-007** (2 dos 3 gatilhos). *Mitigação:* **ADR-008 — "LDC Analytics:
   site estático, dado congelado no bundle, sem banco na v1"**, citando ADR-006/007, **antes** da
   primeira linha de código — senão a decisão acontece por acidente.
7. **Divergência entre o caderno e o portal** — dois canais, duas chances de divergir. *Mitigação:*
   ambos leem a **mesma** tag, e o rodapé imprime o mesmo `DATASET_SHA256` do `HASHES.txt`.
8. **Unidade.** `macro_quarterly` em por cento/pp e `asset_returns_quarterly` em fração, com
   `cdi_tri`/`ipca_tri` homônimos [⌁] — erro de 100× num slide é catastrófico e invisível.
   *Mitigação:* conversão **só** em `web_export/unidades.py`; unidade no JSON por campo;
   `<UnidadeBadge/>` obrigatório em todo eixo.

---

## 8. Estimativa de esforço (dias-agente)

Premissas: um agente competente, Edu revisando, stack já conhecida, e **o dataset já existe e já é
congelável** — é isso que torna a conta pequena. Não inclui o tempo humano de aceitar ADR-001.

**Infraestrutura do portal — reutilizável por todos os módulos**

| Item | Dias | Reuso |
|---|---|---|
| ADR-008 (decisão de arquitetura, citando ADR-006/007) | 0,5 | 100% |
| `apps/web_export/`: gate, unidades, schemas pydantic, CLI, `current.json` | **3,0** | 100% |
| Geração JSON Schema → tipos TS (`packages/shared/contracts-web/`) | 0,5 | 100% |
| Scaffold `apps/portal`: Vite+TS+Tailwind, rotas, **registry**, shell/nav | **2,0** | 100% |
| `core/dataset.ts` (tag por sessão, validação de manifest, política de cache) | 1,0 | 100% |
| `core/gate.tsx` (faixa, `<NConclusao/>`, `<UnidadeBadge/>`, barras de erro) | 1,5 | 100% |
| `core/charts/`: timeline de regime, heatmap, scatter de quadrantes, barras com erro | **2,5** | ~90% |
| Auth (Vercel Authentication) + domínio + `vercel.json` (headers de cache) + deploy | 0,5 | 100% |
| CI: validação do JSON (schema, hash, nada não-publicável) — **sem rede** | 1,0 | 100% |
| Página "Versões do dataset" (histórico de tags/hashes, estilo *releases* do BIS) | 0,5 | 100% |
| **Subtotal infraestrutura** | **13,0** | |

**Módulo 1 — Alocação Macro (MVP)**

| Item | Dias |
|---|---|
| as 6 views em `web_export/views/` | 2,5 |
| `Visao` ("em que regime estamos", 3 lentes + concordância) | 1,5 |
| `Quadrantes` (scatter `g_score`×`pi_score` com trilha temporal) | 1,5 |
| `Heatmap` regime × ativo, com `n`, flags e chave `revised`/`asof` | 2,0 |
| `Vizinhos` ("momentos semelhantes", 8 trimestres, com dispersão) | 1,0 |
| `Internacional` (faixa, nunca ponto) | 1,0 |
| `Metodologia` + `Limitações` (renderiza o markdown existente) | 0,5 |
| Export CSV/XLSX por tabela | 0,5 |
| QA independente (reconstrução numérica contra o Parquet) | 1,5 |
| **Subtotal módulo 1** | **12,0** |

**MVP total ≈ 25 dias-agente** (13 de infra + 12 do módulo), dos quais **~13 são reutilizáveis**.

**Módulos seguintes, com a infra paga: 5 a 9 dias-agente cada** — *validação de teses* na ponta baixa
(lê dado congelado, parecido com o módulo 1); *simulação* e *projeção* na ponta alta, **com uma
ressalva estrutural**: elas precisam de cálculo com input do usuário, que site estático não faz. Duas
saídas, nessa ordem: (i) **cálculo no browser** com os parâmetros em memória — viável, 83 linhas, e
Monte Carlo de carteira em JS/WASM é instantâneo nesse tamanho; mantém o portal estático;
(ii) **Vercel Function** só para o cálculo, com o dado ainda vindo do CDN — custa auth, cold start e
um ADR. **Nunca** (iii) o front reimplementando a convenção de retorno: isso é classe C e mora no
pipeline.

**Caminho mais curto, se o alvo for só o Comitê:** publicar o HTML executado do caderno atrás do auth
= **1 a 2 dias**, zero infraestrutura nova. Vale propor como v0 antes dos 25 dias.

---

## 9. Procedência das fontes

**Lidas na íntegra [✓]:** `vercel.com/docs/deployment-protection/usage-and-pricing` ·
`duckdb.org/docs/current/clients/wasm/overview.html` · `github.com/hyparam/hyparquet` ·
`verdadcap.com/archive/classifying-economic-regimes` · `vercel.com/docs/security/reverse-proxy`.

**Verificadas por busca, com citação [✓]:** `vercel.com/docs/functions/limitations` (4,5 MB payload,
250 MB bundle, 2/4 GB RAM, 800 s, cold start) · `vercel.com/docs/caching/cache-control-headers` e Pro
($20/seat, 1 TB Fast Data Transfer, 10 M edge requests) · `vercel.com/docs/vercel-blob/usage-and-pricing`
· `developers.cloudflare.com/r2/pricing/` (free 10 GB, egress $0) · Cloudflare Zero Trust (free ≤ 50
usuários, $7/user) · MotherDuck (free 3 usuários/10 GB; Business $250/mês) · Clerk/Auth0/Supabase Auth
· `github.com/observablehq/framework`, `observablehq.com/blog/data-loaders-for-the-win`,
`simonwillison.net/2024/Mar/3/interesting-ideas-in-observable-framework/` · `evidence.dev/universal-sql`,
`evidence.dev/blog/why-we-built-usql` · `docs.streamlit.io/deploy/streamlit-community-cloud` ·
`github.com/duckdb/duckdb-wasm/discussions/1469`, `kanopylabs.com/blog/pglite-vs-sqlite-wasm-vs-duckdb-wasm`,
`vldb.org/pvldb/vol15/p3574-kohn.pdf` · `github.com/dsi-rse/cpr-explorer-v2/pull/17`,
`github.com/llimllib/nba0bservable/issues/24` · `docs.github.com/en/repositories/releasing-projects-on-github`
· `docs.github.com/en/actions/reference/runners/self-hosted-runners` ·
`simonwillison.net/series/git-scraping/` · `fred.stlouisfed.org/help/about/about-fred/what-is-fred`,
`fredblog.stlouisfed.org/2026/06/what-can-alfred-do-for-you/` · `data.bis.org/` + `/help/faq` +
`/topics/CBPOL/tables-and-dashboards` · `help.macrobond.com/.../scatter-chart/quadrant-chart/` ·
`koyfin.com/features/` · `legacy.portfoliovisualizer.com/` · `testfol.io/start/` ·
`man.com/insights/road-ahead-regime-based-investing` ·
`github.com/vercel/examples/.../basic-auth-password/middleware.ts`, `github.com/magne4000/vite-plugin-vercel`.

**Conhecimento geral, NÃO verificado [~]:** latências de edge CDN (20-80 ms TTFB); tamanho de
`parquet-wasm` vs. hyparquet; detalhes visuais de Bloomberg, Koyfin e Man Institute; risco de runner
self-hosted em máquina pessoal; CORS em assets de GitHub Release; os 200-400 KB estimados de JSON.

**Medido por mim no repositório [⌁]:** os tamanhos do §0; `MANIFEST.json`/`run.py`
(`ARTEFATOS_NAO_PUBLICAVEIS`, `publicavel`, `determinista`, `DATASET_SHA256 = fc233118…`); as unidades
divergentes de `CONTRACTS.md §3/§4`; 19/19/16/13 + 16 indeterminados e os erros-padrão de
`LIMITACOES-COMITE.md`; os 33,33% de troca `revised`×`asof`; os 8 passos do gate em
`runbooks/entrega-comite.md`; o veto e os 3 gatilhos do ADR-007.

---

## 10. Perguntas abertas para o Edu (não decidi por ele)

1. **Portal ou publicação do caderno?** Os 25 dias só se justificam se houver módulos 2, 3 e 4. Se o
   alvo é a reunião, o HTML executado atrás de auth custa 1-2 dias.
2. **Quem precisa entrar?** Se todos podem ter conta no time Vercel, o auth é de graça e hoje. Se
   não, a decisão é Cloudflare Pages + Access (free, identidade real) vs. US$ 20/mês de senha coletiva.
3. **ADR-008 antes do código?** Recomendo sim — o portal reabre o ADR-007 por construção, e deixar
   isso implícito contraria o `AGENTS.md`.
4. **O portal pode mostrar número enquanto ADR-001 está em `Proposta`?** Tecnicamente sim, com a faixa
   de não-publicável; **mas é decisão de classe D**, não minha. Se a resposta for "não", o MVP é
   construído contra um dataset de exemplo e só aponta para o real depois do congelamento.
