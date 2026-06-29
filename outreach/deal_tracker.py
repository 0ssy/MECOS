"""
MECOS Outreach - Deal Tracker
Logs sales outcomes with CSV export for GitLab Pages / reporting.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import settings


class DealTracker:
    """Track sales outcomes and export to CSV."""

    def __init__(self, deals_path: Optional[Path] = None):
        self.deals_path = deals_path or settings.DATA_DIR / "outreach" / "deals.jsonl"
        self.deals_path.parent.mkdir(parents=True, exist_ok=True)

    def record_deal(self, lead_url: str, amount: float, lead_source: str = "",
                     notes: str = "", status: str = "closed") -> Dict[str, Any]:
        entry = {
            "lead_url": lead_url,
            "amount": amount,
            "lead_source": lead_source,
            "status": status,
            "notes": notes,
            "recorded_at": datetime.now().isoformat(),
        }
        try:
            with open(self.deals_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
            logger.info(f"Deal recorded: ${amount:.2f} from {lead_url} ({status})")
        except Exception as exc:
            logger.error(f"Failed to record deal: {exc}")
        return entry

    def list_deals(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        deals = []
        try:
            with open(self.deals_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        deal = json.loads(line)
                        if status and deal.get("status") != status:
                            continue
                        deals.append(deal)
        except Exception:
            pass
        return deals[-limit:]

    def export_csv(self, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            output_path = settings.DATA_DIR / "outreach" / "reports" / "deals_export.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        deals = self.list_deals(limit=1000)
        fieldnames = ["lead_url", "amount", "lead_source", "status", "notes", "recorded_at"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for deal in deals:
                writer.writerow({k: deal.get(k, "") for k in fieldnames})
        logger.info(f"Deals exported to {output_path}")
        return output_path

    def get_summary(self) -> Dict[str, Any]:
        deals = self.list_deals(limit=1000)
        total = sum(d.get("amount", 0) for d in deals)
        by_source = {}
        for d in deals:
            src = d.get("lead_source", "unknown")
            by_source.setdefault(src, {"count": 0, "revenue": 0.0})
            by_source[src]["count"] += 1
            by_source[src]["revenue"] += d.get("amount", 0)
        return {
            "total_deals": len(deals),
            "total_revenue": total,
            "avg_deal_size": round(total / len(deals), 2) if deals else 0,
            "by_source": by_source,
        }
