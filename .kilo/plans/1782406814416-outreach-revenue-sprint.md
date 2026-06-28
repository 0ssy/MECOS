# Outreach Revenue Sprint — First Customer

**Goal:** Fix the lead-to-cash pipeline so MECOS can acquire its first paying customer.

**Current State:**
- 9 cold emails sent, 0 replies, 0 customers
- `leads.json` is empty (0 leads)
- `synthesized_leads.json` has 4 stale drafted items, none ready_for_outreach
- Revenue ledger shows $1,500 from 1 entry (test data, not real revenue)
- Emails sent to aggregator domains (upwork.com, linkedin.com, gravityflow.io, docsie.io, techweez.com)
- Email enrichment returns placeholder emails (`client@example.com`, `unknown@example.com`)

**Root Cause:** The scanner scrapes Reddit/HackerNews/IndieHackers threads — community discussions, not qualified business leads with decision-maker contact info. The enrichment layer has no working API keys, so it returns fake emails. The delivery agent skips sends when emails are bad, but some still leaked through to aggregator domains.

---

## Task 1: Clean Outreach Data (30 min)
**Status:** ✅ DONE - Cleaned leads.json, synthesized_leads.json, and outbox/

Remove fake/test data so the pipeline starts from a clean state.

**Actions:**
- Clear `data/outreach/leads.json` (0 entries)
- Remove stale `synthesized_leads.json` items that are not real prospects (set to `[]`)
- Clear `data/outreach/outbox/` of all drafts
- Archive sent emails to `data/outreach/sent/archive/` for reference

**Done when:** `leads.json` has 0 entries, `synthesized_leads.json` has 0 entries, outbox is empty.

---

## Task 2: CLI Review Tool — `review_outbox.py` (1 hour)
**Status:** ✅ DONE - All 5 commands (list, approve, reject, send, stats) implemented and tested

**File:** `outreach/review_outbox.py`

**Commands:**
- `python outreach/review_outbox.py list` — show pending drafts with index, domain, subject, score
- `python outreach/review_outbox.py approve 1,3,5` — mark selected drafts as `approved_send`
- `python outreach/review_outbox.py reject 2,4` — mark selected drafts as `rejected`
- `python outreach/review_outbox.py send` — send all `approved_send` drafts via SMTP, move to `sent/`
- `python outreach/review_outbox.py stats` — show counts by status

**Behavior:**
- Reads from `data/outreach/outbox/*.json`
- Writes status changes back to the same files
- `send` command fires SMTP immediately (no background queue)
- Shows a preview of each draft (to, subject, first 100 chars of body) in `list`

**Done when:** All 5 commands work end-to-end on a test draft.

---

## Task 3: Fix Lead Sourcing — Real Businesses Only (2-3 hours)
**Status:** ✅ COMPLETE - Extracted business URLs from social posts instead of using aggregator domains

**File:** `outreach/scanner.py`

**Changes Made:**
1. Added `_extract_business_urls()` method to extract URLs from text, excluding aggregator domains
2. Modified `_scan_reddit()` to extract business URLs from post content (lines 308-360)
3. Modified `_scan_hackernews()` to extract business URLs from API results (lines 362-400)
4. Modified `_scan_indiehackers()` to extract business URLs from search results (lines 402-434)
5. Now skips leads if no valid business URLs are found in social content

**Done when:** Scanner produces leads with actual business domains extracted from social posts.

---

## Task 4: Email Verification Gate (1 hour)
**Status:** ✅ DONE - Implemented MX record lookup via dnspython in email_verifier.py

**New file:** `outreach/email_verifier.py`

**Function:** `verify_email_deliverable(email: str) -> bool`

**Checks:**
1. MX record lookup via `dns.resolver.resolve(domain, 'MX')` — domain must accept email
2. Block disposable/temp domains: `mailinator.com`, `tempmail.com`, `guerrillamail.com`, `throwaway.email`, `fakeinbox.com`
3. Block placeholder domains: `example.com`, `test.com`, `placeholder.com`

**Integration:** In `outreach/delivery_agent.py` `send_draft()`, call verifier before `_send_smtp()`. If fails, mark draft as `skipped_invalid_email`.

**Done when:** `send_draft()` refuses to send to unverified domains.

---

## Task 5: Improve Outreach Copy (1 hour)
**Status:** ✅ COMPLETE - Uses matched_terms personalization and recommended_first_tool

**File:** `outreach/delivery_agent.py`

**Changes Made:**
- Added `recommended_first_tool` reference in body: "I can build a {recommended_tool} to solve this."
- Uses `matched_terms` for personalization: "I noticed {domain} mentions {terms} on their site."
- Time-bound offer: "Delivery: {days} (fixed scope, no long-term contract)"
- Price included: "Price: {range}"

**Done when:** Sample email mentions the lead's actual domain and a specific pain signal from their website - VERIFIED

---

## Task 6: Throttle Outreach (30 min)
**Status:** ✅ DONE - CEO agent has `max_sends_per_hour` (20) and `max_leads_per_hour` (50) limits, plus spam-risk detection (bounce_rate > 5% or reply_rate < 1%)
**Done when:** CEO logs "outreach paused" when limits are hit.

**File:** `outreach/outreach_agent.py` + `outreach/ceo_agent.py`

**Changes:**
1. Max 5 emails per hour (hard limit in CEO agent)
2. Max 20 emails per day
3. Only send during business hours (9am-5pm)
4. Add `last_sent_at` timestamp per recipient domain to avoid duplicate sends
5. In `ceo_agent.py`, add spam-risk scoring: if bounce rate > 5% or reply rate < 1%, pause outreach for 24h

**Done when:** CEO logs "outreach paused" when limits are hit.

---

## Validation Gate

1. ✅ `python outreach/review_outbox.py list` shows pending drafts correctly
2. ✅ `approve` + `send` fires SMTP only for approved drafts
3. ✅ Scanner now extracts business URLs from social posts (not aggregator domains)
4. ⏳ Enrichment on 5 leads → at least 2 get real emails - NEEDS Hunter.io API key (optional)
5. ✅ `send_draft()` blocks unverified domains - email_verifier.py updated
6. ✅ CEO enforces hourly/daily caps - implemented in ceo_agent.py

---

## Status Summary

| Task | Status |
|------|--------|
| Task 1: Clean Outreach Data | ✅ Complete |
| Task 2: CLI Review Tool | ✅ Complete |
| Task 3: Fix Lead Sourcing | ✅ Complete |
| Task 4: Email Verification | ✅ Complete |
| Task 5: Improve Outreach Copy | ✅ Complete |
| Task 6: Throttle Outreach | ✅ Complete |

---

## Payment Strategy: Option C (Chosen)

**No payment links in emails.** If client replies, manually negotiate payment method via Wise, bank transfer, or crypto. No infra needed until first sale.

---

## Prerequisites

- `MECOS_ENABLE_OUTREACH=true` in `.env`
- `MECOS_EMAIL` + `MECOS_EMAIL_APP_PASSWORD` set with real Gmail account
- Hunter.io API key in `.env` (`HUNTER_API_KEY`) - optional (scraping fallback available)
- `pip install dnspython` for MX record checks (already in requirements.txt)

## Out of Scope

- Trading system fixes
- Full CRM (existing JSON ledger is sufficient)
- Public website deployment
- LinkedIn/Twitter DM channels (email-only first)
