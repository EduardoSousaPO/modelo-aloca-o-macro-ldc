# AGENTS.md — Harness v3.2 · Project Wiki + Fast Fix

> Contrato universal de agentes deste repositório (orquestrador Fable 5.1, subagentes Opus, sessões
> interativas). **Máximo: ~360 linhas.** Detalhes em `docs/`, `TODO.md`, `docs/wiki/`,
> `docs/plans/risk-classification.md` e `docs/plans/_templates/*`.
>
> **Natureza do projeto:** ferramenta interna de **dados/quant** — pipeline Python de séries macro e índices
> de ativos brasileiros + análise de regimes macro para o Comitê de Alocação da LDC Capital. **Não é SaaS,
> não é web.** Sem auth, sem pagamento, sem deploy (roda local). **Consequência prática:** o risco não é
> "derrubar o site" — é **entregar número errado para o comitê**. Toda regra abaixo protege a integridade
> da camada de dados canônica.

---

## 1. Papéis

| Papel | Agente | Escopo | Quando usar |
|---|---|---|---|
| **Orquestrador** | Fable 5.1 | Distribui tarefas, checa entregas, mantém `TODO.md` e a wiki coerentes | Sempre; **não executa** extração nem análise |
| **Executor** | Subagentes Opus | Código de extratores, transformações, schemas, testes, notebooks, Feature Contract | Toda feature A/B/C/D |
| **Avaliador** | CI (`.github/workflows/ci.yml`) + pytest + pandera | ruff, pytest unit/integration, validação de schema, reprodutibilidade | Automático em todo push/PR |
| **Dono do escopo** | Humano (Edu) + stakeholder (Alexandre Kaercher) | Aprova mudança de escopo, publica resultado para o Comitê | Classe D e qualquer divergência do e-mail de escopo |

> **Regra estrutural:** quem gera código nunca é quem valida. A separação Generator ↔ Evaluator é mantida
> pelo CI + testes de contrato de dados, não pela autoconfiança do agente. **Regra do orquestrador:** o
> Fable 5.1 distribui e checa — se começar a escrever extrator ou cálculo de retorno, perdeu-se a
> separação: pare e delegue a um subagente Opus.

---

## 2. Classificação de risco (obrigatória por feature)

Toda feature é classificada **antes** de começar. Ver `docs/plans/risk-classification.md`.

| Classe | Exemplos **neste projeto** | CI alvo | Feature Contract | Validação extra |
|---|---|---|---|---|
| **A** Trivial | ajuste de texto/markdown, renomear célula de notebook, docstring, gráfico cosmético, ajuste de `README` | N1 | opcional | não |
| **B** Normal | **novo extrator de fonte** (SGS, SIDRA, ANBIMA, B3), nova transformação, **agregação mensal→trimestral**, novo índice derivado, cache local de requisição | N1 + matriz | obrigatório (inline no TODO) | amostra conferida contra a fonte |
| **C** Crítica | **qualquer coisa que altere a camada de dados canônica**: schema do dataset-base, regras de alinhamento temporal (calendário, lag de divulgação, fim de trimestre), **cálculo de retornos** (acumulação, deflação por IPCA, anualização), definição de regime macro, janela de 20 anos | N2 | obrigatório (detalhado) | **obrigatório**: diff numérico vs. versão anterior + reconstrução completa de `data/canonical/` |
| **D** Publicação/Credencial | **publicar resultado para o Comitê** (relatório/planilha final enviada ao Alexandre), uso de **credencial ou API paga**, mudança que altera número já apresentado ao Comitê | N3 | obrigatório + `docs/plans/infra-ops.md` com rollback | **obrigatório**: revisão humana + registro em `wiki/log.md` + versão congelada do dataset |

Em dúvida entre duas classes, escolha a mais alta. **Por que C é tão amplo aqui:** erro na camada canônica
(um trimestre desalinhado, um retorno acumulado errado, um IPCA aplicado duas vezes) **contamina todo o
modelo** a jusante sem levantar exceção — falha silenciosa é o modo de falha dominante deste projeto.

---

## 3. Onde vai cada coisa

