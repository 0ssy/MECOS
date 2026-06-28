# Multi-Track Revenue Plan: Agency + Productized Outreach Pipeline

## Goal
Run two revenue tracks in parallel: (1) an automation agency selling to local service businesses, and (2) a productized outreach pipeline that can be sold as a self-hosted toolkit, hosted service, or vertical SaaS.

## Vertical
Local service businesses (HVAC, plumbing, auto repair, dental/medical, small professional services).

## Foundation Fix (unblocks all tracks)
Current scanner generates 312 drafts to enterprise/aggregator domains (microsoft.com, marketscreener.com). Fix before any revenue work.

### 1. Scanner ICP Refactor
**File:** `outreach/scanner.py`
- Add `LOCAL_BUSINESS_SIGNALS` scoring boost: address/phone/schedule pages, "family owned", "since 19XX", serving [city], small-team language
- Add `ENTERPRISE_BLOCKS` scoring penalty: Fortune/Inc 5000, /enterprise paths, >500 employees inferred, /solutions, /platform
- Narrow SearXNG queries to local-service pain:
  - "HVAC scheduling spreadsheet hell"
  - "auto repair shop manual invoicing"
  - "dental office patient intake paper forms"
  - "plumbing dispatch spreadsheet"
  - "local business appointment booking pain"
- Add `local_business_score` and `enterprise_penalty` fields to lead output
- Enable existing `AGGREGATOR_DOMAINS` blocklist (already defined, just enforce at scan time)

### 2. Lead Quality Gate
**File:** `outreach/outreach_agent.py:_run_draft_cycle` (around line 268)
- Skip drafts where `local_business_score < 3` or `enterprise_penalty > 2`
- Log skipped leads with reason to `data/outreach/skipped_leads.jsonl`

### 3. Optional Demo Report Generator
**New file:** `outreach/demo_report.py`
- Lightweight tool: takes a URL → runs mini-audit → generates personalized HTML report
- Output: "Automation Opportunity Report" with detected pain points, recommended automation, estimated savings, CTA
- Config flag `MECOS_GENERATE_DEMO_REPORT=true/false` per outreach run
- Used in outreach emails as: "I ran a quick audit on [Business] — here's what I found"

---

## Track 1 — Operator (Agency)

### Funnel
1. Outreach email sent → personalized with scanner-discovered pain point
2. Reply → booked call → scope → PayPal invoice → delivery
3. Demo report attached if `MECOS_GENERATE_DEMO_REPORT=true`
4. Follow-up at 3d/7d/14d (existing `followup_engine.py`)

### Pricing
Fixed scope: $500–$1,500, 3–5 day delivery, no long-term contract.

### Metrics
- Conversations started/week
- Demos delivered/week
- Deals closed/week
- Avg deal size
- Blocker rate

---

## Track 2 — Product A (Self-Hosted Toolkit)

### Scope
Extract `outreach/` pipeline into `service_outreach/` clean importable sub-package:
- `scanner.py`, `enricher.py`, `delivery.py`, `replies.py`, `ledger.py`, `crm_twenty.py`, `config.py`
- MECOS internal code imports from `service_outreach`
- Product tracks import the same package
- CLI wrapper: `service-outreach scan`, `service-outreach enrich`, `service-outreach send`, `service-outreach audit <url>`
- Docker Compose for one-command deployment

### Monetization
$997 one-time or $97/month per agency seat. Includes demo report generator as lead magnet.

---

## Track 3 — Product B (Hosted Service)

### Scope
- Hosted MECOS instance (single-tenant per agency)
- Agencies upload leads (CSV) or connect Google Maps scrape
- Web UI: FastAPI backend + minimal frontend
- Agencies review drafts, click SEND from their own SMTP
- Returns: verified emails, drafted sequences, reply tracking, demo reports

### Monetization
$500–$2,000/month per agency, tiered by lead volume.

---

## Track 4 — Product C (Vertical SaaS)

### Scope
- End-customer signs up on landing page
- Onboarding: connect Google Business Profile OR upload customer lists
- Fully autonomous pipeline: find → verify → enrich → draft → send → reply → book demo
- Customer dashboard: leads, conversations, booked demos, revenue
- Billing: Stripe recurring

### Monetization
$299–$999/month per local business.

---

## Coordination
CEO agent (`ceo_agent.py`) oversees all tracks: circuit breakers, spam-risk monitoring, revenue ledger oversight, outreach throttling. Multi-track execution delegated to CEO; no single-person constraint.

## Evolution Path
1. Fix scanner ICP + extract `service_outreach` + build demo report generator
2. Month 1-2: Operator track — close 3 deals, validate local vertical
3. Month 2-3: Product A — launch toolkit + demo generator
4. Month 3-5: Product B — hosted service for agencies
5. Month 6+: Product C — vertical SaaS (only if demand proven from A/B)

## Validation
- Scanner: zero drafts to aggregator/enterprise domains
- Pipeline: 80%+ of emails to verified local-business inboxes
- Operator: 3 paying clients in 60 days
- Product A: 1 paying agency within 90 days of launch
- Unit economics: outreach cost (API + tools) < 5% of deal value

## Risks
- Scanner drift to non-local domains → hard domain blocklists + scoring thresholds (immediate)
- Gmail SMTP deliverability degrades at scale → warmup domain or SendGrid/Mailgun for product tracks
- CEO agent handles multi-track coordination, but product tracks remain inactive until operator track proves demand
