"""
Exporta os dados do projeto em JSON, para o painel consumir sem backend.

O painel vai ser hospedado no Vercel, que serve arquivo estatico e nao roda
Python. Entao ele nao pode ler os CSV com pandas: precisa de JSON pronto,
servido junto com a pagina.

Os arquivos saem em site/dados/. O formato e compacto de proposito: a serie
diaria vem como listas paralelas e nao como um objeto por linha, o que
derruba o tamanho de alguns megabytes para algumas centenas de kilobytes,
sem perder nada.

Rodar:  .venv\\Scripts\\python.exe coleta\\exportar_json.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from config import DATA_FINAL, DATA_INICIAL, FUSO, RAIZ

PROCESSADOS = RAIZ / "data" / "processed"
SAIDA = RAIZ / "site" / "dados"


def ler(nome: str) -> list[dict]:
    caminho = PROCESSADOS / nome
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def grava(nome: str, conteudo) -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    alvo = SAIDA / nome
    parcial = SAIDA / (nome + ".parcial")
    #separador sem espaco para o arquivo nao inchar a toa
    parcial.write_text(
        json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(parcial, alvo)
    return alvo.stat().st_size


def monta_serie() -> dict:
    """Serie diaria em listas paralelas, que e o formato mais enxuto.

    Em vez de 46 mil objetos com quatro campos cada, sai uma lista de dias,
    uma de campeoes, uma de partidas por dia e um mapa de campeao para a
    lista de escolhas dele, na mesma ordem dos dias. O painel cruza por
    indice.
    """
    linhas = ler("daily_pickrate.csv")
    if not linhas:
        return {}
    dias = sorted({l["date"] for l in linhas})
    campeoes = sorted({l["champion"] for l in linhas})
    indice_dia = {d: i for i, d in enumerate(dias)}

    partidas = [0] * len(dias)
    escolhas = {c: [0] * len(dias) for c in campeoes}
    for l in linhas:
        i = indice_dia[l["date"]]
        partidas[i] = int(l["games_total"])
        escolhas[l["champion"]][i] = int(l["picks"])

    return {
        "dias": dias,
        "campeoes": campeoes,
        "partidas_por_dia": partidas,
        "escolhas": escolhas,
        "como_ler": (
            "escolhas[campeao][i] e quantas vezes o campeao foi escolhido "
            "no dia dias[i]. a taxa e escolhas[campeao][i] dividido por "
            "partidas_por_dia[i]. partidas_por_dia e o total da AMOSTRA "
            "daquele dia, nao o total jogado no servidor."
        ),
    }


def monta_eventos() -> list[dict]:
    """Um objeto por evento, com a lista de campeoes dentro."""
    por_id: dict[str, dict] = {}
    for l in ler("events.csv"):
        evento = por_id.setdefault(l["event_id"], {
            "id": l["event_id"],
            "tipo": l["event_type"],
            "data": l["event_date"],
            "titulo": l["title"],
            "youtube_id": l["youtube_id"],
            "views": int(l["views"]) if l["views"] else None,
            "campeoes": [],
        })
        evento["campeoes"].append(l["champion"])
    for evento in por_id.values():
        evento["campeoes"].sort()
    return sorted(por_id.values(), key=lambda e: (e["data"], e["id"]))


def monta_balanceamento() -> list[dict]:
    return [
        {"patch": l["patch"], "data": l["patch_date"],
         "campeao": l["champion"], "mudanca": l["change"]}
        for l in ler("balance_changes.csv")
    ]


def monta_patches() -> list[dict]:
    return [
        {"patch": l["patch"], "data": l["patch_date"],
         "exata": l["exata"] == "1", "partidas": int(l["partidas"])}
        for l in ler("patch_dates.csv")
    ]


def monta_resumo(serie: dict, eventos: list[dict]) -> dict:
    partidas = sum(serie.get("partidas_por_dia") or [0])
    dias = len(serie.get("dias") or [])
    tipos: dict[str, int] = {}
    for evento in eventos:
        tipos[evento["tipo"]] = tipos.get(evento["tipo"], 0) + 1
    return {
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "periodo": {"de": DATA_INICIAL.isoformat(),
                    "ate": DATA_FINAL.isoformat(), "dias": dias},
        "partidas": partidas,
        "partidas_por_dia": round(partidas / dias) if dias else 0,
        "campeoes": len(serie.get("campeoes") or []),
        "eventos": {"total": len(eventos), "por_tipo": tipos},
        "aviso": (
            "a amostra da peso igual aos dez elos, de Ferro a Challenger, "
            "enquanto a populacao real e quase toda de elo baixo. a taxa "
            "daqui nao e a taxa do servidor. o que vale comparar entre "
            "dias e a taxa, nunca a contagem de partidas."
        ),
    }


def main() -> int:
    serie = monta_serie()
    if not serie:
        print("[erro] daily_pickrate.csv nao existe. rode o agregar.py.")
        return 1
    eventos = monta_eventos()

    arquivos = [
        ("serie.json", serie),
        ("eventos.json", eventos),
        ("patches.json", monta_patches()),
        ("balanceamento.json", monta_balanceamento()),
        ("resumo.json", monta_resumo(serie, eventos)),
    ]
    total = 0
    print(f"{SAIDA.relative_to(RAIZ)}:")
    for nome, conteudo in arquivos:
        tamanho = grava(nome, conteudo)
        total += tamanho
        print(f"  {nome:22s} {tamanho / 1024:8.1f} KB")
    print(f"  {'TOTAL':22s} {total / 1024:8.1f} KB")
    print("")
    print(f"periodo {DATA_INICIAL} a {DATA_FINAL}, "
          f"{len(serie['dias'])} dias, {len(serie['campeoes'])} campeoes")
    print(f"{len(eventos)} eventos")
    print("")
    print("o painel le esses arquivos com fetch, sem backend nenhum. "
          "rode de novo sempre que a coleta avancar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
