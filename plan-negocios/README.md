# Generador de Plan de Negocios por CUIT

App web interna de Bind Banco Industrial: ingresás el CUIT de una empresa y
la aplicación releva los datos, arma el plan de negocios en PDF con el
formato del banco y, previa confirmación, lo envía por mail al equipo COMEX.

## Qué incluye el plan

- **Razón social** — del padrón público de ARCA (ex AFIP), con fallback a la
  base ANA IMPO y a la búsqueda web.
- **Importaciones FOB 2024 y 2025 (USD)** — desde la base ANA IMPO (Excel
  `BASE ANA IMPO filtrada 2024 Y 2025 OK`). Si el CUIT no figura, se pueden
  cargar a mano.
- **Resumen de actividad y sitio web** — relevados con Google Programmable
  Search (Custom Search API), gratis hasta 100 búsquedas por día.
- **Proyectado 2026** — calculado automáticamente: promedio de 2024 y 2025
  más 10%.

El PDF lleva el logo y los colores institucionales de bind.

## Flujo de uso

1. **CUIT** — se valida el dígito verificador y se relevan los datos.
2. **Revisión** — todos los campos son editables; el proyectado 2026 se
   recalcula en vivo.
3. **PDF** — se genera la vista previa del plan.
4. **Confirmación y envío** — la app muestra el mail exacto que va a salir
   (destinatarios fijos del equipo, asunto "Plan de Negocios {razón social}",
   cuerpo estándar y el PDF adjunto) y lo envía al confirmar.

## Puesta en marcha

```bash
cd plan-negocios
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar credenciales
# copiar el Excel de la base ANA a data/base_ana_impo_2024_2025.xlsx
uvicorn app.main:app --reload
```

Abrir <http://localhost:8000>.

> **Importante:** el Excel de la base ANA contiene datos de clientes y **no
> se versiona en git** (está en `.gitignore`). Hay que copiarlo a `data/`
> en cada despliegue, o apuntar `BASE_IMPO_XLSX` a su ubicación (por ejemplo
> una carpeta compartida). El Excel se cachea en memoria al primer uso.

## Configuración (variables de entorno)

| Variable | Descripción |
|---|---|
| `BASE_IMPO_XLSX` | Ruta al Excel de la base ANA IMPO (default `data/base_ana_impo_2024_2025.xlsx`). Columnas esperadas: CUIT, Razon Social, FOB 2025, FOB 2024. |
| `MAIL_DESTINATARIOS` | Destinatarios del envío separados por `;`. Default: la lista fija del equipo COMEX definida en `app/config.py`. |
| `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX` | Credenciales de Google Custom Search. Sin ellas la app funciona, pero el resumen y el sitio web se cargan a mano. Ver paso a paso abajo. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Servidor de mail para el envío del PDF. |

## Cómo sacar las credenciales gratuitas de Google (una sola vez)

No hace falta saber programar, son dos pantallas de Google:

1. **Crear el "motor de búsqueda"** (da el valor de `GOOGLE_SEARCH_CX`):
   - Entrar a <https://programmablesearchengine.google.com/> con una cuenta
     de Google (puede ser una del banco).
   - "Agregar" un motor nuevo, ponerle un nombre (ej. "Plan de Negocios bind").
   - En la configuración del motor, activar **"Buscar en toda la web"**.
   - Copiar el **"ID del motor de búsqueda"** (search engine ID / `cx`) —
     es un código como `a1b2c3d4e5f6g7h8i`.
2. **Sacar la clave de API** (da el valor de `GOOGLE_SEARCH_API_KEY`):
   - Entrar a <https://console.cloud.google.com/> con la misma cuenta.
   - Crear un proyecto (o usar uno existente).
   - Buscar **"Custom Search API"** en la biblioteca de APIs y habilitarla.
   - Ir a "Credenciales" → "Crear credenciales" → "Clave de API" y copiarla.
3. Pegar ambos valores en el archivo `.env` (`GOOGLE_SEARCH_API_KEY` y
   `GOOGLE_SEARCH_CX`).

El nivel gratuito permite 100 búsquedas por día; cada plan de negocios usa
una sola búsqueda, así que alcanza de sobra para el uso normal del equipo.

## Tests

```bash
python -m pytest tests/
```

## Notas de cumplimiento

- El PDF incluye un pie que aclara que es un **borrador generado
  automáticamente** y que requiere revisión humana antes de usarse en
  comunicaciones externas, documentos legales o decisiones crediticias.
- El envío del mail requiere siempre la confirmación explícita del usuario,
  que ve destinatarios, asunto, cuerpo y adjunto antes de confirmar.
- El resumen de actividad y el sitio web provienen de búsqueda web: el paso
  de revisión existe para que un analista los verifique antes del envío.
