@echo off
REM ============================================================
REM  Corrida de PRUEBA: descarga y muestra los datos, pero
REM  NO modifica la planilla de Drive. Guarda capturas en debug\
REM ============================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python src\main.py --dry-run --debug
pause
