"""
Test script: launch multiple Chromium instances and log into Salesforce
via the Authorization Code + singleaccess frontdoor flow.

On first run (no saved refresh token), a browser opens for one-time
interactive login. After that, everything is automatic.

=== USAGE ===

  python scripts/test_frontdoor_login.py --org_alias Automation2
  python scripts/test_frontdoor_login.py --org_alias Automation2 --num_instances 3 --headless
"""

import argparse
import asyncio
import os
import sys
import traceback

import dotenv

dotenv.load_dotenv(override=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from browser_use.custom.browser_zoo import BrowserBugFix
from browser_use.custom.browser_context_zoo import BrowserContextBugFix
from scuba.helpers.sf_oauth import refresh_access_token, get_frontdoor_url

PAUSE_AFTER_LOGIN = 12


async def launch_and_login(
    instance_id: int,
    oauth: dict,
    headless: bool,
    viewport_width: int,
    viewport_height: int,
):
    instance_url = oauth["instance_url"].rstrip("/")

    print(f"[Instance {instance_id}] Launching Chromium (headless={headless})...")
    browser_config = BrowserConfig(headless=headless)
    browser = BrowserBugFix(browser_config)

    context_config = BrowserContextConfig(
        minimum_wait_page_load_time=0.5,
        browser_window_size={"width": viewport_width, "height": viewport_height},
    )
    context = BrowserContextBugFix(browser=browser, config=context_config)

    try:
        session = await context.get_session()
        page = session.current_page

        frontdoor_url = get_frontdoor_url(oauth["access_token"], oauth["instance_url"])
        print(f"[Instance {instance_id}] Got frontdoor URL ({len(frontdoor_url)} chars)")

        await page.goto(frontdoor_url, wait_until="domcontentloaded")
        await asyncio.sleep(PAUSE_AFTER_LOGIN)

        url = page.url
        title = await page.title()
        print(f"[Instance {instance_id}] Post-login — url: {url}")
        print(f"[Instance {instance_id}] Post-login — title: {title}")

        if "login.salesforce.com" in url or "Login" in title:
            print(f"[Instance {instance_id}] FAILED: still on login page after frontdoor")
            return False

        if "lightning" not in url:
            await page.goto(f"{instance_url}/lightning/page/home")
            await asyncio.sleep(PAUSE_AFTER_LOGIN)

        try:
            await page.get_by_role("button", name="App Launcher").click()
            await page.get_by_placeholder("Search apps and items...").fill("sales")
            await page.get_by_role("option", name="Sales", exact=True).click()
            print(f"[Instance {instance_id}] Navigated to Sales app")
        except Exception as e:
            print(f"[Instance {instance_id}] Could not open Sales app ({e}), trying Salesforce Chatter...")
            try:
                await page.get_by_placeholder("Search apps and items...").fill("Salesforce Chatter")
                await page.get_by_role("option", name="Salesforce Chatter", exact=True).click()
            except Exception:
                print(f"[Instance {instance_id}] Skipping app navigation")

        final_url = page.url
        final_title = await page.title()
        print(f"[Instance {instance_id}] SUCCESS — title: '{final_title}', url: {final_url}")
        return True

    except Exception as e:
        print(f"[Instance {instance_id}] FAILED: {e}")
        traceback.print_exc()
        return False
    finally:
        if headless:
            await context.close()
            await browser.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Test Salesforce frontdoor login across multiple Chromium instances",
    )
    parser.add_argument("--org_alias", type=str, required=True)
    parser.add_argument("--num_instances", type=int, default=1)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--viewport_width", type=int, default=1920)
    parser.add_argument("--viewport_height", type=int, default=1080)
    args = parser.parse_args()

    print(f"Org:       {args.org_alias}")
    print(f"Instances: {args.num_instances}\n")

    print("--- Pre-flight: OAuth access token + singleaccess ---")
    oauth = refresh_access_token(args.org_alias)
    print(f"  access_token: {oauth['access_token'][:20]}...({len(oauth['access_token'])} chars)")
    print(f"  instance_url: {oauth.get('instance_url')}")
    print(f"  scope:        {oauth.get('scope')}")

    test_url = get_frontdoor_url(oauth["access_token"], oauth["instance_url"])
    print(f"  singleaccess: OK ({len(test_url)} chars)")

    print(f"\n--- Launching {args.num_instances} browser(s) ---\n")

    tasks = [
        launch_and_login(i, oauth, args.headless, args.viewport_width, args.viewport_height)
        for i in range(args.num_instances)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    if not args.headless:
        input("\nAll browsers launched. Press Enter to close them all...")

    successes = sum(1 for r in results if r is True)
    failures = args.num_instances - successes
    print(f"\nResults: {successes}/{args.num_instances} succeeded, {failures} failed")


if __name__ == "__main__":
    asyncio.run(main())
