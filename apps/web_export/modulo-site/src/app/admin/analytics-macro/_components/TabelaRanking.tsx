/**
 * A tabela de ranking — agrupada por FAIXA, nunca por posição (RF-W027).
 *
 * A decisão de desenho que mais importa aqui é o que a tabela NÃO faz: ela não escreve
 * "1º, 2º, 3º". O número vem com `n` e com a barra de erro ao lado, e as linhas entram em faixas
 * cujo critério **vem do dado**: `distinguivel_de_ruido`, que o exportador calcula de
 * `excesso_em_erros_padrao` contra o limiar de 2. O front não decide o que é distinguível
 * (RF-W016: zero cálculo de metodologia no cliente); ele só agrupa pelo que foi declarado e dá
 * nome em português à faixa.
 *
 * Linha com `conclusao_suprimida` sai **sem número**: na tabela a posição da linha é lida como
 * ordem, e um número ali afirmaria o que o `n` não sustenta. Na figura do heatmap a mesma célula
 * mostra o número rebaixado a `prelim.`, porque lá a posição é o cruzamento regime × ativo.
 */

import { CelulaComN } from "./CelulaComN";
import { BarraDeErro, LegendaDaBarraDeErro } from "./BarraDeErro";
import {
  apresentar,
  apresentarCom,
  formatarInteiro,
  rotuloDeUnidade,
  valorApresentado,
} from "../_lib/formato";
import type { MetaWeb } from "../_lib/schema";

/**
 * O recorte comum de `LinhaDeRanking` (T-01) e `LinhaDoRankingT1` (T-03). Estrutural de
 * propósito: as duas views publicam o mesmo núcleo e esta tabela serve as duas sem adaptador.
 */
export interface LinhaDaTabela {
  asset_id: string;
  n_obs: number;
  excesso_cdi: number | null;
  erro_padrao_media: number | null;
  hit_ratio_cdi: number | null;
  alerta_n_baixo: boolean;
  conclusao_suprimida: boolean;
  excesso_em_erros_padrao?: number | null;
  distinguivel_de_ruido?: boolean | null;
}

const FAIXA_SUPRIMIDA = "sem conclusão: observações abaixo do limiar de supressão";
const FAIXA_DISTINGUIVEL = "acima de 2 erros-padrão";
const FAIXA_RUIDO = "dentro de 2 erros-padrão: não distinguível do CDI nesta janela";
const FAIXA_SEM_SEMAFORO = "sem semáforo declarado para esta linha";

function faixaDa(linha: LinhaDaTabela): string {
  if (linha.conclusao_suprimida) return FAIXA_SUPRIMIDA;
  if (linha.distinguivel_de_ruido === true) return FAIXA_DISTINGUIVEL;
  if (linha.distinguivel_de_ruido === false) return FAIXA_RUIDO;
  return FAIXA_SEM_SEMAFORO;
}

function porFaixa(
  linhas: readonly LinhaDaTabela[],
): Array<{ faixa: string; linhas: LinhaDaTabela[] }> {
  const ordem: string[] = [];
  const mapa = new Map<string, LinhaDaTabela[]>();
  for (const l of linhas) {
    const chave = faixaDa(l);
    if (!mapa.has(chave)) {
      mapa.set(chave, []);
      ordem.push(chave);
    }
    mapa.get(chave)!.push(l);
  }
  return ordem.map((faixa) => ({ faixa, linhas: mapa.get(faixa)! }));
}

export interface PropsDaTabelaRanking {
  linhas: readonly LinhaDaTabela[];
  meta: MetaWeb;
  /** Campo exibido como medida. O padrão é o do heatmap e dos rankings: excesso sobre o CDI. */
  campo?: "excesso_cdi";
  /** Extremo do eixo comum da barra, na escala de apresentação. */
  extremo: number;
  /** Os dois limiares de `n`, lidos do dado (`heatmap.limiares_de_n`), nunca digitados aqui. */
  limiares?: { alerta_abaixo_de: number; supressao_abaixo_de: number };
  compacta?: boolean;
  legenda?: boolean;
}

