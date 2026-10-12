// @vitest-environment jsdom

/**
 * A FAIXA DO GATE — renderizada, não dispensável, e fechada por omissão.
 *
 * Quatro propriedades, cada uma com um teste:
 *   1. com `especificacao_congelada: false` a faixa aparece, repete a marca que o EXPORTADOR
 *      escreveu e diz que nenhum número da tela é insumo de decisão (RF-W002 / CA-090);
 *   2. não existe como fechar: nenhum botão, nenhum controle. Faixa dispensável por clique é
 *      faixa que ninguém vê na segunda visita;
 *   3. sem gate (meta ausente ou ilegível), a faixa aparece no estado MAIS restritivo — é o
 *      caminho de falha fechada: a única maneira de a faixa sair do ar são dois booleanos
 *      explícitos vindos do disco;
 *   4. um dos dois booleanos basta para fechar.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { FaixaDeEstado, SeloDeEstado } from "../_components/FaixaDeEstado";
import { estadoDoGate } from "../_lib/dataset";
import { gate } from "./fixtura";

describe("faixa de estado", () => {
  it("aparece com a especificação não congelada e repete a marca do exportador", () => {
    render(<FaixaDeEstado gate={gate()} />);
    // a marca do exportador aparece no título; o veredito dele repete o mesmo aviso no corpo
    expect(screen.getAllByText(/MATERIAL DE DISCUSSAO/i).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Nenhum número desta tela é insumo de decisão de alocação/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/PROPOSTA/).length).toBeGreaterThan(0);
  });

  it("não oferece como dispensar: nenhum controle dentro da faixa", () => {
    const { container } = render(<FaixaDeEstado gate={gate()} />);
    expect(container.querySelectorAll("button").length).toBe(0);
    expect(container.querySelectorAll("input").length).toBe(0);
    expect(container.querySelectorAll("a").length).toBe(0);
  });

  it("falha fechada: sem gate, a faixa sai no estado mais restritivo", () => {
    render(<FaixaDeEstado gate={null} />);
    expect(screen.getAllByText(/MATERIAL DE DISCUSSAO/i).length).toBeGreaterThan(0);
    expect(estadoDoGate(null).fechado).toBe(true);
    expect(estadoDoGate(undefined).fechado).toBe(true);
    expect(estadoDoGate(null).status_adr_001).toBe("DESCONHECIDO");
  });

  it("some sem mudança de código quando o pipeline congelar e liberar", () => {
    render(
      <FaixaDeEstado
        gate={gate({
          especificacao_congelada: true,
          publicavel: true,
          status_adr_001: "ACEITA",
          marca: "",
          veredito_publicacao: "ADR-001 aceito: o dataset esta publicavel pelo fluxo formal.",
        })}
      />,
    );
    expect(screen.queryByText(/MATERIAL DE DISCUSSAO/i)).toBeNull();
    expect(screen.getByText(/Especificação congelada/i)).toBeInTheDocument();
  });

  it("um dos dois booleanos basta para fechar o gate", () => {
    expect(estadoDoGate(gate({ especificacao_congelada: true, publicavel: false })).fechado).toBe(true);
    expect(estadoDoGate(gate({ especificacao_congelada: false, publicavel: true })).fechado).toBe(true);
    expect(estadoDoGate(gate({ especificacao_congelada: true, publicavel: true })).fechado).toBe(false);
  });

  it("o selo magro acompanha o mesmo estado", () => {
    const { container } = render(<SeloDeEstado gate={gate()} />);
    expect(container.textContent).toContain("espec. não congelada");
  });
});
