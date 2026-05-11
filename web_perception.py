import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from loguru import logger
from memory_system import MemorySystem

class WebPerception:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.browser = None
        self.context = None

    async def startup(self):
        """Initialize Playwright browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        logger.info("Web Perception Module Initialized.")

    async def shutdown(self):
        """Close browser resources."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Web Perception Module Shutdown.")

    async def ingest_url(self, url: str):
        """Navigate to a URL, extract content, and store in memory."""
        if not self.context:
            await self.startup()
            
        page = await self.context.new_page()
        try:
            logger.info(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Extract text content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text(separator='\n')
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            await self.memory.add_experience(
                content=f"WEB CONTENT ({url}):\n{clean_text[:5000]}", # Limit size for now
                source="web_perception"
            )
            logger.success(f"Successfully ingested web content from {url}")
            
        except Exception as e:
            logger.error(f"Failed to ingest {url}: {e}")
        finally:
            await page.close()

    async def collect(self, urls: list):
        """Perform a collection cycle for a list of URLs."""
        for url in urls:
            await self.ingest_url(url)
