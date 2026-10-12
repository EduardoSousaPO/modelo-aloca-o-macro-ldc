/**
 * Loader do dataset do LDC Analytics — Alocação Macro.
 *
 * É SÓ DE SERVIDOR. Usa `node:fs`, então o bundler do Next recusa importá-lo de um componente
 * cliente (`"use client"`) — a garantia é essa, e não um `import "server-only"`: o pacote
 * `server-only` NÃO está em `node_modules` deste app (verificado) e a regra é zero dependência
 * nova.
 *
 * O molde é `src/lib/r2-web/paths.ts` + `referencia-r2/`, item por item: o dado mora em
 * `analytics-macro/` na RAIZ do app (nunca em `public/`, que é servido pela camada estática e
 * não passa pelo middleware); o caminho em runtime é `join(process.cwd(), ...)` porque
 * `import.meta.url` não sobrevive ao bundle do Next/Vercel; e os arquivos entram no deploy por
 * `outputFileTracingIncludes`.
 *
 * O CONTRATO É O DO EXPORTADOR, não um inventado aqui: `apps/web_export/` emite
 * `current.json` (o ponteiro, com `arquivos` mapeando view → caminho relativo), `<tag>/meta.json`
 * (`MetaWeb`, com o gate, o índice de views com `sha256`, as unidades e as reduções declaradas),
 * `<tag>/<view>.json` (cada uma com o envelope `view/tela/pergunta/tag/dataset_sha256/gate/fontes`)
 * e `<tag>/schema.d.ts`, que é a cópia de `_lib/schema.d.ts`.
 *
 * AS TRÊS REGRAS QUE ESTE ARQUIVO EXISTE PARA CUMPRIR
 *
 * 1. **Uma tag por requisição.** `abrirDataset()` lê `current.json`, FIXA a tag e devolve uma
 *    sessão. Nenhuma função aceita tag por parâmetro — então é impossível, por construção, uma
 *    tela mostrar heatmap de uma tag com ranking de outra: o risco nº 2 de
 *    `ldc-analytics-arquitetura.md` §7, que é silencioso quando acontece.
 * 2. **Hash e identidade conferidos; divergência é erro de tela** (RF-W012): o `sha256` de cada
 *    view é recalculado e comparado com o do `meta.json`, e `tag`/`dataset_sha256` de dentro da
 *    view têm de bater com os da sessão.
 * 3. **Falha fechada.** Ausência, JSON inválido, meta divergente: tudo levanta `ErroDeDataset`,
 *    que a tela renderiza nomeando a view e o hash esperado (RF-W049). Nunca tela em branco.
 */

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { cache } from "react";

import type {
  CatalogoView,
  GateDaView,
  HeatmapView,
  InternacionalView,
  MetaWeb,
  PonteiroCurrent,
  RankingAtualView,
  TimelineView,
  VizinhosView,
} from "./schema";

/** Nome da pasta do dataset, na raiz do app. Espelha `referenciaDir()` do R2. */
export const PASTA_DO_DATASET = "analytics-macro";

/** O ponteiro. Único arquivo fora de uma pasta de tag, e o único que não é imutável. */
export const ARQUIVO_DO_PONTEIRO = "current.json";

/** O manifesto da tag, no vocabulário do exportador. */
export const ARQUIVO_DO_META = "meta.json";

/** O `.d.ts` gerado, que o exportador grava junto das views. */
export const ARQUIVO_DOS_TIPOS = "schema.d.ts";

/**
 * O mapa view → tipo. As chaves são EXATAMENTE as de `VIEWS` em
 * `packages/shared/schemas/web_views.py`; o arquivo de cada uma vem do `current.json`
 * (`arquivos`), para o front não adivinhar nome — mas a allowlist da API usa esta lista.
 */
export interface MapaDeViews {
  ranking_atual: RankingAtualView;
  heatmap_regime_ativo: HeatmapView;
  vizinhos: VizinhosView;
  regimes_timeline: TimelineView;
  internacional: InternacionalView;
  catalogo: CatalogoView;
}

