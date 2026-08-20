"""Generación del PDF del plan de negocios con el formato institucional de bind."""

from datetime import date
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .cuit import formatear_cuit

_NEGRO = colors.HexColor("#111111")
_AMARILLO = colors.HexColor("#F8ED09")
_GRIS = colors.HexColor("#5a5a5a")
_GRIS_CLARO = colors.HexColor("#e8e8e8")

_LOGO = Path(__file__).resolve().parent.parent / "static" / "assets" / "logo_bind.png"

DISCLAIMER = (
    "Documento generado automáticamente como borrador interno de trabajo de "
    "Bind Banco Industrial. La información debe ser verificada y el documento "
    "revisado por un analista antes de utilizarse en comunicaciones externas, "
    "documentos legales o decisiones crediticias. El proyectado 2026 es una "
    "estimación aritmética (promedio 2024-2025 + 10%) y no constituye una "
    "proyección financiera avalada."
)


def _moneda(valor: float | None) -> str:
    if valor is None:
        return "Sin datos"
    return f"USD {valor:,.0f}".replace(",", ".")


def _logo_flowable() -> Image | None:
    if not _LOGO.exists():
        return None
    ancho_px, alto_px = ImageReader(str(_LOGO)).getSize()
    ancho = 3.6 * cm
    return Image(str(_LOGO), width=ancho, height=ancho * alto_px / ancho_px)


def generar_pdf(datos: dict) -> bytes:
    """Arma el PDF del plan de negocios y devuelve los bytes.

    `datos` espera: cuit, razon_social, resumen, sitio_web,
    importaciones_2024, importaciones_2025, proyectado_2026, fuentes (opcional).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.6 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        title=f"Plan de Negocios - {datos.get('razon_social') or datos.get('cuit')}",
    )

    estilos = getSampleStyleSheet()
    encabezado_der = ParagraphStyle(
        "EncabezadoDer",
        parent=estilos["Normal"],
        fontSize=9,
        textColor=_GRIS,
        alignment=2,
        leading=13,
    )
    titulo = ParagraphStyle(
        "Titulo",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        textColor=_NEGRO,
        fontSize=24,
        alignment=0,
        spaceBefore=14,
        spaceAfter=8,
    )
    subtitulo = ParagraphStyle(
        "Subtitulo", parent=estilos["Normal"], textColor=_GRIS, fontSize=12, spaceAfter=6
    )
    seccion = ParagraphStyle(
        "Seccion",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        textColor=_NEGRO,
        fontSize=13,
        spaceBefore=18,
        spaceAfter=2,
    )
    cuerpo = ParagraphStyle("Cuerpo", parent=estilos["Normal"], fontSize=10.5, leading=15)
    nota = ParagraphStyle(
        "Nota", parent=estilos["Normal"], fontSize=8, leading=11, textColor=_GRIS
    )

    razon_social = datos.get("razon_social") or "Empresa sin identificar"
    hoy = date.today().strftime("%d/%m/%Y")

    elementos = []

    # Encabezado: logo a la izquierda, área/fecha a la derecha
    logo = _logo_flowable()
    encabezado = Table(
        [
            [
                logo or "",
                Paragraph(
                    f"Negocios Internacionales — COMEX<br/>Buenos Aires, {hoy}",
                    encabezado_der,
                ),
            ]
        ],
        colWidths=[8 * cm, 8.6 * cm],
    )
    encabezado.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elementos.append(encabezado)
    elementos.append(Spacer(1, 6))
    elementos.append(HRFlowable(width="100%", thickness=3, color=_AMARILLO, spaceAfter=2))

    elementos.append(Paragraph("Plan de Negocios", titulo))
    elementos.append(
        Paragraph(f"{razon_social} — CUIT {formatear_cuit(datos['cuit'])}", subtitulo)
    )

    def rotulo(texto: str) -> list:
        return [
            Paragraph(texto, seccion),
            HRFlowable(width="100%", thickness=1, color=_GRIS_CLARO, spaceAfter=8),
        ]

    elementos += rotulo("Perfil de la empresa")
    filas_perfil = [
        ["Razón social", razon_social],
        ["CUIT", formatear_cuit(datos["cuit"])],
        ["Sitio web", datos.get("sitio_web") or "Sin datos"],
    ]
    tabla_perfil = Table(filas_perfil, colWidths=[4.5 * cm, 12.1 * cm])
    tabla_perfil.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (-1, -1), _NEGRO),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, _GRIS_CLARO),
            ]
        )
    )
    elementos.append(tabla_perfil)

    elementos += rotulo("Actividad")
    elementos.append(
        Paragraph(datos.get("resumen") or "Sin información disponible.", cuerpo)
    )

    elementos += rotulo("Importaciones (FOB, fuente base ANA)")
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
    tabla_imp = Table(filas_imp, colWidths=[4.5 * cm, 5 * cm, 7.1 * cm])
    tabla_imp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _NEGRO),
                ("TEXTCOLOR", (0, 0), (-1, 0), _AMARILLO),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fdf9d0")),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9c9c9")),
            ]
        )
    )
    elementos.append(tabla_imp)

    fuentes = [f for f in (datos.get("fuentes") or []) if f]
    if fuentes:
        elementos += rotulo("Fuentes consultadas")
        for fuente in fuentes:
            elementos.append(Paragraph(f"• {fuente}", nota))

    elementos.append(Spacer(1, 26))
    elementos.append(HRFlowable(width="100%", thickness=3, color=_AMARILLO, spaceAfter=6))
    elementos.append(Paragraph(DISCLAIMER, nota))

    doc.build(elementos)
    return buffer.getvalue()
