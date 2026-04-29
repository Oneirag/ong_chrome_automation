"""playwright_copilot

High-level automation helpers for Microsoft Copilot web chat using Playwright.

This module supports BOTH Playwright sync and async APIs.

Design:
- Sync usage: instantiate normally and call sync methods.
- Async usage: create instances with `await Class.acreate(...)` and call async methods prefixed with `a*`.

Why `acreate`?
Playwright's async API requires awaiting navigation/login steps; Python constructors cannot be async.

Example (sync):
    with LocalChromeBrowser() as browser:
        copilot = M365CopilotAutomation(browser)
        copilot.chat("Hello")
        print(copilot.get_text_response())

Example (async):
    async with LocalChromeBrowser() as browser:
        copilot = await M365CopilotAutomation.acreate(browser)
        await copilot.achat("Hello")
        print(await copilot.aget_text_response())
"""

from __future__ import annotations

import asyncio
import io
import inspect
import re
import time
import warnings
from pathlib import Path
from typing import Any, List, Optional, Sequence, Union

import pandas as pd

# Playwright sync & async imports
from playwright.sync_api import ElementHandle as SyncElementHandle
from playwright.sync_api import expect as sync_expect

from playwright.async_api import ElementHandle as AsyncElementHandle
from playwright.async_api import expect as async_expect

try:
    from ong_chrome_automation.local_chrome_browser import LocalChromeBrowser
    from ong_chrome_automation.exceptions import CopilotExceedsMaxLengthError, CopilotTimeoutError
except ImportError:
    from local_chrome_browser import LocalChromeBrowser
    from exceptions import CopilotExceedsMaxLengthError, CopilotTimeoutError


ElementHandle = Union[SyncElementHandle, AsyncElementHandle]


class ElementNotFoundException(Exception):
    pass


def _as_list(x: Union[str, Sequence[str]]) -> List[str]:
    if isinstance(x, str):
        return [x]
    return list(x)


def _is_async_page(page: Any) -> bool:
    """Best-effort detection of Playwright async Page/Locator API."""
    try:
        return inspect.iscoroutinefunction(page.goto)
    except Exception:
        return False


# -----------------
# File chooser helpers
# -----------------

def select_file(page: Any, locator: Any, file_path: Union[str, Path]):
    """Select a file in sync mode using the system's native dialog."""
    file_path = Path(file_path).expanduser().resolve()
    try:
        with page.expect_file_chooser(timeout=10000) as fc_info:
            locator.click()
        file_chooser = fc_info.value
        file_chooser.set_files(str(file_path))
    except Exception as e:
        raise RuntimeError(f"Error selecting file {file_path}: {e}") from e


async def aselect_file(page: Any, locator: Any, file_path: Union[str, Path]):
    """Select a file in async mode using the system's native dialog."""
    file_path = Path(file_path).expanduser().resolve()
    try:
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await locator.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(str(file_path))
    except Exception as e:
        raise RuntimeError(f"Error selecting file {file_path}: {e}") from e


