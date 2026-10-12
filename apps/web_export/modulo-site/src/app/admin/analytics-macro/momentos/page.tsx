/**
 * TELA 3 — Momentos semelhantes.
 *
 * Responde "quais trimestres se parecem com este, e o que rendeu no trimestre SEGUINTE a cada um"
 * (RF-W025 a RF-W028). Server Component: cada combinação de referência e `k` é um grupo já
 * calculado pelo exportador, escolhido por chave. O front não calcula distância, não padroniza
 * vetor e não refaz ranking — ele seleciona.
 *
 * DUAS ADAPTAÇÕES AO CONTRATO REAL DO EXPORTADOR, declaradas na tela em vez de escondidas:
 *
 * 1. **Mahalanobis × Euclidiana e somente-passado não são controles.** A tag publica UMA lente,
 *    descrita campo a campo em `lente` (métrica, janela de padronização, shrinkage, se é somente
 *    passado, se é restrita ao pós-2016). Os seletores aparecem com o valor publicado e
 *    **desabilitados, com o motivo** — porque inventar a alternativa no front seria recalcular
 *    metodologia no cliente, que é justamente o que RF-W016 proíbe. Querer a alternativa é pedir
 *    outra lente ao exportador, e o pedido está no relatório.
 * 2. **O ranking em T+1 existe para o trimestre do Comitê.** É o que a view publica
 *    (`ranking_t_mais_1` + `quarter_do_comite`). Escolher outra referência mostra os vizinhos
 *    dela e diz, nomeando, que a leitura em T+1 daquela referência não está nesta tag.
 *
 * Três declarações ficam NA TELA, não no rodapé, porque mudam o que a lista significa: quantas
 * features rodam, o que `somente_passado` não elimina (safra) e quais vizinhos não têm quadrante.
 * Elas vêm do campo `declaracoes` da própria view.
 */

import type { Metadata } from "next";

import { Moldura, MolduraDeErro, TELAS } from "../_components/Moldura";
import { SeletorDeLente, type CampoDeFiltro } from "../_components/SeletorDeLente";
import { TabelaRanking } from "../_components/TabelaRanking";
import { abrirDataset, tentar } from "../_lib/dataset";
import {
  apresentarCom,
  extremoSimetrico,
  formatarInteiro,
  notaDeUnidade,
  valorApresentado,
} from "../_lib/formato";
import type { VizinhosView } from "../_lib/schema";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alocação Macro · Momentos semelhantes — Admin LDC",
};

const TELA = TELAS[2];

type Busca = { ref?: string; k?: string };

