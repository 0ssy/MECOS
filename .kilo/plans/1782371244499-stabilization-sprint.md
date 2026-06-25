# Stabilization Sprint — MECOS

**Goal:** Secure leaked secrets, clean repository structure, and establish the testing/tooling baseline so MECOS is safe to iterate on.

**Sequence:** Structural cleanup → Testing foundation → Tooling baseline

---

## Prerequisites (user must do before agent runs)

1. Install `git-filter-repo`: `pip install git-filter-repo`
2. Rotate all exposed secrets at the provider consoles:
   - **Notion** (`ntn_b646517068649BKEKR9FekRQHBzEo43qa7n4Q4ieVAh23w`) — appears in both `.env` (committed commit `616209d`) and `.env.example`
   - **Slack** (`Aotc3QSvyLVqA0RRH32ahlR4`) — same exposure
   - **Alpaca** (`PKKMNAQG...` / `BvokH9c8...`)
   - **Binance** (`23ujzktH...` / `3BiR7qmI...`)
   - **Gmail app password** (`ivuv xkkh dvpk zsnh`)

3. Verify `.env is in `.gitignore` (should already be present)

---

## Task 1: Purge `.env` from all git history

**Action:** Run `git filter-repo --path .env --invert-paths` from repo root.

**Done when:**
- `git log --all -- .env` returns empty
- `git log --all --diff-filter=A --name-only --pretty=format:` returns no `.env` entry

**Follow-up:** Force-push to remote. Inform collaborators they must re-pull (or reclone after hard reset).

---

## Task 2: Clean `.env.example`

**Action:** Replace all real credential values with clearly-marked placeholders:
- `NOTION_API_KEY=ntn_b646517068649BKEKR9FekRQHBzEo43qa7n4Q4ieVAh23w` → `NOTION_API_KEY=your_notion_integration_token_here`
- `SLACK_BOT_TOKEN=xoxb-Aotc3QSvyLVqA0RRH32ahlR4` → `SLACK_BOT_TOKEN=your_slack_bot_token_here`
- Any other non-placeholder values (Brave, Granola, Zapier, GitHub) → `your_<service>_token_here`
- Confirm `TRADING_ENABLED=false` on the file (matches safe default)

**Done when:** `grep -i "key\|token\|secret\|password" .env.example` shows no real-looking token strings.

---

## Task 3: Structural cleanup (single commit)

Delete from working tree + commit:

**Debug/repair scripts (root):**
- `check_*.py` (all ~30 files)
- `fix_*.py` and `fix_*.ps1` (all ~25 files)
- `tmp_*.py` (all ~8 files)
- `.bak`, `.bak2`, `.bak3` variants (e.g. `main.py.bak`, `task_planner.py.bak`, `trading_agent.py.bak*`)
- Stray `null` file at root
- Old `engine.log` at root (contains stale Linux paths from prior deployment)

**Duplicate directories at root:**
- Root-level `docs/` (duplicate of `libs/ECC/docs/`) — remove entirely
- Root-level `plans/` — remove entirely

**Outreach stale artifacts:**
- `data/outreach/outbox/*.json` (50+ deleted outreach drafts from prior session)

**Staged/untracked cleanup already present:**
- Commit the deletion of tracked `__pycache__/` directories (root + subpackages)
- Verify `.venv/` is ignored (do not commit removal if it breaks local env)

**Add to `.gitignore` if missing lines:**
```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
*.bak

# Secrets and envs
.env
.env.local
.env.*.local

# Logs and temp
*.log
mecos_*.log
engine.log

# Random temp files
null
```

**Done when:** `git status --short` shows no tracked debug scripts, no tracked `__pycache__`, no tracked `.env`, and `.env.example` is the only `.env`-related tracked file.

---

## Task 4: Testing foundation

Add pytest config to `pyproject.toml` (create if missing):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-x --tb=short --timeout=30"
timeout = 30
```

Create `tests/test_phase_smoke.py` with import-only smoke tests for each phase:
- **Phase 1:** `MemorySystem` imports, asserts `VECTOR_DB_PATH` exists
- **Phase 2:** `PerceptionLayer`, `WebPerception`, `ScreenPerception`, `AppPerception` imports
- **Phase 3:** `Reasoner` import
- **Phase 4:** `ToolRegistry`, `CodeExecutor`, `FileOperations`, `BrowserAutomation` imports
- **Phase 5:** `TradingAgent`, `CodingAgent`, `ResearchAgent`, `OutreachAgent` imports (use `pytest.importorskip` if MECOS trading instantiation hangs on test env)
- **Phase 6:** `RLTrainer`, `SelfSupervisedTrainer`, `CurriculumManager` imports
- **Phase 7:** `GeneticOptimizer`, `StrategyEvolution`, `MetaLearner`, `WorldModel` imports

**Done when:** `pytest tests/test_phase_smoke.py -v` passes in < 30s.

---

## Task 5: Tooling baseline

Add to `pyproject.toml`:
```toml
[tool.ruff]
line-length = 100
select = ["E", "F", "I"]

[tool.mypy]
strict = false
ignore_missing_imports = true
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
```

Install locally (per-user): `pre-commit install`

**Done when:**
- `ruff check .` runs without fatal errors (warnings OK in initial state)
- `pre-commit run --all-files` passes or reports only auto-fixable issues

---

## Validation gate (run after all tasks)

1. `git log --all -- .env` → empty
2. `git log --all --diff-filter=A --name-only --pretty=format: | grep -q ".env"` → non-zero exit
3. `grep -i "key\|token\|secret\|password" .env.example | grep -i "your_" | wc -l` → equals total count of credential lines (no real secrets remain)
4. `git status --short` → no tracked debug scripts, no tracked `__pycache__`, no tracked `.env`
5. `pytest tests/test_phase_smoke.py -v` → all pass in < 30s
6. `ruff check .` → no errors (warnings tolerable)
7. `pre-commit run --all-files` → no blocking errors

---

## Out of scope (do not do in this sprint)

- Fixing `engine.log` stale paths (archival concern only; file will be deleted in Task 3)
- Rewriting `main.py` or any trading logic
- Deploying to remote or setting up CI/CD (GitHub Actions config)
- Running the full engine (`python main.py`)
- Address `libs/` sub-projects (ECC, WorldMonitor, SalesGPT, OpenOutreach) — out of scope until explicitly requested

---

## Risks

- **Force-push disturbs collaborators** — coordinate before Task 1
- **Open PRs/branches become stale** — require rebasing after history rewrite
- **`git-filter-repo` missing** — must be installed before any git mutation
- **Trading smoke tests hang** — handled via `pytest.importorskip`; never block the suite
- **Large untracked `libs/` directory** — not touched (`node_modules`, `__pycache__` inside `libs/` remain untracked noise; separate cleanup if needed later)

---

## Recommended execution order

```
Task 1 (secrets purge)
  ↓
Task 2 (.env.example cleanup)
  ↓
Task 3 (structural cleanup commit)
  ↓
Task 4 (pytest config + smoke tests)
  ↓
Task 5 (ruff + mypy + pre-commit)
  ↓
Validation gate
```
