r"""
Escreve o resultado da analise como CSV, uma linha por campeao por evento.

A analise entrega relatorio em texto e grafico em HTML, que servem para ler
e nao para o painel consumir. A tabela em si vem de coleta/resultados.py,
que chama as proprias funcoes de analise/efeito_vitrine.py, entao os numeros
daqui sao os mesmos do relatorio e os mesmos do JSON do painel, sem conta
repetida em outro lugar para divergir depois.

Rodar:  .venv\Scripts\python.exe entrega\gerar_csv_resultados.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "coleta"))

from resultados import COLUNAS, monta_linhas, para_csv  # noqa: E402

SAIDA = AQUI / "dados" / "resultados_por_campeao_evento.csv"


def main() -> int:
    linhas, resumo = monta_linhas()

    parcial = SAIDA.with_suffix(".parcial")
    with open(parcial, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(para_csv(l) for l in linhas)
    parcial.replace(SAIDA)

    print(f"{SAIDA.relative_to(RAIZ)}: {resumo['pares']} linhas")
    print(f"  {resumo['eventos']} eventos | {resumo['destaques']} destaques | "
          f"{resumo['cruzam']} com intervalos se cruzando | "
          f"{resumo['poucas']} com menos de {resumo['picks_minimos']} "
          "escolhas no antes")
    if resumo["sem_medida"]:
        print(f"  {resumo['sem_medida']} pares sem medida, por janela curta "
              "na borda do periodo ou campeao sem escolha no antes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
