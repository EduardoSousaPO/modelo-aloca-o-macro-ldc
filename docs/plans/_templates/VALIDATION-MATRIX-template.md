# Validation Matrix — F-NNN [Nome da feature]

> **Matriz obrigatória no QA (Prompt 3) de todas as features classe B, C, D.** Relaciona cada critério de aceite com o teste que o cobre, o tipo de teste, o status e a evidência objetiva. No **Validation Mode** (v3.1 patch), o QA não apenas confirma que testes passam — ele **tenta quebrar** a feature antes de aprovar.
>
> **Se algum CA não tem evidência objetiva → resultado final é `MUDANÇAS_SOLICITADAS`. Nunca `APROVADO`.**
>
> **Onde vive:** por padrão, no próprio Feature Contract (bloco final). Só extraia para `docs/plans/validation-matrix/F-NNN.md` se ficar grande ou se quiser preservar evidência fora do TODO.

---

## Identificação

- **Feature:** F-NNN — [nome]
- **Classe de risco:** [A | B | C | D]
- **Branch:** `feat/<slug>`
- **Autor do QA:** [Claude Code + humano revisor]
- **Data:** YYYY-MM-DD

---

## Matriz CA → teste → evidência

| CA | Descrição resumida | Teste que cobre | Tipo | Status | Evidência |
|---|---|---|---|---|---|
| CA-001 | extrator devolve as 5 séries com o shape esperado | `test_sgs.py::test_shape` | unit (fixture) | passou | `pytest tests/unit/test_sgs.py` + 1.248 linhas, `min`/`max` = 2006-01/2026-09 |
| CA-002 | HTTP 200 com corpo de erro levanta e não grava | `test_sgs.py::test_corpo_de_erro` | unit negativo | passou | idem, log no PR |
| CA-003 | valor-canário CDI 2006 = 15,0271% | `test_valores_canario.py::test_cdi_2006` | contract | passou | 3 valores conferidos na fonte (print/link) |
| CA-004 | pipeline do zero duas vezes gera o mesmo hash | `test_reprodutibilidade.py::test_dois_runs` | e2e | passou | `DATASET_SHA256` idêntico nos dois runs, colado no PR |
| CA-005 | % de nulos em coluna crítica = 0 | N/A | **não coberto** | **falhou** | precisa de asserção `pandera` antes do merge |

---

## Resumo

- **CAs totais:** 5
- **Cobertos por teste automatizado:** 4
- **Cobertos por smoke/manual (se inevitável):** 0
- **Não cobertos:** 1 → **CA-005**

---

## Validation Mode — tentativas de quebrar a feature

> Para classe **B** basta revisar mentalmente; para **C/D**, documentar evidências aqui. Sem esta seção, o QA de C/D não pode retornar `APROVADO`.

| Categoria | Cenário exercitado | Evidência / Nota |
|---|---|---|
| Resposta inválida da fonte | HTTP 200 com corpo de erro / HTML onde se esperava planilha | teste `test_sgs.py::test_corpo_de_erro` |
| Truncamento silencioso | janela > 10 anos, `range=max`, limite de 20.000 linhas do Olinda | contagem mínima esperada asseverada no teste |
| Ausência de dados | dia sem publicação / feriado → sucesso **com registro**, não exceção | `test_anbima_diario.py::test_zero_bytes` |
| Caso-armadilha de calendário | 31/12 em fim de semana, feriado em fim de trimestre, série que começa depois de 2006 | `test_alinhamento.py::test_feriados` |
| Idempotência / execuções repetidas | rodar 2x não duplica nem grava conteúdo diferente; dois runs → mesmo hash | `test_reprodutibilidade.py` |
| Escala e sinal | retorno acumulado por razão (não subtração), IPCA aplicado uma única vez, % vs. fração | diff numérico vs. o canônico anterior |
| Nulos e painel desbalanceado | coluna crítica sem `NaN`; nenhuma linha antes do início real da série | `pandera` + print do `isna().sum()` |
| Fora de escopo alterado? | diff só toca arquivos permitidos | `git diff --stat` anexado ao PR |

Se alguma linha está vazia ou marcada como "não exercitado", o agente deve **criar o teste** (A/B) ou **solicitar** (C/D) antes de aprovar.

---

## Tipos de teste aceitos (prioridade decrescente)

1. **unit** — cobre lógica pura, sem IO (parsing, normalização de número pt-BR, cálculo de retorno).
2. **integration** — cobre a costura entre etapas do pipeline sobre **fixture gravada** da fonte.
3. **contract test** — cobre schema `pandera`/`pydantic` vs. a resposta real da fonte + **valor-canário** conhecido.
4. **e2e** — pipeline do zero (`pytest tests/e2e -m "not network"`), incluindo duas execuções com o mesmo hash.
5. **smoke test** — verificação curta do **pacote de entrega** (abre no Excel, contagens, nulos, paridade Parquet × CSV).
6. **manual — só se inevitável** — descreva o passo a passo e anexe print/log como evidência.

---

## O que conta como evidência objetiva

- Saída de `pytest` com o teste nomeado passando.
- Nº de linhas + `min`/`max` de data + % de nulos por coluna crítica do output real.
- **3 valores conferidos contra a fonte original** (print/link) — não contra o teste.
- **Diff numérico** vs. a versão anterior do canônico, com cada divergência explicada (classe C).
- **Dataset congelado**: `DATASET_SHA256` registrado e idêntico em duas execuções do zero (classe D).
- Log do CI do GitHub Actions com a linha final de sucesso.
- Smoke test do pacote rodado com exit code 0 e output anexado.

**O que NÃO conta:**
- "O agente afirma que funciona."
- "O código parece correto."
- Teste que existe mas está `.skip` ou `.only`.
- Cobertura genérica ("o arquivo está testado") sem amarração ao CA.

---

## Resultado final (v3.1 Validation Mode Patch)

Escolha **um**:

- [ ] **APROVADO** — todos os CAs têm evidência objetiva; Validation Mode exercitado; CI verde no nível da classe; Anti-SPEC respeitada; contratos consistentes; nenhum arquivo fora do contrato alterado (ou justificativa aceita com contrato atualizado).
- [ ] **MUDANÇAS_SOLICITADAS** — há CA sem evidência OU teste falhando OU teste fake (ver `risk-classification.md`) OU teste mínimo por classe ausente OU CI vermelho OU contrato divergente OU Validation Mode pulado em C/D.
- [ ] **BLOQUEADO** — Definition of Ready incompleta em domínio sensível OU Anti-SPEC violada OU arquivo fora do Feature Contract sem justificativa aceita OU reclassificação de risco pendente OU operação classe D sem Rollback em `docs/plans/infra-ops.md` / sem dataset congelado.

### Issues (se MUDANÇAS_SOLICITADAS ou BLOQUEADO)

1. [problema específico + caminho de fix]
2. ...

---

*Esta matriz é a peça central do Feedback Hardened. A qualidade do produto depende de nunca aprovar sem evidência.*
