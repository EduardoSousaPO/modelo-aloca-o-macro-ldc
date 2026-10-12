/**
 * TELA 2 — Heatmap regime × ativo.
 *
 * Server Component que faz o recorte e passa dado pronto; a interação (hover com erro-padrão,
 * clique no detalhe do par) é o único pedaço de cliente, em `_components/Heatmap.tsx`. Os filtros
 * também são de cliente, mas guardam estado na URL, não em `useState` — então o recorte é
 * reproduzível por link (RF-W003/RF-W022) e quem filtra é o servidor.
 *
 * UMA ADAPTAÇÃO AO CONTRATO REAL DO EXPORTADOR, que vale explicar: materialização e horizonte
 * **não são eixos independentes**. Quem os determina é a `vista` (`v1_revised`, `v1_asof`,
 * `horizonte_cruzado`), que é a unidade de consistência do exportador — dentro de uma vista a V1
 * pode estar em T0 e a V3 em T+1, e cruzar eixos entre vistas produziria uma coluna que o dataset
 * não publicou. Então a vista é o seletor, e materialização e horizonte aparecem **declarados**
 * para a vista escolhida, lidos de `eixos`. O filtro de lente e o de classe de ativo seguem
 * livres, e a métrica também.
 */

import type { Metadata } from "next";

import { Moldura, MolduraDeErro, TELAS } from "../_components/Moldura";
import { Heatmap, type CampoDoHeatmap } from "../_components/Heatmap";
import { SeletorDeLente, type CampoDeFiltro } from "../_components/SeletorDeLente";
import { abrirDataset, tentar } from "../_lib/dataset";
import {
  extremoDeclarado,
  extremoSimetrico,
  formatarInteiro,
  valorApresentado,
} from "../_lib/formato";
import type { HeatmapView } from "../_lib/schema";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Alocação Macro · Heatmap regime × ativo — Admin LDC",
};

const TELA = TELAS[1];

const MEDIDAS: Array<{ valor: CampoDoHeatmap; rotulo: string }> = [
  { valor: "excesso_cdi", rotulo: "excesso sobre o CDI" },
  { valor: "ret_medio", rotulo: "retorno médio nominal" },
  { valor: "ret_mediana", rotulo: "mediana do retorno" },
];

type Busca = { vista?: string; lente?: string; medida?: string; classes?: string };

