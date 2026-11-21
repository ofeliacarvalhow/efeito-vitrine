"""
Valores da coleta. Mexa aqui, nao dentro do coletar.py.

Nenhum segredo neste arquivo. A chave da Riot vive no .env, que o Git barra.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_ENV = RAIZ / ".env"

#periodo analisado. comecou em 4 de setembro e foi estendido para tras em
#21/11/2026, por poder estatistico: com 76 dias o estudo tinha 24 por cento
#de chance de achar o efeito mesmo se ele existisse, porque o teste conta
#campeoes por evento e so havia 20 pares. com 270 dias sao cerca de 71 pares
#e 86 por cento. o historico da API e o rendimento por jogador foram medidos
#nessas datas antigas e nao caem.
DATA_INICIAL = date(2026, 2, 24)
DATA_FINAL = date(2026, 11, 18)
FUSO = ZoneInfo("America/Sao_Paulo")

#fila ranqueada solo
FILA_RANQUEADA = 420

#jogadores ficam na plataforma, partidas ficam na regiao
PLATAFORMA = "https://br1.api.riotgames.com"
REGIAO = "https://americas.api.riotgames.com"

#limites da chave de desenvolvimento: 20 por segundo e 100 a cada 2 minutos.
#os dois valem ao mesmo tempo e o coletor respeita o mais apertado.
LIMITES = ((20, 1), (100, 120))

#elos que tem divisao I a IV, pedidos pelo endpoint de entries
ELOS_COM_DIVISAO = [
    "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND",
]
DIVISOES = ["I", "II", "III", "IV"]

#elos sem divisao, cada um com endpoint proprio
ELOS_APEX = ["MASTER", "GRANDMASTER", "CHALLENGER"]

#meta de sementes por elo, dividida entre as divisoes
JOGADORES_POR_ELO = 400
PAGINAS_MAXIMAS = 40

#metas de partidas baixadas por semana, uma por passada
METAS_POR_PASSADA = (3000, 6000, 10000)

#a primeira e a ultima janela tem 3 dias, nao 7. com isso ligado a meta delas
#cai na mesma proporcao, para o numero de partidas por DIA ficar parecido em
#todo o periodo. desligue para usar a meta cheia em toda janela.
META_PROPORCIONAL_AOS_DIAS = True

#janela, em segundos, usada para estimar o tempo que falta
JANELA_DA_TAXA = 600

#quantas partidas o coletor baixa de uma semana antes de passar para a proxima
LOTE_POR_SEMANA = 50

#quantos IDs pendentes manter em estoque numa semana antes de baixar
ESTOQUE_MINIMO = 200

#quantos jogadores consultar de uma vez ao buscar IDs de uma semana
LOTE_DE_JOGADORES = 25

IDS_POR_REQUISICAO = 100
SEMENTE_SORTEIO = 20260904

#a cada quantas partidas sai a linha de progresso
PROGRESSO_CADA = 100

#Data Dragon. nao e a API da Riot: nao usa chave e nao tem limite de taxa.
VERSOES_DDRAGON = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON = "https://ddragon.leagueoflegends.com/cdn"
IDIOMA_DDRAGON = "pt_BR"
ESPERA_DDRAGON = 0.05

#patches do periodo. o versions.json numera 16.1 a 16.23, com um build por
#patch, e nao existe 26.x nenhum. a lista cobre de 16.3, que estava no ar em
#24 de fevereiro, ate 16.23, que entrou em 18 de novembro.
PATCHES = ["16.3", "16.4", "16.5", "16.6", "16.7", "16.8", "16.9",
           "16.10", "16.11", "16.12", "16.13", "16.14", "16.15", "16.16",
           "16.17", "16.18", "16.19", "16.20", "16.21", "16.22", "16.23"]

#patch anterior ao primeiro, baixado so para servir de comparacao e revelar
#as skins novas do primeiro. nao gera linha propria no CSV.
PATCH_BASE = "16.2"

BANCO = RAIZ / "data" / "raw" / "coleta.sqlite"
#trava de instancia unica. o sistema solta sozinho quando o processo morre,
#inclusive em queda de energia, entao nao sobra trava velha.
ARQUIVO_TRAVA = RAIZ / "data" / "raw" / "coletor.lock"
CACHE_DDRAGON = RAIZ / "data" / "cache_ddragon"
PARTIDAS = RAIZ / "data" / "raw" / "matches.jsonl"
ARQUIVO_LOG = RAIZ / "coleta" / "coletar.log"
