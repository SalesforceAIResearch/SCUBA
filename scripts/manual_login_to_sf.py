import os
import sys
from playwright.sync_api import sync_playwright
import dotenv
import time
import argparse



dotenv.load_dotenv(override=True)

assert os.getenv("SALESFORCE_USERNAME"), "SALESFORCE_USERNAME is not set"
assert os.getenv("SALESFORCE_PASSWORD"), "SALESFORCE_PASSWORD is not set"


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default='bu', choices=['bu', 'cua'])
    args = parser.parse_args()


    if args.mode == 'cua':
        host = os.getenv("DOCKER_PROVIDER_HOST")
        port = 9222
        remote_debugging_url = f"http://{host}:{port}"
        with sync_playwright() as p:
            browser = None
            for attempt in range(15):
                try:
                    browser = p.chromium.connect_over_cdp(remote_debugging_url)
                    break
                except Exception as e:
                    if attempt < 14:
                        print(f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}")
                        time.sleep(5)
                    else:
                        print(f"Failed to connect after multiple attempts: {e}")
                        raise e
            if not browser:
                raise Exception("Failed to connect to browser")

            context = browser.contexts[0]
            page = context.new_page()
            page.goto("https://login.salesforce.com/")
            page.get_by_label("Username").click()
            page.get_by_label("Username").fill(os.getenv("SALESFORCE_USERNAME"))
            page.get_by_label("Password").click()
            page.get_by_label("Password").fill(os.getenv("SALESFORCE_PASSWORD"))
            page.get_by_role("button", name="Log In").click()
    elif args.mode == 'bu':
        # Add the project root to Python path so we can import browser_use
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, project_root)

        from browser_use.browser.browser import BrowserConfig
        from browser_use.browser.context import BrowserContextConfig
        from browser_use.custom.browser_zoo import BrowserBugFix
        from browser_use.custom.browser_context_zoo import BrowserContextBugFix
        import asyncio
        browser_config = BrowserConfig(headless=False)
        browser = BrowserBugFix(browser_config)

        context_config = BrowserContextConfig(
            minimum_wait_page_load_time=0.5,
            browser_window_size={'width': 1920, 'height': 1080}
        )
        context = BrowserContextBugFix(browser=browser, config=context_config)
        
        async def login_salesforce():
            page = await context.get_current_page()
            await page.goto("https://login.salesforce.com")
            await page.get_by_label("Username").click()
            await page.get_by_label("Username").fill(os.getenv("SALESFORCE_USERNAME"))
            await page.get_by_label("Password").click()
            await page.get_by_label("Password").fill(os.getenv("SALESFORCE_PASSWORD"))
            await page.get_by_role("button", name="Log In").click()
        
        async def main():
            await login_salesforce()
            input("Press Enter to close the browser...")
            # Properly close the context and browser
            await context.close()
            await browser.close()
        
        asyncio.run(main())