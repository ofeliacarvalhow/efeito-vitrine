r"""
Fecha a coleta: roda o ciclo inteiro e deixa a entrega pronta, num comando.

Sao nove passos em ordem, e a ordem importa: o documento da entrega le o
relatorio da analise e os CSV da propria pasta, entao regerar o documento
antes de atualizar essas copias produz um docx com numero velho e cara de
novo. Esse foi o caminho que fez o "cinco clipes" sobreviver a uma entrega
inteira.

Cada passo para na hora se falhar, com o erro inteiro na tela. Nada de
seguir adiante com dado pela metade.

O script se recusa a rodar enquanto houver coletor vivo, porque agregar um
matches.jsonl que ainda esta sendo escrito da um retrato que ninguem
consegue reproduzir depois.

Rodar:  .venv\Scripts\python.exe coleta\fechar_coleta.py

Opcoes:
  --manter-atalho   nao remove o atalho da pasta Startup do Windows
  --sem-downloads   nao monta a pasta de entrega no Downloads
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "coleta"))

from config import ARQUIVO_TRAVA, FUSO  # noqa: E402

PY = RAIZ / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = RAIZ / ".venv" / "bin" / "python"

ENTREGA = RAIZ / "entrega"
PROCESSADOS = RAIZ / "data" / "processed"
PAINEL = RAIZ / "painel" / "dados"
STARTUP = (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" /
           "Start Menu" / "Programs" / "Startup" /
           "coletor-efeito-vitrine.cmd")

#o que a pasta da entrega carrega como copia, e de onde cada coisa vem. sem
#isso os dois geradores de la trabalham em cima do retrato antigo
COPIAS = [
    (PROCESSADOS / "daily_pickrate.csv", ENTREGA / "dados" / "daily_pickrate.csv"),
    (PROCESSADOS / "events.csv", ENTREGA / "dados" / "events.csv"),
    (PROCESSADOS / "patch_dates.csv", ENTREGA / "dados" / "patch_dates.csv"),
    (PROCESSADOS / "balance_changes.csv", ENTREGA / "dados" / "balance_changes.csv"),
    (PROCESSADOS / "new_skins.csv", ENTREGA / "dados" / "new_skins.csv"),
    (RAIZ / "analise" / "relatorio.txt", ENTREGA / "analise-relatorio-completo.txt"),
    (PROCESSADOS / "qualidade.txt", ENTREGA / "qualidade-da-amostra.txt"),
]

PASSOS = [
    ("agregar o bruto na tabela diaria", RAIZ / "coleta" / "agregar.py"),
    ("relatorio de qualidade", RAIZ / "coleta" / "qualidade.py"),
    ("catalogo de eventos", RAIZ / "eventos" / "montar_eventos.py"),
    ("analise, com o placebo", RAIZ / "analise" / "efeito_vitrine.py"),
    ("JSON da coleta", RAIZ / "coleta" / "exportar_json.py"),
    ("JSON dos resultados", RAIZ / "coleta" / "exportar_json_resultados.py"),
]

DEPOIS_DAS_COPIAS = [
    ("CSV de resultados da entrega", ENTREGA / "gerar_csv_resultados.py"),
    ("documento da entrega", ENTREGA / "gerar_documento.py"),
]


def trava_esta_tomada() -> bool:
    """True se a trava de instancia unica ainda esta nas maos de alguem.

    O seek(0) nao e enfeite: msvcrt.locking tranca um byte a partir da
    posicao ATUAL, e abrir em "a+" posiciona no fim do arquivo. Sem o seek
    este teste trancava um byte no fim, que ninguem disputa, e respondia que
    nao havia coletor nenhum enquanto havia. O coletor tranca o byte 0, e e
    o byte 0 que precisa ser testado.
    """
    if not ARQUIVO_TRAVA.exists():
        return False
    try:
        arquivo = open(ARQUIVO_TRAVA, "a+", encoding="utf-8")
    except OSError:
        return True
    try:
        arquivo.seek(0)
        try:
            import msvcrt
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        except ImportError:
            import fcntl
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        arquivo.close()


def log_mexido_agora(minutos: float = 5.0) -> bool:
    """True se o log da coleta mudou ha pouco e nao foi para se despedir.

    Segunda checagem, independente da trava. A primeira versao deste script
    confiou numa trava so, ela respondeu errado, e o ciclo inteiro rodou em
    cima de um matches.jsonl que estava sendo escrito. Dois sinais custam
    nada e cobrem um ao outro.

    O coletor escreve "fim desta rodada" no finally, depois de dar flush no
    arquivo e commit no banco. Quando essa e a ultima linha, o log acabou de
    mudar justamente porque a coleta terminou, e esperar cinco minutos seria
    so atraso.
    """
    log = RAIZ / "coleta" / "coletar.log"
    if not log.exists():
        return False
    idade = datetime.now().timestamp() - log.stat().st_mtime
    if idade >= minutos * 60:
        return False
    ultimas = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for linha in reversed(ultimas[-5:]):
        if "fim desta rodada" in linha:
            return False
    return True


def coletor_vivo() -> tuple[bool, str]:
    if trava_esta_tomada():
        return True, "a trava de instancia unica esta tomada"
    if log_mexido_agora():
        return True, "o coletar.log mudou nos ultimos 5 minutos"
    return False, ""


def roda(rotulo: str, script: Path, numero: int, total: int) -> None:
    print("")
    print("=" * 70)
    print(f"[{numero}/{total}] {rotulo}")
    print(f"        {script.relative_to(RAIZ).as_posix()}")
    print("=" * 70)
    resultado = subprocess.run([str(PY), str(script)], cwd=RAIZ)
    if resultado.returncode != 0:
        print("")
        print(f"[PAROU] {rotulo} saiu com codigo {resultado.returncode}.")
        print("o erro inteiro esta logo acima. nada depois disso rodou, "
              "entao a entrega continua no estado anterior.")
        raise SystemExit(resultado.returncode)


def copia_para_a_entrega(numero: int, total: int) -> None:
    print("")
    print("=" * 70)
    print(f"[{numero}/{total}] copiar os dados frescos para a pasta da entrega")
    print("=" * 70)
    faltando = [o for o, _ in COPIAS if not o.exists()]
    if faltando:
        print("[PAROU] estes arquivos nao existem:")
        for o in faltando:
            print(f"  {o.relative_to(RAIZ).as_posix()}")
        raise SystemExit(1)
    for origem, destino in COPIAS:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        print(f"  {origem.relative_to(RAIZ).as_posix()}"
              f"  ->  {destino.relative_to(RAIZ).as_posix()}")


def tira_o_atalho(numero: int, total: int) -> None:
    print("")
    print("=" * 70)
    print(f"[{numero}/{total}] tirar o atalho da pasta Startup do Windows")
    print("=" * 70)
    if not STARTUP.exists():
        print("  ja nao estava la, nada a fazer")
        return
    conteudo = STARTUP.read_text(encoding="utf-8", errors="replace")
    STARTUP.unlink()
    print(f"  removido: {STARTUP}")
    print("  ele tinha isto, caso precise voltar:")
    for linha in conteudo.splitlines():
        print(f"    {linha}")


def monta_downloads(numero: int, total: int) -> Path | None:
    print("")
    print("=" * 70)
    print(f"[{numero}/{total}] montar a pasta de entrega no Downloads")
    print("=" * 70)
    hoje = datetime.now(FUSO).date().isoformat()
    alvo = Path.home() / "Downloads" / f"efeito-vitrine-painel-{hoje}"
    if alvo.exists():
        shutil.rmtree(alvo)
    (alvo / "dados").mkdir(parents=True)

    for arquivo in sorted(PAINEL.glob("*.json")):
        shutil.copy2(arquivo, alvo / "dados" / arquivo.name)
    leiame_dados = PAINEL / "LEIA-ME.txt"
    if leiame_dados.exists():
        shutil.copy2(leiame_dados, alvo / "dados" / "LEIA-ME.txt")
    for origem, nome in [
        (ENTREGA / "Efeito-Vitrine-painel-especificacao.docx", None),
        (ENTREGA / "dados" / "resultados_por_campeao_evento.csv", None),
        (ENTREGA / "analise-relatorio-completo.txt", None),
        (ENTREGA / "qualidade-da-amostra.txt", None),
    ]:
        shutil.copy2(origem, alvo / (nome or origem.name))

    (alvo / "LEIA-ME.txt").write_text(resumo_da_entrega(), encoding="utf-8")
    quantos = sum(1 for _ in alvo.rglob("*") if _.is_file())
    print(f"  {alvo}")
    print(f"  {quantos} arquivos")
    return alvo


def resumo_da_entrega() -> str:
    """Um LEIA-ME curto com os numeros que acabaram de sair."""
    resumo = json.loads((PAINEL / "resumo.json").read_text(encoding="utf-8"))
    tipos = json.loads((PAINEL / "tipos.json").read_text(encoding="utf-8"))
    placebo = json.loads((PAINEL / "placebo.json").read_text(encoding="utf-8"))

    linhas = [
        "EFEITO VITRINE: ENTREGA PARA O PAINEL",
        f"gerada em {resumo['gerado_em']}",
        "",
        "",
        "A DATA DO RETRATO",
        "",
        f"    dados_de    {resumo['dados_de']}",
        "",
        "Esta e a data que vale, e e ela que deve aparecer em toda tela do",
        "painel. O gerado_em diz so quando o arquivo foi escrito.",
        "",
        "",
        "A AMOSTRA",
        "",
        f"    partidas    {resumo['partidas']}",
        f"    por dia     {resumo['partidas_por_dia']}",
        f"    periodo     {resumo['periodo']['de']} a "
        f"{resumo['periodo']['ate']}, {resumo['periodo']['dias']} dias",
        f"    campeoes    {resumo['campeoes']}",
        f"    eventos     {resumo['eventos']['total']}",
        "",
        f"    {resumo['aviso']}",
        "",
        "",
        "O RESULTADO POR TIPO DE EVENTO",
        "",
        "    tipo         pelo pico (do relatorio)   pelo lift (conservadora)",
    ]
    for t in tipos["tipos"]:
        l = t["pelo_lift"]
        linhas.append(
            f"    {t['tipo']:<10s}   {t['acima']:>3d} de {t['de']:<3d} "
            f"chance {t['chance']:.3f}      "
            f"{l['acima']:>3d} de {l['de']:<3d} chance {l['chance']:.3f}"
        )
    linhas += [
        "",
        "    As duas medidas estao em tipos.json. Qual delas o trabalho adota",
        "    e a decisao da secao 14.4 do documento, e o painel tem que",
        "    mostrar a mesma que o texto.",
        "",
        "",
        "O PLACEBO",
        "",
        f"    real {placebo['real']}, media do sorteio {placebo['media']}, "
        f"chance {placebo['chance']:.3f}",
        f"    as {placebo['repeticoes']} contagens estao em placebo.json, "
        "no campo contagens",
        "",
        "",
        "O QUE TEM NA PASTA",
        "",
        "    dados/        os nove JSON que o painel busca com fetch, e um",
        "                  LEIA-ME proprio com o formato de cada um",
        "    o docx        metodologia, resultados e as 13 telas",
        "    o csv         a mesma tabela do resultados.json, para o Excel",
        "    relatorio     a analise evento por evento",
        "    qualidade     partidas dia por dia e os avisos de leitura",
        "",
    ]
    return "\n".join(linhas) + "\n"


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="roda o ciclo inteiro depois que a coleta encerra")
    analisador.add_argument("--manter-atalho", action="store_true",
                            help="nao remove o atalho da pasta Startup")
    analisador.add_argument("--sem-downloads", action="store_true",
                            help="nao monta a pasta no Downloads")
    argumentos = analisador.parse_args()

    if not PY.exists():
        print(f"[erro] nao achei o python do ambiente virtual em {PY}")
        return 1

    vivo, motivo = coletor_vivo()
    if vivo:
        print(f"[erro] a coleta ainda parece viva: {motivo}.")
        print("agregar um matches.jsonl que esta sendo escrito agora da um")
        print("retrato que ninguem reproduz depois. espere ela encerrar, ou")
        print("pare com Ctrl+C na janela dela, e rode de novo.")
        return 2

    total = len(PASSOS) + 1 + len(DEPOIS_DAS_COPIAS)
    if not argumentos.manter_atalho:
        total += 1
    if not argumentos.sem_downloads:
        total += 1

    comeco = datetime.now(FUSO)
    print(f"fechando a coleta, {comeco:%d/%m %H:%M}")

    numero = 0
    for rotulo, script in PASSOS:
        numero += 1
        roda(rotulo, script, numero, total)

    numero += 1
    copia_para_a_entrega(numero, total)

    for rotulo, script in DEPOIS_DAS_COPIAS:
        numero += 1
        roda(rotulo, script, numero, total)

    if not argumentos.manter_atalho:
        numero += 1
        tira_o_atalho(numero, total)

    pasta = None
    if not argumentos.sem_downloads:
        numero += 1
        pasta = monta_downloads(numero, total)

    resumo = json.loads((PAINEL / "resumo.json").read_text(encoding="utf-8"))
    minutos = (datetime.now(FUSO) - comeco).total_seconds() / 60
    print("")
    print("=" * 70)
    print(f"PRONTO em {minutos:.1f} minutos")
    print("=" * 70)
    print(f"  {resumo['partidas']} partidas, {resumo['periodo']['dias']} "
          f"dias, {resumo['campeoes']} campeoes, "
          f"{resumo['eventos']['total']} eventos")
    print(f"  retrato de {resumo['dados_de']}")
    if pasta:
        print(f"  entrega em {pasta}")
    print("")
    print("  falta so conferir e commitar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
