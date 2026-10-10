# AGENTS.md — Harness v3.2 · Project Wiki + Fast Fix

> Contrato universal de agentes deste repositório (orquestrador Fable 5.1, subagentes Opus, sessões
> interativas). **Máximo: ~360 linhas.** Detalhes em `TODO.md`, `docs/wiki/`, `docs/plans/PLAN.md`,
> `risk-classification.md`, `prompts-cheatsheet.md`, `infra-ops.md`, `checklists/` e `_templates/`.
>
> **Natureza do projeto:** ferramenta interna de **dados/quant** — pipeline Python de séries macro e índices
> de ativos brasileiros + análise de regimes macro para o Comitê de Alocação da LDC Capital. **Não é SaaS,
> não é web.** Sem auth, sem pagamento, sem deploy (roda local). **Consequência prática:** o risco não é
> "derrubar o site" — é **entregar número errado para o comitê**. Toda regra abaixo protege a integridade
> da camada de dados canônica.

## 1. Papéis

| Papel | Agente | Escopo | Quando usar |
|---|---|---|---|
| **Orquestrador** | Fable 5.1 | Abre as ondas do `PLAN.md`, briefa subagentes, **checa a evidência da matriz de validação** e commita | Sempre; **nunca escreve código** |
| **Executor** | Subagente Opus (1 por feature/fonte) | Extratores, transformações, schemas, testes, notebooks, Feature Contract | Toda feature A/B/C/D |
| **Avaliador semântico (QA)** | Subagente Opus **distinto do que implementou** | Prompt 3 em Validation Mode de dados → `APROVADO / MUDANÇAS_SOLICITADAS / BLOQUEADO` | Todo PR B/C/D (§14) |
| **Avaliador executável** | CI (`.github/workflows/ci.yml`) + pytest + pandera | ruff, unit/integration/contract/e2e, schema, reprodutibilidade por hash | Automático em todo push/PR |
| **Dono do escopo** | Humano (Edu) + stakeholder (Alexandre Kaercher) | Aprova mudança de escopo, aceita ADR, publica resultado ao Comitê | Classe D e toda divergência do e-mail |

> **Regra estrutural:** quem gera nunca é quem valida — nem o próprio agente, nem o orquestrador que o
> abriu. A separação Generator ↔ Evaluator é mantida por **dois** avaliadores: o subagente de QA (semântico)
> e o CI (executável).
>
> **Regra do orquestrador (Fable):** ele **distribui, checa evidência e commita**. Suas únicas escritas são
> `TODO.md`, `docs/plans/PLAN.md`, `docs/wiki/log.md` e o git. Se começar a escrever extrator, schema,
> cálculo de retorno ou teste, a separação de papéis caiu: **pare e delegue a um subagente Opus.**

## 2. Classificação de risco (obrigatória por feature)

Toda feature é classificada **antes** de começar. Ver `docs/plans/risk-classification.md`.

| Classe | Exemplos **neste projeto** | CI alvo | Feature Contract | Validação extra |
|---|---|---|---|---|
| **A** Trivial | ajuste de texto/markdown, renomear célula de notebook, docstring, gráfico cosmético, ajuste de `README` | N1 | opcional | não |
| **B** Normal | **novo extrator de fonte** (SGS, SIDRA, ANBIMA, B3, Tesouro, Yahoo), nova transformação, **agregação mensal→trimestral**, novo índice derivado, cache local de requisição | N1 + matriz | obrigatório (inline no TODO) | amostra conferida contra a fonte |
| **C** Crítica | **qualquer coisa que altere a camada de dados canônica**: schema do dataset-base, regras de alinhamento temporal (calendário, lag de divulgação, fim de trimestre), **cálculo de retornos** (acumulação, deflação por IPCA, anualização), definição de regime macro, janela de 20 anos | N2 | obrigatório (detalhado) | **obrigatório**: diff numérico vs. versão anterior + reconstrução completa de `data/canonical/` + revisão numérica independente |
| **D** Publicação/Credencial | **publicar resultado para o Comitê** (F-031: relatório/planilha enviada ao Alexandre), uso de **credencial ou API paga**, mudança que altera número já apresentado | N3 | obrigatório + seção em `docs/plans/infra-ops.md` com **Rollback** | **obrigatório**: gate de 8 passos do §14 (ADR aceito, revisão humana, dataset congelado, rollback, smoke, log) |

