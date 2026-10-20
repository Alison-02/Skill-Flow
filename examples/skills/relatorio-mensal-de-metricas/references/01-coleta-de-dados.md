# Coleta de dados

Primeira etapa do relatório mensal: juntar tudo o que será usado nas etapas seguintes.

## 1. Fontes de dados
- Painel de produto: exporte a tabela do mês em CSV.
- Banco de métricas: consulte `metricas_mensais` pelo projeto e pelo período.
- Planilha de metas, se existir na `{pasta_saida}`.

## 2. Conferir a completude
- Todos os dias do mês aparecem no CSV do painel?
- O banco devolve exatamente uma linha para o projeto e o período?
- Se faltar algo, registre o que falta e pergunte antes de seguir.

## 3. Registrar o que faltou
Anote em `{pasta_saida}/pendencias.md` cada dado que não veio, com a fonte e a data da tentativa.

## Prova de que terminou
Os arquivos coletados estão em `{pasta_saida}` e a lista de pendências (mesmo que vazia) foi escrita.
