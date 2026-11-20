"""
Gera data/mock/daily_pickrate.csv: dados FALSOS no formato do contrato de dados.

Serve para a Pessoa 2 (analise) e a Pessoa 3 (site) trabalharem sem esperar a
coleta real e sem nunca tocar em data/raw/.

Rodar:  .venv/bin/python coleta/gerar_mock.py
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "data" / "mock" / "daily_pickrate.csv"

DATA_INICIAL = date(2026, 9, 4)
DATA_FINAL = date(2026, 11, 18)
PARTIDAS_POR_DIA_BASE = 1000
SEMENTE = 20260904

# Nomes exatamente como aparecem no campo championName da Riot.
# Os 18 primeiros sao obrigatorios para a analise do Efeito Vitrine.
CAMPEOES_OBRIGATORIOS = [
    "Aphelios", "Ezreal", "Kayn", "KSante", "Sett", "Yone", "Janna", "Mel",
    "Anivia", "Urgot", "Akali", "Ekko", "Qiyana", "Senna", "Yasuo", "Ahri",
    "Evelynn", "Kaisa",
]
CAMPEOES_EXTRA = [
    "Jinx", "Lux", "Garen", "Darius", "Jhin", "Caitlyn", "Thresh", "Lulu",
    "Nautilus", "Leona", "LeeSin", "Viego", "Graves", "Hecarim", "Diana",
    "Katarina", "Zed", "Riven", "Vayne", "Teemo", "Morgana", "Brand",
]
CAMPEOES = CAMPEOES_OBRIGATORIOS + CAMPEOES_EXTRA

# Picos falsos de "vitrine": (campeao, data do evento, forca do pico).
# A forca multiplica a taxa base e decai ao longo de ~14 dias.
EVENTOS_FALSOS = [
    ("Aphelios", date(2026, 9, 11), 1.9),
    ("Ezreal", date(2026, 9, 25), 1.6),
    ("Kayn", date(2026, 10, 2), 2.1),
    ("KSante", date(2026, 10, 9), 1.5),
    ("Sett", date(2026, 10, 16), 1.8),
    ("Yone", date(2026, 10, 23), 1.7),
    ("Mel", date(2026, 10, 30), 2.3),
    ("Qiyana", date(2026, 11, 6), 1.6),
    ("Senna", date(2026, 11, 13), 1.4),
    ("Janna", date(2026, 9, 18), 1.3),
]


def dias(inicio: date, fim: date):
    d = inicio
    while d <= fim:
        yield d
        d += timedelta(days=1)


def main() -> None:
    rnd = random.Random(SEMENTE)

    # Taxa base de cada campeao, entre 1% e 15%.
    base = {}
    for i, campeao in enumerate(CAMPEOES):
        # Campeoes populares primeiro, cauda longa depois.
        teto = 0.15 if i < 12 else (0.09 if i < 26 else 0.05)
        base[campeao] = rnd.uniform(0.011, teto)

    # Tendencia lenta por campeao, para a serie nao ficar chapada.
    fase = {c: rnd.uniform(0, 2 * math.pi) for c in CAMPEOES}
    amplitude = {c: rnd.uniform(0.05, 0.25) for c in CAMPEOES}

    eventos_por_campeao: dict[str, list[tuple[date, float]]] = {}
    for campeao, dia_evento, forca in EVENTOS_FALSOS:
        eventos_por_campeao.setdefault(campeao, []).append((dia_evento, forca))

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    linhas = 0
    with SAIDA.open("w", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        escritor.writerow(["date", "champion", "games_total", "picks", "pick_rate"])

        for d in dias(DATA_INICIAL, DATA_FINAL):
            # Fim de semana tem mais partidas.
            fator_semana = 1.18 if d.weekday() >= 5 else 1.0
            games_total = int(PARTIDAS_POR_DIA_BASE * fator_semana * rnd.uniform(0.92, 1.08))

            indice_dia = (d - DATA_INICIAL).days
            for campeao in CAMPEOES:
                taxa = base[campeao]
                taxa *= 1 + amplitude[campeao] * math.sin(
                    2 * math.pi * indice_dia / 45 + fase[campeao]
                )

                for dia_evento, forca in eventos_por_campeao.get(campeao, []):
                    atraso = (d - dia_evento).days
                    if 0 <= atraso <= 14:
                        taxa *= 1 + (forca - 1) * math.exp(-atraso / 5.0)

                taxa *= rnd.uniform(0.90, 1.10)
                taxa = min(max(taxa, 0.010), 0.150)

                picks = int(round(taxa * games_total))
                # Garante que a taxa final (picks/games_total) fique em [1%, 15%]
                # mesmo depois do arredondamento.
                picks = max(math.ceil(0.010 * games_total),
                            min(math.floor(0.150 * games_total), picks))
                escritor.writerow(
                    [d.isoformat(), campeao, games_total, picks,
                     round(picks / games_total, 6)]
                )
                linhas += 1

    print(f"{SAIDA.relative_to(RAIZ)}: {linhas} linhas")
    print(f"periodo: {DATA_INICIAL} a {DATA_FINAL} "
          f"({(DATA_FINAL - DATA_INICIAL).days + 1} dias), {len(CAMPEOES)} campeoes")


if __name__ == "__main__":
    main()
