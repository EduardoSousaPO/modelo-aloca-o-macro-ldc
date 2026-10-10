# Guias Detalhados dos Modos Operacionais

Leia a seção correspondente ao modo que você está executando.

---

## MODO DISCOVERY (detalhes)

*Requer também: `references/question_library.md` e `references/deepening_guide.md`*

Objetivo: entender completamente o agente que o usuário quer criar. Nenhum arquivo é criado neste modo.

### Etapa 1 — Caso de uso e contexto

**Pergunta de abertura:**
> "Descreva o agente que quer criar: o que ele faz, quem usa, e qual problema resolve. Não se preocupe com tecnologia ainda."

Escute sem interromper. Classifique internamente a maturidade da ideia e adapte.

**Sinais de alerta:**
- Descreve funcionalidades de software → "Descreva o que o **agente faz**, não o que o sistema tem"
- Escopo muito amplo → "Se tivesse que escolher a coisa mais importante que ele faz, qual seria?"

### Etapa 2 — Usuário final e canal

Perguntas-guia (escolha 2-3 da question_library):
- Quem interage? Descreva uma pessoa real típica.
- Em que situação ela aciona o agente?
- Precisa ser na hora ou pode levar minutos?
- Sabe que está falando com IA?
- Mais de um perfil de usuário?

### Etapa 3 — Ações concretas do agente

Esta é a etapa mais crítica — define tools, approvals e guardrails.

- Liste as 3-5 coisas que o agente FAZ (não apenas responde)
- Para cada ação: texto ou ação real no mundo?
- Quais são automáticas vs. sob demanda?
- Se errar, causa dano real?

Ao final, construa internamente: ação → tool → risco → precisa de approval?

### Etapa 4 — Fontes de dados e integrações

- Acessa sistemas externos? Quais?
- Lê, escreve, ou ambos?
- Precisa lembrar entre conversas?
- Dados sensíveis envolvidos?

Se dados sensíveis + sem menção a proteção → sinalize imediatamente.

### Etapa 5 — Restrições e sensibilidades

- O que o agente NUNCA pode fazer autonomamente?
- Para quais ações quer aprovação antes?
- 24/7 ou horário específico?
- Restrições de idioma, tom, formato?

**Checkpoint do Discovery:**
```
"Aqui está o que capturei sobre o seu agente:
- O que faz: [resumo]
- Para quem: [persona]
- Canal: [canal preferido]
- Ações concretas: [lista]
- Integra com: [sistemas] ou 'nenhum por enquanto'
- Nunca pode: [lista]
- Requer sua aprovação: [lista]

O que está errado ou faltando?"
```

Após aprovação → anuncie transição para MODO PRD.

---

## MODO PRD (detalhes)

*Requer também: `assets/agent_prd_template.md` e `assets/acceptance_criteria_template.md`*

Objetivo: transformar o discovery em um PRD estruturado que serve como contrato do que será construído.

### O que o PRD contém

Preencha o template `agent_prd_template.md` com todos os dados do Discovery:
1. Resumo do agente (uma frase + contexto)
2. Problema e motivação
3. Usuário final (persona detalhada)
4. Comportamentos do agente (tabela com ID, trigger, ação, output, prioridade)
5. Ações executadas (mapeadas para tools OpenClaw)
6. Integrações e MCPs
7. Estratégia de memória
8. Stack técnica
9. Tool policy
10. Guardrails
11. Skills necessárias
12. Escopo MVP com MoSCoW
13. Métricas
14. Riscos
15. Critérios de aceite

### Critérios de aceite

Para cada comportamento Must/Should, defina:
- Condição de sucesso verificável
- Como testar (manual ou automatizado)
- Resultado esperado específico

Use `assets/acceptance_criteria_template.md` para o formato.

### Escopo MVP com MoSCoW

Aplique priorização rigorosa:
- **Must** — agente não faz sentido sem isso
- **Should** — melhora muito, não bloqueia lançamento
- **Could** — desejável, aguarda feedback real
- **Won't** — explicitamente fora agora, com motivo

**Checkpoint do PRD:**
Apresente o PRD completo e pergunte: "Esse PRD reflete corretamente o que quer construir? Algo para mudar antes de definirmos a arquitetura?"

Após aprovação → anuncie transição para MODO ARQUITETURA.

---

## MODO ARQUITETURA (detalhes)

*Requer também: `references/tech_decisions.md`, `references/clawhub_guide.md`, e `references/lovable_integration.md` se frontend usar Lovable.*

Objetivo: definir todas as decisões técnicas e apresentá-las como recomendações (não perguntas abertas).

