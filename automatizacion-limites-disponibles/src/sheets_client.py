"""Actualización de la planilla 'Corresponsalía Local' en Google Sheets.

Busca cada CUIT de la planilla y completa Cupo, Vto cupo, Deuda y
% utilizado con los valores extraídos del Excel de Qlik.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import gspread

from excel_parser import LineaCupo, normalizar_cuit

log = logging.getLogger(__name__)


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
    """Convierte el valor del Excel a algo que Sheets interprete bien."""
    if v is None:
        return ""
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return ""
    except Exception:
        pass
    return v


def actualizar_planilla(
    cfg: dict,
    service_account_file: str,
    lineas: dict[str, LineaCupo],
    dry_run: bool = False,
) -> ResultadoActualizacion:
    gc = gspread.service_account(filename=service_account_file)
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
            sin_datos.append(cuit)
            continue

        vto_texto = linea.vto_cupo.strftime("%d/%m/%Y") if linea.vto_cupo else ""
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
