"""Automatización: Qlik "Límites & Disponibles" -> planilla "Corresponsalía Local".

Pasos:
1. Ingresa a Qlik Sense con usuario y contraseña.
2. Descarga la tabla "Historico" como Excel (Descargar como... > Datos).
3. Por cada CUIT elige la línea válida: la aún no vencida o, si todas
   vencieron, la última que venció.
4. Completa Cupo, Vto cupo, Deuda y % utilizado en la planilla de Drive.
5. Envía una notificación por correo electrónico con el resultado.

Uso:
    python src/main.py                # ejecución normal
    python src/main.py --dry-run      # no escribe en la planilla
    python src/main.py --debug        # guarda capturas en debug/
    python src/main.py --archivo x.xlsx   # usa un Excel ya descargado
"""

from __future__ import annotations

import argparse
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml
from dotenv import load_dotenv

# El proxy corporativo intercepta HTTPS con su propio certificado.
# truststore hace que Python confíe en el almacén de certificados de
# Windows (igual que Chrome); sin esto, la conexión a Google falla con
# "certificate verify failed: self-signed certificate in certificate chain".
try:
    import truststore

    truststore.inject_into_ssl()
    _TRUSTSTORE_ACTIVO = True
except ImportError:
    _TRUSTSTORE_ACTIVO = False

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from excel_parser import parsear_excel  # noqa: E402
from sheets_client import actualizar_planilla  # noqa: E402


def configurar_logging() -> None:
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / f"corrida_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8"),
        ],
    )


