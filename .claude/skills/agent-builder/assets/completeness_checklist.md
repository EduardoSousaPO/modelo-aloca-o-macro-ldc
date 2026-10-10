# Checklist de Completude — Por Modo Operacional

Use o checklist do modo correspondente para verificar se está tudo pronto antes de avançar.

---

## MODO DISCOVERY — Checklist de saída

### Caso de uso definido
- [ ] Propósito do agente em uma frase clara
- [ ] Problema que resolve descrito com contexto real
- [ ] Motivação documentada (por que um agente e não uma automação simples)

### Usuário final
- [ ] Persona principal descrita (cargo, contexto, dia a dia)
- [ ] Canal de interação identificado
- [ ] Nível técnico do usuário avaliado
- [ ] Mais de um perfil? Se sim, todos mapeados

### Ações concretas
- [ ] 3-5 ações que o agente FAZ (não apenas responde) listadas
- [ ] Para cada ação: texto ou ação real no mundo?
- [ ] Mapa ação → risco → approval identificado
- [ ] Ações automáticas vs. sob demanda separadas

### Integrações
- [ ] Sistemas externos identificados (se houver)
- [ ] Tipo de acesso: leitura, escrita ou ambos
- [ ] Dados sensíveis identificados (se houver)
- [ ] Estratégia de proteção definida (se dados sensíveis)

### Restrições
- [ ] Lista do que o agente NUNCA pode fazer
- [ ] Lista do que requer aprovação humana
- [ ] Horário de funcionamento definido
- [ ] Tom, idioma e formato definidos

---

## MODO PRD — Checklist de saída

- [ ] PRD preenchido com todas as 16 seções do template
- [ ] Comportamentos com IDs (AG-001, AG-002...) e prioridades
- [ ] MoSCoW aplicado (Must/Should/Could/Won't)
- [ ] Critérios de aceite definidos para cada Must e Should
- [ ] Métricas de sucesso definidas com targets
- [ ] Riscos identificados com mitigações
- [ ] Critério de saída do MVP definido ("pronto quando...")
- [ ] Dúvidas pendentes listadas (bloqueantes separadas de não-bloqueantes)
- [ ] Usuário aprovou o PRD

---

## MODO ARQUITETURA — Checklist de saída

### LLM e canal
- [ ] LLM selecionado com justificativa e custo estimado
- [ ] Canal principal definido
- [ ] Método de acesso ao canal identificado (token, API)

### Tools
- [ ] Tool policy completa (cada tool: habilitada/desabilitada + motivo)
- [ ] Tools de alto risco (exec, browser): decisão documentada
- [ ] Exec approvals configurado se exec habilitado
- [ ] Sandbox Docker definido se exec habilitado

### Memória e dados
- [ ] O que vai para MEMORY.md especificado
- [ ] O que vai para Supabase especificado
- [ ] Tabelas necessárias identificadas
- [ ] Dados sensíveis com estratégia de proteção

### Skills
- [ ] Skills do ClawHub pesquisadas e avaliadas
- [ ] Skills custom especificadas (nome + responsabilidade)
- [ ] Build with Claude consultado para padrões relevantes

### Frontend
- [ ] Decisão tomada: Lovable / Next.js / sem frontend
- [ ] Se Lovable: telas principais definidas
- [ ] Se Next.js: componentes principais listados

### Guardrails
- [ ] Soft guardrails para SOUL.md listados
- [ ] Allowlist de usuários: modo decidido
- [ ] Gateway auth definido

### Infraestrutura
- [ ] VPS: status (a provisionar / já existe)
- [ ] Supabase: status (a criar / já existe)
- [ ] GitHub: status (a criar / já existe)
- [ ] Custo mensal estimado calculado

### Escopo MVP
- [ ] MoSCoW alinhado com o PRD
- [ ] Nenhum item bloqueante em aberto
- [ ] Usuário aprovou a especificação técnica

---

## MODO EXECUÇÃO — Checklist de saída

### Arquivos gerados
- [ ] CLAUDE.md — contexto completo para futuras sessões
- [ ] README.md — documentação do projeto
- [ ] soul.md — identidade, princípios, proibições, tom preenchidos
- [ ] config.json — tool policy correta aplicada
- [ ] memory.md.template — template sem dados reais
- [ ] Cada skill custom tem SKILL.md completo
- [ ] SQL schema com tabelas base + tabelas do negócio
- [ ] .github/workflows/deploy.yml — CI/CD
- [ ] .env.example — template com todas as variáveis
- [ ] decision_log.md — todas as decisões registradas
- [ ] .gitignore — protege credenciais e dados sensíveis

### Qualidade dos arquivos
- [ ] soul.md é específico (não genérico)
- [ ] config.json reflete exatamente a tool policy da arquitetura
- [ ] Skills custom têm triggers claros e passos concretos
- [ ] SQL schema tem RLS habilitado em todas as tabelas
- [ ] .env.example tem todos os placeholders necessários
- [ ] .gitignore inclui .env, memory.md, node_modules

---

## MODO INFRA — Checklist de saída

### VPS
- [ ] OpenClaw instalado (`openclaw --version`)
- [ ] OpenClaw rodando via systemd (`systemctl status openclaw` = active)
- [ ] Restart automático configurado (Restart=always, RestartSec=2)
- [ ] .env configurado com credenciais reais
- [ ] .env protegido (chmod 600)
- [ ] Arquivos do agente copiados para ~/.openclaw/
- [ ] `openclaw security audit` sem erros críticos

### Canal
- [ ] Canal conectado e testado
- [ ] Bot responde no Telegram/WhatsApp
- [ ] Logs mostram conexão ativa

### Supabase
- [ ] Projeto criado (região sa-east-1 para Brasil)
- [ ] Migration executada (tabelas criadas)
- [ ] RLS habilitado em todas as tabelas de dados de usuário
- [ ] MCP do Supabase instalado e testado no agente
- [ ] Service Role Key no .env do VPS (nunca no frontend)

### Frontend (se aplicável)
- [ ] Lovable: projeto criado e conectado ao Supabase
- [ ] ou Next.js: app criado com dependências Supabase
- [ ] Login funciona com Supabase Auth
- [ ] Dashboard mostra dados reais

### GitHub
- [ ] Repositório criado e conectado
- [ ] .env NÃO está no repositório
- [ ] GitHub Secrets configurados (VPS_HOST, VPS_USER, VPS_SSH_KEY)
- [ ] GitHub Actions testado (push → deploy automático)

### Backup e segurança
- [ ] Backup diário de ~/.openclaw configurado
- [ ] Tailscale ou acesso seguro configurado
- [ ] Gateway não exposto diretamente à internet

---

## MODO VALIDAÇÃO — Checklist final

### Teste funcional
- [ ] Agente responde no canal configurado
- [ ] Fluxo principal MVP funciona end-to-end (happy path)
- [ ] Agente lida com entrada inválida/incompleta
- [ ] Ações com approval disparam corretamente (se aplicável)
- [ ] Custo por interação dentro do estimado

### Critérios de aceite
- [ ] Todos os critérios MUST passam
- [ ] 80%+ dos critérios SHOULD passam
- [ ] Smoke tests passam (5 testes mínimos)

### Documentação
- [ ] CLAUDE.md atualizado com estado final
- [ ] decision_log.md completo
- [ ] README.md explica como rodar e contribuir

### Critério de conclusão
- [ ] Pelo menos 5 interações de teste reais sem erro
- [ ] Usuário consegue interagir e receber resultado correto no fluxo principal
