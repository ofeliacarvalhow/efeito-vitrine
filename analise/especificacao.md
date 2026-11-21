# Especificação congelada da análise

Congelada em **20 de novembro de 2026, 21h40**, com **10.764 das 108.572
partidas** da coleta completa, ou seja **10%**. O commit anterior a este,
`62061a7`, é o estado em que os dois recortes foram comparados.

Este arquivo existe por um motivo só: impedir que a escolha do recorte seja
feita depois de olhar qual dá o resultado mais bonito. Sem ele, qualquer
número que a gente apresentar em dezembro pode ser contestado com uma
pergunta que não teria resposta, que é "vocês testaram quantos recortes até
esse dar certo?".

## Honestidade sobre o que isto é e o que não é

Isto **não** é um pré-registro de verdade. Pré-registro se faz antes de ver
qualquer dado, e eu já vi 10% da amostra, e mais: já rodei os dois recortes e
sei o resultado dos dois. O que isto é, e é bem mais fraco, é um congelamento
de especificação antes de os 90% restantes chegarem.

O que dá alguma força a esse congelamento é a direção da escolha. Dos dois
recortes vistos, o escolhido é o que dá o **resultado pior**:

| recorte | skin agrupado | placebo geral |
|---|---|---|
| base colada no lançamento | 18/22, p = 0,002 | 0,025 |
| **base afastada 14 dias (escolhido)** | **15/20, p = 0,021** | **0,375** |

Escolher o p maior é o contrário do que faria quem está pescando resultado.

## A especificação

**Fonte.** `data/processed/daily_pickrate.csv`, gerado pelo
`coleta/agregar.py` a partir das partidas da fila 420 do BR1 entre 4 de
setembro e 18 de novembro de 2026.

**Eventos.** `data/processed/events.csv`, com os quatro tipos: `skin`,
`clipe`, `trailer` e `exposicao`.

**Janelas.** Base nos dias -28 a -15 em relação à data do evento, ou seja
`--antes 14 --recuo 14`. Depois nos dias 0 a +6, ou seja `--depois 7`.
Mínimo de 5 dias de cada lado depois do recorte no período.

**O recuo de 14 dias é a decisão principal deste documento.** A razão é
anterior ao dado: skin fica no servidor de teste umas duas semanas antes de
entrar no jogo, e os vídeos de terceiros mostram isso acontecendo, com os
spotlights das Bruxas em 9 e 10 de setembro contra a skin ao vivo em 23. Uma
base colada no lançamento mede jogadores que já viram a skin.

**Medida.** Taxa de escolha depois dividida pela de antes. A medida principal
usa o pico, que é a melhor janelinha de 3 dias dentro do depois, porque
efeito de novidade dura pouco e média longa dilui.

**Controle.** Todos os campeões sem evento num raio de 28 dias da data e sem
mudança de balanceamento dentro da janela. O percentil do campeão do evento
nessa distribuição é a medida de destaque, com corte em p90.

**Teste principal.** O agrupado por tipo de evento: de todos os campeões de
todos os eventos de um tipo, quantos ficaram acima do típico, com a
probabilidade binomial disso. São quatro tipos testados, então o corte
honesto fica perto de 0,0125, e não 0,05.

**Testes secundários, que são robustez e não conclusão.** O placebo com datas
sorteadas, a contagem de momentos distintos acima de p90, o recorte sem recuo
e os números evento por evento.

## O que fica decidido antes do resultado

Se o teste agrupado de skin ficar abaixo de 0,0125 na amostra completa, com o
recuo de 14, isso se relata como efeito encontrado. Se ficar acima, relata-se
que não houve efeito detectável, mesmo que algum outro recorte dê um número
melhor. Os recortes alternativos entram no relatório como robustez, sempre os
dois, nunca só o que convém.

## O que ainda pode mudar sem quebrar isto

Corrigir defeito de dado, como um campeão faltando ou uma data errada, e
acrescentar evento que a gente descobrir que existe. Isso é conserto de
insumo, não de recorte. Qualquer mudança em janela, em corte de percentil ou
em definição de controle, depois desta data, precisa ser escrita aqui com a
razão e com os dois resultados lado a lado.
