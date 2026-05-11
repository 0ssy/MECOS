"""
MECOS Phase 4 - Browser Automation
Full Playwright-based browser automation with session management,
screenshot capture, DOM extraction, and form interaction.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from loguru import logger

from config import settings


class BrowserAutomation:
    """
    Playwright-based browser automation for MECOS.
    Supports navigation, DOM extraction, screenshots, form filling, and JS execution.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self.screenshot_dir = settings.DATA_DIR / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info("BrowserAutomation initialized.")

    async def startup(self):
        """Launch the browser and create a persistent context."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (compatible; MECOS/1.0; +https://github.com/0ssy/MECOS)"
            )
            self._page = await self._context.new_page()
            logger.info("Browser started (headless Chromium).")
        except Exception as e:
            logger.error(f"Browser startup failed: {e}")

    async def shutdown(self):
        """Close the browser and playwright instance."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser shut down.")
        except Exception as e:
            logger.warning(f"Browser shutdown error: {e}")

    async def navigate(self, url: str, wait_until: str = "networkidle", timeout: int = 30000) -> bool:
        """Navigate to a URL and wait for the page to load."""
        if not self._page:
            await self.startup()
        try:
            await self._page.goto(url, wait_until=wait_until, timeout=timeout)
            logger.info(f"Navigated to: {url}")
            return True
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            return False

    async def get_text(self) -> str:
        """Extract all visible text from the current page."""
        if not self._page:
            return ""
        try:
            text = await self._page.evaluate("""() => {
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(el => el.remove());
                return document.body ? document.body.innerText : '';
            }""")
            return text[:10000]  # Limit to 10k chars
        except Exception as e:
            logger.error(f"get_text failed: {e}")
            return ""

    async def get_html(self) -> str:
        """Get the full page HTML."""
        if not self._page:
            return ""
        try:
            return await self._page.content()
        except Exception as e:
            logger.error(f"get_html failed: {e}")
            return ""

    async def screenshot(self, filename: Optional[str] = None) -> str:
        """Take a screenshot and save it. Returns the file path."""
        if not self._page:
            return ""
        from datetime import datetime
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{ts}.png"
        path = self.screenshot_dir / filename
        try:
            await self._page.screenshot(path=str(path), full_page=True)
            logger.info(f"Screenshot saved: {path}")
            return str(path)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""

    async def click(self, selector: str) -> bool:
        """Click an element by CSS selector."""
        if not self._page:
            return False
        try:
            await self._page.click(selector)
            logger.debug(f"Clicked: {selector}")
            return True
        except Exception as e:
            logger.error(f"Click failed ({selector}): {e}")
            return False

    async def fill_form(self, selector: str, value: str) -> bool:
        """Fill a form field."""
        if not self._page:
            return False
        try:
            await self._page.fill(selector, value)
            logger.debug(f"Filled {selector} with value")
            return True
        except Exception as e:
            logger.error(f"Fill failed ({selector}): {e}")
            return False

    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript on the current page."""
        if not self._page:
            return None
        try:
            result = await self._page.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"JS execution failed: {e}")
            return None

    async def extract_links(self) -> List[str]:
        """Extract all hyperlinks from the current page."""
        if not self._page:
            return []
        try:
            links = await self._page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h.startsWith('http'));
            }""")
            return list(set(links))
        except Exception as e:
            logger.error(f"extract_links failed: {e}")
            return []

    async def fetch_page_content(self, url: str) -> Dict[str, str]:
        """Navigate to a URL and return text, title, and links."""
        await self.navigate(url)
        title = ""
        try:
            title = await self._page.title()
        except Exception:
            pass
        text = await self.get_text()
        links = await self.extract_links()
        return {"url": url, "title": title, "text": text, "links": links}

    @property
    def current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""
