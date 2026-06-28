# Outreach Pipeline Finish

## Goal
Run the full outreach pipeline end-to-end: scanner → synthesizer → review_outbox → send, using real SearXNG results instead of test/aggregator data.

## Current State
- SearXNG Docker container starts correctly via `run_mecos.py` and responds on `localhost:8888`
- Scanner queries return results but mostly GitHub repos (aggregator-blocklist now includes github.com)
- `run_mecos.py` launches `main.py` but MECOS crashes on startup due to two bugs:
  1. Ollama model name mismatch (`llama3` requested, only `llama3.1:8b` / `llama3.2:3b` available)
  2. Health monitor await bug (`HealthCheck` object awaited in non-async context)

## Steps

1. **Fix Ollama model name** in `mecos_llm.py` — change default model from `llama3` to `llama3.2:3b` (or `llama3.1:8b`).
2. **Fix health monitor await bug** in `health_monitor.py` — remove or guard the `await` on `HealthCheck` object in the non-async periodic check path.
3. **Run scanner** via `python outreach/review_outbox.py` or direct scanner call to confirm leads are scored ≥3 and non-aggregator domains.
4. **Run synthesizer** on discovered leads to populate `data/outreach/synthesized_leads.json` with viable briefs.
5. **Run `python outreach/review_outbox.py list`** to verify drafts appear.
6. **Approve a draft** and send via SMTP using the throttled `send` command.

## Validation
- MECOS starts cleanly without crashes when running `python run_mecos.py`
- Leads in `leads.json` have score ≥3 and real business domains
- `synthesized_leads.json` contains at least one valid lead brief
- `review_outbox.py list` shows drafts ready for approval
- No unhandled exceptions during pipeline execution
