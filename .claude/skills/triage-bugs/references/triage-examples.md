# Triage Examples — referência prática

> 5 exemplos curtos de triagem (lista in → plano out). Use como calibração quando o contexto da lista não estiver óbvio.

---

## Exemplo 1 — Manhã caótica de segunda

**Input:**
```
- usuário não consegue subir foto de perfil maior que 1MB
- typo no email de boas-vindas: "Bem vindo" (faltou hífen)
- toggle de "modo escuro" não persiste após F5
- migração da última sprint não rodou em 2 envs (staging-2, dev-3)
- Stripe alertou que webhook /v1/payment falhou 12 vezes em 1h
```

**Tempo disponível:** 6 horas

**Output:**

| ID | Bug | Classe | Domínio | Urg | Imp | Esf | Modo | Score |
| BUG-021 | upload > 1MB falha | B | upload | P2 | médio | 30min | fast-fix→standard | 4 |
| BUG-022 | typo "Bem-vindo" | A | copy | P3 | baixo | 2min | fast-fix | 1 |
| BUG-023 | dark mode não persiste | B | ui+storage | P2 | médio | 1h | standard | 3 |
| BUG-024 | migração não rodou em 2 envs | D | infra+deploy | P0 | crítico | 2h | production | 9 |
| BUG-025 | Stripe webhook 12 falhas/h | D | payment+webhook | P0 | crítico | 3h | production | 10 |

**PLANO DE HOJE (6h):**
1. **BUG-025** — Production via Prompt 2 (3h) — payment quebrando agora, P0
2. **BUG-024** — Production via Prompt 2 (2h) — pode ser causa raiz do BUG-025; investigar antes de fechar 025
3. **BUG-022** — /fast-fix (10min) — limpa cosmético rápido para encerrar o dia

**BACKLOG:** BUG-021, BUG-023 (não cabem hoje; sem urgência declarada).

**ESCALATIONS:** BUG-024 e BUG-025 são classe D — exigem cursor-brief antes de tocar.

---

## Exemplo 2 — Lista pequena, fim de tarde

**Input:**
```
- botão "exportar" não aparece em telas com 0 registros
- email de reset de senha cai no spam para usuários do Outlook
```

**Tempo disponível:** 2 horas

**Output:**

| ID | Bug | Classe | Domínio | Urg | Imp | Esf | Modo | Score |
| BUG-030 | botão exportar oculto em estado vazio | B | ui+empty-state | P2 | baixo | 30min | fast-fix | 2 |
| BUG-031 | reset password vai para spam (Outlook) | C | email+deliverability | P1 | alto | 1.5h | standard | 5 |

**PLANO (2h):** 1) BUG-030 (30min); 2) BUG-031 (1.5h).

**ESCALATIONS:** nenhuma. BUG-031 é C porque toca auth+e-mail mas não é Production.

**Notas:** BUG-031 pode escalar para D se exigir mudança de DNS/SPF/DKIM em produção. Reclassificar se sim.

---

## Exemplo 3 — Lista misturando bug com pedido de feature

**Input:**
```
- gráfico do dashboard quebra em 4K (zoom 200%)
- queremos adicionar filtro por data no relatório
- 500 quando admin tenta deletar usuário com pedidos abertos
- exportar CSV em vez de só PDF
```

**Output:**

| ID | Item | Classificação | Onde vai |
| BUG-040 | gráfico quebra em 4K | bug | TODO §5 — classe B |
| FR-001 | filtro por data | **NÃO É BUG** | TODO §2 Backlog (feature B) |
| BUG-041 | 500 ao deletar admin com pedidos | bug | TODO §5 — classe C (regra de negócio) |
| FR-002 | exportar CSV | **NÃO É BUG** | TODO §2 Backlog (feature B) |

**Plano:** triar só os 2 bugs reais. As 2 features vão para backlog SEPARADO.

```
PLANO DE HOJE: 1) BUG-040 fast-fix; 2) BUG-041 standard (regra de negócio).
```

---

## Exemplo 4 — Recorrência detectada

**Input:**
```
- export de PDF lento de novo (45s)
```

**Output:**

| ID | Bug | Classe | Recorrência |
| BUG-052 | PDF lento (45s) | B | **4ª vez** — runbook wiki/runbooks/bug-pdf-lento.md aplicado 3x |

**ESCALATION:** "Pare de aplicar runbook. Causa raiz não foi resolvida. Sugiro Deep Work com Feature Contract de 'refator do gerador de PDF', CI N2, ADR sobre estratégia. Custo do refator < 4× o custo do próximo fast-fix + impacto no cliente."

---

## Exemplo 5 — Vulnerabilidade ativa

**Input:**
```
- alguém me reportou que conseguiu acessar /admin sem login (link direto)
- tela de produtos abre devagar
```

**Output:**

| ID | Bug | Classe | Domínio | Urg | Imp |
| BUG-060 | bypass de auth em /admin (acesso anônimo) | C/D | **auth+vulnerabilidade** | **P0-EMERGÊNCIA** | crítico |
| BUG-061 | tela produtos lenta | B | performance | P3 | baixo |

**ESCALATION P0-EMERGÊNCIA:**

> BUG-060 é vulnerabilidade ativa de autorização. Mesmo que o tempo declarado pelo usuário seja "1 hora", **DEVO** reportar como emergência. O humano decide a janela; eu não silencio um vazamento.
>
> Recomendação imediata:
> 1. Validar repro (1 minuto).
> 2. Se confirmado: rotacionar/desabilitar a rota OU adicionar middleware de auth IMEDIATAMENTE como hot patch (Prompt 2 standard se classe C, Production se D).
> 3. Após patch: criar runbook em `wiki/runbooks/bug-admin-bypass.md` + ADR sobre causa raiz + escrever testes negativos para todos os endpoints admin/.

BUG-061 fica no backlog com calma.

---

## Padrões úteis

- **Bug financeiro / payment / webhook** → quase sempre classe D. Trate como P0 mesmo que cliente diga "pode esperar".
- **Bug de auth** → mínimo classe C. Se permite acesso indevido a dados → vulnerabilidade, P0-emergência.
- **Bug cosmético** → classe A, geralmente fast-fix em < 10 min. Bom para encerrar o dia ou ganhar momentum.
- **Bug de performance** → classe B/C dependendo do impacto. Cuidado com refator preventivo: só ataque causa raiz se ≥ 3 ocorrências do mesmo padrão.
- **Pedido de feature disfarçado de "bug"** → marcar como NÃO É BUG, abrir feature no backlog. Não inflar §5.
- **Bug que ninguém consegue reproduzir** → não triagem ainda; abrir como linha de investigação no DECISIONS_LOG ou wiki/log.md tipo `INGEST` e pedir mais info.

---

*Triage é decisão, não executição. O agente pode triar; o humano confirma o plano antes de o agente atacar.*
