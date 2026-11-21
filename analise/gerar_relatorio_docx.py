"""Gera o relatorio de estado do projeto em docx, Times New Roman."""
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

FONTE = "Times New Roman"


def aplica_fonte(run, tamanho=12, negrito=False, italico=False):
    run.font.name = FONTE
    run.font.size = Pt(tamanho)
    run.bold = negrito
    run.italic = italico
    rpr = run._element.get_or_add_rPr()
    fontes = rpr.find(qn("w:rFonts"))
    if fontes is None:
        fontes = OxmlElement("w:rFonts")
        rpr.append(fontes)
    for atributo in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fontes.set(qn(atributo), FONTE)


doc = Document()

#fonte padrao do documento inteiro
normal = doc.styles["Normal"]
normal.font.name = FONTE
normal.font.size = Pt(12)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONTE)
normal.paragraph_format.space_after = Pt(8)
normal.paragraph_format.line_spacing = 1.15

for nome, tamanho in (("Title", 20), ("Heading 1", 15), ("Heading 2", 13),
                      ("List Bullet", 12)):
    estilo = doc.styles[nome]
    estilo.font.name = FONTE
    estilo.font.size = Pt(tamanho)
    estilo.font.color.rgb = RGBColor(0, 0, 0)
    if nome.startswith("Heading") or nome == "Title":
        estilo.font.bold = True
        estilo.paragraph_format.space_before = Pt(14)
        estilo.paragraph_format.space_after = Pt(6)
        estilo.paragraph_format.keep_with_next = True


def titulo(texto, nivel=1):
    p = doc.add_heading(texto, level=nivel)
    for run in p.runs:
        aplica_fonte(run, 15 if nivel == 1 else 13, True)
    return p


def paragrafo(texto, italico=False):
    p = doc.add_paragraph()
    aplica_fonte(p.add_run(texto), 12, False, italico)
    return p


def ponto(texto):
    p = doc.add_paragraph(style="List Bullet")
    aplica_fonte(p.add_run(texto), 12)
    return p


def tabela(colunas, linhas, larguras=None):
    t = doc.add_table(rows=1, cols=len(colunas))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, nome in enumerate(colunas):
        celula = t.rows[0].cells[i]
        celula.text = ""
        aplica_fonte(celula.paragraphs[0].add_run(nome), 10, True)
        sombra = OxmlElement("w:shd")
        sombra.set(qn("w:val"), "clear")
        sombra.set(qn("w:fill"), "E8E8E8")
        celula._tc.get_or_add_tcPr().append(sombra)
    for linha in linhas:
        celulas = t.add_row().cells
        for i, texto in enumerate(linha):
            celulas[i].text = ""
            aplica_fonte(celulas[i].paragraphs[0].add_run(str(texto)), 10)
    if larguras:
        for linha in t.rows:
            for i, largura in enumerate(larguras):
                linha.cells[i].width = largura
    doc.add_paragraph()
    return t


p = doc.add_heading("Efeito Vitrine", level=0)
for run in p.runs:
    aplica_fonte(run, 20, True)
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
aplica_fonte(sub.add_run("Estado do projeto em 20 de novembro de 2026"),
             11, False, True)

titulo("A pergunta")
paragrafo(
    "Lancamento de skin e clipe musical de League of Legends faz o campeao "
    "ser mais escolhido? A pergunta parece obvia, mas quase ninguem mede "
    "isso com cuidado, porque tres coisas acontecem quase juntas: o clipe "
    "sai, a skin entra no jogo e o campeao costuma levar ajuste de "
    "balanceamento no mesmo patch. Separar as tres e o trabalho."
)
paragrafo(
    "O recorte e a fila ranqueada solo, numero 420, do servidor brasileiro, "
    "entre 4 de setembro e 18 de novembro de 2026, ou seja 76 dias."
)

titulo("O que ja existe")
tabela(
    ["Item", "Numero", "Observacao"],
    [
        ["Partidas coletadas", "11.369", "de 32.572 da primeira passada"],
        ["Jogadores semeados", "3.869", "400 por elo, em 10 elos"],
        ["Dias cobertos", "76", "todos com partida, nenhum vazio"],
        ["Campeoes na amostra", "173", "todos os do jogo"],
        ["Eventos catalogados", "18", "76 linhas, 36 campeoes"],
        ["Videos que viraram evento", "8", "de 239 catalogados"],
        ["Skins novas no periodo", "30", "de 200 linhas, o resto e croma"],
        ["Patches com data medida", "7", "6 delas exatas"],
        ["Mudancas de balanceamento", "43", "em 36 campeoes"],
        ["Scripts", "12", "cerca de 3.900 linhas, em 26 commits"],
    ],
)