```
estrategia-macro-ldc-dados/
├── AGENTS.md · CLAUDE.md · TODO.md · README.md · pyproject.toml
├── docs/
│   ├── product/ESCOPO-EMAIL-ALEXANDRE.md  ← FONTE DE VERDADE DO ESCOPO (não editar)
│   ├── product/PRD.md                 ← o quê e por quê (/consultor-prd)
│   ├── research/                      ← pesquisas de fontes e metodologia (vários agentes escrevem)
│   ├── specs/SPEC.md                  ← o que o pipeline faz + Anti-SPEC (sagrada)
│   ├── contracts/CONTRACTS.md         ← espelho legível de packages/shared/schemas/
│   ├── plans/                         ← risk-classification.md (quente), PLAN, CURRENT_REALITY,
│   │                                     DECISIONS_LOG, infra-ops.md, _templates/, feature-contracts/
│   ├── wiki/                          ← index · log · overview · architecture + modules/ features/
│   │                                     runbooks/ context/  (memória sintetizada)
│   └── decisions/adr/                 ← 1 arquivo por decisão arquitetural
├── apps/pipeline/                     ← extração + transformação + carga (código executável)
├── apps/analysis/                     ← notebooks, regimes macro, relatórios
├── packages/shared/schemas/           ← FONTE DE VERDADE dos contratos de dados (Pydantic + pandera)
├── data/raw/<fonte>/                  ← resposta crua da fonte, imutável (NÃO versionado)
├── data/processed/                    ← limpo/tipado por fonte (NÃO versionado)
├── data/canonical/                    ← dataset-base trimestral alinhado (NÃO versionado)
├── tests/unit|integration|contract|e2e/  (+ tests/fixtures/ com respostas gravadas das fontes)
├── infra/                             ← scripts auxiliares de ambiente
└── .github/workflows/ci.yml
```

**Pastas que NUNCA existem:** `state/`, `handoffs/`, `AGENT-BRIEFS/`, `progress.jsonl`, `scripts/` na raiz.

**Regra de ouro dos dados:** `data/` é **reconstruível**. Nada em `data/` é fonte de verdade — a fonte é o
**script que o produz**. Se um dataset só existe no disco de alguém, ele não existe.

---

## 4. Feed Forward — o que orienta o agente ANTES da execução

Antes de escrever qualquer linha, o agente lê:
1. **`docs/wiki/index.md`** — mapa da Project Wiki + atalhos por cenário.
2. **`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`** — escopo pedido. Toda feature se justifica aqui.
3. **`docs/wiki/context/<F-NNN>.md`** — Context Pack se a tarefa já foi iniciada.
4. `TODO.md` — item da feature + Feature Contract (inline ou em `docs/plans/feature-contracts/`).
5. `docs/specs/SPEC.md` (RFs, CAs, **Anti-SPEC §6**) + `docs/contracts/CONTRACTS.md` e
   `packages/shared/schemas/` (contratos, fonte em Pydantic/pandera).
6. `docs/research/` — o que já foi levantado sobre a fonte (endpoint, formato, limites, pegadinhas).
7. `docs/plans/CURRENT_REALITY.md` e `docs/wiki/log.md` — estado real e últimos eventos.
8. Definition of Ready do item — completa; senão, **pausa** e resolve primeiro.

> A wiki é **memória sintetizada**, NUNCA fonte de verdade. Em conflito, valem as fontes
> (ESCOPO-EMAIL / PRD / SPEC / schemas Pydantic-pandera / ADR).

---

## 5. Feedback — o que valida DEPOIS da execução

Toda feature B/C/D precisa de **evidência objetiva** por CA antes do merge:
- Matriz CA → teste → tipo → status → evidência (Feature Contract ou `_templates/VALIDATION-MATRIX-template.md`);
  CI por nível correspondente à classe (§6).
- **Evidência específica de dados** (além do teste verde): nº de linhas + intervalo de datas (`min`/`max`);
  % de nulos por coluna crítica; **3 valores conferidos contra a fonte original** (print, CSV, página do
  BCB/IBGE/ANBIMA); para C, **diff numérico** vs. a versão anterior do canônico com cada divergência explicada.
- Autorrevisão no **QA do PR**: retorna **APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO**.
- **Nunca APROVADO sem evidência.** "O script rodou sem erro" **não é** evidência.

---

## 6. CI por níveis

