# [Nome do Agente] — Agent PRD

**Versão:** 1.0
**Data:** [DD/MM/AAAA]
**Status:** Rascunho | Aprovado
**Projeto:** [pasta do projeto]

---

## 1. Resumo do Agente

> [Uma frase: "O agente X faz Y para Z, via canal W, integrando com A e B"]

[2-3 parágrafos descrevendo: o problema que resolve, como o agente funciona em alto nível, e o resultado esperado para o usuário]

---

## 2. Problema e Motivação

### O problema atual
[Como as coisas funcionam hoje, sem o agente. O que é feito manualmente ou não é feito.]

### Por que um agente autônomo
[Por que um agente de IA resolve isso melhor do que uma automação simples ou um humano]

### Resultado esperado
[O que muda na vida do usuário quando o agente está funcionando]

---

## 3. Usuário Final

### Persona principal
- **Quem é:** [cargo, contexto, dia a dia]
- **Canal de interação:** [WhatsApp / Telegram / WebChat / outro]
- **Frequência:** [diária / semanal / sob demanda]
- **Nível técnico:** [alto / médio / baixo]
- **Sabe que é IA:** [sim / não / não importa para o caso de uso]
- **O que dispara uma interação:** [situação ou evento]

### Outros perfis (se houver)
- [Persona 2: admin, gestor, etc.]

---

## 4. Comportamentos do Agente

O que o agente FAZ — não funcionalidades de sistema, mas comportamentos observáveis.

| ID | Comportamento | O que dispara | O que o agente executa | O que o usuário recebe | Prioridade |
|---|---|---|---|---|---|
| AG-001 | [nome] | [trigger] | [ação] | [output] | Must |
| AG-002 | [nome] | [trigger] | [ação] | [output] | Must |
| AG-003 | [nome] | [trigger] | [ação] | [output] | Should |
| AG-004 | [nome] | [trigger] | [ação] | [output] | Could |

---

## 5. Ações Executadas (não apenas respostas)

Ações que o agente realiza no mundo real — não apenas respostas de texto.

| Ação | Tool OpenClaw | MCP/Integração | Approval necessária | Risco |
|---|---|---|---|---|
| [ação] | [tool] | [mcp ou nenhum] | Sim / Não | Alto / Médio / Baixo |

---

## 6. Integrações e MCPs

| Sistema | Tipo de acesso | Via | Criticidade para MVP |
|---|---|---|---|
| [sistema] | Leitura / Escrita / Ambos | MCP / API direta / webhook | Obrigatória / Opcional |

---

## 7. Estratégia de Memória

| Tipo de dado | Onde armazenar | Motivo |
|---|---|---|
| Preferências do usuário sobre o agente | MEMORY.md | Injetado automaticamente no context |
| Histórico de conversas | Supabase `messages` | Consultável pelo usuário no frontend |
| Dados do produto / negócio | Supabase tabelas específicas | SQL queries, relatórios |
| Arquivos temporários de tarefas | Workspace OpenClaw | Escopo de sessão |
| [outros] | [onde] | [motivo] |

---

## 8. Stack Técnica

| Componente | Escolha | Justificativa |
|---|---|---|
| Runtime | OpenClaw | — |
| LLM | [modelo] | [motivo] |
| Canal principal | [canal] | [motivo] |
| Backend/dados | Supabase | — |
| Frontend | Next.js / Não tem no MVP | [motivo] |
| VPS | Hostinger [spec] | — |
| Versioning | GitHub | — |

---

## 9. Tool Policy

| Tool | Status | Motivo | Approval? |
|---|---|---|---|
| read | ✅ Habilitada | [motivo] | Não |
| write / edit | ✅ Habilitada | [motivo] | Não |
| web_search | ✅ Habilitada | [motivo] | Não |
| web_fetch | ✅ Habilitada | [motivo] | Não |
| message | ✅/❌ | [motivo] | [se sim: quando] |
| cron | ✅/❌ | [motivo] | Não |
| image | ✅/❌ | [motivo] | Não |
| exec | ❌ Desabilitada | [motivo ou "não necessária"] | — |
| browser | ❌ Desabilitada | [motivo ou "não necessária"] | — |
| MCP supabase | ✅ Habilitada | acesso ao banco | Para deletes |
| MCP [outro] | ✅/❌ | [motivo] | [se sim: quando] |

---

## 10. Guardrails e Segurança

### Soft guardrails (SOUL.md)
- [instrução advisory 1]
- [instrução advisory 2]

### Hard guardrails
- Allowlist de usuários: [pairing / allowlist / open]
- Exec approvals: [configurado / não aplicável]
- Sandbox Docker: [sim / não]
- Gateway auth: token obrigatório

### Ações que requerem aprovação humana
- [ação 1] — notificação via [canal]
- [ação 2]

### Ações que o agente nunca pode fazer
- [ação proibida 1]
- [ação proibida 2]

---

## 11. Skills Necessárias

| Skill | Origem | O que ensina o agente |
|---|---|---|
| [nome] | ClawHub `openclaw skills install [slug]` | [comportamento] |
| [nome] | Custom (criar em `skills/[nome]/SKILL.md`) | [comportamento] |

---

## 12. Escopo MVP (MoSCoW)

**Must Have** — agente não faz sentido sem isso:
- [comportamento AG-001]
- [comportamento AG-002]

**Should Have** — importante, não bloqueia lançamento:
- [comportamento AG-003]

**Could Have** — desejável, aguarda feedback real:
- [comportamento AG-004]

**Won't Have** (nesta versão) — explicitamente fora:
- [item] — motivo: [por quê]

**Critério de saída do MVP:** "O agente está pronto quando [condição verificável]"

---

## 13. Métricas do Agente

| Métrica | Como medir | Target inicial |
|---|---|---|
| Taxa de conclusão de tarefa | % interações sem erro no log | > 90% |
| Latência média de resposta | Tempo entre mensagem e resposta | < [X] segundos |
| Taxa de approval acionada | % tasks que precisaram de intervenção | < [X]% |
| Custo por interação | Tokens / 1K × preço do modelo | < $[X] |
| Taxa de abandono | Usuário para de responder no meio do fluxo | < [X]% |

---

## 14. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Prompt injection | Média | Alto | Tool policy restritiva + sandbox |
| Rate limit do LLM | Alta | Médio | Circuit breaker, modelo alternativo |
| WhatsApp API muda (se aplicável) | Média | Alto | Telegram como fallback |
| Credenciais expostas | Baixa | Alto | .gitignore + env vars + audit |
| VPS fora do ar | Baixa | Alto | Systemd restart + monitoramento |
| [risco específico do negócio] | [prob] | [imp] | [mitigação] |

---

## 15. Dúvidas Pendentes

| # | Dúvida | Bloqueante? | Responsável | Prazo |
|---|---|---|---|---|
| 1 | [dúvida] | Sim / Não | [quem resolve] | [quando] |

---

## 16. Próximos Passos

| # | Ação | Responsável | Prazo |
|---|---|---|---|
| 1 | Gerar arquivos do projeto (soul.md, config.json, skills) | Claude Code / ABC | Agora |
| 2 | Setup VPS Hostinger | Usuário + ABC | [quando] |
| 3 | Instalar skills do ClawHub | Claude Code no VPS | [quando] |
| 4 | Configurar Supabase | Usuário + ABC | [quando] |
| 5 | Criar frontend Next.js | Claude Code | [quando] |
| 6 | Configurar GitHub + CI/CD | Claude Code | [quando] |
| 7 | Teste funcional end-to-end | Usuário | [quando] |
