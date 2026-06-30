# Outreach Performance Fixes

## Goal
Eliminate bottlenecks in the MECOS outreach pipeline for faster lead discovery and email drafting.

## Status: Mostly Already Implemented

### Already Done
1. **Async httpx in scanner.py** — `search_leads` and `_fetch_page_text` already use `httpx.AsyncClient`.
2. **Parallel SearXNG queries** — `_run_scan_cycle` uses `asyncio.gather(*search_tasks)` for concurrent search.
3. **Concurrent URL fetching with semaphore** — `scan_url` wraps with `self._fetch_semaphore`; `search_leads` uses `asyncio.gather` for batch scans.
4. **Parallel research orchestrator** — `discover_for_keyword` + `asyncio.gather` in `discover_lead_signals`.
5. **Redundant social scanning removed** — `_run_scan_cycle` no longer contains social browser scanning.
6. **Business directory query concurrency** — `scan_business_directories` uses `queries[:6]` + `asyncio.gather`.
7. **Scrapling adapter caching** — `fetch_async` checks/sets cache with 10-minute TTL.
8. **Email enrichment concurrency** — `EmailEnricher.enrich_batch` uses semaphore + `asyncio.gather`.
9. **Followup cycle frequency** — Already tuned to every 10 cycles (`cycle % 10 == 0`).

### Remaining (Minor) - COMPLETED
1. **`demo_report.py` sync `requests.get`** — ✅ Converted to async `httpx._fetch_page()` now uses `httpx.AsyncClient`.
2. **Scrapling cache TTL** — ✅ Changed from 600s (10 min) to 300s (5 min).
3. **`WorldMonitorAdapter` sync block in async context** — ✅ Wrapped `enrich_batch` in `asyncio.to_thread`.

## Validation - COMPLETED
1. ✅ Python syntax checks pass for all modified files.
2. ✅ Import verification passes - all modules load correctly.
3. ✅ Async httpx fetch works (tested with example.com).
4. ✅ WorldMonitorAdapter enrich_batch works with asyncio.to_thread wrapper.
5. ✅ ScraplingAdapter cache TTL updated and functional.
