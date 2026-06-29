"""
MECOS Outreach - Lead Source Base
Abstract base for industry-specific lead scrapers.
"""

from __future__ import annotations

import asyncio
import json
import time as time_module
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx
from loguru import logger

try:
    from outreach.scrapling_adapter import get_scrapling_adapter
except ImportError:
    get_scrapling_adapter = None

from config import settings


class LeadSource(ABC):
    """Base class for industry-specific lead sources."""

    def __init__(self, source_name: str, max_leads: int = 25):
        self.source_name = source_name
        self.max_leads = max_leads
        self.feed_path = settings.DATA_DIR / "outreach" / "lead_feeds" / f"{source_name}.jsonl"
        self.feed_path.parent.mkdir(parents=True, exist_ok=True)
        self._fetch_semaphore = asyncio.Semaphore(2)
        self._last_fetch: float = 0
        self._cache_ttl = 3600  # 1 hour

    async def fetch_urls(self) -> List[str]:
        """Fetch candidate URLs - to be implemented by subclasses."""
        return []

    def _save_lead(self, lead: Dict[str, Any]) -> None:
        """Save lead to source-specific JSONL feed."""
        lead_record = {
            "url": lead.get("url", ""),
            "domain": lead.get("domain", ""),
            "discovered_at": datetime.now().isoformat(),
            "source": self.source_name,
            "pain_indicators": lead.get("pain_indicators", []),
            "signal_score": lead.get("signal_score", 1),
        }
        try:
            with open(self.feed_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(lead_record, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to save lead to feed: {e}")

    async def _fetch_page(self, url: str, timeout: int = 15) -> Dict[str, Any]:
        """Fetch page content using scrapling adapter with httpx fallback."""
        if get_scrapling_adapter:
            try:
                result = await get_scrapling_adapter().fetch_async(url, timeout=timeout)
                if result.get("ok"):
                    return {"ok": True, "text": result.get("text", ""), "html": result.get("html", "")}
            except Exception as e:
                logger.debug(f"Scrapling fetch failed for {url}: {e}")

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                if resp.status_code != 200:
                    return {"ok": False, "text": "", "html": ""}
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator="\n")
                return {"ok": True, "text": text, "html": resp.text}
        except Exception as e:
            return {"ok": False, "text": "", "html": "", "error": str(e)}

    async def _check_cache(self) -> bool:
        """Check if cache is still valid."""
        if not self.feed_path.exists():
            return False
        try:
            stat = self.feed_path.stat()
            return (time_module.time() - stat.st_mtime) < self._cache_ttl
        except Exception:
            return False

    def _is_cached(self) -> bool:
        return self.feed_path.exists()

    async def get_leads(self) -> List[Dict[str, Any]]:
        """Get leads from this source, using cache if available."""
        if self._check_cache():
            return self._load_cached()

        leads = []
        urls = await self.fetch_urls()
        async def process_url(url: str) -> None:
            async with self._fetch_semaphore:
                result = await self._fetch_page(url)
                if result.get("ok") and result.get("text"):
                    leads.extend(self._extract_leads(result["text"], result["html"], url))

        await asyncio.gather(*[process_url(u) for u in urls])
        self._save_batch(leads)
        return leads

    def _extract_leads(self, text: str, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract lead data from page content - to be implemented by subclasses."""
        return []

    def _save_batch(self, leads: List[Dict[str, Any]]) -> None:
        """Save multiple leads to feed."""
        if not leads:
            return
        with open(self.feed_path, "a", encoding="utf-8") as f:
            for lead in leads[:self.max_leads]:
                self._save_lead(lead)

    def _load_cached(self) -> List[Dict[str, Any]]:
        """Load cached leads from feed file."""
        leads = []
        try:
            with open(self.feed_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        leads.append(json.loads(line))
        except Exception:
            pass
        return leads