| Nível | Contém | Obrigatório para |
|---|---|---|
| **N1** | `ruff check` + `ruff format --check` + `pytest tests/unit` | A, B |
| **N2** | N1 + `pytest tests/integration tests/contract` (schemas pandera sobre fixtures) + build do dataset canônico a partir de fixtures | B relevante, C |
| **N3** | N2 + `pytest tests/e2e` (pipeline ponta a ponta) + conferência de reprodutibilidade (rodar duas vezes → mesmo hash) | C crítica, D |

Testes de rede ficam marcados `@pytest.mark.network` e **não** rodam no CI. Fonte externa em teste é sempre
**fixture gravada** em `tests/fixtures/`, nunca chamada viva.

---

## 7. Protocolo de geração de código

Ao implementar uma feature, o agente:
1. **Valida a classificação** (A/B/C/D). Se a estimativa mudar, reclassifica antes de codar (§16).
2. **Valida a Definition of Ready** do item. Incompleta → **pausa**.
3. **Checa o escopo contra `ESCOPO-EMAIL-ALEXANDRE.md`.** Fora do e-mail → pausa e registra proposta.
4. Para B/C/D, **cria ou valida o Feature Contract** (inline no TODO).
5. **Usa os schemas de `packages/shared/schemas/`** — nunca inventa DataFrame com colunas ad hoc. Se faltar
   schema, adiciona lá primeiro (Pydantic para config/payload de API, pandera para DataFrame).
6. **Escreve testes falhando** para cada CA antes do código, com fixture da fonte.
7. **Implementa** respeitando os arquivos permitidos no Feature Contract e a **Anti-SPEC**.
8. **Roda o CI local** no nível correspondente à classe.
9. **Preenche a matriz de validação** (CA → teste → evidência) + evidências de dados do §5.
10. **Atualiza `TODO.md`** com PR/SHA e **1 linha em `wiki/log.md`**.

Se encontrar algo fora do Feature Contract, **pausa** e consulta antes (§18).

---

## 8. O que o agente executor PODE e NÃO PODE editar (sem autorização)

**PODE** atualizar no fluxo normal:
- `TODO.md` (estado, Feature Contract inline, matriz), `docs/contracts/CONTRACTS.md` (espelho dos schemas),
  `docs/plans/PLAN.md` ao fechar onda, ADRs em nova decisão arquitetural clara,
  `docs/plans/infra-ops.md` (classe D), `CURRENT_REALITY.md` em diagnóstico
- `docs/wiki/log.md`, `runbooks/*.md`, `context/*.md`, `modules/*.md`, `features/*.md`
- código em `apps/pipeline/`, `apps/analysis/`, `packages/`, `tests/`, `infra/`
- conteúdo de `data/raw|processed|canonical` **via script reprodutível** (nunca à mão)

**NÃO PODE** alterar sem autorização humana explícita:
- `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` — **imutável** (mudança de escopo vai para `DECISIONS_LOG`/ADR);
  `docs/product/PRD.md`, `docs/specs/SPEC.md`, Anti-SPEC (§6 do SPEC)
- arquivos de outros agentes em `docs/research/` (pode criar os seus; **não apaga nem sobrescreve** os alheios)
- schema do dataset canônico e regras de alinhamento temporal / cálculo de retorno (classe C — exige contrato)
- decisões estratégicas aprovadas e arquitetura aprovada em ADR
- `wiki/overview.md` quando contradiz PRD; `wiki/architecture.md` quando contradiz SPEC (ajuste a fonte primeiro)

---

## 9. Autonomia vs pausa vs BLOQUEADO

**CONTINUE automaticamente quando:** a tarefa está dentro do Feature Contract e os arquivos alterados estão
na lista permitida; os testes necessários existem ou estão sendo criados conforme os CAs; não há alteração
destrutiva em `data/` fora de script reprodutível; é classe A/B sem toque na camada canônica; e o escopo não
muda frente ao e-mail do Alexandre.

**PAUSE e peça confirmação humana quando:**
- Precisar mudar `ESCOPO-EMAIL-ALEXANDRE.md`, `PRD.md`, `SPEC.md` ou Anti-SPEC, ou alterar escopo da
  feature (CA novo, arquivo fora da lista com risco).
