"""Cálculo del proyectado de importaciones."""

FACTOR_PROYECCION = 1.10  # 10% por encima del promedio 2024-2025


def proyectar_2026(importaciones_2024: float, importaciones_2025: float) -> float:
    """Proyectado 2026 = promedio(2024, 2025) + 10%."""
    promedio = (float(importaciones_2024) + float(importaciones_2025)) / 2
    return round(promedio * FACTOR_PROYECCION, 2)
