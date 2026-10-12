/**
 * TELA 4 — Dados e limitações (T-07).
 *
 * É a tela que faz o resto do módulo ser auditável: catálogo das séries com cobertura DECLARADA e
 * OBSERVADA em colunas separadas (a divergência é informação, não erro de digitação), hash do
 * dataset, as limitações com o número medido, as decisões pendentes com o custo de discordar, o
 * status dos ADRs como está em disco e o que o gate cortou (RF-W033/RF-W034).
 *
 * Duas regras de desenho vindas do PRD: limitação **não** entra em acordeão fechado — conteúdo
 * que precisa ser lido não começa escondido; e `data_inicio` declarada nunca ocupa o lugar da
 * observada, nem o contrário.
 */

import type { Metadata } from "next";
import { StatCard } from "@/app/admin/wealth-planning/components/charts";

import { Moldura, MolduraDeErro, TELAS } from "../_components/Moldura";
import { SeletorDeLente, type CampoDeFiltro } from "../_components/SeletorDeLente";
import { abrirDataset, tentar } from "../_lib/dataset";
import { formatarInteiro, formatarNumero, hashCurto } from "../_lib/formato";
import type { CatalogoView } from "../_lib/schema";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alocação Macro · Dados e limitações — Admin LDC",
};

const TELA = TELAS[3];
const TODOS = "todos";

type Busca = { item?: string; status?: string; fonte?: string };