- Precisar **alterar schema canônico, alinhamento temporal ou cálculo de retorno** (classe C).
- Precisar **publicar resultado para o Comitê** ou **usar credencial/API paga** (classe D).
- Uma fonte prevista no e-mail **não existir ou estar paga/indisponível** → proponha substituto, não invente série.
- Encontrar divergência material entre duas fontes para a mesma série.
- Precisar deletar arquivo ou dataset relevante, ou criar dependência externa nova (ADR).
- A feature crescer além do combinado (reclassifique antes).

**BLOQUEADO — retorne erro objetivo, não prossiga — quando:**
- **DoR incompleta** → `BLOQUEADO — DEFINITION OF READY INCOMPLETA`. Liste os campos faltantes.
- **Arquivo fora da lista permitida sem justificativa aceita** → `BLOQUEADO — ARQUIVO FORA DO FEATURE CONTRACT` (§18).
- **Anti-SPEC violada** → `BLOQUEADO — ANTI-SPEC VIOLADA`. Identifique o item exato.
- **Reclassificação pendente** → `BLOQUEADO — RECLASSIFICAÇÃO PENDENTE` (§16).
- **Dado não localizado e sem substituto acordado** → `BLOQUEADO — FONTE INDISPONÍVEL`. **Nunca** preencha
  com estimativa, interpolação não documentada ou valor inventado para "fechar" a série.

**FAST FIX (Project Quick):** bug urgente classe **A ou B** que **não toca camada canônica, credenciais nem
entregável do Comitê**, < 30 min do diagnóstico ao PR. Usa `/fast-fix`. Se escalar para C/D, **sai do modo**.

**MVP LITE:** exploração rápida (notebook de sondagem de fonte, teste de endpoint) que não produz dado
canônico nem alimenta entregável. Mantém só: `TODO.md` + classe + 1 teste no caminho crítico + commit +
linha em `wiki/log.md`. **Se o resultado virar insumo do modelo, migra para Standard imediatamente.**
**TRIAGE:** com ≥ 2 problemas na mesma janela (série quebrada, extrator falhando, divergência de número),
use `/triage-bugs` antes de qualquer fix — nunca começa fix automaticamente.

---

## 10. Branches e PRs

- **Branches:** `feat/<slug>`, `fix/<slug>`, `data/<slug>` (nova fonte), `chore/<slug>`. **Classe A** pode
  ir direto em `main` se < 30 min, com teste e CI N1 verde local. **B, C, D** exigem PR e CI verde; **C e D**
  exigem revisão humana; **D** exige dataset congelado + registro em `wiki/log.md`.
- Conventional Commits referenciando o item do TODO. **Nunca** commitar dado bruto > 5 MB.

---

## 11. Quando acionar um subagente Opus dedicado

O orquestrador Fable abre subagente próprio quando a tarefa é: **pesquisa de fonte** (endpoint, auth,
formato, limite) → escreve em `docs/research/`; **novo extrator** de uma fonte (um subagente por fonte evita
contenção de arquivo); **revisão numérica independente** de cálculo classe C (quem calculou não confere);
**relatório do Comitê** (classe D, com revisão humana antes do envio). Cada subagente recebe: objetivo,
arquivos que pode tocar, arquivos proibidos, critério de aceite e o que devolver no relatório. Operações
classe D ganham seção em `docs/plans/infra-ops.md` com **Rollback**.

---

## 12. O que o agente NUNCA faz

- **Inventa dado.** Nem para preencher lacuna, nem para "ilustrar", nem em notebook sem rótulo `FAKE`.
  Nem mistura dado real com sintético no mesmo DataFrame sem coluna de origem.
- Edita arquivo em `data/` à mão (tudo via script reprodutível e versionado).
- Commita dado bruto > 5 MB, `.parquet`, `.duckdb`, `.env` ou credencial.
- Desabilita teste ou usa `.skip`/`xfail` sem ADR; adiciona dependência nova sem ADR.
- Sobrescreve ou apaga trabalho de outro agente em `docs/research/`.
- Altera `ESCOPO-EMAIL-ALEXANDRE.md`, `PRD.md`, `SPEC.md` ou Anti-SPEC sem autorização.
- Aprova PR sem matriz de validação preenchida (B/C/D); cria `scripts/`, `state/`, `handoffs/` ou JSON de estado.

---

## 15. Validation Mode (obrigatório no QA)

