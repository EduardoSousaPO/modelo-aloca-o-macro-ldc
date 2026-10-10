# ADR-007 — Sem Supabase (nem qualquer banco remoto) na v1

- **Status:** **Aceita** — decisão do **Edu** (dono do projeto), sobre recomendação do orquestrador
- **Data:** 2026-10-10
- **Autor:** orquestrador da Onda 0 (recomendação) · **Edu** (decisão)
- **Complementa:** **ADR-006** (alternativa D) · **Cobre:** PRD §4.4, RNF-004/006/009, `AGENTS.md §2`

---

## Contexto

O Edu perguntou se o projeto precisa de **Supabase** como banco de dados. A pergunta é legítima: o
`DECISIONS_LOG` e os schemas já falam de `vintage`, materializações `asof`/`revised` e catálogo de
séries — vocabulário que costuma puxar um Postgres.

O que o projeto é hoje, medido e não suposto:

- **Execução local** na máquina do Edu, Windows, **usuário único** (RNF-004). Sem interface web, sem
  API, sem auth, sem deploy — explicitamente **fora de escopo** no PRD §4.4.
- **Volume pequeno:** ~130 séries catalogadas, **83 trimestres** no canônico (83 × ~40 colunas) e
  ~2.700 linhas de retorno. O maior arquivo do pipeline é o CSV do Tesouro (14,6 MB), que é *raw*.
- **ADR-006 já resolveu a persistência:** Parquet por camada (`raw` / `processed` / `canonical`) +
  **DuckDB derivado** como engine de consulta, nunca fonte de verdade.
- **Compartilhamento** com o Alexandre é por **pacote de entrega** (XLSX/Parquet/figuras, F-031
  classe D) — ele consome arquivo, não banco.
- **Prazo duro:** Comitê em **2026-10-14**.

## Decisão

**A v1 não usa Supabase nem nenhum banco remoto.** A persistência segue integralmente o ADR-006:
Parquet por camada como fonte de verdade reconstruível, DuckDB local opcional e derivado, entrega em
arquivo. Nada em `data/` é versionado e nada sai da máquina fora do pacote classe D.

## Alternativas consideradas

- **A — Parquet por camada + DuckDB local (ADR-006).** **Escolhida.** Zero credencial, zero rede, zero
  custo, zero migration; `pyarrow` e `duckdb` já estão no `pyproject.toml`; reconstrução por um comando
  com hash idêntico (RNF-001/RF-048); diff e inspeção por camada.
- **B — Supabase (Postgres gerenciado).** Prós: SQL, acesso multiusuário, histórico de vintages
  consultável por terceiros, base pronta para um dashboard futuro. Contras, todos relevantes **agora**:
  introduz **credencial** — o que torna classe **D** pelo `AGENTS.md §2` qualquer feature que a toque, e
  viola RNF-006 ("sem credencial no caminho crítico"); cria **dependência de rede** num pipeline que
  precisa rodar a frio em ≤ 30 min (RNF-008) e numa máquina onde o FRED já está bloqueado na camada de
  aplicação (`skills-manifest §3`, R5); adiciona **custo** e cerimônia de migration; e cria um **risco
  novo e específico** — dado errado persistido remotamente, fora do alcance do "apague e reconstrua",
  justamente no modo de falha dominante do projeto (número errado que não levanta exceção). Nenhum
  benefício para o entregável de 14/10. **Rejeitada na v1.**
- **C — SQLite.** Prós: arquivo único, sem servidor, sem credencial. Contras: pior desempenho analítico
  que o DuckDB, sem leitura nativa de Parquet e binário opaco no diff — já **rejeitada no ADR-006 (C)**.
  Não resolve nada que o Parquet não resolva.

## Consequências

### Positivas
- Mantém o projeto em **zero credencial e zero rede na persistência**: nenhuma feature de armazenamento
  é promovida a classe D por causa de banco.
- Preserva a propriedade central do ADR-006: **o dado é descartável, o script é a verdade**. Reconstrói
  do zero, com o mesmo hash, offline.
- Nada novo para instalar, aprender ou provisionar antes de 14/10.

### Negativas / trade-offs
- Nada de consulta SQL remota ou concorrente: quem quiser os números roda o pipeline ou abre o pacote.
- Histórico de vintages fica em Parquet versionado por coluna/materialização, não em tabela
  consultável por terceiros.
- Se a fase 2 trouxer dashboard, parte do trabalho de modelagem relacional será feita depois.

### Neutras
- Nenhuma dependência é adicionada **ou removida** por este ADR; `duckdb` segue pelo ADR-006. O
  vocabulário de banco (`vintage`, `asof`, `revised`) segue válido — é modelagem, não infraestrutura.

## Gatilhos de reavaliação (fase 2)

Reabrir esta decisão **apenas se** ocorrer um destes:

1. **Dashboard multiusuário** (PRD §4.3 prevê "dashboard de regime corrente" como fase 2).
2. **Atualização automática consumida por outras pessoas** — F-040 (atualização trimestral do regime)
   deixando de ser rodada manualmente pelo Edu.
3. **Histórico de vintages consultável por terceiros**, sem que o terceiro rode o pipeline.

Se qualquer um disparar, Supabase/Postgres entra como **classe D, com ADR próprio** (credencial,
rollback em `docs/plans/infra-ops.md`, gate do `AGENTS.md §14`) e **nunca substitui o Parquet como
fonte reconstruível** — no máximo é uma materialização a jusante, alimentada pelo pipeline.

## Referências

- **ADR-006** (armazenamento e convenção de retornos), alternativa **D — Postgres/Supabase local**
- PRD §4.4 (fora de escopo: interface web, dashboard hospedado, API, deploy), §4.3 (fase 2), §6
  (RNF-004, RNF-006, RNF-008, RNF-009)
- `AGENTS.md §2` (credencial ⇒ classe D) e `§14` (gate da classe D) · `CLAUDE.md §4` (camadas)
- `docs/plans/skills-manifest.md §3` (FRED bloqueado) · `DECISIONS_LOG.md §2` · `TODO.md §4`
