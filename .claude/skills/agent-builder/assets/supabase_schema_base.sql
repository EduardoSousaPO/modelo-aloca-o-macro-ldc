-- ============================================================
-- Schema Base — Produto com Agente OpenClaw
-- Gerado pela skill Agent Builder (ABC)
-- ============================================================
-- INSTRUÇÕES:
-- 1. Este é o schema base. Adicione tabelas específicas do
--    seu negócio ABAIXO da seção "Tabelas específicas do negócio"
-- 2. Nunca remova as tabelas base — o agente depende delas
-- 3. Salve como: supabase/migrations/001_initial_schema.sql
-- 4. Execute com: supabase db push
-- ============================================================

-- ============================================================
-- EXTENSÕES
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABELAS BASE
-- ============================================================

-- Perfis de usuário (extensão do auth.users do Supabase)
CREATE TABLE public.profiles (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  display_name TEXT,
  email TEXT,

  -- Identificadores de canal (adicionar os que forem usados)
  telegram_chat_id TEXT UNIQUE,
  whatsapp_number  TEXT UNIQUE,

  -- Preferências do usuário
  preferences JSONB DEFAULT '{}',
  timezone TEXT DEFAULT 'America/Sao_Paulo',
  language TEXT DEFAULT 'pt-BR',

  -- Controle
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversas (sessões de interação com o agente)
CREATE TABLE public.conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,

  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp', 'webchat', 'api')),
  channel_session_id TEXT, -- ID da sessão no canal (ex: chat_id do Telegram)

  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'error', 'abandoned')),

  -- Metadata da conversa
  metadata JSONB DEFAULT '{}',

  -- Timestamps
  started_at TIMESTAMPTZ DEFAULT NOW(),
  last_message_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Mensagens trocadas
CREATE TABLE public.messages (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,

  role TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
  content TEXT NOT NULL,

  -- Para mensagens do agente: ações executadas
  tool_calls JSONB,   -- tools que o agente chamou
  tool_results JSONB, -- resultados das tools

  -- Metadata
  tokens_used INTEGER,
  model_used TEXT,
  latency_ms INTEGER,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks executadas pelo agente (ações no mundo real)
CREATE TABLE public.agent_tasks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE,
  user_id UUID REFERENCES public.profiles(id),

  task_type TEXT NOT NULL,       -- tipo de task (ex: 'send_email', 'update_crm', 'generate_report')
  task_description TEXT,         -- descrição legível do que foi feito

  status TEXT DEFAULT 'pending' CHECK (
    status IN ('pending', 'running', 'completed', 'failed', 'awaiting_approval', 'cancelled')
  ),

  -- Input e output da task
  input_data JSONB,
  output_data JSONB,
  error_message TEXT,

  -- Controle de aprovação
  requires_approval BOOLEAN DEFAULT FALSE,
  approval_requested_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ,
  approved_by UUID REFERENCES public.profiles(id),
  rejection_reason TEXT,

  -- Controle de execução
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  scheduled_for TIMESTAMPTZ,     -- para tasks com cron

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

-- ============================================================
-- FUNÇÕES AUXILIARES
-- ============================================================

-- Atualiza updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para profiles
CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Atualiza last_message_at da conversa quando nova mensagem chega
CREATE OR REPLACE FUNCTION update_conversation_last_message()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE public.conversations
  SET last_message_at = NOW()
  WHERE id = NEW.conversation_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER messages_update_conversation
  AFTER INSERT ON public.messages
  FOR EACH ROW EXECUTE FUNCTION update_conversation_last_message();

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Obrigatório — nunca remover
-- ============================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_tasks ENABLE ROW LEVEL SECURITY;

-- Profiles: usuário vê e edita apenas o próprio perfil
CREATE POLICY "profiles_own" ON public.profiles
  FOR ALL USING (auth.uid() = id);

-- Conversations: usuário vê apenas as próprias conversas
CREATE POLICY "conversations_own" ON public.conversations
  FOR ALL USING (auth.uid() = user_id);

-- Messages: usuário vê apenas mensagens das próprias conversas
CREATE POLICY "messages_own" ON public.messages
  FOR ALL USING (
    conversation_id IN (
      SELECT id FROM public.conversations WHERE user_id = auth.uid()
    )
  );

-- Agent tasks: usuário vê apenas as próprias tasks
CREATE POLICY "tasks_own" ON public.agent_tasks
  FOR SELECT USING (auth.uid() = user_id);

-- Service role bypass (para o agente OpenClaw acessar via MCP com service role key)
-- O agente usa a SERVICE_ROLE_KEY que bypassa RLS — manter assim para operação do agente

-- ============================================================
-- ÍNDICES (performance)
-- ============================================================

CREATE INDEX idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX idx_conversations_status ON public.conversations(status);
CREATE INDEX idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX idx_messages_created_at ON public.messages(created_at DESC);
CREATE INDEX idx_agent_tasks_user_id ON public.agent_tasks(user_id);
CREATE INDEX idx_agent_tasks_status ON public.agent_tasks(status);
CREATE INDEX idx_agent_tasks_requires_approval ON public.agent_tasks(requires_approval) WHERE requires_approval = TRUE;

-- ============================================================
-- TABELAS ESPECÍFICAS DO NEGÓCIO
-- Adicione abaixo as tabelas específicas do seu caso de uso
-- ============================================================

-- Exemplo de tabela específica (remover e substituir pelas suas):
-- CREATE TABLE public.leads (
--   id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
--   user_id UUID REFERENCES public.profiles(id),
--   name TEXT NOT NULL,
--   email TEXT,
--   phone TEXT,
--   status TEXT DEFAULT 'new',
--   notes TEXT,
--   source TEXT,
--   created_by_agent BOOLEAN DEFAULT FALSE,
--   created_at TIMESTAMPTZ DEFAULT NOW()
-- );
-- ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "leads_own" ON public.leads FOR ALL USING (auth.uid() = user_id);
