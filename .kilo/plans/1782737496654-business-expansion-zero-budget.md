# MECOS Business Sector Expansion (Zero-Budget Bootstrap)

## Goal
Expand MECOS into a full business automation suite for revenue generation with zero external costs, targeting industries where MECOS can gain visibility and word-of-mouth adoption.

## Core Strategy
Use free/open-source tools and built-in capabilities to replace paid services:
- Google Sheets as CRM (instead of HubSpot/Salesforce)
- Built-in email sequences (instead of premium follow-up tools)
- Free community scraping (instead of paid lead lists)
- Self-hosted tracking (instead of premium analytics)

## Target Industries (High-Visibility)
These industries actively share tools and provide social proof:
1. **SaaS startups** - Active in communities, love sharing new tools, built-in audience
2. **E-commerce merchants** - High automation pain, active in forums, social proof seekers
3. **Marketing agencies** - Already automation-focused, potential reseller channel
4. **Content creators/YouTubers** - Need scheduling automation, built-in audience
5. **Bootstrapped solopreneurs** - Cost-sensitive, vocal about time-saving tools

## Phase 1: Better Lead Discovery (Week 1-2)

### High-Visibility Scrapers
- Create `outreach/lead_sources/` directory
- Add scrapers for:
  - SaaS: Product Hunt, Indie Hackers, Hacker News "Show HN", GitHub READMEs with "built with"
  - E-commerce: Shopify Community forums, Reddit r/ecommerce, WooCommerce showcase sites
  - Agencies: Dribbble "for hire", Behance portfolios, Clutch.co profiles
  - Creators: Medium publications about tools, YouTube video descriptions mentioning pain points
  - Solopreneurs: Free "built with" badge sites, personal blogs mentioning automation tools

### Decision-Maker Identification
- Enhance `email_enricher.py` to find Twitter/LinkedIn URLs from company pages
- Add contact pattern detection: founder emails, "built with" links
- Create `decision_maker_finder.py` to extract names/titles from "about" pages

### Deduplication Strategy (Resolved)
- Domain + URL matching for duplicate detection
- Content fingerprinting via hash of page text for near-duplicates
- Status-based deduplication: only one active lead per domain

## Phase 2: Free CRM Integration (Week 2-3)

### Google Sheets CRM Bridge
- Create `outreach/crm/sheets_bridge.py`
- Sync discovered leads to a Google Sheet with columns:
  - URL, Domain, Contact, Email, Twitter, Status, Last Contact, Notes, Source
- Implement `crm_actions.py`:
  - Status changes: `new` → `contacted` → `replied` → `meeting_booked` → `deal_won` / `deal_lost`
  - Use Google Sheets API via service account (free tier)
- Create CLI: `mecos crm push`, `mecos crm pull`

### Manual Deal Tracking
- Add `deal_tracker.py` to log sales outcomes
- CSV export of closed deals with: date, amount, lead source, notes

## Phase 3: Conversion Optimization (Week 3-4)

### Email Sequence Engine
- Create `outreach/email_sequence.py`
- 3-touch sequence:
  1. Initial outreach (exists)
  2. Value-add follow-up (50% off first bot + case study) — 3 days later
  3. Final attempt (social proof: "12 startups using MECOS") — 7 days after #2
- Add `followup_scheduler.py` to queue follow-ups

### Reply Intent Analysis
- Enhance `reply_monitor.py` to detect buying signals:
  - Keywords: "pricing", "demo", "call", "meeting", "schedule", "price", "cost", "available"
- Auto-flag high-intent replies in dashboard

## Phase 4: Revenue Analytics (Week 4-5)

### Conversion Funnel Dashboard
- Create `outreach/analytics/funnel.py`
- Track: leads_discovered → emails_sent → replies → meetings → deals_won
- Conversion rates: reply_rate, meeting_rate, close_rate

### ROI Calculator
- Add `roi_tracker.py`:
  - Time invested vs revenue generated
  - By lead source effectiveness
- Extend `revenue_ledger.py` with source tagging

### Performance Reports
- Generate weekly Markdown reports for GitLab Pages:
  - Top performing lead sources
  - Best converting email templates
  - Revenue per hour invested

## Phase 5: Meeting Scheduling (Week 5-6)

### Calendar Integration
- Create `outreach/calendar/booking.py`
- Google Calendar booking links (free)
- Parse replies for "meeting", "call", "available" keywords
- Send booking link via email

## Affected Boundaries
- `outreach/scanner.py` — add lead source integration
- `outreach/email_enricher.py` — enhanced contact discovery
- `outreach/delivery_agent.py` — sequence scheduling
- `outreach/dashboard.py` — funnel metrics display
- `outreach/revenue_ledger.py` — source attribution, ROI

## Data Flow
```
[lead_sources/*.py] → scanner.leads → crm_sheets.sync → email_sequence → reply_monitor
                                                                 ↓
                                                       roi_tracker (close deals)
                                                                 ↓
                                                        weekly_markdown_report
```

## Validation Steps
1. Test lead sources scrape valid business URLs from target industries
2. Verify Google Sheets CRM sync works with test sheet
3. Confirm 3-touch sequence sends correctly
4. Validate reply detection flags buying signals
5. Check weekly Markdown report generates with funnel data

## Risks
- Community scraping may have rate limits
- Google Sheets API requires one-time setup
- Free tiers may have rate/scale limits
- No built-in phone/SMS capability (would need Twilio trial)

## Open Questions
- Which specific communities to scrape first (Product Hunt vs Indie Hackers)?
- Should meeting links be stored in CRM sheet or generated dynamically?
- How many leads to cap per day to avoid rate limits?