export default async function HeatmapPage({ searchParams }: { searchParams: Promise<Busca> }) {
  const aberta = await tentar(abrirDataset());
  if (!aberta.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Heatmap regime × ativo" erro={aberta.erro} />;
  }
  const sessao = aberta.valor;

  const lida = await tentar(sessao.lerView("heatmap_regime_ativo"));
  if (!lida.ok) {
    return <MolduraDeErro atual={TELA.href} titulo="Heatmap regime × ativo" erro={lida.erro} />;
  }
  const view: HeatmapView = lida.valor;

  const busca = await searchParams;

  const vista = view.vistas.includes(busca.vista ?? "") ? (busca.vista as string) : view.vistas[0];
  const medida = (MEDIDAS.some((m) => m.valor === busca.medida)
    ? busca.medida
    : view.metrica_padrao === "ret_medio" || view.metrica_padrao === "ret_mediana"
      ? view.metrica_padrao
      : "excesso_cdi") as CampoDoHeatmap;

  const eixosDaVista = view.eixos
    .filter((e) => e.vista === vista)
    .slice()
    .sort((a, b) => a.coluna - b.coluna);

  const lentesDaVista = Array.from(new Set(eixosDaVista.map((e) => e.lente)));
  const lente =
    busca.lente && (busca.lente === "todas" || lentesDaVista.includes(busca.lente))
      ? busca.lente
      : "todas";

  const eixos = eixosDaVista.filter((e) => lente === "todas" || e.lente === lente);

  const classesDeclaradas = view.grupos;
  const marcadas =
    busca.classes && busca.classes.length > 0
      ? new Set(busca.classes.split(",").filter((c) => classesDeclaradas.includes(c)))
      : new Set(classesDeclaradas);
  const classesVisiveis = marcadas.size === 0 ? new Set(classesDeclaradas) : marcadas;

  const ativos = view.ativos.filter((a) => classesVisiveis.has(a.grupo));
  const ativosVisiveis = new Set(ativos.map((a) => a.asset_id));
  const regimesVisiveis = new Set(eixos.map((e) => e.regime));

  const celulasDaVista = view.celulas.filter((c) => c.vista === vista);
  const celulas = celulasDaVista.filter(
    (c) => ativosVisiveis.has(c.asset_id) && regimesVisiveis.has(c.regime),
  );

  /*
   * O extremo vem DECLARADO pelo exportador (`eixos_de_cor`, desde 2026-10-11): ±max(|valor|) por
   * (vista, campo) sobre a VISTA INTEIRA, nunca sobre o recorte — se dependesse do filtro, marcar
   * uma classe repintaria as outras e duas leituras da mesma tag deixariam de ser comparáveis. É
   * extensão de eixo, não estatística.
   *
   * O cálculo local fica como último recurso, para a tag antiga que não declara o eixo; ele dá o
   * mesmo número, e é exatamente por isso que pode ser substituído sem a tela mudar de aparência.
   */
  const extremo =
    extremoDeclarado(sessao.meta, view.eixos_de_cor ?? [], vista, medida) ??
    extremoSimetrico(
      celulasDaVista.map((c) =>
        c[medida] === null ? null : valorApresentado(sessao.meta, medida, c[medida] as number),
      ),
    );

  // `n` por regime vem da timeline, quando a tag a publica. Sem ela, o cabeçalho não inventa.
  const timeline = sessao.temView("regimes_timeline")
    ? await tentar(sessao.lerView("regimes_timeline"))
    : null;
  const nPorRegime = timeline?.ok ? timeline.valor.distribuicao.por_grupo : undefined;

  const regimeDaV3 = eixos.find((e) => e.lente === "V3")?.regime ?? null;

  const campos: CampoDeFiltro[] = [
    {
      chave: "vista",
      rotulo: "Vista",
      valor: vista,
      nota: "materialização e horizonte vêm com ela",
      opcoes: view.vistas.map((v) => {
        const eixosDaOpcao = view.eixos.filter((e) => e.vista === v);
        const materializacoes = Array.from(new Set(eixosDaOpcao.map((e) => e.materializacao)));
        const horizontes = Array.from(new Set(eixosDaOpcao.map((e) => `${e.lente} em ${e.horizonte}`)));
        return {
          valor: v,
          rotulo: `${v} — ${materializacoes.join("/")} · ${horizontes.join(", ")}`,
        };
      }),
    },
    {
      chave: "lente",
      rotulo: "Lente",
      valor: lente,
      opcoes: [
        { valor: "todas", rotulo: "as duas, lado a lado" },
        ...lentesDaVista.map((l) => ({ valor: l, rotulo: `só ${l}` })),
      ],
    },
    {
      chave: "medida",
      rotulo: "Medida",
      valor: medida,
      nota: "as três são colunas da célula",
      opcoes: MEDIDAS.map((m) => ({ valor: m.valor, rotulo: m.rotulo })),
    },
  ];

  const materializacoesDaVista = Array.from(new Set(eixosDaVista.map((e) => e.materializacao)));
  const horizontesDaVista = Array.from(
    new Set(eixosDaVista.map((e) => `${e.lente} em ${e.horizonte}`)),
  );

  return (
    <Moldura
      atual={TELA.href}
      titulo="Heatmap regime × ativo"
      pergunta={view.pergunta}
      gate={view.gate}
      meta={sessao.meta}
      ponteiro={sessao.ponteiro}
      views={nPorRegime ? ["heatmap_regime_ativo", "regimes_timeline"] : ["heatmap_regime_ativo"]}
    >
      <SeletorDeLente
        campos={campos}
        caixas={classesDeclaradas.map((titulo) => ({
          chave: titulo,
          rotulo: titulo,
          marcada: classesVisiveis.has(titulo),
        }))}
        rotuloDasCaixas="Classe de ativo"
      />

      <p className="mb-3 text-xs text-gray-600">
        Vista {vista}: materialização {materializacoesDaVista.join(" e ")} ·{" "}
        {horizontesDaVista.join(" · ")} · tabela{" "}
        {Array.from(new Set(eixosDaVista.map((e) => e.tabela))).join(", ")}.{" "}
        {formatarInteiro(ativos.length)} linhas · {formatarInteiro(celulas.length)} células ·{" "}
        {formatarInteiro(eixos.length)} colunas. A ordem das linhas é a declarada pelo exportador e
        não muda com o desempenho; a linha do CDI fecha em zero e é a conferência visual da própria
        métrica.
      </p>

      <Heatmap
        meta={sessao.meta}
        eixos={eixos}
        ativos={ativos}
        grupos={classesDeclaradas.filter((g) => classesVisiveis.has(g))}
        celulas={celulas}
        campo={medida}
        extremo={extremo}
        limiares={view.limiares_de_n}
        excluidos={view.excluidos_da_figura}
        escala={view.escala}
        nPorRegime={nPorRegime}
        regimeDestacado={regimeDaV3}
      />

      <p className="ldc-info mt-4 text-xs">
        Legenda dos limiares, como o dado declara:{" "}
        {Object.entries(view.limiares_de_n.legenda)
          .map(([chave, texto]) => `${chave}: ${texto}`)
          .join(" · ")}
        . Fontes desta view: {view.fontes.join(" · ")}.
      </p>
    </Moldura>
  );
}
