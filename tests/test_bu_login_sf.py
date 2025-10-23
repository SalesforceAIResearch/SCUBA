from playwright.sync_api import sync_playwright
import os
import dotenv

dotenv.load_dotenv(override=True)

assert os.getenv("SALESFORCE_USERNAME"), "SALESFORCE_USERNAME is not set"
assert os.getenv("SALESFORCE_PASSWORD"), "SALESFORCE_PASSWORD is not set"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(storage_state="./data/auth_state_bu.json")
    page = context.new_page()
    page.goto("https://login.salesforce.com/")
    page.get_by_label("Username").click()
    page.get_by_label("Username").fill(os.getenv("SALESFORCE_USERNAME"))
    page.get_by_label("Password").click()
    page.get_by_label("Password").fill(os.getenv("SALESFORCE_PASSWORD"))
    page.get_by_role("button", name="Log In").click()
    input("Press Enter to continue...")
    browser.close()
