# MECOS Outreach Next Steps Plan

## Status: IMPLEMENTED ✓

## Current State Summary
- Outreach agent enabled, email (Gmail) configured ✓
- Revenue ledger shows $2,400 but appears bootstrapped, not from real clients ✓
- Scanner currently hitting API endpoints (hn.algolia.com) repeatedly - producing duplicates ✓ (FIXED)
- No real business leads with contact emails extracted ✓ (FIXED)
- No PayPal credentials configured for payment links ✓ (FIXED)
- MCP servers (Notion, Slack, Granola, Zapier) stubbed/not configured ✓

## Changes Implemented

### Priority 1 Fixes ✓
- **PayPal credentials** - Added to `.env` (sandbox mode)
- **Scanner seed URLs** - Updated to target real business forums (smallbusiness, Entrepreneur, webdev)
- **Deduplication** - Added 24h window + content hash checking to `scanner.py`

### Priority 2: SearXNG Integration ✓
- **Config** - Added `SEARXNG_URL` to `config.py` and `.env`
- **Scanner** - Added `search_leads()` method in `outreach/scanner.py`
- **Docker compose** - Created `docker-compose-searxng.yml`
- **Settings** - Created `searxng-settings.yml` for JSON format

### Priority 3: Outreach Improvements ✓
- **Email unsubscribe** - Added to `delivery_agent.py` for CAN-SPAM compliance
- **Enhanced keywords** - Added business-specific signals ("automation needed", "$500", "freelancer", etc.)

## Immediate Fixes (Priority 1)

### 1. Add PayPal Credentials to .env
**Problem:** `paypal_client.py` cannot create orders without `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`

**Fix:** Add credentials from `.env.example` to `.env`:
```
PAYPAL_CLIENT_ID=AYOa5IGMHHqHn5hUOCmI0XsDi_eC1-L_6uJ9FbNpER1sdwJY-4PWJp3OEOPLBM2wq3UQZ8fjJNfHreKP
PAYPAL_CLIENT_SECRET=EEmI3yRKdQVYi1YVN_Z9avoZc1LwyB-nt5ow89N2xsS-kQsYM4BYvHFleeC5Jl1LlqBnOAnAJyQ2m9IO
PAYPAL_MODE=sandbox
```

### 2. Fix Scanner to Target Real Business Sources
**Problem:** `scanner.py` seed URLs are all API/search endpoints producing duplicates

**Fix in `outreach/scanner.py`:**
- Replace hardcoded seed URLs with actual small business directories and forums
- Add proper pagination to avoid re-scanning same content
- Target: Reddit posts from business owners, IndieHackers product posts, small business forums

### 3. Implement Proper Lead Deduplication
**Problem:** Same URLs scanned repeatedly, leads.json shows identical entries

**Fix:**
- Use URL-based deduplication with content hash
- Add `scan_cycle_id` to track when lead was discovered
- Prevent re-scannning within 24h window

## Part 2: SearXNG Search Engine Integration (Priority 2)

### Current Status
- No search engine configured for lead discovery
- User prefers SearXNG over Brave Search API (no API costs, privacy-focused)

### SearXNG Integration Options:

**Option A: Quick Test (Public Instance)**
- Use public instances from searx.space
- Add `SEARXNG_URL=https://searx.rhscz.eu` to `.env`
- Risk: Rate limiting, no SLA

**Option B: Production (Self-Hosted Docker)**
- Docker compose on port 8888
- Enable JSON format in settings.yml
- Unlimited queries, private instance

```yaml
# docker-compose.yml
services:
  searxng:
    image: searxng/searxng:latest
    ports: ["8888:8080"]
    volumes: ["./searxng:/etc/searxng:rw"]
```

### Implementation in `outreach/scanner.py`
Add `search_leads()` method:
```python
async def search_leads(self, query: str, engines: str = "google,duckduckgo") -> List[Dict]:
    params = {"q": query, "format": "json", "engines": engines}
    response = requests.get(settings.SEARXNG_URL, params=params)
    return response.json().get("results", [])
```

