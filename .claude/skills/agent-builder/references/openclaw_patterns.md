# Padrões de Configuração OpenClaw — Agent Builder Copilot

Referência de padrões de configuração do OpenClaw para uso no Modo Execução e Modo Infra.

---

## Estrutura de diretórios do OpenClaw

```
~/.openclaw/                    # Diretório principal do gateway
├── .env                        # Variáveis de ambiente (credenciais)
├── config.json                 # Configuração global do gateway
├── agents/
│   └── [nome-agente]/
│       ├── soul.md             # Identidade e regras do agente
│       ├── config.json         # Configuração específica do agente
│       ├── memory.md           # Memória persistente do agente
│       └── workspace/          # Workspace de trabalho (arquivos temporários)
├── skills/
│   └── [nome-skill]/
│       └── SKILL.md            # Skill instalada ou custom
├── plugins/                    # Plugins de canal, provedor, etc.
└── logs/                       # Logs de execução
```

---

## config.json do agente — Padrão recomendado

```json
{
  "name": "[nome-do-agente]",
  "model": "claude-sonnet-4-6",
  "modelProvider": "anthropic",
  
  "systemPrompt": {
    "source": "soul.md",
    "injectMemory": true,
    "injectSkills": true
  },
  
  "tools": {
    "read": { "enabled": true },
    "write": { "enabled": true },
    "edit": { "enabled": true },
    "web_search": { "enabled": true },
    "web_fetch": { "enabled": true },
    "image": { "enabled": false },
    "exec": { "enabled": false },
    "browser": { "enabled": false },
    "message": { "enabled": false },
    "cron": { "enabled": false }
  },
  
  "toolPolicy": {
    "exec": {
      "requireApproval": true,
      "allowedCommands": [],
      "sandbox": "docker"
    },
    "message": {
      "requireApproval": "bulk",
      "maxPerHour": 50
    }
  },
  
  "memory": {
    "enabled": true,
    "source": "memory.md",
    "maxEntries": 100,
    "autoSave": true
  },
  
  "channels": {
    "telegram": {
      "enabled": false,
      "token": "${TELEGRAM_BOT_TOKEN}"
    },
    "whatsapp": {
      "enabled": false,
      "token": "${WHATSAPP_TOKEN}"
    },
    "websocket": {
      "enabled": false,
      "port": 3001
    }
  },
  
  "gateway": {
    "auth": {
      "enabled": true,
      "token": "${GATEWAY_AUTH_TOKEN}"
    },
    "allowlist": {
      "mode": "pairing"
    },
    "binding": "127.0.0.1"
  },
  
  "mcpServers": {},
  
  "sandbox": {
    "enabled": false,
    "runtime": "docker",
    "memoryLimit": "512m",
    "cpuLimit": "1.0"
  }
}
```

---

## Padrões por caso de uso

### Agente de atendimento (baixo risco)
```json
{
  "tools": {
    "read": { "enabled": true },
    "write": { "enabled": true },
    "web_search": { "enabled": true },
    "web_fetch": { "enabled": true },
    "message": { "enabled": true }
  },
  "toolPolicy": {
    "message": { "requireApproval": false, "maxPerHour": 100 }
  }
}
```
- Tools de leitura + busca web + mensagem proativa
- Sem exec, sem browser
- Message sem approval (respostas de atendimento)

### Agente de automação (médio risco)
```json
{
  "tools": {
    "read": { "enabled": true },
    "write": { "enabled": true },
    "exec": { "enabled": true },
    "cron": { "enabled": true },
    "web_search": { "enabled": true }
  },
  "toolPolicy": {
    "exec": {
      "requireApproval": true,
      "allowedCommands": ["node", "python", "npm run"],
      "sandbox": "docker"
    }
  },
  "sandbox": {
    "enabled": true,
    "runtime": "docker"
  }
}
```
- Exec habilitado mas com approval + sandbox + allowlist
- Cron para tarefas recorrentes
- Docker obrigatório

