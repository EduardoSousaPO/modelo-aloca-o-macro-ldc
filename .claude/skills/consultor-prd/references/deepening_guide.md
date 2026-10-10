# Guia de Aprofundamento de Respostas

Este guia descreve técnicas para quando o usuário dá respostas vagas, genéricas ou insuficientes. O objetivo é extrair informação com a profundidade necessária para um PRD de qualidade sem parecer interrogatório.

---

## Quando Aprofundar

Sinais de que uma resposta precisa de mais profundidade:

- **Usa termos genéricos:** "os usuários", "várias funcionalidades", "vai ter um painel"
- **Não tem números:** "muitos", "bastante", "alguns"
- **Não tem exemplos concretos:** descreve conceitos mas não cenários reais
- **Contradiz algo anterior:** afirmou X na etapa 2 mas Y na etapa 7
- **Evita decisão:** "isso a gente vê depois", "depende"
- **Resposta de uma linha para pergunta complexa**

---

## Técnicas de Aprofundamento

### 1. Concretização
Transformar abstrato em concreto pedindo exemplos reais.

**Gatilho:** Respostas como "vai ter um cadastro" ou "os usuários podem gerenciar seus dados"

**Como usar:**
- "Pode me dar um exemplo específico de como isso funcionaria na prática?"
- "Imagina que a Maria, uma usuária típica, está usando o sistema agora. O que ela vê? O que ela clica?"
- "Me descreva um caso real que você já vivenciou onde esse problema acontece."

---

### 2. Quantificação
Transformar "muito/pouco" em números ou faixas.

**Gatilho:** "Muitos usuários", "uma quantidade grande de dados", "vai crescer bastante"

**Como usar:**
- "Quando diz 'muitos', estamos falando de 50, 500 ou 50.000?"
- "Qual a ordem de grandeza? Dezenas, centenas, milhares?"
- "Se tivesse que chutar um número para o primeiro mês, qual seria?"
- "Qual o volume no pior caso? E no caso típico?"

---

### 3. Comparação
Ancorar a ideia em referências conhecidas para reduzir ambiguidade.

**Gatilho:** Descrições abstratas que poderiam significar coisas muito diferentes

**Como usar:**
- "Isso é mais parecido com Trello ou com Jira? (simples e visual vs. robusto e complexo)"
- "O nível de detalhe que você quer é como uma calculadora simples ou como uma planilha Excel?"
- "Quando diz 'relatório', está pensando em algo como um dashboard interativo ou um PDF estático?"

---

### 4. Consequenciação
Explorar implicações de uma escolha para validar se o usuário realmente pensou nela.

**Gatilho:** Decisões que parecem impulsivas ou que podem ter consequências não óbvias

**Como usar:**
- "Se fizermos dessa forma, isso significa que [consequência]. Você está ok com isso?"
- "Essa escolha implica que no futuro [impacto]. Faz sentido?"
- "Se esse cenário acontecer, como o sistema deveria reagir?"
- "E se o volume triplicar em 6 meses, essa abordagem ainda funciona?"

---

### 5. Contrafactual
Imaginar o oposto para testar a importância real de algo.

**Gatilho:** Funcionalidades que podem não ser realmente necessárias, ou prioridades questionáveis

**Como usar:**
- "E se a gente NÃO tivesse essa funcionalidade no MVP, o que aconteceria?"
- "Se esse requisito simplesmente não existisse, o produto ainda faria sentido?"
- "Imagine que tiramos isso do escopo. Quem reclama? Com que intensidade?"
- "O que o usuário faria como alternativa se essa feature não existisse?"

---

### 6. Decomposição
Quebrar algo grande e vago em partes menores e gerenciáveis.

**Gatilho:** "Vai ter um módulo de relatórios", "precisa de um sistema de notificações"

**Como usar:**
- "Quando diz 'relatórios', quantos tipos diferentes existem?"
- "Vamos listar um por um: qual é o primeiro tipo de relatório que vem à mente?"
- "Desses sub-itens, quais são MVP e quais são futuro?"

---

### 7. Perspectiva do Adversário
Questionar a ideia como um cético faria — respeitosamente.

**Gatilho:** Suposições arriscadas, mercado competitivo, proposta de valor fraca

**Como usar:**
- "Se eu fosse um investidor, perguntaria: por que alguém usaria isso em vez de [alternativa]?"
- "Um concorrente já faz X. O que torna o seu abordagem diferente o suficiente?"
- "Se um usuário me dissesse 'não preciso disso', o que você responderia?"

---

### 8. Escalonamento
Perguntar o que acontece em extremos para descobrir limites e regras.

**Gatilho:** Regras de negócio vagamente definidas, limites não especificados

**Como usar:**
- "E se um usuário fizer isso 1.000 vezes por dia? O sistema permite?"
- "Qual o máximo de [X] permitido? E o mínimo?"
- "O que acontece no limite? Bloqueia, avisa, ou ignora?"
- "E se dois usuários tentarem fazer a mesma coisa ao mesmo tempo?"

---

## Fluxo de Decisão para Aprofundamento

```
Usuário responde algo
    ├── Resposta clara e suficiente? → Aceite e avance
    ├── Resposta vaga? → Use Concretização ou Quantificação
    ├── Resposta com termos ambíguos? → Use Comparação
    ├── Resposta parece impulsiva? → Use Consequenciação
    ├── Prioridade questionável? → Use Contrafactual
    ├── Resposta grande demais? → Use Decomposição
    └── Suposição arriscada? → Use Perspectiva do Adversário
```

---

## Regras de Ouro

1. **Máximo 2 rodadas de aprofundamento por tópico.** Se após 2 tentativas o usuário não consegue dar mais detalhes, registre como "ponto em aberto" e siga em frente.

2. **Sempre explique por que está pedindo mais detalhes.** "Pergunto isso porque sem saber o volume, não consigo definir se precisamos de cache ou não — e isso muda o escopo técnico."

3. **Ofereça opções quando o usuário travar.** Em vez de insistir na pergunta aberta, ofereça: "Geralmente vejo três abordagens: A, B ou C. Qual delas faz mais sentido para vocês?"

4. **Valide antes de encerrar.** "Então, resumindo: [sua interpretação]. Está correto?"

5. **Registre incertezas.** Tudo que não ficou 100% claro deve ir para a seção de "Hipóteses" ou "Dúvidas Pendentes" do PRD.
