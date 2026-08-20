import os


def _bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "si", "sí")


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5").strip()

IMPORTS_API_URL = os.getenv("IMPORTS_API_URL", "").strip()
IMPORTS_API_TOKEN = os.getenv("IMPORTS_API_TOKEN", "").strip()

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "plan-negocios@bind.com.ar").strip()
SMTP_STARTTLS = _bool("SMTP_STARTTLS")
