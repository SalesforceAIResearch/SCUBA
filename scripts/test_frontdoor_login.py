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
LOGIN_STAGGER_DELAY = 1


async def prepare_browser(
    instance_id: int,
    headless: bool,
    viewport_width: int,
    viewport_height: int,
):
    """Phase 1: launch browser and get a ready page. Safe to run in parallel."""
    print(f"[Instance {instance_id}] Launching Chromium (headless={headless})...")
    browser_config = BrowserConfig(headless=headless)
    browser = BrowserBugFix(browser_config)

    context_config = BrowserContextConfig(
        minimum_wait_page_load_time=0.5,
        browser_window_size={"width": viewport_width, "height": viewport_height},
    )
    context = BrowserContextBugFix(browser=browser, config=context_config)

    session = await context.get_session()
    page = session.current_page
    print(f"[Instance {instance_id}] Browser ready")
    return browser, context, page


async def login_and_navigate(
    instance_id: int,
    oauth: dict,
    page,
    browser,
    context,
    headless: bool,
):
    """Phase 2: frontdoor login + post-login navigation. Run with stagger."""
    instance_url = oauth["instance_url"].rstrip("/")
    success = False
    try:
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
            return success, browser, context

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
        success = True

    except Exception as e:
        print(f"[Instance {instance_id}] FAILED: {e}")
        traceback.print_exc()

    if headless:
        await _close_quietly(context, browser, instance_id)
        return success, None, None

    return success, browser, context


async def _close_quietly(context, browser, instance_id: int):
    try:
        if context is not None:
            await context.close()
    except Exception as e:
        print(f"[Instance {instance_id}] Error closing context: {e}")
    try:
        if browser is not None:
            await browser.close()
    except Exception as e:
        print(f"[Instance {instance_id}] Error closing browser: {e}")


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

    # Phase 1: launch all browsers in parallel
    print(f"\n--- Phase 1: Launching {args.num_instances} browser(s) in parallel ---\n")
    prepare_tasks = [
        prepare_browser(i, args.headless, args.viewport_width, args.viewport_height)
        for i in range(args.num_instances)
    ]
    prepared = await asyncio.gather(*prepare_tasks, return_exceptions=True)

    ready = {}
    for i, result in enumerate(prepared):
        if isinstance(result, BaseException):
            print(f"[Instance {i}] FAILED to launch browser: {result}")
        else:
            ready[i] = result

    # Phase 2: staggered frontdoor login (~1s apart)
    print(f"\n--- Phase 2: Logging in {len(ready)} browser(s) (stagger={LOGIN_STAGGER_DELAY}s) ---\n")
    raw_results: dict[int, tuple | BaseException] = {}
    for idx, i in enumerate(sorted(ready)):
        if idx > 0:
            await asyncio.sleep(LOGIN_STAGGER_DELAY)
        browser, context, page = ready[i]
        try:
            raw_results[i] = await login_and_navigate(
                i, oauth, page, browser, context, args.headless
            )
        except BaseException as e:
            raw_results[i] = e

    successes = 0
    open_browsers: list[tuple[int, object, object]] = []
    for i in range(args.num_instances):
        if i not in raw_results:
            continue
        r = raw_results[i]
        if isinstance(r, BaseException):
            print(f"[Instance {i}] FAILED with exception: {r}")
            continue
        success, browser, context = r
        if success:
            successes += 1
        if browser is not None or context is not None:
            open_browsers.append((i, browser, context))

    if not args.headless and open_browsers:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, input, "\nAll browsers launched. Press Enter to close them all..."
        )
        print("Closing browsers...")
        await asyncio.gather(
            *(_close_quietly(ctx, br, i) for (i, br, ctx) in open_browsers),
            return_exceptions=True,
        )

    failures = args.num_instances - successes
    print(f"\nResults: {successes}/{args.num_instances} succeeded, {failures} failed")


if __name__ == "__main__":
    asyncio.run(main())
