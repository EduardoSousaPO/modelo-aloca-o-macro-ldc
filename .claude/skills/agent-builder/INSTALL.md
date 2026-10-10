# Como Instalar a Skill Agent Builder no Claude Code

## Passo 1 — Localizar a pasta de skills do Claude Code

```bash
# No terminal, verificar se a pasta já existe:
ls ~/.claude/skills/

# Se não existir, criar:
mkdir -p ~/.claude/skills/
```

## Passo 2 — Copiar a skill

```bash
# Copiar a pasta agent-builder para as skills globais do Claude Code:
cp -r /caminho/para/agent-builder ~/.claude/skills/agent-builder

# Verificar que os arquivos estão corretos:
ls ~/.claude/skills/agent-builder/
# Deve mostrar: SKILL.md  references/  assets/  INSTALL.md
```

## Passo 3 — Verificar a instalação

```bash
# Abrir Claude Code em qualquer pasta:
claude

# Dentro do Claude Code, verificar que a skill aparece:
/skills

# Deve listar 'agent-builder' entre as skills disponíveis
```

## Como usar

### Para criar um novo agente:

```bash
# 1. Criar pasta para o projeto do agente
mkdir ~/projetos/meu-agente
cd ~/projetos/meu-agente

# 2. Abrir Claude Code dentro dessa pasta
claude

# 3. Chamar a skill
/agent-builder

# A skill vai conduzir você do discovery até o agente em produção
```

### Para retomar um projeto existente:

```bash
# 1. Entrar na pasta do projeto
cd ~/projetos/meu-agente

# 2. Abrir Claude Code
claude

# 3. Claude Code vai ler o CLAUDE.md do projeto automaticamente
# 4. Chamar a skill para continuar de onde parou
/agent-builder
```

## Estrutura de arquivos da skill

```
~/.claude/skills/agent-builder/
├── SKILL.md                          # Entry point — instruções completas
├── references/
│   ├── question_library.md           # Biblioteca de perguntas por etapa
│   ├── deepening_guide.md            # Técnicas de aprofundamento
│   ├── vps_setup_guide.md            # Guia de instalação no Hostinger
│   └── tech_decisions.md             # Catálogo de decisões técnicas
└── assets/
    ├── agent_prd_template.md         # Template de PRD para agentes
    ├── soul_template.md              # Template de SOUL.md
    ├── skill_spec_template.md        # Template de skill custom
    ├── supabase_schema_base.sql      # Schema SQL base
    ├── completeness_checklist.md     # Checklist de validação
    └── decision_log_template.md      # Log de decisões
```
