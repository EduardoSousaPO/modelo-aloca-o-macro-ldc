# Critérios de Aceite — [Nome do Agente]

**Versão:** 1.0
**Data:** [DD/MM/AAAA]
**Derivado do PRD:** [link ou referência ao PRD]

---

## Como usar este documento

Para cada comportamento do agente classificado como Must ou Should no PRD, defina critérios de aceite verificáveis. Cada critério deve poder ser testado e resultar em PASSOU ou FALHOU — sem ambiguidade.

---

## Formato de cada critério

```
### AC-[ID]: [Nome descritivo]
**Comportamento:** [ID do comportamento no PRD, ex: AG-001]
**Prioridade:** Must | Should

**Dado que:** [contexto / pré-condição]
**Quando:** [ação do usuário ou trigger]
**Então:** [resultado esperado específico e verificável]

**Como testar:**
1. [passo 1]
2. [passo 2]
3. [verificação]

**Resultado esperado:** [o que deve acontecer exatamente]
```

---

## Critérios obrigatórios (MUST)

### AC-001: [Nome do critério]
**Comportamento:** AG-001
**Prioridade:** Must

**Dado que:** [contexto]
**Quando:** [trigger]
**Então:** [resultado]

**Como testar:**
1. [passo]
2. [passo]
3. [verificação]

**Resultado esperado:** [específico]

---

### AC-002: [Nome do critério]
**Comportamento:** AG-002
**Prioridade:** Must

**Dado que:** [contexto]
**Quando:** [trigger]
**Então:** [resultado]

**Como testar:**
1. [passo]
2. [passo]
3. [verificação]

**Resultado esperado:** [específico]

---

## Critérios importantes (SHOULD)

### AC-003: [Nome do critério]
**Comportamento:** AG-003
**Prioridade:** Should

**Dado que:** [contexto]
**Quando:** [trigger]
**Então:** [resultado]

**Como testar:**
1. [passo]
2. [passo]
3. [verificação]

**Resultado esperado:** [específico]

---

## Critérios de infraestrutura

### AC-INF-001: Agente disponível 24/7
**Dado que:** o agente está deployado no VPS
**Quando:** um usuário envia mensagem a qualquer hora
**Então:** o agente responde em menos de [X] segundos

**Como testar:** enviar mensagem fora do horário comercial e medir latência

### AC-INF-002: Recuperação automática após falha
**Dado que:** o processo do OpenClaw cai
**Quando:** systemd detecta a falha
**Então:** o processo reinicia em 2 segundos e o agente volta a responder

**Como testar:** `systemctl kill openclaw && sleep 3 && systemctl status openclaw`

### AC-INF-003: Dados protegidos
**Dado que:** o banco Supabase tem dados de usuários
**Quando:** um usuário acessa via frontend
**Então:** ele vê apenas seus próprios dados (RLS ativo)

**Como testar:** fazer login com dois usuários diferentes e verificar que cada um só vê seus dados

---

## Critérios de segurança

### AC-SEC-001: Credenciais protegidas
**Dado que:** o repositório está no GitHub
**Quando:** alguém inspeciona os arquivos
**Então:** nenhuma credencial real aparece (API keys, tokens, senhas)

**Como testar:** `git log --all -p | grep -i "sk-ant\|sk-\|token\|password\|secret"` não retorna resultados

### AC-SEC-002: Auditoria limpa
**Dado que:** o agente está em produção
**Quando:** `openclaw security audit` é executado
**Então:** 0 erros críticos

---

## Smoke tests

Testes rápidos para confirmar que o básico funciona:

| # | Teste | Input | Output esperado | Passou? |
|---|---|---|---|---|
| 1 | Agente responde | "olá" no canal | Resposta coerente com soul.md | [ ] |
| 2 | Fluxo principal | [trigger do AG-001] | [resultado do AG-001] | [ ] |
| 3 | Input inválido | [mensagem sem sentido] | Agente pede esclarecimento | [ ] |
| 4 | Ação com approval | [trigger de ação restrita] | Notificação de aprovação | [ ] |
| 5 | Custo por interação | 10 interações de teste | Custo total < $[X] | [ ] |

---

## Critério de conclusão do MVP

> "O agente está pronto para produção quando:"
> - [ ] Todos os critérios MUST passam
> - [ ] Pelo menos 80% dos critérios SHOULD passam
> - [ ] Todos os smoke tests passam
> - [ ] Todos os critérios de infraestrutura passam
> - [ ] Todos os critérios de segurança passam
