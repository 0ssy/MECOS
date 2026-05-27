"""
MECOS Research Layer — Continuous Research Loop
Persistent autonomous learning loop.
"""
from __future__ import annotations

import asyncio
import time
from typing import List

from loguru import logger

from analyzer import ResearchAgent


class ContinuousResearchLoop:
    def __init__(self, research_agent: ResearchAgent):
        self.agent = research_agent
        self.is_active = False
        self.started_at = 0.0
        self.cycles = 0

    async def start(self, initial_topics: List[str] | None = None):
        self.is_active = True
        self.started_at = time.time()
        topics = initial_topics or ["machine intelligence", "autonomous runtime", "local sovereign ai"]
        logger.info("Continuous Research Loop activated")
        while self.is_active:
            for topic in list(topics):
                if not self.is_active:
                    break
                await self.agent.crawl_web([topic])
                self.cycles += 1
                expanded = f"{topic} optimization"
                if expanded not in topics:
                    topics.append(expanded)
                await asyncio.sleep(2)

    def stop(self):
        self.is_active = False
        logger.warning("Continuous Research Loop stopping...")

    def get_metrics(self):
        elapsed = max(time.time() - self.started_at, 1e-6) if self.started_at else 0.0
        return {
            "active": self.is_active,
            "cycles": int(self.cycles),
            "elapsed_seconds": elapsed,
            "cycles_per_minute": (self.cycles / max(elapsed, 1e-6)) * 60.0 if elapsed else 0.0,
        }

