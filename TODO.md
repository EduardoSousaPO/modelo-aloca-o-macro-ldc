# TODO — estrategia-macro-ldc-dados

> Estado vivo do projeto. Substitui `state/project-state.json`, `progress.jsonl` e `handoffs/`.
> Atualize ao iniciar, ao terminar uma feature e ao fim do dia.
>
> **v3.2 — Feedback Hardened + Project Wiki:** cada feature B/C/D traz o **Feature Contract inline**
> (DoR + escopo + arquivos + CAs + testes + matriz). Features A podem ter apenas a descrição mínima.

**Última revisão:** 2026-10-10
**Fase:** PRD v1.0 escrito (modo autônomo), aguardando aprovação do Edu
**Tipo:** ferramenta interna (dados / quant — não SaaS, não web, roda local)
**Foco atual:** responder as **8 decisões bloqueantes** da §4 → aprovar `docs/product/PRD.md` → `/SDD-avancado`

---

## 0. Contexto do projeto

**Objetivo.** Dar base estatística ao **modelo de alocação macro doméstica** e ao **dimensionamento da
alocação internacional** da LDC Capital. O projeto extrai, normaliza e alinha num dataset canônico
trimestral de **20 anos** (≈ 2006 → 2026): (A) indicadores macroeconômicos brasileiros — PIB/IBC-Br, IPCA,
expectativas do Focus, Selic Over, taxas de títulos públicos, estrutura a termo da curva de juros (ETTJ) —
e (B) desempenho de ativos e subsetores — índices ANBIMA de renda fixa (IMA-B, IRF-M), CDI, índices amplos e
setoriais da B3 (IBOV, IDIV, SMLL, INDX, ICON, IMAT, IEE, IMOB, IFNC) e FIIs (IFIX e segmentações) — mais
(C) proxies para a alocação internacional. Sobre essa base se identificam **regimes macro** e se mede como
cada classe de ativo e setor performou em momentos semelhantes.

**Entregável pedido.** Estrutura de busca e extração desses dados + base pronta para o Alexandre modelar a
estratégia.

**Prazo duro.** Reunião do **Comitê de Alocação: 2026-10-14**. Publicar resultado para o Comitê é operação
**classe D** (revisão humana + dataset congelado + registro em `wiki/log.md`).

**Fonte de verdade do escopo.** [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](docs/product/ESCOPO-EMAIL-ALEXANDRE.md)
— imutável. Toda feature se justifica ali; o que estiver fora exige pausa e registro.
Substituição de fonte (autorizada pelo Alexandre quando um dado não for localizável) vai para
`docs/plans/DECISIONS_LOG.md` com: fonte pedida, fonte usada, por quê, impacto na comparabilidade.

**Pesquisa em andamento.** [`docs/research/`](docs/research/) — levantamento de fontes de dados e
metodologia, sendo produzido em paralelo por outros agentes. Leia antes de escrever extrator.

**Risco dominante.** Não é indisponibilidade: é **número errado chegando ao comitê sem levantar exceção**
(trimestre desalinhado, retorno acumulado errado, IPCA aplicado duas vezes). Daí a classe C ampla para
qualquer mudança na camada canônica — ver `AGENTS.md §2`.

---

## 1. Em andamento

> Máximo 2 itens simultâneos. Se tiver mais, você está dispersando.

*(vazio — a preencher por `/SDD-avancado`)*

<!--
MODELO DE FEATURE CONTRACT INLINE (obrigatório para B/C/D — copie este bloco ao mover um item
do backlog para "Em andamento"). Versão completa: docs/plans/_templates/FEATURE-CONTRACT-template.md

### [ ] F-NNN — <título da feature>

- **Risco:** A | B | C | D   (ver AGENTS.md §2 — camada canônica é C no mínimo)
- **Cobre:** RF-NNN / item do checklist do e-mail (A1..A7, B1..B5, C1)
- **Branch:** `feat/<slug>` | `data/<slug>`
- **CI alvo:** N1 | N2 | N3

**Definition of Ready**
- [ ] Item do escopo do e-mail identificado (A1..C1) e justificado
- [ ] Fonte definida: URL/endpoint, formato, autenticação, limite de requisição (ver docs/research/)
- [ ] Cobertura temporal verificada: a série cobre a janela de 20 anos? Se não, qual o recorte real?
- [ ] Frequência nativa e regra de agregação para trimestral definidas
- [ ] Unidade e natureza do número explícitas (índice vs. variação, % vs. fração, nominal vs. real)
- [ ] Critérios de aceite testáveis (abaixo)
- [ ] Escopo incluído/excluído explícito
- [ ] Risco confirmado
- [ ] Arquivos prováveis listados
- [ ] Testes mapeados + fixture da fonte gravada em tests/fixtures/
- [ ] Schemas: <SchemaX> em `packages/shared/schemas/<modulo>.py` (pydantic/pandera)
- [ ] Camada canônica: altera schema/alinhamento/cálculo de retorno? (se sim → classe C)
- [ ] Credencial: usa API paga ou segredo? (se sim → classe D)

