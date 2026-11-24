Sou a Pessoa 1 do Efeito Vitrine, responsavel pela coleta. Continue o
trabalho de onde a sessao anterior parou.

## Como eu quero que voce trabalhe

- comandos em bloco de codigo fechado com `powershell`, um comando por
  bloco, uma linha cada, para o botao Run funcionar
- sem travessao em nenhuma forma, sem construcao "nao e X, e Y", sem triade
  decorativa
- comentario em Python colado no `#` e minusculo, assim: `#faz tal coisa`
- mostre o que mudou, o numero que prova, e o comando. nada de parede de log
- se um comando falhar, mostre o erro inteiro e pare
- feche cada turno com wrap_up

## Onde a coleta esta (24/11/2026, 08:17)

- coletor rodando em janela externa, PID 18396, subiu as 08:12:04
- 142.670 de 229.714 partidas da passada 2, estimativa do proprio coletor
  em torno de 30 horas
- `PARAR_EM = 25/11 22h00`, estendido de 05h00 para recuperar 17 horas
  perdidas. `PARAR_NA_PASSADA = 2`
- para religar: `coleta\retomar_coletor.cmd`. ele religa sozinho ate 20
  vezes, e codigo de saida 3 e a trava de instancia unica, nao um erro

## O que descobri e consertei em 24/11 (commits d8d79d1 e 980fdfc)

O `puuid` que a `league-v4` devolve vem cifrado com a chave que o pediu.
Quando a chave de desenvolvimento vira, a Riot responde
`400 Bad Request - Exception decrypting` para todo `puuid` guardado, a
coleta deixa de achar ID novo e o periodo congela. Foi isso que matou a
coleta em 23/11 as 14:52 e deixou a janela 17 horas parada no `pause`.
O `match_id` nao e cifrado, e foi so por isso que a rodada anterior
sobreviveu 25 horas antes de secar.

Quatro consertos em `coleta/`, todos commitados:

- `resemeia()` refaz as sementes do zero quando nenhum `puuid` do lote e
  decifrado, ate 3 vezes por execucao
- `resposta.json()` entrou no `try`, e codigo HTTP inesperado agora tenta de
  novo e termina em `ErroDaRiot`, que o `baixa_lote` sabe tratar
- `log.exception` grava o traceback no log, e o `puuid` sai do log trocado
  por `<puuid>` com so o tamanho ao lado
- `retomar_coletor.cmd` religa sozinho em vez de parar no `pause`

## A chave da Riot

Vence por volta das 14h45 de 24/11. Basta trocar o valor no `.env` e salvar,
o coletor pausa, rele, percebe que as sementes morreram e refaz as 3870 em
33 segundos. Nunca escreva a chave em codigo, log, commit ou mensagem.

## O que esta sem commit de proposito

- `eventos/montar_eventos.py`: conserto de `event_id` duplicado. Dois videos
  da mesma linha de skin em datas diferentes davam o mesmo `event_id`, e a
  analise agrupa por `event_id`, entao um dos dois desaparecia. Agora sao 60
  eventos distintos, eram 59
- os CSV de `data/processed/`, `analise/relatorio.txt`,
  `analise/efeito_vitrine.html`, os JSON de `site/dados/`, `README.md`
- a pasta `entrega-painel-2026-11-23/` inteira, ainda nao rastreada

## Quando a coleta encerrar, rodar nesta ordem

1. `coleta\agregar.py`
2. `coleta\qualidade.py`
3. `eventos\montar_eventos.py`
4. `analise\efeito_vitrine.py`
5. `coleta\exportar_json.py`
6. os dois geradores dentro de `entrega-painel-2026-11-23/`

## Proximo trabalho grande

Montar o painel na Vercel com os dados atuais e atualizar depois com os
finais. O que precisa esta em `entrega-painel-2026-11-23/`: o docx com
metodologia, resultados e 13 propostas de visualizacao, e
`dados/resultados_por_campeao_evento.csv` com 133 pares campeao e evento ja
medidos. A Vercel serve estatico e nao roda Python, entao o painel le JSON
por `fetch`, sem backend.

Leia `entrega-painel-2026-11-23/LEIA-ME.txt` e `analise/relatorio.txt` para
os numeros, em vez de recalcular.

## Pendencias menores

- tirar o atalho `coletor-efeito-vitrine.cmd` da pasta Startup quando a
  coleta encerrar
- para a Pessoa 3: converter `resultados_por_campeao_evento.csv` em JSON,
  para o painel nao recalcular janelas e percentis no navegador
- Node.js nao esta instalado nesta maquina

Comece conferindo se a coleta ainda esta viva e lendo
`entrega-painel-2026-11-23/LEIA-ME.txt`.
