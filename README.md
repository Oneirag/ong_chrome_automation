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

#### Basic Chrome Automation

```python
from ong_chrome_automation.local_chrome_browser import LocalChromeBrowser

with LocalChromeBrowser() as browser:
    browser.goto("https://example.com")
```

### With Client Certificate

```python
with LocalChromeBrowser(
    origin="https://your-server.com",
    pfxPath="./path/to/cert.pfx",
    passphrase="your-password"
) as browser:
    browser.goto("https://your-server.com")
```

### Microsoft Copilot Automation

```python
from ong_chrome_automation.local_chrome_browser import LocalChromeBrowser
from ong_chrome_automation.playwright_copilot import CopilotAutomation

with LocalChromeBrowser() as browser:
    copilot = CopilotAutomation(browser)
    copilot.chat("What is the capital of France?")
    print(copilot.get_text_response())
```

## Project Structure
* src/ong_chrome_automation/local_chrome_browser.py: Chrome browser automation class.
* src/ong_chrome_automation/playwright_copilot.py: High-level Copilot automation.
* requirements.txt: Python dependencies.
