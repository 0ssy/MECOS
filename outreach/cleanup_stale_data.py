"""
MECOS Outreach - Stale Data Cleanup
Archives outbox drafts for enterprise/aggregator domains and
cleans leads.json / synthesized_leads.json of bad entries.

Run: python -m outreach.cleanup_stale_data
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from loguru import logger

ARCHIVE_DIR = Path("data/outreach/archive_stale")
BAD_DOMAINS = {
    "microsoft.com", "www.microsoft.com",
    "marketscreener.com", "www.marketscreener.com",
    "markets.businessinsider.com",
    "workspace.google.com",
    "mailmeteor.com",
    "dat.com", "www.dat.com",
    "spiceworks.com", "www.spiceworks.com",
    "hillwalktours.com", "www.hillwalktours.com",
}
BAD_DOMAIN_SUBSTRINGS = [
    "microsoft.com", "marketscreener.com", "businessinsider.com",
    "workspace.google.com", "mailmeteor.com", "dat.com",
    "spiceworks.com", "hillwalktours.com",
]


def _is_bad_domain(domain: str) -> bool:
    d = domain.lower()
    if d in BAD_DOMAINS:
        return True
    for sub in BAD_DOMAIN_SUBSTRINGS:
        if sub in d:
            return True
    return False


def clean_outbox():
    outbox = Path("data/outreach/outbox")
    if not outbox.exists():
        logger.info("Outbox does not exist, skipping.")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in sorted(outbox.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        domain = ""
        lead_brief = data.get("lead_brief", {})
        if isinstance(lead_brief, dict):
            domain = lead_brief.get("domain", "")
        if not domain:
            domain = data.get("domain", "")

        if _is_bad_domain(domain):
            dest = ARCHIVE_DIR / f.name
            shutil.move(str(f), str(dest))
            moved += 1

    logger.info(f"Outbox cleanup: archived {moved} stale drafts to {ARCHIVE_DIR}")
    return moved


def clean_leads():
    leads_path = Path("data/outreach/leads.json")
    if not leads_path.exists():
        logger.info("leads.json does not exist, skipping.")
        return 0

    leads = json.loads(leads_path.read_text(encoding="utf-8"))
    original = len(leads)
    cleaned = []
    for lead in leads:
        domain = lead.get("domain", "")
        if _is_bad_domain(domain):
            continue
        contacts = lead.get("contacts", {})
        emails = contacts.get("emails", [])
        filtered_emails = [e for e in emails if not _is_placeholder_email(e)]
        if filtered_emails != emails:
            lead = dict(lead)
            lead["contacts"] = dict(contacts)
            lead["contacts"]["emails"] = filtered_emails
        cleaned.append(lead)

    leads_path.write_text(json.dumps(cleaned, default=str, indent=2), encoding="utf-8")
    logger.info(f"leads.json cleanup: removed {original - len(cleaned)} bad leads, kept {len(cleaned)}")
    return original - len(cleaned)


def clean_synthesized():
    synth_path = Path("data/outreach/synthesized_leads.json")
    if not synth_path.exists():
        logger.info("synthesized_leads.json does not exist, skipping.")
        return 0

    briefs = json.loads(synth_path.read_text(encoding="utf-8"))
    original = len(briefs)
    cleaned = []
    for brief in briefs:
        domain = brief.get("domain", "")
        if _is_bad_domain(domain):
            continue
        cleaned.append(brief)

    synth_path.write_text(json.dumps(cleaned, default=str, indent=2), encoding="utf-8")
    logger.info(f"synthesized_leads.json cleanup: removed {original - len(cleaned)} bad briefs, kept {len(cleaned)}")
    return original - len(cleaned)


def _is_placeholder_email(email: str) -> bool:
    email_lower = email.lower()
    if not email_lower or "@" not in email_lower:
        return True
    placeholders = {
        "name@company.com", "email@domain.com", "your@email.com",
        "user@example.com", "info@example.com", "admin@example.com",
        "test@test.com", "example@example.com",
    }
    if email_lower in placeholders:
        return True
    local, domain = email_lower.rsplit("@", 1)
    if domain in ("example.com", "test.com", "domain.com", "placeholder.com"):
        return True
    if local in ("name", "email", "your", "user", "info", "admin", "webmaster", "test", "example"):
        if domain in ("company.com", "domain.com", "example.com", "test.com"):
            return True
    return False


def main():
    logger.info("Starting stale data cleanup...")
    outbox_moved = clean_outbox()
    leads_removed = clean_leads()
    synth_removed = clean_synthesized()
    logger.info(
        f"Cleanup complete: {outbox_moved} outbox drafts archived, "
        f"{leads_removed} leads removed, {synth_removed} briefs removed."
    )


if __name__ == "__main__":
    main()
