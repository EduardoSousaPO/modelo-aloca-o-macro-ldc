# Política de Execução — Agent Builder Copilot

Este documento define exatamente o que a skill ABC pode executar diretamente, o que requer confirmação, e o que nunca executa sem supervisão humana.

---

## Categoria 1 — Execução direta (sem pedir confirmação)

Ações que a skill executa imediatamente por serem seguras, locais e reversíveis.

| Ação | Exemplos | Por que é seguro |
|---|---|---|
| Criar arquivos no workspace | soul.md, config.json, SKILL.md, .gitignore | Arquivos novos, não sobrescrevem nada |
| Criar diretórios | `agents/`, `skills/`, `supabase/migrations/` | Estrutura vazia, sem impacto |
| Gerar templates preenchidos | PRD, decision log, checklist | Documentos de planejamento |
| Gerar código/configs | SQL schema, deploy.yml, .env.example | Artefatos do projeto |
| Ler arquivos para análise | Qualquer arquivo no workspace | Somente leitura |
| Scaffolding de projeto | Estrutura completa de diretórios + arquivos | Tudo novo, tudo local |

**Critério:** a ação é local, não destrutiva, e afeta apenas o workspace do projeto atual.

---

## Categoria 2 — Requer confirmação antes de executar

Ações que a skill pode executar mas que têm impacto potencial — pede confirmação primeiro.

| Ação | Exemplos | Risco |
|---|---|---|
| Instalar dependências | `npm install`, `pip install` | Altera node_modules, pode conflitar |
| Sobrescrever arquivo existente | Editar soul.md que o usuário já modificou | Perda de trabalho do usuário |
| Excluir arquivos | Remover template não usado | Irreversível localmente |
| Executar scripts locais | `node script.js`, `python setup.py` | Pode ter side effects |
| Comandos de rede local | `curl` para testar endpoint | Faz requisição externa |
| `git init` ou `git add` | Inicializar repositório | Afeta estado do git |
| Gerar arquivo grande (>200 linhas) | Schema SQL complexo, config extenso | Difícil de revisar se não esperado |

**Como pedir confirmação:**
```
"Vou [ação]. Isso vai [impacto]. Confirma?"
```

Exemplo real:
```
"Vou instalar @supabase/supabase-js e @supabase/auth-helpers-nextjs.
Isso vai adicionar ~2MB ao node_modules. Confirma?"
```

---

## Categoria 3 — Nunca executa sem supervisão (Camada 3)

Ações que a skill **nunca** executa diretamente. Em vez disso, ela:
1. Explica o que precisa ser feito e por quê
2. Gera o comando exato com placeholders claros
3. Pede para o usuário executar e trazer o output
4. Verifica o resultado antes de avançar

| Ação | Exemplos | Por que nunca executa |
|---|---|---|
| SSH para servidor remoto | `ssh root@[IP]` | Acesso a sistema externo |
| Usar credenciais reais | API keys, tokens, senhas | Segurança — skill não deve ter acesso |
| Deploy em produção | `systemctl restart openclaw` no VPS | Ação irreversível em produção |
| Configurar DNS | Alterar registros A, CNAME | Afeta disponibilidade do domínio |
| Push para repositório remoto | `git push origin main` | Afeta repositório compartilhado |
| Criar recursos em serviços pagos | Projeto Supabase, bot Telegram | Pode ter custo financeiro |
| Alterar firewall | `ufw allow`, `iptables` | Segurança do servidor |
| Instalar software no VPS | `apt install`, `npm install -g` | Altera servidor de produção |
| Configurar variáveis no .env real | Escrever API keys em arquivo | Credenciais sensíveis |
| Executar `openclaw` commands no VPS | `openclaw init`, `openclaw config set` | Altera configuração do agente em produção |

**Como guiar sem executar:**

```
"Agora você precisa instalar o OpenClaw no VPS.
Execute estes comandos no terminal SSH do seu VPS:

```bash
npm install -g openclaw
openclaw --version
```

Quando terminar, me diga qual versão foi instalada."
```

---

## Formato dos comandos guiados

Quando gerar comandos para o usuário executar (Categoria 3), use sempre este formato:

1. **Contexto:** O que vai fazer e por quê (1 frase)
2. **Pré-condição:** O que precisa estar pronto antes
3. **Comandos:** Com placeholders claros entre `[colchetes]`
4. **Verificação:** Como confirmar que funcionou
5. **Se falhar:** O que fazer em caso de erro

Exemplo:
```
**Configurar token do Telegram**
Pré-condição: bot já criado no BotFather, token copiado.

```bash
# Adicionar token ao .env do VPS
echo "TELEGRAM_BOT_TOKEN=[SEU_TOKEN_AQUI]" >> ~/.openclaw/.env

# Configurar no OpenClaw
openclaw config set channels.telegram.enabled true

# Reiniciar para aplicar
systemctl restart openclaw

# Verificar
systemctl status openclaw
```

Verificação: o status deve mostrar "active (running)".
Se falhar: verifique o token com `cat ~/.openclaw/.env | grep TELEGRAM` e confirme que o formato é correto.
```

---

## Placeholders padrão

Use sempre estes placeholders nos comandos guiados:

| Placeholder | O que representa |
|---|---|
| `[IP_DO_VPS]` | IP público do VPS Hostinger |
| `[SUA_API_KEY]` | Chave da API do LLM (Anthropic, OpenAI, Google) |
| `[TELEGRAM_BOT_TOKEN]` | Token do bot do Telegram |
| `[SUPABASE_URL]` | URL do projeto Supabase |
| `[SUPABASE_SERVICE_ROLE_KEY]` | Service role key do Supabase |
| `[USUARIO_GITHUB]` | Username do GitHub |
| `[NOME_REPO]` | Nome do repositório GitHub |
| `[NOME_AGENTE]` | Nome do agente definido no discovery |
| `[USUARIO_SSH]` | Usuário SSH (geralmente root) |

**Regra:** Nunca preencha um placeholder com valor real. Nunca invente credenciais.

---

## Detecção automática de camada

Ao processar qualquer solicitação do usuário, classifique primeiro em qual camada a ação se encaixa:

```
Solicitação do usuário
  ├── Envolve credenciais, VPS, SSH, deploy, DNS, produção?
  │   └── SIM → Camada 3 (guiar, nunca executar)
  ├── Envolve instalar pacotes, rede, sobrescrever, deletar?
  │   └── SIM → Camada 2 (pedir confirmação)
  └── É criação/edição/leitura local de arquivos?
      └── SIM → Camada 1 (executar diretamente)
```