Em dúvida entre duas classes, escolha a mais alta. **Por que C é tão amplo aqui:** erro na camada canônica
(um trimestre desalinhado, um retorno acumulado errado, um IPCA aplicado duas vezes) **contamina todo o
modelo** a jusante sem levantar exceção — falha silenciosa é o modo de falha dominante deste projeto.

## 3. Onde vai cada coisa

```
raiz/               AGENTS.md · CLAUDE.md · TODO.md · README.md · pyproject.toml
docs/product/       ESCOPO-EMAIL-ALEXANDRE.md ← FONTE DE VERDADE DO ESCOPO (não editar) · PRD.md
docs/research/      pesquisa de fontes e metodologia (vários agentes escrevem; nunca sobrescrever)
docs/specs/SPEC.md  o que o pipeline faz + Anti-SPEC §10 (sagrada)
docs/contracts/     CONTRACTS.md — espelho legível de packages/shared/schemas/
docs/plans/         risk-classification.md (quente) · PLAN.md (ondas) · prompts-cheatsheet.md ·
                    infra-ops.md (classe D) · checklists/ · DECISIONS_LOG.md ·
                    CURRENT_REALITY.md · _templates/ · feature-contracts/
docs/wiki/          index · log · overview · architecture + modules/ features/ runbooks/ context/
docs/decisions/adr/ 1 arquivo por decisão arquitetural (ADR-001 … ADR-006)
apps/pipeline/      extract/ transform/ load/ analysis/ deliver/ — código executável
apps/analysis/      notebooks, regimes, relatórios (sem lógica de negócio)
packages/shared/schemas/        FONTE DE VERDADE dos contratos (Pydantic + pandera)
data/raw|processed|canonical/   NÃO versionado, reconstruível por script
tests/unit|integration|contract|e2e/  + tests/fixtures/<fonte>/ (respostas gravadas das fontes)
infra/              scripts auxiliares de ambiente · .github/workflows/ci.yml
```

**Pastas que NUNCA existem:** `state/`, `handoffs/`, `AGENT-BRIEFS/`, `progress.jsonl`, `scripts/` na raiz.
**Regra de ouro dos dados:** `data/` é **reconstruível**. Nada ali é fonte de verdade — a fonte é o
**script que o produz**. Se um dataset só existe no disco de alguém, ele não existe.

## 4. Feed Forward — o que orienta o agente ANTES da execução

Antes de escrever qualquer linha, o agente lê **nesta ordem**: (1) `docs/wiki/index.md` — mapa da wiki;
(2) `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` — toda feature se justifica aqui; (3) `TODO.md`, item F-NNN +
Feature Contract inline (ou `docs/plans/feature-contracts/F-NNN.md`); (4) `docs/wiki/context/<F-NNN>.md` —
Context Pack, se outro subagente já começou; (5) `docs/specs/SPEC.md` — os **CAs citados no item** +
**Anti-SPEC §10**; (6) `docs/contracts/CONTRACTS.md` e `packages/shared/schemas/`; (7)
`docs/research/fontes-de-dados.md` — **a seção exata da fonte** (endpoint, formato, limites, pegadinhas);
(8) `CURRENT_REALITY.md`, `DECISIONS_LOG.md` e `wiki/log.md` (últimos 7 dias); (9) a Definition of Ready do
item (base em `TODO.md §2.0` + específica) — se incompleta, **pausa**.

> A wiki é **memória sintetizada**, NUNCA fonte de verdade. Em conflito, valem as fontes
> (ESCOPO-EMAIL / PRD / SPEC / schemas Pydantic-pandera / ADR).

## 5. Feedback — o que valida DEPOIS da execução

Toda feature B/C/D precisa de **evidência objetiva** por CA antes do merge: matriz
`CA | teste | tipo | status | evidência` (Feature Contract ou `_templates/VALIDATION-MATRIX-template.md`)
e CI no nível da classe (§6). **Evidência específica de dados** — os 5 itens, além do teste verde:
(1) log do `pytest`; (2) nº de linhas + `min`/`max` de data; (3) % de nulos por coluna crítica;
(4) **3 valores conferidos contra a fonte original** (print/link do BCB/IBGE/ANBIMA/B3); (5) em classe C,
**diff numérico** vs. a versão anterior do canônico, com cada divergência explicada.
O QA do PR é feito por **subagente Opus distinto** (§14) e devolve
`APROVADO | MUDANÇAS_SOLICITADAS | BLOQUEADO`. **Nunca APROVADO sem evidência** — "o script rodou sem
erro" **não é** evidência.

