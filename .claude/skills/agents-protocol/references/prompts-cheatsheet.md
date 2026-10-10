# Prompts Cheatsheet — Harness v3.2 · Project Wiki + Fast Fix + Triage + MVP Lite

> **4 prompts core** + **1 prompt embutido em skill (`/triage-bugs`)** + **1 modo sem prompt (MVP Lite)**. Coluna vertebral operacional do v3.2.
>
> - **Prompt 0** — Fast Fix (bug urgente, classe A/B, < 30 min)
> - **Prompt 1** — Início de sessão
> - **Prompt 2** — Implementar feature (Standard / Deep Work / Production)
> - **Prompt 3** — QA do PR em Validation Mode
> - **Prompt 4** (em `skills/triage-bugs/SKILL.md`) — Triagem em lote de bugs do cliente
>
> **Modo sem prompt — MVP Lite** (validação de ideia < 1 semana, sem produção): só `TODO.md` + classe + branch + 1 teste no caminho crítico + commit + linha em `wiki/log.md`. Detalhes em `harness-v3.2-manual.md §14.5` e §22.

---

## 0. Fast Fix — Project Quick (NOVO v3.2)

> Cole para bug urgente em produção/desenvolvimento. Classe A ou B sem auth/payment/dados sensíveis/banco/env/deploy. Alvo: < 30 min do diagnóstico ao PR.
>
> Skill dedicada: `/fast-fix`. Detalhes e gates em `skills/fast-fix/SKILL.md`.

```
[FAST FIX — HARNESS v3.2 PROJECT QUICK]

Bug: [1 frase]
Onde dói: [arquivo/módulo/rota suspeita ou "investigar"]
Repro: [comando exato | passos UI | "ainda não tenho"]
Urgência: [demo em N min | cliente parado | produção quebrada | dev travado]

Execute, NA ORDEM. PARE em qualquer ■ e escale para Prompt 2.

1. SCREEN — 60s
   - Lê wiki/index.md.
   - Lê wiki/runbooks/ — algum runbook cobre? Se sim, SIGA RUNBOOK e pule para 7.
   - Lê wiki/log.md últimos 30d — bug recorrente? ≥ 2 ocorrências → ■ ESCALE para Deep Work.
   - Lê TODO.md §5 Bugs abertos.

2. GATE DE CLASSE — 30s
   - Confirme A ou B.
   - ■ Se toca auth/autorização/payment/billing/webhook financeiro/dados sensíveis/RLS/migration/env/deploy/integração crítica → SAIR: "FAST FIX ABORTADO — classe C/D, use Prompt 2."
   - ■ Diagnóstico é palpite → SAIR (escreva teste primeiro via Prompt 2).

3. REPRODUÇÃO — 5 min
   - UM teste falha do jeito esperado. Sem isso, ■ SAIR.

4. FIX — 10–15 min
   - Diff mínimo. Sem refactor adjacente. Sem mudar tipos em packages/shared/types/. Sem SPEC/PRD/Anti-SPEC.
   - ■ Precisa mexer fora do escopo do bug → ESCALE.

5. VALIDAÇÃO — 3 min
   - Teste do passo 3 passa.
   - npm run lint && npm run typecheck && npm test (CI N1).

6. WIKI MEMORY — 1 min
   - Linha em wiki/log.md:
     - [YYYY-MM-DD HH:MM] [BUGFIX] <descrição> — classe <A|B> — ref: PR #<N> | commit <sha>
   - Bug capaz de voltar? Crie/atualize wiki/runbooks/bug-<slug>.md.

7. PR / COMMIT
   - A: commit em main "fix(<area>): <descrição>".
   - B: branch fix/<slug>, PR com causa raiz + mudança + validação + runbook (se aplicável). CI verde antes de merge.

8. FECHAMENTO — 30s
   - TODO.md §5 → mover bug para Resolvido.
   - "FAST FIX OK em <T min> — PR #<N> — runbook: <sim/não>".

REGRAS DURAS:
- ■ Auth/payment/dados sensíveis tocados → SAIR.
- ■ Diff > 50 linhas ou > 3 arquivos → SAIR.
- ■ Tempo > 30 min → SAIR.
- ■ Migration/env/deploy → SAIR (escala para Production).
- Sem teste reproduzindo → não é fix.
- Sem entrada em wiki/log.md → não terminou.
- Sem CI N1 verde → não terminou.
```

---

## 1. Início de sessão

> Cole no Claude Code ao abrir o projeto (ou ao voltar depois de uma pausa).

