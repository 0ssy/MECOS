"""
MECOS Outreach - Scrapling Adapter
Lightweight stealth web scraping wrapper using scrapling Fetcher.
Singleton pattern to share one Fetcher instance across modules.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time as time_module
import warnings
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

scrapling_logger = logging.getLogger("scrapling")
scrapling_logger.setLevel(logging.ERROR)


class ScraplingAdapter:
    """
    Lazy-initialized singleton wrapper for Scrapling Fetcher.
    Provides both sync and async interfaces with httpx fallback.
    """

    _instance: Optional["ScraplingAdapter"] = None
    _fetcher: Optional[Any] = None

    def __new__(cls) -> "ScraplingAdapter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._fetcher = None
        self._initialized = False
        self.timeout = 15
        self.user_agent = "MECOS/1.0 (+https://github.com/0ssy/MECOS)"
        self._cache: Dict[str, Dict[str, Any]] = {}
        ssl_bypass_env = os.getenv("SCRAPING_SKIP_SSL_VERIFY", "")
        self._ssl_bypass = ssl_bypass_env.split(",") if ssl_bypass_env else []

    def _get_cached(self, url: str) -> Optional[Dict[str, Any]]:
        if url in self._cache:
            ts, result = self._cache[url]
            if time_module.time() - ts < 300:
                return result
            del self._cache[url]
        return None

    def _set_cache(self, url: str, result: Dict[str, Any]):
        self._cache[url] = (time_module.time(), result)

    def _ensure_fetcher(self):
        """Lazy-initialize the Scrapling Fetcher on first use."""
        if self._fetcher is not None:
            return self._fetcher

        try:
            from scrapling import Fetcher
            self._fetcher = Fetcher
            self._initialized = True
            logger.info("Scrapling Fetcher class loaded (singleton).")
        except ImportError as e:
            logger.warning(f"Scrapling not available: {e}")
            self._fetcher = None
        except Exception as e:
            logger.warning(f"Scrapling initialization failed: {e}")
            self._fetcher = None

        return self._fetcher

    def fetch(
        self,
        url: str,
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a URL using Scrapling with httpx fallback.
        Returns dict with ok, text, html, status_code, error keys.
        Uses 5-minute cache to prevent repeated fetches.
        """
        timeout = timeout or self.timeout

        cached = self._get_cached(url)
        if cached:
            return cached

        result = self._fetch_with_scrapling(url, timeout, headers)

        if not result.get("ok") or result.get("status_code", 200) != 200:
            result = self._fetch_with_httpx(url, timeout, headers)

        self._set_cache(url, result)
        return result

    async def fetch_async(
        self,
        url: str,
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Async fetch using httpx with scrapling fallback."""
        timeout = timeout or self.timeout

        cached = self._get_cached(url)
        if cached:
            return cached

        result = await self._fetch_with_scrapling_async(url, timeout, headers)

        if not result.get("ok") or result.get("status_code", 200) != 200:
            result = await self._fetch_with_httpx_async(url, timeout, headers)

        self._set_cache(url, result)
        return result

    def _fetch_with_scrapling(
        self,
        url: str,
        timeout: int,
        headers: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Attempt fetch using Scrapling. Returns empty result on failure."""
        try:
            Fetcher = self._ensure_fetcher()
            if Fetcher is None:
                return {"ok": False, "text": "", "html": "", "error": "scrapling_unavailable"}

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*Proxy.*")
                warnings.simplefilter("ignore")
                response = Fetcher.get(url)

            if response is None:
                return {"ok": False, "text": "", "html": "", "error": "no_response"}

            html = response.html_content if hasattr(response, "html_content") else str(response)
            text = response.get_all_text() if hasattr(response, "get_all_text") else str(response)

            return {
                "ok": True,
                "text": text,
                "html": html,
                "status_code": 200,
            }
        except Exception as e:
            logger.debug(f"Scrapling fetch failed for {url}: {e}")
            return {"ok": False, "text": "", "html": "", "error": str(e)}

    async def _fetch_with_scrapling_async(
        self,
        url: str,
        timeout: int,
        headers: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Async wrapper for scrapling fetch."""
        try:
            Fetcher = self._ensure_fetcher()
            if Fetcher is None:
                return {"ok": False, "text": "", "html": "", "error": "scrapling_unavailable"}

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*Proxy.*")
                warnings.simplefilter("ignore")
                response = await asyncio.to_thread(Fetcher.get, url)

            if response is None:
                return {"ok": False, "text": "", "html": "", "error": "no_response"}

            html = response.html_content if hasattr(response, "html_content") else str(response)
            text = response.get_all_text() if hasattr(response, "get_all_text") else str(response)

            return {
                "ok": True,
                "text": text,
                "html": html,
                "status_code": 200,
            }
        except Exception as e:
            logger.debug(f"Scrapling fetch failed for {url}: {e}")
            return {"ok": False, "text": "", "html": "", "error": str(e)}

    def _fetch_with_httpx(
        self,
        url: str,
        timeout: int,
        headers: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Fallback fetch using httpx with standard headers."""
        try:
            return asyncio.run(self._fetch_with_httpx_async(url, timeout, headers))
        except Exception as e:
            logger.debug(f"Httpx fallback failed for {url}: {e}")
            return {"ok": False, "text": "", "html": "", "error": str(e)}

    def _should_skip_ssl_verify(self, url: str) -> bool:
        """Check if SSL verification should be skipped for this URL."""
        try:
            hostname = urlparse(url).hostname or ""
            return any(
                skip_host and hostname.endswith(skip_host)
                for skip_host in self._ssl_bypass
                if skip_host
            )
        except Exception:
            return False

    async def _fetch_with_httpx_async(
        self,
        url: str,
        timeout: int,
        headers: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Async fetch using httpx."""
        try:
            req_headers = headers or {
                "User-Agent": self.user_agent,
            }
            verify = not self._should_skip_ssl_verify(url)
            if self._should_skip_ssl_verify(url):
                hostname = urlparse(url).hostname or "unknown"
                logger.debug(f"SSL verification skipped for {hostname}")
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, verify=verify
            ) as client:
                resp = await client.get(url, headers=req_headers)

            html = resp.text
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)

            return {
                "ok": resp.status_code == 200,
                "text": clean_text,
                "html": html,
                "status_code": resp.status_code,
                "error": f"HTTP {resp.status_code}" if resp.status_code != 200 else "",
            }
        except Exception as e:
            logger.debug(f"Httpx fetch failed for {url}: {e}")
            return {"ok": False, "text": "", "html": "", "error": str(e)}


def get_scrapling_adapter() -> ScraplingAdapter:
    """Get the singleton ScraplingAdapter instance."""
    return ScraplingAdapter()