## 6. CI por níveis

| Nível | Contém | Obrigatório para |
|---|---|---|
| **N1** | `ruff check .` + `ruff format --check .` + `pytest tests/unit -m "not network"` | A, B |
| **N2** | N1 + `pytest tests/integration tests/contract` (schemas **pandera** sobre fixtures) + build do dataset canônico a partir de fixtures | B relevante, C |
| **N3** | N2 + `pytest tests/e2e` (pipeline ponta a ponta) + **reprodutibilidade por hash** (rodar 2x → `sha256` idêntico de `data/canonical/`) | C crítica, D |

Testes de rede ficam marcados `@pytest.mark.network` e **não** rodam no CI (`-m "not network"`). Fonte
externa em teste é sempre **fixture gravada** em `tests/fixtures/<fonte>/`, nunca chamada viva. Os jobs N2 e
N3 estão comentados em `ci.yml` até existirem `tests/integration`, `tests/contract` e `tests/e2e` —
descomentá-los é parte da feature que os cria.

## 7. Protocolo de geração de código

O subagente executor: (1) **valida a classe** A/B/C/D e reclassifica antes de codar se mudou (§16);
(2) **valida a DoR** — incompleta → pausa ou `BLOQUEADO` (§9); (3) **checa o escopo** contra
`ESCOPO-EMAIL-ALEXANDRE.md` — fora do e-mail, pausa e registra a proposta; (4) cria ou valida o **Feature
Contract** (B/C/D); (5) usa os **schemas de `packages/shared/schemas/`** — nunca DataFrame ad hoc; se
faltar schema, **acrescenta** ali primeiro (Pydantic para config/payload, pandera para DataFrame) —
**alterar** schema existente não é acréscimo, é pausa; (6) escreve **testes falhando** por CA, com fixture
gravada da fonte; (7) **implementa** só nos arquivos permitidos, respeitando a Anti-SPEC; (8) roda o **CI
local** no nível da classe; (9) preenche a **matriz de validação** + as 5 evidências do §5; (10) devolve o
**relatório ao orquestrador** e deixa 1 linha em `wiki/log.md` — o Fable atualiza `TODO.md` e commita (§13).
Se encontrar algo fora do Feature Contract, **pausa** e consulta antes (§18).

## 8. O que o agente executor PODE e NÃO PODE editar (sem autorização)

**PODE** no fluxo normal: `docs/contracts/CONTRACTS.md` (espelho dos schemas); ADR em decisão arquitetural
nova e clara; `docs/plans/infra-ops.md` (classe D); `CURRENT_REALITY.md` em diagnóstico;
`DECISIONS_LOG.md`; `docs/wiki/log.md`, `runbooks/`, `context/`, `modules/`, `features/`; código em
`apps/pipeline/`, `apps/analysis/`, `packages/`, `tests/`, `infra/`; conteúdo de
`data/raw|processed|canonical` **via script reprodutível** (nunca à mão); `TODO.md` **fora de onda**.
**Durante uma onda com N subagentes em paralelo, `TODO.md`, `PLAN.md`, `wiki/log.md`, `CONTRACTS.md` e os
schemas existentes são do orquestrador** — ver §13.

**NÃO PODE** sem autorização humana explícita: `docs/product/ESCOPO-EMAIL-ALEXANDRE.md` (**imutável** —
mudança de escopo vai para `DECISIONS_LOG`/ADR), `docs/product/PRD.md`, `docs/specs/SPEC.md`, Anti-SPEC
(`SPEC.md §10`); arquivos de outros agentes em `docs/research/` (pode criar os seus; **não apaga nem
sobrescreve** os alheios); **schema existente** em `packages/shared/schemas/`, schema do canônico, regras de
alinhamento temporal e cálculo de retorno (classe C — contrato próprio); decisão arquitetural aprovada em
ADR; `wiki/overview.md` quando contradiz o PRD e `wiki/architecture.md` quando contradiz a SPEC (ajuste a
fonte primeiro).

## 9. Autonomia vs pausa vs BLOQUEADO

