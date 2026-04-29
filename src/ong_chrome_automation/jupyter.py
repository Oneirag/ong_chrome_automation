"""Utils to run playwright async in a jupyter notebook (sync api won't work) in windows"""

import asyncio
import threading


def run_playwright_jupyter(coro):
    """Call this function in a jupyter notebook to be able to run playwright from it. Create an async funcition and call it from this function.
    e.g: 

    ```python
    async def main():
            print("hello")

    run_playwright_jupyter(main)
    ```
    """
    result, exception = None, None
    def _run():
        nonlocal result, exception
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
        except Exception as e:
            exception = e
        finally:
            loop.close()
    t = threading.Thread(target=_run)
    t.start()
    t.join()
    if exception:
        raise exception
    return result