# Efeito Vitrine, guia do repositório

> ## REGRA EM DESTAQUE
> **Nunca leia arquivos de `data/raw/`.** Esses dados brutos existem apenas
> na máquina que rodou a coleta e contêm partidas individuais. Para
> desenvolver análise e painel, use `data/mock/`. Se precisar de dados reais
> agregados, peça uma amostra de `data/processed/`. Não tente reconstruí-la
> a partir do bruto, não abra `data/raw/matches.jsonl` e não escreva código
> que o leia. As únicas exceções são `coleta/agregar.py`,
> `coleta/qualidade.py` e `coleta/fechar_coleta.py`, que já existem para
> isso.

## O que o projeto mede

Se lançamentos de skins e clipes musicais de League of Legends levantam a
taxa de escolha dos campeões nas partidas ranqueadas solo, fila 420, do
servidor brasileiro.

O período vai de 24 de fevereiro a 18 de novembro de 2026, 268 dias,
reconstruído com o filtro de datas da API de partidas da Riot. Todas as
datas usam o fuso America/Sao_Paulo.

A coleta encerrou em 25 de novembro de 2026 ao meio-dia, com 172.678
partidas. Os dados publicados são agregados por campeão e por dia, e nenhum
jogador aparece em arquivo nenhum.

## As pastas

| pasta | o que tem |
|---|---|
| `coleta/` | coleta na API da Riot, agregação, qualidade, skins, exportação |
| `eventos/` | catálogo de skins, clipes, trailers e balanceamento |
| `analise/` | estatística, antes e depois, gráficos |
| `painel/dados/` | os nove JSON que o painel busca com `fetch` |
| `entrega/` | o pacote fechado para quem monta o painel |
| `site/` | o site em Streamlit |
| `data/processed/` | as tabelas do contrato de dados |
| `data/mock/` | dados falsos, no mesmo formato, para desenvolver |
| `data/raw/` | o bruto, fora do Git, só na máquina que coletou |

Trabalhamos em frentes separadas, coleta, catálogo e análise, painel. Mexa na
frente que é sua. Mudança no contrato de dados precisa ser combinada com
todo mundo antes.

## Contrato de dados

Qualquer mudança nestes arquivos quebra o trabalho de quem está do outro
lado.

### `data/processed/daily_pickrate.csv`

| coluna | descrição |
|---|---|
| `date` | AAAA-MM-DD, fuso America/Sao_Paulo |
| `champion` | `championName` da Riot, como `KSante`, `Kaisa`, `LeeSin` |
| `games_total` | total de partidas daquele dia |
| `picks` | quantas vezes o campeão foi escolhido naquele dia |
| `pick_rate` | `picks / games_total` |

Há uma linha para cada campeão em cada dia, inclusive dias com zero
escolhas.

### Os outros três

`events.csv` tem `event_id`, `champion`, `event_type`, `event_date`,
`title`, `youtube_id` e `views`.

`balance_changes.csv` tem `patch`, `patch_date`, `champion` e `change`.

`new_skins.csv` tem `version`, `champion`, `skin_num` e `skin_name`, e é
gerado pela coleta.

## Os JSON do painel

`painel/dados/` tem nove arquivos, cerca de 370 KB, com LEIA-ME próprio. Os
cinco primeiros saem de `coleta/exportar_json.py` e carregam o dado da
coleta. Os quatro de resultado saem de `coleta/exportar_json_resultados.py`
e carregam o que a análise concluiu, para o painel não refazer conta no
navegador e arriscar mostrar número diferente do relatório.

Todo arquivo em formato de objeto traz `dados_de`, que é quando a coleta foi
agregada, e `gerado_em`, que é quando o arquivo foi escrito. A data do
retrato é `dados_de`.

## Comandos

Sempre com o ambiente virtual ativado.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

