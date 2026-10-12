# LDC Analytics — Inventário do app real e reconsideração arquitetural (v2)

> **Status:** substitui na prática `docs/research/ldc-analytics-identidade.md` (v1) e revisa
> `docs/research/ldc-analytics-arquitetura.md`. O v1 fica no repositório **como registro do erro** —
> não como fonte.
>
> **Retificação.** O v1 auditou `site-eduardo`, que é a **marca pessoal do Eduardo**, e concluiu que
> "não existe identidade visual da LDC Capital neste repositório". O site da LDC está em
> `C:\Users\edusp\Projetos_App_Desktop\site-ldc\` e a conclusão se inverte: existe design system
> documentado, kit de gráficos próprio, auth com RLS, CI, deploy e **dois precedentes diretos de
> ferramenta analítica interna**. O relatório de arquitetura recomendou projeto novo em Vite+React
> partindo da premissa errada; a §8 deste documento reavalia e **contraria** essa recomendação.
>
> **Escopo de escrita:** `site-ldc` foi tratado como **somente leitura**. Nada alterado, nenhum build
> rodado, nenhuma dependência instalada. Toda afirmação abaixo vem de leitura de arquivo.
>
> **Convenção de caminho:** salvo indicação contrária, todo caminho é relativo a
> `C:\Users\edusp\Projetos_App_Desktop\site-ldc\site-ldc\` (o app). Caminhos do projeto de dados
> são prefixados por `estrategia-macro-ldc-dados/`.

---

## 0. Confirmação da estrutura

Confirmada e detalhada. `C:\Users\edusp\Projetos_App_Desktop\site-ldc\` é um **workspace de
trabalho** (SDDs, superprompts, screenshots de auditoria, `wt-wp/`, `wt-editor/`, `wp/`,
`demo-r2-uhnw/`, `material-comercial/`, `parecer-*.md`) e **não** é o repositório da aplicação. O app
real é o submódulo git `site-ldc/site-ldc/`:

- `site-ldc/.gitmodules` → `url = https://github.com/EduardoSousaPO/site-ldc-capital.git`, `path = site-ldc`.
- Branch local atual: **`feat/agente-consultor`** (não `main`) — relevante para a §6.
- Protocolo de submódulo em `AGENTS.md` §13: commit acontece **dentro** de `site-ldc/site-ldc/`,
  depois o ponteiro é commitado no wrapper; `git submodule update --remote` é proibido sem aprovação.
- `CLAUDE.md` memória 3 formaliza: *"Working dir do repo Git real é `site-ldc/site-ldc/`."*

**Stack confirmada** (`package.json`): Next.js `^15.5.3` (App Router) · React `19.1.0` · Tailwind `^4`
(via `@tailwindcss/postcss`) · TypeScript `^5` · Recharts `^2.12.7` · Zod `^4.1.5` · Supabase
(`@supabase/ssr ^0.7.0`, `@supabase/supabase-js ^2.57.4`) · Vitest `^4.1.5` · Playwright `^1.57.0`
(dependência de runtime para PDF — **não** há `playwright.config.*`) · `zustand`, `react-hook-form`,
Radix UI, `lucide-react`, `xlsx`, `docx`, `papaparse`.

---

## 1. Mapa do app

### 1.1 Rotas públicas (institucional + iscas de lead)

De `src/app/**/page.tsx`, 18 rotas públicas:

| Rota | O que é |
|---|---|
| `/` | home institucional (`src/app/page.tsx`) |
| `/blog`, `/blog/[slug]` | blog alimentado por Supabase (`BlogPost`); substituiu `/news` |
| `/consultoria`, `/equipe`, `/contato`, `/trabalhe-conosco` | institucional |
| `/materiais`, `/guia`, `/guia-pdf`, `/ebook-investimentos-internacionais` | materiais + captura de lead |
| `/calculadora-tributacao-dividendos-2026` | calculadora pública (lead magnet) |
| `/pgbl-simulator` | simulador público de PGBL |
| `/diagnostico-gratuito` | formulário de entrada |
| `/informacoes-regulatorias`, `/politica-privacidade`, `/termos-de-uso` | compliance CVM |
| `/wealth-planning` | **não é pública** — ver §4.2 |

### 1.2 `/admin/*` — os módulos internos

51 arquivos `page.tsx` em `src/app/admin/`, todos sob o matcher do middleware:

| Módulo | Caminho | O que faz (lido no código) |
|---|---|---|
| `login` | `src/app/admin/login/page.tsx` | e-mail/senha Supabase; roteia por papel — ADMIN → `/admin/dashboard`, qualquer outro → `/admin/estudos-r2/meu-dia`. Fail-closed por comentário explícito. |
| `dashboard` | `src/app/admin/dashboard/page.tsx` | porta de entrada do ADMIN: contagem de posts, atalhos. Não é analítico. |
| `estudos-r2` | `src/app/admin/estudos-r2/` (12 páginas) | **o módulo mais maduro.** Ciclo de acompanhamento: `meu-dia` (agregado do dia), `clientes/[id]` (workspace + `plano`), `executadas` (retrovisor), `agente` (assistente LLM com tool-calling só de leitura e cálculo determinístico), `novo`/`[id]` (geração de Estudo R2 → DOCX/PDF/HTML), `consultores`, `perfil`. |
| `wealth-planning` | `src/app/admin/wealth-planning/` (21 páginas) | **ferramenta de cenário do consultor.** `dashboard` (12-4-2), `clientes/[id]/{plano,simulador,relatorio,acompanhamento,dividendos,pgbl,protecao-sucessao}`, `premissas`, `compare`, `scenarios/[id]/{edit,results}`. Motor de projeção + PDF assinado. |
| `simulador-eficiencia-exterior` | `src/app/admin/simulador-eficiencia-exterior/page.tsx` + `src/components/wealth-planning/foreign-efficiency/` | eficiência tributária de investimento no exterior; componentes próprios `Charts.tsx`, `Tables.tsx`, `PremisePanel.tsx`, `ScenarioCompare.tsx`, `PresentationView.tsx`. |
| `simulador-holding` | `src/app/admin/simulador-holding/page.tsx` + `src/components/wealth-planning/holding-simulator/` | holding patrimonial; importa `PageHeader` do kit de gráficos. |
| `analytics/utm` | `src/app/admin/analytics/utm/page.tsx` | **o único módulo que já é "analytics"**: série temporal + barras de UTM/GA4 em **Recharts** (`BarChart`, `LineChart`, `ResponsiveContainer`) + tabela. Alimentado por `/api/admin/analytics/utm`. |
| `artigos-ia` | `src/app/admin/artigos-ia/page.tsx` | geração de artigo por tema (pipeline IA). Server Component fino + client component. |
| `bloomberg-pdfs` | `src/app/admin/bloomberg-pdfs/page.tsx` | upload de PDFs Bloomberg (sinal interno autoral, ADR-003) → dispara pipeline. |
| `posts`, `categories`, `materials`, `videos` | `src/app/admin/{posts,categories,materials,videos}/` | CMS do blog/materiais/vídeos. |
| `settings` | `src/app/admin/settings/page.tsx` | página quase estática; só ADMIN (guarda extra no middleware). |

### 1.3 O precedente mais próximo de "ferramenta analítica interna"

**Hipótese do Edu confirmada, com uma correção de ordem.** Do mais ao menos próximo:

1. **`/admin/wealth-planning`** — precedente **estrutural e de design**. É o módulo que motivou o
   registro `product` do `DESIGN.md`, o escopo CSS `.ferramenta`, o container `.ldc-work` e o kit
   `charts.tsx`. É dele que se herda *como se escreve uma tela densa de dado neste app*.
2. **`/admin/simulador-eficiencia-exterior`** — precedente **de forma**: tela isolada, **sem CRUD**,
   que recebe premissas e devolve números + gráficos + visão de apresentação
   (`PresentationView.tsx`). É o formato mais parecido com o LDC Analytics, que também não tem CRUD.
3. **`/admin/analytics/utm`** — precedente **de nome e de stack de gráfico**: a única tela que já se
   chama `analytics`, com `AdminLayout` + Recharts + cards + tabela.

Para o LDC Analytics a combinação certa é **forma do `simulador-eficiencia-exterior`** (tela isolada,
sem CRUD, com modo apresentação) + **disciplina visual do `wealth-planning`** (`.ferramenta` + kit).
A posição no menu, porém, **não** deve ser ao lado de `analytics/utm` — ver §9.2.

---

## 2. Design system real

### 2.1 Onde os tokens vivem

**Não existe `tailwind.config.*`** — confirmado (`ls tailwind.config.*` → não encontrado). O app é
Tailwind 4 puro: os tokens vivem em `src/app/globals.css` (582 linhas), no bloco `@theme inline` e em
`:root`. `postcss.config.mjs` só carrega `@tailwindcss/postcss`. `components.json` confirma
shadcn/ui; os primitivos estão em `src/components/ui/`.

Três camadas, nesta ordem:

1. **`@theme inline`** (linhas 6–22) — gera utilitários Tailwind: `--color-ldc-primary`,
   `--color-ldc-accent-1`, `--color-ldc-accent-2`, `--color-ldc-gray-light`,
   `--color-ldc-neutral-dark`, `--color-ldc-neutral-medium`, `--font-sans`, `--font-serif`,
   escala de `--radius`.
2. **`:root` / `.dark`** — variáveis shadcn (`--background`, `--primary`, `--destructive`, `--ring`…).
3. **`.ferramenta`** — o escopo do registro *product*, que **redefine tokens do framework dentro de
   si**. É a decisão técnica mais importante do design system e é Tailwind-4-específica: como
   `text-sm` compila para `font-size: var(--text-sm)` e `bg-white` para `var(--color-white)`,
   redefinir essas variáveis dentro de `.ferramenta` reescala e re-tinge **tudo que já está escrito**
   sem tocar na marcação. Os comentários no CSS registram a escala do problema resolvido assim:
   166 `text-sm`, 100 `text-xs`, 274 classes de cinza frio e 13 `bg-white` puros.

### 2.2 Paleta (hex + papel semântico)

Fonte: `DESIGN.md` (62 linhas) cruzado com `globals.css` e `charts.tsx`.

| Tinta | Hex | Papel semântico |
|---|---|---|
| **Navy** | `#262d3d` | tinta forte, texto, eixos de gráfico; `--color-gray-900` dentro de `.ferramenta` |
| **Slate** | `#577171` | texto secundário, rótulos, **"informação"** (inclui "deu certo"); `--color-gray-600` |
| **Lime** | `#98ab44` | **acento único** — ação primária, série de destaque, "no trilho". Nunca estado de sucesso. |
| Lime claro | `#becc6a` | acento 2 / `--accent` |
| **Alerta** | `#c0584f` | fora do perfil, atrasado, esgotamento. Único vermelho da casa. |
| Neutral dark | `#344645` | superfície escura (sidebar, card em `.dark`) |
| Gray light | `#e3e3e3` | `--border` / `--input` do site público |

Neutros tintados para o navy, **obrigatórios em superfície de dado**:

