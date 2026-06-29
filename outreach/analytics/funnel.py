"""
MECOS Outreach - Conversion Funnel Analytics
Tracks: leads_discovered → emails_sent → replies → meetings → deals_won
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import settings


class FunnelAnalytics:
    """Tracks and reports on conversion funnel metrics."""

    def __init__(self, funnel_path: Optional[Path] = None):
        self.funnel_path = funnel_path or settings.DATA_DIR / "outreach" / "analytics" / "funnel.jsonl"
        self.funnel_path.parent.mkdir(parents=True, exist_ok=True)
        self.leads_path = settings.DATA_DIR / "outreach" / "leads.json"
        self.sent_path = settings.DATA_DIR / "outreach" / "sent"
        self.replies_path = settings.DATA_DIR / "outreach" / "replies.json"
        self.deals_path = settings.DATA_DIR / "outreach" / "deals.jsonl"

    def record_funnel_event(self, event_type: str, lead_url: str, value: float = 0) -> None:
        """Record a funnel event (lead_created, email_sent, reply, meeting, deal)."""
        event = {
            "event_type": event_type,
            "lead_url": lead_url,
            "value": value,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            with open(self.funnel_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to record funnel event: {e}")

    def get_funnel_metrics(self) -> Dict[str, Any]:
        """Calculate conversion funnel metrics."""
        events = self._load_events()

        metrics = {
            "leads_discovered": 0,
            "emails_sent": 0,
            "replies_received": 0,
            "meetings_booked": 0,
            "deals_won": 0,
            "revenue": 0.0,
        }

        for event in events:
            event_type = event.get("event_type")
            if event_type == "lead_discovered":
                metrics["leads_discovered"] += 1
            elif event_type == "email_sent":
                metrics["emails_sent"] += 1
            elif event_type == "reply":
                metrics["replies_received"] += 1
            elif event_type == "meeting_booked":
                metrics["meetings_booked"] += 1
            elif event_type == "deal_won":
                metrics["deals_won"] += 1
                metrics["revenue"] += event.get("value", 0)

        rates = {}
        if metrics["leads_discovered"] > 0:
            rates["reply_rate"] = round(metrics["replies_received"] / metrics["leads_discovered"], 3)
            rates["meeting_rate"] = round(metrics["meetings_booked"] / metrics["leads_discovered"], 3)
            rates["close_rate"] = round(metrics["deals_won"] / metrics["leads_discovered"], 3)

        return {
            "timestamp": datetime.now().isoformat(),
            "counts": metrics,
            "rates": rates,
        }

    def _load_events(self) -> List[Dict[str, Any]]:
        events = []
        try:
            with open(self.funnel_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception:
            pass
        return events

    def get_source_effectiveness(self) -> Dict[str, Dict[str, Any]]:
        """Calculate conversion rates by lead source."""
        events = self._load_events()
        sources = {}

        for event in events:
            source = event.get("source", "unknown")
            if source not in sources:
                sources[source] = {"leads": 0, "replies": 0, "deals": 0, "revenue": 0.0}

            if event.get("event_type") == "lead_discovered":
                sources[source]["leads"] += 1
            elif event.get("event_type") == "reply":
                sources[source]["replies"] += 1
            elif event.get("event_type") == "deal_won":
                sources[source]["deals"] += 1
                sources[source]["revenue"] += event.get("value", 0)

        for source, data in sources.items():
            if data["leads"] > 0:
                data["reply_rate"] = round(data["replies"] / data["leads"], 3)
                data["conversion_rate"] = round(data["deals"] / data["leads"], 3)

        return sources

    def get_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly funnel report."""
        now = datetime.now()
        cutoff = datetime(now.year, now.month, now.day).isoformat()

        events = self._load_events()
        weekly = [e for e in events if e.get("timestamp", "") >= cutoff]

        return self.get_funnel_metrics()