export const NOMES_DE_VIEW = [
  "ranking_atual",
  "heatmap_regime_ativo",
  "vizinhos",
  "regimes_timeline",
  "internacional",
  "catalogo",
] as const satisfies readonly (keyof MapaDeViews)[];

export type NomeDeView = (typeof NOMES_DE_VIEW)[number];

/**
 * As views que as quatro telas desta entrega exigem. `regimes_timeline` e `internacional` são
 * das telas da v2: quando faltam, o módulo abre normalmente e a tela que depende delas aparece
 * desabilitada com o motivo (regra 2 do registry, `arquitetura` §6.3).
 */
export const VIEWS_OBRIGATORIAS: readonly NomeDeView[] = [
  "ranking_atual",
  "heatmap_regime_ativo",
  "vizinhos",
  "catalogo",
];

/** Janela curta do memo do PONTEIRO. Ele é `no-cache` na API; aqui só evita ler disco duas vezes. */
export const JANELA_DO_PONTEIRO_MS = 30_000;

export class ErroDeDataset extends Error {
  readonly codigo:
    | "DATASET_AUSENTE"
    | "JSON_INVALIDO"
    | "TAG_DIVERGENTE"
    | "HASH_DIVERGENTE"
    | "VIEW_AUSENTE"
    | "CONTRATO_INVALIDO";
  readonly detalhe: string;

  constructor(codigo: ErroDeDataset["codigo"], mensagem: string, detalhe = "") {
    super(mensagem);
    this.name = "ErroDeDataset";
    this.codigo = codigo;
    this.detalhe = detalhe;
  }
}

/** Diretório do dataset em runtime. */
export function diretorioDoDataset(): string {
  return join(process.cwd(), PASTA_DO_DATASET);
}

export function tagEhValida(tag: unknown): tag is string {
  return typeof tag === "string" && /^[a-z0-9][a-z0-9._-]{0,63}$/.test(tag);
}

/**
 * Resolve um caminho RELATIVO dentro do dataset, recusando qualquer coisa que não seja
 * `current.json` ou `<tag>/<arquivo-da-allowlist>`.
 *
 * A tag é validada por forma, então `..`, barra invertida, caminho absoluto e byte nulo caem
 * fora antes de qualquer `join`: a travessia de diretório não é barrada por sanitização, é
 * barrada por lista.
 */
export function resolverCaminho(segmentos: readonly string[]): {
  caminhoAbsoluto: string;
  tipo: "ponteiro" | "tag";
  tag: string | null;
  arquivo: string;
} | null {
  if (segmentos.length === 1 && segmentos[0] === ARQUIVO_DO_PONTEIRO) {
    return {
      caminhoAbsoluto: join(diretorioDoDataset(), ARQUIVO_DO_PONTEIRO),
      tipo: "ponteiro",
      tag: null,
      arquivo: ARQUIVO_DO_PONTEIRO,
    };
  }
  if (segmentos.length !== 2) return null;
  const [tag, arquivo] = segmentos;
  if (!tagEhValida(tag)) return null;
  const permitidos: string[] = [
    ARQUIVO_DO_META,
    ARQUIVO_DOS_TIPOS,
    ...NOMES_DE_VIEW.map((n) => `${n}.json`),
  ];
  if (!permitidos.includes(arquivo)) return null;
  return {
    caminhoAbsoluto: join(diretorioDoDataset(), tag, arquivo),
    tipo: "tag",
    tag,
    arquivo,
  };
}

export function sha256De(texto: string): string {
  return createHash("sha256").update(texto, "utf8").digest("hex");
}

async function lerJson(
  caminhoAbsoluto: string,
  rotulo: string,
): Promise<{ bruto: string; dado: unknown }> {
  let bruto: string;
  try {
    bruto = await readFile(caminhoAbsoluto, "utf8");
  } catch {
    throw new ErroDeDataset(
      "DATASET_AUSENTE",
      `Dataset ausente: ${rotulo} não foi encontrado.`,
      caminhoAbsoluto,
    );
  }
  try {
    return { bruto, dado: JSON.parse(bruto) as unknown };
  } catch (e) {
    throw new ErroDeDataset(
      "JSON_INVALIDO",
      `JSON inválido em ${rotulo}.`,
      e instanceof Error ? e.message : String(e),
    );
  }
}

