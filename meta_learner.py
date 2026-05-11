"""
MECOS Phase 7 - Meta-Learner
Learning to learn: detects failure patterns, adapts hyperparameters,
selects optimal strategies, and coordinates all learning subsystems.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from rl_trainer import RLTrainer
from self_supervised_trainer import SelfSupervisedTrainer
from curriculum_manager import CurriculumManager
from memory_consolidation import MemoryConsolidation
from benchmarking import BenchmarkingEngine
from strategy_evolution import StrategyEvolution
from genetic_optimizer import GeneticOptimizer
from config import settings
from openai import OpenAI


# Hyperparameter search space for genetic optimization
HYPERPARAMETER_SPACE = {
    "learning_rate": {"type": "float", "min": 0.001, "max": 0.5},
    "exploration_rate": {"type": "float", "min": 0.05, "max": 1.0},
    "memory_retrieval_n": {"type": "int", "min": 3, "max": 20},
    "planning_depth": {"type": "int", "min": 1, "max": 8},
    "consolidation_threshold": {"type": "float", "min": 0.1, "max": 0.9},
    "strategy_mutation_rate": {"type": "float", "min": 0.05, "max": 0.5},
}


class MetaLearner:
    """
    The meta-learning coordinator for MECOS.
    Monitors all learning subsystems, detects performance issues,
    adapts learning parameters, and orchestrates evolution cycles.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")

        # Initialize all learning subsystems
        self.rl_trainer = RLTrainer(memory, domain="general")
        self.ssl_trainer = SelfSupervisedTrainer(memory)
        self.curriculum = CurriculumManager(memory)
        self.consolidation = MemoryConsolidation(memory)
        self.benchmarking = BenchmarkingEngine(memory)
        self.strategy_evolution = StrategyEvolution(memory)
        self.genetic_optimizer = GeneticOptimizer(memory)

        # Meta-learning state
        self.meta_episode = 0
        self.performance_baseline: Optional[float] = None
        self.hyperparams: Dict[str, Any] = {
            "learning_rate": 0.1,
            "exploration_rate": 0.3,
            "memory_retrieval_n": 5,
            "planning_depth": 3,
            "consolidation_threshold": 0.3,
            "strategy_mutation_rate": 0.15,
        }
        self.adaptation_log: List[Dict] = []

        self.save_dir = settings.MEMORY_DIR / "meta"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info("MetaLearner initialized with all learning subsystems.")

    def _load(self):
        path = self.save_dir / "meta_state.json"
        if path.exists():
            data = json.loads(path.read_text())
            self.meta_episode = data.get("meta_episode", 0)
            self.performance_baseline = data.get("performance_baseline")
            self.hyperparams.update(data.get("hyperparams", {}))
            self.adaptation_log = data.get("adaptation_log", [])
            logger.info(f"Meta-learner state loaded: episode={self.meta_episode}")

    def _save(self):
        path = self.save_dir / "meta_state.json"
        data = {
            "meta_episode": self.meta_episode,
            "performance_baseline": self.performance_baseline,
            "hyperparams": self.hyperparams,
            "adaptation_log": self.adaptation_log[-50:],
            "timestamp": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, default=str))

    async def run_meta_cycle(self) -> Dict[str, Any]:
        """
        Run a full meta-learning cycle:
        1. Benchmark current performance
        2. Detect failures / regressions
        3. Consolidate memories
        4. Train from replay (RL)
        5. Self-supervised training
        6. Evolve strategies if needed
        7. Adapt hyperparameters
        """
        self.meta_episode += 1
        logger.info(f"Meta-learning cycle {self.meta_episode} starting...")
        results = {}

        # 1. Benchmark
        bench_results = await self.benchmarking.run_full_benchmark()
        current_score = bench_results["avg_score"]
        results["benchmark_score"] = current_score
        results["regression"] = bench_results.get("regression_detected", False)

        # 2. Detect failures and adapt
        adaptation = await self._detect_and_adapt(current_score, bench_results)
        results["adaptation"] = adaptation

        # 3. Memory consolidation
        consolidation_result = await self.consolidation.consolidate(n_memories=30)
        results["consolidation"] = consolidation_result

        # 4. RL training from replay
        await self.rl_trainer.train_from_replay(batch_size=16)
        results["rl_stats"] = self.rl_trainer.get_stats()

        # 5. SSL training
        ssl_result = await self.ssl_trainer.train_from_memory(n_samples=5)
        results["ssl_result"] = ssl_result

        # 6. Strategy evolution (every 5 cycles)
        if self.meta_episode % 5 == 0:
            evolution_result = await self.strategy_evolution.evolve_generation()
            results["strategy_evolution"] = evolution_result

        # 7. Update baseline
        if self.performance_baseline is None:
            self.performance_baseline = current_score
        else:
            self.performance_baseline = 0.9 * self.performance_baseline + 0.1 * current_score

        self._save()

        await self.memory.add_experience(
            f"META CYCLE {self.meta_episode}: score={current_score:.3f}, "
            f"baseline={self.performance_baseline:.3f}, "
            f"regression={results['regression']}",
            source="meta_learner",
        )
        logger.info(f"Meta cycle {self.meta_episode} complete: score={current_score:.3f}")
        return results

    async def _detect_and_adapt(self, current_score: float, bench_results: Dict) -> Dict[str, Any]:
        """Detect performance issues and adapt hyperparameters."""
        if self.performance_baseline is None:
            return {"action": "baseline_set", "score": current_score}

        delta = current_score - self.performance_baseline
        adaptation = {"score": current_score, "baseline": self.performance_baseline, "delta": delta}

        if delta < -0.1:
            # Performance regression — increase exploration, reduce learning rate
            logger.warning(f"Performance regression detected: delta={delta:.3f}")
            self.hyperparams["exploration_rate"] = min(0.8, self.hyperparams["exploration_rate"] * 1.2)
            self.hyperparams["learning_rate"] = max(0.001, self.hyperparams["learning_rate"] * 0.8)
            adaptation["action"] = "increased_exploration"

            # Ask LLM for diagnosis
            diagnosis = await self._diagnose_regression(bench_results)
            adaptation["diagnosis"] = diagnosis

        elif delta > 0.05:
            # Improvement — reduce exploration, increase learning rate slightly
            logger.info(f"Performance improvement: delta={delta:.3f}")
            self.hyperparams["exploration_rate"] = max(0.05, self.hyperparams["exploration_rate"] * 0.95)
            self.hyperparams["learning_rate"] = min(0.3, self.hyperparams["learning_rate"] * 1.05)
            adaptation["action"] = "consolidated_gains"
        else:
            adaptation["action"] = "stable"

        self.adaptation_log.append({
            "episode": self.meta_episode,
            "timestamp": datetime.now().isoformat(),
            **adaptation,
        })
        return adaptation

    async def _diagnose_regression(self, bench_results: Dict) -> str:
        """Use LLM to diagnose why performance regressed."""
        category_scores = bench_results.get("category_scores", {})
        weak_categories = [cat for cat, score in category_scores.items() if score < 0.5]

        prompt = f"""MECOS performance has regressed. Diagnose the likely cause.

Category scores: {json.dumps(category_scores)}
Weak categories: {weak_categories}
Current hyperparameters: {json.dumps(self.hyperparams)}

Provide a brief diagnosis (2-3 sentences) and suggest the most important fix."""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Diagnosis failed: {e}"

    async def optimize_hyperparameters(self, n_generations: int = 5) -> Dict[str, Any]:
        """Use genetic optimization to find better hyperparameters."""
        logger.info("Starting hyperparameter optimization...")

        def fitness_fn(genome: Dict[str, Any]) -> float:
            # Simulate fitness based on hyperparameter plausibility
            score = 0.5
            if 0.01 <= genome.get("learning_rate", 0) <= 0.2:
                score += 0.2
            if 0.1 <= genome.get("exploration_rate", 0) <= 0.5:
                score += 0.2
            if 3 <= genome.get("memory_retrieval_n", 0) <= 10:
                score += 0.1
            return score

        best = await self.genetic_optimizer.evolve(
            fitness_fn=fitness_fn,
            genome_template=HYPERPARAMETER_SPACE,
            n_generations=n_generations,
        )

        # Apply best hyperparameters
        self.hyperparams.update(best.genome)
        self._save()
        logger.info(f"Hyperparameters optimized: {best.genome}")

        await self.memory.add_experience(
            f"HYPERPARAMETER OPTIMIZATION: fitness={best.fitness:.3f}, params={best.genome}",
            source="meta_learner",
        )
        return {"best_fitness": best.fitness, "hyperparams": best.genome}

    def get_learning_status(self) -> Dict[str, Any]:
        """Return a comprehensive status of all learning subsystems."""
        return {
            "meta_episode": self.meta_episode,
            "performance_baseline": round(self.performance_baseline or 0.0, 3),
            "hyperparams": self.hyperparams,
            "rl_stats": self.rl_trainer.get_stats(),
            "ssl_stats": self.ssl_trainer.get_stats(),
            "curriculum": self.curriculum.get_skill_summary(),
            "active_strategy": self.strategy_evolution.active_strategy.name if self.strategy_evolution.active_strategy else "none",
            "genetic_optimizer": self.genetic_optimizer.get_stats(),
        }
