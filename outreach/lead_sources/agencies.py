"""
MECOS Outreach - Agency Lead Source
Scrapes Dribbble, Behance, and Clutch.co for agencies.
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from loguru import logger
from outreach.lead_sources.base import LeadSource


class AgencyLeadSource(LeadSource):
    """Scrapes creative/agency communities for automation opportunities."""

    async def fetch_urls(self) -> List[str]:
        """Fetch URLs from agency communities."""
        urls = []

        # Dribbble "for hire"
        dribbble_urls = await self._scrape_dribbble_hire()
        urls.extend(dribbble_urls)

        # Behance portfolios
        behance_urls = await self._scrape_behance()
        urls.extend(behance_urls)

        # Clutch.co profiles
        clutch_urls = await self._scrape_clutch()
        urls.extend(clutch_urls)

        return urls

    async def _scrape_dribbble_hire(self) -> List[str]:
        """Scrape Dribbble for 'for hire' agencies."""
        urls = []
        try:
            search_urls = [
                "https://dribbble.com/players/for_hire",
                "https://dribbble.com/search/agency",
            ]
            for url in search_urls[:2]:
                result = await self._fetch_page(url)
                if result.get("ok") and result.get("text"):
                    url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                    found = url_pattern.findall(result["text"])
                    for found_url in found:
                        domain = urlparse(found_url).netloc
                        if "dribbble.com" not in domain and "behance.net" not in domain:
                            urls.append(found_url)
        except Exception as e:
            logger.debug(f"Dribbble scrape error: {e}")
        return urls[:8]

    async def _scrape_behance(self) -> List[str]:
        """Scrape Behance portfolios for agencies."""
        urls = []
        try:
            url = "https://www.behance.net/search/projects?field=branding&sort=views"
            result = await self._fetch_page(url)
            if result.get("ok") and result.get("text"):
                url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                found = url_pattern.findall(result["text"])
                for found_url in found:
                    domain = urlparse(found_url).netloc
                    if "behance.net" not in domain and "adobe.com" not in domain:
                        urls.append(found_url)
        except Exception as e:
            logger.debug(f"Behance scrape error: {e}")
        return urls[:8]

    async def _scrape_clutch(self) -> List[str]:
        """Scrape Clutch.co for agency profiles."""
        urls = []
        try:
            url = "https://clutch.co/agencies"
            result = await self._fetch_page(url)
            if result.get("ok") and result.get("text"):
                url_pattern = re.compile(r'href="(https://clutch\.co/profile/[^"]+)"')
                for match in url_pattern.finditer(result["text"]):
                    profile_url = match.group(1)
                    # Get the actual agency website
                    profile_result = await self._fetch_page(profile_url)
                    if profile_result.get("ok") and profile_result.get("text"):
                        website_pattern = re.compile(r'"website":"(https?://[^"]+)"')
                        website_match = website_pattern.search(profile_result["text"])
                        if website_match:
                            urls.append(website_match.group(1))
        except Exception as e:
            logger.debug(f"Clutch scrape error: {e}")
        return urls[:8]

    def _extract_leads(self, text: str, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract agency leads from scraped content."""
        leads = []
        urls = re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+', text)

        pain_keywords = [
            "agency", "consulting", "automation", "workflow",
            "tools", "software", "process", "client work",
            "campaign", "marketing", "growth",
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