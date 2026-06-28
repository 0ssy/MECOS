# Outreach Pipeline Blockers Fix

## Goal
Resolve blockers preventing outreach pipeline from generating real business leads and sending valid emails.

## Root Causes

1. **Configuration mismatch**: `.env.example` sets `DEFAULT_MODEL=llama3` while `config.py` defaults to `llama3.2:3b`
2. **Incomplete email verification**: `email_verifier.py` uses `socket.getaddrinfo` (A record only) instead of MX record lookup as documented
3. **Stale aggregator-domain leads**: `leads.json` and `synthesized_leads.json` contain leads from upwork.com, reddit.com, docparsemagic.com (aggregator domains)
4. **Missing dependency**: `dnspython` not in `requirements.txt` for MX verification

## Tasks

### Task 1: Fix .env.example Model Specification
**File:** `.env.example` line 8
**Change:** `DEFAULT_MODEL=llama3` → `DEFAULT_MODEL=llama3.2:3b`
**Done when:** `.env.example` matches `config.py` default

### Task 2: Implement MX Record Verification
**File:** `outreach/email_verifier.py`
**Actions:**
1. Add `import dns.resolver` at top
2. Replace lines 43-47 with MX lookup logic:
   ```python
   try:
       mx_records = dns.resolver.resolve(domain, 'MX')
       return len(mx_records) > 0
   except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
     return False
   ```

### Task 3: Add dnspython to requirements.txt
**File:** `requirements.txt`
**Add:** `dnspython>=2.0.0`
**Done when:** `pip install dnspython` installs successfully

### Task 4: Clean Stale Lead Data
**File:** `data/outreach/leads.json`
**Action:** Set to `[]` (empty array) - removes all existing leads including aggregator domains

**File:** `data/outreach/synthesized_leads.json`
**Action:** Set to `[]` (empty array) - removes stale briefs

**File:** `data/outreach/outbox/`
**Action:** Remove all draft files

### Task 5: Verify Aggregator Domain Blocking in Scanner
**File:** `outreach/scanner.py` lines 55-82
**Check:** `AGGREGATOR_DOMAINS` set includes: upwork.com, reddit.com, hn.algolia.com, indiehackers.com, docparsemagic.com, techweez.com, docsie.io
**Status:** Already correctly configured - stale data was the issue

## Validation
1. ✅ `python outreach/review_outbox.py list` → "No drafts in outbox"
2. ✅ `outreach/email_verifier.verify_email_deliverable("test@gmail.com")` returns True (valid MX)
3. ✅ `outreach/email_verifier.verify_email_deliverable("test@example.com")` returns False (placeholder blocked)
4. ✅ `outreach/email_verifier.verify_email_deliverable("test@upwork.com")` returns False (aggregator blocked)
5. ✅ All 43 tests pass

## Status: ✅ COMPLETE
- `.env.example` model name fixed ✅
- `email_verifier.py` MX lookup implemented ✅
- `requirements.txt` has dnspython ✅
- `leads.json`, `synthesized_leads.json`, `outbox/` all cleared ✅
- Ollama must have `llama3.2:3b` model pulled (`ollama pull llama3.2:3b`)
- SearXNG Docker required at `localhost:8888`
- Email sending requires `MECOS_EMAIL` and `MECOS_EMAIL_APP_PASSWORD` in `.env`