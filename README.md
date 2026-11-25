# Efeito Vitrine

Sessenta e um campeões de setenta e quatro que ganharam skin nova foram
escolhidos mais vezes na semana seguinte do que o campeão típico do servidor
no mesmo período. A chance de isso acontecer por acaso é 0,000.

O projeto mede se lançamento de skin e clipe musical de League of Legends
levanta a taxa de escolha dos campeões nas partidas ranqueadas solo, fila
420, do servidor brasileiro. Analisamos de 24 de fevereiro a 18 de novembro
de 2026, 268 dias, no fuso America/Sao_Paulo.

Coletamos 172.678 partidas, uma média de 644 por dia, com 173 campeões e 60
eventos catalogados. Nada do que publicamos identifica jogador: os arquivos
finais são agregados por campeão e por dia.

## O que encontramos

| tipo de evento | acima do típico | chance |
|---|---|---|
| skin | 61 de 74 | 0,000 |
| trailer | 13 de 19 | 0,084 |
| clipe musical | 11 de 16 | 0,105 |
| exposição | 14 de 24 | 0,271 |

"Acima do típico" quer dizer que o campeão subiu mais do que os campeões sem
evento nenhum nas mesmas datas. Medimos pelo percentil do pico de três dias,
e `painel/dados/tipos.json` traz também a contagem pela média de sete dias,
que é a medida conservadora.

O teste de placebo repetiu a medida inteira 200 vezes com a data de cada
evento sorteada. Com datas verdadeiras o método marcou 22 momentos; com
datas sorteadas, uma média de 9,7, e nenhum dos 200 sorteios chegou a 22.

Sobre skin o resultado se sustenta com folga. Sobre clipe musical a direção é
a mesma e quatro vídeos não fecham a conta, então o texto do trabalho e o
painel precisam dizer a mesma coisa sobre isso.

## O repositório

```
coleta/      coleta na API da Riot, agregação, qualidade, exportação
eventos/     catálogo de skins, clipes, trailers e balanceamento
analise/     estatística, antes e depois, gráficos
painel/      os dez JSON que o painel lê
entrega/     o pacote fechado para quem monta o painel
site/        o site em Streamlit
data/        processed, mock e raw
```

`data/raw/` fica só na máquina que rodou a coleta e nunca vai para o Git. Ele
guarda as partidas individuais e os `puuid`. Para desenvolver sem esperar
coleta, use `data/mock/daily_pickrate.csv`, que é inventado e tem o mesmo
formato do contrato.

## O painel

O painel vai para a Vercel como site estático. A Vercel não roda Python,
então o painel não lê os CSV: ele busca JSON com `fetch`, sem backend.

Os dez arquivos estão em `painel/dados/`, somam cerca de 420 KB e têm um
LEIA-ME próprio explicando o formato de cada um.

| arquivo | o que tem |
|---|---|
| `resumo.json` | totais do período, contagem de eventos e os avisos de leitura |
| `serie.json` | a série diária inteira, em listas paralelas |
| `eventos.json` | um objeto por evento, com os campeões dentro |
| `patches.json` | a data de cada patch, medida nas próprias partidas |
| `balanceamento.json` | quem foi mexido em cada patch |
| `resultados.json` | os 133 pares de campeão e evento, com lift, pico, percentil e intervalo |
| `tipos.json` | o teste agrupado por tipo, nas duas medidas |
| `placebo.json` | as 200 contagens do sorteio e a contagem real |
| `controle.json` | a distribuição do grupo de controle em cada data de evento |
| `campeoes.json` | um registro por campeão, com os eventos dele, o balanceamento e quanto foi escolhido |

A série vem em listas paralelas em vez de um objeto por linha, e é só por
isso que ela cabe em 140 KB. `escolhas[campeao][i]` é quantas vezes o campeão
foi escolhido no dia `dias[i]`, e a taxa é esse número dividido por
`partidas_por_dia[i]`.

Todo arquivo em formato de objeto traz dois campos de data. `dados_de` é
quando a coleta foi agregada, e é essa a data do retrato, a que precisa
aparecer em toda tela. `gerado_em` diz só quando o arquivo foi escrito.

Para publicar, aponte a Vercel para a pasta do painel e sirva os arquivos
como estão. Não há passo de build, não há dependência de Node e não há
variável de ambiente para configurar.

### O que o painel não deve recalcular

