/**
 * Unidade, precisão e escala — o único lugar do front onde número vira texto.
 *
 * É o espelho, do lado da tela, do contrato de `packages/shared/schemas/web_views.py`. Desde o
 * acerto de 2026-10-11 a apresentação é **leitura de tabela**, não regra escrita aqui:
 *
 *   | o que | de onde vem |
 *   |---|---|
 *   | unidade **nativa** do campo | `meta.unidade_por_campo` |
 *   | casas do valor no JSON | `meta.casas_por_unidade` |
 *   | unidade **apresentada** | `meta.unidade_de_apresentacao` |
 *   | **fator** da conversão (`fracao → %` = 100) | `meta.fator_de_apresentacao` |
 *   | casas na tela | `meta.casas_de_apresentacao` |
 *   | rótulo tipográfico (`%`, `p.p.`) | aqui (`ROTULO`) — é texto de interface, não unidade |
 *
 * O exportador continua sem converter valor (D-W4): o JSON chega em fração e a tela multiplica
 * pelo fator que o `meta` declara. A divergência de RF-W014 que este arquivo carregava — uma
 * tabela `APRESENTACAO` com o número 100 escrito no front — **foi fechada**: o 100 agora está
 * declarado de um lado só, e o teste prova que `0,0504` sai `+5,04` lendo o `meta`.
 *
 * Campo que o `meta` não declarar sai **sem conversão** (fator 1), nunca com um fator adivinhado.
 */

import type { MetaWeb } from "./schema";

/** As unidades nativas que o exportador declara (`web_views.py`). */
export const UNIDADE = {
  fracao: "fracao",
  percentual: "percentual_a_a",
  indice: "indice",
  adimensional: "adimensional",
  contagem: "contagem",
  pontosPercentuais: "pontos_percentuais",
} as const;

/**
 * O rótulo tipográfico de cada unidade **apresentada**. É o que sobrou do lado da tela depois do
 * acerto: texto de interface. Nenhum fator e nenhuma casa decimal aqui — esses vêm do `meta`.
 * Unidade que o `meta` declarar e esta tabela não conhecer sai sem rótulo, nunca com um errado.
 */
export const ROTULO: Record<string, string> = {
  percentual: "%",
  pontos_percentuais: "p.p.",
  percentual_a_a: "% a.a.",
  indice: "índice",
  adimensional: "",
  contagem: "",
  fracao: "fração",
};

const CASAS_SEM_DECLARACAO = 3;

/** A unidade NATIVA de um campo, lida do `meta`. `null` quando o campo não é numérico. */
export function unidadeNativa(meta: MetaWeb, campo: string): string | null {
  return meta.unidade_por_campo?.[campo] ?? null;
}

/** A unidade APRESENTADA de um campo, lida do `meta`. Sem declaração, cai na nativa. */
export function unidadeApresentada(meta: MetaWeb, campo: string): string | null {
  return meta.unidade_de_apresentacao?.[campo] ?? unidadeNativa(meta, campo);
}

/** O fator da conversão, lido do `meta`. Sem declaração, **1**: nunca um fator adivinhado. */
export function fatorDeApresentacao(meta: MetaWeb, campo: string): number {
  const fator = meta.fator_de_apresentacao?.[campo];
  return typeof fator === "number" && Number.isFinite(fator) ? fator : 1;
}

/** As casas na tela, lidas do `meta`. Sem declaração, 3 — e 0 para contagem. */
export function casasDeApresentacao(meta: MetaWeb, campo: string): number {
  const casas = meta.casas_de_apresentacao?.[campo];
  if (typeof casas === "number" && Number.isFinite(casas)) return casas;
  return unidadeNativa(meta, campo) === UNIDADE.contagem ? 0 : CASAS_SEM_DECLARACAO;
}

/** Rótulo da unidade apresentada, para o selo ao lado de todo eixo e cabeçalho. */
export function rotuloDeUnidade(meta: MetaWeb, campo: string): string {
  const apresentada = unidadeApresentada(meta, campo);
  if (!apresentada) return "";
  return ROTULO[apresentada] ?? "";
}

/** A frase que o rodapé imprime, para o leitor saber o que foi convertido e por qual fator. */
export function notaDeUnidade(meta: MetaWeb, campos: readonly string[]): string {
  const partes: string[] = [];
  for (const campo of campos) {
    const nativa = unidadeNativa(meta, campo);
    if (!nativa) continue;
    const casasNativas = meta.casas_por_unidade?.[nativa];
    const fator = fatorDeApresentacao(meta, campo);
    partes.push(
      `${campo}: nativo em ${nativa}` +
        (casasNativas !== undefined ? ` com ${casasNativas} casas` : "") +
        (fator === 1
          ? ", apresentado como está"
          : `, apresentado em ${rotuloDeUnidade(meta, campo) || unidadeApresentada(meta, campo)} (fator ${fator}, declarado no meta)`),
    );
  }
  return partes.join(" · ");
}

