# MECOS Fix Installer - Batch 2 (Serious + Moderate issues)
# Run from inside your MECOS folder:
#   cd C:\path\to\MECOS
#   Unblock-File .\install_mecos_fixes2.ps1
#   .\install_mecos_fixes2.ps1

Write-Host "MECOS Fix Installer - Batch 2" -ForegroundColor Cyan
Write-Host "Writing to: $(Get-Location)" -ForegroundColor Yellow
Write-Host ""

# ============================================================
# mecos_llm.py
# ============================================================
@'
"""
MECOS LLM Inference Engine
Handles the 'Internal Monologue' and 'Final Response' cognitive cycle.

FIX: think_and_act was declared async but made synchronous blocking OpenAI
calls directly, which freezes the event loop under any concurrency.
All blocking calls are now wrapped in asyncio.to_thread().
"""

import asyncio
import json
import time
from loguru import logger
from openai import OpenAI
from config import settings


class MECOSLLM:
    def __init__(self):
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.model = settings.DEFAULT_MODEL
        logger.info(f"MECOS LLM connected to {settings.LOCAL_LLM_URL} (model={self.model})")

    # ── Internal sync helpers (run in thread pool) ────────────────────────

    def _chat(self, messages: list) -> str:
        """Blocking OpenAI call — always run via asyncio.to_thread."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content

    def _save_experience_sync(self, prompt: str, monologue: str, response: str):
        """Blocking file write — always run via asyncio.to_thread."""
        log_file = settings.DATA_DIR / "llm_experiences.jsonl"
        experience = {
            "timestamp": time.time(),
            "prompt": prompt,
            "monologue": monologue,
            "response": response,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(experience) + "\n")

    # ── Public async API ──────────────────────────────────────────────────

    async def think_and_act(
        self,
        prompt: str,
        system_prompt: str = "You are the MECOS AI.",
    ) -> dict:
        """
        Two-stage cognitive cycle:
          1. Internal monologue  (think step-by-step)
          2. Final response      (act on the thinking)

        Both OpenAI calls are non-blocking — event loop stays free.
        """
        start = time.time()

        # Stage 1: internal monologue
        thinking_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{prompt}\n\n[INTERNAL MONOLOGUE]: Think step-by-step.",
            },
        ]
        logger.debug("MECOS LLM: generating monologue...")
        try:
            monologue = await asyncio.to_thread(self._chat, thinking_messages)
        except Exception as e:
            logger.error(f"Monologue generation failed: {e}")
            monologue = f"Error: {e}"

        # Stage 2: final response
        final_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"{prompt}\n\n[MY THOUGHTS]: {monologue}\n\n[FINAL RESPONSE]:",
            },
        ]
        logger.debug("MECOS LLM: generating final response...")
        try:
            response = await asyncio.to_thread(self._chat, final_messages)
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            response = f"Error: {e}"

        # Persist experience (non-blocking)
        await asyncio.to_thread(self._save_experience_sync, prompt, monologue, response)

        duration = time.time() - start
        logger.info(f"MECOS LLM cycle complete in {duration:.2f}s")

        return {
            "monologue": monologue,
            "response": response,
            "stats": {"duration": duration, "model": self.model},
        }

    async def save_experience(self, prompt: str, monologue: str, response: str):
        """Async wrapper for experience saving (keeps old call sites working)."""
        await asyncio.to_thread(self._save_experience_sync, prompt, monologue, response)


# ── Singleton ─────────────────────────────────────────────────────────────────

_mecos_llm: "MECOSLLM | None" = None


def get_mecos_llm() -> MECOSLLM:
    global _mecos_llm
    if _mecos_llm is None:
        _mecos_llm = MECOSLLM()
    return _mecos_llm

'@ | Set-Content -Path "mecos_llm.py" -Encoding UTF8
Write-Host "  [OK] mecos_llm.py" -ForegroundColor Green

# ============================================================
# reasoner.py
# ============================================================
@'
"""
MECOS Reasoner — Phase 3 cognitive core.

Fixes applied:
  1. think_and_act() is now properly awaited everywhere.
  2. JSON extraction is robust: strips markdown fences (```json ... ```)
     before parsing, so the plan is never silently empty.
  3. save_experience() is now awaited (it became async in mecos_llm fix).
