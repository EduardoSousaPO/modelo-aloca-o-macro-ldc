# Biblioteca de Perguntas por Etapa

Este documento contém perguntas organizadas por etapa do processo de discovery. Use-as como referência — não é necessário fazer todas, selecione as mais relevantes para o contexto.

---

## Etapa 1 — Entendimento Inicial da Ideia

### Perguntas de abertura
- Me conte sobre sua ideia. O que você quer construir?
- De onde surgiu essa ideia? O que motivou?
- Você já tem algo construído ou está partindo do zero?
- Em uma frase, como você explicaria esse produto para alguém que nunca ouviu falar dele?
- Existe algum produto no mercado que faz algo parecido? Qual? O que o seu faria de diferente?

### Perguntas de clarificação
- Quando você diz "[termo usado pelo usuário]", o que exatamente quer dizer?
- Isso é um produto, uma funcionalidade dentro de algo maior, ou uma plataforma?
- É para uso interno (da empresa) ou para o mercado (clientes externos)?
- Já existe algum documento, rascunho, wireframe ou referência visual?

---

## Etapa 2 — Definição do Problema e da Oportunidade

### Sobre o problema
- Qual é o problema principal que esse produto resolve?
- Quem sofre com esse problema hoje?
- Com que frequência esse problema ocorre?
- Qual o impacto (financeiro, operacional, emocional) de não resolver?
- Como as pessoas lidam com esse problema hoje, sem o seu produto?

### Sobre a oportunidade
- Por que agora é o momento certo para resolver isso?
- Houve alguma mudança no mercado, tecnologia ou comportamento que abriu essa oportunidade?
- Qual o tamanho dessa oportunidade? (em termos de mercado, usuários ou receita)
- Há alguma tendência ou regulamentação que torna isso urgente?

---

## Etapa 3 — Identificação do Usuário e Contexto

### Sobre os usuários
- Quem são as pessoas que vão usar o produto? Descreva-as.
- Há mais de um tipo/perfil de usuário? Quais?
- Qual o nível técnico desses usuários?
- Em que contexto eles vão usar? (desktop, mobile, em campo, no escritório)
- Qual a frequência de uso esperada? (diário, semanal, eventual)

### Sobre o contexto
- Em que momento do dia/fluxo de trabalho o produto é usado?
- O usuário está sozinho ou em equipe quando usa?
- Há algum ambiente específico? (hospital, obra, escritório, trânsito)
- Quais ferramentas o usuário já usa hoje que se conectam a esse contexto?

### Sobre stakeholders
- Quem é o comprador/decisor (se diferente do usuário)?
- Quem mais é afetado pelo produto? (gestores, equipe de suporte, etc.)
- Há algum "usuário passivo" que recebe outputs do sistema sem interagir diretamente?

---

## Etapa 4 — Clareza sobre Valor Gerado

### Valor para o usuário
- O que muda na vida/rotina do usuário com esse produto?
- Qual o benefício principal em uma frase?
- Como o usuário descreveria o valor desse produto para um colega?
- O produto economiza tempo, dinheiro, esforço ou reduz risco? Quanto?

### Valor para o negócio
- Como esse produto gera valor para a empresa? (receita, retenção, eficiência)
- Qual o modelo de monetização? (assinatura, freemium, licença, transação)
- Qual é o diferencial competitivo central?

### Teste do "E daí?"
- Se eu fosse um usuário cético, por que eu deveria me importar?
- O que acontece se o usuário simplesmente não adotar esse produto?

---

## Etapa 5 — Objetivos do Produto e do Negócio

### Objetivos de produto
- Quais são os 3 principais objetivos do produto no primeiro ano?
- Qual é a north star metric (a métrica que mais importa)?
- Quais objetivos são do MVP vs. da visão de longo prazo?

### Objetivos de negócio
- Qual meta de receita/crescimento está atrelada a esse produto?
- Esse produto abre um novo mercado ou atende o mercado existente?
- Há metas de aquisição, retenção ou conversão definidas?

### Alinhamento
- Os objetivos de produto e negócio estão alinhados? Como?
- Se precisasse escolher entre crescimento e receita no ano 1, qual priorizaria?

---

## Etapa 6 — Definição do Escopo do MVP

### Critérios de corte
- Qual o critério para algo estar no MVP? (resolve a dor central? é viável no prazo?)
- Qual funcionalidade, se retirada, inviabiliza completamente o produto?
- Existe uma data ou evento que define o prazo do MVP?

### Limites
- O que definitivamente NÃO entra no MVP?
- Quais funcionalidades você adoraria ter mas aceita que fiquem para depois?
- Há algo que precisa estar no MVP por razão regulatória ou contratual?

### Validação
- Como vocês vão saber se o MVP funcionou?
- Haverá um piloto/beta antes do lançamento geral?
- Quantos usuários no lançamento inicial?

---

## Etapa 7 — Mapeamento de Funcionalidades

### Para cada funcionalidade identificada
- Descreva em uma frase o que essa funcionalidade faz.
- Quem usa essa funcionalidade? (qual persona)
- Qual problema específico ela resolve?
- É essencial (MVP) ou desejável (futuro)?
- Qual a complexidade estimada? (simples, média, complexa)
- Há dependência de outra funcionalidade?