/* ───────────────────────── conferências (puras, testáveis) ───────────────────────── */

export function conferirPonteiro(dado: unknown): PonteiroCurrent {
  const p = dado as Partial<PonteiroCurrent> | null;
  if (!p || typeof p !== "object") {
    throw new ErroDeDataset("CONTRATO_INVALIDO", "current.json não é um objeto.");
  }
  if (!tagEhValida(p.tag)) {
    throw new ErroDeDataset(
      "CONTRATO_INVALIDO",
      "current.json sem campo `tag` válido.",
      String(p.tag),
    );
  }
  if (typeof p.dataset_sha256 !== "string" || p.dataset_sha256.length !== 64) {
    throw new ErroDeDataset(
      "CONTRATO_INVALIDO",
      "current.json sem `dataset_sha256` de 64 caracteres.",
    );
  }
  if (typeof p.meta !== "string" || !p.arquivos || typeof p.arquivos !== "object") {
    throw new ErroDeDataset(
      "CONTRATO_INVALIDO",
      "current.json sem `meta` e `arquivos` — é o ponteiro que diz onde cada view mora.",
    );
  }
  return p as PonteiroCurrent;
}

export function conferirMeta(dado: unknown, ponteiro: PonteiroCurrent): MetaWeb {
  const m = dado as Partial<MetaWeb> | null;
  if (!m || typeof m !== "object") {
    throw new ErroDeDataset("CONTRATO_INVALIDO", "meta.json não é um objeto.");
  }
  if (m.tag !== ponteiro.tag) {
    throw new ErroDeDataset(
      "TAG_DIVERGENTE",
      `meta.json é da tag "${String(m.tag)}" e o ponteiro aponta para "${ponteiro.tag}".`,
      "Uma tela nunca mistura duas tags. Recarregue depois de publicar o dataset completo.",
    );
  }
  if (m.dataset_sha256 !== ponteiro.dataset_sha256) {
    throw new ErroDeDataset(
      "HASH_DIVERGENTE",
      "O `dataset_sha256` do ponteiro não é o do meta.json.",
      `ponteiro ${String(ponteiro.dataset_sha256).slice(0, 12)}…, meta ${String(m.dataset_sha256).slice(0, 12)}…`,
    );
  }
  if (!m.gate || typeof m.gate.especificacao_congelada !== "boolean" || typeof m.gate.publicavel !== "boolean") {
    throw new ErroDeDataset(
      "CONTRATO_INVALIDO",
      "meta.json sem o bloco `gate` com os dois booleanos.",
      "Sem o gate declarado o módulo falha fechado: nenhuma tela abre.",
    );
  }
  if (!Array.isArray(m.views)) {
    throw new ErroDeDataset("CONTRATO_INVALIDO", "meta.json sem o índice `views`.");
  }
  const declaradas = new Set(m.views.map((v) => v.view));
  const faltando = VIEWS_OBRIGATORIAS.filter((v) => !declaradas.has(v));
  if (faltando.length > 0) {
    throw new ErroDeDataset(
      "VIEW_AUSENTE",
      `A tag "${ponteiro.tag}" não declara ${faltando.length} view obrigatória(s).`,
      faltando.join(", "),
    );
  }
  return m as MetaWeb;
}

/**
 * Confere uma view contra o `meta.json`: hash recalculado, `tag` e `dataset_sha256` internos.
 * As três existem porque falham por motivos diferentes — hash pega byte trocado; tag pega
 * publicação parcial (ponteiro novo, arquivo velho); `dataset_sha256` pega tag reaproveitada.
 */