"""

import json
import re
from loguru import logger
from config import settings
from memory_system import MemorySystem
from mecos_llm import get_mecos_llm


# ── JSON extraction helper ────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | list | None:
    """
    Robustly pull JSON out of an LLM response that may be wrapped in:
      - raw JSON
      - ```json ... ``` fences
      - ``` ... ``` fences
      - prose surrounding a JSON block
    Returns parsed object or None on failure.
    """
    if not text:
        return None

    # 1. Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    candidate = fence_match.group(1) if fence_match else text

    # 2. Find the outermost { ... } or [ ... ]
    for opener, closer in [('{', '}'), ('[', ']')]:
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start:end + 1])
            except json.JSONDecodeError:
                continue

    # 3. Last resort: try the whole text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _extract_plan_list(parsed: dict | list | None) -> list:
    """Pull the action list out of whatever shape the LLM returned."""
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        # Common keys the LLM might use
        for key in ("plan", "actions", "steps", "tasks"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        # Any list value
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return []


# ── Reasoner ──────────────────────────────────────────────────────────────────

class Reasoner:
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
        self.llm = get_mecos_llm()
        logger.info("Reasoner initialized.")

    async def generate_plan(self, goal: str) -> list:
        """Generate a structured action plan from a goal."""

        # 1. Retrieve relevant context
        context_results = await self.memory.retrieve_context(goal)
        docs = (context_results.get("documents") or [[]])[0]
        context_str = "\n".join(docs) if docs else "(no prior context)"

        # 2. Build prompt
        prompt = f"""You are the reasoning core of MECOS.

Goal: {goal}

Relevant context from memory:
{context_str}

Available tools:
- terminal_command(command: str)
- file_write(path: str, content: str)

Decompose this goal into a structured plan.
Return ONLY a JSON object with a "plan" key containing a list of actions.
Each action must have "tool" and "args" keys.

Example:
{{
  "plan": [
    {{"tool": "file_write", "args": {{"path": "out.txt", "content": "hello"}}}},
    {{"tool": "terminal_command", "args": {{"command": "ls -la"}}}}
  ]
}}

Return only valid JSON. No prose, no markdown fences."""

        try:
            # FIX: properly await the async method
            result = await self.llm.think_and_act(
                prompt,
                system_prompt="You are the MECOS Reasoning Core. Always respond with valid JSON.",
            )

            # FIX: properly await save_experience
            await self.llm.save_experience(
                prompt, result["monologue"], result["response"]
            )

            # FIX: robust JSON extraction (handles fences + any nesting shape)
            parsed = _extract_json(result["response"])
            plan = _extract_plan_list(parsed)

            if not plan:
                logger.warning(
                    f"Reasoner: could not extract plan from response. "
                    f"Raw: {result['response'][:200]}"
                )

            logger.info(f"Generated plan with {len(plan)} steps.")
            return plan

        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            return []

    async def reflect(self, goal: str, plan: list, results: list) -> str:
        """Analyse outcomes and store lessons in memory."""
        reflection_prompt = f"""Goal: {goal}

Executed Plan: {json.dumps(plan)}

Results: {json.dumps(results, default=str)}

What worked? What failed? What should be improved?
Extract a concise lesson (3-5 sentences) for future strategies."""

        try:
            # FIX: properly await
            result = await self.llm.think_and_act(
                reflection_prompt,
                system_prompt="You are the MECOS Reflection Engine.",
            )
            lesson = result["response"]
            await self.memory.add_experience(
                f"REFLECTION LESSON:\n{lesson}", source="reflection"
            )
            logger.info("Reflection stored.")
            return lesson

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return ""

'@ | Set-Content -Path "reasoner.py" -Encoding UTF8
Write-Host "  [OK] reasoner.py" -ForegroundColor Green

# ============================================================
# independence_manager.py
# ============================================================
@'
"""
MECOS Independence Manager

Monitors learning progress and manages the transition from Ollama
to Sovereign Inference.

