import io
import re
import time
import warnings
from pathlib import Path
from typing import List

import pandas as pd
from playwright.sync_api import ElementHandle, expect

from ong_chrome_automation.local_chrome_browser import LocalChromeBrowser
from ong_chrome_automation.exceptions import CopilotExceedsMaxLengthError, CopilotTimeoutError

PNG_FILE = r"page_4.png"
TXT_FILE = r"page_4.txt"


def select_file(page, locator, file_path):
    """
    Selects a file using the system's native dialog.
    """
    try:
        # Set up the listener with timeout
        with page.expect_file_chooser(timeout=10000) as fc_info:
            locator.click()  # Click the button to open the file selection dialog

        # Handle the selection
        file_chooser = fc_info.value
        file_chooser.set_files(file_path)

    except Exception as e:
        print(f"Error selecting file: {e}")
        raise


class CopilotAutomation:
    ANSWER_TIMEOUT = 120e3  # 2 minutes in milliseconds. This is the maximum time to wait for a response from Copilot.
    WAIT_DIVS_TIMEOUT = 30e3  # 30 seconds in milliseconds. This is the maximum time to wait for the loading placeholders to be hidden.
    LOGIN_TIMEOUT = 10e3  # 10 seconds in milliseconds. This is the maximum time to wait for the login process.
    URL = "https://m365.cloud.microsoft/"

    def __init__(self, browser, url: str = None):
        url = url or self.URL
        self.browser = browser
        # Extend the browser's default timeout
        self.browser.context.set_default_timeout(30e3)  # 30 seconds in milliseconds
        browser.page.goto(url, wait_until="domcontentloaded")
        self.page = self.browser.page
        login_button = self.page.get_by_role("button", name=re.compile("^Iniciar sesión.*", re.IGNORECASE))
        login_link = self.page.get_by_role("link", name=re.compile("^Iniciar sesión como.*", re.IGNORECASE))
        # If user is already logged in, neither the login button nor link will be visible
        if ((visible_login_button := login_button.is_visible(timeout=self.LOGIN_TIMEOUT)) or
                (visible_login_link := login_link.is_visible(timeout=self.LOGIN_TIMEOUT))):
            if visible_login_button:
                login_button.click()
            else:
                login_link.click()
            # Here you can add the code to complete the login if necessary
            time.sleep(self.LOGIN_TIMEOUT)  # Wait for the login to complete
        self.response_locator = None
        self.user_messages = 0
        # Always start a new chat
        self.new_chat()

    def new_chat(self):
        """Creates a new chat session in copilot."""
        self.page.get_by_test_id("newChatButton").click()
        self.user_messages = 0

    def __fill_chat_input(self, message: str):
        """
        Fills the chat input with the given message.
        This method is used to avoid code duplication in the chat method.
        """
        chat_input = self.page.get_by_role("textbox", name="Entrada del chat")
        chat_input.fill(message)

    def chat(self, message, files: List[str] = None, create_new_session_if_full_context: bool = True):
        """
        Sends a message to the Copilot chat and waits for the response. If context is full, and we are in a
        long conversation, it creates a new chat session if specified.
        """
        self.__fill_chat_input(message)
        exceeded_limit = self.page.get_by_text("Character limit exceeded").is_visible(timeout=500)
        if exceeded_limit:
            # get the text of an element similar to
            # <span class="fai-ChatInput__count r1sdbc9y ___90ugon0 f1oi9n2k">15000 / 8000</span>
            try:
                limit = self.page.locator("span.fai-ChatInput__count").inner_text()
                current, max_length = map(int, re.findall(r"\d+", limit))
            except:
                current = max_length = 0
            raise CopilotExceedsMaxLengthError(
                "Character limit exceeded. Please create a new chat session or reduce the message size.",
                current_length=current, max_length=max_length
            )


        for idx, file in enumerate(files or []):
            # The upload menu button
            self.page.get_by_test_id("PlusMenuButtonUploadMenu").click()
            select_file(self.page, self.page.get_by_text("Cargar desde este dispositivo"), file)

        self.page.get_by_role("button", name="Send").click()
        self.user_messages += 1
        # Wait for the copy button to be visible (response ready).
        # There might be more than one answer, so we have to wait for the last one
        copy_buttons = self.page.locator("[data-testid='CopyButtonTestId']")
        # In a conversation, there must be at least one copy button for each user message, so wait for the number
        # of copy buttons to match the number of user messages
        expect(copy_buttons).to_have_count(self.user_messages, timeout=self.ANSWER_TIMEOUT)
        last_copy_button = copy_buttons.nth(-1)
        # To know if it has responded, wait for the stop button to disappear
        last_copy_button.wait_for(state="visible", timeout=self.ANSWER_TIMEOUT)

        # response_locator = self.page.get_by_test_id("markdown-reply")
        # It might happen that a response has more than one markdown-reply element and to_have_count looks for
        # the exact number of elements, so this is not a good way to wait for the response.
        # expect(response_locator).to_have_count(self.user_messages, timeout=self.ANSWER_TIMEOUT)

        # Now get response locator. There might be many, so wait to get one answer for each user message and then
        # get the last one
        self.response_locator = self.page.get_by_test_id("markdown-reply").nth(-1)
        # Wait for the response to be fully loaded
        """
        Find divs with the following structure:
        <div role="progressbar" aria-busy="true" class="fui-Skeleton ___7ulbs20 f1ggmyuv fq3vbzb f1isyly7
         ftciz5z" data-testid="loadingPlaceholderTestId">
        """
        # wait_divs = self.response_locator.locator("div[role='progressbar'][aria-busy='true']")
        wait_divs = self.response_locator.get_by_test_id("loadingPlaceholderTestId")
        # There might be multiple loading placeholders, so we wait for the last one
        if wait_divs.count() > 0:
            # Wait for all loading placeholder to be hidden
            for i in range(wait_divs.count()):
                try:
                    expect(wait_divs.nth(i)).to_be_hidden(timeout=self.WAIT_DIVS_TIMEOUT)
                except Exception as e:
                    print(f"Error waiting for loading placeholder to be hidden: {e}")
                    raise CopilotTimeoutError("Timeout waiting for the response to be ready. "
                                     "Please try again or create a new chat session.")

    def get_html_response(self) -> str:
        """ Gets the response in HTML format. """
        html_resp = self.response_locator.inner_html()
        return html_resp

    def get_text_response(self) -> str:
        """ Gets the response in plain text format. """
        txt_resp = self.response_locator.inner_text()
        return txt_resp

    def get_response_tables(self) -> List[pd.DataFrame]:
        """ Gets the tables (pandas DataFrames) from the response. """
        try:
            tables = pd.read_html(io.StringIO(self.get_html_response()))
        except ValueError as ve:
            if ve.args == ("No tables found", ):
                warnings.warn("No tables found in the response.")
                return []
            raise
        return tables

    def get_response_code_blocks(self) -> List[str]:
        """ Gets the code blocks from the response. """
        iframes = self.response_locator.locator("iframe").element_handles()
        all_codes = []
        for iframe in iframes:
            iframe_content = iframe.content_frame()
            all_code_lines = iframe_content.locator("#componentDiv").locator(".scriptor-paragraph")
            code = "\n".join([
                all_code_lines.nth(i).inner_text() for i in range(1, all_code_lines.count())
            ])
            all_codes.append(code)
        return all_codes

    def get_response_files(self) -> List[ElementHandle]:
        """ Gets the attached files from the response. """
        retval = list()
        for response_element in [self.response_locator.element_handles()[-1]]:
            # Wait for the response element to be visible
            hrefs = []
            for i in range(2):
                hrefs = response_element.query_selector_all('a[href][download]')
                if hrefs:
                    break
                time.sleep(1)  # Wait one second before trying again
            for href in hrefs:
                retval.append(href)
        return retval

    def download_file(self, element_handle: ElementHandle, download_path: str | Path):
        """ Downloads a file using the given download information and writes it to the specified path."""
        # Ensure the download directory exists     
        destination = Path(download_path).expanduser().resolve().absolute()
        destination.mkdir(parents=True, exist_ok=True)
        # Start the download
        with self.page.expect_download() as download:
            element_handle.click()
        # Wait for the download to complete
        file_name = destination / download.value.suggested_filename
        download.value.save_as(file_name.as_posix())


