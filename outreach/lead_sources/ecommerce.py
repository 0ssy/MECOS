"""
MECOS Outreach - E-commerce Lead Source
Scrapes Shopify Community, Reddit r/ecommerce, and WooCommerce showcases.
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from loguru import logger
from outreach.lead_sources.base import LeadSource


class EcommerceLeadSource(LeadSource):
    """Scrapes e-commerce communities for automation pain signals."""

    def __init__(self, max_leads: int = 25):
        super().__init__("ecommerce", max_leads)

    async def fetch_urls(self) -> List[str]:
        """Fetch URLs from e-commerce communities."""
        urls = []

        # Shopify Community
        shopify_urls = await self._scrape_shopify_community()
        urls.extend(shopify_urls)

        # Reddit r/ecommerce
        reddit_urls = await self._scrape_reddit_ecommerce()
        urls.extend(reddit_urls)

        # WooCommerce showcase
        woo_urls = await self._scrape_woo_sites()
        urls.extend(woo_urls)

        return urls

    async def _scrape_shopify_community(self) -> List[str]:
        """Scrape Shopify Community forums for pain signals."""
        urls = []
        try:
            search_urls = [
                "https://community.shopify.com/c/ecommerce-discussions/new",
                "https://community.shopify.com/c/shopify-discussion/new",
            ]
            for url in search_urls[:2]:
                result = await self._fetch_page(url)
                if result.get("ok") and result.get("text"):
                    # Look for external links in discussions
                    url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                    found = url_pattern.findall(result["text"])
                    # Filter out Shopify domains
                    for found_url in found:
                        domain = urlparse(found_url).netloc
                        if "shopify.com" not in domain and "community.shopify.com" not in domain:
                            urls.append(found_url)
        except Exception as e:
            logger.debug(f"Shopify community scrape error: {e}")
        return urls[:8]

    async def _scrape_reddit_ecommerce(self) -> List[str]:
        """Scrape Reddit r/ecommerce for business links."""
        urls = []
        try:
            url = "https://www.reddit.com/r/ecommerce/new.json?limit=25"
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
            logger.debug(f"Reddit ecommerce scrape error: {e}")
        return urls[:8]

    async def _scrape_woo_sites(self) -> List[str]:
        """Scrape WooCommerce showcase sites."""
        urls = []
        try:
            url = "https://woocommerce.com/posts/"
            result = await self._fetch_page(url)
            if result.get("ok") and result.get("text"):
                url_pattern = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
                found = url_pattern.findall(result["text"])
                for found_url in found:
                    domain = urlparse(found_url).netloc
                    if "woocommerce.com" not in domain:
                        urls.append(found_url)
        except Exception as e:
            logger.debug(f"WooCommerce scrape error: {e}")
        return urls[:5]

    def _extract_leads(self, text: str, html: str, source_url: str) -> List[Dict[str, Any]]:
        """Extract e-commerce leads from scraped content."""
        leads = []
        urls = re.findall(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+', text)

        pain_keywords = [
            "checkout", "cart abandonment", "inventory", "order ful",
            "fulfillment", "shipping", "manual order", "no system",
            "spreadsheet", "copy paste", "time consuming",
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