Percentil, lift, intervalo de confiança e placebo já vêm prontos. Refazer
essas contas no navegador abre espaço para a tela mostrar um número diferente
do que o relatório afirma. O `controle.json` existe por isso: com ele o
histograma de cada campeão e a seta que marca onde ele caiu saem do mesmo
número que a análise usou.

## Como preparar o ambiente

```bash
git clone https://github.com/ofeliacarvalhow/efeito-vitrine.git
cd efeito-vitrine
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

No Windows, troque `.venv/bin/python` por `.venv\Scripts\python.exe`.

A chave da Riot (`RIOT_API_KEY`) sai de <https://developer.riotgames.com> e
vence a cada 24 horas. O `.env` nunca vai para o Git. Quem só vai mexer no
painel ou na análise não precisa de chave nenhuma, porque os dados já estão
no repositório.

## Os comandos

| o que faz | comando |
|---|---|
| gera dados falsos para desenvolver | `.venv/bin/python coleta/gerar_mock.py` |
| roda o coletor | `.venv/bin/python coleta/coletar.py` |
| agrega o bruto na tabela diária | `.venv/bin/python coleta/agregar.py` |
| relatório de qualidade | `.venv/bin/python coleta/qualidade.py` |
| monta o catálogo de eventos | `.venv/bin/python eventos/montar_eventos.py` |
| roda a análise | `.venv/bin/python analise/efeito_vitrine.py` |
| exporta os JSON da coleta | `.venv/bin/python coleta/exportar_json.py` |
| exporta os JSON de resultado | `.venv/bin/python coleta/exportar_json_resultados.py` |
| abre o site em Streamlit | `.venv/bin/python -m streamlit run site/app.py` |

Depois que a coleta encerra, `coleta/fechar_coleta.py` roda tudo isso na
ordem certa, num comando só, e para na hora se algum passo falhar. A ordem
importa: os geradores da pasta `entrega/` leem o relatório da análise e os
CSV da própria pasta, então regerar o documento antes de atualizar essas
cópias produz um arquivo com número velho e cara de novo.

## O contrato de dados

Mudança em qualquer um destes arquivos quebra o trabalho de quem está do
outro lado, então ela precisa ser combinada antes.

`data/processed/daily_pickrate.csv`

| coluna | descrição |
|---|---|
| `date` | AAAA-MM-DD, fuso America/Sao_Paulo |
| `champion` | `championName` da Riot, como `KSante` ou `LeeSin` |
| `games_total` | partidas daquele dia |
| `picks` | escolhas do campeão naquele dia |
| `pick_rate` | `picks / games_total` |

Há uma linha para cada campeão em cada dia, inclusive nos dias em que ele não
foi escolhido nenhuma vez.

Os outros três seguem o mesmo princípio. `events.csv` tem `event_id`,
`champion`, `event_type`, `event_date`, `title`, `youtube_id` e `views`.
`balance_changes.csv` tem `patch`, `patch_date`, `champion` e `change`.
`new_skins.csv` tem `version`, `champion`, `skin_num` e `skin_name`.

## Como ler os números sem errar

A amostra dá peso igual aos dez elos, de Ferro a Challenger, enquanto a
população real do servidor é quase toda de elo baixo. A taxa daqui não é a
taxa do BR1. O que vale comparar entre dias é a taxa, nunca a contagem de
partidas.

Campeão com menos de 100 escolhas na janela de antes vem marcado com
`pouca_amostra`. Em campeão pouco escolhido, meia dúzia de escolhas a mais já
vira lift de duas vezes, e esse número não deve ser lido sozinho.

Clipe e trailer do mesmo lançamento saem com poucos dias de diferença e medem
quase o mesmo pedaço da série. O campo `sobrepostos` em `tipos.json` conta
quantas linhas estão nessa situação, e nelas um tipo não é evidência
independente do outro.

## A coleta

A coleta encerrou em 25 de novembro de 2026 ao meio-dia. Esta seção fica como
registro de como ela funcionava, caso o projeto volte a coletar.

O coletor respeita dois limites ao mesmo tempo, 20 requisições por segundo e
100 a cada 2 minutos, e lê os cabeçalhos `X-App-Rate-Limit` e
`X-Method-Rate-Limit` quando eles vêm. Em 429 ele espera o `Retry-After` e
repete. Em 5xx tenta três vezes com espera crescente. Em 404 pula. Em 401 ou
403 pausa e fica relendo o `.env` a cada 60 segundos até a chave mudar.

O `puuid` que a API devolve vem cifrado com a chave que o pediu. Quando a
chave vence, a Riot responde `400 Bad Request, Exception decrypting` para
todo `puuid` guardado, e o coletor deixa de achar ID novo. Por isso ele refaz
as sementes do zero quando nenhum `puuid` do lote é decifrado, o que leva uns
33 segundos.

Rode o coletor sempre numa janela própria, nunca dentro de um terminal
embutido em outro aplicativo. Se o aplicativo fecha, o shell morre e leva o
coletor junto, sem erro no log: a última linha é um progresso normal e depois
vem o silêncio. Isso já custou duas horas de coleta.

`coleta/retomar_coletor.cmd` religa a coleta retomando do SQLite, sem refazer
sementes e sem baixar de novo o que já está no `matches.jsonl`. Se já houver
um coletor rodando, a trava de instância única faz o segundo sair na hora com
um recado em vez de brigar pelo banco.

## Privacidade

Nenhum arquivo publicado contém jogador, nome de invocador, `puuid` ou
`matchId`. Os `puuid` ficam só no SQLite local, em `data/raw/coleta.sqlite`,
que está no `.gitignore`. A chave da Riot nunca entra em código, log, commit
ou mensagem.

As regras do repositório, com os limites da API e o que não pode ser lido,
estão em [`CLAUDE.md`](CLAUDE.md).

<!-- inicio do dicionario de dados -->

## Dicionario de dados

Numeros de 2026-11-25 12:39, fuso America/Sao_Paulo. O `coleta/qualidade.py` reescreve esta secao, entao ela nunca fica velha. O relatorio completo, com partidas dia por dia e versoes do jogo por semana, fica em `data/processed/qualidade.txt`.

### `daily_pickrate.csv`

| coluna | tipo | descricao |
|---|---|---|
| `date` | texto `AAAA-MM-DD` | dia no fuso America/Sao_Paulo |
| `champion` | texto | `championName` da Riot, como `KSante` |
| `games_total` | inteiro | partidas daquele dia na amostra |
| `picks` | inteiro | vezes que o campeao foi escolhido no dia |
| `pick_rate` | decimal | `picks / games_total`, 6 casas |

Estado atual: **46364 linhas**, 268 dias x 173 campeoes, a partir de **172678 partidas** da fila 420. 268 dos 268 dias do periodo tem partida.

Ha uma linha para cada campeao em cada dia do periodo, inclusive dias com zero escolhas. Em dia sem partida nenhuma, `games_total` e `pick_rate` ficam em zero. A lista de campeoes sai dos proprios dados, entao cresce conforme campeoes novos aparecem na coleta.

### `new_skins.csv`

| coluna | tipo | descricao |
|---|---|---|
| `version` | texto | patch que trouxe a skin, como `16.18` |
| `champion` | texto | mesmo nome usado em `daily_pickrate.csv` |
| `skin_num` | inteiro | numero da skin no Data Dragon, nunca 0 |
| `skin_name` | texto | nome em pt_BR |

Estado atual: **97 linhas**, das quais **97 sao lancamento de skin**, em 86 campeoes, e o resto sao cromas de skins que ja existiam.

**Cuidado ao montar o `events.csv`.** Croma tem nome no formato `Nome da Skin (Cor)` e nao e lancamento nenhum. Uma skin com nove cromas ocupa dez linhas aqui, e contar as dez como evento faz o mesmo lancamento valer dez vezes na analise. Filtre nome com parentese.

O Data Dragon sai dias depois do patch, entao `version` diz qual patch trouxe a skin, nao quando ela saiu. A data oficial do patch entra em `balance_changes.csv`, preenchida a mao.

Para esse preenchimento, o `qualidade.txt` ja traz a data de cada patch **medida nas partidas do BR1**: o dia em que a versao nova aparece pela primeira vez, com o dia da semana e o vao desde o patch anterior. Quando a amostra pegou o dia em que as duas versoes convivem, a data e exata. Quando nao pegou, sai o intervalo em que o patch cabe, em vez de um dia inventado.

### Como a amostra foi montada

As partidas vem de jogadores sorteados de IRON a CHALLENGER no BR1, e o periodo e varrido em semanas de segunda a domingo, em rodizio, para a amostra ficar parelha em todos os dias a qualquer momento em que a coleta pare. Isso significa que `games_total` nao e o total de partidas jogadas no servidor naquele dia: e o total que esta na amostra. A taxa de escolha e o que vale comparar entre dias, e nao a contagem bruta.

<!-- fim do dicionario de dados -->
