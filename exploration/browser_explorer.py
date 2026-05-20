import asyncio
import io
from PIL import Image
from playwright.async_api import async_playwright
from loguru import logger
from exploration.config import config

class BrowserExplorer:
    def __init__(self, knowledge_base, vision_analyzer):
        self.kb = knowledge_base
        self.vision = vision_analyzer
        self.playwright = None
        self.context = None

    async def startup(self):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(config.BROWSER_SESSION_DIR / "session"),
            headless=config.BROWSER_HEADLESS,
            viewport={'width': config.BROWSER_WINDOW_WIDTH, 'height': config.BROWSER_WINDOW_HEIGHT}
        )
        self.page = await self.context.new_page()

    async def explore(self, url, name):
        if not self.page or self.page.is_closed():
            return
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            screenshot_bytes = await self.page.screenshot()
            image = Image.open(io.BytesIO(screenshot_bytes))
            analysis = await self.vision.analyze_screenshot(image)
            self.kb.add_log(name, {"url": url, "analysis": analysis})
        except Exception as e:
            logger.debug(f"Browser explore skipped for {url}: {e}")

    async def shutdown(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.page = None
