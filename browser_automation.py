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
        self._started = False
        self._start_error = ""
        self.screenshot_dir = settings.DATA_DIR / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info("BrowserAutomation initialized (lazy startup).")

    @property
    def is_running(self) -> bool:
        return self._started and self._page is not None

    @property
    def start_error(self) -> str:
        return self._start_error

    async def startup(self):
        """Launch the browser and create a persistent context. Idempotent."""
        if self._started:
            return self.is_running
        self._start_error = ""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (compatible; MECOS/1.0; +https://github.com/0ssy/MECOS)",
                viewport={"width": 1280, "height": 900},
            )
            self._page = await self._context.new_page()
            self._started = True
            logger.info("Browser started (headless Chromium).")
            return True
        except Exception as e:
            self._start_error = str(e)
            self._started = False
            logger.error(f"Browser startup failed: {e}")
            return False

    async def shutdown(self):
        """Close the browser and playwright instance."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Browser shutdown error: {e}")
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None
            self._started = False
        logger.info("Browser shut down.")

    async def _ensure_page(self):
        if not self._started or not self._page:
            await self.startup()
        if not self._page:
            raise RuntimeError(f"Browser unavailable: {self._start_error or 'not started'}")

    async def navigate(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000) -> bool:
        """Navigate to a URL and wait for the page to load."""
        try:
            await self._ensure_page()
            await self._page.goto(url, wait_until=wait_until, timeout=timeout)
            logger.info(f"Navigated to: {url}")
            return True
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            return False

    async def get_text(self) -> str:
        """Extract all visible text from the current page."""
        try:
            await self._ensure_page()
            text = await self._page.evaluate("""() => {
                const scripts = document.querySelectorAll('script, style, noscript');
                scripts.forEach(el => el.remove());
                return document.body ? document.body.innerText : '';
            }""")
            return text[:10000]
        except Exception as e:
            logger.error(f"get_text failed: {e}")
            return ""

    async def get_html(self) -> str:
        """Get the full page HTML."""
        try:
            await self._ensure_page()
            return await self._page.content()
        except Exception as e:
            logger.error(f"get_html failed: {e}")
            return ""

    async def screenshot(self, filename: Optional[str] = None) -> str:
        """Take a screenshot and save it. Returns the file path."""
        try:
            await self._ensure_page()
            from datetime import datetime
            if not filename:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{ts}.png"
            path = self.screenshot_dir / filename
            await self._page.screenshot(path=str(path), full_page=True)
            logger.info(f"Screenshot saved: {path}")
            return str(path)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""

    async def click(self, selector: str) -> bool:
        """Click an element by CSS selector."""
        try:
            await self._ensure_page()
            await self._page.click(selector)
            logger.debug(f"Clicked: {selector}")
            return True
        except Exception as e:
            logger.error(f"Click failed ({selector}): {e}")
            return False

    async def fill_form(self, selector: str, value: str) -> bool:
        """Fill a form field."""
        try:
            await self._ensure_page()
            await self._page.fill(selector, value)
            logger.debug(f"Filled {selector} with value")
            return True
        except Exception as e:
            logger.error(f"Fill failed ({selector}): {e}")
            return False

    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript on the current page."""
        try:
            await self._ensure_page()
            result = await self._page.evaluate(script)
            return result
        except Exception as e:
            logger.error(f"JS execution failed: {e}")
            return None

    async def extract_links(self) -> List[str]:
        """Extract all hyperlinks from the current page."""
        try:
            await self._ensure_page()
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
        await self._ensure_page()
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
