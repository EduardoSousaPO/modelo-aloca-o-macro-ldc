# Exemplos de Uso — Agent Builder Copilot

4 exemplos concretos de como usar a skill ABC em sessões reais.

---

## Exemplo 1 — Discovery de um agente de qualificação de leads

O usuário inicia com uma ideia e a skill conduz o Discovery completo.

### O que o usuário diz:
```
"Quero criar um agente que qualifica leads de vendas que chegam pelo WhatsApp 
da minha empresa de energia solar. Hoje eu faço isso manualmente e demoro 
muito pra responder todo mundo."
```

### O que a skill faz:

**1. Detecta modo: DISCOVERY**

**2. Apresentação:**
> Sou o ABC, seu copiloto de construção de agentes. Vou te ajudar a transformar essa ideia num agente funcional rodando em produção. Vamos começar entendendo melhor o caso de uso.

**3. Etapa 1 — Caso de uso (já tem bastante contexto):**
> Entendi: agente de qualificação de leads via WhatsApp para energia solar. Ótimo ponto de partida. Me ajuda com um detalhe: quando um lead chega, quais informações você precisa coletar dele antes de decidir se vale um contato comercial?

**4. Etapa 2 — Usuário final:**
> Quem é esse lead típico? É pessoa física querendo painel solar em casa, ou empresa? E do seu lado, é só você atendendo ou tem uma equipe de vendas que recebe os leads qualificados?

**5. Etapa 3 — Ações concretas:**
> Então o agente precisa: (1) responder o lead no WhatsApp, (2) fazer perguntas de qualificação, (3) salvar as respostas, (4) classificar o lead, e (5) encaminhar para o vendedor se for qualificado. Dessas ações, quais precisam de sua aprovação antes?

**6. Etapa 4 — Integrações:**
> Você usa algum CRM hoje? As informações dos leads ficam numa planilha, sistema, ou só no WhatsApp mesmo?

**7. Etapa 5 — Restrições:**
> O que o agente nunca pode fazer? Por exemplo: dar preço sem sua aprovação, prometer prazo de instalação, responder sobre financiamento?

**8. Checkpoint:**
```
Aqui está o que capturei sobre o seu agente:
- O que faz: qualifica leads de energia solar via WhatsApp
- Para quem: pessoas interessadas em energia solar (residencial + PME)
- Canal: WhatsApp (desenvolvimento em Telegram enquanto aprova Business)
- Ações concretas: responder lead, fazer 5 perguntas de qualificação, salvar no Supabase, classificar (quente/morno/frio), encaminhar qualificados para vendedor via Telegram
- Integra com: Supabase (banco de leads), Telegram (notificação para vendedor)
- Nunca pode: dar preço final, prometer prazo, falar de financiamento
- Requer aprovação: nenhuma ação precisa de approval (só qualifica e encaminha)

O que está errado ou faltando?
```

---

## Exemplo 2 — Transição para modo Execução

O usuário já fez Discovery, PRD e Arquitetura. Agora quer os arquivos.

### O que o usuário diz:
```
"Tudo certo com a arquitetura. Gera os arquivos do projeto."
```

### O que a skill faz:

**1. Detecta modo: EXECUÇÃO**

**2. Anuncia transição:**
> Entrando no modo Execução. Neste modo eu vou criar todos os arquivos do projeto no workspace atual. Nenhuma credencial será usada, nenhum serviço externo será acessado.

**3. Apresenta plano de execução:**
```
Vou criar os seguintes arquivos:

1. CLAUDE.md — contexto do projeto para futuras sessões
2. agents/lead-qualifier/soul.md — identidade do agente
3. agents/lead-qualifier/config.json — configuração técnica
4. agents/lead-qualifier/memory.md.template — template de memória
5. skills/qualify-lead/SKILL.md — skill de qualificação
6. supabase/migrations/001_initial_schema.sql — schema do banco
7. .github/workflows/deploy.yml — CI/CD
8. .env.example — template de variáveis
9. decision_log.md — registro de decisões
10. .gitignore — proteção de arquivos sensíveis
11. README.md — documentação do projeto

Confirma? Posso criar todos agora.
```

**4. Após confirmação, gera cada arquivo usando os templates e dados do discovery.**

