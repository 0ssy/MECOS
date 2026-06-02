from __future__ import annotations

from typing import Dict, Iterable

import numpy as np


class RegimeDetector:
    """Rule-based market regime detector from local bars."""

    @staticmethod
    def detect_from_bars(close_prices: Iterable[float]) -> Dict[str, float | str]:
        px = np.asarray([float(v) for v in close_prices if v is not None], dtype=float)
        if px.size < 30:
            return {"regime": "unknown", "trend_strength": 0.0, "volatility": 0.0}

        sma20 = float(np.mean(px[-20:]))
        sma50 = float(np.mean(px[-50:])) if px.size >= 50 else float(np.mean(px))
        ret = np.diff(np.log(np.maximum(px, 1e-12)))
        vol = float(np.std(ret[-20:]) * np.sqrt(252.0)) if ret.size >= 20 else 0.0
        trend_strength = (sma20 / sma50 - 1.0) if sma50 != 0 else 0.0

        if trend_strength > 0.015 and vol < 0.55:
            regime = "bull"
        elif trend_strength < -0.015:
            regime = "bear"
        elif vol > 0.80:
            regime = "panic"
        else:
            regime = "sideways"

        return {
            "regime": regime,
            "trend_strength": float(trend_strength),
            "volatility": vol,
        }
