from typing import Dict, List, Any
import numpy as np
from loguru import logger

class CrossAssetArbitrageAgent:
    def __init__(self, memory):
        self.memory = memory
        logger.info('CrossAssetArbitrageAgent initialized')

    async def analyze_spread(
        self,
        asset1_data: List[Dict],
        asset2_data: List[Dict]
    ) -> Dict[str, Any]:

        closes1 = np.array([x['close'] for x in asset1_data[-50:]])
        closes2 = np.array([x['close'] for x in asset2_data[-50:]])

        if len(closes1) < 20 or len(closes2) < 20:
            return {'signal': 'HOLD', 'confidence': 0}

        spread = closes1 - closes2

        mean_spread = np.mean(spread)
        std_spread = np.std(spread)

        if std_spread == 0:
            return {'signal': 'HOLD', 'confidence': 0}

        zscore = (spread[-1] - mean_spread) / std_spread

        signal = 'HOLD'
        confidence = min(abs(zscore) / 3, 1.0)

        if zscore > 2:
            signal = 'SELL_ASSET1_BUY_ASSET2'

        elif zscore < -2:
            signal = 'BUY_ASSET1_SELL_ASSET2'

        return {
            'signal': signal,
            'confidence': float(confidence),
            'spread_zscore': float(zscore)
        }