export function conferirView(nome: NomeDeView, bruto: string, dado: unknown, meta: MetaWeb): void {
  const declarada = meta.views.find((v) => v.view === nome);
  if (!declarada) {
    throw new ErroDeDataset("VIEW_AUSENTE", `A view "${nome}" não é declarada pela tag "${meta.tag}".`);
  }
  const calculado = sha256De(bruto);
  if (declarada.sha256 && calculado !== declarada.sha256) {
    throw new ErroDeDataset(
      "HASH_DIVERGENTE",
      `A view "${nome}" não casa com o hash declarado no meta.json.`,
      `esperado ${declarada.sha256.slice(0, 12)}…, lido ${calculado.slice(0, 12)}…`,
    );
  }
  const envelope = dado as { tag?: unknown; dataset_sha256?: unknown } | null;
  if (envelope?.tag !== meta.tag) {
    throw new ErroDeDataset(
      "TAG_DIVERGENTE",
      `A view "${nome}" é da tag "${String(envelope?.tag)}" e a sessão está fixada em "${meta.tag}".`,
      "Duas tags na mesma tela é o erro que esta conferência existe para impedir.",
    );
  }
  if (envelope?.dataset_sha256 !== meta.dataset_sha256) {
    throw new ErroDeDataset(
      "HASH_DIVERGENTE",
      `A view "${nome}" declara outro dataset.`,
      `view ${String(envelope?.dataset_sha256).slice(0, 12)}…, sessão ${meta.dataset_sha256.slice(0, 12)}…`,
    );
  }
}

/* ───────────────────────── a sessão ───────────────────────── */

export interface SessaoDoDataset {
  /** A tag FIXADA desta requisição. Ninguém pode trocá-la. */
  readonly tag: string;
  readonly ponteiro: PonteiroCurrent;
  readonly meta: MetaWeb;
  /** `true` quando a view é declarada por esta tag. */
  temView(nome: NomeDeView): boolean;
  /** Lê e confere uma view. Levanta `ErroDeDataset` em qualquer divergência. */
  lerView<N extends NomeDeView>(nome: N): Promise<MapaDeViews[N]>;
}

type Memo = { arquivo: string; sha256: string; dado: unknown };

/**
 * Memo em memória das views. A chave inclui o `sha256` e o caminho inclui a tag — e tag é
 * imutável por contrato (RF-W011). Então valor memoizado nunca fica velho: ou a chave é a mesma
 * e o conteúdo é o mesmo, ou a chave muda. É por isso que aqui não há TTL.
 */
const memoDeViews = new Map<string, Memo>();
let memoDoPonteiro: { em: number; ponteiro: PonteiroCurrent } | null = null;

/** Limpa os memos. Existe para o teste; em produção ninguém chama. */
export function limparMemo(): void {
  memoDeViews.clear();
  memoDoPonteiro = null;
}

export async function lerPonteiro(agora = Date.now()): Promise<PonteiroCurrent> {
  if (memoDoPonteiro && agora - memoDoPonteiro.em < JANELA_DO_PONTEIRO_MS) {
    return memoDoPonteiro.ponteiro;
  }
  const { dado } = await lerJson(
    join(diretorioDoDataset(), ARQUIVO_DO_PONTEIRO),
    `${PASTA_DO_DATASET}/${ARQUIVO_DO_PONTEIRO}`,
  );
  const ponteiro = conferirPonteiro(dado);
  memoDoPonteiro = { em: agora, ponteiro };
  return ponteiro;
}

/**
 * O nome do arquivo de uma view, **lido do ponteiro** ("view -> caminho relativo, para o front
 * não adivinhar o nome"), com o nome convencional como última saída.
 */
function arquivoDaView(ponteiro: PonteiroCurrent, nome: NomeDeView): string {
  const relativo = ponteiro.arquivos?.[nome];
  if (typeof relativo === "string" && relativo.length > 0) {
    const pedacos = relativo.split("/");
    return pedacos[pedacos.length - 1];
  }
  return `${nome}.json`;
}

