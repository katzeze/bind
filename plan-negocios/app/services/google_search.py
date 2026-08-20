"""Búsqueda web gratuita vía Google Programmable Search (Custom Search JSON API).

Nivel gratuito: hasta 100 consultas por día. Requiere una clave de API y un
"motor de búsqueda" (cx) creados en una cuenta de Google — ver el README
para el paso a paso. Sin esas dos variables configuradas, la búsqueda queda
deshabilitada y los campos se completan a mano.
"""

import logging
from urllib.parse import urlparse

import httpx

from .. import config

logger = logging.getLogger(__name__)

_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# Dominios que no son el sitio oficial de la empresa (redes sociales,
# directorios, empleo, organismos). Se descartan al elegir "sitio_web".
_DOMINIOS_EXCLUIDOS = (
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "wikipedia.org", "mercadolibre.com", "mercadolibre.com.ar",
    "paginasamarillas.com.ar", "cuitonline.com", "nosis.com", "nosis.com.ar",
    "rapidocuit.com.ar", "boletinoficial.gob.ar", "afip.gob.ar", "arca.gob.ar",
    "google.com", "bing.com", "indeed.com", "computrabajo.com.ar",
    "zonajobs.com.ar", "bumeran.com.ar", "glassdoor.com", "yelp.com",
    "tiktok.com",
)


def _dominio(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _es_sitio_oficial(url: str) -> bool:
    host = _dominio(url)
    return bool(host) and not any(
        host == d or host.endswith("." + d) for d in _DOMINIOS_EXCLUIDOS
    )


def _vacio() -> dict:
    return {"sitio_web": None, "resumen": None, "fuentes": []}


def buscar_empresa(consulta: str) -> dict:
    """Busca `consulta` en Google. Devuelve sitio_web, resumen y fuentes."""
    if not config.GOOGLE_SEARCH_API_KEY or not config.GOOGLE_SEARCH_CX:
        logger.info("Google Custom Search no configurado: se omite la búsqueda web")
        return _vacio()

    try:
        resp = httpx.get(
            _ENDPOINT,
            params={
                "key": config.GOOGLE_SEARCH_API_KEY,
                "cx": config.GOOGLE_SEARCH_CX,
                "q": consulta,
                "num": 5,
                "gl": "ar",
                "hl": "es",
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as exc:  # noqa: BLE001 - la búsqueda web nunca corta el flujo
        logger.warning("Falló la búsqueda en Google para %r: %s", consulta, exc)
        return _vacio()

    if not items:
        return _vacio()

    sitio_web = None
    for item in items:
        link = item.get("link") or ""
        if link and _es_sitio_oficial(link):
            partes = urlparse(link)
            sitio_web = f"{partes.scheme}://{partes.netloc}"
            break

    fragmentos, fuentes = [], []
    for item in items[:3]:
        snippet = (item.get("snippet") or "").replace("\n", " ").strip()
        if snippet:
            fragmentos.append(snippet)
        if item.get("link"):
            fuentes.append(item["link"])

    resumen = " ".join(fragmentos)[:600].strip() or None
    return {"sitio_web": sitio_web, "resumen": resumen, "fuentes": fuentes}
