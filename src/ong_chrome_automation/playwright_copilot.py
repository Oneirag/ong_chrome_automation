from ong_chrome_automation.local_chrome_browser import LocalChromeBrowser
from playwright.sync_api import ElementHandle, expect
import re
import time
from pathlib import Path
import pandas as pd
from typing import List

URL = "https://m365.cloud.microsoft/"
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

    def __init__(self, browser, url: str = URL):
        self.browser = browser
        browser.page.goto(url, wait_until="domcontentloaded")
        self.page = self.browser.page
        login_button = self.page.get_by_role("button", name=re.compile("^Iniciar sesión.*", re.IGNORECASE))
        login_link = self.page.get_by_role("link", name=re.compile("^Iniciar sesión como.*", re.IGNORECASE))
        if login_button.all() or login_link.all():
            if login_button.all():
                login_button.click()
            else:
                login_link.click()
            # Here you can add the code to complete the login if necessary
            time.sleep(5)  # Wait for the login to complete
        self.response_locator = None
        # Always start a new chat
        self.page.get_by_test_id("newChatButton").click()
        self.user_messages = 0
        self.assistant_messages = 0


    def chat(self, message, files: List[str] = None):
        """
        Sends a message to the Copilot chat and waits for the response.
        """
        chat_input = self.page.get_by_role("textbox", name="Entrada del chat")
        chat_input.fill(message)

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

        # Now get response locator. There might be many, so wait to get one answer for each user message and then
        # get the last one
        response_locator = self.page.get_by_test_id("markdown-reply")
        expect(response_locator).to_have_count(self.user_messages, timeout=self.ANSWER_TIMEOUT)
        self.response_locator = self.page.get_by_test_id("markdown-reply").nth(-1)

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
        tables = pd.read_html(self.get_html_response())
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

    with LocalChromeBrowser() as browser:

        copilot = CopilotAutomation(browser)
        # test_copilot_text(copilot)
        # test_copilot_code(copilot)
        # test_copilot_tables(copilot)
        # test_copilot_files(copilot)
        test_copilot_multiple_chats(copilot)
        pass