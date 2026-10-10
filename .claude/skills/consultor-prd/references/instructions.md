# Instruções de Uso — Skill Consultor PRD

## O que é esta Skill?

O Consultor PRD é uma skill que transforma Claude em um consultor sênior de produto. Em vez de simplesmente gerar um template vazio, a skill conduz um processo completo de discovery — fazendo perguntas estratégicas, identificando lacunas, aprofundando respostas superficiais e gerando um PRD (Product Requirements Document) de alto nível.

---

## Como Ativar

A skill é ativada automaticamente quando você menciona termos como:
- "PRD", "product requirements", "requisitos de produto"
- "discovery de produto", "escopo de projeto", "MVP"
- "quero criar um produto", "tenho uma ideia para um app"
- "preciso documentar um projeto"
- "levantamento de requisitos", "especificação de produto"

Você também pode ativá-la explicitamente dizendo: "Use a skill consultor_prd para me ajudar."

---

## Como Funciona

### 1. Você descreve sua ideia
Pode ser uma frase vaga ou um documento detalhado — a skill se adapta.

### 2. A skill conduz um processo de discovery
Através de perguntas progressivas organizadas em 16 etapas:
1. Entendimento inicial
2. Problema e oportunidade
3. Usuário e contexto
4. Valor gerado
5. Objetivos
6. Escopo do MVP
7. Funcionalidades
8. Jornadas e fluxos
9. Regras de negócio
10. Dependências e integrações
11. Restrições
12. Métricas de sucesso
13. Riscos e hipóteses
14. Priorização
15. Consolidação do PRD
16. Próximos passos

### 3. A skill gera um PRD completo
Documento profissional com todas as seções necessárias, pronto para servir de base para SPECs técnicas e desenvolvimento.

---

## Dicas para Melhor Resultado

1. **Seja honesto sobre o que não sabe.** A skill vai ajudar a preencher as lacunas com sugestões e opções.

2. **Não tenha pressa.** O processo de discovery leva tempo, mas o resultado é infinitamente melhor do que preencher um template às pressas.

3. **Discorde quando necessário.** Se a skill fizer uma sugestão que não faz sentido para o seu contexto, diga — ela vai se adaptar.

4. **Use exemplos concretos.** Quando puder, descreva cenários reais em vez de conceitos abstratos.

5. **Peça para pausar e resumir.** A qualquer momento, pode pedir: "Resume o que temos até agora" ou "Gera um PRD parcial com o que temos."

---

## Estrutura de Arquivos da Skill

```
consultor_prd/
├── SKILL.md                              # Instruções principais da skill
├── scripts/
│   ├── generate_prd.py                   # Gerador de PRD a partir de dados JSON
│   └── validate_prd.py                   # Validador de completude do PRD
├── references/
│   ├── question_library.md               # Biblioteca completa de perguntas por etapa
│   ├── deepening_guide.md                # Técnicas de aprofundamento de respostas
│   ├── discovery_playbook.md             # Roteiro operacional do discovery
│   └── instructions.md                   # Este arquivo
└── assets/
    ├── prd_template.md                   # Template base do PRD
    ├── completeness_checklist.md         # Checklist de validação
    └── usage_examples.md                 # Exemplos de uso em diferentes cenários
```

---

## Cenários de Uso

| Cenário | O que acontece |
|---------|---------------|
| Ideia embrionária | Discovery completo desde a etapa 1 |
| Ideia parcial | Validação rápida do que existe + foco nas lacunas |
| PRD incompleto | Análise do documento + preenchimento das lacunas |
| Requisitos técnicos | Aprofundamento nas etapas 7-11 |
| Validação de escopo | Foco nas etapas 6, 14, 15 |

---

## Saídas Possíveis

- **PRD em Markdown**: Documento completo, pronto para copiar/colar ou converter
- **PRD em .docx**: Se a skill docx estiver disponível, pode gerar versão Word profissional
- **Resumos parciais**: A qualquer momento, pode pedir um snapshot do progresso
- **Relatório de validação**: Usando o script validate_prd.py, pode verificar completude
