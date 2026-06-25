import json
from pathlib import Path
from datetime import datetime

BASE = Path("C:/Users/josep/Downloads/MECOS")
OUTREACH = BASE / "data" / "outreach"

leads = json.loads((OUTREACH / "leads.json").read_text())
revenue = json.loads((OUTREACH / "revenue_ledger.json").read_text())
payments = json.loads((OUTREACH / "payments" / "payment_ledger.json").read_text())

now_str = datetime.now().strftime("%H:%M:%S")

print("=== MECOS Business Snapshot ===")
print("Time:", now_str)
print()
print("REVENUE")
buckets = revenue.get("bucket_balances", {})
total = sum(v for v in buckets.values())
print("  Total: $%.2f" % total)
for k in ["ops_hardware", "trading_reserve", "growth_profit"]:
    print("  %s: $%.2f" % (k, buckets.get(k, 0)))
print("  Transactions:", len(revenue.get("entries", [])))
print()
print("OUTREACH")
new = sum(1 for l in leads if l.get("status") == "new")
contacted = sum(1 for l in leads if l.get("status") == "contacted")
print("  Total leads:", len(leads))
print("  New:", new, "| Contacted:", contacted)
if leads:
    avg = sum(l.get("total_score", 0) for l in leads) / max(len(leads), 1)
    print("  Avg score: %.1f" % avg)
print("  Sources:")
sources = {}
for l in leads:
    src = l.get("source", "unknown").split("/")[0]
    sources[src] = sources.get(src, 0) + 1
for s, c in sorted(sources.items(), key=lambda x: -x[1]):
    print("    %s: %d" % (s, c))
print()
print("PAYMENTS")
invs = payments.get("invoices", [])
pending = [i for i in invs if i.get("status") == "pending"]
completed = len([p for p in payments.get("payments", []) if p.get("status") == "completed"])
print("  Invoices:", len(invs), "| Pending:", len(pending), "| Completed:", completed)
print()
print("EMAILS")
outbox = len([f for f in (OUTREACH / "outbox").iterdir() if f.is_file()])
sent = len([f for f in (OUTREACH / "sent").iterdir() if f.is_file()])
print("  Outbox (pending):", outbox)
print("  Sent:", sent)
