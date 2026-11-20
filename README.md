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
