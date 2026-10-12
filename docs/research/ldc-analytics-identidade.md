# LDC Analytics — Inventário de identidade e stack do `site-eduardo`

**Fonte:** `C:\Users\edusp\Projetos_App_Desktop\site-eduardo` (somente leitura; nada alterado)
**Levantamento:** 2026-10-11 · **Último commit lido:** `7d09dd3 fix(deploy): destrava a publicacao do site, parada ha 280 dias`

> **Achado que condiciona todo o resto:** não existe identidade visual da LDC Capital neste repositório. A marca aparece como **string em dois arquivos** — `src/config/identidade.ts:26` (`ESTRUTURA_NOME = 'LDC Capital'`) e `src/lib/leads.ts:44` (texto de privacidade). Não há logo, favicon, fonte própria, og-image nem manual de marca. A identidade implementada é **pessoal do Eduardo Pires** ("premium wealth advisor" + "ferrari-inspired"). "Parecer produto da LDC desde o primeiro dia" **não se resolve por cópia** — a marca LDC ainda precisa ser definida.

---

## 1. Stack real

### 1.1 Versões (`package.json`)

| Camada | Pacote | Versão |
|---|---|---|
| UI | `react` / `react-dom` | `^18.2.0` |
| Build | `vite` / `@vitejs/plugin-react` | `^6.2.2` / `^4.2.1` |
| Linguagem | `typescript` | `^5.2.2` |
| CSS | `tailwindcss` (+ `postcss ^8.4.33`, `autoprefixer ^10.4.17`) | `^3.4.1` |
| Gráficos | `recharts` | `^3.5.1` |
| Rotas | `react-router-dom` | `^6.22.0` |
| Animação | `framer-motion` | `^11.0.3` |
| Dados/auth | `@supabase/supabase-js` | `^2.83.0` |
| Ícones | `lucide-react` | `^0.330.0` |
| Classes | `clsx ^2.1.1` + `tailwind-merge ^3.0.2` | |
| SEO | `react-helmet-async` | `^2.0.5` |
| Datas | `date-fns ^4.1.0`, `react-datepicker ^8.10.0` | |
| Lint | `eslint ^8.55.0`, `@typescript-eslint/* ^6.14.0`, `eslint-plugin-react-hooks ^4.6.0`, `eslint-plugin-react-refresh ^0.4.5` | |

Peso morto que **não** vai para o LDC Analytics: `contentful` + 3 `@contentful/rich-text-*`, `openai ^6.9.1`, `tesseract.js`, `pdfjs-dist`, `pdf-parse`, `@napi-rs/canvas`, `jspdf`, `xlsx`, `express ^5.1.0`, `cors`, `axios`, `@formspree/react`, `react-intersection-observer`.

### 1.2 Scripts

`dev` → vite (porta 3000, `open:true`) · `dev:api` → `node server-api.js` (Express 3001) · `dev:all` → concurrently (⚠ `concurrently` não está nas devDeps) · `prebuild` → `node scripts/verificar-identidade.mjs` (§3) · `build` → `tsc && vite build` · `lint` → `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0` · `preview` → `vite preview`.

- **`npm run lint` está quebrado hoje:** `eslint.config.js` (flat config) importa `@eslint/js`, `globals` e `typescript-eslint`; os dois primeiros existem como transitivos em `node_modules`, mas **`typescript-eslint` não está instalado nem declarado**. Copiar a intenção, não o arquivo.
- **`tsconfig.app.json` é configuração morta:** `tsconfig.json` referencia só `tsconfig.node.json`. O build real roda com `noUnusedLocals/Parameters: false`, enquanto `tsconfig.app.json` diz `true`. Herdar o `tsconfig.app.json` como se fosse o real — é a versão rigorosa.

### 1.3 `vite.config.ts`

`plugins: [react()]`, `optimizeDeps.exclude: ['lucide-react']`, server porta 3000 `strictPort:false`. Proxy `/api` → `http://localhost:3001` com `timeout: 120000` (2 min, por causa da OpenAI) e handlers de `error`/`proxyReq`/`proxyRes` que imprimem instrução de recuperação ("Execute `npm run dev:api`") e devolvem 503 JSON em `ECONNREFUSED` — **padrão copiável e que vale copiar**. Sem aliases de path; todos os imports são relativos.

### 1.4 `vercel.json`

**Só rewrites.** Não há `headers`, `functions`, `regions`, `cleanUrls` nem `crons`. Seis rewrites de compatibilidade mandam URLs antigas (`/api/buscar-cotacao-dolar`, `/api/buscar-cdi-referencia`, `/api/create-cliente`, `/api/delete-cliente`, `/api/send-invite`, `/api/verificar-cliente-id`) para as funções agregadoras com `?op=` (§5.5), e `"/((?!api/).*)" → "/index.html"` fecha a SPA. **Não há `@vercel/analytics` nem `@vercel/speed-insights`** em nenhum lugar.

