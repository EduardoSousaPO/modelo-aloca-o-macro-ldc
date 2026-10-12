// @vitest-environment jsdom

/**
 * `n` EM TODA CÉLULA — o teste que trava o risco nº 1 deste produto.
 *
 * O dado tem 13 a 19 observações por regime e erro-padrão medido de 0 a 6,01 pp. Uma célula sem
 * `n` transforma "rendeu X, com esta incerteza" em "rendeu X", que é outra afirmação. O teste
 * varre TODAS as células desenhadas (atributo `data-celula` no SVG e `data-celula-texto` na tabela
 * acessível) e reprova a primeira que não traga o número de observações.
 *
 * Prova também o que a tela faz com a unidade e com os limiares:
 *   - `0,0504` em fração sai `+5,04%` — nunca `0,05`, nunca `504`: o fator 100 vem de
 *     `meta.fator_de_apresentacao`, declarado pelo exportador, e não de constante no front;
 *   - abaixo do limiar de supressão a célula perde a cor e o número cai para `prelim.`;
 *   - entre os dois limiares entram o asterisco e a borda tracejada;
 *   - a célula **não traz cor** do exportador (D-ai): quem pinta é a rampa da casa, e o extremo
 *     da escala vem do eixo que a view declara (`eixos_de_cor`).
 */

import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { Heatmap } from "../_components/Heatmap";
import { TabelaRanking } from "../_components/TabelaRanking";
import { ESCALA, extremoDeclarado, fatorDeApresentacao } from "../_lib/formato";
import { meta } from "./fixtura";
import type {
  AtivoDoHeatmap,
  CelulaDoHeatmap,
  EixoDoHeatmap,
  ExclusaoDaFigura,
  LimiaresDeN,
  LinhaDeRanking,
} from "../_lib/schema";

const META = meta();
const VISTA = "v1_revised";

const EIXOS: EixoDoHeatmap[] = [
  {
    vista: VISTA,
    regime: "ESTAGFLACAO",
    tabela: "regime_asset_metrics.parquet",
    lente: "V1",
    materializacao: "revised",
    horizonte: "T0",
    coluna: 3,
  },
  {
    vista: VISTA,
    regime: "DESACELERACAO",
    tabela: "regime_asset_metrics.parquet",
    lente: "V1",
    materializacao: "revised",
    horizonte: "T0",
    coluna: 4,
  },
  {
    vista: VISTA,
    regime: "VIZINHOS_2026Q3",
    tabela: "regime_asset_metrics.parquet",
    lente: "V3",
    materializacao: "revised",
    horizonte: "T+1",
    coluna: 5,
  },
];

const ATIVOS: AtivoDoHeatmap[] = [
  { asset_id: "SP500_BRL", grupo: "Internacional (em BRL)", linha: 1, data_inicio_serie: "2006Q2" },
  { asset_id: "IFIX", grupo: "Fundos imobiliarios", linha: 2, data_inicio_serie: "2011Q1" },
  { asset_id: "ICON", grupo: "Acoes - setoriais B3", linha: 3, data_inicio_serie: "2007Q1" },
];

const GRUPOS = ["Internacional (em BRL)", "Fundos imobiliarios", "Acoes - setoriais B3"];

const LIMIARES: LimiaresDeN = {
  alerta_abaixo_de: 8,
  supressao_abaixo_de: 5,
  legenda: {
    alerta: "n abaixo de 8 entra com alerta",
    supressao: "n abaixo de 5 sai sem conclusao",
  },
};

const EXCLUIDOS: ExclusaoDaFigura[] = [
  { asset_id: "SP500_USD", motivo: "retorno em dolar contra CDI em reais mistura moedas" },
];

function celula(
  parcial: Partial<CelulaDoHeatmap> & Pick<CelulaDoHeatmap, "regime" | "asset_id" | "n_obs">,
): CelulaDoHeatmap {
  return {
    vista: VISTA,
    excesso_cdi: 0,
    ret_medio: 0,
    ret_mediana: 0,
    erro_padrao_media: 0.0254,
    hit_ratio_cdi: 0.62,
    pior_tri: -0.1769,
    pior_tri_quarter: "2011Q3",
    alerta_n_baixo: false,
    conclusao_suprimida: false,
    hachura: null,
    ...parcial,
  };
}

