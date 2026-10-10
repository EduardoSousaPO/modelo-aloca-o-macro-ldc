# estrategia-macro-ldc-dados

Ferramenta interna da **LDC Capital** para dar base estatística ao modelo de alocação macro doméstica e ao
dimensionamento da alocação internacional. O projeto extrai, normaliza e alinha séries macroeconômicas
brasileiras (PIB/IBC-Br, IPCA, expectativas do Focus, Selic, taxas de títulos públicos, estrutura a termo da
curva de juros) e séries de desempenho de ativos e subsetores (índices ANBIMA de renda fixa, CDI, índices
amplos e setoriais da B3, FIIs), em uma janela de **20 anos** com frequência **trimestral**, produzindo um
dataset-base canônico sobre o qual se identificam **regimes macro** e se mede como cada classe de ativo e
setor performou em momentos semelhantes. Não é SaaS nem aplicação web: é um pipeline Python que roda local e
alimenta a reunião do Comitê de Alocação. O escopo de origem está em
[`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](docs/product/ESCOPO-EMAIL-ALEXANDRE.md) e é a fonte de verdade.

---

## Stack

- Python 3.11+, pandas, pyarrow
- requests / httpx (extração das fontes)
- pydantic + pandera (contratos de dados)
- DuckDB / Parquet (armazenamento local)
- Jupyter (análise e relatórios)
- pytest + ruff (qualidade)

## Requisitos

- Python ≥ 3.11
- `uv` (recomendado) ou `venv` + pip
- Acesso de rede às fontes públicas (BCB/SGS, IBGE/SIDRA, ANBIMA, B3, Tesouro)

## Como rodar

> **Placeholder** — os comandos do pipeline serão definidos em `/SDD-avancado` e implementados em
> `apps/pipeline/`. Nada abaixo está implementado ainda.

```bash
# ambiente
uv sync                       # ou: python -m venv .venv && pip install -e ".[dev]"

# extração → data/raw/<fonte>/        (placeholder)
python -m pipeline.extract --fonte sgs --desde 2006-01-01

# transformação → data/processed/     (placeholder)
python -m pipeline.transform

# dataset canônico trimestral → data/canonical/   (placeholder)
python -m pipeline.build-canonical

# análise de regimes / relatório      (placeholder)
jupyter lab apps/analysis/
```

## Qualidade

```bash
ruff check . && ruff format --check .       # lint + format
pytest tests/unit                            # N1
pytest tests/integration tests/contract      # N2
pytest tests/e2e                             # N3
pytest -m "not network"                      # pula testes que tocam fontes externas
```

## Estrutura do repositório

Este projeto segue o **Harness v3.2 (Project Wiki + Fast Fix)**, adaptado para projeto de dados. Veja
`AGENTS.md` para papéis, classificação de risco A/B/C/D, Definition of Ready e regras de autonomia/pausa.

```
apps/pipeline/              ← extração, transformação, carga
apps/analysis/              ← notebooks, regimes macro, relatórios
packages/shared/schemas/    ← fonte de verdade dos contratos de dados (Pydantic + pandera)
data/raw/<fonte>/           ← resposta crua da fonte, imutável (não versionado)
data/processed/             ← limpo e tipado por fonte (não versionado)
data/canonical/             ← dataset-base trimestral alinhado (não versionado)
tests/                      ← unit / integration / contract / e2e
docs/product/               ← escopo de origem (e-mail) + PRD
docs/research/              ← pesquisas de fontes e metodologia
docs/specs/, contracts/     ← SPEC + Anti-SPEC, contratos legíveis
docs/wiki/                  ← memória sintetizada do projeto
TODO.md                     ← estado vivo do projeto
AGENTS.md / CLAUDE.md       ← contrato com agentes de IA
```

**Dados não são versionados.** `data/` é reconstruível a partir dos scripts; dado bruto > 5 MB nunca entra
no git. Se um dataset só existe no disco de alguém, ele não existe.

## Como contribuir

1. Pegue o próximo item de `TODO.md` ("Em andamento" ou "Backlog").
2. Confirme a classe A/B/C/D e valide a Definition of Ready (ou crie o Feature Contract inline).
3. Checke a feature contra `docs/product/ESCOPO-EMAIL-ALEXANDRE.md`. Fora do escopo → pause.
4. Crie branch `feat/<slug>` ou `data/<slug>` (classe A trivial pode ir direto em `main`).
5. Escreva teste falhando por critério de aceite, com fixture da fonte.
6. Implemente respeitando os arquivos permitidos no Feature Contract.
7. Rode o CI no nível correspondente: N1 para A/B, N2 para C, N3 para D.
8. Abra PR com matriz de validação + evidências de dados (linhas, intervalo de datas, nulos, 3 valores
   conferidos contra a fonte).
9. CI verde + QA APROVADO com evidência → merge. Atualize `TODO.md` e `docs/wiki/log.md`.

## Prazo

Reunião do **Comitê de Alocação: 2026-10-14**. Publicação de resultado para o Comitê é operação classe D.

## Licença

Interno — LDC Capital. Não distribuir.
