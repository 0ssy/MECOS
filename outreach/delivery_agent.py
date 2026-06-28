"""
MECOS Outreach - Delivery Agent
Drafts cold emails, DMs, and social posts from synthesized lead briefs.
Can auto-send emails via SMTP (Gmail App Password from .env).
Drafts saved to outbox/ for human review of non-email channels.
"""
from __future__ import annotations

import json
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config import settings


class DeliveryAgent:
    def __init__(self):
        self.outbox_dir = settings.DATA_DIR / "outreach" / "outbox"
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.sent_dir = settings.DATA_DIR / "outreach" / "sent"
        self.sent_dir.mkdir(parents=True, exist_ok=True)
        self.email_enabled = bool(settings.MECOS_EMAIL and settings.MECOS_EMAIL_APP_PASSWORD)
        if not self.email_enabled:
            logger.warning("MECOS_EMAIL or MECOS_EMAIL_APP_PASSWORD not set — email sending disabled")

    def draft_email(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        domain = brief.get("domain", "your company")
        pain = brief.get("pain_points", ["efficiency"])[0].replace("_", " ")
        matched_terms = brief.get("matched_terms", [])[:3]
        package = brief.get("recommended_package", {})
        contacts = brief.get("contacts", {})
        emails = contacts.get("emails", [])
        research_summary = brief.get("research_summary", "")
        recommended_tool = brief.get("recommended_first_tool", "custom automation bot")

        recipient = emails[0] if emails else "unknown@example.com"

        personalization = ""
        if matched_terms:
            personalization = f"I came across {domain} and noticed you mention {', '.join(matched_terms[:2])} on your site.\n\n"
        if research_summary:
            personalization += f"{research_summary}\n\n"

        primary_pain = pain.replace("/", " / ").title()

        subject = f"Quick thought for {domain} — {primary_pain}"

        body = (
            f"Hi there,\n\n"
            f"{personalization}"
            f"I build focused automations for local service businesses, and {primary_pain.lower()} "
            f"tends to be one of the biggest time sinks I see.\n\n"
            f"For a business like yours, I'd recommend starting with a single high-impact build:\n"
            f"- {recommended_tool.title()}\n"
            f"- Turnaround: {package.get('delivery', '3-5 days')} (fixed scope, no long-term contract)\n"
            f"- Investment: {package.get('price_range', '$500-$1,500')}\n\n"
            f"No monthly retainers, no lock-in. Just a working tool that replaces the repetitive part of your workflow.\n\n"
            f"If this sounds useful, I can send a quick demo of a comparable build so you can see exactly what's possible.\n\n"
            f"Best,\n"
            f"MECOS Automation\n\n"
            f"---\n"
            f"Reply STOP to unsubscribe."
        )

        draft = {
            "type": "email",
            "to": recipient,
            "subject": subject,
            "body": body,
            "lead_brief": brief,
            "created_at": datetime.now().isoformat(),
            "status": "pending_send",
            "channel": "personal_email",
        }
        return draft

    def _send_smtp(self, to_addr: str, subject: str, body: str) -> bool:
        if not self.email_enabled:
            logger.error("Email sending disabled: MECOS_EMAIL or MECOS_EMAIL_APP_PASSWORD missing")
            return False

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.MECOS_EMAIL
        msg["To"] = to_addr

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls(context=context)
                server.login(settings.MECOS_EMAIL, settings.MECOS_EMAIL_APP_PASSWORD.replace(" ", ""))
                server.sendmail(settings.MECOS_EMAIL, to_addr, msg.as_string())
            logger.info(f"Email sent to {to_addr}: {subject}")
            return True
        except Exception as e:
            logger.error(f"SMTP send failed to {to_addr}: {e}")
            return False

    def send_draft(self, draft: Dict[str, Any]) -> bool:
        if draft.get("type") not in ("email", "vsl_followup"):
            logger.warning(f"Auto-send only supports email/vsl_followup drafts (type={draft.get('type')})")
            return False
        if draft.get("status") not in ("pending_send", "approved_send"):
            logger.warning(f"Draft status is not sendable: {draft.get('status')}")
            return False

        to_addr = draft.get("to", "")
        if not to_addr or "@" not in to_addr:
            logger.warning(f"Invalid recipient: {to_addr}")
            draft["status"] = "skipped_invalid_email"
            self._save_draft(draft)
            return False

        from outreach.email_verifier import verify_email_deliverable
        if not verify_email_deliverable(to_addr):
            logger.warning(f"Email not deliverable: {to_addr}")
            draft["status"] = "skipped_invalid_email"
            self._save_draft(draft)
            return False

        success, message_id = self._send_smtp(to_addr, draft["subject"], draft["body"])
        if success:
            draft["status"] = "sent"
            draft["sent_at"] = datetime.now().isoformat()
            draft["sent_via"] = "smtp"
            draft["message_id"] = message_id
            self._move_to_sent(draft)
        else:
            draft["status"] = "send_failed"
            self._save_draft(draft)
        return success

    def _save_draft(self, draft: Dict[str, Any]):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = draft.get("lead_brief", {}).get("domain", "unknown")
        filename = f"{ts}_{domain}_{draft.get('type', 'draft')}.json"
        path = self.outbox_dir / filename
        path.write_text(json.dumps(draft, default=str, indent=2))

    def update_draft(self, draft: Dict[str, Any]) -> None:
        """Update an existing draft file in place."""
        filename = draft.get("_filename")
        if filename:
            path = self.outbox_dir / filename
            if path.exists():
                path.write_text(json.dumps(draft, default=str, indent=2))

    def _move_to_sent(self, draft: Dict[str, Any]):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = draft.get("lead_brief", {}).get("domain", "unknown")
        filename = f"{ts}_{domain}_{draft.get('type', 'sent')}.json"
        src = self.outbox_dir / draft.get("_filename", filename)
        dst = self.sent_dir / filename
        if src.exists():
            src.rename(dst)
        else:
            dst.write_text(json.dumps(draft, default=str, indent=2))

    def draft_dm_twitter(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        domain = brief.get("domain", "")
        pain = brief.get("pain_points", ["manual tasks"])[0].replace("_", " ")
        package = brief.get("recommended_package", {})

        text = (
            f"Saw @{domain} — if you're still managing {pain} manually, "
            f"I can build you a custom bot that runs it on autopilot. "
            f"({package.get('price_range', '$500+')} | {package.get('delivery', '1 week')})\n\n"
            f"No monthly fees, no lock-in. DM me if curious?"
        )

        draft = {
            "type": "twitter_dm",
            "to": f"@{domain}",
            "text": text,
            "lead_brief": brief,
            "created_at": datetime.now().isoformat(),
            "status": "pending_review",
            "channel": "agent_reach_twitter",
        }
        return draft

    def draft_linkedin_message(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        domain = brief.get("domain", "")
        pain = brief.get("pain_points", ["operational overhead"])[0].replace("_", " ")
        package = brief.get("recommended_package", {})

        text = (
            f"Hi, I came across {domain} and had a quick thought.\n\n"
            f"Based on what you're doing, {pain} is likely eating into your team's bandwidth.\n\n"
            f"I specialize in building custom automation agents — web scraping, data pipelines, "
            f"workflow bots — that replace manual work with reliable, scheduled scripts.\n\n"
            f"I recently built a bot that cut a client's data entry from 4 hours/day to 15 minutes.\n\n"
            f"Worth a 10-minute call to see if there's a fit?\n\n"
            f"Reply here or book directly: calendly.com/mecos-automation"
        )

        draft = {
            "type": "linkedin_message",
            "to": domain,
            "text": text,
            "lead_brief": brief,
            "created_at": datetime.now().isoformat(),
            "status": "pending_review",
            "channel": "agent_reach_linkedin",
        }
        return draft

    def draft_reddit_post(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        domain = brief.get("domain", "")
        pain = brief.get("pain_points", ["manual data work"])[0].replace("_", " ")
        package = brief.get("recommended_package", {})

        title = f"[Show MECOS] Built an automation bot that removed {pain} for a local business"
        body = (
            f"Background: I run an automation agency (MECOS) and recently finished a project for {domain}.\n\n"
            f"The problem: {pain.title()}\n"
            f"The solution: Custom Python bot using browser automation + data pipelines.\n"
            f"Result: {package.get('description', 'Significant time savings')}.\n\n"
            f"I'm documenting the build process and sharing the open-source components.\n\n"
            f"If you run into similar ops headaches, feel free to reach out. Happy to do a free 15-min audit.\n\n"
            f"GitHub: [link]\nDemo video: [link]"
        )

        draft = {
            "type": "reddit_post",
            "subreddit": "automation",
            "title": title,
            "body": body,
            "lead_brief": brief,
            "created_at": datetime.now().isoformat(),
            "status": "pending_review",
            "channel": "agent_reach_reddit",
        }
        return draft

    def draft_for_lead(self, brief: Dict[str, Any], channels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if channels is None:
            channels = ["email"]

        drafts = []
        contacts = brief.get("contacts", {})
        has_email = bool(contacts.get("emails"))

        if "email" in channels and has_email:
            drafts.append(self.draft_email(brief))

        return drafts

    def save_draft(self, draft: Dict[str, Any]) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = draft.get("lead_brief", {}).get("domain", "unknown")
        filename = f"{ts}_{domain}_{draft.get('type', 'draft')}.json"
        path = self.outbox_dir / filename
        draft["_filename"] = filename
        path.write_text(json.dumps(draft, default=str, indent=2))
        logger.info(f"Draft saved to outbox: {path.name}")
        return path

    def save_drafts(self, drafts: List[Dict[str, Any]]) -> List[Path]:
        paths = []
        for draft in drafts:
            try:
                paths.append(self.save_draft(draft))
            except Exception as e:
                logger.error(f"Failed to save draft: {e}")
        return paths

    def list_pending(self) -> List[Dict[str, Any]]:
        pending = []
        for f in sorted(self.outbox_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                if data.get("status") in ("pending_review", "pending_send"):
                    pending.append(data)
            except Exception:
                continue
        return pending

    def mark_sent(self, filename: str):
        src = self.outbox_dir / filename
        dst = self.sent_dir / filename
        if src.exists():
            try:
                data = json.loads(src.read_text())
                data["status"] = "sent"
                data["sent_at"] = datetime.now().isoformat()
                dst.write_text(json.dumps(data, default=str, indent=2))
                src.unlink()
                logger.info(f"Draft marked as sent: {filename}")
            except Exception as e:
                logger.error(f"Failed to mark draft as sent: {e}")
