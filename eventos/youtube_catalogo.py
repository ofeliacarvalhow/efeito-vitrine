"""
Catalogo do que os canais oficiais da Riot publicaram num periodo.

Substitui a busca por nome de skin, que era cara e cega. Buscar custa 100
unidades por chamada e depende de adivinhar o termo certo: procurar
"DJ Sona Remix Supremo" nao acha o clipe chamado "K/DA, DJ Sona - GIRLS",
porque os titulos nao dividem palavra nenhuma. Listar o canal custa 1 unidade
por pagina de 50 e traz tudo, e dai o casamento e feito em cima do texto que
a Riot realmente publicou.

Varrer os dois canais por quatro meses sai por volta de 6 unidades.
"""
from __future__ import annotations

import json
import unicodedata
from datetime import date, datetime
from pathlib import Path

import requests

CANAIS = "https://www.googleapis.com/youtube/v3/channels"
ITENS = "https://www.googleapis.com/youtube/v3/playlistItems"
VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

#os dois canais da Riot, resolvidos a partir do channelId dos clipes do
#HEARTSTEEL, do True Damage e do K/DA. canal de terceiro nao entra: skin
#spotlight de fa nao e lancamento de nada.
CANAIS_OFICIAIS = {
    "UC2t5bjwHdUX4vM2g8TRDq5g": "League of Legends",
    "UC6Xqz2pm50gDCORYztqhDpg": "League of Legends Brasil",
}

#teto de paginas por canal, para nao varrer o canal inteiro desde 2009
PAGINAS_MAXIMAS = 14


def normaliza(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in decomposto if c.isalnum() or c.isspace())


def palavras(texto: str) -> list[str]:
    return normaliza(texto).split()


class YouTube:
    def __init__(self, chave: str, cache: Path, sem_cache: bool = False):
        self.chave = chave
        self.cache = cache
        self.sem_cache = sem_cache
        self.sessao = requests.Session()
        self.cota = 0

    def pede(self, url: str, parametros: dict, custo: int):
        #a chave vai no cabecalho, nunca na URL, para nao vazar em log
        resposta = self.sessao.get(
            url, params=parametros,
            headers={"X-goog-api-key": self.chave}, timeout=30,
        )
        self.cota += custo
        if resposta.status_code == 200:
            return resposta.json()
        corpo = resposta.json() if resposta.content else {}
        mensagem = (corpo.get("error") or {}).get("message", "sem mensagem")
        print(f"[erro] HTTP {resposta.status_code} no YouTube: {mensagem}")
        return None

    def catalogo(self, de: date, ate: date) -> list[dict]:
        """Tudo que os canais oficiais publicaram entre as duas datas."""
        guardado = self.cache / f"catalogo_{de}_{ate}.json"
        if guardado.exists() and not self.sem_cache:
            try:
                return json.loads(guardado.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                guardado.unlink()

        videos: list[dict] = []
        for identificador, nome in CANAIS_OFICIAIS.items():
            dados = self.pede(
                CANAIS, {"part": "contentDetails", "id": identificador}, 1
            )
            if not dados or not dados.get("items"):
                continue
            lista = (dados["items"][0]["contentDetails"]
                     ["relatedPlaylists"]["uploads"])
            pagina = None
            for _ in range(PAGINAS_MAXIMAS):
                parametros = {"part": "snippet", "playlistId": lista,
                              "maxResults": 50}
                if pagina:
                    parametros["pageToken"] = pagina
                dados = self.pede(ITENS, parametros, 1)
                if not dados:
                    break
                mais_velho = None
                for item in dados.get("items", []):
                    trecho = item.get("snippet") or {}
                    bruto = trecho.get("publishedAt") or ""
                    try:
                        quando = datetime.fromisoformat(
                            bruto.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue
                    dia = quando.date()
                    mais_velho = dia
                    if de <= dia <= ate:
                        videos.append({
                            "canal": nome,
                            "publicado": bruto,
                            "titulo": trecho.get("title", ""),
                            "youtube_id": (trecho.get("resourceId") or {})
                            .get("videoId", ""),
                        })
                pagina = dados.get("nextPageToken")
                #a playlist vem da mais nova para a mais velha, entao assim
                #que passar do inicio da janela nao ha mais o que buscar
                if not pagina or (mais_velho and mais_velho < de):
                    break

        guardado.parent.mkdir(parents=True, exist_ok=True)
        guardado.write_text(json.dumps(videos, ensure_ascii=False),
                            encoding="utf-8")
        return videos

    def visualizacoes(self, ids: list[str]) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for comeco in range(0, len(ids), 50):
            lote = ids[comeco:comeco + 50]
            dados = self.pede(
                VIDEOS, {"part": "statistics", "id": ",".join(lote)}, 1
            )
            for item in (dados or {}).get("items", []):
                bruto = (item.get("statistics") or {}).get("viewCount")
                if bruto is not None:
                    contagem[item.get("id", "")] = int(bruto)
        return contagem
