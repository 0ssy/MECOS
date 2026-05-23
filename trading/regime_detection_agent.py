import pandas as pd
import numpy as np
from typing import Dict, List, Any
from loguru import logger

class RegimeDetectionAgent:
    def __init__(self, memory):
        self.memory = memory
        self.lookback = 50
        logger.info("Regime Detection Agent initialized")

    async def detect_regime(self, data: List[Dict]) -> str:
        if len(data) < self.lookback:
            return "unknown"

        df = pd.DataFrame(data)
        close = df["close"]

        returns = np.diff(np.log(close + 1e-10))

        realized_vol = np.std(returns[-20:]) * np.sqrt(252)
        trend_strength = abs(close.iloc[-1] / close.iloc[-20] - 1)

        if realized_vol > 0.5:
            if trend_strength > 0.05:
                return "volatile_trend"
            return "panic"

        if trend_strength > 0.03:
            return "trending"

        if realized_vol < 0.15:
            return "low_volatility"

        return "ranging"