**CONTINUE automaticamente quando:** a tarefa está dentro do Feature Contract e os arquivos alterados estão
na lista permitida; os testes necessários existem ou estão sendo criados conforme os CAs; não há alteração
destrutiva em `data/` fora de script reprodutível; é classe A/B sem toque na camada canônica; e o escopo não
muda frente ao e-mail do Alexandre.

**PAUSE e peça confirmação humana quando:**
- Precisar mudar `ESCOPO-EMAIL-ALEXANDRE.md`, `PRD.md`, `SPEC.md` ou Anti-SPEC, ou alterar escopo da
  feature (CA novo, arquivo fora da lista com risco).
- Precisar **alterar schema canônico, alinhamento temporal ou cálculo de retorno** (classe C), ou
  **alterar** (não acrescentar) schema existente em `packages/shared/schemas/`.
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
  com estimativa, interpolação não documentada ou valor inventado para "fechar" a série. Inclui backfill de
  janela rolante (ANBIMA `ms*.txt`, Curva Zero), IFIX pré-2011 e FII segmentado pré-2019.
- **Número de regime a caminho do Comitê com ADR-001 ainda em `Proposta`** →
  `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA`. Enquanto D1/D3 não estiverem respondidos e o ADR-001 aceito,
  `especificacao_congelada = False` (CA-090) e **nenhum número de regime sai para o Alexandre/Comitê**.
  Desenvolver com o padrão provisório é permitido; **publicar não é** (§14).

**FAST FIX (Project Quick):** bug urgente classe **A ou B** que **não toca camada canônica, credenciais nem
entregável do Comitê**, < 30 min do diagnóstico ao PR. Usa `/fast-fix`. Se escalar para C/D, **sai do modo**.
**MVP LITE:** exploração rápida (notebook de sondagem, teste de endpoint) que não produz dado canônico nem
alimenta entregável. Mantém só `TODO.md` + classe + 1 teste no caminho crítico + commit + linha em
`wiki/log.md`. **Se o resultado virar insumo do modelo, migra para Standard imediatamente.**
**TRIAGE:** com ≥ 2 problemas na mesma janela (série quebrada, extrator falhando, divergência de número),
use `/triage-bugs` antes de qualquer fix — nunca começa fix automaticamente.

## 10. Branches e PRs

**Branches:** `feat/<slug>`, `fix/<slug>`, `data/<slug>` (nova fonte), `chore/<slug>`. **Classe A** pode ir
direto em `main` se < 30 min, com teste e CI N1 verde local. **B, C, D** exigem PR e CI verde; **C e D**
exigem revisão humana; **D** exige dataset congelado + tag git + registro em `wiki/log.md` (§14).
Conventional Commits referenciando o item do TODO (`feat(sgs): extrator IPCA/Selic (F-003)`). **Nunca**
commitar dado bruto > 5 MB. **Quem commita é o orquestrador**, ao fechar a feature.

## 11. Quando acionar um subagente Opus dedicado

O Fable abre subagente próprio quando a tarefa é: **pesquisa de fonte** (endpoint, auth, formato, limite) →
escreve em `docs/research/`; **novo extrator** de uma fonte (um subagente por fonte evita contenção de
arquivo — Prompt 4); **camada canônica** classe C (no máximo dois em paralelo, nunca na mesma tabela);
**QA / revisão numérica independente** (quem calculou não confere — §14); **relatório do Comitê** (classe D,
com revisão humana antes do envio). Cada subagente recebe: objetivo, ordem de leitura, CAs da SPEC,
valor-canário, **arquivos permitidos**, arquivos proibidos, critério de aceite e o formato do relatório
final. Os briefings prontos estão em `docs/plans/prompts-cheatsheet.md`.

## 12. O que o agente NUNCA faz

- **Inventa dado.** Nem para preencher lacuna, nem para "ilustrar", nem em notebook sem rótulo `FAKE`.
  Nem mistura dado real com sintético no mesmo DataFrame sem coluna de origem.
- Edita arquivo em `data/` à mão; commita dado bruto > 5 MB, `.parquet`, `.duckdb`, `.env` ou credencial.
- Desabilita teste ou usa `.skip`/`xfail` sem ADR; adiciona dependência nova sem ADR.
- Sobrescreve ou apaga trabalho de outro agente em `docs/research/`.
- Altera `ESCOPO-EMAIL-ALEXANDRE.md`, `PRD.md`, `SPEC.md` ou Anti-SPEC sem autorização.
- Aprova PR sem matriz de validação (B/C/D) — ou **aprova o próprio trabalho** (§14).
- Cria `scripts/` na raiz, `state/`, `handoffs/` ou JSON de estado.