---

## 2. Identidade de marca extraída do código

### 2.1 Tokens de cor (`tailwind.config.js`, `theme.extend.colors`)

| Token | Hex | Nota |
|---|---|---|
| `premium-black` | `#0a0a0a` | preto de títulos |
| `premium-white` | `#fafafa` | |
| `premium-gold` | `#c5a05e` | **cor de destaque única do produto** |
| `premium-gold-dark` / `premium-gold-light` | `#a88b4d` / `#d4b574` | |
| `ferrari-black` / `ferrari-white` | `#000000` / `#ffffff` | botões primários |
| `ferrari-dark-gray` / `ferrari-medium-gray` | `#1a1a1a` / `#2a2a2a` | `medium-gray` = cor de corpo de texto |
| `ferrari-light-gray` | `#8a8a8a` | |
| `ferrari-bg-gray` / `ferrari-bg-dark` | `#f8f9fa` / `#0f0f0f` | fundo de seção |
| `ferrari-red` / `ferrari-red-dark` | `#dc2626` / `#b91c1c` | |

As escalas `primary`, `gray` e `neutral` (50…950) são **idênticas entre si** e são a paleta cinza do Google Material (`#f8f9fa … #202124`, `950: #000000`). Ou seja, **`gray-*` do Tailwind está sobrescrito**: `text-gray-700` aqui é `#5f6368`. Copiar `tailwind.config.js` sem notar isso muda o cinza de todo o portal. Os mesmos valores estão duplicados como variáveis CSS em `src/index.css:10-28` — duas fontes de verdade.

### 2.2 Tipografia

- Origem: **Google Fonts via `@import` no CSS** (`src/index.css:2-3`) — `Playfair Display` (300–900) e `Inter` (300–900). **Nenhum arquivo de fonte em `public/`** (busca por `*.woff*`/`*.ttf`/`*.otf`: zero). `@import` é a forma mais lenta; migrar para `<link rel=preconnect>` + `<link>`.
- Famílias: `font-sans`/`font-body` → Inter; `font-serif`/`font-heading` → Playfair Display, Georgia, serif.
- Escala (`src/index.css`, `@layer base`): `h1` `text-6xl md:7xl lg:8xl` weight 300 tracking `-0.04em`; `h2` `4xl/5xl/6xl` w400; `h3` `3xl/4xl/5xl`; `h4` `2xl/3xl` w500. `body` com `font-feature-settings:'cv11','ss01'` e `letter-spacing:-0.01em`.
- **Assinatura visual recorrente**, repetida à mão em dezenas de arquivos: `text-xs uppercase tracking-[0.15em] font-medium` para labels e itens de menu (`portal/PortalNavbar.tsx:74`, `portal/DashboardCard.tsx:38`, `portal/TabelaResultadosMensais.tsx:36`). É o elemento mais "de marca" do portal e o mais fácil de herdar — vale virar token.

### 2.3 Espaçamento, raios, sombras, breakpoints, dark mode

- `spacing` estendido: `18:4.5rem`, `88:22rem`, `128:32rem`, `160:40rem`, `192:48rem`. `maxWidth`: `8xl:88rem`, `9xl:96rem`. `container`: `center:true`, `padding:1rem`. `letterSpacing`: `tighter -0.05em` … `wider 0.05em`.
- **Raios: não customizados** — o design é de cantos retos de propósito (`.ferrari-card`, `.ferrari-btn` não usam `rounded-*`).
- Sombras: não em Tailwind, só como variáveis CSS em `:root` — `--shadow-subtle: 0 1px 3px rgba(0,0,0,.05)`, `--shadow-soft: 0 4px 12px rgba(0,0,0,.08)`, `--shadow-medium: 0 8px 24px rgba(0,0,0,.12)`, expostas como `.ferrari-shadow-soft/-medium`. Também `--spacing-xs .5rem` … `--spacing-2xl 6rem`.
- **Breakpoints: padrão do Tailwind.** O código usa quase só `md:` e `lg:`.
- **Dark mode: `darkMode: 'class'` ligado, mas não usado.** `src/hooks/useTheme.ts` tem default `'dark'`; `src/components/ThemeToggle.tsx` tem default light + `prefers-color-scheme` — **dois hooks divergentes**, e nenhum é montado em `src/App.tsx`. Variantes `dark:` só no reset (`src/index.css:50`). Herdar a infra, não o estado.
- `safelist` grande (`tailwind.config.js:5-27`, cores `blue/green/amber/purple/red` + `w-*/h-*`) — sintoma de classes montadas por string. Não copiar; é dívida.

### 2.4 Mini design system em CSS

