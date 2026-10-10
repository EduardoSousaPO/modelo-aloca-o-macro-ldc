# Catálogo de Decisões Técnicas — Defaults e Trade-offs

Use este arquivo na Fase 2 para apresentar decisões ao usuário com justificativa clara.

---

## LLM — Modelo e Provider

### Default: Claude Sonnet 4.6 (Anthropic)

**Quando usar:**
- Maioria dos casos de uso (atendimento, vendas, suporte, automação de escritório)
- Quando custo é uma consideração
- MVP e primeiros agentes

**Custo estimado:**
- Input: ~$3 por 1M tokens
- Output: ~$15 por 1M tokens
- Interação típica (2K tokens): ~$0,03
- 1.000 interações/mês: ~$30

**Alternativas e quando trocar:**

| Modelo | Quando usar | Custo relativo |
|---|---|---|
| Claude Opus 4.6 | Raciocínio muito complexo, análise jurídica/financeira densa | 5-10x mais caro |
| Claude Haiku 4.5 | Respostas simples, alto volume, latência crítica | 5x mais barato |
| GPT-4o | Time já usa OpenAI, melhor integração com ferramentas OpenAI | Similar ao Sonnet |
| Gemini 1.5 Pro | Contexto muito longo (>200K tokens), Google Workspace nativo | Similar |

**Default assumido sem perguntar:** Claude Sonnet 4.6

---

## Canal — Onde o usuário interage

### Default para desenvolvimento: Telegram

**Por que Telegram primeiro:**
- Bot criado em 2 minutos via BotFather
- Sem processo de aprovação
- API estável, raramente muda
- Gratuito sem limites de mensagem para bots

**WhatsApp — quando usar e riscos:**
- Requer conta WhatsApp Business aprovada pela Meta
- Processo de aprovação: de dias a semanas (sem garantia)
- Custo por conversa iniciada pelo negócio (varia por região)
- API muda com frequência (Baileys precisa de atualização)
- **Recomendação:** Desenvolva com Telegram, migre para WhatsApp quando o agente estiver validado

**WebChat — quando usar:**
- Produto tem frontend próprio (Next.js)
- Usuário não quer instalar app
- Integração com site existente
- Requer configuração de WebSocket e autenticação no frontend

**Múltiplos canais:** Possível, mas adicionar um canal por vez. Não tente Telegram + WhatsApp + WebChat no MVP.

**Default assumido sem perguntar:** Telegram para desenvolvimento

---

## Memória — O que persiste onde

### Arquitetura padrão (assumida sem perguntar):

| Tipo de dado | Onde fica | Por quê |
|---|---|---|
| Preferências do usuário no agente | MEMORY.md | Injetado no system prompt automaticamente |
| Personalidade/ajustes do agente | MEMORY.md | Mesmo motivo |
| Histórico de conversas | Supabase (tabela `messages`) | Queryable pelo frontend |
| Dados operacionais do produto | Supabase | SQL queries, relatórios |
| Arquivos temporários de tarefas | Workspace OpenClaw | Escopo de sessão |
| Conhecimento de domínio (FAQ, docs) | Workspace + skill | Consultado via read tool |

### Quando considerar memória avançada (não no MVP):
- Busca semântica (RAG): quando o agente precisa buscar em base de conhecimento grande (>100 documentos)
- DREAMS: processamento assíncrono de memória — pouco documentado, deixar para v2
- Knowledge graph: quando as relações entre entidades são complexas (não para MVP)

---

## Tools — O que habilitar por padrão

### Tools habilitadas por padrão (baixo risco):
- `read` — leitura de arquivos
- `write` / `edit` — escrita de arquivos (com scope limitado ao workspace)
- `web_search` — busca na web
- `web_fetch` — leitura de URLs
- `image` — geração de imagem (se o caso de uso precisar)
- `cron` — agendamento (se o caso de uso precisar)
- `message` — envio de mensagens proativas (se o caso de uso precisar)

### Tools desabilitadas por padrão (requerem decisão explícita):
- `exec` — execução de comandos shell → habilitar apenas se o caso de uso exige, com approval obrigatório
- `browser` — controle de navegador → habilitar apenas para automação web específica
- MCPs externos → habilitar apenas os necessários, um por um

### Quando `exec` é necessário vs. quando é excesso:
- **Necessário:** agente precisa rodar scripts, instalar pacotes, controlar processos, interagir com sistema operacional
- **Excesso (use alternativa):** agente só precisa ler arquivo → use `read`; só precisa buscar na web → use `web_search`; só precisa enviar email → use MCP de email

---

## Guardrails — Configuração padrão

### Sempre configurar (não negociável):
- Gateway auth: token ou senha obrigatório
- Allowlist de usuários: modo `pairing` (usuário novo precisa aprovar código)
- Security audit: executar após cada mudança de configuração

### Configurar baseado no caso de uso:
- Exec approvals: se `exec` habilitado → sempre com approval
- Sandbox Docker: se `exec` habilitado → isolar execução
- Horário de funcionamento: se o agente tem restrições de hora

