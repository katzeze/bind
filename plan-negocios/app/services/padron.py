"""Consulta de razón social en el padrón público de ARCA (ex AFIP).

Usa el servicio público de constancia de inscripción. Si el servicio no
responde (es habitual que aplique límites), se devuelve None y la razón
social se completa vía búsqueda web o carga manual.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_PADRON_URL = "https://soa.afip.gob.ar/sr-padron/v2/persona/{cuit}"


async def buscar_razon_social(cuit: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_PADRON_URL.format(cuit=cuit))
            resp.raise_for_status()
            data = resp.json().get("data", {})
    except Exception as exc:  # noqa: BLE001 - el padrón es best-effort
        logger.warning("No se pudo consultar el padrón para %s: %s", cuit, exc)
        return None

    razon_social = data.get("razonSocial")
    if not razon_social:
        nombre = " ".join(filter(None, (data.get("nombre"), data.get("apellido"))))
        razon_social = nombre or None
    return razon_social
