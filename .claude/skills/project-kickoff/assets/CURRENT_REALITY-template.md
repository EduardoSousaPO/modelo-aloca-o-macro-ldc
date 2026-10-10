# CURRENT_REALITY — [Nome do Projeto]

> **Fotografia honesta do estado atual do repositório.** Obrigatório para projetos **já iniciados**, **em produção** ou **bagunçados** (cenários B, C, D). Opcional para projetos novos (cenário A).
>
> **Gerado antes do PRD/SPEC retroativos.** Evita que o `/consultor-prd` ou o `/SDD-avancado` "inventem" features que o código não faz.
>
> **Onde vive:** `docs/plans/CURRENT_REALITY.md`.
>
> **Quem atualiza:** o Claude Code no diagnóstico inicial, e o humano sempre que descobrir algo novo sobre o estado real.

**Data do diagnóstico:** YYYY-MM-DD
**Branch analisada:** main (commit `<sha>`)
**Autor do diagnóstico:** [humano + agente]

---

## 1. O que este projeto realmente faz hoje

> Descreva em 3–6 frases o que o sistema **efetivamente entrega** para o usuário final **hoje**, baseado em código rodando, não em intenção.

- ...
- ...

---

## 2. Rotas reais

> Endpoints que de fato existem e estão acessíveis. Confirme lendo o código, não o README.

| Método | Rota | Arquivo | Status | Notas |
|---|---|---|---|---|
| POST | `/api/v1/auth/login` | `apps/api/src/auth/login.ts` | funcional | sem rate limit |
| GET | `/api/v1/users/me` | `apps/api/src/users/me.ts` | funcional | retorna campos internos (PII leak potencial) |
| GET | `/api/v1/admin/*` | `apps/api/src/admin/*` | parcial | 3 endpoints, 1 quebrado |

---

## 3. Telas reais

| Rota UI | Arquivo | Estado | Notas |
|---|---|---|---|
| `/` | `apps/web/src/routes/index.tsx` | funcional | landing estática |
| `/login` | `apps/web/src/routes/login.tsx` | funcional | sem "esqueci senha" |
| `/dashboard` | `apps/web/src/routes/dashboard.tsx` | parcial | gráfico quebrado em mobile |

---

## 4. Banco real

- **Provider:** [Supabase / Postgres / MySQL / SQLite / ...]
- **Versão/plano:** [ex: Supabase free + plano pago Q3]
- **Migrations aplicadas em produção:** [ex: 0001..0017]
- **Tabelas ativas:**
  - `users` — X linhas (aprox) — último schema change: 2026-03
  - `sessions` — Y linhas
  - `orders` — Z linhas
- **Políticas RLS:** [mapa curto — quem pode ler/escrever o quê]
- **Índices/views manuais fora de migration:** [lista, se houver — risco alto]

---

## 5. Integrações reais

| Serviço | Finalidade | Status | Env var atual | Notas |
|---|---|---|---|---|
| Resend | envio de e-mail | ativo | `RESEND_API_KEY` | key no Vercel |
| Stripe | billing (assinaturas) | ativo | `STRIPE_SECRET` | webhook em `/api/webhooks/stripe` |
| Sentry | error tracking | configurado, mas sem DSN em prod | `SENTRY_DSN` | **risco** |

---

## 6. Testes existentes

- **Unit:** X arquivos — pastas: `tests/unit/`
- **Integration:** Y arquivos — pastas: `tests/integration/`
- **E2E:** [existe? com quais fluxos?]
- **Contract tests:** [sim/não]
- **Cobertura (se disponível):** [ex: 42%]
- **Testes conhecidos como instáveis:** [lista — `.skip` / flaky]

---

## 7. CI existente

- **Existe `.github/workflows/ci.yml`?** [sim/não]
- **Está verde hoje?** [sim/não — se não, por quê]
- **Rodar local funciona?** [sim/não]
- **Jobs cobertos:** lint? typecheck? unit? integration? e2e? build?
- **Gate de merge em `main`?** [sim/não]
- **Quem configurou?** [humano / herdado / nunca]

---

## 8. O que está quebrado hoje

> Lista honesta. Bugs confirmados, erros no console, features que prometeram e não funcionam.

- **BUG-001:** [descrição + repro + gravidade]
- **BUG-002:** ...

---

## 9. O que parece planejado mas não existe

> Código morto, feature flags ligadas apontando para stubs, rotas que retornam 501.

- ...

---

## 10. Features mencionadas em docs/README/Notion mas NÃO implementadas

> Crítico: alinha a documentação com a realidade. Sem isso, o PRD retroativo tende a "ganhar features" que ninguém construiu.

- [ ] "Exportar relatório PDF" — mencionado no README, não existe em código.
- [ ] "Modo escuro" — prometido em changelog, botão não faz nada.

---

## 11. Débito técnico

| Item | Onde | Impacto | Urgência |
|---|---|---|---|
| Tipos duplicados em `apps/web/types/` e `apps/api/types/` | ambos | drift | média |
| `scripts/` na raiz com 18 arquivos | raiz | bagunça | baixa |
| Nenhum schema Zod — só TypeScript interfaces | app inteiro | boundaries sem runtime check | alta |

---

## 12. Riscos técnicos

| Risco | Probabilidade | Impacto | Mitigação proposta |
|---|---|---|---|
| RLS pode estar permissivo demais | média | alto | auditoria antes de qualquer feature C/D nova |
| Migration 0017 não foi rodada em staging | alta | alto | validar antes de próxima migration |
| Sentry sem DSN em prod | alta | médio | configurar em F-XXX |

---

## 13. Riscos de produção

- **Usuários ativos estimados:** [N]
- **Receita/mês (se aplicável):** [R$/US$]
- **SLA implícito ou explícito:** [uptime, latência]
- **Horários de menor tráfego (janelas de deploy arriscado):** [ex: sáb 02h–05h BRT]
- **Dependências críticas externas:** [Stripe, Supabase, ...]

---

## 14. Pontos que NÃO devem ser tocados ainda

> Alimenta direto a Anti-SPEC. Liste tabelas, rotas, módulos que não aceitam alteração sem migration plan dedicado.

- Tabela `users` não pode ser alterada sem migration com backup em staging.
- Rota `/v1/legacy/*` tem 3 clientes externos — não alterar até migração combinada.
- Webhook Stripe em `/api/webhooks/stripe` — qualquer mudança exige teste de contrato com Stripe CLI antes.

---

## 15. Dependências humanas

- **Quem detém conhecimento tácito (bus factor = 1)?** [nome, módulo]
- **Credenciais guardadas com terceiros?** [lista]
- **Decisões estratégicas pendentes de stakeholder?** [lista]

---

## 16. Conclusão do diagnóstico

> 3–5 frases. A partir deste ponto, o projeto pode seguir para:
> - `/consultor-prd` retroativo (respeitando este CURRENT_REALITY)
> - `/SDD-avancado` retroativo (derivando RFs do que existe, não do desejado)
> - Ou, se o projeto estiver em produção instável, primeiro onda de estabilização antes de PRD.

Próxima decisão:
- [ ] Seguir para PRD retroativo (`/consultor-prd` em modo retroativo).
- [ ] Estabilizar CI antes de PRD (cenário C com CI vermelho/ausente).
- [ ] Reorganizar estrutura antes de PRD (cenário D).

---

*Este arquivo é documento vivo. Qualquer agente ou humano que descobrir algo novo sobre o estado real do sistema deve atualizá-lo antes de iniciar uma feature.*