## 13. Loop de ondas e paralelismo (execução real deste projeto)

A unidade de execução é a **onda** do `docs/plans/PLAN.md` (Onda 0 → 5, até o Comitê de 2026-10-14).
Uma onda só abre quando a anterior está **verde no CI** no nível alvo. Loop do orquestrador, por onda:

1. **Abrir:** lê a onda no `PLAN.md`, move os itens para `TODO.md §1`, confirma classe e DoR de cada um.
2. **Briefar N subagentes Opus em paralelo** — Prompt 5 do `prompts-cheatsheet.md`. Cada subagente recebe
   **seu próprio Feature Contract do `TODO.md`** e uma **lista de arquivos permitidos disjunta** das demais
   (`apps/pipeline/extract/<fonte>.py`, `tests/unit/test_<fonte>.py`, `tests/fixtures/<fonte>/`).
3. **Congelar os arquivos compartilhados durante a onda:** `TODO.md`, `PLAN.md`, `wiki/log.md`,
   `CONTRACTS.md` e os schemas já existentes são **só do orquestrador**. Subagente que precisar deles
   devolve o texto pronto no relatório; o Fable consolida.
4. **Receber relatórios** — matriz de validação + as 5 evidências de dados (§5) por feature.
5. **Checar evidência** (não reimplementar): CA sem evidência, valor-canário ausente ou diff numérico
   inexplicado → devolve ao subagente. Dúvida semântica → abre o QA do §14.
6. **Consolidar e commitar:** aplica as linhas de `TODO.md`/`CONTRACTS.md`/`wiki/log.md`, roda o CI do nível
   da onda e commita por feature.
7. **Fechar a onda** no `PLAN.md` e só então abrir a próxima.

**Limites de paralelismo:** 3-4 subagentes simultâneos (as 7 features de extração da Onda 1 vão em dois
lotes); **classe C no máximo 2 em paralelo**, nunca duas na mesma tabela canônica; **classe D roda sozinha**.
Ninguém **altera** schema existente — só acrescenta; alteração é pausa (§9).

## 14. QA independente e gate da classe D

**Gerador ≠ avaliador, inclusive entre subagentes.** O QA de todo PR B/C/D é feito por um **subagente Opus
distinto** do que implementou, com o Prompt 3 (Validation Mode de dados, §15). Em classe C, a **revisão
numérica independente** é o mesmo princípio aplicado aos números: quem calculou não confere. O orquestrador
não faz o papel de QA — ele **lê o veredito** e age (merge, devolução ou escalada ao humano).

**Gate da classe D (F-031 — pacote de entrega ao Comitê).** Sequência obrigatória, na ordem, sem atalho:

1. CI **N3** verde: e2e + duas execuções do pipeline com `sha256` idêntico.
2. **ADR-001 aceito** (D1 + D3 respondidos). Em `Proposta` → `BLOQUEADO — ESPECIFICAÇÃO NÃO CONGELADA`.
3. **Revisão humana do número pelo Edu**, com 3 valores conferidos por série.
4. **Dataset congelado:** versão + `sha256` de `data/canonical/` + tag git (`comite-2026-10-14`).
5. **Rollback escrito** em `docs/plans/infra-ops.md` para aquela entrega específica.
6. **Smoke test do pacote** (abre no Excel, nº de linhas, datas min/max, nulos nas colunas críticas).
7. **Comunicação escrita das substituições de fonte** (F-032 / `DECISIONS_LOG.md`) junto ao pacote.
8. Linha `[RELEASE]` em `wiki/log.md` com versão e hash + resumo em `wiki/features/F-031.md`.

Faltando qualquer um dos 8 → **não envia**. Vale para o pacote completo e para "só esse número do heatmap no
WhatsApp": **não existe classe A/B para publicação.**

## 15. Validation Mode (obrigatório no QA)

