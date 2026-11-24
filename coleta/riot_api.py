"""
Cliente da API da Riot: limites de taxa, erros e pausa quando a chave expira.

Usado pelo teste_historico.py e pelo coletar.py, para o projeto ter um unico
limitador em vez de duas copias que podem discordar.

A chave sai sempre do .env, nunca de variavel de ambiente ja carregada, e
nunca aparece em mensagem, log ou excecao.
"""
from __future__ import annotations

import sys
import time
from collections import deque
from datetime import datetime, timedelta

import requests
from dotenv import dotenv_values

from config import (
    ARQUIVO_ENV,
    FILA_RANQUEADA,
    FUSO,
    IDS_POR_REQUISICAO,
    LIMITES,
    PLATAFORMA,
    REGIAO,
)


#espera maxima entre tentativas quando a rede cai
ESPERA_MAXIMA_DE_REDE = 60


class ErroDaRiot(RuntimeError):
    """A Riot devolveu 5xx nas tres tentativas.

    Quem chamou decide o que fazer. O coletor marca o item e segue, porque
    uma partida ruim nao pode derrubar uma coleta de dois dias.
    """


def mapa_limite(texto: str) -> dict[int, int]:
    #le "20:1,100:120" e devolve {1: 20, 120: 100}
    mapa: dict[int, int] = {}
    for parte in texto.split(","):
        if ":" not in parte:
            continue
        valor, janela = parte.split(":", 1)
        try:
            mapa[int(janela)] = int(valor)
        except ValueError:
            continue
    return mapa


class Janela:
    """No maximo `maximo` requisicoes em `segundos` segundos."""

    def __init__(self, maximo: int, segundos: int) -> None:
        self.maximo = maximo
        self.segundos = segundos
        self.marcas: deque[float] = deque()

    def espera_necessaria(self) -> float:
        agora = time.monotonic()
        while self.marcas and agora - self.marcas[0] >= self.segundos:
            self.marcas.popleft()
        if len(self.marcas) < self.maximo:
            return 0.0
        return self.segundos - (agora - self.marcas[0]) + 0.05

    def registra(self) -> None:
        self.marcas.append(time.monotonic())


