"""
MECOS Outreach Dashboard
Real-time browser dashboard with Hermis terminal aesthetic.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from loguru import logger

DASHBOARD_DATA_DIR = Path("data/outreach")
DASHBOARD_PORT = 8080


class DashboardService:
    @staticmethod
    def get_status() -> Dict[str, Any]:
        today = datetime.now().date().isoformat()
        status: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "date": today,
            "today_sent": 0,
            "today_drafts": 0,
            "today_flagged": 0,
            "today_rejected": 0,
            "today_skipped_icp": 0,
            "total_replies": 0,
            "total_revenue": 0.0,
            "scheduler_running": False,
            "last_send_timestamp": None,
            "recent_emails": [],
            "recent_replies": [],
            "total_skipped_leads": 0,
        }

        try:
            status["today_sent"] = DashboardService._get_today_sent(today)
            status["today_drafts"] = DashboardService._get_today_drafts(today)
            status["today_skipped_icp"] = DashboardService._count_jsonl_lines(
                DASHBOARD_DATA_DIR / "skipped_leads.jsonl"
            )
            status["total_replies"] = DashboardService._count_json_array(
                DASHBOARD_DATA_DIR / "replies.json"
            )
            status["total_revenue"] = DashboardService._sum_revenue(
                DASHBOARD_DATA_DIR / "revenue_ledger.json"
            )
            status["recent_emails"] = DashboardService._get_recent_emails(limit=10)
            status["recent_replies"] = DashboardService._get_recent_replies(limit=10)
            status["total_skipped_leads"] = status["today_skipped_icp"]
            if status["recent_emails"]:
                status["last_send_timestamp"] = status["recent_emails"][0].get("created_at")
        except Exception as exc:
            logger.error("Dashboard status error: {}", exc)

        status["scheduler_running"] = DashboardService._check_scheduler_running()
        return status

    @staticmethod
    def _get_today_sent(today: str) -> int:
        metrics_path = DASHBOARD_DATA_DIR / "daily_metrics.jsonl"
        if not metrics_path.exists():
            outbox_path = DASHBOARD_DATA_DIR / "outbox"
            if outbox_path.exists():
                count = 0
                for f in outbox_path.iterdir():
                    if f.is_file() and f.suffix == ".json":
                        try:
                            data = json.loads(f.read_text(encoding="utf-8"))
                            created = data.get("created_at", "")
                            if created.startswith(today):
                                count += 1
                        except Exception:
                            continue
                return count
            return 0
        sent = 0
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("date") == today:
                        sent += entry.get("auto_sent", 0)
        except Exception:
            pass
        return sent

    @staticmethod
    def _get_today_drafts(today: str) -> int:
        metrics_path = DASHBOARD_DATA_DIR / "daily_metrics.jsonl"
        if not metrics_path.exists():
            return 0
        drafts = 0
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("date") == today:
                        drafts += entry.get("drafts_created", 0)
        except Exception:
            pass
        return drafts

    @staticmethod
    def _count_jsonl_lines(path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                for _ in f:
                    count += 1
        except Exception:
            pass
        return count

    @staticmethod
    def _count_json_array(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return len(data)
        except Exception:
            pass
        return 0

    @staticmethod
    def _sum_revenue(path: Path) -> float:
        if not path.exists():
            return 0.0
        total = 0.0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
            for entry in entries:
                total += float(entry.get("amount", 0))
        except Exception:
            pass
        return total

    @staticmethod
    def _get_recent_emails(limit: int = 10) -> list:
        outbox_path = DASHBOARD_DATA_DIR / "outbox"
        if not outbox_path.exists():
            return []
        files = []
        for f in outbox_path.iterdir():
            if f.is_file() and f.suffix == ".json":
                files.append(f)
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        recent = []
        for f in files[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                recent.append({
                    "to": data.get("to", ""),
                    "subject": data.get("subject", ""),
                    "created_at": data.get("created_at", ""),
                    "status": data.get("status", ""),
                })
            except Exception:
                continue
        return recent

    @staticmethod
    def _get_recent_replies(limit: int = 10) -> list:
        replies_path = DASHBOARD_DATA_DIR / "replies.json"
        if not replies_path.exists():
            return []
        try:
            data = json.loads(replies_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                recent = data[-limit:]
                for r in recent:
                    r["received_at"] = r.get("received_at", "")
                return list(reversed(recent))
        except Exception:
            pass
        return []

    @staticmethod
    def _check_scheduler_running() -> bool:
        import subprocess
        try:
            result = subprocess.run(
                ["python", "-c", "import psutil; procs=[p for p in psutil.process_iter(['pid','name','cmdline']) if 'main.py' in ' '.join(p.info['cmdline'] or [])]; print(len(procs))"],
                capture_output=True, text=True, timeout=2
            )
            count = int(result.stdout.strip() or 0)
            return count > 0
        except Exception:
            return False


class DraftApprovalAPI:
    """API for approving/rejecting drafts in the outbox."""

    @staticmethod
    def list_pending_drafts() -> list:
        outbox_path = DASHBOARD_DATA_DIR / "outbox"
        if not outbox_path.exists():
            return []
        drafts = []
        for f in sorted(outbox_path.glob("*.json")):
            if f.is_file() and f.suffix == ".json":
                try:
                    data = json.loads(f.read_text())
                    if data.get("status") in ("pending_review", "pending_send"):
                        drafts.append({
                            "filename": f.name,
                            "to": data.get("to", ""),
                            "subject": data.get("subject", ""),
                            "body": data.get("body", ""),
                            "created_at": data.get("created_at", ""),
                            "status": data.get("status", ""),
                        })
                except Exception:
                    continue
        return drafts

    @staticmethod
    def approve_draft(filename: str) -> dict:
        outbox_path = DASHBOARD_DATA_DIR / "outbox" / filename
        if not outbox_path.exists():
            return {"error": "not_found"}
        data = json.loads(outbox_path.read_text())
        data["status"] = "approved_send"
        data["approved_at"] = datetime.now().isoformat()
        data["approved_by"] = "manual"
        outbox_path.write_text(json.dumps(data, indent=2, default=str))
        return {"status": "approved", "filename": filename}

    @staticmethod
    def reject_draft(filename: str) -> dict:
        outbox_path = DASHBOARD_DATA_DIR / "outbox" / filename
        if not outbox_path.exists():
            return {"error": "not_found"}
        data = json.loads(outbox_path.read_text())
        data["status"] = "rejected"
        outbox_path.write_text(json.dumps(data, indent=2, default=str))
        return {"status": "rejected", "filename": filename}
