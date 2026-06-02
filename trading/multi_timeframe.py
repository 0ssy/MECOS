from __future__ import annotations

from typing import Dict, List

import numpy as np


class MultiTimeframeAnalyzer:
    """Computes simple MTF trend/RSI alignment from an existing bar stream."""

    @staticmethod
    def _rsi(close: np.ndarray, period: int = 14) -> float:
        if close.size <= period:
            return 50.0
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.mean(gain[-period:])
        avg_loss = np.mean(loss[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100.0 - (100.0 / (1.0 + rs)))

    def analyze_bars(self, bars: List[Dict]) -> Dict[str, object]:
        closes = np.asarray([float(b.get("close", 0.0) or 0.0) for b in bars if "close" in b], dtype=float)
        if closes.size < 30:
            return {
                "alignment_score": 0.0,
                "timeframes": {},
                "composite_trend": "unknown",
            }

        # Approximate lower-frequency bars by striding.
        tf_series = {
            "15m": closes[-96:],
            "1h": closes[-120::4],
            "4h": closes[-240::16],
            "1d": closes[-400::96],
        }
        views: Dict[str, Dict[str, float | str]] = {}
        votes = []
        for tf, series in tf_series.items():
            if series.size < 20:
                continue
            ma20 = float(np.mean(series[-20:]))
            last = float(series[-1])
            trend = "up" if last >= ma20 else "down"
            votes.append(1.0 if trend == "up" else -1.0)
            views[tf] = {
                "price": last,
                "ma20": ma20,
                "trend": trend,
                "rsi": self._rsi(series, period=14),
            }

        alignment = float(np.mean(votes)) if votes else 0.0
        composite = "bullish" if alignment > 0.3 else "bearish" if alignment < -0.3 else "mixed"
        return {
            "alignment_score": alignment,
            "timeframes": views,
            "composite_trend": composite,
        }
