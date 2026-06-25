# Agent-Reach Integration Phase 2 - Background Research Cycle

## Goal
Add `_run_research_cycle()` to OutreachAgent that runs every 20 cycles, probing Twitter/Reddit/YouTube for pain keywords to discover new leads.

## Decision
Use `PAIN_KEYWORDS` as direct search queries across platforms, treating discovered content as potential new leads.

## Context
- Phase 1 already implemented: on-demand research in `_run_draft_cycle()` for high-score leads
- ResearchOrchestrator exists with `research_lead()` and `should_research()` 
- Research channels (twitter.py, reddit.py, youtube.py, web.py) already exist
- OutreachAgent runs cycles: scan (every 3), enrich (every 4), synth (every 5), draft (every 7), followup (every 15)

## Tasks

1. Extend ResearchOrchestrator with `discover_lead_signals()`
   - Add method that takes keyword list and returns discovered lead candidates
   - Uses existing `research_twitter/reddit/youtube/web` functions
   - Creates minimal lead dicts with: url, domain, text excerpt, source platform
   - Sets initial `total_score` based on pain keyword matches in discovered text

2. Add `_run_research_cycle()` to OutreachAgent
   - Run every 20 cycles: `if self.cycle % 20 == 0:`
   - Import `PAIN_KEYWORDS` from scanner
   - Call `research_orchestrator.discover_lead_signals(PAIN_KEYWORDS[:6])` (limit for latency)
   - Append discovered leads to `self.scanner.leads` via `self.scanner._save_leads()`
   - Log count of new leads discovered

3. Update cycle logic in `run_cycle()`
   - Add research cycle before scan cycle (high priority)
   - Import `AgentReachBridge` for graceful backend availability checks

4. Add tests (`tests/test_agent_reach_phase2.py`)
   - Test `discover_lead_signals()` returns empty list when all backends fail
   - Test `discover_lead_signals()` creates valid lead dicts with Jina fallback
   - Smoke test `_run_research_cycle()` integration

## Validation Gate
- `pytest tests/test_agent_reach_phase2.py -v` passes
- `outreach/research_channels/` files pass ruff lint
- Research cycle runs without blocking draft cycle latency (< 30s total)
- New leads appear in `data/outreach/leads.json` after research cycle (when Jina available)

## Risks
- Jina rate limits could block discovery
- Duplicate leads may be rediscovered - rely on scanner's dedup via `scanned_urls`
- Backend unavailability should not block the cycle - graceful skip required