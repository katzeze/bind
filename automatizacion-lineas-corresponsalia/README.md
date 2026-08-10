# Automatización — Líneas de Corresponsalía (Tesin → Google Sheets)

Reemplaza la carga manual semanal: el script entra a Tesin con un navegador
headless, busca cada banco corresponsal en **Corresponsales → Líneas de
Crédito Recibidas**, toma el **utilizado** de *Cartas de Crédito de
Importación* (LC) y de *Préstamos - Financiaciones* (FINANC), y actualiza esas
celdas en la hoja de Drive **LINEAS CORRESPONSALIA** (bloque UTILIZADO, filas
LC y FINANC de cada banco).

> **Importante:** Tesin solo es accesible desde la red del banco, así que esto
> tiene que correr en una PC o servidor interno (por ejemplo, tu máquina de
> trabajo con el Programador de Tareas de Windows). No puede correr en la nube.

## Instalación (una sola vez)

Requiere Python 3.10 o superior.

```bash
cd automatizacion-lineas-corresponsalia
python -m venv .venv
.venv\Scripts\activate          # en Windows  (en Linux: source .venv/bin/activate)
pip install -r requirements.txt
playwright install chromium
```

### 1. Credenciales de Tesin

Copiá `.env.example` a `.env` y completá `TESIN_USER` y `TESIN_PASS`.
El archivo `.env` queda solo en tu máquina (está en `.gitignore`, nunca se sube
al repositorio). **Recomendado:** pedile a Sistemas/SegInfo un usuario de
servicio de solo consulta para Tesin, en lugar de usar tu usuario personal.

### 2. Acceso a Google Sheets (cuenta de servicio)

1. En [Google Cloud Console](https://console.cloud.google.com/) creá un
   proyecto (o usá uno del área), habilitá la **Google Sheets API** y creá una
   **cuenta de servicio** con una clave JSON.
2. Guardá el JSON como `service_account.json` en esta carpeta (también está
   en `.gitignore`).
3. Compartí la hoja **LINEAS CORRESPONSALIA** con el mail de la cuenta de
   servicio (algo como `xxx@proyecto.iam.gserviceaccount.com`) con permiso de
   **Editor**.

Si el banco tiene Google Workspace administrado, coordiná este paso con
SegInfo/Sistemas.

### 3. Códigos de los bancos

En `config.yaml` está cargado BNA = 9524. Completá el código de búsqueda en
Tesin de los demás (SCH, CMZ, IFC, JPM, BLDX, BID) — son los mismos números
que usás hoy para buscarlos a mano. Los bancos sin código se omiten con un
aviso.

## Primera corrida (calibración)

Tesin es una aplicación GeneXus y este script navega las pantallas como lo
harías vos; los selectores por defecto cubren el caso típico, pero conviene
verificar la primera vez **sin escribir en la hoja**:

```bash
python src/main.py --dry-run --debug
```

- Muestra por pantalla los valores que extrajo, sin tocar la hoja.
- Deja en `debug/` una captura y el HTML de cada paso (login, grilla, búsqueda,
  detalle). Si algo falla, esos archivos indican qué selector o etiqueta hay
  que ajustar en `config.yaml` (están comentados uno por uno).

Cuando los valores del dry-run coincidan con lo que ves en Tesin, corré en real:

```bash
python src/main.py
```

Cada corrida deja un log en `logs/` con el valor anterior y el nuevo de cada
celda, así siempre podés auditar qué cambió.

## Programación semanal

### Windows (Programador de Tareas)

Desde una consola con permisos, ajustando rutas, día y hora (ejemplo: lunes 9:00):

```bat
schtasks /Create /TN "Lineas Corresponsalia" /SC WEEKLY /D MON /ST 09:00 ^
  /TR "C:\ruta\al\repo\automatizacion-lineas-corresponsalia\.venv\Scripts\python.exe C:\ruta\al\repo\automatizacion-lineas-corresponsalia\src\main.py"
```

También se puede crear desde la interfaz gráfica del Programador de Tareas
apuntando al mismo comando. Tildá "Ejecutar aunque el usuario no haya iniciado
sesión" si la PC queda prendida.

### Linux (cron)

```cron
0 9 * * 1 cd /ruta/al/repo/automatizacion-lineas-corresponsalia && .venv/bin/python src/main.py
```

## Consideraciones

- **Revisión humana:** la automatización transcribe datos, no toma decisiones.
  Revisá la hoja después de cada corrida (el log de `logs/` facilita el
  control) antes de usar los números en reportes o decisiones.
- Las fórmulas de TOTALES, composición y ratios de la hoja no se tocan: solo
  se escriben las celdas UTILIZADO/LC y UTILIZADO/FINANC de cada banco.
- Si Tesin cambia de pantalla o de textos, el script falla con un error claro
  en el log en lugar de cargar datos erróneos; se recalibra con `--debug`.
- Coordiná con SegInfo el uso de credenciales automatizadas sobre Tesin y el
  alta de la cuenta de servicio de Google.