**Escopo incluído / excluído**
- incluído: ...
- excluído: ... (vira F-0XX)

**Arquivos que podem ser alterados**
- `apps/pipeline/...`, `packages/shared/schemas/...`, `tests/...`, `docs/contracts/CONTRACTS.md` (espelho)

**Arquivos que NÃO podem ser alterados (sem pausa + confirmação)**
- `docs/product/ESCOPO-EMAIL-ALEXANDRE.md`, `docs/specs/SPEC.md`, `docs/product/PRD.md`
- arquivos de outros agentes em `docs/research/`
- schema canônico e regras de alinhamento/retorno (qualquer mudança vira F-0XX classe C)

**Critérios de aceite**
- [ ] **CA-001:** ...
- [ ] **CA-002:** ...

**Testes obrigatórios** (mínimos por classe em `docs/plans/risk-classification.md`)

| Teste | Tipo | Cobre CA | Arquivo |
|---|---|---|---|
| schema do output valida | contract | CA-001 | `tests/contract/test_<fonte>.py` |
| série sem buraco na janela | unit | CA-002 | `tests/unit/test_<fonte>.py` |
| idempotência (rodar 2x = mesmo hash) | integration | CA-00N | `tests/integration/...` |
| resposta vazia/erro da fonte | unit negativo | CA-00N | `tests/unit/...` |

**Anti-SPEC relevante** (SPEC §6)
- NÃO inventar valor para fechar série (lacuna → BLOQUEADO — FONTE INDISPONÍVEL)
- NÃO misturar dado real e sintético sem coluna de origem
- NÃO editar `data/` à mão

**Matriz de validação (preenchida no QA do PR)**

| CA | Teste | Tipo | Status | Evidência |
|---|---|---|---|---|
| CA-001 | `test_<fonte>.py::schema` | contract | — | log pytest + nº linhas + min/max data |

**Evidências de dados obrigatórias (além do teste verde — AGENTS.md §5)**
- [ ] nº de linhas + intervalo de datas (min/max)
- [ ] % de nulos por coluna crítica
- [ ] 3 valores conferidos contra a fonte original (com print/link)
- [ ] classe C: diff numérico vs. versão anterior do canônico, cada divergência explicada

**Notas:** começar pelo schema; teste com fixture primeiro, implementação depois.
-->

---

## 2. Backlog (próximas features)

> Ordem é intencional: valor × risco × dependência. Cada item recebe seu Feature Contract ao entrar em
> "Em andamento".

*(vazio — a preencher por `/SDD-avancado`)*

---

## 3. Concluído

> Movido para cá ao fazer merge. Inclua SHA/PR.

- [x] **Kickoff — estrutura Harness v3.2 adaptada a projeto de dados** — 2026-10-10 (classe A)

---

## 4. Bloqueios

> **8 decisões de Edu/Alexandre bloqueiam o início da implementação.** Origem: `docs/product/PRD.md §13.2`
> (PRD gerado em modo autônomo em 2026-10-10 — nenhuma dessas respostas veio de humano). Enquanto não
> respondidas, as features de regime e os extratores do caminho crítico não têm Definition of Ready completa.
> Cada item traz a **recomendação da pesquisa** — responder "aceito a recomendação" já destrava.

- [ ] **D1 — Qual lente de regime é a oficial do Comitê?** (V1 / V2 / V3 / as três). Define o que o notebook
      entrega e o que vai ao slide, e precisa estar congelada em ADR **antes** de rodar sobre os retornos
      (RF-031). *Recomendação: V1 oficial + V3 como "momentos semelhantes" + V2 como corte secundário.*
- [ ] **D3 — Eixo inflação da V1: nível vs. meta ou aceleração (Δ IPCA 12m)?** Muda o rótulo dos 83
      trimestres; reclassificar depois invalida o heatmap. *Recomendação: aceleração.*
- [ ] **D5 — Métrica primária do heatmap: nominal, excesso sobre CDI ou real?** É a coluna do entregável
      visual central (RF-033). *Recomendação: excesso sobre CDI (neutraliza a Selic de 19% → 2% → 14%).*
- [ ] **D6 — Internacional: piso estrutural, 100% tático por regime ou híbrido?** Sem isso não se sabe o que
      RF-038/RF-039 devem entregar — e é a resposta ao item C1 do e-mail. *Recomendação: piso 16-20% + banda
      tática 15-35% por regime (n≈20 não sustenta número pontual).*
