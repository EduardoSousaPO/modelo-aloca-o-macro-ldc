# Guia de Setup VPS Hostinger — OpenClaw

Referência completa para instalação do OpenClaw em VPS Hostinger do zero.
Use este guia durante a Fase 4 do SKILL.md.

---

## Pré-requisitos

Antes de começar, confirme que o usuário tem:
- [ ] VPS Hostinger provisionado (Ubuntu 22.04 recomendado)
- [ ] IP do VPS
- [ ] Acesso SSH (senha ou chave)
- [ ] API key do LLM escolhido (Anthropic / OpenAI / Google)
- [ ] Token do canal (Telegram Bot Token, ou conta WhatsApp Business)

---

## Passo 0 — Verificação do estado atual

Antes de qualquer instalação, verifique o que já existe:

```bash
ssh root@[IP_DO_VPS]

# Verificar OS
lsb_release -a

# Verificar Node.js
node --version 2>/dev/null || echo "Node.js não instalado"

# Verificar npm
npm --version 2>/dev/null || echo "npm não disponível"

# Verificar se OpenClaw já está instalado
which openclaw 2>/dev/null || echo "OpenClaw não instalado"

# Verificar se o serviço existe
systemctl status openclaw 2>/dev/null || echo "Serviço openclaw não existe"

# Verificar espaço em disco
df -h

# Verificar RAM disponível
free -h
```

Com base no output, identifique o ponto de entrada:
- Tudo zerado → execute do Passo 1
- Node.js já instalado → pule para Passo 2
- OpenClaw já instalado → pule para Passo 3 (verificar configuração)

---

## Passo 1 — Preparar o servidor

```bash
# Atualizar pacotes
apt update && apt upgrade -y

# Instalar dependências básicas
apt install -y curl wget git unzip build-essential

# Instalar Node.js 24 (versão LTS recomendada para OpenClaw)
curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt install -y nodejs

# Verificar versões
node --version    # deve mostrar v24.x.x
npm --version     # deve mostrar 10.x.x ou superior

# Instalar Docker (necessário para sandboxing se exec estiver habilitado)
curl -fsSL https://get.docker.com | bash -
systemctl enable docker
systemctl start docker
docker --version
```

---

## Passo 2 — Instalar OpenClaw

```bash
# Instalar globalmente via npm
npm install -g openclaw

# Verificar instalação
openclaw --version

# Inicializar (cria estrutura em ~/.openclaw)
openclaw init
```

Durante o `openclaw init`, o assistente faz algumas perguntas. Respostas típicas:
- Nome do agente: [nome definido no projeto]
- Diretório de trabalho: aceitar o padrão (`~/.openclaw`)
- LLM provider: escolher o que foi decidido no discovery (claude/openai/gemini)

---

## Passo 3 — Configurar variáveis de ambiente

```bash
# Criar arquivo .env principal
cat > ~/.openclaw/.env << 'EOF'
# LLM Provider (escolha um)
ANTHROPIC_API_KEY=sk-ant-COLOQUE_SUA_KEY_AQUI
# OPENAI_API_KEY=sk-COLOQUE_SUA_KEY_AQUI
# GOOGLE_AI_API_KEY=COLOQUE_SUA_KEY_AQUI

# Canal (dependendo do que foi configurado)
# TELEGRAM_BOT_TOKEN=COLOQUE_SEU_TOKEN_AQUI

# Supabase (adicionar quando configurado)
# SUPABASE_URL=https://PROJETO.supabase.co
# SUPABASE_SERVICE_ROLE_KEY=eyJ...
EOF

# Proteger o arquivo (só root lê)
chmod 600 ~/.openclaw/.env

# IMPORTANTE: verificar que .env está no .gitignore do projeto
```

⚠️ **Nunca commitar este arquivo no GitHub. Contém credenciais.**

---

## Passo 4 — Copiar arquivos do agente

**Opção A — Via GitHub (recomendado):**
```bash
# No VPS
git clone https://github.com/[usuario]/[repo].git ~/projetos/[nome-agente]

# Copiar soul.md e config.json para o diretório do agente
cp ~/projetos/[nome-agente]/agents/[nome]/* ~/.openclaw/agents/[nome]/

# Copiar skills custom
cp -r ~/projetos/[nome-agente]/skills/* ~/.openclaw/skills/
```

**Opção B — Via SCP (do computador local):**
```bash
# Rodar no seu computador, dentro da pasta do projeto
scp -r ./agents/[nome]/ root@[IP]:~/.openclaw/agents/
scp -r ./skills/ root@[IP]:~/.openclaw/skills/
```

---

## Passo 5 — Instalar skills do ClawHub

```bash
# Para cada skill identificada no discovery, instalar:
openclaw skills install [slug-da-skill]

# Exemplos comuns:
# openclaw skills install telegram-helper
# openclaw skills install web-search-pro
# openclaw skills install email-sender

# Verificar skills instaladas
openclaw skills list

# Executar audit de segurança após cada instalação externa
openclaw security audit
```

---

## Passo 6 — Configurar systemd (restart automático)

```bash
# Criar arquivo de serviço
cat > /etc/systemd/system/openclaw.service << 'EOF'
[Unit]
Description=OpenClaw Agent Gateway
After=network.target
Wants=network-online.target

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

# Limites de recursos
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# Ativar e iniciar o serviço
systemctl daemon-reload
systemctl enable openclaw
systemctl start openclaw

# Verificar status
systemctl status openclaw

# Acompanhar logs em tempo real
journalctl -u openclaw -f
```

