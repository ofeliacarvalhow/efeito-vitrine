"""
Skins novas por versao, pelo Data Dragon.

Baixa a lista de versoes, pega os patches do periodo, le as skins de cada
campeao em cada patch e compara com o patch anterior. O resultado vai para
data/processed/new_skins.csv.

O Data Dragon sai dias depois do patch, entao a coluna version diz QUAL patch
trouxe a skin, nao QUANDO ela saiu. A data oficial de cada patch vem de outra
fonte e quem preenche e a Pessoa 3, em data/processed/balance_changes.csv.

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


def versao_do_patch(versoes: list[str], patch: str) -> str | None:
    #versions.json vem da mais nova para a mais velha, entao a primeira que
    #casar com o patch e o build mais novo dele
    for versao in versoes:
        if versao == patch or versao.startswith(patch + "."):
            return versao
    return None


def skins_da_versao(sessao: requests.Session,
                    versao: str) -> dict[str, dict[int, str]] | None:
    """{campeao: {numero: nome}} de uma versao. Pula a skin 0, a padrao."""
    pasta = CACHE_DDRAGON / versao
    lista = baixa_json(
        sessao,
        f"{DDRAGON}/{versao}/data/{IDIOMA_DDRAGON}/champion.json",
        pasta / "champion.json",
    )
    if lista is None:
        return None
    identificadores = sorted((lista.get("data") or {}).keys())
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
            #a skin 0 e a aparencia padrao, nao e lancamento
            if numero > 0:
                do_campeao[numero] = skin.get("name") or ""
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
            for numero in sorted(atual[campeao]):
                if antes is None or numero not in antes:
                    do_patch.append(
                        (patch, campeao, numero, atual[campeao][numero])
                    )
        novas.extend(do_patch)
        recado = f"{patch}: {len(do_patch)} skins novas"
        if campeoes_novos:
            recado += f", campeao novo {', '.join(campeoes_novos)}"
        print(recado)
        anterior = atual

    escreve_csv(novas)
    print("")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(novas)} linhas")
    print(f"comparacao: {PATCH_BASE} entrou so como base do {PATCHES[0]} "
          "e nao gera linha propria.")
    print("a coluna version diz qual patch trouxe a skin. a data oficial do "
          "patch vem de outra fonte, que a Pessoa 3 preenche.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