class CopilotChatAutomation:
    """Automation for Copilot web chat.

    Supports both sync and async Playwright via dual APIs:
    - Sync methods: `chat`, `get_text_response`, ...
    - Async methods: `achat`, `aget_text_response`, ...

    Async instances MUST be created with `await CopilotChatAutomation.acreate(...)`.
    """

    ANSWER_TIMEOUT = 120e3  # 2 minutes (ms)
    WAIT_DIVS_TIMEOUT = 30e3  # 30 seconds (ms)
    LOGIN_TIMEOUT = 10e3  # 10 seconds (ms)

    URL = "https://m365.cloud.microsoft/chat"

    ROLE_CHAT_PLACEHOLDER = ["textbox", "combobox"]
    NAME_CHAT_PLACEHOLDER = "Entrada del chat"
    NAME_SEND_BUTTON = ["Enviar", "Send"]

    TESTID_PLUS_BUTTON = "PlusMenuButton"  # Formerly PlusMenuButtonUploadMenu
    TEXT_UPLOAD_FILE = "Cargar imágenes y archivos"  # Formerly Cargar desde este dispositivo

    CHAR_LIMIT = 8000

    # Fallback selector for code lines in M365 style responses
    CODE_LOCATOR = ".scriptor-paragraph"

    def __init__(self, browser: LocalChromeBrowser, url: Optional[str] = None, use_work: bool = True, *, defer_init: bool = False):
        self.browser = browser
        self.use_work = use_work
        self.url = url or self.URL

        self.page = self.browser.page
        self._async = _is_async_page(self.page)

        self.response_locator = None
        self.user_messages = 0

        if not defer_init:
            if self._async:
                raise RuntimeError(
                    "Async Playwright detected. Create this class with: `await CopilotChatAutomation.acreate(browser, ...)`"
                )
            self._init_sync()

    # --------
    # Creation
    # --------
    @classmethod
    async def acreate(cls, browser: LocalChromeBrowser, url: Optional[str] = None, use_work: bool = True):
        self = cls(browser, url=url, use_work=use_work, defer_init=True)
        if self._async:
            await self._init_async()
        else:
            # Allow calling acreate even for sync browsers (useful for uniform factories)
            self._init_sync()
        return self

    # ----------------
    # Initialization
    # ----------------
    def _init_sync(self):
        # Extend browser default timeout
        try:
            self.browser.context.set_default_timeout(30e3)
        except Exception:
            pass

        self.page.goto(self.url, wait_until="domcontentloaded")

        login_button = self.page.get_by_role("button", name=re.compile(r"^Iniciar sesión.*", re.IGNORECASE))
        login_link = self.page.get_by_role("link", name=re.compile(r"^Iniciar sesión como.*", re.IGNORECASE))

        visible_login_button = False
        visible_login_link = False
        try:
            visible_login_button = login_button.is_visible(timeout=self.LOGIN_TIMEOUT)
        except Exception:
            pass
        try:
            visible_login_link = login_link.is_visible(timeout=self.LOGIN_TIMEOUT)
        except Exception:
            pass

        if visible_login_button or visible_login_link:
            (login_button if visible_login_button else login_link).click()
            time.sleep(self.LOGIN_TIMEOUT / 1000)

        self.response_locator = None
        self.user_messages = 0
        self.new_chat()

    async def _init_async(self):
        try:
            await self.browser.context.set_default_timeout(30e3)
        except Exception:
            try:
                self.browser.context.set_default_timeout(30e3)
            except Exception:
                pass

        await self.page.goto(self.url, wait_until="domcontentloaded")

        login_button = self.page.get_by_role("button", name=re.compile(r"^Iniciar sesión.*", re.IGNORECASE))
        login_link = self.page.get_by_role("link", name=re.compile(r"^Iniciar sesión como.*", re.IGNORECASE))

        visible_login_button = False
        visible_login_link = False
        try:
            visible_login_button = await login_button.is_visible(timeout=self.LOGIN_TIMEOUT)
        except Exception:
            pass
        try:
            visible_login_link = await login_link.is_visible(timeout=self.LOGIN_TIMEOUT)
        except Exception:
            pass

        if visible_login_button or visible_login_link:
            if visible_login_button:
                await login_button.click()
            else:
                await login_link.click()
            await asyncio.sleep(self.LOGIN_TIMEOUT / 1000)

        self.response_locator = None
        self.user_messages = 0
        await self.anew_chat()

    # ----------------------
    # Element helper methods
    # ----------------------
    def get_element_by_role_name(
        self,
        roles: Union[str, Sequence[str]],
        names: Union[str, Sequence[str]],
        *,
        timeout: int = 200,
        raise_exception: bool = True,
    ):
        """Sync: find a visible element for any of the given roles/names."""
        roles = _as_list(roles)
        names = _as_list(names)

        for role in roles:
            for name in names:
                element = self.page.get_by_role(role, name=name)
                try:
                    if element.is_visible(timeout=timeout):
                        return element
                except Exception:
                    continue

        if raise_exception:
            raise ElementNotFoundException(f"No element found with role {roles} and name {names}")
        return None

    async def aget_element_by_role_name(
        self,
        roles: Union[str, Sequence[str]],
        names: Union[str, Sequence[str]],
        *,
        timeout: int = 200,
        raise_exception: bool = True,
    ):
        """Async: find a visible element for any of the given roles/names."""
        roles = _as_list(roles)
        names = _as_list(names)

        for role in roles:
            for name in names:
                element = self.page.get_by_role(role, name=name)
                try:
                    if await element.is_visible(timeout=timeout):
                        return element
                except Exception:
                    continue

        if raise_exception:
            raise ElementNotFoundException(f"No element found with role {roles} and name {names}")
        return None

    # ---------
    # Sessions
    # ---------
    def new_chat(self):
        """Sync: Creates a new chat session."""
        self.page.get_by_test_id("newChatButton").click()

        if self.use_work:
            try:
                self.page.get_by_test_id("toggle-work").click(timeout=500)
            except Exception:
                # Some tenants show only one mode
                pass
        else:
            try:
                self.page.get_by_test_id("toggle-web").click(timeout=500)
            except Exception:
                pass

        self.user_messages = 0

    async def anew_chat(self):
        """Async: Creates a new chat session."""
        await self.page.get_by_test_id("newChatButton").click()

        if self.use_work:
            try:
                await self.page.get_by_test_id("toggle-work").click(timeout=500)
            except Exception:
                pass
        else:
            try:
                await self.page.get_by_test_id("toggle-web").click(timeout=500)
            except Exception:
                pass

        self.user_messages = 0

    # ------------
    # Chat input
    # ------------
    def __fill_chat_input(self, message: str):
        chat_input = self.get_element_by_role_name(self.ROLE_CHAT_PLACEHOLDER, names=self.NAME_CHAT_PLACEHOLDER)
        chat_input.fill(message)

    async def __afill_chat_input(self, message: str):
        chat_input = await self.aget_element_by_role_name(self.ROLE_CHAT_PLACEHOLDER, names=self.NAME_CHAT_PLACEHOLDER)
        await chat_input.fill(message)

    # ------
    # Chat
    # ------
    def chat(self, message: str, files: Optional[List[Union[str, Path]]] = None, *, create_new_session_if_full_context: bool = True):
        """Sync: Send a message and wait for response."""
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await copilot.achat(...)` instead of `chat(...)`.")

        self.__fill_chat_input(message)

        # Character limit
        exceeded_limit = False
        try:
            exceeded_limit = self.page.get_by_text("Character limit exceeded").is_visible(timeout=500)
        except Exception:
            exceeded_limit = False
        if exceeded_limit:
            try:
                limit = self.page.locator("span.fai-ChatInput__count").inner_text()
                current, max_length = map(int, re.findall(r"\d+", limit))
            except Exception:
                current = max_length = 0
            raise CopilotExceedsMaxLengthError(
                "Character limit exceeded. Please create a new chat session or reduce the message size.",
                current_length=current,
                max_length=max_length,
            )

        # Upload files if any
        for file in files or []:
            file_path = Path(file)
            self.page.get_by_test_id(self.TESTID_PLUS_BUTTON).click()
            select_file(self.page, self.page.get_by_text(self.TEXT_UPLOAD_FILE), file_path)
            time.sleep(2)

        # Send
        self.get_element_by_role_name("button", self.NAME_SEND_BUTTON).click()
        self.user_messages += 1

        # Wait for the response (copy button count == user messages)
        copy_buttons = self.page.locator("[data-testid='CopyButtonTestId']")
        sync_expect(copy_buttons).to_have_count(self.user_messages, timeout=self.ANSWER_TIMEOUT)

        self.response_locator = self.page.get_by_test_id("lastChatMessage")

        # Wait loading skeletons to disappear
        wait_divs = self.response_locator.get_by_test_id("loadingPlaceholderTestId")
        if wait_divs.count() > 0:
            for i in range(wait_divs.count()):
                try:
                    sync_expect(wait_divs.nth(i)).to_be_hidden(timeout=self.WAIT_DIVS_TIMEOUT)
                except Exception as e:
                    raise CopilotTimeoutError(
                        "Timeout waiting for the response to be ready. Please try again or create a new chat session."
                    ) from e

    async def achat(self, message: str, files: Optional[List[Union[str, Path]]] = None, *, create_new_session_if_full_context: bool = True):
        """Async: Send a message and wait for response."""
        if not self._async:
            # allow using achat in sync browsers if caller wants, but execute sync version
            self.chat(message, files=files, create_new_session_if_full_context=create_new_session_if_full_context)
            return

        await self.__afill_chat_input(message)

        exceeded_limit = False
        try:
            exceeded_limit = await self.page.get_by_text("Character limit exceeded").is_visible(timeout=500)
        except Exception:
            exceeded_limit = False
        if exceeded_limit:
            try:
                limit = await self.page.locator("span.fai-ChatInput__count").inner_text()
                current, max_length = map(int, re.findall(r"\d+", limit))
            except Exception:
                current = max_length = 0
            raise CopilotExceedsMaxLengthError(
                "Character limit exceeded. Please create a new chat session or reduce the message size.",
                current_length=current,
                max_length=max_length,
            )

        for file in files or []:
            file_path = Path(file)
            await self.page.get_by_test_id(self.TESTID_PLUS_BUTTON).click()
            await aselect_file(self.page, self.page.get_by_text(self.TEXT_UPLOAD_FILE), file_path)
            await asyncio.sleep(2)

        await (await self.aget_element_by_role_name("button", self.NAME_SEND_BUTTON)).click()
        self.user_messages += 1

        copy_buttons = self.page.locator("[data-testid='CopyButtonTestId']")
        await async_expect(copy_buttons).to_have_count(self.user_messages, timeout=self.ANSWER_TIMEOUT)

        self.response_locator = self.page.get_by_test_id("lastChatMessage")

        wait_divs = self.response_locator.get_by_test_id("loadingPlaceholderTestId")
        try:
            n = await wait_divs.count()
        except Exception:
            n = 0
        if n > 0:
            for i in range(n):
                try:
                    await async_expect(wait_divs.nth(i)).to_be_hidden(timeout=self.WAIT_DIVS_TIMEOUT)
                except Exception as e:
                    raise CopilotTimeoutError(
                        "Timeout waiting for the response to be ready. Please try again or create a new chat session."
                    ) from e

    # ----------------
    # Response getters
    # ----------------
    def get_html_response(self) -> str:
        """Sync: response HTML."""
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await aget_html_response()`")
        return self.response_locator.inner_html() if self.response_locator else ""

    async def aget_html_response(self) -> str:
        """Async: response HTML."""
        if not self.response_locator:
            return ""
        if not self._async:
            return self.get_html_response()
        return await self.response_locator.inner_html()

    def get_text_response(self) -> str:
        """Sync: response text."""
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await aget_text_response()`")
        return self.response_locator.inner_text() if self.response_locator else ""

    async def aget_text_response(self) -> str:
        """Async: response text."""
        if not self.response_locator:
            return ""
        if not self._async:
            return self.get_text_response()
        return await self.response_locator.inner_text()

    def get_response_tables(self) -> List[pd.DataFrame]:
        """Sync: tables from HTML response."""
        try:
            tables = pd.read_html(io.StringIO(self.get_html_response()))
        except ValueError as ve:
            if ve.args == ("No tables found",):
                warnings.warn("No tables found in the response.")
                return []
            raise
        return tables

    async def aget_response_tables(self) -> List[pd.DataFrame]:
        """Async: tables from HTML response."""
        html = await self.aget_html_response()
        try:
            tables = pd.read_html(io.StringIO(html))
        except ValueError as ve:
            if ve.args == ("No tables found",):
                warnings.warn("No tables found in the response.")
                return []
            raise
        return tables

    # -------------
    # Code blocks
    # -------------
    def get_response_code_blocks(self) -> List[str]:
        """Sync: extract code blocks from the response.

        This is a best-effort extraction that tries:
        - <pre> blocks
        - embedded iframes (if any)
        """
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await aget_response_code_blocks()`")
        if not self.response_locator:
            return []

        codes: List[str] = []

        # Direct <pre>
        pre = self.response_locator.locator("pre")
        for i in range(pre.count()):
            try:
                txt = pre.nth(i).inner_text().strip()
                if txt:
                    codes.append(txt)
            except Exception:
                pass

        # Iframes (rare)
        try:
            iframes = self.response_locator.locator("iframe").element_handles()
            for iframe_el in iframes:
                try:
                    frame = iframe_el.content_frame()
                    if not frame:
                        continue
                    fpre = frame.locator("pre")
                    for j in range(fpre.count()):
                        txt = fpre.nth(j).inner_text().strip()
                        if txt:
                            codes.append(txt)
                except Exception:
                    continue
        except Exception:
            pass

        return codes

    async def aget_response_code_blocks(self) -> List[str]:
        """Async: extract code blocks from the response."""
        if not self.response_locator:
            return []
        if not self._async:
            return self.get_response_code_blocks()

        codes: List[str] = []

        pre = self.response_locator.locator("pre")
        try:
            npre = await pre.count()
        except Exception:
            npre = 0
        for i in range(npre):
            try:
                txt = (await pre.nth(i).inner_text()).strip()
                if txt:
                    codes.append(txt)
            except Exception:
                pass

        try:
            iframe_loc = self.response_locator.locator("iframe")
            n_if = await iframe_loc.count()
            for i in range(n_if):
                try:
                    iframe_el = await iframe_loc.nth(i).element_handle()
                    if not iframe_el:
                        continue
                    frame = await iframe_el.content_frame()
                    if not frame:
                        continue
                    fpre = frame.locator("pre")
                    n_fpre = await fpre.count()
                    for j in range(n_fpre):
                        txt = (await fpre.nth(j).inner_text()).strip()
                        if txt:
                            codes.append(txt)
                except Exception:
                    continue
        except Exception:
            pass

        return codes

    # --------
    # Files
    # --------
    def get_response_files(self) -> List[ElementHandle]:
        """Sync: get downloadable file links from the response."""
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await aget_response_files()`")
        if not self.response_locator:
            return []

        retval: List[ElementHandle] = []
        response_element = self.response_locator.element_handle()

        hrefs = []
        for _ in range(2):
            try:
                hrefs = response_element.query_selector_all('a[href][download]')
            except Exception:
                hrefs = []
            if hrefs:
                break
            time.sleep(1)

        retval.extend(hrefs)
        return retval

    async def aget_response_files(self) -> List[ElementHandle]:
        """Async: get downloadable file links from the response."""
        if not self.response_locator:
            return []
        if not self._async:
            return self.get_response_files()

        retval: List[ElementHandle] = []
        response_element = await self.response_locator.element_handle()
        if not response_element:
            return []

        hrefs = []
        for _ in range(2):
            try:
                hrefs = await response_element.query_selector_all('a[href][download]')
            except Exception:
                hrefs = []
            if hrefs:
                break
            await asyncio.sleep(1)

        retval.extend(hrefs)
        return retval

    def download_file(self, element_handle: ElementHandle, download_path: Union[str, Path]):
        """Sync: click download link and save to folder."""
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await adownload_file()`")

        destination = Path(download_path).expanduser().resolve().absolute()
        destination.mkdir(parents=True, exist_ok=True)

        with self.page.expect_download() as download:
            element_handle.click()

        file_name = destination / download.value.suggested_filename
        download.value.save_as(file_name.as_posix())
        return file_name

    async def adownload_file(self, element_handle: ElementHandle, download_path: Union[str, Path]):
        """Async: click download link and save to folder."""
        destination = Path(download_path).expanduser().resolve().absolute()
        destination.mkdir(parents=True, exist_ok=True)

        if not self._async:
            return self.download_file(element_handle, destination)

        async with self.page.expect_download() as download:
            await element_handle.click()

        dl = await download.value
        file_name = destination / dl.suggested_filename
        await dl.save_as(file_name.as_posix())
        return file_name


