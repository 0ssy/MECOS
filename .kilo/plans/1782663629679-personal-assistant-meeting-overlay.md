# Personal Assistant + Meeting Overlay for MECOS

## Goal
Turn MECOS from an autonomous background engine into a real-time personal assistant during meetings and daily work. Add a Windows transparent overlay (Cluely-like), real-time meeting transcription, on-demand web scraping, Kilo deep-code fallback, and autonomous evolution toward a hybrid assistant model.

---

## Locked Decisions

### Overlay UI
- `pywebview` transparent frameless window on Windows
- Content served by MECOS’s existing FastAPI server (no separate HTTP server)
- Split layout: left = live transcript, right = suggested answer / code output
- Tabs: Transcript, Suggestions, Code

### Activation
- Auto-detect meeting apps via `AppPerception` (Zoom, Teams, Google Meet) → show overlay
- Auto-hide when meeting apps exit
- Manual hotkey toggle override (e.g. Ctrl+Alt+O)
- No always-visible mode

### Audio & Transcription
- System audio capture via `pyaudio` + Windows WASAPI loopback (full dual-channel)
- Microphone fallback if loopback unavailable
- Chunked real-time transcription using `agent_reach.transcribe` (Groq Whisper → OpenAI fallback)
- Target latency: < 3s from speech to text in overlay

### Real-Time Answers
- Primary path: MECOS reasoner routes questions through existing LLM stack (Azure OpenAI / Ollama)
- Secondary path: `KiloBridge` subprocess wrapper writes a structured prompt file + context, spawns `kilo` CLI with timeout (default 30s), captures stdout, parses response
- Fallback: if Kilo unavailable or times out, return primary path result

### Web Scraping
- Scrapling-first (`ToolOrchestrator.scrapling_fetch`)
- Playwright fallback (`WebPerception.ingest_url`) if Scrapling fails or returns empty

### Autonomy Model (Hybrid 1 + 3)
- **Autonomous (no approval gate)**: learning, knowledge graph expansion, prompt/strategy evolution, pattern recognition, tool acquisition proposals
- **Approval-gated (outbox model)**: external actions (send email, trade, contact, file documents). Uses existing outreach outbox pattern.

### Business Layer
- Untouched. Outreach, trading, revenue, payments continue running in parallel.
- No refactoring of `outreach/`, `trading_agent.py`, `ceo_agent.py`.

---

## Implementation Phases

### Phase 1: Meeting Audio & Transcription Pipeline
**New:** `meeting_assistant.py`
- WASAPI loopback capture via `pyaudio`
- Audio chunking → `agent_reach.transcribe` → transcript segments
- Segment storage + emit to overlay via WebSocket or SSE
- Graceful fallback to microphone
- Configurable sample rate / chunk size; Windows-only filter

**Modify:** `requirements.txt`
- Add: `pywebview`, `pyaudio`, `scrapling`

---

### Phase 2: Overlay UI (FastAPI + pywebview)
**New:** `ui_overlay/`
- `routes.py` — FastAPI route serving split-panel HTML, transcript SSE endpoint, suggestion endpoint, settings toggle
- `templates/overlay.html` — single-page markdown + code-block renderer, auto-scroll, always-on-top frameless pywebview window

**Modify:** `main.py`
- Initialize overlay server at startup when assistant enabled
- Hotkey listener (`keyboard` or pywebview native) for manual show/hide

---

### Phase 3: App Perception & Auto Detection
**Modify:** `app_perception.py`
- Add meeting-app detection rules (Zoom, Teams, Google Meet) to existing `media_player` / `communication` categories
- Emit events consumed by overlay controller

**Modify:** `main.py` or new `overlay_controller.py`
- Bridge `AppPerception` events → show/hide overlay window
- Debounce rapid open/close (e.g. switching between Zoom and Teams)

---

