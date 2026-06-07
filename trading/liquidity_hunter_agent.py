"""
Liquidity Hunter Agent
Detects liquidity events, hunts stop-loss cascades
"""
import numpy as np
from typing import Dict, Any, List
from loguru import logger

class LiquidityHunterAgent:
    """Hunts liquidity events and cascades"""
    
    def __init__(self, memory):
        self.memory = memory
        logger.info("Liquidity Hunter Agent initialized")
    
    async def analyze(self, data: List[Dict], features: Dict) -> Dict[str, Any]:
        """Detect liquidity events"""
        
        volume_ratio = features.get('volume_ratio', 1.0)
        spread = features.get('spread_pressure', 0.001)
        liquidity_score = features.get('liquidity_score', 1.0)
        
        close = np.array([d['close'] for d in data[-10:]])
        
        signal = "HOLD"
        confidence = 0
        
        # Liquidity drought detection
        if liquidity_score < 0.5 and spread > 0.01:
            # Low liquidity - avoid trading
            signal = "AVOID"
            confidence = 0.8
        
        # Volume spike detection (potential cascade)
        elif volume_ratio > 3.0:
            # Unusual volume - potential stop-loss cascade
            price_move = (close[-1] - close[0]) / close[0]
            
            if price_move < -0.02:  # Down move with volume
                signal = "BUY"  # Fade the panic
                confidence = min(volume_ratio / 5.0, 0.8)
            elif price_move > 0.02:  # Up move with volume
                signal = "SELL"  # Fade the squeeze
                confidence = min(volume_ratio / 5.0, 0.8)
        
        # Normal liquidity conditions
        elif liquidity_score > 0.8:
            signal = "BUY"  # Good conditions to trade
            confidence = 0.6
        
        return {
            "signal": signal,
            "confidence": float(confidence),
            "liquidity_score": float(liquidity_score),
            "volume_ratio": float(volume_ratio),
            "reason": f"Liquidity: {liquidity_score:.2f}, Volume: {volume_ratio:.2f}x"
        }


