import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.cuit import cuit_valido, formatear_cuit, normalizar_cuit
from app.services.pdf import generar_pdf
from app.services.projection import proyectar_2026


def test_proyeccion_es_promedio_mas_diez_por_ciento():
    assert proyectar_2026(100.0, 200.0) == 165.0
    assert proyectar_2026(1_000_000, 1_000_000) == 1_100_000.0
    assert proyectar_2026(0, 0) == 0.0


def test_normalizar_cuit():
    assert normalizar_cuit("30-71234567-0") == "30712345670"
    assert normalizar_cuit(" 20.123.456.78 9 ") == "20123456789"


def test_cuit_valido():
    # CUIT con dígito verificador correcto
    assert cuit_valido("30-58189298-1")
    assert not cuit_valido("30-58189298-2")  # verificador incorrecto
    assert not cuit_valido("123")
    assert not cuit_valido("99-12345678-0")  # prefijo inexistente


def test_formatear_cuit():
    assert formatear_cuit("30581892981") == "30-58189298-1"


def test_generar_pdf_completo():
    datos = {
        "cuit": "30581892981",
        "razon_social": "Empresa de Prueba S.A.",
        "resumen": "Se dedica a la importación de maquinaria industrial.",
        "sitio_web": "https://ejemplo.com.ar",
        "importaciones_2024": 1_500_000.0,
        "importaciones_2025": 2_500_000.0,
        "proyectado_2026": proyectar_2026(1_500_000.0, 2_500_000.0),
        "fuentes": ["https://ejemplo.com.ar/prensa"],
    }
    pdf = generar_pdf(datos)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_generar_pdf_sin_datos_opcionales():
    pdf = generar_pdf({"cuit": "30581892981"})
    assert pdf.startswith(b"%PDF")


def test_base_impo_lee_excel(tmp_path, monkeypatch):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Datos Filtrados"
    ws.append(["CUIT", "Razon Social", "FOB 2025", "FOB 2024"])
    ws.append([30581892981.0, "EMPRESA DE PRUEBA SA", 2500000.5, 1500000.25])
    ws.append(["texto invalido", "OTRA", 1, 2])
    ruta = tmp_path / "base.xlsx"
    wb.save(ruta)

    from app import config
    from app.services import base_impo

    monkeypatch.setattr(config, "BASE_IMPO_XLSX", str(ruta))
    base_impo.recargar()

    fila = base_impo.buscar("30-58189298-1")
    assert fila == {
        "razon_social": "EMPRESA DE PRUEBA SA",
        "fob_2024": 1500000.25,
        "fob_2025": 2500000.5,
    }
    assert base_impo.buscar("20-12345678-6") is None


def test_destinatarios_configurados():
    from app import config

    assert "gjaphet@bind.com.ar" in config.MAIL_DESTINATARIOS
    assert len(config.MAIL_DESTINATARIOS) == 6
    assert "COMEX" in config.MAIL_CUERPO
