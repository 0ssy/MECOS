import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint
from typing import Dict, Any, List
from loguru import logger

class StatisticalArbitrageEngine:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Statistical Arbitrage Engine initialized")

    async def analyze_pair(self,
                           asset_a: List[Dict],
                           asset_b: List[Dict]) -> Dict[str, Any]:

        closes_a = np.array([x["close"] for x in asset_a])
        closes_b = np.array([x["close"] for x in asset_b])

        min_len = min(len(closes_a), len(closes_b))

        closes_a = closes_a[-min_len:]
        closes_b = closes_b[-min_len:]

        score, pvalue, _ = coint(closes_a, closes_b)

        spread = closes_a - closes_b

        mean = np.mean(spread)
        std = np.std(spread)

        z_score = (spread[-1] - mean) / std if std > 0 else 0

        signal = "HOLD"

        if z_score > 2:
            signal = "SELL_SPREAD"

        elif z_score < -2:
            signal = "BUY_SPREAD"

        return {
            "signal": signal,
            "cointegration_pvalue": float(pvalue),
            "z_score": float(z_score),
            "spread_mean": float(mean),
            "spread_std": float(std)
        }
