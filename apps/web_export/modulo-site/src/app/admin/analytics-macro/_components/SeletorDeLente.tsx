"use client";

/**
 * Os filtros do módulo — e o estado deles MORA NA URL (RF-W003).
 *
 * É o requisito mais barato e mais útil do PRD: a URL de uma tela filtrada reproduz a tela,
 * e é isso que substitui o print no WhatsApp. Então nenhum filtro guarda estado em `useState`:
 * cada mudança reescreve a query e o Server Component re-renderiza com o novo recorte. O
 * efeito colateral bom é que voltar no histórico volta o recorte.
 *
 * Por que `<select>` nativo e não o `Select` do shadcn/Radix (que existe no app): o filtro é
 * de recorte, não de formulário; o nativo já traz teclado, leitor de tela e o seletor do
 * sistema no celular, sem portal nem JS de posicionamento. Onde o app usa Radix é em CRUD, e
 * esta tela não tem CRUD. Zero dependência nova nos dois casos.
 *
 * Acessibilidade: todo controle tem `<label>` associado por `htmlFor`; opção indisponível
 * aparece desabilitada COM o motivo no próprio rótulo, nunca removida em silêncio (regra 2 do
 * registry: view ausente desabilita com o motivo).
 */

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export interface Opcao {
  valor: string;
  rotulo: string;
  desabilitada?: boolean;
  motivo?: string;
}

export interface CampoDeFiltro {
  chave: string;
  rotulo: string;
  valor: string;
  opcoes: Opcao[];
  /** Selo de unidade ou nota curta ao lado do rótulo. */
  nota?: string;
}

export interface AlternadorDeFiltro {
  chave: string;
  rotulo: string;
  ligado: boolean;
  nota?: string;
}

const CLASSE_DO_CAMPO =
  "h-9 rounded-lg border bg-white px-2 text-sm text-gray-900 border-gray-300 " +
  "focus:outline-none focus:ring-2 focus:ring-offset-1";

export function SeletorDeLente({
  campos,
  alternadores = [],
  caixas = [],
  rotuloDasCaixas,
}: {
  campos: readonly CampoDeFiltro[];
  alternadores?: readonly AlternadorDeFiltro[];
  /** Grupo de caixas de seleção multivalorado (ex.: classes de ativo). */
  caixas?: readonly { chave: string; rotulo: string; marcada: boolean }[];
  rotuloDasCaixas?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const aplicar = useCallback(
    (mudancas: Record<string, string | null>) => {
      const sp = new URLSearchParams(searchParams?.toString() ?? "");
      for (const [chave, valor] of Object.entries(mudancas)) {
        if (valor === null || valor === "") sp.delete(chave);
        else sp.set(chave, valor);
      }
      const consulta = sp.toString();
      router.replace(consulta ? `${pathname}?${consulta}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  return (
    <div className="mb-4 flex flex-wrap items-end gap-x-5 gap-y-3">
      {campos.map((campo) => (
        <div key={campo.chave} className="flex flex-col gap-1">
          <label
            htmlFor={`filtro-${campo.chave}`}
            className="text-xs font-semibold uppercase tracking-[0.08em] text-gray-600"
          >
            {campo.rotulo}
            {campo.nota ? <span className="ml-1 font-normal normal-case">({campo.nota})</span> : null}
          </label>
          <select
            id={`filtro-${campo.chave}`}
            className={CLASSE_DO_CAMPO}
            value={campo.valor}
            onChange={(e) => aplicar({ [campo.chave]: e.target.value })}
          >
            {campo.opcoes.map((o) => (
              <option key={o.valor} value={o.valor} disabled={o.desabilitada}>
                {o.desabilitada && o.motivo ? `${o.rotulo} — indisponível: ${o.motivo}` : o.rotulo}
              </option>
            ))}
          </select>
        </div>
      ))}

      {alternadores.map((a) => (
        <div key={a.chave} className="flex items-center gap-2 pb-1.5">
          <input
            id={`filtro-${a.chave}`}
            type="checkbox"
            className="h-4 w-4 rounded border-gray-300"
            checked={a.ligado}
            onChange={(e) => aplicar({ [a.chave]: e.target.checked ? "1" : "0" })}
          />
          <label htmlFor={`filtro-${a.chave}`} className="text-sm text-gray-900">
            {a.rotulo}
            {a.nota ? <span className="ml-1 text-xs text-gray-600">{a.nota}</span> : null}
          </label>
        </div>
      ))}

      {caixas.length > 0 && (
        <fieldset className="flex flex-col gap-1">
          <legend className="text-xs font-semibold uppercase tracking-[0.08em] text-gray-600">
            {rotuloDasCaixas ?? "Classe de ativo"}
          </legend>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            {caixas.map((c) => (
              <div key={c.chave} className="flex items-center gap-1.5">
                <input
                  id={`classe-${c.chave}`}
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300"
                  checked={c.marcada}
                  onChange={(e) => {
                    const atuais = new Set(
                      caixas.filter((x) => x.marcada).map((x) => x.chave),
                    );
                    if (e.target.checked) atuais.add(c.chave);
                    else atuais.delete(c.chave);
                    // Nenhuma classe marcada = todas: a tela nunca fica vazia por acidente.
                    const todas = atuais.size === 0 || atuais.size === caixas.length;
                    aplicar({ classes: todas ? null : Array.from(atuais).sort().join(",") });
                  }}
                />
                <label htmlFor={`classe-${c.chave}`} className="text-sm text-gray-900">
                  {c.rotulo}
                </label>
              </div>
            ))}
          </div>
        </fieldset>
      )}
    </div>
  );
}
