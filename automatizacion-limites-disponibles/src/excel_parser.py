"""Lectura del Excel exportado desde Qlik y selección de la línea válida.

Regla de negocio: si un CUIT tiene varias líneas, se toma la aún no
vencida (Vto Cupo >= hoy); si todas vencieron, la última que venció.
En ambos casos equivale a quedarse con la fila de mayor Vto Cupo.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class LineaCupo:
    cuit: str
    cupo: object
    vto_cupo: date | None
    deuda: object
    utilizado: object
    vencida: bool


def _normalizar(texto: str) -> str:
    """Mayúsculas, sin acentos y con espacios colapsados, para comparar."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def normalizar_cuit(valor) -> str:
    """Deja solo los dígitos del CUIT (maneja guiones, puntos, floats)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\D", "", str(valor))


def _buscar_columna(df: pd.DataFrame, alias: list[str]) -> str:
    normalizadas = {_normalizar(c): c for c in df.columns}
    for a in alias:
        clave = _normalizar(a)
        if clave in normalizadas:
            return normalizadas[clave]
    # Búsqueda parcial (el alias contenido en el nombre de la columna)
    for a in alias:
        clave = _normalizar(a)
        for norm, original in normalizadas.items():
            if clave in norm:
                return original
    raise KeyError(
        f"No se encontró ninguna columna {alias} en el Excel. "
        f"Columnas disponibles: {list(df.columns)}"
    )


def _leer_con_encabezado(path) -> pd.DataFrame:
    """Lee el xlsx buscando la fila de encabezados (la que contiene CUIT)."""
    crudo = pd.read_excel(path, header=None)
    for i in range(min(10, len(crudo))):
        fila = [_normalizar(v) for v in crudo.iloc[i].tolist()]
        if "CUIT" in fila:
            df = pd.read_excel(path, header=i)
            df = df.dropna(how="all")
            return df
    raise ValueError(f"No se encontró una fila de encabezados con 'CUIT' en {path}")


def _parse_fecha(valor) -> date | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and not valor.strip():
        return None
    try:
        parsed = pd.to_datetime(valor, dayfirst=True, errors="coerce")
    except Exception:
        return None
    return None if pd.isna(parsed) else parsed.date()


def parsear_excel(path, columnas_cfg: dict, hoy: date | None = None) -> dict[str, LineaCupo]:
    """Devuelve, por CUIT, la línea válida según la regla de vencimiento."""
    hoy = hoy or date.today()
    df = _leer_con_encabezado(path)

    col_cuit = _buscar_columna(df, columnas_cfg["cuit"])
    col_cupo = _buscar_columna(df, columnas_cfg["cupo"])
    col_vto = _buscar_columna(df, columnas_cfg["vto_cupo"])
    col_deuda = _buscar_columna(df, columnas_cfg["deuda"])
    col_util = _buscar_columna(df, columnas_cfg["utilizado"])
    log.info(
        "Columnas detectadas -> CUIT: %s | Cupo: %s | Vto: %s | Deuda: %s | Utilizado: %s",
        col_cuit, col_cupo, col_vto, col_deuda, col_util,
    )

    resultado: dict[str, LineaCupo] = {}
    df = df.copy()
    df["_cuit"] = df[col_cuit].map(normalizar_cuit)
    df["_vto"] = df[col_vto].map(_parse_fecha)

    for cuit, grupo in df.groupby("_cuit"):
        if not cuit:
            continue
        con_fecha = grupo[grupo["_vto"].notna()]
        if len(con_fecha) > 0:
            # Mayor Vto Cupo: la vigente si existe, si no la última vencida
            fila = con_fecha.loc[con_fecha["_vto"].map(lambda d: d.toordinal()).idxmax()]
        else:
            fila = grupo.iloc[-1]  # sin fechas: se toma la última fila

        vto = fila["_vto"]
        resultado[cuit] = LineaCupo(
            cuit=cuit,
            cupo=fila[col_cupo],
            vto_cupo=vto,
            deuda=fila[col_deuda],
            utilizado=fila[col_util],
            vencida=bool(vto and vto < hoy),
        )

    log.info("Se procesaron %d CUITs del Excel (%d filas).", len(resultado), len(df))
    return resultado
