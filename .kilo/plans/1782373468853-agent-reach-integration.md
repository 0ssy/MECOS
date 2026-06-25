# Agent-Reach Integration Plan

## Goal
Strengthen MECOS outreach by adding social/web research signals from Twitter, YouTube, Reddit, and the open web. Use Agent-Reach as the research backend (already vendored as a local Python package in `agent_reach/`).

## Decisions
1. **Integration pattern:** Shell out to the local `agent_reach` package from small Python adapter classes under `outreach/research_channels/`. Reuse `AgentReachBridge` for URL routing and Jina fallback.
2. **Phase scope:** Option 1 first (on-demand research before drafting for high-quality leads). Phase 2 (background monitoring cycle every 20 cycles) can be added later without changing Phase 1 data structures.
3. **Data model (Option C):** Store raw signals on `lead["research_signals"]` so `LeadSynthesizer` can factor them into pain points/persona. Store a condensed, LLM-free summary on `brief["research_summary"]` so `DeliveryAgent.draft_email()` can personalize without re-running research.
4. **Trigger threshold:** Research runs only when `lead.get("total_score", 0) >= 5` or `lead.get("intel_multiplier", 1.0) >= 1.2`. This keeps draft-cycle latency bounded (~2-5s per researched lead via Jina fallback).
5. **Failure handling:** Missing CLI / missing auth → fall back to Jina Reader generic web fetch (already wired in `AgentReachBridge._jina_read`). Log warning, skip personalization for that platform, don't fail the draft cycle.
6. **No new DB tables:** All research results attach to existing in-memory `lead`/`brief` dicts and persist through the existing `leads.json` / `synthesized_leads.json` save paths.

## Data Flow (Phase 1)
```
OutreachScanner.leads (raw signal dict)
        ↓  [high-score gate]
_outreach/research_channels/ adapters
        ↓  shell-out / agent_reach bridge
lead["research_signals"] = {
    "twitter": {"ok": true, "text": "...", "link": "..."},
    "youtube": {"ok": false, "error": "no auth"},
    ...
}
        ↓  (synthesis already done or re-summarized)
brief["research_summary"] = (
    "Lead's recent tweets mention X pain point. "
    "Industry video on YouTube shows trend Y. "
    "Reddit thread highlights Z as top complaint."
)
        ↓
DeliveryAgent.draft_email(brief) → injects 1-2 sentences of personalization
```

## Implementation Tasks

### Task 1: Research adapters (`outreach/research_channels/`)
- Create package with `__init__.py`, `base.py`, `twitter.py`, `youtube.py`, `reddit.py`, `web.py`.
- Each module exports `research_<platform>(query: str, max_results: int = 3) -> dict`.
- Reuse `AgentReachBridge.read_url()` and `AgentReachBridge._jina_read()` for web fallback.
- Twitter/Youtube/Reddit modules shell out via `agent_reach` CLI when available; otherwise return `{"ok": false, "error": "backend_unavailable"}` so the orchestrator falls back gracefully.
- Keep timeouts tight (8-12s per platform) to protect draft-cycle latency.

### Task 2: Research orchestrator (`outreach/research_orchestrator.py`)
- `ResearchOrchestrator` class with `research_lead(lead: dict) -> dict`.
- Applies the high-score gate (`total_score >= 5` or `intel_multiplier >= 1.2`).
- Runs platforms in parallel (asyncio.gather with platform-level timeouts).
- Writes `lead["research_signals"]` with per-platform results.
- Produces `research_summary` string (simple template: pick top 1-2 non-empty platforms, one sentence each) and returns it.

### Task 3: Hook into draft cycle (`outreach/outreach_agent.py`)
- In `_run_draft_cycle()`, before calling `draft_for_lead()`:
  - Instantiate `ResearchOrchestrator`.
  - If lead passes gate, call `research_lead(lead)`.
  - Pass `research_summary` into `lead_brief` so `DeliveryAgent.draft_email()` can use it.
- In `DeliveryAgent.draft_email()`, append 1-2 personalization lines when `brief.get("research_summary")` is present:
  - Insert after the hook sentence, before the outcome sentence.
- No changes to `FunnelBuilder` or `LeadSynthesizer` in Phase 1.

### Task 4: Background research cycle (Phase 2, deferred)
- Add `_run_research_cycle()` to `OutreachAgent`, run every 20 cycles.
- Uses `AgentReachBridge` to probe Twitter/Reddit/YouTube for industry keywords derived from `OutreachScanner.PAIN_KEYWORDS`.
- Discovered URLs → create minimal lead dicts → append to `OutreachScanner.leads`.
- Skip if research backends are unavailable.

### Task 5: Validation
- Unit test: `ResearchOrchestrator.research_lead()` returns expected shape when all backends down (graceful Jina fallback).
- Unit test: `draft_email()` includes personalization when `research_summary` is present and omits it when absent.
- Smoke test: Run one `_run_draft_cycle()` against a high-score lead with Agent-Reach unavailable; verify cycle completes in <15s and draft is generated.

## Ruff/Lint
- Run project lint after adding new files. Fix any `E`/`F` issues in the new modules before finishing.

## Open Questions
- None. If Agent-Reach backends prove too slow at scale, the threshold can be raised or platforms reduced in a follow-up plan.
