# Cálculo dos indicadores

Segunda etapa: transformar os dados coletados nos indicadores do relatório.

## 1. Visão geral
Os indicadores são calculados sempre a partir dos dados brutos coletados, nunca de um relatório anterior.

## 2. Definições
- **Usuários ativos**: usuários distintos com ao menos um evento no mês.
- **Receita**: soma das cobranças pagas no mês, em reais.
- **Churn**: usuários ativos no mês anterior que não aparecem no mês atual, dividido pelos ativos do mês anterior.

## 3. Arredondamento e unidades
- Valores monetários com duas casas decimais.
- Percentuais com uma casa decimal.
- Nunca misture reais e milhares de reais na mesma tabela.

## 4. Recalcular os indicadores
1. Carregue os dados brutos da `{pasta_saida}`.
2. Calcule usuários ativos, receita e churn.
3. Guarde o resultado em `{pasta_saida}/indicadores.csv`.

## 5. Comparar com o painel
Compare cada indicador com o valor mostrado no painel e anote a diferença absoluta e percentual.

## 6. Segmentar por plano
Repita o cálculo por plano (gratuito, básico, avançado). A soma dos planos deve bater com o total.

## 7. Consolidar o resultado (resumo, tabela e gráfico)
Monte uma tabela com os indicadores, o total e a variação sobre o mês anterior. O gráfico é opcional.

## Prova de que terminou
O arquivo `indicadores.csv` existe, a soma dos planos bate com o total e as diferenças contra o painel estão anotadas.