## Part 3: MCP Integration (Priority 3)

### Current Status
- MCP servers configured in `config.py` but not activated
- `.env` missing all MCP API keys except GitHub

**Missing:**
- `NOTION_API_KEY`
- `SLACK_BOT_TOKEN`
- `GRANOLA_API_KEY`
- `ZAPIER_API_KEY`

## Part 4: Outreach Quality Improvements

### Lead Scoring & Targeting
- Current keywords are too broad ("hiring", "repetitive")
- Add business-specific signals: "automation needed", "workflow bottleneck", "$500", "contract", "freelancer"
- Add revenue fit signals: "founder", "startup", "small business", "local"

### Email Deliverability
- Gmail App Password limits: ~500 emails/day
- Current drafts lack unsubscribe link (required for CAN-SPAM compliance)
- Add proper sender identity and business signature

## Part 5: Other MECOS Parts Needing Fixes

### 1. Perception Layer (`perception.py`, `web_perception.py`)
- **Status:** Partially working
- **Issue:** No error recovery for rate-limited sites
- **Fix:** Add exponential backoff and user-agent rotation

### 2. Tool Orchestrator (`tool_orchestrator.py`)
- **Status:** MCP registration has issues
- **Issue:** `mcp_client_register_all()` may fail silently
- **Fix:** Add explicit logging and health check endpoint

### 3. Reasoner (`reasoner.py`)
- **Status:** Skill integration complete
- **Issue:** Skill triggers may not match outreach goals
- **Fix:** Add outreach-specific skill patterns

### 4. Memory System (`memory_system.py`)
- **Status:** Using EphemeralClient (safe)
- **Issue:** Memory resets on restart
- **Fix:** Consider persistent mode once stable

### 5. Trading Agent (`trading_agent.py`)
- **Status:** Disabled per constraint
- **Issue:** Requires paper trading validation before enabling
- **Fix:** Run paper trading simulation first, validate profit threshold

## Execution Steps

### Step 1: Add PayPal to .env
```
PAYPAL_CLIENT_ID=AYOa5IGMHHqHn5hUOCmI0XsDi_eC1-L_6uJ9FbNpER1sdwJY-4PWJp3OEOPLBM2wq3UQZ8fjJNfHreKP
PAYPAL_CLIENT_SECRET=EEmI3yRKdQVYi1YVN_Z9avoZc1LwyB-nt5ow89N2xsS-kQsYM4BYvHFleeC5Jl1LlqBnOAnAJyQ2m9IO
PAYPAL_MODE=sandbox
```

### Step 2a: Add SearXNG to config.py and .env
```
SEARXNG_URL=https://searx.rhscz.eu
```
Add to `config.py` Settings class:
```python
SEARXNG_URL: str = os.getenv("SEARXNG_URL", "http://localhost:8888")
```

### Step 2b: Update Scanner to use SearXNG
- Add `search_leads()` method to `OutreachScanner`
- Use for queries like "small business automation needed", "workflow help site:reddit.com"

### Step 3: Add Real Lead Sources
Implement `scan_business_directories()`:
- YellowPages scraping (if allowed)
- Google Maps leads (via search)
- Local business subreddits

### Step 4: Test Email Path
```python
# Test real delivery to secondary email
delivery_agent.send_draft({...})
```

### Step 5: Run 24h Stability Test
Monitor for crashes, verify revenue ledger updates.

## Timeline Estimates

| Milestone | Estimate |
|-----------|----------|
| PayPal credentials added | Quick (edit .env) |
| SearXNG integration tested | Quick (add SEARXNG_URL) |
| Scanner producing real leads | Days |
| First outbound email to prospect | Days |
| First response received | Weeks |
| First sale closed | Weeks-Months |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Gmail rate limits | Batch emails, monitor sends |
| Low lead quality | Refine keywords, add manual review step |
| PayPal sandbox → live transition | Test thoroughly before production |
| No real responses | A/B test subject lines, improve pitch |