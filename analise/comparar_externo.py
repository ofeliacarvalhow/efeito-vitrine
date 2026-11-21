"""Compara a nossa taxa de escolha com a do op.gg para o BR."""
import collections
import csv
from pathlib import Path

RAIZ = Path(r"C:\Users\Lenovo\Documents\efeito-vitrine")

#op.gg, BR, patch 16.23, todos os elos, somando as linhas por funcao
OPGG = {
    "Lux": 18.09, "Caitlyn": 17.82, "Kaisa": 16.61, "Ezreal": 16.09,
    "Yone": 15.29, "Jhin": 14.88, "MissFortune": 13.45, "Kayn": 13.41,
    "Yasuo": 12.44, "Jinx": 11.84, "Seraphine": 11.38, "Ahri": 11.21,
    "Nami": 11.09, "Lulu": 10.97, "Ashe": 10.73, "Thresh": 9.58,
}

picks = collections.Counter()
jogos = {}
with open(RAIZ / "data" / "processed" / "daily_pickrate.csv",
          encoding="utf-8") as arquivo:
    for linha in csv.DictReader(arquivo):
        picks[linha["champion"]] += int(linha["picks"])
        jogos[linha["date"]] = int(linha["games_total"])
total = sum(jogos.values())
nosso = {c: 100 * n / total for c, n in picks.items()}

comuns = [c for c in OPGG if c in nosso]
print(f"campeoes comparaveis: {len(comuns)} de {len(OPGG)}")
print("")
print(f"  {'campeao':14s} {'nosso':>7s} {'op.gg':>7s} {'razao':>6s}")
for campeao in sorted(comuns, key=lambda c: -OPGG[c]):
    razao = nosso[campeao] / OPGG[campeao]
    print(f"  {campeao:14s} {nosso[campeao]:6.2f}% {OPGG[campeao]:6.2f}% "
          f"{razao:5.2f}")

#correlacao de postos, sem scipy
def postos(valores):
    ordenado = sorted(range(len(valores)), key=lambda i: valores[i])
    r = [0.0] * len(valores)
    for posicao, i in enumerate(ordenado):
        r[i] = posicao + 1
    return r


a = [nosso[c] for c in comuns]
b = [OPGG[c] for c in comuns]
ra, rb = postos(a), postos(b)
n = len(comuns)
soma = sum((ra[i] - rb[i]) ** 2 for i in range(n))
spearman = 1 - 6 * soma / (n * (n * n - 1))
media_razao = sum(nosso[c] / OPGG[c] for c in comuns) / n
print("")
print(f"correlacao de postos (Spearman): {spearman:.2f}")
print(f"razao media nosso/op.gg: {media_razao:.2f}")
print(f"nossa soma nos comuns: {sum(a):.1f}%  op.gg: {sum(b):.1f}%")