class M365CopilotAutomation(CopilotChatAutomation):
    """Automation for M365 Copilot (work mode)."""

    NAME_CHAT_PLACEHOLDER = "Enviar un mensaje a Copilot"
    CHAR_LIMIT = 16000

    def get_response_code_blocks(self) -> List[str]:
        """Sync: Extract code blocks from M365 Copilot responses."""
        if self._async:
            raise RuntimeError("Async Playwright detected. Use `await aget_response_code_blocks()`")
        if not self.response_locator:
            return []

        response_codes = self.page.get_by_test_id("ComponentFluentProviderId")
        all_codes: List[str] = []

        for n_code in range(response_codes.count()):
            code_lines = response_codes.nth(n_code).locator(self.CODE_LOCATOR)
            try:
                txt = "\n".join(code_lines.nth(i).inner_text() for i in range(1, code_lines.count()))
            except Exception:
                txt = ""
            if txt.strip():
                all_codes.append(txt)

        # Fallback to base extraction
        if not all_codes:
            all_codes = super().get_response_code_blocks()

        return all_codes

    async def aget_response_code_blocks(self) -> List[str]:
        """Async: Extract code blocks from M365 Copilot responses."""
        if not self.response_locator:
            return []
        if not self._async:
            return self.get_response_code_blocks()

        response_codes = self.page.get_by_test_id("ComponentFluentProviderId")
        all_codes: List[str] = []

        try:
            n = await response_codes.count()
        except Exception:
            n = 0
        for n_code in range(n):
            code_lines = response_codes.nth(n_code).locator(self.CODE_LOCATOR)
            try:
                m = await code_lines.count()
            except Exception:
                m = 0
            lines = []
            for i in range(1, m):
                try:
                    lines.append(await code_lines.nth(i).inner_text())
                except Exception:
                    pass
            txt = "\n".join(lines)
            if txt.strip():
                all_codes.append(txt)

        if not all_codes:
            all_codes = await super().aget_response_code_blocks()

        return all_codes