---

## Passo 7 — Configurar canal de comunicação

### Telegram (recomendado para desenvolvimento)

```bash
# 1. Criar bot no Telegram:
#    - Abra o Telegram
#    - Procure @BotFather
#    - Envie /newbot
#    - Siga as instruções para nomear o bot
#    - Copie o token gerado (formato: 1234567890:ABCdef...)

# 2. Adicionar token ao .env do VPS
echo "TELEGRAM_BOT_TOKEN=SEU_TOKEN_AQUI" >> ~/.openclaw/.env

# 3. Configurar no OpenClaw
openclaw config set channels.telegram.enabled true
openclaw config set channels.telegram.token "$TELEGRAM_BOT_TOKEN"

# 4. Reiniciar para aplicar
systemctl restart openclaw

# 5. Testar
# Abra o Telegram, procure seu bot pelo nome, envie /start
# Acompanhe os logs:
journalctl -u openclaw -f
```

### WhatsApp (requer conta Business aprovada)

```bash
# ATENÇÃO: WhatsApp requer aprovação prévia da Meta para a WhatsApp Business API
# O processo pode levar dias a semanas
# Enquanto a aprovação não vem, use Telegram para desenvolvimento

# Quando aprovado, o token é configurado via:
openclaw config set channels.whatsapp.enabled true
openclaw config set channels.whatsapp.token "$WHATSAPP_TOKEN"
```

### WebChat (para integração com Next.js)

```bash
# Habilitar API WebSocket do gateway
openclaw config set gateway.websocket.enabled true
openclaw config set gateway.websocket.port 3001

# O frontend Next.js se conecta via:
# ws://[IP_DO_VPS]:3001
# Mas via Tailscale/tunnel para não expor a porta publicamente
```

---

## Passo 8 — Configurar acesso seguro remoto

```bash
# Instalar Tailscale (recomendado para acesso seguro sem expor portas)
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up

# Após autenticar no Tailscale, você terá um IP privado (100.x.x.x)
# Use esse IP para acessar o VPS de qualquer lugar, sem abrir portas

# Alternativa: SSH tunnel para o Control UI
# No seu computador local:
# ssh -L 8080:localhost:8080 root@[IP_VPS]
# Acessa em: http://localhost:8080
```

**Nunca exponha o gateway OpenClaw diretamente na internet sem autenticação.**

---

## Passo 9 — Auditoria de segurança

```bash
# Sempre executar após instalação completa
openclaw security audit

# Ver detalhes
openclaw security audit --verbose

# Corrigir problemas comuns automaticamente
openclaw security audit --fix

# Verificar resultado: deve mostrar 0 erros críticos
```

Problemas comuns que o audit detecta e como resolver:
- "Gateway exposed to network" → setar binding para loopback ou usar Tailscale
- "exec tool without approvals" → configurar exec_approvals ou desabilitar exec
- "No authentication on gateway" → setar gateway.auth.token no config
- "Permissions on .env too broad" → `chmod 600 ~/.openclaw/.env`

---

## Passo 10 — Primeiro teste funcional

```bash
# Verificar status geral
openclaw status

# Acompanhar logs em tempo real
journalctl -u openclaw -f

# No canal configurado (Telegram), enviar:
# "olá" ou "/start"
# O agente deve responder de acordo com o soul.md

# Se não responder, verificar:
# 1. Token do canal está correto no .env?
systemctl restart openclaw
# 2. Logs mostram erro de autenticação?
journalctl -u openclaw --since "5 minutes ago"
# 3. Firewall bloqueando saída de rede?
curl -s https://api.anthropic.com/v1/models -H "x-api-key: $ANTHROPIC_API_KEY" | head -20
```

---

## Configuração de backup

```bash
# Criar script de backup diário
cat > /usr/local/bin/openclaw-backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/root/backups/openclaw"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup do diretório openclaw (exceto logs muito grandes)
tar -czf "$BACKUP_DIR/openclaw_$DATE.tar.gz" \
  --exclude="~/.openclaw/logs" \
  ~/.openclaw/

# Manter apenas últimos 30 backups
ls -t $BACKUP_DIR/openclaw_*.tar.gz | tail -n +31 | xargs rm -f

echo "Backup concluído: openclaw_$DATE.tar.gz"
EOF

chmod +x /usr/local/bin/openclaw-backup.sh

# Agendar backup diário às 3h da manhã
echo "0 3 * * * root /usr/local/bin/openclaw-backup.sh >> /var/log/openclaw-backup.log 2>&1" > /etc/cron.d/openclaw-backup
```

---

## Troubleshooting comum

| Sintoma | Causa provável | Solução |
|---|---|---|
| Agente não responde | Token errado ou serviço parado | Verificar .env + `systemctl status openclaw` |
| Erro "API key invalid" | Key incorreta ou sem crédito | Verificar key no provider + saldo |
| Serviço reinicia em loop | Erro de configuração | `journalctl -u openclaw -n 50` para ver o erro |
| Telegram bot não conecta | Bot token inválido | Criar novo bot no BotFather |
| Latência alta | VPS com pouca RAM | Verificar `free -h`, considerar upgrade |
| Skills não carregam | Path incorreto | `openclaw skills list` para verificar |
| Security audit falha | Configuração permissiva | `openclaw security audit --fix` |
