# Módulo `/admin/analytics-macro` — guia de instalação e decisões

> **Versão:** 1.2 · **Data:** 2026-10-11 (noite) · **Autor:** agente de front-end (Claude), modo
> autônomo; §2 atualizada no fechamento da frente, quando os **3 itens de acerto com o exportador
> foram aplicados** (ver as caixas ✅ abaixo)
>
> A primeira ferramenta do LDC Analytics (Módulo 1 — Alocação Macro), como **pacote pronto para
> colar** em `apps/web_export/modulo-site/`, que reproduz a árvore de destino arquivo por arquivo:
> instalar é copiar e aplicar três mudanças fora dela (§1.2 a §1.4). A v1.1 **consome o contrato
> real do exportador**, que apareceu durante o trabalho: `meta.json`, as 6 views com os nomes
> reais, `GateDaView` lido do dado e `_lib/schema.d.ts` **gerado** por `apps/web_export/tipos_ts.py`.
>
> **O repositório do site não foi tocado** — `feat/agente-consultor`, 63 arquivos modificados,
> tratado como somente leitura: nenhuma branch, commit, edição, `npm install` nem `next build`.
> **Isso continua valendo no fechamento da frente:** o módulo segue **pronto e não instalado**, e as
> 6 decisões que o destravam estão em `TODO.md §4`.
>
> **Não pude rodar `npm run build` e `npm run lint` deles, e declaro.** Rodei, sobre os arquivos do
> pacote e com o compilador e o runner já instalados lá (config descartável no meu diretório
> temporário, nada escrito no repositório deles): `tsc --noEmit --strict` → **0 erros** contra os
> tipos reais de React 19, Next 15, do kit de gráficos, do `AdminLayout` e do `checkAdminAuth`; e
> `vitest run` → **51 testes em 4 arquivos, todos passando**. Cobre tipo e comportamento, não o
> build do Next; §5 lista o que falta.

## 0. O que o módulo entrega

| Tela | Rota | Em uma frase |
|---|---|---|
| **1 · Visão geral** (T-01) | `/admin/analytics-macro` | Responde "em que regime estamos" **três vezes** (V1 revisada, V1 na época, V3), sem escolher nenhuma, com o motivo do indeterminado, o fallback sempre rotulado, a interseção vazia dos cinco primeiros, a concordância como distribuição e os vizinhos do trimestre. |
| **2 · Heatmap regime × ativo** (T-02) | `.../heatmap` | A grade ativo × regime com `n` dentro de **toda** célula, filtros na URL, hover com erro-padrão e clique abrindo o detalhe do par. |
| **3 · Momentos semelhantes** (T-03) | `.../momentos` | Escolhe o trimestre de referência e o `k`; lista os vizinhos com distância e o quadrante de cada um, e o que rendeu em T+1 com `n` e barra de erro. |
| **4 · Dados e limitações** (T-07) | `.../dados` | Catálogo das séries com cobertura declarada **e** observada em colunas separadas, hash do dataset, as limitações com o número medido, as decisões com o custo de discordar, o status dos 7 ADRs e o que o gate cortou. |

O dataset chega por cópia em `analytics-macro/` (raiz do app, **fora de `public/`**) e sai por
`/api/admin/analytics-macro/[...caminho]`, atrás de `checkAdminAuth()`.

---

## 1. Como instalar

### 1.1 Copiar a árvore

```
# de estrategia-macro-ldc-dados/apps/web_export/modulo-site/  →  para site-ldc/site-ldc/
src/app/admin/analytics-macro/      →  src/app/admin/analytics-macro/
src/app/api/admin/analytics-macro/  →  src/app/api/admin/analytics-macro/
analytics-macro/                    →  analytics-macro/   (só README.md + .gitkeep)
```

`src/app/globals.css.patch.md` **não** é copiado: é o trecho a aplicar à mão (§3.3).

Os testes vêm em `src/app/admin/analytics-macro/__tests__/` **de propósito**: o `vitest.config.ts`
do app só inclui `src/**/__tests__/**/*.test.{ts,tsx}` e `src/**/*.test.{ts,tsx}` — um `tests/` na
raiz do módulo nunca rodaria. Os dois `.tsx` abrem com `// @vitest-environment jsdom`, porque o
ambiente global é `node`; `jsdom` e `@testing-library/react` já estão nas devDependencies.

