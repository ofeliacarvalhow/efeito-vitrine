"""
Teste de historico: descobre se a API de partidas da Riot ainda devolve IDs
para as datas do periodo do projeto.

Nao baixa partida nenhuma. Pede apenas listas de IDs e conta quantos
jogadores responderam e quantos IDs sairam.

Rodar:  .venv/Scripts/python.exe coleta/teste_historico.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

import riot_api
from config import DATA_FINAL, DATA_INICIAL, FILA_RANQUEADA
from riot_api import ClienteRiot, intervalo

JOGADORES_SONDAGEM = 20
JOGADORES_BUSCA = 8
DATAS_ALVO = [date(2026, 9, 4), date(2026, 10, 1), date(2026, 11, 10)]


def jogadores_gold_i(cliente: ClienteRiot, quantos: int) -> list[str]:
    puuids: list[str] = []
    for puuid in riot_api.jogadores_por_divisao(cliente, "GOLD", "I", 1):
        if puuid not in puuids:
            puuids.append(puuid)
    if not puuids:
        raise RuntimeError("a liga GOLD I nao devolveu nenhum puuid.")
    return puuids[:quantos]


def sonda(cliente: ClienteRiot, puuids: list[str], inicio: int,
          fim: int) -> tuple[int, int]:
    com_partidas = 0
    total = 0
    for puuid in puuids:
        ids = riot_api.ids_no_intervalo(cliente, puuid, inicio, fim)
        if ids:
            com_partidas += 1
            total += len(ids)
    return com_partidas, total


def busca_data_mais_antiga(cliente: ClienteRiot, puuids: list[str],
                           sem_historico: date, com_historico: date) -> date:
    """Busca binaria pela semana mais antiga que ainda devolve IDs."""
    baixo = sem_historico
    alto = com_historico
    while (alto - baixo).days > 1:
        meio = baixo + timedelta(days=(alto - baixo).days // 2)
        inicio, fim = intervalo(meio, 7)
        com, total = sonda(cliente, puuids, inicio, fim)
        print(f"  semana de {meio}: {com} de {len(puuids)} jogadores, "
              f"{total} IDs")
        if total > 0:
            alto = meio
        else:
            baixo = meio
    return alto


def main() -> int:
    print(f"periodo do projeto: {DATA_INICIAL} a {DATA_FINAL}")
    print(f"fuso: America/Sao_Paulo, fila {FILA_RANQUEADA}")
    print("")

    cliente = ClienteRiot()
    puuids = jogadores_gold_i(cliente, JOGADORES_SONDAGEM)
    print(f"jogadores GOLD I do BR1: {len(puuids)}")
    print("")

    resultados: dict[date, tuple[int, int]] = {}
    for dia in DATAS_ALVO:
        inicio, fim = intervalo(dia, 1)
        com, total = sonda(cliente, puuids, inicio, fim)
        resultados[dia] = (com, total)
        print(f"{dia}: {com} de {len(puuids)} jogadores com partidas, "
              f"{total} IDs no total")

    print("")
    alvo = DATA_INICIAL
    com_alvo, total_alvo = resultados[alvo]
    if total_alvo > 0:
        print(f"VEREDITO: o historico de {alvo} AINDA EXISTE. "
              f"{com_alvo} jogadores devolveram {total_alvo} IDs naquele dia.")
        print(f"a data inicial do periodo pode ficar em {alvo}.")
        print("")
        print(f"requisicoes usadas: {cliente.requisicoes}")
        return 0

    print(f"VEREDITO: o historico de {alvo} NAO EXISTE mais. "
          "nenhum dos jogadores devolveu partidas naquele dia.")

    ancora = None
    for dia in DATAS_ALVO:
        if resultados[dia][1] > 0:
            ancora = dia
            break
    if ancora is None:
        print("nenhuma das datas alvo devolveu IDs. sondando a ultima semana.")
        recente = date.today() - timedelta(days=7)
        inicio, fim = intervalo(recente, 7)
        com, total = sonda(cliente, puuids, inicio, fim)
        print(f"  semana de {recente}: {com} de {len(puuids)} jogadores, "
              f"{total} IDs")
        if total == 0:
            print("")
            print("nem a ultima semana devolveu IDs. a idade do historico nao "
                  "explica isso: reveja a chave, a fila e os jogadores.")
            print(f"requisicoes usadas: {cliente.requisicoes}")
            return 2
        ancora = recente

    print("")
    print(f"buscando a data mais antiga que ainda funciona, entre {alvo} e "
          f"{ancora}, com {JOGADORES_BUSCA} jogadores por sonda:")
    mais_antiga = busca_data_mais_antiga(
        cliente, puuids[:JOGADORES_BUSCA], alvo, ancora
    )
    print("")
    print(f"VEREDITO: a data mais antiga que ainda devolve partidas e "
          f"{mais_antiga}.")
    print(f"ajuste DATA_INICIAL em coleta/config.py de {DATA_INICIAL} para "
          f"{mais_antiga}, e o periodo no CLAUDE.md.")
    print("")
    print(f"requisicoes usadas: {cliente.requisicoes}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
