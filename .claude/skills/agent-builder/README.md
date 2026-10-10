# Agent Builder Copilot (ABC) v2.0

Skill para Claude Code que atua como copiloto completo na criação de agentes autônomos de IA no ecossistema OpenClaw.

## O que faz

Conduz você da ideia até um agente funcional rodando em produção, passando por 6 modos operacionais:

| Modo | O que faz | O que produz |
|---|---|---|
| **Discovery** | Perguntas estratégicas para entender o agente | Mapa de requisitos validado |
| **PRD** | Consolida discovery em especificação | PRD estruturado + critérios de aceite |
| **Arquitetura** | Define stack, tools, memória, guardrails | Especificação técnica completa |
| **Execução** | Gera todos os arquivos do projeto | Projeto completo no workspace |
| **Infra** | Guia setup de VPS, Supabase, GitHub | Ambiente configurado (supervisionado) |
| **Validação** | Testa e verifica o agente | Agente validado em produção |

## Stack suportada

- **Runtime:** OpenClaw
- **LLM:** Claude (padrão), GPT, Gemini
- **Backend/dados:** Supabase
- **Frontend:** Lovable (rápido) ou Next.js (controle total)
- **Hosting:** VPS Hostinger
- **Versionamento:** GitHub
- **Skills:** ClawHub + Build with Claude

## Instalação rápida

```bash
# Copiar para as skills do Claude Code:
cp -r agent-builder ~/.claude/skills/agent-builder

# Verificar instalação:
claude
# Dentro do Claude Code:
/skills
# Deve listar 'agent-builder'
```

Veja [INSTALL.md](INSTALL.md) para instruções detalhadas.

## Como usar

### Criar um novo agente:
```bash
mkdir ~/projetos/meu-agente
cd ~/projetos/meu-agente
claude
# Dentro do Claude Code, diga:
# "Quero criar um agente que qualifica leads via WhatsApp"
# A skill é ativada automaticamente e inicia o Discovery
```

### Retomar um projeto:
```bash
cd ~/projetos/meu-agente
claude
# O CLAUDE.md do projeto é lido automaticamente
# Diga: "continua de onde paramos"
```

### Ir direto para um modo:
```
"Já tenho o discovery feito, vamos para a arquitetura"
"Como instalo o OpenClaw no VPS?" (vai direto para Infra)
"Gera os arquivos do projeto" (vai direto para Execução)
```

## Exemplos de uso

Veja [examples/example_prompts.md](examples/example_prompts.md) para 4 exemplos completos:
1. Discovery de um agente de qualificação de leads
2. Transição para modo Execução
3. Detecção automática de modo Infra
4. Sessão completa de agente funcional

## Estrutura de arquivos

```
agent-builder/
├── SKILL.md                          # Entry point com 6 modos
├── README.md                         # Este arquivo
├── INSTALL.md                        # Guia de instalação
├── references/
│   ├── question_library.md           # Perguntas por etapa
│   ├── deepening_guide.md            # Técnicas de aprofundamento
│   ├── vps_setup_guide.md            # Setup VPS passo-a-passo
│   ├── tech_decisions.md             # Decisões técnicas com defaults
│   ├── execution_policy.md           # O que pode/não pode executar
│   ├── clawhub_guide.md              # Pesquisa e uso de ClawHub
│   ├── lovable_integration.md        # Quando/como usar Lovable
│   └── openclaw_patterns.md          # Padrões de config OpenClaw
├── assets/
│   ├── soul_template.md              # Template de identidade
│   ├── agent_prd_template.md         # Template de PRD
│   ├── completeness_checklist.md     # Checklist por modo
│   ├── decision_log_template.md      # Log de decisões
│   ├── skill_spec_template.md        # Template de skill custom
│   ├── supabase_schema_base.sql      # Schema SQL base
│   ├── execution_plan_template.md    # Plano de execução
│   ├── infra_handoff_template.md     # Handoff de infraestrutura
│   ├── acceptance_criteria_template.md # Critérios de aceite
│   └── env_example_template.env      # Template de .env
└── examples/
    ├── example_prompts.md            # Exemplos de uso
    └── example_openclaw_project/     # Projeto exemplo completo
```

## 3 Camadas Operacionais

A skill opera com clareza sobre o que faz diretamente e o que guia:

| Camada | O que faz | Exemplo |
|---|---|---|
| **Planejamento** | Conversa, analisa, gera specs | Discovery, PRD, Arquitetura |
| **Execução local** | Cria/edita arquivos no workspace | Gerar soul.md, config.json, scripts |
| **Infra guiada** | Gera comandos, explica, espera confirmação | SSH, deploy, API keys, DNS |

A skill **nunca executa ações de infraestrutura sem supervisão**. Credenciais, deploy e ações irreversíveis sempre passam pelo usuário.
