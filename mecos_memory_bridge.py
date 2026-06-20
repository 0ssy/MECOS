"""
MECOS Memory Bridge
Bidirectionally flows data between:
  - NeuralMemoryBank (trading brain, differentiable)
  - MemorySystem (semantic ChromaDB, system-wide)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class MemoryBridge:
    """Bidirectional sync between differentiable neural memory and semantic ChromaDB."""

    def __init__(self, neural_brain_service=None, memory_system=None):
        self.brain_service = neural_brain_service
        self.memory_system = memory_system
        self._last_sync_ts = 0.0

    def push_neural_to_semantic(self, ticker: str, result: Dict[str, Any]) -> None:
        if self.memory_system is None:
            return
        try:
            action = result.get("action", "hold")
            uncertainty = float(result.get("uncertainty", 1.0) or 1.0)
            explanation = result.get("explanation", "")
            memory_sim = result.get("memory_similarity", 0.0)
            parts = [
                f"NeuralBrain [{ticker}] -> action={action}",
                f"uncertainty={uncertainty:.4f}",
                f"memory_similarity={float(memory_sim):.4f}",
            ]
            if explanation:
                parts.append(str(explanation)[:300])
            content = " | ".join(parts)
            self.memory_system.add_experience(
                content=content,
                source="neural_brain_sync",
                metadata={
                    "ticker": str(ticker),
                    "action": str(action),
                    "uncertainty": float(uncertainty),
                    "memory_similarity": float(memory_sim),
                    "timestamp_unix": float(time.time()),
                },
            )
        except Exception:
            pass

    def push_ppo_updates(self, updates: List[Dict[str, Any]]) -> None:
        if self.memory_system is None or not updates:
            return
        try:
            for update in updates:
                reward = float(update.get("reward", 0.0) or 0.0)
                ticker = str(update.get("ticker", "SYS"))
                outcome = str(update.get("outcome", "unknown"))
                content = (
                    f"PPO update [{ticker}] reward={reward:.6f} outcome={outcome}"
                )
                self.memory_system.add_experience(
                    content=content,
                    source="ppo_sync",
                    metadata={
                        "ticker": ticker,
                        "reward": float(reward),
                        "outcome": outcome,
                        "timestamp_unix": float(time.time()),
                    },
                )
        except Exception:
            pass

    async def sync_after_brain_inference(self, ticker: str, result: Dict[str, Any]) -> None:
        self.push_neural_to_semantic(ticker, result)
        now = time.monotonic()
        if now - self._last_sync_ts < 300:
            return
        self._last_sync_ts = now
        try:
            if self.brain_service and self.brain_service.brain is not None:
                self.brain_service.brain.memory.save()
        except Exception:
            pass
