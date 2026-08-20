"""Enriquecimiento de datos de la empresa vía búsqueda web con la API de Claude.

Busca en la web: razón social, un resumen breve de la actividad, el sitio
web oficial y, si hay información pública disponible, montos de
importaciones 2024/2025 en USD. Todo lo que devuelve es un borrador que
el usuario revisa y puede corregir antes de generar el PDF.
"""

import json
import logging

import anthropic

from .. import config

logger = logging.getLogger(__name__)

_MAX_PAUSE_RESTARTS = 5

_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "razon_social": {"type": ["string", "null"]},
            "resumen": {"type": ["string", "null"]},
            "sitio_web": {"type": ["string", "null"]},
            "importaciones_2024_usd": {"type": ["number", "null"]},
            "importaciones_2025_usd": {"type": ["number", "null"]},
            "fuentes": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "razon_social",
            "resumen",
            "sitio_web",
            "importaciones_2024_usd",
            "importaciones_2025_usd",
            "fuentes",
        ],
        "additionalProperties": False,
    },
}

_PROMPT = """Investigá en la web la empresa argentina con CUIT {cuit}{pista}.

Necesito, en JSON:
- razon_social: la razón social registrada.
- resumen: un párrafo breve (3 a 5 oraciones, en español rioplatense) sobre a qué se dedica la empresa.
- sitio_web: la URL del sitio web oficial (null si no tiene o no lo encontrás).
- importaciones_2024_usd e importaciones_2025_usd: el monto total importado por la empresa en cada año, en dólares (USD CIF o FOB), solo si encontrás cifras publicadas atribuibles a esa empresa; si no hay datos confiables, null. No inventes ni estimes montos.
- fuentes: URLs de las fuentes que usaste.

Si un dato no aparece con certeza, devolvé null en ese campo."""


def _vacio() -> dict:
    return {
        "razon_social": None,
        "resumen": None,
        "sitio_web": None,
        "importaciones_2024_usd": None,
        "importaciones_2025_usd": None,
        "fuentes": [],
    }


def enriquecer_empresa(cuit: str, razon_social: str | None = None) -> dict:
    """Busca datos de la empresa en la web. Devuelve un dict con el schema de arriba."""
    if not config.ANTHROPIC_API_KEY:
        logger.info("ANTHROPIC_API_KEY no configurada: se omite el enriquecimiento web")
        return _vacio()

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    pista = f' (razón social: "{razon_social}")' if razon_social else ""
    messages = [{"role": "user", "content": _PROMPT.format(cuit=cuit, pista=pista)}]

    try:
        for _ in range(_MAX_PAUSE_RESTARTS + 1):
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=16000,
                tools=[
                    {
                        "type": "web_search_20260209",
                        "name": "web_search",
                        "max_uses": 8,
                    }
                ],
                output_config={"format": _SCHEMA},
                messages=messages,
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
        else:
            logger.warning("La búsqueda web quedó pausada tras varios reintentos")
            return _vacio()

        if response.stop_reason == "refusal":
            logger.warning("El modelo declinó la consulta para %s", cuit)
            return _vacio()

        texto = next((b.text for b in response.content if b.type == "text"), "")
        datos = json.loads(texto)
    except Exception as exc:  # noqa: BLE001 - el enriquecimiento nunca corta el flujo
        logger.warning("Falló el enriquecimiento web para %s: %s", cuit, exc)
        return _vacio()

    resultado = _vacio()
    for clave in resultado:
        if clave in datos:
            resultado[clave] = datos[clave]
    return resultado