| o que | comando |
|---|---|
| gerar dados falsos para desenvolver | `.venv/bin/python coleta/gerar_mock.py` |
| rodar o coletor, em janela separada | `.venv/bin/python coleta/coletar.py` |
| agregar o bruto na tabela diária | `.venv/bin/python coleta/agregar.py` |
| relatório de qualidade | `.venv/bin/python coleta/qualidade.py` |
| montar o catálogo de eventos | `.venv/bin/python eventos/montar_eventos.py` |
| rodar a análise | `.venv/bin/python analise/efeito_vitrine.py` |
| exportar os JSON da coleta | `.venv/bin/python coleta/exportar_json.py` |
| exportar os JSON de resultado | `.venv/bin/python coleta/exportar_json_resultados.py` |
| fechar a coleta, tudo na ordem | `.venv/bin/python coleta/fechar_coleta.py` |
| abrir o site | `.venv/bin/python -m streamlit run site/app.py` |

No Windows, troque `.venv/bin/python` por `.venv\Scripts\python.exe`.

`coleta/fechar_coleta.py` roda o ciclo inteiro em onze passos e para na hora
se algum falhar. A ordem importa, porque os geradores de `entrega/` leem o
relatório da análise e os CSV da própria pasta.

## Chave da API

A chave fica em `.env`, na raiz, que nunca vai para o Git. O modelo das
variáveis está em `.env.example`.

A chave de desenvolvimento da Riot expira a cada 24 horas. Quando isso
acontece, o coletor pausa sozinho, avisa no terminal e relê o `.env` a cada
60 segundos. Pegue uma chave nova em <https://developer.riotgames.com>,
troque o valor no `.env` e salve, e ele continua de onde parou.

Nunca escreva a chave em código, em log, em commit ou em mensagem. Existe
uma única chave para o projeto.

## Limites da API que o código respeita

20 requisições por segundo e 100 a cada 2 minutos, ao mesmo tempo. O cliente
lê os cabeçalhos `X-App-Rate-Limit` e `X-Method-Rate-Limit` quando eles vêm.

Em 429 espera o `Retry-After` e repete. Em 5xx tenta até três vezes com
espera crescente. Em 404 pula. Em 401 ou 403 pausa e espera a chave nova.

Jogadores em `https://br1.api.riotgames.com`, partidas em
`https://americas.api.riotgames.com`, sempre com o cabeçalho `X-Riot-Token`.

O `puuid` vem cifrado com a chave que o pediu. Quando a chave vira, a Riot
responde `400 Bad Request, Exception decrypting` para todo `puuid` guardado,
e o coletor refaz as sementes do zero.

## Privacidade

Não identifique jogadores. Os `puuid` ficam só no SQLite local, em
`data/raw/coleta.sqlite`, que não vai para o Git. Nada publicado contém
jogador, nome de invocador, `puuid` ou `matchId`.

## Como escrever no projeto

Vale para README, LEIA-ME, mensagens de commit, comentários de código e
texto que aparece na tela.

Nada de travessão, em nenhuma forma. Troque por vírgula, parênteses, ponto
final ou reescreva a frase. Dois-pontos só antes de enumeração ou citação,
nunca para criar suspense. Sem vírgula antes do "e" em enumeração. Sem
setas, símbolos fora do teclado comum, ícones ou emojis.

Nada de "não é X, é Y" nem de suas variações. Nada de grupo de três por
ritmo: use a quantidade de itens que o conteúdo pede. Nada de pergunta
retórica respondida logo em seguida, nem de frase curta de efeito fechando
parágrafo.

Corte palavra inflada: crucial, fundamental, essencial, robusto, poderoso,
inovador, potencializar, alavancar, otimizar, mergulhar, jornada, panorama,
ecossistema, holístico, marco, divisor de águas. Corte expressão de
palestra: "no mundo atual", "cada vez mais", "é importante ressaltar",
"vale destacar", "nesse sentido", "dessa forma", "em suma". Se a frase só
existia para carregar a expressão, apague a frase.

Corte frase que diz que algo é importante sem mostrar por quê. Corte
gerúndio que comenta o que acabou de ser dito. Prefira verbo a substantivo
derivado: "analisamos" em vez de "a realização da análise".

Comece pelo fato ou pelo problema. Termine quando o conteúdo terminar, sem
resumo do que já foi dito e sem otimismo genérico. Varie o tamanho das
frases e o começo dos parágrafos. Título com maiúscula só na primeira
palavra e em nomes próprios.

Comentário em Python fica colado no `#` e em minúscula, assim:
`#faz tal coisa`.

Fale no plural sobre as etapas do trabalho. Não atribua pasta a pessoa
numerada.
