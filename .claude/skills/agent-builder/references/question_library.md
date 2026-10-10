# Biblioteca de Perguntas — Agent Builder

Perguntas organizadas por etapa. Selecione 2-3 por mensagem — nunca todas de uma vez.

---

## Etapa 1 — Caso de uso e contexto

### Abertura
- Me conte sobre o agente que quer criar. O que ele faz, quem usa, qual problema resolve?
- De onde surgiu essa ideia? O que motivou?
- Em uma frase: o que esse agente FAZ para o usuário? (ex: "qualifica leads de vendas", "responde suporte", "organiza agenda")
- Existe alguma automação que você faz hoje manualmente que esse agente vai substituir?
- Já viu algum agente parecido funcionando? O que faria diferente?

### Clarificação de escopo
- Isso é um agente para uso interno (sua equipe) ou externo (seus clientes)?
- O agente vai ter apenas um propósito central ou múltiplos?
- É para validar uma ideia (protótipo) ou já tem usuários esperando?

---

## Etapa 2 — Usuário final e canal

### Sobre o usuário
- Descreva uma pessoa real típica que vai usar esse agente. (cargo, contexto, dia a dia)
- Em que momento do dia ou da semana ela interage com o agente?
- Qual o nível técnico? Sabe que está falando com uma IA?
- Ela está num contexto urgente (resolvendo problema) ou de rotina (consulta diária)?
- Há mais de um perfil? (ex: vendedor + gerente; cliente + atendente)

### Sobre o canal
- Onde essa pessoa está quando precisa do agente? (no celular, no computador, no escritório?)
- Já usa WhatsApp para trabalho? Telegram? Algum chat interno?
- Existe já uma interface (site, app, sistema) onde o agente poderia aparecer?
- O agente vai ser o único canal ou complementa algo que já existe?

---

## Etapa 3 — Ações concretas do agente

### Mapeamento de ações
- Liste as 3-5 coisas que o agente FAZ (não apenas fala). Ex: "busca no CRM", "envia email", "cria registro", "posta no sistema"
- Para cada ação: é uma resposta de texto ou uma ação real que acontece em algum sistema?
- Quais dessas ações o agente faz por conta própria vs. apenas quando o usuário pede?
- Tem alguma ação que acontece em horário programado? (ex: relatório toda segunda)

### Nível de risco das ações
- Se o agente errar em alguma ação, o que de pior pode acontecer?
- Existe alguma ação que é irreversível? (ex: deletar, publicar, transferir)
- Para quais ações você quer ter a palavra final antes do agente executar?
- Já aconteceu alguma vez de um bot ou automação fazer algo errado que causou problema? O que foi?

### Frequência e volume
- Com que frequência essas ações acontecem? (dezenas por dia, centenas, raramente)
- Em pico de uso, quantas interações simultâneas espera?

---

## Etapa 4 — Fontes de dados e integrações

### Sistemas externos
- O agente precisa consultar algum sistema para responder? (CRM, ERP, banco de dados, planilha, API)
- Ele precisa escrever ou atualizar algum sistema após executar uma tarefa?
- Tem alguma API que já usa hoje que o agente vai precisar acessar?
- Existe algum dado que vem de fora (webhook, feed, email) que dispara o agente?

### Dados internos
- Tem alguma base de conhecimento, FAQ ou documentação que o agente precisa consultar?
- Existe um histórico de atendimentos/interações que deve ser aproveitado?
- Há dados que devem ser lidos de uma planilha ou arquivo específico?

### Memória e contexto
- O agente precisa lembrar de conversas anteriores com o mesmo usuário?
- Precisa lembrar de preferências individuais de cada usuário?
- Existe informação de contexto que muda ao longo do tempo? (ex: preços, estoque, promoções)

### Dados sensíveis
- Algum dado envolvido é pessoal ou sensível? (nome completo, CPF, financeiro, saúde, localização)
- Há obrigação legal de proteger esses dados? (LGPD, setores regulados)
- Quem pode ter acesso aos dados gerados pelo agente?

---

## Etapa 5 — Restrições e sensibilidades

### O que o agente não pode fazer
- Existe alguma ação que o agente NUNCA deve fazer autonomamente?
- Há temas ou assuntos que o agente deve evitar comentar?
- Existe alguma frase, tom ou tipo de resposta que seria problemática?

### Aprovações necessárias
- Para quais ações você quer ser notificado antes do agente executar?
- Como você quer ser notificado? (Telegram, email, painel web)
- Existe alguma sequência de aprovações? (ex: agente propõe → você aprova → agente executa)

### Horário e disponibilidade
- O agente precisa funcionar 24/7 ou apenas em horário específico?
- O que deve acontecer fora do horário de funcionamento? (avisa que voltará, enfileira, silencia)
- Há períodos de manutenção planejada?

### Tom e comunicação
- Como o agente deve se comunicar? (formal/informal, técnico/simples, empático/direto)
- Há um nome ou persona para o agente? (ex: "Bia", "Max", "Assistente")
- O agente deve identificar-se como IA ou manter uma persona?
- Existe algum padrão de resposta que deve seguir? (estrutura, comprimento, emojis)

---

## Perguntas de aprofundamento técnico (use somente se necessário)

### Para casos com dados complexos
- Os dados vêm estruturados (tabelas, JSON) ou não estruturados (texto livre, PDFs)?
- Qual o volume de dados que o agente vai processar? (KB por interação, MB, GB)
- A latência é crítica? (resposta deve ser imediata ou pode levar segundos/minutos?)

### Para casos com múltiplos agentes
- Este agente vai trabalhar sozinho ou junto com outros agentes?
- Um agente vai delegar tarefas para outro? Como?
- Quem é o "agente principal" que o usuário interage?

### Para casos com geração de conteúdo
- O agente gera texto, imagens, áudio, ou combinações?
- Esse conteúdo vai direto para o usuário ou passa por aprovação antes?
- Existe um template ou estilo que o conteúdo deve seguir?

### Para casos com automações programadas
- Quais tarefas devem acontecer sem interação do usuário? (cron)
- Com qual frequência? (a cada hora, diário, semanal)
- O que acontece se a tarefa programada falhar? (tenta novamente, notifica, registra)
