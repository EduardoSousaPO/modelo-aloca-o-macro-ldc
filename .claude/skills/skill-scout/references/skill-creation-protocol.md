# Protocolo de criação de skill nova (último recurso)

> Só siga este protocolo se o `/skill-scout` chegou à conclusão de que criar skill nova é necessário.

---

## Critérios obrigatórios para criar

Todos precisam ser verdadeiros:

- [ ] Nenhum MCP nativo cobre.
- [ ] Nenhuma tool nativa do Claude Code/Cursor cobre.
- [ ] Nenhuma skill existente cobre (nem parcialmente + contexto).
- [ ] A capacidade aparece em **pelo menos 3 projetos** ao longo do tempo (não é específica de um cliente).
- [ ] Sem a skill, o agente produz output inconsistente para esta capacidade.
- [ ] A capacidade é estável — não vai mudar a cada atualização da tecnologia envolvida.

Se algum item não for verdadeiro, não crie. Documente como "instrução pontual" no `AGENTS.md` ou em um trecho do `TODO.md`.

---

## Estrutura mínima de uma skill

```
<skill-name>/
├── SKILL.md                  ← frontmatter + prompt do agente
├── assets/                   ← templates fixos
│   └── *.md
├── references/               ← documentação para o agente ler sob demanda
│   └── *.md
└── scripts/                  ← código executável (opcional)
    └── *.py
```

**SKILL.md** tem frontmatter YAML:

```yaml
---
name: nome-da-skill
description: >
  Descrição concisa mas rica em gatilhos de ativação. Inclua os verbos e contextos em que a skill deve ser chamada. Use SEMPRE quando o usuário mencionar...
---

# Nome da skill — [Propósito]

[Corpo da skill: identidade, processo, regras, assets, references]
```

---

## Princípios para escrever a skill

1. **Propósito único.** Se for descrita com "e" (faz X e Y), provavelmente são duas skills.
2. **Assets estáveis.** Templates em `assets/` mudam raramente. Conteúdo variável fica fora.
3. **References sob demanda.** A skill principal aponta; o agente lê quando precisa.
4. **Regras explícitas de quando ativar e quando NÃO ativar.**
5. **Teste em pelo menos 2 casos reais** antes de promover ao catálogo.

---

## Catálogo com teto

Como regra prática: o catálogo de skills pessoais não deve ultrapassar ~20. Para uma skill nova entrar, uma skill antiga e desatualizada deve sair.

---

## Onde colocar

- **Skills genéricas e reutilizáveis** (ex: gerar PDF, criar deck) → catálogo global de skills do seu ambiente (fora do projeto).
- **Skills do próprio Harness Solo** (ex: /consultor-prd, /SDD-avancado) → diretório oficial do Harness Solo.
- **Skills específicas de um projeto** → NÃO vão para nenhum catálogo. Documentação/regras do projeto bastam.

---

## Revisão periódica

A cada 6 meses (ou quando criar uma nova skill):

- Alguma skill não é usada há 3 meses? Arquive.
- Alguma skill foi substituída por MCP nativo novo? Arquive.
- Alguma skill está desatualizada (tecnologia mudou)? Atualize ou arquive.

O objetivo é **manter o catálogo pequeno e útil**, não acumular.
