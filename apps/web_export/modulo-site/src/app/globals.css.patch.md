# Patch proposto para `src/app/globals.css` — a rampa divergente

> **Nada foi editado no CSS do app.** Este arquivo é o trecho exato a acrescentar, com o antes, o
> depois e o porquê, para o Edu aplicar (ou recusar) com uma decisão só. O módulo
> `/admin/analytics-macro` funciona **sem** este patch: a rampa também existe como constante em
> `src/app/admin/analytics-macro/_lib/formato.ts`, que é o que o SVG usa. O patch serve para a
> rampa ter um lugar canônico no design system, do mesmo jeito que `.ldc-alerta` e `.ldc-sup-lime`
> têm — e para a próxima tela não re-inventar a escala.
>
> **Isto é um adendo ao `DESIGN.md` e precisa de assinatura.** O `DESIGN.md` hoje tem *um* acento
> (lime) e *um* alerta, e não tem escala de magnitude com sinal. O heatmap regime × ativo precisa
> de uma, e a saída fácil (lime = positivo) é proibida pela regra escrita: *"Sucesso não ganha
> verde. Lime é acento de ação, não de estado."*

---

## O que acrescentar

**Arquivo:** `src/app/globals.css`
**Onde:** dentro de `@layer base`, no segundo bloco `.ferramenta` — o dos tokens semânticos, o que
hoje termina em `--ldc-linha: #e6e8ea;` (por volta da linha 215). Acrescentar as linhas novas
**depois** de `--ldc-linha`, no mesmo bloco, sem tocar em nada que já está lá.

### Antes

```css
  .ferramenta {
    --ldc-navy: #262d3d;
    --ldc-slate: #577171;
    --ldc-lime: #98ab44;
    --ldc-alerta: #c0584f;
    --ldc-linha: #e6e8ea;
  }
```

### Depois

```css
  .ferramenta {
    --ldc-navy: #262d3d;
    --ldc-slate: #577171;
    --ldc-lime: #98ab44;
    --ldc-alerta: #c0584f;
    --ldc-linha: #e6e8ea;

    /**
     * A ESCALA DIVERGENTE — adendo ao DESIGN.md, para heatmap de magnitude COM SINAL.
     *
     * Por que ela não existia: o DESIGN.md tem um acento (lime) e um alerta, que bastam para
     * estado ("no trilho" / "exige ação") e não bastam para medir quanto. Um mapa de calor de
     * excesso sobre o CDI precisa de ~4 passos por lado e de um meio que signifique "empatou".
     *
     * Por que lime fica FORA da escala: "Sucesso não ganha verde. Lime é acento de ação, não de
     * estado." Lime continua sendo ação — no heatmap ele marca o RECORTE do trimestre corrente
     * (uma borda), nunca o sinal do número.
     *
     * Por que navy ↔ alerta, e não azul ↔ vermelho: azul e vermelho é a convenção, e é o que o
     * lado Python usa hoje (paleta placeholder da skill `dataviz`, não a paleta LDC). Navy e
     * alerta são as duas tintas que a casa já tem nas pontas frias e quentes, então a figura do
     * PDF e a tela do app podem sair da MESMA escala. Em contrapartida, navy ↔ alerta é um par
     * divergente menos convencional e precisa de teste com o Comitê antes de virar padrão.
     *
     * Simetria é obrigatória: a escala é ±extremo. Sem simetria, o neutro do meio deixa de
     * significar "empatou com o CDI" (ADR-002 §3) e passa a ser um artefato da distribuição.
     *
     * CONTRASTE MEDIDO (WCAG 2.1, sobre a própria célula, texto de 10,5px bold):
     *   negativo 1  #f4e1df  com navy #262d3d → 10,9:1   AA e AAA
     *   negativo 2  #e8b4af  com navy #262d3d →  7,6:1   AA e AAA
     *   negativo 3  #a94d46  com  #fcfdfd     →  5,3:1   AA
     *   negativo 4  #8c3b34  com  #fcfdfd     →  7,3:1   AA e AAA
     *   neutro      #f0f2f3  com navy #262d3d → 12,3:1   AA e AAA
     *   positivo 1  #dfe3e8  com navy #262d3d → 10,7:1   AA e AAA
     *   positivo 2  #9aa6b4  com navy #262d3d →  5,6:1   AA
     *   positivo 3  #5a6a7e  com  #fcfdfd     →  5,5:1   AA
     *   positivo 4  #262d3d  com  #fcfdfd     → 13,6:1   AA e AAA
     *   suprimido   #eceef0  com  #43585a     →  6,6:1   AA e AAA
     *
     * A ÚNICA DIVERGÊNCIA em relação à proposta original (`ldc-analytics-identidade-v2.md`
     * §9.4): o 3º passo do arco negativo é #a94d46, não o #c0584f cheio. Medido, #c0584f dá
     * 3,1:1 com navy e 4,4:1 com #fcfdfd — reprova AA para texto pequeno nas DUAS tintas, e a
     * célula carrega número. #a94d46 já existe no sistema (é o hover de .ldc-btn-alerta) e
     * passa. O #c0584f segue sendo a âncora do arco: aparece na legenda e na borda tracejada do
     * estado de alerta, onde não há texto por cima.
     */
    --ldc-escala-neutro: #f0f2f3;        /* zero: empatou. É o grid do DESIGN.md */
    --ldc-escala-neg-1: #f4e1df;
    --ldc-escala-neg-2: #e8b4af;
    --ldc-escala-neg-3: #a94d46;
    --ldc-escala-neg-4: #8c3b34;
    --ldc-escala-pos-1: #dfe3e8;
    --ldc-escala-pos-2: #9aa6b4;
    --ldc-escala-pos-3: #5a6a7e;
    --ldc-escala-pos-4: #262d3d;
    --ldc-escala-suprimido: #eceef0;     /* sem conclusão: o track, não o neutro da escala */
    --ldc-escala-hachura: #cfd4d6;       /* o traço da hachura da supressão */
    --ldc-escala-tinta-clara: #fcfdfd;
    --ldc-escala-tinta-suprimida: #43585a;
  }
```

