"""
MECOS Outreach - Reply Monitor
Polls IMAP inbox, detects DEMO keyword replies, and stores reply events.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from mecos.email_ingester import EmailIngester, EmailDocument


class ReplyMonitor:
    def __init__(self, replies_path: Path | None = None):
        if replies_path is None:
            from config import settings
            replies_path = settings.DATA_DIR / "outreach" / "replies.json"
        self.replies_path = replies_path
        self.replies_path.parent.mkdir(parents=True, exist_ok=True)
        self.ingester = EmailIngester()
        self._replies = self._load_replies()

    def _load_replies(self) -> list[dict]:
        if self.replies_path.exists():
            try:
                data = json.loads(self.replies_path.read_text())
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def _save_replies(self):
        try:
            self.replies_path.write_text(json.dumps(self._replies, default=str, indent=2))
        except Exception as exc:
            logger.error(f"Failed to save replies: {exc}")

    def _matches_sent_email(self, doc: EmailDocument, sent_emails: list[dict]) -> dict | None:
        subject = doc.subject or ""
        sender = doc.sender or ""
        sender_email = sender.split("<")[-1].split(">")[0].strip().lower() if "<" in sender else sender.lower()

        for sent in sent_emails:
            sent_to = sent.get("to", "").lower()
            sent_subject = sent.get("subject", "")
            if not sent_to:
                continue
            sent_domain = sent_to.split("@")[-1] if "@" in sent_to else ""
            sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
            if sent_to == sender_email or (sent_domain and sender_domain and sent_domain == sender_domain):
                subject_base = re.sub(r"(?i)^re:\s*", "", subject).strip()
                sent_base = re.sub(r"(?i)^re:\s*", "", sent_subject).strip()
                if subject_base and sent_base and (subject_base == sent_base or subject_base in sent_base or sent_base in subject_base):
                    return sent
        return None

    def _detect_demo_keyword(self, body: str) -> bool:
        return bool(re.search(r"\bDEMO\b", body, re.IGNORECASE))

    def fetch_new_replies(self) -> list[dict]:
        docs = self.ingester.fetch_unread(max_emails=50)
        if not docs:
            logger.debug("Reply monitor: no new emails")
            return []

        from outreach.delivery_agent import DeliveryAgent
        delivery = DeliveryAgent()
        sent_emails = []
        for f in sorted(delivery.sent_dir.glob("*.json")):
            try:
                sent_emails.append(json.loads(f.read_text()))
            except Exception:
                continue

        new_replies = []
        for doc in docs:
            matched = self._matches_sent_email(doc, sent_emails)
            if not matched:
                continue

            demo_keyword = self._detect_demo_keyword(doc.body)
            reply_event = {
                "receiver_uid": doc.uid,
                "from": doc.sender,
                "subject": doc.subject,
                "body": doc.body,
                "date": doc.date,
                "matched_sent_file": None,
                "demo_keyword_detected": demo_keyword,
                "processed": False,
                "fetched_at": datetime.now().isoformat(),
            }

            if matched:
                from pathlib import Path as _P
                reply_event["matched_sent_file"] = str(_P(matched.get("_filename", "")))

            self._replies.append(reply_event)
            new_replies.append(reply_event)

        self._save_replies()
        logger.info(f"Reply monitor: found {len(new_replies)} matching replies")
        return new_replies

    def mark_processed(self, receiver_uid: str, demo_triggered: bool = False):
        for r in self._replies:
            if r.get("receiver_uid") == receiver_uid:
                r["processed"] = True
                r["demo_triggered"] = demo_triggered
        self._save_replies()

    def has_reply_for_sent_file(self, sent_file: str) -> bool:
        for r in self._replies:
            if r.get("matched_sent_file") == sent_file and r.get("processed"):
                return True
        return False

    def get_unprocessed_demo_replies(self) -> list[dict]:
        return [r for r in self._replies if r.get("demo_keyword_detected") and not r.get("processed")]
