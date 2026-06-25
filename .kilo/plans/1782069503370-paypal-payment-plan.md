# PayPal Payment Integration Plan

## Goal
Add real PayPal payment collection to MECOS outreach pipeline. Clients pay via PayPal; funds tracked in revenue ledger. No business registration required to start.

## Affected Boundaries
- **New module**: `outreach/payments/` (PayPal client, payment ledger, webhook receiver)
- **Extend**: `outreach/outreach_agent.py` (link leads → invoices → payment status)
- **Extend**: `dashboard/server.py` (add `/api/payments`, `/api/invoices/<id>`)
- **Config**: `.env` gets PayPal credentials

## Decisions (resolved)
- **PayPal API**: Orders API (simpler than Invoicing API, no recurring invoices needed)
- **Currency**: USD default for international clients; display KES estimate via cached FX rate
- **Auto-send policy**: Auto-send payment links in email drafts; manual review for Twitter/LinkedIn/Reddit posts
- **Withdrawal path**: PayPal balance → Payoneer/Wise → Kenyan bank/M-Pesa (not built yet, tracked in ledger)
- **Mode**: Sandbox first, live later (`PAYPAL_MODE=sandbox|live`)

## Data Model
```
payments/paypal_client.py
  - PayPalClient.create_order(invoice_id, amount, currency="USD") → PayPal order ID + checkout URL
  - PayPalClient.capture_order(paypal_order_id) → payment status + capture ID
  - Optional: PayPalClient.get_order(paypal_order_id) for status polling

payments/payment_ledger.py
  - Extends outreach/revenue_ledger.py
  - Fields: payment_id, invoice_id, lead_id, paypal_order_id, paypal_capture_id, amount, currency, status (pending/completed/refunded/failed), created_at, captured_at, webhook_received
  - Idempotent: duplicate webhook → no double-credit

payments/webhooks.py
  - POST /webhooks/paypal
  - Verifies PayPal webhook signature
  - On PAYMENT.CAPTURE.COMPLETED: update payment_ledger + revenue_ledger (40/30/30 split)
  - On PAYMENT.CAPTURE.DENIED/REFUNDED: update status only

outreach/outreach_agent.py
  - After draft creation: if email type + has contact email → create invoice, attach PayPal link to draft
  - After webhook confirms payment: auto-mark lead as `contacted` / deal as `won`
```

## Env Variables
```env
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_MODE=sandbox
PAYPAL_RETURN_URL=http://localhost:8080/payment/success
PAYPAL_CANCEL_URL=http://localhost:8080/payment/cancel
```

## Implementation Steps (ordered)
1. Create `outreach/payments/__init__.py`
2. Create `outreach/payments/paypal_client.py` — Orders API wrapper
3. Create `outreach/payments/payment_ledger.py` — extends RevenueLedger
4. Create `outreach/payments/webhooks.py` — Flask/fastapi route or bare HTTP handler
5. Update `outreach/outreach_agent.py` — create invoice + attach link on email drafts
6. Update `dashboard/server.py` — `/api/payments`, `/api/invoices/<id>` endpoints
7. Update `.env.example` with PayPal vars
8. Update `config.py` Settings class with PayPal fields

## Webhook Testing
- Use ngrok: `ngrok http 8080`
- PayPal sandbox webhook URL: `https://<ngrok-id>.ngrok.io/webhooks/paypal`
- PayPal sandbox buyer account for test payments

## Failure Modes
- Webhook not received → ledger stays `pending` → cron/poll job checks PayPal API every 15 min for stuck orders
- Duplicate webhook → idempotency key (`paypal_capture_id`) prevents double-credit
- Network error on capture → retry with exponential backoff (3 attempts)
- Currency mismatch → reject or convert at cached rate before creating order

## Validation Steps
1. Create invoice for $100 in sandbox → verify PayPal checkout loads with correct amount
2. Pay with sandbox buyer → verify webhook fires, ledger marks `completed`, revenue buckets update
3. Cancel payment → verify ledger stays `pending`, no buckets credited
4. Duplicate webhook → verify no double credit
5. Dashboard `/api/stats` reflects new revenue in correct 40/30/30 buckets
6. Dashboard `/api/payments` returns invoice list with statuses

## Out of Scope (for now)
- M-Pesa direct integration (add when local client base grows)
- Crypto/USDT payments
- Recurring subscriptions
- Payout automation to Payoneer/Wise
- Invoicing templates / PDF generation
- Multi-currency auto-conversion live rates

## Risks
- PayPal personal account limits (withdrawal caps apply until account aged)
- ngrok required for local webhook dev; deploy to VPS/cloud for production webhooks
- FX rate cache staleness for KES estimates