`src/index.css`, `@layer components`: `.ferrari-btn` + `-primary` (preto que inverte no hover) `-secondary` `-red`, `.ferrari-card`, `.ferrari-card-hover`, `.ferrari-input`, `.ferrari-section`, `.ferrari-container` (`max-w-7xl mx-auto px-6 lg:px-8`), `.ferrari-divider`, `.ferrari-badge`, `.ferrari-logo-text`, `.ferrari-heading-xl/lg/md`, `.ferrari-text-lg/base`, `.ferrari-fade-in`, `.ferrari-slide-up`. `@layer utilities`: `.ferrari-text-gradient`, `.ferrari-bg-pattern`, `.ferrari-shadow-*`.

**Conflito:** um plugin inline em `tailwind.config.js:200-233` **redefine** `.ferrari-text-gradient`, `.ferrari-card`, `.ferrari-btn-primary` e `.ferrari-btn-secondary` com valores *diferentes* (ex. card com `backdrop-filter: blur(10px)`). Duas definições concorrentes para as mesmas classes; ao copiar, escolher uma. Animações `animate-fade-in` (.8s), `animate-slide-up` (.8s, `translateY(30px)`), `animate-scale-in` (.6s) também estão duplicadas como `@keyframes ferrariFadeIn/ferrariSlideUp`.

### 2.5 Logos e assets de marca

| Arquivo | Nota |
|---|---|
| `public/icon-cvm.svg`, `public/icon-data.svg`, `public/icon-security.svg` | SVG `viewBox 0 0 24 24`, stroke `#F59E0B` (amber — **fora da paleta**) |
| `public/freepik__*.jpeg` (9 arquivos, 130–215 KB) | retratos gerados por IA; não são marca |
| `public/imagens-extratos-exemplo/` | 14 prints de extrato XP/BTG/Avenue + 1 CSV (dados de teste) |

- **Logo: não encontrado.** O "logo" é texto: `Eduardo Pires` em `font-heading` (`src/components/portal/PortalNavbar.tsx:66-72`) e a classe `.ferrari-logo-text`.
- **Favicon: não encontrado.** `index.html:5` aponta `/vite.svg` (inexistente); `src/index.html:5` aponta `/favicon.svg` (também inexistente).
- **og-image: não encontrada.** `src/components/SEO.tsx:27` usa `/images/og-image.jpg` e `logo: /images/logo.png`; `public/images/` **não existe**.
- Há **dois `index.html` divergentes**: o da raiz (usado pelo Vite, título "Eduardo Pires | Advisor", fonte Google comentada) e `src/index.html` órfão, com `theme-color #2B7BBF` e **Montserrat + Inter** — vestígio de identidade anterior.

### 2.6 Documento de identidade

**Não encontrado.** `documentos_base/` tem só governança SDD: `SPEC.md` (44 KB), `ACCEPTANCE.md`, `DECISIONS_TBD.md`, `WORKFLOW.md`, `CHANGELOG.md`, `README_USO_PACOTE.txt`. Grep por `logo|paleta|hex|tom de voz|identidade visual` em `documentos_base/*.md` e `docs/*.md`: nada. `docs/legacy/` tem 50+ how-to/debug e **não define comportamento** (aviso em `README.md`).

O que existe de **tom de voz** está em código, e é bom: `src/config/identidade.ts` (comentário de 20 linhas sobre por que não se publica registro inventado); `src/lib/leads.ts:28-47` com `VERSAO_CONSENTIMENTO = '2026-09-05.v2'` e os textos `TEXTO_CONSENTIMENTO_AGENDAMENTO`, `TEXTO_CONSENTIMENTO_CONTEUDO`, `TEXTO_PRIVACIDADE` — o comentário registra que a v1 prometia "não serão compartilhados com terceiros", promessa que o fluxo não sustentava, e separa as finalidades. `.cursor/rules/index.mdc` manda escrever em PT-BR e não inventar funcionalidades.

---

## 3. O que `scripts/verificar-identidade.mjs` valida (regra a regra)

Roda no `prebuild`, antes de todo `npm run build`. 90 linhas, sem dependências. Na ordem:

1. **Lê `src/config/identidade.ts`** e extrai por regex `/export const CVM_REGISTRO\s*:\s*string\s*=\s*['"]([^'"]*)['"]/`.
2. **Constante ausente ou renomeada → `exit 1` sempre** (inclusive local/preview): "se a constante foi renomeada, atualize o script, senão a trava de publicação passa a não travar nada". O guardião falha quando perde a própria âncora.
3. **Valor real preenchido → `exit 0` imediato.** Nada mais é checado.
4. **Valor é o sentinela → varre `src/` recursivamente** (`.ts`/`.tsx`, excluindo o próprio `identidade.ts`) por `\bCVM_REGISTRO\b`. Os arquivos que casam são os "consumidores", capazes de exibir o número.
5. **Sentinela + zero consumidores → `exit 0`.** Decisão documentada: a landing `/diagnostico` diz "consultor de investimentos independente" sem número, então o sentinela não chega ao público.
6. **Sentinela + algum consumidor:** em produção (`VERCEL_ENV === 'production'` **ou** `PUBLICAR_PRODUCAO === '1'`) → `exit 1`, imprimindo os arquivos culpados e as duas saídas (preencher o número real ou remover a exibição). Em local/preview → só aviso em `stderr`, build liberado.

