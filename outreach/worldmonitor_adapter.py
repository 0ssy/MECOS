"""
MECOS Outreach - WorldMonitor Intelligence Adapter
Pulls global intelligence signals from public feeds to score and prioritize leads.
Lightweight adapter — no heavy dependencies, uses requests + feedparser concepts.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from loguru import logger


class WorldMonitorAdapter:
    """
    Lightweight intelligence adapter inspired by WorldMonitor.
    Scans public RSS/news feeds for signals that indicate lead quality:
    - Hiring/funding announcements
    - Company expansion news
    - Industry pain points
    - Geographic opportunity events
    """

    FEED_URLS = [
        "https://hn.algolia.com/rss",
        "https://www.reddit.com/r/startups/new/.rss",
        "https://www.reddit.com/r/Entrepreneur/new/.rss",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.reuters.com/reuters/businessNews",
    ]

    SIGNAL_KEYWORDS = {
        "hiring": ["hiring", "now hiring", "we're growing", "looking for", "join our team"],
        "funding": ["series a", "series b", "series c", "raised", "funding", "investors"],
        "expansion": ["expanding", "opening new", "launching", "new office", "entering market"],
        "pain": ["bottleneck", "manual process", "outdated", "inefficient", "looking for automation"],
        "tech": ["automation", "ai", "machine learning", "workflow", "integration", "api"],
    }

    SIGNAL_WEIGHTS = {
        "hiring": 2.0,
        "funding": 2.5,
        "expansion": 1.5,
        "pain": 1.8,
        "tech": 1.3,
    }

    CACHE_TTL = timedelta(hours=4)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MECOS-Intel/1.0 (lead-intelligence)",
        })
        self.timeout = 12
        self.cache_path = None  # optional file cache path
        self._cache: Dict[str, tuple] = {}  # url -> (timestamp, items)

    def get_signal_multiplier(self, domain: str) -> float:
        """Return a 0.5–2.5x lead quality multiplier based on recent intelligence."""
        try:
            items = self._fetch_recent_signals()
            matched = 0
            total_weight = 0.0
            domain_lower = domain.lower()

            for item in items:
                text = f"{item.get('title','')} {item.get('summary','')}".lower()
                for signal_type, keywords in self.SIGNAL_KEYWORDS.items():
                    if any(kw in text for kw in keywords):
                        matched += 1
                        total_weight += self.SIGNAL_WEIGHTS.get(signal_type, 1.0)

            if matched == 0:
                return 1.0

            avg = total_weight / matched
            boost = min(max(avg, 0.5), 2.5)
            logger.debug(f"Intel boost for {domain}: {boost:.2f}x ({matched} signals)")
            return boost

        except Exception as e:
            logger.debug(f"Intel fetch skipped: {e}")
            return 1.0

    def enrich_lead_score(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust a lead's total_score using external intelligence signals."""
        domain = lead.get("domain", "")
        if not domain:
            return lead

        multiplier = self.get_signal_multiplier(domain)
        base_score = lead.get("total_score", 0)

        lead = dict(lead)
        lead["total_score"] = round(base_score * multiplier, 2)
        lead["intel_multiplier"] = multiplier
        return lead

    def enrich_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score-adjust a batch of leads using intelligence signals."""
        return [self.enrich_lead_score(l) for l in leads]

    def _fetch_recent_signals(self, max_age_hours: int = 12) -> List[Dict[str, Any]]:
        """Fetch and deduplicate recent items from public feeds."""
        now = datetime.now()
        items = []

        for url in self.FEED_URLS:
            if url in self._cache:
                ts, cached = self._cache[url]
                if now - ts < self.CACHE_TTL:
                    items.extend(cached)
                    continue

            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                if resp.status_code != 200:
                    continue
                text = resp.text
                entries = self._parse_rss(text)
                self._cache[url] = (now, entries)
                items.extend(entries)
            except Exception:
                continue

        cutoff = now - timedelta(hours=max_age_hours)
        recent = [
            i for i in items
            if i.get("published", now) >= cutoff
        ]
        return recent[:200]

    def _parse_rss(self, text: str) -> List[Dict[str, Any]]:
        """Minimal RSS/Atom parser — extracts items with title, summary, date."""
        items = []
        title_match = re.findall(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
        desc_match = re.findall(r'<(?:description|summary|content)[^>]*>(.*?)</(?:description|summary|content)>', text, re.IGNORECASE | re.DOTALL)
        date_match = re.findall(r'<(?:pubDate|published|updated)[^>]*>(.*?)</(?:pubDate|published|updated)>', text, re.IGNORECASE | re.DOTALL)

        n = max(len(title_match), len(desc_match))
        for i in range(min(n, 50)):
            title = re.sub(r'<[^>]+>', '', title_match[i]).strip() if i < len(title_match) else ""
            summary = re.sub(r'<[^>]+>', '', desc_match[i]).strip() if i < len(desc_match) else ""
            date_str = date_match[i].strip() if i < len(date_match) else ""
            try:
                pub = datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            except Exception:
                pub = datetime.now()

            if title and len(summary) < 500:
                items.append({
                    "title": title,
                    "summary": summary[:300],
                    "published": pub,
                })

        return items
