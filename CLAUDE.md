# Efeito Vitrine — guia do projeto

> ## REGRA EM DESTAQUE
> **NUNCA leia arquivos de `data/raw/`.** Esses dados brutos existem apenas no
> computador da Pessoa 1 e contêm partidas individuais. Para desenvolver
> análise e site, **use `data/mock/`**. Se precisar de dados reais agregados,
> **peça uma amostra de `data/processed/`** — não tente reconstruí-la a partir
> do bruto, não abra `data/raw/matches.jsonl` e não escreva código que o leia
> (a única exceção são os scripts `coleta/agregar.py` e `coleta/qualidade.py`,
> que já existem para isso).

## Objetivo

Medir se **lançamentos de skins e clipes musicais de League of Legends
aumentam a taxa de escolha (pick rate) dos campeões** nas partidas ranqueadas
solo (fila 420) do servidor brasileiro (**BR1**).

O período analisado é **4 de setembro de 2026 a 18 de novembro de 2026**,
reconstruído com o filtro de datas (`startTime`/`endTime`) da API de partidas
da Riot. Todas as datas usam o fuso **America/Sao_Paulo**.

Os dados finais são **somente agregados por campeão e por dia**. Nenhum
jogador é identificado em nenhum arquivo publicado.

## Contrato de dados (NÃO PODE MUDAR)

Qualquer mudança nestes arquivos quebra o trabalho das outras pessoas.

### `data/processed/daily_pickrate.csv`
| coluna | descrição |
|---|---|
| `date` | AAAA-MM-DD, fuso America/Sao_Paulo |
| `champion` | `championName` da Riot (ex.: `KSante`, `Kaisa`, `LeeSin`) |
| `games_total` | total de partidas daquele dia |
| `picks` | quantas vezes o campeão foi escolhido naquele dia |
| `pick_rate` | `picks / games_total` |

Há **uma linha para cada campeão em cada dia**, inclusive dias com zero escolhas.

### `data/processed/events.csv`
`event_id`, `champion`, `event_type`, `event_date`, `title`, `youtube_id`, `views`

### `data/processed/balance_changes.csv`
`patch`, `patch_date`, `champion`, `change`

### `data/processed/new_skins.csv` (gerado pela coleta)
`version`, `champion`, `skin_num`, `skin_name`

## Quem cuida de cada pasta

| pasta | responsável |
|---|---|
| `coleta/` | **Pessoa 1** — coleta na API da Riot, agregação, qualidade, skins |
| `eventos/` | **Pessoa 2** — skins/clipes, YouTube, mudanças de balanceamento |
| `analise/` | **Pessoa 2** — estatística, antes/depois, gráficos |
| `site/` | **Pessoa 3** — Streamlit, textos, datas oficiais dos patches |

Mexa só na sua pasta. Mudanças no contrato de dados precisam ser combinadas
com as três pessoas.

## Comandos

Sempre com o ambiente virtual ativado.

```bash
# criar o ambiente (uma vez)
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

| o que | comando |
|---|---|
| gerar dados falsos para desenvolver | `.venv/bin/python coleta/gerar_mock.py` |
| testar se o histórico existe na API | `.venv/bin/python coleta/teste_historico.py` |
| **rodar o coletor** (horas, terminal separado) | `.venv/bin/python coleta/coletar.py` |
| agregar o bruto na tabela diária | `.venv/bin/python coleta/agregar.py` |
| listar skins novas por versão | `.venv/bin/python coleta/datadragon_skins.py` |
| relatório de qualidade dos dados | `.venv/bin/python coleta/qualidade.py` |
| abrir o site | `.venv/bin/python -m streamlit run site/app.py` |

No Windows, troque `.venv/bin/python` por `.venv\Scripts\python`.

## Chave da API

- A chave fica em `.env`, na raiz, **que nunca vai para o Git**.
- Modelo das variáveis: `.env.example`.
- **A chave de desenvolvimento da Riot expira a cada 24 horas.** Quando isso
  acontece, o coletor pausa sozinho, avisa no terminal e relê o `.env` a cada
  60 segundos. Basta pegar uma chave nova em
  <https://developer.riotgames.com>, trocar o valor no `.env` e salvar — o
  coletor continua de onde parou, sem reiniciar.
- **Nunca** escreva a chave em código, em log, em commit ou em mensagem.
- Existe **uma única chave** para o projeto. Não use várias chaves.

## Limites da API que o código respeita

- 20 requisições por segundo **e** 100 a cada 2 minutos, ao mesmo tempo.
- Lê os cabeçalhos `X-App-Rate-Limit` e `X-Method-Rate-Limit` quando vêm.
- `429`: espera o `Retry-After` e repete. `5xx`: até 3 tentativas com espera
  crescente. `404`: pula. `401`/`403`: pausa e espera a chave nova.
- Jogadores em `https://br1.api.riotgames.com`, partidas em
  `https://americas.api.riotgames.com`, sempre com o cabeçalho `X-Riot-Token`.

## Privacidade

Não identifique jogadores. Os `puuid` ficam só no SQLite local
(`data/raw/coleta.sqlite`), que não vai para o Git. Nada publicado contém
jogador, nome de invocador, `puuid` ou `matchId`.
