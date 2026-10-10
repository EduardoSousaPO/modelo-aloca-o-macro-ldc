# CURRENT_REALITY — estrategia-macro-ldc-dados

> **Fotografia honesta do estado atual do repositório.** Obrigatório para projetos **já iniciados**, **em produção** ou **bagunçados** (cenários B, C, D). Opcional para projetos novos (cenário A).
>
> **Gerado antes do PRD/SPEC retroativos.** Evita que o `/consultor-prd` ou o `/SDD-avancado` "inventem" features que o código não faz.
>
> **Onde vive:** `docs/plans/CURRENT_REALITY.md`.
>
> **Quem atualiza:** o Claude Code no diagnóstico inicial, e o humano sempre que descobrir algo novo sobre o estado real.

**Data do diagnóstico:** YYYY-MM-DD
**Branch analisada:** main (commit `<sha>`)
**Autor do diagnóstico:** [humano + agente]

---

## 1. O que este projeto realmente faz hoje

> Descreva em 3–6 frases o que o sistema **efetivamente entrega** para o usuário final **hoje**, baseado em código rodando, não em intenção.

- ...
- ...

---

## 2. Extratores reais

> Fontes que de fato são extraídas hoje. Confirme lendo o código e o conteúdo de `data/raw/`, não o README.

| Fonte | Endpoint / arquivo de origem | Arquivo do extrator | Status | Notas |
|---|---|---|---|---|
| BCB SGS | `api.bcb.gov.br/dados/serie/...` | `apps/pipeline/extract/sgs.py` | funcional | sem cache condicional |
| ANBIMA S3 | bucket público (arquivos IMA) | `apps/pipeline/extract/anbima_s3.py` | funcional | `.xls` que é XLSX — escolhe leitor por magic bytes |
| API B3 | `indexStatisticsProxy` | `apps/pipeline/extract/b3.py` | parcial | 11 índices mapeados, 1 sem histórico completo |

---

## 3. Figuras, tabelas e notebooks reais

| Entregável visual | Arquivo | Estado | Notas |
|---|---|---|---|
| heatmap regime × ativo | `apps/analysis/figuras/heatmap.py` | funcional | `n` anotado em toda célula |
| timeline de regimes | `apps/analysis/figuras/timeline.py` | parcial | sem a Selic no eixo secundário |
| notebook de entrega | `apps/analysis/entrega.ipynb` | parcial | ainda contém lógica de negócio (deveria importar de `apps/pipeline/`) |

---

## 4. Camadas de dados reais

- **Formato por camada:** [Parquet por camada + DuckDB como engine de consulta — ADR-006]
- **`data/raw/`:** [quais subpastas existem, desde quando, tamanho aprox.]
- **`data/processed/`:** [quais séries, frequência nativa, validadas por `pandera`? sim/não]
- **`data/canonical/`:** tabelas materializadas hoje
  - `macro_quarterly` — X linhas (esperado: 83) — última reconstrução: YYYY-MM-DD
  - `asset_returns_quarterly` — Y linhas / Z ativos
  - `regimes` / `regime_neighbors` — [existe? com qual lente?]
- **Schemas `pandera` aplicados de fato:** [mapa curto — quais DataFrames passam por schema na entrada e na saída]
- **Arquivos em `data/` sem script que os reproduza:** [lista, se houver — **risco alto**: a verdade é o script]

---

## 5. Integrações reais

| Fonte / serviço | Finalidade | Status | Credencial | Notas |
|---|---|---|---|---|
| BCB SGS / Olinda | IPCA, Selic, CDI, PTAX, Focus | ativo | nenhuma | pública; HTTP 200 pode trazer corpo de erro |
| IBGE SIDRA | IPCA nº-índice, PIB trimestral | ativo | nenhuma | `apisidra`; janela fatiada |
| FRED | contexto externo (UST, VIX) | **bloqueado nesta máquina** | nenhuma | plano B: Yahoo (`^TNX`, `^VIX`) — ver `DECISIONS_LOG` |
| ANBIMA Feed | ETTJ oficial com 20 anos | **não contratado** | paga | fora do caminho crítico (Anti-SPEC §10.3.14) |

---

## 6. Testes existentes

- **Unit:** X arquivos — pastas: `tests/unit/`
- **Integration:** Y arquivos — pastas: `tests/integration/`
- **E2E:** [existe? cobre o pipeline do zero e as duas execuções com o mesmo hash?]
- **Contract tests com valor-canário:** [sim/não — quais séries]
- **Fixtures gravadas:** [quais fontes têm fixture real em `tests/fixtures/`; quais ainda usam dado sintético]
- **Testes de rede fora de `@pytest.mark.network`:** [nenhum, espera-se — liste se houver]
- **Testes conhecidos como instáveis:** [lista — `skip` / `xfail` / flaky]

