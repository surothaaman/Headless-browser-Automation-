
from playwright.sync_api import sync_playwright


class BrowserManager:
    """Manage a visible Chromium browser for local automation."""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=False,
            slow_mo=300,
            args=[
                "--start-maximized",
                "--force-device-scale-factor=1",
            ],
        )

        # Use the actual browser window dimensions instead
        # of Playwright's default fixed 1280x720 viewport.
        self.context = self.browser.new_context(
            viewport=None,
            no_viewport=True,
        )

        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)

        print("Chromium browser launched in maximized mode.")
        print("Browser viewport:", self.page.viewport_size)

        return self.page

    def open_page(self, url):
        self.page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        print("Simulator opened:", url)

    def close(self):
        if self.context:
            self.context.close()

        if self.browser:
            self.browser.close()

        if self.playwright:
            self.playwright.stop()

        print("Browser closed successfully.")
