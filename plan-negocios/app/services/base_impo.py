"""Fuente de datos de importaciones: base ANA IMPO 2024/2025 (Excel).

Lee el Excel indicado en BASE_IMPO_XLSX (hoja "Datos Filtrados", columnas
CUIT, Razon Social, FOB 2025, FOB 2024) una sola vez y lo cachea en
memoria, indexado por CUIT normalizado a 11 dígitos.
"""

import logging
import threading
from pathlib import Path

from .. import config
from .cuit import normalizar_cuit

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_base: dict[str, dict] | None = None


def _cargar() -> dict[str, dict]:
    ruta = Path(config.BASE_IMPO_XLSX)
    if not ruta.exists():
        logger.warning("No se encontró la base de importaciones en %s", ruta)
        return {}

    import openpyxl  # import diferido: la carga tarda unos segundos

    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = wb[wb.sheetnames[0]]
    filas = hoja.iter_rows(values_only=True)
    encabezado = [str(c or "").strip().upper() for c in next(filas)]

    def col(nombre: str) -> int:
        for i, titulo in enumerate(encabezado):
            if nombre in titulo:
                return i
        raise ValueError(f"No se encontró la columna '{nombre}' en {ruta.name}")

    i_cuit = col("CUIT")
    i_razon = col("RAZON")
    i_2024 = col("2024")
    i_2025 = col("2025")

    base: dict[str, dict] = {}
    for fila in filas:
        crudo = fila[i_cuit]
        if crudo is None:
            continue
        try:
            cuit = str(int(float(str(crudo)))).zfill(11)
        except ValueError:
            continue
        base[cuit] = {
            "razon_social": (str(fila[i_razon]).strip() or None) if fila[i_razon] else None,
            "fob_2024": float(fila[i_2024]) if isinstance(fila[i_2024], (int, float)) else None,
            "fob_2025": float(fila[i_2025]) if isinstance(fila[i_2025], (int, float)) else None,
        }
    wb.close()
    logger.info("Base ANA IMPO cargada: %d CUITs desde %s", len(base), ruta.name)
    return base


def buscar(cuit: str) -> dict | None:
    """Devuelve {razon_social, fob_2024, fob_2025} para el CUIT, o None."""
    global _base
    if _base is None:
        with _lock:
            if _base is None:
                _base = _cargar()
    return _base.get(normalizar_cuit(cuit))


def recargar() -> int:
    """Fuerza la recarga del Excel (por si se actualiza el archivo)."""
    global _base
    with _lock:
        _base = _cargar()
    return len(_base)