```
[INÍCIO DE SESSÃO — HARNESS v3.2 · WIKI + VALIDATION MODE]

Leia nesta ordem (o que existir):
1. docs/wiki/index.md — mapa da Project Wiki (NOVO v3.2)
2. docs/wiki/context/<F-NNN>.md — Context Pack se existir tarefa ativa (NOVO v3.2)
3. TODO.md — estado + Feature Contract do item em andamento
4. AGENTS.md — papéis, classificação A/B/C/D, autonomia vs pausa vs BLOQUEADO
5. docs/specs/SPEC.md (só seções relevantes ao item em andamento) + Anti-SPEC (§6)
6. docs/plans/feature-contracts/<F-NNN>.md se existir (ou bloco inline no TODO)
7. docs/plans/CURRENT_REALITY.md se o projeto já existia antes do Harness
8. docs/plans/DECISIONS_LOG.md — linhas relacionadas à feature em andamento
9. docs/wiki/log.md — últimas entradas (≤ 7 dias) (NOVO v3.2)
10. docs/plans/risk-classification.md (testes mínimos por classe)
11. git status && git log --oneline -5

Responda neste formato EXATO:

ESTADO:
- Fase: [kickoff | spec | execução | manutenção]
- Feature em andamento: [F-NNN — nome OU "nenhuma"]
- Classe: [A | B | C | D | N/A]
- CI alvo: [N1 | N2 | N3 | N/A]
- DoR: [completa | incompleta — itens faltantes]
- Feature Contract: [presente | ausente — precisa criar antes de continuar]
- Próximo do backlog: [F-NNN — nome]
- Classe sugerida para o próximo: [A/B/C/D]
- Risco de reclassificação durante execução: [baixo | médio | alto — motivo em 1 linha]
- Decisões relevantes (DECISIONS_LOG): [linhas aplicáveis ou "nenhuma"]
- Wiki health: [verde | amarelo — rodar /wiki lint | vermelho]
- Context Pack: [presente em wiki/context/ | ausente — rodar /wiki context se feature ativa]
- Bloqueios: [lista ou "nenhum"]
- Git: [clean | mudanças pendentes — arquivos]

PRÓXIMA AÇÃO SUGERIDA:
→ [ação concreta em 1 linha]

AUTONOMIA:
- Posso continuar automaticamente? [SIM | NÃO]
- Se NÃO, motivo: [DoR incompleta em domínio sensível | Feature Contract ausente | reclassificação pendente | precisa tocar produção | precisa alterar PRD/SPEC/Anti-SPEC | outro]
- Decisão humana necessária: [pergunta objetiva OU "proponho preenchimento seguro: ..."]

Regras que vou aplicar nesta sessão:
- Features A podem ir direto em main se <30min, com teste e CI N1 verde.
- Features B/C/D exigem Feature Contract preenchido e matriz de validação.
- Classe D sempre pausa antes de tocar produção/banco/env.
- Se a feature mudar de natureza durante a execução, reclassifico antes de continuar (regra: suba, nunca desça).
- QA roda em Validation Mode — tento quebrar a feature antes de aprovar.
- Nunca aprovo PR sem evidência objetiva (matriz CA → teste → status → evidência).
```

---

## 2. Implementar feature

> Cole quando estiver pronto para começar a próxima feature. Substitua `F-NNN` pelo ID real.

