@echo off
rem Corrida real: extrae de Tesin y ACTUALIZA la hoja LINEAS CORRESPONSALIA.
rem Este es el archivo que tambien ejecuta la tarea programada semanal.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Primero hay que hacer doble clic en "1-INSTALAR.bat".
    pause
    exit /b 1
)
if not exist service_account.json (
    echo Falta el archivo "service_account.json" de Google en esta
    echo carpeta ^(ver paso 2 del README, o pedirselo a Claude^).
    pause
    exit /b 1
)
.venv\Scripts\python.exe src\main.py
echo.
echo  Termino. Revisa la hoja LINEAS CORRESPONSALIA en Drive para
echo  confirmar que los datos esten bien.
pause
