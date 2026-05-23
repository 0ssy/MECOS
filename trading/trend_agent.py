import numpy as np
from typing import Dict, List, Any
from loguru import logger

class TrendAgent:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Trend Agent initialized")

    async def analyze(self, data: List[Dict], features: Dict) -> Dict[str, Any]:

        closes = np.array([d["close"] for d in data])

        if len(closes) < 30:
            return {"signal": "HOLD", "confidence": 0}

        sma_10 = np.mean(closes[-10:])
        sma_30 = np.mean(closes[-30:])

        momentum = closes[-1] / closes[-10] - 1

        if sma_10 > sma_30 and momentum > 0:
            signal = "BUY"
            confidence = min(abs(momentum) * 10, 0.9)

        elif sma_10 < sma_30 and momentum < 0:
            signal = "SELL"
            confidence = min(abs(momentum) * 10, 0.9)

        else:
            signal = "HOLD"
            confidence = 0.3

        return {
            "signal": signal,
            "confidence": float(confidence),
            "momentum": float(momentum)
        }
