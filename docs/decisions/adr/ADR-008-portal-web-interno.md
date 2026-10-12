# ADR-008 — LDC Analytics: portal web interno, dado congelado por tag, sem banco na v1

- **Status:** **Proposta** — aguardando decisão de **Edu** (dono do projeto)
- **Data:** 2026-10-11
- **Autor:** subagente executor de **F-W001** (`apps/web_export/`), modo autônomo
- **Complementa:** **ADR-006** (armazenamento) · **ADR-007** (sem banco remoto na v1)
- **Cobre:** `LDC-ANALYTICS-PRD.md` §5.2 (RF-W009..W018), §9 (RW-07) ·
  `docs/research/ldc-analytics-arquitetura.md` §1.1, §2.2, §7.1, §7.2, §7.6 ·
  `docs/research/ldc-analytics-identidade-v2.md` §9.1, §9.3

> **Este ADR precisa existir antes do portal, não depois.** O PRD registra em **RW-07** que o portal
> aciona **2 dos 3** gatilhos de reavaliação do **ADR-007** — e gatilho acionado sem ADR é decisão
> arquitetural acontecendo **por acidente**. O código de F-W001 foi escrito como se este ADR estivesse
> aceito nas três afirmações abaixo; se o Edu discordar de qualquer uma, o que muda está em
> "Consequências" e em "O que fazer se a decisão for outra".

---

## Contexto

### O que mudou desde o ADR-007

O **ADR-007** ("Sem Supabase, nem qualquer banco remoto, na v1") foi aceito em 2026-10-10 com três
**gatilhos de reavaliação** explícitos. O portal **LDC Analytics** (PRD de 2026-10-11) aciona dois:

| Gatilho do ADR-007 | Acionado? | Pelo quê |
|---|---|---|
| 1. **Dashboard multiusuário** | **SIM** | o portal é exatamente isso: Edu + Alexandre na v1, Comitê depois (PRD §3, DW-4) |
| 2. **Atualização automática consumida por outras pessoas** | **SIM, em parte** | o Alexandre passa a consumir o dataset sem rodar o pipeline. **Mas publicar continua sendo ato humano** — não há atualização automática (PRD §10, fora de escopo) |
| 3. **Histórico de vintages consultável por terceiros** | **NÃO** | o portal lê **uma** tag por sessão; vintage segue em Parquet, e a página "Versões do dataset" é v2 (RF-W018) |

E o `AGENTS.md` abre dizendo, sobre a natureza do projeto: *"Não é SaaS, não é web. Sem auth, sem
pagamento, sem deploy (roda local)."* O portal é **web, com auth e com deploy**. A frase não está
errada — ela descreve o que o repositório **é**: um pipeline de dados. Mas deixa de ser completa.

### O que o dado já é, medido e não suposto

- **610 KB** de Parquet de apresentação em disco; tabela principal de **83 linhas** `[arq §0]`.
- `MANIFEST.json` já é um **content-addressed dataset release**: `sha256` por artefato,
  `DATASET_SHA256` agregado reproduzível na linha de comando, `determinista` e **`publicavel`** por
  artefato, `versao_build` por etapa e `data_do_dado` lida do bruto, nunca do relógio `[arq §2.1]`.
- O conjunto de JSON que F-W001 emite mede, **medido nesta tag**: **369.501 bytes** nas 6 views +
  `schema.d.ts` e **380.713 bytes** nos 9 arquivos (**54.378 bytes** em gzip), abaixo do teto de
  400 KB de RNF-W001.

Ou seja: **o problema deste projeto nunca foi volume. É versionamento, procedência e gate de
publicação** — e os três já estão resolvidos em arquivo.

## Decisão

**O LDC Analytics é um módulo de leitura dentro do app que a LDC já tem (`site-ldc`), alimentado por
um conjunto de JSON derivado, imutável por tag, gerado na máquina do Edu por `apps/web_export/`. A
v1 não tem banco, não tem escrita e não tem backend próprio.** Em cinco afirmações:

1. **O Parquet de `data/canonical/` continua a fonte reconstruível** (ADR-006). O JSON é
   **derivado e descartável**, como o `ldc.duckdb`: apagar e reexportar dá os mesmos bytes
   (determinismo provado em `tests/unit/test_web_export.py`). Nenhum número nasce no portal.