Complemento em runtime: `identidadePendente()` e `exigirIdentidadePublicavel()` (esta **lança `Error`**) em `src/config/identidade.ts`. O próprio script avisa: "isto é uma verificação de software. Não é validação regulatória".

**Padrão a replicar (vale mais que o script):** verificar **uso**, não valor; falhar mais forte em produção que em preview; falhar quando a âncora desaparece. Para o LDC Analytics, o análogo é uma trava de prebuild que recuse o build se credencial/segredo estiver com placeholder **e** for consumido por código que vai ao browser, ou se um `VITE_*` carregar algo que não deveria vazar.

---

## 4. Componentes reaproveitáveis para um portal analítico

Convenção: `export default function`, props em `interface <Nome>Props`, arquivo `PascalCase.tsx`.

| Componente | Caminho | Props principais | Dependências | Copiável isolado? |
|---|---|---|---|---|
| **DashboardCard** (KPI) | `src/components/portal/DashboardCard.tsx` (89 l.) | `title`, `value`, `subtitle?`, `icon?: LucideIcon`, `trend?{value,isPositive}`, `cdiComparison?{percentualCDI,cdiValue}`, `className?` | framer-motion, lucide, `.ferrari-card`, tokens `premium-*` | **Sim** — melhor candidato |
| **TabelaResultadosMensais** | `src/components/portal/TabelaResultadosMensais.tsx` (131 l.) | `dados: ResultadoMensal[]`, `maxItems=12`, `mostrarCDI=true` | só `lib/portal/formatters` | **Sim.** Já traz empty state, zebra e verde/vermelho por sinal |
| **GraficoCarteiraConsolidada** | `src/components/portal/GraficoCarteiraConsolidada.tsx` (83 l.) | `data:{competencia,valor,retorno?}[]`, `height=300` | recharts, `formatters` | **Sim** (§7) |
| **GraficoWealthPlanning** | `src/components/portal/GraficoWealthPlanning.tsx` (113 l.) | `data: WealthPlanningData`, `height=300` | recharts + `lib/portal/calculations` | Sim, mas carrega regra de projeção; usar como referência de tooltip/eixo |
| **PortalNavbar** (header+nav) | `src/components/portal/PortalNavbar.tsx` (170 l.) | nenhuma (lê `useAuth`/`useCliente`) | **react-router + Supabase via hooks** | Parcial — visual ótimo (navbar fixa, `isScrolled`, menu mobile `AnimatePresence`, spacer `h-20 lg:h-24`); arrancar os hooks |
| **AdminNavbar** | `src/components/admin/AdminNavbar.tsx` (97 l.) | nenhuma; `navItems` hardcoded no módulo | **importa `lib/supabase` direto** p/ `signOut` | Parcial — layout mais próximo de ferramenta interna (header sticky, ativo `bg-blue-50 text-blue-700`); logout vira callback |
| **LoadingSpinner** | `src/components/LoadingSpinner.tsx` (13 l.) | nenhuma | lucide | Sim, mas **tem bug**: usa `text-volvo-accent`, token inexistente em `tailwind.config.js` — spinner sem cor |
| **ProtectedRoute** | `src/components/ProtectedRoute.tsx` (64 l.) | `children`, `allowedRoles?: ('ADMIN'\|'CLIENTE')[]` | **Supabase Auth** (`lib/auth`) | Padrão sim, implementação não (§6) |
| **AdminRoute** | `src/components/AdminRoute.tsx` (53 l.) | `children` | **Supabase Auth** | idem |
| **SEO** | `src/components/SEO.tsx` (195 l.) | `title`, `description`, `ogImage`, `structuredData`, +12 | `react-helmet-async` | Não — hardcoda nome, telefone e endereço do Eduardo (`:48-58`) |
| **ServiceCard / AnalysisCard / StatsGrid** | `src/components/` | cards de marketing | framer-motion | Não — de landing; `StatsGrid` tem números hardcoded |
| **ThemeToggle** | `src/components/ThemeToggle.tsx` (76 l.) | nenhuma | framer-motion, lucide | Sim, mas duplica `useTheme.ts` e não está montado |

