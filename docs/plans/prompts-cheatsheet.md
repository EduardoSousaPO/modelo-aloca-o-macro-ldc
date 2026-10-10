# Prompts Cheatsheet — estrategia-macro-ldc-dados (Harness v3.2 · dados/quant)

> **Os 6 prompts do dia a dia deste projeto**, prontos para copiar e colar no briefing de um subagente
> Opus (ou na sessão interativa). Adaptados do cheatsheet genérico do Harness para um pipeline de dados que
> roda local e cujo risco dominante é **número errado chegando ao Comitê**, não indisponibilidade.
>
> | # | Prompt | Quando |
> |---|---|---|
> | **0** | Fast Fix | bug urgente classe A/B que não toca canônico/credencial/entregável |
> | **1** | Início de sessão | ao abrir o projeto ou voltar de pausa |
> | **2** | Implementar feature | qualquer F-NNN do `TODO.md` |
> | **3** | QA — Validation Mode de dados | antes de todo merge B/C/D, por subagente **distinto** |
> | **4** | Extrator de fonte | features B de extração (F-002…F-012) — especialização do Prompt 2 |
> | **5** | Orquestrador — abrir onda | o Fable briefando N subagentes em paralelo (`PLAN.md`) |
>
> **Data:** 2026-10-10 · **Referências:** `AGENTS.md`, `TODO.md`, `docs/specs/SPEC.md`,
> `docs/plans/PLAN.md`, `docs/plans/risk-classification.md`, `docs/plans/infra-ops.md`.
>
> **Ordem de leitura canônica** (igual em todos os prompts, `AGENTS.md §4`):
> `docs/wiki/index.md` → `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` → `TODO.md` item **F-NNN** →
> `AGENTS.md` → `docs/specs/SPEC.md` (**só os CAs do item** + **Anti-SPEC §10**) →
> `docs/contracts/CONTRACTS.md` + `packages/shared/schemas/` →
> `docs/research/fontes-de-dados.md` (**só a seção da fonte**).
>
> **As 5 evidências de dados** (`CLAUDE.md §9` / `AGENTS.md §5`), obrigatórias em toda matriz B/C/D:
> (1) log do `pytest`; (2) nº de linhas + `min`/`max` de data; (3) % de nulos por coluna crítica;
> (4) **3 valores conferidos contra a fonte original** (print/link); (5) classe C: **diff numérico** vs. a
> versão anterior do canônico, cada divergência explicada.

---

## 0. Fast Fix — Project Quick

> Para bug urgente: extrator quebrado, série com buraco novo, número que mudou sem mudança de código.
> **Só classe A ou B** que **não** toca `data/canonical/`, credencial ou entregável do Comitê.
> Alvo: < 30 min do diagnóstico ao PR. Skill dedicada: `/fast-fix`.

```
[FAST FIX — LDC MACRO · PROJECT QUICK]

Bug: [1 frase]
Onde dói: [fonte/módulo suspeito, ex. apps/pipeline/extract/sgs.py — ou "investigar"]
Repro: [comando exato | "ainda não tenho"]
Urgência: [job diário parado | série perdendo dia | revisão do Edu em N min | dev travado]

Execute NA ORDEM. PARE em qualquer ■ e escale para o Prompt 2.

1. SCREEN — 60 s
   - docs/wiki/index.md → atalhos por cenário.
   - docs/wiki/runbooks/ — algum runbook cobre? Se sim, SIGA O RUNBOOK e pule para 7.
   - docs/wiki/log.md (últimos 30 d) — já aconteceu? ≥ 2 ocorrências → ■ ESCALE (bug estrutural).
   - TODO.md §5 Bugs abertos · docs/plans/DECISIONS_LOG.md (pode ser decisão, não bug).

2. GATE DE CLASSE — 30 s
   - Confirme A ou B.
   - ■ Toca data/canonical/, schema canônico, alinhamento temporal, cálculo de retorno, definição de
     regime, credencial/API paga ou qualquer coisa já enviada ao Comitê → SAIR:
     "FAST FIX ABORTADO — classe C/D, use o Prompt 2."
   - ■ Diagnóstico é palpite → SAIR (escreva o teste primeiro, via Prompt 2).

3. REPRODUÇÃO — 5 min
   - UM teste falha do jeito esperado, sobre FIXTURE gravada em tests/fixtures/<fonte>/.
   - Sem fixture que reproduza → grave a fixture primeiro. Sem teste falhando → ■ SAIR.

4. FIX — 10-15 min
   - Diff mínimo. Sem refactor adjacente. Sem ALTERAR schema em packages/shared/schemas/
     (acrescentar é ok). Sem tocar SPEC/PRD/ESCOPO-EMAIL.
   - ■ Precisa mexer fora do escopo do bug → ESCALE.

5. VALIDAÇÃO — 3 min
   - Teste do passo 3 passa.
   - ruff check . && ruff format --check . && pytest tests/unit -m "not network"   (CI N1)
   - Se o bug era de valor: reconfira 1 valor na fonte original e cole o print/link.

6. WIKI MEMORY — 1 min
   - Linha em docs/wiki/log.md:
     - [YYYY-MM-DD HH:MM] [BUGFIX] <descrição> — classe <A|B> — ref: PR #<N> | commit <sha>
   - Pode voltar? Crie/atualize docs/wiki/runbooks/<slug>.md.

7. PR / COMMIT
   - A: commit em main — "fix(<fonte>): <descrição>".
   - B: branch fix/<slug> + PR com causa raiz, mudança, validação e runbook. CI N1 verde antes do merge.

8. FECHAMENTO — 30 s
   - TODO.md §5 → bug para Resolvido. "FAST FIX OK em <T min> — PR #<N> — runbook: <sim/não>".

REGRAS DURAS:
- ■ Camada canônica / credencial / entregável do Comitê tocados → SAIR.
- ■ Diff > 50 linhas ou > 3 arquivos → SAIR.   ■ Tempo > 30 min → SAIR.
- Sem teste reproduzindo sobre fixture → não é fix.
- Nenhum dado inventado, interpolado ou "plausível" para fechar a série (Anti-SPEC §10.1.1).
- Sem linha em wiki/log.md e sem CI N1 verde → não terminou.
```