2. **Sem banco, e sem exceção na v1** (ADR-007 segue valendo). Não há estado de usuário, não há
   escrita, não há *vintage* consultável por terceiro. Banco, se um dia entrar, é materialização **a
   jusante** — nunca fonte —, com ADR próprio e classe D.
3. **O gate vive no exportador, não no front** `[arq §7.1]`. `publicavel: false` ⇒ o exportador
   **recusa rodar**; `especificacao_congelada` do **ADR-001 em disco** viaja em toda view; `n < 5`
   sai com o valor **e** com `conclusao_suprimida: true`. O bundle que desce ao browser é texto
   baixável: filtro no front é decoração.
4. **O dado publicado vive fora de `public/`**, numa pasta na raiz do app servida por *API route*
   com `checkAdminAuth()`, no molde de `referencia-r2/` `[ident §9.3]`. Em Next na Vercel, `public/`
   é servido pela camada estática, que **não passa pelo middleware**: `public/data/<tag>/heatmap.json`
   seria lido por qualquer um que soubesse a URL.
5. **O `AGENTS.md` ganha uma exceção nomeada**, proposta aqui e **não aplicada por agente**: *"sem
   deploy (roda local)" vale para o pipeline. O módulo LDC Analytics é a **única** exceção: ele
   publica, atrás de acesso autorizado, um dataset **derivado** gerado localmente. O pipeline
   continua sem deploy, sem auth e sem rede no caminho crítico.*

## Alternativas consideradas

- **A — Módulo em `/admin/analytics-macro` do `site-ldc`, dado fora de `public/`, servido por API
  route.** **Escolhida.** Zero infraestrutura nova, zero credencial nova (o `/admin` já tem
  middleware, papéis e `robots: noindex`), rollback por `git revert` do commit de dado, e o
  exportador como única ponte. Contras: amarra o portal ao ciclo de deploy do site institucional, e
  o `outputFileTracingIncludes` do `next.config.ts` passa a ser infraestrutura que alguém precisa
  lembrar.
- **B — App separado na Vercel com Vercel Authentication.** Prós: isolamento total; proteção na
  edge "de graça". Contras: **projeto novo, domínio novo, lista de acesso nova** e — o ponto que
  decide — todo membro do Comitê precisaria de conta na Vercel (DW-2). Fica como plano B se o
  `/admin` do `site-ldc` virar obstáculo.
- **C — Parquet remoto + `hyparquet` no browser.** Prós: uma fonte só, sem etapa de exportação.
  Contras: o front passaria a conhecer o formato do canônico, e a conversão de unidade e as travas
  de `n` migrariam para o TypeScript — o oposto de P4/P5 do PRD.
- **D — DuckDB-WASM.** **Rejeitada:** ~2,8 MB gzip de engine para consultar **83 linhas** `[arq §1]`
  — o motor pesando 5× o dataset. Responde a uma pergunta ("consultar sem baixar tudo") que este
  projeto não tem.
- **E — Postgres/Supabase como fonte do portal.** **Rejeitada pelo ADR-007 e mantida rejeitada:**
  introduz credencial (⇒ classe D por `AGENTS.md §2`) e cria o risco específico de **dado errado
  persistido remotamente, fora do alcance do "apague e reconstrua"** — o modo de falha dominante
  deste projeto.
- **F — v0: publicar o HTML executado do caderno atrás de autenticação.** 1 a 2 dias, zero
  infraestrutura `[arq §8]`. **Não é alternativa, é complemento:** se o alvo for a reunião de
  14/10, é isto que se faz, e este ADR continua valendo para a fase 2.

## Consequências

### Positivas

- **Publicar dado deixa de ser deploy de código** (RNF-W011): o caminho contém a tag, o conteúdo é
  imutável, e trocar de versão é trocar **um ponteiro** (`current.json`). Rollback é um arquivo.
- **O gate fica executável e auditável num só lugar.** Hoje são 11 testes de recusa em
  `tests/unit/test_web_export.py`, incluindo um que injeta `publicavel: false` num artefato lido e
  exige falha.
- **O contrato entre os dois repositórios é gerado, não combinado:**
  `packages/shared/schemas/web_views.py` → `schema.d.ts` no mesmo comando, com teste que exige que
  toda chave emitida exista no `.d.ts`.