No QA do PR, o agente assume que a implementação e os testes podem estar errados e **tenta quebrar** a
feature de forma controlada antes de aprovar. **Regras (sempre, para B/C/D) — versão dados:**
1. Antes de aprovar, tente quebrar a feature.
2. **Buracos de série:** feriado, trimestre sem divulgação, série que começa depois de 2006.
3. **Revisão retroativa** da fonte (IBGE revisa PIB) — o pipeline é idempotente ou duplica linha?
4. **Calendário:** fim de trimestre, data de referência vs. data de divulgação (lag).
5. **Unidade e escala:** % vs. fração, índice vs. variação, nominal vs. real, base 100 trocada.
6. **Idempotência:** rodar duas vezes gera o mesmo output (hash igual).
7. **Resposta vazia ou erro da fonte** (HTTP 500, payload truncado, JSON com `null`); **ordenação e
   duplicidade** de índice temporal (datas repetidas, fora de ordem).
8. Verifique se algo **fora do escopo** foi alterado (diff vs. arquivos permitidos).
9. Confira **3 valores contra a fonte original**; divergência não explicada ou CA sem evidência objetiva →
   `MUDANÇAS_SOLICITADAS`. **Nunca `APROVADO`** nesses casos.

Testes mínimos por classe e exemplos de "teste fake" proibido vivem em `docs/plans/risk-classification.md`.

---

## 16. Auto-reclassificação de risco

Se a natureza da feature mudar durante a implementação, **reclassifique antes de continuar**. Regra:
**suba, nunca desça.** Gatilhos:

- **A → B:** passa a alterar **valor ou estrutura** de qualquer output (não é mais só texto/cosmético).
- **B → C:** passa a tocar **schema canônico, alinhamento temporal, cálculo de retorno, deflação,
  agregação trimestral, definição de regime macro** ou qualquer número que alimente o modelo.
- **qualquer → D:** passa a tocar **credencial/API paga**, o resultado será **enviado ao Comitê**, ou
  altera número **já apresentado** ao Comitê.

**Procedimento:** (1) pause se a nova classe é C/D; (2) atualize o Feature Contract; (3) recalcule testes
mínimos; (4) atualize o CI alvo; (5) atualize a matriz; (6) registre nota no `TODO.md` e linha
`RECLASSIFY` em `wiki/log.md`; (7) continue só se §9 permitir.

---

## 17. DECISIONS_LOG (memória operacional leve)

`docs/plans/DECISIONS_LOG.md` é opcional mas recomendado — complementa ADRs sem substituí-los.
- **ADR** → decisão arquitetural com trade-off real (DuckDB vs. Parquet puro, lib de HTTP, cache).
- **DECISIONS_LOG** → decisão operacional que voltará ao debate (usamos IBC-Br em vez de PIB trimestral do
  IBGE; IFIX segmentado sem série oficial e usamos proxy X; trimestre = fim de período).
- **TODO.md** → estado + Feature Contract + matriz. **ESCOPO-EMAIL / PRD / SPEC / Anti-SPEC** → escopo e
  comportamento; o agente **não edita** sem autorização.

