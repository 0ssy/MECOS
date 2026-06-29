"""
MECOS Outreach - SaaS Lead Source
Scrapes Product Hunt, Indie Hackers, and Hacker News for SaaS startups.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from loguru import logger

try:
    from outreach.scrapling_adapter import get_scrapling_adapter
except ImportError:
    get_scrapling_adapter = None

from config import settings
from outreach.lead_sources.base import LeadSource


class SaaSLeadSource(LeadSource):
    """Scrapes SaaS communities for leads showing automation pain."""

    SOURCES = {
        "producthunt": "https://www.producthunt.com/feed",
        "indiehackers": "https://www.indiehackers.com/search?q=automation&type=posts",
        "show_hn": "https://hn.algolia.com/api/v1/search?tags=show_hn&hitsPerPage=30",
    }

    def __init__(self, max_leads: int = 25):
        super().__init__("saas", max_leads)
        self.session_headers = {
            "User-Agent": "MECOS/1.0 (+https://github.com/0ssy/MECOS)",
        }

    async def fetch_urls(self) -> List[str]:
        """Fetch URLs from SaaS communities."""
        urls = []
        now = datetime.now().isoformat()

        # Product Hunt - Get recent products
        ph_urls = await self._scrape_producthunt()
        urls.extend(ph_urls)

        # Indie Hackers - Search for automation posts
        ih_urls = await self._scrape_indiehackers_automation()
        urls.extend(ih_urls)

        # Show HN - Recent show posts
        hn_urls = await self._scrape_show_hn()
        urls.extend(hn_urls)

        return urls

    async def _scrape_producthunt(self) -> List[str]:
        """Scrape Product Hunt for newly launched products."""
        urls = []
        try:
            url = "https://www.producthunt.com/feed"
            result = await self._fetch_page(url, timeout=20)
            if result.get("ok") and result.get("html"):
                # Look for product links
                href_pattern = re.compile(r'href="(https://www\.producthunt\.com/products/[^"]+)"')
                for match in href_pattern.finditer(result["html"]):
                    product_url = match.group(1)
                    # Get the actual product website from product page
                    product_page = await self._fetch_page(product_url)
                    if product_page.get("ok") and product_page.get("html"):
                        website_pattern = re.compile(r'href="(https?://[^"\'\s]+)"[^>]*>.*?Visit.*?<')
                        website_match = website_pattern.search(product_page["html"])
                        if website_match:
                            urls.append(website_match.group(1))
        except Exception as e:
            logger.debug(f"Product Hunt scrape error: {e}")
        return urls[:10]

    async def _scrape_indiehackers_automation(self) -> List[str]:
        """Scrape Indie Hackers for automation-related posts."""
        urls = []
        try:
            url = "https://www.indiehackers.com/search?q=automation&type=posts"
            result = await self._fetch_page(url)
            if result.get("ok") and result.get("text"):
                # Extract URLs from search results
                url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                found = url_pattern.findall(result["text"])
                # Filter to likely business URLs
                for found_url in found:
                    domain = urlparse(found_url).netloc
                    if "indiehackers.com" not in domain and "github.com" not in domain:
                        urls.append(found_url)
        except Exception as e:
            logger.debug(f"Indie Hackers scrape error: {e}")
        return urls[:10]

    async def _scrape_show_hn(self) -> List[str]:
        """Scrape Hacker News Show HN posts."""
        urls = []
        try:
            url = "https://hn.algolia.com/api/v1/search?tags=show_hn&hitsPerPage=30"
            if get_scrapling_adapter:
                result = await get_scrapling_adapter().fetch_async(url, timeout=15)
                if result.get("ok"):
                    import json
                    data = json.loads(result["text"])
                    hits = data.get("hits", [])
                    for hit in hits:
                        story_url = hit.get("url")
                        if story_url and "news.ycombinator.com" not in story_url:
                            urls.append(story_url)
        except Exception as e:
            logger.debug(f"Show HN scrape error: {e}")
        return urls[:10]

    def _extract_leads(self, text: str, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract SaaS leads from scraped content."""
        leads = []
        urls = re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+', text)

        pain_keywords = [
            "built with", "powered by", "api", "integration",
            "workflow", "automation", "tool", "saas", "platform",
            "no-code", "low-code", "looking for", "need help",
        ]

        for url in urls[:5]:
            domain = urlparse(url).netloc
            pain_indicators = [kw for kw in pain_keywords if kw in text.lower()][:3]

            leads.append({
                "url": url,
                "domain": domain,
                "source_url": source_url,
                "pain_indicators": pain_indicators,
                "signal_score": 3 if len(pain_indicators) >= 2 else 2,
            })
        return leads