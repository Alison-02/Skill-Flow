# Changelog

Todas as mudanças relevantes ficam aqui. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.5.0] — 2026-10-20 — primeira versão pública

### Editor
- Canvas de nós com ligações, ramos com condição escrita, saída «se houver dúvida», laços («para cada» e «repita até»), subfluxos, grupos, notas, minimapa, desfazer e refazer.
- Organização automática na horizontal ou em camadas, barra de comandos (Ctrl+K) e atalhos de teclado.
- Fontes dos nós: skills inteiras, seções de skills, arquivos de referência, seções de CLAUDE.md, ferramentas, bancos de dados.
- Parâmetros de entrada com valores calculados (mês, ano, datas) e a janela «Gerar com valores».
- Verificação da lógica do fluxo, com avisos e erros apontados no próprio nó.
- Detecção de mudança de conteúdo: avisa quando um trecho de skill usado no fluxo mudou ou sumiu, mostra o que mudou e permite trocar a fonte.
- Medir: registro de execuções feitas com e sem o fluxo, para comparar a qualidade.

### Consulta ao banco
- Janela «Bancos de dados…» para declarar bancos, tabelas, colunas e a forma de acesso (ferramenta MCP, comando, arquivo, HTTP ou perguntar ao usuário).
- Nó «Consulta ao banco» com campos, filtros, ordem e o que se espera (1 registro, o primeiro ou uma lista).
- SQL gerado por motor: PostgreSQL, MySQL, SQL Server e SQLite.
- Valores devolvidos viram `{nomes}` usados nas etapas seguintes, com verificação de uso antes do preenchimento.
- Chaves e senhas nunca são gravadas: o editor e o servidor recusam formatos inconfundíveis e perguntam diante de textos suspeitos.

### Saída
- `SKILL.md` orquestrador com regras de execução, entradas, mapa Mermaid, etapas numeradas e prova de cada etapa.
- Registro da execução (`registro-da-execucao.md`) com o caminho percorrido.

### Projeto
- Servidor local em Python (só biblioteca padrão), restrito a `127.0.0.1`.
- Atalho `/skill-flow` para o Claude Code.
- Exemplos em `examples/` e testes em `tests/`.
