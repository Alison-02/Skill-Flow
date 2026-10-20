# Security · Segurança

🇬🇧 English first, 🇧🇷 português logo abaixo.

---

## 🇬🇧 English

### What Skill Flow does and does not do
- The server listens **only on `127.0.0.1`** and answers only requests whose `Host` header is `127.0.0.1:<port>` or `localhost:<port>` (which also blocks *DNS rebinding*). Every write requires the `X-Skill-Flow: 1` header, which blocks forms on other sites.
- It reads only the skill and `CLAUDE.md` files it discovers in the configured folders. Your global `~/.claude/CLAUDE.md` is one of them: its sections are shown in the local editor and can end up in a flow you generate, so review generated skills before sharing them.
- It writes only to the data folder (`~/.claude/skill-flows` by default, or the one given by `--data`): flows, registered runs, generated skills and `config.json`.
- It **never connects to a database**. It only describes the database so that Claude can query it the way you declared.
- It sends nothing to the internet. In normal use the page makes no external request. Only the self-test (`?selftest=1`) imports the Mermaid diagram library from a CDN, to validate the generated map; without network access that part is skipped.

### Secrets
API keys, passwords and tokens **must not** be typed into any field.
- In **Databases…**, enter only the **name** of an environment variable (for example `MY_API_KEY`).
- Unmistakable credential formats (JWTs, `sk-…`, `ghp_…`, `user:password@` in a URL…) are rejected on save.
- Text that merely *looks like* a secret triggers a confirmation that shows the database, the field and a masked excerpt. Confirming accepts only that exact text.
- This detection is a heuristic safety net, not a guarantee. It does not replace care.
- The generated `SKILL.md` quotes what you wrote in the fields. Review it before sharing.

### Reporting a vulnerability
Please open a **private security advisory** on GitHub (the *Security* tab of the repository). If that is not available, open an issue asking for a private channel, **without** describing the problem. Include what happens, how to reproduce it and the affected version.

Because this is a local tool, the most useful reports involve: reading or writing outside the allowed folders, code execution, access from another origin, and secrets leaking into generated output.

---

## 🇧🇷 Português

### O que o Skill Flow faz e não faz
- O servidor escuta **somente em `127.0.0.1`** e só atende requisições cujo cabeçalho `Host` seja `127.0.0.1:<porta>` ou `localhost:<porta>` (o que também barra ataques de *DNS rebinding*). Toda gravação exige o cabeçalho `X-Skill-Flow: 1`, o que bloqueia formulários de outros sites.
- Lê apenas os arquivos de skill e de `CLAUDE.md` que descobre nas pastas configuradas. O seu `~/.claude/CLAUDE.md` global é um deles: as seções aparecem no editor local e podem acabar num fluxo que você gerar, então revise as skills geradas antes de compartilhar.
- Grava apenas na pasta de dados (`~/.claude/skill-flows` por padrão, ou a de `--data`): fluxos, execuções registradas, skills geradas e o `config.json`.
- **Nunca conecta a um banco de dados.** Só descreve o banco para que o Claude o consulte do jeito que você declarou.
- Não envia nada para a internet. No uso normal, a página não faz nenhuma requisição externa. Só o autoteste (`?selftest=1`) importa a biblioteca de diagramas Mermaid de uma CDN, para validar o mapa gerado; sem rede, esse trecho é pulado.

### Segredos
Chaves de API, senhas e tokens **não devem** ser digitados em nenhum campo.
- Em **Bancos de dados…**, informe só o **nome** de uma variável de ambiente (por exemplo `MINHA_CHAVE_API`).
- Formatos inconfundíveis de credencial (JWT, `sk-…`, `ghp_…`, `usuario:senha@` numa URL…) são recusados ao salvar.
- Texto que apenas *parece* segredo pede uma confirmação que mostra o banco, o campo e um trecho mascarado. Confirmar aceita só aquele texto exato.
- A detecção é uma rede de proteção heurística, não uma garantia. Ela não substitui o cuidado.
- O `SKILL.md` gerado cita o que você escreveu nos campos. Revise-o antes de compartilhar.

### Relatando uma vulnerabilidade
Abra um *security advisory* **privado** no GitHub (aba *Security* do repositório). Se isso não estiver disponível, abra uma issue pedindo um canal privado, **sem** detalhar o problema. Informe o que acontece, como reproduzir e a versão afetada.

Por ser uma ferramenta local, os relatos mais úteis envolvem: leitura ou gravação fora das pastas permitidas, execução de código, acesso de outra origem e vazamento de segredos para a saída gerada.
