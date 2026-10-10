# Checklist Diário — Harness v3.2 · Project Wiki + Fast Fix

> Rotina mínima para manter o projeto saudável. **Máximo 10 itens.** Se você está gastando mais de 5 minutos nisso, está exagerando.

---

## Abrir o dia (3 itens)

- [ ] `git pull` na branch `main`.
- [ ] Abrir Claude Code e rodar o **Prompt 1 — Início de sessão** (lê `wiki/index.md` + `wiki/context/<atual>.md` + `TODO.md` + `AGENTS.md` + Feature Contract + `DECISIONS_LOG.md` + `wiki/log.md` recente + `git status`). Confirmar classe, CI alvo, DoR, risco de reclassificação, wiki health, autonomia SIM/NÃO.
- [ ] Decidir: **continuar feature atual** OU **iniciar próxima do backlog** OU **resolver BLOQUEADO** OU **bug urgente via `/fast-fix`**.

## Durante o dia (4 itens)

- [ ] Uma branch de feature por vez (ou `main` para classe A trivial < 30min).
- [ ] Testes antes da implementação, respeitando **mínimos por classe** (ver `risk-classification.md`). CI local no nível da classe verde antes de qualquer commit relevante.
- [ ] Se aparecer ideia/bug: registrar **agora** em `TODO.md` com classe estimada. Se for decisão operacional que voltará ao debate: linha em `DECISIONS_LOG.md`.
- [ ] Se a feature cresceu ou mudou de natureza: **reclassificar (suba, nunca desça)**, atualizar Feature Contract + testes + CI alvo, ou dividir.

## Fechar o dia (4 itens)

- [ ] Atualizar `TODO.md`: matriz de validação preenchida se item está em QA; Concluído → SHA/PR; em andamento → onde parou.
- [ ] Se tem PR aberto: rodar o **Prompt 3 — QA em Validation Mode** (tentei quebrar antes de aprovar) e mergear se APROVADO com evidência.
- [ ] **Update memory:** linha em `wiki/log.md` para qualquer release/bugfix do dia. Se a tarefa continua amanhã/em outro agente: `/wiki context <F-NNN>` para gravar handoff em `wiki/context/`.
- [ ] `git push` da branch atual.

---

## Sinais de que o dia foi bem

- `TODO.md` mais curto ou reordenado ao fim do dia.
- CI verde em `main` no nível correspondente.
- Zero itens "invisíveis" na cabeça.
- Nenhum PR aprovado sem matriz de validação **e seção Validation Mode** (C/D).
- Nenhuma operação classe D executada sem Rollback + staging.
- Nenhum BLOQUEADO silenciosamente contornado — BLOQUEADO é informação útil, não falha a esconder.
- `DECISIONS_LOG.md` continua curto (se estiver virando diário, revise).
- `wiki/log.md` ganhou ≥ 1 linha por release/bugfix do dia.
- Tarefa que ficou em aberto tem Context Pack em `wiki/context/` para o próximo agente/sessão.

## Cadência semanal/quinzenal (não diária)

- **A cada 2-4 semanas, ou antes de release grande:** rode `/wiki lint` (somente leitura). Se relatar amarelo/vermelho, rode `/wiki repair` na próxima janela disponível.
- **Antes de produção:** rode `/wiki lint` mesmo se não passou de 2 semanas. Resolva itens vermelhos antes de subir.
