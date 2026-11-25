# Prompt para montar o painel

Cole o texto abaixo, inteiro, na primeira mensagem para o Claude, junto com
o repositório aberto. Ele descreve o projeto, os dados, a metodologia e o
que precisa ser construído.

---

Estou te passando um projeto acadêmico pronto, com os dados coletados e a
análise fechada. Falta construir o painel web. Leia este briefing inteiro
antes de escrever qualquer código, e confira no repositório o que eu afirmar
aqui, porque os números mudam quando a coleta roda de novo.

## O que o projeto mede

Se o lançamento de uma skin ou de um clipe musical de League of Legends faz
o campeão ser mais escolhido nas partidas ranqueadas solo, fila 420, do
servidor brasileiro.

Coletamos 172.678 partidas entre 24 de fevereiro e 18 de novembro de 2026,
268 dias, no fuso America/Sao_Paulo. São 644 partidas por dia em média, 173
campeões e 60 eventos catalogados. A coleta encerrou em 25 de novembro ao
meio-dia.

O resultado principal: 61 de 74 campeões que ganharam skin nova foram
escolhidos mais vezes na semana seguinte do que o campeão típico do servidor
nas mesmas datas. A chance de isso acontecer por acaso é 0,000.

## Como a medida funciona

Entender isto importa, porque o painel mostra esses números e não pode
contradizer o texto escrito.

Para cada evento, comparamos duas janelas da série do campeão. A janela de
antes tem 14 dias, a de depois tem 7, e entre o fim do antes e a data do
evento há um recuo de 14 dias, para a expectativa do lançamento não
contaminar a base de comparação.

O **lift** é a taxa média do depois dividida pela taxa média do antes. O
valor 1,00 significa nenhuma mudança e 1,50 significa cinquenta por cento
mais escolhas.

O **pico** é a mesma conta usando a melhor janelinha de 3 dias dentro do
depois. Ele existe porque efeito de novidade dura pouco e média longa
dilui. Num teste contra dados falsos, um pico plantado de 2,1 vezes aparece
como 1,41 na média de 14 dias.

O **percentil** é o núcleo do método. O lift de um campeão sozinho não diz
nada, porque o servidor inteiro se move junto. Então calculamos o mesmo lift
nas mesmas datas para todos os campeões que não tiveram evento nenhum e não
levaram mudança de balanceamento dentro da janela, e perguntamos onde o
campeão com evento cai nessa distribuição. O percentil 50 é o comportamento
típico do servidor naquele período. O percentil 90 é a fronteira do
destaque. O grupo de controle tem entre 119 e 155 campeões conforme a data.

O **intervalo de confiança** é de 95 por cento, pelo método de Wilson. Quando
o intervalo do antes cruza o do depois, a amostra não sustenta a diferença, e
a linha vem marcada.

O **teste agrupado por tipo** é o número com que o trabalho conclui. Juntando
todos os campeões de todos os eventos do mesmo tipo, quantos ficaram acima do
típico? Se o evento não fizesse nada, a resposta esperada seria metade, como
em moeda honesta. A chance vem da distribuição binomial.

O **teste de placebo** repetiu a medida inteira 200 vezes com a data de cada
evento sorteada, mantendo os campeões verdadeiros. Com datas verdadeiras o
método marcou 22 momentos distintos. Com datas sorteadas, média de 9,7, e
nenhum dos 200 sorteios chegou a 22. O sorteio usa semente fixa, então o
resultado é reproduzível.

## Os números que o painel vai mostrar

Teste por tipo, pelo percentil do pico:

| tipo | acima do típico | chance | leitura |
|---|---|---|---|
| skin | 61 de 74 | 0,000 | efeito claro |
| trailer | 13 de 19 | 0,084 | sugestivo, não conclusivo |
| clipe | 11 de 16 | 0,105 | sugestivo, não conclusivo |
| exposição | 14 de 24 | 0,271 | sem sinal |

