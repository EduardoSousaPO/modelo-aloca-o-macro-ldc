"use client";

/**
 * Barra de erro NO GRÁFICO, não só na tabela (RF-W027, `arquitetura` §7.3).
 *
 * Por que ela é obrigatória: os erros-padrão medidos vão de 0,00 pp (CDI) a 6,01 pp (IMOB), e o
 * primeiro colocado do ranking de T+1 tem média +5,04 pp com erro-padrão de 2,54 pp. Escrito
 * está: "a ordem do ranking não é estatisticamente distinguível". Uma lista numerada sem
 * dispersão desfaz essa frase em um segundo.
 *
 * O desenho: ponto da média + segmento de ±1 erro-padrão (traço cheio) e ±2 (traço fino), sobre
 * um eixo COMUM a todas as linhas da tabela, com o zero marcado. Dois erros-padrão aparecem
 * porque é o limiar que o próprio exportador usa em `excesso_em_erros_padrao` /
 * `distinguivel_de_ruido`.
 *
 * Recebe número **já na escala de apresentação** (quem converte é `_lib/formato.ts`) e textos já
 * formatados: a barra não formata e não converte.
 *
 * POR QUE `"use client"`: `charts.tsx` é um módulo `"use client"`, e no App Router todo export de
 * um módulo de cliente vira referência de cliente — um Server Component que lesse
 * `CHART_COLORS.NAVY` levantaria em runtime. Renderizar um componente de cliente a partir do
 * servidor é permitido; LER um valor dele não é. O alternativo seria redeclarar o hex, que é o
 * drift registrado em `ldc-analytics-identidade-v2.md` §3.2.
 */

import { CHART_COLORS } from "@/app/admin/wealth-planning/components/charts";

const num = { fontVariantNumeric: "tabular-nums" } as const;

export interface PropsDaBarraDeErro {
  /** Na escala de apresentação. `null` desenha só o eixo e o aviso. */
  valor: number | null;
  /** Na mesma escala do valor. */
  erroPadrao: number | null;
  /** Extremo do eixo comum, simétrico, na escala de apresentação. */
  extremo: number;
  /** O rótulo acessível completo, já formatado com unidade e com o `n`. */
  rotulo: string;
  largura?: number;
  altura?: number;
}

export function BarraDeErro({
  valor,
  erroPadrao,
  extremo,
  rotulo,
  largura = 180,
  altura = 26,
}: PropsDaBarraDeErro) {
  const limite = extremo > 0 ? extremo : 1;
  const px = (v: number) =>
    ((Math.max(-limite, Math.min(limite, v)) + limite) / (2 * limite)) * largura;
  const meio = altura / 2;

  if (valor === null) {
    return (
      <svg
        viewBox={`0 0 ${largura} ${altura}`}
        width={largura}
        height={altura}
        role="img"
        aria-label={rotulo}
      >
        <line x1={0} y1={meio} x2={largura} y2={meio} stroke={CHART_COLORS.GRID} />
        <line x1={px(0)} y1={4} x2={px(0)} y2={altura - 4} stroke={CHART_COLORS.LINE} />
        <text x={px(0) + 6} y={meio + 3} fontSize="8.5" fill={CHART_COLORS.SLATE}>
          sem conclusão
        </text>
      </svg>
    );
  }

  const ep = erroPadrao ?? 0;

  return (
    <svg
      viewBox={`0 0 ${largura} ${altura}`}
      width={largura}
      height={altura}
      role="img"
      aria-label={rotulo}
      style={num}
    >
      <line x1={0} y1={meio} x2={largura} y2={meio} stroke={CHART_COLORS.GRID} />
      {/* o zero, marcado: sem ele a barra não diz de que lado do CDI o número está */}
      <line x1={px(0)} y1={3} x2={px(0)} y2={altura - 3} stroke={CHART_COLORS.LINE} strokeWidth={1} />
      {ep > 0 && (
        <>
          <line
            x1={px(valor - 2 * ep)}
            y1={meio}
            x2={px(valor + 2 * ep)}
            y2={meio}
            stroke={CHART_COLORS.SLATE}
            strokeWidth={1}
            strokeOpacity={0.45}
          />
          <line
            x1={px(valor - ep)}
            y1={meio}
            x2={px(valor + ep)}
            y2={meio}
            stroke={CHART_COLORS.SLATE}
            strokeWidth={2.5}
            strokeLinecap="round"
          />
          {[valor - 2 * ep, valor + 2 * ep].map((v, i) => (
            <line
              key={i}
              x1={px(v)}
              y1={meio - 4}
              x2={px(v)}
              y2={meio + 4}
              stroke={CHART_COLORS.SLATE}
              strokeOpacity={0.45}
            />
          ))}
        </>
      )}
      <circle
        cx={px(valor)}
        cy={meio}
        r={3.5}
        fill={CHART_COLORS.NAVY}
        stroke="#fcfdfd"
        strokeWidth={1.5}
      />
    </svg>
  );
}

/** Legenda da barra, uma vez por tabela. */
export function LegendaDaBarraDeErro({ unidade }: { unidade: string }) {
  return (
    <p className="text-xs text-gray-600">
      Barra: traço grosso = ±1 erro-padrão da média, traço fino = ±2. Eixo comum a todas as linhas
      {unidade ? `, em ${unidade}` : ""}, com o zero marcado. Quando o intervalo de ±2 cruza o zero,
      a linha não se distingue do CDI pelo dado desta janela.
    </p>
  );
}
