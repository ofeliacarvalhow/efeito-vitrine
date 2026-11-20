"""
Relatorio de qualidade da coleta.

Este e o outro script autorizado a ler data/raw/. Escreve
data/processed/qualidade.txt e atualiza o dicionario de dados no README.md,
entre marcadores, para os numeros do README nunca ficarem velhos.

Nada do que ele escreve contem jogador, puuid ou matchId.

Pode rodar com o coletor rodando.

Rodar:  .venv/Scripts/python.exe coleta/qualidade.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from coletar import janelas_semanais
from config import (
    DATA_FINAL,
    DATA_INICIAL,
    FILA_RANQUEADA,
    FUSO,
    PARTIDAS,
    RAIZ,
)

SAIDA = RAIZ / "data" / "processed" / "qualidade.txt"
PICKRATE = RAIZ / "data" / "processed" / "daily_pickrate.csv"
NOVAS_SKINS = RAIZ / "data" / "processed" / "new_skins.csv"
LEIAME = RAIZ / "README.md"

MINIMO_PARTIDAS_POR_DIA = 500
MARCADOR_INICIO = "<!-- inicio do dicionario de dados -->"
MARCADOR_FIM = "<!-- fim do dicionario de dados -->"


def patch_da_versao(versao: str) -> str:
    #gameVersion vem como 16.23.1234.5678, e o patch sao os dois primeiros
    partes = (versao or "").split(".")
    if len(partes) < 2:
        return versao or "sem versao"
    return f"{partes[0]}.{partes[1]}"


def semana_do_dia(janelas: list[tuple[date, date]], dia: date) -> int:
    for indice, (inicio, fim) in enumerate(janelas, start=1):
        if inicio <= dia < fim:
            return indice
    return 0


def le_bruto(janelas: list[tuple[date, date]]) -> dict:
    contagens: Counter = Counter()
    vistos: set[str] = set()
    por_dia: Counter = Counter()
    versoes_por_semana: dict[int, Counter] = {
        indice: Counter() for indice in range(1, len(janelas) + 1)
    }
    with open(PARTIDAS, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha:
                continue
            contagens["linhas"] += 1
            try:
                dados = json.loads(linha)
            except json.JSONDecodeError:
                contagens["quebradas"] += 1
                continue
            match_id = dados.get("matchId") or ""
            if not match_id:
                contagens["sem_id"] += 1
                continue
            if match_id in vistos:
                contagens["repetidas"] += 1
                continue
            vistos.add(match_id)
            if dados.get("queueId") != FILA_RANQUEADA:
                contagens["fora_da_fila"] += 1
                continue
            criacao = dados.get("gameCreation") or 0
            dia = datetime.fromtimestamp(criacao / 1000, tz=FUSO).date()
            if not DATA_INICIAL <= dia <= DATA_FINAL:
                contagens["fora_do_periodo"] += 1
                continue
            contagens["validas"] += 1
            por_dia[dia] += 1
            semana = semana_do_dia(janelas, dia)
            if semana:
                versoes_por_semana[semana][
                    patch_da_versao(dados.get("gameVersion"))
                ] += 1
    return {
        "contagens": contagens,
        "por_dia": por_dia,
        "versoes_por_semana": versoes_por_semana,
    }


def le_pickrate() -> dict:
    if not PICKRATE.exists():
        return {}
    dias: set[str] = set()
    campeoes: set[str] = set()
    linhas = 0
    with open(PICKRATE, encoding="utf-8") as arquivo:
        for registro in csv.DictReader(arquivo):
            linhas += 1
            dias.add(registro["date"])
            campeoes.add(registro["champion"])
    return {"linhas": linhas, "dias": len(dias), "campeoes": len(campeoes)}


def conta_linhas_csv(caminho: Path) -> int:
    if not caminho.exists():
        return 0
    with open(caminho, encoding="utf-8") as arquivo:
        return max(0, sum(1 for _ in arquivo) - 1)


def monta_relatorio(bruto: dict, janelas: list[tuple[date, date]],
                    pickrate: dict) -> str:
    contagens = bruto["contagens"]
    por_dia = bruto["por_dia"]
    dias = [DATA_INICIAL + timedelta(days=n)
            for n in range((DATA_FINAL - DATA_INICIAL).days + 1)]
    totais = [por_dia.get(dia, 0) for dia in dias]
    com_partida = [dia for dia, n in zip(dias, totais) if n > 0]
    faltando = [dia for dia, n in zip(dias, totais) if n == 0]
    magros = [dia for dia, n in zip(dias, totais)
              if 0 < n < MINIMO_PARTIDAS_POR_DIA]
    validas = contagens["validas"]

    partes: list[str] = []
    agora = datetime.now(FUSO).strftime("%Y-%m-%d %H:%M")
    partes.append("RELATORIO DE QUALIDADE DA COLETA")
    partes.append(f"gerado em {agora} (America/Sao_Paulo)")
    partes.append("")
    partes.append("PARTIDAS")
    partes.append(f"  partidas unicas na fila {FILA_RANQUEADA}: {validas}")
    partes.append(f"  linhas lidas no bruto:    {contagens['linhas']}")
    partes.append(f"  duplicadas descartadas:   {contagens['repetidas']}")
    partes.append(f"  fora da fila {FILA_RANQUEADA}:          "
                  f"{contagens['fora_da_fila']}")
    partes.append(f"  fora do periodo:          "
                  f"{contagens['fora_do_periodo']}")
    partes.append(f"  linhas sem matchId:       {contagens['sem_id']}")
    partes.append(f"  linhas quebradas:         {contagens['quebradas']}")
    partes.append("")
    partes.append("PERIODO")
    partes.append(f"  periodo do projeto: {DATA_INICIAL} a {DATA_FINAL}, "
                  f"{len(dias)} dias")
    if com_partida:
        partes.append(f"  periodo coberto:    {min(com_partida)} a "
                      f"{max(com_partida)}")
    partes.append(f"  dias com partida:   {len(com_partida)} de {len(dias)}")
    partes.append(f"  dias faltando:      {len(faltando)}")
    if faltando:
        for dia in faltando:
            partes.append(f"    {dia}")
    partes.append("")
    partes.append("PARTIDAS POR DIA")
    if validas:
        partes.append(f"  minimo {min(totais)}, media "
                      f"{validas / len(dias):.1f}, maximo {max(totais)}")
    partes.append(f"  dias abaixo de {MINIMO_PARTIDAS_POR_DIA} partidas: "
                  f"{len(magros)}")
    partes.append("")
    for dia, n in zip(dias, totais):
        aviso = "  <- abaixo do minimo" if n < MINIMO_PARTIDAS_POR_DIA else ""
        partes.append(f"  {dia}  {n:6d}{aviso}")
    partes.append("")
    partes.append("VERSOES DO JOGO POR SEMANA")
    for indice, (inicio, fim) in enumerate(janelas, start=1):
        contagem = bruto["versoes_por_semana"][indice]
        ultimo = fim - timedelta(days=1)
        if not contagem:
            partes.append(f"  semana {indice:2d} ({inicio} a {ultimo}): "
                          "sem partida")
            continue
        detalhe = ", ".join(
            f"{patch} ({quantas})"
            for patch, quantas in sorted(contagem.most_common())
        )
        partes.append(f"  semana {indice:2d} ({inicio} a {ultimo}): "
                      f"{detalhe}")
    partes.append("")
    partes.append("ARQUIVOS ENTREGUES")
    if pickrate:
        partes.append(f"  daily_pickrate.csv: {pickrate['linhas']} linhas, "
                      f"{pickrate['dias']} dias x {pickrate['campeoes']} "
                      "campeoes")
    else:
        partes.append("  daily_pickrate.csv: ainda nao gerado, "
                      "rode o agregar.py")
    partes.append(f"  new_skins.csv:      {conta_linhas_csv(NOVAS_SKINS)} "
                  "linhas")
    partes.append("")
    return "\n".join(partes) + "\n"


def monta_dicionario(bruto: dict, pickrate: dict) -> str:
    contagens = bruto["contagens"]
    por_dia = bruto["por_dia"]
    dias = (DATA_FINAL - DATA_INICIAL).days + 1
    com_partida = sum(1 for n in por_dia.values() if n > 0)
    validas = contagens["validas"]
    agora = datetime.now(FUSO).strftime("%Y-%m-%d %H:%M")
    linhas = pickrate.get("linhas", 0)
    campeoes = pickrate.get("campeoes", 0)

    return "\n".join([
        MARCADOR_INICIO,
        "",
        "## Dicionario de dados",
        "",
        f"Numeros de {agora}, fuso America/Sao_Paulo. O "
        "`coleta/qualidade.py` reescreve esta secao, entao ela nunca fica "
        "velha. O relatorio completo, com partidas dia por dia e versoes do "
        "jogo por semana, fica em `data/processed/qualidade.txt`.",
        "",
        "### `daily_pickrate.csv`",
        "",
        "| coluna | tipo | descricao |",
        "|---|---|---|",
        "| `date` | texto `AAAA-MM-DD` | dia no fuso America/Sao_Paulo |",
        "| `champion` | texto | `championName` da Riot, como `KSante` |",
        "| `games_total` | inteiro | partidas daquele dia na amostra |",
        "| `picks` | inteiro | vezes que o campeao foi escolhido no dia |",
        "| `pick_rate` | decimal | `picks / games_total`, 6 casas |",
        "",
        f"Estado atual: **{linhas} linhas**, {dias} dias x {campeoes} "
        f"campeoes, a partir de **{validas} partidas** da fila "
        f"{FILA_RANQUEADA}. {com_partida} dos {dias} dias do periodo tem "
        "partida.",
        "",
        "Ha uma linha para cada campeao em cada dia do periodo, inclusive "
        "dias com zero escolhas. Em dia sem partida nenhuma, `games_total` e "
        "`pick_rate` ficam em zero. A lista de campeoes sai dos proprios "
        "dados, entao cresce conforme campeoes novos aparecem na coleta.",
        "",
        "### `new_skins.csv`",
        "",
        "| coluna | tipo | descricao |",
        "|---|---|---|",
        "| `version` | texto | patch que trouxe a skin, como `16.18` |",
        "| `champion` | texto | mesmo nome usado em `daily_pickrate.csv` |",
        "| `skin_num` | inteiro | numero da skin no Data Dragon, nunca 0 |",
        "| `skin_name` | texto | nome em pt_BR |",
        "",
        f"Estado atual: **{conta_linhas_csv(NOVAS_SKINS)} linhas**. O Data "
        "Dragon sai dias depois do patch, entao `version` diz qual patch "
        "trouxe a skin, nao quando ela saiu. A data oficial do patch entra "
        "em `balance_changes.csv`, preenchida pela Pessoa 3.",
        "",
        "### Como a amostra foi montada",
        "",
        "As partidas vem de jogadores sorteados de IRON a CHALLENGER no BR1, "
        "e o periodo e varrido em semanas de segunda a domingo, em rodizio, "
        "para a amostra ficar parelha em todos os dias a qualquer momento em "
        "que a coleta pare. Isso significa que `games_total` nao e o total "
        "de partidas jogadas no servidor naquele dia: e o total que esta na "
        "amostra. A taxa de escolha e o que vale comparar entre dias, e nao "
        "a contagem bruta.",
        "",
        MARCADOR_FIM,
    ])


def atualiza_leiame(dicionario: str) -> str:
    texto = LEIAME.read_text(encoding="utf-8")
    if MARCADOR_INICIO in texto and MARCADOR_FIM in texto:
        antes = texto.split(MARCADOR_INICIO)[0]
        depois = texto.split(MARCADOR_FIM)[1]
        novo = antes + dicionario + depois
        acao = "secao atualizada"
    else:
        novo = texto.rstrip("\n") + "\n\n" + dicionario + "\n"
        acao = "secao criada"
    parcial = LEIAME.parent / (LEIAME.name + ".parcial")
    parcial.write_text(novo, encoding="utf-8")
    os.replace(parcial, LEIAME)
    return acao


def main() -> int:
    if not PARTIDAS.exists():
        print(f"[erro] {PARTIDAS} nao existe. rode o coletor primeiro.")
        return 1

    janelas = janelas_semanais(DATA_INICIAL, DATA_FINAL)
    bruto = le_bruto(janelas)
    pickrate = le_pickrate()
    relatorio = monta_relatorio(bruto, janelas, pickrate)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    parcial = SAIDA.parent / (SAIDA.name + ".parcial")
    parcial.write_text(relatorio, encoding="utf-8")
    os.replace(parcial, SAIDA)

    acao = atualiza_leiame(monta_dicionario(bruto, pickrate))

    contagens = bruto["contagens"]
    print(f"{SAIDA.relative_to(RAIZ)}: "
          f"{len(relatorio.splitlines())} linhas")
    print(f"{LEIAME.relative_to(RAIZ)}: dicionario de dados, {acao}")
    print("")
    print(f"partidas unicas: {contagens['validas']} | "
          f"duplicadas {contagens['repetidas']} | "
          f"fora da fila {contagens['fora_da_fila']} | "
          f"quebradas {contagens['quebradas']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