**Dependências indesejadas, mapeadas:** **Contentful** — zero componentes importam; só `src/lib/contentful.ts` (243 l.). **OpenAI** — só `src/lib/bloomberg/pdfProcessor.ts` e `api/process-extrato.js`; nenhuma UI depende. **Supabase em `src/components/`** — apenas `admin/AdminNavbar.tsx` e `admin/ImageUpload.tsx`. Os componentes de extrato (`admin/ExtratoBatchUploader.tsx` 546 l., `admin/ExtratoCompetenciaGroup.tsx`, `pages/admin/portal/components/ExtratoUploader.tsx` 582 l., `ExtratoValidator.tsx` 485 l.) são o oposto — grudados em OpenAI + Supabase + domínio de extrato. **Não usar.**

**Não existe no repositório** (precisa ser criado): `Button`, `Card`, `Modal`/`Dialog`, `Tabs`, `Toast`, `EmptyState`, `Table` genérica, `Sidebar`. Botões são a classe `.ferrari-btn-*`; "modais" são `fixed inset-0` escrito à mão em 5 arquivos (`AdminPosts.tsx`, `AdminClientesPage.tsx`, `ExtratoUploader.tsx`, `ExtratoValidator.tsx`, `FormularioManualExtrato.tsx`) **sem `role="dialog"`/`aria-modal`, sem foco preso, sem fechar no Esc**; "tabs" são `useState` + condicional (`AdminClienteDetailPage.tsx`); feedback é `alert()`/texto inline; empty state é `<td>Nenhum dado disponível</td>`.

---

## 5. Padrões de código

**5.1 Estrutura e nomes** — documentados em `.cursor/rules/frontend-react-vite.mdc` e seguidos: `src/{components,pages,hooks,lib,types,config,utils}` com `components/admin|portal/` e `pages/admin|portal/`. Componentes PascalCase, hooks `useX.ts`, utilitários camelCase, constantes `SCREAMING_SNAKE`, 1 arquivo = 1 rota. Nomes de domínio em **português** (`clientes`, `competencia`, `reunioes`, `carteira`) — convenção consistente, vale manter.

**5.2 Roteamento** — `react-router-dom` v6, `BrowserRouter` em `src/App.tsx`, **todas as 28 páginas em `lazy()` sob um único `<Suspense>`** com `LoadingSpinner`. Layout invertido: rotas de portal/admin primeiro e nuas; o catch-all `path="*"` renderiza `<Navbar />` + `<Routes>` internas do site público.

**5.3 Estado e data fetching** — sem Redux/Zustand/TanStack Query/Context; `.cursor/rules` **proíbe** Context API para estado global. O padrão é um hook por entidade, sempre `{ data, loading, error, refetch }` com `useState` + `useEffect` + `try/catch/finally` e query direta `supabase.from(...)`: `useCliente.ts` (62 l.), `useCarteira.ts` (282 l., com derivados `getCompetenciasDisponiveis`, `getResumoPorConta`, `getCDIPorCompetencia`, `getConsolidadoPorCompetencia`), `useWealthPlanning.ts`, `useReunioes.ts`, `useAuth.ts` (assina `onAuthStateChange`). API própria via `fetch('/api/...')` relativo. Derivados em `useMemo` na página (`PortalCarteiraPage.tsx:41-104`). **Sem cache, revalidação ou deduplicação** — cada montagem refaz as queries.

**5.4 `clsx`/`tailwind-merge`** — `src/lib/utils.ts` define o `cn()` canônico (`twMerge(clsx(inputs))`) e **nenhum arquivo o importa** (zero usos de `cn(` fora da definição). Classes condicionais são template strings com ternário. Herdar o `cn()` e usar de verdade.

**5.5 API serverless (padrão Vercel)** — `api/mercado.js` e `api/clientes.js` são **portas únicas**: um `handler(req,res)` que escolhe a implementação por um mapa `OPERACOES` indexado por `req.query.op || req.body.op`, devolvendo 400 com `{error, recebido, aceitas}` para `op` desconhecida; implementações uma por arquivo em `servicos-api/**`. O comentário no topo explica o porquê: cada arquivo em `api/` vira uma função, o plano limita quantas cabem, e o deploy falha na publicação "com o build inteiro passando antes, o que torna a causa difícil de enxergar". `server-api.js` (18 KB) é o equivalente Express para dev. **Item mais valioso do repo** se o LDC Analytics for para a Vercel.

**5.6 Acessibilidade** — praticamente inexistente. `aria-*` em **5 arquivos** de ~140 (`FAQ.tsx`, `FloatingCTA.tsx`, `LeadCapture.tsx`, `ThemeToggle.tsx`, `ExtratoUploader.tsx`), sempre `aria-label` em botão de ícone. Sem `role="dialog"`, gestão de foco, `aria-live` ou skip link. **Nada a herdar; é lacuna a corrigir.**

