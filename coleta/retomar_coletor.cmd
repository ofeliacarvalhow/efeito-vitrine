@echo off
rem religa o coletor da Riot depois de uma queda ou de um reinicio.
rem
rem se ja existir um coletor rodando, a trava de instancia unica faz este
rem sair na hora com codigo 3 e um recado, sem brigar pelo banco. entao
rem chamar este arquivo duas vezes nao causa estrago.
rem
rem a coleta retoma do data/raw/coleta.sqlite, sem refazer sementes e sem
rem baixar de novo o que ja esta no matches.jsonl.

cd /d "C:\Users\Lenovo\Documents\efeito-vitrine"
if not exist ".venv\Scripts\python.exe" (
    echo [erro] o ambiente virtual nao esta em .venv
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "coleta\coletar.py"

rem codigo 3 e a trava, ou seja ja tinha um rodando. qualquer outro codigo
rem diferente de zero merece a janela ficar aberta para voce ler o erro.
if errorlevel 4 pause
if errorlevel 1 if not errorlevel 3 pause
