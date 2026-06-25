"""
MECOS Outreach - Research Orchestrator
Coordinates social/web research for high-quality leads before drafting.
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from loguru import logger

from .research_channels.reddit import research_reddit
from .research_channels.twitter import research_twitter
from .research_channels.web import research_web
from .research_channels.youtube import research_youtube
from .scanner import (
    INEFFICIENCY_MARKERS,
    ORGANIC_INTENT_PHRASES,
    PAIN_KEYWORDS,
    REVENUE_FIT_SIGNALS,
)


class ResearchOrchestrator:
    """Orchestrates multi-platform research for leads.
    
    Applies high-score gate and runs platforms in parallel.
    Stores results in lead["research_signals"] and brief["research_summary"].
    """

    RESEARCH_GATE_SCORE = 5
    RESEARCH_GATE_MULTIPLIER = 1.2
    PLATFORM_TIMEOUT = 10

    def __init__(self, bridge: Optional[Any] = None):
        self.bridge = bridge

    def should_research(self, lead: Dict[str, Any]) -> bool:
        """Check if lead passes the research threshold gate."""
        total_score = lead.get("total_score", 0)
        intel_multiplier = lead.get("intel_multiplier", 1.0)
        return (total_score >= self.RESEARCH_GATE_SCORE or
                intel_multiplier >= self.RESEARCH_GATE_MULTIPLIER)

    def _build_queries(self, lead: Dict[str, Any]) -> Dict[str, str]:
        """Build research queries from lead data."""
        domain = lead.get("domain", "")
        matched = lead.get("matched_terms", [])
        pain_points = lead.get("pain_points", [])

        pain_str = " ".join(pain_points[:2]) if pain_points else ""
        keyword_str = " ".join(matched[:3]) if matched else ""

        base_query = f"{domain} {pain_str} {keyword_str}".strip()

        return {
            "twitter": base_query or f"{domain} automation",
            "youtube": f"{base_query} workflow" if base_query else f"{domain} automation tutorial",
            "reddit": base_query or f"{domain} problem",
            "web": f"{base_query} solution" if base_query else f"{domain} automation tool",
        }

    async def research_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Run research for a lead and return combined signals."""
        signals = {
            "twitter": {"ok": False, "error": "not_run"},
            "youtube": {"ok": False, "error": "not_run"},
            "reddit": {"ok": False, "error": "not_run"},
            "web": {"ok": False, "error": "not_run"},
        }

        if not self.should_research(lead):
            signals["twitter"] = {"ok": False, "error": "below_threshold"}
            signals["youtube"] = {"ok": False, "error": "below_threshold"}
            signals["reddit"] = {"ok": False, "error": "below_threshold"}
            signals["web"] = {"ok": False, "error": "below_threshold"}
            lead["research_signals"] = signals
            return signals

        queries = self._build_queries(lead)

        async def safe_research(platform: str, query: str):
            try:
                if platform == "twitter":
                    return await research_twitter(
                        query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                    )
                elif platform == "youtube":
                    return await research_youtube(
                        query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                    )
                elif platform == "reddit":
                    return await research_reddit(
                        query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                    )
                elif platform == "web":
                    return await research_web(
                        query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                    )
            except Exception as e:
                logger.debug("Research failed for {}: {}", platform, e)
                return {"ok": False, "error": str(e)}

        results = await asyncio.gather(
            *[safe_research(p, q) for p, q in queries.items()],
            return_exceptions=True,
        )

        for i, platform in enumerate(queries.keys()):
            if isinstance(results[i], dict):
                signals[platform] = results[i]
            elif isinstance(results[i], Exception):
                signals[platform] = {"ok": False, "error": str(results[i])}

        lead["research_signals"] = signals
        return signals

    def build_summary(self, signals: Dict[str, Any]) -> str:
        """Build a condensed research summary from signals for email personalization."""
        parts = []

        if signals.get("twitter", {}).get("ok") and signals["twitter"].get("text"):
            text = signals["twitter"]["text"][:200]
            if len(signals["twitter"]["text"]) > 200:
                text += "..."
            parts.append(f"Recent discussion on Twitter mentions related challenges. {text}")

        if signals.get("youtube", {}).get("ok") and signals["youtube"].get("text"):
            text = signals["youtube"]["text"][:200]
            if len(signals["youtube"]["text"]) > 200:
                text += "..."
            parts.append(f"YouTube content shows interest in automation solutions. {text}")

        if signals.get("reddit", {}).get("ok") and signals["reddit"].get("text"):
            text = signals["reddit"]["text"][:200]
            if len(signals["reddit"]["text"]) > 200:
                text += "..."
            parts.append(f"Reddit discussions highlight similar pain points. {text}")

        return " ".join(parts[:2])

    def discover_lead_signals(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Run research across platforms for keywords and return lead candidates."""
        candidates: List[Dict[str, Any]] = []

        def _score_text(text: str, url: str) -> Dict[str, Any]:
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
                "signals": signals,
                "total_score": total,
                "matched_terms": matched[:10],
            }

        async def _discover() -> List[Dict[str, Any]]:
            for keyword in keywords:
                queries = {
                    "twitter": keyword,
                    "reddit": keyword,
                    "youtube": f"{keyword} workflow",
                    "web": f"{keyword} solution",
                }

                async def safe_research(platform: str, query: str):
                    try:
                        if platform == "twitter":
                            return await research_twitter(
                                query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                            )
                        elif platform == "youtube":
                            return await research_youtube(
                                query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                            )
                        elif platform == "reddit":
                            return await research_reddit(
                                query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                            )
                        elif platform == "web":
                            return await research_web(
                                query, max_results=3, timeout=self.PLATFORM_TIMEOUT
                            )
                    except Exception as e:
                        logger.debug("Discovery failed for {}: {}", platform, e)
                        return {"ok": False, "error": str(e)}

                results = await asyncio.gather(
                    *[safe_research(p, q) for p, q in queries.items()],
                    return_exceptions=True,
                )

                for i, platform in enumerate(queries.keys()):
                    result = results[i]
                    if isinstance(result, dict) and result.get("ok") and result.get("text"):
                        text = result["text"][:2000]
                        url = result.get("link", "")
                        domain = urlparse(url).netloc if url else ""

                        scored = _score_text(text, url)
                        if scored["total_score"] >= 2:
                            text_hash = hashlib.md5(text.encode()).hexdigest()
                            candidate = {
                                "url": url,
                                "domain": domain,
                                "text_excerpt": text[:500],
                                "source_platform": platform,
                                "total_score": scored["total_score"],
                                "matched_terms": scored["matched_terms"],
                                "signals": scored["signals"],
                                "content_hash": text_hash,
                            }
                            candidates.append(candidate)

            return candidates

        return asyncio.run(_discover())