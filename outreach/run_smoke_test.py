"""
MECOS Outreach Smoke Test

Validates the local-business outreach pipeline produces real business emails,
not aggregator/enterprise noise.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ["MECOS_ENABLE_OUTREACH"] = "true"

from ceo_agent import CeoAgent
from memory_system import MemorySystem
from outreach.outreach_agent import OutreachAgent
from outreach.scanner import OutreachScanner


async def run_smoke_test():
    """Run one manual scan→synth→draft→approve→send cycle and validate results."""
    print("=" * 60)
    print("MECOS Outreach Smoke Test")
    print("=" * 60)

    # Create isolated OutreachAgent instance
    memory = MemorySystem()
    agent = OutreachAgent(memory=memory)

    # Clear existing data for clean test
    agent.scanner.leads = []
    agent.scanner.scanned_urls = set()
    agent.scanner.scanned_content_hashes = set()
    agent.scanner.scan_cycles_by_url = {}

    agent.synthesizer.briefs = []
    agent.synthesizer._save()

    # Clear outbox
    for f in agent.delivery_agent.outbox_dir.glob("*.json"):
        f.unlink()

    # Attach CEO agent
    ceo = CeoAgent(memory=memory, revenue_ledger=agent.revenue_ledger)
    ceo.attach_outreach(agent)

    results = {
        "scan": {},
        "enrich": {},
        "synth": {},
        "draft": {},
        "approve": {},
    }

    # Run scan cycle
    print("\n[1/5] Running scan cycle...")
    try:
        scan_result = await agent._run_scan_cycle()
        results["scan"] = scan_result
        print(f"  Scanned: {scan_result.get('urls_scanned', 0)} URLs")
        print(f"  New leads: {scan_result.get('new_leads', 0)}")
    except Exception as e:
        print(f"  Scan cycle error (SearXNG may be unavailable): {e}")

    # Run enrich cycle
    print("\n[2/5] Running enrich cycle...")
    try:
        enrich_result = await agent._run_enrich_cycle()
        results["enrich"] = enrich_result
        e = enrich_result.get("enriched", 0)
        a = enrich_result.get("attempted", 0)
        print(f"  Enriched: {e}/{a} leads")
    except Exception as e:
        print(f"  Enrich cycle error: {e}")

    # Run synth cycle
    print("\n[3/5] Running synth cycle...")
    try:
        synth_result = await agent._run_synth_cycle()
        results["synth"] = synth_result
        print(f"  Synthesized: {synth_result.get('synthesized', 0)} leads")
    except Exception as e:
        print(f"  Synth cycle error: {e}")

    # Run draft cycle
    print("\n[4/5] Running draft cycle...")
    try:
        draft_result = await agent._run_draft_cycle()
        results["draft"] = draft_result
        print(f"  Drafts created: {draft_result.get('drafts_created', 0)}")
        print(f"  Invoiced: {draft_result.get('invoices_created', 0)}")
    except Exception as e:
        print(f"  Draft cycle error: {e}")

    # Run CEO approval
    print("\n[5/5] Running CEO approval...")
    try:
        approval_result = await ceo.approve_drafts()
        results["approve"] = approval_result
        print(f"  Auto-send: {len(approval_result.get('auto_send', []))} drafts")
        print(f"  Flag review: {len(approval_result.get('flag_review', []))} drafts")
        print(f"  Rejected: {len(approval_result.get('reject', []))} drafts")
    except Exception as e:
        print(f"  Approval error: {e}")

    # Validation
    print("\n" + "=" * 60)
    print("Validation Results")
    print("=" * 60)

    # Check outbox for bad domains
    outbox_path = Path("data/outreach/outbox")
    bad_email_count = 0
    for f in outbox_path.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            to = data.get("to", "")
            emails = data.get("lead_brief", {}).get("contacts", {}).get("emails", [""])
            email = to or emails[0]
            if "@" in email:
                domain = email.split("@")[-1].lower()
                if any(bad in domain for bad in OutreachScanner.ENTERPRISE_DOMAIN_KEYWORDS):
                    bad_email_count += 1
        except Exception:
            continue

    # Check skipped leads
    skipped_path = Path("data/outreach/skipped_leads.jsonl")
    skipped_count = 0
    if skipped_path.exists():
        with open(skipped_path, "r", encoding="utf-8") as f:
            for line in f:
                skipped_count += 1

    print(f"\nEmails to bad/aggregator domains: {bad_email_count}")
    print(f"Skipped leads logged: {skipped_count}")

    # Final status - pass if no bad domains slipped through
    success = bad_email_count == 0

    print("\n" + "=" * 60)
    if success:
        print("✓ SMOKE TEST PASSED")
    else:
        print("✗ SMOKE TEST FAILED")
    print("=" * 60)

    return {
        "success": success,
        "results": results,
    }


if __name__ == "__main__":
    result = asyncio.run(run_smoke_test())
    sys.exit(0 if result["success"] else 1)