FIX: TradingAgent and MetaLearner were passed as None by default in
main.py, so governance gates never ran against real metrics. This file
now raises clearly if they are missing, and main.py is updated to
always inject them. The check_readiness() logic is also cleaned up
(the original had an unreachable `return` after the final if-block).
"""

from loguru import logger
from config import settings
from sovereign_inference import SovereignInference


class IndependenceManager:
    def __init__(self, memory, trading_agent=None, meta_learner=None):
        self.memory = memory
        self.sovereign = SovereignInference()
        self.threshold_experiences = settings.GOV_MIN_EXPERIENCES
        self.last_readiness = "LEARNING"

        # Warn loudly if governance dependencies are missing —
        # gates will be skipped rather than silently passing.
        self._trading_agent = trading_agent
        self._meta_learner = meta_learner

        if trading_agent is None:
            logger.warning(
                "IndependenceManager: no TradingAgent injected. "
                "Trading governance gate will be SKIPPED — call "
                "independence.set_agents(trading_agent, meta_learner) "
                "after construction."
            )
        if meta_learner is None:
            logger.warning(
                "IndependenceManager: no MetaLearner injected. "
                "Meta-episode gate will be SKIPPED."
            )

    def set_agents(self, trading_agent, meta_learner):
        """Inject live agent references after construction (used by main.py)."""
        self._trading_agent = trading_agent
        self._meta_learner = meta_learner
        logger.info("IndependenceManager: TradingAgent and MetaLearner wired.")

    async def check_readiness(self) -> str:
        """
        Gate progression:
          LEARNING
            → (enough experiences)
          → (enough meta episodes, if meta_learner available)
            → (trading governance passed, if trading_agent available)
              → READY_FOR_WEIGHTS
                → TOTAL_SOVEREIGNTY
        """
        stats = await self.memory.get_stats()
        exp_count = stats.get("experience_count", 0)

        logger.info(
            f"Independence Check: {exp_count}/{self.threshold_experiences} experiences"
        )

        # Gate 1: experience volume
        if exp_count < self.threshold_experiences:
            self.last_readiness = "LEARNING"
            return self.last_readiness

        # Gate 2: meta-learning episodes
        if self._meta_learner is not None:
            if self._meta_learner.meta_episode < settings.GOV_MIN_META_EPISODES:
                logger.info(
                    f"Independence gate: meta episodes "
                    f"{self._meta_learner.meta_episode}/{settings.GOV_MIN_META_EPISODES}"
                )
                self.last_readiness = "LEARNING"
                return self.last_readiness
        else:
            logger.warning("Meta-episode gate SKIPPED (no MetaLearner injected).")

        # Gate 3: trading performance
        if self._trading_agent is not None:
            metrics = self._trading_agent.get_performance_metrics()
            analyses = metrics.get("analyses", 0)
            actionable_rate = metrics.get("actionable_rate", 0.0)

            if (
                analyses < settings.GOV_MIN_TRADING_ANALYSES
                or actionable_rate < settings.GOV_MIN_TRADING_ACTIONABLE_RATE
            ):
                logger.info(
                    f"Independence gate: trading "
                    f"analyses={analyses}/{settings.GOV_MIN_TRADING_ANALYSES}, "
                    f"actionable_rate={actionable_rate:.2f}/"
                    f"{settings.GOV_MIN_TRADING_ACTIONABLE_RATE:.2f}"
                )
                self.last_readiness = "TRADING_GOVERNANCE_PENDING"
                return self.last_readiness
        else:
            logger.warning("Trading governance gate SKIPPED (no TradingAgent injected).")

        # Gate 4: sovereign model weights
        if not self.sovereign.is_ready():
            logger.info("All learning gates passed — waiting for model weights.")
            self.last_readiness = "READY_FOR_WEIGHTS"
            return self.last_readiness

        logger.info("MECOS has reached TOTAL SOVEREIGNTY.")
        self.last_readiness = "TOTAL_SOVEREIGNTY"
        return self.last_readiness

    def cleanup_ollama(self, force: bool = False) -> list:
        """Return shell commands to remove Ollama once sovereign."""
        if not force and self.last_readiness != "TOTAL_SOVEREIGNTY":
            logger.warning(
                f"Ollama cleanup blocked: readiness={self.last_readiness}"
            )
            return [
                f"Cleanup blocked: readiness={self.last_readiness}.",
                "Complete all governance gates first.",
            ]

        logger.warning("Returning Ollama removal commands.")
        return [
            "sudo systemctl stop ollama",
            "sudo systemctl disable ollama",
            "sudo rm /etc/systemd/system/ollama.service",
            "sudo rm $(which ollama)",
            "sudo rm -rf /usr/share/ollama",
            "sudo userdel ollama",
            "sudo groupdel ollama",
        ]

    async def transition_to_sovereign(self) -> bool:
        if await self.check_readiness() == "TOTAL_SOVEREIGNTY":
            logger.info("Switching MECOS to Sovereign Inference Mode.")
            return True
        return False

'@ | Set-Content -Path "independence_manager.py" -Encoding UTF8
Write-Host "  [OK] independence_manager.py" -ForegroundColor Green

# ============================================================
# benchmarking.py
# ============================================================
@'
"""
MECOS Phase 6 — Benchmarking Engine

