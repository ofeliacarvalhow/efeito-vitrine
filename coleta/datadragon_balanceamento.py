"""
Campeoes mexidos em cada patch, pelo Data Dragon.

Compara os arquivos de campeao de uma versao com os da versao anterior e
anota quem teve numero alterado. Olha os 20 atributos de stats, o cooldown,
o cost e o effect dos 4 feiticos, e o nome do passivo. O resultado vai para
data/processed/balance_changes.csv, uma linha por campeao que mudou em cada
patch.

A coluna change diz QUAL numero mudou e para quanto. Nao diz buff nem nerf,
porque a direcao do numero nao revela isso: custo menor e buff, dano menor e
nerf. Quem usa o arquivo precisa saber quem foi mexido e em que patch, e e
isso que ele entrega.

Texto nao conta como mudanca de balanceamento, entao description, blurb,
lore, allytips e enemytips ficam de fora. A lista de skins tambem, que tem
script proprio no datadragon_skins.py.

Nao baixa nada: le o cache que a coleta ja encheu, so para leitura. O 16.16
entra apenas como base de comparacao do 16.17 e nao gera linha propria.

Rodar:  .venv\\Scripts\\python.exe coleta/datadragon_balanceamento.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from config import PATCH_BASE, PATCHES, RAIZ

#o cache mora no computador da Pessoa 1, fora do Git
CACHE_PADRAO = Path(
    r"C:\Users\Lenovo\Documents\efeito-vitrine\data\cache_ddragon"
)

SAIDA = RAIZ / "data" / "processed" / "balance_changes.csv"
DATAS = RAIZ / "data" / "processed" / "patch_dates.csv"

#quantas mudancas cabem na coluna change antes de virar contagem
LIMITE_DE_MUDANCAS = 6

#os 4 feiticos saem na ordem Q, W, E, R
TECLAS = ["Q", "W", "E", "R"]


def numero(valor) -> str:
    """Numero em texto curto, sem o .0 que o JSON inventa."""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def lista_curta(valores) -> str:
    """Valor por nivel em texto. Um valor so quando todos sao iguais."""
    if not isinstance(valores, list):
        return numero(valores)
    limpos = [v for v in valores if v is not None]
    if not limpos:
        return "-"
    if len(set(numero(v) for v in limpos)) == 1:
        return numero(limpos[0])
    return "/".join(numero(v) for v in limpos)


def tudo_zero(efeito) -> bool:
    """True quando o effect vem sem valor nenhum.

    O Data Dragon as vezes para de exportar os numeros de um feitico e manda
    a matriz toda zerada, com o valor so no tooltip. Isso aparece como
    mudanca enorme sem patch nenhum por tras, entao nao conta.
    """
    if not efeito:
        return True
    for linha in efeito:
        if not linha:
            continue
        if any(v not in (0, None) for v in linha):
            return False
    return True


def le_campeoes(pasta: Path) -> dict[str, dict]:
    """{identificador: dados do campeao} de um build do cache."""
    campeoes: dict[str, dict] = {}
    for arquivo in sorted(pasta.glob("*.json")):
        if arquivo.name == "champion.json":
            continue
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as erro:
            print(f"[aviso] {arquivo.name} ilegivel em {pasta.name}: {erro}")
            continue
        for identificador, detalhe in (dados.get("data") or {}).items():
            campeoes[identificador] = detalhe
    return campeoes


def build_do_patch(cache: Path, patch: str) -> Path | None:
    """A pasta do build mais novo daquele patch, dentro do cache."""
    candidatos = [
        p for p in cache.iterdir()
        if p.is_dir() and (p.name == patch or p.name.startswith(patch + "."))
    ]
    if not candidatos:
        return None
    #16.17.2 ganha de 16.17.1: o build mais novo e o que valeu no patch
    return max(
        candidatos,
        key=lambda p: [int(n) for n in p.name.split(".") if n.isdigit()],
    )


def diferencas_de_efeito(tecla: str, velho, novo) -> list[str]:
    """As faixas de effect que mudaram num feitico."""
    velho = velho or []
    novo = novo or []
    achados: list[str] = []
    for faixa in range(max(len(velho), len(novo))):
        a = velho[faixa] if faixa < len(velho) else None
        b = novo[faixa] if faixa < len(novo) else None
        if a == b:
            continue
        achados.append(
            f"{tecla} efeito {faixa} {lista_curta(a)} para {lista_curta(b)}"
        )
    return achados


def mudancas_do_campeao(antes: dict, agora: dict) -> list[str]:
    """Lista de mudancas de numero de um campeao entre dois patches."""
    achados: list[str] = []

    stats_antes = antes.get("stats") or {}
    stats_agora = agora.get("stats") or {}
    for atributo in sorted(stats_agora):
        if atributo not in stats_antes:
            continue
        velho = stats_antes[atributo]
        novo = stats_agora[atributo]
        if velho == novo:
            continue
        achados.append(f"{atributo} {numero(velho)} para {numero(novo)}")

    feiticos_antes = antes.get("spells") or []
    feiticos_agora = agora.get("spells") or []
    for indice, feitico in enumerate(feiticos_agora):
        tecla = TECLAS[indice] if indice < len(TECLAS) else f"F{indice + 1}"
        if indice >= len(feiticos_antes):
            achados.append(f"{tecla} feitico novo")
            continue
        velho_feitico = feiticos_antes[indice]
        for campo, nome in (("cooldown", "cooldown"), ("cost", "custo")):
            velho = velho_feitico.get(campo)
            novo = feitico.get(campo)
            if velho == novo:
                continue
            achados.append(
                f"{tecla} {nome} {lista_curta(velho)} para {lista_curta(novo)}"
            )
        velho_efeito = velho_feitico.get("effect")
        novo_efeito = feitico.get("effect")
        if velho_efeito == novo_efeito:
            continue
        if tudo_zero(velho_efeito) != tudo_zero(novo_efeito):
            #o Data Dragon ligou ou desligou a exportacao desse feitico
            continue
        achados.extend(diferencas_de_efeito(tecla, velho_efeito, novo_efeito))

    nome_antes = (antes.get("passive") or {}).get("name")
    nome_agora = (agora.get("passive") or {}).get("name")
    if nome_antes and nome_agora and nome_antes != nome_agora:
        achados.append(f"passivo virou {nome_agora}")

    return achados


def resume(achados: list[str]) -> str:
    """As mudancas em uma linha, cortadas quando sao muitas."""
    if len(achados) <= LIMITE_DE_MUDANCAS:
        return "; ".join(achados)
    sobraram = len(achados) - LIMITE_DE_MUDANCAS
    inicio = "; ".join(achados[:LIMITE_DE_MUDANCAS])
    return f"{inicio}; e mais {sobraram} mudanca(s)"


def le_datas() -> dict[str, str]:
    """{patch: patch_date} do patch_dates.csv."""
    if not DATAS.exists():
        return {}
    datas: dict[str, str] = {}
    with open(DATAS, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            patch = (linha.get("patch") or "").strip()
            if patch:
                datas[patch] = (linha.get("patch_date") or "").strip()
    return datas


def escreve_csv(linhas: list[tuple[str, str, str, str]]) -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    parcial = SAIDA.parent / (SAIDA.name + ".parcial")
    with open(parcial, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["patch", "patch_date", "champion", "change"])
        for linha in linhas:
            escritor.writerow(linha)
    os.replace(parcial, SAIDA)


def main() -> int:
    argumentos = argparse.ArgumentParser(
        description="compara builds do Data Dragon e lista quem foi mexido"
    )
    argumentos.add_argument("--cache", type=Path, default=CACHE_PADRAO,
                            help="pasta do cache do Data Dragon, so leitura")
    opcoes = argumentos.parse_args()
    cache: Path = opcoes.cache

    if not cache.is_dir():
        print(f"[erro] o cache {cache} nao existe.")
        return 1

    datas = le_datas()
    if not datas:
        print(f"[erro] {DATAS.name} nao existe ou veio vazio.")
        return 1

    pedidos = [PATCH_BASE] + list(PATCHES)
    por_patch: dict[str, dict[str, dict]] = {}
    for patch in pedidos:
        pasta = build_do_patch(cache, patch)
        if pasta is None:
            print(f"[erro] o patch {patch} nao esta no cache {cache}.")
            return 1
        campeoes = le_campeoes(pasta)
        if not campeoes:
            print(f"[erro] a pasta {pasta.name} nao tem campeao nenhum.")
            return 1
        por_patch[patch] = campeoes
        print(f"{patch} (build {pasta.name}): {len(campeoes)} campeoes")

    print("")
    linhas: list[tuple[str, str, str, str]] = []
    contagem: list[tuple[str, int]] = []
    anterior = por_patch[PATCH_BASE]
    for patch in PATCHES:
        agora = por_patch[patch]
        data = datas.get(patch, "")
        if not data:
            print(f"[aviso] o patch {patch} nao tem data no {DATAS.name}.")
        novos = sorted(set(agora) - set(anterior))
        do_patch = 0
        for campeao in sorted(agora):
            if campeao not in anterior:
                continue
            achados = mudancas_do_campeao(anterior[campeao], agora[campeao])
            if not achados:
                continue
            linhas.append((patch, data, campeao, resume(achados)))
            do_patch += 1
        contagem.append((patch, do_patch))
        recado = f"{patch} ({data}): {do_patch} campeoes mexidos"
        if novos:
            recado += f", campeao novo {', '.join(novos)}"
        print(recado)
        anterior = agora

    escreve_csv(linhas)
    distintos = {linha[2] for linha in linhas}
    print("")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(linhas)} linhas, "
          f"{len(distintos)} campeoes distintos")
    menor = min(n for _, n in contagem)
    maior = max(n for _, n in contagem)
    print(f"campeoes mexidos por patch: de {menor} a {maior}")
    if menor == 0 or maior > 60:
        print("[aviso] essa contagem esta fora do que um patch costuma "
              "mexer, entre 5 e 25 campeoes. vale conferir o comparador.")
    print("")
    print(f"comparacao: {PATCH_BASE} entrou so como base do {PATCHES[0]} "
          "e nao gera linha propria.")
    print("a coluna change nao diz buff nem nerf. custo menor e buff e dano "
          "menor e nerf, entao a direcao do numero nao resolve sozinha.")
    print("ATENCAO para a analise de antes e depois: campeao que aparece "
          "aqui no mesmo patch de uma skin tem duas causas possiveis, e o "
          "efeito da vitrine nao pode ser separado do balanceamento ali.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("")
        print("interrompido pelo teclado.")
        sys.exit(130)
