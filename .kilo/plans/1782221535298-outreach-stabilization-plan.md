# MECOS Outreach Stabilization Plan

## Status: COMPLETED

## Context
- `leads.json` contained duplicates from old `hn.algolia.com` seed URLs; `scan_cycles_by_url` + `scanned_content_hashes` were in-memory only → lost on restart
- SearXNG public instance (`searx.rhscz.eu`) rate-limited (429); self-hosted Docker compose existed but wasn't running
- Memory used EphemeralClient; vector files already existed on disk (`memory_db/vector_db/chroma.sqlite3`)
- `outreach/outbox/` had 57 stale `reddit_post` drafts; email validation was missing (sent fallback to `unknown@example.com`)

## Decision Summary
- SearXNG: bring up local Docker first, repoint `.env`
- Dedup: Option B — add `content_hash` to new lead dicts; restore both dedup sets from `leads.json` on `OutreachScanner.__init__`
- Memory: switch to PersistentClient with fixed collection name
- Outreach: remain disabled during stabilization

## Task List

### Phase 1: Self-hosted SearXNG ✅
- Created `searxng/settings.yml` (JSON format + google/duckduckgo engines)
- Container `searxng` started, healthy at `http://localhost:8888`
- `.env` updated: `SEARXNG_URL=http://localhost:8888`
- Scan cycles confirm **zero 429 errors**

### Phase 2: Dedup restoration (Option B) ✅
- **`outreach/scanner.py` — `scan_url()`**: `content_hash` stored in lead dict
- **`outreach/scanner.py` — `search_leads()`**: `content_hash` stored in lead dict
- **`outreach/scanner.py` — `__init__`**: `_load_leads()` now calls `_restore_dedup_state()`, rebuilding:
  - `self.scan_cycles_by_url` from `discovered_at` timestamps
  - `self.scanned_content_hashes` from `content_hash` fields
- **`outreach/scanner.py` — social scans**: `_scan_reddit`, `_scan_hackernews`, `_scan_indiehackers` now respect 24h dedup window
- Cross-restart dedup verified: scan 1 → 7 new leads → scan 2 (fresh process) → 0 duplicates

### Phase 3: Memory persistence ✅
- **`memory_system.py` — `VectorMemory.__init__`**: default to `PersistentClient(path=settings.VECTOR_DB_PATH)`
- EphemeralClient reserved for pytest only
- Fixed collection name: `mecos_long_term` (no PID/UUID suffix)
- Existing `chroma.sqlite3` data preserved

### Phase 4: Stabilization run ✅
- Outreach confirmed disabled (`MECOS_ENABLE_OUTREACH=false`)
- 3 scan cycles in fresh Python processes: no crashes, no duplicate leads
- Test suite: **108/108 passing**

## Pending / Out of Scope
- **Stale outbox drafts**: 57 `reddit_post` drafts from old hn.algolia.com leads remain in `data/outreach/outbox/`
  - These will all fail send when outreach is re-enabled (invalid Reddit URLs, no valid emails)
  - **Action required before re-enabling**: clean `outbox/` or set stale draft statuses to `dismissed`
- **WAF / firewall rule**: `snapt<SECRET_ac7b2d0a>` (irrelevant path in `web_perception.py` seems to embed email? should verify and flag)
- **Old leads backfill**: 6 pre-existing hn.algolia.com leads lack `content_hash` — graceful degradation to time-window dedup

## Validation Summary
| Check | Result |
|---|---|
| Dedup rebuild across restart | Pass — 13 URLs, 7 hashes restored; 0 new duplicates |
| SearXNG local JSON API | Pass — returns google/brave results instantly |
| 429 rate-limit errors | Pass — 0 occurrences |
| Memory persistence | Pass — PersistentClient active, chroma.sqlite3 untouched |
| Test suite | Pass — 108/108 |

## Risks
- Re-enabling outreach without cleaning outbox will produce 57 failed sends
- Local SearXNG container requires Docker Desktop running; if stopped, rerun `docker compose -f docker-compose-searxng.yml up -d`
- Old leads without `content_hash` only have time-window protection; they will age out eventually but aren't fully content-dedup-protected until rescanned
