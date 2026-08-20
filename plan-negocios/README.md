# Generador de Plan de Negocios por CUIT

App web interna: ingresás el CUIT de una empresa y la aplicación releva los
datos, arma un plan de negocios en PDF y, previa confirmación, lo envía por
mail.

## Qué incluye el plan

- **Razón social** — consultada en el padrón público de ARCA (ex AFIP), con
  fallback a búsqueda web.
- **Resumen de actividad y sitio web** — relevados en la web mediante la API
  de Claude con la herramienta de búsqueda web.
- **Importaciones 2024 y 2025 (USD)** — desde una fuente configurable
  (`IMPORTS_API_URL`, por ejemplo un servicio interno del banco o un proveedor
  como NOSIS) y, si no hay fuente, desde información pública encontrada en la
  web. Siempre se pueden cargar o corregir a mano.
- **Proyectado 2026** — calculado automáticamente: promedio de 2024 y 2025
  más 10%.

## Flujo de uso

1. **CUIT** — se valida el dígito verificador y se relevan los datos.
2. **Revisión** — todos los campos son editables; el proyectado 2026 se
   recalcula en vivo.
3. **PDF** — se genera la vista previa del plan.
4. **Confirmación y envío** — si está OK, se ingresa el mail del destinatario
   y se envía con el PDF adjunto.

## Puesta en marcha

```bash
cd plan-negocios
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completar credenciales
uvicorn app.main:app --reload
```

Abrir <http://localhost:8000>.

## Configuración (variables de entorno)

| Variable | Descripción |
|---|---|
| `ANTHROPIC_API_KEY` | Clave de la API de Claude. Sin ella la app funciona, pero el resumen, el sitio web y las importaciones no relevadas se cargan a mano. |
| `CLAUDE_MODEL` | Modelo a usar (default `claude-opus-5`). |
| `IMPORTS_API_URL` / `IMPORTS_API_TOKEN` | Endpoint que devuelve `{"2024": monto, "2025": monto}` por CUIT (fuente preferida de importaciones). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Servidor de mail para el envío del PDF. |

## Tests

```bash
python -m pytest tests/
```

## Notas de cumplimiento

- El PDF incluye un pie que aclara que es un **borrador generado
  automáticamente** y que requiere revisión humana antes de usarse en
  comunicaciones externas, documentos legales o decisiones crediticias.
- Los montos de importación relevados en la web son datos de terceros: el
  paso de revisión existe justamente para que un analista los verifique
  contra la fuente oficial que corresponda antes de enviar el documento.
- No existe una API pública oficial y gratuita de importaciones por CUIT;
  para datos fehacientes conectá `IMPORTS_API_URL` a la fuente que el banco
  tenga contratada.