**5. Checkpoint:**
```
Arquivos criados:
- CLAUDE.md — contexto completo do projeto
- soul.md — agente "Sol", especialista em energia solar, tom amigável
- config.json — Claude Sonnet 4.6, tools: read, write, web_search, message
- qualify-lead SKILL.md — 5 perguntas de qualificação, classificação automática
- SQL schema — tabelas: profiles, conversations, messages, agent_tasks, leads
- deploy.yml — CI/CD para VPS via GitHub Actions
- .env.example — template com todas as variáveis necessárias
- decision_log.md — 12 decisões registradas

Próximo passo: configurar infraestrutura (VPS, Supabase, Telegram).
Quer continuar para o modo Infra?
```

---

## Exemplo 3 — Detecção automática de modo Infra

O usuário pede algo que envolve credenciais/VPS e a skill muda automaticamente.

### O que o usuário diz:
```
"Como configuro a API key do Claude no servidor?"
```

### O que a skill faz:

**1. Detecta modo: INFRA (envolve credenciais + servidor)**

**2. Anuncia:**
> Essa é uma etapa de infraestrutura (Camada 3). Vou te guiar passo a passo, mas não vou executar nada — você executa os comandos no seu terminal SSH.

**3. Gera comandos exatos com placeholders:**
```
Configurar API key do Claude no VPS

Pré-condição: já tem acesso SSH ao VPS e o OpenClaw instalado.

1. Conecte ao VPS:
   ssh [USUARIO_SSH]@[IP_DO_VPS]

2. Edite o arquivo de ambiente:
   nano ~/.openclaw/.env

3. Adicione ou altere esta linha:
   ANTHROPIC_API_KEY=[SUA_API_KEY_AQUI]

4. Salve e proteja o arquivo:
   chmod 600 ~/.openclaw/.env

5. Reinicie o agente:
   systemctl restart openclaw

6. Verifique:
   systemctl status openclaw
   # Deve mostrar: active (running)

Se der erro "API key invalid", verifique:
- A key começa com sk-ant-?
- Não tem espaços extras?
- A conta Anthropic tem crédito?

Me envie o output do status para confirmar.
```

**4. Espera o usuário executar e trazer o resultado antes de avançar.**

---

## Exemplo 4 — Sessão completa até agente funcional

Resumo de uma sessão completa passando por todos os modos.

### Fluxo da sessão:

```
DISCOVERY (15 min)
├── Usuário: "Quero um agente que responde FAQ do meu SaaS via Telegram"
├── ABC: 5 perguntas estratégicas em 3 mensagens
├── ABC: checkpoint com resumo validado
└── Resultado: mapa de requisitos completo

PRD (5 min)
├── ABC: gera PRD preenchido automaticamente
├── ABC: apresenta critérios de aceite
├── Usuário: aprova com um ajuste
└── Resultado: PRD + acceptance criteria

ARQUITETURA (5 min)
├── ABC: apresenta recomendações (Claude Haiku 4.5, Telegram, sem exec)
├── ABC: pesquisa skills no ClawHub
├── ABC: recomenda Lovable para dashboard
├── Usuário: aprova
└── Resultado: spec técnica completa

EXECUÇÃO (3 min)
├── ABC: apresenta plano de 10 arquivos
├── Usuário: confirma
├── ABC: gera todos os arquivos no workspace
└── Resultado: projeto completo com soul.md, config.json, skills, schema

INFRA (20 min)
├── ABC: gera handoff de infraestrutura
├── Bloco A: guia setup VPS (usuário executa, ABC verifica)
├── Bloco B: guia criação do bot Telegram (usuário executa)
├── Bloco C: guia Supabase (usuário executa migration)
├── Bloco D: guia Lovable (usuário cria dashboard)
├── Bloco E: guia GitHub + CI/CD
└── Resultado: tudo configurado e rodando

VALIDAÇÃO (5 min)
├── ABC: executa checklist de 20 itens
├── 5 smoke tests passam
├── Critérios de aceite verificados
├── ABC: atualiza CLAUDE.md e decision_log
└── Resultado: agente em produção ✓
```

### Total: ~53 minutos de ideia a agente funcional

**O que ficou no workspace:**
```
meu-faq-agent/
├── CLAUDE.md
├── README.md
├── agents/faq-bot/soul.md
├── agents/faq-bot/config.json
├── skills/answer-faq/SKILL.md
├── supabase/migrations/001_initial_schema.sql
├── .github/workflows/deploy.yml
├── .env.example
├── decision_log.md
└── .gitignore
```

**O que está rodando no VPS:**
- OpenClaw com o agente faq-bot ativo
- Bot do Telegram respondendo FAQs
- Supabase armazenando conversas
- Lovable exibindo dashboard de métricas
- GitHub Actions deployando automaticamente
