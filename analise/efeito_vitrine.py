"""
Analise de antes e depois: a taxa de escolha sobe quando sai skin ou clipe?

Para cada evento do events.csv compara a taxa de escolha do campeao numa
janela antes e numa janela depois da data do evento, e situa esse resultado
contra o que os campeoes SEM evento fizeram nas mesmas datas. Essa comparacao
com o grupo de controle e o que separa um efeito de vitrine de uma mudanca que
pegou o servidor todo, como um patch de balanceamento amplo ou o fim de uma
temporada.

Modo de teste: --mock roda contra data/mock/daily_pickrate.csv, onde os picos
sao plantados com forca conhecida pelo coleta/gerar_mock.py. Se o metodo nao
reencontra aqueles numeros, ele nao serve para o dado real. Rode o teste antes
de acreditar no resultado.

Rodar:  .venv\\Scripts\\python.exe analise\\efeito_vitrine.py
Teste:  .venv\\Scripts\\python.exe analise\\efeito_vitrine.py --mock
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
import pathlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
REAL = RAIZ / "data" / "processed" / "daily_pickrate.csv"
MOCK = RAIZ / "data" / "mock" / "daily_pickrate.csv"
EVENTOS = RAIZ / "data" / "processed" / "events.csv"
BALANCEAMENTO = RAIZ / "data" / "processed" / "balance_changes.csv"
#nome por modo, para o relatorio do teste nunca ser confundido com o do dado
#real nem sobrescrever ele
RELATORIOS = {
    False: RAIZ / "analise" / "relatorio.txt",
    True: RAIZ / "analise" / "relatorio_mock.txt",
}
GRAFICOS = {
    False: RAIZ / "analise" / "efeito_vitrine.html",
    True: RAIZ / "analise" / "efeito_vitrine_mock.html",
}

#janelas assimetricas de proposito. o efeito de novidade e curto e decai em
#poucos dias, entao media de 14 dias depois dilui o pico ate quase sumir: no
#teste contra o mock, pico plantado de 2.1x saiu medido como 1.41x com 14
#dias e aparece bem melhor com 7. o antes fica longo porque ali o que se quer
#e uma base estavel.
JANELA_ANTES = 14
JANELA_DEPOIS = 7
#largura do pico, em dias, para a medida que nao depende de media longa
LARGURA_DO_PICO = 3
#minimo de dias de cada lado, depois de recortar no periodo disponivel
MINIMO_DE_DIAS = 5
#do coleta/gerar_mock.py, so para o modo de teste: o pico plantado decai com
#exp(-atraso/5) e a taxa final e limitada a 15%. um campeao de base alta nao
#consegue mostrar o pico inteiro, porque bate no teto antes.
DECAIMENTO_DO_MOCK = 5.0
TETO_DO_MOCK = 0.150
#quanto o medido pode se afastar do esperado e ainda contar como recuperado
TOLERANCIA = 0.30

#um campeao so entra no controle se nao tiver evento nesta folga em volta
FOLGA_DO_CONTROLE = 28
#abaixo disso a taxa e ruido, e o relatorio avisa em vez de concluir
PICKS_MINIMOS = 100
#percentil acima do qual o lift se destaca do que os outros campeoes fizeram
PERCENTIL_DE_CORTE = 90
MAXIMO_DE_PAINEIS = 6
#repeticoes do teste de placebo e semente, para o numero ser reproduzivel
REPETICOES_PLACEBO = 200
SEMENTE_PLACEBO = 20260904


def le_pickrate(caminho: Path):
    """Devolve (picks por dia e campeao, partidas por dia, dias, campeoes)."""
    picks: dict[tuple[date, str], int] = {}
    partidas: dict[date, int] = {}
    campeoes: set[str] = set()
    with open(caminho, encoding="utf-8") as arquivo:
        for registro in csv.DictReader(arquivo):
            dia = date.fromisoformat(registro["date"])
            campeao = registro["champion"]
            picks[(dia, campeao)] = int(registro["picks"])
            partidas[dia] = int(registro["games_total"])
            campeoes.add(campeao)
    return picks, partidas, sorted(partidas), sorted(campeoes)


def le_eventos(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def le_balanceamento(caminho: Path) -> dict[str, list[date]]:
    """{campeao: [datas de patch em que ele foi mexido]}."""
    if not caminho.exists():
        print(f"[aviso] {caminho.name} nao existe, entao a analise roda SEM "
              "controlar por balanceamento. rode "
              "coleta/datadragon_balanceamento.py.")
        return {}
    mexidas: dict[str, list[date]] = defaultdict(list)
    with open(caminho, encoding="utf-8") as arquivo:
        for registro in csv.DictReader(arquivo):
            try:
                quando = date.fromisoformat(registro["patch_date"])
            except (ValueError, KeyError):
                continue
            mexidas[registro["champion"]].append(quando)
    return dict(mexidas)


def eventos_do_mock() -> list[dict]:
    """Os picos plantados no mock, para testar o metodo contra a verdade."""
    sys.path.insert(0, str(RAIZ / "coleta"))
    from gerar_mock import EVENTOS_FALSOS

    plantados = []
    for campeao, dia, forca in EVENTOS_FALSOS:
        plantados.append({
            "event_id": f"plantado-{campeao.lower()}",
            "champion": campeao,
            "event_type": "plantado",
            "event_date": dia.isoformat(),
            "title": f"pico plantado de forca {forca}",
            "youtube_id": "",
            "views": "",
            "forca": forca,
        })
    return plantados


def prepara_tabela(picks, partidas, dias, campeoes) -> dict:
    """Somas acumuladas por dia, para a janela sair em tempo constante.

    Sem isso cada soma varre os 76 dias, e o teste de placebo, que repete a
    medida centenas de vezes com datas sorteadas, levaria dezenas de minutos
    em vez de segundos.
    """
    indice = {dia: i for i, dia in enumerate(dias)}
    jogos = [0] * (len(dias) + 1)
    for i, dia in enumerate(dias):
        jogos[i + 1] = jogos[i] + partidas.get(dia, 0)
    escolhas = {}
    for campeao in campeoes:
        linha = [0] * (len(dias) + 1)
        for i, dia in enumerate(dias):
            linha[i + 1] = linha[i] + picks.get((dia, campeao), 0)
        escolhas[campeao] = linha
    return {"dias": dias, "indice": indice, "jogos": jogos,
            "escolhas": escolhas, "campeoes": campeoes}


def soma(tabela, campeao: str, de: date, ate: date) -> tuple[int, int]:
    comeco = tabela["indice"].get(de)
    fim = tabela["indice"].get(ate)
    if comeco is None or fim is None or fim < comeco:
        return 0, 0
    linha = tabela["escolhas"].get(campeao)
    vagas = tabela["jogos"][fim + 1] - tabela["jogos"][comeco]
    if linha is None:
        return 0, vagas
    return linha[fim + 1] - linha[comeco], vagas


def wilson(sucessos: int, tentativas: int, z: float = 1.96):
    """Intervalo de 95% para uma proporcao, sem precisar de scipy."""
    if tentativas <= 0:
        return 0.0, 0.0
    p = sucessos / tentativas
    denominador = 1 + z * z / tentativas
    centro = (p + z * z / (2 * tentativas)) / denominador
    margem = z * math.sqrt(
        p * (1 - p) / tentativas + z * z / (4 * tentativas * tentativas)
    ) / denominador
    return max(0.0, centro - margem), min(1.0, centro + margem)


def intervalo_da_taxa(escolhas: int, jogos: int):
    #cada partida tem 10 vagas de campeao, entao a proporcao por vaga e
    #escolhas / (10 * partidas), e a taxa do contrato e dez vezes isso
    baixo, alto = wilson(escolhas, 10 * jogos)
    return baixo * 10, alto * 10


def prob_de_cauda(acima: int, total: int) -> float:
    """Chance de ter `acima` ou mais de `total` campeoes passando do p50.

    Debaixo da hipotese de que o evento nao faz nada, cada campeao tem meia
    chance de cair acima do tipico dos campeoes sem evento, igual a moeda.
    Quatro de quatro subindo juntos da 6%, e e por isso que olhar o grupo
    pesa mais que olhar um campeao de cada vez: a amostra de cada um e
    pequena, mas eles erram para lados independentes.
    """
    if total <= 0:
        return 1.0
    return sum(math.comb(total, i) for i in range(acima, total + 1)) / 2 ** total


def percentil(valor: float, amostra: list[float]):
    if not amostra:
        return None
    abaixo = sum(1 for x in amostra if x < valor)
    return 100.0 * abaixo / len(amostra)


def pico(tabela, campeao: str, de: date, ate: date,
         largura: int) -> float:
    """Maior taxa de escolha numa janelinha de `largura` dias no intervalo.

    Mede o topo do pico em vez da media dele, o que nao se perde quando o
    efeito dura poucos dias.
    """
    melhor = 0.0
    inicio = de
    while inicio + timedelta(days=largura - 1) <= ate:
        escolhas, jogos = soma(tabela, campeao, inicio,
                               inicio + timedelta(days=largura - 1))
        if jogos:
            melhor = max(melhor, escolhas / jogos)
        inicio += timedelta(days=1)
    return melhor


def limites_da_janela(dias, dia_do_evento: date, janela_antes: int,
                      janela_depois: int):
    #recorta no periodo que existe, em vez de descartar o evento inteiro
    antes_de = max(dias[0], dia_do_evento - timedelta(days=janela_antes))
    antes_ate = dia_do_evento - timedelta(days=1)
    depois_de = dia_do_evento
    depois_ate = min(dias[-1],
                     dia_do_evento + timedelta(days=janela_depois - 1))
    return antes_de, antes_ate, depois_de, depois_ate


def mede(tabela, campeao: str, dia_do_evento: date,
         janela_antes: int, janela_depois: int) -> dict | None:
    antes_de, antes_ate, depois_de, depois_ate = limites_da_janela(
        tabela["dias"], dia_do_evento, janela_antes, janela_depois
    )
    dias_antes = (antes_ate - antes_de).days + 1
    dias_depois = (depois_ate - depois_de).days + 1
    if dias_antes < MINIMO_DE_DIAS or dias_depois < MINIMO_DE_DIAS:
        return None
    e_antes, j_antes = soma(tabela, campeao, antes_de, antes_ate)
    e_depois, j_depois = soma(tabela, campeao, depois_de, depois_ate)
    if j_antes == 0 or j_depois == 0 or e_antes == 0:
        return None
    taxa_antes = e_antes / j_antes
    taxa_depois = e_depois / j_depois
    topo = pico(tabela, campeao, depois_de, depois_ate,
                min(LARGURA_DO_PICO, dias_depois))
    return {
        "campeao": campeao,
        "taxa_antes": taxa_antes,
        "taxa_depois": taxa_depois,
        "lift": taxa_depois / taxa_antes,
        "lift_do_pico": topo / taxa_antes if taxa_antes else 0.0,
        "picks_antes": e_antes,
        "picks_depois": e_depois,
        "jogos_antes": j_antes,
        "jogos_depois": j_depois,
        "dias_antes": dias_antes,
        "dias_depois": dias_depois,
        "ic_antes": intervalo_da_taxa(e_antes, j_antes),
        "ic_depois": intervalo_da_taxa(e_depois, j_depois),
    }


def mexido_na_janela(balanceamento: dict[str, list[date]], campeao: str,
                     de: date, ate: date) -> bool:
    """O campeao levou mudanca de balanceamento dentro desta janela?"""
    return any(de <= quando <= ate
               for quando in balanceamento.get(campeao, []))


def controle(tabela, campeoes, dia_do_evento: date,
             janela_antes: int, janela_depois: int,
             com_evento: dict[str, list[date]],
             balanceamento: dict[str, list[date]]) -> dict:
    """Lift dos campeoes sem evento e sem mexida perto desta data.

    Tira do controle quem foi buffado ou nerfado dentro da janela, porque
    campeao mexido no meio da medida nao representa o que um campeao sem
    nada fez ali. Mexida de dois meses antes nao atrapalha e fica.
    """
    antes_de, _, _, depois_ate = limites_da_janela(
        tabela["dias"], dia_do_evento, janela_antes, janela_depois
    )
    lifts: list[float] = []
    picos: list[float] = []
    fora_por_evento = 0
    fora_por_mexida = 0
    for campeao in campeoes:
        datas = com_evento.get(campeao) or []
        if any(abs((d - dia_do_evento).days) <= FOLGA_DO_CONTROLE
               for d in datas):
            fora_por_evento += 1
            continue
        if mexido_na_janela(balanceamento, campeao, antes_de, depois_ate):
            fora_por_mexida += 1
            continue
        medida = mede(tabela, campeao, dia_do_evento,
                      janela_antes, janela_depois)
        if medida:
            lifts.append(medida["lift"])
            picos.append(medida["lift_do_pico"])
    return {
        "lift": sorted(lifts),
        "pico": sorted(picos),
        "fora_por_evento": fora_por_evento,
        "fora_por_mexida": fora_por_mexida,
    }


def destaques_distintos(pares: list[tuple[str, date]], janela: int) -> int:
    """Conta momentos distintos, nao pares campeao-evento.

    Dois eventos do mesmo campeao em datas proximas medem o mesmo pedaco da
    serie e nao sao duas evidencias. A Evelynn ganhou duas skins no mesmo
    patch, o que dava a mesma medida contada duas vezes, e o Aphelios teve
    clipe e trailer com quatro dias de diferenca, com as janelas quase
    sobrepostas. Sem esse corte o numero real infla e o placebo nao, porque
    no placebo as datas sorteadas caem longe umas das outras.
    """
    por_campeao: dict[str, list[date]] = defaultdict(list)
    for campeao, quando in pares:
        por_campeao[campeao].append(quando)
    total = 0
    for datas in por_campeao.values():
        ultimo = None
        for quando in sorted(datas):
            if ultimo is None or (quando - ultimo).days > janela:
                total += 1
                ultimo = quando
    return total


def placebo(tabela, campeoes, eventos_reais: list[tuple[str, list[str]]],
            janela_antes: int, janela_depois: int,
            balanceamento: dict[str, list[date]], repeticoes: int,
            semente: int) -> list[int]:
    """Repete a medida inteira com datas de evento sorteadas.

    Serve para responder a pergunta que derruba qualquer analise de antes e
    depois: quantos destaques esse metodo produz quando NAO ha efeito
    nenhum? Os campeoes de cada evento sao os de verdade, so a data e
    falsa. Se o numero de destaques com data falsa for parecido com o
    numero com data real, o resultado real nao diz nada.
    """
    sorteio = random.Random(semente)
    dias = tabela["dias"]
    #so datas que deixam janela suficiente dos dois lados, igual ao real
    possiveis = [
        dia for dia in dias
        if (dia - dias[0]).days >= MINIMO_DE_DIAS
        and (dias[-1] - dia).days >= MINIMO_DE_DIAS - 1
    ]
    if not possiveis:
        return []

    contagens: list[int] = []
    for _ in range(repeticoes):
        datas_falsas = [sorteio.choice(possiveis) for _ in eventos_reais]
        com_evento: dict[str, list[date]] = defaultdict(list)
        for (_, nomes), quando in zip(eventos_reais, datas_falsas):
            for campeao in nomes:
                com_evento[campeao].append(quando)

        cache: dict[date, dict] = {}
        marcados: list[tuple[str, date]] = []
        for (_, nomes), quando in zip(eventos_reais, datas_falsas):
            for campeao in nomes:
                medida = mede(tabela, campeao, quando, janela_antes,
                              janela_depois)
                if not medida:
                    continue
                if quando not in cache:
                    cache[quando] = controle(
                        tabela, campeoes, quando, janela_antes,
                        janela_depois, com_evento, balanceamento
                    )
                posicao = percentil(medida["lift_do_pico"],
                                    cache[quando]["pico"])
                if posicao is not None and posicao >= PERCENTIL_DE_CORTE:
                    marcados.append((campeao, quando))
        contagens.append(destaques_distintos(marcados, janela_depois))
    return contagens


def nome_da_linha(event_id: str) -> str:
    partes = event_id.split("-")
    if partes[0] == "clipe":
        return "-".join(partes[1:])
    if partes[0] == "skin":
        return "-".join(partes[2:])
    return event_id


def valida_contra_o_mock(dados: dict) -> str:
    """Compara o pico medido com o maximo que o mock permitia.

    Nao e o pico plantado cru. O mock decai o pico com exp(-atraso/5), e a
    janelinha do pico pega varios dias, entao parte do excesso se perde por
    construcao. E ele limita a taxa a 15%, entao campeao de base alta nao
    consegue mostrar o pico inteiro de jeito nenhum. O esperado abaixo ja
    desconta as duas coisas.
    """
    largura = min(LARGURA_DO_PICO, dados["depois"])
    fator = sum(math.exp(-i / DECAIMENTO_DO_MOCK)
                for i in range(largura)) / largura

    partes: list[str] = []
    partes.append("TESTE DO METODO CONTRA O MOCK")
    partes.append(f"  o excesso do pico decai com exp(-atraso/"
                  f"{DECAIMENTO_DO_MOCK:.0f}), e a janelinha de {largura} "
                  f"dias pega em media {fator:.3f} dele.")
    partes.append(f"  a taxa do mock para em {TETO_DO_MOCK:.3f}, entao "
                  "campeao de base alta tem teto proprio.")
    partes.append("")
    partes.append(f"  {'campeao':12s} {'forca':>6s} {'teto':>6s} "
                  f"{'esperado':>9s} {'medido':>7s} {'razao':>6s}")

    recuperados = 0
    total = 0
    for evento in dados["resultados"]:
        forca = dados["forcas"].get(evento["event_id"])
        if forca is None:
            continue
        for medida in evento["medidas"]:
            total += 1
            teto = (TETO_DO_MOCK / medida["taxa_antes"]
                    if medida["taxa_antes"] else float("inf"))
            esperado = min(1 + (forca - 1) * fator, teto)
            medido = medida["lift_do_pico"]
            razao = medido / esperado if esperado else 0.0
            if abs(razao - 1) <= TOLERANCIA:
                recuperados += 1
            partes.append(
                f"  {medida['campeao'][:12]:12s} {forca:5.2f}x "
                f"{teto:5.2f}x {esperado:8.2f}x {medido:6.2f}x "
                f"{razao:5.2f}"
            )
    partes.append("")
    partes.append(f"  {recuperados} de {total} dentro de "
                  f"{TOLERANCIA:.0%} do esperado.")
    partes.append("  razao perto de 1.00 quer dizer que o metodo achou o que")
    partes.append("  o mock plantou. muito abaixo de 1.00 e metodo cego, e")
    partes.append("  muito acima e metodo que inventa efeito.")
    partes.append("")
    return "\n".join(partes)


def bloco_do_placebo(dados: dict) -> str:
    contagens = sorted(dados["placebo"])
    real = dados["acima_de_verdade"]
    tantos = sum(1 for c in contagens if c >= real)
    chance = tantos / len(contagens)
    media = sum(contagens) / len(contagens)
    partes = ["TESTE DE PLACEBO"]
    partes.append(f"  a medida inteira foi repetida {len(contagens)} vezes "
                  "com a data de")
    partes.append("  cada evento sorteada, mantendo os campeoes de verdade.")
    partes.append("  isso mostra quantos destaques o metodo inventa quando "
                  "nao ha")
    partes.append("  efeito nenhum para achar.")
    partes.append("")
    partes.append(f"  momentos campeao-data distintos com destaque: {real}")
    partes.append(f"  pares campeao-evento marcados, antes do corte: "
                  f"{dados['pares_de_verdade']}")
    partes.append(f"  destaques com data sorteada:   media {media:.1f}, "
                  f"minimo {contagens[0]}, maximo {contagens[-1]}")
    partes.append(f"  percentil 95 do sorteio:       "
                  f"{contagens[int(0.95 * (len(contagens) - 1))]}")
    partes.append(f"  sorteios que empataram ou passaram o real: "
                  f"{tantos} de {len(contagens)}, ou seja {chance:.3f}")
    partes.append("")
    magros = dados["magros_marcados"]
    pares = dados["pares_de_verdade"]
    if pares:
        partes.append(f"  CUIDADO: {magros} dos {pares} pares marcados vem "
                      f"de campeao com menos de {PICKS_MINIMOS} escolhas na")
        partes.append("  janela de antes. em campeao pouco escolhido, meia")
        partes.append("  duzia de escolhas a mais ja vira lift de duas vezes,")
        partes.append("  entao esse resultado esta pendurado nos numeros mais")
        partes.append("  ruidosos da amostra. compare com os testes por tipo,")
        partes.append("  logo abaixo: se eles nao acompanham, nao conclua.")
        partes.append("")
    if chance > 0.10:
        partes.append("  leitura: o resultado real cabe tranquilamente no "
                      "que o acaso")
        partes.append("  produz. nao ha efeito para relatar.")
    elif chance > 0.05:
        partes.append("  leitura: o resultado real esta na beirada do que o "
                      "acaso produz.")
        partes.append("  sugere algo, nao sustenta conclusao.")
    else:
        partes.append("  leitura: o acaso raramente produz tanto destaque "
                      "assim.")
        partes.append("  aqui ha efeito a relatar.")
    partes.append("")
    return "\n".join(partes)


def monta_relatorio(dados: dict) -> str:
    partes: list[str] = []
    partes.append("EFEITO VITRINE: ANTES E DEPOIS")
    partes.append(f"fonte: {dados['fonte']}")
    partes.append(f"janela: {dados['antes']} dias antes e "
                  f"{dados['depois']} dias depois da data do evento")
    partes.append(f"periodo do dado: {dados['dias'][0]} a {dados['dias'][-1]}")
    media = sum(dados["partidas"].values()) / len(dados["dias"])
    partes.append(f"partidas por dia na amostra: media {media:.0f}")
    partes.append("")
    partes.append("COMO LER")
    partes.append("  lift e a taxa media depois dividida pela taxa antes.")
    partes.append("  1.00 e nenhuma mudanca, 1.50 e cinquenta por cento mais.")
    partes.append(f"  pico e a mesma conta usando a melhor janelinha de")
    partes.append(f"  {LARGURA_DO_PICO} dias dentro do depois. serve porque")
    partes.append("  efeito de novidade dura pouco e media longa o dilui:")
    partes.append("  no teste contra o mock, pico plantado de 2.1x aparece")
    partes.append("  como 1.41x na media de 14 dias.")
    partes.append("  percentil diz onde o numero cai na distribuicao dos")
    partes.append("  campeoes SEM evento nas mesmas datas. p50 e o tipico")
    partes.append("  do servidor naquele periodo, e so acima de")
    partes.append(f"  p{PERCENTIL_DE_CORTE} o campeao se destacou do resto.")
    partes.append("  o intervalo e de 95%. se os dois intervalos se cruzam,")
    partes.append("  a amostra nao sustenta a diferenca.")
    partes.append("")

    for evento in dados["resultados"]:
        partes.append(f"{evento['event_id']}  ({evento['event_type']}, "
                      f"{evento['event_date']})")
        partes.append(f"  {evento['title'][:70]}")
        if not evento["medidas"]:
            partes.append("  sem janela completa no periodo, "
                          "nao da para medir")
            partes.append("")
            continue
        partes.append(f"  {'campeao':12s} {'antes':>8s} {'depois':>8s} "
                      f"{'lift':>7s} {'perc':>5s} {'pico':>7s} {'perc':>5s} "
                      f"{'picks':>13s}")
        for medida in evento["medidas"]:
            pos = medida["percentil"]
            pos_pico = medida["percentil_do_pico"]
            marca = f"p{pos:.0f}" if pos is not None else "-"
            marca_pico = f"p{pos_pico:.0f}" if pos_pico is not None else "-"
            destaque = " *" if (pos_pico is not None
                                and pos_pico >= PERCENTIL_DE_CORTE) else ""
            if medida.get("confundido"):
                destaque += " CONFUNDIDO"
            partes.append(
                f"  {medida['campeao'][:12]:12s} "
                f"{medida['taxa_antes']:8.4f} {medida['taxa_depois']:8.4f} "
                f"{medida['lift']:6.2f}x {marca:>5s} "
                f"{medida['lift_do_pico']:6.2f}x {marca_pico:>5s} "
                f"{medida['picks_antes']:5d} / {medida['picks_depois']:5d}"
                f"{destaque}"
            )
        magros = [m for m in evento["medidas"]
                  if m["picks_antes"] < PICKS_MINIMOS]
        cruzam = [m for m in evento["medidas"]
                  if m["ic_antes"][1] >= m["ic_depois"][0]
                  and m["ic_depois"][1] >= m["ic_antes"][0]]
        acima = [m for m in evento["medidas"]
                 if m["percentil_do_pico"] is not None
                 and m["percentil_do_pico"] >= PERCENTIL_DE_CORTE]
        partes.append(f"  acima de p{PERCENTIL_DE_CORTE}: {len(acima)} de "
                      f"{len(evento['medidas'])} campeoes")
        subiram = [m for m in evento["medidas"]
                   if m["percentil_do_pico"] is not None
                   and m["percentil_do_pico"] > 50]
        com_percentil = [m for m in evento["medidas"]
                         if m["percentil_do_pico"] is not None]
        if com_percentil:
            chance = prob_de_cauda(len(subiram), len(com_percentil))
            partes.append(f"  grupo: {len(subiram)} de "
                          f"{len(com_percentil)} campeoes acima do tipico, "
                          f"chance {chance:.3f} por acaso")
        primeira = evento["medidas"][0]
        partes.append(f"  controle: {primeira['controle']} campeoes, "
                      f"{primeira.get('fora_por_mexida', 0)} tirados por "
                      "mexida de balanceamento na janela")
        confundidos = [m for m in evento["medidas"] if m.get("confundido")]
        if confundidos:
            nomes = ", ".join(m["campeao"] for m in confundidos)
            partes.append(f"  [confundido] {nomes} levou mudanca de "
                          "balanceamento dentro da janela, entao aqui a skin "
                          "e o balanceamento nao se separam")
        if cruzam:
            partes.append(f"  [ressalva] {len(cruzam)} campeoes com os "
                          "intervalos de 95% se cruzando: a amostra nao "
                          "sustenta a diferenca")
        if magros:
            partes.append(f"  [ressalva] {len(magros)} campeoes com menos de "
                          f"{PICKS_MINIMOS} escolhas na janela de antes: "
                          "numero ruidoso")
        partes.append("")

    if dados.get("forcas"):
        partes.append(valida_contra_o_mock(dados))

    if dados.get("placebo"):
        partes.append(bloco_do_placebo(dados))

    partes.append("TESTE AGRUPADO POR TIPO DE EVENTO")
    partes.append("  esta e a pergunta do projeto: skin levanta a taxa?")
    partes.append("  clipe levanta? juntar todos os campeoes de todos os")
    partes.append("  eventos do mesmo tipo ganha poder, porque a amostra de")
    partes.append("  cada campeao e pequena mas eles erram para lados")
    partes.append("  independentes. o numero por evento, acima, serve para")
    partes.append("  olhar, e este serve para concluir.")
    partes.append("")
    partes.append(f"  {'tipo':12s} {'acima':>7s} {'de':>5s} {'chance':>8s}")
    por_tipo: dict[str, list[dict]] = {}
    for evento in dados["resultados"]:
        for medida in evento["medidas"]:
            if medida["percentil_do_pico"] is not None:
                por_tipo.setdefault(evento["event_type"], []).append(medida)
    for tipo in sorted(por_tipo):
        medidas = por_tipo[tipo]
        acima = sum(1 for m in medidas if m["percentil_do_pico"] > 50)
        chance = prob_de_cauda(acima, len(medidas))
        partes.append(f"  {tipo:12s} {acima:7d} {len(medidas):5d} "
                      f"{chance:8.3f}")
    partes.append("")
    #clipe e trailer do mesmo lancamento saem com poucos dias de diferenca,
    #entao medem quase o mesmo pedaco da serie. dizer isso importa: as
    #linhas de um tipo nao sao evidencia independente das do outro.
    momentos: dict[str, list[tuple[date, str]]] = {}
    for evento in dados["resultados"]:
        quando = date.fromisoformat(evento["event_date"])
        for medida in evento["medidas"]:
            momentos.setdefault(medida["campeao"], []).append(
                (quando, evento["event_type"])
            )
    sobrepostos: dict[str, int] = {}
    for lista in momentos.values():
        for quando, tipo in lista:
            if any(outro != tipo and abs((quando - data).days)
                   <= dados["depois"] for data, outro in lista):
                sobrepostos[tipo] = sobrepostos.get(tipo, 0) + 1
    if sobrepostos:
        detalhe = ", ".join(f"{tipo} {n}" for tipo, n in
                            sorted(sobrepostos.items()))
        partes.append(f"  CUIDADO: {detalhe} linhas tem evento de OUTRO tipo")
        partes.append("  do mesmo campeao dentro da janela. clipe e trailer")
        partes.append("  do mesmo lancamento saem com dois a quatro dias de")
        partes.append("  diferenca e medem quase o mesmo pedaco da serie,")
        partes.append("  entao as linhas desses tipos nao sao evidencia")
        partes.append("  independente uma da outra.")
        partes.append("")
    partes.append("  chance e a probabilidade de ver esse tanto de campeoes")
    partes.append("  acima do tipico, ou mais, se o evento nao fizesse nada.")
    partes.append("  abaixo de 0.05 comeca a valer conversa, e com quatro")
    partes.append("  tipos testados o corte honesto fica mais perto de 0.01.")
    partes.append("")

    partes.append("RESUMO")
    total = sum(len(e["medidas"]) for e in dados["resultados"])
    destacados = sum(
        1 for e in dados["resultados"] for m in e["medidas"]
        if m["percentil_do_pico"] is not None
        and m["percentil_do_pico"] >= PERCENTIL_DE_CORTE
    )
    partes.append(f"  {total} pares campeao-evento medidos, {destacados} "
                  f"acima de p{PERCENTIL_DE_CORTE}")
    if total:
        partes.append(f"  por acaso, esperado acima de p"
                      f"{PERCENTIL_DE_CORTE}: "
                      f"{total * (100 - PERCENTIL_DE_CORTE) / 100:.1f}")
        partes.append("  se o numero de destaques nao passa do esperado por")
        partes.append("  acaso, o dado nao mostra efeito nenhum ainda.")
    partes.append("")
    return "\n".join(partes) + "\n"


def desenha(dados: dict, grafico: pathlib.Path) -> bool:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return False

    por_linha: dict[str, list[dict]] = defaultdict(list)
    for evento in dados["resultados"]:
        if evento["medidas"]:
            por_linha[nome_da_linha(evento["event_id"])].append(evento)
    linhas = sorted(por_linha, key=lambda nome: -len(por_linha[nome]))
    linhas = linhas[:MAXIMO_DE_PAINEIS]
    if not linhas:
        return False

    figura = make_subplots(rows=len(linhas), cols=1, shared_xaxes=False,
                           subplot_titles=linhas, vertical_spacing=0.08)
    for posicao, nome in enumerate(linhas, start=1):
        eventos = por_linha[nome]
        campeoes = sorted({m["campeao"] for e in eventos
                           for m in e["medidas"]})
        for campeao in campeoes:
            serie_x = []
            serie_y = []
            for dia in dados["dias"]:
                jogos = dados["partidas"].get(dia, 0)
                if not jogos:
                    continue
                serie_x.append(dia.isoformat())
                serie_y.append(dados["picks"].get((dia, campeao), 0) / jogos)
            figura.add_trace(
                go.Scatter(x=serie_x, y=serie_y, mode="lines", name=campeao,
                           legendgroup=nome, showlegend=posicao == 1),
                row=posicao, col=1,
            )
        for evento in eventos:
            figura.add_vline(
                x=evento["event_date"],
                line_width=1,
                line_dash="dash",
                annotation_text=evento["event_type"],
                row=posicao, col=1,
            )
    figura.update_layout(
        height=320 * len(linhas),
        title="Taxa de escolha em volta de cada evento",
        template="plotly_white",
    )
    grafico.parent.mkdir(parents=True, exist_ok=True)
    figura.write_html(grafico, include_plotlyjs="cdn")
    return True


def main() -> int:
    analisador = argparse.ArgumentParser(description="Analise antes e depois")
    analisador.add_argument("--mock", action="store_true",
                            help="roda no mock, com picos de forca conhecida")
    analisador.add_argument("--antes", type=int, default=JANELA_ANTES,
                            help="dias da janela antes do evento")
    analisador.add_argument("--depois", type=int, default=JANELA_DEPOIS,
                            help="dias da janela depois do evento")
    analisador.add_argument("--placebo", type=int, default=REPETICOES_PLACEBO,
                            help="repeticoes do teste de placebo, 0 desliga")
    argumentos = analisador.parse_args()

    fonte = MOCK if argumentos.mock else REAL
    if not fonte.exists():
        print(f"[erro] {fonte} nao existe.")
        return 1
    picks, partidas, dias, campeoes = le_pickrate(fonte)
    tabela = prepara_tabela(picks, partidas, dias, campeoes)

    if argumentos.mock:
        eventos = eventos_do_mock()
    else:
        eventos = le_eventos(EVENTOS)
    if not eventos:
        print("[erro] nenhum evento para analisar. "
              "rode eventos/montar_eventos.py primeiro.")
        return 1

    com_evento: dict[str, list[date]] = defaultdict(list)
    for linha in eventos:
        com_evento[linha["champion"]].append(
            date.fromisoformat(linha["event_date"])
        )

    #no modo de teste nao entra balanceamento: o mock nao tem patch nenhum,
    #e misturar os dois estragaria a comparacao com a forca plantada
    balanceamento = ({} if argumentos.mock
                     else le_balanceamento(BALANCEAMENTO))

    agrupados: dict[str, list[dict]] = defaultdict(list)
    for linha in eventos:
        agrupados[linha["event_id"]].append(linha)

    cache_controle: dict[tuple[date, int], list[float]] = {}
    resultados = []
    for event_id, linhas in sorted(agrupados.items()):
        dia_do_evento = date.fromisoformat(linhas[0]["event_date"])
        medidas = []
        for linha in sorted(linhas, key=lambda l: l["champion"]):
            medida = mede(tabela, linha["champion"],
                          dia_do_evento, argumentos.antes, argumentos.depois)
            if not medida:
                continue
            chave = (dia_do_evento, argumentos.antes, argumentos.depois)
            if chave not in cache_controle:
                cache_controle[chave] = controle(
                    tabela, campeoes, dia_do_evento,
                    argumentos.antes, argumentos.depois, com_evento,
                    balanceamento
                )
            referencia = cache_controle[chave]
            medida["percentil"] = percentil(medida["lift"],
                                            referencia["lift"])
            medida["percentil_do_pico"] = percentil(medida["lift_do_pico"],
                                                    referencia["pico"])
            medida["controle"] = len(referencia["lift"])
            medida["fora_por_mexida"] = referencia["fora_por_mexida"]
            #o proprio campeao do evento levou mexida dentro da janela?
            antes_de, _, _, depois_ate = limites_da_janela(
                tabela["dias"], dia_do_evento, argumentos.antes,
                argumentos.depois
            )
            medida["confundido"] = mexido_na_janela(
                balanceamento, linha["champion"], antes_de, depois_ate
            )
            medidas.append(medida)
        resultados.append({
            "event_id": event_id,
            "event_type": linhas[0]["event_type"],
            "event_date": linhas[0]["event_date"],
            "title": linhas[0]["title"],
            "medidas": medidas,
        })

    marcas = [
        (m["campeao"], date.fromisoformat(e["event_date"]), m["picks_antes"])
        for e in resultados for m in e["medidas"]
        if m["percentil_do_pico"] is not None
        and m["percentil_do_pico"] >= PERCENTIL_DE_CORTE
    ]
    marcados_de_verdade = [(c, d) for c, d, _ in marcas]
    magros_marcados = sum(1 for _, _, n in marcas if n < PICKS_MINIMOS)
    pares_de_verdade = len(marcados_de_verdade)
    acima_de_verdade = destaques_distintos(marcados_de_verdade,
                                           argumentos.depois)
    contagens_do_placebo: list[int] = []
    if argumentos.placebo > 0:
        eventos_reais = [
            (event_id, [l["champion"] for l in linhas])
            for event_id, linhas in sorted(agrupados.items())
        ]
        print(f"rodando o placebo, {argumentos.placebo} repeticoes com data "
              "sorteada")
        contagens_do_placebo = placebo(
            tabela, campeoes, eventos_reais, argumentos.antes,
            argumentos.depois, balanceamento, argumentos.placebo,
            SEMENTE_PLACEBO,
        )

    dados = {
        "fonte": fonte.relative_to(RAIZ).as_posix(),
        "placebo": contagens_do_placebo,
        "acima_de_verdade": acima_de_verdade,
        "pares_de_verdade": pares_de_verdade,
        "magros_marcados": magros_marcados,
        "antes": argumentos.antes,
        "depois": argumentos.depois,
        "picks": picks,
        "partidas": partidas,
        "dias": dias,
        "resultados": resultados,
        "forcas": {linha["event_id"]: linha["forca"] for linha in eventos
                   if "forca" in linha},
    }

    alvo = RELATORIOS[argumentos.mock]
    grafico = GRAFICOS[argumentos.mock]
    relatorio = monta_relatorio(dados)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    parcial = alvo.parent / (alvo.name + ".parcial")
    parcial.write_text(relatorio, encoding="utf-8")
    os.replace(parcial, alvo)
    print(f"{alvo.relative_to(RAIZ)}: "
          f"{len(relatorio.splitlines())} linhas")
    if desenha(dados, grafico):
        print(f"{grafico.relative_to(RAIZ)}: grafico por evento")

    medidos = sum(len(e["medidas"]) for e in resultados)
    destacados = sum(
        1 for e in resultados for m in e["medidas"]
        if m["percentil_do_pico"] is not None
        and m["percentil_do_pico"] >= PERCENTIL_DE_CORTE
    )
    print("")
    print(f"eventos: {len(resultados)} | pares campeao-evento medidos: "
          f"{medidos} | acima de p{PERCENTIL_DE_CORTE}: {destacados}")
    if medidos:
        print(f"esperado por acaso acima de p{PERCENTIL_DE_CORTE}: "
              f"{medidos * (100 - PERCENTIL_DE_CORTE) / 100:.1f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