### 1.2 `next.config.ts` — uma entrada

```diff
   outputFileTracingIncludes: {
     "/api/admin/r2/**": ["./referencia-r2/**", "./assets-r2/**"],
+    "/api/admin/analytics-macro/**": ["./analytics-macro/**"],
   },
```

Sem isso o JSON não entra no bundle serverless: funciona em desenvolvimento e dá 404 em produção.

### 1.3 `src/app/admin/components/AdminLayout.tsx` — um grupo novo

No array `grupos`, depois de `Simuladores` e antes do item solto `Configurações`:

```diff
+    /*
+     * Grupo próprio, não dentro de "Conteúdo" ao lado de analytics/utm: a navegação é agrupada por
+     * OFÍCIO, e "o que o Comitê decide" não é o ofício de publicar conteúdo.
+     * `editorOk` AUSENTE = somente ADMIN, o default seguro já documentado no tipo ItemNav.
+     */
+    { titulo: "Comitê de Alocação", itens: [
+      {
+        name: "Alocação Macro",
+        href: "/admin/analytics-macro",
+        icon: Grid3x3,
+        current: pathname.startsWith("/admin/analytics-macro"),
+      },
+    ] },
```

E `Grid3x3,` no import de `lucide-react` que já existe no arquivo (não é dependência nova).
Alternativa de diff zero: `ShieldAlert`, hoje **importado e não usado** ali.

Duas consequências que vêm de graça: o grupo **desaparece inteiro** para o `EDITOR` pelo filtro
`editorOk`; e o `useEffect` de *defense-in-depth* do layout **redireciona** o `EDITOR` que digitar
a URL para `/admin/estudos-r2/meu-dia`, porque a rota não está na lista dele. É mais restritivo que
o resto de `/admin`, e é a decisão certa para dado do Comitê. Abrir depois é mudar uma flag e
acrescentar a rota naquele `useEffect`.

### 1.4 `.gitignore` — e a decisão que a linha embute

O dataset **precisa** estar no git: o CI não tem rede nem `data/processed/`, quem congela é o
humano e a Vercel lê do repositório (o "Desenho 1" de `ldc-analytics-arquitetura.md` §4, confirmado
em `ldc-analytics-identidade-v2.md` §9.3). Logo a linha **não** é `analytics-macro/`. O que entra é
trava contra o que nunca deve atravessar:

```gitignore
# LDC Analytics — o JSON das tags e o schema.d.ts SÃO versionados (o CI valida, a Vercel
# publica, o rollback é git revert). O que não atravessa é artefato bruto: parquet, duckdb,
# xlsx ou caderno HTML aparecendo aqui significa --destino errado.
analytics-macro/**/*.parquet
analytics-macro/**/*.duckdb
analytics-macro/**/*.csv
analytics-macro/**/*.xlsx
analytics-macro/**/*.html
analytics-macro/**/*.png
analytics-macro/**/*.svg
```

Se o Edu preferir **não** versionar o dado (RF-W043 pede isso), a linha vira `analytics-macro/*/` e
o módulo mostra "Dataset não instalado" em produção até existir outro caminho de entrega (Storage
privado, a saída de fase 2). As duas opções ficam registradas; a escolha é dele.

### 1.5 Publicar uma tag

```bash
python -m apps.web_export --tag comite-2026-10-14 \
  --destino "C:/Users/edusp/Projetos_App_Desktop/site-ldc/site-ldc/analytics-macro"
```

O exportador escreve `<tag>/*.json`, o `schema.d.ts` e, **por último**, `current.json`. Depois:
commit no submódulo pelo `AGENTS.md` §13, N1, deploy.

---

## 2. O contrato: o que consumi e as três adaptações

**Consumido como está:** `current.json` (`PonteiroCurrent`, com `arquivos` mapeando view →
caminho, "para o front não adivinhar o nome"), `<tag>/meta.json` (`MetaWeb`: gate, índice de views
com `sha256`, `unidade_por_campo`, `casas_por_unidade`, reduções, orçamento, artefatos não
publicáveis), as views `ranking_atual`, `heatmap_regime_ativo`, `vizinhos` e `catalogo`, o envelope
(`view/tela/pergunta/tag/dataset_sha256/gate/fontes`) e o `schema.d.ts` **gerado** — que foi gerado
de verdade e está em `_lib/schema.d.ts`, não escrito à mão.

