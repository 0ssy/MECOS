# Smoke Test: Validate Local-Business Outreach Pipeline

## Goal
Run one manual `scan→synth→draft→approve→send` cycle and inspect `outbox/` to confirm the pipeline produces real local-business emails, not aggregator/enterprise noise.

## Current State (verified)
- 3 fresh `main.py` processes running with patched scanner/outreach code
- `leads.json`: 18 leads, 0 Microsoft/aggregator domains
- `synthesized_leads.json`: 14 leads, 0 bad domains
- `outbox/`: empty (last 5 bad emails quarantined)
- Scanner hard-blocks `AGGREGATOR_DOMAINS` + `ENTERPRISE_DOMAIN_KEYWORDS` at ingestion
- Synth/draft cycles now remove skipped leads from active pool

## Smoke Test Script
**File**: `outreach/run_smoke_test.py` (new, one-shot)
1. Create isolated `OutreachAgent` instance with `MECOS_ENABLE_OUTREACH=true`
2. Run one full cycle:
   - `_run_scan_cycle()` — scan local business directories + SearXNG
   - `_run_enrich_cycle()` — enrich emails
   - `_run_synth_cycle()` — synthesize briefs
   - `_run_draft_cycle()` — create drafts
3. After draft, call `ceo_agent.approve_drafts()` to auto-send high-confidence leads
4. Log results: drafts created, auto-sent, flagged, rejected, skipped
5. Print domain breakdown of any emails sent to verify no bad domains

## Validation Steps
- Check `data/outreach/outbox/` — confirm all emails go to non-aggregator, non-enterprise domains
- Check `data/outreach/skipped_leads.jsonl` — confirm bad domains are logged with reason
- Check `data/outreach/leads.json` and `data/outreach/synthesized_leads.json` — confirm they stay clean after cycle
- Check dashboard `http://127.0.0.1:8080` — confirm tiles update within 2s

## Risk / Mitigation
- Running against live process may interfere with scheduler state → use isolated `OutreachAgent` instance in script, not the running one
- Scanner may find 0 local leads if queries are too narrow → use same query set as production (`scan_business_directories` + SearXNG)

## Success Criteria
- At least 1 email drafted to a local-business domain (not aggregator/enterprise)
- 0 emails drafted to domains in `AGGREGATOR_DOMAINS` or `ENTERPRISE_DOMAIN_KEYWORDS`
- Dashboard shows updated counts after cycle

## Implementation Summary (completed)
- Fixed `outreach/scheduler.py` - added missing `List` import, made `start()` sync (called without await in main.py)
- Created `outreach/run_smoke_test.py` - smoke test script for validating pipeline
- Fixed `tests/test_agent_reach_phase2.py` - changed test domain from `example.com` (blocked) to `localplumbing.com`
- Fixed `outreach_agent.py` `_run_enrich_cycle()` - now properly updates leads with enriched contact info
- All 11 tests passing
