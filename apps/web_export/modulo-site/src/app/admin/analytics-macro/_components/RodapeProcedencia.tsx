/**
 * O rodapé de procedência — em TODA tela (RF-W001, RF-W050).
 *
 * Imprime o MESMO `DATASET_SHA256` que o `HASHES.txt` do pacote do Comitê, para caderno e portal
 * não divergirem (`arquitetura` §7.7), mais a tag, a janela do dado, o nº de artefatos, o
 * `versao_build` do exportador, o `sha256` de cada view que ESTA tela leu, as reduções declaradas
 * e os artefatos que o gate cortou.
 *
 * E dá o link da API para cada view lida: clicar abre exatamente o JSON que a tela desenhou,
 * atrás do mesmo `checkAdminAuth()`. É o que torna a tela conferível sem pedir nada a ninguém.
 *
 * É `.ldc-info` (slate): informação, não alerta. Sem `<details>` fechado — procedência em
 * acordeão é procedência que ninguém lê.
 */

import { formatarInteiro, hashCurto } from "../_lib/formato";
import { urlDoArquivo, type NomeDeView } from "../_lib/dataset";
import type { MetaWeb, PonteiroCurrent } from "../_lib/schema";

export function RodapeProcedencia({
  meta,
  ponteiro,
  views,
}: {
  meta: MetaWeb;
  ponteiro: PonteiroCurrent;
  /** Nomes das views que ESTA tela leu — a procedência é da tela, não do módulo. */
  views: readonly NomeDeView[];
}) {
  const lidas = meta.views.filter((v) => (views as readonly string[]).includes(v.view));
  const dd = meta.data_do_dado;
  return (
    <footer className="ldc-info mt-8 border-t pt-4 text-xs leading-relaxed">
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="inline font-semibold uppercase tracking-[0.08em]">Dataset</dt>{" "}
          <dd className="inline" title={meta.dataset_sha256}>
            {meta.dataset_sha256_curto || hashCurto(meta.dataset_sha256)}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold uppercase tracking-[0.08em]">Tag</dt>{" "}
          <dd className="inline">{meta.tag}</dd>
        </div>
        <div>
          <dt className="inline font-semibold uppercase tracking-[0.08em]">Janela do dado</dt>{" "}
          <dd className="inline">
            {dd.primeiro_trimestre_macro ?? "–"} a {dd.ultimo_trimestre_macro ?? "–"}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold uppercase tracking-[0.08em]">Safra</dt>{" "}
          <dd className="inline">{dd.vintage_max ?? "não declarada"}</dd>
        </div>
        <div>
          <dt className="inline font-semibold uppercase tracking-[0.08em]">Artefatos</dt>{" "}
          <dd className="inline">
            {formatarInteiro(meta.agregado.n_artefatos)}
            {meta.agregado.n_artefatos_fora_do_agregado > 0
              ? ` (${formatarInteiro(meta.agregado.n_artefatos_fora_do_agregado)} fora do agregado)`
              : ""}
          </dd>
        </div>
        <div>
          <dt className="inline font-semibold uppercase tracking-[0.08em]">Exportador</dt>{" "}
          <dd className="inline" title={meta.web_export_versao_build}>
            {hashCurto(meta.web_export_versao_build)} · schema v
            {formatarInteiro(meta.schema_versao)}
          </dd>
        </div>
      </dl>

      <p className="mt-2">
        Views lidas por esta tela:{" "}
        {lidas.length === 0
          ? "nenhuma"
          : lidas.map((v) => `${v.view} (${v.tela})`).join(" · ")}
        .{" "}
        {lidas.map((v) => (
          <span key={v.view}>
            <a
              className="underline decoration-gray-300 underline-offset-2"
              href={urlDoArquivo(meta.tag, v.arquivo)}
              rel="noreferrer noopener"
              target="_blank"
              title={`${v.sha256} · ${formatarInteiro(v.bytes)} bytes · ${formatarInteiro(v.n_registros)} registros`}
            >
              conferir {v.arquivo} ({hashCurto(v.sha256)})
            </a>{" "}
          </span>
        ))}
      </p>

      <p className="mt-2">
        Ponteiro: {ponteiro.tag}, com {Object.keys(ponteiro.arquivos ?? {}).length} arquivos
        declarados e política {ponteiro.cache_control} para ele e {ponteiro.cache_control_da_tag}{" "}
        para a tag. A tag é fixada por requisição: nenhuma tela mistura duas tags, e o hash de cada
        view é conferido contra o meta antes de desenhar.
      </p>

      <p className="mt-2">
        Congelamento: {meta.congelamento.dataset_congelado ? "sim" : "não"}
        {meta.congelamento.tag ? `, tag ${meta.congelamento.tag}` : ""}
        {meta.congelamento.git_commit ? `, commit ${hashCurto(meta.congelamento.git_commit)}` : ""}.
        Reconstruível com um comando: <code>python -m apps.pipeline run --offline</code> reconstrói
        o dataset sem rede a partir do bruto arquivado, e{" "}
        <code>python -m apps.pipeline verify</code> recalcula a impressão digital de todos os
        arquivos publicados e sai com erro se um byte divergir. Hash diferente é outro dataset:
        números de rodadas diferentes não se comparam.
      </p>

      {meta.artefatos_nao_publicaveis.length > 0 && (
        <p className="mt-2">
          Cortado pelo gate, e por isso ausente de toda tela:{" "}
          {meta.artefatos_nao_publicaveis.join(" · ")}.
        </p>
      )}

      {meta.reducoes.length > 0 && (
        <p className="mt-2">
          Reduções declaradas nesta tag:{" "}
          {meta.reducoes.map((r) => `${r.o_que} (${r.por_que})`).join(" · ")}.
        </p>
      )}

      <p className="mt-2">
        Orçamento do conjunto: {formatarInteiro(meta.orcamento.bytes_das_views)} de{" "}
        {formatarInteiro(meta.orcamento.limite_bytes)} bytes em{" "}
        {formatarInteiro(meta.orcamento.arquivos_contados)} arquivos.
      </p>
    </footer>
  );
}
