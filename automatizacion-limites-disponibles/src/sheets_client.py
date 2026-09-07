"""Actualización de la planilla 'Corresponsalía Local' en Google Sheets.

Busca cada CUIT de la planilla y completa Cupo, Vto cupo, Deuda y
% utilizado con los valores extraídos del Excel de Qlik.

Autenticación (config google_sheets.auth.metodo):
- "oauth" (por defecto): el script edita la planilla como el propio
  usuario. La primera vez abre el navegador para iniciar sesión con la
  cuenta corporativa y guarda el token en token_google.json; después no
  vuelve a pedir login. No hace falta compartir la planilla con nadie.
- "service_account": requiere compartir la planilla con la cuenta de
  servicio (solo si la organización lo permite).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import gspread

from excel_parser import LineaCupo, normalizar_cuit

log = logging.getLogger(__name__)

SCOPES_OAUTH = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def conectar(auth_cfg: dict, base_dir: Path) -> gspread.Client:
    """Devuelve un cliente de gspread según el método de autenticación."""

    def _ruta(nombre: str) -> str:
        p = Path(auth_cfg.get(nombre, ""))
        return str(p if p.is_absolute() else base_dir / p)

    metodo = auth_cfg.get("metodo", "oauth")
    if metodo == "service_account":
        archivo = _ruta("service_account")
        log.info("Autenticando con cuenta de servicio: %s", archivo)
        return gspread.service_account(filename=archivo)

    client_secret = _ruta("client_secret")
    token = _ruta("token")
    if not Path(client_secret).exists():
        raise FileNotFoundError(
            f"No se encontró {client_secret}. Copiá el client_secret.json "
            "(el mismo del proyecto de líneas de corresponsalía sirve) a la "
            "carpeta del proyecto."
        )
    log.info("Autenticando con OAuth de usuario (token: %s)", token)
    return gspread.oauth(
        scopes=SCOPES_OAUTH,
        credentials_filename=client_secret,
        authorized_user_filename=token,
    )


@dataclass
class ResultadoActualizacion:
    actualizados: list[str]
    sin_datos: list[str]      # CUITs de la planilla que no están en el Excel
    con_cupo_vencido: list[str]


def _col_a_indice(letra: str) -> int:
    """'A' -> 1, 'D' -> 4, 'AA' -> 27."""
    indice = 0
    for c in letra.strip().upper():
        indice = indice * 26 + (ord(c) - ord("A") + 1)
    return indice


def _formatear_valor(v):
    """Convierte el valor del Excel a algo que Sheets interprete bien.

    Los valores vacíos se cargan como 0 para no dejar celdas en blanco.
    """
    if v is None:
        return 0
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return 0
    except Exception:
        pass
    return v


def actualizar_planilla(
    cfg: dict,
    base_dir: Path,
    lineas: dict[str, LineaCupo],
    dry_run: bool = False,
) -> ResultadoActualizacion:
    gc = conectar(cfg.get("auth", {}), base_dir)
    sh = gc.open_by_key(cfg["spreadsheet_id"])
    ws = sh.worksheet(cfg.get("worksheet", "Hoja 1"))

    cols = cfg["columnas"]
    col_cuit = _col_a_indice(cols["cuit"])
    fila_encabezados = int(cfg.get("fila_encabezados", 1))

    cuits_planilla = ws.col_values(col_cuit)

    actualizados: list[str] = []
    sin_datos: list[str] = []
    con_cupo_vencido: list[str] = []
    updates = []

    for idx, celda in enumerate(cuits_planilla, start=1):
        if idx <= fila_encabezados:
            continue
        cuit = normalizar_cuit(celda)
        if not cuit:
            continue

        linea = lineas.get(cuit)
        if linea is None:
            # CUIT sin datos en el Excel de Qlik: se carga 0 en todo
            for col in (cols["cupo"], cols["vto_cupo"], cols["deuda"], cols["utilizado"]):
                updates.append({"range": f"{col}{idx}", "values": [[0]]})
            sin_datos.append(cuit)
            log.info("CUIT %s sin datos en el Excel: se carga 0.", cuit)
            continue

        vto_texto = linea.vto_cupo.strftime("%d/%m/%Y") if linea.vto_cupo else 0
        updates.append({
            "range": f"{cols['cupo']}{idx}",
            "values": [[_formatear_valor(linea.cupo)]],
        })
        updates.append({
            "range": f"{cols['vto_cupo']}{idx}",
            "values": [[vto_texto]],
        })
        updates.append({
            "range": f"{cols['deuda']}{idx}",
            "values": [[_formatear_valor(linea.deuda)]],
        })
        updates.append({
            "range": f"{cols['utilizado']}{idx}",
            "values": [[_formatear_valor(linea.utilizado)]],
        })

        actualizados.append(cuit)
        if linea.vencida:
            con_cupo_vencido.append(cuit)
        log.info(
            "CUIT %s -> Cupo: %s | Vto: %s%s | Deuda: %s | %% Utilizado: %s",
            cuit, linea.cupo, vto_texto,
            " (VENCIDO)" if linea.vencida else "",
            linea.deuda, linea.utilizado,
        )

    if dry_run:
        log.info("[DRY-RUN] No se escribe en la planilla (%d celdas pendientes).", len(updates))
    elif updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
        log.info("Planilla actualizada: %d filas.", len(actualizados))
    else:
        log.warning("No hubo coincidencias de CUIT: no se actualizó nada.")

    return ResultadoActualizacion(actualizados, sin_datos, con_cupo_vencido)
