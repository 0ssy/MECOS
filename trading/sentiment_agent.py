"""
Market Sentiment Agent
Analyzes market sentiment, fear/greed
"""
import numpy as np
from typing import Dict, Any, List
from loguru import logger

class SentimentAgent:
    """Market sentiment analysis"""
    
    def __init__(self, memory):
        self.memory = memory
        logger.info("Sentiment Agent initialized")
    
    async def analyze(self, data: List[Dict], features: Dict) -> Dict[str, Any]:
        """Analyze market sentiment"""
        
        # Use price action as sentiment proxy
        roc_5 = features.get('roc_5', 0)
        roc_20 = features.get('roc_20', 0)
        volume_ratio = features.get('volume_ratio', 1.0)
        
        # Calculate sentiment score
        price_sentiment = (roc_5 * 0.6 + roc_20 * 0.4)
        volume_sentiment = np.tanh(volume_ratio - 1)  # Normalize
        
        sentiment_score = price_sentiment + volume_sentiment * 0.3
        
        # Classify sentiment
        if sentiment_score > 0.05:
            sentiment = "BULLISH"
            signal = "BUY"
        elif sentiment_score < -0.05:
            sentiment = "BEARISH"
            signal = "SELL"
        else:
            sentiment = "NEUTRAL"
            signal = "HOLD"
        
        # Fear/Greed extremes (contrarian)
        if sentiment_score > 0.15:  # Extreme greed
            signal = "SELL"  # Fade the euphoria
            confidence = min(abs(sentiment_score) * 3, 0.8)
            sentiment = "EXTREME_GREED"
        elif sentiment_score < -0.15:  # Extreme fear
            signal = "BUY"  # Buy the fear
            confidence = min(abs(sentiment_score) * 3, 0.8)
            sentiment = "EXTREME_FEAR"
        else:
            confidence = min(abs(sentiment_score) * 2, 0.7)
        
        return {
            "signal": signal,
            "confidence": float(confidence),
            "sentiment": sentiment,
            "sentiment_score": float(sentiment_score),
            "reason": f"Sentiment: {sentiment}, Score: {sentiment_score:.3f}"
        }
