# Handoff de Infraestrutura — [Nome do Agente]

**Gerado pelo ABC em:** [data]
**Status:** Aguardando execução pelo usuário
**Modo:** Infra (Camada 3 — supervisionado)

---

## Pré-requisitos

Antes de iniciar, confirme que você tem:

- [ ] VPS Hostinger provisionado (Ubuntu 22.04)
- [ ] IP do VPS: `_______________`
- [ ] Acesso SSH configurado (senha ou chave)
- [ ] API key do LLM: `_______________ ` (Anthropic / OpenAI / Google)
- [ ] Token do canal: `_______________` (Telegram Bot Token)
- [ ] Projeto Supabase criado: `_______________` (URL)
- [ ] Supabase Service Role Key: `_______________`
- [ ] Repositório GitHub: `_______________` (URL)

---

## Bloco A — Setup do VPS

### A.1 — Verificar estado atual

```bash
ssh [USUARIO_SSH]@[IP_DO_VPS]
node --version 2>/dev/null || echo "Node.js não instalado"
which openclaw 2>/dev/null || echo "OpenClaw não instalado"
systemctl status openclaw 2>/dev/null || echo "Serviço não existe"
df -h
free -h
```

**Me envie o output para eu identificar o ponto de entrada.**

### A.2 — Preparar servidor (se necessário)

```bash
apt update && apt upgrade -y
apt install -y curl wget git unzip build-essential
curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt install -y nodejs
node --version
npm --version
```

**Verificação:** `node --version` deve mostrar v24.x

### A.3 — Instalar OpenClaw

```bash
npm install -g openclaw
openclaw --version
openclaw init
```

**Verificação:** `openclaw --version` deve mostrar a versão instalada

### A.4 — Configurar variáveis de ambiente

```bash
cat > ~/.openclaw/.env << 'EOF'
# LLM Provider
ANTHROPIC_API_KEY=[SUA_API_KEY]

# Canal
TELEGRAM_BOT_TOKEN=[TELEGRAM_BOT_TOKEN]

# Supabase
SUPABASE_URL=[SUPABASE_URL]
SUPABASE_SERVICE_ROLE_KEY=[SUPABASE_SERVICE_ROLE_KEY]
EOF

chmod 600 ~/.openclaw/.env
```

**IMPORTANTE:** Substitua os placeholders pelos seus valores reais.

### A.5 — Copiar arquivos do agente

```bash
git clone https://github.com/[USUARIO_GITHUB]/[NOME_REPO].git ~/projetos/[NOME_AGENTE]
cp -r ~/projetos/[NOME_AGENTE]/agents/ ~/.openclaw/agents/
cp -r ~/projetos/[NOME_AGENTE]/skills/ ~/.openclaw/skills/
```

### A.6 — Configurar systemd

```bash
cat > /etc/systemd/system/openclaw.service << 'EOF'
[Unit]
Description=OpenClaw Agent Gateway
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/.openclaw
ExecStart=/usr/bin/openclaw start
Restart=always
RestartSec=2
EnvironmentFile=/root/.openclaw/.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=openclaw
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable openclaw
systemctl start openclaw
systemctl status openclaw
```

**Verificação:** Status deve mostrar `active (running)`

### A.7 — Auditoria de segurança

```bash
openclaw security audit
```

**Verificação:** 0 erros críticos. Se houver, me envie o output.

---

## Bloco B — Canal de Comunicação

### Telegram

```bash
# 1. Crie bot no BotFather (t.me/BotFather) → /newbot
# 2. Copie o token gerado
# 3. O token já deve estar no .env (Bloco A.4)
# 4. Configure no OpenClaw:
openclaw config set channels.telegram.enabled true

# 5. Reinicie:
systemctl restart openclaw

# 6. Teste: envie /start para o bot no Telegram
journalctl -u openclaw -f
```

**Verificação:** Bot responde no Telegram

---

## Bloco C — Supabase

```bash
# No seu computador local, dentro da pasta do projeto:
npm install -g supabase
supabase login
supabase link --project-ref [REF_DO_PROJETO]
supabase db push
```

**Verificação:** Tabelas criadas no painel do Supabase, RLS habilitado

### Instalar MCP do Supabase no agente

```bash
# No VPS:
openclaw config set mcpServers.supabase.command "npx"
openclaw config set mcpServers.supabase.args '["@supabase/mcp-server-supabase@latest"]'
systemctl restart openclaw
```

---

## Bloco D — Frontend

### Se Lovable:
1. Acesse lovable.dev → Novo projeto
2. Conecte ao Supabase (use a URL e anon key)
3. Descreva as telas baseadas no PRD
4. Lovable gerencia o deploy

### Se Next.js:
```bash
cd frontend/
npx create-next-app@latest . --typescript --tailwind --app
npm install @supabase/supabase-js @supabase/auth-helpers-nextjs
```

---

## Bloco E — GitHub + CI/CD

```bash
# No computador local:
git init
git add .
git commit -m "feat: initial agent setup"
git remote add origin https://github.com/[USUARIO_GITHUB]/[NOME_REPO].git
git push -u origin main
```

### GitHub Secrets (Settings → Secrets → Actions):
- `VPS_HOST` = [IP_DO_VPS]
- `VPS_USER` = [USUARIO_SSH]
- `VPS_SSH_KEY` = [conteúdo da chave privada SSH]

---

## Checklist final

- [ ] `systemctl status openclaw` = active (running)
- [ ] Bot responde no canal configurado
- [ ] Supabase conectado (MCP testado)
- [ ] `.env` não está no repositório GitHub
- [ ] `openclaw security audit` sem erros críticos
- [ ] GitHub Actions configurado e testado
- [ ] Frontend conectado ao Supabase (se aplicável)

**Quando todos os itens estiverem marcados, avise para entrarmos no Modo Validação.**
