"""Automatización: Qlik "Límites & Disponibles" -> planilla "Corresponsalía Local".

Pasos:
1. Ingresa a Qlik Sense con usuario y contraseña.
2. Descarga la tabla "Historico" como Excel (Descargar como... > Datos).
3. Por cada CUIT elige la línea válida: la aún no vencida o, si todas
   vencieron, la última que venció.
4. Completa Cupo, Vto cupo, Deuda y % utilizado en la planilla de Drive.

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
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Automatización Límites & Disponibles")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la planilla")
    parser.add_argument("--debug", action="store_true", help="Guarda capturas de pantalla en debug/")
    parser.add_argument("--archivo", help="Usar un Excel ya descargado en lugar de bajarlo de Qlik")
    args = parser.parse_args()

    configurar_logging()
    log = logging.getLogger("main")

    load_dotenv(BASE_DIR / ".env")
    with open(BASE_DIR / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # ------------------------------------------------------------------
    # 1 y 2: descarga del Excel desde Qlik (salvo que se pase --archivo)
    # ------------------------------------------------------------------
    if args.archivo:
        excel_path = Path(args.archivo)
        if not excel_path.exists():
            log.error("El archivo %s no existe.", excel_path)
            return 1
        log.info("Usando Excel existente: %s", excel_path)
    else:
        qlik_user = os.getenv("QLIK_USER")
        qlik_pass = os.getenv("QLIK_PASS")
        if not qlik_user or not qlik_pass:
            log.error("Faltan QLIK_USER / QLIK_PASS en el archivo .env")
            return 1

        from qlik_client import QlikClient  # import tardío: requiere playwright

        cliente = QlikClient(
            cfg["qlik"],
            user=qlik_user,
            password=qlik_pass,
            download_dir=BASE_DIR / cfg.get("descargas", {}).get("carpeta", "descargas"),
            debug_dir=(BASE_DIR / "debug") if args.debug else None,
        )
        excel_path = cliente.descargar_tabla()

    # ------------------------------------------------------------------
    # 3: parseo y selección de la línea válida por CUIT
    # ------------------------------------------------------------------
    lineas = parsear_excel(excel_path, cfg["excel"]["columnas"])
    if not lineas:
        log.error("El Excel no tiene filas con CUIT: se aborta sin tocar la planilla.")
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
            "CUITs de la planilla SIN datos en el Excel de Qlik: %s",
            ", ".join(resultado.sin_datos),
        )
    log.info("=========================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