E, **fora** de `@layer base`, junto dos utilitários semânticos (a seção que começa em
`.ferramenta .ldc-alerta`), duas regras de conveniência — opcionais, só para quem montar legenda
em HTML em vez de SVG:

```css
/**
 * Amostra de escala para legenda em HTML. O SVG do heatmap pinta por atributo (`fill`), como o
 * kit de gráficos da casa faz, e não usa estas classes.
 */
.ferramenta .ldc-amostra {
  display: inline-block;
  width: 1.25rem;
  height: 0.875rem;
  border-radius: 0.125rem;
}
.ferramenta .ldc-suprimido {
  background: var(--ldc-escala-suprimido);
  border: 1px solid var(--ldc-escala-hachura);
  color: var(--ldc-escala-tinta-suprimida);
}
```

---

## Por que o patch é só isto

- **Nenhuma tinta nova fora do arco das duas que a marca já tem.** Os dez valores são clareamentos
  e escurecimentos de `#c0584f` e de `#262d3d`, mais o grid e o track que o `DESIGN.md` já nomeia.
- **Nenhum token do framework é redefinido.** O patch só acrescenta variáveis `--ldc-escala-*`
  dentro de `.ferramenta`. Nada que já está escrito no app muda de aparência: os 274 cinzas, os 13
  `bg-white` e as 166 ocorrências de `text-sm` que o escopo já corrige continuam exatamente como
  estão.
- **Nenhuma regra nova no site público.** Fora de `.ferramenta` nada é afetado.
- **Sem `color-mix`.** O CSS do app já registra por escrito por que `color-mix` saiu
  (`.ldc-sup-alerta`): com variável CSS nos operandos, o fallback injeta o token em força total e
  o painel vira vermelho sólido com texto vermelho. Aqui todo valor é hex resolvido à mão.

## O que fica como dívida, declarada

1. **O hex está em dois lugares.** `_lib/formato.ts` (para o SVG) e `globals.css` (para o sistema).
   É o mesmo trade-off que `charts.tsx` já tem: o kit declara `NAVY`/`SLATE`/`LIME`/`RED` como
   constantes locais e exporta `CHART_COLORS` para o resto do app não re-declarar. Se o patch for
   aceito, o caminho limpo é `CHART_COLORS` ganhar a escala e `formato.ts` importar dela — o que é
   uma alteração no arquivo deles, e por isso não foi feita aqui.
2. **O lado Python precisa adotar a mesma rampa.** `apps/analysis/figuras/_comum.py` usa hoje
   `ARCO_FRIO`/`ARCO_QUENTE` da paleta placeholder da skill `dataviz`. Enquanto os dois não
   convergirem, a figura do PDF e a tela do app saem de cores diferentes para o mesmo número — o
   que é pior do que qualquer uma das duas escolhas.
3. **Validação com gente, e uma medição que falta.** Navy ↔ alerta é menos convencional que
   azul ↔ vermelho. Os dez pares de contraste acima foram medidos; a separação em protanopia e
   deuteranopia **não** foi: o que dá confiança é que os dois arcos se separam por **luminância**
   (o canal que sobrevive às duas), ao contrário de verde ↔ vermelho, que é o par que o mercado
   usaria por reflexo e que colapsa. Rodar o `validate_palette.py --mode light --pairs all` do
   lado Python sobre esta rampa é uma tarefa de meia hora, e ninguém do Comitê olhou ainda.

## Como conferir depois de aplicar

```bash
npm run lint          # o CSS não entra no ESLint; serve para garantir que nada mais quebrou
npm run build         # Tailwind 4 compila o globals.css; token inválido falha aqui
```

Visualmente, a prova de que o patch não mexeu em nada: abrir `/admin/wealth-planning/dashboard` e
`/admin/estudos-r2/meu-dia` antes e depois. Nenhum pixel deve mudar — as variáveis novas não são
consumidas por nenhuma regra existente.
