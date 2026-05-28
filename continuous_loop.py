"""
MECOS Research Layer — Continuous Research Loop
Persistent autonomous learning loop.
"""
from __future__ import annotations

import asyncio
import random
import time
from typing import List, Set

from loguru import logger

from analyzer import ResearchAgent


class ContinuousResearchLoop:
    def __init__(self, research_agent: ResearchAgent):
        self.agent = research_agent
        self.is_active = False
        self.started_at = 0.0
        self.cycles = 0
        self.visited_topics: Set[str] = set()
        self.base_topics = [
            "machine intelligence",
            "autonomous runtime",
            "local sovereign ai",
            "quantitative finance",
            "market microstructure",
            "recursive engineering",
            "distributed systems",
            "agentic workflows",
            "reinforcement learning for trading",
            "multi-agent coordination systems",
            "portfolio optimization under uncertainty",
            "market regime detection models",
            "execution microstructure modeling",
            "risk-aware policy gradients",
        ]

    async def start(self, initial_topics: List[str] | None = None):
        self.is_active = True
        self.started_at = time.time()
        topics = initial_topics or self.base_topics
        logger.info("Continuous Research Loop activated with diversification")
        while self.is_active:
            if not self.visited_topics or random.random() < 0.2:
                topic = random.choice(topics)
            else:
                seed = random.choice(list(self.visited_topics))
                modifier = random.choice(["optimization", "architecture", "security", "scaling", "latency", "governance"])
                topic = f"{seed} {modifier}"

            if topic in self.visited_topics and len(self.visited_topics) < 120:
                await asyncio.sleep(1)
                continue

            logger.info(f"Autonomous research cycle {self.cycles + 1}: {topic}")
            try:
                await self.agent.crawl_web([topic])
                self.visited_topics.add(topic)
                self.cycles += 1
            except Exception as exc:
                logger.error(f"Research cycle failed for {topic}: {exc}")

            await asyncio.sleep(random.randint(10, 25))

    def stop(self):
        self.is_active = False
        logger.warning("Continuous Research Loop stopping...")

    def get_metrics(self):
        elapsed = max(time.time() - self.started_at, 1e-6) if self.started_at else 0.0
        return {
            "active": self.is_active,
            "cycles": int(self.cycles),
            "visited_count": len(self.visited_topics),
            "elapsed_seconds": elapsed,
            "cycles_per_minute": (self.cycles / max(elapsed, 1e-6)) * 60.0 if elapsed else 0.0,
        }