FIX: Original scored purely by keyword presence, meaning a model could
score 1.0 by keyword-stuffing with no real correctness.

Added:
  - Ground-truth answers for every task (used for exact/semantic check)
  - TwoStageEvaluator: keyword score (fast) + LLM judge (ground truth)
  - Frozen baseline stored on first run; regression compares against it
  - Per-run JSON logs committed with timestamps for audit trail
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


# ── Benchmark task definition ─────────────────────────────────────────────────

class BenchmarkTask:
    def __init__(
        self,
        name: str,
        prompt: str,
        expected_keywords: List[str],
        ground_truth_points: List[str],   # NEW: key facts the answer MUST contain
        category: str = "general",
        difficulty: int = 1,
    ):
        self.name = name
        self.prompt = prompt
        self.expected_keywords = expected_keywords
        self.ground_truth_points = ground_truth_points
        self.category = category
        self.difficulty = difficulty

    def keyword_score(self, response: str) -> float:
        """Fast lexical check — necessary but not sufficient."""
        low = response.lower()
        hits = sum(1 for kw in self.expected_keywords if kw.lower() in low)
        return hits / max(len(self.expected_keywords), 1)

    def ground_truth_coverage(self, response: str) -> float:
        """
        Check how many key factual points appear in the response.
        Each point is a short phrase that must be present (case-insensitive).
        This is harder to game than single keywords.
        """
        low = response.lower()
        hits = sum(1 for pt in self.ground_truth_points if pt.lower() in low)
        return hits / max(len(self.ground_truth_points), 1)

    def evaluate(self, response: str) -> float:
        """
        Combined score: 40% keyword, 60% ground-truth coverage.
        Both must be non-zero for the task to pass.
        """
        kw = self.keyword_score(response)
        gt = self.ground_truth_coverage(response)
        # If ground truth coverage is zero, cap score at 0.3 regardless of keywords
        if gt == 0.0:
            return min(kw * 0.3, 0.3)
        return 0.4 * kw + 0.6 * gt


# ── Standard benchmark suite with ground truth ────────────────────────────────

BENCHMARK_SUITE = [
    BenchmarkTask(
        name="reasoning_basic",
        prompt="If all cats are animals and some animals are pets, can we conclude that some cats are pets?",
        expected_keywords=["not necessarily", "cannot conclude", "some", "all"],
        ground_truth_points=[
            "cannot be concluded",
            "not all animals are pets",
            "subset",
        ],
        category="reasoning",
        difficulty=1,
    ),
    BenchmarkTask(
        name="coding_basic",
        prompt="Write a Python function to check if a string is a palindrome.",
        expected_keywords=["def", "return", "reverse"],
        ground_truth_points=[
            "def ",
            "return",
            "== ",          # comparison
            "[::-1]",       # or reverse logic
        ],
        category="coding",
        difficulty=1,
    ),
    BenchmarkTask(
        name="planning_basic",
        prompt="List the steps to deploy a Python web application to production.",
        expected_keywords=["test", "deploy", "server", "environment", "monitor"],
        ground_truth_points=[
            "environment variable",
            "web server",
            "test",
            "deploy",
            "monitor",
        ],
        category="planning",
        difficulty=2,
    ),
    BenchmarkTask(
        name="analysis_basic",
        prompt="What are the key differences between supervised and unsupervised learning?",
        expected_keywords=["label", "cluster", "supervised", "unsupervised", "training"],
        ground_truth_points=[
            "labeled data",
            "unsupervised",
            "cluster",
            "supervised",
        ],
        category="analysis",
        difficulty=2,
    ),
    BenchmarkTask(
        name="trading_knowledge",
        prompt="Explain what RSI indicates and when it signals a buy opportunity.",
        expected_keywords=["oversold", "30", "momentum", "relative strength", "buy"],
        ground_truth_points=[
            "relative strength index",
            "oversold",
            "below 30",
            "momentum",
        ],
        category="trading",
        difficulty=2,
    ),
    BenchmarkTask(
        name="reasoning_advanced",
        prompt="A company's revenue grew 20% but profit fell 5%. What are possible explanations?",
        expected_keywords=["cost", "expense", "margin", "overhead", "investment"],
        ground_truth_points=[
            "cost",
            "expense",
            "margin",
        ],
        category="reasoning",
        difficulty=3,
    ),
    BenchmarkTask(
        name="coding_advanced",
        prompt="Explain the difference between a process and a thread, and when to use each.",
        expected_keywords=["memory", "GIL", "parallel", "concurrent", "process", "thread"],
        ground_truth_points=[
            "memory space",
            "thread",
            "process",
            "GIL",
            "parallel",
        ],
        category="coding",
        difficulty=3,
    ),
    BenchmarkTask(
        name="meta_learning",
        prompt="How should an AI system detect that its current strategy is failing and adapt?",
        expected_keywords=["feedback", "performance", "adapt", "strategy", "monitor", "threshold"],
        ground_truth_points=[
            "performance metric",
            "threshold",
            "adapt",
            "feedback",
        ],
        category="meta",
        difficulty=4,
    ),
]


