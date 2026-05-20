import numpy as np
from scipy.stats import norm
from loguru import logger
from typing import Dict, Any
from trading.config import TradingConfig

class OptionsPricingAgent:
    def __init__(self, memory_system):
        self.memory = memory_system
        logger.info("OptionsPricingAgent initialized.")

    def black_scholes(self, S, K, T, sigma, opt_type="call"):
        r = TradingConfig.RISK_FREE_RATE
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if opt_type == "call":
            p, delta = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2), norm.cdf(d1)
        else:
            p, delta = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1), -norm.cdf(-d1)
        return {"price": p, "delta": delta, "gamma": norm.pdf(d1) / (S * sigma * np.sqrt(T)), "vega": S * norm.pdf(d1) * np.sqrt(T)}

    async def price_options(self, data: Dict) -> Dict[str, Any]:
        S, K, T, sigma = data.get("S"), data.get("K"), data.get("T"), data.get("sigma")
        if None in [S, K, T, sigma]: return {"error": "Missing data"}
        return self.black_scholes(S, K, T, sigma, data.get("type", "call"))
