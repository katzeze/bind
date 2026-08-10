@echo off
rem Instalacion completa con doble clic. Se corre UNA sola vez.
cd /d "%~dp0"
echo ============================================================
echo  PASO 1 de 3: Verificando que Python este instalado...
echo ============================================================
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo  ERROR: Python no esta instalado en esta computadora.
    echo  Instalalo desde https://www.python.org/downloads/
    echo  IMPORTANTE: al instalar, tildar la casilla "Add Python to PATH".
    echo  Despues volve a hacer doble clic en este archivo.
    echo.
    pause
    exit /b 1
)
echo  OK, Python encontrado.
echo.
echo ============================================================
echo  PASO 2 de 3: Instalando los componentes (puede tardar
echo  varios minutos, no cierres esta ventana)...
echo ============================================================
python -m venv .venv
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto :error
echo.
echo ============================================================
echo  PASO 3 de 3: Ahora se abre el Bloc de notas.
echo  Completa tu usuario y contrasena de Tesin, guarda con
echo  Ctrl+G (o Archivo, Guardar) y cerra el Bloc de notas.
echo ============================================================
if not exist .env copy .env.example .env >nul
notepad .env
echo.
echo  LISTO. La instalacion termino bien.
echo  Ahora hace doble clic en "2-PROBAR.bat" para hacer una
echo  prueba (no modifica la hoja de calculo).
echo.
pause
exit /b 0

:error
echo.
echo  Hubo un ERROR durante la instalacion.
echo  Saca una captura de esta ventana (o copia el texto) y
echo  pasasela a Claude para que lo resuelva.
echo.
pause
exit /b 1
