import asyncio
import os
from collections import deque
from contextlib import suppress
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from loguru import logger
from memory_system import MemorySystem
from config import settings

class WebPerception:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.playwright = None
        self.browser = None
        self.context = None
        self._playwright_lock = asyncio.Lock()
        self._navigation_timeout_ms = max(
            5000,
            min(int(settings.WEB_NAVIGATION_TIMEOUT_MS), 30000),
        )
        http_only_env = os.getenv("MECOS_WEB_HTTP_ONLY")
        if http_only_env is not None:
            self._http_only = http_only_env.strip() == "1"
        else:
            self._http_only = False
        self._playwright_failed = False
        self.agent_reach_bridge = None

    async def startup(self):
        """Initialize Playwright browser."""
        async with self._playwright_lock:
            await self._startup_playwright_unlocked()

    async def set_agent_reach_bridge(self, bridge):
        self.agent_reach_bridge = bridge

    async def _startup_playwright_unlocked(self):
        if self._http_only or self._playwright_failed:
            logger.info("Web Perception running in HTTP mode (Playwright disabled).")
            return
        if self.context:
            return
        await self._teardown_playwright()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        logger.info("Web Perception Module Initialized.")

    async def shutdown(self):
        """Close browser resources."""
        async with self._playwright_lock:
            await self._teardown_playwright()
        logger.info("Web Perception Module Shutdown.")

    async def ingest_url(self, url: str):
        """Navigate to a URL, extract content, and store in memory.

        Preference order:
        1. Agent-Reach bridge (platform-specific channels when available)
        2. Playwright browser
        3. HTTP fallback
        """
        if self._is_blocked_url(url):
            logger.warning(f"Skipping blocked URL: {url}")
            return {
                "url": url,
                "text": "",
                "links": [],
                "ok": False,
                "error": "blocked_url",
            }

        if self.agent_reach_bridge is not None:
            try:
                bridge_result = await self.agent_reach_bridge.read_url(url)
                if bridge_result.get("ok"):
                    return bridge_result
            except Exception as e:
                logger.debug(f"Agent-Reach bridge ingest failed for {url}: {e}")

        if not self._http_only and not self._playwright_failed:
            try:
                return await self._ingest_url_playwright(url)
            except Exception as e:
                logger.error(f"Playwright ingest failed for {url}: {e}")
                return await self._ingest_url_http(url, transport_error=str(e))

        return await self._ingest_url_http(url)

    async def _ingest_url_playwright(self, url: str):
        content = await self._fetch_content_playwright(url)
        return await self._build_ingest_result(url, content)

    async def _fetch_content_playwright(self, url: str) -> str:
        async with self._playwright_lock:
            if self._http_only or self._playwright_failed:
                logger.info("Web Perception running in HTTP mode (Playwright disabled).")
                raise RuntimeError("playwright_disabled")
            if not self.context:
                await self._startup_playwright_unlocked()
            page = await self.context.new_page()
            try:
                logger.info(f"Navigating to {url}...")
                await asyncio.wait_for(
                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self._navigation_timeout_ms,
                    ),
                    timeout=(self._navigation_timeout_ms / 1000) + 5,
                )
                return await page.content()
            except Exception as exc:
                if self._is_transport_error(exc):
                    logger.warning("Playwright transport dropped; restarting browser driver.")
                    await self._teardown_playwright()
                    self._playwright_failed = False
                    await self._startup_playwright_unlocked()
                    with suppress(Exception):
                        await page.close()
                    retry_page = await self.context.new_page()
                    try:
                        await asyncio.wait_for(
                            retry_page.goto(
                                url,
                                wait_until="domcontentloaded",
                                timeout=self._navigation_timeout_ms,
                            ),
                            timeout=(self._navigation_timeout_ms / 1000) + 5,
                        )
                        return await retry_page.content()
                    finally:
                        with suppress(Exception):
                            await retry_page.close()
                raise
            finally:
                with suppress(Exception):
                    await page.close()

    async def _build_ingest_result(self, url: str, content: str):
        soup = BeautifulSoup(content, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = "\n".join(chunk for chunk in chunks if chunk)
        links = [
            urljoin(url, anchor.get("href"))
            for anchor in soup.find_all("a", href=True)
        ]
        links = [link for link in links if self._is_allowed_link(link)]
        try:
            await asyncio.wait_for(
                self.memory.add_experience(
                    content=f"WEB CONTENT ({url}):\n{clean_text[:5000]}",
                    source="web_perception",
                ),
                timeout=5,
            )
        except Exception:
            pass
        logger.success(f"Successfully ingested web content from {url}")
        return {
            "url": url,
            "text": clean_text,
            "links": list(dict.fromkeys(links)),
            "ok": True,
        }

    async def _ingest_url_http(self, url: str, transport_error: str | None = None):
        try:
            logger.info(f"HTTP ingest fallback for {url}")
            timeout_seconds = max(5, int(settings.WEB_NAVIGATION_TIMEOUT_MS) // 1000)
            content = await asyncio.to_thread(self._fetch_html, url, timeout_seconds)
            return await self._build_ingest_result(url, content)
        except Exception as e:
            logger.error(f"Failed to ingest {url}: {e}")
            error_message = str(e)
            if transport_error:
                error_message = f"{transport_error}; fallback_error={error_message}"
            return {
                "url": url,
                "text": "",
                "links": [],
                "ok": False,
                "error": error_message,
            }

    @staticmethod
    def _fetch_html(url: str, timeout_seconds: int) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0.0.0 Safari/537.36"
                )
            },
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="ignore")

    @staticmethod
    def _is_transport_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "broken pipe" in text
            or "epipe" in text
            or "target page, context or browser has been closed" in text
            or "connection closed" in text
            or "browser has been closed" in text
        )

    async def _teardown_playwright(self):
        if self.context:
            with suppress(Exception):
                await self.context.close()
        if self.browser:
            with suppress(Exception):
                await self.browser.close()
        if self.playwright:
            with suppress(Exception):
                await self.playwright.stop()
        self.context = None
        self.browser = None
        self.playwright = None

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
