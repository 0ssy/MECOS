import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import asyncio
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
        enriched = await enricher.enrich_batch(unenriched[:5])
        update_map = {l["url"]: l for l in enriched if l.get("contacts", {}).get("emails")}
        updated = 0
        for i, lead in enumerate(leads):
            if lead.get("url") in update_map:
                leads[i]["contacts"] = update_map[lead["url"]]["contacts"]
                updated += 1
        synth_path.write_text(json.dumps(leads, default=str, indent=2))
        print(f"Updated {updated} synthesized leads with emails")
    else:
        print("synthesized_leads.json not found, skipping")

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
    else:
        print("leads.json not found, skipping")


if __name__ == "__main__":
    asyncio.run(main())
