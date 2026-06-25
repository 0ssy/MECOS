"""Cleanup fake leads, drafts, and test revenue from MECOS data."""
import json
from pathlib import Path

BASE = Path("C:/Users/josep/Downloads/MECOS")
OUTREACH = BASE / "data" / "outreach"

AGGREGATOR_DOMAINS = {
    "hn.algolia.com", "news.ycombinator.com", "reddit.com",
    "www.reddit.com", "old.reddit.com", "indiehackers.com",
    "www.indiehackers.com",
}

def clean_leads():
    path = OUTREACH / "leads.json"
    data = json.loads(path.read_text()) if path.exists() else []
    original = len(data)
    cleaned = [l for l in data if l.get("domain") not in AGGREGATOR_DOMAINS]
    path.write_text(json.dumps(cleaned, indent=2))
    print(f"Leads: {original} -> {len(cleaned)} (removed {original - len(cleaned)} fake)")

def clean_synthesized():
    path = OUTREACH / "synthesized_leads.json"
    data = json.loads(path.read_text()) if path.exists() else []
    original = len(data)
    cleaned = [b for b in data if b.get("domain") not in AGGREGATOR_DOMAINS]
    path.write_text(json.dumps(cleaned, indent=2))
    print(f"Briefs: {original} -> {len(cleaned)} (removed {original - len(cleaned)} fake)")

def clean_outbox():
    outbox = OUTREACH / "outbox"
    removed = 0
    for f in list(outbox.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            domain = d.get("lead_brief", {}).get("domain", "")
            if domain in AGGREGATOR_DOMAINS or d.get("type") == "reddit_post":
                f.unlink()
                removed += 1
        except Exception:
            continue
    print(f"Outbox: removed {removed} fake drafts")

def clean_revenue():
    path = OUTREACH / "revenue_ledger.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    entries = data.get("entries", [])
    original = len(entries)
    cleaned = [
        e for e in entries
        if "test" not in e.get("deal_id", "").lower()
        and "test" not in e.get("description", "").lower()
    ]
    data["entries"] = cleaned
    path.write_text(json.dumps(data, indent=2))
    print(f"Revenue entries: {original} -> {len(cleaned)} (removed {original - len(cleaned)} test)")

    payments_path = OUTREACH / "payments" / "payment_ledger.json"
    payments_data = json.loads(payments_path.read_text()) if payments_path.exists() else {}
    payments = payments_data.get("payments", [])
    cleaned_payments = [
        p for p in payments
        if "test" not in p.get("lead_id", "").lower()
        and "example.com" not in p.get("client_email", "").lower()
    ]
    payments_data["payments"] = cleaned_payments
    payments_path.write_text(json.dumps(payments_data, indent=2))
    print(f"Payment records: {len(payments)} -> {len(cleaned_payments)} (removed {len(payments) - len(cleaned_payments)} test)")

if __name__ == "__main__":
    clean_leads()
    clean_synthesized()
    clean_outbox()
    clean_revenue()
    print("Cleanup complete.")
