# Guia de Aprofundamento de Respostas — Agent Builder

Adaptado do consultor-prd para o domínio de agentes autônomos.

---

## Quando aprofundar

Aprofunde quando a resposta:
- Usa termos vagos: "os usuários", "várias integrações", "vai ter automação"
- Não tem exemplos concretos: descreve conceitos mas não cenários reais
- Não tem números: "muitos", "bastante", "às vezes"
- Contradiz algo anterior
- Evita decisão: "isso a gente vê depois", "depende"
- É uma linha para pergunta complexa

**Regra de ouro:** máximo 2 rodadas de aprofundamento por tópico. Se não conseguir mais detalhe, registre como "ponto em aberto" e siga.

---

## Técnicas

### 1. Concretização
**Quando:** resposta genérica sobre o que o agente faz

**Como:**
- "Me descreva uma conversa real que você imagina entre o usuário e o agente. Passo a passo."
- "Imagine que estou usando o agente agora. O que eu digito? O que ele responde? O que acontece depois?"
- "Me dê um exemplo de tarefa real que esse agente já resolveria hoje."

**Exemplo de uso:**
- Usuário: "O agente vai atender clientes"
- Você: "Me descreva uma atendimento específico. O cliente chegou com qual problema? O agente fez o quê exatamente? Como terminou?"

---

### 2. Quantificação
**Quando:** números ausentes em estimativas de volume, frequência ou escala

**Como:**
- "Quando diz 'muitos usuários', estamos falando de 10, 100 ou 10.000?"
- "Com que frequência isso acontece? Por dia, por semana?"
- "Se tivesse que chutar: quantas interações o agente vai ter no primeiro mês?"
- "Qual o tamanho típico de uma conversa? 2 mensagens, 10, 20?"

**Por que importa para agentes:** volume determina custo de LLM, infraestrutura do VPS e tier do Supabase.

---

### 3. Comparação por referência
**Quando:** descrição abstrata que pode significar coisas muito diferentes

**Como:**
- "É mais parecido com [A] ou com [B]? (simples vs. complexo)"
- "Quando diz 'painel de controle', está pensando em algo como um dashboard de métricas ou uma tela de configuração?"
- "O nível de autonomia do agente: ele decide tudo sozinho (como um assistente), ou sempre pede confirmação (como um formulário inteligente)?"

**Exemplos específicos para agentes:**
- "O agente é reativo (responde quando perguntado) ou proativo (manda mensagem por conta própria)?"
- "É um agente de conversa (chat) ou de execução (roda tarefas em background)?"

---

### 4. Consequenciação
**Quando:** decisão que parece impulsiva ou com implicações não óbvias

**Como:**
- "Se deixarmos o agente executar [ação X] sem aprovação, isso significa que [consequência Y]. Você está ok com isso?"
- "Essa escolha implica que o agente vai [Z] sempre que [condição]. Faz sentido?"
- "Se o volume triplicar em 3 meses, essa abordagem ainda funciona?"

**Exemplos específicos:**
- "Habilitar a tool `exec` sem approval significa que o agente pode rodar qualquer comando no servidor. Você quer configurar uma allowlist de comandos permitidos?"
- "Usar WhatsApp como canal principal significa depender da aprovação da Meta. O que acontece com o projeto enquanto essa aprovação não vem?"

---

### 5. Contrafactual
**Quando:** funcionalidade ou requisito que parece desnecessário no MVP

**Como:**
- "E se NÃO tivéssemos essa funcionalidade no MVP, o que aconteceria?"
- "Se tirarmos isso do escopo, quem reclama? Com que intensidade?"
- "O agente ainda faz sentido sem isso?"

**Exemplos específicos:**
- "Memória semântica avançada (busca vetorial) é realmente necessária no MVP? Ou MEMORY.md simples já resolve por enquanto?"
- "A interface web (Next.js) é necessária para o piloto, ou o agente pode funcionar só via Telegram inicialmente?"

---

### 6. Decomposição
**Quando:** resposta grande e vaga ("vai ter um sistema de notificações", "precisa de integrações")

**Como:**
- "Quando diz 'integrações', quais sistemas especificamente? Vamos listar um por um."
- "Esse módulo tem sub-funcionalidades? Quais são as partes?"
- "De tudo que mencionou, qual é a parte mais simples que já resolve 80% do problema?"

---

### 7. Perspectiva do risco
**Quando:** decisão técnica com implicação de segurança ou custo oculto

**Como:**
- "Se o agente tiver acesso a [sistema X], o que acontece se a autenticação vazar?"
- "Essa integração com [API Y] tem custo por uso? Qual o limite antes de virar problema?"
- "Se o VPS cair, o que o usuário experimenta? Mensagem de erro? Silêncio?"

---

## Fluxo de decisão

```
Usuário responde algo
  ├── Clara e suficiente? → Aceite e avance
  ├── Vaga / genérica? → Concretização ou Quantificação
  ├── Termos ambíguos? → Comparação por referência
  ├── Decisão impulsiva? → Consequenciação
  ├── Prioridade questionável? → Contrafactual
  ├── Resposta muito grande? → Decomposição
  └── Implicação de risco? → Perspectiva do risco
```

---

## Quando NÃO aprofundar

- A resposta é clara o suficiente para tomar a próxima decisão
- Já fez 2 rodadas sobre o mesmo tópico sem mais detalhes
- O detalhe faltante é de baixo impacto (pode ser um default ou ajustado depois)
- O usuário demonstra que não sabe a resposta e isso é legítimo — registre como "ponto em aberto"

Ao registrar como ponto em aberto: "Não precisamos resolver isso agora. Vou registrar como decisão pendente e continuamos. Você pode responder quando tiver clareza."
