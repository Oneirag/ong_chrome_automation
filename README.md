# ong_chrome_automation

Automate Chrome browser tasks using Playwright, with special support for Microsoft Copilot interactions (**work** copilot, not personal copilot).

## Features

- Launch and control a local Chrome browser using Playwright.
- Support for client certificates (PFX/PKCS12) for secure sites.
- Optional anti-detection (stealth) scripts.
- High-level automation for Microsoft Copilot web chat:
  - Send messages and files.
  - Retrieve responses as text, HTML, tables (pandas DataFrames), code blocks, and downloadable files.
- Example scripts for common Copilot automation tasks.

## Requirements

- Python >= 3.11
- Google Chrome installed (default path: `C:/Program Files/Google/Chrome/Application/chrome.exe`)
- See `requirements.txt` for Python dependencies.

## Installation

```bash
pip install -r requirements.txt
playwright install
```

## Usage

### Basic Chrome Automation

```python
from ong_chrome_automation import LocalChromeBrowser

with LocalChromeBrowser() as browser:
    browser.goto("https://example.com")
```

### With Client Certificate

```python
from ong_chrome_automation import LocalChromeBrowser
with LocalChromeBrowser(
    origin="https://your-server.com",
    pfxPath="./path/to/cert.pfx",
    passphrase="your-password"
) as browser:
    browser.goto("https://your-server.com")
```

### Hide Browser Window
To run the browser in headless mode (without a visible window), set `visible=False`:
```python
from ong_chrome_automation import LocalChromeBrowser
with LocalChromeBrowser(visible=False) as browser:
    browser.goto("https://example.com")
```

### Run in Jupyter Notebook (windows)
In windows, playwright sync api does not work, and you should use async api within a thread. Function `ong_chrome_automation.jupyter import run_playwright_jupyter` is provided for convenience.

Here is sample code:

```python
from ong_chrome_automation.jupyter import run_playwright_jupyter
from ong_chrome_automation import LocalChromeBrowser


async def main():
    async with LocalChromeBrowser() as browser:
        await browser.a_goto("https://example.com")
        await browser.a_random_delay()

run_playwright_jupyter(main)
```

## Microsoft Copilot Automation

The `CopilotChatAutomation` class allows you to automate interactions with Microsoft Copilot web chat using Playwright. Use `M365CopilotAutomation` for M365 Copilot interaction (work mode by default). Below are some usage examples:

It is designed to work with the **work** version of Copilot (https://m365.cloud.microsoft/), not the personal version. To avoid MFA, you should have logged in in your Chrome session before using this class.

You can use it to send messages, upload files, and retrieve responses in various formats.

### Example 1: Send a Message and Get Response
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation     # Use M365CopilotAutomation for M365 version

with LocalChromeBrowser() as browser:
    copilot = CopilotChatAutomation(browser)    # Use M365CopilotAutomation for M365 version
    copilot.chat("What is the capital of France?")
    print(copilot.get_text_response())
```
#### Example 2: Ask for code generation and read code blocks in response
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation # Use M365CopilotAutomation for M365 version
with LocalChromeBrowser() as browser:
    copilot = CopilotChatAutomation(browser)        # Use M365CopilotAutomation for M365 version
    copilot.chat("Generate a Python code with a function named factorial that calculates the factorial of a positive integer.")
    codes = copilot.get_response_code_blocks()
    print(codes[0])  # Print the first code block```
```

#### Example 3: Upload a file and get response
Files can be uploaded to Copilot, and the response can be retrieved as text or HTML.

The limits of copilot apply to this case, e.g. just a single image file can be uploaded per message.
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation # Use M365CopilotAutomation for M365 version
with LocalChromeBrowser() as browser:
    copilot = CopilotChatAutomation(browser)    # Use M365CopilotAutomation for M365 version
    copilot.chat("Analyze this file:", ["./path/to/your/file.txt"])
    print(copilot.get_text_response())
```

### Example 4: Get response as a pandas DataFrame
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation # Use M365CopilotAutomation for M365 version
import pandas as pd
with LocalChromeBrowser() as browser:
    copilot = CopilotChatAutomation(browser)        # Use M365CopilotAutomation for M365 version
    copilot.chat("Create a table for the squares of the first 10 numbers.")
    df = copilot.get_response_tables()[0]
    print(df.head())  # Display the first few rows of the DataFrame
```
### Example 5: Download a file from Copilot response
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation     # Use M365CopilotAutomation for M365 version
with LocalChromeBrowser() as browser:
    copilot = CopilotChatAutomation(browser)        # Use M365CopilotAutomation for M365 version
    copilot.chat("Create an excel sheet with the numbers from 1 to 10.")
    files = copilot.get_response_files()
    for file in files:
        copilot.download_file(file, "download_folder")
        print("File downloaded successfully.")
```

### Example 6: Handling long messages
If you send a message that exceeds the character limit of copilot, a `ong_chrome_automation.exceptions.CopilotExceedsMaxLengthError` will be raised.

If you want to handle this case, you can catch the exception and take appropriate action, such as splitting the message or notifying the user.

```python
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation  # Use M365CopilotAutomation for M365 version
from ong_chrome_automation.exceptions import CopilotExceedsMaxLengthError

with LocalChromeBrowser() as browser:
  copilot = CopilotChatAutomation(browser) # Use M365CopilotAutomation for M365 version
  try:
    copilot.chat("1" * 10000)
  except CopilotExceedsMaxLengthError as e:
    print("Error:", e)
```    

### Async versions
Class `CopilotChatAutomation` works also in async mode. Just use methods starting with `a`.

```python
import asyncio
from ong_chrome_automation import LocalChromeBrowser, CopilotChatAutomation

async def async_main():
        async with LocalChromeBrowser(capture_headers=True) as browser:
            copilot = await M365CopilotAutomation.acreate(browser)
            await copilot.achat("Hello")
            text = await copilot.aget_text_response()

asyncio.run(async_main())
``` 

## Project Structure
* src/ong_chrome_automation/local_chrome_browser.py: Chrome browser automation class.
* src/ong_chrome_automation/playwright_copilot.py: High-level Copilot automation.
* requirements.txt: Python dependencies.