Pela média de 7 dias, que é a medida conservadora, a skin dá 60 de 74 e o
trailer dá 12 de 19 com chance 0,180. As duas contagens estão em
`tipos.json`, e qual delas o trabalho adota ainda não foi decidido. O painel
precisa mostrar a mesma medida que o texto final adotar. Pergunte antes de
escolher.

Entre os 23 pares que se destacaram, o lift mediano é 1,73 vezes. Juntando
os 74 campeões com skin, inclusive os que não reagiram, o campeão típico
passou a ser escolhido 16 por cento mais vezes na semana seguinte.

## O repositório

```
README.md          a porta de entrada, com o resultado e os comandos
CLAUDE.md          as regras do repositório, incluindo as de escrita
painel/dados/      os dez JSON que o painel lê, com LEIA-ME próprio
entrega/           o documento, os CSV e os relatórios
analise/           a estatística em Python, e o relatorio.txt
coleta/            a coleta na API da Riot e os exportadores
eventos/           o catálogo de skins, clipes e balanceamento
site/              uma versão local em Streamlit, que não é o painel
data/processed/    as tabelas do contrato de dados, em CSV
data/mock/         dados falsos no mesmo formato, para desenvolver
```

Não existe `data/raw/` no que você recebeu, e isso é proposital. O bruto tem
partidas individuais e identificadores de jogador, e fica só na máquina que
coletou.

## Os dez arquivos de dados

Ficam em `painel/dados/`, somam cerca de 420 KB e são buscados com `fetch`.
Leia `painel/dados/LEIA-ME.txt`, que detalha cada um.

`resumo.json` tem `periodo`, `partidas`, `partidas_por_dia`, `campeoes`,
`eventos` por tipo e `aviso`.

`serie.json` tem `dias`, `campeoes`, `partidas_por_dia` e `escolhas`. Vem em
listas paralelas, e é por isso que cabe em 143 KB. `escolhas[campeao][i]` é
quantas vezes o campeão foi escolhido no dia `dias[i]`, e a taxa é esse
número dividido por `partidas_por_dia[i]`.

`eventos.json` é uma lista de 60, com `id`, `tipo`, `data`, `titulo`,
`youtube_id`, `views` e `campeoes`.

`patches.json` é uma lista de 20, com `patch`, `data`, `exata` e `partidas`.
O campo `exata` diz se a data foi medida nas próprias partidas ou estimada.

`balanceamento.json` é uma lista de 175, com `patch`, `data`, `campeao` e
`mudanca`.

`resultados.json` tem `janela`, `contagem` e `pares`. Cada par traz `evento`,
`tipo`, `data`, `campeao`, `taxa_antes`, `taxa_depois`, `lift`, `percentil`,
`lift_do_pico`, `percentil_do_pico`, `picks_antes`, `picks_depois`,
`jogos_antes`, `jogos_depois`, `ic_antes`, `ic_depois`,
`intervalos_se_cruzam`, `pouca_amostra`, `destaque`, `campeoes_no_controle` e
`lift_mediano_do_controle`. São 133 pares.

`tipos.json` tem `medida`, que nomeia o critério, e `tipos`, com `acima`,
`de`, `fracao`, `ic`, `chance`, `eventos`, `sobrepostos` e um bloco
`pelo_lift` com a mesma conta pela outra medida.

`placebo.json` tem `contagens` com os 200 valores, `real`, `media`,
`minimo`, `maximo`, `percentil_95`, `empataram_ou_passaram` e `chance`.

`controle.json` tem, por `event_id`, as listas ordenadas `pico` e `lift` do
grupo de controle naquela data, mais `campeoes` e `fora_por_mexida`. Cobre 56
dos 60 eventos. Os outros quatro caem perto da borda do período e não sobra
janela para montar grupo de controle.

`campeoes.json` tem a mesma informação virada do avesso, um registro por
campeão, com `eventos` em ordem de data, `balanceamento`,
`escolhas_no_periodo`, `taxa_media` e `destaques`. Mais `sem_evento`, que
lista os 96 campeões sem evento nenhum, que formam o grupo de controle.