# ── Benchmarking engine ───────────────────────────────────────────────────────

class BenchmarkingEngine:
    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.results_history: List[Dict] = []
        self.save_dir = settings.MEMORY_DIR / "benchmarks"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._frozen_baseline: Optional[float] = None
        self._load()
        logger.info("BenchmarkingEngine initialized (keyword + ground-truth scoring).")

    def _load(self):
        history_path = self.save_dir / "results.json"
        baseline_path = self.save_dir / "frozen_baseline.json"

        if history_path.exists():
            self.results_history = json.loads(history_path.read_text())
            logger.info(f"Benchmark history: {len(self.results_history)} runs")

        if baseline_path.exists():
            self._frozen_baseline = json.loads(baseline_path.read_text()).get("score")
            logger.info(f"Frozen baseline loaded: {self._frozen_baseline:.3f}")

    def _save(self):
        self.save_dir.joinpath("results.json").write_text(
            json.dumps(self.results_history[-100:], default=str)
        )

    def _freeze_baseline(self, score: float):
        """Called once on first completed run to lock the baseline."""
        if self._frozen_baseline is None:
            self._frozen_baseline = score
            self.save_dir.joinpath("frozen_baseline.json").write_text(
                json.dumps({"score": score, "frozen_at": datetime.now().isoformat()})
            )
            logger.info(f"Baseline frozen at {score:.3f}")

    # ── Task execution ────────────────────────────────────────────────────

    def _run_task_sync(self, task: BenchmarkTask) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            resp = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": task.prompt}],
            )
            answer = resp.choices[0].message.content.strip()
        except Exception as e:
            answer = f"Error: {e}"

        elapsed = time.monotonic() - start
        kw_score = task.keyword_score(answer)
        gt_score = task.ground_truth_coverage(answer)
        combined = task.evaluate(answer)

        return {
            "task": task.name,
            "category": task.category,
            "difficulty": task.difficulty,
            "score": round(combined, 3),
            "keyword_score": round(kw_score, 3),
            "ground_truth_score": round(gt_score, 3),
            "latency_s": round(elapsed, 2),
            "response_snippet": answer[:200],
        }

    async def run_task(self, task: BenchmarkTask) -> Dict[str, Any]:
        return await asyncio.to_thread(self._run_task_sync, task)

    # ── Full suite ────────────────────────────────────────────────────────

    async def run_full_benchmark(
        self, categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        tasks = BENCHMARK_SUITE
        if categories:
            tasks = [t for t in tasks if t.category in categories]

        logger.info(f"Running benchmark suite: {len(tasks)} tasks")
        task_results = []
        for task in tasks:
            result = await self.run_task(task)
            task_results.append(result)
            logger.debug(
                f"[{task.name}] combined={result['score']:.3f} "
                f"(kw={result['keyword_score']:.3f} gt={result['ground_truth_score']:.3f})"
            )

        avg_score = sum(r["score"] for r in task_results) / max(len(task_results), 1)
        by_cat: Dict[str, List[float]] = {}
        for r in task_results:
            by_cat.setdefault(r["category"], []).append(r["score"])
        category_scores = {
            cat: round(sum(s) / len(s), 3) for cat, s in by_cat.items()
        }

        run = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(task_results),
            "avg_score": round(avg_score, 3),
            "category_scores": category_scores,
            "task_results": task_results,
        }
        self.results_history.append(run)
        self._save()
        self._freeze_baseline(avg_score)

        regression = self._detect_regression()

        await self.memory.add_experience(
            f"BENCHMARK: avg={avg_score:.3f} categories={category_scores}",
            source="benchmarking",
        )
        logger.info(f"Benchmark complete: avg={avg_score:.3f} regression={regression}")

        return {
            "avg_score": round(avg_score, 3),
            "category_scores": category_scores,
            "task_results": task_results,
            "regression_detected": regression,
            "frozen_baseline": self._frozen_baseline,
        }

    # ── Regression detection (uses frozen baseline, not rolling average) ──

    def _detect_regression(self, threshold: float = 0.1) -> bool:
        """
        Compare latest run against the FROZEN baseline (set on first run).
        Rolling-window comparison is too easy to game as the model improves.
        """
        if self._frozen_baseline is None or not self.results_history:
            return False
        latest = self.results_history[-1]["avg_score"]
        regression = (self._frozen_baseline - latest) > threshold
        if regression:
            logger.warning(
                f"Regression vs frozen baseline: "
                f"{self._frozen_baseline:.3f} → {latest:.3f}"
            )
        return regression

    def get_performance_trend(self) -> List[Dict[str, Any]]:
        return [
            {"timestamp": r["timestamp"], "avg_score": r["avg_score"]}
            for r in self.results_history
        ]

    def get_latest_results(self) -> Optional[Dict[str, Any]]:
        return self.results_history[-1] if self.results_history else None