# -----------------
# Manual test runner
# -----------------
if __name__ == "__main__":
    PDF_FILE = r"tests/sample_tables.pdf"

    def test_copilot_text(copilot: CopilotChatAutomation):
        copilot.chat("Write a 100-word poem about the importance of sustainability in urban development.")
        print(copilot.get_text_response())

    async def atest_copilot_text(copilot: CopilotChatAutomation):
        await copilot.achat("Write a 100-word poem about the importance of sustainability in urban development.")
        print(await copilot.aget_text_response())

    def test_copilot_code(copilot: CopilotChatAutomation):
        copilot.chat("Generate a Python code that calculates the factorial of a positive integer.")
        codes = copilot.get_response_code_blocks()
        for i_code, code in enumerate(codes):
            print("#" * 50)
            print(f"Generated code number {i_code + 1}:")
            print("#" * 50)
            print(code)

    async def atest_copilot_code(copilot: CopilotChatAutomation):
        await copilot.achat("Generate a Python code that calculates the factorial of a positive integer.")
        codes = await copilot.aget_response_code_blocks()
        for i_code, code in enumerate(codes):
            print("#" * 50)
            print(f"Generated code number {i_code + 1}:")
            print("#" * 50)
            print(code)


    def test_copilot_tables(copilot: CopilotChatAutomation, pdf_file: str|Path = None):
        pdf_file = pdf_file or PDF_FILE
        copilot.chat("Give me the tables you find in this PDF.", [pdf_file])
        tables = copilot.get_response_tables()
        for idx, table in enumerate(tables):
            print(f"Table {idx + 1}:\n{table}\n")

    async def atest_copilot_tables(copilot: CopilotChatAutomation, pdf_file: str|Path = None):
        pdf_file = pdf_file or PDF_FILE
        await copilot.achat("Give me the tables you find in this PDF.", [pdf_file])
        tables = await copilot.aget_response_tables()
        for idx, table in enumerate(tables):
            print(f"Table {idx + 1}:\n{table}\n")

    def test_copilot_files(copilot: CopilotChatAutomation, download_path: str | Path = "copilot_downloads"):
        copilot.chat("Generate an Excel file with the numbers from 1 to 10.")
        download_path = Path(download_path).expanduser().absolute()
        files = copilot.get_response_files()
        print(f"Found files: {files}")
        for file in files:
            download_path.mkdir(exist_ok=True, parents=True)
            name = file.get_attribute("download")
            print(f"Downloading file: {name}")
            copilot.download_file(file, download_path=download_path)
            print(f"File downloaded: {name} in copilot_downloads/{name}")


    async def atest_copilot_files(copilot: CopilotChatAutomation, download_path: str | Path = "copilot_downloads"):
        await copilot.achat("Generate an Excel file with the numbers from 1 to 10.")
        download_path = Path(download_path).expanduser().absolute()
        files = await copilot.aget_response_files()
        print(f"Found files: {files}")
        for file in files:
            download_path.mkdir(exist_ok=True, parents=True)
            name = await file.get_attribute("download")
            print(f"Downloading file: {name}")
            await copilot.adownload_file(file, download_path=download_path)
            print(f"File downloaded: {name} in copilot_downloads/{name}")

    def test_copilot_multiple_chats(copilot: CopilotChatAutomation):
        copilot.chat("What is the capital of France?")
        print(copilot.get_text_response())

        copilot.chat("What is the population of France?")
        print(copilot.get_text_response())

        copilot.chat("What is the currency of France?")
        print(copilot.get_text_response())

    async def atest_copilot_multiple_chats(copilot: CopilotChatAutomation):
        await copilot.achat("What is the capital of France?")
        print(await copilot.aget_text_response())

        await copilot.achat("What is the population of France?")
        print(await copilot.aget_text_response())

        await copilot.achat("What is the currency of France?")
        print(await copilot.aget_text_response())


    def test_copilot_long_chat(copilot: CopilotChatAutomation):
        try:
            copilot.chat("1" * (copilot.CHAR_LIMIT + 1))
        except CopilotExceedsMaxLengthError as e:
            print(e)
        else:
            raise ValueError("No exception raised!")
        pass

    async def atest_copilot_long_chat(copilot: CopilotChatAutomation):
        try:
            await copilot.achat("1" * (copilot.CHAR_LIMIT + 1))
        except CopilotExceedsMaxLengthError as e:
            print(e)
        else:
            raise ValueError("No exception raised!")
        pass


    def sync_main():
        with LocalChromeBrowser(capture_headers=True) as browser:
            # copilot = CopilotChatAutomation(browser)
            copilot = M365CopilotAutomation(browser)
            
            # test_copilot_long_chat(copilot)
            # test_copilot_text(copilot)
            test_copilot_code(copilot)
            # test_copilot_tables(copilot)
            # test_copilot_files(copilot)
            # test_copilot_multiple_chats(copilot)
            pass

    async def async_main():
        async with LocalChromeBrowser(capture_headers=True) as browser:
            copilot = await M365CopilotAutomation.acreate(browser)
            # await atest_copilot_text(co<<<<pilot)
            # await atest_copilot_long_chat(copilot)
            #await atest_copilot_code(copilot)
            #await atest_copilot_tables(copilot)
            await atest_copilot_files(copilot)
            await atest_copilot_multiple_chats(copilot)


    # Choose one:
    sync_main()
    # asyncio.run(async_main())