- **ADR-007 fica honestamente reafirmado** em vez de contornado em silêncio — que era o risco
  **RW-07** do PRD.

### Negativas / trade-offs

- **O Edu passa a ser gargalo de publicação**, não só de leitura (**RW-05**). O portal reduz "me
  manda o recorte" e cria "publica a tag nova". Mitigação parcial: um comando, determinístico, com
  runbook; e alerta de dataset envelhecido para a dívida ficar **visível** em vez de suposta.
- **Toda visão nova exige uma exportação nova** — é o custo do pré-computado `[arq §1.1]`. Em troca,
  nenhum cálculo roda no cliente.
- **Dois lugares para olhar quando um número divergir**: o Parquet e o JSON. Mitigado por `sha256`
  por view em `meta.json` e pela regra "divergência portal × pipeline é bug **do portal**, sempre".
- **O `AGENTS.md` deixa de ter uma frase absoluta.** "Sem deploy" com asterisco é mais frágil de
  ler do que "sem deploy". É o preço de o portal existir.

### Neutras

- Nenhuma dependência Python nova: `apps/web_export/` usa `pandas`, `pyarrow` e `pydantic`, que já
  estão no `pyproject.toml`.
- O vocabulário de banco (`vintage`, `asof`, `revised`) segue válido — é modelagem, não
  infraestrutura (igual ao ADR-007).

## Decisões de implementação que este ADR registra

| # | Decisão | Por quê |
|---|---|---|
| **D-W1** | O manifesto da tag chama-se **`meta.json`** e ocupa o slot `manifest.json` de RF-W009/W011 | um só manifesto por tag; `current.json` **nomeia o arquivo**, então o front não adivinha. Se o consumidor preferir `manifest.json`, é trocar `NOME_META` — uma constante |
| **D-W2** | A 6ª view chama-se **`catalogo.json`** e ocupa o slot `macro_series` de `[arq §1.1]` | a tela que o MVP precisa é a **T-07** (condição para qualquer número ser publicável). As séries macro que alguma tela do MVP consome — Selic e IBOV por trimestre — viajam em `regimes_timeline`, onde a T-04 as usa |
| **D-W3** | A view de vizinhos traz **uma** lente (Mahalanobis · `somente_passado` · janela cheia) e emite **um** ranking por referência (`k=12`), com os `k` menores declarados como **prefixo** dele | as 9.692 linhas das 4 lentes × 2 métricas não cabem em 400 KB. O prefixo é **conferido a cada exportação** (58/58 referências, zero divergências), não suposto; e truncar não é recalcular |
| **D-W4** | **Nenhuma conversão de unidade.** Cada campo publica a unidade **nativa** do pipeline, declarada em `meta.unidade_por_campo` | RF-W014 pede unidade por campo; zero conversão é zero chance do erro de **100×** entre `%/pp` e fração. A conversão que o PRD previa em `unidades.py` **não existe porque não é necessária** |
| **D-W5** | Precisão declarada: **4 casas em fração** (= 2 casas em pp, a precisão que as telas exibem), 6 em correlação e distância, 2 em índice | é a redução de precisão que o orçamento de 400 KB exigiu, declarada em `meta.casas_por_unidade`. Quem precisa de mais casas lê o Parquet |
| **D-W6** | O destino padrão do exportador é **`data/web/`**, fora de `data/canonical/` | `run.inventariar` varre `data/canonical/` **recursivamente**: cada JSON escrito ali aparece no `verify` como "não listado no manifesto" (`rc != 0`) e um `freeze` novo passaria a incluir o JSON no `DATASET_SHA256` — **que o próprio JSON cita**. Ver a proposta abaixo |

### Proposta ao orquestrador: uma exclusão por prefixo em `run.py` (D-W6)

É a **mesma colisão que D-ag resolveu** para o pacote de entrega, e a saída é a mesma.

> **Atualização de 2026-10-11 (noite) — `D-ah`.** O orquestrador generalizou a exclusão: o que
> `inventariar()` ignora agora é `PREFIXO_DE_ENTREGAVEL_DERIVADO = "entrega/"` **inteiro**, com uma
> lista nomeada de exceções (`ARTEFATOS_DE_ENTREGA`, as 2 saídas do caderno de F-027); a constante
> `PREFIXO_PACOTE_DE_ENTREGA` de D-ag deixou de existir. O gatilho foi o terceiro entregável
> derivado desta onda — `entrega/RELATORIO-ALEXANDRE-2026-10-14.html`, que reproduziu a falha byte
> por byte. **Então o padrão desta decisão existe e está testado**, e aplicar o mesmo a `web/` é a
> mesma função com outra constante.

