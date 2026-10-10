# Integração com Lovable — Agent Builder Copilot

Guia para uso do Lovable como ferramenta de frontend quando o agente precisa de interface web.

---

## O que é o Lovable

Lovable (lovable.dev) é uma plataforma de geração de frontend com IA. Permite criar interfaces web completas descrevendo o que quer em linguagem natural. Gera código React/TypeScript com Tailwind CSS e integração Supabase nativa.

---

## Quando usar Lovable vs. Next.js

### Use Lovable quando:
- O frontend é um painel/dashboard de acompanhamento do agente
- O usuário não tem experiência com frontend
- Velocidade de entrega é prioridade (horas vs. dias)
- O frontend é "complementar" ao agente (o agente é o produto, o frontend é visualização)
- Precisa de UI bonita rapidamente sem designer
- O caso de uso é CRUD + visualização + autenticação

### Use Next.js (via Claude Code) quando:
- O frontend TEM lógica complexa (SSR, API routes, middleware)
- Precisa de controle total sobre o código
- Há requisitos de performance específicos (ISR, edge functions)
- O frontend É o produto principal (não apenas painel do agente)
- O time tem desenvolvedores frontend
- Precisa de WebSocket direto com o gateway OpenClaw

### Não crie frontend no MVP quando:
- O agente funciona 100% via canal (Telegram/WhatsApp)
- Você é o único usuário por enquanto
- O frontend não agrega valor na fase de validação

---

## Arquitetura: Lovable + Supabase + OpenClaw

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│    Lovable       │     │   Supabase   │     │    OpenClaw     │
│  (Frontend)      │────→│  (Backend)   │←────│   (Agente)      │
│                  │     │              │     │                  │
│  - Dashboard     │     │  - Auth      │     │  - Gateway       │
│  - Histórico     │     │  - Database  │     │  - LLM           │
│  - Config        │     │  - RLS       │     │  - Tools          │
│  - Login         │     │  - Realtime  │     │  - Skills         │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

**Separação de responsabilidades:**
- **Lovable** → interface do usuário humano (visualiza, configura, monitora)
- **Supabase** → banco de dados compartilhado (ambos leem/escrevem)
- **OpenClaw** → runtime do agente (processa, age, responde)

O agente e o frontend **não se comunicam diretamente**. Ambos falam com o Supabase:
- Agente escreve em `messages`, `agent_tasks`, `conversations`
- Frontend lê dessas tabelas e exibe para o usuário
- Frontend pode escrever configs/preferências que o agente lê

---

## Como configurar Lovable no projeto

### Passo 1 — Criar projeto no Lovable
Instrua o usuário:
1. Acesse lovable.dev
2. Crie novo projeto
3. Conecte ao Supabase (Lovable tem integração nativa)
4. Use o URL e anon key do projeto Supabase já criado

### Passo 2 — Descrever as telas para o Lovable

O que pedir ao Lovable gerar (baseado no PRD do agente):

**Tela de Login:**
```
"Crie uma tela de login com autenticação Supabase.
Email e senha. Design moderno e minimalista."
```

**Dashboard principal:**
```
"Crie um dashboard que mostra:
- Número de conversas ativas
- Últimas 10 mensagens do agente
- Tasks pendentes de aprovação
- Status do agente (online/offline)
Dados vêm das tabelas: conversations, messages, agent_tasks no Supabase."
```

**Histórico de conversas:**
```
"Crie uma tela de histórico de conversas.
Lista de conversas na esquerda, mensagens da conversa selecionada na direita.
Tabelas: conversations e messages no Supabase.
Filtro por data e status."
```

**Painel de aprovações (se o agente tem ações com approval):**
```
"Crie um painel que mostra tasks aguardando aprovação.
Cada task mostra: descrição, dados de entrada, botões Aprovar/Rejeitar.
Tabela: agent_tasks onde status = 'awaiting_approval'."
```

### Passo 3 — Conectar ao repositório GitHub
O Lovable pode exportar o código para o GitHub:
1. No Lovable, vá em Settings → GitHub
2. Conecte ao repositório do projeto
3. O código do frontend fica numa branch ou pasta separada
4. Lovable gerencia deploy automaticamente ou você faz deploy manual

### Passo 4 — Verificar integração com Supabase
- RLS deve estar habilitado (o frontend usa anon key)
- Tabelas base devem existir (rodar migration antes)
- Supabase Realtime pode ser usado para updates em tempo real no dashboard

---

## Lovable no fluxo da ABC

### No Modo Arquitetura (Etapa 11):
Apresente a opção:
```
"Para o frontend, recomendo Lovable:
- Gera interface React bonita em minutos
- Integração nativa com Supabase
- Sem necessidade de código manual
- Ideal para dashboard de acompanhamento

O frontend vai mostrar: [lista baseada no PRD]
Confirma Lovable ou prefere Next.js?"
```

### No Modo Infra (Bloco D):
Guie a configuração:
```
"Agora vamos criar o frontend no Lovable.

1. Acesse lovable.dev e crie um novo projeto
2. Conecte ao seu Supabase (URL: [SUPABASE_URL])
3. Descreva a primeira tela: [sugestão baseada no PRD]
4. Quando a tela estiver pronta, me avise que eu guio as próximas

O Lovable cuida do deploy automaticamente."
```

### No Modo Validação:
Verifique:
- [ ] Frontend mostra dados reais do Supabase
- [ ] Login funciona com Supabase Auth
- [ ] Dashboard atualiza quando o agente processa uma tarefa
- [ ] RLS impede acesso a dados de outros usuários

---

## Limitações do Lovable

Esteja ciente e comunique quando relevante:
- Não suporta WebSocket direto com OpenClaw gateway (use Supabase Realtime como ponte)
- Controle limitado sobre performance e otimizações avançadas
- Se o frontend crescer muito em complexidade, pode ser hora de migrar para Next.js
- O código gerado é React + Vite, não Next.js — sem SSR nativo