| Papel | Hex |
|---|---|
| Superfície de painel (nunca `#fff`) | `#fcfdfd` (`--color-white` dentro de `.ferramenta`) |
| Hover de linha | `#f4f5f6` (`.ldc-linha:hover`) / `#f7f8f9` (`--color-gray-50`) |
| Grid de gráfico | `#f0f2f3` |
| Track de gráfico | `#eceef0` |
| Linha / borda | `#e6e8ea` |
| Borda de campo | `#d3d8da` |
| Placeholder / dica | `#7d8c8c` |
| Scrollbar thumb | `#cfd4d6` → hover `#b6bdc0` |

Utilitários semânticos (escopados em `.ferramenta`, `globals.css` ~linhas 200–240):

| Classe | Efeito |
|---|---|
| `.ldc-alerta` | `color: #c0584f` |
| `.ldc-info` | `color: #577171` |
| `.ldc-sup-alerta` | fundo `#faf2f1`, borda `#f4e1df`, texto alerta (alerta a 8%/18%, **hex sólido pré-calculado** — `color-mix` foi removido por quebrar em navegador sem suporte, virando painel vermelho sólido com texto vermelho: ilegível) |
| `.ldc-sup-lime` | fundo `#f5f7ec`, borda `#e8edd6`, texto navy |
| `.ldc-btn-alerta` | fundo alerta cheio, hover `#a94d46` — único lugar onde o alerta é fundo |
| `.ldc-work` | container de trabalho: `max-width: 80rem` (1280px), centrado |
| `.ldc-linha` | linha de lista densa: `min-height: 2.75rem` (44px) + hover tintado |
| `.ldc-num` | célula numérica: alinhada à direita + `tabular-nums` |
| `.ldc-nav` | scrollbar da sidebar em branco translúcido (não lime) |
| `.ldc-scroll` | scrollbar neutra fora de `.ferramenta` |

**Duas regras decorrentes, escritas no `DESIGN.md`:**

- *"Sucesso não ganha verde."* Lime é acento de **ação** e de "no trilho", não de estado — e lime como
  texto sobre branco reprova contraste. "Deu certo" é informação → slate.
- *"Importante ≠ problema."* Prioridade alta é só **texto** em alerta; problema (vencido, bloqueado,
  par descoberto) ganha **superfície**. A diferença é de forma, não de matiz.

### 2.3 Tipografia

| Registro | Títulos | Corpo | Onde |
|---|---|---|---|
| **brand** (site público) | **Ivy Mode** serif, via `h1..h6 { @apply font-serif }`, escala **fluida** (`h1` até `text-7xl`) | Public Sans, escala fluida | `src/app/globals.css` `@layer base` |
| **product** (ferramenta) | **Public Sans** 700 `tracking-tight` | Public Sans **15px**, escala **fixa** razão ~1,2 | `.ferramenta h1..h6` + override de token |

Escala fixa de `.ferramenta`: `xs` 13px · `sm` **15px (corpo)** · `base` 17px · `lg` 19px · `xl` 21px ·
`2xl` **26px (título de tela)**. Eyebrow: 11px, uppercase, `tracking-[0.14em]`, slate.
`font-variant-numeric: tabular-nums` é **herdado por todo o escopo** — não depende de alguém lembrar
de escrever a classe.

**Arquivos de fonte:** `src/fonts/` — `IvyMode-{Regular,SemiBold,Bold}.otf` (3 pesos) e
`PublicSans-*.ttf` (21 variantes). Também `@fontsource/public-sans ^5.2.6` no `package.json`,
`public/fonts/` (ativos servidos) e `ttf2woff2` nas devDependencies.

### 2.4 Banidos (slop) — `DESIGN.md` §Banidos

Texto em gradiente · glassmorphism decorativo · borda lateral colorida · card dentro de card ·
grades de cards idênticos · travessões (em dashes). E a regra de fronteira: o site público **usa**
`.text-gradient-ldc`, `.glass-effect`, `.card-premium`, `.gradient-premium`, `.animate-glow`
(`globals.css` ~380–520) — **não levar isso para o módulo product**. O kit de KPI reforça: *"nunca o
clichê hero-metric com número gigante + gradiente"*.

### 2.5 `docs/design/` e `.impeccable/`

- **`docs/design/`** — existe, com **uma** subpasta: `docs/design/uiux-eficiencia-exterior/`. Não há
  segundo documento de regras; `DESIGN.md` na raiz é a fonte única. Adjacentes:
  `docs/design-brief-simulador-relatorio-2026-07-10.md`,
  `docs/superprompt-benchmark-design-simulador-relatorio-wp.md`,
  `docs/auditorias/auditoria-ux-*.md` com pastas de evidência PNG (`docs/auditorias/evidencias-*/`).
- **`.impeccable/`** — é o **histórico da skill `impeccable`** (crítica de interface). Contém só
  `.impeccable/critique/`, com 4 arquivos datados (`2026-06-29` plano do cliente; `2026-08-21` e
  `2026-08-25` ×2 em `src-app-admin-estudos-r2`). Não é configuração nem build: é a trilha das
  rodadas de crítica visual que produziram o `.ferramenta` e os tokens da §2.1.
- `docs/sdd/` → **não encontrado**. O SDD mora em `docs/specs/`, `docs/contracts/`, `docs/plans/`.

---

## 3. Kit de gráficos — `src/app/admin/wealth-planning/components/charts.tsx`

309 linhas, `"use client"`. **SVG vetorial próprio, escrito à mão — não Recharts.** O docblock:
*"Identidade LDC, sem dependência externa. Tudo recalcula ao vivo. Ver DESIGN.md."* O `DESIGN.md`
confirma: *"mesma identidade do relatório PDF, sem dependência nova além do recharts já existente"* —
o kit convive com Recharts mas não o usa.

### 3.1 O que exporta

| Export | Tipo | O que é |
|---|---|---|
| `StatCard` | React | KPI discreto: rótulo 11px uppercase + número 22px `tabular-nums` + `delta` (▲/▼/—) + `sub`; aceita `accent` |
| `ProgressBar` | React | barra 8px, track `#eceef0`, transição 220ms `cubic-bezier(0.22,1,0.36,1)` |
| `GaugeEnquadramento` | SVG | gauge semicircular 220×140 com **marca de teto** e **marcador de ponta** (não agulha); alterna lime/alerta por `dentro` |
| `RingGauge` | SVG | anel de progresso 160×160, `strokeDasharray` animado |
| `ProjectionChart` | SVG | área + linha + linha de meta tracejada; grid de 4 níveis; eixo em `brlShort` |
| `DepletionChart` | SVG | duas curvas (viver de renda × consumo), marcador vertical de aposentadoria, **marcador de esgotamento**, **clamp anotado de escala** (curva > 3× a meta ⇒ eixo trava em 1,6× e o pico vira anotação), **anti-colisão de rótulo de eixo X** |
| `CaseCards` | React | trio de cards headline com `tone: good/navy/slate` |
| `Donut` | SVG | rosca com gap angular + legenda com percentual |
| `PageHeader` | React | eyebrow + título sans 26px + sub + slot de ação |
| `CHART_COLORS` | const | `{ NAVY, SLATE, LIME, RED, LINE, TRACK, GRID }` |

Internos (não exportados, mas são **o idioma a copiar**): `brlShort` (R$ mil/mi/bi em pt-BR),
`pctFmt`, `num = { fontVariantNumeric: "tabular-nums" }`, e o par de escalas `px(x)` / `py(y)` com
`padL/padR/padT/padB`.

### 3.2 Como é tematizado

**Por constantes locais, não por CSS var.** Linha 9:
`const NAVY = "#262d3d", SLATE = "#577171", LIME = "#98ab44", RED = "#c0584f";` + `LINE/TRACK/GRID`.
As cores entram por `style={{ fill }}` / `stroke` inline. Consequência prática: o kit é **portável
por cópia** (não depende do `globals.css` para cor), mas **não responde a troca de tema** e
**duplica o hex** do `DESIGN.md`. `CHART_COLORS` existe para o resto do app não re-declarar hex.

### 3.3 Quem já reusa (prova de que é kit, não componente de uma tela)

11 arquivos importam de `charts.tsx`, incluindo **de fora** do `wealth-planning`:
`src/app/admin/simulador-holding/page.tsx` (`PageHeader`);
`src/components/wealth-planning/simulator/LiveSimulator.tsx` (`Donut`);
`src/app/admin/wealth-planning/clientes/[id]/plano/page.tsx` (`GaugeEnquadramento`,
`DepletionChart`, `Donut`, `ProgressBar`, `StatCard`);
`.../acompanhamento/page.tsx` (`RingGauge`, `StatCard`, `CHART_COLORS` **+ Recharts `ComposedChart`
no mesmo arquivo** — kit e Recharts coexistem por design);
`src/app/admin/wealth-planning/components/MeetingsTimeline.tsx` (`CHART_COLORS`).

### 3.4 O que **falta** para as telas do LDC Analytics

| Tela | Reusável hoje | Falta construir | Esforço |
|---|---|---|---|
| **Heatmap (regime × ativo) com `n`** | `PageHeader`, `StatCard`, `CHART_COLORS`, `pctFmt`, `num` | **tudo o essencial**: grade de células `<rect>`; **rampa divergente** (o kit tem 1 acento + 1 alerta, não tem escala); anotação de `n` por célula; agrupamento de linhas com vão (padrão `GRUPOS` do Python); legenda de escala; notas de rodapé; supressão de célula | ~200–250 linhas |
| **Scatter de quadrantes com trilha** | o **idioma** `px/py` + `padL..padB` de `ProjectionChart` (copiável quase literal), `CHART_COLORS` | eixos cruzados com tinta de fundo por quadrante; marcas de ponto; **trilha** (path ordenado com opacidade decrescente + ponta destacada — o `circle` de ponta de `ProjectionChart`/`DepletionChart` é o precedente); rótulos com anti-colisão | ~150 linhas |
| **Timeline com faixas de regime** | `DepletionChart` traz **dois padrões diretamente aproveitáveis**: o marcador vertical com rótulo (`apoX`, `depletaX`) e o algoritmo de **anti-sobreposição de rótulo de eixo X** (`stepL`/`labelIdx`). `MeetingsTimeline.tsx` é o precedente de timeline | faixas horizontais (`<rect>` por corrida de regime); legenda categórica; hover/tooltip | ~120 linhas |

**O gap é de design, não de código.** O `DESIGN.md` **não tem rampa divergente** — a paleta é *um*
acento (lime) + *um* alerta. Um heatmap de magnitude com sinal precisa de ~4 passos por lado. E a
saída fácil (lime = positivo) é **explicitamente proibida**: *"Sucesso não ganha verde. Lime é acento
de ação, não de estado."* Isto é uma **decisão nova que precisa ir ao `DESIGN.md` com assinatura do
Edu** — proposta em §9.4.