---

## 1. Início de sessão

> Cole ao abrir o projeto ou ao voltar depois de uma pausa. Serve tanto para a sessão do Edu quanto para
> um subagente Opus que assume uma tarefa já começada.

```
[INÍCIO DE SESSÃO — LDC MACRO · HARNESS v3.2 · WIKI + VALIDATION MODE]

Leia NESTA ORDEM (o que existir):
1. docs/wiki/index.md — mapa da Project Wiki + atalhos por cenário
2. docs/product/ESCOPO-EMAIL-ALEXANDRE.md — fonte de verdade do escopo (imutável)
3. TODO.md — §0 contexto, §1 em andamento, §2 backlog, §4 bloqueios, §7 DoD
4. AGENTS.md — papéis, classe A/B/C/D, §9 autonomia/pausa/BLOQUEADO, §13 ondas, §14 gate D
5. docs/wiki/context/<F-NNN>.md — Context Pack, se há tarefa ativa
6. docs/plans/PLAN.md — qual ONDA estamos e o critério de saída dela
7. docs/specs/SPEC.md — só os CAs do item ativo + Anti-SPEC §10
8. docs/plans/DECISIONS_LOG.md — linhas relacionadas ao item ativo
9. docs/wiki/log.md — últimos 7 dias
10. docs/plans/risk-classification.md — testes mínimos por classe e "teste fake" em dados
11. git status && git log --oneline -5

Responda NESTE formato EXATO:

ESTADO:
- Fase: [kickoff | spec | execução | entrega | manutenção]
- Onda do PLAN.md: [Onda N — objetivo] · critério de saída: [1 linha]
- Feature em andamento: [F-NNN — nome OU "nenhuma"]
- Classe: [A|B|C|D] · CI alvo: [N1|N2|N3]
- DoR: [completa | incompleta — itens faltantes]
- Feature Contract: [presente inline no TODO | em docs/plans/feature-contracts/ | ausente]
- Próximo do backlog: [F-NNN — nome] · classe sugerida: [A|B|C|D]
- Risco de reclassificação: [baixo|médio|alto — motivo em 1 linha]
- Job diário F-009 rodou hoje? [sim — arquivo do dia em data/raw/anbima-ms/ | NÃO — dado perdendo]
- Estado do canônico: [inexistente | linhas de macro_quarterly / asset_returns_quarterly + hash]
- ADR-001 (lente de regime): [Proposta → publicação BLOQUEADA | Aceito → gate liberado]
- Bloqueios (TODO §4): [quais das 8 decisões travam o item ativo, ou "nenhum"]
- Decisões relevantes (DECISIONS_LOG): [linhas aplicáveis ou "nenhuma"]
- Wiki health: [verde | amarelo — rodar /wiki lint | vermelho]
- Git: [clean | mudanças pendentes — arquivos]

PRÓXIMA AÇÃO SUGERIDA:
→ [ação concreta em 1 linha, ancorada na onda atual do PLAN.md]

AUTONOMIA:
- Posso continuar automaticamente? [SIM | NÃO]
- Se NÃO: [DoR incompleta | Feature Contract ausente | reclassificação pendente | toca camada canônica
  (classe C) | publicação ao Comitê (classe D) | FONTE INDISPONÍVEL | ESPECIFICAÇÃO NÃO CONGELADA |
  precisa alterar ESCOPO-EMAIL/PRD/SPEC]
- Decisão humana necessária: [pergunta objetiva OU "proponho preenchimento seguro: ..."]

Regras que vou aplicar nesta sessão:
- Toda feature se justifica no e-mail do Alexandre; fora dele → pauso e registro a proposta.
- Nenhum dado inventado, interpolado ou estimado. Lacuna sem substituto → BLOQUEADO — FONTE INDISPONÍVEL.
- Classe C (camada canônica) pausa antes de começar; classe D (Comitê) segue os 8 passos de AGENTS §14.
- Fonte externa em teste só via fixture gravada; rede apenas sob @pytest.mark.network.
- QA é feito por subagente DIFERENTE do que implementou. Nunca aprovo meu próprio trabalho.
- Nenhum APROVADO sem as 5 evidências de dados.
```

