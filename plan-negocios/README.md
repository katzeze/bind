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
- **Resumen de actividad y sitio web** — relevados en la web mediante la API
  de Claude con la herramienta de búsqueda web.
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
| `ANTHROPIC_API_KEY` | Clave de la API de Claude. Sin ella la app funciona, pero el resumen y el sitio web se cargan a mano. |
| `CLAUDE_MODEL` | Modelo a usar (default `claude-opus-5`). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Servidor de mail para el envío del PDF. |

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
