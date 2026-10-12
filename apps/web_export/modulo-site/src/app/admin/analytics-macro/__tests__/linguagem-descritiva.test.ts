/**
 * NADA PREDITIVO EM NENHUM TEXTO — a guarda de linguagem do módulo (Anti-SPEC §10.2.10).
 *
 * É a porta do lado do site da mesma guarda que roda no desenho das figuras do pipeline
 * (`apps/analysis/_linguagem.py`). As duas listas e as três janelas de negação são as mesmas,
 * portadas: forma assertiva é proibida por inteiro, com a exceção medida da frase citada dentro
 * de uma negação curta; substantivo preditivo é permitido só sob negação, porque é exatamente
 * dizendo o que o material não é que o material se protege.
 *
 * O teste varre TODO arquivo `.ts`/`.tsx` do módulo, inclusive comentário e docblock: texto de
 * comentário vira texto de tela com um copiar e colar, e a guarda do pipeline também varre o
 * texto inteiro do artefato.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ_DO_MODULO = join(AQUI, "..");

const FORMAS_PREDITIVAS_PROIBIDAS = [
  "vai render",
  "vai subir",
  "vai cair",
  "vai performar",
  "vai entregar",
  "deve render",
  "deve subir",
  "deve cair",
  "deve performar",
  "tende a render",
  "tende a subir",
  "tende a cair",
  "retorno esperado",
  "esperado para",
  "projetamos",
  "prevemos",
  "esperamos",
  "espera-se",
  "estimamos que",
  "recomendamos",
  "recomendação de alocação:",
  "sugerimos",
  "melhor aposta",
  "aposta para",
  "é o melhor",
  "e o melhor",
] as const;

const SUBSTANTIVOS_SOB_NEGACAO = [
  "previsao",
  "previsão",
  "projecao",
  "projeção",
  "extrapolacao",
  "extrapolação",
  "backtest",
  "recomendacao",
  "recomendação",
  "quanto vai render",
] as const;

const MARCADORES_DE_NEGACAO = [
  "não",
  "nao",
  "nunca",
  "nenhum",
  "nenhuma",
  "nada",
  "nem ",
  "sem ",
  "≠",
  "proib",
  "fora de escopo",
  "fora desta",
  "fora deste",
  "jamais",
] as const;

const JANELA_ANTES = 160;
const JANELA_DEPOIS = 60;
const JANELA_ASSERTIVA = 40;

function negadoNoContexto(minusculo: string, posicao: number, termo: string): boolean {
  const antes = minusculo.slice(Math.max(0, posicao - JANELA_ANTES), posicao);
  const depois = minusculo.slice(posicao + termo.length, posicao + termo.length + JANELA_DEPOIS);
  return MARCADORES_DE_NEGACAO.some((m) => antes.includes(m) || depois.includes(m));
}

export function termosPreditivosEm(texto: string): string[] {
  const minusculo = texto.toLowerCase();
  const achados: string[] = [];

  for (const forma of FORMAS_PREDITIVAS_PROIBIDAS) {
    let posicao = minusculo.indexOf(forma);
    while (posicao !== -1) {
      const antes = minusculo.slice(Math.max(0, posicao - JANELA_ASSERTIVA), posicao);
      if (!MARCADORES_DE_NEGACAO.some((m) => antes.includes(m))) {
        achados.push(forma);
        break;
      }
      posicao = minusculo.indexOf(forma, posicao + forma.length);
    }
  }

  for (const termo of SUBSTANTIVOS_SOB_NEGACAO) {
    let posicao = minusculo.indexOf(termo);
    while (posicao !== -1) {
      if (!negadoNoContexto(minusculo, posicao, termo)) {
        achados.push(termo);
        break;
      }
      posicao = minusculo.indexOf(termo, posicao + termo.length);
    }
  }

  return achados;
}

/**
 * `__tests__` fica FORA da varredura, e de propósito: este arquivo precisa escrever
 * "vai render" e "recomendamos" como caso de teste, e o alvo da guarda é o texto que chega ao
 * leitor, não o texto que prova a guarda. É o mesmo recorte do lado Python, onde a guarda roda
 * sobre os textos do artefato, não sobre o `tests/`.
 */
const PASTAS_FORA_DA_VARREDURA = new Set(["__tests__"]);

function arquivosDoModulo(dir: string, acumulado: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      if (PASTAS_FORA_DA_VARREDURA.has(nome)) continue;
      arquivosDoModulo(caminho, acumulado);
    } else if (/\.tsx?$/.test(nome)) {
      acumulado.push(caminho);
    }
  }
  return acumulado;
}

describe("linguagem descritiva", () => {
  const arquivos = arquivosDoModulo(RAIZ_DO_MODULO);

  it("encontra os arquivos do módulo", () => {
    expect(arquivos.length).toBeGreaterThan(8);
  });

  it.each(arquivos.map((a) => [a.slice(RAIZ_DO_MODULO.length + 1), a] as const))(
    "%s não afirma nada preditivo",
    (_rotulo, caminho) => {
      const texto = readFileSync(caminho, "utf8");
      expect(termosPreditivosEm(texto)).toEqual([]);
    },
  );

  it("a guarda reprova a forma assertiva solta", () => {
    expect(termosPreditivosEm("No próximo trimestre o IBOV vai render +5%")).toContain("vai render");
    expect(termosPreditivosEm("Retorno esperado de 8% ao ano")).toContain("retorno esperado");
    expect(termosPreditivosEm("Recomendamos aumentar o internacional")).toContain("recomendamos");
  });

  it("a guarda absolve a negação, que é como o material se protege", () => {
    expect(termosPreditivosEm('Nada aqui é projeção, e nunca "quanto vai render".')).toEqual([]);
    expect(termosPreditivosEm("Este entregável não é previsão nem backtest.")).toEqual([]);
    expect(
      termosPreditivosEm("A recomendação é do Comitê, e nenhuma linha desta tela a substitui."),
    ).toEqual([]);
  });

  it("a guarda não absolve um parágrafo que nega no começo e afirma no fim", () => {
    const texto =
      "Isto não é previsão. " +
      "Segue um parágrafo longo o bastante para a janela curta da forma assertiva não alcançar o começo, " +
      "com bastante texto de enchimento para passar dos quarenta caracteres exigidos pela janela, " +
      "e no final o IBOV vai subir.";
    expect(termosPreditivosEm(texto)).toContain("vai subir");
  });
});
