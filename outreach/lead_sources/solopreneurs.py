"""
MECOS Outreach - Solopreneur Lead Source
Scrapes badge sites and personal blogs for solopreneurs.
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from loguru import logger
from outreach.lead_sources.base import LeadSource


class SolopreneurLeadSource(LeadSource):
    """Scrapes solopreneur communities for automation opportunities."""

    BADGE_SITES = [
        "https://builtwith.com/?q=solopreneur",
        "https://www.ossgallery.com/",
        "https://github.com/topics/solopreneur",
    ]

    async def fetch_urls(self) -> List[str]:
        """Fetch URLs from solopreneur communities."""
        urls = []

        # Badge sites
        badge_urls = await self._scrape_badge_sites()
        urls.extend(badge_urls)

        # Personal blogs
        blog_urls = await self._scrape_blog_search()
        urls.extend(blog_urls)

        return urls

    async def _scrape_badge_sites(self) -> List[str]:
        """Scrape 'built with' badge sites."""
        urls = []
        for url in self.BADGE_SITES[:2]:
            try:
                result = await self._fetch_page(url)
                if result.get("ok") and result.get("text"):
                    url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                    found = url_pattern.findall(result["text"])
                    for found_url in found:
                        domain = urlparse(found_url).netloc
                        if "builtwith.com" not in domain and "github.com" not in domain:
                            urls.append(found_url)
            except Exception as e:
                logger.debug(f"Badge site scrape error: {e}")
        return urls[:10]

    async def _scrape_blog_search(self) -> List[str]:
        """Search for solopreneur automation blogs."""
        urls = []
        try:
            # Use the scanner's SearXNG to find blogs
            from config import settings
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                search_url = f"{settings.SEARXNG_URL.rstrip('/')}/search"
                params = {
                    "q": "solopreneur automation tools site:medium.com OR site:dev.to",
                    "format": "json",
                    "language": "en-US",
                    "engines": "bing",
                }
                resp = await client.get(search_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    for result in data.get("results", [])[:8]:
                        url = result.get("url")
                        if url:
                            urls.append(url)
        except Exception as e:
            logger.debug(f"Blog search error: {e}")
        return urls

    def _extract_leads(self, text: str, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract solopreneur leads from scraped content."""
        leads = []
        urls = re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+', text)

        pain_keywords = [
            "side hustle", "solopreneur", "one person", "myself",
            "automation", "save time", "workflow", "tool",
            "no team", "doing everything", "time consuming",
        ]

        for url in urls[:5]:
            domain = urlparse(url).netloc
            pain_indicators = [kw for kw in pain_keywords if kw in text.lower()][:3]

            leads.append({
                "url": url,
                "domain": domain,
                "source_url": source_url,
                "pain_indicators": pain_indicators,
                "signal_score": 4 if len(pain_indicators) >= 3 else 3,
            })
        return leads