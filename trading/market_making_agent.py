"""
Market Making Agent
Microstructure-aware spread capture and inventory balancing.
"""
from typing import Dict, Any, List
import numpy as np
from loguru import logger


class MarketMakingAgent:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Market Making Agent initialized")

    async def analyze(self, data: List[Dict], features: Dict, physics: Dict) -> Dict[str, Any]:
        if len(data) < 10:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "insufficient_data"}

        spread_pressure = float(features.get("spread_pressure", 0.0))
        liquidity = float(features.get("liquidity_score", 1.0))
        imbalance = float(features.get("order_flow_imbalance", 0.0))
        z_score = float(features.get("z_score", 0.0))

        # Market-making is most attractive in liquid, low-spread conditions.
        mm_readiness = max(0.0, liquidity) * max(0.0, 1.0 - spread_pressure * 50.0)
        confidence = float(np.clip(mm_readiness * 0.5 + abs(imbalance) * 0.3, 0.0, 0.8))

        signal = "HOLD"
        if mm_readiness > 0.6:
            # Lean against short-term order-flow pressure while respecting mean-reversion extremes.
            if imbalance > 0.25 or z_score > 1.5:
                signal = "SELL"
            elif imbalance < -0.25 or z_score < -1.5:
                signal = "BUY"
            else:
                signal = "HOLD"

        return {
            "signal": signal,
            "confidence": confidence,
            "mm_readiness": float(mm_readiness),
            "order_flow_imbalance": imbalance,
            "reason": f"mm={mm_readiness:.2f} spread={spread_pressure:.4f} imbalance={imbalance:.2f}",
        }
