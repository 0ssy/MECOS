"""
MECOS Outreach - Review Outbox CLI
Human-in-the-loop review tool for approving/rejecting/sending outreach drafts.

Usage:
    python outreach/review_outbox.py list
    python outreach/review_outbox.py approve 1,3,5
    python outreach/review_outbox.py reject 2,4
    python outreach/review_outbox.py send
    python outreach/review_outbox.py stats
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings


def get_outbox_dir() -> Path:
    return settings.DATA_DIR / "outreach" / "outbox"


def get_sent_dir() -> Path:
    return settings.DATA_DIR / "outreach" / "sent"


def load_drafts() -> List[Dict[str, Any]]:
    outbox_dir = get_outbox_dir()
    if not outbox_dir.exists():
        return []
    drafts = []
    for f in sorted(outbox_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            data["_filename"] = f.name
            drafts.append(data)
        except Exception:
            continue
    return drafts


def save_draft(draft: Dict[str, Any]):
    outbox_dir = get_outbox_dir()
    filename = draft.get("_filename")
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        domain = draft.get("lead_brief", {}).get("domain", "unknown")
        filename = f"{ts}_{domain}_{draft.get('type', 'draft')}.json"
        draft["_filename"] = filename
    path = outbox_dir / filename
    path.write_text(json.dumps(draft, default=str, indent=2))


def move_to_sent(draft: Dict[str, Any]):
    sent_dir = get_sent_dir()
    filename = draft.get("_filename")
    if not filename:
        return
    src = get_outbox_dir() / filename
    dst = sent_dir / filename
    if src.exists():
        src.rename(dst)
    else:
        dst.write_text(json.dumps(draft, default=str, indent=2))


def cmd_list(args: argparse.Namespace):
    drafts = load_drafts()
    if not drafts:
        print("No drafts in outbox.")
        return
    print(f"{'#':<4} {'Status':<20} {'To':<35} {'Subject':<50} {'Preview'}")
    print("-" * 140)
    for i, d in enumerate(drafts, 1):
        to = d.get("to", d.get("lead_brief", {}).get("domain", "unknown"))
        subject = d.get("subject", "")[:49]
        body = d.get("body", "")[:60].replace("\n", " ")
        status = d.get("status", "unknown")
        print(f"{i:<4} {status:<20} {to:<35} {subject:<50} {body}")
    print(f"\nTotal: {len(drafts)} drafts")


def cmd_approve(args: argparse.Namespace):
    indices = [int(x.strip()) for x in args.indices.split(",") if x.strip().isdigit()]
    drafts = load_drafts()
    changed = 0
    for idx in indices:
        if 1 <= idx <= len(drafts):
            d = drafts[idx - 1]
            old_status = d.get("status", "unknown")
            d["status"] = "approved_send"
            save_draft(d)
            changed += 1
            print(f"Approved #{idx}: {d.get('to', d.get('lead_brief', {}).get('domain'))} (was {old_status})")
        else:
            print(f"Skipped #{idx}: out of range")
    print(f"Approved {changed} drafts.")


def cmd_reject(args: argparse.Namespace):
    indices = [int(x.strip()) for x in args.indices.split(",") if x.strip().isdigit()]
    drafts = load_drafts()
    changed = 0
    for idx in indices:
        if 1 <= idx <= len(drafts):
            d = drafts[idx - 1]
            old_status = d.get("status", "unknown")
            d["status"] = "rejected"
            save_draft(d)
            changed += 1
            print(f"Rejected #{idx}: {d.get('to', d.get('lead_brief', {}).get('domain'))} (was {old_status})")
        else:
            print(f"Skipped #{idx}: out of range")
    print(f"Rejected {changed} drafts.")


def cmd_send(args: argparse.Namespace):
    from datetime import datetime, time as dt_time
    from outreach.delivery_agent import DeliveryAgent
    from outreach.email_verifier import verify_email_deliverable

    agent = DeliveryAgent()
    if not agent.email_enabled:
        print("ERROR: Email sending disabled. Set MECOS_EMAIL and MECOS_EMAIL_APP_PASSWORD in .env")
        sys.exit(1)

    now = datetime.now()
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    business_hour_start = dt_time(9, 0)
    business_hour_end = dt_time(17, 0)
    if not (business_hour_start <= now.time() <= business_hour_end):
        print(f"WARNING: Outside business hours ({now.time().strftime('%H:%M')}). Sending anyway per explicit CLI send command.")

    drafts = load_drafts()
    approved = [d for d in drafts if d.get("status") == "approved_send"]
    if not approved:
        print("No approved_send drafts found. Use 'approve' first.")
        return

    sent_today = sum(
        1 for d in drafts
        if d.get("status") == "sent"
        and d.get("sent_at", "") >= day_start.isoformat()
    )
    sent_this_hour = sum(
        1 for d in drafts
        if d.get("status") == "sent"
        and d.get("sent_at", "") >= current_hour_start.isoformat()
    )

    max_per_hour = 5
    max_per_day = 20
    available_hour = max_per_hour - sent_this_hour
    available_day = max_per_day - sent_today
    batch_size = min(len(approved), available_hour, available_day)

    if batch_size <= 0:
        print(f"THROTTLED: Already sent {sent_this_hour}/hr and {sent_today}/day today. Try again later.")
        return

    if len(approved) > batch_size:
        print(f"THROTTLE: {len(approved)} approved, but only {batch_size} slots available ({sent_this_hour}/{max_per_hour} hr, {sent_today}/{max_per_day} day). Sending first {batch_size}.")
        approved = approved[:batch_size]

    print(f"Sending {len(approved)} approved drafts...")
    sent = 0
    failed = 0
    for d in approved:
        to_addr = d.get("to", "")
        if not to_addr or "@" not in to_addr:
            print(f"  SKIP: no valid to address in {d.get('_filename')}")
            d["status"] = "skipped_invalid_email"
            save_draft(d)
            failed += 1
            continue

        if not verify_email_deliverable(to_addr):
            print(f"  SKIP: email not deliverable {to_addr}")
            d["status"] = "skipped_invalid_email"
            save_draft(d)
            failed += 1
            continue

        subject = d.get("subject", "")
        body = d.get("body", "")
        ok = agent._send_smtp(to_addr, subject, body)
        if ok:
            d["status"] = "sent"
            d["sent_at"] = datetime.now().isoformat()
            d["sent_via"] = "cli_review"
            move_to_sent(d)
            sent += 1
            print(f"  SENT: {to_addr} — {subject}")
        else:
            d["status"] = "send_failed"
            save_draft(d)
            failed += 1
            print(f"  FAIL: {to_addr} — {subject}")

    print(f"\nDone. Sent: {sent}, Failed/Skipped: {failed}")
    print(f"Today: {sent_today + sent}/{max_per_day} sent, {sent_this_hour + sent}/{max_per_hour} this hour")


def cmd_stats(args: argparse.Namespace):
    drafts = load_drafts()
    if not drafts:
        print("No drafts in outbox.")
        return
    counts: Dict[str, int] = {}
    for d in drafts:
        s = d.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    print("Outbox stats:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    print(f"  TOTAL: {len(drafts)}")


def main():
    parser = argparse.ArgumentParser(description="MECOS Outreach Outbox Review")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List pending drafts")
    p_approve = sub.add_parser("approve", help="Approve drafts by index (comma-separated)")
    p_approve.add_argument("indices", help="e.g. 1,3,5")
    p_reject = sub.add_parser("reject", help="Reject drafts by index (comma-separated)")
    p_reject.add_argument("indices", help="e.g. 2,4")
    p_send = sub.add_parser("send", help="Send all approved_send drafts")
    p_stats = sub.add_parser("stats", help="Show outbox stats by status")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "approve":
        cmd_approve(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
