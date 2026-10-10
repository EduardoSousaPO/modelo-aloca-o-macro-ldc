# Decision Log — [Nome do Agente]

*Atualizado pela skill ABC durante a sessão. Sempre manter este arquivo atualizado.*
*Na próxima sessão do Claude Code, leia este arquivo primeiro para retomar o contexto.*

**Projeto iniciado em:** [data]
**Última atualização:** [data]
**Status:** [Em discovery / Arquitetura definida / Arquivos gerados / Em deploy / Em produção]

---

## Resumo em uma linha

> [O agente X faz Y para Z via canal W]

---

## Decisões de Produto

| ID | Decisão | Valor escolhido | Alternativa rejeitada | Motivo | Data |
|---|---|---|---|---|---|
| DP-001 | Canal principal | [canal] | [alternativa] | [motivo] | [data] |
| DP-002 | Escopo MVP | [definido em AG-00X a AG-00X] | [excluídos] | [motivo] | [data] |
| DP-003 | Usuário alvo | [persona] | — | — | [data] |

---

## Decisões Técnicas

| ID | Decisão | Valor | Default ou Customizado | Justificativa |
|---|---|---|---|---|
| DT-001 | LLM | [modelo] | Default / Customizado | [motivo] |
| DT-002 | Exec habilitado | Sim / Não | Default (não) | [motivo se customizado] |
| DT-003 | Canal | [canal] | Default (Telegram) | [motivo se customizado] |
| DT-004 | Frontend no MVP | Sim / Não | [decisão] | [motivo] |
| DT-005 | Sandbox Docker | Sim / Não | [decisão] | [motivo] |
| DT-006 | Supabase região | [região] | Default (sa-east-1) | [motivo se customizado] |

---

## Defaults Assumidos pela Skill (sem perguntar ao usuário)

Lista de decisões técnicas que a ABC tomou automaticamente. O usuário pode sobrescrever qualquer uma.

| Item | Valor assumido | Onde alterar |
|---|---|---|
| Node.js version | 24.x | Script de instalação VPS |
| OS do VPS | Ubuntu 22.04 | Script de instalação VPS |
| Restart policy | always / RestartSec=2 | `/etc/systemd/system/openclaw.service` |
| Gateway binding | loopback + Tailscale | `openclaw config` |
| Allowlist mode | pairing | `openclaw config` |
| Supabase Auth | Supabase nativo (JWT) | `supabase/config.toml` |
| RLS | habilitado em todas as tabelas | `supabase/migrations/` |
| Branches GitHub | main + develop | `.github/` |

---

## Skills Planejadas

| Skill | Origem | Status | Slug ou path |
|---|---|---|---|
| [nome] | ClawHub | A instalar / Instalada | `openclaw skills install [slug]` |
| [nome] | Custom | A criar / Criada | `skills/[nome]/SKILL.md` |

---

## Itens em Aberto

Tudo que não foi decidido ainda. Separado por impacto.

### Bloqueantes (impede avançar para a próxima fase)
| ID | Item | O que impede | Responsável | Prazo |
|---|---|---|---|---|
| AB-001 | [item] | [o que trava] | [quem] | [quando] |

### Não-bloqueantes (pode resolver depois)
| ID | Item | Impacto se não resolvido | Prazo |
|---|---|---|---|
| ANB-001 | [item] | [impacto] | [quando] |

---

## Estado atual das fases

| Fase | Status | Observações |
|---|---|---|
| Fase 1 — Discovery de negócio | [Não iniciada / Em andamento / Completa] | |
| Fase 2 — Decisões técnicas | [Não iniciada / Em andamento / Completa] | |
| Fase 3 — Geração de arquivos | [Não iniciada / Em andamento / Completa] | Arquivos em: [lista] |
| Fase 4 — Setup VPS | [Não iniciada / Em andamento / Completa] | VPS: [IP] |
| Fase 5 — Supabase + Frontend | [Não iniciada / Em andamento / Completa] | Supabase: [URL] |
| Fase 6 — GitHub + CI/CD | [Não iniciada / Em andamento / Completa] | Repo: [URL] |
| Fase 7 — Validação | [Não iniciada / Em andamento / Completa] | |

---

## Histórico de sessões

| Data | O que foi feito | O que ficou para a próxima sessão |
|---|---|---|
| [data] | [resumo] | [pendências] |
