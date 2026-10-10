# Plano de Execução — [Nome do Agente]

**Gerado pelo ABC em:** [data]
**Modo atual:** Execução
**Status:** Aguardando confirmação para iniciar

---

## Resumo

Este plano lista todos os arquivos que serão criados no workspace. Nenhum arquivo externo será afetado. Nenhuma credencial será usada.

---

## Arquivos a serem criados

| # | Arquivo | O que contém | Template base |
|---|---|---|---|
| 1 | `CLAUDE.md` | Contexto do projeto para futuras sessões | — (gerado sob medida) |
| 2 | `README.md` | Documentação do projeto | — (gerado sob medida) |
| 3 | `agents/[nome]/soul.md` | Identidade e regras do agente | `assets/soul_template.md` |
| 4 | `agents/[nome]/config.json` | Configuração técnica | `references/openclaw_patterns.md` |
| 5 | `agents/[nome]/memory.md.template` | Template de memória (sem dados reais) | — |
| 6 | `skills/[skill-1]/SKILL.md` | Skill custom #1 | `assets/skill_spec_template.md` |
| 7 | `skills/[skill-2]/SKILL.md` | Skill custom #2 (se houver) | `assets/skill_spec_template.md` |
| 8 | `supabase/migrations/001_initial_schema.sql` | Schema do banco de dados | `assets/supabase_schema_base.sql` |
| 9 | `.github/workflows/deploy.yml` | CI/CD para deploy automático | `references/openclaw_patterns.md` |
| 10 | `.env.example` | Template de variáveis de ambiente | `assets/env_example_template.env` |
| 11 | `decision_log.md` | Registro de todas as decisões | `assets/decision_log_template.md` |
| 12 | `.gitignore` | Arquivos ignorados pelo git | — (gerado padrão) |

---

## Decisões aplicadas neste plano

As decisões abaixo foram tomadas nos modos Discovery, PRD e Arquitetura:

| Decisão | Valor | Origem |
|---|---|---|
| LLM | [modelo] | Modo Arquitetura, Etapa 6 |
| Canal | [canal] | Modo Arquitetura, Etapa 6 |
| Tools habilitadas | [lista] | Modo Arquitetura, Etapa 7 |
| Tools com approval | [lista] | Modo Arquitetura, Etapa 7 |
| Memória | [estratégia] | Modo Arquitetura, Etapa 8 |
| Guardrails | [resumo] | Modo Arquitetura, Etapa 9 |
| Skills ClawHub | [lista] | Modo Arquitetura, Etapa 10 |
| Skills custom | [lista] | Modo Arquitetura, Etapa 10 |
| Frontend | [Lovable / Next.js / nenhum] | Modo Arquitetura, Etapa 11 |
| Tabelas Supabase extras | [lista] | Modo Arquitetura, Etapa 12 |

---

## Ordem de criação

A ABC gera os arquivos nesta sequência:

1. **Estrutura de diretórios** — criar todas as pastas
2. **CLAUDE.md** — contexto para continuidade (depende de todas as decisões)
3. **soul.md** — identidade do agente (depende do discovery + PRD)
4. **config.json** — configuração técnica (depende da arquitetura)
5. **Skills custom** — uma por uma (depende da tool policy)
6. **SQL schema** — banco de dados (depende das integrações)
7. **.gitignore** — proteção de arquivos sensíveis
8. **.env.example** — template de variáveis (depende das integrações)
9. **decision_log.md** — registro completo (depende de todas as fases)
10. **deploy.yml** — CI/CD (depende da infra escolhida)
11. **README.md** — documentação (depende de tudo acima)

---

## O que NÃO está neste plano

Estes itens ficam para o Modo Infra (Camada 3 — supervisionado):
- [ ] Instalação do OpenClaw no VPS
- [ ] Configuração do .env real com credenciais
- [ ] Criação do bot no Telegram/WhatsApp
- [ ] Criação do projeto no Supabase
- [ ] Configuração do GitHub remoto + secrets
- [ ] Deploy em produção
- [ ] Frontend no Lovable ou Next.js

---

## Confirmação

> "Vou criar os [N] arquivos listados acima no workspace atual.
> Nenhuma credencial será usada, nenhum serviço externo será acessado.
> Posso prosseguir?"