function emPtBr(valor: number, casas: number, sinal: boolean): string {
  const texto = valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
  return sinal && valor > 0 ? `+${texto}` : texto;
}

/**
 * O valor de um campo, pronto para a tela: fator e casas vindos da unidade declarada.
 * Devolve também o rótulo da unidade, para número e unidade nunca se separarem.
 */
export function apresentar(
  meta: MetaWeb,
  campo: string,
  valor: number | null | undefined,
  opcoes: { sinal?: boolean } = {},
): { texto: string; unidade: string; ausente: boolean } {
  const unidade = rotuloDeUnidade(meta, campo);
  if (valor === null || valor === undefined || Number.isNaN(valor)) {
    return { texto: "–", unidade, ausente: true };
  }
  const texto = emPtBr(
    valor * fatorDeApresentacao(meta, campo),
    casasDeApresentacao(meta, campo),
    opcoes.sinal ?? false,
  );
  return { texto, unidade, ausente: false };
}

/** `apresentar` colado: texto e unidade numa string. */
export function apresentarCom(
  meta: MetaWeb,
  campo: string,
  valor: number | null | undefined,
  opcoes: { sinal?: boolean } = {},
): string {
  const { texto, unidade } = apresentar(meta, campo, valor, opcoes);
  if (!unidade) return texto;
  return unidade === "%" ? `${texto}%` : `${texto} ${unidade}`;
}

/** O valor na escala de APRESENTAÇÃO, para a geometria do desenho (eixo, barra, passo). */
export function valorApresentado(meta: MetaWeb, campo: string, valor: number): number {
  return valor * fatorDeApresentacao(meta, campo);
}

/** Inteiro em pt-BR (contagens, `n`, nº de trimestres). */
export function formatarInteiro(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "–";
  return Math.round(valor).toLocaleString("pt-BR");
}

/** Número solto, sem campo declarado (percentual de nulos, bytes, contagem de arquivo). */
export function formatarNumero(valor: number | null | undefined, casas = 2, sinal = false): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "–";
  return emPtBr(valor, casas, sinal);
}

/** Os 12 primeiros caracteres do hash — a convenção do pacote do Comitê. */
export function hashCurto(hash: string | null | undefined): string {
  if (!hash) return "–";
  return hash.slice(0, 12);
}

/* ────────────────────────── a escala divergente ────────────────────────── */

/**
 * A rampa divergente proposta em `ldc-analytics-identidade-v2.md` §9.4, com UMA correção de
 * contraste medida aqui (ver `src/app/globals.css.patch.md`):
 *
 *   - neutro (zero) = `#f0f2f3`, o grid do `DESIGN.md`;
 *   - lado NEGATIVO = arco do alerta, 4 passos;
 *   - lado POSITIVO = arco do navy, 4 passos;
 *   - lime FORA da escala: por `DESIGN.md`, lime é ação e "no trilho", não estado — aqui ele
 *     marca a coluna do recorte corrente, nunca o sinal do número;
 *   - célula suprimida = `#eceef0`, o track, SEM cor divergente e com hachura — perder o canal
 *     de magnitude é o ponto de CA-109.
 *
 * A correção: `#c0584f` cheio **não** alcança 4,5:1 com nenhuma das duas tintas da casa
 * (medido: 3,1:1 com navy, 4,4:1 com `#fcfdfd`), e a célula carrega texto de 8,5 a 10,5px. O 3º
 * passo do arco negativo é `#a94d46` — que já existe no `globals.css` como o hover de
 * `.ldc-btn-alerta` — e alcança 5,3:1 com `#fcfdfd`. O hex da marca segue sendo a âncora do
 * arco: aparece na legenda e na borda, onde não há texto por cima.
 *
 * O exportador **não manda cor** (D-ai, 2026-10-11): mandava `cor_hex`, o hex da figura
 * matplotlib derivado da paleta placeholder da skill `dataviz`, que a tela já ignorava. Cor é
 * decisão de apresentação e vive aqui; do dado vem o **eixo** da escala (`eixos_de_cor`) e os
 * canais sem cor. Enquanto esta rampa e a da figura do PDF não convergirem, a tela usa a da casa
 * e o PDF a dele — a convergência é o adendo ao `DESIGN.md` proposto no patch.
 */
