from __future__ import annotations

from typing import Dict

import numpy as np
from scipy.stats import norm


class OptionsEngine:
    """Vanilla Black-Scholes pricing, IV solver, and Greeks."""

    @staticmethod
    def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
        S = max(float(S), 1e-12)
        K = max(float(K), 1e-12)
        T = max(float(T), 1e-12)
        sigma = max(float(sigma), 1e-9)
        d1 = (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return float(d1), float(d2)

    def black_scholes(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
    ) -> float:
        d1, d2 = self._d1_d2(S, K, T, r, sigma)
        discount = np.exp(-r * max(float(T), 0.0))
        t = str(option_type or "call").strip().lower()
        if t == "put":
            return float(K * discount * norm.cdf(-d2) - S * norm.cdf(-d1))
        return float(S * norm.cdf(d1) - K * discount * norm.cdf(d2))

    def implied_volatility(
        self,
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str = "call",
        max_iter: int = 100,
    ) -> float:
        target = max(float(market_price), 0.0)
        lo, hi = 1e-4, 5.0
        for _ in range(max(5, int(max_iter))):
            mid = (lo + hi) / 2.0
            price = self.black_scholes(S, K, T, r, mid, option_type)
            if price > target:
                hi = mid
            else:
                lo = mid
        return float((lo + hi) / 2.0)

    def greeks(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "call",
    ) -> Dict[str, float]:
        d1, d2 = self._d1_d2(S, K, T, r, sigma)
        root_t = np.sqrt(max(float(T), 1e-12))
        pdf = norm.pdf(d1)
        call = str(option_type or "call").strip().lower() != "put"

        if call:
            delta = norm.cdf(d1)
            theta = (-(S * pdf * sigma) / (2 * root_t) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365.0
            rho = (K * T * np.exp(-r * T) * norm.cdf(d2)) / 100.0
        else:
            delta = norm.cdf(d1) - 1.0
            theta = (-(S * pdf * sigma) / (2 * root_t) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365.0
            rho = (-K * T * np.exp(-r * T) * norm.cdf(-d2)) / 100.0

        gamma = pdf / (max(S, 1e-12) * max(sigma, 1e-9) * root_t)
        vega = (S * pdf * root_t) / 100.0

        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "theta": float(theta),
            "vega": float(vega),
            "rho": float(rho),
        }
