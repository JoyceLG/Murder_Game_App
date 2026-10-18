"""Print the path of Playwright's Chromium (used as CHROME_BIN for Karma)."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    print(p.chromium.executable_path)