No QA do PR o agente assume que a implementação e os testes podem estar errados e **tenta quebrar** a
feature de forma controlada antes de aprovar. **Regras (sempre, para B/C/D) — versão dados:**
1. Antes de aprovar, tente quebrar a feature.
2. **Buracos de série:** feriado, trimestre sem divulgação, série que começa depois de 2006.
3. **Revisão retroativa** da fonte (IBGE revisa PIB) — o pipeline é idempotente ou duplica linha?
4. **Calendário:** fim de trimestre, data de referência vs. data de divulgação (lag).
5. **Unidade e escala:** % vs. fração, índice vs. variação, nominal vs. real, base 100 trocada.
6. **Idempotência:** rodar duas vezes gera o mesmo output (hash igual).
7. **Resposta vazia ou erro da fonte** (HTTP 500, HTTP 200 com corpo de erro, payload truncado, JSON com
   `null`); **ordenação e duplicidade** do índice temporal (datas repetidas, fora de ordem).
8. Verifique se algo **fora do escopo** foi alterado (diff vs. arquivos permitidos).
9. Confira **3 valores contra a fonte original**; divergência não explicada ou CA sem evidência objetiva →
   `MUDANÇAS_SOLICITADAS`. **Nunca `APROVADO`** nesses casos.

Testes mínimos por classe e exemplos de "teste fake" proibido vivem em `docs/plans/risk-classification.md`.

## 16. Auto-reclassificação de risco

Se a natureza da feature mudar durante a implementação, **reclassifique antes de continuar**. Regra:
**suba, nunca desça.** Gatilhos: **A → B** quando passa a alterar valor ou estrutura de qualquer output
(não é mais só texto/cosmético); **B → C** quando passa a tocar schema canônico, alinhamento temporal,
cálculo de retorno, deflação, agregação trimestral, definição de regime macro ou qualquer número que
alimente o modelo; **qualquer → D** quando passa a tocar credencial/API paga, o resultado será enviado ao
Comitê, ou altera número já apresentado. **Procedimento:** (1) pause se a nova classe é C/D; (2) atualize o
Feature Contract; (3) recalcule os testes mínimos; (4) atualize o CI alvo; (5) atualize a matriz;
(6) registre nota no `TODO.md` e linha `RECLASSIFY` em `wiki/log.md`; (7) continue só se §9 permitir.

## 17. DECISIONS_LOG (memória operacional leve)

`docs/plans/DECISIONS_LOG.md` complementa os ADRs sem substituí-los. **ADR** → decisão arquitetural com
trade-off real (DuckDB vs. Parquet puro, lib de HTTP, cache). **DECISIONS_LOG** → decisão operacional que
voltará ao debate (IBC-Br em vez de PIB trimestral do IBGE; proxy de FII segmentado; trimestre = fim de
período). **TODO.md** → estado + Feature Contract + matriz. **ESCOPO-EMAIL / PRD / SPEC / Anti-SPEC** →
escopo e comportamento; o agente **não edita** sem autorização. Toda **substituição de fonte** autorizada
pelo Alexandre ("fique à vontade para ajustes caso não localize estes dados") entra no DECISIONS_LOG com:
fonte pedida, fonte usada, por quê, impacto na comparabilidade.

## 18. Arquivo fora do Feature Contract — fluxo de justificativa

**Padrão: BLOQUEADO.** **Caminho de escape (autonomia em A/B sem risco):** justificativa explícita com
(1) qual arquivo; (2) por quê; (3) impacto (superfície do diff, módulos tocados); (4) se altera escopo;
(5) se exige atualizar o Feature Contract; (6) se exige novos testes; (7) se exige reclassificação (§16).
Se a justificativa é puramente operacional e **não** toca camada canônica, credencial, entregável do Comitê
nem escopo: atualize o Feature Contract, registre no DECISIONS_LOG se útil, e continue. Se toca qualquer um
desses domínios — ou se o arquivo está congelado pela onda em curso (§13) — **pausa** e devolve ao
orquestrador: nunca simplesmente prossegue.

## 19. Convenções de código

- **Python 3.11+**, ambiente local com `uv` (preferido) ou `venv` — nunca global. **ruff** para lint e
  format; sem ESLint/Prettier/tsc. Type hints em toda função pública.
- **Contratos de dados:** `pydantic` para config/env/payload de API; `pandera` para schema de DataFrame.
  Fonte de verdade em `packages/shared/schemas/`; `docs/contracts/CONTRACTS.md` é **espelho legível** — se
  vai documentar um contrato lá, **primeiro** crie o schema aqui. Todo DataFrame que entra ou sai de
  `data/canonical/` passa por pandera.
