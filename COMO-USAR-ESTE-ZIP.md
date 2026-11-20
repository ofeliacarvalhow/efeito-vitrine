# Efeito Vitrine — como usar este zip

Gerado em 20/11/2026. Este zip é o repositório `ofeliacarvalhow/efeito-vitrine`
com a **Etapa 1 pronta e já commitada**, e com o `bannertestt.png` removido.

---

## 1. O que está pronto e o que NÃO está

| etapa | estado |
|---|---|
| **1. Base do repositório** | **PRONTA** — estrutura, `.gitignore`, `.env.example`, `requirements.txt`, `README.md`, `CLAUDE.md` e `data/mock/daily_pickrate.csv` |
| 2. Teste de histórico (`coleta/teste_historico.py`) | **NÃO FEITA** |
| 3. Coletor (`coleta/config.py`, `coleta/coletar.py`) | **NÃO FEITA** |
| 4. Agregação (`coleta/agregar.py`) | **NÃO FEITA** |
| 5. Skins por versão (`coleta/datadragon_skins.py`) | **NÃO FEITA** |
| 6. Qualidade (`coleta/qualidade.py`) | **NÃO FEITA** |

**Nenhuma chamada à API da Riot foi feita ainda.** Ainda não se sabe se o
histórico de 4 de setembro de 2026 está disponível — isso é o que a Etapa 2
responde, e é o maior risco do projeto.

### O que tem dentro

```
CLAUDE.md                     guia do projeto: objetivo, contrato de dados,
                              donos das pastas, comandos, regras da API
README.md                     leia-me do repositório
COMO-USAR-ESTE-ZIP.md         este arquivo
.gitignore                    protege .env, data/raw/, .venv/, *.log
.env.example                  modelo das variáveis (sem valores)
requirements.txt              requests, pandas, python-dotenv, plotly,
                              streamlit, tzdata
coleta/gerar_mock.py          gera os dados falsos
eventos/  analise/  site/     pastas das Pessoas 2 e 3
data/mock/daily_pickrate.csv  3.040 linhas: 76 dias x 40 campeões
data/processed/               vazia; as tabelas finais nascem aqui
data/raw/                     não vem no zip; é criada ao rodar o coletor
.git/                         repositório git de verdade, com o commit da
                              Etapa 1 e o remote origin já configurado
```

### Sobre os dados falsos

`data/mock/daily_pickrate.csv` é **inventado**, só para a Pessoa 2 e a Pessoa 3
trabalharem sem esperar a coleta. Cobre 4/9/2026 a 18/11/2026, 40 campeões
(incluindo os 18 obrigatórios), taxas entre 1% e 15% e ~1000 partidas por dia.
Tem picos artificiais em alguns campeões para dar o que testar na análise.

---

## 2. Instalar (Windows, PowerShell)

Descompacte o zip e entre na pasta. Depois:

```
python -m venv .venv
```

```
.venv\Scripts\python -m pip install -r requirements.txt
```

---

## 3. Criar o `.env` com a chave da Riot

O `.env` **não vem no zip** — chave de API nunca viaja em arquivo compartilhado.

```
copy .env.example .env
```

```
notepad .env
```

Deixe assim, com a sua chave, e salve:

```
RIOT_API_KEY=RGAPI-...
YOUTUBE_API_KEY=
```

A chave de desenvolvimento da Riot **expira a cada 24 horas**. Pegue uma nova
em <https://developer.riotgames.com> e troque só esse valor.

O `.gitignore` já protege o `.env`. Ele nunca deve ir para o GitHub.

---

## 4. Testar que funciona

```
.venv\Scripts\python coleta\gerar_mock.py
```

Deve imprimir `3040 linhas` e `76 dias, 40 campeoes`.

---

## 5. Commitar e subir para o GitHub

O `.git` já vem pronto, com o commit da Etapa 1 feito e o `origin` apontando
para `https://github.com/ofeliacarvalhow/efeito-vitrine`. **Você só precisa dar
push** — o commit já existe.

Antes, confira que nada sensível está indo:

```
git status --short
```

Se aparecer `.env` ou algo dentro de `data/raw/` nessa lista, **pare**. Não
deveria acontecer, mas vale conferir.

```
git log --oneline -2
```

Você deve ver `Etapa 1: base do repositorio...` em cima de `Add files via upload`.

```
git push -u origin main
```

Esse push roda com a **sua** conta do GitHub, no seu computador. (O push a
partir da sessão do Claude foi recusado: o app do Claude não tem permissão de
escrita nesse repositório.)

---

## 6. Avisos

- **Nunca comite o `.env`.** Confira com `git status` antes de cada commit.
- **A chave que foi colada na conversa com a IA deve ser trocada.** Pegue uma
  nova no portal da Riot.
- **Não leia `data/raw/`** para fazer análise ou site. Use `data/mock/`. Essa
  regra está no `CLAUDE.md` e vale para as três pessoas.
- O `data/raw/` existe só no computador de quem roda o coletor e nunca vai
  para o Git.
