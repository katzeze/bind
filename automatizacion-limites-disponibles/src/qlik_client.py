"""Cliente Playwright para Qlik Sense (bi.somosbind.com.ar).

Flujo:
1. Abre la URL de la hoja y espera a que aparezca el login o la hoja
   (busca el formulario de login también dentro de iframes).
2. Si hay login, completa usuario y contraseña (o usa autenticación
   Windows/NTLM si windows_auth: true en config.yaml).
3. Ubica el objeto (tabla) por su título, abre su menú contextual
   ("...") y ejecuta "Descargar como... > Datos".
4. Captura la descarga del .xlsx y lo guarda en la carpeta de descargas.

Ante cualquier error guarda SIEMPRE captura de pantalla + HTML de la
página en la carpeta debug/, para poder diagnosticar.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

log = logging.getLogger(__name__)

# Textos de menú en español e inglés, por si el cliente Qlik está en otro idioma
RE_DESCARGAR = re.compile(r"(descargar como|download as|export)", re.IGNORECASE)
RE_DATOS = re.compile(r"(exportar datos|export data|^\s*datos\s*$|^\s*data\s*$)", re.IGNORECASE)
RE_LINK_DESCARGA = re.compile(r"(clic aquí|click here|descargar el archivo|download the file)", re.IGNORECASE)

# Selectores que indican que la hoja de Qlik ya está renderizada
SELECTOR_HOJA = ".qv-object, .qvt-sheet, [tid='qv-object'], .njs-cell, .qv-panel-sheet, .sheet-title-container"
# Objetos de tipo tabla (evita filtros, textos y KPIs)
SELECTOR_TABLA = ".qv-object-table, .qv-object-pivot-table, .qv-object-sn-table, .qv-object-sn-pivot-table"


class QlikClient:
    def __init__(self, cfg: dict, user: str, password: str, download_dir: Path,
                 debug_dir: Path, capturas_paso_a_paso: bool = False):
        self.cfg = cfg
        self.user = user
        self.password = password
        self.download_dir = Path(download_dir)
        self.debug_dir = Path(debug_dir)
        self.capturas_paso_a_paso = capturas_paso_a_paso
        self.timeout_ms = int(cfg.get("timeout_seconds", 90)) * 1000

    # ------------------------------------------------------------------
    def descargar_tabla(self) -> Path:
        """Descarga la tabla como Excel y devuelve la ruta del archivo."""
        self.download_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=bool(self.cfg.get("headless", True)))
            context_args = {"accept_downloads": True, "ignore_https_errors": True}
            if self.cfg.get("windows_auth"):
                # Autenticación Windows/NTLM: se resuelve a nivel HTTP
                context_args["http_credentials"] = {"username": self.user, "password": self.password}
            context = browser.new_context(**context_args)
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)

            try:
                log.info("Abriendo Qlik Sense: %s", self.cfg["sheet_url"])
                respuesta = page.goto(self.cfg["sheet_url"], wait_until="domcontentloaded")
                if respuesta is not None:
                    log.info("Respuesta HTTP: %s | URL actual: %s", respuesta.status, page.url)
                    if respuesta.status == 401:
                        if not self.cfg.get("windows_auth"):
                            raise RuntimeError(
                                "El servidor respondió 401 (pide autenticación Windows/NTLM). "
                                "Poné windows_auth: true en config.yaml y volvé a correr."
                            )
                        raise RuntimeError(
                            "El servidor rechazó las credenciales (401). Revisá QLIK_USER y "
                            "QLIK_PASS en el .env; si el usuario está sin dominio, probá el "
                            "formato QLIK_USER=INDUSTRIAL\\tu_usuario."
                        )

                estado = self._esperar_login_u_hoja(page)
                if estado == "login":
                    self._completar_login(page)
                self._esperar_hoja(page)

                log.info("Hoja cargada. Título: %r | URL: %s", page.title(), page.url)
                self._screenshot(page, "01_hoja_cargada")

                objeto = self._buscar_objeto(page)
                archivo = self._exportar_datos(page, objeto)
                log.info("Excel descargado: %s", archivo)
                return archivo
            except Exception:
                self._volcar_diagnostico(page)
                raise
            finally:
                context.close()
                browser.close()

    # ------------------------------------------------------------------
    def _buscar_password_en_frames(self, page: Page):
        """Busca un input de contraseña visible en la página o sus iframes."""
        for frame in page.frames:
            try:
                loc = frame.locator("input[type='password']")
                for i in range(loc.count()):
                    if loc.nth(i).is_visible():
                        return frame, loc.nth(i)
            except Exception:
                continue  # frames que se destruyen mientras iteramos
        return None, None

    # ------------------------------------------------------------------
    def _esperar_login_u_hoja(self, page: Page) -> str:
        """Espera hasta que aparezca el formulario de login o la hoja Qlik."""
        log.info("Esperando login o carga de la hoja...")
        fin = time.monotonic() + self.timeout_ms / 1000
        while time.monotonic() < fin:
            try:
                if page.locator(SELECTOR_HOJA).count() > 0:
                    log.info("La hoja apareció sin pedir login (sesión ya iniciada o SSO).")
                    return "hoja"
                frame, _ = self._buscar_password_en_frames(page)
                if frame is not None:
                    log.info("Formulario de login detectado (frame: %s).", frame.url)
                    return "login"
            except Exception:
                pass
            time.sleep(0.5)

        raise RuntimeError(
            "No apareció ni el login ni la hoja de Qlik en "
            f"{self.timeout_ms // 1000}s. URL actual: {page.url} | "
            f"Título: {page.title()!r}. Revisá los archivos de debug/. "
            "Si la página quedó en blanco, probá windows_auth: true en config.yaml; "
            "si carga pero lento, subí qlik.timeout_seconds."
        )

    # ------------------------------------------------------------------
    def _completar_login(self, page: Page) -> None:
        log.info("Completando formulario de login...")
        self._screenshot(page, "00_login")

        frame, pass_input = self._buscar_password_en_frames(page)
        if pass_input is None:
            raise RuntimeError("Se detectó el login pero desapareció el campo de contraseña.")

        user_input = frame.locator(
            "input[name*='user' i], input[id*='user' i], "
            "input[type='text'], input[type='email']"
        ).first
        user_input.fill(self.user)
        pass_input.fill(self.password)

        boton = frame.locator(
            "button[type='submit'], input[type='submit'], "
            "button:has-text('Iniciar'), button:has-text('Ingresar'), "
            "button:has-text('Acceder'), button:has-text('Log in'), button:has-text('Login')"
        ).first
        try:
            boton.click(timeout=5_000)
        except PlaywrightTimeout:
            # Sin botón visible: enviamos el form con Enter
            pass_input.press("Enter")

        # Verificar que el login no haya fallado (el form sigue visible)
        time.sleep(4)
        frame, pass_visible = self._buscar_password_en_frames(page)
        if pass_visible is not None:
            self._volcar_diagnostico(page)
            raise RuntimeError(
                "El formulario de login sigue visible: revisar usuario/contraseña "
                "(QLIK_USER / QLIK_PASS en el archivo .env)."
            )

    # ------------------------------------------------------------------
    def _esperar_hoja(self, page: Page) -> None:
        """Espera a que la hoja Qlik esté realmente renderizada."""
        log.info("Esperando que cargue la hoja...")
        page.wait_for_selector(SELECTOR_HOJA, timeout=self.timeout_ms)

        # Esperar a que desaparezca el splash "Opening the sheet"
        for texto in ("Opening the sheet", "Abriendo la hoja"):
            try:
                splash = page.get_by_text(texto, exact=False).first
                if splash.count() > 0:
                    splash.wait_for(state="hidden", timeout=self.timeout_ms)
            except Exception:
                pass

        # Esperar a que aparezca al menos una tabla (el objeto que exportamos)
        try:
            page.wait_for_selector(SELECTOR_TABLA, timeout=self.timeout_ms)
        except PlaywrightTimeout:
            log.warning("No apareció ningún objeto de tipo tabla; se seguirá con los objetos genéricos.")

        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except PlaywrightTimeout:
            pass  # Qlik mantiene websockets abiertos; no siempre llega a networkidle
        # Margen extra para que la tabla termine de poblarse
        time.sleep(3)

    # ------------------------------------------------------------------
    def _mas_grande(self, page: Page, selector: str):
        """Devuelve el elemento visible de mayor superficie para el selector."""
        loc = page.locator(selector)
        mejor, mejor_area = None, 0.0
        for i in range(loc.count()):
            el = loc.nth(i)
            try:
                if not el.is_visible():
                    continue
                caja = el.bounding_box()
                if not caja:
                    continue
                area = caja["width"] * caja["height"]
                if area > mejor_area:
                    mejor, mejor_area = el, area
            except Exception:
                continue
        return mejor

    # ------------------------------------------------------------------
    def _buscar_objeto(self, page: Page):
        """Ubica la tabla a exportar.

        Nota: 'Historico' suele ser el título de la HOJA, no del objeto,
        así que la estrategia principal es tomar el objeto de tipo tabla
        más grande de la pantalla (la grilla con los CUITs).
        """
        objeto = self._mas_grande(page, SELECTOR_TABLA)
        if objeto is not None:
            clase = objeto.get_attribute("class") or ""
            log.info("Tabla encontrada por tipo de objeto (class=%r).", clase[:120])
            objeto.scroll_into_view_if_needed()
            return objeto

        titulo = self.cfg.get("object_title", "")
        if titulo:
            candidato = page.locator(".qv-object", has=page.get_by_text(titulo, exact=False)).first
            if candidato.count() > 0 and candidato.is_visible():
                log.info("Objeto encontrado por título '%s'.", titulo)
                candidato.scroll_into_view_if_needed()
                return candidato

        objeto = self._mas_grande(page, ".qv-object, .njs-cell")
        if objeto is None:
            raise RuntimeError("No se encontró ningún objeto exportable en la hoja.")
        log.warning("No hay objetos de tipo tabla; se usa el objeto más grande de la hoja.")
        return objeto

    # ------------------------------------------------------------------
    def _abrir_menu_objeto(self, page: Page, objeto) -> None:
        """Abre el menú contextual del objeto.

        En este Qlik el botón '...' es un <a title="More" class="lui-icon--more">
        dentro de div.qv-object-nav, HERMANO del objeto dentro de la celda
        (.qv-gridcell). Ojo: [tid='nav-menu'] a nivel página es el menú
        hamburguesa global, NO hay que tocarlo.
        """
        objeto.hover()
        time.sleep(1.5)
        self._screenshot(page, "02_hover_objeto")

        selector_mas = (
            ".qv-object-nav a.lui-icon--more, .qv-object-nav [title='More' i], "
            ".qv-object-nav [q-title-translation='Tooltip.ContextMenu']"
        )
        celda = objeto.locator("xpath=ancestor::div[contains(@class,'qv-gridcell')][1]")
        ambitos = ([celda] if celda.count() > 0 else []) + [page]

        for ambito in ambitos:
            botones = ambito.locator(selector_mas)
            for i in range(botones.count()):
                boton = botones.nth(i)
                try:
                    if boton.is_visible():
                        boton.click(timeout=3_000)
                        log.info("Menú del objeto abierto con el botón '...'.")
                        return
                except Exception:
                    continue

        # El botón existe pero puede estar oculto hasta el hover: forzar clic
        try:
            boton = (celda if celda.count() > 0 else page).locator(selector_mas).first
            if boton.count() > 0:
                boton.click(timeout=3_000, force=True)
                log.info("Menú del objeto abierto con el botón '...' (clic forzado).")
                return
        except Exception:
            pass

        log.info("No se encontró el botón '...'; se abre el menú con clic derecho.")
        objeto.click(button="right")

    # ------------------------------------------------------------------
    def _click_item_menu(self, page: Page, patron: re.Pattern, timeout: int = 15_000) -> None:
        """Clickea una entrada de menú por rol o por texto."""
        try:
            item = page.get_by_role("menuitem", name=patron).first
            item.click(timeout=timeout // 2)
            return
        except Exception:
            pass
        page.get_by_text(patron).first.click(timeout=timeout)

    # ------------------------------------------------------------------
    def _exportar_datos(self, page: Page, objeto) -> Path:
        """Abre el menú del objeto y ejecuta 'Descargar como... > Datos'."""
        log.info("Abriendo menú del objeto...")
        self._abrir_menu_objeto(page, objeto)
        time.sleep(1)
        self._screenshot(page, "03_menu_abierto")

        self._click_item_menu(page, RE_DESCARGAR)
        time.sleep(1)
        self._screenshot(page, "04_submenu_descargar")
        # Según la versión de Qlik puede haber submenú ("Download as... > Data")
        # o un único ítem ("Export data"); si no hay submenú, seguimos de largo.
        try:
            self._click_item_menu(page, RE_DATOS, timeout=8_000)
        except Exception:
            log.info("No apareció el submenú de datos; se asume exportación directa.")

        # Diálogo "Exportación completada" con el link de descarga
        log.info("Esperando que Qlik genere el archivo...")
        link = page.get_by_text(RE_LINK_DESCARGA).first
        link.wait_for(state="visible", timeout=self.timeout_ms)
        self._screenshot(page, "05_dialogo_exportacion")

        with page.expect_download(timeout=self.timeout_ms) as download_info:
            link.click()
        download = download_info.value

        destino = self.download_dir / f"limites_disponibles_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        download.save_as(destino)
        return destino

    # ------------------------------------------------------------------
    def _screenshot(self, page: Page, nombre: str) -> None:
        """Captura por paso (solo con --debug)."""
        if not self.capturas_paso_a_paso:
            return
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(self.debug_dir / f"{nombre}.png"), full_page=True)
        except Exception:  # el debug nunca debe romper el flujo principal
            log.exception("No se pudo guardar la captura %s", nombre)

    # ------------------------------------------------------------------
    def _volcar_diagnostico(self, page: Page) -> None:
        """Ante un error guarda SIEMPRE captura + HTML + URL en debug/."""
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            marca = datetime.now().strftime("%Y%m%d_%H%M%S")
            page.screenshot(path=str(self.debug_dir / f"error_{marca}.png"), full_page=True)
            (self.debug_dir / f"error_{marca}.html").write_text(page.content(), encoding="utf-8")
            (self.debug_dir / f"error_{marca}.txt").write_text(
                f"URL: {page.url}\nTitulo: {page.title()}\n", encoding="utf-8"
            )
            log.error("Diagnóstico guardado en %s (error_%s.*)", self.debug_dir, marca)
        except Exception:
            log.exception("No se pudo guardar el diagnóstico del error.")
