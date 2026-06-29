# Outreach System Performance Fixes

## Goal
Eliminate all bottlenecks in the MECOS outreach pipeline to enable faster lead discovery and email drafting.

## Critical Bottlenecks (fix first - highest speed impact)

### 1. Replace sync `requests.get` with async `httpx` in scanner.py
**File:** `outreach/scanner.py`
**Lines:** 581, 600-608
**Problem:** Blocking synchronous HTTP calls in async context stall the event loop
**Fix:** 
- Replace `requests.get(search_url, ...)` with async `httpx.get(...)`
- Wrap blocking calls in `asyncio.to_thread()` if httpx not available
**Impact:** Unblocks event loop, enables true concurrency

### 2. Parallelize SearXNG queries in `_run_scan_cycle`
**File:** `outreach/outreach_agent.py`
**Lines:** 197-212
**Problem:** 8 search queries run sequentially, wasting 60-200 seconds per cycle
**Fix:**
- Collect all async tasks for searches
- Use `asyncio.gather(*tasks, return_exceptions=True)`
**Impact:** ~8x faster search phase

### 3. Add concurrent URL fetching with semaphore in `search_leads`
**File:** `outreach/scanner.py`
**Lines:** 599-609
**Problem:** Sequential URL fetching is slow and no concurrency limit
**Fix:**
- Add `self._fetch_semaphore = asyncio.Semaphore(3)` in `__init__`
- Wrap `scan_url` calls with semaphore acquisition
- Use `asyncio.gather` for batch fetching
**Impact:** 3-5x faster URL processing

### 4. Parallelize research orchestrator keywords
**File:** `outreach/research_orchestrator.py`
**Lines:** 211-274
**Problem:** Outer loop processes keywords sequentially
**Fix:**
- Extract `_discover()` into `discover_for_keyword()` method
- Call `asyncio.gather` on all `discover_for_keyword()` calls
**Impact:** 5-6x faster research phase

### 5. Remove redundant social scanning in `_run_scan_cycle`
**File:** `outreach/outreach_agent.py`
**Lines:** 217-223
**Problem:** Social scanning via browser duplicates research_orchestrator
**Fix:**
- Remove social scanning calls (Reddit, HackerNews, IndieHackers)
- Rely on research_orchestrator for social signals
**Impact:** Eliminates redundant browser automation

## Medium Bottlenecks (fix second - moderate impact)

### 6. Optimize business directory query count
**File:** `outreach/scanner.py`
**Lines:** 548-557
**Problem:** 8 queries but only 4 executed, could increase to 6-7
**Fix:**
- Increase `queries[:6]` to cover more verticals
- Add concurrency to query execution
**Impact:** 50% more lead discovery coverage

### 7. Add caching to `_fetch_page_text`
**File:** `outreach/scanner.py`
**Lines:** 307-336
**Problem:** No caching, re-fetches same pages
**Fix:**
- Use scrapling_adapter cache (already added, verify integration)
- Add 5-minute TTL for page content
**Impact:** Reduced duplicate fetching

### 8. Optimize email enrichment concurrency
**File:** `outreach/outreach_agent.py`
**Lines:** 260
**Problem:** `enrich_batch` processes leads sequentially
**Fix:**
- Add semaphore to limit concurrent enrichments to 2
- Use `asyncio.gather` for batch enrichment
**Impact:** Faster email discovery

## Low Bottlenecks (fix last - minor impact)

### 9. Reduce followup cycle frequency
**File:** `outreach/outreach_agent.py`
**Lines:** 106-108
**Problem:** Followup cycle runs every 15 cycles
**Fix:**
- Change to every 10 cycles or trigger on demand
**Impact:** More timely followups

### 10. Optimize scrapling cache TTL
**File:** `outreach/scrapling_adapter.py`
**Lines:** 5-minute cache
**Problem:** Cache may be too short for busy systems
**Fix:**
- Reduce to 2 minutes for faster stale data refresh, or increase to 10 minutes for less API calls
**Impact:** Balancing API load vs freshness

## Validation Steps
1. Run single outreach cycle and measure scan time before/after
2. Verify drafts are still created correctly
3. Check no duplicate leads are generated
4. Monitor memory usage with concurrent fetches
5. Test SearXNG server load handling

## Risk Assessment
- **Medium:** Concurrency increase may overwhelm SearXNG server
- **Low:** httpx already in requirements.txt
- **Low:** Existing fallback paths for failed network calls