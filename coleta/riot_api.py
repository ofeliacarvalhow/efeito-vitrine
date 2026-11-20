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

    def respeita_cabecalhos(self, resposta: requests.Response) -> None:
        #se a Riot diz que a janela encheu, espera a janela inteira
        pares = (
            (resposta.headers.get("X-App-Rate-Limit", ""),
             resposta.headers.get("X-App-Rate-Limit-Count", "")),
            (resposta.headers.get("X-Method-Rate-Limit", ""),
             resposta.headers.get("X-Method-Rate-Limit-Count", "")),
        )
        for texto_limite, texto_contagem in pares:
            limites = mapa_limite(texto_limite)
            contagens = mapa_limite(texto_contagem)
            for segundos, maximo in limites.items():
                if contagens.get(segundos, 0) >= maximo:
                    self.aviso(f"[limite] {texto_contagem} de {texto_limite}, "
                               f"esperando {segundos}s")
                    time.sleep(segundos + 1)
                    return

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
        """Devolve o JSON, ou None em 404. Levanta erro se nao der jeito."""
        falhas = 0
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
                falhas += 1
                if falhas > 3:
                    raise RuntimeError(f"rede falhou 3 vezes em {url}: {erro}")
                espera = 2 ** falhas
                self.aviso(f"[rede] {erro.__class__.__name__}, tentativa "
                           f"{falhas}, esperando {espera}s")
                time.sleep(espera)
                continue

            self.respeita_cabecalhos(resposta)
            codigo = resposta.status_code

            if codigo == 200:
                return resposta.json()
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
                falhas += 1
                if falhas > 3:
                    raise RuntimeError(f"HTTP {codigo} 3 vezes em {url}")
                espera = 2 ** falhas
                self.aviso(f"[{codigo}] erro da Riot, tentativa {falhas}, "
                           f"esperando {espera}s")
                time.sleep(espera)
                continue
            raise RuntimeError(f"HTTP {codigo} em {url}: {resposta.text[:300]}")


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
