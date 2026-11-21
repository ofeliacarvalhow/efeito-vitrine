# Validação externa da taxa de escolha

Conferência feita em 20 de novembro de 2026, com 10.593 partidas coletadas,
contra o [op.gg](https://op.gg/lol/champions?region=br&tier=all), servidor
BR, patch 16.23, todos os elos.

Ela existe para responder uma pergunta que nenhum teste interno responde: os
números que o nosso pipeline produz têm alguma relação com a realidade? Erro
de denominador, contagem dobrada ou unidade trocada passariam por todos os
testes internos sem deixar rastro, e apareceriam aqui na hora.

## O resultado

| campeão | nosso | op.gg | razão |
|---|---|---|---|
| Lux | 14,67% | 18,09% | 0,81 |
| Caitlyn | 13,74% | 17,82% | 0,77 |
| Kai'Sa | 15,43% | 16,61% | 0,93 |
| Ezreal | 15,07% | 16,09% | 0,94 |
| Yone | 14,35% | 15,29% | 0,94 |
| Jhin | 14,32% | 14,88% | 0,96 |
| Miss Fortune | 8,02% | 13,45% | 0,60 |
| Kayn | 10,84% | 13,41% | 0,81 |
| Yasuo | 18,97% | 12,44% | 1,53 |
| Jinx | 13,14% | 11,84% | 1,11 |
| Seraphine | 11,27% | 11,38% | 0,99 |
| Ahri | 11,00% | 11,21% | 0,98 |
| Nami | 13,00% | 11,09% | 1,17 |
| Lulu | 13,68% | 10,97% | 1,25 |
| Ashe | 8,91% | 10,73% | 0,83 |
| Thresh | 9,84% | 9,58% | 1,03 |

**Razão média: 0,98.** Soma nos 16 campeões: 206,2% contra 214,9%, uma
diferença de 4%. Correlação de postos: 0,62.

## Como ler isso

A razão média de 0,98 é o número que importa. Ela diz que a nossa taxa de
escolha está na mesma escala de uma fonte independente, construída por outra
gente a partir de outra amostra. Qualquer erro grosseiro de pipeline, do tipo
dividir pelo número errado ou contar escolha duas vezes, apareceria como
razão 0,1 ou 2,0, e não é o caso em nenhum dos 16.

A correlação de postos de 0,62 é positiva mas longe de 1, e isso também é
esperado, por três motivos que não são defeito:

O período é outro. O op.gg mostra o patch 16.23 sozinho, e a nossa taxa é a
média de 76 dias cobrindo sete patches, de 16.17 a 16.23. Campeão que subiu
ou caiu no último patch aparece diferente.

O elo é outro. Semeamos 400 jogadores por elo em dez elos, o que dá peso
igual a Ferro e a Challenger, enquanto o op.gg com `tier=all` reflete a
população real, que é quase toda de elo baixo. Taxa de escolha muda com o
elo, então a nossa amostra é de um BR mais bem ranqueado que o BR de verdade.

Os números do op.gg vieram somados por função, de uma tabela que carrega em
partes. Campeão jogado em muitas funções pode ter ficado subcontado do lado
deles. A Miss Fortune, com razão 0,60, é a candidata mais provável a isso.

O Yasuo, com razão 1,53, é o outro extremo e não tem explicação fechada. Pode
ser o nosso período mais longo pegando o pico da skin True Damage dele em
outubro, pode ser função faltando do lado do op.gg, pode ser o viés de elo
indo na direção contrária do esperado. Fica registrado como ponto aberto.

## O que essa conferência não prova

Que a nossa taxa é a taxa do BR. Ela não é, pelo viés de elo descrito acima,
e nunca pretendeu ser. O que ela prova é que o pipeline mede o que diz medir,
na escala certa, e que a comparação de antes e depois dentro da nossa própria
amostra está apoiada em números que não estão quebrados.
