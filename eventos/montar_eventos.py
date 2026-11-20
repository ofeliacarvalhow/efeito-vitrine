"""
Monta data/processed/events.csv a partir das skins e dos videos da Riot.

Duas fontes:

1. data/processed/new_skins.csv, sem os cromas, cruzado com
   data/processed/patch_dates.csv, da o evento de LANCAMENTO DE SKIN, com a
   data medida em que o patch entrou no BR1.
2. o catalogo dos canais oficiais da Riot no periodo da o evento de CLIPE,
   de TRAILER e de EXPOSICAO.

Uma linha por campeao por evento. O event_id repete entre os campeoes do
mesmo evento, entao a analise agrupa por ele.

Rodar:           .venv\\Scripts\\python.exe eventos\\montar_eventos.py
Sem gastar cota: .venv\\Scripts\\python.exe eventos\\montar_eventos.py --sem-youtube
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

from youtube_catalogo import YouTube, normaliza, palavras

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_ENV = RAIZ / ".env"
NOVAS_SKINS = RAIZ / "data" / "processed" / "new_skins.csv"
DATAS_PATCHES = RAIZ / "data" / "processed" / "patch_dates.csv"
CACHE = RAIZ / "data" / "cache_youtube"
SAIDA = RAIZ / "data" / "processed" / "events.csv"

FUSO = ZoneInfo("America/Sao_Paulo")

#sufixos que marcam variante da mesma skin, nao linha nova
SUFIXOS = ["de prestigio", "prestigio"]

#janela em que um video conta como ligado ao patch da skin
DIAS_ANTES = 60
DIAS_DEPOIS = 15
#o catalogo cobre um pouco alem das skins, para pegar clipe que sai antes
FOLGA_DO_CATALOGO = 75

#palavra que nao distingue linha nenhuma e so atrapalha o casamento
VAZIAS = {"de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "the"}

#classificacao pelo titulo. a ordem importa: clipe ganha de trailer.
TIPOS = [
    #a Riot nao e consistente: o clipe do K/DA com a DJ Sona termina em
    #"(Official Video)", sem o "Music" que os outros tres tem. so com
    #"official music video" aquele clipe ficava de fora. no catalogo do
    #periodo esse termo mais frouxo pega um titulo so, e e justamente ele.
    ("clipe", ["official music video", "official video", "videoclipe oficial",
               "video oficial"]),
    ("trailer", ["skins trailer", "trailer das skins", "trailer de skins",
                 "gameplay trailer", "trailer de mecanica"]),
    ("exposicao", ["opening ceremony", "cerimonia de abertura"]),
]


def eh_croma(nome: str) -> bool:
    return nome.endswith(")") and " (" in nome


def slug(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", (texto or "").lower())
    sem_acento = "".join(c for c in decomposto
                         if not unicodedata.combining(c))
    limpo = "".join(c if c.isalnum() else "-" for c in sem_acento)
    while "--" in limpo:
        limpo = limpo.replace("--", "-")
    return limpo.strip("-")


def tira_nome_do_campeao(nome_skin: str, campeao: str) -> str:
    """De "K'Sante HEARTSTEEL Live My Life" devolve "HEARTSTEEL Live My Life".

    O nome na skin e o nome de exibicao, com apostrofo e espaco, e a coluna
    champion e o id, sem nada disso. Compara normalizado, palavra por
    palavra, ate casar.
    """
    alvo = normaliza(campeao).replace(" ", "")
    pedacos = nome_skin.split()
    for quantas in range(1, len(pedacos) + 1):
        acumulado = normaliza(" ".join(pedacos[:quantas])).replace(" ", "")
        if acumulado == alvo:
            return " ".join(pedacos[quantas:]).strip()
        if not alvo.startswith(acumulado):
            break
    return nome_skin


def tira_sufixo(linha: str) -> str:
    """Prestigio e variante da mesma skin, entao cai na mesma linha."""
    pedacos = linha.split()
    for sufixo in SUFIXOS:
        alvo = normaliza(sufixo).replace(" ", "")
        for quantas in range(1, min(3, len(pedacos)) + 1):
            if normaliza(" ".join(pedacos[-quantas:])).replace(" ", "") \
                    == alvo:
                return " ".join(pedacos[:-quantas]).strip()
    return linha


def junta_linhas_estendidas(grupos: dict) -> dict:
    """Linha que comeca com outra do mesmo patch e variante dela.

    "K/DA FIRESTARTER Ignicao" cai em "K/DA FIRESTARTER", senao a Akali fica
    como evento solto de um campeao so. Nao mexe em "Deus Antigo" e "Deusa
    Antiga", que divergem antes do fim.
    """
    por_patch: dict[str, list[str]] = {}
    for versao, linha in grupos:
        por_patch.setdefault(versao, []).append(linha)

    destino: dict[tuple[str, str], tuple[str, str]] = {}
    for versao, linhas in por_patch.items():
        for linha in linhas:
            for outra in linhas:
                se_outra = normaliza(outra).replace(" ", "")
                if outra == linha or len(se_outra) < 6:
                    continue
                if normaliza(linha).replace(" ", "").startswith(se_outra):
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


def dia_publicado(texto: str) -> date | None:
    #publishedAt vem em UTC, como 2026-10-02T15:00:00Z
    if not texto:
        return None
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento.astimezone(FUSO).date()


def classifica(titulo: str) -> str | None:
    """Que tipo de evento o titulo anuncia, ou None se nao for lancamento.

    Deixa de fora bastidor, coreografia, visualizador de musica, corte
    curto e tudo mais que comenta um lancamento em vez de ser um.
    """
    texto = normaliza(titulo)
    for tipo, marcas in TIPOS:
        if any(normaliza(marca) in texto for marca in marcas):
            return tipo
    return None


def tokens_da_linha(linha: str) -> list[str]:
    return [p for p in palavras(linha) if p not in VAZIAS and len(p) > 2]


def casa_linha(titulo: str, linha: str, campeoes: set[str], tipo: str,
               quando: date, data_do_patch: date | None) -> str | None:
    """Esse video fala desta linha de skin?

    Tres regras, da mais segura para a mais frouxa:

    1. todas as palavras da linha aparecem no titulo. pega
       "K/DA - FIRESTARTER" e recusa "K/DA - WATCH ME".
    2. o nome de um campeao da linha aparece como palavra inteira e o video
       saiu perto do patch. e o que acha o clipe "K/DA, DJ Sona - GIRLS",
       cujo titulo nao divide palavra nenhuma com "DJ Sona Remix Supremo".
       palavra inteira importa: "Mel" nao pode casar com "melhor".
    3. so para exposicao, a primeira palavra da linha basta, porque a
       cerimonia cita o grupo e nao a skin.
    """
    conjunto = set(palavras(titulo))
    tokens = tokens_da_linha(linha)
    if tokens and all(t in conjunto for t in tokens):
        return "forte"
    if data_do_patch and tipo in ("clipe", "trailer"):
        perto = (data_do_patch - timedelta(days=DIAS_ANTES) <= quando
                 <= data_do_patch + timedelta(days=DIAS_DEPOIS))
        if perto and any(normaliza(c) in conjunto for c in campeoes):
            return "campeao"
    if tipo == "exposicao" and tokens and tokens[0] in conjunto:
        return "grupo"
    return None


def nome_do_evento(entrada: dict) -> str:
    """Como chamar o evento.

    Linha casada palavra por palavra manda, porque e a certeza. Se nao tem
    nenhuma e so uma linha casou, vale ela. Se varias casaram, como na
    cerimonia do Mundial, que cita K/DA e True Damage de uma vez, o nome sai
    pelo tipo e pela data, para nao dar a entender que o evento e de um
    grupo so.
    """
    if entrada["fortes"]:
        return slug(max(entrada["fortes"], key=len))
    if len(entrada["linhas"]) == 1:
        return slug(entrada["linhas"][0])
    return entrada["quando"].isoformat()


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
                            help="ignora o cache e varre os canais de novo")
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
        #comparar
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
    if fora:
        print(f"[fora] {len(fora)} linhas de skin nao entraram, porque o "
              "patch delas ja estava no ar quando o periodo comecou e nao "
              "existe 'antes' para comparar:")
        for nome in fora:
            print(f"  {nome}")
        print("")

    if argumentos.sem_youtube:
        escreve_csv(eventos)
        print(f"{SAIDA.relative_to(RAIZ)}: {len(eventos)} linhas, "
              "so eventos de skin. nenhuma cota gasta.")
        return 0

    chave = (dotenv_values(ARQUIVO_ENV).get("YOUTUBE_API_KEY") or "").strip()
    if not chave:
        print(f"[erro] YOUTUBE_API_KEY vazia em {ARQUIVO_ENV}")
        return 1
    youtube = YouTube(chave, CACHE, sem_cache=argumentos.buscar_de_novo)

    todas_as_datas = [date.fromisoformat(d["patch_date"])
                      for d in datas.values() if d.get("patch_date")]
    de = min(todas_as_datas) - timedelta(days=FOLGA_DO_CATALOGO)
    ate = max(todas_as_datas) + timedelta(days=FOLGA_DO_CATALOGO)
    print(f"varrendo os canais oficiais de {de} a {ate}")
    catalogo = youtube.catalogo(de, ate)
    print(f"{len(catalogo)} videos no catalogo, "
          f"{youtube.cota} unidades gastas ate aqui")
    print("")

    #um video vale um evento, com todos os campeoes que ele cita juntos.
    #sem isso a cerimonia do Mundial, que cita K/DA e True Damage, virava
    #tres eventos e a Evelynn aparecia duas vezes no mesmo video.
    por_video: dict[tuple[str, str], dict] = {}
    for video in catalogo:
        tipo = classifica(video["titulo"])
        if not tipo:
            continue
        quando = dia_publicado(video["publicado"])
        if not quando:
            continue
        for (versao, linha), itens in grupos.items():
            registro = datas.get(versao) or {}
            bruto = registro.get("patch_date") or ""
            data_do_patch = date.fromisoformat(bruto) if bruto else None
            campeoes = {i["champion"] for i in itens}
            forca = casa_linha(video["titulo"], linha, campeoes, tipo,
                               quando, data_do_patch)
            if not forca:
                continue
            chave = (tipo, video["youtube_id"])
            entrada = por_video.setdefault(chave, {
                "tipo": tipo, "quando": quando, "video": video,
                "campeoes": set(), "linhas": [], "fortes": [],
            })
            entrada["campeoes"].update(campeoes)
            if linha not in entrada["linhas"]:
                entrada["linhas"].append(linha)
            if forca == "forte" and linha not in entrada["fortes"]:
                entrada["fortes"].append(linha)

    vistas = youtube.visualizacoes(
        sorted({e["video"]["youtube_id"] for e in por_video.values()})
    )

    #o mesmo lancamento sai nos dois canais, com ids diferentes. mesmo tipo,
    #mesmo dia e mesmos campeoes e o mesmo evento, e vence o de mais views.
    escolhidos: dict[tuple, dict] = {}
    for entrada in por_video.values():
        chave = (entrada["tipo"], entrada["quando"],
                 frozenset(entrada["campeoes"]))
        atual = escolhidos.get(chave)
        if atual is None or (vistas.get(entrada["video"]["youtube_id"], 0)
                             > vistas.get(atual["video"]["youtube_id"], 0)):
            escolhidos[chave] = entrada

    #a Riot publica o video cheio e tambem cortes por grupo. mesmo tipo,
    #mesmo dia e conjunto de campeoes contido no de outro video e o mesmo
    #evento visto de perto, entao fica o mais abrangente. sem isso a Akali
    #e a Evelynn contariam duas vezes na cerimonia do Mundial.
    sobreviventes: list[dict] = []
    for entrada in escolhidos.values():
        contido = any(
            outra is not entrada
            and outra["tipo"] == entrada["tipo"]
            and outra["quando"] == entrada["quando"]
            and entrada["campeoes"] < outra["campeoes"]
            for outra in escolhidos.values()
        )
        if not contido:
            sobreviventes.append(entrada)
    colapsados = len(escolhidos) - len(sobreviventes)
    if colapsados:
        print(f"  [colapsado] {colapsados} videos eram corte de um evento "
              "maior do mesmo dia e sairam")
        print("")

    for entrada in sorted(sobreviventes,
                          key=lambda e: (e["tipo"], e["quando"])):
        video = entrada["video"]
        identificador = f"{entrada['tipo']}-{nome_do_evento(entrada)}"
        print(f"  [{entrada['tipo']}] {entrada['quando']}  "
              f"{identificador}")
        print(f"      {video['titulo'][:72]}")
        print(f"      {video['canal']} | "
              f"{vistas.get(video['youtube_id'], 0):,} views | "
              f"{len(entrada['campeoes'])} campeoes | "
              f"https://youtu.be/{video['youtube_id']}")
        for campeao in sorted(entrada["campeoes"]):
            eventos.append({
                "event_id": identificador,
                "champion": campeao,
                "event_type": entrada["tipo"],
                "event_date": entrada["quando"].isoformat(),
                "title": video["titulo"],
                "youtube_id": video["youtube_id"],
                "views": vistas.get(video["youtube_id"], ""),
            })

    escreve_csv(eventos)
    print("")
    contagem = {t: sum(1 for e in eventos if e["event_type"] == t)
                for t in sorted({e["event_type"] for e in eventos})}
    resumo = ", ".join(f"{n} de {t}" for t, n in contagem.items())
    print(f"{SAIDA.relative_to(RAIZ)}: {len(eventos)} linhas, {resumo}")
    print(f"eventos distintos: {len(set(e['event_id'] for e in eventos))}")
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
