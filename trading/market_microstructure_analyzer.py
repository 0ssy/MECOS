from typing import Dict, Any
from loguru import logger
import numpy as np

class MKDvoVT7E8tdF4vmk78us6XYnsxz3iik5U:
    def __init__(self, memory):
        self.memory = memory
        logger.info('MKDvoVT7E8tdF4vmk78us6XYnsxz3iik5U initialized')

    async def analyze(self, orderbook: Dict) -> Dict[str, Any]:

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return {'imbalance': 0}

        bid_volume = sum([b[1] for b in bids])
        ask_volume = sum([a[1] for a in asks])

        total = bid_volume + ask_volume

        imbalance = 0 if total == 0 else (bid_volume - ask_volume) / total

        spread = asks[0][0] - bids[0][0]

        return {
            'imbalance': float(imbalance),
            'spread': float(spread),
            'bid_volume': float(bid_volume),
            'ask_volume': float(ask_volume)
        }
