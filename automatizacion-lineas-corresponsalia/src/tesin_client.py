"""Cliente de Tesin: login, navegación a Líneas de Crédito Recibidas y
extracción de los importes utilizados de LC y Financiaciones por corresponsal.

Tesin es una aplicación GeneXus, por lo que las URLs de detalle llevan
parámetros cifrados y no se pueden construir a mano: la navegación se hace
como lo haría una persona (buscar el corresponsal en la grilla y hacer clic).
"""

import re
import unicodedata
from pathlib import Path


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados, para comparar textos."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def parsear_importe(texto: str) -> float:
    """Convierte un importe en formato es-AR ('1.664.336,91') a float."""
    limpio = re.sub(r"[^\d,.\-]", "", texto)
    if not limpio:
        raise ValueError(f"No se pudo interpretar el importe: {texto!r}")
    limpio = limpio.replace(".", "").replace(",", ".")
    return float(limpio)


class TesinClient:
    def __init__(self, config: dict, usuario: str, password: str, debug_dir: Path | None = None):
        self.cfg = config
        self.usuario = usuario
        self.password = password
        self.debug_dir = debug_dir
        self._paso = 0

    def _url(self, page: str) -> str:
        return f"{self.cfg['base_url']}/{page}"

    def _dump(self, page, nombre: str):
        if not self.debug_dir:
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self._paso += 1
        base = self.debug_dir / f"{self._paso:02d}_{nombre}"
        page.screenshot(path=f"{base}.png", full_page=True)
        Path(f"{base}.html").write_text(page.content(), encoding="utf-8")

    def obtener_lineas(self, bancos: list[dict]) -> dict[str, dict[str, float]]:
        """Devuelve {codigo_banco: {"lc": importe, "financ": importe}}."""
        from playwright.sync_api import sync_playwright

        resultados = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                ignore_https_errors=self.cfg.get("ignorar_errores_tls", True)
            )
            context.set_default_timeout(self.cfg.get("timeout_segundos", 45) * 1000)
            page = context.new_page()
            try:
                self._login(page)
                for banco in bancos:
                    codigo = banco["codigo"]
                    resultados[codigo] = self._extraer_banco(page, codigo)
            finally:
                browser.close()
        return resultados

    def _login(self, page):
        page.goto(self._url(self.cfg["login_page"]))
        self._dump(page, "login")

        sel_user = self.cfg.get("selector_usuario") or "input[type='text']:visible"
        sel_pass = self.cfg.get("selector_password") or "input[type='password']:visible"
        page.locator(sel_user).first.fill(self.usuario)
        page.locator(sel_pass).first.fill(self.password)

        sel_boton = self.cfg.get("selector_boton_login")
        if sel_boton:
            page.locator(sel_boton).first.click()
        else:
            page.locator(sel_pass).first.press("Enter")
        page.wait_for_load_state("networkidle")
        self._dump(page, "post_login")

        if page.locator("input[type='password']:visible").count() > 0:
            raise RuntimeError(
                "El login parece haber fallado (sigue visible el campo de contraseña). "
                "Verificar credenciales o ajustar selectores en config.yaml."
            )

    def _extraer_banco(self, page, codigo: str) -> dict[str, float]:
        # La sesión ya está iniciada: se puede ir directo a la grilla de líneas.
        page.goto(self._url(self.cfg["lineas_page"]))
        page.wait_for_load_state("networkidle")
        self._dump(page, f"grilla_{codigo}")

        sel_filtro = self.cfg.get("selector_filtro_corresponsal") or "input[type='text']:visible"
        filtro = page.locator(sel_filtro).first
        filtro.fill(codigo)
        filtro.press("Enter")
        page.wait_for_load_state("networkidle")
        self._dump(page, f"busqueda_{codigo}")

        # En las grillas GeneXus el detalle se abre desde un link en la fila.
        fila = page.locator(f"tr:has-text('{codigo}')").first
        link = fila.locator("a").first
        link.click()
        page.wait_for_load_state("networkidle")
        self._dump(page, f"detalle_{codigo}")

        lc = self._leer_valor_detalle(page, self.cfg["etiqueta_lc"])
        financ = self._leer_valor_detalle(page, self.cfg["etiqueta_financ"])
        return {"lc": lc, "financ": financ}

    def _leer_valor_detalle(self, page, etiqueta: str) -> float:
        """Busca en las tablas del detalle la fila cuyo concepto contiene la
        etiqueta y devuelve el importe de la columna 'Utilizado'."""
        etiqueta_norm = normalizar(etiqueta)
        col_valor = self.cfg.get("indice_columna_valor")
        etiqueta_col = normalizar(self.cfg.get("etiqueta_columna_valor", "utilizado"))

        for tabla in page.locator("table").all():
            filas = tabla.locator("tr").all()
            indice_col = col_valor
            for fila in filas:
                celdas = [c.inner_text() for c in fila.locator("td, th").all()]
                celdas_norm = [normalizar(c) for c in celdas]
                if indice_col is None and etiqueta_col in celdas_norm:
                    indice_col = celdas_norm.index(etiqueta_col)
                    continue
                if any(etiqueta_norm in c for c in celdas_norm):
                    if indice_col is not None and indice_col < len(celdas):
                        return parsear_importe(celdas[indice_col])
                    # Sin encabezado detectado: se toma el último importe de la fila
                    for celda in reversed(celdas):
                        try:
                            return parsear_importe(celda)
                        except ValueError:
                            continue
        raise RuntimeError(
            f"No se encontró el concepto '{etiqueta}' en la pantalla de detalle. "
            "Correr con --debug y revisar los archivos en debug/ para ajustar "
            "las etiquetas o selectores en config.yaml."
        )
