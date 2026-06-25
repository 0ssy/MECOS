# Plan: Wire Email Enrichment Into Lead Discovery Pipeline

## Goal
Ensure every newly discovered lead is enriched with email addresses immediately after discovery, before it becomes available for synthesis/drafting.

## Root Cause
`EmailEnricher` runs in a standalone cycle (`_run_enrich_cycle`, cycle % 4 == 3) that fires independently from the scan cycle (cycle % 3 == 1). Leads discovered in a scan cycle sit in `scanner.leads` without emails until a later separate enrichment cycle runs, and synthesis (`cycle % 5 == 2`) can pick them up unenriched in between.

Current state:
- 16 leads in `data/outreach/leads.json`, 0 with emails
- 300 leads in `data/outreach/synthesized_leads.json`, 0 with emails

## Changes

### 1. `outreach/outreach_agent.py` — `_run_scan_cycle()`
After collecting `all_new = leads + social_leads`, call `self.email_enricher.enrich_batch(all_new)` BEFORE intel adapter scoring. This ensures emails are on leads at discovery time.

Replace:
```python
all_new = leads + social_leads
scored = self.intel_adapter.enrich_batch(all_new)
```

With:
```python
all_new = leads + social_leads

if all_new:
    enriched_new = await self.email_enricher.enrich_batch(all_new)
    for lead in enriched_new:
        if lead.get("contacts", {}).get("emails"):
            existing = next((l for l in self.scanner.leads if l.get("url") == lead.get("url")), None)
            if existing:
                existing["contacts"] = lead["contacts"]
                existing["contacts"]["email_source"] = lead["contacts"].get("email_source")
                existing["contacts"]["email_confidence"] = lead["contacts"].get("email_confidence")
            else:
                self.scanner.leads.append(lead)

scored = self.intel_adapter.enrich_batch(all_new)
```

### 2. `outreach/outreach_agent.py` — `_run_enrich_cycle()`
Convert from standalone batch to fallback sweep. Only process leads that somehow still lack emails after scan-cycle enrichment.

Change:
```python
batch = unenriched[:15]
```
To:
```python
batch = unenriched[:10]
```
(Reduced since most leads are now enriched at discovery time.)

### 3. New file `scripts/backfill_emails.py`
One-time backfill of existing stale leads (300 synthesized + 16 scanner leads) so they can enter the pipeline immediately.

```python
import json
import asyncio
from pathlib import Path
from outreach.email_enricher import EmailEnricher

async def main():
    enricher = EmailEnricher()
    data_dir = Path("data/outreach")

    # Backfill synthesized_leads.json
    synth_path = data_dir / "synthesized_leads.json"
    if synth_path.exists():
        leads = json.loads(synth_path.read_text())
        unenriched = [l for l in leads if not l.get("contacts", {}).get("emails")]
        print(f"Backfilling {len(unenriched)}/{len(leads)} synthesized leads...")
        enriched = await enricher.enrich_batch(unenriched[:50])
        update_map = {l["url"]: l for l in enriched if l.get("contacts", {}).get("emails")}
        updated = 0
        for i, lead in enumerate(leads):
            if lead.get("url") in update_map:
                leads[i]["contacts"] = update_map[lead["url"]]["contacts"]
                updated += 1
        synth_path.write_text(json.dumps(leads, default=str, indent=2))
        print(f"Updated {updated} synthesized leads with emails")

    # Backfill leads.json
    leads_path = data_dir / "leads.json"
    if leads_path.exists():
        leads = json.loads(leads_path.read_text())
        unenriched = [l for l in leads if not l.get("contacts", {}).get("emails")]
        print(f"Backfilling {len(unenriched)}/{len(leads)} scanner leads...")
        enriched = await enricher.enrich_batch(unenriched)
        update_map = {l["url"]: l for l in enriched if l.get("contacts", {}).get("emails")}
        updated = 0
        for i, lead in enumerate(leads):
            if lead.get("url") in update_map:
                leads[i]["contacts"] = update_map[lead["url"]]["contacts"]
                updated += 1
        leads_path.write_text(json.dumps(leads, default=str, indent=2))
        print(f"Updated {updated} scanner leads with emails")

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. `outreach/scanner.py` — No structural changes needed
`scan_url()` and social scan methods already call `_extract_contact_hints()` which finds emails in page text. The enrichment layer now supplements this with website scraping and API lookups. No scanner changes required.

## Execution Order

1. Apply changes 1 and 2 (`outreach_agent.py`)
2. Create `scripts/backfill_emails.py`
3. Run backfill script: `python scripts/backfill_emails.py`
4. Restart MECOS
5. Validate

## Validation

1. **Backfill succeeds**: `python scripts/backfill_emails.py` shows >0 emails found and written
2. **Logs show enrichment at scan time**: After restart, new scan cycles log `Enriched <domain>: <email> (website_scrape)` or similar
3. **Synthesis sees enriched leads**: `synthesized_leads.json` entries have `contacts.emails` populated
4. **Drafts no longer skip**: `pending_review` count drops because `unknown@example.com` skip condition is no longer hit
5. **Fallback still works**: Intentionally clear emails on one lead, run one cycle, verify `_run_enrich_cycle()` catches it (logs: `all_leads_have_emails` when none missing)
6. **No duplicate sends**: Run 3+ cycles, verify no duplicate `contacted` status resets

## Risks / Mitigations

| Risk | Mitigation |
|------|-----------|
| Enrichment HTTP timeouts slow scan cycle | Per-lead try/except already in `enrich_batch`; failures are isolated, scan continues |
| Pattern-guessed emails (low confidence) generate false sends | Draft cycle in `outreach_agent.py:206` skips `unknown@example.com`; add same guard for low-confidence if needed |
| Rate limits on API enrichment | Only fires when API keys are set; Hunter.io free tier = 25 req/month; no keys = website scrape only |
| Duplicate email dedup | `_scrape_website` uses `set()`; API results append once per strategy |

## Out of Scope

- SMTP email deliverability verification (bounce detection, MX record checks)
- New lead discovery sources
- Changing cycle scheduling intervals
- CEO-level enrichment quality metrics/dashboards
