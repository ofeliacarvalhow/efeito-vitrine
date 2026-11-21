"""
Reatribui a semana de cada ID depois de o periodo mudar.

Quando DATA_INICIAL muda, os indices de semana mudam de significado: a
semana 1 deixa de ser uma data e passa a ser outra. Os IDs ja baixados
ficam apontando para a semana errada, o que nao estraga o dado, porque a
data de verdade vem do gameCreation no matches.jsonl, mas estraga o
controle da coleta: o rodizio passa a achar que semanas vazias estao cheias.

Este script conserta, lendo a data real de cada partida baixada e
reescrevendo a coluna semana. Os IDs pendentes, cuja data ninguem sabe sem
baixar, sao apagados para serem redescobertos, e a tabela de sementes
usadas e limpa pelo mesmo motivo.

E manutencao do coletor, nao analise. Rodar com o coletor parado.

Rodar:  .venv\\Scripts\\python.exe coleta\\reatribuir_semanas.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime

from coletar import abre_banco, janelas_semanais, registra_semanas
from config import ARQUIVO_TRAVA, DATA_FINAL, DATA_INICIAL, FUSO, PARTIDAS


def main() -> int:
    if not PARTIDAS.exists():
        print(f"[erro] {PARTIDAS} nao existe.")
        return 1

    janelas = janelas_semanais(DATA_INICIAL, DATA_FINAL)
    print(f"periodo {DATA_INICIAL} a {DATA_FINAL}, {len(janelas)} semanas")

    con = abre_banco()
    registra_semanas(con, janelas)

    #de cada dia para o indice da semana que o contem
    de_dia_para_semana = {}
    for indice, (inicio, fim) in enumerate(janelas, start=1):
        dia = inicio
        while dia < fim:
            de_dia_para_semana[dia] = indice
            dia = dia.fromordinal(dia.toordinal() + 1)

    novos: list[tuple[int, str]] = []
    fora = 0
    lidas = 0
    with open(PARTIDAS, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            try:
                dados = json.loads(linha)
            except json.JSONDecodeError:
                continue
            lidas += 1
            match_id = dados.get("matchId") or ""
            criacao = dados.get("gameCreation") or 0
            if not match_id or not criacao:
                continue
            dia = datetime.fromtimestamp(criacao / 1000, tz=FUSO).date()
            semana = de_dia_para_semana.get(dia)
            if semana is None:
                fora += 1
                continue
            novos.append((semana, match_id))

    print(f"linhas lidas do bruto: {lidas}")
    print(f"IDs com semana recalculada: {len(novos)}")
    print(f"IDs fora do periodo novo: {fora}")

    antes = con.execute(
        "SELECT COUNT(*) FROM ids WHERE situacao = 'pendente'"
    ).fetchone()[0]
    sementes = con.execute("SELECT COUNT(*) FROM sementes_usadas").fetchone()[0]

    con.executemany("UPDATE ids SET semana = ? WHERE match_id = ?", novos)
    con.execute("DELETE FROM ids WHERE situacao = 'pendente'")
    con.execute("DELETE FROM sementes_usadas")
    con.commit()

    print("")
    print(f"pendentes apagados: {antes}, para serem redescobertos")
    print(f"consultas de semente esquecidas: {sementes}")
    print("")
    distribuicao = con.execute(
        "SELECT semana, COUNT(*) FROM ids WHERE situacao = 'baixado' "
        "GROUP BY semana ORDER BY semana"
    ).fetchall()
    print(f"semanas com partida agora: {len(distribuicao)} de {len(janelas)}")
    for semana, quantas in distribuicao:
        inicio = janelas[semana - 1][0]
        print(f"  semana {semana:2d} ({inicio}): {quantas}")
    con.close()
    return 0


if __name__ == "__main__":
    if ARQUIVO_TRAVA.exists():
        print("lembre de parar o coletor antes. a trava em "
              f"{ARQUIVO_TRAVA.name} nao impede este script.")
    sys.exit(main())