titulo("Os oito videos")
paragrafo(
    "Saem dos dois canais oficiais da Riot. Video de canal de terceiro, tipo "
    "spotlight de skin feito por fa, nao entra, porque nao e lancamento de "
    "nada."
)
tabela(
    ["Data", "Tipo", "Video", "Views", "Campeoes"],
    [
        ["18/09", "clipe", "HEARTSTEEL, Live My Life", "7.950.915",
         "Aphelios, Ezreal, KSante, Kayn, Sett, Yone"],
        ["22/09", "trailer", "HEARTSTEEL Live My Life, Skins Trailer",
         "269.202", "os mesmos 6"],
        ["06/10", "trailer", "True Damage: Know My Name, Skins Trailer",
         "716.285", "Akali, Ekko, Qiyana, Senna, Yasuo"],
        ["08/10", "clipe", "Know My Name ft. True Damage", "47.154.942",
         "os mesmos 5"],
        ["18/10", "clipe", "K/DA, FIRESTARTER", "57.674.446",
         "Ahri, Akali, Evelynn, Kaisa"],
        ["05/11", "clipe", "K/DA, DJ Sona, GIRLS", "3.628.302", "Sona"],
        ["14/11", "exposicao", "New Dawn Teaser", "2.173.347",
         "16 campeoes, lista no events.csv"],
        ["14/11", "exposicao", "Worlds 2026 Final Opening Ceremony",
         "1.916.371",
         "Ahri, Akali, Ekko, Evelynn, Kaisa, Qiyana, Senna, Yasuo"],
    ],
)
paragrafo(
    "Um detalhe que vale guardar: o clipe sai de 13 a 19 dias antes de a "
    "skin entrar no jogo. Isso permite perguntar qual dos dois move a "
    "agulha, em vez de medir os dois embolados num borrao so."
)

titulo("As skins e os campeoes")
tabela(
    ["Patch", "Data", "Linha de skin", "Campeoes"],
    [
        ["16.18", "10/09", "Lenda Ascendida e Lenda Imortalizada",
         "Orianna, Tristana"],
        ["16.19", "23/09", "Congregacao das Bruxas", "Janna, Mel"],
        ["16.19", "23/09", "Deus Antigo e Deusa Antiga", "Urgot, Anivia"],
        ["16.20", "07/10", "HEARTSTEEL Live My Life",
         "Aphelios, Ezreal, KSante, Kayn, Sett, Yone"],
        ["16.20", "07/10", "Barao Classico", "KogMaw"],
        ["16.21", "21/10", "True Damage Know My Name",
         "Akali, Ekko, Qiyana, Senna, Yasuo"],
        ["16.22", "04/11", "K/DA FIRESTARTER e K/DA Hitmaker",
         "Ahri, Akali, Evelynn, Kaisa"],
        ["16.23", "18/11", "DJ Sona Remix Supremo", "Sona"],
        ["16.23", "18/11", "Kawaii Cafe", "Neeko, Zoe"],
    ],
)
paragrafo(
    "Os 18 campeoes que o projeto escolheu analisar sao os das tres linhas "
    "musicais, HEARTSTEEL, True Damage e K/DA, mais as linhas tematicas do "
    "patch 16.19. Todos eles tiveram lancamento de verdade no periodo."
)

titulo("O que o sistema faz")

titulo("Coleta", 2)
paragrafo(
    "Sorteia jogadores de Ferro a Challenger no servidor brasileiro, pede a "
    "lista de partidas ranqueadas de cada um e baixa cada partida, guardando "
    "so o que interessa: o identificador, a data, a versao do jogo e os dez "
    "campeoes escolhidos. Nenhum jogador e identificado em arquivo nenhum "
    "publicado."
)
paragrafo(
    "O periodo e varrido em semanas de segunda a domingo, em rodizio. Isso "
    "quer dizer que a coleta nao enche setembro primeiro e deixa novembro "
    "vazio: ela pega um pedaco de cada semana por vez. Se parar a qualquer "
    "momento, os 76 dias estao cobertos de forma parecida."
)
paragrafo(
    "A chave da Riot expira a cada 24 horas. Quando isso acontece o coletor "
    "pausa, avisa e fica relendo o arquivo de configuracao a cada 60 "
    "segundos ate alguem trocar o valor, e entao continua sozinho, sem "
    "precisar reiniciar."
)

