@echo off
rem Prueba: extrae los datos de Tesin y los muestra, SIN tocar la hoja.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Primero hay que hacer doble clic en "1-INSTALAR.bat".
    pause
    exit /b 1
)
echo ============================================================
echo  PRUEBA: se conecta a Tesin y muestra los datos extraidos.
echo  NO modifica la hoja de calculo. Puede tardar unos minutos.
echo ============================================================
echo.
.venv\Scripts\python.exe src\main.py --dry-run --debug
echo.
echo ============================================================
echo  Si arriba se ven los importes de cada banco y coinciden
echo  con Tesin, ya esta todo listo: el paso siguiente es
echo  "3-ACTUALIZAR-HOJA.bat".
echo  Si aparecio un error, quedaron capturas de pantalla en la
echo  carpeta "debug": pasaselas a Claude para ajustarlo.
echo ============================================================
pause
