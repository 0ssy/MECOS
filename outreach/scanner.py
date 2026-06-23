"""
MECOS Outreach - Scanner
Autonomous web scanner that detects lead signals across four categories:
A) Inefficiency markers, B) Pain point indicators, C) Revenue fit, D) Organic intent.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
import hashlib
import time as time_module

from loguru import logger
from config import settings
from memory_system import MemorySystem
from browser_automation import BrowserAutomation
from web_perception import WebPerception


PAIN_KEYWORDS = [
    "manual data entry", "too much time", "wasting time", "bottleneck",
    "error prone", "spreadsheet hell", "copy paste", "repetitive",
    "can't keep up", "hiring someone to", "out of control", "messy",
    "no system", "disorganized", "frustrated with", "drowning in",
    "looking for automation", "need help with", "recommend a bot",
    "automation needed", "workflow bottleneck", "process improvement",
    "manual work", "time consuming", "inefficient process",
]
INEFFICIENCY_MARKERS = [
    "no chatbot", "contact form", "no api", "hours of operation",
    "call during", "email us at", "manual process", "paperwork",
    "please allow", "processing time", "business days", "mailing address",
    "fax", "walk in", "appointment only", "call for pricing",
]
ORGANIC_INTENT_PHRASES = [
    "we need help with", "looking for automation", "automate our",
    "build us a bot", "need a tool that", "recommend a bot",
    "anyone know a tool", "software that can", "integration for",
    "automation needed", "workflow help", "bot for",
]
REVENUE_FIT_SIGNALS = [
    "hiring", "now hiring", "we're growing", "series a", "series b",
    "funded", "expansion", "opening new", "enterprise", "fortune",
    "inc 5000", "fastest growing", "small business", "local business",
    "founder", "startup", "freelancer", "contract", "$500",
]


class OutreachScanner:
    def __init__(self, memory: MemorySystem, browser: Optional[BrowserAutomation] = None,
                 web_perception: Optional[WebPerception] = None):
        self.memory = memory
        self.browser = browser or BrowserAutomation()
        self.web_perception = web_perception or WebPerception(memory)
        self.leads: List[Dict[str, Any]] = []
        self.scanned_urls: set = set()
        self.scanned_content_hashes: set = set()  # For deduplication
        self.scan_cycles_by_url: Dict[str, float] = {}  # Last scan timestamp per URL
        self.save_path = settings.DATA_DIR / "outreach" / "leads.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_leads()

    def _load_leads(self):
        if self.save_path.exists():
            try:
                self.leads = json.loads(self.save_path.read_text())
                logger.info(f"Loaded {len(self.leads)} existing leads")
            except Exception as e:
                logger.warning(f"Failed to load leads: {e}")
                self.leads = []
        self._restore_dedup_state()

    def _restore_dedup_state(self):
        from datetime import datetime as dt
        restored_urls = 0
        restored_hashes = 0
        for lead in self.leads:
            url = lead.get("url")
            discovered_at = lead.get("discovered_at")
            content_hash = lead.get("content_hash")
            if url and discovered_at:
                try:
                    ts = dt.fromisoformat(discovered_at).timestamp()
                    self.scan_cycles_by_url[url] = ts
                    restored_urls += 1
                except Exception:
                    pass
            if content_hash:
                self.scanned_content_hashes.add(content_hash)
                restored_hashes += 1
        logger.info(
            f"Dedup state restored: {restored_urls} URLs, {restored_hashes} content hashes from leads.json"
        )

    def _save_leads(self):
        try:
            self.save_path.write_text(json.dumps(self.leads[-500:], default=str))
        except Exception as e:
            logger.error(f"Failed to save leads: {e}")

    async def startup(self):
        await self.browser.startup()
        await self.web_perception.startup()

    async def shutdown(self):
        await self.browser.shutdown()
        await self.web_perception.shutdown()
        self._save_leads()

    def _score_signal(self, text: str, url: str) -> Dict[str, Any]:
        text_lower = text.lower()
        signals = {
            "inefficiency_markers": 0,
            "pain_points": 0,
            "organic_intent": 0,
            "revenue_fit": 0,
        }
        matched = []

        for kw in INEFFICIENCY_MARKERS:
            if kw in text_lower:
                signals["inefficiency_markers"] += 1
                matched.append(kw)

        for kw in PAIN_KEYWORDS:
            if kw in text_lower:
                signals["pain_points"] += 1
                matched.append(kw)

        for phrase in ORGANIC_INTENT_PHRASES:
            if phrase in text_lower:
                signals["organic_intent"] += 1
                matched.append(phrase)

        for kw in REVENUE_FIT_SIGNALS:
            if kw in text_lower:
                signals["revenue_fit"] += 1
                matched.append(kw)

        total = sum(signals.values())
        return {
            "url": url,
            "signals": signals,
            "total_score": total,
            "matched_terms": matched[:10],
        }

    def _extract_contact_hints(self, text: str, html: str) -> Dict[str, List[str]]:
        email_re = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
        emails = list(set(email_re.findall(text + " " + html)))
        emails = [e for e in emails if not any(x in e.lower() for x in [
            "example.com", "sentry", "webpack", "svg", "png", "jpg", "jpeg",
            "placeholder", "noreply", "no-reply", "github.com", "w3.org",
        ])][:5]

        phone_re = re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")
        phones = list(set(phone_re.findall(text)))[:3]

        social = []
        for platform in ["twitter.com", "x.com", "linkedin.com", "reddit.com"]:
            if platform in html:
                social.append(platform)

        return {"emails": emails, "phones": phones, "social": social}

    async def scan_url(self, url: str) -> Optional[Dict[str, Any]]:
        # Check 24h deduplication window
        now = time_module.time()
        last_scan = self.scan_cycles_by_url.get(url, 0)
        if now - last_scan < 86400:  # 24 hours in seconds
            return None
        self.scan_cycles_by_url[url] = now

        result = await self.web_perception.ingest_url(url)
        if not result.get("ok") or not result.get("text"):
            return None

        text = result["text"]
        html = result.get("html", "")
        
        # Content hash deduplication
        content_hash = hashlib.md5((text + html)[:5000].encode()).hexdigest()
        if content_hash in self.scanned_content_hashes:
            return None
        self.scanned_content_hashes.add(content_hash)
        
        score = self._score_signal(text, url)
        contacts = self._extract_contact_hints(text, html)

        if score["total_score"] == 0:
            return None

        domain = urlparse(url).netloc
        lead = {
            "url": url,
            "domain": domain,
            "discovered_at": datetime.now().isoformat(),
            "scan_cycle_id": int(now),
            "content_hash": content_hash,
            "signals": score["signals"],
            "total_score": score["total_score"],
            "matched_terms": score["matched_terms"],
            "contacts": contacts,
            "status": "new",
            "pitch_suggestion": "",
        }
        self.leads.append(lead)
        self._save_leads()
        logger.info(f"New lead: {domain} | score={score['total_score']} | signals={score['signals']}")
        return lead

    async def scan_seed_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        tasks = [self.scan_url(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def scan_social_source(self, source_type: str, query: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        if source_type == "reddit":
            return await self._scan_reddit(query, limit)
        elif source_type == "hackernews":
            return await self._scan_hackernews(query, limit)
        elif source_type == "indiehackers":
            return await self._scan_indiehackers(query, limit)
        else:
            logger.warning(f"Unknown social source: {source_type}")
            return []

    async def _scan_reddit(self, query: str, limit: int) -> List[Dict[str, Any]]:
        leads = []
        subreddits = [
            "r/automation", "r/smallbusiness", "r/Entrepreneur",
            "r/webdev", "r/Productivity", "r/startups",
        ]
        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/{sub}/new.json?limit={limit}"
                now = time_module.time()
                if now - self.scan_cycles_by_url.get(url, 0) < 86400:
                    continue
                self.scan_cycles_by_url[url] = now
                await self.browser.navigate(url, wait_until="domcontentloaded", timeout=15000)
                text = await self.browser.get_text()
                score = self._score_signal(text, url)
                if score["total_score"] >= 2:
                    lead = {
                        "url": url,
                        "domain": "reddit.com",
                        "discovered_at": datetime.now().isoformat(),
                        "signals": score["signals"],
                        "total_score": score["total_score"],
                        "matched_terms": score["matched_terms"],
                        "contacts": {"emails": [], "phones": [], "social": ["reddit"]},
                        "status": "new",
                        "pitch_suggestion": "",
                        "source": f"reddit/{sub}",
                    }
                    leads.append(lead)
                    self.leads.append(lead)
            except Exception as e:
                logger.debug(f"Reddit scan failed for {sub}: {e}")
                continue
        self._save_leads()
        return leads

    async def _scan_hackernews(self, query: str, limit: int) -> List[Dict[str, Any]]:
        leads = []
        try:
            search_q = query or "automation"
            url = f"https://hn.algolia.com/api/v1/search?query={search_q}&tags=story&hitsPerPage={limit}"
            now = time_module.time()
            if now - self.scan_cycles_by_url.get(url, 0) < 86400:
                return leads
            self.scan_cycles_by_url[url] = now
            await self.browser.navigate(url, wait_until="domcontentloaded", timeout=15000)
            text = await self.browser.get_text()
            score = self._score_signal(text, url)
            if score["total_score"] >= 2:
                lead = {
                    "url": url,
                    "domain": "news.ycombinator.com",
                    "discovered_at": datetime.now().isoformat(),
                    "signals": score["signals"],
                    "total_score": score["total_score"],
                    "matched_terms": score["matched_terms"],
                    "contacts": {"emails": [], "phones": [], "social": ["hackernews"]},
                    "status": "new",
                    "pitch_suggestion": "",
                    "source": "hackernews",
                }
                leads.append(lead)
                self.leads.append(lead)
        except Exception as e:
            logger.debug(f"HackerNews scan failed: {e}")
        self._save_leads()
        return leads

    async def _scan_indiehackers(self, query: str, limit: int) -> List[Dict[str, Any]]:
        leads = []
        try:
            search_q = query or "automation"
            url = f"https://www.indiehackers.com/search?q={search_q}&type=posts"
            now = time_module.time()
            if now - self.scan_cycles_by_url.get(url, 0) < 86400:
                return leads
            self.scan_cycles_by_url[url] = now
            await self.browser.navigate(url, wait_until="domcontentloaded", timeout=15000)
            text = await self.browser.get_text()
            score = self._score_signal(text, url)
            if score["total_score"] >= 2:
                lead = {
                    "url": url,
                    "domain": "indiehackers.com",
                    "discovered_at": datetime.now().isoformat(),
                    "signals": score["signals"],
                    "total_score": score["total_score"],
                    "matched_terms": score["matched_terms"],
                    "contacts": {"emails": [], "phones": [], "social": ["indiehackers"]},
                    "status": "new",
                    "pitch_suggestion": "",
                    "source": "indiehackers",
                }
                leads.append(lead)
                self.leads.append(lead)
        except Exception as e:
            logger.debug(f"IndieHackers scan failed: {e}")
        self._save_leads()
        return leads

    async def search_leads(self, query: str, engines: str = "google,duckduckgo", limit: int = 20) -> List[Dict[str, Any]]:
        """Search for leads using SearXNG and create leads from results."""
        now = time_module.time()
        
        search_url = settings.SEARXNG_URL.rstrip("/") + "/search"
        params = {
            "q": query,
            "format": "json",
            "engines": engines,
            "language": "en-US",
        }
        
        leads = []
        try:
            response = requests.get(search_url, params=params, timeout=30)
            if response.status_code != 200:
                logger.warning(f"SearXNG search failed: {response.status_code}")
                return leads
            
            results = response.json()
            for result in results.get("results", [])[:limit]:
                url = result.get("url", "")
                title = result.get("title", "")
                content = result.get("content", "")
                
                if not url:
                    continue
                
                # Check deduplication
                last_scan = self.scan_cycles_by_url.get(url, 0)
                if now - last_scan < 86400:
                    continue
                
                combined_text = title + " " + content
                score = self._score_signal(combined_text, url)
                
                if score["total_score"] >= 2:
                    content_hash = hashlib.md5(combined_text.encode()).hexdigest()
                    lead = {
                        "url": url,
                        "domain": urlparse(url).netloc,
                        "discovered_at": datetime.now().isoformat(),
                        "scan_cycle_id": int(now),
                        "content_hash": content_hash,
                        "signals": score["signals"],
                        "total_score": score["total_score"],
                        "matched_terms": score["matched_terms"],
                        "contacts": self._extract_contact_hints(combined_text, ""),
                        "status": "new",
                        "source": "searxng_search",
                    }
                    self.leads.append(lead)
                    self.scan_cycles_by_url[url] = now
                    leads.append(lead)
            
            if leads:
                self._save_leads()
                logger.info(f"SearXNG search '{query}': {len(leads)} leads found")
                
        except Exception as e:
            logger.error(f"SearXNG search error: {e}")
        
        return leads

    def get_new_leads(self, min_score: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
        return [lead for lead in self.leads if lead.get("status") == "new" and lead.get("total_score", 0) >= min_score][-limit:]

    def mark_contacted(self, lead_url: str):
        for lead in self.leads:
            if lead.get("url") == lead_url:
                lead["status"] = "contacted"
        self._save_leads()