Registro adjacente importante: o lado Python **já derivou** uma rampa divergente validada em
`estrategia-macro-ldc-dados/apps/analysis/figuras/_comum.py` —
`ARCO_FRIO = ("#6da7ec","#3987e5","#256abf","#184f95")`,
`ARCO_QUENTE = ("#ed8786","#e55555","#bc3d3c","#8f2e2d")`, neutro `#f0efec`, superfície `#fcfcfb`,
tinta `#0b0b0b`, `COR_CRITICO = "#d03b3b"` — mas ela vem da **paleta placeholder brand-neutral da
skill `dataviz`**, **não** da paleta LDC. As duas precisam convergir, senão a figura do PDF e a tela
do app saem de cores diferentes para o mesmo número.

---

## 4. Autenticação e autorização

### 4.1 As três camadas

1. **Middleware — `src/middleware.ts`** (único, 118 linhas). Matcher:
   `["/admin/:path*", "/wealth-planning", "/wealth-planning/:path*", "/news", "/news/:path*"]`.
   Usa `createServerClient` do `@supabase/ssr`, filtra cookie pelo `projectRef` extraído de
   `NEXT_PUBLIC_SUPABASE_URL`, chama `supabase.auth.getUser()` e:
   - sem usuário ou com erro → `redirect /admin/login`;
   - `user.user_metadata?.role` ∉ {`ADMIN`,`EDITOR`} → `redirect /admin/login`;
   - `/admin/settings` com papel ≠ `ADMIN` → `redirect /admin/dashboard`;
   - `try/catch` externo → **fail-closed** (qualquer exceção redireciona ao login).

   Exceções deliberadas e documentadas: `/admin/login` e `/admin/manifest.webmanifest` (o browser
   busca `rel="manifest"` **sem credenciais**; atrás do guard o atalho nascia sem nome nem ícone —
   *"falha silenciosa: a página carrega normalmente e nada no admin denuncia"*).
   **Não é NextAuth**: há `NEXTAUTH_SECRET`/`NEXTAUTH_URL` no `.env.example`, mas são resíduo.
2. **Layout/UI — `src/app/admin/components/AdminLayout.tsx`** (client component). Faz **double-check**
   com `getCurrentUser()` e redireciona; monta a navegação em **grupos** (`Dashboard` solto,
   `Acompanhamento`, `Conteúdo`, `Simuladores`, `Configurações` solto) e aplica **RBAC de menu** pela
   flag `editorOk`: `user.role === "ADMIN" ? g.itens : g.itens.filter(i => i.editorOk)`, com **grupo
   vazio desaparecendo inteiro, título e tudo**. `src/app/admin/layout.tsx` é só metadata (manifest,
   `appleWebApp`, `robots: { index: false }`, `themeColor: '#262d3d'`, `viewportFit: 'cover'`).
3. **API — `src/lib/auth-check.ts` → `checkAdminAuth()`**, usado em **58** route handlers. Valida
   sessão, deriva o papel, faz upsert em `public."User"` e retorna `null` se o papel não for
   `ADMIN`/`EDITOR`. Para o R2 há wrapper: `src/lib/r2-web/route-helpers.ts` → `r2Auth()`, que
   devolve `{ user, session, admin }` — **dois clients**, deliberadamente: `session` (anon + cookie,
   sujeito a RLS por `auth.uid()`) para dado de cliente, e `admin` (service role) só para
   storage/memória.

> **Correção de um falso positivo da minha própria varredura:** 28 rotas `/api/admin/r2/*` parecem
> "sem guarda" se se procura `checkAdminAuth` no arquivo. Elas chamam `r2Auth()`, que chama
> `checkAdminAuth()`. **Estão protegidas.** Registro porque é exatamente o tipo de conclusão errada
> que uma auditoria rápida produz — e porque é a mesma classe de erro que gerou o v1.

### 4.2 `/wealth-planning` (fora de `/admin`) — exposição **já encontrada e corrigida**

O comentário no `src/middleware.ts` é a documentação do incidente: a rota servia o assistente de
reunião — motor de projeção + export de PDF assinado "Consultor LDC Capital" — **a qualquer
visitante**, porque o matcher cobria só `/admin` e `/news`, e respondia **200 em produção sem login**.
Achado na *"auditoria de simplicidade 2026-07-31, S-02"*, corrigido estendendo o matcher, com a
justificativa escrita: *"Ferramenta interna de consultoria não fica pública numa casa autorizada
pela CVM."* A rota continua existindo (`src/app/wealth-planning/page.tsx` + `layout.tsx` com
`robots: noindex`), agora atrás do guard. **É evidência positiva:** o app acha e fecha exposição,
com rastro escrito.

### 4.3 RLS — existe, e é de verdade

29 migrations em `supabase/migrations/` ligam RLS; 16 arquivos declaram política.
`supabase/migrations/20260625000000_wp_foundation.sql` é o padrão da casa:

- `enable row level security` em **12** tabelas `wp_*`.
- Duas funções `security definer set search_path = public`: `public.wp_is_admin()` —
  `exists(select 1 from wp_advisors where id = auth.uid() and role = 'admin' and ativo)` — e
  `public.wp_owns_client(p_client_id uuid)`.
- Políticas por operação escopadas por `advisor_id = auth.uid() or wp_is_admin()`; o `insert` é mais
  restrito (`with check (advisor_id = auth.uid())` — nem admin insere para outro).
- Tabelas-filhas recebem política via `execute format('… wp_owns_client(client_id) …')` em loop —
  isolamento por posse, não por tabela.
- `wp_assumptions` / `wp_assumptions_itcmd`: leitura `using (true)` para `authenticated`, escrita só
  admin. `wp_audit_log` com select restrito.
- `supabase/migrations/20260702150000_r2_foundation.sql` replica em `r2_*` (4 tabelas) e traz
  Anti-SPEC no cabeçalho: *"cliente SEMPRE codificado — nome real/CPF NUNCA persistidos. Prints não
  são persistidos."* `src/lib/r2-web/db.ts` reforça: o **prenome** entra, em uma única coluna
  (`r2_clientes.primeiro_nome`), por decisão datada (ADR-R2-003 + migration `20260914120000`), e o
  caminho do LLM lê por `listClientesParaAgente`, que **não seleciona a coluna**.
- Há **teste de integração de RLS**: `src/lib/r2-web/__tests__/rls.integration.test.ts` cria dois
  usuários via service role e verifica o isolamento.

### 4.4 A falha: `user_metadata.role` é gravável — e aqui ela **vaza para o banco**

**Comparação direta com o achado do v1 no `site-eduardo`: este app está muito melhor na primeira
metade do problema e, num ponto, pior na segunda.**

| | `site-eduardo` (v1) | `site-ldc` (este app) |
|---|---|---|
| Páginas admin sem guarda de rota | **sim** — *"`AdminDashboardPage`, `AdminAnalysisFormPage`, `AdminPDFsPage` e `AdminExtratosPage` não importam guarda alguma"* | **não** — middleware com matcher + double-check no layout + 58 `checkAdminAuth()` |
| Guarda no roteador | **não** — *"`src/App.tsx` não envolve nenhuma rota"* | **sim** — `src/middleware.ts` é guarda de borda |
| RLS no banco | parcial, com furo reconhecido na migration `014` | **sim** — 16 migrations com política, isolamento por `advisor_id`, teste de integração |
| Fonte do papel | `user_metadata.role` | `user_metadata.role` — **mesma classe de falha** |
| Papel persiste no banco a partir do metadata | não reportado | **sim — e é o agravante deste app** |

A cadeia de escalação, com caminho de arquivo:

1. `src/lib/auth-check.ts:32` — `const metadataRole = authUser.user_metadata?.role`.
2. `src/lib/auth-check.ts:35-47` — faz **upsert em `public."User"` com `role: normalizedRole`**,
   usando o client **service role**. O papel autodeclarado é **gravado** como se fosse autoridade.
3. `src/lib/r2-web/route-helpers.ts:27` → `ensureAdvisor(user)` →
   `src/lib/wealth-planning/db.ts:88` — `role: user.role === 'ADMIN' ? 'admin' : 'advisor'`, upsert
   em **`wp_advisors`**, também via service role.
4. `wp_advisors.role = 'admin'` é exatamente o que `public.wp_is_admin()` consulta — e `wp_is_admin()`
   é o que **todas** as políticas RLS usam para liberar `or wp_is_admin()`.

Ou seja: `user_metadata`, que o próprio usuário escreve com a chave anon via
`supabase.auth.updateUser({ data: { role: 'ADMIN' } })`, **promove o usuário a admin no banco** na
requisição seguinte, e a RLS — que está bem escrita — passa a liberar os clientes de **todos** os
advisors. A boa engenharia da §4.3 é anulada por uma linha da §4.4. E `app_metadata`, o campo que
**só** service role escreve, **não é usado em lugar nenhum**: `grep -rn "app_metadata" src/ packages/
supabase/` → **zero** ocorrências. É exatamente o alerta que a própria migration `014` do
`site-eduardo` já tinha escrito: *"A autorização NÃO pode vir de `user_metadata.role`: esse campo é
gravável pelo próprio usuário via `updateUser`."*

**Fatores atenuantes, que mudam a severidade sem mudar o diagnóstico:**

- **Não há UI nem rota de cadastro.** `grep` por `signUp` em `src/` → **zero**. Usuários nascem por
  service role: `scripts/sync-admin-users.ts` (lista **fechada** de 4 e-mails `@ldccapital.com.br`),
  `scripts/seed.ts` e `POST /api/app/advisors` (que é ele mesmo protegido). Se o projeto Supabase
  tiver *"allow new users to sign up"* **desligado** — configuração de Dashboard, **não verificável
  no código** —, o ataque exige **conta existente**. O vetor realista é **interno**: um `EDITOR`
  (consultor) se promove a `ADMIN` e passa a ver a carteira dos colegas. Não é um estranho na rua.
- `scripts/sync-admin-users.ts` mostra que a **intenção** é papel por provisionamento, não por
  autodeclaração. A falha é de implementação, não de desenho.

**Veredito para "dá para confiar nele com dado de alocação?"** — **Sim, com uma distinção que
importa.** O dataset do LDC Analytics é **macro + métrica de regime × ativo**: é IP do Comitê e é
material potencialmente sensível sob CVM 3976-4 (porque *parece* recomendação), mas **não** é PII de
cliente, e **não** é da mesma classe do que o app já guarda (carteira e plano de cliente real).
Colocar o Analytics ali **não cria** superfície nova: ele herda um guard que já protege algo mais
sensível. O que **não** entra antes da correção é número ainda não publicado ao Comitê e marcado
`publicavel: false` — caso de `internacional_pesos.parquet` (decisão **D-af** no `TODO.md` do projeto
de dados). Correção proposta em §9.3.

---

## 5. Padrão de dados — existe um precedente de "dataset versionado servido ao front"

**Sim. E é exatamente o molde de que o LDC Analytics precisa.** Chama-se `referencia-r2/`.

### 5.1 `referencia-r2/` — JSON versionado no repo, lido por `fs` em runtime, atrás do guard