**5.7 Qualidade observada** — `strict: true`. Comentários de alto valor explicando *por quê* (ex. `PortalCarteiraPage.tsx:95-96`: "o TypeScript não propaga o narrowing através da variável"). Convivem com `catch (err: any)`, `CustomTooltip = ({active,payload}: any)`, `console.log` de debug em `src/lib/supabase.ts:9-16` e — pior — `src/lib/supabase.ts:63-69`, que **cria um client com URL e JWT placeholder hardcoded** quando o env falta, em vez de falhar. Úteis e copiáveis: `src/lib/logging/logger.ts` (92 l., singleton com buffer de 1000), `src/lib/utils/errorHandler.ts` (16 l., `getErrorMessage(unknown): string`), `src/lib/monitoring/performance.ts` (54 l.).

---

## 6. Autenticação e acesso (hoje)

**É Supabase Auth com RLS real — e com um furo conhecido, já corrigido só para leads.**

- **Client** (`src/lib/supabase.ts`): `createClient<Database>` com `flowType:'pkce'`, `persistSession`, `autoRefreshToken`, `detectSessionInUrl`, header `x-client-info: 'eduardo-pires-portal'`.
- **Login:** `supabase.auth.signInWithPassword` (`PortalLoginPage.tsx`, `AdminLoginPage.tsx`).
- **Papéis:** `UserRole = 'ADMIN' | 'CLIENTE'` em `src/lib/auth.ts`, lidos de `session.user.user_metadata.role`; `cliente_id` também em `user_metadata`.
- **Frontend:** `useAuth()` → `{user, role, clienteId, loading, isAuthenticated, isAdmin, isClient, logout}`; guardas `ProtectedRoute` (com `allowedRoles`) e `AdminRoute`.
- **Como as guardas são aplicadas — detalhe crítico:** `src/App.tsx` **não envolve nenhuma rota**. Cada página se auto-envolve no `return` (`PortalDashboardPage.tsx:258`, `AdminClientesPage.tsx:517`, `AdminParametrosEconomicosPage.tsx:476`). Resultado: **`AdminDashboardPage`, `AdminAnalysisFormPage`, `AdminPDFsPage` e `AdminExtratosPage` não importam guarda alguma** — carregam para qualquer um que digite a URL e só falham quando a RLS nega a query.
- **RLS:** habilitada em 8 tabelas (`supabase/migrations/001_portal_cliente.sql:247-254`: `clientes`, `contas`, `posicoes_mensais`, `consolidado_mensal`, `reunioes`, `tarefas`, `wealth_planning`, `eventos_calendario`), com ~16 policies no padrão `USING (cliente_id = get_cliente_id_from_auth() OR is_admin())` para leitura do cliente e `FOR ALL USING (is_admin())` para escrita. Mais policies em `003`, `005`, `008`, `013`, `014`. (As migrations `010` e `011` não existem — lacuna na numeração.)
- **Helpers SQL** (`001:195-240`, `SECURITY DEFINER`): `get_cliente_id_from_auth()` lê `auth.jwt() -> 'user_metadata' ->> 'cliente_id'` com fallback para a raiz do JWT; `is_admin()` compara `UPPER(user_metadata.role) = 'ADMIN'`. `006_fix_function_search_path.sql` corrige o `search_path` dessas funções.
- **O furo, e a lição mais importante do repositório.** `supabase/migrations/014_leads_seguranca_supressao.sql:28-35` registra: *"A autorização **NÃO pode vir de `user_metadata.role`**: esse campo é gravável pelo próprio usuário via `updateUser`. Precisa ser uma tabela que só o `service_role` escreve."* A correção criou `operadores_aquisicao` (PK `user_id` → `auth.users`, **sem policy de escrita** — só o `service_role` insere) e `eh_operador_aquisicao()` `SECURITY DEFINER STABLE`, usada nas policies de `leads`. **O portal do cliente continua no modelo antigo:** um cliente autenticado pode, em teoria, se promover a ADMIN via `supabase.auth.updateUser`.
- **Operações sensíveis** (criar usuário, deletar cliente, convite) usam `service_role_key` só no backend, em `servicos-api/clientes/*`. `SPEC.md:47-58` proíbe expor `service_role_key` no frontend e desabilitar RLS em produção.

**Insumo para o LDC Analytics:** não herdar `is_admin()` sobre `user_metadata`. Herdar o modelo da `014` — **tabela de autorização escrita apenas pelo `service_role` + função `SECURITY DEFINER`** — e aplicar a guarda no roteador, não dentro de cada página.

---

## 7. Gráficos (Recharts)

**Não há wrapper, nem tema, nem paleta de séries centralizada.** Recharts aparece em 3 lugares, cada um repetindo as mesmas decisões: `src/components/portal/GraficoCarteiraConsolidada.tsx` (`LineChart`), `src/components/portal/GraficoWealthPlanning.tsx` (`LineChart` + `ReferenceLine`) e `src/pages/portal/PortalCarteiraPage.tsx` (`PieChart`/`Pie`/`Cell` + `BarChart`/`Bar`, inline na página).

