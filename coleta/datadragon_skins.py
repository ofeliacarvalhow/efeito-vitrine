"""
Skins novas por versao, pelo Data Dragon.

Baixa a lista de versoes, pega os patches do periodo, le as skins de cada
campeao em cada patch e compara com o patch anterior. O resultado vai para
data/processed/new_skins.csv.

O Data Dragon sai dias depois do patch, entao a coluna version diz QUAL patch
trouxe a skin, nao QUANDO ela saiu. A data oficial de cada patch vem de outra
fonte e entra a mao em data/processed/balance_changes.csv.

O cache fica em data/cache_ddragon/, fora do Git. Rodar de novo com o cache
cheio nao faz requisicao nenhuma.

Rodar:  .venv/Scripts/python.exe coleta/datadragon_skins.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

import requests

from config import (
    CACHE_DDRAGON,
    DDRAGON,
    ESPERA_DDRAGON,
    IDIOMA_DDRAGON,
    PATCH_BASE,
    PATCHES,
    PATCHES_SUSPEITOS,
    RAIZ,
    VERSOES_DDRAGON,
)

SAIDA = RAIZ / "data" / "processed" / "new_skins.csv"


def baixa_json(sessao: requests.Session, url: str, cache: Path,
               tentativas: int = 4):
    """Devolve o JSON, do cache quando ja existe. None em 404.

    O Data Dragon derruba conexao de vez em quando numa sequencia longa de
    requisicoes, entao repete com espera crescente. O que ja esta em cache
    nao e pedido de novo, logo uma rodada interrompida retoma de onde parou.
    """
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            #cache truncado por alguma queda, baixa de novo
            cache.unlink()
    espera = 2
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = sessao.get(url, timeout=30)
        except requests.RequestException as erro:
            if tentativa == tentativas:
                raise RuntimeError(
                    f"{tentativas} falhas de rede em {url}: {erro}"
                )
            print(f"[rede] {erro.__class__.__name__}, tentativa {tentativa}, "
                  f"esperando {espera}s")
            time.sleep(espera)
            espera *= 2
            continue
        if resposta.status_code == 404:
            return None
        if 500 <= resposta.status_code < 600:
            if tentativa == tentativas:
                raise RuntimeError(f"HTTP {resposta.status_code} em {url}")
            print(f"[{resposta.status_code}] tentativa {tentativa}, "
                  f"esperando {espera}s")
            time.sleep(espera)
            espera *= 2
            continue
        resposta.raise_for_status()
        dados = resposta.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(dados, ensure_ascii=False),
                         encoding="utf-8")
        time.sleep(ESPERA_DDRAGON)
        return dados
    return None


def eh_croma(nome: str) -> bool:
    #croma vem como "Nome da Skin (Cor)", e nao e lancamento de skin nova
    return nome.endswith(")") and " (" in nome


def versao_do_patch(versoes: list[str], patch: str) -> str | None:
    #versions.json vem da mais nova para a mais velha, entao a primeira que
    #casar com o patch e o build mais novo dele
    for versao in versoes:
        if versao == patch or versao.startswith(patch + "."):
            return versao
    return None


def skins_da_versao(sessao: requests.Session,
                    versao: str) -> dict[str, dict[str, int]] | None:
    """{campeao: {nome: numero}} de uma versao. Pula a skin 0, a padrao.

    A chave e o NOME e nao o numero, porque numero nao e estavel: quando os
    cromas entraram na lista, no 16.6, as skins antigas foram renumeradas e
    62 delas apareceram como novas so por isso. Nome de skin nao muda.
    """
    pasta = CACHE_DDRAGON / versao
    lista = baixa_json(
        sessao,
        f"{DDRAGON}/{versao}/data/{IDIOMA_DDRAGON}/champion.json",
        pasta / "champion.json",
    )
    if lista is None:
        return None
    #o Data Dragon traz entradas que nao sao campeao do jogo normal. o patch
    #16.15 metou 60 delas com prefixo Jade_, que renderam 1464 skins falsas.
    #campeao de verdade nunca tem sublinhado no id: KSante, Kaisa, LeeSin,
    #MonkeyKing. filtrar por isso tira o lixo sem lista fixa para manter.
    identificadores = sorted(
        i for i in (lista.get("data") or {}).keys() if "_" not in i
    )
    descartados = len(lista.get("data") or {}) - len(identificadores)
    if descartados:
        print(f"  {versao}: {descartados} entradas com sublinhado no id "
              "descartadas, nao sao campeao do jogo")
    skins: dict[str, dict[int, str]] = {}
    for identificador in identificadores:
        dados = baixa_json(
            sessao,
            f"{DDRAGON}/{versao}/data/{IDIOMA_DDRAGON}/champion/"
            f"{identificador}.json",
            pasta / f"{identificador}.json",
        )
        if dados is None:
            continue
        detalhe = (dados.get("data") or {}).get(identificador) or {}
        do_campeao: dict[int, str] = {}
        for skin in detalhe.get("skins") or []:
            try:
                numero = int(skin.get("num", -1))
            except (TypeError, ValueError):
                continue
            nome = skin.get("name") or ""
            #a skin 0 e a aparencia padrao, nao e lancamento
            if numero <= 0:
                continue
            #croma fora daqui, nao so do resultado. o Data Dragon so comecou
            #a listar croma no 16.6: antes dele sao 11 skins por campeao e
            #depois sao 50. comparar as duas formas daria 6717 skins falsas
            #num patch so, que e mudanca de formato e nao lancamento.
            if eh_croma(nome):
                continue
            do_campeao[nome] = numero
        skins[identificador] = do_campeao
    return skins


def escreve_csv(novas: list[tuple[str, str, int, str]]) -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    parcial = SAIDA.parent / (SAIDA.name + ".parcial")
    with open(parcial, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["version", "champion", "skin_num", "skin_name"])
        for linha in novas:
            escritor.writerow(linha)
    os.replace(parcial, SAIDA)


def main() -> int:
    sessao = requests.Session()
    CACHE_DDRAGON.mkdir(parents=True, exist_ok=True)
    versoes = baixa_json(sessao, VERSOES_DDRAGON,
                         CACHE_DDRAGON / "versions.json")
    if not versoes:
        print("[erro] o Data Dragon nao devolveu a lista de versoes.")
        return 1

    pedidos = [PATCH_BASE] + list(PATCHES)
    por_patch: dict[str, dict[str, dict[int, str]]] = {}
    for patch in pedidos:
        versao = versao_do_patch(versoes, patch)
        if versao is None:
            print(f"[erro] o patch {patch} nao existe no versions.json.")
            return 1
        skins = skins_da_versao(sessao, versao)
        if skins is None:
            print(f"[erro] a versao {versao} nao tem champion.json.")
            return 1
        por_patch[patch] = skins
        total_skins = sum(len(s) for s in skins.values())
        print(f"{patch} (build {versao}): {len(skins)} campeoes, "
              f"{total_skins} skins")

    print("")
    novas: list[tuple[str, str, int, str]] = []
    anterior = por_patch[PATCH_BASE]
    for patch in PATCHES:
        atual = por_patch[patch]
        do_patch: list[tuple[str, str, int, str]] = []
        campeoes_novos = []
        for campeao in sorted(atual):
            antes = anterior.get(campeao)
            if antes is None:
                campeoes_novos.append(campeao)
            for nome in sorted(atual[campeao],
                               key=lambda n: atual[campeao][n]):
                if antes is None or nome not in antes:
                    do_patch.append(
                        (patch, campeao, atual[campeao][nome], nome)
                    )
        if patch in PATCHES_SUSPEITOS:
            print(f"{patch}: {len(do_patch)} diferencas DESCARTADAS, patch "
                  "marcado como fonte nao confiavel no config")
            anterior = atual
            continue
        novas.extend(do_patch)
        recado = f"{patch}: {len(do_patch)} skins novas"
        if campeoes_novos:
            recado += f", campeao novo {', '.join(campeoes_novos)}"
        print(recado)
        anterior = atual

    escreve_csv(novas)
    lancamentos = [linha for linha in novas if not eh_croma(linha[3])]
    cromas = len(novas) - len(lancamentos)
    campeoes = {linha[1] for linha in lancamentos}
    print("")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(novas)} linhas")
    print(f"  lancamentos de skin: {len(lancamentos)}, "
          f"em {len(campeoes)} campeoes")
    print(f"  cromas de skin que ja existia: {cromas}")
    print("")
    print(f"comparacao: {PATCH_BASE} entrou so como base do {PATCHES[0]} "
          "e nao gera linha propria.")
    print("a coluna version diz qual patch trouxe a skin. a data oficial do "
          "patch vem de outra fonte, preenchida a mao.")
    print("croma nao entra neste arquivo: ele e descartado na comparacao, "
          "nao so no resultado, porque o Data Dragon so comecou a listar "
          "croma no 16.6 e isso criaria 6717 skins falsas naquele patch.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