class ClienteRiot:
    """Respeita as duas janelas de limite ao mesmo tempo."""

    def __init__(self, aviso=print) -> None:
        #aviso recebe uma linha de texto. o coletor passa o log aqui.
        self.aviso = aviso
        self.chave = self.le_chave(obrigatoria=True)
        self.janelas = [Janela(maximo, segundos) for maximo, segundos in LIMITES]
        self.por_segundos = {janela.segundos: janela for janela in self.janelas}
        self.cheias: set[int] = set()
        self.sessao = requests.Session()
        self.requisicoes = 0
        self.marcas_hora: deque[float] = deque()

    def le_chave(self, obrigatoria: bool = False) -> str:
        valores = dotenv_values(ARQUIVO_ENV)
        chave = (valores.get("RIOT_API_KEY") or "").strip()
        if not chave and obrigatoria:
            self.aviso(f"[erro] RIOT_API_KEY vazia em {ARQUIVO_ENV}")
            sys.exit(1)
        return chave

    def requisicoes_na_ultima_hora(self) -> int:
        agora = time.monotonic()
        while self.marcas_hora and agora - self.marcas_hora[0] >= 3600:
            self.marcas_hora.popleft()
        return len(self.marcas_hora)

    def espera_vaga(self) -> None:
        while True:
            espera = max(janela.espera_necessaria() for janela in self.janelas)
            if espera <= 0:
                return
            time.sleep(espera)

    def aperta_janelas(self, declarados: dict[int, int]) -> None:
        #vale sempre o limite mais apertado entre o config e o que a Riot diz
        for segundos, maximo in declarados.items():
            janela = self.por_segundos.get(segundos)
            if janela is None:
                nova = Janela(maximo, segundos)
                self.janelas.append(nova)
                self.por_segundos[segundos] = nova
                self.aviso(f"[limite] a Riot declarou {maximo} por {segundos}s, "
                           "janela nova no limitador")
            elif maximo < janela.maximo:
                self.aviso(f"[limite] a Riot declarou {maximo} por {segundos}s, "
                           f"abaixo dos {janela.maximo} do config, "
                           "vale o menor")
                janela.maximo = maximo

    def le_cabecalhos(self, resposta: requests.Response) -> None:
        """Le os limites da chave e aperta o limitador local se preciso.

        Nao dorme aqui. O limitador local ja garante no maximo 100
        requisicoes em QUALQUER intervalo de 120 segundos, e a Riot conta por
        janela fixa, que e sempre um pedaco de algum intervalo desses, logo a
        contagem dela nunca estoura. Dormir a janela inteira aqui em cima do
        limitador custava 150 segundos por lote de 100 em vez de 120. O 429
        com Retry-After e a rede de seguranca.

        So o X-App-Rate-Limit vale para o limitador, porque e o limite da
        chave inteira na regiao. O X-Method-Rate-Limit vale por endpoint, e
        aplicar o de um endpoint em todos freava a coleta sem motivo.
        """
        app = mapa_limite(resposta.headers.get("X-App-Rate-Limit", ""))
        self.aperta_janelas(app)
        contagens = mapa_limite(
            resposta.headers.get("X-App-Rate-Limit-Count", "")
        )
        for segundos, maximo in app.items():
            cheia = contagens.get(segundos, 0) >= maximo
            if cheia and segundos not in self.cheias:
                self.cheias.add(segundos)
                self.aviso(f"[limite] a janela de {segundos}s encheu com "
                           f"{contagens.get(segundos, 0)} de {maximo}, "
                           "o limitador local segura o ritmo")
            elif not cheia:
                self.cheias.discard(segundos)
        limite_metodo = mapa_limite(
            resposta.headers.get("X-Method-Rate-Limit", "")
        )
        conta_metodo = mapa_limite(
            resposta.headers.get("X-Method-Rate-Limit-Count", "")
        )
        for segundos, maximo in limite_metodo.items():
            chave = -segundos
            cheia = conta_metodo.get(segundos, 0) >= maximo
            if cheia and chave not in self.cheias:
                self.cheias.add(chave)
                self.aviso(f"[limite] o endpoint encheu a janela de "
                           f"{segundos}s com {maximo}, o 429 avisa se a Riot "
                           "cobrar")
            elif not cheia:
                self.cheias.discard(chave)

    def pausa_ate_trocar_chave(self) -> None:
        antiga = self.chave
        self.aviso("[chave] a Riot recusou a chave (401/403). "
                   "A COLETA ESTA PAUSADA.")
        self.aviso(f"[chave] troque o valor de RIOT_API_KEY em {ARQUIVO_ENV} "
                   "e eu sigo sozinho.")
        self.aviso("[chave] relendo o .env a cada 60 segundos ate o valor mudar.")
        while True:
            time.sleep(60)
            nova = self.le_chave()
            if nova and nova != antiga:
                self.chave = nova
                self.aviso("[chave] valor novo encontrado, retomando a coleta.")
                return
            self.aviso("[chave] ainda sem troca, esperando outros 60 segundos.")

    def get(self, url: str, parametros: dict | None = None):
        """Devolve o JSON, ou None em 404.

        Queda de rede nao desiste nunca: a coleta leva dois dias e o Wi-Fi
        cair por um minuto nao pode derrubar o processo. Ja 5xx segue a regra
        de tres tentativas e levanta ErroDaRiot, que o coletor trata marcando
        o item e seguindo adiante.
        """
        falhas_de_rede = 0
        falhas_da_riot = 0
        while True:
            self.espera_vaga()
            agora = time.monotonic()
            for janela in self.janelas:
                janela.registra()
            self.marcas_hora.append(agora)
            self.requisicoes += 1
            try:
                resposta = self.sessao.get(
                    url,
                    params=parametros,
                    headers={"X-Riot-Token": self.chave},
                    timeout=20,
                )
            except requests.RequestException as erro:
                falhas_de_rede += 1
                espera = min(2 ** min(falhas_de_rede, 6),
                             ESPERA_MAXIMA_DE_REDE)
                self.aviso(f"[rede] {erro.__class__.__name__} na tentativa "
                           f"{falhas_de_rede}, esperando {espera}s. o coletor "
                           "espera a rede voltar, nao desiste")
                time.sleep(espera)
                continue

            if falhas_de_rede:
                self.aviso(f"[rede] voltou depois de {falhas_de_rede} "
                           "tentativas, seguindo a coleta")
                falhas_de_rede = 0

            self.le_cabecalhos(resposta)
            codigo = resposta.status_code

            if codigo == 200:
                try:
                    return resposta.json()
                except ValueError:
                    #200 com corpo que nao e JSON e coisa de proxy ou de
                    #pagina de erro no caminho, e nao resposta da Riot. isso
                    #estourava para fora do laco e derrubava a coleta inteira.
                    #aqui conta como falha de rede e tenta de novo.
                    falhas_de_rede += 1
                    espera = min(2 ** min(falhas_de_rede, 6),
                                 ESPERA_MAXIMA_DE_REDE)
                    self.aviso(f"[rede] 200 sem JSON na tentativa "
                               f"{falhas_de_rede}, esperando {espera}s")
                    time.sleep(espera)
                    continue
            if codigo == 404:
                return None
            if codigo == 429:
                espera = int(resposta.headers.get("Retry-After", "10") or 10)
                self.aviso(f"[429] limite estourado, esperando {espera}s")
                time.sleep(espera + 1)
                continue
            if codigo in (401, 403):
                self.pausa_ate_trocar_chave()
                continue
            if 500 <= codigo < 600:
                falhas_da_riot += 1
                if falhas_da_riot > 3:
                    raise ErroDaRiot(f"HTTP {codigo} tres vezes")
                espera = 2 ** falhas_da_riot
                self.aviso(f"[{codigo}] erro da Riot, tentativa "
                           f"{falhas_da_riot}, esperando {espera}s")
                time.sleep(espera)
                continue
            #codigo fora do previsto (400, 204, 3xx de proxy) subia como
            #RuntimeError, e RuntimeError nao e ErroDaRiot: ninguem pegava,
            #a coleta morria com o traceback na tela e o log nao guardava
            #uma linha do motivo. agora tenta de novo algumas vezes e depois
            #devolve ErroDaRiot, que o baixa_lote trata deixando a partida
            #para a proxima execucao. a url nao entra na mensagem porque
            #carrega puuid.
            #a mensagem da Riot explica o motivo do 400, e so ela diz se o
            #problema e o puuid ou o parametro. ela viaja na excecao e nao
            #no log daqui, porque pode trazer o puuid dentro: quem chama
            #conhece o puuid e troca por <puuid> antes de logar.
            try:
                recado = ((resposta.json().get("status") or {})
                          .get("message") or "")[:120]
            except ValueError:
                recado = ""
            #"Exception decrypting" nao melhora com tentativa: o puuid foi
            #cifrado com outra chave e vai falhar sempre. insistir custava
            #14 segundos por jogador, e com 25 por lote a resemeadura so
            #comecava 6 minutos depois de a coleta subir.
            if "decrypting" in recado.lower():
                raise ErroDaRiot(f"HTTP {codigo} inesperado: {recado}")
            falhas_da_riot += 1
            if falhas_da_riot > 3:
                if recado:
                    raise ErroDaRiot(
                        f"HTTP {codigo} inesperado tres vezes: {recado}")
                raise ErroDaRiot(f"HTTP {codigo} inesperado tres vezes")
            espera = 2 ** falhas_da_riot
            self.aviso(f"[{codigo}] resposta inesperada, tentativa "
                       f"{falhas_da_riot}, esperando {espera}s")
            time.sleep(espera)
            continue


