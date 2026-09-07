@echo off
REM ============================================================
REM  Corrida REAL: descarga desde Qlik y actualiza la planilla
REM  "Corresponsalia Local" en Google Drive.
REM ============================================================
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python src\main.py
pause