export function TabelaRanking({
  linhas,
  meta,
  campo = "excesso_cdi",
  extremo,
  limiares,
  compacta = false,
  legenda = true,
}: PropsDaTabelaRanking) {
  if (linhas.length === 0) {
    return (
      <p className="text-sm text-gray-600">
        Nenhuma linha nesta combinação. A tag publicada não traz o recorte pedido.
      </p>
    );
  }
  const grupos = porFaixa(linhas);
  const unidade = rotuloDeUnidade(meta, campo);
  const colunas = compacta ? 3 : 5;

  return (
    <div>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          Ranking descritivo por faixa, com observações e erro-padrão em toda linha.
        </caption>
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-[0.08em] text-gray-600">
            <th scope="col" className="py-2 pr-3 font-semibold">
              Ativo
            </th>
            <th scope="col" className="py-2 pr-3 text-right font-semibold">
              Excesso sobre o CDI{unidade ? <span className="font-normal"> ({unidade})</span> : null}
            </th>
            {!compacta && (
              <th scope="col" className="py-2 pr-3 text-right font-semibold">
                Erro-padrão
              </th>
            )}
            {!compacta && (
              <th scope="col" className="py-2 pr-3 text-right font-semibold">
                Acerto vs CDI
              </th>
            )}
            <th scope="col" className="py-2 font-semibold">
              Dispersão
            </th>
          </tr>
        </thead>
        {grupos.map((grupo) => (
          <tbody key={grupo.faixa}>
            <tr>
              <th
                scope="colgroup"
                colSpan={colunas}
                className="pt-3 pb-1 text-left text-xs font-semibold uppercase tracking-[0.08em] text-gray-600"
              >
                Faixa: {grupo.faixa}
              </th>
            </tr>
            {grupo.linhas.map((l) => {
              const medida = apresentar(meta, campo, l[campo], { sinal: true });
              const valorNaEscala =
                l[campo] === null ? null : valorApresentado(meta, campo, l[campo] as number);
              const epNaEscala =
                l.erro_padrao_media === null
                  ? null
                  : valorApresentado(meta, "erro_padrao_media", l.erro_padrao_media);
              const rotulo =
                `${l.asset_id}: ` +
                (l.conclusao_suprimida
                  ? "sem conclusão"
                  : `${medida.texto}${medida.unidade === "%" ? "%" : ` ${medida.unidade}`}`) +
                `, erro-padrão ${apresentarCom(meta, "erro_padrao_media", l.erro_padrao_media)}` +
                `, n igual a ${formatarInteiro(l.n_obs)}`;
              return (
                <tr key={`${grupo.faixa}-${l.asset_id}`} className="ldc-linha border-b align-middle">
                  <th scope="row" className="py-2 pr-3 text-left font-medium text-gray-900">
                    {l.asset_id}
                  </th>
                  <td className="ldc-num py-2 pr-3">
                    <CelulaComN
                      texto={
                        medida.unidade === "%" ? `${medida.texto}%` : `${medida.texto} ${medida.unidade}`
                      }
                      n={l.n_obs}
                      alerta={l.alerta_n_baixo}
                      suprimida={l.conclusao_suprimida}
                    />
                  </td>
                  {!compacta && (
                    <td className="ldc-num py-2 pr-3 text-gray-700">
                      {apresentarCom(meta, "erro_padrao_media", l.erro_padrao_media)}
                    </td>
                  )}
                  {!compacta && (
                    <td className="ldc-num py-2 pr-3 text-gray-700">
                      {l.hit_ratio_cdi === null
                        ? "–"
                        : `${apresentarCom(meta, "hit_ratio_cdi", l.hit_ratio_cdi)} em ${formatarInteiro(l.n_obs)}`}
                    </td>
                  )}
                  <td className="py-2">
                    <BarraDeErro
                      valor={l.conclusao_suprimida ? null : valorNaEscala}
                      erroPadrao={epNaEscala}
                      extremo={extremo}
                      rotulo={rotulo}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        ))}
      </table>
      {legenda && (
        <div className="mt-2 space-y-1">
          <LegendaDaBarraDeErro unidade={unidade} />
          <p className="text-xs text-gray-600">
            O asterisco ao lado do número marca a linha com observações abaixo do limiar de alerta
            {limiares ? ` (n < ${formatarInteiro(limiares.alerta_abaixo_de)})` : ""}. Linha sem
            número é linha abaixo do limiar de supressão
            {limiares ? ` (n < ${formatarInteiro(limiares.supressao_abaixo_de)})` : ""}: o dado
            desta janela não sustenta a leitura. Dentro de uma faixa a ordem é a declarada pelo
            exportador, e não um pódio: as linhas da mesma faixa não se distinguem entre si.
          </p>
        </div>
      )}
    </div>
  );
}
