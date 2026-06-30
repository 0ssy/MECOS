# Email Send Flow Fix Plan

## Problem
Emails are not being sent after approval. The smoke test shows "0 sent (manual review)" because the approval flow never triggers SMTP delivery.

## Root Cause Analysis
The code has three status concepts that never connect:
1. **Local outbox status** - `"pending_review"`, `"approved_send"`, `"skipped_bad_lead"`
2. **Twenty CRM status** - `"approved"` in GraphQL queries
3. **Send requirement** - `send_draft` only accepts `"approved_send"` status

## Issues

### Issue 1: Status Mismatch in CEO Approval
**File:** outreach/ceo_agent.py:466
- Sets `draft["status"] = "pending_review"` for auto_send
- Should set `"approved_send"` to trigger `_run_approval_cycle` sending

**Fix:** Change to `"approved_send"` to match `send_draft` requirement.

### Issue 2: Missing Send Trigger in `_run_approval_cycle`
**File:** outreach/outreach_agent.py:613-656
- Queries Twenty CRM for drafts with status `"approved"`
- Never calls `send_draft(draft)` to actually send emails
- Only logs stats, doesn't execute sends

**Fix:** After fetching approved drafts, iterate and call `send_draft(draft)`.

### Issue 3: Status Mismatch in Twenty CRM Bridge
**File:** outreach/twenty/twenty_bridge.py:328
- Queries GraphQL for `status == "approved"`
- Should query for `"approved_send"` to match codebase

**Fix:** Update GraphQL query filter to `"approved_send"`.

### Issue 4: Unused Variable
**File:** outreach/outreach_agent.py:430
- `total_sent = 0` assigned but never incremented
- Remove dead code or repurpose for actual send tracking.

## Decision Required
**Should drafts auto-send or require manual review?**

Current behavior: "0 sent (manual review)" - emails require manual action in Twenty CRM UI.

If auto-send is desired:
- Use `"approved_send"` status throughout
- Call `send_draft` after approval
- Track send success/failure in Twenty CRM

If manual review is required:
- Keep current flow but document the manual step
- Update smoke test expectations

## Tasks (Option A: Auto-send mode)

1. **ceo_agent.py:466** - Change `"pending_review"` to `"approved_send"` for auto_send
2. **ceo_agent.py:468** - Add `send_draft` call and track sends
3. **twenty_bridge.py:328** - Change query from `"approved"` to `"approved_send"`
4. **outreach_agent.py:430** - Remove or repurpose `total_sent`
5. **delivery_agent.py:127** - Update sent draft status in Twenty CRM after SMTP send

## Data Flow After Fix

```
1. Lead discovered -> scanner.leads
2. Lead briefed -> synthesizer.briefs
3. Draft created -> delivery_agent.outbox (status: "pending_review")
4. CEO approves -> status changed to "approved_send"
5. _run_approval_cycle -> send_draft() called
6. SMTP sends -> delivery_agent.sent, status: "sent"
7. TwentyBridge.sync_draft -> status synced to CRM
```

## Validation
- Smoke test shows `drafts_sent > 0`
- Files in `data/outreach/sent/` directory
- Email arrives at target address (use test email like `test@example.com`)

## Risks
- **Spam risk**: Auto-send without proper validation could hit bad addresses
- **Rate limits**: No send throttling currently in place
- **Duplicate sends**: Need to check `scanner.scanned_urls` during intel expansion