Três pontos em que a tela teve de decidir algo, todos declarados na própria tela:

1. **Unidade.** ✅ **RESOLVIDO em 2026-10-11 (D-aj).** O exportador publica fração (`0,0504`) e
   declara a unidade; as telas do PRD mostram `+5,04%`. Cumprir RF-W014 ao pé da letra imprimiria
   `+0,0504 fracao` numa célula de heatmap. A conversão continua existindo em **um** lugar
   (`_lib/formato.ts`), mas a tabela `APRESENTACAO` **não existe mais**: o `meta.json` passou a
   declarar `unidade_de_apresentacao`, `fator_de_apresentacao` e `casas_de_apresentacao` **por
   campo**, e o arquivo virou leitura — o que sobrou do lado da tela é o rótulo tipográfico (`%`,
   `p.p.`), que é texto de interface. O selo mostra a unidade apresentada e o rodapé imprime a
   nativa com o fator. O teste que fixava a tabela agora **lê o fator do `meta`**
   (`fatorDeApresentacao(META, "excesso_cdi") === 100` e `…("selic_meta_pct") === 1`, que é o caso
   de 100× que importa). **O que sobra de dívida:** RF-W014 lido ao pé da letra proíbe conversão no
   front, e multiplicar por fator declarado ainda é conversão — ver `TODO.md §6`.
2. **Materialização e horizonte não são eixos independentes** — quem os determina é a `vista`, que é
   a unidade de consistência do exportador (dentro de uma vista a V1 está em T0 e a V3 em T+1).
   Então a vista é o seletor, e materialização/horizonte aparecem **declarados** para a vista
   escolhida. Cruzar eixos entre vistas produziria coluna que o dataset não publicou.
3. **A lente dos vizinhos é uma só.** A tag publica uma lente descrita campo a campo (métrica,
   janela, shrinkage, somente-passado). Mahalanobis × Euclidiana e somente-passado aparecem com o
   valor publicado e **desabilitados com o motivo**, porque inventar a alternativa no front seria
   recalcular metodologia no cliente. Querer a alternativa é pedir outra lente ao exportador.
   Mesmo caso do ranking em T+1, que a view publica para o trimestre do Comitê: outra referência
   mostra os vizinhos e diz, nomeando, que a leitura em T+1 dela não está nesta tag.

E duas decisões de design, as duas **resolvidas** no mesmo fechamento:

- ✅ **`cor_hex` não existe mais** (**D-ai**). A célula trazia o hex da figura **matplotlib** (paleta
  *placeholder* da skill `dataviz`), a tela **ignorava** e pintava com a rampa da casa (§3.3), e
  havia teste provando. Campo que ninguém lê é campo que faz a próxima pessoa adivinhar qual das
  duas cores vale: o exportador **parou de emitir**, na célula do heatmap e no estilo da faixa da
  timeline. Ficou o que tem significado e não é cor (`hachura`, `conclusao_suprimida`). É remoção de
  campo, então `SCHEMA_VERSAO` subiu **1 → 2**. A convergência da rampa da tela com a da figura do
  PDF segue sendo o adendo proposto ao `DESIGN.md` — e agora as duas convivem sem contradizer um
  número, porque só uma delas é publicada.
- ✅ **O extremo da escala vem declarado** (**D-aj**). `heatmap_regime_ativo.eixos_de_cor` publica
  `extremo_simetrico` por `(vista, campo)` — `max(|valor|)` da **vista inteira**, em unidade nativa,
  como **eixo** e não como estatística. A tela multiplica pelo fator declarado e usa
  (`extremoDeclarado`); o cálculo local (`extremoSimetrico`) ficou como último recurso para tag
  antiga e para as views que não declaram eixo (o ranking em T+1 de T-01 e T-03).

---

## 3. As decisões de desenho

### 3.1 Por que Server Component

- **O JSON não desce para o cliente**: desce HTML do recorte visível. Para dado do Comitê é menos
  superfície que entregar o recorte inteiro ao navegador de quem abriu.
- **A tag é fixada no servidor.** `abrirDataset()` é memoizado por requisição (`cache()` do React) e
  **nenhuma função aceita tag por parâmetro** — "heatmap de uma tag com ranking de outra" deixa de
  ser um caminho que alguém consiga escrever. É o risco nº 2 da arquitetura, e é silencioso.
