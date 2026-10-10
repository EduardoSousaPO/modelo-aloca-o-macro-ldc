# ADR-006 — Armazenamento (Parquet por camada + DuckDB para consulta) e convenção de retornos

- **Status:** **Proposta** — decisão técnica do agente; **não depende** das 8 decisões bloqueantes,
  mas precisa de validação do Edu antes de virar base da camada canônica (classe C)
- **Data:** 2026-10-10
- **Autor:** `/SDD-avancado` (modo autônomo)
- **Substitui:** o item "ADR-001 — DuckDB vs. Parquet puro" listado como pendente em
  `docs/wiki/architecture.md §5` no kickoff
- **Cobre:** SPEC RF-020..RF-024, RF-043, RF-046, RF-048 · CA-056..071, CA-113, CA-118..122

---

## Contexto

Duas decisões estruturais foram deixadas abertas no kickoff e precisam estar fechadas **antes** de a
camada canônica existir, porque mudá-las depois é classe C com reconstrução completa:

**(a) Como armazenar.** O pipeline roda **local**, em Windows, sem servidor. Os volumes são modestos
(a maior fonte é o CSV do Tesouro, 14,6 MB; o canônico trimestral tem 83 linhas × ~40 colunas e
~2.700 linhas de retorno). O consumo tem dois públicos: **o notebook** (pandas) e o **Alexandre**
(que não roda o pipeline e quer arquivo).

**(b) Convenção de retorno e alinhamento.** A pesquisa é explícita: armazenar na **granularidade
nativa** e agregar por função; trimestral como dado primário é **erro irreversível**. E, para
retorno, misturar subtração com razão, ou price return com total return, introduz viés material
(com Selic a 14% a diferença entre `r − cdi` e `(1+r)/(1+cdi) − 1` não é arredondamento).

## Decisão

### (a) Armazenamento: **Parquet por camada + DuckDB apenas como engine de consulta**

1. **Parquet é o formato de persistência** nas três camadas:
   `data/raw/<fonte>/` (resposta crua, imutável, no formato original da fonte — JSON/CSV/XLS — mais
   um Parquet espelho quando o parse for caro), `data/processed/<fonte>/*.parquet` (tipado, frequência
   nativa) e `data/canonical/*.parquet` (as 6 tabelas do contrato).
2. **DuckDB é opcional e derivado**: um arquivo `data/canonical/macro.duckdb` construído **a partir**
   dos Parquet, para consulta ad hoc e joins no notebook. **Nunca** é fonte de verdade e pode ser
   apagado e regenerado. Não entra no git.
3. **Entrega ao Alexandre em Parquet + CSV/XLSX** (RF-043) — ele consome arquivo, não banco.
4. Nenhum dado versionado: `data/` inteiro no `.gitignore`; a fonte de verdade é o **script**.
5. Reprodutibilidade: um comando reconstrói tudo; rodar duas vezes sobre o mesmo `raw/` produz
   **o mesmo hash** (RF-048). O hash do canônico é registrado no log quando congelado (classe D).

### (b) Convenção de retornos e alinhamento (classe C, congelada aqui)

1. **Granularidade nativa na persistência**; trimestral é **agregação derivada**, sempre calculada.
2. **Trimestre = último dia útil** de mar/jun/set/dez, pelo calendário de feriados **ANBIMA**
   (fallback `bizdays`). Fim de período, nunca média de período, para variável de estoque/preço.
3. **Retorno de T** = `P(último DU de T) / P(último DU de T−1) − 1`.
4. **Encadeamento sempre geométrico** (produto de fatores), nunca soma de retornos.
5. **Excesso sobre CDI e retorno real sempre por razão**: `(1 + r) / (1 + b) − 1`. Teste unitário
   dedicado falha se alguém usar subtração.
6. **CDI trimestral** = `prod(1 + v/100)` sobre a série diária SGS 12 (a série é **percentual**, não
   fator). Valor-canário: 2006 = **15,0271%**.
7. **Total return**: todo ativo carrega `is_total_return`. Comparar price return com total return sem
   a flag é proibido (viés ~2 p.p./ano). `None` = a confirmar (gap G-01).
8. **Forward-fill de no máximo 5 dias úteis** para ativo que não negociou no fechamento; acima disso
   `NULL` registrado, com `ffill_dias_uteis` gravado por linha.
9. **Datas ISO-8601**, índice temporal tz-naive, `vintage` e `collected_at` em toda linha bruta.
10. **Revisão retroativa** da fonte (IBGE revisa o PIB) gera **novo `vintage`** e atualiza a
    materialização corrente — nunca duplica linha.

## Alternativas consideradas

- **A — Só CSV.** Prós: zero dependência, legível à mão. Contras: perde tipo (datas e floats voltam
  como string), arquivo grande, parse lento, decimal/encoding ambíguos — exatamente a classe de bug
  que mais ameaça este projeto. **Rejeitada como persistência** (mantida só na entrega).
- **B — DuckDB como fonte de verdade.** Prós: SQL, joins, um arquivo só. Contras: binário opaco no
  diff, acopla o dado ao engine, e "o dataset existe só no `.duckdb` do disco de alguém" é
  exatamente o anti-padrão que `AGENTS.md §3` proíbe. **Rejeitada como fonte; aceita como engine.**
- **C — SQLite.** Mesmos contras do DuckDB, com pior desempenho analítico e sem leitura nativa de
  Parquet. **Rejeitada.**
- **D — Postgres/Supabase local.** Introduz servidor, migrations e credencial num projeto que roda
  local e não tem deploy. **Rejeitada** (contradiz `wiki/architecture.md §7`).
- **E — Trimestre por média do período** em vez de fim de período. Rejeitada: para preço e estoque a
  média mistura regimes dentro do trimestre e quebra a razão de retorno; a média fica disponível como
  transformação alternativa (`media_do_trimestre`) para variáveis de fluxo.

## Consequências

### Positivas
- Diff e inspeção simples por camada; `pyarrow` já é dependência declarada no `pyproject.toml`.
- DuckDB lê Parquet direto — dá SQL sem duplicar dado.
- Convenções congeladas em um único lugar, citáveis por CA nos Feature Contracts.

### Negativas / trade-offs
- Parquet não é legível em editor de texto: a conferência manual depende de script/notebook.
- Manter DuckDB como derivado exige um passo extra no pipeline (barato, e descartável).
- `ffill` de até 5 DU é uma escolha arbitrária defensável; precisa estar na página de limitações.

### Neutras
- `duckdb` já está no `pyproject.toml`; nenhuma dependência nova é introduzida por este ADR.

## Referências

- PRD §5.2, §5.6, §6 (RNF-001, RNF-009), §11 (RN-01, RN-02, RN-08)
- SPEC §2 (definições), RF-020..024, RF-046..048, Anti-SPEC §10.2.13, §10.4.21-22, §10.4.28
- `docs/research/metodologia-regimes-macro.md` §5.6, §6.5
- `docs/research/fontes-de-dados.md` §B7 (fórmula do CDI validada), riscos R10-R13, R21
- `CLAUDE.md §4` (camadas), `AGENTS.md §3` (regra de ouro dos dados), `§19` (convenções)
- Contratos: `packages/shared/schemas/raw_series.py`, `macro_quarterly.py`,
  `asset_returns_quarterly.py`
