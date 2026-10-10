# Overview — estrategia-macro-ldc-dados

> **O que este projeto entrega hoje em 1 página.** Leitura em 60s.
>
> **Fonte de verdade do escopo:** [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
> (imutável). Quando houver PRD, `docs/product/PRD.md` passa a ser a fonte de produto e esta página o resume.
> **Atualizado pelo agente** após mudanças relevantes. Revisão a cada 2 semanas.

**Última revisão:** 2026-10-10
**Versão refletida:** e-mail de escopo transcrito em 2026-10-10 (PRD ainda não existe)

---

## 1. Em 1 frase

> Ferramenta interna de dados/quant da LDC Capital que monta a base estatística trimestral de 20 anos
> (macro brasileiro + desempenho de ativos e subsetores) para fundamentar o modelo de alocação macro
> doméstica e o tamanho da alocação internacional do Comitê de Alocação.

## 2. Objetivo (síntese do e-mail do Alexandre, 5 linhas)

1. O Alexandre está desenvolvendo um **modelo de alocação macro doméstica + dimensionamento da alocação
   internacional** e quer fundamentar as decisões com **base estatística**, não com leitura qualitativa.
2. A pergunta central é: **como cada classe de ativo e cada setor performou em momentos macro semelhantes?**
   — isto é, análise por **regimes macro**.
3. Período: **últimos 20 anos**, idealmente em frequência **trimestral** (dados brutos podem ser
   diários/mensais e serem agregados).
4. Variáveis mapeadas: bloco **A** macro (PIB/IBC-Br, IPCA, expectativas Focus, Selic Over, taxas de títulos
   públicos, ETTJ/inclinação da curva) e bloco **B** ativos (IMA-B e IRF-M da ANBIMA, CDI, índices amplos e
   setoriais da B3 — IBOV, IDIV, SMLL, INDX, ICON, IMAT, IEE, IMOB, IFNC — e FIIs via IFIX e segmentações);
   o bloco **C** (proxy internacional) está implícito no objetivo e precisa ser definido.
5. O pedido explícito é **estruturar a busca e a extração desses dados via IA**, entregando base pronta para
   ele modelar a estratégia — com liberdade para **ajustar ou substituir fontes** que não forem localizáveis,
   desde que a troca fique registrada.

## 3. Para quem

- **Usuário primário:** Alexandre Kaercher — consome o dataset canônico e os cortes por regime para modelar
  a estratégia de alocação.
- **Usuário secundário:** Comitê de Alocação da LDC Capital (consome o resultado sintetizado, não o pipeline).
- **Operador:** Eduardo (Edu) — roda o pipeline local, orquestra os agentes, aprova classe D.
- **Quem NÃO é o público:** cliente final, usuário externo, público via web. Não há interface, não há conta,
  não há multi-tenant.

## 4. Stack em 1 linha

Python 3.11+ · pandas + pyarrow · requests/httpx · pydantic + pandera (contratos de dados) ·
DuckDB/Parquet local · Jupyter (análise) · pytest + ruff. Roda **local**, sem deploy.

## 5. Restrições conhecidas (base da futura Anti-SPEC)

- **Não inventar dado.** Lacuna sem substituto acordado → `BLOQUEADO — FONTE INDISPONÍVEL`. Nada de
  interpolação silenciosa, estimativa ou valor "plausível" para fechar série.
- **Não é SaaS/web.** Sem auth, sem pagamento, sem deploy em produção, sem frontend.
- **`data/` não é versionado** e não é fonte de verdade — o script que produz o dado é. Dado bruto > 5 MB
  nunca entra no git.
- **Camada canônica é classe C.** Schema, alinhamento temporal e cálculo de retorno só mudam com Feature
  Contract detalhado + diff numérico vs. versão anterior.
- **Publicar para o Comitê é classe D** (revisão humana + dataset congelado).
- Fontes públicas podem revisar números retroativamente (ex.: PIB do IBGE): o pipeline tem de ser
  **idempotente** e registrar a revisão, não duplicar linha.
- Nem toda série pedida cobre os 20 anos completos (ex.: segmentações de IFIX). O recorte real de cada série
  precisa ficar explícito, não ser mascarado.

## 6. Estado atual

- **Fase:** kickoff concluído (estrutura Harness v3.2 criada em 2026-10-10)
- **Pipeline implementado:** nenhum ainda — `apps/pipeline/` e `apps/analysis/` vazios
- **Dataset canônico:** não existe ainda
- **Pesquisa de fontes:** em andamento em [`docs/research/`](../research/) (vários agentes em paralelo)
- **CI:** N1 configurado (ruff + pytest unit); N2/N3 comentados aguardando testes reais
- **Próximo passo:** `/consultor-prd` → `/SDD-avancado` para gerar PRD, SPEC/Anti-SPEC, contratos e backlog

## 7. Próximo grande objetivo

Entregar o dataset canônico trimestral de 20 anos, com os blocos A e B conferidos contra as fontes
originais, **antes da reunião do Comitê de Alocação em 2026-10-14**.

---

## Links

- Escopo de origem (imutável) → [`docs/product/ESCOPO-EMAIL-ALEXANDRE.md`](../product/ESCOPO-EMAIL-ALEXANDRE.md)
- Pesquisa de fontes e metodologia (em andamento) → [`docs/research/`](../research/)
- PRD (a criar) → [`docs/product/PRD.md`](../product/PRD.md)
- SPEC + Anti-SPEC (a criar) → [`docs/specs/SPEC.md`](../specs/SPEC.md)
- Arquitetura → [`wiki/architecture.md`](./architecture.md)
- Estado vivo → [`TODO.md`](../../TODO.md)
- Histórico → [`wiki/log.md`](./log.md)
- Contrato com agentes → [`AGENTS.md`](../../AGENTS.md)

---

*Atualize esta página quando: o escopo mudar (com registro), a fase mudar, uma restrição grande for
adicionada/removida, ou o dataset canônico passar a existir. Não atualize por feature pequena.*
