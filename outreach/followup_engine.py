"""
MECOS Outreach - Follow-up Engine
Manages 3d/7d/14d follow-up sequences for sent emails.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class FollowupEngine:
    def __init__(self):
        from config import settings
        self.sent_dir = settings.DATA_DIR / "outreach" / "sent"
        self.sent_dir.mkdir(parents=True, exist_ok=True)
        self.replies_path = settings.DATA_DIR / "outreach" / "replies.json"
        self.outbox_dir = settings.DATA_DIR / "outreach" / "outbox"
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.schedule = {"day_3": 3, "day_7": 7, "day_14": 14}

    def _load_replies(self) -> list[dict]:
        if self.replies_path.exists():
            try:
                return json.loads(self.replies_path.read_text())
            except Exception:
                pass
        return []

    def _has_reply(self, sent_file: str | Path) -> bool:
        base = Path(sent_file).name if isinstance(sent_file, str) else sent_file.name
        for r in self._load_replies():
            if r.get("matched_sent_file") == base or r.get("matched_sent_file") in str(sent_file):
                return True
        return False

    def get_sent_emails_needing_followup(self) -> list[dict]:
        now = datetime.now()
        followups = []

        for f in sorted(self.sent_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue

            if data.get("type") not in ("email",):
                continue

            sent_raw = data.get("sent_at") or data.get("created_at", "")
            if not sent_raw:
                continue
            try:
                sent_at = datetime.fromisoformat(sent_raw)
            except Exception:
                continue

            if (now - sent_at).total_seconds() < 0:
                continue

            base = f.name

            for label, days in self.schedule.items():
                due_at = sent_at + timedelta(days=days)
                if now >= due_at and not self._has_reply(base):
                    followups.append({"sent_file": base, "label": label, "days": days, "sent_at": sent_at.isoformat(), "draft": data})
                    break
        return followups

    def create_followup_drafts(self, limit: int = 10) -> list[dict]:
        followups = self.get_sent_emails_needing_followup()
        drafts = []

        for item in followups[:limit]:
            draft = self._build_followup_draft(item["draft"], item["label"])
            if draft:
                from outreach.delivery_agent import DeliveryAgent
                delivery = DeliveryAgent()
                path = delivery.save_draft(draft)
                drafts.append({"saved": str(path), "label": item["label"], "sent_file": item["sent_file"]})
                logger.info(f"Follow-up draft created: {item['label']} for {item['sent_file']}")

        logger.info(f"Follow-up engine: generated {len(drafts)} follow-up drafts")
        return drafts

    def _build_followup_draft(self, sent_draft: dict, label: str) -> dict | None:
        lead_brief = sent_draft.get("lead_brief", {}) or {}
        referral_code = sent_draft.get("referral_code", "")
        to_addr = sent_draft.get("to", "unknown@example.com")

        if label == "day_3":
            subject = "Quick follow-up — {domain}".format(domain=lead_brief.get("domain", "you"))
            body = (
                f"Hi,\n\n"
                f"Just checking in — did my last note about {lead_brief.get('domain', 'your process')} land?\n\n"
                f"If you're still exploring automation options, I'm happy to share a quick case study "
                f"or jump on a 10-min call this week.\n\n"
                f"Reply anytime and I'll get right back to you.\n"
            )
        elif label == "day_7":
            subject = "Update — 2 spots left this month"
            body = (
                f"Hi again,\n\n"
                f"Quick update: we just wrapped a similar project with another client this week, "
                f"so I have limited capacity for new builds before month-end.\n\n"
                f"If you wanted to move forward, now is the time to lock it in.\n\n"
                f"Reply 'BOOK' and I'll send a calendar link.\n"
            )
        else:
            subject = "Last check-in — closing file this week"
            body = (
                f"Hi,\n\n"
                f"Closing out outreach for this cycle, so this is my last note.\n\n"
                f"If timing is better later, just reply with 'RETRY' and I'll add you back.\n\n"
                f"No hard feelings if now isn't the right time.\n"
            )

        return {
            "type": "followup_email",
            "to": to_addr,
            "subject": subject,
            "body": body,
            "lead_brief": lead_brief,
            "referral_code": referral_code,
            "original_sent_file": sent_draft.get("_filename"),
            "created_at": datetime.now().isoformat(),
            "status": "pending_send",
            "channel": "followup",
        }
