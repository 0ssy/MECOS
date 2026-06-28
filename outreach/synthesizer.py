"""
MECOS Outreach - Synthesizer
LLM-backed lead profiler that turns raw signal data into actionable lead briefs.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from config import settings
from memory_system import MemorySystem


class LeadSynthesizer:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.save_path = settings.DATA_DIR / "outreach" / "synthesized_leads.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.briefs: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.save_path.exists():
            try:
                self.briefs = json.loads(self.save_path.read_text())
            except Exception:
                self.briefs = []

    def _save(self):
        try:
            self.save_path.write_text(json.dumps(self.briefs[-300:], default=str))
        except Exception as e:
            logger.error(f"Failed to save synthesized leads: {e}")

    async def synthesize(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        signals = lead.get("signals", {})
        matched = lead.get("matched_terms", [])
        url = lead.get("url", "")
        domain = lead.get("domain", "")
        contacts = lead.get("contacts", {})

        pain_points = self._categorize_pain(signals, matched)
        suggested_pitch = self._craft_pitch(pain_points, domain, contacts)
        persona = self._derive_persona(pain_points, domain)
        package = self._recommend_package(pain_points)

        brief = {
            "url": url,
            "domain": domain,
            "synthesized_at": datetime.now().isoformat(),
            "pain_points": pain_points,
            "persona": persona,
            "suggested_pitch": suggested_pitch,
            "recommended_package": package,
            "recommended_first_tool": self._recommend_first_tool(pain_points),
            "contacts": contacts,
            "original_signals": signals,
            "matched_terms": matched,
            "status": "ready_for_outreach",
        }

        self.briefs.append(brief)
        self._save()
        logger.info(f"Synthesized lead brief for {domain}: {package['name']}")
        return brief

    async def synthesize_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for lead in leads:
            try:
                brief = await self.synthesize(lead)
                results.append(brief)
            except Exception as e:
                logger.error(f"Failed to synthesize lead {lead.get('url')}: {e}")
        return results

    def _categorize_pain(self, signals: Dict[str, int], matched: List[str]) -> List[str]:
        pains = []
        if signals.get("pain_points", 0) > 0:
            pains.append("manual labor / operational overhead")
        if signals.get("inefficiency_markers", 0) > 0:
            pains.append("missing automation / outdated processes")
        if signals.get("organic_intent", 0) > 0:
            pains.append("actively seeking automation solutions")
        if signals.get("revenue_fit", 0) > 0:
            pains.append("growing team / scaling challenges")
        if not pains:
            pains.append("potential efficiency gains")
        return pains

    def _derive_persona(self, pain_points: List[str], domain: str) -> str:
        if "actively seeking" in str(pain_points):
            return "active_buyer"
        if "growing team" in str(pain_points):
            return "scaling_business"
        if "operational overhead" in str(pain_points):
            return "overwhelmed_operator"
        return "prospect"

    def _recommend_package(self, pain_points: List[str]) -> Dict[str, Any]:
        if "actively seeking" in str(pain_points):
            return {
                "name": "rapid_automation_audit",
                "price_range": "$500-$1,500 one-time",
                "description": "1-week audit + custom bot build",
                "delivery": "1 week",
            }
        if "growing team" in str(pain_points):
            return {
                "name": "workflow_retainer",
                "price_range": "$1,000-$2,000/mo",
                "description": "Ongoing automation maintenance + new workflows",
                "delivery": "ongoing",
            }
        if "operational overhead" in str(pain_points):
            return {
                "name": "single_bot_package",
                "price_range": "$500-$1,500 one-time",
                "description": "Focused automation for one high-impact process",
                "delivery": "2-3 days",
            }
        return {
            "name": "exploratory_package",
            "price_range": "$500 one-time",
            "description": "Small proof-of-concept automation",
            "delivery": "3-5 days",
        }

    def _craft_pitch(self, pain_points: List[str], domain: str, contacts: Dict[str, Any]) -> str:
        primary_pain = pain_points[0].replace("_", " ").title() if pain_points else "Efficiency"
        return (
            f"Automated solution for {domain} targeting {primary_pain}. "
            f"Build: 2-3 days. Price: fixed scope. No long-term contract required."
        )

    def _recommend_first_tool(self, pain_points: List[str]) -> str:
        if "actively seeking" in str(pain_points):
            return "full automation audit — we map your workflow first"
        if "growing team" in str(pain_points):
            return "workflow automation retainer — ongoing optimization"
        if "operational overhead" in str(pain_points):
            return "targeted bot for your highest-friction process"
        return "proof-of-concept automation for one repetitive task"

    def get_ready_for_outreach(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [b for b in self.briefs if b.get("status") == "ready_for_outreach"][-limit:]