---

## 2. Implementar feature

> Cole para qualquer F-NNN. Para features **B de extração de fonte**, use o Prompt 4 (é este, com o
> bloco de fonte já preenchido).

```
[IMPLEMENTAR FEATURE — F-NNN · LDC MACRO · HARNESS v3.2]

Feature: F-NNN — [nome exato como está no TODO.md]
Classe declarada: [A|B|C|D] · CI alvo: [N1|N2|N3] · Branch: [do item do TODO]

ARQUIVOS QUE VOCÊ PODE TOCAR: [copiar a lista "Arquivos" do Feature Contract]
ARQUIVOS PROIBIDOS: ESCOPO-EMAIL-ALEXANDRE.md · PRD.md · SPEC.md (inclusive Anti-SPEC §10) ·
  arquivos de outros agentes em docs/research/ · schema JÁ EXISTENTE em packages/shared/schemas/
  (acrescentar campo novo é permitido; alterar existente é pausa) · [+ arquivos congelados pela onda]

Execute o loop. ▲ = pausa e pergunta. ■ = retorne BLOQUEADO e pare.

1. LEITURA (nesta ordem — não pule, não leia o resto da SPEC)
   a. docs/wiki/index.md
   b. docs/product/ESCOPO-EMAIL-ALEXANDRE.md — em que item (A1..A7 / B1..B5 / C1) esta feature se encaixa
   c. TODO.md → item F-NNN completo (DoR, escopo incluído/excluído, arquivos, tabela de testes)
      + TODO.md §2.0 (regras herdadas por TODO contrato) + §7 DoD da classe
   d. AGENTS.md — §2 classe, §9 autonomia, §13 onda em curso, §15 Validation Mode
   e. docs/specs/SPEC.md — SÓ os CAs listados no item + Anti-SPEC §10 (liste quais itens podem colidir)
   f. docs/contracts/CONTRACTS.md + packages/shared/schemas/ — os schemas que esta feature usa
   g. docs/research/fontes-de-dados.md — SÓ a seção da fonte desta feature (endpoint, formato,
      cobertura, pegadinhas confirmadas) + docs/research/metodologia-regimes-macro.md se for feature de regime
   h. docs/plans/DECISIONS_LOG.md — substituição de fonte já decidida que afete esta feature

2. CLASSIFICAÇÃO + DoR
   - Confirme a classe (docs/plans/risk-classification.md §"Exemplos concretos deste projeto").
   - Determine os testes mínimos da classe e o CI alvo.
   - ■ DoR incompleta em item que toca camada canônica, credencial ou entregável do Comitê →
     BLOQUEADO — DEFINITION OF READY INCOMPLETA (liste os campos faltantes e a pergunta ao humano).
   - ▲ DoR incompleta só em detalhe operacional (nome de arquivo, path) → proponha e siga.
   - ■ A feature depende de regime e ADR-001 está em Proposta E o resultado seria publicado →
     BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA (implementar é permitido; publicar não).

3. FEATURE CONTRACT (B/C/D obrigatório)
   - Valide o contrato inline do TODO. Se passar de ~40 linhas, mova para
     docs/plans/feature-contracts/F-NNN.md e deixe o link no TODO.
   - Classe C: liste explicitamente o diff numérico que você vai produzir e contra qual versão.

4. CONTRATOS PRIMEIRO
   - Precisa de coluna/campo novo? Acrescente em packages/shared/schemas/ ANTES do código
     (pydantic p/ config e payload; pandera p/ DataFrame) e espelhe em CONTRACTS.md.
   - ■ Precisa ALTERAR schema existente → ▲ pausa (é classe C própria).

5. TESTES FALHANDO, UM POR CA
   - Fixture gravada da fonte em tests/fixtures/<fonte>/ — nunca dado sintético "plausível".
   - Mínimos: B = 1 teste por CA + 1 negativo de fonte (HTTP 200 com corpo de erro, payload vazio);
     C = 1 por CA crítico + 1 caso-armadilha de calendário + 1 de idempotência + contract/pandera;
     D = e2e + reprodutibilidade (2 execuções, mesmo sha256).
   - Proibido "teste fake" de dados: len(df) > 0 sem contagem mínima; mock da fonte com valor inventado;
     comparar o resultado com a própria fórmula reimplementada no teste; tolerância de float tão larga
     que erro de escala passa; @pytest.mark.network em teste que deveria rodar sobre fixture.

6. IMPLEMENTAÇÃO
   - Só os arquivos permitidos. Encoding explícito em todo leitor. Número pt-BR pelo normalizador único.
   - ■ Precisa de arquivo fora da lista: aplique o fluxo de 7 itens de AGENTS §18. Se toca canônico,
     credencial, Comitê, escopo ou arquivo congelado pela onda →
     BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT.
   - ■ Fonte não existe, está paga ou a série não cobre a janela e não há substituto acordado →
     BLOQUEADO — FONTE INDISPONÍVEL. Proponha substituto; NÃO interpole, NÃO estime, NÃO invente.

7. AUTO-RECLASSIFICAÇÃO (monitore sempre — suba, nunca desça)
   - Virou agregação trimestral dentro do canônico, cálculo de retorno, deflação, calendário, regime?
     → classe C. Virou credencial/API paga ou vai ao Comitê? → classe D.
   - ■ Reclassificou e não atualizou contrato/testes/CI/matriz → BLOQUEADO — RECLASSIFICAÇÃO PENDENTE.
   - ▲ Nova classe C ou D → pause antes de continuar.

8. CI LOCAL no nível da classe
   - N1: ruff check . && ruff format --check . && pytest tests/unit -m "not network"
   - N2: + pytest tests/integration tests/contract -m "not network" + build do canônico por fixtures
   - N3: + pytest tests/e2e -m "not network" + rodar o pipeline 2x e comparar sha256

9. MATRIZ DE VALIDAÇÃO + EVIDÊNCIAS DE DADOS (as 5)
   - Preencha a matriz no Feature Contract. Status ∈ {passou, falhou, não coberto}.
   - Classe C: anexe o diff numérico vs. a versão anterior, com CADA divergência explicada, e confirme
     a reconstrução completa de data/canonical/ a partir de zero.

10. MEMÓRIA E FECHAMENTO
   - 1 linha em docs/wiki/log.md ([RELEASE] ou [VALIDATION]) + atualize docs/wiki/modules/<fonte>.md.
   - Classe C/D mergeada: resumo de ≤ 5 linhas em docs/wiki/features/F-NNN.md.
   - Decisão operacional que volta ao debate → linha em DECISIONS_LOG.md. Trade-off arquitetural → ADR.
     Decisão de produto/escopo → ▲ pausa.
   - Se a onda está em curso, NÃO edite TODO.md / PLAN.md / wiki/log.md diretamente: devolva o texto
     pronto no relatório para o orquestrador aplicar (AGENTS §13).

RELATÓRIO FINAL (formato obrigatório):

FEATURE: F-NNN — <nome> · CLASSE: <A|B|C|D> (original → atual) · CI RODADO: <N1|N2|N3>
ITEM DO E-MAIL COBERTO: <A1..C1>
ARQUIVOS ALTERADOS vs PERMITIDOS:
- <caminho> — [dentro do contrato | FORA — justificativa aceita/recusada]
ANTI-SPEC VERIFICADA: <§10.x respeitado | §10.x VIOLADA — qual>
MATRIZ DE VALIDAÇÃO:
| CA | Teste | Tipo | Status | Evidência |
|---|---|---|---|---|
| CA-NNN | tests/.../test_x.py::test_y | unit/integration/contract/e2e | passou | <comando + log resumido> |
EVIDÊNCIA DE DADOS (os 5 itens):
1. log do pytest: <resumo: N passed, 0 failed>
2. nº de linhas e datas: <N linhas · min=YYYY-MM-DD · max=YYYY-MM-DD>
3. % de nulos por coluna crítica: <coluna: x,x%>
4. 3 valores conferidos na fonte: <data | valor obtido | valor na fonte | link/print>
5. diff numérico vs. versão anterior (só C): <N células mudaram — explicação de cada uma | N/A>
DECISÕES / SUBSTITUIÇÕES DE FONTE: <texto pronto para DECISIONS_LOG ou "nenhuma">
TEXTO PARA O ORQUESTRADOR APLICAR: <linhas de TODO.md, CONTRACTS.md e wiki/log.md>
PENDÊNCIAS / DÍVIDA: <lista ou "nenhuma">
VEREDITO: PRONTO PARA QA | BLOQUEADO — <estado exato>

O QUE NÃO FAZER:
- Não inventar, interpolar, estimar nem "plausibilizar" nenhum valor. Nem para ilustrar.
- Não misturar dado real e sintético sem coluna de origem; sintético só em tests/fixtures/.
- Não editar ESCOPO-EMAIL-ALEXANDRE.md, PRD.md, SPEC.md ou Anti-SPEC.
- Não apagar nem sobrescrever arquivo de outro agente em docs/research/.
- Não editar data/ à mão; não commitar data/raw, *.parquet, *.duckdb, .env.
- Não chamar fonte externa em teste de CI; não usar .skip/xfail nem instalar dependência sem ADR.
- Não aprovar o próprio trabalho — o QA é outro subagente (Prompt 3).
- Não mandar número nenhum ao Alexandre/Comitê: isso é classe D (AGENTS §14).
- Não criar scripts/ na raiz, state/, handoffs/ nem JSON de estado.
```