const CELULAS: CelulaDoHeatmap[] = [
  celula({ regime: "ESTAGFLACAO", asset_id: "SP500_BRL", n_obs: 16, excesso_cdi: 0.0504 }),
  celula({ regime: "DESACELERACAO", asset_id: "SP500_BRL", n_obs: 13, excesso_cdi: -0.0256 }),
  celula({ regime: "VIZINHOS_2026Q3", asset_id: "SP500_BRL", n_obs: 8, excesso_cdi: 0.0341 }),
  celula({
    regime: "ESTAGFLACAO",
    asset_id: "IFIX",
    n_obs: 4,
    excesso_cdi: -0.065,
    conclusao_suprimida: true,
    hachura: "///",
  }),
  celula({
    regime: "DESACELERACAO",
    asset_id: "IFIX",
    n_obs: 4,
    excesso_cdi: null,
    conclusao_suprimida: true,
    hachura: "///",
  }),
  celula({
    regime: "VIZINHOS_2026Q3",
    asset_id: "IFIX",
    n_obs: 4,
    excesso_cdi: null,
    conclusao_suprimida: true,
    hachura: "///",
  }),
  celula({
    regime: "ESTAGFLACAO",
    asset_id: "ICON",
    n_obs: 6,
    excesso_cdi: -0.004,
    alerta_n_baixo: true,
  }),
  celula({
    regime: "DESACELERACAO",
    asset_id: "ICON",
    n_obs: 6,
    excesso_cdi: 0.012,
    alerta_n_baixo: true,
  }),
  celula({
    regime: "VIZINHOS_2026Q3",
    asset_id: "ICON",
    n_obs: 6,
    excesso_cdi: 0.009,
    alerta_n_baixo: true,
  }),
];

function renderHeatmap() {
  return render(
    <Heatmap
      meta={META}
      eixos={EIXOS}
      ativos={ATIVOS}
      grupos={GRUPOS}
      celulas={CELULAS}
      campo="excesso_cdi"
      extremo={8}
      limiares={LIMIARES}
      excluidos={EXCLUIDOS}
      escala="Divergente SIMETRICA em +/- extremo"
      nPorRegime={{ ESTAGFLACAO: 16, DESACELERACAO: 13 }}
      regimeDestacado="VIZINHOS_2026Q3"
    />,
  );
}

describe("heatmap: n em toda célula", () => {
  it("desenha uma célula por par visível e nenhuma sem o n", () => {
    const { container } = renderHeatmap();
    const celulas = container.querySelectorAll("[data-celula]");
    expect(celulas.length).toBe(CELULAS.length);
    for (const el of Array.from(celulas)) {
      expect(el.textContent ?? "").toMatch(/n = \d/);
    }
  });

  it("repete o n na tabela acessível, célula por célula", () => {
    const { container } = renderHeatmap();
    const celulas = container.querySelectorAll("[data-celula-texto]");
    expect(celulas.length).toBe(CELULAS.length);
    for (const el of Array.from(celulas)) {
      expect(el.textContent ?? "").toMatch(/n = \d/);
    }
  });

  it("traz o n do regime no cabeçalho quando a tag publica a timeline", () => {
    const { container } = renderHeatmap();
    const texto = container.textContent ?? "";
    expect(texto).toContain("n = 16");
    expect(texto).toContain("n = 13");
  });

  it("converte pelo fator que o meta declara: 0,0504 em fração é +5,04% na célula", () => {
    expect(fatorDeApresentacao(META, "excesso_cdi")).toBe(100);
    expect(fatorDeApresentacao(META, "selic_meta_pct")).toBe(1);
    const { container } = renderHeatmap();
    const alvo = container.querySelector('[data-celula="ESTAGFLACAO|SP500_BRL"]');
    expect(alvo).not.toBeNull();
    const texto = alvo!.textContent ?? "";
    expect(texto).toContain("+5,04%");
    expect(texto).not.toContain("0,05%");
    expect(texto).not.toContain("504,");
  });

  it("célula abaixo do limiar de supressão perde a cor, rebaixa o número e mantém o n", () => {
    const { container } = renderHeatmap();
    const alvo = container.querySelector('[data-celula="ESTAGFLACAO|IFIX"]');
    const texto = alvo!.textContent ?? "";
    expect(texto).toContain("prelim. -6,50%");
    expect(texto).toContain("n = 4");
    const rect = alvo!.querySelector("rect");
    expect(rect?.getAttribute("fill")).toContain("url(#am-hachura)");
    const textos = Array.from(alvo!.querySelectorAll("text"));
    expect(textos.every((t) => t.getAttribute("font-weight") !== "700")).toBe(true);
  });

  it("célula sem valor nenhum sai como sem conclusão, com o n", () => {
    const { container } = renderHeatmap();
    const alvo = container.querySelector('[data-celula="DESACELERACAO|IFIX"]');
    const texto = alvo!.textContent ?? "";
    expect(texto).toContain("sem conclusão");
    expect(texto).toContain("n = 4");
  });

  it("célula entre os dois limiares traz cor, asterisco e borda tracejada", () => {
    const { container } = renderHeatmap();
    const alvo = container.querySelector('[data-celula="ESTAGFLACAO|ICON"]');
    const texto = alvo!.textContent ?? "";
    expect(texto).toContain("-0,40%*");
    expect(texto).toContain("n = 6");
    expect(alvo!.querySelector("rect")?.getAttribute("stroke-dasharray")).toBe("3 2");
  });

  it("a célula não traz cor do exportador: quem pinta é a rampa da casa", () => {
    /*
     * D-ai: o exportador parou de emitir `cor_hex` (era o hex da figura matplotlib). O tipo
     * gerado já não tem o campo — o `tsc` reprovaria pôr de volta — e o que a tela desenha é a
     * rampa de `_lib/formato.ts`: dois arcos da marca, nenhum azul de paleta placeholder.
     */
    const { container } = renderHeatmap();
    const fills = Array.from(container.querySelectorAll("[data-celula] rect")).map((r) =>
      r.getAttribute("fill"),
    );
    const paleta: string[] = [
      ESCALA.neutro,
      ESCALA.suprimido,
      ...ESCALA.negativo,
      ...ESCALA.positivo,
    ];
    expect(fills.length).toBeGreaterThan(0);
    expect(fills.some((f) => f === "#3987e5")).toBe(false);
    for (const fill of fills) {
      // a célula suprimida é a hachura (um `url(#...)`), as outras são hex da rampa da casa
      const daCasa = fill !== null && (fill.startsWith("url(#") || paleta.includes(fill));
      expect(daCasa).toBe(true);
    }
  });

  it("o extremo da escala vem do eixo declarado pela view, na escala apresentada", () => {
    /*
     * `eixos_de_cor` publica ±max(|valor|) por (vista, campo) sobre a VISTA INTEIRA, em unidade
     * nativa: 0,0650 de IFIX em ESTAGFLACAO. Na tela isso é 6,50 — o fator vem do mesmo `meta`.
     * Vista que a view não declara sai `null`, e aí a tela não inventa escala.
     */
    const eixos = [
      { vista: VISTA, campo: "excesso_cdi", extremo_simetrico: 0.065 },
      { vista: VISTA, campo: "pior_tri", extremo_simetrico: null },
    ];
    expect(extremoDeclarado(META, eixos, VISTA, "excesso_cdi")).toBeCloseTo(6.5, 10);
    expect(extremoDeclarado(META, eixos, VISTA, "pior_tri")).toBeNull();
    expect(extremoDeclarado(META, eixos, "OUTRA_VISTA", "excesso_cdi")).toBeNull();
  });

  it("todo tooltip de célula nomeia erro-padrão, mediana e pior trimestre", () => {
    const { container } = renderHeatmap();
    for (const el of Array.from(container.querySelectorAll("[data-celula]"))) {
      const titulo = el.querySelector("title")?.textContent ?? "";
      expect(titulo).toContain("erro-padrão");
      expect(titulo).toContain("mediana");
      expect(titulo).toContain("pior trimestre");
      expect(titulo).toMatch(/n = \d/);
    }
  });

  it("os dois limiares vêm do dado e aparecem escritos na legenda", () => {
    const { container } = renderHeatmap();
    const texto = container.textContent ?? "";
    expect(texto).toContain("n abaixo de 8");
    expect(texto).toContain("n abaixo de 5");
  });
});