---

## 7. CI existente

- **Existe `.github/workflows/ci.yml`?** [sim/não]
- **Está verde hoje?** [sim/não — se não, por quê]
- **Rodar local funciona?** [sim/não]
- **Jobs cobertos:** `ruff check`? `ruff format --check`? `pytest tests/unit`? integration/contract? e2e? build do canônico?
- **Gate de merge em `main`?** [sim/não]
- **Quem configurou?** [humano / herdado / nunca]

---

## 8. O que está quebrado hoje

> Lista honesta. Bugs confirmados, erros no console, features que prometeram e não funcionam.

- **BUG-001:** [descrição + repro + gravidade]
- **BUG-002:** ...

---

## 9. O que parece planejado mas não existe

> Código morto, feature flags ligadas apontando para stubs, rotas que retornam 501.

- ...

---

## 10. Features mencionadas em docs/README/Notion mas NÃO implementadas

> Crítico: alinha a documentação com a realidade. Sem isso, o PRD retroativo tende a "ganhar features" que ninguém construiu.

- [ ] "Exportar relatório PDF" — mencionado no README, não existe em código.
- [ ] "Modo escuro" — prometido em changelog, botão não faz nada.

---

## 11. Débito técnico

| Item | Onde | Impacto | Urgência |
|---|---|---|---|
| Mesma série lida por dois caminhos diferentes | `extract/` e notebook | drift de número | alta |
| `scripts/` na raiz com N arquivos soltos | raiz | bagunça | baixa |
| DataFrame ad hoc sem schema `pandera` na fronteira do canônico | `transform/` | erro silencioso de escala/coluna | alta |

---

## 12. Riscos técnicos

| Risco | Probabilidade | Impacto | Mitigação proposta |
|---|---|---|---|
| Endpoint não documentado muda sem aviso (B3, MSCI, S3) | média | alto | teste de contrato com valor-canário + fallback no catálogo |
| Canônico atual não reproduz do zero | alta | alto | reconstrução completa + **diff numérico** antes de qualquer feature C nova |
| Janela rolante da ANBIMA sem job rodando | alta | alto | job diário + `[DATA-LOSS]` no `wiki/log.md` se falhar > 20 d.u. |

---

## 13. Riscos de publicação

- **Números já enviados ao Alexandre/Comitê:** [versão, hash, data — ou "nenhum"]
- **Decisões de alocação já tomadas sobre esses números:** [quais — define o custo de um rollback]
- **Prazo duro mais próximo:** [ex: Comitê de Alocação em 2026-10-14]
- **Séries que não cobrem a janela de 20 anos:** [lista — vão para a página de limitações]
- **Dependências críticas externas:** [BCB SGS, IBGE SIDRA, ANBIMA, API B3, Yahoo/MSCI]

---

## 14. Pontos que NÃO devem ser tocados ainda

> Alimenta direto a Anti-SPEC. Liste tabelas canônicas, séries e módulos que não aceitam alteração sem Feature Contract classe C dedicado.

- Schema do canônico (`macro_quarterly`, `asset_returns_quarterly`, `regimes`) — alteração é **feature classe C** própria, com diff numérico e **dataset congelado** da versão anterior preservado.
- Regras de alinhamento temporal e cálculo de retorno — não ajustar "só um pouco" sem Feature Contract C.
- `data/raw/` é **imutável**: nunca editar nem apagar; é a única base de reconstrução.

---

## 15. Dependências humanas

- **Quem detém conhecimento tácito (bus factor = 1)?** [nome, módulo]
- **Credenciais guardadas com terceiros?** [lista]
- **Decisões estratégicas pendentes de stakeholder?** [lista]

---

## 16. Conclusão do diagnóstico

> 3–5 frases. A partir deste ponto, o projeto pode seguir para:
> - `/consultor-prd` retroativo (respeitando este CURRENT_REALITY)
> - `/SDD-avancado` retroativo (derivando RFs do que existe, não do desejado)
> - Ou, se o projeto estiver em produção instável, primeiro onda de estabilização antes de PRD.

Próxima decisão:
- [ ] Seguir para PRD retroativo (`/consultor-prd` em modo retroativo).
- [ ] Estabilizar CI antes de PRD (cenário C com CI vermelho/ausente).
- [ ] Reorganizar estrutura antes de PRD (cenário D).

---

*Este arquivo é documento vivo. Qualquer agente ou humano que descobrir algo novo sobre o estado real do sistema deve atualizá-lo antes de iniciar uma feature.*
