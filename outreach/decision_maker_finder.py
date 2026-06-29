"""
MECOS Outreach - Decision Maker Finder
Extracts names, titles, and social profiles from company "about" pages.
Enhances email enrichment with contact pattern detection.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger

try:
    from outreach.scrapling_adapter import get_scrapling_adapter
except ImportError:
    get_scrapling_adapter = None


class DecisionMakerFinder:
    """Finds decision makers (founders, executives) at companies."""

    TITLE_PATTERNS = [
        r"(founder|ceo|cto|cmo|coo|chief|co-founder|co.founder)",
        r"(owner|partner|director|head of|lead)",
        r"(president|vp|vice president)",
    ]

    SOCIAL_PATTERNS = {
        "twitter": re.compile(r'(?:twitter\.com|x\.com)/@([a-zA-Z0-9_]+)'),
        "linkedin": re.compile(r'linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)'),
        "github": re.compile(r'github\.com/([a-zA-Z0-9_-]+)'),
    }

    EMAIL_PATTERNS = [
        r"[a-zA-Z0-9._%+\-]+@(?:.*?\.)?(?:founder|ceo|owner)[^@\s]*\.[a-zA-Z]{2,}",
        r"(?:founder|ceo|owner)[a-zA-Z0-9._%+\-]*@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": "MECOS Decision Maker Finder/1.0",
        }
        self.timeout = 10

    async def find_for_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Find decision maker info for a lead."""
        url = lead.get("url", "")
        domain = lead.get("domain", "")

        if not url and domain:
            url = f"https://{domain}"

        lead = dict(lead)
        contacts = dict(lead.get("contacts", {}))

        # Scrape about pages
        about_pages = self._get_about_pages(url)
        decision_maker = None

        for page in about_pages:
            result = await self._fetch_page(page)
            if result.get("ok"):
                decision_maker = self._extract_decision_maker(result["text"], domain)
                if decision_maker:
                    contacts["decision_maker"] = decision_maker
                    break

        # Extract social profiles
        social_profiles = self._extract_socials(lead.get("contacts", {}).get("social", []))
        contacts["social_profiles"] = social_profiles

        # Find founder email patterns
        founder_emails = self._find_founder_emails(lead)
        if founder_emails:
            contacts["founder_emails"] = founder_emails

        lead["contacts"] = contacts
        return lead

    def _get_about_pages(self, url: str) -> List[str]:
        """Get likely about/contact pages for a URL."""
        pages = []
        if url:
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            pages = [
                f"{base}/about",
                f"{base}/team",
                f"{base}/about-us",
                f"{base}/contact",
                url,
            ]
        return pages

    async def _fetch_page(self, url: str) -> Dict[str, Any]:
        """Fetch page content."""
        if get_scrapling_adapter:
            try:
                return await get_scrapling_adapter().fetch_async(url, timeout=self.timeout, headers=self.headers)
            except Exception:
                pass

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=self.headers)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()
                return {"ok": True, "text": soup.get_text(separator="\n"), "html": resp.text}
        except Exception as e:
            return {"ok": False, "text": "", "html": "", "error": str(e)}

    def _extract_decision_maker(self, text: str, domain: str) -> Optional[Dict[str, str]]:
        """Extract decision maker name and title from page text."""
        text_lower = text.lower()

        # Look for founder/CEO patterns
        for pattern in self.TITLE_PATTERNS:
            matches = re.findall(
                rf"([^\n.,]+?)\s*[,\n]?\s*(?:-{2,}|\|)?\s*\b{pattern}\b[^a-z]",
                text,
                re.IGNORECASE,
            )
            if matches:
                name = matches[0].strip()
                if name and len(name) < 50:
                    return {"name": name, "title": "founder", "source": "about_page"}

        return None

    def _extract_socials(self, existing_social: List[str]) -> Dict[str, str]:
        """Map social indicators to profile URLs."""
        profiles = {}
        for platform in existing_social:
            if platform in ("twitter.com", "x.com"):
                profiles["twitter"] = f"https://twitter.com/@{platform}"
            elif platform == "linkedin.com":
                profiles["linkedin"] = "https://linkedin.com/company"
        return profiles

    def _find_founder_emails(self, lead: Dict[str, Any]) -> List[str]:
        """Generate likely founder email patterns."""
        domain = lead.get("domain", "")
        if not domain:
            return []

        patterns = [
            f"founder@{domain}",
            f"ceo@{domain}",
            f"hello@{domain}",
            f"team@{domain}",
        ]

        # Try to extract from existing emails
        for email in lead.get("contacts", {}).get("emails", []):
            if any(kw in email.lower() for kw in ["founder", "ceo", "owner"]):
                patterns.insert(0, email)

        return list(set(patterns))[:3]

    async def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for find_for_lead."""
        return await self.find_for_lead(lead)