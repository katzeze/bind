"""Generador de planes de negocios por CUIT — Bind Banco Industrial.

Flujo: se ingresa un CUIT, la app releva razón social (padrón ARCA),
resumen de actividad, sitio web e importaciones 2024/2025 (fuente
configurable + búsqueda web), calcula el proyectado 2026 (promedio
2024-2025 + 10%), arma el PDF y, previa confirmación del usuario,
lo envía por mail.
"""

import asyncio
import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .services import enrichment, imports_provider, mailer, padron, pdf
from .services.cuit import cuit_valido, formatear_cuit, normalizar_cuit
from .services.projection import proyectar_2026

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Generador de Plan de Negocios", version="1.0.0")

_STATIC = Path(__file__).parent / "static"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ConsultaCuit(BaseModel):
    cuit: str


class DatosPlan(BaseModel):
    cuit: str
    razon_social: str | None = None
    resumen: str | None = None
    sitio_web: str | None = None
    importaciones_2024: float | None = Field(default=None, ge=0)
    importaciones_2025: float | None = Field(default=None, ge=0)
    fuentes: list[str] = []


class EnvioMail(BaseModel):
    datos: DatosPlan
    destinatario: str


def _validar_cuit(valor: str) -> str:
    cuit = normalizar_cuit(valor)
    if not cuit_valido(cuit):
        raise HTTPException(status_code=422, detail="El CUIT ingresado no es válido.")
    return cuit


def _armar_datos_pdf(datos: DatosPlan) -> dict:
    cuit = _validar_cuit(datos.cuit)
    proyectado = None
    if datos.importaciones_2024 is not None and datos.importaciones_2025 is not None:
        proyectado = proyectar_2026(datos.importaciones_2024, datos.importaciones_2025)
    return {
        "cuit": cuit,
        "razon_social": datos.razon_social,
        "resumen": datos.resumen,
        "sitio_web": datos.sitio_web,
        "importaciones_2024": datos.importaciones_2024,
        "importaciones_2025": datos.importaciones_2025,
        "proyectado_2026": proyectado,
        "fuentes": datos.fuentes,
    }


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


@app.post("/api/empresa")
async def consultar_empresa(consulta: ConsultaCuit) -> dict:
    """Releva los datos de la empresa y devuelve el borrador editable."""
    cuit = _validar_cuit(consulta.cuit)

    razon_social, importaciones = await asyncio.gather(
        padron.buscar_razon_social(cuit),
        imports_provider.buscar_importaciones(cuit),
    )
    web = await asyncio.to_thread(enrichment.enriquecer_empresa, cuit, razon_social)

    imp_2024 = importaciones["2024"]
    imp_2025 = importaciones["2025"]
    if imp_2024 is None:
        imp_2024 = web["importaciones_2024_usd"]
    if imp_2025 is None:
        imp_2025 = web["importaciones_2025_usd"]

    proyectado = None
    if imp_2024 is not None and imp_2025 is not None:
        proyectado = proyectar_2026(imp_2024, imp_2025)

    return {
        "cuit": cuit,
        "cuit_formateado": formatear_cuit(cuit),
        "razon_social": razon_social or web["razon_social"],
        "resumen": web["resumen"],
        "sitio_web": web["sitio_web"],
        "importaciones_2024": imp_2024,
        "importaciones_2025": imp_2025,
        "proyectado_2026": proyectado,
        "fuentes": web["fuentes"],
    }


@app.post("/api/pdf")
async def generar_pdf(datos: DatosPlan) -> Response:
    """Genera el PDF del plan de negocios con los datos ya revisados."""
    contenido = await asyncio.to_thread(pdf.generar_pdf, _armar_datos_pdf(datos))
    nombre = f"plan-negocios-{normalizar_cuit(datos.cuit)}.pdf"
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre}"'},
    )


@app.post("/api/enviar")
async def enviar_por_mail(envio: EnvioMail) -> dict:
    """Regenera el PDF y lo envía por mail al destinatario indicado."""
    if not _EMAIL_RE.match(envio.destinatario.strip()):
        raise HTTPException(status_code=422, detail="El mail del destinatario no es válido.")

    datos_pdf = _armar_datos_pdf(envio.datos)
    contenido = await asyncio.to_thread(pdf.generar_pdf, datos_pdf)
    nombre = f"plan-negocios-{datos_pdf['cuit']}.pdf"
    razon_social = datos_pdf["razon_social"] or f"CUIT {formatear_cuit(datos_pdf['cuit'])}"

    cuerpo = (
        f"Se adjunta el plan de negocios de {razon_social} "
        f"(CUIT {formatear_cuit(datos_pdf['cuit'])}), generado automáticamente.\n\n"
        "Recordá que el documento es un borrador interno y debe ser revisado "
        "antes de usarse en comunicaciones externas o decisiones crediticias."
    )

    try:
        await asyncio.to_thread(
            mailer.enviar_plan,
            envio.destinatario.strip(),
            f"Plan de negocios — {razon_social}",
            cuerpo,
            contenido,
            nombre,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - errores SMTP hacia el usuario
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el mail: {exc}") from exc

    return {"ok": True, "mensaje": f"Plan enviado a {envio.destinatario.strip()}."}


app.mount("/static", StaticFiles(directory=_STATIC), name="static")
