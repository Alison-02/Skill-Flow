# Contributing · Contribuindo

🇬🇧 English first, 🇧🇷 português logo abaixo.

---

## 🇬🇧 English

Thanks for wanting to help. Skill Flow is small on purpose: one Python file (the local server), one HTML file (the editor) and a tiny Claude Code hook. There is no build step and no dependency to install.

### Ground rules
- **Keep it dependency-free.** The server uses only the Python standard library; the editor is plain JavaScript in a single `index.html`. Please do not add a bundler, a framework or `pip`/`npm` packages.
- **Never store secrets.** Nothing the editor writes may contain a password or API key, only the *name* of an environment variable. See [SECURITY.md](SECURITY.md).
- **The server only talks to `127.0.0.1`** and never connects to a database. Changes that break either promise will not be merged.
- **Use fictional data** in examples, tests and screenshots. No real company names, people, paths or credentials.
- The interface and the generated `SKILL.md` are in **Brazilian Portuguese** for now. Translations are welcome, but please open an issue first so we agree on how language is selected.

### Setup
```bash
git clone https://github.com/Alison-02/Skill-Flow.git
cd skill-flow
python app/server.py --data examples/data      # serves at http://127.0.0.1:8765
```
Open `http://127.0.0.1:8765/?demo=1` to load the sample flow.

### Tests
Run all of them before opening a pull request:
```bash
python tests/test_server.py          # secret detection, config safety, paths (no browser needed)
python tests/test_editor.py          # ~450 checks of the editor in headless Chrome/Chromium/Edge
python tests/test_content_drift.py   # change-detection end to end (same requirement)
claude plugin test .                 # the /skill-flow launcher (needs Claude Code)
```
`test_editor.py` and `test_content_drift.py` look for Chrome, Chromium or Edge; point the `CHROME` environment variable at the executable if yours is somewhere unusual. The tests run against a temporary copy of `examples/` and with a fake home folder, so they never read or write your real skills and flows.

### Where things live
| Path | What |
|---|---|
| `app/server.py` | local server: reads skills and CLAUDE.md, stores flows, runs and generated files, secret detection |
| `app/index.html` | the whole editor (HTML, CSS, JS) and its in-page self-test (`?selftest=1`) |
| `hooks/` | the `/skill-flow` command for Claude Code |
| `examples/` | fictional skills, CLAUDE.md and databases used by the demo and the tests |
| `tests/` | the test scripts above |

### Pull requests
- One topic per pull request, with a short description of the *why*.
- Add or adjust a test for the behaviour you change. In the editor, add a check to `selfTest()` in `app/index.html`.
- Update [CHANGELOG.md](CHANGELOG.md).

---

## 🇧🇷 Português

Obrigado por querer ajudar. O Skill Flow é pequeno de propósito: um arquivo Python (o servidor local), um arquivo HTML (o editor) e um gancho mínimo para o Claude Code. Não há etapa de build nem dependência para instalar.

### Regras do jogo
- **Sem dependências.** O servidor usa só a biblioteca padrão do Python; o editor é JavaScript puro em um único `index.html`. Não adicione bundler, framework nem pacotes `pip`/`npm`.
- **Nunca guarde segredos.** Nada que o editor grava pode conter senha ou chave de API, só o *nome* de uma variável de ambiente. Veja o [SECURITY.md](SECURITY.md).
- **O servidor só fala com `127.0.0.1`** e nunca conecta a banco de dados. Mudanças que quebrem uma dessas promessas não serão aceitas.
- **Use dados fictícios** em exemplos, testes e capturas de tela. Nada de empresas, pessoas, caminhos ou credenciais reais.
- A interface e o `SKILL.md` gerado estão em **português do Brasil** por enquanto. Traduções são bem-vindas, mas abra antes uma issue para combinarmos como o idioma é escolhido.

### Preparar o ambiente
```bash
git clone https://github.com/Alison-02/Skill-Flow.git
cd skill-flow
python app/server.py --data examples/data      # abre em http://127.0.0.1:8765
```
Abra `http://127.0.0.1:8765/?demo=1` para carregar o fluxo de exemplo.

### Testes
Rode todos antes de abrir um pull request:
```bash
python tests/test_server.py          # detecção de segredos, segurança do config, caminhos (sem navegador)
python tests/test_editor.py          # ~450 verificações do editor em Chrome/Chromium/Edge sem janela
python tests/test_content_drift.py   # detecção de mudança de ponta a ponta (mesmo requisito)
claude plugin test .                 # o atalho /skill-flow (precisa do Claude Code)
```
Os dois testes que usam navegador procuram Chrome, Chromium ou Edge; aponte a variável `CHROME` para o executável se o seu estiver em outro lugar. Os testes rodam sobre uma cópia temporária de `examples/` e com uma pasta pessoal falsa, então nunca leem nem gravam as suas skills e fluxos de verdade.

### Pull requests
- Um assunto por pull request, com uma descrição curta do *porquê*.
- Inclua ou ajuste um teste para o que você mudar. No editor, acrescente uma verificação em `selfTest()` no `app/index.html`.
- Atualize o [CHANGELOG.md](CHANGELOG.md).
