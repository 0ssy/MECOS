"""Full outreach data reset to eliminate fake orphaned data."""
import json
from pathlib import Path

BASE = Path("C:/Users/josep/Downloads/MECOS")
OUTREACH = BASE / "data" / "outreach"

AGGREGATOR_DOMAINS = {
    "hn.algolia.com", "news.ycombinator.com", "reddit.com",
    "www.reddit.com", "old.reddit.com", "indiehackers.com",
    "www.indiehackers.com", "linkedin.com", "www.linkedin.com",
    "upwork.com", "www.upwork.com",
}

def reset_leads():
    path = OUTREACH / "leads.json"
    path.write_text("[]")
    print("leads.json -> []")

def reset_synthesized():
    path = OUTREACH / "synthesized_leads.json"
    path.write_text("[]")
    print("synthesized_leads.json -> []")

def reset_outbox():
    outbox = OUTREACH / "outbox"
    removed = 0
    for f in list(outbox.glob("*.json")):
        f.unlink()
        removed += 1
    print(f"outbox/ -> cleared ({removed} files)")

def reset_sent():
    sent = OUTREACH / "sent"
    removed = 0
    for f in list(sent.glob("*.json")):
        f.unlink()
        removed += 1
    print(f"sent/ -> cleared ({removed} files)")

def reset_revenue():
    path = OUTREACH / "revenue_ledger.json"
    data = {
        "entries": [],
        "bucket_balances": {
            "ops_hardware": 0.0,
            "trading_reserve": 0.0,
            "growth_profit": 0.0,
        },
        "last_updated": "2026-06-25T17:48:00",
    }
    path.write_text(json.dumps(data, indent=2))
    print("revenue_ledger.json -> reset to zero")

def reset_payments():
    path = OUTREACH / "payments" / "payment_ledger.json"
    data = {
        "payments": [],
        "withdrawals": [],
        "last_updated": "2026-06-25T17:48:00",
    }
    path.write_text(json.dumps(data, indent=2))
    print("payment_ledger.json -> reset to empty")

if __name__ == "__main__":
    reset_leads()
    reset_synthesized()
    reset_outbox()
    reset_sent()
    reset_revenue()
    reset_payments()
    print("Full outreach reset complete.")