Se o Edu quiser o dataset do portal sob `data/canonical/web/`, `run.py` precisa de um
`PREFIXO_WEB_EXPORT = "web/"` na mesma peneira de `inventariar`, pela mesma razão: artefato
**derivado do manifesto** não pode entrar no manifesto. `run.py` era arquivo congelado para o agente
desta feature, então a mudança ficou proposta, não aplicada — e, enquanto não existir, o padrão
`data/web/` resolve sem tocar em nada. **Demonstrado:** exportar para dentro de `data/canonical/` produz 9 divergências
graves + agregado divergente no `verificar` (teste
`test_aviso_quando_o_destino_fica_dentro_do_canonical`).

## O que fazer se a decisão for outra

- **"Não quero portal agora"** ⇒ `apps/web_export/` fica como está e não é chamado por ninguém: ele
  não escreve em `data/canonical/`, não roda no CI por omissão e não altera nenhum artefato
  existente. Custo de reverter: apagar 4 arquivos e 2 testes.
- **"Quero, mas fora do `site-ldc`"** ⇒ alternativa **B**; muda o `--destino` do comando e nada mais
  neste repositório.
- **"Quero com banco"** ⇒ reabre o ADR-007 de verdade, com credencial no caminho ⇒ **classe D**,
  seção de rollback em `docs/plans/infra-ops.md` e o gate de 8 passos do `AGENTS.md §14`.
- **"Não aceito a exceção no `AGENTS.md`"** ⇒ o portal não pode existir como descrito, e a resposta
  honesta é **v0** (alternativa F): HTML do caderno atrás de autenticação, sem dataset publicado.

## Gatilhos de reavaliação

Reabrir **este** ADR se qualquer um ocorrer:

1. **O dado de apresentação passar de ~20-30 MB** ⇒ Parquet + `hyparquet`; **> ~200 MB ou consulta
   ad hoc sobre série diária** ⇒ DuckDB-WASM `[arq §1.1]`.
2. **O usuário passar a compor a consulta** (filtro livre sobre 42 variáveis × 24 ativos) ⇒ visão
   pré-computada explode combinatorialmente; isso é SQL, e é também um gerador de p-hacking com
   interface bonita (**RW-06**).
3. **Aparecer estado de usuário** (carteira salva, anotação, preferência compartilhada) ⇒ precisa de
   escrita ⇒ reabre o ADR-007 de verdade.
4. **A publicação deixar de ser ato humano** (F-040 automática) ⇒ o gate de classe D deixa de ter
   onde acontecer.
5. **O ADR-001 ser aceito** ⇒ não reabre este ADR, mas a faixa de não publicável some **sozinha** no
   próximo `web_export` (P3 do PRD) — zero linha de código.

## Referências

- **ADR-006** (Parquet por camada + DuckDB derivado; `(a).2` "derivado e descartável") ·
  **ADR-007** (sem banco remoto na v1, e os seus 3 gatilhos) · **ADR-001** (gate de
  `especificacao_congelada`, hoje em `Proposta`)
- `docs/product/LDC-ANALYTICS-PRD.md` §2 (P1-P10), §5.2, §9 (RW-01, RW-03, RW-05, RW-07), §10, §11
- `docs/research/ldc-analytics-arquitetura.md` §0, §1.1, §2.1, §2.2, §3, §6.2, §6.4, §6.5, §7
- `docs/research/ldc-analytics-identidade-v2.md` §9.1 (onde o módulo mora), §9.2 (como a rota é
  protegida), §9.3 (por que não `public/`)
- `AGENTS.md` (cabeçalho: "sem deploy (roda local)"), §2 (credencial ⇒ classe D), §14 (gate da
  classe D) · `docs/product/LIMITACOES-COMITE.md` §7 (as 12 decisões que o portal **mostra** e não
  decide)
- `apps/web_export/` (F-W001) · `packages/shared/schemas/web_views.py` ·
  `tests/unit/test_web_export.py` · `tests/contract/test_web_views_contract.py`
