"""Cliente Playwright para Qlik Sense (bi.somosbind.com.ar).

Flujo:
1. Abre la URL de la hoja. Si aparece un formulario de login, completa
   usuario y contraseña (o usa autenticación Windows si está configurada).
2. Espera a que la hoja termine de renderizar.
3. Ubica el objeto (tabla) por su título, abre su menú contextual
   ("...") y ejecuta "Descargar como... > Datos".
4. Captura la descarga del .xlsx y lo guarda en la carpeta de descargas.
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
RE_DESCARGAR = re.compile(r"(descargar como|download as|exportar)", re.IGNORECASE)
RE_DATOS = re.compile(r"^\s*(datos|data)\s*$", re.IGNORECASE)
RE_LINK_DESCARGA = re.compile(r"(clic aquí|click here|descargar el archivo|download the file)", re.IGNORECASE)


class QlikClient:
    def __init__(self, cfg: dict, user: str, password: str, download_dir: Path, debug_dir: Path | None = None):
        self.cfg = cfg
        self.user = user
        self.password = password
        self.download_dir = Path(download_dir)
        self.debug_dir = Path(debug_dir) if debug_dir else None
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
                page.goto(self.cfg["sheet_url"], wait_until="domcontentloaded")

                if not self.cfg.get("windows_auth"):
                    self._login_si_corresponde(page)

                self._esperar_hoja(page)
                self._screenshot(page, "01_hoja_cargada")

                objeto = self._buscar_objeto(page)
                archivo = self._exportar_datos(page, objeto)
                log.info("Excel descargado: %s", archivo)
                return archivo
            except Exception:
                self._screenshot(page, "99_error")
                raise
            finally:
                context.close()
                browser.close()

    # ------------------------------------------------------------------
    def _login_si_corresponde(self, page: Page) -> None:
        """Si la página muestra un formulario de login, lo completa."""
        try:
            pass_input = page.locator("input[type='password']").first
            pass_input.wait_for(state="visible", timeout=10_000)
        except PlaywrightTimeout:
            log.info("No apareció formulario de login (sesión ya iniciada o SSO).")
            return

        log.info("Completando formulario de login...")
        self._screenshot(page, "00_login")

        user_input = page.locator(
            "input[name*='user' i], input[id*='user' i], "
            "input[type='text'], input[type='email']"
        ).first
        user_input.fill(self.user)
        pass_input = page.locator("input[type='password']").first
        pass_input.fill(self.password)

        boton = page.locator(
            "button[type='submit'], input[type='submit'], "
            "button:has-text('Iniciar'), button:has-text('Ingresar'), "
            "button:has-text('Log in'), button:has-text('Login')"
        ).first
        try:
            boton.click(timeout=5_000)
        except PlaywrightTimeout:
            # Sin botón visible: enviamos el form con Enter
            pass_input.press("Enter")

        # Verificar que el login no haya fallado (el form sigue visible)
        time.sleep(3)
        if page.locator("input[type='password']").count() > 0 and page.locator("input[type='password']").first.is_visible():
            raise RuntimeError(
                "El formulario de login sigue visible: revisar usuario/contraseña "
                "(QLIK_USER / QLIK_PASS en el archivo .env)."
            )

    # ------------------------------------------------------------------
    def _esperar_hoja(self, page: Page) -> None:
        """Espera a que los objetos de la hoja Qlik estén renderizados."""
        log.info("Esperando que cargue la hoja...")
        page.wait_for_selector(".qv-object, .qvt-sheet, [tid='qv-object']", timeout=self.timeout_ms)
        # Margen extra para que la tabla termine de poblarse
        page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        time.sleep(3)

    # ------------------------------------------------------------------
    def _buscar_objeto(self, page: Page):
        """Ubica el objeto de la hoja por su título (p. ej. 'Historico')."""
        titulo = self.cfg.get("object_title", "")
        if titulo:
            objeto = page.locator(".qv-object", has=page.get_by_text(titulo, exact=False)).first
            if objeto.count() > 0:
                log.info("Objeto '%s' encontrado por título.", titulo)
                objeto.scroll_into_view_if_needed()
                return objeto
            log.warning("No se encontró un objeto con título '%s'; se usa la primera tabla.", titulo)

        objeto = page.locator(".qv-object-table, .qv-object").first
        objeto.wait_for(state="visible", timeout=self.timeout_ms)
        return objeto

    # ------------------------------------------------------------------
    def _exportar_datos(self, page: Page, objeto) -> Path:
        """Abre el menú del objeto y ejecuta 'Descargar como... > Datos'."""
        log.info("Abriendo menú del objeto...")
        objeto.hover()
        time.sleep(1)

        # Intento 1: botón "..." que aparece al pasar el mouse
        menu_abierto = False
        boton_menu = objeto.locator(
            "[tid='nav-menu'], button[title*='men' i], "
            "button[aria-label*='men' i], .qv-object-nav button"
        ).first
        try:
            boton_menu.click(timeout=5_000)
            menu_abierto = True
        except PlaywrightTimeout:
            log.info("No se pudo clickear el botón '...'; se intenta con clic derecho.")

        # Intento 2: clic derecho sobre el objeto (menú contextual de Qlik)
        if not menu_abierto:
            objeto.click(button="right")

        self._screenshot(page, "02_menu_abierto")

        page.get_by_text(RE_DESCARGAR).first.click(timeout=15_000)
        time.sleep(1)
        self._screenshot(page, "03_submenu_descargar")
        page.get_by_text(RE_DATOS).first.click(timeout=15_000)

        # Diálogo "Exportación completada" con el link de descarga
        log.info("Esperando que Qlik genere el archivo...")
        link = page.get_by_text(RE_LINK_DESCARGA).first
        link.wait_for(state="visible", timeout=self.timeout_ms)
        self._screenshot(page, "04_dialogo_exportacion")

        with page.expect_download(timeout=self.timeout_ms) as download_info:
            link.click()
        download = download_info.value

        destino = self.download_dir / f"limites_disponibles_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        download.save_as(destino)
        return destino

    # ------------------------------------------------------------------
    def _screenshot(self, page: Page, nombre: str) -> None:
        if not self.debug_dir:
            return
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(self.debug_dir / f"{nombre}.png"), full_page=True)
        except Exception:  # el debug nunca debe romper el flujo principal
            log.exception("No se pudo guardar la captura %s", nombre)