export const ESCALA = {
  neutro: "#f0f2f3",
  suprimido: "#eceef0",
  /** Do mais fraco ao mais forte. */
  negativo: ["#f4e1df", "#e8b4af", "#a94d46", "#8c3b34"],
  positivo: ["#dfe3e8", "#9aa6b4", "#5a6a7e", "#262d3d"],
  /** Âncoras do arco, para legenda e borda. Nunca fundo de texto. */
  ancoraNegativa: "#c0584f",
  ancoraPositiva: "#262d3d",
  hachura: "#cfd4d6",
  tintaClara: "#fcfdfd",
  tintaEscura: "#262d3d",
  tintaSuprimida: "#43585a",
} as const;

export const PASSOS_POR_LADO = ESCALA.negativo.length;

/**
 * Índice do passo (1..4) de um valor, com a escala SIMÉTRICA em ±extremo.
 * Simetria é obrigatória: sem ela o neutro do meio deixa de significar "empatou" (ADR-002 §3).
 */
export function passoDaEscala(valor: number, extremo: number): number {
  if (extremo <= 0) return 1;
  const fracao = Math.min(1, Math.abs(valor) / extremo);
  return Math.max(1, Math.min(PASSOS_POR_LADO, Math.ceil(fracao * PASSOS_POR_LADO)));
}

export interface PinturaDaCelula {
  fundo: string;
  tinta: string;
  hachurada: boolean;
  tracejada: boolean;
}

/**
 * A pintura de uma célula, com os TRÊS estados de confiança em DOIS canais cada:
 *   - acima do limiar de alerta: cor + número;
 *   - entre os dois limiares: cor + borda tracejada + asterisco;
 *   - abaixo do limiar de supressão: SEM cor divergente + hachura + número rebaixado a prelim.
 * Cor nunca é o único canal.
 */
export function pintarCelula(entrada: {
  valor: number | null;
  extremo: number;
  alerta: boolean;
  suprimida: boolean;
}): PinturaDaCelula {
  const { valor, extremo, alerta, suprimida } = entrada;
  if (suprimida || valor === null) {
    return {
      fundo: ESCALA.suprimido,
      tinta: ESCALA.tintaSuprimida,
      hachurada: true,
      tracejada: false,
    };
  }
  const passo = passoDaEscala(valor, extremo);
  const arco = valor >= 0 ? ESCALA.positivo : ESCALA.negativo;
  const fundo = valor === 0 ? ESCALA.neutro : arco[passo - 1];
  const tinta = passo >= 3 && valor !== 0 ? ESCALA.tintaClara : ESCALA.tintaEscura;
  return { fundo, tinta, hachurada: false, tracejada: alerta };
}

/**
 * O extremo da escala a partir dos valores da tela. **Última opção**: só para a view que não
 * declara eixo de cor (o ranking em T+1 de T-01 e T-03). Para o heatmap use
 * `extremoDeclarado`, que lê o eixo que o exportador publica.
 *
 * Sempre sobre TODAS as células da vista, nunca sobre o recorte filtrado: extremo que dependesse
 * do filtro repintaria as outras classes quando alguém marcasse uma, e duas leituras da mesma tag
 * deixariam de ser comparáveis. É extensão de eixo, não estatística: nenhum valor é combinado
 * com outro.
 */
export function extremoSimetrico(valores: readonly (number | null)[]): number {
  let extremo = 0;
  for (const v of valores) {
    if (v === null || Number.isNaN(v)) continue;
    const a = Math.abs(v);
    if (a > extremo) extremo = a;
  }
  return extremo;
}

/** O eixo de cor que a view do heatmap declara, como `EixoDeCorDaVista` do `schema.d.ts`. */
export interface EixoDeCorDeclarado {
  vista: string;
  campo: string;
  extremo_simetrico: number | null;
}

/**
 * O extremo da escala **lido do dado**, na escala de apresentação (RF-W014 pelo fator do `meta`).
 *
 * Desde 2026-10-11 o exportador publica `heatmap_regime_ativo.eixos_de_cor`: `±max(|valor|)` por
 * `(vista, campo)` sobre a vista inteira, em unidade nativa. A tela multiplica pelo fator
 * declarado e usa — em vez de varrer as células a cada requisição, o que deixava o eixo
 * dependente de quem varre. `null` quando a vista não tem valor no campo: aí não há escala, e o
 * desenho cai no passo neutro.
 */
export function extremoDeclarado(
  meta: MetaWeb,
  eixos: readonly EixoDeCorDeclarado[],
  vista: string,
  campo: string,
): number | null {
  const eixo = eixos.find((e) => e.vista === vista && e.campo === campo);
  if (!eixo || eixo.extremo_simetrico === null) return null;
  return Math.abs(eixo.extremo_simetrico) * fatorDeApresentacao(meta, campo);
}
