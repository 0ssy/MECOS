"""
MECOS Outreach - CRM Actions
Handles status changes: new → contacted → replied → meeting_booked → deal_won / deal_lost.
Provides CLI: mecos crm push, mecos crm pull.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from config import settings
from outreach.deal_tracker import DealTracker


class CRMActions:
    """Manage lead lifecycle and CRM operations."""

    STATUS_SEQUENCE = ["new", "contacted", "replied", "meeting_booked", "deal_won", "deal_lost"]

    def __init__(self, jsonl_path: Optional[Path] = None):
        from outreach.crm.sheets_bridge import SheetsBridge
        self.jsonl_path = jsonl_path or settings.DATA_DIR / "outreach" / "crm_leads.jsonl"
        self.sheets_bridge = SheetsBridge()
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def list_leads(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List leads from local JSONL file."""
        leads = []
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        lead = json.loads(line)
                        if status and lead.get("status") != status:
                            continue
                        leads.append(lead)
        except Exception:
            pass
        return leads[-limit:]

    def get_lead(self, url: str) -> Optional[Dict[str, Any]]:
        """Get single lead by URL."""
        for lead in self.list_leads(limit=500):
            if lead.get("url") == url:
                return lead
        return None

    def create_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Create new lead entry."""
        lead["created_at"] = datetime.now().isoformat()
        lead["status"] = lead.get("status", "new")
        lead["updated_at"] = lead["created_at"]

        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead, default=str) + "\n")

        logger.info(f"CRM: Created lead {lead.get('domain', 'unknown')}")
        return lead

    def update_status(self, url: str, new_status: str, notes: str = "") -> Dict[str, Any]:
        """Update lead status with transition validation."""
        lead = self.get_lead(url)
        if not lead:
            return {"status": "error", "reason": "not_found"}

        current_status = lead.get("status", "new")
        if new_status not in self.STATUS_SEQUENCE:
            return {"status": "error", "reason": "invalid_status"}

        # Validate transition
        try:
            current_idx = self.STATUS_SEQUENCE.index(current_status)
            new_idx = self.STATUS_SEQUENCE.index(new_status)
            if new_idx < current_idx and new_status not in ("deal_lost", "deal_won"):
                return {"status": "error", "reason": "invalid_transition"}
        except ValueError:
            pass

        lead["status"] = new_status
        lead["updated_at"] = datetime.now().isoformat()
        if notes:
            lead["notes"] = notes
        if new_status in ("contacted", "replied", "meeting_booked"):
            lead["last_contact"] = datetime.now().isoformat()

        # Record deal if won
        if new_status == "deal_won":
            try:
                tracker = DealTracker()
                tracker.record_deal(
                    lead_url=url,
                    amount=float(lead.get("deal_amount", 0) or 0),
                    lead_source=lead.get("source", ""),
                    notes=notes or lead.get("notes", ""),
                    status="closed",
                )
            except Exception as exc:
                logger.warning(f"DealTracker sync failed: {exc}")

        # Rewrite JSONL with updated lead
        self._update_jsonl(lead, url)

        # Sync to Google Sheets
        self.sheets_bridge.update_lead_status(url, new_status, notes)

        logger.info(f"CRM: Updated {lead.get('domain', 'unknown')} status: {current_status} → {new_status}")
        return {"status": "success", "lead": lead}

    def _update_jsonl(self, updated_lead: Dict[str, Any], url: str) -> None:
        """Update lead in JSONL file."""
        leads = []
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        lead = json.loads(line)
                        if lead.get("url") == url:
                            leads.append(updated_lead)
                        else:
                            leads.append(lead)
        except Exception:
            leads = [updated_lead]

        with open(self.jsonl_path, "w", encoding="utf-8") as f:
            for lead in leads:
                f.write(json.dumps(lead, default=str) + "\n")

    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all leads with specific status."""
        return self.list_leads(status=status)

    def get_pipeline_stats(self) -> Dict[str, int]:
        """Get counts by status for pipeline view."""
        stats = {status: 0 for status in self.STATUS_SEQUENCE}
        for lead in self.list_leads(limit=1000):
            status = lead.get("status", "new")
            if status in stats:
                stats[status] += 1
        return stats

    def push_to_sheets(self) -> Dict[str, Any]:
        """Push all leads to Google Sheets."""
        leads = self.list_leads(limit=500)
        return self.sheets_bridge.push_leads(leads)

    def pull_from_sheets(self) -> Dict[str, Any]:
        """Pull leads from Google Sheets and merge."""
        sheet_leads = self.sheets_bridge.pull_leads()
        for lead in sheet_leads:
            existing = self.get_lead(lead.get("url", ""))
            if not existing:
                self.create_lead(lead)
        return {"status": "success", "count": len(sheet_leads)}


def cli_push() -> None:
    """CLI: Push leads to CRM."""
    actions = CRMActions()
    result = actions.push_to_sheets()
    print(json.dumps(result, indent=2))


def cli_pull() -> None:
    """CLI: Pull leads from CRM."""
    actions = CRMActions()
    result = actions.pull_from_sheets()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: mecos crm <push|pull|status|update>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "push":
        cli_push()
    elif cmd == "pull":
        cli_pull()
    elif cmd == "status":
        actions = CRMActions()
        print(json.dumps(actions.get_pipeline_stats(), indent=2))
    else:
        print(f"Unknown command: {cmd}")