describe("tabela de ranking: n em toda linha", () => {
  function linha(
    parcial: Partial<LinhaDeRanking> & Pick<LinhaDeRanking, "asset_id" | "n_obs">,
  ): LinhaDeRanking {
    return {
      lente_rotulo: "V3 (momentos semelhantes)",
      lente: "V3",
      regime: "VIZINHOS_2026Q3",
      posicao: 1,
      excesso_cdi: 0.0504,
      ret_medio: 0.06,
      ret_mediana: 0.05,
      hit_ratio_cdi: 0.62,
      erro_padrao_media: 0.0254,
      excesso_em_erros_padrao: 1.98,
      distinguivel_de_ruido: false,
      alerta_n_baixo: true,
      conclusao_suprimida: false,
      ...parcial,
    };
  }

  const linhas: LinhaDeRanking[] = [
    linha({ asset_id: "INDX", n_obs: 8 }),
    linha({
      asset_id: "IMOB",
      n_obs: 4,
      posicao: 2,
      excesso_cdi: null,
      erro_padrao_media: 0.0601,
      excesso_em_erros_padrao: null,
      distinguivel_de_ruido: null,
      conclusao_suprimida: true,
    }),
  ];

  it("nenhuma linha sai sem o n, e a linha suprimida sai sem número", () => {
    const { container } = render(
      <TabelaRanking
        linhas={linhas}
        meta={META}
        extremo={8}
        limiares={{ alerta_abaixo_de: 8, supressao_abaixo_de: 5 }}
      />,
    );
    const linhasDeDado = Array.from(container.querySelectorAll("tbody tr")).filter((tr) =>
      tr.querySelector("td"),
    );
    expect(linhasDeDado.length).toBe(2);
    for (const tr of linhasDeDado) {
      expect(tr.textContent ?? "").toMatch(/n = \d/);
    }
    const texto = container.textContent ?? "";
    expect(texto).toContain("+5,04%");
    expect(texto).toContain("sem conclusão");
  });

  it("agrupa por faixa declarada pelo dado e não numera pódio", () => {
    const { container } = render(<TabelaRanking linhas={linhas} meta={META} extremo={8} />);
    const texto = container.textContent ?? "";
    expect(texto).toContain("Faixa: dentro de 2 erros-padrão");
    expect(texto).toContain("Faixa: sem conclusão");
    expect(texto).not.toMatch(/\b1º\b/);
    expect(texto).not.toMatch(/\b2º\b/);
  });
});
