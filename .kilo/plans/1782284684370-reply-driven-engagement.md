# MECOS Reply-Driven Engagement Plan

## Goal
Transform cold email outreach into reply-driven conversations with automated demo delivery and follow-up sequences.

## Current State
- ✓ VSL pages generated (13 total) with referral rewards ($50 credit + 10% off + 30 days extension)
- ✓ Cold emails sent (9 total) with "Reply 'DEMO'" CTA
- ✗ No IMAP reply polling
- ✗ No DEMO keyword detection
- ✗ No automated demo response

## Decisions Resolved
1. Static demo pages over Loom API (uses existing VSL infrastructure)
2. Email threading via In-Reply-To headers (imported from OpenOutreach)

## Implementation Tasks

### Task 1: Reply Monitor Agent (`outreach/reply_monitor.py`)
- Poll IMAP inbox via existing `mecos/email_ingester.py`
- Match replies to sent emails using subject + sender domain
- Detect "DEMO" keyword in body (case-insensitive)
- Store reply events in `data/outreach/replies.json`

### Task 2: Demo Delivery Bot (`outreach/demo_deliverer.py`)
- Reuse `funnel_builder.generate_demo_project_brief()`
- Create `data/outreach/demos/` folder for demo pages
- Send reply email with demo link + referral code
- Include "DEMO" response handling

### Task 3: Follow-up Engine (`outreach/followup_engine.py`)
- Track sent emails in `data/outreach/sent/`
- Schedule 3d/7d/14d follow-ups using draft `outreach/delivery_agent.py:81`
- Thread follow-ups using In-Reply-To from `openoutreach/emails/sender.py`
- Skip if reply received (check replies.json)

### Task 4: Integration (`main.py`)
- Add `_run_reply_check_cycle()` to `outreach_agent.py` after line 194
- Add `_run_followup_cycle()` every 15 cycles  
- Call `outreach_agent.check_replies()` and `outreach_agent.send_followups()`
- Use Message-ID header for reply matching (fall back to subject+domain fuzzy matching)

## Data Flow
```
Sent Emails (data/outreach/sent/*.json)
       ↓
IMAP Inbox ←→ Reply Monitor ←→ replies.json
       ↓ (DEMO detected)
Demo Deliverer → demo page + reply email
       ↓
Follow-up Engine (3d/7d/14d)
```

## Risks
- IMAP credentials required (MECOS_EMAIL + MECOS_EMAIL_APP_PASSWORD)
- Follow-ups may trigger spam filters
- No tracking for email opens (static links only)

## Validation
- Unit test: DEMO keyword detection in email body
- Test: Reply from known address creates demo page
- End-to-end: Email reply → demo link within 2 minutes

## Dependencies
- `mecos/email_ingester.py` - IMAP polling already exists
- `openoutreach/emails/sender.py` - In-Reply-To threading support
- `outreach/delivery_agent.py` - Email sending with SMTP