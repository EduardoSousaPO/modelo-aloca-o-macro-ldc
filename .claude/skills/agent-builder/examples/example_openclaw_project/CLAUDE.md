# Lead Qualifier Agent — Contexto do Projeto

**Gerado pelo Agent Builder Copilot (ABC)**
**Última atualização:** [data]

---

## O que é este projeto

Agente autônomo de qualificação de leads para empresa de energia solar. Recebe leads via Telegram (migrar para WhatsApp quando aprovado pela Meta), faz 5 perguntas de qualificação, classifica o lead como quente/morno/frio, e encaminha leads qualificados para o vendedor.

## Stack

- **Runtime:** OpenClaw no VPS Hostinger
- **LLM:** Claude Sonnet 4.6 (Anthropic)
- **Canal:** Telegram (dev) → WhatsApp (prod)
- **Backend:** Supabase (sa-east-1)
- **Frontend:** Lovable (dashboard de leads)
- **Versionamento:** GitHub com CI/CD

## Estrutura do projeto

```
agents/lead-qualifier/
  soul.md          → identidade do agente "Sol"
  config.json      → Claude Sonnet, tools: read, write, web_search, message
  memory.md.template → template de memória

skills/qualify-lead/
  SKILL.md         → skill de qualificação em 5 perguntas

supabase/migrations/
  001_initial_schema.sql → profiles, conversations, messages, agent_tasks, leads
```

## Decisões tomadas

- LLM: Claude Sonnet 4.6 (custo adequado para volume de ~500 leads/mês)
- Canal: Telegram para dev porque WhatsApp requer aprovação Meta
- Exec: desabilitado (agente só qualifica, não precisa rodar comandos)
- Browser: desabilitado
- Sandbox: não necessário (sem exec)
- Frontend: Lovable para dashboard de leads + métricas

## O que falta

- [ ] Setup VPS Hostinger (Modo Infra)
- [ ] Criar bot no Telegram (Modo Infra)
- [ ] Criar projeto Supabase e rodar migration (Modo Infra)
- [ ] Criar dashboard no Lovable (Modo Infra)
- [ ] Configurar GitHub Actions (Modo Infra)
- [ ] Validação end-to-end (Modo Validação)

## Como retomar

Abra o Claude Code nesta pasta. O ABC vai ler este arquivo e retomar do ponto onde parou. Diga "continua de onde paramos" ou vá direto para o modo que precisa.