if __name__ == "__main__":

    PDF_FILE = r"report.pdf"


    def test_copilot_text(copilot: CopilotAutomation):
        copilot.chat("Write a 100-word poem about the importance of sustainability in urban development.")
        print(copilot.get_text_response())


    def test_copilot_code(copilot: CopilotAutomation):
        copilot.chat("Generate a Python code that calculates the factorial of a positive integer.")
        codes = copilot.get_response_code_blocks()
        print("Generated codes:"
              f"\n{codes}\n")


    def test_copilot_tables(copilot: CopilotAutomation):
        copilot.chat("Give me the tables you find in this PDF.", [PDF_FILE])
        tables = copilot.get_response_tables()
        for idx, table in enumerate(tables):
            print(f"Table {idx + 1}:\n{table}\n")

    def test_copilot_files(copilot: CopilotAutomation, download_path: str | Path = "../../copilot_downloads"):
        copilot.chat("Generate an Excel file with the numbers from 1 to 10.")
        files = copilot.get_response_files()
        print(f"Found files: {files}")
        for file in files:
            name = file.get_attribute("download")
            print(f"Downloading file: {name}")
            copilot.download_file(file, download_path=download_path)
            print(f"File downloaded: {name} in copilot_downloads/{name}")


    def test_copilot_multiple_chats(copilot: CopilotAutomation):
        copilot.chat("What is the capital of France?")
        print(copilot.get_text_response())

        copilot.chat("What is the population of France?")
        print(copilot.get_text_response())

        copilot.chat("What is the currency of France?")
        print(copilot.get_text_response())

    def test_copilot_long_chat(copilot: CopilotAutomation):
        copilot.chat("1" * 10000)
        pass


    with LocalChromeBrowser() as browser:

        copilot = CopilotAutomation(browser)
        try:
            test_copilot_long_chat(copilot)
        except ValueError as e:
            print("Raised exception for long chat:", e)
            pass
        # test_copilot_text(copilot)
        # test_copilot_code(copilot)
        # test_copilot_tables(copilot)
        # test_copilot_files(copilot)
        # test_copilot_multiple_chats(copilot)
        pass