- **O gate não depende de hidratação**: a faixa chega no primeiro byte.
- **Filtro na URL, não em estado** (RF-W003): com o servidor filtrando, a URL *é* o estado.

Cliente só onde há interação: `Heatmap`, `SeletorDeLente` e `BarraDeErro`. A barra é de cliente por
um motivo que vale registrar: `charts.tsx` é `"use client"`, e no App Router **todo export de um
módulo de cliente vira referência de cliente** — um Server Component que lesse `CHART_COLORS.NAVY`
levantaria em runtime. Renderizar um componente de cliente a partir do servidor é permitido; ler um
valor dele não é. A alternativa seria redeclarar o hex, que é o drift registrado na §3.2 do
inventário.

Todas as telas são `force-dynamic`: com `revalidate` de segmento, ponteiro e faixa do gate poderiam
vir do cache de rota, e dataset velho com faixa errada é a falha que não se pode ter. O cache vive
onde é seguro — `private, immutable` por tag na API, `no-store` no ponteiro, e um memo em memória no
loader **cuja chave inclui o `sha256`**, então valor memoizado nunca envelhece.

### 3.2 Por que SVG próprio

Recharts está no `package.json` e **não tem heatmap**: o que existe é `ScatterChart` com célula
desenhada à mão — o mesmo trabalho, com uma abstração no caminho. E as exigências são todas de
desenho fino: `n` **dentro** da célula, borda tracejada como segundo canal entre os limiares,
hachura sem cor na supressão, vão entre grupos e ordem de linha declarada (`ativos[].linha`). O kit
da casa já é SVG escrito à mão ("Identidade LDC, sem dependência externa") e o idioma `px`/`py` com
`padL/padR/padT/padB` do `ProjectionChart` foi copiado quase literal. Zero dependência nova.

`PageHeader` e `StatCard` entram como são; `GaugeEnquadramento`, `RingGauge`, `Donut` e
`DepletionChart` não têm forma para grade. `brlShort`, `pctFmt` e `num` são internos do kit (não
exportados), então o idioma foi copiado para `_lib/formato.ts` — o único lugar onde número vira
texto.

### 3.3 Por que a rampa divergente é assim

O `DESIGN.md` tem *um* acento (lime) e *um* alerta, e não tem escala de magnitude com sinal. A saída
fácil (lime = positivo) é proibida pela regra escrita: *"Sucesso não ganha verde."* A rampa é a da
§9.4 do inventário: neutro `#f0f2f3` no zero, 4 passos no arco do **alerta** do lado negativo, 4 no
arco do **navy** do positivo, lime **fora da escala** (marca o recorte corrente, não o sinal) e
`#eceef0` hachurado na supressão. Simetria em ±extremo é obrigatória: sem ela o meio deixa de
significar "empatou". E o extremo é calculado sobre a **vista inteira**, não sobre o recorte
filtrado — se dependesse do filtro, marcar uma classe repintaria as outras.

Uma correção medida: `#c0584f` cheio dá **3,1:1** com navy e **4,4:1** com `#fcfdfd` — reprova AA
para texto pequeno nas duas tintas, e a célula carrega número. O 3º passo do arco negativo é
`#a94d46` (o hover de `.ldc-btn-alerta`, já no sistema), que alcança **5,3:1**. Os dez pares estão
medidos em `modulo-site/src/app/globals.css.patch.md`, com antes/depois — **o CSS deles não foi
editado**. O patch é opcional: a rampa também vive em `_lib/formato.ts`, que é o que o SVG usa.

---

## 4. O que falta — as três telas da v2

1. **Timeline de regimes sobre IBOV e Selic** (T-04): dois painéis empilhados, faixa de regime
   **dentro** de cada um (nunca eixo y duplo), `INDETERMINADO` hachurado, as divergências marcadas.
   A view `regimes_timeline` **já existe** e o loader já a conhece — o módulo até lê dela o `n` por
   regime para o cabeçalho do heatmap. Falta a tela, que é desenho; o `DepletionChart` traz o
   marcador vertical e o anti-colisão de rótulo quase prontos.
2. **Internacional** (T-06): a view `internacional` **já existe**, com faixa de D6, correlações com
   `n_pares`, regra de stress e as omissões do gate. Falta a tela — e a pré-condição **P2** manda
   não publicar número `publicavel: false` antes da correção de `app_metadata`.
