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
    parser.add_argument("--save_storage_state", action='store_true', help='Save the storage state to data/auth_state_cua.json or data/auth_state_bu.json')
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
            input("Check if you are blocked by the 2-way auth.\nIf so, manually input the code and login.\nAfter you input the code, you will be logged in successfully.\nThen press Enter to continue, the script will save the auth state to data/auth_state_cua.json if --save_storage_state is set.")
            if args.save_storage_state:
                context.storage_state(path="data/auth_state_cua.json")
                print("Storage state saved to data/auth_state_cua.json")
    elif args.mode == 'bu':
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://login.salesforce.com/")
            page.get_by_label("Username").click()
            page.get_by_label("Username").fill(os.getenv("SALESFORCE_USERNAME"))
            page.get_by_label("Password").click()
            page.get_by_label("Password").fill(os.getenv("SALESFORCE_PASSWORD"))
            page.get_by_role("button", name="Log In").click()
            input("Check if you are blocked by the 2-way auth.\nIf so, manually input the code and login.\nAfter you input the code, you will be logged in successfully.\nThen press Enter to continue, the script will save the auth state to data/auth_state_bu.json if --save_storage_state is set.")  
            if args.save_storage_state:
                context.storage_state(path="data/auth_state_bu.json")
                print("Storage state saved to data/auth_state_bu.json")
            browser.close()