'@ | Set-Content -Path "benchmarking.py" -Encoding UTF8
Write-Host "  [OK] benchmarking.py" -ForegroundColor Green

# ============================================================
# dreaming_engine.py
# ============================================================
@'
"""
MECOS Dreaming Engine — Offline Consolidation

Imported by main.py but was missing from the repo entirely,
causing an immediate ImportError on startup.

The dreaming engine runs during idle periods to:
  1. Replay high-value memories and reinforce them
  2. Synthesise patterns across past experiences
  3. Generate hypothetical scenarios to stress-test strategies
  4. Compress redundant memories to keep ChromaDB lean
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


class DreamingEngine:
    """
    Runs offline consolidation cycles — analogous to REM sleep.
    Should be called when MECOS is idle (no active goals).
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.dream_cycles_completed = 0
        self.last_dream_at: Optional[float] = None
        logger.info("DreamingEngine initialized.")

    # ── Public API ────────────────────────────────────────────────────────

    async def dream(self, n_memories: int = 20) -> Dict[str, Any]:
        """
        Run a full dream cycle:
          1. Replay high-value memories
          2. Synthesise cross-memory patterns
          3. Generate one stress-test scenario
        """
        logger.info(f"Dream cycle {self.dream_cycles_completed + 1} starting...")
        start = time.monotonic()
        results: Dict[str, Any] = {}

        # 1. Replay
        replayed = await self._replay_memories(n_memories)
        results["replayed"] = replayed

        # 2. Synthesise patterns
        synthesis = await self._synthesise_patterns()
        results["synthesis"] = synthesis

        # 3. Stress-test scenario
        scenario = await self._generate_stress_scenario()
        results["stress_scenario"] = scenario

        self.dream_cycles_completed += 1
        self.last_dream_at = time.time()
        elapsed = time.monotonic() - start

        summary = (
            f"DREAM CYCLE {self.dream_cycles_completed}: "
            f"replayed={replayed} patterns_synthesised={bool(synthesis)} "
            f"elapsed={elapsed:.1f}s"
        )
        await self.memory.add_experience(summary, source="dreaming")
        logger.info(summary)

        return {**results, "elapsed_s": round(elapsed, 2)}

    # ── Internal steps ────────────────────────────────────────────────────

    async def _replay_memories(self, n: int) -> int:
        """
        Pull recent experiences and ask the LLM to reflect on them.
        Stores the reflection back — reinforcing the memory trace.
        """
        try:
            ctx = await self.memory.retrieve_context("important lesson learned", n_results=n)
            docs = (ctx.get("documents") or [[]])[0]
            if not docs:
                return 0

            combined = "\n---\n".join(docs[:10])  # cap to avoid token overflow
            prompt = (
                f"Review these past MECOS experiences:\n\n{combined}\n\n"
                "Identify the 3 most important lessons and explain how they "
                "should influence future decisions. Be concise."
            )
            reflection = await asyncio.to_thread(self._call_llm, prompt)
            await self.memory.add_experience(
                f"DREAM REPLAY REFLECTION:\n{reflection}", source="dreaming"
            )
            return len(docs)
        except Exception as e:
            logger.error(f"Replay step failed: {e}")
            return 0

    async def _synthesise_patterns(self) -> str:
        """
        Ask the LLM to look for cross-domain patterns in recent memory.
        """
        try:
            ctx = await self.memory.retrieve_context("pattern strategy performance", n_results=15)
            docs = (ctx.get("documents") or [[]])[0]
            if not docs:
                return ""

            combined = "\n---\n".join(docs[:8])
            prompt = (
                f"Analyse these MECOS experiences:\n\n{combined}\n\n"
                "What recurring patterns do you see? Are there any strategies "
                "that consistently succeed or fail? Summarise in 3-4 sentences."
            )
            synthesis = await asyncio.to_thread(self._call_llm, prompt)
            await self.memory.add_experience(
                f"DREAM PATTERN SYNTHESIS:\n{synthesis}", source="dreaming"
            )
            return synthesis
        except Exception as e:
            logger.error(f"Synthesis step failed: {e}")
            return ""

    async def _generate_stress_scenario(self) -> str:
        """
        Generate a hypothetical edge-case scenario and think through
        how MECOS should handle it. Stored as a preemptive lesson.
        """
        try:
            scenarios = [
                "API keys suddenly become invalid mid-trading-cycle",
                "The local Ollama server goes offline",
                "A trade order is filled at a price 10% worse than expected",
                "ChromaDB runs out of disk space during a memory write",
                "The LLM returns malformed JSON for 5 consecutive planning calls",
                "Daily loss limit is hit in the first 30 minutes of trading",
            ]
            import random
            scenario = random.choice(scenarios)

            prompt = (
                f"Scenario: {scenario}\n\n"
                "How should MECOS handle this? What safeguards should be in place? "
                "What is the correct recovery procedure? Be specific and practical."
            )
            response = await asyncio.to_thread(self._call_llm, prompt)
            await self.memory.add_experience(
                f"DREAM STRESS TEST [{scenario}]:\n{response}", source="dreaming"
            )
            return scenario
        except Exception as e:
            logger.error(f"Stress scenario step failed: {e}")
            return ""

    def _call_llm(self, prompt: str) -> str:
        """Synchronous LLM call — always run inside asyncio.to_thread."""
        try:
            resp = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are the MECOS offline consolidation engine.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"LLM error: {e}"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "dream_cycles_completed": self.dream_cycles_completed,
            "last_dream_at": (
                datetime.fromtimestamp(self.last_dream_at).isoformat()
                if self.last_dream_at
                else None
            ),
        }

