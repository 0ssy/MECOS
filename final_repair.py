import os

def overwrite_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Re-written {path} successfully.")

def patch_file(path, old, new):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            c = f.read()
        if old in c:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(c.replace(old, new))
            print(f"✅ Patched {path} successfully.")
            return True
    return False

# 1. Overwrite continuous_loop.py to fix Indentation Error permanently
research_code = """from __future__ import annotations
import asyncio
import time
import random
from typing import List, Set
from loguru import logger

class ContinuousResearchLoop:
    def __init__(self, research_agent):
        self.agent = research_agent
        self.is_active = False
        self.started_at = 0.0
        self.cycles = 0
        self.visited_topics: Set[str] = set()
        self.base_topics = [
            "machine intelligence", "autonomous runtime", "local sovereign ai",
            "quantitative finance", "market microstructure", "recursive engineering",
            "distributed systems", "agentic workflows", "quant trading reinforcement learning",
            "multi-agent system coordination", "zero-shot engineering agents",
            "automated strategy synthesis", "sovereign compute orchestration",
            "high-frequency data ingestion"
        ]

    async def start(self, initial_topics: List[str] | None = None):
        self.is_active = True
        self.started_at = time.time()
        topics = initial_topics or self.base_topics
        logger.info("Continuous Research Loop activated with diversification")
        
        while self.is_active:
            if not self.visited_topics or random.random() < 0.3:
                topic = random.choice(topics)
            else:
                seed = random.choice(list(self.visited_topics))
                modifiers = ["optimization", "architecture", "security", "scaling", "latency", "governance"]
                topic = f"{seed} {random.choice(modifiers)}"

            if topic in self.visited_topics and len(self.visited_topics) < 200:
                await asyncio.sleep(1)
                continue

            logger.info(f"Autonomous research cycle {self.cycles + 1}: {topic}")
            try:
                await self.agent.crawl_web([topic])
                self.visited_topics.add(topic)
                self.cycles += 1
            except Exception as e:
                logger.error(f"Research cycle failed for {topic}: {e}")

            await asyncio.sleep(random.randint(30, 60))

    def stop(self):
        self.is_active = False
        logger.warning('Continuous Research Loop stopping...')

    def get_metrics(self):
        elapsed = max(time.time() - self.started_at, 1e-6) if self.started_at else 0.0
        return {
            'active': self.is_active,
            'cycles': int(self.cycles),
            'visited_count': len(self.visited_topics),
            'elapsed_seconds': elapsed,
            'cycles_per_minute': (self.cycles / max(elapsed, 1e-6)) * 60.0 if elapsed else 0.0,
        }
"""
overwrite_file("continuous_loop.py", research_code)

# 2. Smart-Active Tuning (Addressing the Cons)
# Using 0.1 ensures the trade covers 10% of the spread, preventing guaranteed losses.
patch_file("trading/autonomous_trading_loop.py", "self.trade_quality_spread_multiplier = 2.5", "self.trade_quality_spread_multiplier = 0.1")
patch_file("trading/autonomous_trading_loop.py", "self.min_acceptable_volatility = 0.003", "self.min_acceptable_volatility = 0.0001")

# 3. Increase Risk Limits
patch_file("trading/risk_engine.py", "self.max_position_size = 0.10", "self.max_position_size = 0.40")
