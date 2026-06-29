# Scrapling Integration Plan

## Goal
Replace `requests.get()` with Scrapling for stealth web scraping in both email enrichment and lead scanning, with requests as fallback.

## Current State
- `email_enricher.py:_scrape_website()` uses synchronous `requests.get()` (lines 129-141)
- `scanner.py:_fetch_page_text()` uses synchronous `requests.get()` (lines 295-314)
- Both lack stealth capabilities for sites with bot protection
- `BrowserAutomation` class exists with Playwright but is overkill for simple fetches

## Integration Points

### 1. `outreach/email_enricher.py` - `_scrape_website()`
- Replace `requests.get()` with Scrapling's `Fetcher.fetch()`
- Keep requests as sync fallback when Scrapling fails

### 2. `outreach/scanner.py` - `_fetch_page_text()`
- Replace `requests.get()` with Scrapling's `Fetcher.fetch()`  
- Keep requests as sync fallback when Scrapling fails

## Implementation Tasks

1. **Add Scrapling dependency**
   - Add `scrapling` to `pyproject.toml` or `requirements.txt`

2. **Create `outreach/scrapling_adapter.py`** (new file)
   - Lazy-initialized Scrapling Fetcher wrapper
   - Sync and async interfaces
   - Fallback to requests on failure
   - Shared across modules to avoid repeated setup

3. **Update `outreach/email_enricher.py`**
   - Import from scrapling_adapter
   - Use Scrapling as primary in `_scrape_website()`
   - Fallback to requests on `FetcherError`, timeout, or non-200 status

4. **Update `outreach/scanner.py`**
   - Import from scrapling_adapter  
   - Use Scrapling as primary in `_fetch_page_text()`
   - Fallback to requests on failure

5. **Add tests to `tests/test_agent_reach_phase2.py`**
   - Test `scrapling_adapter` with mocked responses
   - Verify fallback behavior works

## Risks / Mitigations

- **Risk**: Scrapling may be slower than requests
  - **Mitigation**: Only use Scrapling for sites that return 403/429 or timeout

- **Risk**: Scrapling may fail on certain edge cases
  - **Mitigation**: Always fallback to requests

- **Risk**: New dependency may cause import issues
  - **Mitigation**: Lazy import pattern, try/except with clear error logging

## Validation
- Run existing tests to ensure no regressions
- Verify smoke test works with Scrapling adapter
- Check that skipped_leads.jsonl doesn't increase for previously blocked domains