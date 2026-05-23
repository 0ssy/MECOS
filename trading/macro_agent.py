from typing import Dict, List, Any
import numpy as np
from loguru import logger

class MacroAgent:
    def __init__(self, memory):
        self.memory = memory
        logger.info('MacroAgent initialized')

    async def analyze(
        self,
        data: List[Dict],
        features: Dict,
        macro_data: Dict = None
    ) -> Dict[str, Any]:

        if not macro_data:
            return {
                'signal': 'HOLD',
                'confidence': 0.2,
                'reason': 'No macro data'
            }

        rates = macro_data.get('interest_rate_trend', 0)
        gdp = macro_data.get('gdp_growth', 0)
        inflation = macro_data.get('inflation', 0)

        score = 0

        if rates < 0:
            score += 0.25

        if gdp > 0.02:
            score += 0.35

        if inflation < 0.03:
            score += 0.20

        if score >= 0.5:
            signal = 'BUY'
        elif score <= -0.5:
            signal = 'SELL'
        else:
            signal = 'HOLD'

        return {
            'signal': signal,
            'confidence': float(abs(score)),
            'macro_score': float(score)
        }
