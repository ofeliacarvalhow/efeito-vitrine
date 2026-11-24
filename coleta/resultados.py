"""
A tabela de resultado por campeao e por evento, uma vez so.

O CSV da entrega e o JSON do painel precisam da mesma tabela, e antes isso
estava escrito duas vezes. Dois lugares com a mesma conta divergem no dia em
que alguem mexe em um e esquece o outro, entao a conta mora aqui e os dois
geradores importam daqui.

As funcoes de medida continuam em analise/efeito_vitrine.py. Este modulo nao
calcula nada por conta propria: ele so percorre os eventos, chama `mede` e
`controle` de la, e devolve uma linha por par de campeao e evento.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "analise") not in sys.path:
    sys.path.insert(0, str(RAIZ / "analise"))

from efeito_vitrine import (  # noqa: E402
    BALANCEAMENTO, EVENTOS, JANELA_ANTES, JANELA_DEPOIS, PERCENTIL_DE_CORTE,
    PICKS_MINIMOS, REAL, RECUO_PADRAO, controle, le_balanceamento,
    le_eventos, le_pickrate, mede, percentil, prepara_tabela,
)

COLUNAS = [
    "event_id", "event_type", "event_date", "champion",
    "taxa_antes", "taxa_depois", "lift", "percentil_do_lift",
    "lift_do_pico", "percentil_do_pico",
    "picks_antes", "picks_depois", "jogos_antes", "jogos_depois",
    "ic_antes_de", "ic_antes_ate", "ic_depois_de", "ic_depois_ate",
    "intervalos_se_cruzam", "pouca_amostra", "destaque",
    "campeoes_no_controle", "lift_mediano_do_controle",
]

#quantas casas cada coluna leva no CSV, para o arquivo sair igual ao de antes
CASAS = {
    "taxa_antes": 6, "taxa_depois": 6, "lift": 4, "percentil_do_lift": 1,
    "lift_do_pico": 4, "percentil_do_pico": 1,
    "ic_antes_de": 6, "ic_antes_ate": 6, "ic_depois_de": 6,
    "ic_depois_ate": 6, "lift_mediano_do_controle": 4,
}


def carrega():
    """Le os CSV de data/processed e devolve o que o resto precisa."""
    picks, partidas, dias, campeoes = le_pickrate(REAL)
    return {
        "tabela": prepara_tabela(picks, partidas, dias, campeoes),
        "campeoes": campeoes,
        "eventos": le_eventos(EVENTOS),
        "balanceamento": le_balanceamento(BALANCEAMENTO),
    }


def agrupa_eventos(eventos: list[dict]) -> dict[str, dict]:
    """Um registro por event_id, com os campeoes dele dentro."""
    grupos: dict[str, dict] = {}
    for linha in eventos:
        grupo = grupos.setdefault(linha["event_id"], {
            "tipo": linha["event_type"],
            "data": date.fromisoformat(linha["event_date"]),
            "titulo": linha.get("title", ""),
            "campeoes": [],
        })
        if linha["champion"] not in grupo["campeoes"]:
            grupo["campeoes"].append(linha["champion"])
    return grupos


def monta_linhas(dados: dict | None = None) -> tuple[list[dict], dict]:
    """Uma linha por par de campeao e evento, com numero de verdade.

    Devolve as linhas e um resumo com o que nao deu para medir. Os valores
    saem como int e float, nao como texto: quem escreve CSV formata depois,
    e quem escreve JSON usa direto.
    """
    if dados is None:
        dados = carrega()
    tabela = dados["tabela"]
    campeoes = dados["campeoes"]
    balanceamento = dados["balanceamento"]

    com_evento: dict[str, list[date]] = defaultdict(list)
    for linha in dados["eventos"]:
        com_evento[linha["champion"]].append(
            date.fromisoformat(linha["event_date"])
        )

    grupos = agrupa_eventos(dados["eventos"])
    linhas: list[dict] = []
    controles: dict[str, dict] = {}
    sem_medida = 0
    for event_id in sorted(grupos, key=lambda i: (grupos[i]["data"], i)):
        grupo = grupos[event_id]
        #o controle depende so da data, entao sai uma vez por evento e nao
        #uma vez por campeao
        referencia = controle(tabela, campeoes, grupo["data"], JANELA_ANTES,
                              JANELA_DEPOIS, com_evento, balanceamento,
                              RECUO_PADRAO)
        if not referencia["lift"]:
            sem_medida += len(grupo["campeoes"])
            continue
        mediana = referencia["lift"][len(referencia["lift"]) // 2]
        #a tela do histograma mostra onde o campeao caiu dentro do controle,
        #entao a distribuicao inteira precisa sair daqui em vez de ser
        #refeita no navegador
        controles[event_id] = {
            "pico": referencia["pico"],
            "lift": referencia["lift"],
            "fora_por_mexida": referencia["fora_por_mexida"],
        }
        for campeao in sorted(grupo["campeoes"]):
            medida = mede(tabela, campeao, grupo["data"], JANELA_ANTES,
                          JANELA_DEPOIS, RECUO_PADRAO)
            if not medida:
                sem_medida += 1
                continue
            perc = percentil(medida["lift"], referencia["lift"])
            perc_pico = percentil(medida["lift_do_pico"], referencia["pico"])
            antes_de, antes_ate = medida["ic_antes"]
            depois_de, depois_ate = medida["ic_depois"]
            cruzam = not (depois_de > antes_ate or antes_de > depois_ate)
            #o mesmo critério do relatorio: percentil do PICO, sem filtrar
            #por escolhas minimas. a coluna pouca_amostra fica do lado para
            #quem quiser filtrar depois, e a contagem daqui precisa bater
            #com a do relatorio.
            destaque = (perc_pico is not None
                        and perc_pico >= PERCENTIL_DE_CORTE)
            linhas.append({
                "event_id": event_id,
                "event_type": grupo["tipo"],
                "event_date": grupo["data"].isoformat(),
                "champion": campeao,
                "taxa_antes": medida["taxa_antes"],
                "taxa_depois": medida["taxa_depois"],
                "lift": medida["lift"],
                "percentil_do_lift": perc,
                "lift_do_pico": medida["lift_do_pico"],
                "percentil_do_pico": perc_pico,
                "picks_antes": medida["picks_antes"],
                "picks_depois": medida["picks_depois"],
                "jogos_antes": medida["jogos_antes"],
                "jogos_depois": medida["jogos_depois"],
                "ic_antes_de": antes_de,
                "ic_antes_ate": antes_ate,
                "ic_depois_de": depois_de,
                "ic_depois_ate": depois_ate,
                "intervalos_se_cruzam": int(cruzam),
                "pouca_amostra": int(medida["picks_antes"] < PICKS_MINIMOS),
                "destaque": int(destaque),
                "campeoes_no_controle": len(referencia["lift"]),
                "lift_mediano_do_controle": mediana,
            })

    resumo = {
        "eventos": len(grupos),
        "pares": len(linhas),
        "sem_medida": sem_medida,
        "destaques": sum(l["destaque"] for l in linhas),
        "cruzam": sum(l["intervalos_se_cruzam"] for l in linhas),
        "poucas": sum(l["pouca_amostra"] for l in linhas),
        "picks_minimos": PICKS_MINIMOS,
        "percentil_de_corte": PERCENTIL_DE_CORTE,
        "antes": JANELA_ANTES,
        "depois": JANELA_DEPOIS,
        "recuo": RECUO_PADRAO,
        "controles": controles,
    }
    return linhas, resumo


def para_csv(linha: dict) -> dict:
    """A mesma linha com os numeros virados texto, nas casas do CSV."""
    saida = {}
    for coluna in COLUNAS:
        valor = linha[coluna]
        casas = CASAS.get(coluna)
        if casas is None or valor is None:
            saida[coluna] = "" if valor is None else valor
        else:
            saida[coluna] = f"{valor:.{casas}f}"
    return saida
