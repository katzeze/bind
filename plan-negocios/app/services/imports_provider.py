"""Fuente de datos de importaciones por CUIT.

Los montos de importación por empresa no están publicados en una API
oficial gratuita, así que la fuente es configurable vía IMPORTS_API_URL
(por ejemplo un servicio interno del banco o un proveedor como NOSIS).
El contrato esperado es:

    GET {IMPORTS_API_URL}?cuit=30XXXXXXXXX
    -> {"2024": 1234567.0, "2025": 2345678.0}

Si no hay endpoint configurado o falla, se devuelven None y los montos
se completan con la búsqueda web o a mano en la pantalla de revisión.
"""

import logging

import httpx

from .. import config

logger = logging.getLogger(__name__)


async def buscar_importaciones(cuit: str) -> dict[str, float | None]:
    vacio: dict[str, float | None] = {"2024": None, "2025": None}
    if not config.IMPORTS_API_URL:
        return vacio

    headers = {}
    if config.IMPORTS_API_TOKEN:
        headers["Authorization"] = f"Bearer {config.IMPORTS_API_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                config.IMPORTS_API_URL, params={"cuit": cuit}, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 - fuente externa best-effort
        logger.warning("No se pudo consultar importaciones para %s: %s", cuit, exc)
        return vacio

    resultado = dict(vacio)
    for anio in ("2024", "2025"):
        valor = data.get(anio)
        if isinstance(valor, (int, float)):
            resultado[anio] = float(valor)
    return resultado