## O que o painel não deve calcular sozinho

Percentil, lift, intervalo e placebo já vêm prontos. Se o navegador refizer
essas contas, a tela pode mostrar um número diferente do que o documento
afirma, e aí o trabalho se contradiz na frente de quem está avaliando.

O `controle.json` existe exatamente por isso. Com ele, o histograma de cada
campeão e a seta que marca onde ele caiu saem do mesmo número que a análise
usou.

O navegador pode filtrar, ordenar, agrupar para exibição e desenhar. Não
pode recalcular.

## O que precisa aparecer em toda tela

A data do retrato, que é o campo `dados_de`, e não o `gerado_em`. O
`dados_de` diz quando a coleta foi agregada; o `gerado_em` diz quando o
arquivo foi escrito, e pode ser horas depois. Mostrar o segundo faz o painel
parecer mais novo do que é.

As limitações da seção 11 do documento precisam estar visíveis, em página
própria linkada do topo, não em letra pequena no rodapé. As principais:

A amostra dá peso igual aos dez elos, de Ferro a Challenger, enquanto a
população real do servidor é quase toda de elo baixo. A taxa daqui não é a
taxa do BR1. O que vale comparar entre dias é a taxa, nunca a contagem de
partidas.

O estudo é observacional. Não houve sorteio de quem recebe skin, então a
conclusão é de associação, e não de causa provada.

Skin e balanceamento às vezes andam juntos no mesmo patch, e nesses casos as
duas explicações se sobrepõem. O relatório marca esses casos.

Clipe, trailer e skin da mesma linha saem em poucos dias e medem pedaços
sobrepostos da série. O campo `sobrepostos` em `tipos.json` conta quantas
linhas estão nessa situação.

Campeão com menos de 100 escolhas na janela de antes vem com
`pouca_amostra` verdadeiro. Esse número não deve ser lido sozinho, e a tela
precisa marcá-lo visualmente, em cinza ou com um selo.

## As telas

A seção 13 do documento em `entrega/Efeito-Vitrine-painel-especificacao.docx`
descreve treze telas, cada uma com o que ela responde, como se parece e de
onde vem o dado. As cinco primeiras sustentam o argumento e as outras servem
para explorar. Leia essa seção antes de desenhar qualquer coisa.

A seção 13.14 traz as decisões visuais que valem para todas as telas: quatro
cores fixas, uma por tipo de evento, cinza sempre para o grupo de controle,
taxa em porcentagem com uma casa, lift no formato 1,78x, e o painel
funcionando no celular, porque é nele que o trabalho vai ser apresentado.

## Como publicar

A Vercel serve arquivo estático e não roda Python. O painel busca os JSON
com `fetch`, sem backend, sem passo de build e sem variável de ambiente.
Aponte a Vercel para a pasta do painel e sirva os arquivos como estão.

## Onde ler mais

`entrega/Efeito-Vitrine-painel-especificacao.docx` é o documento completo,
com metodologia nas seções 9.1 a 9.7, resultados na 10, limitações na 11 e
as telas na 13.

`analise/relatorio.txt` tem 663 linhas, um bloco para cada um dos 56 eventos
medidos, com todo campeão, taxa antes e depois, lift, percentil, pico e
escolhas cruas, mais o teste do grupo e as ressalvas.

`entrega/qualidade-da-amostra.txt` tem partidas dia por dia e versões do jogo
por semana.

`painel/dados/LEIA-ME.txt` detalha o formato de cada JSON.

## Uma coisa que ainda não foi decidida

Se o trabalho conclui sobre clipe musical ou limita a conclusão à skin. O
dado sustenta a afirmação sobre skin com folga. Sobre clipe, a direção é a
mesma e quatro vídeos não fecham a conta. As duas escolhas são defensáveis, e
a escolha precisa aparecer no texto e no painel de forma coerente.

Pergunte antes de escrever qualquer frase conclusiva sobre clipe.
