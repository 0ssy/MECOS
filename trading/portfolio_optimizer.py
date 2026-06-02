from __future__ import annotations

from typing import Dict, Iterable

import numpy as np


class PortfolioOptimizer:
    """Simple optimizer utilities that are safe for live decision support."""

    @staticmethod
    def _returns(prices: Iterable[float]) -> np.ndarray:
        values = np.asarray([float(p) for p in prices if p is not None], dtype=float)
        if values.size < 2:
            return np.asarray([], dtype=float)
        prev = values[:-1]
        curr = values[1:]
        valid = prev != 0.0
        if not np.any(valid):
            return np.asarray([], dtype=float)
        return (curr[valid] / prev[valid]) - 1.0

    def recommend_single_asset(
        self,
        prices: Iterable[float],
        base_confidence: float,
        edge: float,
        regime: str,
    ) -> Dict[str, float | str]:
        rets = self._returns(prices)
        if rets.size == 0:
            return {
                "allocation_multiplier": 1.0,
                "annualized_return": 0.0,
                "annualized_volatility": 0.0,
                "sharpe_like": 0.0,
                "regime_bias": "neutral",
            }

        mu = float(np.mean(rets) * 252.0)
        vol = float(np.std(rets) * np.sqrt(252.0))
        sharpe_like = mu / vol if vol > 0 else 0.0
        conf = max(0.0, min(1.0, float(base_confidence)))
        edge_factor = max(0.5, min(1.5, 1.0 + float(edge)))
        risk_penalty = max(0.4, min(1.2, 0.18 / max(vol, 0.06)))

        regime_token = str(regime or "").lower()
        if regime_token in {"bear", "panic", "risk_off"}:
            regime_bias = "defensive"
            regime_factor = 0.75
        elif regime_token in {"bull", "trending", "risk_on"}:
            regime_bias = "pro_risk"
            regime_factor = 1.1
        else:
            regime_bias = "neutral"
            regime_factor = 0.95

        multiplier = max(0.25, min(1.25, (0.5 + conf) * edge_factor * risk_penalty * regime_factor))
        return {
            "allocation_multiplier": float(multiplier),
            "annualized_return": mu,
            "annualized_volatility": vol,
            "sharpe_like": float(sharpe_like),
            "regime_bias": regime_bias,
        }
