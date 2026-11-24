"""
Coletor de partidas ranqueadas do BR1.

Divide o periodo em semanas de segunda a domingo no fuso de Brasilia e baixa
partidas em rodizio entre elas, em tres passadas de meta crescente, para que
o dado fique equilibrado a qualquer momento em que a coleta pare.

O estado fica em data/raw/coleta.sqlite e o coletor retoma de onde parou.
Ctrl+C encerra sem corromper o matches.jsonl.

Rodar:  .venv/Scripts/python.exe coleta/coletar.py
Teste:  .venv/Scripts/python.exe coleta/coletar.py --minutos 2 --cada 10
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sqlite3
import sys
import time
from collections import deque
from datetime import date, datetime, timedelta

import riot_api
from config import (
    ARQUIVO_LOG,
    ARQUIVO_TRAVA,
    BANCO,
    DATA_FINAL,
    DATA_INICIAL,
    DIVISOES,
    ELOS_APEX,
    ELOS_COM_DIVISAO,
    ESTOQUE_MINIMO,
    FILA_RANQUEADA,
    FUSO,
    JANELA_DA_TAXA,
    JOGADORES_POR_ELO,
    LOTE_DE_JOGADORES,
    LOTE_POR_SEMANA,
    META_PROPORCIONAL_AOS_DIAS,
    METAS_POR_PASSADA,
    PARAR_EM,
    PARAR_NA_PASSADA,
    PAGINAS_MAXIMAS,
    PARTIDAS,
    PROGRESSO_CADA,
    SEMENTE_SORTEIO,
)
from riot_api import ClienteRiot, epoch

ESQUEMA = """
CREATE TABLE IF NOT EXISTS jogadores (
    puuid    TEXT PRIMARY KEY,
    elo      TEXT NOT NULL,
    visto_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paginas (
    elo     TEXT NOT NULL,
    divisao TEXT NOT NULL,
    proxima INTEGER NOT NULL,
    PRIMARY KEY (elo, divisao)
);
CREATE TABLE IF NOT EXISTS semanas (
    indice INTEGER PRIMARY KEY,
    inicio TEXT NOT NULL,
    fim    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ids (
    match_id TEXT PRIMARY KEY,
    semana   INTEGER NOT NULL,
    situacao TEXT NOT NULL DEFAULT 'pendente',
    erro     TEXT
);
CREATE TABLE IF NOT EXISTS sementes_usadas (
    puuid  TEXT NOT NULL,
    semana INTEGER NOT NULL,
    PRIMARY KEY (puuid, semana)
);
CREATE TABLE IF NOT EXISTS progresso (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ids_semana ON ids (semana, situacao);
"""


def prepara_log() -> logging.Logger:
    ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
    log = logging.getLogger("coletor")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    arquivo = logging.FileHandler(ARQUIVO_LOG, encoding="utf-8")
    arquivo.setFormatter(formato)
    tela = logging.StreamHandler(sys.stdout)
    tela.setFormatter(formato)
    log.addHandler(arquivo)
    log.addHandler(tela)
    return log


def trava_instancia_unica(log: logging.Logger):
    """Garante um coletor so neste projeto.

    Dois coletores brigam pelo banco e um morre no meio, com um traceback de
    "database is locked" que nao explica nada. A trava e um bloqueio de
    arquivo do proprio sistema operacional, que ele solta sozinho quando o
    processo termina, inclusive em queda de energia, entao nunca sobra trava
    velha para limpar na mao.

    Devolve o arquivo aberto, que precisa ficar vivo enquanto o coletor
    roda: se ele for fechado, a trava sai junto.
    """
    ARQUIVO_TRAVA.parent.mkdir(parents=True, exist_ok=True)
    arquivo = open(ARQUIVO_TRAVA, "a+", encoding="utf-8")
    arquivo.seek(0)
    try:
        try:
            import msvcrt
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        except ImportError:
            import fcntl
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        arquivo.close()
        log.info("[trava] ja existe um coletor rodando neste projeto.")
        log.info("[trava] dois ao mesmo tempo brigam pelo banco e um morre "
                 "no meio da coleta.")
        log.info("[trava] pare o outro antes, ou deixe ele terminar.")
        sys.exit(3)
    arquivo.seek(0)
    arquivo.truncate()
    arquivo.write(f"{os.getpid()}\n")
    arquivo.flush()
    return arquivo


def abre_banco() -> sqlite3.Connection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO)
    #WAL deixa o agregar.py ler enquanto o coletor escreve
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(ESQUEMA)
    con.commit()
    return con


def valor(con: sqlite3.Connection, chave: str, padrao: str) -> str:
    linha = con.execute("SELECT valor FROM progresso WHERE chave = ?",
                        (chave,)).fetchone()
    return linha[0] if linha else padrao


def guarda(con: sqlite3.Connection, chave: str, novo) -> None:
    con.execute(
        "INSERT INTO progresso (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, str(novo)),
    )
    con.commit()


def janelas_semanais(inicio: date, fim: date) -> list[tuple[date, date]]:
    """Semanas de segunda a domingo, recortadas no periodo. Fim exclusivo."""
    janelas: list[tuple[date, date]] = []
    atual = inicio
    limite = fim + timedelta(days=1)
    while atual < limite:
        passo = (7 - atual.weekday()) % 7 or 7
        proxima = min(atual + timedelta(days=passo), limite)
        janelas.append((atual, proxima))
        atual = proxima
    return janelas


def registra_semanas(con: sqlite3.Connection,
                     janelas: list[tuple[date, date]]) -> None:
    for indice, (inicio, fim) in enumerate(janelas, start=1):
        con.execute(
            "INSERT INTO semanas (indice, inicio, fim) VALUES (?, ?, ?) "
            "ON CONFLICT(indice) DO UPDATE SET inicio = excluded.inicio, "
            "fim = excluded.fim",
            (indice, inicio.isoformat(), fim.isoformat()),
        )
    con.commit()


def conta_jogadores(con: sqlite3.Connection, elo: str | None = None) -> int:
    if elo is None:
        return con.execute("SELECT COUNT(*) FROM jogadores").fetchone()[0]
    return con.execute("SELECT COUNT(*) FROM jogadores WHERE elo = ?",
                       (elo,)).fetchone()[0]


def conta_ids(con: sqlite3.Connection, semana: int, situacao: str) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM ids WHERE semana = ? AND situacao = ?",
        (semana, situacao),
    ).fetchone()[0]


def proxima_pagina(con: sqlite3.Connection, elo: str, divisao: str) -> int:
    linha = con.execute(
        "SELECT proxima FROM paginas WHERE elo = ? AND divisao = ?",
        (elo, divisao),
    ).fetchone()
    return linha[0] if linha else 1


def marca_pagina(con: sqlite3.Connection, elo: str, divisao: str,
                 pagina: int) -> None:
    con.execute(
        "INSERT INTO paginas (elo, divisao, proxima) VALUES (?, ?, ?) "
        "ON CONFLICT(elo, divisao) DO UPDATE SET proxima = excluded.proxima",
        (elo, divisao, pagina),
    )


def guarda_jogadores(con: sqlite3.Connection, puuids: list[str],
                     elo: str) -> int:
    agora = datetime.now(FUSO).isoformat(timespec="seconds")
    antes = conta_jogadores(con)
    con.executemany(
        "INSERT OR IGNORE INTO jogadores (puuid, elo, visto_em) "
        "VALUES (?, ?, ?)",
        [(puuid, elo, agora) for puuid in puuids],
    )
    con.commit()
    return conta_jogadores(con) - antes


def amplia_sementes(cliente: ClienteRiot, con: sqlite3.Connection,
                    log: logging.Logger, cota: int) -> int:
    """Lista jogadores do BR1 de forma estratificada por elo."""
    novos = 0
    for elo in ELOS_COM_DIVISAO:
        while conta_jogadores(con, elo) < cota:
            rendeu = 0
            for divisao in DIVISOES:
                if conta_jogadores(con, elo) >= cota:
                    break
                pagina = proxima_pagina(con, elo, divisao)
                if pagina > PAGINAS_MAXIMAS:
                    continue
                puuids = riot_api.jogadores_por_divisao(
                    cliente, elo, divisao, pagina
                )
                if not puuids:
                    #divisao esgotada, nao insiste nela
                    marca_pagina(con, elo, divisao, PAGINAS_MAXIMAS + 1)
                    con.commit()
                    continue
                marca_pagina(con, elo, divisao, pagina + 1)
                random.shuffle(puuids)
                rendeu += guarda_jogadores(con, puuids, elo)
            if rendeu == 0:
                break
            novos += rendeu
        log.info(f"[sementes] {elo}: {conta_jogadores(con, elo)} jogadores")
    for elo in ELOS_APEX:
        if conta_jogadores(con, elo) >= cota:
            continue
        puuids = riot_api.jogadores_apex(cliente, elo)
        random.shuffle(puuids)
        novos += guarda_jogadores(con, puuids[:cota], elo)
        log.info(f"[sementes] {elo}: {conta_jogadores(con, elo)} jogadores")
    return novos


def busca_ids(cliente: ClienteRiot, con: sqlite3.Connection, semana: int,
              inicio: int, fim: int,
              quantos: int) -> tuple[int, int, int]:
    """Pede IDs de jogadores ainda nao consultados nesta semana.

    Devolve quantos foram consultados, quantos IDs novos renderam e quantos
    a chave de agora nao conseguiu decifrar.
    """
    linhas = con.execute(
        "SELECT puuid FROM jogadores WHERE puuid NOT IN "
        "(SELECT puuid FROM sementes_usadas WHERE semana = ?) "
        "ORDER BY RANDOM() LIMIT ?",
        (semana, quantos),
    ).fetchall()
    if not linhas:
        return 0, 0, 0
    novos = 0
    invalidos = 0
    for (puuid,) in linhas:
        try:
            ids = riot_api.ids_no_intervalo(cliente, puuid, inicio, fim)
        except riot_api.ErroDaRiot as erro:
            #esse jogador fica marcado como consultado e a semana segue.
            #o puuid sai da mensagem antes de ir para o log, e no lugar dele
            #fica o tamanho, que e o que distingue puuid global de id antigo
            #sem identificar ninguem.
            recado = str(erro).replace(puuid, "<puuid>")
            cliente.aviso(f"[erro] jogador pulado nesta semana: {recado} "
                          f"| puuid de {len(puuid)} caracteres")
            #"Exception decrypting" quer dizer que o puuid foi cifrado com
            #outra chave, e nao que o jogador sumiu
            if "decrypting" in recado.lower():
                invalidos += 1
            ids = []
        if ids:
            antes = con.total_changes
            con.executemany(
                "INSERT OR IGNORE INTO ids (match_id, semana, situacao) "
                "VALUES (?, ?, 'pendente')",
                [(match_id, semana) for match_id in ids],
            )
            novos += con.total_changes - antes
        con.execute(
            "INSERT OR IGNORE INTO sementes_usadas (puuid, semana) "
            "VALUES (?, ?)",
            (puuid, semana),
        )
    con.commit()
    return len(linhas), novos, invalidos


def resemeia(cliente: ClienteRiot, con: sqlite3.Connection,
             log: logging.Logger) -> int:
    """Refaz as sementes com puuids que a chave de agora decifra."""
    #o puuid que a league-v4 devolve vem cifrado com a chave que o pediu, e a
    #chave de desenvolvimento vira a cada 24 horas. depois de uma troca a
    #Riot responde 400 "Exception decrypting" para todo puuid guardado, a
    #coleta deixa de achar ID novo e o periodo congela. foi isso que parou a
    #coleta em 23/11 as 14:52. os match_id ja guardados nao sao cifrados e
    #continuam valendo, entao aqui so as sementes sao refeitas.
    antes = con.execute("SELECT COUNT(*) FROM jogadores").fetchone()[0]
    con.execute("DELETE FROM jogadores")
    #as duas tabelas abaixo guardam puuid antigo, que nunca mais volta pela
    #API: deixar as linhas la so engana a conta de jogador ja consultado
    con.execute("DELETE FROM sementes_usadas")
    con.execute("DELETE FROM paginas")
    guarda(con, "cota_sementes", JOGADORES_POR_ELO)
    con.commit()
    log.info(f"[sementes] a chave de agora nao decifra os {antes} puuids "
             "guardados, refazendo as sementes do zero")
    novos = amplia_sementes(cliente, con, log, JOGADORES_POR_ELO)
    log.info(f"[sementes] {novos} jogadores novos com a chave de agora")
    return novos


def garante_estoque(cliente: ClienteRiot, con: sqlite3.Connection,
                    log: logging.Logger, semana: int, inicio: int, fim: int,
                    alvo: int, estado: dict) -> None:
    secas = 0
    while conta_ids(con, semana, "pendente") < alvo:
        if hora_de_parar(estado):
            return
        consultados, novos, invalidos = busca_ids(
            cliente, con, semana, inicio, fim, LOTE_DE_JOGADORES
        )
        if consultados and invalidos == consultados:
            #nenhum dos consultados foi decifrado: isso e chave trocada, e
            #nao jogador ruim. buscar mais semente antiga nao resolveria
            if estado.get("resemeadas", 0) >= 3:
                log.info("[sementes] ja refiz as sementes 3 vezes nesta "
                         "execucao e a Riot continua recusando os puuids. "
                         "paro de insistir nesta semana.")
                return
            estado["resemeadas"] = estado.get("resemeadas", 0) + 1
            resemeia(cliente, con, log)
            continue
        if consultados == 0:
            #acabaram os jogadores nao consultados, busca mais na API
            cota = int(valor(con, "cota_sementes", str(JOGADORES_POR_ELO)))
            cota += JOGADORES_POR_ELO
            guarda(con, "cota_sementes", cota)
            log.info(f"[sementes] semana {semana} sem jogadores novos, "
                     f"ampliando a cota para {cota} por elo")
            if amplia_sementes(cliente, con, log, cota) == 0:
                log.info(f"[sementes] a API nao oferece mais jogadores. "
                         f"semana {semana} segue com "
                         f"{conta_ids(con, semana, 'pendente')} IDs pendentes.")
                return
            continue
        if novos == 0:
            secas += 1
            if secas >= 4:
                #esses jogadores nao rendem mais IDs novos nesta semana
                return
        else:
            secas = 0


def resumo_da_partida(dados: dict) -> dict:
    info = dados.get("info", {})
    metadados = dados.get("metadata", {})
    campeoes = [
        (participante.get("championName") or "")
        for participante in info.get("participants", [])
    ]
    return {
        "matchId": metadados.get("matchId", ""),
        "gameCreation": info.get("gameCreation", 0),
        "gameVersion": info.get("gameVersion", ""),
        "queueId": info.get("queueId", -1),
        "champions": campeoes,
    }


def formata_duracao(segundos: float) -> str:
    if segundos <= 0:
        return "0min"
    minutos = int(segundos // 60)
    if minutos < 60:
        return f"{minutos}min"
    return f"{minutos // 60}h{minutos % 60:02d}"


def proporcional(quantidade: int, inicio: date, fim: date) -> int:
    #fim e exclusivo, entao (fim - inicio).days ja e o numero de dias
    dias = (fim - inicio).days
    if not META_PROPORCIONAL_AOS_DIAS or dias >= 7:
        return quantidade
    return max(1, round(quantidade * dias / 7))


def meta_da_semana(meta: int, inicio: date, fim: date) -> int:
    return proporcional(meta, inicio, fim)


def taxa_por_segundo(estado: dict) -> float:
    """Partidas por segundo nos ultimos JANELA_DA_TAXA segundos."""
    agora = time.monotonic()
    marcas = estado["marcas"]
    while marcas and agora - marcas[0] >= JANELA_DA_TAXA:
        marcas.popleft()
    if len(marcas) < 2:
        return 0.0
    decorrido = agora - marcas[0]
    if decorrido <= 0:
        return 0.0
    return len(marcas) / decorrido


def hora_de_parar(estado: dict) -> bool:
    if estado["parar"]:
        return True
    if PARAR_EM and datetime.now(FUSO) >= PARAR_EM:
        estado["parar"] = True
        estado["parou_na_hora"] = True
        return True
    if estado["limite"] and time.monotonic() >= estado["limite"]:
        estado["parar"] = True
        return True
    return False


def linha_de_progresso(log: logging.Logger, cliente: ClienteRiot,
                       con: sqlite3.Connection, estado: dict,
                       metas: list[int], passada: int) -> None:
    por_semana = [conta_ids(con, i, "baixado")
                  for i in range(1, len(metas) + 1)]
    total = sum(por_semana)
    faltam = sum(max(0, meta - n) for meta, n in zip(metas, por_semana))
    taxa = taxa_por_segundo(estado)
    estimativa = formata_duracao(faltam / taxa) if taxa > 0 else "?"
    log.info(
        f"[progresso] passada {passada}/{len(METAS_POR_PASSADA)} | "
        f"baixadas {total} de {sum(metas)} | "
        f"por semana {'/'.join(str(n) for n in por_semana)} | "
        f"req na ultima hora {cliente.requisicoes_na_ultima_hora()} | "
        f"faltam ~{estimativa}"
    )


def baixa_lote(cliente: ClienteRiot, con: sqlite3.Connection,
               log: logging.Logger, arquivo, semana: int, quantas: int,
               estado: dict, metas: list[int], passada: int) -> int:
    linhas = con.execute(
        "SELECT match_id FROM ids WHERE semana = ? AND situacao = 'pendente' "
        "ORDER BY RANDOM() LIMIT ?",
        (semana, quantas),
    ).fetchall()
    feitas = 0
    for (match_id,) in linhas:
        if hora_de_parar(estado):
            break
        try:
            dados = riot_api.partida(cliente, match_id)
        except riot_api.ErroDaRiot as erro:
            #a partida fica como erro e a proxima execucao tenta de novo
            log.info(f"[erro] partida fica para depois: {erro}")
            con.execute(
                "UPDATE ids SET situacao = 'erro', erro = ? "
                "WHERE match_id = ?", (str(erro)[:200], match_id)
            )
            continue
        if dados is None:
            #404 nao volta a existir, entao nao tenta de novo nunca
            con.execute(
                "UPDATE ids SET situacao = 'ausente', erro = '404' "
                "WHERE match_id = ?", (match_id,)
            )
            continue
        resumo = resumo_da_partida(dados)
        if resumo["queueId"] != FILA_RANQUEADA:
            con.execute("UPDATE ids SET situacao = 'fora' WHERE match_id = ?",
                        (match_id,))
            continue
        #primeiro o arquivo, depois o banco: uma queda repete a linha em vez
        #de perder a partida, e o agregar.py despreza matchId repetido
        arquivo.write(json.dumps(resumo, ensure_ascii=False) + "\n")
        arquivo.flush()
        con.execute("UPDATE ids SET situacao = 'baixado' WHERE match_id = ?",
                    (match_id,))
        feitas += 1
        estado["baixadas"] += 1
        estado["marcas"].append(time.monotonic())
        if estado["baixadas"] % estado["cada"] == 0:
            con.commit()
            linha_de_progresso(log, cliente, con, estado, metas, passada)
    con.commit()
    return feitas


def coleta(cliente: ClienteRiot, con: sqlite3.Connection,
           log: logging.Logger, arquivo, janelas: list[tuple[date, date]],
           estado: dict) -> None:
    quantas_semanas = len(janelas)
    primeira = int(valor(con, "passada", "1"))
    for passada, base in enumerate(METAS_POR_PASSADA, start=1):
        if passada < primeira:
            continue
        metas = [meta_da_semana(base, inicio, fim) for inicio, fim in janelas]
        guarda(con, "passada", passada)
        log.info(f"passada {passada}: meta de {base} partidas por semana "
                 f"cheia, {sum(metas)} no periodo todo")
        while not hora_de_parar(estado):
            trabalhou = False
            #numa volta, so a semana atrasada recebe. ordenar por atraso
            #nao basta: o laco passava por todas de qualquer jeito e dava
            #um lote para cada, entao a diferenca entre a semana nova e a
            #antiga nunca fechava. aqui a semana que ja esta na frente fica
            #de fora da volta ate as outras alcancarem.
            #a comparacao e por partida POR DIA, nao por total da semana.
            #a primeira semana tem 6 dias e a ultima tem 3, entao igualar
            #o total deixaria a de 3 dias com o dobro da densidade das de
            #7, bem na borda onde ainda ha evento para medir.
            por_dia = {}
            for i, (comeco, fim) in enumerate(janelas, start=1):
                por_dia[i] = conta_ids(con, i, "baixado") / (fim - comeco).days
            menor = min(por_dia.values())
            teto_da_volta = menor + LOTE_POR_SEMANA * 2 / 7
            ordem = sorted(enumerate(janelas, start=1),
                           key=lambda par: por_dia[par[0]])
            for indice, (inicio_dia, fim_dia) in ordem:
                if por_dia[indice] > teto_da_volta:
                    continue
                if hora_de_parar(estado):
                    break
                meta = metas[indice - 1]
                baixadas = conta_ids(con, indice, "baixado")
                if baixadas >= meta:
                    continue
                guarda(con, "semana", indice)
                inicio = epoch(inicio_dia)
                fim = epoch(fim_dia)
                alvo = min(ESTOQUE_MINIMO, meta - baixadas)
                if conta_ids(con, indice, "pendente") < alvo:
                    garante_estoque(cliente, con, log, indice, inicio, fim,
                                    alvo, estado)
                pendentes = conta_ids(con, indice, "pendente")
                #o lote tambem cai nas janelas de 3 dias, senao elas ficariam
                #mais densas por dia que as de 7 durante a coleta, e nao so
                #no fim dela
                lote = proporcional(LOTE_POR_SEMANA, inicio_dia, fim_dia)
                quantas = min(lote, meta - baixadas, pendentes)
                if quantas <= 0:
                    continue
                if baixa_lote(cliente, con, log, arquivo, indice, quantas,
                              estado, metas, passada) > 0:
                    trabalhou = True
            if not trabalhou:
                break
        if hora_de_parar(estado):
            return
        #o laco acima tambem sai quando nenhuma semana tem ID para baixar,
        #nao so quando todas batem a meta. os dois casos sao diferentes e o
        #log precisa dizer qual foi, senao um fim por falta de ID passa por
        #passada completa.
        abaixo = [i for i, meta in enumerate(metas, start=1)
                  if conta_ids(con, i, "baixado") < meta]
        if abaixo:
            log.info(f"passada {passada} parou com {len(abaixo)} de "
                     f"{quantas_semanas} semanas abaixo da meta. nao foi a "
                     "meta que fechou, foi o ID que acabou.")
        else:
            log.info(f"passada {passada} encerrada com todas as "
                     f"{quantas_semanas} semanas na meta.")
        limite = estado.get("ate_passada") or 0
        if limite and passada >= limite:
            como = "incompleta" if abaixo else "redonda"
            log.info(f"a passada {limite} terminou {como} e era ate aqui. "
                     "encerrando.")
            estado["parar"] = True
            return


def main() -> int:
    analisador = argparse.ArgumentParser(description="Coletor de partidas BR1")
    analisador.add_argument("--minutos", type=float, default=0,
                            help="para sozinho depois de N minutos")
    analisador.add_argument("--cada", type=int, default=PROGRESSO_CADA,
                            help="intervalo da linha de progresso")
    analisador.add_argument("--ate-passada", type=int,
                            default=PARAR_NA_PASSADA,
                            help="encerra ao fechar esta passada. 0 vai ate "
                                 "o fim das tres")
    argumentos = analisador.parse_args()

    random.seed(SEMENTE_SORTEIO)
    log = prepara_log()
    #a trava vem antes de tudo, para o segundo coletor sair com recado em
    #vez de traceback de banco travado
    trava = trava_instancia_unica(log)
    con = abre_banco()
    cliente = ClienteRiot(aviso=log.info)

    janelas = janelas_semanais(DATA_INICIAL, DATA_FINAL)
    registra_semanas(con, janelas)
    log.info(f"periodo {DATA_INICIAL} a {DATA_FINAL}, "
             f"{len(janelas)} semanas, fila {FILA_RANQUEADA}")
    log.info(f"banco {BANCO}")
    log.info(f"partidas {PARTIDAS}")
    log.info("Ctrl+C encerra sem corromper o arquivo.")

    #o que deu erro numa execucao anterior volta para a fila. o 404 fica como
    #ausente e nao volta, porque partida apagada nao reaparece.
    reenfileirados = con.execute(
        "UPDATE ids SET situacao = 'pendente', erro = NULL "
        "WHERE situacao = 'erro'"
    ).rowcount
    con.commit()
    if reenfileirados:
        log.info(f"{reenfileirados} IDs com erro voltaram para a fila")

    cota = int(valor(con, "cota_sementes", str(JOGADORES_POR_ELO)))
    if conta_jogadores(con) == 0:
        log.info(f"listando sementes, meta de {cota} jogadores por elo")
        amplia_sementes(cliente, con, log, cota)
    log.info(f"sementes no banco: {conta_jogadores(con)} jogadores")

    PARTIDAS.parent.mkdir(parents=True, exist_ok=True)
    estado = {
        "inicio": time.monotonic(),
        "baixadas": 0,
        "cada": max(1, argumentos.cada),
        "marcas": deque(),
        "ate_passada": argumentos.ate_passada,
        "parar": False,
        "limite": (time.monotonic() + argumentos.minutos * 60
                   if argumentos.minutos > 0 else None),
    }

    if PARAR_EM:
        log.info(f"esta coleta encerra em {PARAR_EM:%d/%m as %Hh%M}, ou "
                 f"antes se a passada {argumentos.ate_passada} fechar")

    arquivo = open(PARTIDAS, "a", encoding="utf-8")
    codigo_de_saida = 0
    try:
        coleta(cliente, con, log, arquivo, janelas, estado)
    except KeyboardInterrupt:
        log.info("Ctrl+C recebido, encerrando com o arquivo fechado.")
    except Exception:
        #sem isto o traceback ia somente para a tela da janela: a coleta de
        #23/11 morreu as 14:52 e o log nao guardou o motivo, so o fim da
        #rodada. o log e o que sobra depois que a janela fecha.
        log.exception("a coleta parou por erro nao previsto")
        codigo_de_saida = 1
    finally:
        arquivo.flush()
        arquivo.close()
        con.commit()
        baixadas = sum(conta_ids(con, i, "baixado")
                       for i in range(1, len(janelas) + 1))
        if estado.get("parou_na_hora"):
            log.info(f"chegou a hora marcada, {PARAR_EM:%d/%m %Hh%M}. "
                     "encerrando com o periodo parelho.")
        log.info(f"fim desta rodada: {estado['baixadas']} partidas nesta "
                 f"execucao, {baixadas} no total, "
                 f"{cliente.requisicoes} requisicoes.")
        con.close()
        trava.close()
    return codigo_de_saida


if __name__ == "__main__":
    sys.exit(main())
