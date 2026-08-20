"""Enriquecimiento de datos de la empresa vía búsqueda web gratuita (Google).

Busca un resumen de actividad y el sitio web oficial. Los montos de
importaciones NO salen de acá: la fuente es la base ANA IMPO (Excel). Todo
lo que devuelve es un borrador que el usuario revisa y puede corregir antes
de generar el PDF.
"""

from . import google_search


def enriquecer_empresa(cuit: str, razon_social: str | None = None) -> dict:
    """Busca datos de la empresa en la web. Devuelve sitio_web, resumen y fuentes."""
    consulta = (
        f'"{razon_social}" Argentina' if razon_social else f"CUIT {cuit} Argentina empresa"
    )
    resultado = google_search.buscar_empresa(consulta)
    return {
        "razon_social": None,
        "resumen": resultado["resumen"],
        "sitio_web": resultado["sitio_web"],
        "fuentes": resultado["fuentes"],
    }
