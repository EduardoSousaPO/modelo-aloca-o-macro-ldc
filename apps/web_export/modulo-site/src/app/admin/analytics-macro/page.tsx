/**
 * TELA 1 — Visão geral: "Em que regime estamos?"
 *
 * A tela responde a pergunta TRÊS VEZES e não escolhe nenhuma (RF-W019, F-024 §2). A escolha da
 * lente oficial é a decisão D1, do Edu e do Comitê, e não deste módulo — então as três respostas
 * saem com o mesmo peso visual, na ordem em que o exportador as publicou, e o fallback nunca é
 * chamado de "o regime atual": a resposta diz de qual trimestre é o rótulo.
 *
 * Server Component: lê a view do disco pelo loader, com a tag FIXADA na requisição. Esta tela não
 * tem filtro — o PRD diz, com razão, que ela é idêntica para todos —, então não há nada a
 * hidratar além do que o `AdminLayout` já traz.
 *
 * `force-dynamic`: a faixa do gate e o ponteiro `current.json` não podem ser servidos do cache de
 * rota. O cache vive onde é seguro: no memo por hash do loader e no `Cache-Control` imutável da
 * API.
 */

import type { Metadata } from "next";

import { Moldura, MolduraDeErro, TELAS } from "./_components/Moldura";
import { TabelaRanking } from "./_components/TabelaRanking";
import { abrirDataset, tentar } from "./_lib/dataset";
import {
  apresentarCom,
  extremoSimetrico,
  formatarInteiro,
  formatarNumero,
  notaDeUnidade,
  valorApresentado,
} from "./_lib/formato";
import type { LinhaDeRanking, MetaWeb, RankingAtualView, RespostaDeRegimeWeb } from "./_lib/schema";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alocação Macro · Em que regime estamos — Admin LDC",
};

const TELA = TELAS[0];

function Resposta({
  resposta,
  rankings,
  meta,
  extremo,
  limiares,
}: {
  resposta: RespostaDeRegimeWeb;
  rankings: readonly LinhaDeRanking[];
  meta: MetaWeb;
  extremo: number;
  limiares?: { alerta_abaixo_de: number; supressao_abaixo_de: number };
}) {
  const top5 = rankings
    .filter((l) => l.lente === resposta.lente && l.regime === resposta.regime)
    .slice()
    .sort((a, b) => a.posicao - b.posicao)
    .slice(0, 5);

  return (
    <div className="px-4 py-4 first:pl-0 last:pr-0">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gray-600">
        {resposta.lente_rotulo}
      </p>
      <p className="mt-1 text-xs leading-snug text-gray-600">{resposta.lente_titulo}</p>

      <p className="mt-2 text-xl font-bold leading-tight text-gray-900">
        {resposta.regime ?? resposta.status_regime_v1 ?? "sem rótulo declarado"}
      </p>
      <p className="text-xs text-gray-600">
        pergunta sobre {resposta.quarter_perguntado} · célula de {resposta.quarter_da_celula} ·{" "}
        {resposta.materializacao} · horizonte {resposta.horizonte} · n ={" "}
        {formatarInteiro(resposta.n_obs)}
      </p>

      {resposta.status_regime_v1 && resposta.regime !== resposta.status_regime_v1 && (
        <p className="mt-1.5 text-xs text-gray-900">
          Status do trimestre perguntado: {resposta.status_regime_v1}.
        </p>
      )}

      {resposta.motivo_indeterminado && (
        <p className="mt-1 text-xs text-gray-900">
          Motivo declarado: {resposta.motivo_indeterminado}. Nenhum quadrante foi estimado no lugar.
        </p>
      )}

      {resposta.e_fallback && (
        <p className="ldc-sup-alerta mt-2 rounded-lg px-2 py-1.5 text-xs">
          O rótulo é de {resposta.quarter_da_celula}, usado como referência declarada. Não é o
          regime do trimestre perguntado.
        </p>
      )}

      {(resposta.conclusao_suprimida || resposta.alerta_n_baixo) && (
        <p className="mt-2 text-xs text-gray-900">
          {resposta.conclusao_suprimida
            ? "Observações abaixo do limiar de supressão: esta lente sai sem conclusão."
            : "Observações abaixo do limiar de alerta: leia o erro-padrão antes da ordem."}
        </p>
      )}

      <div className="mt-3">
        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.08em] text-gray-600">
          As cinco primeiras linhas desta lente
        </p>
        <TabelaRanking
          linhas={top5}
          meta={meta}
          extremo={extremo}
          limiares={limiares}
          compacta
          legenda={false}
        />
      </div>

      <p className="mt-2 text-xs text-gray-600">Tabela de origem: {resposta.tabela_de_origem}.</p>
    </div>
  );
}

