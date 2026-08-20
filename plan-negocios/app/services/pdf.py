"""Generación del PDF del plan de negocios con reportlab."""

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .cuit import formatear_cuit

_AZUL = colors.HexColor("#1a3e6e")
_GRIS = colors.HexColor("#555555")

DISCLAIMER = (
    "Documento generado automáticamente como borrador interno de trabajo. "
    "La información debe ser verificada y el documento revisado por un analista "
    "antes de utilizarse en comunicaciones externas, documentos legales o "
    "decisiones crediticias. El proyectado 2026 es una estimación aritmética "
    "(promedio 2024-2025 + 10%) y no constituye una proyección financiera avalada."
)


def _moneda(valor: float | None) -> str:
    if valor is None:
        return "Sin datos"
    return f"USD {valor:,.0f}".replace(",", ".")


def generar_pdf(datos: dict) -> bytes:
    """Arma el PDF del plan de negocios y devuelve los bytes.

    `datos` espera: cuit, razon_social, resumen, sitio_web,
    importaciones_2024, importaciones_2025, proyectado_2026, fuentes (opcional).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        title=f"Plan de Negocios - {datos.get('razon_social') or datos.get('cuit')}",
    )

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "Titulo", parent=estilos["Title"], textColor=_AZUL, fontSize=22, spaceAfter=4
    )
    subtitulo = ParagraphStyle(
        "Subtitulo", parent=estilos["Normal"], textColor=_GRIS, fontSize=11, spaceAfter=18
    )
    seccion = ParagraphStyle(
        "Seccion",
        parent=estilos["Heading2"],
        textColor=_AZUL,
        fontSize=14,
        spaceBefore=16,
        spaceAfter=6,
    )
    cuerpo = ParagraphStyle("Cuerpo", parent=estilos["Normal"], fontSize=10.5, leading=15)
    nota = ParagraphStyle(
        "Nota", parent=estilos["Normal"], fontSize=8, leading=11, textColor=_GRIS
    )

    razon_social = datos.get("razon_social") or "Empresa sin identificar"
    hoy = date.today().strftime("%d/%m/%Y")

    elementos = [
        Paragraph("Plan de Negocios", titulo),
        Paragraph(f"{razon_social} — CUIT {formatear_cuit(datos['cuit'])} — {hoy}", subtitulo),
        Paragraph("Perfil de la empresa", seccion),
    ]

    filas_perfil = [
        ["Razón social", razon_social],
        ["CUIT", formatear_cuit(datos["cuit"])],
        ["Sitio web", datos.get("sitio_web") or "Sin datos"],
    ]
    tabla_perfil = Table(filas_perfil, colWidths=[4.5 * cm, 11.5 * cm])
    tabla_perfil.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), _AZUL),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#dddddd")),
            ]
        )
    )
    elementos.append(tabla_perfil)

    elementos.append(Paragraph("Actividad", seccion))
    elementos.append(
        Paragraph(datos.get("resumen") or "Sin información disponible.", cuerpo)
    )

    elementos.append(Paragraph("Importaciones", seccion))
    filas_imp = [
        ["Período", "Monto (USD)", "Observación"],
        ["2024", _moneda(datos.get("importaciones_2024")), "Dato relevado"],
        ["2025", _moneda(datos.get("importaciones_2025")), "Dato relevado"],
        [
            "2026 (proyectado)",
            _moneda(datos.get("proyectado_2026")),
            "Promedio 2024-2025 + 10%",
        ],
    ]
    tabla_imp = Table(filas_imp, colWidths=[4.5 * cm, 5 * cm, 6.5 * cm])
    tabla_imp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef3fa")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    elementos.append(tabla_imp)

    fuentes = [f for f in (datos.get("fuentes") or []) if f]
    if fuentes:
        elementos.append(Paragraph("Fuentes consultadas", seccion))
        for fuente in fuentes:
            elementos.append(Paragraph(f"• {fuente}", nota))

    elementos.append(Spacer(1, 24))
    elementos.append(Paragraph(DISCLAIMER, nota))

    doc.build(elementos)
    return buffer.getvalue()
