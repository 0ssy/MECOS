"""
MECOS Phase 6 - Benchmarking Engine
Standardized performance evaluation, capability testing,
regression detection, and performance trend analysis.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


class BenchmarkTask:
    """A single benchmark task with evaluation criteria."""

    def __init__(
        self,
        name: str,
        prompt: str,
        expected_keywords: List[str],
        category: str = "general",
        difficulty: int = 1,
    ):
        self.name = name
        self.prompt = prompt
        self.expected_keywords = expected_keywords
        self.category = category
        self.difficulty = difficulty

    def evaluate(self, response: str) -> float:
        """Score a response based on keyword presence."""
        response_lower = response.lower()
        hits = sum(1 for kw in self.expected_keywords if kw.lower() in response_lower)
        return hits / max(len(self.expected_keywords), 1)


# Standard benchmark suite
BENCHMARK_SUITE = [
    BenchmarkTask(
        name="reasoning_basic",
        prompt="If all cats are animals and some animals are pets, can we conclude that some cats are pets?",
        expected_keywords=["not necessarily", "cannot conclude", "some", "all"],
        category="reasoning",
        difficulty=1,
    ),
    BenchmarkTask(
        name="coding_basic",
        prompt="Write a Python function to check if a string is a palindrome.",
        expected_keywords=["def", "return", "reverse", "[::-1]"],
        category="coding",
        difficulty=1,
    ),
    BenchmarkTask(
        name="planning_basic",
        prompt="List the steps to deploy a Python web application to production.",
        expected_keywords=["test", "deploy", "server", "environment", "monitor"],
        category="planning",
        difficulty=2,
    ),
    BenchmarkTask(
        name="analysis_basic",
        prompt="What are the key differences between supervised and unsupervised learning?",
        expected_keywords=["label", "cluster", "supervised", "unsupervised", "training"],
        category="analysis",
        difficulty=2,
    ),
    BenchmarkTask(
        name="trading_knowledge",
        prompt="Explain what RSI indicates and when it signals a buy opportunity.",
        expected_keywords=["oversold", "30", "momentum", "relative strength", "buy"],
        category="trading",
        difficulty=2,
    ),
    BenchmarkTask(
        name="reasoning_advanced",
        prompt="A company's revenue grew 20% but profit fell 5%. What are possible explanations?",
        expected_keywords=["cost", "expense", "margin", "overhead", "investment"],
        category="reasoning",
        difficulty=3,
    ),
    BenchmarkTask(
        name="coding_advanced",
        prompt="Explain the difference between a process and a thread, and when to use each.",
        expected_keywords=["memory", "GIL", "parallel", "concurrent", "process", "thread"],
        category="coding",
        difficulty=3,
    ),
    BenchmarkTask(
        name="meta_learning",
        prompt="How should an AI system detect that its current strategy is failing and adapt?",
        expected_keywords=["feedback", "performance", "adapt", "strategy", "monitor", "threshold"],
        category="meta",
        difficulty=4,
    ),
]


class BenchmarkingEngine:
    """
    Evaluates MECOS capabilities against standardized benchmarks.
    Tracks performance over time and detects regressions.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.results_history: List[Dict] = []
        self.save_dir = settings.MEMORY_DIR / "benchmarks"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("BenchmarkingEngine initialized.")

    def _load(self):
        path = self.save_dir / "results.json"
        if path.exists():
            self.results_history = json.loads(path.read_text())
            logger.info(f"Benchmark history loaded: {len(self.results_history)} runs")

    def _save(self):
        path = self.save_dir / "results.json"
        path.write_text(json.dumps(self.results_history[-100:], default=str))

    async def run_task(self, task: BenchmarkTask) -> Dict[str, Any]:
        """Run a single benchmark task and return the result."""
        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": task.prompt}],
            )
            answer = response.choices[0].message.content.strip()
        except Exception as e:
            answer = f"Error: {e}"

        elapsed = time.monotonic() - start
        score = task.evaluate(answer)

        return {
            "task": task.name,
            "category": task.category,
            "difficulty": task.difficulty,
            "score": round(score, 3),
            "latency_s": round(elapsed, 2),
            "response_snippet": answer[:200],
        }

    async def run_full_benchmark(self, categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run the full benchmark suite and return aggregated results."""
        tasks = BENCHMARK_SUITE
        if categories:
            tasks = [t for t in tasks if t.category in categories]

        logger.info(f"Running benchmark suite: {len(tasks)} tasks")
        task_results = []

        for task in tasks:
            result = await self.run_task(task)
            task_results.append(result)
            logger.debug(f"Benchmark [{task.name}]: score={result['score']:.3f}")

        # Aggregate
        avg_score = sum(r["score"] for r in task_results) / max(len(task_results), 1)
        by_category: Dict[str, List[float]] = {}
        for r in task_results:
            by_category.setdefault(r["category"], []).append(r["score"])
        category_scores = {cat: round(sum(scores) / len(scores), 3) for cat, scores in by_category.items()}

        run = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(task_results),
            "avg_score": round(avg_score, 3),
            "category_scores": category_scores,
            "task_results": task_results,
        }
        self.results_history.append(run)
        self._save()

        # Detect regression
        regression = self._detect_regression()

        await self.memory.add_experience(
            f"BENCHMARK RUN: avg_score={avg_score:.3f}, categories={category_scores}",
            source="benchmarking",
        )
        logger.info(f"Benchmark complete: avg_score={avg_score:.3f}")

        return {
            "avg_score": round(avg_score, 3),
            "category_scores": category_scores,
            "task_results": task_results,
            "regression_detected": regression,
        }

    def _detect_regression(self, window: int = 3, threshold: float = 0.1) -> bool:
        """Detect if recent performance has regressed compared to historical average."""
        if len(self.results_history) < window + 2:
            return False
        recent = [r["avg_score"] for r in self.results_history[-window:]]
        historical = [r["avg_score"] for r in self.results_history[:-window]]
        recent_avg = sum(recent) / len(recent)
        historical_avg = sum(historical) / len(historical)
        regression = (historical_avg - recent_avg) > threshold
        if regression:
            logger.warning(f"Performance regression detected: {historical_avg:.3f} → {recent_avg:.3f}")
        return regression

    def get_performance_trend(self) -> List[Dict[str, Any]]:
        """Return the performance trend over all benchmark runs."""
        return [
            {"timestamp": r["timestamp"], "avg_score": r["avg_score"]}
            for r in self.results_history
        ]

    def get_latest_results(self) -> Optional[Dict[str, Any]]:
        if self.results_history:
            return self.results_history[-1]
        return None
