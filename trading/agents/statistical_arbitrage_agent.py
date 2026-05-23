import numpy as np
from statsmodels.tsa.stattools import coint
from typing import Dict, Any, List
from loguru import logger


class StatisticalArbitrageAgent:
    def __init__(self, memory_system):
        self.memory = memory_system
        logger.info("StatisticalArbitrageAgent initialized.")

    async def analyze(self, data: Dict[str, List[Dict]], params: Dict = None) -> Dict[str, Any]:
        """Analyzes two assets for cointegration and spread deviation."""
        params = params or {}

        if not isinstance(data, dict) or len(data) != 2:
            return {"signal": "HOLD", "confidence": 0, "reason": "Requires exactly two assets for analysis"}

        asset_names = list(data.keys())
        asset_a_data = data[asset_names[0]]
        asset_b_data = data[asset_names[1]]

        closes_a = np.array([d["close"] for d in asset_a_data])
        closes_b = np.array([d["close"] for d in asset_b_data])

        min_len = min(len(closes_a), len(closes_b))
        if min_len < 60:
            return {"signal": "HOLD", "confidence": 0, "reason": "Insufficient data for cointegration"}

        closes_a = closes_a[-min_len:]
        closes_b = closes_b[-min_len:]

        try:
            _, pvalue, _ = coint(closes_a, closes_b)
        except ValueError:
            return {"signal": "HOLD", "confidence": 0, "reason": "Cointegration test failed (e.g., all same values)"}

        if pvalue > 0.05:
            return {"signal": "HOLD", "confidence": 0, "reason": f"Assets not cointegrated (p-value: {pvalue:.2f})"}

        spread = closes_a - closes_b
        mean = np.mean(spread)
        std = np.std(spread)
        z_score = (spread[-1] - mean) / std if std > 0 else 0

        signal = "HOLD"
        confidence = 0.0
        threshold = params.get("z_score_threshold", 2.0)

        if z_score > threshold:
            signal = "SELL_SPREAD"
            confidence = min(abs(z_score) / threshold, 1.0)
        elif z_score < -threshold:
            signal = "BUY_SPREAD"
            confidence = min(abs(z_score) / threshold, 1.0)

        logger.info(
            f"StatArb for {asset_names[0]}/{asset_names[1]}: "
            f"Z-score={z_score:.2f}, Signal={signal}, Confidence={confidence:.2f}"
        )

        return {
            "signal": signal,
            "confidence": float(confidence),
            "cointegration_pvalue": float(pvalue),
            "z_score": float(z_score),
            "spread_mean": float(mean),
            "spread_std": float(std),
            "asset_a": asset_names[0],
            "asset_b": asset_names[1]
        }

    async def find_arbitrage(self, data: Dict[str, List[Dict]], params: Dict = None) -> Dict[str, Any]:
        """Alias for analyze method."""
        return await self.analyze(data, params)
