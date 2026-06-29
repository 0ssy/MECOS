"""
MECOS Outreach - Creator Lead Source
Scrapes Medium publications and YouTube for content creators.
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from loguru import logger
from outreach.lead_sources.base import LeadSource


class CreatorLeadSource(LeadSource):
    """Scrapes creator communities for automation needs."""

    async def fetch_urls(self) -> List[str]:
        """Fetch URLs from creator communities."""
        urls = []

        # Medium publications about tools
        medium_urls = await self._scrape_medium_tools()
        urls.extend(medium_urls)

        # YouTube video descriptions (via search)
        youtube_urls = await self._scrape_youtube_search()
        urls.extend(youtube_urls)

        # Reddit r/YouTubers
        reddit_urls = await self._scrape_reddit_creators()
        urls.extend(reddit_urls)

        return urls

    async def _scrape_medium_tools(self) -> List[str]:
        """Scrape Medium for tool-related publications."""
        urls = []
        try:
            search_urls = [
                "https://medium.com/tag/tools-for-creators",
                "https://medium.com/tag/automation-tools",
            ]
            for url in search_urls[:2]:
                result = await self._fetch_page(url)
                if result.get("ok") and result.get("text"):
                    url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                    found = url_pattern.findall(result["text"])
                    for found_url in found:
                        domain = urlparse(found_url).netloc
                        if "medium.com" not in domain and "youtube.com" not in domain:
                            urls.append(found_url)
        except Exception as e:
            logger.debug(f"Medium scrape error: {e}")
        return urls[:8]

    async def _scrape_youtube_search(self) -> List[str]:
        """Scrape YouTube search for creator tool inquiries."""
        urls = []
        try:
            url = "https://www.youtube.com/results?search_query=automation+tools+for+creators"
            result = await self._fetch_page(url)
            if result.get("ok") and result.get("text"):
                # Extract channel URLs
                channel_pattern = re.compile(r'href="/@([^"]+)"')
                channels = channel_pattern.findall(result["text"])
                for channel in channels[:5]:
                    urls.append(f"https://www.youtube.com/@{channel}")
        except Exception as e:
            logger.debug(f"YouTube scrape error: {e}")
        return urls[:5]

    async def _scrape_reddit_creators(self) -> List[str]:
        """Scrape Reddit creator communities."""
        urls = []
        try:
            url = "https://www.reddit.com/r/YouTubers/new.json?limit=20"
            result = await self._fetch_page(url)
            if result.get("ok") and result.get("text"):
                import json
                data = json.loads(result["text"])
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = child.get("data", {})
                    url_in_post = post.get("url")
                    if url_in_post and "reddit.com" not in url_in_post:
                        urls.append(url_in_post)
        except Exception as e:
            logger.debug(f"Reddit creators scrape error: {e}")
        return urls[:8]

    def _extract_leads(self, text: str, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract creator leads from scraped content."""
        leads = []
        urls = re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+', text)

        pain_keywords = [
            "schedule", "post", "publish", "content calendar",
            "automation", "tool", "platform", "workflow",
            "time consuming", "spreadsheet", "no system",
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