export default async function DadosPage({ searchParams }: { searchParams: Promise<Busca> }) {
  const aberta = await tentar(abrirDataset());
  if (!aberta.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Dados e limitações" erro={aberta.erro} />;
  }
  const sessao = aberta.valor;

  const lida = await tentar(sessao.lerView("catalogo"));
  if (!lida.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Dados e limitações" erro={lida.erro} />;
  }
  const view: CatalogoView = lida.valor;

  const busca = await searchParams;

  const itens = Array.from(
    new Set(view.series.map((s) => s.item_email).filter((i): i is string => !!i)),
  ).sort();
  const status = Array.from(new Set(view.series.map((s) => s.status))).sort();
  const fontes = Array.from(new Set(view.series.map((s) => s.fonte))).sort();

  const itemEscolhido = busca.item && itens.includes(busca.item) ? busca.item : TODOS;
  const statusEscolhido = busca.status && status.includes(busca.status) ? busca.status : TODOS;
  const fonteEscolhida = busca.fonte && fontes.includes(busca.fonte) ? busca.fonte : TODOS;

  const series = view.series.filter(
    (s) =>
      (itemEscolhido === TODOS || s.item_email === itemEscolhido) &&
      (statusEscolhido === TODOS || s.status === statusEscolhido) &&
      (fonteEscolhida === TODOS || s.fonte === fonteEscolhida),
  );

  const campos: CampoDeFiltro[] = [
    {
      chave: "item",
      rotulo: "Item do e-mail",
      valor: itemEscolhido,
      opcoes: [{ valor: TODOS, rotulo: "todos" }, ...itens.map((i) => ({ valor: i, rotulo: i }))],
    },
    {
      chave: "status",
      rotulo: "Status",
      valor: statusEscolhido,
      opcoes: [{ valor: TODOS, rotulo: "todos" }, ...status.map((s) => ({ valor: s, rotulo: s }))],
    },
    {
      chave: "fonte",
      rotulo: "Fonte",
      valor: fonteEscolhida,
      opcoes: [{ valor: TODOS, rotulo: "todas" }, ...fontes.map((f) => ({ valor: f, rotulo: f }))],
    },
  ];

  return (
    <Moldura
      atual={TELA.href}
      titulo="Dados e limitações"
      pergunta={view.pergunta}
      gate={view.gate}
      meta={sessao.meta}
      ponteiro={sessao.ponteiro}
      views={["catalogo"]}
    >
      {/* KPI como bloco de dado discreto, do kit da casa: rótulo uppercase + número tabular */}
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard
          label="Impressão digital do dataset"
          value={sessao.meta.dataset_sha256_curto || hashCurto(sessao.meta.dataset_sha256)}
          sub={`tag ${sessao.meta.tag}`}
        />
        <StatCard
          label="Artefatos do manifesto"
          value={formatarInteiro(sessao.meta.agregado.n_artefatos)}
          sub={
            view.artefatos_nao_publicaveis.length > 0
              ? `${formatarInteiro(view.artefatos_nao_publicaveis.length)} cortados pelo gate e ausentes de toda tela`
              : "todos publicáveis"
          }
        />
        <StatCard
          label="Séries no catálogo"
          value={formatarInteiro(view.cobertura.n_series)}
          sub={`${formatarInteiro(view.cobertura.n_presentes)} presentes · ${formatarInteiro(view.cobertura.n_cobrem_1t2006)} cobrem o primeiro trimestre da janela`}
        />
      </div>

      <section aria-labelledby="catalogo" className="mt-6">
        <h2 id="catalogo" className="text-base font-bold text-gray-900">
          Catálogo das séries
        </h2>
        <p className="mt-1 mb-3 text-sm text-gray-900">
          Início declarado pela fonte e início observado no dado vêm em colunas separadas. Quando
          divergem, a divergência é a informação: é ela que diz quanto da janela a série sustenta.
        </p>
        <SeletorDeLente campos={campos} />
        <p className="mb-2 text-xs text-gray-600">
          {formatarInteiro(series.length)} de {formatarInteiro(view.series.length)} séries neste
          recorte.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">
              Séries do dataset, com fonte, cobertura declarada, cobertura observada, frequência,
              unidade e status
            </caption>
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-[0.08em] text-gray-600">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Série
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Item
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Fonte
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Início declarado
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Início observado
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Frequência
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Unidade
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Status
                </th>
                <th scope="col" className="py-2 pr-3 text-right font-semibold">
                  Observações
                </th>
                <th scope="col" className="py-2 text-right font-semibold">
                  Defasagem (dias)
                </th>
              </tr>
            </thead>
            <tbody>
              {series.map((s) => {
                const divergem =
                  s.data_inicio !== null &&
                  s.data_inicio_observada !== null &&
                  s.data_inicio !== s.data_inicio_observada;
                return (
                  <tr key={s.series_id} className="ldc-linha border-b">
                    <th scope="row" className="py-2 pr-3 text-left font-medium text-gray-900">
                      {s.series_id}
                      <span className="ml-2 block text-xs font-normal text-gray-600">{s.nome}</span>
                    </th>
                    <td className="py-2 pr-3 text-gray-700">{s.item_email ?? "–"}</td>
                    <td className="py-2 pr-3 text-gray-700">
                      {s.fonte_url ? (
                        <a
                          className="underline decoration-gray-300 underline-offset-2"
                          href={s.fonte_url}
                          rel="noreferrer noopener"
                          target="_blank"
                        >
                          {s.fonte}
                        </a>
                      ) : (
                        s.fonte
                      )}
                    </td>
                    <td className="ldc-num py-2 pr-3 text-gray-900">
                      {s.data_inicio ?? "não declarado"}
                    </td>
                    <td
                      className={`ldc-num py-2 pr-3 ${divergem ? "ldc-alerta font-semibold" : "text-gray-900"}`}
                    >
                      {s.data_inicio_observada ??
                        (s.presente_no_processed ? "não observado" : "série não chegou")}
                    </td>
                    <td className="py-2 pr-3 text-gray-700">{s.freq}</td>
                    <td className="py-2 pr-3 text-gray-700">{s.unit}</td>
                    <td className="py-2 pr-3 text-gray-700">
                      {s.status}
                      <span className="ml-1 text-xs text-gray-600">({s.confianca})</span>
                    </td>
                    <td className="ldc-num py-2 pr-3 text-gray-900">
                      {formatarInteiro(s.n_obs)}
                      {s.pct_nulos !== null ? (
                        <span className="ml-1 text-xs text-gray-600">
                          {formatarNumero(s.pct_nulos, 2)}% nulos
                        </span>
                      ) : null}
                    </td>
                    <td className="ldc-num py-2 text-gray-900">
                      {formatarInteiro(s.lag_divulgacao_dias)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="limitacoes" className="mt-8">
        <h2 id="limitacoes" className="text-base font-bold text-gray-900">
          As {formatarInteiro(view.limitacoes.length)} limitações, cada uma com o número medido
        </h2>
        <ol className="mt-2 space-y-2">
          {view.limitacoes
            .slice()
            .sort((a, b) => a.numero - b.numero)
            .map((l) => (
              <li key={l.numero} className="border-b pb-2 text-sm leading-relaxed text-gray-900">
                <span className="font-semibold">{formatarInteiro(l.numero)}.</span> {l.texto}
              </li>
            ))}
        </ol>
      </section>

      <section aria-labelledby="decisoes" className="mt-8">
        <h2 id="decisoes" className="text-base font-bold text-gray-900">
          As {formatarInteiro(view.decisoes_pendentes.length)} decisões pendentes, com o custo de
          discordar
        </h2>
        <p className="mt-1 mb-3 text-sm text-gray-900">
          Nenhuma resposta aqui veio de uma pessoa: todas são a recomendação da pesquisa, aplicada
          como padrão provisório para que a estrutura pudesse ser construída. Virar qualquer uma é
          legítimo e previsto.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-[0.08em] text-gray-600">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Nº
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Decisão
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Padrão provisório
                </th>
                <th scope="col" className="py-2 font-semibold">
                  Se o Comitê discordar
                </th>
              </tr>
            </thead>
            <tbody>
              {view.decisoes_pendentes.map((d) => (
                <tr key={d.id} className="ldc-linha border-b align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-medium text-gray-900">
                    {d.id}
                  </th>
                  <td className="py-2 pr-3 text-gray-900">{d.decisao}</td>
                  <td className="py-2 pr-3 text-gray-700">{d.padrao_provisorio}</td>
                  <td className="py-2 text-gray-700">{d.se_discordar}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="adrs" className="mt-8">
        <h2 id="adrs" className="text-base font-bold text-gray-900">
          Status dos ADRs, como está em disco
        </h2>
        <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
          {view.adrs.map((a) => (
            <li key={a.id} className="ldc-linha flex items-center justify-between gap-3 border-b py-1">
              <span className="text-gray-900">
                {a.id}
                <span className="ml-2 text-xs text-gray-600">{a.arquivo}</span>
              </span>
              <span
                className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold ${
                  a.status.toUpperCase().startsWith("ACEIT") ? "ldc-sup-lime" : "ldc-sup-alerta"
                }`}
              >
                {a.status}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="artefatos" className="mt-8">
        <h2 id="artefatos" className="text-base font-bold text-gray-900">
          Artefatos publicados
        </h2>
        <p className="mt-1 mb-2 text-sm text-gray-900">
          O que está marcado como não publicável não tem view: o corte é do exportador, não da tela.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-[0.08em] text-gray-600">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Arquivo
                </th>
                <th scope="col" className="py-2 pr-3 text-right font-semibold">
                  Linhas
                </th>
                <th scope="col" className="py-2 pr-3 text-right font-semibold">
                  Colunas
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Janela
                </th>
                <th scope="col" className="py-2 pr-3 text-right font-semibold">
                  Nulos
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Determinístico
                </th>
                <th scope="col" className="py-2 font-semibold">
                  Impressão digital
                </th>
              </tr>
            </thead>
            <tbody>
              {view.artefatos.map((a) => (
                <tr key={a.arquivo} className="ldc-linha border-b">
                  <th scope="row" className="py-2 pr-3 text-left font-medium text-gray-900">
                    {a.arquivo}
                  </th>
                  <td className="ldc-num py-2 pr-3 text-gray-900">{formatarInteiro(a.linhas)}</td>
                  <td className="ldc-num py-2 pr-3 text-gray-900">{formatarInteiro(a.colunas)}</td>
                  <td className="py-2 pr-3 text-gray-700">
                    {a.date_min ?? "–"} a {a.date_max ?? "–"}
                  </td>
                  <td className="ldc-num py-2 pr-3 text-gray-700">
                    {a.pct_nulos === null ? "–" : `${formatarNumero(a.pct_nulos, 2)}%`}
                  </td>
                  <td className="py-2 pr-3 text-gray-700">{a.determinista ? "sim" : "não"}</td>
                  <td className="ldc-num py-2 text-gray-700" title={a.sha256 ?? undefined}>
                    {hashCurto(a.sha256)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {view.artefatos_nao_publicaveis.length > 0 && (
          <div className="ldc-sup-alerta mt-3 rounded-xl p-3 text-sm">
            <p className="font-semibold">Cortado pelo gate, e por isso ausente de toda tela</p>
            <ul className="mt-1 space-y-0.5 text-xs text-gray-900">
              {view.artefatos_nao_publicaveis.map((o) => (
                <li key={o.artefato}>
                  {o.artefato}: {o.motivo}
                </li>
              ))}
            </ul>
          </div>
        )}

        {view.reducoes.length > 0 && (
          <div className="mt-3 rounded-xl border p-3 text-sm">
            <p className="font-semibold text-gray-900">Reduções declaradas nesta tag</p>
            <ul className="mt-1 space-y-0.5 text-xs text-gray-700">
              {view.reducoes.map((r, i) => (
                <li key={i}>
                  {r.o_que}
                  {r.artefato ? ` (${r.artefato})` : ""}: {r.por_que}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <p className="ldc-info mt-6 text-xs">Fontes desta view: {view.fontes.join(" · ")}.</p>
    </Moldura>
  );
}