titulo("Eventos", 2)
paragrafo(
    "Lista tudo que os canais oficiais publicaram no periodo e cruza com as "
    "skins que sairam, para montar a tabela de eventos. Descobriu sozinho a "
    "data em que cada patch entrou no servidor brasileiro, olhando a versao "
    "do jogo gravada em cada partida: o primeiro dia em que a versao nova "
    "aparece e o dia da virada."
)

titulo("Analise", 2)
paragrafo(
    "Para cada evento, compara a taxa de escolha do campeao antes e depois, "
    "e compara esse resultado com o que os campeoes SEM evento fizeram nas "
    "mesmas datas. Essa comparacao com grupo de controle e o que separa "
    "efeito de vitrine de uma mudanca que pegou o servidor inteiro, tipo "
    "patch grande ou virada de temporada."
)

titulo("O resultado de agora")
paragrafo("Com 11 mil das 108 mil partidas previstas, ou seja 10 por cento:")
tabela(
    ["Tipo de evento", "Campeoes acima do tipico", "Chance por acaso",
     "Leitura"],
    [
        ["skin", "15 de 20", "0,021", "o unico que chama atencao"],
        ["clipe", "7 de 10", "0,172", "nada"],
        ["exposicao", "13 de 24", "0,419", "nada"],
        ["trailer", "2 de 5", "0,812", "nada"],
    ],
)
paragrafo(
    "O lado da skin e o unico que inclina. Com quatro tipos testados, o "
    "corte honesto fica perto de 0,0125, entao nem ele conclui nada ainda. "
    "Todos os eventos saem com a ressalva de que os intervalos de confianca "
    "se cruzam, o que e esperado com uma amostra de 10 por cento."
)

titulo("Como sabemos que o metodo funciona")
paragrafo("Tres verificacoes, e elas valem mais que o resultado em si.")
ponto(
    "Teste contra dados falsos. Existe um gerador que planta picos de forca "
    "conhecida, de 1,3 a 2,3 vezes. O metodo reencontra os dez, todos dentro "
    "de 30 por cento do esperado. Dois campeoes que pareciam falha eram o "
    "teto de 15 por cento do proprio gerador, e o metodo acertou o teto na "
    "casa decimal."
)
ponto(
    "Teste de placebo. A medida inteira e repetida 200 vezes com a data de "
    "cada evento sorteada, para mostrar quantos destaques o metodo inventa "
    "quando nao ha nada para achar. Nos dados falsos ele dispara, com chance "
    "0,000. Nos dados reais nao dispara."
)
ponto(
    "Validacao externa. A nossa taxa de escolha foi comparada com o op.gg em "
    "16 campeoes do servidor brasileiro, e a razao media deu 0,98. Erro de "
    "conta, de unidade ou de contagem dobrada apareceria aqui como 0,1 ou "
    "2,0."
)

titulo("Erros que o proprio metodo pegou")
paragrafo(
    "Esta secao existe porque ela e o melhor argumento do trabalho. Cada um "
    "destes erros teria inflado o resultado se ninguem olhasse."
)
ponto(
    "Dos 200 registros de skin nova, 170 eram cromas, que sao variacoes de "
    "cor da mesma skin. Conta-las como lancamento faria uma skin valer dez "
    "eventos."
)
ponto(
    "A janela de 14 dias depois do evento diluia o pico ate quase sumir, "
    "porque efeito de novidade dura poucos dias."
)
ponto(
    "Dois campeoes ganharam duas skins no mesmo patch, o que criava a mesma "
    "medida contada duas vezes."
)
ponto(
    "Clipe e trailer do mesmo lancamento saem com dois a quatro dias de "
    "diferenca e medem quase o mesmo pedaco da serie, entao nao sao duas "
    "evidencias independentes."
)
ponto(
    "Um clipe musical estava faltando, porque a busca procurava pelo nome da "
    "skin e o titulo do video nao dividia nenhuma palavra com ele."
)

