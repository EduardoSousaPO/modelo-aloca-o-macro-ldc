"use client";

/**
 * O heatmap regime × ativo. SVG próprio, no idioma do kit do wealth-planning.
 *
 * POR QUE SVG PRÓPRIO E NÃO RECHARTS (que está no `package.json`): Recharts não tem heatmap; o
 * que existe é `ScatterChart` com célula desenhada à mão, e aí o trabalho é o mesmo com uma
 * camada de abstração no caminho. E as exigências desta figura são todas de desenho fino: `n`
 * DENTRO de cada célula, borda tracejada como segundo canal entre os dois limiares, hachura sem
 * cor na supressão, vão entre grupos de classe. O kit da casa já é SVG escrito à mão
 * (`charts.tsx`: "Identidade LDC, sem dependência externa") — o idioma `px`/`py` com
 * `padL/padR/padT/padB` do `ProjectionChart` é copiado aqui quase literal.
 *
 * O que esta figura NÃO faz:
 *   - não ordena linhas por desempenho: a ordem é o campo `linha` que o exportador declara, e a
 *     mesma figura em duas rodadas fica comparável;
 *   - não recalcula nada: valor, `n_obs` e as duas flags vêm da view;
 *   - não esconde o `n` em tooltip: ele é desenhado dentro de toda célula;
 *   - não usa verde contra vermelho (colapsa em protanopia/deuteranopia) nem lime como sinal do
 *     número — lime, por `DESIGN.md`, é ação: aqui marca a coluna do recorte corrente;
 *   - não recebe cor nenhuma do exportador: desde **D-ai** a célula não traz `cor_hex` (era o hex
 *     da figura matplotlib, da paleta placeholder da skill `dataviz`). Quem pinta é a rampa da
 *     casa (`_lib/formato.ts`); o que vem do dado é o **eixo** da escala (`eixos_de_cor`) e os
 *     canais sem cor (`hachura`, `conclusao_suprimida`). A convergência da rampa com a figura do
 *     PDF é o adendo proposto ao `DESIGN.md`.
 */

import { useMemo, useState } from "react";
import { CHART_COLORS } from "@/app/admin/wealth-planning/components/charts";

import { CelulaDoHeatmapSvg, DefsDaEscala } from "./CelulaComN";
import {
  ESCALA,
  apresentar,
  apresentarCom,
  formatarInteiro,
  formatarNumero,
  notaDeUnidade,
  rotuloDeUnidade,
  valorApresentado,
} from "../_lib/formato";
import type {
  AtivoDoHeatmap,
  CelulaDoHeatmap,
  EixoDoHeatmap,
  ExclusaoDaFigura,
  LimiaresDeN,
  MetaWeb,
} from "../_lib/schema";

const LARGURA_ROTULO = 168;
const LARGURA_COLUNA = 112;
const ALTURA_LINHA = 30;
const ALTURA_TITULO_DE_GRUPO = 18;
const ALTURA_CABECALHO = 58;
const VAO_ENTRE_GRUPOS = 10;
const RECUO = 2;

const num = { fontVariantNumeric: "tabular-nums" } as const;

/** Os campos que a figura sabe mostrar. Todos existem como coluna da célula. */
export type CampoDoHeatmap = "excesso_cdi" | "ret_medio" | "ret_mediana";

type Linha =
  | { tipo: "grupo"; titulo: string; y: number }
  | { tipo: "ativo"; ativo: AtivoDoHeatmap; y: number };

function montarLinhas(
  grupos: readonly string[],
  ativos: readonly AtivoDoHeatmap[],
): { linhas: Linha[]; altura: number } {
  const linhas: Linha[] = [];
  let y = ALTURA_CABECALHO;
  grupos.forEach((grupo, i) => {
    const doGrupo = ativos
      .filter((a) => a.grupo === grupo)
      .slice()
      .sort((a, b) => a.linha - b.linha);
    if (doGrupo.length === 0) return;
    if (i > 0) y += VAO_ENTRE_GRUPOS;
    linhas.push({ tipo: "grupo", titulo: grupo, y });
    y += ALTURA_TITULO_DE_GRUPO;
    for (const ativo of doGrupo) {
      linhas.push({ tipo: "ativo", ativo, y });
      y += ALTURA_LINHA;
    }
  });
  return { linhas, altura: y + 6 };
}

