r"""
Exporta em JSON o que a analise concluiu, para o painel nao recalcular nada.

O exportar_json.py entrega os dados crus da coleta: serie, eventos, patches,
balanceamento e resumo. Faltavam os tres arquivos de resultado, e sem eles
cada tela do painel teria que refazer janela, percentil e placebo no
navegador, com risco de mostrar numero diferente do que o relatorio afirma.

Saem tres arquivos:

  resultados.json  uma linha por par de campeao e evento, com lift, pico,
                   percentil contra o controle e intervalo de confianca
  tipos.json       o teste agrupado por tipo de evento, que e o numero que
                   o trabalho conclui, com intervalo e chance
  placebo.json     as 200 contagens com data sorteada e a contagem real,
                   que e o histograma da tela do placebo
  controle.json    a distribuicao do grupo de controle em cada data de
                   evento, que e o fundo cinza do histograma de cada campeao

A tabela de resultado vem de coleta/resultados.py e o placebo vem de
analise/efeito_vitrine.py, entao nenhum numero daqui e conta nova.

Rodar:  .venv\Scripts\python.exe coleta\exportar_json_resultados.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coleta"))
sys.path.insert(0, str(RAIZ / "analise"))

from config import FUSO  # noqa: E402
from efeito_vitrine import (  # noqa: E402
    REPETICOES_PLACEBO, SEMENTE_PLACEBO, destaques_distintos, placebo,
    prob_de_cauda, wilson,
)
from resultados import carrega, monta_linhas  # noqa: E402

SAIDA = RAIZ / "painel" / "dados"

#o campo do CSV a esquerda, o nome no JSON a direita. o painel le em
#portugues igual aos outros arquivos, e nao em ingles do contrato de dados
NOMES = {
    "event_id": "evento", "event_type": "tipo", "event_date": "data",
    "champion": "campeao",
}


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


def quando_agregou() -> str:
    """Quando o daily_pickrate.csv foi escrito pela ultima vez.

    Igual ao do exportar_json.py, e pelo mesmo motivo: o painel mostra a
    data do DADO em toda tela, nao a hora em que o JSON saiu.
    """
    caminho = RAIZ / "data" / "processed" / "daily_pickrate.csv"
    if not caminho.exists():
        return ""
    quando = datetime.fromtimestamp(caminho.stat().st_mtime, tz=FUSO)
    return quando.isoformat(timespec="seconds")


def arredonda(valor, casas: int):
    return None if valor is None else round(valor, casas)


def monta_resultados(linhas: list[dict], resumo: dict, agora: str) -> dict:
    pares = []
    for l in linhas:
        par = {NOMES[c]: l[c] for c in NOMES}
        par.update({
            "taxa_antes": arredonda(l["taxa_antes"], 6),
            "taxa_depois": arredonda(l["taxa_depois"], 6),
            "lift": arredonda(l["lift"], 4),
            "percentil": arredonda(l["percentil_do_lift"], 1),
            "lift_do_pico": arredonda(l["lift_do_pico"], 4),
            "percentil_do_pico": arredonda(l["percentil_do_pico"], 1),
            "picks_antes": l["picks_antes"],
            "picks_depois": l["picks_depois"],
            "jogos_antes": l["jogos_antes"],
            "jogos_depois": l["jogos_depois"],
            "ic_antes": [arredonda(l["ic_antes_de"], 6),
                         arredonda(l["ic_antes_ate"], 6)],
            "ic_depois": [arredonda(l["ic_depois_de"], 6),
                          arredonda(l["ic_depois_ate"], 6)],
            "intervalos_se_cruzam": bool(l["intervalos_se_cruzam"]),
            "pouca_amostra": bool(l["pouca_amostra"]),
            "destaque": bool(l["destaque"]),
            "campeoes_no_controle": l["campeoes_no_controle"],
            "lift_mediano_do_controle": arredonda(
                l["lift_mediano_do_controle"], 4),
        })
        pares.append(par)

    corte = resumo["percentil_de_corte"]
    minimos = resumo["picks_minimos"]
    return {
        "gerado_em": agora,
        "dados_de": quando_agregou(),
        "janela": {
            "antes": resumo["antes"], "depois": resumo["depois"],
            "recuo": resumo["recuo"],
            "picks_minimos": minimos,
            "percentil_de_corte": corte,
        },
        "contagem": {
            "pares": resumo["pares"], "eventos": resumo["eventos"],
            "destaques": resumo["destaques"],
            "sem_medida": resumo["sem_medida"],
            "pouca_amostra": resumo["poucas"],
        },
        "como_ler": (
            "lift e a taxa de depois dividida pela taxa de antes, em vezes. "
            "percentil_do_pico e a posicao do campeao dentro dos campeoes "
            "SEM evento nas mesmas datas, e destaque e percentil_do_pico "
            "igual ou acima de " + str(corte) + ". pouca_amostra marca "
            "menos de " + str(minimos) + " escolhas na janela de antes, e "
            "esse numero nao deve ser lido sozinho."
        ),
        "pares": pares,
    }


def monta_tipos(linhas: list[dict], resumo: dict, agora: str) -> dict:
    """O teste agrupado por tipo, igual ao bloco do relatorio.

    Cada campeao medido conta como uma moeda: acima do tipico do servidor ou
    abaixo. A chance e a de sair tanto ou mais cara em moeda honesta. O
    intervalo e o de Wilson sobre essa mesma fracao.
    """
    por_tipo: dict[str, list[dict]] = defaultdict(list)
    for l in linhas:
        if l["percentil_do_pico"] is not None:
            por_tipo[l["event_type"]].append(l)

    #clipe e trailer do mesmo lancamento saem com poucos dias de diferenca e
    #medem quase o mesmo pedaco da serie. contar isso importa: as linhas de
    #um tipo nao sao evidencia independente das do outro
    momentos: dict[str, list[tuple[date, str]]] = defaultdict(list)
    for l in linhas:
        momentos[l["champion"]].append(
            (date.fromisoformat(l["event_date"]), l["event_type"])
        )
    sobrepostos: dict[str, int] = defaultdict(int)
    for lista in momentos.values():
        for quando, tipo in lista:
            if any(outro != tipo
                   and abs((quando - data).days) <= resumo["depois"]
                   for data, outro in lista):
                sobrepostos[tipo] += 1

    def conta(medidas: list[dict], campo: str) -> dict:
        acima = sum(1 for m in medidas if m[campo] > 50)
        de = len(medidas)
        ic_de, ic_ate = wilson(acima, de)
        return {
            "acima": acima,
            "de": de,
            "fracao": round(acima / de, 4) if de else None,
            "ic": [round(ic_de, 4), round(ic_ate, 4)],
            "chance": round(prob_de_cauda(acima, de), 4),
        }

    saida = []
    for tipo in sorted(por_tipo):
        medidas = por_tipo[tipo]
        #pelo pico e a medida que o relatorio usa para concluir. pelo lift e
        #a conservadora, e as duas nao dao a mesma resposta para clipe, entao
        #o painel precisa das duas para mostrar de que a conclusao depende
        linha = conta(medidas, "percentil_do_pico")
        pelo_lift = [m for m in medidas if m["percentil_do_lift"] is not None]
        linha.update({
            "tipo": tipo,
            "eventos": len({m["event_id"] for m in medidas}),
            "sobrepostos": sobrepostos.get(tipo, 0),
            "pelo_lift": conta(pelo_lift, "percentil_do_lift"),
        })
        saida.append(linha)

    return {
        "gerado_em": agora,
        "dados_de": quando_agregou(),
        "medida": {
            "criterio": "percentil_do_pico acima de 50",
            "pico": ("a melhor janelinha de 3 dias dentro da janela de "
                     "depois, que e o que captura efeito de novidade"),
            "alternativa": ("percentil_do_lift acima de 50, a media dos 7 "
                            "dias inteiros, que e a medida conservadora"),
            "aviso": ("as duas medidas nao concordam em clipe, entao o "
                      "numero sozinho nao decide: o trabalho precisa dizer "
                      "qual medida ele usa, e o painel precisa mostrar a "
                      "mesma."),
        },
        "tipos": saida,
        "como_ler": (
            "acima e quantos campeoes daquele tipo ficaram acima do tipico "
            "dos campeoes sem evento nas mesmas datas, de um total de de. "
            "os campos de cima sao pelo percentil do PICO, que e a medida do "
            "relatorio, e pelo_lift traz a mesma conta pelo percentil do "
            "LIFT. chance e a de isso acontecer com moeda honesta, entao "
            "chance pequena e sinal. sobrepostos conta as linhas que tem "
            "evento de OUTRO tipo do mesmo campeao dentro da janela, e "
            "nessas o tipo nao e evidencia independente do outro."
        ),
    }


def monta_placebo(dados: dict, linhas: list[dict], resumo: dict,
                  agora: str, repeticoes: int) -> dict:
    agrupados: dict[str, list[str]] = defaultdict(list)
    for l in dados["eventos"]:
        if l["champion"] not in agrupados[l["event_id"]]:
            agrupados[l["event_id"]].append(l["champion"])
    eventos_reais = [(i, agrupados[i]) for i in sorted(agrupados)]

    contagens = placebo(
        dados["tabela"], dados["campeoes"], eventos_reais, resumo["antes"],
        resumo["depois"], dados["balanceamento"], repeticoes,
        SEMENTE_PLACEBO, resumo["recuo"],
    )
    marcados = [(l["champion"], date.fromisoformat(l["event_date"]))
                for l in linhas if l["destaque"]]
    real = destaques_distintos(marcados, resumo["depois"])
    magros = sum(1 for l in linhas if l["destaque"] and l["pouca_amostra"])

    ordenadas = sorted(contagens)
    tantos = sum(1 for c in ordenadas if c >= real)
    quantos = len(ordenadas)
    return {
        "gerado_em": agora,
        "dados_de": quando_agregou(),
        "repeticoes": quantos,
        "semente": SEMENTE_PLACEBO,
        "contagens": contagens,
        "real": real,
        "pares_marcados": resumo["destaques"],
        "pares_marcados_magros": magros,
        "media": round(sum(ordenadas) / quantos, 2) if quantos else 0,
        "minimo": ordenadas[0] if quantos else 0,
        "maximo": ordenadas[-1] if quantos else 0,
        "percentil_95": ordenadas[int(0.95 * (quantos - 1))] if quantos else 0,
        "empataram_ou_passaram": tantos,
        "chance": round(tantos / quantos, 4) if quantos else 1.0,
        "como_ler": (
            "a medida inteira foi repetida com a data de cada evento "
            "sorteada e os campeoes de verdade. contagens tem um numero por "
            "sorteio: quantos destaques o metodo inventou sem efeito nenhum "
            "para achar. real e a contagem com as datas verdadeiras, e a "
            "distancia entre as duas coisas e o argumento."
        ),
    }


def monta_controle(resumo: dict, agora: str) -> dict:
    """A distribuicao do grupo de controle em cada data de evento.

    O histograma de cada campeao mostra em cinza o lift dos campeoes SEM
    evento naquelas mesmas datas, e a seta do campeao em cima. Sem este
    arquivo o navegador teria que refazer essa distribuicao, varrendo os 173
    campeoes em 268 dias, e um erro ali daria percentil diferente do que o
    relatorio afirma.
    """
    eventos = {}
    for event_id, dist in resumo["controles"].items():
        eventos[event_id] = {
            "pico": [round(v, 4) for v in dist["pico"]],
            "lift": [round(v, 4) for v in dist["lift"]],
            "campeoes": len(dist["lift"]),
            "fora_por_mexida": dist["fora_por_mexida"],
        }
    return {
        "gerado_em": agora,
        "dados_de": quando_agregou(),
        "eventos": eventos,
        "como_ler": (
            "para cada evento, pico e lift sao as listas ordenadas do grupo "
            "de controle: os campeoes que NAO tiveram evento nem mexida de "
            "balanceamento dentro da janela daquela data. o percentil de um "
            "campeao em resultados.json e a posicao dele dentro destas "
            "listas, entao o histograma e a seta saem do mesmo numero."
        ),
    }


def main() -> int:
    repeticoes = REPETICOES_PLACEBO
    if len(sys.argv) > 1:
        repeticoes = int(sys.argv[1])

    dados = carrega()
    if not dados["tabela"]["dias"]:
        print("[erro] daily_pickrate.csv nao existe. rode o agregar.py.")
        return 1
    linhas, resumo = monta_linhas(dados)
    if not linhas:
        print("[erro] nenhum par campeao-evento medido. rode o "
              "montar_eventos.py.")
        return 1
    agora = datetime.now(FUSO).isoformat(timespec="seconds")

    print("rodando o placebo, " + str(repeticoes) +
          " repeticoes com data sorteada")
    tipos = monta_tipos(linhas, resumo, agora)
    pl = monta_placebo(dados, linhas, resumo, agora, repeticoes)
    arquivos = [
        ("resultados.json", monta_resultados(linhas, resumo, agora)),
        ("tipos.json", tipos),
        ("placebo.json", pl),
        ("controle.json", monta_controle(resumo, agora)),
    ]

    print(f"{SAIDA.relative_to(RAIZ)}:")
    total = 0
    for nome, conteudo in arquivos:
        tamanho = grava(nome, conteudo)
        total += tamanho
        print(f"  {nome:18s} {tamanho / 1024:8.1f} KB")
    print(f"  {'TOTAL':18s} {total / 1024:8.1f} KB")
    print("")
    for t in tipos["tipos"]:
        print(f"  {t['tipo']:10s} {t['acima']:3d} de {t['de']:3d} acima do "
              f"tipico | chance {t['chance']:.3f}")
    print("")
    print(f"  placebo: real {pl['real']}, media do sorteio {pl['media']}, "
          f"chance {pl['chance']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
