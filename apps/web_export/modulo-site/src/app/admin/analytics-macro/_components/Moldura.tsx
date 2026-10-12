/**
 * A moldura das quatro telas: shell do admin, escopo `.ferramenta`, faixa do gate, cabeçalho com
 * a pergunta, atalhos e rodapé de procedência — nessa ordem, em toda tela.
 *
 * Existe para que a conformidade com o `DESIGN.md` e com RF-W001/W002/W035 seja por construção e
 * não por disciplina: quem escrever a quinta tela herda a faixa do gate, o rodapé com hash e a
 * pergunta no topo sem precisar lembrar. É o papel que o `arquitetura` §6.3 dá ao registry
 * ("gate por omissão, não por disciplina do programador"), com o shell sendo o `AdminLayout` que
 * já existe.
 *
 * `<div className="ferramenta ldc-work">` é o que resolve tipografia, neutro tintado e
 * `tabular-nums` de uma vez — os tokens são redefinidos nesse escopo no `src/app/globals.css`.
 * Fora dele, a tela nasceria com a escala fluida do site público.
 *
 * Não é um card: é um container. Nada aqui abre borda ao redor do conteúdo, para que os blocos
 * internos possam ter a sua sem virar card dentro de card (banido no `DESIGN.md`).
 *
 * A pergunta vem da view (`pergunta`, campo do envelope), não de uma string daqui: é o
 * exportador que declara a que pergunta cada tela responde (P7).
 */

import Link from "next/link";
import type { ReactNode } from "react";
import AdminLayout from "@/app/admin/components/AdminLayout";
import { PageHeader } from "@/app/admin/wealth-planning/components/charts";

import { FaixaDeEstado } from "./FaixaDeEstado";
import { RodapeProcedencia } from "./RodapeProcedencia";
import type { ErroDeDataset, NomeDeView } from "../_lib/dataset";
import type { GateDaView, MetaWeb, PonteiroCurrent } from "../_lib/schema";

export const TELAS = [
  { href: "/admin/analytics-macro", rotulo: "Visão geral", tela: "T-01" },
  { href: "/admin/analytics-macro/heatmap", rotulo: "Heatmap regime × ativo", tela: "T-02" },
  { href: "/admin/analytics-macro/momentos", rotulo: "Momentos semelhantes", tela: "T-03" },
  { href: "/admin/analytics-macro/dados", rotulo: "Dados e limitações", tela: "T-07" },
] as const;

function Atalhos({ atual }: { atual: string }) {
  return (
    <nav aria-label="Telas do módulo" className="mb-5 flex flex-wrap gap-2">
      {TELAS.map((t) => {
        const ativa = t.href === atual;
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={ativa ? "page" : undefined}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
              ativa
                ? "border-gray-900 bg-gray-900 font-semibold text-white"
                : "border-gray-300 bg-white text-gray-900 hover:bg-gray-50"
            }`}
          >
            {t.rotulo}
          </Link>
        );
      })}
    </nav>
  );
}

export function Moldura({
  atual,
  titulo,
  pergunta,
  gate,
  meta,
  ponteiro,
  views,
  acao,
  children,
}: {
  atual: string;
  titulo: string;
  /** A pergunta que a tela responde, em uma frase, vinda da view (RF-W035). */
  pergunta: string;
  /** O gate da VIEW lida. Igual ao do meta por contrato; a view é a fonte mais próxima do dado. */
  gate: GateDaView | null;
  meta: MetaWeb;
  ponteiro: PonteiroCurrent;
  views: readonly NomeDeView[];
  acao?: ReactNode;
  children: ReactNode;
}) {
  return (
    <AdminLayout>
      <div className="ferramenta ldc-work">
        <FaixaDeEstado gate={gate} />
        <Atalhos atual={atual} />
        <PageHeader
          eyebrow="LDC Analytics · Alocação Macro"
          title={titulo}
          sub={pergunta}
          action={acao}
        />
        {children}
        <RodapeProcedencia meta={meta} ponteiro={ponteiro} views={views} />
      </div>
    </AdminLayout>
  );
}

/**
 * O estado de erro: visível e nomeado, nunca tela em branco (RF-W049). A faixa do gate aparece no
 * estado mais restritivo, porque sem meta não há como afirmar o contrário.
 */
export function MolduraDeErro({
  atual,
  titulo,
  erro,
}: {
  atual: string;
  titulo: string;
  erro: ErroDeDataset | Error;
}) {
  const codigo = "codigo" in erro ? (erro as ErroDeDataset).codigo : "FALHA_INESPERADA";
  const detalhe = "detalhe" in erro ? (erro as ErroDeDataset).detalhe : "";
  const ausente = codigo === "DATASET_AUSENTE";
  return (
    <AdminLayout>
      <div className="ferramenta ldc-work">
        <FaixaDeEstado gate={null} />
        <Atalhos atual={atual} />
        <PageHeader
          eyebrow="LDC Analytics · Alocação Macro"
          title={titulo}
          sub="Esta tela não foi desenhada porque o dataset não pôde ser lido."
        />
        <div className="ldc-sup-alerta rounded-xl p-4">
          <p className="text-lg font-bold leading-tight">
            {ausente ? "Dataset não instalado" : "O dataset não passou na conferência"}
          </p>
          <p className="mt-1 text-sm text-gray-900">{erro.message}</p>
          {detalhe && <p className="mt-1 text-xs text-gray-700">{detalhe}</p>}
          <p className="mt-2 text-xs text-gray-700">
            Código: {codigo}.{" "}
            {ausente
              ? "Rode o exportador do projeto de dados com destino na pasta analytics-macro deste app e recarregue. Nada é editado à mão nessa pasta."
              : "Nenhum número é mostrado enquanto a conferência não passar: divergência de hash ou de tag é erro de tela, não aviso de rodapé."}
          </p>
        </div>
      </div>
    </AdminLayout>
  );
}