3. **Ativo em foco** (T-05): distribuição ponto a ponto por regime, pior trimestre com a data,
   estado de `is_total_return`. Precisa de uma view nova no exportador.

Também fora: exportação CSV/PNG do recorte visível (RF-W037 a W040), versões do dataset (RF-W018),
quadrantes (RF-W036), a home-catálogo (RF-W006) e o `/caderno` do v0.

---

## 5. O que conferir ao instalar

| # | Verificação | Por que |
|---|---|---|
| 1 | `npm run typecheck` e `npm run lint` | O typecheck rodei (0 erros); o ESLint deles não — o build ignora lint, então não quebra o deploy. ⚠️ **As mudanças de 2026-10-11 em `_lib/{formato,schema.d.ts}`, na fixtura e no teste do heatmap não passaram pelo `tsc` nem pelo `vitest` do app** — só por um `tsc --strict` isolado sobre `formato.ts` + `schema.d.ts` (0 erros). Rodar os dois é a primeira coisa ao instalar. |
| 2 | `npm run build` | **A que mais importa:** valida a fronteira servidor/cliente de verdade, `searchParams` como `Promise` do Next 15 e o `outputFileTracingIncludes`. |
| 3 | `npm test` | Os 51 testes do módulo passaram no vitest deles, sem mudar `vitest.config.ts`. |
| 4 | Abrir as 4 rotas com `analytics-macro/` **vazia** | Cada tela deve mostrar "Dataset não instalado", nomeado, com o gate fechado. Nenhuma tela em branco. |
| 5 | `curl` na API **sem cookie**, e depois como `EDITOR` | Sem cookie: `current.json` → **401**, caminho fora da allowlist → **404**. Como `EDITOR`: o grupo não aparece e a URL redireciona para `/admin/estudos-r2/meu-dia`. |
| 6 | `grep -r "analytics-macro" public/` → vazio | É a trava P1, e vale como teste de CI. |
| 7 | Publicar uma tag e ler o rodapé | O `DATASET_SHA256` tem de ser o do `HASHES.txt` do pacote, e os links "conferir" têm de abrir o JSON. |

---

## 6. As três pré-condições de segurança

- **P1 — nenhum byte do dataset em `public/`.** `public/` é servido pela camada estática da Vercel,
  que **não passa pelo middleware**: no mesmo deployment do site institucional, o JSON seria legível
  por quem soubesse a URL. O módulo já cumpre (o loader só resolve
  `join(process.cwd(), "analytics-macro")` e a API é a única porta); falta o teste de CI da
  verificação 8.
- **P2 — nada `publicavel: false` entra enquanto o papel vier de `user_metadata`.** Hoje é o caso de
  `internacional_pesos.parquet` (**D-af**). O exportador já recusa; a regra aqui é não contorná-lo.
  A Tela 4 mostra, em bloco próprio, todo artefato que o gate cortou e o motivo.
- **P3 — `ADR-008` no projeto de dados, antes do merge**, revisando a premissa "não é web, sem
  deploy" do `AGENTS.md`: *"LDC Analytics: módulo interno no app LDC (`/admin/analytics-macro`), dado
  congelado servido fora de `public/` atrás da auth existente, sem banco novo na v1"*, citando
  ADR-006/007. Sem ele a reabertura do ADR-007 acontece por acidente.

---

## 7. Item separado e **anterior**: `user_metadata` → `app_metadata`

**Não é parte deste módulo, não é pré-requisito do MVP dele, é pré-requisito de P2.** Classe C/D no
`site-ldc` (toca auth), PR próprio.

**A falha.** O papel vem de `user_metadata.role`, que o próprio usuário escreve com a chave anon via
`updateUser({ data: { role: 'ADMIN' } })` — e aqui ele **vaza para o banco**:
`src/lib/auth-check.ts:32` lê o metadata e as linhas 35-47 fazem **upsert em `public."User"` com
`role`** usando o client **service role**; `r2-web/route-helpers.ts` → `ensureAdvisor()` →
`wealth-planning/db.ts:88` grava `wp_advisors.role = 'admin'`; e é exatamente isso que
`public.wp_is_admin()` consulta — a função que **todas** as políticas RLS usam no `or wp_is_admin()`.
Um `EDITOR` se promove e passa a ver a carteira de todos os advisors: 29 migrations de RLS bem
escrita, anuladas por uma linha. `app_metadata`, que só service role escreve, não é usado em lugar
nenhum (`grep -rn "app_metadata" src/ packages/ supabase/` → zero). Atenuante que muda a severidade,
não o diagnóstico: não há UI nem rota de cadastro (`grep signUp src/` → zero), então o vetor é
interno.

