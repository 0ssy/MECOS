"""
MECOS Outreach - Email Sequence Engine
3-touch follow-up sequence:
1. Initial outreach (exists)
2. Value-add follow-up (50% off first bot + case study) — 3 days later
3. Final attempt (social proof: "12 startups using MECOS") — 7 days after #2
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import settings


class EmailSequence:
    """Manages email follow-up sequences."""

    TIMING = {
        "touch_1": 0,       # Initial send
        "touch_2": 3,       # 3 days later
        "touch_3": 7,       # 7 days after touch 2 (10 days total)
    }

    TEMPLATES = {
        "touch_1": {
            "subject": "Quick automation idea for {domain}",
            "body": (
                "Hi {name},\n\n"
                "I spotted {domain} while researching automation pain points. "
                "Many similar businesses struggle with {pain_point}.\n\n"
                "I've helped bootstrapped companies automate workflows like this — "
                "would you be open to a quick case study showing how we saved "
                "~15 hours/week for a comparable business?\n\n"
                "Either way, keep crushing it!\n"
            ),
        },
        "touch_2": {
            "subject": "50% off your first automation — 3 days later",
            "body": (
                "Hi {name},\n\n"
                "Just circling back on my note about {domain}. "
                "I'd like to offer 50% off your first automation bot.\n\n"
                "Here's a quick case study: a local HVAC business I worked with "
                "automated their scheduling and intake process, saving 20+ hours weekly:\n\n"
                "{case_study_link}\n\n"
                "If this resonates, reply 'YES' and I'll send pricing options.\n\n"
                "Cheers,\n"
            ),
        },
        "touch_3": {
            "subject": "12 startups using MECOS + last check-in",
            "body": (
                "Hi {name},\n\n"
                "Last note — we're now working with 12 SaaS startups and 8 e-commerce "
                "stores on automation workflows.\n\n"
                "A few quick wins from recent projects:\n"
                "- Order intake automation (3x faster)\n"
                "- Email follow-ups (set-n-forget)\n"
                "- Customer data sync (zero manual entry)\n\n"
                "If you're still exploring options, I'm happy to jump on a 10-min call. "
                "Otherwise, no hard feelings — just wanted to share.\n\n"
                "Best,\n"
            ),
        },
    }

    def __init__(self, sequence_path: Optional[Path] = None):
        self.sequence_path = sequence_path or settings.DATA_DIR / "outreach" / "email_sequences.jsonl"
        self.sequence_path.parent.mkdir(parents=True, exist_ok=True)

    def create_sequence(self, lead: Dict[str, Any], initial_draft_path: Path) -> Dict[str, Any]:
        """Create a follow-up sequence for a lead."""
        domain = lead.get("domain", "your business")
        name = lead.get("contacts", {}).get("decision_maker", {}).get("name", "there")
        pain = lead.get("pain", ["manual processes"])[0] if lead.get("pain") else "manual processes"

        sequence = {
            "lead_url": lead.get("url", ""),
            "lead_domain": domain,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "touches_sent": [initial_draft_path.name],
            "next_touch": self._calculate_next_touch(1),
            "touch_timing": {f"touch_{i}": {"due_at": self._calculate_next_touch(i), "sent_at": None} 
                           for i in range(1, 4)},
        }

        self._save_sequence(sequence)
        logger.info(f"Email sequence created for {domain}")
        return sequence

    def _calculate_next_touch(self, touch_num: int) -> str:
        """Calculate when next touch should be sent."""
        days_offset = self.TIMING.get(f"touch_{touch_num}", 0)
        if touch_num == 1:
            days_offset = 3
        elif touch_num == 2:
            days_offset = 7
        else:
            days_offset = 14
        return (datetime.now() + timedelta(days=days_offset)).isoformat()

    def _save_sequence(self, sequence: Dict[str, Any]) -> None:
        """Save sequence to JSONL."""
        with open(self.sequence_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sequence, default=str) + "\n")

    def get_due_sequences(self) -> List[Dict[str, Any]]:
        """Get sequences that are due for next touch."""
        due = []
        now = datetime.now()
        try:
            with open(self.sequence_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    seq = json.loads(line)
                    if seq.get("status") != "active":
                        continue
                    for touch_key, touch_data in seq.get("touch_timing", {}).items():
                        if touch_data.get("sent_at") is None:
                            due_at = touch_data.get("due_at")
                            if due_at:
                                touch_due = datetime.fromisoformat(due_at)
                                if now >= touch_due:
                                    due.append(seq)
                                    break
        except Exception as e:
            logger.debug(f"Sequence read error: {e}")
        return due

    def mark_sent(self, lead_url: str, touch_num: int, draft_path: Path) -> bool:
        """Mark a touch as sent."""
        sequences = []
        updated = False
        try:
            with open(self.sequence_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    seq = json.loads(line)
                    if seq.get("lead_url") == lead_url:
                        touch_key = f"touch_{touch_num}"
                        if touch_key in seq.get("touch_timing", {}):
                            seq["touch_timing"][touch_key]["sent_at"] = datetime.now().isoformat()
                            updated = True
                    sequences.append(seq)
        except Exception:
            return False

        self._rewrite_sequences(sequences)
        return updated

    def _rewrite_sequences(self, sequences: List[Dict[str, Any]]) -> None:
        """Rewrite sequences to file."""
        with open(self.sequence_path, "w", encoding="utf-8") as f:
            for seq in sequences:
                f.write(json.dumps(seq, default=str) + "\n")

    def get_template(self, touch: str, lead: Dict[str, Any]) -> Dict[str, str]:
        """Get templated content for a touch."""
        domain = lead.get("domain", "your business")
        name = lead.get("contacts", {}).get("decision_maker", {}).get("name", "there")
        pain = lead.get("pain", ["manual processes"])[0] if lead.get("pain") else "manual processes"

        template = self.TEMPLATES.get(touch, {})
        return {
            "subject": template.get("subject", "").format(domain=domain, name=name),
            "body": template.get("body", "").format(
                domain=domain, name=name, pain_point=pain,
                case_study_link="[case study link]",
            ),
        }

    def cancel_sequence(self, lead_url: str) -> bool:
        """Cancel sequence (lead replied or deal closed)."""
        sequences = []
        cancelled = False
        try:
            with open(self.sequence_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    seq = json.loads(line)
                    if seq.get("lead_url") == lead_url:
                        seq["status"] = "cancelled"
                        cancelled = True
                    sequences.append(seq)
        except Exception:
            return False

        self._rewrite_sequences(sequences)
        return cancelled