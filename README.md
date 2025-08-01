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

## Microsoft Copilot Automation

The `CopilotAutomation` class allows you to automate interactions with Microsoft Copilot web chat using Playwright. Below are some usage examples:

It is designed to work with the **work** version of Copilot (https://m365.cloud.microsoft/), not the personal version. To avoid MFA, you should have logged in in your Chrome session before using this class.

You can use it to send messages, upload files, and retrieve responses in various formats.

### Example 1: Send a Message and Get Response
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation

with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    copilot.chat("What is the capital of France?")
    print(copilot.get_text_response())
```
#### Example 2: Ask for code generation and read code blocks in response
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation
with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    copilot.chat("Generate a Python code with a function named factorial that calculates the factorial of a positive integer.")
    codes = copilot.get_response_code_blocks()
    print(codes[0])  # Print the first code block```
```

#### Example 3: Upload a file and get response
Files can be uploaded to Copilot, and the response can be retrieved as text or HTML.

The limits of copilot apply to this case, e.g. just a single image file can be uploaded per message.
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation
with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    copilot.chat("Analyze this file:", ["./path/to/your/file.txt"])
    print(copilot.get_text_response())
```

### Example 4: Get response as a pandas DataFrame
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation
import pandas as pd
with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    copilot.chat("Create a table for the squares of the first 10 numbers.")
    df = copilot.get_response_tables()[0]
    print(df.head())  # Display the first few rows of the DataFrame
```
### Example 5: Download a file from Copilot response
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation
with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    copilot.chat("Create an excel sheet with the numbers from 1 to 10.")
    files = copilot.get_response_files()
    for file in files:
        copilot.download_file(file, "download_folder")
        print("File downloaded successfully.")
```

### Example 6: Handling long messages
If you send a message that exceeds the character limit of copilot, a `ValueError` will be raised. 

If the message is part of a long conversation, it tries to create a new conversation first before raising the exception.
```python
from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation
with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    try:
        copilot.chat("1" * 10000)
    except ValueError as e:
        print("Error:", e)
```    

## Project Structure
* src/ong_chrome_automation/local_chrome_browser.py: Chrome browser automation class.
* src/ong_chrome_automation/playwright_copilot.py: High-level Copilot automation.
* requirements.txt: Python dependencies.
