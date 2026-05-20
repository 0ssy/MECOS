import asyncio
from collections import deque
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from loguru import logger
from memory_system import MemorySystem
from config import settings

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

        if self._is_blocked_url(url):
            logger.warning(f"Skipping blocked URL: {url}")
            return {
                "url": url,
                "text": "",
                "links": [],
                "ok": False,
                "error": "blocked_url",
            }

        page = await self.context.new_page()
        try:
            logger.info(f"Navigating to {url}...")
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(settings.WEB_NAVIGATION_TIMEOUT_MS),
            )
            
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
            
            links = [
                urljoin(url, anchor.get("href"))
                for anchor in soup.find_all("a", href=True)
            ]
            links = [link for link in links if self._is_allowed_link(link)]

            await self.memory.add_experience(
                content=f"WEB CONTENT ({url}):\n{clean_text[:5000]}",  # Limit size for now
                source="web_perception"
            )
            logger.success(f"Successfully ingested web content from {url}")
            return {
                "url": url,
                "text": clean_text,
                "links": list(dict.fromkeys(links)),
                "ok": True,
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest {url}: {e}")
            return {
                "url": url,
                "text": "",
                "links": [],
                "ok": False,
                "error": str(e),
            }
        finally:
            await page.close()

    async def crawl_web(self, seed_urls: list, max_pages: int = 10, max_depth: int = 1, same_domain_only: bool = True):
        """
        Crawl multiple webpages and ingest discovered content.
        Uses bounded BFS from the provided seed URLs.
        """
        if not seed_urls:
            return {"visited": [], "ingested": 0}

        max_pages = max(1, int(max_pages))
        max_depth = max(0, int(max_depth))

        queue = deque()
        visited = set()
        results = []

        seed_domains = {
            urlparse(url).netloc.lower()
            for url in seed_urls
            if isinstance(url, str)
        }

        for url in seed_urls:
            if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
                queue.append((url, 0))

        while queue and len(visited) < max_pages:
            current_url, depth = queue.popleft()
            if current_url in visited:
                continue
            visited.add(current_url)

            page_result = await self.ingest_url(current_url)
            results.append(page_result)

            if depth >= max_depth:
                continue

            for link in page_result.get("links", []):
                if link in visited:
                    continue
                if not self._is_allowed_link(link):
                    continue
                if same_domain_only:
                    link_domain = urlparse(link).netloc.lower()
                    if seed_domains and link_domain not in seed_domains:
                        continue
                else:
                    link_domain = urlparse(link).netloc.lower()
                    if self._is_search_domain(link_domain):
                        continue
                queue.append((link, depth + 1))

        successful_pages = sum(1 for result in results if result.get("ok"))
        crawl_summary = {
            "visited": [result.get("url") for result in results],
            "ingested": successful_pages,
            "failed": len(results) - successful_pages,
        }
        await self.memory.add_experience(
            content=f"WEB CRAWL SUMMARY: {crawl_summary}",
            source="web_perception_crawl",
        )
        logger.info(
            f"Web crawl complete: {successful_pages}/{len(results)} pages ingested."
        )
        return crawl_summary

    def _is_search_domain(self, domain: str) -> bool:
        domain = (domain or "").lower()
        return (
            "google." in domain
            or "duckduckgo." in domain
            or "search.brave.com" in domain
        )

    def _is_blocked_url(self, url: str) -> bool:
        url_l = (url or "").lower()
        return any(pattern.lower() in url_l for pattern in settings.WEB_BLOCKED_URL_PATTERNS)

    def _is_allowed_link(self, url: str) -> bool:
        if not (url.startswith("http://") or url.startswith("https://")):
            return False
        if self._is_blocked_url(url):
            return False
        parsed = urlparse(url)
        # Skip obvious binary/document links for crawler efficiency
        blocked_ext = (".pdf", ".zip", ".exe", ".dmg", ".tar", ".gz")
        if parsed.path.lower().endswith(blocked_ext):
            return False
        return True

    async def collect(self, urls: list):
        """Perform a collection cycle for a list of URLs."""
        await self.crawl_web(
            seed_urls=urls,
            max_pages=settings.WEB_CRAWL_MAX_PAGES,
            max_depth=settings.WEB_CRAWL_MAX_DEPTH,
            same_domain_only=settings.WEB_CRAWL_SAME_DOMAIN_ONLY,
        )
