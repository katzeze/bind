"""Envío del plan de negocios por mail (SMTP)."""

import smtplib
from email.message import EmailMessage

from .. import config


def enviar_plan(destinatario: str, asunto: str, cuerpo: str, pdf: bytes, nombre_pdf: str) -> None:
    if not config.SMTP_HOST:
        raise RuntimeError(
            "SMTP no configurado: definí SMTP_HOST (y credenciales) en el entorno."
        )

    mensaje = EmailMessage()
    mensaje["From"] = config.SMTP_FROM
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    mensaje.add_attachment(
        pdf, maintype="application", subtype="pdf", filename=nombre_pdf
    )

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
        if config.SMTP_STARTTLS:
            smtp.starttls()
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(mensaje)