**Diff conceitual** — quatro leituras e uma escrita:

```diff
# 1) src/middleware.ts:87 — a guarda de borda
-  const userRole = user.user_metadata?.role;
+  const userRole = user.app_metadata?.role;   // só service role escreve

# 2) src/lib/auth-check.ts:32 — a API
-  const metadataRole = (authUser.user_metadata?.role as string | undefined) || undefined;
+  const metadataRole = (authUser.app_metadata?.role as string | undefined) || undefined;

# 3) e 4) src/lib/auth-server.ts:19 e src/lib/auth-supabase.ts:68 — idem

# 5) src/lib/wealth-planning/db.ts:88 — ensureAdvisor PARA de derivar papel da sessão
-  role: user.role === 'ADMIN' ? 'admin' : 'advisor',
+  // papel de advisor é provisionado, não inferido: INSERT entra 'advisor'; promover é
+  // operação de admin, por script ou pela tela de Consultores
+  role: existente?.role ?? 'advisor',

# 6) scripts/sync-admin-users.ts — a lista fechada de 4 e-mails passa a escrever app_metadata
-  { user_metadata: { role } }
+  { app_metadata: { role } }
```

**A ordem importa:** (a) o script passa a escrever `app_metadata` **mantendo** `user_metadata`; (b)
rodar para os 4 e-mails; (c) trocar as quatro leituras com fallback temporário e log; (d) conferir
que ninguém caiu no fallback; (e) remover o fallback e parar de escrever `user_metadata`; (f)
corrigir `ensureAdvisor` e **auditar `wp_advisors.role` no banco**, que já pode ter `admin` gravado
por autodeclaração. Um teste que tente a autopromoção e verifique que o acesso não muda fecha o
item.

---

## 8. Riscos

1. **O contrato pode mudar de novo.** Mitigado por `schema.d.ts` **gerado** (regenerar é um comando
   e o `tsc` aponta o que quebrou), por uma lista de nomes no loader, e por conferência de hash,
   tag e `dataset_sha256` que **falha a tela** em vez de desenhar errado.
2. **Não rodei o `next build`** — risco residual na fronteira servidor/cliente, mitigado por
   inspeção e por `tsc --strict` limpo, mas só o build confirma.
3. **A conversão de unidade no front** era divergência de RF-W014 contida numa tabela do front;
   desde 2026-10-11 o `meta` publica o fator campo a campo e a tabela virou leitura (D-aj). O que
   resta é de **redação da regra**, não de risco: ver `TODO.md §6`.
4. **A rampa navy ↔ alerta não foi vista pelo Comitê**, e a separação em protanopia/deuteranopia não
   foi medida (só o contraste). Os dois arcos se separam por luminância, que é o canal que sobrevive.
5. **Versionar o dado faz o repo crescer** — o orçamento do exportador é 400 KB por tag, e ele
   publica o número medido no `meta`. Dez tags são ~4 MB; a saída de fase 2 está desenhada.

**Procedência.** Projeto de dados: `LDC-ANALYTICS-PRD.md`, `ldc-analytics-identidade-v2.md`,
`ldc-analytics-arquitetura.md`, `LIMITACOES-COMITE.md`, `wiki/context/F-022|023|024`,
`apps/analysis/_linguagem.py`, `apps/web_export/*.py`, `packages/shared/schemas/web_views.py`,
`data/canonical/MANIFEST.json`. App (somente leitura): `DESIGN.md`, `globals.css`, `admin/layout.tsx`,
`admin/components/AdminLayout.tsx`, `middleware.ts`, `lib/auth-check.ts`,
`wealth-planning/components/charts.tsx`, `simulador-eficiencia-exterior/page.tsx`,
`analytics/utm/page.tsx`, `next.config.ts`, `lib/r2-web/paths.ts`, `api/admin/r2/perfil/route.ts`,
`components.json`, `package.json`, `vitest.config.ts`, `vitest.setup.ts`, `tsconfig.json`.