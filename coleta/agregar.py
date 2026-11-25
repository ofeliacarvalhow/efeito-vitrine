"""
Agregacao: le data/raw/matches.jsonl em streaming e escreve
data/processed/daily_pickrate.csv no formato do contrato de dados.

Este e um dos dois scripts autorizados a ler data/raw/. Nada do que ele
escreve contem jogador, puuid ou matchId.

Pode rodar com o coletor rodando. Le o arquivo linha por linha, descarta
matchId repetido e a ultima linha caso o coletor a tenha deixado pela metade,
e grava o CSV num arquivo temporario antes de trocar pelo definitivo, para
que a analise nunca leia um CSV incompleto.

Rodar:  .venv/Scripts/python.exe coleta/agregar.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from config import (
    DATA_FINAL,
    DATA_INICIAL,
    FILA_RANQUEADA,
    FUSO,
    PARTIDAS,
    RAIZ,
)
from gerar_mock import CAMPEOES_OBRIGATORIOS

SAIDA = RAIZ / "data" / "processed" / "daily_pickrate.csv"

#limiares do relatorio, os mesmos que a Etapa 6 cobra
MINIMO_PARTIDAS_POR_DIA = 500
MINIMO_ESCOLHAS_POR_DIA = 20


def dia_da_partida(criacao_ms: int) -> date:
    #gameCreation vem em milissegundos desde a epoca
    return datetime.fromtimestamp(criacao_ms / 1000, tz=FUSO).date()


def le_partidas(caminho: Path, contagens: Counter, vistos: set[str]):
    """Gera (dia, campeoes) de cada partida valida, uma linha por vez."""
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            contagens["linhas"] += 1
            try:
                dados = json.loads(linha)
            except json.JSONDecodeError:
                #o coletor pode ter deixado a ultima linha pela metade
                contagens["quebradas"] += 1
                continue
            match_id = dados.get("matchId") or ""
            if not match_id or match_id in vistos:
                contagens["repetidas"] += 1
                continue
            vistos.add(match_id)
            if dados.get("queueId") != FILA_RANQUEADA:
                contagens["fora_da_fila"] += 1
                continue
            dia = dia_da_partida(dados.get("gameCreation") or 0)
            if not DATA_INICIAL <= dia <= DATA_FINAL:
                contagens["fora_do_periodo"] += 1
                continue
            campeoes = [nome for nome in (dados.get("champions") or []) if nome]
            if not campeoes:
                contagens["sem_campeao"] += 1
                continue
            contagens["validas"] += 1
            yield dia, campeoes


def escreve_csv(dias: list[date], campeoes: list[str],
                partidas_por_dia: Counter, escolhas: Counter) -> int:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    parcial = SAIDA.parent / (SAIDA.name + ".parcial")
    linhas = 0
    with open(parcial, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(
            ["date", "champion", "games_total", "picks", "pick_rate"]
        )
        for dia in dias:
            total = partidas_por_dia.get(dia, 0)
            for campeao in campeoes:
                picks = escolhas.get((dia, campeao), 0)
                taxa = round(picks / total, 6) if total else 0.0
                escritor.writerow(
                    [dia.isoformat(), campeao, total, picks, taxa]
                )
                linhas += 1
    #a troca e atomica, entao quem estiver lendo ve a versao velha ou a nova
    os.replace(parcial, SAIDA)
    return linhas


def lista_curta(itens: list[str], quantos: int = 8) -> str:
    if len(itens) <= quantos:
        return ", ".join(itens)
    return ", ".join(itens[:quantos]) + f", e mais {len(itens) - quantos}"


def main() -> int:
    if not PARTIDAS.exists():
        print(f"[erro] {PARTIDAS} nao existe. rode o coletor primeiro.")
        return 1

    contagens: Counter = Counter()
    vistos: set[str] = set()
    partidas_por_dia: Counter = Counter()
    escolhas: Counter = Counter()
    nomes: set[str] = set()

    for dia, campeoes in le_partidas(PARTIDAS, contagens, vistos):
        partidas_por_dia[dia] += 1
        for campeao in campeoes:
            escolhas[(dia, campeao)] += 1
            nomes.add(campeao)

    validas = contagens["validas"]
    if validas == 0:
        print(f"[erro] nenhuma partida valida em {PARTIDAS}.")
        return 1

    dias = [DATA_INICIAL + timedelta(days=n)
            for n in range((DATA_FINAL - DATA_INICIAL).days + 1)]
    campeoes = sorted(nomes)
    linhas = escreve_csv(dias, campeoes, partidas_por_dia, escolhas)

    totais = [partidas_por_dia.get(dia, 0) for dia in dias]
    com_partida = [n for n in totais if n > 0]
    magros = [dia.isoformat() for dia, n in zip(dias, totais)
              if n < MINIMO_PARTIDAS_POR_DIA]
    pouco_escolhidos = sorted(
        campeao for campeao in campeoes
        if sum(escolhas.get((dia, campeao), 0) for dia in dias) / len(dias)
        < MINIMO_ESCOLHAS_POR_DIA
    )

    print(f"{SAIDA.relative_to(RAIZ)}: {linhas} linhas, "
          f"{len(dias)} dias x {len(campeoes)} campeoes")
    print("")
    print(f"total de partidas: {validas}")
    print(f"linhas lidas: {contagens['linhas']} | "
          f"repetidas {contagens['repetidas']} | "
          f"fora da fila {contagens['fora_da_fila']} | "
          f"fora do periodo {contagens['fora_do_periodo']} | "
          f"sem campeao {contagens['sem_campeao']} | "
          f"quebradas {contagens['quebradas']}")
    print(f"periodo: {DATA_INICIAL} a {DATA_FINAL}, {len(dias)} dias, "
          f"{len(com_partida)} com partida e "
          f"{len(dias) - len(com_partida)} sem nenhuma")
    print(f"partidas por dia: minimo {min(totais)}, "
          f"media {validas / len(dias):.1f}, maximo {max(totais)}")
    print(f"dias com menos de {MINIMO_PARTIDAS_POR_DIA} partidas: "
          f"{len(magros)} de {len(dias)}")
    if magros:
        print(f"  {lista_curta(magros)}")
    print(f"campeoes com menos de {MINIMO_ESCOLHAS_POR_DIA} escolhas por dia "
          f"em media: {len(pouco_escolhidos)} de {len(campeoes)}")
    if pouco_escolhidos:
        print(f"  {lista_curta(pouco_escolhidos)}")

    faltando = [campeao for campeao in CAMPEOES_OBRIGATORIOS
                if campeao not in nomes]
    if faltando:
        print(f"campeoes da analise que ainda nao apareceram: "
              f"{lista_curta(faltando)}")
    else:
        print("os 18 campeoes da analise todos apareceram.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
