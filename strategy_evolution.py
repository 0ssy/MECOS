"""
MECOS Phase 7 - Strategy Evolution
Automated strategy generation, mutation, evaluation, and selection.
Evolves planning strategies, reasoning approaches, and action policies.
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from loguru import logger

from memory_system import MemorySystem
from config import settings
from openai import OpenAI


class Strategy:
    """A behavioral strategy with a description and performance record."""

    def __init__(self, name: str, description: str, rules: List[str]):
        self.name = name
        self.description = description
        self.rules = rules  # List of behavioral rules
        self.performance_scores: List[float] = []
        self.generation = 0

    @property
    def avg_performance(self) -> float:
        if not self.performance_scores:
            return 0.0
        return sum(self.performance_scores) / len(self.performance_scores)

    def record_performance(self, score: float):
        self.performance_scores.append(score)
        # Keep last 20 scores
        if len(self.performance_scores) > 20:
            self.performance_scores = self.performance_scores[-20:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "rules": self.rules,
            "avg_performance": round(self.avg_performance, 3),
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Strategy":
        s = cls(data["name"], data["description"], data.get("rules", []))
        s.generation = data.get("generation", 0)
        return s


# Seed strategies for initial population
SEED_STRATEGIES = [
    Strategy(
        name="conservative_planner",
        description="Break tasks into small, safe steps. Verify each step before proceeding.",
        rules=[
            "Always decompose tasks into steps of 3 or fewer actions",
            "Verify output before proceeding to next step",
            "Prefer reversible actions over irreversible ones",
            "Ask for clarification when uncertain",
        ],
    ),
    Strategy(
        name="aggressive_executor",
        description="Execute plans quickly with minimal verification. Optimize for speed.",
        rules=[
            "Execute all steps in parallel when possible",
            "Skip verification for low-risk actions",
            "Use the most powerful tool available",
            "Retry failures immediately without analysis",
        ],
    ),
    Strategy(
        name="research_first",
        description="Always gather information before acting. Make data-driven decisions.",
        rules=[
            "Research the topic before taking any action",
            "Retrieve relevant memories before planning",
            "Validate assumptions with external sources",
            "Document findings before execution",
        ],
    ),
    Strategy(
        name="adaptive_hybrid",
        description="Adapt strategy based on task type and past performance.",
        rules=[
            "Classify task complexity before choosing approach",
            "Use conservative approach for high-risk tasks",
            "Use aggressive approach for well-understood tasks",
            "Learn from failures and adjust strategy",
        ],
    ),
]


class StrategyEvolution:
    """
    Evolves behavioral strategies for MECOS through mutation, crossover,
    and performance-based selection.
    """

    def __init__(self, memory: MemorySystem):
        self.memory = memory
        self.client = OpenAI(base_url=settings.LOCAL_LLM_URL, api_key="local-no-key")
        self.strategies: List[Strategy] = list(SEED_STRATEGIES)
        self.active_strategy: Optional[Strategy] = self.strategies[3]  # Start with adaptive
        self.generation = 0
        self.save_dir = settings.MEMORY_DIR / "evolution"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._load()
        logger.info(f"StrategyEvolution initialized: {len(self.strategies)} strategies")

    def _load(self):
        path = self.save_dir / "strategies.json"
        if path.exists():
            data = json.loads(path.read_text())
            loaded = [Strategy.from_dict(s) for s in data.get("strategies", [])]
            if loaded:
                self.strategies = loaded
            self.generation = data.get("generation", 0)
            active_name = data.get("active_strategy")
            if active_name:
                self.active_strategy = next((s for s in self.strategies if s.name == active_name), self.strategies[-1])
            logger.info(f"Strategies loaded: {len(self.strategies)} (gen {self.generation})")

    def _save(self):
        path = self.save_dir / "strategies.json"
        data = {
            "strategies": [s.to_dict() for s in self.strategies],
            "generation": self.generation,
            "active_strategy": self.active_strategy.name if self.active_strategy else None,
            "timestamp": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, default=str))

    async def mutate_strategy(self, strategy: Strategy) -> Strategy:
        """Use the LLM to generate a mutated variant of a strategy."""
        rules_text = "\n".join(f"- {r}" for r in strategy.rules)
        prompt = f"""You are evolving an AI behavioral strategy.

