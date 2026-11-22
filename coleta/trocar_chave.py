"""
Troca a chave da Riot no .env e confere se ela funciona.

Existe por causa de uma pegadinha que custou uma pausa na coleta: chave
recem gerada no portal da Riot leva alguns segundos para valer, e nesse
intervalo ela responde 401. Quem testa na hora ve "recusada", acha que
copiou errado e volta para a anterior, que a geracao da nova ja invalidou.
Resultado: duas chaves mortas e a coleta parada.

Por isso aqui ele tenta varias vezes com espera antes de desistir, e so
grava depois de a chave responder.

O valor nunca e impresso, nem em caso de erro. Ele entra por argumento,
entao fica no historico do terminal: rode de um terminal que voce nao se
importe, ou cole o valor direto no .env, que funciona igual.

Rodar:  .venv\\Scripts\\python.exe coleta\\trocar_chave.py RGAPI-...
"""
from __future__ import annotations

import sys
import time

import requests
from dotenv import dotenv_values

from config import ARQUIVO_ENV, PLATAFORMA

VARIAVEL = "RIOT_API_KEY"
TESTE = f"{PLATAFORMA}/lol/status/v4/platform-data"
TENTATIVAS = 6
ESPERA = 10


def testa(chave: str) -> int:
    try:
        resposta = requests.get(
            TESTE, headers={"X-Riot-Token": chave}, timeout=20
        )
    except requests.RequestException as erro:
        print(f"[rede] {erro.__class__.__name__}")
        return 0
    return resposta.status_code


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: trocar_chave.py RGAPI-...")
        return 1
    nova = sys.argv[1].strip()
    if not nova.startswith("RGAPI-") or len(nova) != 42:
        print(f"[erro] isso nao parece uma chave: {len(nova)} caracteres, "
              "esperado 42 comecando em RGAPI-")
        return 1

    print(f"testando a chave antes de gravar, ate {TENTATIVAS} vezes com "
          f"{ESPERA}s de espera")
    for tentativa in range(1, TENTATIVAS + 1):
        codigo = testa(nova)
        if codigo == 200:
            print(f"  tentativa {tentativa}: HTTP 200, chave boa")
            break
        print(f"  tentativa {tentativa}: HTTP {codigo}, esperando {ESPERA}s")
        if tentativa < TENTATIVAS:
            time.sleep(ESPERA)
    else:
        print("")
        print("[erro] a chave nao passou a valer. NADA foi gravado, entao a "
              "chave que estava no .env continua la.")
        print("confira se copiou inteira do portal, sem espaco no fim.")
        return 2

    linhas = ARQUIVO_ENV.read_text(encoding="utf-8").splitlines()
    saida = []
    achou = False
    for linha in linhas:
        if linha.startswith(VARIAVEL + "="):
            saida.append(f"{VARIAVEL}={nova}")
            achou = True
        else:
            saida.append(linha)
    if not achou:
        saida.append(f"{VARIAVEL}={nova}")
    ARQUIVO_ENV.write_text("\n".join(saida) + "\n", encoding="utf-8")

    valores = dotenv_values(ARQUIVO_ENV)
    relido = (valores.get(VARIAVEL) or "").strip()
    outra = (valores.get("YOUTUBE_API_KEY") or "").strip()
    print("")
    print(f"gravada no .env: {len(relido)} caracteres, "
          f"igual ao passado: {relido == nova}")
    print(f"YOUTUBE_API_KEY intacta: {len(outra)} caracteres")
    print("")
    print("o coletor rele o .env a cada 60 segundos e retoma sozinho, "
          "sem reiniciar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
