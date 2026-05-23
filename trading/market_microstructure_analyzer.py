import numpy as np
from typing import Dict, List, Any
from loguru import logger

class MarketMicrostructureAnalyzer:
    def __init__(self, memory):
        self.memory = memory
        logger.info("Market Microstructure Analyzer initialized")

    async def analyze_orderbook(self,
                                bids: List[Dict],
                                asks: List[Dict]) -> Dict[str, Any]:

        total_bid_volume = sum([b["size"] for b in bids])
        total_ask_volume = sum([a["size"] for a in asks])

        imbalance = (
            total_bid_volume - total_ask_volume
        ) / max(total_bid_volume + total_ask_volume, 1)

        best_bid = max([b["price"] for b in bids])
        best_ask = min([a["price"] for a in asks])

        spread = best_ask - best_bid

        if imbalance > 0.2:
            pressure = "BUY_PRESSURE"

        elif imbalance < -0.2:
            pressure = "SELL_PRESSURE"

        else:
            pressure = "NEUTRAL"

        return {
            "orderbook_imbalance": float(imbalance),
            "spread": float(spread),
            "pressure": pressure,
            "bid_volume": float(total_bid_volume),
            "ask_volume": float(total_ask_volume)
        }