def enviar_correo_notificacion(asunto: str, mensaje: str, cfg: dict, log: logging.Logger) -> None:
    """Envía un correo electrónico de notificación vía SMTP.

    Servidor, remitente y destinatario salen de config.yaml (email:);
    la contraseña de aplicación sale del .env (SMTP_PASSWORD) para no
    dejar secretos en archivos versionados.
    """
    cfg_email = cfg.get("email", {})
    if not cfg_email.get("enabled", False):
        log.info("Envío de notificaciones por correo desactivado en config.yaml.")
        return

    remitente = cfg_email.get("sender_email")
    destinatario = cfg_email.get("recipient_email")
    smtp_server = cfg_email.get("smtp_server", "smtp.gmail.com")
    smtp_port = cfg_email.get("smtp_port", 587)
    # La contraseña va en el .env; se acepta el viejo campo de config
    # solo por compatibilidad (no recomendado).
    password = os.getenv("SMTP_PASSWORD") or cfg_email.get("sender_password")

    if not remitente or not password or not destinatario:
        log.warning(
            "Faltan datos de correo (sender/recipient en config.yaml, "
            "SMTP_PASSWORD en .env). No se enviará notificación."
        )
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = remitente
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.attach(MIMEText(mensaje, "plain", "utf-8"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(remitente, password)
            server.send_message(msg)

        log.info("📧 Correo de notificación enviado exitosamente a %s", destinatario)
    except Exception as e:
        log.error("❌ Error al enviar la notificación por correo: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Automatización Límites & Disponibles")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la planilla")
    parser.add_argument("--debug", action="store_true", help="Guarda capturas de pantalla en debug/")
    parser.add_argument("--archivo", help="Usar un Excel ya descargado en lugar de bajarlo de Qlik")
    args = parser.parse_args()

    configurar_logging()
    log = logging.getLogger("main")

    load_dotenv(BASE_DIR / ".env")
    try:
        with open(BASE_DIR / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        log.critical("Error al cargar config.yaml: %s", e)
        return 1

    # --- Certificados para el proxy corporativo ---
    if _TRUSTSTORE_ACTIVO:
        log.info("truststore activo: se usa el almacén de certificados de Windows.")
    else:
        log.warning(
            "truststore NO está instalado: la conexión a Google va a fallar detrás "
            "del proxy del banco. Ejecutar en el entorno virtual: pip install truststore"
        )

    ca_bundle = os.getenv("CA_BUNDLE")
    if ca_bundle:
        if Path(ca_bundle).exists():
            os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle
            os.environ["SSL_CERT_FILE"] = ca_bundle
            log.info("Usando CA_BUNDLE: %s", ca_bundle)
        else:
            log.warning("CA_BUNDLE apunta a un archivo inexistente: %s", ca_bundle)

    try:
        # ------------------------------------------------------------------
        # 1 y 2: descarga del Excel desde Qlik (salvo que se pase --archivo)
        # ------------------------------------------------------------------
        if args.archivo:
            excel_path = Path(args.archivo)
            if not excel_path.exists():
                error_msg = f"El archivo especificado {excel_path} no existe."
                log.error(error_msg)
                enviar_correo_notificacion("🔴 ERROR: Automatización Límites & Disponibles", error_msg, cfg, log)
                return 1
            log.info("Usando Excel existente: %s", excel_path)
        else:
            qlik_user = os.getenv("QLIK_USER")
            qlik_pass = os.getenv("QLIK_PASS")
            if not qlik_user or not qlik_pass:
                error_msg = "Faltan las credenciales QLIK_USER / QLIK_PASS en el archivo .env"
                log.error(error_msg)
                enviar_correo_notificacion("🔴 ERROR: Automatización Límites & Disponibles", error_msg, cfg, log)
                return 1

            from qlik_client import QlikClient  # import tardío: requiere playwright

            cliente = QlikClient(
                cfg["qlik"],
                user=qlik_user,
                password=qlik_pass,
                download_dir=BASE_DIR / cfg.get("descargas", {}).get("carpeta", "descargas"),
                debug_dir=BASE_DIR / "debug",
                capturas_paso_a_paso=args.debug,
            )
            excel_path = cliente.descargar_tabla()

        # ------------------------------------------------------------------
        # 3: parseo y selección de la línea válida por CUIT
        # ------------------------------------------------------------------
        lineas = parsear_excel(excel_path, cfg["excel"]["columnas"])
        if not lineas:
            error_msg = "El Excel descargado no tiene filas con CUIT válidos. Se aborta la actualización."
            log.error(error_msg)
            enviar_correo_notificacion("🔴 ERROR: Automatización Límites & Disponibles", error_msg, cfg, log)
            return 1

        # ------------------------------------------------------------------
        # 4: actualización de la planilla "Corresponsalía Local"
        # ------------------------------------------------------------------
        resultado = actualizar_planilla(
            cfg["google_sheets"], BASE_DIR, lineas, dry_run=args.dry_run
        )

        log.info("================ RESUMEN ================")
        log.info("Filas actualizadas: %d", len(resultado.actualizados))
        if resultado.con_cupo_vencido:
            log.warning(
                "CUITs con cupo VENCIDO (se cargó la última línea vencida): %s",
                ", ".join(resultado.con_cupo_vencido),
            )
        if resultado.sin_datos:
            log.warning(
                "CUITs de la planilla sin datos en el Excel de Qlik (se cargó 0): %s",
                ", ".join(resultado.sin_datos),
            )
        log.info("=========================================")

        # ------------------------------------------------------------------
        # 5: Notificación por correo electrónico de éxito
        # ------------------------------------------------------------------
        cuerpo_exito = (
            "El proceso de actualización finalizó correctamente.\n\n"
            f"• Filas actualizadas: {len(resultado.actualizados)}\n"
            f"• CUITs con cupo vencido: {len(resultado.con_cupo_vencido)}\n"
            f"• CUITs sin datos en Qlik: {len(resultado.sin_datos)}\n"
            f"• Modo de ejecución: {'DRY-RUN (Sin escritura)' if args.dry_run else 'NORMAL'}\n"
            f"• Archivo procesado: {excel_path.name}"
        )
        enviar_correo_notificacion("🟢 ÉXITO: Automatización Límites & Disponibles", cuerpo_exito, cfg, log)
        return 0

    except Exception as e:
        log.exception("Ocurrió un error irrecuperable durante la ejecución:")
        cuerpo_error = (
            "Se produjo un fallo inesperado durante la automatización.\n\n"
            f"Detalle del error:\n{str(e)}\n\n"
            "Revisa los archivos en la carpeta /logs para obtener más información."
        )
        enviar_correo_notificacion("🔴 ERROR: Automatización Límites & Disponibles", cuerpo_error, cfg, log)
        return 1


if __name__ == "__main__":
    sys.exit(main())