Current strategy: {strategy.name}
Description: {strategy.description}
Rules:
{rules_text}

Create a mutated variant by:
1. Modifying 1-2 rules to improve performance
2. Adding one new rule
3. Keeping the core approach but improving it

Return JSON:
{{
    "name": "mutated_name",
    "description": "brief description",
    "rules": ["rule1", "rule2", "rule3", "rule4"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            mutated = Strategy(
                name=data.get("name", f"{strategy.name}_mut"),
                description=data.get("description", strategy.description),
                rules=data.get("rules", strategy.rules),
            )
            mutated.generation = self.generation + 1
            logger.info(f"Strategy mutated: {strategy.name} → {mutated.name}")
            return mutated
        except Exception as e:
            logger.error(f"Strategy mutation failed: {e}")
            return strategy

    async def crossover_strategies(self, s1: Strategy, s2: Strategy) -> Strategy:
        """Combine two strategies to create a hybrid."""
        rules_s1 = "\n".join(f"- {r}" for r in s1.rules)
        rules_s2 = "\n".join(f"- {r}" for r in s2.rules)
        prompt = f"""Combine these two AI strategies into a superior hybrid.

Strategy 1: {s1.name}
Rules:
{rules_s1}

Strategy 2: {s2.name}
Rules:
{rules_s2}

Create a hybrid that takes the best elements from both.
Return JSON:
{{
    "name": "hybrid_name",
    "description": "brief description",
    "rules": ["rule1", "rule2", "rule3", "rule4", "rule5"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            hybrid = Strategy(
                name=data.get("name", f"{s1.name}_{s2.name}_hybrid"),
                description=data.get("description", "Hybrid strategy"),
                rules=data.get("rules", s1.rules + s2.rules),
            )
            hybrid.generation = self.generation + 1
            logger.info(f"Strategy crossover: {s1.name} × {s2.name} → {hybrid.name}")
            return hybrid
        except Exception as e:
            logger.error(f"Strategy crossover failed: {e}")
            return s1

    def record_performance(self, score: float):
        """Record performance for the currently active strategy."""
        if self.active_strategy:
            self.active_strategy.record_performance(score)
            logger.debug(f"Strategy [{self.active_strategy.name}]: score={score:.3f}, avg={self.active_strategy.avg_performance:.3f}")

    def select_best_strategy(self) -> Strategy:
        """Select the strategy with the best average performance."""
        if not self.strategies:
            return SEED_STRATEGIES[3]
        best = max(self.strategies, key=lambda s: s.avg_performance)
        return best

    async def evolve_generation(self) -> Dict[str, Any]:
        """
        Run one generation of strategy evolution:
        1. Evaluate current strategies
        2. Select top performers
        3. Mutate and crossover
        4. Replace worst performers
        """
        self.generation += 1
        logger.info(f"Strategy evolution generation {self.generation}")

        # Sort by performance
        self.strategies.sort(key=lambda s: s.avg_performance, reverse=True)
        top_strategies = self.strategies[:max(2, len(self.strategies) // 2)]

        new_strategies = list(top_strategies)

        # Mutate top strategies
        for s in top_strategies[:2]:
            mutated = await self.mutate_strategy(s)
            new_strategies.append(mutated)

        # Crossover top 2
        if len(top_strategies) >= 2:
            hybrid = await self.crossover_strategies(top_strategies[0], top_strategies[1])
            new_strategies.append(hybrid)

        # Keep population bounded
        self.strategies = new_strategies[:8]

        # Update active strategy to best performer
        self.active_strategy = self.select_best_strategy()
        self._save()

        await self.memory.add_experience(
            f"STRATEGY EVOLUTION gen={self.generation}: "
            f"active={self.active_strategy.name}, "
            f"performance={self.active_strategy.avg_performance:.3f}",
            source="strategy_evolution",
        )

        return {
            "generation": self.generation,
            "strategies": len(self.strategies),
            "active_strategy": self.active_strategy.name,
            "best_performance": self.active_strategy.avg_performance,
        }

    def get_active_rules(self) -> List[str]:
        """Return the rules of the currently active strategy."""
        if self.active_strategy:
            return self.active_strategy.rules
        return []

    def get_all_strategies(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.strategies]
