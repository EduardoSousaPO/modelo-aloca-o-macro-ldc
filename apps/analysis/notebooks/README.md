# `apps/analysis/notebooks/` — os cadernos de entrega

> **Regra da pasta, herdada de `CLAUDE.md §3` e `AGENTS.md §19`: notebook não tem lógica de
> negócio.** Todo cálculo vive em `apps/pipeline/`, todo desenho em `apps/analysis/{figuras,tabelas}/`.
> O caderno **abre arquivo, chama função pública e mostra o resultado** — nada mais. E vai para o
> commit **com os outputs limpos**.

## O que tem aqui

| Arquivo | O que é | Feature | CAs |
|---|---|---|---|
| `entrega_comite_2026-10-14.ipynb` | o caderno de leitura do Comitê de Alocação: gate, dados, regimes, "momentos semelhantes", mapa de calor, internacional, limitações, decisões abertas e reprodução | **F-027** | RF-041 / CA-110, CA-111 |

## Como abrir

Do **diretório raiz do repositório**:

```bash
uv run python -m jupyter lab apps/analysis/notebooks/
```

O caderno descobre a raiz do repositório subindo de `Path.cwd()` até achar `pyproject.toml`, então
ele também funciona se você abrir o JupyterLab já dentro desta pasta. Fora da árvore do
repositório ele para na primeira célula com a mensagem dizendo isso — é de propósito: sem a raiz
não há `apps/` para importar nem `data/canonical/` para ler.

**Pré-requisitos:** `uv sync --extra dev` e a camada canônica construída. Se `data/canonical/`
estiver vazia:

```bash
uv run python -m apps.pipeline run --offline   # reconstrói do bruto já arquivado, sem rede
uv run python -m apps.pipeline verify          # confere sha256 contra o MANIFEST.json
```

## Como exportar para quem não abre Jupyter

O HTML executado é o formato de leitura para o gestor — e **não é versionado**: ele mora em
`data/canonical/entrega/`, que é camada de dado reconstruível.

```bash
# 1. executar uma CÓPIA (nunca o arquivo versionado)
cp apps/analysis/notebooks/entrega_comite_2026-10-14.ipynb data/canonical/entrega/_executado.ipynb
uv run python -m nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.timeout=900 data/canonical/entrega/_executado.ipynb

# 2. exportar o HTML a partir da cópia executada
uv run python -m nbconvert --to html --output-dir data/canonical/entrega \
    --output entrega_comite_2026-10-14.html data/canonical/entrega/_executado.ipynb
```

> Use `python -m nbconvert`, **não** `jupyter nbconvert`: o despachante `jupyter` resolve pelo
> `PATH` e pode cair num Python global com extensões antigas instaladas.

## Antes de commitar

```bash
uv run python -m nbconvert --clear-output apps/analysis/notebooks/entrega_comite_2026-10-14.ipynb
uv run ruff check . && uv run ruff format --check .      # o ruff linta e formata .ipynb
uv run pytest tests/unit/test_notebook_entrega.py -q
```

**Atenção ao fim de linha.** O `nbconvert` grava com o terminador da plataforma (CRLF no Windows),
e o arquivo versionado aqui é **LF** — há teste que falha se um CR entrar, porque CRLF muda o
`sha256` do mesmo conteúdo e quebra a comparação entre checkouts (mesma razão de `D-v` no
`DECISIONS_LOG`). Se o `--clear-output` introduzir CRLF, normalize antes de commitar.

## O que os testes não deixam passar

`tests/unit/test_notebook_entrega.py` lê o `.ipynb` e reprova, entre outras coisas:

- **output ou `execution_count` no commit** (CA-111);
- **`def`, `async def`, `lambda` ou `class`** em célula de código (CA-110);
- **operador aritmético** — `+ - * / // % ** @`, inclusive `+=` — em célula de código. Comparação e
  combinação booleana de máscaras do pandas (`&`, `|`, `~`) são permitidas: recortar linha não é
  calcular;
- **método de agregação do pandas** (`sum`, `mean`, `groupby`, `apply`, `rolling`, `pct_change`…);
- **magia de IPython** (`%`, `!`) e import fora da lista declarada;
- **caminho de camada escrito à mão** (`data/canonical/...`) ou caminho absoluto de máquina — o
  endereço vem de `apps.pipeline.common.io_layers.caminho_canonical`;
- **qualquer escrita em disco** (`to_parquet`, `write_text`, `savefig`, `mkdir`) — Anti-SPEC §10.4.22;
- **relógio, `random`, `uuid`, variável de ambiente** e qualquer módulo de rede;
- **linguagem preditiva** em qualquer célula, pela guarda executável
  `conferir_linguagem_descritiva` de `apps/analysis/tabelas/ranking_regime_atual.py` (Anti-SPEC
  §10.2.10) — a mesma que trava a tabela do Comitê;
- **a tabela de variância mínima por regime**, que a Anti-SPEC §10.5 põe fora da entrega de
  2026-10-14: o caderno entrega a **faixa** de D6 e declara a ausência.

Como formatar número em pt-BR sem usar aritmética: importe `pct`, `pp` e `num` de
`apps.analysis.tabelas.ranking_regime_atual` e passe a função ao `Styler.format` do pandas.

## O caderno é gerado, não digitado

As células de `entrega_comite_2026-10-14.ipynb` foram montadas uma por uma com `nbformat`, com
`id` explícito em cada uma — sem o `id` fixo o `nbformat` sorteia um novo a cada gravação e o
arquivo muda de bytes sem mudar de conteúdo, o que torna o diff inútil. Duas gerações seguidas
produzem o **mesmo `sha256`**.

**Dívida registrada (ver `docs/wiki/context/F-027.md §6`):** o gerador **não** está versionado — o
contrato de F-027 não previa arquivo para ele e `scripts/` na raiz é proibido (Anti-SPEC §10.4.29).
Até o orquestrador decidir onde ele mora (proposta: `apps/analysis/notebooks/_gerar_entrega.py`), a
manutenção é **no próprio `.ipynb`**, que é JSON legível: edite o `source` da célula, mantenha o
`id`, rode `ruff format` e `--clear-output`.

## Convenções para um caderno novo nesta pasta

1. Nome que diz **para quem e para quando** (`entrega_comite_<data>`), não `analise_v3_final`.
2. Primeira célula de código: resolução da raiz, imports e os relatórios lidos de uma vez. Nenhum
   `import` espalhado pelo meio.
3. Primeira seção: **o gate**, lido do disco (`especificacao_congelada`) mais o `DATASET_SHA256` da
   rodada. Afirmação sobre publicabilidade nunca é texto digitado.
4. Toda célula numérica mostra o **`n`** (Anti-SPEC §10.2.8) e todo ponto de atenção entra como
   ressalva ao lado do número, não em nota de rodapé.
5. Caderno novo ⇒ linha na tabela deste README e um arquivo de teste irmão de
   `test_notebook_entrega.py`.