### Etapa 6 — LLM e canal

Apresente recomendação com justificativa e custo estimado. Use os defaults de `tech_decisions.md` como base.

### Etapa 7 — Tool policy

Traduza ações do PRD para tools OpenClaw:

| Ação de negócio | Tool | Risco | Approval? |
|---|---|---|---|
| Buscar na web | web_search / web_fetch | Baixo | Não |
| Ler arquivo | read | Baixo | Não |
| Criar/editar arquivo | write, edit | Médio | Opcional |
| Executar comando | exec | Alto | Sim |
| Controlar navegador | browser | Alto | Situacional |
| Enviar mensagem proativa | message | Médio | Para bulk |
| Agendar tarefa | cron | Médio | Não |
| Gerar imagem | image | Baixo | Não |
| Ler/escrever banco | MCP supabase | Médio | Para deletes |

### Etapa 8 — Memória

Apresente proposta padrão: MEMORY.md para preferências do agente, Supabase para histórico e dados do produto, Workspace files para dados temporários. DREAMS opcional para v2.

### Etapa 9 — Guardrails

Monte automaticamente com base nas restrições do Discovery: SOUL.md (soft), Tool policy (hard), Allowlist de usuários, Sandbox Docker se exec habilitado.

### Etapa 10 — Skills

*Leia `references/clawhub_guide.md` antes desta etapa.*

1. Pesquise skills relevantes no ClawHub para o caso de uso
2. Avalie se reutilizar vs. criar do zero
3. Considere componentes do Build with Claude
4. Apresente mapa: skills do ClawHub + skills custom a criar

### Etapa 11 — Frontend

Apresente a recomendação baseada no caso de uso:
- **Lovable** (padrão) → para frontend rápido, visual, sem muito controle técnico
- **Next.js via Claude Code** → para controle total, SSR, lógica complexa
- **Sem frontend no MVP** → se o agente funciona só via canal (Telegram/WhatsApp)

*Leia `references/lovable_integration.md` se Lovable for escolhido.*

### Etapa 12 — Infraestrutura e escopo MVP

Pergunte apenas o que não tem default (VPS existe? Supabase existe? GitHub existe?). Apresente defaults assumidos. Defina MoSCoW do MVP.

**Checkpoint da Arquitetura:**
```
"Especificação técnica completa:

LLM: [modelo] | Canal: [canal]
Tools: [lista] | Com approval: [lista]
Skills: ClawHub [lista] + Custom [lista]
Memória: MEMORY.md + Supabase
Guardrails: [resumo]
Frontend: [Lovable / Next.js / sem frontend]
Infra: Hostinger VPS + Supabase + GitHub
MVP: [lista Must]

Posso gerar os arquivos do projeto?"
```

Após aprovação → anuncie transição para MODO EXECUÇÃO.

---

## MODO EXECUÇÃO (detalhes)

*Requer também: `references/execution_policy.md`, `references/openclaw_patterns.md` e templates de `assets/`.*

Objetivo: gerar todos os arquivos do projeto dentro do workspace do Claude Code.

### Plano de execução

Antes de criar qualquer arquivo, apresente o plano:
```
"Vou criar os seguintes arquivos:
1. [arquivo] — [o que contém]
2. [arquivo] — [o que contém]
...
Confirma?"
```

### Estrutura de diretórios gerada

```
[nome-do-agente]/
├── CLAUDE.md                    # Contexto para futuras sessões
├── README.md
├── agents/
│   └── [nome]/
│       ├── soul.md              # Use assets/soul_template.md
│       ├── config.json
│       └── memory.md.template
├── skills/
│   └── [nome-skill]/
│       └── SKILL.md             # Use assets/skill_spec_template.md
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql  # Use assets/supabase_schema_base.sql
├── .github/
│   └── workflows/
│       └── deploy.yml
├── .env.example                 # Use assets/env_example_template.env
├── decision_log.md              # Use assets/decision_log_template.md
└── .gitignore
```

### CLAUDE.md (crítico para continuidade)

Gere com: nome do agente, todas as decisões tomadas, stack, onde cada coisa está, o que foi feito, o que falta. Garante retomada em sessões futuras.

### Ordem de geração

1. Estrutura de diretórios
2. CLAUDE.md
3. soul.md (de `assets/soul_template.md`)
4. config.json
5. SKILL.md de cada skill custom (de `assets/skill_spec_template.md`)
6. SQL schema (de `assets/supabase_schema_base.sql`)
7. .gitignore
8. .env.example
9. decision_log.md (de `assets/decision_log_template.md`)
10. deploy.yml
11. README.md do projeto

