/**
 * A API que serve o dataset do LDC Analytics — DE FORA de `public/`.
 *
 * Quem desenha as telas é Server Component e lê o disco direto pelo loader: esta rota não é a
 * fonte delas. Ela existe para três coisas, todas reais: conferir por `curl` (ou por link no
 * rodapé de procedência) exatamente o JSON que a tela desenhou, baixar o `schema.d.ts` da tag, e
 * ser o caminho das exportações da v2 (CSV e PNG do recorte visível).
 *
 * Esta rota é a razão pela qual o módulo pode viver no mesmo deployment do site
 * institucional. Em Next na Vercel, `public/` é servido pela camada ESTÁTICA, que **não passa
 * pelo middleware**: um `public/data/<tag>/heatmap.json` seria lido por qualquer um que
 * soubesse a URL. O dataset mora em `analytics-macro/` na raiz do app, entra no deploy pelo
 * `outputFileTracingIncludes` e só sai por aqui, depois de `checkAdminAuth()`. É o mesmo
 * mecanismo de `referencia-r2/` (`src/lib/r2-web/paths.ts` + `next.config.ts`).
 *
 * Três decisões, todas verificáveis no código abaixo:
 *
 * 1. **Allowlist, não sanitização.** O caminho aceito é `current.json` ou
 *    `<tag>/<arquivo-declarado>`, com a tag validada por forma e o arquivo conferido contra a
 *    lista de `VIEWS` do loader. Qualquer outra coisa é 404 — inclusive `..`, caminho
 *    absoluto e barra invertida, que não precisam de tratamento especial porque não estão na
 *    lista. A lista é a MESMA que o loader usa, importada, não copiada.
 * 2. **Cache honesto.** O ponteiro é `no-store`: ele é o único arquivo que muda de conteúdo.
 *    O arquivo de uma tag é `immutable` com um ano, porque o caminho contém a tag e a tag
 *    nunca é sobrescrita (RF-W011). `private` em todos: nada de CDN compartilhado para dado
 *    do Comitê. `Vary: Cookie` porque a resposta depende da sessão.
 * 3. **Sem corpo de erro falante.** 401 e 404 respondem o mínimo. Dizer "a tag existe mas
 *    você não tem acesso" é contar o que não precisa ser contado.
 */

import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";

import { checkAdminAuth } from "@/lib/auth-check";

import {
  PASTA_DO_DATASET,
  resolverCaminho,
} from "@/app/admin/analytics-macro/_lib/dataset";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UM_ANO = 60 * 60 * 24 * 365;

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ caminho: string[] }> },
) {
  const usuario = await checkAdminAuth();
  if (!usuario) {
    return NextResponse.json({ error: "Nao autorizado" }, { status: 401 });
  }

  const { caminho } = await params;
  const segmentos = Array.isArray(caminho) ? caminho : [];
  const alvo = resolverCaminho(segmentos);
  if (!alvo) {
    return NextResponse.json({ error: "Nao encontrado" }, { status: 404 });
  }

  let conteudo: string;
  try {
    conteudo = await readFile(alvo.caminhoAbsoluto, "utf8");
  } catch {
    /*
     * 404, e não 500: o caminho é válido pela allowlist e o arquivo não está em disco. É o
     * estado normal de um app recém-instalado, em que `analytics-macro/` só tem o `.gitkeep`
     * — e a tela do módulo já trata isso com um estado vazio nomeado.
     */
    return NextResponse.json(
      { error: "Nao encontrado", detalhe: `${PASTA_DO_DATASET}/${segmentos.join("/")}` },
      { status: 404 },
    );
  }

  const cache =
    alvo.tipo === "ponteiro"
      ? "private, no-store, max-age=0, must-revalidate"
      : `private, max-age=${UM_ANO}, immutable`;

  /*
   * O `schema.d.ts` que o exportador grava junto das views sai como texto: é o contrato de tipos,
   * serve para conferência e para quem for escrever a quinta tela, e não é JSON.
   */
  const tipo = alvo.arquivo.endsWith(".d.ts")
    ? "text/plain; charset=utf-8"
    : "application/json; charset=utf-8";

  return new NextResponse(conteudo, {
    status: 200,
    headers: {
      "Content-Type": tipo,
      "Cache-Control": cache,
      Vary: "Cookie",
      "X-Content-Type-Options": "nosniff",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}
