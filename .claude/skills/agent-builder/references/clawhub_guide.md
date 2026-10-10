# Guia de Uso do ClawHub — Agent Builder Copilot

O ClawHub é o marketplace de skills, plugins e componentes para agentes OpenClaw. Use este guia durante o Modo Arquitetura (Etapa 10) para pesquisar, avaliar e instalar skills existentes.

---

## O que é o ClawHub

ClawHub é o ecossistema de componentes reutilizáveis para OpenClaw:
- **Skills** — comportamentos que ensinam o agente a agir em situações específicas
- **Plugins** — extensões que adicionam capacidades ao runtime (canais, provedores, integrações)
- **Templates** — projetos base pré-configurados para casos de uso comuns

URL: https://clawhub.com (ou o endereço atual do registry)

---

## Quando pesquisar no ClawHub

Pesquise ANTES de criar uma skill custom se o comportamento desejado é:
- Comum (atendimento, vendas, suporte, scheduling)
- Genérico (busca web, envio de email, geração de relatório)
- Relacionado a integração (CRM, ERP, calendário, redes sociais)

Crie do zero SOMENTE quando:
- O comportamento é específico do negócio do usuário
- Nenhuma skill existente cobre o caso de uso
- As skills existentes não são adaptáveis

---

## Como pesquisar skills

### Via CLI do OpenClaw
```bash
# Buscar por palavra-chave
openclaw skills search [termo]

# Exemplos:
openclaw skills search "lead qualification"
openclaw skills search "customer support"
openclaw skills search "telegram"
openclaw skills search "scheduling"
openclaw skills search "email"

# Ver detalhes de uma skill
openclaw skills info [slug-da-skill]

# Listar skills instaladas
openclaw skills list
```

### Via site do ClawHub
Navegue por categorias ou busque por caso de uso. Cada skill tem:
- Descrição do que faz
- Tools necessárias
- Compatibilidade de versão
- Avaliações da comunidade
- Código-fonte (open source)

---

## Como avaliar uma skill do ClawHub

Antes de instalar uma skill, verifique:

### 1. Compatibilidade
- A skill requer tools que o agente tem habilitadas?
- A skill requer MCPs que o agente usa?
- A versão do OpenClaw é compatível?

### 2. Segurança
- A skill pede permissões excessivas? (ex: `exec` para algo que não precisa)
- O código-fonte está disponível para revisão?
- A skill tem avaliações positivas da comunidade?
- Quando foi atualizada pela última vez?

### 3. Adequação
- A skill resolve o problema do agente ou é similar mas não serve?
- A skill é adaptável (pode ser customizada) ou é rígida?
- A skill tem documentação clara de como usar?

### 4. Trade-off: instalar vs. criar

| Fator | Instalar do ClawHub | Criar custom |
|---|---|---|
| Tempo | Minutos | Horas |
| Manutenção | Atualizada pela comunidade | Você mantém |
| Personalização | Limitada ao que a skill expõe | Total |
| Confiabilidade | Testada por outros | Você testa |
| Especificidade | Genérica | Exata para o caso de uso |

**Regra prática:** se a skill do ClawHub cobre 80%+ do comportamento desejado, instale e adapte. Se cobre menos de 50%, crie do zero.

---

## Como instalar e configurar

```bash
# Instalar
openclaw skills install [slug-da-skill]

# Verificar instalação
openclaw skills list

# Auditoria de segurança após instalação
openclaw security audit

# Se a skill precisa de configuração adicional:
# Leia a documentação da skill para variáveis de ambiente ou configs necessárias
```

---

## Skills comuns por caso de uso

### Atendimento ao cliente
- Busque: "customer support", "helpdesk", "ticket management"
- Tools típicas: read, write, web_search, message, MCP de CRM

### Vendas e qualificação de leads
- Busque: "lead qualification", "sales assistant", "crm integration"
- Tools típicas: read, write, web_search, message, MCP de CRM

### Automação de tarefas
- Busque: "task automation", "scheduling", "cron", "workflow"
- Tools típicas: exec, cron, read, write, message

### Pesquisa e análise
- Busque: "research", "web scraping", "data analysis", "report"
- Tools típicas: web_search, web_fetch, read, write, browser

### Comunicação
- Busque: "email", "notification", "telegram", "whatsapp"
- Tools típicas: message, MCP de email

---

## Build with Claude

Além do ClawHub, considere o Build with Claude (buildwithclaude.com ou recurso equivalente) para:
- Componentes de interface para dashboards e painéis
- Templates de projetos com Supabase + autenticação
- Padrões de integração Claude API
- Exemplos de agentes funcionais

### Quando usar Build with Claude vs. ClawHub

| Build with Claude | ClawHub |
|---|---|
| Componentes de frontend/UI | Skills de comportamento do agente |
| Patterns de integração API | Plugins de runtime |
| Templates de projeto completo | Componentes individuais |
| Foco em Claude como LLM | Agnóstico de LLM |

**Na prática:** Use ClawHub para skills do agente e Build with Claude para inspiração de arquitetura e componentes de frontend.

---

## Apresentação ao usuário

No Modo Arquitetura (Etapa 10), apresente as skills assim:

```
"Para o seu agente, identifiquei estas opções:

Skills do ClawHub (prontas para instalar):
- [slug] → [o que faz] — compatível com suas tools
- [slug] → [o que faz] — requer [tool adicional]

Skills custom (vou criar no projeto):
- [nome] → [o que ensina o agente] — não encontrei equivalente no ClawHub

Quer que eu pesquise mais algum comportamento específico?"
```
