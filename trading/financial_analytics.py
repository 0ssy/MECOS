from __future__ import annotations

from typing import Dict, Iterable, List

import numpy as np


class FinancialAnalytics:
    """Lightweight risk and return analytics for decision context."""

    @staticmethod
    def _to_prices(prices: Iterable[float]) -> np.ndarray:
        values = np.asarray([float(p) for p in prices if p is not None], dtype=float)
        return values[~np.isnan(values)]

    def returns(self, prices: Iterable[float]) -> np.ndarray:
        px = self._to_prices(prices)
        if px.size < 2:
            return np.asarray([], dtype=float)
        prev = px[:-1]
        curr = px[1:]
        valid = prev != 0.0
        if not np.any(valid):
            return np.asarray([], dtype=float)
        return (curr[valid] / prev[valid]) - 1.0

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        if returns.size == 0:
            return 0.0
        std = float(np.std(returns))
        if std <= 0.0:
            return 0.0
        excess = float(np.mean(returns)) - (risk_free_rate / 252.0)
        return float((excess / std) * np.sqrt(252.0))

    @staticmethod
    def historical_var(returns: np.ndarray, confidence: float = 0.95) -> float:
        if returns.size == 0:
            return 0.0
        percentile = max(0.0, min(100.0, (1.0 - confidence) * 100.0))
        return float(np.percentile(returns, percentile))

    @staticmethod
    def max_drawdown(prices: Iterable[float]) -> float:
        px = np.asarray([float(p) for p in prices if p is not None], dtype=float)
        if px.size == 0:
            return 0.0
        running_peak = np.maximum.accumulate(px)
        drawdowns = (px - running_peak) / np.maximum(running_peak, 1e-12)
        return float(np.min(drawdowns))

    def summarize_prices(self, prices: List[float]) -> Dict[str, float]:
        px = self._to_prices(prices)
        r = self.returns(px.tolist())
        volatility = float(np.std(r) * np.sqrt(252.0)) if r.size else 0.0
        return {
            "sample_size": float(px.size),
            "latest_price": float(px[-1]) if px.size else 0.0,
            "annualized_volatility": volatility,
            "sharpe": self.sharpe_ratio(r),
            "var_95": self.historical_var(r, confidence=0.95),
            "max_drawdown": self.max_drawdown(px.tolist()),
        }
