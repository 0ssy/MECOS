"""
MECOS Outreach - Follow-up Scheduler
Queues follow-ups based on sequence timing.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import settings


class FollowupScheduler:
    """Queue and manage follow-up emails based on sequences."""

    def __init__(self, queue_path: Optional[Path] = None):
        self.queue_path = queue_path or settings.DATA_DIR / "outreach" / "followup_queue.jsonl"
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def queue_followup(self, lead: Dict[str, Any], touch_num: int, scheduled_for: datetime) -> Dict[str, Any]:
        """Queue a follow-up for a lead."""
        entry = {
            "lead_url": lead.get("url", ""),
            "lead_domain": lead.get("domain", ""),
            "touch_num": touch_num,
            "scheduled_for": scheduled_for.isoformat(),
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "sent": False,
        }
        self._save_entry(entry)
        logger.info(f"Queued follow-up #{touch_num} for {lead.get('domain', 'unknown')}")
        return entry

    def _save_entry(self, entry: Dict[str, Any]) -> None:
        """Save entry to queue."""
        with open(self.queue_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def get_due_followups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get follow-ups scheduled for now or past."""
        now = datetime.now()
        due = []
        entries = []

        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if entry.get("sent"):
                        entries.append(entry)
                        continue
                    scheduled = datetime.fromisoformat(entry.get("scheduled_for", ""))
                    if scheduled <= now:
                        due.append(entry)
                    entries.append(entry)
        except Exception as e:
            logger.debug(f"Queue read error: {e}")

        # Remove due items from entries for rewrite
        remaining = [e for e in entries if e not in due]
        if len(remaining) != len(entries):
            self._rewrite_queue(remaining)

        return due[:limit]

    def _rewrite_queue(self, entries: List[Dict[str, Any]]) -> None:
        """Rewrite queue without processed entries."""
        with open(self.queue_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, default=str) + "\n")

    def mark_sent(self, lead_url: str, touch_num: int) -> bool:
        """Mark follow-up as sent."""
        entries = []
        updated = False
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if (entry.get("lead_url") == lead_url and 
                        entry.get("touch_num") == touch_num and 
                        not entry.get("sent")):
                        entry["sent"] = True
                        entry["sent_at"] = datetime.now().isoformat()
                        updated = True
                    entries.append(entry)
        except Exception:
            return False

        self._rewrite_queue(entries)
        return updated

    def get_queue_size(self) -> int:
        """Get total queued follow-ups count."""
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def get_pending_count(self) -> int:
        """Get count of unsent follow-ups."""
        try:
            with open(self.queue_path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip() and not json.loads(line).get("sent"))
        except Exception:
            return 0