- **Testes:** `pytest`, um por CA. Fonte externa só via fixture gravada (`tests/fixtures/<fonte>/`); rede
  sob `@pytest.mark.network` e **só no teste live**. **Notebooks** em `apps/analysis/` não têm lógica de
  negócio — importam de `apps/pipeline/` e têm outputs limpos antes do commit.
- **Datas** em ISO-8601; índice temporal `DatetimeIndex` tz-naive, convenção documentada no schema.
  Trimestre = **fim de período**, salvo decisão registrada em contrário. Encoding **sempre explícito** no
  leitor (o default do locale no Windows, cp1252, não é aceitável). Conventional Commits.

## 20. Para o humano (Edu)

- Uma sessão de orquestração por vez; subagentes em paralelo só com arquivos disjuntos (§13).
- Revise o `TODO.md` no fim do dia: mova itens, anote Feature Contracts em andamento. Não force classe A/B
  em algo que mexe no dataset canônico.
- Se o agente pausou, **leia o motivo** — é a principal proteção contra número errado. Se retornou
  `BLOQUEADO`, ele está te protegendo: resolva a causa, não contorne.
- **Destrave a publicação respondendo D1/D3** (1 linha de "aceito a recomendação" em cada ADR). Sem
  ADR-001 aceito, o gate do §14 não libera o envio ao Comitê.
- Antes de mandar qualquer coisa para o Alexandre: é classe **D** (§14 — os 8 passos).
- Bug urgente: `/fast-fix`. Feature normal: Prompt 2. Onda nova: Prompt 5. Wiki: `/wiki <modo>`.

## 21. Project Wiki (memória entre sessões/agentes)

A Project Wiki vive em `docs/wiki/`. É **memória sintetizada** entre fontes brutas (prints, respostas de
API, logs, pesquisas em `docs/research/`) e os agentes. **Princípio:** a wiki **nunca** substitui
ESCOPO-EMAIL/PRD/SPEC/CONTRACTS/ADR — referencia, sintetiza e linka. Páginas: `index.md` (mapa, primeira
leitura), `log.md` (histórico cronológico, ≤ 200 linhas), `overview.md`, `architecture.md`,
`modules/<mod>.md` (`sgs`, `sidra`, `anbima`, `b3`, `canonical`, `regimes`), `features/<F-NNN>.md`
(≤ 5 linhas após merge de C/D), `runbooks/<slug>.md` (reconstruir dataset, série fora do ar, fechar
relatório do Comitê, arquivamento diário ANBIMA), `context/<F-NNN>.md` (Context Pack descartável).

**Skill `/wiki`:** `ingest` (fonte bruta colada → páginas certas + linha no log), `context` (Context Pack
reusável entre subagentes), `lint` (audita contradições, só leitura), `repair` (aplica correções).
**Manutenção:** toda feature B/C/D termina com 1 linha em `wiki/log.md`; decisão arquitetural → ADR;
decisão operacional → `DECISIONS_LOG.md`; substituição de fonte → log + DECISIONS_LOG. Wiki pequena: se uma
página passa do tamanho-alvo, divida ou arquive.

## 22. Continuidade entre agentes (Fable ↔ subagentes Opus)

1. Agente atual roda `/wiki context <tarefa-ativa>` → grava estado em `wiki/context/<F-NNN>.md`.
2. O Fable abre o próximo subagente Opus, que lê `AGENTS.md` + `wiki/index.md` + o Context Pack +
   `ESCOPO-EMAIL-ALEXANDRE.md`: estado, arquivos permitidos, restrições, próximos passos, handoff.
3. O subagente continua e, ao parar, atualiza o mesmo pack. No fim, o pack é deletado e um resumo de
   ≤ 5 linhas vai para `wiki/features/F-NNN.md`.

> Este `AGENTS.md` é o contrato comum; a wiki é a memória viva. Juntos eliminam "perdi o contexto".

*Última revisão: 2026-10-10 — Harness v3.2 adaptado para projeto de dados/quant (LDC Capital). Seções 13 e
14 preenchidas (antes faltavam, numeração pulava de 12 para 15); §15-§22 mantiveram o número porque
`CLAUDE.md`, `SPEC.md`, `TODO.md`, o PRD e os templates citam §2/§3/§5/§8/§9/§12/§15/§16/§18/§19/§22.*
