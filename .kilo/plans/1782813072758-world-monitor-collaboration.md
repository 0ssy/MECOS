# WorldMonitor Collaboration — Lead Pipeline Fix

## Goal
Turn `WorldMonitorAdapter` into an active lead-generation collaborator by:
1. Fixing `LeadSource` instantiation errors
2. Adding intel-driven pre-scan expansion
3. Scoring intel before the ICP gate with pass-through behavior

## Context
- Smoke test passes infrastructure fix but yields 0 leads
- 4 of 5 LeadSources crash on `source_cls()` with `TypeError: __init__() missing 1 required positional argument: 'source_name'`
- All errors are swallowed by broad `except` in `_run_scan_cycle`
- `WorldMonitorAdapter` exists but only scores existing leads; never generates candidates

## Tasks

### 1. Fix LeadSource instantiation
**File:** `outreach/lead_sources/base.py:30`
- Change `source_name: str` to `source_name: Optional[str] = None`
- Derive from class name when None:
  ```python
  if source_name is None:
      source_name = self.__class__.__name__.replace("LeadSource", "").lower()
  ```
- Add `Optional` to typing imports

### 2. Add `generate_lead_candidates` to WorldMonitorAdapter
**File:** `outreach/worldmonitor_adapter.py`
- Signature:
  ```python
  async def generate_lead_candidates(self, industry: str, count: int = 5, scanner: OutreachScanner = None) -> List[Dict[str, Any]]:
  ```
- Look up `industry` in `INDUSTRY_FEED_URLS`; fetch each RSS feed (10s timeout per feed, continue-on-fail)
- Parse items; match against `SIGNAL_KEYWORDS`; collect matched signal types
- **Build queries**: require min 2 matched keywords + append industry context suffix (e.g. `"automation hiring small business"`, `"raised funding SaaS agency"`)
- **Dedup before search**: skip if URL already in `scanner.scanned_urls` OR hash in `scanner.scanned_content_hashes`
- Call `scanner.search_leads(query, limit=count // 2)` for each query
- Attach to returned leads:
  ```python
  lead["intel_multiplier"] = self._calculate_multiplier(matched_signals)
  lead["intel_signals"] = matched_signals
  ```

### 3. Pre-scan intel expansion
**File:** `outreach/outreach_agent.py:_run_scan_cycle`
- After `all_new = dir_leads + search_leads + source_leads` (line 235)
- If `len(all_new) == 0`:
  ```python
  new_candidates = []
  for industry in self.lead_sources.keys():
      try:
          candidates = await self.intel_adapter.generate_lead_candidates(
              industry, count=5, scanner=self.scanner
          )
          new_candidates.extend(candidates)
      except Exception as exc:
          logger.debug(f"Intel expansion skip ({industry}): {exc}")
  all_new.extend(new_candidates)
  if new_candidates:
      logger.info(f"WorldMonitorAdapter expansion: added {len(new_candidates)} intel candidates")
  ```

### 4. Mid-pipeline intel enrichment before ICP gate
**File:** `outreach/outreach_agent.py:_run_scan_cycle`
- Current order: `enrich_batch` → intel → ICP gate
- New order:
  1. Assemble `all_new`
  2. Intel expansion (Task 3)
  3. `enriched = await asyncio.to_thread(self.intel_adapter.enrich_batch, all_new)`
  4. **ICP gate with intel relaxation**:
     - If `lead.get("intel_multiplier", 1.0) > 1.5`:
       - Accept if `local_score >= 2` OR `intel_multiplier >= 1.8`
     - Else original filter: `local_score >= 3` AND `enterprise_penalty <= 2`
- Pass-through: if no signal, `intel_multiplier = 1.0` and lead hits original filter

### 5. Async safety (no blocking)
- `enrich_batch` already runs via `asyncio.to_thread` (line 279)
- `generate_lead_candidates` uses `scanner.search_leads` which is already async
- RSS fetching inside `_fetch_recent_signals` uses `requests.get`; wrap its call in `asyncio.to_thread` from the agent side:
  ```python
  signals = await asyncio.to_thread(self.intel_adapter._fetch_recent_signals)
  ```

## Data Flow
```
lead_sources.get_leads()          → URLs + pain signals + local_score
scanner.search_leads()             → SearXNG URLs with ICP scores
if all_new empty:
  intel_adapter.generate_lead_candidates() → signal-boosted URLs
              ↓ merged all_new ↓
         intel_adapter.enrich_batch()       (multiplier 0.5–2.5)
              ↓ ICP gate with relaxation ↓
         email enrichment → synth → draft → send
```

## Risks & Mitigations
| Risk | Mitigation |
|---|---|
| Slow RSS feeds | Per-feed 10s timeout + continue-on-fail |
| Weak intel leads | Relaxed ICP gate only when multiplier > 1.5 |
| Query quality | Min 2 signal keywords + industry context suffix |
| Dedup collisions | Check both `scanned_urls` and `scanned_content_hashes` |
| Async blocking | Wrap sync RSS fetches in `asyncio.to_thread` |

## Affected Files
- `outreach/lead_sources/base.py`
- `outreach/worldmonitor_adapter.py`
- `outreach/outreach_agent.py`

## Validation
1. Smoke test logs `WorldMonitorAdapter expansion:` when primary sources yield nothing
2. Smoke test logs `Intel boost for <domain>` when signals match
3. No `TypeError` on `source_cls()` instantiation
4. No sync-blocking RSS calls in async event loop
5. >0 leads OR >0 skipped leads after ICP gate when intel expansion fires
