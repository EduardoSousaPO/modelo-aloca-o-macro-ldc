# Roteiro de Discovery — Playbook Operacional

Este documento descreve como conduzir uma sessão de discovery do início ao fim, incluindo ritmo, agrupamento de perguntas, checkpoints e produção do PRD.

---

## Visão Geral do Processo

```
ABERTURA → EXPLORAÇÃO → DEFINIÇÃO → DETALHAMENTO → CONSOLIDAÇÃO → ENTREGA
(Etapas 1-2)  (Etapas 3-5)  (Etapas 6-8)  (Etapas 9-13)   (Etapas 14-15)  (Etapa 16)
```

---

## Fase 1: Abertura (Etapas 1-2)

### Objetivo
Entender a essência da ideia e mapear o problema/oportunidade.

### Ritmo
- Comece com pergunta aberta: "Me conta sobre o que você quer construir."
- Escute sem interromper na primeira resposta.
- Faça 2-3 perguntas de follow-up sobre o problema.

### Checkpoint 1
Apresente um resumo de 3-5 linhas:
> "Pelo que entendi até agora: [resumo]. Estou no caminho certo?"

### Sinais de alerta nesta fase
- O usuário descreve funcionalidades em vez de problemas → Redirecione: "Antes de falar do que o sistema FAZ, vamos entender QUAL PROBLEMA ele resolve."
- A ideia é uma cópia de produto existente → Explore diferenciação: "O que torna isso diferente de [concorrente]?"
- O problema não parece real → Questione gentilmente: "Você já validou essa dor com potenciais usuários?"

---

## Fase 2: Exploração (Etapas 3-5)

### Objetivo
Mapear público-alvo, proposta de valor e objetivos.

### Ritmo
- 2-3 perguntas por mensagem.
- Alterne entre perguntas sobre usuário, valor e metas.

### Checkpoint 2
```
Resumo parcial:
- Problema: [X]
- Público: [Y]
- Proposta de valor: [Z]
- Objetivos principais: [A, B, C]

Está correto? Algo para ajustar?
```

### Técnicas para esta fase
- Se o público é vago, peça para descrever UM usuário real (nome fictício, cargo, rotina).
- Se o valor é genérico ("economiza tempo"), peça quantificação ("quanto tempo? comparado a quê?").
- Se os objetivos são irrealistas, mostre gentilmente: "Para chegar a [meta], com [público-alvo], precisaríamos de [X]. Faz sentido?"

---

## Fase 3: Definição (Etapas 6-8)

### Objetivo
Delimitar o MVP, listar funcionalidades e mapear os fluxos principais.

### Ritmo
- Esta fase costuma ser mais longa. Mantenha o foco.
- Para funcionalidades, crie uma lista progressiva: adicione cada funcionalidade conforme é mencionada.
- Para fluxos, peça o happy path primeiro, depois explore exceções.

### Checkpoint 3
```
Funcionalidades mapeadas até agora:
MVP:
  1. [Func A] - [descrição breve]
  2. [Func B] - [descrição breve]
  3. [Func C] - [descrição breve]

Futuro:
  1. [Func D] - [descrição breve]

Fluxos mapeados:
  1. [Jornada principal]
  2. [Jornada secundária]

Faltam detalhes sobre: [X, Y]
```

### Técnicas para esta fase
- Use contrafactual para validar MVP: "E se tirássemos [funcionalidade], o produto ainda faz sentido?"
- Use decomposição para funcionalidades grandes: "Esse módulo tem sub-funcionalidades? Quais?"
- Para fluxos, peça narração: "Imagina que estou sentado na frente do sistema. O que aparece? O que faço?"

---

## Fase 4: Detalhamento (Etapas 9-13)

### Objetivo
Capturar regras de negócio, dependências, restrições, métricas e riscos.

### Ritmo
- Estas perguntas podem ser mais técnicas. Adapte a linguagem ao usuário.
- Se o usuário não for técnico, traduza: "Integração com API" → "Precisa puxar dados de algum outro sistema?"
- Agrupe temas relacionados: regras + restrições, dependências + integrações.

### Checkpoint 4
```
Detalhamento técnico:
- Regras de negócio: [N] regras mapeadas
- Integrações: [lista]
- Restrições: [lista]
- Métricas: [lista com targets]
- Riscos identificados: [N]
- Hipóteses não validadas: [N]
- Pontos em aberto: [N]

Algo mais para adicionar?
```

---

## Fase 5: Consolidação (Etapas 14-15)

### Objetivo
Priorizar e gerar o PRD final.

### Ritmo
- Apresente a priorização como proposta e peça validação.
- Gere o PRD completo.
- Faça uma revisão final item por item.

### Priorização
Use o framework que parecer mais adequado:

**MoSCoW:**
- **Must** — Essencial para o MVP funcionar
- **Should** — Importante mas não bloqueante
- **Could** — Desejável se houver tempo/recursos
- **Won't** — Explicitamente fora de escopo (por agora)

**RICE:**
- **Reach** — Quantos usuários impacta
- **Impact** — Quanto impacta cada usuário (0.25 a 3)
- **Confidence** — Quão confiantes estamos (%)
- **Effort** — Pessoa-semanas de desenvolvimento

### Geração do PRD
1. Leia `assets/prd_template.md`
2. Preencha cada seção com os dados coletados
3. Verifique contra `assets/completeness_checklist.md`
4. Gere o documento

---

## Fase 6: Entrega (Etapa 16)

### Objetivo
Garantir que o PRD está pronto para a próxima fase.

### Ações
- Revise dúvidas pendentes com o usuário
- Sugira próximos passos concretos
- Ofereça gerar versão .docx se apropriado
- Indique quem deveria revisar o PRD

---

## Gerenciamento de Sessão

### Sessões longas
Se a sessão está ficando muito longa (muitas mensagens), ofereça salvar o progresso:
- "Temos bastante material coletado. Quer que eu gere um PRD parcial com o que temos até agora? Podemos continuar e complementar depois."

### Usuário ansioso para ver o documento
Se o usuário quer pular para o PRD final:
- Faça um mini-checklist do que falta
- Se as lacunas são menores, avance para o PRD e marque as lacunas como "TBD"
- Se as lacunas são críticas, explique por que é importante cobrir antes

### Múltiplas sessões
Se o discovery precisa ser dividido em mais de uma sessão:
- Sempre termine com um resumo do que foi coberto
- Na sessão seguinte, comece relembrando onde pararam
- Mantenha um "estado" claro das etapas concluídas

---

## Adaptação por Maturidade da Ideia

### Ideia Embrionária ("Tenho uma ideia vaga...")
- Dedique mais tempo às Fases 1 e 2
- Use muitas perguntas abertas
- Ajude a cristalizar antes de detalhar

### Ideia Em Formação ("Já sei o problema e o público, mas...")
- Valide rapidamente as Fases 1-2
- Concentre energia nas Fases 3-4

### Ideia Avançada ("Já tenho requisitos parciais, preciso completar")
- Leia os requisitos existentes
- Identifique lacunas usando o checklist
- Preencha apenas o que falta