def intervalo(dia, dias: int) -> tuple[int, int]:
    #epoch em segundos do inicio do dia ate `dias` depois, fuso de Brasilia
    inicio = datetime(dia.year, dia.month, dia.day, tzinfo=FUSO)
    fim = inicio + timedelta(days=dias)
    return int(inicio.timestamp()), int(fim.timestamp())


def epoch(dia) -> int:
    #meia noite do dia no fuso de Brasilia, em segundos
    return int(datetime(dia.year, dia.month, dia.day, tzinfo=FUSO).timestamp())


def puuids_de_entradas(entradas) -> list[str]:
    vistos: list[str] = []
    for entrada in entradas or []:
        puuid = (entrada.get("puuid") or "").strip()
        if puuid:
            vistos.append(puuid)
    return vistos


def jogadores_por_divisao(cliente: ClienteRiot, elo: str, divisao: str,
                          pagina: int) -> list[str]:
    url = (f"{PLATAFORMA}/lol/league/v4/entries/RANKED_SOLO_5x5/"
           f"{elo}/{divisao}")
    return puuids_de_entradas(cliente.get(url, {"page": pagina}))


def jogadores_apex(cliente: ClienteRiot, elo: str) -> list[str]:
    nomes = {
        "MASTER": "masterleagues",
        "GRANDMASTER": "grandmasterleagues",
        "CHALLENGER": "challengerleagues",
    }
    url = (f"{PLATAFORMA}/lol/league/v4/{nomes[elo]}/by-queue/"
           "RANKED_SOLO_5x5")
    dados = cliente.get(url) or {}
    return puuids_de_entradas(dados.get("entries"))


def ids_no_intervalo(cliente: ClienteRiot, puuid: str, inicio: int,
                     fim: int) -> list[str]:
    url = f"{REGIAO}/lol/match/v5/matches/by-puuid/{puuid}/ids"
    parametros = {
        "queue": FILA_RANQUEADA,
        "count": IDS_POR_REQUISICAO,
        "startTime": inicio,
        "endTime": fim,
    }
    return cliente.get(url, parametros) or []


def partida(cliente: ClienteRiot, match_id: str):
    #sem timeline: o contrato de dados nao usa nada dela
    url = f"{REGIAO}/lol/match/v5/matches/{match_id}"
    return cliente.get(url)
