"""
MECOS Outreach - Email Enricher
Multi-strategy email discovery for leads:
1. Website scraping (contact pages, mailto links)
2. Pattern guessing (firstname.lastname@domain.com patterns)
3. API enrichment (Hunter.io, Apollo, BetterContact if keys available)
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from loguru import logger


class EmailEnricher:
    """Discovers and enriches lead email addresses via multiple strategies."""

    def __init__(self):
        self.api_keys = {
            "hunter": os.getenv("HUNTER_API_KEY", ""),
            "apollo": os.getenv("APOLLO_API_KEY", ""),
            "bettercontact": os.getenv("BETTERCONTACT_API_KEY", ""),
        }
        self.headers = {
            "User-Agent": "MECOS Lead Enrichment Bot/1.0"
        }
        self.timeout = 10

    async def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single lead with discovered email addresses."""
        domain = lead.get("domain", "")
        url = lead.get("url", "")
        contacts = lead.get("contacts", {})

        if not domain:
            return lead

        # Skip if email already exists
        if contacts.get("emails"):
            return lead

        emails = []
        source = None

        # Strategy 1: Website scraping
        scraped = self._scrape_website(url, domain)
        if scraped:
            emails.extend(scraped)
            source = "website_scrape"

        # Strategy 2: API enrichment (if keys available)
        if not emails:
            api_email = self._api_enrich(domain, lead)
            if api_email:
                emails.append(api_email)
                source = "api"

        # Strategy 3: Pattern guessing (only if no better source)
        if not emails:
            guessed = self._guess_emails(domain, lead)
            emails.extend(guessed)
            source = "pattern_guess"

        if emails:
            lead = dict(lead)
            lead["contacts"] = dict(contacts)
            lead["contacts"]["emails"] = emails
            lead["contacts"]["email_source"] = source
            lead["contacts"]["email_confidence"] = self._confidence_score(source, emails)
            logger.info(f"Enriched {domain}: {emails[0]} ({source})")

        return lead

    async def enrich_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich a batch of leads."""
        enriched = []
        for lead in leads:
            try:
                enriched.append(await self.enrich_lead(lead))
            except Exception as e:
                logger.debug(f"Enrichment failed for {lead.get('domain')}: {e}")
                enriched.append(lead)
        return enriched

    def _scrape_website(self, url: str, domain: str) -> List[str]:
        """Scrape website pages for email addresses."""
        emails = set()
        pages_to_check = []

        if url:
            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            pages_to_check = [
                url,
                urljoin(base, "/"),
                urljoin(base, "/contact"),
                urljoin(base, "/about"),
                urljoin(base, "/team"),
                urljoin(base, "/about-us"),
            ]

        # Also try the domain directly
        if domain and not url:
            pages_to_check = [
                f"https://{domain}",
                f"https://{domain}/contact",
                f"https://{domain}/about",
                f"http://{domain}",
            ]

        email_pattern = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
        exclude_patterns = re.compile(
            r'(example\.com|test\.com|domain\.com|placeholder|sentry|wixpress|wysiwyg|'
            r'webpack|babel|github|google|jquery|bootstrap|fontawesome|'
            r'@\d+\.\d+\.\d+\.\d+|\.(png|jpg|gif|svg|css|js|woff|ttf))',
            re.IGNORECASE
        )

        for page in pages_to_check:
            try:
                resp = requests.get(page, headers=self.headers, timeout=self.timeout, allow_redirects=True)
                if resp.status_code != 200:
                    continue
                text = resp.text
                found = email_pattern.findall(text)
                for email in found:
                    email = email.lower().strip()
                    if not exclude_patterns.search(email):
                        emails.add(email)
                if emails:
                    break
            except Exception:
                continue

        return list(emails)

    def _api_enrich(self, domain: str, lead: Dict[str, Any]) -> Optional[str]:
        """Try API-based email enrichment."""
        # Hunter.io
        if self.api_keys.get("hunter"):
            email = self._hunter_find(domain)
            if email:
                return email

        # Apollo
        if self.api_keys.get("apollo"):
            email = self._apollo_find(domain, lead)
            if email:
                return email

        # BetterContact
        if self.api_keys.get("bettercontact"):
            email = self._bettercontact_find(domain, lead)
            if email:
                return email

        return None

    def _hunter_find(self, domain: str) -> Optional[str]:
        """Use Hunter.io to find emails."""
        try:
            url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={self.api_keys['hunter']}&limit=1"
            resp = requests.get(url, timeout=self.timeout)
            data = resp.json()
            emails = data.get("data", {}).get("emails", [])
            if emails:
                return emails[0].get("value")
        except Exception as e:
            logger.debug(f"Hunter.io lookup failed: {e}")
        return None

    def _apollo_find(self, domain: str, lead: Dict[str, Any]) -> Optional[str]:
        """Use Apollo API to find emails."""
        try:
            url = "https://api.apollo.io/v1/people/match"
            headers = {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
            }
            payload = {
                "api_key": self.api_keys["apollo"],
                "domain": domain,
                "person_locations": [],
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            data = resp.json()
            person = data.get("person", {})
            email = person.get("email")
            if email and not email.endswith("@example.com"):
                return email
        except Exception as e:
            logger.debug(f"Apollo lookup failed: {e}")
        return None

    def _bettercontact_find(self, domain: str, lead: Dict[str, Any]) -> Optional[str]:
        """Use BetterContact finder."""
        try:
            # BetterContact uses URL for finding
            url = lead.get("url", f"https://{domain}")
            api_url = f"https://api.bettercontact.rocks/v1/find-email"
            payload = {
                "url": url,
                "api_key": self.api_keys["bettercontact"],
            }
            resp = requests.post(api_url, json=payload, timeout=self.timeout)
            data = resp.json()
            email = data.get("email")
            if email:
                return email
        except Exception as e:
            logger.debug(f"BetterContact lookup failed: {e}")
        return None

    def _guess_emails(self, domain: str, lead: Dict[str, Any]) -> List[str]:
        """Guess likely email patterns for a domain."""
        guessed = []
        name = lead.get("contact_name", "") or lead.get("name", "")

        if not name:
            return guessed

        parts = name.lower().strip().split()
        if len(parts) < 2:
            return guessed

        first = parts[0]
        last = parts[-1]
        patterns = [
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{first[0]}{last}@{domain}",
            f"{last}.{first}@{domain}",
            f"{first}@{domain}",
        ]

        for email in patterns:
            guessed.append(email)

        return guessed[:3]

    def _confidence_score(self, source: str, emails: List[str]) -> str:
        """Rate confidence of discovered email."""
        if source == "website_scrape":
            return "high"
        if source == "api":
            return "high"
        if source == "pattern_guess":
            return "low"
        return "unknown"

    def get_summary(self) -> Dict[str, Any]:
        """Get enricher status."""
        return {
            "apis_available": [k for k, v in self.api_keys.items() if v],
            "hunter": bool(self.api_keys.get("hunter")),
            "apollo": bool(self.api_keys.get("apollo")),
            "bettercontact": bool(self.api_keys.get("bettercontact")),
        }
