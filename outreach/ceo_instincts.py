"""
MECOS CEO Instincts
ECC-inspired decision patterns for the CEO agent.
Provides rule-based instincts that guide outreach priority, lead scoring,
and system stability decisions without requiring an LLM call every cycle.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class CeoInstincts:
    """
    Rule-based instinct engine inspired by ECC's skills/instincts patterns.
    Stores learnable instincts as JSON and applies them at decision points.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("data/outreach/ceo_instincts.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.instincts: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                self.instincts = json.loads(self.storage_path.read_text())
            except Exception:
                self.instincts = []

    def _save(self):
        try:
            self.storage_path.write_text(json.dumps(self.instincts[-200:], default=str, indent=2))
        except Exception as e:
            pass  # instincts are non-critical

    def score_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Apply instinct-based score adjustments to a lead."""
        lead = dict(lead)
        base = lead.get("total_score", 0)
        bonus = 0.0
        flags: List[str] = []

        for instinct in self.instincts:
            if not instinct.get("enabled", True):
                continue
            if self._matches(lead, instinct.get("conditions", [])):
                bonus += instinct.get("score_bonus", 0)
                flags.append(instinct.get("name", "unnamed"))

        lead["total_score"] = round(base + bonus, 2)
        lead["instinct_flags"] = flags
        return lead

    def recommend_action(self, state: Dict[str, Any]) -> str:
        """Recommend a CEO action based on current system state."""
        pending = state.get("pending_drafts", 0)
        leads_queued = state.get("leads_queued", 0)
        revenue = state.get("revenue", {}).get("total_revenue", 0)
        health = state.get("health", {}).get("status", "unknown")

        if health == "unhealthy":
            return "PAUSE_OUTREACH"

        if pending > 50 and leads_queued > 100:
            return "DRAIN_OUTBOX"

        if revenue < 100 and leads_queued < 20:
            return "BOOST_SCANNING"

        if revenue > 0 and pending < 10:
            return "ACCELERATE_OUTREACH"

        return "MAINTAIN"

    def learn_from_outcome(self, lead: Dict[str, Any], outcome: str):
        """Record an instinct trigger/outcome for future tuning."""
        flags = lead.get("instinct_flags", [])
        if not flags:
            return

        for flag in flags:
            instinct = next((i for i in self.instincts if i.get("name") == flag), None)
            if not instinct:
                continue
            stats = instinct.setdefault("stats", {"hits": 0, "positive": 0})
            stats["hits"] += 1
            if outcome in ("replied", "converted", "meeting_scheduled"):
                stats["positive"] += 1

        self._save()

    def register_instinct(self, name: str, conditions: List[Dict], score_bonus: float, enabled: bool = True):
        """Register a new instinct pattern."""
        existing = next((i for i in self.instincts if i.get("name") == name), None)
        if existing:
            existing["conditions"] = conditions
            existing["score_bonus"] = score_bonus
            existing["enabled"] = enabled
        else:
            self.instincts.append({
                "name": name,
                "conditions": conditions,
                "score_bonus": score_bonus,
                "enabled": enabled,
                "created_at": datetime.now().isoformat(),
                "stats": {"hits": 0, "positive": 0},
            })
        self._save()

    def _matches(self, lead: Dict[str, Any], conditions: List[Dict]) -> bool:
        for cond in conditions:
            field = cond.get("field")
            op = cond.get("op", "eq")
            value = cond.get("value")
            lead_val = lead.get(field)

            if op == "gte" and isinstance(lead_val, (int, float)):
                if lead_val < value:
                    return False
            elif op == "lte" and isinstance(lead_val, (int, float)):
                if lead_val > value:
                    return False
            elif op == "contains":
                text = str(lead_val).lower()
                if not any(v.lower() in text for v in (value if isinstance(value, list) else [value])):
                    return False
            elif op == "eq":
                if lead_val != value:
                    return False
            elif op == "in":
                if lead_val not in (value if isinstance(value, list) else [value]):
                    return False
            else:
                if lead_val != value:
                    return False
        return True

    def bootstrap_defaults(self):
        """Seed with proven default instincts if none exist."""
        if self.instincts:
            return

        defaults = [
            {
                "name": "high_pain_boost",
                "conditions": [
                    {"field": "total_score", "op": "gte", "value": 3},
                    {"field": "status", "op": "eq", "value": "new"},
                ],
                "score_bonus": 1.5,
                "enabled": True,
            },
            {
                "name": "recent_funding_signal",
                "conditions": [
                    {"field": "matched_terms", "op": "contains", "value": ["funding", "series", "raised"]},
                ],
                "score_bonus": 2.0,
                "enabled": True,
            },
            {
                "name": "organic_intent_boost",
                "conditions": [
                    {"field": "signals", "op": "contains", "value": {"organic_intent": 1}},
                ],
                "score_bonus": 1.2,
                "enabled": True,
            },
            {
                "name": "cold_lead_penalty",
                "conditions": [
                    {"field": "signals", "op": "contains", "value": {"organic_intent": 0}},
                    {"field": "signals", "op": "contains", "value": {"pain_points": 0}},
                ],
                "score_bonus": -2.0,
                "enabled": True,
            },
        ]

        for d in defaults:
            d.setdefault("created_at", datetime.now().isoformat())
            d.setdefault("stats", {"hits": 0, "positive": 0})
            self.instincts.append(d)

        self._save()
        logger.info(f"Bootstrapped {len(defaults)} CEO instincts")
