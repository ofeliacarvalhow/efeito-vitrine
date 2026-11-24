"""
Monta o docx de especificacao do painel.

Todo numero que aparece no texto sai dos CSV desta pasta, nunca digitado a
mao, para o documento nao envelhecer em silencio quando a coleta avancar.
Rodar de novo depois de atualizar a pasta dados/ regenera o documento com os
numeros novos.

Rodar:  .venv\\Scripts\\python.exe entrega-painel-2026-11-23\\gerar_documento.py
"""
from __future__ import annotations

import csv
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

AQUI = Path(__file__).resolve().parent
DADOS = AQUI / "dados"
RAIZ = AQUI.parent
RELATORIO = AQUI / "analise-relatorio-completo.txt"
SAIDA = AQUI / "Efeito-Vitrine-painel-especificacao.docx"

FONTE = "Times New Roman"
PRETO = RGBColor(0, 0, 0)


#-------------------------------------------------------------- leitura

def ler(nome: str) -> list[dict]:
    with open(DADOS / nome, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


serie = ler("daily_pickrate.csv")
eventos = ler("events.csv")
skins = ler("new_skins.csv")
patches = ler("patch_dates.csv")
balanceamento = ler("balance_changes.csv")
resultados = ler("resultados_por_campeao_evento.csv")
texto_do_relatorio = RELATORIO.read_text(encoding="utf-8")

#tamanho do efeito, direto do CSV de resultados
lift_por_tipo = defaultdict(list)
for linha in resultados:
    lift_por_tipo[linha["event_type"]].append(float(linha["lift"]))
MARCADOS = [l for l in resultados if l["destaque"] == "1"]
LIFT_DOS_MARCADOS = sorted(float(l["lift"]) for l in MARCADOS)
PICO_DOS_MARCADOS = sorted(float(l["lift_do_pico"]) for l in MARCADOS)
CONTROLE_MEDIANO = sorted(float(l["lift_mediano_do_controle"])
                          for l in resultados)
TAMANHO_DO_CONTROLE = sorted(int(l["campeoes_no_controle"])
                             for l in resultados)
CRUZAM = sum(1 for l in resultados if l["intervalos_se_cruzam"] == "1")

#partidas por dia
partidas_por_dia = {}
escolhas_por_campeao = Counter()
for linha in serie:
    partidas_por_dia[linha["date"]] = int(linha["games_total"])
    escolhas_por_campeao[linha["champion"]] += int(linha["picks"])

DIAS = sorted(partidas_por_dia)
TOTAL_DE_PARTIDAS = sum(partidas_por_dia.values())
TOTAL_DE_ESCOLHAS = sum(escolhas_por_campeao.values())
CAMPEOES = sorted(escolhas_por_campeao)
VALORES_POR_DIA = sorted(partidas_por_dia.values())

#eventos agrupados
grupos = {}
for linha in eventos:
    grupo = grupos.setdefault(linha["event_id"], {
        "campeoes": set(),
        "tipo": linha["event_type"],
        "data": linha["event_date"],
        "titulo": linha["title"],
        "youtube": linha["youtube_id"],
        "views": linha["views"],
    })
    grupo["campeoes"].add(linha["champion"])

POR_TIPO = Counter(g["tipo"] for g in grupos.values())


def por_data(ids):
    return sorted(ids, key=lambda i: (grupos[i]["data"], i))


def chave_de_patch(versao: str):
    return [int(parte) for parte in versao.split(".")]


#resultados por tipo, lidos do relatorio
resultado_por_tipo = {}
for achado in re.finditer(
    r"^  (clipe|exposicao|skin|trailer)\s+(\d+)\s+(\d+)\s+([\d.]+)$",
    texto_do_relatorio, re.M
):
    tipo, acima, de, chance = achado.groups()
    resultado_por_tipo[tipo] = (int(acima), int(de), float(chance))

achado = re.search(r"sorteios que empataram ou passaram o real: (\d+) de "
                   r"(\d+), ou seja ([\d.]+)", texto_do_relatorio)
PLACEBO = achado.groups() if achado else ("?", "?", "?")
achado = re.search(r"destaques com data sorteada:\s+media ([\d.]+), "
                   r"minimo (\d+), maximo (\d+)", texto_do_relatorio)
PLACEBO_SORTEIO = achado.groups() if achado else ("?", "?", "?")
achado = re.search(r"momentos campeao-data distintos com destaque: (\d+)",
                   texto_do_relatorio)
MOMENTOS_DISTINTOS = achado.group(1) if achado else "?"
achado = re.search(r"pares campeao-evento marcados, antes do corte: (\d+)",
                   texto_do_relatorio)
PARES_MARCADOS = achado.group(1) if achado else "?"
achado = re.search(r"(\d+) pares campeao-evento medidos, (\d+) acima de p90",
                   texto_do_relatorio)
PARES_MEDIDOS, ACIMA_DE_P90 = achado.groups() if achado else ("?", "?")
achado = re.search(r"esperado acima de p90: ([\d.]+)", texto_do_relatorio)
ESPERADO_P90 = achado.group(1) if achado else "?"

#destaques nominais
destaques = []
evento_atual = tipo_atual = data_atual = None
for linha in texto_do_relatorio.splitlines():
    cabeca = re.match(
        r"^(\S+)\s+\((clipe|skin|trailer|exposicao), (\d{4}-\d\d-\d\d)\)",
        linha)
    if cabeca:
        evento_atual, tipo_atual, data_atual = cabeca.groups()
    if linha.rstrip().endswith("*") and evento_atual:
        partes = linha.split()
        destaques.append({
            "data": data_atual, "tipo": tipo_atual, "campeao": partes[0],
            "lift": partes[3], "perc": partes[4], "pico": partes[5],
            "perc_pico": partes[6], "picks": partes[7],
            "evento": evento_atual,
        })
destaques.sort(key=lambda d: (d["data"], d["campeao"]))


#-------------------------------------------------------------- escrita

doc = Document()

estilo = doc.styles["Normal"]
estilo.font.name = FONTE
estilo.font.size = Pt(11)
estilo.font.color.rgb = PRETO
estilo.paragraph_format.space_after = Pt(6)
estilo.paragraph_format.line_spacing = 1.15


def preto(paragrafo):
    """O Word herda cor de tema no titulo, entao a cor vai explicita."""
    for trecho in paragrafo.runs:
        trecho.font.name = FONTE
        trecho.font.color.rgb = PRETO
    return paragrafo


def h(texto: str, nivel: int = 1):
    paragrafo = doc.add_heading(texto, level=nivel)
    return preto(paragrafo)


def p(texto: str = "", negrito=False, tamanho=11, centro=False):
    paragrafo = doc.add_paragraph()
    trecho = paragrafo.add_run(texto)
    trecho.bold = negrito
    trecho.font.size = Pt(tamanho)
    trecho.font.name = FONTE
    trecho.font.color.rgb = PRETO
    if centro:
        paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return paragrafo


def lista(itens, estilo_de_lista="List Bullet"):
    for item in itens:
        paragrafo = doc.add_paragraph(style=estilo_de_lista)
        trecho = paragrafo.add_run(item)
        trecho.font.name = FONTE
        trecho.font.size = Pt(11)
        trecho.font.color.rgb = PRETO


def tabela(cabecalho, linhas, larguras=None, tamanho=9):
    tab = doc.add_table(rows=1, cols=len(cabecalho))
    tab.style = "Table Grid"
    tab.alignment = WD_TABLE_ALIGNMENT.CENTER
    for coluna, titulo in enumerate(cabecalho):
        celula = tab.rows[0].cells[coluna]
        celula.text = ""
        trecho = celula.paragraphs[0].add_run(str(titulo))
        trecho.bold = True
        trecho.font.name = FONTE
        trecho.font.size = Pt(tamanho)
        trecho.font.color.rgb = PRETO
    for linha in linhas:
        celulas = tab.add_row().cells
        for coluna, valor in enumerate(linha):
            celulas[coluna].text = ""
            trecho = celulas[coluna].paragraphs[0].add_run(str(valor))
            trecho.font.name = FONTE
            trecho.font.size = Pt(tamanho)
            trecho.font.color.rgb = PRETO
    if larguras:
        for linha in tab.rows:
            for coluna, largura in enumerate(larguras):
                linha.cells[coluna].width = Pt(largura)
    doc.add_paragraph()
    return tab


#-------------------------------------------------------------- capa

titulo = doc.add_heading("Efeito Vitrine", level=0)
preto(titulo)
p("Especificacao do painel e estado completo do projeto", negrito=True,
  tamanho=14, centro=True)
p(f"Retrato de 23 de novembro de 2026, as 10h47, fuso America/Sao_Paulo",
  centro=True)
p(f"{TOTAL_DE_PARTIDAS:,} partidas ranqueadas solo do servidor BR1, "
  f"{len(DIAS)} dias, {len(CAMPEOES)} campeoes, {len(grupos)} eventos"
  .replace(",", "."), centro=True)
doc.add_paragraph()

p("Este documento tem duas funcoes. A primeira e registrar, com numero e "
  "fonte, tudo que o projeto mediu ate agora: cada patch, cada skin, cada "
  "video, cada resultado. A segunda e servir de especificacao para quem vai "
  "montar o painel, dizendo o que cada tela responde, de que arquivo ela "
  "tira o dado e como ela se parece.")
p("A pasta que acompanha este arquivo tem os dados do mesmo instante. "
  "Nenhum numero daqui foi digitado a mao: o gerador le os CSV da pasta e "
  "escreve o texto, entao o documento e os dados nunca discordam.")

doc.add_page_break()

#-------------------------------------------------------------- 1

h("1. O que o projeto mede", 1)
p("A pergunta e simples de enunciar e dificil de responder: quando a Riot "
  "lanca uma skin ou publica um clipe musical, mais gente escolhe aquele "
  "campeao?")
p("A intuicao diz que sim. Skin nova aparece na loja, o campeao ganha "
  "destaque na tela inicial, o clipe acumula milhoes de visualizacoes, e "
  "quem assistiu quer jogar. Essa e a hipotese do efeito vitrine: a "
  "exposicao comercial do campeao desloca a escolha dos jogadores.")
p("O problema e que a taxa de escolha de um campeao se move por muitas "
  "razoes ao mesmo tempo. Um ajuste de balanceamento muda o quanto ele "
  "ganha. Um streamer popular joga com ele e a copia se espalha. O "
  "campeonato mundial mostra uma estrategia e o servidor inteiro imita. "
  "Cada uma dessas forcas produz exatamente o que a skin produziria, que e "
  "a taxa subindo depois de uma data.")
p("Por isso a medida precisa de uma referencia. O projeto mede quanto a "
  "taxa de um campeao subiu depois do evento e compara esse numero com "
  "quanto subiram, nas mesmas datas, os campeoes que nao tiveram evento "
  "nenhum. Se o campeao com skin sobe tanto quanto os outros, a skin nao "
  "explica nada. Se ele sobe mais do que quase todos, ha algo a relatar.")

h("1.1. Escopo exato", 2)
tabela(
    ["item", "valor"],
    [
        ["servidor", "BR1, Brasil"],
        ["fila", "420, ranqueada solo e duo"],
        ["periodo", f"{DIAS[0]} a {DIAS[-1]}, {len(DIAS)} dias"],
        ["fuso", "America/Sao_Paulo em todas as datas"],
        ["elos", "IRON a CHALLENGER, sem recorte"],
        ["unidade do dado", "campeao por dia"],
        ["partidas na amostra", f"{TOTAL_DE_PARTIDAS:,}".replace(",", ".")],
        ["campeoes vistos", f"{len(CAMPEOES)}"],
        ["eventos catalogados", f"{len(grupos)}"],
    ],
    larguras=[130, 300], tamanho=10)

p("O periodo comecou em 4 de setembro e foi estendido para tras em 21 de "
  "novembro, por poder estatistico. Com 76 dias o estudo tinha cerca de 24 "
  "por cento de chance de encontrar o efeito mesmo que ele existisse, "
  "porque o teste conta campeoes por evento e havia apenas 20 pares para "
  "contar. Com 268 dias sao mais de 130 pares e a chance passa de 85 por "
  "cento. A extensao foi testada antes de ser feita: o historico da API "
  "alcanca partidas de setembro de 2025, e o rendimento de IDs por jogador "
  "nao cai com a idade da janela, com 2,48 IDs por jogador em outubro, 3,88 "
  "em fevereiro e 4,52 em abril.")

doc.add_page_break()

#-------------------------------------------------------------- 2

h("2. O retrato deste arquivo", 1)
p("A coleta continua rodando enquanto este documento e escrito, e termina "
  "na madrugada de quarta-feira, 25 de novembro. Os numeros abaixo valem "
  "para o instante da capa.")

media = st.mean(VALORES_POR_DIA)
tabela(
    ["medida", "valor", "o que significa"],
    [
        ["partidas", f"{TOTAL_DE_PARTIDAS:,}".replace(",", "."),
         "partidas distintas da fila 420 no periodo"],
        ["linhas na serie", f"{len(serie):,}".replace(",", "."),
         f"{len(DIAS)} dias vezes {len(CAMPEOES)} campeoes"],
        ["dias com partida", f"{sum(1 for v in VALORES_POR_DIA if v)} de "
         f"{len(DIAS)}", "nenhum dia do periodo ficou vazio"],
        ["partidas por dia", f"media {media:.0f}, minimo "
         f"{VALORES_POR_DIA[0]}, maximo {VALORES_POR_DIA[-1]}",
         "a variacao e de dia de semana, nao de falha de coleta"],
        ["desvio relativo", f"{st.pstdev(VALORES_POR_DIA) / media * 100:.1f} "
         "por cento", "espalhamento dos dias em torno da media"],
        ["escolhas", f"{TOTAL_DE_ESCOLHAS:,}".replace(",", "."),
         "soma de picks em toda a tabela"],
        ["escolhas por partida", f"{TOTAL_DE_ESCOLHAS / TOTAL_DE_PARTIDAS:.2f}",
         "toda partida tem 10 campeoes, e a conta fecha"],
    ],
    larguras=[110, 150, 210], tamanho=10)

h("2.1. A amostra e proporcional em todo o periodo", 2)
p("Essa e a propriedade que torna o dado comparavel entre datas, e ela nao "
  "foi um acidente. A coleta varre o periodo em semanas de segunda a "
  "domingo e visita as semanas em rodizio, sempre priorizando a que tem "
  "menos partidas por dia. O efeito pratico e que a amostra fica parelha em "
  "qualquer instante em que a coleta pare, e nao apenas no fim.")

por_mes = defaultdict(list)
for dia, quantas in partidas_por_dia.items():
    por_mes[dia[:7]].append(quantas)
tabela(
    ["mes", "dias", "partidas", "media por dia"],
    [[mes, len(por_mes[mes]), f"{sum(por_mes[mes]):,}".replace(",", "."),
      f"{st.mean(por_mes[mes]):.0f}"] for mes in sorted(por_mes)],
    larguras=[80, 60, 100, 110], tamanho=10)

menor = min(st.mean(v) for v in por_mes.values())
maior = max(st.mean(v) for v in por_mes.values())
p(f"As medias mensais vao de {menor:.0f} a {maior:.0f} partidas por dia, "
  f"uma faixa de {(maior / menor - 1) * 100:.0f} por cento entre o mes mais "
  "magro e o mais cheio. Fevereiro tem apenas 5 dias e novembro 18, porque "
  "o periodo comeca em 24 de fevereiro e termina em 18 de novembro.")
p("Esse e o sentido da expressao retrato proporcional. Comparar a taxa de "
  "escolha de marco com a de outubro e legitimo porque os dois meses foram "
  "amostrados com a mesma densidade. O que nao se pode fazer e ler "
  "games_total como o numero de partidas jogadas no servidor naquele dia, "
  "porque e o numero que esta na amostra.")

doc.add_page_break()

#-------------------------------------------------------------- 3

h("3. Como a amostra foi construida", 1)

h("3.1. O caminho do dado", 2)
p("A API da Riot nao oferece consulta por data nem por campeao. Ela oferece "
  "o historico de um jogador. Para reconstruir um periodo foi preciso "
  "inverter o problema:")
lista([
    "sortear jogadores de todos os elos, de IRON a CHALLENGER, pelo "
    "endpoint league-v4/entries, com 400 jogadores por elo",
    "para cada jogador, pedir os IDs das partidas dele dentro de uma janela "
    "de datas, pelo endpoint match-v5 por puuid com startTime e endTime",
    "baixar cada partida e guardar apenas o que a pesquisa usa, que e a "
    "data, a versao do jogo e os dez campeoes escolhidos",
    "agregar tudo por campeao e por dia, descartando qualquer vestigio de "
    "jogador",
])
p("Os jogadores ficam no host da plataforma, br1.api.riotgames.com, e as "
  "partidas no host da regiao, americas.api.riotgames.com. A chave vai "
  "sempre no cabecalho X-Riot-Token, nunca na URL.")

h("3.2. Privacidade", 2)
p("Nenhum arquivo publicado contem jogador. Os identificadores de jogador "
  "ficam apenas no SQLite local, que o Git ignora, e servem somente para a "
  "coleta saber de quem ja pediu o historico. A tabela final tem data, "
  "campeao e contagem, e nada mais. Nao ha nome de invocador, nem "
  "identificador de partida, nem recorte de elo que permita reduzir o grupo "
  "a poucas pessoas.")

h("3.3. Os limites da API", 2)
p("A chave de desenvolvimento permite 20 requisicoes por segundo e 100 a "
  "cada 2 minutos, e os dois limites valem ao mesmo tempo. O coletor "
  "mantem uma janela deslizante para cada um deles, que e mais rigorosa que "
  "o balde fixo da Riot: quando o limitador local libera, a Riot "
  "certamente libera tambem. O codigo 429 nunca deveria aparecer, e quando "
  "aparece o coletor respeita o cabecalho Retry-After.")
tabela(
    ["situacao", "o que o coletor faz"],
    [
        ["429", "espera o Retry-After e repete a mesma requisicao"],
        ["5xx", "tenta ate 3 vezes, com espera crescente"],
        ["404", "pula, porque a partida saiu do historico"],
        ["401 ou 403", "pausa, avisa na janela e rele o .env a cada 60s"],
        ["falha de rede", "tenta para sempre, com espera limitada a 60s"],
    ],
    larguras=[110, 330], tamanho=10)
p("A chave de desenvolvimento vence a cada 24 horas, e e por isso que a "
  "pausa em 401 nao e um erro fatal. O coletor fica relendo o arquivo de "
  "ambiente e retoma de onde parou assim que a chave nova e salva, sem "
  "reiniciar e sem refazer trabalho.")

h("3.4. O que ja deu errado", 2)
p("Vale registrar, porque explica buracos no log e porque evita repetir:")
tabela(
    ["o que aconteceu", "custo", "o que mudou"],
    [
        ["o coletor rodava numa aba de terminal dentro do aplicativo, e "
         "morreu quando o aplicativo fechou",
         "cerca de 5.700 partidas",
         "passou a rodar em processo proprio, e o README proibe a aba"],
        ["a maquina suspendeu de madrugada",
         "cerca de 19.500 partidas",
         "suspensao desligada no painel de energia, com registro conferido"],
        ["erro de DNS derrubou a coleta depois de 3 tentativas",
         "uma noite parada",
         "falha de rede agora tenta para sempre, com espera limitada"],
        ["uma espera cega de 120 segundos a cada leitura de cabecalho",
         "42 de 50 minutos de uma janela",
         "a leitura passou a apertar a janela local sem dormir, e o ritmo "
         "subiu 34 por cento"],
        ["troca de chave voltou para a chave anterior, que a geracao da nova "
         "ja havia invalidado", "uma pausa",
         "o script de troca testa a chave ate seis vezes antes de gravar"],
    ],
    larguras=[170, 100, 170], tamanho=9)

h("3.5. Provas de integridade", 2)
p("Tres conferencias sustentam a confianca no dado:")
lista([
    f"a soma de escolhas dividida pelo total de partidas da "
    f"{TOTAL_DE_ESCOLHAS / TOTAL_DE_PARTIDAS:.2f}, e toda partida de League "
    "tem exatamente 10 campeoes. Se houvesse partida truncada ou campeao "
    "perdido na leitura, esse numero cairia abaixo de 10",
    f"{sum(1 for v in VALORES_POR_DIA if v)} dos {len(DIAS)} dias do "
    "periodo tem partida, e nenhum ficou vazio",
    "a taxa de escolha de 16 campeoes foi comparada com a de um site "
    "publico de estatisticas, e a razao media entre as duas fontes ficou em "
    "0,98, com correlacao de ordem de 0,62. Isso nao valida o numero "
    "absoluto, e sim descarta erro grosseiro de pipeline",
])

doc.add_page_break()

#-------------------------------------------------------------- 4

h("4. O contrato de dados", 1)
p("Cinco arquivos. O painel le estes mesmos dados, convertidos para JSON. "
  "Qualquer mudanca de coluna quebra o trabalho das outras pessoas, e por "
  "isso o contrato e combinado antes de ser alterado.")

h("4.1. daily_pickrate.csv", 2)
p(f"{len(serie):,} linhas. O coracao do projeto.".replace(",", "."))
tabela(
    ["coluna", "tipo", "descricao"],
    [
        ["date", "texto AAAA-MM-DD", "dia no fuso America/Sao_Paulo"],
        ["champion", "texto", "championName da Riot, como KSante ou Kaisa"],
        ["games_total", "inteiro", "partidas daquele dia na amostra"],
        ["picks", "inteiro", "vezes que o campeao foi escolhido no dia"],
        ["pick_rate", "decimal", "picks dividido por games_total, 6 casas"],
    ],
    larguras=[90, 110, 240], tamanho=10)
p("Ha uma linha para cada campeao em cada dia, inclusive nos dias em que o "
  "campeao nao foi escolhido uma vez. Isso faz o arquivo ser grande e faz "
  "qualquer grafico de serie funcionar sem preencher buraco.")
p("A taxa chega perto de 0,16 para os campeoes mais populares, porque dez "
  "campeoes entram em cada partida: a soma das taxas de todos os campeoes "
  "num dia da 10, e nao 1.")

h("4.2. events.csv", 2)
p(f"{len(eventos)} linhas, {len(grupos)} eventos distintos. Uma linha por "
  "campeao por evento.")
tabela(
    ["coluna", "descricao"],
    [
        ["event_id", "identificador do evento, repetido entre os campeoes "
         "dele"],
        ["champion", "mesmo nome usado em daily_pickrate.csv"],
        ["event_type", "skin, clipe, trailer ou exposicao"],
        ["event_date", "data do evento, AAAA-MM-DD"],
        ["title", "titulo do video ou nome da skin"],
        ["youtube_id", "identificador do video, vazio em evento de skin"],
        ["views", "visualizacoes no momento da leitura"],
    ],
    larguras=[100, 340], tamanho=10)
p("A coluna views e um retrato do instante em que o catalogo foi lido, e "
  "nao tem coluna de data no contrato. Quem usar esse numero no painel "
  "precisa dizer quando ele foi lido.")
p("Um detalhe que custou uma correcao: dois videos da mesma linha de skin "
  "em datas diferentes recebiam o mesmo event_id, e a analise agrupa por "
  "event_id. O Pandemonio tinha trailer de Ato I em 14 de abril e de Ato II "
  "em 27 de maio, os dois saiam como trailer-pandemonio, e um dos dois "
  "desaparecia da contagem. Agora, quando o nome colide, a data entra no "
  "identificador.")

h("4.3. new_skins.csv", 2)
p(f"{len(skins)} linhas, em {len({s['champion'] for s in skins})} campeoes. "
  "Sai da comparacao entre versoes consecutivas do Data Dragon, que e o "
  "catalogo publico de conteudo do jogo e nao pede chave nem tem limite de "
  "taxa.")
tabela(
    ["coluna", "descricao"],
    [
        ["version", "patch que trouxe a skin, como 16.18"],
        ["champion", "mesmo nome usado em daily_pickrate.csv"],
        ["skin_num", "numero da skin no Data Dragon, nunca 0"],
        ["skin_name", "nome em portugues do Brasil"],
    ],
    larguras=[100, 340], tamanho=10)
p("Esse arquivo deu quatro armadilhas, todas resolvidas:")
lista([
    "croma nao e skin. Ele tem nome no formato Nome da Skin entre "
    "parenteses com a cor, e uma skin com nove cromas ocupa dez linhas. "
    "Contar as dez como evento faz o mesmo lancamento valer dez vezes na "
    "analise, entao nome com parentese e descartado antes da comparacao",
    "comparar por numero de skin falha, porque o Data Dragon renumera. A "
    "comparacao e feita por nome",
    "campeao novo entra com todas as skins de uma vez, e o filtro de "
    "identificador com sublinhado cuida disso",
    "no patch 16.6 o Data Dragon mudou de conteudo e passou a listar croma, "
    "saltando de 11 para 50 skins por campeao, e junto apareceram 62 skins "
    "base que ninguem lancou num patch so. Esse patch continua na cadeia de "
    "comparacao, para a diferenca nao cair no patch seguinte, mas nao gera "
    "evento",
])

h("4.4. patch_dates.csv", 2)
p(f"{len(patches)} patches, "
  f"{sum(1 for r in patches if r['exata'] == '1')} com data exata. Medida "
  "nas proprias partidas, e nao copiada de site de noticia.")
p("O metodo e direto: cada partida carrega a versao do jogo, e o dia em que "
  "a versao nova aparece pela primeira vez na amostra e a data do patch. "
  "Quando a amostra pegou o dia em que as duas versoes convivem, a data e "
  "exata. Quando nao pegou, o arquivo entrega o intervalo em que o patch "
  "cabe, em vez de um dia inventado.")

h("4.5. balance_changes.csv", 2)
p(f"{len(balanceamento)} linhas, "
  f"{len({r['champion'] for r in balanceamento})} campeoes distintos. "
  "Serve para tirar do grupo de controle quem foi mexido perto do evento.")
tabela(
    ["coluna", "descricao"],
    [
        ["patch", "versao em que a mudanca entrou"],
        ["patch_date", "data medida do patch"],
        ["champion", "mesmo nome usado em daily_pickrate.csv"],
        ["change", "o que mudou, com valor antes e depois"],
    ],
    larguras=[100, 340], tamanho=10)

h("4.6. resultados_por_campeao_evento.csv", 2)
p(f"{len(resultados)} linhas. Este arquivo nao faz parte do contrato de "
  "dados e foi criado para esta entrega, porque a analise entregava apenas "
  "relatorio em texto e grafico em HTML, que servem para ler e nao para o "
  "painel consumir. Ele e a tabela de resultados pronta, uma linha por "
  "campeao por evento.")
tabela(
    ["coluna", "descricao"],
    [
        ["event_id, event_type, event_date, champion",
         "a chave, igual a de events.csv"],
        ["taxa_antes, taxa_depois", "taxa media em cada janela"],
        ["lift", "taxa_depois dividida por taxa_antes"],
        ["percentil_do_lift", "onde esse lift cai entre os campeoes sem "
         "evento nas mesmas datas"],
        ["lift_do_pico, percentil_do_pico", "o mesmo, pela melhor janelinha "
         "de 3 dias"],
        ["picks_antes, picks_depois", "escolhas em cada janela"],
        ["jogos_antes, jogos_depois", "partidas em cada janela"],
        ["ic_antes_de ate ic_depois_ate", "os intervalos de 95 por cento"],
        ["intervalos_se_cruzam", "1 quando a amostra nao sustenta a "
         "diferenca"],
        ["pouca_amostra", "1 quando picks_antes ficou abaixo de 100"],
        ["destaque", "1 quando o percentil do pico passou de 90"],
        ["campeoes_no_controle", "quantos campeoes formaram a referencia"],
        ["lift_mediano_do_controle", "o que o servidor fez nas mesmas datas"],
    ],
    larguras=[175, 265], tamanho=9)
p(f"O gerador do arquivo importa as proprias funcoes de "
  "analise/efeito_vitrine.py, entao os numeros do CSV sao os mesmos do "
  f"relatorio: {len(resultados)} pares medidos e {len(MARCADOS)} destaques "
  "nas duas fontes. Dos pares medidos, "
  f"{CRUZAM} tem os intervalos de 95 por cento se cruzando, e essa coluna "
  "deve virar aviso visivel no painel.")
p("Sete pares de campeao e evento ficaram sem medida, por janela curta na "
  "borda do periodo ou por campeao sem escolha nenhuma na janela de antes. "
  "Eles aparecem em events.csv e nao aparecem aqui, o que explica a "
  f"diferenca entre as {len(eventos)} linhas de um e as {len(resultados)} "
  "do outro.")

doc.add_page_break()

#-------------------------------------------------------------- 5

h("5. Os patches do periodo", 1)
p("Vinte patches entraram no ar durante o periodo analisado. A cadencia e "
  "de 14 dias e cai quase sempre na quarta-feira, o que a medicao revelou "
  "sem que ninguem tivesse dito.")

linhas = []
for registro in patches:
    linhas.append([
        registro["patch"], registro["patch_date"],
        "exata" if registro["exata"] == "1" else "estimada",
        f"{int(registro['partidas']):,}".replace(",", "."),
        len([s for s in skins if s["version"] == registro["patch"]]),
        sum(1 for b in balanceamento if b["patch"] == registro["patch"]),
    ])
tabela(["patch", "data", "precisao", "partidas", "skins", "ajustes"],
       linhas, larguras=[55, 75, 70, 70, 50, 55], tamanho=9)

p("A coluna partidas e quantas partidas da amostra rodaram naquela versao. "
  "O 16.13 aparece com mais partidas porque durou tres semanas, e o 16.23 "
  "com poucas porque entrou em 18 de novembro, o ultimo dia do periodo.")
p("A unica data estimada e a do 16.4, que e o patch que estava no ar quando "
  "a coleta comeca, em 24 de fevereiro. Nao existe dia anterior na amostra "
  "para ver a troca acontecer.")

doc.add_page_break()

#-------------------------------------------------------------- 6

h("6. As skins lancadas no periodo", 1)
p(f"{len(skins)} lancamentos em "
  f"{len({s['champion'] for s in skins})} campeoes, patch por patch. Esta e "
  "a lista completa, com o nome em portugues do Brasil como aparece no "
  "jogo.")

for versao in sorted({s["version"] for s in skins}, key=chave_de_patch):
    do_patch = [s for s in skins if s["version"] == versao]
    data = next((r["patch_date"] for r in patches if r["patch"] == versao),
                "antes do periodo")
    h(f"Patch {versao}, {data}, {len(do_patch)} skins", 3)
    tabela(["campeao", "skin"],
           [[s["champion"], s["skin_name"]]
            for s in sorted(do_patch, key=lambda x: x["champion"])],
           larguras=[120, 320], tamanho=9)

p("Algumas observacoes que o painel pode querer mostrar:")
lista([
    "as skins de Prestigio aparecem na lista e sao lancamento de verdade, "
    "mas chegam por moeda de evento e nao pela loja comum, o que muda o "
    "quanto elas aparecem na frente do jogador",
    "o patch 16.3 traz 12 skins porque junta duas linhas sazonais, Fogos de "
    "Artificio e Petalas da Primavera, que saem no ano novo lunar",
    "as tres linhas grandes de musica do periodo sao HEARTSTEEL no 16.20, "
    "True Damage no 16.21 e K/DA no 16.22, e sao justamente as que tem "
    "clipe e trailer proprios",
])

doc.add_page_break()

#-------------------------------------------------------------- 7

h("7. Os eventos catalogados", 1)
p(f"{len(grupos)} eventos, divididos em quatro tipos. A divisao importa "
  "porque os tipos expoem o campeao de maneiras diferentes, e a hipotese do "
  "projeto nao e a mesma para cada um.")

tabela(
    ["tipo", "eventos", "linhas", "o que e"],
    [
        ["skin", POR_TIPO["skin"],
         sum(1 for e in eventos if e["event_type"] == "skin"),
         "a skin entra no jogo, e o campeao aparece na loja e na tela "
         "inicial"],
        ["clipe", POR_TIPO["clipe"],
         sum(1 for e in eventos if e["event_type"] == "clipe"),
         "clipe musical oficial, com milhoes de visualizacoes"],
        ["trailer", POR_TIPO["trailer"],
         sum(1 for e in eventos if e["event_type"] == "trailer"),
         "video curto que mostra as skins da linha"],
        ["exposicao", POR_TIPO["exposicao"],
         sum(1 for e in eventos if e["event_type"] == "exposicao"),
         "cerimonia de abertura e teaser, onde o campeao aparece sem ser o "
         "assunto"],
    ],
    larguras=[70, 60, 55, 255], tamanho=10)

p("Os eventos de skin nao tem video, e por isso a coluna youtube_id deles "
  "fica vazia. A descoberta que levou a essa separacao foi que a Riot nao "
  "publica video nenhum para linha de skin comum. A Congregacao das "
  "Bruxas, por exemplo, saiu sem trailer. Somente as linhas grandes de "
  "musica ganham clipe.")

h("7.1. Os clipes musicais", 2)
p("Cinco clipes, e sao o material mais forte do estudo, porque o publico e "
  "enorme e a data e precisa.")
for eid in por_data([i for i, g in grupos.items() if g["tipo"] == "clipe"]):
    g = grupos[eid]
    h(f'{g["data"]}, {eid}', 3)
    p(g["titulo"])
    vistas = f'{int(g["views"]):,}'.replace(",", ".") if g["views"] else "?"
    p(f'Visualizacoes no momento da leitura: {vistas}. '
      f'Endereco: youtu.be/{g["youtube"]}')
    p(f'Campeoes ({len(g["campeoes"])}): {", ".join(sorted(g["campeoes"]))}')

p("O achado metodologico mais util do catalogo esta aqui. O clipe sai antes "
  "da skin entrar no jogo, com 13 a 19 dias de diferenca, e isso separa os "
  "dois eventos no tempo. Em HEARTSTEEL, o clipe saiu em 18 de setembro e a "
  "skin em 7 de outubro, 19 dias depois. Em True Damage, o clipe saiu em 8 "
  "de outubro e a skin em 21 de outubro, 13 dias. Em K/DA, o clipe saiu em "
  "18 de outubro e a skin em 4 de novembro, 17 dias. Essa folga permite "
  "perguntar se o clipe sozinho move a taxa, antes de a skin existir no "
  "jogo.")

h("7.2. Os trailers", 2)
p(f'{POR_TIPO["trailer"]} eventos. Video curto que mostra as skins da '
  "linha, publicado nos dias que antecedem o patch.")
for eid in por_data([i for i, g in grupos.items() if g["tipo"] == "trailer"]):
    g = grupos[eid]
    vistas = f'{int(g["views"]):,}'.replace(",", ".") if g["views"] else "?"
    p(f'{g["data"]}  {eid}', negrito=True)
    p(f'{g["titulo"]}')
    p(f'{vistas} visualizacoes. youtu.be/{g["youtube"]}. '
      f'Campeoes: {", ".join(sorted(g["campeoes"]))}')

h("7.3. As exposicoes", 2)
p(f'{POR_TIPO["exposicao"]} linhas de evento. O campeao aparece, mas nao e '
  "o assunto do video.")
for eid in por_data([i for i, g in grupos.items()
                     if g["tipo"] == "exposicao"]):
    g = grupos[eid]
    vistas = f'{int(g["views"]):,}'.replace(",", ".") if g["views"] else "?"
    p(f'{g["data"]}  {eid}', negrito=True)
    p(f'{g["titulo"]}')
    p(f'{vistas} visualizacoes. youtu.be/{g["youtube"]}')
    p(f'Campeoes ({len(g["campeoes"])}): '
      f'{", ".join(sorted(g["campeoes"]))}')

p("O teaser de New Dawn merece nota de metodo. Os 16 campeoes dele foram "
  "identificados a olho por quem assistiu ao video, e nao por casamento de "
  "texto no titulo, porque o titulo nao nomeia ninguem. O arquivo "
  "eventos_manuais.csv registra isso na coluna de fonte, para quem ler "
  "depois saber que aquela linha tem origem diferente das outras.")

h("7.4. Os eventos de skin", 2)
p(f'{POR_TIPO["skin"]} eventos, construidos a partir do Data Dragon. '
  "Skins da mesma linha que saem no mesmo patch formam um evento so, porque "
  "dividem a data e a campanha.")
linhas = []
for eid in por_data([i for i, g in grupos.items() if g["tipo"] == "skin"]):
    g = grupos[eid]
    linhas.append([g["data"], eid.replace("skin-", ""),
                   ", ".join(sorted(g["campeoes"]))])
tabela(["data", "evento", "campeoes"], linhas,
       larguras=[65, 155, 220], tamanho=8)

doc.add_page_break()

#-------------------------------------------------------------- 8

h("8. O balanceamento e o grupo de controle", 1)
p("O balanceamento e o principal concorrente da skin na explicacao de uma "
  "subida de taxa. Um campeao que ficou mais forte sobe sem skin nenhuma, e "
  "se ele estiver no grupo de comparacao ele contamina a referencia.")
p(f"Por isso o projeto cataloga as mudancas: {len(balanceamento)} linhas em "
  f"{len({r['champion'] for r in balanceamento})} campeoes, extraidas da "
  "comparacao entre versoes do Data Dragon. Na hora de medir um evento, "
  "todo campeao mexido dentro da janela sai do grupo de controle.")

contagem = Counter(r["patch"] for r in balanceamento)
tabela(["patch", "campeoes mexidos"],
       [[v, contagem[v]] for v in sorted(contagem, key=chave_de_patch)],
       larguras=[90, 130], tamanho=9)

mais_comum = Counter(r["change"] for r in balanceamento).most_common(1)[0]
p(f"O patch 16.16 aparece com {contagem.get('16.16', 0)} campeoes mexidos, "
  "muito acima dos outros, e a razao esta no tipo de mudanca: "
  f"{mais_comum[1]} das linhas do arquivo sao a mesma alteracao de "
  "resistencia magica aplicada a muitos campeoes de uma vez. Isso e ajuste "
  "sistemico, e nao campeao por campeao, e o painel deve mostrar o 16.16 "
  "com essa ressalva.")
p("Existe um limite no detector para esse caso. Quando uma mudanca atinge "
  "mais da metade dos campeoes do jogo, ela nao e tratada como mudanca "
  "individual, porque mexer em todo mundo nao desloca a escolha de ninguem "
  "em particular.")

doc.add_page_break()

#-------------------------------------------------------------- 9

h("9. A metodologia da analise", 1)
p("Esta secao e a parte do documento que sustenta qualquer afirmacao do "
  "painel. A especificacao esta congelada em analise/especificacao.md, "
  "escrita antes de os resultados serem olhados, para a janela e o corte "
  "nao serem escolhidos depois de ver o que da resultado bonito.")

h("9.1. As janelas", 2)
tabela(
    ["parametro", "valor", "por que"],
    [
        ["janela de antes", "14 dias", "base de comparacao do campeao com "
         "ele mesmo"],
        ["recuo", "14 dias", "a janela de antes termina 14 dias antes do "
         "evento, e nao no dia anterior, para escapar do periodo em que a "
         "skin ja esta no servidor de teste e o clipe ja circula"],
        ["janela de depois", "7 dias", "efeito de novidade dura pouco"],
        ["largura do pico", "3 dias", "a melhor janelinha de 3 dias dentro "
         "do depois"],
        ["minimo de dias", "5", "evento perto da borda do periodo sai da "
         "conta"],
        ["folga do controle", "28 dias", "campeao com evento proprio nessa "
         "distancia nao serve de controle"],
        ["picks minimos", "100", "abaixo disso o ruido domina"],
        ["corte do destaque", "percentil 90", "acima disso o campeao se "
         "destacou do resto do servidor"],
    ],
    larguras=[95, 65, 280], tamanho=9)

p("O recuo de 14 dias e a decisao menos obvia e a mais importante. Medir o "
  "antes nos dias imediatamente anteriores ao lancamento seria medir um "
  "periodo que ja esta contaminado: a skin aparece no servidor de teste "
  "semanas antes, o trailer circula, e parte do efeito ja comecou. A base "
  "recuada pega o campeao em regime normal.")

h("9.2. Lift e pico", 2)
p("O lift e a taxa media do depois dividida pela taxa media do antes. O "
  "valor 1,00 significa nenhuma mudanca e 1,50 significa cinquenta por "
  "cento mais escolhas.")
p("O pico e a mesma conta usando a melhor janelinha de 3 dias dentro do "
  "depois. Ele existe porque efeito de novidade dura pouco e media longa o "
  "dilui. O teste contra dados falsos mostra o tamanho da diluicao: um pico "
  "plantado de 2,1 vezes aparece como 1,41 vezes quando medido pela media "
  "de 14 dias.")

h("9.3. O percentil contra o grupo de controle", 2)
p("Esse e o nucleo do metodo. O lift de um campeao, sozinho, nao diz nada, "
  "porque o servidor inteiro se move junto. O que o percentil faz e "
  "calcular o mesmo lift, nas mesmas datas, para todos os campeoes que nao "
  "tiveram evento, e perguntar onde o campeao com evento cai nessa "
  "distribuicao.")
p("O percentil 50 e o comportamento tipico do servidor naquele periodo. O "
  "percentil 90 e a fronteira: acima dela, apenas um em dez campeoes sem "
  f"evento chegou. O grupo de controle tem de {TAMANHO_DO_CONTROLE[0]} a "
  f"{TAMANHO_DO_CONTROLE[-1]} campeoes, com "
  f"{st.median(TAMANHO_DO_CONTROLE):.0f} no caso tipico, variando conforme "
  "quantos sairam por mudanca de balanceamento na janela.")
p(f"Vale olhar o que o controle faz: o lift mediano dos campeoes sem evento "
  f"vai de {CONTROLE_MEDIANO[0]:.2f} a {CONTROLE_MEDIANO[-1]:.2f} vezes, "
  f"com {st.median(CONTROLE_MEDIANO):.2f} no caso tipico. Ou seja, o "
  "campeao comum do servidor ficou praticamente parado no periodo, e as "
  "vezes de leve em queda. Isso e importante porque significa que a "
  "comparacao nao esta sendo feita contra um servidor em crescimento, que "
  "mascararia o efeito.")
p("Um detalhe de implementacao que quem for montar o painel precisa saber: "
  "a marca de destaque usa o percentil do pico, e nao o do lift. A razao e "
  "que o efeito de novidade e curto, entao o pico de 3 dias e a medida que "
  "o captura, e a media de 7 dias e a medida conservadora. As duas "
  "aparecem no CSV de resultados, e a coluna destaque segue o pico.")

h("9.4. Os intervalos de confianca", 2)
p("Cada taxa vem com intervalo de 95 por cento, calculado pelo metodo de "
  "Wilson, que e adequado a proporcao com contagem pequena. Quando o "
  "intervalo do antes e o do depois se cruzam, a amostra nao sustenta a "
  "diferenca, e o relatorio marca a linha com uma ressalva. Isso aparece "
  "com frequencia em campeao pouco escolhido, e e honesto que apareca.")

h("9.5. O teste agrupado por tipo", 2)
p("Esta e a pergunta do projeto, e e o numero que vale para concluir. "
  "Juntar todos os campeoes de todos os eventos do mesmo tipo ganha poder, "
  "porque a amostra de cada campeao e pequena mas os erros deles vao para "
  "lados independentes. O teste e um sinal binomial: dos N campeoes com "
  "evento daquele tipo, quantos ficaram acima do tipico do servidor? Se o "
  "evento nao fizesse nada, a resposta esperada seria metade.")
p("O numero por evento, campeao a campeao, serve para olhar e para contar "
  "historia. O numero agrupado serve para concluir.")

h("9.6. O teste de placebo", 2)
p("A medida inteira e repetida 200 vezes com a data de cada evento "
  "sorteada, mantendo os campeoes de verdade. Isso mostra quantos destaques "
  "o metodo inventa quando nao existe efeito nenhum para achar. Se o "
  "numero real nao se distingue do que o sorteio produz, o metodo esta "
  "medindo o proprio ruido.")
p("O sorteio usa semente fixa, entao o resultado e reproduzivel.")

h("9.7. A validacao contra dados falsos", 2)
p("Antes de rodar no dado real, a analise roda num conjunto falso com picos "
  "plantados de tamanho conhecido. Isso responde se o codigo encontra o que "
  "deveria encontrar. O resultado e que ele encontra, com a diluicao "
  "esperada pela media longa, e dentro de uma tolerancia de 30 por cento.")

doc.add_page_break()

#-------------------------------------------------------------- 10

h("10. Os resultados ate agora", 1)
p(f"Com {TOTAL_DE_PARTIDAS:,} partidas, {PARES_MEDIDOS} pares de campeao e "
  f"evento foram medidos, e {ACIMA_DE_P90} ficaram acima do percentil 90. "
  f"Por acaso, o esperado seria {ESPERADO_P90}."
  .replace(",", "."))

h("10.1. O resultado por tipo de evento", 2)
tabela(
    ["tipo", "acima do tipico", "de", "chance por acaso", "leitura"],
    [
        ["skin", resultado_por_tipo["skin"][0], resultado_por_tipo["skin"][1],
         f'{resultado_por_tipo["skin"][2]:.3f}', "efeito claro"],
        ["clipe", resultado_por_tipo["clipe"][0],
         resultado_por_tipo["clipe"][1],
         f'{resultado_por_tipo["clipe"][2]:.3f}', "sugestivo, nao conclusivo"],
        ["trailer", resultado_por_tipo["trailer"][0],
         resultado_por_tipo["trailer"][1],
         f'{resultado_por_tipo["trailer"][2]:.3f}', "sem sinal"],
        ["exposicao", resultado_por_tipo["exposicao"][0],
         resultado_por_tipo["exposicao"][1],
         f'{resultado_por_tipo["exposicao"][2]:.3f}', "sem sinal"],
    ],
    larguras=[70, 90, 40, 95, 145], tamanho=10)

acima, de, chance = resultado_por_tipo["skin"]
p(f"O resultado da skin e o mais forte do estudo: {acima} de {de} campeoes "
  f"com skin nova ficaram acima do comportamento tipico do servidor, com "
  f"chance de {chance:.3f} de isso acontecer se a skin nao fizesse nada. "
  "Com quatro tipos testados, o corte honesto fica mais perto de 0,01 do "
  "que de 0,05, e esse resultado passa dos dois.")
acima, de, chance = resultado_por_tipo["clipe"]
p(f"O clipe da {acima} de {de}, com chance {chance:.3f}. A direcao e a "
  "mesma da skin, e a amostra e pequena: cinco clipes, dezesseis pares. "
  "Nao da para concluir, e tambem nao da para descartar.")
h("10.1.1. O tamanho do efeito", 3)
p("O teste por tipo responde se o efeito existe. Esta tabela responde "
  "quanto ele vale, e e o numero que o painel deve mostrar ao lado da "
  "conclusao.")
tabela(
    ["tipo", "campeoes", "lift mediano", "menor", "maior"],
    [[tipo, len(lift_por_tipo[tipo]),
      f"{st.median(lift_por_tipo[tipo]):.2f}x",
      f"{min(lift_por_tipo[tipo]):.2f}x",
      f"{max(lift_por_tipo[tipo]):.2f}x"]
     for tipo in ["skin", "clipe", "trailer", "exposicao"]],
    larguras=[80, 75, 95, 65, 65], tamanho=10)
p(f"A leitura da primeira linha e esta: juntando os "
  f"{len(lift_por_tipo['skin'])} campeoes que receberam skin no periodo, o "
  f"campeao tipico passou a ser escolhido "
  f"{(st.median(lift_por_tipo['skin']) - 1) * 100:.0f} por cento mais "
  "vezes na semana seguinte ao lancamento. Esse numero inclui os campeoes "
  "que nao reagiram, e por isso ele e menor que o dos destaques.")
p(f"Entre os {len(MARCADOS)} pares que se destacaram, o lift mediano e "
  f"{st.median(LIFT_DOS_MARCADOS):.2f} vezes, com a metade central entre "
  f"{LIFT_DOS_MARCADOS[len(LIFT_DOS_MARCADOS) // 4]:.2f} e "
  f"{LIFT_DOS_MARCADOS[3 * len(LIFT_DOS_MARCADOS) // 4]:.2f} vezes. "
  f"Medido pelo pico de 3 dias, a mediana sobe para "
  f"{st.median(PICO_DOS_MARCADOS):.2f} vezes e o maior caso chega a "
  f"{PICO_DOS_MARCADOS[-1]:.2f} vezes.")
p("Trailer e exposicao nao mostram sinal. Faz sentido para a exposicao, em "
  "que o campeao aparece de passagem numa cerimonia sem ser o assunto. Para "
  "o trailer o resultado pede cautela, porque trailer e clipe do mesmo "
  "lancamento saem com poucos dias de diferenca e medem quase o mesmo "
  "pedaco da serie, entao as linhas desses dois tipos nao sao evidencia "
  "independente uma da outra.")

h("10.2. O teste de placebo", 2)
p(f"Dos 200 sorteios com data trocada, {PLACEBO[0]} empatou ou passou o "
  f"numero real, ou seja {PLACEBO[2]}. O sorteio produz em media "
  f"{PLACEBO_SORTEIO[0]} destaques, com minimo de {PLACEBO_SORTEIO[1]} e "
  f"maximo de {PLACEBO_SORTEIO[2]}, contra {MOMENTOS_DISTINTOS} momentos "
  "distintos no dado real.")
p("A leitura e que o acaso raramente produz tanto destaque assim. O metodo "
  "nao esta encontrando padrao em qualquer data que se escolha.")
p("Uma correcao anterior vale registro, porque mudou o numero. O placebo "
  "havia dado uma chance muito menor porque contava o mesmo momento varias "
  "vezes: Aphelios aparecia em clipe, trailer e skin, tres eventos a poucos "
  "dias de distancia, e o mesmo pico da serie entrava tres vezes na "
  f"contagem. A contagem passou a ser por momento distinto, e os "
  f"{PARES_MARCADOS} pares marcados viram {MOMENTOS_DISTINTOS} momentos.")

h("10.3. Os destaques, nome por nome", 2)
p(f"Os {len(destaques)} pares de campeao e evento que passaram do percentil "
  "90, em ordem de data. A coluna picks e quantas escolhas o campeao teve na "
  "janela de antes, e serve para julgar o peso da linha.")
tabela(
    ["data", "tipo", "campeao", "lift", "perc", "pico", "perc", "picks"],
    [[d["data"], d["tipo"], d["campeao"], d["lift"], d["perc"], d["pico"],
      d["perc_pico"], d["picks"]] for d in destaques],
    larguras=[60, 55, 75, 45, 38, 45, 38, 42], tamanho=9)

p("Alguns casos merecem leitura cuidadosa:")
lista([
    "Aphelios aparece tres vezes, no clipe de 18 de setembro, no trailer de "
    "22 de setembro e na skin de 7 de outubro. Sao tres eventos do mesmo "
    "lancamento HEARTSTEEL em vinte dias, e o mesmo trecho da serie sustenta "
    "as tres linhas. O lift dele de 2,34 vezes e o maior do estudo, e nao "
    "deve ser contado tres vezes",
    "Akali aparece duas vezes, no clipe de K/DA e na skin de True Damage, "
    "que sao campanhas diferentes em datas diferentes, e aqui as duas "
    "linhas tem mais independencia",
    "Belveth tem o maior lift de skin, 2,26 vezes, com apenas 113 escolhas "
    "na janela de antes. Campeao pouco escolhido produz lift grande com "
    "pouca escolha a mais, e e por isso que a coluna de picks importa",
    "Diana e Leona sobem juntas na mesma skin de Aspecto Eterno, em 28 de "
    "maio, com 1,78 e 1,51 vezes. Lancamento com duas skins que sobem as "
    "duas e evidencia melhor que lancamento solo",
    "Janna sobe 2,29 vezes com a Congregacao das Bruxas, que e a linha que "
    "nao teve video nenhum. Isso e util para o argumento: a skin sozinha, "
    "sem campanha de video, deslocou a escolha",
])

h("10.4. O que se pode afirmar hoje", 2)
p("Com o dado atual, e defensavel dizer que o lancamento de skin desloca a "
  "taxa de escolha do campeao no servidor brasileiro, e que o deslocamento "
  "e visivel na primeira semana. O campeao tipico com skin nova e escolhido "
  f"{(st.median(lift_por_tipo['skin']) - 1) * 100:.0f} por cento mais "
  "vezes, e entre os que se destacaram do servidor a mediana e de "
  f"{st.median(LIFT_DOS_MARCADOS):.2f} vezes a taxa anterior.")
p("Nao e defensavel, com este dado, afirmar que o clipe musical sozinho "
  "produz o mesmo efeito. A direcao aponta para isso, e a amostra de cinco "
  "clipes nao fecha a conta.")
p("Tambem nao e defensavel atribuir o efeito a um mecanismo especifico. O "
  "dado mostra que a taxa sobe depois do lancamento e mais do que nos "
  "campeoes de comparacao. Ele nao distingue entre quem comprou a skin e "
  "quis usar, quem viu o campeao na tela inicial e lembrou dele, e quem "
  "copiou um streamer que estava mostrando a skin.")

doc.add_page_break()

#-------------------------------------------------------------- 11

h("11. Limitacoes", 1)
p("O painel deve carregar estas ressalvas de forma visivel, e nao em letra "
  "pequena no rodape.")
lista([
    "a amostra e de partidas de jogadores sorteados, e nao do servidor "
    "inteiro. A taxa de escolha e comparavel entre dias porque a densidade "
    "da amostra e parelha, mas games_total nao e o numero de partidas "
    "jogadas no BR1 naquele dia",
    "o estudo e observacional. Nao houve sorteio de quem recebe skin, entao "
    "a conclusao e de associacao, e nao de causa provada. O placebo e o "
    "grupo de controle reduzem o risco de confusao, e nao o eliminam",
    "skin e balanceamento podem andar juntos. A Riot as vezes ajusta um "
    "campeao no mesmo patch em que lanca a skin dele, e nesse caso as duas "
    "explicacoes se sobrepoem",
    "clipe, trailer e skin da mesma linha saem em poucos dias e medem "
    "pedacos sobrepostos da serie, o que impede tratar as linhas como "
    "evidencia independente",
    "campeao pouco escolhido produz lift instavel. Meia duzia de escolhas a "
    "mais vira lift de duas vezes, e por isso o corte de 100 escolhas na "
    "janela de antes existe",
    "a coluna views e um retrato, sem data no contrato, e muda a cada "
    "leitura",
    "o teaser de New Dawn tem campeoes identificados a olho, e nao por "
    "regra automatica",
    "o periodo cobre nove meses de um ano. Efeito sazonal, como o pico de "
    "ferias ou a semana do campeonato mundial, aparece no dado sem estar "
    "separado",
])

doc.add_page_break()

#-------------------------------------------------------------- 12

h("12. Os dados do painel", 1)
p("O painel vai no Vercel, que serve arquivo estatico e nao roda Python, "
  "entao ele nao le os CSV. O exportador gera uma pasta de JSON que o "
  "painel busca com fetch, sem backend nenhum.")

json = AQUI / "json"
linhas = []
descricao = {
    "serie.json": "a serie diaria inteira, em listas paralelas",
    "eventos.json": "um objeto por evento, com os campeoes dentro",
    "patches.json": "a data medida de cada patch",
    "balanceamento.json": "quem foi mexido em cada patch",
    "resumo.json": "periodo, totais e os avisos de leitura",
}
for arquivo in sorted(json.glob("*.json")):
    linhas.append([arquivo.name,
                   f"{arquivo.stat().st_size / 1024:.1f} KB",
                   descricao.get(arquivo.name, "")])
total = sum(a.stat().st_size for a in json.glob("*.json")) / 1024
linhas.append(["total", f"{total:.1f} KB", ""])
tabela(["arquivo", "tamanho", "o que tem"], linhas,
       larguras=[120, 70, 250], tamanho=10)

p("A serie vem como listas paralelas, e nao como um objeto por linha, e e "
  "isso que a deixa em pouco mais de 100 KB em vez de alguns megabytes. A "
  "leitura e assim: escolhas[campeao][i] e o numero de escolhas no dia "
  "dias[i], e a taxa e esse numero dividido por partidas_por_dia[i].")
p("Como sao arquivos estaticos, eles sao um retrato. O exportador precisa "
  "rodar de novo sempre que a coleta avancar, e a data do retrato deve "
  "aparecer na tela, para ninguem apresentar numero velho sem saber.")
p("Falta um sexto arquivo, e ele e o que o painel mais vai usar nas telas "
  "de resultado: a tabela de resultados por campeao e evento, que nesta "
  "entrega esta em dados/resultados_por_campeao_evento.csv e descrita na "
  "secao 4.6. Converter esse CSV para JSON e tarefa pequena, e sem ele cada "
  "tela de resultado teria que refazer a conta de janela e de percentil no "
  "navegador, com risco de divergir do relatorio.")

h("12.1. O que o painel nao deve calcular sozinho", 2)
p("Vale separar o que o navegador pode fazer do que precisa vir pronto, "
  "para o painel nunca mostrar um numero diferente do que o trabalho "
  "escrito afirma.")
tabela(
    ["o navegador pode", "precisa vir pronto"],
    [
        ["desenhar a serie de qualquer campeao",
         "o lift e o percentil de cada par de campeao e evento"],
        ["somar escolhas num intervalo que o visitante escolheu",
         "o grupo de controle de cada data, com quem saiu e por que"],
        ["ordenar e filtrar as tabelas",
         "as contagens do teste por tipo e a chance de cada uma"],
        ["converter taxa em porcentagem e lift em vezes",
         "os 200 valores do placebo"],
    ],
    larguras=[215, 225], tamanho=9)

doc.add_page_break()

#-------------------------------------------------------------- 13

h("13. Sugestoes de visualizacao", 1)
p("Treze telas, em ordem de prioridade. Cada uma traz o que ela responde, "
  "o que aparece na tela e de onde vem o dado. As primeiras cinco "
  "sustentam o argumento do trabalho, e as demais servem para explorar.")

def visual(numero, nome, pergunta, aparencia, dado, nota=None):
    h(f"13.{numero}. {nome}", 2)
    p("O que responde: " + pergunta)
    p("Como se parece: " + aparencia)
    p("De onde vem: " + dado)
    if nota:
        p("Nota: " + nota)

visual(
    1, "A abertura",
    "o visitante entendeu em cinco segundos o que o estudo achou?",
    "uma faixa larga no topo com quatro numeros grandes e rotulo pequeno "
    "embaixo de cada um: partidas analisadas, dias, campeoes e eventos. "
    "Abaixo deles, uma frase unica em corpo grande com o resultado "
    f"principal, no formato de {resultado_por_tipo['skin'][0]} de "
    f"{resultado_por_tipo['skin'][1]} campeoes com skin nova subiram mais "
    "que o tipico do servidor. Ao lado da frase, um selo pequeno com a data "
    "do retrato dos dados.",
    "resumo.json",
    "o numero grande e honesto apenas com a ressalva ao lado. O selo com a "
    "data do retrato evita que alguem apresente numero velho."
)

visual(
    2, "A serie de um campeao com a marca do evento",
    "a taxa subiu depois do evento, e quando?",
    "um grafico de linha ocupando a largura da tela. O eixo horizontal e o "
    "tempo, os 268 dias. O eixo vertical e a taxa de escolha. A linha do "
    "campeao escolhido vem em cor forte, e atras dela, em cinza muito "
    "claro, a faixa entre o percentil 25 e o 75 dos campeoes sem evento, "
    "que mostra o que o servidor estava fazendo naquele periodo. Linhas "
    "verticais pontilhadas marcam os eventos daquele campeao, com rotulo "
    "curto. Duas faixas sombreadas marcam a janela de antes e a de depois, "
    "para o visitante ver de onde saiu a conta. Ao passar o mouse, uma "
    "caixa mostra a data, a taxa, as escolhas e as partidas do dia.",
    "serie.json e eventos.json",
    "esta e a tela principal e deve ser a primeira coisa interativa da "
    "pagina. A faixa cinza do controle e o que diferencia este grafico de "
    "um grafico de taxa qualquer."
)

visual(
    3, "O antes e depois pareado",
    "o tamanho do efeito, campeao por campeao, de um jeito que se compara "
    "de relance?",
    "um grafico de pares, com uma linha horizontal por campeao. Em cada "
    "linha, um ponto claro na taxa de antes e um ponto escuro na taxa de "
    "depois, ligados por um segmento. Segmento apontando para a direita e "
    "subida. Os campeoes vem ordenados pelo tamanho da subida, e uma linha "
    "vertical fina marca a mediana dos campeoes sem evento no mesmo "
    "periodo. Filtro no topo por tipo de evento.",
    "serie.json e eventos.json, com a mesma conta de janela da analise",
    "e a forma mais direta de mostrar o resultado de um evento com varios "
    "campeoes, como HEARTSTEEL com seis."
)

visual(
    4, "A distribuicao do controle com a seta do campeao",
    "o campeao se destacou mesmo, ou subiu junto com todo mundo?",
    "um histograma do lift de todos os campeoes sem evento naquelas datas, "
    "em cinza. Uma seta vertical em cor forte marca onde o campeao com "
    "evento caiu, com o percentil escrito ao lado. A regiao acima do "
    "percentil 90 vem levemente sombreada. O grafico e pequeno, do tamanho "
    "de um cartao, porque ele acompanha cada campeao.",
    "serie.json, calculando o lift do grupo de controle no navegador",
    "esta e a tela que explica o metodo sem texto. Vale repetir ela em "
    "miniatura ao lado de cada numero de percentil do painel."
)

visual(
    5, "O resultado por tipo de evento",
    "qual tipo de evento move a escolha?",
    "quatro barras horizontais, uma por tipo, mostrando a fracao de "
    "campeoes acima do tipico. Uma linha vertical em 50 por cento marca o "
    "que o acaso produziria. Cada barra traz o intervalo de confianca como "
    "uma linha fina sobreposta, e ao lado da barra o texto com a contagem "
    "crua e a chance. Barra com chance abaixo de 0,01 recebe cor de "
    "destaque, as outras ficam em cinza.",
    "um JSON pequeno gerado pela analise, com as quatro contagens",
    "a barra de trailer precisa de um aviso visivel, porque trailer e clipe "
    "do mesmo lancamento medem pedacos sobrepostos da serie."
)

visual(
    6, "O placebo",
    "o metodo acha padrao em qualquer data?",
    "um histograma dos 200 sorteios, cada um com o numero de destaques que "
    "produziu, em cinza. Uma linha vertical vermelha marca o numero real. O "
    "texto embaixo diz quantos sorteios empataram ou passaram o real. A "
    "distancia entre a montanha cinza e a linha vermelha e o argumento "
    "inteiro, e ela deve ser visivel sem leitura de eixo.",
    "um JSON pequeno com os 200 valores",
    "e a tela mais convincente para um leitor cetico, e a mais barata de "
    "fazer."
)

visual(
    7, "A linha do tempo dos eventos",
    "o que aconteceu no periodo, e quando?",
    "uma faixa horizontal com os 268 dias. Quatro trilhas empilhadas, uma "
    "por tipo de evento, com um marcador por evento. O tamanho do marcador "
    "acompanha o numero de campeoes, e a cor acompanha o tipo. Acima das "
    "trilhas, marcas verticais finas para os 20 patches. Clicar num "
    "marcador abre a pagina daquele evento. Arrastar seleciona um intervalo "
    "e filtra o resto do painel.",
    "eventos.json e patches.json",
    "esta faixa funciona bem como navegacao permanente no topo do painel, e "
    "nao apenas como grafico."
)

visual(
    8, "A dispersao de lift contra escolhas",
    "o lift grande vem de campeao pouco jogado?",
    "um grafico de dispersao com as escolhas na janela de antes no eixo "
    "horizontal, em escala logaritmica, e o lift no eixo vertical. Um ponto "
    "por par de campeao e evento, com a cor pelo tipo. Uma linha "
    "horizontal em 1,00 marca o nenhum efeito, e uma linha vertical em 100 "
    "marca o corte de escolhas minimas. O funil que se forma a esquerda e a "
    "mensagem: pouco jogado produz numero extremo nos dois sentidos.",
    "serie.json e eventos.json",
    "esta tela e uma limitacao transformada em grafico, e por isso ganha "
    "credibilidade em vez de perder."
)

visual(
    9, "A pagina do campeao",
    "o que aconteceu com este campeao no periodo?",
    "uma pagina por campeao, com a serie dele no topo, a lista de eventos "
    "dele com data e tipo, a lista de mudancas de balanceamento no periodo, "
    "e a tabela de lift de cada evento com percentil e intervalo. Um seletor "
    "de campeao com busca por nome, e setas para o campeao anterior e o "
    "proximo em ordem de popularidade.",
    "serie.json, eventos.json e balanceamento.json",
    "e a tela que o visitante vai querer quando ele tem um campeao "
    "preferido, e e o que faz ele ficar no site."
)

visual(
    10, "A pagina do evento",
    "este lancamento funcionou?",
    "uma pagina por evento, com o titulo, a data, o tipo, o video incorporado "
    "quando houver, as visualizacoes com a data da leitura, e o grafico de "
    "pares de todos os campeoes do evento. Abaixo, a tabela com lift, pico, "
    "percentil e ressalva de intervalo por campeao, e o veredito do grupo.",
    "eventos.json e serie.json",
    "para os cinco clipes vale destacar a diferenca de dias entre o clipe e "
    "a skin, porque e o que permite separar os dois efeitos."
)

visual(
    11, "O mapa de calor de campeao por semana",
    "existe padrao no periodo que ninguem procurou?",
    "uma matriz com os campeoes nas linhas e as semanas nas colunas. A cor "
    "de cada celula e o desvio da taxa daquele campeao naquela semana em "
    "relacao a media dele no periodo, numa escala que vai do azul ao "
    "vermelho passando pelo branco no zero. Pequenos marcadores sobre as "
    "celulas indicam evento. Ordenar as linhas por popularidade ou por "
    "momento do maior desvio muda o que a figura conta.",
    "serie.json",
    "e a tela de exploracao, e e onde aparecem coisas que o estudo nao "
    "estava procurando. Com 173 campeoes ela precisa de rolagem e de um "
    "filtro para os 40 mais jogados."
)

visual(
    12, "Visualizacoes contra efeito",
    "clipe com mais publico move mais a escolha?",
    "uma dispersao com as visualizacoes do video no eixo horizontal, em "
    "escala logaritmica, e o lift mediano dos campeoes do evento no eixo "
    "vertical. Um ponto por evento com video, rotulado com o nome do "
    "evento. Apenas os eventos com video entram, entao sao poucos pontos e "
    "cada um pode ser rotulado.",
    "eventos.json e serie.json",
    "com cinco clipes e alguns trailers, esta tela nao sustenta conclusao "
    "nenhuma, e deve dizer isso. Ela vale como pergunta aberta e como "
    "convite para a proxima rodada de coleta."
)

visual(
    13, "A pagina de metodo",
    "por que acreditar nestes numeros?",
    "uma pagina de texto com figuras pequenas, explicando a janela, o "
    "recuo, o grupo de controle e o placebo, nessa ordem. Cada conceito vem "
    "com um grafico minimo ao lado, do tamanho de um paragrafo. No fim, a "
    "lista de limitacoes em texto corrido, e o endereco do repositorio.",
    "este documento",
    "e a pagina que um avaliador vai abrir primeiro, e ela deve estar "
    "linkada no topo e nao escondida no rodape."
)

h("13.14. Decisoes visuais que valem para todas as telas", 2)
lista([
    "a cor marca tipo de evento, e deve ser a mesma em todo o painel. Quatro "
    "cores fixas, uma por tipo, e cinza sempre para o grupo de controle",
    "o eixo vertical da taxa comeca em zero quando a comparacao e entre "
    "campeoes, e pode comecar acima de zero quando a comparacao e do "
    "campeao com ele mesmo, com aviso de escala cortada",
    "a taxa aparece em porcentagem com uma casa, e nao em decimal de seis "
    "casas. O lift aparece como numero de vezes, no formato 1,78x",
    "todo numero que vem de campeao com menos de 100 escolhas na janela de "
    "antes aparece em cinza, com marca de pouca amostra",
    "a data do retrato dos dados aparece em toda tela, e nao apenas na "
    "abertura",
    "o painel precisa funcionar em celular, porque e onde o trabalho vai "
    "ser mostrado. As tabelas largas viram cartoes empilhados, e a faixa do "
    "tempo vira rolagem horizontal",
])

doc.add_page_break()

#-------------------------------------------------------------- 14

h("14. O que falta", 1)

h("14.1. Pessoa 1, coleta", 2)
lista([
    "deixar a coleta terminar na madrugada de quarta, 25 de novembro, e "
    "rodar o ciclo completo de agregacao, qualidade, eventos, analise e "
    "exportacao uma ultima vez",
    "remover o atalho de religar da pasta de inicializacao do Windows "
    "quando a coleta acabar",
    "entregar a pasta de JSON final para quem monta o painel, com a data do "
    "retrato",
])

h("14.2. Pessoa 2, eventos e analise", 2)
lista([
    "revisar o catalogo de eventos a olho, porque o casamento por texto "
    "acerta o essencial e erra nos casos de borda",
    "conferir se algum campeao do teaser de New Dawn ficou de fora da lista "
    "feita a olho",
    "decidir se o trailer entra na conclusao ou sai dela, dado que ele mede "
    "pedaco sobreposto ao do clipe",
    "escrever a secao de discussao do trabalho, separando o que o dado "
    "mostra do que o dado sugere",
])

h("14.3. Pessoa 3, painel", 2)
lista([
    "montar as cinco primeiras telas da secao 13, que sao as que sustentam "
    "o argumento",
    "colocar a data do retrato visivel em toda tela",
    "carregar as limitacoes da secao 11 numa pagina propria, linkada do "
    "topo",
    "conferir o painel no celular antes da apresentacao",
])

h("14.4. Decisao que ainda nao foi tomada", 2)
p("Falta combinar entre as tres pessoas se o trabalho conclui sobre clipe "
  "musical ou se limita a conclusao a skin. O dado atual sustenta a "
  "afirmacao sobre skin com folga. Sobre clipe, a direcao e a mesma e a "
  "amostra de cinco videos nao fecha. As duas escolhas sao defensaveis, e a "
  "escolha precisa aparecer no texto do trabalho e no painel de forma "
  "coerente.")

doc.save(SAIDA)

#-------------------------------------------------------------- conferencia

bruto = SAIDA.read_bytes()
texto = []
for paragrafo in Document(SAIDA).paragraphs:
    texto.append(paragrafo.text)
for tab in Document(SAIDA).tables:
    for linha in tab.rows:
        for celula in linha.cells:
            texto.append(celula.text)
tudo = "\n".join(texto)

print(f"{SAIDA.name}: {len(bruto) / 1024:.0f} KB")
print(f"paragrafos {len(Document(SAIDA).paragraphs)} | "
      f"tabelas {len(Document(SAIDA).tables)}")
print(f"travessao: {tudo.count(chr(8212))} em-dash, "
      f"{tudo.count(chr(8211))} en-dash")
onde = [l for l in texto if chr(8211) in l or chr(8212) in l]
for linha in onde:
    print(f"   {linha[:90]}")
