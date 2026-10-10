# Como inspecionar o catálogo rapidamente

> Versão simplificada: inspeção manual, sem scripts. Rápido para solo.

---

## Diretório padrão

```
<raiz do ambiente Claude>/skills/
```

Cada subpasta é uma skill. Ler o `SKILL.md` (especialmente o frontmatter `description:`) já diz se serve.

---

## Procedimento

1. Liste as pastas:

    ```bash
    ls <raiz>/skills/
    ```

2. Para cada skill que pareça relevante pelo nome, leia apenas o frontmatter e a primeira seção do `SKILL.md`:

    ```bash
    head -40 <raiz>/skills/<nome>/SKILL.md
    ```

3. Decida em 1 minuto: "resolve o que preciso?"

4. Se resolver → adicione à lista de `skill_existente` no manifest.

---

## Padrões que costumam existir

- `docx`, `pdf`, `pptx`, `xlsx` — geração e manipulação de arquivos Office/PDF
- `frontend-design` — estética de UI
- `mcp-builder` — criar MCPs novos
- `skill-creator` — criar skills novas (meta)
- Skills de Harness (consultor-prd, SDD-avancado, agents-protocol, project-kickoff, skill-scout)

---

## Quando NÃO precisa de skill

- Se a operação é "rodar um comando" → terminal nativo.
- Se a operação é "ler/escrever arquivo" → edit nativo do Claude Code.
- Se a operação é "chamar uma API" → código no próprio projeto.
- Se a operação é "lembrar de uma regra" → `AGENTS.md`.

A pergunta certa: *"o agente precisa de um corpo de conhecimento estruturado para fazer isso bem?"* — se a resposta é "não, só fazer", não é skill.