titulo("Limitacoes, ditas sem rodeio")
ponto(
    "A amostra e enviesada para elo alto. Semeamos 400 jogadores por elo em "
    "dez elos, o que da peso igual a Ferro e a Challenger, enquanto a "
    "populacao real e quase toda de elo baixo. A nossa taxa nao e a taxa do "
    "servidor e nunca pretendeu ser. Para comparar antes e depois isso em "
    "boa parte se cancela, porque o vies e o mesmo nos dois lados."
)
ponto(
    "Jogador que joga mais entra mais vezes na amostra, pelo mesmo motivo e "
    "com o mesmo efeito."
)
ponto(
    "Skin fica no servidor de teste umas duas semanas antes de entrar no "
    "jogo, entao uma base colada no lancamento ja viu a skin. A analise "
    "afasta a base 14 dias para escapar disso, e essa decisao foi registrada "
    "por escrito antes de a coleta terminar."
)
ponto(
    "A lista de campeoes que aparecem no teaser de Nova Alvorada foi feita "
    "por alguem assistindo ao video, nao por medicao. O arquivo marca isso "
    "em coluna propria."
)
ponto(
    "Os dois eventos de 18 de novembro nao tem como ser medidos, porque o "
    "periodo acaba naquele dia e nao sobra depois."
)

titulo("O que falta")
ponto(
    "Terminar a coleta. A primeira passada fecha de madrugada, com 429 "
    "partidas por dia. A segunda dobra isso e passa do minimo de 500 por dia "
    "que o relatorio de qualidade cobra. A terceira fecha a amostra. No "
    "ritmo atual, tudo isso acaba no domingo."
)
ponto("Rodar a analise final com a amostra cheia e o recorte ja congelado.")
ponto(
    "O painel, que vai ser feito no Vercel e precisa dos dados em formato "
    "JSON, que ainda nao existe."
)
ponto("Escrever a apresentacao de 20 minutos.")

titulo("O que cada pessoa deveria fazer")

titulo("Pessoa 1, coleta", 2)
ponto(
    "Trocar a chave da Riot quando ela expirar, o que acontece as 14h de "
    "sabado. O coletor avisa na tela e retoma sozinho depois da troca."
)
ponto(
    "Conferir o log uma vez por dia e rodar a agregacao e o relatorio de "
    "qualidade quando quiser um retrato novo."
)

titulo("Pessoa 2, eventos e analise", 2)
ponto(
    "Conferir os oito videos da tabela acima, abrindo cada um. A escolha foi "
    "automatica, e quem assina o dado e uma pessoa."
)
ponto(
    "Decidir, junto com as outras duas, qual momento vale como leitura das "
    "visualizacoes dos videos, porque esse numero muda todo dia e o contrato "
    "de dados nao tem coluna de data para ele."
)
ponto(
    "Olhar a coluna de mudancas de balanceamento antes de afirmar qualquer "
    "coisa sobre um campeao."
)

titulo("Pessoa 3, site", 2)
ponto(
    "Montar o painel no Vercel lendo os arquivos de dados, e deixar visivel "
    "na tela quando o dado for de desenvolvimento e nao o real."
)
ponto(
    "Lembrar no texto do site que o total de partidas do dia e o total da "
    "AMOSTRA, nao o total jogado no servidor, entao o que vale comparar "
    "entre dias e a taxa e nao a contagem."
)

titulo("Como rodar")
paragrafo(
    "Todos os comandos usam o ambiente virtual do projeto, na pasta .venv, e "
    "rodam a partir da pasta do projeto."
)
tabela(
    ["O que", "Comando"],
    [
        ["Coletar partidas", "coleta\\coletar.py"],
        ["Gerar a tabela diaria", "coleta\\agregar.py"],
        ["Relatorio de qualidade", "coleta\\qualidade.py"],
        ["Skins novas por patch", "coleta\\datadragon_skins.py"],
        ["Mudancas de balanceamento", "coleta\\datadragon_balanceamento.py"],
        ["Montar a tabela de eventos", "eventos\\montar_eventos.py"],
        ["Analise antes e depois", "analise\\efeito_vitrine.py"],
        ["Testar o metodo", "analise\\efeito_vitrine.py --mock"],
    ],
)
paragrafo(
    "O coletor religa sozinho quando alguem faz login na maquina, e recusa "
    "subir se ja houver outro rodando, para dois nao brigarem pelo mesmo "
    "banco."
)

titulo("Uma palavra sobre o resultado")
paragrafo(
    "Existe uma chance real de a resposta final ser que nao ha efeito "
    "mensuravel. Isso e um resultado, e com grupo de controle, teste de "
    "placebo, validacao externa e recorte congelado por escrito, e um "
    "resultado que se defende. O que nao se defende e um numero bonito sem "
    "nenhuma dessas verificacoes."
)

doc.save(sys.argv[1])
print("gerado:", sys.argv[1])