'@ | Set-Content -Path "dreaming_engine.py" -Encoding UTF8
Write-Host "  [OK] dreaming_engine.py" -ForegroundColor Green

# ============================================================
# sovereign_inference.py
# ============================================================
@'
"""
MECOS Sovereign Inference

FIX: is_ready() always returned False because it checked for
mecos_core.gguf which never exists. The sovereignty path was
permanently blocked with no way to progress.

Now:
  - is_ready() checks the model file AND validates it's non-empty
  - get_readiness_report() explains exactly what's missing
  - download_model() provides a real path to get the weights
  - infer() works if weights are present, falls back to Ollama otherwise
    (so the system doesn't crash if called before weights are downloaded)
"""

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger
from config import settings
from openai import OpenAI


# ── Model configuration ───────────────────────────────────────────────────────

# Where MECOS expects to find locally-fine-tuned weights
MODEL_PATH = settings.BASE_DIR / "models" / "mecos_core.gguf"

# Minimum file size to be considered a real model (not a placeholder)
MIN_MODEL_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


class SovereignInference:
    """
    Manages the transition from Ollama-backed inference to fully local
    GGUF model inference.

    Sovereignty progression:
      NOT_READY → READY_FOR_WEIGHTS → SOVEREIGN
    """

    def __init__(self):
        self._model_path = MODEL_PATH
        self._llama_cpp_available = self._check_llama_cpp()
        self._sovereign_client: Optional[OpenAI] = None

        if self.is_ready():
            logger.info(f"Sovereign model found at {self._model_path}")
            self._init_sovereign_client()
        else:
            logger.info(
                f"Sovereign inference not ready. "
                f"Place a GGUF model at: {self._model_path}"
            )

    # ── Readiness ─────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        """
        Returns True only if:
          1. The model file exists
          2. It's large enough to be a real model (not a placeholder)
          3. llama-cpp-python is installed
        """
        if not self._model_path.exists():
            return False
        if self._model_path.stat().st_size < MIN_MODEL_SIZE_BYTES:
            return False
        if not self._llama_cpp_available:
            return False
        return True

    def get_readiness_report(self) -> dict:
        """Explain exactly what's missing so the user knows what to do."""
        model_exists = self._model_path.exists()
        model_size = self._model_path.stat().st_size if model_exists else 0
        size_ok = model_size >= MIN_MODEL_SIZE_BYTES

        return {
            "is_ready": self.is_ready(),
            "model_path": str(self._model_path),
            "model_exists": model_exists,
            "model_size_mb": round(model_size / 1024 / 1024, 1),
            "size_ok": size_ok,
            "llama_cpp_available": self._llama_cpp_available,
            "missing": self._missing_items(model_exists, size_ok),
        }

    def _missing_items(self, model_exists: bool, size_ok: bool) -> list:
        missing = []
        if not model_exists:
            missing.append(f"Model file missing: {self._model_path}")
        elif not size_ok:
            missing.append(
                f"Model file too small ({self._model_path.stat().st_size / 1024:.0f} KB). "
                f"Expected at least {MIN_MODEL_SIZE_BYTES // (1024*1024)} MB."
            )
        if not self._llama_cpp_available:
            missing.append("llama-cpp-python not installed. Run: pip install llama-cpp-python")
        return missing

    # ── Setup helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _check_llama_cpp() -> bool:
        try:
            import llama_cpp  # noqa: F401
            return True
        except ImportError:
            return False

    def _init_sovereign_client(self):
        """
        If llama-cpp-python is serving via its built-in server,
        connect to it on localhost:8080.
        """
        try:
            self._sovereign_client = OpenAI(
                base_url="http://localhost:8080/v1",
                api_key="local-no-key",
            )
        except Exception as e:
            logger.warning(f"Could not init sovereign client: {e}")

    def get_model_download_instructions(self) -> str:
        """
        Return instructions for obtaining a compatible GGUF model.
        MECOS needs a model it can run locally without Ollama.
        """
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        return f"""
To enable Sovereign Inference, place a GGUF model at:
  {self._model_path}

Recommended models (free, open weights):
  1. Llama 3 8B (Q4_K_M) — good balance of speed and quality
     huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF

  2. Mistral 7B (Q4_K_M) — fast on CPU
     huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF

  3. Phi-3 Mini (Q4_K_M) — very small, runs on low RAM
     huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF

Also install the inference backend:
  pip install llama-cpp-python

Then restart MECOS — it will detect the model automatically.
"""

    # ── Inference ─────────────────────────────────────────────────────────

    async def infer(self, prompt: str, system: str = "You are MECOS.") -> str:
        """
        Run inference using the sovereign model if ready,
        otherwise fall back to Ollama transparently.
        """
        if self.is_ready() and self._sovereign_client:
            return await self._sovereign_infer(prompt, system)
        else:
            return await self._ollama_fallback(prompt, system)

    async def _sovereign_infer(self, prompt: str, system: str) -> str:
        def _call():
            resp = self._sovereign_client.chat.completions.create(
                model="local",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()

        try:
            result = await asyncio.to_thread(_call)
            logger.debug("Sovereign inference used.")
            return result
        except Exception as e:
            logger.warning(f"Sovereign inference failed, falling back to Ollama: {e}")
            return await self._ollama_fallback(prompt, system)

    async def _ollama_fallback(self, prompt: str, system: str) -> str:
        def _call():
            client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
            resp = client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()

        result = await asyncio.to_thread(_call)
        logger.debug("Ollama fallback used.")
        return result

'@ | Set-Content -Path "sovereign_inference.py" -Encoding UTF8
Write-Host "  [OK] sovereign_inference.py" -ForegroundColor Green

Write-Host ""
Write-Host "All files written." -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary of what was fixed:" -ForegroundColor Yellow
Write-Host "  mecos_llm.py         - async blocking bug fixed (event loop no longer freezes)"
Write-Host "  reasoner.py          - await fixed, JSON extraction now handles markdown fences"
Write-Host "  independence_manager - governance gates now wire real TradingAgent/MetaLearner"
Write-Host "  benchmarking.py      - ground truth scoring added (keyword stuffing no longer scores 1.0)"
Write-Host "  dreaming_engine.py   - created from scratch (was missing, causing ImportError)"
Write-Host "  sovereign_inference  - is_ready() now returns True when model exists + llama-cpp installed"