"""
workers/research_worker.py
Isolated research worker process.
Runs continuous web research independently of other agents.
Communicates results via multiprocessing Queue.
"""
from __future__ import annotations

import multiprocessing
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
import random
from typing import Any, Dict
from runtime.worker_process import BaseWorker


RESEARCH_TOPICS = [
    "autonomous trading strategies quantitative finance",
    "recursive self-improvement AI systems",
    "market microstructure order flow",
    "distributed systems fault tolerance",
    "reinforcement learning financial markets",
    "knowledge graph reasoning",
    "meta-learning few-shot adaptation",
    "volatility forecasting models",
    "agent coordination protocols",
    "sovereign AI infrastructure",
]

MODIFIERS = ["optimization", "architecture", "implementation", "analysis", "benchmarks"]


class ResearchWorkerProcess(BaseWorker):
    def __init__(self, worker_id, inbox, outbox, cycle_interval=45.0):
        super().__init__(worker_id, inbox, outbox, cycle_interval)
        self._visited = set()
        self._cycle_count = 0

    def run_cycle(self) -> Dict[str, Any]:
        # Select topic
        if not self._visited or random.random() < 0.3:
            topic = random.choice(RESEARCH_TOPICS)
        else:
            seed  = random.choice(list(self._visited))
            words = seed.split()[:3]
            topic = " ".join(words) + " " + random.choice(MODIFIERS)

        self._visited.add(topic)
        self._cycle_count += 1

        # Simulate research (in real deployment, this calls the actual ResearchAgent)
        result = {
            "topic":       topic,
            "cycle":       self._cycle_count,
            "timestamp":   time.time(),
            "discoveries": 1,
            "worker_id":   self.worker_id,
        }

        # Send to main process for memory storage
        self._send_result("research_result", result)
        return result


def run_research_worker(worker_id: str, inbox: multiprocessing.Queue,
                        outbox: multiprocessing.Queue, cycle_interval: float):
    worker = ResearchWorkerProcess(worker_id, inbox, outbox, cycle_interval)
    worker.start()