- [ ] **D12 — Setoriais B3 e FII segmentado entram no pacote mínimo?** (completo / best-effort / fora).
      Define quantos extratores entram no caminho crítico de 3 dias. *Recomendação: best-effort, com `n` e
      `data_inicio` visíveis.*
- [ ] **L1 — IFIX só existe de 2011 em diante (metade da janela).** Aceitar janela própria 2011-2026?
      *Recomendação: janela própria + IMOB (2008+) como proxy imperfeito; **não** reconstruir IFIX sintético.*
- [ ] **L2 — Segmentação de FII (Tijolo/Papel/Logística/Shoppings) só desde 2019 e via provedor privado
      (Teva) sem licença comercial explícita.** Autorizar o uso? *Recomendação: usar para dispersão setorial,
      declarando que cobre ~2 ciclos macro; tratar como qualitativo.*
- [ ] **L4 — ETTJ oficial da ANBIMA com 20 anos exige contratar o ANBIMA Feed (≈R$ 686–8.238/mês).**
      Contratar ou aceitar a inclinação construída do Tesouro Direto? Era pedido explícito do e-mail (item A6).
      *Recomendação: Tesouro Direto — tecnicamente defensável sem comprar o Feed; registrar em DECISIONS_LOG
      e comunicar ao Alexandre.*

**Não bloqueantes** (17 decisões D2/D4/D7-D11 e lacunas L3/L5-L13 + 7 gaps "a confirmar") estão em
`docs/product/PRD.md §13.3` e §13.4 com a recomendação adotada por padrão — podem ser decididas durante a
execução, sem travar o início.

> Se tiver bloqueio: descreva o problema, o que já foi tentado e o que precisa para destravar.
> **Não pausar trabalho em outra feature para resolver bloqueio** — use o bloqueio como input de conversa
> com o humano/Alexandre e siga em outra coisa.

---

## 5. Bugs abertos

| ID | Descrição curta | Repro | Gravidade | Classe se virar feature | Nota |
|---|---|---|---|---|---|
| — | *(vazio)* | — | — | — | — |

> Em projeto de dados, "bug" inclui: série com buraco não explicado, divergência entre fontes, número que
> mudou sem mudança de código, extrator que falha silenciosamente. Use `/triage-bugs` com ≥ 2 itens.

---

## 6. Ideias / parking lot

> Coisas que apareceram mas não devem quebrar o foco. Revisar a cada 2 semanas.

- *(vazio — preencher durante o discovery)*

---

## 7. Definition of Done (DoD) — aplica a TODA feature

### Classe A
- [ ] CI N1 local verde (`ruff check . && ruff format --check . && pytest tests/unit`)
- [ ] `TODO.md` atualizado (item → Concluído com SHA)
- [ ] Teste cobre o CA (mesmo que unit simples)

### Classe B
- [ ] Tudo de A +
- [ ] Feature Contract preenchido
- [ ] Matriz de validação com status = passou em todos os CAs
- [ ] Evidências de dados: nº de linhas, intervalo de datas, % de nulos, 3 valores conferidos na fonte
- [ ] CI verde no PR
- [ ] `docs/contracts/CONTRACTS.md` atualizado se os schemas mudaram
- [ ] Fixture da fonte gravada em `tests/fixtures/`
- [ ] 1 linha em `docs/wiki/log.md`

### Classe C
- [ ] Tudo de B +
- [ ] CI N2 verde (integration + contract/pandera + build do canônico)
- [ ] **Reconstrução completa de `data/canonical/` a partir de zero, com sucesso**
- [ ] **Diff numérico vs. versão anterior do canônico, com cada divergência explicada**
- [ ] Anti-SPEC verificada explicitamente no QA
- [ ] Revisão numérica independente (quem calculou não confere)
- [ ] ADR se houve decisão arquitetural; `DECISIONS_LOG` se houve substituição de fonte

### Classe D
- [ ] Tudo de C +
- [ ] CI N3 verde (e2e + reprodutibilidade: rodar 2x → mesmo hash)
- [ ] Rollback documentado em `docs/plans/infra-ops.md`
- [ ] Revisão humana do número antes do envio ao Alexandre/Comitê
- [ ] Dataset congelado (versão + hash) e registrado em `docs/wiki/log.md`
- [ ] Credencial/API paga: uso autorizado e nenhum segredo no repo

---

*Este arquivo substitui `state/project-state.json`, `progress.jsonl`, `handoffs/*.json` e `bugs/*.md`.
O histórico granular vive no `git log`. Feature Contracts vivem aqui inline (ou em
`docs/plans/feature-contracts/F-NNN.md` quando extensos). Decisões operacionais que voltarão ao debate vão
para `docs/plans/DECISIONS_LOG.md`. Escopo e comportamento permanecem em ESCOPO-EMAIL/PRD/SPEC/Anti-SPEC e
só mudam com autorização humana.*
