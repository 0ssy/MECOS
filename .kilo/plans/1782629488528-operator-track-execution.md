# Operator Track Execution Plan

## Goal
Close 3 paying local-business clients in 60 days using the cleaned outreach pipeline.

## Locked Decisions
- **Sequencing**: Operator track first (Month 1-2); Product A extraction only after 3 deals closed
- **Volume**: 50 emails/day
- **Demo reports**: Post-reply only (attached when recipient replies with demo keyword)
- **Execution model**: Dedicated outreach scheduler, daily batch at 8am, decoupled from cognition loop
- **Send strategy**: CEO-approves with tiered rules (auto-send high-confidence, flag low-confidence, reject bad leads)

## CEO Approval Rules
| Rule | Auto-Send | Flag for Review | Reject |
|------|-----------|-----------------|--------|
| email_confidence | `high` | `low` | placeholder/example |
| local_business_score | >= 5 | 3-4 | < 3 |
| enterprise_penalty | <= 1 | 2 | > 2 |
| recipient_domain | not in AGGREGATOR_DOMAINS | — | in AGGREGATOR_DOMAINS |
| body length | >= 200 chars | — | < 200 chars |
| email source | website_scrape / api | pattern_guess | — |

**Circuit breakers (existing, keep active):**
- bounce_rate > 5% or reply_rate < 1% with total_sent >= 10 → pause outreach
- 3 consecutive send failures → pause outreach
- Max 20 sends/hour, 50 sends/day cap

## Implementation Tasks

### 1. Outreach Scheduler (new module)
**File**: `outreach/scheduler.py`
- Daily batch trigger at configurable time (default 8am)
- Decoupled from cognition loop; runs as independent asyncio task
- Calls `outreach_agent.run_cycle()` in batch mode, processing up to 50 emails per day
- Respects existing CEO throttling (max 20/hr = ~2.5hrs for 50 emails)
- Logs daily metrics: emails drafted, auto-sent, flagged, rejected, skipped_icp

### 2. CEO Auto-Approval Engine (extend `ceo_agent.py`)
**File**: `ceo_agent.py`
- Add `approve_drafts()` method that applies the tiered rules above
- Returns three lists: `auto_send`, `flag_review`, `reject`
- `auto_send` drafts transition to `pending_send` and are sent via SMTP within the batch
- `flag_review` drafts stay in `pending_review` for human review next day
- `reject` drafts get `skipped_bad_lead` status and are archived
- Persist daily approval report to `data/outreach/ceo_approvals.jsonl`

### 3. Daily Metrics Tracker (new module)
**File**: `outreach/metrics.py`
- Track: conversations_started, demos_delivered, deals_closed, blocker_rate, avg_deal_size
- Read from `revenue_ledger.json` and `replies.json`
- Write daily summary to `data/outreach/daily_metrics.jsonl`
- Expose `get_weekly_summary()` for CEO health checks

### 4. Demo Report Reply Integration (extend `reply_monitor.py`)
**File**: `outreach/reply_monitor.py`
- When `demo_keyword_detected` is true, call `DemoReportGenerator.generate(lead_url)`
- Attach generated HTML report to demo reply email
- Log demo deliveries to `data/outreach/demos/delivered.jsonl`

### 5. Main Loop Integration (extend `main.py`)
**File**: `main.py`
- Start outreach scheduler as background task after outreach_agent.startup()
- CEO agent already supervises outreach; ensure scheduler runs under CEO circuit breakers
- Add CLI flag `--outreach-only` to run cognition loop without trading for faster outreach cycles

## Data Flow
```
Daily 8am batch
  → outreach_agent.run_cycle() [scan → enrich → synth → draft]
    → ceo_agent.approve_drafts() [apply tiered rules]
      → auto_send: SMTP send (max 20/hr)
      → flag_review: queue for next-day human review
      → reject: archive with reason
  → metrics.py records daily totals
  → reply_monitor polls for replies (every cycle)
    → demo_keyword → DemoReportGenerator → send HTML report
```

## Validation Criteria
- Scanner: zero drafts to aggregator/enterprise domains (verify via `skipped_leads.jsonl`)
- Pipeline: 80%+ of emails to verified local-business inboxes
- Operator: 3 paying clients in 60 days
- Unit economics: outreach cost (API + tools) < 5% of deal value

## Risks & Mitigations
- **SMTP deliverability degrades at scale**: warmup domain or SendGrid/Mailgun if bounce rate spikes
- **CEO approval bottleneck**: tiered rules reduce manual review to ~10-20/day; if flagged queue grows, loosen threshold from score 3 to 4
- **Searcher drift to non-local domains**: hard domain blocklists + scoring thresholds already in scanner
- **Product tracks remain inactive until operator track proves demand**: explicit gating in sequencing decision

## Out of Scope
- Product A extraction (`service_outreach/` package) — starts after 3 deals closed
- Product B (hosted service) and Product C (vertical SaaS) — gated on demand proof from Product A
- Reply monitor SMTP delegation — plan for agency-supplied IMAP/SMTP or shared mail relay in future phase

## Next Agent Should
1. Create `outreach/scheduler.py` with daily batch trigger and CEO circuit breaker integration
2. Extend `ceo_agent.py` with `approve_drafts()` implementing the tiered rules table
3. Create `outreach/metrics.py` with daily/weekly tracking
4. Wire scheduler into `main.py` as background task
5. Test end-to-end: scan → enrich → synth → draft → CEO approve → send → reply → demo report