### Soft guardrails no SOUL.md (advisory, não técnico):
- "Nunca execute ações irreversíveis sem confirmação explícita"
- "Se não tiver certeza, pergunte antes de agir"
- "Identifique-se como IA quando perguntado diretamente"
- [+ regras específicas do caso de uso]

---

## Infraestrutura VPS — Sizing

### Para MVP e primeiros usuários (< 100 usuários ativos):

| Spec | Valor | Observação |
|---|---|---|
| CPU | 2 vCPU | 1 vCPU funciona mas gera latência em pico |
| RAM | 2 GB | Mínimo confortável. 4 GB se usar Docker/sandbox |
| Storage | 40 GB SSD | SSD obrigatório (startup do Node é lento em HDD) |
| OS | Ubuntu 22.04 LTS | Suporte até 2027 |
| Node.js | 24.x | Recomendado oficial do OpenClaw |

### Hostinger — planos compatíveis:
- KVM 2: 2 vCPU, 8 GB RAM, 100 GB → mais do que suficiente para MVP
- KVM 1: 1 vCPU, 4 GB RAM, 50 GB → suficiente para começar

### Quando fazer upgrade:
- Latência de resposta > 5 segundos consistentemente
- RAM usage > 80% em horário normal
- Muitos usuários simultâneos (> 50 conversas simultâneas)

---

## GitHub — Estrutura de branches

### Padrão adotado (sem perguntar):
- `main` → produção (protegido, só via PR)
- `develop` → integração e testes
- `feature/[nome]` → desenvolvimento de nova skill ou funcionalidade

### CI/CD padrão:
- Push em `main` → deploy automático no VPS via SSH
- Push em `develop` → apenas validação (lint, checklist de skills)

---

## Supabase — Configuração padrão

### Região recomendada para Brasil:
- `sa-east-1` (South America - São Paulo) → menor latência para usuários brasileiros

### Segurança sempre ativa (não negociável):
- Row Level Security (RLS) em todas as tabelas de dados de usuário
- Auth via Supabase Auth (JWT)
- Service Role Key apenas no servidor (nunca no frontend)
- Anon Key apenas no frontend (com RLS para limitar acesso)

### Tabelas base (sempre criadas):
- `profiles` — extensão de auth.users
- `conversations` — registro de sessões
- `messages` — mensagens trocadas
- `agent_tasks` — ações executadas pelo agente

### Tabelas específicas do negócio:
- Definidas durante a Etapa 4 do discovery
- Criadas como migrations numeradas (001, 002, ...)

---

## Frontend — Lovable vs. Next.js vs. Sem Frontend

### Opção 1: Lovable (padrão recomendado para dashboards)

**Quando usar:**
- Dashboard de acompanhamento do agente (métricas, histórico, aprovações)
- Usuário não tem experiência com frontend
- Velocidade é prioridade (horas vs. dias)
- CRUD + visualização + autenticação básica
- Frontend é "complementar" ao agente (não é o produto principal)

**Vantagens:**
- Gera React + Tailwind com IA em minutos
- Integração nativa com Supabase
- Deploy automático incluído
- Sem necessidade de código manual

**Limitações:**
- Sem SSR (Server-Side Rendering)
- Controle limitado sobre otimizações
- Sem WebSocket direto com OpenClaw (usar Supabase Realtime como ponte)
- Se crescer muito em complexidade, pode exigir migração

### Opção 2: Next.js via Claude Code

**Quando usar:**
- Frontend TEM lógica complexa (SSR, API routes, middleware)
- Precisa de controle total sobre o código
- Requisitos de performance específicos
- O frontend É o produto principal
- Time tem desenvolvedores frontend
- Precisa de WebSocket direto com gateway OpenClaw

**Vantagens:**
- Controle total
- SSR e edge functions
- Ecosystem React maduro

**Limitações:**
- Mais tempo de desenvolvimento
- Requer conhecimento técnico
- Manutenção manual

### Opção 3: Sem frontend no MVP

**Quando usar:**
- Agente funciona 100% via canal (Telegram/WhatsApp)
- Você é o único usuário por enquanto
- Frontend não agrega valor na fase de validação
- Quer validar o agente antes de investir em UI

**Default:** Se o usuário mencionou produto com usuários externos → Lovable. Se precisa de controle total → Next.js. Se é uso interno ou piloto → adia frontend.

---

## ClawHub — Pesquisa de skills existentes

### Quando consultar:
- Antes de criar qualquer skill custom
- Quando o comportamento desejado parece comum (atendimento, vendas, scheduling)
- Quando o agente precisa de integração com serviço popular

### Regra prática:
- Skill do ClawHub cobre 80%+ do comportamento → instale e adapte
- Cobre menos de 50% → crie do zero
- Entre 50-80% → avalie custo de adaptação vs. criação

*Para guia detalhado, leia `references/clawhub_guide.md`*

---

## Build with Claude — Componentes e padrões

### Quando consultar:
- Para componentes de frontend/UI
- Para padrões de integração com Claude API
- Para templates de projeto completo
- Para exemplos de agentes funcionais

### Diferença do ClawHub:
- ClawHub = skills de comportamento do agente (runtime)
- Build with Claude = componentes de interface e padrões de arquitetura