Convenções repetidas, que valem virar um wrapper:
- Série principal: `stroke="#c5a05e"` (`premium-gold`), `strokeWidth={2}`, `dot={{fill:'#c5a05e',r:4}}`, `activeDot={{r:6}}`, `type="monotone"`.
- `<CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />`; eixos `stroke="#6b7280"`, `fontSize={12}`, `tick={{fill:'#6b7280'}}`. **Esses dois cinzas são do Tailwind padrão, não dos tokens do projeto** (que foram sobrescritos) — inconsistência real.
- `tickFormatter` de dinheiro **duplicado literalmente** nos dois gráficos de linha (`>=1e6 → R$ X.XM`, `>=1e3 → R$ Xk`, senão `R$ X`); `margin={{top:5,right:30,left:20,bottom:5}}` em todos.
- `CustomTooltip` escrito à mão em cada arquivo (`bg-white border border-gray-200 p-3 shadow-lg`, título `text-sm font-semibold text-gray-700`, valores com `entry.color` + `formatCurrency`), tipado como `any`.
- **Paleta de séries categóricas** (`PortalCarteiraPage.tsx:105`), a única que existe: `['#c5a05e','#a88b4d','#d4b574','#8b7355','#6b5d4d','#9c8c6c','#bfa86f']` — 7 tons de dourado/marrom, **monocromáticos**. Num pie de alocação por instituição, categorias adjacentes ficam quase indistinguíveis e sem contraste suficiente para quem não distingue cores. Como alocação é o dado central do LDC Analytics, **esta paleta precisa ser refeita, não herdada**.
- Comparativo CDI: `Bar dataKey="retorno" fill="#c5a05e"` vs `Bar dataKey="cdi" fill="#9ca3af"` — a convenção "nosso número em ouro, benchmark em cinza" **é boa e vale herdar**.
- Semântica de desempenho consistente entre card e tabela: positivo `text-green-600`, negativo `text-red-600`, abaixo do CDI `text-orange-500/700`, ≥100% do CDI `bg-green-100 text-green-700` + `✓` (`DashboardCard.tsx:70-84`, `TabelaResultadosMensais.tsx:86-121`).

**Herdar de fato:** `src/lib/portal/formatters.ts` (160 l., zero dependências) — `formatCurrency` (BRL), `formatCurrencyUSD`, `formatPercent`, `formatDate`, `formatDateTime`, `formatCompetencia` ("Janeiro de 2025"), `formatCompetenciaShort` ("01/2025"), `formatCompetenciaMMYY` ("jan/25"), `getPerfilRiscoLabel`, `getTipoReuniaoLabel`, `getStatusTarefaLabel`. Tudo `Intl.*` em `pt-BR` com tratamento de `null|undefined`. **Copiar inteiro.**

---

## 8. Veredito de reaproveitamento

