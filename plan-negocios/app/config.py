import os
from pathlib import Path


def _bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "si", "sí")


_RAIZ = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5").strip()

# Base ANA IMPO 2024/2025: fuente de importaciones y razón social
BASE_IMPO_XLSX = os.getenv(
    "BASE_IMPO_XLSX", str(_RAIZ / "data" / "base_ana_impo_2024_2025.xlsx")
)

# Destinatarios fijos del envío del plan de negocios
_DESTINATARIOS_DEFAULT = (
    "gjaphet@bind.com.ar;"
    "gguastavino@bind.com.ar;"
    "oficialesempresas@bind.com.ar;"
    "dmarmonti@bancoindustrial.com.ar;"
    "ggrasso@bancoindustrial.com.ar;"
    "mmazzocchi@bancoindustrial.com.ar"
)
MAIL_DESTINATARIOS = [
    d.strip()
    for d in os.getenv("MAIL_DESTINATARIOS", _DESTINATARIOS_DEFAULT).replace(",", ";").split(";")
    if d.strip()
]

MAIL_CUERPO = (
    "Buenas, envío en adjunto el plan de negocios de la empresa de referencia.\n"
    "De acuerdo al análisis de la info y elementos aportados, estaríamos OK desde COMEX.\n"
    "Aguardo sus ok a fin de informar a la empresa.\n"
    "Saludos"
)

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "plan-negocios@bind.com.ar").strip()
SMTP_STARTTLS = _bool("SMTP_STARTTLS")
