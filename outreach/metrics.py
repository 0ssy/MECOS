"""
MECOS Outreach - Metrics Tracker
Daily and weekly metrics for outreach performance.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


class OutreachMetrics:
    def __init__(self, metrics_path: Optional[Path] = None, replies_path: Optional[Path] = None):
        self.metrics_path = metrics_path or Path("data/outreach/daily_metrics.jsonl")
        self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.replies_path = replies_path or Path("data/outreach/replies.json")
        self.ledger_path = Path("data/outreach/revenue_ledger.json")
        self.archive_path = Path("data/outreach/archive_stale")

    def record_daily(self, metrics: Dict[str, Any]) -> None:
        record = {
            "date": datetime.now().date().isoformat(),
            "timestamp": datetime.now().isoformat(),
            **metrics,
        }
        try:
            with open(self.metrics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.error("Metrics: failed to record daily metrics: {}", exc)

    def get_daily(self, date: Optional[str] = None) -> Dict[str, Any]:
        target = date or datetime.now().date().isoformat()
        if not self.metrics_path.exists():
            return {"date": target, "found": False}

        try:
            with open(self.metrics_path, "r", encoding="utf-8") as f:
                for line in reversed(list(f)):
                    entry = json.loads(line)
                    if entry.get("date") == target:
                        return {"date": target, "found": True, **entry}
        except Exception as exc:
            logger.debug("Metrics: failed to read daily: {}", exc)
        return {"date": target, "found": False}

    def _count_replies(self, days: int = 7) -> int:
        if not self.replies_path.exists():
            return 0
        try:
            with open(self.replies_path, "r", encoding="utf-8") as f:
                replies = json.loads(f.read())
            cutoff = datetime.now() - timedelta(days=days)
            return sum(1 for r in replies if datetime.fromisoformat(r.get("_fetched_at", r.get("date", "1970-01-01"))) >= cutoff)
        except Exception:
            return 0

    def _count_demo_deliveries(self, days: int = 7) -> int:
        if not self.replies_path.exists():
            return 0
        try:
            with open(self.replies_path, "r", encoding="utf-8") as f:
                replies = json.loads(f.read())
            cutoff = datetime.now() - timedelta(days=days)
            return sum(1 for r in replies if r.get("demo_triggered") and datetime.fromisoformat(r.get("_fetched_at", r.get("date", "1970-01-01"))) >= cutoff)
        except Exception:
            return 0

    def _count_revenue(self, days: int = 7) -> float:
        if not self.ledger_path.exists():
            return 0.0
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                ledger = json.loads(f.read())
            entries = ledger.get("entries", [])
            cutoff = datetime.now() - timedelta(days=days)
            return sum(
                e.get("amount", 0)
                for e in entries
                if e.get("source") == "client_payment" and datetime.fromisoformat(e.get("allocated_at", "1970-01-01")) >= cutoff
            )
        except Exception:
            return 0.0

    def _count_archived_rejects(self, days: int = 7) -> int:
        if not self.archive_path.exists():
            return 0
        try:
            cutoff = datetime.now() - timedelta(days=days)
            count = 0
            for f in self.archive_path.glob("*.json"):
                if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff:
                    count += 1
            return count
        except Exception:
            return 0

    def get_weekly_summary(self) -> Dict[str, Any]:
        now = datetime.now()
        week_ago = now - timedelta(days=7)

        summary = {
            "start_date": week_ago.date().isoformat(),
            "end_date": now.date().isoformat(),
            "conversations_started": self._count_replies(7),
            "demos_delivered": self._count_demo_deliveries(7),
            "deals_closed": 0,
            "total_revenue": self._count_revenue(7),
            "blocker_rate": 0.0,
            "avg_deal_size": 0.0,
        }

        if self.metrics_path.exists():
            try:
                total_sent = 0
                total_failed = 0
                with open(self.metrics_path, "r", encoding="utf-8") as f:
                    for line in f:
                        entry = json.loads(line)
                        entry_date = entry.get("date", "")
                        try:
                            if datetime.fromisoformat(entry_date) >= week_ago:
                                total_sent += entry.get("auto_sent", 0)
                                total_failed += entry.get("rejected", 0)
                        except Exception:
                            continue
                if total_sent > 0:
                    summary["blocker_rate"] = total_failed / total_sent
            except Exception as exc:
                logger.debug("Metrics: failed weekly rollup: {}", exc)

        if summary["deals_closed"] > 0:
            summary["avg_deal_size"] = summary["total_revenue"] / summary["deals_closed"]

        return summary

    def get_health(self) -> Dict[str, Any]:
        daily = self.get_daily()
        weekly = self.get_weekly_summary()
        return {
            "daily": daily,
            "weekly": weekly["conversations_started"],
            "weekly_demos": weekly["demos_delivered"],
            "weekly_revenue": weekly["total_revenue"],
            "blocker_rate": weekly["blocker_rate"],
            "avg_deal_size": weekly["avg_deal_size"],
        }