17 JSON na raiz do app: `acoes.json`, `alocacoes.json`, `ancora-valor.json`,
`blocos-argumentativos.json`, `blocos-fixos.json`, `carteiras-modelo.json`, `deteccao.json`,
`fees.json`, `guardrail.json`, `opcionais.json`, `projecao.json`, `proposta.json`,
`racional-classes.json`, `raiox.json`, `retornos.json`, `thresholds.json`, `tom-revisao.json`.

O mecanismo, em quatro peças:

1. **Resolução de caminho** — `src/lib/r2-web/paths.ts:12`:
   `return join(process.cwd(), 'referencia-r2') + '/'`. O docblock explica por que não é
   `import.meta.url`: *"o default por import.meta.url não sobrevive ao bundle do Next/Vercel"*.
   Mesmo padrão em `src/lib/r2/tools/referencia/index.ts:39` e `src/lib/r2/tools/tom/index.ts:87`.
2. **Entrada no bundle serverless** — `next.config.ts`:
   `outputFileTracingIncludes: { "/api/admin/r2/**": ["./referencia-r2/**", "./assets-r2/**"] }`.
   O JSON **não** vai para `public/`; vai para o **trace da rota serverless**, acessível só por quem
   passa pelo guard da rota. **Esse detalhe é a razão pela qual a opção (A) da §8 é segura.**
3. **Contrato** — os loaders aceitam `baseDir` por injeção; schema em Zod
   (`src/lib/r2-web/plano-contratos.ts`, `@ldcclaw/types`). `referencia-r2/` é descrito em
   `paths.ts` como *"thresholds/alocações/textos versionados (Anti-SPEC)"* e em
   `src/app/api/admin/r2/perfil/route.ts:43` como *"NÃO é editável por consultor"*.
4. **Teste trava o dado** — `src/lib/r2/__tests__/unit/tom/tom-revisao.test.ts:150` faz
   `readFileSync(join(process.cwd(), 'referencia-r2', arq))` e valida;
   `src/lib/r2/tools/aderencia/index.ts:106` emite aviso nomeando o arquivo quando a soma dos pesos
   foge de 100% ±0,5pp: *"corrija referencia-r2/carteiras-modelo.json"*. O dataset é **testado**, não
   só lido.

### 5.2 Os outros padrões de dado no app

| Padrão | Onde | Uso |
|---|---|---|
| **Supabase Postgres + RLS** | `supabase/migrations/`, `src/lib/wealth-planning/db.ts`, `src/lib/r2-web/db.ts` | todo dado mutável de cliente/advisor |
| **Supabase Storage** | `src/lib/r2-web/paths.ts:chaveStorage`, migration `20260707120300_news_storage_buckets.sql` | artefatos gerados (DOCX/PDF/HTML), imagens de carrossel |
| **Vercel Blob** | `@vercel/blob ^2.3.3`, `src/app/api/admin/bloomberg-pdfs/upload/route.ts` | upload de PDF Bloomberg |
| **Asset de marca em disco** | `assets-r2/brand/` (só `.gitkeep` hoje) | fotos-slot do relatório |
| **`.data/leads.json`** | `.data/leads.json` | único arquivo; fallback local de lead, não é padrão |

`packages/shared/` é **mínimo**: só `packages/shared/types/wealth-planning.ts` + `.gitkeep`. **Não** é
workspace npm com build próprio — é pasta de tipos compartilhados. E **não** existe object storage
externo tipo Cloudflare R2: `assets-r2/` é pasta local, e `src/lib/r2/` / `src/lib/r2-web/` são o
**motor do produto "Estudo R2"**, não storage. Vale dizer explicitamente porque o nome engana.

### 5.3 O lado do projeto de dados — o que já existe para exportar

- `estrategia-macro-ldc-dados/data/canonical/` — 47 artefatos parquet + `ldc.duckdb` + `MANIFEST.json`.
- **`data/canonical/MANIFEST.json`** é o contrato de versionamento, e é bom: por artefato `sha256`,
  `bytes`, `linhas`, `colunas`, `date_min`/`date_max`, `pct_nulos`, `nulos_por_coluna_pct`,
  `determinista`, **`publicavel: true|false`**. No agregado: `sha256` global, `n_artefatos`,
  `n_artefatos_fora_do_agregado`, `bytes`, `linhas`.
- As figuras **já emitem o dado ao lado da imagem**: `data/canonical/figuras/heatmap_dados.parquet`,
  `timeline_regimes_dados.parquet`, mais `.png` e `.svg` em duas vistas (`_asof`, `_revised`) e
  `heatmap_horizonte_cruzado.*`.