```
[IMPLEMENTAR FEATURE — F-NNN · HARNESS v3.1 VALIDATION MODE]

Feature: [nome, ex: F-003 Login com e-mail/senha]

Execute o loop abaixo. PAUSE nas paradas explícitas (▲). BLOQUEIE e retorne erro objetivo nas paradas marcadas ■.

1. LEITURA
   - Ler item F-NNN no TODO.md (Feature Contract inline se existir).
   - Ler SPEC.md nas seções que cobrem os RFs desta feature.
   - Ler Anti-SPEC (SPEC §6) e listar quais itens podem colidir com esta feature.
   - Ler packages/shared/types/ relevantes.
   - Ler DECISIONS_LOG.md se houver linha relacionada ao domínio da feature.

2. CLASSIFICAÇÃO INICIAL
   - Confirmar classe A/B/C/D (ver risk-classification.md).
   - Determinar CI alvo (N1 para A/B, N2 para C, N3 para D).
   - Determinar testes mínimos obrigatórios (risk-classification.md §Testes mínimos).

3. FAIL FAST — DEFINITION OF READY
   - Validar cada item da DoR.
   - ■ Se DoR incompleta E a lacuna toca produto/produção/banco/auth/pagamento/dados sensíveis
     → retorne BLOQUEADO — DEFINITION OF READY INCOMPLETA, liste:
       - itens faltantes
       - por que impedem a implementação
       - qual pergunta precisa resposta do humano
       - se é decisão humana ou se consigo propor preenchimento seguro
   - ▲ Se DoR incompleta mas a lacuna é puramente operacional (naming, path, versão de lib)
     → proponha preenchimento seguro e prossiga após o usuário concordar.

4. FEATURE CONTRACT (B / C / D — obrigatório)
   - Se não existir Feature Contract para F-NNN, CRIE-O antes de escrever código.
   - Bloco inline no TODO.md se couber; senão, crie docs/plans/feature-contracts/F-NNN.md.
   - Campos mínimos: objetivo, escopo incluído/excluído, arquivos permitidos,
     arquivos proibidos, contratos Zod, testes mínimos por classe, comandos CI alvo,
     Anti-SPEC relevante, rollback plan (só D), matriz vazia.
   - Para classe A, bloco mínimo no TODO (objetivo + CA + teste) é suficiente.

5. CONTRATOS
   - Se há novo tipo/schema: atualize packages/shared/types/ PRIMEIRO.
   - Atualize CONTRACTS.md como espelho (não fonte).

6. BRANCH
   - Crie feat/<slug> a partir de main atualizada. (Classe A pode ir direto em main.)

7. TESTES PRIMEIRO
   - Escreva um teste FALHANDO para cada CA listado no Feature Contract.
   - Respeite o MÍNIMO POR CLASSE (risk-classification.md):
       A: opcional (se realmente isolado; senão vira B)
       B: ≥1 teste por CA (unit ou integration)
       C: ≥1 por CA crítico + ≥1 edge case + ≥1 negativo + integration se há API/auth/regra/dados + e2e se fluxo principal
       D: integration + smoke + staging + rollback + migration validation + e2e ou manual evidenciado
   - Testes "fake" (expect(true).toBe(true), teste que só renderiza, teste que mocka a regra sob validação) NÃO contam.

8. IMPLEMENTAÇÃO
   - Use EXATAMENTE os tipos de packages/shared/types/.
   - Só toque arquivos listados em "podem ser alterados" do Feature Contract.
   - ■ Se precisar alterar arquivo FORA da lista permitida:
       (a) Se toca produto/produção/banco/auth/pagamento/dados sensíveis → ▲ PAUSE, peça confirmação humana.
       (b) Senão, apresente justificativa (7 itens: arquivo, motivo, impacto, escopo, contrato, testes, reclassificação).
           Se aceita: atualize o Feature Contract (permitidos, testes, matriz) + registre no DECISIONS_LOG se útil + prossiga.
           Se não aceita ou ambígua: ■ retorne BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT.

9. AUTO-RECLASSIFICAÇÃO (monitorar continuamente)
   - Se a feature passar a alterar comportamento observável → A vira B.
   - Se passar a tocar auth/autorização/permissão/pagamento/billing/dados sensíveis/webhooks/regra central/fluxo principal → B vira C.
   - Se passar a tocar banco/migration/RLS/env/deploy/staging/produção/integração crítica → qualquer classe vira D (ou exige subtask D).
   - ■ Após reclassificar, atualize Feature Contract + testes mínimos + CI alvo + matriz + TODO.
     Se ainda não atualizou ao pedir APROVADO → retorno será BLOQUEADO — RECLASSIFICAÇÃO PENDENTE.
   - ▲ Se nova classe é C/D com risco alto (produção, banco, auth), PAUSE antes de continuar.

10. CI LOCAL (no nível correspondente à classe)
    - A/B: npm run lint && npm run typecheck && npm test
    - C:   acima + npm run test:integration (+ test:contract) + npm run build
    - D:   acima + npm run test:e2e + smoke test + migration validation

11. INFRA (classe D — se aplicável)
    - ▲ Gere a seção correspondente em docs/plans/cursor-brief.md (inclui Rollback + Staging + Smoke).
    - PAUSE. Espere confirmação de que o humano executou o Cursor Agent
      e validou critério de aceite em STAGING.
    - Só então continue.

12. MATRIZ DE VALIDAÇÃO
    - Preencha (ou atualize) a matriz CA → teste → tipo → status → evidência
      no Feature Contract da feature.
    - Seção "Validation Mode — tentativas de quebrar a feature" também preenchida para C/D.

13. DECISÕES OPERACIONAIS
    - Se durante a implementação surgiu decisão operacional que provavelmente volta ao debate
      (ex.: manter comportamento legado, não usar lib X, campo Y continua opcional),
      adicione uma linha em docs/plans/DECISIONS_LOG.md.
    - Se é decisão arquitetural com trade-off real → proponha ADR (não log).
    - Se é decisão de produto → PAUSE, peça autorização humana para editar PRD/SPEC.

14. DOCUMENTAÇÃO
    - Atualize CONTRACTS.md se contratos mudaram.
    - Atualize PLAN.md se fechou uma onda.
    - Crie ADR se decisão arquitetural ou dependência nova.
    - NUNCA altere PRD.md, SPEC.md ou Anti-SPEC sem pausa + confirmação humana.

15. PR / MERGE
    - Classe A trivial: commit e merge direto em main se CI N1 verde.
    - B/C/D: abra PR usando pr-description-template.md.
    - Espere CI verde (nível apropriado).

16. PÓS-MERGE (UPDATE MEMORY — v3.2)
    - Mova o item para "Concluído" no TODO.md com SHA/PR.
    - Registre bugs/ideias surgidos nas seções apropriadas.
    - Adicione 1 linha em docs/wiki/log.md tipo [RELEASE] ou [BUGFIX]:
      - [YYYY-MM-DD HH:MM] [RELEASE] F-NNN — <descrição curta> — ref: PR #N
    - Para classe C/D mergeada, escreva resumo de ≤ 5 linhas em docs/wiki/features/F-NNN.md.
    - Se a feature alterou um módulo significativamente, atualize docs/wiki/modules/<mod>.md.
    - Delete docs/wiki/context/F-NNN.md se existia (Context Pack consumido).

Restrições (violações = BLOQUEADO, não pausa simples):
- DoR incompleta em domínio sensível → BLOQUEADO — DEFINITION OF READY INCOMPLETA.
- Arquivo fora do contrato sem justificativa aceita → BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT.
- Anti-SPEC violada → BLOQUEADO — ANTI-SPEC VIOLADA.
- Reclassificação identificada sem contrato atualizado → BLOQUEADO — RECLASSIFICAÇÃO PENDENTE.

Restrições (violações = pausa para confirmação humana):
- Mudar PRD.md, SPEC.md ou Anti-SPEC.
- Tocar produção/banco real (classe D).
- Deletar arquivo importante.
- Criar dependência externa relevante.

Restrições (violações = recusa do agente):
- NÃO criar state/, handoffs/, *.json de estado.
- NÃO inventar tipos fora de packages/shared/types/.
- NÃO aprovar merge com CI vermelho ou matriz incompleta (B/C/D).
- NÃO aprovar com "teste fake" (ver risk-classification.md).
```

