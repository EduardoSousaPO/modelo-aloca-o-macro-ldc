/**
 * O LOADER RECUSA DUAS TAGS — e recusa hash que não bate.
 *
 * O risco é o nº 2 de `ldc-analytics-arquitetura.md` §7, e o que o torna grave é o silêncio:
 * heatmap de uma tag com ranking de outra desenha perfeitamente, e ninguém vê. Daí as quatro
 * conferências testadas aqui:
 *
 *   1. o `meta.json` tem de ser da tag que o `current.json` aponta;
 *   2. o `dataset_sha256` do ponteiro tem de ser o do meta;
 *   3. cada view tem de declarar, no envelope, a mesma `tag` e o mesmo `dataset_sha256`;
 *   4. o `sha256` recalculado do arquivo tem de ser o declarado no índice do meta.
 *
 * E a propriedade de desenho que fecha a porta: nenhuma função do loader aceita tag por
 * parâmetro. A tag sai do ponteiro, fica na sessão, e `lerView` a usa — então "duas tags na mesma
 * tela" não é um caminho que o chamador consiga escrever.
 */

import { createHash } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";

const readFileMock = vi.fn();
vi.mock("node:fs/promises", () => ({ readFile: (...args: unknown[]) => readFileMock(...args) }));

import {
  ErroDeDataset,
  NOMES_DE_VIEW,
  abrirDatasetSemCache,
  conferirView,
  limparMemo,
  resolverCaminho,
  tagEhValida,
} from "../_lib/dataset";
import { OUTRA_TAG, SHA, TAG, meta as metaBase } from "./fixtura";

const sha = (texto: string) => createHash("sha256").update(texto, "utf8").digest("hex");

const OBRIGATORIAS = ["ranking_atual", "heatmap_regime_ativo", "vizinhos", "catalogo"] as const;

/**
 * Monta o disco falso. Cada opção liga UMA das divergências que o loader tem de recusar.
 */
function montarDisco(
  opcoes: {
    tagDoPonteiro?: string;
    tagDoMeta?: string;
    tagDentroDaView?: string;
    shaDentroDaView?: string;
    shaDoPonteiro?: string;
    shaDeclaradoErrado?: boolean;
    viewsObrigatoriasFaltando?: boolean;
  } = {},
) {
  const tagPonteiro = opcoes.tagDoPonteiro ?? TAG;
  const tagMeta = opcoes.tagDoMeta ?? TAG;
  const tagView = opcoes.tagDentroDaView ?? TAG;
  const shaView = opcoes.shaDentroDaView ?? SHA;

  const corpoDaView = new Map<string, string>();
  for (const nome of OBRIGATORIAS) {
    corpoDaView.set(
      nome,
      JSON.stringify({ view: nome, tela: "T-0X", pergunta: "?", tag: tagView, dataset_sha256: shaView }),
    );
  }

  const nomes = opcoes.viewsObrigatoriasFaltando ? OBRIGATORIAS.slice(0, 2) : OBRIGATORIAS;
  const views = nomes.map((nome) => ({
    arquivo: `${nome}.json`,
    view: nome,
    tela: "T-0X",
    slot_arquitetura: "slot",
    bytes: corpoDaView.get(nome)!.length,
    sha256: opcoes.shaDeclaradoErrado ? sha("outro conteudo") : sha(corpoDaView.get(nome)!),
    n_registros: 0,
  }));

  const meta = metaBase({ tag: tagMeta, views });

  readFileMock.mockImplementation(async (caminho: string) => {
    const p = String(caminho).replace(/\\/g, "/");
    if (p.endsWith("/current.json")) {
      return JSON.stringify({
        tag: tagPonteiro,
        dataset_sha256: opcoes.shaDoPonteiro ?? SHA,
        meta: `${tagPonteiro}/meta.json`,
        arquivos: Object.fromEntries(nomes.map((n) => [n, `${tagPonteiro}/${n}.json`])),
        especificacao_congelada: false,
        cache_control: "no-cache",
        cache_control_da_tag: "immutable",
      });
    }
    if (p.endsWith("/meta.json")) return JSON.stringify(meta);
    for (const [nome, corpo] of corpoDaView) {
      if (p.endsWith(`/${nome}.json`)) return corpo;
    }
    throw new Error(`ENOENT: ${p}`);
  });

  return { meta, corpoDaView };
}

beforeEach(() => {
  readFileMock.mockReset();
  limparMemo();
});

