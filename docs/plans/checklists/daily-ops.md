# Checklist diário — estrategia-macro-ldc-dados

> Rotina mínima de um dia de execução. **Se levar mais de 5 minutos, está virando cerimônia.**
> Prompts em `docs/plans/prompts-cheatsheet.md` · regras em `AGENTS.md`.

## Abrir o dia (4 itens)

- [ ] **Job diário da ANBIMA (F-009) rodou?** `ls -la data/raw/anbima-ms/ | tail -3` — tem o arquivo do
      último dia útil, tamanho > 0? **Se não, rode à mão AGORA** (`infra-ops.md §2.4`). Janela rolante de
      ~20 d.u.: dia perdido não volta.
- [ ] `git pull` na `main` (ou `git init` + primeiro commit, se o repo ainda não existe).
- [ ] Rodar o **Prompt 1 — Início de sessão**. Confirmar: onda do `PLAN.md`, feature ativa, classe, CI
      alvo, DoR, status do ADR-001, bloqueios, autonomia SIM/NÃO.
- [ ] Decidir o dia: **continuar a feature atual** · **abrir a próxima onda (Prompt 5)** · **destravar um
      BLOQUEADO** · **bug urgente (`/fast-fix`)** · **≥ 2 problemas (`/triage-bugs`)**.

## Durante o dia (5 itens)

- [ ] Máximo 2 itens em `TODO.md §1`. Subagentes em paralelo só com **arquivos disjuntos**; `TODO.md`,
      `PLAN.md`, `wiki/log.md` e `CONTRACTS.md` ficam **congelados para os subagentes** durante a onda.
- [ ] **Teste falhando antes do código**, sempre sobre **fixture gravada** em `tests/fixtures/<fonte>/`.
      Rede só sob `@pytest.mark.network` e só no teste live.
- [ ] CI local no nível da classe verde antes de qualquer commit relevante:
      `ruff check . && ruff format --check . && pytest tests/unit -m "not network"` (N1).
- [ ] Número novo aparecendo? **Confira 3 valores na fonte original** (print/link) antes de seguir em
      frente. Lacuna sem substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`; nada de interpolar.
- [ ] A feature cresceu ou mudou de natureza (tocou canônico, calendário, retorno, regime, credencial,
      Comitê)? **Reclassifique antes de continuar** (suba, nunca desça) e atualize contrato + CI + matriz.

## Fechar o dia (5 itens)

- [ ] `TODO.md` atualizado: matriz preenchida no que está em QA; Concluído com SHA; em andamento com
      "onde parei".
- [ ] PR aberto? Rodar o **Prompt 3 (Validation Mode)** em um subagente **diferente** do que implementou.
      Mergear só com `APROVADO` + as **5 evidências de dados**.
- [ ] 1 linha em `docs/wiki/log.md` por release/bugfix/validação do dia. Substituição de fonte → também
      em `docs/plans/DECISIONS_LOG.md`.
- [ ] Tarefa que continua amanhã ou passa para outro subagente: `/wiki context <F-NNN>`.
- [ ] `git push`. Fechou onda? Marcar no `PLAN.md`.

## Sinais de que o dia foi bem

- O arquivo da ANBIMA do dia está no disco.
- `TODO.md` mais curto ou melhor ordenado do que na abertura.
- CI verde na `main` no nível da onda.
- Nenhum PR aprovado sem matriz + 5 evidências; nenhum QA feito pelo próprio implementador.
- Nenhum valor no canônico que você não saiba de onde veio.
- Nenhum `BLOQUEADO` contornado em silêncio — bloqueio é informação, não falha a esconder.
- Nenhum número saiu para o Alexandre fora do gate de 8 passos (`AGENTS.md §14`).

## Cadência não diária

- **Antes de cada entrega ao Comitê:** `/wiki lint`; resolver vermelhos; conferir `infra-ops.md §1`.
- **A cada 2-4 semanas:** `/wiki lint` → `/wiki repair` se amarelo/vermelho.
- **Semanal:** revisar `TODO.md §6` (parking lot) e `§4` (bloqueios) — alguma das 8 decisões foi
  respondida e destrava uma feature?
