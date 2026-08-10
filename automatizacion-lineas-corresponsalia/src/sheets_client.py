"""Actualización de la hoja LINEAS CORRESPONSALIA en Google Sheets.

Localiza dinámicamente la fila de encabezados de bancos (BNA, SCH, ...) y las
filas UTILIZADO/LC y UTILIZADO/FINANC, así la automatización no se rompe si se
insertan filas o columnas en la hoja.
"""

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, config: dict, service_account_file: str):
        creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        gc = gspread.authorize(creds)
        libro = gc.open_by_key(config["spreadsheet_id"])
        try:
            self.hoja = libro.worksheet(config["worksheet"])
        except gspread.WorksheetNotFound:
            self.hoja = libro.get_worksheet(0)
        self._grilla = self.hoja.get_all_values()

    def _fila_encabezados(self, columnas: list[str]) -> int:
        """Fila (base 0) que contiene los encabezados de los bancos."""
        for i, fila in enumerate(self._grilla):
            valores = [v.strip() for v in fila]
            if sum(1 for c in columnas if c in valores) >= 2:
                return i
        raise RuntimeError("No se encontró la fila con los encabezados de bancos en la hoja.")

    def _fila_utilizado(self, sublinea: str) -> int:
        """Fila (base 0) del bloque UTILIZADO cuya segunda columna es LC o FINANC.

        Las celdas combinadas devuelven el valor solo en la primera fila del
        bloque, por eso se arrastra el último valor no vacío de la columna A.
        """
        bloque_actual = ""
        for i, fila in enumerate(self._grilla):
            if fila and fila[0].strip():
                bloque_actual = fila[0].strip().upper()
            if bloque_actual == "UTILIZADO" and len(fila) > 1 and fila[1].strip().upper() == sublinea:
                return i
        raise RuntimeError(f"No se encontró la fila UTILIZADO / {sublinea} en la hoja.")

    def actualizar(self, bancos: list[dict], datos: dict[str, dict[str, float]]) -> list[str]:
        """Escribe los valores extraídos. Devuelve un detalle de los cambios."""
        columnas = [b["columna"] for b in bancos]
        fila_enc = self._fila_encabezados(columnas)
        encabezados = [v.strip() for v in self._grilla[fila_enc]]
        fila_lc = self._fila_utilizado("LC")
        fila_financ = self._fila_utilizado("FINANC")

        cambios, celdas = [], []
        for banco in bancos:
            codigo, columna = banco["codigo"], banco["columna"]
            if codigo not in datos:
                continue
            if columna not in encabezados:
                raise RuntimeError(f"La columna '{columna}' no está en los encabezados de la hoja.")
            col = encabezados.index(columna)
            for fila, clave in ((fila_lc, "lc"), (fila_financ, "financ")):
                valor_nuevo = datos[codigo][clave]
                valor_anterior = self._grilla[fila][col] if col < len(self._grilla[fila]) else ""
                celdas.append(gspread.Cell(row=fila + 1, col=col + 1, value=valor_nuevo))
                cambios.append(
                    f"{columna} ({codigo}) {clave.upper()}: '{valor_anterior}' -> {valor_nuevo}"
                )
        self.hoja.update_cells(celdas, value_input_option="RAW")
        return cambios