---

## 3. QA — Validation Mode de dados

> Cole antes de todo merge B/C/D. **Rode em um subagente Opus DIFERENTE do que implementou**
> (`AGENTS.md §14` — gerador ≠ avaliador). O trabalho não é confirmar que passa: é **tentar quebrar**.

```
[QA — VALIDATION MODE DE DADOS · LDC MACRO]

Feature: F-NNN · Branch: <feat/...> · Classe declarada: <A|B|C|D>
Você NÃO implementou esta feature e não deve corrigi-la — você a avalia.

Leia NESTA ORDEM:
1. docs/wiki/index.md
2. docs/product/ESCOPO-EMAIL-ALEXANDRE.md — a feature está no escopo pedido?
3. TODO.md → item F-NNN (Feature Contract + arquivos permitidos) + §7 DoD da classe
4. AGENTS.md §15 (Validation Mode) · §9 (BLOQUEADO) · §14 (gate D)
5. docs/specs/SPEC.md — os CAs do item + Anti-SPEC §10, item por item
6. docs/contracts/CONTRACTS.md + packages/shared/schemas/ — o output respeita o schema?
7. docs/research/fontes-de-dados.md — a seção da fonte (para conferir valores e pegadinhas)
8. docs/plans/risk-classification.md — testes mínimos + "teste fake na versão dados"
9. docs/plans/DECISIONS_LOG.md — antes de acusar bug, veja se é decisão registrada

Execute:
1. DIFF: git diff main...HEAD. Cada arquivo está na lista permitida? Algo fora do escopo mudou?
   ■ Fora da lista sem justificativa de 7 itens aceita → BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT.
2. DoR + DoD da classe cumpridos? ■ DoR incompleta em domínio sensível → BLOQUEADO.
3. CLASSE: a feature deveria ser mais alta? Tocou canônico/retorno/calendário/regime → C.
   Credencial ou vai ao Comitê → D. ■ Sem contrato atualizado → BLOQUEADO — RECLASSIFICAÇÃO PENDENTE.
4. ANTI-SPEC §10, item por item dos listados no contrato: respeitado ou violado.
   ■ Violação → BLOQUEADO — ANTI-SPEC VIOLADA (cite o item exato).
5. TESTES: mínimos da classe presentes? Leia os testes e marque os "fake" de dados —
   len(df) > 0 sem contagem mínima; mock com dado inventado em vez da fixture; nenhum caminho de erro
   com HTTP 200; comparação com a própria fórmula; tolerância de float larga demais; @pytest.mark.network
   usado para fugir do CI; schema validado contra DataFrame construído no próprio teste.
6. TENTE QUEBRAR (AGENTS §15) — rode de fato em C/D, raciocine em B:
   (a) buraco de série: feriado, trimestre sem divulgação, série que começa depois de 2006
   (b) revisão retroativa da fonte (IBGE revisa PIB): duplica linha ou é idempotente?
   (c) calendário: fim de trimestre, 31/12 em fim de semana, data de referência vs. divulgação (lag)
   (d) unidade e escala: % vs. fração, índice vs. variação, nominal vs. real, base 100 trocada
   (e) idempotência: rodar 2x → mesmo sha256?
   (f) fonte vazia / HTTP 500 / HTTP 200 com corpo de erro / payload truncado / JSON com null
   (g) ordenação e duplicidade do índice temporal
   (h) look-ahead: trimestre T classificado com dado divulgado depois do fim de T sem flag asof
   (i) algo fora do escopo foi alterado?
7. CONFIRA 3 VALORES contra a fonte original (não contra o teste). Canários conhecidos:
   IBOV 01/02/2006 = 38.484,84 · IMA-B 16/09/2003 = 723,070317 ·
   MSCI ACWI NETR 31/01/2006 = 121,3858 · CDI 2006 = 15,0271%.
8. MATRIZ: toda linha tem evidência objetiva e as 5 evidências de dados estão preenchidas?
9. CI no nível da classe, rodado por você: N1 / N2 / N3.
10. CLASSE D: os 8 passos do gate de AGENTS §14 estão cumpridos, na ordem?

RESPONDA EXATAMENTE:

RESULTADO: [APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO]
CLASSE: <declarada> → <correta> (manteve | subiu — motivo)
CI EXIGIDO / RODADO: <N1|N2|N3> / <N1|N2|N3>
ARQUIVOS ALTERADOS vs PERMITIDOS: <lista com veredito por arquivo>
ANTI-SPEC: <§10.x respeitado | §10.x VIOLADA>
TESTES MÍNIMOS DA CLASSE: <cumprido | faltante — lista>
TESTE FAKE DETECTADO: <nenhum | arquivo:linha + razão>
TENTATIVAS DE QUEBRAR:
| Categoria | Cenário testado | Resultado |
|---|---|---|
| buraco de série | ... | coberto / criei teste / solicitado |
| revisão retroativa | ... | ... |
| calendário | ... | ... |
| unidade e escala | ... | ... |
| idempotência (hash) | ... | ... |
| fonte vazia/erro | ... | ... |
| duplicidade de índice | ... | ... |
| look-ahead | ... | ... |
| fora de escopo | ... | não / sim (+arquivos) |
MATRIZ DE VALIDAÇÃO: | CA | Teste | Tipo | Status | Evidência |
EVIDÊNCIA DE DADOS (os 5): 1. log pytest · 2. linhas + min/max · 3. % nulos ·
  4. 3 valores conferidos (valor obtido | valor na fonte | link) · 5. diff numérico (C)
GATE CLASSE D (só D): <os 8 passos, um por linha, cumprido/faltante>
DECISIONS_LOG CONSULTADO: <linhas ou "nenhuma">
ISSUES (se não APROVADO): <problema + caminho de correção concreto, numerado>

CRITÉRIOS, nesta ordem:
1. DoR incompleta em domínio sensível                          → BLOQUEADO
2. Arquivo fora do contrato sem justificativa aceita           → BLOQUEADO
3. Anti-SPEC violada                                           → BLOQUEADO
4. Reclassificação pendente                                    → BLOQUEADO
5. Dado inventado/interpolado/estimado encontrado              → BLOQUEADO
6. Lacuna de série fechada sem substituto acordado             → BLOQUEADO — FONTE INDISPONÍVEL
7. Número de regime a publicar com ADR-001 em Proposta         → BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA
8. Classe D sem os 8 passos do gate (§14)                      → BLOQUEADO
9. Teste mínimo da classe ausente, ou teste fake no lugar dele → MUDANÇAS_SOLICITADAS
10. CI vermelho                                                → MUDANÇAS_SOLICITADAS
11. CA sem evidência objetiva, ou < 3 valores conferidos       → MUDANÇAS_SOLICITADAS
12. Diff numérico de classe C ausente ou inexplicado           → MUDANÇAS_SOLICITADAS
13. Validation Mode não exercitado em C/D                      → MUDANÇAS_SOLICITADAS

Nenhuma das condições → APROVADO.
Regra final: sem evidência, nunca APROVADO. "O script rodou sem erro" não é evidência.

O QUE NÃO FAZER:
- Não corrija a feature. Você avalia e devolve issues; quem corrige é o subagente executor.
- Não aprove porque o teste está verde — teste verde sobre fixture errada não vale nada.
- Não reescreva o Feature Contract para caber no que foi feito.
- Não edite ESCOPO-EMAIL/PRD/SPEC, docs/research/ alheio, TODO.md/PLAN.md durante a onda.
```

