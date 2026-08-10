"""Automatización semanal: Tesin -> hoja LINEAS CORRESPONSALIA.

Uso:
    python src/main.py              # extrae de Tesin y actualiza la hoja
    python src/main.py --dry-run    # extrae y muestra, sin tocar la hoja
    python src/main.py --debug      # guarda capturas y HTML de cada paso en debug/
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from tesin_client import TesinClient  # noqa: E402
from sheets_client import SheetsClient  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def configurar_logging() -> logging.Logger:
    logs = RAIZ / "logs"
    logs.mkdir(exist_ok=True)
    archivo = logs / f"corrida_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(archivo, encoding="utf-8"), logging.StreamHandler()],
    )
    return logging.getLogger("lineas")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la hoja")
    parser.add_argument("--debug", action="store_true", help="Guarda capturas de cada paso")
    args = parser.parse_args()

    log = configurar_logging()
    load_dotenv(RAIZ / ".env")

    usuario = os.environ.get("TESIN_USER")
    password = os.environ.get("TESIN_PASS")
    if not usuario or not password:
        log.error("Faltan TESIN_USER / TESIN_PASS (ver .env.example).")
        return 1

    config = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
    bancos = [b for b in config["bancos"] if b.get("codigo")]
    omitidos = [b["columna"] for b in config["bancos"] if not b.get("codigo")]
    if omitidos:
        log.warning("Sin código configurado, se omiten: %s", ", ".join(omitidos))
    if not bancos:
        log.error("No hay bancos con código en config.yaml.")
        return 1

    log.info("Extrayendo %d corresponsales de Tesin...", len(bancos))
    tesin = TesinClient(
        config["tesin"], usuario, password,
        debug_dir=RAIZ / "debug" if args.debug else None,
    )
    try:
        datos = tesin.obtener_lineas(bancos)
    except Exception:
        log.exception("Falló la extracción de Tesin. Correr con --debug para diagnosticar.")
        return 1

    for banco in bancos:
        d = datos[banco["codigo"]]
        log.info("%s (%s): LC utilizado=%s | FINANC utilizado=%s",
                 banco["columna"], banco["codigo"], d["lc"], d["financ"])

    if args.dry_run:
        log.info("Dry-run: no se actualizó la hoja.")
        return 0

    sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", str(RAIZ / "service_account.json"))
    try:
        sheets = SheetsClient(config["sheet"], sa_file)
        cambios = sheets.actualizar(bancos, datos)
    except Exception:
        log.exception("Falló la actualización de la hoja de cálculo.")
        return 1

    for cambio in cambios:
        log.info("Actualizado: %s", cambio)
    log.info("Listo: %d celdas actualizadas. Revisar la hoja antes de usar los datos.", len(cambios))
    return 0


if __name__ == "__main__":
    sys.exit(main())
