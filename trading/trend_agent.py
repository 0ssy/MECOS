import numpy as np
import pandas as pd
from typing import Dict, List, Any
from loguru import logger

class TrendAgent:
    def __init__(self, memory):
        self.memory = memory
        self.short_window = 8
        self.medium_window = 21
        self.long_window = 55
        self.breakout_lookback = 20
        logger.info("Trend Agent initialized")

    async def analyze(self, data: List[Dict], features: Dict) -> Dict[str, Any]:
        prices = [d["close"] for d in data]
        momentum = float(features.get("roc_20", 0.0))
        trend_strength = float(features.get("trend_strength", 0.0))
        volatility = float(features.get("realized_volatility", 0.0))

        signal, score = get_trend_signal(
            prices,
            short_window=self.short_window,
            medium_window=self.medium_window,
            long_window=self.long_window,
            breakout_lookback=self.breakout_lookback,
        )

        # Favor trends with stronger momentum while penalizing very noisy regimes.
        signal_score = score + np.tanh(momentum * 8.0) * 0.25 + np.tanh(trend_strength * 12.0) * 0.2
        if volatility > 0.6:
            signal_score *= 0.8

        confidence = float(np.clip(abs(signal_score), 0.0, 0.95))
        if signal == "HOLD":
            confidence = min(confidence, 0.4)

        return {
            "signal": signal,
            "confidence": confidence,
            "trend_score": float(signal_score),
            "momentum": momentum,
            "trend_strength": trend_strength,
        }

def get_trend_signal(
    prices,
    short_window: int = 8,
    medium_window: int = 21,
    long_window: int = 55,
    breakout_lookback: int = 20,
):
    """
    Multi-horizon momentum + breakout trend model.
    Returns: (BUY / SELL / HOLD, signed_score)
    """
    try:
        min_history = max(long_window, breakout_lookback + 1)
        if prices is None or len(prices) < min_history:
            return "HOLD", 0.0

        series = pd.Series(prices)
        sma_short = float(series.tail(short_window).mean())
        sma_medium = float(series.tail(medium_window).mean())
        sma_long = float(series.tail(long_window).mean())

        current = float(series.iloc[-1])
        prev = float(series.iloc[-2])
        breakout_high = float(series.tail(breakout_lookback + 1).iloc[:-1].max())
        breakout_low = float(series.tail(breakout_lookback + 1).iloc[:-1].min())

        slope = (current / max(sma_medium, 1e-9)) - 1.0
        stacked_bull = sma_short > sma_medium > sma_long
        stacked_bear = sma_short < sma_medium < sma_long
        breakout_up = current > breakout_high and current > prev
        breakout_down = current < breakout_low and current < prev

        score = 0.0
        if stacked_bull:
            score += 0.55
        if stacked_bear:
            score -= 0.55
        if breakout_up:
            score += 0.35
        if breakout_down:
            score -= 0.35
        score += float(np.tanh(slope * 14.0) * 0.25)

        if score > 0.12:
            return "BUY", float(score)
        if score < -0.12:
            return "SELL", float(score)
        return "HOLD", float(score)
    except Exception as e:
        print(f"Trend calculation failed: {e}")
        return "HOLD", 0.0





