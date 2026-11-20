# Efeito Vitrine

Projeto acadêmico que mede se **lançamentos de skins e clipes musicais de
League of Legends aumentam a taxa de escolha dos campeões** nas partidas
ranqueadas solo (fila 420) do servidor brasileiro (**BR1**).

Período analisado: **4/9/2026 a 18/11/2026**, fuso **America/Sao_Paulo**.
Os dados publicados são **apenas agregados por campeão e por dia** — nenhum
jogador é identificado.

## Como preparar

```bash
git clone https://github.com/ofeliacarvalhow/efeito-vitrine.git
cd efeito-vitrine
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Depois copie `.env.example` para `.env` e preencha as chaves:

```bash
cp .env.example .env
```

A chave da Riot (`RIOT_API_KEY`) sai de <https://developer.riotgames.com> e
**expira a cada 24 horas**. O `.env` nunca vai para o Git.

No Windows, use `.venv\Scripts\python` em vez de `.venv/bin/python`.

## Pastas

```
coleta/     coleta na API da Riot, agregação, qualidade, skins   (Pessoa 1)
eventos/    skins, clipes, YouTube, balanceamento               (Pessoa 2)
analise/    estatística e gráficos                              (Pessoa 2)
site/       site em Streamlit                                   (Pessoa 3)
data/raw/       dados brutos — SÓ no computador da Pessoa 1, fora do Git
data/processed/ tabelas finais do contrato de dados
data/mock/      dados FALSOS para desenvolver sem esperar a coleta
```

**Para desenvolver análise e site, use `data/mock/daily_pickrate.csv`.**
Não leia `data/raw/`.

## Scripts

| o que faz | comando |
|---|---|
| gera dados falsos | `.venv/bin/python coleta/gerar_mock.py` |
| testa o histórico na API | `.venv/bin/python coleta/teste_historico.py` |
| roda o coletor | `.venv/bin/python coleta/coletar.py` |
| agrega o bruto na tabela diária | `.venv/bin/python coleta/agregar.py` |
| lista skins novas por versão | `.venv/bin/python coleta/datadragon_skins.py` |
| relatório de qualidade | `.venv/bin/python coleta/qualidade.py` |

## Contrato de dados

`data/processed/daily_pickrate.csv`

| coluna | descrição |
|---|---|
| `date` | AAAA-MM-DD, fuso America/Sao_Paulo |
| `champion` | `championName` da Riot |
| `games_total` | partidas do dia |
| `picks` | escolhas do campeão no dia |
| `pick_rate` | `picks / games_total` |

`data/processed/events.csv` — `event_id`, `champion`, `event_type`,
`event_date`, `title`, `youtube_id`, `views`

`data/processed/balance_changes.csv` — `patch`, `patch_date`, `champion`,
`change`

`data/processed/new_skins.csv` — `version`, `champion`, `skin_num`,
`skin_name`

Detalhes de responsabilidade, limites da API e regras do projeto estão em
[`CLAUDE.md`](CLAUDE.md).

<!-- inicio do dicionario de dados -->

## Dicionario de dados

Numeros de 2026-11-20 17:02, fuso America/Sao_Paulo. O `coleta/qualidade.py` reescreve esta secao, entao ela nunca fica velha. O relatorio completo, com partidas dia por dia e versoes do jogo por semana, fica em `data/processed/qualidade.txt`.

### `daily_pickrate.csv`

| coluna | tipo | descricao |
|---|---|---|
| `date` | texto `AAAA-MM-DD` | dia no fuso America/Sao_Paulo |
| `champion` | texto | `championName` da Riot, como `KSante` |
| `games_total` | inteiro | partidas daquele dia na amostra |
| `picks` | inteiro | vezes que o campeao foi escolhido no dia |
| `pick_rate` | decimal | `picks / games_total`, 6 casas |

Estado atual: **13148 linhas**, 76 dias x 173 campeoes, a partir de **2346 partidas** da fila 420. 76 dos 76 dias do periodo tem partida.

Ha uma linha para cada campeao em cada dia do periodo, inclusive dias com zero escolhas. Em dia sem partida nenhuma, `games_total` e `pick_rate` ficam em zero. A lista de campeoes sai dos proprios dados, entao cresce conforme campeoes novos aparecem na coleta.

### `new_skins.csv`

| coluna | tipo | descricao |
|---|---|---|
| `version` | texto | patch que trouxe a skin, como `16.18` |
| `champion` | texto | mesmo nome usado em `daily_pickrate.csv` |
| `skin_num` | inteiro | numero da skin no Data Dragon, nunca 0 |
| `skin_name` | texto | nome em pt_BR |

Estado atual: **0 linhas**. O Data Dragon sai dias depois do patch, entao `version` diz qual patch trouxe a skin, nao quando ela saiu. A data oficial do patch entra em `balance_changes.csv`, preenchida pela Pessoa 3.

### Como a amostra foi montada

As partidas vem de jogadores sorteados de IRON a CHALLENGER no BR1, e o periodo e varrido em semanas de segunda a domingo, em rodizio, para a amostra ficar parelha em todos os dias a qualquer momento em que a coleta pare. Isso significa que `games_total` nao e o total de partidas jogadas no servidor naquele dia: e o total que esta na amostra. A taxa de escolha e o que vale comparar entre dias, e nao a contagem bruta.

<!-- fim do dicionario de dados -->