export default async function MomentosPage({ searchParams }: { searchParams: Promise<Busca> }) {
  const aberta = await tentar(abrirDataset());
  if (!aberta.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Momentos semelhantes" erro={aberta.erro} />;
  }
  const sessao = aberta.valor;

  const lida = await tentar(sessao.lerView("vizinhos"));
  if (!lida.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Momentos semelhantes" erro={lida.erro} />;
  }
  const view: VizinhosView = lida.valor;

  const busca = await searchParams;

  const ref =
    busca.ref && view.referencias.includes(busca.ref) ? busca.ref : view.quarter_do_comite;
  const k = view.ks.includes(Number(busca.k)) ? Number(busca.k) : (view.k_completo ?? view.ks[0]);

  const grupo = view.rankings.find((r) => r.quarter_ref === ref && r.k_usado === k) ?? null;

  const limiares = sessao.temView("heatmap_regime_ativo")
    ? await tentar(sessao.lerView("heatmap_regime_ativo"))
    : null;
  // O rodapé declara toda view lida, inclusive a que entrou só pelos limiares de `n`.
  const viewsLidas = limiares?.ok
    ? (["vizinhos", "heatmap_regime_ativo"] as const)
    : (["vizinhos"] as const);

  const extremo = extremoSimetrico(
    view.ranking_t_mais_1.map((l) =>
      l.excesso_cdi === null ? null : valorApresentado(sessao.meta, "excesso_cdi", l.excesso_cdi),
    ),
  );

  const campos: CampoDeFiltro[] = [
    {
      chave: "ref",
      rotulo: "Trimestre de referência",
      valor: ref,
      nota: `${formatarInteiro(view.referencias.length)} com vetor completo`,
      opcoes: view.referencias.map((q) => ({
        valor: q,
        rotulo: q === view.quarter_do_comite ? `${q} (trimestre do Comitê)` : q,
      })),
    },
    {
      chave: "k",
      rotulo: "Vizinhos (k)",
      valor: String(k),
      nota: view.regra_de_truncamento,
      opcoes: view.ks.map((n) => ({ valor: String(n), rotulo: String(n) })),
    },
    {
      chave: "metrica_declarada",
      rotulo: "Distância",
      valor: view.lente.metrica,
      nota: "publicada, não selecionável",
      opcoes: [
        { valor: view.lente.metrica, rotulo: view.lente.metrica },
        {
          valor: "outra",
          rotulo: "outra métrica",
          desabilitada: true,
          motivo: "a tag publica uma lente só; a alternativa é pedido ao exportador",
        },
      ],
    },
    {
      chave: "janela_declarada",
      rotulo: "Janela e padronização",
      valor: view.lente.janela_padronizacao,
      nota: view.lente.somente_passado ? "somente passado" : "descritiva",
      opcoes: [
        { valor: view.lente.janela_padronizacao, rotulo: view.lente.janela_padronizacao },
        {
          valor: "outra",
          rotulo: "outra janela",
          desabilitada: true,
          motivo: "mudar a janela é recalcular metodologia, e isso não acontece no cliente",
        },
      ],
    },
  ];

  return (
    <Moldura
      atual={TELA.href}
      titulo="Momentos semelhantes"
      pergunta={view.pergunta}
      gate={view.gate}
      meta={sessao.meta}
      ponteiro={sessao.ponteiro}
      views={viewsLidas}
    >
      <SeletorDeLente campos={campos} />

      <section aria-labelledby="declaracoes" className="mb-5">
        <h2 id="declaracoes" className="sr-only">
          O que esta lente usa e o que ela não elimina
        </h2>
        <ul className="space-y-1 text-sm text-gray-900">
          {view.declaracoes.map((d, i) => (
            <li key={i}>{d}</li>
          ))}
          <li>
            Lente publicada: {view.lente.metrica}, {formatarInteiro(view.lente.n_features)} features
            ({view.lente.features_usadas}), padronização {view.lente.janela_padronizacao}
            {view.lente.shrinkage ? `, shrinkage ${view.lente.shrinkage}` : ""},
            {view.lente.somente_passado ? " somente passado" : " descritiva"},
            {view.lente.restrito_pos_2016 ? " restrita ao pós-2016" : " janela cheia"}.
          </li>
        </ul>
      </section>

      {!grupo ? (
        <p className="ldc-sup-alerta rounded-xl p-4 text-sm">
          A tag {sessao.tag} não traz a referência {ref} com k = {formatarInteiro(k)}. O exportador
          publica {formatarInteiro(view.rankings.length)} combinações; mude um dos controles acima.
        </p>
      ) : (
        <section aria-labelledby="vizinhos" className="mt-2">
          <h2 id="vizinhos" className="text-base font-bold text-gray-900">
            Os {formatarInteiro(grupo.n_vizinhos)} trimestres mais parecidos com {grupo.quarter_ref}
          </h2>
          <table className="mt-2 w-full border-collapse text-sm">
            <caption className="sr-only">
              Vizinhos com distância, quadrante da V1 e o trimestre seguinte
            </caption>
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
              {grupo.vizinhos
                .slice()
                .sort((a, b) => a.rank - b.rank)
                .map((v) => {
                  const quadrante = view.quadrante_por_quarter[v.quarter_neighbor];
                  const seguinte = view.t_mais_1_por_quarter[v.quarter_neighbor];
                  return (
                    <tr key={`${v.rank}-${v.quarter_neighbor}`} className="ldc-linha border-b">
                      <td className="ldc-num py-2 pr-3 text-gray-700">{formatarInteiro(v.rank)}</td>
                      <th scope="row" className="py-2 pr-3 text-left font-medium text-gray-900">
                        {v.quarter_neighbor}
                      </th>
                      <td className="ldc-num py-2 pr-3 text-gray-900">
                        {apresentarCom(sessao.meta, "distancia", v.distancia)}
                      </td>
                      <td className="py-2 pr-3 text-gray-900">
                        {quadrante?.regime_v1 ?? (
                          <span className="text-gray-700">
                            sem quadrante
                            {quadrante?.status_regime_v1 ? `: ${quadrante.status_regime_v1}` : ""}
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-gray-900">{seguinte ?? "não existe na janela"}</td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-gray-600">
            Vizinho sem quadrante da V1 não é defeito da lista: é trimestre que a V1 não classifica,
            e o motivo aparece na própria linha.
          </p>
        </section>
      )}

      <section aria-labelledby="ranking-t1" className="mt-6">
        <h2 id="ranking-t1" className="text-base font-bold text-gray-900">
          O que rendeu nos trimestres seguintes a esses momentos
        </h2>
        {ref !== view.quarter_do_comite ? (
          <p className="ldc-sup-alerta mt-2 rounded-xl p-4 text-sm">
            A leitura em T+1 que esta tag publica é a do trimestre do Comitê (
            {view.quarter_do_comite}). Para {ref}, a lista de vizinhos acima está completa, e o
            ranking em T+1 não está nesta tag: pedir essa referência é pedir uma view ao
            exportador, não um cálculo na tela.
          </p>
        ) : (
          <>
            <p className="mt-1 mb-2 text-sm text-gray-900">
              Excesso sobre o CDI medido em T+1, com observações e barra de erro em toda linha.
              Quando o intervalo de dois erros-padrão cruza o zero, a linha não se distingue do CDI
              nesta janela, e a ordem entre linhas da mesma faixa não é distinguível de ruído.
            </p>
            <TabelaRanking
              linhas={view.ranking_t_mais_1}
              meta={sessao.meta}
              extremo={extremo}
              limiares={limiares?.ok ? limiares.valor.limiares_de_n : undefined}
            />
          </>
        )}
      </section>

      <p className="ldc-info mt-6 text-xs">
        Unidades: {notaDeUnidade(sessao.meta, ["excesso_cdi", "erro_padrao_media", "distancia"])}.
        Fontes desta view: {view.fontes.join(" · ")}.
      </p>
    </Moldura>
  );
}
