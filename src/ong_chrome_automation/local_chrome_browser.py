from __future__ import annotations

import os
import random
import time
import asyncio
from typing import Optional, List, Dict, Union, Any

from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

try:
    from ong_chrome_automation.capture_headers import CaptureHeaders
except ImportError:
    from capture_headers import CaptureHeaders


import asyncio

class LocalChromeBrowser:
    """
    Un único wrapper que puede usarse:
      - Sincrónico:   with LocalChromeBrowser(...) as b: ...
      - Asíncrono:    async with LocalChromeBrowser(...) as b: ...

    Y además expone métodos:
      - sync: goto(), random_delay(), close()
      - async: a_goto(), a_random_delay(), a_close()
    """

    def __init__(
        self,
        origin: Optional[str] = None,
        pfxPath: Optional[str] = None,
        passphrase: Optional[str] = None,
        cert_config: Optional[List[Dict[str, Any]]] = None,
        visible: bool = True,
        add_stealth_scrips: bool = False,
        capture_headers: bool | list | None = None,
        executable_path: str = "C:/Program Files/Google/Chrome/Application/chrome.exe",
    ):
        self.playwright = None
        self.context = None
        self.page = None

        self.visible = visible
        self.add_stealth_scrips = add_stealth_scrips

        self.capture_headers = None
        self.__capture_headers_cfg = capture_headers

        self.executable_path = executable_path

        # Modo actual: "sync" o "async" (se fija en __enter__/__aenter__)
        self._mode: Optional[str] = None

        # Validación de certs (igual que tu código)
        cert_params = [origin, pfxPath, passphrase]
        if any(cert_params) and not all(cert_params):
            raise ValueError(
                "All certificate parameters (origin, path, and password) must be provided together"
            )

        self.cert_config = cert_config or None
        if all(cert_params):
            self.cert_config = [
                {
                    "origin": origin,
                    "pfxPath": pfxPath,
                    "passphrase": passphrase,
                }
            ]

    # -----------------------
    # Context management sync
    # -----------------------
    def __enter__(self) -> "LocalChromeBrowser":
        self._mode = "sync"
        self.playwright = sync_playwright().start()

        context_options = self._build_context_options()
        if self.cert_config:
            context_options["client_certificates"] = self.cert_config

        self.context = self.playwright.chromium.launch_persistent_context(**context_options)

        if self.__capture_headers_cfg:
            self.capture_headers = CaptureHeaders(self.context, self.__capture_headers_cfg)

        self.page = self.context.new_page()
        self._add_stealth_scripts_sync()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ------------------------
    # Context management async
    # ------------------------
    async def __aenter__(self) -> "LocalChromeBrowser":
        self._mode = "async"
        try:
            self.playwright = await async_playwright().start()
        except NotImplementedError:
            print("Are you using this code in windows inside a Jupyter Notebook or Lab? If so, create an async function and run it wrapped in run_playwright_jupyter")
            print("Example code:")
            print("""from ong_chrome_automation.jupyter import run_playwright_jupyter
            async def main():
                async with LocalChromeBrowser() as browser:
                    await browser.a_goto("http://example.com")
            
            run_playwright_jupyter(main())""")
            raise

        context_options = self._build_context_options()
        if self.cert_config:
            context_options["client_certificates"] = self.cert_config

        self.context = await self.playwright.chromium.launch_persistent_context(**context_options)

        if self.__capture_headers_cfg:
            # Normalmente funciona igual porque se engancha a eventos del context.
            # Si tu CaptureHeaders internamente usa cosas sync, aquí sería donde
            # harías una variante async. De momento lo mantenemos como en tu versión.
            self.capture_headers = CaptureHeaders(self.context, self.__capture_headers_cfg)

        self.page = await self.context.new_page()
        await self._add_stealth_scripts_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.a_close()

    # -------------
    # Shared helpers
    # -------------
    def _get_user_profile_dir(self) -> str:
        # Tu ruta original (Windows) + fallback razonable
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return os.path.join(local_appdata, "Google/Chrome/User Data/Default")
        return os.path.join(os.path.expanduser("~"), ".config", "google-chrome", "Default")

    def _build_context_options(self) -> Dict[str, Any]:
        user_profile = self._get_user_profile_dir()

        context_options: Dict[str, Any] = {
            "user_data_dir": user_profile,
            "channel": "chrome",
            "headless": not self.visible,
            "executable_path": self.executable_path,
            "ignore_https_errors": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-automation",
                "--disable-extensions",
                # Session restore prevention
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--disable-restore-session-state",
                "--disable-sync",
                "--disable-crash-reporter",
            ],
            "bypass_csp": True,
        }
        return context_options

    @property
    def headers(self) -> dict:
        if self.capture_headers:
            return self.capture_headers.headers
        return {}

    # -----------------
    # Stealth injection
    # -----------------
    _STEALTH_JS = r"""
        // Overwrite the automation-related properties
        const overwriteProperties = {
            webdriver: undefined,
            __driver_evaluate: undefined,
            __webdriver_evaluate: undefined,
            __selenium_evaluate: undefined,
            __fxdriver_evaluate: undefined,
            __driver_unwrapped: undefined,
            __webdriver_unwrapped: undefined,
            __selenium_unwrapped: undefined,
            __fxdriver_unwrapped: undefined,
            _Selenium_IDE_Recorder: undefined,
            calledSelenium: undefined,
            _selenium: undefined,
            callSelenium: undefined,
            _WEBDRIVER_ELEM_CACHE: undefined,
            ChromeDriverw: undefined,
            domAutomation: undefined,
            domAutomationController: undefined,
        };

        Object.keys(overwriteProperties).forEach(prop => {
            Object.defineProperty(window, prop, {
                get: () => overwriteProperties[prop],
                set: () => {}
            });
            Object.defineProperty(navigator, prop, {
                get: () => overwriteProperties[prop],
                set: () => {}
            });
        });

        delete navigator.__proto__.webdriver;
    """

    def _add_stealth_scripts_sync(self) -> None:
        if self.add_stealth_scrips and self.page:
            self.page.add_init_script(self._STEALTH_JS)

    async def _add_stealth_scripts_async(self) -> None:
        if self.add_stealth_scrips and self.page:
            await self.page.add_init_script(self._STEALTH_JS)

    # ------------------------
    # Public API (sync methods)
    # ------------------------
    def goto(self, url: str) -> "LocalChromeBrowser":
        if self._mode != "sync":
            raise RuntimeError("Este objeto está en modo async. Usa: await a_goto(url)")
        self.page.goto(url, wait_until="networkidle")
        return self

    def random_delay(self, min_seconds: float = 1, max_seconds: float = 3) -> "LocalChromeBrowser":
        if self._mode != "sync":
            raise RuntimeError("Este objeto está en modo async. Usa: await a_random_delay(...)")
        time.sleep(random.uniform(min_seconds, max_seconds))
        return self

    def close(self) -> None:
        # Cierre sync (idempotente)
        if self._mode and self._mode != "sync":
            raise RuntimeError("Este objeto está en modo async. Usa: await a_close()")

        try:
            if self.context:
                self.context.close()
        finally:
            self.context = None

        try:
            if self.playwright:
                self.playwright.stop()
        finally:
            self.playwright = None
            self._mode = None
            self.page = None
            self.capture_headers = None

    # -------------------------
    # Public API (async methods)
    # -------------------------
    async def a_goto(self, url: str) -> "LocalChromeBrowser":
        if self._mode != "async":
            raise RuntimeError("Este objeto está en modo sync. Usa: goto(url)")
        await self.page.goto(url, wait_until="networkidle")
        return self

    async def a_random_delay(self, min_seconds: float = 1, max_seconds: float = 3) -> "LocalChromeBrowser":
        if self._mode != "async":
            raise RuntimeError("Este objeto está en modo sync. Usa: random_delay(...)")
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))
        return self

    async def a_close(self) -> None:
        # Cierre async (idempotente)
        if self._mode and self._mode != "async":
            raise RuntimeError("Este objeto está en modo sync. Usa: close()")

        try:
            if self.context:
                await self.context.close()
        finally:
            self.context = None

        try:
            if self.playwright:
                await self.playwright.stop()
        finally:
            self.playwright = None
            self._mode = None
            self.page = None
            self.capture_headers = None

    # -----------------
    # Destructor (best effort)
    # -----------------
    def __del__(self):
        # Evitamos cosas async en __del__. Si estaba en sync y quedó abierto, cerramos.
        try:
            if self._mode == "sync":
                self.close()
        except Exception:
            pass


# -----------------
# Example usage
# -----------------
if __name__ == "__main__":

    # Basic usage without certificates
    with LocalChromeBrowser() as browser:
        browser.goto("https://example.com")
        browser.random_delay()
    
    from pathlib import Path

    # test if certificates are valid
    certificate_path = "./path/to/cert.pfx"
    if Path(certificate_path).exists():
        # Usage with certificates
        with LocalChromeBrowser(
            origin="https://your-server.com",
            pfxPath="./path/to/cert.pfx",
            passphrase="your-password"
        ) as browser:
            browser.goto("https://your-server.com")
            # Your code here...

    # Async
    async def main():
        async with LocalChromeBrowser(capture_headers=True) as browser:
            await browser.a_goto("https://example.com")
            await browser.a_random_delay()
            # await browser.page.click(...)

    asyncio.run(main())