describe("loader: uma tag por requisição", () => {
  it("abre o dataset e fixa a tag do ponteiro", async () => {
    montarDisco();
    const sessao = await abrirDatasetSemCache();
    expect(sessao.tag).toBe(TAG);
    expect(sessao.meta.tag).toBe(TAG);
    const view = await sessao.lerView("ranking_atual");
    expect(view.tag).toBe(TAG);
  });

  it("recusa meta de outra tag, nomeando as duas", async () => {
    montarDisco({ tagDoMeta: OUTRA_TAG });
    const erro = await abrirDatasetSemCache().catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroDeDataset);
    expect((erro as ErroDeDataset).codigo).toBe("TAG_DIVERGENTE");
    expect((erro as ErroDeDataset).message).toContain(TAG);
    expect((erro as ErroDeDataset).message).toContain(OUTRA_TAG);
  });

  it("recusa ponteiro e meta com dataset_sha256 diferentes", async () => {
    montarDisco({ shaDoPonteiro: sha("outro dataset") });
    const erro = await abrirDatasetSemCache().catch((e: unknown) => e);
    expect((erro as ErroDeDataset).codigo).toBe("HASH_DIVERGENTE");
  });

  it("recusa view cuja tag interna não é a da sessão (publicação parcial)", async () => {
    montarDisco({ tagDentroDaView: OUTRA_TAG });
    const sessao = await abrirDatasetSemCache();
    const erro = await sessao.lerView("heatmap_regime_ativo").catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroDeDataset);
    expect((erro as ErroDeDataset).codigo).toBe("TAG_DIVERGENTE");
    expect((erro as ErroDeDataset).message).toContain(OUTRA_TAG);
    expect((erro as ErroDeDataset).message).toContain(TAG);
  });

  it("recusa view que declara outro dataset, mesmo com a tag certa", async () => {
    montarDisco({ shaDentroDaView: sha("dataset antigo") });
    const sessao = await abrirDatasetSemCache();
    const erro = await sessao.lerView("catalogo").catch((e: unknown) => e);
    expect((erro as ErroDeDataset).codigo).toBe("HASH_DIVERGENTE");
  });

  it("recusa view cujo sha256 não é o declarado no meta", async () => {
    montarDisco({ shaDeclaradoErrado: true });
    const sessao = await abrirDatasetSemCache();
    const erro = await sessao.lerView("vizinhos").catch((e: unknown) => e);
    expect(erro).toBeInstanceOf(ErroDeDataset);
    expect((erro as ErroDeDataset).codigo).toBe("HASH_DIVERGENTE");
  });

  it("recusa tag que não declara as views obrigatórias", async () => {
    montarDisco({ viewsObrigatoriasFaltando: true });
    const erro = await abrirDatasetSemCache().catch((e: unknown) => e);
    expect((erro as ErroDeDataset).codigo).toBe("VIEW_AUSENTE");
  });

  it("dataset ausente levanta com código próprio, não tela em branco", async () => {
    readFileMock.mockImplementation(async () => {
      throw new Error("ENOENT");
    });
    const erro = await abrirDatasetSemCache().catch((e: unknown) => e);
    expect((erro as ErroDeDataset).codigo).toBe("DATASET_AUSENTE");
  });

  it("a sessão não expõe nenhuma porta para trocar de tag", async () => {
    montarDisco();
    const sessao = await abrirDatasetSemCache();
    // `lerView` recebe o NOME da view e nada mais: a tag não é parâmetro em lugar nenhum.
    expect(sessao.lerView.length).toBe(1);
    expect(Object.keys(sessao).sort()).toEqual(["lerView", "meta", "ponteiro", "tag", "temView"]);
  });

  it("view opcional ausente é recusada com motivo, sem derrubar as obrigatórias", async () => {
    montarDisco();
    const sessao = await abrirDatasetSemCache();
    expect(sessao.temView("internacional")).toBe(false);
    expect(sessao.temView("regimes_timeline")).toBe(false);
    const erro = await sessao.lerView("internacional").catch((e: unknown) => e);
    expect((erro as ErroDeDataset).codigo).toBe("VIEW_AUSENTE");
    await expect(sessao.lerView("catalogo")).resolves.toBeTruthy();
  });
});

describe("conferirView, isolada", () => {
  it("aceita o trio (hash, tag, dataset) correto", () => {
    const bruto = JSON.stringify({ view: "catalogo", tag: TAG, dataset_sha256: SHA });
    const meta = metaBase({
      views: [
        {
          arquivo: "catalogo.json",
          view: "catalogo",
          tela: "T-07",
          slot_arquitetura: "slot",
          bytes: bruto.length,
          sha256: sha(bruto),
          n_registros: 1,
        },
      ],
    });
    expect(() => conferirView("catalogo", bruto, JSON.parse(bruto), meta)).not.toThrow();
  });
});

describe("allowlist de caminho", () => {
  it("aceita o ponteiro, o meta, os tipos e as views declaradas", () => {
    expect(resolverCaminho(["current.json"])?.tipo).toBe("ponteiro");
    expect(resolverCaminho([TAG, "meta.json"])?.tipo).toBe("tag");
    expect(resolverCaminho([TAG, "schema.d.ts"])?.tipo).toBe("tag");
    for (const nome of NOMES_DE_VIEW) {
      expect(resolverCaminho([TAG, `${nome}.json`])?.tipo).toBe("tag");
    }
  });

  it("recusa travessia, caminho fora da lista e profundidade errada", () => {
    expect(resolverCaminho(["..", "package.json"])).toBeNull();
    expect(resolverCaminho([TAG, "..", "..", ".env"])).toBeNull();
    expect(resolverCaminho([TAG, "ldc.duckdb"])).toBeNull();
    expect(resolverCaminho([TAG, "internacional_pesos.json"])).toBeNull();
    expect(resolverCaminho([TAG])).toBeNull();
    expect(resolverCaminho([])).toBeNull();
    expect(resolverCaminho(["current.json", "x"])).toBeNull();
  });

  it("recusa tag com forma inválida", () => {
    expect(tagEhValida("comite-2026-10-14")).toBe(true);
    expect(tagEhValida("../etc")).toBe(false);
    expect(tagEhValida("Comite")).toBe(false);
    expect(tagEhValida("")).toBe(false);
  });
});
