"""
Monta data/processed/events.csv a partir das skins e dos clipes do YouTube.

Duas fontes:

1. data/processed/new_skins.csv, sem os cromas, cruzado com
   data/processed/patch_dates.csv, da o evento de LANCAMENTO DE SKIN, com a
   data medida em que o patch entrou no BR1.
2. a YouTube Data API v3, buscando o clipe de cada linha de skin, da o evento
   de CLIPE, com a data de publicacao e as visualizacoes.

Uma linha por campeao por evento. O event_id repete entre os campeoes do
mesmo evento, entao a analise agrupa por ele. O clipe do HEARTSTEEL com seis
campeoes vira seis linhas com o mesmo event_id.

A escolha do video e um palpite de busca, entao o script imprime o que achou,
com canal e data, para conferencia humana antes de usar.

Rodar:         .venv\\Scripts\\python.exe eventos\\montar_eventos.py
Sem gastar cota: .venv\\Scripts\\python.exe eventos\\montar_eventos.py --sem-youtube
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_ENV = RAIZ / ".env"
NOVAS_SKINS = RAIZ / "data" / "processed" / "new_skins.csv"
CACHE = RAIZ / "data" / "cache_youtube"
DATAS_PATCHES = RAIZ / "data" / "processed" / "patch_dates.csv"
SAIDA = RAIZ / "data" / "processed" / "events.csv"

FUSO = ZoneInfo("America/Sao_Paulo")
BUSCA = "https://www.googleapis.com/youtube/v3/search"
VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

#sufixos que marcam variante da mesma skin, nao linha nova
SUFIXOS = ["de prestigio", "prestigio"]

#so canal oficial conta como evento. video de canal de terceiro, tipo
#spotlight de skin, nao e lancamento de nada.
CANAIS_OFICIAIS = ["leagueoflegends", "riotgames", "riotmusic"]

#o clipe tem que sair perto do patch da skin. sem essa janela a busca aceita
#video de 2023 e 2024 com nome parecido, que nao e o lancamento nenhum.
DIAS_ANTES = 60
DIAS_DEPOIS = 15


def normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in sem_acento if c.isalnum())


def tira_nome_do_campeao(nome_skin: str, campeao: str) -> str:
    """De "K'Sante HEARTSTEEL Live My Life" devolve "HEARTSTEEL Live My Life".

    O nome na skin e o nome de exibicao, com apostrofo e espaco, e a coluna
    champion e o id, sem nada disso. Compara normalizado, palavra por
    palavra, ate casar.
    """
    alvo = normaliza(campeao)
    palavras = nome_skin.split()
    for quantas in range(1, len(palavras) + 1):
        acumulado = normaliza(" ".join(palavras[:quantas]))
        if acumulado == alvo:
            return " ".join(palavras[quantas:]).strip()
        if not alvo.startswith(acumulado):
            break
    return nome_skin


def tira_sufixo(linha: str) -> str:
    """Prestigio e variante da mesma skin, entao cai na mesma linha.

    Sem isso o Sett fica fora do HEARTSTEEL e o Ekko fora do True Damage,
    so porque a versao deles e de Prestigio.
    """
    palavras = linha.split()
    for sufixo in SUFIXOS:
        alvo = normaliza(sufixo)
        for quantas in range(1, min(3, len(palavras)) + 1):
            if normaliza(" ".join(palavras[-quantas:])) == alvo:
                return " ".join(palavras[:-quantas]).strip()
    return linha


def junta_linhas_estendidas(grupos: dict) -> dict:
    """Linha que comeca com outra do mesmo patch e variante dela.

    "K/DA FIRESTARTER Ignicao" cai em "K/DA FIRESTARTER", senao a Akali fica
    como evento solto de um campeao so, separada das outras tres do mesmo
    lancamento. Nao mexe em "Deus Antigo" e "Deusa Antiga", que divergem
    antes do fim, nem em "K/DA Hitmaker", que e outra skin.
    """
    por_patch: dict[str, list[str]] = {}
    for versao, linha in grupos:
        por_patch.setdefault(versao, []).append(linha)

    destino: dict[tuple[str, str], tuple[str, str]] = {}
    for versao, linhas in por_patch.items():
        for linha in linhas:
            for outra in linhas:
                if outra == linha or len(normaliza(outra)) < 6:
                    continue
                if normaliza(linha).startswith(normaliza(outra)):
                    destino[(versao, linha)] = (versao, outra)

    novos: dict[tuple[str, str], list[dict]] = {}
    for chave, itens in grupos.items():
        final = chave
        for _ in range(3):
            if final not in destino:
                break
            final = destino[final]
        novos.setdefault(final, []).extend(itens)
    return novos


def eh_croma(nome: str) -> bool:
    return nome.endswith(")") and " (" in nome


def slug(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", (texto or "").lower())
    #joga fora o acento solto antes de trocar o resto por hifen, senao
    #"Congregacao" virava "congregac-a-o"
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    limpo = "".join(c if c.isalnum() else "-" for c in sem_acento)
    while "--" in limpo:
        limpo = limpo.replace("--", "-")
    return limpo.strip("-")


def le_datas_dos_patches() -> dict[str, dict]:
    if not DATAS_PATCHES.exists():
        return {}
    with open(DATAS_PATCHES, encoding="utf-8") as arquivo:
        return {l["patch"]: l for l in csv.DictReader(arquivo)}


def le_lancamentos() -> list[dict]:
    """Skins de verdade, com a linha a que pertencem."""
    if not NOVAS_SKINS.exists():
        return []
    lancamentos = []
    with open(NOVAS_SKINS, encoding="utf-8") as arquivo:
        for registro in csv.DictReader(arquivo):
            if eh_croma(registro["skin_name"]):
                continue
            linha = tira_sufixo(
                tira_nome_do_campeao(registro["skin_name"],
                                     registro["champion"])
            )
            lancamentos.append({
                "version": registro["version"],
                "champion": registro["champion"],
                "skin_name": registro["skin_name"],
                "linha": linha or registro["skin_name"],
            })
    return lancamentos


class YouTube:
    def __init__(self, sem_cache: bool = False) -> None:
        self.sem_cache = sem_cache
        valores = dotenv_values(ARQUIVO_ENV)
        self.chave = (valores.get("YOUTUBE_API_KEY") or "").strip()
        if not self.chave:
            print(f"[erro] YOUTUBE_API_KEY vazia em {ARQUIVO_ENV}")
            sys.exit(1)
        self.sessao = requests.Session()
        self.cota = 0

    def pede(self, url: str, parametros: dict, custo: int):
        #a chave vai no cabecalho, nunca na URL, para nao vazar em log
        resposta = self.sessao.get(
            url,
            params=parametros,
            headers={"X-goog-api-key": self.chave},
            timeout=30,
        )
        self.cota += custo
        if resposta.status_code == 200:
            return resposta.json()
        corpo = resposta.json() if resposta.content else {}
        mensagem = (corpo.get("error") or {}).get("message", "sem mensagem")
        print(f"[erro] HTTP {resposta.status_code} no YouTube: {mensagem}")
        return None

    def procura(self, termo: str, quantos: int = 10) -> list[dict]:
        """Busca com cache em disco.

        O search.list custa 100 unidades por chamada, nao por resultado,
        entao pedir 10 em vez de 5 sai de graca. E resultado de busca nao
        muda de um dia para o outro, enquanto as visualizacoes mudam, logo
        vale guardar a busca e repetir so o videos.list, que custa 1. Sem o
        cache, montar o events.csv de novo gasta 1400 unidades das 10000 do
        dia e so da para sete rodadas.
        """
        guardado = CACHE / f"{slug(termo)}.json"
        if guardado.exists() and not self.sem_cache:
            try:
                return json.loads(guardado.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                guardado.unlink()
        dados = self.pede(BUSCA, {
            "part": "snippet",
            "q": termo,
            "type": "video",
            "maxResults": quantos,
            "order": "relevance",
        }, custo=100)
        if not dados:
            return []
        achados = []
        for item in dados.get("items") or []:
            trecho = item.get("snippet") or {}
            achados.append({
                "youtube_id": (item.get("id") or {}).get("videoId", ""),
                "title": trecho.get("title", ""),
                "canal": trecho.get("channelTitle", ""),
                "publicado": trecho.get("publishedAt", ""),
            })
        guardado.parent.mkdir(parents=True, exist_ok=True)
        guardado.write_text(json.dumps(achados, ensure_ascii=False),
                            encoding="utf-8")
        return achados

    def visualizacoes(self, ids: list[str]) -> dict[str, int]:
        if not ids:
            return {}
        dados = self.pede(VIDEOS, {
            "part": "statistics",
            "id": ",".join(ids[:50]),
        }, custo=1)
        if not dados:
            return {}
        contagem = {}
        for item in dados.get("items") or []:
            bruto = (item.get("statistics") or {}).get("viewCount")
            if bruto is not None:
                contagem[item.get("id", "")] = int(bruto)
        return contagem


def canal_oficial(canal: str) -> bool:
    normal = normaliza(canal)
    return any(oficial in normal for oficial in CANAIS_OFICIAIS)


def escolhe_video(achados: list[dict],
                  data_patch: str) -> tuple[dict | None, list[tuple]]:
    """Primeiro resultado de canal oficial publicado perto do patch.

    Devolve tambem os recusados com o motivo, para o humano conferir se a
    busca jogou fora algo que devia entrar.
    """
    recusados: list[tuple] = []
    for achado in achados:
        if not canal_oficial(achado["canal"]):
            recusados.append((achado, f"canal {achado['canal']}"))
            continue
        dia = dia_publicado(achado["publicado"])
        if not dia:
            recusados.append((achado, "sem data de publicacao"))
            continue
        if not data_patch:
            return achado, recusados
        distancia = (date.fromisoformat(data_patch)
                     - date.fromisoformat(dia)).days
        if not -DIAS_DEPOIS <= distancia <= DIAS_ANTES:
            recusados.append((achado, f"publicado em {dia}, "
                                      f"{distancia} dias antes do patch"))
            continue
        return achado, recusados
    return None, recusados


def nome_do_evento(entrada: dict) -> str:
    """Nome do clipe quando varias linhas de skin caem no mesmo video.

    Vale a linha que aparece no titulo do video, e a mais especifica entre
    elas. Sem isso o clipe do FIRESTARTER sairia com o nome da linha
    Hitmaker, so porque ela e mais curta.
    """
    titulo = normaliza(entrada["achado"]["title"])
    no_titulo = [linha for linha in entrada["linhas"]
                 if normaliza(linha) and normaliza(linha) in titulo]
    if no_titulo:
        return max(no_titulo, key=lambda linha: len(normaliza(linha)))
    return sorted(entrada["linhas"], key=len)[0]


def dia_publicado(texto: str) -> str:
    #publishedAt vem em UTC, como 2026-10-02T15:00:00Z
    if not texto:
        return ""
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return momento.astimezone(FUSO).date().isoformat()


def escreve_csv(eventos: list[dict]) -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    parcial = SAIDA.parent / (SAIDA.name + ".parcial")
    colunas = ["event_id", "champion", "event_type", "event_date", "title",
               "youtube_id", "views"]
    with open(parcial, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        for evento in eventos:
            escritor.writerow(evento)
    os.replace(parcial, SAIDA)


def main() -> int:
    analisador = argparse.ArgumentParser(description="Monta o events.csv")
    analisador.add_argument("--sem-youtube", action="store_true",
                            help="so os eventos de skin, sem gastar cota")
    analisador.add_argument("--buscar-de-novo", action="store_true",
                            help="ignora o cache de busca e procura outra vez")
    argumentos = analisador.parse_args()

    lancamentos = le_lancamentos()
    if not lancamentos:
        print(f"[erro] {NOVAS_SKINS} vazio ou ausente. "
              "rode coleta/datadragon_skins.py primeiro.")
        return 1
    datas = le_datas_dos_patches()
    if not datas:
        print(f"[erro] {DATAS_PATCHES} ausente. "
              "rode coleta/qualidade.py primeiro.")
        return 1

    #agrupa por linha de skin dentro do patch
    grupos: dict[tuple[str, str], list[dict]] = {}
    for item in lancamentos:
        grupos.setdefault((item["version"], item["linha"]), []).append(item)
    grupos = junta_linhas_estendidas(grupos)

    print(f"{len(lancamentos)} lancamentos de skin em {len(grupos)} linhas:")
    for (versao, linha), itens in sorted(grupos.items()):
        nomes = ", ".join(sorted(i["champion"] for i in itens))
        print(f"  {versao}  {linha}  ->  {nomes}")
    print("")

    eventos: list[dict] = []
    fora: list[str] = []
    for (versao, linha), itens in sorted(grupos.items()):
        registro = datas.get(versao) or {}
        data = registro.get("patch_date", "")
        exata = registro.get("exata", "0") == "1"
        #patch sem limite de baixo ja estava no ar quando o periodo comecou,
        #logo a skin saiu antes do dado existir e nao tem "antes" para
        #comparar. entrar com a data do inicio do periodo seria inventar um
        #lancamento que nao aconteceu ali.
        if not exata and not (registro.get("intervalo_de") or ""):
            fora.append(f"{versao} {linha}")
            continue
        identificador = f"skin-{versao}-{slug(linha)}"
        for item in sorted(itens, key=lambda i: i["champion"]):
            eventos.append({
                "event_id": identificador,
                "champion": item["champion"],
                "event_type": "skin",
                "event_date": data,
                "title": item["skin_name"],
                "youtube_id": "",
                "views": "",
            })
        if not exata:
            print(f"[aviso] a data do patch {versao} nao e exata, "
                  f"a linha {linha} herda {data} como limite de cima")
    if fora:
        print(f"[fora] {len(fora)} linhas de skin nao entraram, porque o "
              "patch delas ja estava no ar quando o periodo comecou e nao "
              "existe 'antes' para comparar:")
        for nome in fora:
            print(f"  {nome}")
        print("")

    if argumentos.sem_youtube:
        escreve_csv(eventos)
        print("")
        print(f"{SAIDA.relative_to(RAIZ)}: {len(eventos)} linhas, "
              "so eventos de skin. nenhuma cota gasta.")
        return 0

    youtube = YouTube(sem_cache=argumentos.buscar_de_novo)
    linhas_unicas = sorted({linha for _, linha in grupos})
    print(f"procurando o clipe de {len(linhas_unicas)} linhas no YouTube. "
          "busca em cache sai de graca, busca nova custa 100 unidades")
    print("")

    data_da_linha = {
        linha: (datas.get(versao) or {}).get("patch_date", "")
        for versao, linha in grupos
    }
    escolhidos: dict[str, dict] = {}
    sem_clipe: list[tuple[str, list]] = []
    for linha in linhas_unicas:
        achados = youtube.procura(f"{linha} League of Legends")
        escolhido, recusados = escolhe_video(achados, data_da_linha[linha])
        if escolhido is None:
            sem_clipe.append((linha, recusados))
            continue
        escolhidos[linha] = escolhido
        print(f"  {linha}")
        print(f"    {escolhido['title']}")
        print(f"    canal {escolhido['canal']} | "
              f"{dia_publicado(escolhido['publicado'])} | "
              f"id {escolhido['youtube_id']}")

    if sem_clipe:
        print("")
        print(f"[sem clipe] {len(sem_clipe)} linhas ficaram sem video, e isso "
              "costuma ser o certo: skin sem clipe musical nao tem evento de "
              "clipe. o primeiro recusado de cada uma, para conferencia:")
        for linha, recusados in sem_clipe:
            if recusados:
                achado, motivo = recusados[0]
                print(f"  {linha}: {achado['title'][:60]} ({motivo})")
            else:
                print(f"  {linha}: a busca nao devolveu nada")

    #um video vale um evento, mesmo que duas linhas de skin cheguem nele
    por_video: dict[str, dict] = {}
    for (versao, linha), itens in sorted(grupos.items()):
        escolhido = escolhidos.get(linha)
        if not escolhido or not escolhido["youtube_id"]:
            continue
        entrada = por_video.setdefault(escolhido["youtube_id"], {
            "achado": escolhido,
            "campeoes": set(),
            "linhas": [],
        })
        entrada["campeoes"].update(item["champion"] for item in itens)
        entrada["linhas"].append(linha)

    contagem = youtube.visualizacoes(sorted(por_video))
    for youtube_id, entrada in sorted(por_video.items()):
        achado = entrada["achado"]
        identificador = f"clipe-{slug(nome_do_evento(entrada))}"
        for campeao in sorted(entrada["campeoes"]):
            eventos.append({
                "event_id": identificador,
                "champion": campeao,
                "event_type": "clipe",
                "event_date": dia_publicado(achado["publicado"]),
                "title": achado["title"],
                "youtube_id": youtube_id,
                "views": contagem.get(youtube_id, ""),
            })
        if len(entrada["linhas"]) > 1:
            juntas = ", ".join(sorted(entrada["linhas"]))
            print("")
            print(f"[juntado] {juntas} cairam no mesmo video, entao viraram "
                  f"um evento so, {identificador}")

    escreve_csv(eventos)
    de_skin = sum(1 for e in eventos if e["event_type"] == "skin")
    de_clipe = len(eventos) - de_skin
    print("")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(eventos)} linhas, "
          f"{de_skin} de skin e {de_clipe} de clipe, "
          f"{len(por_video)} clipes distintos")
    print(f"cota gasta: {youtube.cota} unidades de 10000 por dia")
    print("a coluna views e um retrato de agora, e nao tem coluna de data no "
          "contrato. combine com as outras pessoas o momento da leitura.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
