"""
MECOS Outreach - Scanner
Autonomous web scanner that detects lead signals across four categories:
A) Inefficiency markers, B) Pain point indicators, C) Revenue fit, D) Organic intent.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time as time_module
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

try:
    from outreach.scrapling_adapter import get_scrapling_adapter
except ImportError:
    get_scrapling_adapter = None

from browser_automation import BrowserAutomation
from config import settings
from memory_system import MemorySystem
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
    "hiring", "now hiring", "we're growing", "expansion", "opening new",
    "small business", "local business",
    "founder", "startup", "freelancer", "contract",
]
LOCAL_BUSINESS_SIGNALS = [
    "family owned", "family-owned", "since 19", "since 20",
    "serving", "proudly serving", "locally owned", "locally-owned",
    "neighborhood", "community", "trusted", "established",
    "appointment", "walk-ins welcome", "call for pricing",
    "our team", "our staff", "master", "licensed",
    "certified", "insured", "years of experience",
    "address", "phone", "directions", "hours",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "closed",
]
ENTERPRISE_BLOCKS = [
    "fortune 500", "fortune 1000", "inc 5000", "enterprise",
    "/enterprise", "/solutions", "/platform", "/products",
    "enterprise-grade", "enterprise class", "global scale",
    "public company", "nasdaq", "nyse", "stock symbol",
]
ENTERPRISE_DOMAIN_KEYWORDS = [
    "microsoft", "google", "apple", "ibm", "oracle", "sap",
    "salesforce", "adobe", "servicenow", "workday", "snowflake",
    "datadog", "crowdstrike", "zscaler", "twilio", "twitch",
    "marketscreener", "businessinsider", "bloomberg",
    "wikipedia", "docsie", "gravityflow", "timedoctor",
]


class OutreachScanner:
    AGGREGATOR_DOMAINS = {
        "hn.algolia.com",
        "news.ycombinator.com",
        "reddit.com",
        "indiehackers.com",
        "upwork.com",
        "linkedin.com",
        "gravityflow.io",
        "docparsemagic.com",
        "timedoctor.com",
        "techweez.com",
        "docsie.io",
        "freelancer.com",
        "pinterest.com",
        "bing.com",
        "google.com",
        "youtube.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "craigslist.org",
        "ebay.com",
        "amazon.com",
        "github.com",
    }
    BLOCKED_TLDS = {".reddit.com", ".hackernews.com", ".indiehackers.com", ".upwork.com", ".linkedin.com"}
    BLOCKED_GEO_DOMAINS = {
        "babbel.com", "auto.ru", "myauto.ge", "drom.ru", "avito.ru",
        "russian", "russia", "india", "indian", "china", "chinese",
        "brazil", "brazilian", "argentina", "mexico", "mexican",
    }  # non-target regions (Europe, NA, Japan, Oceania focus)

    def __init__(self, memory: MemorySystem, browser: Optional[BrowserAutomation] = None,
                 web_perception: Optional[WebPerception] = None):
        self.memory = memory
        self.browser = browser or BrowserAutomation()
        self.web_perception = web_perception or WebPerception(memory)
        self.leads: List[Dict[str, Any]] = []
        self.scanned_urls: set = set()
        self.scanned_content_hashes: set = set()
        self.scan_cycles_by_url: Dict[str, float] = {}
        self.save_path = settings.DATA_DIR / "outreach" / "leads.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_leads()

    @staticmethod
    def _is_business_url(url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        parsed = urlparse(url)
        if domain in OutreachScanner.AGGREGATOR_DOMAINS:
            return False
        for blocked in OutreachScanner.BLOCKED_GEO_DOMAINS:
            if blocked in domain:
                return False
        for keyword in ENTERPRISE_DOMAIN_KEYWORDS:
            if keyword in domain:
                return False
        if domain in ("localhost", "127.0.0.1"):
            return False
        if domain == "example.com" or ".example.com" in domain:
            return False
        if parsed.path.startswith("/search") or parsed.query.startswith("q=") or "/search" in parsed.query:
            return False
        for blocked in OutreachScanner.BLOCKED_TLDS:
            if domain.endswith(blocked):
                return False
        return True

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

    def _calculate_local_business_score(self, text: str, url: str) -> int:
        text_lower = text.lower()
        parsed = urlparse(url)
        path = parsed.path.lower()
        score = 0

        for signal in LOCAL_BUSINESS_SIGNALS:
            if signal in text_lower:
                score += 1

        if any(ext in path for ext in ["/contact", "/about", "/team", "/about-us"]):
            score += 1
        if "address" in text_lower or "directions" in text_lower:
            score += 1
        if re.search(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}", text):
            score += 1

        return min(score, 10)

    def _calculate_enterprise_penalty(self, text: str, url: str) -> int:
        text_lower = text.lower()
        parsed = urlparse(url)
        path = parsed.path.lower()
        penalty = 0

        for block in ENTERPRISE_BLOCKS:
            if block.startswith("/"):
                if block in path:
                    penalty += 2
            elif block in text_lower:
                penalty += 1

        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        for keyword in ENTERPRISE_DOMAIN_KEYWORDS:
            if keyword in domain:
                penalty += 3

        return min(penalty, 10)

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

    def _extract_business_urls(self, text: str) -> List[str]:
        """Extract business URLs from text, excluding aggregator domains."""
        url_re = re.compile(r'https?://[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/[^\s\'"<>]+')
        urls = url_re.findall(text)
        # Filter out aggregator domains
        return [u for u in urls if self._is_business_url(u)][:5]

    def _fetch_page_text(self, url: str, timeout: int = 15) -> Dict[str, Any]:
        if get_scrapling_adapter:
            try:
                result = get_scrapling_adapter().fetch(url, timeout=timeout)
                if result.get("ok"):
                    txt = result.get("text", "")
                    return {"ok": True, "text": txt, "html": result.get("html", "")}
            except Exception as e:
                logger.debug(f"Scrapling fetch failed for {url}: {e}")

        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            if response.status_code != 200:
                err = f"HTTP {response.status_code}"
                return {"ok": False, "text": "", "html": "", "error": err}
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            return {"ok": True, "text": clean_text, "html": html}
        except Exception as e:
            return {"ok": False, "text": "", "html": "", "error": str(e)}

    async def scan_url(self, url: str) -> Optional[Dict[str, Any]]:
        if not self._is_business_url(url):
            return None
        # Check 24h deduplication window
        now = time_module.time()
        last_scan = self.scan_cycles_by_url.get(url, 0)
        if now - last_scan < 86400:  # 24 hours in seconds
            return None
        self.scan_cycles_by_url[url] = now

        result = await asyncio.to_thread(self._fetch_page_text, url)
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

        if score["total_score"] < 3:
            return None

        domain = urlparse(url).netloc
        local_score = self._calculate_local_business_score(text, url)
        enterprise_penalty = self._calculate_enterprise_penalty(text, url)
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
            "source": "web_scan",
            "local_business_score": local_score,
            "enterprise_penalty": enterprise_penalty,
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
                if not self._is_business_url(url):
                    continue
                self.scan_cycles_by_url[url] = now
                await self.browser.navigate(url, wait_until="domcontentloaded", timeout=15000)
                text = await self.browser.get_text()
                score = self._score_signal(text, url)
                if score["total_score"] >= 3:
                    # Extract business URLs from post content instead of using reddit.com as domain
                    extracted_urls = self._extract_business_urls(text)
                    if not extracted_urls:
                        continue  # Skip if no business URLs found in post
                    for extracted_url in extracted_urls[:2]:  # Limit 2 per post
                        if not self._is_business_url(extracted_url):
                            continue
                        domain = urlparse(extracted_url).netloc.lower()
                        local_score = self._calculate_local_business_score(text, extracted_url)
                        enterprise_penalty = self._calculate_enterprise_penalty(text, extracted_url)
                        lead = {
                            "url": extracted_url,
                            "domain": domain,
                            "discovered_at": datetime.now().isoformat(),
                            "signals": score["signals"],
                            "total_score": score["total_score"],
                            "matched_terms": score["matched_terms"],
                            "contacts": {"emails": [], "phones": [], "social": ["reddit"]},
                            "status": "new",
                            "pitch_suggestion": "",
                            "source": f"reddit/{sub}",
                            "local_business_score": local_score,
                            "enterprise_penalty": enterprise_penalty,
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
            if not self._is_business_url(url):
                return leads
            self.scan_cycles_by_url[url] = now
            await self.browser.navigate(url, wait_until="domcontentloaded", timeout=15000)
            text = await self.browser.get_text()
            score = self._score_signal(text, url)
            if score["total_score"] >= 3:
                # Extract business URLs from API response (hits contain story URLs)
                extracted_urls = self._extract_business_urls(text)
                for extracted_url in extracted_urls[:2]:
                    if not self._is_business_url(extracted_url):
                        continue
                    domain = urlparse(extracted_url).netloc.lower()
                    local_score = self._calculate_local_business_score(text, extracted_url)
                    enterprise_penalty = self._calculate_enterprise_penalty(text, extracted_url)
                    lead = {
                        "url": extracted_url,
                        "domain": domain,
                        "discovered_at": datetime.now().isoformat(),
                        "signals": score["signals"],
                        "total_score": score["total_score"],
                        "matched_terms": score["matched_terms"],
                        "contacts": {"emails": [], "phones": [], "social": ["hackernews"]},
                        "status": "new",
                        "pitch_suggestion": "",
                        "source": "hackernews",
                        "local_business_score": local_score,
                        "enterprise_penalty": enterprise_penalty,
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
            if not self._is_business_url(url):
                return leads
            self.scan_cycles_by_url[url] = now
            await self.browser.navigate(url, wait_until="domcontentloaded", timeout=15000)
            text = await self.browser.get_text()
            score = self._score_signal(text, url)
            if score["total_score"] >= 3:
                # Extract business URLs from search results
                extracted_urls = self._extract_business_urls(text)
                for extracted_url in extracted_urls[:2]:
                    if not self._is_business_url(extracted_url):
                        continue
                    domain = urlparse(extracted_url).netloc.lower()
                    local_score = self._calculate_local_business_score(text, extracted_url)
                    enterprise_penalty = self._calculate_enterprise_penalty(text, extracted_url)
                    lead = {
                        "url": extracted_url,
                        "domain": domain,
                        "discovered_at": datetime.now().isoformat(),
                        "signals": score["signals"],
                        "total_score": score["total_score"],
                        "matched_terms": score["matched_terms"],
                        "contacts": {"emails": [], "phones": [], "social": ["indiehackers"]},
                        "status": "new",
                        "pitch_suggestion": "",
                        "source": "indiehackers",
                        "local_business_score": local_score,
                        "enterprise_penalty": enterprise_penalty,
                    }
                    leads.append(lead)
                    self.leads.append(lead)
        except Exception as e:
            logger.debug(f"IndieHackers scan failed: {e}")
        self._save_leads()
        return leads

    async def scan_business_directories(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Scan business directories for leads with automation pain signals."""
        queries = [
            "HVAC scheduling spreadsheet hell small business",
            "auto repair shop manual invoicing small business",
            "dental office patient intake paper forms small business",
            "plumbing dispatch spreadsheet small business",
            "local business appointment booking pain",
            "family owned business manual processes",
            "small business workflow bottleneck",
            "local service business automation needed",
        ]
        all_leads = []
        for query in queries[:4]:
            try:
                found = await self.search_leads(query, limit=limit)
                all_leads.extend(found)
            except Exception as e:
                logger.debug(f"Business directory scan skip '{query}': {e}")
        return all_leads

    async def search_leads(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for leads using SearXNG. Requires SearXNG running at localhost:8888."""
        now = time_module.time()
        
        search_url = settings.SEARXNG_URL.rstrip("/") + "/search"
        params = {
            "q": query,
            "format": "json",
            "language": "en-US",
            "engines": "bing",
        }
        
        leads = []
        try:
            response = requests.get(search_url, params=params, timeout=30)
            if response.status_code != 200:
                logger.error(f"SearXNG search failed: {response.status_code} - is Docker running?")
                return leads
            
            results = response.json()
            candidate_urls = []
            for result in results.get("results", [])[:limit]:
                url = result.get("url", "")
                if not url:
                    continue
                if not self._is_business_url(url):
                    continue
                last_scan = self.scan_cycles_by_url.get(url, 0)
                if now - last_scan < 86400:
                    continue
                candidate_urls.append(url)
            
            for url in candidate_urls:
                try:
                    lead = await self.scan_url(url)
                    if lead:
                        leads.append(lead)
                        if len(leads) >= limit:
                            break
                except Exception as e:
                    logger.debug(f"scan_url skip for {url}: {e}")
                    continue
            
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