export default async function VisaoGeralPage() {
  const aberta = await tentar(abrirDataset());
  if (!aberta.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Em que regime estamos" erro={aberta.erro} />;
  }
  const sessao = aberta.valor;

  const lida = await tentar(sessao.lerView("ranking_atual"));
  if (!lida.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Em que regime estamos" erro={lida.erro} />;
  }
  const view: RankingAtualView = lida.valor;

  // Os limiares de `n` são do dado, e vivem na view do heatmap. Quando ela não está na tag, a
  // legenda sai sem os números em vez de inventá-los.
  const heatmap = sessao.temView("heatmap_regime_ativo")
    ? await tentar(sessao.lerView("heatmap_regime_ativo"))
    : null;
  const limiares = heatmap?.ok ? heatmap.valor.limiares_de_n : undefined;
  // O rodapé declara toda view lida, inclusive esta: procedência parcial é procedência errada.
  const viewsLidas = limiares
    ? (["ranking_atual", "heatmap_regime_ativo"] as const)
    : (["ranking_atual"] as const);

  const extremo = extremoSimetrico(
    view.rankings.map((l) =>
      l.excesso_cdi === null ? null : valorApresentado(sessao.meta, "excesso_cdi", l.excesso_cdi),
    ),
  );

  const secoes = Array.from(new Set(view.concordancia.map((l) => l.secao)));

  return (
    <Moldura
      atual={TELA.href}
      titulo="Em que regime estamos"
      pergunta={view.pergunta}
      gate={view.gate}
      meta={sessao.meta}
      ponteiro={sessao.ponteiro}
      views={viewsLidas}
    >
      {/* as três respostas, lado a lado, em UM painel com colunas divididas: três cards
          idênticos é padrão banido no DESIGN.md, e a divisão por régua diz a mesma coisa */}
      <section aria-labelledby="tres-respostas" className="rounded-xl border bg-white">
        <h2 id="tres-respostas" className="sr-only">
          As três respostas sobre {view.quarter_perguntado}
        </h2>
        <div className="grid divide-y lg:grid-cols-3 lg:divide-x lg:divide-y-0">
          {view.respostas.map((r) => (
            <Resposta
              key={`${r.lente}-${r.quarter_da_celula}`}
              resposta={r}
              rankings={view.rankings}
              meta={sessao.meta}
              extremo={extremo}
              limiares={limiares}
            />
          ))}
        </div>
      </section>

      <p className="mt-2 text-xs text-gray-600">
        Nenhuma das três foi escolhida: qual abre a página é decisão do Comitê (D1), não deste
        módulo. A ordem aqui é a declarada pelo exportador e não sugere escolha.
      </p>

      <section aria-labelledby="intersecao" className="mt-6">
        <h2 id="intersecao" className="text-base font-bold text-gray-900">
          Interseção dos cinco primeiros das três lentes
        </h2>
        <p className="mt-1 text-sm text-gray-900">
          {view.intersecao_dos_top5.length === 0 ? (
            <>
              A interseção é <strong>vazia</strong>: nenhum ativo aparece entre os cinco primeiros
              das três lentes ao mesmo tempo. Isso é o resultado, não um defeito do cálculo.
            </>
          ) : (
            <>Em comum nas três lentes: {view.intersecao_dos_top5.join(", ")}.</>
          )}
        </p>
        <ul className="mt-2 space-y-1 text-sm text-gray-900">
          {Object.entries(view.top5_por_lente).map(([lente, ativos]) => (
            <li key={lente}>
              <span className="font-semibold">{lente}:</span> {ativos.join(", ") || "sem linhas"}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="concordancia" className="mt-6">
        <h2 id="concordancia" className="text-base font-bold text-gray-900">
          Concordância entre as lentes
        </h2>
        <p className="mt-1 mb-2 text-sm text-gray-900">
          Jaccard, Spearman e a distribuição nas referências do histórico — e não só o número do
          trimestre corrente: afirmar concordância olhando um trimestre só é escolher a evidência
          depois de ver o resultado.
        </p>
        {secoes.map((secao) => (
          <div key={secao} className="mt-3">
            <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-gray-600">
              {secao}
            </h3>
            <table className="mt-1 w-full border-collapse text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-[0.08em] text-gray-600">
                  <th scope="col" className="py-1.5 pr-3 font-semibold">
                    Chave
                  </th>
                  <th scope="col" className="py-1.5 pr-3 font-semibold">
                    Métrica
                  </th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-semibold">
                    Valor
                  </th>
                  <th scope="col" className="py-1.5 font-semibold">
                    Leitura
                  </th>
                </tr>
              </thead>
              <tbody>
                {view.concordancia
                  .filter((l) => l.secao === secao)
                  .map((l, i) => (
                    <tr key={`${secao}-${l.chave}-${l.metrica}-${i}`} className="ldc-linha border-b">
                      <th scope="row" className="py-1.5 pr-3 text-left font-medium text-gray-900">
                        {l.chave}
                      </th>
                      <td className="py-1.5 pr-3 text-gray-700">{l.metrica}</td>
                      <td className="ldc-num py-1.5 pr-3 text-gray-900">
                        {l.valor_num === null ? "–" : formatarNumero(l.valor_num, 3)}
                      </td>
                      <td className="py-1.5 text-gray-700">{l.valor_texto ?? ""}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ))}
      </section>

      <section aria-labelledby="vizinhos" className="mt-6">
        <h2 id="vizinhos" className="text-base font-bold text-gray-900">
          Os {formatarInteiro(view.n_vizinhos)} trimestres mais parecidos com{" "}
          {view.quarter_perguntado}
        </h2>
        <table className="mt-2 w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left text-xs uppercase tracking-[0.08em] text-gray-600">
              <th scope="col" className="py-2 pr-3 font-semibold">
                Ordem
              </th>
              <th scope="col" className="py-2 pr-3 font-semibold">
                Trimestre
              </th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold">
                Distância
              </th>
              <th scope="col" className="py-2 pr-3 font-semibold">
                Quadrante da V1
              </th>
              <th scope="col" className="py-2 font-semibold">
                Trimestre seguinte
              </th>
            </tr>
          </thead>
          <tbody>
            {view.vizinhos_do_quarter.map((v) => (
              <tr key={`${v.rank}-${v.quarter_neighbor}`} className="ldc-linha border-b">
                <td className="ldc-num py-2 pr-3 text-gray-700">{formatarInteiro(v.rank)}</td>
                <th scope="row" className="py-2 pr-3 text-left font-medium text-gray-900">
                  {v.quarter_neighbor}
                </th>
                <td className="ldc-num py-2 pr-3 text-gray-900">
                  {apresentarCom(sessao.meta, "distancia", v.distancia)}
                </td>
                <td className="py-2 pr-3 text-gray-900">
                  {v.regime_v1_neighbor ?? (
                    <span className="text-gray-700">
                      sem quadrante
                      {v.status_regime_v1_neighbor ? `: ${v.status_regime_v1_neighbor}` : ""}
                    </span>
                  )}
                </td>
                <td className="py-2 text-gray-900">
                  {v.quarter_t_mais_1 ?? "não existe na janela"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-gray-600">
          A leitura em T+1 destes vizinhos, com observações e barra de erro, está na tela Momentos
          semelhantes.
        </p>
      </section>

      <p className="ldc-info mt-6 text-xs">
        Unidades: {notaDeUnidade(sessao.meta, ["excesso_cdi", "erro_padrao_media", "distancia"])}.
        Fontes desta view: {view.fontes.join(" · ")}.
      </p>
    </Moldura>
  );
}