**Checkpoint da Execução:**
```
"Arquivos criados:
- [lista com descrição de uma linha cada]

Próximo passo: configurar infraestrutura (VPS, Supabase, GitHub).
Quer continuar para o modo Infra?"
```

Após aprovação → anuncie transição para MODO INFRA.

---

## MODO INFRA (detalhes)

*Requer também: `references/vps_setup_guide.md` (leia antes de começar) e `assets/infra_handoff_template.md`.*

Objetivo: guiar o usuário na configuração de infraestrutura. **Esta é Camada 3 — tudo é supervisionado.**

### Regras deste modo

1. **Nunca assuma credenciais** — sempre pergunte
2. **Nunca execute SSH** — gere os comandos e explique
3. **Gere comandos exatos** com placeholders claros: `[IP_DO_VPS]`, `[SUA_API_KEY]`
4. **Pare antes de cada bloco** — "Pronto para executar estes comandos no VPS?"
5. **Verifique resultado** — após cada bloco, peça o output para confirmar sucesso

### Sequência de setup

**Bloco A — VPS Hostinger:**
1. Verificar estado atual (Passo 0 do vps_setup_guide)
2. Preparar servidor (Node.js, dependências)
3. Instalar OpenClaw
4. Configurar .env com credenciais (usuário fornece, skill gera o arquivo)
5. Copiar arquivos do agente (via GitHub ou SCP)
6. Configurar systemd
7. Auditoria de segurança

**Bloco B — Canal de comunicação:**
1. Telegram: guiar criação do bot no BotFather
2. WhatsApp: alertar sobre processo de aprovação Meta
3. WebChat: configurar WebSocket no gateway

**Bloco C — Supabase:**
1. Guiar criação do projeto (região sa-east-1)
2. Copiar URL e keys
3. Rodar migration
4. Verificar RLS
5. Instalar MCP do Supabase no agente

**Bloco D — Frontend (se aplicável):**
- **Se Lovable:** Leia `references/lovable_integration.md` e guie a criação do projeto
- **Se Next.js:** Guie `create-next-app` + instalação de dependências Supabase

**Bloco E — GitHub + CI/CD:**
1. Inicializar repositório
2. Configurar remote
3. Configurar GitHub Secrets (VPS_HOST, VPS_USER, VPS_SSH_KEY)
4. Verificar deploy automático

**Checkpoint da Infra:**
```
"Infraestrutura configurada. Confirme:
- [ ] OpenClaw rodando (systemctl status openclaw = active)
- [ ] Canal conectado (bot responde)
- [ ] Supabase conectado (MCP testado)
- [ ] .env não está no repositório
- [ ] security audit sem erros críticos
- [ ] GitHub Actions configurado

Tudo ok? Vamos para validação."
```

Após confirmação → anuncie transição para MODO VALIDAÇÃO.

---

## MODO VALIDAÇÃO (detalhes)

*Requer também: `assets/completeness_checklist.md` e `assets/acceptance_criteria_template.md`.*

Objetivo: confirmar que o agente funciona end-to-end e atende os critérios de aceite do PRD.

### Verificação em 4 blocos

**Bloco 1 — Agente:**
- [ ] soul.md define identidade, princípios, proibições e tom
- [ ] config.json tem tool policy correta
- [ ] Todas as skills custom têm SKILL.md completo
- [ ] MEMORY.md template criado

**Bloco 2 — Segurança:**
- [ ] `openclaw security audit` sem erros críticos
- [ ] .env não está no repositório
- [ ] RLS habilitado no Supabase
- [ ] Ações com approval configuradas

**Bloco 3 — Infraestrutura:**
- [ ] OpenClaw via systemd com Restart=always
- [ ] Canal conectado e testado
- [ ] Supabase conectado (MCP funcional)
- [ ] GitHub Actions deployando

**Bloco 4 — Teste funcional:**
- [ ] Agente responde no canal configurado
- [ ] Fluxo principal MVP funciona end-to-end (happy path)
- [ ] Agente lida com entrada inválida
- [ ] Ações com approval disparam corretamente
- [ ] Critérios de aceite do PRD verificados

### Smoke tests sugeridos

1. Enviar mensagem simples no canal → agente responde
2. Solicitar ação principal do MVP → agente executa
3. Enviar input inválido → agente trata graciosamente
4. Testar ação com approval → notificação chega
5. Verificar custo por interação → dentro do estimado

**Se tudo OK:** Agente em produção. Atualize decision_log.md e CLAUDE.md com estado final.

**Se algo falhou:** Identifique o problema, volte ao modo apropriado (Execução ou Infra), resolva, e re-valide.
