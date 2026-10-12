/**
 * A célula — e o `n` dentro dela, nunca no tooltip (RF-W021, Anti-SPEC §10.2.8).
 *
 * `n` é prop OBRIGATÓRIA e não opcional por um motivo: é o que torna impossível escrever uma
 * célula sem observação visível. O risco nº 1 deste produto é `n` pequeno virando conclusão, e
 * "esqueci de passar o n" não pode ser um caminho possível.
 *
 * Duas formas, um comportamento:
 *   - `CelulaComN`          → conteúdo de `<td>`, para as tabelas;
 *   - `CelulaDoHeatmapSvg`  → um `<g>` do SVG, para a grade do heatmap.
 *
 * Os três estados de confiança vêm de `pintarCelula` (`_lib/formato.ts`), sempre em dois canais:
 * cor + número · cor + tracejado + asterisco · sem cor + hachura + número rebaixado a `prelim.`.
 * Na tabela a célula suprimida sai **sem** número ("sem conclusão"), porque ali a posição da
 * linha é lida como ordem; na figura o número é rebaixado, porque a posição é o cruzamento
 * regime × ativo e não afirma nada. É a forma declarada em RF-W021 e em F-023 §4.3.
 */

import { ESCALA, formatarInteiro, pintarCelula } from "../_lib/formato";

const ID_DA_HACHURA = "am-hachura";

/** Os `<defs>` do SVG: a hachura da supressão, declarada uma vez por figura. */
export function DefsDaEscala() {
  return (
    <defs>
      <pattern
        id={ID_DA_HACHURA}
        width="6"
        height="6"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <rect width="6" height="6" fill={ESCALA.suprimido} />
        <line x1="0" y1="0" x2="0" y2="6" stroke={ESCALA.hachura} strokeWidth="2" />
      </pattern>
    </defs>
  );
}

export interface PropsDaCelula {
  /** Já formatado e com unidade pela camada `_lib/formato.ts`. A célula não formata número. */
  texto: string;
  /** Observações da célula. Obrigatório de propósito. */
  n: number;
  alerta: boolean;
  suprimida: boolean;
}

/** Conteúdo de célula de tabela: valor, `n` e as marcas. Alinhado à direita (`.ldc-num`). */
export function CelulaComN({ texto, n, alerta, suprimida }: PropsDaCelula) {
  return (
    <span className="inline-flex flex-col items-end leading-tight">
      {suprimida ? (
        <span className="text-xs font-normal text-gray-700">sem conclusão</span>
      ) : (
        <span className="text-sm font-semibold text-gray-900">
          {texto}
          {alerta ? "*" : ""}
        </span>
      )}
      <span className="text-xs text-gray-600">n = {formatarInteiro(n)}</span>
    </span>
  );
}

export interface PropsDaCelulaSvg {
  x: number;
  y: number;
  largura: number;
  altura: number;
  /** O valor na escala de APRESENTAÇÃO, só para escolher o passo da cor. */
  valor: number | null;
  extremo: number;
  /** O texto já formatado, com sinal. */
  texto: string;
  n: number;
  alerta: boolean;
  suprimida: boolean;
  /** Texto do `<title>`: erro-padrão, acerto, mediana, pior trimestre e flags. */
  tooltip: string;
  rotuloAcessivel: string;
  /** Lime fora da escala: a marca do recorte corrente, nunca o sinal do número. */
  destacada?: boolean;
  onSelecionar?: () => void;
  /** Identidade da célula no DOM. É o que o teste de "n em toda célula" enumera. */
  dataChave?: string;
}

/** Uma célula da grade do heatmap. */
export function CelulaDoHeatmapSvg({
  x,
  y,
  largura,
  altura,
  valor,
  extremo,
  texto,
  n,
  alerta,
  suprimida,
  tooltip,
  rotuloAcessivel,
  destacada = false,
  onSelecionar,
  dataChave,
}: PropsDaCelulaSvg) {
  const pintura = pintarCelula({ valor, extremo, alerta, suprimida });
  const cx = x + largura / 2;
  const interativa = typeof onSelecionar === "function";
  const semValor = valor === null;
  return (
    <g
      data-celula={dataChave}
      role={interativa ? "button" : "img"}
      tabIndex={interativa ? 0 : -1}
      aria-label={rotuloAcessivel}
      onClick={onSelecionar}
      onKeyDown={
        interativa
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelecionar?.();
              }
            }
          : undefined
      }
      style={interativa ? { cursor: "pointer" } : undefined}
    >
      <title>{tooltip}</title>
      <rect
        x={x}
        y={y}
        width={largura}
        height={altura}
        rx={3}
        fill={pintura.hachurada ? `url(#${ID_DA_HACHURA})` : pintura.fundo}
        stroke={
          destacada
            ? "#98ab44"
            : pintura.tracejada
              ? ESCALA.ancoraNegativa
              : pintura.hachurada
                ? ESCALA.hachura
                : "transparent"
        }
        strokeWidth={destacada ? 2 : pintura.tracejada ? 1.25 : 1}
        strokeDasharray={pintura.tracejada ? "3 2" : undefined}
      />
      {suprimida || semValor ? (
        <>
          <text
            x={cx}
            y={y + altura / 2 - 1}
            textAnchor="middle"
            fontSize="8.5"
            fill={ESCALA.tintaSuprimida}
          >
            {semValor ? "sem conclusão" : `prelim. ${texto}`}
          </text>
          <text
            x={cx}
            y={y + altura / 2 + 10}
            textAnchor="middle"
            fontSize="8"
            fill={ESCALA.tintaSuprimida}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            n = {formatarInteiro(n)}
          </text>
        </>
      ) : (
        <>
          <text
            x={cx}
            y={y + altura / 2 - 1}
            textAnchor="middle"
            fontSize="10.5"
            fontWeight={700}
            fill={pintura.tinta}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {texto}
            {alerta ? "*" : ""}
          </text>
          <text
            x={cx}
            y={y + altura / 2 + 10}
            textAnchor="middle"
            fontSize="8"
            fill={pintura.tinta}
            fillOpacity={0.9}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            n = {formatarInteiro(n)}
          </text>
        </>
      )}
    </g>
  );
}
