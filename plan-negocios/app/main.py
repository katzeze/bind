"""Generador de planes de negocios por CUIT — Bind Banco Industrial.

Flujo: se ingresa un CUIT, la app releva razón social e importaciones
2024/2025 desde la base ANA IMPO (Excel) y el padrón ARCA, busca en la
web el resumen de actividad y el sitio oficial, calcula el proyectado
2026 (promedio 2024-2025 + 10%), arma el PDF con el formato del banco
y, previa confirmación del usuario, lo envía por mail al equipo COMEX.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .services import base_impo, enrichment, mailer, padron, pdf
from .services.cuit import cuit_valido, formatear_cuit, normalizar_cuit
from .services.projection import proyectar_2026

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Generador de Plan de Negocios", version="2.0.0")

_STATIC = Path(__file__).parent / "static"


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


@app.get("/api/envio-config")
async def envio_config() -> dict:
    """Destinatarios y cuerpo fijos del mail, para mostrarlos en la UI."""
    return {"destinatarios": config.MAIL_DESTINATARIOS, "cuerpo": config.MAIL_CUERPO}


@app.post("/api/empresa")
async def consultar_empresa(consulta: ConsultaCuit) -> dict:
    """Releva los datos de la empresa y devuelve el borrador editable."""
    cuit = _validar_cuit(consulta.cuit)

    fila_base, razon_padron = await asyncio.gather(
        asyncio.to_thread(base_impo.buscar, cuit),
        padron.buscar_razon_social(cuit),
    )
    razon_social = razon_padron or (fila_base or {}).get("razon_social")
    web = await asyncio.to_thread(enrichment.enriquecer_empresa, cuit, razon_social)

    imp_2024 = (fila_base or {}).get("fob_2024")
    imp_2025 = (fila_base or {}).get("fob_2025")

    proyectado = None
    if imp_2024 is not None and imp_2025 is not None:
        proyectado = proyectar_2026(imp_2024, imp_2025)

    return {
        "cuit": cuit,
        "cuit_formateado": formatear_cuit(cuit),
        "en_base_impo": fila_base is not None,
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
    """Regenera el PDF y lo envía por mail a los destinatarios configurados."""
    datos_pdf = _armar_datos_pdf(envio.datos)
    if not datos_pdf["razon_social"]:
        raise HTTPException(
            status_code=422,
            detail="Falta la razón social: se usa en el asunto del mail.",
        )

    contenido = await asyncio.to_thread(pdf.generar_pdf, datos_pdf)
    nombre = f"plan-negocios-{datos_pdf['cuit']}.pdf"
    asunto = f"Plan de Negocios {datos_pdf['razon_social']}"

    try:
        await asyncio.to_thread(
            mailer.enviar_plan,
            config.MAIL_DESTINATARIOS,
            asunto,
            config.MAIL_CUERPO,
            contenido,
            nombre,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - errores SMTP hacia el usuario
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el mail: {exc}") from exc

    return {
        "ok": True,
        "mensaje": f"Plan enviado a {len(config.MAIL_DESTINATARIOS)} destinatarios.",
        "destinatarios": config.MAIL_DESTINATARIOS,
    }


app.mount("/static", StaticFiles(directory=_STATIC), name="static")