---

## 3. QA do PR — Validation Mode

> Cole antes de mergear. O agente **tenta quebrar a feature** antes de aprovar. Sem evidência, nunca `APROVADO`.

```
[QA — VALIDATION MODE · HARNESS v3.1]

Branch: [feat/<slug>]
Feature: F-NNN

Você está em VALIDATION MODE. Assuma que a implementação E os testes podem estar
incompletos ou errados. Seu trabalho não é confirmar que tudo passa — é TENTAR QUEBRAR
a feature antes de aprovar.

Execute, na ordem:

1. LER ARTEFATOS
   - Feature Contract inline no TODO.md (ou docs/plans/feature-contracts/F-NNN.md).
   - TODO.md (seção em andamento).
   - SPEC.md (RFs cobertos) + Anti-SPEC (§6).
   - DECISIONS_LOG.md (linhas relacionadas à feature, se houver).
   - packages/shared/types/ relevantes.
   - risk-classification.md (testes mínimos e exemplos de teste fake).

2. DIFF E ARQUIVOS ALTERADOS
   - Rodar: git diff main...HEAD
   - Listar arquivos alterados.
   - Para cada arquivo: está na lista "podem ser alterados"?
   - ■ Se NÃO e não há justificativa aceita (7 itens) com contrato atualizado
     → BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT.

3. DEFINITION OF READY & DEFINITION OF DONE
   - DoR do Feature Contract está completa?
   - ■ Se não, em domínio sensível → BLOQUEADO — DEFINITION OF READY INCOMPLETA.
   - DoD da classe respectiva (TODO.md §7) está cumprida?

4. AUTO-RECLASSIFICAÇÃO
   - A feature tocou auth/autorização/pagamento/dados sensíveis durante a execução?
     → Classe deveria ser ao menos C.
   - Tocou banco/migration/env/deploy/integração crítica?
     → Classe deveria ser D.
   - ■ Se sim e o Feature Contract não foi atualizado → BLOQUEADO — RECLASSIFICAÇÃO PENDENTE.

5. CONTRATOS
   - Algo em packages/shared/types/ mudou? CONTRACTS.md reflete?
   - Algum tipo foi inventado fora de packages/shared/types/? ■ se sim, violação.
   - Schemas Zod em todos os boundaries adicionados? ■ se não, violação.

6. ANTI-SPEC
   - Para cada item da Anti-SPEC relevante listado no Feature Contract,
     confirmar explicitamente: respeitado ou violado.
   - ■ Qualquer violação → BLOQUEADO — ANTI-SPEC VIOLADA.

7. TESTES MÍNIMOS POR CLASSE
   - Consultar risk-classification.md §Testes mínimos.
   - Para a classe da feature:
       A: se alterou comportamento e não tem teste → vira B, exigir teste.
       B: ≥1 teste por CA, unit ou integration.
       C: ≥1 por CA crítico + ≥1 edge case + ≥1 negativo + integration (se API/auth/regra/dados) + e2e (se fluxo principal).
       D: integration + smoke + staging + rollback + migration + e2e/manual evidenciado.
   - ■ Se algum mínimo está ausente → MUDANÇAS_SOLICITADAS (não BLOQUEADO, a menos que combine com outra violação).

8. DETECÇÃO DE TESTE FAKE
   - Leia os testes relevantes.
   - Marque como "fake" (não conta) qualquer teste que:
       - use expect(true).toBe(true) ou tautologia
       - só verifique renderização sem exercitar comportamento
       - mocke justamente a regra que deveria validar
       - tenha assertion genérica irrelevante
       - esteja em .skip ou .only
       - não exercite o CA declarado
   - Testes "fake" reduzem a cobertura efetiva — reavalie os mínimos por classe.

9. VALIDATION MODE — TENTE QUEBRAR
   Exercite mentalmente (B) ou rodando (C/D):
     (a) Inputs inválidos: string vazia, número fora da range, tipo errado.
     (b) Inputs no limite: tamanho máximo/mínimo.
     (c) Ausência de dados / estado vazio.
     (d) Permissões incorretas quando aplicável.
     (e) Chamadas repetidas / idempotência.
     (f) Edge cases óbvios: timezone, unicode, concorrência simples.
     (g) UI: comportamento vazio / loading / erro.
     (h) Fora de escopo: algo no diff que não era pra estar?
   Para cada categoria, registre na matriz "Validation Mode — tentativas de quebrar" do Feature Contract.
   Se encontrou cenário não coberto:
     - A/B: crie o teste agora.
     - C/D: solicite teste; se é produção, pause e peça humano.

10. MATRIZ DE VALIDAÇÃO (preenchida)
    | CA | Teste | Tipo | Status | Evidência |
    - Status: passou | falhou | não coberto.
    - Evidência: comando exato + arquivo:linha + log resumido.
    - ■ Qualquer CA "não coberto" ou "falhou" → resultado NÃO PODE ser APROVADO.

11. CI LOCAL (no nível da classe)
    A/B: lint + typecheck + unit
    C:   acima + integration + contract + build
    D:   acima + e2e + smoke + migration validation
    - ■ CI vermelho → MUDANÇAS_SOLICITADAS com o comando exato que falhou.

12. PRODUÇÃO (classe D)
    - cursor-brief.md inclui seção Rollback? ■ se não: BLOQUEADO.
    - Staging foi validado (log/print)? Feature flag se muda contrato público?
    - Smoke test pós-deploy planejado/executado?

13. DECISIONS_LOG
    - Encontrou comportamento aparentemente estranho?
      → Consulte DECISIONS_LOG antes de acusar bug.
      → Se há linha explicando, cite-a na evidência.

14. TODO E DOCS
    - TODO.md tem o item com Feature Contract preenchido e matriz completa?

15. WIKI (v3.2 — só se RESULTADO = APROVADO)
    - Após merge, garantir que o passo 16 do Prompt 2 será executado: linha em wiki/log.md, resumo em wiki/features/ (C/D), atualização de wiki/modules/ se aplicável, deleção do Context Pack consumido.
    - Se durante o QA encontrou contradição na wiki, registrar para `/wiki lint` e `/wiki repair` na próxima janela.

Responda EXATAMENTE neste formato:

RESULTADO: [APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO]

CLASSE DA FEATURE: [A | B | C | D]
CLASSE ORIGINAL vs ATUAL: [manteve | subiu de X para Y — motivo]
CI NÍVEL EXIGIDO: [N1 | N2 | N3]
CI NÍVEL RODADO LOCAL: [N1 | N2 | N3 | faltante]

ARQUIVOS ALTERADOS vs PERMITIDOS:
- [caminho] — [dentro do contrato | FORA — justificativa aceita/recusada]

CONTRATOS:
- [status: alinhado | divergente — detalhes]

ANTI-SPEC:
- [status: respeitado | violação detectada — item específico]

TESTES MÍNIMOS POR CLASSE:
- [cumprido | faltante — lista]

TESTE FAKE DETECTADO:
- [nenhum | lista — arquivo:linha + razão]

VALIDATION MODE — TENTATIVAS DE QUEBRAR:
| Categoria | Cenário | Resultado |
| inputs inválidos | ... | coberto/criado/solicitado |
| ausência de dados | ... | ... |
| permissões | ... | ... |
| idempotência | ... | ... |
| edge cases | ... | ... |
| UI vazio/loading/erro | ... | ... |
| fora de escopo alterado? | ... | não/sim (+arquivos) |

MATRIZ DE VALIDAÇÃO:
| CA | Teste | Tipo | Status | Evidência |
| CA-NNN | ... | ... | ... | ... |

CI LOCAL:
- lint / typecheck / unit / integration / contract / e2e / smoke / build — [verde | vermelho | N/A]

PRODUÇÃO (só D):
- cursor-brief com Rollback: [sim/não/N/A]
- staging validado: [sim/não/N/A]
- feature flag: [sim/não/N/A]
- smoke pós-deploy: [planejado/executado/N/A]

DECISIONS_LOG RELEVANTE:
- [linhas consultadas OU "nenhuma"]

ISSUES (se MUDANÇAS_SOLICITADAS ou BLOQUEADO):
1. [problema específico + caminho de fix concreta]
2. ...

Critérios de decisão (aplicar nesta ordem):
1. DoR incompleta em domínio sensível                       → BLOQUEADO
2. Arquivo fora do contrato sem justificativa aceita        → BLOQUEADO
3. Anti-SPEC violada                                         → BLOQUEADO
4. Reclassificação identificada sem contrato atualizado     → BLOQUEADO
5. Classe D sem rollback/staging                             → BLOQUEADO
6. Teste mínimo por classe ausente                           → MUDANÇAS_SOLICITADAS
7. Teste fake detectado em posição que deveria cobrir CA     → MUDANÇAS_SOLICITADAS
8. CI vermelho                                               → MUDANÇAS_SOLICITADAS
9. CA sem evidência objetiva                                 → MUDANÇAS_SOLICITADAS
10. Validation Mode pulado em C/D                             → MUDANÇAS_SOLICITADAS

Nenhuma das condições acima → APROVADO.

Regra final: Sem evidência, nunca APROVADO.
```

