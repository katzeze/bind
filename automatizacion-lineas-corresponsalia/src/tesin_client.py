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

    def _esperar(self, page):
        """Espera a que la página se asiente. Las pantallas de Tesin mantienen
        conexiones abiertas, así que 'networkidle' puede no llegar nunca: si no
        llega en unos segundos, se sigue con una pausa fija."""
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

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
                page = self._login(page)
                for banco in bancos:
                    codigo = banco["codigo"]
                    resultados[codigo] = self._extraer_banco(page, codigo)
            except Exception:
                # Captura del estado exacto en el que se produjo la falla.
                try:
                    self._dump(page, "ERROR")
                except Exception:
                    pass
                raise
            finally:
                browser.close()
        return resultados

    def _login(self, page):
        page.goto(self._url(self.cfg["login_page"]))
        self._esperar(page)
        self._dump(page, "portada")

        # La entrada de Tesin es una portada: el formulario de usuario y
        # contraseña aparece recién después de apretar el botón "Ingresar".
        if page.locator("input[type='password']:visible").count() == 0:
            texto = self.cfg.get("texto_boton_ingresar") or "Ingresar"
            for candidato in (
                page.get_by_role("button", name=texto),
                page.get_by_role("link", name=texto),
                page.get_by_text(texto),
            ):
                if candidato.count() > 0:
                    candidato.first.click()
                    break
            else:
                raise RuntimeError(
                    f"No se encontró el botón '{texto}' en la portada de Tesin. "
                    "Revisar debug/ y ajustar 'texto_boton_ingresar' en config.yaml."
                )
            self._esperar(page)
            # Si el formulario se abrió en otra pestaña, se sigue en esa.
            for otra in page.context.pages:
                if otra.locator("input[type='password']").count() > 0:
                    page = otra
                    break
            page.wait_for_selector("input[type='password']:visible")
        self._dump(page, "login")

        sel_user = self.cfg.get("selector_usuario") or "input[type='text']:visible"
        sel_pass = self.cfg.get("selector_password") or "input[type='password']:visible"
        page.locator(sel_user).first.fill(self.usuario)
        page.locator(sel_pass).first.fill(self.password)

        # El formulario se envía con clic en el botón (Enter no lo dispara).
        sel_boton = self.cfg.get("selector_boton_login")
        if sel_boton:
            page.locator(sel_boton).first.click()
        else:
            texto = self.cfg.get("texto_boton_ingresar") or "Ingresar"
            boton = page.get_by_role("button", name=texto)
            if boton.count() == 0:
                boton = page.get_by_text(texto)
            if boton.count() > 0:
                boton.first.click()
            else:
                page.locator(sel_pass).first.press("Enter")
        self._esperar(page)
        try:
            page.wait_for_selector("input[type='password']", state="hidden", timeout=15000)
        except Exception:
            pass
        self._dump(page, "post_login")

        if page.locator("input[type='password']:visible").count() > 0:
            raise RuntimeError(
                "El login parece haber fallado (sigue visible el campo de contraseña). "
                "Verificar credenciales o ajustar selectores en config.yaml."
            )
        return page

    def _extraer_banco(self, page, codigo: str) -> dict[str, float]:
        # La sesión ya está iniciada: se puede ir directo a la grilla de líneas.
        page.goto(self._url(self.cfg["lineas_page"]))
        self._esperar(page)
        self._dump(page, f"grilla_{codigo}")

        filtro = self._buscar_filtro(page)
        filtro.fill(codigo)
        # La búsqueda se dispara al salir del campo con Tab (Enter no filtra).
        filtro.press("Tab")
        self._esperar(page)
        try:
            page.wait_for_selector(f"tr:has-text('{codigo}')", timeout=15000)
        except Exception:
            pass
        self._dump(page, f"busqueda_{codigo}")

        # En las grillas GeneXus el detalle se abre desde un link en la fila;
        # si la fila no tiene <a>, se hace clic sobre la celda con el código.
        fila = page.locator(f"tr:has-text('{codigo}')").first
        if fila.count() == 0:
            raise RuntimeError(
                f"La búsqueda del corresponsal {codigo} no devolvió ninguna fila. "
                "Verificar el código en config.yaml."
            )
        enlaces = fila.locator("a:visible")
        if enlaces.count() > 0:
            enlaces.first.click()
        else:
            fila.locator("td").filter(has_text=codigo).first.click()
        self._esperar(page)
        self._dump(page, f"detalle_{codigo}")

        lc = self._leer_valor_detalle(page, self.cfg["etiqueta_lc"])
        financ = self._leer_valor_detalle(page, self.cfg["etiqueta_financ"])
        return {"lc": lc, "financ": financ}

    def _buscar_filtro(self, page):
        """Campo de búsqueda por corresponsal en la grilla, salteando el
        buscador del menú lateral ('Buscar opción del menú...')."""
        sel = self.cfg.get("selector_filtro_corresponsal")
        if sel:
            return page.locator(sel).first
        for candidato in page.locator("input:visible").all():
            tipo = (candidato.get_attribute("type") or "text").lower()
            if tipo not in ("text", "search", "tel", "number"):
                continue
            pista = normalizar(
                (candidato.get_attribute("placeholder") or "")
                + " " + (candidato.get_attribute("id") or "")
                + " " + (candidato.get_attribute("name") or "")
            )
            if "menu" in pista:
                continue
            return candidato
        raise RuntimeError(
            "No se encontró el campo de búsqueda en la grilla de líneas. "
            "Revisar debug/ y fijar 'selector_filtro_corresponsal' en config.yaml."
        )

    IMPORTE_RE = r"-?\d[\d.]*,\d{2}"

    def _indice_valor(self, cantidad: int) -> int:
        """Posición del importe 'Utilizado' entre los importes de la fila."""
        fijo = self.cfg.get("indice_columna_valor")
        if fijo is not None:
            return min(int(fijo), cantidad - 1)
        # El detalle muestra Asignado | Utilizado | Saldo: Utilizado es el 2do.
        return 1 if cantidad >= 3 else cantidad - 1

    def _leer_valor_detalle(self, page, etiqueta: str) -> float:
        """Busca la fila cuyo concepto contiene la etiqueta y devuelve el
        importe de la columna 'Utilizado'."""
        etiqueta_norm = normalizar(etiqueta)
        etiqueta_col = normalizar(self.cfg.get("etiqueta_columna_valor", "utilizado"))

        # 1) Grillas armadas con <table>, ubicando la columna por su encabezado.
        for tabla in page.locator("table").all():
            indice_col = None
            for fila in tabla.locator("tr").all():
                celdas = [c.inner_text() for c in fila.locator("td, th").all()]
                celdas_norm = [normalizar(c) for c in celdas]
                if indice_col is None and etiqueta_col in celdas_norm:
                    indice_col = celdas_norm.index(etiqueta_col)
                    continue
                if any(etiqueta_norm in c for c in celdas_norm):
                    if indice_col is not None and indice_col < len(celdas):
                        return parsear_importe(celdas[indice_col])
                    importes = re.findall(self.IMPORTE_RE, " | ".join(celdas))
                    if importes:
                        return parsear_importe(importes[self._indice_valor(len(importes))])

        # 2) Genérico (grillas sin <table>): se ubica el texto del concepto y
        # se sube por sus contenedores hasta encontrar la fila con importes.
        for elemento in page.get_by_text(re.compile(re.escape(etiqueta), re.IGNORECASE)).all():
            contenedor = elemento
            for _ in range(5):
                contenedor = contenedor.locator("xpath=..")
                if contenedor.count() == 0:
                    break
                importes = re.findall(self.IMPORTE_RE, contenedor.inner_text())
                if importes:
                    return parsear_importe(importes[self._indice_valor(len(importes))])

        raise RuntimeError(
            f"No se encontró el concepto '{etiqueta}' en la pantalla de detalle. "
            "Correr con --debug y revisar los archivos en debug/ para ajustar "
            "las etiquetas o selectores en config.yaml."
        )
