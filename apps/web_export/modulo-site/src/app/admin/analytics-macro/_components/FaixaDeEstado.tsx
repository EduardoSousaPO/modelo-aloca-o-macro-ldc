/**
 * A faixa do gate (RF-W002 / CA-090), lida do `meta.json`.
 *
 * Fica no TOPO de toda tela enquanto `gate.especificacao_congelada` for `false`, e **não é
 * dispensável por clique** — não existe botão de fechar, nem estado, nem `localStorage`. Quando
 * o ADR-001 for aceito e o exportador publicar `especificacao_congelada: true`, a faixa some sem
 * alteração de código.
 *
 * O texto da marca é o que o **exportador** escreveu (`gate.marca`, "a faixa fixa do topo de
 * toda tela"), com uma frase fixa da tela ao lado. Reescrever a marca aqui criaria duas versões
 * da mesma afirmação, e a do dado é a que o pipeline sabe defender.
 *
 * FALHA FECHADA: a prop é `GateDaView` ou `null`. `null` (meta ausente, JSON inválido, leitura
 * que levantou) renderiza a faixa no estado mais restritivo. O caminho em que a faixa NÃO
 * aparece é o único que exige dois booleanos explícitos vindos do disco.
 *
 * Design: `.ldc-sup-alerta` do `globals.css` — superfície para problema, texto para ação
 * (`DESIGN.md`, "Importante ≠ problema"). O título vai a 19px bold porque `#c0584f` sobre
 * `#faf2f1` mede 4,05:1: passa AA como texto grande (≥18,66px bold, limite 3:1) e não passaria a
 * 15px. O corpo é navy sobre a mesma superfície (11,9:1). Medições em
 * `src/app/globals.css.patch.md`.
 */

import type { GateDaView } from "../_lib/schema";
import { estadoDoGate } from "../_lib/dataset";

export function FaixaDeEstado({ gate }: { gate: GateDaView | null }) {
  const estado = estadoDoGate(gate);

  if (!estado.fechado) {
    return (
      <div className="ldc-sup-lime mb-4 rounded-xl px-4 py-3" role="note">
        <p className="text-sm font-semibold">
          Especificação congelada. O pipeline marcou este dataset como publicável.
        </p>
        <p className="mt-1 text-xs">ADR-001: {estado.status_adr_001}. {estado.veredito}</p>
      </div>
    );
  }

  return (
    <div className="ldc-sup-alerta mb-4 rounded-xl px-4 py-3" role="note" aria-label="Estado do dataset">
      <p className="text-lg font-bold leading-tight">
        {estado.marca || "Material de discussão: especificação não congelada"}
      </p>
      <p className="mt-1 text-sm leading-relaxed text-gray-900">
        Nenhum número desta tela é insumo de decisão de alocação. ADR-001 em{" "}
        {estado.status_adr_001}.
      </p>
      {estado.veredito && <p className="mt-1.5 text-xs text-gray-700">{estado.veredito}</p>}
      <p className="mt-1.5 text-xs text-gray-700">
        A faixa sai do ar quando o pipeline publicar a especificação congelada, sem mudança de
        código. O conteúdo é descritivo: responde em que quadrante cada trimestre do histórico caiu
        e, em momentos parecidos, como cada classe rendeu, com quantas observações.
      </p>
    </div>
  );
}

/** A versão magra, para cabeçalho de tabela e de figura: o mesmo estado em uma linha. */
export function SeloDeEstado({ gate }: { gate: GateDaView | null }) {
  const estado = estadoDoGate(gate);
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${
        estado.fechado ? "ldc-sup-alerta" : "ldc-sup-lime"
      }`}
    >
      {estado.fechado ? "espec. não congelada" : "espec. congelada"}
    </span>
  );
}
