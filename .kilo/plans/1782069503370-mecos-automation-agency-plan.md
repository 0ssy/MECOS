# MECOS Automation Agency Plan

## Goal
Turn MECOS into a web/app automation agency generating $10,000/mo revenue. Profit split 40% ops/hardware, 30% trading reserve, 30% growth/profit, locked at $10k milestone.

## Constraints
- $0 starting capital; no purchased domains; no paid email infrastructure
- Trading **disabled from outreach start** until paper trading shows consistent profits
- Binance/Alpaca keys present in `.env` but **not used for outreach or revenue** until trading is validated
- Everything except trading **must be real** (no stubs, no simulated data for outreach/email/revenue)

## Current State
- Crash fix applied: ChromaDB `EphemeralClient` (was access-violating on persistent DB)
- Outreach module: code complete but **never produced real data**
- SMTP email: configured via `.env` (`MECOS_EMAIL`, `MECOS_EMAIL_APP_PASSWORD`), **not yet tested**
- Dashboard: serving on `:8080`, all zeros
- Scanner: code exists but **has never completed a real scan cycle**

## What Must Be Real (Not Stubbed)
- `outreach/scanner.py` — real web scans via `web_perception` / `browser_automation`
- `outreach/delivery_agent.py` — real SMTP send via Gmail App Password
- `outreach/synthesizer.py` — real LLM-backed lead profiling (Ollama local)
- `outreach/revenue_ledger.py` — real transaction records (even if paper revenue initially)
- `outreach/funnel_builder.py` — real content drafts from case studies
- Dashboard — must reflect real outreach data, not zeros

## What Is Missing / Must Be Fixed

### 1. Outreach Pipeline Activation
**Problem:** Scanner, synthesizer, and delivery_agent exist but have never run in production.
**Fix:**
- Start MECOS and confirm `OutreachAgent.run_cycle()` executes inside the cognition loop
- Verify `data/outreach/leads.json` gets real entries from live URL scans
- Verify `data/outreach/outbox/` gets real draft files
- Verify dashboard `/api/stats` shows non-zero leads/outreach values

### 2. SMTP Email Delivery Test
**Problem:** `delivery_agent.py` has SMTP code but no end-to-end delivery proof.
**Fix:**
- Run a direct test: `delivery_agent.send_draft()` with a test draft to a known inbox
- Confirm Gmail App Password auth succeeds (not just config presence)
- Verify sent mail appears in Gmail Sent folder
- If fails: diagnose Gmail 2FA / App Password / "less secure apps" settings

### 3. Revenue Ledger Initialization
**Problem:** `RevenueLedger` is empty. No transactions recorded.
**Fix:**
- Record first real outreach transaction (even $0 or paper deal) to bootstrap 40/30/30 buckets
- Verify dashboard `/api/revenue` reflects the entry
- Ensure `outbox/` sent items auto-record to ledger

### 4. First Case Study Content
**Problem:** `data/outreach/funnel/case_studies.json` is empty.
**Fix:**
- Add at least one case study entry manually or via first real deal
- Verify `funnel_builder.generate_social_content()` produces posts for Twitter/LinkedIn/Reddit

### 5. Trading Isolation
**Constraint:** No trading until paper trading shows consistent profits.
**Implementation:**
- Keep `TRADING_ENABLED=true` in `.env` (MECOS architecture requires it)
- But **do not record trading P&L into revenue buckets** until consistent profit threshold met
- Outreach revenue path is independent of trading revenue path

## Immediate Execution Steps

### Step 1: Run First Real Outreach Scan
```powershell
cd C:\Users\josep\Downloads\MECOS
.venv\Scripts\python.exe main.py
```
- Watch logs for `Outreach scan:` entries
- Verify `data/outreach/leads.json` populates
- Check dashboard `/api/stats` for non-zero leads

### Step 2: Test SMTP Email Send
- Use `outreach/delivery_agent.py` to send a test email
- Verify delivery to test inbox
- Fix any Gmail auth issues

### Step 3: Bootstrap Revenue
- Record first transaction via `revenue_ledger.record_payment()` or direct JSON
- Verify dashboard reflects it

### Step 4: Add First Case Study
- Populate `data/outreach/funnel/case_studies.json`
- Verify social content generation works

### Step 5: Stability Proof
- Run MECOS for 24h
- Confirm no crashes, outreach cycles repeat, data accumulates

## Risks
- **Gmail send limits**: App Password has daily/hourly caps. High-volume outreach may need batching or alternate SMTP.
- **Lead quality**: Scanner uses keyword matching on public URLs (Reddit, HN, IndieHackers). May need tuning.
- **Revenue attribution**: Paper trading P&L is separate from outreach revenue until trading is validated.

## Out of Scope (for now)
- Real domain purchase / paid email
- MCP server integrations (Notion, Slack, Granola, Zapier) — stubbed
- Sovereign inference / Ollama cleanup
- Model fine-tuning or deployment