- Geradores: `apps/analysis/figuras/heatmap_regime_ativo.py` (com `ResultadoHeatmap =
  {dados, figuras, caminhos, caminho_dados, relatorio}` — *"a figura é a leitura, isto é a
  evidência"*), `timeline_regimes.py`, `_comum.py`, `apps/analysis/tabelas/ranking_regime_atual.py`.
- Empacotador: `apps/analysis/entrega/montar_pacote.py` — já exporta `.csv` pt-BR,
  `PACOTE-COMITE.xlsx` de 8 abas, `MANIFEST.json`, `FROZEN.txt`, `HASHES.txt`, com **lista de
  inclusão fechada** conferida contra o `MANIFEST.json` e bloqueio em `publicavel: false`.
- `apps/web_export/` → **não encontrado.** Não existe hoje.

**Conclusão da §5:** não falta padrão em nenhum dos dois lados. Falta só a **ponte**: um exportador
JSON no lado Python e um loader `fs` + guard no lado Next — e os dois moldes já estão escritos
(`montar_pacote.py` e `referencia-r2/`).

---

## 6. Infra

| Item | Estado |
|---|---|
| **Hospedagem** | Vercel. `.vercel/project.json` → `projectName: "site-ldc-capital"`, `projectId: prj_JMqdgZSYVDGHz8FEHOBrLNElzMIm`, `orgId: team_p1sq2J2cKb1DegOBqxezTKQ3`. `VERCEL_CONFIG.md` documenta. |
| **Build** | `vercel.json`: `buildCommand: npm run build`, `framework: nextjs`, `installCommand: npm install`. |
| **Cron** | **8 crons** em `vercel.json`: `/api/news/cron` (10h e 17h), `/api/posts/cleanup-expired-tokens` (3h), `/api/admin/bloomberg-pdfs/cleanup` (4h), `/api/admin/blog-carousels/cleanup` (5h), `/api/cron/guia-backfill` (11h), `/api/cron/ebook-backfill` (12h), `/api/cron/r2-resumo-diario` (10h30). Protegidos por `CRON_SECRET`. |
| **Preview por branch** | **Sim** (default Vercel), com armadilha documentada: `src/lib/r2-web/route-helpers.ts:anonymizeSalt()` **lança exceção** quando `ANONYMIZE_SALT` falta — e falta **de propósito** em preview, porque *"preview compartilha o banco de PRODUÇÃO"* e um sal divergente corromperia o código do cliente (runbook `docs/wiki/runbooks/deploy-vercel.md` §5.1). **Preview e produção usam o mesmo Supabase.** |
| **CI** | `.github/workflows/ci.yml` — **um** workflow, job **`n1` apenas**: checkout `submodules: recursive`, Node 20 + cache npm, `npm ci`, `lint`, `typecheck`, `test`. `n2` (integration/contract/build) e `n3` (e2e/smoke/migration) **comentados**, com gatilho previsto por label `classe-c`/`classe-d`. Dispara em push/PR para `main`/`master`. |
| **Build tolerante** | `next.config.ts`: `eslint.ignoreDuringBuilds: true`; `typescript.ignoreBuildErrors` está **comentado** (typecheck real vale). |
| **Testes** | **146** arquivos `*.test.ts(x)`, todos em `src/**/__tests__/`. `vitest.config.ts`: `environment: "node"`, `exclude: [node_modules, .next, scripts, wealth-planning]`, reporters `["default","json"]` → `test-results/vitest.json` (o reporter default não nomeia o teste fora de TTY, e é aí que a intermitência aparece). |
| **`tests/`** | **vazio**: `tests/{unit,integration,contract,e2e}/.gitkeep` — estrutura do Harness aguardando N2/N3. |
| **Playwright** | dependência de runtime (PDF, `scripts/e2e-r2-full.mjs`). **Sem** `playwright.config.*`, sem suíte e2e versionada. `e2e-artifacts/` e `.playwright-mcp/` guardam evidência de rodadas manuais via MCP. |
| **Env** | 38 chaves em `.env.example`. Essenciais: `NEXT_PUBLIC_SUPABASE_{URL,ANON_KEY}`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `DATABASE_URL`, `CRON_SECRET`, `NEXT_PUBLIC_SITE_URL`, + `ANONYMIZE_SALT` (**não** está no example). IA: `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `PERPLEXITY_API_KEY`, `GOOGLE_GEMINI_API_KEY`. E-mail: `RESEND_API_KEY`, `SMTP_*`. Resíduo: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `ADMIN_PASSWORD`. Flags: `NEXT_PUBLIC_WEALTH_PLANNING_V2`, `NEWS_PIPELINE_ENABLED`. |
| **Higiene — risco registrado** | `.env` (6.463 bytes) está no diretório de trabalho, e `ldc-project-476717-b9cd681b3bfa.json` (service account Google) está **na raiz do app**. Se estão no `.gitignore` não foi auditado aqui. **Merece verificação dedicada**, fora do escopo deste relatório. |

---

## 7. Qualidade e convenções — e a convivência com o Harness do projeto de dados

**Os dois projetos rodam o mesmo Harness, na mesma versão.** É a descoberta que mais pesa na §8.

| | `site-ldc/site-ldc` | `estrategia-macro-ldc-dados` |
|---|---|---|
| `AGENTS.md` | **sim**, 16.508 bytes, "Harness v3.2", 17 seções | **sim**, 27.613 bytes, "Harness v3.2" |
| `CLAUDE.md` | **sim**, 5.818 bytes | **sim**, 7.615 bytes |
| `TODO.md` | **sim**, 17.432 bytes | **sim**, 174.867 bytes |
| Classes A/B/C/D | §3 | §2 |
| CI por níveis N1/N2/N3 | §12 — só N1 ativo | `.github/workflows/ci.yml` — mesma estrutura |
| Feature Contract | §5 | §5 + `docs/plans/_templates/` |
| Gates de autonomia | §6 | §6 |
| Project Wiki | §8 → `docs/wiki/{index,log,overview,architecture,modules/,runbooks/}` | idem |
| ADRs | §10 + `docs/decisions/adr/`, `ADR-R2-00{2,3}` | `docs/decisions/adr/` |
| Antipadrões | §14 (13 itens) | §14 |
| Gate de publicação | — | §14, **8 passos obrigatórios** |

Convenções específicas do `site-ldc` que um módulo novo tem de respeitar
(`CLAUDE.md` "Memórias-chave" + `AGENTS.md` §10/§14):

- **ADR-001 — Anti-Anthropic absoluto.** Nunca importar `@anthropic-ai/sdk`. Stack IA é OpenAI
  GPT-5-mini + Perplexity Sonar Pro + Gemini 2.5. *"ADR-001 é trava física."* Todo modelo passa por
  `src/lib/r2-web/llm.ts` (trilho único, ADR-013).
- **ADR-003 — Bloomberg é sinal interno autoral.** PDFs via e-mail são input privado; **jamais**
  citar como fonte. *"ADR-003 é absoluta."*
- **CVM 3976-4.** Qualquer feature de conteúdo IA é **classe C/D**. Anti-SPEC §6 é "sagrada".
- **ADR-R2-002** — a fonte de verdade do motor R2 é este repo; o LDCclaw está congelado.
- **ADR-R2-003** — prenome do cliente em uma única coluna; nada mais de PII.
- Antipadrões relevantes: *"Mexi num arquivo fora da lista porque estava no caminho" → BLOQUEADO*;
  *"Refactor preventivo porque o código está feio" → não*; *"Esqueci de atualizar `wiki/log.md`" →
  feature B/C/D não fecha*.
- **`AGENTS.md` §16 e §17 são adendos de módulo** (Wealth Planning 2026-06-25, Estudo R2 web
  2026-07-03). Ou seja: **o app já tem a convenção de abrir um adendo por módulo novo.** Um
  `§18 — Adendo LDC Analytics` é o caminho pavimentado.

`.claude/` do app tem só duas skills de criativo (`carrossel-padrao-visual`, `ldc-creatives`) —
**não** há regra de projeto em `.claude/`; a regra está em `AGENTS.md`/`CLAUDE.md`. `.cursor/` existe
**no wrapper** (`site-ldc/.cursor/`), não no app. **Não encontrados:**
`.github/PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`, `docs/sdd/`. O padrão de PR está em prosa no
`AGENTS.md` (matriz de validação obrigatória para B/C/D).

**Nota decisiva sobre o lado dos dados.** O `AGENTS.md` do projeto de dados abre com: *"Não é SaaS,
não é web. Sem auth, sem pagamento, sem deploy (roda local). Consequência prática: o risco não é
'derrubar o site' — é entregar número errado para o comitê."* E o backlog pós-Comitê **F-040** diz,
literalmente: *"transforma o projeto em ativo reutilizável… **Sem dashboard hospedado**."* Qualquer
opção da §8 que coloque um front no ar **muda essa premissa** e exige ADR no projeto de dados. Não é
obstáculo — é um passo que tem de estar no plano.

---

## 8. RECONSIDERAÇÃO — (A) módulo no app existente × (B) projeto novo × (C) híbrido

### 8.0 O que mudou na base factual

Três fatos novos derrubam a premissa dos dois relatórios anteriores:

1. **Existe app LDC em produção**, Next 15 + React 19 + Tailwind 4, com `DESIGN.md`, `.ferramenta`,
   kit de gráficos SVG próprio, fontes locais e logo (§1–§3).
2. **Existe auth Supabase com RLS**, guarda de borda em middleware, RBAC de menu e teste de
   isolamento (§4) — não é "do zero", e **não** "arrastaria um banco": o banco já está lá.
3. **Existe precedente de dataset JSON versionado servido atrás do guard** (`referencia-r2/` +
   `outputFileTracingIncludes`), com teste que trava o conteúdo (§5.1).

E um fato que **não** mudou e continua pesando: o `MANIFEST.json`, o `freeze --tag`, o `verify` por
`sha256` e o gate de 8 passos do `AGENTS.md §14` do projeto de dados são bons e **independentes de
front**. Tudo que o relatório de arquitetura escreveu sobre **exportador, gate, tag, ponteiro
`current.json`, hash no rodapé e CI sem rede continua válido.** O que cai é a escolha de stack, a
escolha de auth e o scaffold.

### 8.1 Opção (A) — novo módulo `/admin/analytics-macro` dentro do app existente

Seguindo o precedente do `wealth-planning` (disciplina) e do `simulador-eficiencia-exterior` (forma).

**Ganha:**
- **Identidade de graça.** `DESIGN.md` + `.ferramenta` + `.ldc-work` + `charts.tsx` + fontes locais +
  logo. O relatório (2) orçou `core/charts/` em **2,5 dias** "from scratch"; aqui `StatCard`,
  `PageHeader`, `CHART_COLORS`, `ProgressBar`, `Donut`, `brlShort`/`pctFmt` e o idioma `px/py` já
  existem e já são reusados por 11 arquivos. Sobram só os 3 primitivos novos (§3.4).
- **Auth de graça, e melhor que a proposta.** O matcher `/admin/:path*` cobre o módulo **no dia em
  que o arquivo é criado** — zero linha de auth. E é **identidade por pessoa**, que o próprio
  relatório (2) definiu como requisito (*"identidade por pessoa > senha coletiva para dado de
  alocação"*) e para o qual propôs **trocar de hospedagem** (Cloudflare Pages + Access).
- **Deploy e CI de graça.** Vercel configurado, preview por branch, N1 verde em PR.
- **Padrão de dado de graça**, e o **mais seguro dos dois desenhos** — `referencia-r2/` serve JSON
  versionado **atrás do guard**, enquanto `public/data/<tag>/` (proposta de (2)) seria servido pela
  camada **estática**, fora de qualquer middleware. Detalhe em §9.3.
- **Zero infra nova.** Nenhum repo, projeto Vercel, domínio ou credencial. Pelo `AGENTS.md §2` do
  projeto de dados, credencial nova **promove a feature a classe D**; não criar nenhuma a mantém B/C.
- **Velocidade até o Alexandre ver algo.** A ferramenta mora ao lado do que Luciano, Marcos e Eduardo
  já abrem todo dia — não há "mais um link, mais uma senha".
- **Convenção pavimentada.** `AGENTS.md §16`/`§17` são adendos de módulo; `§18` é o próximo.

**Perde / arrisca:**
- **Dado de alocação num app que também é site público.** É o risco real, e é de *configuração*, não
  de arquitetura: uma rota mal colocada (em `public/`, ou fora do matcher) vaza. Mitigação: dado só
  por **API route sob `/api/admin/`** com `checkAdminAuth()`, + teste de CI que falha se um JSON de
  dataset aparecer em `public/`. **É o item nº 1 do plano (§9.3).**
- **A falha da §4.4 passa a cobrir também o Analytics.** Verdade — mas ela **já** cobre carteira de
  cliente, que é mais sensível. (A) não cria o problema; herda-o, e dá motivo para consertá-lo.
  Mitigação dura: enquanto `user_metadata.role` for a fonte do papel, **nada `publicavel: false`**.
- **Tamanho de bundle.** Risco **baixo**: App Router faz code-splitting por rota, `/admin/*` já
  carrega Recharts em 3 telas, e o módulo é SVG próprio. Mas o dataset precisa ser `fetch`ado, não
  `import`ado, para não entrar no chunk.
- **Acoplamento.** Regressão no app (lint/typecheck) bloqueia o PR do Analytics e vice-versa. Com N1
  em minutos e 146 testes verdes, custo real mas pequeno.
- **O app é submódulo git de outro repo.** Todo commit exige dois passos (`AGENTS.md §13`), o CI roda
  `submodules: recursive`, e o branch atual é `feat/agente-consultor` — **há trabalho em voo** com o
  qual conviver. Atrito de processo, não impedimento, e atrito que o Edu já paga diariamente.
- **Dois repos no caminho de uma entrega.** O JSON nasce em `estrategia-macro-ldc-dados` e tem de
  chegar em `site-ldc/site-ldc` — cópia versionada entre repos (§9.3).
- **Mudança de premissa no projeto de dados.** `AGENTS.md`: "não é web, sem deploy". Exige ADR lá.

### 8.2 Opção (B) — projeto novo separado (a recomendação anterior), reavaliada

O relatório (2) recomendou Vite 6 + React 18 + Tailwind 3 + react-router, `apps/portal/` dentro de
`estrategia-macro-ldc-dados`, auth por Vercel Authentication, dataset em `public/data/<tag>/`.

**O que continua certo:** JSON pré-computado no build; tag + `current.json` como ponteiro; hash no
rodapé de toda tela; freeze local com CI validando sem rede; `apps/web_export/` em Python como única
ponte; herança do gate (`publicavel`, `n<5`, `n<8`, `especificacao_congelada`); as referências de UI
(Verdad, Macrobond, ALFRED, BIS). **Nada disso depende de qual front existe.**

**O que não se sustenta mais:**
- **A justificativa de stack caiu.** *"a stack LDC é Vite+React+TS+Tailwind+Recharts"* e *"um só
  modelo mental com o site institucional"* — o site institucional é **Next 15 / React 19 / Tailwind 4**.
  O argumento do modelo mental único agora aponta para o lado **oposto**: Vite+react-router é o
  modelo mental **divergente**. E `RouteObject[]` do react-router, no registry proposto, não é o
  roteamento desta casa.
- **A recusa do Supabase Auth caiu.** *"não na v1 — arrastaria o banco que o ADR-007 veta"*. Não
  arrasta nada: o banco já está em produção, com RLS, `wp_advisors` e teste de isolamento. E Vercel
  Authentication é conta-de-plataforma ou senha coletiva — inferior, pelo critério do próprio
  relatório, a identidade por pessoa.
- **A premissa de "nada a herdar" caiu.** Dos 13 dias de infra orçados, **~6,5** (scaffold 2,0 +
  `core/charts/` 2,5 + auth/deploy 0,5 + parte de `dataset.ts` e CI) são exatamente o que o
  `site-ldc` já tem pronto.
- **A ausência de design tokens era consequência do erro.** A §B.7 do levantamento é explícita: o
  relatório (2) menciona *"wrappers Recharts com os defaults da LDC"* **sem nunca definir nem
  localizar** esses defaults, porque delegava isso ao relatório (1), que concluiu que não existiam.
  `DESIGN.md` resolve a lacuna inteira.

**O que (B) ainda ganha, honestamente:**
- **Isolamento de segurança real.** Deployment separado, protegido por inteiro, sem site público ao
  lado. É a opção mais defensável se a decisão for "nada do Comitê perto de conteúdo público".
- **Não herda a falha da §4.4.**
- **Não herda o submódulo** nem o acoplamento de CI.
- **Mono-repo com o pipeline:** dado e front versionam juntos, `git revert` é rollback de ambos.
  Em (A) o JSON atravessa dois repositórios.

**O que (B) perde:** recria identidade (ou copia e divergirá), recria auth pior, recria deploy, abre
projeto Vercel novo, e entrega **semanas** depois.

### 8.3 Opção (C) — híbrido

Duas leituras, e vale separá-las porque têm perfis muito diferentes.

**(C1) App separado consumindo `packages/shared` e o design system por cópia controlada.**
Morre na primeira linha: `packages/shared/` do `site-ldc` tem **um** arquivo
(`types/wealth-planning.ts`); não é workspace npm, não tem build, não é publicado. "Consumir" exige
transformá-lo em pacote de verdade — trabalho novo em dois repos, para servir um consumidor. E a
"cópia controlada" do design system é a pior parte: `charts.tsx` **duplica o hex** em constantes
locais (§3.2), então a cópia nasce com duas fontes de verdade para navy, slate, lime e alerta — o
diagnóstico que o próprio v1 fez sobre o `site-eduardo` ("paleta duplicada… duas fontes de verdade")
e recomendou **não** repetir. Nada impede o drift, e o drift em paleta é exatamente o que o
`.impeccable/critique/` passou quatro rodadas consertando.

**(C2) Subdomínio próprio no mesmo repo** (ex.: `analytics.ldccapital.com.br` → segundo projeto
Vercel apontando para o mesmo repositório, ou um route group isolado). Tecnicamente viável e com um
ganho real: dá para ligar **Vercel Authentication no projeto do subdomínio** sem afetar o site
público, somando duas camadas de auth. Mas: dois projetos Vercel sobre um repo significa dois builds,
dois conjuntos de env, e um `middleware.ts` compartilhado que precisa saber em qual host está
rodando. É complexidade de infra para comprar uma camada que, em (A), já se resolve com API route
atrás de `checkAdminAuth()`. **Vale como fase 2** se o Comitê (gente de fora do time de consultoria)
passar a entrar direto.

### 8.4 Comparação

| Critério | **(A)** módulo no app | **(B)** projeto novo | **(C2)** subdomínio mesmo repo |
|---|---|---|---|
| **Esforço — infra** | **1,5–2 d** (rota + nav + loader + API route + teste de CI + ADR) | **13 d** (orçamento do relatório 2, confirmado) | **4–5 d** (2º projeto Vercel, env, host-aware middleware, auth extra) |
| **Esforço — primitivos de gráfico** | **1,5–2 d** (3 primitivos; o resto é reuso) | **2,5 d** (from scratch) | 1,5–2 d (reuso) |
| **Esforço — módulo 1 (6 telas)** | **9–10 d** | 12 d | 9–10 d |
| **Total até o MVP** | **≈ 13–14 dias-agente** | **≈ 25 dias-agente** | ≈ 16–17 dias-agente |
| **Risco de segurança** | **médio-baixo** — herda guard que já protege PII; herda a falha §4.4; risco de configuração (`public/`) mitigável por teste | **baixo** — isolado, sem site público ao lado | **baixo-médio** — auth dupla, mas superfície de config maior |
| **Velocidade até o Alexandre ver algo** | **~3–4 dias** para 1ª tela navegável com dado real (nav + heatmap) | **~8–10 dias** (infra antes de qualquer pixel) | ~6–7 dias |
| **Manutenção** | **menor** — um design system, um auth, um deploy, um CI. Custo: acoplamento de CI + submódulo | **maior** — segunda identidade que divergirá, segundo auth, segundo deploy | **média** — um código, duas configs de deploy |
| **Gate de publicação** | gate vive no exportador Python (inalterado); o site ganha teste de CI que confere `sha256` vs `FROZEN.txt` e ausência de `publicavel:false`. **O gate de 8 passos do `AGENTS.md §14` continua sendo a autoridade** | idem, e com rollback por `git revert` no mesmo repo do dado | idem (A) |
| **Premissa "não é web" do projeto de dados** | muda → **ADR obrigatório** | muda → **ADR obrigatório** | muda → **ADR obrigatório** |

### 8.5 Recomendação: **(A)**, com três pré-condições

**Recomendo (A): um módulo novo `/admin/analytics-macro` dentro do app existente.** Isto contraria
explicitamente as duas conclusões anteriores — o v1 ("a identidade LDC ainda não existe em nenhum
arquivo lido"; "o modelo de segurança desse repositório não aguenta hospedar dado de alocação", dito
do `site-eduardo` e herdado como se fosse geral) e o relatório de arquitetura (projeto novo em
Vite+React, auth do zero, `core/charts/` from scratch).

**A defesa, em três movimentos:**

1. **O trabalho que (B) orça já está feito e em produção.** `DESIGN.md` com paleta, papel semântico,
   tipografia e lista de banidos; `.ferramenta` com escala e neutro tintado por token; kit SVG com 10
   exports já reusado por 11 arquivos; fontes locais; auth com RLS, RBAC e teste de isolamento;
   deploy com preview; CI verde; e um precedente de dataset JSON versionado servido atrás do guard.
   Isso não é "massa crítica insuficiente" — é a infra inteira que (B) planejava construir. Refazer é
   pagar ~12 dias-agente e **ganhar uma segunda identidade que vai divergir da primeira**.
2. **(A) é mais segura do que a proposta de (B) no ponto que mais importa: onde o JSON mora.** (B)
   propôs `public/data/<tag>/*.json` protegido por Vercel Authentication no deployment inteiro — o
   que funciona só porque (B) não tem site público. Em (A) o `public/` está proibido, e o padrão
   correto já existe no repo: JSON fora de `public/`, `outputFileTracingIncludes`, servido por API
   route atrás de `checkAdminAuth()`. É **mais** controle sobre quem lê o número, não menos.
   E a auth resultante é identidade por pessoa — o requisito que (B) só alcançaria trocando de host.
3. **A objeção de segurança é real mas está mal endereçada.** A falha da §4.4 é séria e deve ser
   corrigida — mas ela hoje expõe **carteira e plano de cliente real**, que é dado mais sensível que
   métrica de regime × ativo. Mover o Analytics para fora não conserta isso; só adia. O caminho certo
   é: (A) **mais** a correção de `app_metadata` como item próprio (§9.3), **mais** a regra de que
   nada `publicavel: false` entra até a correção estar em produção. Assim o Analytics vira o motivo
   pelo qual a falha é consertada, em vez de uma razão para criar um segundo sistema e deixá-la lá.

**Pré-condições (sem elas, a recomendação não vale):**

- **P1.** Nenhum byte do dataset em `public/`. Serviço só por API route sob `/api/admin/`, com
  `outputFileTracingIncludes`. **Teste de CI que falha** se um JSON de dataset aparecer em `public/`.
- **P2.** Enquanto `user_metadata.role` for a fonte do papel, **nada marcado `publicavel: false`**
  entra no módulo (hoje: `internacional_pesos.parquet`, decisão **D-af**). O exportador já recusa;
  a regra aqui é não contorná-lo.
- **P3.** **ADR no projeto de dados**, antes da primeira linha de código, revisando a premissa "não é
  web, sem deploy" do `AGENTS.md` e declarando onde vive a fronteira. É o `ADR-008` que o relatório
  (2) já recomendou, com o conteúdo corrigido: *"LDC Analytics: módulo interno no app LDC
  (`/admin/analytics-macro`), dado congelado servido fora de `public/` atrás da auth existente, sem
  banco novo na v1"*, citando ADR-006/007.

**Fase 2, se e quando o Comitê entrar direto:** migrar para **(C2)** — subdomínio próprio no mesmo
repo, com Vercel Authentication somada. O módulo escrito em (A) migra sem reescrita; o inverso
(começar em (B) e integrar depois) custa a reescrita inteira.

**E uma recomendação de sequência, independente de A/B/C:** o relatório (2) propôs um **v0 de 1–2
dias** — publicar o HTML já executado do caderno (`data/canonical/entrega/entrega_comite_2026-10-14.html`,
2,09 MB) atrás de auth. Com (A) isso é ainda mais barato: uma rota `/admin/analytics-macro/caderno`
servindo o HTML. **Vale fazer isso primeiro**, na semana do Comitê, e começar o módulo depois.

---

## 9. Plano concreto da opção (A)

### 9.1 Onde o módulo mora

```
src/app/admin/analytics-macro/
  page.tsx                      # Server Component fino (convenção /admin/bloomberg-pdfs,
                                # /admin/artigos-ia): export const dynamic = "force-dynamic",
                                # metadata { title: "Alocação Macro — Admin LDC" }, retorna o client
  AnalyticsMacroShell.tsx       # "use client" — AdminLayout + <div className="ferramenta ldc-work">
  caderno/page.tsx              # v0: serve o HTML executado do caderno
  visao/page.tsx                # "em que regime estamos" — 3 lentes + concordância
  quadrantes/page.tsx           # scatter g_score × pi_score com trilha temporal
  heatmap/page.tsx              # regime × ativo, com n, flags e chave revised/asof
  vizinhos/page.tsx             # "momentos semelhantes", 8 trimestres, com dispersão
  internacional/page.tsx        # faixa, nunca ponto (desabilitado enquanto publicavel:false)
  metodologia/page.tsx          # renderiza o markdown existente — tela de primeira classe
  versoes/page.tsx              # histórico de tags/hashes (estilo releases do BIS)
  components/
    charts-macro.tsx            # OS 3 PRIMITIVOS NOVOS (§3.4), importando CHART_COLORS
    gate.tsx                    # <GateBanner/> <NConclusao/> <UnidadeBadge/> <RodapeVersao/>
    dataset.ts                  # client: lê current.json, FIXA a tag da sessão, valida o manifest
src/app/api/admin/analytics-macro/
  current/route.ts              # GET → ponteiro {tag, dataset_sha256}; Cache-Control: no-store
  [tag]/[view]/route.ts         # GET → a view; Cache-Control: private, immutable
analytics-macro/                # ← o dataset, NA RAIZ DO APP, fora de public/ (molde referencia-r2/)
  current.json
  <tag>/{manifest,regimes_timeline,heatmap_regime_ativo,ranking_atual,
         vizinhos,internacional,macro_series}.json
```

Mudanças fora do módulo, mínimas e nomeáveis num Feature Contract:

- `next.config.ts` — uma entrada:
  `outputFileTracingIncludes: { "/api/admin/analytics-macro/**": ["./analytics-macro/**"] }`.
- `src/app/admin/components/AdminLayout.tsx` — um grupo novo no array `grupos`.
- `AGENTS.md` — `§18 — Adendo LDC Analytics` (mesma forma de §16/§17).
- `docs/wiki/modules/analytics-macro.md` + linha em `docs/wiki/log.md`.
- `src/lib/analytics-macro/` — loader de servidor (`fs` + Zod), espelhando `src/lib/r2-web/paths.ts`.

**Nada mais.** Nenhum arquivo do site público, nenhum arquivo do `wealth-planning`, nenhuma migration.

### 9.2 Como a rota é protegida

- **De graça, na criação do arquivo.** `src/middleware.ts` já tem `/admin/:path*` no matcher: sem
  sessão → `/admin/login`; papel ∉ {ADMIN, EDITOR} → `/admin/login`; exceção → fail-closed.
- **Segunda camada:** o shell usa `AdminLayout`, que faz double-check com `getCurrentUser()`.
- **Terceira camada (a que realmente importa):** as duas API routes chamam `checkAdminAuth()` antes
  de ler disco. É o que impede alguém de `curl`ar o JSON com cookie inválido.
- **Menu:** no array `grupos` do `AdminLayout.tsx`, grupo novo **`Comitê de Alocação`**, com
  `editorOk` **ausente** (ou seja: só ADMIN) no MVP. O grupo vazio desaparece inteiro para o
  consultor — o mecanismo já existe e é testado pelo comportamento atual. Isso é **mais restritivo**
  que o resto de `/admin` e é a decisão certa para dado do Comitê. Abrir para `EDITOR` depois é mudar
  uma flag. Posição: **grupo próprio**, não dentro de `Conteúdo` ao lado de `analytics/utm` — a
  navegação é agrupada **por ofício**, e "o que o Comitê decide" não é o ofício de publicar conteúdo.
- **Não indexado:** `src/app/admin/layout.tsx` já declara `robots: { index: false, follow: false }`.

### 9.3 Como o JSON do dataset chega

**Resposta curta: pasta na raiz do app (não `public/`), servida por API route.** O molde é
`referencia-r2/`, item por item:

| Peça | `referencia-r2/` (existe) | `analytics-macro/` (novo) |
|---|---|---|
| Local | raiz do app | raiz do app — **nunca `public/`** |
| Caminho em runtime | `join(process.cwd(), 'referencia-r2')` | `join(process.cwd(), 'analytics-macro')` |
| Entra no deploy | `outputFileTracingIncludes["/api/admin/r2/**"]` | `outputFileTracingIncludes["/api/admin/analytics-macro/**"]` |
| Validação | Zod + teste que lê o arquivo | Zod gerado do `schemas.py` + teste que confere `sha256` vs `FROZEN.txt` |
| Quem serve | API route com `r2Auth()` | API route com `checkAdminAuth()` |

**Por que não `public/`** — e isto é a correção técnica mais importante deste relatório em relação à
proposta anterior: em Next na Vercel, `public/` é servido pela camada **estática**, que **não passa
pelo middleware**. `public/data/<tag>/heatmap.json` seria **lido por qualquer um** que soubesse a
URL. Em (B) isso era aceitável porque o deployment inteiro ficava atrás de Vercel Authentication; em
(A), onde o mesmo deployment serve o site institucional, **não é**. `referencia-r2/` existe
exatamente por esse motivo e resolve.

**Por que não Supabase/R2 no MVP:** o recorte útil mede **~608 KB** (medição do relatório 2) e cabe
no repo. Credencial nova promoveria a feature a **classe D** pelo `AGENTS.md §2`. Supabase Storage
em bucket privado é a **saída de fase 2**, se o payload crescer.

**A travessia entre os dois repos.** O exportador Python permanece como o relatório (2) desenhou —
`estrategia-macro-ldc-dados/apps/web_export/`, classe C, única ponte, aplicando o gate
(`publicavel=false` → corta; `especificacao_congelada` → marca; `n<5` → sem conclusão; `n<8` →
alerta; conversão de unidade só em `unidades.py`). Muda só o `--destino`:

```
# na máquina do Edu
python -m apps.web_export --tag comite-2026-10-14 \
    --destino "C:/Users/edusp/Projetos_App_Desktop/site-ldc/site-ldc/analytics-macro"
# escreve <tag>/*.json e, POR ÚLTIMO, current.json (o ponteiro sempre por último)
# depois: commit no submódulo (AGENTS.md §13) → N1 + teste do dataset → Vercel
```

E o teste de CI que o relatório (2) acertadamente chamou de "o primeiro que eu escreveria", agora do
lado do site, em `src/lib/analytics-macro/__tests__/dataset.test.ts`:

1. todo `<tag>/manifest.json` tem `dataset_sha256` que casa com o `FROZEN.txt` citado;
2. **nenhuma** view contém dado vindo de artefato `publicavel: false`;
3. `especificacao_congelada` está refletido no JSON;
4. **nenhum arquivo de dataset existe em `public/`** (a trava da P1);
5. `current.json` aponta para uma tag que existe em disco.

Isso **transforma o gate do pipeline em gate do site**, sem rede, dentro do N1 que já roda.

**Rollback:** `git revert` do commit de dado no submódulo + redeploy. O ponteiro `current.json`
voltando para a tag anterior é suficiente mesmo sem revert, porque as tags antigas continuam em disco.

**A correção de segurança, como item próprio (não dentro desta feature):** mover a autoridade do
papel de `user_metadata` para `app_metadata` (escrito só por service role) ou para uma tabela de
autorização, nos **quatro** pontos da cadeia da §4.4 — `src/middleware.ts:87`,
`src/lib/auth-check.ts:32`, `src/lib/auth-server.ts:19`, `src/lib/auth-supabase.ts:68` — e trocar
`src/lib/wealth-planning/db.ts:88` (`ensureAdvisor`) para **não** derivar `wp_advisors.role` do papel
autodeclarado. `scripts/sync-admin-users.ts` passa a escrever `app_metadata`. É **classe C/D** no
`site-ldc` (toca auth) e **não** é pré-requisito do MVP do Analytics — mas **é** pré-requisito de
publicar número `publicavel: false` ali (P2).

### 9.4 Como o `DESIGN.md` é respeitado

- Todo conteúdo dentro de `<div className="ferramenta ldc-work">` — herda escala fixa 15px, neutro
  tintado, `tabular-nums` e títulos Public Sans. É uma classe, e resolve a conformidade por construção.
- Importar `PageHeader`, `StatCard`, `ProgressBar`, `Donut` e `CHART_COLORS` de
  `src/app/admin/wealth-planning/components/charts.tsx`. **Nenhum hex novo** nos primitivos novos:
  `charts-macro.tsx` importa `CHART_COLORS` em vez de redeclarar — evitando o drift que a §3.2
  registra como risco.
- Usar `.ldc-sup-alerta` para a faixa de gate (⛔ especificação não congelada) e `.ldc-info` para o
  rodapé de versão. **Não** inventar um terceiro papel semântico.
- Respeitar os banidos: nada de gradiente, glass, card-em-card. KPI como bloco discreto —
  `StatCard` já é isso.
- Números em pt-BR com `toLocaleString("pt-BR")`, seguindo `brlShort`/`pctFmt`. Pontos percentuais
  com `<UnidadeBadge/>` em todo eixo (regra do relatório 2, §7.8).

**A decisão de design que falta, e precisa de assinatura do Edu — proposta:** o heatmap exige uma
**rampa divergente**, que o `DESIGN.md` não tem. A saída fácil (lime = positivo) é proibida pela
regra *"Sucesso não ganha verde"*. Proposta, construída só com tintas que já existem na casa:

- **neutro (zero):** `#f0f2f3` (o grid do `DESIGN.md`) — o meio da escala;
- **lado negativo:** arco do **alerta** `#c0584f`, 4 passos
  (clareando para `#f4e1df`/`#e8b4af` e escurecendo para `#a94d46`/`#8c3b34`);
- **lado positivo:** arco do **navy** `#262d3d`, 4 passos
  (`#dfe3e8` → `#9aa6b4` → `#5a6a7e` → `#262d3d`);
- **lime fica fora da escala**, reservado para o que `DESIGN.md` manda: ação e "no trilho" — o que
  no heatmap vira o **destaque do trimestre corrente**, não o sinal do número;
- célula suprimida (`n<5`): `#eceef0` (o track) com o texto "sem conclusão (n=4)" em slate.

Isto preserva as duas regras do `DESIGN.md`, usa zero tinta nova, e tem a propriedade que a rampa
azul↔vermelha do Python não tem: **é LDC**. Em contrapartida, navy↔alerta é um par divergente menos
convencional que azul↔vermelho e precisa de validação de contraste e de teste com o Comitê antes de
virar padrão. Entra como **adendo ao `DESIGN.md`**, com a medição de contraste ao lado, e o Python
(`apps/analysis/figuras/_comum.py`) **adota a mesma rampa** — senão a figura do PDF e a tela saem de
cores diferentes para o mesmo número, que é pior que qualquer das duas escolhas.

### 9.5 O que muda no `apps/web_export/` proposto pelo relatório de arquitetura

| Peça proposta | Destino |
|---|---|
| `apps/web_export/__main__.py`, `gate.py`, `unidades.py`, `views/*.py`, `schemas.py` | **mantém tudo**, classe C, única ponte. Muda só o default de `--destino`: a pasta `analytics-macro/` do app, em vez de `apps/portal/public/data/` |
| `packages/shared/contracts-web/` (JSON Schema → tipos TS) | **mantém**, e passa a alimentar o Zod de `src/lib/analytics-macro/` no site |
| `docs/contracts/CONTRACTS.md §10 — views da web` | **mantém** (espelho legível, nunca fonte) |
| **`apps/portal/`** (Vite, `src/app/`, `src/core/`, `src/modules/`, `registry.ts` com `RouteObject[]`) | **não se cria.** O shell é o `AdminLayout`; o roteamento é o App Router por pasta; o registry vira o array `grupos` do `AdminLayout.tsx` + um `modulos.ts` local declarando as views requeridas por tela |
| `src/core/charts/` from scratch (2,5 d) | **vira `components/charts-macro.tsx`**, 3 primitivos, importando `CHART_COLORS` (1,5–2 d) |
| `src/core/gate.tsx` | **mantém a ideia**, vira `components/gate.tsx` com as classes `.ldc-sup-alerta`/`.ldc-info` |
| `src/core/dataset.ts` | **mantém a ideia** (fixa a tag da sessão, valida o manifest, nunca mistura duas tags), mas busca por `fetch` nas duas API routes, não por asset estático |
| Auth: Vercel Authentication / Cloudflare Access | **não se cria.** Middleware + `checkAdminAuth()` existentes |
| `vercel.json` com headers de cache | **não se cria.** Cache vira header na `Response` da API route (`no-store` no ponteiro, `private, immutable` na view) |
| `ADR-008` | **mantém, com texto corrigido** (ver P3 na §8.5) |
| As 3 regras do registry (shell não conhece módulo; `dados` declarativo; gate por omissão) | **mantém as três.** A segunda e a terceira são as mais valiosas e independem de framework |

**Saldo:** de 13 dias de infra para **~3,5–4**; o Módulo 1 cai de 12 para **~9–10** (o que sobrevive
é o trabalho de view e de tela, que é o trabalho de verdade).

---

## 10. Correções a fazer nos dois relatórios anteriores

### 10.1 `docs/research/ldc-analytics-identidade.md` (v1)

| Afirmação | Vira |
|---|---|
| *"não existe identidade visual da LDC Capital neste repositório"* (a conclusão-mãe, usada adiante como absoluta) | **Falsa como premissa geral.** Existe em `site-ldc/site-ldc/DESIGN.md` + `src/app/globals.css`: paleta com hex, papéis semânticos, dois registros (brand/product), tipografia, escala, lista de banidos. |
| *"Não há logo, favicon, fonte própria, og-image nem manual de marca"* | **Falsa.** Logo em `public/images/LDC Capital - Logo Final_Aplicação Branca + Colorida.png`; ícones em `public/icons/` (incl. `ldc-180.png`); fontes locais em `src/fonts/` (Ivy Mode 3 pesos + Public Sans 21 variantes); `@vercel/og` instalado; `DESIGN.md` **é** o manual, derivado do "Manual da Marca LDC" que ele cita. |
| *"A marca aparece como string em dois arquivos"* | **Verdadeira para `site-eduardo`, irrelevante para a pergunta.** No app real a marca é token (`--color-ldc-*`), classe (`.ldc-*`) e constante (`CHART_COLORS`). |
| *"`docs/identidade-ldc.md` no próprio LDC Analytics… para ser a fonte que um futuro monorepo consumiria"* (recomendação 5) | **Cancelada.** Criar isso instituiria uma **segunda** fonte de verdade. A fonte é `site-ldc/site-ldc/DESIGN.md`; o que falta é **um adendo** a ele (a rampa divergente da §9.4). |
| *"Não há wrapper, nem tema, nem paleta de séries centralizada"* (sobre Recharts) | **Falsa para o app real.** `charts.tsx` é kit SVG próprio com 10 exports e `CHART_COLORS` centralizado, reusado por 11 arquivos. |
| *"esta paleta precisa ser refeita, não herdada"* (7 tons de dourado monocromáticos) | **Verdadeira e irrelevante** — era a paleta pessoal do Eduardo. A paleta LDC é navy/slate/lime/alerta + neutros tintados. |
| *"Não existe no repositório: `Button`, `Card`, `Modal`, `Tabs`, `Toast`, `Table`, `Sidebar`"* | **Falsa para o app real.** `src/components/ui/` com shadcn/ui (`components.json`), Radix (dialog, tabs, select, tooltip, accordion, alert-dialog, checkbox, label), `sonner` para toast, `AdminLayout` para sidebar. |
| *"Acessibilidade — praticamente inexistente. Nada a herdar"* | **Falsa para o app real.** Radix traz semântica e foco; `*:focus-visible` com outline lime em `globals.css`; alvo de clique de 44px em `.ldc-linha`; `viewportFit: cover` + safe-area. Há o que auditar, não o que criar do zero. |
| *"Não há massa crítica para monorepo… o reutilizável são ~400 linhas úteis"* | **Falsa como base de decisão.** O reutilizável é design system + auth + RLS + CI + deploy + kit de gráficos — ~6,5 dias-agente de infra já paga. |
| *"`AdminDashboardPage`… não importam guarda alguma"* e *"`src/App.tsx` não envolve nenhuma rota"* | **Verdadeiras, e exclusivas do `site-eduardo`.** O app real tem guarda de borda em `src/middleware.ts` + double-check no layout + 58 `checkAdminAuth()`. |
| *"`user_metadata.role` é gravável pelo próprio usuário via `updateUser`"* | **Verdadeira — e vale integralmente para o `site-ldc` também**, com um agravante que o v1 não poderia ter visto: aqui o papel autodeclarado é **persistido** em `public."User"` e em `wp_advisors.role`, que é a autoridade da RLS. Ver §4.4. **Este é o achado do v1 que sobrevive e se amplia.** |
| *"não herdar `is_admin()` sobre `user_metadata`… aplicar a guarda no roteador, não dentro de cada página"* | **Mantida e promovida.** A segunda metade **já está feita** no app real; a primeira **não**, e virou o item de §9.3. |
| *"O modelo de segurança desse repositório não aguenta hospedar dado de alocação. Descartada."* | **Verdadeira do `site-eduardo`; não transferível.** O modelo do `site-ldc` já hospeda carteira e plano de cliente real com RLS por advisor e teste de isolamento. Avaliação completa na §4. |
| *"projeto novo (Vite 6 + React 18 + TS 5 + Tailwind 3), repositório e deploy separados"* (plano mínimo) | **Revogada.** Ver §8.5 — módulo no app existente (Next 15 / React 19 / Tailwind 4). |
| *"`npm run lint` está quebrado hoje"*, *"dois `index.html` divergentes"*, *"`tsconfig.app.json` morto"*, *"paleta duplicada"* | **Verdadeiras e sem consequência** — são dívidas do `site-eduardo`, que deixa de ser origem de cópia. |

**Ação sugerida:** não apagar o v1. Inserir no topo dele um bloco de 5 linhas: fonte auditada =
`site-eduardo`, por que isso estava errado, qual é o repo certo, e link para este v2. O achado de
`user_metadata.role` é bom e merece sobreviver com crédito.

### 10.2 `docs/research/ldc-analytics-arquitetura.md`

| Afirmação / decisão | Vira |
|---|---|
| *"a stack LDC é Vite+React+TS+Tailwind+Recharts"* | **Falsa.** É **Next.js 15.5 (App Router) + React 19.1 + Tailwind 4 + Recharts 2.12 + TS 5**. A stack foi herdada do plano mínimo do v1, nunca verificada; "Next", "App Router", "React 19" e "Tailwind 4" não aparecem no documento. |
| *"um só modelo mental com o site institucional"* como argumento **pró** Vite | **Invertida.** É o argumento **contra**: o site institucional é Next 15, e Vite + `react-router` (`RouteObject[]`) é o modelo divergente. |
| *"Veredito: não adotar framework de data app como base"* | **Mantida** (Streamlit/Observable/Evidence seguem recusados) — mas a alternativa não é Vite; é **o Next que já existe**. |
| *"middleware.ts na raiz; com Vite via `vite-plugin-vercel`"* | **Obsoleta.** `src/middleware.ts` existe, é nativo, está em produção e já cobre `/admin/:path*`. |
| **Auth: Vercel Authentication no MVP** | **Revogada.** Middleware Supabase + `checkAdminAuth()`, identidade por pessoa, zero dia de esforço. |
| *"Supabase Auth: **não na v1** — arrastaria o banco que o ADR-007 veta"* | **Falsa.** Não arrasta nada: Supabase Auth + Postgres + RLS + `wp_advisors` já estão em produção no app. O ADR-007 veta **banco novo para o Analytics**, e (A) não cria nenhum. |
| *"avaliar mudar o host para Cloudflare Pages + Access… identidade por pessoa > senha coletiva"* | **Desnecessária.** O critério está certo e **já é atendido** sem trocar de host. |
| **`apps/portal/` novo (Vite + `src/app/` + `src/core/` + `src/modules/`)** | **Não se cria.** Ver árvore da §9.1. |
| *"`core/charts/` (timeline, heatmap, scatter de quadrantes, barras com erro) — 2,5 dias"* from scratch | **Reduzida.** `StatCard`, `PageHeader`, `ProgressBar`, `Donut`, `CHART_COLORS`, `brlShort`/`pctFmt` e o idioma `px/py` já existem. Restam 3 primitivos: **1,5–2 dias**. |
| *"wrappers Recharts com os defaults da LDC"* (defaults nunca definidos nem localizados) | **Resolvida.** Os defaults são `DESIGN.md` + `CHART_COLORS`. E o idioma da casa é **SVG próprio**, não wrapper de Recharts — embora Recharts siga disponível e em uso em 3 telas de `/admin`. |
| **Ausência total de seção de design tokens** | **Preenchida** pelas §2 e §9.4 deste documento. A delegação ao relatório (1) foi o ponto de falha em cadeia. |
| *"Scaffold `apps/portal`: Vite+TS+Tailwind, rotas, registry, shell/nav — 2,0 dias"* | **Reduzida a ~0,5 dia**: uma pasta, um Server Component fino, um grupo no array `grupos`. |
| *"Auth + domínio + `vercel.json` + deploy — 0,5 dia"* | **Zera.** Nada a configurar. |
| *"`apps/portal/public/data/<tag>/*.json"* como local do dataset | **Trocada, e é a correção técnica mais importante.** Num app Next que também é site público, `public/` **não passa pelo middleware** e seria lido por qualquer um com a URL. Vai para `analytics-macro/` na raiz do app, com `outputFileTracingIncludes`, servido por API route atrás de `checkAdminAuth()` — o padrão que `referencia-r2/` já prova em produção. |
| *"`vercel.json` (headers de cache)"* | **Vira header na `Response` da API route** (`no-store` no ponteiro, `private, immutable` na view). |
| *"MVP total ≈ 25 dias-agente (13 de infra + 12 do módulo)"* | **Revisada para ≈ 13–14 dias-agente** (~3,5–4 de infra + ~9–10 do Módulo 1). |
| *"Módulos seguintes, com a infra paga: 5 a 9 dias-agente cada"* | **Mantida**, e provavelmente otimista agora: `AdminLayout`, auth e kit já estarão pagos. |
| *"Caminho mais curto… publicar o HTML executado do caderno atrás do auth = 1 a 2 dias"* (v0) | **Mantida e recomendada como primeiro passo** — e ainda mais barata em (A): uma rota `/admin/analytics-macro/caderno`. |
| `apps/web_export/` em Python, classe C, única ponte, com o gate dentro | **Mantido integralmente.** Muda só o `--destino`. |
| Tag + `current.json` como ponteiro · hash no rodapé de toda tela · nunca duas tags na mesma tela · freeze local com CI validando sem rede · herança do gate (`publicavel`, `especificacao_congelada`, `n<5`, `n<8`) · `UnidadeBadge` em todo eixo · "o gate não é do front, é do exportador" · as 6 views nomeadas · as referências de UI (Verdad, Macrobond, ALFRED, BIS, Observable) · os 3 riscos (R1, R2, R7) · as 3 regras do registry | **Mantidos integralmente.** É a espinha dorsal do relatório e **não depende de qual front existe**. |
| *"ADR-008 antes da primeira linha de código"* | **Mantida, com texto corrigido** (P3, §8.5). |
| *"Auth protege o portal; o gate protege o número"* | **Mantida** — e vale mais em (A), onde o auth não custa nada e toda a atenção pode ir para o gate. |

---

## Apêndice — o que não foi encontrado

| Procurado | Resultado |
|---|---|
| `tailwind.config.*` no app | **não encontrado** (Tailwind 4, tokens em `globals.css`) |
| `docs/sdd/` no app | **não encontrado** (é `docs/specs/`, `docs/contracts/`, `docs/plans/`) |
| `playwright.config.*` | **não encontrado** (Playwright é dependência de runtime; sem suíte e2e versionada) |
| `.github/PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS` | **não encontrados** |
| `app_metadata` em `src/`, `packages/`, `supabase/` | **não encontrado** — zero ocorrências (é a raiz da §4.4) |
| `signUp` em `src/` | **não encontrado** — não há cadastro público pela aplicação |
| `estrategia-macro-ldc-dados/apps/web_export/` | **não encontrado** — proposto, não existe |
| `.cursor/` dentro do app | **não encontrado** (existe no wrapper `site-ldc/.cursor/`) |
| Regras de projeto em `.claude/` do app | **não encontradas** — só duas skills de criativo; as regras estão em `AGENTS.md`/`CLAUDE.md` |
| Tabela de autorização escrita só por service role | **não encontrada** — `wp_advisors.role` existe, mas é derivado de `user_metadata` (§4.4) |
| `ANONYMIZE_SALT` em `.env.example` | **não encontrado** (existe em `.env`; ausência em preview é deliberada) |
| "Allow new users to sign up" do projeto Supabase | **não verificável no código** — configuração de Dashboard |
