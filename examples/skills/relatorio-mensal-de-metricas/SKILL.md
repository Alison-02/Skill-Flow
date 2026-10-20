---
name: relatorio-mensal-de-metricas
description: Gera o relatório mensal de métricas de um projeto: coleta os dados, calcula os indicadores, compara com o mês anterior, investiga anomalias e publica o resumo. Use ao produzir o relatório de um mês de um projeto.
---

# Relatório mensal de métricas

Rotina fictícia, usada nos exemplos do Skill Flow, para produzir todo mês o relatório de métricas de um projeto. Cada etapa tem um arquivo próprio em `references/`.

## Quando usar
- No início de cada mês, para o mês anterior.
- Quando alguém pedir uma versão revisada de um relatório já publicado.

## Entradas
- `{projeto}`: nome ou código do projeto.
- `{periodo}`: mês de referência, no formato MM/AAAA.
- `{pasta_saida}`: pasta onde ficam os arquivos do relatório.

## Fluxo do mês
1. Coletar os dados (`references/01-coleta-de-dados.md`).
2. Calcular os indicadores (`references/02-calculo-dos-indicadores.md`).
3. Comparar com o mês anterior e investigar anomalias (`references/03-comparacao-e-anomalias.md`).
4. Publicar o resumo (`references/04-publicacao.md`).

## Regras de ouro
- Nunca estime um número que a fonte não trouxe: marque como «sem dado» e siga.
- Toda diferença acima de 2% entre o painel e a fonte precisa de explicação escrita.
- Só publique depois da conferência final.

## Prova de que terminou
Resumo publicado, diferenças explicadas e o registro da execução salvo em `{pasta_saida}`.
