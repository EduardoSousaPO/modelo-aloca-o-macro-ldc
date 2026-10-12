# `analytics-macro/` — o dataset do LDC Analytics

**Esta pasta não é editada à mão. Nunca.** Todo byte aqui dentro é escrito pelo exportador do
projeto de dados (`estrategia-macro-ldc-dados/apps/web_export/`), e qualquer edição manual quebra,
de propósito, a conferência de `sha256` que o loader faz antes de desenhar a tela.

## Por que a pasta mora aqui, na raiz do app, e não em `public/`

Em Next na Vercel, `public/` é servido pela camada **estática**, que **não passa pelo middleware**.
Um `public/data/<tag>/heatmap.json` seria lido por qualquer um que soubesse a URL — e este mesmo
deployment serve o site institucional. O dataset fica fora de `public/`, entra no deploy pelo
`outputFileTracingIncludes` do `next.config.ts` e só sai pela rota
`/api/admin/analytics-macro/[...caminho]`, depois de `checkAdminAuth()`.

É o mesmo mecanismo de `referencia-r2/`, descrito em `src/lib/r2-web/paths.ts`.

## Forma do conteúdo (o que o exportador escreve)

```
analytics-macro/
  current.json                     # O ÚNICO ponteiro: tag, dataset_sha256, meta e arquivos
  <tag>/meta.json                  # MetaWeb: gate, índice de views com sha256, unidades, reduções
  <tag>/ranking_atual.json         # T-01
  <tag>/heatmap_regime_ativo.json  # T-02
  <tag>/vizinhos.json              # T-03
  <tag>/regimes_timeline.json      # T-04 (tela da v2)
  <tag>/internacional.json         # T-06 (tela da v2)
  <tag>/catalogo.json              # T-07
  <tag>/schema.d.ts                # os tipos TS gerados dos modelos pydantic
```

As quatro telas instaladas hoje exigem `ranking_atual`, `heatmap_regime_ativo`, `vizinhos` e
`catalogo`. As outras duas são das telas da v2: quando faltam, o módulo abre normalmente e o que
depende delas aparece desabilitado com o motivo.

Regras que o loader impõe, e recusa desenhar se forem quebradas:

1. **O ponteiro é escrito por último.** Primeiro a pasta da tag inteira, depois `current.json`.
2. **Caminho de tag é imutável.** Tag nunca é sobrescrita; rodada nova é tag nova. É o que torna o
   `Cache-Control: immutable` honesto e o rollback trivial.
3. **Uma tag por requisição.** O `meta.json` e cada view declaram a própria `tag` e o próprio
   `dataset_sha256`, e a tela recusa abrir se algum divergir do ponteiro.
4. **`sha256` por view no `meta.json`.** O loader recalcula e compara.
5. **Nada marcado `publicavel: false` chega aqui.** O corte é do exportador, não da tela; o que foi
   cortado aparece nomeado na tela de Dados e limitações.

## Como publicar uma tag

Na máquina do Edu, dentro do projeto de dados, com o dataset já congelado:

```bash
python -m apps.web_export --tag comite-2026-10-14 \
  --destino "C:/Users/edusp/Projetos_App_Desktop/site-ldc/site-ldc/analytics-macro"
```

Depois: conferir `git status` (só JSON e `schema.d.ts` novos dentro de `analytics-macro/`), rodar os
testes do módulo, commitar no submódulo pelo protocolo do `AGENTS.md` §13 e deixar a Vercel
publicar.

## Rollback

Trocar `current.json` de volta para a tag anterior já basta: as tags antigas continuam em disco e o
caminho delas é imutável. `git revert` do commit de dado é o caminho completo.

## Pasta vazia

Com só este `README.md` e o `.gitkeep`, o módulo abre e mostra o estado "Dataset não instalado",
nomeado, nas quatro telas. Isso é o comportamento correto: nenhuma tela em branco e nenhum número
sem procedência.