### Phase 4: Real-Time Reasoner Integration
**New:** `assistant_engine.py`
- Subscribes to transcript segments
- Detects questions (simple LLM classifier or keyword heuristic MVP)
- Routes questions to reasoner
- Formats answer as markdown → overlay right panel

**New:** `kilo_bridge.py`
- Subprocess wrapper: write prompt file → `kilo.cmd --prompt-file <path>` → capture stdout → parse
- Timeout + fallback to `assistant_engine` primary path
- Temp directory cleanup

---

### Phase 5: Scrapling Primary + Playwright Fallback
**Modify:** `tool_orchestrator.py`
- Add `scrapling_fetch(url, **kwargs)` method as primary scraper
- On Scrapling failure (timeout / unsupported site / empty result), fallback to `WebPerception.ingest_url` (Playwright)
- Return unified result schema `{"url", "text", "links", "ok", "error"}`

**Modify:** `tool_registry.py`
- Register `scrapling_fetch` in tool registry with permission / category metadata

---

### Phase 6: Autonomous Evolution (Pattern Recognition & Self-Tuning)
**New:** `assistant_evolution.py`
- Logs interaction patterns (frequent questions, referenced files, contacts, code topics)
- Builds lightweight usage profile stored in memory
- Surfaces patterns to reasoner as context injection
- Weekly prompt tuning: benchmarks recent answers, suggests system-prompt refinements via LLM, stages changes in `data/assistant/prompt_drafts/`

**New:** `requirement_engine.py` (renamed from provisional names)
- Detects missing capability gaps (e.g. repeated failures to answer a domain)
- Proposes new tools / integrations as draft plans
- Stores proposals in `data/assistant/proposals/` for user review
- Does **not** execute without explicit approval

---

## Data Flow (Happy Path)

1. User joins Zoom/Teams/Google Meet
2. `AppPerception` detects meeting app → `overlay_controller` shows pywebview window
3. `meeting_assistant` captures system audio → chunks → Whisper → transcript segments
4. Transcript displayed in overlay left panel (auto-scroll)
5. Reasoner (or KiloBridge on code question) generates answer → overlay right panel
6. If Scrapling scrape fails → Playwright fallback invoked automatically
7. Meeting ends → `AppPerception` detects app close → overlay auto-hides
8. Summary saved to `memory_system` for future pattern recognition

---

## Rollout / Migration Path

1. Install new Python deps (`pywebview`, `pyaudio`, `scrapling`)
2. Feature flag `MECOS_ENABLE_ASSISTANT=false` by default
3. Phase 1–3 shipped first (audio + overlay + auto-detect), manual hotkey works independent of meeting detection
4. Phase 4–6 shipped in follow-up commits
5. Business/trading/outreach loops unaffected; new code runs in separate tasks

---

## Validation

- Overlay launches, positioned top-right, frameless, click-through optional
- Auto-detects Zoom/Teams/Meet start/stop within 5s
- System audio captured, transcribed, displayed real-time with < 3s latency
- Suggested answers render markdown + code syntax highlighting correctly
- KiloBridge returns answer or falls back gracefully within timeout
- Scrapling successfully extracts primary content; Playwright fallback works on sites Scrapling can’t handle
- Approval-gated actions (email, file) remain in outbox until manual review
- Existing outreach / trading tests still pass (`pytest tests/`)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| WASAPI loopback fails on some Windows audio drivers | Fallback to microphone; log warning and surface in overlay |
| pywebview threading issues with asyncio | Run overlay in dedicated `uvloop` / thread; communicate via FastAPI only |
| Kilo CLI output parsing brittleness | Strict JSON envelope with `kilo` or line-bounded parsing; timeouts hard-capped |
| Meeting detection false-positives (e.g. recording a video) | Require sustained presence (60s) before auto-show; user can always dismiss |
| Scrapling dependency bloat | Keep Playwright as fallback; both installed in requirements |
| Overlay privacy (always on) | Default off; explicit opt-in per session; hotkey to dismiss |
