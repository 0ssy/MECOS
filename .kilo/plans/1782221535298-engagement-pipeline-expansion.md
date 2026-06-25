# Plan: Engagement Pipeline Expansion

## Goal
Turn MECOS into a revenue-generating outreach machine using Hormozi-style outcome-based offers, a basic-ads → VSL funnel, onboarding course/quiz, referral asks, and agreement tracking; extend monitoring with WorldMonitor intelligence feeds.

## Constraints
- Agreements tracked in a single ledger, tied to outcomes (not time/deliverables), with payment status.
- Referral asks occur during onboarding; course + quiz set expectations before payment.
- Email-only drafting remains default to prevent `pending_review` backlog.
- Do not commit `.env` or runtime data to git.
- Flags: `MECOS_ENABLE_TRADING=false`, `MECOS_ENABLE_OUTREACH=true`.

---

## Tasks

### 1. Monitoring v2 (`ceo_agent.py`)
- Add system health checks: disk space, CPU, network connectivity.
- Add outreach funnel metrics: emails sent, agreements (pending/signed/fulfilled), referrals, course completions.
- Add WorldMonitor feed ingestion: economic/consumer-prices, cyber/threats, supply-chain, unrest/displacement.
- CEO dashboard surfaces all metrics with thresholds.

### 2. Progress Ledger (`outreach/payments/payment_ledger.py`)
- Extend `PaymentLedger` with agreement state:
  - `agreement_type` (email/contract/verbal)
  - `status` (pending/signed/fulfilled/cancelled)
  - `outcome` dict: `time_saved_before`, `time_saved_after`, `pct_improved`
- Add referral tracking:
  - `referral_source` (lead_id or "self")
  - `referral_credit_amount`
- Link agreements via `agreement_id`.
- Maintain backward compat: existing `status` values still work, new fields optional.

### 3. Hormozi Outcome-Based Offers (`outreach/delivery_agent.py`)
- Replace deliverable pricing with outcome guarantee copy.
- Default offer: "We guarantee 60%+ time reduction. If not, you pay nothing."
- Risk-reversal language in all email templates.
- Shift from fixed pricing ($500–$1,500) to value-based pricing tied to client ROI.

### 4. VSL Funnel Brief (`outreach/funnel_builder.py`)
- New method: `generate_funnel_brief(lead, case_study)`.
- Produces structured brief: ad creative, VSL script outline, CTA flow, agreement CTA.
- Phase 2 (post-revenue): generate HTML page from brief (out of scope now).

### 5. Referral Ask in Onboarding
- When agreement is created, include referral request in agreement CTA.
- Track referral credits in `PaymentLedger`.
- CEO dashboard shows referral conversion rate.

### 6. Course + Quiz (`outreach/funnel_builder.py`)
- New data model: `course_module` with sections, quiz questions, pass threshold.
- New method: `generate_onboarding_sequence(brief)` producing course outline + quiz.
- Stores in `data/outreach/funnel/courses.json`.

### 7. CEO Dashboard Progress View
- Real metrics from `PaymentLedger` + `RevenueLedger`.
- Emails sent, agreements by status, referrals, course completions.
- Revenue by bucket (ops/trading/growth).
- WorldMonitor signal summary per feed category.

---

## Files Touched
- `ceo_agent.py` — monitoring expansion, dashboard
- `outreach/payments/payment_ledger.py` — agreement/outcome/referral fields
- `outreach/delivery_agent.py` — Hormozi offer copy
- `outreach/funnel_builder.py` — funnel briefs, course/quiz generation
- `outreach/outreach_agent.py` — wire referral ask into draft cycle
- `data/outreach/payments/payment_ledger.json` — schema migration
- `data/outreach/funnel/courses.json` — new

## Out of Scope
- HTML page generation from funnel briefs (Phase 2 after revenue).
- Percentage referral kickback (Phase 2 after growth).
- WorldMonitor private API integration (public feeds only).
- Course delivery platform (quiz is data model only).