### Visão geral
- Consigo agrupar essas funcionalidades em módulos ou áreas?
- Qual funcionalidade é a "killer feature"?
- Alguma funcionalidade poderia ser substituída por uma integração com ferramenta existente?

---

## Etapa 8 — Mapeamento de Jornadas e Fluxos Críticos

### Jornadas principais
- Descreva passo a passo o que acontece quando o usuário [ação principal].
- Qual é a primeira coisa que o usuário vê/faz ao entrar?
- Quais são os pontos de decisão no fluxo?
- O que acontece se algo der errado? (cenários de erro)

### Fluxos secundários
- Há fluxos alternativos? (ex: cadastro via Google vs. email)
- Quais fluxos administrativos existem? (gestão, moderação, configuração)
- Existe algum fluxo de onboarding?

### Mapeamento
- Onde o usuário pode ficar confuso ou travar?
- Qual o "caminho feliz" (happy path) mais importante?
- Há fluxos que envolvem espera, aprovação ou processamento assíncrono?

---

## Etapa 9 — Regras de Negócio

### Regras gerais
- Quais regras governam o comportamento do sistema?
- Há limites de quantidade, frequência ou valor?
- Existem regras de permissão? (quem pode fazer o quê)

### Regras por funcionalidade
- Para [funcionalidade X], quais são as condições/validações?
- Há regras de cálculo? (preços, descontos, taxas, comissões)
- Existem estados/status? Quais? Quais as transições permitidas?

### Exceções
- Quais são os cenários de exceção?
- Há regras que mudam conforme o perfil do usuário?
- Existem regras temporais? (promoções, períodos, safras)

---

## Etapa 10 — Dependências e Integrações

### Integrações
- O produto precisa se integrar com algum sistema externo?
- Há APIs de terceiros envolvidas? Quais?
- Alguma integração é obrigatória para o MVP?

### Dados
- De onde vêm os dados? (input manual, importação, API)
- Há necessidade de migração de dados?
- Qual o formato/padrão dos dados?

### Dependências internas
- O produto depende de algum outro sistema interno da empresa?
- Há dependência de equipe, infraestrutura ou licença?

---

## Etapa 11 — Restrições Técnicas e Operacionais

### Técnicas
- Há stack tecnológica obrigatória? (linguagem, framework, cloud)
- Há requisitos de performance? (tempo de resposta, throughput)
- Há requisitos de segurança específicos? (LGPD, SOC2, criptografia)
- Deve funcionar offline?

### Operacionais
- Qual o orçamento disponível?
- Qual o tamanho da equipe?
- Qual o prazo?
- Há restrições de infraestrutura? (on-premise vs. cloud)

### Regulatórias
- Há regulamentações setoriais? (saúde, finanças, educação)
- Há requisitos de acessibilidade?
- Há requisitos de internacionalização?

---

## Etapa 12 — Métricas de Sucesso

### Métricas de produto
- Quais métricas definem que o produto está funcionando?
- Quais são os thresholds mínimos de sucesso?
- Como essas métricas serão coletadas?

### Métricas de negócio
- Quais KPIs de negócio esse produto impacta?
- Qual a meta para cada KPI?
- Em quanto tempo esperamos ver resultados?

### Métricas de experiência
- Como medir satisfação do usuário? (NPS, CSAT, CES)
- Qual a taxa de adoção esperada?
- Qual a taxa de churn aceitável?

---

## Etapa 13 — Riscos, Hipóteses e Pontos em Aberto

### Riscos
- Quais são os maiores riscos do projeto?
- O que pode fazer o projeto falhar?
- Há riscos técnicos, de mercado, regulatórios ou de equipe?
- Qual o plano de mitigação para os riscos principais?

### Hipóteses
- Quais suposições estamos fazendo que ainda não foram validadas?
- Quais dessas hipóteses são críticas? (se erradas, inviabilizam o produto)
- Como podemos testar essas hipóteses antes de investir pesado?

### Pontos em aberto
- O que ainda não foi decidido?
- Quem precisa ser consultado para fechar essas pendências?
- Qual o prazo para resolução?

---

## Etapa 14 — Priorização

### Classificação
- Para cada funcionalidade: é Must, Should, Could ou Won't? (MoSCoW)
- Alternativamente: qual o score RICE? (Reach, Impact, Confidence, Effort)
- Se precisasse cortar 50% do escopo, o que ficaria?

### Trade-offs
- Onde estamos trocando simplicidade por poder?
- Onde estamos trocando velocidade de entrega por qualidade?
- Qual funcionalidade entrega mais valor com menor esforço?

---

## Etapa 15 — Consolidação do PRD

### Validação final
- Todas as seções do PRD estão preenchidas?
- Há contradições entre seções?
- Os requisitos são testáveis/verificáveis?
- O escopo está claro e delimitado?

---

## Etapa 16 — Preparação para Próximos Passos

### Transição
- O PRD tem informação suficiente para começar SPECs técnicas?
- Quem será responsável por cada próximo passo?
- Qual a sequência recomendada de implementação?
- Há algo que precisa acontecer antes de começar o desenvolvimento?
