# Twenty CRM Integration for MECOS Outreach

## Goal
Integrate Twenty CRM as MECOS's persistent data backend to transform MECOS from autonomous-only to human-in-the-loop outreach, enabling scalable client acquisition, payment processing, and company growth.

## Integration Tasks

### A. Twenty Objects
- [x] `outreach/twenty/schema.py` - Python schema definitions for all four objects
- [x] `outreach/twenty/setup_twenty.py` - Script to create objects/fields in Twenty via GraphQL
  - `mecosLead` — url, domain, signals, totalScore, contacts, status, source, discoveredAt
  - `mecosLeadBrief` — lead (relation), painPoints, persona, suggestedPitch, valueProposition, recommendedPackage, recommendedFirstTool, originalSignals, matchedTerms, status, synthesizedAt
  - `mecosEmailDraft` — leadBrief (relation), draftType, subject, body, status, recipientEmail, paymentLink, invoiceId, createdAt, sentAt
  - `mecosPayment` — lead (relation), amount, currencyCode, source, status, invoiceId, paypalOrderId, paypalCaptureId, clientEmail, description, createdAt

### B. MECOS Bridge
- [x] `outreach/twenty/twenty_bridge.py` - GraphQL client with auth, error handling
  - `sync_lead()`, `sync_brief()`, `sync_draft()`, `sync_payment()` — upsert by natural key
  - `get_approved_drafts()` — query drafts with status=approved
  - `get_leads_by_status()` — query leads by status
  - `mark_draft_sent()` — update draft status to sent
- [x] `outreach/twenty/models.py` - Payload builders mapping MECOS dicts to Twenty GraphQL inputs
  - Fixed: removed `contacts` from brief payload (not supported in Twenty mutation input)
- [x] `outreach/twenty/__init__.py` - Package exports

### C. OutreachAgent Modifications
- [x] `TWENTY_CRM_ENABLED` flag in `config.py`
- [x] Auto-sync leads, briefs, drafts, payments to Twenty during pipeline cycles
- [x] `_run_approval_cycle()` - reads approved drafts from Twenty, sends via DeliveryAgent, marks sent
- [ ] Payment webhook updates lead status in Twenty (deferred until payment flow is live)

### D. Webhooks
- [x] `/api/payments/webhook` for PayPal (existing, in `dashboard/server.py`)
- [x] `/api/emails/send-approved` for UI approval (new, in `dashboard/server.py`)
- [x] `/api/twenty/leads` and `/api/twenty/briefs` dashboard endpoints
- [x] `docker-compose-twenty.yml` for self-hosted Twenty instance
- [x] `.env.example` updated with Twenty CRM variables

## Status
- ✅ Twenty instance running at `localhost:3000`
- ✅ 4 custom objects created manually in Twenty UI
- ✅ Bridge tested and working: all sync operations (lead, brief, draft, payment) successful
- ⏳ Payment webhook integration deferred until payment flow is live
- ✅ API key updated in `.env`, `.env.twenty`, `.env.example`

---

## Implementation Status Summary

All core integration is complete. Remaining work:
1. Payment webhook → lead status update in Twenty (deferred - no funds for live payments yet)
2. Testing with real outreach data flow
