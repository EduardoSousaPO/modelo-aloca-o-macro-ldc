# Exemplos de Uso — Consultor PRD

Este documento mostra cenários reais de como usar a skill, desde a ativação até a geração do PRD final.

---

## Exemplo 1: Ideia Embrionária — "App de delivery para pet shops"

### O que o usuário diz:
> "Quero criar um app de delivery para pet shops. Tipo um iFood mas só para produtos de pet."

### Como a skill deve agir:

**Abertura:**
> "Ótimo, vamos explorar essa ideia juntos. Antes de pensar em funcionalidades, me ajude a entender melhor o contexto. De onde surgiu essa ideia? Você trabalha no mercado pet ou identificou essa oportunidade de outra forma?"

**Aprofundamento do problema (Etapa 2):**
> "Quando diz 'tipo um iFood para pet shops', você está pensando em:
> A) Um marketplace onde várias pet shops listam produtos e o cliente escolhe
> B) Um app white-label que cada pet shop usa individualmente
> C) Um serviço de delivery terceirizado que as pet shops contratam
>
> São modelos bem diferentes e cada um tem implicações de escopo."

**Definição de público (Etapa 3):**
> "Existem pelo menos dois lados aqui: o dono do pet que compra, e a pet shop que vende. Vamos mapear ambos. Sobre o dono do pet: estamos falando de qual perfil? Jovens urbanos com gatos? Famílias suburbanas com cachorros? Isso muda bastante a experiência."

**Resultado:** A skill guia o usuário por todas as 16 etapas, transformando uma ideia de uma linha em um PRD completo com funcionalidades detalhadas para ambos os lados do marketplace, regras de comissão, fluxo de pedido/entrega, e métricas de sucesso.

---

## Exemplo 2: Ideia em Formação — "Sistema interno de gestão de projetos"

### O que o usuário diz:
> "Preciso documentar os requisitos de um sistema de gestão de projetos para uso interno da minha empresa. Já temos uma noção do que queremos: precisa ter criação de projetos, atribuição de tarefas, timeline, e relatórios. Somos uns 50 funcionários."

### Como a skill deve agir:

**Validação rápida das Etapas 1-2:**
> "Bom, você já tem uma base sólida. Deixa eu validar: o problema que vocês estão resolvendo é falta de visibilidade sobre projetos e tarefas, correto? O que vocês usam hoje? Planilhas? Trello? E-mail? O que não funciona na solução atual?"

**Pulo para Etapas 3-5 com foco:**
> "Com 50 funcionários, quantos seriam usuários ativos? Todos ou só gestores? Há hierarquia (gestores veem tudo, membros veem só suas tarefas)? E qual seria a métrica principal de sucesso: redução de tempo em reuniões de status? Redução de projetos atrasados?"

**Resultado:** A skill identifica que o usuário já tem contexto sólido e foca em preencher lacunas específicas (regras de permissão, fluxo de aprovação, integrações com Slack/email), gerando um PRD objetivo e conciso.

---

## Exemplo 3: Ideia Avançada — "Já tenho um doc, preciso completar"

### O que o usuário diz:
> "Já tenho um rascunho de PRD para um módulo de faturamento. Preciso que você revise e complete o que está faltando."

### Como a skill deve agir:

**Análise do documento existente:**
> "Vou analisar seu rascunho usando o checklist de completude. Aqui está o que encontrei:
>
> Presente e adequado: Problema, público-alvo, 8 requisitos funcionais.
>
> Presente mas incompleto: Regras de negócio (falta detalhar cálculo de impostos e cenários de estorno). Fluxo principal existe mas falta fluxo de erro/exceção.
>
> Ausente: Requisitos não-funcionais, métricas de sucesso, riscos, priorização.
>
> Vamos começar pelas lacunas mais críticas. Sobre as regras de cálculo de impostos: qual regime tributário se aplica? Simples Nacional, Lucro Presumido ou Real?"

**Resultado:** A skill funciona como um auditor que identifica lacunas precisas e conduz o usuário para preenchê-las, sem refazer o que já está bom.

---

## Exemplo 4: Produto B2B SaaS Complexo

### O que o usuário diz:
> "Estou planejando uma plataforma SaaS B2B de compliance automatizado para fintechs. O produto precisa automatizar KYC, monitoramento de transações, geração de relatórios para o BACEN e gestão de alertas de PLD/FT."

### Como a skill deve agir:

**Reconhecimento de complexidade:**
> "Esse é um domínio regulado e complexo. Vamos precisar ser muito rigorosos com as regras de negócio e requisitos não-funcionais. Antes de entrar nas funcionalidades, preciso entender: vocês já têm expertise regulatória interna ou vão precisar de consultoria? Isso impacta o que colocamos no PRD vs. o que fica como dependência."

**Aprofundamento por módulo:**
A skill decompõe o produto em 4 módulos (KYC, Monitoramento, Relatórios BACEN, Alertas PLD/FT) e conduz discovery separado para cada um, mantendo rastreabilidade de dependências entre módulos.

**Resultado:** PRD de alta complexidade com seções robustas de compliance, regras de negócio detalhadas com base regulatória, requisitos de auditoria, e riscos regulatórios com planos de mitigação.
