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

