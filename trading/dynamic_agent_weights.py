"""
trading/dynamic_agent_weights.py
Dynamic agent weight adjustment based on rolling PnL performance.

Usage:
    from trading.dynamic_agent_weights import DynamicAgentWeights
    weights = DynamicAgentWeights()
    weights.record_outcome("trend", pnl=0.005, signal="BUY")
    current_weights = weights.get_weights()
"""
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


BASE_WEIGHTS = {
    "trend":                   1.30,
    "mean_reversion":          1.10,
    "volatility":              1.00,
    "options_pricing":         0.85,
    "order_flow":              1.15,
    "liquidity_hunter":        1.00,
    "statistical_arbitrage":   0.90,
    "sentiment":               0.60,
    "reinforcement_learning":  0.50,
    "market_making":           0.90,
}

WEIGHT_FLOOR   = 0.20   # Never go below 20% of base weight
WEIGHT_CEILING = 2.00   # Never exceed 2x base weight
DECAY_FACTOR   = 0.98   # Per-trade exponential decay of old outcomes
WINDOW         = 50     # Rolling window for weight calculation
PERSIST_PATH   = Path("data/dynamic_agent_weights.json")


class DynamicAgentWeights:
    """
    Tracks rolling per-agent outcomes and adjusts weights.
    Agents that consistently generate profitable signals get higher weight.
    Agents that generate losing signals get reduced weight.
    """

    def __init__(self):
        self._outcomes: Dict[str, List[Dict]] = {k: [] for k in BASE_WEIGHTS}
        self._weights: Dict[str, float] = dict(BASE_WEIGHTS)
        self._load()
        logger.info("DynamicAgentWeights initialized")

    def record_outcome(
        self,
        agent_name: str,
        pnl: float,
        signal: str = "BUY",
        confidence: float = 0.5,
    ):
        """
        Call after a trade closes.
        agent_name: which agent generated the primary signal
        pnl: realized PnL as a fraction (0.01 = 1% gain)
        """
        base = agent_name.split(":", 1)[0]
        if base not in self._outcomes:
            self._outcomes[base] = []

        self._outcomes[base].append({
            "pnl":        float(pnl),
            "signal":     str(signal),
            "confidence": float(confidence),
            "timestamp":  time.time(),
        })

        # Keep only last WINDOW outcomes
        self._outcomes[base] = self._outcomes[base][-WINDOW:]
        self._recalculate(base)
        self._save()

    def _recalculate(self, agent_name: str):
        """Recalculate weight for one agent based on recent outcomes."""
        outcomes = self._outcomes.get(agent_name, [])
        if len(outcomes) < 5:
            # Not enough data — use base weight
            self._weights[agent_name] = BASE_WEIGHTS.get(agent_name, 1.0)
            return

        pnls = np.array([o["pnl"] for o in outcomes])

        # Exponentially weight recent outcomes
        decays = np.array([DECAY_FACTOR ** (len(pnls) - 1 - i) for i in range(len(pnls))])
        decays /= decays.sum()

        weighted_pnl  = float(np.dot(pnls, decays))
        win_rate      = float(np.mean(pnls > 0))
        sharpe_proxy  = float(np.mean(pnls) / (np.std(pnls) + 1e-9))

        # Score: combination of weighted PnL, win rate, and Sharpe
        score = (weighted_pnl * 50) + (win_rate - 0.5) + (sharpe_proxy * 0.5)

        # Map score to weight multiplier
        multiplier = float(np.clip(1.0 + score, WEIGHT_FLOOR, WEIGHT_CEILING))
        base        = BASE_WEIGHTS.get(agent_name, 1.0)
        new_weight  = float(np.clip(base * multiplier, base * WEIGHT_FLOOR, base * WEIGHT_CEILING))

        self._weights[agent_name] = new_weight
        logger.debug(
            f"[DynamicWeights] {agent_name}: score={score:.3f} "
            f"multiplier={multiplier:.2f} weight={new_weight:.3f} "
            f"(base={base:.2f})"
        )

    def get_weights(self) -> Dict[str, float]:
        return dict(self._weights)

    def get_summary(self) -> Dict:
        summary = {}
        for agent, outcomes in self._outcomes.items():
            if not outcomes:
                continue
            pnls = [o["pnl"] for o in outcomes]
            summary[agent] = {
                "weight":    round(self._weights.get(agent, BASE_WEIGHTS.get(agent, 1.0)), 3),
                "base":      round(BASE_WEIGHTS.get(agent, 1.0), 3),
                "trades":    len(pnls),
                "win_rate":  round(sum(1 for p in pnls if p > 0) / len(pnls), 3),
                "avg_pnl":   round(float(np.mean(pnls)), 5),
            }
        return summary

    def _save(self):
        try:
            PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PERSIST_PATH, "w") as f:
                json.dump({
                    "weights":  self._weights,
                    "outcomes": self._outcomes,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"DynamicAgentWeights save failed: {e}")

    def _load(self):
        if not PERSIST_PATH.exists():
            return
        try:
            with open(PERSIST_PATH) as f:
                data = json.load(f)
            self._weights  = data.get("weights", dict(BASE_WEIGHTS))
            self._outcomes = data.get("outcomes", {k: [] for k in BASE_WEIGHTS})
            logger.info(f"DynamicAgentWeights loaded from {PERSIST_PATH}")
        except Exception as e:
            logger.warning(f"DynamicAgentWeights load failed: {e}")