---

## 4. Extrator de fonte (features B de extração)

> Especialização do Prompt 2 para **F-002 … F-012** (ANBIMA S3, SGS, SIDRA, Tesouro, B3, Yahoo/MSCI,
> calendário, ANBIMA diário, Focus, FRED, Teva). Um subagente por fonte — arquivos disjuntos.

```
[EXTRATOR DE FONTE — F-NNN · <FONTE> · LDC MACRO]

Feature: F-NNN — extrator <FONTE>
Classe: B · CI alvo: N1 · Branch: <do item do TODO>
Seção da pesquisa: docs/research/fontes-de-dados.md §<A1|A2|A3|A4.1|A4.2|A5|B6|B7|B8|B9|...>
Item do e-mail coberto: <A1..A7 | B1..B5 | C1>
CAs da SPEC: <lista exata do item do TODO>

ARQUIVOS PERMITIDOS (só estes):
- apps/pipeline/extract/<fonte>.py
- tests/unit/test_<fonte>.py  (+ tests/contract/test_<fonte>_contract.py se houver valor-canário)
- tests/fixtures/<fonte>/*    (fixtures gravadas)
- docs/wiki/modules/<fonte>.md
ARQUIVOS PROIBIDOS: tudo o mais — em especial packages/shared/schemas/ já existentes (acrescentar campo
é permitido e deve ser avisado no relatório), TODO.md, PLAN.md, wiki/log.md, CONTRACTS.md (congelados
pela onda — devolva o texto no relatório), docs/research/, SPEC/PRD/ESCOPO-EMAIL.

LEITURA, NESTA ORDEM:
1. docs/wiki/index.md
2. docs/product/ESCOPO-EMAIL-ALEXANDRE.md — confirme o item que esta fonte atende
3. TODO.md → F-NNN (DoR, escopo incluído/excluído, tabela de testes) + §2.0 regras herdadas
4. AGENTS.md §6 (CI), §9 (BLOQUEADO), §13 (onda), §19 (convenções)
5. docs/specs/SPEC.md — só os CAs do item + Anti-SPEC §10
6. packages/shared/schemas/ — ExtractorConfig, raw_series, series_catalog
7. docs/research/fontes-de-dados.md §<da fonte> — endpoint exato, formato, cobertura medida, pegadinhas
   [CONFIRMADO] e fallbacks

ENTREGUE, nesta ordem:
1. FIXTURE GRAVADA em tests/fixtures/<fonte>/ — resposta real da fonte, salva em arquivo, com o nome
   dizendo data e recorte (ex.: ms261008.txt, sgs_433_2006_2016.json). Nunca dado sintético "plausível".
   Grave também UMA fixture de caminho de erro (corpo de erro com HTTP 200, payload vazio ou truncado).
2. EXTRATOR em apps/pipeline/extract/<fonte>.py:
   - usa o cliente HTTP de F-001 (UA de browser, retry, timeout, validação de shape)
   - encoding EXPLÍCITO no leitor; magic bytes antes de escolher o parser (PK = XLSX, "<" = HTML)
   - número pt-BR pelo normalizador único; datas em ISO-8601
   - grava em data/raw/<fonte>/ (imutável, versionado por data) e data/processed/ na FREQUÊNCIA NATIVA
     (nunca trimestral aqui — Anti-SPEC §10.4.28)
   - coluna de origem (source/series_id) em tudo; nenhuma coluna fora dos schemas
   - janela fatiada se a fonte limita (ex.: SGS, 10 anos por requisição)
3. IDEMPOTÊNCIA: rodar 2x no mesmo dia não duplica linha nem reescreve conteúdo diferente.
   Teste obrigatório. Se a fonte revisa o histórico, trate como vintage novo, não como sobrescrita.
4. TRÊS VALORES-CANÁRIO conferidos NA FONTE (não no teste), com data, valor e link/print. Use os já
   conhecidos quando a fonte for uma destas: IBOV 01/02/2006 = 38.484,84 ·
   IMA-B 16/09/2003 = 723,070317 · MSCI ACWI NETR 31/01/2006 = 121,3858 · CDI 2006 = 15,0271%.
   Para as outras fontes, escolha 3 datas: a primeira da série, uma do meio e a última.
5. TESTES (todos sobre fixture, nenhum em rede):
   - 1 teste por CA do item
   - 1 teste de contagem mínima esperada (NÃO len(df) > 0 — truncamento silencioso é o risco real)
   - 1 teste negativo: HTTP 200 com corpo de erro → levanta e NÃO grava
   - 1 teste de idempotência
   - 1 teste de valor-canário (tests/contract/) com tolerância justificada
   - teste de rede, se existir, marcado @pytest.mark.network e APENAS ele — é o único teste live,
     não roda no CI, serve para o Edu verificar a fonte à mão
6. docs/wiki/modules/<fonte>.md: endpoint, formato, cobertura real medida (min/max), pegadinhas,
   o que fazer quando a fonte cai.

■ PARE E RETORNE BLOQUEADO — FONTE INDISPONÍVEL se: a fonte não existe mais, exige credencial/pagamento,
ou a série não cobre a janela pedida e não há substituto já acordado no DECISIONS_LOG. Proponha o
substituto no relatório (fonte pedida / fonte usada / por quê / impacto na comparabilidade) e PARE.
NÃO interpole, NÃO estime, NÃO reconstrua série sintética, NÃO use janela rolante como backfill.

RELATÓRIO FINAL: o mesmo do Prompt 2, mais:
- COBERTURA REAL DA SÉRIE: <min date | max date | nº de observações | frequência nativa>
- FALTA PARA OS 20 ANOS? <não | sim — de quando começa e qual proxy/decisão proponho>
- PEGADINHAS CONFIRMADAS NA PRÁTICA: <o que a pesquisa previu e se bateu>
- FIXTURES GRAVADAS: <caminhos + o que cada uma representa>
- VALORES-CANÁRIO: <data | valor obtido | valor na fonte | link>
- CAMPO NOVO EM SCHEMA? <não | sim — qual, e o texto pronto para CONTRACTS.md>

O QUE NÃO FAZER:
- Não tocar em nenhuma outra fonte nem no canônico. Não agregar para trimestral.
- Não alterar schema existente, TODO.md, PLAN.md, wiki/log.md, CONTRACTS.md (onda em curso).
- Não chamar a fonte dentro de teste sem @pytest.mark.network.
- Não commitar o arquivo bruto se passar de 5 MB (ex.: CSV do Tesouro, 14,6 MB) — fixture é um recorte.
- Não fazer scraping de HTML de SPA (B3, ANBIMA Data) nem usar API protegida por reCAPTCHA.
```

