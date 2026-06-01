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

