---
name: [nome-da-skill]
description: >
  [Uma linha descrevendo o que esta skill ensina o agente a fazer.
  Esta linha aparece no system prompt — seja específico e direto.]
---

# [Nome da Skill]

<!--
INSTRUÇÕES (remover antes de usar):
Este é o template para skills CUSTOM do agente — comportamentos específicos
do seu negócio que não existem no ClawHub.
Escreva em linguagem natural, como se estivesse ensinando um colega novo.
-->

## Quando usar esta skill

Use esta skill quando:
- [Condição 1 — ser específico sobre o trigger]
- [Condição 2]

NÃO use esta skill quando:
- [Condição que parece similar mas não é — evitar confusão]

---

## O que você precisa ter disponível

Antes de executar esta skill, verifique que tem:
- [Informação 1 necessária — ex: nome do usuário, ID do pedido]
- [Tool necessária — ex: web_search habilitada, MCP supabase conectado]
- [Dado de contexto — ex: histórico da conversa atual]

---

## Como executar — passo a passo

1. **[Passo 1]**
   [Descrição detalhada do que fazer. Inclua exemplos quando útil.]

2. **[Passo 2]**
   [Descrição. Se envolve uma tool, especifique qual e como usar.]
   Exemplo: Use `web_search` para buscar "[query específica]"

3. **[Passo 3]**
   [Continuar...]

4. **[Passo final]**
   [O que entregar ao usuário ao final.]

---

## Formato da resposta

[Descreva como a resposta deve ser formatada. Exemplos:]
- Responda em [formato: bullet points / parágrafo / tabela / JSON]
- Extensão: [curta / até 3 parágrafos / detalhada]
- Inclua sempre: [elementos obrigatórios]
- Evite: [o que não incluir]

---

## Cenários de erro — o que fazer quando algo falha

| Situação | O que fazer |
|---|---|
| [Dado necessário não disponível] | [Como proceder — pedir ao usuário? usar fallback?] |
| [Tool falhou] | [Tentar novamente? Comunicar ao usuário? Usar alternativa?] |
| [Resultado inesperado] | [Como validar e tratar] |

---

## Exemplo de uso

**Trigger:** [O que o usuário disse ou aconteceu]

**Execução:**
```
[Passo 1]: [o que o agente fez]
[Passo 2]: [resultado intermediário]
[Passo 3]: [resultado final]
```

**Resposta para o usuário:**
> [Exemplo de resposta que o agente daria]
