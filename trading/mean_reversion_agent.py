"""
Mean Reversion Trading Agent
Statistical arbitrage, pairs trading, reversion to mean
"""
import numpy as np
from typing import Dict, Any, List
from loguru import logger

class MeanReversionAgent:
    """Mean reversion strategy specialist"""
    
    def __init__(self, memory):
        self.memory = memory
        self.lookback = 20
        self.entry_threshold = 1.5  # Z-score threshold (lowered from 2.0 for liquid ETFs)
        self.exit_threshold = 0.5
        logger.info("Mean Reversion Agent initialized")
    
    async def analyze(self, data: List[Dict], features: Dict) -> Dict[str, Any]:
        """Analyze mean reversion opportunity"""
        
        if len(data) < self.lookback:
            return {"signal": "HOLD", "confidence": 0, "reason": "Insufficient data"}
        
        close = np.array([d['close'] for d in data])
        
        # Calculate z-score
        mean = np.mean(close[-self.lookback:])
        std = np.std(close[-self.lookback:])
        current = close[-1]
        
        z_score = (current - mean) / std if std > 0 else 0
        
        # Mean reversion score from features
        mean_rev_score = features.get('mean_reversion_score', features.get('z_score', 0.0))
        autocorr = features.get('autocorr_1', -0.05)
        
        # Signal generation
        signal = "HOLD"
        confidence = 0
        
        # Strong mean reversion (negative autocorrelation)
        if autocorr < -0.04:
            if z_score > self.entry_threshold:
                signal = "SELL"  # Overextended, revert down
                confidence = min(abs(z_score) / 3.0, 0.9)
            elif z_score < -self.entry_threshold:
                signal = "BUY"  # Oversold, revert up
                confidence = min(abs(z_score) / 3.0, 0.9)
            elif abs(z_score) < self.exit_threshold:
                signal = "EXIT"  # Back to mean
                confidence = 0.7
        
        return {
            "signal": signal,
            "confidence": float(confidence),
            "z_score": float(z_score),
            "mean_reversion_strength": float(abs(autocorr)),
            "reason": f"Z-score: {z_score:.2f}, Autocorr: {autocorr:.2f}"
        }