/** A implementação sem memo de requisição. É a porta que o teste usa. */
export async function abrirDatasetSemCache(): Promise<SessaoDoDataset> {
  const ponteiro = await lerPonteiro();
  const tag = ponteiro.tag;
  const { dado } = await lerJson(
    join(diretorioDoDataset(), tag, ARQUIVO_DO_META),
    `${PASTA_DO_DATASET}/${tag}/${ARQUIVO_DO_META}`,
  );
  const meta = conferirMeta(dado, ponteiro);

  const temView = (nome: NomeDeView) => meta.views.some((v) => v.view === nome);

  async function lerView<N extends NomeDeView>(nome: N): Promise<MapaDeViews[N]> {
    const declarada = meta.views.find((v) => v.view === nome);
    if (!declarada) {
      throw new ErroDeDataset(
        "VIEW_AUSENTE",
        `A view "${nome}" não é declarada pela tag "${tag}".`,
        "A tela que depende dela aparece desabilitada com este motivo.",
      );
    }
    const arquivo = declarada.arquivo || arquivoDaView(ponteiro, nome);
    const chave = `${tag}/${arquivo}#${declarada.sha256}`;
    const guardado = memoDeViews.get(chave);
    if (guardado) return guardado.dado as MapaDeViews[N];

    const { bruto, dado: conteudo } = await lerJson(
      join(diretorioDoDataset(), tag, arquivo),
      `${PASTA_DO_DATASET}/${tag}/${arquivo}`,
    );
    conferirView(nome, bruto, conteudo, meta);
    memoDeViews.set(chave, { arquivo, sha256: declarada.sha256, dado: conteudo });
    return conteudo as MapaDeViews[N];
  }

  return { tag, ponteiro, meta, temView, lerView };
}

/**
 * Abre o dataset com a tag fixada PARA ESTA REQUISIÇÃO.
 *
 * `cache()` do React memoiza por requisição: as quatro telas podem chamar à vontade e o disco é
 * lido uma vez. E como a tag sai daqui, duas chamadas na mesma árvore devolvem necessariamente
 * a mesma tag.
 */
export const abrirDataset = cache(abrirDatasetSemCache);

/**
 * O estado do gate, derivado do `meta.json` — e com FALHA FECHADA: meta ausente ou ilegível
 * devolve o estado mais restritivo, nunca "está liberado".
 */
export interface EstadoDoGate {
  fechado: boolean;
  especificacao_congelada: boolean;
  publicavel: boolean;
  status_adr_001: string;
  /** A faixa que o próprio exportador escreveu. Vazia quando congelada. */
  marca: string;
  veredito: string;
}

export function estadoDoGate(gate: GateDaView | null | undefined): EstadoDoGate {
  if (!gate) {
    return {
      fechado: true,
      especificacao_congelada: false,
      publicavel: false,
      status_adr_001: "DESCONHECIDO",
      marca: "MATERIAL DE DISCUSSAO - estado do dataset nao foi lido",
      veredito: "O estado do gate não pôde ser lido. O mais restritivo é o padrão.",
    };
  }
  return {
    fechado: !gate.especificacao_congelada || !gate.publicavel,
    especificacao_congelada: gate.especificacao_congelada,
    publicavel: gate.publicavel,
    status_adr_001: gate.status_adr_001 || "DESCONHECIDO",
    marca: gate.marca ?? "",
    veredito: gate.veredito_publicacao ?? "",
  };
}

/**
 * `Resultado` + `tentar`: o jeito de uma tela carregar sem `try/catch` em volta de JSX. Com
 * `tentar`, a tela tem duas saídas explícitas — a de erro, que renderiza a moldura nomeada, e a
 * de sucesso, em que `valor` já está tipado. Evita o `let` sem inicializador, que o TypeScript
 * aceita como "any evolutivo" e que tiraria a verificação do caminho em que o dado entra.
 */
export type Resultado<T> = { ok: true; valor: T } | { ok: false; erro: ErroDeDataset | Error };

export async function tentar<T>(promessa: Promise<T>): Promise<Resultado<T>> {
  try {
    return { ok: true, valor: await promessa };
  } catch (e) {
    return { ok: false, erro: e instanceof Error ? e : new Error(String(e)) };
  }
}

/** Caminho da API que serve um arquivo da tag. Usado pelo cliente, nunca `fs` no cliente. */
export function urlDoArquivo(tag: string, arquivo: string): string {
  return `/api/admin/analytics-macro/${encodeURIComponent(tag)}/${encodeURIComponent(arquivo)}`;
}