---

## 5. Orquestrador — abrir uma onda

> Cole na sessão do **Fable** ao abrir uma onda do `PLAN.md`. Este prompt não produz código: produz **N
> briefings** e, no fim, a consolidação. O orquestrador não escreve extrator nem cálculo (`AGENTS.md §1`).

```
[ORQUESTRADOR — ABRIR ONDA N · LDC MACRO · HARNESS v3.2]

Você é o orquestrador (Fable). Você NÃO escreve código: distribui, checa evidência e commita.

PASSO 1 — PREPARAR (leitura)
- docs/plans/PLAN.md §2 → Onda N: features, paralelismo (‖), critério de saída.
- TODO.md → o Feature Contract inline de CADA feature da onda + §2.0 + §4 bloqueios.
- AGENTS.md §13 (ondas), §14 (QA/gate D), §2 (classe).
- Confirme: a onda anterior está verde no CI do nível alvo? Se não, NÃO abra esta.

PASSO 2 — MAPA DE ARQUIVOS (antes de qualquer briefing)
Monte a tabela e verifique que as listas são DISJUNTAS:

| Subagente | Feature | Classe | Arquivos permitidos (exclusivos) |
|---|---|---|---|
| S1 | F-002 ANBIMA S3 | B | apps/pipeline/extract/anbima_s3.py · tests/unit/test_anbima_s3.py · tests/fixtures/anbima/ · docs/wiki/modules/anbima.md |
| S2 | F-003 BCB SGS | B | apps/pipeline/extract/sgs.py · tests/unit/test_sgs.py · tests/fixtures/sgs/ · docs/wiki/modules/sgs.md |
| ... | ... | ... | ... |

- Dois subagentes com o mesmo arquivo na lista → quebre a onda em dois lotes. Não negocie isso.
- ARQUIVOS CONGELADOS PARA TODOS durante a onda (só o orquestrador escreve):
  TODO.md · docs/plans/PLAN.md · docs/wiki/log.md · docs/contracts/CONTRACTS.md ·
  packages/shared/schemas/* já existentes · docs/product/* · docs/specs/* · docs/research/*
- Acréscimo de campo em schema é permitido ao subagente, mas ele entrega o texto de CONTRACTS.md
  no relatório — não edita o espelho.

PASSO 3 — LIMITES
- Máximo 3-4 subagentes simultâneos. 7 features de extração → dois lotes.
- Classe C: no máximo 2 em paralelo e nunca duas na mesma tabela canônica.
- Classe D: roda sozinha, depois de todo o resto verde.
- Nenhum subagente faz o QA do que ele mesmo implementou (§14).

PASSO 4 — BRIEFAR (um prompt por subagente, em paralelo)
Para cada linha da tabela, monte o briefing com o Prompt 2 (ou o Prompt 4 se for extrator) preenchendo:
- Feature + classe + CI alvo + branch
- Ordem de leitura, com a SEÇÃO EXATA de docs/research/fontes-de-dados.md
- CAs da SPEC (copiados do item do TODO) e Anti-SPEC específica do item
- Arquivos permitidos (da tabela) e a lista de congelados
- Valor-canário esperado, quando houver
- Formato do relatório final (matriz + as 5 evidências de dados)
- A frase: "Se precisar de arquivo fora da lista, PARE e devolva — não edite."

PASSO 5 — RECEBER E CHECAR (não reimplementar)
Para cada relatório:
- [ ] Matriz completa, sem CA "não coberto"
- [ ] As 5 evidências de dados presentes (log, linhas+min/max, % nulos, 3 valores na fonte, diff se C)
- [ ] Valor-canário conferido NA FONTE, com link/print
- [ ] Fixture gravada (não sintética) e nenhum teste de rede fora de @pytest.mark.network
- [ ] Arquivos alterados ⊆ arquivos permitidos
- [ ] Anti-SPEC verificada item a item
- [ ] Nenhum BLOQUEADO sem encaminhamento
Faltando algo → devolva ao MESMO subagente com a lista de pendências.
Dúvida sobre a correção do número → abra o QA (Prompt 3) em um subagente DIFERENTE.

PASSO 6 — CONSOLIDAR (só o orquestrador)
- Aplique as linhas devolvidas: TODO.md (estado, matriz, Concluído com SHA), CONTRACTS.md (espelho),
  docs/wiki/log.md (1 linha por feature), DECISIONS_LOG.md (substituições de fonte).
- Rode o CI do nível da onda. Commite feature por feature (Conventional Commits, ref. F-NNN).
- Classe C mergeada: confirme reconstrução completa do canônico e diff numérico explicado.
- Feche a Onda N no PLAN.md com o critério de saída atendido (ou registre o que ficou devendo).

PASSO 7 — RELATÓRIO DA ONDA
ONDA N — <objetivo> · <aberta HH:MM / fechada HH:MM>
| Feature | Classe | Subagente | Veredito | CI | Evidência completa? | Commit |
CRITÉRIO DE SAÍDA: <atendido | parcial — o que falta>
BLOQUEIOS ABERTOS: <FONTE INDISPONÍVEL / ESPECIFICAÇÃO NÃO CONGELADA / decisão humana>
PRÓXIMA ONDA: <N+1 — pode abrir? sim/não e por quê>
DÍVIDA REGISTRADA NO TODO: <lista>

O QUE NÃO FAZER:
- Não escrever extrator, schema, cálculo ou teste. Se a tentação vier, abra outro subagente.
- Não abrir onda nova com a anterior vermelha no CI.
- Não dar o mesmo arquivo a dois subagentes.
- Não deixar subagente editar TODO.md / PLAN.md / wiki/log.md durante a onda.
- Não aceitar relatório sem as 5 evidências de dados — "rodou sem erro" não é evidência.
- Não usar o próprio implementador como QA.
- Não publicar nada ao Comitê fora do gate de 8 passos (AGENTS §14).
```

---

## Dicas de uso

- **Prompt 1 nunca se pula.** É o que impede reimplementar algo que já existe ou quebrar convenção de
  trimestre.
- **Prompt 0 é exceção, não norma.** No minuto em que o bug toca `data/canonical/`, ele sai do Fast Fix.
- **Prompt 2/4 é atômico.** Se no meio aparecer CA novo ou arquivo fora da lista, o subagente pausa ou
  devolve `BLOQUEADO` — responda, mas **não acumule escopo no mesmo ciclo**.
- **Prompt 3 roda sempre em outro subagente.** 2-4 min em classe B, 5-10 min em C/D. Se o mesmo agente
  implementou e avaliou, o resultado não conta como QA.
- **Prompt 5 é o único que escreve `TODO.md` durante uma onda.** Toda a consolidação passa por ele.
- **Se um prompt personalizado passa de ~120 linhas**, a feature está grande demais — quebre.
- **Antes de encerrar a sessão de uma feature viva:** `/wiki context <F-NNN>`.
- **A cada 2-4 semanas ou antes de uma entrega ao Comitê:** `/wiki lint` (e `/wiki repair` se vermelho).