export interface PropsDoHeatmap {
  meta: MetaWeb;
  /** Já filtrados para a vista escolhida e ordenados por `coluna`. */
  eixos: readonly EixoDoHeatmap[];
  /** Já filtrados pela classe marcada; a ordem de desenho é o campo `linha`. */
  ativos: readonly AtivoDoHeatmap[];
  grupos: readonly string[];
  celulas: readonly CelulaDoHeatmap[];
  campo: CampoDoHeatmap;
  /** Extremo na escala de apresentação, calculado sobre a vista inteira. */
  extremo: number;
  limiares: LimiaresDeN;
  excluidos: readonly ExclusaoDaFigura[];
  /** O texto que o exportador escreveu sobre a escala. */
  escala: string;
  /** `n` do regime, quando a tag publica a timeline. Sem ela, o cabeçalho não inventa número. */
  nPorRegime?: Record<string, number>;
  /** Regime a destacar com lime: o recorte do trimestre corrente. */
  regimeDestacado?: string | null;
}

export function Heatmap({
  meta,
  eixos,
  ativos,
  grupos,
  celulas,
  campo,
  extremo,
  limiares,
  excluidos,
  escala,
  nPorRegime,
  regimeDestacado = null,
}: PropsDoHeatmap) {
  const { linhas, altura } = useMemo(() => montarLinhas(grupos, ativos), [grupos, ativos]);
  const largura = LARGURA_ROTULO + eixos.length * LARGURA_COLUNA;

  const porChave = useMemo(() => {
    const m = new Map<string, CelulaDoHeatmap>();
    for (const c of celulas) m.set(`${c.regime}|${c.asset_id}`, c);
    return m;
  }, [celulas]);

  const inicioDaSerie = useMemo(() => {
    const m = new Map<string, string | null>();
    for (const a of ativos) m.set(a.asset_id, a.data_inicio_serie);
    return m;
  }, [ativos]);

  const tabelaPorRegime = useMemo(() => {
    const m = new Map<string, EixoDoHeatmap>();
    for (const e of eixos) m.set(e.regime, e);
    return m;
  }, [eixos]);

  const [emFoco, setEmFoco] = useState<CelulaDoHeatmap | null>(null);
  const [selecionada, setSelecionada] = useState<CelulaDoHeatmap | null>(null);

  const unidade = rotuloDeUnidade(meta, campo);

  const textoDa = (c: CelulaDoHeatmap) => {
    const a = apresentar(meta, campo, c[campo], { sinal: true });
    return a.unidade === "%" ? `${a.texto}%` : a.texto;
  };
  const naEscala = (c: CelulaDoHeatmap) =>
    c[campo] === null ? null : valorApresentado(meta, campo, c[campo] as number);

  const tooltipDa = (c: CelulaDoHeatmap) => {
    const partes = [
      `${c.asset_id} · ${c.regime}`,
      `${textoDa(c)}`,
      `n = ${formatarInteiro(c.n_obs)}`,
      `erro-padrão ${apresentarCom(meta, "erro_padrao_media", c.erro_padrao_media)}`,
      `mediana ${apresentarCom(meta, "ret_mediana", c.ret_mediana, { sinal: true })}`,
      `acerto vs CDI ${apresentarCom(meta, "hit_ratio_cdi", c.hit_ratio_cdi)}`,
      `pior trimestre ${apresentarCom(meta, "pior_tri", c.pior_tri, { sinal: true })}${
        c.pior_tri_quarter ? ` em ${c.pior_tri_quarter}` : ""
      }`,
      `série desde ${inicioDaSerie.get(c.asset_id) ?? "não declarado"}`,
    ];
    if (c.conclusao_suprimida) {
      partes.push(`sem conclusão: n abaixo de ${formatarInteiro(limiares.supressao_abaixo_de)}`);
    } else if (c.alerta_n_baixo) {
      partes.push(`alerta: n abaixo de ${formatarInteiro(limiares.alerta_abaixo_de)}`);
    }
    return partes.join(" | ");
  };

  return (
    <div>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${largura} ${altura}`}
          width="100%"
          style={{ minWidth: largura, ...num }}
          role="img"
          aria-label={`Heatmap de ${ativos.length} ativos por ${eixos.length} recortes de regime, com observações em toda célula.`}
        >
          <DefsDaEscala />

          {eixos.map((eixo, i) => {
            const x = LARGURA_ROTULO + i * LARGURA_COLUNA;
            const destacada = regimeDestacado === eixo.regime;
            const nRegime = nPorRegime?.[eixo.regime];
            return (
              <g key={`${eixo.vista}|${eixo.regime}`}>
                {destacada && (
                  <rect
                    x={x + RECUO}
                    y={6}
                    width={LARGURA_COLUNA - 2 * RECUO}
                    height={altura - 12}
                    fill={CHART_COLORS.LIME}
                    fillOpacity={0.06}
                  />
                )}
                <text
                  x={x + LARGURA_COLUNA / 2}
                  y={24}
                  textAnchor="middle"
                  fontSize="10.5"
                  fontWeight={700}
                  fill={CHART_COLORS.NAVY}
                >
                  {eixo.regime}
                </text>
                <text
                  x={x + LARGURA_COLUNA / 2}
                  y={38}
                  textAnchor="middle"
                  fontSize="9"
                  fill={CHART_COLORS.SLATE}
                >
                  {eixo.lente} · {eixo.horizonte}
                  {nRegime !== undefined ? ` · n = ${formatarInteiro(nRegime)}` : ""}
                </text>
                <line
                  x1={x}
                  y1={ALTURA_CABECALHO - 10}
                  x2={x + LARGURA_COLUNA}
                  y2={ALTURA_CABECALHO - 10}
                  stroke={CHART_COLORS.LINE}
                />
              </g>
            );
          })}

          {linhas.map((linha) =>
            linha.tipo === "grupo" ? (
              <text
                key={`g-${linha.titulo}`}
                x={0}
                y={linha.y + 12}
                fontSize="9"
                fontWeight={700}
                fill={CHART_COLORS.SLATE}
                letterSpacing="0.6"
              >
                {linha.titulo.toUpperCase()}
              </text>
            ) : (
              <g key={`a-${linha.ativo.asset_id}`}>
                <text
                  x={LARGURA_ROTULO - 10}
                  y={linha.y + ALTURA_LINHA / 2 + 3}
                  textAnchor="end"
                  fontSize="10"
                  fill={CHART_COLORS.NAVY}
                >
                  {linha.ativo.asset_id}
                </text>
                {eixos.map((eixo, i) => {
                  const chave = `${eixo.regime}|${linha.ativo.asset_id}`;
                  const celula = porChave.get(chave);
                  const x = LARGURA_ROTULO + i * LARGURA_COLUNA;
                  if (!celula) {
                    return (
                      <g
                        key={chave}
                        role="img"
                        aria-label={`${linha.ativo.asset_id} em ${eixo.regime}: sem linha no dataset`}
                      >
                        <title>{`${linha.ativo.asset_id} · ${eixo.regime}: a tag não traz esta linha`}</title>
                        <rect
                          x={x + RECUO}
                          y={linha.y + RECUO}
                          width={LARGURA_COLUNA - 2 * RECUO}
                          height={ALTURA_LINHA - 2 * RECUO}
                          rx={3}
                          fill="none"
                          stroke={CHART_COLORS.LINE}
                          strokeDasharray="2 3"
                        />
                        <text
                          x={x + LARGURA_COLUNA / 2}
                          y={linha.y + ALTURA_LINHA / 2 + 3}
                          textAnchor="middle"
                          fontSize="8.5"
                          fill={CHART_COLORS.SLATE}
                        >
                          sem linha
                        </text>
                      </g>
                    );
                  }
                  return (
                    <g
                      key={chave}
                      onMouseEnter={() => setEmFoco(celula)}
                      onMouseLeave={() => setEmFoco(null)}
                      onFocus={() => setEmFoco(celula)}
                      onBlur={() => setEmFoco(null)}
                    >
                      <CelulaDoHeatmapSvg
                        dataChave={chave}
                        x={x + RECUO}
                        y={linha.y + RECUO}
                        largura={LARGURA_COLUNA - 2 * RECUO}
                        altura={ALTURA_LINHA - 2 * RECUO}
                        valor={naEscala(celula)}
                        extremo={extremo}
                        texto={textoDa(celula)}
                        n={celula.n_obs}
                        alerta={celula.alerta_n_baixo}
                        suprimida={celula.conclusao_suprimida}
                        tooltip={tooltipDa(celula)}
                        rotuloAcessivel={`${celula.asset_id} em ${eixo.regime}: ${
                          celula.conclusao_suprimida ? "sem conclusão" : textoDa(celula)
                        }, n igual a ${formatarInteiro(celula.n_obs)}. Abrir o detalhe do par.`}
                        destacada={regimeDestacado === eixo.regime}
                        onSelecionar={() => setSelecionada(celula)}
                      />
                    </g>
                  );
                })}
              </g>
            ),
          )}
        </svg>
      </div>

      {/* A mesma grade em tabela, para leitor de tela: o SVG dá a leitura, a tabela dá a
          navegação por célula com cabeçalho de linha e de coluna. */}
      <table className="sr-only">
        <caption>
          Heatmap em forma de tabela. Toda célula traz o valor e o número de observações.
        </caption>
        <thead>
          <tr>
            <th scope="col">Ativo</th>
            {eixos.map((e) => (
              <th key={`${e.vista}|${e.regime}`} scope="col">
                {e.regime} ({e.lente}, {e.horizonte})
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas
            .filter((l): l is Extract<Linha, { tipo: "ativo" }> => l.tipo === "ativo")
            .map((l) => (
              <tr key={`t-${l.ativo.asset_id}`}>
                <th scope="row">
                  {l.ativo.asset_id} ({l.ativo.grupo})
                </th>
                {eixos.map((e) => {
                  const celula = porChave.get(`${e.regime}|${l.ativo.asset_id}`);
                  if (!celula) return <td key={e.regime}>sem linha no dataset</td>;
                  return (
                    <td key={e.regime} data-celula-texto={`${e.regime}|${l.ativo.asset_id}`}>
                      {celula.conclusao_suprimida ? "sem conclusão" : textoDa(celula)}, n ={" "}
                      {formatarInteiro(celula.n_obs)}
                    </td>
                  );
                })}
              </tr>
            ))}
        </tbody>
      </table>

      {/* legenda da escala: dois canais sempre, e o que o lime significa */}
      <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-gray-600">
        <div className="flex items-center gap-1.5">
          <span>perdeu do CDI</span>
          {[...ESCALA.negativo].reverse().map((cor) => (
            <span key={cor} className="inline-block h-3.5 w-5 rounded-sm" style={{ background: cor }} />
          ))}
          <span className="inline-block h-3.5 w-5 rounded-sm" style={{ background: ESCALA.neutro }} />
          {ESCALA.positivo.map((cor) => (
            <span key={cor} className="inline-block h-3.5 w-5 rounded-sm" style={{ background: cor }} />
          ))}
          <span>bateu o CDI</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3.5 w-5 rounded-sm"
            style={{ background: ESCALA.negativo[1], border: `1.25px dashed ${ESCALA.ancoraNegativa}` }}
          />
          <span>
            n abaixo de {formatarInteiro(limiares.alerta_abaixo_de)}: asterisco no número
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3.5 w-5 rounded-sm"
            style={{ background: ESCALA.suprimido, border: `1px solid ${ESCALA.hachura}` }}
          />
          <span>
            n abaixo de {formatarInteiro(limiares.supressao_abaixo_de)}: sem cor, número rebaixado a
            prelim.
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block h-3.5 w-5 rounded-sm"
            style={{ border: `2px solid ${CHART_COLORS.LIME}` }}
          />
          <span>recorte do trimestre corrente (lime é marca de recorte, não sinal do número)</span>
        </div>
      </div>

      {/* hover: o que não cabe na célula */}
      <div className="mt-3 min-h-[3.5rem] rounded-xl border p-3 text-sm" aria-live="polite">
        {emFoco ? (
          <p className="text-gray-900">
            <strong>
              {emFoco.asset_id} · {emFoco.regime}
            </strong>{" "}
            <span className="text-gray-700">
              {emFoco.conclusao_suprimida ? "sem conclusão" : textoDa(emFoco)} · n ={" "}
              {formatarInteiro(emFoco.n_obs)} · erro-padrão{" "}
              {apresentarCom(meta, "erro_padrao_media", emFoco.erro_padrao_media)} · mediana{" "}
              {apresentarCom(meta, "ret_mediana", emFoco.ret_mediana, { sinal: true })} · acerto vs
              CDI {apresentarCom(meta, "hit_ratio_cdi", emFoco.hit_ratio_cdi)} · pior trimestre{" "}
              {apresentarCom(meta, "pior_tri", emFoco.pior_tri, { sinal: true })}
              {emFoco.pior_tri_quarter ? ` em ${emFoco.pior_tri_quarter}` : ""} · série desde{" "}
              {inicioDaSerie.get(emFoco.asset_id) ?? "não declarado"}
            </span>
          </p>
        ) : (
          <p className="text-gray-600">
            Passe o cursor ou navegue por teclado até uma célula para ver erro-padrão, mediana,
            acerto contra o CDI e pior trimestre. Clique para abrir o detalhe do par.
          </p>
        )}
      </div>

      {/* detalhe do par */}
      {selecionada && (
        <section className="mt-4 rounded-xl border p-4">
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-base font-bold text-gray-900">
              {selecionada.asset_id} em {selecionada.regime} ·{" "}
              {formatarInteiro(selecionada.n_obs)} observações
            </h2>
            <button
              type="button"
              className="rounded-lg border px-2 py-1 text-xs text-gray-700"
              onClick={() => setSelecionada(null)}
            >
              Fechar o detalhe
            </button>
          </div>
          <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
            {[
              ["Excesso sobre o CDI", apresentarCom(meta, "excesso_cdi", selecionada.excesso_cdi, { sinal: true })],
              ["Retorno médio", apresentarCom(meta, "ret_medio", selecionada.ret_medio, { sinal: true })],
              ["Mediana", apresentarCom(meta, "ret_mediana", selecionada.ret_mediana, { sinal: true })],
              ["Erro-padrão da média", apresentarCom(meta, "erro_padrao_media", selecionada.erro_padrao_media)],
              ["Acerto contra o CDI", apresentarCom(meta, "hit_ratio_cdi", selecionada.hit_ratio_cdi)],
              [
                "Pior trimestre",
                `${apresentarCom(meta, "pior_tri", selecionada.pior_tri, { sinal: true })}${
                  selecionada.pior_tri_quarter ? ` em ${selecionada.pior_tri_quarter}` : ""
                }`,
              ],
              ["Observações", formatarInteiro(selecionada.n_obs)],
              ["Série desde", inicioDaSerie.get(selecionada.asset_id) ?? "não declarado"],
              ["Tabela de origem", tabelaPorRegime.get(selecionada.regime)?.tabela ?? "não declarada"],
            ].map(([rotulo, valor]) => (
              <div key={rotulo} className="flex justify-between gap-3 border-b py-1">
                <dt className="text-gray-600">{rotulo}</dt>
                <dd className="ldc-num text-gray-900">{valor}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-gray-700">
            Os trimestres que compõem esta célula não vêm nesta tag: o exportador publica a célula
            agregada pelo pipeline e declara a omissão nas reduções do meta. Para ver trimestre por
            trimestre, o caminho é o Parquet do pacote, que é a fonte.
          </p>
        </section>
      )}

      {/* rodapé da figura */}
      <div className="ldc-info mt-4 space-y-1 border-t pt-3 text-xs">
        <p>
          Medida: {campo}
          {unidade ? ` em ${unidade}` : ""}. Escala: {escala}, simétrica em ±
          {formatarNumero(extremo, 2)}
          {unidade === "%" ? "%" : unidade ? ` ${unidade}` : ""}.
        </p>
        <p>Unidades declaradas: {notaDeUnidade(meta, [campo, "erro_padrao_media", "hit_ratio_cdi"])}.</p>
        <p>
          Limiares de observações lidos do dado: alerta abaixo de{" "}
          {formatarInteiro(limiares.alerta_abaixo_de)}, supressão abaixo de{" "}
          {formatarInteiro(limiares.supressao_abaixo_de)}.
        </p>
        {excluidos.length > 0 && (
          <p>
            Retirado da figura:{" "}
            {excluidos.map((e) => `${e.asset_id} (${e.motivo})`).join(" · ")}. A linha continua nas
            tabelas de números.
          </p>
        )}
        <p>
          Erro-padrão por célula no tooltip e no painel acima. Ler a ordem do topo sem ler o
          erro-padrão é ler ruído.
        </p>
      </div>
    </div>
  );
}
