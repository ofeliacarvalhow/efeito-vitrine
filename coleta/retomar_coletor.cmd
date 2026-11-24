@echo off
rem religa o coletor da Riot depois de uma queda ou de um reinicio.
rem
rem se ja existir um coletor rodando, a trava de instancia unica faz este
rem sair na hora com codigo 3 e um recado, sem brigar pelo banco. entao
rem chamar este arquivo duas vezes nao causa estrago.
rem
rem a coleta retoma do data/raw/coleta.sqlite, sem refazer sementes e sem
rem baixar de novo o que ja esta no matches.jsonl.
rem
rem em 23/11 o coletor caiu as 14:52 e esta janela ficou parada no pause por
rem 17 horas, sem coletar nada. agora a janela religa sozinha em vez de
rem esperar alguem ler o erro.

cd /d "C:\Users\Lenovo\Documents\efeito-vitrine"
if not exist ".venv\Scripts\python.exe" (
    echo [erro] o ambiente virtual nao esta em .venv
    pause
    exit /b 1
)

set /a tentativas=0

:rodar
".venv\Scripts\python.exe" "coleta\coletar.py"
set codigo=%errorlevel%
if "%codigo%"=="0" goto fim
if "%codigo%"=="3" goto fim
set /a tentativas+=1
if %tentativas% GEQ 20 goto desistiu
echo.
echo [religando] o coletor saiu com codigo %codigo%. tentativa %tentativas% de 20, esperando 30 segundos.
echo [religando] o motivo esta no fim de coleta\coletar.log
timeout /t 30 /nobreak >nul
goto rodar

:desistiu
echo.
echo [parou] 20 quedas seguidas, nao vou religar mais.
echo [parou] leia o fim de coleta\coletar.log
pause
exit /b 1

:fim
echo.
echo [fim] o coletor saiu com codigo %codigo%, sem queda.
timeout /t 15 >nul
