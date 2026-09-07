# Automatización: Límites & Disponibles (Qlik) → Corresponsalía Local (Drive)

Automatiza el circuito completo:

1. **Ingresa a Qlik Sense** (`bi.somosbind.com.ar`, app *Límites & Disponibles*) con usuario y contraseña.
2. **Descarga la tabla "Historico"** como datos (Excel), replicando el flujo manual de
   pasar el mouse por el cuadro → `...` → *Descargar como...* → *Datos*.
3. **Elige la línea válida por CUIT**: si hay varias filas para un mismo CUIT, toma la
   **aún no vencida** (Vto Cupo ≥ hoy) y, si todas vencieron, **la última que venció**.
4. **Completa la planilla de Drive "Corresponsalía Local"** buscando cada CUIT y
   cargando: **Cupo, Vto cupo, Deuda y % utilizado**.

> ⚠️ Los datos cargados alimentan decisiones internas: revisá el resumen de cada corrida
> (log + CUITs sin datos o con cupo vencido) antes de usar la planilla.

---

## Requisitos previos

* **Python 3.10+** en la PC (con acceso de red a `bi.somosbind.com.ar`).
* Usuario con permisos en el app de Qlik *Límites & Disponibles*.
* Un **`client_secret.json`** de Google (credencial OAuth de escritorio). Sirve el
  mismo que ya usás en `automatizacion-lineas-corresponsalia`: el script edita la
  planilla **con tu propia cuenta**, así que **no hace falta compartirla con nadie**
  (compatible con la restricción de no compartir fuera de la organización).

## Instalación

1. Ejecutar `1-INSTALAR.bat` (crea el entorno virtual, instala dependencias y Chromium).
2. Copiar `.env.example` a `.env` y completar `QLIK_USER` y `QLIK_PASS`.
3. Copiar `client_secret.json` a la carpeta del proyecto.
4. **Primera corrida**: se abre el navegador para iniciar sesión con tu cuenta
   corporativa y autorizar el acceso a Sheets. El token queda guardado en
   `token_google.json` y no vuelve a pedir login (también podés copiar el
   `token_google.json` del proyecto anterior si sigue vigente).

## Uso

| Acción | Comando |
|---|---|
| **Prueba** (no toca la planilla, guarda capturas en `debug/`) | `2-PROBAR.bat` o `python src/main.py --dry-run --debug` |
| **Corrida real** | `3-ACTUALIZAR-PLANILLA.bat` o `python src/main.py` |
| Reprocesar un Excel ya descargado | `python src/main.py --archivo descargas\archivo.xlsx` |

Cada corrida deja un log en `logs/` con el detalle por CUIT y un resumen final:
filas actualizadas, CUITs con cupo **vencido** (se cargó la última línea vencida) y
CUITs de la planilla **sin datos** en el Excel.

## Configuración (`config.yaml`)

* `qlik.sheet_url`: URL de la hoja en Qlik Sense.
* `qlik.object_title`: título del cuadro a exportar (por defecto `Historico`).
* `qlik.headless`: poner `false` para **ver el navegador** mientras trabaja (útil la
  primera vez o para diagnosticar).
* `qlik.windows_auth`: `true` (default). El sitio autentica con el **popup nativo de
  Windows** (dominio `INDUSTRIAL`), así que las credenciales se envían por NTLM.
  Si diera 401, probar en el `.env` el formato `QLIK_USER=INDUSTRIAL\tu_usuario`.
* `excel.columnas`: alias de las columnas del Excel exportado (CUIT, Cupo, Vto Cupo,
  Deuda, % utilizado). Si Qlik las exporta con otro nombre, agregarlo acá.
* `google_sheets`: ID de la planilla, nombre de la hoja y columnas destino
  (hoy: Cupo=D, Vto cupo=E, Deuda=F, % utilizado=G).

## Programación automática (opcional)

Para que corra sola todos los días, crear una tarea en el **Programador de tareas de
Windows** que ejecute `3-ACTUALIZAR-PLANILLA.bat` en el horario deseado (quitar el
`pause` final del .bat si se programa desatendido).

## Estructura

```
├── config.yaml              # URLs, columnas y planilla destino
├── .env                     # Credenciales de Qlik (NO subir a Git)
├── client_secret.json       # Credencial OAuth de Google (NO subir a Git)
├── token_google.json        # Token de sesión de Google (NO subir a Git)
├── descargas/               # Excel bajados de Qlik
├── logs/                    # Log de cada corrida
├── debug/                   # Capturas de pantalla (--debug)
└── src/
    ├── main.py              # Orquestación
    ├── qlik_client.py       # Playwright: login + exportación de la tabla
    ├── excel_parser.py      # Lectura del Excel y regla de vencimiento
    └── sheets_client.py     # Actualización de la planilla en Drive
```

## Primera puesta en marcha (importante)

Los selectores del menú de Qlik pueden variar según la versión instalada en el banco.
Si la primera corrida falla en el paso de exportación:

1. Correr `python src/main.py --dry-run --debug` con `qlik.headless: false`.
2. Revisar las capturas en `debug/` para ver en qué paso se trabó
   (login, carga de hoja, menú `...`, diálogo de exportación).
3. Ajustar `qlik.object_title` o avisarme con la captura para afinar el selector.