### Agente de pesquisa (baixo risco)
```json
{
  "tools": {
    "read": { "enabled": true },
    "write": { "enabled": true },
    "web_search": { "enabled": true },
    "web_fetch": { "enabled": true },
    "browser": { "enabled": true }
  },
  "toolPolicy": {
    "browser": { "requireApproval": false }
  }
}
```
- Browser habilitado para scraping mais avançado
- Sem exec (pesquisa não precisa rodar comandos)

### Agente com Supabase (qualquer caso)
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["@supabase/mcp-server-supabase@latest"],
      "env": {
        "SUPABASE_URL": "${SUPABASE_URL}",
        "SUPABASE_SERVICE_ROLE_KEY": "${SUPABASE_SERVICE_ROLE_KEY}"
      }
    }
  }
}
```
- Sempre via Service Role Key (bypassa RLS para operação do agente)
- RLS protege o frontend (anon key)

---

## soul.md — Padrões de escrita

### Boas práticas
- Ser específico sobre o domínio: "Você é especialista em [domínio X]" é melhor que "Você é útil"
- Listar ações concretas: "Você busca leads no CRM" é melhor que "Você interage com dados"
- Proibições claras: "Nunca deleta registros sem aprovação" é melhor que "Seja cuidadoso"
- Tom operacional: "Responda em 2-3 frases, formato bullet point" é melhor que "Seja conciso"

### Estrutura recomendada (ver `assets/soul_template.md`)
1. Identidade (quem é, para quem trabalha, objetivo)
2. O que faz (lista de ações concretas com verbos)
3. O que nunca faz (proibições específicas)
4. O que requer aprovação (ações de risco)
5. Princípios (4 max, cada um verificável)
6. Tom e estilo (idioma, formato, extensão)
7. Quando não sabe (como lidar com incerteza)
8. Em caso de erro (como comunicar falhas)

---

## Skills — Padrões de escrita

### Trigger claro
O `description` no frontmatter deve ser específico o suficiente para o LLM saber quando ativar:
- Bom: "Qualifica leads de vendas recebidos via Telegram, fazendo 5 perguntas sobre orçamento, prazo, decisor e necessidade"
- Ruim: "Ajuda com vendas"

### Estrutura recomendada (ver `assets/skill_spec_template.md`)
1. Quando usar (triggers concretos)
2. O que precisa ter disponível (tools, dados, contexto)
3. Passo a passo (ações com exemplos)
4. Formato da resposta (como entregar o resultado)
5. Cenários de erro (fallbacks)
6. Exemplo de uso (trigger → execução → resposta)

---

## Memória — Padrões

### MEMORY.md (injetado no context)
Usar para: preferências do agente sobre cada usuário, configurações que afetam comportamento.

```markdown
# Memória do Agente

## Preferências de usuários
- @joao: prefere respostas curtas, estilo direto
- @maria: prefere detalhamento, envia áudio frequentemente

## Ajustes aprendidos
- Quando perguntam sobre preço, sempre mencionar que o valor é sem impostos
- Relatórios semanais devem ser enviados segunda às 9h
```

### Supabase (dados persistentes)
Usar para: histórico de conversas, dados do produto, métricas, logs de ações.

### Workspace (dados temporários)
Usar para: arquivos em processamento, rascunhos, dados de sessão ativa.

---

## systemd — Padrão do service file

```ini
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
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Verificação: `systemctl status openclaw` deve mostrar `active (running)`.

---

## GitHub Actions — Padrão de deploy

```yaml
name: Deploy Agent to VPS
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to VPS
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd ~/projetos/[NOME_AGENTE]
            git pull origin main
            cp -r agents/ ~/.openclaw/agents/
            cp -r skills/ ~/.openclaw/skills/
            systemctl restart openclaw
            echo "Deploy: $(date)"
```

Secrets necessários: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
