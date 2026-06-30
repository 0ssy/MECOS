# Smoke Test Infrastructure Fix

## Goal
Fix circular import error blocking smoke test execution by renaming the `outreach/calendar` module that shadows Python's stdlib `calendar` module.

## Context
- Performance fixes (async httpx in demo_report.py, 300s cache TTL in scrapling_adapter.py, `asyncio.to_thread` wrapper for WorldMonitorAdapter) are complete and verified
- Smoke test fails with `ImportError: cannot import name 'logger' from partially initialized module 'loguru'` due to `outreach/calendar/__init__.py` shadowing stdlib `calendar` module
- `loguru` imports stdlib `calendar`, but Python finds `outreach/calendar` instead

## Affected Files
1. `outreach/calendar/` → rename to `outreach/booking_scheduler/`
2. `outreach/reply_monitor.py` - update import on line 16
3. `outreach/outreach_agent.py` - update import on line 530

## Implementation Tasks

### Task 1: Rename module directory
- Rename `outreach/calendar/` to `outreach/booking_scheduler/`
- Ensure `booking_scheduler/__init__.py` retains `CalendarBooking` export

### Task 2: Update imports in reply_monitor.py
- Change `from outreach.calendar.booking import CalendarBooking` to `from outreach.booking_scheduler.booking import CalendarBooking`

### Task 3: Update imports in outreach_agent.py
- Change `from outreach.calendar.booking import CalendarBooking` to `from outreach.booking_scheduler.booking import CalendarBooking`

## Validation
1. `python -c "from outreach.booking_scheduler.booking import CalendarBooking"` succeeds
2. `python -c "from outreach.reply_monitor import ReplyMonitor"` succeeds
3. `python -c "from outreach.outreach_agent import OutreachAgent"` succeeds
4. Smoke test starts without circular import error

## Risks
- Low: Only 2 import paths need updating; no logic changes required
- Breaking change for any external code importing `outreach.calendar`

## Open Questions
- None - straightforward rename operation