---

## Dicas de uso

- **Prompt 0 (Fast Fix)** é exceção, não a norma. Use para bug urgente A/B sem auth/payment/db. Se escalar, sai do modo automaticamente.
- **Nunca pule o prompt 1.** A sincronização com wiki/index, TODO.md, Feature Contract e DECISIONS_LOG evita retrabalho.
- **O prompt 2 é atômico.** Se no meio surgir CA novo ou arquivo fora da lista, o agente pausa ou retorna BLOQUEADO — responda, mas NÃO acumule escopo no mesmo ciclo.
- **O prompt 3 roda antes de TODO merge (B/C/D).** É o coração do Validation Mode. 2–4 min classe B; 5–10 min classe C/D.
- **Classe D sempre pausa** antes de tocar produção/banco/env. Se o agente não pausou, a DoR ou o contrato estão mal preenchidos.
- **Se o agente retornou BLOQUEADO**, ele está te protegendo. Resolva a causa, não tente contornar.
- **Se um prompt passa de 100 linhas ao ser personalizado**, a feature provavelmente precisa ser quebrada.
- **Antes de fechar a sessão, rode `/wiki context <F-NNN>`** se a tarefa continua. Próximo agente (você amanhã, Codex, Cursor) abre o pack e segue.
- **A cada 2-4 semanas ou antes de release grande, rode `/wiki lint`.** Não vire rotina diária — é checkpoint, não cerimônia.
