@echo off
REM ============================================================
REM  Instalacion inicial (ejecutar una sola vez)
REM ============================================================
cd /d "%~dp0"

echo Creando entorno virtual...
python -m venv .venv

echo Instalando dependencias...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
playwright install chromium

echo.
echo Listo. Ahora:
echo   1. Copia .env.example a .env y completa las credenciales.
echo   2. Coloca client_secret.json en esta carpeta.
echo   3. Ejecuta 2-PROBAR.bat para una corrida de prueba.
pause