| Artefato | Veredito | Por quê |
|---|---|---|
| `src/lib/portal/formatters.ts` | **copiar** | 160 linhas sem dependências; resolve BRL/USD/%/competência em pt-BR |
| `src/lib/utils.ts` (`cn`) | **copiar** | 5 linhas, padrão certo — e lá passa a ser usado |
| `src/lib/utils/errorHandler.ts` | **copiar** | `getErrorMessage(unknown)` elimina `catch (e: any)` |
| `logger.ts` + `performance.ts` | **copiar** | Pequenos, sem dependências, úteis num portal interno |
| Tokens `premium-*` (5 hex) | **copiar** | Única assinatura cromática existente; ponto de partida |
| `uppercase tracking-[0.15em]` | **copiar** | Elemento de marca mais reconhecível; virar token em vez de repetir |
| `portal/DashboardCard.tsx` | **copiar** | KPI card pronto, props limpas, só pede `.ferrari-card` |
| `portal/TabelaResultadosMensais.tsx` | **copiar** | Tabela + empty state + semântica de sinal, sem acoplamento |
| `portal/GraficoCarteiraConsolidada.tsx` | **copiar e refatorar** | Base para extrair o wrapper Recharts que não existe |
| Padrão `api/*.js` com mapa `OPERACOES` | **copiar** | Contorna o limite de funções da Vercel; decisão já paga e documentada |
| Proxy `/api` do `vite.config.ts` | **copiar** | Erros acionáveis em dev valem o copy-paste |
| Modelo de autorização da migration `014` | **copiar** | Tabela escrita só pelo `service_role` + `SECURITY DEFINER`: o jeito certo |
| `scripts/verificar-identidade.mjs` | **referenciar** | O padrão vale (valida uso, não valor; mais duro em produção); a regra CVM não se aplica |
| `.cursor/rules/frontend-react-vite.mdc` | **referenciar** | Convenções de nome/hook/tipagem já pensadas; adaptar |
| `SPEC.md` §4.4 (UX do portal) | **referenciar** | "quanto tenho / como foi o mês / o que ficou combinado" é boa disciplina de dashboard |
| `src/index.css` (`@layer components`) | **referenciar** | Vale ler como design system; copiar traz a duplicação com o plugin do Tailwind |
| `PortalNavbar` / `AdminNavbar` | **recriar** | Layout bom; a cola com Supabase e os `navItems` hardcoded não |
| `ProtectedRoute` / `AdminRoute` | **recriar** | Ideia certa, mas `is_admin()` sobre `user_metadata` é o furo da `014` |
| Paleta de séries (7 dourados) | **recriar** | Monocromática demais para alocação; refazer com contraste e acessibilidade |
| `tailwind.config.js` inteiro | **recriar** | Traz `safelist` inútil, `gray-*` sobrescrito e plugin que conflita com o CSS |
| Modal / Tabs / Toast / Sidebar / Button | **recriar** | Não existem como componentes; só HTML inline sem acessibilidade |
| `LoadingSpinner.tsx` | **recriar** | 13 linhas, e uma usa `text-volvo-accent`, token inexistente |
| `SEO.tsx` | **não usar** | 195 linhas com telefone, endereço e schema.org do Eduardo; portal interno não indexa |
| `src/lib/contentful.ts` + 4 pacotes | **não usar** | CMS de blog, irrelevante |
| `pdfProcessor.ts`, `api/process-*`, componentes de extrato | **não usar** | OpenAI + domínio de extrato; ~2.500 linhas de acoplamento |
| `src/lib/supabase.ts` como está | **não usar** | Cria client com URL/JWT placeholder hardcoded quando falta env, em vez de falhar |
| `src/index.html`, `docs/legacy/`, `public/freepik__*` | **não usar** | Órfãos e resquícios; `docs/legacy` avisa que não define comportamento |
| Logo / favicon / og-image / fontes locais | **não encontrado** | Nada disso existe; precisa ser criado |
| Documento de identidade de marca LDC | **não encontrado** | `documentos_base/` é só governança SDD |

### Recomendação: **(b) copiar os tokens e 5-8 componentes para um projeto novo**

1. **O site-eduardo é público; o LDC Analytics tem dado sensível de alocação.** A opção (c) põe os dois no mesmo deploy, domínio, bundle e `vercel.json`. Pior: a proteção de rota ali é feita dentro de cada página, e já há 4 páginas admin sem guarda nenhuma (§6). O modelo de segurança desse repositório não aguenta hospedar dado de alocação. Descartada.
2. **Não há massa crítica para monorepo.** A opção (a) presume biblioteca comum; o reutilizável são ~400 linhas úteis (`formatters.ts`, `cn()`, `errorHandler`, 5 hex, 3 componentes). Um pacote compartilhado custa build, versionamento e release para distribuir isso — e amarraria o portal ao `tailwind.config.js` do site, que precisa ser reescrito de todo modo. Monorepo passa a fazer sentido só quando a identidade LDC existir e servir 3+ produtos.
3. **A dívida vem junto se a cópia for em bloco:** lint quebrado, `tsconfig.app.json` morto, dois hooks de tema, dois `index.html`, `cn()` nunca usado, token fantasma `text-volvo-accent`, favicon e og-image apontando para arquivos inexistentes, paleta duplicada com valores divergentes entre CSS e Tailwind.
4. **O melhor do site-eduardo é padrão, não código** — e padrão se copia de graça: o guardião de prebuild que valida uso e falha mais duro em produção; a porta única `?op=` para caber no limite de funções da Vercel; o hook `{data, loading, error, refetch}`; nomes de domínio em português; a honestidade dos textos de consentimento; e a lição da `014` (autorização nunca em `user_metadata`).
5. **A identidade LDC ainda não existe em nenhum arquivo lido.** Vale decidir isso uma vez e registrar — sugestão: `docs/identidade-ldc.md` no próprio LDC Analytics, com paleta, tipografia, logo e regras de uso, para ser a fonte que um futuro monorepo consumiria.

**Plano mínimo:** projeto novo (Vite 6 + React 18 + TS 5 + Tailwind 3), repositório e deploy separados, acesso restrito; copiar `formatters.ts`, `utils.ts`, `errorHandler.ts`, `logger.ts`, `DashboardCard`, `TabelaResultadosMensais`, `GraficoCarteiraConsolidada`; recriar `tailwind.config.js` com os 5 hex `premium-*` mais uma paleta de séries acessível; autorização pelo modelo da `014`; guarda aplicada no roteador; e um guardião de prebuild espelhado no `verificar-identidade.mjs`, apontado para segredo/env em vez de registro CVM.
