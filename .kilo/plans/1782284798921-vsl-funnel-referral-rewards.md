# VSL Funnel with Referral Rewards

## Status: IMPLEMENTED

## Goal
Replace deliverable-focused offers with outcome-based VSL funnels featuring $50 credit + 10% off + service extension referral rewards.

## Changes Made

### outreach/payments/payment_ledger.py
- Added `referral_source` and `referral_code` fields to `create_invoice()`
- Added `referral_rewards` object to invoice (credit_amount, discount_pct, extension_days)
- Added `_generate_referral_code()` method
- Added `apply_referral_rewards()` method for when referral converts

### outreach/funnel_builder.py
- Added `generate_vsl_landing_page(case_study, referral_code)` returning downloadable HTML
- Added `generate_referral_link(lead_id)` method

### outreach/delivery_agent.py
- Replaced `draft_email()` with SOP-compliant outcome-focused copy
- Added `draft_vsl_followup()` method for post-delivery referral emails
- Updated `draft_for_lead()` to pass referral_code to email drafts
- Updated `send_draft()` to support vsl_followup type

### outreach/outreach_agent.py
- Added `_generate_referral_code()` method
- Added `generate_referral_link()` method
- Updated `_run_draft_cycle()` to create referral codes and generate VSL pages
- Added VSL path to draft metadata

### outreach/email_enricher.py
- Reduced timeout from 10s to 3s for faster iteration
- Reduced pages scraped per domain from 6 to 3

### config.py
- Reduced IDLE_SLEEP_TIME from 60s to 10s

## Validation
- All modules import without errors
- Referral codes generated via MD5 hash (8 chars, uppercase)
- VSL HTML pages saved to `data/outreach/funnel/vsl_pages/`

## Performance Optimizations Applied
- Email enrichment timeout: Reduced from 10s to 3s
- Scraping pages per domain: Reduced from 6 to 3
- Outreach cycles: Run every cycle (was cycle % 3-7)
- Idle sleep: Reduced from 60s to 10s

## Current State
- Synthesized leads: 288
- Ready for outreach: 248
- With emails: 1 (support@docparsemagic.com)
- Scanner leads: 15