Toda **substituição de fonte** autorizada pelo Alexandre ("fique à vontade para ajustes caso não localize
estes dados") entra no DECISIONS_LOG com: fonte pedida, fonte usada, por quê, impacto na comparabilidade.

---

## 18. Arquivo fora do Feature Contract — fluxo de justificativa

**Padrão: BLOQUEADO.** **Caminho de escape (autonomia em A/B sem risco):** justificativa explícita com
(1) qual arquivo; (2) por quê; (3) impacto (superfície do diff, módulos tocados); (4) se altera escopo;
(5) se exige atualizar o Feature Contract; (6) se exige novos testes; (7) se exige reclassificação (§16).
Se a justificativa é puramente operacional e **não** toca camada canônica, credencial, entregável do Comitê
nem escopo: atualize o Feature Contract, registre no DECISIONS_LOG se útil, e continue. Se toca qualquer um
desses domínios: **pausa** e pede confirmação humana — nunca simplesmente prossegue.

---

## 19. Convenções de código

- **Python 3.11+**, ambiente local com `uv` (preferido) ou `venv` — nunca global. **ruff** para lint e
  format; sem ESLint/Prettier/tsc. Type hints em toda função pública.
- **Contratos de dados:** `pydantic` para config/env/payload de API; `pandera` para schema de DataFrame.
  Fonte de verdade em `packages/shared/schemas/`; `docs/contracts/CONTRACTS.md` é **espelho legível** — se
  vai documentar um contrato lá, **primeiro** crie o schema aqui. Todo DataFrame que entra ou sai de
  `data/canonical/` passa por pandera.
- **Testes:** `pytest`, um por CA. Fonte externa só via fixture gravada (`tests/fixtures/`); rede sob
  `@pytest.mark.network`. **Notebooks** em `apps/analysis/` não têm lógica de negócio — importam de
  `apps/pipeline/` e têm outputs limpos antes do commit.
- **Datas** em ISO-8601; índice temporal `DatetimeIndex` tz-naive, convenção documentada no schema.
  Trimestre = **fim de período**, salvo decisão registrada em contrário. Conventional Commits.

---

## 20. Para o humano (Edu)

- Uma sessão de orquestração por vez; subagentes em paralelo só com arquivos disjuntos.
- Revise o `TODO.md` no fim do dia: mova itens, anote Feature Contracts em andamento. Não force classe A/B
  em algo que mexe no dataset canônico.
- Se o agente pausou, **leia o motivo** — é a principal proteção contra número errado. Se retornou
  `BLOQUEADO`, ele está te protegendo: resolva a causa, não contorne.
- Antes de mandar qualquer coisa para o Alexandre: é classe **D** (revisão humana + dataset congelado).
- Bug urgente: `/fast-fix`. Feature normal: Prompt 2. Wiki: `/wiki <modo>`.

---

## 21. Project Wiki (memória entre sessões/agentes)

A Project Wiki vive em `docs/wiki/`. É **memória sintetizada** entre fontes brutas (prints, respostas de
API, logs, pesquisas em `docs/research/`) e os agentes. **Princípio:** a wiki **nunca** substitui
ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR — referencia, sintetiza e linka.
| Página | Conteúdo |
|---|---|
| `wiki/index.md` | mapa principal — primeira leitura de qualquer agente |
| `wiki/log.md` | histórico cronológico (ingest, releases, fixes, validações) — ≤ 200 linhas |
| `wiki/overview.md` | 1 página com o que o projeto é hoje |
| `wiki/architecture.md` | arquitetura viva (fontes → raw → processed → canonical → análise) |
| `wiki/modules/<mod>.md` | memória por área (`sgs`, `sidra`, `anbima`, `b3`, `canonical`, `regimes`) |
| `wiki/features/<F-NNN>.md` | resumo de 1 parágrafo após merge (C/D apenas) |
| `wiki/runbooks/<slug>.md` | reconstruir dataset, atualizar série, fonte fora do ar, relatório do Comitê |
| `wiki/context/<F-NNN>.md` | Context Pack temporário por tarefa ativa (descartável) |

**Skill `/wiki`:** `ingest` (fonte bruta colada → páginas certas + linha no log), `context` (Context Pack
reusável entre subagentes), `lint` (audita contradições, só leitura), `repair` (aplica correções).
**Manutenção:** toda feature B/C/D termina com 1 linha em `wiki/log.md`; decisão arquitetural → ADR;
decisão operacional → `DECISIONS_LOG.md`; substituição de fonte → log + DECISIONS_LOG. Wiki pequena: se uma
página passa do tamanho-alvo, divida ou arquive.

---

## 22. Continuidade entre agentes (Fable ↔ subagentes Opus)
1. Agente atual roda `/wiki context <tarefa-ativa>` → grava estado em `wiki/context/<F-NNN>.md`.
2. O Fable abre o próximo subagente Opus, que lê `AGENTS.md` + `wiki/index.md` + o Context Pack +
   `ESCOPO-EMAIL-ALEXANDRE.md`: estado, arquivos permitidos, restrições, próximos passos, handoff.
3. O subagente continua e, ao parar, atualiza o mesmo pack. No fim, o pack é deletado e um resumo de
   ≤ 5 linhas vai para `wiki/features/F-NNN.md`.

> Este `AGENTS.md` é o contrato comum; a wiki é a memória viva. Juntos eliminam "perdi o contexto".

---

*Última revisão: 2026-10-10 — Harness v3.2 adaptado para projeto de dados/quant (LDC Capital).*
